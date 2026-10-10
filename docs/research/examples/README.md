# Synthetic Dossier example — NOT evidence or a publication

The adjacent [dossier-v1-synthetic.json](dossier-v1-synthetic.json) is a **proposed data-shape illustration only**, for the [B1 RFC](../DOSSIER_B1_ENGINEERING_RFC_2026-10-09.md) and [test matrix](../DOSSIER_B1_VALIDATION_MATRIX_2026-10-09.md).

- Fictional country, institution and source labels, URLs hosted at example.org, publisher text and IDs 900001–900002. **No IPR record** is claimed for either ID.
- Draft-only. `reviewed_on: null` and `source_use_decision_ref: null` deliberately communicate that **no human editorial review or permissions decision exists**. The future validator must refuse to promote these fields without an independently documented owner decision.
- No B1 validator exists yet; this example has **not** been schema-tested. When B1 implementation begins after the #319 owner scope gate, use **synthetic SQLite fixtures** matching these IDs. Do not point this document at the real tracked `pla_watch.db`.
- Do not copy this file into `dossiers/`, public `output/`, the release pipeline, or any official IPR publication; no public link/record page/rights can be inferred from its presence.
- The example is kept separate from the *real*, unapproved MINDEF pilot in [PR #324](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/324). It is not a candidate Dossier for editorial approval.

Important contract decision still open: a declaration in an editor-authored JSON file must **never** count as independent permission to link, quote, display body text or publish a source. Keep that receipt under separate owner-controlled source-use review.
