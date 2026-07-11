"""SEC EDGAR ingest source (MVP_PLAN.md §7's "optional convenience" beyond
paste-only text). Fetches a real filing by ticker + form type from SEC's
public, no-auth APIs, strips it to plain text, and hands back the same shape
ingest_service.ingest_text() already consumes -- same real-data-only path,
a second real source instead of paste-only.

SEC requires a real identifying User-Agent on every request (fair-access
policy) -- not optional, requests without one get rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

USER_AGENT = "Neurosymbolic-KG research contact@example.com"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# Real filings run ~400K+ characters (confirmed live: a real 10-K came back
# at ~430K chars) -- unbounded, that blows past any practical LLM context/
# latency budget for a single extraction call. Truncate to the opening
# section, where the entity/relationship-dense material (company name,
# subsidiaries, business description) concentrates.
MAX_FILING_CHARS = 8000
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{document}"

_HEADERS = {"User-Agent": USER_AGENT}


@dataclass(frozen=True)
class EdgarFiling:
    ticker: str
    form_type: str
    filed_at: str
    text: str
    source_url: str


def _cik_for_ticker(ticker: str) -> str | None:
    resp = httpx.get(TICKERS_URL, headers=_HEADERS, timeout=10.0)
    resp.raise_for_status()
    ticker_upper = ticker.upper()
    for entry in resp.json().values():
        if entry.get("ticker") == ticker_upper:
            return str(entry["cik_str"]).zfill(10)
    return None


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;|&amp;|&#\d+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _skip_to_narrative(text: str) -> str:
    """Real SEC filings open with an XBRL cover-page metadata block (tag
    URLs, CIK numbers -- confirmed live: ~39K characters of it on a real
    10-K), and the first "Item 1." match is the table of contents, not the
    real section. The second "item 1." occurrence is reliably the actual
    "ITEM 1. BUSINESS" narrative section. Falls back to the start of the
    document if the pattern isn't found (e.g. shorter filings with no TOC)."""
    lowered = text.lower()
    first = lowered.find("item 1.")
    if first == -1:
        return text
    second = lowered.find("item 1.", first + 1)
    return text[second:] if second != -1 else text[first:]


def fetch_filing(ticker: str, form_type: str) -> EdgarFiling | None:
    """Returns the most recent filing of form_type for ticker, or None if
    the ticker isn't a real SEC-registered company or has no such filing."""
    cik = _cik_for_ticker(ticker)
    if cik is None:
        return None

    resp = httpx.get(_SUBMISSIONS_URL.format(cik=cik), headers=_HEADERS, timeout=10.0)
    resp.raise_for_status()
    recent = resp.json()["filings"]["recent"]

    for i, form in enumerate(recent["form"]):
        if form != form_type:
            continue
        accession_nodash = recent["accessionNumber"][i].replace("-", "")
        document = recent["primaryDocument"][i]
        url = _ARCHIVE_URL.format(cik_int=int(cik), accession_nodash=accession_nodash, document=document)
        doc_resp = httpx.get(url, headers=_HEADERS, timeout=20.0)
        doc_resp.raise_for_status()
        text = _skip_to_narrative(_strip_html(doc_resp.text))[:MAX_FILING_CHARS]
        return EdgarFiling(
            ticker=ticker.upper(), form_type=form_type,
            filed_at=recent["filingDate"][i], text=text, source_url=url,
        )
    return None
