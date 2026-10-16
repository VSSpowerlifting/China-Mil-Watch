"""Standalone fictional Living Dossier HTML *string* preview — never a publisher.

Uses only the B2.2a validated private reader projection, assembled afresh
from fictional sidecars + synthetic archive evidence. Does not accept arbitrary
caller-supplied view dictionaries, write files, invoke site/Jinja templates,
register routes or touch production. The result is NOT authorized for hosting,
public export, deployment or search indexing.

No network resources or external hyperlinks are emitted. All editorial fields
are escaped as HTML text, including the fields originally validated in B1.
"""
from __future__ import annotations

from html import escape

from core.dossier_private_view import build_private_dossier_view

PRIVATE_BANNER = "FICTIONAL — PRIVATE EDITORIAL REVIEW — DO NOT PUBLISH"

# Entirely self-contained styles. No user CSS, external fonts, images, scripts,
# or site-theme imports. They intentionally do not edit the actual frontend.
_STYLE = r"""
:root {
  color-scheme: light;
  --paper:#f8f5ed; --ink:#172f3c; --muted:#52646a; --teal:#176977;
  --rule:#cdd7d4; --white:#fffdf8; --accent:#d7e8e4;
}
* { box-sizing:border-box; }
html { scroll-behavior:auto; }
body { margin:0; background:var(--paper); color:var(--ink);
  font:16px/1.64 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }
a { color:#075363; text-underline-offset:.18em; }
a:focus-visible, summary:focus-visible { outline:3px solid #c16c16; outline-offset:3px; }
.skip { position:absolute; inset:0 auto auto 0; padding:.65rem 1rem;
  background:var(--white); transform:translateY(-140%); z-index:5; }
.skip:focus { transform:none; }
.banner { background:#142f3c; color:#fff; font:bold .72rem/1.5 ui-sans-serif,system-ui,sans-serif;
  letter-spacing:.12em; text-align:center; padding:.85rem 1rem; }
.wrap { width:min(1100px,calc(100% - 2rem)); margin:auto; }
header { padding:clamp(2.6rem,7vw,6.7rem) 0 2.2rem;
  background:linear-gradient(138deg,#e2eeeb 0%,var(--paper) 64%); }
.kicker { font:.72rem/1.45 ui-sans-serif,system-ui,sans-serif;
  letter-spacing:.16em; text-transform:uppercase; color:var(--teal); font-weight:750; }
h1,h2,h3 { font-family:Georgia,"Times New Roman",serif; font-weight:500;
  line-height:1.17; letter-spacing:-.024em; }
h1 { font-size:clamp(2.55rem,5.3vw,5rem); max-width:20ch; margin:.65rem 0 1.2rem; }
h2 { font-size:clamp(1.72rem,3vw,2.5rem); margin:0 0 1.1rem; }
h3 { font-size:1.45rem; margin:.3rem 0 .7rem; }
.dek { max-width:66ch; font-size:clamp(1.06rem,2vw,1.3rem); line-height:1.58; }
.meta { color:var(--muted); font-size:.85rem; }
.meta strong { color:var(--ink); }
.page { display:grid; grid-template-columns:minmax(0,1fr) 235px; column-gap:4rem;
  padding:2.8rem 0 5rem; }
main { min-width:0; }
aside { border-left:1px solid var(--rule); padding-left:1.4rem; align-self:start; }
nav { position:sticky; top:1.5rem; }
nav a { display:block; margin:.6rem 0; font-size:.9rem; }
section { padding:2.5rem 0; border-top:1px solid var(--rule); }
section:first-child { border-top:0; padding-top:0; }
.question { border-left:4px solid var(--teal); background:var(--white); padding:1rem 1.25rem; }
.question .kicker { margin:0 0 .35rem; }
.question p:last-child { margin:0; font:1.3rem/1.55 Georgia,"Times New Roman",serif; }
.two { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1.6rem; }
.small { font-size:.85rem; color:var(--muted); }
ul { padding-left:1.15rem; }
li { margin-bottom:.48rem; overflow-wrap:anywhere; }
.claim { padding:1.3rem 0 1.5rem; border-bottom:1px solid var(--rule); }
.claim:last-child { border-bottom:0; }
.claim-kind { display:inline-block; font-size:.72rem; letter-spacing:.09em;
  text-transform:uppercase; font-weight:750; color:var(--teal); margin-bottom:.5rem; }
.claim p { margin:.4rem 0 .75rem; }
.claim-body { font:1.13rem/1.65 Georgia,"Times New Roman",serif; }
.limits { margin-top:.85rem; padding:.8rem 1rem; background:var(--accent); font-size:.86rem; }
.cites { font-size:.86rem; color:var(--muted); margin-top:.65rem; }
.cites a { margin-right:.7rem; white-space:nowrap; }
.evidence-row { border-top:1px solid var(--rule); padding:1rem 0; }
.evidence-row:first-of-type { border-top:0; }
.evidence-row:target,.claim:target,section:target { outline:2px solid #177080;
  outline-offset:5px; }
.dispute { background:var(--white); border-left:3px solid #ae7941;
  padding:1rem 1.15rem; margin:1rem 0; }
footer { border-top:1px solid var(--rule); padding:2rem 0; font-size:.8rem; }
@media(max-width:820px) {
 .page { display:flex; flex-direction:column-reverse; gap:1.5rem; }
 aside { width:100%; border-left:0; border-bottom:1px solid var(--rule);
   padding:0 0 1rem; }
 nav { position:static; display:flex; flex-wrap:wrap; gap:.35rem .9rem; }
 nav a { margin:0; }
 .two { grid-template-columns:1fr; gap:.25rem; }
 section { padding:1.7rem 0; }
}
@media print {
 :root { --paper:white; --white:white; --ink:black; --muted:#333; }
 body { font-size:11pt; }
 .banner { color:black; background:white; border:2px solid black; }
 aside,.skip { display:none; }
 .page { display:block; padding:0; }
 header { background:white; padding:1.2rem 0; }
 section,.claim,.evidence-row { break-inside:avoid; }
 a { color:inherit; }
 .wrap { width:100%; }
}
"""


def _e(value):
    return escape(str(value), quote=True)


def _cites(citations, title):
    if not citations:
        return ""
    links = " ".join(
        '<a href="%s">Record %s</a>' % (_e(ref["source_anchor"]), _e(ref["record_id"]))
        for ref in citations
    )
    return '<div class="cites"><strong>%s:</strong> %s</div>' % (_e(title), links)


def _render_scope(view):
    scope = view["scope"]
    return (
        '<section id="scope"><h2>Scope &amp; method</h2>'
        '<div class="two"><div><p><strong>Coverage period:</strong> %s to %s</p>'
        '<p><strong>Included:</strong> %s</p><p><strong>Excluded:</strong> %s</p></div>'
        '<div><p><strong>Jurisdictions:</strong> %s</p>'
        '<p><strong>Institutions:</strong> %s</p>'
        '<p><strong>Method:</strong> %s</p></div></div>'
        '<div class="limits"><strong>Collection limitations:</strong> %s</div></section>'
    ) % (
        _e(scope["period_start"]), _e(scope["period_end"]),
        _e(scope["included"]), _e(scope["excluded"]),
        _e(", ".join(scope["jurisdictions"])),
        _e(", ".join(scope["institutions"])),
        _e(scope["method"]), _e(scope["collection_limits"]),
    )


def _render_sections(view):
    parts = []
    for section in view["sections"]:
        rendered = [
            '<section id="%s"><p class="kicker">Thematic evidence</p><h2>%s</h2><p>%s</p>'
            % (_e(section["anchor"]), _e(section["heading"]), _e(section["intro"]))
        ]
        for claim in section["claims"]:
            timing = ""
            if claim["event_period"] is not None:
                p = claim["event_period"]
                timing = (
                    '<p class="small">Date basis: %s · %s to %s — %s</p>'
                    % (_e(p["basis"]), _e(p["start"]), _e(p["end"]),
                       _e(p["date_basis"]))
                )
            rendered.append(
                '<article class="claim" id="%s">'
                '<span class="claim-kind">%s</span>'
                '<p class="claim-body">%s</p>%s%s%s'
                '<div class="limits"><strong>Qualification:</strong> %s</div></article>'
                % (
                    _e(claim["anchor"]), _e(claim["attribution_label"]),
                    _e(claim["text"]), timing,
                    _cites(claim["supporting_citations"], "Supporting sources"),
                    _cites(claim["counterevidence_citations"], "Counterevidence"),
                    _e(claim["limitations"]),
                )
            )
        rendered.append("</section>")
        parts.append("".join(rendered))
    return "".join(parts)


def _render_disagreements(view):
    parts = ['<section id="disagreements"><h2>Disagreements &amp; uncertainty</h2>']
    if not view["disagreements"]:
        parts.append(
            "<p>No specific disagreement is recorded in this fictional version. "
            "This is not evidence of consensus or completeness.</p>"
        )
    for issue in view["disagreements"]:
        refs = " ".join(
            '<a href="%s">%s</a>' % (_e(anchor), _e(anchor[7:]))
            for anchor in issue["claim_anchors"]
        )
        parts.append(
            '<div class="dispute"><p class="kicker">%s</p><p>%s</p>'
            '<p class="small">Claims: %s</p></div>'
            % (_e(issue["status"]), _e(issue["note"]), refs)
        )
    parts.append("</section>")
    return "".join(parts)


def _render_sources(view):
    parts = [
        '<section id="sources"><h2>Fictional source ledger</h2>'
        '<p class="small">References resolve to this private page only. '
        'No publisher hyperlinks, public IPR record URLs, or copied original '
        'source text are exposed.</p>'
    ]
    for source in view["source_ledger"]:
        parts.append(
            '<div class="evidence-row" id="%s"><strong>Record %s</strong>'
            '<p class="small">Desk: %s · Source: %s · Issuer: %s'
            ' · Language: %s · Published: %s</p></div>'
            % (_e(source["anchor"]), _e(source["record_id"]),
               _e(source["desk"]), _e(source["source_id"]),
               _e(source["institution_id"]), _e(source["language"]),
               _e(source["published_on"]))
        )
    parts.append("</section>")
    return "".join(parts)


def _render_changes(view):
    parts = [
        '<section id="updates"><h2>Review &amp; revision history</h2>',
        '<p class="small">Fictional, structurally compared drafts; this is NOT '
        'an authenticated historical release register.</p>',
    ]
    comparison = view["revision_comparison"]
    if comparison["previous_revision"] is not None:
        parts.append(
            '<p class="small">Compared with fictional revision %s; '
            'prior content fingerprint %s.</p>'
            % (_e(comparison["previous_revision"]),
               _e(comparison["previous_content_sha256"]))
        )
    for note in view["changes"]:
        refs = ", ".join(_e(x.removeprefix("#claim-")) for x in note["affected_claim_anchors"])
        parts.append(
            '<div class="evidence-row"><strong>Revision %s · %s</strong>'
            '<p>%s</p><p class="small">Affected current claims: %s</p></div>'
            % (_e(note["revision"]), _e(note["changed_on"]),
               _e(note["summary"]), refs if refs else "None listed")
        )
    parts.append("</section>")
    return "".join(parts)


def render_private_dossier_html(sidecar, archive_review, *,
                                synthetic_authority, previous_sidecar=None):
    """Produce safe HTML text from the gated fictional model; NO FILE WRITES.

    HTML is an inert review illustration, not an approved publication surface.
    The caller cannot bypass the gate by passing a preassembled view dictionary.
    """
    view = build_private_dossier_view(
        sidecar, archive_review,
        synthetic_authority=synthetic_authority,
        previous_sidecar=previous_sidecar,
    )
    # Defense in depth: any future relaxation of the projection's positive
    # preview state must not quietly turn this renderer into public output.
    if (view["eligible_for_publication"] is not False
            or view["private_synthetic_preview_only"] is not True
            or view["indexable"] is not False
            or view["public_route"] is not None
            or view["canonical"] is not None
            or view["sitemap_route"] is not None
            or view["feed_route"] is not None):
        raise ValueError("nonprivate-preview-state-refused")

    links = [("Overview", "#overview"), ("Scope", "#scope")]
    links += [(s["heading"], "#" + s["anchor"]) for s in view["sections"]]
    links += [
        ("Disagreements", "#disagreements"),
        ("Evidence", "#sources"),
        ("Revisions", "#updates"),
    ]
    navigation = "".join(
        '<a href="%s">%s</a>' % (_e(anchor), _e(label))
        for label, anchor in links
    )
    return (
        '<!doctype html><html lang="en"><head>'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow,noarchive,nosnippet">'
        '<meta name="referrer" content="no-referrer">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; '
        'object-src &#39;none&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
        '<title>%s — FICTIONAL PRIVATE DOSSIER PREVIEW</title>'
        '<style>%s</style></head><body>'
        '<a class="skip" href="#main">Skip to evidence</a>'
        '<div class="banner">%s</div>'
        '<header><div class="wrap"><p class="kicker">IPR / Fictional dossier prototype · Rev. %s</p>'
        '<h1>%s</h1><p class="dek">%s</p>'
        '<p class="meta">Edited (fictional): %s · Last reviewed: %s · Updated: %s</p>'
        '</div></header>'
        '<div class="wrap page"><main id="main">'
        '<section id="overview"><p class="kicker">Research question</p>'
        '<div class="question"><p class="kicker">Bounded inquiry</p><p>%s</p></div>'
        '<h2>What this fictional record establishes</h2><p>%s</p></section>'
        '%s%s%s%s%s'
        '</main><aside><nav aria-label="On this fictional dossier">%s</nav></aside></div>'
        '<footer><div class="wrap">%s · Private, synthetic demonstration only. '
        'No real evidence, public links, source rights, or publication approval.</div></footer>'
        '</body></html>'
    ) % (
        _e(view["title"]), _STYLE, _e(PRIVATE_BANNER),
        _e(view["revision"]), _e(view["title"]), _e(view["dek"]),
        _e(view["editor_name"]), _e(view["reviewed_on"]), _e(view["updated_on"]),
        _e(view["research_question"]), _e(view["overview"]),
        _render_scope(view), _render_sections(view), _render_disagreements(view),
        _render_sources(view), _render_changes(view), navigation, _e(PRIVATE_BANNER),
    )
