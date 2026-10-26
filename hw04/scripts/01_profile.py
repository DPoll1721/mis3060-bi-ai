"""
HW4 Part A - Audit / profile of the raw Wildcat Capital tables.
Run from the repo root:  python hw04/scripts/01_profile.py
"""
from pathlib import Path
import pandas as pd
import numpy as np

# Folder paths, worked out from where this script lives
HW_DIR = Path(__file__).resolve().parents[1]      # ...\hw04
RAW_DIR = HW_DIR / "data" / "raw"
REPORT_DIR = HW_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TABLES = [
    "dim_advisor", "dim_client", "dim_date", "dim_security", "dim_benchmark",
    "fact_fees", "fact_portfolio_snapshot", "fact_transactions",
]


def load_raw(name):
    """Read a table as pure text so nothing gets silently converted."""
    return pd.read_csv(RAW_DIR / f"{name}.csv", dtype=str, keep_default_na=False)


# ---------------------------------------------------------------------------
# GENERIC PROFILER - works on ANY table, nothing is specific to one file
# Speed trick: every check runs on the DISTINCT values of a column (with their
# counts), not on all 300K rows, and shapes use str.translate instead of regex.
# ---------------------------------------------------------------------------
SHAPE_MAP = str.maketrans("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
                          "9" * 10 + "A" * 52)


def value_shape(s):
    """'PA' -> 'AA', '45.0' -> '99.9', '9.28%' -> '9.99%'. Letters=A, digits=9."""
    return s.str.translate(SHAPE_MAP)


def format_family(shapes):
    """Collapse runs and drop the minus sign, so '7' and '25' are the same format
    but '45' and '45.0', or '0.09' and '9.28%', are not."""
    return (shapes.str.lstrip("-")
            .str.replace(r"9+", "9", regex=True).str.replace(r"A+", "A", regex=True))


def infer_type(vals, counts):
    """Guess the intended type from non-blank values (95% weighted majority)."""
    keep = vals.str.strip() != ""
    v, w = vals[keep].str.strip(), counts[keep]
    if w.sum() == 0:
        return "empty"
    share = lambda ok: (w * ok).sum() / w.sum()
    if share(v.str.fullmatch(r"-?\d+")) >= 0.95:
        return "integer"
    if share(pd.to_numeric(v, errors="coerce").notna()) >= 0.95:
        return "decimal"
    if share(v.str.fullmatch(r"\d{4}-\d{2}-\d{2}")) >= 0.95:
        return "date"
    if share(v.str.lower().isin(["true", "false"])) >= 0.95:
        return "boolean"
    return "text"


def parse_fails(s, typ):
    """True where a NON-blank value does not parse as the expected type."""
    v = s.str.strip()
    nonblank = v != ""
    if typ == "integer":
        ok = v.str.fullmatch(r"-?\d+")
    elif typ == "decimal":
        ok = pd.to_numeric(v, errors="coerce").notna()
    elif typ == "date":
        ok = pd.to_datetime(v, format="%Y-%m-%d", errors="coerce").notna()
    elif typ == "boolean":
        ok = v.str.lower().isin(["true", "false"])
    else:
        ok = pd.Series(True, index=s.index)
    return nonblank & ~ok


def profile_table(name, df):
    """One profile row per column."""
    rows = []
    for col in df.columns:
        vc = df[col].value_counts()                      # distinct value -> count
        vals = pd.Series(vc.index, dtype=str)
        cnt = pd.Series(vc.values)
        n = int(cnt.sum())
        blank = (vals.str.strip() == "").to_numpy()
        shapes = cnt[~blank].groupby(value_shape(vals[~blank]).to_numpy()).sum().sort_values(ascending=False)
        fam = shapes.groupby(format_family(pd.Series(shapes.index)).to_numpy()).sum().sort_values(ascending=False)
        typ = infer_type(vals, cnt)
        fails = parse_fails(vals, typ).to_numpy()
        nums = pd.to_numeric(vals.str.strip(), errors="coerce")
        ws = (vals != vals.str.strip()).to_numpy()
        rows.append({
            "table": name,
            "column": col,
            "rows": n,
            "null_blank": int(cnt[blank].sum()),
            "null_blank_pct": round(cnt[blank].sum() / n * 100, 2),
            "distinct": int((~blank).sum()),
            "inferred_type": typ,
            "parse_fail_count": int(cnt[fails].sum()),
            "parse_fail_pct": round(cnt[fails].sum() / n * 100, 3),
            "parse_fail_examples": "; ".join(vals[fails].head(3)),
            "whitespace_issues": int(cnt[ws].sum()),
            "n_shapes": len(shapes),
            "n_format_families": len(fam),
            "mixed_formats": len(fam) > 1,
            "top_shapes": "; ".join(f"{k} ({v})" for k, v in shapes.head(4).items()),
            "format_families": "; ".join(f"{k} ({v})" for k, v in fam.head(4).items()),
            "numeric_min": nums.min() if typ in ("integer", "decimal") else "",
            "numeric_max": nums.max() if typ in ("integer", "decimal") else "",
            "sample_values": "; ".join(vals[~blank].head(5)),
        })
    print(f"  profiled {name}", flush=True)
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# Findings collector
# ---------------------------------------------------------------------------
FINDINGS = []


def add_finding(table, group, check, column, severity, mask_or_count, total, example="", note=""):
    """Record one finding. mask_or_count is a boolean Series or an int."""
    n = int(mask_or_count.sum()) if isinstance(mask_or_count, pd.Series) else int(mask_or_count)
    FINDINGS.append({
        "table": table, "check_group": group, "check": check, "column": column,
        "severity": severity if n > 0 else "PASS",
        "rows_affected": n, "total_rows": total,
        "pct_affected": round(n / total * 100, 3) if total else 0,
        "example": str(example)[:200], "note": note,
    })


def examples(df, mask, cols, k=3):
    """Short text with up to k example rows for the report."""
    if not isinstance(mask, pd.Series) or mask.sum() == 0:
        return ""
    return " | ".join(df.loc[mask, cols].head(k).astype(str).agg(", ".join, axis=1))


def num(s):
    """Text -> number. Anything that is not a clean number (e.g. '9.28%') becomes NaN."""
    return pd.to_numeric(s.str.strip(), errors="coerce")


# ---------------------------------------------------------------------------
# RULE SPECS  (declarative - the check functions below are generic)
# ---------------------------------------------------------------------------
US_STATES = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY",
             "LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND",
             "OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"}

TABLE_SPECS = {
    "dim_advisor": {
        "pk": "advisor_id",
        "types": {"advisor_id": "integer", "years_experience": "integer", "aum_target_mm": "integer"},
        "ranges": {"years_experience": (0, 50), "aum_target_mm": (1, 1000)},
        "allowed": {"region": {"Northeast", "Mid-Atlantic", "Southeast", "Midwest", "West"}},
    },
    "dim_client": {
        "pk": "client_id",
        "types": {"client_id": "integer", "age": "integer", "initial_aum": "decimal",
                  "client_since": "date", "advisor_id": "integer", "is_active": "boolean"},
        "ranges": {"age": (18, 110), "initial_aum": (0.01, None)},
        "allowed": {"state": US_STATES,
                    "risk_profile": {"Conservative", "Moderately Conservative", "Balanced",
                                     "Moderately Aggressive", "Aggressive"},
                    "client_tier": {"Retail", "HNW", "UHNW"},
                    "primary_account_type": {"Taxable", "IRA", "Roth IRA", "Trust", "529"}},
        "patterns": {"zip_code": r"\d{5}"},
        "near_dup_keys": ["first_name", "age", "city", "zip_code", "initial_aum"],
    },
    "dim_date": {
        "pk": "date_id",
        "types": {"date_id": "integer", "date": "date", "year": "integer", "quarter": "integer",
                  "month": "integer", "week_of_year": "integer"},
        "ranges": {"year": (2020, 2024), "quarter": (1, 4), "month": (1, 12), "week_of_year": (1, 53)},
        "allowed": {c: {"0", "1"} for c in ["is_month_end", "is_quarter_end", "is_year_end", "is_trading_day"]},
        "unique_also": ["date"],
    },
    "dim_security": {
        "pk": "security_id",
        "types": {"security_id": "integer", "benchmark_id": "integer", "is_etf": "boolean",
                  "expense_ratio_bps": "decimal"},
        "ranges": {"expense_ratio_bps": (0, 300)},
        "allowed": {"asset_class": {"Equity", "Fixed Income", "Alternative", "Cash Equivalent"}},
        "unique_also": ["ticker"],
    },
    "dim_benchmark": {
        "pk": "benchmark_id",
        "types": {"benchmark_id": "integer"},
    },
    "fact_fees": {
        "pk": "fee_id",
        "types": {"fee_id": "integer", "client_id": "integer", "advisor_id": "integer",
                  "fee_date": "date", "aum_basis": "decimal", "bps_charged": "decimal", "amount": "decimal"},
        "ranges": {"aum_basis": (0.01, None), "bps_charged": (0, 100), "amount": (0, None)},
        "allowed": {"fee_type": {"Management", "Advisory", "Custodial", "Performance"}},
        "grain": ["client_id", "fee_date"],
    },
    "fact_portfolio_snapshot": {
        "pk": "snapshot_id",
        "types": {"snapshot_id": "integer", "client_id": "integer", "advisor_id": "integer",
                  "benchmark_id": "integer", "snapshot_date": "date", "year": "integer", "month": "integer",
                  "aum": "decimal", "return_ytd": "decimal", "benchmark_return_ytd": "decimal",
                  "active_alpha_ytd": "decimal", "cash_pct": "decimal"},
        # return_ytd is a fraction (0.05 = 5%); a YTD return above +100% is not plausible for this book
        "ranges": {"aum": (1000.01, None), "return_ytd": (-1, 1), "benchmark_return_ytd": (-1, 1),
                   "active_alpha_ytd": (-1, 1), "cash_pct": (0, 1), "month": (1, 12)},
        "allowed": {"account_type": {"Taxable", "IRA", "Roth IRA", "Trust", "529"}},
        "grain": ["client_id", "snapshot_date"],
    },
    "fact_transactions": {
        "pk": "txn_id",
        "types": {"txn_id": "integer", "client_id": "integer", "advisor_id": "integer",
                  "security_id": "integer", "txn_date": "date", "shares": "decimal",
                  "price": "decimal", "amount": "decimal"},
        "ranges": {"shares": (0, None), "price": (0.01, None), "amount": (0.01, None)},
        "allowed": {"txn_type": {"Buy", "Sell", "Dividend", "Deposit", "Withdrawal", "Advisory Fee"}},
    },
}

# (fact/child table, FK column, parent table, PK column)  - 10 ID-based + 3 date joins
FOREIGN_KEYS = [
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

# ---------------------------------------------------------------------------
# GROUP 1 - column level (type, allowed values, ranges, key uniqueness)
# ---------------------------------------------------------------------------
def column_checks(name, df, spec):
    n = len(df)
    for col in [spec["pk"]] + spec.get("unique_also", []):
        d = df[col].duplicated(keep=False)
        add_finding(name, "1 Column", "key uniqueness", col, "ERROR", d, n, examples(df, d, [col]))
    for col, typ in spec.get("types", {}).items():
        f = parse_fails(df[col], typ)
        add_finding(name, "1 Column", f"type = {typ}", col, "ERROR", f, n,
                    "; ".join(df.loc[f, col].unique()[:5]))
    for col, allowed in spec.get("allowed", {}).items():
        v = df[col].str.strip()
        bad = (v != "") & ~v.isin(allowed)
        add_finding(name, "1 Column", "allowed values", col, "ERROR", bad, n,
                    "; ".join(v[bad].value_counts().head(5).index))
    for col, (lo, hi) in spec.get("ranges", {}).items():
        x = num(df[col])
        bad = pd.Series(False, index=df.index)
        if lo is not None:
            bad |= x < lo
        if hi is not None:
            bad |= x > hi
        add_finding(name, "1 Column", f"range [{lo}, {hi}]", col, "WARN", bad, n,
                    "; ".join(df.loc[bad, col].value_counts().head(5).index))
    for col, pat in spec.get("patterns", {}).items():
        bad = ~df[col].str.fullmatch(pat)
        add_finding(name, "1 Column", f"pattern {pat}", col, "ERROR", bad, n, examples(df, bad, [col]))
    # Completeness - every column with blanks is reported (INFO: may be legitimate structure)
    for col in df.columns:
        b = df[col].str.strip() == ""
        if b.any():
            add_finding(name, "1 Column", "blank values", col, "INFO", b, n,
                        note="Check whether blanks are a defect or legitimate structure")
    # Literal text that a default parser would turn into NaN
    for col in df.columns:
        lit = df[col].str.strip().isin(["None", "NULL", "null", "NaN", "nan", "N/A", "NA"])
        if lit.any():
            add_finding(name, "1 Column", "null-like text literal", col, "INFO", lit, n,
                        "; ".join(df.loc[lit, col].unique()[:3]),
                        "Default read_csv would convert this to NaN")
    # Whitespace
    for col in df.columns:
        ws = df[col] != df[col].str.strip()
        if ws.any():
            add_finding(name, "1 Column", "leading/trailing whitespace", col, "WARN", ws, n)


# ---------------------------------------------------------------------------
# GROUP 2 - single-table rules (duplicates, near-duplicates, row contradictions)
# ---------------------------------------------------------------------------
def single_table_checks(name, df, spec):
    n = len(df)
    non_key = [c for c in df.columns if c != spec["pk"]]
    d = df.duplicated(non_key, keep=False)
    add_finding(name, "2 Single-table", "exact duplicate rows (ignoring PK)", "all", "ERROR", d, n,
                examples(df, d, [spec["pk"]]))
    if "grain" in spec:
        g = df.duplicated(spec["grain"], keep=False)
        add_finding(name, "2 Single-table", f"duplicate grain {spec['grain']}", ",".join(spec["grain"]),
                    "ERROR", g, n, examples(df, g, [spec["pk"]] + spec["grain"]))
    if "near_dup_keys" in spec:
        keys = spec["near_dup_keys"]
        nd = df.duplicated(keys, keep=False)
        add_finding(name, "2 Single-table", f"near-duplicates on {keys}", ",".join(keys), "ERROR", nd, n,
                    examples(df, nd, [spec["pk"], "first_name", "last_name", "initial_aum"], 4),
                    "Same person under two IDs")



def market_holidays(dates):
    """Fixed-date US market holidays (New Year, July 4, Christmas), shifted to the
    observed weekday. NYSE does not close the Friday before a Saturday New Year."""
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

def row_rules(T):
    """Values that contradict other columns of the same row."""
    # dim_date: derived calendar columns must match the date itself
    d = T["dim_date"]; dt = pd.to_datetime(d["date"], errors="coerce"); n = len(d)
    rules = {
        "year": dt.dt.year.astype("Int64").astype(str) != d["year"],
        "month": dt.dt.month.astype("Int64").astype(str) != d["month"],
        "quarter": dt.dt.quarter.astype("Int64").astype(str) != d["quarter"],
        "month_name": dt.dt.month_name() != d["month_name"],
        "day_of_week": dt.dt.day_name() != d["day_of_week"],
        "is_month_end": dt.dt.is_month_end.astype(int).astype(str) != d["is_month_end"],
        "is_trading_day": ((dt.dt.dayofweek < 5).astype(int).astype(str) != d["is_trading_day"]),
    }
    for col, bad in rules.items():
        add_finding("dim_date", "2 Single-table", "derived column matches date", col, "ERROR", bad, n)
    gaps = (dt.diff().dt.days.dropna() != 1)
    add_finding("dim_date", "2 Single-table", "calendar has no gaps", "date", "ERROR", int(gaps.sum()), n)
    on_hol = dt.isin(market_holidays(dt)) & (d["is_trading_day"] == "1")
    add_finding("dim_date", "2 Single-table", "market holiday marked as trading day", "is_trading_day",
                "WARN", on_hol, n, "; ".join(d.loc[on_hol, "date"].head(5)),
                "Checks New Year, July 4, Christmas (observed)")    

    # dim_security: ETFs have expense ratio & no sector; stocks the opposite
    s = T["dim_security"]; n = len(s)
    etf = s["is_etf"] == "True"
    add_finding("dim_security", "2 Single-table", "ETF has no sector / stock has sector", "sector", "WARN",
                (etf & (s["sector"] != "")) | (~etf & (s["sector"] == "")), n)
    add_finding("dim_security", "2 Single-table", "ETF has expense ratio / stock has none",
                "expense_ratio_bps", "WARN",
                (etf & (s["expense_ratio_bps"] == "")) | (~etf & (s["expense_ratio_bps"] != "")), n)
    dn = s["name"].duplicated(keep=False)
    add_finding("dim_security", "2 Single-table", "same name, different ticker", "name", "INFO", dn, n,
                examples(s, dn, ["security_id", "ticker", "name"]),
                "Different tickers/asset classes - likely different funds")

    # dim_client: tier must agree with initial AUM band
    c = T["dim_client"]; n = len(c); ia = num(c["initial_aum"])
    band = np.select([ia < 500_000, ia < 5_000_000], ["Retail", "HNW"], "UHNW")
    bad = band != c["client_tier"]
    add_finding("dim_client", "2 Single-table", "client_tier matches initial_aum band (<500K / <5M / 5M+)",
                "client_tier", "WARN", pd.Series(bad, index=c.index), n)

    # fact_fees: amount = aum_basis x bps / 10,000 / 12
    f = T["fact_fees"]; n = len(f)
    calc = num(f["aum_basis"]) * num(f["bps_charged"]) / 10_000 / 12
    bad = (calc - num(f["amount"])).abs() > 0.02
    add_finding("fact_fees", "2 Single-table", "amount = aum_basis x bps / 10000 / 12", "amount", "ERROR",
                bad, n, examples(f, bad, ["fee_id", "aum_basis", "bps_charged", "amount"]))

    # fact_portfolio_snapshot
    p = T["fact_portfolio_snapshot"]; n = len(p)
    pct = p["return_ytd"].str.contains("%")
    add_finding("fact_portfolio_snapshot", "2 Single-table", "return stored as '%' string", "return_ytd",
                "ERROR", pct, n, examples(p, pct, ["snapshot_id", "return_ytd"]))
    r = num(p["return_ytd"]).fillna(num(p["return_ytd"].str.rstrip("%")) / 100)
    alpha_bad = (r - num(p["benchmark_return_ytd"]) - num(p["active_alpha_ytd"])).abs() > 1e-4
    add_finding("fact_portfolio_snapshot", "2 Single-table",
                "active_alpha = return - benchmark_return (after % -> fraction)", "active_alpha_ytd",
                "ERROR", alpha_bad, n)
    ym_bad = (p["year"] != p["snapshot_date"].str[:4]) | (p["month"].str.zfill(2) != p["snapshot_date"].str[5:7])
    add_finding("fact_portfolio_snapshot", "2 Single-table", "year/month match snapshot_date", "year,month",
                "ERROR", ym_bad, n)
    floor = num(p["aum"]) == 1000
    add_finding("fact_portfolio_snapshot", "2 Single-table", "aum exactly 1000.00 (suspected floor/placeholder)",
                "aum", "WARN", floor, n, examples(p, floor, ["client_id", "snapshot_date", "aum"]),
                f"{p.loc[floor, 'client_id'].nunique()} clients")

    # fact_transactions
    t = T["fact_transactions"]; n = len(t)
    traded = t["txn_type"].isin(["Buy", "Sell", "Dividend"])
    cash = ~traded
    add_finding("fact_transactions", "2 Single-table", "Buy/Sell/Dividend missing security, shares or price",
                "security_id,shares,price", "ERROR",
                traded & ((t["security_id"] == "") | (t["shares"] == "") | (t["price"] == "")), n)
    add_finding("fact_transactions", "2 Single-table", "cash rows (Deposit/Withdrawal/Fee) have blank security",
                "security_id", "INFO", cash & (t["security_id"] == ""), n,
                note="Legitimate structure: cash movements have no security")
    neg = num(t["shares"]) < 0
    add_finding("fact_transactions", "2 Single-table", "negative shares", "shares", "ERROR", neg, n,
                examples(t, neg, ["txn_id", "txn_type", "shares", "price", "amount"]),
                "By txn_type: " + str(t.loc[neg, "txn_type"].value_counts().to_dict()))
    amt_bad = traded & ((num(t["shares"]).abs() * num(t["price"]) - num(t["amount"])).abs()
                        > 0.01 * num(t["amount"]).clip(lower=1))
    add_finding("fact_transactions", "2 Single-table", "amount = |shares| x price (within 1%)", "amount",
                "ERROR", amt_bad, n)
    div = t["txn_type"] == "Dividend"
    add_finding("fact_transactions", "2 Single-table",
                "Dividend amount equals full position value (shares x price)", "amount", "WARN",
                div & ~amt_bad, n, note="A dividend is normally a small % of position value")


# ---------------------------------------------------------------------------
# GROUP 3 - referential integrity
# ---------------------------------------------------------------------------
def ri_checks(T):
    for child, fk, parent, pk in FOREIGN_KEYS:
        c = T[child][fk]
        nonblank = c.str.strip() != ""
        orphans = nonblank & ~c.isin(set(T[parent][pk]))
        add_finding(child, "3 Referential", f"{fk} -> {parent}.{pk}", fk, "ERROR", orphans, int(nonblank.sum()),
                    "; ".join(c[orphans].unique()[:5]),
                    f"{c[orphans].nunique()} distinct orphan keys; {(~nonblank).sum()} blank keys")
        # Same test after stripping a trailing '.0' - tells us if the orphans are only a format problem
        if orphans.any() and c.str.endswith(".0").any():
            norm = c.str.replace(r"\.0$", "", regex=True)
            still = nonblank & ~norm.isin(set(T[parent][pk]))
            add_finding(child, "3 Referential", f"{fk} -> {parent}.{pk} after removing '.0'", fk,
                        "ERROR", still, int(nonblank.sum()), "; ".join(c[still].unique()[:5]),
                        f"{c[still].nunique()} distinct orphan keys remain after format fix")


# ---------------------------------------------------------------------------
# GROUP 4 - cross-table business rules
# ---------------------------------------------------------------------------
def cross_table_checks(T):
    c = T["dim_client"]; p = T["fact_portfolio_snapshot"]; f = T["fact_fees"]; t = T["fact_transactions"]
    d = T["dim_date"]

    # Advisor on each fact row must be the client's advisor
    cl_adv = c.set_index("client_id")["advisor_id"]
    for name in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
        df = T[name]
        exp = df["client_id"].map(cl_adv)
        bad = exp.notna() & (exp != df["advisor_id"])
        add_finding(name, "4 Cross-table", "advisor_id = client's advisor in dim_client", "advisor_id",
                    "ERROR", bad, len(df))

    # Snapshot account type = client's primary account type
    exp = p["client_id"].map(c.set_index("client_id")["primary_account_type"])
    add_finding("fact_portfolio_snapshot", "4 Cross-table", "account_type = dim_client.primary_account_type",
                "account_type", "WARN", exp.notna() & (exp != p["account_type"]), len(p))

    # Fee AUM basis = snapshot AUM for the same client-month
    m = f.merge(p[["client_id", "snapshot_date", "aum"]], left_on=["client_id", "fee_date"],
                right_on=["client_id", "snapshot_date"], how="left")
    add_finding("fact_fees", "4 Cross-table", "fee has matching snapshot (client, month)", "fee_date", "ERROR",
                m["aum"].isna(), len(f))
    add_finding("fact_fees", "4 Cross-table", "aum_basis = snapshot aum", "aum_basis", "ERROR",
                m["aum"].notna() & ((num(m["aum_basis"]) - num(m["aum"])).abs() > 0.01), len(f))
    add_finding("fact_fees", "4 Cross-table", "fee charged on 1000.00 placeholder AUM", "aum_basis", "WARN",
                num(f["aum_basis"]) == 1000, len(f))

    # Snapshot benchmark should be consistent with risk profile
    first = p.drop_duplicates("client_id")[["client_id", "benchmark_id"]]
    rb = first.merge(c[["client_id", "risk_profile"]], on="client_id")
    xt = pd.crosstab(rb["risk_profile"].replace("", "(blank)"), rb["benchmark_id"])
    add_finding("dim_client", "4 Cross-table", "risk_profile -> benchmark mapping (see note)", "risk_profile",
                "INFO", 0, len(c), note=xt.to_dict().__str__()[:200])
    blank_rp = (c["risk_profile"] == "")
    rec = c.loc[blank_rp, "client_id"].map(first.set_index("client_id")["benchmark_id"])
    add_finding("dim_client", "4 Cross-table", "blank risk_profile with a snapshot benchmark (recoverable?)",
                "risk_profile", "WARN", int(rec.notna().sum()), len(c),
                note=f"benchmark of those clients: {rec.value_counts().to_dict()}")

    # Transactions must not happen before the client relationship began
    since = t["client_id"].map(c.set_index("client_id")["client_since"])
    add_finding("fact_transactions", "4 Cross-table", "txn_date >= client_since", "txn_date", "ERROR",
                since.notna() & (t["txn_date"] < since), len(t))

    # Inactive clients: activity after their last snapshot month
    last = p.groupby("client_id")["snapshot_date"].max().str[:7]
    lm = t["client_id"].map(last)
    after = lm.notna() & (t["txn_date"].str[:7] > lm)
    add_finding("fact_transactions", "4 Cross-table", "txn after client's last snapshot month (account closed?)",
                "txn_date", "WARN", after, len(t),
                note=f"{t.loc[after, 'client_id'].nunique()} clients; is_active of these: "
                     f"{t.loc[after, 'client_id'].map(c.set_index('client_id')['is_active']).value_counts().to_dict()}")

    # Active clients should have a snapshot in the last month
    last_month = p["snapshot_date"].max()
    has_last = c["client_id"].isin(p.loc[p["snapshot_date"] == last_month, "client_id"])
    add_finding("dim_client", "4 Cross-table", f"is_active=True but no snapshot on {last_month}", "is_active",
                "WARN", (c["is_active"] == "True") & ~has_last, len(c))
    add_finding("dim_client", "4 Cross-table", "client has no fact rows at all", "client_id", "WARN",
                ~c["client_id"].isin(set(p["client_id"]) | set(f["client_id"]) | set(t["client_id"])), len(c))

    # Trades on non-trading days
    trading = t["txn_date"].map(d.set_index("date")["is_trading_day"])
    trade = t["txn_type"].isin(["Buy", "Sell"])
    add_finding("fact_transactions", "4 Cross-table", "Buy/Sell on a non-trading day (dim_date)", "txn_date",
                "WARN", trade & (trading == "0"), len(t))
    hol = pd.to_datetime(t["txn_date"], format="%Y-%m-%d", errors="coerce").isin(
        market_holidays(pd.to_datetime(d["date"], format="%Y-%m-%d", errors="coerce")))
    add_finding("fact_transactions", "4 Cross-table", "Buy/Sell on a market holiday (missed by dim_date)",
                "txn_date", "WARN", trade & hol, len(t))
    # Advisory Fee debits in transactions vs. fee charges in fact_fees (same client-month)
    af = t[t["txn_type"] == "Advisory Fee"].assign(ym=lambda x: x["txn_date"].str[:7], a=lambda x: num(x["amount"]))
    ff = f.assign(ym=f["fee_date"].str[:7], a=num(f["amount"]))
    j = pd.concat([af.groupby(["client_id", "ym"])["a"].sum(), ff.groupby(["client_id", "ym"])["a"].sum()],
                  axis=1, keys=["txn", "fee"]).dropna()
    add_finding("fact_transactions", "4 Cross-table",
                "Advisory Fee debits = fact_fees amount (client-month)", "amount", "WARN",
                int(((j["txn"] - j["fee"]).abs() > 0.02).sum()), len(j),
                note=f"{len(j)} client-months present in both tables")

def main():
    T = {name: load_raw(name) for name in TABLES}
    for name, df in T.items():
        print(f"Loaded {name:<26} {len(df):>8,} rows x {df.shape[1]} cols")

    profile = pd.concat([profile_table(n, df) for n, df in T.items()], ignore_index=True)
    profile.to_csv(REPORT_DIR / "profile_raw.csv", index=False)
    print(f"\nSaved profile_raw.csv ({len(profile)} rows = one per column)")

    # ---- The four check groups ----
    for name, df in T.items():
        column_checks(name, df, TABLE_SPECS[name])          # Group 1
        single_table_checks(name, df, TABLE_SPECS[name])    # Group 2
    row_rules(T)                                            # Group 2 (row contradictions)
    ri_checks(T)                                            # Group 3
    cross_table_checks(T)                                   # Group 4

    dq = pd.DataFrame(FINDINGS)
    order = {"ERROR": 0, "WARN": 1, "INFO": 2, "PASS": 3}
    dq = dq.sort_values(["severity", "table"], key=lambda s: s.map(order) if s.name == "severity" else s)
    dq.to_csv(REPORT_DIR / "dq_summary_raw.csv", index=False)
    print(f"Saved dq_summary_raw.csv ({len(dq)} checks)")
    print("\nFindings by severity:", dq["severity"].value_counts().to_dict())
    print("\n=== ERROR and WARN findings ===")
    show = dq[dq["severity"].isin(["ERROR", "WARN"])]
    with pd.option_context("display.width", 250, "display.max_colwidth", 70, "display.max_rows", 200):
        print(show[["severity", "table", "column", "check", "rows_affected"]].to_string(index=False))


if __name__ == "__main__":
    main()    