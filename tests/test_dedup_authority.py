"""
Cross-source canonical selection tests.

Regression cover for the 2026-08-17 MOD China defect: canonical choice was
decided by the first path segment of the URL, using a map built for 81.cn's
internal sections. `http://www.mod.gov.cn/gfbw/...` parsed as section "gfbw",
missed the map, scored 70, and lost to PLA Daily's 要闻 at 100 — so the Tier A
ministry copy was discarded in favour of a Tier B newspaper reprint on every
duplicate, and `mod_china` stored nothing for 38 days while publishing.

Offline: no network, no model calls, no database.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import itertools                                                # noqa: E402

from processing.dedup import (                                  # noqa: E402
    _AUTHORITY_TIER_RANK,
    _SOURCE_AUTHORITY_TIER,
    authority_priority,
    authority_slug,
    canonical_sort_key,
    dedup_articles,
    select_canonical,
    source_priority,
    title_hash,
    url_section,
)

TITLE = "国防部：“台独”死局演不赢、改不了"


def art(url, slug=None, title=TITLE):
    a = {"url": url, "title_original": title, "text_original": "正文"}
    if slug is not None:
        a["source_slug"] = slug
    return a


class TestCrossSourceWinner(unittest.TestCase):
    """Requirement 1: MOD China Tier A beats PLA Daily Tier B on the same title."""

    def test_mod_china_wins_over_pla_daily(self):
        mod = art("http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/16479365.html", "mod_china")
        pla = art("http://www.81.cn/yw_208727/16479366.html", "pla_daily")
        for group in ([mod, pla], [pla, mod]):     # order must not matter
            kept = dedup_articles(group)
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]["source_slug"], "mod_china")

    def test_mod_wins_even_against_the_highest_81cn_section(self):
        """The old bug was numeric: 70 < 100. Authority must dominate outright."""
        mod = art("http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/16479365.html", "mod_china")
        pla = art("http://www.81.cn/yw_208727/1.html", "pla_daily")
        self.assertGreater(authority_priority(mod), authority_priority(pla))
        self.assertLess(source_priority(mod["url"]), source_priority(pla["url"]))
        self.assertEqual(dedup_articles([pla, mod])[0]["source_slug"], "mod_china")

    def test_bilingual_tag_still_collapses_onto_the_chinese_title(self):
        """
        Title normalization is deliberately unchanged: 【双语】 is stripped, which
        is what makes MOD's bilingual release group with PLA Daily's reprint.
        """
        mod = art("http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/16479363.html",
                  "mod_china", title="【双语】" + TITLE)
        pla = art("http://www.81.cn/yw_208727/16479368.html", "pla_daily")
        self.assertEqual(title_hash(mod["title_original"]), title_hash(pla["title_original"]))
        kept = dedup_articles([pla, mod])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["source_slug"], "mod_china")

    def test_slug_missing_falls_back_to_host(self):
        mod = art("http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/16479365.html")
        pla = art("http://www.81.cn/yw_208727/16479366.html")
        self.assertEqual(authority_slug(mod), "mod_china")
        self.assertEqual(dedup_articles([pla, mod])[0]["url"], mod["url"])

    def test_host_fallback_covers_the_hosts_sources_actually_serve(self):
        """
        China Military Online is declared as english.chinamil.com.cn but serves
        eng.chinamil.com.cn. A fallback keyed only on the manifest base_url
        would score its articles as ungoverned.
        """
        for host, slug in (
            ("eng.chinamil.com.cn", "china_mil_online"),
            ("english.chinamil.com.cn", "china_mil_online"),
            ("www.globaltimes.cn", "global_times_mil"),
            ("www.mod.gov.cn", "mod_china"),
            ("www.81.cn", "pla_daily"),
        ):
            a = {"url": f"http://{host}/x/1.html", "title_original": TITLE}
            self.assertEqual(authority_slug(a), slug, host)
            self.assertGreater(authority_priority(a), 0, host)

    def test_unknown_source_never_outranks_a_governed_one(self):
        unknown = art("https://example.test/whatever/1.html", "not_a_source")
        pla = art("http://www.81.cn/yw_208727/1.html", "pla_daily")
        self.assertLess(authority_priority(unknown), authority_priority(pla))
        self.assertEqual(dedup_articles([unknown, pla])[0]["source_slug"], "pla_daily")


class TestOrderingIsTotal(unittest.TestCase):
    """
    The key must decide every group on the group's own content, never on the
    order the rows arrived in.

    The previous key was (authority, section, -len(url)). It tied at the top on
    16 of the 17 duplicate groups in production, so the survivor was whichever
    tied row `max()` happened to see first — reverse the batch and a different
    row survived, from the same function that also drives deletion.
    """

    #: Same source, same section, same URL length. Every earlier key component
    #: ties; only the final URL component can separate these.
    EQUAL = [
        "http://www.81.cn/yw_208727/16463738.html",
        "http://www.81.cn/yw_208727/16468666.html",
        "http://www.81.cn/yw_208727/16470502.html",
    ]

    def _arts(self, urls):
        return [art(u, "pla_daily") for u in urls]

    def test_every_permutation_picks_the_same_url(self):
        winners = {
            select_canonical(self._arts(list(p)))["url"]
            for p in itertools.permutations(self.EQUAL)
        }
        self.assertEqual(len(winners), 1,
                         "winner changed with input order: %s" % sorted(winners))

    def test_dedup_articles_agrees_across_every_permutation(self):
        winners = set()
        for p in itertools.permutations(self.EQUAL):
            kept = dedup_articles(self._arts(list(p)))
            self.assertEqual(len(kept), 1)
            winners.add(kept[0]["url"])
        self.assertEqual(len(winners), 1,
                         "dedup_articles is order-dependent: %s" % sorted(winners))

    def test_pipeline_and_shared_key_agree_on_every_permutation(self):
        for p in itertools.permutations(self.EQUAL):
            arts = self._arts(list(p))
            self.assertEqual(dedup_articles(arts)[0]["url"],
                             max(arts, key=canonical_sort_key)["url"])

    def test_the_earlier_three_part_key_really_did_tie(self):
        """Documents the defect this replaced, so it cannot quietly return."""
        old = {(authority_priority(a), source_priority(a["url"]), -len(a["url"]))
               for a in self._arts(self.EQUAL)}
        self.assertEqual(len(old), 1, "fixture no longer reproduces the tie")
        new = {canonical_sort_key(a) for a in self._arts(self.EQUAL)}
        self.assertEqual(len(new), len(self.EQUAL), "new key must separate them")

    def test_key_is_total_over_distinct_urls(self):
        arts = self._arts(self.EQUAL) + [
            art("http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/1.html", "mod_china"),
            art("http://eng.chinamil.com.cn/view/1.html", "china_mil_online"),
        ]
        self.assertEqual(len({canonical_sort_key(a) for a in arts}), len(arts))


class TestEqualTierCrossSource(unittest.TestCase):
    """
    Equal-tier cross-source ties resolve on source identity, lexically.

    china_mil_online and pla_daily are both Tier B. Nothing in the manifest
    ranks one above the other, so the tie-break is a deterministic lexical
    comparison of the slug — NOT a judgement that either outranks the other.
    It is recorded here so the behaviour is explicit rather than emergent.
    """

    MOD = "http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/1.html"
    PLA_MAIN = "http://www.81.cn/yw_208727/1.html"
    CMO = "http://eng.chinamil.com.cn/view/1.html"

    def test_equal_tier_winner_is_stable_and_named(self):
        pla = art(self.PLA_MAIN, "pla_daily")
        cmo = art(self.CMO, "china_mil_online")
        self.assertEqual(authority_priority(pla), authority_priority(cmo),
                         "fixture assumes both are Tier B")
        for group in ([pla, cmo], [cmo, pla]):
            self.assertEqual(select_canonical(group)["source_slug"], "pla_daily")

    def test_equal_tier_result_does_not_depend_on_81cn_path_shape(self):
        """
        Section priority must not reach across a source boundary. PLA Daily wins
        this pairing on identity, so changing its section — or removing the
        81.cn-shaped path entirely — must not change the outcome.
        """
        cmo = art(self.CMO, "china_mil_online")
        for pla_url in (
            "http://www.81.cn/yw_208727/1.html",     # highest mapped section
            "http://www.81.cn/hj_208557/1.html",     # service section
            "http://www.81.cn/unmapped_999/1.html",  # unmapped 81.cn section
            "http://www.81.cn/1.html",               # no section at all
        ):
            pla = art(pla_url, "pla_daily")
            with self.subTest(pla_url):
                self.assertEqual(select_canonical([cmo, pla])["source_slug"],
                                 "pla_daily")
                self.assertEqual(select_canonical([pla, cmo])["source_slug"],
                                 "pla_daily")

    def test_a_higher_tier_still_beats_both_regardless_of_section(self):
        mod = art(self.MOD, "mod_china")
        pla = art(self.PLA_MAIN, "pla_daily")
        cmo = art(self.CMO, "china_mil_online")
        for group in itertools.permutations([mod, pla, cmo]):
            self.assertEqual(select_canonical(list(group))["source_slug"],
                             "mod_china")

    #: Equal tier, equal URL length, and section priority pointing the OPPOSITE
    #: way to source identity. Section says china_mil_online (mapped 要闻, 100);
    #: identity says pla_daily (lexically greater). Only a key that compares
    #: identity BEFORE section can get this right, so this pair is what proves
    #: section cannot reach across a source boundary.
    CMO_HIGH_SECTION = "http://www.81.cn/yw_208727/0001.html"   # section 100
    PLA_LOW_SECTION = "http://www.81.cn/aaaaaaaaa/0001.html"    # section 70

    def test_identity_beats_section_when_the_two_disagree(self):
        cmo = art(self.CMO_HIGH_SECTION, "china_mil_online")
        pla = art(self.PLA_LOW_SECTION, "pla_daily")

        self.assertEqual(len(cmo["url"]), len(pla["url"]), "fixture: equal length")
        self.assertEqual(authority_priority(cmo), authority_priority(pla),
                         "fixture: equal tier")
        self.assertGreater(source_priority(cmo["url"]), source_priority(pla["url"]),
                           "fixture: section favours china_mil_online")

        for group in ([cmo, pla], [pla, cmo]):
            self.assertEqual(
                select_canonical(group)["source_slug"], "pla_daily",
                "section priority must not decide a cross-source pair",
            )
            self.assertEqual(dedup_articles(group)[0]["source_slug"], "pla_daily")

    def test_section_cannot_separate_candidates_of_different_identity(self):
        """
        Structural: identity is compared before section, so two rows with
        different identities are always decided before section is consulted.
        """
        cmo = art(self.CMO_HIGH_SECTION, "china_mil_online")
        pla = art(self.PLA_LOW_SECTION, "pla_daily")
        kc, kp = canonical_sort_key(cmo), canonical_sort_key(pla)
        self.assertEqual(kc[0], kp[0], "same tier")
        self.assertEqual(kc[1], "china_mil_online")
        self.assertEqual(kp[1], "pla_daily")
        self.assertLess(kc[:2], kp[:2],
                        "the decision is made before the section component")
        self.assertGreater(kc[2], kp[2],
                           "section, had it been reached first, would disagree")


class TestIntra81cnPriorityUnchanged(unittest.TestCase):
    """Requirement 2: PLA Daily main-news vs service-section behaviour is intact."""

    def test_main_news_still_beats_service_section(self):
        main = art("http://www.81.cn/yw_208727/16479366.html", "pla_daily")
        navy = art("http://www.81.cn/hj_208557/16479366.html", "pla_daily")
        for group in ([main, navy], [navy, main]):
            self.assertEqual(dedup_articles(group)[0]["url"], main["url"])

    def test_documented_section_scores_are_unchanged(self):
        self.assertEqual(source_priority("http://www.81.cn/yw_208727/1.html"), 100)
        self.assertEqual(source_priority("http://www.81.cn/hj_208557/1.html"), 90)
        self.assertEqual(source_priority("http://www.81.cn/kj_208559/1.html"), 90)
        self.assertEqual(source_priority("http://www.81.cn/wj_208567/1.html"), 85)
        self.assertEqual(source_priority("http://www.81.cn/jw_208551/1.html"), 80)
        self.assertEqual(source_priority("http://www.81.cn/fyr/1.html"), 50)

    def test_shorter_url_still_breaks_a_full_tie(self):
        short = art("http://www.81.cn/yw_208727/1.html", "pla_daily")
        long_ = art("http://www.81.cn/yw_208727/1234567890.html", "pla_daily")
        self.assertEqual(dedup_articles([long_, short])[0]["url"], short["url"])


class TestSectionClassification(unittest.TestCase):
    """Requirement 3: unmapped 81.cn section != non-81.cn path."""

    def test_unmapped_81cn_section_and_foreign_path_differ(self):
        unmapped_81cn = "http://www.81.cn/brand_new_section_999/1.html"
        foreign = "http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/1.html"
        self.assertEqual(url_section(unmapped_81cn), "brand_new_section_999")
        self.assertEqual(url_section(foreign), "")
        self.assertEqual(source_priority(unmapped_81cn), 70)
        self.assertEqual(source_priority(foreign), 50)
        self.assertNotEqual(source_priority(unmapped_81cn), source_priority(foreign))

    def test_no_foreign_host_is_scored_as_an_81cn_section(self):
        for url in (
            "http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/1.html",
            "http://english.chinamil.com.cn/view/1.html",
            "https://www.globaltimes.cn/page/1.html",
            "https://www.xinhuanet.com/mil/1.html",
            "https://example.test/yw_208727/1.html",   # 81.cn-looking, wrong host
        ):
            self.assertEqual(url_section(url), "", url)
            self.assertEqual(source_priority(url), 50, url)

    def test_bare_81cn_host_is_still_recognised(self):
        self.assertEqual(source_priority("http://81.cn/yw_208727/1.html"), 100)


class TestTierTableGovernance(unittest.TestCase):
    """
    The tier table in processing/dedup.py is a constant, not a manifest read,
    to keep a low-level batch function free of configuration I/O. This test is
    the price of that choice: it fails the moment the two disagree.
    """

    @staticmethod
    def _governed_sources_from_every_desk():
        """
        {slug: authority_tier} across EVERY desk manifest, not just China.

        Scoped to `desks/*/manifest.json`, the same set core/registry.py syncs.
        A new desk's sources are governed the moment its manifest exists, so
        they must appear in the constant too — otherwise they would silently
        rank at _UNKNOWN_AUTHORITY and lose every duplicate to a governed
        source.
        """
        manifests = sorted((REPO_ROOT / "desks").glob("*/manifest.json"))
        assert manifests, "no desk manifests found under desks/*/manifest.json"
        governed = {}
        for path in manifests:
            for src in json.loads(path.read_text()).get("sources", []):
                governed[src["slug"]] = src["authority_tier"]
        return governed, manifests

    def test_tier_table_matches_manifest(self):
        from_manifests, paths = self._governed_sources_from_every_desk()
        self.assertEqual(
            _SOURCE_AUTHORITY_TIER, from_manifests,
            "processing/dedup.py._SOURCE_AUTHORITY_TIER has drifted from the "
            "authority_tier values in %s. Update the constant deliberately — "
            "it is a mirror, not a cache."
            % ", ".join(str(p.relative_to(REPO_ROOT)) for p in paths),
        )

    def test_every_manifest_source_is_governed(self):
        """Adding a manifest source must fail this until the constant is updated."""
        from_manifests, _ = self._governed_sources_from_every_desk()
        self.assertEqual(
            set(_SOURCE_AUTHORITY_TIER) - set(from_manifests), set(),
            "constant lists sources no manifest declares",
        )
        self.assertEqual(
            set(from_manifests) - set(_SOURCE_AUTHORITY_TIER), set(),
            "manifest declares sources the constant does not govern",
        )

    def test_every_manifest_tier_value_matches(self):
        """Changing any authority_tier must fail this until the constant agrees."""
        from_manifests, _ = self._governed_sources_from_every_desk()
        for slug, tier in from_manifests.items():
            self.assertEqual(
                _SOURCE_AUTHORITY_TIER.get(slug), tier,
                "authority_tier for %s differs between manifest and constant" % slug,
            )

    def test_no_config_io_in_the_hot_path(self):
        """
        The constant exists so dedup_articles() performs no configuration I/O.

        Asserted structurally (imports and calls), not by substring: the module
        legitimately *discusses* manifests in its comments, and a prose match
        would fail on documentation while missing a real import.
        """
        import ast

        tree = ast.parse((REPO_ROOT / "processing" / "dedup.py").read_text())

        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for forbidden in ("json", "sqlite3", "pathlib", "config", "core", "storage"):
            self.assertNotIn(
                forbidden, imported,
                "processing/dedup.py must not import %r — it is a pure batch "
                "transform in the pipeline's hot path" % forbidden,
            )

        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertNotIn("open", called, "processing/dedup.py must not open files")

    def test_every_tier_used_by_the_manifest_has_a_rank(self):
        for slug, tier in _SOURCE_AUTHORITY_TIER.items():
            self.assertIn(tier, _AUTHORITY_TIER_RANK, slug)

    def test_ranks_are_strictly_ordered_a_to_d(self):
        r = _AUTHORITY_TIER_RANK
        self.assertGreater(r["A"], r["B"])
        self.assertGreater(r["B"], r["C"])
        self.assertGreater(r["C"], r["D"])


class TestScopeIsPartOfTheContract(unittest.TestCase):
    """
    `dedup_articles()` collapses same-title copies **within one batch**. That
    scope is not an implementation detail waiting to be widened — it is the
    only scope that is correct for every source at once, and these tests exist
    so that widening it has to be a deliberate act.

    Why it matters: a corpus-wide title check is right for a source that reuses
    a title for the same story (PLA Daily reposts one piece across
    service-branch sub-paths) and destructive for a source that reuses a title
    for different events. The second-desk research found the latter — on the
    Japan Joint Staff feed "Japan-U.S. Bilateral Exercise" titles 27 distinct
    exercises. A global check would drop 26 of them as duplicates, with no
    error raised and nothing in the ledger to show for it.

    `FOLLOWUP.md` proposes exactly that widening. It is annotated as blocked;
    this is the executable half of that annotation.
    """

    def _release(self, url, title):
        return {"url": url, "source_slug": "pla_daily",
                "title_original": title,
                "text_original": "正文内容 %s" % url,
                "published_date": "2026-05-10"}

    def test_dedup_reads_only_the_batch_it_is_given(self):
        """No database, no filesystem, no global state — call it twice and the
        second call cannot know what the first one saw."""
        title = "日米共同訓練について"
        first = dedup_articles([self._release("http://x/a1", title)])
        second = dedup_articles([self._release("http://x/a2", title)])
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1,
                         "a later batch was collapsed against an earlier one; "
                         "dedup has acquired cross-batch memory")
        self.assertEqual(second[0]["url"], "http://x/a2")

    def test_recurring_event_titles_survive_across_batches(self):
        """The Joint Staff case, run through the real function."""
        title = "Japan-U.S. Bilateral Exercise"
        kept = [dedup_articles([self._release("http://js/p%02d" % i, title)])[0]
                for i in range(1, 28)]
        self.assertEqual(len({a["url"] for a in kept}), 27,
                         "recurring event titles were collapsed; 27 distinct "
                         "exercises must survive as 27 records")

    def test_same_title_inside_one_batch_is_still_collapsed(self):
        """The behaviour that must NOT regress while protecting the above."""
        title = "解放军演习报道"
        kept = dedup_articles([self._release("http://x/a1", title),
                               self._release("http://x/a2", title)])
        self.assertEqual(len(kept), 1)

    def test_dedup_takes_no_database_handle(self):
        """
        The signature is the guard. A corpus-wide check needs a connection or a
        lookup callable; if one is ever added, this fails and the author has to
        come and read why.
        """
        import inspect
        params = list(inspect.signature(dedup_articles).parameters)
        self.assertEqual(params, ["articles"],
                         "dedup_articles gained a parameter — if this is the "
                         "persistent title-hash work, read the blocked note in "
                         "FOLLOWUP.md first")


if __name__ == "__main__":
    unittest.main()
