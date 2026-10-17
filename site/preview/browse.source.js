/* Production controller. Build with scripts/build_archive_js.py; PR #766 is the private reference. */
(function () {
 "use strict";
 const $ = id => document.getElementById(id), root = $("browse"), A = Array.isArray;
 if (!root || !window.fetch || !window.URLSearchParams) return;
 const form = $("controls"), out = $("results"), range = $("result-range"), live = $("result-live"),
   wait = $("index-state"), fail = $("index-error"), none = $("no-results"),
   prev = $("page-prev"), next = $("page-next"), chips = $("chips"), reset = $("f-reset"),
   list = $("research-list"), note = $("selection-note"), error = $("research-error"), E = ArchiveSearch,
   KEYS = "scope q desk source status sort institution language from to trail keywords record_type issuer".split(" "),
   F = form.elements, PER = 50,
   storage = "ipr/1", TR = "In an analysis source trail";
 let research, prepared, pending, view = [], page = 1, selected = new Set();
 function get(k) { return F[k].type === "checkbox" ? (F[k].checked ? "1" : "") : F[k].value.trim(); }
 function put(k, value) {
  const e = F[k], v = value || (k === "sort" ? "new" : k === "scope" ? "focus" : "");
  if (e.type === "checkbox") e.checked = v === "1";
  else {
   if (["issuer", "source"].includes(k) && v && ![...e.options].some(o => o.value === v)) e.add(new Option(v, v));
   e.value = v; if (e.selectedIndex === -1) e.selectedIndex = 0;
  }
 }
 function readUrl() {
  const p = new URLSearchParams(location.search);
  KEYS.forEach(k => put(k, p.get(k))); page = Math.max(1, parseInt(p.get("page"), 10) || 1);
 }
 function writeUrl(push) {
  const p = new URLSearchParams();
  KEYS.forEach(k => { const v = get(k); if (v && !(k === "sort" && v === "new") && !(k === "scope" && v === "focus")) p.set(k, v); });
  if (page > 1) p.set("page", page);
  history[push ? "pushState" : "replaceState"](null, "", location.pathname + (p.size ? "?" + p : ""));
 }
 function el(tag, cls, txt) {
  const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e;
 }
 const clone = id => $(id).content.firstElementChild.cloneNode(true);
 function card(r) {
  const li = clone("archive-row"), find = q => li.querySelector(q), meta = research.display[r.id],
    fields = {...r, hold:research.holds[r.id], ...(meta || {who:r.issuer || r.source, via:r.source, state:r.record_type.replaceAll("_", " ")}),
      title:r.title || r.original_title || "Published original source text",
      original:r.title && r.original_title && r.title.trim() !== r.original_title.trim() ? r.original_title : null,
      date_info:[r.date_kind,r.date].filter(Boolean).join(" · ")};
  li.querySelectorAll("[data-text]").forEach(e => { const text = fields[e.dataset.text]; if (text) e.textContent = text; else e.remove(); });
  find("h3 a").href = meta ? "record/" + r.id.slice(7) + ".html" : r.ipr_url || r.source_url;
  if (meta) {
   if (meta.title_lang) find("h3").lang = meta.title_lang;
   if (find(".original") && meta.lang) find(".original").lang = meta.lang;
   if (meta.desk_route) find(".row-side a").href = meta.desk_route;
   const state = li.querySelector('[data-text="analyzed"],[data-text="state"]'); state.className = meta.state_class;
  }
  if (!find(".row-tags").children.length) find(".row-tags").remove();
  const citation = find(".archive-citation"), copy = find("details button"), check = find("input");
  check.checked = selected.has(r.id); check.setAttribute("aria-label", "Keep: " + fields.title);
  check.onchange = () => { const first = !selected.size; check.checked ? selected.add(r.id) : selected.delete(r.id); updateList(first && check.checked); };
  copy.onclick = async () => {
   try { await navigator.clipboard.writeText(r.citation); copy.textContent = "Copied"; }
   catch (_) { citation.focus(); const rng = document.createRange(); rng.selectNodeContents(citation);
    const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(rng); copy.textContent = "Select text to copy"; }
  };
  return li;
 }
 function day(date) {
  const sec = clone("archive-day"), time = sec.querySelector("time");
  if (!date) time.textContent = "Date unrecorded";
  else { time.dateTime = date; sec.querySelectorAll("span").forEach((e,i) => { e.textContent = research.days[date][i]; }); }
  return sec;
 }
 function matches(r) {
  const m = research.display[r.id], q = get("q").toLowerCase();
  return (!q || ((m && !m.english ? "" : r.title || "") + " " + (r.original_title || "")).toLowerCase().includes(q)) &&
   (get("scope") === "published" || m && (get("scope") === "all" || m.focus)) &&
   ["source","status","institution","language"].every(k => !get(k) || get(k) === (m || r)[k]) && (!get("trail") || m && m.trail);
 }
 function render() {
  const total = view.length, pages = Math.max(1, Math.ceil(total / PER)); page = Math.min(page, pages);
  const start = (page - 1) * PER, rows = view.slice(start, start + PER), wrap = el("div", "records-days");
  let last, ul; wrap.setAttribute("data-from-index", "");
  rows.forEach(r => { if (r.date !== last) { last = r.date; const sec = wrap.appendChild(day(last)); ul = sec.querySelector("ul"); } ul.appendChild(card(r)); });
  out.replaceChildren(wrap);
  const msg = total ? "Showing " + (start + 1).toLocaleString("en-US") + "–" + (start + rows.length).toLocaleString("en-US") + " of " + total.toLocaleString("en-US") +
   (get("scope") === "focus" ? " research-focus records" : get("scope") === "all" ? " preserved records" : " published items") +
   (filtered() ? " matching filters" : "") : "No records match these filters.";
  range.textContent = total ? msg + (pages > 1 ? " · page " + page + " of " + pages : "") : "";
  live.textContent = msg; none.hidden = total !== 0;
  prev.hidden = next.hidden = pages < 2; prev.disabled = page <= 1; next.disabled = page >= pages;
 }
 function filtered() { return KEYS.some(k => !["scope","sort"].includes(k) && get(k)); }
 function drawChips() {
  chips.replaceChildren(); reset.hidden = !filtered();
  KEYS.filter(k => !["scope","sort"].includes(k) && get(k)).forEach(k => {
   const e = F[k], label = k === "trail" ? TR : e.tagName === "SELECT" ? e.selectedOptions[0].text : get(k),
    b = chips.appendChild(el("li")).appendChild(el("button", "chip", label));
   b.type = "button"; b.setAttribute("aria-label", "Remove filter: " + label);
   b.onclick = () => { put(k, ""); go(true, true); F.q.focus(); };
  });
 }
 function updateList(first) {
  $("selection-count").textContent = selected.size; $("export-cue").hidden = !selected.size;
  ["export-csv","export-json","selection-clear"].forEach(id => { $(id).disabled = !selected.size; });
  note.textContent = first ? note.dataset.first : selected.size + " records kept.";
  try { sessionStorage.setItem(storage, JSON.stringify([...selected])); } catch (_) {}
 }
 function unavailable() { root.hidden = wait.hidden = prev.hidden = next.hidden = list.hidden = true; fail.hidden = false; }
 function load() {
  if (!pending) {
   wait.hidden = false;
   const fetchJson = async (path, expected) => {
    const response = await fetch(path + "?s=" + expected, {credentials:"omit"}), raw = await response.text();
    const actual = [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(raw)))].map(x => x.toString(16).padStart(2,"0")).join("");
    if (!response.ok || actual !== expected) throw Error("index mismatch");
    return JSON.parse(raw);
   };
   pending = fetchJson("corpus-index.json", root.dataset.archiveDigest)
    .then(() => fetchJson("archive-research-index.json", root.dataset.researchDigest)).then(r => {
    research = r; prepared = E.prepare(r.records);
    try { const ids = JSON.parse(sessionStorage.getItem(storage) || "[]"); if (A(ids)) selected = new Set(ids.filter(id => r.records.some(x => x.id === id))); } catch (_) {}
    wait.hidden = true; updateList();
   }); pending.catch(unavailable);
  } return pending;
 }
 function go(push, first) {
  if (first) page = 1;
  load().then(() => {
   try {
    error.hidden = true;
    view = E.search(prepared, {q:get("keywords"), desk:get("desk"), issuer:get("issuer"), record_type:get("record_type"),
      from:get("from"), to:get("to"), sort:get("sort") === "relevance" ? "relevance" : get("sort") === "old" ? "oldest" : "newest"}).map(h => h.record).filter(matches);
    if (get("scope") !== "published" && get("sort") !== "relevance") {
     view.sort((a,b) => research.display[a.id].order-research.display[b.id].order); if (get("sort") === "old") view.reverse();
    }
    drawChips(); render(); writeUrl(push);
   } catch (e) { error.textContent = e.message; error.hidden = false; }
  }, () => {});
 }
 for (const type of ["csv","json"]) $("export-" + type).onclick = () => {
  const content = type === "csv" ? E.csv(research.records, selected) : JSON.stringify({schema:E.SCHEMA, corpus_digest:research.digest, records:E.selected(research.records, selected)}),
    url = URL.createObjectURL(new Blob([content], {type:type === "csv" ? "text/csv;charset=utf-8" : "application/json"})), a = el("a");
  a.href = url; a.download = "ipr." + type; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
 };
 $("selection-clear").onclick = () => { selected.clear(); updateList(); out.querySelectorAll("input").forEach(e => { e.checked = false; }); };
 let timer;
 F.q.onfocus = () => load(); F.q.oninput = F.keywords.oninput = () => { clearTimeout(timer); timer = setTimeout(() => go(false, true), 200); };
 KEYS.filter(k => !["q","keywords"].includes(k)).forEach(k => { F[k].onchange = () => go(true, true); });
 form.onsubmit = e => { e.preventDefault(); go(true, true); };
 reset.onclick = () => { KEYS.forEach(k => put(k, "")); go(true, true); F.q.focus(); };
 function turn(d) { page += d; go(true); range.focus(); }
 prev.onclick = () => turn(-1); next.onclick = () => turn(1);
 window.onpopstate = () => { readUrl(); go(false); };
 root.hidden = form.hidden = next.hidden = list.hidden = false;
 list.open = !matchMedia("(max-width:680px)").matches; readUrl();
 if (filtered() || page > 1 || get("scope") !== "focus" || get("sort") !== "new") go(false);
 else try { if (JSON.parse(sessionStorage.getItem(storage) || "[]").length) load(); } catch (_) {}
})();
