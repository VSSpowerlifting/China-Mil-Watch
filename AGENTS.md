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

