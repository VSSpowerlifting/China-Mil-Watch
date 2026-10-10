"""Fictional inputs exercising the real application's storage and migrations."""
from contextlib import contextmanager
from unittest.mock import patch
import json
from pathlib import Path

from processing.metadata import normalize_article
from storage import db


@contextmanager
def bind_database(path):
    # Exercise the real injected connection paths, not a module-global patch.
    from storage.evidence_custody import _scratch_root, application_identity
    path = Path(path).resolve()
    execution = json.loads((path.parent / "execution.json").read_text())
    def validate():
        import sqlite3
        _scratch_root(path.parent)
        if not path.is_file() or path.is_symlink():
            from core.evidence_snapshot import EvidenceContractError
            raise EvidenceContractError("custody_working_database_missing")
        c = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            c.execute("BEGIN")
            application_identity(c)
        finally:
            c.close()
    context = db.DatabaseContext(path, validate, execution["execution_id"],
                                 execution["logical_date"])
    with db.use_database_context(context):
        yield


def initialize_application(path):
    # Fixture construction explicitly initializes a new marked scratch DB.
    # Runtime private contexts refuse initialization/migration; this is not
    # a restore or private-mode startup path.
    with patch.object(db, "DB_PATH", path):
        db.init_db()
        with db.get_conn() as connection:
            connection.execute(
                "INSERT INTO sources(slug,display_name,base_url,language,desk_id) "
                "VALUES('fictional_custody','Fictional fixture institution',"
                "'https://fixture.invalid/','en','china')")


def insert_fictional(path, number=1):
    article = normalize_article({
        "source_slug": "fictional_custody",
        "url": "https://fixture.invalid/record/%d" % number,
        "title_original": "Fictional fixture title %d" % number,
        "text_original": "CUSTODY_PRIVATE_SYNTHETIC_BODY_%d" % number,
        "published_date": "2026-10-10",
    })
    with bind_database(path):
        run_id = db.start_scrape_run()
        article_id = db.insert_article(article, run_id)
        from core.collection.contract import SourceRunResult
        db.record_source_run_result(run_id, SourceRunResult(
            source_slug="fictional_custody", desk_id="china", status="ok",
            new_documents=1, extracted=1, fetched=1, references_discovered=1))
    return article_id
