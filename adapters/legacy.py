"""
Compatibility wrapper: existing `BaseScraper` subclasses behind the neutral
adapter contract.

This is the load-bearing decision of Phase 2. The five China scrapers work.
Their selectors, date matching and encoding handling represent months of
accumulated corrections against real sites, and rewriting them to a new
interface would risk all of it for no collection benefit. So they are not
rewritten: this adapter calls exactly the same methods, in exactly the same
order, as `BaseScraper.scrape()` does today.

    urls = get_article_urls()
    for url in urls:
        html = fetch(url)
        if not html: continue
        article = parse_article(url, html)
        if article: keep it

What changes is only what is *recorded* around that loop. Where `scrape()`
returns a bare list — which is why "MOD published nothing" and "MOD was
unreachable" have been indistinguishable for four weeks at a time — this
returns a structured `SourceRunResult` naming which happened.
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from core.collection import status as st
from core.collection.contract import (
    CandidateReference,
    CaptureResult,
    CollectionWindow,
    DiscoveryResult,
    ExtractedDocument,
    ExtractionResult,
    SourceAdapter,
    SourceHealthResult,
    SourceRunResult,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def load_scraper_class(dotted: str):
    """
    Resolve "package.module:ClassName" from a desk manifest.

    Import errors are raised, not swallowed: a manifest naming an adapter that
    does not exist is a configuration defect, and a registry that quietly
    skipped it would recreate the silent-inert-source problem this phase exists
    to remove.
    """
    if not dotted or ":" not in dotted:
        raise ValueError(
            "adapter must be 'module.path:ClassName', got %r" % (dotted,)
        )
    module_path, class_name = dotted.split(":", 1)
    module = importlib.import_module(module_path)
    try:
        return getattr(module, class_name)
    except AttributeError:
        raise ImportError(
            "module %s has no attribute %r" % (module_path, class_name)
        )


class LegacyScraperAdapter(SourceAdapter):
    """Wraps one `BaseScraper` subclass."""

    def __init__(self, source, scraper_class=None) -> None:
        super().__init__(source)
        self._scraper_class = scraper_class or load_scraper_class(source.adapter)
        self._scraper = None
        # A stub adapter declares itself. Xinhua Military's scraper returns []
        # by design because its listing is JS-rendered; without this flag it is
        # indistinguishable from a healthy source that published nothing, which
        # is precisely how it contributed zero rows for the life of the project
        # while every run reported success.
        self.implemented = not getattr(self._scraper_class, "IS_STUB", False)

    # ── construction ─────────────────────────────────────────────────────────

    def _get(self, window: Optional[CollectionWindow] = None):
        """Instantiate lazily so constructing the registry performs no I/O."""
        if self._scraper is None:
            kwargs = {}
            if window is not None:
                kwargs["target_date"] = window.target_date
            self._scraper = self._scraper_class(**kwargs)
        return self._scraper

    @property
    def failed_fetches(self) -> List[str]:
        if self._scraper is None:
            return []
        return list(getattr(self._scraper, "failed_fetches", []))

    # ── contract ─────────────────────────────────────────────────────────────

    def discover(self, window: CollectionWindow) -> DiscoveryResult:
        scraper = self._get(window)
        try:
            urls = scraper.get_article_urls()
        except Exception as exc:
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE, [],
                error_detail="listing traversal raised: %s" % _brief(exc),
            )

        refs = [CandidateReference(url=u, source_slug=self.slug) for u in urls]

        if refs:
            return DiscoveryResult(self.slug, st.OK, refs)

        # Zero references. The whole point of this phase is to say which zero.
        if self.failed_fetches:
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE, [],
                failed_endpoints=self.failed_fetches,
                error_detail=(
                    "%d listing fetch(es) exhausted all retries"
                    % len(self.failed_fetches)
                ),
            )
        if not self.implemented:
            return DiscoveryResult(
                self.slug, st.NOT_IMPLEMENTED, [],
                error_detail="adapter is a documented stub",
            )
        return DiscoveryResult(self.slug, st.OK_NO_PUBLICATIONS, [])

    def fetch(self, reference: CandidateReference) -> CaptureResult:
        scraper = self._get()
        try:
            html = scraper.fetch(reference.url)
        except Exception as exc:
            return CaptureResult(
                reference, st.FETCH_FAILURE, reference.url,
                error_detail="fetch raised: %s" % _brief(exc),
            )

        if not html:
            return CaptureResult(
                reference, st.FETCH_FAILURE, reference.url,
                error_detail="fetch returned no body (retries exhausted)",
            )

        import hashlib
        payload = html.encode("utf-8", "replace")
        return CaptureResult(
            reference=reference,
            status=st.OK,
            requested_url=reference.url,
            final_url=reference.url,
            content_type="text/html",
            payload_bytes=len(payload),
            payload_sha256=hashlib.sha256(payload).hexdigest(),
            retrieved_at=_now(),
            body=html,
        )

    def extract(self, capture: CaptureResult) -> ExtractionResult:
        if not capture.ok or capture.body is None:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE, [],
                error_detail="no capture body to extract from",
            )
        scraper = self._get()
        try:
            article = scraper.parse_article(capture.requested_url, capture.body)
        except Exception as exc:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE, [],
                error_detail="parser raised: %s" % _brief(exc),
            )

        if not article:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE, [],
                error_detail="parser returned nothing for %s"
                             % capture.requested_url,
            )

        doc = ExtractedDocument(
            url=article.get("url", capture.requested_url),
            source_slug=article.get("source_slug", self.slug),
            title_original=article.get("title_original", "") or "",
            text_original=article.get("text_original", "") or "",
            published_date=article.get("published_date"),
            language_tag=getattr(self.source, "language_tag", None),
            extra={
                k: v for k, v in article.items()
                if k not in ("url", "source_slug", "title_original",
                             "text_original", "published_date")
            },
            # Verbatim parser output. Downstream normalization, dedup and the
            # keyword filter must receive exactly what they receive today.
            raw=dict(article),
        )
        return ExtractionResult(self.slug, st.OK, [doc])

    def healthcheck(self) -> SourceHealthResult:
        if not self.implemented:
            return SourceHealthResult(
                self.slug, st.NOT_IMPLEMENTED,
                "documented stub — no working collection path",
            )
        if not getattr(self.source, "enabled", True):
            return SourceHealthResult(
                self.slug, st.SKIPPED_DISABLED, "disabled in desk manifest",
            )
        try:
            load_scraper_class(self.source.adapter)
        except Exception as exc:
            return SourceHealthResult(
                self.slug, st.ADAPTER_ERROR,
                "adapter not importable: %s" % _brief(exc),
            )
        return SourceHealthResult(self.slug, st.OK, "configured and importable")

    # ── whole-source collection ──────────────────────────────────────────────

    def collect(
        self, window: CollectionWindow
    ) -> Tuple[SourceRunResult, List[ExtractedDocument]]:
        """
        Run discover → fetch → extract for this source.

        Mirrors `BaseScraper.scrape()` exactly, including the `if not html:
        continue` and `if article:` skips, so the documents produced here are
        the same documents the legacy path produces. Only the bookkeeping is new.
        """
        started = _now()
        result = SourceRunResult(
            source_slug=self.slug,
            status=st.OK,
            desk_id=getattr(self.source, "desk_id", None),
            started_at=started,
        )

        if not getattr(self.source, "enabled", True):
            result.status = st.SKIPPED_DISABLED
            result.completed_at = _now()
            return result, []

        discovery = self.discover(window)
        result.references_discovered = len(discovery.references)

        if not discovery.ok or not discovery.references:
            result.status = discovery.status
            result.error_detail = discovery.error_detail
            result.failed_fetches = len(self.failed_fetches)
            result.completed_at = _now()
            return result, []

        documents: List[ExtractedDocument] = []
        extraction_failures = 0
        for ref in discovery.references:
            capture = self.fetch(ref)
            if not capture.ok:
                continue
            result.fetched += 1
            extracted = self.extract(capture)
            if extracted.status == st.OK and extracted.documents:
                documents.extend(extracted.documents)
            else:
                extraction_failures += 1

        result.extracted = len(documents)
        result.failed_fetches = len(self.failed_fetches)
        result.completed_at = _now()

        if documents:
            result.status = st.OK
            if extraction_failures:
                result.error_detail = (
                    "%d of %d fetched page(s) failed extraction"
                    % (extraction_failures, result.fetched)
                )
        elif result.fetched == 0:
            result.status = st.FETCH_FAILURE
            result.error_detail = (
                "%d reference(s) discovered, none could be fetched"
                % result.references_discovered
            )
        else:
            result.status = st.EXTRACTION_FAILURE
            result.error_detail = (
                "%d page(s) fetched, none could be parsed — check for source "
                "markup drift" % result.fetched
            )
        return result, documents


def _brief(exc: Exception, limit: int = 200) -> str:
    """
    One-line, length-capped exception text.

    Scraped sites are untrusted input; their content can reach exception
    messages. Logs get a bounded single line, never an unbounded blob of
    hostile page content and never a stack trace on a public surface.
    """
    text = "%s: %s" % (type(exc).__name__, exc)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
