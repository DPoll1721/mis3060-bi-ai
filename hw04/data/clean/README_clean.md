# Wildcat Capital — Clean Data (HW4)
Produced by `scripts/02_clean.py` from `data/raw/`. Decisions: see `decision_log.md`. Audit trail: `data/audit/`.

## Row counts (raw = clean + quarantined)
| Table | Raw | Clean | Quarantined |
|---|---:|---:|---:|
| dim_advisor | 25 | 25 | 0 |
| dim_client | 2,525 | 2,500 | 25 (duplicate clients) |
| dim_date | 1,827 | 1,827 | 0 |
| dim_security | 500 | 500 | 0 |
| dim_benchmark | 8 | 8 | 0 |
| fact_fees | 122,197 | 122,197 | 0 |
| fact_portfolio_snapshot | 129,547 | 129,547 | 0 |
| fact_transactions | 298,772 | 298,572 | 200 (orphan client_id) |

## Relationships (star schema)
All are many-to-one, from the fact (or child) table to the dimension.
| From | → To | Notes |
|---|---|---|
| dim_client.advisor_id | dim_advisor.advisor_id | |
| dim_security.benchmark_id | dim_benchmark.benchmark_id | |
| fact_fees.client_id | dim_client.client_id | |
| fact_fees.advisor_id | dim_advisor.advisor_id | |
| fact_portfolio_snapshot.client_id | dim_client.client_id | |
| fact_portfolio_snapshot.advisor_id | dim_advisor.advisor_id | |
| fact_portfolio_snapshot.benchmark_id | dim_benchmark.benchmark_id | |
| fact_transactions.client_id | dim_client.client_id | |
| fact_transactions.advisor_id | dim_advisor.advisor_id | |
| fact_transactions.security_id | dim_security.security_id | blank on cash rows (Deposit/Withdrawal/Advisory Fee), by design |
| fact_fees.fee_date | dim_date.date | first of month |
| fact_portfolio_snapshot.snapshot_date | dim_date.date | first of month |
| fact_transactions.txn_date | dim_date.date | daily |

Note: advisor_id appears on both the facts and dim_client (and always agrees). In a BI model, relate the facts to dim_advisor directly, or go through dim_client, but not both, to avoid an ambiguous path.

## Column types a BI tool needs
- **Text (do not auto-detect as number):** `zip_code` (232 have a leading 0, e.g. 03897), `primary_account_type` / `account_type` ("529" is a label, not a number), `certifications` ("None" = no certification, not null).
- **Whole number:** all `*_id` columns, `age`, `years_experience`, `aum_target_mm`, `year`, `month`, `quarter`, `week_of_year`, all `flag_*` columns.
- **Decimal:** `initial_aum`, `aum`, `aum_basis`, `amount`, `shares`, `price`, `bps_charged`, `expense_ratio_bps`, `cash_pct`.
- **Decimal, shown as %:** `return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd` are **fractions** (0.0928 = 9.28%). Format as percentage; do not divide again.
- **Date (YYYY-MM-DD):** `date`, `client_since`, `fee_date`, `snapshot_date`, `txn_date`.
- **True/False:** `is_active`, `is_etf`. **0/1:** `is_month_end`, `is_quarter_end`, `is_year_end`, `is_trading_day`.
- **Blanks are legitimate** in: `fact_transactions.security_id/shares/price` (cash rows), `dim_security.sector` (ETFs), `dim_security.expense_ratio_bps` (stocks).

## Flag columns added (0/1)
| Table | Column | Rows = 1 | Meaning |
|---|---|---:|---|
| dim_client | flag_risk_profile_imputed | 75 | risk_profile filled as "Balanced" from benchmark 3 (decision D3) |
| fact_transactions | flag_nontrading_day | 41,725 | Buy/Sell dated on a weekend or market holiday (F6) |
| fact_transactions | flag_after_account_close | 2,410 | dated after the client's last snapshot month; all inactive clients (F7) |
| fact_portfolio_snapshot | flag_aum_placeholder | 420 | aum = 1,000.00 placeholder, not a real balance (F10) |
| fact_fees | flag_aum_placeholder | 386 | fee charged on the 1,000.00 placeholder AUM (F10) |
| fact_portfolio_snapshot | flag_return_outlier | 1,282 | \|return_ytd\| or \|active_alpha_ytd\| > 100% (F11) |

## Known limitations (not fixed, with reasons)
1. **Dividend amounts = full position value** (53,864 rows). There is no dividend-per-share data to recompute them. Do **not** sum dividends as income.
2. **Advisory Fee transactions don't reconcile to fact_fees** (match in 1 of 28,746 client-months). fact_fees reconciles to AUM × bps ÷ 10,000 ÷ 12 and to snapshot AUM with 0 mismatches, so **use fact_fees for fee revenue**.
3. **AUM placeholder 1,000.00** (420 snapshots) is flagged, not replaced. Interpolating would invent balances. Filter `flag_aum_placeholder = 0` for AUM trends.
4. **Return outliers** (1,282 snapshots) are internally consistent (alpha = return − benchmark), so they were flagged, not changed. Use medians or filter the flag for average-return charts.
5. **Holidays:** only fixed-date NYSE holidays (New Year, July 4, Christmas) were corrected in dim_date. Floating holidays (MLK, Presidents Day, Good Friday, Memorial Day, Labor Day, Thanksgiving) are still marked as trading days.
6. **200 orphan transactions** (client IDs 2702–3192) are quarantined. If those clients exist in a source system, client totals are understated by 0.07% of rows.
7. **Order effect:** the audit found 836 negative-share Buys; the clean script fixed 835, because 1 belonged to an orphan client and was quarantined first.
8. **dim_benchmark 6** (MSCI Emerging Markets) is referenced by no security or snapshot; kept as a valid reference row.