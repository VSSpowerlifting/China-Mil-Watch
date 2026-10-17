# Archive release — 17 October 2026

Published and verified under the owner's explicit coordinated-release authorization.
Live: [Archive](https://indopacificrecord.org/archive.html?scope=published).
[Concise machine receipt](evidence/archive-release-published-2026-10-17.json).
The earlier preparation report is retained as a historical record.

- PR #776 approved head: `6d9368c2f60679f44aaa034c5bb5541976520f9b`.
- Source merge: `027f3f56ca9ccef323545124f55ac3c3fb319e01`.
- Inherited-main output commit: `db2afc8bd2b6e6b7003e37bfecf71e4ec8434be4`.
- Archive output commit: `f50524cb119b039c9d7e090a5f6bbd43a06d2917`.
- [Output-only deployment 39062144232](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39062144232), checked out exactly that output commit.
- Published Pages commit: `6e7ab454a735ba92f9e1a654c891b43c1ef155a1`; legacy Pages build succeeded on the same commit.

The merged source tree exactly equals the approved Linux-CI-tested tree.
[CI 39059700956](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39059700956)
passed 7,376 tests with no failures/errors and two explained corpus-dependent
skips; all 56 GPG-backed cases, seven Archive browser contracts and 60+60
historical source/review replays executed. No check was weakened.

## Accepted corpus and complete output

Corpus: **2026-10-17 / 912 records / 1,006 public research items**.
Logical SHA-256: `6dc8594a72c2b8fd435a95c59f5a4af4e4eda98ae474610b9ad463b0df704930`.
Complete output manifest: `8bce55968f1df8a586753c053fe200d54477a8a2808f3fc4c0a61156141e1e02`.

A fresh isolated build through the merged source's `site/render.py`, with the
explicit accepted pin, matched every accepted output byte. The actual tracked
production output was then populated exclusively from generated output and
validated with **zero errors and ten governed historical warnings**.

The 981 inherited main-render paths and four Archive paths were committed
separately. Their combined diff is 984 paths because Archive HTML overlaps the
inherited shell change. Team, all three author profiles and staff CSS are included.
There are no unexplained changes or deletions. The unchanged compact index and
new research index were published together with their bound HTML and assets in
one complete Pages commit. Raw page JS remains 9,879/10,000 bytes.

## Coordination and public readback

Existing workflow enable/disable controls provided a release window: 21 main or
Pages writers were temporarily paused, with zero running/queued writer jobs at
merge. Only the existing output-only publication workflow was enabled for the
accepted deployment. Read-only checks and shadow-branch collectors were left
alone. The optional generation guard was not assumed active. Original states
and restoration verification are retained in the local execution receipt.

- All **1,894 published Git files** match the accepted manifest. All **1,892 public
  files** returned HTTP 200 with matching SHA-256/length at normal HTTPS URLs;
  `CNAME` and `.nojekyll` are deployment controls verified in the Git payload.
- All **eight live verification contracts** passed: legacy query results/order/
  pagination, published search, canonical article navigation, citations and copy
  fallback, CSV/JSON, kept-list restoration/removal, stale-index refusal, visible
  holds, keyboard/focus behavior and no-JavaScript week browsing.
- Responsive checks cover 320/375/768/1280 px; no-JavaScript and Team/author
  navigation cover 375/1280 px. Actual desktop/mobile captures have no console
  errors, unexpected requests or horizontal overflow; custom fonts rendered.
- All three author routes and Team resolve. All 4,400 retired IDs are absent
  from both deployed record/alias namespaces; 20 representative live retired
  URLs returned not-found responses. The deployed tree has no extra files, and
  the public indexes retain the approved body/permission/private-material bounds.

The database remains byte-identical at
`21012d0e3f04426145ccf9eddae2e2dd9c820e42283230011f62163dd52e48a6`.
Canonical edition records, editorial approvals, source permissions and concurrent
desk work are preserved. PR #766 and db53 were not changed. Full manifests,
HTTP receipts, screenshots and operational journals remain local/untracked.

No release blocker remains. The ten historical validator warnings and two
corpus-dependent CI skips are unchanged; their explanations remain in the
preparation evidence. No new content admission, collector run or model call was
part of this release. Subsequent scheduled rendering uses the activated source.
