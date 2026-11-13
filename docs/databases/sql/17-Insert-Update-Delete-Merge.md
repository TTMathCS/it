# 17. INSERT, UPDATE, DELETE, MERGE

*Reading data is half the job; a data engineer also loads it, corrects it and removes it. This chapter covers the
four statements that change rows, the `RETURNING` clause that shows what changed, and the upsert: "insert this row,
or update it if it is already there". Upserts are where PostgreSQL and SQLite differ most, so every form here was run
on both, and the page says plainly which database supports which.*

!!! abstract "In this chapter"
    **You will learn:**

    - `INSERT` with a column list, several rows at once, and from a `SELECT`
    - `UPDATE` with a condition, with a subquery, and with `UPDATE ... FROM`
    - `DELETE`, `DELETE ... USING` and `TRUNCATE`
    - `RETURNING`: see the rows you changed
    - upserts with `INSERT ... ON CONFLICT`, on both databases
    - `MERGE` on PostgreSQL, and what to write on SQLite instead
    - SQLite's `INSERT OR REPLACE`, and the columns it quietly wipes
    - the habits that stop a bad `UPDATE` from reaching every row

    **You need:** chapters 1 to 11, from [1. tables and keys](01-Tables-Rows-and-Keys.md) to [11. CTEs](11-CTEs-and-Recursive-CTEs.md). Every example below runs inside a transaction that is rolled back afterwards, so
    the shop is unchanged for the next one; most end with a `SELECT` that shows the rows afterwards.

**Which database supports what** (all run for this page, PostgreSQL 16 and SQLite 3.53):

| Statement | PostgreSQL 16 | SQLite 3.53 |
| --- | --- | --- |
| `INSERT ... VALUES (...), (...)`, `INSERT ... SELECT` | yes | yes |
| `UPDATE ... FROM` | yes | yes (from 3.33) |
| `DELETE ... USING` | yes | no: use `WHERE ... IN` / `EXISTS` |
| `TRUNCATE` | yes | no: use `DELETE FROM t` |
| `RETURNING` | yes | yes (from 3.35) |
| `INSERT ... ON CONFLICT ... DO UPDATE / DO NOTHING` | yes | yes (from 3.24) |
| `MERGE` | yes (from 15) | no |
| `INSERT OR REPLACE`, `REPLACE INTO` | no | yes |

## 17.1 INSERT { #insert }

Name the columns, then give the values in the same order. Several rows can go in one statement:

**Task:** Add two products, 12 Desk organiser (Office, 14.50) and 13 Teapot (Kitchen, 27.00), then list products 11 and up.

<!-- sql -->
```sql
INSERT INTO products (product_id, name, category, price)
VALUES (12, 'Desk organiser', 'Office', 14.50),
       (13, 'Teapot',         'Kitchen', 27.00);
SELECT product_id, name, category, price
FROM products
WHERE product_id >= 11
ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| product_id | name | category | price |
| --- | --- | --- | --- |
| 11 | Bookend | Home | 9.50 |
| 12 | Desk organiser | Office | 14.50 |
| 13 | Teapot | Kitchen | 27.00 |
<!-- /result -->

`INSERT INTO products VALUES (...)` without the column list also works, but it depends on the table's column order,
and it breaks the day someone adds a column. Columns you leave out get their default, or NULL.

`INSERT ... SELECT` copies the result of a query into a table, the everyday way to fill one table from another:

**Task:** Make a `cancelled_orders` table and copy the cancelled orders into it, then list it by order id.

<!-- sql -->
```sql
CREATE TABLE cancelled_orders (
  order_id    INTEGER PRIMARY KEY,
  customer_id INTEGER,
  order_date  DATE NOT NULL
);
INSERT INTO cancelled_orders (order_id, customer_id, order_date)
SELECT order_id, customer_id, order_date
FROM orders
WHERE status = 'cancelled';
SELECT order_id, customer_id, order_date FROM cancelled_orders ORDER BY order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| order_id | customer_id | order_date |
| --- | --- | --- |
| 104 | 3 | 2026-01-20 |
| 113 | 2 | 2026-03-05 |
<!-- /result -->

Rows that break a constraint are refused, and the **whole statement** fails, not just the bad row:

<!-- sql error -->
```sql
INSERT INTO products (product_id, name, category, price)
VALUES (14, 'Coaster', 'Kitchen', 4.00),
       (1,  'Duplicate lamp', 'Home', 1.00);
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>duplicate key value violates unique constraint "products_pkey"</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>UNIQUE constraint failed: products.product_id</code></p>
<!-- /result -->

Product 14 was not added either. To skip bad rows instead of failing, see `ON CONFLICT DO NOTHING` in
[section 17.5](#upsert).

## 17.2 UPDATE { #update }

`UPDATE` changes columns in the rows that match its `WHERE`:

**Task:** Raise every Kitchen price by 10%, rounded to cents, then list the Kitchen products.

<!-- sql -->
```sql
UPDATE products
SET price = ROUND(price * 1.10, 2)
WHERE category = 'Kitchen';
SELECT product_id, name, price FROM products WHERE category = 'Kitchen' ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| product_id | name | price |
| --- | --- | --- |
| 4 | Coffee mug | 9.63 |
| 5 | Tea kettle | 35.20 |
<!-- /result -->

!!! danger "UPDATE without WHERE changes every row"
    `UPDATE products SET price = 0;` is a valid statement. It sets all eleven prices to zero, at once, without asking.
    Before running an `UPDATE` or `DELETE` on real data, run a `SELECT` with the same `WHERE` and check the row count;
    on a database that supports it, do it inside a transaction so you can roll back ([section 17.8](#habits)).

Several columns change in one `SET`, separated by commas. Every expression on the right sees the row **as it was
before** the update, so swapping two columns works:

**Task:** For customer 2, swap the city and country columns, then show the row.

<!-- sql -->
```sql
UPDATE customers
SET city = country, country = city
WHERE customer_id = 2;
SELECT customer_id, city, country FROM customers WHERE customer_id = 2;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| customer_id | city | country |
| --- | --- | --- |
| 2 | Nigeria | Lagos |
<!-- /result -->

### Updating from another table { #update-from }

"Set each product's price to the lowest price it has ever been sold for" needs data from `order_items`. The
portable way is a correlated subquery in `SET`:

**Task:** Set each product's price to the lowest price it was ever sold at (products never sold keep theirs), then show products 5, 6 and 11.

<!-- sql -->
```sql
UPDATE products
SET price = (SELECT MIN(i.unit_price) FROM order_items i WHERE i.product_id = products.product_id)
WHERE EXISTS (SELECT 1 FROM order_items i WHERE i.product_id = products.product_id);
SELECT product_id, name, price FROM products WHERE product_id IN (5, 6, 11) ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| product_id | name | price |
| --- | --- | --- |
| 5 | Tea kettle | 30.00 |
| 6 | Office chair | 139.00 |
| 11 | Bookend | 9.50 |
<!-- /result -->

The `WHERE EXISTS` matters: without it, the bookend (never sold) would get `MIN` of no rows, which is NULL, and lose
its price. The tea kettle (once sold at 30.00) and the office chair (once at 139.00) get their lowest prices.
The shorter form is `UPDATE ... FROM`, a join inside the update:

<!-- sql same -->
```sql
UPDATE products
SET price = s.min_paid
FROM (SELECT product_id, MIN(unit_price) AS min_paid FROM order_items GROUP BY product_id) AS s
WHERE s.product_id = products.product_id;
SELECT product_id, name, price FROM products WHERE product_id IN (5, 6, 11) ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 3 rows.</p>

| product_id | name | price |
| --- | --- | --- |
| 5 | Tea kettle | 30.00 |
| 6 | Office chair | 139.00 |
| 11 | Bookend | 9.50 |
<!-- /result -->

A product with no match in `s` is simply not updated, so the bookend is safe here without an extra condition.
`UPDATE ... FROM` works on PostgreSQL and on SQLite from 3.33; SQL Server has it with a slightly different layout,
and MySQL writes `UPDATE products JOIN (...) s ON ... SET ...`. If one target row matches **several** rows in
`FROM`, PostgreSQL and SQLite update it with one of them, chosen unpredictably; aggregate first, as here, so each
row matches at most one.

## 17.3 DELETE and TRUNCATE { #delete }

`DELETE` removes the rows that match its `WHERE` (and, like `UPDATE`, every row without one). Conditions on other
tables are written with a subquery, which works on both databases:

**Task:** Delete the logins of Canadian customers, then count the logins left per customer.

<!-- sql -->
```sql
DELETE FROM logins
WHERE customer_id IN (SELECT customer_id FROM customers WHERE country = 'Canada');
SELECT customer_id, COUNT(*) AS logins FROM logins GROUP BY customer_id ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| customer_id | logins |
| --- | --- |
| 2 | 4 |
| 4 | 4 |
<!-- /result -->

PostgreSQL also has `DELETE ... USING`, a join in the delete; SQLite does not:

**Task:** The same delete, written as a join with `USING`.

<!-- sql pg -->
```sql
DELETE FROM logins AS l
USING customers AS c
WHERE c.customer_id = l.customer_id AND c.country = 'Canada';
SELECT customer_id, COUNT(*) AS logins FROM logins GROUP BY customer_id ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

| customer_id | logins |
| --- | --- |
| 2 | 4 |
| 4 | 4 |
<!-- /result -->

<!-- sql sqlite error -->
```sql
DELETE FROM logins AS l
USING customers AS c
WHERE c.customer_id = l.customer_id AND c.country = 'Canada';
```

<!-- result -->
<p class="sql-tested sql-error">SQLite 3.53: error: <code>near "USING": syntax error</code></p>
<!-- /result -->

Foreign keys protect the rows other tables point at ([chapter 1](01-Tables-Rows-and-Keys.md#foreign-key)): deleting
a customer who has orders fails until the orders are dealt with (on SQLite only with `PRAGMA foreign_keys = ON`,
chapter 1).

`TRUNCATE logins` empties a table at once, faster than `DELETE` on a large table because it does not visit the rows.
PostgreSQL has it (and can roll it back inside a transaction); SQLite does not, but optimises a plain
`DELETE FROM logins` with no `WHERE` in a similar way. In MySQL and Oracle, `TRUNCATE` commits immediately and cannot
be rolled back.

## 17.4 RETURNING { #returning }

`RETURNING` makes a changing statement also return rows: the rows it inserted, updated or deleted, as they are
afterwards (for `DELETE`, as they were). It saves a second query and shows exactly what changed:

**Task:** Raise every Home price by 1 and show the changed rows in the same statement.

<!-- sql -->
```sql
UPDATE products
SET price = price + 1
WHERE category = 'Home'
RETURNING product_id, name, price;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| product_id | name | price |
| --- | --- | --- |
| 1 | Desk lamp | 25.50 |
| 8 | Plant pot | 13.25 |
| 9 | Wall clock | 25.50 |
| 11 | Bookend | 10.50 |
<!-- /result -->

PostgreSQL has had it for years; SQLite since 3.35. SQL Server's version is `OUTPUT inserted.*`; MySQL has none.
A common use is getting the id a database just generated: `INSERT ... RETURNING id`.

## 17.5 Upsert: INSERT ... ON CONFLICT { #upsert }

Loading data often means "add these rows; if a row with the same key is already there, update it instead". That
is an **upsert**. PostgreSQL and SQLite share the same syntax for it:

**Task:** Load two products: update the price of product 1 if it exists, insert product 12 if not; then show both.

<!-- sql -->
```sql
INSERT INTO products (product_id, name, category, price)
VALUES (1,  'Desk lamp', 'Home',    26.00),     -- exists: update its price
       (12, 'Teapot',    'Kitchen', 27.00)      -- new: insert it
ON CONFLICT (product_id) DO UPDATE
SET price = excluded.price;
SELECT product_id, name, price FROM products WHERE product_id IN (1, 12) ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| product_id | name | price |
| --- | --- | --- |
| 1 | Desk lamp | 26.00 |
| 12 | Teapot | 27.00 |
<!-- /result -->

`ON CONFLICT (product_id)` names the key to check; `excluded` is the row that was refused, so `excluded.price` is
the new price. `DO NOTHING` instead skips the rows that already exist, which makes a load safe to repeat:

**Task:** Load the same two products, but leave existing products untouched; then show both.

<!-- sql -->
```sql
INSERT INTO products (product_id, name, category, price)
VALUES (1,  'Desk lamp', 'Home',    26.00),
       (12, 'Teapot',    'Kitchen', 27.00)
ON CONFLICT (product_id) DO NOTHING;
SELECT product_id, name, price FROM products WHERE product_id IN (1, 12) ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| product_id | name | price |
| --- | --- | --- |
| 1 | Desk lamp | 24.50 |
| 12 | Teapot | 27.00 |
<!-- /result -->

The lamp kept its old price; only the teapot went in. Two rules:

- The columns in `ON CONFLICT (...)` must have a primary key, a `UNIQUE` constraint or a unique index. A name is not unique here, so
  this fails on both databases:

    <!-- sql error -->
    ```sql
    INSERT INTO products (product_id, name, category, price)
    VALUES (20, 'Desk lamp', 'Home', 26.00)
    ON CONFLICT (name) DO UPDATE SET price = excluded.price;
    ```

    <!-- result -->
    <p class="sql-tested sql-error">PostgreSQL 16: error: <code>there is no unique or exclusion constraint matching the ON CONFLICT specification</code></p>
    <p class="sql-tested sql-error">SQLite 3.53: error: <code>ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint</code></p>
    <!-- /result -->

- A `WHERE` on the `DO UPDATE` limits which existing rows change. Updating only when something really changed keeps
  "last updated" columns and change logs honest:

    <!-- sql -->
    ```sql
    INSERT INTO products (product_id, name, category, price)
    VALUES (1, 'Desk lamp',  'Home', 24.50),
           (2, 'Notebook',   'Office', 3.50)
    ON CONFLICT (product_id) DO UPDATE
    SET price = excluded.price
    WHERE products.price <> excluded.price
    RETURNING product_id, price;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | product_id | price |
    | --- | --- |
    | 2 | 3.50 |
    <!-- /result -->

    The lamp's price was already 24.50, so only the notebook changed and only it is returned.

MySQL writes the same idea as `INSERT ... ON DUPLICATE KEY UPDATE price = VALUES(price)` (newer versions: a row
alias), SQL Server uses `MERGE`.

## 17.6 MERGE { #merge }

`MERGE` is the SQL standard's statement for "compare a source with a target and insert, update or delete as needed",
in one statement. It is common in warehouses (SQL Server, Oracle, Snowflake, and Databricks's `MERGE INTO` on Delta
tables). PostgreSQL has had it since version 15:

**Task:** Apply a price feed to products in one statement: update matching products, delete discontinued ones, insert new ones.

<!-- sql pg -->
```sql
CREATE TABLE price_feed (product_id INTEGER, name VARCHAR(50), category VARCHAR(20), price NUMERIC(8,2),
                         discontinued BOOLEAN);
INSERT INTO price_feed VALUES
  (1,  'Desk lamp', 'Home',    26.00, FALSE),   -- price change
  (2,  'Notebook',  'Office',   3.25, FALSE),   -- no change
  (11, 'Bookend',   'Home',     9.50, TRUE),    -- to remove
  (12, 'Teapot',    'Kitchen', 27.00, FALSE);   -- new
MERGE INTO products AS t
USING price_feed AS s
ON t.product_id = s.product_id
WHEN MATCHED AND s.discontinued THEN
  DELETE
WHEN MATCHED AND t.price <> s.price THEN
  UPDATE SET price = s.price
WHEN NOT MATCHED AND NOT s.discontinued THEN
  INSERT (product_id, name, category, price) VALUES (s.product_id, s.name, s.category, s.price);
SELECT product_id, name, price FROM products WHERE product_id IN (1, 2, 11, 12) ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

| product_id | name | price |
| --- | --- | --- |
| 1 | Desk lamp | 26.00 |
| 2 | Notebook | 3.25 |
| 12 | Teapot | 27.00 |
<!-- /result -->

Each target row may be matched by at most one source row, and the first `WHEN` whose condition is true decides
what happens to it. Matched rows can be updated or deleted; unmatched ones inserted. If two source rows match
the same target row, PostgreSQL stops with an error rather than guess; de-duplicate the source first
([chapter 22](22-Duplicates-and-Incremental-Loads.md)).

SQLite has no `MERGE`:

<!-- sql sqlite error -->
```sql
MERGE INTO products AS t
USING (SELECT 1 AS product_id, 26.00 AS price) AS s
ON t.product_id = s.product_id
WHEN MATCHED THEN UPDATE SET price = s.price;
```

<!-- result -->
<p class="sql-tested sql-error">SQLite 3.53: error: <code>near "MERGE": syntax error</code></p>
<!-- /result -->

On SQLite, do the same with two or three statements in one transaction: `INSERT ... ON CONFLICT DO UPDATE` for the
inserts and updates, and a `DELETE ... WHERE product_id IN (...)` for the removals. The upsert is also the better
choice on PostgreSQL when you only insert or update: it is safe when two sessions load at the same time, while
`MERGE` can still fail with a duplicate-key error in that case.

!!! note "Newer PostgreSQL"
    PostgreSQL 17 added `RETURNING` to `MERGE` and `WHEN NOT MATCHED BY SOURCE` (act on target rows the source no
    longer has). Neither works on version 16, which is what this page ran on; check the version before relying on
    them.

## 17.7 SQLite's INSERT OR REPLACE { #replace }

SQLite also has `INSERT OR REPLACE` (and its short form `REPLACE INTO`), which looks like an upsert but is not one:
when the key exists, it **deletes** the old row and inserts the new one. Columns you did not give are not kept;
they become NULL or their default:

**Task:** Replace customer 1's row with only a name, country and signup date, and see what happens to the other columns.

<!-- sql sqlite -->
```sql
REPLACE INTO customers (customer_id, name, country, signup_date)
VALUES (1, 'Ana Silva', 'Canada', '2025-11-03');
SELECT customer_id, name, email, city, country FROM customers WHERE customer_id = 1;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| customer_id | name | email | city | country |
| --- | --- | --- | --- | --- |
| 1 | Ana Silva | *NULL* | *NULL* | Canada |
<!-- /result -->

Ana's email and city are gone. Use `ON CONFLICT ... DO UPDATE` to change only the columns you mean to. MySQL's
`REPLACE` behaves the same way; PostgreSQL has neither.

## 17.8 Safe habits { #habits }

1. **SELECT first.** Write the `WHERE`, run it as a `SELECT`, check the rows and their count, then change `SELECT`
   to `UPDATE` or `DELETE`.
2. **Use a transaction.** `BEGIN;` the change, check, then `COMMIT;` or `ROLLBACK;` ([chapter 20](20-Transactions-and-Isolation.md)).
3. **Use `RETURNING`** to see exactly which rows changed.
4. **Name the columns** in every `INSERT`.
5. **Make loads repeatable.** A load that runs twice should not double the data: upsert on a key, or delete the
   batch and insert it again, inside one transaction ([chapter 22](22-Duplicates-and-Incremental-Loads.md)).
6. **Change the fewest rows.** `WHERE target.x IS DISTINCT FROM source.x` skips rows that would not change.

## 17.9 Summary { #summary }

- `INSERT` with a column list; several rows per statement; `INSERT ... SELECT` to copy. One bad row fails the
  whole statement.
- `UPDATE` and `DELETE` change every row unless a `WHERE` says otherwise. `SET` expressions see the old row.
- Update from another table with a correlated subquery (portable) or `UPDATE ... FROM` (aggregate first).
- `DELETE ... USING` and `TRUNCATE` are PostgreSQL only; `DELETE ... WHERE ... IN` works everywhere.
- `RETURNING` shows the changed rows (PostgreSQL, SQLite 3.35+).
- Upsert: `INSERT ... ON CONFLICT (key) DO UPDATE SET col = excluded.col` (or `DO NOTHING`), the same on both.
- `MERGE`: PostgreSQL 15+, not SQLite. SQLite's `REPLACE` deletes and reinserts, wiping columns you did not give.

!!! question "Asked aloud: changing data"
    Questions an interviewer may ask in a spoken round. Answer out loud first, then open the model answer.

    ??? note "What is an upsert, and how do you write one?"
        Insert a row, or update it if a row with the same key already exists. In PostgreSQL and SQLite:
        `INSERT ... ON CONFLICT (key) DO UPDATE SET col = excluded.col`. In SQL Server, Oracle, Snowflake and
        Databricks, `MERGE`. In MySQL, `ON DUPLICATE KEY UPDATE`. It needs a unique key to detect the conflict.

    ??? note "What does MERGE do that an upsert does not?"
        It can also **delete** matched rows, and apply different actions under different conditions
        (`WHEN MATCHED AND ... THEN`), all in one statement driven by a source table. An upsert only inserts or
        updates.

    ??? note "DELETE versus TRUNCATE?"
        `DELETE` removes rows one by one, can have a `WHERE`, fires row triggers and can be rolled back. `TRUNCATE`
        empties the whole table at once, much faster, without a `WHERE`. Whether it can be rolled back depends on
        the database: yes in PostgreSQL, no in MySQL and Oracle (it commits).

    ??? note "How do you make a daily load idempotent?"
        So that running it twice leaves the same result as running it once: upsert on a business key, or delete the
        day's partition and reinsert it inside one transaction, or `MERGE`. Never a plain `INSERT` of the whole
        batch.

    ??? note "You ran an UPDATE without a WHERE in production. What now?"
        If it is still inside an open transaction, `ROLLBACK`. If it was committed, restore the affected rows from a
        backup or point-in-time recovery, or from history tables or a data lake copy; then add safeguards: changes
        reviewed, run in transactions, `SELECT` first, permissions that prevent ad-hoc writes.

    ??? note "Why name the columns in an INSERT?"
        The statement keeps working when columns are added or reordered, and a value cannot land in the wrong column
        by position.

## Practice { #practice }

**17.1** Customer 10 (the second Ana Silva) has moved from Lisbon to Porto. Change her city, and return her id,
name and new city in the same statement.

??? success "Answer"
    <!-- sql -->
    ```sql
    UPDATE customers
    SET city = 'Porto'
    WHERE customer_id = 10
    RETURNING customer_id, name, city;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | customer_id | name | city |
    | --- | --- | --- |
    | 10 | Ana Silva | Porto |
    <!-- /result -->

    The `WHERE` uses the id, not the name: `WHERE name = 'Ana Silva'` would move both Ana Silvas.

**17.2** Delete the logins of customers who have never placed an order. Then show how many logins are left.

??? success "Answer"
    <!-- sql -->
    ```sql
    DELETE FROM logins
    WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = logins.customer_id);
    SELECT COUNT(*) AS logins_left FROM logins;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | logins_left |
    | --- |
    | 15 |
    <!-- /result -->

    Every customer with logins (1, 2, 4 and 6) has placed an order, so nothing is deleted and 15 remain: a correct
    answer can change nothing. `NOT IN (SELECT customer_id FROM orders)` would also delete nothing here, but for the
    wrong reason: order 108's NULL customer makes every `NOT IN` unknown ([6.8](06-Null-and-Three-Valued-Logic.md#joins-not-in)).

**17.3** A price list arrives as rows `(2, 3.50)`, `(4, 8.75)`, `(10, 30.00)`. Update the products whose price
differs, and return each changed product's id and new price. Write it so it runs on both databases.

??? success "Answer"
    <!-- sql -->
    ```sql
    UPDATE products
    SET price = s.price
    FROM (SELECT 2 AS product_id, 3.50 AS price
          UNION ALL SELECT 4, 8.75
          UNION ALL SELECT 10, 30.00) AS s
    WHERE s.product_id = products.product_id
      AND products.price <> s.price
    RETURNING products.product_id, products.price;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | product_id | price |
    | --- | --- |
    | 2 | 3.50 |
    | 10 | 30.00 |
    <!-- /result -->

    The mug is already 8.75, so it is not touched. On SQLite before 3.33, use the correlated-subquery form from
    [section 17.2](#update-from) (and before 3.35 drop the `RETURNING`).

**17.4** Load these two products so that running the statement twice gives the same result as running it once:
`(14, 'Coaster', 'Kitchen', 4.00)` and `(15, 'Lamp shade', 'Home', 11.00)`. If a product id is already there, keep
the existing row unchanged.

??? success "Answer"
    <!-- sql -->
    ```sql
    INSERT INTO products (product_id, name, category, price)
    VALUES (14, 'Coaster', 'Kitchen', 4.00), (15, 'Lamp shade', 'Home', 11.00)
    ON CONFLICT (product_id) DO NOTHING;
    INSERT INTO products (product_id, name, category, price)
    VALUES (14, 'Coaster', 'Kitchen', 4.00), (15, 'Lamp shade', 'Home', 11.00)
    ON CONFLICT (product_id) DO NOTHING;
    SELECT COUNT(*) AS products FROM products;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | products |
    | --- |
    | 13 |
    <!-- /result -->

    The statement ran twice and the shop has 13 products, not 15: the second run found both ids and skipped them.

**17.5** What is wrong with this statement, meant to raise the price of products that sold more than 5 units?

```sql
UPDATE products SET price = price * 1.05
WHERE product_id IN (SELECT product_id FROM order_items GROUP BY product_id HAVING SUM(quantity) > 5);
```

??? success "Answer"
    Nothing: it runs on both databases and changes the three products that sold more than 5 units, the notebook (25),
    the coffee mug (9) and the plant pot (6). It is a trap question; the point is to check the subquery alone first,
    which shows exactly which rows the update will touch:

    <!-- sql -->
    ```sql
    SELECT product_id, SUM(quantity) AS units
    FROM order_items
    GROUP BY product_id
    HAVING SUM(quantity) > 5
    ORDER BY product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | product_id | units |
    | --- | --- |
    | 2 | 25 |
    | 4 | 9 |
    | 8 | 6 |
    <!-- /result -->

    One thing to say aloud: `price * 1.05` can give more than 2 decimal places. A `NUMERIC(8,2)` column rounds it on
    PostgreSQL when it is stored; SQLite stores the longer number. `ROUND(price * 1.05, 2)` makes both the same.

**Next:** [18. CREATE TABLE: types and constraints](18-Create-Table-Types-Constraints.md).
