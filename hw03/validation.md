# HW3 Validation

## 5A — Known-Answer Check: Earnings (Apple, Q3 FY2026)

| Check | Official Source | Your CSV | Match? |
|---|---|---|---|
| Apple Q3 FY26 Revenue | $109.4 billion ([Apple Newsroom](https://www.apple.com/newsroom/2026/07/apple-reports-third-quarter-results/)) | $109.4 billion | Yes |
| Apple Q3 FY26 EPS Diluted | $2.02 ([Apple Newsroom](https://www.apple.com/newsroom/2026/07/apple-reports-third-quarter-results/)) | $2.02 | Yes |

## 5B — Known-Answer Check: Executive Events

Event checked: Apple, filed 2026-04-20 — Tim Cook departure as CEO

| Check | News Source Confirms? | Notes |
|---|---|---|
| Person name and title | Yes | Tim Cook, Chief Executive Officer ([Apple Newsroom](https://www.apple.com/newsroom/2026/04/tim-cook-to-become-apple-executive-chairman-john-ternus-to-become-apple-ceo/)) |
| Event type (departure/appointment) | Partially | He is leaving the CEO role, but moving to executive chairman of the board rather than leaving Apple. "Departure" is accurate for the CEO title; the script didn't capture his new role. |
| Effective date | Yes | CSV effective_date: 2026-09-01; news says: September 1, 2026 |

## 5C — Cross-Validation: Earnings via Yahoo Finance (AAPL)

| Metric | From 8-K text extraction | From yfinance | Match? |
|---|---|---|---|
| Revenue | $109.4 billion | $109,417,000,000 ($109.4 billion) | Yes |
| Net Income | $29,789 million | $29,789,000,000 ($29,789 million) | Yes |

Explanation of any differences: Both sources agree once units are converted. The
8-K press release rounds revenue to $109.4 billion, while yfinance reports the
exact figure ($109,417,000,000). yfinance labels the quarter as ending 2026-06-30,
but Apple's fiscal Q3 actually ended June 27, 2026, since Apple's fiscal quarters
end on the last Saturday of the month. It is the same quarter, not a period mismatch.

## 5D — Pipeline Integrity Checks

| Check | Expected | Actual | Pass/Fail |
|---|---|---|---|
| `earnings_history.csv` row count | Up to 20 (5 companies × 4 quarters) | 20 | Pass |
| `executive_events.csv` row count | At least 0 (document actual) | 28 | Pass |
| `corporate_events_timeline.csv` created | Yes | Yes (28 rows) | Pass |
| Rows with all three fields `"NOT_FOUND"` | 0 (investigate if > 0) | 0 | Pass |