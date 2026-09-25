# HW3 Specifications

## Specification A — Earnings Pipeline (hw03/hw03_earnings.py)

### Goal
Write a Python script that extracts quarterly earnings from SEC
Form 8-K filings (Item 2.02) for five companies and saves the results
to a CSV file.

### Companies
Apple Inc. | AAPL | 0000320193
Microsoft Corporation | MSFT | 0000789019
NVIDIA Corporation | NVDA | 0001045810
JPMorgan Chase & Co. | JPM | 0000019617
Walmart Inc. | WMT | 0000104169

### Steps
1. On every HTTP request, set the User-Agent header to:
   "MIS3060 Villanova dpollo01@villanova.edu"
2. For each company, request the EDGAR submissions API at:
https://data.sec.gov/submissions/CIK{cik}.json 
3. Keep only filings where the form is 8-K and the `items` field
   contains "2.02".
4. Select the four most recent matching filings per company.
5. For each filing, build the filing index URL:
   https://www.sec.gov/Archives/edgar/data/{CIK without leading zeros}/{accession number without dashes}/
   then find the earnings press release exhibit (a .htm file, usually named ex99 / Exhibit 99.1).
6. Download the exhibit and use beautifulsoup4 to strip the HTML into plain text.
7. From the plain text, extract these 4 fields:
   - Quarterly revenue (in millions or billions)
   - Diluted EPS (per-share figure)
   - Net income
   - Reporting period (e.g., "fourth quarter fiscal 2024")
8. Pause 0.2 seconds between requests to respect SEC's rate limit
   (10 requests/second max).

### Output
- Print one line per filing in this format:
[Ticker] | [Period] | Revenue: $X | EPS: $X | Net Income: $X
- Save all rows to hw03/earnings_history.csv
  with these columns in order:
company, ticker, cik, filing_date, period, revenue_reported, eps_diluted, net_income
- Print a confirmation message after the CSV is saved.

### Error handling
- If a field can't be extracted, store the string "NOT_FOUND" instead of
  leaving it blank, because blank cells and missing data are different things.
- If a filing's press release exhibit can't be found, print a warning and
  continue to the next filing (do not crash).
- Wrap each filing in try/except so one bad filing doesn't stop the script.

## Specification B — Executive Events Pipeline (hw03/hw03_executives.py)

### Goal
Write a Python script that finds executive departures and appointments reported in
SEC 8-K filings (Item 5.02) over the past 12 months for five
companies and saves them to a CSV.

### Companies
Same five companies and CIKs as Specification A.

### Steps
1. Use the same User-Agent header on every request.
2. For each company, request the same EDGAR submissions API URL.
3. Keep only 8-K filings where `items` contains "5.02" AND the
   `filingDate` field is within the past 12 months (calculated from
   today's date, not hard-coded).
4. For each matching filing, download the full 8-K document and strip
   the HTML to plain text.
5. From the Item 5.02 section, extract:
   - event type: "departure", "appointment", or "both"
   - the person's full name
   - their title 
   - the effective date of the change
6. Hint words for classifying events:
   - departure: resign, retire, step down, depart
   - appointment: appoint, elect, name, promote

### Output
- Print one line per event in this format:
[Ticker] | [Date] | [Event Type] | [Name] | [Title]
- Save all events to hw03/executive_events.csv
  with these columns in order:
company, ticker, cik, filing_date, event_type, person_name, title, effective_date
- Print a confirmation message after the CSV is saved.

### Error handling
- If one filing reports multiple events (e.g., a departure AND an
  appointment), create a separate row for each event.
- If a company has zero 5.02 filings in the past 12 months, print:
  "[Ticker]: No executive events in past 12 months"
  This is valid data, not an error.
- Store "NOT_FOUND" for any field that can't be extracted.
- Still write the CSV with column headers even if there are zero events.