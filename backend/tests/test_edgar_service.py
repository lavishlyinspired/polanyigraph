"""Integration tests for services/edgar_service.py against the real, public
SEC EDGAR API (no API key needed) -- MVP_PLAN.md §7's "optional convenience"
ingest source, same real-data-only discipline as this repo's Neo4j/GraphDB
tests: real service, skip cleanly if unreachable, no mocking."""

from __future__ import annotations

import httpx
import pytest

from services import edgar_service


@pytest.fixture(autouse=True)
def _skip_if_sec_unreachable():
    try:
        resp = httpx.get(
            edgar_service.TICKERS_URL,
            headers={"User-Agent": edgar_service.USER_AGENT},
            timeout=5.0,
        )
        resp.raise_for_status()
    except Exception:
        pytest.skip("SEC EDGAR API not reachable")


def test_fetch_filing_returns_real_apple_10k():
    filing = edgar_service.fetch_filing("AAPL", "10-K")

    assert filing is not None
    assert filing.ticker == "AAPL"
    assert filing.form_type == "10-K"
    assert len(filing.text) > 1000
    assert filing.source_url.startswith("https://www.sec.gov/Archives/")


def test_fetch_filing_truncates_real_filings_to_a_bounded_size():
    """Live discovery: a real 10-K is ~430K characters -- unbounded, that
    blows past any practical LLM context/latency budget for extraction.
    Real filings must come back truncated to something an extraction call
    can actually handle."""
    filing = edgar_service.fetch_filing("TSLA", "10-K")

    assert filing is not None
    assert len(filing.text) <= edgar_service.MAX_FILING_CHARS


def test_fetch_filing_skips_xbrl_boilerplate_to_real_narrative_text():
    """Live discovery: the first ~39K characters of a real 10-K are XBRL
    cover-page metadata (tag URLs, CIK numbers), and the first "Item 1."
    match is the table of contents, not the real section -- naive [:N]
    truncation captured only junk tags, not prose. Must skip to the second
    "item 1." occurrence, which is the real "ITEM 1. BUSINESS" section."""
    filing = edgar_service.fetch_filing("TSLA", "10-K")

    assert filing is not None
    assert "item 1" in filing.text.lower()
    assert "http://fasb.org" not in filing.text


def test_fetch_filing_returns_none_for_unknown_ticker():
    filing = edgar_service.fetch_filing("NOT-A-REAL-TICKER-XYZ", "10-K")
    assert filing is None


def test_fetch_filing_returns_none_when_form_type_not_found():
    filing = edgar_service.fetch_filing("AAPL", "NOT-A-REAL-FORM-TYPE")
    assert filing is None
