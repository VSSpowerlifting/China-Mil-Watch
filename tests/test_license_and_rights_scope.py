"""
The licence claim must match the licence files.

This suite exists because the repository regressed once: `README.md` said
"MIT.  See LICENSE." while no `LICENSE` file existed. The claim was checked by
nobody, so it stayed wrong. A reader following it found nothing, and GitHub
could not detect a licence at all.

The tests here are deliberately narrow. They assert three things and no more:

1. the MIT grant exists, unmodified, and names its copyright holder;
2. every file the rights documents point at actually exists;
3. no document overstates the grant — neither by claiming all content is MIT,
   nor by claiming this project owns official government material.

They do not police prose style, section ordering or wording. A licence document
should be editable without a test failing for aesthetic reasons.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LICENSE = ROOT / "LICENSE"
RIGHTS = ROOT / "CONTENT_AND_DATA_RIGHTS.md"
README = ROOT / "README.md"

#: Clauses that make the MIT grant what it is. Paraphrasing any of them changes
#: the licence into something that is not MIT while still being called MIT.
MIT_CLAUSES = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy",
    "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell",
    "The above copyright notice and this permission notice shall be included in all",
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND',
    "IN NO EVENT SHALL THE",
)


def _text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TestTheMitGrantExistsAndIsCanonical(unittest.TestCase):

    def test_a_license_file_exists(self):
        self.assertTrue(
            LICENSE.is_file(),
            "README claims MIT; GitHub and every downstream reader look for a "
            "root LICENSE file. Claiming a licence without shipping one is the "
            "exact regression this suite exists to prevent.")

    def test_it_is_named_as_the_mit_license(self):
        self.assertIn("MIT License", _text(LICENSE))

    def test_the_grant_is_unmodified(self):
        body = _text(LICENSE)
        for clause in MIT_CLAUSES:
            with self.subTest(clause=clause[:48]):
                self.assertIn(
                    clause, body,
                    "MIT clause missing or paraphrased. A modified grant that "
                    "still calls itself MIT misleads every downstream user.")

    def test_it_names_a_copyright_holder(self):
        m = re.search(r"^Copyright \(c\) (\d{4}) (.+)$", _text(LICENSE), re.M)
        self.assertIsNotNone(m, "MIT requires an attributable copyright line.")
        self.assertTrue(m.group(2).strip(), "copyright holder is blank")

    def test_the_grant_carries_no_extra_conditions(self):
        """MIT plus a restriction is not MIT."""
        body = _text(LICENSE).lower()
        for smell in ("non-commercial", "noncommercial", "except", "you may not"):
            with self.subTest(smell=smell):
                self.assertNotIn(smell, body)


class TestTheRightsDocumentIsReachable(unittest.TestCase):

    def test_the_scope_document_exists(self):
        self.assertTrue(RIGHTS.is_file())

    def test_every_local_link_in_the_rights_documents_resolves(self):
        """A rights document that points at a missing file is the old bug."""
        for doc in (RIGHTS, README):
            for target in re.findall(r"\]\(([^)#][^)]*)\)", _text(doc)):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                with self.subTest(doc=doc.name, target=target):
                    self.assertTrue(
                        (ROOT / target.split("#")[0]).exists(),
                        "%s links to %s, which does not exist"
                        % (doc.name, target))


class TestTheClaimIsNotOverbroad(unittest.TestCase):

    def test_the_readme_does_not_claim_bare_mit_for_everything(self):
        """
        The regression was a bare "MIT." standing for the whole repository —
        code, editorial writing and collected ministry documents alike.
        """
        self.assertNotIn(
            "MIT.  See LICENSE.", _text(README),
            "the bare claim is back; it covers editorial work and official "
            "documents that MIT cannot licence")

    def test_the_readme_points_at_the_scope_document(self):
        self.assertIn("CONTENT_AND_DATA_RIGHTS.md", _text(README))

    def test_the_scope_document_reserves_editorial_work(self):
        body = _text(RIGHTS).lower()
        self.assertIn("all rights reserved", body)

    def test_the_scope_document_disclaims_ownership_of_official_material(self):
        body = _text(RIGHTS).lower()
        self.assertTrue(
            "does not" in body and "own" in body,
            "the document must say plainly that official material is not owned "
            "by this project")

    def test_no_document_claims_to_own_government_material(self):
        for doc in (RIGHTS, README, LICENSE):
            body = _text(doc).lower()
            for claim in ("we own the official",
                          "owns the official",
                          "our government documents"):
                with self.subTest(doc=doc.name, claim=claim):
                    self.assertNotIn(claim, body)


if __name__ == "__main__":
    unittest.main()
