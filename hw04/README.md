# HW4 — Cleaning the Wildcat Capital Data

## Structure
```
hw04/
├── decision_log.md              Part B: one entry per issue (written before cleaning code)
├── claude_code_notes.md         Full Claude Code review of each script + what I did
├── scripts/
│   ├── 01_profile.py            Part A: generic profiler + 4 check groups
│   ├── 02_clean.py              Part C: cleaning program (asserts after every step)
│   └── 03_validate.py           Part D: RI function, rules, reconciliations, IQR, scorecard
├── data/
│   ├── raw/                     8 source CSVs (not committed; never modified)
│   ├── clean/                   8 clean CSVs + README_clean.md
│   └── audit/                   cleaning_log.csv, value_changes.csv, quarantine_*.csv
└── reports/
    ├── profile_raw.csv, dq_summary_raw.csv          (Part A)
    ├── data_quality_scorecard.csv                   (Part D)
    ├── ri_results.csv, rule_checks.csv, reconciliations.csv, iqr_outliers.csv
    └── cleaning_report.md                           (Part E)
```

## How to run
1. Put the 8 Wildcat Capital CSVs in `hw04/data/raw/`.
2. From the repo root, with the `MIS3060` conda env active:
```
python hw04/scripts/01_profile.py
python hw04/scripts/02_clean.py
python hw04/scripts/03_validate.py
```
Run them in order: `03_validate.py` compares `data/raw` with the `data/clean` output of `02_clean.py`. Each script stops with an AssertionError if a check fails.

## Claude Code review findings
Every script was reviewed by Claude Code before its commit. The full findings are in `claude_code_notes.md`; summary:

| Script | Flagged | Key fixes | Left as is (with reason) |
|---|---:|---|---|
| 01_profile.py | 22 | Added market-holiday check (found 14 holiday dates marked as trading days, 1,095 trades on holidays); RI % now excludes blank FKs | Robustness items with no effect on current data (verified: no whitespace, all ISO dates, no duplicate keys) |
| 02_clean.py | 13 | Asserts that could never fail now check exact flag counts; D1 verifies all 7 attributes and IDs 2501–2525; F3 reconciles to $0.01 and checks only the sign changed | Hard-coded expected counts kept on purpose (they make asserts stronger) |
| 03_validate.py | 14 | Rule pass rates use applicable rows only; removed a triple-counted security_id penalty; added the D4 check, cross-table advisor/account rules and R6; clean data must pass everything except the documented R5 limitation | Flag counts already asserted in 02_clean.py |

## Notes
- Hard-coded business thresholds: AUM placeholder $1,000.00; tier bands <$500K Retail / <$5M HNW / $5M+ UHNW; fee = AUM × bps ÷ 10,000 ÷ 12; tolerances $0.01–$0.02 for amounts and 0.0001 for returns.
- `check_referential_integrity()` in `03_validate.py` is kept for Assignment 5.