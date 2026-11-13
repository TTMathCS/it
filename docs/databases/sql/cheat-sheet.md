# SQL cheat sheet

*Every part of SQL you need for a test, each with what it does, when you would use it, and a small example that
runs on the [sample shop](sample-database.md). Every example was checked on PostgreSQL and SQLite; the grey line
under it says so. Press **Run this** under an example to try it, change it, and run it again.*

!!! tip "How to read this page"
    Each section starts with one sentence on **what the tool is for**, then a table: **what it is**, **what it
    does**, and **when you reach for it**. Then a worked example: the question in plain words, the query, and its
    real result. The last line, **Learn it fully**, names the chapter that teaches it step by step.

    The examples use the shop's tables: `customers`, `products`, `orders` (one row per order), `order_items` (one
    row per product in an order), `employees`, `logins`, `payments` and `page_views`. Every column is described on
    [the sample database page](sample-database.md).

## The shape of a query { #shape }

**What it is for:** every question you ask a database is a `SELECT`. It has up to seven parts, always written in
this order.

```text
SELECT   columns, expressions, aggregates        -- 5. pick and compute the output columns
FROM     table JOIN table ON condition           -- 1. find and join the rows
WHERE    condition on single rows                -- 2. keep rows
GROUP BY columns                                 -- 3. make one group per value
HAVING   condition on groups                     -- 4. keep groups
ORDER BY columns [ASC|DESC]                      -- 6. sort
LIMIT    n OFFSET m                              -- 7. cut (SQL Server: TOP n / OFFSET ... FETCH)
```

| Part | What it does | When you use it |
| --- | --- | --- |
| `SELECT` | Chooses the columns of the answer, and can compute new ones (`price * 2 AS double_price`). | Always. |
| `FROM` | Names the table the rows come from. | Always, except for a quick calculation such as `SELECT 7 * 3`. |
| `JOIN ... ON` | Adds the matching rows of a second table. | The answer needs columns from two tables, such as a customer's name next to their order. |
| `WHERE` | Keeps only the rows that pass a test. | "Only shipped orders", "only 2026". |
| `GROUP BY` | Folds the rows into one row per value (per customer, per month). | Questions with "per", "for each", "how many", "total". |
| `HAVING` | Keeps only the groups that pass a test. | "Customers with **more than 2** orders": a test on a count or a sum. |
| `ORDER BY` | Sorts the answer. | Always when the task names an order; without it the order is luck. |
| `LIMIT` / `OFFSET` | Keeps the first `n` rows, after skipping `m`. | "The top 3", or one page of results. |

The numbers in the comments are the order the database **works** in. That is why a name you give in `SELECT`
(an alias) can't be used in `WHERE`: `WHERE` runs before `SELECT`, so the name does not exist yet. It can be
used in `ORDER BY`, which runs after.

**Learn it fully:** [2. SELECT, WHERE, ORDER BY, LIMIT](02-Select-Where-Order-By-Limit.md) and
[3. The order a query really runs in](03-The-Order-a-Query-Runs-In.md).

## Looking at a table, quotes, and laying out a query { #describe }

**What it is for:** finding out what a table holds before you query it, and writing queries you can read back.

| Write | What it does | When you use it |
| --- | --- | --- |
| `SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'orders' ORDER BY ordinal_position;` | Lists a table's columns and types (PostgreSQL, MySQL, SQL Server). | "Describe a table" in a Run box. `DESCRIBE orders` is MySQL only, and `\d orders` works only in the `psql` program. |
| `SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';` | Lists the tables. | "Which tables are there?" |
| `SELECT * FROM pragma_table_info('orders');` | SQLite's way to list the columns. | The same question on SQLite. |
| `SELECT * FROM orders LIMIT 5;` | A first look at a few rows, with the column names. | Any database, any time. |
| `'Tom Becker'` (single quotes) | A piece of text, a value. | Every text value: `WHERE name = 'Tom Becker'`. |
| `"Full name"` (double quotes) | A name: a column, table or alias. | Only a name with spaces, capitals or a reserved word: `AS "Full name"`. On PostgreSQL, `WHERE name = "Tom Becker"` fails with `column "Tom Becker" does not exist`. |
| `'O''Brien'` | A single quote inside text, written twice. | Names and words with an apostrophe. |

**Layout:** keywords in capitals, one clause per line, a name (`AS`) for every computed column, each `JOIN` on its own
line, the table's alias on every column when there are several tables. Two or three plain columns may stay on one
line; otherwise one column per line. The database ignores layout; you, finding a mistake under time pressure, do
not. Examples: [describe a table](sample-database.md#describe) and [how to lay out a query](02-Select-Where-Order-By-Limit.md#layout).

## Filtering rows: WHERE { #filter }

**What it is for:** keeping only the rows you want before anything else happens.

| Write | What it does | When you use it |
| --- | --- | --- |
| `=`, `<>`, `<`, `<=`, `>`, `>=` | Compare two values (`<>` means "not equal"; `!=` works too). | `status = 'shipped'`, `price > 20`. |
| `BETWEEN a AND b` | True when the value is from `a` to `b`, **both ends included**. | A range: prices 10 to 30, dates in one month. |
| `IN ('a', 'b')` | True when the value is one of a list. | Several allowed values, instead of a chain of `OR`s. |
| `LIKE 'pat'` | Text pattern: `%` is any run of characters (even none), `_` is exactly one. | "Name starts with A" (`'A%'`), "contains gmail" (`'%gmail%'`). |
| `ILIKE` (PostgreSQL) | `LIKE` that ignores upper and lower case. | Matching text typed by people. |
| `IS NULL`, `IS NOT NULL` | True when the value is missing, or present. | "Customers with no email". Never write `= NULL` (see NULL below). |
| `AND`, `OR`, `NOT` | Combine tests. `AND` is done before `OR`. | Put brackets around `OR`s: `WHERE a = 1 AND (b = 2 OR b = 3)`. |

**Example.** The three most expensive products priced from 10 to 30 in the Home or Office category whose name
contains the letter a:

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

**Learn it fully:** [2. SELECT, WHERE, ORDER BY, LIMIT](02-Select-Where-Order-By-Limit.md) and
[5. Text functions and pattern matching](05-Text-Functions-and-Pattern-Matching.md).

## NULL: a missing value { #null }

**What it is for:** `NULL` means "no value here": unknown, missing or not applicable (a customer who gave no
email). It is not 0 and not the empty text `''`. Most mistakes in SQL tests are about NULL, so know these by heart.

| Write | What it does | When you use it |
| --- | --- | --- |
| `x IS NULL` / `x IS NOT NULL` | The only correct test for a missing value. `x = NULL` is never true, not even when `x` is NULL. | "Orders with no customer", "products with a category". |
| `COALESCE(a, b, ...)` | Returns the first value in the list that is not NULL. | Show `0` instead of a missing total, or `'Unknown'` instead of a missing category. |
| `NULLIF(a, b)` | Returns NULL when `a` equals `b`, otherwise `a`. | Avoid dividing by zero: `total / NULLIF(count, 0)` gives NULL instead of an error. |
| `COUNT(*)` vs `COUNT(col)` | `COUNT(*)` counts rows; `COUNT(col)` counts only rows where `col` is not NULL. | "How many customers" vs "how many customers gave an email". |
| `SUM`, `AVG`, `MIN`, `MAX` | Skip NULLs. `AVG` divides by the count of non-NULL values. | Know it, so an average over missing values does not surprise you. |
| `ORDER BY x NULLS LAST` | Puts missing values at the end (PostgreSQL puts them **last** going up and **first** going down; SQLite the opposite). | When a task says where missing values go, or to get the same order on both. |

**What happens to NULL** in `DISTINCT`, `GROUP BY` and the counts (on `customers`, where one of the 10 has no city):

| Query | What happens to NULL | On `customers.city` |
| --- | --- | --- |
| `SELECT DISTINCT city` | kept, shown once | 8 rows: 7 cities and one NULL |
| `GROUP BY city` | kept, as one group | 8 groups |
| `COUNT(DISTINCT city)` | not counted | 7 |
| `COUNT(city)` | not counted | 9 |
| `COUNT(*)` | counted, it counts rows | 10 |

The query that shows all five: [DISTINCT and NULL](02-Select-Where-Order-By-Limit.md#distinct-null).

**Why `=` fails.** A comparison with NULL gives *unknown*, not true or false. `WHERE` keeps only rows where the
test is **true**, so rows with unknown disappear quietly. The same rule breaks `NOT IN`: if the list holds a NULL,
`x NOT IN (list)` is never true and the query returns nothing. Use `NOT EXISTS` instead (see Joins).

**Example.** Every customer with their email, or a note when they gave none, and their city, blanked out when it
is Toronto:

<!-- sql -->
```sql
SELECT name,
       COALESCE(email, 'no email')   AS email_or_note,   -- the first value that is not NULL
       NULLIF(city, 'Toronto')       AS city_not_toronto -- NULL when the city is Toronto
FROM customers
ORDER BY customer_id
LIMIT 5;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| name | email_or_note | city_not_toronto |
| --- | --- | --- |
| Ana Silva | ana@example.com | *NULL* |
| Ben Okafor | ben@example.com | Lagos |
| Chen Wei | no email | Shanghai |
| Dana Kim | dana@example.com | Seoul |
| Eli Cohen | eli@example.com | *NULL* |
<!-- /result -->

Eli Cohen has no city at all, so `city_not_toronto` is NULL on that row too: `NULLIF` of NULL is NULL.

**Learn it fully:** [6. NULL and three-valued logic](06-Null-and-Three-Valued-Logic.md).

## CASE: if-then-else inside a query { #case }

**What it is for:** making a new value from a rule, row by row. SQL has no `if` statement inside a query; `CASE`
is how you write one.

| Use | How it looks | When you use it |
| --- | --- | --- |
| Put values into bands | `CASE WHEN price >= 100 THEN 'high' WHEN price >= 20 THEN 'mid' ELSE 'low' END` | "Group products by price range", "label orders small or large". |
| Count only some rows | `SUM(CASE WHEN status = 'shipped' THEN 1 ELSE 0 END)` | Several counts side by side in one row (a "pivot"). |
| Sum only some rows | `SUM(CASE WHEN method = 'card' THEN amount ELSE 0 END)` | Revenue by payment method as columns. |
| Your own sort order | `ORDER BY CASE status WHEN 'pending' THEN 1 WHEN 'shipped' THEN 2 ELSE 3 END` | A task orders by status in an order that is not alphabetical. |

`CASE` checks the `WHEN`s from top to bottom and takes the **first** that is true, so put the strictest test
first. Without `ELSE`, a row that matches nothing gets NULL.

**Example.** Every product with its price band:

<!-- sql -->
```sql
SELECT name, price,
       CASE WHEN price >= 100 THEN 'high'
            WHEN price >= 20  THEN 'mid'     -- only reached when the price is under 100
            ELSE 'low' END AS band
FROM products
ORDER BY price DESC, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

| name | price | band |
| --- | --- | --- |
| Office chair | 149.00 | high |
| Monitor stand | 32.00 | mid |
| Tea kettle | 32.00 | mid |
| Gift card | 25.00 | mid |
| Desk lamp | 24.50 | mid |
| Wall clock | 24.50 | mid |
| Fountain pen | 18.00 | low |
| Plant pot | 12.25 | low |
| Bookend | 9.50 | low |
| Coffee mug | 8.75 | low |
| Notebook | 3.25 | low |
<!-- /result -->

**Learn it fully:** [4. Expressions: CASE, numbers, dates, CAST](04-Expressions-Case-Numbers-Dates-Cast.md).

## Numbers and types { #numbers }

**What it is for:** doing arithmetic without losing the decimals, and turning one type into another.

| Write | What it does | When you use it |
| --- | --- | --- |
| `7 / 2` | Gives **3** when both numbers are whole: integer division drops the decimals. | Watch for it in averages and percentages. |
| `7 * 1.0 / 2`, `7::numeric / 2` | Gives 3.5: one decimal number makes the whole division decimal. | Any share, rate or percentage. |
| `ROUND(x, 2)` | Rounds to 2 decimals. | When a task says "rounded to two decimal places". |
| `CAST(x AS type)`, `x::type` (PostgreSQL) | Changes the type: text to number, timestamp to date. | Comparing a text column with a number; removing the time from a timestamp. |
| `ABS`, `%` (or `MOD`), `CEIL`, `FLOOR` | Absolute value, remainder, round up, round down. | Differences of any sign; "every other row" (`id % 2 = 0`). |

**Example.** The share of shipped orders, the wrong way and the right way:

<!-- sql -->
```sql
SELECT COUNT(*)                                                   AS orders,
       SUM(CASE WHEN status = 'shipped' THEN 1 ELSE 0 END)        AS shipped,
       SUM(CASE WHEN status = 'shipped' THEN 1 ELSE 0 END) / COUNT(*)  AS share_wrong,   -- whole numbers: 0
       ROUND(SUM(CASE WHEN status = 'shipped' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS shipped_pct
FROM orders;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| orders | shipped | share_wrong | shipped_pct |
| --- | --- | --- | --- |
| 20 | 16 | 0 | 80.0 |
<!-- /result -->

**Learn it fully:** [4. Expressions: CASE, numbers, dates, CAST](04-Expressions-Case-Numbers-Dates-Cast.md).

## Aggregates: GROUP BY and HAVING { #aggregate }

**What it is for:** turning many rows into one number per group: totals, counts, averages, the first and the last.

| Write | What it does | When you use it |
| --- | --- | --- |
| `COUNT(*)` | Number of rows in the group. | "How many orders". |
| `COUNT(col)` | Number of rows where `col` is not NULL. | "How many have a salary". |
| `COUNT(DISTINCT col)` | Number of **different** values, **not counting NULL**. | "How many different customers ordered" (one customer with 3 orders counts once). `SELECT DISTINCT col` keeps NULL as one row, so it can return one row more ([DISTINCT and NULL](02-Select-Where-Order-By-Limit.md#distinct-null)). |
| `COUNT(1)` | The same as `COUNT(*)` (1 is never NULL); not faster. | Nothing new: write `COUNT(*)`. `SELECT 1` inside `EXISTS (...)` is a placeholder, not a count ([7.2](07-Aggregation-Group-By-Having.md#count-one)). |
| `SUM(col)`, `AVG(col)` | Total and average, skipping NULLs. | Revenue, average order size. |
| `MIN(col)`, `MAX(col)` | Smallest and largest; work on numbers, dates and text. | First order date, highest price. |
| `GROUP BY a, b` | One output row per different combination of `a` and `b`. | Any "per ..." or "for each ...". |
| `HAVING test` | Keeps groups, after grouping; can use aggregates. | "Departments with at least 2 people". |
| `WHERE test` | Keeps rows, **before** grouping; can't use aggregates. | "Count only orders from 2026". |
| `COUNT(*) FILTER (WHERE ...)` (PostgreSQL) | Counts only the rows that pass the test. | Same as `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`, shorter. |

The rule that catches everyone: every column in `SELECT` must either be in `GROUP BY` or sit inside an aggregate.
PostgreSQL stops with an error when it is not; SQLite quietly picks a value from some row.

**Example.** For each department with at least two people hired before 2026: the head count, how many have a
salary, the payroll, the average salary and the first hire date.

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

**Learn it fully:** [7. Aggregation: GROUP BY and HAVING](07-Aggregation-Group-By-Having.md).

## Joins: rows from two tables side by side { #joins }

**What it is for:** answers that need columns from more than one table. A join pairs each row of one table with
the rows of the other that match the `ON` condition, usually a key: `ON o.customer_id = c.customer_id`.

| Join | Keeps | When you use it |
| --- | --- | --- |
| `INNER JOIN` (or just `JOIN`) | Only pairs that match. A row with no partner disappears. | Orders with their customer's name, when every order has a customer. |
| `LEFT JOIN` | Every row of the left (first) table; NULLs in the right table's columns where there is no match. | "Every customer, **including those with no orders**", with 0 orders shown as 0 via `COALESCE`. |
| `RIGHT JOIN` | Every row of the right table. (SQLite has it since 3.39.) | Rarely: swap the tables and use `LEFT JOIN` instead, it reads better. |
| `FULL JOIN` | Every row from both, matched where possible. (SQLite since 3.39; not in MySQL.) | Comparing two lists: rows only in A, only in B, or in both (ledger vs bank). |
| `CROSS JOIN` | Every row paired with every row. | Building a grid: every customer × every month, then `LEFT JOIN` the real data onto it. |
| Self join | A table joined to itself under two names. | Employee next to their manager (`e.manager_id = m.employee_id`). |
| Semi join: `WHERE EXISTS (...)` | Rows that have **at least one** match, each kept once. | "Customers who ordered something". |
| Anti join: `WHERE NOT EXISTS (...)` | Rows that have **no** match. | "Customers who never ordered", "products never sold". |

Two traps: (1) a test on the right table of a `LEFT JOIN` belongs in `ON`; in `WHERE` it removes the NULL rows and
the `LEFT JOIN` behaves like an `INNER JOIN`. (2) Joining a "many" table multiplies rows: one order with three
items appears three times, so a `SUM` over the order's own columns counts it three times. Aggregate first, then
join.

**Example.** Customers 6 to 10, each with their shipped orders. Ivan Petrov has none and still appears, with
NULL as the order:

<!-- sql -->
```sql
SELECT c.name, o.order_id
FROM customers c
LEFT JOIN orders o
       ON o.customer_id = c.customer_id
      AND o.status = 'shipped'           -- a filter on the right table goes in ON, or the LEFT JOIN turns INNER
WHERE c.customer_id BETWEEN 6 AND 10     -- a filter on the LEFT table is fine in WHERE
ORDER BY c.customer_id, o.order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| name | order_id |
| --- | --- |
| Farah Haddad | 109 |
| Gus Novak | 111 |
| Hana Sato | 114 |
| Ivan Petrov | *NULL* |
| Ana Silva | 117 |
<!-- /result -->

**Example: an anti join.** Customers who never placed an order:

<!-- sql -->
```sql
SELECT c.name
FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id)
ORDER BY c.name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| name |
| --- |
| Ivan Petrov |
<!-- /result -->

`SELECT 1` inside `EXISTS` is a habit: `EXISTS` only asks whether a row exists, not what is in it. On SQLite with no
index on `orders.customer_id`, `NOT EXISTS` runs once per customer and can time out on a big table;
`LEFT JOIN orders o ON o.customer_id = c.customer_id WHERE o.order_id IS NULL` gives the same rows and stays fast
on both ([26.4](26-Making-Slow-Queries-Fast.md#anti-join)).

**Learn it fully:** [8. Joins](08-Joins-Inner-Left-Right-Full-Cross.md) and
[9. Self, semi and anti joins](09-Self-Semi-and-Anti-Joins.md).

## Subqueries and CTEs: a query in steps { #cte }

**What it is for:** breaking a hard question into small steps, each one a query you can run and check on its own.

| Write | What it does | When you use it |
| --- | --- | --- |
| Scalar subquery `(SELECT AVG(price) FROM products)` | A query that returns one value, used like a number. | "Products above the average price". |
| `IN (SELECT ...)` | True when the value is in the subquery's list. | "Orders of customers from Canada". (Use `EXISTS` when NULLs may appear and you need `NOT`.) |
| `EXISTS (SELECT ...)` | True when the subquery finds any row. | Semi and anti joins (see Joins). |
| Subquery in `FROM` | A query used as a table: `FROM (SELECT ...) AS t`. | Aggregate first, then join or filter on the result. |
| `WITH name AS (SELECT ...)` (a CTE) | Names a step; later steps and the final query use it like a table. | Any task with more than one step: it reads top to bottom and you can run each step. |
| `WITH RECURSIVE` | A step that refers to itself, repeating until no new rows come. | Walking a tree: every manager above an employee; a list of every date in a range. |

A **correlated** subquery refers to the outer row (`WHERE o.customer_id = c.customer_id` inside it), so it runs
once per outer row: fine on small tables, slow on large ones. A join or a window function usually does the same work
in one pass.

**Example.** Orders whose total is above the average order total. Step 1 computes each order's total; the final
query compares each total with the average of step 1:

<!-- sql -->
```sql
WITH order_totals AS (                    -- step 1: one row per order, with its total
  SELECT order_id, SUM(quantity * unit_price) AS total
  FROM order_items
  GROUP BY order_id
)
SELECT order_id, total                    -- step 2: keep the orders above the average total
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

**Learn it fully:** [10. Subqueries](10-Subqueries.md) and [11. CTEs and recursive CTEs](11-CTEs-and-Recursive-CTEs.md).

## Window functions: compare a row with its neighbours { #window }

**What it is for:** a calculation over a group of related rows that **keeps every row** (`GROUP BY` folds them into
one). Use it whenever the answer has one row per item but needs to know about the other items: its rank, the
previous value, a running total, its share of the group.

Every window function has `OVER (...)`, which says which rows it looks at:

| Part of `OVER` | What it does | Example |
| --- | --- | --- |
| `PARTITION BY col` | Splits the rows into groups; the function restarts in each. Leave it out for one group of all rows. | `PARTITION BY department`: rank inside each department. |
| `ORDER BY col` | The order inside each group: who is first, who is "previous". | `ORDER BY salary DESC`: the best paid is number 1. |
| `ROWS BETWEEN ... AND ...` | The frame: which rows around the current one a `SUM` or `AVG` adds up. | `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW`: the last 7 rows, for a 7-day average. |

| Function | What it does | When you use it |
| --- | --- | --- |
| `ROW_NUMBER()` | 1, 2, 3, 4 in the window's order; ties get different numbers. | Exactly one row per group: "the latest order of each customer" (`WHERE rn = 1`), or removing duplicates. |
| `RANK()` | 1, 2, 2, 4: ties share a number, then a gap. | "Top 3 with ties included", like a sports ranking. |
| `DENSE_RANK()` | 1, 2, 2, 3: ties share a number, no gap. | "The second highest **different** salary". |
| `LAG(col)` | The value of `col` in the **previous** row of the window. | Change from the day or month before; the gap since the last login. |
| `LEAD(col)` | The value in the **next** row. | Time until the next event; "what came after". |
| `SUM(col) OVER (ORDER BY ...)` | A running total. | Cumulative revenue, a balance after each payment. |
| `SUM(col) OVER (PARTITION BY g)` | The group's total on every row. | Each row's share of its group: `amount * 100.0 / SUM(amount) OVER (PARTITION BY g)`. |
| `FIRST_VALUE(col)`, `LAST_VALUE(col)` | The first or last value of the window. | Each customer's first product bought, on every row of theirs. |
| `NTILE(4)` | Splits the rows into 4 nearly equal buckets: 1 to 4. | Quartiles: "the top 25% of customers". |

**Example: all of them at once.** Every paid employee with their place in their department (three ways of
numbering), how much more they earn than the next lower salary, and the department's payroll:

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

Read the result: Priya and Sam earn the same, so `ROW_NUMBER` still gives them 2 and 3 (the tie is broken by name),
`RANK` gives both 2 and skips 3, `DENSE_RANK` gives both 2 and goes on with 3. `LAG` is NULL on the lowest salary
of each department: there is no row before it.

**Example: top N per group.** The best-paid person in each department. A window function can't go in `WHERE`
(`WHERE` runs before the window is computed), so number the rows in a CTE and filter outside:

<!-- sql -->
```sql
WITH ranked AS (
  SELECT name, department, salary,
         ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC, name) AS rn
  FROM employees
  WHERE salary IS NOT NULL
)
SELECT department, name, salary
FROM ranked
WHERE rn = 1                              -- use RANK() and rn <= N to keep ties, or for the top N
ORDER BY department;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| department | name | salary |
| --- | --- | --- |
| Engineering | Tom Becker | 140000 |
| Management | Maya Rossi | 180000 |
| Sales | Omar Aziz | 110000 |
| Support | Kwame Mensah | 75000 |
<!-- /result -->

**Example: a running total.** Revenue per order date and the total so far:

<!-- sql -->
```sql
WITH daily AS (
  SELECT o.order_date, SUM(oi.quantity * oi.unit_price) AS revenue
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  GROUP BY o.order_date
)
SELECT order_date, revenue,
       SUM(revenue) OVER (ORDER BY order_date
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS revenue_so_far
FROM daily
ORDER BY order_date
LIMIT 6;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

| order_date | revenue | revenue_so_far |
| --- | --- | --- |
| 2026-01-03 | 183.25 | 183.25 |
| 2026-01-15 | 33.75 | 217.00 |
| 2026-01-20 | 32.00 | 249.00 |
| 2026-01-28 | 24.50 | 273.50 |
| 2026-02-02 | 93.25 | 366.75 |
| 2026-02-10 | 50.00 | 416.75 |
<!-- /result -->

`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` means "from the first row up to this one". Without it, a `SUM`
with `ORDER BY` uses `RANGE`, which adds all rows with the **same** date at once; with one row per date (as here)
both give the same answer.

**Learn it fully:** [13. Window functions: ranking](13-Window-Functions-Ranking.md) and
[14. Window functions: LAG, LEAD and running totals](14-Window-Functions-Lag-Lead-Running-Totals.md).

## Set operations: stacking two results { #sets }

**What it is for:** combining the rows of two queries that return the same columns, one list on top of the other.

| Write | What it does | When you use it |
| --- | --- | --- |
| `UNION` | Rows in either result, duplicates removed. | One list of "every city we sell to or buy from". |
| `UNION ALL` | Rows of both, duplicates kept; faster (no duplicate check). | Stacking two tables of events (web and app clicks) before counting. |
| `INTERSECT` | Rows in **both** results. | "Customers who bought in 2025 **and** in 2026". |
| `EXCEPT` (Oracle before 21c: `MINUS`) | Rows in the first result but **not** in the second. | "Customers who never ordered", a check that two tables hold the same rows. |

Both queries must return the same number of columns, in the same order, with types that match. The column names
come from the first query; one `ORDER BY` at the very end sorts the combined result.

**Example.** Customers who have never ordered, with `EXCEPT` (compare the anti join above):

<!-- sql -->
```sql
SELECT customer_id FROM customers
EXCEPT
SELECT customer_id FROM orders
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| customer_id |
| --- |
| 9 |
<!-- /result -->

`EXCEPT` treats two NULLs as equal, so a NULL `customer_id` in `orders` does no harm here, unlike `NOT IN`.

**Learn it fully:** [12. UNION, INTERSECT, EXCEPT](12-Set-Operations.md).

## Dates { #dates }

**What it is for:** grouping by day, week or month, and measuring time between two events. Dates are where
PostgreSQL and SQLite differ most: SQLite stores dates as text `'2026-01-31'` and uses functions on it.

| Task | PostgreSQL | SQLite | When you use it |
| --- | --- | --- | --- |
| first day of the month | `date_trunc('month', d)::date` | `date(d, 'start of month')` | Group by month and still have a date. |
| month as text `'2026-01'` | `to_char(d, 'YYYY-MM')` | `strftime('%Y-%m', d)` | A task asks for the month in that format. |
| year, month as numbers | `EXTRACT(YEAR FROM d)` | `CAST(strftime('%Y', d) AS INTEGER)` | "Orders in 2026", "per month number". |
| add 7 days | `d + 7` or `d + INTERVAL '7 days'` | `date(d, '+7 days')` | "Within 7 days of signing up". |
| days between | `d2 - d1` (a whole number) | `julianday(d2) - julianday(d1)` | Days from signup to first order. |
| today | `CURRENT_DATE` | `date('now')` | Ages and "in the last 30 days". (Tests usually give a fixed date instead.) |
| a timestamp's date | `ts::date` | `date(ts)` | Group events (`paid_at`, `viewed_at`) by day. |

**Example.** Orders per month:

<!-- sql pg -->
```sql
SELECT to_char(order_date, 'YYYY-MM') AS month, COUNT(*) AS orders
FROM orders
GROUP BY to_char(order_date, 'YYYY-MM')
ORDER BY month;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

| month | orders |
| --- | --- |
| 2026-01 | 5 |
| 2026-02 | 6 |
| 2026-03 | 6 |
| 2026-04 | 3 |
<!-- /result -->

The same on SQLite:

<!-- sql sqlite same -->
```sql
SELECT strftime('%Y-%m', order_date) AS month, COUNT(*) AS orders
FROM orders
GROUP BY strftime('%Y-%m', order_date)
ORDER BY month;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 4 rows.</p>

| month | orders |
| --- | --- |
| 2026-01 | 5 |
| 2026-02 | 6 |
| 2026-03 | 6 |
| 2026-04 | 3 |
<!-- /result -->

A month with no orders does not appear at all. When a task wants every month, build the list of months first
(`generate_series` in PostgreSQL, a recursive CTE in SQLite) and `LEFT JOIN` the counts onto it.

**Learn it fully:** [16. Dates and time series](16-Dates-and-Time-Series.md).

## Text { #text }

**What it is for:** cleaning, cutting and joining text: names, emails, codes.

| Write | What it does | When you use it |
| --- | --- | --- |
| `UPPER(s)`, `LOWER(s)` | All capitals, all small letters. | Comparing text whatever the case: `LOWER(email) = 'ana@example.com'`. |
| `TRIM(s)` | Removes spaces at both ends. | Data typed by people, `' Toronto '`. |
| `LENGTH(s)` | Number of characters. | "Codes that are not 6 characters long". |
| `SUBSTR(s, start, len)` | Part of the text; the first character is 1. | The first 3 characters of a postcode. |
| `REPLACE(s, 'a', 'b')` | Replaces every `a` with `b`. | Removing dashes from phone numbers. |
| <code>s1 &#124;&#124; s2</code> | Joins two texts. (NULL in, NULL out.) | <code>first_name &#124;&#124; ' ' &#124;&#124; last_name</code>. |
| `split_part(s, '@', 2)` (PostgreSQL) | The 2nd piece when cut at `@`. | An email's domain. SQLite: `substr(s, instr(s, '@') + 1)`. |
| `strpos(s, 'x')` (PostgreSQL), `instr(s, 'x')` (SQLite) | Position of `x` in `s`, 0 if absent. | Cutting text at a character. |
| `left(s, n)`, `right(s, n)`, `regexp_replace` (PostgreSQL) | First or last `n` characters; replace by a pattern. | Fixed-format codes; cleaning messy text. |
| `STRING_AGG(x, ', ' ORDER BY x)` | Joins a group's values into one text (an aggregate). (SQLite from 3.44; older SQLite: `group_concat`.) | "List the products of each order in one cell". |

`LIKE` ignores case on SQLite only: write `LOWER(x) LIKE '...'` for the same rows on both.

**Example.** Each customer's email domain:

<!-- sql pg -->
```sql
SELECT name, email, split_part(email, '@', 2) AS domain
FROM customers
WHERE email IS NOT NULL
ORDER BY customer_id
LIMIT 4;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

| name | email | domain |
| --- | --- | --- |
| Ana Silva | ana@example.com | example.com |
| Ben Okafor | ben@example.com | example.com |
| Dana Kim | dana@example.com | example.com |
| Eli Cohen | eli@example.com | example.com |
<!-- /result -->

**Learn it fully:** [5. Text functions and pattern matching](05-Text-Functions-and-Pattern-Matching.md).

## Changing data { #change }

**What it is for:** adding, changing and removing rows. Coding tests rarely ask for it; pipeline interviews often do.

| Write | What it does | When you use it |
| --- | --- | --- |
| `INSERT INTO t (a, b) VALUES (1, 'x'), (2, 'y');` | Adds rows. | Loading data, adding test rows of your own. |
| `INSERT INTO t (a, b) SELECT ...` | Adds the rows a query returns. | Copying the result of a query into a table. |
| `UPDATE t SET b = 'z' WHERE a = 1;` | Changes rows that pass the test. **No `WHERE` = every row.** | Fixing a value, marking rows as processed. |
| `DELETE FROM t WHERE a = 2;` | Removes rows. **No `WHERE` = every row.** | Removing bad or duplicate rows. |
| `INSERT ... ON CONFLICT (a) DO UPDATE SET b = excluded.b` | An "upsert": insert, or update the row that already has this key. `excluded` is the row you tried to insert. | Loading a file again without making duplicates. PostgreSQL and SQLite; other databases use `MERGE`. |

```text
INSERT INTO t (a, b) VALUES (1, 'x'), (2, 'y');
UPDATE t SET b = 'z' WHERE a = 1;                      -- no WHERE = every row
DELETE FROM t WHERE a = 2;
INSERT INTO t (a, b) VALUES (1, 'x')
  ON CONFLICT (a) DO UPDATE SET b = excluded.b;        -- upsert: PostgreSQL and SQLite
```

Before an `UPDATE` or `DELETE`, run the same `WHERE` in a `SELECT` to see which rows it touches.

**Learn it fully:** [17. INSERT, UPDATE, DELETE, MERGE](17-Insert-Update-Delete-Merge.md).

## Answering a test task { #test-output }

A checker compares your rows with its own. On Codility's practice SQL tasks (checked 11 Nov 2026) the column
**order** matters and the column names do not. So:

1. Return **exactly** the columns asked for, in the order asked, and nothing else (no `SELECT *`, no helper column).
2. When the task gives an order, `ORDER BY` it, and add a **tie-breaker** (usually the key) so the order is unique.
3. Match the requested format: rounding (`ROUND(x, 2)`), text such as `'YYYY-MM'`, 0 instead of NULL when asked
   (`COALESCE`).
4. Check the edge cases the hidden tests will have: NULLs, ties, empty groups, duplicates, an empty table.
5. Write it so it runs on PostgreSQL; it will then almost always run on SQLite too ([chapter 3](03-The-Order-a-Query-Runs-In.md#differences)).

Not sure which technique a task wants? [Which technique does this wording ask for?](which-technique.md) maps task
phrases to patterns and chapters.

## The usual mistakes { #mistakes }

| Mistake | Why it is wrong | Fix |
| --- | --- | --- |
| `WHERE col = NULL` | A comparison with NULL is never true, so no row is kept. | `WHERE col IS NULL` |
| `NOT IN (subquery)` where the subquery can return NULL | One NULL in the list makes `NOT IN` unknown for every row: the answer is empty. | `NOT EXISTS`, or `LEFT JOIN ... IS NULL` on SQLite |
| Filtering the right table of a LEFT JOIN in WHERE | The unmatched rows have NULL there, so WHERE removes them: an inner join in disguise. | Move the condition into ON |
| `SUM` after joining to a "many" table | Each row is repeated once per match, so it is added several times. | Aggregate first, then join |
| `7 / 2` expecting 3.5 | Two whole numbers give whole-number division. | `7 * 1.0 / 2` |
| `LIMIT 1` for "the highest" when there are ties | Only one of the tied rows comes back, and which one is luck. | `RANK()` / `DENSE_RANK()`, or `WHERE x = (SELECT MAX(x) ...)` |
| Window function in WHERE | WHERE runs before window functions are computed. | Compute it in a CTE, filter outside |
| No ORDER BY when the order matters | Without it the database returns rows in any order it likes. | Always finish with ORDER BY |
| `COUNT(*)` with a LEFT JOIN, for "how many orders" | A customer with no orders still has one row (with NULLs), so the count is 1. | `COUNT(o.order_id)`: counts only real matches |
