"""Deterministic, provisional China research focus — NEVER editorial approval.

A *discovery aid* with a full-corpus escape hatch. It is not a 600-document
verified list: titles are machine-derived, source bodies can be faulty, and
new daily records are never automatically human-approved.

No DB writes, external requests, ML or source-text modifications.
"""
from collections import Counter, defaultdict
import re

FOCUS_TARGET = 600
CHINA_SOURCE_CAPS = {
    "pla_daily": 300,
    "mod_china": 130,
    "china_mil_online": 140,
    "xinhua_mil": 10,
    "global_times_mil": 20,
}
# Explicit known historical evidence quality issues; records remain in full
# browsing, their record/ and article/ routes, all citation trails and sitemap.
KNOWN_BODY_HOLDS = frozenset({
    170, 419, 905, 946, 1246, 1954, 2180, 2265, 2753, 2881, 3180, 3181
})
# Two known screening negatives that are nevertheless consequential formal
# Foreign Ministry originals. Provisional lead discovery, NOT a claim that
# original text has received independent human verification.
ORIGINAL_LEADS = frozenset({2391, 2849})

# These words influence discoverability only. They are not evidence of any
# underlying event, authenticity, military capability, or editorial value.
TOPIC_CUES = (
    "台湾", "台海", "南海", "黄岩", "东海", "菲律宾", "日本", "美国",
    "朝鲜", "韩国", "导弹", "核", "航母", "战机", "联演", "军演",
    "海警", "防长", "防务", "联合", "出口管制", "制裁", "台独",
    "军事合作", "空军", "海军", "战略", "装备", "人工智能",
    "台灣", "印太", "洲际", "驱逐舰", "军舰", "防空", "火箭军",
)
# Recurring column titles can contain substantive reporting too. Modest
# de-prioritization is safer than inventing categorical exclusions.
COMMENTARY_CUES = (
    "强军论坛", "八一锐评", "清风正气歌", "思想战线",
    "军人修养", "树立和践行正确政绩观", "政绩观", "思想政治",
)


def _source(row):
    return row.get("source_slug")


def _is_china(row):
    return row.get("desk_id") == "china" or _source(row) in CHINA_SOURCE_CAPS


def _normal(title):
    return re.sub(r"[\W_]+", "", (title or "").lower(), flags=re.UNICODE)


def _captured_on(row):
    return str(row.get("scraped_at") or "")[:10]


def _eligible(row):
    if row.get("id") in KNOWN_BODY_HOLDS or _source(row) not in CHINA_SOURCE_CAPS:
        return False
    if _source(row) == "global_times_mil":
        # Historical pre-repair Global Times copies have demonstrated severe
        # body contamination. This is a capture-quality hold, NOT proof the
        # publisher original was worthless or wrong.
        stamp = _captured_on(row)
        if len(stamp) != 10 or stamp < "2026-09-16":
            return False
    if row.get("id") in ORIGINAL_LEADS:
        return True
    # The analysis state is an *automated relevance* signal, not editor review.
    if row.get("state") == "analyzed":
        return True
    # Limited title-only primary-source coverage in low-analyzed sources.
    if _source(row) == "xinhua_mil":
        return True
    return False


def _rank(row):
    chinese = row.get("title_original") or ""
    english = row.get("title_english") or ""
    title = chinese + " " + english
    score = 0
    if row.get("state") == "analyzed":
        score += 6
    if row.get("in_trails"):
        score += 3
    if row.get("id") in ORIGINAL_LEADS:
        score += 15
    score += min(6, sum(cue in title for cue in TOPIC_CUES))
    score -= 5 * any(cue in title for cue in COMMENTARY_CUES)
    if row.get("model_flagged") is True:
        score += 2
    return (-score, -(row.get("id") or 0))


def _balanced(pool, limit, already):
    """Take distributed monthly document opportunities, not newest-only."""
    months = defaultdict(list)
    for row in pool:
        months[(row.get("published_date") or "")[:7]].append(row)
    for items in months.values():
        items.sort(key=_rank)
    order = sorted(months, reverse=True)
    selected = []
    while len(selected) < limit:
        any_added = False
        for month in order:
            if len(selected) >= limit:
                break
            bucket = months[month]
            while bucket:
                row = bucket.pop(0)
                ident = row["id"]
                title = _normal(row.get("title_original") or row.get("title_english"))
                # Exact normalized title suppression prevents a repeated title
                # from consuming multiple headline slots. All source copies
                # stay in the complete corpus and available via direct URLs.
                if not title or title in already["titles"]:
                    continue
                if ident in already["ids"]:
                    continue
                already["titles"].add(title)
                already["ids"].add(ident)
                selected.append(row)
                any_added = True
                break
        if not any_added:
            break
    return selected


def build_focus(corpus, china_target=FOCUS_TARGET):
    if not isinstance(corpus, list):
        raise ValueError("focus requires the complete rendered corpus")
    if type(china_target) is not int or china_target < 1:
        raise ValueError("invalid provisional focus target")
    ids = set()
    for row in corpus:
        ident = row.get("id")
        if type(ident) is not int or ident <= 0 or ident in ids:
            raise ValueError("full-corpus identity missing or repeated")
        ids.add(ident)
    china = [r for r in corpus if _is_china(r)]
    other = [r for r in corpus if not _is_china(r)]
    selected = []
    seen = {"titles": set(), "ids": set()}
    # Preserve per-source breadth; do not let 4,000 PLA Daily titles override
    # every other source merely because of collection volume.
    allocations = {slug: quota * china_target // FOCUS_TARGET
                   for slug, quota in CHINA_SOURCE_CAPS.items()}
    unassigned = china_target - sum(allocations.values())
    remainders = sorted(
        CHINA_SOURCE_CAPS,
        key=lambda slug: (-(CHINA_SOURCE_CAPS[slug] * china_target % FOCUS_TARGET), slug))
    for slug in remainders[:unassigned]:
        allocations[slug] += 1
    for slug, quota in allocations.items():
        if quota:
            selected.extend(_balanced(
                [r for r in china if _source(r) == slug and _eligible(r)],
                quota, seen))
    # If a low-volume source cannot fill its allocated spots (e.g. the
    # quarantined historical Global Times bodies), fill only from other
    # machine-analyzed, non-held China material — never false "approved" IDs.
    if len(selected) < china_target:
        selected.extend(_balanced(
            [r for r in china if _eligible(r)],
            china_target - len(selected), seen))
    if len(selected) > china_target:
        raise ValueError("focus exceeded target")
    wanted = {r["id"] for r in selected}
    if not wanted.issubset(ids) or wanted & KNOWN_BODY_HOLDS:
        raise ValueError("focus lost custody or promoted a historical hold")
    all_visible = wanted | {r["id"] for r in other}
    focus_rows = [r for r in corpus if r["id"] in all_visible]
    if len(focus_rows) != len(all_visible):
        raise ValueError("focus duplication")
    assert len(selected) == len(wanted)
    return {
        "ids": sorted(all_visible),
        "china_ids": sorted(wanted),
        "china_total": len(china),
        "china_focus": len(wanted),
        "all_focus": len(all_visible),
        "full_total": len(corpus),
        "source_counts": dict(sorted(Counter(
            _source(r) for r in selected).items())),
        "rows": focus_rows,
        "policy": "automated_research_focus_not_human_curated",
    }
