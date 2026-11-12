# 30. Practice set A

*Fifteen questions in the style of an online SQL test, easy to medium, all on the [shop
database](sample-database.md#tables). Each one says exactly which columns to return, in which order, and how to
sort, the way a test task does. Write your query first, then open the answer. Every answer below ran on PostgreSQL 16
and SQLite 3.53, and most answers also show the wrong query people usually write, with what it really returns.*

!!! abstract "How to use this set"
    - Give yourself about 10 minutes a question, the pace of a timed test. Write the query on paper or in a real
      database (the [sample database](sample-database.md) page shows how to load it), then open the answer.
    - **Columns in the order asked.** A test checker usually compares your rows with its own, column by column. On
      Codility's public practice SQL tasks the column order matters and the column names do not; the format of any
      real test you are sent is not known in advance, so match the question exactly.
    - **Watch for the edge cases.** The data has a guest order with no customer, a customer with no orders, a product
      never sold, NULL emails, cities and salaries, tied prices and salaries, a duplicated login, and two sales below
      list price. Most questions here touch at least one of them, as test data does.
    - Where an answer depends on the database, it is given for PostgreSQL and SQLite in tabs.

    **You need:** chapters 7 to 16, from [7. GROUP BY](07-Aggregation-Group-By-Having.md) to [16. dates](16-Dates-and-Time-Series.md). Each answer names the chapter to go back to if it surprised you.

## Questions { #questions }

**A.1** Customers who have no email address. Return `customer_id`, `name`, sorted by `customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id, name
    FROM customers
    WHERE email IS NULL
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | customer_id | name |
    | --- | --- |
    | 3 | Chen Wei |
    | 8 | Hana Sato |
    <!-- /result -->

    The usual wrong answer is `WHERE email = NULL`. It is not an error, it just returns nothing, because a comparison
    with NULL is never true:

    <!-- sql -->
    ```sql
    SELECT customer_id, name
    FROM customers
    WHERE email = NULL
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

    | customer_id | name |
    | --- | --- |
    | *(no rows)* | |
    <!-- /result -->

    Back to: [6. NULL and three-valued logic](06-Null-and-Three-Valued-Logic.md).

**A.2** Every customer with the number of shipped orders they placed, 0 for none. Return `customer_id`, `name`,
`shipped_orders`, sorted by `shipped_orders` from most to fewest, then by `customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name, COUNT(o.order_id) AS shipped_orders
    FROM customers c
    LEFT JOIN orders o
      ON o.customer_id = c.customer_id
     AND o.status = 'shipped'
    GROUP BY c.customer_id, c.name
    ORDER BY shipped_orders DESC, c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

    | customer_id | name | shipped_orders |
    | --- | --- | --- |
    | 1 | Ana Silva | 5 |
    | 2 | Ben Okafor | 2 |
    | 4 | Dana Kim | 2 |
    | 3 | Chen Wei | 1 |
    | 5 | Eli Cohen | 1 |
    | 6 | Farah Haddad | 1 |
    | 7 | Gus Novak | 1 |
    | 8 | Hana Sato | 1 |
    | 10 | Ana Silva | 1 |
    | 9 | Ivan Petrov | 0 |
    <!-- /result -->

    Two things make it right. The status test sits in `ON`, so customers with no shipped order keep their row; and
    `COUNT(o.order_id)` counts only real orders, so those rows count 0. The usual wrong answer puts the status in
    `WHERE` and counts `*`:

    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name, COUNT(*) AS shipped_orders
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.customer_id
    WHERE o.status = 'shipped'
    GROUP BY c.customer_id, c.name
    ORDER BY shipped_orders DESC, c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | customer_id | name | shipped_orders |
    | --- | --- | --- |
    | 1 | Ana Silva | 5 |
    | 2 | Ben Okafor | 2 |
    | 4 | Dana Kim | 2 |
    | 3 | Chen Wei | 1 |
    | 5 | Eli Cohen | 1 |
    | 6 | Farah Haddad | 1 |
    | 7 | Gus Novak | 1 |
    | 8 | Hana Sato | 1 |
    | 10 | Ana Silva | 1 |
    <!-- /result -->

    Ivan Petrov (9) is missing: the `WHERE` removed every customer without a shipped order, which turned the left
    join back into an inner join. Back to: [8.4 ON or
    WHERE](08-Joins-Inner-Left-Right-Full-Cross.md#on-vs-where) and [the COUNT trap](08-Joins-Inner-Left-Right-Full-Cross.md#count-left).

**A.3** The three products with the most units sold in shipped orders. Return `product_id`, `name`, `units`, sorted
by `units` from most to fewest; if units tie, the product with the lower `product_id` first.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT p.product_id, p.name, SUM(i.quantity) AS units
    FROM products p
    JOIN order_items i ON i.product_id = p.product_id
    JOIN orders o      ON o.order_id = i.order_id
    WHERE o.status = 'shipped'
    GROUP BY p.product_id, p.name
    ORDER BY units DESC, p.product_id
    LIMIT 3;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | product_id | name | units |
    | --- | --- | --- |
    | 2 | Notebook | 25 |
    | 4 | Coffee mug | 9 |
    | 1 | Desk lamp | 5 |
    <!-- /result -->

    This data has no tie at the cut-off (the next product has 4 units), but a test's hidden data may. Without the
    tie-break (`, p.product_id`) the third row could then be either of two products with the same units, and a checker
    comparing rows would mark it wrong on some runs. SQL Server writes `SELECT TOP 3 ...` or `OFFSET 0 ROWS
    FETCH NEXT 3 ROWS ONLY` instead of `LIMIT`. Back to: [7. Aggregates and GROUP BY](07-Aggregation-Group-By-Having.md).

**A.4** The average value of a shipped order, where an order's value is the sum of quantity × unit price over its
lines. Return one column, `avg_order_value`, rounded to 2 decimal places.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH order_values AS (
      SELECT o.order_id, SUM(i.quantity * i.unit_price) AS order_value
      FROM orders o
      JOIN order_items i ON i.order_id = o.order_id
      WHERE o.status = 'shipped'
      GROUP BY o.order_id
    )
    SELECT ROUND(AVG(order_value), 2) AS avg_order_value
    FROM order_values;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | avg_order_value |
    | --- |
    | 62.81 |
    <!-- /result -->

    First one row per order, then the average of those rows. The usual wrong answer averages the lines instead, which
    gives the average line value, a different number:

    <!-- sql -->
    ```sql
    SELECT ROUND(AVG(i.quantity * i.unit_price), 2) AS avg_order_value
    FROM orders o
    JOIN order_items i ON i.order_id = o.order_id
    WHERE o.status = 'shipped';
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | avg_order_value |
    | --- |
    | 38.65 |
    <!-- /result -->

    Back to: [11. CTEs](11-CTEs-and-Recursive-CTEs.md) and [the fan-out](08-Joins-Inner-Left-Right-Full-Cross.md#fan-out).

**A.5** The logins table should hold at most one row per customer per day. Find the rows that break this. Return
`customer_id`, `login_date`, `copies` (how many times the pair appears), sorted by `customer_id`, then `login_date`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id, login_date, COUNT(*) AS copies
    FROM logins
    GROUP BY customer_id, login_date
    HAVING COUNT(*) > 1
    ORDER BY customer_id, login_date;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | customer_id | login_date | copies |
    | --- | --- | --- |
    | 2 | 2026-03-02 | 2 |
    <!-- /result -->

    Group by every column that defines "the same row", keep the groups with more than one. `HAVING`, not `WHERE`:
    the count exists only after grouping. Back to: [15. Classic patterns](15-Classic-Interview-Patterns.md).

**A.6** Customers whose name is shared with at least one other customer. Return `customer_id`, `name`, `email`,
sorted by `name`, then `customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name, c.email
    FROM customers c
    WHERE EXISTS (
      SELECT 1
      FROM customers d
      WHERE d.name = c.name
        AND d.customer_id <> c.customer_id
    )
    ORDER BY c.name, c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | customer_id | name | email |
    | --- | --- | --- |
    | 1 | Ana Silva | ana@example.com |
    | 10 | Ana Silva | ana.silva@example.com |
    <!-- /result -->

    The question wants the rows themselves, not just the duplicated name, so `GROUP BY name HAVING COUNT(*) > 1` alone
    is not enough: it returns one row, `Ana Silva`, and no ids. Either use `EXISTS` as here, or join the grouped names
    back to the table. The `d.customer_id <> c.customer_id` stops every customer matching themselves. Back to:
    [9. Semi and anti joins](09-Self-Semi-and-Anti-Joins.md).

**A.7** Employees who earn more than the average salary of their own department (the average of the known
salaries). Return `name`, `department`, `salary`, `dept_avg` (rounded to 0 decimal places), sorted by `department`,
then `salary` from highest, then `name`.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH d AS (
      SELECT department, AVG(salary) AS dept_avg
      FROM employees
      GROUP BY department
    )
    SELECT e.name, e.department, e.salary, ROUND(d.dept_avg, 0) AS dept_avg
    FROM employees e
    JOIN d ON d.department = e.department
    WHERE e.salary > d.dept_avg
    ORDER BY e.department, e.salary DESC, e.name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | name | department | salary | dept_avg |
    | --- | --- | --- | --- |
    | Tom Becker | Engineering | 140000 | 118750 |
    | Priya Nair | Engineering | 120000 | 118750 |
    | Sam Lee | Engineering | 120000 | 118750 |
    | Omar Aziz | Sales | 110000 | 78750 |
    | Kwame Mensah | Support | 75000 | 63500 |
    <!-- /result -->

    `AVG` skips Leo Park's NULL salary, so Support's average is that of the two known salaries; Leo's own row drops out
    because `NULL > 63500` is not true. Management has one person, who cannot earn more than their own average. If the
    question had said "treat a missing salary as 0", the average would be `AVG(COALESCE(salary, 0))`. On SQLite,
    `ROUND(x, 0)` returns a decimal such as `63500.0`; the values are the same. Back to: [10. Correlated
    subqueries](10-Subqueries.md#correlated).

**A.8** For each department, the employees who are paid one of the two highest salary levels in it (equal salaries
are one level). Return `department`, `name`, `salary`, `salary_level` (1 for the highest), sorted by `department`,
`salary_level`, then `name`. Employees with no salary are left out.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH ranked AS (
      SELECT department, name, salary,
             DENSE_RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS salary_level
      FROM employees
      WHERE salary IS NOT NULL
    )
    SELECT department, name, salary, salary_level
    FROM ranked
    WHERE salary_level <= 2
    ORDER BY department, salary_level, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | department | name | salary | salary_level |
    | --- | --- | --- | --- |
    | Engineering | Tom Becker | 140000 | 1 |
    | Engineering | Priya Nair | 120000 | 2 |
    | Engineering | Sam Lee | 120000 | 2 |
    | Management | Maya Rossi | 180000 | 1 |
    | Sales | Omar Aziz | 110000 | 1 |
    | Sales | Nina Berg | 70000 | 2 |
    | Sales | Raj Patel | 70000 | 2 |
    | Support | Kwame Mensah | 75000 | 1 |
    | Support | Ella Novak | 52000 | 2 |
    <!-- /result -->

    "Salary levels" means `DENSE_RANK`: Priya Nair and Sam Lee share level 2 in Engineering, and so do Nina Berg and
    Raj Patel in Sales. `ROW_NUMBER` would cut one of each pair, and `RANK` would number the salary after a tie 4
    instead of 3, so after a tie at the top (1, 1, 3) the second salary level would be missed. The filter on `salary_level` needs the CTE because a window result cannot be used in `WHERE` of the same
    query. Leaving out `WHERE salary IS NOT NULL` would matter here: PostgreSQL sorts NULL first in a descending order,
    so Leo Park would take level 1 in Support. Back to: [13. Ranking](13-Window-Functions-Ranking.md).

**A.9** Shipped revenue per month and the change from the previous month. Return `month` (as `YYYY-MM`), `revenue`,
`prev_revenue` (NULL for the first month), `change_pct` (the change as a percentage of the previous month, rounded
to 1 decimal place), sorted by `month`.

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
           LAG(revenue) OVER (ORDER BY month) AS prev_revenue,
           ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
                 / LAG(revenue) OVER (ORDER BY month), 1) AS change_pct
    FROM monthly
    ORDER BY month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | month | revenue | prev_revenue | change_pct |
    | --- | --- | --- | --- |
    | 2026-01 | 241.50 | *NULL* | *NULL* |
    | 2026-02 | 277.50 | 241.50 | 14.9 |
    | 2026-03 | 322.50 | 277.50 | 16.2 |
    | 2026-04 | 163.50 | 322.50 | -49.3 |
    <!-- /result -->

    `SUBSTR(CAST(date AS TEXT), 1, 7)` gives `YYYY-MM` on both databases (PostgreSQL could also use
    `to_char(order_date, 'YYYY-MM')`, SQLite `strftime('%Y-%m', order_date)`). The `100.0` keeps the division
    decimal; with whole-number columns `100 * a / b` would divide as integers. Repeating `LAG(...)` three times is
    fine; a second CTE that computes it once is tidier. If a month could have a previous revenue of 0, wrap the
    divisor as `NULLIF(..., 0)` to get NULL instead of a division-by-zero error. Back to: [14. LAG and
    LEAD](14-Window-Functions-Lag-Lead-Running-Totals.md).

**A.10** Customers who placed an order (any status) in January 2026 and also in March 2026. Return `customer_id`,
sorted by `customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id
    FROM orders
    WHERE order_date >= '2026-01-01' AND order_date < '2026-02-01'
    INTERSECT
    SELECT customer_id
    FROM orders
    WHERE order_date >= '2026-03-01' AND order_date < '2026-04-01'
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_id |
    | --- |
    | 1 |
    | 2 |
    | 4 |
    <!-- /result -->

    The same answer by conditional aggregation, which also works where `INTERSECT` is missing (MySQL before 8.0.31):

    <!-- sql same -->
    ```sql
    SELECT customer_id
    FROM orders
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
    HAVING SUM(CASE WHEN order_date >= '2026-01-01' AND order_date < '2026-02-01' THEN 1 ELSE 0 END) > 0
       AND SUM(CASE WHEN order_date >= '2026-03-01' AND order_date < '2026-04-01' THEN 1 ELSE 0 END) > 0
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 3 rows.</p>

    | customer_id |
    | --- |
    | 1 |
    | 2 |
    | 4 |
    <!-- /result -->

    The usual wrong answer is `WHERE order_date in January AND order_date in March` on one row, which can never be
    true and returns nothing: one order has one date. Back to: [12. Set operations](12-Set-Operations.md).

**A.11** Shipped orders whose value is above the average shipped order value. Return `order_id`, `customer_id`,
`order_value`, sorted by `order_value` from highest, then `order_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH order_values AS (
      SELECT o.order_id, o.customer_id, SUM(i.quantity * i.unit_price) AS order_value
      FROM orders o
      JOIN order_items i ON i.order_id = o.order_id
      WHERE o.status = 'shipped'
      GROUP BY o.order_id, o.customer_id
    )
    SELECT order_id, customer_id, order_value
    FROM order_values
    WHERE order_value > (SELECT AVG(order_value) FROM order_values)
    ORDER BY order_value DESC, order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | order_id | customer_id | order_value |
    | --- | --- | --- |
    | 112 | 4 | 181.00 |
    | 102 | 2 | 149.00 |
    | 120 | 1 | 139.00 |
    | 109 | 6 | 65.00 |
    <!-- /result -->

    The average from A.4 is used here without being typed in: the scalar subquery reads the same CTE. Writing
    `WHERE order_value > AVG(order_value)` is an error, because an aggregate cannot sit in `WHERE`. Back to:
    [10. Subqueries](10-Subqueries.md).

**A.12** For each customer with at least two orders (any status): the dates of their first and last order and the
number of days between them. Return `customer_id`, `first_order`, `last_order`, `days_between`, sorted by
`days_between` from most, then `customer_id`.

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        SELECT customer_id,
               MIN(order_date) AS first_order,
               MAX(order_date) AS last_order,
               MAX(order_date) - MIN(order_date) AS days_between
        FROM orders
        WHERE customer_id IS NOT NULL
        GROUP BY customer_id
        HAVING COUNT(*) >= 2
        ORDER BY days_between DESC, customer_id;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 6 rows.</p>

        | customer_id | first_order | last_order | days_between |
        | --- | --- | --- | --- |
        | 1 | 2026-01-03 | 2026-04-05 | 92 |
        | 3 | 2026-01-20 | 2026-04-01 | 71 |
        | 2 | 2026-01-03 | 2026-03-05 | 61 |
        | 5 | 2026-02-02 | 2026-04-02 | 59 |
        | 6 | 2026-02-14 | 2026-03-22 | 36 |
        | 4 | 2026-01-28 | 2026-03-01 | 32 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        SELECT customer_id,
               MIN(order_date) AS first_order,
               MAX(order_date) AS last_order,
               CAST(julianday(MAX(order_date)) - julianday(MIN(order_date)) AS INTEGER) AS days_between
        FROM orders
        WHERE customer_id IS NOT NULL
        GROUP BY customer_id
        HAVING COUNT(*) >= 2
        ORDER BY days_between DESC, customer_id;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 6 rows.</p>

        | customer_id | first_order | last_order | days_between |
        | --- | --- | --- | --- |
        | 1 | 2026-01-03 | 2026-04-05 | 92 |
        | 3 | 2026-01-20 | 2026-04-01 | 71 |
        | 2 | 2026-01-03 | 2026-03-05 | 61 |
        | 5 | 2026-02-02 | 2026-04-02 | 59 |
        | 6 | 2026-02-14 | 2026-03-22 | 36 |
        | 4 | 2026-01-28 | 2026-03-01 | 32 |
        <!-- /result -->

    In PostgreSQL, one `DATE` minus another is a whole number of days. SQLite stores dates as text, so convert with
    `julianday` and cast the difference. `WHERE customer_id IS NOT NULL` keeps the guest order from forming a "customer
    NULL" group (it has only one order, so `HAVING` would drop it anyway, but a test can add a second). Back to:
    [16. Dates](16-Dates-and-Time-Series.md).

**A.13** Daily active customers for 1 to 10 March 2026: for each day, the number of different customers who logged in,
0 on days with no logins. Return `day`, `active_customers`, sorted by `day`.

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        WITH RECURSIVE days AS (
          SELECT DATE '2026-03-01' AS day
          UNION ALL
          SELECT day + 1 FROM days WHERE day < DATE '2026-03-10'
        )
        SELECT d.day, COUNT(DISTINCT l.customer_id) AS active_customers
        FROM days d
        LEFT JOIN logins l ON l.login_date = d.day
        GROUP BY d.day
        ORDER BY d.day;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 10 rows.</p>

        | day | active_customers |
        | --- | --- |
        | 2026-03-01 | 2 |
        | 2026-03-02 | 2 |
        | 2026-03-03 | 2 |
        | 2026-03-04 | 2 |
        | 2026-03-05 | 2 |
        | 2026-03-06 | 2 |
        | 2026-03-07 | 0 |
        | 2026-03-08 | 1 |
        | 2026-03-09 | 0 |
        | 2026-03-10 | 1 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        WITH RECURSIVE days AS (
          SELECT '2026-03-01' AS day
          UNION ALL
          SELECT date(day, '+1 day') FROM days WHERE day < '2026-03-10'
        )
        SELECT d.day, COUNT(DISTINCT l.customer_id) AS active_customers
        FROM days d
        LEFT JOIN logins l ON l.login_date = d.day
        GROUP BY d.day
        ORDER BY d.day;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 10 rows.</p>

        | day | active_customers |
        | --- | --- |
        | 2026-03-01 | 2 |
        | 2026-03-02 | 2 |
        | 2026-03-03 | 2 |
        | 2026-03-04 | 2 |
        | 2026-03-05 | 2 |
        | 2026-03-06 | 2 |
        | 2026-03-07 | 0 |
        | 2026-03-08 | 1 |
        | 2026-03-09 | 0 |
        | 2026-03-10 | 1 |
        <!-- /result -->

    Three traps in one question. Days with no logins (7 and 9 March) appear only because the calendar is generated
    and the logins are left-joined to it. `COUNT(DISTINCT ...)` stops customer 2's duplicated login on 2 March from
    counting twice. And `COUNT(l.customer_id)`, not `COUNT(*)`, gives 0 for an empty day. Back to: [16.6 Every
    day](16-Dates-and-Time-Series.md#calendar) and [11. Recursive CTEs](11-CTEs-and-Recursive-CTEs.md#recursive).

**A.14** The number of customers who signed up each month and the running total of customers so far. Return
`month` (`YYYY-MM`), `new_customers`, `total_customers`, sorted by `month`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT SUBSTR(CAST(signup_date AS TEXT), 1, 7) AS month,
           COUNT(*) AS new_customers,
           SUM(COUNT(*)) OVER (ORDER BY SUBSTR(CAST(signup_date AS TEXT), 1, 7)) AS total_customers
    FROM customers
    GROUP BY SUBSTR(CAST(signup_date AS TEXT), 1, 7)
    ORDER BY month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | month | new_customers | total_customers |
    | --- | --- | --- |
    | 2025-11 | 1 | 1 |
    | 2025-12 | 1 | 2 |
    | 2026-01 | 3 | 5 |
    | 2026-02 | 3 | 8 |
    | 2026-03 | 2 | 10 |
    <!-- /result -->

    `SUM(COUNT(*)) OVER (...)` is a window over the grouped rows: `GROUP BY` runs first, then the window adds up the
    monthly counts in order. It reads oddly the first time; a CTE with the monthly counts and then
    `SUM(new_customers) OVER (ORDER BY month)` gives the same rows. Back to: [14. Running
    totals](14-Window-Functions-Lag-Lead-Running-Totals.md) and [aggregates as windows](13-Window-Functions-Ranking.md#aggregate-windows).

**A.15** Next-day retention: of the customers who have logged in, the percentage who logged in again on the day after
their first login. Return one column, `retention_pct`, rounded to 1 decimal place.

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        WITH first_login AS (
          SELECT customer_id, MIN(login_date) AS first_day
          FROM logins
          GROUP BY customer_id
        )
        SELECT ROUND(100.0 * COUNT(DISTINCT l.customer_id) / COUNT(DISTINCT f.customer_id), 1) AS retention_pct
        FROM first_login f
        LEFT JOIN logins l
          ON l.customer_id = f.customer_id
         AND l.login_date = f.first_day + 1;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

        | retention_pct |
        | --- |
        | 75.0 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        WITH first_login AS (
          SELECT customer_id, MIN(login_date) AS first_day
          FROM logins
          GROUP BY customer_id
        )
        SELECT ROUND(100.0 * COUNT(DISTINCT l.customer_id) / COUNT(DISTINCT f.customer_id), 1) AS retention_pct
        FROM first_login f
        LEFT JOIN logins l
          ON l.customer_id = f.customer_id
         AND l.login_date = date(f.first_day, '+1 day');
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 1 row.</p>

        | retention_pct |
        | --- |
        | 75 |
        <!-- /result -->

    Customers 1, 2 and 4 came back the next day; customer 6 did not: 3 of 4. The left join keeps every customer in the
    denominator, and `COUNT(DISTINCT l.customer_id)` counts only those with a matching next-day login (once each,
    even with a duplicated login). An inner join would drop customer 6 from both counts and give 100.0. "Customers who
    have logged in" are the denominator here; if the question had said "of all customers", it would be
    `customers` left-joined instead. Back to: [8. Joins](08-Joins-Inner-Left-Right-Full-Cross.md) and [16.
    Dates](16-Dates-and-Time-Series.md).

## After this set { #next }

If you got most of these right without opening an answer, you are ready for the timed tests in [32. Mock
tests](32-Mock-Tests.md). If one kind kept catching you, the "Back to" line under each answer names the chapter.
[31. Practice set B](31-Practice-Set-B.md) is harder: more steps per question, and the patterns from chapters 15 and
16 combined.

**Next:** Part I starts at [1. Tables, rows and keys](01-Tables-Rows-and-Keys.md), if you want the foundations from
the start; for the interview, [31. Practice set B](31-Practice-Set-B.md).
