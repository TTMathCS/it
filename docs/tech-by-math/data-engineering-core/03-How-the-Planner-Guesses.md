# 3. How the planner guesses: row estimates and join order

*Before a database runs a query, it guesses how many rows each step will produce, and picks the plan that is cheapest for those guesses. When a guess is wrong by a factor of a thousand, the plan can be wrong by a factor of a thousand too. This tutorial works out the guesses by hand: the selectivity of one filter, two filters multiplied together, the size of a join, and the search for the best join order by dynamic programming. Then it reproduces, on PostgreSQL 16, a query that took 18 seconds because of one bad guess, and fixes it with one statement so that it takes 68 milliseconds.*

!!! abstract "In this tutorial"
    **You will learn:**

    - what selectivity is, and how a planner turns column statistics into a row estimate
    - why it multiplies the selectivities of two filters, which assumption that hides, and what it costs when the assumption fails
    - the join size estimate |R| × |S| / max(V(R), V(S)), derived from its two assumptions
    - how many join orders there are, and how dynamic programming finds the best one without trying them all, with the proof
    - how to read estimated against actual rows in `EXPLAIN ANALYZE`, and how `CREATE STATISTICS` repairs an estimate
    - the limits: correlation, skew, stale statistics, errors that multiply through joins

    **You need:** probability of independent events (P(A and B) = P(A) × P(B)) from the [Probability book](https://math.akadian.ca/books/probability/), and reading a plan from [SQL ch 25](../../databases/sql/25-Indexes-and-Explain.md). [Tutorial 2](02-Why-an-Index-Is-Fast.md) explains page counts, but this one does not need it.

    **How to learn from it:** read 3.1 to 3.3, close the page, redo the three estimates of 3.3 and the join-order table on paper, then try the exercises in 3.7 before opening any answer. Plan about three hours.

**About the examples.** The PostgreSQL plans come from two scripts that build the tables and print the planner's real output on PostgreSQL 16; each section links them. `ANALYZE` reads a random sample of the table, so a rerun can give estimates a few rows different (994 or 995 instead of 1,000); the plans shown are from the saved run. Parallel workers were turned off so each plan is one process.

## 3.1 The question

Two tables: `orders3`, one million orders, each with a city, a province and a country; and `returns3`, the 333,333 orders that came back. The question: how many orders from city 7 were returned?

```sql
SELECT count(*) FROM orders3 o JOIN returns3 r ON r.order_id = o.order_id
WHERE o.city_id = 7 AND o.province_id = 0 AND o.country_id = 0
  AND r.city_id = 7 AND r.province_id = 0 AND r.country_id = 0;
```

The answer is 333. PostgreSQL took **18.5 seconds** to find it. Then one statement was run, `CREATE STATISTICS`, which changes no data and adds no index, and the same query took **68 milliseconds**: 270 times faster. On bigger tables the same mistake is the classic "query that ran for an hour". What did the planner believe the first time, and why?

## 3.2 The idea: the plan is chosen for the guess, not for the data

The planner cannot count rows without running the query, which is what it is trying to plan. So it **estimates**. For each table, `ANALYZE` stores a few numbers per column: how many distinct values, the most common values and how often each appears, a histogram. From these the planner estimates how many rows each step returns, gives each possible plan a **cost** built from those row counts, and runs the cheapest.

The trap is in the cost of the two usual join methods:

- **Nested loop:** for each row of the outer input, scan the inner input. Cost ≈ outer cost + (outer rows) × (inner cost).
- **Hash join:** read one input into a hash table once, then stream the other past it. Cost ≈ both scans + building the hash table.

If the outer input has **1** row, the nested loop scans the inner input once, and it skips building a hash table, so it is the cheapest plan there is. If the outer input really has 1,000 rows, it scans the inner input 1,000 times.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 250" role="img" aria-label="Two query plans side by side. Left, planned with an estimate of 1 row: a nested loop over a scan of orders3, estimated 1 row, actually 1,000, and a scan of returns3, estimated 1 row, which actually runs 1,000 times; 18.5 seconds. Right, planned with an estimate of 995 rows: a hash join over a scan of orders3, estimated 995, actually 1,000, and a hash of returns3, estimated 331, actually 333, scanned once; 68 milliseconds.">
<g font-size="13" fill="currentColor">
<text x="160" y="20" text-anchor="middle" font-weight="bold">planned for 1 row</text>
<text x="480" y="20" text-anchor="middle" font-weight="bold">planned for 995 rows</text>
<text x="160" y="60" text-anchor="middle" font-weight="bold">Nested Loop</text>
<text x="80" y="132" text-anchor="middle">scan orders3</text><text x="80" y="150" text-anchor="middle">guess 1, real 1,000</text>
<text x="240" y="132" text-anchor="middle">scan returns3</text><text x="240" y="150" text-anchor="middle" font-weight="bold">run 1,000 times</text>
<text x="480" y="60" text-anchor="middle" font-weight="bold">Hash Join</text>
<text x="400" y="132" text-anchor="middle">scan orders3</text><text x="400" y="150" text-anchor="middle">guess 995, real 1,000</text>
<text x="560" y="132" text-anchor="middle">hash returns3</text><text x="560" y="150" text-anchor="middle">guess 331, run once</text>
<text x="160" y="225" text-anchor="middle" font-size="20" font-weight="bold">18.5 s</text>
<text x="480" y="225" text-anchor="middle" font-size="20" font-weight="bold">68 ms</text>
</g>
<g fill="none" stroke="currentColor">
<rect x="100" y="40" width="120" height="30" rx="5" stroke-width="3"/>
<rect x="7" y="112" width="146" height="48" rx="5" stroke-width="1.2"/>
<rect x="167" y="112" width="146" height="48" rx="5" stroke-width="3"/>
<rect x="420" y="40" width="120" height="30" rx="5" stroke-width="1.2"/>
<rect x="327" y="112" width="146" height="48" rx="5" stroke-width="1.2"/>
<rect x="487" y="112" width="146" height="48" rx="5" stroke-width="1.2"/>
<line x1="140" y1="70" x2="80" y2="112" stroke-width="1.2"/><line x1="180" y1="70" x2="240" y2="112" stroke-width="3"/>
<line x1="460" y1="70" x2="400" y2="112" stroke-width="1.2"/><line x1="500" y1="70" x2="560" y2="112" stroke-width="1.2"/>
<path d="M 215 160 C 215 196, 265 196, 265 160" stroke-width="1.5" stroke-dasharray="4 3"/>
<line x1="320" y1="30" x2="320" y2="240" stroke-width="1" opacity="0.4"/>
</g>
</svg>
<figcaption>Figure 3.1. The same query, the same data, two plans (real output in 3.5). Only the planner's guess changed: with a guess of 1 row it chose a nested loop, which then had to rescan the inner table once per real row.</figcaption>
</figure>

So the whole story is in the guess. Here is how it is made.

## 3.3 The math by hand

The tables were built so that the right answers are known. City c (0 to 999) is in province c / 10 (rounded down, 100 provinces) and country c / 100 (10 countries): city 7 is in province 0 and country 0. Each city has exactly 1,000 orders. The column `amount` (0 to 999) was made independent of the city.

### Step 1. One filter: selectivity

The **selectivity** of a condition is the fraction of rows it keeps. With V distinct values spread evenly, an equality keeps 1 in V:

```text
sel(city_id = 7) = 1 / V(city_id) = 1 / 1,000
rows             = 1,000,000 × 1/1,000 = 1,000
```

PostgreSQL estimated 994: its statistics come from a random sample (30,000 rows at the default settings), so its 1/1,000 is a little off. Close enough.

### Step 2. Two filters: multiply, if they are independent

For `city_id = 7 AND amount < 100`, the planner multiplies:

```text
sel = sel(city_id = 7) × sel(amount < 100) = 1/1,000 × 1/10 = 1/10,000
rows = 1,000,000 × 1/10,000 = 100
```

The real count is 100 (the estimate was 99). Now the three filters on the place:

```text
sel = 1/1,000 × 1/100 × 1/10 = 1/1,000,000
rows = 1,000,000 × 1/1,000,000 = 1
```

The real count is **1,000**. Every order in city 7 is in province 0 and country 0, so the last two filters remove nothing. Multiplying assumed they would each remove most rows, and the estimate came out a thousand times too small.

### Step 3. The size of a join

For a join on `R.a = S.a`, the textbook estimate (and PostgreSQL's when it has no better statistics) is

```text
|R ⋈ S| = |R| × |S| / max(V(R,a), V(S,a))
```

Try it on two tiny tables. R has 4 rows with a = x, x, y, y (V = 2). S has 6 rows with a = x, x, y, y, z, z (V = 3).

```text
formula: 4 × 6 / max(2, 3) = 24 / 3 = 8
count:   x matches 2 × 2 = 4 pairs, y matches 2 × 2 = 4 pairs, z matches none: 8
```

Right. Now make S lopsided: a = x, x, x, x, y, z (still V = 3, still 6 rows). The formula still says 8. The count is x: 2 × 4 = 8, y: 2 × 1 = 2, total **10**. The formula assumed each value appears equally often; 3.4 says exactly what it assumes.

### Step 4. The best join order, by dynamic programming

Three tables: orders O (10,000 rows), customers C filtered to one country (10 rows left of 1,000), shipments S (10,000 rows, one per order). O joins C on the customer (V = 1,000 customers) and S on the order (V = 10,000 orders). C and S have no condition between them, so joining them first is a product.

A join of three tables makes one **intermediate result** (the first pair) before the final one, and the final result is the same whatever the order. So compare orders by the size of what they build on the way:

| First pair | Its size, by Step 3 | Then add | Final size |
| --- | --- | --- | --- |
| C ⋈ O | 10 × 10,000 / 1,000 = **100** | S | 100 |
| O ⋈ S | 10,000 × 10,000 / 10,000 = 10,000 | C | 100 |
| C × S (no condition) | 10 × 10,000 = 100,000 | O | 100 |

Best: **(C ⋈ O) ⋈ S**, building 100 rows on the way, against 100,000 for the worst. Dynamic programming finds this without listing every order: compute the best way to build each set of 2 tables, then the best way to build each set of 3 as "a best set of 2, plus one table", and so on up. For n tables it looks at each of the 2ⁿ − 1 sets once.

### Step 5. Why not try every order?

With n tables there are n! orders of the "add one table at a time" kind (left-deep plans), and (2n − 2)! / (n − 1)! plans of any tree shape. From [ex02_join_order.py](src/03/ex02_join_order.py) ([output](src/03/ex02.out.txt)):

| Tables n | Left-deep orders n! | Plans of any shape | Sets to look at, 2ⁿ − 1 |
| --- | --- | --- | --- |
| 3 | 6 | 12 | 7 |
| 4 | 24 | 120 | 15 |
| 5 | 120 | 1,680 | 31 |
| 8 | 40,320 | 17,297,280 | 255 |
| 12 | 479,001,600 | 28,158,588,057,600 | 4,095 |
| 20 | 2,432,902,008,176,640,000 | about 4.3 × 10³⁰ | 1,048,575 |

Trying every order stops being possible around ten tables. Looking at every set grows too, as 2ⁿ, which is why PostgreSQL switches to a different search above 12 tables (3.6).

## 3.4 Why it is true

### Multiplying is exact under independence, and only then

Read the selectivity of a condition A as a probability: P(A) is the chance that a row picked at random satisfies A. By definition, conditions A and B are **independent** when P(A and B) = P(A) × P(B). So the multiplied estimate is exactly right when the conditions are independent and each P is right, as for `city_id = 7 AND amount < 100`.

When A **implies** B (every row with A also has B), P(A and B) = P(A), and the multiplied estimate is too small by a factor of 1 / P(B). For the place filters: city implies province and country, so the estimate is too small by 1 / (1/100 × 1/10) = **1,000**. That is exactly the 1 against 1,000 of Step 2. The error is not noise: it is a formula applied outside its assumption.

### The join estimate: uniformity and containment

**Claim.** Assume (U) **uniformity**: in R each of its V(R) values appears |R| / V(R) times, and in S each of its V(S) values appears |S| / V(S) times; and (C) **containment**: if V(R) ≤ V(S), every value of R also appears in S. Then |R ⋈ S| = |R| × |S| / max(V(R), V(S)).

**Proof.** Say V(R) ≤ V(S). By (C) each of R's V(R) values finds a partner value in S. One value pairs |R| / V(R) rows of R with |S| / V(S) rows of S, by (U). Add over the V(R) values:

```text
V(R) × (|R| / V(R)) × (|S| / V(S)) = |R| × |S| / V(S) = |R| × |S| / max(V(R), V(S))   ∎
```

The lopsided S of Step 3 broke (U), and the count came out 10 instead of 8. Section 3.5 breaks (C) on a real table: the formula predicts a million rows and the answer is none.

### Dynamic programming finds the best order

Score a plan by the sum of its intermediate result sizes, as in Step 4. Under the estimates above, **the size of a join result depends only on which tables are in it**, not on the order they were joined in (it is the product of the table sizes and the selectivities of the conditions among them).

**Claim.** Let best(S) be the cheapest way to build the set of tables S. Then best(S) = min over the tables t in S of [best(S − {t}) + size(S)], where size(S) is counted only if S is not the whole query.

**Proof.** Any left-deep plan for S builds S − {t} first, for some last table t, and then adds t. Its cost is (its cost for S − {t}) + size(S). The second term does not depend on how S − {t} was built. So if the plan built S − {t} in any way costlier than best(S − {t}), swapping in best(S − {t}) gives a plan for S that is no more expensive. The cheapest plan for S therefore uses best(S − {t}) for its last t, and trying every t finds it. By induction on the size of S, starting from single tables (cost 0), the recurrence computes the true best for every set. ∎

The proof needs the cost of the last step to depend only on the **set** S − {t}. Real cost models break this a little: a sorted intermediate result can make the next merge join cheaper, so how S − {t} was built matters after all. Selinger's System R planner (1979) handled it by keeping, for every set, the best plan for each useful sort order ("interesting orders"), and PostgreSQL does the same: it keeps several candidate paths per set of tables. The recurrence is the same, with a slightly richer table.

### Counting the orders

A left-deep plan is a sequence of the n tables: n! of them. A plan of any shape is a binary tree with n leaves, labelled by the tables, where left and right matter: there are C(n − 1) tree shapes (the Catalan number, C(n − 1) = (2n − 2)! / (n! (n − 1)!)) and n! ways to label the leaves, so n! × C(n − 1) = (2n − 2)! / (n − 1)!.

## 3.5 See it in the database

All output below is from [ex01_estimates.py](src/03/ex01_estimates.py) ([output](src/03/ex01.out.txt)). In `EXPLAIN ANALYZE`, each line shows the guess, `rows=` inside the first brackets, and the truth, `actual rows=` inside the second. Comparing the two, line by line, is the most useful habit in query tuning.

### What ANALYZE stored

`pg_stats` holds the statistics. For `orders3` it found 1,000 distinct values of `city_id`, 100 of `province_id`, 10 of `country_id`, and `-1` for `order_id`, which means "every value is distinct". The planner's V(·) in Step 3 is this number.

### One filter, two independent filters, three dependent ones

```text
Seq Scan on orders3  (cost=0.00..18870.00 rows=994 width=20) (actual rows=1000 loops=1)
  Filter: (city_id = 7)

Seq Scan on orders3  (cost=0.00..21370.00 rows=99 width=20) (actual rows=100 loops=1)
  Filter: ((amount < 100) AND (city_id = 7))

Seq Scan on orders3  (cost=0.00..23870.00 rows=1 width=20) (actual rows=1000 loops=1)
  Filter: ((city_id = 7) AND (province_id = 0) AND (country_id = 0))
```

994 against 1,000, 99 against 100, and **1 against 1,000**: Step 1, Step 2 and the failure of Step 2, exactly as worked by hand.

### The join, planned on the bad guess

```text
Aggregate  (cost=31559.34..31559.35 rows=1 width=8) (actual rows=1 loops=1)
  ->  Nested Loop  (cost=0.00..31559.34 rows=1 width=0) (actual rows=333 loops=1)
        Join Filter: (o.order_id = r.order_id)
        Rows Removed by Join Filter: 332667
        ->  Seq Scan on orders3 o  (cost=0.00..23870.00 rows=1 width=4) (actual rows=1000 loops=1)
              Filter: ((city_id = 7) AND (province_id = 0) AND (country_id = 0))
              Rows Removed by Filter: 999000
        ->  Seq Scan on returns3 r  (cost=0.00..7689.33 rows=1 width=4) (actual rows=333 loops=1000)
              Filter: ((city_id = 7) AND (province_id = 0) AND (country_id = 0))
              Rows Removed by Filter: 333000
Execution Time: 18477.640 ms
```

Read the cost the planner computed with the formula of 3.2: outer cost + (outer rows) × (inner cost) = 23,870.00 + **1** × 7,689.33 = 31,559.33, the 31,559.34 at the top. The hash join it rejected cost 31,567.21 (below): the nested loop won by **8 cost units**, about one part in four thousand. Then the real outer input had 1,000 rows, the inner scan ran `loops=1000` times over 333,333 rows each, and the query took 18.5 seconds.

### The fix: tell the planner the columns depend on each other

```sql
CREATE STATISTICS orders3_place (dependencies) ON city_id, province_id, country_id FROM orders3;
CREATE STATISTICS returns3_place (dependencies) ON city_id, province_id, country_id FROM returns3;
ANALYZE orders3;
ANALYZE returns3;
```

`ANALYZE` now measures **functional dependencies** between the columns and stores them:

```text
{"2 => 3": 1.000000, "2 => 4": 1.000000, "3 => 4": 1.000000, "2, 3 => 4": 1.000000, "2, 4 => 3": 1.000000}
```

The numbers are column positions (2 = `city_id`, 3 = `province_id`, 4 = `country_id`): "2 => 3: 1.0" means the city determines the province in 100% of the sampled rows. The planner then stops multiplying the implied filters, and the same query is planned again:

```text
Aggregate  (cost=31567.21..31567.22 rows=1 width=8) (actual rows=1 loops=1)
  ->  Hash Join  (cost=7693.47..31567.21 rows=1 width=0) (actual rows=333 loops=1)
        Hash Cond: (o.order_id = r.order_id)
        ->  Seq Scan on orders3 o  (cost=0.00..23870.00 rows=995 width=4) (actual rows=1000 loops=1)
              Filter: ((city_id = 7) AND (province_id = 0) AND (country_id = 0))
              Rows Removed by Filter: 999000
        ->  Hash  (cost=7689.33..7689.33 rows=331 width=4) (actual rows=333 loops=1)
              Buckets: 1024  Batches: 1  Memory Usage: 20kB
              ->  Seq Scan on returns3 r  (cost=0.00..7689.33 rows=331 width=4) (actual rows=333 loops=1)
                    Filter: ((city_id = 7) AND (province_id = 0) AND (country_id = 0))
                    Rows Removed by Filter: 333000
Execution Time: 68.344 ms
```

Guesses 995 and 331, truths 1,000 and 333. With 995 outer rows the nested loop would cost about 23,870 + 995 × 7,689 ≈ 7.7 million, so the hash join at 31,567 wins easily. 68 milliseconds. (Look at the top line, though: the join itself is still guessed at 1 row against 333. Exercise E6 asks why, and why the plan is right anyway.)

### The join estimate, when it holds and when it does not

Joining all orders to all returns on `order_id`: |R| = 1,000,000, |S| = 333,333, V(R) = 1,000,000, V(S) = 333,333, so the formula gives 1,000,000 × 333,333 / 1,000,000 = **333,333**:

```text
Hash Join  (cost=10658.99..43229.32 rows=333333 width=0) (actual rows=333333 loops=1)
```

Exact, because both assumptions hold: every returned order is an order (containment), and every id appears once (uniformity). Now a table of 1,000 promotions for cities 1000 to 1999, none of which has orders. The formula sees 1,000 values on each side and assumes they are the same values: 1,000,000 × 1,000 / 1,000 = **1,000,000**:

```text
Hash Join  (cost=30.50..30150.50 rows=1000000 width=0) (actual rows=0 loops=1)
```

The real answer is 0. Containment failed, and the planner has no way to know: it stores how many distinct values each column has, not whether two columns share them. (When both columns have a most-common-values list, PostgreSQL compares the two lists directly and can do better; here `promos3.city_id` has none, since all its values are distinct.)

## 3.6 Where it breaks

- **Correlated columns.** Step 2 multiplies, and real data is full of dependencies: city and postcode, model and make, a date and its fiscal year. `CREATE STATISTICS` fixes the ones you declare, with three kinds: `dependencies` (shown above), `ndistinct` (for `GROUP BY` on several columns) and `mcv` (the most common combinations). It cannot find them for you.
- **Correlation across tables.** No statistics object spans two tables. After the fix above, the join was still guessed at 1 row instead of 333 (E6). Here it did no harm; above that join, in a bigger query, it could.
- **Skew.** Uniformity is assumed for every value outside the most-common-values list, which holds up to 100 values at the default `default_statistics_target` of 100. A column with a long tail of moderately common values (a few big customers among millions) is estimated as if those values were average. Raising the target for that column (`ALTER TABLE ... ALTER COLUMN ... SET STATISTICS 1000`) keeps more of them.
- **Stale statistics.** The numbers are from the last `ANALYZE`. The automatic one runs after about 50 + 10% of the rows have changed (`autovacuum_analyze_threshold` and `autovacuum_analyze_scale_factor`). A table loaded with today's data and queried for today's data before that point is planned on yesterday's histogram. Run `ANALYZE` after a big load.
- **Errors multiply through joins.** Each join's estimate is computed from the estimates of its inputs. A factor of 10 off at each of 5 joins can be a factor of 100,000 at the top. Ioannidis and Christodoulakis (1991) showed that, under their model, the error grows exponentially with the number of joins. This is why the query that "ran for an hour" usually has many joins.
- **The search is cut off.** PostgreSQL searches join orders by dynamic programming only within limits: `join_collapse_limit` and `from_collapse_limit` are 8 (beyond 8 tables in one `FROM`, part of the order is taken as written) and `geqo_threshold` is 12 (at 12 or more tables it uses a genetic algorithm, which is randomized and not guaranteed to find the best order). These are the values the script read from PostgreSQL 16.
- **Cost is not time.** The cost units model pages and CPU steps, with settings such as `random_page_cost`. Even a perfect row estimate gives the plan that is cheapest in the model, not necessarily on your hardware.

## 3.7 Exercises

1 to 5 by hand. 6 is reading a plan. 7 is arithmetic. 8 is SQL on your own database.

**E1. A table has 1,000,000 rows. `status` has 5 values and `country` has 50, each evenly spread. Estimate the rows for `status = 'late' AND country = 'NO'`. Then suppose the two are tied: every order in Norway is late. What is the real count, and by what factor was the estimate off?**

??? success "Answer"
    Estimate: 1,000,000 × 1/5 × 1/50 = **4,000**. If every Norwegian order is late, the condition `status = 'late'` removes none of them, so the real count is all of Norway's orders: 1,000,000 / 50 = **20,000**. Country implies status here, so by 3.4 the estimate is too small by 1 / P(status = 'late') = **5**: 20,000 / 4,000 = 5.

**E2. On `orders3`, estimate `city_id IN (7, 8) AND amount < 500`. Check against the plan.**

??? success "Answer"
    `IN (7, 8)` keeps 2 cities: 2/1,000. `amount < 500` keeps half: 1/2. Independent, so 1,000,000 × 2/1,000 × 1/2 = **1,000**. The plan ([output](src/03/ex01.out.txt), part 8): `rows=990`, `actual rows=1000`. The data was built so each city's 1,000 amounts are exactly 0 to 999, so the true count is exactly 1,000.

**E3. R has 1,000 rows with 100 distinct values of a; S has 50,000 rows with 2,000 distinct values of a. Estimate |R ⋈ S|. Which two assumptions does it make? Give one real situation where each fails.**

??? success "Answer"
    1,000 × 50,000 / max(100, 2,000) = **25,000**. Uniformity: a few values of a could hold most of S's rows (big customers), and if R holds those, the join is much larger. Containment: R's 100 values could be codes S has never seen (a new product line), and the join is empty, as with the promotions in 3.5.

**E4. Add a fourth table to Step 4: products P, 100 rows, joined to orders by product (V = 100). Find the best left-deep order by dynamic programming, and its cost.**

??? success "Answer"
    Sets of two: C ⋈ O = 100; O ⋈ P = 10,000 × 100 / 100 = 10,000; O ⋈ S = 10,000; C × P = 1,000; C × S = 100,000; P × S = 1,000,000. Sets of three, each as the best pair plus one table: {C, O, P} = 100 (from C ⋈ O, cost 100 + 100); {C, O, S} = 100 (cost 100 + 100); {O, P, S} = 10,000 (cost 10,000 + 10,000); {C, P, S}: 10,000,000. Adding the last table to {C, O, P} or {C, O, S} gives total **200**: (C ⋈ O) ⋈ P, then S, or (C ⋈ O) ⋈ S, then P. The script ([ex02 output](src/03/ex02.out.txt)) lists all 12 distinct orders, from 200 up to 11,000,000, and the dynamic program finds 200 after looking at 15 sets.

**E5. How many left-deep orders and how many sets does dynamic programming look at for 4 tables? For 5?**

??? success "Answer"
    4 tables: 4! = 24 orders, 2⁴ − 1 = 15 sets. 5 tables: 120 orders, 31 sets. (Plans of any shape: 120 and 1,680.)

**E6. After `CREATE STATISTICS`, the join in 3.5 is still estimated at 1 row, and the truth is 333. Use the formula to explain the 1. Why did the planner choose the right plan anyway?**

??? success "Answer"
    The planner joins its two input estimates with the join formula: 995 × 331 / max(1,000,000, 333,333) ≈ 0.33, shown as 1. The formula assumes the 995 orders and the 331 returns are an unrelated pick of order ids, so a random order id from one side rarely meets one from the other. In fact they are the same orders (city 7's orders and their returns), so a third of them match. The plan was right anyway because the choice between nested loop and hash join depends on the **input** sizes, 995 and 331, which were now right. The wrong output estimate would matter only if something sat above the join.

**E7. A table has 2,000,000 rows. After how many changed rows does the automatic ANALYZE run, at the default settings? A nightly load adds 150,000 rows and the morning report queries only them: is it planned on fresh statistics?**

??? success "Answer"
    50 + 0.1 × 2,000,000 = **200,050** changed rows. 150,000 is fewer, so the automatic ANALYZE has not run when the report starts: the new rows are not in the statistics, and a filter on the new dates looks (to the histogram) like it matches almost nothing. Add `ANALYZE` to the end of the load.

**E8. On your own PostgreSQL, find a query whose plan has a line where `rows=` and `actual rows=` differ by more than 10 times. Which assumption failed?**

??? success "Answer"
    Run `EXPLAIN (ANALYZE, BUFFERS)` and read bottom-up: the first line where the guess and the truth part ways is where the error starts; everything above it inherits it. A filter on several related columns points to correlation (fix: `CREATE STATISTICS`); a recently loaded range points to stale statistics (fix: `ANALYZE`); a join that is far bigger than guessed points to skew; far smaller, to containment.

## 3.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a plan where the guess and the truth were far apart, and what fixed it.)*

## 3.9 Further reading

On your own sites:

- Independence and conditional probability: the [Probability book](https://math.akadian.ca/books/probability/); counting orders and Catalan numbers: the [Combinatorics book](https://math.akadian.ca/books/combinatorics/)
- Dynamic programming and its proofs: [Algorithms, ch 13. Dynamic programming](https://cs.akadian.ca/books/algorithms/13-Dynamic-Programming/)
- The SQL side: [25. Indexes and EXPLAIN](../../databases/sql/25-Indexes-and-Explain.md), [26. Making slow queries fast](../../databases/sql/26-Making-Slow-Queries-Fast.md)

Original sources:

- P. G. Selinger, M. M. Astrahan, D. D. Chamberlin, R. A. Lorie and T. G. Price, "Access Path Selection in a Relational Database Management System", *Proceedings of ACM SIGMOD*, 1979. The System R planner: selectivity estimates, dynamic programming over join orders, interesting orders.
- Y. E. Ioannidis and S. Christodoulakis, "On the Propagation of Errors in the Size of Join Results", *Proceedings of ACM SIGMOD*, 1991.
- V. Leis, A. Gubichev, A. Mirchev, P. Boncz, A. Kemper and T. Neumann, "How Good Are Query Optimizers, Really?", *Proceedings of the VLDB Endowment* 9(3), 2015. Measures real planners, PostgreSQL among them, on a benchmark of correlated data, and finds the row estimates matter more than the cost model.
- PostgreSQL 16 documentation: [Statistics used by the planner](https://www.postgresql.org/docs/16/planner-stats.html), [Row estimation examples](https://www.postgresql.org/docs/16/row-estimation-examples.html), [CREATE STATISTICS](https://www.postgresql.org/docs/16/sql-createstatistics.html), [Controlling the planner with explicit JOIN clauses](https://www.postgresql.org/docs/16/explicit-joins.html), [Genetic query optimizer](https://www.postgresql.org/docs/16/geqo.html).

## Glossary

- **Planner (optimizer)**: the part of the database that chooses how to run a query.
- **Estimate**: the planner's guess of how many rows a step returns (`rows=` in a plan).
- **Selectivity**: the fraction of rows a condition keeps.
- **Statistics**: what `ANALYZE` stores per column (distinct values, most common values, histogram); read them in `pg_stats`.
- **Independence**: two conditions are independent when P(A and B) = P(A) × P(B); the planner assumes it when it multiplies.
- **Functional dependency**: one column determines another (a city determines its country).
- **Uniformity**: the assumption that every value of a column appears equally often.
- **Containment**: the assumption that the values of the smaller side of a join all appear on the other side.
- **Nested loop join**: for each outer row, scan the inner input.
- **Hash join**: build a hash table from one input, stream the other past it.
- **Left-deep plan**: a join order that adds one table at a time.
- **Dynamic programming**: solving a problem from the best answers to its smaller sub-problems, each solved once.
- **Interesting order**: a sort order of an intermediate result that a later step can use, kept as a separate candidate by the planner.
