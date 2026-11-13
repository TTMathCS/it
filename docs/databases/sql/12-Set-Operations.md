# 12. UNION, INTERSECT, EXCEPT

*Joins put tables side by side; set operations stack results on top of each other. UNION puts two lists together,
INTERSECT keeps what is in both, EXCEPT keeps what is in the first and not the second. They are short to write and
they answer "compare these two lists" questions in one line. The one rule to remember: UNION removes duplicates and
UNION ALL does not, and the difference is both a correctness and a speed question.*

!!! abstract "In this chapter"
    **You will learn:**

    - `UNION` and `UNION ALL`, and when each is right
    - `INTERSECT` and `EXCEPT` for "in both" and "in one but not the other"
    - the rules: same number of columns, compatible types, names from the first query, one ORDER BY at the end
    - how set operations treat NULL (unlike `=`, they treat two NULLs as the same)
    - turning columns into rows with UNION ALL

    **You need:** [2. SELECT and WHERE](02-Select-Where-Order-By-Limit.md) and [9. self, semi and anti joins](09-Self-Semi-and-Anti-Joins.md).

## 12.1 UNION and UNION ALL { #union }

`UNION ALL` puts the rows of the second query under the rows of the first. Canadian customers with their city and
Support staff with their department, in one labelled list:

**Task:** In one list, show the Canadian customers with their city and the Support staff with their department, labelled 'customer' or 'employee', by label then name.

<!-- sql -->
```sql
SELECT 'customer' AS who, name, city AS place FROM customers WHERE country = 'Canada'
UNION ALL
SELECT 'employee', name, department FROM employees WHERE department = 'Support'
ORDER BY who, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

| who | name | place |
| --- | --- | --- |
| customer | Ana Silva | Toronto |
| customer | Farah Haddad | Toronto |
| customer | Ivan Petrov | Toronto |
| employee | Ella Novak | Support |
| employee | Kwame Mensah | Support |
| employee | Leo Park | Support |
<!-- /result -->

The rules:

- Both queries return the **same number of columns**, and each pair of columns has a compatible type.
- The **column names come from the first query**; the second's names are ignored.
- **One ORDER BY**, at the very end, sorts the combined result. It can only name output columns.

`UNION` (without ALL) also **removes duplicate rows** from the combined result. The cities where customers live, from
two halves of the table:

**Task:** List the different cities of customers 1 to 5 and 6 to 10 together, each once, missing city last.

<!-- sql -->
```sql
SELECT city FROM customers WHERE customer_id <= 5
UNION
SELECT city FROM customers WHERE customer_id > 5
ORDER BY city NULLS LAST;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 8 rows.</p>

| city |
| --- |
| Lagos |
| Lisbon |
| Osaka |
| Prague |
| Seoul |
| Shanghai |
| Toronto |
| *NULL* |
<!-- /result -->

**Task:** The same, but keep every row, duplicates included.

<!-- sql -->
```sql
SELECT city FROM customers WHERE customer_id <= 5
UNION ALL
SELECT city FROM customers WHERE customer_id > 5
ORDER BY city NULLS LAST;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

| city |
| --- |
| Lagos |
| Lisbon |
| Osaka |
| Prague |
| Seoul |
| Shanghai |
| Toronto |
| Toronto |
| Toronto |
| *NULL* |
<!-- /result -->

UNION gave 8 rows, UNION ALL 10: Toronto three times became once. UNION removes duplicates **within** each half
too, not just between them. For set operations two NULLs count as the same, so two unknown cities would also have
become one row.

`NULLS LAST` is there because the two databases put NULL at different ends: in ascending order PostgreSQL sorts NULL after
every value and SQLite before (DESC flips both). Saying where you want it makes the result the same on both (SQLite has understood `NULLS FIRST` and
`NULLS LAST` since version 3.30; MySQL and SQL Server do not have them, chapter 6).

!!! tip "Interview tip: UNION ALL unless you need UNION"
    Removing duplicates means sorting or hashing the whole result, which costs time on big tables. If the two parts
    can't overlap (different years, different labels), or if duplicates are real and should be counted, use
    `UNION ALL`. Use `UNION` only when you want duplicates gone, and say so. A common wrong answer is counting
    events from two tables with `UNION`: two identical events (same customer, same day) collapse into one.

## 12.2 INTERSECT: in both { #intersect }

Customers who both ordered (any status) and logged in:

**Task:** List the customers who both ordered (any status) and logged in: customer id, in order.

<!-- sql -->
```sql
SELECT customer_id FROM orders WHERE customer_id IS NOT NULL
INTERSECT
SELECT customer_id FROM logins
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| customer_id |
| --- |
| 1 |
| 2 |
| 4 |
| 6 |
<!-- /result -->

INTERSECT removes duplicates too, so each customer appears once. The same as a semi join with EXISTS (chapter 9),
written as a set operation.

## 12.3 EXCEPT: in the first, not in the second { #except }

Customers who never ordered:

**Task:** List the customers who never ordered: customer id, in order.

<!-- sql -->
```sql
SELECT customer_id FROM customers
EXCEPT
SELECT customer_id FROM orders
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| customer_id |
| --- |
| 9 |
<!-- /result -->

Unlike `NOT IN`, this works despite the NULL in `orders.customer_id`: EXCEPT compares rows with "is the same as",
under which NULL matches NULL, not with `=`. It is an anti join that can't fall into the NULL trap. Oracle called it
`MINUS` until version 21c, which added `EXCEPT`; MySQL has had both INTERSECT and EXCEPT only since 8.0.31 (2022).

**Comparing two versions of a table** is the most common real use. Suppose a staging copy of `products` arrived with
one price changed, one product missing and one new product. EXCEPT in both directions shows every difference:

**Task:** Compare a staging copy of products with the real table and list every difference, saying which side each row is only on.

<!-- sql -->
```sql
WITH staging AS (
  SELECT product_id, name, category, price FROM products WHERE product_id <> 11
  UNION ALL
  SELECT 99, 'Desk mat', 'Office', 15.00
),
fixed_staging AS (
  SELECT product_id, name, category,
         CASE WHEN product_id = 4 THEN 9.25 ELSE price END AS price
  FROM staging
)
SELECT 'only in products' AS side, product_id, name, price FROM (
  SELECT product_id, name, price FROM products
  EXCEPT
  SELECT product_id, name, price FROM fixed_staging
) AS a
UNION ALL
SELECT 'only in staging', product_id, name, price FROM (
  SELECT product_id, name, price FROM fixed_staging
  EXCEPT
  SELECT product_id, name, price FROM products
) AS b
ORDER BY product_id, side;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| side | product_id | name | price |
| --- | --- | --- | --- |
| only in products | 4 | Coffee mug | 8.75 |
| only in staging | 4 | Coffee mug | 9.25 |
| only in products | 11 | Bookend | 9.50 |
| only in staging | 99 | Desk mat | 15.00 |
<!-- /result -->

The changed coffee mug shows on both sides (old price and new); the bookend is only in the real table; the desk mat
only in staging. [Chapter 23](23-Data-Quality-Checks.md) builds data-quality checks on this.

## 12.4 Columns into rows { #unpivot }

UNION ALL turns several columns into rows ("unpivot"). Each customer's email and city as separate "fact" rows:

**Task:** For the first 3 customers, show the email and the city as separate rows: customer id, field name and value, by customer then field.

<!-- sql -->
```sql
SELECT customer_id, 'email' AS field, email AS value FROM customers WHERE customer_id <= 3
UNION ALL
SELECT customer_id, 'city', city FROM customers WHERE customer_id <= 3
ORDER BY customer_id, field;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

| customer_id | field | value |
| --- | --- | --- |
| 1 | city | Toronto |
| 1 | email | ana@example.com |
| 2 | city | Lagos |
| 2 | email | ben@example.com |
| 3 | city | Shanghai |
| 3 | email | *NULL* |
<!-- /result -->

The reverse, rows into columns ("pivot"), is done with CASE inside aggregates: [chapter 15](15-Classic-Interview-Patterns.md#pivot).

## 12.5 Summary { #summary }

| Operation | Keeps | Duplicates |
| --- | --- | --- |
| `UNION ALL` | every row of both | kept |
| `UNION` | every different row of both | removed |
| `INTERSECT` | rows in both | removed |
| `EXCEPT` | rows in the first and not the second | removed |

- Same number of columns, compatible types; names from the first query; one ORDER BY at the end.
- Set operations treat NULLs as equal to each other, so EXCEPT is a NULL-safe anti join.
- Prefer UNION ALL when duplicates can't happen or should be kept.

## Practice { #practice }

**12.1** One list of every date on which anything happened (an order or a login), each date once, latest first.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT order_date AS day FROM orders
    UNION
    SELECT login_date FROM logins
    ORDER BY day DESC;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 24 rows.</p>

    | day |
    | --- |
    | 2026-04-05 |
    | 2026-04-02 |
    | 2026-04-01 |
    | 2026-03-25 |
    | 2026-03-22 |
    | 2026-03-18 |
    | 2026-03-10 |
    | 2026-03-09 |
    | 2026-03-08 |
    | 2026-03-06 |
    | 2026-03-05 |
    | 2026-03-04 |
    | 2026-03-03 |
    | 2026-03-02 |
    | 2026-03-01 |
    | 2026-02-21 |
    | 2026-02-20 |
    | 2026-02-14 |
    | 2026-02-10 |
    | 2026-02-02 |
    | 2026-01-28 |
    | 2026-01-20 |
    | 2026-01-15 |
    | 2026-01-03 |
    <!-- /result -->

    UNION, because "each date once". The ORDER BY uses the first query's column name.

**12.2** Count all events (orders and logins) per customer, among customers who have any. An order and a login on
the same day are two events.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id, COUNT(*) AS events
    FROM (
      SELECT customer_id, order_date AS day FROM orders WHERE customer_id IS NOT NULL
      UNION ALL
      SELECT customer_id, login_date FROM logins
    ) AS e
    GROUP BY customer_id
    ORDER BY events DESC, customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | customer_id | events |
    | --- | --- |
    | 1 | 11 |
    | 2 | 7 |
    | 4 | 6 |
    | 6 | 3 |
    | 3 | 2 |
    | 5 | 2 |
    | 7 | 1 |
    | 8 | 1 |
    | 10 | 1 |
    <!-- /result -->

    UNION ALL, because every event counts. With UNION, customer 2's duplicate login on 2 March would collapse into
    one and the counts would be too small.

**12.3** Products that were in a cancelled order but have never been in a shipped one. Use EXCEPT.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT i.product_id FROM order_items i JOIN orders o ON o.order_id = i.order_id WHERE o.status = 'cancelled'
    EXCEPT
    SELECT i.product_id FROM order_items i JOIN orders o ON o.order_id = i.order_id WHERE o.status = 'shipped'
    ORDER BY product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

    | product_id |
    | --- |
    | *(no rows)* |
    <!-- /result -->

    No rows: both products from cancelled orders (the fountain pen and the tea kettle) have also been shipped.

**12.4** What is wrong here? `SELECT name, city FROM customers UNION SELECT name FROM employees;`

??? success "Answer"
    <!-- sql error -->
    ```sql
    SELECT name, city FROM customers UNION SELECT name FROM employees;
    ```

    <!-- result -->
    <p class="sql-tested sql-error">PostgreSQL 16: error: <code>each UNION query must have the same number of columns</code></p>
    <p class="sql-tested sql-error">SQLite 3.53: error: <code>SELECTs to the left and right of UNION do not have the same number of result columns</code></p>
    <!-- /result -->

    The two halves have different numbers of columns. Add a placeholder to the second: `SELECT name, NULL FROM
    employees`.

**Next:** [13. Window functions: ranking](13-Window-Functions-Ranking.md).
