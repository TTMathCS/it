# 8. Joins: inner, left, right, full, cross

*Data is split across tables so that each fact is written once: a customer's name lives in `customers`, not in every
order. A join puts the pieces back together. This chapter covers the five kinds of join, what each keeps and drops,
and the three join mistakes that fail more test answers than anything else: a LEFT JOIN quietly turned into an INNER
one, `COUNT(*)` counting a row that isn't there, and a join that multiplies rows so that every sum comes out too
big.*

!!! abstract "In this chapter"
    **You will learn:**

    - `INNER JOIN`, `LEFT JOIN`, `RIGHT JOIN`, `FULL JOIN` and `CROSS JOIN`, with the rows each keeps
    - why a condition on the right-hand table belongs in `ON`, not `WHERE`, after a LEFT JOIN
    - counting after a LEFT JOIN: `COUNT(*)` versus `COUNT(column)`
    - joining three or more tables
    - **fan-out**: how joining to a "many" table multiplies rows, how to spot it, and how to avoid it
    - `USING`, joins on conditions other than `=`, and why `NATURAL JOIN` is best avoided

    **You need:** chapters 2 and 7, and the [sample database](sample-database.md).

## 8.1 INNER JOIN: only the pairs that match { #inner }

Each order holds a `customer_id`. To show the customer's name beside the order, join the two tables on that column:

<!-- sql -->
```sql
SELECT o.order_id, o.order_date, c.name
FROM orders o
INNER JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_date < '2026-02-01'
ORDER BY o.order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| order_id | order_date | name |
| --- | --- | --- |
| 101 | 2026-01-03 | Ana Silva |
| 102 | 2026-01-03 | Ben Okafor |
| 103 | 2026-01-15 | Ana Silva |
| 104 | 2026-01-20 | Chen Wei |
| 105 | 2026-01-28 | Dana Kim |
<!-- /result -->

`o` and `c` are **aliases**: short names for the tables, so `o.order_id` means "order_id from orders". Use them in
every query with more than one table; they make it clear where each column comes from, and a column name that exists
in both tables (like `customer_id`) must be written with its table's alias in front.

How to think about it: for each order, find the customer rows whose `customer_id` equals the order's; output one row
per pair found. An order with **no** matching customer produces no row at all. Count the whole result:

<!-- sql -->
```sql
SELECT COUNT(*) AS orders_with_a_customer
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| orders_with_a_customer |
| --- |
| 19 |
<!-- /result -->

There are 20 orders, but only 19 rows: the guest order 108 has `customer_id` NULL, NULL equals nothing, so it has no
partner and disappears. `JOIN` on its own means `INNER JOIN`.

## 8.2 LEFT JOIN: keep every row on the left { #left }

A **LEFT JOIN** keeps every row of the left table (the one written first). Where nothing matches on the right, the
right-hand columns are filled with NULL.

<!-- sql -->
```sql
SELECT c.customer_id, c.name, o.order_id, o.status
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id
WHERE c.customer_id >= 7
ORDER BY c.customer_id, o.order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| customer_id | name | order_id | status |
| --- | --- | --- | --- |
| 7 | Gus Novak | 111 | shipped |
| 8 | Hana Sato | 114 | shipped |
| 9 | Ivan Petrov | *NULL* | *NULL* |
| 10 | Ana Silva | 117 | shipped |
<!-- /result -->

Ivan Petrov (9) has no orders, yet he is still in the result, with NULL in the order columns. That NULL is how you
find "rows with no match": keep only the rows where a right-hand column that can't otherwise be NULL is NULL.

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

This is the **anti join**, one of three ways to write "customers with no orders"; [chapter 9](09-Self-Semi-and-Anti-Joins.md)
compares them. Test on `o.order_id`, the right table's key, which is never NULL in a real row.

## 8.3 The trap: WHERE turns a LEFT JOIN into an INNER JOIN { #on-vs-where }

The task: "every customer, with their **shipped** orders; show customers with none as well."

!!! failure "The usual wrong answer"
    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name, o.order_id
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.customer_id
    WHERE o.status = 'shipped'
      AND c.customer_id IN (3, 6, 9)
    ORDER BY c.customer_id, o.order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | customer_id | name | order_id |
    | --- | --- | --- |
    | 3 | Chen Wei | 118 |
    | 6 | Farah Haddad | 109 |
    <!-- /result -->

    Ivan Petrov (9) has vanished. The LEFT JOIN gave him a row with `o.status` NULL, then WHERE tested
    `NULL = 'shipped'`, which is not true, and threw the row away. Any WHERE condition on a right-hand column that
    rejects NULL does this: the LEFT JOIN now behaves exactly like an INNER JOIN.

Put the condition on the right-hand table **in the ON clause**. ON decides which rows match; the LEFT JOIN then
still keeps every left row:

<!-- sql -->
```sql
SELECT c.customer_id, c.name, o.order_id
FROM customers c
LEFT JOIN orders o
       ON o.customer_id = c.customer_id
      AND o.status = 'shipped'
WHERE c.customer_id IN (3, 6, 9)
ORDER BY c.customer_id, o.order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| customer_id | name | order_id |
| --- | --- | --- |
| 3 | Chen Wei | 118 |
| 6 | Farah Haddad | 109 |
| 9 | Ivan Petrov | *NULL* |
<!-- /result -->

Chen Wei (3) keeps his shipped order 118 (his cancelled 104 is not a match), Farah Haddad (6) keeps 109 (116 is
pending), and Ivan is back with NULL. The rule:

| Condition on | After a LEFT JOIN, put it in |
| --- | --- |
| the left table (`c.customer_id IN (...)`) | `WHERE` |
| the right table (`o.status = 'shipped'`) | `ON` |
| "the right side is missing" (`o.order_id IS NULL`) | `WHERE` (that is the point of it) |

For an INNER JOIN, ON and WHERE give the same result; it makes no difference where a condition goes.

## 8.4 Counting after a LEFT JOIN { #count-left }

"The number of orders for every customer, including those with none."

!!! failure "The usual wrong answer"
    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name, COUNT(*) AS orders
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.customer_id
    GROUP BY c.customer_id, c.name
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

    | customer_id | name | orders |
    | --- | --- | --- |
    | 1 | Ana Silva | 5 |
    | 2 | Ben Okafor | 3 |
    | 3 | Chen Wei | 2 |
    | 4 | Dana Kim | 2 |
    | 5 | Eli Cohen | 2 |
    | 6 | Farah Haddad | 2 |
    | 7 | Gus Novak | 1 |
    | 8 | Hana Sato | 1 |
    | 9 | Ivan Petrov | 1 |
    | 10 | Ana Silva | 1 |
    <!-- /result -->

    Ivan Petrov shows **1** order. He has none, but the LEFT JOIN gave him one row (full of NULLs), and `COUNT(*)`
    counts rows.

Count a column from the right-hand table instead. `COUNT(column)` skips NULLs, so Ivan's padded row counts 0:

<!-- sql -->
```sql
SELECT c.customer_id, c.name, COUNT(o.order_id) AS orders
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
ORDER BY c.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

| customer_id | name | orders |
| --- | --- | --- |
| 1 | Ana Silva | 5 |
| 2 | Ben Okafor | 3 |
| 3 | Chen Wei | 2 |
| 4 | Dana Kim | 2 |
| 5 | Eli Cohen | 2 |
| 6 | Farah Haddad | 2 |
| 7 | Gus Novak | 1 |
| 8 | Hana Sato | 1 |
| 9 | Ivan Petrov | 0 |
| 10 | Ana Silva | 1 |
<!-- /result -->

The same goes for sums: `SUM` of nothing but NULLs is NULL, not 0. Wrap it, `COALESCE(SUM(x), 0)`, when the task wants
a zero.

## 8.5 RIGHT JOIN and FULL JOIN { #right-full }

A **RIGHT JOIN** is a LEFT JOIN written the other way round: it keeps every row of the right-hand table. `A RIGHT
JOIN B` gives the same rows as `B LEFT JOIN A`. Most people only ever write LEFT JOIN and put the table to keep first;
that is easier to read. SQLite has had RIGHT and FULL JOIN only since version 3.39 (2022); MySQL has RIGHT JOIN but
no FULL JOIN.

A **FULL JOIN** (FULL OUTER JOIN) keeps the unmatched rows of **both** sides. Customers and orders have one of each:
a customer with no orders and an order with no customer.

<!-- sql -->
```sql
SELECT c.customer_id, c.name, o.order_id
FROM customers c
FULL JOIN orders o ON o.customer_id = c.customer_id
WHERE c.customer_id IS NULL OR o.order_id IS NULL;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| customer_id | name | order_id |
| --- | --- | --- |
| *NULL* | *NULL* | 108 |
| 9 | Ivan Petrov | *NULL* |
<!-- /result -->

The WHERE keeps only the rows that found no partner: Ivan from the left, guest order 108 from the right. This is a
standard way to compare two lists, for example yesterday's and today's copy of a table: what is only in one, what is
only in the other. ([Chapter 23](23-Data-Quality-Checks.md) uses it to reconcile tables.)

## 8.6 CROSS JOIN: every pair { #cross }

A **CROSS JOIN** has no condition: every row on the left is paired with every row on the right. 3 rows by 4 rows
gives 12. It sounds useless, and it is the right tool for "every customer for every month, even months with no
orders": build the full grid first, then LEFT JOIN the facts onto it.

<!-- sql -->
```sql
WITH months AS (
  SELECT '2026-01' AS month UNION ALL
  SELECT '2026-02' UNION ALL
  SELECT '2026-03'
)
SELECT c.customer_id, m.month, COUNT(o.order_id) AS orders
FROM customers c
CROSS JOIN months m
LEFT JOIN orders o
       ON o.customer_id = c.customer_id
      AND SUBSTR(CAST(o.order_date AS TEXT), 1, 7) = m.month
WHERE c.customer_id IN (1, 4)
GROUP BY c.customer_id, m.month
ORDER BY c.customer_id, m.month;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

| customer_id | month | orders |
| --- | --- | --- |
| 1 | 2026-01 | 2 |
| 1 | 2026-02 | 1 |
| 1 | 2026-03 | 1 |
| 4 | 2026-01 | 1 |
| 4 | 2026-02 | 0 |
| 4 | 2026-03 | 1 |
<!-- /result -->

Dana Kim (4) ordered nothing in February, and the grid still gives her a February row with 0. Without the cross join
that row would simply be missing, and a chart or a "months with no orders" question would be wrong. A forgotten join
condition makes an accidental cross join, which is why a result with far too many rows is the first sign of a
missing ON.

## 8.7 Three tables and more { #many-tables }

Joins chain: each new JOIN adds a table to the rows built so far. Revenue by product category, from shipped orders:

<!-- sql -->
```sql
SELECT p.category,
       SUM(i.quantity * i.unit_price) AS revenue
FROM orders o
JOIN order_items i ON i.order_id = o.order_id
JOIN products p    ON p.product_id = i.product_id
WHERE o.status = 'shipped'
GROUP BY p.category
ORDER BY revenue DESC;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| category | revenue |
| --- | --- |
| Office | 618.25 |
| Home | 196.00 |
| Kitchen | 140.75 |
| *NULL* | 50.00 |
<!-- /result -->

Read a chain of joins as a path through the diagram on the [sample database page](sample-database.md#tables):
orders, to their items, to each item's product. Each step follows one arrow.

## 8.8 Fan-out: when a join multiplies rows { #fan-out }

A join produces one row **per matching pair**. Join an order to its items and an order with three items becomes three
rows. That is right when you want items. It is wrong the moment you then count or sum something that belongs to the
order.

!!! failure "The usual wrong answer: orders per customer, after joining the items"
    <!-- sql -->
    ```sql
    SELECT o.customer_id, COUNT(*) AS orders
    FROM orders o
    JOIN order_items i ON i.order_id = o.order_id
    WHERE o.customer_id IN (1, 2)
    GROUP BY o.customer_id
    ORDER BY o.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | customer_id | orders |
    | --- | --- |
    | 1 | 8 |
    | 2 | 4 |
    <!-- /result -->

    Ana Silva (1) has 5 orders, not 8; Ben Okafor has 3, not 4. Every order was counted once per item.

`COUNT(DISTINCT o.order_id)` mends a count, but `SUM(DISTINCT ...)` exists and does not mend a sum: it would
also drop equal values that really do repeat. The reliable cure is to **aggregate before you join**, so that each side has
one row per key when the join happens.

The worst case is joining one table to **two** different "many" tables. Each customer's orders get paired with each
of their logins:

!!! failure "Two many-sides at once"
    <!-- sql -->
    ```sql
    SELECT c.customer_id,
           COUNT(o.order_id)   AS orders,
           COUNT(l.login_date) AS logins
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.customer_id
    LEFT JOIN logins l ON l.customer_id = c.customer_id
    WHERE c.customer_id IN (1, 2)
    GROUP BY c.customer_id
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | customer_id | orders | logins |
    | --- | --- | --- |
    | 1 | 30 | 30 |
    | 2 | 12 | 12 |
    <!-- /result -->

    Ana Silva has 5 orders and 6 logins; the join made 5 × 6 = 30 rows, so both counts say 30.

Aggregate each side first, then join the one-row-per-customer results:

<!-- sql -->
```sql
WITH o AS (SELECT customer_id, COUNT(*) AS orders FROM orders GROUP BY customer_id),
     l AS (SELECT customer_id, COUNT(*) AS logins FROM logins GROUP BY customer_id)
SELECT c.customer_id,
       COALESCE(o.orders, 0) AS orders,
       COALESCE(l.logins, 0) AS logins
FROM customers c
LEFT JOIN o ON o.customer_id = c.customer_id
LEFT JOIN l ON l.customer_id = c.customer_id
WHERE c.customer_id IN (1, 2)
ORDER BY c.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| customer_id | orders | logins |
| --- | --- | --- |
| 1 | 5 | 6 |
| 2 | 3 | 4 |
<!-- /result -->

!!! tip "Interview tip: check the grain"
    Before and after each join, ask "what is one row now?" (one per customer, one per order, one per order item).
    If the answer changes in a way you did not intend, sums will be wrong. In a test, run `SELECT COUNT(*)` on the
    joined rows and compare it with what you expect; it takes ten seconds and catches most fan-out bugs.

## 8.9 USING, other join conditions, and NATURAL JOIN { #using }

When the join columns have the same name on both sides, `USING (column)` is a shorter ON, and the column appears once
in the output:

<!-- sql -->
```sql
SELECT order_id, customer_id, name
FROM orders
JOIN customers USING (customer_id)
WHERE order_id IN (101, 102)
ORDER BY order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| order_id | customer_id | name |
| --- | --- | --- |
| 101 | 1 | Ana Silva |
| 102 | 2 | Ben Okafor |
<!-- /result -->

`NATURAL JOIN` goes further and joins on **every** column whose name appears in both tables. That breaks silently:
add a `created_at` column to both `orders` and `customers`, and `orders NATURAL JOIN customers` would match on it
as well as on `customer_id`, so almost every row would vanish. Write the condition out.

A join condition doesn't have to be `=`. Here each product is paired with the cheaper products in its category, a
**non-equi join**:

<!-- sql -->
```sql
SELECT a.name AS product, b.name AS cheaper_in_same_category
FROM products a
JOIN products b
  ON b.category = a.category
 AND b.price < a.price
WHERE a.category = 'Kitchen' OR a.name = 'Desk lamp'
ORDER BY a.name, b.name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| product | cheaper_in_same_category |
| --- | --- |
| Desk lamp | Bookend |
| Desk lamp | Plant pot |
| Tea kettle | Coffee mug |
<!-- /result -->

Joining a table to itself, as here, is a **self join**; chapter 9 is about it. Note that the wall clock costs the
same as the desk lamp, so `<` leaves it out; `<=` would bring it back, along with the lamp paired with itself.

## 8.10 Summary { #summary }

| Join | Keeps |
| --- | --- |
| `INNER JOIN` (`JOIN`) | pairs that match; unmatched rows on either side are dropped |
| `LEFT JOIN` | every left row; right columns NULL when nothing matches |
| `RIGHT JOIN` | every right row (write it as a LEFT JOIN instead) |
| `FULL JOIN` | every row from both sides |
| `CROSS JOIN` | every pair, no condition |

- After a LEFT JOIN, conditions on the right table go in ON; in WHERE they undo the LEFT JOIN.
- After a LEFT JOIN, count with `COUNT(right_table.key)`, not `COUNT(*)`.
- A join to a "many" table multiplies rows. Aggregate first, then join.
- NULL never matches in a join condition.

## Practice { #practice }

**8.1** List every product with the total units sold, showing 0 for a product never sold. Sort by units, highest
first, then by product name.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT p.product_id, p.name, COALESCE(SUM(i.quantity), 0) AS units
    FROM products p
    LEFT JOIN order_items i ON i.product_id = p.product_id
    GROUP BY p.product_id, p.name
    ORDER BY units DESC, p.name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

    | product_id | name | units |
    | --- | --- | --- |
    | 2 | Notebook | 25 |
    | 4 | Coffee mug | 9 |
    | 8 | Plant pot | 6 |
    | 1 | Desk lamp | 5 |
    | 3 | Fountain pen | 4 |
    | 10 | Gift card | 3 |
    | 6 | Office chair | 3 |
    | 5 | Tea kettle | 3 |
    | 7 | Monitor stand | 2 |
    | 9 | Wall clock | 1 |
    | 11 | Bookend | 0 |
    <!-- /result -->

    The bookend has no items; the LEFT JOIN keeps it, `SUM` of its NULL gives NULL, and `COALESCE` turns that into 0.

**8.2** Products that have never been sold, by an anti join.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT p.product_id, p.name
    FROM products p
    LEFT JOIN order_items i ON i.product_id = p.product_id
    WHERE i.order_id IS NULL
    ORDER BY p.product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | product_id | name |
    | --- | --- |
    | 11 | Bookend |
    <!-- /result -->

**8.3** For each order, its date, the customer's name (or `guest` when there is no customer) and the order's
revenue. Only orders from February.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT o.order_id, o.order_date,
           COALESCE(c.name, 'guest')       AS customer,
           SUM(i.quantity * i.unit_price) AS revenue
    FROM orders o
    LEFT JOIN customers c ON c.customer_id = o.customer_id
    JOIN order_items i    ON i.order_id = o.order_id
    WHERE o.order_date >= '2026-02-01' AND o.order_date < '2026-03-01'
    GROUP BY o.order_id, o.order_date, c.name
    ORDER BY o.order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

    | order_id | order_date | customer | revenue |
    | --- | --- | --- | --- |
    | 106 | 2026-02-02 | Ben Okafor | 56.50 |
    | 107 | 2026-02-02 | Eli Cohen | 36.75 |
    | 108 | 2026-02-10 | guest | 50.00 |
    | 109 | 2026-02-14 | Farah Haddad | 65.00 |
    | 110 | 2026-02-20 | Ana Silva | 32.50 |
    | 111 | 2026-02-21 | Gus Novak | 36.75 |
    <!-- /result -->

    The customer join must be LEFT, or the guest order 108 disappears. Joining to the items multiplies rows, but
    that is fine here: the only thing summed comes from the items, and the GROUP BY brings it back to one row per
    order. The date range `>= start AND < next month's start` is the safe way to take a month; it works whatever the
    type of the column.

**8.4** Customers who have bought something from the Office category in a shipped order. Each customer once.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT DISTINCT c.customer_id, c.name
    FROM customers c
    JOIN orders o      ON o.customer_id = c.customer_id
    JOIN order_items i ON i.order_id = o.order_id
    JOIN products p    ON p.product_id = i.product_id
    WHERE o.status = 'shipped' AND p.category = 'Office'
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | customer_id | name |
    | --- | --- |
    | 1 | Ana Silva |
    | 2 | Ben Okafor |
    | 4 | Dana Kim |
    | 10 | Ana Silva |
    <!-- /result -->

    `DISTINCT` is needed because a customer with several Office items appears once per item. An `EXISTS` subquery
    (chapter 9) avoids making the duplicates in the first place.

**8.5** For each sale, show the price paid and today's price, but only where they differ.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT i.order_id, p.name, i.unit_price AS paid, p.price AS price_now
    FROM order_items i
    JOIN products p ON p.product_id = i.product_id
    WHERE i.unit_price <> p.price
    ORDER BY i.order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | order_id | name | paid | price_now |
    | --- | --- | --- | --- |
    | 109 | Tea kettle | 30.00 | 32.00 |
    | 120 | Office chair | 139.00 | 149.00 |
    <!-- /result -->

**8.6** Every employee with their manager's name; the person with no manager should still appear, with NULL.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT e.name AS employee, m.name AS manager
    FROM employees e
    LEFT JOIN employees m ON m.employee_id = e.manager_id
    ORDER BY e.employee_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 12 rows.</p>

    | employee | manager |
    | --- | --- |
    | Maya Rossi | *NULL* |
    | Tom Becker | Maya Rossi |
    | Priya Nair | Tom Becker |
    | Sam Lee | Tom Becker |
    | Lucia Gomez | Tom Becker |
    | Omar Aziz | Maya Rossi |
    | Nina Berg | Omar Aziz |
    | Raj Patel | Omar Aziz |
    | Zoe Martin | Omar Aziz |
    | Kwame Mensah | Maya Rossi |
    | Ella Novak | Kwame Mensah |
    | Leo Park | Kwame Mensah |
    <!-- /result -->

    The same table twice, with two aliases: `e` for the employee, `m` for the manager. Maya Rossi has no manager, so
    the LEFT JOIN keeps her with a NULL. Chapter 9 goes further with self joins.

**8.7** This query is meant to show every customer from Canada with their number of pending orders (0 if none).
What does it return, and how would you fix it?

```text
SELECT c.name, COUNT(o.order_id) AS pending
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id
WHERE c.country = 'Canada' AND o.status = 'pending'
GROUP BY c.customer_id, c.name;
```

??? success "Answer"
    It returns only Farah Haddad: the `o.status = 'pending'` in WHERE removes the customers whose only rows have a
    different status or NULL. Move it into ON:

    <!-- sql -->
    ```sql
    SELECT c.name, COUNT(o.order_id) AS pending
    FROM customers c
    LEFT JOIN orders o
           ON o.customer_id = c.customer_id
          AND o.status = 'pending'
    WHERE c.country = 'Canada'
    GROUP BY c.customer_id, c.name
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | name | pending |
    | --- | --- |
    | Ana Silva | 0 |
    | Farah Haddad | 1 |
    | Ivan Petrov | 0 |
    <!-- /result -->

**8.8** For each customer who has logged in at least once: the number of logins and their total shipped revenue
(0 if none). Watch the grain.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH l AS (
      SELECT customer_id, COUNT(*) AS logins
      FROM logins
      GROUP BY customer_id
    ),
    r AS (
      SELECT o.customer_id, SUM(i.quantity * i.unit_price) AS revenue
      FROM orders o
      JOIN order_items i ON i.order_id = o.order_id
      WHERE o.status = 'shipped'
      GROUP BY o.customer_id
    )
    SELECT l.customer_id, l.logins, COALESCE(r.revenue, 0) AS revenue
    FROM l
    LEFT JOIN r ON r.customer_id = l.customer_id
    ORDER BY l.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | customer_id | logins | revenue |
    | --- | --- | --- |
    | 1 | 6 | 289.00 |
    | 2 | 4 | 205.50 |
    | 4 | 4 | 205.50 |
    | 6 | 1 | 65.00 |
    <!-- /result -->

    Joining logins and items in one go would multiply each login by each item. Two CTEs, each one row per
    customer, then one join.

**8.9** How many rows does `SELECT * FROM customers CROSS JOIN products` return? Check with a query.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT COUNT(*) AS pairs FROM customers CROSS JOIN products;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | pairs |
    | --- |
    | 110 |
    <!-- /result -->

    10 customers times 11 products.

**8.10** Pairs of customers who live in the same city, each pair once (not A–B and B–A, and nobody with themselves).

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT a.name AS customer_a, b.name AS customer_b, a.city
    FROM customers a
    JOIN customers b
      ON b.city = a.city
     AND b.customer_id > a.customer_id
    ORDER BY a.customer_id, b.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_a | customer_b | city |
    | --- | --- | --- |
    | Ana Silva | Farah Haddad | Toronto |
    | Ana Silva | Ivan Petrov | Toronto |
    | Farah Haddad | Ivan Petrov | Toronto |
    <!-- /result -->

    `b.customer_id > a.customer_id` keeps each pair once and leaves out a customer paired with themselves. Three
    customers in Toronto make three pairs. Eli Cohen's NULL city matches nobody, not even other NULL cities.

**Next:** [9. Self, semi and anti joins](09-Self-Semi-and-Anti-Joins.md).
