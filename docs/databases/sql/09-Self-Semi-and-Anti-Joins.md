# 9. Self, semi and anti joins

*Three kinds of join answer three kinds of question that come up in almost every SQL test. A self join compares rows
of a table with other rows of the same table: an employee with their manager. A semi join asks "is there at least
one?": customers who have ordered. An anti join asks "is there none?": customers who never ordered. The anti join
hides the most famous trap in SQL, `NOT IN` with a NULL, and this chapter shows it failing on the sample data.*

!!! abstract "In this chapter"
    **You will learn:**

    - self joins: one table, two aliases; employees and managers, pairs, levels of a hierarchy
    - semi joins with `EXISTS` and `IN`, and why a plain JOIN gives duplicates instead
    - anti joins three ways: `NOT EXISTS`, `LEFT JOIN ... IS NULL`, `NOT IN`
    - why `NOT IN` returns nothing when the list holds a NULL, and the fix
    - anti joins with a condition: "no shipped order in March"

    **You need:** [6. NULL](06-Null-and-Three-Valued-Logic.md) and [8. joins](08-Joins-Inner-Left-Right-Full-Cross.md).

## 9.1 Self joins { #self }

A **self join** joins a table to itself. The table appears twice under two aliases, and each alias plays a role. In
`employees`, `manager_id` holds another employee's `employee_id`; to put each person beside their manager, use one
alias for the employee and one for the manager:

<!-- sql -->
```sql
SELECT e.name AS employee, e.salary,
       m.name AS manager,  m.salary AS manager_salary
FROM employees e
JOIN employees m ON m.employee_id = e.manager_id
WHERE e.department = 'Engineering'
ORDER BY e.salary DESC, e.name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| employee | salary | manager | manager_salary |
| --- | --- | --- | --- |
| Tom Becker | 140000 | Maya Rossi | 180000 |
| Priya Nair | 120000 | Tom Becker | 140000 |
| Sam Lee | 120000 | Tom Becker | 140000 |
| Lucia Gomez | 95000 | Tom Becker | 140000 |
<!-- /result -->

It is an inner join, so Maya Rossi, who has no manager, would not appear (she is not in Engineering anyway). Use a
LEFT JOIN when everyone must be listed.

**Going up two levels** takes a third alias: each employee, their manager, and their manager's manager.

<!-- sql -->
```sql
SELECT e.name AS employee, m.name AS manager, g.name AS managers_manager
FROM employees e
LEFT JOIN employees m ON m.employee_id = e.manager_id
LEFT JOIN employees g ON g.employee_id = m.manager_id
WHERE e.department IN ('Engineering', 'Management')
ORDER BY e.employee_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| employee | manager | managers_manager |
| --- | --- | --- |
| Maya Rossi | *NULL* | *NULL* |
| Tom Becker | Maya Rossi | *NULL* |
| Priya Nair | Tom Becker | Maya Rossi |
| Sam Lee | Tom Becker | Maya Rossi |
| Lucia Gomez | Tom Becker | Maya Rossi |
<!-- /result -->

Each extra level needs one more join. For a hierarchy of unknown depth, a recursive CTE walks it to the end
([chapter 11](11-CTEs-and-Recursive-CTEs.md#recursive)).

**Comparing with the manager** is a classic test question. Who earns at least 85% of what their manager earns?

<!-- sql -->
```sql
SELECT e.name AS employee, e.salary, m.name AS manager, m.salary AS manager_salary,
       ROUND(100.0 * e.salary / m.salary, 1) AS pct_of_manager
FROM employees e
JOIN employees m ON m.employee_id = e.manager_id
WHERE e.salary >= 0.85 * m.salary
ORDER BY pct_of_manager DESC, e.name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| employee | salary | manager | manager_salary | pct_of_manager |
| --- | --- | --- | --- | --- |
| Priya Nair | 120000 | Tom Becker | 140000 | 85.7 |
| Sam Lee | 120000 | Tom Becker | 140000 | 85.7 |
<!-- /result -->

Leo Park's salary is NULL, so his comparison is unknown and WHERE drops him, which is what you want.

**Pairs from the same group**: employees who share a manager, each pair once. The condition `a.employee_id <
b.employee_id` stops a person being paired with themselves and stops each pair appearing twice (A–B and B–A).

<!-- sql -->
```sql
SELECT a.name AS colleague_a, b.name AS colleague_b, m.name AS shared_manager
FROM employees a
JOIN employees b ON b.manager_id = a.manager_id AND a.employee_id < b.employee_id
JOIN employees m ON m.employee_id = a.manager_id
WHERE m.name = 'Omar Aziz'
ORDER BY a.employee_id, b.employee_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| colleague_a | colleague_b | shared_manager |
| --- | --- | --- |
| Nina Berg | Raj Patel | Omar Aziz |
| Nina Berg | Zoe Martin | Omar Aziz |
| Raj Patel | Zoe Martin | Omar Aziz |
<!-- /result -->

## 9.2 Semi joins: "at least one" { #semi }

The question: "customers who have placed at least one shipped order". A plain JOIN finds them, but returns one row
per matching order:

!!! failure "The usual wrong answer"
    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    WHERE o.status = 'shipped'
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 15 rows.</p>

    | customer_id | name |
    | --- | --- |
    | 1 | Ana Silva |
    | 1 | Ana Silva |
    | 1 | Ana Silva |
    | 1 | Ana Silva |
    | 1 | Ana Silva |
    | 2 | Ben Okafor |
    | 2 | Ben Okafor |
    | 3 | Chen Wei |
    | 4 | Dana Kim |
    | 4 | Dana Kim |
    | 5 | Eli Cohen |
    | 6 | Farah Haddad |
    | 7 | Gus Novak |
    | 8 | Hana Sato |
    | 10 | Ana Silva |
    <!-- /result -->

    Ana Silva (1) is listed five times. The question was about customers, so each should appear once.

`SELECT DISTINCT` hides the duplicates afterwards. A **semi join** never makes them: it keeps each left row once if
**at least one** match exists. SQL writes it with `EXISTS` or `IN`:

<!-- sql -->
```sql
SELECT c.customer_id, c.name
FROM customers c
WHERE EXISTS (
  SELECT 1
  FROM orders o
  WHERE o.customer_id = c.customer_id
    AND o.status = 'shipped'
)
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

`EXISTS (subquery)` is true as soon as the subquery finds one row; what it selects doesn't matter, so `SELECT 1` is
the custom. The subquery refers to `c.customer_id` from the outer query: it is **correlated**, run (in principle) once
per customer. The database is free to run it more cleverly, and modern ones do.

The same with `IN`:

<!-- sql -->
```sql
SELECT c.customer_id, c.name
FROM customers c
WHERE c.customer_id IN (SELECT o.customer_id FROM orders o WHERE o.status = 'shipped')
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

`IN` and `EXISTS` give the same answer here. For semi joins either is fine; the difference matters for their
negations, next.

## 9.3 Anti joins: "none at all" { #anti }

"Customers who have never placed an order." Three ways to write it. Two are always right.

**1. NOT EXISTS**, the safest:

<!-- sql -->
```sql
SELECT c.customer_id, c.name
FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id)
ORDER BY c.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| customer_id | name |
| --- | --- |
| 9 | Ivan Petrov |
<!-- /result -->

**2. LEFT JOIN and IS NULL** (chapter 8): keep the rows where the join found nothing.

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

**3. NOT IN**, which looks the simplest and is broken on this data:

!!! failure "The NOT IN trap"
    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name
    FROM customers c
    WHERE c.customer_id NOT IN (SELECT o.customer_id FROM orders o)
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

    | customer_id | name |
    | --- | --- |
    | *(no rows)* | |
    <!-- /result -->

    No rows at all, on both databases. Ivan Petrov is not in the list of customer ids in `orders`, yet he is not
    returned.

**Why.** `9 NOT IN (1, 2, 3, NULL)` means `9 <> 1 AND 9 <> 2 AND 9 <> 3 AND 9 <> NULL`. The last part compares with
NULL, so it is **unknown**, and "true and unknown" is unknown. WHERE keeps only rows that are true. The guest order 108
has `customer_id` NULL, so the list contains a NULL, and `NOT IN` can never be true for anybody. (Chapter 6 has the
whole three-valued logic.)

You can see it directly:

<!-- sql -->
```sql
SELECT 9 NOT IN (1, 2, 3)       AS without_null,
       9 NOT IN (1, 2, 3, NULL) AS with_null;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| without_null | with_null |
| --- | --- |
| true | *NULL* |
<!-- /result -->

PostgreSQL prints true and NULL (unknown); SQLite prints 1 and NULL, since it has no separate true/false type.

If you must use NOT IN, take the NULLs out of the list:

<!-- sql -->
```sql
SELECT c.customer_id, c.name
FROM customers c
WHERE c.customer_id NOT IN (SELECT o.customer_id FROM orders o WHERE o.customer_id IS NOT NULL)
ORDER BY c.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| customer_id | name |
| --- | --- |
| 9 | Ivan Petrov |
<!-- /result -->

!!! tip "Interview tip: say why you chose NOT EXISTS"
    Writing `NOT EXISTS` and adding one sentence, "NOT IN would return nothing if the subquery ever returned a
    NULL", shows the interviewer you know the trap. A column that is nullable today (even if it holds no NULLs yet)
    is enough reason. `IN` (without NOT) has no such problem: a NULL in the list just never matches.

!!! warning "Speed on SQLite"
    On PostgreSQL, `NOT EXISTS` and `LEFT JOIN ... IS NULL` run equally fast. On SQLite, `NOT EXISTS` runs its
    subquery once per outer row: with no index on the inner column (`orders.customer_id`), 50,000 customers against
    200,000 orders did not finish in 30 seconds, while `LEFT JOIN ... IS NULL` took about a tenth of a second
    ([chapter 26](26-Making-Slow-Queries-Fast.md#anti-join) has the timings). On SQLite with large tables, prefer the
    `LEFT JOIN` form.

| Way | Safe with NULLs | Notes |
| --- | --- | --- |
| `NOT EXISTS` | yes | The standard choice. Easy to add conditions inside. |
| `LEFT JOIN ... WHERE right.key IS NULL` | yes | Test the right table's key, a column that is never NULL in a real row. |
| `NOT IN (subquery)` | **no** | Returns nothing if the subquery returns any NULL. |
| `EXCEPT` | yes | Compares whole rows; [chapter 12](12-Set-Operations.md). |

## 9.4 Anti joins with conditions { #anti-conditions }

The condition goes **inside** the subquery (or in the ON of the LEFT JOIN). "Customers with no shipped order in
March 2026", among customers who signed up before March:

<!-- sql -->
```sql
SELECT c.customer_id, c.name
FROM customers c
WHERE c.signup_date < '2026-03-01'
  AND NOT EXISTS (
    SELECT 1
    FROM orders o
    WHERE o.customer_id = c.customer_id
      AND o.status = 'shipped'
      AND o.order_date >= '2026-03-01'
      AND o.order_date <  '2026-04-01'
  )
ORDER BY c.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| customer_id | name |
| --- | --- |
| 2 | Ben Okafor |
| 3 | Chen Wei |
| 5 | Eli Cohen |
| 6 | Farah Haddad |
| 7 | Gus Novak |
<!-- /result -->

Ben Okafor (2) did order in March, but that order (113) was cancelled, so he counts as having no shipped March
order. Farah Haddad's March order is pending. Put the status and date conditions outside the subquery and the
meaning changes completely.

The LEFT JOIN version keeps the conditions in ON, for the reason in [chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md#on-vs-where):

<!-- sql -->
```sql
SELECT c.customer_id, c.name
FROM customers c
LEFT JOIN orders o
       ON o.customer_id = c.customer_id
      AND o.status = 'shipped'
      AND o.order_date >= '2026-03-01'
      AND o.order_date <  '2026-04-01'
WHERE c.signup_date < '2026-03-01'
  AND o.order_id IS NULL
ORDER BY c.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| customer_id | name |
| --- | --- |
| 2 | Ben Okafor |
| 3 | Chen Wei |
| 5 | Eli Cohen |
| 6 | Farah Haddad |
| 7 | Gus Novak |
<!-- /result -->

## 9.5 Summary { #summary }

- A self join uses one table under two (or more) aliases, each with its own role.
- Pairs once: join on the shared value and `a.id < b.id`.
- Semi join ("at least one"): `EXISTS` or `IN`. A plain JOIN repeats the left row once per match.
- Anti join ("none"): `NOT EXISTS` or `LEFT JOIN ... IS NULL`. Avoid `NOT IN` with a subquery: one NULL makes it
  return nothing.
- Conditions about the other table go inside the subquery, or in ON.

## Practice { #practice }

**9.1** Employees who have no one reporting to them (nobody's manager). Use NOT EXISTS.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT e.employee_id, e.name
    FROM employees e
    WHERE NOT EXISTS (SELECT 1 FROM employees r WHERE r.manager_id = e.employee_id)
    ORDER BY e.employee_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 8 rows.</p>

    | employee_id | name |
    | --- | --- |
    | 3 | Priya Nair |
    | 4 | Sam Lee |
    | 5 | Lucia Gomez |
    | 7 | Nina Berg |
    | 8 | Raj Patel |
    | 9 | Zoe Martin |
    | 11 | Ella Novak |
    | 12 | Leo Park |
    <!-- /result -->

    Now try it with `WHERE e.employee_id NOT IN (SELECT manager_id FROM employees)`: Maya Rossi's `manager_id` is
    NULL, so it returns no rows, the same trap as in 9.3.

**9.2** Managers, with how many people report directly to them.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT m.employee_id, m.name, COUNT(*) AS direct_reports
    FROM employees m
    JOIN employees e ON e.manager_id = m.employee_id
    GROUP BY m.employee_id, m.name
    ORDER BY direct_reports DESC, m.employee_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | employee_id | name | direct_reports |
    | --- | --- | --- |
    | 1 | Maya Rossi | 3 |
    | 2 | Tom Becker | 3 |
    | 6 | Omar Aziz | 3 |
    | 10 | Kwame Mensah | 2 |
    <!-- /result -->

    A **self join**: `employees` appears twice, as `m` (the manager) and `e` (a person reporting to them),
    matched on `e.manager_id = m.employee_id`. Grouping by the manager counts their direct reports; people who
    manage no one have no match and are left out by the inner join.


**9.3** Products that have been sold in a shipped order to a customer in Canada. Each product once, no DISTINCT.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT p.product_id, p.name
    FROM products p
    WHERE EXISTS (
      SELECT 1
      FROM order_items i
      JOIN orders o    ON o.order_id = i.order_id
      JOIN customers c ON c.customer_id = o.customer_id
      WHERE i.product_id = p.product_id
        AND o.status = 'shipped'
        AND c.country = 'Canada'
    )
    ORDER BY p.product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | product_id | name |
    | --- | --- |
    | 1 | Desk lamp |
    | 2 | Notebook |
    | 4 | Coffee mug |
    | 5 | Tea kettle |
    | 6 | Office chair |
    <!-- /result -->

    The subquery can hold joins of its own; only its link to the outer row (`i.product_id = p.product_id`) makes it
    correlated.

**9.4** Customers who have logged in but never placed an order.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name
    FROM customers c
    WHERE EXISTS     (SELECT 1 FROM logins l WHERE l.customer_id = c.customer_id)
      AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id)
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

    | customer_id | name |
    | --- | --- |
    | *(no rows)* | |
    <!-- /result -->

    No rows: everyone who logged in has ordered. An empty result is a correct answer; in a test, check it by
    looking at the data (customers 1, 2, 4 and 6 logged in, and all four have orders).

**9.5** Employees who earn more than everyone else in their department hired before them. (Hint: NOT EXISTS with
two conditions.)

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT e.department, e.name, e.hire_date, e.salary
    FROM employees e
    WHERE e.salary IS NOT NULL
      AND NOT EXISTS (
        SELECT 1
        FROM employees x
        WHERE x.department = e.department
          AND x.hire_date  < e.hire_date
          AND x.salary    >= e.salary
      )
    ORDER BY e.department, e.hire_date;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | department | name | hire_date | salary |
    | --- | --- | --- | --- |
    | Engineering | Tom Becker | 2020-01-15 | 140000 |
    | Management | Maya Rossi | 2019-04-01 | 180000 |
    | Sales | Omar Aziz | 2020-07-01 | 110000 |
    | Support | Kwame Mensah | 2021-11-01 | 75000 |
    <!-- /result -->

    The first person hired in each department qualifies automatically (nobody earlier). Nobody later out-earns all
    their predecessors in this data: within each department, pay never goes up with a later hire date.

**9.6** Customers who have bought **every** product in the Kitchen category (in any order, any status).

??? success "Answer"
    "Every" is a double negative: customers for whom there is **no** Kitchen product that they have **not** bought.

    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name
    FROM customers c
    WHERE NOT EXISTS (
      SELECT 1
      FROM products p
      WHERE p.category = 'Kitchen'
        AND NOT EXISTS (
          SELECT 1
          FROM orders o
          JOIN order_items i ON i.order_id = o.order_id
          WHERE o.customer_id = c.customer_id
            AND i.product_id = p.product_id
        )
    )
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | customer_id | name |
    | --- | --- |
    | 1 | Ana Silva |
    | 6 | Farah Haddad |
    <!-- /result -->

    This is called **relational division**. A counting version is often easier to write under time pressure:
    count each customer's different Kitchen products and keep those whose count equals the number of Kitchen
    products.

    <!-- sql same -->
    ```sql
    SELECT c.customer_id, c.name
    FROM customers c
    JOIN orders o      ON o.customer_id = c.customer_id
    JOIN order_items i ON i.order_id = o.order_id
    JOIN products p    ON p.product_id = i.product_id
    WHERE p.category = 'Kitchen'
    GROUP BY c.customer_id, c.name
    HAVING COUNT(DISTINCT p.product_id) = (SELECT COUNT(*) FROM products WHERE category = 'Kitchen')
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 2 rows.</p>

    | customer_id | name |
    | --- | --- |
    | 1 | Ana Silva |
    | 6 | Farah Haddad |
    <!-- /result -->

**9.7** Pairs of products in the same category whose prices are within 5.00 of each other, each pair once.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT a.name AS product_a, b.name AS product_b, a.category, ABS(a.price - b.price) AS difference
    FROM products a
    JOIN products b
      ON b.category = a.category
     AND a.product_id < b.product_id
     AND ABS(a.price - b.price) <= 5
    ORDER BY a.category, a.product_id, b.product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | product_a | product_b | category | difference |
    | --- | --- | --- | --- |
    | Desk lamp | Wall clock | Home | 0.00 |
    | Plant pot | Bookend | Home | 2.75 |
    <!-- /result -->

    A self join that pairs products of the same category. `a.product_id < b.product_id` keeps each pair once
    (not A-B and B-A) and never pairs a product with itself. `ABS(...)` is the size of the difference whatever
    its sign.


**Next:** [10. Subqueries](10-Subqueries.md).
