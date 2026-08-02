"""
Central configuration for PLA Watch.
Edit values here; load secrets from .env (never commit .env).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

if os.environ.get("ANTHROPIC_API_KEY") == "":
    os.environ.pop("ANTHROPIC_API_KEY")
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR   = Path(__file__).parent
CACHE_DIR  = ROOT_DIR / "cache"
OUTPUT_DIR = ROOT_DIR / "output"
DB_PATH    = ROOT_DIR / "pla_watch.db"

# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

# ---------------------------------------------------------------------------
# HTTP behavior
# ---------------------------------------------------------------------------
REQUEST_DELAY_SECONDS:   float = 2.5   # Minimum gap between outbound requests
REQUEST_TIMEOUT_SECONDS: int   = 30
MAX_RETRIES:             int   = 3

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
RELEVANCE_THRESHOLD: float = 0.60      # LLM confidence score; articles below this are filtered

# RELEVANCE_MODEL: cheap first-pass binary classifier (pass/fail at threshold).
# Haiku is ~10-20x cheaper than Sonnet and sufficient for binary relevance scoring.
# Full analysis (translation, summary, categorization) always uses ANALYSIS_MODEL.
RELEVANCE_MODEL: str = os.environ.get("RELEVANCE_MODEL", "claude-haiku-4-5-20251001")

# ANALYSIS_MODEL: used for translation, summarization, and categorization.
# If the API returns a model-not-found error, verify the current ID at
# https://docs.anthropic.com/en/docs/about-claude/models
ANALYSIS_MODEL: str = os.environ.get("ANALYSIS_MODEL", "claude-sonnet-4-6")

# Hard cap on LLM-analyzed articles per daily run.
# Prevents runaway costs from large scrape days or backlog catch-up.
# Override via env var: DAILY_ANALYSIS_CAP=20 python pipeline.py
# DAILY_ANALYSIS_CAP: per-run ceiling on articles sent to the LLM. Raised 15→40
# on 2026-07-30, then 40→55 on 2026-07-31 (analyst-approved). At 15 the cap sat
# *below* the ~30/day scrape rate, so every run deferred ~18 articles into a
# backlog that could only grow; 1,119 articles accumulated over 66 days without
# ever being relevance-screened (DECISION_LOG 2026-07-30).
#
# Sizing rule: fresh scrapes receive (1 - BACKLOG_RESERVE_FRACTION) * cap slots,
# so break-even against a scrape rate S requires cap >= S / (1 - reserve).
# Measured intake is 32–40/day (avg ~37) over 2026-07-26..07-31, so at a 0.3
# reserve the break-even cap is 37 / 0.7 ≈ 53. 40 was still below it: the
# 2026-07-30 run deferred 9 fresh articles. 55 clears break-even with ~1 day of
# margin and leaves ~17 slots/run draining the backlog.
# The cap must stay above the scrape rate or the backlog resumes growing — watch
# the "newly scraped article(s) deferred by the cap" warning in pipeline logs,
# which fires when it doesn't.
DAILY_ANALYSIS_CAP: int = int(os.environ.get("DAILY_ANALYSIS_CAP", "55"))

# BACKLOG_RESERVE_FRACTION: share of DAILY_ANALYSIS_CAP held for backlog articles
# (relevance-pending or never-scored) so a full day of fresh scrapes cannot crowd
# them out. Until 2026-07-30 the queue was `new + pending + unscored` truncated to
# the cap; since a run inserts ~30 articles and the cap is 15, the slice never
# reached the backlog and it drained at exactly zero per run — permanently
# (DECISION_LOG 2026-07-30). Unused new-article slots still spill to the backlog.
# NOTE: this guarantees the backlog *drains*, not that it *shrinks*. While
# DAILY_ANALYSIS_CAP is below the ~30/day inflow, the backlog still grows.
BACKLOG_RESERVE_FRACTION: float = float(os.environ.get("BACKLOG_RESERVE_FRACTION", "0.3"))

# LIVE_BACKLOG_DAYS: how recently an unscreened article must have been scraped
# to be treated as *editorially live* — i.e. still able to reach an edition that
# has not been written yet. Live articles are screened before older ones; the
# rest keep FIFO order for archive completeness.
#
# Why this is not plain FIFO (DECISION_LOG 2026-08-02): the backlog is drained
# oldest-first, so a deferred article joins the BACK of a queue ~1,180 deep.
# On 2026-08-02 the recovered 07-30/07-31 articles sat behind 1,106 older
# unscreened rows — roughly two months at ~16-20 slots/run — so they could not
# be screened in time for edition No. 12, the edition covering their own week.
# Pure FIFO spends the entire backlog reserve on material too old to affect any
# unwritten edition, while burying the material that still can.
#
# 14 days covers the current edition window plus one week of slack for a late
# draft. Raising it enlarges the priority tier and slows archive drain; the
# archive is never starved outright, only deferred behind the live tier.
LIVE_BACKLOG_DAYS: int = int(os.environ.get("LIVE_BACKLOG_DAYS", "14"))

# TRANSLATION_MAX_TOKENS: output ceiling for the Chinese→English translation call.
# Was 4000 until 2026-07-30, which silently truncated every long article: the
# response was cut mid-JSON, parsing failed, and the article was never written
# (163 of 697 relevant articles, 100% of those over 5000 Chinese characters —
# see DECISION_LOG 2026-07-30). ANALYSIS_MODEL allows 128K output; 32K covers
# the longest article observed (18,148 chars) with wide margin. Calls at this
# size must stream, or the SDK hits an HTTP timeout.
TRANSLATION_MAX_TOKENS: int = int(os.environ.get("TRANSLATION_MAX_TOKENS", "32000"))

PROMPT_VERSION: str = "v1"

# ---------------------------------------------------------------------------
# Keyword pre-filter
# An article must match at least one keyword to proceed to the LLM pass.
# Scope: PLA + PLAN/PLAAF/PLARF/PLASSF + PAP + Coast Guard + defense industry
#        + Taiwan/SCS/ECS gray-zone + cyber/info warfare
# ---------------------------------------------------------------------------
RELEVANCE_KEYWORDS_ZH: list[str] = [
    # Core institutions
    "解放军", "人民解放军", "军委", "中央军委", "国防部", "战区",
    # Services and branches
    "海军", "空军", "火箭军", "陆军", "战略支援部队", "联合参谋部",
    "海警", "武警", "人民武装警察",
    # Platforms and systems
    "导弹", "航母", "舰", "潜艇", "歼", "轰", "运", "直", "无人机",
    "高超音速", "核", "弹道导弹", "巡航导弹",
    # Operations and readiness
    "演习", "军演", "实弹", "联合作战", "战备", "巡逻", "侦察",
    # Geographic flashpoints
    "台湾", "台海", "南海", "东海", "钓鱼岛", "黄岩岛", "渤海",
    # Modernization / industry
    "国防工业", "装备", "采购", "研制", "航空工业", "中船集团",
    "兵器工业", "航天科工", "航天科技",
    # Doctrine / information domain
    "信息化", "智能化", "网络战", "信息战", "认知战", "心理战",
    "电子战", "太空", "网络空间",
    # Internal security (PAP-relevant)
    "新疆", "西藏", "香港", "反恐", "维稳",
    # Leadership / political work
    "军事委员会", "政治工作", "习近平主席", "国防",
]

RELEVANCE_KEYWORDS_EN: list[str] = [
    # Institutions
    "PLA", "People's Liberation Army", "CMC", "Central Military Commission",
    "Ministry of National Defense", "MND",
    "People's Armed Police", "PAP", "China Coast Guard",
    # Services
    "PLAN", "PLAAF", "PLARF", "PLASSF", "PLA Navy", "PLA Air Force",
    "PLA Rocket Force",
    # Operations
    "military exercise", "live-fire", "joint exercise", "patrol", "drill",
    "deployment", "readiness",
    # Platforms
    "aircraft carrier", "destroyer", "submarine", "fighter jet", "bomber",
    "missile", "hypersonic", "nuclear", "ballistic", "cruise missile",
    "drone", "UAV",
    # Flashpoints
    "Taiwan", "South China Sea", "East China Sea", "Senkaku", "Diaoyu",
    "Scarborough", "Spratlys", "Paracels",
    # Modernization
    "defense industry", "AVIC", "CSSC", "procurement", "weapons system",
    # Doctrine / information
    "cyber", "information warfare", "cognitive warfare", "electronic warfare",
    "space", "counterspace",
    # Misc
    "defense", "military",
]
