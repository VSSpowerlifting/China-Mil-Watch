/* Enhancement over source-approved HTML only; nothing is fetched or inferred. */
(() => {
  "use strict";
  for (const region of document.querySelectorAll("[data-reference-browser]")) {
    const controls = region.querySelector("[data-reference-controls]");
    const search = region.querySelector("[data-reference-search]");
    const source = region.querySelector("[data-reference-source]");
    const language = region.querySelector("[data-reference-language]");
    const month = region.querySelector("[data-reference-month]");
    const count = region.querySelector("[data-reference-result-count]");
    const empty = region.querySelector("[data-reference-empty]");
    const rows = [...region.querySelectorAll("[data-reference-list] li")];
    if (!controls || !search || !source || !language || !month || !count || !empty) continue;
    function update() {
      const query = search.value.trim().toLocaleLowerCase();
      let shown = 0;
      for (const row of rows) {
        const yes = (!query || row.textContent.toLocaleLowerCase().includes(query)) &&
          (!source.value || row.dataset.source === source.value) &&
          (!language.value || row.dataset.language === language.value) &&
          (!month.value || row.dataset.published.startsWith(month.value + "-"));
        row.hidden = !yes;
        if (yes) shown++;
      }
      count.textContent = shown + " of " + rows.length + " reviewed references";
      empty.hidden = shown !== 0;
    }
    controls.hidden = false;
    for (const item of [search, source, language, month]) {
      item.addEventListener(item === search ? "input" : "change", update);
    }
    update();
  }
})();
