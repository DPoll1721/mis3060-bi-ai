# HW4 Decision Log — Wildcat Capital
Written before the cleaning code. Each entry is the instruction for `scripts/02_clean.py`.
Evidence comes from `reports/dq_summary_raw.csv` (01_profile.py) plus targeted checks noted below.

## Cleaning order (and why)
1. **Standardize formats first** (security_id `45.0`→`45`, `%` returns, state names). Otherwise the RI check would count format problems as orphans and quarantine good rows.
2. **De-duplicate dimensions** (dim_client duplicates). Facts can't be checked against a dimension that has duplicate keys.
3. **Fill from verified sources** (risk_profile from benchmark). Runs after de-duplication so only real clients are filled.
4. **Quarantine true orphans** (after steps 1–3, anything still unmatched really has no parent).
5. **Sign fixes and flags** last, on the final set of rows.

---

## Dimension tables

### D1. dim_client — duplicate clients (IDs 2501–2525)
- **Evidence:** 25 clients (50 rows counting both copies) match another client on first_name, age, city, zip_code and initial_aum. Last name is truncated in the copy (e.g. 2501 "Taylo" vs 674 "Taylor"). Checked the other 7 attributes (state, risk_profile, tier, account type, client_since, advisor, is_active): 0 differences. None of the 25 IDs appear in any fact table.
- **Dimension:** Uniqueness, Accuracy
- **Decision:** Quarantine IDs 2501–2525 → `quarantine_dim_client_duplicates.csv` (with the ID of the original they duplicate).
- **Justification:** Same person under two IDs inflates the client count (2,525 vs the true 2,500) and splits activity. The originals have the correct full name, and no facts point to the copies, so removing them loses nothing.
- **Risk:** If two real, different people share name, age, city, zip and AUM to the cent, we'd remove a real client. Very unlikely, and the truncated last names point to a data-entry copy.

### D2. dim_client.state — full state names
- **Evidence:** 78 rows use full names instead of 2-letter codes: Pennsylvania 25, Florida 15, New York 14, New Jersey 13, California 5, Illinois 4, Texas 2. The other 2,447 use USPS codes.
- **Dimension:** Consistency, Validity
- **Decision:** Standardize to USPS codes (PA, FL, NY, NJ, CA, IL, TX). Log each change in `value_changes.csv`.
- **Justification:** A BI slicer or map would show "PA" and "Pennsylvania" as two states, splitting PA, the largest state (439 clients after the fix).
- **Risk:** Very low; the mapping is one-to-one. The script asserts that every value is a valid code after the fix.

### D3. dim_client.risk_profile — blanks
- **Evidence:** 76 blank. 1 belongs to a duplicate client (removed in D1). For the other 75, the portfolio snapshots use benchmark 3 (60/40 Blend). Across all clients with a known profile, benchmark 3 is used **only** by "Balanced" (757 of 757). Benchmarks 1 and 8 are each shared by two profiles, but none of the blanks use them.
- **Dimension:** Completeness
- **Decision:** Fill the 75 with "Balanced" and add flag column `flag_risk_profile_imputed` = 1.
- **Justification:** This isn't a guess. The benchmark assignment uniquely identifies the profile, so we reconcile from another table. The flag keeps it transparent for anyone filtering on risk.
- **Risk:** If the benchmark rule has exceptions we can't see, a few clients could be mislabeled. The flag lets an analyst exclude them.

### D4. dim_client.is_active = True with no Dec-2024 snapshot
- **Evidence:** 24 clients. All 24 are duplicate IDs from D1 (the 25th duplicate is inactive).
- **Dimension:** Consistency (cross-table)
- **Decision:** Leave as is; resolved by D1.
- **Justification:** Once duplicates are removed, every active client has a December 2024 snapshot. The validation script re-checks this.
- **Risk:** None beyond D1.

### D5. dim_client.zip_code — leading zeros
- **Evidence:** 232 zip codes start with 0 (e.g. "03897"). Default `read_csv` would turn these into 3897.
- **Dimension:** Validity (format risk, not a defect)
- **Decision:** Leave as is; keep as text. Document in README_clean.md that BI must load zip_code as **Text**.
- **Justification:** The raw values are correct; only a careless load would break them.
- **Risk:** If a BI tool auto-detects it as a number, NJ/MA/CT zips lose their leading 0.

### D6. dim_advisor.certifications — the text "None"
- **Evidence:** 6 advisors have the literal text "None".
- **Dimension:** Completeness (apparent only)
- **Decision:** Leave as is (legitimate value).
- **Justification:** "None" means the advisor holds no certifications, which is a real business answer, not missing data. Default `read_csv` would wrongly turn it into NaN, which is why we read as text.
- **Risk:** A BI tool may treat "None" as null; documented in README_clean.md.

### D7. dim_security — blank sector / blank expense_ratio_bps
- **Evidence:** sector is blank for 219 securities, all ETFs (is_etf = True). expense_ratio_bps is blank for 281, all individual stocks. 0 exceptions either way.
- **Dimension:** Completeness (apparent only)
- **Decision:** Leave as is (legitimate structure).
- **Justification:** Funds don't have a single GICS sector, and stocks don't have an expense ratio. Filling either would invent data.
- **Risk:** None; documented so BI users don't read blanks as missing data.

### D8. dim_security.name — same name, different ticker
- **Evidence:** 3 pairs (e.g. "Jones Inc Fund": OLAB = Alternative, YXPS = Fixed Income).
- **Dimension:** Uniqueness (apparent only)
- **Decision:** Leave as is.
- **Justification:** Different tickers and asset classes, so they're different products. ticker and security_id are unique.
- **Risk:** Low; reports should label by ticker, not name.

### D9. dim_date.is_trading_day — market holidays marked as trading days
- **Evidence:** 14 dates are fixed-date NYSE holidays but have is_trading_day = 1 (e.g. 2020-01-01, 2020-07-03, 2020-12-25, 2021-07-05). The flag is simply "weekday = 1". (Found by the Claude Code review.)
- **Dimension:** Accuracy
- **Decision:** Correct is_trading_day to 0 for these 14 dates, logged in `value_changes.csv`.
- **Justification:** NYSE closures are fixed public facts, not guesses, and trading-day counts feed return and turnover math.
- **Risk:** Only New Year, July 4 and Christmas are covered. Floating holidays (MLK, Good Friday, Thanksgiving, etc.) are still marked 1. This is listed as a known limitation.
---

## Fact tables

### F1. fact_transactions.security_id — stored as decimal text
- **Evidence:** All 197,175 non-blank values end in ".0" (e.g. "45.0"), while dim_security uses "45". Raw RI match = 0%. After removing ".0": 100% match, 0 orphans.
- **Dimension:** Validity, Referential Integrity
- **Decision:** Convert: strip ".0", keep as integer text.
- **Justification:** A float export artifact. Without the fix, no trade or dividend can be joined to its security.
- **Risk:** None if the assert passes. The script asserts 100% RI match after the fix and that no value had a non-zero decimal.

### F2. fact_transactions.client_id — orphan clients
- **Evidence:** 200 rows reference 200 distinct client IDs (2702–3192) that don't exist in dim_client (which ends at 2525). This is after F1, so it's not a format problem.
- **Dimension:** Referential Integrity
- **Decision:** Quarantine → `quarantine_fact_transactions_orphan_client.csv`.
- **Justification:** We can't assign these to a real client without inventing a mapping. Kept, not deleted, so they can be traced back to the source system.
- **Risk:** If these are real clients missing from the dimension, client-level totals are understated by 200 rows (0.07%).

### F3. fact_transactions.shares — negative on Buy rows
- **Evidence:** 836 rows, all txn_type = Buy, with negative shares but a positive amount. For all 836, |shares| × price = amount (within 1%).
- **Dimension:** Validity, Consistency
- **Decision:** Convert to absolute value; log in `value_changes.csv`.
- **Justification:** Reconciled, not assumed: the amount and price confirm the size, so only the sign is wrong. The sign convention is carried by txn_type (Buy/Sell), not by shares.
- **Risk:** If these were really sells mislabeled as buys, flipping the sign keeps the wrong type. But amount × price matches, and no other column suggests a sell.

### F4. fact_transactions — blank security_id / shares / price on cash rows
- **Evidence:** 101,597 rows blank in all three; every one is a Deposit, Withdrawal or Advisory Fee. 0 Buy/Sell/Dividend rows are missing them.
- **Dimension:** Completeness (apparent only)
- **Decision:** Leave as is (legitimate structure).
- **Justification:** Cash movements have no security.
- **Risk:** None; documented. In BI, the security_id relationship must allow blanks.

### F5. fact_transactions — Dividend amount = full position value
- **Evidence:** All 53,864 Dividend rows have amount = shares × price, i.e. the value of the whole position (e.g. txn 1: 455 shares × $147.90 = $67,311 "dividend").
- **Dimension:** Accuracy/Plausibility
- **Decision:** Leave as is; document as a known limitation.
- **Justification:** A real dividend is a small % of position value, but we have no dividend-per-share data to recompute it. A flag on 100% of dividends adds nothing.
- **Risk:** Income totals would be massively overstated if summed. The README warns not to use dividend amounts as income.

### F6. fact_transactions — Buy/Sell on non-trading days
- **Evidence:** 40,649 Buy/Sell rows on weekends, plus 1,095 on market holidays (D9).
- **Dimension:** Accuracy/Plausibility
- **Decision:** Flag: add `flag_nontrading_day` = 1.
- **Justification:** Exchanges are closed on these days, so the date is probably a booking or settlement date. We can't know the true trade date, so we flag rather than move it.
- **Risk:** If these are legitimate booking dates, the flag is just noise; analysts can ignore it.

### F7. fact_transactions — activity after the account closed
- **Evidence:** 2,410 rows for 131 clients dated after the client's last snapshot month. All 131 are is_active = False.
- **Dimension:** Consistency (cross-table)
- **Decision:** Flag: add `flag_after_account_close` = 1.
- **Justification:** A closed account shouldn't trade, but these could be final settlements. We can't tell which, so we flag them.
- **Risk:** Flows from closed accounts stay in totals unless filtered.

### F8. fact_transactions Advisory Fee vs fact_fees — don't reconcile
- **Evidence:** 28,746 client-months appear in both tables; amounts match in only 1. Transactions can hold several fee rows a month.
- **Dimension:** Consistency (cross-table)
- **Decision:** Leave as is; document.
- **Justification:** fact_fees reconciles perfectly in two independent ways: amount = aum_basis × bps ÷ 10,000 ÷ 12 (0 mismatches), and aum_basis = snapshot AUM (0 mismatches). So **fact_fees is the source of truth for fee revenue**; the transaction fee rows are cash debits on a different schedule.
- **Risk:** Anyone summing "Advisory Fee" transactions as revenue gets a different number. The README says to use fact_fees.

### F9. fact_portfolio_snapshot.return_ytd — "%" strings
- **Evidence:** 300 values stored like "9.28%"; all others are fractions (0.0928).
- **Dimension:** Validity, Consistency
- **Decision:** Convert: strip "%" and divide by 100.
- **Justification:** Verified against another column: for all 300 rows, value/100 − benchmark_return_ytd = active_alpha_ytd (within 0.0001). This confirms the intended fraction.
- **Risk:** None if the assert passes; the script asserts the alpha identity on all rows after the fix.

### F10. fact_portfolio_snapshot.aum = 1,000.00 placeholder
- **Evidence:** 420 rows (92 clients) at exactly 1000.0, the minimum value in the table, usually between normal months (e.g. client 1026: 33,870 → 1,000 → 1,000 → 33,978). 386 fee rows were charged on this 1,000 basis.
- **Dimension:** Accuracy/Plausibility
- **Decision:** Flag: add `flag_aum_placeholder` = 1 in fact_portfolio_snapshot and fact_fees. Values unchanged.
- **Justification:** It looks like a floor/default, not a real balance, but filling it in (e.g. interpolating) would invent AUM.
- **Risk:** AUM totals for those months are understated; filter on the flag for AUM trend charts.

### F11. fact_portfolio_snapshot — implausible returns (return_ytd > 100%)
- **Evidence:** 976 rows (144 clients) with return_ytd > 1 (max 94.67 = +9,467%). active_alpha_ytd is outside ±1 on 1,176 rows. The values are internally consistent: alpha = return − benchmark holds, and they follow the AUM path. These are small accounts (median lowest AUM in the year: $25.8K), often recovering from the 1,000 placeholder.
- **Dimension:** Accuracy/Plausibility
- **Decision:** Flag: add `flag_return_outlier` = 1 where |return_ytd| > 1 or |active_alpha_ytd| > 1. Values unchanged.
- **Justification:** The math is consistent, so we can't "correct" them, but they would wreck any average-return chart.
- **Risk:** Averages stay distorted unless filtered or median is used.

### F12. fact_fees.bps_charged = 100.38 (above 100)
- **Evidence:** 1 row (fee 68809, Retail client). The Retail range is 74.9–100.4 bps, and the amount reconciles exactly.
- **Dimension:** Validity (range)
- **Decision:** Leave as is.
- **Justification:** 0.38 bps over a soft cap, consistent with the Retail range, and the fee math checks out. Not a defect.
- **Risk:** Negligible ($90.68 fee).

### F13. Checks that passed (no action)
- 0 duplicate primary keys or grains in any table; 0 whitespace problems; all dates ISO.
- All advisor_id, benchmark_id and date foreign keys match 100%.
- advisor_id on every fact row = the client's advisor; snapshot account_type = the client's primary account type.
- dim_date: year/month/quarter/day names all match the date; no gaps; 1,827 consecutive days.
- client_tier always matches the initial AUM band (<$500K Retail, <$5M HNW, $5M+ UHNW).