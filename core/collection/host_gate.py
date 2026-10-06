"""
Per-host request spacing shared by separate collector processes.

An adapter spaces its own requests. That cannot stop two runs started back to
back, in two processes, from reaching the same host closer together than the
interval: each process starts with no memory of the other. This gate closes
that gap. Every process that names the same gate directory shares, per host,
one lock file and one record of when the last request to that host ended.

    with gate.slot("moit.gov.vn", 2.0) as slot:
        ... make exactly one request, read it and close it ...

`slot` takes the host's exclusive lock and holds it for the whole request, so
two processes can never have requests to one host in flight at once. It then
waits until the interval has passed since the END of the previous request,
whichever process made it, records the start, and on exit records the end. If
a process dies mid-request its record is left open; the next request then
treats the previous one as ending now and waits the full interval.

The interval is the longer of the one the caller asks for and the one recorded
for the host. A caller that reads a longer published Crawl-delay during a
request calls `slot.require(delay)` before the slot closes, so the delay is
recorded with that request's end and binds the very next request to the host,
from any process, including one that has not read robots.txt yet. The
recorded interval never decreases within a gate directory.

Times are wall-clock epoch seconds, because they are compared across
processes. A wait is never longer than the interval plus the margin: a record
dated in the future (a clock stepped back, or a seed from evidence) can
lengthen a wait to the full interval but never stall a run. Every wait carries
a small margin so that float rounding can never land a request a hair inside
the interval.

`seed(host, epoch)` records evidence of an earlier request's end that this
directory never saw, such as a run on another machine whose ledger was read
from its state branch. A seed never lowers what is already recorded.

The gate is a floor, not a scheduler. It makes no request, and holds no state
outside its directory. Nothing here reads or writes production storage.
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional

#: A lower-case DNS host name. It becomes a file name, so nothing else passes.
_HOST_RE = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
                      r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$")

#: Added to every wait that is not zero.
MARGIN = 0.005

#: A recorded interval above this is a damaged record, not a requirement.
#: Adapters refuse a Crawl-delay above their own ceiling before asking for it.
MAX_INTERVAL = 120.0


class GateError(RuntimeError):
    """The gate could not be used: a bad host name, directory or record, or a lock timeout."""


@dataclass
class Slot:
    """What one request's passage through the gate measured."""
    host: str
    #: The interval actually applied: the longer of the requested and recorded.
    interval: float
    waited: float
    started: float
    #: The recorded end of the previous request to this host, if any.
    previous_end: Optional[float]
    #: True when the previous holder died mid-request and the full interval was waited.
    recovered_open: bool
    ended: Optional[float] = None
    #: A longer interval the host published during this request (see `require`).
    required: Optional[float] = None

    def require(self, interval: float) -> None:
        """Record, when the slot closes, that the host needs at least `interval` s."""
        if not 0 < interval <= MAX_INTERVAL:
            raise GateError("interval %r s is outside (0, %s]" % (interval, MAX_INTERVAL))
        self.required = max(self.required or 0.0, float(interval))


class HostGate:
    def __init__(self, directory, sleeper: Callable[[float], None] = time.sleep,
                 wall: Callable[[], float] = time.time,
                 lock_timeout: float = 600.0) -> None:
        self.directory = Path(directory)
        self._sleep = sleeper
        self._wall = wall
        self._lock_timeout = lock_timeout
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise GateError("gate directory %s is unusable: %s" % (self.directory, exc))
        if self.directory.is_symlink() or not self.directory.is_dir():
            raise GateError("gate directory %s is not a plain directory" % self.directory)

    # -- files ----------------------------------------------------------------

    def _paths(self, host: str):
        if not isinstance(host, str) or not _HOST_RE.match(host):
            raise GateError("not a lower-case host name: %r" % (host,))
        return self.directory / (host + ".lock"), self.directory / (host + ".json")

    @contextmanager
    def _locked(self, host: str) -> Iterator[Path]:
        lock_path, record_path = self._paths(host)
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            # Lock contention is real time, whatever sleeper the gate was given.
            deadline = time.monotonic() + self._lock_timeout
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                        raise
                    if time.monotonic() >= deadline:
                        raise GateError("timed out waiting for the %s gate" % host)
                    time.sleep(0.05)
            yield record_path
        finally:
            os.close(fd)   # closing the descriptor releases the lock

    @staticmethod
    def _read(record_path: Path) -> dict:
        if not record_path.exists():
            return {"last_end": None, "open_since": None, "interval": None}
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            for key in ("last_end", "open_since", "interval"):
                if record.get(key) is not None:
                    record[key] = float(record[key])
                else:
                    record[key] = None
        except (ValueError, TypeError, AttributeError) as exc:
            # An unreadable record is never read as "no previous request".
            raise GateError("gate record %s is unreadable: %s" % (record_path, exc))
        if record["interval"] is not None and not 0 < record["interval"] <= MAX_INTERVAL:
            raise GateError("gate record %s holds an interval of %r s"
                            % (record_path, record["interval"]))
        return record

    def _write(self, record_path: Path, record: dict) -> None:
        fd, tmp = tempfile.mkstemp(prefix=record_path.name + ".", dir=str(self.directory))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True) + "\n")
            os.replace(tmp, str(record_path))
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # -- use ------------------------------------------------------------------

    def record(self, host: str) -> dict:
        """The host's current record, for evidence and tests."""
        with self._locked(host) as record_path:
            return self._read(record_path)

    def seed(self, host: str, epoch: float) -> None:
        """Record that a request to `host` ended no later than `epoch`."""
        with self._locked(host) as record_path:
            record = self._read(record_path)
            if record["last_end"] is None or float(epoch) > record["last_end"]:
                record.update(host=host, last_end=float(epoch))
                self._write(record_path, record)

    @contextmanager
    def slot(self, host: str, interval: float) -> Iterator[Slot]:
        if not 0 < interval <= MAX_INTERVAL:
            raise GateError("interval %r s is outside (0, %s]" % (interval, MAX_INTERVAL))
        with self._locked(host) as record_path:
            record = self._read(record_path)
            interval = max(interval, record["interval"] or 0.0)
            now = self._wall()
            recovered = record["open_since"] is not None
            reference = now if recovered else record["last_end"]
            wait = 0.0
            if reference is not None:
                elapsed = now - reference
                if elapsed < interval:
                    wait = min(interval, interval - elapsed) + MARGIN
            if wait > 0:
                self._sleep(wait)
            started = self._wall()
            record.update(host=host, interval=interval, open_since=started, pid=os.getpid())
            self._write(record_path, record)
            slot = Slot(host, interval, wait, started, record["last_end"], recovered)
            try:
                yield slot
            finally:
                slot.ended = self._wall()
                last = record["last_end"]
                record.update(open_since=None,
                              last_end=slot.ended if last is None else max(last, slot.ended),
                              interval=max(interval, slot.required or 0.0))
                self._write(record_path, record)
