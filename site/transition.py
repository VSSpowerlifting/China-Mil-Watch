"""
The URL transition map — loader, resolver and validator.

`site/url_transition_map.json` is the promise: every route the site publishes
today, and what happens to it when Indo-Pacific Record launches. This module is
what makes the promise checkable, and the tests that read it are what stop it
drifting between now and the launch that executes it.

Nothing here deploys anything. It writes no redirect, changes no DNS, selects
no domain, and is not imported by the production renderer. It is a plan and a
checker for a plan.

Why a resolver and not just a table
-----------------------------------
Two of the failures this map exists to prevent are not visible by reading it:

  * a redirect chain that loops, or that needs more than one hop
  * a rule that quietly sends many distinct records to one page

Both are properties of the map as a whole rather than of any row, so both are
computed here and asserted in tests.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = REPO_ROOT / "site" / "url_transition_map.json"
PRODUCTION_OUT = REPO_ROOT / "output"

#: Every disposition a route may carry. A row using anything else fails the
#: load: an unrecognised disposition is an unanswered question about a public
#: URL, not a value to pass through.
DISPOSITIONS = ("preserve", "move", "legacy_archive", "owner_decision",
                "evidence")

#: Placeholders a pattern route may use. Kept closed so a typo in a pattern
#: cannot silently match nothing.
PLACEHOLDERS = ("{id}", "{date}", "{file}", "{slug}", "{start}")

_PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}")


class TransitionMapError(ValueError):
    """Raised when the transition map is malformed. Never caught internally."""


@dataclass(frozen=True)
class Route:
    old: str
    new: str
    disposition: str
    redirect: bool
    canonical: Optional[str]
    legacy_label: bool
    pattern: bool = False
    evidence: bool = False
    note: str = ""

    @property
    def moves(self) -> bool:
        return self.old != self.new


@dataclass(frozen=True)
class TransitionMap:
    routes: List[Route]
    new_routes: List[str]
    dispositions: Dict[str, str]

    def __iter__(self):
        return iter(self.routes)

    def __len__(self) -> int:
        return len(self.routes)

    def get(self, old: str) -> Optional[Route]:
        for route in self.routes:
            if route.old == old:
                return route
        return None

    @property
    def redirects(self) -> List[Route]:
        return [r for r in self.routes if r.redirect]

    @property
    def evidence_routes(self) -> List[Route]:
        return [r for r in self.routes if r.evidence]

    def resolve(self, old: str, _seen=None) -> str:
        """
        Follow the map from an old address to where it finally lands.

        Raises on a cycle rather than returning something. A redirect loop is
        not a degraded experience — it is a URL that has stopped existing while
        appearing to exist, which is worse than a 404 for anyone checking a
        citation.
        """
        seen = list(_seen or [])
        if old in seen:
            raise TransitionMapError(
                "redirect loop: %s" % " -> ".join(seen + [old]))
        seen.append(old)
        route = self.get(old)
        if route is None or not route.redirect or route.new == old:
            return old
        return self.resolve(route.new, seen)

    def hops(self, old: str) -> int:
        """How many redirects a reader traverses from `old`."""
        count = 0
        current = old
        seen = [current]
        while True:
            route = self.get(current)
            if route is None or not route.redirect or route.new == current:
                return count
            current = route.new
            if current in seen:
                raise TransitionMapError(
                    "redirect loop: %s" % " -> ".join(seen + [current]))
            seen.append(current)
            count += 1


def _require(raw: dict, key: str, where: str):
    if key not in raw:
        raise TransitionMapError("%s: missing required field %r" % (where, key))
    return raw[key]


def load_map(path: Optional[Path] = None) -> TransitionMap:
    path = Path(path) if path is not None else MAP_PATH
    if not path.is_file():
        raise TransitionMapError("transition map not found: %s" % path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TransitionMapError("%s: invalid JSON — %s" % (path, exc))

    if raw.get("map_version") != 1:
        raise TransitionMapError(
            "%s: unsupported map_version %r" % (path, raw.get("map_version")))

    routes: List[Route] = []
    seen = set()
    for index, item in enumerate(raw.get("routes") or []):
        where = "%s: routes[%d]" % (path.name, index)
        old = _require(item, "old", where)
        if old in seen:
            raise TransitionMapError("%s: duplicate route %r" % (where, old))
        seen.add(old)
        disposition = _require(item, "disposition", where)
        if disposition not in DISPOSITIONS:
            raise TransitionMapError(
                "%s: %r is not a valid disposition (permitted: %s)"
                % (where, disposition, ", ".join(DISPOSITIONS)))
        pattern = bool(item.get("pattern", False))
        for field in ("old", "new"):
            value = item.get(field) or ""
            for placeholder in _PLACEHOLDER_RE.findall(value):
                if placeholder not in PLACEHOLDERS:
                    raise TransitionMapError(
                        "%s: unknown placeholder %s in %s"
                        % (where, placeholder, field))
            if _PLACEHOLDER_RE.search(value) and not pattern:
                raise TransitionMapError(
                    "%s: %s carries a placeholder but the route is not marked "
                    "as a pattern" % (where, field))
        routes.append(Route(
            old=old,
            new=_require(item, "new", where),
            disposition=disposition,
            redirect=bool(_require(item, "redirect", where)),
            canonical=item.get("canonical"),
            legacy_label=bool(item.get("legacy_label", False)),
            pattern=pattern,
            evidence=bool(item.get("evidence", False)),
            note=item.get("note", ""),
        ))

    if not routes:
        raise TransitionMapError("%s: 'routes' must not be empty" % path)

    return TransitionMap(
        routes=routes,
        new_routes=list(raw.get("new_routes") or []),
        dispositions=dict(raw.get("dispositions") or {}),
    )


#: What the predecessor published, frozen at launch. See the file's own header.
PREDECESSOR_ROUTES = Path(__file__).resolve().parent / "predecessor_routes.txt"


def predecessor_routes(path: Optional[Path] = None) -> List[str]:
    """
    Every route China Mil Watch served, as map patterns.

    Frozen rather than derived. `production_routes()` below reads the deployed
    tree, which was the right source for this question while the deployed tree
    *was* the predecessor's. Since the launch it is Indo-Pacific Record's, and
    asking it what the predecessor published would get an answer about the
    successor. The transition map is a promise about addresses that existed;
    this is the record of which addresses those were.
    """
    source = Path(path or PREDECESSOR_ROUTES)
    routes = []
    for line in source.read_text(encoding="utf-8").splitlines():
        route = line.strip()
        if route and not route.startswith("#"):
            routes.append(route)
    return sorted(set(routes))


def production_routes(output_dir: Optional[Path] = None) -> List[str]:
    """
    Every route a built tree serves, as map patterns.

    Still derived rather than listed, and still the right tool for asking what
    a tree in hand actually contains — the launch verification uses it on the
    freshly built site. It is no longer the answer to "what did the predecessor
    publish": use `predecessor_routes()` for that.

    Directory-index files also yield their bare directory address, because that
    is the address people actually hold.
    """
    out = Path(output_dir or PRODUCTION_OUT)
    if not out.is_dir():
        return []
    collapse = (
        (re.compile(r"^/article/\d+\.html$"), "/article/{id}.html"),
        (re.compile(r"^/the-pla-watch/posts/[\d-]+\.html$"),
         "/the-pla-watch/posts/{date}.html"),
        (re.compile(r"^/the-pla-watch/posts/[\d-]+\.json$"),
         "/the-pla-watch/posts/{date}.json"),
        (re.compile(r"^/the-pla-watch/covers/.+$"),
         "/the-pla-watch/covers/{file}"),
        (re.compile(r"^/the-pla-watch/media/.+$"),
         "/the-pla-watch/media/{file}"),
        (re.compile(r"^/assets/editorial/.+$"), "/assets/editorial/{file}"),
    )
    found = set()
    for path in out.rglob("*"):
        if not path.is_file():
            continue
        route = "/" + str(path.relative_to(out))
        for probe, replacement in collapse:
            if probe.match(route):
                route = replacement
                break
        found.add(route)
        if route.endswith("/index.html"):
            found.add(route[: -len("index.html")])
    return sorted(found)
