# Claude Code review of `hw06/scripts/01_reconcile_measures.py`

Raw output from Claude Code, before fixes. What I did about each finding is in `hw06/README.md`.

---

I found no bugs that change any of the current 89 results. Python isn't installed in this environment, so I didn't re-run the script. I checked its logic against the DAX in `hw06/claude/`, profiled the CSVs with awk, and read the existing `measure_reconciliation.csv`. The real problems are what the 89/89 doesn't prove, plus a few spots where the pandas logic differs from DAX on data you don't have yet. I didn't edit anything.

## High

**1. The DAX for 12 of the 14 measures isn't in the repo, so the "mirror" can't be checked.**
The repo only has the DAX for `Ending AUM` and `Top 10 Client Share` (in `dax_session.md`). Each of these pandas choices is a guess that happens to match Power BI on this data:

* `growth()` (line 121): a blank current value is treated as 0, so a period with no current data shows −100%. That only matches if the DAX is `DIVIDE([Ending AUM] - [LY], [LY])` with no blank guard.
* `avg_monthly_aum` (line 135): divides by the number of distinct snapshot dates. An `AVERAGEX` over months would skip blank months.
* `fee_yield_bps` (line 146): uses fees × 12 × 10000 ÷ total AUM across all snapshots in the period.
* `organic_growth` (line 159): the denominator is last year's ending AUM, not beginning-of-period AUM.
* `weighted_alpha` (line 167): the denominator is the AUM of filtered rows only, not `[Ending AUM]`.

Fix: export the measure DAX into `hw06/claude/` and put a one-line comment above each pandas function naming the DAX it mirrors.

**2. The tolerance is far looser than the actual differences.**
The largest ratio difference in the current output is about 4e-14, but `RATIO_TOL = 0.0001`. For `AUM-Weighted Alpha` 2021 (−0.00157), 0.0001 is about 6% of the value. A wrong suspect filter or the wrong denominator could still pass. Use a relative tolerance (e.g. `math.isclose(rel_tol=1e-9, abs_tol=1e-9)`) or about 1e-9 absolute.

**3. The clean data never runs the blank-handling code.**
I checked the CSVs: 0 null `aum`, 0 null `active_alpha_ytd`, 0 duplicate client/date rows, `is_return_suspect` is always 0 or 1, and every snapshot is on the 1st of the month. So these paths have never been tested:

* the `notna()` filter at line 92
* the "blank current → 0" branch in `growth()`
* how `ne(1)` treats a missing suspect flag
* `DIVIDE` with a zero denominator

The only blank case exercised is the three 2020 rows, which match because both sides are blank (line 243). The 89/89 shows the main path is right, not that the blank handling copies DAX. A few unit tests on small hand-made DataFrames would cover it.

## Medium

**4. How independent the check is from Power BI.**

* Nothing is read from Power BI before the comparison. That part is fine.
* The pandas logic was written from the DAX design, so both sides share the same business definitions (LY means the last snapshot in the shifted window, tie-break on `client_id` ASC, ±0.02 alpha thresholds, the organic growth denominator). That checks the implementation, not the definitions. Say this in your write-up.
* Both sides read the same `hw05/data` CSVs, so a Power Query step in the .pbix (type change, filter, removed rows) wouldn't show up here. Confirm Power BI loads those files unchanged.
* The pandas Total slice filters facts to the `dim_date` range (line 214). In Power BI, the grand total for naive SUM, fees and flows has no date filter, so it includes rows whose date isn't in `dim_date`. All dates are in range today, so this doesn't matter yet.

**5. `shift()` isn't exactly `DATEADD` or `SAMEPERIODLASTYEAR` (lines 63–66).**
`DateOffset` moves the end date by calendar position. DAX moves whole months:

* Apr 1–30 shifted back one month gives Mar 1–30, which misses Mar 31. DAX returns Mar 1–31.
* Feb 2025 shifted back a year gives Feb 1–28, 2024, which misses Feb 29.

With snapshots on the 1st this has no effect now, but it would break with month-end snapshots or a shifted transaction measure. Fix: snap the shifted end to the end of the month (`+ pd.offsets.MonthEnd(0)`) when the original window ends on a month end.

**6. The `dim_client` merge has no check (lines 50–52).**
A duplicate `client_id` (HW4 had 25) would copy fact rows and inflate every sum without any error. Add `validate="many_to_one"`, plus a check that no fact row is left without a tier.

**7. Matching on fixed strings and flag values.**

* Lines 151–152 match `"Deposit"` and `"Withdrawal"` exactly, so `"deposit "` or a different case would be dropped silently. The sign is also assumed: Withdrawals are positive today, which I checked, but nothing in the script asserts it.
* Line 164: if `is_return_suspect` ever loads as `"True"`/`"False"` strings, `ne(1)` is always true and no rows are excluded.

## Low

**8. Hard-coded values that won't follow the data.**

* Years `range(2020, 2025)` (line 215)
* The tier list (line 217)
* `"2024"` and `"2024-12"` (lines 218–219)

The outer merge would catch drift, but taking these from `dim_date` and `dim_client` is cleaner. The paths are fine because they're relative to the script.

**9. Date parsing.** `pd.to_datetime` has no `format=`, so it guesses the format. Use `format="%Y-%m-%d"`. Also, `between(start, end)` with `end` at midnight would drop any timestamp later on the last day; there are none today.

**10. Two possible label mix-ups.** These are notes for your write-up, not code bugs.

* `"2024-12"` Ending AUM is the 12/1/2024 snapshot, which is really the end-of-November balance.
* `Ending Clients` is in `CURRENCY_MEASURES`, so it gets the 0.01 tolerance (correct for a count, but the set name is misleading).

## Code quality

* Everything runs at import time with no `main()`, so the measure functions can't be imported into tests.
* The script always exits 0, even with mismatches. Add `sys.exit(1)` when `ok < n` so it can gate a commit.
* The measure names are repeated across `MEASURES`, `CURRENCY_MEASURES`, `YEAR_M`, `TIER_M` and `MONTH_M`. Any new measure gets the ratio tolerance by default without warning. One table of measure name, function, kind and slices would remove that.
* `pandas_value` holds both floats and strings, so the CSV output is inconsistent. Consider a separate text column.
* Blank-vs-blank rows count as matches with `abs_diff = 0`. Label them `"both blank"` so the 3 rows that weren't really compared are visible.
* `ending_aum` is computed again inside several measures. That's harmless at this data size.

The most useful fixes before you commit are #2 (tighter tolerance) and getting the DAX source into the repo (#1). Those two decide whether 89/89 is real evidence.