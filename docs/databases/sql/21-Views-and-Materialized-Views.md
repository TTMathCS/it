# 21. Views and materialized views

*A view is a query with a name. You select from it like a table, but it stores no rows: the database runs the
query each time. A materialized view stores the result and must be refreshed. This chapter shows both, what you can
and cannot do through a view, and where PostgreSQL and SQLite differ.*

!!! abstract "In this chapter"
    **You will learn:**

    - `CREATE VIEW`, and why a view always shows current data
    - replacing and dropping views, and what happens to a view when its table changes
    - updating rows through a view, and `WITH CHECK OPTION`
    - materialized views: `CREATE MATERIALIZED VIEW`, `REFRESH`, `CONCURRENTLY`, and how to get the same on SQLite
    - when to use a view, a materialized view, a CTE or a table

    **You need:** [chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md) and [chapter 11](11-CTEs-and-Recursive-CTEs.md).

## 21.1 A view is a saved query { #create-view }

This view gives each customer's number of shipped orders and what they spent. It is created once and kept for the
rest of the page.

<!-- sql keep quiet -->
```sql
CREATE VIEW customer_sales AS
SELECT c.customer_id, c.name,
       COUNT(DISTINCT o.order_id)        AS orders,
       SUM(oi.quantity * oi.unit_price)  AS spent
FROM customers c
JOIN orders o       ON o.customer_id = c.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'shipped'
GROUP BY c.customer_id, c.name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: done.</p>
<!-- /result -->

Now it reads like a table:

<!-- sql -->
```sql
SELECT customer_id, name, orders, spent
FROM customer_sales
ORDER BY spent DESC, customer_id
LIMIT 3;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| customer_id | name | orders | spent |
| --- | --- | --- | --- |
| 1 | Ana Silva | 5 | 289.00 |
| 2 | Ben Okafor | 2 | 205.50 |
| 4 | Dana Kim | 2 | 205.50 |
<!-- /result -->

A view stores no rows. Each query on it runs the view's query again, so it always shows the data as it is now. Here
the price on order 102 is changed (inside a transaction that is rolled back), and Ben's total follows at once:

<!-- sql -->
```sql
UPDATE order_items SET unit_price = 100.00 WHERE order_id = 102;
SELECT customer_id, name, spent FROM customer_sales WHERE customer_id = 2;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| customer_id | name | spent |
| --- | --- | --- |
| 2 | Ben Okafor | 156.50 |
<!-- /result -->

Ben's 205.50 became 156.50. What views are for:

- **Naming a query used in many places**, so the logic (here: what counts as a sale) is written once.
- **Hiding detail**: a view with no `email` column can be granted to people who must not see emails
  ([chapter 29](29-Safe-SQL.md)).
- **A stable interface**: if the tables behind it are reorganized, the view can be rewritten so that its users see
  the same columns.

A view's query should not end in `ORDER BY` for its users' sake: the query that reads the view decides the order. As
everywhere, a result without its own `ORDER BY` has no promised order.

### Views and speed { #speed }

A view is not faster than its query, and usually not slower. PostgreSQL puts the view's query into the outer query
before planning it (SQLite does the same whenever its "query flattening" rules allow), so a `WHERE customer_id = 2`
on the view filters early, as if you had written the whole thing out ([chapter 25](25-Indexes-and-Explain.md) shows how to see the plan). A view on a view on a view, though,
is hard to read and can hide expensive joins that the outer query does not need.

## 21.2 Replacing, dropping, and what breaks { #replace }

PostgreSQL can replace a view in one statement. SQLite has no `CREATE OR REPLACE VIEW`; drop it and create it again.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    CREATE OR REPLACE VIEW customer_sales AS
    SELECT c.customer_id, c.name,
           COUNT(DISTINCT o.order_id)        AS orders,
           SUM(oi.quantity * oi.unit_price)  AS spent,
           MAX(o.order_date)                 AS last_order
    FROM customers c
    JOIN orders o       ON o.customer_id = c.customer_id
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'shipped'
    GROUP BY c.customer_id, c.name;
    SELECT customer_id, orders, spent, last_order FROM customer_sales WHERE customer_id = 1;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

    | customer_id | orders | spent | last_order |
    | --- | --- | --- | --- |
    | 1 | 5 | 289.00 | 2026-04-05 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    DROP VIEW IF EXISTS customer_sales;
    CREATE VIEW customer_sales AS
    SELECT c.customer_id, c.name,
           COUNT(DISTINCT o.order_id)        AS orders,
           SUM(oi.quantity * oi.unit_price)  AS spent,
           MAX(o.order_date)                 AS last_order
    FROM customers c
    JOIN orders o       ON o.customer_id = c.customer_id
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'shipped'
    GROUP BY c.customer_id, c.name;
    SELECT customer_id, orders, spent, last_order FROM customer_sales WHERE customer_id = 1;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 1 row.</p>

    | customer_id | orders | spent | last_order |
    | --- | --- | --- | --- |
    | 1 | 5 | 289 | 2026-04-05 |
    <!-- /result -->

(Both blocks are rolled back, so the rest of the page keeps the first version of the view.) PostgreSQL's
`CREATE OR REPLACE` may only **add** columns at the end. Renaming or retyping an existing column is refused, and you
must drop the view first:

<!-- sql pg error -->
```sql
CREATE OR REPLACE VIEW customer_sales AS
SELECT c.customer_id, c.name AS customer_name, 0 AS orders, 0 AS spent
FROM customers c;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>cannot change name of view column "name" to "customer_name"</code></p>
<!-- /result -->

**When the table under a view changes**, the two databases protect you differently. PostgreSQL records which tables
each view depends on and refuses to drop one that is still used:

=== "PostgreSQL"

    <!-- sql pg error -->
    ```sql
    DROP TABLE order_items;
    ```

    <!-- result -->
    <p class="sql-tested sql-error">PostgreSQL 16: error: <code>cannot drop table order_items because other objects depend on it</code></p>
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite error -->
    ```sql
    DROP TABLE order_items;
    SELECT * FROM customer_sales;
    ```

    <!-- result -->
    <p class="sql-tested sql-error">SQLite 3.53: error: <code>no such table: main.order_items</code></p>
    <!-- /result -->

SQLite drops the table without a word; the view is broken and fails only when someone next uses it. (On PostgreSQL,
`DROP TABLE ... CASCADE` drops the views too, which is rarely what you want.)

**`SELECT *` in a view** is another difference. PostgreSQL turns the `*` into a fixed list of columns when the view is
created; a column added to the table later does not appear in the view. SQLite keeps the text of the view and reads
the `*` again on every use, so the new column does appear:

<!-- sql pg -->
```sql
CREATE VIEW all_products AS SELECT * FROM products;
ALTER TABLE products ADD COLUMN weight_kg NUMERIC(6,2);
SELECT * FROM all_products WHERE product_id = 1;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| product_id | name | category | price |
| --- | --- | --- | --- |
| 1 | Desk lamp | Home | 24.50 |
<!-- /result -->

<!-- sql sqlite -->
```sql
CREATE VIEW all_products AS SELECT * FROM products;
ALTER TABLE products ADD COLUMN weight_kg NUMERIC(6,2);
SELECT * FROM all_products WHERE product_id = 1;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| product_id | name | category | price | weight_kg |
| --- | --- | --- | --- | --- |
| 1 | Desk lamp | Home | 24.5 | *NULL* |
<!-- /result -->

List the columns in a view instead of `*`, so that what it returns never changes by accident.

## 21.3 Changing data through a view { #updatable }

On PostgreSQL a **simple** view (one table, no `GROUP BY`, `DISTINCT`, aggregates, set operations or `LIMIT`) can be
updated, and the change goes to the table under it. SQLite views are read-only (unless you write an `INSTEAD OF`
trigger for them).

<!-- sql keep quiet -->
```sql
CREATE VIEW toronto_customers AS
SELECT customer_id, name, city FROM customers WHERE city = 'Toronto';
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: done.</p>
<!-- /result -->

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    UPDATE toronto_customers SET name = 'Ivan P. Petrov' WHERE customer_id = 9;
    SELECT customer_id, name, city FROM customers WHERE customer_id = 9;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

    | customer_id | name | city |
    | --- | --- | --- |
    | 9 | Ivan P. Petrov | Toronto |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite error -->
    ```sql
    UPDATE toronto_customers SET name = 'Ivan P. Petrov' WHERE customer_id = 9;
    ```

    <!-- result -->
    <p class="sql-tested sql-error">SQLite 3.53: error: <code>cannot modify toronto_customers because it is a view</code></p>
    <!-- /result -->

A row can be changed so that it no longer belongs to the view. Ivan moves to Ottawa through the Toronto view, and
leaves it:

<!-- sql pg -->
```sql
UPDATE toronto_customers SET city = 'Ottawa' WHERE customer_id = 9;
SELECT COUNT(*) AS toronto_customers FROM toronto_customers;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| toronto_customers |
| --- |
| 2 |
<!-- /result -->

Three became two. `WITH CHECK OPTION` forbids that: every row written through the view must still match its
`WHERE`.

<!-- sql pg error -->
```sql
CREATE VIEW toronto_only AS
SELECT customer_id, name, city FROM customers WHERE city = 'Toronto'
WITH CHECK OPTION;
UPDATE toronto_only SET city = 'Ottawa' WHERE customer_id = 9;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>new row violates check option for view "toronto_only"</code></p>
<!-- /result -->

Updating through views is used less than reading through them. It is worth knowing for the interview question "can
you update a view?": *yes, a simple one, in most databases; not one with aggregates; joins only in some databases;
and not in SQLite without triggers.*

## 21.4 Materialized views { #materialized }

A **materialized view** runs its query once and stores the result like a table. Reading it is as fast as reading a
table, but it does not follow changes: it shows the data as it was at the last `REFRESH`. PostgreSQL has them
(SQLite does not; see [below](#sqlite-materialized)).

<!-- sql pg keep quiet -->
```sql
CREATE MATERIALIZED VIEW product_units AS
SELECT p.product_id, p.name, SUM(oi.quantity) AS units
FROM products p
JOIN order_items oi ON oi.product_id = p.product_id
GROUP BY p.product_id, p.name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16: 10 rows changed.</p>
<!-- /result -->

Change an order, and the materialized view still shows the old number:

<!-- sql pg -->
```sql
UPDATE order_items SET quantity = 5 WHERE order_id = 102 AND product_id = 6;
SELECT product_id, name, units FROM product_units WHERE product_id = 6;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| product_id | name | units |
| --- | --- | --- |
| 6 | Office chair | 3 |
<!-- /result -->

After a refresh it is right again:

<!-- sql pg -->
```sql
UPDATE order_items SET quantity = 5 WHERE order_id = 102 AND product_id = 6;
REFRESH MATERIALIZED VIEW product_units;
SELECT product_id, name, units FROM product_units WHERE product_id = 6;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| product_id | name | units |
| --- | --- | --- |
| 6 | Office chair | 7 |
<!-- /result -->

A plain `REFRESH` locks the materialized view: anyone reading it waits until the refresh ends. `REFRESH
MATERIALIZED VIEW CONCURRENTLY` lets readers keep reading the old rows while the new ones are computed, but it needs
a unique index on the materialized view, so that it can match old rows to new ones:

<!-- sql pg error -->
```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY product_units;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>cannot refresh materialized view "public.product_units" concurrently</code></p>
<!-- /result -->

<!-- sql pg -->
```sql
CREATE UNIQUE INDEX product_units_id ON product_units (product_id);
REFRESH MATERIALIZED VIEW CONCURRENTLY product_units;
SELECT COUNT(*) AS products FROM product_units;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| products |
| --- |
| 10 |
<!-- /result -->

PostgreSQL never refreshes a materialized view by itself. Something must run `REFRESH`: a scheduled job, or the
last step of the pipeline that loads the tables. Data warehouses offer more. Databricks and Snowflake, for example,
have materialized views that the platform refreshes, fully or only for changed data, under rules that differ by
product (from their documentation; the Databricks tutorial covers its own).

### The same on SQLite: a summary table { #sqlite-materialized }

Without materialized views, build the table yourself and refresh it inside one transaction, so that readers never
see it empty ([chapter 20](20-Transactions-and-Isolation.md#pipelines)). This works on every database:

<!-- sql raw -->
```sql
CREATE TABLE product_units_table AS
SELECT p.product_id, p.name, SUM(oi.quantity) AS units
FROM products p
JOIN order_items oi ON oi.product_id = p.product_id
GROUP BY p.product_id, p.name;

BEGIN;
DELETE FROM product_units_table;
INSERT INTO product_units_table (product_id, name, units)
SELECT p.product_id, p.name, SUM(oi.quantity)
FROM products p
JOIN order_items oi ON oi.product_id = p.product_id
GROUP BY p.product_id, p.name;
COMMIT;

SELECT product_id, name, units FROM product_units_table ORDER BY units DESC, product_id LIMIT 3;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| product_id | name | units |
| --- | --- | --- |
| 2 | Notebook | 25 |
| 4 | Coffee mug | 9 |
| 8 | Plant pot | 6 |
<!-- /result -->

## 21.5 Which one to use { #choose }

| | Stores rows? | Always current? | Lives | Use it for |
| --- | --- | --- | --- | --- |
| CTE (`WITH`) | no | yes | one query | breaking one query into steps ([chapter 11](11-CTEs-and-Recursive-CTEs.md)) |
| Temporary view (`CREATE TEMP VIEW`) | no | yes | your session | a helper for several queries in one session |
| View | no | yes | until dropped | shared logic, hiding columns, a stable interface |
| Materialized view | yes | no, until `REFRESH` | until dropped | an expensive query read often, where data a little old is acceptable |
| Table (summary table) | yes | no, until reloaded | until dropped | the same, on any database, with full control of how it is loaded |

`CREATE TEMP VIEW` (or `TEMPORARY`) works on both databases; the view disappears when the connection closes.

## 21.6 Summary { #summary }

- A view is a named query; it stores nothing and shows current data. Select from it like a table.
- PostgreSQL has `CREATE OR REPLACE VIEW` (only adding columns at the end); SQLite needs `DROP VIEW` then `CREATE VIEW`.
- PostgreSQL refuses to drop a table a view uses; SQLite allows it and the view fails later. PostgreSQL fixes a view's
  `SELECT *` at creation; SQLite reads it again each time. List the columns.
- Simple one-table views can be updated on PostgreSQL; `WITH CHECK OPTION` keeps written rows inside the view. SQLite
  views are read-only.
- A materialized view stores its result and is only as fresh as its last `REFRESH`; `CONCURRENTLY` needs a unique
  index. On SQLite, use a summary table refreshed in one transaction.

!!! question "Asked aloud: views"
    ??? note "What is the difference between a view and a table?"
        A table stores rows. A view stores only a query; each time it is read, the query runs against the tables under
        it, so it is always current and takes no space. A materialized view is in between: it stores the query's result
        and is current only as of its last refresh.

    ??? note "View or materialized view: how do you choose?"
        A view when the query is cheap enough to run each time or the data must be current. A materialized view when the
        query is expensive, it is read much more often than the data changes, and results some minutes or hours old are
        acceptable. Someone must then own the refresh schedule.

    ??? note "Does a view make a query faster?"
        No. The database merges the view's query into yours and plans the whole thing, so it costs the same as writing
        it out. Only a materialized view (or a summary table, or an index) saves the work, by doing it in advance.

    ??? note "Can you insert or update through a view?"
        Yes for a simple view over one table, in PostgreSQL, MySQL, SQL Server and Oracle; the change goes to the base
        table. MySQL, SQL Server and Oracle also allow it through a join view when only one table's columns change.
        Not for views with `GROUP BY`, aggregates or `DISTINCT`, unless you write an `INSTEAD OF` trigger.
        SQLite views are read-only without such a trigger. `WITH CHECK OPTION` stops writes that would fall outside the
        view's `WHERE`.

    ??? note "How would you use views for security?"
        Grant users access to a view rather than the table: the view leaves out sensitive columns (emails, salaries) or
        rows (other regions), and the user cannot read the table directly. Row-level security policies do the row part
        more completely in PostgreSQL and in warehouses ([chapter 29](29-Safe-SQL.md)).

    ??? note "What does REFRESH MATERIALIZED VIEW CONCURRENTLY do, and what does it need?"
        It computes the new result and applies only the differences, while readers keep reading the old rows, instead of
        locking them out during the refresh. It needs a unique index on the materialized view (on plain columns, with no
        `WHERE`), and it is usually slower than a plain refresh.

## Practice { #practice }

**21.1** Create a view `monthly_revenue` with one row per month (`'2026-01'` and so on) and the revenue of shipped
orders in it, then use it to list the months with more than 200 in revenue, highest first. It must run on both
databases.

??? success "Answer"
    <!-- sql -->
    ```sql
    CREATE VIEW monthly_revenue AS
    SELECT SUBSTR(CAST(o.order_date AS TEXT), 1, 7) AS month,
           SUM(oi.quantity * oi.unit_price)          AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'shipped'
    GROUP BY SUBSTR(CAST(o.order_date AS TEXT), 1, 7);

    SELECT month, revenue
    FROM monthly_revenue
    WHERE revenue > 200
    ORDER BY revenue DESC, month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | month | revenue |
    | --- | --- |
    | 2026-03 | 322.50 |
    | 2026-02 | 277.50 |
    | 2026-01 | 241.50 |
    <!-- /result -->

    `CAST(... AS TEXT)` gives `'2026-01-03'` on both databases, so the first seven characters are the month. The
    `WHERE` on the view works like a `HAVING` on the query inside it.

**21.2** The support team must see customers' names and cities but not their emails. Write the view, and say how it
keeps emails hidden.

??? success "Answer"
    <!-- sql -->
    ```sql
    CREATE VIEW customers_public AS
    SELECT customer_id, name, city, country FROM customers;
    SELECT customer_id, name, city, country FROM customers_public WHERE country = 'Canada' ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_id | name | city | country |
    | --- | --- | --- | --- |
    | 1 | Ana Silva | Toronto | Canada |
    | 6 | Farah Haddad | Toronto | Canada |
    | 9 | Ivan Petrov | Toronto | Canada |
    <!-- /result -->

    The view alone hides nothing: it only helps when the support team is granted `SELECT` on the view and not on the
    table (`GRANT SELECT ON customers_public TO support;`, [chapter 29](29-Safe-SQL.md)). SQLite has no users or
    grants, so there the view is only a convenience.

**21.3** A dashboard reads a materialized view refreshed at 2 am. At 10 am, a manager asks why a large order placed
at 9 am is missing. Explain, and give two possible fixes.

??? success "Answer"
    The materialized view holds the result as of 2 am; the 9 am order arrives in it at the next refresh. Fixes: refresh
    more often (every hour, or at the end of each load), with `CONCURRENTLY` so the dashboard is not blocked; or, if
    the query is cheap enough, use a plain view so the data is always current. A third option is to show "data as of
    2:00" on the dashboard so nobody expects otherwise.

**21.4** A view is created as `CREATE VIEW v AS SELECT * FROM products;` and then a column `supplier` is added to
`products`. On which database does `SELECT * FROM v` show `supplier`? Why is this a reason to avoid `SELECT *` in
views on both?

??? success "Answer"
    On SQLite, which reads the `*` again at every use. PostgreSQL fixed the column list when the view was created, so
    `supplier` is missing until the view is created again ([21.2](#replace)). Either way, `SELECT *` makes the view's
    columns depend on the table's history: on PostgreSQL they silently fall behind, on SQLite they silently change
    under the view's users. Listing the columns makes the view say exactly what it returns.

**Next:** [22. Duplicates and incremental loads](22-Duplicates-and-Incremental-Loads.md).
