"""
HW6 Part B - Reconcile Power BI measures to an independent pandas calculation.

1. Recomputes every measure in pandas from the Wildcat Capital Clean CSVs (hw05/data).
   Nothing is read from Power BI for this step.
2. Reads the Power BI numbers from hw06/reports/powerbi_values.csv (measure, slice, value).
3. Writes hw06/reports/measure_reconciliation.csv with
   measure, slice, powerbi_value, pandas_value, abs_diff, match.

Tolerance: 0.01 for currency/count measures, 0.0001 for ratios and bps.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[2]          # repo root (mis3060-bi-ai)
DATA = ROOT / "hw05" / "data"
REPORTS = ROOT / "hw06" / "reports"
PBI_FILE = REPORTS / "powerbi_values.csv"
OUT_FILE = REPORTS / "measure_reconciliation.csv"

CURRENCY_TOL = 0.01
RATIO_TOL = 0.0001
CURRENCY_MEASURES = {
    "AUM (naive SUM)", "Ending AUM", "Ending Clients", "Avg AUM per Client",
    "Ending AUM LY", "Ending AUM PM", "Avg Monthly AUM",
}
TEXT_MEASURES = {"Alpha Signal"}


# ---------------------------------------------------------------- load data
def load(name, date_cols=()):
    df = pd.read_csv(DATA / f"{name}.csv")
    df.columns = df.columns.str.strip().str.lower()
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], format="%Y-%m-%d")
    return df


dim_date = load("dim_date", ["date"])
dim_client = load("dim_client")
snap = load("fact_portfolio_snapshot", ["snapshot_date"])
fees = load("fact_fees", ["fee_date"])
txns = load("fact_transactions", ["txn_date"])

# attach client_tier (mirrors dim_client -> fact relationships)
tier_map = dim_client[["client_id", "client_tier"]]
snap = snap.merge(tier_map, on="client_id", how="left", validate="many_to_one")
fees = fees.merge(tier_map, on="client_id", how="left", validate="many_to_one")
txns = txns.merge(tier_map, on="client_id", how="left", validate="many_to_one")

DATE_MIN, DATE_MAX = dim_date["date"].min(), dim_date["date"].max()


# ---------------------------------------------------------------- filter helpers
def window(start, end, tier=None):
    """A slice = a date range on dim_date plus an optional client_tier filter."""
    return {"start": pd.Timestamp(start), "end": pd.Timestamp(end), "tier": tier}


def shift(w, **offset):
    """Shift a window back in time (SAMEPERIODLASTYEAR / DATEADD equivalent)."""
    off = pd.DateOffset(**offset)
    return {**w, "start": w["start"] - off, "end": w["end"] - off}


def filt(df, date_col, w):
    mask = df[date_col].between(w["start"], w["end"])
    if w["tier"] is not None:
        mask &= df["client_tier"].eq(w["tier"])
    return df[mask]


def div(num, den):
    """DAX DIVIDE: blank if numerator blank or denominator blank/zero."""
    if pd.isna(num) or pd.isna(den) or den == 0:
        return np.nan
    return num / den


# ---------------------------------------------------------------- measures
def naive_sum(w):
    s = filt(snap, "snapshot_date", w)
    return s["aum"].sum() if not s.empty else np.nan


def last_snapshot(w):
    """Rows on the last snapshot_date in the slice that has AUM (LASTNONBLANK)."""
    s = filt(snap, "snapshot_date", w)
    s = s[s["aum"].notna()]
    if s.empty:
        return s
    return s[s["snapshot_date"] == s["snapshot_date"].max()]


def ending_aum(w):
    s = last_snapshot(w)
    return s["aum"].sum() if not s.empty else np.nan


def ending_clients(w):
    s = last_snapshot(w)
    return s["client_id"].nunique() if not s.empty else np.nan


def avg_aum_per_client(w):
    return div(ending_aum(w), ending_clients(w))


def ending_aum_ly(w):
    return ending_aum(shift(w, years=1))


def ending_aum_pm(w):
    return ending_aum(shift(w, months=1))


def growth(cur, prior):
    cur = 0 if pd.isna(cur) else cur
    return div(cur - prior, prior)


def aum_yoy(w):
    return growth(ending_aum(w), ending_aum_ly(w))


def aum_mom(w):
    return growth(ending_aum(w), ending_aum_pm(w))


def avg_monthly_aum(w):
    s = filt(snap, "snapshot_date", w)
    return div(s["aum"].sum(), s["snapshot_date"].nunique()) if not s.empty else np.nan


def total_fees(w):
    f = filt(fees, "fee_date", w)
    return f["amount"].sum() if not f.empty else np.nan


def fee_yield_bps(w):
    s = filt(snap, "snapshot_date", w)
    tf = total_fees(w)
    return div(tf * 12 * 10000, s["aum"].sum()) if not s.empty else np.nan


def net_flows(w):
    t = filt(txns, "txn_date", w)
    dep = t.loc[t["txn_type"] == "Deposit", "amount"]
    wd = t.loc[t["txn_type"] == "Withdrawal", "amount"]
    if dep.empty and wd.empty:
        return np.nan
    return dep.sum() - wd.sum()


def organic_growth(w):
    return div(net_flows(w), ending_aum_ly(w))


def weighted_alpha(w):
    s = last_snapshot(w)
    s = s[s["is_return_suspect"].ne(1) & s["active_alpha_ytd"].notna()]
    if s.empty:
        return np.nan
    return div((s["active_alpha_ytd"] * s["aum"]).sum(), s["aum"].sum())


def alpha_signal(w):
    a = weighted_alpha(w)
    if pd.isna(a):
        return np.nan
    if a >= 0.02:
        return "Outperforming"
    if a <= -0.02:
        return "Lagging"
    return "In line"


def top10_share(w):
    s = last_snapshot(w)
    if s.empty:
        return np.nan
    by_client = s.groupby("client_id", as_index=False)["aum"].sum()
    top = by_client.sort_values(["aum", "client_id"], ascending=[False, True]).head(10)
    return div(top["aum"].sum(), s["aum"].sum())


MEASURES = {
    "AUM (naive SUM)": naive_sum,
    "Ending AUM": ending_aum,
    "Ending Clients": ending_clients,
    "Avg AUM per Client": avg_aum_per_client,
    "Ending AUM LY": ending_aum_ly,
    "AUM YoY %": aum_yoy,
    "Ending AUM PM": ending_aum_pm,
    "AUM MoM %": aum_mom,
    "Avg Monthly AUM": avg_monthly_aum,
    "Fee Yield (bps)": fee_yield_bps,
    "Organic Growth Rate": organic_growth,
    "AUM-Weighted Alpha": weighted_alpha,
    "Alpha Signal": alpha_signal,
    "Top 10 Client Share": top10_share,
}

# ---------------------------------------------------------------- required slices
YEAR_M = ["AUM (naive SUM)", "Ending AUM", "Ending AUM LY", "AUM YoY %", "Avg Monthly AUM",
          "Fee Yield (bps)", "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal"]
TIER_M = ["Ending AUM", "Avg AUM per Client", "Ending AUM LY", "AUM YoY %", "Fee Yield (bps)",
          "Organic Growth Rate", "AUM-Weighted Alpha", "Alpha Signal", "Top 10 Client Share"]
MONTH_M = ["Ending AUM", "Ending AUM PM", "AUM MoM %"]

jobs = [(m, "Total", window(DATE_MIN, DATE_MAX)) for m in MEASURES]
for y in range(2020, 2025):
    jobs += [(m, str(y), window(f"{y}-01-01", f"{y}-12-31")) for m in YEAR_M]
for t in ["HNW", "Retail", "UHNW"]:
    jobs += [(m, f"2024|{t}", window("2024-01-01", "2024-12-31", t)) for m in TIER_M]
jobs += [(m, "2024-12", window("2024-12-01", "2024-12-31")) for m in MONTH_M]

pandas_df = pd.DataFrame(
    [{"measure": m, "slice": s, "pandas_value": MEASURES[m](w)} for m, s, w in jobs]
)

# ---------------------------------------------------------------- compare to Power BI
pbi = pd.read_csv(PBI_FILE, dtype=str, keep_default_na=False)
pbi.columns = pbi.columns.str.strip().str.lower()
pbi = pbi.rename(columns={"value": "powerbi_value"})

recon = pbi.merge(pandas_df, on=["measure", "slice"], how="outer", indicator=True)


def compare(row):
    if row["_merge"] != "both":
        return pd.Series({"abs_diff": np.nan, "match": False})
    pb, pv = row["powerbi_value"], row["pandas_value"]
    if row["measure"] in TEXT_MEASURES:
        pb = "" if pd.isna(pb) else str(pb).strip()
        pv = "" if pd.isna(pv) else str(pv)
        return pd.Series({"abs_diff": np.nan, "match": pb == pv})
    pbn = pd.to_numeric(pb, errors="coerce")
    pvn = pd.to_numeric(pv, errors="coerce")
    if pd.isna(pbn) and pd.isna(pvn):          # both blank (e.g. 2020 YoY)
        return pd.Series({"abs_diff": 0.0, "match": True})
    if pd.isna(pbn) or pd.isna(pvn):
        return pd.Series({"abs_diff": np.nan, "match": False})
    diff = abs(pbn - pvn)
    tol = CURRENCY_TOL if row["measure"] in CURRENCY_MEASURES else RATIO_TOL
    return pd.Series({"abs_diff": diff, "match": diff <= tol})


recon[["abs_diff", "match"]] = recon.apply(compare, axis=1)
recon = recon[["measure", "slice", "powerbi_value", "pandas_value", "abs_diff", "match"]]
recon.to_csv(OUT_FILE, index=False)

# ---------------------------------------------------------------- summary
n, ok = len(recon), int(recon["match"].sum())
print(f"Rows compared: {n} | matches: {ok} | mismatches: {n - ok}")
print(f"Written to: {OUT_FILE}")
if ok < n:
    print("\nMismatches:")
    print(recon.loc[~recon["match"]].to_string(index=False))
if ok < n:
    sys.exit(1)