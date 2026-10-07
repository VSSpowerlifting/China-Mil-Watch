"""Offline tests replay exact official captures; never connect to a source."""
import hashlib
import io
import json
import socket
import sqlite3
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from core.collection import status as st
from core.collection.contract import CollectionWindow, CandidateReference
from core.manifests import load_all_desks, load_manifest
from scraper.sources import desk_shadow_http as http
from scraper.sources.id_kemhan import KemhanAdapter, LISTING as ID_LISTING, article_url as id_url
from scraper.sources.kr_policy_briefing import KoreaPolicyAdapter, LISTING as KR_LISTING, article_url as kr_url, hwpx_text
from scripts import shadow_collect_desk as runner
from scripts import review_desk_shadow as reviewer

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/indonesia_korea"
ROWS = json.loads((FIX / "requests.json").read_text())
TARGET = date(2026, 10, 6)


def fixture(name):
    return (FIX / name).read_bytes()


class Response:
    def __init__(self, url, payload, status=200, ctype="text/html; charset=UTF-8", headers=None):
        self.url, self.payload, self.status_code = url, payload, status
        self.headers = {"Content-Type": ctype, **(headers or {})}

    def iter_content(self, chunk_size):
        for pos in range(0, len(self.payload), chunk_size):
            yield self.payload[pos:pos + chunk_size]

    def close(self):
        pass


class Session:
    def __init__(self, mutations=None):
        self.calls, self.mutations = [], mutations or {}

    def request(self, method, url, data, headers, **kwargs):
        assert self.trust_env is False
        assert headers["User-Agent"] == http.USER_AGENT
        assert headers["Accept-Encoding"] == "identity"
        assert kwargs["allow_redirects"] is False
        self.calls.append((method, url, data))
        if url in self.mutations:
            value = self.mutations[url]
            if isinstance(value, Exception):
                raise value
            return value
        for row in ROWS:
            original_url = row["url"]
            if "pressReleaseView.do" in original_url:
                original_url = kr_url(original_url)
            if original_url != url:
                continue
            if "pressReleaseList.do" in url and row.get("form") != data:
                continue
            if "capture" in row:
                headers = row.get("headers", {})
                ctype = next((v for k, v in headers.items() if k.lower() == "content-type"), "text/html")
                return Response(url, fixture(row["capture"]), row["status"], ctype)
        raise AssertionError("unrecorded request: " + repr((method, url, data)))


def adapter(desk, mutations=None):
    name, cls, _ = runner.DESKS[desk]
    source = load_manifest(ROOT / "shadow" / name / "manifest.json").sources[0]
    session = Session(mutations)
    return cls(source, session=session, sleeper=lambda _: None), session


class Case(unittest.TestCase):
    def setUp(self):
        guard = mock.patch.object(socket.socket, "connect", side_effect=AssertionError("real network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)


class Evidence(Case):
    def test_all_capture_bytes_match_the_native_request_ledger(self):
        for row in ROWS:
            if "capture" in row:
                data = fixture(row["capture"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), row["sha256"])
                self.assertEqual(len(data), row["bytes"])

    def test_both_manifests_are_absent_from_production_discovery_and_registry(self):
        self.assertNotIn("indonesia", load_all_desks())
        self.assertNotIn("korea", load_all_desks())
        slugs = [d["slug"] for d in json.loads((ROOT / "desks/registry.json").read_text())["desks"]]
        self.assertNotIn("indonesia", slugs)
        self.assertNotIn("korea", slugs)

    def test_korean_ministry_policy_blocks_the_publication_paths(self):
        rules, _ = http.robots_policy(fixture("mnd-robots.bin").decode())
        self.assertFalse(http.robots_allows(rules, "https://www.mnd.go.kr/mnd/167/subview.do"))
        self.assertTrue(http.robots_allows(rules, "https://www.mnd.go.kr/mnd/index.do"))

    def test_portal_and_kemhan_policies_allow_the_declared_routes(self):
        for name, url in [("kemhan-robots.bin", ID_LISTING), ("korea-policy.bin", KR_LISTING)]:
            rules, delay = http.robots_policy(fixture(name).decode())
            self.assertTrue(http.robots_allows(rules, url))
            self.assertEqual(delay, 2)

    def test_longest_rule_allow_tie_named_group_and_crawl_delay(self):
        rules, delay = http.robots_policy("User-agent: *\nDisallow: /\nUser-agent: IndoPacificRecord\nDisallow: /secret*\nAllow: /secret/public$\nCrawl-delay: 4.5\n")
        self.assertTrue(http.robots_allows(rules, "https://www.korea.kr/briefing/"))
        self.assertFalse(http.robots_allows(rules, "https://www.korea.kr/secret/file"))
        self.assertTrue(http.robots_allows(rules, "https://www.korea.kr/secret/public"))
        self.assertEqual(delay, 4.5)


class Indonesia(Case):
    def test_discovery_retains_every_current_day_news_item(self):
        a, session = adapter("indonesia")
        result = a.discover(CollectionWindow(TARGET, 0))
        self.assertEqual(result.status, st.OK)
        self.assertEqual(len(result.references), 1)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(a.listing_report["pages_walked"], 1)

    def test_pagination_walks_only_the_published_next_link(self):
        a, session = adapter("indonesia")
        result = a.discover(CollectionWindow(TARGET, 6))
        self.assertEqual(result.status, st.OK)
        self.assertGreater(len(result.references), 1)
        self.assertEqual(a.listing_report["pages_walked"], 2)
        self.assertEqual(session.calls[-1][1], ID_LISTING + "/page/2")

    def test_original_body_keeps_prose_wrapped_by_malformed_image_markup(self):
        a, _ = adapter("indonesia")
        ref = a.discover(CollectionWindow(TARGET, 0)).references[0]
        result = a.extract(a.fetch(ref))
        self.assertEqual(result.status, st.OK)
        doc = result.documents[0]
        self.assertTrue(doc.text_original.startswith("Jakarta –"))
        self.assertTrue(doc.text_original.endswith("(Biro Infohan Setjen Kemhan)"))
        self.assertNotIn("Statistik Pengunjung", doc.text_original)
        self.assertEqual(doc.published_date, "2026-10-06")
        self.assertEqual(doc.extra["date_precision"], "day")
        self.assertIsNone(doc.extra["issuer"])

    def test_second_real_article_extracts_by_the_same_body_rule(self):
        a, _ = adapter("indonesia")
        url = next(r["url"] for r in ROWS if r.get("capture") == "kemhan-article-2.bin")
        doc = a.parse_article(fixture("kemhan-article-2.bin").decode(), url)
        self.assertTrue(doc.has_usable_text)
        self.assertEqual(doc.published_date, id_url(url)[1])

    def test_future_window_is_healthy_empty(self):
        a, _ = adapter("indonesia")
        self.assertEqual(a.discover(CollectionWindow(date(2026, 10, 7), 0)).status, st.OK_NO_PUBLICATIONS)

    def test_markup_loss_is_failure_not_silence(self):
        a, _ = adapter("indonesia", {ID_LISTING: Response(ID_LISTING, b"<html></html>")})
        self.assertEqual(a.discover(CollectionWindow(TARGET)).status, st.LISTING_FAILURE)

    def test_missing_next_page_is_failure(self):
        soup = BeautifulSoup(fixture("kemhan-news.bin"), "html.parser")
        for anchor in soup.select('a[href="' + ID_LISTING + '/page/2"]'):
            anchor.decompose()
        a, _ = adapter("indonesia", {ID_LISTING: Response(ID_LISTING, str(soup).encode())})
        self.assertEqual(a.discover(CollectionWindow(TARGET, 6)).status, st.LISTING_FAILURE)

    def test_repeated_page_fails_without_partial_candidates(self):
        url = ID_LISTING + "/page/2"
        payload = fixture("kemhan-news.bin").replace(b'>1</a>', b'>2</a>')
        a, _ = adapter("indonesia", {url: Response(url, payload)})
        result = a.discover(CollectionWindow(TARGET, 6))
        self.assertFalse(result.ok)
        self.assertEqual(result.references, [])

    def test_date_mismatch_and_foreign_url_are_refused(self):
        a, _ = adapter("indonesia")
        row = next(r for r in ROWS if r.get("capture") == "kemhan-article.bin")
        with self.assertRaises(ValueError):
            a.parse_article(fixture("kemhan-article.bin").decode().replace("6 Oktober 2026", "5 Oktober 2026"), row["url"])
        with self.assertRaises(ValueError):
            id_url(row["url"].replace("www.kemhan.go.id", "tni.mil.id"))


class Korea(Case):
    def test_native_current_day_discovery_fetch_and_document_extraction(self):
        a, session = adapter("korea")
        result = a.discover(CollectionWindow(TARGET))
        self.assertEqual(result.status, st.OK)
        self.assertEqual(len(result.references), 1)
        capture = a.fetch(result.references[0])
        extracted = a.extract(capture)
        self.assertEqual(extracted.status, st.OK)
        self.assertEqual(extracted.documents[0].published_date, "2026-10-06")
        self.assertEqual(len(session.calls), 4)
        self.assertFalse(any("mnd.go.kr" in c[1] for c in session.calls))

    def test_filtered_listing_preserves_all_listed_mnd_identities(self):
        a, session = adapter("korea")
        page = a.parse_listing(fixture("korea-filtered.bin").decode(),
                               (KR_LISTING, {"repCode": "A00005", "pageIndex": "1",
                                             "startDate": "2026-09-01", "endDate": "2026-10-06"}), 1)
        self.assertEqual(len(page.items), 20)
        self.assertEqual(page.next_request[1]["pageIndex"], "2")
        self.assertTrue(all(urlsplit(i["url"]).netloc == "www.korea.kr" for i in page.items))
        self.assertEqual(session.calls, [])

    def test_real_hwpx_documents_extract_as_original_korean(self):
        a, _ = adapter("korea")
        for n in (1, 2):
            row = next(r for r in ROWS if r.get("capture") == "korea-article-%d.bin" % n)
            url = kr_url(row["url"])
            body = fixture("korea-document-%d.bin" % n)
            a.documents[url] = (body, {"capture_sha256": hashlib.sha256(body).hexdigest(), "retrieved_at": row["retrieved_at"]})
            doc = a.parse_article(fixture("korea-article-%d.bin" % n).decode(), url)
            self.assertEqual(doc.text_original, hwpx_text(body))
            self.assertIn(doc.title_original, doc.text_original)
            self.assertEqual(doc.extra["issuer"], "국방부")
            self.assertEqual(doc.extra["publisher"], "대한민국 정책브리핑")
            self.assertEqual(doc.extra["body_scope"], "published_hwpx_text")
            self.assertNotIn("이 자료는 국방부의 보도자료를 전재", doc.text_original)

    def test_iframe_html_cannot_become_a_body_without_its_document(self):
        a, _ = adapter("korea")
        row = next(r for r in ROWS if r.get("capture") == "korea-article-1.bin")
        with self.assertRaisesRegex(ValueError, "not retrieved"):
            a.parse_article(fixture("korea-article-1.bin").decode(), kr_url(row["url"]))

    def test_real_empty_search_is_healthy_without_a_pagination_block(self):
        a, _ = adapter("korea")
        self.assertEqual(a.discover(CollectionWindow(date(2026, 10, 5))).status, st.OK_NO_PUBLICATIONS)

    def test_filter_loss_and_missing_empty_marker_are_failures(self):
        a, _ = adapter("korea")
        form = {"repCode": "A00005", "pageIndex": "1", "startDate": "2026-10-05", "endDate": "2026-10-05"}
        text = fixture("korea-empty.bin").decode()
        for bad in (text.replace('class="no_data"', 'class=""'), text.replace('value="A00005"', 'value=""')):
            with self.assertRaises(ValueError):
                a.parse_listing(bad, (KR_LISTING, form), 1)

    def test_malformed_or_entity_xml_is_refused(self):
        with self.assertRaises(ValueError):
            hwpx_text(b"<html>not a document</html>")
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("Contents/section0.xml", '<!DOCTYPE x [<!ENTITY y "z">]><x/>')
        with self.assertRaises(ValueError):
            hwpx_text(stream.getvalue())


class Access(Case):
    def test_policy_refusal_causes_no_listing_request(self):
        url = "https://www.kemhan.go.id/robots.txt"
        a, session = adapter("indonesia", {url: Response(url, b"User-agent: *\nDisallow: /", ctype="text/plain")})
        result = a.discover(CollectionWindow(TARGET))
        self.assertEqual(result.status, st.AUTH_FAILURE)
        self.assertEqual(len(session.calls), 1)

    def test_unreadable_or_html_robots_is_never_permission(self):
        url = "https://www.kemhan.go.id/robots.txt"
        for response in (Response(url, b"denied", 403, "text/plain"), Response(url, b"<html></html>")):
            a, session = adapter("indonesia", {url: response})
            self.assertFalse(a.discover(CollectionWindow(TARGET)).ok)
            self.assertEqual(len(session.calls), 1)

    def test_redirect_and_http_200_challenge_are_refused(self):
        for response, status in [(Response(ID_LISTING, b"", 302), st.DISALLOWED_REDIRECT),
                                 (Response(ID_LISTING, b'<html><title>Just a moment</title></html>'), st.ACCESS_CHALLENGED)]:
            a, _ = adapter("indonesia", {ID_LISTING: response})
            self.assertEqual(a.discover(CollectionWindow(TARGET)).status, status)

    def test_fetch_cannot_bypass_discovery(self):
        a, session = adapter("indonesia")
        result = a.fetch(CandidateReference(ID_LISTING, a.slug))
        self.assertEqual(result.status, st.AUTH_FAILURE)
        self.assertEqual(session.calls, [])


class Runner(Case):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"

    def go(self, run_id="r1", mutations=None, cap=40):
        a, _ = adapter("indonesia", mutations)
        return runner.run("indonesia", self.state, TARGET, 0, cap, run_id, "collector-sha", adapter=a)

    def test_original_records_captures_clock_and_append_only_ledger(self):
        entry = self.go()
        self.assertEqual(entry["result"], st.OK)
        self.assertEqual(entry["inserted"], 1)
        self.assertEqual(len(entry["requests"]), 3)
        before = {p: p.read_bytes() for p in (self.state / "ledger").glob("*.json")}
        clock = (self.state / "clock.json").read_bytes()
        second = self.go("r2")
        self.assertEqual(second["result"], st.OK_ALL_DUPLICATES)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(clock, (self.state / "clock.json").read_bytes())
        self.assertEqual(len(list((self.state / "ledger").glob("*.json"))), 2)
        for p, body in before.items():
            self.assertEqual(p.read_bytes(), body)
        for p in (self.state / "captures").glob("*.bin"):
            self.assertEqual(p.stem, hashlib.sha256(p.read_bytes()).hexdigest())

    def test_failure_preserves_evidence_without_starting_clock_or_corpus(self):
        entry = self.go(mutations={ID_LISTING: Response(ID_LISTING, b"denied", 403)})
        self.assertEqual(entry["result"], st.AUTH_FAILURE)
        self.assertFalse((self.state / "clock.json").exists())
        self.assertFalse((self.state / "shadow.db").exists())
        self.assertEqual(len(entry["requests"]), 2)

    def test_extraction_failure_does_not_store_a_partial_batch(self):
        row = next(r for r in ROWS if r.get("capture") == "kemhan-article.bin")
        payload = fixture(row["capture"]).replace(b"6 Oktober 2026", b"5 Oktober 2026")
        entry = self.go(mutations={row["url"]: Response(row["url"], payload)})
        self.assertEqual(entry["result"], st.EXTRACTION_FAILURE)
        self.assertEqual(entry["inserted"], 0)
        self.assertFalse((self.state / "shadow.db").exists())

    def test_failure_after_one_complete_release_rolls_back_the_whole_batch(self):
        soup = BeautifulSoup(fixture("korea-filtered.bin"), "html.parser")
        links = soup.select('a[href*="pressReleaseView.do"][href*="pageIndex="]')
        for link in links[2:]:
            link.parent.decompose()
        soup.select_one('#mainForm input[name="startDate"]')["value"] = "2026-10-02"
        soup.select_one(".result strong").string = "2"
        for link in soup.select(".paging a[onclick]"):
            if "pageLink(" in link["onclick"]:
                link.parent.decompose()
        document = next(r["url"] for r in ROWS if r.get("capture") == "korea-document-2.bin")
        a, _ = adapter("korea", {KR_LISTING: Response(KR_LISTING, str(soup).encode()),
                                  document: Response(document, b"<html>unavailable</html>")})
        entry = runner.run("korea", self.state, TARGET, 4, adapter=a)
        self.assertEqual(entry["selected"], 2)
        self.assertEqual(entry["extracted"], 1)
        self.assertEqual(entry["inserted"], 0)
        self.assertFalse((self.state / "shadow.db").exists())
        self.assertFalse((self.state / "clock.json").exists())

    def test_ambiguous_rerun_is_refused_before_state_creation(self):
        from contextlib import redirect_stderr
        with redirect_stderr(io.StringIO()):
            code = runner.main(["--desk", "indonesia", "--state-dir", str(self.state),
                                "--event-name", "schedule", "--cron-utc", "07:10", "--run-attempt", "2"])
        self.assertEqual(code, 2)
        self.assertFalse(self.state.exists())

    def test_wrong_desk_cannot_reuse_an_existing_corpus(self):
        self.go()
        with self.assertRaisesRegex(ValueError, "another desk"):
            runner.run("korea", self.state, TARGET)

    def test_korea_stores_both_capture_types_and_explicit_republication_metadata(self):
        a, _ = adapter("korea")
        entry = runner.run("korea", self.state, TARGET, 0, adapter=a)
        self.assertEqual(entry["result"], st.OK)
        self.assertEqual(len(entry["requests"]), 4)
        with sqlite3.connect(self.state / "shadow.db") as db:
            metadata = json.loads(db.execute("SELECT metadata_json FROM shadow_records").fetchone()[0])
        self.assertEqual(metadata["issuer"], "국방부")
        self.assertEqual(metadata["body_scope"], "published_hwpx_text")
        path = self.state / "captures" / (metadata["document_capture_sha256"] + ".bin")
        self.assertEqual(hwpx_text(path.read_bytes()), hwpx_text(fixture("korea-document-1.bin")))

    def test_window_over_cap_fails_before_body_fetch(self):
        a, session = adapter("indonesia")
        entry = runner.run("indonesia", self.state, TARGET, 6, 1, adapter=a)
        self.assertEqual(entry["result"], st.LISTING_FAILURE)
        self.assertEqual(entry["selected"], 0)
        self.assertEqual(len(session.calls), 3)
        self.assertFalse((self.state / "clock.json").exists())

    def test_reviewer_exports_originals_read_only_without_human_sign_off(self):
        self.go()
        before = reviewer.hash_files(self.state)
        report = reviewer.review(self.state, "indonesia", Path(self.tmp.name) / "packet", TARGET)
        self.assertEqual(report["records"], 1)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["mode"], "rehearsal")
        self.assertFalse(report["human_review_completed"])
        self.assertFalse(report["promotion_authorized"])
        self.assertEqual(reviewer.hash_files(self.state), before)
        protected = Path(self.tmp.name) / "other-checkout"
        with mock.patch.object(reviewer, "git", return_value=("worktree " + str(protected) + "\n").encode()):
            with self.assertRaisesRegex(ValueError, "outside collector"):
                reviewer.review(self.state, "indonesia", protected / "packet", TARGET)

    def test_reviewer_reports_capture_corruption_and_a_missing_logical_day(self):
        self.go()
        capture = next((self.state / "captures").glob("*.bin"))
        capture.write_bytes(b"")
        report = reviewer.review(self.state, "indonesia", Path(self.tmp.name) / "packet", date(2026, 10, 7))
        self.assertTrue(report["findings"])
        self.assertEqual(report["missing_successful_days"], ["2026-10-07"])

    def test_formal_review_reads_pinned_git_objects_and_refuses_foreign_branches(self):
        import subprocess
        self.go()
        repo = Path(self.tmp.name) / "git-state"
        repo.mkdir()
        import shutil
        shutil.copytree(self.state, repo / "state")
        def git(*args):
            return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL)
        git("init")
        git("checkout", "--orphan", reviewer.BRANCHES["indonesia"])
        git("add", "state")
        git("-c", "user.name=Fixture rehearsal", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Fixture state only")
        commit = git("rev-parse", "HEAD").decode().strip()
        (repo / "state/clock.json").write_text("uncommitted fixture corruption")
        export = Path(self.tmp.name) / "export"
        tree = reviewer.export_commit(repo, commit, "indonesia", export)
        report = reviewer.review(export / "state", "indonesia", Path(self.tmp.name) / "packet", TARGET, commit, tree)
        self.assertEqual(report["mode"], "formal_commit_snapshot")
        self.assertEqual(report["findings"], [])
        with self.assertRaises(subprocess.CalledProcessError):
            reviewer.export_commit(repo, commit, "korea", Path(self.tmp.name) / "wrong")
        (repo / "unexpected").write_text("fixture contamination")
        git("add", "unexpected")
        git("-c", "user.name=Fixture rehearsal", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Fixture contamination")
        bad_commit = git("rev-parse", "HEAD").decode().strip()
        with self.assertRaisesRegex(ValueError, "outside state"):
            reviewer.export_commit(repo, bad_commit, "indonesia", Path(self.tmp.name) / "contaminated")

    def test_workflow_preserves_manual_launch_and_explicit_success_only_state_destination(self):
        raw = (ROOT / ".github/workflows/indonesia_korea_shadow.yml").read_text()
        self.assertIn("workflow_dispatch:", raw)
        self.assertIn("  schedule:", raw)
        self.assertIn('git push origin "HEAD:refs/heads/$STATE_BRANCH"', raw)
        self.assertIn("if: success()", raw)
        self.assertNotIn("--force", raw)
        self.assertNotIn("actions-gh-pages", raw)
        self.assertEqual(reviewer.BRANCHES, {desk: spec[2] for desk, spec in runner.DESKS.items()})

    def test_workflow_shell_blocks_parse(self):
        import re
        import subprocess
        import textwrap
        raw = (ROOT / ".github/workflows/indonesia_korea_shadow.yml").read_text()
        blocks = re.findall(r"        run: \|\n(.*?)(?=^      - name:|\Z)", raw, re.M | re.S)
        for block in blocks:
            block = block.split("\n      - name:", 1)[0]
            subprocess.run(["bash", "-n"], input=textwrap.dedent(block), text=True, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_repository_paths_and_symlink_state_are_refused(self):
        with self.assertRaises(ValueError):
            runner.assert_isolated(ROOT / "shadow/test-state")
        link = Path(self.tmp.name) / "link"
        link.symlink_to(self.state)
        with self.assertRaises(ValueError):
            runner.assert_isolated(link)
        protected = Path(self.tmp.name) / "other-collector-checkout"
        with mock.patch.object(runner.subprocess, "check_output", return_value="worktree " + str(protected) + "\n"):
            with self.assertRaises(ValueError):
                runner.assert_isolated(protected / "state")

    def test_no_relevance_translation_or_production_storage_in_runner(self):
        import ast
        source = (ROOT / "scripts/shadow_collect_desk.py").read_text()
        tree = ast.parse(source)
        strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        self.assertFalse(any("pla_watch.db" in s or "output/" in s for s in strings))


class WorkflowCadence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.raw = (ROOT / ".github/workflows/indonesia_korea_shadow.yml").read_text()

    def block(self, name):
        import textwrap
        step = self.raw.split("      - name: " + name + "\n", 1)[1].split("      - name:", 1)[0]
        return textwrap.dedent(step.split("        run: |\n", 1)[1])

    def shell(self, name, values):
        import os
        import subprocess
        return subprocess.run(["bash", "-c", self.block(name)], cwd=self.root,
                              env={**os.environ, **values}, text=True, capture_output=True)

    def selection(self, event, schedule="", desk=""):
        env_file = self.root / "selected-env"
        env_file.write_text("")
        result = self.shell("Select the fixed desk branch", {
            "EVENT_NAME": event, "SCHEDULE_INPUT": schedule, "DESK_INPUT": desk,
            "GITHUB_ENV": str(env_file),
        })
        values = dict(line.split("=", 1) for line in env_file.read_text().splitlines())
        return result, values

    def probes(self):
        import os
        import sys
        directory = self.root / "bin"
        directory.mkdir(exist_ok=True)
        bodies = {
            "git": "import sys\nassert sys.argv[1:] == ['rev-parse', 'HEAD']\nprint('fixture-collector')\n",
            "python": "import json, os, sys\nfrom pathlib import Path\nPath(os.environ['PROBE_ARGS']).write_text(json.dumps(sys.argv[1:]))\n",
        }
        for name, body in bodies.items():
            path = directory / name
            path.write_text("#!" + sys.executable + "\n" + body)
            path.chmod(0o755)
        return str(directory) + os.pathsep + os.environ["PATH"]

    def collection_args(self, values, event, target="", attempt="1"):
        path = self.root / "args.json"
        result = self.shell("Collect the declared window", {
            **values, "PATH": self.probes(), "PROBE_ARGS": str(path),
            "RUNNER_TEMP": str(self.root), "GITHUB_EVENT_NAME": event,
            "GITHUB_RUN_ID": "fixture", "GITHUB_RUN_ATTEMPT": attempt,
            "TARGET_DATE_INPUT": target,
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(path.read_text())
        self.assertEqual(args[0], "scripts/shadow_collect_desk.py")
        return args[1:]

    def test_each_schedule_selects_its_desk_even_with_conflicting_dispatch_input(self):
        for cron, desk, branch, time in (
            ("17 17 * * *", "indonesia", "shadow/indonesia-kemhan", "17:17"),
            ("47 17 * * *", "korea", "shadow/korea-policy-briefing", "17:47"),
        ):
            with self.subTest(desk=desk):
                result, values = self.selection("schedule", cron, "korea" if desk == "indonesia" else "indonesia")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(values, {"SHADOW_DESK": desk, "STATE_BRANCH": branch, "SHADOW_CRON_UTC": time})

    def test_manual_dispatch_keeps_its_selected_desk(self):
        for desk, time in (("indonesia", "17:17"), ("korea", "17:47")):
            result, values = self.selection("workflow_dispatch", "", desk)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(values["SHADOW_DESK"], desk)
            self.assertEqual(values["SHADOW_CRON_UTC"], time)

    def test_unknown_events_schedules_and_desks_fail_before_state_selection(self):
        for event, schedule, desk in (
            ("schedule", "", "indonesia"), ("schedule", "0 * * * *", "korea"),
            ("push", "", "indonesia"), ("workflow_dispatch", "", "../foreign"),
        ):
            with self.subTest(event=event, schedule=schedule, desk=desk):
                result, values = self.selection(event, schedule, desk)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(values, {})

    def test_actual_workflow_arguments_preserve_scheduled_dates_across_midnight(self):
        from contextlib import redirect_stdout
        from datetime import datetime, timezone
        for cron in ("17 17 * * *", "47 17 * * *"):
            _, values = self.selection("schedule", cron)
            args = self.collection_args(values, "schedule")
            with mock.patch.object(runner, "datetime") as clock, mock.patch.object(runner, "run", return_value={"health": "ok"}) as collect:
                clock.now.return_value = datetime(2026, 10, 7, 0, 15, tzinfo=timezone.utc)
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(runner.main(args), 0)
                self.assertEqual(collect.call_args.args[2], date(2026, 10, 6))
                self.assertEqual(collect.call_args.kwargs["target_source"], "schedule-slot")

    def test_actual_manual_arguments_keep_utc_today_or_explicit_recovery_date(self):
        from contextlib import redirect_stdout
        from datetime import datetime, timezone
        _, values = self.selection("workflow_dispatch", "", "korea")
        for target, expected, provenance in (("", date(2026, 10, 7), "manual-utc-date"),
                                              ("2026-10-03", date(2026, 10, 3), "explicit")):
            args = self.collection_args(values, "workflow_dispatch", target)
            with mock.patch.object(runner, "datetime") as clock, mock.patch.object(runner, "run", return_value={"health": "ok"}) as collect:
                clock.now.return_value = datetime(2026, 10, 7, 0, 15, tzinfo=timezone.utc)
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(runner.main(args), 0)
                self.assertEqual(collect.call_args.args[2], expected)
                self.assertEqual(collect.call_args.kwargs["target_source"], provenance)

    def test_scheduled_ui_rerun_still_refuses_an_ambiguous_date(self):
        from contextlib import redirect_stderr
        _, values = self.selection("schedule", "17 17 * * *")
        args = self.collection_args(values, "schedule", attempt="2")
        with mock.patch.object(runner, "run") as collect, redirect_stderr(io.StringIO()):
            self.assertEqual(runner.main(args), 2)
        collect.assert_not_called()
        self.assertFalse((self.root / "candidate-state").exists())

    def test_missing_scheduled_state_refuses_to_bootstrap_a_new_clock(self):
        import sys
        path = self.probes()
        (self.root / "bin/git").write_text("#!" + sys.executable + "\nimport sys\nsys.exit(2 if sys.argv[1] == 'ls-remote' else 98)\n")
        result = self.shell("Check out isolated state", {
            "PATH": path, "RUNNER_TEMP": str(self.root), "GITHUB_EVENT_NAME": "schedule",
            "STATE_BRANCH": "shadow/indonesia-kemhan", "STATE_REMOTE": "https://example.invalid/fixture",
        })
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("refusing to restart its clock", result.stdout)
        self.assertFalse((self.root / "candidate-state").exists())

    def test_schedule_contract_keeps_daily_slots_main_guard_and_desk_serialization(self):
        import re
        self.assertEqual(re.findall(r"- cron: '([^']+)'", self.raw), ["17 17 * * *", "47 17 * * *"])
        self.assertIn("if: github.ref == 'refs/heads/main'", self.raw)
        group = next(line for line in self.raw.splitlines() if line.startswith("  group:"))
        self.assertIn("inputs.desk ||", group)
        self.assertIn("github.event.schedule == '17 17 * * *' && 'indonesia'", group)
        self.assertIn("github.event.schedule == '47 17 * * *' && 'korea'", group)
        self.assertIn("cancel-in-progress: false", self.raw)
        self.assertIn('--lookback-days 6 --cap 40', self.raw)

    def test_scheduled_state_requires_both_existing_database_and_clock(self):
        import sys
        path = self.probes()
        (self.root / "bin/git").write_text("#!" + sys.executable + "\n" +
            "import os, sys\nfrom pathlib import Path\n" +
            "cmd = sys.argv[1]\n" +
            "if cmd == 'ls-remote':\n    sys.exit(0)\n" +
            "elif cmd == 'clone':\n" +
            "    state = Path(sys.argv[-1]) / 'state'\n    state.mkdir(parents=True)\n" +
            "    if os.environ['HAS_DB'] == '1': (state / 'shadow.db').write_bytes(b'fixture')\n" +
            "    if os.environ['HAS_CLOCK'] == '1': (state / 'clock.json').write_text('{}')\n" +
            "elif cmd == 'branch':\n    print(os.environ['STATE_BRANCH'])\n" +
            "elif cmd == 'rev-parse':\n    print('fixture-collector')\n" +
            "elif cmd == 'ls-tree':\n    print('state')\n" +
            "else:\n    sys.exit(98)\n")
        for has_db, has_clock, expected in (("1", "0", 1), ("0", "1", 1), ("1", "1", 0)):
            with self.subTest(database=has_db, clock=has_clock):
                run_temp = self.root / (has_db + has_clock)
                run_temp.mkdir()
                result = self.shell("Check out isolated state", {
                    "PATH": path, "RUNNER_TEMP": str(run_temp), "GITHUB_EVENT_NAME": "schedule",
                    "STATE_BRANCH": "shadow/korea-policy-briefing", "STATE_REMOTE": "https://example.invalid/fixture",
                    "HAS_DB": has_db, "HAS_CLOCK": has_clock,
                })
                self.assertEqual(result.returncode, expected, result.stderr)
                if expected:
                    self.assertIn("refusing to restart its clock", result.stdout)


if __name__ == "__main__":
    unittest.main()
