# 7. Aggregation: GROUP BY and HAVING

*Most questions about data are questions about groups: how many orders each customer placed, the revenue of each
month, the average salary in each department. This chapter turns many rows into one row per group: the five
aggregate functions, the three ways to count, GROUP BY, the difference between WHERE and HAVING, and counting with
conditions. It ends with the mistakes that cost the most marks in tests: dividing whole numbers, grouping by a name,
and the columns PostgreSQL refuses but SQLite lets through.*

!!! abstract "In this chapter"
    **You will learn:**

    - `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, and what each does with NULL
    - `COUNT(*)`, `COUNT(column)` and `COUNT(DISTINCT column)`, and when each is right
    - `GROUP BY` on one column, several columns and an expression
    - `WHERE` (before grouping) and `HAVING` (after grouping)
    - counting with a condition: `SUM(CASE ...)` and `FILTER`
    - why `1 / 4` is `0`, and how to get `0.25`
    - the rule for what may appear in SELECT, and why SQLite breaks it

    **You need:** [2. SELECT and WHERE](02-Select-Where-Order-By-Limit.md) and [3. the order a query runs in](03-The-Order-a-Query-Runs-In.md), and the [sample database](sample-database.md). [6. NULL](06-Null-and-Three-Valued-Logic.md) helps.

## 7.1 Many rows in, one row out { #aggregates }

An **aggregate function** reads many rows and returns one value. Without GROUP BY, the whole table is one group, so
the answer is one row.

**Task:** For all products, show in one row: how many, the total of the prices, the average, the cheapest and the dearest price.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT COUNT(*)        AS products,
           SUM(price)      AS total_of_prices,
           AVG(price)      AS average_price,
           MIN(price)      AS cheapest,
           MAX(price)      AS dearest
    FROM products;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | products | total_of_prices | average_price | cheapest | dearest |
    | --- | --- | --- | --- | --- |
    | 11 | 338.75 | 30.7954545454545455 | 3.25 | 149.00 |
    <!-- /result -->

PostgreSQL returns a `NUMERIC` with many decimal places; SQLite returns a floating-point number. Round it
when you show it: `ROUND(AVG(price), 2)`.

`MIN` and `MAX` work on text and dates too: the first and last in sorting order.

**Task:** Show the first and last customer name in alphabetical order, and the first and last signup date.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT MIN(name) AS first_name, MAX(name) AS last_name,
           MIN(signup_date) AS first_signup, MAX(signup_date) AS last_signup
    FROM customers;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | first_name | last_name | first_signup | last_signup |
    | --- | --- | --- | --- |
    | Ana Silva | Ivan Petrov | 2025-11-03 | 2026-03-15 |
    <!-- /result -->

**What every aggregate does with NULL:** it skips it. `SUM`, `AVG`, `MIN`, `MAX` and `COUNT(column)` look only at
the values that are there. Only `COUNT(*)` counts rows whatever is in them.

## 7.2 Three ways to count { #count }

**Task:** For customers, show in one row: customers, customers with an email, customers with a city, different cities and different names.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT COUNT(*)             AS customers,
           COUNT(email)         AS with_email,
           COUNT(city)          AS with_city,
           COUNT(DISTINCT city) AS different_cities,
           COUNT(DISTINCT name) AS different_names
    FROM customers;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | customers | with_email | with_city | different_cities | different_names |
    | --- | --- | --- | --- | --- |
    | 10 | 8 | 9 | 7 | 9 |
    <!-- /result -->

- `COUNT(*)` counts **rows**: 10 customers.
- `COUNT(email)` counts rows where `email` **is not NULL**: two customers have no email, so 8.
- `COUNT(DISTINCT city)` counts **different non-NULL values**: one city is NULL and Toronto appears three times, so
  the nine known cities are only seven different ones.
- `COUNT(DISTINCT name)` is 9, not 10, because two different customers are both called Ana Silva. Counting names is
  not counting people.

!!! tip "Interview tip: which count?"
    Read the question for the noun. "How many customers" is `COUNT(*)` on customers (or `COUNT(DISTINCT
    customer_id)` after a join). "How many customers have an email" is `COUNT(email)`. "How many cities" is
    `COUNT(DISTINCT city)`, and the task should say whether an unknown city counts; by default it does not.

### COUNT(1), and the SELECT 1 inside EXISTS { #count-one }

Two more forms come up in other people's SQL, and in interview questions about it.

**`COUNT(1)` is the same as `COUNT(*)`.** `COUNT(x)` counts the rows where `x` is not NULL, and `1` is never NULL, so
every row counts. Some people believe `COUNT(1)` is faster; in PostgreSQL, SQLite and every other common database it
is not. Write `COUNT(*)`: it says "count rows" most clearly.

**Task:** Count the customers three ways: `COUNT(*)`, `COUNT(1)` and `COUNT(email)`.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT COUNT(*)     AS count_star,
           COUNT(1)     AS count_one,
           COUNT(email) AS count_email
    FROM customers;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | count_star | count_one | count_email |
    | --- | --- | --- |
    | 10 | 10 | 8 |
    <!-- /result -->

**`COUNT(*)` after a `LEFT JOIN` counts a customer with no orders as 1.** The `LEFT JOIN` keeps that customer as one
row with NULLs in the `orders` columns, and `COUNT(*)` counts the row. Count a column of the right-hand table
instead; its NULL is not counted:

**Task:** For customers 8 to 10, show the id, `COUNT(*)` and the real number of orders, by id.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT c.customer_id,
           COUNT(*)          AS count_star,        -- wrong for "number of orders": 1 for customer 9
           COUNT(o.order_id) AS orders              -- right: 0 for customer 9
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.customer_id
    WHERE c.customer_id >= 8
    GROUP BY c.customer_id
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_id | count_star | orders |
    | --- | --- | --- |
    | 8 | 1 | 1 |
    | 9 | 1 | 0 |
    | 10 | 1 | 1 |
    <!-- /result -->

**`SELECT 1` is not a count.** Inside `EXISTS (...)` you will often see `SELECT 1`. `EXISTS` only asks whether the
subquery finds **any** row; what the subquery selects is never looked at, so `1` is a placeholder (`SELECT *` or
`SELECT order_id` would give the same answer). The database can stop at the first matching row. Customers who placed
at least one order:

**Task:** List the customers who have at least one order: id and name, by id.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name
    FROM customers c
    WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id)
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | customer_id | name |
    | --- | --- |
    | 1 | Ana Silva |
    | 2 | Ben Okafor |
    | 3 | Chen Wei |
    | 4 | Dana Kim |
    | 5 | Eli Cohen |
    | 6 | Farah Haddad |
    | 7 | Gus Novak |
    | 8 | Hana Sato |
    | 10 | Ana Silva |
    <!-- /result -->

The same rows come from counting, but the count has to find **every** order of each customer before it can compare
with 0. Prefer `EXISTS` for "has at least one", and `NOT EXISTS` for "has none"
([chapter 9](09-Self-Semi-and-Anti-Joins.md#semi)):

<!-- sql same -->
```sql
SELECT c.customer_id, c.name
FROM customers c
WHERE (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.customer_id) > 0
ORDER BY c.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 9 rows.</p>

| customer_id | name |
| --- | --- |
| 1 | Ana Silva |
| 2 | Ben Okafor |
| 3 | Chen Wei |
| 4 | Dana Kim |
| 5 | Eli Cohen |
| 6 | Farah Haddad |
| 7 | Gus Novak |
| 8 | Hana Sato |
| 10 | Ana Silva |
<!-- /result -->

| You write | It returns | Use it for |
| --- | --- | --- |
| `COUNT(*)` | the number of rows | "how many orders" |
| `COUNT(1)` | the same as `COUNT(*)` | nothing new; prefer `COUNT(*)` |
| `COUNT(col)` | rows where `col` is not NULL | "how many have an email"; the number of matches after a `LEFT JOIN` |
| `COUNT(DISTINCT col)` | different non-NULL values | "how many different cities" |
| `EXISTS (SELECT 1 ...)` | true or false: is there at least one row? | "customers who have an order" |
| `NOT EXISTS (SELECT 1 ...)` | true when there is no row | "customers who never ordered" |

## 7.3 GROUP BY: one row per group { #group-by }

`GROUP BY status` puts the rows into one group per different status, and each aggregate is worked out once per group.

**Task:** Count the orders in each status, most orders first (ties by status).

??? success "Solution"

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

The question "what is one row of the answer?" decides the GROUP BY. "Revenue of each order" means one row per
order, so group `order_items` by `order_id`:

**Task:** Show the 5 biggest orders by revenue: order id, number of lines, units and revenue, highest revenue first (ties by order id).

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT order_id,
           COUNT(*)                   AS lines,
           SUM(quantity)              AS units,
           SUM(quantity * unit_price) AS revenue
    FROM order_items
    GROUP BY order_id
    ORDER BY revenue DESC, order_id
    LIMIT 5;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | order_id | lines | units | revenue |
    | --- | --- | --- | --- |
    | 112 | 2 | 2 | 181.00 |
    | 102 | 1 | 1 | 149.00 |
    | 120 | 1 | 1 | 139.00 |
    | 109 | 2 | 5 | 65.00 |
    | 106 | 2 | 2 | 56.50 |
    <!-- /result -->

**Several columns** make one group per combination:

**Task:** Count the customers in each (country, city) pair, by country then city.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT country, city, COUNT(*) AS customers
    FROM customers
    GROUP BY country, city
    ORDER BY country, city;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 8 rows.</p>

    | country | city | customers |
    | --- | --- | --- |
    | Canada | Toronto | 3 |
    | China | Shanghai | 1 |
    | Czechia | Prague | 1 |
    | Israel | *NULL* | 1 |
    | Japan | Osaka | 1 |
    | Nigeria | Lagos | 1 |
    | Portugal | Lisbon | 1 |
    | South Korea | Seoul | 1 |
    <!-- /result -->

Eli Cohen's city is NULL, and NULLs form **one group of their own**: Israel's row has a NULL city. GROUP BY treats
all NULLs as equal to each other, even though `NULL = NULL` is not true in a WHERE or a join (chapter 6).

**An expression** can be grouped on too. Here the price band is worked out with CASE and then grouped; the SELECT
repeats the same expression:

**Task:** Count the products priced 30 and up and those under 30, as `band` and `products`, by band.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT CASE WHEN price >= 30 THEN '30 and up' ELSE 'under 30' END AS band,
           COUNT(*) AS products
    FROM products
    GROUP BY CASE WHEN price >= 30 THEN '30 and up' ELSE 'under 30' END
    ORDER BY band;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | band | products |
    | --- | --- |
    | 30 and up | 3 |
    | under 30 | 8 |
    <!-- /result -->

PostgreSQL and SQLite also accept `GROUP BY band` (the alias) or `GROUP BY 1` (the first SELECT column). Both are
handy in a timed test, but neither is standard SQL, and SQL Server accepts neither.

## 7.4 The SELECT rule { #select-rule }

After GROUP BY, each output row stands for a whole group. So every column in SELECT must be either **in the GROUP
BY** (the same for the whole group) or **inside an aggregate** (one value made from the group). Anything else has no
single value. PostgreSQL refuses it. SQLite does not:

<!-- sql pgerror -->
```sql
SELECT department, name, MAX(salary) AS top_salary
FROM employees
GROUP BY department;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>column "employees.name" must appear in the GROUP BY clause or be used in an aggregate function</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 4 rows.</p>
<!-- /result -->

SQLite picks a `name` from some row of each group. It has a documented special case: with exactly one `MAX` or
`MIN`, the bare column comes from the row that holds the maximum or minimum. With a tie, though, only one of the tied
rows is shown, and with any other aggregate the name is from an arbitrary row. On a test, write the query that
PostgreSQL would accept; [chapter 13](13-Window-Functions-Ranking.md) shows the right way to get "the name of the
best-paid person in each department", ties included.

!!! note "One exception"
    If you group by a table's primary key, PostgreSQL lets you select that table's other columns, because the key
    decides them: `GROUP BY c.customer_id` allows `c.name` in SELECT. Writing `GROUP BY c.customer_id, c.name` works
    everywhere and costs nothing.

## 7.5 WHERE or HAVING { #having }

Both filter, at different moments (chapter 3):

- **WHERE** removes **rows** before they are grouped. It can't see aggregates, because none exist yet.
- **HAVING** removes **groups** after they are made. It is the place for conditions on `COUNT`, `SUM` and the rest.

"Customers with at least two **shipped** orders" needs both: WHERE keeps shipped orders, HAVING keeps customers
with two or more of them.

**Task:** List the customers with at least 2 shipped orders: customer id and shipped orders, most first (ties by customer id).

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT customer_id, COUNT(*) AS shipped_orders
    FROM orders
    WHERE status = 'shipped'
    GROUP BY customer_id
    HAVING COUNT(*) >= 2
    ORDER BY shipped_orders DESC, customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_id | shipped_orders |
    | --- | --- |
    | 1 | 5 |
    | 2 | 2 |
    | 4 | 2 |
    <!-- /result -->

An aggregate in WHERE is an error on both databases:

<!-- sql error -->
```sql
SELECT customer_id, COUNT(*) AS orders
FROM orders
WHERE COUNT(*) >= 2
GROUP BY customer_id;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>aggregate functions are not allowed in WHERE</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>misuse of aggregate: COUNT()</code></p>
<!-- /result -->

A condition on a grouped column can go in either place and gives the same answer, but WHERE is the better home: it
throws rows away before the work of grouping.

## 7.6 Counting with a condition { #conditional }

To count several things in one pass, put a CASE inside the aggregate. A row that doesn't match adds 0 (or gives
NULL, which COUNT skips):

**Task:** For each customer with orders, show all orders and how many are shipped, cancelled and pending, by customer id.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT customer_id,
           COUNT(*)                                           AS orders,
           SUM(CASE WHEN status = 'shipped'   THEN 1 ELSE 0 END) AS shipped,
           COUNT(CASE WHEN status = 'cancelled' THEN 1 END)     AS cancelled,
           COUNT(*) FILTER (WHERE status = 'pending')           AS pending
    FROM orders
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | customer_id | orders | shipped | cancelled | pending |
    | --- | --- | --- | --- | --- |
    | 1 | 5 | 5 | 0 | 0 |
    | 2 | 3 | 2 | 1 | 0 |
    | 3 | 2 | 1 | 1 | 0 |
    | 4 | 2 | 2 | 0 | 0 |
    | 5 | 2 | 1 | 0 | 1 |
    | 6 | 2 | 1 | 0 | 1 |
    | 7 | 1 | 1 | 0 | 0 |
    | 8 | 1 | 1 | 0 | 0 |
    | 10 | 1 | 1 | 0 | 0 |
    <!-- /result -->

All three styles give the same kind of count. `FILTER (WHERE ...)` is standard SQL and works on PostgreSQL and on
SQLite 3.30 and later, but not on MySQL, SQL Server or Oracle; `SUM(CASE ...)` works everywhere, so it is the safe
habit. This is also how a **pivot** is written: one CASE per output column (more in
[chapter 15](15-Classic-Interview-Patterns.md#pivot)).

## 7.7 Averages, ratios and whole-number division { #division }

"What share of orders were cancelled?" The obvious query is wrong:

!!! failure "The usual wrong answer"
    <!-- sql -->
    ```sql
    SELECT COUNT(CASE WHEN status = 'cancelled' THEN 1 END) / COUNT(*) AS cancelled_share
    FROM orders;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | cancelled_share |
    | --- |
    | 0 |
    <!-- /result -->

    Both counts are whole numbers, and dividing a whole number by a whole number gives a whole number in PostgreSQL,
    SQLite and SQL Server: 2 / 20 is 0, with the remainder thrown away. (MySQL and Oracle return 0.1 here.)

Make one side a decimal first, by multiplying by `1.0` (or `100.0` for a percentage), then round at the end:

**Task:** What percentage of all orders were cancelled, to 1 decimal place?

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT ROUND(100.0 * COUNT(CASE WHEN status = 'cancelled' THEN 1 END) / COUNT(*), 1) AS cancelled_pct
    FROM orders;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | cancelled_pct |
    | --- |
    | 10.0 |
    <!-- /result -->

`AVG` itself is safe: it returns a decimal on both databases, even for whole numbers (not on SQL Server, where `AVG` of an integer column is an
integer). The danger is only in `/`
between two whole numbers, including `SUM(...) / COUNT(...)` written out by hand.

**AVG skips NULLs**, which changes the answer when NULL means "zero":

**Task:** For Support, show the average of the known salaries, and the average if a missing salary counted as 0, both to 2 decimals.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT ROUND(AVG(salary), 2)                  AS avg_known_salaries,
           ROUND(SUM(salary) * 1.0 / COUNT(*), 2) AS avg_counting_missing_as_zero
    FROM employees
    WHERE department = 'Support';
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | avg_known_salaries | avg_counting_missing_as_zero |
    | --- | --- |
    | 63500.00 | 42333.33 |
    <!-- /result -->

Leo Park's salary is not set. `AVG` averages the two known salaries; the second column divides by all three people.
Which is right depends on the question; usually it is the first, and saying why earns credit.

## 7.8 Grouping by the key, not the name { #group-by-key }

!!! failure "The usual wrong answer: orders per customer, grouped by name"
    <!-- sql -->
    ```sql
    SELECT c.name, COUNT(*) AS orders
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    GROUP BY c.name
    ORDER BY orders DESC, c.name
    LIMIT 3;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | name | orders |
    | --- | --- |
    | Ana Silva | 6 |
    | Ben Okafor | 3 |
    | Chen Wei | 2 |
    <!-- /result -->

    Ana Silva seems to have 6 orders. There are two Ana Silvas: customer 1 placed 5 and customer 10 placed 1.

Group by the **key** and show the name beside it:

**Task:** Show the 3 customers with the most orders: id, name and orders, most first (ties by id).

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name, COUNT(*) AS orders
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    GROUP BY c.customer_id, c.name
    ORDER BY orders DESC, c.customer_id
    LIMIT 3;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_id | name | orders |
    | --- | --- | --- |
    | 1 | Ana Silva | 5 |
    | 2 | Ben Okafor | 3 |
    | 3 | Chen Wei | 2 |
    <!-- /result -->

## 7.9 Summary { #summary }

- Aggregates turn a group of rows into one value and skip NULLs; only `COUNT(*)` counts every row.
- `GROUP BY` makes one output row per different value (or combination); NULLs form one group.
- Every SELECT column must be grouped or aggregated. PostgreSQL enforces it; SQLite lets it through and guesses.
- `WHERE` filters rows before grouping; `HAVING` filters groups after.
- Count with a condition using `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`.
- Whole number divided by whole number is a whole number: multiply by `1.0` first.
- Group by the key, never by a name.

## Practice { #practice }

Try each one on the sample database before opening the answer.

**7.1** How many orders are there, and how many different customers placed them? (The guest order has no customer.)

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT COUNT(*) AS orders, COUNT(DISTINCT customer_id) AS customers
    FROM orders;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | orders | customers |
    | --- | --- |
    | 20 | 9 |
    <!-- /result -->

    `COUNT(DISTINCT customer_id)` skips the NULL of the guest order, which is what "different customers" means.

**7.2** For each category, the number of products and the average price rounded to 2 places, most products first.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT category, COUNT(*) AS products, ROUND(AVG(price), 2) AS avg_price
    FROM products
    GROUP BY category
    ORDER BY products DESC, category;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | category | products | avg_price |
    | --- | --- | --- |
    | Home | 4 | 17.69 |
    | Office | 4 | 50.56 |
    | Kitchen | 2 | 20.38 |
    | *NULL* | 1 | 25.00 |
    <!-- /result -->

    The gift card has no category, so it forms a group of its own with a NULL category. If the task wanted it left
    out, add `WHERE category IS NOT NULL`. Where NULL sorts depends on the database: PostgreSQL puts NULLs last in
    ascending order, SQLite first (chapter 6); here the sort is first by count, so it doesn't matter.

**7.3** Total units sold and revenue for each product that has been sold, highest revenue first. Show the product
id only.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT product_id,
           SUM(quantity)              AS units,
           SUM(quantity * unit_price) AS revenue
    FROM order_items
    GROUP BY product_id
    ORDER BY revenue DESC, product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

    | product_id | units | revenue |
    | --- | --- | --- |
    | 6 | 3 | 437.00 |
    | 1 | 5 | 122.50 |
    | 5 | 3 | 94.00 |
    | 2 | 25 | 81.25 |
    | 4 | 9 | 78.75 |
    | 10 | 3 | 75.00 |
    | 8 | 6 | 73.50 |
    | 3 | 4 | 72.00 |
    | 7 | 2 | 64.00 |
    | 9 | 1 | 24.50 |
    <!-- /result -->

    Revenue uses `unit_price` from `order_items`, the price actually paid. Note this counts items in every order,
    cancelled ones too; the next question fixes that.

**7.4** The same, but only for orders that were shipped. (You need a join; [chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md) explains it.)

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT i.product_id,
           SUM(i.quantity)                AS units,
           SUM(i.quantity * i.unit_price) AS revenue
    FROM order_items i
    JOIN orders o ON o.order_id = i.order_id
    WHERE o.status = 'shipped'
    GROUP BY i.product_id
    ORDER BY revenue DESC, i.product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

    | product_id | units | revenue |
    | --- | --- | --- |
    | 6 | 3 | 437.00 |
    | 1 | 5 | 122.50 |
    | 2 | 25 | 81.25 |
    | 4 | 9 | 78.75 |
    | 7 | 2 | 64.00 |
    | 5 | 2 | 62.00 |
    | 10 | 2 | 50.00 |
    | 8 | 4 | 49.00 |
    | 3 | 2 | 36.00 |
    | 9 | 1 | 24.50 |
    <!-- /result -->

    Each item has exactly one order, so joining items to orders doesn't multiply rows. The WHERE drops items of
    cancelled and pending orders before grouping.

**7.5** Departments whose average known salary is above 75,000. Show the department and the average, rounded to a
whole number.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT department, ROUND(AVG(salary), 0) AS avg_salary
    FROM employees
    GROUP BY department
    HAVING AVG(salary) > 75000
    ORDER BY avg_salary DESC;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | department | avg_salary |
    | --- | --- |
    | Management | 180000 |
    | Engineering | 118750 |
    | Sales | 78750 |
    <!-- /result -->

    The condition is on an aggregate, so it goes in HAVING. Use the unrounded `AVG(salary)` in HAVING so rounding
    can't move a value across the line.

**7.6** For each month of 2026 that has orders, the number of orders and the number of cancelled orders. Write the
month as text like `2026-01`.

??? success "Answer"
    Taking the first seven characters of the date works on both databases, because SQLite stores these dates as
    text `YYYY-MM-DD` and PostgreSQL turns a date into that same text when cast:

    <!-- sql -->
    ```sql
    SELECT SUBSTR(CAST(order_date AS TEXT), 1, 7) AS month,
           COUNT(*) AS orders,
           SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
    FROM orders
    GROUP BY SUBSTR(CAST(order_date AS TEXT), 1, 7)
    ORDER BY month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | month | orders | cancelled |
    | --- | --- | --- |
    | 2026-01 | 5 | 1 |
    | 2026-02 | 6 | 0 |
    | 2026-03 | 6 | 1 |
    | 2026-04 | 3 | 0 |
    <!-- /result -->

    The usual date functions differ between the two (`to_char` and `date_trunc` in PostgreSQL, `strftime` in
    SQLite); [chapter 16](16-Dates-and-Time-Series.md) has both.

**7.7** The percentage of shipped orders that contain more than one product line, to one decimal place.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH lines AS (
      SELECT i.order_id, COUNT(*) AS n
      FROM order_items i
      JOIN orders o ON o.order_id = i.order_id
      WHERE o.status = 'shipped'
      GROUP BY i.order_id
    )
    SELECT ROUND(100.0 * SUM(CASE WHEN n > 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS multi_line_pct
    FROM lines;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | multi_line_pct |
    | --- |
    | 56.3 |
    <!-- /result -->

    First one row per order with its line count (a CTE, [chapter 11](11-CTEs-and-Recursive-CTEs.md)), then a
    conditional count over those rows. `100.0` makes the division a decimal one.

**7.8** Countries with more than one customer, and how many of those customers have no email.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT country,
           COUNT(*)                AS customers,
           COUNT(*) - COUNT(email) AS without_email
    FROM customers
    GROUP BY country
    HAVING COUNT(*) > 1
    ORDER BY country;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | country | customers | without_email |
    | --- | --- | --- |
    | Canada | 3 | 0 |
    <!-- /result -->

    Only Canada has more than one customer. `COUNT(*) - COUNT(email)` is the number of NULL emails, a neat trick
    worth remembering.

**7.9** Which query is wrong, and why? Both try to list customers with more than 100 of revenue in shipped orders.

```text
-- A
SELECT o.customer_id, SUM(i.quantity * i.unit_price) AS revenue
FROM orders o JOIN order_items i ON i.order_id = o.order_id
WHERE o.status = 'shipped' AND SUM(i.quantity * i.unit_price) > 100
GROUP BY o.customer_id;

-- B
SELECT o.customer_id, SUM(i.quantity * i.unit_price) AS revenue
FROM orders o JOIN order_items i ON i.order_id = o.order_id
WHERE o.status = 'shipped'
GROUP BY o.customer_id
HAVING SUM(i.quantity * i.unit_price) > 100;
```

??? success "Answer"
    A is wrong: an aggregate can't be used in WHERE, and both databases stop with an error. B is right:

    <!-- sql -->
    ```sql
    SELECT o.customer_id, SUM(i.quantity * i.unit_price) AS revenue
    FROM orders o JOIN order_items i ON i.order_id = o.order_id
    WHERE o.status = 'shipped'
    GROUP BY o.customer_id
    HAVING SUM(i.quantity * i.unit_price) > 100
    ORDER BY revenue DESC, o.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_id | revenue |
    | --- | --- |
    | 1 | 289.00 |
    | 2 | 205.50 |
    | 4 | 205.50 |
    <!-- /result -->

    Customers 2 and 4 tie on 205.50, so the ORDER BY needs a second column to make the order certain. The guest
    order (customer NULL) would appear as a group of its own if its revenue passed the line; it is 50.00, so it
    doesn't.

**7.10** The average number of orders per customer, counting customers who never ordered as 0. Round to 2 places.

??? success "Answer"
    Count the orders that have a customer and divide by the number of customers:

    <!-- sql -->
    ```sql
    SELECT ROUND(1.0 * (SELECT COUNT(*) FROM orders WHERE customer_id IS NOT NULL)
                 / (SELECT COUNT(*) FROM customers), 2) AS avg_orders_per_customer;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | avg_orders_per_customer |
    | --- |
    | 1.90 |
    <!-- /result -->

    19 orders have a customer and there are 10 customers. Averaging `COUNT(*)` grouped by `customer_id` on `orders`
    alone would miss Ivan Petrov, who has no orders and so no group: that gives 19 / 9. [Chapter
    8](08-Joins-Inner-Left-Right-Full-Cross.md#count-left) shows the LEFT JOIN way, and its own trap.

**Next:** [8. Joins](08-Joins-Inner-Left-Right-Full-Cross.md).
