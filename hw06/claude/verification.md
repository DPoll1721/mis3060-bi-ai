# Part D — Verification of Claude's `Top 10 Client Share`

Workflow: **Draft → Test → Debug → Review.** I exported the model metadata with the INFO.VIEW queries (`model_metadata.md`). I prompted Claude with that metadata plus what the metadata can't show: the grain, that `aum` is a balance, that alpha is YTD, and the business definition. The session is in `dax_session.md`.

## 1. Did it run as written? What did the test query return?

**Yes.** I pasted Claude's measure into `_Measures` unchanged. It ran with no errors and returned values between 0 and 1 in every context.

Claude's 4-part test query also ran. The only change I made was `"Gold"` → `"Retail"` in query 4 (see section 5).

| Test | Result |
|---|---|
| 1. Grand total | Last Snap Date **12/1/2024**, Ending AUM **$12,729,572,078.86**, Top 10 Share **6.16%** |
| 3. By tier, 2024 | HNW **3.14%**, Retail **1.83%**, UHNW **8.13%**, total row **6.16%** (all on 12/1/2024) |
| 4. Retail drill-down (top 12) | #1 client 1573 ($1,081,976.39) … #10 client 985 ($928,501.84), #11 client 222 ($914,405.62) |

**Hand check of query 4:** the top 10 Retail balances sum to **$9,787,902.89**. Divided by Retail Ending AUM of $533,452,497.89, that's **1.8348%**, which matches the measure's 0.018348218 for Retail.

## 2. Which rows of `measure_reconciliation.csv` prove it?

All four rows match the independent pandas version (rank clients at the last snapshot in the slice, tie-break by `client_id`, top 10 ÷ total):

| measure | slice | Power BI | pandas | match |
|---|---|---:|---:|---|
| Top 10 Client Share | Total | 0.0615893 | 0.0615893 | True |
| Top 10 Client Share | 2024\|HNW | 0.0313967 | 0.0313967 | True |
| Top 10 Client Share | 2024\|Retail | 0.0183482 | 0.0183482 | True |
| Top 10 Client Share | 2024\|UHNW | 0.0812643 | 0.0812643 | True |

## 3. Edge cases checked

1. **Grand total ≠ sum or average of the tiers.** The total (6.16%) is not 3.14% + 1.83% + 8.13%, nor their average. That's correct: TOPN re-ranks all clients firm-wide. 6.16% × $12.73B ≈ **$784.0M**, and 8.13% × $9.65B (UHNW) ≈ **$784.0M** too, so the firm's top 10 clients are all UHNW.
2. **The 2024 tier table (visual-level filter).** Each tier row ranks only that tier's clients. The Retail drill-down confirms it: every client in query 4 is Retail, and the hand-sum matches.
3. **Ties at rank 10.** None in Retail: #10 is $928,501.84 and #11 is $914,405.62. The `client_id ASC` tie-break would guarantee exactly 10 anyway, and pandas uses the same tie-break.
4. **Clients who left before the last snapshot.** 175 clients are missing from the 12/1/2024 snapshot (they left Dec 2022 – Nov 2023). Because every client is valued **on the shared `LastSnap` date**, they get a blank and are excluded from both the ranking and the denominator. A simpler `TOPN ( 10, VALUES ( client_id ), [Ending AUM] )` would have ranked them at their old balances. Part C(a) shows those old balances total $419.7M.
5. **Tiers with fewer than 10 clients.** Not possible in this data. The smallest tier, UHNW, has 244 clients at the last snapshot.

## 4. What I changed and why

**Nothing in the measure.** It matched pandas on every required slice, and its design (one shared `LastSnap`, then ADDCOLUMNS and TOPN with a tie-break) is better than the simple TOPN-over-`[Ending AUM]` version, for the reason in edge case 4.

In the **test query only**:

- I changed `"Gold"` → `"Retail"`. Claude invented a "Gold" tier. The real tiers are HNW, Retail and UHNW (from `INFO.VIEW.COLUMNS` and the data).
- I did **not** click "Update model with changes". That would have saved Claude's temporary `Last Snap Date` helper measure into the model.

## 5. Claims I confirmed or refuted

- **Refuted:** "It returns the last date where Gold clients hold any AUM (**normally 2024‑12‑31**)." Test query 1 returned **12/1/2024**. Snapshots are dated the **1st of each month**, not month-end. My prompt said "month-end snapshot_date" too, so Claude repeated my wrong assumption. The measure is still correct, because `LASTNONBLANK` finds the last date that has data, whatever day it is. This is why the grain has to be checked against the data, not just described.
- **Refuted:** "`account_type` suggests a client could have several rows on one date." A pandas/awk check of `fact_portfolio_snapshot` found **0 duplicate (client_id, snapshot_date) rows**, so the grain really is one row per client per snapshot. The measure's client-level sum is harmless but not needed.
- **Confirmed:** "The total is not the sum or average of the tier rows… the firm-wide top 10 may come mostly from one tier." The total of 6.16% isn't any combination of the tier values, and the $784.0M check shows the firm-wide top 10 come **entirely** from UHNW.