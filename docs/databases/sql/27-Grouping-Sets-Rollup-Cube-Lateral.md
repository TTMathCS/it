# 27. GROUPING SETS, ROLLUP, CUBE and LATERAL

*Reports need subtotals and grand totals, and tables turned sideways. This chapter shows the SQL that produces
several levels of grouping in one query (`ROLLUP`, `CUBE`, `GROUPING SETS`), the portable way to do the same on
SQLite, counting with `FILTER`, pivoting rows into columns, and `LATERAL`, the join that lets a subquery see the
row next to it.*

!!! abstract "In this chapter"
    **You will learn:**

    - `ROLLUP` for subtotals and a grand total, and `GROUPING()` to label them
    - `CUBE` and `GROUPING SETS` for every combination, or exactly the ones you choose
    - the same results with `UNION ALL`, which runs everywhere
    - `FILTER` and conditional aggregation, and pivoting rows into columns
    - `LATERAL`: top N per group and calling functions per row

    **You need:** [chapter 7](07-Aggregation-Group-By-Having.md) and [chapter 10](10-Subqueries.md).

The `ROLLUP`, `CUBE` and pivot examples use the shop's shipped order lines. This view gives each line its month, category and revenue, so
that the queries below stay short:

<!-- sql keep quiet -->
```sql
CREATE VIEW sales AS
SELECT SUBSTR(CAST(o.order_date AS TEXT), 1, 7) AS month,
       COALESCE(p.category, 'Other')             AS category,
       oi.quantity * oi.unit_price               AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p     ON p.product_id = oi.product_id
WHERE o.status = 'shipped';
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: done.</p>
<!-- /result -->

## 27.1 ROLLUP: subtotals and a grand total { #rollup }

`GROUP BY ROLLUP (month, category)` groups by `(month, category)`, then by `(month)` alone, then by nothing (the
grand total), and returns all three levels in one result. In the extra rows, the columns that were rolled up are
NULL.

<!-- sql pg -->
```sql
SELECT month, category, SUM(revenue) AS revenue
FROM sales
WHERE month IN ('2026-01', '2026-02')
GROUP BY ROLLUP (month, category)
ORDER BY month, category;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 10 rows.</p>

| month | category | revenue |
| --- | --- | --- |
| 2026-01 | Home | 24.50 |
| 2026-01 | Kitchen | 17.50 |
| 2026-01 | Office | 199.50 |
| 2026-01 | *NULL* | 241.50 |
| 2026-02 | Home | 98.00 |
| 2026-02 | Kitchen | 65.00 |
| 2026-02 | Office | 64.50 |
| 2026-02 | Other | 50.00 |
| 2026-02 | *NULL* | 277.50 |
| *NULL* | *NULL* | 519.00 |
<!-- /result -->

PostgreSQL sorts NULLs last, so each month's subtotal comes after its categories and the grand total comes at the
end. `ROLLUP` is hierarchical: with `(a, b, c)` it gives `(a, b, c)`, `(a, b)`, `(a)` and `()`; the order of the
columns matters.

### GROUPING(): which NULL is a subtotal? { #grouping }

A NULL in a rolled-up row means "all categories", but a real NULL in the data looks the same. `GROUPING(column)`
is 1 when the column was rolled up in that row and 0 otherwise, so you can label the rows:

<!-- sql pg -->
```sql
SELECT CASE WHEN GROUPING(month) = 1 THEN 'All months' ELSE month END          AS month,
       CASE WHEN GROUPING(category) = 1 THEN 'All categories' ELSE category END AS category,
       SUM(revenue) AS revenue
FROM sales
WHERE month IN ('2026-01', '2026-02')
GROUP BY ROLLUP (month, category)
ORDER BY GROUPING(month), month, GROUPING(category), category;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 10 rows.</p>

| month | category | revenue |
| --- | --- | --- |
| 2026-01 | Home | 24.50 |
| 2026-01 | Kitchen | 17.50 |
| 2026-01 | Office | 199.50 |
| 2026-01 | All categories | 241.50 |
| 2026-02 | Home | 98.00 |
| 2026-02 | Kitchen | 65.00 |
| 2026-02 | Office | 64.50 |
| 2026-02 | Other | 50.00 |
| 2026-02 | All categories | 277.50 |
| All months | All categories | 519.00 |
<!-- /result -->

Ordering by `GROUPING(...)` first is the reliable way to put subtotals after their details on every database,
whatever it does with NULLs.

## 27.2 CUBE and GROUPING SETS { #cube }

`CUBE (month, category)` gives **every** combination: `(month, category)`, `(month)`, `(category)` and `()`.
`GROUPING SETS` lists exactly the groupings you want; `ROLLUP` and `CUBE` are shorthands for common lists. Here, the
total per month and the total per category, without the detail rows:

<!-- sql pg -->
```sql
SELECT month, category, SUM(revenue) AS revenue
FROM sales
GROUP BY GROUPING SETS ((month), (category))
ORDER BY GROUPING(month), month, category;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 8 rows.</p>

| month | category | revenue |
| --- | --- | --- |
| 2026-01 | *NULL* | 241.50 |
| 2026-02 | *NULL* | 277.50 |
| 2026-03 | *NULL* | 322.50 |
| 2026-04 | *NULL* | 163.50 |
| *NULL* | Home | 196.00 |
| *NULL* | Kitchen | 140.75 |
| *NULL* | Office | 618.25 |
| *NULL* | Other | 50.00 |
<!-- /result -->

The first four rows are per month (category rolled up), the rest per category (month rolled up).

| Write | Means |
| --- | --- |
| `ROLLUP (a, b)` | `GROUPING SETS ((a, b), (a), ())` |
| `CUBE (a, b)` | `GROUPING SETS ((a, b), (a), (b), ())` |
| `GROUPING SETS ((a), (b))` | only the totals per `a` and per `b` |

PostgreSQL, SQL Server, Oracle, Snowflake, Databricks and BigQuery have all three; MySQL has only `WITH ROLLUP`
(`GROUP BY a, b WITH ROLLUP`); SQLite has none of them.

## 27.3 The same on SQLite: UNION ALL { #union-all }

Every grouping set is just another `GROUP BY`. Write one `SELECT` per level, put a label (or NULL) in the columns
that level does not group by, and glue them with `UNION ALL`. This runs on every database:

<!-- sql -->
```sql
SELECT month, category, SUM(revenue) AS revenue, 0 AS lvl
FROM sales WHERE month IN ('2026-01', '2026-02')
GROUP BY month, category
UNION ALL
SELECT month, 'All categories', SUM(revenue), 1
FROM sales WHERE month IN ('2026-01', '2026-02')
GROUP BY month
UNION ALL
SELECT 'All months', 'All categories', SUM(revenue), 2
FROM sales WHERE month IN ('2026-01', '2026-02')
ORDER BY lvl, month, category;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

| month | category | revenue | lvl |
| --- | --- | --- | --- |
| 2026-01 | Home | 24.50 | 0 |
| 2026-01 | Kitchen | 17.50 | 0 |
| 2026-01 | Office | 199.50 | 0 |
| 2026-02 | Home | 98.00 | 0 |
| 2026-02 | Kitchen | 65.00 | 0 |
| 2026-02 | Office | 64.50 | 0 |
| 2026-02 | Other | 50.00 | 0 |
| 2026-01 | All categories | 241.50 | 1 |
| 2026-02 | All categories | 277.50 | 1 |
| All months | All categories | 519.00 | 2 |
<!-- /result -->

The same totals as the `ROLLUP` above. The cost: the table is read once per level, where `ROLLUP` can do it in one
pass, and the filter must be repeated in each part (a CTE avoids repeating it).

## 27.4 Counting with conditions: FILTER { #filter }

To count or sum only some rows inside a group, PostgreSQL and SQLite (3.30+) accept `FILTER (WHERE ...)` after an
aggregate. The older way, `SUM(CASE WHEN ... THEN ... END)`, runs everywhere and means the same.

=== "FILTER"

    <!-- sql -->
    ```sql
    SELECT c.country,
           COUNT(*)                                       AS orders,
           COUNT(*) FILTER (WHERE o.status = 'shipped')   AS shipped,
           COUNT(*) FILTER (WHERE o.status = 'cancelled') AS cancelled
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    GROUP BY c.country
    ORDER BY orders DESC, c.country;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 8 rows.</p>

    | country | orders | shipped | cancelled |
    | --- | --- | --- | --- |
    | Canada | 7 | 6 | 0 |
    | Nigeria | 3 | 2 | 1 |
    | China | 2 | 1 | 1 |
    | Israel | 2 | 1 | 0 |
    | South Korea | 2 | 2 | 0 |
    | Czechia | 1 | 1 | 0 |
    | Japan | 1 | 1 | 0 |
    | Portugal | 1 | 1 | 0 |
    <!-- /result -->

=== "CASE (every database)"

    <!-- sql same -->
    ```sql
    SELECT c.country,
           COUNT(*)                                                  AS orders,
           SUM(CASE WHEN o.status = 'shipped'   THEN 1 ELSE 0 END)   AS shipped,
           SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END)   AS cancelled
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    GROUP BY c.country
    ORDER BY orders DESC, c.country;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 8 rows.</p>

    | country | orders | shipped | cancelled |
    | --- | --- | --- | --- |
    | Canada | 7 | 6 | 0 |
    | Nigeria | 3 | 2 | 1 |
    | China | 2 | 1 | 1 |
    | Israel | 2 | 1 | 0 |
    | South Korea | 2 | 2 | 0 |
    | Czechia | 1 | 1 | 0 |
    | Japan | 1 | 1 | 0 |
    | Portugal | 1 | 1 | 0 |
    <!-- /result -->

`COUNT(CASE WHEN ... THEN 1 END)` also works: a `CASE` with no `ELSE` gives NULL, and `COUNT` skips NULLs.

## 27.5 Pivot: rows into columns { #pivot }

A pivot turns the values of one column into column headings: one row per category, one column per month. Each
column is a conditional aggregate, so you must know the columns when you write the query:

<!-- sql -->
```sql
SELECT category,
       SUM(CASE WHEN month = '2026-01' THEN revenue ELSE 0 END) AS jan,
       SUM(CASE WHEN month = '2026-02' THEN revenue ELSE 0 END) AS feb,
       SUM(CASE WHEN month = '2026-03' THEN revenue ELSE 0 END) AS mar,
       SUM(CASE WHEN month = '2026-04' THEN revenue ELSE 0 END) AS apr,
       SUM(revenue)                                             AS total
FROM sales
GROUP BY category
ORDER BY total DESC, category;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| category | jan | feb | mar | apr | total |
| --- | --- | --- | --- | --- | --- |
| Office | 199.50 | 64.50 | 215.25 | 139.00 | 618.25 |
| Home | 24.50 | 98.00 | 49.00 | 24.50 | 196.00 |
| Kitchen | 17.50 | 65.00 | 58.25 | 0 | 140.75 |
| Other | 0 | 50.00 | 0 | 0 | 50.00 |
<!-- /result -->

`ELSE 0` shows 0 for a month with no sales; leave it out to show NULL instead. SQL Server, Oracle, Snowflake and
Databricks have a `PIVOT` clause that writes the same thing more briefly, and PostgreSQL has `crosstab()` in the
`tablefunc` extension; most of them still need the list of columns (Snowflake's `PIVOT ... IN (ANY)` is an exception), because a query's columns are fixed before it
runs. The reverse, **unpivot** (columns into rows), is a `UNION ALL` of one `SELECT` per column, or a join to a
`VALUES` list.

## 27.6 LATERAL: a subquery that sees the row beside it { #lateral }

A subquery in `FROM` normally cannot refer to the other tables in the same `FROM`. With `LATERAL` it can: it runs
once per row of the tables to its left, like a correlated subquery that may return several rows and several
columns. The classic use is **top N per group**: each customer's two largest orders.

<!-- sql pg -->
```sql
SELECT c.customer_id, c.name, t.order_id, t.order_total
FROM customers c
CROSS JOIN LATERAL (
  SELECT o.order_id, SUM(oi.quantity * oi.unit_price) AS order_total
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE o.customer_id = c.customer_id
  GROUP BY o.order_id
  ORDER BY order_total DESC, o.order_id
  LIMIT 2
) t
WHERE c.customer_id IN (1, 2, 4)
ORDER BY c.customer_id, t.order_total DESC, t.order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 6 rows.</p>

| customer_id | name | order_id | order_total |
| --- | --- | --- | --- |
| 1 | Ana Silva | 120 | 139.00 |
| 1 | Ana Silva | 115 | 49.50 |
| 2 | Ben Okafor | 102 | 149.00 |
| 2 | Ben Okafor | 106 | 56.50 |
| 4 | Dana Kim | 112 | 181.00 |
| 4 | Dana Kim | 105 | 24.50 |
<!-- /result -->

`CROSS JOIN LATERAL` drops customers for whom the subquery returns nothing; `LEFT JOIN LATERAL (...) t ON true`
keeps them, with NULLs. SQL Server and Oracle write the same idea as `CROSS APPLY` / `OUTER APPLY`. SQLite has no
`LATERAL`; the window-function version runs everywhere ([chapter 13](13-Window-Functions-Ranking.md)):

<!-- sql same -->
```sql
SELECT customer_id, name, order_id, order_total
FROM (
  SELECT c.customer_id, c.name, o.order_id,
         SUM(oi.quantity * oi.unit_price) AS order_total,
         ROW_NUMBER() OVER (PARTITION BY c.customer_id
                            ORDER BY SUM(oi.quantity * oi.unit_price) DESC, o.order_id) AS rn
  FROM customers c
  JOIN orders o       ON o.customer_id = c.customer_id
  JOIN order_items oi ON oi.order_id = o.order_id
  WHERE c.customer_id IN (1, 2, 4)
  GROUP BY c.customer_id, c.name, o.order_id
) ranked
WHERE rn <= 2
ORDER BY customer_id, order_total DESC, order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 6 rows.</p>

| customer_id | name | order_id | order_total |
| --- | --- | --- | --- |
| 1 | Ana Silva | 120 | 139.00 |
| 1 | Ana Silva | 115 | 49.50 |
| 2 | Ben Okafor | 102 | 149.00 |
| 2 | Ben Okafor | 106 | 56.50 |
| 4 | Dana Kim | 112 | 181.00 |
| 4 | Dana Kim | 105 | 24.50 |
<!-- /result -->

Which is faster depends on the data. `LATERAL` with an index on the inner table's key (`orders.customer_id`) and a
small `LIMIT` reads only a few rows per outer row, which wins when there are few outer rows; the window version reads
everything once and wins when you want the answer for every group.

The other everyday use of `LATERAL` is calling a function that returns rows, once per row, as in
[chapter 24](24-JSON-and-Arrays.md#explode) (`jsonb_array_elements`, `UNNEST`). There PostgreSQL lets you leave out
the word `LATERAL`; for subqueries it is required.

## 27.7 Summary { #summary }

- `ROLLUP (a, b)` adds subtotals per `a` and a grand total; `CUBE` adds every combination; `GROUPING SETS` lists the
  groupings you want. Rolled-up columns are NULL; `GROUPING(col)` tells those NULLs from real ones.
- SQLite (and any database) can do the same with `UNION ALL` of one `GROUP BY` per level.
- `COUNT(*) FILTER (WHERE ...)` or `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` counts some rows of a group.
- Pivot with one conditional aggregate per column; the columns must be known in advance.
- `LATERAL` runs a subquery once per row to its left: top N per group, or a function per row. Without it, use
  `ROW_NUMBER`.

!!! question "Asked aloud: grouping and pivoting"
    ??? note "What is the difference between ROLLUP and CUBE?"
        `ROLLUP (a, b, c)` follows the hierarchy: `(a, b, c)`, `(a, b)`, `(a)`, `()`; it suits year > month > day or
        country > city. `CUBE (a, b, c)` gives all 2³ = 8 combinations, including `(b)` and `(a, c)`; it suits
        cross-tabulations where no column is above another. `GROUPING SETS` lists exactly the combinations wanted.

    ??? note "How do you tell a subtotal row from a NULL in the data?"
        With `GROUPING(column)`, which is 1 when that column was aggregated away in the row. Use it to label the rows
        ("All categories") and to sort subtotals after their details.

    ??? note "How do you pivot in SQL?"
        Conditional aggregation: group by the row key, and one `SUM(CASE WHEN col = 'value' THEN amount END)` per
        output column. Some databases have a `PIVOT` clause for the same. The output columns must be known when the query
        is written; a truly dynamic pivot needs the query text built by a program.

    ??? note "What does LATERAL do?"
        It lets a subquery or function in `FROM` refer to columns of the tables before it, so it runs once per row of
        those tables. It is used for top N per group with `ORDER BY ... LIMIT`, and to expand arrays or JSON per row.
        SQL Server and Oracle call it `CROSS APPLY` and `OUTER APPLY`.

    ??? note "Why use FILTER instead of a WHERE?"
        `WHERE` removes rows before grouping, so every aggregate sees the same rows. `FILTER` (or a `CASE` inside the
        aggregate) applies a condition to one aggregate only, so one query can count all orders, shipped orders and
        cancelled orders side by side.

## Practice { #practice }

**27.1** For each country and city of the shop's customers, and for each country alone, count the customers, using
`ROLLUP` on PostgreSQL. Leave out the grand total, and label each country's total row 'All cities'. Ignore customers
with no city.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT country,
           CASE WHEN GROUPING(city) = 1 THEN 'All cities' ELSE city END AS city,
           COUNT(*) AS customers
    FROM customers
    WHERE city IS NOT NULL
    GROUP BY ROLLUP (country, city)
    HAVING GROUPING(country) = 0
    ORDER BY country, GROUPING(city), city;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 14 rows.</p>

    | country | city | customers |
    | --- | --- | --- |
    | Canada | Toronto | 3 |
    | Canada | All cities | 3 |
    | China | Shanghai | 1 |
    | China | All cities | 1 |
    | Czechia | Prague | 1 |
    | Czechia | All cities | 1 |
    | Japan | Osaka | 1 |
    | Japan | All cities | 1 |
    | Nigeria | Lagos | 1 |
    | Nigeria | All cities | 1 |
    | Portugal | Lisbon | 1 |
    | Portugal | All cities | 1 |
    | South Korea | Seoul | 1 |
    | South Korea | All cities | 1 |
    <!-- /result -->

    `HAVING GROUPING(country) = 0` removes the grand-total row, in which `country` itself was rolled up.
    `GROUP BY country, ROLLUP (city)` gives the same groupings more directly.

**27.2** Write 27.1 so that it runs on SQLite.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT country, city, COUNT(*) AS customers, 0 AS lvl
    FROM customers WHERE city IS NOT NULL
    GROUP BY country, city
    UNION ALL
    SELECT country, 'All cities', COUNT(*), 1
    FROM customers WHERE city IS NOT NULL
    GROUP BY country
    ORDER BY country, lvl, city;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 14 rows.</p>

    | country | city | customers | lvl |
    | --- | --- | --- | --- |
    | Canada | Toronto | 3 | 0 |
    | Canada | All cities | 3 | 1 |
    | China | Shanghai | 1 | 0 |
    | China | All cities | 1 | 1 |
    | Czechia | Prague | 1 | 0 |
    | Czechia | All cities | 1 | 1 |
    | Japan | Osaka | 1 | 0 |
    | Japan | All cities | 1 | 1 |
    | Nigeria | Lagos | 1 | 0 |
    | Nigeria | All cities | 1 | 1 |
    | Portugal | Lisbon | 1 | 0 |
    | Portugal | All cities | 1 | 1 |
    | South Korea | Seoul | 1 | 0 |
    | South Korea | All cities | 1 | 1 |
    <!-- /result -->

    The extra `lvl` column sorts each country's total after its cities. In a test, if the task asks for exactly three
    columns, wrap it in an outer `SELECT country, city, customers FROM (...) ORDER BY ...`.

**27.3** Show, for each department of `employees`, the number of employees hired before 2022 and from 2022 on, in
two columns, using `FILTER`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT department,
           COUNT(*) FILTER (WHERE hire_date <  '2022-01-01') AS before_2022,
           COUNT(*) FILTER (WHERE hire_date >= '2022-01-01') AS from_2022
    FROM employees
    GROUP BY department
    ORDER BY department;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | department | before_2022 | from_2022 |
    | --- | --- | --- |
    | Engineering | 2 | 2 |
    | Management | 1 | 0 |
    | Sales | 1 | 3 |
    | Support | 1 | 2 |
    <!-- /result -->

    `COUNT(*) FILTER (WHERE ...)` counts only the rows that pass the test, inside an ordinary `GROUP BY`. It is
    the short PostgreSQL way of writing `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`; SQLite supports it too (since
    3.30).


**27.4** On PostgreSQL, for every product category, return its single best-selling product by units, using
`LATERAL`. Ignore products with no category.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT cat.category, best.name, best.units
    FROM (SELECT DISTINCT category FROM products WHERE category IS NOT NULL) cat
    CROSS JOIN LATERAL (
      SELECT p.name, SUM(oi.quantity) AS units
      FROM products p
      JOIN order_items oi ON oi.product_id = p.product_id
      WHERE p.category = cat.category
      GROUP BY p.product_id, p.name
      ORDER BY units DESC, p.name
      LIMIT 1
    ) best
    ORDER BY cat.category;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | category | name | units |
    | --- | --- | --- |
    | Home | Plant pot | 6 |
    | Kitchen | Coffee mug | 9 |
    | Office | Notebook | 25 |
    <!-- /result -->

    The tie-breaker `p.name` makes the answer the same on every run if two products sell the same number of units.

**Next:** [28. Dialect differences](28-Dialect-Differences.md).
