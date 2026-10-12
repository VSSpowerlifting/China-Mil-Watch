"""Loopback-only, server-rendered private metadata reader; no JS or remote assets."""
from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

from core.source_occurrences import OccurrenceError
from storage.source_occurrences import read_batches

CSS = """
:root{color-scheme:light;--bg:#F3F2EC;--ink:#1D2D31;--accent:#176C6C;--rule:#CDD5CF}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:32px 24px}header{border-bottom:3px solid var(--ink);padding-bottom:20px}
h1,h2{font-family:Georgia,serif;font-weight:400;line-height:1.15}h1{font-size:clamp(30px,5vw,48px)}h2{font-size:28px}
a{color:var(--accent);text-underline-offset:3px}a:focus-visible,input:focus-visible,select:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:4px}
.skip{position:absolute;left:20px;top:-100px}.skip:focus{top:10px;background:var(--bg);padding:12px}
form{display:flex;flex-wrap:wrap;gap:16px;align-items:end;padding:24px 0;border-bottom:1px solid var(--rule)}label{display:block;font-size:14px}
input,select,button{font:inherit;max-width:100%;padding:8px;border:1px solid #405456;background:#FAFBF7;color:var(--ink)}button{cursor:pointer}
article,section.group{border-top:1px solid var(--rule);padding:20px 0}dl{display:grid;grid-template-columns:minmax(130px,1fr) 3fr;gap:8px;margin:12px 0}dt{color:#405456}dd{margin:0;overflow-wrap:anywhere}
code{font:13px/1.6 ui-monospace,monospace;overflow-wrap:anywhere}.locator{overflow-wrap:anywhere}.label{font-weight:600;color:var(--accent)}summary{cursor:pointer;padding:8px 0}.caveat{max-width:80ch}.states{font-weight:600}.stats{display:flex;flex-wrap:wrap;gap:20px}.stats p{margin:8px 0}
@media(max-width:600px){main{padding:24px 16px}dl{grid-template-columns:1fr;gap:2px}dd{margin-bottom:12px}form>div{width:100%}input,select{width:100%}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto;animation:none;transition:none}}
"""


def e(value):
    return escape(str(value), quote=True)


def link(params, label):
    return '<a href="/?%s">%s</a>' % (e(urlencode(params)), e(label))


def metadata_html(m, native_id=None):
    pairs = [("Source identity", m.source_slug or "Unknown identity"),
             ("Desk / institution", "%s / %s" % (m.desk_id or "unknown", m.institution_id or "unknown")),
             ("Publication date", m.published_date or "Missing / unavailable date"),
             ("Collected date", m.scraped_at or "Unavailable"),
             ("Title availability", m.title_state),
             ("Body availability / type", m.body_state + " / " + m.body_kind),
             ("Stored legacy hash", m.stored_hash_state)]
    if native_id is not None:
        pairs.insert(0, ("Native record", str(native_id)))
    fields = "".join('<dt>%s</dt><dd>%s</dd>' % (e(k), e(v)) for k, v in pairs)
    fields += '<dt>Source locator</dt><dd class="locator"><a rel="noopener noreferrer" href="%s">%s</a></dd>' % (e(m.url), e(m.url))
    if m.supplied_url != m.url:
        fields += '<dt>Exact supplied locator</dt><dd class="locator">%s</dd>' % e(m.supplied_url)
    digests = [("Extracted title SHA-256", m.extracted_title_sha256),
               ("Extracted text SHA-256", m.extracted_text_sha256),
               ("Extracted document SHA-256 (title/text fields; not HTTP capture)", m.extracted_document_sha256),
               ("Normalized text SHA-256", m.normalized_text_sha256),
               ("Title group SHA-1", m.title_group_sha1),
               ("Recomputed legacy normalized TITLE PLUS TEXT SHA-256", m.legacy_title_text_sha256),
               ("Stored legacy TITLE PLUS TEXT SHA-256", m.stored_legacy_title_text_sha256),
               ("Producer capture reference (only when supplied)", m.producer_capture_sha256),
               ("Saved local input bytes SHA-256 (not HTTP capture)", m.saved_input_bytes_sha256),
               ("Producer retrieval date", m.producer_retrieved_at)]
    detail = "".join('<dt>%s</dt><dd><code>%s</code></dd>' % (e(k), e(v or "Unavailable")) for k, v in digests)
    return '<dl>%s</dl><details><summary>Digest and version evidence</summary><dl>%s</dl></details>' % (fields, detail)


def render(batches, params=None):
    params = params or {}
    selected = params.get("batch")
    mode = params.get("mode", "")
    source = params.get("source", "")
    from core.source_occurrences import actual_date
    start, end = actual_date(params.get("from")) or "", actual_date(params.get("to")) or ""
    group_key = params.get("group")
    observation_id = params.get("observation")
    native = params.get("native")
    try:
        page = max(0, int(params.get("page", "0")))
    except ValueError:
        page = 0
    def matches(m):
        return (not source or (m.source_slug or "unknown") == source) and (
            not start or (m.published_date is not None and m.published_date >= start)) and (
            not end or (m.published_date is not None and m.published_date <= end))
    options = sorted({o.metadata.source_slug or "unknown" for b in batches for o in b.observations})
    filters = {k: v for k, v in (("mode", mode), ("source", source),
                                ("from", start), ("to", end)) if v}
    hidden = ('<input type="hidden" name="show" value="all">'
              if params.get("show") == "all" else '')
    if selected:
        hidden += '<input type="hidden" name="batch" value="%s">' % e(selected)
    select = '<select id="source" name="source"><option value="">All sources</option>' + "".join(
        '<option%s value="%s">%s</option>' % (' selected' if s == source else '', e(s), e(s)) for s in options) + '</select>'
    mode_select = '<select id="mode" name="mode"><option value="">Both modes</option>' + "".join(
        '<option value="%s"%s>%s</option>' % (k, ' selected' if k == mode else '', label)
        for k, label in [("archive_inventory", "Archive inventory"), ("observed_replay", "Observed replay")]) + '</select>'
    body = ['<a class="skip" href="#results">Skip to results</a><main><header><p class="label">ipr · Private local metadata</p><h1>Deduplication provenance workbench</h1><p class="caveat">Archive inventory describes retained rows. Observed replay preserves supplied local documents and their actual dedup decisions. Historical batch membership and decisions are unknown. Lost historical URLs cannot be recovered; no ongoing capture is active.</p><p class="caveat">Title groups are candidate relationships, not shared events. URL equality does not establish an unchanged body; normalized hashes are not independent corroboration. Missing text never establishes full-text equality. This reader confers no rights or custody approval.</p></header>']
    body.append('<form method="get" action="/">%s<div><label for="mode">Mode</label>%s</div><div><label for="source">Source</label>%s</div><div><label for="from">From publication date</label><input id="from" name="from" type="date" value="%s"></div><div><label for="to">To publication date</label><input id="to" name="to" type="date" value="%s"></div><button type="submit">Apply filters</button><a href="/">Reset filters</a></form><div id="results" tabindex="-1">' % (hidden, mode_select, select, e(start), e(end)))
    count = 0
    for b in batches:
        if selected and selected != b.batch_key_sha256 or mode and mode != b.mode:
            continue
        base = {"batch": b.batch_key_sha256}
        label = "Archive inventory · existing_archive_row" if b.mode == "archive_inventory" else "Observed replay · supplied local documents"
        body.append('<section><h2>%s</h2><p>Batch <code>%s</code> · %d observations</p><details><summary>Snapshot, input and code binding</summary><dl>%s</dl></details>' % (label, e(b.batch_key_sha256), len(b.observations), "".join('<dt>%s</dt><dd><code>%s</code></dd>' % (e(k),e(v)) for k,v in [("Snapshot SHA-256",b.snapshot_sha256),("Input SHA-256",b.input_sha256),("Code SHA-256",b.code_sha256),("Git HEAD",b.code_git_head),("Execution",b.execution_sha256)])))
        nodes = {"o:" + o.observation_id: o.metadata for o in b.observations}
        nodes.update({"n:" + str(r.native_id): r.metadata for r in b.records})
        groups = [r for r in b.relations if r.kind == "same_title_group" and
                  (not group_key or r.key == group_key) and any(matches(nodes[n]) for n in r.members)]
        members = set()
        for g in groups:
            members.update(g.members)
            dates = {nodes[n].published_date for n in g.members if nodes[n].published_date}
            bodies = {nodes[n].normalized_text_sha256 for n in g.members if nodes[n].normalized_text_sha256}
            states = []
            if len(dates) > 1: states.append("Differing publication dates")
            if any(not nodes[n].published_date for n in g.members): states.append("Missing date evidence")
            if any(not nodes[n].normalized_text_sha256 for n in g.members): states.append("Missing body evidence")
            if len(bodies) > 1: states.append("Differing extracted versions; unresolved")
            if not states: states.append("Candidate title relationship; event equivalence unresolved")
            body.append('<section class="group" id="group-%s"><h3>%s</h3><p class="states">%s</p><p>%d members</p></section>' % (e(g.key), link(dict(base,group=g.key), 'Title group ' + g.key[:12]), e(" · ".join(states)), len(g.members)))
            body.append('<p>%s</p>' % link({'group':g.key}, 'Inspect this title group across batches'))
        obs = [o for o in b.observations if matches(o.metadata) and
               (not observation_id or o.observation_id == observation_id) and
               (not group_key or o.metadata.title_group_sha1 == group_key) and
               (b.mode == "observed_replay" or params.get("show") == "all" or observation_id or
                group_key or "o:" + o.observation_id in members)]
        if native:
            obs = []
        body.append('<p>%s · %d matching observations; showing up to 100.</p>' % (link(dict(filters,**base,show="all"), "Show all observations"), len(obs)))
        for o in obs[page * 100:(page + 1) * 100]:
            count += 1
            body.append('<article id="observation-%s"><h3>%s · position %d</h3><p>%s → %s</p>' % (e(o.observation_id), link(dict(base, observation=o.observation_id), 'Observation ' + o.observation_id[:12]), o.position, e(o.title_reason), e(o.url_hash_reason)))
            if o.metadata.title_group_sha1:
                body.append('<p>%s</p>' % link({'group':o.metadata.title_group_sha1}, 'Inspect title group across batches'))
            for title, representative in [("Title representative",o.title_representative),("URL/hash representative",o.url_hash_representative)]:
                if representative:
                    body.append('<p>%s: %s</p>' % (title, link(dict(base,observation=representative),representative[:12])))
            for title, pointers in [("Exact URL native pointers",o.native_ids),("Decision native matches",o.decision_native_ids)]:
                body.append('<p>%s: %s%s</p>' % (title, 'Ambiguous matches · ' if len(pointers)>1 else '', " · ".join(link(dict(base,native=n), 'Record ' + str(n)) for n in pointers) or 'No stored native ID'))
            body.append(metadata_html(o.metadata))
            body.append('<details><summary>Exact relationships (no event graph)</summary><ul>')
            for r in b.relations:
                if "o:" + o.observation_id in r.members:
                    versions = {nodes[n].extracted_document_sha256 for n in r.members}
                    missing = any(not nodes[n].normalized_text_sha256 for n in r.members)
                    state = (' · Missing body evidence' if missing else '') + (
                        ' · Differing extracted versions; unresolved' if len(versions)>1 else '')
                    pointers = [link(dict(base,observation=n[2:]) if n.startswith('o:') else
                                     dict(base,native=n[2:]),
                                     ('Observation ' if n.startswith('o:') else 'Record ') + n[2:12])
                                for n in r.members]
                    body.append('<li>%s · <code>%s</code>%s<details><summary>%d members</summary>%s</details></li>' %
                                (e(r.kind),e(r.key),e(state),len(r.members),' · '.join(pointers)))
            body.append('</ul></details></article>')
        record_ids = {int(n[2:]) for n in members if n.startswith("n:")}
        for r in b.records:
            if (native and str(r.native_id) == native) or (not native and group_key and r.native_id in record_ids):
                body.append('<article id="native-%d"><h3>Selected snapshot native record %d</h3>%s</article>' % (r.native_id, r.native_id, metadata_html(r.metadata,r.native_id)))
                count += 1
        if len(obs) > (page + 1) * 100:
            body.append(link(dict(params, batch=b.batch_key_sha256, page=page+1), "Next 100 observations"))
        body.append('</section>')
    if not count:
        body.append('<p>No matching observation or record. Reset filters to reopen the ledger overview.</p>')
    body.append('</div><footer><p>Local metadata only. Source links open only when you choose them. No publisher embeds or remote assets.</p></footer></main>')
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>IPR private deduplication workbench</title><style>%s</style></head><body>%s</body></html>' % (CSS, "".join(body))


def make_server(ledger, port=0):
    # Validate before opening a socket. HTTP never accepts writes or source paths.
    read_batches(ledger)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Query strings and source inputs never enter access logs.

        def do_GET(self):
            parts = urlsplit(self.path)
            if parts.path != "/":
                self.send_error(404, "Not found")
                return
            try:
                params = {k: v[-1] for k,v in parse_qs(parts.query).items()
                          if k in {"batch","mode","source","from","to","group","observation","native","page","show"}}
                data = render(read_batches(ledger), params).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(data)
            except (OccurrenceError, OSError):
                self.send_error(503, "Private ledger unavailable")
    return HTTPServer(("127.0.0.1", port), Handler)


def serve(ledger, port=8767):
    server = make_server(ledger, port)
    print("Private metadata reader: http://127.0.0.1:%d/ (loopback only; Ctrl-C to stop)" % server.server_port, flush=True)
    server.serve_forever()
