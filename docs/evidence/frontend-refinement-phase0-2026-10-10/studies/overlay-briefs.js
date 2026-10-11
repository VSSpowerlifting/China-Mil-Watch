/* Phase 0 study overlay — Briefs catalogue (disposable). In Phase 1 these
   nodes are rendered at build time from sidecars + the image resolver; the
   page gains no runtime script. Every image below was verified to exist in
   output/ and to be the same image the opened edition already shows. */
(function () {
  var NO81 = document.documentElement.classList.contains("study-no81");
  var P = window.STUDY.plates;
  var C81 = "Image: PLA Daily (81.cn). Context, not evidence.";
  var V = function (d) { return "the-pla-watch/media/" + d + "-veil.jpg"; };
  var CUR = function (id) { return "assets/editorial/derivatives/" + id + "-duo-navy.jpg"; };
  var B = {
    17: { plate: ["china", "singapore"] },
    16: { plate: ["china", "singapore"] },
    15: { img: "briefs/media/maritime-cooperation-2026-veil.jpg", r81: 1, credit: "Photo: 葛瀚强 / PLA Daily (via 81.cn). Context, not evidence." },
    14: { plate: ["china"] },
    13: { img: V("2026-08-08"), r81: 1, credit: C81 },
    12: { plate: ["china"], held: 1 },
    11: { img: V("2026-07-18"), r81: 1, credit: C81 },
    10: { img: CUR("jin-class-type-094-ssbn"), credit: "U.S. government photo, via CRS report RL33153 (R. O'Rourke). Public domain, via Wikimedia Commons. Context, not evidence." },
    9: { img: CUR("scarborough-shoal-iss"), credit: "NASA / ISS Expedition 45. Public domain, via Wikimedia Commons. Context, not evidence." },
    8: { img: CUR("liaoning-j15-recovery"), credit: "Japan Ministry of Defense, Joint Staff (統合幕僚監部). CC BY 4.0, toned by IPR, via Wikimedia Commons. Context, not evidence." },
    7: { img: V("2026-06-20"), r81: 1, credit: C81 },
    6: { img: V("2026-06-13"), r81: 1, credit: C81 },
    5: { img: V("2026-06-06"), r81: 1, credit: C81 },
    4: { plate: ["china"] },
    3: { img: V("2026-05-23"), r81: 1, credit: C81 },
    2: { img: V("2026-05-16"), r81: 1, credit: C81 },
    1: { img: "the-pla-watch/media/2026-05-10-auto-image-optimized.jpg", photo: 1, credit: "Roberto Villa Jr. Public domain, via Wikimedia Commons. Context, not evidence." }
  };
  var SEAT = { china: "Beijing", singapore: "Singapore" };

  // One shared copy of the regional land geometry; plates <use> it.
  var defs = document.createElementNS(SVGNS, "svg");
  defs.setAttribute("aria-hidden", "true");
  defs.setAttribute("style", "position:absolute;width:0;height:0");
  defs.innerHTML = '<defs><path id="pl-land" d="' + P.paths.land + '"/><path id="pl-china" d="' + P.paths.china +
    '"/><path id="pl-singapore" d="' + P.paths.singapore + '"/></defs>';
  document.body.appendChild(defs);

  function plate(desks) {
    var s = '<svg viewBox="' + P.viewBox + '" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">';
    s += '<g class="pl-wl"><use href="#pl-land" class="w1"/><use href="#pl-land" class="w2"/></g><use href="#pl-land" class="pl-land"/>';
    desks.forEach(function (d) { s += '<use href="#pl-' + d + '" class="pl-desk"/>'; });
    desks.forEach(function (d) {
      var c = P.seats[d];
      s += '<circle class="pl-seat" cx="' + c[0] + '" cy="' + c[1] + '" r="2.4"/>' +
        '<text class="pl-lab" x="' + (c[0] + 6) + '" y="' + (c[1] + 3.5) + '">' + SEAT[d] + "</text>";
    });
    return s + "</svg>";
  }

  document.querySelectorAll(".issue-ledger--briefs .issue-ledger-row").forEach(function (row) {
    var no = +row.querySelector(".issue-no").textContent.replace(/\D/g, "");
    var b = B[no];
    if (!b) return;
    row.classList.add("bc");
    var fig = document.createElement("figure");
    fig.className = "bc-media";
    if (b.img && !(NO81 && b.r81)) {
      fig.classList.add(b.photo ? "bc-media--photo" : "bc-media--veil");
      fig.innerHTML = '<div class="bc-print"><img src="' + b.img + '" alt="" loading="lazy" decoding="async"></div><figcaption>' + b.credit + "</figcaption>";
    } else if (b.img) {
      fig.classList.add("bc-media--withheld");
      fig.innerHTML = '<div class="bc-print"><span>PLA Daily photograph. Shown in the private review build only; not reproduced in this packet.</span></div><figcaption>' + b.credit + "</figcaption>";
    } else {
      fig.classList.add("bc-media--plate");
      fig.innerHTML = '<div class="bc-print">' + plate(b.plate) + '<span class="pl-tag">Editorial plate</span></div><figcaption>' +
        (b.held ? "No photograph shown: the edition’s image is held for a credit check. " : "No source photograph. ") +
        "Outlines from Natural Earth; dots mark desk seats.</figcaption>";
    }
    row.insertBefore(fig, row.firstChild);
  });

  // Hero: the lead Brief's Singapore desk, drawn as a raised island plate.
  var lead = document.querySelector(".briefs-lead");
  if (lead && /Singapore Desk/.test(lead.textContent)) {
    var f = document.createElement("figure");
    f.className = "bh-island";
    f.setAttribute("aria-hidden", "true");
    f.innerHTML = studyEmblem("singapore", { prefix: "bh", pad: 16, seat: false }) +
      "<figcaption>Singapore Island. Natural Earth 1:10m.</figcaption>";
    lead.appendChild(f);
  }
})();
