# SQL cheat sheet

*The whole language on one page, for coming back to SQL after a while. Every query here runs on the
[sample shop](sample-database.md) and was checked on PostgreSQL and SQLite; the line under each says so. Where the two
differ, both are given. The chapter number at each heading leads to the full story.*

## The shape of a query (ch. [2](02-Select-Where-Order-By-Limit.md), [3](03-The-Order-a-Query-Runs-In.md)) { #shape }

```text
SELECT   columns, expressions, aggregates        -- 5. pick and compute the output columns
FROM     table JOIN table ON condition           -- 1. find and join the rows
WHERE    condition on single rows                -- 2. keep rows
GROUP BY columns                                 -- 3. make one group per value
HAVING   condition on groups                     -- 4. keep groups
ORDER BY columns [ASC|DESC]                      -- 6. sort
LIMIT    n OFFSET m                              -- 7. cut (SQL Server: TOP n / OFFSET ... FETCH)
```

The numbers are the order the database works in. That is why a SELECT alias can't be used in WHERE (it doesn't
exist yet) but can be used in ORDER BY.

## Filtering (ch. [2](02-Select-Where-Order-By-Limit.md), [5](05-Text-Functions-and-Pattern-Matching.md), [6](06-Null-and-Three-Valued-Logic.md)) { #filter }

<!-- sql quiet -->
```sql
SELECT name, price
FROM products
WHERE price BETWEEN 10 AND 30          -- both ends included
  AND category IN ('Home', 'Office')
  AND name LIKE '%a%'                  -- % any run of characters, _ exactly one
  AND category IS NOT NULL             -- never "= NULL"
ORDER BY price DESC, name
LIMIT 3;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both (3 rows).</p>
<!-- /result -->

`LIKE` is case-sensitive in PostgreSQL (`ILIKE` ignores case) but not, for plain English letters, in SQLite.

## NULL (ch. [6](06-Null-and-Three-Valued-Logic.md)) { #null }

<!-- sql quiet -->
```sql
SELECT name,
       COALESCE(email, 'no email')   AS email_or_note,   -- first non-NULL
       NULLIF(city, 'Toronto')       AS city_not_toronto -- NULL when equal
FROM customers;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both (10 rows).</p>
<!-- /result -->

Any comparison with NULL is unknown, and WHERE keeps only true. `x NOT IN (list with a NULL)` is never true: use
`NOT EXISTS`.

## CASE (ch. [4](04-Expressions-Case-Numbers-Dates-Cast.md)) { #case }

<!-- sql quiet -->
```sql
SELECT name,
       CASE WHEN price >= 100 THEN 'high'
            WHEN price >= 20  THEN 'mid'
            ELSE 'low' END AS band
FROM products;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both (11 rows).</p>
<!-- /result -->

## Aggregates (ch. [7](07-Aggregation-Group-By-Having.md)) { #aggregate }

<!-- sql -->
```sql
SELECT department,
       COUNT(*)            AS people,     -- every row
       COUNT(salary)       AS paid,       -- rows where salary is not NULL
       SUM(salary)         AS payroll,
       ROUND(AVG(salary), 0) AS avg_salary, -- AVG skips NULLs
       MIN(hire_date)      AS first_hire
FROM employees
WHERE hire_date < '2026-01-01'           -- rows, before grouping
GROUP BY department
HAVING COUNT(*) >= 2                     -- groups, after grouping
ORDER BY payroll DESC;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| department | people | paid | payroll | avg_salary | first_hire |
| --- | --- | --- | --- | --- | --- |
| Engineering | 4 | 4 | 475000 | 118750 | 2020-01-15 |
| Sales | 4 | 4 | 315000 | 78750 | 2020-07-01 |
| Support | 2 | 2 | 127000 | 63500 | 2021-11-01 |
<!-- /result -->

Every column in SELECT is either in GROUP BY or inside an aggregate. `COUNT(DISTINCT x)` counts different values.
Conditional counts: `SUM(CASE WHEN status = 'shipped' THEN 1 ELSE 0 END)`.

## Joins (ch. [8](08-Joins-Inner-Left-Right-Full-Cross.md), [9](09-Self-Semi-and-Anti-Joins.md)) { #joins }

<!-- sql quiet -->
```sql
SELECT c.name, o.order_id
FROM customers c
LEFT JOIN orders o
       ON o.customer_id = c.customer_id
      AND o.status = 'shipped'           -- a filter on the right table goes in ON, or the LEFT JOIN turns INNER
ORDER BY c.customer_id, o.order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both (16 rows).</p>
<!-- /result -->

| Join | Keeps |
| --- | --- |
| `INNER JOIN` | only pairs that match |
| `LEFT JOIN` | every left row; NULLs where no match |
| `RIGHT JOIN` | every right row (SQLite has it since 3.39) |
| `FULL JOIN` | every row from both (SQLite since 3.39; not in MySQL) |
| `CROSS JOIN` | every pair |

Rows with no match (anti join), the safe way:

<!-- sql quiet -->
```sql
SELECT c.name
FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id);
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both (1 row).</p>
<!-- /result -->

## Subqueries and CTEs (ch. [10](10-Subqueries.md), [11](11-CTEs-and-Recursive-CTEs.md)) { #cte }

<!-- sql -->
```sql
WITH order_totals AS (
  SELECT order_id, SUM(quantity * unit_price) AS total
  FROM order_items
  GROUP BY order_id
)
SELECT order_id, total
FROM order_totals
WHERE total > (SELECT AVG(total) FROM order_totals)
ORDER BY total DESC;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| order_id | total |
| --- | --- |
| 112 | 181.00 |
| 102 | 149.00 |
| 120 | 139.00 |
| 109 | 65.00 |
| 106 | 56.50 |
<!-- /result -->

## Window functions (ch. [13](13-Window-Functions-Ranking.md), [14](14-Window-Functions-Lag-Lead-Running-Totals.md)) { #window }

A window function computes over related rows **without** collapsing them into one.

<!-- sql -->
```sql
SELECT name, department, salary,
       ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC, name) AS rn,  -- 1,2,3,4 always
       RANK()       OVER (PARTITION BY department ORDER BY salary DESC) AS rnk,        -- 1,2,2,4 on ties
       DENSE_RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS drnk,       -- 1,2,2,3 on ties
       salary - LAG(salary) OVER (PARTITION BY department ORDER BY salary, name) AS up_from_prev,
       SUM(salary)  OVER (PARTITION BY department)                          AS dept_total
FROM employees
WHERE salary IS NOT NULL
ORDER BY department, salary DESC, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

| name | department | salary | rn | rnk | drnk | up_from_prev | dept_total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tom Becker | Engineering | 140000 | 1 | 1 | 1 | 20000 | 475000 |
| Priya Nair | Engineering | 120000 | 2 | 2 | 2 | 25000 | 475000 |
| Sam Lee | Engineering | 120000 | 3 | 2 | 2 | 0 | 475000 |
| Lucia Gomez | Engineering | 95000 | 4 | 4 | 3 | *NULL* | 475000 |
| Maya Rossi | Management | 180000 | 1 | 1 | 1 | *NULL* | 180000 |
| Omar Aziz | Sales | 110000 | 1 | 1 | 1 | 40000 | 315000 |
| Nina Berg | Sales | 70000 | 2 | 2 | 2 | 5000 | 315000 |
| Raj Patel | Sales | 70000 | 3 | 2 | 2 | 0 | 315000 |
| Zoe Martin | Sales | 65000 | 4 | 4 | 3 | *NULL* | 315000 |
| Kwame Mensah | Support | 75000 | 1 | 1 | 1 | 23000 | 127000 |
| Ella Novak | Support | 52000 | 2 | 2 | 2 | *NULL* | 127000 |
<!-- /result -->

`ROW_NUMBER` needs a tie-break (`, name` above) or tied rows get their numbers by luck. Top N per group: rank in a CTE, then `WHERE rnk <= N` outside (a window function can't go in WHERE).

Running total: `SUM(x) OVER (ORDER BY d ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`.

## Set operations (ch. [12](12-Set-Operations.md)) { #sets }

`UNION` (removes duplicates), `UNION ALL` (keeps them, faster), `INTERSECT`, `EXCEPT` (Oracle before 21c: `MINUS`).
The column counts and types must line up.

## Dates (ch. [16](16-Dates-and-Time-Series.md)) { #dates }

| Task | PostgreSQL | SQLite |
| --- | --- | --- |
| first day of the month | `date_trunc('month', d)::date` | `date(d, 'start of month')` |
| year, month as numbers | `EXTRACT(YEAR FROM d)` | `CAST(strftime('%Y', d) AS INTEGER)` |
| add 7 days | `d + 7` or `d + INTERVAL '7 days'` | `date(d, '+7 days')` |
| days between | `d2 - d1` | `julianday(d2) - julianday(d1)` |
| today | `CURRENT_DATE` | `date('now')` |

## Text (ch. [5](05-Text-Functions-and-Pattern-Matching.md)) { #text }

Both: `UPPER`, `LOWER`, `TRIM`, `LENGTH`, `REPLACE`, `SUBSTR(s, start, len)`, `s1 || s2`. PostgreSQL also has
`split_part`, `position`, `left`, `right`, `regexp_replace`, `string_agg`; SQLite has `instr` and `group_concat`.

## Changing data (ch. [17](17-Insert-Update-Delete-Merge.md)) { #change }

```text
INSERT INTO t (a, b) VALUES (1, 'x'), (2, 'y');
UPDATE t SET b = 'z' WHERE a = 1;                      -- no WHERE = every row
DELETE FROM t WHERE a = 2;
INSERT INTO t (a, b) VALUES (1, 'x')
  ON CONFLICT (a) DO UPDATE SET b = excluded.b;        -- upsert: PostgreSQL and SQLite
```

## The usual mistakes { #mistakes }

| Mistake | Fix |
| --- | --- |
| `WHERE col = NULL` | `WHERE col IS NULL` |
| `NOT IN (subquery)` where the subquery can return NULL | `NOT EXISTS` |
| Filtering the right table of a LEFT JOIN in WHERE | Move the condition into ON |
| `SUM` after joining to a "many" table | Aggregate first, then join |
| `7 / 2` expecting 3.5 | `7 * 1.0 / 2` |
| `LIMIT 1` for "the highest" when there are ties | `RANK()` / `DENSE_RANK()`, or `WHERE x = (SELECT MAX(x) ...)` |
| Window function in WHERE | Compute it in a CTE, filter outside |
| No ORDER BY when the order matters | Always finish with ORDER BY |
