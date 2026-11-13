# 23. Data quality checks

*Bad data rarely announces itself. A load runs without an error and a report is quietly wrong, because a column was
empty, an id appeared twice, a date was in the wrong format or yesterday's file never arrived. This chapter writes
the checks that catch those problems in SQL, puts them together into one test query, and splits incoming rows into
good and rejected.*

!!! abstract "In this chapter"
    **You will learn:**

    - the kinds of check: completeness, uniqueness, validity, references, consistency, volume and freshness
    - the habit that makes checks easy to automate: **a check returns the bad rows; no rows means it passed**
    - testing text that should be a number or a date, on PostgreSQL and on SQLite
    - one query that runs every check and reports a count for each
    - splitting a batch into clean rows and rejected rows with a reason
    - reconciling a source and a target, and profiling a column you have never seen

    **You need:** [chapter 5](05-Text-Functions-and-Pattern-Matching.md), [chapter 9](09-Self-Semi-and-Anti-Joins.md)
    (anti-joins) and [chapter 12](12-Set-Operations.md).

## 23.1 A batch to check { #batch }

Data usually lands first in a **staging** table, with every column as text exactly as it came from the file. Only
after the checks does it go into the real table with real types. This batch has one problem of each common kind
(the comments say which; the checks have to find them without the comments).

<!-- sql setup -->
```sql
CREATE TABLE stg_orders (
  order_id    VARCHAR(10),
  customer_id VARCHAR(10),
  order_date  VARCHAR(20),
  amount      VARCHAR(20),
  status      VARCHAR(20)
);
INSERT INTO stg_orders VALUES
  ('201', '1',  '2026-06-01', '25.00', 'shipped'),
  ('202', '2',  '2026-06-01', '12.5',  'Shipped '),   -- capital letter, trailing space
  ('203', NULL, '2026-06-02', '40.00', 'shipped'),    -- no customer
  ('204', '99', '2026-06-02', '18.00', 'pending'),    -- customer 99 does not exist
  ('205', '3',  '2026-06-31', '9.99',  'shipped'),    -- 31 June
  ('206', '4',  '2026-06-03', '12abc', 'shipped'),    -- not a number
  ('206', '4',  '2026-06-03', '12.00', 'shipped'),    -- order id twice
  ('207', '5',  '2026-06-04', '-5.00', 'refunded'),   -- negative, unknown status
  ('208', '6',  '03/06/2026', '30.00', 'shipped');    -- wrong date format
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Every check below is written the same way: **it returns the rows that fail**. A check that returns no rows has
passed. This makes every check look alike, and a pipeline can run them all and stop when any returns rows. dbt's
tests work exactly this way.

## 23.2 Completeness: missing values { #completeness }

`COUNT(*)` counts rows; `COUNT(column)` counts non-NULL values. The difference is the number of NULLs:

**Task:** For `stg_orders`, count all rows and the missing values in each column.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT COUNT(*)                      AS total_rows,
           COUNT(*) - COUNT(order_id)    AS missing_order_id,
           COUNT(*) - COUNT(customer_id) AS missing_customer_id,
           COUNT(*) - COUNT(order_date)  AS missing_order_date,
           COUNT(*) - COUNT(amount)      AS missing_amount
    FROM stg_orders;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | total_rows | missing_order_id | missing_customer_id | missing_order_date | missing_amount |
    | --- | --- | --- | --- | --- |
    | 9 | 0 | 1 | 0 | 0 |
    <!-- /result -->

Files often say "missing" in other ways: an empty string, `'N/A'`, `'null'`, spaces. Count those too, or turn them
into NULL while loading with `NULLIF(TRIM(x), '')` ([chapter 4](04-Expressions-Case-Numbers-Dates-Cast.md#coalesce-nullif)).

## 23.3 Uniqueness { #uniqueness }

The key must appear once. As a check, return the keys that do not:

**Task:** List the order ids that appear more than once in `stg_orders`, with how many copies.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT order_id, COUNT(*) AS copies
    FROM stg_orders
    GROUP BY order_id
    HAVING COUNT(*) > 1;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | order_id | copies |
    | --- | --- |
    | 206 | 2 |
    <!-- /result -->

Order 206 is in the file twice with different amounts, so this is not a harmless exact copy: someone must decide
which is right ([chapter 22](22-Duplicates-and-Incremental-Loads.md) shows how to keep one).

## 23.4 Validity: types, formats, ranges, allowed values { #validity }

### Text that should be a number { #is-number }

Casting `'12abc'` fails on PostgreSQL and quietly gives 12 on SQLite ([chapter 4](04-Expressions-Case-Numbers-Dates-Cast.md#cast)),
so test the text before casting. PostgreSQL 16 can ask directly whether a value is valid for a type, and it has
regular expressions. A test that runs on both: strip every digit, dot and minus sign from the ends, and see if
anything is left.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT order_id, amount
    FROM stg_orders
    WHERE NOT pg_input_is_valid(amount, 'numeric');
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

    | order_id | amount |
    | --- | --- |
    | 206 | 12abc |
    <!-- /result -->

=== "Both databases"

    <!-- sql same -->
    ```sql
    SELECT order_id, amount
    FROM stg_orders
    WHERE TRIM(amount, '0123456789.-') <> '';
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 1 row.</p>

    | order_id | amount |
    | --- | --- |
    | 206 | 12abc |
    <!-- /result -->

The portable test is rougher: it would let `'1.2.3'`, `'5-'`, `'.'` or an empty string through, and on
PostgreSQL the later `CAST` would then fail. On PostgreSQL a regular expression is exact:
`amount !~ '^-?[0-9]+(\.[0-9]+)?$'`. SQLite has no regular expressions built in.

### Text that should be a date { #is-date }

Two rows have bad dates: 31 June does not exist, and `'03/06/2026'` is in the wrong format. The format matters more
than it looks. PostgreSQL happily reads `'03/06/2026'` as a date: with its default setting (`DateStyle` = `ISO, MDY`)
that is **6 March**, while the file probably meant 3 June. So check the shape as well as the value.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT order_id, order_date
    FROM stg_orders
    WHERE order_date !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
       OR NOT pg_input_is_valid(order_date, 'date');
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | order_id | order_date |
    | --- | --- |
    | 205 | 2026-06-31 |
    | 208 | 03/06/2026 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    SELECT order_id, order_date
    FROM stg_orders
    WHERE date(order_date) IS NOT order_date;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 2 rows.</p>

    | order_id | order_date |
    | --- | --- |
    | 205 | 2026-06-31 |
    | 208 | 03/06/2026 |
    <!-- /result -->

The SQLite test uses a quirk on purpose: `date()` returns NULL for text it cannot read, and turns `'2026-06-31'`
into `'2026-07-01'`. Either way the result differs from the input, so `IS NOT` (which treats NULL as a value) flags
it. A valid `YYYY-MM-DD` date comes back unchanged.

### Allowed values { #allowed-values }

**Task:** List the staged orders whose status is not pending, shipped or cancelled.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT order_id, status
    FROM stg_orders
    WHERE status NOT IN ('pending', 'shipped', 'cancelled');
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | order_id | status |
    | --- | --- |
    | 202 | Shipped  |
    | 207 | refunded |
    <!-- /result -->

Two rows fail, for different reasons: `'refunded'` is a status nobody planned for (ask the business), and
`'Shipped '` is a real status written badly (clean it: `LOWER(TRIM(status))`). Keep the two apart; the first needs a
person, the second a fix in the load.

### Ranges { #ranges }

Only test the range of values that are valid numbers, or the cast fails first:

**Task:** List the staged orders whose amount is a valid number but not above 0.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT order_id, amount
    FROM stg_orders
    WHERE TRIM(amount, '0123456789.-') = ''
      AND CAST(amount AS NUMERIC(10,2)) <= 0;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | order_id | amount |
    | --- | --- |
    | 207 | -5.00 |
    <!-- /result -->

`AND` does not promise to test its left side first in SQL. Here it works on both databases, but the safe way to
cast only the valid rows is a `CASE`, which does test in order:
`CASE WHEN TRIM(amount, '0123456789.-') = '' THEN CAST(amount AS NUMERIC(10,2)) END`.

## 23.5 References: orphans { #orphans }

Every `customer_id` should exist in `customers`. The anti-join finds the ones that do not
([chapter 9](09-Self-Semi-and-Anti-Joins.md)). The staging column is text and the key is a number, so cast it;
PostgreSQL refuses to compare text with an integer.

**Task:** List the staged orders whose customer id does not exist in `customers`.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT s.order_id, s.customer_id
    FROM stg_orders s
    LEFT JOIN customers c ON c.customer_id = CAST(s.customer_id AS INTEGER)
    WHERE s.customer_id IS NOT NULL
      AND c.customer_id IS NULL;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | order_id | customer_id |
    | --- | --- |
    | 204 | 99 |
    <!-- /result -->

Order 204 points at customer 99. The `IS NOT NULL` keeps a missing customer (order 203) out of this check: that is a
completeness problem, already counted in [23.2](#completeness), and reporting it twice would make the failure counts
add up wrong.

## 23.6 Consistency, volume and freshness { #consistency }

**Consistency** checks compare columns or tables that must agree: a ship date not before the order date, line items
that add up to the order total, a country that matches the city. In the shop, every shipped order must have at
least one item:

**Task:** List the shipped orders that have no items.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT o.order_id, o.status
    FROM orders o
    WHERE o.status = 'shipped'
      AND NOT EXISTS (SELECT 1 FROM order_items oi WHERE oi.order_id = o.order_id);
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

    | order_id | status |
    | --- | --- |
    | *(no rows)* | |
    <!-- /result -->

No rows: the shop passes.

**Volume** checks compare today's row count with what is normal. A file with 40 rows when every other day had 10,000
loaded "successfully" and is almost certainly wrong. Keep a small history of loads:

<!-- sql setup -->
```sql
CREATE TABLE load_history (
  load_date  DATE        NOT NULL,
  table_name VARCHAR(30) NOT NULL,
  row_count  INTEGER     NOT NULL,
  PRIMARY KEY (load_date, table_name)
);
INSERT INTO load_history VALUES
  ('2026-06-01', 'orders', 10120), ('2026-06-02', 'orders', 9870),
  ('2026-06-03', 'orders', 10340), ('2026-06-04', 'orders', 10010),
  ('2026-06-05', 'orders', 40);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

**Task:** Check whether today's load of orders is less than half or more than double the usual size, and show it if so.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT today.load_date, today.row_count,
           ROUND(AVG(earlier.row_count)) AS usual
    FROM load_history today
    JOIN load_history earlier
      ON earlier.table_name = today.table_name
     AND earlier.load_date <  today.load_date
    WHERE today.load_date = '2026-06-05'
      AND today.table_name = 'orders'
    GROUP BY today.load_date, today.row_count
    HAVING today.row_count < 0.5 * AVG(earlier.row_count)
        OR today.row_count > 2.0 * AVG(earlier.row_count);
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | load_date | row_count | usual |
    | --- | --- | --- |
    | 2026-06-05 | 40 | 10085 |
    <!-- /result -->

The thresholds (half and double here) are a choice; a busy shop on a holiday may really halve.

**Freshness** checks ask whether the newest data is recent enough. Here "now" is written in as 5 June so that the
page shows the same result every day; a real check uses `CURRENT_DATE`.

**Task:** Show the newest order date only if it is older than 4 June 2026 (the data is stale).

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT MAX(order_date) AS newest_order
    FROM orders
    HAVING MAX(order_date) < '2026-06-04';
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | newest_order |
    | --- |
    | 2026-04-05 |
    <!-- /result -->

The shop's newest order is from April, so it fails: nothing has arrived for two months. A `HAVING` without
`GROUP BY` filters the single row of the whole-table aggregate, which turns any summary into a pass/fail check.

## 23.7 All checks in one query { #suite }

Each check above can be turned into a count of failing rows. `UNION ALL` puts them together, one row per check. An
aggregate with no `GROUP BY` always returns exactly one row, so a check that passes shows 0 instead of disappearing.

**Task:** Run every check on `stg_orders` in one query: one row per check, with its number of failures.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT 'missing customer_id' AS check_name, COUNT(*) AS failures
    FROM stg_orders WHERE customer_id IS NULL
    UNION ALL
    SELECT 'duplicate order_id', COUNT(*)
    FROM (SELECT order_id FROM stg_orders GROUP BY order_id HAVING COUNT(*) > 1) d
    UNION ALL
    SELECT 'amount not a number', COUNT(*)
    FROM stg_orders WHERE TRIM(amount, '0123456789.-') <> ''
    UNION ALL
    SELECT 'amount not positive', COUNT(*)
    FROM stg_orders
    WHERE CASE WHEN TRIM(amount, '0123456789.-') = '' THEN CAST(amount AS NUMERIC(10,2)) END <= 0
    UNION ALL
    SELECT 'unknown status', COUNT(*)
    FROM stg_orders WHERE LOWER(TRIM(status)) NOT IN ('pending', 'shipped', 'cancelled')
    UNION ALL
    SELECT 'unknown customer', COUNT(*)
    FROM stg_orders s
    LEFT JOIN customers c ON c.customer_id = CAST(s.customer_id AS INTEGER)
    WHERE s.customer_id IS NOT NULL AND c.customer_id IS NULL
    ORDER BY check_name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

    | check_name | failures |
    | --- | --- |
    | amount not a number | 1 |
    | amount not positive | 1 |
    | duplicate order_id | 1 |
    | missing customer_id | 1 |
    | unknown customer | 1 |
    | unknown status | 1 |
    <!-- /result -->

The status check cleans before comparing, so `'Shipped '` passes and only the truly unknown `'refunded'` fails. The
date check is left out only because it is written differently on each database ([23.4](#is-date)).

A pipeline runs a query like this after loading staging and decides: **stop** (some checks must be zero, such as
duplicate keys, which would break the real table), or **warn and continue** (a few unknown statuses). Deciding which
check is which is part of the design, and worth saying in an interview.

## 23.8 Quarantine: split good rows from bad { #quarantine }

Stopping the whole load for one bad row is often too strict. The common alternative is to load the good rows and
put the bad ones in a **rejects** (or quarantine) table with the reason, for someone to fix. One `CASE` gives each
row its first failing reason, or NULL when it passes every check:

**Task:** For every staged order, give its first failing reason, or NULL when it passes every check.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT s.order_id,
           CASE
             WHEN s.order_id IS NULL                              THEN 'missing order_id'
             WHEN (SELECT COUNT(*) FROM stg_orders d
                   WHERE d.order_id = s.order_id) > 1             THEN 'duplicate order_id'
             WHEN s.customer_id IS NULL                           THEN 'missing customer_id'
             WHEN c.customer_id IS NULL                           THEN 'unknown customer'
             WHEN s.order_date NOT LIKE '____-__-__'              THEN 'bad date format'
             WHEN TRIM(s.amount, '0123456789.-') <> ''            THEN 'amount not a number'
             WHEN CAST(s.amount AS NUMERIC(10,2)) <= 0            THEN 'amount not positive'
             WHEN LOWER(TRIM(s.status)) NOT IN ('pending', 'shipped', 'cancelled')
                                                                  THEN 'unknown status'
           END AS reject_reason
    FROM stg_orders s
    LEFT JOIN customers c ON c.customer_id = CAST(s.customer_id AS INTEGER)
    ORDER BY s.order_id, s.amount;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | order_id | reject_reason |
    | --- | --- |
    | 201 | *NULL* |
    | 202 | *NULL* |
    | 203 | missing customer_id |
    | 204 | unknown customer |
    | 205 | *NULL* |
    | 206 | duplicate order_id |
    | 206 | duplicate order_id |
    | 207 | amount not positive |
    | 208 | bad date format |
    <!-- /result -->

`CASE` stops at the first true `WHEN`, which is what makes the cast in `'amount not positive'` safe: a row whose
amount is not a number has already been caught one line above. One thing this does not catch: 31 June passes the
`LIKE` shape test (a real date test is in [23.4](#is-date), written per database). Note also that both copies of
order 206 are rejected, because nobody can tell which is right.

From here the load is two `INSERT ... SELECT`s in one transaction: rows with a NULL reason, cleaned and cast, into
the real table; the others, with their reason and the load date, into the rejects table.

## 23.9 Reconciliation and profiling { #reconcile }

**Reconciliation** checks that the target holds what the source sent: the same number of rows, the same totals, per
day or per batch. The `FULL OUTER JOIN` from [chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md) shows days that
are missing on either side, and days whose numbers differ:

<!-- sql setup -->
```sql
CREATE TABLE source_daily (day DATE PRIMARY KEY, orders INTEGER NOT NULL, revenue NUMERIC(10,2) NOT NULL);
CREATE TABLE target_daily (day DATE PRIMARY KEY, orders INTEGER NOT NULL, revenue NUMERIC(10,2) NOT NULL);
INSERT INTO source_daily VALUES
  ('2026-06-01', 120, 3410.50), ('2026-06-02', 98, 2875.00), ('2026-06-03', 131, 3900.25);
INSERT INTO target_daily VALUES
  ('2026-06-01', 120, 3410.50), ('2026-06-02', 97, 2850.00);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

**Task:** Compare the source and target daily totals and list only the days that are missing on one side or differ.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT COALESCE(s.day, t.day) AS day,
           s.orders  AS source_orders,  t.orders  AS target_orders,
           s.revenue AS source_revenue, t.revenue AS target_revenue
    FROM source_daily s
    FULL OUTER JOIN target_daily t ON t.day = s.day
    WHERE s.day IS NULL OR t.day IS NULL
       OR s.orders  <> t.orders
       OR s.revenue <> t.revenue
    ORDER BY day;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | day | source_orders | target_orders | source_revenue | target_revenue |
    | --- | --- | --- | --- | --- |
    | 2026-06-02 | 98 | 97 | 2875.00 | 2850.00 |
    | 2026-06-03 | 131 | *NULL* | 3900.25 | *NULL* |
    <!-- /result -->

2 June lost one order worth 25.00, and 3 June never arrived. `EXCEPT` both ways does the same row by row
([chapter 12](12-Set-Operations.md)).

**Profiling** is the first look at a column you do not know yet: how many values, how many distinct, how many
missing, the smallest and largest. It tells you what checks to write.

**Task:** Profile the `city` column of customers: rows, rows with a city, different cities, first and last city, shortest and longest length.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT COUNT(*)                     AS total_rows,
           COUNT(city)                  AS with_city,
           COUNT(DISTINCT city)         AS distinct_cities,
           MIN(city)                    AS first_city,
           MAX(city)                    AS last_city,
           MIN(LENGTH(city))            AS shortest,
           MAX(LENGTH(city))            AS longest
    FROM customers;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | total_rows | with_city | distinct_cities | first_city | last_city | shortest | longest |
    | --- | --- | --- | --- | --- | --- | --- |
    | 10 | 9 | 7 | Lagos | Toronto | 5 | 8 |
    <!-- /result -->

Add the most common values (`GROUP BY city ORDER BY COUNT(*) DESC`) and you know the column.

### Where these checks live in real pipelines { #tools }

You rarely hand-run these queries. **Constraints** ([chapter 18](18-Create-Table-Types-Constraints.md#constraints))
are the strongest checks, enforced on every write, when the database supports them. dbt has built-in tests for
`unique`, `not_null`, `accepted_values` and `relationships`, each compiled to a query that returns failing rows,
as here. Great Expectations and Soda run similar checks from a configuration file, and Databricks pipelines have
expectations that drop, keep or fail on bad rows (the Databricks tutorial covers them). Behind all of them are the
queries in this chapter.

## 23.10 Summary { #summary }

- Write every check to return the failing rows (or a count of them); no rows, or 0, means passed.
- Completeness: `COUNT(*) - COUNT(col)`, plus empty strings and placeholders. Uniqueness: `GROUP BY key HAVING
  COUNT(*) > 1`.
- Test text before casting: `pg_input_is_valid` and regular expressions on PostgreSQL; `TRIM(x, chars)` and
  `date(x) IS NOT x` on SQLite. Check a date's format, not just whether it parses.
- Orphans: anti-join to the parent table, ignoring NULL keys (count those as missing instead).
- Volume and freshness catch the missing file; consistency and reconciliation catch the wrong numbers.
- Combine checks with `UNION ALL`, one row per check; decide which stop the load and which only warn.
- Quarantine bad rows with a `CASE` that gives the first failing reason.

!!! question "Asked aloud: data quality"
    ??? note "What data quality checks would you put on a new pipeline?"
        On keys: not null and unique. On foreign keys: every value exists in the parent. On important columns: not
        null, valid type and format, allowed values, sensible ranges. On the batch: row count within the usual range,
        newest timestamp recent enough, totals reconciled with the source. Some checks stop the load (duplicate keys);
        others warn (an unknown category).

    ??? note "How do you handle bad rows: fail the load, or not?"
        It depends on the check. Fail when loading would break the target or make every report wrong (duplicate keys,
        an empty file, a schema change). Otherwise load the good rows and quarantine the bad ones in a rejects table
        with the reason and the batch id, alert someone, and reprocess them once fixed. Always make the failure
        visible: silent dropping is the worst option.

    ??? note "How do you check that a load is complete?"
        Reconcile with the source: row counts and sums of key amounts per day or batch, compared with what the source
        reports (a control file, a count query on the source). A `FULL OUTER JOIN` or `EXCEPT` both ways shows missing
        and different rows. Add a volume check against recent history to catch a partial file.

    ??? note "Why stage data as text first?"
        So that one bad value cannot stop the whole file from landing, and so that you can see and report exactly what
        arrived. Checks then run in SQL on the staging table, and only clean, cast rows move into the typed table.

    ??? note "What is data profiling?"
        A first statistical look at the data: row count, nulls, distinct values, minimum and maximum, lengths, most
        common values, per column. It reveals what "normal" looks like, and so which checks and thresholds to write.

    ??? note "How would you detect that a source system changed its schema?"
        Compare the incoming columns (names, order, types) with the expected list before loading, for example from the
        file header or the database catalogue (`information_schema.columns`), and stop the load on a difference. A
        sudden jump in NULLs in one column is the usual symptom when this check is missing.

## Practice { #practice }

**23.1** Write one query on the shop's `customers` that returns one row with three counts: customers with no
email, customers with no city, and emails that do not contain `@`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT COUNT(*) - COUNT(email)                          AS no_email,
           COUNT(*) - COUNT(city)                           AS no_city,
           SUM(CASE WHEN email NOT LIKE '%@%' THEN 1 ELSE 0 END) AS bad_email
    FROM customers;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | no_email | no_city | bad_email |
    | --- | --- | --- |
    | 2 | 1 | 0 |
    <!-- /result -->

    `email NOT LIKE '%@%'` is UNKNOWN for a NULL email, so the `CASE` gives 0 for those and they are not counted
    twice. `SUM(CASE ...)` is the portable way to count rows matching a condition; PostgreSQL also has
    `COUNT(*) FILTER (WHERE ...)`.

**23.2** Return the order lines of the shop whose `unit_price` differs from the product's list price by more than
10%. Show the order, the product, both prices.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT oi.order_id, oi.product_id, oi.unit_price, p.price AS list_price
    FROM order_items oi
    JOIN products p ON p.product_id = oi.product_id
    WHERE oi.unit_price < p.price * 0.9
       OR oi.unit_price > p.price * 1.1
    ORDER BY oi.order_id, oi.product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

    | order_id | product_id | unit_price | list_price |
    | --- | --- | --- | --- |
    | *(no rows)* | | | |
    <!-- /result -->

    No rows: the shop's two discounts (the kettle at 30.00 instead of 32.00, the chair at 139.00 instead of 149.00)
    are both under 10%. A consistency check like this one usually warns rather than stops a load.

**23.3** The shop wants a check that fails when any customer placed two orders on the same day. Write it so that it
returns the failing customers and days.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id, order_date, COUNT(*) AS orders
    FROM orders
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id, order_date
    HAVING COUNT(*) > 1;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

    | customer_id | order_date | orders |
    | --- | --- | --- |
    | *(no rows)* | | |
    <!-- /result -->

    No rows: it passes. It is a uniqueness check on a pair of columns rather than on a key.

**23.4** Using `stg_orders`, write a check that returns the rows whose `status`, once cleaned with `LOWER(TRIM(...))`,
is valid but was not clean as sent. These are the rows a load should fix rather than reject.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT order_id, status
    FROM stg_orders
    WHERE status <> LOWER(TRIM(status))
      AND LOWER(TRIM(status)) IN ('pending', 'shipped', 'cancelled');
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | order_id | status |
    | --- | --- |
    | 202 | Shipped  |
    <!-- /result -->

    `<>` compares text exactly on both databases (only `LIKE` ignores case on SQLite, [chapter 5](05-Text-Functions-and-Pattern-Matching.md#like-case)).

**Next:** [24. JSON and arrays](24-JSON-and-Arrays.md).
