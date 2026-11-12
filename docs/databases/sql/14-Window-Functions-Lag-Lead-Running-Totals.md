# 14. Window functions: LAG, LEAD and running totals

*The second half of window functions looks along the rows in order: the value in the row before (LAG) or after
(LEAD), the total so far (a running sum), the average of the last three (a moving average). These answer the
time-based questions that data engineering tests love: change from last month, days since the previous order,
cumulative revenue, a 7-day average. They hide one trap that catches experienced people: the default "frame" of a
window, which quietly changes running totals when dates tie and makes LAST_VALUE return the wrong row.*

!!! abstract "In this chapter"
    **You will learn:**

    - `LAG` and `LEAD`, with an offset and a default
    - the gap between consecutive events, per customer
    - month-over-month change and growth
    - running totals, overall and per group
    - **frames**: `ROWS BETWEEN ... AND ...`, and why `RANGE` (the default) treats ties as one
    - moving averages
    - `FIRST_VALUE`, `LAST_VALUE` (and its trap), `NTH_VALUE`

    **You need:** chapter 13.

## 14.1 LAG and LEAD: the row before and after { #lag-lead }

`LAG(x)` is the value of `x` in the **previous** row of the window; `LEAD(x)` in the **next**. The window's ORDER BY
says what "previous" means, and PARTITION BY keeps each group separate.

<!-- sql -->
```sql
SELECT customer_id, order_id, order_date,
       LAG(order_date)  OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS previous_order,
       LEAD(order_date) OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS next_order
FROM orders
WHERE customer_id IN (1, 2)
ORDER BY customer_id, order_date, order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 8 rows.</p>

| customer_id | order_id | order_date | previous_order | next_order |
| --- | --- | --- | --- | --- |
| 1 | 101 | 2026-01-03 | *NULL* | 2026-01-15 |
| 1 | 103 | 2026-01-15 | 2026-01-03 | 2026-02-20 |
| 1 | 110 | 2026-02-20 | 2026-01-15 | 2026-03-18 |
| 1 | 115 | 2026-03-18 | 2026-02-20 | 2026-04-05 |
| 1 | 120 | 2026-04-05 | 2026-03-18 | *NULL* |
| 2 | 102 | 2026-01-03 | *NULL* | 2026-02-02 |
| 2 | 106 | 2026-02-02 | 2026-01-03 | 2026-03-05 |
| 2 | 113 | 2026-03-05 | 2026-02-02 | *NULL* |
<!-- /result -->

The first order of each customer has no previous one, so LAG gives NULL; the last has no next, so LEAD gives NULL.
The partition stops customer 2's first order looking back at customer 1's last.

Both take two more arguments: how many rows back or forward (default 1), and what to give instead of NULL when there
is no such row. `LAG(x, 1, 0)` is "previous value, or 0 for the first row".

**Days between orders** needs date arithmetic, which differs (chapter 16): PostgreSQL subtracts dates directly and
gets whole days; SQLite turns dates into day numbers with `julianday`.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT customer_id, order_id, order_date,
           order_date - LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS days_since_previous
    FROM orders
    WHERE customer_id = 1
    ORDER BY order_date, order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 5 rows.</p>

    | customer_id | order_id | order_date | days_since_previous |
    | --- | --- | --- | --- |
    | 1 | 101 | 2026-01-03 | *NULL* |
    | 1 | 103 | 2026-01-15 | 12 |
    | 1 | 110 | 2026-02-20 | 36 |
    | 1 | 115 | 2026-03-18 | 26 |
    | 1 | 120 | 2026-04-05 | 18 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    SELECT customer_id, order_id, order_date,
           CAST(julianday(order_date)
                - julianday(LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_date, order_id)) AS INTEGER)
             AS days_since_previous
    FROM orders
    WHERE customer_id = 1
    ORDER BY order_date, order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 5 rows.</p>

    | customer_id | order_id | order_date | days_since_previous |
    | --- | --- | --- | --- |
    | 1 | 101 | 2026-01-03 | *NULL* |
    | 1 | 103 | 2026-01-15 | 12 |
    | 1 | 110 | 2026-02-20 | 36 |
    | 1 | 115 | 2026-03-18 | 26 |
    | 1 | 120 | 2026-04-05 | 18 |
    <!-- /result -->

## 14.2 Change from the previous period { #period-change }

First one row per month (a CTE), then LAG over the months. Shipped revenue per month and the change from the month
before:

<!-- sql -->
```sql
WITH monthly AS (
  SELECT SUBSTR(CAST(o.order_date AS TEXT), 1, 7) AS month,
         SUM(i.quantity * i.unit_price) AS revenue
  FROM orders o
  JOIN order_items i ON i.order_id = o.order_id
  WHERE o.status = 'shipped'
  GROUP BY SUBSTR(CAST(o.order_date AS TEXT), 1, 7)
)
SELECT month, revenue,
       LAG(revenue) OVER (ORDER BY month)            AS previous,
       revenue - LAG(revenue) OVER (ORDER BY month)  AS change,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / LAG(revenue) OVER (ORDER BY month), 1) AS pct_change
FROM monthly
ORDER BY month;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| month | revenue | previous | change | pct_change |
| --- | --- | --- | --- | --- |
| 2026-01 | 241.50 | *NULL* | *NULL* | *NULL* |
| 2026-02 | 277.50 | 241.50 | 36.00 | 14.9 |
| 2026-03 | 322.50 | 277.50 | 45.00 | 16.2 |
| 2026-04 | 163.50 | 322.50 | -159.00 | -49.3 |
<!-- /result -->

January has no previous month, so its change is NULL, which is the honest answer (not 0, and not 100%).

!!! warning "Missing periods"
    LAG looks at the previous **row**, not the previous **month**. If a month had no orders it would have no row, and
    LAG would compare with two months back without telling you. When periods can be missing, build the full list of
    months first and LEFT JOIN the data onto it ([chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md#cross),
    [chapter 16](16-Dates-and-Time-Series.md)). Also watch for division by a previous value of 0:
    `NULLIF(LAG(...), 0)` turns it into NULL instead of an error in PostgreSQL (SQLite already gives NULL).

## 14.3 Running totals { #running }

An aggregate with ORDER BY in its window becomes a **running** aggregate: the sum of every row from the start up to
this one.

<!-- sql -->
```sql
WITH monthly AS (
  SELECT SUBSTR(CAST(o.order_date AS TEXT), 1, 7) AS month,
         SUM(i.quantity * i.unit_price) AS revenue
  FROM orders o
  JOIN order_items i ON i.order_id = o.order_id
  WHERE o.status = 'shipped'
  GROUP BY SUBSTR(CAST(o.order_date AS TEXT), 1, 7)
)
SELECT month, revenue,
       SUM(revenue) OVER (ORDER BY month) AS revenue_to_date
FROM monthly
ORDER BY month;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| month | revenue | revenue_to_date |
| --- | --- | --- |
| 2026-01 | 241.50 | 241.50 |
| 2026-02 | 277.50 | 519.00 |
| 2026-03 | 322.50 | 841.50 |
| 2026-04 | 163.50 | 1005.00 |
<!-- /result -->

With PARTITION BY the total restarts in each group: each customer's spending to date, order by order.

<!-- sql -->
```sql
WITH order_values AS (
  SELECT o.customer_id, o.order_id, o.order_date, SUM(i.quantity * i.unit_price) AS total
  FROM orders o
  JOIN order_items i ON i.order_id = o.order_id
  WHERE o.customer_id IN (1, 4)
  GROUP BY o.customer_id, o.order_id, o.order_date
)
SELECT customer_id, order_id, order_date, total,
       SUM(total) OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS spent_to_date
FROM order_values
ORDER BY customer_id, order_date, order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 7 rows.</p>

| customer_id | order_id | order_date | total | spent_to_date |
| --- | --- | --- | --- | --- |
| 1 | 101 | 2026-01-03 | 34.25 | 34.25 |
| 1 | 103 | 2026-01-15 | 33.75 | 68.00 |
| 1 | 110 | 2026-02-20 | 32.50 | 100.50 |
| 1 | 115 | 2026-03-18 | 49.50 | 150.00 |
| 1 | 120 | 2026-04-05 | 139.00 | 289.00 |
| 4 | 105 | 2026-01-28 | 24.50 | 24.50 |
| 4 | 112 | 2026-03-01 | 181.00 | 205.50 |
<!-- /result -->

## 14.4 Frames: ROWS, RANGE and the tie trap { #frames }

Every window with an ORDER BY has a **frame**: the rows, around the current one, that the function reads. When you
don't write one, the default is:

```text
RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
```

**RANGE** means "every row whose ORDER BY value is up to and including this row's value". So rows with the **same**
value (peers) all count as "the current row", and they all get the same running total. Watch what that does to a
running total of orders by date, where two orders share 3 January and two share 2 February:

!!! failure "The usual wrong answer: a running count with ties"
    <!-- sql -->
    ```sql
    SELECT order_id, order_date,
           COUNT(*) OVER (ORDER BY order_date) AS orders_so_far
    FROM orders
    WHERE order_date < '2026-02-15'
    ORDER BY order_date, order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | order_id | order_date | orders_so_far |
    | --- | --- | --- |
    | 101 | 2026-01-03 | 2 |
    | 102 | 2026-01-03 | 2 |
    | 103 | 2026-01-15 | 3 |
    | 104 | 2026-01-20 | 4 |
    | 105 | 2026-01-28 | 5 |
    | 106 | 2026-02-02 | 7 |
    | 107 | 2026-02-02 | 7 |
    | 108 | 2026-02-10 | 8 |
    | 109 | 2026-02-14 | 9 |
    <!-- /result -->

    The first row says 2 orders so far, though it is the first order. Both 3 January orders see each other as part
    of "up to the current value". If the task wanted a count that goes up by one on every row, this is wrong.

**ROWS** counts physical rows instead: "from the first row up to this row, exactly". With a tie-break in the ORDER
BY, every row gets its own total:

<!-- sql -->
```sql
SELECT order_id, order_date,
       COUNT(*) OVER (ORDER BY order_date, order_id
                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS orders_so_far
FROM orders
WHERE order_date < '2026-02-15'
ORDER BY order_date, order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

| order_id | order_date | orders_so_far |
| --- | --- | --- |
| 101 | 2026-01-03 | 1 |
| 102 | 2026-01-03 | 2 |
| 103 | 2026-01-15 | 3 |
| 104 | 2026-01-20 | 4 |
| 105 | 2026-01-28 | 5 |
| 106 | 2026-02-02 | 6 |
| 107 | 2026-02-02 | 7 |
| 108 | 2026-02-10 | 8 |
| 109 | 2026-02-14 | 9 |
<!-- /result -->

Neither is wrong in itself: RANGE answers "orders up to and including this **day**", ROWS answers "orders up to and
including this **row**". Know which one the question asks for, and write the frame explicitly when it matters.

!!! tip "Interview tip: write the frame"
    For running totals write `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` and a unique ORDER BY (add the id).
    It makes the result certain, and it shows the interviewer you know the default is RANGE. If the data is one row
    per date already (as in a monthly CTE), both give the same answer.

The frame words:

| Bound | Means |
| --- | --- |
| `UNBOUNDED PRECEDING` | the first row of the partition |
| `n PRECEDING` | `n` rows before (with ROWS) |
| `CURRENT ROW` | this row (with RANGE: this row and its peers) |
| `n FOLLOWING` | `n` rows after |
| `UNBOUNDED FOLLOWING` | the last row of the partition |

## 14.5 Moving averages { #moving }

"The average of this row and the two before it" is a frame of three rows:

<!-- sql -->
```sql
WITH daily AS (
  SELECT login_date, COUNT(*) AS logins
  FROM logins
  GROUP BY login_date
)
SELECT login_date, logins,
       ROUND(AVG(logins) OVER (ORDER BY login_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS avg_3_rows,
       COUNT(*)          OVER (ORDER BY login_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)     AS rows_in_avg
FROM daily
ORDER BY login_date;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 8 rows.</p>

| login_date | logins | avg_3_rows | rows_in_avg |
| --- | --- | --- | --- |
| 2026-03-01 | 2 | 2.00 | 1 |
| 2026-03-02 | 3 | 2.50 | 2 |
| 2026-03-03 | 2 | 2.33 | 3 |
| 2026-03-04 | 2 | 2.33 | 3 |
| 2026-03-05 | 2 | 2.00 | 3 |
| 2026-03-06 | 2 | 2.00 | 3 |
| 2026-03-08 | 1 | 1.67 | 3 |
| 2026-03-10 | 1 | 1.33 | 3 |
<!-- /result -->

Two things to notice. The first two rows average fewer than three values (the `rows_in_avg` column shows it); a task
may want those left NULL instead (`CASE WHEN rows_in_avg = 3 THEN ... END`). And this is three **rows**, not three
**days**: nobody logged in on 7 or 9 March, so those days have no rows, and the averages on 8 and 10 March reach back
over four and five calendar days. For a true 3-day average, fill in the missing days with 0 first (chapter 16).

## 14.6 FIRST_VALUE, LAST_VALUE, NTH_VALUE { #first-last }

`FIRST_VALUE(x)` is `x` from the first row of the frame. The highest salary in each department, beside everyone:

<!-- sql -->
```sql
SELECT department, name, salary,
       FIRST_VALUE(name) OVER (PARTITION BY department ORDER BY salary DESC, name) AS top_earner
FROM employees
WHERE department IN ('Sales', 'Support') AND salary IS NOT NULL
ORDER BY department, salary DESC, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

| department | name | salary | top_earner |
| --- | --- | --- | --- |
| Sales | Omar Aziz | 110000 | Omar Aziz |
| Sales | Nina Berg | 70000 | Omar Aziz |
| Sales | Raj Patel | 70000 | Omar Aziz |
| Sales | Zoe Martin | 65000 | Omar Aziz |
| Support | Kwame Mensah | 75000 | Kwame Mensah |
| Support | Ella Novak | 52000 | Kwame Mensah |
<!-- /result -->

`LAST_VALUE` looks like its mirror, and isn't, because of the default frame:

!!! failure "The LAST_VALUE trap"
    <!-- sql -->
    ```sql
    SELECT department, name, salary,
           LAST_VALUE(name) OVER (PARTITION BY department ORDER BY salary DESC, name) AS lowest_earner
    FROM employees
    WHERE department IN ('Sales', 'Support') AND salary IS NOT NULL
    ORDER BY department, salary DESC, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

    | department | name | salary | lowest_earner |
    | --- | --- | --- | --- |
    | Sales | Omar Aziz | 110000 | Omar Aziz |
    | Sales | Nina Berg | 70000 | Nina Berg |
    | Sales | Raj Patel | 70000 | Raj Patel |
    | Sales | Zoe Martin | 65000 | Zoe Martin |
    | Support | Kwame Mensah | 75000 | Kwame Mensah |
    | Support | Ella Novak | 52000 | Ella Novak |
    <!-- /result -->

    Every row names itself. The default frame ends at the **current row**, so the last row of the frame is always
    the row you're on.

Extend the frame to the end of the partition:

<!-- sql -->
```sql
SELECT department, name, salary,
       LAST_VALUE(name) OVER (PARTITION BY department ORDER BY salary DESC, name
                              ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS lowest_earner
FROM employees
WHERE department IN ('Sales', 'Support') AND salary IS NOT NULL
ORDER BY department, salary DESC, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

| department | name | salary | lowest_earner |
| --- | --- | --- | --- |
| Sales | Omar Aziz | 110000 | Zoe Martin |
| Sales | Nina Berg | 70000 | Zoe Martin |
| Sales | Raj Patel | 70000 | Zoe Martin |
| Sales | Zoe Martin | 65000 | Zoe Martin |
| Support | Kwame Mensah | 75000 | Ella Novak |
| Support | Ella Novak | 52000 | Ella Novak |
<!-- /result -->

Easier still: `FIRST_VALUE(name) OVER (PARTITION BY department ORDER BY salary ASC, name)`, the first in the opposite
order. `NTH_VALUE(x, n)` gives the n-th row's value and has the same frame trap.

## 14.7 Summary { #summary }

- `LAG(x, n, default)` / `LEAD(x, n, default)`: the value n rows before or after, in the window's order.
- Compare periods by building one row per period first, then LAG. Missing periods must be filled in first.
- `SUM(x) OVER (ORDER BY ...)` is a running total; add PARTITION BY to restart per group.
- The default frame is `RANGE ... CURRENT ROW`: ties share a value. Write `ROWS BETWEEN UNBOUNDED PRECEDING AND
  CURRENT ROW` with a unique ORDER BY for row-by-row totals.
- Moving average: `AVG(x) OVER (ORDER BY d ROWS BETWEEN n PRECEDING AND CURRENT ROW)`, over rows, not days.
- `LAST_VALUE` needs `... AND UNBOUNDED FOLLOWING`, or use `FIRST_VALUE` in reverse order.

## Practice { #practice }

**14.1** For each order of customer 4, the value of the order and the value of their previous order (0 if none).

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH v AS (
      SELECT o.order_id, o.order_date, SUM(i.quantity * i.unit_price) AS total
      FROM orders o
      JOIN order_items i ON i.order_id = o.order_id
      WHERE o.customer_id = 4
      GROUP BY o.order_id, o.order_date
    )
    SELECT order_id, order_date, total,
           LAG(total, 1, 0) OVER (ORDER BY order_date, order_id) AS previous_total
    FROM v
    ORDER BY order_date, order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | order_id | order_date | total | previous_total |
    | --- | --- | --- | --- |
    | 105 | 2026-01-28 | 24.50 | 0 |
    | 112 | 2026-03-01 | 181.00 | 24.50 |
    <!-- /result -->

**14.2** Customers who placed an order within 15 days of their previous order. Show the customer, the two order ids
and dates. Write it in PostgreSQL (or in SQLite, with `julianday`).

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        WITH x AS (
          SELECT customer_id, order_id, order_date,
                 LAG(order_id)   OVER w AS prev_order_id,
                 LAG(order_date) OVER w AS prev_date
          FROM orders
          WHERE customer_id IS NOT NULL
          WINDOW w AS (PARTITION BY customer_id ORDER BY order_date, order_id)
        )
        SELECT customer_id, prev_order_id, prev_date, order_id, order_date
        FROM x
        WHERE order_date - prev_date <= 15
        ORDER BY customer_id, order_date;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

        | customer_id | prev_order_id | prev_date | order_id | order_date |
        | --- | --- | --- | --- | --- |
        | 1 | 101 | 2026-01-03 | 103 | 2026-01-15 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        WITH x AS (
          SELECT customer_id, order_id, order_date,
                 LAG(order_id)   OVER w AS prev_order_id,
                 LAG(order_date) OVER w AS prev_date
          FROM orders
          WHERE customer_id IS NOT NULL
          WINDOW w AS (PARTITION BY customer_id ORDER BY order_date, order_id)
        )
        SELECT customer_id, prev_order_id, prev_date, order_id, order_date
        FROM x
        WHERE julianday(order_date) - julianday(prev_date) <= 15
        ORDER BY customer_id, order_date;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 1 row.</p>

        | customer_id | prev_order_id | prev_date | order_id | order_date |
        | --- | --- | --- | --- | --- |
        | 1 | 101 | 2026-01-03 | 103 | 2026-01-15 |
        <!-- /result -->

    For a first order, `prev_date` is NULL, the comparison is unknown, and the row is dropped, as it should be.

**14.3** The running total of notebook units sold (product 2), order by order, in order-id order.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT order_id, quantity,
           SUM(quantity) OVER (ORDER BY order_id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS units_to_date
    FROM order_items
    WHERE product_id = 2
    ORDER BY order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | order_id | quantity | units_to_date |
    | --- | --- | --- |
    | 101 | 3 | 3 |
    | 103 | 5 | 8 |
    | 105 | 2 | 10 |
    | 110 | 10 | 20 |
    | 117 | 5 | 25 |
    <!-- /result -->

**14.4** The first day on which the running total of shipped revenue reached 500.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH daily AS (
      SELECT o.order_date, SUM(i.quantity * i.unit_price) AS revenue
      FROM orders o
      JOIN order_items i ON i.order_id = o.order_id
      WHERE o.status = 'shipped'
      GROUP BY o.order_date
    ),
    running AS (
      SELECT order_date, revenue,
             SUM(revenue) OVER (ORDER BY order_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS to_date
      FROM daily
    )
    SELECT MIN(order_date) AS day_reached_500
    FROM running
    WHERE to_date >= 500;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | day_reached_500 |
    | --- |
    | 2026-02-21 |
    <!-- /result -->

    Group to one row per day first, so that the running total is per day; then the first day whose total is at
    least 500.

**14.5** For each employee in Engineering, the difference between their salary and the next-lower salary in the
department (by salary, ties broken by name). NULL for the lowest.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, salary,
           salary - LEAD(salary) OVER (ORDER BY salary DESC, name) AS above_next
    FROM employees
    WHERE department = 'Engineering'
    ORDER BY salary DESC, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | name | salary | above_next |
    | --- | --- | --- |
    | Tom Becker | 140000 | 20000 |
    | Priya Nair | 120000 | 0 |
    | Sam Lee | 120000 | 25000 |
    | Lucia Gomez | 95000 | *NULL* |
    <!-- /result -->

    Priya Nair is 0 above Sam Lee: tied salaries, and the name decides who is "next".

**14.6** Each month's shipped revenue as a share of the revenue so far (running total), one decimal.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH monthly AS (
      SELECT SUBSTR(CAST(o.order_date AS TEXT), 1, 7) AS month,
             SUM(i.quantity * i.unit_price) AS revenue
      FROM orders o
      JOIN order_items i ON i.order_id = o.order_id
      WHERE o.status = 'shipped'
      GROUP BY SUBSTR(CAST(o.order_date AS TEXT), 1, 7)
    )
    SELECT month, revenue,
           ROUND(100.0 * revenue / SUM(revenue) OVER (ORDER BY month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 1)
             AS pct_of_running_total
    FROM monthly
    ORDER BY month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | month | revenue | pct_of_running_total |
    | --- | --- | --- |
    | 2026-01 | 241.50 | 100.0 |
    | 2026-02 | 277.50 | 53.5 |
    | 2026-03 | 322.50 | 38.3 |
    | 2026-04 | 163.50 | 16.3 |
    <!-- /result -->

**Next:** [15. Classic interview patterns](15-Classic-Interview-Patterns.md).
