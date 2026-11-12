# 8. Shuffles and skew in Spark

*A Spark stage has 200 tasks. 199 of them finish in about two minutes; the last one runs for forty. Nothing is broken, and adding machines does not help. This tutorial works out why with pencil-sized arithmetic: where a row goes in a shuffle, the smallest possible time for a stage, how uneven partitions are by pure chance, and how much salting really buys. Every number from Spark below was produced by a real run, and Spark's own hash is recomputed by hand to show there is no magic in it.*

!!! abstract "In this tutorial"
    **You will learn:**

    - the exact rule Spark uses to send a row to a partition, `pmod(hash(key), n)`, and how to compute it yourself
    - why one key can never be split, and the lower bound that follows: a stage takes at least `max(m / n, h)` rows' worth of time
    - why this bound looks like Amdahl's law but is a different statement
    - how far the fullest partition sits above the average when keys are spread at random (balls into bins)
    - how to choose the number of salt values, and why salting is itself a random throw
    - two everyday traps: NULL keys, and joins where salting copies the other side

    **You need:** remainders (`17 mod 5 = 2`) and the idea of an average (expected value). [3. Apache Spark for data engineers](../../data-engineering/databricks/03-Apache-Spark.md) explains partitions, stages and shuffles in Spark itself; this tutorial is the math under it.

    **How to learn from it:** read 8.1 to 8.3, close the page, redo the example of 8.3 on paper, then try the exercises in 8.7 before opening any answer. Plan about three hours.

**About the examples.** Every Spark result ran on Apache Spark 4.2.0 in local mode (`local[2]`), with adaptive query execution (AQE) turned off so that the number of partitions asked for is the number used. The data is Red Rock Supply orders, built so that one reseller account, customer 7, places 80% of 300,000 orders, the same shape as section 22.14 of the Databricks book. The scripts and their full output are next to this page: [ex01_spark_partitions.py](src/08/ex01_spark_partitions.py) ([output](src/08/ex01.out.txt)), [ex02_balls_bins.py](src/08/ex02_balls_bins.py) ([output](src/08/ex02.out.txt)), [ex03_murmur3.py](src/08/ex03_murmur3.py) ([output](src/08/ex03.out.txt)), [ex04_checks.py](src/08/ex04_checks.py) ([output](src/08/ex04.out.txt)) and [ex05_partial_agg.py](src/08/ex05_partial_agg.py) ([output](src/08/ex05.out.txt)). Simulations use Python with NumPy (200 random trials each, fixed seed).

## 8.1 The question

The nightly job groups Red Rock Supply orders by customer and joins them to the customers table. On the Spark UI, the stage after the shuffle shows: 200 tasks, median duration 2 minutes, maximum 40 minutes. The team doubles the cluster. The median drops to 1 minute; the maximum stays at 40.

Three questions, each with a number for an answer:

1. Which rows end up in that one slow task, and could we have predicted it?
2. What is the shortest time this stage could ever take, on any cluster?
3. If we split the guilty key into `k` pieces ("salting"), how big must `k` be?

## 8.2 The idea: one key, one partition

A **shuffle** moves rows between machines so that rows that must meet end up together. For a `groupBy(customer_id)` or a join on `customer_id`, all rows of one customer must reach the same task. Spark does this with a rule that needs no coordination at all:

```text
partition = pmod(hash(key), n)
```

`hash` turns the key into a 32-bit integer, `n` is the number of partitions after the shuffle (`spark.sql.shuffle.partitions`, 200 by default), and `pmod` is the remainder after division, made non-negative. Every machine applies the same rule to every row, so all rows of customer 7 land in the same partition, wherever they started.

That guarantee is the whole point of the shuffle, and it is also the whole problem: **a key is never split**. If customer 7 owns 80% of the rows, one task receives at least 80% of the rows.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 260" role="img" aria-label="Eight customers on the left, each with its number of orders, are sent by pmod of hash by 3 to three partitions on the right. Customers 2, 3, 4, 5, 7 and 8 go to partition 0 with 500 rows; customers 1 and 6 go to partition 1 with 50 rows; partition 2 receives nothing.">
<g font-size="13" fill="currentColor">
<text x="20" y="22" font-weight="bold">customer (orders)</text>
<text x="440" y="22" font-weight="bold">partition = pmod(hash, 3)</text>
<g>
<text x="20" y="50">1 (30)</text><text x="20" y="76">2 (20)</text><text x="20" y="102">3 (25)</text><text x="20" y="128">4 (15)</text>
<text x="20" y="154">5 (10)</text><text x="20" y="180">6 (20)</text><text x="20" y="206" font-weight="bold">7 (400)</text><text x="20" y="232">8 (30)</text>
</g>
<rect x="440" y="40" width="180" height="70" rx="6" fill="none" stroke="currentColor" stroke-width="2.5"/>
<text x="452" y="64" font-weight="bold">partition 0</text><text x="452" y="88">500 rows (2,3,4,5,7,8)</text>
<rect x="440" y="125" width="180" height="50" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="452" y="148">partition 1</text><text x="452" y="166">50 rows (1,6)</text>
<rect x="440" y="190" width="180" height="50" rx="6" fill="none" stroke="currentColor" stroke-width="1.2" stroke-dasharray="4 3"/>
<text x="452" y="213">partition 2</text><text x="452" y="231">0 rows</text>
</g>
<g stroke="currentColor" stroke-width="1" fill="none" opacity="0.7">
<line x1="80" y1="46" x2="440" y2="150"/><line x1="80" y1="72" x2="440" y2="70"/><line x1="80" y1="98" x2="440" y2="72"/>
<line x1="80" y1="124" x2="440" y2="74"/><line x1="80" y1="150" x2="440" y2="76"/><line x1="80" y1="176" x2="440" y2="152"/>
<line x1="95" y1="202" x2="440" y2="80" stroke-width="3"/><line x1="80" y1="228" x2="440" y2="84"/>
</g>
</svg>
<figcaption>Figure 8.1. Eight customers sent to three partitions by Spark's real hash (worked in 8.3). Six of the eight keys land in partition 0, including the big one; partition 2 gets nothing.</figcaption>
</figure>

## 8.3 The math by hand

### Step 1. From key to partition

Spark's `hash` of an integer is MurmurHash3 (32-bit) with seed 42. You do not need to compute it by hand; Spark prints it (section 8.5), and `ex03_murmur3.py` recomputes it in twenty lines of plain Python. Here are the real values for customers 1 to 8:

| customer | orders | hash | Java `%` 3 | pmod 3 |
| --- | ---: | ---: | ---: | ---: |
| 1 | 30 | -559,580,957 | -2 | **1** |
| 2 | 20 | 1,765,031,574 | 0 | **0** |
| 3 | 25 | -1,823,081,949 | 0 | **0** |
| 4 | 15 | -397,064,898 | 0 | **0** |
| 5 | 10 | 1,023,896,466 | 0 | **0** |
| 6 | 20 | -331,964,951 | -2 | **1** |
| 7 | 400 | 1,079,293,707 | 0 | **0** |
| 8 | 30 | -132,918,897 | 0 | **0** |

Two things to do with a pencil:

- **Remainder by 3 without dividing.** A number and the sum of its digits leave the same remainder when divided by 3, because 10 leaves remainder 1, so every power of 10 does too. For customer 1: 5+5+9+5+8+0+9+5+7 = 53, and 53 = 3 × 17 + 2, so 559,580,957 leaves 2.
- **Negative numbers.** Java (and so Spark) gives `-559,580,957 % 3 = -2`: the remainder takes the sign of the number. A partition number cannot be negative, so `pmod` adds 3 once: `-2 + 3 = 1`. Customer 1 goes to partition 1.

Adding the orders per partition:

```text
partition 0: customers 2, 3, 4, 5, 7, 8  ->  20 + 25 + 15 + 10 + 400 + 30 = 500 rows
partition 1: customers 1, 6              ->  30 + 20                     =  50 rows
partition 2: nobody                      ->                                  0 rows
total m = 550, mean m / n = 183.3, max = 500, max / mean = 2.73
```

### Step 2. A stage ends when its slowest task ends

Assume each row costs the same time `c` to process, and there are at least as many free cores as tasks, so all tasks run at once. Then a task with `L` rows takes about `c × L`, and the stage takes the time of its longest task:

```text
stage time ≈ c × max(L_0, L_1, ..., L_(n-1))
```

Here: `c × 500`, even though the average task has only 183 rows. Two-thirds of the cluster sits idle for most of the stage.

### Step 3. The bound no cluster can beat

Write `m` for the number of rows, `n` for the number of partitions and `h` for the number of rows of the largest key. Then, whatever the hash does:

```text
max load ≥ max( m / n , h )
```

- `max load ≥ m / n`: the loads add up to `m`, and `n` numbers cannot all be below their average.
- `max load ≥ h`: the largest key goes, whole, into one partition.

So the shortest possible stage time is `c × max(m / n, h)`. The best speed-up over one task doing all `m` rows is

```text
speed-up ≤ m / max(m / n, h) = min( n , m / h )
```

In the example: `m / h = 550 / 400 = 1.375`. With 3 partitions, or 3,000, this stage can never run more than 1.375 times faster than on a single core. In the 300,000-order data of section 8.5, customer 7 has `h = 240,060` rows, so `m / h = 1.25`: doubling the cluster changes nothing, exactly as in the story of 8.1.

!!! note "Not quite Amdahl's law"
    Amdahl's law is about a program whose time has a serial part, a fraction `s` that only one processor can do, *before or after* the parallel part. With `n` processors its speed-up is `1 / (s + (1 - s) / n)`, which approaches `1 / s`.

    The hot-key bound is about data, not time: one task must handle the fraction `f = h / m` of the rows, and it runs *at the same time* as the other tasks, not before them. That is why the bound is `1 / max(1/n, f)`, a maximum, where Amdahl's law has a sum. Both say "the part you cannot split limits you", and both tend to `1/f` (or `1/s`) for very large `n`, but for `f = 0.8` and `n = 8` they give different numbers: 1.25 here, `1 / (0.8 + 0.2 / 8) = 1.21` for Amdahl. Keep them apart.

### Step 4. Uneven without any hot key

Now suppose there is no big customer: `K` keys, all with the same number of rows, thrown into `n` partitions. If the hash behaves like a fair random choice (an assumption; section 8.4), each partition gets `K / n` keys **on average**. But the fullest partition gets more than average. This is the classic *balls into bins* problem, and for `K` much larger than `n × ln n` it has a known answer (Raab and Steger, 1998):

```text
fullest partition ≈ K/n + sqrt( 2 × (K/n) × ln n )        (keys, not rows)
```

For `n = 200` partitions, `ln 200 = 5.30`. With 20,000 keys the average is 100 keys per partition and the formula gives `100 + sqrt(2 × 100 × 5.30) = 100 + 32.6 = 132.6`: the slowest task does about 33% more work than the average task, by pure chance.

The gap shrinks as keys get more numerous, but only like a square root:

| keys K (n = 200) | mean K/n | formula | simulated, average of 200 runs | max / mean |
| ---: | ---: | ---: | ---: | ---: |
| 2,000 | 10 | 20.3 | 19.7 | 1.97 |
| 20,000 | 100 | 132.6 | 128.6 | 1.29 |
| 200,000 | 1,000 | 1,102.9 | 1,087.0 | 1.09 |
| 1,000,000 | 5,000 | 5,230.2 | 5,194.0 | 1.04 |

(From `ex02_balls_bins.py`.) Two lessons. Few distinct keys means uneven tasks even with no hot key: 2,000 customers over 200 partitions gives one task about twice the average. And the formula is an approximation: it is a little high in every row, and it is only promised for `K` much larger than `n ln n` (here 1,060), so the first row is outside its guarantee, though still close.

### Step 5. Salting is a second throw

**Salting** replaces the key `customer_id` by the pair `(customer_id, salt)`, where `salt` takes `k` values (for example `order_id % k`). The hot key's `h` rows become `k` slices of `h / k` rows, and each slice is hashed to its own partition. The aggregation then runs in two stages: sum per `(customer_id, salt)`, then add the at most `k` partial sums per customer.

The trap: the `k` slices are themselves balls thrown into `n` bins. With `k = n = 8`, you might expect one slice per partition; in fact the expected number of *empty* partitions is `n × (1 - 1/n)^k = 8 × (7/8)^8 = 2.75`, so some partitions get two or three slices. The fullest partition holds about

```text
(h / k) × (largest number of slices in one partition) + (other rows per partition)
```

For the 300,000 orders (`h = 240,060`, other rows 59,940, so 7,493 per partition when `n = 8`), the simulation gives the average largest number of slices, and Spark gives one real outcome:

| salt values k | average largest number of slices (range) | predicted fullest partition | measured in Spark |
| ---: | ---: | ---: | ---: |
| 1 (no salt) | 1 | 247,553 | 247,560 |
| 2 | 1.11 (1 to 2) | 141,326 | 127,200 |
| 4 | 1.74 (1 to 4) | 111,919 | 67,920 |
| 8 | 2.69 (2 to 5) | 88,063 | 67,920 |
| 16 | 4.23 (3 to 7) | 70,958 | 54,780 |
| 32 | 7.03 (5 to 11) | 60,231 | 59,730 |
| 64 | 12.10 (9 to 17) | 52,879 | 59,933 |
| 256 | 40.45 (34 to 53) | 45,424 | 49,578 |
| perfect spread | | 37,500 | |

The predicted column is an average over many random throws; a real run is one throw and can land anywhere in the range. That is why Spark did better than predicted at `k = 4` and worse at `k = 64`. Read the trend, not one row: more salt values bring the fullest partition towards the perfect 37,500, quickly at first and then slowly (the same square-root shape as step 4).

**A rule for `k`.** The hot key alone should not overload a partition, so its slice per partition should be about the average load: `k ≥ f × n`, where `f = h / m`. Then take several times that, because of the random collisions. In the example `f × n = 0.8 × 8 = 6.4`. On average `k = 64` leaves the fullest partition about 40% above perfect and `k = 256` about 20% (Spark's single runs: 60% and 32%).

## 8.4 Why it is true

**Same key, same partition.** `hash` is a function: the same input always gives the same output, on every machine. So `pmod(hash(key), n)` sends all rows of a key to one partition. Spark's hash is also *seeded* (42) and fixed, so the same key goes to the same partition in every run, as long as `n` does not change.

**The lower bound.** Proved in step 3, using only "the parts add up to the whole" and "a key is not split". It needs no assumption about the hash, so it is the most useful line in this tutorial: it tells you, from one `GROUP BY key ORDER BY count DESC` query, the best any tuning can do.

**The average is `m / n`.** Assume the hash sends each key to each partition with probability `1 / n`, independently. The expected load of one partition is then the sum over keys of `(rows of the key) × (1 / n)` = `m / n`, by linearity of expectation (which needs no independence). Is the assumption true? MurmurHash3 is not random: it is a fixed function. But it mixes the bits of its input thoroughly, and section 8.5 shows that on real customer numbers its partition counts match the random model as closely as one random run would. On adversarial or oddly patterned keys it could do worse; nothing here proves otherwise.

**The fullest partition.** The formula in step 4 is a theorem of Raab and Steger for truly random throws, stated for `K` much larger than `n ln n`. It is not proved here. This tutorial checks it by simulation (step 4 table) and against Spark's real hash (section 8.5). Treat it as a good estimate, slightly on the high side.

**Salting gives the same answer.** The two-stage sum adds the same numbers in a different grouping. For whole numbers that is the same sum, because addition is associative and commutative. (For floating-point numbers the last digits can differ; the next tutorial in this course is about exactly which aggregates may be split this way.) `ex01` checks that the salted and plain results are equal on the 300,000 orders.

## 8.5 See it in Spark

### Spark's partition rule is `pmod(hash(key), n)`, exactly

`ex01_spark_partitions.py` prints the hash and `pmod` of customers 1 to 8:

```python
ids.select("customer_id",
           F.hash("customer_id").alias("hash"),
           F.pmod(F.hash("customer_id"), F.lit(3)).alias("pmod_3")).show()
```

```text
+-----------+-----------+------+
|customer_id|       hash|pmod_3|
+-----------+-----------+------+
|          1| -559580957|     1|
|          2| 1765031574|     0|
|          3|-1823081949|     0|
|          4| -397064898|     0|
|          5| 1023896466|     0|
|          6| -331964951|     1|
|          7| 1079293707|     0|
|          8| -132918897|     0|
+-----------+-----------+------+
```

Then it checks the rule on every row: it repartitions 20,000 rows by `customer_id` and compares the partition each row really landed in (`spark_partition_id()`) with the predicted `pmod(hash(customer_id), n)`:

```text
n = 3: rows = 20000, rows where actual <> predicted = 0
n = 8: rows = 20000, rows where actual <> predicted = 0
n = 200: rows = 20000, rows where actual <> predicted = 0
```

And `ex03_murmur3.py`, plain Python with no Spark, gets the same eight hash values from the MurmurHash3 steps (multiply, rotate, mix). The physical plan names the rule too: `Exchange hashpartitioning(customer_id, 200)`.

### The hot key, measured

300,000 orders, customer 7 owning 240,060 of them, repartitioned into 8 partitions by `customer_id`:

```text
largest keys: [(7, 240060), (148, 60), (463, 60)]
by customer_id, n = 8: rows per partition = [8100, 8040, 7500, 247560, 6720, 8040, 7320, 6720]; max = 247560, mean = 37500.0, max/mean = 6.60
lower bound max(total/n, largest key) = max(37500, 240060) = 240060; measured max = 247560 (1.031 x the bound)
```

Customer 7 hashes to partition 3 (`pmod(1079293707, 8) = 3`), and partition 3 holds its 240,060 rows plus 7,500 others. The bound of step 3 is within about 3% of the real maximum.

### Random unevenness, with Spark's real hash

The same experiment as the table in step 4, but with Spark's hash of the integers `0 .. K-1` instead of random numbers, into 200 partitions:

```text
K =     2000: mean = 10, max = 20, min = 2, max/mean = 2.000
K =    20000: mean = 100, max = 128, min = 63, max/mean = 1.280
K =   200000: mean = 1000, max = 1067, min = 912, max/mean = 1.067
K =  1000000: mean = 5000, max = 5176, min = 4813, max/mean = 1.035
```

Every maximum falls inside the range the random simulation produced (16 to 24, 118 to 147, 1,060 to 1,133, 5,134 to 5,273). On these keys, Spark's hash behaves like a fair random throw.

### Salting, measured

```python
salted = orders.withColumn("salt", F.col("order_id") % k)
salted.repartition(8, "customer_id", "salt")
```

The "measured in Spark" column of the step 5 table comes from this loop (full lines in `ex01.out.txt`). With two columns, Spark chains the hash: the hash of the first column becomes the seed for the second. `ex04_checks.py` confirms it for `(7, 0)` to `(7, 3)` by hand.

### A groupBy sum is gentler than a repartition

A `groupBy(...).sum(...)` does not ship every row. Its plan has two `HashAggregate` steps around the exchange:

```text
*(2) HashAggregate(keys=[customer_id#2], functions=[sum(amount#3)])
+- Exchange hashpartitioning(customer_id#2, 8), ENSURE_REQUIREMENTS, [plan_id=17]
   +- *(1) HashAggregate(keys=[customer_id#2], functions=[partial_sum(amount#3)])
```

Each map task first adds up its own rows per customer (`partial_sum`), so at most one row per customer per map task crosses the shuffle. With 4 map tasks, customer 7's 240,060 rows become at most 4 partial sums (`ex05_partial_agg.py`). The hot key still lands in one partition, but as 4 rows, not 240,060. The skew problem of this tutorial is therefore about operations that must move every row: repartitioning, joins, and aggregates whose partial state keeps every value (such as `collect_list`, whose plan shows `partial_collect_list`, or an exact median). Which aggregates can be summed in parts is the subject of the next tutorial in this course.

### NULL keys all go to one place

```text
+-----------+----------+------+
|customer_id|      hash|pmod_8|
+-----------+----------+------+
|       NULL|        42|     2|
|       NULL|        42|     2|
|          5|1023896466|     2|
+-----------+----------+------+

promo_id with 40% NULL, n = 8: rows per partition = [8080, 7400, 47340, 7500, 7320, 7500, 7520, 7340]; max = 47340, mean = 12500.0, max/mean = 3.79
```

The hash of NULL is the seed itself, 42, so every NULL lands in partition `pmod(42, n)`. A nullable column is a hot key whose value is "nothing". For an inner join Spark removes them first (the plan shows `Filter isnotnull(promo_id)` below the exchange), because NULL never equals anything. For a left join it cannot remove them from the left side, and the plan shows no such filter there (`ex04.out.txt`).

## 8.6 Where it breaks

- **Equal cost per row.** Step 2 assumed every row costs the same. Wide rows, nested data or a Python UDF on some keys break that; the bound then holds in bytes or in work, not in rows.
- **Enough cores.** With fewer cores `C` than tasks, tasks wait in line, and the stage takes at least `c × max(m / C, h)`. The hot key still sets the floor.
- **Memory.** When one partition no longer fits in the memory set aside for it, Spark spills to disk, and time grows faster than the row count. A 6.6 times larger partition can be much more than 6.6 times slower.
- **Changing `n` moves everything.** `pmod(hash, n)` depends on `n`; change 200 to 201 and almost every key moves. (A streaming query's state is tied to its original number of shuffle partitions; Databricks book, section 22.17.)
- **AQE does part of this for you.** With AQE on (the default since Spark 3.2.0), the Spark 4.2.0 tuning guide says it "dynamically handles skew in sort-merge join by splitting (and replicating if needed) skewed tasks into roughly evenly sized tasks". A partition counts as skewed when it is larger than `spark.sql.adaptive.skewJoin.skewedPartitionFactor` (5) times the median partition **and** larger than `spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes` (256 MB). It also splits skewed partitions of a `REBALANCE` (`spark.sql.adaptive.optimizeSkewsInRebalancePartitions.enabled`). The page lists no such handling for aggregations. Section 22.13 of the Databricks book shows AQE's skew join working.
- **Broadcast joins avoid the shuffle.** If one side is small, Spark can copy it to every executor and never shuffle the big side, so no hot partition forms (Databricks book, section 3.7).
- **Salting a join copies the other side.** To join salted orders, every customer row must exist once per salt value, so the customers side grows `k` times. Cheap when the hot key has one row there; ruinous when it has thousands (exercise 5).
- **The hash is fixed, not random.** Everything about averages assumed random-looking behaviour. Someone who knows the hash can choose keys that all collide.

## 8.7 Exercises

Do 1 to 4 with a pencil. 5 to 7 need only a few lines of thought. 8 is code.

**E1. Customers 1 to 6 (hashes in the table of 8.3) have 100, 50, 70, 30, 40 and 10 orders. Send them to `n = 4` partitions. Give the rows per partition and max / mean. (Hint: for remainders by 4, the last two digits are enough. Why?)**

??? success "Answer"
    100 is divisible by 4, so a number and its last two digits leave the same remainder by 4. Java remainders: 1: `-(57 mod 4) = -1`, pmod `3`; 2: `74 mod 4 = 2`; 3: `-(49 mod 4) = -1`, pmod `3`; 4: `-(98 mod 4) = -2`, pmod `2`; 5: `66 mod 4 = 2`; 6: `-(51 mod 4) = -3`, pmod `1`.

    Loads: partition 0 = 0, partition 1 = 10 (customer 6), partition 2 = 50 + 30 + 40 = 120, partition 3 = 100 + 70 = 170. Total 300, mean 75, max / mean = 170 / 75 = 2.27. (Checked in `ex04.out.txt`.)

**E2. A table has 1,000,000 rows and its largest key has 30,000. The stage runs with 200 partitions on 200 cores. What is the best speed-up this stage can reach? How many cores are worth paying for?**

??? success "Answer"
    `max(m / n, h) = max(5,000, 30,000) = 30,000`, so the stage takes at least the time of 30,000 rows. Speed-up ≤ `min(n, m / h) = min(200, 33.3) = 33.3`. Beyond about 34 partitions (and cores) this stage gets no faster; the other cores finish early and wait. Fix the key (salt it, or handle it separately), not the cluster.

**E3. 2,000 customers with 500 orders each go to 200 partitions. About how many rows does the fullest partition hold? How many keys would be needed for the fullest partition to be within 10% of the average?**

??? success "Answer"
    Mean 10 keys per partition; formula `10 + sqrt(2 × 10 × 5.30) = 20.3` keys, simulation 19.7, Spark's real hash 20. So about 20 × 500 = 10,000 rows, twice the average 5,000.

    Within 10%: `sqrt(2 × (K/n) × ln n) ≤ 0.1 × K/n`. Square and divide by `K/n`: `K/n ≥ 2 ln n / 0.01 = 200 × 5.30 = 1,060`. So `K ≥ 1,060 × 200 ≈ 212,000` keys. Check: in the table of step 4, 200,000 keys gave max / mean 1.09.

**E4. A hot key has 600,000 of 2,000,000 rows, `n = 100`. The other rows spread evenly (14,000 per partition). For `k = 100`, `1,000` and `10,000` salt values, estimate the fullest partition. Which `k` would you choose?**

??? success "Answer"
    Mean load = 20,000. Slices of `600,000 / k` rows are thrown into 100 partitions; the fullest partition ≈ slice × (largest number of slices) + 14,000.

    | k | slice | largest number of slices (simulated; formula) | fullest partition |
    | ---: | ---: | ---: | ---: |
    | 100 | 6,000 | 4.2 (4.0) | about 39,400 |
    | 1,000 | 600 | 18.8 (19.6) | about 25,300 |
    | 10,000 | 60 | 125.9 (130.3) | about 21,600 |

    `k = 100 = n` still leaves one task twice the average. `k = 1,000` brings it within about 27%, `k = 10,000` within about 8%. For an aggregation the cost of a large `k` is small (at most `k` partial rows for that key), so 1,000 to 10,000 is reasonable. The rule `k ≥ f × n = 0.3 × 100 = 30` is only the starting point. (Numbers from `ex04.out.txt`.)

**E5. You salt `orders` with `k = 1,000` to join it to another table on `customer_id`. How many rows does the other side gain if the hot customer has (a) 1 row there (the customers table), (b) 50,000 rows there (a shipments table)?**

??? success "Answer"
    The other side's rows for the salted key are copied once per salt value: (a) 1 × 1,000 = 1,000 rows, nothing. (b) 50,000 × 1,000 = 50,000,000 rows: the cure is worse than the disease. In case (b), first ask whether the join is right at all (a many-to-many join on a customer multiplies rows anyway), pre-aggregate one side, or join on a finer key. For a sort-merge join with AQE on, also check whether AQE's skew join already splits it.

**E6. 10 million orders, 40% with a NULL `promo_id`, are left-joined to `promotions` on `promo_id` with 200 shuffle partitions. Roughly how many rows does the slowest task receive, compared with the average? What is the fix?**

??? success "Answer"
    The 4,000,000 NULL rows all hash to 42 and land in partition `pmod(42, 200) = 42`, plus about `6,000,000 / 200 = 30,000` ordinary rows: about 4,030,000 rows against a mean of 50,000, roughly 80 times. A NULL can never match in an equality join, so split: join only the rows where `promo_id IS NOT NULL`, then `unionByName` the NULL rows back with NULL promotion columns. Spark adds that filter itself for an inner join (section 8.5) but cannot for the preserved side of a left join.

**E7. A shuffle has 2,000 map tasks and 200 reduce partitions. Each reduce task fetches one block from each map task. How many block fetches is that? What happens to that number if you raise the partitions to 2,000 "to fix skew"? Does it fix the skew?**

??? success "Answer"
    2,000 × 200 = 400,000 fetches; with 2,000 partitions, 4,000,000, each ten times smaller. More partitions reduce the random unevenness of step 4 and the average task size, but a hot key is not split by any `n`: its partition still holds all of its rows. The bound `max(m / n, h)` shows it: raising `n` lowers only the first term.

**E8. (Code.) Using `murmur3_int` from `ex03_murmur3.py`, write `partition(key, n)` and check it against Spark for keys 1 to 1,000 and `n = 200`. Then use the chaining rule (first column's hash as the second's seed) to predict the partition of `(7, salt)` for `salt = 0..3` with `n = 8`.**

??? success "Answer"
    ```python
    from ex03_murmur3 import murmur3_int, pmod

    def partition(key, n):
        return pmod(murmur3_int(key), n)

    def partition2(a, b, n):
        seed = murmur3_int(a) & 0xFFFFFFFF      # the first hash, as 32 unsigned bits
        return pmod(murmur3_int(b, seed=seed), n)

    print([partition2(7, s, 8) for s in range(4)])   # [0, 2, 7, 3]
    ```

    Spark gives the same: `ex04.out.txt` shows partitions 0, 2, 7 and 3 for `(7, 0)` to `(7, 3)`. To compare keys 1 to 1,000, collect `F.pmod(F.hash("k"), F.lit(200))` from `spark.range(1, 1001)` cast to int, and compare with `[partition(k, 200) for k in range(1, 1001)]`: all 1,000 agree (`ex04.out.txt`).

## 8.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a skewed job you met, what the key was, and what fixed it.)*

## 8.9 Further reading

On your own sites:

- Hashing and hash tables: [Algorithms, ch 7. Searching and hashing](https://cs.akadian.ca/books/algorithms/07-Searching-and-Hashing/)
- Randomized analysis: [Algorithms, ch 21. Randomized and amortized analysis](https://cs.akadian.ca/books/algorithms/21-Randomized-and-Amortized-Analysis/)
- Many processors: [Algorithms, ch 24. Algorithms for big data and many processors](https://cs.akadian.ca/books/algorithms/24-Algorithms-for-Big-Data-and-Many-Processors/)
- Expectation and linearity: [Probability, ch 6. Expectation and variance](https://math.akadian.ca/books/probability/06-Expectation-and-Variance.html)
- Spark itself: [3. Apache Spark for data engineers](../../data-engineering/databricks/03-Apache-Spark.md) and [22. Performance tuning](../../data-engineering/databricks/22-Performance-Tuning.md) (sections 22.13 and 22.14)

Original sources:

- M. Raab and A. Steger, "'Balls into Bins': A Simple and Tight Analysis", *Randomization and Approximation Techniques in Computer Science (RANDOM 1998)*, Lecture Notes in Computer Science 1518, Springer. The formula of step 4.
- G. M. Amdahl, "Validity of the single processor approach to achieving large scale computing capabilities", AFIPS Spring Joint Computer Conference, 1967.
- [Spark SQL performance tuning (4.2.0)](https://spark.apache.org/docs/4.2.0/sql-performance-tuning.html): adaptive query execution, skew join settings.

## Glossary

- **Shuffle**: moving rows between tasks so that rows with the same key end up in the same partition.
- **Partition**: one slice of the data, processed by one task.
- **Hash partitioning**: choosing a row's partition as `pmod(hash(key), n)`.
- **pmod**: the remainder after division, made non-negative.
- **Skew**: one partition much larger than the others, usually because one key owns many rows.
- **Hot key**: a key with a large share of the rows.
- **Salting**: adding a small extra column to the key so that one hot key becomes `k` smaller keys.
- **Partial aggregation**: summing inside each task before the shuffle, so fewer rows cross it.
- **Balls into bins**: the probability problem of throwing `K` balls at random into `n` bins and asking how full the fullest bin is.
