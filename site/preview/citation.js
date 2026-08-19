/* Citation copy controls — progressive enhancement only.
 *
 * Every citation on the page is rendered, visible and selectable without this
 * script. It adds one thing: a button that puts the same string on the
 * clipboard. The buttons ship `hidden` and are revealed here, so nothing ever
 * looks operative when nothing can operate it.
 *
 * Two rules, both about not creating a second copy of a citation:
 *   1. The copied text is read from the rendered element's textContent. There
 *      is no data-attribute or markup duplicate to drift away from what the
 *      reader can see and select.
 *   2. No corpus value is ever written through innerHTML. Stored titles are
 *      source data; they are read, never re-templated.
 *
 * Feedback is local and visible. Each block carries its own polite status
 * line beside its own button: a page-level region would announce a result far
 * from the control that produced it, and on Analysis there are thirteen
 * controls. The line is empty until something happens, so it costs nothing on
 * load, and the failure message is readable by everyone rather than only by a
 * screen reader.
 */
(function () {
  "use strict";

  var buttons = document.querySelectorAll("button[data-copy]");
  if (!buttons.length) return;

  /* The status line sharing this button's block. */
  function statusFor(button) {
    return button.parentNode
      ? button.parentNode.querySelector(".cite-status") : null;
  }

  /* Clearing first matters: assigning the same string twice is not a change,
     so a second identical result would never be announced. */
  function announce(button, message) {
    var status = statusFor(button);
    if (!status) return;
    status.textContent = "";
    window.setTimeout(function () { status.textContent = message; }, 60);
  }

  /* Honest on failure: it says the copy did not happen and points at the text,
     which is still right there and still selectable. */
  function finish(button, ok) {
    button.textContent = ok ? "Copied" : "Copy failed";
    announce(button, ok
      ? "Citation copied to the clipboard."
      : "Copy failed. The citation text is selectable — select it and copy it "
        + "manually.");
    window.setTimeout(function () {
      button.textContent = button.getAttribute("data-label");
    }, 4000);
  }

  Array.prototype.forEach.call(buttons, function (button) {
    button.setAttribute("data-label", button.textContent);
    button.hidden = false;

    button.addEventListener("click", function () {
      var source = document.getElementById(button.getAttribute("data-copy"));
      var clipboard = navigator.clipboard;
      if (!source || !clipboard || !clipboard.writeText) {
        finish(button, false);
        return;
      }
      /* The rendered string itself. Collapsing runs of whitespace only
         normalizes what HTML wrapping introduced; the citation is emitted on
         one line, so this changes nothing about its content. */
      var text = source.textContent.replace(/\s+/g, " ").trim();
      clipboard.writeText(text).then(
        function () { finish(button, true); },
        function () { finish(button, false); }
      );
    });
  });
})();
