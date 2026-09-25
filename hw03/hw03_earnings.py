"""
hw03_earnings.py
MIS3060 - Business Intelligence with AI - HW03 (Specification A: Earnings Pipeline)

Extracts quarterly earnings from SEC Form 8-K filings (Item 2.02) for five
companies and saves the results to hw03/earnings_history.csv.

Run from the repo root or from inside hw03/:
    python hw03/hw03_earnings.py
"""

import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HEADERS = {"User-Agent": "MIS3060 Villanova dpollo01@villanova.edu"}
REQUEST_PAUSE = 0.2          # seconds between requests (SEC max = 10 req/sec)
FILINGS_PER_COMPANY = 4
NOT_FOUND = "NOT_FOUND"

COMPANIES = [
    ("Apple Inc.", "AAPL", "0000320193"),
    ("Microsoft Corporation", "MSFT", "0000789019"),
    ("NVIDIA Corporation", "NVDA", "0001045810"),
    ("JPMorgan Chase & Co.", "JPM", "0000019617"),
    ("Walmart Inc.", "WMT", "0000104169"),
]

# CSV lives next to this script, i.e. hw03/earnings_history.csv
OUTPUT_CSV = Path(__file__).resolve().parent / "earnings_history.csv"
CSV_COLUMNS = ["company", "ticker", "cik", "filing_date", "period",
               "revenue_reported", "eps_diluted", "net_income"]


# ---------------------------------------------------------------------------
# HTTP helper - every request uses the User-Agent and pauses afterwards
# ---------------------------------------------------------------------------
def sec_get(url):
    """GET a URL with the required User-Agent, then pause 0.2 seconds."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response
    finally:
        time.sleep(REQUEST_PAUSE)


# ---------------------------------------------------------------------------
# Steps 2-4: submissions API -> four most recent 8-K / Item 2.02 filings
# ---------------------------------------------------------------------------
def get_earnings_filings(cik):
    """Return the four most recent 8-K filings whose items include 2.02."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    recent = sec_get(url).json()["filings"]["recent"]

    matches = []
    for i, form in enumerate(recent["form"]):
        items = recent["items"][i] or ""
        if form == "8-K" and "2.02" in items:
            matches.append({
                "accession": recent["accessionNumber"][i],
                "filing_date": recent["filingDate"][i],
                "primary_doc": recent["primaryDocument"][i],
            })

    # EDGAR lists "recent" newest-first, but sort anyway to be safe
    matches.sort(key=lambda f: f["filing_date"], reverse=True)
    return matches[:FILINGS_PER_COMPANY]


# ---------------------------------------------------------------------------
# Step 5: filing index -> earnings press release exhibit (EX-99.1)
# ---------------------------------------------------------------------------
EX991_PATTERN = re.compile(r"ex(hibit)?[-_.]?99[-_.]?0?1(?!\d)", re.IGNORECASE)
EX99_PATTERN = re.compile(r"ex(hibit)?[-_.]?99", re.IGNORECASE)


def find_press_release(cik, accession, primary_doc):
    """Return the URL of the earnings press release exhibit, or None."""
    cik_no_zeros = str(int(cik))
    acc_no_dashes = accession.replace("-", "")
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{acc_no_dashes}/"

    # Attempt 1: read the folder listing and look for an ex99 .htm file name
    soup = BeautifulSoup(sec_get(index_url).text, "html.parser")
    htm_files = []
    for link in soup.find_all("a", href=True):
        name = link["href"].rstrip("/").split("/")[-1]
        if name.lower().endswith(".htm") and name != primary_doc \
                and not name.lower().endswith("-index.htm") \
                and not name.lower().endswith("-index-headers.htm"):
            if name not in htm_files:
                htm_files.append(name)

    for pattern in (EX991_PATTERN, EX99_PATTERN):
        for name in htm_files:
            if pattern.search(name):
                return index_url + name

    # Attempt 2: some companies (e.g., NVIDIA) use names like "q3fy25pr.htm",
    # so fall back to the "-index.htm" page, which lists each document's Type.
    detail_url = f"{index_url}{accession}-index.htm"
    soup = BeautifulSoup(sec_get(detail_url).text, "html.parser")
    fallback = None
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        doc_type = cells[3].get_text(strip=True).upper()
        link = cells[2].find("a", href=True)
        if not link or not link["href"].lower().endswith(".htm"):
            continue
        name = link["href"].split("/")[-1]
        if doc_type == "EX-99.1":
            return index_url + name
        if doc_type.startswith("EX-99") and fallback is None:
            fallback = index_url + name

    return fallback


# ---------------------------------------------------------------------------
# Step 6: download exhibit and strip HTML to plain text
# ---------------------------------------------------------------------------
def get_plain_text(url):
    """Download an exhibit and return its plain text (whitespace collapsed)."""
    soup = BeautifulSoup(sec_get(url).content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = text.replace("\xa0", " ").replace("’", "'")
    return re.sub(r"\s+", " ", text)


# ---------------------------------------------------------------------------
# Step 7: extract the four fields with regular expressions
# ---------------------------------------------------------------------------
MONEY = r"\$\s*([\d,]+(?:\.\d+)?)\s*(billion|million)"   # "$94.9 billion"
TABLE_NUM = r"\$?\s*([\d,]{3,}(?:\.\d+)?)"                 # "$ 94,930" (table, in millions)
EPS_NUM = r"\$\s*(\d{1,3}\.\d{2})"                        # "$0.97"


def first_match(text, patterns):
    """Return the first regex match object across a list of patterns."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match
    return None


def extract_revenue(text):
    # Narrative sentences, e.g. "quarterly revenue of $94.9 billion",
    # "Revenue was $65.6 billion", "net revenue of $43.3 billion"
    narrative = [
        r"(?:quarterly|total|consolidated|net|reported) revenues?[^$.]{0,60}?" + MONEY,
        r"revenues?[^$.]{0,60}?" + MONEY,
        r"(?:total )?net sales[^$.]{0,60}?" + MONEY,
    ]
    match = first_match(text, narrative)
    if match:
        return f"${match.group(1)} {match.group(2).lower()}"

    # Financial statement tables (amounts shown in millions)
    tables = [
        r"Total net sales\s*" + TABLE_NUM,
        r"Total (?:net )?revenues?\s*" + TABLE_NUM,
        r"\bRevenues?\s*" + TABLE_NUM,
    ]
    match = first_match(text, tables)
    if match:
        return f"${match.group(1)} million"
    return NOT_FOUND


def extract_eps(text):
    patterns = [
        r"diluted (?:earnings|net income) per (?:common )?share[^$]{0,60}?" + EPS_NUM,
        r"earnings per diluted share[^$]{0,60}?" + EPS_NUM,
        r"diluted EPS[^$]{0,40}?" + EPS_NUM,
        EPS_NUM + r" (?:of )?(?:per )?diluted (?:earnings per )?share",
        r"GAAP EPS[^$]{0,40}?" + EPS_NUM,
        EPS_NUM + r" per (?:common )?share",
        r"\bDiluted\s*" + EPS_NUM.replace(r"\$\s*", r"\$?\s*"),   # table row
    ]
    match = first_match(text, patterns)
    return f"${match.group(1)}" if match else NOT_FOUND


def extract_net_income(text):
    # Narrative, e.g. "Net income was $24.7 billion", "net income of $12.9 billion"
    narrative = [
        r"net income(?: attributable to [A-Za-z.,&' ]{1,40})?[^$.]{0,40}?" + MONEY,
    ]
    match = first_match(text, narrative)
    if match:
        return f"${match.group(1)} {match.group(2).lower()}"

    # Table row, e.g. "Net income $ 14,736" or
    # "Consolidated net income attributable to Walmart $ 4,579" (in millions)
    tables = [
        r"net income attributable to [A-Za-z.,&' ]{1,40}?\s*" + TABLE_NUM,
        r"\bNet income\s*" + TABLE_NUM,
    ]
    match = first_match(text, tables)
    if match:
        return f"${match.group(1)} million"
    return NOT_FOUND


QUARTERS = {"first": "first", "second": "second", "third": "third", "fourth": "fourth",
            "1": "first", "2": "second", "3": "third", "4": "fourth"}

# Sentences containing these words usually describe a different quarter
# (next-quarter outlook or a prior-year comparison), so they are skipped.
PERIOD_SKIP_WORDS = re.compile(
    r"\b(outlook|expects?|expected|expecting|guidance|compared|comparison|"
    r"forecasts?|anticipat\w*|versus|vs\.|year-ago|prior[- ]year|next quarter)\b",
    re.IGNORECASE,
)
OPENING_CHARS = 2500     # roughly the headline plus the opening paragraph

_Q = r"(first|second|third|fourth)"
_YR = r"(\d{4}|\d{2})"


def _full_year(yr):
    return yr if len(yr) == 4 else "20" + yr


# Each entry: (compiled pattern, function that turns the match into a period string)
PERIOD_PATTERNS = [
    # "fourth quarter fiscal 2024", "third quarter of fiscal year 2025",
    # "third-quarter 2024", "Fourth Quarter and Fiscal 2026", "fourth quarter and full year 2025"
    (re.compile(_Q + r"[- ]quarter(?: and(?: full)?)?(?: of)?( fiscal)?(?: year)? (\d{4})\b",
                re.IGNORECASE),
     lambda m: f"{m.group(1).lower()} quarter{' fiscal' if m.group(2) else ''} {m.group(3)}"),
    # "fiscal 2025 fourth quarter" (Apple style)
    (re.compile(r"fiscal(?: year)? (\d{4}) " + _Q + r"[- ]quarter", re.IGNORECASE),
     lambda m: f"{m.group(2).lower()} quarter fiscal {m.group(1)}"),
    # "Q3 FY26", "Q3 fiscal 2026", "Q3 fiscal year 2026" (Walmart style)
    (re.compile(r"\bQ([1-4])\s*(?:FY|fiscal(?: year)?\s)\s*'?" + _YR + r"\b", re.IGNORECASE),
     lambda m: f"{QUARTERS[m.group(1)]} quarter fiscal {_full_year(m.group(2))}"),
    # "FY26 Q3"
    (re.compile(r"\bFY\s*'?" + _YR + r"\s*Q([1-4])\b", re.IGNORECASE),
     lambda m: f"{QUARTERS[m.group(2)]} quarter fiscal {_full_year(m.group(1))}"),
]
QUARTER_ENDED = re.compile(r"quarter ended ([A-Z][a-z]+ \d{1,2}, \d{4})")


def split_sentences(text):
    """Rough sentence split. Headlines have no period, so they join the first sentence."""
    return re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", text)


def first_period_in(sentences):
    """Return the period mentioned earliest, reading sentences in order and
    skipping any sentence that talks about outlook, guidance or comparisons."""
    for sentence in sentences:
        if PERIOD_SKIP_WORDS.search(sentence):
            continue
        found = [(m.start(), fmt(m)) for pattern, fmt in PERIOD_PATTERNS
                 for m in [pattern.search(sentence)] if m]
        if found:
            return min(found)[1]          # earliest position in the sentence wins
    return None


def first_quarter_ended_in(sentences):
    for sentence in sentences:
        if PERIOD_SKIP_WORDS.search(sentence):
            continue
        m = QUARTER_ENDED.search(sentence)
        if m:
            return f"quarter ended {m.group(1)}"
    return None


def extract_period(text):
    opening = split_sentences(text[:OPENING_CHARS])
    rest = split_sentences(text[OPENING_CHARS:])

    # 1) headline/opening paragraph first, 2) then the rest of the release
    for sentences in (opening, rest):
        period = first_period_in(sentences) or first_quarter_ended_in(sentences)
        if period:
            return period
    return NOT_FOUND


def extract_fields(text):
    return {
        "period": extract_period(text),
        "revenue_reported": extract_revenue(text),
        "eps_diluted": extract_eps(text),
        "net_income": extract_net_income(text),
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main():
    rows = []

    for company, ticker, cik in COMPANIES:
        print(f"\n=== {company} ({ticker}) ===")
        try:
            filings = get_earnings_filings(cik)
        except Exception as e:
            print(f"WARNING: could not load submissions for {ticker}: {e}")
            continue

        if not filings:
            print(f"WARNING: no 8-K Item 2.02 filings found for {ticker}")
            continue

        for filing in filings:
            try:
                exhibit_url = find_press_release(cik, filing["accession"],
                                                 filing["primary_doc"])
                if exhibit_url is None:
                    print(f"WARNING: no press release exhibit found for {ticker} "
                          f"filing {filing['accession']} ({filing['filing_date']}) - skipping")
                    continue

                text = get_plain_text(exhibit_url)
                fields = extract_fields(text)

                row = {
                    "company": company,
                    "ticker": ticker,
                    "cik": cik,
                    "filing_date": filing["filing_date"],
                    **fields,
                }
                rows.append(row)

                print(f"{ticker} | {row['period']} | Revenue: {row['revenue_reported']} | "
                      f"EPS: {row['eps_diluted']} | Net Income: {row['net_income']}")

            except Exception as e:
                print(f"WARNING: error processing {ticker} filing "
                      f"{filing.get('accession')}: {e} - skipping")
                continue

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
