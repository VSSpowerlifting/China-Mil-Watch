"""Milestone B: the Desks Source Atlas, as rendered from the tracked DB.

A presentation and data contract for `desk_atlas` and the "What each desk
reads" section of desks.html. It builds into a disposable folder through the
renderer's safe path, never touches output/, and needs no browser: every
claim checked here is in the markup, because no limit may depend on script.
"""
from __future__ import annotations

import html as htmllib
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site" / "preview"))
import generate_preview as gp  # noqa: E402
from core.desk_source_provenance import EvidenceClass  # noqa: E402
from scripts.desk_source_provenance import build as build_provenance  # noqa: E402
from core.viewmodel import PublicView  # noqa: E402

DB = ROOT / "pla_watch.db"
CSS = ROOT / "site" / "preview" / "desk-atlas.css"
#: Desks whose official material is referenced or shadow-evaluated. None of
#: them may read as holding a public production archive.
NON_PRODUCTION = ("japan", "korea", "vietnam", "indonesia", "philippines",
                  "us-indopacific")


def _text(fragment: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


class DesksSourceAtlas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB.is_file():
            raise unittest.SkipTest("tracked DB unavailable")
        cls.tmp = Path(tempfile.mkdtemp(prefix="ipr-source-atlas-"))
        cls.out = cls.tmp / "preview"
        try:
            snapshot = gp.snapshot_from_corpus(DB)
            gp.build(cls.out, "Indo-Pacific Record", DB, snapshot=snapshot)
        except Exception:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise
        cls.html = (cls.out / "desks.html").read_text(encoding="utf-8")
        view = PublicView(DB)
        cls.desks = view.desk_directory()
        cls.source_views = view.source_directory()
        cls.prov = build_provenance(as_of=snapshot["date"], db_path=DB,
                                    with_health=False)
        start = cls.html.index('<h2 id="desk-scopes">')
        end = cls.html.index('<h2 id="desk-comparison">')
        cls.atlas = cls.html[start:end]
        cls.panels = dict(re.findall(
            r'<article class="sa-panel[^"]*" id="atlas-([a-z-]+)"[^>]*>(.*?)</article>',
            cls.atlas, re.S))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def group(self, slug, cls):
        m = re.search(r'<section class="sa-group sa-group--%s".*?</section>' % cls,
                      self.panels[slug], re.S)
        return m.group(0) if m else ""

    # -- structure ---------------------------------------------------------
    def test_one_panel_per_declared_desk_in_registry_order(self):
        order = re.findall(r'id="atlas-([a-z-]+)"[^>]*aria-labelledby', self.atlas)
        self.assertEqual(order, [d.slug for d in self.desks])
        self.assertEqual(len(order), 8)
        index = re.search(r'<nav class="sa-index".*?</nav>', self.atlas, re.S).group(0)
        self.assertEqual(re.findall(r'href="#atlas-([a-z-]+)"', index), order)

    def test_panels_do_not_feed_map_or_desk_counters(self):
        # The map's plate/flag-tab counts and per-desk guards read
        # `section.desk` and data-desk; the Atlas carries neither.
        self.assertNotIn('<section class="desk', self.atlas)
        self.assertNotIn("data-desk", self.atlas)
        self.assertEqual(self.atlas.count('<h2 id="desk-scopes">What each desk reads</h2>'), 1)

    def test_status_and_scope_come_from_the_registry(self):
        for d in self.desks:
            with self.subTest(desk=d.slug):
                panel = self.panels[d.slug]
                self.assertIn("desk-state--%s" % d.status, panel)
                self.assertIn(htmllib.escape(d.status_label, quote=False), panel)
                explain = re.search(r'<p class="sa-explain">(.*?)</p>', panel, re.S)
                self.assertEqual(_text(explain.group(1)),
                                 self.prov.get(d.slug).status_explanation)

    # -- limits, rights, blockers -------------------------------------------
    def test_limits_match_each_desk_page_and_are_never_hidden(self):
        for d in self.desks:
            with self.subTest(desk=d.slug):
                want = gp.public_desk_limits(d, self.source_views)
                block = re.search(r'<section class="sa-limits".*?</section>',
                                  self.panels[d.slug], re.S)
                got = ([_text(li) for li in re.findall(r"<li>(.*?)</li>", block.group(0), re.S)]
                       if block else [])
                self.assertEqual(got, want)
                page = htmllib.unescape((self.out / d.route).read_text(encoding="utf-8"))
                for limit in want:
                    self.assertIn(limit, page)
        # Nothing in the Atlas opens, collapses or hides text from a reader;
        # aria-hidden sits only on decorative marks with no text of their own.
        self.assertNotIn("<details", self.atlas)
        self.assertNotRegex(self.atlas, r"\shidden[\s>=]")
        for tag in re.findall(r'<[a-z0-9]+[^>]*aria-hidden="true"[^>]*>', self.atlas):
            self.assertRegex(tag, r'^<(svg|div class="sa-mark")')

    def test_rights_and_blockers_are_printed_verbatim(self):
        for d in self.desks:
            prov = self.prov.get(d.slug)
            panel = htmllib.unescape(self.panels[d.slug])
            with self.subTest(desk=d.slug):
                rights = {s.rights_statement for s in prov.sources if s.rights_statement}
                for text in rights:
                    self.assertIn(text, panel)
                self.assertEqual("sa-rights" in panel, bool(rights))
                for head, body in prov.blockers:
                    self.assertIn(head, panel)
                    self.assertIn(body, panel)

    # -- evidence classes ----------------------------------------------------
    def test_every_source_sits_under_its_class_heading(self):
        for d in self.desks:
            prov = self.prov.get(d.slug)
            with self.subTest(desk=d.slug):
                classes = re.findall(r'sa-group sa-group--([a-z_]+)"', self.panels[d.slug])
                self.assertEqual(classes, [c.value for c in prov.evidence_classes])
                for cls in prov.evidence_classes:
                    group = htmllib.unescape(self.group(d.slug, cls.value))
                    names = [s.name for s in prov.sources_of(cls)]
                    self.assertEqual(group.count('<li class="sa-source'), len(names))
                    for name in names:
                        self.assertIn(name, group)
                if not prov.sources:
                    self.assertIn("No source is declared for this desk.", self.panels[d.slug])

    def test_notes_disclose_nothing_not_already_public(self):
        # Production notes are internal registry text; a research family's
        # note is printed only where its own desk page already prints it.
        for d in self.desks:
            prov = self.prov.get(d.slug)
            page = htmllib.unescape((self.out / d.route).read_text(encoding="utf-8"))
            notes = [_text(n) for n in re.findall(
                r'<p class="sa-src-note">(.*?)</p>', self.panels[d.slug], re.S)]
            with self.subTest(desk=d.slug):
                self.assertNotIn("sa-src-note", self.group(d.slug, "production"))
                for s in prov.sources_of(EvidenceClass.PRODUCTION):
                    if s.note:
                        self.assertNotIn(htmllib.escape(s.note, quote=False)[:60],
                                         self.panels[d.slug])
                for note in notes:
                    self.assertIn(note, page)

    def test_run_health_and_counts_appear_only_on_production(self):
        for d in self.desks:
            panel = self.panels[d.slug]
            outside = re.sub(r'<section class="sa-group sa-group--production".*?</section>',
                             "", panel, flags=re.S)
            with self.subTest(desk=d.slug):
                self.assertNotIn("Latest run", outside)
                self.assertNotIn("records in the corpus", outside)
                self.assertNotIn('href="source/', outside)

    def test_non_production_desks_never_read_as_a_public_archive(self):
        for slug in NON_PRODUCTION:
            panel = self.panels[slug]
            with self.subTest(desk=slug):
                self.assertNotIn("sa-group--production", panel)
                self.assertNotIn("archive.html", panel)
                self.assertNotIn("Latest run", panel)
                self.assertNotIn("records in the corpus", panel)
                self.assertNotRegex(_text(panel), r"Browse its [\d,]+ records")

    def test_production_source_counts_sum_to_the_desk_total(self):
        for d in self.desks:
            if not self.prov.get(d.slug).sources_of(EvidenceClass.PRODUCTION):
                continue
            panel = self.panels[d.slug]
            with self.subTest(desk=d.slug):
                counts = [int(n.replace(",", "")) for n in
                          re.findall(r"· ([\d,]+) records in the corpus", panel)]
                self.assertTrue(counts)
                self.assertEqual(sum(counts), d.record_count)
                self.assertIn('href="archive.html?desk=%s">Browse its %s records'
                              % (d.slug, "{:,}".format(d.record_count)), panel)

    def test_reference_lanes_are_links_not_records(self):
        for d in self.desks:
            refs = self.prov.get(d.slug).references
            panel = self.panels[d.slug]
            with self.subTest(desk=d.slug):
                self.assertEqual("sa-refs" in panel, bool(refs))
                for ref in refs:
                    self.assertRegex(_text(panel), r"%d links? — " % ref.link_count)
                if refs:
                    self.assertIn("Outbound official pages, not IPR archived records.", panel)

    # -- marks and assets ----------------------------------------------------
    def test_glyphs_only_for_a_stored_production_source_type(self):
        families = {"armed_forces_newspaper", "state_linked_newspaper",
                    "ministry_website", "government_republished_release",
                    "official_institutional_news",
                    "maritime_law_enforcement_official_release",
                    "state_news_agency", "military_journal_editorial",
                    "armed_forces_english_portal"}
        types = {s.slug: s.source_type for s in self.source_views}
        for d in self.desks:
            panel = self.panels[d.slug]
            prod = self.prov.get(d.slug).sources_of(EvidenceClass.PRODUCTION)
            want = sum(1 for s in prod if types.get(s.source_slug) in families)
            with self.subTest(desk=d.slug):
                self.assertEqual(self.group(d.slug, "production").count('class="rl-glyph"'), want)
                self.assertEqual(panel.count('class="rl-glyph"'), want)
        self.assertTrue((self.out / "assets/glyphs/sources.svg").is_file())

    def test_flags_on_every_panel_and_no_invented_emblem(self):
        for d in self.desks:
            panel = self.panels[d.slug]
            with self.subTest(desk=d.slug):
                self.assertEqual(panel.count('class="rl-flag"'), 1)
                emblems = re.findall(r'emblems\.svg#([a-z]+)"', panel)
                self.assertLessEqual(set(emblems), {"china", "singapore", "japan",
                                                    "vietnam", "hawaii"})
        for slug in ("korea", "philippines", "indonesia"):
            self.assertNotIn("rl-emblem", self.panels[slug])

    # -- navigation ----------------------------------------------------------
    def test_locate_on_map_only_for_placed_desks(self):
        mapped = set(re.findall(r'id="desk-([a-z-]+)"', self.html))
        for d in self.desks:
            panel = self.panels[d.slug]
            with self.subTest(desk=d.slug):
                if d.slug in mapped:
                    self.assertIn('href="#desk-%s">Locate on map</a>' % d.slug, panel)
                    self.assertNotIn("sa-unplaced", panel)
                else:
                    self.assertNotIn("Locate on map", panel)
                    self.assertIn("Not plotted on the map", panel)

    def test_indonesia_is_navigable_without_a_map_position(self):
        self.assertIn("indonesia", self.panels)
        self.assertIn('href="#atlas-indonesia"', self.atlas)
        self.assertIn('href="indonesia.html"', self.panels["indonesia"])

    def test_every_in_page_and_desk_page_anchor_resolves(self):
        ids = set(re.findall(r'\bid="([^"]+)"', self.html))
        for target in set(re.findall(r'href="#([^"]+)"', self.html)):
            with self.subTest(href=target):
                self.assertIn(target, ids)
        for route, frag in set(re.findall(r'href="([a-z-]+\.html)#([^"]+)"', self.atlas)):
            with self.subTest(href=route + "#" + frag):
                page = (self.out / route).read_text(encoding="utf-8")
                self.assertIn('id="%s"' % frag, page)

    def test_outbound_publisher_links_are_safe_and_honestly_labelled(self):
        for href, label in re.findall(
                r'<a href="(https?://[^"]+)" rel="noopener noreferrer">([^<]+)</a>', self.atlas):
            self.assertIn(htmllib.unescape(label),
                          ("Open the publisher's site", "Open the official publisher page"))
        outbound = re.findall(r'<a href="https?://[^"]+"([^>]*)>', self.atlas)
        self.assertTrue(outbound)
        for attrs in outbound:
            self.assertIn('rel="noopener noreferrer"', attrs)

    # -- budgets and restraint -----------------------------------------------
    def test_no_new_script_motion_or_shadow(self):
        scripts = re.findall(r"<script[^>]*>", self.html)
        self.assertEqual(scripts, ['<script src="desk-map.js" defer>'])
        css = CSS.read_text(encoding="utf-8")
        for banned in ("box-shadow", "animation", "transition", "@keyframes"):
            self.assertNotIn(banned, css)
        self.assertNotIn("<script", self.atlas)

    def test_hub_page_html_and_css_within_300_kb(self):
        sheets = re.findall(r'<link rel="stylesheet" href="([^"]+)"', self.html)
        total = (self.out / "desks.html").stat().st_size + sum(
            (self.out / h).stat().st_size for h in sheets)
        self.assertLessEqual(total, 300_000)
        self.assertTrue((self.out / "desk-atlas.css").is_file())


if __name__ == "__main__":
    unittest.main()
