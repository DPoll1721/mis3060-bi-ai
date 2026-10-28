"""HW5 Parts A and B: prove key uniqueness, referential integrity, and fact-table grain.

Exits with code 1 if any check fails, so a failure can't scroll past unnoticed.
"""
import sys
from pathlib import Path
import pandas as pd

DATA = Path(__file__).parent / "data"
failures = []


def check(ok, label):
    """Print PASS/FAIL and remember any failure."""
    print(f"{'PASS' if ok else 'FAIL'}  {label}")
    if not ok:
        failures.append(label)


# 1. Load all eight tables
names = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
         "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]
t = {n: pd.read_csv(DATA / f"{n}.csv") for n in names}

expected_rows = {"dim_advisor": 25, "dim_benchmark": 8, "dim_client": 2500,
                 "dim_date": 1827, "dim_security": 500, "fact_fees": 122197,
                 "fact_portfolio_snapshot": 129547, "fact_transactions": 298572}

print("=== Row counts (vs. handout) ===")
for n, df in t.items():
    check(len(df) == expected_rows[n], f"{n:<26}{len(df):>9,} rows (expected {expected_rows[n]:,})")

# 2. Primary keys: unique and never blank
pks = {"dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id",
       "dim_client": "client_id", "dim_date": "date_id",
       "dim_security": "security_id", "fact_fees": "fee_id",
       "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

print("\n=== Primary keys ===")
for n, col in pks.items():
    s = t[n][col]
    check(s.is_unique and s.notna().all(),
          f"{n}[{col}]  duplicates={s.duplicated().sum()}  blanks={s.isna().sum()}")

# dim_date[date] is the join column for the facts, so it must be unique, non-blank,
# and (for "Mark as date table") a complete run of days with no gaps
d = t["dim_date"]["date"]
check(d.is_unique and d.notna().all(), f"dim_date[date] unique and non-blank (join column)")
dates = pd.to_datetime(d)
full_range = pd.date_range(dates.min(), dates.max(), freq="D")
check(len(full_range) == len(dates),
      f"dim_date has no missing days ({dates.min().date()} to {dates.max().date()}, {len(dates):,} days)")

# 3. Foreign keys: no orphans, and no blanks unless the key is allowed to be blank
fks = [  # (child table, child column, parent table, parent column, blanks allowed?)
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id", False),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id", False),
    ("fact_fees", "client_id", "dim_client", "client_id", False),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_fees", "fee_date", "dim_date", "date", False),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id", False),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id", False),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date", False),
    ("fact_transactions", "client_id", "dim_client", "client_id", False),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id", False),
    ("fact_transactions", "security_id", "dim_security", "security_id", True),
    ("fact_transactions", "txn_date", "dim_date", "date", False),
]

print("\n=== Foreign keys ===")
for child, ccol, parent, pcol, blanks_ok in fks:
    vals = t[child][ccol]
    blanks = vals.isna().sum()
    orphans = (~vals.dropna().isin(t[parent][pcol])).sum()
    ok = orphans == 0 and (blanks_ok or blanks == 0)
    check(ok, f"{child}[{ccol}] -> {parent}[{pcol}]  orphans={orphans}  blanks={blanks}"
              f"{' (blanks allowed)' if blanks_ok else ''}")

# 4. Blank security_id must be exactly the cash rows
txn = t["fact_transactions"]
cash_types = {"Deposit", "Withdrawal", "Advisory Fee"}
is_cash = txn["txn_type"].isin(cash_types)
is_blank = txn["security_id"].isna()

print("\n=== Blank security_id vs. txn_type ===")
check((is_blank == is_cash).all(),
      f"security_id is blank on every cash row and on no trade/dividend row "
      f"(blank={is_blank.sum():,}, cash rows={is_cash.sum():,})")
print(txn.loc[is_blank, "txn_type"].value_counts().to_string())

# 5. Fact advisor_id agrees with the client's advisor in dim_client (supports Part E(b))
print("\n=== Fact advisor_id vs. dim_client[advisor_id] ===")
client_adv = t["dim_client"].set_index("client_id")["advisor_id"]
for n in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
    mismatches = (t[n]["advisor_id"] != t[n]["client_id"].map(client_adv)).sum()
    check(mismatches == 0, f"{n}: advisor_id matches the client's advisor  mismatches={mismatches}")

# 6. Why dates join on dim_date[date], not date_id
print("\n=== Date join check ===")
print("Sample fee_date values:      ", t["fact_fees"]["fee_date"].head(3).tolist())
print("Sample dim_date[date] values:", t["dim_date"]["date"].head(3).tolist())
print("Sample dim_date[date_id]:    ", t["dim_date"]["date_id"].head(3).tolist())

# 7. Part B: grain checks
print("\n=== Grain checks (Part B) ===")
check(not t["fact_fees"].duplicated(subset=["client_id", "fee_date"]).any(),
      "fact_fees: one row per client_id + fee_date")
check(not t["fact_portfolio_snapshot"].duplicated(subset=["client_id", "snapshot_date"]).any(),
      "fact_portfolio_snapshot: one row per client_id + snapshot_date")

# Transactions: client + date + type + security is NOT unique, so txn_id is the row identifier
txn_dups = txn.duplicated(subset=["client_id", "txn_date", "txn_type", "security_id"]).sum()
print(f"INFO  fact_transactions: client_id + txn_date + txn_type + security_id has "
      f"{txn_dups} duplicate rows, so txn_id is the row identifier")

# Fees and snapshots are monthly: every date must be the 1st of the month
for n, col in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date")]:
    days = pd.to_datetime(t[n][col]).dt.day
    check((days == 1).all(), f"{n}[{col}] is always the 1st of the month")

# Summary
print("\n=== Summary ===")
if failures:
    print(f"{len(failures)} check(s) FAILED:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("All checks passed.")