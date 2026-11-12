# SQL drills: quick reps on the shop

*Short exercises, one idea each, on the [sample database](sample-database.md), to build speed before a test.
Each has a **Try it here** box: write the query, press **Check**, and only then open the answer. Aim for two to five
minutes each. If one takes longer, read the chapter named under the group's heading, then come back.*

!!! abstract "How to use the drills"
    - Do a group in one sitting, without looking at earlier answers.
    - Say the **shape** of the result before you type: which columns, one row per what, which order.
    - When Check says "Not yet", read its message: it names the first row or column that differs.
    - The column **names** must match the task's, and so must the **order** of rows when the task says how to sort.
    - Every answer was run on PostgreSQL 16 and SQLite 3.53 (or PostgreSQL only, where it says so) and gave the
      result shown.

## A. Filters and NULL { #filters }

Chapters [2](02-Select-Where-Order-By-Limit.md) and [6](06-Null-and-Three-Valued-Logic.md).

**D.1** Products that cost between 10 and 30, both included. Return `name`, `price`, cheapest first, then by name.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, price
    FROM products
    WHERE price BETWEEN 10 AND 30
    ORDER BY price, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | name | price |
    | --- | --- |
    | Plant pot | 12.25 |
    | Fountain pen | 18.00 |
    | Desk lamp | 24.50 |
    | Wall clock | 24.50 |
    | Gift card | 25.00 |
    <!-- /result -->

    `BETWEEN` includes both ends. The two products at 24.50 are sorted by name, the tie-break.

**D.2** Customers with no email **or** no city. Return `customer_id`, `email`, `city`, sorted by `customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id, email, city
    FROM customers
    WHERE email IS NULL OR city IS NULL
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_id | email | city |
    | --- | --- | --- |
    | 3 | *NULL* | Shanghai |
    | 5 | eli@example.com | *NULL* |
    | 8 | *NULL* | Osaka |
    <!-- /result -->

**D.3** Customers who are **not** in Toronto, including the one whose city is unknown. Return `customer_id`, `city`,
sorted by `customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id, city
    FROM customers
    WHERE city <> 'Toronto' OR city IS NULL
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 7 rows.</p>

    | customer_id | city |
    | --- | --- |
    | 2 | Lagos |
    | 3 | Shanghai |
    | 4 | Seoul |
    | 5 | *NULL* |
    | 7 | Prague |
    | 8 | Osaka |
    | 10 | Lisbon |
    <!-- /result -->

    `city <> 'Toronto'` alone loses customer 5: comparing `NULL` with anything is unknown, and `WHERE` keeps only
    rows where the condition is true. `city IS DISTINCT FROM 'Toronto'` does the same in one test (PostgreSQL, and
    SQLite from version 3.39).

**D.4** Employees whose salary is unknown, or less than 60,000. Return `name`, `salary`, sorted by `name`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, salary
    FROM employees
    WHERE salary IS NULL OR salary < 60000
    ORDER BY name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | name | salary |
    | --- | --- |
    | Ella Novak | 52000 |
    | Leo Park | *NULL* |
    <!-- /result -->

**D.5** Each customer's email, or the text `'(none)'` when it is missing. Return `name`, `email_shown`, sorted by
`customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, COALESCE(email, '(none)') AS email_shown
    FROM customers
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

    | name | email_shown |
    | --- | --- |
    | Ana Silva | ana@example.com |
    | Ben Okafor | ben@example.com |
    | Chen Wei | (none) |
    | Dana Kim | dana@example.com |
    | Eli Cohen | eli@example.com |
    | Farah Haddad | farah@example.com |
    | Gus Novak | gus@example.com |
    | Hana Sato | (none) |
    | Ivan Petrov | ivan@example.com |
    | Ana Silva | ana.silva@example.com |
    <!-- /result -->

**D.6** The three most expensive products. If several share the third price, return only three rows, the ones
first by name. Return `name`, `price`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, price
    FROM products
    ORDER BY price DESC, name
    LIMIT 3;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | name | price |
    | --- | --- |
    | Office chair | 149.00 |
    | Monitor stand | 32.00 |
    | Tea kettle | 32.00 |
    <!-- /result -->

    Two products share the third price, 32.00. Here both fit in the three rows, but with one more tie the
    tie-break `name` would decide which ones are kept; without a tie-break, `LIMIT` may return either.

## B. GROUP BY and HAVING { #grouping }

Chapter [7](07-Aggregation-Group-By-Having.md).

**D.7** The number of orders in each status. Return `status`, `orders`, most orders first.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT status, COUNT(*) AS orders
    FROM orders
    GROUP BY status
    ORDER BY orders DESC, status;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | status | orders |
    | --- | --- |
    | shipped | 16 |
    | cancelled | 2 |
    | pending | 2 |
    <!-- /result -->

**D.8** For each category, the number of products, the cheapest and the dearest price. Products with no category
form their own row. Return `category`, `products`, `cheapest`, `dearest`, sorted by `category` with the missing one
last.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT category, COUNT(*) AS products, MIN(price) AS cheapest, MAX(price) AS dearest
    FROM products
    GROUP BY category
    ORDER BY category NULLS LAST;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | category | products | cheapest | dearest |
    | --- | --- | --- | --- |
    | Home | 4 | 9.50 | 24.50 |
    | Kitchen | 2 | 8.75 | 32.00 |
    | Office | 4 | 3.25 | 149.00 |
    | *NULL* | 1 | 25.00 | 25.00 |
    <!-- /result -->

**D.9** Customers with **three or more** orders. Return `customer_id`, `orders`, sorted by `customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id, COUNT(*) AS orders
    FROM orders
    WHERE customer_id IS NOT NULL
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

**D.10** The value of each order (sum of quantity × unit price), for orders worth more than 100. Return `order_id`,
`value`, highest value first.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT order_id, SUM(quantity * unit_price) AS value
    FROM order_items
    GROUP BY order_id
    HAVING SUM(quantity * unit_price) > 100
    ORDER BY value DESC;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | order_id | value |
    | --- | --- |
    | 112 | 181.00 |
    | 102 | 149.00 |
    | 120 | 139.00 |
    <!-- /result -->

**D.11** For each department: the number of employees, how many have a known salary, and the average known salary
rounded to a whole number. Return `department`, `people`, `with_salary`, `avg_salary`, sorted by `department`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT department,
           COUNT(*)              AS people,
           COUNT(salary)         AS with_salary,
           ROUND(AVG(salary), 0) AS avg_salary
    FROM employees
    GROUP BY department
    ORDER BY department;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | department | people | with_salary | avg_salary |
    | --- | --- | --- | --- |
    | Engineering | 4 | 4 | 118750 |
    | Management | 1 | 1 | 180000 |
    | Sales | 4 | 4 | 78750 |
    | Support | 3 | 2 | 63500 |
    <!-- /result -->

    `COUNT(*)` counts rows; `COUNT(salary)` counts rows where `salary` is not `NULL`; `AVG` ignores `NULL`s, so
    Support's average is over two people, not three.

**D.12** The number of **different** customers who placed an order in each month of 2026, as `month` (1 to 12)
and `customers`, sorted by `month`. Guest orders do not count.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT EXTRACT(MONTH FROM order_date) AS month,
           COUNT(DISTINCT customer_id)    AS customers
    FROM orders
    WHERE order_date >= DATE '2026-01-01' AND order_date < DATE '2027-01-01'
    GROUP BY EXTRACT(MONTH FROM order_date)
    ORDER BY month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | month | customers |
    | --- | --- |
    | 1 | 4 |
    | 2 | 5 |
    | 3 | 6 |
    | 4 | 3 |
    <!-- /result -->

    `COUNT(DISTINCT customer_id)` ignores `NULL`, so the guest order 108 is left out without a `WHERE`. The date
    range uses `>=` and `<` the next year, a habit that also works for timestamps.

## C. Joins { #joins }

Chapters [8](08-Joins-Inner-Left-Right-Full-Cross.md) and [9](09-Self-Semi-and-Anti-Joins.md).

**D.13** Every order with its customer's name; the guest order shows `NULL`. Return `order_id`, `name`, sorted by
`order_id`, for orders placed in February 2026.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT o.order_id, c.name
    FROM orders o
    LEFT JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_date >= '2026-02-01' AND o.order_date < '2026-03-01'
    ORDER BY o.order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

    | order_id | name |
    | --- | --- |
    | 106 | Ben Okafor |
    | 107 | Eli Cohen |
    | 108 | *NULL* |
    | 109 | Farah Haddad |
    | 110 | Ana Silva |
    | 111 | Gus Novak |
    <!-- /result -->

**D.14** Every customer with their number of orders, **including customers with none** (0). Return `name`,
`orders`, sorted by `customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT c.name, COUNT(o.order_id) AS orders
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.customer_id
    GROUP BY c.customer_id, c.name
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

    | name | orders |
    | --- | --- |
    | Ana Silva | 5 |
    | Ben Okafor | 3 |
    | Chen Wei | 2 |
    | Dana Kim | 2 |
    | Eli Cohen | 2 |
    | Farah Haddad | 2 |
    | Gus Novak | 1 |
    | Hana Sato | 1 |
    | Ivan Petrov | 0 |
    | Ana Silva | 1 |
    <!-- /result -->

    `COUNT(o.order_id)`, not `COUNT(*)`: a customer with no orders still has one row after the `LEFT JOIN` (with
    `NULL`s on the order side), and `COUNT(*)` would count it as 1. Group by `customer_id` too, because two customers
    share a name.

**D.15** Products that have never been ordered. Return `product_id`, `name`, sorted by `product_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT p.product_id, p.name
    FROM products p
    WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.product_id = p.product_id)
    ORDER BY p.product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | product_id | name |
    | --- | --- |
    | 11 | Bookend |
    <!-- /result -->

**D.16** Customers who never placed an order, written with `LEFT JOIN`. Return `customer_id`, `name`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.customer_id
    WHERE o.order_id IS NULL
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | customer_id | name |
    | --- | --- |
    | 9 | Ivan Petrov |
    <!-- /result -->

    Test a column of the right-hand table that can never be `NULL` in a real match (its key). `NOT IN (SELECT
    customer_id FROM orders)` would return **nothing**, because that list contains a `NULL` (the guest order).

**D.17** Each employee with their manager's name; the top manager shows `NULL`. Return `employee`, `manager`,
sorted by `employee`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT e.name AS employee, m.name AS manager
    FROM employees e
    LEFT JOIN employees m ON m.employee_id = e.manager_id
    ORDER BY e.name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 12 rows.</p>

    | employee | manager |
    | --- | --- |
    | Ella Novak | Kwame Mensah |
    | Kwame Mensah | Maya Rossi |
    | Leo Park | Kwame Mensah |
    | Lucia Gomez | Tom Becker |
    | Maya Rossi | *NULL* |
    | Nina Berg | Omar Aziz |
    | Omar Aziz | Maya Rossi |
    | Priya Nair | Tom Becker |
    | Raj Patel | Omar Aziz |
    | Sam Lee | Tom Becker |
    | Tom Becker | Maya Rossi |
    | Zoe Martin | Omar Aziz |
    <!-- /result -->

**D.18** For each order item where the price paid is **different** from today's price: `order_id`, `product`,
`unit_price`, `price_today`, sorted by `order_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT i.order_id, p.name AS product, i.unit_price, p.price AS price_today
    FROM order_items i
    JOIN products p ON p.product_id = i.product_id
    WHERE i.unit_price <> p.price
    ORDER BY i.order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | order_id | product | unit_price | price_today |
    | --- | --- | --- | --- |
    | 109 | Tea kettle | 30.00 | 32.00 |
    | 120 | Office chair | 139.00 | 149.00 |
    <!-- /result -->

**D.19** Customers who bought something in **both** the Kitchen and the Office categories. Return `customer_id`,
sorted.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT o.customer_id
    FROM orders o
    JOIN order_items i ON i.order_id = o.order_id
    JOIN products p    ON p.product_id = i.product_id
    WHERE p.category IN ('Kitchen', 'Office')
      AND o.customer_id IS NOT NULL
    GROUP BY o.customer_id
    HAVING COUNT(DISTINCT p.category) = 2
    ORDER BY o.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | customer_id |
    | --- |
    | 1 |
    | 10 |
    <!-- /result -->

    Filter to the two categories, then keep customers with two **different** categories. `WHERE p.category =
    'Kitchen' AND p.category = 'Office'` can never be true on one row.

**D.20** Pairs of customers who live in the same city, each pair once. Return `a`, `b` (the two `customer_id`s,
smaller first) and `city`, sorted by `a`, `b`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT x.customer_id AS a, y.customer_id AS b, x.city
    FROM customers x
    JOIN customers y ON y.city = x.city AND y.customer_id > x.customer_id
    ORDER BY a, b;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | a | b | city |
    | --- | --- | --- |
    | 1 | 6 | Toronto |
    | 1 | 9 | Toronto |
    | 6 | 9 | Toronto |
    <!-- /result -->

    `y.customer_id > x.customer_id` keeps each pair once and never pairs a customer with themselves. Customer 5
    has no city, and `NULL = NULL` is not true, so they are in no pair.

## D. Subqueries and CTEs { #subqueries }

Chapters [10](10-Subqueries.md) and [11](11-CTEs-and-Recursive-CTEs.md).

**D.21** Products that cost more than the average product. Return `name`, `price`, dearest first.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, price
    FROM products
    WHERE price > (SELECT AVG(price) FROM products)
    ORDER BY price DESC, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | name | price |
    | --- | --- |
    | Office chair | 149.00 |
    | Monitor stand | 32.00 |
    | Tea kettle | 32.00 |
    <!-- /result -->

**D.22** Employees who earn more than the average of **their own department**. Return `name`, `department`,
`salary`, sorted by `department`, then `salary` from highest.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT e.name, e.department, e.salary
    FROM employees e
    WHERE e.salary > (SELECT AVG(x.salary) FROM employees x WHERE x.department = e.department)
    ORDER BY e.department, e.salary DESC;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | name | department | salary |
    | --- | --- | --- |
    | Tom Becker | Engineering | 140000 |
    | Priya Nair | Engineering | 120000 |
    | Sam Lee | Engineering | 120000 |
    | Omar Aziz | Sales | 110000 |
    | Kwame Mensah | Support | 75000 |
    <!-- /result -->

    A **correlated** subquery: it runs for each row of the outer query, using that row's department. The window
    version, `AVG(salary) OVER (PARTITION BY department)` in a CTE, gives the same result and reads the table once.

**D.23** The customer (or customers) with the highest total spent on shipped orders. Return `customer_id`, `total`.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH spent AS (
      SELECT o.customer_id, SUM(i.quantity * i.unit_price) AS total
      FROM orders o
      JOIN order_items i ON i.order_id = o.order_id
      WHERE o.status = 'shipped' AND o.customer_id IS NOT NULL
      GROUP BY o.customer_id
    )
    SELECT customer_id, total
    FROM spent
    WHERE total = (SELECT MAX(total) FROM spent)
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | customer_id | total |
    | --- | --- |
    | 1 | 289.00 |
    <!-- /result -->

    Compare with the maximum instead of `ORDER BY ... LIMIT 1`, so that a tie returns every winner.

**D.24** The second-highest **distinct** salary. Return one column, `salary`. (If there were no second salary, the
query should return `NULL`.)

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT MAX(salary) AS salary
    FROM employees
    WHERE salary < (SELECT MAX(salary) FROM employees);
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | salary |
    | --- |
    | 140000 |
    <!-- /result -->

    `MAX` over no rows returns one row with `NULL`, which is what "return NULL" asks for. `ORDER BY salary DESC
    LIMIT 1 OFFSET 1` would return the second **row**, which is wrong when the top salary is shared, and no row at
    all when there is no second one.

## E. Window functions { #windows }

Chapters [13](13-Window-Functions-Ranking.md) and [14](14-Window-Functions-Lag-Lead-Running-Totals.md).

**D.25** Number the orders of each customer from their first (1) to their latest. Return `customer_id`,
`order_id`, `order_date`, `order_no`, sorted by `customer_id`, then `order_no`. Leave out the guest order.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id, order_id, order_date,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS order_no
    FROM orders
    WHERE customer_id IS NOT NULL
    ORDER BY customer_id, order_no;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 19 rows.</p>

    | customer_id | order_id | order_date | order_no |
    | --- | --- | --- | --- |
    | 1 | 101 | 2026-01-03 | 1 |
    | 1 | 103 | 2026-01-15 | 2 |
    | 1 | 110 | 2026-02-20 | 3 |
    | 1 | 115 | 2026-03-18 | 4 |
    | 1 | 120 | 2026-04-05 | 5 |
    | 2 | 102 | 2026-01-03 | 1 |
    | 2 | 106 | 2026-02-02 | 2 |
    | 2 | 113 | 2026-03-05 | 3 |
    | 3 | 104 | 2026-01-20 | 1 |
    | 3 | 118 | 2026-04-01 | 2 |
    | 4 | 105 | 2026-01-28 | 1 |
    | 4 | 112 | 2026-03-01 | 2 |
    | 5 | 107 | 2026-02-02 | 1 |
    | 5 | 119 | 2026-04-02 | 2 |
    | 6 | 109 | 2026-02-14 | 1 |
    | 6 | 116 | 2026-03-22 | 2 |
    | 7 | 111 | 2026-02-21 | 1 |
    | 8 | 114 | 2026-03-09 | 1 |
    | 10 | 117 | 2026-03-25 | 1 |
    <!-- /result -->

**D.26** Each customer's **first** order: `customer_id`, `order_id`, `order_date`, sorted by `customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH numbered AS (
      SELECT customer_id, order_id, order_date,
             ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS rn
      FROM orders
      WHERE customer_id IS NOT NULL
    )
    SELECT customer_id, order_id, order_date
    FROM numbered
    WHERE rn = 1
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | customer_id | order_id | order_date |
    | --- | --- | --- |
    | 1 | 101 | 2026-01-03 |
    | 2 | 102 | 2026-01-03 |
    | 3 | 104 | 2026-01-20 |
    | 4 | 105 | 2026-01-28 |
    | 5 | 107 | 2026-02-02 |
    | 6 | 109 | 2026-02-14 |
    | 7 | 111 | 2026-02-21 |
    | 8 | 114 | 2026-03-09 |
    | 10 | 117 | 2026-03-25 |
    <!-- /result -->

    A window function cannot be used in `WHERE` of the same query (it is computed after `WHERE`), so number the
    rows in a CTE and filter outside.

**D.27** Rank employees by salary within each department, highest first; equal salaries share a rank and the next
rank is skipped. Leave out unknown salaries. Return `department`, `name`, `salary`, `rnk`, sorted by `department`,
`rnk`, `name`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT department, name, salary,
           RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS rnk
    FROM employees
    WHERE salary IS NOT NULL
    ORDER BY department, rnk, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

    | department | name | salary | rnk |
    | --- | --- | --- | --- |
    | Engineering | Tom Becker | 140000 | 1 |
    | Engineering | Priya Nair | 120000 | 2 |
    | Engineering | Sam Lee | 120000 | 2 |
    | Engineering | Lucia Gomez | 95000 | 4 |
    | Management | Maya Rossi | 180000 | 1 |
    | Sales | Omar Aziz | 110000 | 1 |
    | Sales | Nina Berg | 70000 | 2 |
    | Sales | Raj Patel | 70000 | 2 |
    | Sales | Zoe Martin | 65000 | 4 |
    | Support | Kwame Mensah | 75000 | 1 |
    | Support | Ella Novak | 52000 | 2 |
    <!-- /result -->

    `RANK` skips after a tie (1, 2, 2, 4), `DENSE_RANK` does not (1, 2, 2, 3), `ROW_NUMBER` never ties.

**D.28** For each of customer 1's orders: the date of the **previous** order and the number of days since it. Return
`order_id`, `order_date`, `prev_date`, `days_since`, sorted by `order_date`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT order_id, order_date,
           LAG(order_date) OVER (ORDER BY order_date, order_id)              AS prev_date,
           order_date - LAG(order_date) OVER (ORDER BY order_date, order_id) AS days_since
    FROM orders
    WHERE customer_id = 1
    ORDER BY order_date;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 5 rows.</p>

    | order_id | order_date | prev_date | days_since |
    | --- | --- | --- | --- |
    | 101 | 2026-01-03 | *NULL* | *NULL* |
    | 103 | 2026-01-15 | 2026-01-03 | 12 |
    | 110 | 2026-02-20 | 2026-01-15 | 36 |
    | 115 | 2026-03-18 | 2026-02-20 | 26 |
    | 120 | 2026-04-05 | 2026-03-18 | 18 |
    <!-- /result -->

    In PostgreSQL, a date minus a date is a whole number of days. The first order has no previous one, so both are
    `NULL`.

**D.29** The running total of shipped order value by order date, over all customers. Return `order_date`,
`day_value`, `running_total`, one row per date, sorted by date.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH daily AS (
      SELECT o.order_date, SUM(i.quantity * i.unit_price) AS day_value
      FROM orders o
      JOIN order_items i ON i.order_id = o.order_id
      WHERE o.status = 'shipped'
      GROUP BY o.order_date
    )
    SELECT order_date, day_value,
           SUM(day_value) OVER (ORDER BY order_date) AS running_total
    FROM daily
    ORDER BY order_date;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 14 rows.</p>

    | order_date | day_value | running_total |
    | --- | --- | --- |
    | 2026-01-03 | 183.25 | 183.25 |
    | 2026-01-15 | 33.75 | 217.00 |
    | 2026-01-28 | 24.50 | 241.50 |
    | 2026-02-02 | 93.25 | 334.75 |
    | 2026-02-10 | 50.00 | 384.75 |
    | 2026-02-14 | 65.00 | 449.75 |
    | 2026-02-20 | 32.50 | 482.25 |
    | 2026-02-21 | 36.75 | 519.00 |
    | 2026-03-01 | 181.00 | 700.00 |
    | 2026-03-09 | 49.00 | 749.00 |
    | 2026-03-18 | 49.50 | 798.50 |
    | 2026-03-25 | 43.00 | 841.50 |
    | 2026-04-01 | 24.50 | 866.00 |
    | 2026-04-05 | 139.00 | 1005.00 |
    <!-- /result -->

**D.30** Each product's price as a **percentage of its category's total** price, one decimal. Leave out the product
with no category. Return `category`, `name`, `pct`, sorted by `category`, then `pct` from highest, then `name`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT category, name,
           ROUND(100.0 * price / SUM(price) OVER (PARTITION BY category), 1) AS pct
    FROM products
    WHERE category IS NOT NULL
    ORDER BY category, pct DESC, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

    | category | name | pct |
    | --- | --- | --- |
    | Home | Desk lamp | 34.6 |
    | Home | Wall clock | 34.6 |
    | Home | Plant pot | 17.3 |
    | Home | Bookend | 13.4 |
    | Kitchen | Tea kettle | 78.5 |
    | Kitchen | Coffee mug | 21.5 |
    | Office | Office chair | 73.7 |
    | Office | Monitor stand | 15.8 |
    | Office | Fountain pen | 8.9 |
    | Office | Notebook | 1.6 |
    <!-- /result -->

    A window `SUM` with `PARTITION BY` and no `ORDER BY` is the total of the whole group, on every row.

## F. Dates and CASE { #dates }

Chapters [4](04-Expressions-Case-Numbers-Dates-Cast.md) and [16](16-Dates-and-Time-Series.md). PostgreSQL.

**D.31** Shipped order value per month of 2026, every month from January to April, showing 0 for a month with
nothing. Return `month` (the first day of the month) and `value`, sorted by `month`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH months AS (
      SELECT generate_series(DATE '2026-01-01', DATE '2026-04-01', INTERVAL '1 month')::date AS month
    ),
    value AS (
      SELECT date_trunc('month', o.order_date)::date AS month, SUM(i.quantity * i.unit_price) AS value
      FROM orders o
      JOIN order_items i ON i.order_id = o.order_id
      WHERE o.status = 'shipped'
      GROUP BY 1
    )
    SELECT m.month, COALESCE(v.value, 0) AS value
    FROM months m
    LEFT JOIN value v ON v.month = m.month
    ORDER BY m.month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | month | value |
    | --- | --- |
    | 2026-01-01 | 241.50 |
    | 2026-02-01 | 277.50 |
    | 2026-03-01 | 322.50 |
    | 2026-04-01 | 163.50 |
    <!-- /result -->

    `generate_series` makes the list of months, so a month with no sales still appears; `LEFT JOIN` the sales to it
    and `COALESCE` the missing ones to 0.

**D.32** For each customer, the number of days from signing up to their first order. Leave out customers with no
order. Return `customer_id`, `days_to_first_order`, sorted by `customer_id`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT c.customer_id, MIN(o.order_date) - c.signup_date AS days_to_first_order
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    GROUP BY c.customer_id, c.signup_date
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 9 rows.</p>

    | customer_id | days_to_first_order |
    | --- | --- |
    | 1 | 61 |
    | 2 | 24 |
    | 3 | 15 |
    | 4 | 23 |
    | 5 | 13 |
    | 6 | 12 |
    | 7 | 7 |
    | 8 | 9 |
    | 10 | 10 |
    <!-- /result -->

    `MIN(o.order_date)` is the first order; a date minus a date is a number of days in PostgreSQL. `signup_date` is
    in the `GROUP BY` so it can be used next to the aggregate. In real data, check for negative values here: an order
    dated before its customer's sign-up is a data quality problem ([chapter 23](23-Data-Quality-Checks.md)).

**D.33** Label each product by price: `'budget'` under 10, `'mid'` from 10 to under 50, `'premium'` from 50.
Return `price_band` and `products` (how many), sorted by `price_band`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT CASE
             WHEN price < 10 THEN 'budget'
             WHEN price < 50 THEN 'mid'
             ELSE 'premium'
           END AS price_band,
           COUNT(*) AS products
    FROM products
    GROUP BY 1
    ORDER BY price_band;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | price_band | products |
    | --- | --- |
    | budget | 3 |
    | mid | 7 |
    | premium | 1 |
    <!-- /result -->

    `CASE` checks its branches in order and stops at the first true one, so the second branch does not need
    `price >= 10`.

**D.34** One row per customer who ordered, with the number of orders in **each status** as columns: `customer_id`,
`shipped`, `pending`, `cancelled`, sorted by `customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id,
           SUM(CASE WHEN status = 'shipped'   THEN 1 ELSE 0 END) AS shipped,
           SUM(CASE WHEN status = 'pending'   THEN 1 ELSE 0 END) AS pending,
           SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
    FROM orders
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | customer_id | shipped | pending | cancelled |
    | --- | --- | --- | --- |
    | 1 | 5 | 0 | 0 |
    | 2 | 2 | 0 | 1 |
    | 3 | 1 | 0 | 1 |
    | 4 | 2 | 0 | 0 |
    | 5 | 1 | 1 | 0 |
    | 6 | 1 | 1 | 0 |
    | 7 | 1 | 0 | 0 |
    | 8 | 1 | 0 | 0 |
    | 10 | 1 | 0 | 0 |
    <!-- /result -->

    Rows into columns ("pivot") with one `SUM(CASE ...)` per column. It works in every database.

**D.35** Orders placed on a **weekend** (Saturday or Sunday). Return `order_id`, `order_date`, `weekday` (the
day's name), sorted by `order_id`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT order_id, order_date, trim(to_char(order_date, 'Day')) AS weekday
    FROM orders
    WHERE EXTRACT(ISODOW FROM order_date) IN (6, 7)
    ORDER BY order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 7 rows.</p>

    | order_id | order_date | weekday |
    | --- | --- | --- |
    | 101 | 2026-01-03 | Saturday |
    | 102 | 2026-01-03 | Saturday |
    | 109 | 2026-02-14 | Saturday |
    | 111 | 2026-02-21 | Saturday |
    | 112 | 2026-03-01 | Sunday |
    | 116 | 2026-03-22 | Sunday |
    | 120 | 2026-04-05 | Sunday |
    <!-- /result -->

    `ISODOW` numbers Monday 1 to Sunday 7. `DOW` numbers Sunday 0 to Saturday 6: easy to mix up. `to_char` pads
    the day name with spaces to nine letters, so `trim` it.

**D.36** Logins: for each customer, the **longest run of consecutive days** they signed in. Count a day once even
if they signed in twice. Return `customer_id`, `longest_streak`, sorted by `customer_id`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH days AS (
      SELECT DISTINCT customer_id, login_date FROM logins
    ),
    grouped AS (
      SELECT customer_id, login_date,
             login_date - CAST(ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY login_date) AS INTEGER) AS grp
      FROM days
    )
    SELECT customer_id, MAX(streak) AS longest_streak
    FROM (SELECT customer_id, grp, COUNT(*) AS streak FROM grouped GROUP BY customer_id, grp) s
    GROUP BY customer_id
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | customer_id | longest_streak |
    | --- | --- |
    | 1 | 3 |
    | 2 | 2 |
    | 4 | 4 |
    | 6 | 1 |
    <!-- /result -->

    The **gaps and islands** trick: in a run of consecutive days, the date and the row number both go up by 1, so
    date minus row number is the same for the whole run. Group by that value to get each run. Remove duplicate days
    first, or a repeated day breaks the run.
