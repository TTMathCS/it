# 8. Columns, files and reflections

*A dashboard asks for revenue per region per day from a table of two billion orders, and the answer comes back in about a second. Nothing about that is magic. The engine reads only the columns the query names, only the files whose statistics say they might match, and, when it can, a small pre-added table instead of the orders themselves. Each of the three is short arithmetic: bytes per column, a range test per file, and sums of sums. This tutorial does each by hand and checks it with a program.*

!!! abstract "In this tutorial"
    **You will learn:**

    - how Apache Arrow lays a column out in memory: a validity bitmap of one bit per row, the values, offsets for strings, and padding to 8 or 64 bytes
    - how much a query saves by reading 3 columns out of 40
    - Apache Iceberg's partition transforms, `day`, `bucket[N]` and `truncate[W]`, worked by hand and checked against every test value in the Iceberg spec
    - how a file is skipped by its min and max, why sorted data skips almost everything, and why a random file of `k` rows can be skipped with chance only `p^k`
    - what a Dremio aggregation reflection keeps, how big it can get, which questions it answers exactly (sum, count, min, max, average) and which only approximately (distinct counts, through a HyperLogLog sketch)

    **You need:** multiplication, remainders, powers, and the idea of a sum of sums from [Spark 9. Why sums split and medians do not](../spark/09-Why-Sums-Split.md).

    **How to learn from it:** read 8.1 to 8.3, close the page, redo the examples of 8.3 on paper, then try the exercises in 8.7 before opening any answer. Plan about two and a half hours.

**About the examples.** No Dremio server was run for this tutorial. The column layout is checked with **pyarrow 26.0.1**, the Python library of the Arrow project. The partition transforms are ported from the **Iceberg table spec** and checked against its own test values; all eleven match. The facts about reflections (the measures Dremio offers, the default date granularity, the size of its sketch) were read from Dremio's open-source code, `dremio-oss`; how Dremio's current commercial versions differ is unknown here. File skipping and the reflection are **simulations** on made-up data. The scripts and their full output: [ex01_arrow.py](src/08/ex01_arrow.py) ([output](src/08/ex01.out.txt)), [ex02_iceberg.py](src/08/ex02_iceberg.py) ([output](src/08/ex02.out.txt)), [ex03_pruning.py](src/08/ex03_pruning.py) ([output](src/08/ex03.out.txt)), [ex04_reflection.py](src/08/ex04_reflection.py) ([output](src/08/ex04.out.txt)) and [ex05_buckets.py](src/08/ex05_buckets.py) ([output](src/08/ex05.out.txt)).

## 8.1 The question

1. A column holds one million 32-bit integers, some of them missing. How many bytes does it take in memory, and what does "missing" cost?
2. A table is split by `bucket[16](customer_id)`. Which bucket holds customer 34, and can you compute it on paper?
3. A filter asks for `amount BETWEEN 900 AND 1000`. Which files can the engine skip without opening them, and why does sorting the data first change the answer from "almost none" to "almost all"?
4. A reflection keeps revenue per region per day. Can it answer revenue per region? The average order? The number of different customers?

## 8.2 The idea: read less

A query's cost is mostly the bytes it reads. There are three ways to read fewer:

- **Fewer columns.** In a columnar format each column is stored apart, so a query that names 3 columns reads 3. Dremio works on data in memory as **Apache Arrow** columns (Arrow was started in 2016 with Dremio's engineers among its creators), and the files underneath are usually Parquet ([Parquet 1. Column files](../parquet/01-Column-Files.md)).
- **Fewer files.** A table in **Apache Iceberg** is a list of data files, and the metadata keeps, for each file, its partition values and the lowest and highest value of each column. A file whose range cannot match the filter is never opened.
- **Fewer rows.** A Dremio **reflection** is a copy of a table or view that Dremio keeps and refreshes, and uses in place of the original when it can answer the query. An **aggregation reflection** keeps rows already grouped by chosen columns (the **dimensions**) with chosen totals (the **measures**). Dremio's open-source code lists the measures it offers: `MIN`, `MAX`, `SUM`, `COUNT` and `APPROX_COUNT_DISTINCT`.

Each of these turns into one line of arithmetic.

## 8.3 The math by hand

### Step 1. An Arrow column

The Arrow spec stores a column of `n` values in **buffers**:

- a **validity bitmap**: one bit per value, 1 if present and 0 if null. Value `j` is bit `j mod 8` of byte `j div 8`, counting bits from the right. It takes `⌈n / 8⌉` bytes.
- the **values**: `n × width` bytes for fixed-width types (4 for `int32`, 8 for `int64` and `double`).
- for strings, an **offsets** buffer of `n + 1` 32-bit integers, and one buffer of all the UTF-8 bytes end to end. String `j` runs from `offsets[j]` to `offsets[j+1]`.

The spec's own example is `['joe', null, null, 'mark']`:

```text
validity   00001001          slots 0 and 3 present (read right to left)
offsets    0, 3, 3, 3, 7     'joe' is bytes 0-2, the nulls are empty, 'mark' is 3-6
values     joemark
```

`ex01` builds the same array with pyarrow and finds exactly these three buffers.

For one million `int32` values: bitmap `⌈1,000,000 / 8⌉ = 125,000` bytes, values `1,000,000 × 4 = 4,000,000` bytes. So the ability to say "missing" costs `125,000 / 4,000,000 = 3.1%` of the data, whatever the number of nulls. pyarrow allocates 125,000 and 4,000,000 bytes.

Buffers are also **padded**: the spec recommends allocating and padding each buffer to a multiple of 64 bytes, the width of the largest SIMD registers on common x86 chips, so a loop can always load 64 bytes at a time; when Arrow data is sent between processes, padding to a multiple of 8 or 64 is required. Padding to 64 rounds 125,000 up to `⌈125,000 / 64⌉ × 64 = 1,954 × 64 = 125,056`. pyarrow 26's messages pad to 8: an `int32` column of 7 values (28 bytes) is sent as 32 (`ex01`, part 4).

### Step 2. Columns a query does not read

A table of 2 billion rows and 40 `int64` columns: one column is `2 × 10^9 × 8 = 16 × 10^9` bytes, 16 GB; all forty are 640 GB. A query that names three reads `3 × 16 = 48` GB, `3 / 40 = 7.5%`. That is before compression (Parquet's dictionaries and run lengths, which shrink most columns much further) and before skipping files.

### Step 3. Partitions: day, bucket, truncate

An Iceberg table is split into **partitions** by a **transform** of a column, and each data file holds rows of one partition only. The spec defines the transforms; three of them:

**`day(ts)`** is the number of days since 1970-01-01. For `2017-11-16 22:31:08`: from 1970-01-01 to 2017-01-01 is 47 years with 12 leap days (1972, 1976, …, 2016), `47 × 365 + 12 = 17,167` days; then 304 days to November 1 and 15 more to the 16th: `17,167 + 304 + 15 = 17,486`. `ex02` agrees.

**`bucket[N](x)`** spreads values evenly over `N` partitions by a hash:

```text
bucket[N](x) = (murmur3_x86_32(x) & Integer.MAX_VALUE) mod N
```

Murmur3 is the same 32-bit hash used by Elasticsearch's routing ([Elasticsearch 8](../elasticsearch/08-How-Search-Ranks.md)), seeded with 0. Integers are hashed as 8 little-endian bytes, so `34` and `34L` land in the same bucket. The spec gives the hash of `34` as `2017239379`. `& Integer.MAX_VALUE` clears the sign bit, so the number cannot be negative; here it is already positive. Then `2017239379 mod 16`: `16 × 126,077,461 = 2,017,239,376`, remainder **3**. Customer 34 is in bucket 3.

A negative hash shows why the mask is needed: customer `-7` hashes to `-1,703,207,563`. Clearing the sign bit adds `2^31 = 2,147,483,648`, giving `444,276,085`, and `444,276,085 mod 16 = 5`.

**`truncate[W](v)`** rounds an integer down to a multiple of `W`, as `v − (v mod W)` with a remainder that **must not be negative**. For `−37` and `W = 10`, the remainder is 3 (since `−37 = −4 × 10 + 3`), so the answer is `−40`. Java's and C's `%` would give `−7` and the answer `−30`, putting `−37` in the wrong partition; the spec warns about this and gives the safe form `v − (((v % W) + W) % W)`. For strings, `truncate[L]` keeps the first `L` characters: `truncate[3]('iceberg') = 'ice'`.

The spec lists test values for every hashed type, and the port in `ex02` reproduces all eleven:

```text
int 34 (hashed as a long)                2017239379  spec   2017239379  ok
decimal 14.20 (unscaled 1420)            -500754589  spec   -500754589  ok
date 2017-11-16                          -653330422  spec   -653330422  ok
timestamp 2017-11-16T22:31:08           -2047944441  spec  -2047944441  ok
string 'iceberg'                         1210000089  spec   1210000089  ok
string '34' (not the same as int 34)     -427558391  spec   -427558391  ok
```

A query with `WHERE day = …` or `WHERE customer_id = 34` reads one partition. Seven days of a table with 365 daily partitions read `7 / 365 = 1.9%` of its files.

### Step 4. Skipping a file by its min and max

For each data file, Iceberg's metadata keeps a **lower bound** and an **upper bound** for each column: every non-null value in the file lies between them. For a filter `amount BETWEEN 900 AND 1000`, a file with range `[lo, hi]` can contain a match only if the two ranges overlap:

```text
read the file  ⟺  not (hi < 900 or lo > 1000)
```

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 230" role="img" aria-label="Six files drawn as bars on an amount axis from 0 to 2000, with the filter band from 900 to 1000. Files f3, from 400 to 950, and f4, from 990 to 1500, cross the band and are read. Files f1, f2, f5 and f6 lie entirely outside it and are skipped; f6 stops at 899, just short of the band.">
<g font-size="12" fill="currentColor">
<rect x="303" y="14" width="27" height="170" fill="currentColor" opacity="0.18"/>
<text x="290" y="10">900–1000</text>
<g stroke="currentColor" stroke-width="10">
<line x1="61" y1="30" x2="190" y2="30" opacity="0.35"/>
<line x1="92" y1="56" x2="295" y2="56" opacity="0.35"/>
<line x1="168" y1="82" x2="317" y2="82"/>
<line x1="327" y1="108" x2="465" y2="108"/>
<line x1="333" y1="134" x2="600" y2="134" opacity="0.35"/>
<line x1="68" y1="160" x2="302" y2="160" opacity="0.35"/>
</g>
<text x="2" y="34">f1 skip</text><text x="2" y="60">f2 skip</text><text x="2" y="86">f3 read</text><text x="2" y="112">f4 read</text><text x="2" y="138">f5 skip</text><text x="2" y="164">f6 skip</text>
<g stroke="currentColor"><line x1="60" y1="190" x2="600" y2="190"/></g>
<text x="56" y="206">0</text><text x="183" y="206">500</text><text x="318" y="206">1000</text><text x="453" y="206">1500</text><text x="586" y="206">2000</text>
<text x="270" y="224">amount</text>
</g>
</svg>
<figcaption>Figure 8.1. Six files by their min and max of <code>amount</code>, and the filter 900 to 1000 (<code>ex03</code>, part 1). Only f3 and f4 cross the band; the other four are skipped without being opened. f6 ends at 899, one short.</figcaption>
</figure>

Of the six files in Figure 8.1, two are read. How many files a filter skips depends on how the rows were placed. `ex03` writes the same one million random values into 100 files of 10,000 rows twice:

```text
rows in arrival order : read 100 of 100 files
rows sorted by x      : read   1 of 100 files
```

for the filter `x ≥ 0.99`, which matches 9,923 rows. The arithmetic behind the first line: a file of `k` random values, each below 0.9 with chance 0.9, can be skipped for `x ≥ 0.9` only if **all** `k` values are below 0.9. Independent chances multiply:

```text
P(skip) = 0.9^k        k = 10: 0.349     k = 50: 0.005     k = 10,000: about 10^-458
```

So with randomly placed rows a real file is never skipped. Sorting (or clustering) the data by the filtered column makes each file's range narrow, and then most files miss the filter. Dates are often close to sorted already, because rows arrive in time order, which is why filters on dates skip well.

### Step 5. A reflection: sums of sums

An aggregation reflection on `orders` with dimensions `region` and the order date, and measures `SUM(amount)`, `COUNT(*)`, `MIN(amount)`, `MAX(amount)` and `APPROX_COUNT_DISTINCT(customer_id)`, keeps one row per (region, day). Dremio's code cuts a timestamp dimension to a `DATE` by default, so the rows are per day, not per second.

**Size.** It has at most `regions × days` rows, whatever the number of orders: 8 regions over 365 days give at most `8 × 365 = 2,920` rows, against 2 billion orders, a factor of about 685,000. `ex04` builds one from 200,000 made-up orders and gets exactly 2,920 rows.

**Rolling up.** The query "revenue per region" groups by fewer columns than the reflection. Each region's revenue is the sum of its 365 daily sums, because addition can be regrouped freely (the reason is the same as in [Spark 9](../spark/09-Why-Sums-Split.md)). In the same way:

| Asked for | Answered from the reflection by | Exact? |
| --- | --- | --- |
| `SUM` | adding the sums | yes |
| `COUNT` | adding the counts | yes |
| `MIN`, `MAX` | the min of the mins, the max of the maxes | yes |
| `AVG` | total `SUM` ÷ total `COUNT` | yes |
| `AVG`, the wrong way | the mean of the daily averages | no |
| distinct count | adding the daily distinct counts | no, far too big |
| distinct count | merging the daily sketches | approximately |
| median | — | no: the reflection does not keep it |

The wrong average, by hand: day 1 has one order of $100, day 2 has three orders of $10. The true average is `(100 + 30) / 4 = 32.50`. The mean of the daily averages is `(100 + 10) / 2 = 55`, because it gives the lone big order the same weight as three small ones. Keeping `SUM` and `COUNT` and dividing at the end is always right.

**Distinct customers.** A customer who orders on 7 days is counted once per day, so adding daily distinct counts counts them 7 times. In `ex04`, North has 3,708 different customers, but its daily distinct counts add up to 24,482. The measure `APPROX_COUNT_DISTINCT` stores a **HyperLogLog** sketch per row instead of a number. In `dremio-oss` it is Apache DataSketches' HLL with `lgConfigK = 12`, that is `2^12 = 4,096` registers. Two sketches merge by taking the larger value register by register, and the merged sketch estimates the distinct count of the union. With `m` registers the usual standard error is `1.04 / √m = 1.04 / 64 = 1.6%`. The textbook sketch in `ex04`, also with 4,096 registers, estimates North at 3,779 (+1.9%), and the eight regions are off by 3.0% at most.

## 8.4 Why it is true

**One bit per row.** A bitmap needs one bit per value to tell present from missing, so `n / 8` bytes is the least possible without compression, and against 4-byte values it is always `1 / 32 = 3.1%`.

**Bucket sizes are even, not equal.** If the hash behaves like a random number, each of 100,000 ids falls in a given bucket of 16 with chance `1/16`, so a bucket holds on average 6,250 with standard deviation `√(100,000 × 1/16 × 15/16) ≈ 77`. `ex02` finds sizes from 6,059 to 6,324, all within 2.5 standard deviations. Buckets even out the **number of keys**, not the number of rows per key: a customer with a million orders still lands in one bucket, the same skew as in [Spark 8](../spark/08-Shuffles-and-Skew.md).

**Doubling buckets splits them.** `(h mod 32) mod 16 = h mod 16` because 16 divides 32, so moving from 16 to 32 buckets sends bucket `b` only to `b` and `b + 16` (`ex05`). With 24 buckets, 16 does not divide 24, and bucket 3 spreads over three new buckets.

**Skipping is safe.** The bounds are guaranteed: every value in the file is at least the lower and at most the upper bound. If the ranges do not overlap, no row can match, so skipping never loses a row. Reading a file that turns out to have no match is only wasted work, never a wrong answer.

**Sums of sums.** Grouping the orders by (region, day) and then adding over days gives the same total as adding all of a region's orders at once, because each order is in exactly one day and addition can be reordered and regrouped. Counts, minima and maxima work the same way. An average is a ratio of two sums, so it rolls up through the sums, not by itself. A median depends on all the values, and no fixed set of totals per day determines it.

**The sketch merges.** Taking the larger value register by register is the same as building one sketch from all the values at once, because each register keeps a maximum, and the maximum of maxima is the overall maximum. So the merged sketch is exactly the sketch of the union, and its error is that of any sketch of that size.

## 8.5 See it in code

`ex01` checks the Arrow arithmetic of steps 1 and 2:

```text
by hand: bitmap ceil(1,000,000/8) = 125,000 bytes, data 1,000,000 x 4 = 4,000,000 bytes
pyarrow: bitmap 125,000 bytes, data 4,000,000 bytes, null_count 100,000
```

`ex03` prints the six files of Figure 8.1 and the table of `0.9^k` against simulation:

```text
k =     10: formula 0.349   simulated 0.349 (20,000 trials)
k =     50: formula 0.00515   simulated 0.0053 (20,000 trials)
```

`ex04` answers every query of step 5 from the raw rows and from the reflection:

```text
North  revenue $ 6,280,791.30  orders 24,685  max $ 500.00  avg $254.4376 = sum/count $254.4376; mean of daily averages $254.6246
sums, counts and maxima equal the raw answer exactly: True
North  exact 3,708  sum of daily distinct counts 24,482 (wrong)  merged sketch    3,779 (+1.92%)
```

In made-up data with similar numbers of orders each day, the mean of the daily averages is only slightly off ($254.62 against $254.44); with very uneven days, as in the hand example, it is far off.

## 8.6 Where it breaks

- **How Dremio chooses** whether a reflection can answer a query, and its cost model, are not worked here; their details in current versions are unknown to this tutorial. The rules of step 5 say what a reflection *can* answer, not when Dremio will use it.
- **Reflections are copies.** Between refreshes they can be behind the source tables. How far behind depends on the refresh schedule you set.
- **Float sums** can differ in the last digits when added in another order; money is safer as integers or decimals ([Spark 9](../spark/09-Why-Sums-Split.md)). `ex04` keeps cents as integers.
- **Bounds can be loose.** Bounds on long strings may be stored truncated, and a file with a few far-off values gets a wide range. A loose bound only costs extra reads.
- **Nulls and NaN** are not inside the bounds; Iceberg counts them separately, and a filter on them needs those counts.
- **Small files** make each file's statistics cheap to skip but add metadata to read; very large files skip less. The best file size is a trade-off, not a formula.

## 8.7 Exercises

Do 1 to 6 with a pencil. 7 needs a little care. 8 is code.

**E1. A column of 10,000,000 `int64` values may contain nulls. How many bytes do the bitmap and the values take, before and after padding each to a multiple of 64?**

??? success "Answer"
    Bitmap `⌈10,000,000 / 8⌉ = 1,250,000` bytes, padded to `⌈1,250,000 / 64⌉ × 64 = 19,532 × 64 = 1,250,048`. Values `10,000,000 × 8 = 80,000,000` bytes, already a multiple of 64.

**E2. Write the validity bitmap byte, the offsets and the number of value bytes of `['a', '', null, 'été']`.**

??? success "Answer"
    Slots 0, 1 and 3 are present (the empty string is a value, not a null): `00001011`. `'été'` is 5 UTF-8 bytes (`é` takes 2). Offsets `0, 1, 1, 1, 6`; 6 value bytes. pyarrow gives the same (checked while writing this answer).

**E3. Using the spec's hash values, find `bucket[8]` of the integer 34 and of the string `'iceberg'`.**

??? success "Answer"
    `2017239379 mod 8`: since `2017239379 mod 16 = 3`, and 8 divides 16, the answer is `3 mod 8 = 3`. `1210000089` is positive, and `1210000089 = 8 × 151,250,011 + 1`, so bucket 1.

**E4. Find `truncate[100]` of 250 and of −250, and `day` of 2026-01-01.**

??? success "Answer"
    `250 − 50 = 200`. For −250 the non-negative remainder is 50 (`−250 = −3 × 100 + 50`), so `−300`. From 1970-01-01 to 2026-01-01: 56 years with 14 leap days (1972 to 2024), `56 × 365 + 14 = 20,454`.

**E5. Files have `amount` ranges f1 `[0, 99]`, f2 `[100, 500]`, f3 `[50, 150]`, f4 `[101, 200]`. Which are read for `amount < 100`?**

??? success "Answer"
    A file can match if its lower bound is below 100: f1 (0) and f3 (50). f2 starts at 100, which is not below 100, and f4 at 101. Two of four.

**E6. Values are random between 0 and 1. What is the chance that a file of 20 rows can be skipped for `x ≥ 0.95`? Of 1,000 rows?**

??? success "Answer"
    All rows must be below 0.95: `0.95^20 ≈ 0.358`, about one file in three. `0.95^1000 ≈ 5.3 × 10^-23`: never.

**E7. A reflection has two rows for one region. Day 1: count 2, sum 300, min 100, max 200. Day 2: count 3, sum 90, min 20, max 40. Give the two-day count, sum, min, max and average. What does the mean of the daily averages give? Can you find the median?**

??? success "Answer"
    Count 5, sum 390, min 20, max 200, average `390 / 5 = 78`. The mean of daily averages is `(150 + 30) / 2 = 90`, wrong. The median is the third of the five values in order; we know two are between 100 and 200 and three between 20 and 40, so the median is between 20 and 40 but its exact value is unknown from the reflection.

**E8. (Code.) Show that if a table moves from 16 to 32 buckets, every id of old bucket `b` goes to new bucket `b` or `b + 16`. What happens with 24?**

??? success "Answer"
    ```python
    from ex02_iceberg import hash_long, bucket

    for cid in range(1, 100_001):
        h = hash_long(cid)
        assert bucket(h, 32) % 16 == bucket(h, 16)
    ```
    No assertion fails. Bucket 0 goes to 0 and 16, bucket 3 to 3 and 19, bucket 15 to 15 and 31. With 24 buckets, bucket 3 of 16 spreads over 3 of the 24. ([ex05_buckets.py](src/08/ex05_buckets.py), [output](src/08/ex05.out.txt).)

## 8.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a slow Dremio query, a reflection that did or did not get used, or a table whose files skipped badly, and which step explained it.)*

## 8.9 Further reading

On your own sites:

- [Parquet 1. Column files](../parquet/01-Column-Files.md): dictionaries, run lengths and min/max inside one file
- [Spark 9. Why sums split and medians do not](../spark/09-Why-Sums-Split.md): the same rollup rules, and HyperLogLog in more detail
- [Elasticsearch 8](../elasticsearch/08-How-Search-Ranks.md) and [Kafka 8](../kafka/08-Log-Offsets-and-Lag.md): hashing keys into shards and partitions

Original sources:

- Apache Arrow, *Arrow Columnar Format* (the specification: buffers, validity bitmaps, alignment and padding).
- Apache Iceberg, *Iceberg Table Spec* (partition transforms, Appendix B hash test values, file-level lower and upper bounds).
- Dremio, `dremio-oss` on GitHub: `reflection-common.proto` (the measure types), `ReflectionExpander.java` (the default `DATE` granularity and the `HLL` measure), `StatisticsAggrFunctions.java` (`HLL_ACCURACY = 12`).
- P. Flajolet, É. Fusy, O. Gandouet and F. Meunier, "HyperLogLog: the analysis of a near-optimal cardinality estimation algorithm", *AofA 2007*.
- A. Appleby, MurmurHash3 (the `x86_32` variant), 2011.

## Glossary

- **Columnar format**: each column stored apart, so a query reads only the columns it names.
- **Apache Arrow**: a columnar layout for data in memory, shared by many engines, Dremio among them.
- **Validity bitmap**: one bit per value, 1 for present, 0 for null.
- **Offsets buffer**: where each string starts and ends inside one buffer of bytes.
- **Padding**: extra bytes so each buffer's length is a multiple of 8 or 64.
- **Apache Iceberg**: a table format that keeps a list of data files with their partitions and column statistics.
- **Partition transform**: the rule that gives each row its partition: `identity`, `day`, `bucket[N]`, `truncate[W]` and others.
- **Lower and upper bound**: the smallest and largest non-null value of a column in one file.
- **Reflection**: a copy of a table or view, grouped or not, that Dremio refreshes and uses in place of the original when it can.
- **Dimension, measure**: in an aggregation reflection, the columns it groups by, and the totals it keeps.
- **HyperLogLog**: a sketch of `m` small registers that estimates a distinct count and merges by maximum.
