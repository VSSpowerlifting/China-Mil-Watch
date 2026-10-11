/* Phase 0 study helper (disposable). Builds emblem SVG strings from
   window.STUDY.emblems: real Natural Earth geometry, desk-map projection. */
window.SVGNS = "http://www.w3.org/2000/svg";
window.studyEmblem = function (slug, o) {
  o = o || {};
  var e = window.STUDY.emblems[slug];
  var vb = e.viewBox.split(" ").map(Number), pad = o.pad == null ? 9 : o.pad, p = o.prefix || "rc";
  var w = vb[2], h = vb[3];
  var s = '<svg xmlns="' + SVGNS + '" viewBox="' + (-pad) + " " + (-pad) + " " + (w + 2 * pad) + " " + (h + 2 * pad) +
    '" aria-hidden="true" focusable="false"' + (o.cls ? ' class="' + o.cls + '"' : "") + ">";
  if (!o.noWater) {
    s += '<g class="' + p + '-wl">';
    for (var i = 1; i <= 5; i++) s += '<path class="w' + i + '" pathLength="1" d="' + e.d + '"/>';
    s += "</g>";
  }
  s += '<path class="' + p + '-land-side ' + p + '-side" d="' + e.d + '"/>';
  s += '<path class="' + p + '-land" d="' + e.d + '"/>';
  if (o.seat && e.seat) s += '<circle class="' + p + '-seat" cx="' + e.seat[0] + '" cy="' + e.seat[1] + '" r="' + (o.seatR || 2.8) + '"/>';
  if (o.glyph) s += window.studyGlyph(o.glyph, w + pad - 19, h + pad - 15, p);
  return s + "</svg>";
};
/* Source-type glyphs: generic forms of a printed newspaper and a web page.
   Never a seal, crest, flag or institutional logo. */
window.studyGlyph = function (type, x, y, p) {
  var g = '<g class="' + p + '-glyph" transform="translate(' + x + " " + y + ')">';
  if (type === "armed_forces_newspaper" || type === "state_linked_newspaper") {
    g += '<rect x="0" y="0" width="18" height="14" rx="1"/><path d="M3 4H15M3 7H9M3 10H9M11 7H15V11H11Z"/>';
  } else {
    g += '<rect x="0" y="0" width="18" height="14" rx="1"/><path d="M0 4H18M3 8H15M3 11H11"/><path d="M2.4 2H2.6M4.6 2H4.8" stroke-linecap="round" stroke-width="1.6"/>';
  }
  return g + "</g>";
};
