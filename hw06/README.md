# HW6 — DAX Measure Library: AUM & Performance

MIS3060 Business Intelligence with AI · Drew Pollock

A library of 12 DAX measures (plus 2 base measures) on the Wildcat Capital star model. Each measure uses the pattern that matches its additivity class, and all 89 required Power BI values are reconciled to an independent pandas calculation.

## Folder structure

```
hw06/
├── README.md                         ← this file
├── powerbi/
│   ├── hw06.pbix                     posted model + _Measures table + "Measures" report page
│   └── measures.md                   Part A (DAX, pattern, business meaning) + Part C answers
├── scripts/
│   ├── 01_reconcile_measures.py      Part B: pandas recompute + comparison to Power BI
│   └── 02_part_c_evidence.py         Part C: pandas evidence for questions (a)–(d)
├── reports/
│   ├── powerbi_values.csv            89 Power BI values (measure, slice, value) from DAX query view
│   ├── measure_reconciliation.csv    89 rows: powerbi_value, pandas_value, abs_diff, match
│   └── part_c_evidence.txt           output of 02_part_c_evidence.py
└── claude/
    ├── model_metadata.md             INFO.VIEW.TABLES / COLUMNS / RELATIONSHIPS output
    ├── dax_session.md                Part D prompt + Claude's full response
    ├── verification.md               Part D verification
    └── verification_notes.md         working notes (raw test-query output, review decisions)
```

## How to run

The scripts read the Wildcat Capital Clean CSVs from `hw05/data/`. That folder is git-ignored, so place the eight CSVs there first.

```bash
conda activate MIS3060
python hw06/scripts/01_reconcile_measures.py
python hw06/scripts/02_part_c_evidence.py > hw06/reports/part_c_evidence.txt
```

`01_reconcile_measures.py` prints `Rows compared: 89 | matches: 89 | mismatches: 0` and exits with code 1 if any row fails.

**Getting the Power BI values:** in DAX query view, one `EVALUATE` query loops over every required measure × slice (grand total, 2020–2024, 2024 × client tier, Dec 2024). It converts each value to text so numbers and the `Alpha Signal` text fit in one column. The result was copied with **Copy → Copy table**, tabs were replaced with commas, and the header was renamed to `measure,slice,value`.

## Reconciliation result

**89 / 89 rows match** on the first run:

- every measure at the grand total
- measures 1, 4, 6–10 by year
- measures 1, 3, 4, 7–11 by client tier for 2024
- measure 5 for December 2024
- `AUM (naive SUM)` at the total and by year, which shows that both tools make the same mistake when asked to

The largest difference is about 3e-5 dollars on currency measures and about 4e-14 on ratios. Both are floating-point rounding, far inside the assignment's tolerances (0.01 currency, 0.0001 ratios). The three blank-vs-blank rows (2020 LY, YoY and Organic Growth, where there's no prior year) are counted as matches.

**Mismatches and fixes:** no reconciliation row ever mismatched. Problems I hit along the way:

| Problem | Which side | Fix |
|---|---|---|
| `Ending AUM` failed with "The syntax for 'LastDate' is incorrect" | Power BI (DAX) | `LASTDATE` is a built-in DAX function, so it can't be a variable name. Renamed the variable to `LastSnap` in every measure. |
| Export query failed with "The syntax for 'Rows' is incorrect" | Power BI (DAX query) | `ROWS` is a reserved word. Renamed the variable to `RowList`. |
| `year` kept being summed in the table visual ("Sum of year") | Power BI (model) | Set `dim_date[year]` → Column tools → Summarization → **Don't summarize** |
| Card visuals rendered blank in Apporto's Power BI build | Power BI (environment) | Built the cards in Power BI Desktop on my own laptop. The measures are unchanged. |
| Assumed snapshots were month-end | Assumption | DAX test query and pandas both show snapshots are dated the **1st of each month** (last = 2024-12-01). `LASTNONBLANK` doesn't depend on the day, so no measure changed. |

## Claude Code review of `01_reconcile_measures.py`

Claude Code read the script, compared it to the DAX in `claude/`, and profiled the CSVs. It found **no bugs that change any of the 89 results**. What it flagged and what I did:

| # | Severity | Finding | What I did |
|---|---|---|---|
| 1 | High | DAX for 12 of 14 measures wasn't in the repo, so the "mirror" couldn't be checked | **Addressed:** all DAX is now in `powerbi/measures.md` |
| 2 | High | Tolerance (0.0001) is much looser than the actual differences (~1e-14) | **Kept** the assignment's tolerances. I documented the actual max differences above, so the evidence is visible. |
| 3 | High | Clean data never runs the blank-handling paths (0 null `aum`/alpha, 0 duplicate client-dates) | **Noted.** Only the three 2020 blank rows test that path. The 89/89 proves the main path. |
| 4 | Medium | Both sides share the same business definitions | **Noted.** The reconciliation tests implementation, not definitions. Definitions are justified in `measures.md` and Part C. |
| 5 | Medium | `shift()` with `DateOffset` isn't exactly DATEADD at month-ends | **No change.** Snapshots fall on the 1st, so the edge case can't occur in this data. |
| 6 | Medium | `dim_client` merge has no duplicate check | **Fixed:** added `validate="many_to_one"` to all three merges |
| 7 | Medium | Hard-coded `"Deposit"`/`"Withdrawal"` strings and suspect flag | **No change.** Verified the values in the data. They match the DAX exactly. |
| 8 | Low | Years, tiers and slice labels are hard-coded | **No change.** The outer merge flags any slice present on only one side. |
| 9 | Low | `pd.to_datetime` guesses the date format | **Fixed:** added `format="%Y-%m-%d"` |
| 10 | Low | Label notes (`2024-12`, `Ending Clients` in the currency set) | **Noted** |
| CQ | Low | Script always exits 0 | **Fixed:** `sys.exit(1)` when any row mismatches |

After the fixes, the script was re-run: still 89/89.

## Power BI file

`powerbi/hw06.pbix` is about 21 MB, under GitHub's 100 MB limit. It's saved with the **Measures** page open, which contains:

- **Cards:** Ending AUM, Ending Clients, Avg AUM per Client, Top 10 Client Share
- **Table by year:** Ending AUM, AUM YoY %, Avg Monthly AUM, Fee Yield (bps), Organic Growth Rate, AUM-Weighted Alpha, Alpha Signal
- **Table by client tier**, with a visual-level filter `year = 2024`: Ending AUM, Avg AUM per Client, AUM YoY %, Fee Yield (bps), Organic Growth Rate, AUM-Weighted Alpha, Alpha Signal, Top 10 Client Share

## Process

| Step | Tool |
|---|---|
| Draft the measures and scripts | Claude Desktop |
| Run the scripts | VS Code (conda env `MIS3060`) |
| Review the script before commit | Claude Code (findings above) |
| Build the model and report | Power BI Desktop (Apporto + laptop) |
| Part D measure | Claude, using exported INFO.VIEW metadata (see `claude/`) |