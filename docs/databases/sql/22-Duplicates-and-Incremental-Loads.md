# 22. Duplicates and incremental loads

*Data engineering is mostly moving data from one place to another, again and again, without losing rows or counting
them twice. This chapter covers the SQL for that: finding and removing duplicates, loading only what is new, making
a load safe to run twice, catching late data, detecting changes and deletes, and keeping a type 2 history up to
date. Every step runs on both PostgreSQL and SQLite.*

!!! abstract "In this chapter"
    **You will learn:**

    - exact duplicates and duplicates by key, and how to find each
    - keeping the newest row per key with `ROW_NUMBER`, and deleting duplicates from a table
    - full and incremental loads, the watermark, and why a load must be **idempotent**
    - an upsert that is safe to repeat and never lets old data overwrite new
    - late-arriving data, and classifying rows as new, changed, deleted or unchanged
    - updating a slowly changing dimension (type 2) from a daily snapshot

    **You need:** [chapter 13](13-Window-Functions-Ranking.md) (`ROW_NUMBER`), [chapter 17](17-Insert-Update-Delete-Merge.md)
    (upsert and `MERGE`) and [chapter 19](19-Data-Modelling.md#scd) (type 2 history).

## 22.1 What counts as a duplicate { #duplicates }

The table below is a feed from another system: every time a customer changes, the system sends the whole customer
again. It also sent one row twice.

<!-- sql setup -->
```sql
CREATE TABLE customer_feed (
  customer_id INTEGER     NOT NULL,
  email       VARCHAR(50),
  city        VARCHAR(20),
  updated_at  TIMESTAMP   NOT NULL
);
INSERT INTO customer_feed VALUES
  (1, 'ana@example.com',  'Toronto',   '2026-05-01 09:00:00'),
  (1, 'ana@example.com',  'Toronto',   '2026-05-01 09:00:00'),
  (2, 'ben@example.com',  'Lagos',     '2026-05-01 10:00:00'),
  (3, NULL,               'Shanghai',  '2026-05-02 12:00:00'),
  (1, 'ana@example.com',  'Vancouver', '2026-05-03 08:30:00'),
  (3, 'chen@example.com', 'Shanghai',  '2026-05-04 07:15:00'),
  (4, 'dana@example.com', 'Seoul',     '2026-05-04 07:15:00');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

There are two kinds of duplicate, and the first question in any task is which one is meant.

**Exact duplicates** are rows equal in every column. Group by all the columns and keep groups with more than one row:

<!-- sql -->
```sql
SELECT customer_id, email, city, updated_at, COUNT(*) AS copies
FROM customer_feed
GROUP BY customer_id, email, city, updated_at
HAVING COUNT(*) > 1;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| customer_id | email | city | updated_at | copies |
| --- | --- | --- | --- | --- |
| 1 | ana@example.com | Toronto | 2026-05-01 09:00:00 | 2 |
<!-- /result -->

`GROUP BY` puts NULLs together, so two rows that are both NULL in `email` count as equal here, which is what you
want when looking for copies (a plain `=` would not match them).

**Duplicates by key** are several rows for the same business key, here `customer_id`, that may differ in other
columns: different versions of the same customer.

<!-- sql -->
```sql
SELECT customer_id, COUNT(*) AS rows_for_key
FROM customer_feed
GROUP BY customer_id
HAVING COUNT(*) > 1
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| customer_id | rows_for_key |
| --- | --- |
| 1 | 3 |
| 3 | 2 |
<!-- /result -->

Customer 1 has three rows (the 1 May row twice, and a newer one from 3 May); customer 3 has two versions.

## 22.2 Keeping one row per key { #keep-newest }

For exact duplicates, `SELECT DISTINCT` is enough. For duplicates by key you must say **which** row to keep, usually
the newest. Number each key's rows newest first and keep number 1:

<!-- sql -->
```sql
SELECT customer_id, email, city, updated_at
FROM (
  SELECT f.customer_id, f.email, f.city, f.updated_at,
         ROW_NUMBER() OVER (PARTITION BY f.customer_id ORDER BY f.updated_at DESC) AS rn
  FROM customer_feed f
) numbered
WHERE rn = 1
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| customer_id | email | city | updated_at |
| --- | --- | --- | --- |
| 1 | ana@example.com | Vancouver | 2026-05-03 08:30:00 |
| 2 | ben@example.com | Lagos | 2026-05-01 10:00:00 |
| 3 | chen@example.com | Shanghai | 2026-05-04 07:15:00 |
| 4 | dana@example.com | Seoul | 2026-05-04 07:15:00 |
<!-- /result -->

This is the single most useful pattern in this chapter. Three details make it correct:

- **`ROW_NUMBER`, not `RANK`.** If two rows tie on `updated_at`, `RANK` gives both a 1 and you keep both.
- **A tie-breaker when ties are possible.** If two *different* rows for a key can share a timestamp, add a column to
  the `ORDER BY` that decides (a load sequence number, a file name), or the row you keep can change from run to
  run. Here the only tie is the exact copy, and either copy gives the same result.
- **Not `MAX` per column.** `GROUP BY customer_id` with `MAX(city)` and `MAX(updated_at)` takes each column's
  largest value separately, mixing rows: customer 1 would get the newest date and the alphabetically last city.

PostgreSQL also has a shorter form, `SELECT DISTINCT ON (customer_id) ... ORDER BY customer_id, updated_at DESC`,
and Databricks, Snowflake and BigQuery have `QUALIFY ROW_NUMBER() OVER (...) = 1`, which filters a window function
without a subquery. Neither runs on SQLite; the subquery above runs everywhere.

## 22.3 Deleting duplicates from a table { #delete-duplicates }

The shop's `logins` table has no key, and customer 2's login on 2 March is in it twice
([chapter 1](01-Tables-Rows-and-Keys.md)). Both rows are equal in every column, so there is no column to say "delete
this one, keep that one". Each database has a hidden row id for that: `ctid` (the row's physical address) on
PostgreSQL, `rowid` on SQLite.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    DELETE FROM logins a
    USING logins b
    WHERE a.customer_id = b.customer_id
      AND a.login_date  = b.login_date
      AND a.ctid > b.ctid;
    SELECT COUNT(*) AS logins FROM logins;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

    | logins |
    | --- |
    | 14 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    DELETE FROM logins
    WHERE rowid NOT IN (
      SELECT MIN(rowid) FROM logins GROUP BY customer_id, login_date
    );
    SELECT COUNT(*) AS logins FROM logins;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 1 row.</p>

    | logins |
    | --- |
    | 14 |
    <!-- /result -->

Fifteen rows became fourteen. A way that works on every database, and is often faster on a big table with many
duplicates, is to rebuild the table from its distinct rows inside one transaction, then add the key that was missing
so the duplicates cannot come back:

<!-- sql raw -->
```sql
BEGIN;
CREATE TABLE logins_clean AS SELECT DISTINCT customer_id, login_date FROM logins;
DELETE FROM logins;
INSERT INTO logins (customer_id, login_date) SELECT customer_id, login_date FROM logins_clean;
DROP TABLE logins_clean;
CREATE UNIQUE INDEX logins_once ON logins (customer_id, login_date);
COMMIT;
SELECT COUNT(*) AS logins FROM logins;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| logins |
| --- |
| 14 |
<!-- /result -->

<!-- sql error -->
```sql
INSERT INTO logins (customer_id, login_date) VALUES (2, '2026-03-02');
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>duplicate key value violates unique constraint "logins_once"</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>UNIQUE constraint failed: logins.customer_id, logins.login_date</code></p>
<!-- /result -->

When the duplicates are by key and the table has an id column, keep the row you want by id:
`DELETE FROM t WHERE id NOT IN (SELECT MIN(id) FROM t GROUP BY key)` keeps the first; a `ROW_NUMBER` subquery that
returns the ids with `rn > 1` deletes all but the newest.

## 22.4 Full and incremental loads { #incremental }

A **full load** copies the whole source table every time: simple and always right, but slow once the table is big.
An **incremental load** copies only rows that changed since the last load. To know where the last load stopped, the
pipeline keeps a **watermark**: the largest `updated_at` it has loaded.

The target table and the watermark, as they stand after an earlier load that took everything up to 2 May:

<!-- sql setup -->
```sql
CREATE TABLE customers_current (
  customer_id INTEGER PRIMARY KEY,
  email       VARCHAR(50),
  city        VARCHAR(20),
  updated_at  TIMESTAMP NOT NULL
);
INSERT INTO customers_current VALUES
  (1, 'ana@example.com', 'Toronto', '2026-05-01 09:00:00'),
  (2, 'ben@example.com', 'Lagos',   '2026-05-01 10:00:00');

CREATE TABLE load_state (
  table_name   VARCHAR(30) PRIMARY KEY,
  loaded_up_to TIMESTAMP NOT NULL
);
INSERT INTO load_state VALUES ('customers', '2026-05-02 00:00:00');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

The load has three steps, in one transaction: read the rows newer than the watermark, keep the newest per customer,
upsert them; then move the watermark.

<!-- sql raw -->
```sql
BEGIN;

INSERT INTO customers_current (customer_id, email, city, updated_at)
SELECT customer_id, email, city, updated_at
FROM (
  SELECT f.customer_id, f.email, f.city, f.updated_at,
         ROW_NUMBER() OVER (PARTITION BY f.customer_id ORDER BY f.updated_at DESC) AS rn
  FROM customer_feed f
  WHERE f.updated_at > (SELECT loaded_up_to FROM load_state WHERE table_name = 'customers')
) newest
WHERE rn = 1
ON CONFLICT (customer_id) DO UPDATE
SET email      = excluded.email,
    city       = excluded.city,
    updated_at = excluded.updated_at
WHERE excluded.updated_at > customers_current.updated_at;

UPDATE load_state
SET loaded_up_to = (SELECT MAX(updated_at) FROM customers_current)
WHERE table_name = 'customers';

COMMIT;

SELECT customer_id, email, city, updated_at FROM customers_current ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| customer_id | email | city | updated_at |
| --- | --- | --- | --- |
| 1 | ana@example.com | Vancouver | 2026-05-03 08:30:00 |
| 2 | ben@example.com | Lagos | 2026-05-01 10:00:00 |
| 3 | chen@example.com | Shanghai | 2026-05-04 07:15:00 |
| 4 | dana@example.com | Seoul | 2026-05-04 07:15:00 |
<!-- /result -->

Ana moved to Vancouver, Chen and Dana are new, Ben was not touched. Each part of the statement has a job:

| Part | Why |
| --- | --- |
| `WHERE f.updated_at > watermark` | read only what is new |
| `ROW_NUMBER ... WHERE rn = 1` | the batch can hold several versions of one customer (Chen has two). Given two rows for one key, PostgreSQL's upsert stops with "ON CONFLICT DO UPDATE command cannot affect row a second time"; SQLite applies both one after the other, which the newer-wins `WHERE` below happens to sort out, except when two rows share a timestamp |
| `ON CONFLICT (customer_id) DO UPDATE` | insert new customers, update known ones |
| `WHERE excluded.updated_at > customers_current.updated_at` | **newer wins**: a row older than what is already loaded never overwrites it |
| one transaction, watermark last | if anything fails, neither the data nor the watermark moves, and the next run simply tries again |

`excluded` is the row that was refused by the conflict (the one you tried to insert), on both databases.

!!! warning "SQLite: INSERT ... SELECT ... ON CONFLICT needs a WHERE"
    When an upsert's `SELECT` has no `WHERE` of its own, SQLite cannot tell whether `ON CONFLICT` belongs to the
    `SELECT`'s last join, and reports a syntax error near `DO`. Add `WHERE true` to the `SELECT` (from SQLite's
    documentation, and checked below). Above, the outer `WHERE rn = 1` already does it.

<!-- sql sqlite error -->
```sql
INSERT INTO customers_current (customer_id, email, city, updated_at)
SELECT customer_id, email, city, updated_at FROM customer_feed
ON CONFLICT (customer_id) DO NOTHING;
```

<!-- result -->
<p class="sql-tested sql-error">SQLite 3.53: error: <code>near "DO": syntax error</code></p>
<!-- /result -->

<!-- sql sqlite -->
```sql
INSERT INTO customers_current (customer_id, email, city, updated_at)
SELECT customer_id, email, city, updated_at FROM customer_feed WHERE true
ON CONFLICT (customer_id) DO NOTHING;
SELECT COUNT(*) AS customers FROM customers_current;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| customers |
| --- |
| 4 |
<!-- /result -->

### Idempotent: safe to run twice { #idempotent }

Jobs fail and get re-run; schedulers retry; someone runs yesterday's load again by hand. A load is **idempotent**
when running it twice gives the same result as running it once. Here the same load is run again as if the watermark
had not moved (the old value written in by hand):

<!-- sql -->
```sql
INSERT INTO customers_current (customer_id, email, city, updated_at)
SELECT customer_id, email, city, updated_at
FROM (
  SELECT f.customer_id, f.email, f.city, f.updated_at,
         ROW_NUMBER() OVER (PARTITION BY f.customer_id ORDER BY f.updated_at DESC) AS rn
  FROM customer_feed f
  WHERE f.updated_at > '2026-05-02 00:00:00'
) newest
WHERE rn = 1
ON CONFLICT (customer_id) DO UPDATE
SET email = excluded.email, city = excluded.city, updated_at = excluded.updated_at
WHERE excluded.updated_at > customers_current.updated_at;

SELECT customer_id, email, city, updated_at FROM customers_current ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| customer_id | email | city | updated_at |
| --- | --- | --- | --- |
| 1 | ana@example.com | Vancouver | 2026-05-03 08:30:00 |
| 2 | ben@example.com | Lagos | 2026-05-01 10:00:00 |
| 3 | chen@example.com | Shanghai | 2026-05-04 07:15:00 |
| 4 | dana@example.com | Seoul | 2026-05-04 07:15:00 |
<!-- /result -->

Nothing changed. A plain `INSERT` in the same place would have failed on the primary key, or, on a table without
one, doubled every row. The three usual ways to make a load idempotent:

1. **Upsert by key** (as above, or `MERGE`), so a second run updates rows to the values they already have.
2. **Delete the batch, then insert it**, in one transaction: delete every row of the day (or file, or partition)
   being loaded, then insert it. Running it twice deletes and inserts the same rows
   ([chapter 20, practice 20.4](20-Transactions-and-Isolation.md#practice)).
3. **Overwrite the partition**, the lakehouse version of 2: replace a whole day's partition in one atomic write.

On PostgreSQL 15+ the same load can be written as a `MERGE` ([chapter 17](17-Insert-Update-Delete-Merge.md#merge)):

<!-- sql pg -->
```sql
MERGE INTO customers_current t
USING (
  SELECT customer_id, email, city, updated_at
  FROM (
    SELECT f.customer_id, f.email, f.city, f.updated_at,
           ROW_NUMBER() OVER (PARTITION BY f.customer_id ORDER BY f.updated_at DESC) AS rn
    FROM customer_feed f
    WHERE f.updated_at > '2026-05-02 00:00:00'
  ) numbered
  WHERE rn = 1
) s
ON t.customer_id = s.customer_id
WHEN MATCHED AND s.updated_at > t.updated_at THEN
  UPDATE SET email = s.email, city = s.city, updated_at = s.updated_at
WHEN NOT MATCHED THEN
  INSERT (customer_id, email, city, updated_at) VALUES (s.customer_id, s.email, s.city, s.updated_at);
SELECT COUNT(*) AS customers FROM customers_current;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| customers |
| --- |
| 4 |
<!-- /result -->

## 22.5 Late-arriving data { #late-data }

A watermark on the source's `updated_at` has a weakness. Suppose Ben moved to Abuja on 3 May at 10:00, but the
source system only sent that row after the load above had run; the watermark is already 4 May 07:15. The next
load reads `updated_at > '2026-05-04 07:15:00'` and never sees Ben's change:

<!-- sql -->
```sql
INSERT INTO customer_feed VALUES (2, 'ben@example.com', 'Abuja', '2026-05-03 10:00:00');
SELECT f.customer_id, f.city, f.updated_at
FROM customer_feed f
WHERE f.updated_at > (SELECT loaded_up_to FROM load_state WHERE table_name = 'customers');
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

| customer_id | city | updated_at |
| --- | --- | --- |
| *(no rows)* | | |
<!-- /result -->

No rows: the late change is lost for good. Two fixes, often used together:

- **Look back.** Read from a little before the watermark (a day, a few hours: longer than data is ever late), and
  rely on the newer-wins upsert to ignore what was already loaded. The cost is reading the overlap again.
- **Use the time the row arrived, not the time it changed.** Give every incoming row an `arrived_at` (or
  `ingested_at`) set by your own pipeline when it lands, and keep the watermark on that. A late row then has a late
  `arrived_at` and is picked up. Keep `updated_at` for "newer wins".

The look-back, with the date arithmetic written for each database ([chapter 16](16-Dates-and-Time-Series.md)):

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    INSERT INTO customer_feed VALUES (2, 'ben@example.com', 'Abuja', '2026-05-03 10:00:00');
    SELECT f.customer_id, f.city, f.updated_at
    FROM customer_feed f
    WHERE f.updated_at > (SELECT loaded_up_to - INTERVAL '2 days'
                          FROM load_state WHERE table_name = 'customers')
    ORDER BY f.updated_at, f.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 5 rows.</p>

    | customer_id | city | updated_at |
    | --- | --- | --- |
    | 3 | Shanghai | 2026-05-02 12:00:00 |
    | 1 | Vancouver | 2026-05-03 08:30:00 |
    | 2 | Abuja | 2026-05-03 10:00:00 |
    | 3 | Shanghai | 2026-05-04 07:15:00 |
    | 4 | Seoul | 2026-05-04 07:15:00 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    INSERT INTO customer_feed VALUES (2, 'ben@example.com', 'Abuja', '2026-05-03 10:00:00');
    SELECT f.customer_id, f.city, f.updated_at
    FROM customer_feed f
    WHERE f.updated_at > (SELECT datetime(loaded_up_to, '-2 days')
                          FROM load_state WHERE table_name = 'customers')
    ORDER BY f.updated_at, f.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 5 rows.</p>

    | customer_id | city | updated_at |
    | --- | --- | --- |
    | 3 | Shanghai | 2026-05-02 12:00:00 |
    | 1 | Vancouver | 2026-05-03 08:30:00 |
    | 2 | Abuja | 2026-05-03 10:00:00 |
    | 3 | Shanghai | 2026-05-04 07:15:00 |
    | 4 | Seoul | 2026-05-04 07:15:00 |
    <!-- /result -->

Ben's row is back in the batch. Ana's, Chen's and Dana's rows come in again too, and the newer-wins rule leaves
them unchanged. That rule also handles data that arrives **out of order**: if an old version of Ana (Toronto, 1 May)
arrived after the Vancouver row, it would not overwrite Vancouver, because its `updated_at` is older.

## 22.6 What changed? New, changed, deleted { #change-detection }

Some sources have no `updated_at`; all you get is a full copy (a **snapshot**) every day. To find what changed,
compare the snapshot with the target. One `FULL OUTER JOIN` sorts every key into one of four groups:

<!-- sql setup -->
```sql
CREATE TABLE snapshot_today (
  customer_id INTEGER PRIMARY KEY,
  email       VARCHAR(50),
  city        VARCHAR(20)
);
INSERT INTO snapshot_today VALUES
  (1, 'ana@example.com',  'Vancouver'),
  (2, 'ben@example.com',  'Abuja'),
  (3, 'chen@example.com', 'Shanghai'),
  (5, 'eli@example.com',  NULL);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

<!-- sql -->
```sql
SELECT COALESCE(s.customer_id, t.customer_id) AS customer_id,
       CASE
         WHEN t.customer_id IS NULL THEN 'new'
         WHEN s.customer_id IS NULL THEN 'deleted'
         WHEN s.email IS DISTINCT FROM t.email
           OR s.city  IS DISTINCT FROM t.city THEN 'changed'
         ELSE 'unchanged'
       END AS change
FROM snapshot_today s
FULL OUTER JOIN customers_current t ON t.customer_id = s.customer_id
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| customer_id | change |
| --- | --- |
| 1 | unchanged |
| 2 | changed |
| 3 | unchanged |
| 4 | deleted |
| 5 | new |
<!-- /result -->

| Group | Test | What the load does |
| --- | --- | --- |
| new | no target row | insert |
| deleted | no snapshot row | delete, or better, mark as deleted (`is_deleted`, `deleted_at`) so history and old reports keep working |
| changed | some column differs | update (or a new version, [22.7](#scd2)) |
| unchanged | all columns equal | nothing: skipping these keeps the load small |

Compare with `IS DISTINCT FROM`, not `<>`. A change from NULL to a value (or back) makes `<>` UNKNOWN, and the row
would be reported as unchanged ([chapter 6](06-Null-and-Three-Valued-Logic.md#is-null)). `IS DISTINCT FROM` runs on
SQLite 3.39+ (older SQLite: `IS NOT`). `FULL OUTER JOIN` needs SQLite 3.39+ too. With many columns, pipelines often
compare one hash of all the columns instead (PostgreSQL has `md5()`; SQLite has no built-in hash).

Deletes are the part incremental loads miss: a row deleted in the source does not show up in "rows changed since
the watermark", because it is not there any more. Finding deletes needs a full list of the source's keys (as above),
or a source that records deletes, such as change data capture (CDC) from the database's log, which sends each insert,
update and delete as an event.

## 22.7 Keeping a type 2 history up to date { #scd2 }

[Chapter 19](19-Data-Modelling.md#scd) built a type 2 table by hand: one row per version of a customer, with the
dates it was true. Here it is kept up to date from each day's snapshot, in two statements. The surrogate key is left
out to keep the table the same on both databases ([chapter 18](18-Create-Table-Types-Constraints.md#identity) shows
ids that number themselves).

<!-- sql setup -->
```sql
CREATE TABLE customer_history (
  customer_id INTEGER     NOT NULL,
  city        VARCHAR(20),
  valid_from  DATE        NOT NULL,
  valid_to    DATE        NOT NULL,
  is_current  BOOLEAN     NOT NULL,
  PRIMARY KEY (customer_id, valid_from)
);
INSERT INTO customer_history VALUES
  (1, 'Toronto',   '2026-01-01', '2026-05-03', FALSE),
  (1, 'Vancouver', '2026-05-03', '9999-12-31', TRUE),
  (2, 'Lagos',     '2026-01-01', '9999-12-31', TRUE);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

The 10 May snapshot (`snapshot_today` above) says: Ana still in Vancouver, Ben now in Abuja, Chen new, Eli new with
no city. The load:

<!-- sql raw -->
```sql
BEGIN;

-- 1. close the current version of every customer whose city changed
UPDATE customer_history
SET valid_to = '2026-05-10', is_current = FALSE
WHERE is_current = TRUE
  AND EXISTS (SELECT 1 FROM snapshot_today s
              WHERE s.customer_id = customer_history.customer_id
                AND s.city IS DISTINCT FROM customer_history.city);

-- 2. add a current version for every customer who has none now (changed or new)
INSERT INTO customer_history (customer_id, city, valid_from, valid_to, is_current)
SELECT s.customer_id, s.city, '2026-05-10', '9999-12-31', TRUE
FROM snapshot_today s
WHERE NOT EXISTS (SELECT 1 FROM customer_history h
                  WHERE h.customer_id = s.customer_id AND h.is_current = TRUE);

COMMIT;

SELECT customer_id, city, valid_from, valid_to, is_current
FROM customer_history
ORDER BY customer_id, valid_from;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

| customer_id | city | valid_from | valid_to | is_current |
| --- | --- | --- | --- | --- |
| 1 | Toronto | 2026-01-01 | 2026-05-03 | false |
| 1 | Vancouver | 2026-05-03 | 9999-12-31 | true |
| 2 | Lagos | 2026-01-01 | 2026-05-10 | false |
| 2 | Abuja | 2026-05-10 | 9999-12-31 | true |
| 3 | Shanghai | 2026-05-10 | 9999-12-31 | true |
| 5 | *NULL* | 2026-05-10 | 9999-12-31 | true |
<!-- /result -->

The order of the two steps is the trick. Step 1 leaves changed customers without a current row; step 2 then inserts
a current row for exactly the customers who lack one, which is the changed ones plus the new ones. Unchanged
customers (Ana) still have their current row and are skipped. Run the same load a second time and nothing happens:
nobody differs from the snapshot any more, and everybody has a current row.

<!-- sql -->
```sql
UPDATE customer_history
SET valid_to = '2026-05-10', is_current = FALSE
WHERE is_current = TRUE
  AND EXISTS (SELECT 1 FROM snapshot_today s
              WHERE s.customer_id = customer_history.customer_id
                AND s.city IS DISTINCT FROM customer_history.city);
INSERT INTO customer_history (customer_id, city, valid_from, valid_to, is_current)
SELECT s.customer_id, s.city, '2026-05-10', '9999-12-31', TRUE
FROM snapshot_today s
WHERE NOT EXISTS (SELECT 1 FROM customer_history h
                  WHERE h.customer_id = s.customer_id AND h.is_current = TRUE);
SELECT COUNT(*) AS versions FROM customer_history;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| versions |
| --- |
| 6 |
<!-- /result -->

Still six versions. This load does not handle a customer deleted from the snapshot (it would stay current
forever); closing those is practice [22.4](#practice). On PostgreSQL and in lakehouses, both steps are often written
as one `MERGE`; the two-statement form is easier to read and runs everywhere.

## 22.8 Summary { #summary }

- Decide first whether "duplicate" means equal in every column or equal on a key.
- Newest row per key: `ROW_NUMBER() OVER (PARTITION BY key ORDER BY updated_at DESC, tie_breaker)`, keep `rn = 1`.
  Never `MAX` per column.
- Delete exact duplicates with the hidden row id (`ctid`, `rowid`) or by rebuilding from `DISTINCT` in one
  transaction; then add the missing key.
- Incremental load: rows after the watermark, de-duplicated, upserted with "newer wins", watermark moved last, all
  in one transaction. It must be idempotent.
- Late data: look back past the watermark, or keep the watermark on arrival time.
- Classify new, changed, deleted and unchanged with a `FULL OUTER JOIN` and `IS DISTINCT FROM`. Deletes need a full
  key list or CDC.
- Type 2 update: close changed current rows, then insert a current row for everyone without one.

!!! question "Asked aloud: loads and duplicates"
    ??? note "What does idempotent mean for a pipeline, and how do you achieve it?"
        Running it twice (or after a partial failure) gives the same result as running it once. Achieve it by
        upserting or merging on a key, by deleting the batch or partition before inserting it in one transaction, or by
        overwriting whole partitions atomically, and by moving any watermark only after the data is committed.

    ??? note "Full load or incremental load?"
        Full: reload everything; simple, catches deletes and corrections, but cost grows with the table. Incremental:
        only rows changed since the watermark; fast, but needs a reliable change column or CDC, and misses deletes and
        late rows unless designed for them. Common practice: incremental daily, with a periodic full reload or
        reconciliation to catch drift.

    ??? note "What is a watermark, and what can go wrong with it?"
        The highest change timestamp (or id) already loaded; the next load reads rows above it. It goes wrong when rows
        arrive late with older timestamps (they are skipped), when clocks differ between systems, when the watermark is
        moved before the data commits, or when many rows share the boundary timestamp and `>` versus `>=` drops or
        repeats some. Fixes: a look-back window with idempotent upserts, an arrival-time watermark, moving it last.

    ??? note "How do you remove duplicates, keeping the latest record per key?"
        `ROW_NUMBER() OVER (PARTITION BY key ORDER BY updated_at DESC, tiebreaker)`, keep `rn = 1`; in Databricks or
        Snowflake with `QUALIFY`. To delete them in place, delete the rows whose `rn > 1` by id, or rebuild the table
        from the `rn = 1` rows. Then add a unique constraint or a merge-on-key load so they do not return.

    ??? note "How do you detect deleted records in the source?"
        Incremental reads cannot see them. Compare a full list of source keys with the target (anti-join), use CDC
        that emits delete events, or have the source soft-delete with an `is_deleted` flag and timestamp. In the target,
        prefer marking rows deleted over removing them.

    ??? note "What is CDC?"
        Change data capture: reading the source database's change log (PostgreSQL's write-ahead log, MySQL's binlog)
        to get every insert, update and delete as an ordered event, usually with tools like Debezium. It catches deletes
        and every intermediate change, without querying the source tables.

    ??? note "At-least-once versus exactly-once delivery?"
        At-least-once: no event is lost, but some may arrive twice (after retries). Exactly-once: each event takes
        effect once. In practice exactly-once is usually at-least-once delivery plus an idempotent write (dedupe by an
        event id, merge on a key), which is why idempotent loads matter.

    ??? note "How do you keep a type 2 dimension up to date?"
        For each batch: close the current row of every key whose tracked columns changed (set its end date and
        current flag), then insert a new current row for every key that has none (changed and new keys). Compare with
        `IS DISTINCT FROM` or a hash, run both steps in one transaction (or one `MERGE`), and handle keys that disappear.

## Practice { #practice }

**22.1** In the shop's `customers` table, find email addresses used by more than one customer, ignoring upper and
lower case. Return the address in lower case and the number of customers, most used first.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT LOWER(email) AS email, COUNT(*) AS customers
    FROM customers
    WHERE email IS NOT NULL
    GROUP BY LOWER(email)
    HAVING COUNT(*) > 1
    ORDER BY customers DESC, email;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

    | email | customers |
    | --- | --- |
    | *(no rows)* | |
    <!-- /result -->

    No rows: every address in the shop is different, even ignoring case. (The two Ana Silvas used different emails;
    whether they are one person is a question for the business, [chapter 15](15-Classic-Interview-Patterns.md).) Group
    by the cleaned value, not the raw one, or `Ana@x.com` and `ana@x.com` land in different groups.

**22.2** The feed below sends price changes. Two rows for product 7 share a timestamp, and the later file
(`batch` 2) is the correction. Return each product's current price.

<!-- sql setup -->
```sql
CREATE TABLE price_feed (
  product_id INTEGER       NOT NULL,
  price      NUMERIC(8,2)  NOT NULL,
  changed_at TIMESTAMP     NOT NULL,
  batch      INTEGER       NOT NULL
);
INSERT INTO price_feed VALUES
  (6, 149.00, '2026-05-01 08:00:00', 1),
  (6, 139.00, '2026-05-03 08:00:00', 1),
  (7,  32.00, '2026-05-02 09:00:00', 1),
  (7,  23.00, '2026-05-04 09:00:00', 1),
  (7,  32.50, '2026-05-04 09:00:00', 2);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Your query should return:

<!-- expected -->
| product_id | price |
| --- | --- |
| 6 | 139.00 |
| 7 | 32.50 |
<!-- /expected -->

??? success "Answer"
    <!-- sql expect -->
    ```sql
    SELECT product_id, price
    FROM (
      SELECT product_id, price,
             ROW_NUMBER() OVER (PARTITION BY product_id
                                ORDER BY changed_at DESC, batch DESC) AS rn
      FROM price_feed
    ) numbered
    WHERE rn = 1
    ORDER BY product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | product_id | price |
    | --- | --- |
    | 6 | 139.00 |
    | 7 | 32.50 |
    <!-- /result -->

    Without `batch DESC`, the two 4 May rows for product 7 tie, and the database may pick 23.00 one day and 32.50 the
    next.

**22.3** A nightly job runs `INSERT INTO sales_daily SELECT ... FROM orders WHERE order_date = <yesterday>`. When it
is re-run after a failure, yesterday's sales are counted twice. Give two ways to fix it.

??? success "Answer"
    (1) In one transaction, `DELETE FROM sales_daily WHERE day = <yesterday>` and then the `INSERT`: a re-run replaces
    the day instead of adding to it. (2) Give `sales_daily` a primary key (for example `(day, city)`) and load with an
    upsert or `MERGE` on it. Either makes the job idempotent. The first also removes rows that should no longer exist,
    which an upsert does not.

**22.4** Extend the type 2 load in [22.7](#scd2) so that a customer who is current in `customer_history` but missing
from the snapshot has their current row closed on 10 May. Write the extra statement, and show the result after
running the whole load.

??? success "Answer"
    One more `UPDATE`, for current rows with no snapshot row. Every customer in the history is also in the snapshot,
    so the example first adds one who is not: customer 9, current since 1 April.

    <!-- sql -->
    ```sql
    INSERT INTO customer_history VALUES (9, 'Toronto', '2026-04-01', '9999-12-31', TRUE);

    UPDATE customer_history
    SET valid_to = '2026-05-10', is_current = FALSE
    WHERE is_current = TRUE
      AND NOT EXISTS (SELECT 1 FROM snapshot_today s
                      WHERE s.customer_id = customer_history.customer_id);

    SELECT customer_id, city, valid_from, valid_to, is_current
    FROM customer_history
    WHERE customer_id = 9;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | customer_id | city | valid_from | valid_to | is_current |
    | --- | --- | --- | --- | --- |
    | 9 | Toronto | 2026-04-01 | 2026-05-10 | false |
    <!-- /result -->

    Customer 9 is no longer current; their history stays. Run this before or after the two steps in 22.7: it only
    touches keys missing from the snapshot, which the other two steps never touch.

**22.5** Using `snapshot_today` and `customers_current`, count how many customers are new, changed, deleted and
unchanged. One row per group that occurs, in alphabetical order of the group.

??? success "Answer"
    The query from [22.6](#change-detection), grouped.

    <!-- sql -->
    ```sql
    SELECT change, COUNT(*) AS customers
    FROM (
      SELECT CASE
               WHEN t.customer_id IS NULL THEN 'new'
               WHEN s.customer_id IS NULL THEN 'deleted'
               WHEN s.email IS DISTINCT FROM t.email
                 OR s.city  IS DISTINCT FROM t.city THEN 'changed'
               ELSE 'unchanged'
             END AS change
      FROM snapshot_today s
      FULL OUTER JOIN customers_current t ON t.customer_id = s.customer_id
    ) classified
    GROUP BY change
    ORDER BY change;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | change | customers |
    | --- | --- |
    | changed | 1 |
    | deleted | 1 |
    | new | 1 |
    | unchanged | 2 |
    <!-- /result -->

**Next:** [23. Data quality checks](23-Data-Quality-Checks.md).
