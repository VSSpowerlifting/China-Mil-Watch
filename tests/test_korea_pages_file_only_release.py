"""Contract for narrow, owner-approved Korea-only Pages recovery release."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / ".github/workflows/korea_pages_file_only_release.yml"


class KoreaFileOnlyPagesTests(unittest.TestCase):
    def test_release_is_owner_approved_and_canonical_fourteen_links(self):
        from core.korea_public_bibliography import load_public_korea_links
        from core.korea_additional_public_links import load_additional_korea_official_links
        old = load_public_korea_links()
        new = load_additional_korea_official_links()
        self.assertEqual((len(old),len(new)), (5,9))
        self.assertEqual(len({x["source_identity"] for x in old+new}),14)
        self.assertEqual(len([x for x in new if x["editorial_hold"]]),1)
        self.assertEqual(next(x["source_identity"] for x in new
                              if x["editorial_hold"]),
                         "korea-policy:156785161")
        self.assertEqual(set(x["source_identity"].split(":")[-1]
                             for x in new), set(json.loads(
            (ROOT/"research/korea_additional_public_official_links_2026-10-15.json")
            .read_text())["source_ids"]))

    def test_only_korea_html_is_staged_on_each_branch(self):
        text = FLOW.read_text()
        self.assertIn("ref: main", text)
        self.assertIn("ref: gh-pages", text)
        self.assertIn("path: korea-existing-pages", text)
        self.assertIn("git add -- output/korea.html", text)
        self.assertIn('test "$staged" = "output/korea.html"', text)
        self.assertIn("git add -- korea.html", text)
        self.assertIn('test "$staged" = "korea.html"', text)
        self.assertIn("git push origin HEAD:main", text)
        self.assertIn("git push origin HEAD:gh-pages", text)
        self.assertIn("Main moved; stop rather than write from a stale render", text)
        self.assertIn("Pages moved; refuse a stale or broader overwrite", text)
        self.assertIn("sha256sum -c", text)
        self.assertIn("python scripts/verify_db_current.py", text)
        self.assertIn("python scripts/validate_output.py", text)
        self.assertNotIn("publish_dir: ./output", text)
        self.assertNotIn("peaceiris/actions-gh-pages@", text)
        self.assertNotIn("git push --force", text)
        self.assertNotIn("git add -A -- output/", text)

    def test_website_identity_and_scope_checks_present(self):
        text = FLOW.read_text()
        for snippet in (
            "html.count('data-korea-public-link=')==5",
            "html.count('data-korea-additional-link=')==9",
            "newsId=')==14",
            "unresolved excavation-year discrepancy",
            "not IPR archived records",
            "KOGL Type 1",
            "download.do?fileId=",
            'kr["status"]=="shadow"',
            'kr["has_production_records"] is False',
            "sha256sum pla_watch.db",
            "git diff --exit-code -- pla_watch.db",
            "git diff --name-only -- output/",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)
        self.assertNotIn("anthropic.messages", text)
        self.assertNotIn("smtplib", text)
        self.assertNotIn("KoreaPolicyAdapter(", text)

    def test_never_uses_unreviewed_broad_push_trigger_or_schedule(self):
        text = FLOW.read_text()
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("branches: [main]", text)
        self.assertIn("paths:", text)
        self.assertIn(".github/workflows/korea_pages_file_only_release.yml",text)
        self.assertNotIn("  schedule:", text)
        self.assertIn("group: daily-update", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertNotIn("  issues:", text)
        self.assertNotIn("  repository_dispatch:", text)
        registry=json.loads((ROOT/"desks/registry.json").read_text())
        kr=next(d for d in registry["desks"] if d["slug"]=="korea")
        self.assertIs(kr["public"],True)
        self.assertIs(kr["has_production_records"],False)
        self.assertEqual(kr["status"],"shadow")


if __name__=="__main__":
    unittest.main()
