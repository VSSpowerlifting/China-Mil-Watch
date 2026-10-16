#!/usr/bin/env node
'use strict';
const fs = require('fs'), engine = require('./web/search.js');
try {
  const [path, ...args] = process.argv.slice(2);
  if (!path || args.length % 2) throw Error('Usage: node research/archive_workbench/query.cjs INDEX.json [--q TERM] [--desk DESK] [--issuer ISSUER] [--source SOURCE] [--record_type TYPE] [--from DATE] [--to DATE] [--sort relevance|newest|oldest]');
  const allowed = new Set(['q', 'desk', 'issuer', 'source', 'record_type', 'from', 'to', 'sort']), query = {};
  for (let i = 0; i < args.length; i += 2) {
    const k = args[i].replace(/^--/, '');
    if (!args[i].startsWith('--') || !allowed.has(k)) throw Error('Unknown query option.');
    query[k] = args[i + 1];
  }
  const data = JSON.parse(fs.readFileSync(path, 'utf8'));
  if (data.schema !== engine.SCHEMA) throw Error('Unknown workbench schema.');
  const start = performance.now(), hits = engine.search(engine.prepare(data.records), query);
  process.stdout.write(JSON.stringify({total: hits.length, elapsed_ms: performance.now() - start,
    results: hits.map(h => ({id: h.record.id, title: h.record.title, date: h.record.date,
      ipr_url: h.record.ipr_url, source_url: h.record.source_url, score: h.score}))}, null, 2) + '\n');
} catch (error) { process.stderr.write(error.message + '\n'); process.exitCode = 2; }
