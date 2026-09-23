# HW2 Validation — Wildcat Capital Transaction EDA

**Author:** Drew Pollock

## Run notes (1C)
Overall, this seemed to run quite smoothly, with no real errors. It printed matplotlibDeprecationWarning, but not an error.

## 2A — Known-Answer Benchmarks

| Check | Expected | Your Script Produced | Match? | Notes |
|---|---|---|---|---|
| Dataset shape | (298772, 9) | (298772, 9) | Yes | |
| Null count — `security_id` | 101,597 | 101,597 | Yes | |
| Null count — `amount` | 0 | 0 | Yes | |
| Unique `txn_type` values | 6 | 6 | Yes | |
| Count of `Buy` transactions | 83,556 | 83,556 | Yes | |
| `txn_date` data type | object | str | No |The benchmark says object, but newer versions are just labeling the text columns str. Either way, it does not matter because either way, the column is still text, and not a real date. |
| Earliest `txn_date` | 2020-01-01 | 2020-01-01 | Yes | |
| Latest `txn_date` | 2024-12-30 | 2024-12-30 | Yes | |
| Duplicate `txn_id` count | 0 | 0 | Yes | |
| Mean `amount` | $54,075.17 | $54,075.17 | Yes | |
| Median `amount` | $41,220.48 | $41,220.49 (section 10); $41,220.48 (section 5) | No |The true median is 41,220.485 so the script used two different rounding methods that break the tie differently. This is more of a rounding difference than a data error. |
| Skewness of `amount` | 1.15 | 1.1463 | Yes | Rounds to 1.15 |
| Correlation `shares`–`amount` | 0.65 | 0.65 | Yes | |
| Correlation `price`–`amount` | 0.64 | 0.64 | Yes | |
| Correlation `shares`–`price` | 0.00 | 0.00 | Yes | |
| Negative `shares` count (Buy only) | 836 | 836 (all Buy) | Yes | |
| Profile file created | Yes | Yes | Yes | |
| Chart files created (3) | Yes | Yes | Yes | |

### Discrepancy investigations

**Q1 (me):** My pandas script shows the dtype of txn_date as "str", but my assignment's benchmark says it should be "object". Why would that happen, and does it change anything?

**Claude:** It's a pandas version difference, and it doesn't change any of your results. The values in the column are the same text either way. pd.to_datetime, nunique(), value_counts() and missing-value counts all work the same, so your date range and every other result will match. The only difference is the label printed in step 3. Any other text columns, like txn_type or text IDs, will show str for the same reason.

**Q2 (me):** My script printed the median of amount as 41,220.49 in one place and 41,220.48 in another. The benchmark says 41,220.48. The true median is 41,220.485. Why would the two values differ?

**Claude:** The two numbers come from two different rounding methods in your script, and 41,220.485 sits exactly on the halfway point, where the methods disagree. I checked each method in Python to confirm this. The f-string f"{amt_median:,.2f}" rounds the value exactly as the computer stores it. A computer can't store 41,220.485 exactly. The closest value it can store is 41,220.485000000000582…, which is slightly above the halfway point, so it rounds up to .49. The .round(2) in pandas and NumPy doesn't round the stored value directly. It multiplies by 100 first, and that multiplication drops the tiny excess, leaving exactly 4,122,048.5. NumPy then rounds halves to the nearest even number ("banker's rounding"). 4,122,048 is even, so the result is .48.

## 2B — Explain the Code and Output

## 2C — Business Check & Cross-Validation