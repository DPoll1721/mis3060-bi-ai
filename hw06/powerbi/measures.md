# HW6 — Measure Library (`_Measures` table)

**Additivity patterns used** (from Assignment 5 Part C):

- **SUM**: fully additive facts (fees, flows) are added across every dimension, including time.
- **Last balance**: semi-additive `aum` is summed across clients on **one** date, never across dates. `LASTNONBLANK` picks the last snapshot in the filter.
- **Recompute-and-weight**: ratios are never summed or averaged. The numerator and denominator are recomputed in each filter context and then divided, or weighted by `aum`.

Snapshots are dated the **1st of each month** (last snapshot = 2024-12-01). Every measure below was reconciled to pandas (`reports/measure_reconciliation.csv`, 89/89 rows match).

---

## Base measures (from ICE 9/10)

### Total Fees — *SUM*
```dax
Total Fees = SUM ( fact_fees[amount] )
```
Total fee revenue billed in the period.

### Net Flows — *SUM*
```dax
Net Flows =
CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Deposit" )
    - CALCULATE ( SUM ( fact_transactions[amount] ), fact_transactions[txn_type] = "Withdrawal" )
```
New money clients brought in minus money they took out.

---

## 0. AUM (naive SUM) — ⚠️ WRONG, never use on a report
```dax
AUM (naive SUM) = SUM ( fact_portfolio_snapshot[aum] )
```
**Pattern:** plain SUM applied to a balance, **which is wrong**. It adds every monthly balance in the filter, so 2024 shows $135.5B (about 11 × the real $12.7B). It's kept only to show the trap. pandas makes the same mistake when told to, which the reconciliation proves.

## 1. Ending AUM — *last balance*
```dax
Ending AUM =
VAR LastSnap =
    LASTNONBLANK ( dim_date[date], CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) ) )
RETURN
    CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LastSnap )
```
How much Wildcat manages at the end of the selected period ($12.73B at 2024-12-01).
*Note:* the variable can't be named `LastDate`, because that's a reserved DAX function name.

## 2. Ending Clients — *last balance*
```dax
Ending Clients =
VAR LastSnap =
    LASTNONBLANK ( dim_date[date], CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) ) )
RETURN
    CALCULATE ( DISTINCTCOUNT ( fact_portfolio_snapshot[client_id] ), LastSnap )
```
How many clients hold assets with Wildcat at the end of the period (2,325).

## 3. Avg AUM per Client — *recompute-and-weight*
```dax
Avg AUM per Client = DIVIDE ( [Ending AUM], [Ending Clients] )
```
The typical relationship size at period end ($5.48M firm-wide; $39.5M UHNW vs $383K Retail).

## 4. Ending AUM LY / AUM YoY % — *last balance, time-shifted / recompute*
```dax
Ending AUM LY = CALCULATE ( [Ending AUM], SAMEPERIODLASTYEAR ( dim_date[date] ) )
AUM YoY % = DIVIDE ( [Ending AUM] - [Ending AUM LY], [Ending AUM LY] )
```
How much the book grew versus the same point last year (+19.6% in 2024). It's blank in 2020 because there's no prior year.

## 5. Ending AUM PM / AUM MoM % — *last balance, time-shifted / recompute*
```dax
Ending AUM PM = CALCULATE ( [Ending AUM], DATEADD ( dim_date[date], -1, MONTH ) )
AUM MoM % = DIVIDE ( [Ending AUM] - [Ending AUM PM], [Ending AUM PM] )
```
Month-over-month change in the book (+4.25% from the Nov to the Dec 2024 snapshot).

## 6. Avg Monthly AUM — *recompute-and-weight*
```dax
Avg Monthly AUM =
DIVIDE (
    SUM ( fact_portfolio_snapshot[aum] ),
    DISTINCTCOUNT ( fact_portfolio_snapshot[snapshot_date] )
)
```
The average balance Wildcat carried across the months in the filter ($11.29B in 2024). It's the right denominator for revenue-per-dollar measures, unlike the year-end balance.

## 7. Fee Yield (bps) — *recompute-and-weight, two fact tables*
```dax
Fee Yield (bps) =
DIVIDE ( [Total Fees] * 12 * 10000, SUM ( fact_portfolio_snapshot[aum] ) )
```
Annualized fee revenue per dollar of managed assets (43.2 bps in 2024; 82.8 Retail vs 36.1 UHNW). Fees come from `fact_fees` and AUM from `fact_portfolio_snapshot`. They're linked only through the shared `dim_date` and `dim_client` filters. See Part C(b).

## 8. Organic Growth Rate — *recompute*
```dax
Organic Growth Rate = DIVIDE ( [Net Flows], [Ending AUM LY] )
```
Growth from clients' own deposits and withdrawals, excluding market moves (0.73% firm-wide in 2024; 9.87% Retail). See Part C(d).

## 9. AUM-Weighted Alpha — *recompute-and-weight at the last balance*
```dax
AUM-Weighted Alpha =
VAR LastSnap =
    LASTNONBLANK ( dim_date[date], CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) ) )
RETURN
    CALCULATE (
        DIVIDE (
            SUMX (
                fact_portfolio_snapshot,
                fact_portfolio_snapshot[active_alpha_ytd] * fact_portfolio_snapshot[aum]
            ),
            SUM ( fact_portfolio_snapshot[aum] )
        ),
        LastSnap,
        fact_portfolio_snapshot[is_return_suspect] <> 1,
        NOT ISBLANK ( fact_portfolio_snapshot[active_alpha_ytd] )
    )
```
How much Wildcat's client dollars beat their benchmarks year-to-date (+1.45% in 2024). It's read only at the last snapshot because alpha is YTD, and it excludes suspect returns. See Part C(c).

## 10. Alpha Signal — *text from a recomputed measure*
```dax
Alpha Signal =
VAR a = [AUM-Weighted Alpha]
RETURN
    IF (
        ISBLANK ( a ),
        BLANK (),
        SWITCH ( TRUE (), a >= 0.02, "Outperforming", a <= -0.02, "Lagging", "In line" )
    )
```
A plain-English flag a manager can scan. In 2024 only Retail is "Outperforming" (+2.40%), and 2022 was the firm's only outperforming year.

## 11. Top 10 Client Share — *recompute-and-weight at the last balance* (Claude-assisted, see `claude/`)
```dax
Top 10 Client Share =
VAR LastSnap =
    LASTNONBLANK ( dim_date[Date], CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) ) )
VAR ClientAUM =
    FILTER (
        ADDCOLUMNS (
            VALUES ( dim_client[client_id] ),
            "@AUM", CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LastSnap )
        ),
        NOT ISBLANK ( [@AUM] )
    )
VAR Top10 =
    TOPN ( 10, ClientAUM, [@AUM], DESC, dim_client[client_id], ASC )
VAR Top10AUM =
    SUMX ( Top10, [@AUM] )
VAR TotalAUM =
    CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LastSnap )
RETURN
    DIVIDE ( Top10AUM, TotalAUM )
```
Concentration risk: the share of AUM that would be at risk if the 10 largest relationships in the selection left (6.16% firm-wide; 8.13% within UHNW). All clients are valued on **one** shared last date, so departed clients can't be ranked by an old balance.

---

# Part C — Design questions

## (a) Ending AUM vs SUMX over clients

| Calculation (no filters) | Value |
|---|---:|
| `[Ending AUM]` | $12,729,572,078.86 |
| `SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] )` | $13,149,297,713.80 |
| **Difference** | **$419,725,634.94** |

`[Ending AUM]` finds the last snapshot date in the filter (2024-12-01) and sums every client's balance **on that one date**. Inside `SUMX`, each client becomes its own filter context, so `LASTNONBLANK` finds **that client's** last snapshot. Clients who left the firm still show up at their final balance.

pandas confirms the difference to the cent: **175 clients** are absent from the 2024-12-01 snapshot, and their last balances sum to exactly **$419,725,634.94**. They left between Dec 2022 and Nov 2023. By tier, the departures were 9 UHNW clients ($252.1M), 50 HNW ($137.1M) and 116 Retail ($30.5M).

**"How much do we manage today?" is answered by `[Ending AUM]` ($12.73B).** The SUMX version mixes balances from different dates and counts $420M that has already left the firm. It describes each client's last balance whenever that was, not current AUM.

## (b) Fee Yield (bps) vs ICE 9 Effective Fee Rate (bps), 2024

| 2024 | Fees | Denominator | bps |
|---|---:|---:|---:|
| Effective Fee Rate (ICE 9) | $48,714,005.93 | Σ `fact_fees[aum_basis]` = $128.39B | **45.53** |
| Fee Yield (HW6) | $48,714,005.93 | Σ `fact_portfolio_snapshot[aum]` = $135.46B | **43.15** |

The numerators are identical. The difference is entirely in the denominator. pandas evidence:

- Of 27,900 snapshot client-months in 2024, **1,684 (6.0% of rows, 5.2% of AUM) have no matching fee record**. That AUM is in Fee Yield's denominator but earns no fee in the numerator.
- On the client-months that **do** have a fee record, `aum_basis` = snapshot `aum` exactly (ratio 1.0000), and Fee Yield on those rows alone is **45.53 bps**, identical to the Effective Fee Rate.
- Every client was billed at least once in 2024, and no fee row lacks a snapshot. So the gaps are individual **missing months**, spread across all tiers and all 12 months (154 in January, falling to 91 in December).

**Data limitation:** `fact_fees` does not cover every client-month in `fact_portfolio_snapshot`. The data can't tell us whether those 1,684 months were fee waivers, billing lags, or simply missing records. The Effective Fee Rate is the price charged **on billed assets**. Fee Yield is revenue per dollar of **all** managed assets, so it understates pricing if the records are missing, and correctly shows lost revenue if the fees were waived. Joining the two fact tables at a common grain is what exposed the gap.

## (c) AUM-Weighted Alpha: why the last snapshot, and why exclude suspects

At the 2024-12-01 snapshot (2,325 rows, of which 148 are suspect):

| Version | Alpha |
|---|---:|
| **Measure: AUM-weighted, suspects excluded** | **1.45%** |
| Simple mean, same rows (suspects excluded) | 0.88% |
| AUM-weighted, suspects **included** | 1.67% |
| Simple mean, suspects included | 15.56% |
| Wrong: AUM-weighted over **all** 2024 months | 0.32% |

**Why the last snapshot only:** `active_alpha_ytd` is **year-to-date**, so each month's value already includes all earlier months. The 2024 weighted alpha builds from −0.01% in January to 1.45% in December. Averaging the months mixes a January number (one month of performance) with a December number (a full year), which gives 0.32%. That figure doesn't measure any real period. Only the last snapshot gives the full-period figure, and for a balance-weighted measure the weights must be balances on that same date.

**Why exclude `is_return_suspect = 1`:** the 148 suspect rows hold only **0.1% of AUM**, but their alpha ranges from −120.9% to **+7,133.8%** (mean 231.6%). These are data errors, not performance. Including them raises the weighted figure from 1.45% to 1.67%, and it inflates the simple mean to an absurd 15.56%. AUM-weighting limits the damage, but excluding the bad rows is the right fix.

The gap between the simple mean (0.88%) and the weighted figure (1.45%) also shows that **larger accounts beat their benchmarks by more than small ones**. The firm's dollars outperformed by more than the typical client did.

## (d) Organic Growth Rate vs AUM YoY % by tier, 2024

| Tier | AUM YoY % | Organic Growth % | Non-flow growth (YoY − Organic) | Net flows | Share of firm net flows |
|---|---:|---:|---:|---:|---:|
| HNW | 19.64% | 1.18% | 18.46 pts | $25.2M | 32.5% |
| Retail | 19.13% | **9.87%** | 9.26 pts | $44.2M | **57.0%** |
| UHNW | 19.59% | 0.10% | 19.49 pts | $8.1M | 10.5% |
| **Firm** | **19.58%** | **0.73%** | 18.85 pts | $77.5M | 100% |

**What it says:** every tier grew about 19%, but almost none of that was new money. At the firm level, 0.73 points of the 19.58% came from net deposits and about 18.9 points came from something else, mostly market performance. **Retail is the only tier where clients are actively adding money.** Its organic growth (9.9%) is half of its total growth, and it supplies 57% of the firm's net new money with only 4% of AUM. UHNW, which holds 76% of AUM, grew almost entirely through the market (0.1% organic).

**What it does not tell you:**

- **Why the non-flow growth happened.** It's a residual. It mixes investment returns with fee deductions, dividends and any data effects, and it doesn't separate skill (alpha) from the market (benchmark return).
- **Whether flows came from new or existing clients.** Client counts are identical at the end of 2023 and 2024 (687 / 1,394 / 244), so 2024 net flows came from existing clients. The measure itself can't show that.
- **Profitability.** Retail's flows are large relative to its AUM but small in dollars ($44M vs the firm's $12.7B). At 82.8 bps vs UHNW's 36.1 bps, Retail's revenue impact is a separate question.
- **Timing.** The denominator is last year's ending balance, so a deposit in January and one in December count the same.
- **Tier history.** `client_tier` is the client's current tier, so clients who changed tiers are reported under their tier today.