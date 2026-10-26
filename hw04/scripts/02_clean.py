"""
HW4 Part C - Clean the Wildcat Capital tables, following decision_log.md.
Run from the repo root:  python hw04/scripts/02_clean.py

Reads  hw04/data/raw/*.csv   (never modified)
Writes hw04/data/clean/*.csv (same file names, same columns + 0/1 flag columns)
       hw04/data/audit/cleaning_log.csv, value_changes.csv, quarantine_*.csv

Every step: prints rows affected + a before/after check, then ASSERTS the
after-state. If a fix did not do what we claimed, the script stops.
"""
from pathlib import Path
import pandas as pd

HW_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = HW_DIR / "data" / "raw"
CLEAN_DIR = HW_DIR / "data" / "clean"
AUDIT_DIR = HW_DIR / "data" / "audit"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

TABLES = [
    "dim_advisor", "dim_client", "dim_date", "dim_security", "dim_benchmark",
    "fact_fees", "fact_portfolio_snapshot", "fact_transactions",
]
PK = {"dim_advisor": "advisor_id", "dim_client": "client_id", "dim_date": "date_id",
      "dim_security": "security_id", "dim_benchmark": "benchmark_id", "fact_fees": "fee_id",
      "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}

STATE_CODES = {"Pennsylvania": "PA", "Florida": "FL", "New York": "NY", "New Jersey": "NJ",
               "California": "CA", "Illinois": "IL", "Texas": "TX"}
US_STATES = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY",
             "LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND",
             "OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"}
AUM_PLACEHOLDER = 1000.0

# ---------------------------------------------------------------------------
# Audit-trail helpers
# ---------------------------------------------------------------------------
CLEANING_LOG = []      # table, issue, action, rows_affected, note
VALUE_CHANGES = []     # small DataFrames, concatenated at the end
QUARANTINE = {}        # file name -> DataFrame of removed rows


def num(s):
    return pd.to_numeric(s.str.strip(), errors="coerce")


def log_step(table, issue, action, rows, note=""):
    CLEANING_LOG.append({"table": table, "issue": issue, "action": action,
                         "rows_affected": int(rows), "note": note})
    print(f"  [{table}] {issue}: {action} -> {int(rows):,} rows. {note}")


def record_changes(table, df, mask, col, old_values):
    """Store one row per changed cell: table, key column, key, column, old, new."""
    key = PK[table]
    VALUE_CHANGES.append(pd.DataFrame({
        "table": table, "key_column": key, "key": df.loc[mask, key].values,
        "column": col, "old_value": old_values[mask].values, "new_value": df.loc[mask, col].values,
    }))


def quarantine(table, name, rows, reason):
    rows = rows.copy()
    rows.insert(0, "quarantine_reason", reason)
    QUARANTINE[f"quarantine_{table}_{name}.csv"] = (table, rows)


def load_raw(name):
    return pd.read_csv(RAW_DIR / f"{name}.csv", dtype=str, keep_default_na=False)


def market_holidays(dates):
    """Fixed-date US market holidays (New Year, July 4, Christmas), observed weekday."""
    hol = []
    for y in sorted(dates.dt.year.dropna().unique()):
        for m, d in [(1, 1), (7, 4), (12, 25)]:
            h = pd.Timestamp(int(y), m, d)
            if h.dayofweek == 5 and (m, d) != (1, 1):
                h -= pd.Timedelta(days=1)
            elif h.dayofweek == 6:
                h += pd.Timedelta(days=1)
            if h.dayofweek < 5:
                hol.append(h)
    return pd.Series(hol)
# ---------------------------------------------------------------------------
# STEP 1 - Standardize formats (decision log F1, F9, D2)
# ---------------------------------------------------------------------------
def step_f1_security_id(T):
    t = T["fact_transactions"]
    old = t["security_id"].copy()
    has = old != ""
    # Guard: only strip a decimal part that is exactly ".0" - never round a real decimal
    assert old[has].str.fullmatch(r"\d+\.0").all(), "security_id has a non-.0 decimal - stop"
    t["security_id"] = old.str.replace(r"\.0$", "", regex=True)
    changed = old != t["security_id"]
    record_changes("fact_transactions", t, changed, "security_id", old)
    match_before = old[has].isin(set(T["dim_security"]["security_id"])).mean()
    match_after = t.loc[has, "security_id"].isin(set(T["dim_security"]["security_id"])).mean()
    log_step("fact_transactions", "F1 security_id stored as '45.0'", "convert to integer text",
             changed.sum(), f"RI match {match_before:.1%} -> {match_after:.1%}")
    assert match_after == 1.0, "security_id still has orphans after format fix"
    assert t.loc[has, "security_id"].str.fullmatch(r"\d+").all()


def step_f9_return_pct(T):
    p = T["fact_portfolio_snapshot"]
    old = p["return_ytd"].copy()
    pct = old.str.endswith("%")
    fixed = (num(old[pct].str.rstrip("%")) / 100).round(6)
    p.loc[pct, "return_ytd"] = fixed.map(lambda v: f"{v:.6f}".rstrip("0").rstrip("."))
    record_changes("fact_portfolio_snapshot", p, pct, "return_ytd", old)
    # Reconcile: return - benchmark_return must equal active_alpha on EVERY row
    gap = (num(p["return_ytd"]) - num(p["benchmark_return_ytd"]) - num(p["active_alpha_ytd"])).abs()
    log_step("fact_portfolio_snapshot", "F9 return_ytd stored as '9.28%'", "strip % and divide by 100",
             pct.sum(), f"max |return - bench - alpha| after fix = {gap.max():.6f}")
    assert num(p["return_ytd"]).notna().all(), "return_ytd still has non-numeric values"
    assert (gap <= 1e-4).all(), "alpha identity fails after % fix"


def step_d2_state(T):
    c = T["dim_client"]
    old = c["state"].copy()
    c["state"] = old.replace(STATE_CODES)
    changed = old != c["state"]
    record_changes("dim_client", c, changed, "state", old)
    log_step("dim_client", "D2 full state names", "standardize to USPS codes", changed.sum(),
             f"invalid before {(~old.isin(US_STATES)).sum()}, after {(~c['state'].isin(US_STATES)).sum()}")
    assert c["state"].isin(US_STATES).all(), "state still has non-USPS values"


# ---------------------------------------------------------------------------
# STEP 2 - De-duplicate dimensions (D1)
# ---------------------------------------------------------------------------
def step_d1_duplicate_clients(T):
    c = T["dim_client"]
    keys = ["first_name", "age", "city", "zip_code", "initial_aum"]
    c = c.assign(_id=c["client_id"].astype(int)).sort_values("_id")
    dup = c.duplicated(keys, keep="first")             # later (higher) ID = the copy
    original_id = c.groupby(keys)["client_id"].transform("first")
    removed = c[dup].drop(columns="_id").assign(duplicate_of_client_id=original_id[dup])
    # Verify before removing: copies must not be used by any fact table
    used = set(T["fact_fees"]["client_id"]) | set(T["fact_portfolio_snapshot"]["client_id"]) \
        | set(T["fact_transactions"]["client_id"])
    assert not removed["client_id"].isin(used).any(), "a duplicate client ID is used by facts - stop"
        # Verify the copy's last name differs by exactly one final letter (Taylo/Taylor, Leen/Lee)
    orig = c.set_index("client_id").loc[removed["duplicate_of_client_id"]].reset_index()
    assert all(n != o and (n == o[:-1] or n[:-1] == o)
               for n, o in zip(removed["last_name"], orig["last_name"])), "last-name rule broken"
    # Verify the other 7 attributes are identical to the original (decision log D1)
    for col in ["state", "risk_profile", "client_tier", "primary_account_type",
                "client_since", "advisor_id", "is_active"]:
        assert (removed[col].values == orig[col].values).all(), f"duplicate differs on {col}"
    # Verify exactly the IDs the decision log names were removed
    assert sorted(removed["client_id"].astype(int)) == list(range(2501, 2526))
    quarantine("dim_client", "duplicates", removed, "D1 duplicate of another client_id (last name mistyped)")
    before = len(c)
    T["dim_client"] = c[~dup].drop(columns="_id").sort_index()
    log_step("dim_client", "D1 duplicate clients", "quarantine", dup.sum(),
             f"rows {before:,} -> {len(T['dim_client']):,}")
    assert not T["dim_client"].duplicated(keys).any()
    assert len(T["dim_client"]) == 2500


# ---------------------------------------------------------------------------
# STEP 3 - Fill from a verified source (D3) and fix dim_date (D9)
# ---------------------------------------------------------------------------
def step_d3_risk_profile(T):
    c = T["dim_client"]; p = T["fact_portfolio_snapshot"]
    assert p.groupby("client_id")["benchmark_id"].nunique().max() == 1, "a client changed benchmark"
    bench = p.drop_duplicates("client_id").set_index("client_id")["benchmark_id"]
    known = c[c["risk_profile"] != ""].assign(bm=lambda x: x["client_id"].map(bench)).dropna(subset=["bm"])
    profiles_per_bench = known.groupby("bm")["risk_profile"].unique()
    unique_map = {b: v[0] for b, v in profiles_per_bench.items() if len(v) == 1}   # only 1-to-1 benchmarks
    print(f"  benchmark -> risk_profile (only unambiguous ones used): {unique_map}")
    old = c["risk_profile"].copy()
    blank = old == ""
    fill = c.loc[blank, "client_id"].map(bench).map(unique_map)
    c.loc[blank, "risk_profile"] = fill.fillna("")
    c["flag_risk_profile_imputed"] = (blank & fill.reindex(c.index).notna()).astype(int)
    changed = old != c["risk_profile"]
    record_changes("dim_client", c, changed, "risk_profile", old)
    log_step("dim_client", "D3 blank risk_profile", "fill from snapshot benchmark + flag", changed.sum(),
             f"blanks before {blank.sum()}, after {(c['risk_profile'] == '').sum()}")
    assert (c["risk_profile"] != "").all(), "risk_profile still has blanks"
    assert c.loc[changed, "risk_profile"].eq("Balanced").all()


def step_d9_holidays(T):
    d = T["dim_date"]
    dt = pd.to_datetime(d["date"], format="%Y-%m-%d")
    old = d["is_trading_day"].copy()
    hol = dt.isin(market_holidays(dt))
    d.loc[hol, "is_trading_day"] = "0"
    changed = old != d["is_trading_day"]
    record_changes("dim_date", d, changed, "is_trading_day", old)
    log_step("dim_date", "D9 market holidays marked as trading days", "set is_trading_day = 0",
             changed.sum(), "New Year, July 4, Christmas (observed)")
    assert changed.sum() == 14, "expected 14 holidays (decision log D9)"
# ---------------------------------------------------------------------------
# STEP 4 - Quarantine true orphans (F2)
# ---------------------------------------------------------------------------
def step_f2_orphan_clients(T):
    t = T["fact_transactions"]
    orphan = ~t["client_id"].isin(set(T["dim_client"]["client_id"]))
    quarantine("fact_transactions", "orphan_client", t[orphan], "F2 client_id not in dim_client")
    before = len(t)
    T["fact_transactions"] = t[~orphan].copy()
    log_step("fact_transactions", "F2 orphan client_id", "quarantine", orphan.sum(),
             f"{t.loc[orphan, 'client_id'].nunique()} distinct IDs; rows {before:,} -> {len(T['fact_transactions']):,}")
    assert T["fact_transactions"]["client_id"].isin(set(T["dim_client"]["client_id"])).all()


# ---------------------------------------------------------------------------
# STEP 5 - Sign fix (F3) and flags (F6, F7, F10, F11)
# ---------------------------------------------------------------------------
def step_f3_negative_shares(T):
    t = T["fact_transactions"]
    sh, pr, am = num(t["shares"]), num(t["price"]), num(t["amount"])
    neg = sh < 0
    # Reconcile BEFORE fixing: amount must equal |shares| x price, so only the sign is wrong
    assert ((sh[neg].abs() * pr[neg] - am[neg]).abs() <= 0.01).all(), "amount does not reconcile to the cent"
    assert t.loc[neg, "txn_type"].eq("Buy").all(), "negative shares on a non-Buy row - stop"
    old = t["shares"].copy()
    t.loc[neg, "shares"] = old[neg].str.lstrip("-")
    record_changes("fact_transactions", t, neg, "shares", old)
    log_step("fact_transactions", "F3 negative shares on Buy", "absolute value (amount reconciles)",
             neg.sum(), f"negatives before {neg.sum()}, after {(num(t['shares']) < 0).sum()}")
    assert (num(t["shares"]) < 0).sum() == 0
    assert (num(t.loc[neg, "shares"]) == num(old[neg]).abs()).all(), "size changed, not just sign"
    assert ((t["shares"] == "") == (old == "")).all(), "blank shares changed"
    assert num(t.loc[t["shares"] != "", "shares"]).notna().all(), "non-numeric shares"


def step_flags(T):
    t = T["fact_transactions"]; p = T["fact_portfolio_snapshot"]; f = T["fact_fees"]
    c = T["dim_client"]; d = T["dim_date"]

    # F6 - Buy/Sell on a non-trading day (uses the corrected dim_date from D9)
    trading = t["txn_date"].map(d.set_index("date")["is_trading_day"])
    assert trading.notna().all(), "txn_date missing from dim_date"
    t["flag_nontrading_day"] = (t["txn_type"].isin(["Buy", "Sell"]) & (trading == "0")).astype(int)
    log_step("fact_transactions", "F6 Buy/Sell on non-trading day", "flag", t["flag_nontrading_day"].sum())

    # F7 - activity after the client's last snapshot month
    last = p.groupby("client_id")["snapshot_date"].max().str[:7]
    lm = t["client_id"].map(last)
    t["flag_after_account_close"] = (lm.notna() & (t["txn_date"].str[:7] > lm)).astype(int)
    inactive = t.loc[t["flag_after_account_close"] == 1, "client_id"].map(c.set_index("client_id")["is_active"])
    log_step("fact_transactions", "F7 txn after account close", "flag", t["flag_after_account_close"].sum(),
             f"all for inactive clients: {inactive.eq('False').all()}")
    assert inactive.eq("False").all()

    # F10 - AUM placeholder 1,000.00 in snapshots and the fees charged on it
    p["flag_aum_placeholder"] = (num(p["aum"]) == AUM_PLACEHOLDER).astype(int)
    f["flag_aum_placeholder"] = (num(f["aum_basis"]) == AUM_PLACEHOLDER).astype(int)
    log_step("fact_portfolio_snapshot", "F10 AUM placeholder 1000.00", "flag", p["flag_aum_placeholder"].sum())
    log_step("fact_fees", "F10 fee on AUM placeholder 1000.00", "flag", f["flag_aum_placeholder"].sum())

    # F11 - implausible YTD returns / alpha
    p["flag_return_outlier"] = ((num(p["return_ytd"]).abs() > 1) | (num(p["active_alpha_ytd"]).abs() > 1)).astype(int)
    log_step("fact_portfolio_snapshot", "F11 |return_ytd| or |alpha| > 100%", "flag", p["flag_return_outlier"].sum())

        # Flag counts must match the decision log (after the 200 orphan rows were quarantined)
    expected = {("fact_transactions", "flag_nontrading_day"): 41725,
                ("fact_transactions", "flag_after_account_close"): 2410,
                ("fact_portfolio_snapshot", "flag_aum_placeholder"): 420,
                ("fact_fees", "flag_aum_placeholder"): 386,
                ("fact_portfolio_snapshot", "flag_return_outlier"): 1282}
    for (name, col), n in expected.items():
        assert T[name][col].sum() == n, f"{name}.{col}: {T[name][col].sum()} flagged, expected {n}"


# ---------------------------------------------------------------------------
# Leave-as-is decisions (logged so the audit trail is complete)
# ---------------------------------------------------------------------------
def log_left_as_is():
    for table, issue, note in [
        ("dim_client", "D4 is_active=True with no Dec-2024 snapshot", "resolved by D1 (all 24 were duplicate IDs)"),
        ("dim_client", "D5 zip_code leading zeros", "kept as text; BI must load as Text"),
        ("dim_advisor", "D6 certifications = 'None'", "legitimate value: no certifications"),
        ("dim_security", "D7 blank sector (ETFs) / expense_ratio (stocks)", "legitimate structure"),
        ("dim_security", "D8 same name, different ticker", "different products"),
        ("fact_transactions", "F4 blank security/shares/price on cash rows", "legitimate structure"),
        ("fact_transactions", "F5 Dividend amount = position value", "no data to recompute; documented limitation"),
        ("fact_transactions", "F8 Advisory Fee txns vs fact_fees", "fact_fees is source of truth; documented"),
        ("fact_fees", "F12 bps_charged 100.38", "within Retail range, amount reconciles"),
    ]:
        log_step(table, issue, "leave as is", 0, note)


# ---------------------------------------------------------------------------
# Save + prove raw rows = clean rows + quarantined rows
# ---------------------------------------------------------------------------
def save_all(T, raw_counts):
    print("\nRow reconciliation (raw = clean + quarantined):")
    for name in TABLES:
        q = sum(len(df) for (tbl, df) in QUARANTINE.values() if tbl == name)
        clean = len(T[name])
        print(f"  {name:<26} raw {raw_counts[name]:>8,} = clean {clean:>8,} + quarantined {q:>4,}")
        assert raw_counts[name] == clean + q, f"{name}: rows lost or created!"
        T[name].to_csv(CLEAN_DIR / f"{name}.csv", index=False)
    for fname, (_, df) in QUARANTINE.items():
        df.to_csv(AUDIT_DIR / fname, index=False)
    pd.DataFrame(CLEANING_LOG).to_csv(AUDIT_DIR / "cleaning_log.csv", index=False)
    vc = pd.concat(VALUE_CHANGES, ignore_index=True)
    vc.to_csv(AUDIT_DIR / "value_changes.csv", index=False)
    print(f"\nSaved 8 clean tables to {CLEAN_DIR}")
    print(f"Saved cleaning_log.csv ({len(CLEANING_LOG)} steps), value_changes.csv ({len(vc):,} cell changes), "
          f"{len(QUARANTINE)} quarantine files")


def main():
    T = {name: load_raw(name) for name in TABLES}
    raw_counts = {name: len(df) for name, df in T.items()}
    print("STEP 1 - standardize formats")
    step_f1_security_id(T)
    step_f9_return_pct(T)
    step_d2_state(T)
    print("STEP 2 - de-duplicate dimensions")
    step_d1_duplicate_clients(T)
    print("STEP 3 - fill from verified sources / fix calendar")
    step_d3_risk_profile(T)
    step_d9_holidays(T)
    print("STEP 4 - quarantine orphans")
    step_f2_orphan_clients(T)
    print("STEP 5 - sign fix and flags")
    step_f3_negative_shares(T)
    step_flags(T)
    print("Leave-as-is decisions")
    log_left_as_is()
    save_all(T, raw_counts)


if __name__ == "__main__":
    main()