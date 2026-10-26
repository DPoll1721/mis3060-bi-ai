# Wildcat Capital — Data Cleaning Report
**To:** Portfolio Committee  **From:** Drew Pollock, MIS3060  **Re:** Data warehouse extract, 2020–2024

## Executive summary
The eight-table warehouse extract (555,401 rows) was audited with 163 automated checks, cleaned by a script that stops if any fix fails its own test, and re-validated. The clean data is ready for the Power BI star schema: **every relationship between tables now matches 100%**, and every table scores 100% on completeness, key uniqueness, type validity and rule compliance.

Two problems would have broken reporting outright: **197,175 trades and dividends (66% of all transactions) could not be linked to their security** because of a number-format error, and **25 clients were entered twice**, inflating the client count from 2,500 to 2,525. Both are fixed. No data was invented: 225 rows that could not be repaired were moved to a quarantine file rather than deleted, and values that look wrong but cannot be proven wrong are **flagged** for the committee rather than changed.

## Cleaning summary
| Issue | Table | Rows | Action |
|---|---|---:|---|
| security_id stored as "45.0" — 0% joined to securities | fact_transactions | 197,175 | Converted; join now 100% |
| Returns stored as text ("9.28%") | fact_portfolio_snapshot | 300 | Converted to fraction; verified against alpha |
| Duplicate clients (IDs 2501–2525) | dim_client | 25 | Quarantined |
| Transactions for clients that don't exist | fact_transactions | 200 | Quarantined |
| Full state names ("Pennsylvania") | dim_client | 78 | Standardized to USPS codes |
| Blank risk profile | dim_client | 75 | Filled "Balanced" from benchmark; flagged |
| Negative share counts on Buys | fact_transactions | 835 | Sign corrected; amount reconciles to the cent |
| Market holidays marked as trading days | dim_date | 14 | Corrected |
| Trades dated on weekends/holidays | fact_transactions | 41,725 | Flagged |
| Activity after an account closed | fact_transactions | 2,410 | Flagged |
| AUM = $1,000.00 placeholder | snapshots / fees | 420 / 386 | Flagged |
| Implausible returns (beyond ±100%) | fact_portfolio_snapshot | 1,282 | Flagged |

**Before vs. after (fact_transactions):** type validity 90.54% → 100%, rule pass 99.94% → 100%, referential match 81.95% → 100%. Raw rows (555,401) = clean rows (555,176) + quarantined rows (225), checked for every table.

## Key judgment calls
**1. Filling 75 blank risk profiles as "Balanced."** Filling a blank is normally guessing, but here a second table settles it: every one of these clients is benchmarked to the 60/40 Blend, and among clients with a known profile, that benchmark is used *only* by "Balanced" (757 of 757). *Risk:* if the firm makes exceptions to its benchmark policy, a few clients may be mislabeled. A flag column (`flag_risk_profile_imputed`) lets anyone exclude them.

**2. Correcting 835 negative share counts rather than quarantining them.** For every one of these Buys, |shares| × price equals the recorded amount to within one cent, so the trade size is confirmed and only the sign is wrong. *Risk:* if some were really sells entered as buys, the type stays wrong; nothing in the data suggests this.

**3. Flagging — not fixing — the $1,000 AUM placeholder and extreme returns.** 420 monthly balances sit at exactly $1,000.00 between normal months, and 1,282 snapshots show returns beyond ±100%. Replacing them would mean inventing balances. They are flagged so AUM-trend and average-return charts can exclude them. *Risk:* unfiltered averages will remain distorted.

**4. Treating fact_fees as the source of truth for fee revenue.** Fee debits in the transaction table match fact_fees in only 1 of 28,746 client-months. fact_fees, however, reconciles perfectly two independent ways: amount = AUM × bps ÷ 12 (0 mismatches), and its AUM equals the portfolio snapshot (0 mismatches). *Risk:* anyone summing "Advisory Fee" transactions will report a different revenue number.

## Limitations (not fixed)
- **Dividend amounts equal the full position value** (53,864 rows). With no per-share dividend data, they cannot be corrected. Do not report them as income.
- **Advisory Fee transactions do not reconcile** to fact_fees (see judgment call 4).
- **Only fixed-date holidays** (New Year, July 4, Christmas) were corrected in the calendar; floating holidays such as Thanksgiving are still marked as trading days.
- **200 quarantined transactions** reference client IDs 2702–3192, which are not in the client table. If these clients exist elsewhere, client totals are understated by 0.07%.
- **IQR outlier flags are not errors.** About 10% of AUM values exceed the IQR fence, because a few UHNW clients hold $5M–$50M. A flag is a reason to look, not proof of a mistake.

---
AI-assisted report — reviewed for factual accuracy on 10/26/26 by Drew Pollock