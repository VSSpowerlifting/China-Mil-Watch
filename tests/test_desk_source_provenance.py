"""Desk source provenance: five evidence classes, never promoted by accident.

Two halves. The first runs the adapter on the real registry, bindings,
shadow declarations and gated reference loaders and pins what each desk may
truthfully show. The second feeds synthetic inputs to prove every malformed,
missing, duplicated or conflicting input either raises or is recorded and
resolved toward the weaker claim — a conflict may hide a source, never
promote one, and no health is ever attached to anything but a validated
production source.
"""
from __future__ import annotations

import copy
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core import desk_source_provenance as dsp
from core.desk_registry import load_registry
from core.domain import COLLECTING_DESK_STATUSES
from migrations.versions import m0004_source_run_results as m0004
from scripts import desk_source_provenance as gather

ROOT = Path(__file__).resolve().parents[1]
MATRIX_DOC = ROOT / "docs" / "engineering" / "DESK_SOURCE_PROVENANCE_MATRIX_2026-10-13.md"
BEGIN, END = "<!-- BEGIN GENERATED MATRIX -->", "<!-- END GENERATED MATRIX -->"
EC = dsp.EvidenceClass
RS = dsp.RunState


def real_atlas(health=None):
    registry = load_registry()
    bindings = dsp.load_bindings()
    return dsp.build_desk_provenance(
        registry, bindings, dsp.load_shadow_declarations(),
        gather.gather_lane_data(bindings), health, as_of="2026-10-13")


class RealInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry()
        cls.atlas = real_atlas()

    def test_every_desk_in_registry_order(self):
        self.assertEqual([d.slug for d in self.atlas.desks], self.registry.slugs)
        self.assertEqual(len(self.atlas.desks), 8)

    def test_real_inputs_record_no_conflicts(self):
        # Every registry family is bound exactly once, every bound slug is a
        # declared shadow source on its own desk, every lane loads.
        self.assertEqual(self.atlas.conflicts, ())

    def test_limits_and_status_explanations_are_verbatim(self):
        for entry in self.registry:
            desk = self.atlas.get(entry.slug)
            self.assertEqual(desk.limits, tuple(entry.limits))
            self.assertEqual(desk.status_explanation, entry.status_explanation)
            self.assertEqual(desk.status, entry.status)
            self.assertEqual(desk.scope, entry.scope)

    def test_production_is_exactly_the_validated_sources_of_collecting_desks(self):
        expected = {(e.slug, s.slug) for e in self.registry for s in e.sources
                    if s.contract_validated and e.status in COLLECTING_DESK_STATUSES}
        shown = {(d.slug, s.source_slug) for d in self.atlas.desks
                 for s in d.sources_of(EC.PRODUCTION)}
        self.assertEqual(shown, expected)
        self.assertEqual({d for d, _ in shown}, {"china", "singapore"})

    def test_health_only_on_production(self):
        for desk in self.atlas.desks:
            for src in desk.sources:
                if src.evidence_class is EC.PRODUCTION:
                    self.assertIsNotNone(src.health)
                else:
                    self.assertIsNone(src.health, src.name)

    def test_without_health_input_production_reports_no_history(self):
        self.assertFalse(self.atlas.health_supplied)
        for src in self.atlas.get("china").sources:
            self.assertIs(src.health.state, RS.NO_HISTORY)
            self.assertIsNone(src.health.record_count)

    def test_singapore_shadow_duplicate_is_not_a_second_source(self):
        sg = self.atlas.get("singapore")
        self.assertEqual([s.source_slug for s in sg.sources], ["sg_mindef_releases"])
        self.assertIs(sg.sources[0].evidence_class, EC.PRODUCTION)
        self.assertTrue(any(u.startswith("sg_mindef_releases ")
                            for u in self.atlas.undisplayed_shadow_declarations))

    def test_us_desk_shows_no_source_and_dvids_is_not_displayed(self):
        us = self.atlas.get("us-indopacific")
        self.assertEqual(us.sources, ())
        self.assertEqual(us.references, ())
        self.assertTrue(any(u.startswith("us_dvids_indopacom ")
                            for u in self.atlas.undisplayed_shadow_declarations))
        self.assertNotIn("dvids", json.dumps(dsp.atlas_to_dict(self.atlas)["desks"]).lower())

    def test_expected_classes_per_desk(self):
        def classes(slug):
            return {s.source_slug or s.name: s.evidence_class for s in self.atlas.get(slug).sources}
        jp = classes("japan")
        self.assertIs(jp["jp_mod_news_ja"], EC.SHADOW)
        self.assertIs(jp["jp_joint_staff_en"], EC.ACCESS_BLOCKED)
        self.assertIs(jp["jp_mod_press_en"], EC.ACCESS_BLOCKED)
        vn = classes("vietnam")
        self.assertIs(vn["Government portal"], EC.INSUFFICIENT_EVIDENCE)
        self.assertIs(vn["Ministry of Finance"], EC.ACCESS_BLOCKED)
        self.assertIs(vn["vn_national_defence_journal_en"], EC.SHADOW)
        kr = classes("korea")
        self.assertIs(kr["kr_policy_mnd_releases"], EC.SHADOW)
        self.assertEqual(sum(c is EC.PUBLIC_REFERENCE for c in kr.values()), 1)
        idn = classes("indonesia")
        self.assertIs(idn["id_kemhan_news"], EC.SHADOW)
        self.assertEqual(sum(c is EC.PUBLIC_REFERENCE for c in idn.values()), 1)

    def test_shadow_sources_carry_manifest_flags_not_production_flags(self):
        for desk in self.atlas.desks:
            for src in desk.sources_of(EC.SHADOW) + desk.sources_of(EC.ACCESS_BLOCKED):
                self.assertIsNone(src.production_enabled)
                self.assertIsNone(src.authority_tier)
        journal = [s for s in self.atlas.get("vietnam").sources
                   if s.source_slug == "vn_national_defence_journal_en"][0]
        self.assertIs(journal.shadow_enabled, False)
        self.assertIsNotNone(journal.rights_statement)

    def test_reference_lanes_are_links_with_their_own_provenance(self):
        kr = self.atlas.get("korea").references
        self.assertEqual([(g.lane_id, g.link_count) for g in kr], [("korea_mnd_bibliography", 5)])
        self.assertEqual((kr[0].issuer, kr[0].publisher), ("국방부", "대한민국 정책브리핑"))
        idn = {g.lane_id: g for g in self.atlas.get("indonesia").references}
        self.assertEqual(idn["indonesia_berita_index"].link_count, 15)
        self.assertEqual(idn["indonesia_press_index"].link_count, 2)
        self.assertEqual(idn["indonesia_berita_index"].editorial_status,
                         "publisher_links_not_independently_human_reviewed")
        self.assertTrue(idn["indonesia_press_index"].index_url.startswith("https://www.kemhan.go.id/"))
        for desk in self.atlas.desks:
            urls = [r.url for g in desk.references for r in g.entries]
            self.assertEqual(len(urls), len(set(urls)))

    def test_no_workflow_branch_or_schedule_identity_is_emitted(self):
        text = dsp.atlas_to_json(self.atlas)
        raw = json.loads((ROOT / "config" / "shadow_source_workflow_bindings.json").read_text())
        for entry in raw["sources"]:
            # A state branch can share its name with a shadow/ directory, so
            # match whole JSON string values rather than substrings.
            for key in ("state_branch", "workflow", "cron"):
                if entry.get(key):
                    self.assertNotIn(json.dumps(entry[key]), text, key)
            for key in ("workflow", "cron"):
                if entry.get(key):
                    self.assertNotIn(entry[key], text, key)
        for word in ("state_branch", "cron", ".github/workflows"):
            self.assertNotIn(word, text)

    def test_build_is_byte_deterministic(self):
        self.assertEqual(dsp.atlas_to_json(self.atlas), dsp.atlas_to_json(real_atlas()))

    def test_committed_matrix_matches_regenerated_output(self):
        doc = MATRIX_DOC.read_text(encoding="utf-8")
        self.assertEqual(doc.count(BEGIN), 1)
        self.assertEqual(doc.count(END), 1)
        block = doc.split(BEGIN, 1)[1].split(END, 1)[0].strip("\n") + "\n"
        self.assertEqual(block, dsp.render_matrix(self.atlas),
                         "regenerate with scripts/desk_source_provenance.py --no-health --matrix -")

    def test_core_is_pure(self):
        text = (ROOT / "core" / "desk_source_provenance.py").read_text(encoding="utf-8")
        for banned in ("datetime", "date.today", "sqlite3", "urllib", "requests",
                       "generate_preview", "geography", "subprocess"):
            self.assertNotIn(banned, text)


# ── Synthetic fixtures ───────────────────────────────────────────────────────

def src(slug, *, validated=True, enabled=True, lang="en", access="html"):
    return SimpleNamespace(slug=slug, display_name=slug.upper(), base_url="https://example.test/" + slug,
                           language_tag=lang, authority_tier="primary", access_method=access,
                           enabled=enabled, contract_validated=validated, notes=None)


def desk(slug, status="shadow", sources=(), families=(), limits=("Limit one.",), research=True):
    return SimpleNamespace(
        slug=slug, name=slug.title() + " Desk", route="desks/%s.html" % slug, scope="Scope.",
        status=status, status_label=status.title(), status_explanation="Because %s." % slug,
        public=True, has_production_records=status == "live", limits=list(limits),
        sources=list(sources), manifest_path="desks/%s/manifest.json" % slug,
        research={"source_families": [dict(f) for f in families],
                  "blockers": [["Block", "Text"]]} if research else None,
        qualification=None)


def fam(name, url=None):
    out = {"name": name, "format": "fmt", "note": "note"}
    if url:
        out["publisher_url"] = url
    return out


def binding(name, cls="shadow", slug=None, lanes=(), basis="Recorded."):
    return {"name": name, "evidence_class": cls, "source_slug": slug,
            "reference_lanes": list(lanes), "basis": basis}


LANES = {"lane_a": {"loader": "indonesia_official_index", "kind": "official_index",
                    "filter_by_source_slug": False},
         "lane_r": {"loader": "reviewed_links_vietnam", "kind": "reviewed_links",
                    "filter_by_source_slug": True}}


def raw_bindings(desks):
    return {"schema": dsp.BINDINGS_SCHEMA, "reference_lanes": copy.deepcopy(LANES), "desks": desks}


def decl(slug, desk_id="alpha", enabled=True, tags=("xx",)):
    return dsp.ShadowDeclaration(slug=slug, manifest="shadow/%s/manifest.json" % desk_id,
                                 desk_id=desk_id, display_name=slug, base_url=None,
                                 language_tags=tuple(tags), access_method="html",
                                 shadow_enabled=enabled, rights_statement=None)


def ref(i, url=None, slug=None):
    return dsp.PublicReference(id="r%d" % i, url=url or "https://pub.test/%d" % i,
                               title_original="T%d" % i, published_date="2026-10-0%d" % i,
                               language="xx", source_slug=slug)


def lane(*entries):
    return dsp.LaneData(schema="s/1", publisher="P", issuer=None, editorial_status=None,
                        snapshot_date=None, entries=tuple(entries))


def build(registry, desks_raw, shadow=None, lanes=None, health=None):
    return dsp.build_desk_provenance(registry, dsp.parse_bindings(raw_bindings(desks_raw)),
                                     shadow or {}, lanes or {}, health, as_of="2026-10-13")


def row(status="ok", is_failure=0, new=1, run=7, at="2026-10-12 21:00:00"):
    return dsp.RunRow(status, is_failure, new, run, at)


class BindingsValidation(unittest.TestCase):
    def base(self):
        return raw_bindings({"alpha": {"shadow_desk_ids": ["alpha"],
                                       "families": [binding("F", slug="a_one", lanes=["lane_a"])]}})

    def assertRejects(self, raw, pattern):
        with self.assertRaisesRegex(dsp.ProvenanceInputError, pattern):
            dsp.parse_bindings(raw)

    def test_valid_bindings_parse(self):
        b = dsp.parse_bindings(self.base())
        self.assertEqual(b.desks["alpha"].families[0].evidence_class, EC.SHADOW)

    def test_structural_malformation_raises(self):
        self.assertRejects([], "must be an object")
        raw = self.base(); raw["schema"] = "other/1"; self.assertRejects(raw, "schema")
        raw = self.base(); raw["extra"] = 1; self.assertRejects(raw, "top-level")
        raw = self.base(); del raw["desks"]; self.assertRejects(raw, "top-level")
        raw = self.base(); raw["reference_lanes"]["lane_a"]["loader"] = "web"
        self.assertRejects(raw, "unknown loader")
        raw = self.base(); raw["reference_lanes"]["lane_a"]["kind"] = "archive"
        self.assertRejects(raw, "unknown kind")
        raw = self.base(); raw["reference_lanes"]["lane_r"]["loader"] = "indonesia_official_index"
        self.assertRejects(raw, "share one loader")

    def test_family_field_errors_raise(self):
        cases = [
            (lambda f: f.update(evidence_class="production"), "production cannot be assigned"),
            (lambda f: f.update(evidence_class="significant"), "unknown evidence class"),
            (lambda f: f.update(basis="  "), "needs a basis"),
            (lambda f: f.update(name=" F"), "trimmed"),
            (lambda f: f.update(source_slug=3), "string or null"),
            (lambda f: f.update(reference_lanes=["missing"]), "undeclared lane"),
            (lambda f: f.update(reference_lanes=["lane_a", "lane_a"]), "repeats a lane"),
            (lambda f: f.update(rights="granted"), "unexpected fields"),
            (lambda f: f.pop("basis"), "unexpected fields"),
        ]
        for mutate, pattern in cases:
            raw = self.base()
            mutate(raw["desks"]["alpha"]["families"][0])
            self.assertRejects(raw, pattern)

    def test_duplicates_raise(self):
        raw = self.base()
        raw["desks"]["alpha"]["families"].append(binding("F"))
        self.assertRejects(raw, "twice")
        raw = self.base()
        raw["desks"]["alpha"]["families"].append(binding("G", slug="a_one"))
        self.assertRejects(raw, "bound twice")
        raw = self.base()
        raw["desks"]["beta"] = {"shadow_desk_ids": ["alpha"], "families": []}
        self.assertRejects(raw, "bound to two desks")

    def test_slug_filtered_lane_needs_a_slug(self):
        raw = self.base()
        raw["desks"]["alpha"]["families"][0].update(source_slug=None, reference_lanes=["lane_r"],
                                                    evidence_class="public_reference")
        self.assertRejects(raw, "needs a source slug")

    def test_file_loader_rejects_duplicate_keys_and_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text('{"schema": "a", "schema": "b"}', encoding="utf-8")
            with self.assertRaisesRegex(dsp.ProvenanceInputError, "duplicate JSON key"):
                dsp.load_bindings(path)
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(dsp.ProvenanceInputError, "not valid JSON"):
                dsp.load_bindings(path)
            with self.assertRaisesRegex(dsp.ProvenanceInputError, "absent"):
                dsp.load_bindings(Path(tmp) / "missing.json")


class ShadowManifestParsing(unittest.TestCase):
    def manifest(self, **source):
        base = {"slug": "a_one", "display_name": "A", "enabled": True, "language_tags": ["xx"]}
        base.update(source)
        return {"_shadow": True, "desk": {"desk_id": "alpha"}, "sources": [base], "rights": "Verbatim."}

    def test_parses_public_safe_fields_and_rights_verbatim(self):
        d = dsp.parse_shadow_manifest("a_one", "shadow/a/manifest.json", self.manifest())
        self.assertEqual((d.desk_id, d.language_tags, d.rights_statement), ("alpha", ("xx",), "Verbatim."))
        single = self.manifest(language_tag="yy")
        del single["sources"][0]["language_tags"]
        self.assertEqual(dsp.parse_shadow_manifest("a_one", "m", single).language_tags, ("yy",))
        none = self.manifest()
        del none["sources"][0]["language_tags"]
        self.assertEqual(dsp.parse_shadow_manifest("a_one", "m", none).language_tags, ())

    def test_malformed_manifests_raise(self):
        bad = [
            ({**self.manifest(), "_shadow": False}, "_shadow"),
            ({**self.manifest(), "desk": {}}, "desk_id"),
            (self.manifest(enabled="yes"), "boolean"),
            (self.manifest(language_tag="xx"), "both language_tag"),
            (self.manifest(display_name=""), "display_name"),
            ({**self.manifest(), "sources": []}, "exactly once"),
        ]
        twice = self.manifest()
        twice["sources"].append(dict(twice["sources"][0]))
        bad.append((twice, "exactly once"))
        for raw, pattern in bad:
            with self.assertRaisesRegex(dsp.ProvenanceInputError, pattern):
                dsp.parse_shadow_manifest("a_one", "m", raw)

    def test_declarations_must_live_under_shadow_and_not_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "shadow" / "a").mkdir(parents=True)
            (root / "shadow" / "a" / "manifest.json").write_text(json.dumps(self.manifest()))
            path = root / "b.json"

            def write(entries):
                path.write_text(json.dumps({"schema": dsp.SHADOW_BINDINGS_SCHEMA, "sources": entries}))

            write([{"source_slug": "a_one", "manifest": "shadow/a/manifest.json"}])
            self.assertEqual(set(dsp.load_shadow_declarations(path, root)), {"a_one"})
            write([{"source_slug": "a_one", "manifest": "desks/a/manifest.json"}])
            with self.assertRaisesRegex(dsp.ProvenanceInputError, "under shadow/"):
                dsp.load_shadow_declarations(path, root)
            write([{"source_slug": "a_one", "manifest": "shadow/../desks/a.json"}])
            with self.assertRaisesRegex(dsp.ProvenanceInputError, "under shadow/"):
                dsp.load_shadow_declarations(path, root)
            write([{"source_slug": "a_one", "manifest": "shadow/a/manifest.json"}] * 2)
            with self.assertRaisesRegex(dsp.ProvenanceInputError, "declared twice"):
                dsp.load_shadow_declarations(path, root)


class BuilderConflicts(unittest.TestCase):
    def test_registry_and_bindings_must_cover_the_same_desks(self):
        with self.assertRaisesRegex(dsp.ProvenanceInputError, "missing"):
            build([desk("alpha"), desk("beta")], {"alpha": {"shadow_desk_ids": [], "families": []}})
        with self.assertRaisesRegex(dsp.ProvenanceInputError, "repeats a desk"):
            build([desk("alpha"), desk("alpha")], {"alpha": {"shadow_desk_ids": [], "families": []}})
        with self.assertRaisesRegex(dsp.ProvenanceInputError, "as_of"):
            dsp.build_desk_provenance([], dsp.parse_bindings(raw_bindings({})), {}, {}, None, as_of="now")

    def test_unbound_family_is_insufficient_and_recorded(self):
        atlas = build([desk("alpha", families=[fam("F")])],
                      {"alpha": {"shadow_desk_ids": ["alpha"], "families": []}})
        (s,) = atlas.get("alpha").sources
        self.assertIs(s.evidence_class, EC.INSUFFICIENT_EVIDENCE)
        self.assertIsNone(s.basis)
        self.assertRegex(atlas.conflicts[0], "no reviewed binding")

    def test_binding_for_unknown_family_is_ignored_and_recorded(self):
        atlas = build([desk("alpha")], {"alpha": {"shadow_desk_ids": [], "families": [
            binding("Ghost", cls="access_blocked")]}})
        self.assertEqual(atlas.get("alpha").sources, ())
        self.assertRegex(atlas.conflicts[0], "does not declare")

    def test_repeated_registry_family_is_shown_once(self):
        atlas = build([desk("alpha", families=[fam("F"), fam("F")])],
                      {"alpha": {"shadow_desk_ids": [], "families": [binding("F", cls="access_blocked")]}})
        self.assertEqual(len(atlas.get("alpha").sources), 1)
        self.assertRegex(atlas.conflicts[0], "twice")

    def test_shadow_binding_of_a_production_slug_is_downgraded_without_health(self):
        live = desk("alpha", status="live", sources=[src("p_one")], families=[fam("F")])
        health = {"p_one": dsp.HealthInput(True, row())}
        atlas = build([live], {"alpha": {"shadow_desk_ids": ["alpha"],
                                         "families": [binding("F", slug="p_one")]}},
                      shadow={"p_one": decl("p_one")}, health=health)
        prod, shadow_fam = atlas.get("alpha").sources
        self.assertIs(prod.evidence_class, EC.PRODUCTION)
        self.assertIs(prod.health.state, RS.COLLECTED_NEW)
        self.assertIs(shadow_fam.evidence_class, EC.INSUFFICIENT_EVIDENCE)
        self.assertIsNone(shadow_fam.health)
        self.assertIsNone(shadow_fam.source_slug)
        self.assertRegex(atlas.conflicts[0], "production slug")

    def test_undeclared_or_misplaced_shadow_slug_is_downgraded(self):
        families = {"alpha": {"shadow_desk_ids": ["alpha"], "families": [binding("F", slug="a_one")]}}
        atlas = build([desk("alpha", families=[fam("F")])], families)
        self.assertIs(atlas.get("alpha").sources[0].evidence_class, EC.INSUFFICIENT_EVIDENCE)
        self.assertRegex(atlas.conflicts[0], "no shadow declaration")
        atlas = build([desk("alpha", families=[fam("F")])], families,
                      shadow={"a_one": decl("a_one", desk_id="beta")})
        s = atlas.get("alpha").sources[0]
        self.assertIs(s.evidence_class, EC.INSUFFICIENT_EVIDENCE)
        self.assertEqual(s.language_tags, ())
        self.assertRegex(atlas.conflicts[0], "desk id beta")

    def test_shadow_class_without_slug_is_downgraded(self):
        atlas = build([desk("alpha", families=[fam("F")])],
                      {"alpha": {"shadow_desk_ids": [], "families": [binding("F")]}})
        self.assertIs(atlas.get("alpha").sources[0].evidence_class, EC.INSUFFICIENT_EVIDENCE)

    def test_public_reference_needs_a_link_or_lane(self):
        bound = {"alpha": {"shadow_desk_ids": [], "families": [binding("F", cls="public_reference")]}}
        atlas = build([desk("alpha", families=[fam("F")])], bound)
        self.assertIs(atlas.get("alpha").sources[0].evidence_class, EC.INSUFFICIENT_EVIDENCE)
        atlas = build([desk("alpha", families=[fam("F", url="https://pub.test/")])], bound)
        self.assertIs(atlas.get("alpha").sources[0].evidence_class, EC.PUBLIC_REFERENCE)
        self.assertEqual(atlas.conflicts, ())

    def test_validated_source_on_non_collecting_desk_is_never_production(self):
        for status in ("planned", "research", "shadow", "paused", "access_blocked"):
            atlas = build([desk("alpha", status=status, sources=[src("p_one")])],
                          {"alpha": {"shadow_desk_ids": [], "families": []}},
                          health={"p_one": dsp.HealthInput(True, row())})
            (s,) = atlas.get("alpha").sources
            self.assertIs(s.evidence_class, EC.INSUFFICIENT_EVIDENCE, status)
            self.assertIsNone(s.health)
            self.assertEqual(atlas.unmatched_health_slugs, ("p_one",))

    def test_unbound_registry_shadow_source_is_recorded(self):
        atlas = build([desk("alpha", sources=[src("a_one", validated=False)])],
                      {"alpha": {"shadow_desk_ids": ["alpha"], "families": []}})
        (s,) = atlas.get("alpha").sources
        self.assertIs(s.evidence_class, EC.INSUFFICIENT_EVIDENCE)
        self.assertRegex(atlas.conflicts[0], "not bound")

    def test_shadow_source_is_never_given_health(self):
        atlas = build([desk("alpha", sources=[src("a_one", validated=False)], families=[fam("F")])],
                      {"alpha": {"shadow_desk_ids": ["alpha"], "families": [binding("F", slug="a_one")]}},
                      shadow={"a_one": decl("a_one", enabled=False)},
                      health={"a_one": dsp.HealthInput(True, row())})
        (s,) = atlas.get("alpha").sources
        self.assertIs(s.evidence_class, EC.SHADOW)
        self.assertIsNone(s.health)
        self.assertIs(s.shadow_enabled, False)
        self.assertEqual(s.language_tags, ("xx",))
        self.assertEqual(atlas.unmatched_health_slugs, ("a_one",))
        self.assertEqual(atlas.conflicts, ())

    def test_missing_research_and_metadata_stay_unknown(self):
        atlas = build([desk("alpha", research=False, limits=())],
                      {"alpha": {"shadow_desk_ids": [], "families": []}})
        d = atlas.get("alpha")
        self.assertEqual((d.sources, d.blockers, d.limits, d.observed_volume), ((), (), (), ()))
        self.assertIsNone(d.observed_volume_subject)
        self.assertIsNone(d.qualification)

    def test_malformed_registry_research_raises(self):
        broken = desk("alpha")
        broken.research = {"source_families": [{"format": "no name"}]}
        with self.assertRaisesRegex(dsp.ProvenanceInputError, "needs a name"):
            build([broken], {"alpha": {"shadow_desk_ids": [], "families": []}})
        broken.research = {"blockers": [["only title"]]}
        with self.assertRaisesRegex(dsp.ProvenanceInputError, "string pairs"):
            build([broken], {"alpha": {"shadow_desk_ids": [], "families": []}})

    def test_reference_lanes_filter_dedupe_and_fail_closed(self):
        registry = [desk("alpha", sources=[src("a_one", validated=False)], families=[fam("F")])]
        bound = {"alpha": {"shadow_desk_ids": ["alpha"],
                           "families": [binding("F", slug="a_one", lanes=["lane_a", "lane_r"])]}}
        shadow = {"a_one": decl("a_one")}
        lanes = {"lane_a": lane(ref(1), ref(2)),
                 "lane_r": lane(ref(3, url="https://pub.test/1", slug="a_one"),
                                ref(4, slug="a_one"), ref(5, slug="other"))}
        atlas = build(registry, bound, shadow, lanes)
        groups = {g.lane_id: [r.id for r in g.entries] for g in atlas.get("alpha").references}
        self.assertEqual(groups, {"lane_a": ["r1", "r2"], "lane_r": ["r4"]})
        self.assertRegex(atlas.conflicts[0], "repeats a URL")
        self.assertEqual(atlas.get("alpha").sources[0].reference_lanes, ("lane_a", "lane_r"))
        atlas = build(registry, bound, shadow, {"lane_a": None})
        self.assertEqual(atlas.get("alpha").references, ())
        self.assertEqual(len(atlas.conflicts), 2)
        self.assertTrue(all("unavailable" in c for c in atlas.conflicts))

    def test_reference_links_never_become_a_record_count(self):
        live = desk("alpha", status="live", sources=[src("p_one")])
        atlas = build([live], {"alpha": {"shadow_desk_ids": [], "families": []}},
                      lanes={"lane_a": lane(ref(1))})
        self.assertIsNone(atlas.get("alpha").sources[0].health.record_count)


class HealthClassification(unittest.TestCase):
    def state(self, latest, available=True):
        return dsp.classify_health(dsp.HealthInput(available, latest)).state

    def test_four_contract_states_are_distinguished(self):
        self.assertIs(self.state(row("ok", 0, 3)), RS.COLLECTED_NEW)
        for status in ("ok", "ok_no_publications", "ok_all_duplicates", "ok_all_filtered"):
            self.assertIs(self.state(row(status, 0, 0)), RS.COLLECTED_NO_NEW, status)
        for status in ("fetch_failure", "listing_failure", "access_challenged", "timeout"):
            self.assertIs(self.state(row(status, 1, 0)), RS.COLLECTION_FAILED, status)
        self.assertIs(self.state(None), RS.NO_HISTORY)
        self.assertIs(self.state(row(), available=False), RS.NO_HISTORY)
        self.assertIs(dsp.classify_health(None).state, RS.NO_HISTORY)

    def test_not_implemented_and_disabled_are_not_no_new_publications(self):
        self.assertIs(self.state(row("not_implemented", 0, 0)), RS.NOT_ATTEMPTED)
        self.assertIs(self.state(row("skipped_disabled", 0, 0)), RS.NOT_ATTEMPTED)

    def test_disagreeing_failure_signals_report_failure(self):
        for latest in (row("ok", 1, 0), row("fetch_failure", 0, 0)):
            h = dsp.classify_health(dsp.HealthInput(True, latest))
            self.assertIs(h.state, RS.COLLECTION_FAILED)
            self.assertRegex(h.reason, "disagree")

    def test_malformed_or_contradictory_rows_are_unknown(self):
        for latest in (row(None), row("ok", None), row("ok", True, 1), row("ok", 2, 1),
                       row("ok", 0, -1), row("ok", 0, "3"), row("ok", 0, True),
                       row("made_up_status", 0, 0), row("ok_no_publications", 0, 2),
                       row("ok_all_duplicates", 0, 1)):
            self.assertIs(self.state(latest), RS.NO_HISTORY, latest)

    def test_fields_are_carried_only_when_well_typed(self):
        h = dsp.classify_health(dsp.HealthInput(True, row("ok", 0, 0, run="7", at=5),
                                                last_new_document_at="2026-10-10", record_count=4))
        self.assertIs(h.state, RS.COLLECTED_NO_NEW)
        self.assertEqual((h.scrape_run_id, h.completed_at, h.raw_status), (None, None, "ok"))
        self.assertEqual((h.last_new_document_at, h.record_count), ("2026-10-10", 4))

    def test_report_parsing_is_strict(self):
        good = {"per_source_history_available": True, "sources": [
            {"source_slug": "p_one", "articles_total": 9, "last_new_document_at": None,
             "latest_run_result": {"status": "ok", "is_failure": 0, "new_documents": 2,
                                   "scrape_run_id": 5, "completed_at": "2026-10-12"}}]}
        parsed = dsp.health_inputs_from_report(good)
        self.assertIs(dsp.classify_health(parsed["p_one"]).state, RS.COLLECTED_NEW)
        self.assertEqual(parsed["p_one"].record_count, 9)
        for broken, pattern in (
                ([], "object"), ({"sources": []}, "boolean"),
                ({"per_source_history_available": True, "sources": {}}, "list"),
                ({"per_source_history_available": True, "sources": [{}]}, "source_slug"),
                ({"per_source_history_available": True,
                  "sources": [{"source_slug": "x", "latest_run_result": "ok"}]}, "object"),
                ({"per_source_history_available": True,
                  "sources": [{"source_slug": "x"}, {"source_slug": "x"}]}, "repeats")):
            with self.assertRaisesRegex(dsp.ProvenanceInputError, pattern):
                dsp.health_inputs_from_report(broken)
        odd = copy.deepcopy(good)
        odd["sources"][0]["articles_total"] = True
        self.assertIsNone(dsp.health_inputs_from_report(odd)["p_one"].record_count)


class HealthFromDatabase(unittest.TestCase):
    def conn(self, with_table=True):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE scrape_runs (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT)")
        conn.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, source_id INTEGER)")
        if with_table:
            m0004.up(conn)
        return conn

    def add(self, conn, run, slug, status, failure, new, at):
        conn.execute("INSERT OR IGNORE INTO scrape_runs (id) VALUES (?)", (run,))
        conn.execute("INSERT INTO source_run_results (scrape_run_id, source_slug, status, is_failure, "
                     "new_documents, completed_at) VALUES (?,?,?,?,?,?)",
                     (run, slug, status, failure, new, at))

    def test_absent_table_means_no_history(self):
        health = gather.health_from_connection(self.conn(with_table=False), ["p_one"])
        self.assertFalse(health["p_one"].history_available)
        self.assertIs(dsp.classify_health(health["p_one"]).state, RS.NO_HISTORY)

    def test_latest_row_and_aggregates(self):
        conn = self.conn()
        conn.execute("INSERT INTO sources (id, slug) VALUES (1, 'p_one')")
        conn.executemany("INSERT INTO articles (source_id) VALUES (?)", [(1,), (1,)])
        self.add(conn, 1, "p_one", "ok", 0, 4, "2026-10-01")
        self.add(conn, 2, "p_one", "not_implemented", 0, 0, "2026-10-05")
        self.add(conn, 3, "p_one", "fetch_failure", 1, 0, "2026-10-09")
        self.add(conn, 3, "p_two", "ok_all_duplicates", 0, 0, "2026-10-09")
        health = gather.health_from_connection(conn, ["p_one", "p_two", "p_three"])
        one = dsp.classify_health(health["p_one"])
        self.assertIs(one.state, RS.COLLECTION_FAILED)
        self.assertEqual((one.scrape_run_id, one.raw_status), (3, "fetch_failure"))
        self.assertEqual(one.last_new_document_at, "2026-10-01")
        # not_implemented has is_failure=0 but is not a successful collection.
        self.assertEqual(one.last_successful_collection_at, "2026-10-01")
        self.assertEqual(one.record_count, 2)
        self.assertIs(dsp.classify_health(health["p_two"]).state, RS.COLLECTED_NO_NEW)
        self.assertIsNone(health["p_two"].last_new_document_at)
        self.assertIs(dsp.classify_health(health["p_three"]).state, RS.NO_HISTORY)
        self.assertEqual(health["p_three"].record_count, 0)


class Serialization(unittest.TestCase):
    def test_json_is_sorted_and_carries_schema(self):
        atlas = build([desk("alpha", status="live", sources=[src("p_one")])],
                      {"alpha": {"shadow_desk_ids": [], "families": []}})
        data = json.loads(dsp.atlas_to_json(atlas))
        self.assertEqual(data["schema"], dsp.ATLAS_SCHEMA)
        self.assertEqual(data["desks"][0]["sources"][0]["evidence_class"], "production")
        self.assertNotIn("health", data["desks"][0]["sources"][0])
        self.assertEqual(dsp.atlas_to_internal_dict(atlas)["desks"][0]
                         ["sources"][0]["health"]["state"], "no_history")
        self.assertEqual(dsp.atlas_to_json(atlas), json.dumps(data, ensure_ascii=False, indent=2,
                                                              sort_keys=True) + "\n")

    def test_public_json_excludes_private_shadow_diagnostics(self):
        atlas = real_atlas()
        public = dsp.atlas_to_dict(atlas)
        internal = dsp.atlas_to_internal_dict(atlas)
        self.assertEqual(public["schema"], dsp.ATLAS_SCHEMA)
        self.assertEqual(len(public["desks"]), 8)
        self.assertIn("undisplayed_shadow_declarations", internal)
        self.assertTrue(any("us_dvids_indopacom" in x for x in
                            internal["undisplayed_shadow_declarations"]))
        for key in ("undisplayed_shadow_declarations", "unmatched_health_slugs",
                    "conflicts", "health_supplied"):
            self.assertNotIn(key, public)
        raw = dsp.atlas_to_json(atlas)
        for fragment in ("us_dvids_indopacom", "shadow/jp_mod/", "shadow/id_kemhan/",
                         "manifest.json", "scrape_run_id", "source_slug",
                         "fixtures", "rights_statement",
                         "shadow_enabled", "production_enabled", "\"basis\"",
                         "\"lane_id\"", "\"conflicts\""):
            self.assertNotIn(fragment, raw)
        self.assertIn("shadow/jp_mod/", dsp.atlas_to_internal_json(atlas))
        self.assertNotIn("rights_statement", raw)
        self.assertNotIn('"note"', raw)
        self.assertIn("status_explanation", raw)

    def test_public_projection_preserves_approved_reference_links_and_limitations(self):
        public = dsp.atlas_to_dict(real_atlas())
        by_slug = {d["slug"]: d for d in public["desks"]}
        for entry in load_registry():
            if not entry.public:
                self.assertNotIn(entry.slug, by_slug)
                continue
            d = by_slug[entry.slug]
            self.assertEqual(d["limits"], list(entry.limits))
            self.assertEqual(d["status_explanation"], entry.status_explanation)
        kr = by_slug["korea"]["references"]
        self.assertEqual(len(kr), 1)
        self.assertEqual(len(kr[0]["entries"]), 5)
        self.assertEqual(kr[0]["issuer"], "국방부")
        idn = by_slug["indonesia"]["references"]
        self.assertEqual(sum(len(group["entries"]) for group in idn), 17)
        for desk in public["desks"]:
            for source in desk["sources"]:
                self.assertNotIn("health", source)
                self.assertNotIn("basis", source)
                self.assertNotIn("source_slug", source)
                self.assertNotIn("note", source)
                self.assertNotIn("rights_statement", source)

    def test_public_projection_drops_nonpublic_desk(self):
        private = desk("research-room", status="shadow")
        private.public = False
        atlas = build([private], {"research-room": {"shadow_desk_ids": [], "families": []}})
        self.assertEqual(dsp.atlas_to_dict(atlas)["desks"], [])
        self.assertEqual(len(dsp.atlas_to_internal_dict(atlas)["desks"]), 1)

    def test_matrix_escapes_cells_and_omits_health_values(self):
        atlas = build([desk("alpha", status="live", sources=[src("p_one")],
                            families=[fam("A | B")])],
                      {"alpha": {"shadow_desk_ids": [], "families": [binding("A | B", cls="access_blocked")]}},
                      health={"p_one": dsp.HealthInput(True, row(run=99, at="2026-10-12 21:00:00"))})
        text = dsp.render_matrix(atlas)
        self.assertIn("A \\| B", text)
        self.assertNotIn("2026-10-12", text)
        self.assertNotIn("collected_new", text)
        self.assertIsNone(re.search(r"\b99\b", text))


if __name__ == "__main__":
    unittest.main()
