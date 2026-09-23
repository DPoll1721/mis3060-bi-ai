import pandas as pd

df = pd.read_csv("data/raw/fact_transactions.csv")

total_rows = len(df)
non_buy_types = ["Sell", "Deposit", "Withdrawal", "Dividend", "Advisory Fee"]
non_buy_count = df["txn_type"].isin(non_buy_types).sum()
remaining = total_rows - non_buy_count

print(f"Total rows:              {total_rows:,}")
print(f"Non-Buy rows (5 types):  {non_buy_count:,}")
print(f"Remaining (implied Buy): {remaining:,}")