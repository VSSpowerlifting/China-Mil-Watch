"""
The opened article's hero media, as one read-only view (Phase 3C).

An article page shows at most one image in its hero. This module does not
decide whether an image may appear: that was decided upstream, by the
resolvers that already govern the opened article (`scripts.pw_env`'s
`editorial_veil_for_edition` / `source_veil_for_edition` for an earlier
issue, `core.brief_collection.brief_photo` for a brief). It only says how an
image those resolvers returned is presented, as one of these kinds:

* ``photograph`` — a curated photograph from the editorial manifest, shown
  with its full credit, its licence, its source and IPR's change note;
* ``signal-veil`` — a duotone of the cited source's own photograph, shown
  with the existing source-linked caption, word for word;
* ``plate`` — original IPR artwork (the regional relief): decorative,
  labelled "Editorial plate", never evidence, never a photograph;
* ``none`` — no image: the hero is text-led;
* ``preserved`` — an image whose existing markup is kept byte for byte
  because a ruling holds it (see ``PRESERVED_MEDIA``).

Nothing here grants a photograph: a brief's cover is granted by
`core.brief_cover`, and only shown here. It never reads catalogue admissions
(`core.catalogue_media` governs the catalogue only), never creates an image
association, and never infers ownership or a licence from an article URL. A
Signal Veil's `credit` field is never shown: for a source veil it is a
collector note, not an attribution.
"""
from __future__ import annotations

from typing import Mapping, Optional

from core.brief_cover import TREATMENT_NOTES

PHOTOGRAPH = "photograph"
SIGNAL_VEIL = "signal-veil"
PLATE = "plate"
NONE = "none"
PRESERVED = "preserved"
KINDS = (PHOTOGRAPH, SIGNAL_VEIL, PLATE, NONE, PRESERVED)

LABELS = {
    PHOTOGRAPH: "Photograph",
    SIGNAL_VEIL: "Signal Veil",
    PLATE: "Editorial plate",
}

#: The same notes the catalogue shows for an approved photograph (Phase 3B).
#: The change note is true of every curated derivative: the duo-navy tone,
#: the 1600 px downscale at fetch, and the hero's cover crop.
CHANGE_NOTE = "Toned, cropped and resized by IPR."
CONTEXT_NOTE = "Visual context, not evidence."
PLATE_NOTE = "Original IPR artwork. No source photograph."
PLATE_CONTEXT = "Decorative, not evidence."

#: The catalogue's regional relief (Phase 3B), referenced, never inlined. Its
#: viewBox is the `region` symbol's, recorded in `assets/geo/geo.receipt.json`;
#: only these desks have a highlight in it.
PLATE_ART = "assets/geo/region.svg"
PLATE_VIEWBOX = "0 0 300 196"
PLATE_DESKS = ("china", "singapore")

#: Media whose opened-article markup stays exactly as it was before Phase 3C.
#: A held item is not reclassified, relabelled or recaptioned here; clearing
#: one is a separate, recorded decision.
PRESERVED_MEDIA = {
    # No. 10. Phase 3B held this photograph: neither its author nor the
    # drafted alt text ("underway on the surface") is established by the
    # source. Its opened-article use is unchanged until that is resolved.
    "jin-class-type-094-ssbn": "3B hold: authorship and alt text not established",
    # No. 12. The cited Global Times article and the image's dated path do
    # not agree (B5), and its stored attribution note names the wrong
    # publisher, so it must never be shown as a credit. Kept as it is.
    "src-2026-08-01": "B5: provenance unresolved",
}


def _part(text, href=None, rel=None, before=""):
    return {"before": before, "text": text, "href": href or None,
            "rel": rel if href else None, "native": None}


def credit_parts(credit: str, *, license_name: str = "",
                 license_url: str = "", source_page: str = "",
                 native: str = "", native_lang: str = "") -> list:
    """
    The manifest credit, split on its own " · " separators, with the licence
    linked to its deed when the manifest records one and "via <host>" linked
    to the source page. Every word shown is the manifest's; when the credit
    names no host, a plain "Source" link is added so the source stays one
    click away.

    `native` and `native_lang` are the manifest's `credit_native` and
    `credit_native_lang`: the creator's name in its own script, recorded
    from the source's own author field, and that name's language. The
    segment holding it is split so only the name carries `lang`. The
    language is never guessed from the script, and a name that does not
    occur exactly once in the credit is not tagged at all (a test then
    fails on the untagged script rather than the page guessing).
    """
    tag = bool(native and native_lang and (credit or "").count(native) == 1)
    parts, linked_source = [], False
    for segment in [s.strip() for s in (credit or "").split(" · ") if s.strip()]:
        if license_name and segment == license_name and license_url:
            parts.append(_part(segment, license_url, "license noopener nofollow"))
        elif segment.startswith("via ") and source_page and not linked_source:
            parts.append(_part(segment[4:], source_page, "noopener nofollow",
                               before="via "))
            linked_source = True
        else:
            part = _part(segment)
            if tag and native in segment:
                pre, _, post = segment.partition(native)
                part["native"] = {"pre": pre, "text": native,
                                  "lang": native_lang, "post": post}
            parts.append(part)
    if source_page and not linked_source:
        parts.append(_part("Source", source_page, "noopener nofollow"))
    return parts


def _image(veil: Mapping) -> dict:
    return {"id": veil.get("id"), "src": veil.get("duo"),
            "alt": veil.get("alt") or "",
            "focus": veil.get("mask_focus") or ""}


def historical_article_media(veil: Optional[Mapping],
                             cover: Optional[Mapping] = None,
                             manifest_entry: Optional[Mapping] = None,
                             *, root: Optional[str] = None) -> dict:
    """
    How an earlier issue's hero image is shown.

    `veil` is the issue's already-resolved `pw_veil` (curated or source),
    `cover` its legacy `cover_media_item`, and `manifest_entry` the editorial
    manifest entry with the veil's id, read only for its licence deed URL
    and the language of a native-script name in its credit.

    With `root` (the page's path to the site root), an issue with no image
    gets the China Desk's editorial plate instead of a text-led hero: the
    China Desk published every earlier issue, as the catalogue records. A
    plate never replaces a photograph, a Signal Veil or a preserved image.
    """
    if veil:
        if veil.get("id") in PRESERVED_MEDIA:
            return {"kind": PRESERVED, "reason": PRESERVED_MEDIA[veil["id"]]}
        if veil.get("kind") == "curated":
            entry = (manifest_entry if manifest_entry
                     and manifest_entry.get("id") == veil.get("id") else {})
            return {"kind": PHOTOGRAPH, "label": LABELS[PHOTOGRAPH],
                    **_image(veil),
                    "subject": veil.get("subject") or "",
                    "credit": credit_parts(
                        veil.get("credit"), license_name=veil.get("license") or "",
                        license_url=entry.get("license_url") or "",
                        source_page=veil.get("source_page") or "",
                        native=entry.get("credit_native") or "",
                        native_lang=entry.get("credit_native_lang") or ""),
                    "notes": (CHANGE_NOTE, CONTEXT_NOTE)}
        if veil.get("kind") == "source":
            # The caption the page already carried, word for word, with only
            # its kind named. The stored `credit` is never read.
            return {"kind": SIGNAL_VEIL, "label": LABELS[SIGNAL_VEIL],
                    **_image(veil),
                    "subject": veil.get("subject") or "",
                    "source_id": veil.get("source_id") or "",
                    "source_page": veil.get("source_page") or ""}
        # An unknown veil kind is not guessed at: it keeps its old markup.
        return {"kind": PRESERVED, "reason": "unrecognised veil kind"}
    if cover and cover.get("src"):
        # Only No. 1 has a legacy cover; Phase 3B held it (identifiable people,
        # a filename for alt text). Its existing markup is kept.
        return {"kind": PRESERVED, "reason": "3B hold: legacy edition cover"}
    if root is not None:
        return editorial_plate(root, ("china",))
    return {"kind": NONE}


def native_article_media(photo: Optional[Mapping], desks=(),
                         root: Optional[str] = None,
                         cover: Optional[Mapping] = None) -> dict:
    """
    How a brief's hero image is shown. A brief's photograph (`brief_photo`)
    keeps its existing figure and two-level credit (Phase 0 §1.2). Otherwise
    a cover granted by `core.brief_cover.brief_cover` is shown as a
    photograph with its full credit, licence, source, change note and any
    notice its terms require. Without either, and given `root`, the hero
    carries the editorial plate for the brief's own desks; otherwise it is
    text-led. `cover` is only ever what that gate returned: nothing here
    re-checks or widens a grant.
    """
    if photo:
        return {"kind": PRESERVED, "reason": "Phase 0 §1.2: brief photograph"}
    if cover:
        return cover_view(cover, root or "")
    if root is not None:
        return editorial_plate(root, desks)
    return {"kind": NONE}


def cover_view(cover: Mapping, root: str) -> dict:
    """A granted cover as a photograph view, with responsive sources."""
    entry = cover["entry"]
    treatment = entry["cover_treatment"]
    return {"kind": PHOTOGRAPH, "label": LABELS[PHOTOGRAPH], "cover": True,
            "id": entry["id"], "treatment": treatment,
            "src": root + cover["src"]["route"],
            "width": cover["src"]["width"], "height": cover["src"]["height"],
            "srcset": ", ".join("%s%s %dw" % (root, f["route"], f["width"])
                                for f in cover["webp"]),
            "alt": entry["alt"], "focus": entry.get("focal") or "",
            "caption": entry["caption"], "date_note": entry.get("date_note") or "",
            "credit": credit_parts(
                entry["credit"], license_name=entry["license"],
                license_url=entry.get("license_url") or "",
                source_page=entry["source_page"]),
            "notes": (TREATMENT_NOTES[treatment], CONTEXT_NOTE),
            "notice": entry.get("notice") or ""}


def editorial_plate(root: str, desks=()) -> dict:
    """
    Original IPR artwork in the hero: the catalogue's regional relief, with
    the brief's desks picked out. Decorative and never evidence: the art is
    hidden from assistive technology and the label and note carry its
    meaning. Its outlines are generated from Natural Earth and are not
    boundary claims (`assets/geo/geo.receipt.json`). It is not a photograph
    and grants none.
    """
    return {"kind": PLATE, "label": LABELS[PLATE], "id": None,
            "art": root + PLATE_ART, "viewbox": PLATE_VIEWBOX,
            "desks": tuple(d for d in desks if d in PLATE_DESKS),
            "notes": (PLATE_NOTE, PLATE_CONTEXT)}
