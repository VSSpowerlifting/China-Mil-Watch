# U.S. Desk public delivery preflight — BIS first-run prerequisite

This is a **read-only** preflight for the public U.S. Desk delivery route.
It makes no BIS source request, creates no scheduled observation, and does not
modify production SQLite, source evidence, site output or gh-pages.

## Why this exists

The repository's main generated output/us-indopacific.html and current
gh-pages/us-indopacific.html have matched exactly, each with ten USCC, ten
Treasury and nine PACOM outbound source references. A separate web index
displayed older U.S. Desk content without the first two source feeds. A
dated index or cached search result is not proof of what the server currently
delivers, so this workflow fetches actual public HTTP bytes from GitHub Actions.

## Check

A PR-scoped or manually dispatched read-only Actions run fetches the real
public U.S. Desk under a unique cache-busting query parameter, and requires
exact identity with both the current repository output and gh-pages Git file.
The delivered page must display at least ten USCC and ten Treasury official
links, exactly nine PACOM static links, and safe outbound anchor semantics.
BIS is optional and not treated as live/qualified by this check.

If public HTTP differs from Git, record an honest HOLD and investigate CDN,
DNS, Pages deployment, custom-domain mapping, or propagation. Never overwrite
the main database or unrelated desk output to silence it. A public Git match
is necessary for later BIS deployed-readback claims, not sufficient to prove
that BIS ran a genuine scheduled collector or that its source records exist.

The checker uses only public HTTP and Git. The workflow cannot write back.
