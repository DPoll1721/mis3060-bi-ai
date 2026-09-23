# =============================================================================
# Script:      hw02/hw02_eda.py
# Purpose:     Exploratory Data Analysis (EDA) of Wildcat Capital transactions
# Dataset:     data/raw/fact_transactions.csv
# Author:      Drew Pollock
# Course:      MIS3060 Business Intelligence with AI
# Generated:   2026-09-23
#
# Usage (from the repository root):
#     python hw02/hw02_eda.py
#
# Outputs:
#     hw02/charts/hist_amount.png
#     hw02/charts/box_amount_by_type.png
#     hw02/charts/scatter_shares_amount.png
#     hw02/hw02_profile.txt   (plain-text summary of items 2-13)
# =============================================================================

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Save charts to files only; no pop-up windows
import matplotlib.pyplot as plt
import pandas as pd

# -----------------------------------------------------------------------------
# Paths (resolved from this script's location so they work from the repo root)
# -----------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "data" / "raw" / "fact_transactions.csv"
HW_DIR = REPO_ROOT / "hw02"
CHART_DIR = HW_DIR / "charts"
PROFILE_PATH = HW_DIR / "hw02_profile.txt"

EXPECTED_SHAPE = (298772, 9)

CHART_DIR.mkdir(parents=True, exist_ok=True)

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 50)

# -----------------------------------------------------------------------------
# Output helper: prints to console AND records lines for the profile file
# -----------------------------------------------------------------------------
profile_lines = []


def out(text=""):
    """Print text and keep a copy for the plain-text profile."""
    text = str(text)
    print(text)
    profile_lines.append(text)


def section(title):
    """Print a clearly labeled section header."""
    out()
    out("=" * 70)
    out(title)
    out("=" * 70)


# -----------------------------------------------------------------------------
# 1. Load the data
# -----------------------------------------------------------------------------
df = pd.read_csv(DATA_PATH)
print(f"Loaded: {DATA_PATH}")

out("WILDCAT CAPITAL TRANSACTIONS - EDA PROFILE")
out(f"Source file: data/raw/fact_transactions.csv")
out(f"Author: Drew Pollock")

# -----------------------------------------------------------------------------
# 2. Rows and columns
# -----------------------------------------------------------------------------
section("2. DATASET SHAPE")
n_rows, n_cols = df.shape
out(f"Number of rows:    {n_rows:,}")
out(f"Number of columns: {n_cols}")

# -----------------------------------------------------------------------------
# 3. Column names and data types
# -----------------------------------------------------------------------------
section("3. COLUMN NAMES AND DATA TYPES")
dtype_table = pd.DataFrame({"column": df.columns, "dtype": df.dtypes.astype(str).values})
out(dtype_table.to_string(index=False))

# -----------------------------------------------------------------------------
# 4. Missing values per column
# -----------------------------------------------------------------------------
section("4. MISSING VALUES PER COLUMN")
missing = df.isna().sum()
out(missing.to_string())
out(f"Total missing values (all columns): {int(missing.sum()):,}")

# -----------------------------------------------------------------------------
# 5. Descriptive statistics for numeric columns
# -----------------------------------------------------------------------------
section("5. DESCRIPTIVE STATISTICS (NUMERIC COLUMNS)")
desc = df.describe().rename(
    index={"25%": "25th pct", "50%": "median", "75%": "75th pct"}
)
out(desc.round(2).to_string())

# -----------------------------------------------------------------------------
# 6. Value counts and percentages for txn_type
# -----------------------------------------------------------------------------
section("6. TXN_TYPE VALUE COUNTS AND PERCENTAGES")
type_counts = df["txn_type"].value_counts(dropna=False)
type_pct = (type_counts / len(df) * 100).round(2)
type_table = pd.DataFrame({"count": type_counts, "percent": type_pct})
out(type_table.to_string())

# -----------------------------------------------------------------------------
# 7. Unique clients, advisors, securities
# -----------------------------------------------------------------------------
section("7. UNIQUE ENTITY COUNTS")
out(f"Unique clients:    {df['client_id'].nunique():,}")
out(f"Unique advisors:   {df['advisor_id'].nunique():,}")
out(f"Unique securities: {df['security_id'].nunique():,}")

# -----------------------------------------------------------------------------
# 8. Date range
# -----------------------------------------------------------------------------
section("8. TRANSACTION DATE RANGE")
txn_dates = pd.to_datetime(df["txn_date"], errors="coerce")
earliest, latest = txn_dates.min(), txn_dates.max()
out(f"Earliest txn_date: {earliest.date()}")
out(f"Latest txn_date:   {latest.date()}")
out(f"Date range span:   {(latest - earliest).days:,} days")
unparsed = int(txn_dates.isna().sum() - df["txn_date"].isna().sum())
if unparsed > 0:
    out(f"Note: {unparsed:,} txn_date values could not be parsed as dates.")

# -----------------------------------------------------------------------------
# 9. Duplicate txn_id check
# -----------------------------------------------------------------------------
section("9. DUPLICATE TXN_ID CHECK")
id_counts = df["txn_id"].value_counts()
dup_ids = int((id_counts > 1).sum())
out(f"Number of duplicate txn_id values: {dup_ids} (expected: 0)")
if dup_ids > 0:
    out(f"Rows involved in duplicates: {int(id_counts[id_counts > 1].sum()):,}")

# -----------------------------------------------------------------------------
# 10. Mean, median, skewness of amount
# -----------------------------------------------------------------------------
section("10. AMOUNT: MEAN, MEDIAN, SKEWNESS")
amt_mean = df["amount"].mean()
amt_median = df["amount"].median()
amt_skew = df["amount"].skew()
out(f"Mean amount:     {amt_mean:,.2f}")
out(f"Median amount:   {amt_median:,.2f}")
out(f"Skewness amount: {amt_skew:.4f}")

# -----------------------------------------------------------------------------
# 11. Amount by txn_type (count, mean, median), sorted by mean desc
# -----------------------------------------------------------------------------
section("11. AMOUNT BY TXN_TYPE (SORTED BY MEAN, DESCENDING)")
by_type = (
    df.groupby("txn_type")["amount"]
    .agg(count="count", mean="mean", median="median")
    .round(2)
    .sort_values("mean", ascending=False)
)
out(by_type.to_string())

# -----------------------------------------------------------------------------
# 12. Correlation matrix for shares, price, amount + top 3 correlations
# -----------------------------------------------------------------------------
section("12. CORRELATION MATRIX (SHARES, PRICE, AMOUNT)")
corr_cols = ["shares", "price", "amount"]
corr = df[corr_cols].corr().round(2)
out(corr.to_string())

pairs = []
for i, a in enumerate(corr_cols):
    for b in corr_cols[i + 1:]:
        pairs.append((a, b, corr.loc[a, b]))
pairs.sort(key=lambda p: abs(p[2]), reverse=True)

out()
out("Three strongest correlations (by absolute value, excluding self-correlation):")
for rank, (a, b, r) in enumerate(pairs[:3], start=1):
    out(f"  {rank}. {a} vs {b}: r = {r:.2f}")

# -----------------------------------------------------------------------------
# 13. Negative shares by txn_type
# -----------------------------------------------------------------------------
section("13. SHARES: MIN, MAX, AND NEGATIVE COUNT BY TXN_TYPE")
shares_by_type = df.groupby("txn_type")["shares"].agg(
    min="min",
    max="max",
    negative_count=lambda s: int((s < 0).sum()),
)
out(shares_by_type.to_string())
out(f"Total negative share values: {int((df['shares'] < 0).sum()):,}")

# -----------------------------------------------------------------------------
# 14. Shape check warning
# -----------------------------------------------------------------------------
print()
if df.shape != EXPECTED_SHAPE:
    print(f"WARNING: Expected shape {EXPECTED_SHAPE}, but got {df.shape}.")
else:
    print(f"Shape check passed: {df.shape} matches expected {EXPECTED_SHAPE}.")

# -----------------------------------------------------------------------------
# 15. Charts
# -----------------------------------------------------------------------------
# 15a. Histogram of amount with mean and median lines
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(df["amount"].dropna(), bins=100, color="steelblue", edgecolor="white")
ax.axvline(amt_mean, color="red", linestyle="--", linewidth=2,
           label=f"Mean = {amt_mean:,.2f}")
ax.axvline(amt_median, color="orange", linestyle="-", linewidth=2,
           label=f"Median = {amt_median:,.2f}")
ax.set_title("Distribution of Transaction Amount")
ax.set_xlabel("Amount")
ax.set_ylabel("Number of Transactions")
ax.legend()
fig.tight_layout()
fig.savefig(CHART_DIR / "hist_amount.png", dpi=150)
plt.close(fig)

# 15b. Horizontal box plot of amount by txn_type
types = sorted(df["txn_type"].dropna().unique())
box_data = [df.loc[df["txn_type"] == t, "amount"].dropna() for t in types]
fig, ax = plt.subplots(figsize=(10, 6))
ax.boxplot(box_data, vert=False)
ax.set_yticks(range(1, len(types) + 1))
ax.set_yticklabels(types)
ax.set_title("Transaction Amount by Transaction Type")
ax.set_xlabel("Amount")
ax.set_ylabel("Transaction Type")
fig.tight_layout()
fig.savefig(CHART_DIR / "box_amount_by_type.png", dpi=150)
plt.close(fig)

# 15c. Scatter of shares vs amount colored by txn_type
fig, ax = plt.subplots(figsize=(10, 6))
for t in types:
    subset = df[df["txn_type"] == t]
    ax.scatter(subset["shares"], subset["amount"], s=4, alpha=0.3, label=t)
ax.set_title("Shares vs. Amount by Transaction Type")
ax.set_xlabel("Shares")
ax.set_ylabel("Amount")
ax.legend(title="txn_type", markerscale=4)
fig.tight_layout()
fig.savefig(CHART_DIR / "scatter_shares_amount.png", dpi=150)
plt.close(fig)

print(f"Charts saved to: {CHART_DIR}")

# -----------------------------------------------------------------------------
# 16. Save plain-text profile (items 2-13)
# -----------------------------------------------------------------------------
PROFILE_PATH.write_text("\n".join(profile_lines) + "\n", encoding="utf-8")
print(f"Profile saved to: {PROFILE_PATH}")