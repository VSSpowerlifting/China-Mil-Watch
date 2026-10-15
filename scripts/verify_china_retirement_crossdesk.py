"""Verify a China-only archive retirement preserves unrelated live desk data.

Compare exact SQLite source rows and DDL on the source database and the
throwaway retired database. The four U.S. first-party metadata tables and the live Korea MND official-link
table are independent of the article corpus. Their rows and complete schemas
must remain byte-for-byte equivalent across a 4,400-row China deletion.

Read-only: the source uses the repository's read_only helper; the destination
uses immutable SQLite URI. This script neither publishes nor modifies a DB.
"""
import argparse
from html.parser import HTMLParser
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from scripts.reconcile_db import read_only

PRESERVED = (
    "sources",
    "uscc_official_source_records",
    "uscc_official_observations",
    "treasury_official_source_records",
    "treasury_official_observations",
    "korea_official_source_records",
)
SOURCE_FAMILIES = (
    ("uscc_official_source_records", "uscc_official_observations"),
    ("treasury_official_source_records", "treasury_official_observations"),
)


def _encode(v):
    """Preserve SQLite type differences, bytes, and exact float bit-equivalent text."""
    if v is None:
        return ["null"]
    if type(v) is int:
        return ["int", str(v)]
    if type(v) is float:
        return ["real", v.hex()]
    if type(v) is bytes:
        return ["blob", v.hex()]
    if type(v) is str:
        return ["text", v]
    raise ValueError("unknown SQLite column type")


def _snapshot(con, table):
    if not con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone():
        return None
    escaped = '"' + table.replace('"', '""') + '"'
    rows = [
        json.dumps([_encode(v) for v in row], ensure_ascii=False,
                   separators=(",", ":"), sort_keys=True)
        for row in con.execute("SELECT * FROM " + escaped)
    ]
    rows.sort()
    ddl = sorted(
        (str(typ), str(name), str(sql) if sql is not None else "")
        for typ, name, sql in con.execute(
            "SELECT type,name,sql FROM sqlite_master "
            "WHERE (name=? AND type='table') "
            "OR (tbl_name=? AND type IN ('index','trigger'))",
            (table, table),
        )
    )
    payload = json.dumps({"schema": ddl, "rows": rows}, ensure_ascii=False,
                         separators=(",", ":"), sort_keys=True).encode()
    return {"rows": len(rows), "sha256": sha256(payload).hexdigest(),
            "schema_sha256": sha256(
                json.dumps(ddl, separators=(",", ":")).encode()
            ).hexdigest()}


def validate(source_db, retired_db):
    source_db = Path(source_db).resolve(strict=True)
    retired_db = Path(retired_db).resolve(strict=True)
    if source_db == retired_db:
        raise ValueError("source and retired database must be distinct")
    with read_only(source_db) as original:
        with sqlite3.connect(retired_db.as_uri() + "?mode=ro&immutable=1",
                             uri=True) as reduced:
            before = {t: _snapshot(original, t) for t in PRESERVED}
            after = {t: _snapshot(reduced, t) for t in PRESERVED}
            if before["korea_official_source_records"] is not None:
                korea_released = sorted(
                    (str(identity), str(url), str(day))
                    for identity, url, day in original.execute(
                        "SELECT source_identity,canonical_official_url,"
                        "publisher_posted_date FROM korea_official_source_records "
                        "WHERE public_scope='official_link_only'"
                    )
                )
            else:
                korea_released = []
    if before["sources"] is None:
        raise ValueError("source registry table missing in original SQLite")
    for a, b in SOURCE_FAMILIES:
        if (before[a] is None) != (before[b] is None):
            raise ValueError("partial official metadata family in original SQLite: " + a)
    for table in PRESERVED:
        if before[table] != after[table]:
            raise ValueError(
                "Unrelated desk source table changed during China retirement: " + table
            )
    return {
        "preserved_tables": {
            table: snapshot for table, snapshot in before.items()
            if snapshot is not None
        },
        "korea_released_official_links": korea_released,
        "official_source_rows": {
            table: before[table]["rows"] if before[table] is not None else None
            for table in (
                "uscc_official_source_records", "treasury_official_source_records"
            )
        },
    }



class _OfficialUSLinkParser(HTMLParser):
    """stdlib HTML parser for the two first-party US desk link families."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = {
            "uscc_official_source_records": [],
            "treasury_official_source_records": [],
        }
        self.active = None
        self.all_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "li":
            for attr, family in (
                ("data-uscc-official-link", "uscc_official_source_records"),
                ("data-us-treasury-official-link",
                 "treasury_official_source_records"),
            ):
                if attr in attrs:
                    if self.active is not None:
                        raise ValueError("nested U.S. metadata link item")
                    self.active = {
                        "family": family, "identity": attrs[attr],
                        "href": None, "dates": [], "text": [],
                    }
                    break
        if self.active is not None:
            if tag == "a" and self.active["href"] is None:
                self.active["href"] = attrs.get("href")
            elif tag == "time" and attrs.get("datetime") is not None:
                self.active["dates"].append(attrs["datetime"])

    def handle_data(self, data):
        self.all_text.append(data)
        if self.active is not None:
            self.active["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "li" and self.active is not None:
            item = self.active
            if not item["href"] or not item["identity"]:
                raise ValueError("official U.S. metadata lacks source identity or URL")
            self.rows[item["family"]].append(
                (item["identity"], item["href"], tuple(item["dates"]),
                 " ".join(" ".join(item["text"]).split()))
            )
            self.active = None


def verify_us_public_link_parity(before_site, after_site, sqlite_receipt):
    """Preserve link identity, URL, issuer/date text and PACOM access hold.

    Unlike the corpus totals, this first-party metadata must be unchanged by
    deletion of the unrelated Chinese article cohort. Standard library only,
    so CI's credential-free short contract need not install network packages.
    """
    before = _OfficialUSLinkParser()
    after = _OfficialUSLinkParser()
    before.feed((Path(before_site) / "us-indopacific.html").read_text(
        encoding="utf-8"))
    after.feed((Path(after_site) / "us-indopacific.html").read_text(
        encoding="utf-8"))
    receipt = {}
    for table in (
        "uscc_official_source_records",
        "treasury_official_source_records",
    ):
        original = before.rows[table]
        rendered = after.rows[table]
        if len(set(original)) != len(original) or len(set(rendered)) != len(rendered):
            raise ValueError("duplicate official U.S. metadata reference: " + table)
        expected = sqlite_receipt["official_source_rows"][table]
        if expected is not None and expected > 0 and not original:
            raise ValueError("live U.S. SQLite metadata was not rendered: " + table)
        if original != rendered:
            raise ValueError("U.S. official link/date/issuer changed or vanished: " + table)
        receipt[table] = len(rendered)
    if "PACOM collection blocked" not in " ".join(after.all_text):
        raise ValueError("official U.S. link metadata must not promote PACOM collector")
    return receipt


class _KoreaOfficialLinkParser(HTMLParser):
    """Extract exact released Korea metadata and fixed-directory exclusions."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.auto = []
        self.fixed = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "li":
            for name in ("data-korea-public-link", "data-korea-additional-link"):
                if name in attrs:
                    self.fixed.append(attrs[name])
            if "data-korea-auto-official-link" in attrs:
                if self.current is not None:
                    raise ValueError("nested Korea metadata row")
                self.current = {
                    "identity": attrs["data-korea-auto-official-link"],
                    "href": None, "dates": [], "text": [],
                }
        elif self.current is not None and tag == "a":
            if self.current["href"] is None:
                self.current["href"] = attrs.get("href")
        elif self.current is not None and tag == "time":
            if "datetime" in attrs:
                self.current["dates"].append(attrs["datetime"])

    def handle_data(self, value):
        if self.current is not None:
            self.current["text"].append(value)

    def handle_endtag(self, tag):
        if tag != "li" or self.current is None:
            return
        item = self.current
        identity, url, dates = item["identity"], item["href"], item["dates"]
        if not isinstance(identity, str) or not identity.startswith("korea-policy:"):
            raise ValueError("invalid Korea metadata identity")
        number = identity[len("korea-policy:"):]
        if len(number) != 9 or not number.isascii() or not number.isdigit():
            raise ValueError("invalid Korea metadata official ID")
        if url != "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + number:
            raise ValueError("invalid Korea official link URL")
        if len(dates) != 1:
            raise ValueError("Korea official link needs exactly one date")
        self.auto.append((identity, url, dates[0], " ".join(
            " ".join(item["text"]).split())))
        self.current = None


def verify_korea_public_link_parity(before_site, after_site, sqlite_receipt):
    """Require rendered live Korea links to match the surviving SQLite rows.

    The site's fixed five+nine official directories may reference a live
    record already; these identities are deliberately excluded from the
    *additional* automatic list rather than duplicated.
    """
    before, after = _KoreaOfficialLinkParser(), _KoreaOfficialLinkParser()
    before.feed((Path(before_site) / "korea.html").read_text(encoding="utf-8"))
    after.feed((Path(after_site) / "korea.html").read_text(encoding="utf-8"))
    if len(before.fixed) != len(set(before.fixed)) or before.fixed != after.fixed:
        raise ValueError("Korea existing source directory changed during China retirement")
    released = sqlite_receipt["korea_released_official_links"]
    expected = {tuple(row) for row in released if row[0] not in set(before.fixed)}
    for parsed in (before, after):
        identities = [row[0] for row in parsed.auto]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate Korea automatically published official link")
        if {(row[0], row[1], row[2]) for row in parsed.auto} != expected:
            raise ValueError("Korea live published metadata differs from protected SQLite")
    if before.auto != after.auto:
        raise ValueError("Korea official link/date/issuer text changed in China retirement")
    return len(after.auto)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--retired-db", type=Path, required=True)
    a = parser.parse_args()
    print(json.dumps(validate(a.source_db, a.retired_db),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
