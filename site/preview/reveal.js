/*
 * Reveal on scroll — the whole of this publication's scripted motion.
 *
 * Three properties, in order of importance:
 *
 *   1. Content is never behind it. The start state lives in styles.css under
 *      `html.js-reveal` AND under `prefers-reduced-motion: no-preference`.
 *      This file is what adds that class, so a reader without JavaScript,
 *      a reader who asked for less motion, and a printer all get the
 *      finished page without this file having an opinion.
 *   2. It cannot strand the page. The class is removed after 1.5s no matter
 *      what the observer did, so a browser that runs this script and then
 *      fails to observe still ends with everything visible.
 *   3. It is one-shot. An element that has arrived is unobserved; nothing
 *      re-animates on the way back up, and there is no scroll listener.
 *
 * ~900 bytes, no dependencies. Loaded synchronously in <head> so the class
 * lands before first paint and nothing flashes in and back out.
 */
(function () {
  "use strict";
  var doc = document.documentElement;

  // Bail before touching anything if the browser cannot do this properly or
  // the reader has asked for less movement. Bailing means: no class, no start
  // state, finished page.
  if (!("IntersectionObserver" in window)) return;
  if (window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  doc.classList.add("js-reveal");

  function release() { doc.classList.remove("js-reveal"); }

  function start() {
    var targets = document.querySelectorAll("[data-reveal]");
    if (!targets.length) { release(); return; }

    var answered = false;

    var io = new IntersectionObserver(function (entries) {
      answered = true;
      for (var i = 0; i < entries.length; i++) {
        if (!entries[i].isIntersecting) continue;
        entries[i].target.classList.add("is-in");
        io.unobserve(entries[i].target);
      }
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.01 });

    for (var i = 0; i < targets.length; i++) io.observe(targets[i]);

    // The failsafe, and the reason it is conditional. An IntersectionObserver
    // delivers an initial callback for every target it is given, so one
    // callback proves the mechanism works and the elements still hidden are
    // hidden because they are genuinely below the fold. Releasing then would
    // dump the whole page into view at 1.5s, which is not a safety net — it
    // is the bug. The net is only for the case where nothing answered at all.
    window.setTimeout(function () { if (!answered) release(); }, 1500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
