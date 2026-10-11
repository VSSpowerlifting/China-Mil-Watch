/* Phase 0 study overlay — Desks map + "What each desk reads" (disposable).
   Phase 1 renders all of this at build time (desk_map.py + desks template);
   the only runtime script stays the existing desk-map.js. */
(function () {
  var D = window.STUDY;
  var FLAG = { china: "cn", singapore: "sg", japan: "jp", vietnam: "vn", "us-indopacific": "us" };
  var EMB = { china: "china", singapore: "singapore", japan: "japan", vietnam: "vietnam", "us-indopacific": "hawaii" };
  var SEAT = { china: "Beijing", singapore: "Singapore", japan: "Tokyo", vietnam: "Hanoi", "us-indopacific": "Hawaii" };
  var TONE = { live: "on", shadow: "quiet", research: "quiet", access_blocked: "blocked" };
  var TYPE = {
    armed_forces_newspaper: "Armed forces newspaper", ministry_website: "Ministry website",
    state_news_agency: "State news agency", state_linked_newspaper: "State-linked newspaper",
    armed_forces_english_portal: "Armed forces English portal", military_journal_editorial: "Military journal"
  };
  var LANG = { "zh-Hans": "Chinese", en: "English", ja: "Japanese", vi: "Vietnamese" };
  function flag(slug) {
    return '<span class="dp-flag" aria-hidden="true"><img alt="" width="22" height="16.5" src="data:image/svg+xml;charset=utf-8,' +
      encodeURIComponent(D.flags[FLAG[slug]]) + '"></span>';
  }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;"); }

  /* 1. Map: the chart holds only the SVG, so plate percentages resolve
     against the map box (Phase 1: template moves note + context out). */
  var fig = document.querySelector(".deskmap"), stage = fig.querySelector(".deskmap-stage");
  var ctx = fig.querySelector(".deskmap-context"), note = fig.querySelector(".deskmap-chart-note");
  stage.after(note); note.after(ctx);
  var reg = {};
  D.sources._registry && Object.keys(D.sources._registry).forEach(function (k) { reg[k] = D.sources._registry[k]; });
  fig.querySelectorAll(".deskmap-plate").forEach(function (p) {
    var slug = p.dataset.desk, tone = TONE[reg[slug].status];
    p.classList.add("dp", "dp--" + tone);
    p.insertAdjacentHTML("afterbegin", flag(slug));
  });
  fig.querySelectorAll(".dm-country").forEach(function (c) {
    var slug = c.dataset.desk;
    c.classList.add(slug === "us-indopacific" ? "dm-ref" : "dm-" + TONE[reg[slug].status]);
  });
  fig.querySelectorAll(".dm-anchor").forEach(function (a) { a.classList.add("dm-" + TONE[reg[a.dataset.desk].status]); });
  /* Study-only collision fix (Phase 1: geography.json wide placement):
     the Japan plate rises so it clears the US Indo-Pacific label. */
  var jl = fig.querySelector('.dm-leader--wide[data-desk="japan"]');
  if (jl) jl.setAttribute("points", "797.0,227.1 960.0,64.1");
  var key = fig.querySelector(".deskmap-key");
  key.insertAdjacentHTML("afterbegin",
    '<span class="dk"><i class="dk-sw dk-on"></i>Collecting into the record</span>' +
    '<span class="dk"><i class="dk-sw dk-quiet"></i>Declared, not collecting</span>' +
    '<span class="dk"><i class="dk-sw dk-ref"></i>Seat only: regional reference, not a country fill</span>');

  /* 2. What each desk reads: one panel per desk, all text complete. */
  document.querySelectorAll(".scope-register .scope-entry").forEach(function (e) {
    var a = e.querySelector("dt a"), slug = a.getAttribute("href").replace(".html", ""), r = reg[slug], tone = TONE[r.status];
    e.classList.add("sp", "sp--" + tone);
    var head = '<div class="sp-geo">' + studyEmblem(EMB[slug], { prefix: "sp", pad: 6, seat: true, seatR: slug === "singapore" ? 6 : 3.2 }) +
      '<p class="sp-seatname">' + SEAT[slug] + ' seat</p></div>';
    e.insertAdjacentHTML("afterbegin", head);
    e.querySelector("dt").insertAdjacentHTML("afterbegin", flag(slug));
    var dd = e.querySelector("dd"), foot = dd.querySelector(".card-foot");
    var src = D.sources[slug], h = "";
    if (src) {
      h += '<h4 class="sp-h">' + (tone === "on" ? "Sources in the manifest" : "Sources in the shadow manifest") + '</h4><ul class="sp-src">';
      src.forEach(function (s) {
        var t = s.type ? TYPE[s.type] : "";
        var langs = [].concat(s.lang || []).map(function (l) { return LANG[l] || l; }).join(", ");
        /* Manifest state only. Whether a source actually collects comes from
         run health in Phase 1 (source_health_report), never from this flag. */
      var st = s.enabled ? (tone === "on" ? "Configured" : "Enabled in shadow manifest, not public") : "Not enabled";
        h += '<li class="' + (s.enabled ? "" : "is-off") + '">' + studyGlyph(s.type || "feed", 0, 0, "sp").replace("<g", '<svg viewBox="-1 -1 20 16" aria-hidden="true" focusable="false"><g') + "</svg>" +
          '<span class="sp-src-name">' + esc(s.name) + "</span>" +
          '<span class="sp-src-meta">' + [t, langs, st].filter(Boolean).join(" · ") + "</span></li>";
      });
      h += "</ul>";
    } else {
      h += '<p class="sp-none">No source manifest is listed for this desk.</p>';
    }
    h += '<h4 class="sp-h">Limits</h4><ul class="sp-limits">' + r.limits.map(function (l) { return "<li>" + esc(l) + "</li>"; }).join("") + "</ul>";
    var locate = '<a class="sp-locate" href="#desk-' + slug + '">Locate on the map</a>';
    if (foot) { foot.insertAdjacentHTML("beforebegin", h); foot.insertAdjacentHTML("beforeend", locate); }
    else dd.insertAdjacentHTML("beforeend", h + '<p class="card-foot">' + locate + "</p>");
  });
})();
