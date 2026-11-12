# 1. Joins are set math: relational algebra and NULL logic

*Every SQL query, however long, is built from a handful of operations on sets of rows: filter, keep some columns, pair every row with every row, add, subtract. This tutorial works through those operations by hand on two tables small enough to write on a napkin, counts how many rows each one can return, proves the rules a query planner uses to rewrite your query, and then explains two classic surprises with three-valued logic: why `NOT IN` returns nothing when the list holds one NULL, and why a `WHERE` clause can quietly turn a `LEFT JOIN` into an inner join. Every query below ran on PostgreSQL 16 and SQLite 3.53, and the results under them are the real ones.*

!!! abstract "In this tutorial"
    **You will learn:**

    - the five basic operations of relational algebra (selection, projection, product, union, difference) and how a join, a semi join and an anti join are built from them
    - how many rows each operation can return, so you can predict a result size before you run anything
    - the pushdown law that query planners use, with a two-line proof, and when it does not apply
    - three-valued logic (TRUE, FALSE, UNKNOWN) as truth tables, and the two laws it breaks
    - exactly when `NOT IN` and `NOT EXISTS` give the same answer, and when they do not
    - why SQL tables are bags, not sets, and the counting rules for `UNION ALL`, `INTERSECT ALL` and `EXCEPT ALL`

    **You need:** what a set is, and basic SQL (`SELECT`, `WHERE`, `JOIN`). The [SQL course](../../databases/sql/index.md) covers the SQL; chapters [6](../../databases/sql/06-Null-and-Three-Valued-Logic.md), [8](../../databases/sql/08-Joins-Inner-Left-Right-Full-Cross.md), [9](../../databases/sql/09-Self-Semi-and-Anti-Joins.md) and [12](../../databases/sql/12-Set-Operations.md) are the practical side of this tutorial.

    **How to learn from it:** read 1.1 to 1.3, close the page, redo the 16-cell grid of 1.3 on paper, then try the exercises in 1.7 before opening any answer. Plan about three hours.

**About the examples.** Every query ran on PostgreSQL 16 and SQLite 3.53 through the IT site's test runner, which writes the real result under each query and fails if the two databases disagree. Queries marked as PostgreSQL only use a feature SQLite lacks. Plans come from `EXPLAIN (COSTS OFF)` on PostgreSQL 16; another version may print them a little differently.

## 1.1 The question

A report should list the buyers who have never made a purchase. Two people write it two ways:

```sql
-- Version A
SELECT name FROM buyers WHERE buyer_id NOT IN (SELECT buyer_id FROM purchases);
-- Version B
SELECT name FROM buyers b WHERE NOT EXISTS (SELECT 1 FROM purchases p WHERE p.buyer_id = b.buyer_id);
```

Version B returns two names. Version A returns **nothing**. Nobody gets an error. The reason is one purchase whose `buyer_id` is NULL (a walk-in sale), and the logic that SQL uses when a value is missing. By the end of this tutorial you will be able to prove, in three lines, that version A can never return a row while that NULL is there.

## 1.2 The idea: a table is a set of rows, a query is a formula

In 1970 Edgar F. Codd proposed treating a table as a mathematical **relation**: a set of rows (tuples), each row having the same named columns. A query is then a formula built from a few operations, each taking tables in and giving a table out. Five are enough for everything a plain `SELECT` does:

| Operation | Symbol | SQL | What it does |
| --- | --- | --- | --- |
| Selection | σ<sub>p</sub>(R) | `WHERE p` | keep the rows where condition `p` is TRUE |
| Projection | π<sub>cols</sub>(R) | `SELECT cols` | keep some columns |
| Product | R × S | `CROSS JOIN` | pair every row of R with every row of S |
| Union | R ∪ S | `UNION` | rows in either |
| Difference | R − S | `EXCEPT` | rows in R and not in S |

Everything else is built from these. A **join** is a product followed by a selection:

```text
R ⋈p S  =  σp( R × S )
```

Read it as: "make every pair, then keep the pairs that match." No database actually builds the whole product (that would be far too slow), but every join it runs must return exactly the rows this formula describes. That is what lets a database choose its own method.

Two more joins come up all the time, and both are built from the same pieces:

- **Semi join** R ⋉ S: the rows of R that have **at least one** match in S (SQL: `EXISTS`, `IN`). It is the join projected back onto R's columns, with each row of R kept once.
- **Anti join** R ▷ S: the rows of R with **no** match in S (SQL: `NOT EXISTS`). It is R minus the semi join: `R − (R ⋉ S)`.

And the **left join** is the join plus the unmatched rows of R, padded with NULL for S's columns:

```text
R ⟕ S  =  (R ⋈ S)  ∪  ( (R ▷ S) × {one row of NULLs} )
```

## 1.3 The math by hand

Here are the two tables, small enough to hold in your head. One purchase, number 13, has no buyer on record.

<!-- sql setup -->
```sql
CREATE TABLE buyers (
  buyer_id INTEGER PRIMARY KEY,
  name     VARCHAR(10) NOT NULL,
  city     VARCHAR(10) NOT NULL
);
CREATE TABLE purchases (
  purchase_id INTEGER PRIMARY KEY,
  buyer_id    INTEGER,          -- NULL: a walk-in sale, buyer unknown
  amount      INTEGER NOT NULL
);
CREATE TABLE stores (city VARCHAR(10) NOT NULL);
INSERT INTO buyers VALUES (1, 'Ana', 'Toronto'), (2, 'Ben', 'Lagos'), (3, 'Cai', 'Toronto'), (4, 'Dee', 'Oslo');
INSERT INTO purchases VALUES (10, 1, 50), (11, 1, 20), (12, 3, 70), (13, NULL, 40);
INSERT INTO stores VALUES ('Toronto'), ('Oslo'), ('Oslo');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

### Step 1. The product: 4 × 4 = 16 pairs

Draw a grid: one row per buyer, one column per purchase. Each cell is one row of `buyers × purchases`. A cell **matches** when `purchases.buyer_id = buyers.buyer_id` is TRUE.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="A 4 by 4 grid. Rows are buyers Ana 1, Ben 2, Cai 3 and Dee 4. Columns are purchases 10 (buyer 1), 11 (buyer 1), 12 (buyer 3) and 13 (buyer NULL). Three cells match: Ana with 10, Ana with 11, Cai with 12. Column 13 is marked unknown in every row. Ben and Dee have no match.">
<g font-size="13" fill="currentColor">
<text x="200" y="22" font-weight="bold">purchases (purchase_id: buyer_id)</text>
<text x="160" y="50" text-anchor="middle">10: 1</text><text x="260" y="50" text-anchor="middle">11: 1</text><text x="360" y="50" text-anchor="middle">12: 3</text><text x="460" y="50" text-anchor="middle">13: NULL</text>
<text x="20" y="90">Ana (1)</text><text x="20" y="140">Ben (2)</text><text x="20" y="190">Cai (3)</text><text x="20" y="240">Dee (4)</text>
</g>
<g fill="none" stroke="currentColor" stroke-width="1" opacity="0.6">
<rect x="110" y="65" width="400" height="200"/>
<line x1="210" y1="65" x2="210" y2="265"/><line x1="310" y1="65" x2="310" y2="265"/><line x1="410" y1="65" x2="410" y2="265"/>
<line x1="110" y1="115" x2="510" y2="115"/><line x1="110" y1="165" x2="510" y2="165"/><line x1="110" y1="215" x2="510" y2="215"/>
</g>
<g fill="none" stroke="currentColor" stroke-width="3">
<rect x="116" y="71" width="88" height="38" rx="4"/><rect x="216" y="71" width="88" height="38" rx="4"/><rect x="316" y="171" width="88" height="38" rx="4"/>
</g>
<g font-size="13" fill="currentColor" text-anchor="middle">
<text x="160" y="95" font-weight="bold">TRUE</text><text x="260" y="95" font-weight="bold">TRUE</text><text x="360" y="95">false</text><text x="460" y="95" font-style="italic">unknown</text>
<text x="160" y="145">false</text><text x="260" y="145">false</text><text x="360" y="145">false</text><text x="460" y="145" font-style="italic">unknown</text>
<text x="160" y="195">false</text><text x="260" y="195">false</text><text x="360" y="195" font-weight="bold">TRUE</text><text x="460" y="195" font-style="italic">unknown</text>
<text x="160" y="245">false</text><text x="260" y="245">false</text><text x="360" y="245">false</text><text x="460" y="245" font-style="italic">unknown</text>
</g>
<g font-size="12" fill="currentColor"><text x="525" y="145">Ben: no TRUE</text><text x="525" y="245">Dee: no TRUE</text></g>
</svg>
<figcaption>Figure 1.1. The product of the two tables as a grid. The join keeps the three TRUE cells. Column 13 is "unknown" everywhere, because NULL compared with anything is unknown, so purchase 13 joins nobody. Ben and Dee have no TRUE cell: they are the anti join.</figcaption>
</figure>

Reading the grid gives every answer:

| Operation | Rows, read off the grid | Count |
| --- | --- | ---: |
| Product `buyers × purchases` | every cell | 16 |
| Join on `buyer_id` | (Ana, 10), (Ana, 11), (Cai, 12) | 3 |
| Semi join: buyers with a purchase | Ana, Cai (Ana once, not twice) | 2 |
| Anti join: buyers with no purchase | Ben, Dee | 2 |
| Left join `buyers ⟕ purchases` | the 3 join rows + (Ben, NULL), (Dee, NULL) | 5 |

### Step 2. Count before you run

These counting rules hold for any tables, not just this one. Write |R| for the number of rows of R.

```text
|R × S|  =  |R| × |S|                                   16 = 4 × 4
0 ≤ |R ⋈ S|  ≤  |R| × |S|                               a join keeps some cells of the grid
|R ⋈ S|  ≤  |S|    if each S row matches at most one R row (S.buyer_id points at a key of R)
|R ⟕ S|  =  |R ⋈ S|  +  |R ▷ S|                         5 = 3 + 2
|R ⋉ S| + |R ▷ S|  =  |R|                               2 + 2 = 4
```

The third line is the one that catches bugs. `buyer_id` is the key of `buyers`, so each purchase matches **at most one** buyer, and the join can never have more rows than `purchases`. If a join between a fact table and a "dimension" returns more rows than the fact table had, the key is not unique: a duplicate crept into the dimension.

### Step 3. Three-valued logic

SQL's comparisons can give three answers: TRUE, FALSE and UNKNOWN (written U below). Any comparison with NULL is UNKNOWN, including `NULL = NULL`. `AND`, `OR` and `NOT` then follow these tables (this is Kleene's three-valued logic):

```text
 AND | T  U  F         OR | T  U  F         NOT
 ----+---------        ---+---------        ------
  T  | T  U  F         T  | T  T  T          T | F
  U  | U  U  F         U  | T  U  U          U | U
  F  | F  F  F         F  | T  U  F          F | T
```

A trick to remember them: think of U as "TRUE or FALSE, we do not know which". `T AND U` could be either, so it is U. `F AND U` is FALSE whatever U is. `T OR U` is TRUE whatever U is.

The last rule is the one that matters: **`WHERE` keeps a row only when its condition is TRUE.** FALSE and UNKNOWN are both thrown away.

### Step 4. NOT IN by hand

`buyer_id NOT IN (list)` means "different from every item in the list", which is an `AND` of `<>` comparisons. The subquery returns the list (1, 1, 3, NULL). For Ben, `buyer_id = 2`:

```text
2 NOT IN (1, 1, 3, NULL)
  = (2 <> 1) AND (2 <> 1) AND (2 <> 3) AND (2 <> NULL)
  =    T     AND    T     AND    T     AND     U
  =  U                                        -> not TRUE, row dropped
```

For Ana, `1 <> 1` is FALSE, so the whole `AND` is FALSE: also dropped, correctly. Every buyer ends up with FALSE or UNKNOWN, never TRUE. Version A of 1.1 returns nothing.

`NOT EXISTS` asks a different question: "is there a row in purchases with `p.buyer_id = 2` TRUE?" Looking down Ben's row of the grid: false, false, false, unknown. No TRUE, so no such row exists, so `NOT EXISTS` is TRUE and Ben is kept.

## 1.4 Why it is true

**Pushdown.** If a condition `p` uses only columns of R, then

```text
σp( R × S )  =  σp(R) × S
```

*Proof.* A pair (r, s) is in the left side exactly when `p` is TRUE for it. Since `p` reads only r's columns, its value is the same for every s. So the pair is kept exactly when `p(r)` is TRUE and s is any row of S: that is the right side. ∎

This is the most useful law in query planning: filter a table **before** joining it, so the join sees fewer rows. Because a join is a selection over a product, the law carries over to joins: `σp(R ⋈ S) = σp(R) ⋈ S` when `p` reads only R. Section 1.5 shows PostgreSQL doing exactly this.

**Filters on the right side of a left join.** Call a condition `p` on S's columns **null-rejecting** if it is not TRUE when all of S's columns are NULL. `amount > 30` is null-rejecting: `NULL > 30` is UNKNOWN. Then

```text
σp( R ⟕ S )  =  σp( R ⋈ S )         for a null-rejecting p on S
```

*Proof.* R ⟕ S is the join rows plus the padded rows (r, NULL, ..., NULL). On a padded row, every column of S is NULL, so `p` is not TRUE (that is what null-rejecting means), and `WHERE` drops it. Only join rows can survive, and on them both sides apply the same `p`. ∎

So `LEFT JOIN ... WHERE right_table.column > 30` is an inner join wearing a disguise. If you meant "all buyers, plus their big purchases if any", the condition belongs in the `ON` clause, where it decides which pairs match instead of which rows survive.

**NOT IN and NULL.** Suppose the subquery returns at least one NULL. Then `x NOT IN (...)` is an `AND` that contains the term `x <> NULL`, which is UNKNOWN. By the AND table, a conjunction with a U in it is U or F, never T. So `WHERE x NOT IN (...)` keeps no row at all. ∎

And when are the two versions equal? If the subquery's column has **no NULLs** and `x` is not NULL, every `<>` is TRUE or FALSE, and `x NOT IN (list)` is TRUE exactly when no item equals `x`, which is exactly when `NOT EXISTS` finds no matching row. There is one more corner: if `x` itself is NULL, `x NOT IN (non-empty list)` is UNKNOWN (dropped), while `NOT EXISTS (... WHERE p.col = x)` is TRUE (kept), because `p.col = NULL` is never TRUE and so no row exists. Exercise 4 runs it.

**Two laws that break.** In ordinary two-valued logic, `p OR NOT p` is always TRUE (the law of the excluded middle). In SQL it is UNKNOWN when `p` is UNKNOWN, so `WHERE x = 1 OR NOT (x = 1)` does **not** return every row: it skips rows where `x` is NULL. And `x = x` is not always TRUE either. De Morgan's laws, on the other hand, still hold in three-valued logic: `NOT (p AND q) = (NOT p) OR (NOT q)`, which you can check from the tables (exercise 3).

## 1.5 See it in the database

### The grid, from SQL

The product has 16 rows; the join keeps 3:

<!-- sql -->
```sql
SELECT (SELECT COUNT(*) FROM buyers CROSS JOIN purchases) AS product_rows,
       (SELECT COUNT(*) FROM buyers b JOIN purchases p ON p.buyer_id = b.buyer_id) AS join_rows,
       (SELECT COUNT(*) FROM buyers b LEFT JOIN purchases p ON p.buyer_id = b.buyer_id) AS left_join_rows;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| product_rows | join_rows | left_join_rows |
| --- | --- | --- |
| 16 | 3 | 5 |
<!-- /result -->

<!-- sql -->
```sql
SELECT b.name, p.purchase_id, p.amount
FROM buyers b
LEFT JOIN purchases p ON p.buyer_id = b.buyer_id
ORDER BY b.buyer_id, p.purchase_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| name | purchase_id | amount |
| --- | --- | --- |
| Ana | 10 | 50 |
| Ana | 11 | 20 |
| Ben | *NULL* | *NULL* |
| Cai | 12 | 70 |
| Dee | *NULL* | *NULL* |
<!-- /result -->

### NOT IN against NOT EXISTS

Version A, `NOT IN`:

<!-- sql -->
```sql
SELECT name FROM buyers
WHERE buyer_id NOT IN (SELECT buyer_id FROM purchases)
ORDER BY name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

| name |
| --- |
| *(no rows)* |
<!-- /result -->

Version B, `NOT EXISTS`:

<!-- sql -->
```sql
SELECT name FROM buyers b
WHERE NOT EXISTS (SELECT 1 FROM purchases p WHERE p.buyer_id = b.buyer_id)
ORDER BY name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| name |
| --- |
| Ben |
| Dee |
<!-- /result -->

Removing the NULLs from the list makes them agree, as the proof in 1.4 says:

<!-- sql -->
```sql
SELECT name FROM buyers
WHERE buyer_id NOT IN (SELECT buyer_id FROM purchases WHERE buyer_id IS NOT NULL)
ORDER BY name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| name |
| --- |
| Ben |
| Dee |
<!-- /result -->

### The planner uses the same algebra

PostgreSQL's plan for a `NOT EXISTS` is an **anti join**, the operation of 1.2. For `NOT IN` it cannot use one, because the two are not the same operation when NULLs are possible; it runs the subquery and tests every row with it:

<!-- sql pg -->
```sql
EXPLAIN (COSTS OFF)
SELECT name FROM buyers b
WHERE NOT EXISTS (SELECT 1 FROM purchases p WHERE p.buyer_id = b.buyer_id);
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 5 rows.</p>

| QUERY PLAN |
| --- |
| Hash Right Anti Join |
|   Hash Cond: (p.buyer_id = b.buyer_id) |
|   ->  Seq Scan on purchases p |
|   ->  Hash |
|         ->  Seq Scan on buyers b |
<!-- /result -->

<!-- sql pg -->
```sql
EXPLAIN (COSTS OFF)
SELECT name FROM buyers WHERE buyer_id NOT IN (SELECT buyer_id FROM purchases);
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

| QUERY PLAN |
| --- |
| Seq Scan on buyers |
|   Filter: (NOT (hashed SubPlan 1)) |
|   SubPlan 1 |
|     ->  Seq Scan on purchases |
<!-- /result -->

In the first plan, `Hash Right Anti Join` is the anti join; "Right" only says PostgreSQL built its hash table from `buyers` and streamed `purchases` past it. In the second, `NOT (hashed SubPlan 1)` tests each buyer against the subquery's list, with the NULL rule of 1.3 applied.

Pushdown: the condition on `city` is applied while scanning `buyers`, before the join:

<!-- sql pg -->
```sql
EXPLAIN (COSTS OFF)
SELECT b.name, p.amount
FROM buyers b JOIN purchases p ON p.buyer_id = b.buyer_id
WHERE b.city = 'Toronto';
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 6 rows.</p>

| QUERY PLAN |
| --- |
| Hash Join |
|   Hash Cond: (p.buyer_id = b.buyer_id) |
|   ->  Seq Scan on purchases p |
|   ->  Hash |
|         ->  Seq Scan on buyers b |
|               Filter: ((city)::text = 'Toronto'::text) |
<!-- /result -->

And the disguised inner join: with a null-rejecting `WHERE` on the right table, PostgreSQL drops the "left" from the join, exactly as the second proof of 1.4 allows. The plan says `Hash Join`, not `Hash Left Join`, and the amount filter has been pushed down onto the scan of `purchases`:

<!-- sql pg -->
```sql
EXPLAIN (COSTS OFF)
SELECT b.name, p.amount
FROM buyers b LEFT JOIN purchases p ON p.buyer_id = b.buyer_id
WHERE p.amount > 30;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 6 rows.</p>

| QUERY PLAN |
| --- |
| Hash Join |
|   Hash Cond: (p.buyer_id = b.buyer_id) |
|   ->  Seq Scan on purchases p |
|         Filter: (amount > 30) |
|   ->  Hash |
|         ->  Seq Scan on buyers b |
<!-- /result -->

The rows confirm it: Ben and Dee are gone.

<!-- sql -->
```sql
SELECT b.name, p.amount
FROM buyers b LEFT JOIN purchases p ON p.buyer_id = b.buyer_id
WHERE p.amount > 30
ORDER BY b.name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| name | amount |
| --- | --- |
| Ana | 50 |
| Cai | 70 |
<!-- /result -->

Moving the condition into `ON` keeps every buyer, and only decides which purchases count as a match:

<!-- sql -->
```sql
SELECT b.name, p.amount
FROM buyers b LEFT JOIN purchases p ON p.buyer_id = b.buyer_id AND p.amount > 30
ORDER BY b.name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| name | amount |
| --- | --- |
| Ana | 50 |
| Ben | *NULL* |
| Cai | 70 |
| Dee | *NULL* |
<!-- /result -->

### The excluded middle, failing

`buyer_id = 1 OR NOT (buyer_id = 1)` looks as if it must be TRUE for every row. Purchase 13 disagrees:

<!-- sql -->
```sql
SELECT purchase_id FROM purchases
WHERE buyer_id = 1 OR NOT (buyer_id = 1)
ORDER BY purchase_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| purchase_id |
| --- |
| 10 |
| 11 |
| 12 |
<!-- /result -->

### Bags, not sets

Codd's relations are sets: no row twice. SQL tables are **bags** (multisets): the same row may appear several times, and a projection keeps the duplicates unless you ask for `DISTINCT`. The cities of the buyers, as a bag, are Toronto ×2, Lagos ×1, Oslo ×1; the `stores` table holds Toronto ×1, Oslo ×2. For a row that appears m times on the left and n times on the right:

```text
UNION ALL      m + n            UNION       1 if m + n > 0
INTERSECT ALL  min(m, n)        INTERSECT   1 if both m > 0 and n > 0
EXCEPT ALL     max(m − n, 0)    EXCEPT      1 if m > 0 and n = 0
```

By hand: `UNION ALL` gives Toronto 3, Lagos 1, Oslo 3 (7 rows); `INTERSECT ALL` gives Toronto min(2, 1) = 1 and Oslo min(1, 2) = 1; `EXCEPT ALL` gives Toronto 2 − 1 = 1, Lagos 1, Oslo max(1 − 2, 0) = 0.

<!-- sql -->
```sql
SELECT city, COUNT(*) AS times
FROM (SELECT city FROM buyers UNION ALL SELECT city FROM stores) AS u
GROUP BY city ORDER BY city;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| city | times |
| --- | --- |
| Lagos | 1 |
| Oslo | 3 |
| Toronto | 3 |
<!-- /result -->

SQLite has `UNION ALL` but not `INTERSECT ALL` or `EXCEPT ALL`, so these two ran on PostgreSQL only:

<!-- sql pg -->
```sql
SELECT city FROM buyers INTERSECT ALL SELECT city FROM stores ORDER BY city;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

| city |
| --- |
| Oslo |
| Toronto |
<!-- /result -->

<!-- sql pg -->
```sql
SELECT city FROM buyers EXCEPT ALL SELECT city FROM stores ORDER BY city;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

| city |
| --- |
| Lagos |
| Toronto |
<!-- /result -->

## 1.6 Where it breaks

- **Order is not part of the algebra.** A relation has no first row. Without `ORDER BY` the database may return rows in any order, and it may change between runs.
- **NULL is "equal" in some places and not others.** In a join or `WHERE`, `NULL = NULL` is UNKNOWN. But `GROUP BY`, `DISTINCT`, `UNION` and `INTERSECT` put NULLs together, as if they were equal (the SQL standard calls them "not distinct"). Keep the two rules apart.
- **Outer joins do not reorder freely.** Inner joins can be done in any order (they are a product plus a selection, and products commute up to column order and associate). Left and full joins cannot always be reordered, which limits what a planner may do. Tutorial 3 is about join order.
- **Bag laws differ from set laws.** In sets, `R ∪ R = R`; in bags, `R UNION ALL R` has every row twice. Selection still pushes through bag products, so the pushdown proof stands, but a law about duplicates must be checked for bags separately.
- **The planner is not obliged to use the laws.** They say which rewrites are allowed, not which ones a given database version performs. The plans above are from PostgreSQL 16 on these tiny tables.

## 1.7 Exercises

Do 1 to 5 with a pencil. 6 and 7 need only a few lines of thought. 8 is SQL.

**E1. Add a fifth purchase, (14, 3, 90). Without running anything, how many rows do the product, the join, the left join, the semi join and the anti join now have?**

??? success "Answer"
    Product 4 × 5 = 20. Join: Cai gets a second match, so 4. Left join: 4 join rows + Ben and Dee padded = 6. Semi join: still Ana and Cai, 2 (each buyer once). Anti join: still Ben and Dee, 2. Check: semi + anti = 2 + 2 = 4 = |buyers|.

**E2. Fill in: `T AND U`, `F OR U`, `NOT U`, `U AND F`, `U OR T`, `(T AND U) OR F`.**

??? success "Answer"
    U, U, U, F, T, and `(T AND U) OR F = U OR F = U`.

**E3. Check De Morgan's law `NOT (p AND q) = (NOT p) OR (NOT q)` for all nine pairs of values of p and q in three-valued logic.**

??? success "Answer"
    | p | q | p AND q | NOT (p AND q) | NOT p | NOT q | (NOT p) OR (NOT q) |
    | --- | --- | --- | --- | --- | --- | --- |
    | T | T | T | F | F | F | F |
    | T | U | U | U | F | U | U |
    | T | F | F | T | F | T | T |
    | U | T | U | U | U | F | U |
    | U | U | U | U | U | U | U |
    | U | F | F | T | U | T | T |
    | F | T | F | T | T | F | T |
    | F | U | F | T | T | U | T |
    | F | F | F | T | T | T | T |

    The two columns agree in all nine rows, so De Morgan's law holds. (The excluded middle `p OR NOT p` does not: it is U when p is U.)

**E4. A purchase can also have a buyer who is not in `buyers` at all. Now take the reverse question: which purchases have no buyer in `buyers`? Compare `WHERE buyer_id NOT IN (SELECT buyer_id FROM buyers)` with `NOT EXISTS`. Which returns purchase 13, and why?**

??? success "Answer"
    `buyers.buyer_id` has no NULLs (it is the key), so the list is (1, 2, 3, 4). For purchase 13, `NULL NOT IN (1, 2, 3, 4)` is `NULL <> 1 AND ...`, all U, so U: dropped. `NOT EXISTS (SELECT 1 FROM buyers b WHERE b.buyer_id = p.buyer_id)` finds no row where `b.buyer_id = NULL` is TRUE, so it is TRUE: purchase 13 is kept.

    <!-- sql -->
    ```sql
    SELECT 'not in' AS version, purchase_id FROM purchases
    WHERE buyer_id NOT IN (SELECT buyer_id FROM buyers)
    UNION ALL
    SELECT 'not exists', purchase_id FROM purchases p
    WHERE NOT EXISTS (SELECT 1 FROM buyers b WHERE b.buyer_id = p.buyer_id)
    ORDER BY version, purchase_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | version | purchase_id |
    | --- | --- |
    | not exists | 13 |
    <!-- /result -->

    This is the corner case of 1.4: a NULL on the **outside** of `NOT IN` is also dropped. Which answer is right depends on the question; "purchases with no known buyer" wants 13.

**E5. `orders` has 1,000,000 rows and `customers` has 50,000 rows with `customer_id` as the key. An inner join on `customer_id` returns 1,000,350 rows. What do you conclude?**

??? success "Answer"
    If `customer_id` were really unique in `customers`, each order would match at most one customer, and the join could have at most 1,000,000 rows. 350 extra rows mean some `customer_id` values appear more than once in `customers`. Find them with `SELECT customer_id, COUNT(*) FROM customers GROUP BY customer_id HAVING COUNT(*) > 1`.

**E6. Is `WHERE p.amount > 30 OR p.amount IS NULL` null-rejecting? What does a left join with this `WHERE` return on our tables?**

??? success "Answer"
    No: on a padded row `amount` is NULL, so `p.amount IS NULL` is TRUE and the row survives. The left join keeps (Ana, 50), (Cai, 70), (Ben, NULL), (Dee, NULL); it drops (Ana, 20). Note that it would also keep a real purchase whose amount is NULL, which is a different thing from "no purchase". That is why the `ON` version of 1.5 is usually what is meant.

**E7. Prove that `σp(σq(R)) = σ(p AND q)(R)` in three-valued logic.**

??? success "Answer"
    A row survives the left side exactly when `q` is TRUE (inner filter) and then `p` is TRUE (outer filter). It survives the right side exactly when `p AND q` is TRUE. From the AND table, `p AND q` is TRUE only when both are TRUE (any U or F gives U or F). So the two sides keep the same rows. ∎

**E8. (SQL.) Write a query that lists every buyer with the number of their purchases over 30, showing 0 for buyers with none. Predict the four rows first.**

??? success "Answer"
    Put the amount condition in the `ON` clause and count a column of `purchases`, not `*`, so padded rows count 0:

    <!-- sql -->
    ```sql
    SELECT b.name, COUNT(p.purchase_id) AS big_purchases
    FROM buyers b
    LEFT JOIN purchases p ON p.buyer_id = b.buyer_id AND p.amount > 30
    GROUP BY b.buyer_id, b.name
    ORDER BY b.name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | name | big_purchases |
    | --- | --- |
    | Ana | 1 |
    | Ben | 0 |
    | Cai | 1 |
    | Dee | 0 |
    <!-- /result -->

    `COUNT(*)` would count the padded rows and give Ben and Dee 1. With the condition in `WHERE`, Ben and Dee would disappear (1.4).

## 1.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a query that returned too many or too few rows, and the operation that explained it.)*

## 1.9 Further reading

On your own sites:

- Truth tables and logical laws: [Logic, ch 2. Propositional logic](https://math.akadian.ca/books/logic/02-Propositional-Logic.html); sets: [Logic, ch 5. Sets](https://math.akadian.ca/books/logic/05-Sets.html); relations: [Logic, ch 6. Relations and functions](https://math.akadian.ca/books/logic/06-Relations-and-Functions.html); other logics, including many-valued ones: [Logic, ch 19. Other logics](https://math.akadian.ca/books/logic/19-Other-Logics.html)
- The SQL side: [6. NULL and three-valued logic](../../databases/sql/06-Null-and-Three-Valued-Logic.md), [8. Joins](../../databases/sql/08-Joins-Inner-Left-Right-Full-Cross.md), [9. Self, semi and anti joins](../../databases/sql/09-Self-Semi-and-Anti-Joins.md), [12. Set operations](../../databases/sql/12-Set-Operations.md)

Original sources:

- E. F. Codd, "A Relational Model of Data for Large Shared Data Banks", *Communications of the ACM* 13(6), 1970. The paper that introduced relations, and an algebra over them, as the model for databases.
- [PostgreSQL 16: Using EXPLAIN](https://www.postgresql.org/docs/16/using-explain.html), for reading the plans above.

## Glossary

- **Relation**: a set of rows with the same named columns; a table in Codd's model.
- **Selection (σ)**: keep the rows where a condition is TRUE; SQL `WHERE`.
- **Projection (π)**: keep some columns; SQL `SELECT col, ...`.
- **Product (×)**: every row of one table paired with every row of the other; SQL `CROSS JOIN`.
- **Join (⋈)**: a product followed by a selection.
- **Semi join (⋉)**: rows of R with at least one match in S; SQL `EXISTS`.
- **Anti join (▷)**: rows of R with no match in S; SQL `NOT EXISTS`.
- **Three-valued logic**: logic with TRUE, FALSE and UNKNOWN; SQL's logic for NULL.
- **Null-rejecting condition**: a condition that is not TRUE when the columns it reads are all NULL.
- **Pushdown**: applying a filter before a join instead of after it; allowed when the filter reads only one side.
- **Bag (multiset)**: a collection where a row can appear more than once; what SQL tables really are.
