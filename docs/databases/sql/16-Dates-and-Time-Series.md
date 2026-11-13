# 16. Dates and time series

*Dates are where SQL dialects differ most, and where tests hide their nastiest edge cases: a month with no orders, a
timestamp at 3 pm on the last day of the range, a week that starts on Sunday in one system and Monday in another. This
chapter gives each common date task in both PostgreSQL and SQLite, side by side, then the two time-series patterns
every data engineer is asked about: filling in missing days, and cohort retention.*

!!! abstract "In this chapter"
    **You will learn:**

    - how PostgreSQL and SQLite store dates (SQLite has no date type at all)
    - taking a date apart: year, month, day of week
    - truncating to month and week, adding and subtracting, the end of the month
    - safe date ranges, and the `BETWEEN` trap with timestamps
    - a calendar of every day, joined to the data so empty days show as 0
    - cohorts and retention

    **You need:** [7. GROUP BY](07-Aggregation-Group-By-Having.md), [8. joins](08-Joins-Inner-Left-Right-Full-Cross.md), [11. CTEs](11-CTEs-and-Recursive-CTEs.md) and [14. LAG, LEAD, running totals](14-Window-Functions-Lag-Lead-Running-Totals.md).

## 16.1 How dates are stored { #storage }

**PostgreSQL** has real types: `DATE` (a day), `TIMESTAMP` (day and time), `TIMESTAMPTZ` (day and time, stored as
an exact instant and shown in the session's time zone), and `INTERVAL` (a length of time). Comparing and subtracting
them is built in.

**SQLite has no date type.** The sample database stores dates as text in the form `YYYY-MM-DD`, and SQLite's date
functions read and write that text. It works because ISO dates sort correctly as text: `'2026-02-10' <
'2026-03-01'` is true both as dates and as strings. It breaks if any date is written differently (`2026-3-1`,
`01/03/2026`), because then text order is no longer date order.

<!-- sql -->
```sql
SELECT '2026-02-10' < '2026-03-01' AS iso_text_sorts_right,
       '2026-10-01' < '2026-9-01'  AS unpadded_text_sorts_wrong;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| iso_text_sorts_right | unpadded_text_sorts_wrong |
| --- | --- |
| true | true |
<!-- /result -->

The second is "true" as text (`'1'` comes before `'9'`), although October is after September. In PostgreSQL these are
text literals too, so the result is the same; in a real PostgreSQL date column the comparison would be correct.

## 16.2 Taking a date apart { #parts }

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT order_id, order_date,
           EXTRACT(YEAR  FROM order_date) AS year,
           EXTRACT(MONTH FROM order_date) AS month,
           EXTRACT(DAY   FROM order_date) AS day,
           EXTRACT(DOW   FROM order_date) AS weekday_0_sunday,
           to_char(order_date, 'YYYY-MM') AS year_month
    FROM orders
    WHERE order_id IN (101, 109, 120)
    ORDER BY order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | order_id | order_date | year | month | day | weekday_0_sunday | year_month |
    | --- | --- | --- | --- | --- | --- | --- |
    | 101 | 2026-01-03 | 2026 | 1 | 3 | 6 | 2026-01 |
    | 109 | 2026-02-14 | 2026 | 2 | 14 | 6 | 2026-02 |
    | 120 | 2026-04-05 | 2026 | 4 | 5 | 0 | 2026-04 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    SELECT order_id, order_date,
           CAST(strftime('%Y', order_date) AS INTEGER) AS year,
           CAST(strftime('%m', order_date) AS INTEGER) AS month,
           CAST(strftime('%d', order_date) AS INTEGER) AS day,
           CAST(strftime('%w', order_date) AS INTEGER) AS weekday_0_sunday,
           strftime('%Y-%m', order_date) AS year_month
    FROM orders
    WHERE order_id IN (101, 109, 120)
    ORDER BY order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 3 rows.</p>

    | order_id | order_date | year | month | day | weekday_0_sunday | year_month |
    | --- | --- | --- | --- | --- | --- | --- |
    | 101 | 2026-01-03 | 2026 | 1 | 3 | 6 | 2026-01 |
    | 109 | 2026-02-14 | 2026 | 2 | 14 | 6 | 2026-02 |
    | 120 | 2026-04-05 | 2026 | 4 | 5 | 0 | 2026-04 |
    <!-- /result -->

`EXTRACT(part FROM d)` takes one part out of a date: `YEAR`, `MONTH`, `DAY`, or `DOW`, the day of the week. `to_char(d,
'YYYY-MM')` formats a date as text in the pattern you give. `strftime` returns text, so cast it when you need a
number. Both number the days of the week from 0 = Sunday here
(PostgreSQL's `ISODOW` gives 1 = Monday to 7 = Sunday). In PostgreSQL 14 and later, `EXTRACT` returns a `numeric`;
cast to `INTEGER` if a test compares types strictly.

A trick that works on both: `SUBSTR(CAST(d AS TEXT), 1, 7)` gives `YYYY-MM`, because both turn a date into ISO text.
This course uses it where one query must run on both databases.

## 16.3 Truncating: the start of the month and week { #truncate }

Grouping by month means mapping every date to the first day of its month:

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT order_date,
           CAST(date_trunc('month', order_date) AS DATE) AS month_start,
           CAST(date_trunc('week',  order_date) AS DATE) AS week_start_monday,
           CAST(date_trunc('month', order_date) + INTERVAL '1 month' - INTERVAL '1 day' AS DATE) AS month_end
    FROM orders
    WHERE order_id IN (101, 108, 113, 120)
    ORDER BY order_date;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | order_date | month_start | week_start_monday | month_end |
    | --- | --- | --- | --- |
    | 2026-01-03 | 2026-01-01 | 2025-12-29 | 2026-01-31 |
    | 2026-02-10 | 2026-02-01 | 2026-02-09 | 2026-02-28 |
    | 2026-03-05 | 2026-03-01 | 2026-03-02 | 2026-03-31 |
    | 2026-04-05 | 2026-04-01 | 2026-03-30 | 2026-04-30 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    SELECT order_date,
           date(order_date, 'start of month') AS month_start,
           date(order_date, '-6 days', 'weekday 1') AS week_start_monday,
           date(order_date, 'start of month', '+1 month', '-1 day') AS month_end
    FROM orders
    WHERE order_id IN (101, 108, 113, 120)
    ORDER BY order_date;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 4 rows.</p>

    | order_date | month_start | week_start_monday | month_end |
    | --- | --- | --- | --- |
    | 2026-01-03 | 2026-01-01 | 2025-12-29 | 2026-01-31 |
    | 2026-02-10 | 2026-02-01 | 2026-02-09 | 2026-02-28 |
    | 2026-03-05 | 2026-03-01 | 2026-03-02 | 2026-03-31 |
    | 2026-04-05 | 2026-04-01 | 2026-03-30 | 2026-04-30 |
    <!-- /result -->

`date_trunc` returns a timestamp, hence the cast back to DATE. PostgreSQL's weeks start on Monday (ISO weeks). SQLite's
`'weekday 1'` moves **forward** to the next Monday (or stays, if already Monday), so going back 6 days first lands on
the Monday of the same week. SQL Server and MySQL have different week rules again, configurable; if a task says
"week", check which day it starts on.

## 16.4 Adding and subtracting { #arithmetic }

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT order_date,
           order_date + 7                                     AS plus_7_days,
           CAST(order_date + INTERVAL '1 month' AS DATE)      AS plus_1_month,
           DATE '2026-04-30' - order_date                     AS days_until_30_april
    FROM orders
    WHERE order_id IN (101, 110)
    ORDER BY order_date;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | order_date | plus_7_days | plus_1_month | days_until_30_april |
    | --- | --- | --- | --- |
    | 2026-01-03 | 2026-01-10 | 2026-02-03 | 117 |
    | 2026-02-20 | 2026-02-27 | 2026-03-20 | 69 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    SELECT order_date,
           date(order_date, '+7 days')                                  AS plus_7_days,
           date(order_date, '+1 month')                                 AS plus_1_month,
           CAST(julianday('2026-04-30') - julianday(order_date) AS INTEGER) AS days_until_30_april
    FROM orders
    WHERE order_id IN (101, 110)
    ORDER BY order_date;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 2 rows.</p>

    | order_date | plus_7_days | plus_1_month | days_until_30_april |
    | --- | --- | --- | --- |
    | 2026-01-03 | 2026-01-10 | 2026-02-03 | 117 |
    | 2026-02-20 | 2026-02-27 | 2026-03-20 | 69 |
    <!-- /result -->

In PostgreSQL, `date + integer` is a date and `date - date` is a whole number of days. In SQLite, `julianday` turns
a date into a (fractional) day number, so subtracting two of them gives days.

**Adding a month to 31 January** is where the two disagree:

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT CAST(DATE '2026-01-31' + INTERVAL '1 month' AS DATE) AS jan31_plus_1_month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

    | jan31_plus_1_month |
    | --- |
    | 2026-02-28 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite -->
    ```sql
    SELECT date('2026-01-31', '+1 month') AS jan31_plus_1_month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

    | jan31_plus_1_month |
    | --- |
    | 2026-03-03 |
    <!-- /result -->

PostgreSQL clips to the last day of February; SQLite adds one to the month number, gets "31 February" and rolls over
into March. If month arithmetic on month-ends matters, work from the first of the month instead, which is safe in
both.

## 16.5 Date ranges: half-open is safe { #ranges }

To take "January", write **from the first of the month, up to but not including the first of the next**:

```text
WHERE order_date >= '2026-01-01' AND order_date < '2026-02-01'
```

`BETWEEN '2026-01-01' AND '2026-01-31'` looks the same, and it is, for a pure date. With a timestamp it drops most of
the last day:

**Task:** For two events on 31 January 2026 (midnight and 15:30), show whether each counts as January by `BETWEEN` and by a half-open range.

<!-- sql -->
```sql
WITH events AS (
  SELECT 1 AS id, '2026-01-31 00:00:00' AS ts UNION ALL
  SELECT 2,       '2026-01-31 15:30:00'
)
SELECT id, ts,
       CASE WHEN ts BETWEEN '2026-01-01' AND '2026-01-31'      THEN 'yes' ELSE 'no' END AS in_between,
       CASE WHEN ts >= '2026-01-01' AND ts < '2026-02-01'      THEN 'yes' ELSE 'no' END AS in_half_open
FROM events
ORDER BY id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| id | ts | in_between | in_half_open |
| --- | --- | --- | --- |
| 1 | 2026-01-31 00:00:00 | no | yes |
| 2 | 2026-01-31 15:30:00 | no | yes |
<!-- /result -->

Here the timestamps are text, so `BETWEEN` compares strings: `'2026-01-31 00:00:00'` is a longer string than
`'2026-01-31'`, sorts after it, and both events fall outside. With a real `TIMESTAMP` column the answer changes a
little, because `'2026-01-31'` becomes midnight at the start of the 31st:

**Task:** The same, with real timestamps on PostgreSQL.

<!-- sql pg -->
```sql
WITH events AS (
  SELECT 1 AS id, TIMESTAMP '2026-01-31 00:00:00' AS ts UNION ALL
  SELECT 2,       TIMESTAMP '2026-01-31 15:30:00'
)
SELECT id, ts,
       CASE WHEN ts BETWEEN '2026-01-01' AND '2026-01-31'      THEN 'yes' ELSE 'no' END AS in_between,
       CASE WHEN ts >= '2026-01-01' AND ts < '2026-02-01'      THEN 'yes' ELSE 'no' END AS in_half_open
FROM events
ORDER BY id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

| id | ts | in_between | in_half_open |
| --- | --- | --- | --- |
| 1 | 2026-01-31 00:00:00 | yes | yes |
| 2 | 2026-01-31 15:30:00 | no | yes |
<!-- /result -->

Midnight is now inside, but the 3:30 pm event is still not "between 1 and 31 January". Either way `BETWEEN` loses part
of the last day, and the half-open range is right for text and timestamps alike.

## 16.6 Every day, even the empty ones { #calendar }

Daily revenue for the first ten days of January, with the days that had no orders shown as 0. GROUP BY alone can only
show days that have rows, so make a calendar first and LEFT JOIN the data onto it.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    WITH days AS (
      SELECT CAST(d AS DATE) AS day
      FROM generate_series(DATE '2026-01-01', DATE '2026-01-10', INTERVAL '1 day') AS g(d)
    ),
    daily AS (
      SELECT o.order_date, SUM(i.quantity * i.unit_price) AS revenue
      FROM orders o JOIN order_items i ON i.order_id = o.order_id
      WHERE o.status = 'shipped'
      GROUP BY o.order_date
    )
    SELECT days.day, COALESCE(daily.revenue, 0) AS revenue
    FROM days
    LEFT JOIN daily ON daily.order_date = days.day
    ORDER BY days.day;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 10 rows.</p>

    | day | revenue |
    | --- | --- |
    | 2026-01-01 | 0 |
    | 2026-01-02 | 0 |
    | 2026-01-03 | 183.25 |
    | 2026-01-04 | 0 |
    | 2026-01-05 | 0 |
    | 2026-01-06 | 0 |
    | 2026-01-07 | 0 |
    | 2026-01-08 | 0 |
    | 2026-01-09 | 0 |
    | 2026-01-10 | 0 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    WITH RECURSIVE days AS (
      SELECT '2026-01-01' AS day
      UNION ALL
      SELECT date(day, '+1 day') FROM days WHERE day < '2026-01-10'
    ),
    daily AS (
      SELECT o.order_date, SUM(i.quantity * i.unit_price) AS revenue
      FROM orders o JOIN order_items i ON i.order_id = o.order_id
      WHERE o.status = 'shipped'
      GROUP BY o.order_date
    )
    SELECT days.day, COALESCE(daily.revenue, 0) AS revenue
    FROM days
    LEFT JOIN daily ON daily.order_date = days.day
    ORDER BY days.day;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 10 rows.</p>

    | day | revenue |
    | --- | --- |
    | 2026-01-01 | 0 |
    | 2026-01-02 | 0 |
    | 2026-01-03 | 183.25 |
    | 2026-01-04 | 0 |
    | 2026-01-05 | 0 |
    | 2026-01-06 | 0 |
    | 2026-01-07 | 0 |
    | 2026-01-08 | 0 |
    | 2026-01-09 | 0 |
    | 2026-01-10 | 0 |
    <!-- /result -->

Aggregate the data to one row per day **before** the join (the `daily` CTE), so the calendar's rows can't multiply.
With a full calendar, moving averages over "the last 7 days" (chapter 14) really are 7 days.

## 16.7 Cohorts and retention { #cohorts }

A **cohort** is a group of customers who started in the same period, usually the month of their first order.
**Retention** asks: of each cohort, how many came back 1, 2, 3 months later? It is a favourite data-engineering
question because it combines most of this course: a first-order CTE, month arithmetic, a join and conditional counts.

Months are turned into numbers (`year * 12 + month`) so that "months since the first order" is a subtraction that
works on both databases:

**Task:** For each month cohort (the month of a customer's first order), show how many customers it has and how many came back 1, 2 and 3 months later.

<!-- sql -->
```sql
WITH o AS (
  SELECT customer_id,
         CAST(SUBSTR(CAST(order_date AS TEXT), 1, 4) AS INTEGER) * 12
           + CAST(SUBSTR(CAST(order_date AS TEXT), 6, 2) AS INTEGER) AS month_no,
         SUBSTR(CAST(order_date AS TEXT), 1, 7) AS month
  FROM orders
  WHERE customer_id IS NOT NULL AND status <> 'cancelled'
),
firsts AS (
  SELECT customer_id, MIN(month_no) AS first_month_no, MIN(month) AS cohort
  FROM o
  GROUP BY customer_id
),
activity AS (
  SELECT DISTINCT f.cohort, f.customer_id, o.month_no - f.first_month_no AS months_after
  FROM firsts f
  JOIN o ON o.customer_id = f.customer_id
)
SELECT cohort,
       COUNT(DISTINCT customer_id)                        AS customers,
       SUM(CASE WHEN months_after = 1 THEN 1 ELSE 0 END)  AS back_month_1,
       SUM(CASE WHEN months_after = 2 THEN 1 ELSE 0 END)  AS back_month_2,
       SUM(CASE WHEN months_after = 3 THEN 1 ELSE 0 END)  AS back_month_3
FROM activity
GROUP BY cohort
ORDER BY cohort;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| cohort | customers | back_month_1 | back_month_2 | back_month_3 |
| --- | --- | --- | --- | --- |
| 2026-01 | 3 | 2 | 2 | 1 |
| 2026-02 | 3 | 1 | 1 | 0 |
| 2026-03 | 2 | 0 | 0 | 0 |
| 2026-04 | 1 | 0 | 0 | 0 |
<!-- /result -->

Read the first row: three customers placed their first (non-cancelled) order in January; of them, how many ordered
again one, two and three months later. `DISTINCT` in `activity` makes a customer count once per month however many
orders they placed in it. Divide each "back" column by `customers` (times 100.0) for retention percentages. Later
cohorts have fewer months to come back in, which is why their right-hand columns are 0: not lost, just not yet.

## 16.8 Summary { #summary }

| Task | PostgreSQL | SQLite |
| --- | --- | --- |
| year (number) | `EXTRACT(YEAR FROM d)` | `CAST(strftime('%Y', d) AS INTEGER)` |
| `YYYY-MM` text | `to_char(d, 'YYYY-MM')` | `strftime('%Y-%m', d)` |
| first of month | `CAST(date_trunc('month', d) AS DATE)` | `date(d, 'start of month')` |
| Monday of the week | `CAST(date_trunc('week', d) AS DATE)` | `date(d, '-6 days', 'weekday 1')` |
| last of month | `CAST(date_trunc('month', d) + INTERVAL '1 month' - INTERVAL '1 day' AS DATE)` | `date(d, 'start of month', '+1 month', '-1 day')` |
| plus 7 days | `d + 7` | `date(d, '+7 days')` |
| days between | `d2 - d1` | `julianday(d2) - julianday(d1)` |
| every day in a range | `generate_series(a, b, INTERVAL '1 day')` | recursive CTE |
| on both | `SUBSTR(CAST(d AS TEXT), 1, 7)` for `YYYY-MM` | the same |

- Use half-open ranges: `>= start AND < next start`.
- Build a calendar and LEFT JOIN to show empty periods.
- Number months as `year * 12 + month` to do month arithmetic portably.

## Practice { #practice }

**16.1** The number of orders on each day of the week (0 = Sunday), busiest first. Write it for one database of your
choice; the answer gives both.

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        SELECT CAST(EXTRACT(DOW FROM order_date) AS INTEGER) AS weekday, COUNT(*) AS orders
        FROM orders
        GROUP BY 1
        ORDER BY orders DESC, weekday;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 7 rows.</p>

        | weekday | orders |
        | --- | --- |
        | 3 | 4 |
        | 6 | 4 |
        | 0 | 3 |
        | 1 | 3 |
        | 4 | 3 |
        | 2 | 2 |
        | 5 | 1 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        SELECT CAST(strftime('%w', order_date) AS INTEGER) AS weekday, COUNT(*) AS orders
        FROM orders
        GROUP BY 1
        ORDER BY orders DESC, weekday;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 7 rows.</p>

        | weekday | orders |
        | --- | --- |
        | 3 | 4 |
        | 6 | 4 |
        | 0 | 3 |
        | 1 | 3 |
        | 4 | 3 |
        | 2 | 2 |
        | 5 | 1 |
        <!-- /result -->

    Both versions take the day of the week out of the date as a number (0 = Sunday): `EXTRACT(DOW FROM d)` on
    PostgreSQL, `strftime('%w', d)` on SQLite, which returns text and so is cast to a number. `GROUP BY 1` means
    "group by the first column of the SELECT".


**16.2** For each customer, the number of days from signing up to their first order. Customers without orders are
left out. (PostgreSQL.)

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT c.customer_id, c.signup_date, MIN(o.order_date) AS first_order,
           MIN(o.order_date) - c.signup_date AS days_to_first_order
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    GROUP BY c.customer_id, c.signup_date
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 9 rows.</p>

    | customer_id | signup_date | first_order | days_to_first_order |
    | --- | --- | --- | --- |
    | 1 | 2025-11-03 | 2026-01-03 | 61 |
    | 2 | 2025-12-10 | 2026-01-03 | 24 |
    | 3 | 2026-01-05 | 2026-01-20 | 15 |
    | 4 | 2026-01-05 | 2026-01-28 | 23 |
    | 5 | 2026-01-20 | 2026-02-02 | 13 |
    | 6 | 2026-02-02 | 2026-02-14 | 12 |
    | 7 | 2026-02-14 | 2026-02-21 | 7 |
    | 8 | 2026-02-28 | 2026-03-09 | 9 |
    | 10 | 2026-03-15 | 2026-03-25 | 10 |
    <!-- /result -->

    In SQLite: `CAST(julianday(MIN(o.order_date)) - julianday(c.signup_date) AS INTEGER)`.

**16.3** Weekly shipped revenue (weeks starting Monday) for February 2026, with the week's Monday as the label.

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        SELECT CAST(date_trunc('week', o.order_date) AS DATE) AS week_start,
               SUM(i.quantity * i.unit_price) AS revenue
        FROM orders o JOIN order_items i ON i.order_id = o.order_id
        WHERE o.status = 'shipped'
          AND o.order_date >= '2026-02-01' AND o.order_date < '2026-03-01'
        GROUP BY 1
        ORDER BY 1;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

        | week_start | revenue |
        | --- | --- |
        | 2026-02-02 | 93.25 |
        | 2026-02-09 | 115.00 |
        | 2026-02-16 | 69.25 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        SELECT date(o.order_date, '-6 days', 'weekday 1') AS week_start,
               SUM(i.quantity * i.unit_price) AS revenue
        FROM orders o JOIN order_items i ON i.order_id = o.order_id
        WHERE o.status = 'shipped'
          AND o.order_date >= '2026-02-01' AND o.order_date < '2026-03-01'
        GROUP BY 1
        ORDER BY 1;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 3 rows.</p>

        | week_start | revenue |
        | --- | --- |
        | 2026-02-02 | 93.25 |
        | 2026-02-09 | 115 |
        | 2026-02-16 | 69.25 |
        <!-- /result -->

    No shipped order falls on Sunday 1 February, so every week here starts in February. Had one fallen there, it would
    show under week_start 2026-01-26, a Monday in the month before: say in your answer which you mean.

**16.4** Customers whose most recent order is more than 30 days before 5 April 2026 (the last order date in the data):
a "lapsed customers" list. PostgreSQL.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT customer_id, MAX(order_date) AS last_order,
           DATE '2026-04-05' - MAX(order_date) AS days_since
    FROM orders
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
    HAVING DATE '2026-04-05' - MAX(order_date) > 30
    ORDER BY days_since DESC, customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | customer_id | last_order | days_since |
    | --- | --- | --- |
    | 7 | 2026-02-21 | 43 |
    | 4 | 2026-03-01 | 35 |
    | 2 | 2026-03-05 | 31 |
    <!-- /result -->

    In a real system the reference date would be `CURRENT_DATE` (SQLite: `date('now')`); a fixed date keeps the
    answer the same whenever you run it.

**Next:** Part III starts with [17. INSERT, UPDATE, DELETE, MERGE](17-Insert-Update-Delete-Merge.md). For the
interview, go to [30. Practice set A](30-Practice-Set-A.md).
