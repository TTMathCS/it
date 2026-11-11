# Which technique does this wording ask for?

*A test task is a paragraph of words about an unfamiliar table. The first minute goes on turning the words into a
technique. This page maps the phrases that come up again and again to the technique that answers them, the trap
that usually comes with it, and the chapter that teaches it with run examples.*

!!! abstract "How to read a task, in five steps"
    1. **The grain of the answer.** What is one output row: one customer, one day, one pair? That decides the
       `GROUP BY` or the window's `PARTITION BY`.
    2. **The columns, in order.** Write the final `SELECT` list first, exactly as asked.
    3. **The phrases.** Find them in the tables below; each points to a technique.
    4. **The edge cases.** NULLs, ties, empty groups, duplicates, rows with no match. The task's example rarely shows
       them; the hidden tests nearly always do.
    5. **The order.** If the task gives one, `ORDER BY` it with a tie-breaker; if not, sort by the key anyway.

## Which rows { #rows }

| The task says | Technique | The usual trap | Chapter |
| --- | --- | --- | --- |
| "who have ...", "at least one ..." | `EXISTS` (semi join), or a join + `DISTINCT` | the join repeats rows | [9.2](09-Self-Semi-and-Anti-Joins.md#semi) |
| "never", "without any", "who have not", "no ..." | `NOT EXISTS` (anti join), or `LEFT JOIN ... WHERE right.key IS NULL` | `NOT IN` with a NULL in the list returns nothing | [9.3](09-Self-Semi-and-Anti-Joins.md#anti), [6.8](06-Null-and-Three-Valued-Logic.md#joins-not-in) |
| "none in March", "no shipped orders" | anti join with the condition **inside** the subquery | putting the condition in the outer `WHERE` | [9.4](09-Self-Semi-and-Anti-Joins.md#anti-conditions) |
| "in both A and B", "and also" | `INTERSECT`, or `HAVING` with two conditional counts | one row cannot be in January and March | [12.2](12-Set-Operations.md#intersect) |
| "in A but not B" | `EXCEPT`, or anti join | `EXCEPT` removes duplicates | [12.3](12-Set-Operations.md#except) |
| "every", "all of", "each of the ..." | `COUNT(DISTINCT x) = (SELECT COUNT(*) ...)`, or double `NOT EXISTS` | counting duplicates twice | [15.6](15-Classic-Interview-Patterns.md#every) |
| "more than the average", "above their department's ..." | scalar subquery, correlated subquery, or `AVG(...) OVER (PARTITION BY ...)` | an aggregate in `WHERE` | [10.3](10-Subqueries.md#correlated), [13.1](13-Window-Functions-Ranking.md#aggregate-windows) |
| "earns more than their manager", "pairs of ..." | self join | pairs counted twice: add `a.id < b.id` | [9.1](09-Self-Semi-and-Anti-Joins.md#self) |
| "between 1 and 31 March", "in March" | `>= '2026-03-01' AND < '2026-04-01'` | `BETWEEN` loses most of the last day of timestamps | [16.5](16-Dates-and-Time-Series.md#ranges) |
| "names starting with a" | `LOWER(name) LIKE 'a%'` | `LIKE` ignores case on SQLite only | [5.6](05-Text-Functions-and-Pattern-Matching.md#like-case) |
| "missing", "unknown", "not given" | `IS NULL` | `= NULL` finds nothing | [6.3](06-Null-and-Three-Valued-Logic.md#is-null) |

## Counting and totals { #totals }

| The task says | Technique | The usual trap | Chapter |
| --- | --- | --- | --- |
| "for each ...", "per ...", "by ..." | `GROUP BY` the key of that thing | grouping by a name that repeats | [7.3](07-Aggregation-Group-By-Having.md#group-by), [7.8](07-Aggregation-Group-By-Having.md#group-by-key) |
| "how many different ..." | `COUNT(DISTINCT x)` | `COUNT(x)` counts repeats | [7.2](07-Aggregation-Group-By-Having.md#count) |
| "including those with none", "show 0" | `LEFT JOIN` + `COUNT(right.key)` or `COALESCE(SUM(...), 0)` | `COUNT(*)` counts 1; a filter in `WHERE` drops them | [8.3](08-Joins-Inner-Left-Right-Full-Cross.md#on-vs-where), [8.4](08-Joins-Inner-Left-Right-Full-Cross.md#count-left) |
| "groups with more than ..." | `HAVING` | the condition in `WHERE` | [7.5](07-Aggregation-Group-By-Having.md#having) |
| "how many of them are ...", "and how many cancelled" | `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` | a second query, or a `WHERE` that drops the rest | [7.6](07-Aggregation-Group-By-Having.md#conditional) |
| "percentage", "ratio", "rate" | `100.0 * part / whole`, `ROUND(..., n)` | whole-number division gives 0 | [7.7](07-Aggregation-Group-By-Having.md#division) |
| "percent of total", "share of all" | `100.0 * x / SUM(x) OVER ()` | dividing by a total from the wrong grain | [13.1](13-Window-Functions-Ranking.md#aggregate-windows) |
| "average order value" | aggregate to one row per order first, then `AVG` | averaging the lines instead | [Practice A.4](30-Practice-Set-A.md#questions) |
| "total revenue per customer" with several joined tables | aggregate each table to the key first, then join | fan-out multiplies sums | [8.8](08-Joins-Inner-Left-Right-Full-Cross.md#fan-out) |
| "one column per year / status / month" | `SUM(CASE ...)` per column (pivot) | `GROUP BY` the year gives rows, not columns | [15.4](15-Classic-Interview-Patterns.md#pivot) |
| "the median" | `PERCENTILE_CONT` (PostgreSQL) or the two-middle-rows method | `AVG` is the mean, not the median | [15.5](15-Classic-Interview-Patterns.md#median) |

## Ranking and order { #ranking }

| The task says | Technique | The usual trap | Chapter |
| --- | --- | --- | --- |
| "the highest", "the most" (one row) | `ORDER BY ... DESC` + tie-break + `LIMIT 1`, or `= (SELECT MAX ...)` | ties: `LIMIT 1` hides the others | [2.7](02-Select-Where-Order-By-Limit.md#limit) |
| "the second highest", "the Nth largest" | `DENSE_RANK() = N`, or `DISTINCT ... OFFSET N-1` | returning a row when there is no Nth | [15.1](15-Classic-Interview-Patterns.md#nth-highest) |
| "top 3 in each ...", "best per ..." | `ROW_NUMBER` / `RANK` / `DENSE_RANK` with `PARTITION BY` in a CTE, filter outside | a window function in `WHERE` | [13.4](13-Window-Functions-Ranking.md#top-n) |
| "with ties", "equal values share a rank" | `RANK` (gaps) or `DENSE_RANK` (no gaps) | `ROW_NUMBER` cuts ties | [13.3](13-Window-Functions-Ranking.md#ties) |
| "the latest / most recent ... for each", "the first ... per" | `ROW_NUMBER() OVER (PARTITION BY key ORDER BY date DESC, id DESC) = 1` | no tie-break when two rows share a date | [13.5](13-Window-Functions-Ranking.md#latest) |
| "number the rows", "the first, second ... order" | `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` | no tie-break, so numbers change between runs | [13.2](13-Window-Functions-Ranking.md#row-number) |
| "quartile", "top 10 percent" | `NTILE(4)`, `PERCENT_RANK` | `NTILE` splits ties across buckets | [13.7](13-Window-Functions-Ranking.md#ntile) |

## Sequences and time { #time }

| The task says | Technique | The usual trap | Chapter |
| --- | --- | --- | --- |
| "compared with the previous", "change since", "growth" | `LAG(x) OVER (ORDER BY ...)` | no `PARTITION BY` when it is per customer | [14.1](14-Window-Functions-Lag-Lead-Running-Totals.md#lag-lead), [14.2](14-Window-Functions-Lag-Lead-Running-Totals.md#period-change) |
| "the next ...", "time until the next" | `LEAD` | the last row has no next: NULL | [14.1](14-Window-Functions-Lag-Lead-Running-Totals.md#lag-lead) |
| "so far", "cumulative", "running total", "to date" | `SUM(x) OVER (ORDER BY ... ROWS UNBOUNDED PRECEDING)` | the default `RANGE` frame adds tied rows together | [14.3](14-Window-Functions-Lag-Lead-Running-Totals.md#running), [14.4](14-Window-Functions-Lag-Lead-Running-Totals.md#frames) |
| "the first day the total reached ..." | running total in a CTE, then `MIN(date) WHERE total >= ...` | filtering before the running total | [14.3](14-Window-Functions-Lag-Lead-Running-Totals.md#running) |
| "7-day average", "moving average" | `AVG(x) OVER (ORDER BY d ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)` | missing days make 7 rows longer than 7 days | [14.5](14-Window-Functions-Lag-Lead-Running-Totals.md#moving) |
| "consecutive days", "in a row", "streak" | gaps and islands: `date - ROW_NUMBER()` per key, then group | duplicates in the data break the run: `DISTINCT` first | [15.3](15-Classic-Interview-Patterns.md#islands) |
| "per month", "per week" | `date_trunc` / `strftime`, or `SUBSTR(CAST(d AS TEXT), 1, 7)` | weeks start on Monday in one function and Sunday in another | [16.3](16-Dates-and-Time-Series.md#truncate) |
| "every day, including days with none" | a generated calendar (recursive CTE or `generate_series`) + `LEFT JOIN` | days with no rows simply vanish | [16.6](16-Dates-and-Time-Series.md#calendar) |
| "returned the next month", "retention", "cohort" | first date per customer, then join back on the later period | counting a customer twice in one month | [16.7](16-Dates-and-Time-Series.md#cohorts) |
| "how many days between" | `d2 - d1` (PostgreSQL), `julianday(d2) - julianday(d1)` (SQLite) | SQLite returns a decimal: cast it | [16.4](16-Dates-and-Time-Series.md#arithmetic) |
| "missing ids", "gaps in the sequence" | a generated series + anti join, or `LEAD(id) - id > 1` | the first and last gaps | [15 practice](15-Classic-Interview-Patterns.md#practice) |
| "everyone below this manager", "the whole chain" | recursive CTE | no stop condition on cyclic data | [11.3](11-CTEs-and-Recursive-CTEs.md#recursive) |

## Cleaning and duplicates { #cleaning }

| The task says | Technique | The usual trap | Chapter |
| --- | --- | --- | --- |
| "duplicates", "appears more than once" | `GROUP BY` all the identifying columns `HAVING COUNT(*) > 1` | grouping by too few columns | [15.2](15-Classic-Interview-Patterns.md#duplicates) |
| "keep one row per ...", "remove duplicates" | `ROW_NUMBER() ... = 1`, or `DISTINCT` on the whole row | `DISTINCT` on some columns keeps them all | [15.2](15-Classic-Interview-Patterns.md#duplicates) |
| "rows where the value changed" | `IS DISTINCT FROM` | `<>` misses a change from or to NULL | [6.3](06-Null-and-Three-Valued-Logic.md#is-null) |
| "the domain of the email", "the first word" | `SPLIT_PART` (PostgreSQL), `SUBSTR` + `INSTR` (SQLite) | positions start at 1 | [5.3](05-Text-Functions-and-Pattern-Matching.md#split) |
| "ignore case", "trim spaces" | `LOWER(TRIM(x))` on both sides | joining raw text that differs by a space | [5.4](05-Text-Functions-and-Pattern-Matching.md#trim-replace) |
| "in one string, separated by commas" | `STRING_AGG(x, ', ' ORDER BY x)` | no `ORDER BY` inside: random order | [5.8](05-Text-Functions-and-Pattern-Matching.md#string-agg) |

## When two techniques both work { #scaling }

Hidden tests can include a large table, and some correct answers slow down sharply as a table grows. The short
version:

- A **correlated subquery** in `SELECT` or `WHERE` ("the average of this row's own department") can run once per
  row. A **window function** (`AVG(...) OVER (PARTITION BY ...)`) or a join to a grouped CTE reads the table once.
  On a large table, prefer the window or the join.
- **`NOT EXISTS`** and **`LEFT JOIN ... IS NULL`** are both fine on modern databases; `NOT IN` is the one to avoid,
  for correctness first.
- A **self join on a date range** ("orders within 7 days of each other") grows with the square of the rows per key;
  `LAG` / `LEAD` grows with the rows.
- **`ORDER BY ... LIMIT`** to find a maximum sorts everything unless an index helps; `MAX()` or a window does not.

[Chapter 26](26-Making-Slow-Queries-Fast.md) times these forms on a large table.

**Next:** practise the recognition on [practice set A](30-Practice-Set-A.md), then the test-style tasks in the
[Codility test prep](../../interview/codility/index.md) guide.
