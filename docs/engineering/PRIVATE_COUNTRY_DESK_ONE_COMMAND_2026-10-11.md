# One-command private Philippines and Vietnam desks

**October 11, 2026 — functional private analyst interface, not production activation.**

PR #384 provides a working private source reader based on pinned original shadow SQLite stores. The following wrapper eliminates the manual work of fetching/pinning five independent Git shadow branches and creates a usable local browser view **with one explicitly approved command**. This is not an automated collector, public site rollout, source-rights decision or new source capture.

### One-command launch

From a trusted, current IPR source-code checkout with Python 3.9 and Git installed, choose a **new private HTML output path** outside your repository.

**Philippines (AFP + NSC):**

```bash
python -m scripts.launch_private_country_desks \
  --desk philippines --approve-github-shadow-fetch \
  --format html --output "$HOME/Downloads/ipr-philippines-private.html"
```

**Vietnam (MPS + two MOIT):**

```bash
python -m scripts.launch_private_country_desks \
  --desk vietnam --approve-github-shadow-fetch \
  --format html --output "$HOME/Downloads/ipr-vietnam-private.html"
```

**Both countries and a private full-text query (metadata results only):**

```bash
python -m scripts.launch_private_country_desks \
  --desk both --approve-github-shadow-fetch \
  --query maritime --limit 200 --format html \
  --output "$HOME/Downloads/ipr-regional-research-private.html"
```

Open the resulting file locally in your browser. It has a title/source filter, country filter, exact publisher links, original title/date, stored source identity and immutable state revision, and a prominent public-review-pending warning. You can also request `--format json` (printed to stdout, redirect only to a private path). **Full-text search happens only during the command's local private run**; the subsequent HTML input searches the *metadata shown in that file*, not undisclosed body text.

### What the command actually fetches

The code uses only the fixed existing GitHub repository `https://github.com/VSSpowerlifting/China-Mil-Watch.git`. With the owner's explicit `--approve-github-shadow-fetch` flag, it fetches the required already-existing orphan source-state Git branches into a temporary local Git directory. The program resolves each exact SHA and calls the #384 reader on those immutable Git objects:

- Philippines AFP `shadow/ph-afp` and NSC `shadow/ph-nsc`;
- Vietnam MPS `shadow/vietnam-mps-foreign-affairs`, MOIT Energy `shadow/vietnam-moit-energy` and MOIT Foundational `shadow/vietnam-moit-foundational-industry`.

An absent, inaccessible, corrupt or misattributed source stops the command. It does not silently drop the family and pretend complete desk coverage. Git downloads of the existing shadow branches are **not live requests to any publisher**. The downloaded source DB objects and internal preserved original bodies stay in a disposable temporary directory and are deleted after the reader finishes. The rendered HTML or JSON contains no copied original document body, paragraph, image, PDF, attachment or API capture; it contains only already-collected metadata and official first-party source URLs.

The command has **no implicit network use** unless the explicit flag is supplied; it has no GitHub Actions schedule, upload-artifact, source collector, AI call, production SQLite write, public site emission, email or deployment.

### Verified current baseline and limitations

As of the verified October 11 source-state heads, AFP holds 18 stored records; NSC holds **zero** (a running source cannot guarantee publications); Vietnam MPS holds 6; MOIT energy 2; MOIT foundational 1. **27 stored records** across both country scopes. These are shadow research records, not 27 approved public archive records. No model summaries or rights determinations are inferred from their presence. Both MOIT families have ongoing robots MIME warnings under review.

This interface makes **two country-specific research workflows usable today**. It does not assert that both desks meet IPR's strict `functional` production standard: not every institution/source has passed independent original-language checks, reuse-rights determinations, 30-day continuous observation or public qualification. It does not cover the Philippine Department of National Defense, Vietnamese MOD, Japanese MOD or the broader country institution lists.

The next truly public step needs source-specific admission evidence—AFP seven scheduled days starting Oct 7, then 30 days and Day 7/14/30 human review where the current IPR standard requires it; Vietnam Oct 14/21/Nov 6 ministry reviews; human fidelity, signed rights and owner source/desk admission, production rendering and safe rollback. Do not bypass those gates by adding a record count to the website registry.

### Offline proof

```bash
python -m unittest tests.test_private_country_desk_reader -v
python -m unittest tests.test_launch_private_country_desks -v
```

Tests build **real local synthetic Git repositories and five SQLite snapshots**, fetch each mock branch through the same Git command, construct a private HTML view, assert that no body text leaks, that both desks and all five families appear, that missing branches fail closed and that the CLI does not fetch anything without explicit approval. No outside networks are contacted in CI.

**No new publisher collection, rights grant, desk status change or release authorization occurs merely by integrating this helper.**
