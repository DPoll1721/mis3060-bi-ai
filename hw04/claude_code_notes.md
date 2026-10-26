## Part A - 01_profile.py
Claude Code flagged:
I  read the whole file and checked its assumptions against the raw CSVs in hw04/data/raw (read-only, using C:\Users\dpoll\anaconda3\python.exe, since python/py aren't on PATH). I didn't edit anything. Issues are ordered by how likely they are to put a wrong number in the report.

Logic bugs that produce wrong or misleading counts
01_profile.py:380, 392-399: every Dividend gets flagged one way or the other. Dividend is in traded, so a dividend whose amount doesn't equal shares × price raises an ERROR (L394). The dividends that do match raise a WARN (L398), because div & ~amt_bad catches exactly those. All 53,864 Dividend rows end up flagged. Dividends should be left out of the shares × price ERROR rule.
01_profile.py:326 and 488-491: holidays are invisible. The rule only checks "weekday means trading day", and dim_date follows that exactly, so it passes. But dim_date marks 2020-01-01, 2020-12-25 and 2021-07-05 as trading days. As a result, "Buy/Sell on a non-trading day" undercounts: I found 453 Buy/Sell rows on New Year's or Christmas dates alone, and none of them get flagged.
01_profile.py:494-501: Advisory Fee reconciliation.
.dropna() silently drops client-months that appear in only one of the two tables, and those are the most serious mismatches.
ff sums all fee types (Management 71K, Advisory 32K, Custodial, Performance) against only the "Advisory Fee" transactions. That may compare different things.
The denominator is client-months, but the finding is filed under fact_transactions, so pct_affected is mixing units.
01_profile.py:263-268, 355-356, 366, 392: values that don't parse pass silently. num() turns them into NaN, and any comparison with NaN is False, so they never count as violations. For example, the 300 '%' rows in return_ytd skip the [-1, 1] range check entirely.
01_profile.py:348: NaN AUM becomes UHNW. np.select falls through to its default, so an unparseable initial_aum is classed as UHNW and probably flagged as a tier mismatch. A blank client_tier is also counted as a mismatch.
01_profile.py:444-449: the merge can add rows. If the snapshot table ever has a duplicate (client_id, snapshot_date), the left merge grows m, and the counts go above len(f). It's clean today (0 duplicate grains), but nothing protects against it. Also, a blank aum is "" rather than NaN (because of keep_default_na=False), so it counts as a match, and then the aum_basis comparison passes as NaN.
01_profile.py:330: gap check.
It assumes the file is sorted.
.dropna() throws away the diffs around any NaT row, which hides those gaps.
It counts breaks, not missing days, so a 10-day hole counts as 1.
01_profile.py:318: to_datetime has no format=. Non-ISO dates could be parsed silently, possibly with day and month swapped. Any NaT row also fails all 7 derived-column rules, so one bad date is counted 7 times.
01_profile.py:477: the counts don't match their label. The note reports a number of clients, but the "is_active of these" breakdown counts transaction rows.
01_profile.py:454: drop_duplicates("client_id") takes the first row in file order, not the earliest date. It's correct today only because the file is sorted and no client's benchmark changes.
The same rows reported twice
AUM = 1000: the range floor 1000.01 (L213) and the "exactly 1000" check (L373) both flag the same 420 rows.
Negative shares: the range check (0, None) (L223, WARN) and the "negative shares" check (L388, ERROR) flag the same rows.
Exact duplicates are also near-duplicates (L300 and L309). Every duplicated(keep=False) check counts every copy, including the first. "Same person under two IDs" therefore reports 2 rows per person. That's fine if you mean it, but the report should say so.
01_profile.py:410: RI percentages use len(c) as the denominator, which includes the blank FKs. For security_id, the 101,597 legitimately blank values push the percentage down.
Inconsistent normalization (strip, case, .0)
Some checks strip whitespace and some don't:

The allowed-values check strips (L258).
The pattern check (L272), the PK duplicate check (L251) and the RI isin (L409) don't.
Neither do the == "" and == "True" tests at L335, 337, 340, 384, 459 and 483.
The pattern check also counts blanks as failures, unlike the other checks.

Cross-table checks compare raw strings (L433-434, 485, 488). An ID stored as '22.0' (like security_id, where all 197,175 non-blank values look like 45.0) either doesn't map at all (NaN, then skipped silently) or counts as a mismatch.

01_profile.py:414: the "after removing .0" finding is only added in some cases. So the number of checks in dq_summary_raw.csv changes from run to run. The fix also doesn't strip whitespace.

01_profile.py:468, 473: dates are compared as strings. That only works for ISO YYYY-MM-DD; it holds today, but nothing guards it.

Crash risks
set_index(...).map(...) at L430, 439, 466, 477 and 488 raises InvalidIndexError if client_id (or dim_date.date) has any duplicate, which is exactly what the PK check is looking for.
01_profile.py:311: the "generic" near-duplicate check hard-codes first_name, last_name and initial_aum. It throws a KeyError if it's used on any other table.
01_profile.py:102: an empty table divides by zero. L514: any table without a spec throws a KeyError.
01_profile.py:124: FINDINGS is a module-level global. Running main() twice in the same session (for example, in a notebook) produces every finding twice.
Hard-coded values (should be named constants or documented)
Ranges: year (2020, 2024) (L182), plus the age, bps, expense ratio and YTD ±1 limits.
Placeholder AUM: 1000 / 1000.01 (L213, 373, 451).
Tier bands: 500K and 5M (L348).
Fee formula: /12 for every fee type, including Performance and Custodial (L355).
Tolerances: 0.02 (L356, 500), 1e-4 (L366; the '9.28%' values carry only about 5e-5 of precision, so this is close to the edge), and 1% with clip(lower=1) (L393).
Inferred-type threshold: 95% (L54-61).
Lists repeated inside rule bodies: the txn-type lists (L380, 489) and the "True"/"0" string literals.
Null-like literals (L282): the list misses none, n/a, #N/A, <NA> and -. Separately, "None" in dim_advisor.certifications may be a real value ("no certifications").
Gaps
is_quarter_end, is_year_end and week_of_year are never checked against the date (L319-327).
Only return_ytd handles the % format. If % values ever appear in benchmark_return_ytd or active_alpha_ytd, they'd pass silently (none do today).
cash = ~traded (L381) treats unknown or blank txn_type values as cash, and nothing checks the reverse case (a cash row that has a security filled in).
The crosstab note is cut off at 200 characters (L458).
Several of these have no effect on today's data, which has no duplicate grains, no whitespace, no non-ISO dates and no negative amounts. Items 1–3, 4 (the % rows), 11–14 and 16 do change the numbers in the current report.

What I did:
**Fixed**
- Holidays (#2): dim_date marks market holidays as trading days. Added a holiday check -> 14 holiday dates flagged in dim_date, 1,095 Buy/Sell rows on holidays.
- RI denominator (#14): now uses non-blank keys only, so the security_id orphan rate shows 100% (all 197,175 non-blank values are '45.0'-style), not 66%.

**Left as is (by design)**
- Dividends (#1): flagging every Dividend is intended. The WARN says dividend = full position value, which is implausible. 0 dividends fail the shares x price ERROR rule.
- Overlapping checks (AUM = 1000, negative shares): the generic range check and the specific rule both fire on purpose; each issue is counted once in the decision log.
- Near-duplicates: 50 rows = 25 duplicate client pairs (both copies counted on purpose).
- Advisory Fee reconciliation (#3): kept as a WARN showing the two tables don't reconcile; documented as a limitation, not fixed.

**Left as is (no effect on current data)**
- Whitespace, non-ISO dates, NaN handling, duplicate-key crash risks, empty tables, global FINDINGS list: verified the raw data has no whitespace, all dates are ISO, and the PK/grain checks pass, so none of these change a count today.
- Hard-coded thresholds (1000 placeholder, 500K/5M tier bands, tolerances, 95% type threshold) are kept as business rules and will be listed in the README.md.