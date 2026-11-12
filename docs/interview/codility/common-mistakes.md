# The 15 most common mistakes

Every one of these was shown, with a query or program that was run and failed, somewhere in this guide.

## SQL

| # | Mistake | Fix | Shown in |
|---|---|---|---|
| 1 | An inner `JOIN` (or a `WHERE` on the right-hand table) drops rows that must appear with 0 or `NULL` | `LEFT JOIN`, and put conditions on the right-hand table in `ON` | [Mock 1 task 1](mock-test-1.md), [Seven-day retention](sql-practice.md#31-seven-day-retention) |
| 2 | `COUNT(*)` counts the empty row a `LEFT JOIN` makes | `COUNT(right_table.id)`; and remember every right-hand column, even one you test with `IS NULL`, is `NULL` in that row | [Mock 1 task 1](mock-test-1.md), [Mock 3 task 1](mock-test-3.md), [How many customers ordered how often](sql-practice.md#7-how-many-customers-ordered-how-often) |
| 3 | `SUM` of nothing is `NULL`, not 0 | `COALESCE(SUM(x), 0)` | [Mock 1 task 1](mock-test-1.md) |
| 4 | `NOT IN (subquery)` returns nothing when the subquery has a `NULL` | `LEFT JOIN ... IS NULL`, or filter the `NULL`s out | [Customers who never ordered](sql-practice.md#8-customers-who-never-ordered) |
| 5 | No tie-breaker in `ORDER BY` (or in a window's `ORDER BY`) | Add every sort key the task names | [Mock 1 task 1](mock-test-1.md), [Top two products](sql-practice.md#21-top-two-products-per-category), [Busiest day](sql-practice.md#2-busiest-day) |
| 6 | `ROW_NUMBER` when ties must be kept, or `RANK`/`DENSE_RANK` when exactly N rows are wanted | Match the function to the task's tie rule | [Top earner](sql-practice.md#20-top-earner-in-each-department-ties-included), [Top two products](sql-practice.md#21-top-two-products-per-category), [Mock 4 task 1](mock-test-4.md) |
| 7 | Integer division: `5 / 2` is 2 | `* 1.0` before dividing, and `NULLIF(divisor, 0)` against dividing by zero | [Share of total revenue](sql-practice.md#24-share-of-total-revenue), [Late delivery rate per carrier](sql-practice.md#16-late-delivery-rate-per-carrier) |
| 8 | Forgetting `DISTINCT` (or de-duplication) before counting days or runs | `SELECT DISTINCT` first, or `COUNT(DISTINCT ...)`; but use `UNION ALL`, not `UNION`, when the duplicates are real rows that must be counted | [Mock 1 task 2](mock-test-1.md), [Seven-day retention](sql-practice.md#31-seven-day-retention), [Products bought together](sql-practice.md#18-products-bought-together), [Mock 4 task 2](mock-test-4.md) |
| 9 | Filtering before a window function that needed the removed rows | Compute the window in a CTE, filter outside | [Three hot readings](sql-practice.md#28-three-hot-readings-in-a-row), [Mock 2 task 2](mock-test-2.md) |
| 10 | Date arithmetic written for the wrong dialect, or by hand | PostgreSQL `d + 1`, `EXTRACT`; SQLite `date(d, '+1 day')`, `julianday`, `strftime` | [Mock 1 task 2](mock-test-1.md), [Count sessions](sql-practice.md#30-count-sessions), [Seven-day sales with missing days](sql-practice.md#33-seven-day-sales-with-missing-days) |
| 11 | A correlated subquery that is fine on PostgreSQL but takes minutes on SQLite with big tables | Prefer a join | [Customers who never ordered](sql-practice.md#8-customers-who-never-ordered) |

## Python

| # | Mistake | Fix | Shown in |
|---|---|---|---|
| 12 | An O(N²) loop when N can be 100,000 (`x in list`, re-summing slices, `max(T[:i])`) | `set`/`dict`, prefix sums, sliding window, a running maximum | [First repeated ID](python-practice.md#1-first-repeated-id), [Best K consecutive days](python-practice.md#24-best-k-consecutive-days), [Mock 2 task 3](mock-test-2.md), [Mock 4 task 3](mock-test-4.md) |
| 13 | A tie rule ignored: `Counter.most_common` breaks ties by first appearance, and a plain FIFO queue ignores "smallest ID first" | Sort with a key tuple such as `(-count, name)`, or use a heap | [Most frequent error code](python-practice.md#2-most-frequent-error-code), [Run order for pipeline tasks](python-practice.md#35-run-order-for-pipeline-tasks) |
| 14 | Edge input crashes the code: empty input, a blank line, a trailing newline | Run the empty case yourself; `split()` with no argument | [Count log levels](python-practice.md#11-count-log-levels), [Rows with the wrong number of fields](python-practice.md#13-rows-with-the-wrong-number-of-fields) |
| 15 | Deep recursion on big input (`RecursionError`) | Loops with an explicit stack or `deque` | [Count the blocks on a map](python-practice.md#34-count-the-blocks-on-a-map), [Flatten a nested record](python-practice.md#20-flatten-a-nested-record) |

## And one for both

Read the statement twice: **strictly** greater or **at least**? "Every X" or only those with rows? Which order,
which columns, which type to return? Most lost points come from the statement, not the algorithm.
