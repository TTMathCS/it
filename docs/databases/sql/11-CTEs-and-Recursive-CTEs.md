# 11. CTEs and recursive CTEs

*A CTE (common table expression) is a named subquery written at the top of a query with `WITH`. It turns a tangle of
nested brackets into a list of steps, each with a name, read from top to bottom. That makes it the single most
useful habit for a timed SQL test: build the answer one step at a time and check each step as you go. A recursive
CTE goes further and lets a query refer to itself, which is how SQL counts from 1 to 100, fills in missing dates and
walks an org chart of any depth.*

!!! abstract "In this chapter"
    **You will learn:**

    - `WITH name AS (...)`: one step, several steps, a step used twice
    - how to build and test a hard query step by step
    - `WITH RECURSIVE`: number series, date series, hierarchies with levels and paths
    - how to stop a recursive query running forever
    - what a CTE can't do

    **You need:** chapters 7, 8 and 10.

## 11.1 WITH: name a step { #with }

A CTE is a subquery moved to the front and given a name. These two queries are the same; the second reads in the
order you think it:

<!-- sql -->
```sql
SELECT ROUND(AVG(total), 2) AS avg_order_value
FROM (SELECT order_id, SUM(quantity * unit_price) AS total
      FROM order_items GROUP BY order_id) AS t;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| avg_order_value |
| --- |
| 56.13 |
<!-- /result -->

<!-- sql same -->
```sql
WITH order_totals AS (
  SELECT order_id, SUM(quantity * unit_price) AS total
  FROM order_items
  GROUP BY order_id
)
SELECT ROUND(AVG(total), 2) AS avg_order_value
FROM order_totals;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 1 row.</p>

| avg_order_value |
| --- |
| 56.13 |
<!-- /result -->

Several CTEs are separated by commas, and each can use the ones before it. `WITH` is written once.

<!-- sql -->
```sql
WITH order_totals AS (
  SELECT o.order_id, o.customer_id, SUM(i.quantity * i.unit_price) AS total
  FROM orders o
  JOIN order_items i ON i.order_id = o.order_id
  WHERE o.status = 'shipped'
  GROUP BY o.order_id, o.customer_id
),
customer_totals AS (
  SELECT customer_id, COUNT(*) AS orders, SUM(total) AS revenue
  FROM order_totals
  WHERE customer_id IS NOT NULL
  GROUP BY customer_id
)
SELECT c.name, ct.orders, ct.revenue,
       ROUND(ct.revenue / ct.orders, 2) AS avg_order
FROM customer_totals ct
JOIN customers c ON c.customer_id = ct.customer_id
ORDER BY ct.revenue DESC, c.customer_id
LIMIT 5;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| name | orders | revenue | avg_order |
| --- | --- | --- | --- |
| Ana Silva | 5 | 289.00 | 57.80 |
| Ben Okafor | 2 | 205.50 | 102.75 |
| Dana Kim | 2 | 205.50 | 102.75 |
| Farah Haddad | 1 | 65.00 | 65.00 |
| Hana Sato | 1 | 49.00 | 49.00 |
<!-- /result -->

Step 1 makes one row per shipped order; step 2 one row per customer; the final SELECT adds names. Each step has one
clear grain, which is exactly what prevents the fan-out mistakes of [chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md#fan-out).
(`revenue / orders` is a decimal divided by a whole number, so it doesn't truncate.)

**A CTE can be used twice**, which a derived table can't without copying it out again. Orders whose value is above
the average order value:

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
ORDER BY total DESC, order_id;
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

## 11.2 Building a hard query in steps { #steps }

This is the method to use in a test. The task: "For each month, the customer with the highest shipped revenue that
month, with that revenue. If two customers tie, show both."

**Step 1: one row per order, with its month and value.** Run it on its own and look at the rows.

<!-- sql -->
```sql
WITH order_values AS (
  SELECT o.order_id, o.customer_id,
         SUBSTR(CAST(o.order_date AS TEXT), 1, 7) AS month,
         SUM(i.quantity * i.unit_price) AS total
  FROM orders o
  JOIN order_items i ON i.order_id = o.order_id
  WHERE o.status = 'shipped' AND o.customer_id IS NOT NULL
  GROUP BY o.order_id, o.customer_id, o.order_date
)
SELECT * FROM order_values ORDER BY month, order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 15 rows.</p>

| order_id | customer_id | month | total |
| --- | --- | --- | --- |
| 101 | 1 | 2026-01 | 34.25 |
| 102 | 2 | 2026-01 | 149.00 |
| 103 | 1 | 2026-01 | 33.75 |
| 105 | 4 | 2026-01 | 24.50 |
| 106 | 2 | 2026-02 | 56.50 |
| 107 | 5 | 2026-02 | 36.75 |
| 109 | 6 | 2026-02 | 65.00 |
| 110 | 1 | 2026-02 | 32.50 |
| 111 | 7 | 2026-02 | 36.75 |
| 112 | 4 | 2026-03 | 181.00 |
| 114 | 8 | 2026-03 | 49.00 |
| 115 | 1 | 2026-03 | 49.50 |
| 117 | 10 | 2026-03 | 43.00 |
| 118 | 3 | 2026-04 | 24.50 |
| 120 | 1 | 2026-04 | 139.00 |
<!-- /result -->

**Step 2: one row per customer per month.** **Step 3: the best total in each month.** **Step 4: keep the
customer-months that equal it.** Each step is a CTE; the last SELECT only reads from them.

<!-- sql -->
```sql
WITH order_values AS (
  SELECT o.order_id, o.customer_id,
         SUBSTR(CAST(o.order_date AS TEXT), 1, 7) AS month,
         SUM(i.quantity * i.unit_price) AS total
  FROM orders o
  JOIN order_items i ON i.order_id = o.order_id
  WHERE o.status = 'shipped' AND o.customer_id IS NOT NULL
  GROUP BY o.order_id, o.customer_id, o.order_date
),
customer_month AS (
  SELECT month, customer_id, SUM(total) AS revenue
  FROM order_values
  GROUP BY month, customer_id
),
best AS (
  SELECT month, MAX(revenue) AS top_revenue
  FROM customer_month
  GROUP BY month
)
SELECT cm.month, cm.customer_id, cm.revenue
FROM customer_month cm
JOIN best b ON b.month = cm.month AND cm.revenue = b.top_revenue
ORDER BY cm.month, cm.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| month | customer_id | revenue |
| --- | --- | --- |
| 2026-01 | 2 | 149.00 |
| 2026-02 | 6 | 65.00 |
| 2026-03 | 4 | 181.00 |
| 2026-04 | 1 | 139.00 |
<!-- /result -->

Each month here has a single winner, but the query is ready for a tie: the last join keeps **every** customer-month
whose revenue equals the month's best, so two customers on the same top figure would both appear. `ORDER BY revenue
DESC LIMIT 1` could not do that per month at all. The same task with a window function (`RANK() OVER (PARTITION BY
month ORDER BY revenue DESC)`) is in [chapter 13](13-Window-Functions-Ranking.md).

!!! tip "Interview tip: test each step"
    In the test editor, end the query after any CTE with `SELECT * FROM that_step` and run it. Look at five rows. Is
    the grain right (one row per what)? Are the numbers plausible? Then add the next step. A wrong final answer
    built from checked steps is almost always a one-line fix; a wrong answer written in one go can take the rest of
    the time to find.

## 11.3 Recursive CTEs { #recursive }

A **recursive CTE** refers to itself. It has two parts joined by `UNION ALL`:

1. the **anchor**: a normal query that gives the starting rows;
2. the **recursive part**: a query that reads the rows made in the previous round and makes the next ones.

The database runs the anchor, then the recursive part again and again on the newest rows, until a round produces
no rows. The keyword is `WITH RECURSIVE` in PostgreSQL, SQLite and MySQL; SQL Server and Oracle write plain `WITH`.

**Counting from 1 to 5:**

<!-- sql -->
```sql
WITH RECURSIVE n AS (
  SELECT 1 AS i                 -- anchor
  UNION ALL
  SELECT i + 1 FROM n           -- recursive part: the previous row plus one
  WHERE i < 5                   -- the stop condition
)
SELECT i FROM n ORDER BY i;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| i |
| --- |
| 1 |
| 2 |
| 3 |
| 4 |
| 5 |
<!-- /result -->

Without `WHERE i < 5` it would never stop: the query runs until it is cancelled or the database runs out of space.
Write the stop condition first, before anything else.

**Every day in a range.** Date arithmetic differs between the two databases (chapter 16), so this one comes in two
versions. It makes a calendar for the first week of March, the backbone of "show every day, even days with no
logins":

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    WITH RECURSIVE days AS (
      SELECT DATE '2026-03-01' AS d
      UNION ALL
      SELECT d + 1 FROM days WHERE d < DATE '2026-03-07'
    )
    SELECT d, (SELECT COUNT(*) FROM logins l WHERE l.login_date = days.d) AS logins
    FROM days
    ORDER BY d;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 7 rows.</p>

    | d | logins |
    | --- | --- |
    | 2026-03-01 | 2 |
    | 2026-03-02 | 3 |
    | 2026-03-03 | 2 |
    | 2026-03-04 | 2 |
    | 2026-03-05 | 2 |
    | 2026-03-06 | 2 |
    | 2026-03-07 | 0 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    WITH RECURSIVE days AS (
      SELECT '2026-03-01' AS d
      UNION ALL
      SELECT date(d, '+1 day') FROM days WHERE d < '2026-03-07'
    )
    SELECT d, (SELECT COUNT(*) FROM logins l WHERE l.login_date = days.d) AS logins
    FROM days
    ORDER BY d;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 7 rows.</p>

    | d | logins |
    | --- | --- |
    | 2026-03-01 | 2 |
    | 2026-03-02 | 3 |
    | 2026-03-03 | 2 |
    | 2026-03-04 | 2 |
    | 2026-03-05 | 2 |
    | 2026-03-06 | 2 |
    | 2026-03-07 | 0 |
    <!-- /result -->

PostgreSQL also has `generate_series(start, stop, step)` for exactly this; SQLite has a `generate_series` table in its
command-line tool, but not in most programs that use SQLite as a library, so the recursive CTE is the portable way.

**Walking a hierarchy.** Everyone under Maya Rossi, at every level, with their level and the chain of managers:

<!-- sql -->
```sql
WITH RECURSIVE chain AS (
  SELECT employee_id, name, manager_id, 0 AS level, CAST(name AS TEXT) AS path
  FROM employees
  WHERE manager_id IS NULL                       -- anchor: the top of the tree
  UNION ALL
  SELECT e.employee_id, e.name, e.manager_id, c.level + 1,
         c.path || ' > ' || e.name
  FROM employees e
  JOIN chain c ON e.manager_id = c.employee_id   -- each round goes one level down
)
SELECT level, name, path
FROM chain
ORDER BY path;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 12 rows.</p>

| level | name | path |
| --- | --- | --- |
| 0 | Maya Rossi | Maya Rossi |
| 1 | Kwame Mensah | Maya Rossi > Kwame Mensah |
| 2 | Ella Novak | Maya Rossi > Kwame Mensah > Ella Novak |
| 2 | Leo Park | Maya Rossi > Kwame Mensah > Leo Park |
| 1 | Omar Aziz | Maya Rossi > Omar Aziz |
| 2 | Nina Berg | Maya Rossi > Omar Aziz > Nina Berg |
| 2 | Raj Patel | Maya Rossi > Omar Aziz > Raj Patel |
| 2 | Zoe Martin | Maya Rossi > Omar Aziz > Zoe Martin |
| 1 | Tom Becker | Maya Rossi > Tom Becker |
| 2 | Lucia Gomez | Maya Rossi > Tom Becker > Lucia Gomez |
| 2 | Priya Nair | Maya Rossi > Tom Becker > Priya Nair |
| 2 | Sam Lee | Maya Rossi > Tom Becker > Sam Lee |
<!-- /result -->

Each round joins `employees` to the rows found in the round before: round 0 is Maya, round 1 her three direct
reports, round 2 theirs. Sorting by the path lists the tree in outline order.

**Why the CAST.** In PostgreSQL the anchor and the recursive part must give each column the same type. `name` is
`VARCHAR(50)`, but `path || ' > ' || name` is plain text of any length. Without `CAST(name AS TEXT)` in the anchor,
PostgreSQL stops with *recursive query "chain" column 5 has type character varying(50) in non-recursive term but
type character varying overall*. SQLite doesn't check types and runs it either way. In a test on PostgreSQL, a
growing text or number column in a recursive CTE is the usual place for this error; cast the anchor's column to the
wider type.

!!! warning "Cycles"
    If the data loops (A manages B, B manages A), the recursion never ends. Guard it with a depth limit
    (`WHERE c.level < 20`), or keep the path and stop when it already contains the next id. PostgreSQL 14 and later
    also have a `CYCLE` clause for this.

## 11.4 What a CTE is not { #limits }

- A CTE lasts for **one statement**. To reuse it in the next query, write it again, or make a view
  ([chapter 21](21-Views-and-Materialized-Views.md)) or a temporary table.
- A CTE is not automatically faster. PostgreSQL 12 and later fold a CTE that is used only once into the main
  query, like a subquery; a CTE used twice is computed once. `WITH x AS MATERIALIZED (...)` and `AS NOT MATERIALIZED`
  override this. For a test, write for clarity.
- Inside a CTE, ORDER BY is pointless unless paired with LIMIT; order the final SELECT.

## 11.5 Summary { #summary }

- `WITH a AS (...), b AS (...) SELECT ...` names steps; each may use the earlier ones, and each can be used more
  than once.
- Build hard queries step by step and run each step on its own.
- `WITH RECURSIVE`: anchor `UNION ALL` recursive part, with a stop condition. Used for series and hierarchies.
- Date series need different date arithmetic in PostgreSQL and SQLite.

## Practice { #practice }

**11.1** Using CTEs: the share of total shipped revenue that came from each product category, as a percentage with
one decimal, largest first. The gift card's missing category should show as `none`.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH shipped AS (
      SELECT COALESCE(p.category, 'none') AS category, i.quantity * i.unit_price AS amount
      FROM orders o
      JOIN order_items i ON i.order_id = o.order_id
      JOIN products p    ON p.product_id = i.product_id
      WHERE o.status = 'shipped'
    ),
    by_category AS (
      SELECT category, SUM(amount) AS revenue FROM shipped GROUP BY category
    )
    SELECT category, revenue,
           ROUND(100.0 * revenue / (SELECT SUM(revenue) FROM by_category), 1) AS pct
    FROM by_category
    ORDER BY revenue DESC;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | category | revenue | pct |
    | --- | --- | --- |
    | Office | 618.25 | 61.5 |
    | Home | 196.00 | 19.5 |
    | Kitchen | 140.75 | 14.0 |
    | none | 50.00 | 5.0 |
    <!-- /result -->

**11.2** The numbers 1 to 12 with their squares, using a recursive CTE.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH RECURSIVE n AS (
      SELECT 1 AS i
      UNION ALL
      SELECT i + 1 FROM n WHERE i < 12
    )
    SELECT i, i * i AS square FROM n ORDER BY i;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 12 rows.</p>

    | i | square |
    | --- | --- |
    | 1 | 1 |
    | 2 | 4 |
    | 3 | 9 |
    | 4 | 16 |
    | 5 | 25 |
    | 6 | 36 |
    | 7 | 49 |
    | 8 | 64 |
    | 9 | 81 |
    | 10 | 100 |
    | 11 | 121 |
    | 12 | 144 |
    <!-- /result -->

**11.3** For every employee, the number of people below them at any depth (not just direct reports). Show only
those with at least one.

??? success "Answer"
    Walk down from every employee at once: the anchor pairs each person with each of their direct reports, and the
    recursive part extends each pair one level further down.

    <!-- sql -->
    ```sql
    WITH RECURSIVE below AS (
      SELECT manager_id AS boss, employee_id AS person
      FROM employees
      WHERE manager_id IS NOT NULL
      UNION ALL
      SELECT b.boss, e.employee_id
      FROM below b
      JOIN employees e ON e.manager_id = b.person
    )
    SELECT m.name, COUNT(*) AS people_below
    FROM below b
    JOIN employees m ON m.employee_id = b.boss
    GROUP BY m.employee_id, m.name
    ORDER BY people_below DESC, m.name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | name | people_below |
    | --- | --- |
    | Maya Rossi | 11 |
    | Omar Aziz | 3 |
    | Tom Becker | 3 |
    | Kwame Mensah | 2 |
    <!-- /result -->

    Maya Rossi has everyone else below her: 11 people.

**11.4** Months from January to April 2026 with the number of new customers who signed up that month, including
months with none. Write the month as `YYYY-MM`.

??? success "Answer"
    Four months is short enough to list by hand, which works the same on both databases:

    <!-- sql -->
    ```sql
    WITH months AS (
      SELECT '2026-01' AS month UNION ALL SELECT '2026-02'
      UNION ALL SELECT '2026-03' UNION ALL SELECT '2026-04'
    )
    SELECT m.month, COUNT(c.customer_id) AS new_customers
    FROM months m
    LEFT JOIN customers c ON SUBSTR(CAST(c.signup_date AS TEXT), 1, 7) = m.month
    GROUP BY m.month
    ORDER BY m.month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | month | new_customers |
    | --- | --- |
    | 2026-01 | 3 |
    | 2026-02 | 3 |
    | 2026-03 | 2 |
    | 2026-04 | 0 |
    <!-- /result -->

    April has no sign-ups and still gets its row with 0. For a long range, generate the months with a recursive CTE
    (chapter 16).

**11.5** The chain of managers above Lucia Gomez, from her up to the top, one row each, with the number of steps up.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH RECURSIVE up AS (
      SELECT employee_id, name, manager_id, 0 AS steps
      FROM employees
      WHERE name = 'Lucia Gomez'
      UNION ALL
      SELECT m.employee_id, m.name, m.manager_id, u.steps + 1
      FROM up u
      JOIN employees m ON m.employee_id = u.manager_id
    )
    SELECT steps, name FROM up ORDER BY steps;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | steps | name |
    | --- | --- |
    | 0 | Lucia Gomez |
    | 1 | Tom Becker |
    | 2 | Maya Rossi |
    <!-- /result -->

    The recursion stops by itself when it reaches Maya Rossi, whose `manager_id` is NULL and so joins to nothing.

**Next:** [12. UNION, INTERSECT, EXCEPT](12-Set-Operations.md).
