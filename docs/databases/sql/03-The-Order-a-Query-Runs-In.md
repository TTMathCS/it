# 3. The order a query really runs in

*You write `SELECT` first, but the database works it out almost last. Knowing the real order of the clauses explains
a whole family of errors at once: why an alias works in `ORDER BY` but not in `WHERE`, why `COUNT(*)` cannot go in
`WHERE`, and why a window function's result has to be filtered in an outer query. It is also a favourite interview
question in its own right.*

!!! abstract "In this chapter"
    **You will learn:**

    - the logical order of the clauses, and how to remember it
    - what each step can see, and why an alias is unknown in `WHERE`
    - `WHERE` (rows) versus `HAVING` (groups), from the order alone
    - why window functions cannot be filtered in the same query, and the fix
    - where PostgreSQL and SQLite differ, so an answer that works in one does not fail in the other
    - the difference between the logical order and what the database really does

    **You need:** [chapter 2](02-Select-Where-Order-By-Limit.md). Grouping and joins appear here only as names;
    chapters 7 and 8 teach them.

## 3.1 Written order, run order { #order }

The order you **write** a query in:

```text
SELECT ... FROM ... JOIN ... WHERE ... GROUP BY ... HAVING ... ORDER BY ... LIMIT ...
```

The order the database **works it out** in (the logical order):

```text
1. FROM and JOIN    which tables, joined into one big set of rows
2. WHERE            keep the rows that pass
3. GROUP BY         put the remaining rows into groups
4. HAVING           keep the groups that pass
5. SELECT           compute the output columns and window functions; give them their aliases
                    (aggregates were already worked out per group in step 3)
6. DISTINCT         remove duplicate output rows
7. ORDER BY         sort
8. LIMIT / OFFSET   cut
```

Each step only sees what the steps before it produced. Everything in this chapter follows from that one rule.

!!! tip "Interview tip: say it in one breath"
    "FROM, WHERE, GROUP BY, HAVING, SELECT, ORDER BY, LIMIT." When asked "why can't I use my alias in WHERE?", the
    answer is: because `WHERE` runs before `SELECT`, so the alias does not exist yet.

## 3.2 An alias does not exist in WHERE { #alias-where }

`line_value` is created in step 5, so step 2 cannot see it:

<!-- sql pgerror -->
```sql
SELECT order_id, product_id, quantity * unit_price AS line_value
FROM order_items
WHERE line_value > 100;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>column "line_value" does not exist</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 3 rows.</p>
<!-- /result -->

PostgreSQL follows the rule. SQLite bends it and looks up the alias, so the same query runs there. That makes it
dangerous: an answer tested on SQLite fails on PostgreSQL, SQL Server and Oracle. (MySQL refuses it too.) Write the
expression again, or compute it in an inner query and filter outside:

**Task:** List the order lines worth more than 100 (quantity times unit price): order id, product id and `line_value`, by order id.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT order_id, product_id, quantity * unit_price AS line_value
    FROM order_items
    WHERE quantity * unit_price > 100
    ORDER BY order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | order_id | product_id | line_value |
    | --- | --- | --- |
    | 102 | 6 | 149.00 |
    | 112 | 6 | 149.00 |
    | 120 | 6 | 139.00 |
    <!-- /result -->

<!-- sql same -->
```sql
WITH lines AS (
  SELECT order_id, product_id, quantity * unit_price AS line_value
  FROM order_items
)
SELECT order_id, product_id, line_value
FROM lines
WHERE line_value > 100
ORDER BY order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 3 rows.</p>

| order_id | product_id | line_value |
| --- | --- | --- |
| 102 | 6 | 149.00 |
| 112 | 6 | 149.00 |
| 120 | 6 | 139.00 |
<!-- /result -->

The second form, a **CTE** (`WITH ... AS`), names a step so the next one can use it. It is the general fix for
"I need to filter on something computed in SELECT", and [chapter 11](11-CTEs-and-Recursive-CTEs.md) covers it fully.

`ORDER BY` runs after `SELECT`, so there the alias works on every database:

**Task:** Show the 3 most valuable order lines: order id, product id and `line_value`, highest first (ties by order id, then product id).

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT order_id, product_id, quantity * unit_price AS line_value
    FROM order_items
    ORDER BY line_value DESC, order_id, product_id
    LIMIT 3;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | order_id | product_id | line_value |
    | --- | --- | --- |
    | 102 | 6 | 149.00 |
    | 112 | 6 | 149.00 |
    | 120 | 6 | 139.00 |
    <!-- /result -->

## 3.3 Aggregates cannot go in WHERE { #aggregate-where }

`WHERE` decides which rows go into the groups; the groups' counts and sums do not exist until after step 3. So a
condition on an aggregate is an error on every database:

<!-- sql error -->
```sql
SELECT customer_id, COUNT(*) AS orders
FROM orders
WHERE COUNT(*) >= 3
GROUP BY customer_id;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>aggregate functions are not allowed in WHERE</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>misuse of aggregate: COUNT()</code></p>
<!-- /result -->

A condition on a group belongs in `HAVING`, step 4, which runs after grouping:

**Task:** List the customers with 3 or more orders: customer id and number of orders, by customer id.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT customer_id, COUNT(*) AS orders
    FROM orders
    GROUP BY customer_id
    HAVING COUNT(*) >= 3
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | customer_id | orders |
    | --- | --- |
    | 1 | 5 |
    | 2 | 3 |
    <!-- /result -->

A condition on single rows belongs in `WHERE`, even when the query also groups. "Customers with at least two
**shipped** orders" filters rows by status first, then groups:

**Task:** List the customers with at least 2 shipped orders: customer id and number of shipped orders, by customer id.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT customer_id, COUNT(*) AS shipped_orders
    FROM orders
    WHERE status = 'shipped'
    GROUP BY customer_id
    HAVING COUNT(*) >= 2
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_id | shipped_orders |
    | --- | --- |
    | 1 | 5 |
    | 2 | 2 |
    | 4 | 2 |
    <!-- /result -->

`HAVING` can only see what exists after grouping: the grouped columns and aggregates. Using the alias `orders` in
`HAVING` (`HAVING orders >= 3`) is the same alias problem as in `WHERE`: SQLite and MySQL accept it, PostgreSQL does
not. Repeat the aggregate. [Chapter 7](07-Aggregation-Group-By-Having.md#having) has more on `WHERE` versus `HAVING`.

## 3.4 Window functions run in SELECT { #window-order }

A **window function** such as `ROW_NUMBER() OVER (...)` is computed in step 5, alongside the other `SELECT`
expressions ([chapter 13](13-Window-Functions-Ranking.md) introduces them). That puts it after `WHERE` and `HAVING`,
so neither can filter on it:

<!-- sql error -->
```sql
SELECT name, price
FROM products
WHERE ROW_NUMBER() OVER (ORDER BY price DESC, name) <= 3;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>window functions are not allowed in WHERE</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>misuse of window function ROW_NUMBER()</code></p>
<!-- /result -->

The fix is the same as for an alias: compute it in an inner query, filter in the outer one.

**Task:** Show the 3 most expensive products (ties by name) using `ROW_NUMBER`: name and price, in rank order.

??? success "Solution"

    <!-- sql -->
    ```sql
    WITH ranked AS (
      SELECT name, price, ROW_NUMBER() OVER (ORDER BY price DESC, name) AS rn
      FROM products
    )
    SELECT name, price
    FROM ranked
    WHERE rn <= 3
    ORDER BY rn;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | name | price |
    | --- | --- |
    | Office chair | 149.00 |
    | Monitor stand | 32.00 |
    | Tea kettle | 32.00 |
    <!-- /result -->

This pattern, "rank in a CTE, filter outside", is behind most "top N per group" answers. Some databases
(Snowflake, BigQuery, Databricks, DuckDB) add a `QUALIFY` clause that filters on a window function directly;
PostgreSQL and SQLite do not have it.

It also explains a subtle point: because `WHERE` runs first, the window only sees the rows that passed `WHERE`.
Ranking products "within the Office category" by filtering in `WHERE` ranks four products, not eleven.

## 3.5 DISTINCT, ORDER BY and LIMIT come last { #last-steps }

`DISTINCT` (step 6) works on the finished output rows, which is why it applies to the whole row. `ORDER BY` (step 7)
then sorts, and `LIMIT` (step 8) cuts the sorted result; that is why `LIMIT` without `ORDER BY` gives arbitrary rows.

One consequence trips people up: after `DISTINCT`, only the output columns are left to sort by.

<!-- sql pgerror -->
```sql
SELECT DISTINCT country
FROM customers
ORDER BY signup_date;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>for SELECT DISTINCT, ORDER BY expressions must appear in select list</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 8 rows.</p>
<!-- /result -->

PostgreSQL refuses, because after removing duplicates there is no single `signup_date` per country: Canada has three.
SQLite runs it and sorts by some `signup_date` from each group, which is not a meaningful order. If you want countries
in the order of their first signup, say so with grouping: `GROUP BY country ORDER BY MIN(signup_date)`.

## 3.6 Logical order is not physical order { #physical }

The logical order says what the answer **means**, not how the database computes it. The planner is free to do the
work in any order that gives the same result: push a `WHERE` condition into a join, use an index to skip the sort,
stop reading after the `LIMIT` is filled. [Chapter 25](25-Indexes-and-Explain.md) shows how to see the real plan with
`EXPLAIN`.

One practical result: you cannot rely on the conditions in a `WHERE` being checked left to right. To guard against
dividing by zero, do not count on `quantity <> 0 AND 10 / quantity > 1` checking the first part first; put the guard
where it is guaranteed, inside the expression: `CASE WHEN quantity <> 0 THEN 10 / quantity END`, or
`10 / NULLIF(quantity, 0)` ([chapter 4](04-Expressions-Case-Numbers-Dates-Cast.md)).

## 3.7 Where PostgreSQL and SQLite differ { #differences }

| Writing this | PostgreSQL | SQLite | Safe answer |
| --- | --- | --- | --- |
| a `SELECT` alias in `WHERE` | error | runs | repeat the expression, or a CTE |
| a `SELECT` alias in `HAVING` | error | runs | repeat the aggregate |
| a `SELECT` alias in `GROUP BY` | runs | runs | runs on both; SQL Server refuses it |
| a `SELECT` alias in `ORDER BY` | runs | runs | fine everywhere |
| `ORDER BY` a column not in a `SELECT DISTINCT` | error | runs | sort by output columns only |
| an aggregate in `WHERE` | error | error | `HAVING` |
| a window function in `WHERE` | error | error | CTE, filter outside |
| a column in `SELECT` that is neither grouped nor aggregated | error (unless grouped by the table's primary key) | runs | group by it or aggregate it ([chapter 7](07-Aggregation-Group-By-Having.md#select-rule)) |

The rule of thumb: if it is correct on PostgreSQL, it almost always runs on SQLite too. The reverse is not true. Test
your answers on PostgreSQL when you can.

## 3.8 Summary { #summary }

- The run order is FROM, WHERE, GROUP BY, HAVING, SELECT, DISTINCT, ORDER BY, LIMIT.
- Aliases are born in SELECT: usable in ORDER BY, not in WHERE or HAVING.
- Row conditions in WHERE, group conditions (aggregates) in HAVING.
- Window functions are computed in SELECT; filter them in an outer query (a CTE).
- The planner may do the work in any order; never rely on WHERE conditions running left to right.
- SQLite accepts several things PostgreSQL refuses. Write for PostgreSQL.

## Practice { #practice }

**3.1** Put these clauses in the order the database works them out: `ORDER BY`, `HAVING`, `FROM`, `SELECT`, `LIMIT`,
`WHERE`, `GROUP BY`.

??? success "Answer"
    `FROM`, `WHERE`, `GROUP BY`, `HAVING`, `SELECT`, `ORDER BY`, `LIMIT`.

**3.2** This fails on PostgreSQL. Why, and how do you fix it without a CTE?

```sql
SELECT name, price * 1.13 AS price_with_tax
FROM products
WHERE price_with_tax > 30;
```

??? success "Answer"
    `price_with_tax` is made in `SELECT`, which runs after `WHERE`. Repeat the expression:

    <!-- sql -->
    ```sql
    SELECT name, price * 1.13 AS price_with_tax
    FROM products
    WHERE price * 1.13 > 30
    ORDER BY price_with_tax DESC, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | name | price_with_tax |
    | --- | --- |
    | Office chair | 168.3700 |
    | Monitor stand | 36.1600 |
    | Tea kettle | 36.1600 |
    <!-- /result -->

    The tea kettle and the monitor stand cost 32.00 before tax, so with tax they are 36.16. The desk lamp and the wall
    clock (24.50, 27.685 with tax) and the gift card (25.00, 28.25) stay below 30.

**3.3** Find the departments with more than two employees whose salary is known. Return `department`, `staff`. Decide
which condition goes in `WHERE` and which in `HAVING` before writing it.

??? success "Answer"
    "Salary is known" is about single rows: `WHERE`. "More than two" is about groups: `HAVING`.

    <!-- sql -->
    ```sql
    SELECT department, COUNT(*) AS staff
    FROM employees
    WHERE salary IS NOT NULL
    GROUP BY department
    HAVING COUNT(*) > 2
    ORDER BY department;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | department | staff |
    | --- | --- |
    | Engineering | 4 |
    | Sales | 4 |
    <!-- /result -->

    Support has three employees but only two known salaries, so it drops out.

**3.4** For each department, the single highest-paid employee (if two tie, the one whose name comes first). Use a
window function and filter it correctly. Return `department`, `name`, `salary`.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH ranked AS (
      SELECT department, name, salary,
             ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC, name) AS rn
      FROM employees
      WHERE salary IS NOT NULL
    )
    SELECT department, name, salary
    FROM ranked
    WHERE rn = 1
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

    `PARTITION BY department` restarts the numbering in each department ([chapter 13](13-Window-Functions-Ranking.md)).
    The `WHERE salary IS NOT NULL` inside matters on PostgreSQL, which sorts NULL first in a descending order: without
    it, Leo Park (no salary) would be number 1 in Support.

**3.5** True or false: "In `WHERE a <> 0 AND b / a > 2`, the database always checks `a <> 0` first, so there can be no
division by zero."

??? success "Answer"
    False. SQL does not promise the order in which conditions are checked; the planner may evaluate `b / a` first.
    Guard inside the expression: `b / NULLIF(a, 0) > 2` (dividing by NULL gives NULL, which is not true, so the row is
    simply left out).

**Next:** [4. Expressions: CASE, numbers, dates, CAST](04-Expressions-Case-Numbers-Dates-Cast.md).
