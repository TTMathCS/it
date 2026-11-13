# 19. Data modelling

*How to split data into tables decides how easy it is to keep correct and how easy it is to query. Systems that take
orders want every fact stored once (normalised); systems that answer questions want a few wide, simple tables (a
star schema). A data engineer builds the second from the first, so interviews ask about both: normal forms, facts
and dimensions, the grain of a table, and slowly changing dimensions. This chapter builds each one from the shop,
and runs the queries.*

!!! abstract "In this chapter"
    **You will learn:**

    - why storing a fact twice goes wrong: update anomalies
    - first, second and third normal form, in plain words
    - transactional (OLTP) and analytical (OLAP) models, and why they differ
    - a star schema: fact tables, dimension tables, and the date dimension
    - the **grain** of a fact table, and the bug that mixing grains causes
    - slowly changing dimensions, types 1, 2 and 3, with a point-in-time join
    - snowflake schemas, data vault, one big table, and where the medallion layers fit

    **You need:** [1. tables and keys](01-Tables-Rows-and-Keys.md), [7. GROUP BY](07-Aggregation-Group-By-Having.md), [8. joins](08-Joins-Inner-Left-Right-Full-Cross.md) and [18. CREATE TABLE](18-Create-Table-Types-Constraints.md).

## 19.1 Store each fact once { #anomalies }

Imagine the shop kept everything in one wide table, one row per order line with the customer's and product's
details copied in. It is easy to query, and it goes wrong as soon as data changes:

**Task:** Build one wide table of order lines with the customer and product details copied in, then count the rows holding Ana Silva's city.

<!-- sql -->
```sql
CREATE TABLE order_lines_wide AS
SELECT o.order_id, o.order_date, c.customer_id, c.name AS customer_name, c.city,
       p.product_id, p.name AS product_name, p.price AS list_price, i.quantity, i.unit_price
FROM orders o
JOIN customers c   ON c.customer_id = o.customer_id
JOIN order_items i ON i.order_id = o.order_id
JOIN products p    ON p.product_id = i.product_id;
SELECT COUNT(*) AS rows_holding_ana_city
FROM order_lines_wide
WHERE customer_id = 1;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| rows_holding_ana_city |
| --- |
| 8 |
<!-- /result -->

Ana's city is now stored on eight rows. When she moves, all eight must change; miss one and the table contradicts
itself. That is an **update anomaly**. Two more come with it: an **insert anomaly** (a new customer with no orders,
like Ivan, has nowhere to go) and a **delete anomaly** (delete a customer's only order line and you lose the fact
that the customer exists). In the shop's real tables, Ana's city is stored once, in `customers`, and
every order points to her by id.

## 19.2 Normal forms { #normal-forms }

**Normalisation** is splitting tables until each fact is stored once. The first three normal forms cover almost
everything an interview asks:

| Form | Rule, in plain words | Breaking it in the shop would look like |
| --- | --- | --- |
| 1NF | each cell holds one value; no repeating groups of columns | `orders.products = 'lamp, notebook'`, or columns `product1`, `product2`, `product3` |
| 2NF | 1NF, and every non-key column depends on the **whole** key | `order_items (order_id, product_id, quantity, product_name)`: the name depends on `product_id` alone |
| 3NF | 2NF, and non-key columns depend **only** on the key, not on other non-key columns | `orders (order_id, customer_id, customer_city)`: the city depends on the customer, not on the order |

The memory aid: every non-key column depends on "the key, the whole key, and nothing but the key". The shop's six
tables are in third normal form. (There are higher forms, Boyce-Codd, fourth and fifth, that deal with rarer cases;
naming them is usually enough.)

One column in the shop looks like it breaks the rule and does not: `order_items.unit_price` repeats a product's
price. It is not a copy of the current price but a separate fact, the price **paid on that order**, which is why
orders 109 and 120 can differ from today's list price. Telling a real duplicate from a separate fact that looks
the same is most of the skill.

## 19.3 Two kinds of system { #oltp-olap }

| | Transactional (OLTP) | Analytical (OLAP) |
| --- | --- | --- |
| Used for | running the business: take an order, update a stock level | answering questions: revenue by month and country |
| Typical query | read or change a few rows by key, thousands a second | read millions of rows and aggregate them; fewer queries, each much bigger |
| Model | normalised (3NF): many narrow tables | dimensional (star schema): few wide tables, some repetition on purpose |
| Examples | PostgreSQL, MySQL, SQL Server, Oracle behind an application | Snowflake, BigQuery, Redshift, Databricks, Synapse |
| History | usually only the current state | keeps history, often for years |

A data pipeline copies data from the OLTP systems into the analytical one and reshapes it on the way. The rest of
this chapter is that reshaping.

## 19.4 A star schema { #star }

A **star schema** has one **fact table** in the middle, holding measurements of business events (quantities,
amounts), and **dimension tables** around it, holding the descriptions you filter and group by (who, what, when,
where). Built from the shop:

```text
                 dim_date
                    |
  dim_customer -- fact_sales -- dim_product
```

<!-- sql keep -->
```sql
CREATE TABLE dim_customer AS
SELECT customer_id AS customer_key, name, city, country FROM customers;

CREATE TABLE dim_product AS
SELECT product_id AS product_key, name, COALESCE(category, 'Uncategorised') AS category FROM products;

CREATE TABLE dim_date AS
SELECT DISTINCT order_date AS date_key,
       CAST(SUBSTR(CAST(order_date AS TEXT), 1, 4) AS INTEGER) AS year,
       CAST(SUBSTR(CAST(order_date AS TEXT), 6, 2) AS INTEGER) AS month
FROM orders;

CREATE TABLE fact_sales AS
SELECT o.order_id, o.order_date AS date_key, o.customer_id AS customer_key, i.product_id AS product_key,
       i.quantity, i.quantity * i.unit_price AS revenue
FROM orders o
JOIN order_items i ON i.order_id = o.order_id
WHERE o.status = 'shipped';

SELECT COUNT(*) AS fact_rows FROM fact_sales;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| fact_rows |
| --- |
| 26 |
<!-- /result -->

Questions now have one shape: join the fact to the dimensions you need, filter and group by their columns, add up
the facts.

**Task:** From the star schema, show revenue by year, month and category for January and February 2026, highest revenue first within each month.

<!-- sql -->
```sql
SELECT d.year, d.month, p.category, SUM(f.revenue) AS revenue
FROM fact_sales f
JOIN dim_date d    ON d.date_key = f.date_key
JOIN dim_product p ON p.product_key = f.product_key
WHERE d.year = 2026 AND d.month IN (1, 2)
GROUP BY d.year, d.month, p.category
ORDER BY d.year, d.month, revenue DESC, p.category;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 7 rows.</p>

| year | month | category | revenue |
| --- | --- | --- | --- |
| 2026 | 1 | Office | 199.50 |
| 2026 | 1 | Home | 24.50 |
| 2026 | 1 | Kitchen | 17.50 |
| 2026 | 2 | Home | 98.00 |
| 2026 | 2 | Kitchen | 65.00 |
| 2026 | 2 | Office | 64.50 |
| 2026 | 2 | Uncategorised | 50.00 |
<!-- /result -->

Things to notice:

- **The guest order.** Order 108 has no customer, so its `customer_key` is NULL, and a join to `dim_customer` would
  drop it. Warehouses avoid NULL keys: they add an "unknown customer" row (often key 0 or -1) to the dimension and
  point such facts at it, so inner joins never lose revenue.
- **The NULL category** became `'Uncategorised'` in the dimension, for the same reason.
- **The date dimension** usually holds every day of a range, not only days with sales, plus columns such as weekday,
  week, quarter, holiday and fiscal period, so reports never compute them again.
- **Dimensions are denormalised on purpose.** A product's category is a column of `dim_product`, not a separate
  table. Splitting it out again gives a **snowflake schema**: less repetition, more joins.

## 19.5 The grain { #grain }

The **grain** of a fact table is what one row means. Here: "one product line of one shipped order". Decide it first
and write it down; every column must be true at that grain. The classic bug is putting a fact of a coarser grain on
finer rows. Say each order has a 5.00 delivery fee, and someone adds it to the line-level table:

!!! failure "Mixing grains: an order-level fee on line-level rows"
    <!-- sql -->
    ```sql
    SELECT SUM(5.00) AS fees_if_stored_per_line,
           COUNT(DISTINCT order_id) * 5.00 AS fees_actually_charged
    FROM fact_sales;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | fees_if_stored_per_line | fees_actually_charged |
    | --- | --- |
    | 130.00 | 80.00 |
    <!-- /result -->

    Every order with two or three lines now counts its fee two or three times. This is the same multiplication as a
    join fan-out ([8.8](08-Joins-Inner-Left-Right-Full-Cross.md#fan-out)).

Order-level facts belong in an order-level fact table (`fact_orders`, one row per order), or the fee is split across
the lines so that the lines add up to it. Most warehouses have several fact tables at different grains, sharing the
same dimensions ("conformed dimensions"), so that results from different facts can be put side by side.

Fact tables come in three common kinds: **transaction** facts (one row per event, like this one), **periodic
snapshots** (one row per thing per period: stock at the end of each day) and **accumulating snapshots** (one row
per process, updated as it moves on: ordered, shipped, delivered dates on one row).

## 19.6 Slowly changing dimensions { #scd }

Ana moves from Toronto to Vancouver on 15 February 2026. What should a report of "revenue by city" say about her
January orders? It depends on the question, and the dimension's design decides what is possible.

| Type | What happens on a change | Keeps history? |
| --- | --- | --- |
| **Type 1** | overwrite the old value | no: all of Ana's orders move to Vancouver |
| **Type 2** | close the old row and add a new row, with validity dates | yes: each order keeps the city of its time |
| **Type 3** | keep the previous value in an extra column (`previous_city`) | only one step back |

Type 2 is the one interviews ask about. Each version of a customer is its own row, with its own **surrogate key**
(`customer_sk`), the customer's real id (the **business key**, `customer_id`), and the dates it was valid:

<!-- sql keep -->
```sql
CREATE TABLE dim_customer_history (
  customer_sk  INTEGER PRIMARY KEY,
  customer_id  INTEGER NOT NULL,
  city         VARCHAR(50),
  valid_from   DATE NOT NULL,
  valid_to     DATE NOT NULL,          -- the day this version stopped being true (not included)
  is_current   BOOLEAN NOT NULL
);
INSERT INTO dim_customer_history VALUES
  (1, 1, 'Toronto',   '1900-01-01', '2026-02-15', FALSE),
  (2, 1, 'Vancouver', '2026-02-15', '9999-12-31', TRUE),
  (3, 2, 'Lagos',     '1900-01-01', '9999-12-31', TRUE);
SELECT customer_sk, customer_id, city, valid_from, valid_to, is_current
FROM dim_customer_history ORDER BY customer_sk;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| customer_sk | customer_id | city | valid_from | valid_to | is_current |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | Toronto | 1900-01-01 | 2026-02-15 | false |
| 2 | 1 | Vancouver | 2026-02-15 | 9999-12-31 | true |
| 3 | 2 | Lagos | 1900-01-01 | 9999-12-31 | true |
<!-- /result -->

A far-future `valid_to` for the current row (instead of NULL) keeps every lookup a plain range test. A
**point-in-time join** then finds the version that was true on the day of each sale:

**Task:** For customer 1's sales, show each order with the city the customer lived in on the day of the sale.

<!-- sql -->
```sql
SELECT f.order_id, f.date_key, h.city, SUM(f.revenue) AS revenue
FROM fact_sales f
JOIN dim_customer_history h
  ON h.customer_id = f.customer_key
 AND f.date_key >= h.valid_from
 AND f.date_key <  h.valid_to
WHERE f.customer_key = 1
GROUP BY f.order_id, f.date_key, h.city
ORDER BY f.date_key, f.order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| order_id | date_key | city | revenue |
| --- | --- | --- | --- |
| 101 | 2026-01-03 | Toronto | 34.25 |
| 103 | 2026-01-15 | Toronto | 33.75 |
| 110 | 2026-02-20 | Vancouver | 32.50 |
| 115 | 2026-03-18 | Vancouver | 49.50 |
| 120 | 2026-04-05 | Vancouver | 139.00 |
<!-- /result -->

Ana's January orders stay in Toronto; from 20 February they are in Vancouver. With a half-open range
(`>= valid_from AND < valid_to`) every day falls in exactly one version; `BETWEEN` would put 15 February in both. In
a real warehouse the join is usually done once, when the facts are loaded: each fact row stores the `customer_sk`
of the version current at the time, and reports join on that key alone. Building the rows of a type 2 table from
daily snapshots is [practice set B, task 10](31-Practice-Set-B.md#b10); keeping it up to date with each load is in
[chapter 22](22-Duplicates-and-Incremental-Loads.md).

## 19.7 Other models you will hear about { #other-models }

- **Snowflake schema:** a star whose dimensions are normalised into further tables (product → category). Saves
  space, costs joins; less common in modern column stores.
- **Data vault:** for large, changing enterprise sources. **Hubs** hold business keys, **links** hold relationships
  between hubs, **satellites** hold descriptive attributes with load dates. Very good at keeping full history from
  many sources; usually turned into stars for reporting.
- **One big table (OBT):** a single very wide, fully denormalised table per subject. Simple and fast to query in
  column stores, at the cost of repetition and harder changes.
- **Medallion layers:** a way of organising a data lake by quality: **bronze** (raw, as loaded), **silver** (cleaned,
  de-duplicated, conformed), **gold** (modelled for use, often star schemas). It describes stages of a pipeline, not
  a table design, and combines with any of the models above. The Databricks tutorial on this site covers it in
  depth.

## 19.8 Summary { #summary }

- Store each fact once in transactional systems: 1NF one value per cell, 2NF depend on the whole key, 3NF depend
  only on the key. Otherwise updates, inserts and deletes go wrong.
- Analytical systems use star schemas: a fact table of measurements, dimension tables of descriptions.
- State the grain of every fact table; never put a coarser-grain number on finer rows.
- Avoid NULL foreign keys in facts: point them at an "unknown" dimension row.
- SCD type 1 overwrites, type 2 adds a row per version with validity dates, type 3 keeps one previous value. Join
  type 2 with a half-open date range, or store the surrogate key in the fact at load time.

!!! question "Asked aloud: data modelling"
    ??? note "What is normalisation, and why would you denormalise?"
        Splitting data so each fact is stored once, which prevents update, insert and delete anomalies; it suits
        systems that change data constantly. You denormalise for reading: an analytical model repeats descriptions
        (category on every product row) so queries need fewer joins and run faster, and the data changes only
        through controlled loads.

    ??? note "Explain 1NF, 2NF and 3NF in one sentence each."
        1NF: one value per cell, no repeating column groups. 2NF: no column depends on only part of a composite key.
        3NF: no column depends on another non-key column. "The key, the whole key and nothing but the key."

    ??? note "What is the difference between a fact and a dimension?"
        A fact table records events or measurements at a stated grain, with numbers to add up and keys to
        dimensions. A dimension describes the who, what, where and when, with the attributes you filter and group by.
        Facts are long and narrow; dimensions are shorter and wide.

    ??? note "What is the grain of a fact table, and why decide it first?"
        What one row represents, for example one order line. Every measure must be true at that grain; mixing grains
        double counts (an order-level fee on line rows is summed once per line).

    ??? note "Star versus snowflake schema?"
        In a star, each dimension is one denormalised table joined directly to the fact. In a snowflake, dimensions
        are normalised into sub-tables. Stars mean simpler, faster queries; snowflakes save space and keep
        hierarchies in one place.

    ??? note "Describe SCD type 2. What columns does the table need?"
        Each change to a tracked attribute closes the current row (sets its end date, clears its current flag) and
        inserts a new row. Columns: a surrogate key per version, the business key, the attributes, `valid_from`,
        `valid_to` (or NULL / far future for current) and often `is_current`. Facts store the surrogate key of the
        version valid when the event happened.

    ??? note "Why use surrogate keys in a warehouse?"
        Business keys from different sources can clash or change; a type 2 dimension needs a different key per
        version; and small integer keys make the large fact table smaller and joins faster.

    ??? note "How do you handle facts that arrive with no matching dimension row?"
        Do not drop them and do not leave the key NULL: point them at an "unknown" member (key -1), or create an
        "inferred" dimension row with only the business key and fill in its attributes when the dimension data
        arrives. Then count and report such rows as a data quality check.

## Practice { #practice }

**19.1** Using the star schema from [section 19.4](#star), revenue by customer country for shipped orders, highest
first. Include the guest order's revenue as `Unknown`. Return `country`, `revenue`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT COALESCE(c.country, 'Unknown') AS country, SUM(f.revenue) AS revenue
    FROM fact_sales f
    LEFT JOIN dim_customer c ON c.customer_key = f.customer_key
    GROUP BY COALESCE(c.country, 'Unknown')
    ORDER BY revenue DESC, country;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | country | revenue |
    | --- | --- |
    | Canada | 354.00 |
    | Nigeria | 205.50 |
    | South Korea | 205.50 |
    | Unknown | 50.00 |
    | Japan | 49.00 |
    | Portugal | 43.00 |
    | Czechia | 36.75 |
    | Israel | 36.75 |
    | China | 24.50 |
    <!-- /result -->

    The left join keeps the guest order (gift cards, 50.00) as `Unknown`. With an inner join the total would be 50.00
    short. Adding an "unknown customer" row to `dim_customer` would let an inner join work.

**19.2** Is this table in third normal form? `employees (employee_id, name, department, department_head, salary)`.
If not, how would you split it?

??? success "Answer"
    No. `department_head` depends on `department`, not on the employee: a transitive dependency. If a department's
    head changes, every employee row of that department must change. Split it into `departments (department,
    department_head)` and `employees (employee_id, name, department, salary)`, with `employees.department` a foreign
    key to `departments`.

**19.3** With `dim_customer_history` from [section 19.6](#scd), which city was customer 1 in on 15 February 2026, and
on 14 February? Write one query that answers both.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT q.day, h.city
    FROM (SELECT '2026-02-14' AS day UNION ALL SELECT '2026-02-15') AS q
    JOIN dim_customer_history h
      ON h.customer_id = 1
     AND q.day >= CAST(h.valid_from AS TEXT)
     AND q.day <  CAST(h.valid_to AS TEXT)
    ORDER BY q.day;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | day | city |
    | --- | --- |
    | 2026-02-14 | Toronto |
    | 2026-02-15 | Vancouver |
    <!-- /result -->

    15 February is the first day of the Vancouver version (`valid_from` is included), so it is Vancouver; the 14th is
    Toronto. Comparing as text (`CAST(... AS TEXT)`) works on both databases because the dates are `YYYY-MM-DD`; on
    PostgreSQL alone, `DATE '2026-02-14'` would be the cleaner way to write the days.

**19.4** A fact table has one row per order line and a column `order_discount` copied onto every line of the order.
What goes wrong with `SUM(order_discount)`, and what are two fixes?

??? success "Answer"
    The discount is an order-level fact on line-level rows, so an order with three lines counts its discount three
    times. Fixes: move it to an order-grain fact table (one row per order); or allocate it across the lines (for
    example in proportion to each line's value) so that the lines' shares add up to the order's discount. A quick
    patch in a query, `SUM(DISTINCT ...)`, is wrong too: two orders with the same discount would count once.

**Next:** [20. Transactions and isolation](20-Transactions-and-Isolation.md).
