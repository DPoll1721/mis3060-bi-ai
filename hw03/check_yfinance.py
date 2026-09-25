import yfinance as yf

ticker = yf.Ticker("AAPL")

# Quarterly income statement: rows = line items, columns = quarter-end dates
income = ticker.quarterly_income_stmt

# Most recent quarter is the first column
latest_date = income.columns[0]
revenue = income.loc["Total Revenue", latest_date]
net_income = income.loc["Net Income", latest_date]

print(f"AAPL - quarter ended {latest_date.date()}")
print(f"Total Revenue: ${revenue:,.0f}")
print(f"Net Income:    ${net_income:,.0f}")
print(f"Net Margin:    {net_income / revenue:.1%}")