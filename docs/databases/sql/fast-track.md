# SQL interview fast track

*For someone who used SQL before, has forgotten much of it, and has a coding test coming. Two days, the chapters
that are tested most, in the order that builds fastest. Each step says what to be able to do before moving on.*

!!! abstract "What the test is likely to look like"
    A data engineering coding test often has two SQL tasks and one in Python, timed. On Codility's own practice
    page (checked 11 Nov 2026) a SQL task offers two languages: **SQL (PostgreSQL)** and **SQL (SQLite)**, and says
    the names of the result's columns do not matter but their **order** does. A real employer's test may differ:
    its first page lists the languages allowed, so read it before you start. The [Codility test
    prep](../../interview/codility/index.md) guide covers the test itself; this page covers the SQL.

    **Pick PostgreSQL if you are free to choose.** It follows the standard more closely, it has every function this
    course uses, and it reports mistakes instead of guessing. SQLite quietly accepts some wrong queries (you will
    see examples), which helps nobody under time pressure.

## Day 1: the core { #day-1 }

| Step | Read | What it is about | Be able to |
| --- | --- | --- | --- |
| 1 | [Cheat sheet](cheat-sheet.md) | Every clause and function on one page: what it does and when to use it. | Recall the shape of every clause |
| 2 | [The sample database](sample-database.md) | The shop's 8 tables (customers, orders, products ...) that every example uses. | Know the tables; you will use them all day |
| 3 | [3. The order a query really runs in](03-The-Order-a-Query-Runs-In.md) | A query is written SELECT first but runs FROM, WHERE, GROUP BY, HAVING, SELECT, ORDER BY, LIMIT. | Say why an alias from SELECT can't be used in WHERE |
| 4 | [6. NULL and three-valued logic](06-Null-and-Three-Valued-Logic.md) | NULL is a missing value; any comparison with it is *unknown*, which quietly drops rows. | Explain why `NOT IN` can return nothing |
| 5 | [7. Aggregation: GROUP BY and HAVING](07-Aggregation-Group-By-Having.md) | `GROUP BY` folds rows into one per group; `COUNT`, `SUM`, `AVG` summarise each; `HAVING` filters groups. | Pick between WHERE and HAVING; count three ways |
| 6 | [8. Joins](08-Joins-Inner-Left-Right-Full-Cross.md) | Joins put rows of two tables side by side; `LEFT JOIN` keeps rows that have no match. | Keep unmatched rows with LEFT JOIN, and not lose them again in WHERE |
| 7 | [9. Self, semi and anti joins](09-Self-Semi-and-Anti-Joins.md) | A self join pairs a table with itself; semi and anti joins keep rows with, or without, a match. | Find "customers with no orders" three ways |
| 8 | [10. Subqueries](10-Subqueries.md) and [11. CTEs](11-CTEs-and-Recursive-CTEs.md) | A query inside a query, and `WITH` steps that name each part of a long query. | Break a hard question into named steps |

## Day 2: what separates a pass from a strong pass { #day-2 }

| Step | Read | What it is about | Be able to |
| --- | --- | --- | --- |
| 9 | [13. Window functions: ranking](13-Window-Functions-Ranking.md) | Window functions number or rank rows inside groups without merging them into one row. | Top N per group, with ties handled the way the task asks |
| 10 | [14. Window functions: LAG, LEAD, running totals](14-Window-Functions-Lag-Lead-Running-Totals.md) | `LAG` and `LEAD` read the previous and next row; `SUM(...) OVER` gives running totals. | Compare each row with the one before it; running sums |
| 11 | [15. Classic interview patterns](15-Classic-Interview-Patterns.md) | Ready-made answers to the questions asked most often: Nth highest, latest row, streaks, pivots. | Nth highest, latest row per key, streaks, pivots, percent of total |
| 12 | [16. Dates and time series](16-Dates-and-Time-Series.md) | Grouping by month or week, counting days between dates, and listing days that have no data. | Group by month in both PostgreSQL and SQLite; fill missing days |
| 13 | [5. Text functions and pattern matching](05-Text-Functions-and-Pattern-Matching.md) | Cutting, cleaning and matching text: `LIKE`, `SUBSTR`, `TRIM`, `split_part`. | LIKE, splitting and trimming, in both dialects |
| 14 | [Which technique does this wording ask for?](which-technique.md) | A table from task phrases ("never", "per month", "in a row") to the technique that answers them. | Turn a task's words into a technique in a minute |
| 15 | [30. Practice set A](30-Practice-Set-A.md) | Interview-style questions on the shop, answers hidden until you open them. | Solve each in under 10 minutes before opening the answer |
| 16 | [32. Mock tests](32-Mock-Tests.md) | Timed two-question tests in the format of a coding test. | Two questions in 40 minutes, timed |
| 17 | [SQL drills](drills.md) | Short exercises with a Check button, one idea each. | 36 short exercises with Check: filters, GROUP BY, joins, subqueries, windows, dates |
| 18 | [Analytics workshop](analytics-workshop.md) | Longer analytics tasks on payments and page views, the kind a data team asks. | Aggregate before joining, reconcile, deduplicate, sessions and a funnel |

If there is time left, [12. UNION and friends](12-Set-Operations.md), [22. Duplicates and incremental
loads](22-Duplicates-and-Incremental-Loads.md) and [19. Data modelling](19-Data-Modelling.md) are the topics a data
engineering interviewer most often talks about after the coding test.

## Ten habits for the test itself { #habits }

1. **Read the expected output first.** Its columns, their order, the sort order and how numbers are rounded are
   part of the answer. A correct query in the wrong column order can fail.
2. **Ask what one row of the answer is** ("one row per customer", "one row per month") before writing anything.
   That decides the GROUP BY.
3. **Build in steps with CTEs** (`WITH a AS (...), b AS (...) SELECT ...`) and run each step on its own.
4. **Look for ties.** "The highest paid" may be two people. Use `RANK` or `DENSE_RANK` unless the task says to pick
   one, and then say how (`ROW_NUMBER` with a tie-break column).
5. **Look for NULLs** in every column you filter, join or count. `COUNT(col)` skips them; `= NULL` never matches.
6. **Check row counts after every join.** If a join to a "many" table multiplies rows, sums double count.
7. **Integer division:** `7 / 2` is `3` in both PostgreSQL and SQLite. Multiply by `1.0` first when you need a
   fraction.
8. **Round only at the end,** and the way the task asks (`ROUND(x, 2)`). In PostgreSQL, `ROUND(x, 2)` needs `x` to be
   `numeric`, not `double precision` (see [chapter 4](04-Expressions-Case-Numbers-Dates-Cast.md)).
9. **Always end with ORDER BY** when the task names an order. Without it the database may return rows in any order.
10. **Test on the edge cases** the task hints at: an empty group, a tie, a NULL, a single row. Hidden tests usually
    check exactly those.
