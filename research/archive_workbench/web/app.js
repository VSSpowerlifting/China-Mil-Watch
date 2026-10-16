/* All indexed strings enter the DOM as text nodes. Search never contacts publishers. */
(async function () {
  'use strict';
  const E = window.ArchiveSearch, $ = id => document.getElementById(id);
  const keys = ['q', 'desk', 'source', 'issuer', 'record_type', 'from', 'to', 'sort'];
  const labels = {q: 'Search', desk: 'Desk', source: 'Source', issuer: 'Issuer / author',
    record_type: 'Type', from: 'From', to: 'Through', sort: 'Sort'};
  const types = {archive_record: 'Archive record · public metadata', official_link: 'Official-link reference',
    preserved_original: 'Preserved original', human_analysis: 'Human-authored analysis',
    reviewed_translation: 'Reviewed translation', reviewed_analysis: 'Reviewed analysis'};
  const controls = Object.fromEntries(keys.map(k => [k, $(k === 'q' ? 'query' : k)]));
  const node = (tag, value, className) => {
    const el = document.createElement(tag);
    if (value != null) el.textContent = value;
    if (className) el.className = className;
    return el;
  };
  function safeLink(value, ipr = false) {
    if (!value || typeof value !== 'string' || /[\s\\\u0000-\u001f]/.test(value)) return null;
    try {
      const u = new URL(value);
      if (!['http:', 'https:'].includes(u.protocol) || u.username || u.password ||
          (u.port && !['80', '443'].includes(u.port))) return null;
      return ipr && u.origin !== 'https://indopacificrecord.org' ? null : u.href;
    } catch (_) { return null; }
  }
  function link(value, title, ipr) {
    const href = safeLink(value, ipr);
    if (!href) return null;
    const a = node('a', title); a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer';
    return a;
  }
  let urlError = null;
  let records, prepared, manifest, selection = new Set(), limit = 30, query = {}, hits = [];
  const STORAGE = 'ipr-archive-research-selection-v1';
  function store() { try { sessionStorage.setItem(STORAGE, JSON.stringify([...selection].sort())); } catch (_) {} }
  const display = r => r.title || (r.record_type === 'preserved_original' ? 'Published original source text' : 'Untitled published record');
  function readUrl() {
    const p = new URLSearchParams(location.search); urlError = null;
    keys.forEach(k => {
      const v = p.get(k) || (k === 'sort' ? 'relevance' : '');
      if ((k === 'from' || k === 'to') && v && !E.validDate(v)) urlError = 'Use a valid publication date (YYYY-MM-DD).';
      if (v.length > 512) urlError = 'The shared query is too large. Clear the search and try fewer terms.';
      if (controls[k].tagName === 'SELECT' && v.length <= 512 && ![...controls[k].options].some(o => o.value === v)) {
        controls[k].appendChild(new Option(v + ' (unavailable in this snapshot)', v));
      }
      controls[k].value = v;
    });
    $('more-filters').open = ['source', 'issuer', 'from', 'to'].some(k => controls[k].value);
  }
  function state(push) {
    const p = new URLSearchParams();
    keys.forEach(k => {
      query[k] = controls[k].value.trim();
      if (query[k] && !(k === 'sort' && query[k] === 'relevance')) p.set(k, query[k]);
    });
    if (push) history.pushState(null, '', location.pathname + (p.size ? '?' + p.toString() : ''));
  }
  function highlighted(el, value) {
    const ts = E.terms(query.q || '').filter(Boolean).sort((a, b) => b.length - a.length);
    if (!ts.length) { el.textContent = value; return; }
    const re = new RegExp(ts.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'giu');
    let start = 0;
    for (const m of value.matchAll(re)) {
      el.appendChild(document.createTextNode(value.slice(start, m.index)));
      el.appendChild(node('mark', m[0])); start = m.index + m[0].length;
    }
    el.appendChild(document.createTextNode(value.slice(start)));
  }
  function selectionPanel() {
    $('selection-count').textContent = selection.size + ' selected';
    $('research-list').dataset.empty = String(selection.size === 0);
    for (const id of ['export-csv', 'export-json', 'clear-selection']) $(id).disabled = !selection.size;
    $('selected-list').replaceChildren();
    E.selected(records, [...selection]).forEach(r => {
      const li = node('li'), name = node('span', display(r));
      const remove = node('button', '×'); remove.type = 'button';
      remove.setAttribute('aria-label', 'Remove ' + display(r));
      remove.addEventListener('click', () => {
        selection.delete(r.id); store(); selectionPanel();
        document.querySelectorAll('input[data-record-id]').forEach(input => { if (input.dataset.recordId === r.id) input.checked = false; });
        $('selection-count').tabIndex = -1; $('selection-count').focus();
      });
      li.append(name, remove); $('selected-list').appendChild(li);
    });
  }
  function card(r) {
    const article = node('article', null, 'result'); article.dataset.recordId = r.id;
    const top = node('div', null, 'result-top'), titleArea = node('div', null, 'title-area');
    titleArea.appendChild(node('span', types[r.record_type], 'kind ' + r.record_type));
    const title = node('h3'); highlighted(title, display(r)); titleArea.appendChild(title);
    const select = node('label'), input = document.createElement('input');
    input.type = 'checkbox'; input.dataset.recordId = r.id; input.checked = selection.has(r.id);
    input.setAttribute('aria-label', 'Select ' + display(r));
    input.addEventListener('change', () => {
      if (input.checked) selection.add(r.id); else selection.delete(r.id);
      store(); selectionPanel();
    });
    select.append(input, document.createTextNode('Keep')); top.append(titleArea, select); article.appendChild(top);
    article.appendChild(node('p', [r.date || 'Publication date not recorded',
      r.desks.join(', ') || 'Desk not recorded'].join(' · '), 'metadata'));
    article.appendChild(node('p', [r.issuer || 'Issuer / author not recorded', r.source].filter(Boolean).join(' · '), 'metadata attribution'));
    // A short reading-list label; the complete, unchanged note remains in the
    // provenance panel and exports. This never assigns a new editorial state.
    let processing = r.record_type === 'archive_record' ? (r.processing || '').split(' · ')[0] : '';
    if (processing === 'Analyzed') processing += ' · Machine-generated English; not human-reviewed';
    if (r.record_type === 'reviewed_translation' || r.record_type === 'reviewed_analysis') processing = 'Machine-assisted · Editor-reviewed';
    if (processing) article.appendChild(node('p', processing, 'processing' +
      (r.record_type !== 'human_analysis' ? ' machine' : '')));
    // Keep a source-specific hold visible even when its provenance is closed.
    const hold = r.record_type === 'official_link' && (r.processing || '').split('verification. ')[1];
    if (hold) article.appendChild(node('p', hold, 'hold'));
    const originalMatch = r.original_title && E.normalize(r.original_title) !== E.normalize(r.title) &&
      E.terms(query.q || '').some(t => E.normalize(r.original_title).includes(t) && !E.normalize(r.title).includes(t));
    const snippet = E.snippet(r, query.q);
    if (snippet && (r.summary || r.text || originalMatch)) { const p = node('p', null, 'snippet'); highlighted(p, snippet); article.appendChild(p); }
    const links = node('div', null, 'links');
    const ipr = link(r.ipr_url, 'Open IPR record', true), source = link(r.source_url, 'Open official source', false);
    if (ipr) links.appendChild(ipr); if (source) links.appendChild(source); article.appendChild(links);
    const details = node('details'), summary = node('summary', 'Citation & provenance'); details.appendChild(summary);
    const provenance = node('div', null, 'provenance-notes');
    if (r.date_kind) provenance.appendChild(node('p', r.date_kind));
    if (r.processing) provenance.appendChild(node('p', r.processing));
    if (r.original_title && r.original_title !== r.title) provenance.appendChild(node('p', 'Original title: ' + r.original_title));
    details.appendChild(provenance);
    details.appendChild(node('p', r.citation, 'citation'));
    const copy = node('button', 'Copy citation', 'copy'); copy.type = 'button';
    const feedback = node('p'); feedback.setAttribute('role', 'status'); feedback.setAttribute('aria-live', 'polite');
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(r.citation); feedback.textContent = 'Citation copied.'; }
      catch (_) {
        const range = document.createRange(); range.selectNodeContents(details.querySelector('.citation'));
        window.getSelection().removeAllRanges(); window.getSelection().addRange(range);
        feedback.textContent = 'Copy was unavailable. Citation selected; use your device’s copy command.';
      }
    });
    details.append(copy, feedback, node('p', 'Record identity: ' + r.id + '. Export does not grant reuse rights.', 'record-identity'));
    article.appendChild(details); return article;
  }
  function renderResults() {
    $('results').replaceChildren(...hits.slice(0, limit).map(h => card(h.record)));
    $('more').hidden = hits.length <= limit;
    $('more').textContent = 'Show more results (' + Math.min(limit, hits.length) + ' of ' + hits.length + ' shown)';
  }
  function update(push = false) {
    limit = 30; state(push); $('error').hidden = true;
    $('active').replaceChildren();
    const extraFilters = ['source', 'issuer', 'from', 'to'].filter(k => query[k]).length;
    $('more-filter-count').textContent = extraFilters ? ' (' + extraFilters + ')' : '';
    keys.filter(k => k !== 'sort' && query[k]).forEach(k => {
      const label = controls[k].tagName === 'SELECT' ? controls[k].selectedOptions[0].textContent : query[k];
      const chip = node('button', labels[k] + ': ' + label + ' ×'); chip.type = 'button';
      chip.setAttribute('aria-label', 'Remove ' + labels[k] + ' filter');
      chip.addEventListener('click', () => { controls[k].value = ''; update(true);
        if (controls[k].closest('#more-filters') && !$('more-filters').open) $('more-filters').querySelector('summary').focus();
        else controls[k].focus(); });
      $('active').appendChild(chip);
    });
    try {
      if (urlError) throw Error(urlError);
      if (location.search.length > 8192) throw Error('The shared query is too large. Clear the search and try fewer terms.');
      hits = E.search(prepared, query);
      const desks = new Set(hits.flatMap(h => h.record.desks)).size;
      const issuers = new Set(hits.map(h => h.record.issuer).filter(Boolean)).size;
      $('count').textContent = hits.length.toLocaleString('en-US') + (hits.length === 1 ? ' result' : ' results');
      $('coverage').textContent = records.length.toLocaleString('en-US') + ' published items indexed. ' +
        desks + (desks === 1 ? ' desk and ' : ' desks and ') + issuers + (issuers === 1 ? ' issuer / author' : ' issuers / authors') + ' in this result set.';
      $('empty').hidden = hits.length !== 0; renderResults();
    } catch (err) {
      hits = []; $('count').textContent = 'Search needs attention'; $('results').replaceChildren();
      $('error').hidden = false; $('error').textContent = err.message; $('empty').hidden = true; $('more').hidden = true;
    }
  }
  function exportList(format) {
    const content = format === 'csv' ? E.csv(records, [...selection]) : JSON.stringify({schema: E.SCHEMA,
      corpus_sha256: manifest.records_sha256, records: E.selected(records, [...selection])}, null, 2) + '\n';
    const blob = new Blob([content], {type: format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8'});
    const url = URL.createObjectURL(blob), a = node('a');
    a.href = url; a.download = 'ipr-research-list.' + format; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    $('feedback').textContent = selection.size + ' selected records exported as ' + format.toUpperCase() + '.';
  }
  try {
    const fetchJSON = async path => {
      const response = await fetch(path, {credentials: 'omit', cache: 'no-store'});
      if (!response.ok) throw Error('The local index could not be loaded. Rebuild this preview and reload.');
      const body = await response.text();
      if (body.length > 16000000) throw Error('The local index exceeds this preview’s size limit.');
      return JSON.parse(body);
    };
    const [data, meta] = await Promise.all([fetchJSON('index.json'), fetchJSON('manifest.json')]);
    manifest = meta;
    if (data.schema !== E.SCHEMA || !Array.isArray(data.records) || data.records.length > 30000 ||
        meta.schema !== E.SCHEMA || meta.included !== data.records.length) throw Error('Index schema or count mismatch. Rebuild the preview.');
    records = data.records.map(r => {
      if (!r || E.FIELDS.some(k => !(k in r)) || !Array.isArray(r.desks) || !types[r.record_type] ||
          typeof r.id !== 'string' || (r.date && !E.validDate(r.date)) ||
          (r.record_type === 'official_link' && (r.text || r.summary))) throw Error('Invalid public index record. Rebuild the preview.');
      return Object.fromEntries(E.FIELDS.map(k => [k, r[k]]));
    });
    if (new Set(records.map(r => r.id)).size !== records.length) throw Error('Duplicate public identities. Rebuild the preview.');
    prepared = E.prepare(records);
    for (const key of ['desk', 'source', 'issuer', 'record_type']) {
      const values = [...new Set(records.flatMap(r => key === 'desk' ? r.desks : [r[key]]).filter(Boolean))].sort();
      values.forEach(v => controls[key].appendChild(new Option(key === 'record_type' ? types[v] : v, v)));
    }
    const known = new Set(records.map(r => r.id));
    try {
      const ids = JSON.parse(sessionStorage.getItem(STORAGE) || '[]');
      if (Array.isArray(ids)) selection = new Set(ids.filter(id => known.has(id)));
    } catch (_) {}
    store(); selectionPanel();
    $('snapshot').textContent = 'Archive snapshot ' + meta.public_snapshot.date + '. Source revision ' + meta.source_revision +
      '. ' + meta.retirement_ledger_entries + ' retirement tombstones enforced. Corpus digest ' + meta.records_sha256 + '.';
    readUrl(); update();
    $('controls').addEventListener('submit', e => { e.preventDefault(); urlError = null; update(true); });
    keys.filter(k => k !== 'q').forEach(k => controls[k].addEventListener('change', () => update(true)));
    $('reset').addEventListener('click', () => {
      urlError = null; keys.forEach(k => { controls[k].value = k === 'sort' ? 'relevance' : ''; });
      $('more-filters').open = false; update(true); $('query').focus();
    });
    $('more').addEventListener('click', () => {
      const firstNew = limit; limit += 30; renderResults();
      const card = $('results').children[firstNew];
      if (card) { card.tabIndex = -1; card.focus(); }
    });
    $('clear-selection').addEventListener('click', () => {
      selection.clear(); store(); selectionPanel();
      document.querySelectorAll('input[data-record-id]').forEach(input => { input.checked = false; });
      $('selection-count').tabIndex = -1; $('selection-count').focus();
    });
    $('export-csv').addEventListener('click', () => exportList('csv'));
    $('export-json').addEventListener('click', () => exportList('json'));
    window.addEventListener('popstate', () => { readUrl(); update(); });
  } catch (_) {
    $('error').hidden = false;
    $('error').textContent = 'The private index could not be validated. Rebuild this preview and reload.';
    $('count').textContent = 'Index unavailable';
  }
})();
