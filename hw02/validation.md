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
**1. Did Claude's predicted outputs (Prompt 1) match what I actually saw?**

Claude's predictions mostly matched for the basics: rows, columns, and duplicates. However, it predicted txn_date and txn_type would show as `object`, but my output showed str. It also guessed that sells might have negative shares, but only buys did (836 rows). Most other values were placeholders because it didn't have the data file.

**2. What did Claude flag as unexpected or worth investigating (Prompt 2)?**

Claude flagged 5 things. The most important was the negative shares on buys. It also pointed out that advisory fees are very skewed, and that all amounts are positive, so direction comes from txn_type.

**3. Did Claude mention the 101,597 null values in security_id? What explanation did it give?**

Yes. Claude explained that the 101,597 blanks equal the number of deposits, advisory fees, and withdrawals transactions combined. Since those are cash transactions, they have no security, so the blanks are expected, not errors.

**4. Did Claude flag txn_date as a concern? Why would that matter for a time-series analysis?**

No, not really. Claude noted the type was str but did not flag it as a concern. This matters for time-series analysis because text dates can't be subtracted to find the days between transactions, and you can't group by month or year until they're converted to real dates.

**5. Do my three charts match Claude's explanation?**

- **Histogram:** Matches Claude's description. The shape is right-skewed, and the mean line is to the right of the median line.
- **Box plot:** Matches. The boxes are bunched toward the left, and advisory fee stands out as much smaller than the other types.
- **Scatter plot:** Matches. The dots are colored by txn_type, and I can see a small group of points with negative shares.

**6. My follow-up question and Claude's answer:**

**Me:** 
You said the 836 negative Buy shares might be sign flips. What are two possible business explanations for a Buy transaction having a negative share count, and how could I tell which one is true?

**Claude:**
Here are two explanations that fit a Buy with negative shares:

1. Data entry or system error (a sign flip). The trade was an ordinary purchase, but the minus sign was added by mistake. That could happen through a keying error, a bug in the system that exports the data, or a feed that uses a different sign convention. In that case the correct share count is just the absolute value.

2. A reversal or cancellation. Firms often cancel or correct a trade by booking an offsetting entry against it. A Buy that was entered and then cancelled could appear as the original Buy of +200 shares plus a Buy of −200 to undo it. Here the negative sign is real information: the net effect on the client's holdings is zero, and you shouldn't "fix" it.

How to tell which one is true

The amount column won't settle it. Amounts are positive for every transaction type, and |shares| × price should match amount under either explanation. These tests can tell them apart:

Look for matching partners. A reversal should have a twin: a positive Buy for the same client and security, with the same share count and usually the same price, dated on or shortly before the negative one. If most of the 836 have a twin, it's reversals. If almost none do, it's sign flips.

buys = df[df["txn_type"] == "Buy"].copy()
buys["abs_shares"] = buys["shares"].abs().round(4)
neg = buys[buys["shares"] < 0]
pos = buys[buys["shares"] > 0]

pairs = neg.merge(pos, on=["client_id", "security_id", "abs_shares"], suffixes=("_neg", "_pos"))
pairs["days_apart"] = (pd.to_datetime(pairs["txn_date_neg"]) - pd.to_datetime(pairs["txn_date_pos"])).dt.days

print(f"Negative buys: {len(neg)}")
print(f"With a matching positive buy: {pairs['txn_id_neg'].nunique()}")
print(pairs["days_apart"].describe())

Check the pattern. Sign flips from a random error would be spread evenly across clients, advisors, securities and dates, and their share sizes would look like normal Buys (evenly spread up to 500). Reversals tend to happen soon after the original trade. Also count the negatives per advisor and per month. If they're concentrated in one advisor or one time period, that points to a process or system problem, not a random one.

Test the holdings. For each client and security, add up shares over time: Buys add, Sells subtract. Do it twice, once treating the negatives as reversals and once treating them as positive Buys. Whichever version ends up with clients selling shares they don't own (negative holdings) is probably the wrong one.

Ask the data owner. In a real firm, the data dictionary or the operations team would tell you how cancellations are recorded. That's the definitive answer.

For this dataset, my guess is sign flips. The count is exactly 1% of Buys, Wildcat Capital data is generated for the course, and a planted error would look like this. Run the partner check before you commit to that, though, and note what you found in your write-up. Whichever way it comes out, flagging and explaining how you handled the 836 rows will count for more than quietly fixing them.

## 2C — Business Check & Cross-Validation
### Business-reasonableness questions

**1. Which three transaction types have no security, and do the counts add up to 101,597?**

The three types with no security are deposit, withdrawal, and advisory fee. They make sense because these transactions only move cash, not stocks/securities. Their counts are 35,981 + 29,850 + 35,766 = 101,597, which is equivalent to the 101,597 nulls.

**2. What does it mean to have significantly more Buys than Sells over five years?**

Having 83,556 Buys but only 59,755 Sells means clients are buying and investing more than they are selling over time. This suggests Wildcat Capital's assets under management are growing over time, likely because clients are adding/depositing new money. This also fits with Deposits being higher than Withdrawals.

**3. What would go wrong computing average days between transactions if txn_date stays a string?**

Because txn_date is stored as str, Python sees "2024-05-15" as a string of characters, not a real date. If the code tried to subtract two dates to find the days between them, it would throw an error, because you can't subtract text from text. The dates would need to be converted to date type first.

**4. Is ~108 clients per advisor plausible for a registered investment advisory firm?**

2,700 clients ÷ 25 advisors ≈ 108 clients per advisor. According to a Financial Planning article citing the 2025 Ensemble Practice Report (a survey of 230 firms), a typical advisor serves about 100-164 clients. So 108 is pretty plausible for a firm like Wildcat Capital because it falls within in the range.
   Source: [Financial Planning – How many clients should an RIA have](https://www.financial-planning.com/news/how-many-clients-should-an-ria-have)


**5. Two plausible explanations for negative shares on Buy transactions, and what I'd do next:**

One explanation is a data-entry sign error, where someone or the system accidentally added a minus sign on a normal Buy, so the real share count is just the positive number. A second explanation is a reversal, where the firm cancels an earlier Buy by recording an offsetting negative entry. To figure out which is more likely, I would first check whether each negative Buy has a matching positive Buy for the same client and security. If most do, it points to reversals. If almost none do, it points to sign errors. I'd also check whether the negatives are concentrated in one advisor or time period, and ask the data owner how cancellations are recorded.
### Cross-validation

**6. What did each script return?**

Script A (direct filter) returned 83,556 Buy transactions. Script B (subtraction) found 298,772 total rows, subtracted 215,216 non-Buy rows, and was left with 83,556.

**7. Do the results agree? If not, which is wrong and why?**

Yes, both methods returned 83,556, which also matches the benchmark. Since two different approaches gave the same answer, I'm assuming that the Buy count is correct.

**8. Why is it useful to verify a count using subtraction rather than direct filtering?**

Direct filtering only counts rows that exactly match "Buy", so it would silently miss rows with problems like a typo or a blank value. Subtraction counts everything that aren't one of the other five types, so if there were any misspelled or unexpected values, the two counts would not match. Getting the same number both ways confirms that there are no hidden bad or unexpected values in txn_type. 