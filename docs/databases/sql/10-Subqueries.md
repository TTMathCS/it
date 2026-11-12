# 10. Subqueries

*A subquery is a query inside another query, in brackets. It lets you use one answer to ask the next question:
"products dearer than the average", where the average is itself a query. This chapter covers the four places a
subquery can go (WHERE, SELECT, FROM and HAVING), the difference between a subquery that runs once and one that runs
for every row, and two traps: a "one value" subquery that returns several rows (PostgreSQL stops, SQLite quietly picks
one), and one that returns no rows at all.*

!!! abstract "In this chapter"
    **You will learn:**

    - scalar subqueries (one value) in WHERE, SELECT and HAVING
    - list subqueries with `IN`, and `ANY` / `ALL` (not in SQLite)
    - correlated subqueries: "above the average **of its own group**"
    - subqueries in FROM (derived tables) and why they need a name in most databases
    - what happens when a "one value" subquery returns two rows
    - when to use a subquery, a join, or a CTE

    **You need:** chapters 7 and 9.

## 10.1 One value: scalar subqueries { #scalar }

A subquery that returns one column and at most one row can be used anywhere a single value can. "Products that cost
more than the average product":

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

The database works out the inner query first (the average is 30.80 to two places) and then uses that number in the
outer WHERE. You can't write `WHERE price > AVG(price)`: an aggregate is not allowed in WHERE (chapter 7), and even if
it were, the outer query has no groups to average.

In SELECT, a scalar subquery adds the same value to every row; useful for "compared with the whole":

<!-- sql -->
```sql
SELECT name, price,
       ROUND(price - (SELECT AVG(price) FROM products), 2) AS above_average,
       ROUND(100.0 * price / (SELECT SUM(price) FROM products), 1) AS pct_of_all_prices
FROM products
WHERE category = 'Office'
ORDER BY price DESC;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| name | price | above_average | pct_of_all_prices |
| --- | --- | --- | --- |
| Office chair | 149.00 | 118.20 | 44.0 |
| Monitor stand | 32.00 | 1.20 | 9.4 |
| Fountain pen | 18.00 | -12.80 | 5.3 |
| Notebook | 3.25 | -27.55 | 1.0 |
<!-- /result -->

(A window function, `AVG(price) OVER ()`, does the same without a subquery: [chapter 13](13-Window-Functions-Ranking.md).)

## 10.2 Many values: IN, ANY, ALL { #in }

A subquery that returns one column and many rows makes a list for `IN`. Products that appear in at least one
cancelled order:

<!-- sql -->
```sql
SELECT product_id, name
FROM products
WHERE product_id IN (
  SELECT i.product_id
  FROM order_items i
  JOIN orders o ON o.order_id = i.order_id
  WHERE o.status = 'cancelled'
)
ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| product_id | name |
| --- | --- |
| 3 | Fountain pen |
| 5 | Tea kettle |
<!-- /result -->

Duplicates in the list don't matter to `IN`. `NOT IN` with a subquery has the NULL trap from
[chapter 9](09-Self-Semi-and-Anti-Joins.md#anti): prefer `NOT EXISTS`.

`> ALL (subquery)` means "greater than every value in the list", and `> ANY (subquery)` "greater than at least one".
PostgreSQL, MySQL, SQL Server and Oracle have them; **SQLite does not**:

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT name, salary
    FROM employees
    WHERE salary > ALL (SELECT salary FROM employees WHERE department = 'Sales' AND salary IS NOT NULL)
    ORDER BY salary DESC;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | name | salary |
    | --- | --- |
    | Maya Rossi | 180000 |
    | Tom Becker | 140000 |
    | Priya Nair | 120000 |
    | Sam Lee | 120000 |
    <!-- /result -->

=== "Both (MAX instead of ALL)"

    <!-- sql same -->
    ```sql
    SELECT name, salary
    FROM employees
    WHERE salary > (SELECT MAX(salary) FROM employees WHERE department = 'Sales')
    ORDER BY salary DESC;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 4 rows.</p>

    | name | salary |
    | --- | --- |
    | Maya Rossi | 180000 |
    | Tom Becker | 140000 |
    | Priya Nair | 120000 |
    | Sam Lee | 120000 |
    <!-- /result -->

`> ALL` is the same as `> MAX`, and `> ANY` the same as `> MIN`, except when the list is empty or has NULLs. That
is why the PostgreSQL version filters out NULL salaries: `x > ALL (list with a NULL)` is never true, for the same
reason as `NOT IN`. Using MAX and MIN is portable and easier to read.

## 10.3 Correlated subqueries: compared with its own group { #correlated }

"Employees who earn more than the average **of their own department**." The average changes from row to row, so the
subquery has to know which department the outer row is in. It refers to the outer query's alias:

<!-- sql -->
```sql
SELECT e.name, e.department, e.salary
FROM employees e
WHERE e.salary > (
  SELECT AVG(x.salary)
  FROM employees x
  WHERE x.department = e.department
)
ORDER BY e.department, e.salary DESC, e.name;
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

This is a **correlated** subquery: `e.department` comes from outside. Think of it as run once for each outer row
(the database may find a faster plan, but the answer is the same). Management has one person, who can't be above
her own average, so the department doesn't appear.

The same question with a derived table, worked out once per department instead of once per person:

<!-- sql same -->
```sql
SELECT e.name, e.department, e.salary
FROM employees e
JOIN (
  SELECT department, AVG(salary) AS avg_salary
  FROM employees
  GROUP BY department
) d ON d.department = e.department
WHERE e.salary > d.avg_salary
ORDER BY e.department, e.salary DESC, e.name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 5 rows.</p>

| name | department | salary |
| --- | --- | --- |
| Tom Becker | Engineering | 140000 |
| Priya Nair | Engineering | 120000 |
| Sam Lee | Engineering | 120000 |
| Omar Aziz | Sales | 110000 |
| Kwame Mensah | Support | 75000 |
<!-- /result -->

And a third way, with a window function, is in [chapter 13](13-Window-Functions-Ranking.md#aggregate-windows). In a
test, any of the three is right; pick the one you can write without mistakes.

## 10.4 Subqueries in FROM: derived tables { #derived }

A subquery in FROM is a temporary table that exists for this query only, often called a **derived table**. Use it
to aggregate in two steps: first one row per order, then statistics over the orders.

<!-- sql -->
```sql
SELECT COUNT(*)              AS orders,
       ROUND(AVG(total), 2)  AS avg_order_value,
       MAX(total)            AS biggest_order
FROM (
  SELECT order_id, SUM(quantity * unit_price) AS total
  FROM order_items
  GROUP BY order_id
) AS t;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| orders | avg_order_value | biggest_order |
| --- | --- | --- |
| 20 | 56.13 | 181.00 |
<!-- /result -->

An aggregate of an aggregate (`AVG(SUM(...))`) is not allowed in one step; the derived table makes the step
explicit.

**The name.** `AS t` gives the derived table a name. MySQL and SQL Server refuse a derived table without one, and so
did PostgreSQL before version 16; SQLite and PostgreSQL 16 accept it unnamed. Always name it; it costs two
characters.

## 10.5 When "one value" is not one value { #too-many-rows }

A scalar subquery must return at most one row. If it returns more, PostgreSQL stops with an error. SQLite quietly
uses the first row it finds:

<!-- sql pgerror random -->
```sql
SELECT name, price
FROM products
WHERE price = (SELECT price FROM products WHERE category = 'Kitchen');
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>more than one row returned by a subquery used as an expression</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 1 row.</p>
<!-- /result -->

SQLite's answer depends on which Kitchen product it happens to read first. Reading the table in its stored
order it returned the coffee mug; told to read the same table backwards, it returned the tea kettle and the monitor
stand instead. Same query, same data, different answer, and no warning. If
a subquery might return several rows, decide what you mean: `IN (...)` for "any of them", `MAX(...)` or `MIN(...)`
for one of them. And a scalar subquery that returns **no** rows gives NULL, which then compares as unknown:

<!-- sql -->
```sql
SELECT name
FROM products
WHERE price > (SELECT price FROM products WHERE category = 'Garden');
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

| name |
| --- |
| *(no rows)* |
<!-- /result -->

There is no Garden category, so the subquery is NULL, every comparison is unknown, and no rows come back. No error.

## 10.6 Subquery, join or CTE? { #which }

| Question | Natural fit |
| --- | --- |
| Compare with one overall number (the average, the maximum) | Scalar subquery |
| "Has at least one" / "has none" | `EXISTS` / `NOT EXISTS` |
| Compare with a per-group number | Join to a grouped derived table, or a window function |
| Several steps, each building on the last | CTEs ([chapter 11](11-CTEs-and-Recursive-CTEs.md)) |
| Columns from both tables in the output | Join |

A subquery nested three deep is hard to read and hard to check. In a test, the moment you reach a second level of
nesting, switch to CTEs: the same logic, written top to bottom.

## 10.7 Summary { #summary }

- A scalar subquery returns one value and can go wherever a value can.
- `IN (subquery)` tests membership; `NOT IN` breaks on NULLs, so prefer `NOT EXISTS`.
- `ANY` / `ALL` exist in PostgreSQL but not SQLite; `MAX` and `MIN` say the same thing portably.
- A correlated subquery refers to the outer row and is (logically) run per row.
- A subquery in FROM is a derived table; give it a name.
- More than one row from a scalar subquery: an error in PostgreSQL, a silent guess in SQLite. No rows: NULL.

## Practice { #practice }

**10.1** The most recent order: its id, date and customer id. Use a subquery, not ORDER BY ... LIMIT.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT order_id, order_date, customer_id
    FROM orders
    WHERE order_date = (SELECT MAX(order_date) FROM orders);
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | order_id | order_date | customer_id |
    | --- | --- | --- |
    | 120 | 2026-04-05 | 1 |
    <!-- /result -->

    Unlike `ORDER BY order_date DESC LIMIT 1`, this returns every order on the latest day if there are several.
    Ask which the task wants.

**10.2** Customers whose first order was in February 2026.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT c.customer_id, c.name
    FROM customers c
    WHERE (SELECT MIN(o.order_date) FROM orders o WHERE o.customer_id = c.customer_id)
          BETWEEN '2026-02-01' AND '2026-02-28'
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_id | name |
    | --- | --- |
    | 5 | Eli Cohen |
    | 6 | Farah Haddad |
    | 7 | Gus Novak |
    <!-- /result -->

    A correlated scalar subquery finds each customer's first order date. Ivan has no orders: the subquery gives
    NULL and the BETWEEN is unknown, so he is left out. (`BETWEEN` includes both ends; with dates that carry a time
    of day, use `>= '2026-02-01' AND < '2026-03-01'` instead.)

**10.3** Products whose price is above the average price of their own category.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT p.name, p.category, p.price
    FROM products p
    WHERE p.price > (SELECT AVG(x.price) FROM products x WHERE x.category = p.category)
    ORDER BY p.category, p.price DESC, p.name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | name | category | price |
    | --- | --- | --- |
    | Desk lamp | Home | 24.50 |
    | Wall clock | Home | 24.50 |
    | Tea kettle | Kitchen | 32.00 |
    | Office chair | Office | 149.00 |
    <!-- /result -->

    The gift card has a NULL category: `x.category = NULL` matches nothing, the average is NULL, and the gift card
    is left out. That is usually right, but say so.

**10.4** The average number of items (lines) per order, and the largest number, using a derived table.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT ROUND(AVG(lines * 1.0), 2) AS avg_lines, MAX(lines) AS max_lines
    FROM (
      SELECT order_id, COUNT(*) AS lines
      FROM order_items
      GROUP BY order_id
    ) AS per_order;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | avg_lines | max_lines |
    | --- | --- |
    | 1.50 | 3 |
    <!-- /result -->

    `AVG` of whole numbers already gives a decimal on both databases; `* 1.0` just makes the intent obvious.

**10.5** For each customer with orders: the number of orders, and that number as a percentage of all orders that
have a customer. One decimal.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id,
           COUNT(*) AS orders,
           ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM orders WHERE customer_id IS NOT NULL), 1) AS pct
    FROM orders
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
    ORDER BY orders DESC, customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | customer_id | orders | pct |
    | --- | --- | --- |
    | 1 | 5 | 26.3 |
    | 2 | 3 | 15.8 |
    | 3 | 2 | 10.5 |
    | 4 | 2 | 10.5 |
    | 5 | 2 | 10.5 |
    | 6 | 2 | 10.5 |
    | 7 | 1 | 5.3 |
    | 8 | 1 | 5.3 |
    | 10 | 1 | 5.3 |
    <!-- /result -->

**10.6** The department with the highest total payroll. Show it with its payroll; if two departments tie, show both.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT department, SUM(salary) AS payroll
    FROM employees
    GROUP BY department
    HAVING SUM(salary) = (
      SELECT MAX(total)
      FROM (SELECT SUM(salary) AS total FROM employees GROUP BY department) AS t
    );
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | department | payroll |
    | --- | --- |
    | Engineering | 475000 |
    <!-- /result -->

    A subquery in HAVING compares each group with the best group. The inner derived table makes one total per
    department, and MAX picks the largest. Ties are kept, which `ORDER BY payroll DESC LIMIT 1` would not do.

**10.7** What does this return on PostgreSQL, and on SQLite? `SELECT (SELECT name FROM customers WHERE city =
'Toronto') AS who;`

??? success "Answer"
    <!-- sql pgerror random -->
    ```sql
    SELECT (SELECT name FROM customers WHERE city = 'Toronto') AS who;
    ```

    <!-- result -->
    <p class="sql-tested sql-error">PostgreSQL 16: error: <code>more than one row returned by a subquery used as an expression</code></p>
    <p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 1 row.</p>
    <!-- /result -->

    Three customers live in Toronto. PostgreSQL refuses: a scalar subquery returned more than one row. SQLite
    returns one name, the first one it reads, with no warning.

**Next:** [11. CTEs and recursive CTEs](11-CTEs-and-Recursive-CTEs.md).
