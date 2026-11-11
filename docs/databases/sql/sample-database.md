# The sample database: a small shop

*Every example in this course runs on the same small, made-up shop: its customers, products, orders, staff and
logins. It is small enough to read in full on this page, so you can check any result by eye. The odd cases that
trip people up in tests are in it on purpose: missing emails, an order with no customer, a customer with no orders,
tied prices and salaries, and a duplicated row.*

!!! abstract "On this page"
    - the six tables and how they connect
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

How they connect:

```text
customers 1 ──< orders 1 ──< order_items >── 1 products
    1                                   
    └──< logins          employees 1 ──< employees (manager_id)
```

Read `1 ──<` as "one of these has many of those": one customer has many orders, one order has many items, one product
appears in many items. `orders.customer_id` points at `customers.customer_id`, and `order_items` points at both
`orders` and `products`. `employees.manager_id` points back into `employees`: each employee's manager is another
employee.

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

    Paste the contents of [shop.sql](shop.sql) into an online SQL playground that runs PostgreSQL or SQLite (search
    for "PostgreSQL online playground" or "SQLite online"), run it once, then run your queries below it. Playgrounds
    come and go, so none is linked here.

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

!!! note "How the results on this site were made"
    Each page starts from a fresh copy of this database. Every query on the page is run on PostgreSQL 16.15 and on
    SQLite 3.53 by a small program in this site's repository (`tools/sqlrun.py`). It writes the real result under the
    query and refuses to publish if the two databases disagree where they should agree. Numbers are shown as
    PostgreSQL prints them: it keeps trailing zeros (`24.50`), where SQLite prints `24.5`.
