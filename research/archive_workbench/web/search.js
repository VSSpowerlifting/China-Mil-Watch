/* One deterministic query/export implementation, shared by browser and Node CLI. */
(function (root) {
  'use strict';
  const SCHEMA = 'ipr-archive-workbench/1';
  const FIELDS = ['id', 'title', 'original_title', 'summary', 'text', 'date', 'date_kind', 'desks',
    'source', 'issuer', 'record_type', 'processing', 'ipr_url', 'source_url', 'citation'];
  const normalize = s => String(s || '').normalize('NFKC').toLowerCase();
  const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  function validDate(s) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
    const d = new Date(s + 'T00:00:00Z');
    return Number.isFinite(+d) && d.toISOString().slice(0, 10) === s;
  }
  function terms(q) {
    if (typeof q !== 'string' || q.length > 512) throw Error('Use a query of at most 512 characters.');
    if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(q)) throw Error('Remove control characters from the query.');
    const out = []; let current = '', quoted = false;
    for (const c of q.normalize('NFKC')) {
      if (c === '"') {
        if (current.trim()) out.push(normalize(current.trim()));
        current = ''; quoted = !quoted;
      } else if (/\s/u.test(c) && !quoted) {
        if (current) out.push(normalize(current));
        current = '';
      } else current += c;
    }
    if (quoted) throw Error('Close the quoted phrase with a double quote.');
    if (current.trim()) out.push(normalize(current.trim()));
    const unique = [...new Set(out)];
    if (unique.length > 32) throw Error('Use at most 32 search terms.');
    return unique;
  }
  function prepare(records) {
    return records.map(record => ({record, fields: [record.title, record.original_title,
      record.summary, record.text, [record.source, record.issuer, ...record.desks, record.record_type,
        record.processing].join(' ')].map(normalize)}));
  }
  function search(prepared, query = {}) {
    const ts = terms(query.q || '');
    for (const k of ['from', 'to']) if (query[k] && !validDate(query[k])) throw Error('Use a valid publication date (YYYY-MM-DD).');
    if (query.from && query.to && query.from > query.to) throw Error('The start date must be on or before the end date.');
    if (query.sort && !['relevance', 'newest', 'oldest'].includes(query.sort)) throw Error('Unknown sort order.');
    let result = [];
    for (const {record: r, fields} of prepared) {
      if (query.desk && !r.desks.includes(query.desk)) continue;
      if (['source', 'issuer', 'record_type'].some(k => query[k] && query[k] !== r[k])) continue;
      if ((query.from || query.to) && !r.date) continue;
      if ((query.from && r.date < query.from) || (query.to && r.date > query.to)) continue;
      let score = 0, found = true;
      for (const t of ts) {
        const weights = [12, 10, 4, 3, 2]; let best = 0;
        fields.forEach((f, i) => { if (f.includes(t)) best = Math.max(best, weights[i] + (f === t ? 5 : 0)); });
        if (!best) { found = false; break; }
        score += best;
      }
      if (found) result.push({record: r, score});
    }
    result.sort((a, b) => {
      if ((!query.sort || query.sort === 'relevance') && b.score !== a.score) return b.score - a.score;
      const ad = a.record.date, bd = b.record.date;
      if (!ad !== !bd) return ad ? -1 : 1; // Missing dates last in either direction.
      const dateOrder = compare(ad || '', bd || '');
      return (query.sort === 'oldest' ? dateOrder : -dateOrder) || compare(a.record.id, b.record.id);
    });
    return result;
  }
  function snippet(record, q) {
    const ts = terms(q || ''), fields = [record.summary, record.text, record.original_title, record.title];
    const value = fields.find(s => s && ts.some(t => normalize(s).includes(t))) || fields.find(Boolean) || '';
    const matching = ts.find(t => normalize(value).includes(t));
    const offset = matching ? value.toLowerCase().indexOf(matching) : 0;
    const pos = offset > 0 ? Array.from(value.slice(0, offset)).length : 0;
    const start = Math.max(0, pos - 65);
    return (start ? '…' : '') + Array.from(value).slice(start, start + 240).join('') + (Array.from(value).length > start + 240 ? '…' : '');
  }
  function selected(records, ids) {
    const wanted = new Set(ids);
    return records.filter(r => wanted.has(r.id)).sort((a, b) => compare(a.id, b.id))
      .map(r => Object.fromEntries(FIELDS.map(k => [k, r[k] == null ? null : r[k]])));
  }
  function csv(records, ids) {
    const cell = value => {
      let s = Array.isArray(value) ? value.join('; ') : String(value == null ? '' : value);
      if (/^[\s\u0000-\u001f\u200b-\u200f\ufeff]*[=+\-@]/u.test(s)) s = "'" + s;
      return '"' + s.replace(/"/g, '""') + '"';
    };
    return '\ufeff' + [FIELDS, ...selected(records, ids).map(r => FIELDS.map(k => r[k]))]
      .map(row => row.map(cell).join(',')).join('\r\n') + '\r\n';
  }
  const api = {SCHEMA, FIELDS, normalize, terms, validDate, prepare, search, snippet, selected, csv};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ArchiveSearch = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
