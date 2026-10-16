#!/usr/bin/env node
/* Repeatable local query timings; no network, model or corpus mutation. */
'use strict';
const fs = require('fs'), E = require('./web/search.js');
const path = process.argv[2];
if (!path) throw Error('Usage: node research/archive_workbench/benchmark.cjs INDEX.json');
const start = performance.now(), raw = fs.readFileSync(path), data = JSON.parse(raw);
if (data.schema !== E.SCHEMA) throw Error('Unknown workbench schema');
const prepared = E.prepare(data.records), prepareMs = performance.now() - start;
const cases = [{q: 'maritime'}, {q: '"South China Sea"'}, {q: '北约'},
  {desk: 'singapore', from: '2026-09-01', to: '2026-10-15', sort: 'oldest'},
  {q: 'nonexistent-token'}];
const results = cases.map(query => {
  for (let i = 0; i < 10; i++) E.search(prepared, query);
  const samples = []; let total;
  for (let i = 0; i < 200; i++) {
    const t = performance.now(); total = E.search(prepared, query).length;
    samples.push(performance.now() - t);
  }
  samples.sort((a, b) => a - b);
  return {query, total, median_ms: +samples[100].toFixed(4), p95_ms: +samples[190].toFixed(4)};
});
console.log(JSON.stringify({runtime:process.version, records:data.records.length,
  index_bytes:raw.length, read_parse_prepare_ms:+prepareMs.toFixed(4), warmup:10,
  samples_per_query:200, results}, null, 2));
