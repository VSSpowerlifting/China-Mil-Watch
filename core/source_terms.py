"""
Notices a publisher's terms require wherever its photographs appear.

This is separate from copyright status (`license`) and from IPR's own use
approval (the owner's G-rulings in DECISION_LOG). A public-domain photograph
can still carry a publisher condition, and most public-domain photographs
carry none. So a notice is required only where a publisher's own terms have
been read and recorded below. It is never inferred from licence, subject or
government authorship.

A source is recognised by the host of its `source_page` or by its
`source_label`. Either one is enough, so a record cannot shed its notice by
changing only one of them. Each gate that admits a photograph
(`core.brief_cover`, `core.catalogue_media`) calls `notice_problem` on its
own record. A missing or reworded notice fails that gate, even when the two
records agree with each other.

To add a publisher: read its terms, record the receipt in the evidence for
the first admission, and add one entry here with the exact notice text.
"""
from __future__ import annotations

from typing import Mapping, Optional
from urllib.parse import urlsplit

#: Publisher conditions, each read from the publisher's own terms.
REQUIRED_NOTICES = (
    {
        # https://www.dvidshub.net/about/copyright, read 12 October 2026
        # (docs/evidence/brief-cover-no17-2026-10-12/README.md).
        "publisher": "DVIDS",
        "hosts": ("dvidshub.net",),
        "labels": ("DVIDS",),
        "notice": ("The appearance of U.S. Department of War (DoW) visual "
                   "information does not imply or constitute DoW endorsement."),
    },
)


def _host(url) -> str:
    try:
        return (urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""


def required_notice(entry: Mapping) -> Optional[str]:
    """The exact notice the entry's source requires, or None."""
    host = _host(entry.get("source_page"))
    label = str(entry.get("source_label") or "").strip().casefold()
    for term in REQUIRED_NOTICES:
        if (any(host == h or host.endswith("." + h) for h in term["hosts"])
                or label in (x.casefold() for x in term["labels"])):
            return term["notice"]
    return None


def notice_problem(entry: Mapping) -> Optional[str]:
    """None when the entry carries any notice its source requires, word for
    word; otherwise a reason code."""
    required = required_notice(entry)
    if required is None:
        return None
    notice = entry.get("notice") or ""
    if not notice:
        return "required-notice-missing"
    if notice != required:
        return "required-notice-altered"
    return None
