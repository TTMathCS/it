# 1. Tables, rows and keys

*Before the first query, the shape of the data. A relational database keeps everything in tables; every row in a
table is one thing of the same kind, and keys tie the tables together. This chapter names the parts, shows the
database refusing bad rows, and gives the words interviewers use: primary key, foreign key, one-to-one,
one-to-many, many-to-many, DDL and DML.*

!!! abstract "In this chapter"
    **You will learn:**

    - tables, rows and columns, and why a table has no built-in order
    - primary keys, including a key made of two columns
    - foreign keys, and how they stop an order for a customer who does not exist
    - one-to-one, one-to-many, many-to-many and a table that points at itself
    - why a name is not a key
    - the families of SQL statements: DDL, DML, DQL, DCL, TCL

    **You need:** nothing. The [sample database](sample-database.md) page shows every row used here.

## 1.1 Tables, rows and columns { #tables }

A **table** holds one kind of thing. In the shop, `customers` holds customers and `products` holds products. Each
**row** is one of those things, and each **column** is one fact about it, with a **type**: a whole number, a piece
of text, a date, a price.

**Task:** Show the first 4 customers by id: id, name, city, country and signup date.

<!-- sql -->
```sql
SELECT customer_id, name, city, country, signup_date
FROM customers
ORDER BY customer_id
LIMIT 4;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| customer_id | name | city | country | signup_date |
| --- | --- | --- | --- | --- |
| 1 | Ana Silva | Toronto | Canada | 2025-11-03 |
| 2 | Ben Okafor | Lagos | Nigeria | 2025-12-10 |
| 3 | Chen Wei | Shanghai | China | 2026-01-05 |
| 4 | Dana Kim | Seoul | South Korea | 2026-01-05 |
<!-- /result -->

Every row of a table has the same columns. A fact that does not apply, or is not known, is stored as **NULL**, the
marker for "no value": customer 5's city is NULL. [Chapter 6](06-Null-and-Three-Valued-Logic.md) is all about it.

The words change from book to book. Rows are also called **records** or **tuples**, columns are **fields** or
**attributes**, and a table is a **relation** (that is where "relational" comes from). They mean the same things.

## 1.2 A table has no order { #no-order }

A table is a **set** of rows, not a list. The database may store and return them in any order it finds fast, and
the order can change after an update, an index, or an upgrade. The only way to get rows in an order is to ask for
it with `ORDER BY` ([chapter 2](02-Select-Where-Order-By-Limit.md)).

!!! tip "Interview tip"
    "Return the first three customers" has no answer until someone says first by what. If a test question says
    "sorted by", the checker will usually compare the order too; if it says nothing, sort anyway (by the key) so your
    answer does not depend on luck. Every query in this course that shows more than one row has an `ORDER BY` for
    that reason.

## 1.3 Primary keys { #primary-key }

A **primary key** is the column (or columns) that tells one row from every other row. It must be **unique** and it
can never be NULL. (SQLite has an old exception: a primary key that is not `INTEGER PRIMARY KEY` accepts NULL
unless the column also says `NOT NULL`.) In `customers` it is `customer_id`, declared in the table's definition:

```sql
CREATE TABLE customers (
  customer_id INTEGER PRIMARY KEY,
  name        VARCHAR(50) NOT NULL,
  ...
);
```

The database enforces it. Adding a second customer number 1 fails on both databases:

<!-- sql error -->
```sql
INSERT INTO customers (customer_id, name, country, signup_date)
VALUES (1, 'Another Ana', 'Canada', '2026-04-10');
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>duplicate key value violates unique constraint "customers_pkey"</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>UNIQUE constraint failed: customers.customer_id</code></p>
<!-- /result -->

The PostgreSQL message names the constraint, `customers_pkey`, a name it made up from the table. (The example is
rolled back after it runs, as every example that changes data in this course is, so the shop stays as it was.)

### A key of two columns { #composite-key }

In `order_items`, one row is one product in one order. Neither column is unique on its own: order 101 has two
products, and product 2 is in many orders. The pair is unique, so the pair is the key:

```sql
CREATE TABLE order_items (
  order_id   INTEGER NOT NULL REFERENCES orders (order_id),
  product_id INTEGER NOT NULL REFERENCES products (product_id),
  quantity   INTEGER NOT NULL,
  unit_price NUMERIC(8,2) NOT NULL,
  PRIMARY KEY (order_id, product_id)
);
```

`NUMERIC(8,2)` is an exact decimal number with up to 8 digits, 2 of them after the point: the right type for money,
because it never rounds 0.10 + 0.20 into 0.30000000000000004 the way a floating-point number can.

A key made of several columns is a **composite key**. It means "the same product cannot appear twice in one order";
buying three notebooks is one row with `quantity` 3. Trying to add product 1 to order 101 a second time fails:

<!-- sql error -->
```sql
INSERT INTO order_items VALUES (101, 1, 1, 24.50);
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>duplicate key value violates unique constraint "order_items_pkey"</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>UNIQUE constraint failed: order_items.order_id, order_items.product_id</code></p>
<!-- /result -->

`logins` has no primary key at all, and that is how it ended up holding the same login twice (customer 2 on
2 March). A table without a key can hold duplicates; finding and removing them is a favourite test question
([chapter 15](15-Classic-Interview-Patterns.md) and [chapter 22](22-Duplicates-and-Incremental-Loads.md)).

## 1.4 Foreign keys { #foreign-key }

`orders.customer_id` says which customer placed the order. It is a **foreign key**: a column whose values must
match the primary key (or a unique column) of a row in the table it refers to, usually another table.

```sql
CREATE TABLE orders (
  order_id    INTEGER PRIMARY KEY,
  customer_id INTEGER REFERENCES customers (customer_id),
  ...
);
```

An order for customer 99, who does not exist, is refused:

<!-- sql error -->
```sql
INSERT INTO orders VALUES (121, 99, '2026-04-06', 'shipped');
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>insert or update on table "orders" violates foreign key constraint "orders_customer_id_fkey"</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>FOREIGN KEY constraint failed</code></p>
<!-- /result -->

!!! warning "SQLite checks foreign keys only when asked"
    SQLite ignores `REFERENCES` unless the connection first runs `PRAGMA foreign_keys = ON;`, and it is off by
    default in the `sqlite3` program and in most libraries. The examples in this course run with it on, which is why
    SQLite refused the row above. PostgreSQL, MySQL (InnoDB) and SQL Server check them by default.

A foreign key can be NULL unless the column says `NOT NULL`. Order 108 was placed by a guest, so its `customer_id`
is NULL, which the key allows:

**Task:** Show orders 107 to 109: order id, customer id, order date and status, by order id.

<!-- sql -->
```sql
SELECT order_id, customer_id, order_date, status
FROM orders
WHERE order_id BETWEEN 107 AND 109
ORDER BY order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| order_id | customer_id | order_date | status |
| --- | --- | --- | --- |
| 107 | 5 | 2026-02-02 | shipped |
| 108 | *NULL* | 2026-02-10 | shipped |
| 109 | 6 | 2026-02-14 | shipped |
<!-- /result -->

That one NULL is behind many wrong answers later: it vanishes from inner joins ([chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md))
and it breaks `NOT IN` ([chapter 9](09-Self-Semi-and-Anti-Joins.md#anti)).

The key also works the other way: you cannot delete customer 1 while orders still point at them.

<!-- sql error -->
```sql
DELETE FROM customers WHERE customer_id = 1;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>update or delete on table "customers" violates foreign key constraint "orders_customer_id_fkey" on table "orders"</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>FOREIGN KEY constraint failed</code></p>
<!-- /result -->

A foreign key can instead say what should happen, with `ON DELETE CASCADE` (delete the orders too) or `ON DELETE
SET NULL`; [chapter 18](18-Create-Table-Types-Constraints.md) shows both.

## 1.5 How tables relate { #relationships }

Four shapes cover almost every database.

**One-to-many.** One customer has many orders; each order has at most one customer. The foreign key sits on the
"many" side: `orders.customer_id`.

**Many-to-many.** An order has many products and a product is in many orders. No single foreign key can say that, so
a third table sits between them, one row per pair: `order_items`. It is called a **junction** (or bridge, or link)
table, and it often carries facts about the pair, here the quantity and the price paid.

<span id="one-to-one"></span>**One-to-one.** Each row on one side has at most one row on the other. The sample shop has no such pair, so here is
a small extra table, made up for this example: `customer_profiles`, with at most one profile per customer.

<!-- sql setup -->
```sql
CREATE TABLE customer_profiles (
  customer_id INTEGER PRIMARY KEY REFERENCES customers (customer_id),
  phone       TEXT NOT NULL,
  language    TEXT NOT NULL
);
INSERT INTO customer_profiles VALUES
  (1, '+1 416 555 0101', 'English'),
  (2, '+234 1 555 0102', 'English'),
  (5, '+972 3 555 0105', 'Hebrew'),
  (10, '+351 21 555 0110', 'Portuguese');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

The trick is in the first line: `customer_id` is the **foreign key** (it must be a real customer) **and** the
**primary key** (it cannot repeat). A foreign key that cannot repeat is what makes the relationship one-to-one. A
second profile for customer 1 is refused:

<!-- sql error -->
```sql
INSERT INTO customer_profiles VALUES (1, '+1 416 555 0199', 'French');
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>duplicate key value violates unique constraint "customer_profiles_pkey"</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>UNIQUE constraint failed: customer_profiles.customer_id</code></p>
<!-- /result -->

The other common way to write it: give the second table its own id, and make the foreign key `UNIQUE`
(`customer_id INTEGER NOT NULL UNIQUE REFERENCES customers (customer_id)`). Without `UNIQUE` it would be one-to-many.

When it is used:

- **Optional details.** Only some customers fill in a profile. In a separate table, the others simply have no row,
  instead of a row full of NULLs in `customers`.
- **Sensitive details.** Salaries, health or identity documents go in their own table, so permissions can hide that
  table while the main one stays readable ([chapter 29](29-Safe-SQL.md)).
- **Large or rarely read columns,** such as a long biography or a photo, so that everyday queries on the main table
  stay small and fast.

In a join it behaves differently from one-to-many: **the row count does not grow.** Joining 10 customers to their
profiles gives at most 10 rows, never more; with a `LEFT JOIN`, the customers without a profile stay, with NULLs:

**Task:** List every customer with their phone and language from the profile table, keeping customers who have no profile, by customer id.

<!-- sql -->
```sql
SELECT c.customer_id, c.name, p.phone, p.language
FROM customers c
LEFT JOIN customer_profiles p ON p.customer_id = c.customer_id
ORDER BY c.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

| customer_id | name | phone | language |
| --- | --- | --- | --- |
| 1 | Ana Silva | +1 416 555 0101 | English |
| 2 | Ben Okafor | +234 1 555 0102 | English |
| 3 | Chen Wei | *NULL* | *NULL* |
| 4 | Dana Kim | *NULL* | *NULL* |
| 5 | Eli Cohen | +972 3 555 0105 | Hebrew |
| 6 | Farah Haddad | *NULL* | *NULL* |
| 7 | Gus Novak | *NULL* | *NULL* |
| 8 | Hana Sato | *NULL* | *NULL* |
| 9 | Ivan Petrov | *NULL* | *NULL* |
| 10 | Ana Silva | +351 21 555 0110 | Portuguese |
<!-- /result -->

Joining the same 10 customers to `orders` (one-to-many) would give one row per order instead. That is why, before
any join, it pays to ask "one-to-one or one-to-many?": it tells you whether the row count can grow and whether a
total can be counted twice ([chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md)).

Strictly, this is "one to zero-or-one": a customer may have no profile. A rule that **every** customer must have
exactly one profile, both ways round, cannot be written with plain keys, because each row would have to exist before
the other; in practice the application creates both rows in one transaction.

**A table that points at itself.** Each employee's `manager_id` is another employee's `employee_id`:

**Task:** List the employees in Management and Sales with their id, name, department and manager's id, by employee id.

<!-- sql -->
```sql
SELECT employee_id, name, department, manager_id
FROM employees
WHERE department IN ('Management', 'Sales')
ORDER BY employee_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| employee_id | name | department | manager_id |
| --- | --- | --- | --- |
| 1 | Maya Rossi | Management | *NULL* |
| 6 | Omar Aziz | Sales | 1 |
| 7 | Nina Berg | Sales | 6 |
| 8 | Raj Patel | Sales | 6 |
| 9 | Zoe Martin | Sales | 6 |
<!-- /result -->

Maya Rossi has no manager (NULL); Omar Aziz reports to her (1); Nina, Raj and Zoe report to Omar (6). Questions such
as "employees who earn more than their manager" join this table to itself ([chapter 9](09-Self-Semi-and-Anti-Joins.md)),
and "everyone below Maya, at any depth" needs a recursive query ([chapter 11](11-CTEs-and-Recursive-CTEs.md#recursive)).

## 1.6 A name is not a key { #name-not-key }

Two different customers are called Ana Silva:

**Task:** Find every customer called Ana Silva: id, name, email and city, by id.

<!-- sql -->
```sql
SELECT customer_id, name, email, city
FROM customers
WHERE name = 'Ana Silva'
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| customer_id | name | email | city |
| --- | --- | --- | --- |
| 1 | Ana Silva | ana@example.com | Toronto |
| 10 | Ana Silva | ana.silva@example.com | Lisbon |
<!-- /result -->

Names repeat, change, and get typed differently. That is why tables use a made-up number as the key, a **surrogate
key**, rather than a fact about the thing (a **natural key**, such as an email or a tax number). Natural keys still
matter: they are what a data engineer matches on when loading data from another system, and they usually get a
`UNIQUE` constraint of their own.

!!! failure "The usual wrong answer"
    "Orders per customer" grouped by `name` adds up both Ana Silvas as one person. Group by `customer_id` and show the
    name beside it. [Chapter 7](07-Aggregation-Group-By-Having.md#group-by-key) runs both queries and shows the
    difference.

## 1.7 The families of SQL statements { #statement-families }

Interviewers sometimes ask for these names.

| Family | Stands for | Statements | Chapters |
| --- | --- | --- | --- |
| DQL | data query language | `SELECT` | 2 to 16 |
| DML | data manipulation language | `INSERT`, `UPDATE`, `DELETE`, `MERGE` | [17](17-Insert-Update-Delete-Merge.md) |
| DDL | data definition language | `CREATE`, `ALTER`, `DROP`, `TRUNCATE` | [18](18-Create-Table-Types-Constraints.md) |
| TCL | transaction control language | `BEGIN`, `COMMIT`, `ROLLBACK`, `SAVEPOINT` | [20](20-Transactions-and-Isolation.md) |
| DCL | data control language | `GRANT`, `REVOKE` | [29](29-Safe-SQL.md) |

Many books count `SELECT` as part of DML; both uses are common. `TRUNCATE` is listed under DDL because it empties
the whole table at once rather than deleting rows one by one; how it behaves inside a transaction depends on the
database.

SQL keywords are not case-sensitive: `select`, `SELECT` and `Select` are the same. This course writes keywords in
capitals so they stand out. Text inside quotes **is** case-sensitive in a comparison on PostgreSQL and SQLite
(`'ana silva'` does not equal `'Ana Silva'`); [chapter 5](05-Text-Functions-and-Pattern-Matching.md) covers this.

## 1.8 Summary { #summary }

- A table holds one kind of thing; a row is one of them; a column is one fact with a type. NULL means "no value".
- Rows have no order. Only `ORDER BY` gives one.
- A primary key is unique and never NULL; it can be one column or several (composite).
- A foreign key must match a key in the table it refers to, or be NULL. SQLite enforces it only with
  `PRAGMA foreign_keys = ON`.
- One-to-one is a foreign key that is also unique (or the primary key), and a join over it never adds rows;
  one-to-many puts the foreign key on the many side; many-to-many needs a junction table; a table can point at
  itself.
- Names are not keys. Group and join by ids.

## Practice { #practice }

**1.1** Name the primary key of each of the six shop tables. Which table has none, and what has that allowed?

??? success "Answer"
    `customers`: `customer_id`. `products`: `product_id`. `orders`: `order_id`. `order_items`: the pair
    `order_id, product_id`. `employees`: `employee_id`. `logins` has none, and it holds a duplicate row (customer 2,
    2 March 2026). The [sample database](sample-database.md#tables) page lists them.

**1.2** Show every line of order 117: the product id, quantity and price paid, by product id.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT product_id, quantity, unit_price
    FROM order_items
    WHERE order_id = 117
    ORDER BY product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | product_id | quantity | unit_price |
    | --- | --- | --- |
    | 2 | 5 | 3.25 |
    | 3 | 1 | 18.00 |
    | 4 | 1 | 8.75 |
    <!-- /result -->

    Three rows, one per product. The order's key appears in all three; together with `product_id` it is unique.

**1.3** Will this run? `INSERT INTO order_items VALUES (120, 99, 1, 5.00);` Say why before you try it.

??? success "Answer"
    No: there is no product 99, and `order_items.product_id` is a foreign key to `products`.

    <!-- sql error -->
    ```sql
    INSERT INTO order_items VALUES (120, 99, 1, 5.00);
    ```

    <!-- result -->
    <p class="sql-tested sql-error">PostgreSQL 16: error: <code>insert or update on table "order_items" violates foreign key constraint "order_items_product_id_fkey"</code></p>
    <p class="sql-tested sql-error">SQLite 3.53: error: <code>FOREIGN KEY constraint failed</code></p>
    <!-- /result -->

**1.4** Which relationship shape is each of these: customers and logins; products and orders; employees and their
managers?

??? success "Answer"
    Customers and logins: one-to-many (one customer, many logins; the foreign key is `logins.customer_id`). Products
    and orders: many-to-many, through the junction table `order_items`. Employees and managers: one-to-many inside one
    table (one manager, many reports), through `employees.manager_id`.

**1.5** Show the employees who report to Tom Becker (employee 2): id, name, salary, by id.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT employee_id, name, salary
    FROM employees
    WHERE manager_id = 2
    ORDER BY employee_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | employee_id | name | salary |
    | --- | --- | --- |
    | 3 | Priya Nair | 120000 |
    | 4 | Sam Lee | 120000 |
    | 5 | Lucia Gomez | 95000 |
    <!-- /result -->

    Finding them by Tom's name instead of his id needs a join of the table with itself, the subject of
    [chapter 9](09-Self-Semi-and-Anti-Joins.md). The name goes in **single** quotes; `"Tom Becker"` in double quotes
    means a column called Tom Becker, and PostgreSQL answers `column "Tom Becker" does not exist`
    ([2.3](02-Select-Where-Order-By-Limit.md#quotes)):

    <!-- sql -->
    ```sql
    SELECT e.employee_id, e.name, e.salary
    FROM employees e
    JOIN employees m ON e.manager_id = m.employee_id
    WHERE m.name = 'Tom Becker'
    ORDER BY e.employee_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | employee_id | name | salary |
    | --- | --- | --- |
    | 3 | Priya Nair | 120000 |
    | 4 | Sam Lee | 120000 |
    | 5 | Lucia Gomez | 95000 |
    <!-- /result -->

**Next:** [2. SELECT, WHERE, ORDER BY, LIMIT](02-Select-Where-Order-By-Limit.md).
