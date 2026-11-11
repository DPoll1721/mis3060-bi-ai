dim_client[client_tier]	[Is Total]	[Last Snap Date]	[Ending AUM]	[Top 10 Client Share]
HNW	false	Sun, 01 Dec 2024 00:00:00	2548521154.329999	0.03139674749179622
Retail	false	Sun, 01 Dec 2024 00:00:00	533452497.88999945	0.018348218311311226
UHNW	false	Sun, 01 Dec 2024 00:00:00	9647598426.639997	0.08126426752227996
	true	Sun, 01 Dec 2024 00:00:00	12729572078.859997	0.06158926746579308

    dim_client[client_id]	[@SnapDate]	[@AUM]
1573	Sun, 01 Dec 2024 00:00:00	1081976.39
154	Sun, 01 Dec 2024 00:00:00	1054582
361	Sun, 01 Dec 2024 00:00:00	988209.02
195	Sun, 01 Dec 2024 00:00:00	983842.58
1990	Sun, 01 Dec 2024 00:00:00	970770.87
1016	Sun, 01 Dec 2024 00:00:00	966191.94
278	Sun, 01 Dec 2024 00:00:00	947197.93
1454	Sun, 01 Dec 2024 00:00:00	937087.73
756	Sun, 01 Dec 2024 00:00:00	929542.59
985	Sun, 01 Dec 2024 00:00:00	928501.84
222	Sun, 01 Dec 2024 00:00:00	914405.62
2204	Sun, 01 Dec 2024 00:00:00	911285.72
## Part C(a) — Ending AUM vs SUMX over clients (no filters)
| | Value |
|---|---|
| Ending AUM | 12,729,572,078.86 |
| SUMX ( VALUES ( dim_client[client_id] ), [Ending AUM] ) | 13,149,297,713.80 |
| Difference | 419,725,634.94 |

Last snapshot date in model: 12/1/2024 (snapshots are dated 1st of month, not month-end)