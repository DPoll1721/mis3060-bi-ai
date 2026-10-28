# HW5: Wildcat Capital Star Schema and Power BI

MIS3060 Business Intelligence with AI | Villanova University | Drew Pollock

## Structure

```
hw05/
├── README.md            this file
├── star_design.md       Parts A (keys), B (grain), C (measures), E (relationships), F (reflection)
├── check_keys.py        proves PK uniqueness, FK integrity, and fact-table grain
├── data/                the 8 Wildcat Capital Clean CSVs (not committed; see .gitignore)
└── powerbi/
    ├── hw05.pbix        Power BI model: 8 tables, 11 relationships, dim_date marked as date table
    └── model_view.png   Model view screenshot
```

## How to run

1. Put the eight `Wildcat Capital Clean` CSVs in `hw05/data/`.
2. From the repo root:
   ```
   conda activate MIS3060
   cd hw05
   python check_keys.py
   ```
3. Expected output: every line says PASS (row counts, primary keys, foreign keys, the cash-row `security_id` check, advisor consistency, and grain), and the last line reads `All checks passed.` The script exits with code 1 if any check fails.

## Power BI model

- 8 tables loaded with types checked in Power Query (`zip_code` set to Text; dates set to Date)
- 11 active many-to-one relationships, single direction, from each fact to its dimensions; fact dates join to `dim_date[date]`
- `dim_client[advisor_id]` → `dim_advisor` and `dim_security[benchmark_id]` → `dim_benchmark` intentionally not created (see Part E)
- `dim_date` marked as the date table on `date`
- Row counts in Power BI match the handout for all 8 tables

## Claude Code findings

Before committing, Claude Code reviewed `check_keys.py` and `star_design.md` against the CSVs (no files edited by the review). It confirmed every key, foreign key, grain, and the `bps_charged` formula, and found these issues:

**Fixed**
- `check_keys.py` always exited with code 0, so a FAIL could scroll past unnoticed. It now collects failures and exits with code 1 if any check fails.
- The foreign-key check counted only orphans, so a blank `client_id`, `advisor_id`, or date would still pass. Blanks now fail everywhere except `fact_transactions[security_id]`.
- The "blank `security_id` = cash rows" claim was only printed, not tested. It is now a PASS/FAIL check (blank on every Deposit, Withdrawal, and Advisory Fee row and on no trade or dividend).
- Part E(b)'s "0 mismatches" between fact `advisor_id` and `dim_client[advisor_id]` was not tested. Added a check for all three facts.
- Added checks that `dim_date[date]` is non-blank with no missing days (needed for Mark as date table), and turned the 1st-of-month printout into PASS/FAIL.
- Part B overstated that "no combination of descriptive columns is unique"; only client + date + type + security was tested. Reworded.
- Part F Q1 grouped by `dim_advisor[last_name]`, but two advisors are named Johnson. Changed to `advisor_id`.
- Part E(b) cited `is_post_departure_txn` as evidence of client reassignment, but the data shows none (0 mismatches). Reframed as a design reason.
- Part C now says returns should exclude `is_return_suspect` = 1 rows (3,875 rows with returns up to 9,467%), the `price` average applies within one security and type, and "twelvefold" is now "up to twelvefold."

**Not changed**
- Setting key columns to "Don't summarize" in Power BI: noted for Assignment 6, when measures are added.
- The review flagged that the fact date columns show a different icon from `dim_date[date]` in Model view. All columns were set to Date in Power Query and Power BI only creates relationships between matching types, so no change was needed.