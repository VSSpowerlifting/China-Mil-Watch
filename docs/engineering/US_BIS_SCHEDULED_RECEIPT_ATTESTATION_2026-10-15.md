# BIS scheduled-source receipt — independent attestation, not promotion

Separate from BIS collector #693 and typed scratch staging #702.

The collector's own green check is insufficient evidence for later live SQLite admission. This reviewer accepts a READ-ONLY clone of shadow/us-bis-homepage, the actual JSON returned by the **authenticated GitHub Actions REST API** for a specific completed run, and the exact remote branch head SHA independently obtained from GitHub. It holds unless ALL agree:

- real schedule event, successful completed run, correct GitHub repo, default-branch workflow identity, exact run ID/attempt and event timestamps;
- exactly one source-branch Git commit bearing that run/attempt marker;
- commit adds only the one observations/YYYY-MM-DD.json receipt (plus README on first orphan commit) and no prior receipt is changed;
- per-day receipt fields, official first-party URLs, issuer, dates and ordered identities pass BIS packet verification; homepage digest equals the receipt commit trailer; remote branch head stays unchanged before/after review.

The separate workflow_run callback reads GitHub's authenticated Actions JSON and source Git only after an actual successful scheduled collector event. PR checks use **synthetic local fixtures** and cannot create a genuine source day. It writes **no source Git commits, production SQLite, Pages files or evidence branch**. A failed attestation ends in HOLD.

This proves recorded metadata and event/commit consistency, not a cryptographic copy of the publisher's exact HTML (which the collector deliberately does not retain). It does not qualify a clean-day streak, grant reuse rights, validate Indo-Pacific subject relevance, or authorize public source materials, translations or IPR analysis. A later live-release phase must independently match the source digest to the original source collection job logs and owner decision; no publication is permitted from the attestor alone.

The first real scheduled run is expected no earlier than the next scheduled 12:35 UTC slot after collector #693 merged. Failure to receive a scheduled event is not a missing source record, and manual dispatch/PR checks never count.
