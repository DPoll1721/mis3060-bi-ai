"""
HW3 - Corporate Events Timeline
MIS3060 Business Intelligence with AI

Joins each executive event (8-K Item 5.02) to the nearest earnings release
(8-K Item 2.02) for the same company, measures the gap in days, and labels
whether the event came before, after, or in the same week as earnings.

Inputs:  hw03/earnings_history.csv, hw03/executive_events.csv
Output:  hw03/corporate_events_timeline.csv
"""

from pathlib import Path

import pandas as pd

# Paths are relative to this script, so it runs from the repo root or hw03/
HW_DIR = Path(__file__).resolve().parent
EARNINGS_CSV = HW_DIR / "earnings_history.csv"
EVENTS_CSV = HW_DIR / "executive_events.csv"
OUTPUT_CSV = HW_DIR / "corporate_events_timeline.csv"

SAME_WEEK_DAYS = 7


def categorize(days):
    """days = event date minus earnings date (negative means the event came first)."""
    if abs(days) <= SAME_WEEK_DAYS:
        return "same week"
    return "before earnings" if days < 0 else "after earnings"


def main():
    # Read everything as text so CIK leading zeros and "NOT_FOUND" values survive
    earnings = pd.read_csv(EARNINGS_CSV, dtype=str)
    events = pd.read_csv(EVENTS_CSV, dtype=str)

    # Both tables have a filing_date column, so give each a clear name
    earnings = earnings.rename(columns={"filing_date": "earnings_filing_date"})
    events = events.rename(columns={"filing_date": "event_filing_date"})
    earnings["earnings_filing_date"] = pd.to_datetime(earnings["earnings_filing_date"])
    events["event_filing_date"] = pd.to_datetime(events["event_filing_date"])

    # Keep the original event order so we can pick one earnings row per event
    events["event_id"] = range(len(events))

    # Pair every event with every earnings filing for the same company (matched on CIK)
    pairs = events.merge(
        earnings.drop(columns=["company", "ticker"]), on="cik", how="left"
    )
    pairs["days_to_nearest_earnings"] = (
        pairs["event_filing_date"] - pairs["earnings_filing_date"]
    ).dt.days
    pairs["abs_days"] = pairs["days_to_nearest_earnings"].abs()

    # Keep the closest earnings filing for each event (ties go to the earlier filing)
    timeline = (
        pairs.sort_values(["event_id", "abs_days", "earnings_filing_date"])
        .drop_duplicates(subset="event_id", keep="first")
        .sort_values("event_id")
        .reset_index(drop=True)
    )

    timeline["days_to_nearest_earnings"] = timeline["days_to_nearest_earnings"].astype(int)
    timeline["event_timing"] = timeline["days_to_nearest_earnings"].apply(categorize)

    # Direction ignoring the 7-day window, used in the summary for "same week" events
    timeline["direction"] = timeline["days_to_nearest_earnings"].apply(
        lambda d: "before" if d < 0 else ("after" if d > 0 else "same day")
    )

    # All columns from both tables, plus the two new ones
    output_cols = [
        "company", "ticker", "cik",
        "event_filing_date", "event_type", "person_name", "title", "effective_date",
        "earnings_filing_date", "period", "revenue_reported", "eps_diluted", "net_income",
        "days_to_nearest_earnings", "event_timing",
    ]
    out = timeline[output_cols].copy()
    out["event_filing_date"] = out["event_filing_date"].dt.strftime("%Y-%m-%d")
    out["earnings_filing_date"] = out["earnings_filing_date"].dt.strftime("%Y-%m-%d")
    out.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {len(out)} rows to {OUTPUT_CSV}\n")

    # ---- Summary by company ----
    print("=" * 78)
    print("EXECUTIVE EVENTS RELATIVE TO NEAREST EARNINGS ANNOUNCEMENT")
    print("=" * 78)
    for (company, ticker), group in timeline.groupby(["company", "ticker"], sort=False):
        print(f"\n{company} ({ticker})")
        for _, row in group.iterrows():
            days = row["days_to_nearest_earnings"]
            earn_date = row["earnings_filing_date"].strftime("%Y-%m-%d")
            if days == 0:
                relation = f"same day as earnings on {earn_date}"
            else:
                relation = f"{abs(days)} days {row['direction']} earnings on {earn_date}"
            print(
                f"  {row['event_filing_date']:%Y-%m-%d} | {row['event_type']:<11} | "
                f"{row['person_name']:<22} | {relation} [{row['event_timing']}]"
            )

    # Companies in the earnings table with no executive events
    for _, row in earnings[~earnings["cik"].isin(events["cik"])][
        ["company", "ticker"]
    ].drop_duplicates().iterrows():
        print(f"\n{row['company']} ({row['ticker']})\n  No executive events")

    # ---- Final counts ----
    counts = timeline["event_timing"].value_counts()
    same_week = timeline[timeline["event_timing"] == "same week"]
    print("\n" + "=" * 78)
    print("FINAL COUNT (all five companies)")
    print("=" * 78)
    print(f"  Before earnings: {counts.get('before earnings', 0)}")
    print(f"  After earnings:  {counts.get('after earnings', 0)}")
    print(f"  Same week:       {counts.get('same week', 0)}", end="")
    if len(same_week):
        split = same_week["direction"].value_counts()
        parts = [f"{n} {d}" for d, n in split.items()]
        print(f"  ({', '.join(parts)})")
    else:
        print()
    print(f"  Total events:    {len(timeline)}")

    # Before vs. after ignoring the 7-day window (every event falls on one side)
    direction = timeline["direction"].value_counts()
    print(
        f"\n  Ignoring the same-week window: {direction.get('before', 0)} before, "
        f"{direction.get('after', 0)} after, {direction.get('same day', 0)} same day"
    )


if __name__ == "__main__":
    main()
