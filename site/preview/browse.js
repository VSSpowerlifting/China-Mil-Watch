/* Corpus browser — progressive enhancement; corpus.html reaches every record
 * without it. Two rules: corpus values use textContent only, and nothing is
 * revealed until the index is proved to be this page's declared snapshot.
 */
(function () {
  "use strict";

  var root = document.getElementById("browse");
  if (!root || !window.fetch) return;

  var $ = function (id) { return document.getElementById(id); };
  var els = {
    q: $("f-q"), source: $("f-source"), institution: $("f-institution"),
    language: $("f-language"), status: $("f-status"),
    from: $("f-from"), to: $("f-to"), reset: $("f-reset"),
    results: $("results"), range: $("result-range"), live: $("result-live"),
    prev: $("page-prev"), next: $("page-next"), pager: $("pager"),
    error: $("index-error"), empty: $("no-results"), controls: $("controls")
  };

  var PER_PAGE = 50;
  var IDX = { id: 0, date: 1, source: 2, state: 3, en: 4, orig: 5 };
  var FIELDS = ["id", "date", "source", "state", "title_en", "title_orig"];
  var FACETS = ["source", "institution", "language", "status"];
  var DICTS = ["sources", "institutions", "languages", "states"];
  var data = null, view = [], page = 1;

  /* The page states which snapshot it describes; the index must agree. */
  var WANT_DATE = root.getAttribute("data-snapshot-date");
  var WANT_COUNT = parseInt(root.getAttribute("data-snapshot-records"), 10);

  function valid(d) {
    if (!d || !d.snapshot || !Array.isArray(d.records)) return false;
    if (d.snapshot.date !== WANT_DATE) return false;
    if (d.snapshot.records !== WANT_COUNT) return false;
    if (d.records.length !== WANT_COUNT) return false;
    if (!Array.isArray(d.fields) || d.fields.join() !== FIELDS.join())
      return false;
    if (!DICTS.every(function (k) {
      return Array.isArray(d[k]) && d[k].length;
    })) return false;
    /* Every row, not a sample: reject a malformed row here, not by throwing
       later where it is indistinguishable from a validation decision. */
    for (var i = 0; i < d.records.length; i++) {
      if (!Array.isArray(d.records[i]) ||
          d.records[i].length !== FIELDS.length) return false;
    }
    return true;
  }

  /* URL state: reload, back/forward and copied links reproduce the view. */
  function readUrl() {
    var p = new URLSearchParams(location.search);
    els.q.value = p.get("q") || "";
    FACETS.forEach(function (k) { els[k].value = p.get(k) || ""; });
    els.from.value = p.get("from") || "";
    els.to.value = p.get("to") || "";
    page = Math.max(1, parseInt(p.get("page"), 10) || 1);
  }

  function writeUrl(push) {
    var p = new URLSearchParams();
    var pairs = [["q", els.q.value.trim()], ["from", els.from.value],
                 ["to", els.to.value], ["page", page > 1 ? String(page) : ""]];
    FACETS.forEach(function (k) { pairs.push([k, els[k].value]); });
    pairs.forEach(function (kv) { if (kv[1]) p.set(kv[0], kv[1]); });
    var url = location.pathname + (p.toString() ? "?" + p.toString() : "");
    history[push ? "pushState" : "replaceState"](null, "", url);
  }

  /* Only values with backing records are offered; labels come from the
     index's single server-side mapping. */
  function fillOptions(select, entries, allLabel) {
    var first = document.createElement("option");
    first.value = "";
    first.textContent = allLabel;
    select.appendChild(first);
    entries.forEach(function (e) {
      if (!e.count) return;
      var o = document.createElement("option");
      o.value = e.code;
      o.textContent = e.label + " (" + e.count.toLocaleString() + ")";
      select.appendChild(o);
    });
  }

  /* All active filters combine conjunctively. */
  function matches(row) {
    var src = data.sources[row[IDX.source]];
    var q = els.q.value.trim().toLowerCase();
    if (q && (row[IDX.en] + " " + row[IDX.orig]).toLowerCase().indexOf(q) < 0)
      return false;
    if (els.source.value && src.code !== els.source.value) return false;
    if (els.institution.value) {
      var inst = data.institutions[src.institution];
      if (!inst || inst.code !== els.institution.value) return false;
    }
    if (els.language.value) {
      var lang = data.languages[src.language];
      if (!lang || lang.code !== els.language.value) return false;
    }
    if (els.status.value &&
        data.states[row[IDX.state]].code !== els.status.value) return false;
    /* Inclusive both ends, on the source-stated publication date. */
    if (els.from.value && row[IDX.date] < els.from.value) return false;
    if (els.to.value && row[IDX.date] > els.to.value) return false;
    return true;
  }

  function text(tag, cls, value) {
    var el = document.createElement(tag);
    if (cls) el.className = cls;
    el.textContent = value;
    return el;
  }

  function card(row) {
    var src = data.sources[row[IDX.source]];
    var inst = data.institutions[src.institution];
    var lang = data.languages[src.language];

    var art = document.createElement("article");
    art.className = "record";

    var head = text("div", "record-head", "");
    head.appendChild(text("span", "evidence evidence--record", "Source record"));
    head.appendChild(text("span", "meta",
      (inst ? inst.label : src.label) + " · " + row[IDX.date]));
    art.appendChild(head);

    var h3 = document.createElement("h3");
    var a = document.createElement("a");
    a.href = "record/" + row[IDX.id] + ".html";
    a.textContent = row[IDX.en] || row[IDX.orig];
    h3.appendChild(a);
    art.appendChild(h3);

    if (row[IDX.en] && row[IDX.orig]) {
      var orig = text("p", "original", row[IDX.orig]);
      orig.setAttribute("lang", lang ? lang.code : "zh");
      art.appendChild(orig);
    }

    /* Editorial language name, never the raw tag. */
    art.appendChild(text("p", "meta", src.label + " · " +
      (lang ? lang.label : "—") + " · " + data.states[row[IDX.state]].label));
    return art;
  }

  function render(announce) {
    var total = view.length;
    var pages = Math.max(1, Math.ceil(total / PER_PAGE));
    if (page > pages) page = pages;
    var start = (page - 1) * PER_PAGE;
    var slice = view.slice(start, start + PER_PAGE);

    els.results.textContent = "";
    var frag = document.createDocumentFragment();
    slice.forEach(function (row) { frag.appendChild(card(row)); });
    els.results.appendChild(frag);

    var summary;
    if (total === 0) {
      summary = "No records match these filters.";
      els.range.textContent = "";
    } else {
      summary = "Showing " + (start + 1).toLocaleString() + "–" +
        (start + slice.length).toLocaleString() + " of " +
        total.toLocaleString() + " records";
      els.range.textContent = summary + " · page " + page + " of " + pages;
    }
    /* A genuine empty result set, distinct from an unavailable index. */
    els.empty.hidden = total !== 0;
    els.pager.hidden = total === 0;
    els.prev.disabled = page <= 1;
    els.next.disabled = page >= pages;
    if (announce) els.live.textContent = summary;
  }

  function update(push, resetPage) {
    if (resetPage) page = 1;
    view = data.records.filter(matches);
    writeUrl(push);
    render(true);
  }

  function wire() {
    var debounce = null;
    els.q.addEventListener("input", function () {
      clearTimeout(debounce);
      debounce = setTimeout(function () { update(false, true); }, 180);
    });
    FACETS.concat(["from", "to"]).forEach(function (k) {
      els[k].addEventListener("change", function () { update(false, true); });
    });
    els.prev.addEventListener("click", function () {
      if (page > 1) { page--; update(true, false); window.scrollTo(0, 0); }
    });
    els.next.addEventListener("click", function () {
      page++; update(true, false); window.scrollTo(0, 0);
    });
    els.reset.addEventListener("click", function () {
      els.q.value = els.from.value = els.to.value = "";
      FACETS.forEach(function (k) { els[k].value = ""; });
      update(true, true);
      els.q.focus();
    });
    window.addEventListener("popstate", function () {
      readUrl(); view = data.records.filter(matches); render(true);
    });
  }

  function unavailable() {
    /* Never "0 results": the corpus is not empty, the index is unusable.
       Restores the hidden state explicitly so a throw mid-render cannot
       strand controls or partial cards. Week path and volume stay visible. */
    els.controls.hidden = true;
    root.hidden = true;
    els.results.textContent = "";
    els.error.hidden = false;
  }

  /* Cache discriminator from PUBLIC snapshot facts only; the internal
     fingerprint is a build guard, never shipped. */
  fetch("corpus-index.json?s=" + encodeURIComponent(WANT_DATE) + "-" +
        WANT_COUNT, { credentials: "omit" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (json) {
      if (!valid(json)) throw new Error("snapshot mismatch");
      data = json;
      fillOptions(els.source, data.sources, "All sources");
      fillOptions(els.institution, data.institutions, "All institutions");
      fillOptions(els.language, data.languages, "All original languages");
      fillOptions(els.status, data.states, "All processing states");
      readUrl();
      els.controls.hidden = false;
      root.hidden = false;
      wire();
      view = data.records.filter(matches);
      render(false);
    })
    .catch(unavailable);
})();
