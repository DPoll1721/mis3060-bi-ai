"""
HW6 Part C - pandas evidence for design questions (a)-(d).
Reads the Wildcat Capital Clean CSVs in hw05/data. Prints results only.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "hw05" / "data"
pd.set_option("display.width", 160)
pd.set_option("display.float_format", "{:,.4f}".format)


def load(name, date_cols=()):
    df = pd.read_csv(DATA / f"{name}.csv")
    df.columns = df.columns.str.strip().str.lower()
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], format="%Y-%m-%d")
    return df


tier = load("dim_client")[["client_id", "client_tier"]]
snap = load("fact_portfolio_snapshot", ["snapshot_date"]).merge(tier, on="client_id", how="left", validate="many_to_one")
fees = load("fact_fees", ["fee_date"]).merge(tier, on="client_id", how="left", validate="many_to_one")
txns = load("fact_transactions", ["txn_date"]).merge(tier, on="client_id", how="left", validate="many_to_one")


def money(x):
    return f"${x:,.2f}"


# ------------------------------------------------------------------ (a)
print("=" * 70, "\n(a) Ending AUM vs SUMX over clients (no filters)\n" + "=" * 70)
last_date = snap["snapshot_date"].max()
ending = snap.loc[snap["snapshot_date"] == last_date, "aum"].sum()
client_last = snap.sort_values("snapshot_date").groupby("client_id").tail(1)
sumx = client_last["aum"].sum()
departed = client_last[client_last["snapshot_date"] < last_date]
print("Last snapshot date:              ", last_date.date())
print("Ending AUM:                      ", money(ending))
print("SUMX (each client's own last):   ", money(sumx))
print("Difference:                      ", money(sumx - ending))
print("Clients absent from last snapshot:", len(departed))
print("Their last balances (sum):       ", money(departed["aum"].sum()))
print("Their last snapshot dates range: ", departed["snapshot_date"].min().date(), "to",
      departed["snapshot_date"].max().date())
print("Departed clients by tier:\n", departed.groupby("client_tier")["aum"].agg(["count", "sum"]))

# ------------------------------------------------------------------ (b)
print("\n" + "=" * 70, "\n(b) 2024 Fee Yield vs Effective Fee Rate\n" + "=" * 70)
s24 = snap[snap["snapshot_date"].dt.year == 2024]
f24 = fees[fees["fee_date"].dt.year == 2024]
fee_total = f24["amount"].sum()
fee_yield = fee_total * 12 * 10000 / s24["aum"].sum()
eff_rate = fee_total * 12 * 10000 / f24["aum_basis"].sum()
print("Total fees 2024:                 ", money(fee_total))
print("Sum of snapshot aum 2024:        ", money(s24["aum"].sum()))
print("Sum of fee aum_basis 2024:       ", money(f24["aum_basis"].sum()))
print(f"Fee Yield (bps, snapshot denom): {fee_yield:.2f}")
print(f"Effective Fee Rate (bps, aum_basis denom): {eff_rate:.2f}")
print("Fee types:", f24["fee_type"].value_counts().to_dict())

fee_cm = (f24.groupby(["client_id", "fee_date"], as_index=False)[["amount", "aum_basis"]].sum()
             .rename(columns={"fee_date": "snapshot_date"}))
cov = s24.merge(fee_cm, on=["client_id", "snapshot_date"], how="left", indicator=True)
billed = cov[cov["_merge"] == "both"]
unbilled = cov[cov["_merge"] == "left_only"]
print("\nSnapshot client-months 2024:     ", len(cov))
print("  with a fee record:             ", len(billed))
print("  WITHOUT a fee record:          ", len(unbilled),
      f"({len(unbilled) / len(cov):.1%} of rows, {unbilled['aum'].sum() / cov['aum'].sum():.1%} of AUM)")
print("  distinct clients never billed in 2024:",
      len(set(s24["client_id"]) - set(f24["client_id"])))
print(f"Fee yield on billed rows only:    {billed['amount'].sum() * 12 * 10000 / billed['aum'].sum():.2f} bps")
print(f"aum_basis / snapshot aum on billed rows: {billed['aum_basis'].sum() / billed['aum'].sum():.4f}")
print("Unbilled rows by tier:\n", unbilled.groupby("client_tier")["aum"].agg(["count", "sum"]))
print("Unbilled rows by month:\n", unbilled.groupby(unbilled["snapshot_date"].dt.month)["aum"].agg(["count", "sum"]))
orphan_fees = f24.merge(s24[["client_id", "snapshot_date"]].rename(columns={"snapshot_date": "fee_date"}),
                        on=["client_id", "fee_date"], how="left", indicator=True)
print("Fee rows with no matching snapshot:", (orphan_fees["_merge"] == "left_only").sum())

# ------------------------------------------------------------------ (c)
print("\n" + "=" * 70, "\n(c) AUM-Weighted Alpha at the last 2024 snapshot\n" + "=" * 70)
last24 = s24[s24["snapshot_date"] == s24["snapshot_date"].max()]
clean = last24[last24["is_return_suspect"].ne(1)]
sus = last24[last24["is_return_suspect"].eq(1)]


def wavg(df):
    return (df["active_alpha_ytd"] * df["aum"]).sum() / df["aum"].sum()


print("Snapshot date:", last24["snapshot_date"].iloc[0].date(), "| rows:", len(last24),
      "| suspect rows:", len(sus), f"({sus['aum'].sum() / last24['aum'].sum():.1%} of AUM)")
print(f"Weighted alpha, suspects EXCLUDED (measure): {wavg(clean):.4%}")
print(f"Simple mean alpha, same rows:                {clean['active_alpha_ytd'].mean():.4%}")
print(f"Weighted alpha, suspects INCLUDED:           {wavg(last24):.4%}")
print(f"Simple mean alpha, suspects included:        {last24['active_alpha_ytd'].mean():.4%}")
print(f"Suspect rows: mean alpha {sus['active_alpha_ytd'].mean():.4%}, "
      f"min {sus['active_alpha_ytd'].min():.4%}, max {sus['active_alpha_ytd'].max():.4%}")
clean24 = s24[s24["is_return_suspect"].ne(1)]
print(f"WRONG: weighted alpha over ALL 2024 months:  {wavg(clean24):.4%}")
print("Alpha (YTD) by month, weighted, suspects excluded:")
print(clean24.groupby(clean24["snapshot_date"].dt.month).apply(wavg).map("{:.4%}".format).to_string())

# ------------------------------------------------------------------ (d)
print("\n" + "=" * 70, "\n(d) Organic Growth vs AUM YoY by tier, 2024\n" + "=" * 70)
s23 = snap[snap["snapshot_date"].dt.year == 2023]
end24 = s24[s24["snapshot_date"] == s24["snapshot_date"].max()].groupby("client_tier")["aum"].sum()
end23 = s23[s23["snapshot_date"] == s23["snapshot_date"].max()].groupby("client_tier")["aum"].sum()
t24 = txns[txns["txn_date"].dt.year == 2024]
dep = t24[t24["txn_type"] == "Deposit"].groupby("client_tier")["amount"].sum()
wd = t24[t24["txn_type"] == "Withdrawal"].groupby("client_tier")["amount"].sum()
cl24 = s24[s24["snapshot_date"] == s24["snapshot_date"].max()].groupby("client_tier")["client_id"].nunique()
cl23 = s23[s23["snapshot_date"] == s23["snapshot_date"].max()].groupby("client_tier")["client_id"].nunique()
d = pd.DataFrame({"end_2023": end23, "end_2024": end24, "deposits": dep, "withdrawals": wd,
                  "clients_2023": cl23, "clients_2024": cl24})
d["net_flows"] = d["deposits"] - d["withdrawals"]
d["yoy_%"] = (d["end_2024"] / d["end_2023"] - 1) * 100
d["organic_%"] = d["net_flows"] / d["end_2023"] * 100
d["non_flow_%"] = d["yoy_%"] - d["organic_%"]
d["share_of_firm_net_flows_%"] = d["net_flows"] / d["net_flows"].sum() * 100
print(d.to_string())