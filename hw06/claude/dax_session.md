## Prompt
I'm building a DAX measure in Power BI for a wealth-management star schema. The attached model_metadata.md contains the output of INFO.VIEW.TABLES(), INFO.VIEW.COLUMNS() and INFO.VIEW.RELATIONSHIPS() for my model.

Context the metadata can't tell you:
- Grain of fact_portfolio_snapshot: one row per client per month-end snapshot_date. It is a periodic snapshot, not a transaction table.
- aum is a BALANCE (semi-additive): it can be summed across clients on a single date, but never across dates.
- active_alpha_ytd is year-to-date, so it is not additive across months either.
- dim_date is marked as the date table; dim_date[date] relates to fact_portfolio_snapshot[snapshot_date]. dim_client[client_id] relates to fact_portfolio_snapshot[client_id]. All relationships are single-direction, one-to-many.
- All measures live in a table called _Measures. I already have this measure, which returns the balance at the last snapshot in the current filter context:

Ending AUM =
VAR LastSnap =
    LASTNONBLANK ( dim_date[date], CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) ) )
RETURN
    CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LastSnap )

Business definition of the measure I need:
"Top 10 Client Share" = the share of Ending AUM held by the 10 largest clients WITHIN THE CURRENT FILTER. Clients are ranked by their AUM at the last snapshot date in the filter. Use TOPN over VALUES ( dim_client[client_id] ). For example, in a table by dim_client[client_tier] filtered to 2024, each row should rank only that tier's clients at the end of 2024.

Please give me:
1. The DAX for [Top 10 Client Share]
2. An explanation of its filter context: what the last-date logic does, how TOPN is evaluated inside a tier row, and what happens at the grand total
3. A DAX test query (EVALUATE) I can run in DAX query view that returns the measure at the grand total, by dim_date[year], and by dim_client[client_tier] for 2024
4. Any edge cases I should check (ties at rank 10, clients that left before the last snapshot, tiers with fewer than 10 clients)
## Claude's Response
1. The measure

To create it, select _Measures in the Data pane, open Table tools, choose New measure, paste the code below and press Enter.

```dax
Top 10 Client Share =
VAR LastSnap =
    -- One-row table: the last date in the current filter context that has any AUM
    LASTNONBLANK (
        dim_date[Date],
        CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) )
    )
VAR ClientAUM =
    -- Clients visible in the current filter, each valued at that single date
    FILTER (
        ADDCOLUMNS (
            VALUES ( dim_client[client_id] ),
            "@AUM", CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LastSnap )
        ),
        NOT ISBLANK ( [@AUM] )
    )
VAR Top10 =
    TOPN ( 10, ClientAUM, [@AUM], DESC, dim_client[client_id], ASC )
VAR Top10AUM =
    SUMX ( Top10, [@AUM] )
VAR TotalAUM =
    -- Same result as [Ending AUM], tied to the same LastSnap date
    CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LastSnap )
RETURN
    DIVIDE ( Top10AUM, TotalAUM )

The most important design choice: LastSnap is calculated once for the whole filter context, and every client is then valued on that one date. You might be tempted to write TOPN ( 10, VALUES ( dim_client[client_id] ), [Ending AUM] ), but that version has a bug. Inside TOPN, context transition puts each client into the filter. [Ending AUM] would then find that client’s own last snapshot. A client who left in March 2024 would be ranked by their March balance, and the top 10 total would mix balances from different dates. It can even be larger than the denominator.

2. How the filter context works

Take one row of the table, with tier = “Gold” and year = 2024.

LastSnap. LASTNONBLANK steps through every dim_date[Date] in 2024. For each date, CALCULATE turns that date into a filter while keeping the Gold filter. It returns the last date where Gold clients hold any AUM (normally 2024‑12‑31). The result is a one-row table linked to dim_date[Date], so it can be used as a filter.
VALUES ( dim_client[client_id] ) is evaluated in the outer context, so it returns only Gold clients. The 2024 filter does not reach dim_client, because the relationship only filters one way. This list therefore includes Gold clients with no 2024 rows. The blank filter removes them.
ADDCOLUMNS / CALCULATE. For each client, context transition adds client_id = x. LastSnap then replaces the date filter with 12/31. Because dim_date is marked as a date table, a filter on its date column also clears the Year filter, which doesn’t matter here since 12/31 is in 2024. The tier filter stays, which is harmless.
TOPN ranks only the rows in ClientAUM, which are only Gold clients. TOPN itself knows nothing about tiers. The “within the current filter” behavior comes entirely from step 2.
Numerator and denominator use the same date and the same client set, so the result always falls between 0 and 1. This assumes AUM is never negative.

At the grand total: with no tier filter, VALUES returns every client. Under a 2024 filter, LastSnap is the firm-wide last date of 2024 and you get the firm’s top 10. With no filters at all, LastSnap is the latest snapshot in the whole model and the result is the current firm-wide top 10. The total is not the sum or average of the tier rows. That is correct, because the firm-wide top 10 may come mostly from one tier.

3. Test query

In Power BI Desktop, click the DAX query view icon in the left rail. Paste the query below and click Run. Each EVALUATE produces its own result grid.

```dax
DEFINE
    MEASURE _Measures[Last Snap Date] =
        MAXX (
            LASTNONBLANK ( dim_date[Date], CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) ) ),
            dim_date[Date]
        )

-- 1) Grand total
EVALUATE
ROW (
    "Last Snap Date", [Last Snap Date],
    "Ending AUM", [Ending AUM],
    "Top 10 Client Share", [Top 10 Client Share]
)

-- 2) By year
EVALUATE
SUMMARIZECOLUMNS (
    dim_date[Year],
    "Last Snap Date", [Last Snap Date],
    "Ending AUM", [Ending AUM],
    "Top 10 Client Share", [Top 10 Client Share]
)
ORDER BY dim_date[Year]

-- 3) By tier, 2024, with a 2024 total row
EVALUATE
SUMMARIZECOLUMNS (
    ROLLUPADDISSUBTOTAL ( dim_client[client_tier], "Is Total" ),
    TREATAS ( { 2024 }, dim_date[Year] ),
    "Last Snap Date", [Last Snap Date],
    "Ending AUM", [Ending AUM],
    "Top 10 Client Share", [Top 10 Client Share]
)
ORDER BY [Is Total], dim_client[client_tier]

-- 4) Drill-down: the actual ranked list for one tier (replace "Gold" with a real tier)
EVALUATE
CALCULATETABLE (
    VAR LastSnap =
        LASTNONBLANK ( dim_date[Date], CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ) ) )
    RETURN
        TOPN (
            12,
            ADDCOLUMNS (
                VALUES ( dim_client[client_id] ),
                "@SnapDate", MAXX ( LastSnap, dim_date[Date] ),
                "@AUM", CALCULATE ( SUM ( fact_portfolio_snapshot[aum] ), LastSnap )
            ),
            [@AUM], DESC
        ),
    dim_date[Year] = 2024,
    dim_client[client_tier] = "Gold"
)
ORDER BY [@AUM] DESC

Query 4 returns 12 rows so you can see the cut-off at rank 10. It’s a quick way to check for ties and to add up the first 10 by hand.

4. Edge cases to check

Ties at rank 10. On its own, TOPN returns every row tied at the Nth position, so you could get 11 or more clients. The second sort key, dim_client[client_id], ASC, guarantees exactly 10, but the tie-break is arbitrary. If you would rather include all tied clients, remove that sort key and accept a top “10” that is sometimes 11. Ties are rare with real-valued AUM. They are more likely with rounded or zero balances.

Clients who left before the last snapshot. They have no row on LastSnap, so their value is blank and they are left out. They are neither ranked by an old balance nor counted in the denominator. Watch for these:

Zero-balance rows after departure: If your ETL writes aum = 0 rows after a client leaves, those clients are not blank. They get included but sort to the bottom, which is still correct.
Don’t use dim_client[is_active] for this: It’s a current-state flag. Using it would wrongly drop clients who were active in 2024 and left in 2025.
Inconsistent month-end dates: If some clients’ December snapshot is dated 12/30, the last trading day, while others are dated 12/31, the 12/30 clients will silently disappear. Check that each month has exactly one distinct snapshot_date.
Departures you know about: The fact_transactions[is_post_departure_txn] flag tells you departures exist in this data. Pick a known departed client and confirm they are missing from query 4.

Tiers with fewer than 10 clients. TOPN returns all of them and the share is 100%. That’s correct but not very informative. If you’d rather show a blank, change the RETURN to:

```dax
RETURN
    IF ( COUNTROWS ( ClientAUM ) <= 10, BLANK (), DIVIDE ( Top10AUM, TotalAUM ) )

Issues I spotted in the metadata:

Two sets of Year/Month columns: fact_portfolio_snapshot has its own Year and Month columns. A slicer on those gives the right result, but it bypasses dim_date and is easy to mix up. Hide them and always slice by dim_date[Year].
More than one row per client per date: fact_portfolio_snapshot[account_type] suggests a client could have several rows on one date, one per account. The measure adds them up to the client level before ranking, which matches your definition. It’s still worth confirming the grain with a COUNTROWS check grouped by client and date.
Fact rows with no matching client: If any fact client_id has no match in dim_client, [Ending AUM] includes those rows under a blank client. That blank “client” could rank in the top 10. Check with EVALUATE FILTER ( VALUES ( dim_client[client_id] ), ISBLANK ( dim_client[client_id] ) ), which should return no rows.
Tier history: client_tier is a current attribute, so 2024 is grouped by each client’s tier today, not their 2024 tier.
Auto date/time is on: The hidden LocalDateTable_… on client_since shows it. Turning it off keeps the model tidy: File → Options and settings → Options → Current File → Data Load → uncheck Auto date/time.
Partial current year: For 2026, LastSnap will be the latest month loaded (for example, October), not year-end. That’s expected, but it’s worth labeling in the visual.

I haven’t been able to run this against your data. Run the test query first and compare query 4 against the tier row in query 3.


