# 2. Why an index is fast: B-tree height by hand

*A table with 100 million rows takes up hundreds of thousands of pages on disk, yet a lookup by key reads four or five of them. This tutorial works out why, with nothing but division: how many keys fit on one page, how many pages sit on each level of the tree, and how many levels that makes. It then proves the bound that keeps every B-tree short, builds and splits a small one by hand, and checks every number against real PostgreSQL 16 indexes of a thousand to a hundred million rows. The last part is about when an index does not help, and what it costs on every write.*

!!! abstract "In this tutorial"
    **You will learn:**

    - why a database reads and writes whole pages, and how many keys fit on one
    - fan-out and height: why each level of a B-tree divides the work by about 300, and why that makes the height a logarithm
    - how a B-tree grows: inserts, page splits, and why the tree only ever grows at the top
    - the height bound, proved by counting, and what it says for 100 million rows (exactly four levels)
    - how to measure a real index's levels and pages with PostgreSQL's `pgstattuple` and `pageinspect`, and a lookup's page reads with `EXPLAIN (ANALYZE, BUFFERS)`
    - when an index does not help (too many matches, a function on the column), and the price every insert pays

    **You need:** what a logarithm is ([Algebra, ch 7. Exponents and logarithms](https://math.akadian.ca/books/algebra/07-Exponents-and-Logarithms.html) if it is rusty), and basic SQL. The practical side is in the [SQL course](../../databases/sql/index.md), chapters [25. Indexes and EXPLAIN](../../databases/sql/25-Indexes-and-Explain.md) and [26. Making slow queries fast](../../databases/sql/26-Making-Slow-Queries-Fast.md).

    **How to learn from it:** read 2.1 to 2.3, close the page, redo the level count for 100 million rows and the two inserts of 2.3 on paper, then try the exercises in 2.7 before opening any answer. Plan about three hours.

**About the examples.** The PostgreSQL numbers come from three Python scripts that build real tables and indexes on PostgreSQL 16 and print what the database reports; each section links the script and its full output. The SQLite plans ran through the IT site's test runner, which writes the real result under each query. Parallel workers were turned off in the scripts, so each plan prints one page count instead of one per worker.

## 2.1 The question

A table holds 100 million orders, numbered 1 to 100,000,000. This query returns one row:

```sql
SELECT * FROM big WHERE order_id = 76543210;
```

With an index on `order_id`, PostgreSQL reports that it touched **5 pages** to answer it. The table itself fills **442,478 pages**. Without the index the database must read all of them, because the row could be anywhere.

Five out of 442,478. Where does that number come from, and why would a table a hundred times bigger need only one more page? By the end of this tutorial you will be able to predict the five, and prove that no B-tree on these keys can need more.

## 2.2 The idea: a table of contents for the table of contents

A database never reads one row from disk. It reads a **page**, a fixed block of bytes; PostgreSQL's page is 8 kB (8,192 bytes). Reading a page costs about the same whether you need one byte of it or all of it, so the question "how fast is a lookup?" becomes "how many pages does it read?".

A **B-tree index** is a stack of pages built on that fact:

- The bottom level, the **leaves**, holds every key in sorted order, each with the address of its row in the table. A leaf page holds a few hundred keys.
- One level up, each page holds one signpost per leaf page: "keys from 5,000 on are in leaf 14". So one page there covers a few hundred leaves.
- The next level up covers a few hundred of those pages, and so on, until a single page, the **root**, covers everything.

The number of children one page can point to is the **fan-out**, f. Each level up divides the number of pages by about f. With f in the hundreds, a few levels are enough for any table that fits on Earth. A lookup starts at the root, follows one signpost per level, and reads one page per level: the height of the tree is the number of index pages it reads.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 275" role="img" aria-label="Four rows of boxes. Top: the root, one page. Second: level 1, 97 pages, a few drawn. Third: leaves, 27,323 pages, a few drawn. Bottom: the table, 54,055 pages, drawn as one long strip. A thick path goes from the root, numbered 1, to one level 1 page, numbered 2, to one leaf, numbered 3, to one page of the table, numbered 4. Thin lines show the other branches not taken.">
<g font-size="13" fill="currentColor">
<text x="10" y="36" font-weight="bold">root</text><text x="10" y="52">1 page</text>
<text x="10" y="104" font-weight="bold">level 1</text><text x="10" y="120">97 pages</text>
<text x="10" y="174" font-weight="bold">leaves</text><text x="10" y="190">27,323 pages</text>
<text x="10" y="244" font-weight="bold">table</text><text x="10" y="260">54,055 pages</text>
<text x="315" y="41" text-anchor="middle" font-weight="bold">1</text>
<text x="368" y="110" text-anchor="middle" font-weight="bold">2</text>
<text x="366" y="179" text-anchor="middle" font-weight="bold">3</text>
<text x="430" y="250" text-anchor="middle" font-weight="bold">4</text>
<text x="300" y="108">…</text><text x="474" y="108">…</text>
<text x="250" y="177">…</text><text x="452" y="177">…</text>
</g>
<g fill="none" stroke="currentColor">
<rect x="275" y="18" width="80" height="32" rx="4" stroke-width="3"/>
<rect x="120" y="90" width="56" height="28" rx="4" stroke-width="1.2"/>
<rect x="186" y="90" width="56" height="28" rx="4" stroke-width="1.2"/>
<rect x="340" y="90" width="56" height="28" rx="4" stroke-width="3"/>
<rect x="406" y="90" width="56" height="28" rx="4" stroke-width="1.2"/>
<rect x="540" y="90" width="56" height="28" rx="4" stroke-width="1.2"/>
<rect x="120" y="160" width="40" height="26" rx="3" stroke-width="1.2"/>
<rect x="166" y="160" width="40" height="26" rx="3" stroke-width="1.2"/>
<rect x="300" y="160" width="40" height="26" rx="3" stroke-width="1.2"/>
<rect x="346" y="160" width="40" height="26" rx="3" stroke-width="3"/>
<rect x="392" y="160" width="40" height="26" rx="3" stroke-width="1.2"/>
<rect x="490" y="160" width="40" height="26" rx="3" stroke-width="1.2"/>
<rect x="560" y="160" width="40" height="26" rx="3" stroke-width="1.2"/>
<rect x="120" y="230" width="500" height="28" rx="3" stroke-width="1.2" stroke-dasharray="4 3"/>
<rect x="418" y="232" width="24" height="24" rx="2" stroke-width="3"/>
</g>
<g stroke="currentColor" stroke-width="1" opacity="0.6">
<line x1="315" y1="50" x2="148" y2="90"/><line x1="315" y1="50" x2="214" y2="90"/>
<line x1="315" y1="50" x2="434" y2="90"/><line x1="315" y1="50" x2="568" y2="90"/>
<line x1="368" y1="118" x2="320" y2="160"/><line x1="368" y1="118" x2="412" y2="160"/>
</g>
<g stroke="currentColor" stroke-width="3">
<line x1="320" y1="50" x2="364" y2="90"/><line x1="368" y1="118" x2="366" y2="160"/><line x1="370" y1="186" x2="428" y2="232"/>
</g>
</svg>
<figcaption>Figure 2.1. The real index of 2.5 on a 10 million row table: 3 levels, then the table. One lookup reads the four numbered pages and no others.</figcaption>
</figure>

Compare a balanced **binary** search tree, where each node has 2 children: 100 million keys need about log₂ 100,000,000 ≈ 27 levels, so 27 reads. A B-tree gets its short height from one change: it makes each node a whole page and fills it with hundreds of keys, so each read gives hundreds of choices instead of two.

## 2.3 The math by hand

### Step 1. How many keys fit on a page

The index in the question has a `bigint` key (8 bytes). On a PostgreSQL leaf page, each key is stored as one **index entry** of 16 bytes (an 8-byte header holding the row's address, then the key), plus a 4-byte slot in a list at the top of the page that points to it: 20 bytes in all. The page gives 24 bytes to its header and 16 to B-tree bookkeeping at the end:

```text
space for entries   = 8192 − 24 − 16 = 8152 bytes
entries per page    = ⌊8152 / 20⌋    = 407
```

So a full page holds 407 entries. `CREATE INDEX` deliberately leaves 10% of each leaf empty (the default *fillfactor* of 90, so that later inserts fit without splitting at once), and one entry on every leaf but the last is a "high key" marking the page's upper bound. The real count, measured in 2.5, is **366 rows per leaf page**. Upper pages are filled to about 70% when the index is built, about **284 children** each.

### Step 2. Count the levels for 100 million rows

Divide, round up, repeat until one page is left:

| Level | Pages | How |
| --- | --- | --- |
| leaves (level 0) | 273,225 | ⌈100,000,000 / 366⌉ |
| level 1 | 963 | ⌈273,225 / 284⌉ |
| level 2 | 4 | ⌈963 / 284⌉ |
| root (level 3) | 1 | ⌈4 / 284⌉ |

**Four levels.** A lookup reads one page on each: four index pages, and then one page of the table to fetch the row. That is the 5 of 2.1. The table has 442,478 pages because a table row (with its own 24-byte header) is much wider than an index entry and the table holds every column.

The same count in one line: with L leaf pages and fan-out f, the number of levels is about

```text
levels ≈ 1 + ⌈log_f L⌉ = 1 + ⌈log₂₈₄ 273,225⌉ = 1 + ⌈2.22⌉ = 4
```

Turn it around: 4 levels hold up to 366 × 284³ ≈ 8.4 billion rows, and 3 levels hold up to 366 × 284² ≈ 29.5 million. A table must grow almost 300 times before it needs one more level.

### Step 3. A small B-tree, built by hand

Real pages hold hundreds of keys, too many to draw. The same rules work with tiny nodes. Here is a B-tree of **order 3**: each node holds 1 or 2 keys, and an inner node with k keys has k + 1 children. These are the rules:

1. **Search:** in a node, go to the child between the two keys your key falls between.
2. **Insert:** search down to a leaf and put the key there, in order.
3. **Split:** if a node now holds 3 keys, cut it in two and send the middle key up to the parent. If that makes the parent hold 3 keys, split it too.
4. **Grow:** if the root splits, its middle key becomes a new root above it. This is the only way the tree gets taller.

Start with this tree of 11 keys and 3 levels:

```text
                 [50]
        [20]              [70 85]
  [10 15]    [30]    [60]  [75 80]  [90]
```

**Search 80.** Root: 80 > 50, go right. [70 85]: 80 is between 70 and 85, go to the middle child. [75 80]: found. Three nodes read, one per level.

**Insert 12.** 12 < 50, then 12 < 20, so it goes into the leaf [10 15], which becomes [10 12 15]: three keys, too many. Split it into [10] and [15] and send 12 up to the parent, which becomes [12 20]. The parent had room, so we stop.

```text
                   [50]
        [12 20]                [70 85]
  [10]   [15]   [30]     [60]  [75 80]  [90]
```

**Insert 78.** It goes to the leaf [75 80], which becomes [75 78 80]. Split: [75] and [80], and 78 goes up. The parent [70 85] becomes [70 78 85]: too many again. Split it: [70] and [85], and 78 goes up again, into the root, which becomes [50 78]. The root had room, so the height stays 3.

```text
                       [50 78]
        [12 20]          [70]           [85]
  [10]   [15]   [30]   [60]  [75]    [80]  [90]
```

Two things to notice. First, every leaf is still exactly 3 levels below the root: a split adds a node **beside** another one, never below it, and the only new level is a new root at the **top**, which lengthens every path by one at the same time. So the tree is always perfectly balanced, whatever order the keys arrive in. Second, every node made by a split holds at least 1 key out of a possible 2: at least half full. That is the fact the proof in 2.4 rests on.

**The real thing is a B+ tree.** In this drawing, keys sit in inner nodes too. PostgreSQL, like most databases, uses the **B+ tree** variant: every key is in a leaf, the inner pages hold only signpost copies, and each leaf links to the next one, so a range (`BETWEEN 1000 AND 1100`) is one descent and then a walk along the leaves. The splitting rules and the height argument are the same. The script [ex03_btree_by_hand.py](src/02/ex03_btree_by_hand.py) replays these inserts ([output](src/02/ex03.out.txt)).

## 2.4 Why it is true

Take a B-tree of **order m**: an inner node has at most m children. Assume the two properties of 2.3:

- **(A) Balanced.** All leaves are at the same depth. Say the tree has h levels.
- **(B) Half full.** Every inner node except the root has at least d = ⌈m/2⌉ children, and the root, if it is not a leaf, has at least 2.

**Claim.** If the tree has L leaves and h ≥ 2 levels, then

```text
2 · d^(h−2)  ≤  L  ≤  m^(h−1)        so        1 + log_m L  ≤  h  ≤  2 + log_d (L/2)
```

**Proof, by counting nodes level by level.** Level 1 is the root: 1 node. Every node has at most m children, so level k has at most m^(k−1) nodes, and the leaves, on level h, number at most m^(h−1). For the other side: the root has at least 2 children, so level 2 has at least 2 nodes; each of those has at least d children, so level 3 has at least 2d, and level k has at least 2·d^(k−2). The leaves number at least 2·d^(h−2). Taking logarithms of both inequalities gives the bounds on h. ∎

**Why (A) and (B) hold.** Both are kept by the insert rules, by induction over the inserts. (A): a split puts the new node on the same level as the old one, and a root split adds one level to every path at once. (B): a node splits when it has m + 1 children, into two nodes of ⌈(m+1)/2⌉ and ⌊(m+1)/2⌋ children, and ⌊(m+1)/2⌋ = ⌈m/2⌉ = d for every whole number m (check m = 3: 4 children split 2 and 2, and d = 2). A textbook B-tree also keeps (B) on delete, by merging or borrowing from a neighbour; PostgreSQL does not, which is the first entry in 2.6.

**What it says for PostgreSQL pages.** From Step 1, m = 407, so d = 204. Leaves hold between half a page and a full page of rows, 203 to 406, so 100 million rows need between 246,306 and 492,610 leaves. Now test values of h:

| h | most leaves, m^(h−1) | fewest leaves, 2·d^(h−2) | possible for 246,306 to 492,610 leaves? |
| --- | --- | --- | --- |
| 3 | 165,649 | 408 | no: 165,649 is too few, even at best |
| 4 | 67,419,143 | 83,232 | yes |
| 5 | 27,439,591,201 | 16,979,328 | no: 16,979,328 is too many, even at worst |

So **any** B-tree on 100 million `bigint` keys in 8 kB pages, filled anywhere between half and full, has exactly 4 levels. The estimate of Step 2 was not luck: there was no other possible answer.

The same test for other sizes, worked by the script, shows how slowly the height grows:

| Rows | Fewest levels possible | Most levels possible | A fresh `CREATE INDEX` gives |
| --- | --- | --- | --- |
| 1,000 | 2 | 2 | 2 |
| 100,000 | 2 | 3 | 2 |
| 10,000,000 | 3 | 3 | 3 |
| 100,000,000 | 4 | 4 | 4 |
| 1,000,000,000 | 4 | 4 | 4 |
| 10,000,000,000 | 4 | 5 | 5 |
| 1,000,000,000,000 | 5 | 6 | 5 |

A thousand rows and a trillion rows differ by a factor of a billion, and by three page reads.

**A rule of thumb, labelled as one.** "Height ≈ log_f N" with f a few hundred is the version people quote. The bound above is the theorem; the rule of thumb is its middle.

## 2.5 See it in the database

### The shape of real indexes

The script [ex01_btree_levels.py](src/02/ex01_btree_levels.py) builds tables of 1 thousand, 100 thousand and 10 million rows with a `bigint` key, indexes the key, and asks PostgreSQL about the tree. `pgstatindex()` (from the `pgstattuple` extension) gives the levels and page counts; `bt_page_stats()` (from `pageinspect`) gives the contents of one page. [ex02_hundred_million.py](src/02/ex02_hundred_million.py) does the same for the 100 million rows of the question. Real output ([ex01](src/02/ex01.out.txt), [ex02](src/02/ex02.out.txt)):

| Rows | Levels | Leaf pages | Upper pages | Root's children | Rows per leaf | Leaves full |
| --- | --- | --- | --- | --- | --- | --- |
| 1,000 | 2 | 3 | 1 | 3 | 366 | 82.0% |
| 100,000 | 2 | 274 | 1 | 274 | 366 | 89.8% |
| 10,000,000 | 3 | 27,323 | 98 | 97 | 366 | 90.1% |
| 100,000,000 | 4 | 273,225 | 968 | not measured | not measured | 90.1% |

Check them against the hand count. For 10 million rows: ⌈10,000,000 / 366⌉ = 27,323 leaves, exactly; ⌈27,323 / 284⌉ = 97 pages on level 1, exactly the root's 97 children; plus the root, 98 upper pages. For 100 million: 273,225 leaves, exactly Step 2's count, and 963 + 4 + 1 = 968 upper pages, exactly. The 1,000-row index is only 82% full because its last leaf is partly empty.

One leaf page of the 10 million row index, from `bt_page_stats`: 367 items (366 rows and the high key), each 16 bytes, on an 8,192-byte page with 808 bytes free. That is Step 1's 20 bytes per entry and the 10% left free.

### One lookup, page by page

`EXPLAIN (ANALYZE, BUFFERS)` runs the query and counts the pages it touched ("shared hit" = found in memory, "read" = fetched from disk; both are page reads for this tutorial's purpose). On the 10 million row table:

```text
Index Scan using orders_10000000_id on orders_10000000 (actual rows=1 loops=1)
  Index Cond: (order_id = 7654321)
  Buffers: shared hit=4
```

Four pages: 3 index levels and 1 table page, the four numbered pages of Figure 2.1. On 100 million rows:

```text
Index Scan using big_id on big (actual rows=1 loops=1)
  Index Cond: (order_id = 76543210)
  Buffers: shared hit=5
```

Five: 4 index levels and 1 table page, as predicted in 2.1. (That table has only the key column, so PostgreSQL can also answer from the index alone, an *index-only scan*. It also touched 5 pages: 4 of the index and 1 of the *visibility map*, a small file that tells it whether the table page must be checked.)

### The same lookup without the index

Wrap the column in arithmetic, `order_id + 0 = 7654321`, and the index no longer applies (2.6 explains why). The 10 million row table:

```text
Seq Scan on orders_10000000 (actual rows=1 loops=1)
  Filter: ((order_id + 0) = 7654321)
  Rows Removed by Filter: 9999999
  Buffers: shared hit=16194 read=37861 written=8
```

16,194 + 37,861 = 54,055 pages, every page of the table, to find one row. ("written=8" means the scan had to save 8 changed pages from memory to disk to make room; it is housekeeping, not part of the search.) 4 against 54,055.

### A range is one descent, then a walk

```text
Index Scan using orders_10000000_id on orders_10000000 (actual rows=101 loops=1)
  Index Cond: ((order_id >= 1000) AND (order_id <= 1100))
  Buffers: shared hit=5
```

101 rows for 5 pages. The descent finds key 1000 in the third leaf (leaves hold keys 1 to 366, 367 to 732, 733 to 1098): root, level 1, leaf 3. The range continues into leaf 4 by its link to the next leaf: 4 index pages. The table was loaded in key order, about 185 rows per page, so rows 1000 to 1100 all sit on one table page: 5.

### SQLite: the plan says SEARCH or SCAN

SQLite stores both tables and indexes as B-trees, and its `EXPLAIN QUERY PLAN` says which kind of access it chose: **SEARCH** (descend a B-tree) or **SCAN** (read it all). A small table for the purpose:

<!-- sql setup -->
```sql
CREATE TABLE sales (sale_id INTEGER NOT NULL, region INTEGER NOT NULL, amount INTEGER NOT NULL);
WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < 1000)
INSERT INTO sales SELECT x, x % 4, (x * 7919) % 1000 FROM n;
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

<!-- sql sqlite -->
```sql
EXPLAIN QUERY PLAN SELECT * FROM sales WHERE sale_id = 765;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| id | parent | notused | detail |
| --- | --- | --- | --- |
| 2 | 0 | 216 | SCAN sales |
<!-- /result -->

No index on `sale_id` yet, so: read everything. Now add one:

<!-- sql sqlite keep quiet -->
```sql
CREATE INDEX sales_id ON sales (sale_id);
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53: done.</p>
<!-- /result -->

<!-- sql sqlite -->
```sql
EXPLAIN QUERY PLAN SELECT * FROM sales WHERE sale_id = 765;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| id | parent | notused | detail |
| --- | --- | --- | --- |
| 3 | 0 | 62 | SEARCH sales USING INDEX sales_id (sale_id=?) |
<!-- /result -->

<!-- sql sqlite -->
```sql
EXPLAIN QUERY PLAN SELECT * FROM sales WHERE sale_id + 0 = 765;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| id | parent | notused | detail |
| --- | --- | --- | --- |
| 2 | 0 | 216 | SCAN sales |
<!-- /result -->

The same rule as PostgreSQL: the index is sorted by `sale_id`, not by `sale_id + 0`, so a condition on the expression cannot use it.

## 2.6 Where it breaks

- **Deletes do not rebalance in PostgreSQL.** The proof assumed every page stays at least half full. PostgreSQL's B-tree does not merge half-empty pages; it removes a page only once it is completely empty. After heavy deletes an index can be mostly air: more leaves than needed, a range scan reading many near-empty pages. The height stays small, because levels are never added by deletes, but the page counts of 2.5 no longer hold. `REINDEX` rebuilds it packed.
- **Too many matches.** An index finds rows one at a time, and each row may be on a different table page. In the 10 million row table, `region = 2` matches 25% of the rows, spread evenly. PostgreSQL used the region index (as a *bitmap* scan, which sorts the row addresses into page order first) and still had to read **all 54,055 table pages plus 2,108 index pages, 56,163 in all**: more than the plain full scan's 54,055. For `region IN (1, 2, 3)`, 75% of the rows, it did not use the index at all and scanned the table. Exercise E5 shows how few matches it takes before nearly every page holds one.
- **A function on the column.** The index is sorted by `order_id`. `order_id + 0`, `lower(email)` or `date(created_at)` are different values in a different order, so the tree cannot be searched for them, as 2.5 showed. The fix is to write the condition on the bare column, or to build an index on the expression ([SQL ch 25](../../databases/sql/25-Indexes-and-Explain.md#sargable)).
- **Every write pays.** Each index is another B-tree to update on every insert, and to log. Inserting 100,000 rows into a copy of the table wrote this many WAL (write-ahead log) records:

    | Indexes | WAL records | WAL bytes | Pages on disk (table and indexes) |
    | --- | --- | --- | --- |
    | 0 | 100,000 | 7,100,000 | 544 |
    | 1 | 200,274 | 13,707,620 | 820 |
    | 2 | 302,619 | 20,885,268 | 957 |

    One record per row for the table, one more per row for each index, and a few hundred extra for page splits (100,000 / 366 ≈ 273 leaves filled, matching the 274 extra records of the one-index row; that reading is ours, from the counts, not from a log dump).
- **Wider keys, lower fan-out.** A 16-byte `uuid` key makes 24-byte entries, so fewer per page (exercise E2). The height grows a little sooner, though the logarithm keeps it small.
- **Pages are not all equal.** The tutorial counts page reads. A page already in memory costs far less than one fetched from disk, and on spinning disks a random read costs far more than the next page in sequence. The upper levels of a busy index are almost always in memory, so in practice a lookup's real cost is mostly the leaf and the table page.

## 2.7 Exercises

Do 1 to 4 with a pencil. 5 needs a calculator. 6 is a short proof. 7 and 8 are small code.

**E1. Using 366 rows per leaf and 284 children per upper page, how many levels has an index on 1 million rows? How many pages does a lookup read, counting the table page?**

??? success "Answer"
    Leaves ⌈1,000,000 / 366⌉ = 2,733; level 1 ⌈2,733 / 284⌉ = 10; root ⌈10 / 284⌉ = 1. Three levels, so a lookup reads 3 index pages + 1 table page = 4. (Check: 3 levels hold up to 366 × 284² ≈ 29.5 million rows, and 1 million is less.)

**E2. A `uuid` key is 16 bytes, so an index entry is 8 + 16 = 24 bytes, plus the 4-byte pointer. How many entries fit on a page? With leaves 90% full, about how many rows per leaf? How many levels for 1 million rows, and for 100 million (take about 203 children per upper page)?**

??? success "Answer"
    ⌊8,152 / 28⌋ = 291 entries; 90% of that is about 262 entries, one of them the high key, so about 261 rows per leaf. 1 million rows: ⌈1,000,000 / 261⌉ = 3,832 leaves, then 19, then 1: **3 levels**. The script [ex04_exercises.py](src/02/ex04_exercises.py) built it on PostgreSQL ([output](src/02/ex04.out.txt)): items of 24 bytes, 261 rows on a leaf, 3,832 leaf pages, 20 upper pages (19 plus the root), 3 levels. 100 million rows: 383,142 leaves, then 1,888, then 10, then 1: **4 levels**, the same as `bigint`.

**E3. Insert 16 and then 17 into the last tree of 2.3. Draw the tree after each insert. What happens to the height?**

??? success "Answer"
    16 goes into the leaf [15], which becomes [15 16]: no split. 17 makes [15 16 17]: split, 16 goes up. The parent [12 20] becomes [12 16 20]: split, 16 goes up. The root [50 78] becomes [16 50 78]: split, and 50 becomes a new root. The tree grows from 3 to 4 levels, at the top:

    ```text
                                 [50]
                  [16]                           [78]
          [12]           [20]             [70]          [85]
       [10]   [15]    [17]   [30]      [60]   [75]   [80]   [90]
    ```

    Every leaf is still at the same depth. (Checked by [ex03_btree_by_hand.py](src/02/ex03_btree_by_hand.py).)

**E4. In the 10 million row table (3 index levels, 185 table rows per page), a query matches 100 rows by an indexed column. Estimate the pages read (a) if the 100 rows are scattered at random through the table, and (b) if they are next to each other, as `order_id` 1000 to 1099 are.**

??? success "Answer"
    (a) Descent 3 pages, the matching index entries fit on 1 or 2 leaves, then up to 100 different table pages: about **103 to 105**. (b) Descent 3, 1 or 2 leaves, and the rows fill one or two table pages: about **5 or 6**, like the range in 2.5. Same index, same row count, twenty times the reads: where the rows sit on disk matters as much as the tree. PostgreSQL tracks this as the column's *correlation* in `pg_stats`.

**E5. A table has 185 rows per page and a fraction p of its rows match, spread at random. Show that the share of pages with at least one match is 1 − (1 − p)^185, and compute it for p = 0.1% and 1%.**

??? success "Answer"
    A page has no match when all 185 rows miss, each with probability 1 − p, independently: (1 − p)^185. So at least one match: 1 − (1 − p)^185. For p = 0.1%: 1 − 0.999^185 ≈ 16.9%. For p = 1%: 1 − 0.99^185 ≈ 84.4%. A simulation in [ex04_exercises.py](src/02/ex04_exercises.py) gives 17.0% and 84.7%. So when just 1% of the rows match at random, an index route still visits 84% of the table's pages, one at a time, plus the index: the full scan is usually the better plan, which is why the planner chose it for `region IN (1, 2, 3)`.

**E6. Show that when a node with m + 1 children splits into two nodes of ⌈(m+1)/2⌉ and ⌊(m+1)/2⌋ children, both have at least ⌈m/2⌉ children.**

??? success "Answer"
    The larger half is at least the smaller, so check ⌊(m+1)/2⌋ ≥ ⌈m/2⌉. If m is even, m = 2k: ⌊(2k+1)/2⌋ = k and ⌈2k/2⌉ = k. If m is odd, m = 2k + 1: ⌊(2k+2)/2⌋ = k + 1 and ⌈(2k+1)/2⌉ = k + 1. Equal in both cases, so both halves have at least ⌈m/2⌉ = d children, and property (B) survives every split.

**E7. Write a function `levels(n, per_leaf, fanout)` that repeats "divide and round up" until one page is left, and check it against the table in 2.5.**

??? success "Answer"
    ```python
    import math

    def levels(n, per_leaf=366, fanout=284):
        pages, h = math.ceil(n / per_leaf), 1
        while pages > 1:
            pages, h = math.ceil(pages / fanout), h + 1
        return h

    print([levels(n) for n in (1_000, 100_000, 10_000_000, 100_000_000)])  # [2, 2, 3, 4]
    ```

    This is `built_levels` in [ex03_btree_by_hand.py](src/02/ex03_btree_by_hand.py); it matches the measured levels for all four tables.

**E8. On your own PostgreSQL, measure an index's levels and pages. (You need permission to create the `pgstattuple` extension.)**

??? success "Answer"
    ```sql
    CREATE EXTENSION IF NOT EXISTS pgstattuple;
    SELECT tree_level + 1 AS levels, internal_pages, leaf_pages, avg_leaf_density
    FROM pgstatindex('your_index_name');
    ```

    `tree_level` counts the levels above the leaves, hence the + 1. Compare `leaf_pages` with rows / 366 for a fresh `bigint` index; an index much bigger than that has been through many deletes or random inserts (2.6). Then try `EXPLAIN (ANALYZE, BUFFERS)` on a lookup and count the pages.

## 2.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: an index that made a query fast, one that did not help, and the page counts that explained each.)*

## 2.9 Further reading

On your own sites:

- B-trees as a data structure, with insertion by splitting and B+ trees: [Algorithms, ch 8. Trees and balanced search trees](https://cs.akadian.ca/books/algorithms/08-Trees-and-Balanced-Search-Trees/), section 8.5
- Logarithms: [Algebra, ch 7. Exponents and logarithms](https://math.akadian.ca/books/algebra/07-Exponents-and-Logarithms.html)
- The SQL side: [25. Indexes and EXPLAIN](../../databases/sql/25-Indexes-and-Explain.md), [26. Making slow queries fast](../../databases/sql/26-Making-Slow-Queries-Fast.md)

Original sources:

- R. Bayer and E. McCreight, "Organization and Maintenance of Large Ordered Indexes", *Acta Informatica* 1(3), 1972. The paper that introduced B-trees.
- D. Comer, "The Ubiquitous B-Tree", *ACM Computing Surveys* 11(2), 1979. A survey of the variants, including B+ trees.
- P. Lehman and S. B. Yao, "Efficient Locking for Concurrent Operations on B-Trees", *ACM Transactions on Database Systems* 6(4), 1981. The design PostgreSQL's B-tree is based on (the high key and the link to the next page come from it).
- PostgreSQL 16 documentation: [B-Tree indexes](https://www.postgresql.org/docs/16/btree.html), [pageinspect](https://www.postgresql.org/docs/16/pageinspect.html), [pgstattuple](https://www.postgresql.org/docs/16/pgstattuple.html), [Using EXPLAIN](https://www.postgresql.org/docs/16/using-explain.html).

## Glossary

- **Page**: the fixed block a database reads and writes as a unit; 8 kB in PostgreSQL.
- **B-tree**: a balanced tree of pages in which every node holds many sorted keys; all leaves are at the same depth.
- **B+ tree**: the B-tree variant real databases use: all keys in the leaves, signposts above, leaves linked in order.
- **Leaf**: a page on the bottom level, holding keys and the addresses of their rows.
- **Root**: the single page at the top, where every search starts.
- **Fan-out**: how many children one inner page points to; a few hundred for small keys.
- **Height (levels)**: the number of levels from root to leaf; the number of index pages one lookup reads.
- **Split**: cutting an overfull node in two and sending its middle key up to the parent.
- **Fillfactor**: how full `CREATE INDEX` packs each page; 90% for PostgreSQL B-tree leaves by default.
- **High key**: an extra entry on a PostgreSQL leaf giving the largest key that belongs on that page.
- **Selectivity**: the share of rows a condition matches; an index pays when it is small.
- **Index-only scan**: answering from the index without reading the table.
- **WAL (write-ahead log)**: the log every change is written to before the data pages; each index adds to it.
