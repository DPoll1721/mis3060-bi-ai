"""HW5 Part A: prove primary-key uniqueness and foreign-key integrity."""
from pathlib import Path
import pandas as pd

DATA = Path(__file__).parent / "data"

# 1. Load all eight tables
names = ["dim_advisor", "dim_benchmark", "dim_client", "dim_date", "dim_security",
         "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]
t = {n: pd.read_csv(DATA / f"{n}.csv") for n in names}

print("=== Row counts ===")
for n, df in t.items():
    print(f"{n:<26}{len(df):>9,}")

# 2. Primary keys: unique and never blank
pks = {"dim_advisor": "advisor_id", "dim_benchmark": "benchmark_id",
       "dim_client": "client_id", "dim_date": "date_id",
       "dim_security": "security_id", "fact_fees": "fee_id",
       "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

print("\n=== Primary keys ===")
for n, col in pks.items():
    s = t[n][col]
    ok = s.is_unique and s.notna().all()
    print(f"{'PASS' if ok else 'FAIL'}  {n}[{col}]  duplicates={s.duplicated().sum()}  blanks={s.isna().sum()}")

# dim_date[date] is the join column for the facts, so it must be unique too
print(f"{'PASS' if t['dim_date']['date'].is_unique else 'FAIL'}  dim_date[date] unique (join column)")

# 3. Foreign keys: every non-blank value must exist in the parent table
fks = [  # (child table, child column, parent table, parent column)
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]

print("\n=== Foreign keys ===")
for child, ccol, parent, pcol in fks:
    vals = t[child][ccol]
    blanks = vals.isna().sum()
    orphans = (~vals.dropna().isin(t[parent][pcol])).sum()
    print(f"{'PASS' if orphans == 0 else 'FAIL'}  {child}[{ccol}] -> {parent}[{pcol}]  orphans={orphans}  blanks={blanks}")

# 4. Blank security_id: confirm it only happens on cash rows
txn = t["fact_transactions"]
print("\n=== Blank security_id by txn_type ===")
print(txn.loc[txn["security_id"].isna(), "txn_type"].value_counts().to_string())

# 5. Why dates join on dim_date[date], not date_id
print("\n=== Date join check ===")
print("Sample fee_date values:      ", t["fact_fees"]["fee_date"].head(3).tolist())
print("Sample dim_date[date] values:", t["dim_date"]["date"].head(3).tolist())
print("Sample dim_date[date_id]:    ", t["dim_date"]["date_id"].head(3).tolist())

# 6. Part B: grain checks (is each candidate grain actually unique?)
print("\n=== Grain checks (Part B) ===")
grains = [
    ("fact_fees", ["client_id", "fee_date"]),
    ("fact_portfolio_snapshot", ["client_id", "snapshot_date"]),
    ("fact_transactions", ["client_id", "txn_date", "txn_type", "security_id"]),
]
for n, cols in grains:
    dups = t[n].duplicated(subset=cols).sum()
    print(f"{'UNIQUE' if dups == 0 else 'NOT UNIQUE'}  {n} by {cols}  duplicate rows={dups}")

# Fees and snapshots are monthly: every date should be the 1st of the month
for n, col in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date")]:
    days = pd.to_datetime(t[n][col]).dt.day.unique()
    print(f"{n}[{col}] day-of-month values: {sorted(days)}")