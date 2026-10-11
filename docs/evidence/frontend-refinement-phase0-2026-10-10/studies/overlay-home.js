/* Phase 0 study overlay — home (disposable). In Phase 1 these nodes are
   rendered by templates at build time; no runtime script is added to home. */
(function () {
  var D = window.STUDY;
  var SEAT = { china: "Beijing", singapore: "Singapore" };
  // Source-stated dates verified from record/50xx.html p.record-source-line.
  var DATES = { "5071": "10 October 2026", "5070": "10 October 2026", "5069": "10 October 2026", "5068": "10 October 2026" };
  document.querySelectorAll(".home-recent .record-row").forEach(function (li) {
    var desk = li.querySelector(".row-side a").getAttribute("href").replace(".html", "");
    var via = li.querySelector(".row-via").textContent;
    var type = /PLA Daily/.test(via) ? "armed_forces_newspaper" : "ministry_website";
    var fig = document.createElement("figure");
    fig.className = "rc-emblem";
    fig.setAttribute("aria-hidden", "true");
    fig.innerHTML = studyEmblem(desk, { seat: true, glyph: type, seatR: desk === "singapore" ? 2.2 : 2.8 }) + "<figcaption>" + SEAT[desk] + " seat</figcaption>";
    li.insertBefore(fig, li.firstChild);
    var id = li.querySelector("h3 a").getAttribute("href").match(/(\d+)/)[1];
    var p = document.createElement("p");
    p.className = "rc-date";
    p.innerHTML = 'Source-stated date <time datetime="2026-10-10">' + DATES[id] + "</time>";
    li.insertBefore(p, fig.nextSibling);
  });

  var band = document.querySelector(".home-coast-band");
  if (band) {
    var f = document.createElement("figure");
    f.className = "rl-wrap";
    f.setAttribute("aria-hidden", "true");
    f.innerHTML = studyEmblem("strait", { prefix: "rl", pad: 0 });
    band.insertBefore(f, band.firstChild);
    var cap = document.createElement("p");
    cap.className = "rl-cap";
    cap.textContent = "Singapore Strait coastline: Natural Earth 1:10m. The offshore lines are drawn water-lining, not depth or territory.";
    band.appendChild(cap);
  }

  var desks = document.querySelector(".home-desks");
  if (desks) {
    var head = desks.querySelector(".home-section-head");
    var note = desks.querySelector(".home-coverage-note");
    var list = desks.querySelector(".home-desk-list");
    var wires = document.createElementNS(SVGNS, "svg");
    wires.setAttribute("class", "hd-wires");
    wires.setAttribute("viewBox", "0 0 100 84");
    wires.setAttribute("preserveAspectRatio", "none");
    wires.setAttribute("aria-hidden", "true");
    wires.innerHTML = '<path class="w-china" pathLength="1" d="M23.7 0V84"/><path class="w-singapore" pathLength="1" d="M76.3 0V84"/>';
    var headLink = head.querySelector("a");
    head.parentNode.insertBefore(wires, head.nextSibling);
    list.parentNode.insertBefore(note, list.nextSibling);
    if (headLink) note.parentNode.insertBefore(headLink, note.nextSibling);
    list.querySelectorAll("a").forEach(function (a) {
      var slug = a.getAttribute("href").replace(".html", "");
      a.insertAdjacentHTML("afterbegin", studyEmblem(slug, { seat: true, seatR: slug === "singapore" ? 2.2 : 2.8 }));
    });
  }
})();
