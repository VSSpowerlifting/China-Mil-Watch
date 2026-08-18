"""
Chinese-title-based deduplication for PLA Daily syndicated reposts.

PLA Daily (81.cn) reposts the same article across multiple service-branch
sub-paths. The URL differs, the body text often has small variations
(headers, footers, paragraph ordering), but the Chinese title is reused
verbatim. The existing URL + content-hash dedup misses these because both
signals diverge across reposts.

Design choice: title hash is the sole grouping key. Body-prefix matching
was considered as a confirmation step but rejected — body content is not
stable across reposts (the very problem this module exists to solve), so
a prefix hash will sometimes split a true duplicate group and keep both
copies. PLA Daily reuses titles deliberately; that makes the title the
only reliable signal. The body_prefix_hash() helper is kept in the module
because it's cheap and may be useful elsewhere, but dedup_articles() does
not call it.

Canonical selection is a five-part TOTAL ordering — governed source authority,
then source identity, then 81.cn section priority, then URL length, then the
URL itself. See canonical_sort_key(). Only the first part is an editorial
judgement; the rest exist so that a tie resolves identically in every input
order. Before 2026-08-17 only section priority existed, applied to every URL
regardless of host, which silently demoted the Tier A ministry below a Tier B
newspaper; the first fix added authority but left a three-part key that still
tied at the top on 16 of 17 production groups.
"""

import hashlib
import re
from typing import Optional
from urllib.parse import urlparse


# ── Cross-source authority → canonical priority ──────────────────────────────
#
# The FIRST and dominant key in canonical selection. When the same release is
# published by two different sources, the more authoritative institution wins,
# regardless of URL shape.
#
# Why this exists: until 2026-08-17 canonical choice was decided solely by the
# first path segment of the URL (see _SOURCE_PRIORITY below), a map built for
# 81.cn's internal sections. A MOD China URL (/gfbw/…) parsed as section
# "gfbw", missed the map, and scored 70 — below PLA Daily's 要闻 at 100. So the
# Ministry of National Defense, the Tier A source of record, lost every
# head-to-head to a Tier B service newspaper reprinting the same spokesperson
# text. MOD China contributed zero stored rows between 2026-07-10 and
# 2026-08-17 while publishing on cadence throughout.
#
# Tiers mirror `authority_tier` in desks/china/manifest.json. They are a
# constant here rather than a manifest read on purpose: dedup_articles() is a
# pure, low-level function on a list of dicts, called once per run inside the
# pipeline's hot path, and giving it manifest or database I/O would invert the
# layering — a batch-transform function would then depend on desk
# configuration loading. The drift risk this creates is covered by
# test_dedup_authority.py::test_tier_table_matches_manifest, which fails if
# this table and the manifest ever disagree.
_AUTHORITY_TIER_RANK: dict[str, int] = {
    "A": 400,   # authorized institutional position (ministry, CMC)
    "B": 300,   # service media / official mirror
    "C": 200,   # state news agency syndication
    "D": 100,   # state-linked commercial press
}

_SOURCE_AUTHORITY_TIER: dict[str, str] = {
    "mod_china":        "A",
    "pla_daily":        "B",
    "china_mil_online": "B",
    "xinhua_mil":       "C",
    "global_times_mil": "D",
}

# Fallback only: used when an article dict carries no `source_slug` (the spec
# naming variant this function also accepts). Never a substitute for the slug.
#
# Hosts are the ones sources actually serve, which are not always the manifest's
# `base_url`: China Military Online is declared as english.chinamil.com.cn but
# every one of its 331 stored articles is on eng.chinamil.com.cn. Both are
# mapped. This mismatch is exactly why the destructive cleanup joins
# articles→sources for the slug instead of inferring it from the URL.
_HOST_AUTHORITY_SLUG: dict[str, str] = {
    "www.mod.gov.cn":             "mod_china",
    "mod.gov.cn":                 "mod_china",
    "www.81.cn":                  "pla_daily",
    "81.cn":                      "pla_daily",
    "eng.chinamil.com.cn":        "china_mil_online",
    "english.chinamil.com.cn":    "china_mil_online",
    "www.chinamil.com.cn":        "china_mil_online",
    "www.xinhuanet.com":          "xinhua_mil",
    "xinhuanet.com":              "xinhua_mil",
    "www.globaltimes.cn":         "global_times_mil",
    "globaltimes.cn":             "global_times_mil",
}

# Sources absent from the table rank below every governed tier, so an
# unrecognised source can never displace a governed one as canonical.
_UNKNOWN_AUTHORITY = 0


# ── 81.cn section → canonical priority ───────────────────────────────────────
#
# The THIRD key. It is reached only when authority tier AND source identity are
# both equal, so by the shape of canonical_sort_key() it can only ever separate
# candidates from the same source — a structural guarantee, not a convention.
# Built from scraper/sources/pla_daily.py _SECTIONS. Higher = more canonical.
# When the same article appears in both 要闻 (main news) and a service-branch
# section, prefer the main-news copy.
_SOURCE_PRIORITY: dict[str, int] = {
    # Main news — most canonical
    "yw_208727":  100,  # 要闻 (Top News)

    # Service branches
    "bz_208549":   90,  # 备战 (Combat Readiness / Army-adjacent)
    "hj_208557":   90,  # 海军 (Navy)
    "kj_208559":   90,  # 空军 (Air Force)
    "hjj_208561":  90,  # 火箭军 (Rocket Force)

    # Paramilitary
    "wj_208567":   85,  # 武警 (PAP)

    # Higher-level command and policy sections
    "jw_208551":   80,  # 军委 (CMC)
    "zq_208553":   80,  # 战区 (Theater Commands)

    # Other known sections from the scraper
    "fyr":         50,  # 发言人 (Spokesperson)
}

_DEFAULT_PRIORITY = 50


# ── Title normalization ─────────────────────────────────────────────────────

# Leading bracket tags like 【双语】, 【独家】, [Bilingual], [Exclusive], etc.
# Matches both CJK 【】 and ASCII [] brackets at the start of the string.
_LEADING_TAG_RE = re.compile(r"^\s*(?:【[^】]*】|\[[^\]]*\])\s*")


def _normalize_title(title: str) -> str:
    """
    Strip whitespace and leading bracket tags like 【双语】 or [Bilingual].
    Preserves all CJK characters and Chinese punctuation.
    """
    if not title:
        return ""
    t = title.strip()
    # Strip repeated leading tags, e.g. "【双语】【独家】标题"
    while True:
        stripped = _LEADING_TAG_RE.sub("", t)
        if stripped == t:
            break
        t = stripped
    return t.strip()


def title_hash(title: str) -> str:
    """SHA-1 of the normalized title. Empty string if title is empty."""
    norm = _normalize_title(title or "")
    if not norm:
        return ""
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def body_prefix_hash(body: str, n: int = 200) -> str:
    """
    SHA-1 of the first n non-whitespace characters of the body.

    Not used by dedup_articles() (see module docstring). Retained as a
    cheap utility for callers that need a body fingerprint.
    """
    if not body:
        return ""
    compact = re.sub(r"\s+", "", body)
    if not compact:
        return ""
    return hashlib.sha1(compact[:n].encode("utf-8")).hexdigest()


# ── URL → section / priority ────────────────────────────────────────────────

_SECTION_RE = re.compile(r"^/([^/]+)/")

# Hosts whose first path segment is an 81.cn *section*. Any other host's first
# path segment means nothing in this vocabulary and must not be scored as if it
# did — that conflation is what let /gfbw/… be read as an unmapped 81.cn
# section worth 70.
_PLA_DAILY_HOSTS = frozenset({"www.81.cn", "81.cn"})


def url_host(url: str) -> str:
    """Lowercased hostname, or empty string if it cannot be parsed."""
    if not url:
        return ""
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def url_section(url: str) -> str:
    """
    Extract the section identifier from an 81.cn URL.
    e.g. "yw_208727" from "http://www.81.cn/yw_208727/16459467.html".

    Returns empty string when the URL is not an 81.cn URL at all: a first path
    segment on some other host is not an 81.cn section and must not be treated
    as one.
    """
    if not url:
        return ""
    if url_host(url) not in _PLA_DAILY_HOSTS:
        return ""
    try:
        path = urlparse(url).path
    except Exception:
        return ""
    m = _SECTION_RE.match(path)
    return m.group(1) if m else ""


def source_priority(url: str) -> int:
    """
    Intra-81.cn section priority — higher means more canonical.

    Scope: this ranks 81.cn sections against each other. It is deliberately
    NOT a cross-source authority signal; see authority_priority(). Mapped
    sections use _SOURCE_PRIORITY; an 81.cn section we have not mapped yet
    falls through to 70; anything that is not an 81.cn URL gets 50, meaning
    "no 81.cn section applies" rather than "unknown 81.cn section".
    """
    section = url_section(url)
    if section in _SOURCE_PRIORITY:
        return _SOURCE_PRIORITY[section]
    if section:
        # Section parsed but not in our map — likely a real 81.cn section we
        # haven't seen yet. Worth more than total-unknown but less than mapped.
        return 70
    return _DEFAULT_PRIORITY


# ── Cross-source authority ───────────────────────────────────────────────────

def authority_slug(article: dict) -> str:
    """
    The article's source identity. Prefers the explicit `source_slug` the
    scrapers set; falls back to the URL host only when the dict does not carry
    one (the `title_zh`/`body_zh` spec-naming variant).
    """
    slug = (_field(article, "source_slug") or "").strip()
    if slug:
        return slug
    return _HOST_AUTHORITY_SLUG.get(url_host(_field(article, "url") or ""), "")


def authority_priority(article: dict) -> int:
    """
    Governed authority rank for cross-source canonical choice — higher wins.

    Derived from the source's `authority_tier` in the desk manifest, keyed by
    source identity, never by URL path shape. An unrecognised source ranks
    below every governed tier.
    """
    tier = _SOURCE_AUTHORITY_TIER.get(authority_slug(article))
    if tier is None:
        return _UNKNOWN_AUTHORITY
    return _AUTHORITY_TIER_RANK.get(tier, _UNKNOWN_AUTHORITY)


# ── The canonical winner key ─────────────────────────────────────────────────
#
# ONE definition, used by every consumer that has to pick a survivor from a
# duplicate group — the pipeline's dedup_articles() and the destructive
# scripts/cleanup_duplicates.py. They previously ranked by different rules:
# the pipeline gained authority-first ordering while cleanup still sorted by
# source_priority(url) alone, so cleanup would have scored a MOD China URL at
# 50 against PLA Daily's 要闻 at 100 and deleted the Tier A ministry copy the
# pipeline had just chosen to keep. A destructive tool must not disagree with
# the tool that decided what to store.


def canonical_sort_key(article) -> tuple:
    """
    The complete ordering key for canonical selection. Higher tuple wins.

    Accepts anything supporting ``[]``/``.get`` for "url" and "source_slug" —
    both a pipeline article dict and a ``sqlite3.Row`` from the cleanup query.

        1. governed authority tier of the source
        2. source identity (slug), lexical
        3. 81.cn section priority
        4. shorter URL
        5. the URL itself, lexical

    **This ordering is total.** The earlier three-part key
    ``(authority, section, -len(url))`` tied at the top on 16 of the 17
    duplicate groups in production, which meant the winner was decided by input
    order: reverse the batch and a different row survived — from a function that
    both stores documents and deletes rows. Components 2 and 5 remove that.

    **Only component 1 is an editorial judgement.** Components 2 and 5 are
    lexical comparisons of a slug and a URL. They are determinism devices, not
    claims that `pla_daily` is a better source than `china_mil_online`, or that
    one URL is more canonical than another. They exist so that a tie resolves
    the same way on every machine, in every input order, forever. Where a real
    ranking between equal-tier sources is wanted, it belongs in the manifest as
    an authority distinction, not in this tie-break.

    **Section priority cannot cross a source boundary.** Component 3 is only
    reached when components 1 AND 2 are equal, and component 2 is the source
    identity — so two candidates from different sources are always separated
    before section priority is consulted. That is a structural guarantee of the
    key's shape, not a convention.
    """
    url = _field(article, "url") or ""
    return (
        authority_priority(article),   # 1 governed tier — the editorial judgement
        authority_slug(article),       # 2 identity — deterministic, not editorial
        source_priority(url),          # 3 81.cn section — same-identity candidates only
        -len(url),                     # 4 shorter URL
        url,                           # 5 total order — deterministic, not editorial
    )


def select_canonical(group):
    """The winning member of a duplicate group, by canonical_sort_key."""
    return max(group, key=canonical_sort_key)


def rank_canonical(group) -> list:
    """The group ordered winner-first. Same key, descending."""
    return sorted(group, key=canonical_sort_key, reverse=True)


def is_governed(article) -> bool:
    """True when the article's source identity resolves to a governed tier."""
    return authority_slug(article) in _SOURCE_AUTHORITY_TIER


def unresolved_authority(group) -> Optional[str]:
    """
    Fail-closed guard for DESTRUCTIVE callers.

    Returns None when a group is safe to rank for deletion, or a human-readable
    reason when it is not.

    Three rules, in order:

    1. **An empty identity always refuses the whole group.** An empty slug is
       the absence of an answer, never evidence that two rows share a source.
       The previous version compared ``len(set(slugs)) <= 1`` first, so two rows
       whose identity could not be resolved — different unknown hosts, or
       dangling ``source_id`` values — both mapped to ``""``, collapsed to a
       one-element set, and were ranked and deleted as though they were
       confirmed same-source duplicates. That is the one case where guessing is
       least defensible, and it was the case that passed.
    2. **One shared, explicit, presently ungoverned slug is rankable.** When
       every member carries the *same* named slug, authority is a constant
       within the group and cannot decide the winner, so an unrecognised source
       is harmless: ordering falls to the section and URL rules. This is how a
       newly added source behaves before it reaches the tier table.
    3. **A mixed group with any ungoverned identity refuses.** If identities
       differ and any of them is not governed, the ungoverned member might be
       the true authority, and picking a winner would be a guess.

    Non-destructive callers do not use this: dedup_articles() discards a
    duplicate it has not yet stored, which is recoverable on the next run. A
    DELETE is not.
    """
    slugs = [authority_slug(a) for a in group]

    # Rule 1 — unresolved identity, before any sameness test.
    if any(not s for s in slugs):
        n = sum(1 for s in slugs if not s)
        return (
            "%d of %d row(s) have no resolvable source identity; an empty "
            "identity is unresolved, not proof of a shared source" % (n, len(slugs))
        )

    # Rule 2 — one explicit identity, governed or not.
    if len(set(slugs)) == 1:
        return None

    # Rule 3 — mixed identities, any ungoverned.
    ungoverned = sorted({s for s in slugs if s not in _SOURCE_AUTHORITY_TIER})
    if ungoverned:
        return (
            "cross-source group with ungoverned source identity: %s"
            % ", ".join(ungoverned)
        )
    return None


def _field(obj, name):
    """Read a field from a dict-like or a sqlite3.Row."""
    getter = getattr(obj, "get", None)
    if getter is not None:
        try:
            return getter(name)
        except TypeError:
            pass
    try:
        return obj[name]
    except (KeyError, IndexError, TypeError):
        return None


# ── Dedup ────────────────────────────────────────────────────────────────────

def dedup_articles(articles: list[dict]) -> list[dict]:
    """
    Group articles by Chinese-title hash and keep the highest-priority copy
    from each group. PLA Daily reposts the same piece across multiple
    service-branch sub-paths under the same Chinese title; this filter
    collapses those into one before LLM translation runs.

    Each input dict is expected to carry either:
        - `title_zh` / `body_zh`  (spec naming), or
        - `title_original` / `text_original`  (existing pipeline naming).
    The function reads `title_zh` first and falls back to `title_original`;
    same for body. Articles with no usable Chinese title pass through
    unchanged (we have no reliable grouping signal for them).

    Returns a new list; does not mutate the input.

    Provenance limitation (unresolved, deliberately out of scope here): this
    collapses a duplicate group to ONE surviving dict and discards the losing
    copies' URLs entirely. After this change the survivor is the most
    authoritative copy rather than an arbitrary one, but the fact that MOD
    China and PLA Daily both carried a release — and at which URLs — is still
    not recorded anywhere. Representing a release as one document with several
    source-attributed locations is a provenance-model question (capture
    storage / document versioning, Phase 3 of the Defense Discourse
    foundation), not something a title-dedup filter should invent.
    """
    groups: dict[str, list[dict]] = {}
    passthrough: list[dict] = []

    for article in articles:
        title = article.get("title_zh") or article.get("title_original") or ""
        h = title_hash(title)
        if not h:
            passthrough.append(article)
            continue
        groups.setdefault(h, []).append(article)

    deduped: list[dict] = []
    for h, group in groups.items():
        if len(group) == 1:
            deduped.append(group[0])
            continue
        # Canonical selection uses the shared key — see canonical_sort_key().
        # scripts/cleanup_duplicates.py ranks with the same function, so a
        # destructive cleanup can never disagree with what the pipeline stored.
        winner = select_canonical(group)
        deduped.append(winner)

    # Preserve input order roughly: re-sort by first appearance.
    order = {id(a): i for i, a in enumerate(articles)}
    deduped.sort(key=lambda a: order.get(id(a), 0))
    passthrough.sort(key=lambda a: order.get(id(a), 0))

    return deduped + passthrough
