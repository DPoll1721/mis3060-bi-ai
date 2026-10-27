# HW5: Wildcat Capital Star Schema

## Part A — Keys

| Table | Type | Primary key | Foreign keys (column → table[column]) |
|---|---|---|---|
| dim_advisor | Dimension | `advisor_id` | — |
| dim_benchmark | Dimension | `benchmark_id` | — |
| dim_client | Dimension | `client_id` | `advisor_id` → dim_advisor[advisor_id] |
| dim_date | Dimension | `date_id` | — |
| dim_security | Dimension | `security_id` | `benchmark_id` → dim_benchmark[benchmark_id] |
| fact_fees | Fact | `fee_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`fee_date` → dim_date[date] |
| fact_portfolio_snapshot | Fact | `snapshot_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`benchmark_id` → dim_benchmark[benchmark_id]<br>`snapshot_date` → dim_date[date] |
| fact_transactions | Fact | `txn_id` | `client_id` → dim_client[client_id]<br>`advisor_id` → dim_advisor[advisor_id]<br>`security_id` → dim_security[security_id] *(can be blank)*<br>`txn_date` → dim_date[date] |

**Notes**
- `fact_transactions[security_id]` is legitimately blank on 101,528 cash rows (`txn_type` = Deposit, Withdrawal, Advisory Fee). Cash movements and fee debits don't involve a security, so there's nothing to point to. This is expected structure, not an orphan key.
- The fact date columns (`txn_date`, `fee_date`, `snapshot_date`) store calendar dates, so they match `dim_date[date]`, not `dim_date[date_id]` (an integer 1–1,827).
- Two foreign keys link one dimension to another: `dim_client[advisor_id]` and `dim_security[benchmark_id]`. These are snowflake links, covered in Part E(d).
- Uniqueness and referential integrity are proven in `check_keys.py`.

## Part B — Grain

- **fact_fees:** One row represents one fee charged to one client in one month (`client_id` + `fee_date` is unique; every `fee_date` is the 1st of the month, and `fee_type` describes the charge).
- **fact_portfolio_snapshot:** One row represents one client's account balance and performance as of the first day of one month (`client_id` + `snapshot_date` is unique).
- **fact_transactions:** One row represents a single transaction (a buy, sell, dividend, deposit, withdrawal, or advisory-fee debit) for one client on one date. No combination of descriptive columns is unique (622 duplicates on client + date + type + security), so `txn_id` is the only row identifier.

Grain uniqueness is checked in `check_keys.py` (section 6).

## Part C — Measures

**Additive** = can be summed across every dimension (clients, advisors, securities, and time).
**Semi-additive** = can be summed across some dimensions (e.g., clients) but not across time.
**Non-additive** = can never be summed; must be averaged (usually weighted) or recalculated.

### fact_fees
| Column | Type | How it may be aggregated |
|---|---|---|
| `amount` | Additive | Sum across clients, advisors, and months to get total fee revenue. |
| `aum_basis` | Semi-additive | A balance: sum across clients within one month for firm AUM, but never across months; use the latest month's value or average over time. |
| `bps_charged` | Non-additive | A rate: summing basis points is meaningless; use a weighted average, SUM(`amount`) ÷ SUM(`aum_basis`) × 12 × 10,000. |

### fact_portfolio_snapshot
| Column | Type | How it may be aggregated |
|---|---|---|
| `aum` | Semi-additive | A month-start balance: sum across clients/advisors for one month, but summing across months double-counts the same money; use the latest or average over time. |
| `return_ytd` | Non-additive | A cumulative year-to-date percentage: never summed across clients or months; use an AUM-weighted average across clients and take the latest month within a year. |
| `benchmark_return_ytd` | Non-additive | Same as `return_ytd`: a YTD percentage that is averaged or read at a point in time, never summed. |
| `active_alpha_ytd` | Non-additive | The difference between two YTD returns; same treatment as `return_ytd`. |
| `cash_pct` | Non-additive | A percentage of the account; average weighted by `aum`, never summed. |

### fact_transactions
| Column | Type | How it may be aggregated |
|---|---|---|
| `amount` | Additive *(within `txn_type`)* | Summable across clients, securities, and dates, but only after filtering or grouping by `txn_type`, because every amount is stored as a positive number (buys and sells, deposits and withdrawals all add rather than net). |
| `shares` | Additive *(within one security and `txn_type`)* | Shares of different securities aren't comparable, so sum only for one security and one transaction type; blank on cash rows. |
| `price` | Non-additive | A per-share price: never summed; use a share-weighted average, SUM(`amount`) ÷ SUM(`shares`). |

### Numeric columns that are NOT measures
- **Keys:** `fee_id`, `snapshot_id`, `txn_id`, `client_id`, `advisor_id`, `benchmark_id`, `security_id`. These are identifiers; summing or averaging them means nothing.
- **Date parts:** `fact_portfolio_snapshot[year]`, `[month]`. These are labels for grouping (and duplicate what `dim_date` provides).
- **Flags:** `fact_portfolio_snapshot[is_return_suspect]`, `fact_transactions[is_post_departure_txn]`. These are 0/1 indicators used to filter or count rows, not to measure an amount.

### Numeric attributes in dimension tables (never summed)
- **dim_client:** `age`, `initial_aum` (a starting balance, not a flow), and `zip_code` (stored as text).
- **dim_advisor:** `years_experience`, `aum_target_mm` (a target per advisor).
- **dim_security:** `expense_ratio_bps` (a rate; blank for individual stocks).
- **dim_date:** `year`, `quarter`, `month`, `week_of_year`, and the flags `is_month_end`, `is_quarter_end`, `is_year_end`, `is_trading_day`.

## Part E — Relationships and Design

### Relationships built in Power BI
All relationships are Many-to-one (*:1), fact on the many side, single cross-filter direction (dimension filters fact).

| From (many side) | To (one side) | Status |
|---|---|---|
| fact_fees[client_id] | dim_client[client_id] | Active |
| fact_fees[advisor_id] | dim_advisor[advisor_id] | Active |
| fact_fees[fee_date] | dim_date[date] | Active |
| fact_portfolio_snapshot[client_id] | dim_client[client_id] | Active |
| fact_portfolio_snapshot[advisor_id] | dim_advisor[advisor_id] | Active |
| fact_portfolio_snapshot[benchmark_id] | dim_benchmark[benchmark_id] | Active |
| fact_portfolio_snapshot[snapshot_date] | dim_date[date] | Active |
| fact_transactions[client_id] | dim_client[client_id] | Active |
| fact_transactions[advisor_id] | dim_advisor[advisor_id] | Active |
| fact_transactions[security_id] | dim_security[security_id] | Active |
| fact_transactions[txn_date] | dim_date[date] | Active |
| dim_client[advisor_id] | dim_advisor[advisor_id] | Not created (second path to dim_advisor) |
| dim_security[benchmark_id] | dim_benchmark[benchmark_id] | Not created (keeps the star; avoids two meanings of "benchmark") |

**Conformed dimensions:** `dim_client`, `dim_advisor`, and `dim_date` connect to all three fact tables, so one slicer on any of them filters fees, snapshots, and transactions consistently. `dim_security` is used only by `fact_transactions`, and `dim_benchmark` only by `fact_portfolio_snapshot`.

### (a) Why do some transactions have no `security_id`? Is it a defect?
101,528 transaction rows have a blank `security_id`, and every one is a Deposit, Withdrawal, or Advisory Fee (verified in `check_keys.py`). These are cash movements in and out of the account: no stock or fund is bought or sold, so there is no security to reference. This is not a defect; it is the correct structure for cash rows. In Power BI these rows appear under a `(Blank)` ticker, which is expected. A `(Blank)` would only signal a problem if it appeared for a trade or dividend, and the script confirms there are zero orphan security keys.

### (b) Which `advisor_id` relationship(s) did you keep active, and why?
I kept the three direct relationships from each fact table's `advisor_id` to `dim_advisor` active, and did not create `dim_client[advisor_id]` → `dim_advisor`. Power BI allows only one active filter path between two tables, and having both would create two routes from `dim_advisor` to each fact (direct, and through `dim_client`). The direct links are better because each fact row records the advisor responsible for that specific fee, snapshot, or transaction, which preserves history if a client is reassigned (the `is_post_departure_txn` flag shows advisor changes matter in this data). It also makes `dim_advisor` a conformed dimension that filters all three facts in one step and keeps the model a true star. In the current data, every fact's `advisor_id` matches the client's `advisor_id` in `dim_client` (0 mismatches), so no information is lost.

### (c) Which date column did you join on, and why?
I joined each fact's date column (`fee_date`, `snapshot_date`, `txn_date`) to `dim_date[date]`, not `dim_date[date_id]`. The facts store calendar dates such as `2020-01-01`, while `date_id` is an integer from 1 to 1,827, so joining on `date_id` would match nothing. `dim_date[date]` is unique (verified in the script), so it can serve as the one side of the relationship, and every fact date has a match (0 orphans). `dim_date` is marked as the date table on the `date` column so time-intelligence functions work in Assignment 6.

### (d) Star or snowflake?
Two columns connect one dimension to another: `dim_client[advisor_id]` → `dim_advisor` and `dim_security[benchmark_id]` → `dim_benchmark`. Keeping them would make the model a snowflake. I did not create either relationship, so the model is a star. The advisor link would duplicate the direct fact-to-advisor path (see b). The benchmark link would let a benchmark slicer filter transactions by each security's benchmark while filtering snapshots by each account's benchmark: two different meanings under one slicer. The columns stay in the tables as attributes, so they can still be shown in visuals.

## Part F — Reflection

### Three business questions (one per fact table)

**1. fact_fees — "What was total fee revenue by advisor, by quarter, in 2024?"**
Answerable in a single visual with no DAX workaround. Fee `amount` is fully additive, so a matrix with `dim_advisor[last_name]` on rows, `dim_date[quarter]` on columns, a `dim_date[year]` = 2024 filter, and Sum of `amount` gives the correct answer, including correct row and column totals.

**2. fact_transactions — "What were net client flows (deposits minus withdrawals) by advisor each month?"**
Not answerable in a single visual without DAX. Every `amount` is stored as a positive number, so Sum of `amount` adds withdrawals to deposits instead of subtracting them. Getting net flows needs a measure such as `CALCULATE(SUM(amount), txn_type = "Deposit") - CALCULATE(SUM(amount), txn_type = "Withdrawal")`.
*Schema fix:* add a signed amount column to `fact_transactions` (positive for money coming in such as deposits, sells, and dividends; negative for money going out such as withdrawals, buys, and fee debits), or a `direction` column (+1 / −1). Net flow would then be a plain Sum.

**3. fact_portfolio_snapshot — "Which advisors' clients beat their benchmarks in 2024, and what AUM do those advisors manage today?"**
Not answerable in a single visual without DAX, for two reasons. First, `aum` is semi-additive: a visual at the year level sums twelve monthly balances and overstates AUM about twelvefold, so "AUM today" needs a last-date measure (e.g., `LASTDATE`). Second, `active_alpha_ytd` is a non-additive percentage: Average treats a $50K client the same as a $5M client, and Sum is meaningless, so an AUM-weighted average and the latest month in the year both require DAX.
*Schema fix:* add an `is_latest_snapshot` (or `is_year_end_snapshot`) flag so a visual can filter to one balance per client without DAX, and add an `alpha_x_aum` column (`active_alpha_ytd` × `aum`) so a weighted alpha is just SUM(`alpha_x_aum`) ÷ SUM(`aum`).

### Overall assessment
The star schema answers "how much" questions on additive flows (fees, individual transaction types) directly and correctly across every dimension. Its limits are balances (AUM), rates and returns, and unsigned cash flows: those need DAX measures or extra columns, which is the work planned for Assignment 6.