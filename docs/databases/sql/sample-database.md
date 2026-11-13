# The sample database: a small shop

*Every example in this course runs on the same small, made-up shop: its customers, products, orders, staff,
logins, payments and website visits. It is small enough to read in full on this page, so you can check any result by eye. The odd cases that
trip people up in tests are in it on purpose: missing emails, an order with no customer, a customer with no orders,
tied prices and salaries, and a duplicated row.*

!!! abstract "On this page"
    - the eight tables, every column, and how they connect
    - a playground: real PostgreSQL in your browser, loaded with this database
    - every row of every table
    - how to load it on your own computer, on PostgreSQL or SQLite, in a few minutes
    - the traps built into the data, so you know them before you meet them

## The tables { #tables }

| Table | One row is | Key | Rows |
| --- | --- | --- | --- |
| `customers` | a customer | `customer_id` | 10 |
| `products` | a product for sale | `product_id` | 11 |
| `orders` | one order, placed on one day | `order_id` | 20 |
| `order_items` | one product in one order, with its quantity and the price paid | `order_id` + `product_id` | 30 |
| `employees` | a member of staff; `manager_id` points at another employee | `employee_id` | 12 |
| `logins` | a customer signing in on a day | none (it has a duplicate) | 15 |
| `payments` | one attempt to pay for an order (paid, failed or refunded) | `payment_id` | 22 |
| `page_views` | one page shown to one visitor on the website | `view_id` | 20 |

How they connect:

```text
customers 1 ──< orders 1 ──< order_items >── 1 products
  1  1                  1                      1
  │  └──< logins        └──< payments          │
  └──< page_views >────────────────────────────┘ (product_id, when the page shows a product)

employees 1 ──< employees (manager_id)
```

Read `1 ──<` as "one of these has many of those": one customer has many orders, one order has many items, one product
appears in many items. `orders.customer_id` points at `customers.customer_id`, and `order_items` points at both
`orders` and `products`. `employees.manager_id` points back into `employees`: each employee's manager is another
employee. `payments.order_id` points at `orders`, and `page_views` points at `customers` (when the visitor is signed in)
and at `products` (when the page shows one).

## Every column { #columns }

| Table | Column | Type | Can be NULL? | Meaning |
| --- | --- | --- | --- | --- |
| customers | `customer_id` | INTEGER, primary key | no | the customer's number |
| customers | `name` | VARCHAR(50) | no | full name; two customers share one |
| customers | `email` | VARCHAR(100) | **yes** | missing for customers 3 and 8 |
| customers | `city` | VARCHAR(50) | **yes** | missing for customer 5 |
| customers | `country` | VARCHAR(50) | no | |
| customers | `signup_date` | DATE | no | the day the account was opened |
| products | `product_id` | INTEGER, primary key | no | |
| products | `name` | VARCHAR(50) | no | |
| products | `category` | VARCHAR(20) | **yes** | Home, Kitchen or Office; the gift card has none |
| products | `price` | NUMERIC(8,2) | no | today's price |
| orders | `order_id` | INTEGER, primary key | no | 101 to 120 |
| orders | `customer_id` | INTEGER, refers to customers | **yes** | missing for the guest order 108 |
| orders | `order_date` | DATE | no | the day the order was placed |
| orders | `status` | VARCHAR(10) | no | shipped, pending or cancelled |
| order_items | `order_id` | INTEGER, refers to orders | no | part of the key |
| order_items | `product_id` | INTEGER, refers to products | no | part of the key |
| order_items | `quantity` | INTEGER | no | |
| order_items | `unit_price` | NUMERIC(8,2) | no | the price paid, which can differ from today's price |
| employees | `employee_id` | INTEGER, primary key | no | |
| employees | `name` | VARCHAR(50) | no | |
| employees | `department` | VARCHAR(20) | no | Management, Engineering, Sales or Support |
| employees | `manager_id` | INTEGER, refers to employees | **yes** | missing for the top manager |
| employees | `salary` | INTEGER | **yes** | missing for the newest employee |
| employees | `hire_date` | DATE | no | |
| logins | `customer_id` | INTEGER, refers to customers | no | there is no key: one row is repeated |
| logins | `login_date` | DATE | no | |
| payments | `payment_id` | INTEGER, primary key | no | |
| payments | `order_id` | INTEGER, refers to orders | no | an order can have several payments, or none |
| payments | `paid_at` | TIMESTAMP | no | date and time of the attempt |
| payments | `method` | VARCHAR(10) | **yes** | card, paypal or gift; unknown for payment 10 |
| payments | `amount` | NUMERIC(8,2) | no | negative for a refund |
| payments | `status` | VARCHAR(10) | no | paid, failed or refunded |
| page_views | `view_id` | INTEGER, primary key | no | |
| page_views | `visitor_id` | VARCHAR(10) | no | the browser's id, v1 to v5 |
| page_views | `customer_id` | INTEGER, refers to customers | **yes** | missing while the visitor is not signed in |
| page_views | `viewed_at` | TIMESTAMP | no | date and time the page was shown |
| page_views | `page` | VARCHAR(10) | no | home, product, cart, checkout or thanks (the page after paying) |
| page_views | `product_id` | INTEGER, refers to products | **yes** | only on product and cart pages |

## Try it: the playground { #playground }

This box runs **real PostgreSQL inside your browser**, already loaded with every table on this page. Type any query
and press **Run** (or Ctrl+Enter, Cmd+Enter on a Mac). Each run starts again from the same data, so you cannot break
anything: try `INSERT`, `UPDATE` or `DELETE` too. The first run on a page takes a few seconds while PostgreSQL loads
(about 5 MB, from this site only); after that each run takes milliseconds. It is PostgreSQL 18, a newer version than
the PostgreSQL 16 the course's printed results come from; every result in the course is the same on both.

<div class="sqlplay-free" data-db="shop" data-start="SELECT o.order_id, c.name, o.order_date, o.status
FROM orders o
LEFT JOIN customers c ON c.customer_id = o.customer_id
ORDER BY o.order_id;
"></div>

Every example in the course has a **Run this** button under it that opens the same kind of box with the example
in it, and every exercise has a **Try it here** box with a **Check** button that compares your result with the
answer's.

## Describe a table from the Run box { #describe }

"Which columns does `orders` have, and of what type?" Some databases answer `DESCRIBE orders` (that is MySQL), and the
`psql` command line answers `\d orders`. Neither works here: PostgreSQL has no `DESCRIBE`, and `\d` is a command of
the `psql` program, not SQL, so a Run box (or any editor that only sends SQL) rejects it.

The SQL way is to ask the database's own catalogue, **`information_schema`**: a set of read-only views, part of the
SQL standard, that describe every table and column. It works in PostgreSQL, MySQL and SQL Server.

**Task:** Describe the `orders` table: each column's name, type, maximum length and whether it may be NULL, in column order.

<!-- sql pg -->
```sql
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'orders'          -- the table's name, in lower case
ORDER BY ordinal_position;             -- the order the columns were created in
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

| column_name | data_type | character_maximum_length | is_nullable |
| --- | --- | --- | --- |
| order_id | integer | *NULL* | NO |
| customer_id | integer | *NULL* | YES |
| order_date | date | *NULL* | NO |
| status | character varying | 10 | NO |
<!-- /result -->

`data_type` is the type, `character_maximum_length` the length of a `VARCHAR`, and `is_nullable` says whether the
column may hold NULL. Add `column_default` to see default values. Which tables are there at all:

**Task:** List the tables of the database, alphabetically.

<!-- sql pg -->
```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'          -- leave out the system's own tables
ORDER BY table_name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 8 rows.</p>

| table_name |
| --- |
| customers |
| employees |
| logins |
| order_items |
| orders |
| page_views |
| payments |
| products |
<!-- /result -->

SQLite has no `information_schema`. It describes a table with `PRAGMA table_info(orders)`, which can also be read as
a table:

**Task:** Describe the `orders` table on SQLite: each column's name, type, NOT NULL flag and key flag.

<!-- sql sqlite -->
```sql
SELECT name, type, "notnull", pk
FROM pragma_table_info('orders')
ORDER BY cid;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 4 rows.</p>

| name | type | notnull | pk |
| --- | --- | --- | --- |
| order_id | INTEGER | 0 | 1 |
| customer_id | INTEGER | 0 | 0 |
| order_date | DATE | 1 | 0 |
| status | VARCHAR(10) | 1 | 0 |
<!-- /result -->

And the quickest look of all, on any database, is a few rows: the column names come with them.

**Task:** Show the first 3 orders, all columns, to see what the table looks like.

<!-- sql -->
```sql
SELECT *
FROM orders
ORDER BY order_id
LIMIT 3;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| order_id | customer_id | order_date | status |
| --- | --- | --- | --- |
| 101 | 1 | 2026-01-03 | shipped |
| 102 | 2 | 2026-01-03 | shipped |
| 103 | 1 | 2026-01-15 | shipped |
<!-- /result -->

In a test, the task text already gives each table's `CREATE TABLE`; read it there. In the Run boxes of this course,
the **Show tables** button lists the tables too.

## Load it yourself { #load }

The whole database is one file, [shop.sql](shop.sql), that runs unchanged on both databases.

=== "SQLite (easiest)"

    1. Install SQLite: on a Mac it is already there (type `sqlite3` in Terminal); on Windows download the
       "command-line tools" from [sqlite.org/download.html](https://sqlite.org/download.html).
    2. Save [shop.sql](shop.sql) into a folder, open a terminal in that folder and run:

        ```text
        sqlite3 shop.db < shop.sql
        sqlite3 shop.db
        ```

    3. At the `sqlite>` prompt type `.headers on` and `.mode box`, then any query, ending with `;`.

=== "PostgreSQL"

    1. Install PostgreSQL from [postgresql.org/download](https://www.postgresql.org/download/) (on a Mac,
       Postgres.app is the simplest).
    2. Make an empty database and load the file:

        ```text
        createdb shop
        psql -d shop -f shop.sql
        psql -d shop
        ```

    3. Type any query, ending with `;`. `\dt` lists the tables, `\d orders` shows one table's columns, `\q` quits.

=== "No install"

    Use [the playground](#playground) on this page: PostgreSQL running in your browser, already loaded with
    [shop.sql](shop.sql).

## Every row { #rows }

### customers

<!-- sql -->
```sql
SELECT * FROM customers ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

| customer_id | name | email | city | country | signup_date |
| --- | --- | --- | --- | --- | --- |
| 1 | Ana Silva | ana@example.com | Toronto | Canada | 2025-11-03 |
| 2 | Ben Okafor | ben@example.com | Lagos | Nigeria | 2025-12-10 |
| 3 | Chen Wei | *NULL* | Shanghai | China | 2026-01-05 |
| 4 | Dana Kim | dana@example.com | Seoul | South Korea | 2026-01-05 |
| 5 | Eli Cohen | eli@example.com | *NULL* | Israel | 2026-01-20 |
| 6 | Farah Haddad | farah@example.com | Toronto | Canada | 2026-02-02 |
| 7 | Gus Novak | gus@example.com | Prague | Czechia | 2026-02-14 |
| 8 | Hana Sato | *NULL* | Osaka | Japan | 2026-02-28 |
| 9 | Ivan Petrov | ivan@example.com | Toronto | Canada | 2026-03-03 |
| 10 | Ana Silva | ana.silva@example.com | Lisbon | Portugal | 2026-03-15 |
<!-- /result -->

Two customers are both called **Ana Silva** (1 and 10): they are different people, in different cities. Chen Wei
and Hana Sato have no email (`NULL`), and Eli Cohen has no city. Ivan Petrov (9) has never ordered anything.

### products

<!-- sql -->
```sql
SELECT * FROM products ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

| product_id | name | category | price |
| --- | --- | --- | --- |
| 1 | Desk lamp | Home | 24.50 |
| 2 | Notebook | Office | 3.25 |
| 3 | Fountain pen | Office | 18.00 |
| 4 | Coffee mug | Kitchen | 8.75 |
| 5 | Tea kettle | Kitchen | 32.00 |
| 6 | Office chair | Office | 149.00 |
| 7 | Monitor stand | Office | 32.00 |
| 8 | Plant pot | Home | 12.25 |
| 9 | Wall clock | Home | 24.50 |
| 10 | Gift card | *NULL* | 25.00 |
| 11 | Bookend | Home | 9.50 |
<!-- /result -->

The tea kettle and the monitor stand cost the same (32.00), and so do the desk lamp and the wall clock (24.50): ties
for every "top N" question. The gift card has no category. The bookend (11) has never been sold.

### orders

<!-- sql -->
```sql
SELECT * FROM orders ORDER BY order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 20 rows.</p>

| order_id | customer_id | order_date | status |
| --- | --- | --- | --- |
| 101 | 1 | 2026-01-03 | shipped |
| 102 | 2 | 2026-01-03 | shipped |
| 103 | 1 | 2026-01-15 | shipped |
| 104 | 3 | 2026-01-20 | cancelled |
| 105 | 4 | 2026-01-28 | shipped |
| 106 | 2 | 2026-02-02 | shipped |
| 107 | 5 | 2026-02-02 | shipped |
| 108 | *NULL* | 2026-02-10 | shipped |
| 109 | 6 | 2026-02-14 | shipped |
| 110 | 1 | 2026-02-20 | shipped |
| 111 | 7 | 2026-02-21 | shipped |
| 112 | 4 | 2026-03-01 | shipped |
| 113 | 2 | 2026-03-05 | cancelled |
| 114 | 8 | 2026-03-09 | shipped |
| 115 | 1 | 2026-03-18 | shipped |
| 116 | 6 | 2026-03-22 | pending |
| 117 | 10 | 2026-03-25 | shipped |
| 118 | 3 | 2026-04-01 | shipped |
| 119 | 5 | 2026-04-02 | pending |
| 120 | 1 | 2026-04-05 | shipped |
<!-- /result -->

Order 108 has no customer: a guest checkout, `customer_id` is `NULL`. Two orders are cancelled and two are pending.
Ana Silva (1) ordered in every month from January to April. Orders 101 and 102, and 106 and 107, share a day.

### order_items

<!-- sql -->
```sql
SELECT * FROM order_items ORDER BY order_id, product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 30 rows.</p>

| order_id | product_id | quantity | unit_price |
| --- | --- | --- | --- |
| 101 | 1 | 1 | 24.50 |
| 101 | 2 | 3 | 3.25 |
| 102 | 6 | 1 | 149.00 |
| 103 | 2 | 5 | 3.25 |
| 103 | 4 | 2 | 8.75 |
| 104 | 5 | 1 | 32.00 |
| 105 | 2 | 2 | 3.25 |
| 105 | 3 | 1 | 18.00 |
| 106 | 1 | 1 | 24.50 |
| 106 | 7 | 1 | 32.00 |
| 107 | 8 | 3 | 12.25 |
| 108 | 10 | 2 | 25.00 |
| 109 | 4 | 4 | 8.75 |
| 109 | 5 | 1 | 30.00 |
| 110 | 2 | 10 | 3.25 |
| 111 | 8 | 1 | 12.25 |
| 111 | 9 | 1 | 24.50 |
| 112 | 6 | 1 | 149.00 |
| 112 | 7 | 1 | 32.00 |
| 113 | 3 | 2 | 18.00 |
| 114 | 1 | 2 | 24.50 |
| 115 | 4 | 2 | 8.75 |
| 115 | 5 | 1 | 32.00 |
| 116 | 10 | 1 | 25.00 |
| 117 | 2 | 5 | 3.25 |
| 117 | 3 | 1 | 18.00 |
| 117 | 4 | 1 | 8.75 |
| 118 | 1 | 1 | 24.50 |
| 119 | 8 | 2 | 12.25 |
| 120 | 6 | 1 | 139.00 |
<!-- /result -->

`unit_price` is the price actually paid, which is not always today's price in `products`: the kettle sold for 30.00
in order 109 and the chair for 139.00 in order 120. **Revenue is always `quantity * unit_price` from
`order_items`**, never the price in `products`.

### employees

<!-- sql -->
```sql
SELECT * FROM employees ORDER BY employee_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 12 rows.</p>

| employee_id | name | department | manager_id | salary | hire_date |
| --- | --- | --- | --- | --- | --- |
| 1 | Maya Rossi | Management | *NULL* | 180000 | 2019-04-01 |
| 2 | Tom Becker | Engineering | 1 | 140000 | 2020-01-15 |
| 3 | Priya Nair | Engineering | 2 | 120000 | 2021-03-01 |
| 4 | Sam Lee | Engineering | 2 | 120000 | 2022-06-15 |
| 5 | Lucia Gomez | Engineering | 2 | 95000 | 2024-09-01 |
| 6 | Omar Aziz | Sales | 1 | 110000 | 2020-07-01 |
| 7 | Nina Berg | Sales | 6 | 70000 | 2023-02-01 |
| 8 | Raj Patel | Sales | 6 | 70000 | 2023-05-15 |
| 9 | Zoe Martin | Sales | 6 | 65000 | 2025-01-06 |
| 10 | Kwame Mensah | Support | 1 | 75000 | 2021-11-01 |
| 11 | Ella Novak | Support | 10 | 52000 | 2024-02-12 |
| 12 | Leo Park | Support | 10 | *NULL* | 2026-01-12 |
<!-- /result -->

Maya Rossi has no manager: she runs the company. Priya Nair and Sam Lee earn the same in Engineering, as do Nina
Berg and Raj Patel in Sales: ties for every ranking question. Leo Park has just joined and his salary is not set yet
(`NULL`).

### logins

<!-- sql -->
```sql
SELECT * FROM logins ORDER BY customer_id, login_date;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 15 rows.</p>

| customer_id | login_date |
| --- | --- |
| 1 | 2026-03-01 |
| 1 | 2026-03-02 |
| 1 | 2026-03-03 |
| 1 | 2026-03-05 |
| 1 | 2026-03-06 |
| 1 | 2026-03-10 |
| 2 | 2026-03-01 |
| 2 | 2026-03-02 |
| 2 | 2026-03-02 |
| 2 | 2026-03-04 |
| 4 | 2026-03-03 |
| 4 | 2026-03-04 |
| 4 | 2026-03-05 |
| 4 | 2026-03-06 |
| 6 | 2026-03-08 |
<!-- /result -->

Customer 2 signed in twice on 2 March: an exact duplicate row. Customer 1 has runs of consecutive days broken by
gaps, and customer 4 signed in four days in a row: the data for "streak" questions in
[chapter 15](15-Classic-Interview-Patterns.md).

### payments

<!-- sql -->
```sql
SELECT * FROM payments ORDER BY payment_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 22 rows.</p>

| payment_id | order_id | paid_at | method | amount | status |
| --- | --- | --- | --- | --- | --- |
| 1 | 101 | 2026-01-03 09:12:00 | card | 34.25 | paid |
| 2 | 102 | 2026-01-03 18:40:00 | card | 149.00 | failed |
| 3 | 102 | 2026-01-03 18:44:00 | paypal | 149.00 | paid |
| 4 | 103 | 2026-01-15 11:05:00 | card | 33.75 | paid |
| 5 | 104 | 2026-01-20 14:30:00 | card | 32.00 | paid |
| 6 | 104 | 2026-01-22 10:00:00 | card | -32.00 | refunded |
| 7 | 105 | 2026-01-28 08:15:00 | paypal | 24.50 | paid |
| 8 | 106 | 2026-02-02 20:01:00 | card | 40.00 | paid |
| 9 | 106 | 2026-02-02 20:02:00 | gift | 16.50 | paid |
| 10 | 107 | 2026-02-02 21:30:00 | *NULL* | 36.75 | paid |
| 11 | 108 | 2026-02-10 12:00:00 | card | 50.00 | paid |
| 12 | 109 | 2026-02-14 16:45:00 | card | 65.00 | paid |
| 13 | 110 | 2026-02-20 09:30:00 | card | 32.50 | paid |
| 14 | 111 | 2026-02-21 13:13:00 | paypal | 36.75 | paid |
| 15 | 112 | 2026-03-01 07:55:00 | card | 181.00 | paid |
| 16 | 114 | 2026-03-09 19:20:00 | card | 49.00 | paid |
| 17 | 115 | 2026-03-18 10:10:00 | card | 49.50 | paid |
| 18 | 117 | 2026-03-25 15:00:00 | paypal | 43.00 | paid |
| 19 | 118 | 2026-04-01 08:00:00 | card | 24.50 | paid |
| 20 | 119 | 2026-04-02 22:10:00 | card | 24.50 | failed |
| 21 | 120 | 2026-04-05 12:30:00 | card | 139.00 | paid |
| 22 | 120 | 2026-04-05 12:30:00 | card | 139.00 | paid |
<!-- /result -->

Each row is one **attempt** to pay, so an order can have several rows, or none:

* Order 102 failed on a card, then was paid by PayPal four minutes later (payments 2 and 3).
* Order 104 was paid and then **refunded** two days later, as a negative amount (payments 5 and 6); the order is
  cancelled.
* Order 106 was paid in two parts, by card and gift card (payments 8 and 9).
* Payment 10 has no `method` (`NULL`): the payment service did not say.
* Order 119 has only a **failed** payment, and orders 113 and 116 have no payment at all.
* Order 120 was charged **twice** at the same second (payments 21 and 22): a double charge, the kind of duplicate a
  data engineer has to find.

### page_views

<!-- sql -->
```sql
SELECT * FROM page_views ORDER BY visitor_id, viewed_at, view_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 20 rows.</p>

| view_id | visitor_id | customer_id | viewed_at | page | product_id |
| --- | --- | --- | --- | --- | --- |
| 1 | v1 | 1 | 2026-04-05 12:00:00 | home | *NULL* |
| 2 | v1 | 1 | 2026-04-05 12:03:10 | product | 6 |
| 3 | v1 | 1 | 2026-04-05 12:10:00 | cart | 6 |
| 4 | v1 | 1 | 2026-04-05 12:29:30 | checkout | *NULL* |
| 5 | v1 | 1 | 2026-04-05 12:30:05 | thanks | *NULL* |
| 6 | v1 | 1 | 2026-04-05 18:45:00 | home | *NULL* |
| 7 | v1 | 1 | 2026-04-05 18:46:00 | product | 1 |
| 8 | v2 | 2 | 2026-04-05 09:00:00 | home | *NULL* |
| 9 | v2 | 2 | 2026-04-05 09:01:00 | product | 5 |
| 10 | v2 | 2 | 2026-04-05 09:01:00 | product | 5 |
| 11 | v2 | 2 | 2026-04-05 09:20:00 | cart | 5 |
| 12 | v2 | 2 | 2026-04-05 09:55:00 | cart | 5 |
| 13 | v3 | *NULL* | 2026-04-05 10:00:00 | home | *NULL* |
| 14 | v3 | *NULL* | 2026-04-05 10:02:00 | product | 5 |
| 15 | v3 | *NULL* | 2026-04-05 10:31:59 | product | 4 |
| 16 | v3 | *NULL* | 2026-04-05 11:02:00 | checkout | *NULL* |
| 17 | v4 | 4 | 2026-04-04 23:50:00 | home | *NULL* |
| 18 | v4 | 4 | 2026-04-05 00:10:00 | product | 9 |
| 19 | v4 | 4 | 2026-04-05 00:12:00 | cart | 9 |
| 20 | v5 | *NULL* | 2026-04-05 14:00:00 | product | 10 |
<!-- /result -->

One row per page shown, on 4 and 5 April 2026. A **visitor** is one browser; `customer_id` is filled in only when
the visitor is signed in, so `v3` and `v5` are guests. The traps:

* **Sessions.** A common rule is "a gap of more than 30 minutes starts a new session". Visitor `v3` has a gap of
  29 min 59 s (same session) and then one of 30 min 1 s (new session); `v1` comes back in the evening.
* **Funnel.** `v1` goes home, product, cart, checkout, thanks (and the order 120 is placed at 12:30); `v2` stops at
  the cart; `v3` reaches checkout without a cart page.
* **A repeated event.** Views 9 and 10 are the same page, for the same visitor, at the same second.
* **Midnight.** Visitor `v4`'s session starts on 4 April and ends on 5 April.

## The traps, in one list { #traps }

| Trap | Where | Chapter |
| --- | --- | --- |
| `NULL` email, city, salary, customer | customers 3, 5, 8; employees 12; order 108 | [6](06-Null-and-Three-Valued-Logic.md) |
| `NOT IN` against a column with a `NULL` | `orders.customer_id` | [6](06-Null-and-Three-Valued-Logic.md), [9](09-Self-Semi-and-Anti-Joins.md) |
| A customer with no orders, a product never sold | customer 9, product 11 | [8](08-Joins-Inner-Left-Right-Full-Cross.md), [9](09-Self-Semi-and-Anti-Joins.md) |
| Ties in "top N" and "Nth highest" | prices, salaries | [13](13-Window-Functions-Ranking.md), [15](15-Classic-Interview-Patterns.md) |
| Two people with the same name | customers 1 and 10 | [7](07-Aggregation-Group-By-Having.md) |
| Price paid differs from today's price | orders 109, 120 | [8](08-Joins-Inner-Left-Right-Full-Cross.md) |
| An exact duplicate row | logins | [22](22-Duplicates-and-Incremental-Loads.md) |
| Joining orders to items multiplies rows | every order with two or more items | [8](08-Joins-Inner-Left-Right-Full-Cross.md) |
| Several payments per order: failed, split, refunded, doubled | payments 2-3, 5-6, 8-9, 21-22 | [Analytics workshop](analytics-workshop.md) |
| Orders with no successful payment | orders 113, 116, 119 | [Analytics workshop](analytics-workshop.md) |
| Sessions split by a 30-minute gap, at the boundary | page_views of `v3` | [Analytics workshop](analytics-workshop.md) |

!!! note "How the results on this site were made"
    Each page starts from a fresh copy of this database. Every query on the page is run on PostgreSQL 16.15 and on
    SQLite 3.53 by a small program in this site's repository (`tools/sqlrun.py`). It writes the real result under the
    query and refuses to publish if the two databases disagree where they should agree. Numbers are shown as
    PostgreSQL prints them: it keeps trailing zeros (`24.50`), where SQLite prints `24.5`.
