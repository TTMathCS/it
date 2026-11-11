# 25. Indexes and EXPLAIN

*A query says what you want, not how to get it. The database's planner decides how: which table to read first,
whether to use an index, how to join. This chapter shows what an index is, how to read the plan the planner chose
with `EXPLAIN`, and the common reasons an index is not used. Every plan on this page is the real plan from
PostgreSQL 16 or SQLite 3.53 on a table of 200,000 rows.*

!!! abstract "In this chapter"
    **You will learn:**

    - what a B-tree index is, and what it costs
    - reading `EXPLAIN` on PostgreSQL and `EXPLAIN QUERY PLAN` on SQLite
    - seq scan, index scan, bitmap scan and covering (index-only) scans
    - why an index is skipped: low selectivity, a function on the column, the wrong column order
    - composite, partial and expression indexes
    - estimated versus actual rows with `EXPLAIN ANALYZE`, and the three join algorithms

    **You need:** [chapter 3](03-The-Order-a-Query-Runs-In.md) and [chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md).
    [Chapter 26](26-Making-Slow-Queries-Fast.md) uses all of this to speed up real queries, with timings.

## 25.1 A table big enough to matter { #big-table }

On the shop's tiny tables every plan is "read the whole table", because that is fastest for twenty rows. This
table has 200,000 orders from 5,000 customers. A recursive CTE makes the rows, so the same script runs on both
databases. `ANALYZE` then gathers the statistics (how many rows, how values are spread) that the planner uses to
choose a plan.

<!-- sql setup -->
```sql
CREATE TABLE big_orders (
  order_id     INTEGER PRIMARY KEY,
  customer_id  INTEGER NOT NULL,
  amount_cents INTEGER NOT NULL,
  status       VARCHAR(10) NOT NULL
);
WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 200000)
INSERT INTO big_orders (order_id, customer_id, amount_cents, status)
SELECT i, (i * 7919) % 5000 + 1, (i * 37) % 100000,
       CASE i % 20 WHEN 0 THEN 'cancelled' WHEN 1 THEN 'pending' ELSE 'shipped' END
FROM n;
ANALYZE big_orders;
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

Each customer has 40 orders, scattered through the table. 90% of orders are shipped, 5% pending, 5% cancelled.

PostgreSQL can split a big scan across several worker processes (a **parallel** plan). That makes plans longer
without changing the ideas, so it is switched off for this page's session:

<!-- sql pg keep quiet -->
```sql
SET max_parallel_workers_per_gather = 0;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16: done.</p>
<!-- /result -->

## 25.2 No index: read everything { #seq-scan }

`EXPLAIN` before a query shows the plan without running the query. `COSTS OFF` hides the planner's cost estimates,
which are useful when tuning but differ from machine to machine.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    EXPLAIN (COSTS OFF)
    SELECT order_id, amount_cents FROM big_orders WHERE customer_id = 42;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | QUERY PLAN |
    | --- |
    | Seq Scan on big_orders |
    |   Filter: (customer_id = 42) |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite -->
    ```sql
    EXPLAIN QUERY PLAN
    SELECT order_id, amount_cents FROM big_orders WHERE customer_id = 42;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

    | id | parent | notused | detail |
    | --- | --- | --- | --- |
    | 2 | 0 | 192 | SCAN big_orders |
    <!-- /result -->

Both read every row and keep those that match: a **sequential scan** (PostgreSQL's `Seq Scan`, SQLite's `SCAN`).
On SQLite read the `detail` column; the others are internal numbers. For 40 rows out of 200,000 that is a lot of
wasted reading.

## 25.3 What an index is { #b-tree }

An index is a separate, sorted structure that holds one column's values (or several columns'), each with a pointer
to its row. The usual kind is a **B-tree**: a shallow tree of sorted pages, so the database finds a value in a few
page reads instead of reading the table, the way you find a word with the index at the back of a book instead of
reading every page. Because it is sorted, it also serves ranges (`BETWEEN`, `>`), `ORDER BY` and `MIN`/`MAX`.

<!-- sql keep quiet -->
```sql
CREATE INDEX big_orders_customer ON big_orders (customer_id);
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: done.</p>
<!-- /result -->

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    EXPLAIN (COSTS OFF)
    SELECT order_id, amount_cents FROM big_orders WHERE customer_id = 42;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | QUERY PLAN |
    | --- |
    | Bitmap Heap Scan on big_orders |
    |   Recheck Cond: (customer_id = 42) |
    |   ->  Bitmap Index Scan on big_orders_customer |
    |         Index Cond: (customer_id = 42) |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite -->
    ```sql
    EXPLAIN QUERY PLAN
    SELECT order_id, amount_cents FROM big_orders WHERE customer_id = 42;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

    | id | parent | notused | detail |
    | --- | --- | --- | --- |
    | 3 | 0 | 61 | SEARCH big_orders USING INDEX big_orders_customer (customer_id=?) |
    <!-- /result -->

Read a PostgreSQL plan from the most indented line outward: the innermost step runs first and feeds the one above
it. Here the **Bitmap Index Scan** finds the 40 matching entries in the index and marks which table pages hold
them; the **Bitmap Heap Scan** then reads just those pages (the table itself is called the *heap*), checking the
condition again (`Recheck Cond`). PostgreSQL chooses a bitmap scan when the rows are spread over many pages, and a
plain **Index Scan** (index entry, then its row, one at a time) when there are very few rows or they are stored in
index order. SQLite's `SEARCH ... USING INDEX` means the same: find through the index, then fetch the rows.

What an index costs:

- **Every write gets slower.** Each `INSERT`, `DELETE`, and `UPDATE` of an indexed column must change every index on
  the table too. A table with ten indexes loads much more slowly than one with two.
- **Space**, on disk and in memory.
- So index the columns you filter, join and sort on often, not every column. A primary key and a `UNIQUE`
  constraint create an index automatically; a **foreign key does not** on PostgreSQL or SQLite, and the column
  behind one is usually worth indexing because joins use it.

## 25.4 Estimated and actual rows: EXPLAIN ANALYZE { #analyze }

`EXPLAIN ANALYZE` (PostgreSQL) runs the query and adds what really happened to each step. `TIMING OFF` and
`SUMMARY OFF` leave out the milliseconds, which change from run to run; keep them on when you tune.

<!-- sql pg -->
```sql
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY OFF)
SELECT order_id, amount_cents FROM big_orders WHERE customer_id = 42;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 5 rows.</p>

| QUERY PLAN |
| --- |
| Bitmap Heap Scan on big_orders (actual rows=40 loops=1) |
|   Recheck Cond: (customer_id = 42) |
|   Heap Blocks: exact=40 |
|   ->  Bitmap Index Scan on big_orders_customer (actual rows=40 loops=1) |
|         Index Cond: (customer_id = 42) |
<!-- /result -->

`actual rows=40` is what each step produced; `Heap Blocks: exact=40` says the 40 rows sat on 40 different pages.
With `COSTS` on, each line also shows the planner's estimate (`rows=...`). **A big gap between estimated and actual
rows is the most common cause of a bad plan**: the planner chose a method for 10 rows and got a million. The usual
cure is fresh statistics: `ANALYZE table_name;`. PostgreSQL's autovacuum runs it in the background, but not always
right after a bulk load, so pipelines often run it themselves after loading.

`EXPLAIN ANALYZE` really runs the statement: on an `UPDATE` or `DELETE`, wrap it in `BEGIN ... ROLLBACK`. SQLite
has no `EXPLAIN ANALYZE`; time the query instead (`.timer on` in the `sqlite3` shell).

## 25.5 Why the index is not used { #not-used }

### Too many rows match (low selectivity) { #selectivity }

An index helps when it picks out **a small part** of the table. For `status = 'shipped'`, 90% of the rows match;
jumping from index to row 180,000 times is slower than reading the table straight through, so PostgreSQL ignores
the index. For `'pending'` (5%) it uses it:

=== "'shipped' (90%)"

    <!-- sql pg -->
    ```sql
    CREATE INDEX big_orders_status ON big_orders (status);
    ANALYZE big_orders;
    EXPLAIN (COSTS OFF) SELECT order_id FROM big_orders WHERE status = 'shipped';
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | QUERY PLAN |
    | --- |
    | Seq Scan on big_orders |
    |   Filter: ((status)::text = 'shipped'::text) |
    <!-- /result -->

=== "'pending' (5%)"

    <!-- sql pg -->
    ```sql
    CREATE INDEX big_orders_status ON big_orders (status);
    ANALYZE big_orders;
    EXPLAIN (COSTS OFF) SELECT order_id FROM big_orders WHERE status = 'pending';
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | QUERY PLAN |
    | --- |
    | Bitmap Heap Scan on big_orders |
    |   Recheck Cond: ((status)::text = 'pending'::text) |
    |   ->  Bitmap Index Scan on big_orders_status |
    |         Index Cond: ((status)::text = 'pending'::text) |
    <!-- /result -->

The planner knows the split from the statistics. There is no fixed cut-off; it depends on the table, the row size
and the settings, but "more than a few percent of the rows" usually means a scan.

SQLite takes the index even for `'shipped'`, for a different reason:

<!-- sql sqlite -->
```sql
CREATE INDEX big_orders_status ON big_orders (status);
ANALYZE big_orders;
EXPLAIN QUERY PLAN SELECT order_id FROM big_orders WHERE status = 'shipped';
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| id | parent | notused | detail |
| --- | --- | --- | --- |
| 2 | 0 | 174 | SEARCH big_orders USING COVERING INDEX big_orders_status (status=?) |
<!-- /result -->

`COVERING INDEX` means everything the query needs is in the index itself, so SQLite never touches the table. That is
possible here because `order_id` is the table's `INTEGER PRIMARY KEY`, which SQLite stores in every index entry as
the pointer to the row. Reading a small index is cheaper than reading the table, however many rows match.

### A function or calculation on the column { #sargable }

The index holds `customer_id` sorted. It does not hold `customer_id + 0`, `LOWER(email)` or
`CAST(order_date AS TEXT)`; once the column is wrapped in a calculation, the index cannot help:

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    EXPLAIN (COSTS OFF)
    SELECT order_id FROM big_orders WHERE customer_id + 0 = 42;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | QUERY PLAN |
    | --- |
    | Seq Scan on big_orders |
    |   Filter: ((customer_id + 0) = 42) |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite -->
    ```sql
    EXPLAIN QUERY PLAN
    SELECT order_id FROM big_orders WHERE customer_id + 0 = 42;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

    | id | parent | notused | detail |
    | --- | --- | --- | --- |
    | 2 | 0 | 186 | SCAN big_orders USING COVERING INDEX big_orders_customer |
    <!-- /result -->

PostgreSQL goes back to reading the table. SQLite reads the whole index from start to end instead (`SCAN ... USING
COVERING INDEX`, not `SEARCH`), because the index is smaller than the table, but it still looks at every entry.
Neither can jump straight to 42.

A condition that can use an index is called **sargable** (from "search argument"). Make conditions sargable by
moving the calculation to the other side:

| Not sargable | Sargable |
| --- | --- |
| `WHERE amount_cents / 100 = 500` | `WHERE amount_cents >= 50000 AND amount_cents < 50100` |
| `WHERE EXTRACT(YEAR FROM order_date) = 2026` | `WHERE order_date >= '2026-01-01' AND order_date < '2027-01-01'` |
| `WHERE SUBSTR(code, 1, 3) = 'ABC'` | `WHERE code LIKE 'ABC%'` (see the note below) |
| `WHERE LOWER(email) = 'ana@example.com'` | keep it, and add an expression index on `LOWER(email)` ([25.6](#expression)) |
| `WHERE COALESCE(city, '') = 'Toronto'` | `WHERE city = 'Toronto'` (NULL never equals 'Toronto' anyway) |

A `LIKE` that starts with a wildcard (`'%abc'`) can never use a B-tree index. One with a fixed start (`'abc%'`) can,
but on PostgreSQL only if the database uses the "C" collation or the index is created with `text_pattern_ops`
(`CREATE INDEX ... (code text_pattern_ops)`); SQLite has its own rules, based on its case-insensitive `LIKE`.
Searching inside text needs a different tool, such as PostgreSQL's full-text search or trigram (`pg_trgm`) indexes.

### The wrong column order in a composite index { #composite }

An index on several columns is sorted by the first column, then by the second within equal firsts, like a phone book
sorted by last name, then first name. It helps a query that filters on the **first** column (or the first two, and
so on): you can find all the Smiths, or Smith, John, but the book is no help for finding everyone named John.

<!-- sql pg -->
```sql
CREATE INDEX big_orders_status_cust ON big_orders (status, customer_id);
EXPLAIN (COSTS OFF)
SELECT order_id FROM big_orders WHERE status = 'pending' AND customer_id = 42;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

| QUERY PLAN |
| --- |
| Index Scan using big_orders_status_cust on big_orders |
|   Index Cond: (((status)::text = 'pending'::text) AND (customer_id = 42)) |
<!-- /result -->

Both conditions are answered inside the index (`Index Cond`). Rules of thumb for the column order: columns tested
with `=` first, then the one tested with a range (`>`, `BETWEEN`) or used for `ORDER BY`; among the `=` columns,
put first the one that other queries also filter on alone. (Some databases, SQLite included, can sometimes "skip"
an unselective first column; do not design for it.)

## 25.6 Other kinds of index { #kinds }

### Covering indexes and index-only scans { #covering }

If an index holds every column a query uses, the table need not be read at all. SQLite calls this a covering index;
PostgreSQL an **Index Only Scan**, and it can add extra, unsorted columns to an index just to cover queries:
`CREATE INDEX ... (customer_id) INCLUDE (amount_cents)`. On SQLite, put the extra column in the index itself:

<!-- sql sqlite -->
```sql
CREATE INDEX big_orders_cust_amt ON big_orders (customer_id, amount_cents);
EXPLAIN QUERY PLAN
SELECT customer_id, SUM(amount_cents) FROM big_orders WHERE customer_id = 42 GROUP BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| id | parent | notused | detail |
| --- | --- | --- | --- |
| 6 | 0 | 54 | SEARCH big_orders USING COVERING INDEX big_orders_cust_amt (customer_id=?) |
<!-- /result -->

(PostgreSQL's index-only scans also depend on `VACUUM` having marked the table's pages as all-visible, so on a
freshly loaded table they may still visit the table.)

### Indexes for ORDER BY ... LIMIT { #order-limit }

"Top 5 largest orders" without an index sorts all 200,000 rows to keep 5. With an index on `amount_cents`, the
database reads the index from the large end and stops after 5 entries:

=== "PostgreSQL, no index"

    <!-- sql pg -->
    ```sql
    EXPLAIN (COSTS OFF)
    SELECT order_id, amount_cents FROM big_orders ORDER BY amount_cents DESC LIMIT 5;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | QUERY PLAN |
    | --- |
    | Limit |
    |   ->  Sort |
    |         Sort Key: amount_cents DESC |
    |         ->  Seq Scan on big_orders |
    <!-- /result -->

=== "PostgreSQL, with index"

    <!-- sql pg -->
    ```sql
    CREATE INDEX big_orders_amount ON big_orders (amount_cents);
    EXPLAIN (COSTS OFF)
    SELECT order_id, amount_cents FROM big_orders ORDER BY amount_cents DESC LIMIT 5;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | QUERY PLAN |
    | --- |
    | Limit |
    |   ->  Index Scan Backward using big_orders_amount on big_orders |
    <!-- /result -->

=== "SQLite, with index"

    <!-- sql sqlite -->
    ```sql
    CREATE INDEX big_orders_amount ON big_orders (amount_cents);
    EXPLAIN QUERY PLAN
    SELECT order_id, amount_cents FROM big_orders ORDER BY amount_cents DESC LIMIT 5;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

    | id | parent | notused | detail |
    | --- | --- | --- | --- |
    | 4 | 0 | 186 | SCAN big_orders USING COVERING INDEX big_orders_amount |
    <!-- /result -->

PostgreSQL's sort without an index is a **top-N sort** (`EXPLAIN ANALYZE` reports `Sort Method: top-N heapsort`):
it keeps only the best 5 while reading, so it is not as bad as a full sort, but it still reads every row. A B-tree can be read in either direction (`Index Scan Backward`).

### Expression and partial indexes { #expression }

An **expression index** stores a calculation, so a query using exactly that calculation can use it. A **partial
index** stores only the rows matching a `WHERE`: small, and ideal when queries always look for the same rare value.
Both databases support both.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    CREATE INDEX big_orders_pending ON big_orders (customer_id) WHERE status = 'pending';
    CREATE INDEX big_orders_euros   ON big_orders ((amount_cents / 100));
    EXPLAIN (COSTS OFF)
    SELECT order_id FROM big_orders WHERE amount_cents / 100 = 500;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | QUERY PLAN |
    | --- |
    | Bitmap Heap Scan on big_orders |
    |   Recheck Cond: ((amount_cents / 100) = 500) |
    |   ->  Bitmap Index Scan on big_orders_euros |
    |         Index Cond: ((amount_cents / 100) = 500) |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite -->
    ```sql
    CREATE INDEX big_orders_pending ON big_orders (customer_id) WHERE status = 'pending';
    CREATE INDEX big_orders_euros   ON big_orders ((amount_cents / 100));
    EXPLAIN QUERY PLAN
    SELECT order_id FROM big_orders WHERE amount_cents / 100 = 500;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

    | id | parent | notused | detail |
    | --- | --- | --- | --- |
    | 3 | 0 | 53 | SEARCH big_orders USING COVERING INDEX big_orders_euros (<expr>=?) |
    <!-- /result -->

PostgreSQL needs the extra brackets around an expression in `CREATE INDEX`; SQLite accepts them too. A partial index
is used only when the query's `WHERE` implies the index's (`status = 'pending'` here). A partial **unique** index
enforces a rule on some rows only, for example "one open cart per customer":
`CREATE UNIQUE INDEX ... (customer_id) WHERE status = 'open'`.

### Other index types (PostgreSQL) { #index-types }

| Type | For |
| --- | --- |
| B-tree (the default) | `=`, ranges, sorting, `LIKE 'abc%'`; almost everything |
| Hash | `=` only; rarely better than a B-tree |
| GIN | values that contain many keys: `JSONB` (`@>`, [chapter 24](24-JSON-and-Arrays.md#index)), arrays, full-text search |
| GiST, SP-GiST | geometry, ranges, nearest-neighbour searches |
| BRIN | huge tables whose rows arrive in order (logs by time): stores only the min and max per block of pages, tiny |

Data warehouses and lakehouses mostly have no B-tree indexes. They make queries fast by reading less instead:
**partitioning** (files split by a column such as date, so a filter on it skips whole partitions), keeping
min/max statistics per file so files can be skipped (**data skipping**), and **clustering** rows with similar values
into the same files. The Databricks tutorial covers its versions of these.

## 25.7 How joins run { #join-algorithms }

The planner has three ways to join two tables, and `EXPLAIN` names the one it picked:

| Algorithm | How | Good when |
| --- | --- | --- |
| **Nested loop** | for each row of the outer input, look up matches in the inner one (best through an index) | the outer input is small, and the inner has an index on the join column |
| **Hash join** | build a hash table of the smaller input, then stream the larger one past it | big inputs, equality joins, no useful index |
| **Merge join** | sort both inputs on the join key (or read them in order from indexes), then walk them together | both inputs already sorted, or very large inputs |

One customer's orders: one row from `customers`, then an index lookup in `big_orders` per row: a nested loop.

<!-- sql pg -->
```sql
EXPLAIN (COSTS OFF)
SELECT c.name, b.order_id
FROM customers c
JOIN big_orders b ON b.customer_id = c.customer_id
WHERE c.customer_id = 3;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 7 rows.</p>

| QUERY PLAN |
| --- |
| Nested Loop |
|   ->  Index Scan using customers_pkey on customers c |
|         Index Cond: (customer_id = 3) |
|   ->  Bitmap Heap Scan on big_orders b |
|         Recheck Cond: (customer_id = 3) |
|         ->  Bitmap Index Scan on big_orders_customer |
|               Index Cond: (customer_id = 3) |
<!-- /result -->

Counting orders for every customer: every row of both tables is needed, so a hash join.

<!-- sql pg -->
```sql
EXPLAIN (COSTS OFF)
SELECT c.customer_id, COUNT(*) AS orders
FROM customers c
JOIN big_orders b ON b.customer_id = c.customer_id
GROUP BY c.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 7 rows.</p>

| QUERY PLAN |
| --- |
| HashAggregate |
|   Group Key: c.customer_id |
|   ->  Hash Join |
|         Hash Cond: (b.customer_id = c.customer_id) |
|         ->  Seq Scan on big_orders b |
|         ->  Hash |
|               ->  Seq Scan on customers c |
<!-- /result -->

The hash is built from `customers` (the small side, under `Hash`) and `big_orders` streams past it. SQLite
implements every join as a nested loop, creating a temporary index on the fly when no index fits ("AUTOMATIC
INDEX" in its plan).

## 25.8 Summary { #summary }

- An index is a sorted copy of some columns with pointers to rows. It speeds up finding, ranges, sorting and joins,
  and slows down every write.
- `EXPLAIN` shows the plan; `EXPLAIN ANALYZE` (PostgreSQL) runs it and shows actual rows. Read PostgreSQL plans from
  the innermost line out. Compare estimated and actual rows; refresh statistics with `ANALYZE`.
- Seq scan reads everything; index scan and bitmap scan use an index; a covering / index-only scan never reads the
  table.
- An index is skipped when too many rows match, when the column is inside a function or calculation (make it
  sargable or index the expression), or when the query does not filter on the index's first column.
- Index foreign keys used in joins. Use partial indexes for rare values, `INCLUDE` or wider indexes to cover.
- Joins run as nested loop, hash join or merge join; warehouses use partitions, file statistics and clustering
  instead of B-trees.

!!! question "Asked aloud: indexes and plans"
    ??? note "What is an index, and what does it cost?"
        A separate sorted structure (usually a B-tree) of one or more columns' values with pointers to their rows, so
        the database can find, range-scan and sort without reading the whole table. It costs disk and memory, and every
        insert, delete, or update of indexed columns must maintain it, so writes and bulk loads slow down.

    ??? note "Clustered versus non-clustered index?"
        A clustered index is the table itself stored in key order (SQL Server's clustered index, MySQL InnoDB's
        primary key, SQLite's rowid tables); there can be one. A non-clustered (secondary) index is separate and points
        to the rows. PostgreSQL tables are unordered heaps and every index is secondary; `CLUSTER` reorders a table
        once but does not keep it ordered.

    ??? note "Your query is slow. What do you do?"
        Run `EXPLAIN ANALYZE` (or the platform's query profile). Look for the step that takes the time and for big gaps
        between estimated and actual rows. Typical fixes: refresh statistics, add or change an index (column order,
        covering), make a condition sargable, filter or aggregate earlier, replace a correlated subquery with a join or
        window, avoid `SELECT *`. Then measure again ([chapter 26](26-Making-Slow-Queries-Fast.md)).

    ??? note "Why might the database not use my index?"
        Too many rows match, so a scan is cheaper; the column is wrapped in a function, cast or calculation; the
        condition does not use the index's leading column; a type mismatch forces a cast; statistics are stale so the
        estimate is wrong; or the table is so small a scan is fastest anyway.

    ??? note "How do you choose the column order of a composite index?"
        Columns compared with `=` first, then the range or `ORDER BY` column, because after a range the rest of the
        index is no longer sorted usefully. Among the equality columns, lead with one other queries also filter on alone,
        so the index serves them too.

    ??? note "What is a covering index?"
        An index that contains every column a query reads, so the query is answered from the index without visiting the
        table: an index-only scan. Built by adding columns to the key or, in PostgreSQL and SQL Server, with `INCLUDE`.

    ??? note "Hash join, merge join, nested loop: when is each used?"
        Nested loop when one side is small and the other can be probed through an index. Hash join for large unsorted
        inputs joined on equality: build a hash table on the smaller side. Merge join when both inputs are already
        sorted on the key (from indexes or earlier sorts), or for very large inputs, and it also handles range joins.

    ??? note "How do data warehouses speed up queries without indexes?"
        Columnar storage (read only the columns used), partition pruning (skip partitions by a filter column), min/max
        statistics per file or block to skip data (zone maps, data skipping), clustering or sort keys so similar values
        sit together, caching, and massive parallelism.

## Practice { #practice }

**25.1** An index exists on `orders (order_date)`. Which of these conditions can use it?
(a) `order_date = '2026-03-01'` (b) `order_date >= '2026-03-01'` (c) `EXTRACT(MONTH FROM order_date) = 3`
(d) `order_date + 1 = '2026-03-02'` (e) `order_date BETWEEN '2026-03-01' AND '2026-03-31'`

??? success "Answer"
    (a), (b) and (e): the column stands alone on one side. (c) and (d) wrap it in a calculation. Rewrite (c) as a range,
    `order_date >= '2026-03-01' AND order_date < '2026-04-01'` (for one year; across years it needs an expression
    index), and (d) as `order_date = '2026-03-01'`.

**25.2** Rewrite `WHERE amount_cents / 100 = 500` so that the plain index on `amount_cents` (from [25.6](#order-limit))
is used, and show the plan on both databases.

??? success "Answer"
    Euros 500 means cents from 50000 up to, but not including, 50100.

    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        CREATE INDEX big_orders_amount ON big_orders (amount_cents);
        EXPLAIN (COSTS OFF)
        SELECT order_id FROM big_orders WHERE amount_cents >= 50000 AND amount_cents < 50100;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

        | QUERY PLAN |
        | --- |
        | Bitmap Heap Scan on big_orders |
        |   Recheck Cond: ((amount_cents >= 50000) AND (amount_cents < 50100)) |
        |   ->  Bitmap Index Scan on big_orders_amount |
        |         Index Cond: ((amount_cents >= 50000) AND (amount_cents < 50100)) |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite -->
        ```sql
        CREATE INDEX big_orders_amount ON big_orders (amount_cents);
        EXPLAIN QUERY PLAN
        SELECT order_id FROM big_orders WHERE amount_cents >= 50000 AND amount_cents < 50100;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

        | id | parent | notused | detail |
        | --- | --- | --- | --- |
        | 2 | 0 | 126 | SEARCH big_orders USING COVERING INDEX big_orders_amount (amount_cents>? AND amount_cents<?) |
        <!-- /result -->

    Both use the index for the range. Integer division makes the two conditions equal only for whole, non-negative
    cents; check that kind of detail whenever you rewrite a condition.

**25.3** A dashboard runs `SELECT order_id, amount_cents FROM big_orders WHERE status = 'pending' AND customer_id = ?`
thousands of times a day. Pending orders are 5% of the table and the rest are never queried this way. Which index
would you create, and why?

??? success "Answer"
    A partial index, `CREATE INDEX ... ON big_orders (customer_id) WHERE status = 'pending'`, or, to also cover the
    query on PostgreSQL, `... (customer_id) INCLUDE (amount_cents) WHERE status = 'pending'`. It holds only the 5% of
    rows the dashboard asks about, so it is about twenty times smaller than a full index and cheaper to maintain. A
    composite index `(status, customer_id)` also works and serves other statuses too, at the full size.

**25.4** A colleague adds an index on `big_orders (status)` and is surprised that PostgreSQL does not use it for
`WHERE status = 'shipped'`. Explain in two sentences.

??? success "Answer"
    90% of the rows are shipped, so using the index would mean 180,000 jumps from index to table, which is slower
    than reading the table once from start to end; the planner knows the split from its statistics and chooses the
    scan ([25.5](#selectivity)). The index is still useful for the rare statuses, pending and cancelled.

**Next:** [26. Making slow queries fast](26-Making-Slow-Queries-Fast.md).
