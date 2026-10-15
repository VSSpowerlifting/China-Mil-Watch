"""Offline, synthetic Korea original -> held production candidate bridge tests."""
import hashlib
import io
import zipfile
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import stage_korea_production_candidates as stage
from tests.test_korea_private_custody_equivalence import fixture, git


class KoreaProductionCandidateBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, _, self.frozen, self.html, self.hwpx = fixture(self.root)
        self.parent = self.root / "private-output"
        self.parent.mkdir(mode=0o700)
        self.out = self.parent / "held-candidates.json"
        db = self.source / "state/shadow.db"
        con = sqlite3.connect(db)
        for name in ("title_original", "published_date", "language_tag",
                     "first_seen_run"):
            con.execute("ALTER TABLE shadow_records ADD COLUMN " + name + " TEXT")
        rows = con.execute(
            "SELECT source_identity,metadata_json FROM shadow_records ORDER BY source_identity"
        ).fetchall()
        self.hwpx_by_id = {}
        for i, (ident, metadata) in enumerate(rows):
            m = json.loads(metadata)
            korean_text = "Synthetic original " + ident.partition(":")[2]
            # Build five genuine but invented HWPX ZIP/XML byte streams,
            # allowing the same re-extraction gate used on actual MND originals.
            payload = io.BytesIO()
            with zipfile.ZipFile(payload, "w") as archive:
                xml = "<root><p><run><t>" + korean_text + "</t></run></p></root>"
                archive.writestr("Contents/section0.xml", xml.encode("utf-8"))
            binary = payload.getvalue()
            sha = hashlib.sha256(binary).hexdigest()
            (self.source / "state/captures" / (sha + ".bin")).write_bytes(binary)
            self.hwpx_by_id[ident] = sha
            m.update({
                "document_capture_sha256": sha,
                "document_url": "https://www.korea.kr/common/download.do"
                                "?fileId=198565537&tblKey=GMN",
            })
            m.update({
                "issuer": "국방부", "publisher": "대한민국 정책브리핑",
                "publication_kind": "syndicated_press_release",
                "body_scope": "published_hwpx_text",
                "attachments_collected": True,
            })
            con.execute(
                "UPDATE shadow_records SET title_original=?,"
                " published_date=?,language_tag=?,first_seen_run=?,"
                " metadata_json=? WHERE source_identity=?",
                ("합성 원문 제목 " + str(i), "2026-10-13",
                 "ko", "local-native-20261006-korea",
                 json.dumps(m, ensure_ascii=False), ident))
        con.commit()
        con.close()
        git(self.source, "add", "state")
        git(self.source, "commit", "-q", "-m", "fictional typed Korea rows")
        self.current_tip = git(self.source, "rev-parse", "HEAD")

    def test_five_realistically_shaped_synthetic_rows_stay_unpublished(self):
        receipt = stage.create(str(self.source), str(self.out),
                               frozen=self.frozen)
        self.assertEqual(receipt["source_git_commit"], self.current_tip)
        self.assertEqual(receipt["held_production_candidate_count"], 5)
        self.assertEqual(receipt["production_rows_written"], 0)
        self.assertFalse(receipt["source_bodies_exported"])
        data = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(data["source_original_count"], 5)
        self.assertEqual(data["source_git_commit"], self.current_tip)
        self.assertEqual(data["frozen_fourteen_ancestor"], self.frozen)
        self.assertFalse(data["production_import_enabled"])
        self.assertFalse(data["reviewer_identity_authenticated"])
        self.assertFalse(data["per_source_rights_granted"])
        self.assertFalse(data["model_email_or_publication_authorized"])
        ids = []
        for row in data["records"]:
            ids.append(row["source_identity"])
            self.assertEqual(row["authority_tier"], "B")
            self.assertEqual(row["originality"], "syndicated")
            self.assertEqual(row["disposition"],
                             "held_pending_exact_version_human_and_rights_review")
            self.assertEqual(row["canonical_source_url"],
                             stage.URL + row["source_identity"].split(":")[1])
            self.assertEqual(row["original_hwpx_sha256"],
                             self.hwpx_by_id[row["source_identity"]])
            self.assertEqual(row["publisher_html_sha256"], self.html)
            for flag in ("original_text_included", "original_title_included",
                         "original_media_included", "approved_for_production",
                         "approved_for_publication", "approved_for_model_or_email"):
                self.assertIs(row[flag], False)
            for prohibited in ("title_original", "text_original", "metadata_json",
                               "document_url", "summary_english", "body", "title"):
                self.assertNotIn(prohibited, row)
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))
        blob = self.out.read_bytes()
        self.assertNotIn("Synthetic original".encode(), blob)
        self.assertNotIn("합성 원문 제목".encode(), blob)
        self.assertNotIn(b"synthetic-hwpx-no-real-korean-original", blob)
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o600)
        self.assertEqual(stage.digest(blob), receipt["packet_sha256"])

    def update(self, sql, args=()):
        con = sqlite3.connect(self.source / "state/shadow.db")
        try:
            con.execute(sql, args)
            con.commit()
        finally:
            con.close()
        git(self.source, "add", "state")
        git(self.source, "commit", "-q", "-m", "synthetic change")

    def test_future_new_korea_release_is_normalized_but_never_auto_admitted(self):
        new_ident = "korea-policy:156799901"
        body = "Entirely invented future Korean source for rehearsal"
        zipped = io.BytesIO()
        with zipfile.ZipFile(zipped, "w") as archive:
            archive.writestr(
                "Contents/section0.xml",
                ("<root><p><run><t>" + body + "</t></run></p></root>").encode())
        raw = zipped.getvalue()
        docsha = hashlib.sha256(raw).hexdigest()
        (self.source / "state/captures" / (docsha + ".bin")).write_bytes(raw)
        m = {
            "issuer": "국방부", "publisher": "대한민국 정책브리핑",
            "publication_kind": "syndicated_press_release",
            "body_scope": "published_hwpx_text",
            "attachments_collected": True,
            "document_capture_sha256": docsha,
            "document_url": "https://www.korea.kr/common/download.do"
                            "?fileId=198565539&tblKey=GMN",
        }
        con = sqlite3.connect(self.source / "state/shadow.db")
        con.execute(
            "INSERT INTO shadow_records "
            "(source_identity,url,source_slug,title_original,text_original,"
            "published_date,language_tag,metadata_json,content_sha256,"
            "capture_sha256,first_seen_run) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (new_ident, stage.URL + "156799901", stage.SOURCE,
             "가상 국방부 새 보도자료", body, "2026-10-15", "ko",
             json.dumps(m, ensure_ascii=False),
             hashlib.sha256(body.encode()).hexdigest(), self.html,
             "38636466191-1"))
        con.commit()
        con.close()
        git(self.source, "add", "state")
        git(self.source, "commit", "-q", "-m", "fictional later original")
        result = stage.create(str(self.source), str(self.out), frozen=self.frozen)
        self.assertEqual(result["source_original_count"], 6)
        data = json.loads(self.out.read_text())
        latest = next(x for x in data["records"]
                      if x["source_identity"] == new_ident)
        self.assertEqual(latest["original_hwpx_sha256"], docsha)
        self.assertEqual(latest["publisher_posted_date"], "2026-10-15")
        self.assertFalse(latest["approved_for_production"])
        self.assertFalse(latest["approved_for_publication"])
        self.assertFalse(data["production_import_enabled"])

    def test_wrong_issuer_or_document_scope_is_refused(self):
        for field, wrong in [
            ("issuer", "방위사업청"),
            ("publisher", "wrong publisher"),
            ("body_scope", "html-description-only"),
            ("attachments_collected", False),
            ("publication_kind", "original_ministry_release"),
        ]:
            with self.subTest(field=field):
                db = self.source / "state/shadow.db"
                con = sqlite3.connect(db)
                ident, old = con.execute(
                    "SELECT source_identity,metadata_json FROM shadow_records LIMIT 1"
                ).fetchone()
                m = json.loads(old)
                m[field] = wrong
                con.execute("UPDATE shadow_records SET metadata_json=? "
                            "WHERE source_identity=?",
                            (json.dumps(m, ensure_ascii=False), ident))
                con.commit()
                con.close()
                with self.assertRaisesRegex(stage.IntakeHold,
                                            "wrong_korea_publisher_or_content_scope"):
                    stage._normalized(stage._rows(self.source)[0])
                con = sqlite3.connect(db)
                con.execute("UPDATE shadow_records SET metadata_json=? "
                            "WHERE source_identity=?", (old, ident))
                con.commit()
                con.close()

    def test_duplicate_or_changed_identity_and_dates_fail_closed(self):
        for sql in (
            "UPDATE shadow_records SET url='https://example.invalid/'",
            "UPDATE shadow_records SET published_date='2026-15-44'",
            "UPDATE shadow_records SET language_tag='en'",
            "UPDATE shadow_records SET source_slug='dapa'",
            "UPDATE shadow_records SET first_seen_run='../../evil'",
            "UPDATE shadow_records SET content_sha256='f' || substr(content_sha256,2)",
        ):
            with self.subTest(sql=sql[:60]):
                git(self.source, "reset", "--hard", self.current_tip)
                self.update(sql)
                with self.assertRaises(stage.IntakeHold):
                    stage.build(str(self.source), frozen=self.frozen)
        git(self.source, "reset", "--hard", self.current_tip)

    def test_forged_korean_text_even_with_matching_new_digest_fails_original_replay(self):
        # A reviewer cannot trust a shadow DB text+hash pair in isolation.
        # The HWPX bytes must independently re-extract into those same lines.
        text = "A fabricated original claim not present in the HWPX"
        self.update(
            "UPDATE shadow_records SET text_original=?,content_sha256=? "
            "WHERE source_identity=?",
            (text, hashlib.sha256(text.encode()).hexdigest(),
             sorted(self.hwpx_by_id)[0]))
        with self.assertRaisesRegex(stage.IntakeHold,
                                    "korea_original_hwpx_replay_failed"):
            stage.build(str(self.source), frozen=self.frozen)

    def test_corrupted_historical_capture_or_forged_clock_refused(self):
        original = self.source / "state/captures" / (
            next(iter(self.hwpx_by_id.values())) + ".bin")
        original.write_bytes(b"corrupt fictional hwpx")
        with self.assertRaises(stage.IntakeHold):
            stage.build(str(self.source), frozen=self.frozen)
        git(self.source, "reset", "--hard", "HEAD")
        clock = self.source / "state/clock.json"
        x = json.loads(clock.read_text())
        x["day_zero_utc"] = "2026-10-12T00:00:00+00:00"
        clock.write_text(json.dumps(x))
        with self.assertRaises(stage.IntakeHold):
            stage.build(str(self.source), frozen=self.frozen)

    def test_approved_flags_cannot_be_created_by_exporter(self):
        report = stage.build(str(self.source), frozen=self.frozen)
        for item in report["records"]:
            self.assertFalse(item["approved_for_publication"])
            self.assertFalse(item["approved_for_production"])
            self.assertFalse(item["approved_for_model_or_email"])
        self.assertEqual(report["approved_count"], 0)

    def test_output_never_in_repository_or_overwrites_existing(self):
        stage.create(str(self.source), str(self.out), frozen=self.frozen)
        with self.assertRaises(stage.IntakeHold):
            stage.create(str(self.source), str(self.out), frozen=self.frozen)
        with self.assertRaises(stage.IntakeHold):
            stage.create(str(self.source),
                         str(stage.ROOT / "output" / "korea-bridge.json"),
                         frozen=self.frozen)
        with self.assertRaises(stage.IntakeHold):
            stage.create(str(self.source), "relative.json", frozen=self.frozen)
        second = self.root / "world-readable"
        second.mkdir(mode=0o755)
        with self.assertRaises(stage.IntakeHold):
            stage.create(str(self.source), str(second / "bad.json"),
                         frozen=self.frozen)

    def test_cli_explicit_no_send_acknowledgement(self):
        with self.assertRaises(stage.IntakeHold):
            stage.main(["--source-checkout", str(self.source),
                        "--private-output", str(self.out)])
        self.assertFalse(self.out.exists())

    def test_never_wires_korea_into_live_production_or_sunday(self):
        source = (stage.ROOT / "scripts/stage_korea_production_candidates.py").read_text()
        for prohibited in (
            "requests.get", "urllib.request", "anthropic", "smtplib",
            "git push", "INSERT INTO articles", "UPDATE articles",
            "pipeline.run", "send_email", "publish_brief",
        ):
            self.assertNotIn(prohibited, source)
        reg = json.loads((stage.ROOT / "desks/registry.json").read_text())
        korea = next(d for d in reg["desks"] if d["slug"] == "korea")
        self.assertEqual(korea["status"], "shadow")
        self.assertIs(korea["has_production_records"], False)
        self.assertIsNone(korea["manifest"])


if __name__ == "__main__":
    unittest.main()
