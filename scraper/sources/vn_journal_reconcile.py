"""Reconcile Vietnam journal listing hints against a parsed article, offline.

No HTTP, no filesystem writes, no archival authorization. Publisher prose may
exist in the caller's in-memory OfflineArticle but is never included in the
returned metadata. Source-page dates take precedence for analysis, but any
disagreement remains explicit and requires editorial review.
"""
from __future__ import annotations

from urllib.parse import urlsplit
from scraper.sources import vn_defence_journal as identity
from scraper.sources import vn_journal_article as article_parser
from scraper.sources import vn_journal_listing as listings


class ReconciliationRefused(ValueError):
    """Source identity or evidence provenance cannot be reconciled safely."""


def reconcile_article(observations, article):
    """Return bounded source/date metadata; never article body, title or credit.

    `observations` must contain the exact four offline ListingObservation
    values from a *single* bounded sample. It is not proof of historical
    completeness. `article` must be a parsed, in-memory OfflineArticle.
    The caller owns both the source access decision and destruction of HTML.
    """
    if not isinstance(article, article_parser.OfflineArticle):
        raise ReconciliationRefused("expected offline journal article parser result")
    if (article.source_slug != identity.SOURCE_SLUG
            or article.publisher != article_parser.PUBLISHER
            or article.language_tag != "en"
            or article.author_name_verified is not False
            or article.full_text_reuse_authorized is not False):
        raise ReconciliationRefused("article source/provenance or rights mismatch")

    try:
        canonical = identity.canonical_article_url(article.url)
        article_id = identity.article_identity(article.url)
        page_date = identity.stated_date(article.published_date_original)
    except (ValueError, TypeError) as exc:
        raise ReconciliationRefused("invalid article page identity or date stamp") from exc
    if (canonical != article.url or article_id != article.source_identity
            or page_date != article.published_date):
        raise ReconciliationRefused("article identity/date parser fields disagree")

    if not isinstance(observations, (list, tuple)) or len(observations) != len(listings.CATEGORY_URLS):
        raise ReconciliationRefused("exactly four category observations required")
    by_page, by_id = {}, {}
    for observation in observations:
        if not isinstance(observation, listings.ListingObservation):
            raise ReconciliationRefused("expected offline listing parser result")
        category = observation.category_page
        if category not in listings.CATEGORY_URLS or category in by_page:
            raise ReconciliationRefused("unknown or duplicated category observation")
        if observation.completeness_proven is not False or observation.pagination_verified is not False:
            raise ReconciliationRefused("unsupported listing completeness claim")
        if not observation.candidates:
            raise ReconciliationRefused("empty category observation")
        local_ids = set()
        for candidate in observation.candidates:
            if not isinstance(candidate, listings.ListingCandidate):
                raise ReconciliationRefused("expected offline listing candidate")
            if (candidate.category_page != category or candidate.article_date_verified is not False):
                raise ReconciliationRefused("candidate category or verified-date claim invalid")
            try:
                candidate_url = identity.canonical_article_url(candidate.canonical_url)
                candidate_id = identity.article_identity(candidate.canonical_url)
                category_from_url = urlsplit(candidate.canonical_url).path.split("/")[2]
                if candidate.date_hint is not None:
                    # A listing date hint has day precision, never a verified
                    # article publication date. strptime validates the day.
                    from datetime import datetime
                    valid_hint = datetime.strptime(candidate.date_hint, "%Y-%m-%d").date().isoformat()
                    if valid_hint != candidate.date_hint:
                        raise ValueError("noncanonical listing date")
            except (ValueError, TypeError, IndexError) as exc:
                raise ReconciliationRefused("invalid listing candidate identity/date") from exc
            if (candidate_url != candidate.canonical_url
                    or candidate_id != candidate.source_identity
                    or category_from_url != candidate.category_from_permalink):
                raise ReconciliationRefused("listing candidate canonical identity disagreement")
            if candidate_id in local_ids:
                raise ReconciliationRefused("duplicate candidate on category page")
            local_ids.add(candidate_id)
            existing = by_id.get(candidate_id)
            if existing is None:
                by_id[candidate_id] = (candidate.canonical_url, candidate.date_hint, {category})
            else:
                previous_url, previous_hint, pages = existing
                if previous_url != candidate.canonical_url:
                    raise ReconciliationRefused("same article ID has conflicting canonical URLs")
                if previous_hint is not None and candidate.date_hint is not None and previous_hint != candidate.date_hint:
                    raise ReconciliationRefused("conflicting listing hints for same article")
                pages.add(category)
                by_id[candidate_id] = (previous_url, previous_hint or candidate.date_hint, pages)
        by_page[category] = len(local_ids)
    if set(by_page) != set(listings.CATEGORY_URLS):
        raise ReconciliationRefused("four-category observation incomplete")

    candidate = by_id.get(article_id)
    if candidate is None:
        hint, pages, status = None, [], "not_visible_in_observed_pages"
    else:
        found_url, hint, associated_pages = candidate
        if found_url != article.url:
            raise ReconciliationRefused("article/listing canonical URL collision")
        pages = sorted(associated_pages)
        status = ("no_listing_date_hint" if hint is None
                  else "matches_article_date" if hint == page_date
                  else "date_hint_disagrees")
    return {
        "schema": "ipr-vndj-listing-article-reconciliation/1",
        "source_slug": identity.SOURCE_SLUG,
        "source_identity": article_id,
        "canonical_url": article.url,
        "source_type": "journal_commentary_not_ministry_directive",
        "article_page_date": page_date,
        "article_page_date_basis": "in_memory_article_specific_publication_stamp",
        "article_date_human_verified": False,
        "listing_date_hint": hint,
        "listing_date_status": status,
        "listing_pages_observed": pages,
        "editorial_review_required": status != "matches_article_date",
        "historical_completeness_proven": False,
        "full_text_retention_authorized": False,
        "public_record_authorized": False,
    }
