"""
Deterministic editorial lint for daily summaries and readout text.

Stdlib-only, no API calls. Used by tests/test_editorial_regression.py as an
offline regression harness over archived outputs, and available for future
log-only pipeline checks. A lint finding is an editorial-quality signal, not
automatically an error: archived text predating a prompt change is evidence
of the old prompt's behavior and is reported, not "fixed."
"""

import re

# Openers the style guide bans for summaries (generic meta-language).
BANNED_OPENERS = (
    "the article discusses",
    "the article reports",
    "the report highlights",
    "the piece discusses",
    "this article",
    "this development underscores",
    "in today's",
)

# Corpus-flattening filler and inflation the prompt now bans.
BANNED_PHRASES = (
    "underscores the importance",
    "in today's complex geopolitical landscape",
    "it is important to note",
    "game-changing",
    "unprecedented",
    "historic milestone",
    "comprehensive capabilities",
)

# Second-sentence crutch verbs the prompt tells the model not to default to.
CRUTCH_OPENERS = ("this signals", "it signals", "this reflects continued")

MAX_SENTENCES = 3
MAX_WORDS = 100          # prompt asks ≤ ~90; allow slack before flagging
CARD_EXCERPT_CHARS = 300  # homepage card truncation (site/generator.py)


def _sentences(text: str) -> list:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p for p in parts if p]


def lint_summary(title: str, summary: str) -> list:
    """Return a list of editorial findings (empty = clean)."""
    findings = []
    s = " ".join((summary or "").split())
    if not s:
        return ["empty summary"]
    low = s.lower()

    for opener in BANNED_OPENERS:
        if low.startswith(opener):
            findings.append(f"banned opener: {opener!r}")
            break
    for phrase in BANNED_PHRASES:
        if phrase in low:
            findings.append(f"banned phrase: {phrase!r}")
    for crutch in CRUTCH_OPENERS:
        if crutch in low:
            findings.append(f"crutch construction: {crutch!r}")

    sentences = _sentences(s)
    if len(sentences) > MAX_SENTENCES:
        findings.append(f"{len(sentences)} sentences (max {MAX_SENTENCES})")
    words = len(s.split())
    if words > MAX_WORDS:
        findings.append(f"{words} words (target ≤ ~90)")

    # Headline repetition: summary opening reproduces the headline nearly
    # verbatim (normalized prefix match on the first 8+ words).
    t = re.sub(r"[^a-z0-9 ]", "", (title or "").lower()).split()
    s_words = re.sub(r"[^a-z0-9 ]", "", low).split()
    if len(t) >= 8 and s_words[: len(t)] == t:
        findings.append("summary opens by restating the headline")

    # First sentence must stand alone on cards: it should not be cut
    # mid-thought at the card excerpt boundary.
    if sentences and len(sentences[0]) > CARD_EXCERPT_CHARS:
        findings.append(
            f"first sentence {len(sentences[0])} chars — exceeds the "
            f"{CARD_EXCERPT_CHARS}-char card excerpt"
        )

    return findings
