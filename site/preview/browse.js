/* Records finder. The index loads on first request, and only if it is
 * this page's snapshot. State lives in the URL. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); },
      root = $("browse"), A = Array.isArray;
  if (!root || !window.fetch || !window.URLSearchParams) return;
  var form = $("controls"), out = $("results"), range = $("result-range"),
      live = $("result-live"), wait = $("index-state"), fail = $("index-error"),
      none = $("no-results"), prev = $("page-prev"), next = $("page-next"),
      chips = $("chips"), reset = $("f-reset");
  var KEYS = "q desk source status sort institution language from to trail".split(" ");
  var NAME = {q: "Title", from: "From", to: "To"}, F = {},
      TR = "In an analysis source trail";
  KEYS.forEach(function (k) { F[k] = $("f-" + k); });
  var PER = 50, data, pending, view = [], page = 1, trail = {};
  var WANT = root.getAttribute("data-snapshot-date"),
      COUNT = parseInt(root.getAttribute("data-snapshot-records"), 10);

  /* Every row, never a sample. */
  function valid(d) {
    if (!d || !d.snapshot || !A(d.records)) return false;
    if (d.snapshot.date !== WANT || d.snapshot.records !== COUNT ||
        d.records.length !== COUNT || !A(d.fields) ||
        d.fields.join() !== "id,date,source,state,title_en,title_orig")
      return false;
    if (!["sources", "institutions", "languages", "states"].every(
        function (k) { return A(d[k]) && d[k].length; }))
      return false;
    for (var i = 0; i < d.records.length; i++) {
      var r = d.records[i];
      if (!A(r) || r.length !== 6 || !d.sources[r[2]] ||
          !d.states[r[3]]) return false;
    }
    return true;
  }

  function get(k) {
    var e = F[k];
    return e.type === "checkbox" ? (e.checked ? "1" : "") : e.value.trim();
  }
  function put(k, v) {
    var e = F[k];
    if (e.type === "checkbox") e.checked = v === "1";
    else e.value = v || (k === "sort" ? "new" : "");
    if (e.selectedIndex < 0) e.selectedIndex = 0;
  }
  function filtered() {
    return KEYS.some(function (k) { return k !== "sort" && get(k); });
  }
  function asked() { return filtered() || page > 1 || get("sort") === "old"; }
  function readUrl() {
    var p = new URLSearchParams(location.search);
    KEYS.forEach(function (k) { put(k, p.get(k)); });
    page = Math.max(1, parseInt(p.get("page"), 10) || 1);
  }
  function writeUrl(push) {
    var p = new URLSearchParams();
    KEYS.forEach(function (k) {
      var v = get(k);
      if (v && !(k === "sort" && v === "new")) p.set(k, v);
    });
    if (page > 1) p.set("page", page);
    p = p.toString();
    history[push ? "pushState" : "replaceState"](null, "",
      location.pathname + (p ? "?" + p : ""));
  }

  function matches(r) {
    var s = data.sources[r[2]], q = get("q").toLowerCase(), v;
    if (q && (r[4] + " " + r[5]).toLowerCase().indexOf(q) < 0) return false;
    if ((v = get("desk")) && !(s.desk && s.desk.code === v)) return false;
    if ((v = get("source")) && s.code !== v) return false;
    if ((v = get("institution")) &&
        (data.institutions[s.institution] || {}).code !== v) return false;
    if ((v = get("language")) &&
        (data.languages[s.language] || {}).code !== v) return false;
    if ((v = get("status")) && data.states[r[3]].code !== v) return false;
    /* Inclusive, on the source-stated date. */
    if ((v = get("from")) && r[1] < v) return false;
    if ((v = get("to")) && r[1] > v) return false;
    return !(get("trail") && !trail[r[0]]);
  }

  function el(tag, cls, txt, kid) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    if (kid) e.appendChild(kid);
    return e;
  }
  function n(x) { return x.toLocaleString("en-US"); }

  /* _records.html record_row, field for field. */
  function card(r) {
    var s = data.sources[r[2]], lang = data.languages[s.language],
        who = data.institutions[s.institution],
        st = data.states[r[3]], a = el("a", null, r[4] || r[5]),
        h = el("h3", null, null, a), main = el("div", null, null, h),
        tags = el("p", "row-tags"), side = el("p", "row-side"),
        li = el("li", "record-row", null, main);
    a.href = "record/" + r[0] + ".html";
    if (!r[4] && lang) h.setAttribute("lang", lang.code);
    if (r[4] && r[5] && r[5].trim() !== r[4].trim()) {
      var o = main.appendChild(el("p", "original", r[5]));
      if (lang) o.setAttribute("lang", lang.code);
    }
    if (st.code === "analyzed")
      tags.appendChild(el("span", "state state--analyzed", st.label));
    if (trail[r[0]])
      tags.appendChild(el("span", "trail-tag", TR));
    if (tags.firstChild) main.appendChild(tags);
    side.appendChild(el("span", "row-who", who ? who.label : s.label));
    side.appendChild(el("span", "row-via",
      [who && s.label, lang && lang.label].filter(Boolean).join(" · ")));
    if (s.desk) side.appendChild(el("a", null, s.desk.label)).href = s.desk.route;
    if (st.code !== "analyzed")
      side.appendChild(el("span", "state state--" + st.code, st.label));
    li.appendChild(side);
    return li;
  }

  function cal(date, o) {
    o.timeZone = "UTC";
    return new Date(date + "T00:00:00Z").toLocaleDateString("en-US", o);
  }
  function day(date) {
    var mo = cal(date, {month: "long", year: "numeric"}),
        t = el("time", null, null, el("span", "day-num", +date.slice(8, 10))),
        sec = el("section", "records-day", null, el("p", "day-date", null, t));
    t.setAttribute("datetime", date);
    t.appendChild(el("span", "day-month", mo));
    t.appendChild(el("span", "day-week", cal(date, {weekday: "long"})));
    return sec;
  }

  function render() {
    var total = view.length, pages = Math.max(1, Math.ceil(total / PER));
    if (page > pages) page = pages;
    var start = (page - 1) * PER, rows = view.slice(start, start + PER),
        wrap = el("div", "records-days"), list, last = "";
    wrap.setAttribute("data-from-index", "");
    rows.forEach(function (r) {
      if (r[1] !== last) {
        last = r[1];
        list = wrap.appendChild(day(r[1])).appendChild(el("ul", "record-list"));
      }
      list.appendChild(card(r));
    });
    out.textContent = "";
    out.appendChild(wrap);
    var msg = total ? "Showing " + n(start + 1) + "–" + n(start + rows.length) +
      " of " + n(total) + (filtered() ? " matching records" : " records")
      : "No records match these filters.";
    range.textContent = total ? msg + (pages > 1 ? " · page " + page +
      " of " + pages : "") : "";
    live.textContent = msg;
    none.hidden = total !== 0;
    prev.hidden = next.hidden = pages < 2;
    prev.disabled = page <= 1;
    next.disabled = page >= pages;
  }

  function drawChips() {
    chips.textContent = "";
    KEYS.forEach(function (k) {
      var v = get(k), e = F[k];
      if (!v || k === "sort") return;
      var label = (NAME[k] ? NAME[k] + ": " : "") + (k === "trail"
        ? TR : e.tagName === "SELECT"
        ? e.options[e.selectedIndex].text.replace(/ \([\d,]+\)$/, "") : v);
      var b = chips.appendChild(el("li")).appendChild(el("button", "chip", label));
      b.type = "button";
      b.setAttribute("aria-label", "Remove filter: " + label);
      b.onclick = function () { put(k, ""); go(true, true); F.q.focus(); };
    });
    reset.hidden = !filtered();
  }

  /* An unusable index, never "0 results". */
  function unavailable() {
    wait.hidden = root.hidden = prev.hidden = next.hidden = true;
    out.classList.remove("is-updating");
    fail.hidden = false;
  }

  function load() {
    if (!pending) {
      wait.hidden = false;
      /* Public snapshot facts only. */
      pending = fetch("corpus-index.json?s=" + encodeURIComponent(WANT) + "-" +
                      COUNT, {credentials: "omit"})
        .then(function (r) { if (!r.ok) throw Error(r.status); return r.json(); })
        .then(function (j) {
          if (!valid(j)) throw Error("invalid index");
          (j.trail_ids || []).forEach(function (id) { trail[id] = 1; });
          wait.hidden = true;
          return (data = j);
        });
      pending.catch(unavailable);
    }
    return pending;
  }

  function go(push, first) {
    if (first) page = 1;
    out.classList.add("is-updating");
    load().then(function () {
      view = data.records.filter(matches);
      if (get("sort") === "old") view.reverse();
      drawChips();
      render();
      writeUrl(push);
      out.classList.remove("is-updating");
    }, function () {});
  }

  var timer;
  F.q.onfocus = function () { load().then(null, function () {}); };
  F.q.oninput = function () {
    clearTimeout(timer);
    timer = setTimeout(function () { go(false, true); }, 200);
  };
  KEYS.forEach(function (k) {
    if (k !== "q") F[k].onchange = function () { go(true, true); };
  });
  form.onsubmit = function (e) { e.preventDefault(); go(true, true); };
  reset.onclick = function () {
    KEYS.forEach(function (k) { put(k, ""); });
    go(true, true);
    F.q.focus();
  };
  /* Focus the range line: a disabled button would drop focus. */
  function turn(d) { page += d; go(true); range.focus(); }
  prev.onclick = function () { if (page > 1) turn(-1); };
  next.onclick = function () { turn(1); };
  window.onpopstate = function () {
    readUrl();
    if (data || asked()) go(false);
  };

  root.hidden = form.hidden = next.hidden = false;
  readUrl();
  if (asked()) go(false);
})();
