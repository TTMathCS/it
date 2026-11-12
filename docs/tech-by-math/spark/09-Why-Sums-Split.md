# 9. Why sums split and medians do not

*A report groups a million orders by region. The total and the average come back in seconds. The median takes far longer, and with more data it runs out of memory. Same rows, same groups, same cluster. This tutorial works out why with pencil-sized examples: which answers can be built from small pieces, which provably cannot, what "approximate" buys and costs, and why even a plain sum of decimals can change in its last digits when the number of partitions changes. Every number from Spark below was produced by a real run.*

!!! abstract "In this tutorial"
    **You will learn:**

    - why Spark can add up each partition first and send only a few numbers through the shuffle (`partial_sum`)
    - the three kinds of aggregates: those that merge directly (sum, count, min, max), those that merge through a small helper (average, standard deviation), and those that cannot be built from any small summary (exact median, exact distinct count)
    - a short proof that an exact median must keep every value
    - how an approximate median keeps about `1/ε` values and is wrong by at most `ε × N` places, and how to read Spark's `accuracy`
    - how `approx_count_distinct` turns distinct counting into a merge by maximum
    - why a sum of decimals is not the same in 1, 4 and 16 partitions

    **You need:** averages, sorting, and the idea of a rank (the 3rd smallest value has rank 3). [8. Shuffles and skew in Spark](08-Shuffles-and-Skew.md) explains the shuffle and partial aggregation; this tutorial picks up where its section 8.5 stops.

    **How to learn from it:** read 9.1 to 9.3, close the page, redo the examples of 9.3 on paper, then try the exercises in 9.7 before opening any answer. Plan about two and a half hours.

**About the examples.** Every Spark result ran on Apache Spark 4.2.0 in local mode (`local[4]`, 4 input partitions, 4 shuffle partitions), with adaptive query execution turned off. The data is a million rows with a group `k = id mod 10` (10 groups of 100,000 rows) and a value `x = (id × 7919) mod 100,003`, which spreads the values evenly between 0 and 100,002. Shuffle sizes are read from Spark's own monitoring API, the numbers the Spark UI shows. The scripts and their full output are next to this page: [ex01_spark_merge.py](src/09/ex01_spark_merge.py) ([output](src/09/ex01.out.txt)), [ex02_by_hand.py](src/09/ex02_by_hand.py) ([output](src/09/ex02.out.txt)), [ex03_spark_distinct.py](src/09/ex03_spark_distinct.py) ([output](src/09/ex03.out.txt)) and [ex04_buffers.py](src/09/ex04_buffers.py) ([output](src/09/ex04.out.txt)), plus the answer to exercise E8, [ex05_merge_variance.py](src/09/ex05_merge_variance.py). `ex02` is plain Python and checks every pencil example of 9.3.

## 9.1 The question

The job is `groupBy("k").agg(...)` over a million rows in 4 partitions. On the Spark UI, the stage before the shuffle reports how much it wrote. For six aggregates over the same data:

| aggregate | rows written to the shuffle | bytes written to the shuffle |
| --- | ---: | ---: |
| `count(x)` | 40 | 1,012 |
| `sum(x)` | 40 | 1,117 |
| `avg(x)` | 40 | 1,297 |
| `percentile_approx(x, 0.5, 10000)` | 40 | 3,348,440 |
| exact `median(x)` | 40 | 5,999,772 |
| `collect_list(x)` | 40 | 4,955,811 |

Every aggregate sends 40 rows: one per group (10) per input partition (4). But a sum's row is a single number, and an exact median's row is a bag of 25,000 values. Three questions:

1. Why can a sum be sent as one number, and an average as two?
2. Is there a cleverer way to send a median, or is "keep everything" forced?
3. What does `percentile_approx` give up to be smaller, and when is it actually smaller?

## 9.2 The idea: an aggregate is a summary plus a merge rule

Spark computes an aggregate in two steps around the shuffle, as tutorial 8 showed:

```text
HashAggregate(keys=[k], functions=[sum(x)])               <- after the shuffle: merge the pieces
+- HashAggregate(keys=[k], functions=[partial_sum(x)])    <- before it: one summary per group and partition
```

For this to work, the aggregate needs three things:

- a **summary** (Spark calls it the aggregation buffer) that each task builds from its own rows;
- a **merge rule** that combines two summaries into the summary of all their rows together;
- a **finish rule** that turns the last summary into the answer.

The merge rule must give the same result whatever the grouping and order, because Spark does not choose them in advance: any partition can arrive first. In algebra words, the merge must be **associative** (`(a ⊕ b) ⊕ c = a ⊕ (b ⊕ c)`) and **commutative** (`a ⊕ b = b ⊕ a`).

Jim Gray and his colleagues sorted aggregates into three kinds by the size of that summary (1997):

| kind | summary | examples |
| --- | --- | --- |
| **distributive** | the answer itself | count, sum, min, max |
| **algebraic** | a few numbers, fixed in advance | average (sum, count), standard deviation (count, mean, M2) |
| **holistic** | no summary of fixed size is enough | exact median, exact mode, exact distinct count |

The cost of the shuffle is the size of the summary. Distributive and algebraic aggregates send a few numbers per group and partition, however many rows there are. Holistic ones send something that grows with the data.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 180" role="img" aria-label="Three partitions of one group. Left: each partition sends one number, its sum, 18, 40 and 18; they merge into 76. Right: each partition must send its whole sorted list of values, and only the merged list gives the median 5.5.">
<g font-size="13" fill="currentColor">
<text x="20" y="22" font-weight="bold">sum: send one number</text>
<text x="340" y="22" font-weight="bold">median: send every value</text>
<g>
<rect x="20" y="40" width="120" height="34" rx="5" fill="none" stroke="currentColor"/><text x="30" y="62">4, 8, 6 → 18</text>
<rect x="20" y="86" width="120" height="34" rx="5" fill="none" stroke="currentColor"/><text x="30" y="108">10, 30 → 40</text>
<rect x="20" y="132" width="160" height="34" rx="5" fill="none" stroke="currentColor"/><text x="30" y="154">1, 2, 3, 5, 7 → 18</text>
<rect x="220" y="86" width="80" height="34" rx="5" fill="none" stroke="currentColor" stroke-width="2.5"/><text x="232" y="108" font-weight="bold">76</text>
</g>
<g stroke="currentColor" fill="none" stroke-width="1.2"><line x1="140" y1="57" x2="220" y2="100"/><line x1="140" y1="103" x2="220" y2="103"/><line x1="180" y1="149" x2="220" y2="106"/></g>
<g>
<rect x="340" y="40" width="120" height="34" rx="5" fill="none" stroke="currentColor"/><text x="350" y="62">4, 6, 8</text>
<rect x="340" y="86" width="120" height="34" rx="5" fill="none" stroke="currentColor"/><text x="350" y="108">10, 30</text>
<rect x="340" y="132" width="120" height="34" rx="5" fill="none" stroke="currentColor"/><text x="350" y="154">1, 2, 3, 5, 7</text>
<rect x="490" y="70" width="140" height="66" rx="5" fill="none" stroke="currentColor" stroke-width="2.5"/>
<text x="500" y="92">1 2 3 4 <tspan font-weight="bold">5 6</tspan> 7</text><text x="500" y="112">8 10 30</text><text x="500" y="130" font-weight="bold">median 5.5</text>
</g>
<g stroke="currentColor" fill="none" stroke-width="1.2"><line x1="460" y1="57" x2="490" y2="90"/><line x1="460" y1="103" x2="490" y2="103"/><line x1="460" y1="149" x2="490" y2="116"/></g>
</g>
</svg>
<figcaption>Figure 9.1. One group spread over three partitions (the example of 9.3). A sum needs one number from each; an exact median needs every value. The partition medians are 6, 20 and 3, and their median, 6, is not the true median, 5.5.</figcaption>
</figure>

## 9.3 The math by hand

One group, ten values, spread over three partitions:

```text
P1 = {4, 8, 6}     P2 = {10, 30}     P3 = {1, 2, 3, 5, 7}
```

### Step 1. A sum splits

Partial sums: `18`, `40`, `18`. Merged: `18 + 40 + 18 = 76`, the sum of all ten values. Any grouping gives 76: `(18 + 40) + 18 = 18 + (40 + 18)`. The summary is one number, the merge is `+`, and the empty partition's summary is `0`. Count (merge `+`), min (merge `min`) and max (merge `max`) work the same way.

### Step 2. An average splits only with a helper

The partition averages are `6`, `20` and `3.6`. Their average is `(6 + 20 + 3.6) / 3 = 9.87`. The true average is `76 / 10 = 7.6`. The partitions have different sizes, so their averages must not count equally.

Carry two numbers instead, `(sum, count)`: `(18, 3)`, `(40, 2)`, `(18, 5)`. The merge adds both: `(76, 10)`. The finish divides: `76 / 10 = 7.6`. Correct. This is exactly what Spark keeps: the plan of `avg` shows a partial buffer of `sum` and `count` (`ex04`).

The **variance** needs a third number. Spark keeps `(n, mean, M2)`, where `M2` is the sum of squared distances from the mean. Two summaries `a` and `b` merge as

```text
n    = n_a + n_b
d    = mean_b − mean_a
mean = mean_a + d × n_b / n
M2   = M2_a + M2_b + d² × n_a × n_b / n
```

and the finish is `variance = M2 / (n − 1)`. The plan of `stddev` shows its buffer as `n, avg, m2` (`ex04`). Why not the simpler `(n, Σx, Σx²)` from a textbook? It is also algebraic, but `Σx² − (Σx)²/n` subtracts two large, nearly equal numbers, and floating-point arithmetic loses most of the digits in such a subtraction. The `M2` form avoids it. (Exercise E3 merges two summaries by hand.)

### Step 3. A median does not split

The partition medians are `6`, `20` and `3`; their median is `6`. The sorted values are `1 2 3 4 5 6 7 8 10 30`, so the true median is `(5 + 6) / 2 = 5.5`. Wrong again. But this time no helper of fixed size can fix it, and here is why.

**Claim.** To find the exact median of `A ∪ B` from a summary of `A` and the full `B`, the summary of `A` must let you recover every value of `A`. So it must be as large as `A`.

**Proof by example.** Take `A = {3, 7, 9, 12, 20}` (`m = 5` values). Let `B` hold `m` values too: `j` very small ones (say −1000) and `m − j` very large ones (say 1000). The combined list has `2m = 10` values; take the lower median, the 5th smallest. In sorted order come first the `j` small values, then `3, 7, 9, 12, 20`, then the large ones. The 5th smallest is therefore the `(5 − j)`-th value of `A`:

| j | B | lower median of A ∪ B |
| ---: | --- | ---: |
| 0 | five 1000s | 20 |
| 1 | one −1000, four 1000s | 12 |
| 2 | two −1000s, three 1000s | 9 |
| 3 | three −1000s, two 1000s | 7 |
| 4 | four −1000s, one 1000 | 3 |

Every value of `A` is the right answer for some `B`. A summary of `A` that forgot any one of them would give a wrong answer for that `B`. Since Spark does not know the other partitions when it builds a partition's summary, the summary has to keep every value (it may store repeated values once, with a count). The same argument works for any size `m`: an exact median is **holistic**.

The exact distinct count is holistic for a similar reason: to know whether the next partition's values are new, you must remember which values you have seen.

### Step 4. An approximate median keeps a sample with ranks

Relax the goal: return a value whose rank is within `ε × N` of the middle, where `N` is the number of values. Then a fixed-size summary works.

**The simple version.** Sort the partition and keep every `g`-th value with its rank in the partition. For `P1 = {1, 3, 5, …, 199}` (100 values) and `g = 10`, keep `(19, 10), (39, 20), (59, 30), …`: 10 pairs. For a value `v`, the kept pairs give its rank in that partition to within `g − 1` places: at least the rank of the last kept value at or below `v`, at most one less than the rank of the next kept value.

With several partitions, add up the lower bounds and the upper bounds. The uncertainties add too, so with `P` partitions the rank of `v` is known to within `P × (g − 1)`. Choose `g = ε × n_i` in a partition of `n_i` values. It keeps `n_i / g = 1/ε` values, and the total uncertainty is at most `ε × (n_1 + … + n_P) = ε × N`. **The summary keeps `1/ε` values per partition, whatever the partition's size.**

Worked (in `ex02`): `P1` = the 100 odd numbers 1 to 199, `P2` = the 100 numbers 2, 6, 10, …, 398, `g = 10`. Each summary keeps 10 pairs; for every kept value the true rank lies inside the estimated interval, and the widest interval is 18 = `2 × (g − 1)`. The value whose interval centres closest to the middle (rank 100 of 200) is 119, with an interval of ranks 90 to 108. Its true rank is 90: 10 places from the middle, within the promised 18. (The true lower median is 133; a rank error of 10 here is a value error of 14, because 10 places in this data span 14 units.)

**The real version.** The simple version sorts the partition first, so the task still holds all its values for a moment. Michael Greenwald and Sanjeev Khanna (2001) built a summary in one pass over unsorted data, with at most `(11 / (2ε)) × log₂(2εN)` entries (their paper's bound). Spark's `approxQuantile` documentation says it "implements a variation of the Greenwald-Khanna algorithm", and its `percentile_approx` keeps the same kind of summary (the class `QuantileSummaries` in Spark's code). The guarantee is the same shape as above: **the error is in rank, not in value**, and `ε = 1 / accuracy`.

### Step 5. A sum of decimals depends on the order

Step 1 said the order does not matter. That is true for whole numbers and for exact fractions. It is not true for the floating-point numbers (`double`) computers use for decimals, because each addition rounds:

```text
(0.1 + 0.2) + 0.3 = 0.6000000000000001
0.1 + (0.2 + 0.3) = 0.6
1e16 + 1 − 1e16   = 0.0        1e16 − 1e16 + 1 = 1.0
```

(`ex02`.) Floating-point addition is commutative but **not associative**. A sum over partitions groups the additions by partition, so a different number of partitions can change the last digits. The answer is still close; the error is tiny relative to the total, as long as there are no huge cancellations as in the third line.

## 9.4 Why it is true

**Any order, same answer.** Spark merges partial summaries in whatever order the shuffle delivers them, and the partial step itself sees rows in an order that depends on how the input was split. An aggregate gives a well-defined answer only if the merge is associative and commutative on its summaries. Sum, count, min and max are, on whole numbers. `(sum, count)` merges by adding both parts, so it inherits the property. The `(n, mean, M2)` merge is also associative and commutative in exact arithmetic (it is the exact statistics of the union, whichever way the union is built), which is what makes it correct.

**The median needs everything.** Proved in step 3 by showing, for a set `A` of `m` distinct values, `m` different continuations `B` that make each value of `A` the median. A summary that answers all of them correctly must distinguish every value of `A`. This is the two-part version of a classical result of J. Ian Munro and Mike Paterson (1980): finding the exact median of `N` values in one pass needs memory that grows like `N`.

**The approximate median.** The rank bound of step 4 was proved there for the simple sample: each partition's uncertainty is below `g = ε n_i`, and uncertainties add. The Greenwald-Khanna bound is a theorem of their paper and is not proved here. Section 9.5 checks Spark's guarantee on a million values.

**Floating point.** IEEE 754 arithmetic rounds each result to the nearest representable number. Rounding after each step is what breaks associativity: in `1e16 + 1`, the exact result 10,000,000,000,000,001 is not representable as a double (doubles near `1e16` are 2 apart), so it rounds to `1e16` and the 1 is lost.

## 9.5 See it in Spark

### The plans: every aggregate has a partial step

`ex01` prints the two aggregate steps of a sum, an exact median and an approximate one:

```text
-- sum
HashAggregate(keys=[k#1L], functions=[sum(x#2)], ...)
+- HashAggregate(keys=[k#1L], functions=[partial_sum(x#2)], output=[k#1L, sum#138])
-- exact median
ObjectHashAggregate(keys=[k#1L], functions=[percentile(x#2, 0.5, 1, 0, 0, false)], ...)
+- ObjectHashAggregate(keys=[k#1L], functions=[partial_percentile(x#2, 0.5, 1, 0, 0, false)], output=[k#1L, buf#145])
-- percentile_approx
ObjectHashAggregate(keys=[k#1L], functions=[percentile_approx(x#2, 0.5, 10000, 0, 0)], ...)
+- ObjectHashAggregate(keys=[k#1L], functions=[partial_percentile_approx(x#2, 0.5, 10000, 0, 0)], output=[k#1L, buf#152])
```

The exact median has a partial step too, so partial aggregation alone is not the difference. The difference is what the partial step outputs. For a sum it is one number (`sum#138`). For a median it is a `buf`, an object holding every distinct value of the group in that partition with its count. The table in 9.1 shows the cost: 1,117 bytes for the sum, 5,999,772 bytes for the exact median, even more than `collect_list` (4,955,811), which also ships every value. The plans of `avg` and `stddev` show their algebraic buffers by name (`ex04`):

```text
partial_stddev(x#2), partial_avg(x#2)], output=[k#1L, n#10, avg#11, m2#12, sum#35, count#36L]
```

### The approximate median keeps its promise

The exact median of the million `x` values is 50,001. For three accuracies, `ex01` finds where Spark's approximate answer really sits in the sorted data:

| accuracy | ε = 1/accuracy | answer | true rank of the answer | off from rank 500,000 by | allowed |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 1% | 49,830 | 498,297 | 0.17% of the rows | 1% |
| 1,000 | 0.1% | 49,979 | 499,787 | 0.021% | 0.1% |
| 10,000 | 0.01% | 49,999 | 499,987 | 0.0013% | 0.01% |

All three are well inside the bound. The value errors are small here only because these values are spread evenly; on data with gaps, a small rank error can be a large value error (step 4).

### Approximate is smaller only when the partitions are big

`ex03` measures the summary size for each accuracy, on the same 40 partial summaries of 25,000 values each:

| `percentile_approx` accuracy | bytes through the shuffle |
| ---: | ---: |
| 100 | 74,051 |
| 1,000 | 647,519 |
| 10,000 | 3,348,440 |
| exact median, for comparison | 5,999,772 |

With accuracy 10,000 the summary may keep on the order of 10,000 entries per partition (step 4: about `1/ε`, times a slowly growing factor in the real algorithm), and each partition has only 25,000 values, so it saves less than half. The rule of thumb from step 4: an approximate quantile pays off when each task holds many more values than the accuracy. At accuracy 100 it is 81 times smaller than the exact median here, and the gap grows with the data, because the exact buffer grows with the rows and the approximate one hardly does.

### Distinct counts: merge by maximum

`approx_count_distinct` uses HyperLogLog++ (the class `HyperLogLogPlusPlus` in Spark). The idea, in one paragraph: hash each value to random-looking bits; send it to one of `m` registers by its first bits; in that register, keep the largest number of leading zeros seen in the rest of the bits. Seeing a long run of zeros is rare, so the maximum tells you roughly how many different values went into the register. Repeats hash the same way and change nothing, which is why it counts distinct values. Two summaries merge by taking the **maximum, register by register**. That merge is associative, commutative, and also idempotent (`a ⊕ a = a`), so the same partition merged twice does no harm.

Spark chooses the number of registers from `rsd`, the relative standard deviation you ask for: `p = ⌈2 × log₂(1.106 / rsd)⌉` and `m = 2^p` registers of 6 bits, packed 10 to a 64-bit word (constants read from Spark 4.2's `HyperLogLogPlusPlusHelper`). For the default `rsd = 0.05`: `log₂(22.12) = 4.47`, so `p = 9`, `m = 512` registers, 52 words = 416 bytes. For `rsd = 0.01`: `p = 14`, 16,384 registers, 1,639 words = 13,112 bytes. Neither depends on the number of rows. Measured (`ex03`), per query, all shuffles added up:

| aggregate per group | rows through the shuffle | bytes through the shuffle | answer for group 0 (true: 100,000) |
| --- | ---: | ---: | ---: |
| `count_distinct(x)` | 1,000,040 | 8,517,401 | 100,000 |
| `approx_count_distinct(x)` (rsd 0.05) | 40 | 17,193 | 95,546 (4.45% low) |
| `approx_count_distinct(x, 0.01)` | 40 | 465,981 | 100,425 (0.43% high) |

The exact count shuffles twice and ships every distinct `(k, x)` pair: a million rows. The sketches ship 40 rows each, about 40 × 416 and 40 × 13,112 bytes (the shuffle compresses, so the last one is a little below its raw size). The errors are within about one standard deviation. A note on honesty: each of the 10 groups holds 100,000 of the same 100,003 numbers, so all ten estimates are nearly identical (`ex03` lists them); this is really one sample of the error, not ten.

### The same sum in 1, 4 and 16 partitions

`ex01` sums a million doubles `0.1 × (i mod 7 + 1)` after `repartition(p)`:

```text
 1 partitions: 399999.70000026026
 4 partitions: 399999.7000010521
16 partitions: 399999.70000000263
exact (as a fraction): 399999.7
```

Three different answers, all correct to nine significant digits, none exact. Spark does not promise the order in which a partition's rows or the shuffle's blocks are added, so a rerun can also change the last digits. For money, use `DECIMAL`, whose sums are exact.

## 9.6 Where it breaks

- **Rank error is not value error.** `percentile_approx` promises a rank within `ε × N`. Where the data has a gap (many orders at 20 dollars, then many at 500), being a few ranks off can move the answer from 20 to 500.
- **Small partitions defeat the summary.** As measured above, an approximate summary with accuracy 10,000 over 25,000 values is not small. Lower the accuracy, or let the partitions grow, before relying on it to save memory.
- **A hot key still lands on one task.** Partial aggregation shrinks a hot key's sum to a few rows (tutorial 8, section 8.5). For an exact median, the partial buffers of the hot key still hold all its values, and they all merge in one task. Salting does not help a median: the median of salted pieces is not the median (step 3).
- **Distinct counts across groups do not add.** The distinct count of a week is not the sum of the seven daily counts, exact or approximate; values repeat across days. HyperLogLog sketches of the days, kept and merged by maximum, do give the week. Spark 4.2 has functions that keep the sketch itself (`hll_sketch_agg`, `hll_union_agg`, `hll_union`, `hll_sketch_estimate`); this tutorial did not test them.
- **Floating point.** Step 5. Results that must match to the cent belong in `DECIMAL`. Tests that compare doubles need a tolerance, not equality.
- **`avg` of averages in SQL.** Averaging a column that is itself an average (of days, of stores) is the mistake of step 2. Keep sums and counts in summary tables, not averages.

## 9.7 Exercises

Do 1 to 5 with a pencil. 6 and 7 need only a few lines of thought. 8 is code.

**E1. Which of these are distributive, which algebraic, which holistic: `max`, `count(*)`, the range `max − min`, the geometric mean, the most frequent value (mode), the 90th percentile? For each algebraic one, name the summary.**

??? success "Answer"
    `max`, `count(*)`: distributive. Range: algebraic, summary `(min, max)`. Geometric mean `(x_1 × … × x_n)^(1/n)`: algebraic, summary `(Σ ln x, n)`; finish `exp(Σ ln x / n)` (for positive values). Mode: holistic, by an argument like step 3 (a summary must remember how often every value occurred). 90th percentile: holistic exactly, like the median; approximate with a quantile summary.

**E2. A table of store averages has (store, orders, average): (A, 200, 50), (B, 50, 10), (C, 750, 30). What is the average order value over all stores? What does `AVG(average)` give?**

??? success "Answer"
    Sums: 200 × 50 = 10,000; 50 × 10 = 500; 750 × 30 = 22,500. Total 33,000 over 1,000 orders: 33.00. `AVG(average)` = (50 + 10 + 30) / 3 = 30.00, which counts store B's 50 orders as much as store C's 750.

**E3. Merge the variance summaries of `A = {2, 4, 6}` and `B = {10, 12}` with the formula of step 2. Check against the ten-second direct computation.**

??? success "Answer"
    `A`: n = 3, mean 4, M2 = 4 + 0 + 4 = 8. `B`: n = 2, mean 11, M2 = 1 + 1 = 2. Merge: n = 5, d = 11 − 4 = 7, mean = 4 + 7 × 2 / 5 = 6.8, M2 = 8 + 2 + 49 × 3 × 2 / 5 = 10 + 58.8 = 68.8. Sample variance 68.8 / 4 = 17.2, standard deviation 4.147.

    Direct: mean of 2, 4, 6, 10, 12 is 34 / 5 = 6.8; squared distances 23.04, 7.84, 0.64, 10.24, 27.04 add to 68.8. Same.

**E4. Redo the proof of step 3 for `A = {1, 4, 9}`. Give the three sets `B` and the median each produces.**

??? success "Answer"
    `m = 3`, combined 6 values, lower median = 3rd smallest. `j = 0`, `B = {1000, 1000, 1000}`: 9. `j = 1`, `B = {−1000, 1000, 1000}`: 4. `j = 2`, `B = {−1000, −1000, 1000}`: 1. Each value of `A` is the answer for one `B`.

**E5. A task holds 4 million values. With the simple summary of step 4, how many values does it keep for ε = 1%? For ε = 0.1%? If 200 tasks each send such a summary for the same group, how far from the middle can the merged answer be, in rows, for ε = 1%?**

??? success "Answer"
    `1/ε`: 100 values for 1%, 1,000 for 0.1%, whatever the task's size. Merged: N = 200 × 4,000,000 = 800,000,000 values, and the rank error is at most ε × N = 8,000,000 rows, that is 1% of the rows, as promised. The summaries total 200 × 100 = 20,000 values, against 800 million for the exact median.

**E6. You must report a daily median order value for the last 365 days, every morning, from a table of 2 billion orders. Exact or approximate? What would you store so that each morning only yesterday is read?**

??? success "Answer"
    A median per day is a separate group per day, so yesterday's median needs only yesterday's rows: compute it each morning and store one number per day. Exact is fine if one day's rows fit in one task; otherwise use `percentile_approx` with an accuracy well below the rows per task. A median of the whole year cannot be built from the 365 daily medians (step 3); for that, keep a quantile summary per day and merge them, or compute the year's median directly.

**E7. A job sums a `DOUBLE` column of payments. The test compares the result with yesterday's run on the same data and fails: 1,234,567.8900000001 against 1,234,567.89. Is the data different? What is the fix?**

??? success "Answer"
    Probably not: the number of partitions or the order of the additions changed (step 5, and the 1, 4, 16 partitions run). Fix the type (`DECIMAL(18, 2)` for money, whose sums are exact), or compare with a tolerance, such as a relative difference below 1e-12.

**E8. (Code.) Write `merge(a, b)` for `(n, mean, M2)` summaries in Python. Split 1,000 random numbers into 7 uneven pieces, summarise each piece, merge them in a random order, and compare the variance with `statistics.variance` of all 1,000.**

??? success "Answer"
    ```python
    import random, statistics

    def summ(xs):
        n, m = len(xs), sum(xs) / len(xs)
        return n, m, sum((x - m) ** 2 for x in xs)

    def merge(a, b):
        na, ma, m2a = a
        nb, mb, m2b = b
        n = na + nb
        d = mb - ma
        return n, ma + d * nb / n, m2a + m2b + d * d * na * nb / n

    random.seed(1)
    xs = [random.gauss(50, 12) for _ in range(1000)]
    cuts = sorted(random.sample(range(1, 1000), 6))
    pieces = [xs[i:j] for i, j in zip([0] + cuts, cuts + [1000])]
    random.shuffle(pieces)
    total = summ(pieces[0])
    for p in pieces[1:]:
        total = merge(total, summ(p))
    n, mean, m2 = total
    print(m2 / (n - 1), statistics.variance(xs))
    ```

    It prints `145.06316068156016 145.06316068156013` ([ex05_merge_variance.py](src/09/ex05_merge_variance.py)): equal to 16 significant digits, with the last digits different for the reason of step 5.

## 9.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a slow or memory-hungry aggregate you met, what it was, and what you replaced it with.)*

## 9.9 Further reading

On your own sites:

- Many processors: [Algorithms, ch 24. Algorithms for big data and many processors](https://cs.akadian.ca/books/algorithms/24-Algorithms-for-Big-Data-and-Many-Processors/)
- Expectation and variance: [Probability, ch 6. Expectation and variance](https://math.akadian.ca/books/probability/06-Expectation-and-Variance.html)
- Spark itself: [3. Apache Spark for data engineers](../../data-engineering/databricks/03-Apache-Spark.md) and [22. Performance tuning](../../data-engineering/databricks/22-Performance-Tuning.md)

Original sources:

- J. Gray, S. Chaudhuri, A. Bosworth, A. Layman, D. Reichart, M. Venkatrao, F. Pellow and H. Pirahesh, "Data Cube: A Relational Aggregation Operator Generalizing Group-By, Cross-Tab, and Sub-Totals", *Data Mining and Knowledge Discovery* 1(1), 1997. Distributive, algebraic and holistic aggregates.
- J. I. Munro and M. S. Paterson, "Selection and sorting with limited storage", *Theoretical Computer Science* 12, 1980. Exact selection needs memory.
- M. Greenwald and S. Khanna, "Space-efficient online computation of quantile summaries", *SIGMOD 2001*, [doi:10.1145/375663.375670](https://doi.org/10.1145/375663.375670). The quantile summary behind Spark's.
- P. Flajolet, É. Fusy, O. Gandouet and F. Meunier, "HyperLogLog: the analysis of a near-optimal cardinality estimation algorithm", *AofA 2007*; S. Heule, M. Nunkesser and A. Hall, "HyperLogLog in practice", *EDBT 2013* (the "++" version).
- T. F. Chan, G. H. Golub and R. J. LeVeque, "Algorithms for computing the sample variance: analysis and recommendations", *The American Statistician* 37(3), 1983. The merge formula of step 2.
- D. Goldberg, "What every computer scientist should know about floating-point arithmetic", *ACM Computing Surveys* 23(1), 1991.

## Glossary

- **Aggregate**: a function from many rows to one value per group, such as a sum or a median.
- **Summary (aggregation buffer)**: what a task keeps for one group before the shuffle.
- **Merge rule**: how two summaries combine into the summary of all their rows.
- **Associative**: the grouping does not matter: `(a ⊕ b) ⊕ c = a ⊕ (b ⊕ c)`.
- **Commutative**: the order does not matter: `a ⊕ b = b ⊕ a`.
- **Idempotent**: merging something with itself changes nothing: `a ⊕ a = a`.
- **Distributive / algebraic / holistic**: the summary is the answer / a few fixed numbers / cannot be of fixed size.
- **Rank**: a value's place in sorted order; the median has rank about `N / 2`.
- **Quantile summary**: a small sample of values with rank bounds, from which any percentile can be read within `ε × N` places.
- **HyperLogLog**: a sketch of `m` small registers that estimates a distinct count and merges by maximum.
- **Floating point (double)**: the computer's way to store decimals with about 16 significant digits, rounding after every operation.
