/* Citation and link copy controls, and the way back to results — progressive
 * enhancement only.
 *
 * Every citation on the page is rendered, visible and selectable without this
 * script. It adds a button that puts the same string on the clipboard. The
 * buttons ship `hidden` and are revealed here, so nothing ever looks operative
 * when nothing can operate it.
 *
 * Two rules, both about not creating a second copy of a citation:
 *   1. The copied text is read from the rendered element's textContent.
 *   2. No corpus value is ever written through innerHTML.
 *
 * Feedback is local and visible: each block carries its own polite status
 * line beside its own button, empty until something happens. On failure the
 * text is selected, so the manual remedy is one keystroke away.
 */
(function () {
  "use strict";

  /* Back to results, when — and only when — the reader came here from this
     site's search, the week list or a week page. The link goes back through
     history, so the search, its filters and the scroll position return as
     they were; opened in a new tab, it follows the referring address. */
  var back = document.getElementById("back-link");
  if (back && document.referrer) {
    try {
      var ref = new URL(document.referrer), link = back.querySelector("a");
      var from = ref.pathname.match(/\/(archive|corpus|week-[\d-]+)\.html$/);
      if (ref.origin === location.origin && from) {
        link.href = ref.href;
        link.textContent = from[1] === "archive"
          ? (ref.search ? "Back to search results" : "Back to records")
          : from[1] === "corpus" ? "Back to records by week" : "Back to the week";
        link.addEventListener("click", function (e) {
          if (window.history.length > 1) { e.preventDefault(); history.back(); }
        });
        back.hidden = false;
      }
    } catch (err) { /* an unparseable referrer leaves the breadcrumb alone */ }
  }

  var buttons = document.querySelectorAll("button[data-copy], button[data-copy-link]");
  if (!buttons.length) return;

  /* Each control reports in the status line of its own block: a record's
     citation block, the record rail's share block, or an issue's citation
     disclosure (`.ed-cite`, on the series and brief pages). */
  function statusFor(button) {
    var block = button.closest(".cite-block, .rail-block, .ed-cite");
    return block ? block.querySelector(".cite-status") : null;
  }

  /* Clearing first matters: assigning the same string twice is not a change,
     so a second identical result would never be announced. */
  function announce(button, message) {
    var status = statusFor(button);
    if (!status) return;
    status.textContent = "";
    window.setTimeout(function () { status.textContent = message; }, 60);
  }

  function select(node) {
    if (!node || !window.getSelection) return;
    var range = document.createRange();
    range.selectNodeContents(node);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  /* The page's own address: the canonical when the build wrote one, else this
     location without query or fragment. Never a parameterised URL. */
  function pageLink() {
    var canon = document.querySelector('link[rel="canonical"]');
    return canon ? canon.href : location.origin + location.pathname;
  }

  function finish(button, ok, source, text) {
    var isLink = button.hasAttribute("data-copy-link");
    button.textContent = ok ? "Copied" : "Copy failed";
    button.classList.toggle("is-done", ok);
    button.classList.toggle("is-failed", !ok);
    if (!ok) select(source);
    announce(button, ok
      ? (isLink ? "Link copied to the clipboard." : "Citation copied to the clipboard.")
      : isLink
        ? "Copy failed. The link is " + text + " — select it and copy it manually."
        : "Copy failed. The citation text is selectable — select it and copy it "
          + "manually.");
    window.setTimeout(function () {
      button.textContent = button.getAttribute("data-label");
      button.classList.remove("is-done", "is-failed");
    }, 4000);
  }

  Array.prototype.forEach.call(buttons, function (button) {
    button.setAttribute("data-label", button.textContent);
    button.hidden = false;

    button.addEventListener("click", function () {
      var source = button.hasAttribute("data-copy")
        ? document.getElementById(button.getAttribute("data-copy")) : null;
      var text = source
        ? source.textContent.replace(/\s+/g, " ").trim() : pageLink();
      var clipboard = navigator.clipboard;
      if ((button.hasAttribute("data-copy") && !source) ||
          !clipboard || !clipboard.writeText) {
        finish(button, false, source, text);
        return;
      }
      clipboard.writeText(text).then(
        function () { finish(button, true, source, text); },
        function () { finish(button, false, source, text); }
      );
    });
  });
})();
