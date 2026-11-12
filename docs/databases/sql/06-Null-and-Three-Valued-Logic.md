# 6. NULL and three-valued logic

*NULL is the most common cause of a wrong answer that looks right. It means "no value", and SQL treats it as
"unknown": a comparison with NULL is neither true nor false, a sum with NULL is NULL, and a `WHERE` quietly drops
the row. This chapter shows every place NULL changes a result, on the shop's own NULLs: two missing emails, a missing
city, a missing salary, a product with no category and an order with no customer.*

!!! abstract "In this chapter"
    **You will learn:**

    - what NULL is and is not (not zero, not empty text)
    - why `= NULL` finds nothing, and `IS NULL`, `IS NOT NULL`, `IS DISTINCT FROM`
    - three-valued logic: TRUE, FALSE and UNKNOWN, and why `NOT` does not bring the NULL rows back
    - NULL in arithmetic, text, aggregates, `GROUP BY`, `DISTINCT` and joins
    - the `NOT IN` trap, in one example
    - where NULLs sort, and `NULLS FIRST` / `NULLS LAST`
    - `COALESCE`, `NULLIF`, and the other databases' names for them

    **You need:** [chapters 2](02-Select-Where-Order-By-Limit.md) and [4](04-Expressions-Case-Numbers-Dates-Cast.md).

## 6.1 What NULL means { #meaning }

NULL marks a value that is missing: not known (Chen Wei's email), not applicable (the top manager's `manager_id`),
or not yet set (Leo Park's salary). It is not a value itself, so it is not 0 and not empty text `''`:

<!-- sql -->
```sql
SELECT customer_id, name, email, city
FROM customers
WHERE customer_id IN (3, 5, 8)
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| customer_id | name | email | city |
| --- | --- | --- | --- |
| 3 | Chen Wei | *NULL* | Shanghai |
| 5 | Eli Cohen | eli@example.com | *NULL* |
| 8 | Hana Sato | *NULL* | Osaka |
<!-- /result -->

An empty string `''` is a real value, a piece of text with no characters; a test checker treats it differently from
NULL. One exception to know: Oracle stores `''` as NULL, so on Oracle the two cannot be told apart.

## 6.2 Comparisons with NULL are unknown { #unknown }

SQL reads NULL as "some value we do not know". Is an unknown value equal to 1? Unknown. Is it equal to another
unknown value? Also unknown. Every comparison with NULL gives NULL, which in a condition means **UNKNOWN**:

<!-- sql -->
```sql
SELECT NULL = 1     AS eq_one,
       NULL = NULL  AS eq_null,
       NULL <> 1    AS not_one,
       NULL > 0     AS gt_zero;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| eq_one | eq_null | not_one | gt_zero |
| --- | --- | --- | --- |
| *NULL* | *NULL* | *NULL* | *NULL* |
<!-- /result -->

`WHERE` keeps a row only when its condition is TRUE. FALSE and UNKNOWN are both dropped. So this finds nothing,
although two customers have no email:

<!-- sql -->
```sql
SELECT customer_id, name
FROM customers
WHERE email = NULL;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

| customer_id | name |
| --- | --- |
| *(no rows)* | |
<!-- /result -->

## 6.3 IS NULL and IS DISTINCT FROM { #is-null }

`IS NULL` and `IS NOT NULL` are the only tests that ask "is it missing?", and they are always TRUE or FALSE:

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

Comparing two columns that may both be NULL needs a **null-safe** comparison, where two NULLs count as the same.
`a IS NOT DISTINCT FROM b` is the standard form, and works on PostgreSQL and on SQLite (from 3.39):

<!-- sql -->
```sql
SELECT NULL IS NOT DISTINCT FROM NULL AS both_null,
       NULL IS DISTINCT FROM 1        AS null_vs_one,
       2    IS DISTINCT FROM 2        AS two_vs_two;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| both_null | null_vs_one | two_vs_two |
| --- | --- | --- |
| true | true | false |
<!-- /result -->

This matters when loading data: to find rows whose `city` changed, `old.city <> new.city` misses a change from
NULL to 'Toronto' (the comparison is UNKNOWN), while `old.city IS DISTINCT FROM new.city` catches it
([chapter 22](22-Duplicates-and-Incremental-Loads.md)). SQLite also accepts the short forms `a IS b` and
`a IS NOT b`; MySQL writes `a <=> b`.

## 6.4 Three-valued logic { #three-valued }

With UNKNOWN in play, `AND`, `OR` and `NOT` follow these tables (U is UNKNOWN):

| `AND` | TRUE | FALSE | U |
| --- | --- | --- | --- |
| **TRUE** | TRUE | FALSE | U |
| **FALSE** | FALSE | FALSE | FALSE |
| **U** | U | FALSE | U |

| `OR` | TRUE | FALSE | U |
| --- | --- | --- | --- |
| **TRUE** | TRUE | TRUE | TRUE |
| **FALSE** | TRUE | FALSE | U |
| **U** | TRUE | U | U |

`NOT TRUE` is FALSE, `NOT FALSE` is TRUE, and **`NOT UNKNOWN` is UNKNOWN**. The tables follow common sense: FALSE
`AND` anything is FALSE whatever the unknown is, TRUE `OR` anything is TRUE, and every other combination that involves UNKNOWN stays UNKNOWN.

The last rule is the trap. You might expect "not in Toronto" to return every customer that "in Toronto" did not:

!!! failure "The usual wrong answer: customers not in Toronto"
    <!-- sql -->
    ```sql
    SELECT customer_id, name, city
    FROM customers
    WHERE NOT (city = 'Toronto')
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

    | customer_id | name | city |
    | --- | --- | --- |
    | 2 | Ben Okafor | Lagos |
    | 3 | Chen Wei | Shanghai |
    | 4 | Dana Kim | Seoul |
    | 7 | Gus Novak | Prague |
    | 8 | Hana Sato | Osaka |
    | 10 | Ana Silva | Lisbon |
    <!-- /result -->

    Ten customers, three in Toronto, but only six rows: Eli Cohen (5) is missing. His city is NULL, so
    `city = 'Toronto'` is UNKNOWN, `NOT` leaves it UNKNOWN, and `WHERE` drops him. `city <> 'Toronto'` does the same.

If customers with no city belong in the answer, say so:

<!-- sql -->
```sql
SELECT customer_id, name, city
FROM customers
WHERE city <> 'Toronto' OR city IS NULL
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 7 rows.</p>

| customer_id | name | city |
| --- | --- | --- |
| 2 | Ben Okafor | Lagos |
| 3 | Chen Wei | Shanghai |
| 4 | Dana Kim | Seoul |
| 5 | Eli Cohen | *NULL* |
| 7 | Gus Novak | Prague |
| 8 | Hana Sato | Osaka |
| 10 | Ana Silva | Lisbon |
<!-- /result -->

`WHERE city IS DISTINCT FROM 'Toronto'` is the same in one condition. Which answer is right depends on the
question; a test usually has a NULL in the data exactly to see whether you thought about it. Say which you chose.

`CHECK` constraints use the opposite rule from `WHERE`: a row is refused only when the check is FALSE, so a NULL
passes a `CHECK (salary > 0)`. Add `NOT NULL` if missing values are not allowed ([chapter 18](18-Create-Table-Types-Constraints.md)).

## 6.5 NULL in arithmetic and text { #arithmetic }

Any arithmetic with NULL gives NULL, and so does `||`:

<!-- sql -->
```sql
SELECT name, salary,
       salary + 5000          AS after_raise,
       name || ': ' || salary AS label
FROM employees
WHERE employee_id IN (11, 12)
ORDER BY employee_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| name | salary | after_raise | label |
| --- | --- | --- | --- |
| Ella Novak | 52000 | 57000 | Ella Novak: 52000 |
| Leo Park | *NULL* | *NULL* | *NULL* |
<!-- /result -->

`COALESCE(x, default)` replaces NULL with a value: `COALESCE(salary, 0) + 5000`. Use it on purpose: turning an
unknown salary into 0 changes averages and totals, and that may or may not be what the question means.

## 6.6 NULL in aggregates { #aggregates }

Aggregate functions **skip** NULLs, except `COUNT(*)`, which counts rows:

<!-- sql -->
```sql
SELECT COUNT(*)      AS employees,
       COUNT(salary) AS with_salary,
       SUM(salary)   AS payroll,
       AVG(salary)   AS avg_known,
       MIN(salary)   AS lowest
FROM employees
WHERE department = 'Support';
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| employees | with_salary | payroll | avg_known | lowest |
| --- | --- | --- | --- | --- |
| 3 | 2 | 127000 | 63500.000000000000 | 52000 |
<!-- /result -->

Three people, two known salaries. `AVG` is the average of the two known ones (63,500), not the total over three.
[Chapter 7](07-Aggregation-Group-By-Having.md#division) shows the other average, counting a missing salary as 0.

When there are no values at all, `COUNT` gives 0 but `SUM`, `AVG`, `MIN` and `MAX` give **NULL**, not 0:

<!-- sql -->
```sql
SELECT COUNT(*)               AS n,
       SUM(price)             AS total,
       COALESCE(SUM(price), 0) AS total_or_zero
FROM products
WHERE price > 1000;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| n | total | total_or_zero |
| --- | --- | --- |
| 0 | *NULL* | 0 |
<!-- /result -->

A question that asks for "total sales, 0 if none" needs the `COALESCE`.

## 6.7 NULL in GROUP BY and DISTINCT { #group-by }

`GROUP BY` and `DISTINCT` treat all NULLs as one group, even though `NULL = NULL` is not true:

<!-- sql -->
```sql
SELECT category, COUNT(*) AS products
FROM products
GROUP BY category
ORDER BY category NULLS LAST;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| category | products |
| --- | --- |
| Home | 4 |
| Kitchen | 2 |
| Office | 4 |
| *NULL* | 1 |
<!-- /result -->

The gift card has no category and forms a group of its own. If a test asks for "products per category", decide
whether that NULL group belongs in the answer; often it should be shown with a label:
`COALESCE(category, 'Uncategorised')`. (`NULLS LAST` is explained in [section 6.9](#sorting).)

## 6.8 NULL in joins and NOT IN { #joins-not-in }

A join condition is a comparison, so NULL never matches anything, not even another NULL. Order 108 has no customer,
so an inner join to `customers` drops it; a left join keeps it with NULLs ([chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md)).

The same rule breaks `NOT IN` when the list contains a NULL. "Customers who never placed an order" looks like this:

!!! failure "The usual wrong answer: NOT IN with a NULL in the list"
    <!-- sql -->
    ```sql
    SELECT customer_id, name
    FROM customers
    WHERE customer_id NOT IN (SELECT customer_id FROM orders);
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

    | customer_id | name |
    | --- | --- |
    | *(no rows)* | |
    <!-- /result -->

    Ivan Petrov (9) never ordered, yet nothing comes back. The list contains the NULL from order 108, and
    `9 NOT IN (1, 2, ..., NULL)` means `9 <> 1 AND 9 <> 2 AND ... AND 9 <> NULL`. The last part is UNKNOWN. For a customer who
    ordered, another part is FALSE, so the whole condition is FALSE; for Ivan every other part is TRUE, so it is
    UNKNOWN. Neither is TRUE, so no row comes back.

Use `NOT EXISTS`, which does not have the problem, or filter the NULLs out of the list:

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

[Chapter 9](09-Self-Semi-and-Anti-Joins.md#anti) compares all the ways to write an anti join. `IN` (without `NOT`) is
safe: a NULL in the list just never matches.

## 6.9 Where NULLs sort { #sorting }

The SQL standard leaves it to each database whether NULLs sort first or last, and they disagree. PostgreSQL and
Oracle treat NULL as larger than every value (last in ascending order); SQLite, MySQL and SQL Server treat it as
smaller (first):

<!-- sql pg -->
```sql
SELECT customer_id, city
FROM customers
WHERE customer_id BETWEEN 3 AND 6
ORDER BY city;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

| customer_id | city |
| --- | --- |
| 4 | Seoul |
| 3 | Shanghai |
| 6 | Toronto |
| 5 | *NULL* |
<!-- /result -->

<!-- sql sqlite -->
```sql
SELECT customer_id, city
FROM customers
WHERE customer_id BETWEEN 3 AND 6
ORDER BY city;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 4 rows.</p>

| customer_id | city |
| --- | --- |
| 5 | *NULL* |
| 4 | Seoul |
| 3 | Shanghai |
| 6 | Toronto |
<!-- /result -->

`NULLS FIRST` or `NULLS LAST` after a sort column decides it, on PostgreSQL, Oracle and SQLite (from 3.30):

<!-- sql -->
```sql
SELECT customer_id, city
FROM customers
WHERE customer_id BETWEEN 3 AND 6
ORDER BY city NULLS LAST;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| customer_id | city |
| --- | --- |
| 4 | Seoul |
| 3 | Shanghai |
| 6 | Toronto |
| 5 | *NULL* |
<!-- /result -->

MySQL and SQL Server do not have `NULLS LAST`; there, sort by a flag first: `ORDER BY CASE WHEN city IS NULL THEN 1
ELSE 0 END, city`, which works everywhere.

!!! tip "Interview tip"
    Descending order flips it: on PostgreSQL, `ORDER BY salary DESC` puts Leo Park's NULL salary **first**, so a
    "highest salary" query with `LIMIT 1` returns NULL. Filter `WHERE salary IS NOT NULL` or write
    `ORDER BY salary DESC NULLS LAST`. The same happens inside window functions ([chapter 13](13-Window-Functions-Ranking.md)).

## 6.10 Unique keys and NULL { #unique }

A `UNIQUE` constraint lets many rows hold NULL in PostgreSQL, SQLite, MySQL and Oracle, because two NULLs are not
"equal". SQL Server allows only one NULL. PostgreSQL 15 added `UNIQUE NULLS NOT DISTINCT` to allow just one. A
primary key can never be NULL at all. [Chapter 18](18-Create-Table-Types-Constraints.md) covers constraints.

## 6.11 The NULL functions { #functions }

| Purpose | Standard (PostgreSQL, SQLite) | Other names |
| --- | --- | --- |
| first value that is not NULL | `COALESCE(a, b, ...)` | `IFNULL(a, b)` (SQLite, MySQL), `ISNULL(a, b)` (SQL Server), `NVL(a, b)` (Oracle) |
| NULL when two values are equal | `NULLIF(a, b)` | the same everywhere |
| null-safe equal | `a IS NOT DISTINCT FROM b` | `a IS b` (SQLite), `a <=> b` (MySQL) |

`COALESCE` takes any number of arguments and is in every database; prefer it.

## 6.12 Summary { #summary }

- NULL is "no value": not 0, not `''`. Every comparison with it is UNKNOWN, and `WHERE` keeps only TRUE.
- Test with `IS NULL` / `IS NOT NULL`; compare null-safely with `IS DISTINCT FROM`.
- `NOT` does not turn UNKNOWN into TRUE: "not in Toronto" leaves out customers with no city.
- Arithmetic and `||` with NULL give NULL. `COALESCE` gives a default, on purpose.
- Aggregates skip NULLs (except `COUNT(*)`); `SUM` of nothing is NULL.
- `GROUP BY` and `DISTINCT` put all NULLs in one group.
- NULL never matches in a join. `NOT IN` with a NULL in the list returns nothing: use `NOT EXISTS`.
- In ascending order, NULLs sort last on PostgreSQL and first on SQLite; say `NULLS FIRST` or `NULLS LAST`.

## Practice { #practice }

**6.1** Employees who are not in the Sales department and whose salary is not 70,000. Return `name`, `department`,
`salary`, by `employee_id`. Should Leo Park be in the answer? Write it both ways.

??? success "Answer"
    Read literally, Leo Park's salary is unknown, so we cannot say it is "not 70,000". A plain condition leaves him
    out:

    <!-- sql -->
    ```sql
    SELECT name, department, salary
    FROM employees
    WHERE department <> 'Sales' AND salary <> 70000
    ORDER BY employee_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 7 rows.</p>

    | name | department | salary |
    | --- | --- | --- |
    | Maya Rossi | Management | 180000 |
    | Tom Becker | Engineering | 140000 |
    | Priya Nair | Engineering | 120000 |
    | Sam Lee | Engineering | 120000 |
    | Lucia Gomez | Engineering | 95000 |
    | Kwame Mensah | Support | 75000 |
    | Ella Novak | Support | 52000 |
    <!-- /result -->

    If "not 70,000" should include "unknown", use the null-safe form:

    <!-- sql -->
    ```sql
    SELECT name, department, salary
    FROM employees
    WHERE department <> 'Sales' AND salary IS DISTINCT FROM 70000
    ORDER BY employee_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 8 rows.</p>

    | name | department | salary |
    | --- | --- | --- |
    | Maya Rossi | Management | 180000 |
    | Tom Becker | Engineering | 140000 |
    | Priya Nair | Engineering | 120000 |
    | Sam Lee | Engineering | 120000 |
    | Lucia Gomez | Engineering | 95000 |
    | Kwame Mensah | Support | 75000 |
    | Ella Novak | Support | 52000 |
    | Leo Park | Support | *NULL* |
    <!-- /result -->

**6.2** For each customer: `customer_id`, `name`, and `contact`, which is the email, or the text `city: ` followed by
the city when there is no email, or `none` when both are missing. By `customer_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id, name,
           COALESCE(email, 'city: ' || city, 'none') AS contact
    FROM customers
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

    | customer_id | name | contact |
    | --- | --- | --- |
    | 1 | Ana Silva | ana@example.com |
    | 2 | Ben Okafor | ben@example.com |
    | 3 | Chen Wei | city: Shanghai |
    | 4 | Dana Kim | dana@example.com |
    | 5 | Eli Cohen | eli@example.com |
    | 6 | Farah Haddad | farah@example.com |
    | 7 | Gus Novak | gus@example.com |
    | 8 | Hana Sato | city: Osaka |
    | 9 | Ivan Petrov | ivan@example.com |
    | 10 | Ana Silva | ana.silva@example.com |
    <!-- /result -->

    `'city: ' || city` is NULL when the city is NULL, so `COALESCE` moves on to `'none'`. Here every customer without
    an email has a city, so `none` does not appear; the expression still handles it.

**6.3** What do these return? `SELECT COUNT(*), COUNT(email), COUNT(DISTINCT city) FROM customers`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT COUNT(*) AS all_rows, COUNT(email) AS with_email, COUNT(DISTINCT city) AS cities
    FROM customers;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | all_rows | with_email | cities |
    | --- | --- | --- |
    | 10 | 8 | 7 |
    <!-- /result -->

    Ten rows; eight emails (two are NULL); seven different cities: Toronto counts once, and the NULL city is not
    counted by `COUNT(DISTINCT ...)`.

**6.4** The product categories with their number of products, with the missing category shown as `Uncategorised`, by
category name.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT COALESCE(category, 'Uncategorised') AS category, COUNT(*) AS products
    FROM products
    GROUP BY COALESCE(category, 'Uncategorised')
    ORDER BY category;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | category | products |
    | --- | --- |
    | Home | 4 |
    | Kitchen | 2 |
    | Office | 4 |
    | Uncategorised | 1 |
    <!-- /result -->

    Grouping by the `COALESCE` expression (not by `category`) makes sure the label and the group agree. If a real
    category were called "Uncategorised", the two groups would merge, so pick a label that cannot clash.

**6.5** This query should list products that were never sold. It returns the right rows today. Why is it fragile,
and what is the safe version?

```sql
SELECT name FROM products
WHERE product_id NOT IN (SELECT product_id FROM order_items);
```

??? success "Answer"
    `order_items.product_id` is `NOT NULL`, so the list has no NULLs and `NOT IN` works. If the column ever allowed
    NULLs (or the subquery were changed to a column that does), one NULL would make the query return nothing at all.
    `NOT EXISTS` is correct either way:

    <!-- sql -->
    ```sql
    SELECT p.name
    FROM products p
    WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.product_id = p.product_id)
    ORDER BY p.name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | name |
    | --- |
    | Bookend |
    <!-- /result -->

**6.6** The highest salary in the Support department and who earns it, written so that it gives the same answer on
PostgreSQL and SQLite. Return `name`, `salary`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, salary
    FROM employees
    WHERE department = 'Support'
    ORDER BY salary DESC NULLS LAST, name
    LIMIT 1;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | name | salary |
    | --- | --- |
    | Kwame Mensah | 75000 |
    <!-- /result -->

    Without `NULLS LAST`, PostgreSQL would put Leo Park's NULL first and return him with an empty salary; SQLite
    already puts NULL last in descending order. `WHERE salary IS NOT NULL` instead of `NULLS LAST` works too.

**Next:** Part II starts with [7. Aggregation: GROUP BY and HAVING](07-Aggregation-Group-By-Having.md).
