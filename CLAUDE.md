# Claude Operating Rules

Be token-efficient by default.

Do not paste entire files unless explicitly asked. Use concise diffs, filenames, and summaries.

Before editing, inspect only the relevant files. Avoid broad repo scans unless necessary.

When making changes, make the smallest safe change.

After editing, report only:
- files changed
- what changed
- how to test/check it

Do not provide long explanations, large plans, or repeated project summaries unless asked.

For writing tasks, do not rewrite the whole piece unless asked. Diagnose briefly, then revise only the necessary section.

For coding tasks, avoid printing long command outputs. Summarize the result and include only important errors.

For this project, do not commit, push, deploy, publish, or regenerate anything unless I explicitly ask.

## Token-efficient navigation (Graphify)

- Start each session by reading `PROJECT_STATE.md` if it exists.
- For architecture, file locations, data flow, generation flow, or "where should
  I edit?" questions, read `graphify-out/GRAPH_REPORT.md` before broad search.
- Order of operations: Graphify report first, targeted `rg` second, direct file
  reads third.
- Do not re-audit the whole repo unless explicitly asked.
- Do not open large files unless Graphify or targeted search identifies them as
  relevant.
- Summarize large outputs instead of pasting them back.
- Use Ruflo only when role separation genuinely helps (research, source
  verification, methodology review, editorial skepticism, publishing QA,
  longitudinal comparison, claim-to-source traceability). Not for simple coding
  edits, one-file fixes, nav changes, README edits, formatting, or routine build
  errors.
- Use Headroom only for long logs, repetitive JSON, large search/validation
  output, or Ruflo multi-agent context. Never treat Headroom summaries as
  authoritative for Chinese text, translations, dates, ranks, or claims.
- After major architecture or file-structure changes, run `graphify update .` to
  refresh the graph (no API cost with `--code-only`).
- After meaningful work, update `PROJECT_STATE.md`.
- Prefer small, focused changes over large rewrites.
- Do not push, merge, publish, deploy, or sync without explicit permission.

