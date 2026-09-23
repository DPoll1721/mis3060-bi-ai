# HW2 Specification: EDA Script for Wildcat Capital Transactions

**Author:** Drew Pollock
**Date:** 9/22/2026
**Course:** MIS3060 Business Intelligence with AI

Write one single Python script, saved as `hw02/hw02_eda.py`, that performs all of the steps below in a single run.

- Run it from the repository root with `python hw02/hw02_eda.py`.
- Create the `hw02/charts/` folder if it doesn't exist.
- Save charts to files without opening pop-up windows.

## Steps the script must perform

1. Load the file data/raw/fact_transactions.csv into a pandas DataFrame.
2. Print the number of rows and columns, with a clear label.
3. Print all column names and their data types, with a clear label.
4. Print the total number of missing values for each column.
5. Print all descriptive statistics for all numeric columns, including count, mean, std, min, 25th pct, median, 75th pct, max
6. Print value counts and percentages for txn_type, in descending order of frequency it appears in
7. Print the unique count of clients, advisors, and securities referenced in file
8. Print earliest and latest txn_date, the date range of the dataset
9. Check whether any txn_id value appears more than once. Print the number of duplicate txn_id values with a clear label. The expected result is 0.
10. Print mean, median, and skewness of the amount column.
11. Group the data by txn_type and print, for each type, the count and the mean and the median amount (rounded to 2 decimal places), sorted by mean amount in descending order
12. Compute the correlation matrix for shares, price, and amount (rounded to 2 decimal places), print it, and identify the three strongest correlations (excluding a variable's correlation with itself)
13. Print the minimum, maximum, and count of negative values in the shares column, broken out by txn_type
14. Print a warning if the shape is not (298772,9)
15. Create and save three charts to the hw02/charts/ folder: a histogram of amount with vertical lines at the mean and median, labeled clearly (hw02/charts/hist_amount.png); a horizontal box plot of amount by txn_type (hw02/charts/box_amount_by_type.png); and a scatter plot of shares (x-axis) vs. amount (y-axis) colored by txn_type, using small, semi-transparent dots (hw02/charts/scatter_shares_amount.png).
16. Save a plain-text summary of items 2-13 to hw02/hw02_profile.txt
17. Include a comment block at the top identifying the script, dataset, author (Drew Pollock), and generation date