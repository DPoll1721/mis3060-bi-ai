"""
HW4 Part D - Referential integrity, rule checks, reconciliations, IQR outliers,
and a raw-vs-clean data quality scorecard.
Run from the repo root:  python hw04/scripts/03_validate.py

Outputs (hw04/reports/):
    data_quality_scorecard.csv  one row per table per stage (raw / clean)
    ri_results.csv              all 13 relationships, raw and clean
    rule_checks.csv             every business-rule check, raw and clean
    reconciliations.csv         cross-table / recomputed-amount checks, raw and clean
    iqr_outliers.csv            IQR outlier flags on unbounded numeric columns
"""
from pathlib import Path
import pandas as pd

HW_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = HW_DIR / "data"
REPORT_DIR = HW_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TABLES = [
    "dim_advisor", "dim_client", "dim_date", "dim_security", "dim_benchmark",
    "fact_fees", "fact_portfolio_snapshot", "fact_transactions",
]


def load(stage, name):
    return pd.read_csv(DATA_DIR / stage / f"{name}.csv", dtype=str, keep_default_na=False)


def num(s):
    return pd.to_numeric(s.str.strip(), errors="coerce")


# ---------------------------------------------------------------------------
# 1. REUSABLE REFERENTIAL INTEGRITY FUNCTION  (keep for Assignment 5)
# ---------------------------------------------------------------------------
def check_referential_integrity(fact_df, fact_key, dim_df, dim_key):
    """Check that every non-blank fact_df[fact_key] exists in dim_df[dim_key].

    Returns a dict with:
        rows, null_keys, null_key_rate  - blank/null foreign keys (not counted as orphans)
        orphan_rows                     - non-blank keys with no match in the dimension
        distinct_orphan_keys            - how many different orphan key values
        match_rate                      - matched / non-blank keys (1.0 = perfect)
        orphan_examples                 - up to 5 orphan key values
        parent_duplicate_keys           - duplicated keys in the dimension (must be 0)
    """
    fk = fact_df[fact_key].astype(str).str.strip()
    is_null = fk.isin(["", "nan", "None", "NaN"]) | fact_df[fact_key].isna()
    parent = dim_df[dim_key].astype(str).str.strip()
    valid_keys = set(parent)
    orphan = ~is_null & ~fk.isin(valid_keys)
    non_null = int((~is_null).sum())
    return {
        "rows": len(fk),
        "null_keys": int(is_null.sum()),
        "null_key_rate": round(is_null.mean(), 6) if len(fk) else 0.0,
        "orphan_rows": int(orphan.sum()),
        "distinct_orphan_keys": int(fk[orphan].nunique()),
        "match_rate": round((non_null - int(orphan.sum())) / non_null, 6) if non_null else 1.0,
        "orphan_examples": "; ".join(fk[orphan].unique()[:5]),
        "parent_duplicate_keys": int(parent.duplicated().sum()),
    }


# (child table, FK column, parent table, PK column) - 10 ID-based + 3 date joins
RELATIONSHIPS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]


def run_ri(T, stage):
    rows = []
    for child, fk, parent, pk in RELATIONSHIPS:
        r = check_referential_integrity(T[child], fk, T[parent], pk)
        rows.append({"stage": stage, "relationship": f"{child}.{fk} -> {parent}.{pk}",
                     "child_table": child, **r})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2. RULE-BASED CHECKS (natural business bounds, allowed lists, sign rules)
#    Each rule returns (pass_mask, applies_mask). Pass rates use ONLY the rows a
#    rule applies to, so out-of-scope rows (e.g. cash rows for a trade rule)
#    never count as passes. Unparseable values fail.
# ---------------------------------------------------------------------------
US_STATES = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY",
             "LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND",
             "OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"}
ACCOUNT_TYPES = {"Taxable", "IRA", "Roth IRA", "Trust", "529"}


def between(s, lo=None, hi=None):
    x = num(s)
    ok = x.notna()
    if lo is not None:
        ok &= x >= lo
    if hi is not None:
        ok &= x <= hi
    return ok


def market_holidays(dates):
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


def rules_for(name, T):
    """Return {rule name: (pass_mask, applies_mask)} for one table."""
    df = T[name]
    ALL = pd.Series(True, index=df.index)
    R = {}
    if name == "dim_advisor":
        R["years_experience in [0, 50]"] = (between(df["years_experience"], 0, 50), ALL)
        R["aum_target_mm > 0"] = (between(df["aum_target_mm"], 0.01), ALL)
        R["region in allowed list"] = (df["region"].isin({"Northeast", "Mid-Atlantic", "Southeast", "Midwest", "West"}), ALL)
    elif name == "dim_client":
        ia = num(df["initial_aum"])
        R["age in [18, 110]"] = (between(df["age"], 18, 110), ALL)
        R["initial_aum > 0"] = (between(df["initial_aum"], 0.01), ALL)
        R["state is USPS code"] = (df["state"].isin(US_STATES), ALL)
        R["risk_profile in allowed list"] = (df["risk_profile"].isin(
            {"Conservative", "Moderately Conservative", "Balanced", "Moderately Aggressive", "Aggressive"}), ALL)
        R["client_tier in allowed list"] = (df["client_tier"].isin({"Retail", "HNW", "UHNW"}), ALL)
        R["primary_account_type in allowed list"] = (df["primary_account_type"].isin(ACCOUNT_TYPES), ALL)
        R["is_active is True/False"] = (df["is_active"].isin({"True", "False"}), ALL)
        R["zip_code is 5 digits"] = (df["zip_code"].str.fullmatch(r"\d{5}"), ALL)
        band = pd.Series("UHNW", index=df.index).mask(ia < 5_000_000, "HNW").mask(ia < 500_000, "Retail")
        R["client_tier matches initial_aum band"] = (band == df["client_tier"], ia.notna())
        # Decision log D4: every active client has a snapshot in the last month
        p = T["fact_portfolio_snapshot"]
        last = set(p.loc[p["snapshot_date"] == p["snapshot_date"].max(), "client_id"])
        R["active client has a snapshot in the last month (D4)"] = (df["client_id"].isin(last),
                                                                    df["is_active"] == "True")
    elif name == "dim_date":
        dt = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
        R["year/month/quarter match date"] = (
            (dt.dt.year.astype("Int64").astype(str) == df["year"]) &
            (dt.dt.month.astype("Int64").astype(str) == df["month"]) &
            (dt.dt.quarter.astype("Int64").astype(str) == df["quarter"]), ALL)
        R["is_month_end matches date"] = (dt.dt.is_month_end.astype(int).astype(str) == df["is_month_end"], ALL)
        for c in ["is_month_end", "is_quarter_end", "is_year_end", "is_trading_day"]:
            R[f"{c} is 0/1"] = (df[c].isin({"0", "1"}), ALL)
        expected = ((dt.dt.dayofweek < 5) & ~dt.isin(market_holidays(dt))).astype(int).astype(str)
        R["is_trading_day = weekday and not a market holiday"] = (expected == df["is_trading_day"], ALL)
    elif name == "dim_security":
        etf = df["is_etf"] == "True"
        R["asset_class in allowed list"] = (df["asset_class"].isin(
            {"Equity", "Fixed Income", "Alternative", "Cash Equivalent"}), ALL)
        R["is_etf is True/False"] = (df["is_etf"].isin({"True", "False"}), ALL)
        R["ETF expense_ratio_bps in (0, 300]"] = (between(df["expense_ratio_bps"], 0.01, 300), etf)
        R["stock has no expense ratio"] = (df["expense_ratio_bps"] == "", ~etf)
        R["stock has sector, ETF has none"] = ((etf & (df["sector"] == "")) | (~etf & (df["sector"] != "")), ALL)
    elif name == "dim_benchmark":
        R["ticker_proxy not blank"] = (df["ticker_proxy"].str.strip() != "", ALL)
    elif name == "fact_fees":
        R["aum_basis > 0"] = (between(df["aum_basis"], 0.01), ALL)
        R["bps_charged in (0, 200]"] = (between(df["bps_charged"], 0.01, 200), ALL)
        R["amount >= 0"] = (between(df["amount"], 0), ALL)
        R["fee_type in allowed list"] = (df["fee_type"].isin({"Management", "Advisory", "Custodial", "Performance"}), ALL)
    elif name == "fact_portfolio_snapshot":
        R["aum > 0"] = (between(df["aum"], 0.01), ALL)
        R["return_ytd >= -100% (cannot lose more than everything)"] = (between(df["return_ytd"], -1), ALL)
        R["benchmark_return_ytd in [-100%, 100%]"] = (between(df["benchmark_return_ytd"], -1, 1), ALL)
        R["cash_pct in [0, 1]"] = (between(df["cash_pct"], 0, 1), ALL)
        R["year/month match snapshot_date"] = ((df["year"] == df["snapshot_date"].str[:4]) &
                                               (df["month"].str.zfill(2) == df["snapshot_date"].str[5:7]), ALL)
        R["account_type in allowed list"] = (df["account_type"].isin(ACCOUNT_TYPES), ALL)
    elif name == "fact_transactions":
        trade = df["txn_type"].isin(["Buy", "Sell", "Dividend"])
        R["txn_type in allowed list"] = (df["txn_type"].isin(
            {"Buy", "Sell", "Dividend", "Deposit", "Withdrawal", "Advisory Fee"}), ALL)
        R["sign rule: shares > 0 on trades"] = (between(df["shares"], 0.0001), trade)
        R["price > 0 on trades"] = (between(df["price"], 0.01), trade)
        R["sign rule: amount > 0"] = (between(df["amount"], 0.01), ALL)
        R["cash rows have no security, shares or price"] = (
            (df["security_id"] == "") & (df["shares"] == "") & (df["price"] == ""), ~trade)
    # Cross-table consistency: the same fact stored in two places must agree
    if name in ("fact_fees", "fact_portfolio_snapshot", "fact_transactions"):
        c = T["dim_client"].drop_duplicates("client_id").set_index("client_id")
        exp_adv = df["client_id"].map(c["advisor_id"])
        R["advisor_id = client's advisor (dim_client)"] = (exp_adv == df["advisor_id"], exp_adv.notna())
        if name == "fact_portfolio_snapshot":
            exp_acct = df["client_id"].map(c["primary_account_type"])
            R["account_type = client's primary_account_type"] = (exp_acct == df["account_type"], exp_acct.notna())
    return R


def run_rules(T, stage):
    rows = []
    for name in TABLES:
        for rule, (ok, applies) in rules_for(name, T).items():
            ok = ok.fillna(False).astype(bool)
            applies = applies.fillna(False).astype(bool)
            n = int(applies.sum())
            fails = int((applies & ~ok).sum())
            rows.append({"stage": stage, "table": name, "rule": rule, "applicable_rows": n,
                         "fail_rows": fails, "pass_rate": round(1 - fails / n, 6) if n else 1.0})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. CROSS-TABLE RECONCILIATIONS (recomputed vs stored). Unparseable = mismatch.
# ---------------------------------------------------------------------------
def run_reconciliations(T, stage):
    f, p, t = T["fact_fees"], T["fact_portfolio_snapshot"], T["fact_transactions"]
    out = []

    def add(name, compared, mismatches, note):
        out.append({"stage": stage, "reconciliation": name, "rows_compared": int(compared),
                    "mismatches": int(mismatches),
                    "match_rate": round(1 - mismatches / compared, 6) if compared else 1.0, "note": note})

    # R1 fee amount = aum_basis x bps / 10,000 / 12
    gap1 = (num(f["aum_basis"]) * num(f["bps_charged"]) / 10_000 / 12 - num(f["amount"])).abs()
    add("R1 fact_fees.amount = aum_basis x bps / 10000 / 12", len(f),
        (gap1.isna() | (gap1 > 0.02)).sum(), "tolerance $0.02")

    # R2 fee aum_basis = snapshot aum for the same client and date (two tables, same fact)
    m = f.merge(p[["client_id", "snapshot_date", "aum"]], how="left",
                left_on=["client_id", "fee_date"], right_on=["client_id", "snapshot_date"])
    assert len(m) == len(f), "snapshot grain is not unique - merge added rows"
    gap2 = (num(m["aum_basis"]) - num(m["aum"].fillna(""))).abs()
    add("R2 fact_fees.aum_basis = fact_portfolio_snapshot.aum", len(f),
        (gap2.isna() | (gap2 > 0.01)).sum(), "joined on client_id + date (all are the 1st of the month); tolerance $0.01")

    # R3 active_alpha = return - benchmark_return (recomputed vs stored)
    gap3 = (num(p["return_ytd"]) - num(p["benchmark_return_ytd"]) - num(p["active_alpha_ytd"])).abs()
    add("R3 snapshot.active_alpha_ytd = return_ytd - benchmark_return_ytd", len(p),
        (gap3.isna() | (gap3 > 1e-4)).sum(), "tolerance 0.0001")

    # R4 trade amount = shares x price (signed shares: a negative count breaks it)
    tr = t[t["txn_type"].isin(["Buy", "Sell"])]
    gap4 = (num(tr["shares"]) * num(tr["price"]) - num(tr["amount"])).abs()
    add("R4 Buy/Sell amount = shares x price", len(tr),
        (gap4.isna() | (gap4 > 0.01)).sum(), "tolerance $0.01")

    # R5 Advisory Fee transactions vs fact_fees (known limitation F8 - expected to fail)
    af = t[t["txn_type"] == "Advisory Fee"].assign(ym=lambda x: x["txn_date"].str[:7], a=lambda x: num(x["amount"]))
    ff = f.assign(ym=f["fee_date"].str[:7], a=num(f["amount"]))
    j = pd.concat([af.groupby(["client_id", "ym"])["a"].sum(), ff.groupby(["client_id", "ym"])["a"].sum()],
                  axis=1, keys=["txn", "fee"])
    both = j.dropna()
    add("R5 Advisory Fee txns = fact_fees (client-month)", len(both),
        ((both["txn"] - both["fee"]).abs() > 0.02).sum(),
        f"known limitation F8; {j['txn'].isna().sum()} fee months with no txn, {j['fee'].isna().sum()} txn months with no fee")

    # R6 risk_profile consistent with the snapshot benchmark - re-verifies the D3 fill
    c = T["dim_client"].drop_duplicates("client_id")
    bm = c["client_id"].map(p.drop_duplicates("client_id").set_index("client_id")["benchmark_id"])
    allowed = {"1": {"Aggressive", "Moderately Aggressive"}, "3": {"Balanced"},
               "8": {"Conservative", "Moderately Conservative"}}
    has = bm.notna()
    ok = [rp in allowed.get(b, set()) for rp, b in zip(c.loc[has, "risk_profile"], bm[has])]
    add("R6 dim_client.risk_profile consistent with snapshot benchmark", int(has.sum()), len(ok) - sum(ok),
        "benchmark 1 = (Mod.) Aggressive, 3 = Balanced, 8 = (Mod.) Conservative")
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# 4. IQR OUTLIERS on numeric columns with no natural upper bound
# ---------------------------------------------------------------------------
IQR_COLUMNS = [("dim_client", "initial_aum", None), ("fact_portfolio_snapshot", "aum", None),
               ("fact_transactions", "amount", ["Buy", "Sell"]),   # trades only - don't pool deposits/fees
               ("fact_fees", "amount", None)]


def run_iqr(T, stage):
    rows = []
    for table, col, types in IQR_COLUMNS:
        df = T[table] if types is None else T[table][T[table]["txn_type"].isin(types)]
        x = num(df[col]).dropna()
        q1, q3 = x.quantile(0.25), x.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        flagged = (x < lo) | (x > hi)
        rows.append({"stage": stage, "table": table, "column": col,
                     "subset": "all rows" if types is None else "/".join(types), "n": len(x),
                     "q1": round(q1, 2), "q3": round(q3, 2), "iqr": round(iqr, 2),
                     "lower_fence": round(lo, 2), "upper_fence": round(hi, 2),
                     "flagged": int(flagged.sum()), "flagged_pct": round(flagged.mean() * 100, 2),
                     "max_value": round(x.max(), 2)})
    return pd.DataFrame(rows)


IQR_NOTE = ("Flagged does not mean wrong: AUM and transaction amounts are heavily right-skewed "
            "(a few UHNW clients hold $5M-$50M), so the IQR fence flags real large accounts; "
            "a flag is a prompt to investigate, and only a business rule or reconciliation can prove a value is wrong.")


# ---------------------------------------------------------------------------
# 5. SCORECARD - one row per table per stage
#    completeness  = filled required cells / required cells (blanks-by-design excluded)
#    uniqueness    = 1 - extra copies / rows, worst of PK and natural key (keep="first")
#    type validity = non-blank typed cells that parse / non-blank typed cells
#    rule pass     = 1 - failing applicable rows / applicable rows, over all rules
#    referential   = 1 - orphan FK values / non-blank FK values, over the table's FKs
# ---------------------------------------------------------------------------
PK = {"dim_advisor": "advisor_id", "dim_client": "client_id", "dim_date": "date_id",
      "dim_security": "security_id", "dim_benchmark": "benchmark_id", "fact_fees": "fee_id",
      "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}
NATURAL_KEY = {"dim_client": ["first_name", "age", "city", "zip_code", "initial_aum"],
               "dim_date": ["date"], "dim_security": ["ticker"],
               "fact_fees": ["client_id", "fee_date"], "fact_portfolio_snapshot": ["client_id", "snapshot_date"]}
TYPES = {
    "dim_advisor": {"advisor_id": "int", "years_experience": "int", "aum_target_mm": "int"},
    "dim_client": {"client_id": "int", "age": "int", "initial_aum": "dec", "client_since": "date",
                   "advisor_id": "int", "is_active": "bool"},
    "dim_date": {"date_id": "int", "date": "date", "year": "int", "quarter": "int", "month": "int",
                 "week_of_year": "int"},
    "dim_security": {"security_id": "int", "benchmark_id": "int", "is_etf": "bool", "expense_ratio_bps": "dec"},
    "dim_benchmark": {"benchmark_id": "int"},
    "fact_fees": {"fee_id": "int", "client_id": "int", "advisor_id": "int", "fee_date": "date",
                  "aum_basis": "dec", "bps_charged": "dec", "amount": "dec"},
    "fact_portfolio_snapshot": {"snapshot_id": "int", "client_id": "int", "advisor_id": "int",
                                "benchmark_id": "int", "snapshot_date": "date", "year": "int", "month": "int",
                                "aum": "dec", "return_ytd": "dec", "benchmark_return_ytd": "dec",
                                "active_alpha_ytd": "dec", "cash_pct": "dec"},
    "fact_transactions": {"txn_id": "int", "client_id": "int", "advisor_id": "int", "security_id": "int",
                          "txn_date": "date", "shares": "dec", "price": "dec", "amount": "dec"},
}


def legit_blank(name, df):
    """Cells that are blank by design (decision log D7, F4) - excluded from completeness."""
    m = pd.DataFrame(False, index=df.index, columns=df.columns)
    if name == "fact_transactions":
        cash = ~df["txn_type"].isin(["Buy", "Sell", "Dividend"])
        for c in ["security_id", "shares", "price"]:
            m[c] = cash
    if name == "dim_security":
        m["sector"] = df["is_etf"] == "True"
        m["expense_ratio_bps"] = df["is_etf"] == "False"
    return m


def type_ok(s, typ):
    v = s.str.strip()
    if typ == "int":
        return v.str.fullmatch(r"-?\d+")
    if typ == "dec":
        return num(v).notna()
    if typ == "date":
        return pd.to_datetime(v, format="%Y-%m-%d", errors="coerce").notna()
    return v.isin({"True", "False"})


def scorecard(T, stage, ri, rules):
    rows = []
    for name in TABLES:
        df = T[name]
        d = df[[c for c in df.columns if not c.startswith("flag_")]]
        required = ~legit_blank(name, d)
        filled = d.apply(lambda s: s.str.strip() != "")
        completeness = (filled & required).values.sum() / required.values.sum()

        keys = [[PK[name]]] + ([NATURAL_KEY[name]] if name in NATURAL_KEY else [])
        uniqueness = min(1 - d.duplicated(k, keep="first").mean() for k in keys)

        checked = passed = 0
        for col, typ in TYPES[name].items():
            nonblank = d[col].str.strip() != ""
            checked += int(nonblank.sum())
            passed += int((type_ok(d[col], typ) & nonblank).sum())
        type_validity = passed / checked if checked else 1.0

        r = rules[rules["table"] == name]
        rule_pass = 1 - r["fail_rows"].sum() / r["applicable_rows"].sum() if r["applicable_rows"].sum() else 1.0

        rr = ri[ri["child_table"] == name]
        non_null = (rr["rows"] - rr["null_keys"]).sum()
        ref = (1 - rr["orphan_rows"].sum() / non_null) if non_null else None

        rows.append({"table": name, "stage": stage, "rows": len(df),
                     "pct_completeness": round(completeness * 100, 2),
                     "pct_key_uniqueness": round(uniqueness * 100, 2),
                     "pct_type_validity": round(type_validity * 100, 2),
                     "pct_rule_pass": round(rule_pass * 100, 2),
                     "pct_referential_match": round(ref * 100, 2) if ref is not None else "n/a (no FKs)"})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# MAIN - run everything on raw AND clean
# ---------------------------------------------------------------------------
def main():
    all_ri, all_rules, all_rec, all_iqr, all_sc = [], [], [], [], []
    for stage in ["raw", "clean"]:
        T = {name: load(stage, name) for name in TABLES}
        ri = run_ri(T, stage)
        rules = run_rules(T, stage)
        all_ri.append(ri)
        all_rules.append(rules)
        all_rec.append(run_reconciliations(T, stage))
        all_iqr.append(run_iqr(T, stage))
        all_sc.append(scorecard(T, stage, ri, rules))
        print(f"Validated {stage}")

    ri = pd.concat(all_ri); rules = pd.concat(all_rules); rec = pd.concat(all_rec)
    iqr = pd.concat(all_iqr); sc = pd.concat(all_sc).sort_values(["table", "stage"], ascending=[True, False])
    ri.to_csv(REPORT_DIR / "ri_results.csv", index=False)
    rules.to_csv(REPORT_DIR / "rule_checks.csv", index=False)
    rec.to_csv(REPORT_DIR / "reconciliations.csv", index=False)
    iqr.assign(note=IQR_NOTE).to_csv(REPORT_DIR / "iqr_outliers.csv", index=False)
    sc.to_csv(REPORT_DIR / "data_quality_scorecard.csv", index=False)

    with pd.option_context("display.width", 250, "display.max_colwidth", 60, "display.max_rows", 100):
        print("\n=== Referential integrity (raw -> clean) ===")
        piv = ri.pivot_table(index="relationship", columns="stage", values="match_rate", sort=False)
        orphans = ri.pivot_table(index="relationship", columns="stage", values="orphan_rows", sort=False)
        print(pd.concat([piv[["raw", "clean"]], orphans[["raw", "clean"]]], axis=1,
                        keys=["match_rate", "orphan_rows"]).to_string())
        print("\n=== Rules that fail in raw or clean (fail_rows / applicable_rows) ===")
        rp = rules.pivot_table(index=["table", "rule"], columns="stage", values="fail_rows", sort=False)
        ap = rules.pivot_table(index=["table", "rule"], columns="stage", values="applicable_rows", sort=False)
        bad = (rp["raw"] > 0) | (rp["clean"] > 0)
        print(pd.concat([rp[["raw", "clean"]], ap[["raw", "clean"]]], axis=1,
                        keys=["fail_rows", "applicable_rows"])[bad].to_string())
        print(f"({len(rules) // 2} rules per stage; all others pass 100% in both stages)")
        print("\n=== Reconciliations (mismatches: raw -> clean) ===")
        print(rec.pivot_table(index="reconciliation", columns="stage", values="mismatches", sort=False)[["raw", "clean"]].to_string())
        print("\n=== IQR outliers (clean) ===")
        print(iqr[iqr["stage"] == "clean"][["table", "column", "subset", "q1", "q3", "upper_fence",
                                            "flagged", "flagged_pct", "max_value"]].to_string(index=False))
        print("Note:", IQR_NOTE)
        print("\n=== DATA QUALITY SCORECARD ===")
        print(sc.to_string(index=False))

    # The clean data must pass everything except the documented limitation R5
    c_ri, c_rules = ri[ri["stage"] == "clean"], rules[rules["stage"] == "clean"]
    c_rec, c_sc = rec[rec["stage"] == "clean"], sc[sc["stage"] == "clean"]
    assert (c_ri["orphan_rows"] == 0).all(), "clean data still has orphan keys"
    assert (c_ri["parent_duplicate_keys"] == 0).all(), "a dimension has duplicate keys"
    assert (c_rules["fail_rows"] == 0).all(), "clean data fails a business rule"
    assert (c_rec.loc[~c_rec["reconciliation"].str.startswith("R5"), "mismatches"] == 0).all(), "R1-R4/R6 fail on clean"
    assert (c_sc[["pct_completeness", "pct_key_uniqueness", "pct_type_validity", "pct_rule_pass"]] == 100).all().all()
    print("\nAll clean-data assertions passed.")
    print("Saved data_quality_scorecard.csv, ri_results.csv, rule_checks.csv, reconciliations.csv, iqr_outliers.csv")


if __name__ == "__main__":
    main()
