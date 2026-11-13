# 18. CREATE TABLE: types and constraints

*A table's definition decides what can go into it. Good types and constraints stop bad data at the door, so that
every query after them can trust what it reads. This chapter covers the column types worth knowing, the five kinds
of constraint (plus `DEFAULT`), ids the database numbers for you, and changing a table later. It also shows the biggest difference
between the two databases in this course: PostgreSQL enforces types, and SQLite, unless asked, does not.*

!!! abstract "In this chapter"
    **You will learn:**

    - the common column types, and which to use for money, dates and text
    - how PostgreSQL enforces types and lengths, and how SQLite's "type affinity" and `STRICT` tables differ
    - `NOT NULL`, `DEFAULT`, `UNIQUE`, `PRIMARY KEY`, `CHECK` and `FOREIGN KEY`, with `ON DELETE` actions
    - ids that number themselves: `GENERATED AS IDENTITY` and SQLite's `INTEGER PRIMARY KEY`
    - `CREATE TABLE ... AS SELECT`, `ALTER TABLE` and `DROP TABLE`

    **You need:** [chapter 1](01-Tables-Rows-and-Keys.md) and [chapter 17](17-Insert-Update-Delete-Merge.md). Every
    example runs in a transaction that is rolled back.

## 18.1 A table definition { #create }

**Task:** Create a `shipments` table with a key, a link to orders, a positive weight, a default for `delivered`, and one shipment per order and carrier; add one shipment and show it.

<!-- sql -->
```sql
CREATE TABLE shipments (
  shipment_id INTEGER       PRIMARY KEY,
  order_id    INTEGER       NOT NULL REFERENCES orders (order_id),
  carrier     VARCHAR(20)   NOT NULL,
  weight_kg   NUMERIC(6,2)  CHECK (weight_kg > 0),
  shipped_on  DATE          NOT NULL,
  delivered   BOOLEAN       NOT NULL DEFAULT FALSE,
  UNIQUE (order_id, carrier)
);
INSERT INTO shipments (shipment_id, order_id, carrier, weight_kg, shipped_on)
VALUES (1, 101, 'Canada Post', 1.20, '2026-01-04');
SELECT shipment_id, order_id, carrier, weight_kg, shipped_on, delivered FROM shipments;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| shipment_id | order_id | carrier | weight_kg | shipped_on | delivered |
| --- | --- | --- | --- | --- | --- |
| 1 | 101 | Canada Post | 1.20 | 2026-01-04 | false |
<!-- /result -->

Each column has a name, a type and optional constraints; constraints over several columns (here `UNIQUE (order_id,
carrier)`) go after the columns. `delivered` was not given, so it took its default. (SQLite shows the `FALSE` as 0;
the result is the same.)

## 18.2 Column types { #types }

| Kind | PostgreSQL | Notes |
| --- | --- | --- |
| whole numbers | `INTEGER` (to about 2.1 billion), `BIGINT`, `SMALLINT` | ids that may pass 2 billion: `BIGINT` |
| exact decimals | `NUMERIC(p, s)` (= `DECIMAL`) | **money**: `NUMERIC(12,2)`; p digits in all, s after the point |
| approximate decimals | `DOUBLE PRECISION`, `REAL` | measurements, science; never money ([4.2](04-Expressions-Case-Numbers-Dates-Cast.md#rounding)) |
| text | `TEXT`, `VARCHAR(n)`, `CHAR(n)` | `CHAR(n)` pads with spaces: avoid; `VARCHAR(n)` when a limit is a rule |
| true or false | `BOOLEAN` | SQLite stores 1 and 0 |
| dates and times | `DATE`, `TIMESTAMP`, `TIMESTAMPTZ`, `INTERVAL` | store moments as `TIMESTAMPTZ` (UTC inside) |
| other | `UUID`, `JSONB`, arrays, `BYTEA` | [chapter 24](24-JSON-and-Arrays.md) for JSON and arrays |

SQL Server spells some differently (`DATETIME2`, `NVARCHAR`, `BIT`), Oracle too (`NUMBER`, `VARCHAR2`), but the
choices are the same: exact decimals for money, a real date type for dates, a time zone for moments.

`TIMESTAMP` holds a date and time with no time zone. `TIMESTAMPTZ` (`TIMESTAMP WITH TIME ZONE`) converts the value
to UTC when it is stored and back to the session's time zone when read, so the same moment compares equal wherever
it was entered:

<!-- sql pg -->
```sql
SELECT CAST('2026-05-01 10:00:00+02' AS TIMESTAMPTZ) = CAST('2026-05-01 08:00:00+00' AS TIMESTAMPTZ) AS same_moment;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| same_moment |
| --- |
| true |
<!-- /result -->

## 18.3 Types are enforced on PostgreSQL, not on SQLite { #affinity }

PostgreSQL refuses a value that does not fit the column:

<!-- sql pgerror -->
```sql
CREATE TABLE codes (code VARCHAR(3), qty INTEGER);
INSERT INTO codes VALUES ('ABCDE', 1);
SELECT code, qty FROM codes;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>value too long for type character varying(3)</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 1 row.</p>
<!-- /result -->

SQLite stores it as given. It treats a column type as a preference, called **type affinity**: an `INTEGER` column
turns `'42'` into the number 42, but keeps `'hello'` as text, and `VARCHAR(3)` sets no length limit at all:

<!-- sql sqlite -->
```sql
CREATE TABLE codes (code VARCHAR(3), qty INTEGER);
INSERT INTO codes VALUES ('ABCDE', '42'), ('XY', 'hello');
SELECT code, qty, typeof(qty) AS stored_as FROM codes;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 2 rows.</p>

| code | qty | stored_as |
| --- | --- | --- |
| ABCDE | 42 | integer |
| XY | hello | text |
<!-- /result -->

From version 3.37, a table declared `STRICT` makes SQLite check types (it allows only `INT`, `INTEGER`, `REAL`,
`TEXT`, `BLOB` and `ANY` as types, and still does not check lengths):

<!-- sql sqlite error -->
```sql
CREATE TABLE codes (code TEXT, qty INTEGER) STRICT;
INSERT INTO codes VALUES ('XY', 'hello');
```

<!-- result -->
<p class="sql-tested sql-error">SQLite 3.53: error: <code>cannot store TEXT value in INTEGER column codes.qty</code></p>
<!-- /result -->

Decimals differ too. `NUMERIC(6,2)` on PostgreSQL rounds a value to 2 places as it is stored and refuses one that
does not fit; SQLite keeps the number as given:

<!-- sql pg -->
```sql
CREATE TABLE amounts (amount NUMERIC(6,2));
INSERT INTO amounts VALUES (1.005), (2.344);
SELECT amount FROM amounts;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

| amount |
| --- |
| 1.01 |
| 2.34 |
<!-- /result -->

<!-- sql sqlite -->
```sql
CREATE TABLE amounts (amount NUMERIC(6,2));
INSERT INTO amounts VALUES (1.005), (2.344);
SELECT amount FROM amounts;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 2 rows.</p>

| amount |
| --- |
| 1.005 |
| 2.344 |
<!-- /result -->

<!-- sql pgerror -->
```sql
CREATE TABLE amounts (amount NUMERIC(4,2));
INSERT INTO amounts VALUES (123.45);
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>numeric field overflow</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 0 rows.</p>
<!-- /result -->

`NUMERIC(4,2)` allows 4 digits in all, 2 after the point, so at most 99.99.

!!! tip "In a test on SQLite"
    Because SQLite stores what it is given, a task's data on SQLite can hold surprises PostgreSQL would have refused:
    a number stored as text, a date in another format, a value longer than the declared length. If a comparison or
    sort looks wrong on SQLite, check with `typeof(column)`.

## 18.4 Constraints { #constraints }

| Constraint | Means | NULL |
| --- | --- | --- |
| `NOT NULL` | a value is required | refuses NULL |
| `DEFAULT x` | the value when an `INSERT` leaves the column out | (not a check) |
| `UNIQUE` | no two rows have the same value (or combination) | NULLs do not clash |
| `PRIMARY KEY` | `UNIQUE` and `NOT NULL`; one per table | refuses NULL |
| `CHECK (condition)` | the condition must not be false | NULL passes |
| `FOREIGN KEY ... REFERENCES` | the value must exist in the other table's key | NULL passes |

Two of these surprise people because of NULL. A `CHECK` refuses a row only when the condition is FALSE, and with
NULL it is UNKNOWN, so NULL passes:

<!-- sql -->
```sql
CREATE TABLE stock (item VARCHAR(10), qty INTEGER CHECK (qty >= 0));
INSERT INTO stock VALUES ('pen', NULL);
SELECT item, qty FROM stock;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| item | qty |
| --- | --- |
| pen | *NULL* |
<!-- /result -->

<!-- sql error -->
```sql
CREATE TABLE stock (item VARCHAR(10), qty INTEGER CHECK (qty >= 0));
INSERT INTO stock VALUES ('cup', -1);
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>new row for relation "stock" violates check constraint "stock_qty_check"</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>CHECK constraint failed: qty &gt;= 0</code></p>
<!-- /result -->

The `NULL` row went in; the `-1` row was refused. Add `NOT NULL` when a value is required. And a `UNIQUE` constraint lets
several rows have NULL, since two NULLs are not equal:

<!-- sql -->
```sql
CREATE TABLE pairs (a INTEGER, b INTEGER, UNIQUE (a, b));
INSERT INTO pairs VALUES (1, NULL), (1, NULL);
SELECT COUNT(*) AS rows_stored FROM pairs;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| rows_stored |
| --- |
| 2 |
<!-- /result -->

Both rows are stored. SQL Server allows only one NULL; Oracle also refuses the second row when some key columns
are not NULL, as here. PostgreSQL 15 added `UNIQUE NULLS NOT DISTINCT` for that behaviour.

Give constraints names (`CONSTRAINT qty_not_negative CHECK (qty >= 0)`) and the error message names them, which
helps when a load fails at 3 a.m.

### What happens to the children: ON DELETE { #on-delete }

A foreign key can say what to do when the row it points at is deleted:

| Action | Deleting the parent ... |
| --- | --- |
| (none) / `NO ACTION` / `RESTRICT` | fails while children exist (the default) |
| `ON DELETE CASCADE` | deletes the children too |
| `ON DELETE SET NULL` | sets the children's foreign key to NULL |

**Task:** Make carts and cart items where deleting a cart deletes its items; delete cart 1 and list the items left.

<!-- sql -->
```sql
CREATE TABLE carts (cart_id INTEGER PRIMARY KEY, owner VARCHAR(10));
CREATE TABLE cart_items (
  cart_id INTEGER REFERENCES carts (cart_id) ON DELETE CASCADE,
  item    VARCHAR(10)
);
INSERT INTO carts VALUES (1, 'ana'), (2, 'bo');
INSERT INTO cart_items VALUES (1, 'pen'), (1, 'cup'), (2, 'lamp');
DELETE FROM carts WHERE cart_id = 1;
SELECT cart_id, item FROM cart_items ORDER BY item;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| cart_id | item |
| --- | --- |
| 2 | lamp |
<!-- /result -->

Cart 1's items went with it. On SQLite all of this needs `PRAGMA foreign_keys = ON` first; without it the foreign
key is not checked at all. `CASCADE` is right for things that cannot exist alone (an order's lines); for
anything with history, such as customers and their orders, the default refusal is safer.

## 18.5 Ids that number themselves { #identity }

Most tables use a number the database assigns. The spelling differs:

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    CREATE TABLE tickets (
      ticket_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      subject   VARCHAR(50) NOT NULL
    );
    INSERT INTO tickets (subject) VALUES ('Login fails'), ('Refund');
    SELECT ticket_id, subject FROM tickets ORDER BY ticket_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | ticket_id | subject |
    | --- | --- |
    | 1 | Login fails |
    | 2 | Refund |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    CREATE TABLE tickets (
      ticket_id INTEGER PRIMARY KEY,
      subject   VARCHAR(50) NOT NULL
    );
    INSERT INTO tickets (subject) VALUES ('Login fails'), ('Refund');
    SELECT ticket_id, subject FROM tickets ORDER BY ticket_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 2 rows.</p>

    | ticket_id | subject |
    | --- | --- |
    | 1 | Login fails |
    | 2 | Refund |
    <!-- /result -->

On PostgreSQL, `GENERATED ALWAYS AS IDENTITY` is the standard form (older code uses `SERIAL`). On SQLite, a column
declared exactly `INTEGER PRIMARY KEY` becomes the row's own id and fills itself. The same SQLite definition on
PostgreSQL does **not** number itself: the insert fails because the id is NULL. MySQL writes `AUTO_INCREMENT`, SQL
Server `IDENTITY(1,1)`. Generated ids can have gaps (after a rollback or a failed insert): never use them to count
rows or to mean "order of arrival" exactly.

## 18.6 Making and changing tables { #alter }

`CREATE TABLE ... AS SELECT` makes a table from a query, columns and rows, but **without** keys or constraints:

**Task:** Save each customer's number of orders as a new table, then show the top 3.

<!-- sql -->
```sql
CREATE TABLE customer_order_counts AS
SELECT customer_id, COUNT(*) AS orders
FROM orders
WHERE customer_id IS NOT NULL
GROUP BY customer_id;
SELECT customer_id, orders FROM customer_order_counts ORDER BY orders DESC, customer_id LIMIT 3;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| customer_id | orders |
| --- | --- |
| 1 | 5 |
| 2 | 3 |
| 3 | 2 |
<!-- /result -->

`ALTER TABLE` changes a table that already has data. Adding a column gives existing rows its default:

**Task:** Add a `vip` column to customers (false by default), make customer 1 a VIP, then show the first 3 customers.

<!-- sql -->
```sql
ALTER TABLE customers ADD COLUMN vip BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE customers SET vip = TRUE WHERE customer_id = 1;
SELECT customer_id, name, vip FROM customers WHERE customer_id <= 3 ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| customer_id | name | vip |
| --- | --- | --- |
| 1 | Ana Silva | true |
| 2 | Ben Okafor | false |
| 3 | Chen Wei | false |
<!-- /result -->

`ALTER TABLE ... RENAME COLUMN a TO b` and `DROP COLUMN` work on both (SQLite from 3.25 and 3.35). Changing a
column's type, `ALTER COLUMN city TYPE VARCHAR(100)`, is PostgreSQL only; on SQLite you create a new table, copy
the rows and rename it. On a large production table, some `ALTER`s rewrite every row and lock the table while they
do; check before running one at midday.

`DROP TABLE t` deletes the table and its data; `DROP TABLE IF EXISTS t` does not fail when it is missing, which
makes setup scripts repeatable.

## 18.7 Summary { #summary }

- Money in `NUMERIC(p, s)`, dates in `DATE`, moments in `TIMESTAMPTZ`, ids in `INTEGER` or `BIGINT`.
- PostgreSQL enforces types, lengths and decimal places. SQLite stores what it is given unless the table is
  `STRICT`; `typeof()` shows what is really stored.
- Constraints: `NOT NULL`, `DEFAULT`, `UNIQUE`, `PRIMARY KEY`, `CHECK`, `FOREIGN KEY`. NULL passes `CHECK`,
  `UNIQUE` and foreign keys: add `NOT NULL` where a value is required.
- `ON DELETE CASCADE` deletes children; the default refuses the delete.
- Self-numbering ids: `GENERATED ALWAYS AS IDENTITY` (PostgreSQL), `INTEGER PRIMARY KEY` (SQLite). Gaps happen.
- `CREATE TABLE AS SELECT` copies data, not constraints. `ALTER TABLE` adds, renames and drops columns.

!!! question "Asked aloud: tables, types and constraints"
    ??? note "Why not store money in a FLOAT?"
        Floating point stores most decimals approximately, so sums drift by fractions of a cent and comparisons
        fail. `NUMERIC(12,2)` stores exact decimals.

    ??? note "TIMESTAMP or TIMESTAMPTZ?"
        `TIMESTAMPTZ` for real moments (events, logs): it is stored in UTC and converted for display, so values
        entered in different time zones compare correctly. `TIMESTAMP` only for "wall clock" values with no zone,
        such as a shop's opening time.

    ??? note "Primary key versus unique constraint?"
        Both forbid duplicates. A primary key also forbids NULL, there is one per table, and it is what foreign keys
        point at by default. A table can have several unique constraints, and they allow NULL (several, except in
        SQL Server).

    ??? note "Surrogate key or natural key?"
        A surrogate key (a generated number) never changes and is small and fast to join on. A natural key (an
        email, a product code) has meaning but can change or repeat. Usual practice: a surrogate primary key plus a
        `UNIQUE` constraint on the natural key.

    ??? note "What does ON DELETE CASCADE do, and when is it dangerous?"
        Deleting a parent row also deletes the rows that reference it. It is dangerous where children carry history
        (orders, payments): one delete of a customer could silently remove years of records. Use it for parts that
        cannot exist alone.

    ??? note "Why might a constraint be left out of a data warehouse table?"
        Checking constraints slows bulk loads, and many warehouse engines (Snowflake, BigQuery, Databricks) accept
        primary and foreign keys only as information and do not enforce them. Data quality is then checked by tests
        in the pipeline instead ([chapter 23](23-Data-Quality-Checks.md)).

## Practice { #practice }

**18.1** Write a `CREATE TABLE` for product reviews: a self-numbering id; the product (must exist); a rating from 1
to 5 (required); an optional comment; the date written (default today); and at most one review per customer per
product. Then insert one review for product 2 by customer 1 and show it.

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        CREATE TABLE reviews (
          review_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          product_id  INTEGER NOT NULL REFERENCES products (product_id),
          customer_id INTEGER NOT NULL REFERENCES customers (customer_id),
          rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
          comment     TEXT,
          written_on  DATE NOT NULL DEFAULT CURRENT_DATE,
          UNIQUE (customer_id, product_id)
        );
        INSERT INTO reviews (product_id, customer_id, rating) VALUES (2, 1, 5);
        SELECT review_id, product_id, customer_id, rating, comment FROM reviews;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

        | review_id | product_id | customer_id | rating | comment |
        | --- | --- | --- | --- | --- |
        | 1 | 2 | 1 | 5 | *NULL* |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        CREATE TABLE reviews (
          review_id   INTEGER PRIMARY KEY,
          product_id  INTEGER NOT NULL REFERENCES products (product_id),
          customer_id INTEGER NOT NULL REFERENCES customers (customer_id),
          rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
          comment     TEXT,
          written_on  DATE NOT NULL DEFAULT CURRENT_DATE,
          UNIQUE (customer_id, product_id)
        );
        INSERT INTO reviews (product_id, customer_id, rating) VALUES (2, 1, 5);
        SELECT review_id, product_id, customer_id, rating, comment FROM reviews;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 1 row.</p>

        | review_id | product_id | customer_id | rating | comment |
        | --- | --- | --- | --- | --- |
        | 1 | 2 | 1 | 5 | *NULL* |
        <!-- /result -->

    (The date column is left out of the `SELECT` only so that this page shows the same result every day.)

**18.2** Which of these inserts into `stock (item VARCHAR(10), qty INTEGER CHECK (qty >= 0))` succeed on PostgreSQL:
`('pen', 0)`, `('cup', NULL)`, `('lamp', -2)`, `('a very long item name', 1)`?

??? success "Answer"
    The first two. `0` passes `qty >= 0`; NULL passes any `CHECK`; `-2` fails the check; the long name is over 10
    characters. On SQLite (not `STRICT`), the long name would also go in.

    <!-- sql pg error -->
    ```sql
    CREATE TABLE stock (item VARCHAR(10), qty INTEGER CHECK (qty >= 0));
    INSERT INTO stock VALUES ('pen', 0), ('cup', NULL);
    INSERT INTO stock VALUES ('a very long item name', 1);
    ```

    <!-- result -->
    <p class="sql-tested sql-error">PostgreSQL 16: error: <code>value too long for type character varying(10)</code></p>
    <!-- /result -->

**18.3** A table of customer emails must not hold the same email twice, but many customers have none. Which
constraint does that, and does it allow several NULL emails?

??? success "Answer"
    `UNIQUE (email)`. Yes: on PostgreSQL and SQLite (and MySQL, Oracle), several NULLs are allowed because NULLs are
    not equal to each other. On SQL Server only one NULL is allowed, unless you use a filtered unique index
    (`WHERE email IS NOT NULL`).

    <!-- sql -->
    ```sql
    CREATE TABLE contacts (customer_id INTEGER PRIMARY KEY, email VARCHAR(100) UNIQUE);
    INSERT INTO contacts (customer_id, email)
    SELECT customer_id, email FROM customers;
    SELECT COUNT(*) AS customers, COUNT(email) AS with_email FROM contacts;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | customers | with_email |
    | --- | --- |
    | 10 | 8 |
    <!-- /result -->

    All ten customers went in, two of them without an email.

**Next:** [19. Data modelling](19-Data-Modelling.md).
