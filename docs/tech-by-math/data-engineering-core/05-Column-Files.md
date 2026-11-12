# 5. Column files: run-length, dictionary coding, min/max skipping

*Save a table as Parquet instead of CSV and the file shrinks several times; filter it by date and the reader touches a few percent of it. Neither is magic. This tutorial takes a 12-value column through the three tricks a column file uses (a dictionary, run-length coding and bit-packing), counts the bits by hand, proves why sorting gives the fewest runs, and works out which row groups a filter can skip using only each group's minimum and maximum. Then it writes a million orders with pyarrow, predicts the size of each column from the same arithmetic, and counts the bytes a one-day filter really reads.*

!!! abstract "In this tutorial"
    **You will learn:**

    - why storing a table column by column, in row groups, makes both compression and skipping possible
    - dictionary coding, bit-packing and run-length coding, worked bit by bit on a 12-value column
    - why the number of runs is the number of value changes plus one, and why sorting minimises it
    - min/max skipping: which row groups a filter must read, why it never misses a row, and why it only works on sorted (or clustered) data
    - how to predict the size of a real Parquet column from its number of distinct values, and check it against the file's own metadata
    - entropy as the floor no encoding can beat, and where these tricks stop working

    **You need:** binary numbers and log₂ ([Networks Math, ch 1. Bits, binary and masks](https://networks.akadian.ca/books/math/01-Bits-Binary-and-Masks/) if rusty). The practical side is the [Databricks book](../../data-engineering/databricks/index.md): [ch 4. Delta Lake](../../data-engineering/databricks/04-Delta-Lake.md) and [ch 22. Performance tuning](../../data-engineering/databricks/22-Performance-Tuning.md), sections 22.6 and 22.7.

    **How to learn from it:** read 5.1 to 5.3, close the page, encode the 12 cities and skip the row groups on paper, then try the exercises in 5.7 before opening any answer. Plan about three hours.

**About the examples.** The by-hand work is checked by [ex01_by_hand.py](src/05/ex01_by_hand.py) ([output](src/05/ex01.out.txt)). The Parquet numbers come from [ex02_parquet.py](src/05/ex02_parquet.py) ([output](src/05/ex02.out.txt)), which writes the files with pyarrow 26 and counts every byte the reader asks for by wrapping the file in a counter.

## 5.1 The question

A million orders, six columns (an id, the date, a customer, a city, a status, an amount), saved as CSV: **45.4 MB**. The same rows saved as Parquet with pyarrow's defaults: **13.8 MB**, 3.3 times smaller; with zstd compression 9.3 MB; with one more setting, **6.4 MB**, 7 times smaller. Then a query for one day's orders, `WHERE order_date = '2026-07-15'`, reads **5.5%** of the Parquet file. But shuffle the same rows into random order and write them again, and the same query reads **all** of it.

Why is the column file so much smaller, why does a filter read so little of it, and why does row order decide both?

## 5.2 The idea: store columns, in blocks, with a summary of each

A CSV, like most databases' table pages, stores **row after row**: all six values of order 1, then all six of order 2. A **column file** turns this around. It cuts the table into **row groups** (here 50,000 rows each) and, inside each group, stores each column's values together, as a **column chunk**. Two things follow.

1. **Similar values sit next to each other.** A chunk of the `status` column holds 50,000 values drawn from 4 words. Values that repeat compress very well, and they compress best when equal values are side by side.
2. **Each chunk can carry a summary.** The file stores, for each chunk, the smallest and largest value. A reader that wants one day can look at the summaries in the file's footer first and skip every row group whose date range does not contain that day. And a query that needs only `amount` reads only the `amount` chunks.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 240" role="img" aria-label="A grid: columns order_date, city, status and amount across the top; four row groups down the side, labelled with their date ranges, Jan 1 to Jan 19, and so on, with Jul 2 to Jul 20 as the third. A query for July 15 reads only the third row: its date range is the only one that contains the day. A query for the sum of amount reads only the amount column, top to bottom.">
<g font-size="13" fill="currentColor">
<text x="230" y="22" text-anchor="middle" font-weight="bold">order_date</text>
<text x="330" y="22" text-anchor="middle" font-weight="bold">city</text>
<text x="430" y="22" text-anchor="middle" font-weight="bold">status</text>
<text x="530" y="22" text-anchor="middle" font-weight="bold">amount</text>
<text x="10" y="55">group 1</text><text x="10" y="71" font-size="11">Jan 1 – Jan 19</text>
<text x="10" y="105">group 2</text><text x="10" y="121" font-size="11">Jan 19 – Feb 6</text>
<text x="10" y="155" font-weight="bold">group 11</text><text x="10" y="171" font-size="11" font-weight="bold">Jul 2 – Jul 20</text>
<text x="10" y="205">group 20</text><text x="10" y="221" font-size="11">Dec 13 – Dec 31</text>
<text x="150" y="138" text-anchor="middle">⋮</text>
</g>
<g fill="none" stroke="currentColor" stroke-width="1.2">
<rect x="185" y="40" width="90" height="36" rx="3"/><rect x="285" y="40" width="90" height="36" rx="3"/><rect x="385" y="40" width="90" height="36" rx="3"/><rect x="485" y="40" width="90" height="36" rx="3"/>
<rect x="185" y="90" width="90" height="36" rx="3"/><rect x="285" y="90" width="90" height="36" rx="3"/><rect x="385" y="90" width="90" height="36" rx="3"/><rect x="485" y="90" width="90" height="36" rx="3"/>
<rect x="185" y="140" width="90" height="36" rx="3" stroke-width="3"/><rect x="285" y="140" width="90" height="36" rx="3" stroke-width="3"/><rect x="385" y="140" width="90" height="36" rx="3" stroke-width="3"/><rect x="485" y="140" width="90" height="36" rx="3" stroke-width="3"/>
<rect x="185" y="190" width="90" height="36" rx="3"/><rect x="285" y="190" width="90" height="36" rx="3"/><rect x="385" y="190" width="90" height="36" rx="3"/><rect x="485" y="190" width="90" height="36" rx="3"/>
<rect x="478" y="33" width="104" height="200" rx="6" stroke-width="2" stroke-dasharray="6 4"/>
</g>
</svg>
<figcaption>Figure 5.1. The million-order file of 5.5, drawn small: 20 row groups of 50,000 rows, each stored column by column. The footer keeps each chunk's minimum and maximum, so a date filter can pick out the one group it needs (thick), and a query on one column reads only that column (dashed). The date ranges are the real ones from the file.</figcaption>
</figure>

## 5.3 The math by hand

### Step 1. Twelve cities, plain

Here is one column of 12 rows:

```text
Oslo Oslo Oslo Lagos Lagos Toronto Toronto Toronto Toronto Oslo Oslo Lagos
```

Written as text it takes 5 × 4 + 3 × 5 + 4 × 7 = 63 letters: **63 bytes = 504 bits**. (Oslo appears 5 times, Lagos 3, Toronto 4.)

### Step 2. A dictionary, then bit-packing

There are only 3 different values. Number them, in a **dictionary** stored once: 0 = Lagos, 1 = Oslo, 2 = Toronto. The column becomes a list of codes:

```text
1 1 1 0 0 2 2 2 2 1 1 0
```

Three codes fit in 2 bits each (00, 01, 10), so **bit-packing** stores them as **12 × 2 = 24 bits**, plus the dictionary (16 letters, once per chunk). The rule: with V distinct values, each code takes ⌈log₂ V⌉ bits.

### Step 3. Run-length coding

Look at the codes again: there are stretches of the same code. A **run** is a maximal stretch of equal values, written as (value, length):

```text
(1,3) (0,2) (2,4) (1,2) (0,1)          5 runs
```

Run-length coding stores the runs instead of the values. Here 5 runs of (2-bit code, small count) save little; on a long, sorted column they save almost everything. Count the runs another way: there is a new run exactly where the value **changes**. The codes change 4 times (1→0, 0→2, 2→1, 1→0), and 4 changes make **5** runs.

### Step 4. Sort, and count again

Sort the column:

```text
Lagos Lagos Lagos Oslo Oslo Oslo Oslo Oslo Toronto Toronto Toronto Toronto
codes: 0 0 0 1 1 1 1 1 2 2 2 2        runs: (0,3) (1,5) (2,4)    3 runs
```

3 runs, one per distinct value, and no column of these 12 values can have fewer. Parquet's main encoding for dictionary codes (`RLE_DICTIONARY`) is a hybrid of exactly these two: runs where values repeat, bit-packed groups where they do not.

### Step 5. Min/max skipping

Now a column of 12 sale days, stored in 4 row groups of 3 rows each, in the order they were loaded:

| Row group | Days | min | max |
| --- | --- | --- | --- |
| 0 | 5, 1, 9 | 1 | 9 |
| 1 | 2, 12, 7 | 2 | 12 |
| 2 | 3, 11, 6 | 3 | 11 |
| 3 | 8, 4, 10 | 4 | 10 |

For `WHERE day = 7`, a reader that sees only the min and max must read every group whose range [min, max] contains 7: **all 4**, although only group 1 holds a 7. Sort the days and store them again:

| Row group | Days | min | max |
| --- | --- | --- | --- |
| 0 | 1, 2, 3 | 1 | 3 |
| 1 | 4, 5, 6 | 4 | 6 |
| 2 | 7, 8, 9 | 7 | 9 |
| 3 | 10, 11, 12 | 10 | 12 |

Now 7 is in the range of **one** group, group 2, which is exactly the group that holds it. Same data, same summary, from reading everything to reading a quarter. A range works the same way: `day BETWEEN 10 AND 12` reads 3 groups of the loaded order and 1 of the sorted order.

## 5.4 Why it is true

### Runs = changes + 1, and sorting gives the fewest

**Claim 1.** A column of n ≥ 1 values with c places where a value differs from the one before has exactly c + 1 runs.

*Proof.* The first value starts a run. After that, a new run starts at position i exactly when value i differs from value i − 1, which happens c times. So there are 1 + c runs. ∎

**Claim 2.** A column with V distinct values has at least V runs, and a sorted column has exactly V.

*Proof.* Each run holds one value, so each of the V values needs at least one run: at least V runs. In a sorted column all copies of each value are next to each other, so each value forms one run: exactly V. ∎

So sorting is the best possible order for run-length coding, and it costs nothing in the bit-packed part (the codes are the same, only reordered). With several columns there is a catch: you can sort by only one of them first. Sorting by date then city gives the fewest runs for date, and for city within each date.

### Skipping never misses a row

**Claim 3.** If x < min or x > max of a row group, no row of that group has value x.

*Proof.* Every value v in the group satisfies min ≤ v ≤ max, by the definition of min and max. If x < min then x < v for every v, so x ≠ v; the same for x > max. ∎

So skipping is **safe**: it can only waste reads (a group whose range contains x but which does not hold x, like groups 0, 2 and 3 for `day = 7` above), never miss a row. How much it saves depends on how the values are spread over the groups. If the column is sorted, the groups' ranges barely overlap, and a value with k copies lies in at most ⌈k / g⌉ + 1 consecutive groups (g rows per group). If the rows are in random order, each group of thousands of rows almost surely contains values near the column's overall minimum and maximum, so every range is nearly the whole range and nothing is skipped (5.5 shows exactly this).

### The floor: entropy

Dictionary and bit-packing used 2 bits per city. Can any code do better? Shannon's source coding theorem says: for values drawn independently with probabilities p₁, p₂, ..., no code can average fewer than **H = −Σ pᵢ log₂ pᵢ** bits per value, and good codes come close. For the 12 cities (frequencies 5/12, 4/12, 3/12) H = 1.555 bits per value, about 18.7 bits for 12 values, against our 24. A general compressor (snappy, zstd) applied after the encoding claws back part of that gap. Runs do better than H because the values are **not** independent: in a sorted column, each value tells you the next is very likely the same. The entropy is explained in [Networks Math, ch 5. Information and capacity](https://networks.akadian.ca/books/math/05-Information-and-Capacity/); this tutorial only uses it as the floor.

## 5.5 See it in a real Parquet file

The script makes 1,000,000 orders for 2026 in date order (as they would arrive, about 2,740 a day), with 100,000 customers, 50 cities (a few big, a long tail), 4 statuses (85% "delivered") and amounts from 1 to 1,000. It writes them as CSV and as Parquet in 20 row groups of 50,000 rows.

### The sizes

| File | Bytes | Smaller than the CSV by |
| --- | --- | --- |
| CSV | 45,380,909 | |
| Parquet, encodings only (no compression) | 20,661,390 | 2.2 × |
| Parquet, snappy (pyarrow's default) | 13,825,131 | 3.3 × |
| Parquet, zstd | 9,315,408 | 4.9 × |
| Parquet, snappy, **rows shuffled** | 15,914,666 | 2.9 × |
| Parquet, zstd, `order_id` stored as differences | 6,431,065 | 7.1 × |

Shuffling the rows alone made the file 15% bigger: same values, worse runs.

### Predicting each column from 5.3

The file's footer reports, per column, the encodings and the bytes before and after compression. Each line can be predicted with the arithmetic of Step 2:

| Column | Distinct values | Prediction | Bytes before compression (real) |
| --- | --- | --- | --- |
| `status` | 4 | 2 bits × 1,000,000 = 250,000 | 244,891 |
| `city` | 50 | ⌈log₂ 50⌉ = 6 bits × 1,000,000 = 750,000 | 766,637 |
| `amount` | 1,000 | 10 bits × 1,000,000 = 1,250,000, plus a dictionary of 1,000 × 8 bytes in each of 20 groups = 160,000: 1,410,000 | 1,417,020 |
| `order_date` | 365, sorted | about 18 days per group, so about 18 runs per group | **6,607** for a million dates |
| `customer_id` | about 39,000 per group | per group: dictionary 39,341 × 8 bytes + 16-bit codes × 50,000 ≈ 415,000; × 20 ≈ 8.3 million | 8,252,808 |
| `order_id` | 50,000 per group, all different | per group: dictionary 50,000 × 8 + 16-bit codes × 50,000 = 500,000; × 20 = 10 million | 9,957,080 |

(The script counted 39,341 distinct customers in the first group: 50,000 draws from 100,000 values give about 100,000 × (1 − e^−0.5) ≈ 39,347 different ones.) The small differences are headers and the runs that `RLE_DICTIONARY` finds by chance. Two lessons:

- **A sorted, repetitive column costs almost nothing.** A million dates take 6.6 kB, about 1/20 of a bit per row.
- **A dictionary is wasted on a column where every value is different.** `order_id` was stored as a dictionary of all its own values plus a code for each, 10 MB, more than the 8 MB of plain 64-bit numbers. Stored instead as **differences** (`DELTA_BINARY_PACKED`: the ids go 1, 2, 3, ..., so every difference is 1 and takes 0 bits once the first is known), the whole column took **24,758 bytes** before compression and 6,258 after. That one setting is the difference between 9.3 MB and 6.4 MB above.

### Skipping, counted in bytes

The `order_date` statistics of the first four row groups, from the footer:

```text
date order:     (2026-01-01, 2026-01-19), (2026-01-19, 2026-02-06), (2026-02-06, 2026-02-24), (2026-02-24, 2026-03-14)
rows shuffled:  (2026-01-01, 2026-12-31), (2026-01-01, 2026-12-31), (2026-01-01, 2026-12-31), (2026-01-01, 2026-12-31)
```

Then `pq.read_table(file, filters=[("order_date", "=", date(2026, 7, 15))])`, with every byte the reader asked for counted:

| File | Row groups whose range contains the day | Rows found | Bytes read |
| --- | --- | --- | --- |
| date order | 1 of 20 | 2,680 | 755,667 of 13,825,131 (**5.5%**) |
| rows shuffled | 20 of 20 | 2,680 | 15,963,796 of 15,914,666 (**100.3%**) |

Exactly Step 5 at full size. (The shuffled read is a little over 100% because the footer is read more than once.) And reading one column, `SELECT sum(amount)`, read 1,403,043 bytes, **10.1%** of the file: the `amount` chunks and the footer.

## 5.6 Where it breaks

- **High-cardinality, unsorted columns.** Random ids, hashes, floating-point measurements: dictionary coding does not help (or, as with `order_id`, hurts), runs do not exist, and the bytes left are close to the entropy, which is high. Choose `DELTA_BINARY_PACKED` for counters and timestamps that only grow, and leave the rest to the compressor.
- **One sort order.** Rows can be sorted by one column first. A file sorted by date skips beautifully on date and not at all on customer. **Z-ordering** and **liquid clustering** ([Databricks ch 22.7](../../data-engineering/databricks/22-Performance-Tuning.md)) interleave several columns so that each skips reasonably well, none perfectly.
- **Ranges that hide gaps.** Min and max say nothing about the middle. A group with values 1 and 1,000,000 and nothing in between is read for every query in that range. **Bloom filters**, which Parquet can store per column chunk, answer "is this exact value here?" with no false negatives and a small rate of false positives.
- **Small files and small groups.** Each row group and file has a footer and headers; a dictionary is stored per chunk. A table spread over thousands of tiny files spends its time on metadata (the small-files problem of [Databricks ch 22.3](../../data-engineering/databricks/22-Performance-Tuning.md)).
- **Updates.** A column file is written once. Changing one row means rewriting its file (or, in Delta Lake, marking it deleted in a deletion vector and writing the new version elsewhere).
- **Functions on the column.** As with a B-tree index ([tutorial 2](02-Why-an-Index-Is-Fast.md)), statistics are on the stored values: a filter on `month(order_date)` cannot use the date's min and max unless the engine rewrites it into a date range.

## 5.7 Exercises

1 to 4 with a pencil. 5 and 6 are arithmetic. 7 is a proof. 8 is code.

**E1. Encode `A A B B B A C C C C` with a dictionary (A = 0, B = 1, C = 2). How many bits bit-packed? How many runs? How many runs after sorting?**

??? success "Answer"
    Codes 0 0 1 1 1 0 2 2 2 2; 3 values need 2 bits: 10 × 2 = **20 bits**. Changes: 0→1, 1→0, 0→2: 3 changes, so **4 runs**: (0,2) (1,3) (0,1) (2,4). Sorted: (0,3) (1,3) (2,4), **3 runs**, one per value.

**E2. A column has 300 distinct values. How many bits per code? With 1,000,000 rows, how many bytes bit-packed?**

??? success "Answer"
    2⁸ = 256 < 300 ≤ 512 = 2⁹, so **9 bits**. 9 × 1,000,000 = 9,000,000 bits = **1,125,000 bytes**, plus the dictionary.

**E3. A file sorted by date has 20 row groups of 50,000 rows, about 2,740 orders a day. A query asks for 7 consecutive days. About how many row groups does it read?**

??? success "Answer"
    7 × 2,740 ≈ 19,180 rows, less than one group of 50,000, so the week lies in **1 or 2** consecutive groups, depending on whether it crosses a group boundary. (A group covers about 18 days, so a 7-day window crosses a boundary in about 7/18 of cases.) In the shuffled file: all 20.

**E4. In the 12-day example, which groups must be read for `day BETWEEN 4 AND 6`, in the loaded order and in the sorted order?**

??? success "Answer"
    Loaded order, ranges [1,9], [2,12], [3,11], [4,10]: every range overlaps [4, 6], so **all 4** must be read (the 4, 5 and 6 really are in groups 3, 0 and 2). Sorted: only group 1, [4, 6]. A range overlaps [lo, hi] when min ≤ hi and max ≥ lo.

**E5. Predict the bytes before compression of a `country` column with 10 values, evenly spread, over 1,000,000 rows in 20 row groups, if each value is an 8-byte number. Then: if the file is sorted by country, roughly how many runs per row group?**

??? success "Answer"
    ⌈log₂ 10⌉ = 4 bits × 1,000,000 = 500,000 bytes for the codes, plus 20 dictionaries of 10 × 8 = 80 bytes: about **501,600 bytes**. Sorted by country, each country fills 100,000 rows, two whole row groups, so most groups hold **1 run** (a few hold 2 if a boundary falls inside them; here none does, since 100,000 is a multiple of 50,000).

**E6. The file in 5.5 had 2,680 orders on 2026-07-15 and 2,740 a day on average. Estimate, from the bytes per row of the sorted file, how many bytes those orders' own rows take. Why did the read take 755,667 bytes, about 15 times more?**

??? success "Answer"
    13,825,131 bytes / 1,000,000 rows ≈ 13.8 bytes a row; 2,680 rows ≈ 37,000 bytes. But the smallest unit a reader fetches is a column chunk (here, of a 50,000-row group), so it reads the whole group that holds the day: about 1/20 of the data, ≈ 690,000 bytes, plus the footer. Smaller row groups would read less per query and add more metadata; that is the trade-off behind the row-group size setting (Parquet's **page index**, which pyarrow can also write, narrows reads to pages inside a group).

**E7. Show that the number of runs of a column does not depend on which numbers the dictionary gives the values.**

??? success "Answer"
    A dictionary is a one-to-one map from values to codes. Two neighbouring values are equal exactly when their codes are equal, so the codes change at exactly the same places as the values. By Claim 1 the number of runs is that number of changes plus one: the same for every dictionary.

**E8. Write the encoder of Steps 2 and 3 in Python: a function that returns the dictionary, the codes, the bits per code and the runs of a list.**

??? success "Answer"
    ```python
    import math

    def encode(values):
        dictionary = sorted(set(values))
        codes = [dictionary.index(v) for v in values]
        bits = max(1, math.ceil(math.log2(len(dictionary))))
        runs = []
        for c in codes:
            if runs and runs[-1][0] == c:
                runs[-1][1] += 1
            else:
                runs.append([c, 1])
        return dictionary, codes, bits, runs
    ```

    The same code is in [ex01_by_hand.py](src/05/ex01_by_hand.py); its output for the 12 cities gives 24 bits and 5 runs, and 3 runs sorted.

## 5.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a table that shrank or grew when it was rewritten, and a filter that read far more or far less than expected.)*

## 5.9 Further reading

On your own sites:

- Entropy and the limits of compression: [Networks Math, ch 5. Information and capacity](https://networks.akadian.ca/books/math/05-Information-and-Capacity/)
- Data skipping, Z-order and liquid clustering in practice: [Databricks ch 22. Performance tuning](../../data-engineering/databricks/22-Performance-Tuning.md); the table format on top of Parquet: [ch 4. Delta Lake](../../data-engineering/databricks/04-Delta-Lake.md)

Original sources:

- [Apache Parquet file format documentation](https://parquet.apache.org/docs/file-format/), including the [encodings](https://parquet.apache.org/docs/file-format/data-pages/encodings/) (RLE/bit-packing hybrid, dictionary, delta).
- D. Abadi, S. Madden and M. Ferreira, "Integrating Compression and Execution in Column-Oriented Database Systems", *Proceedings of ACM SIGMOD*, 2006.
- S. Melnik and others, "Dremel: Interactive Analysis of Web-Scale Datasets", *Proceedings of the VLDB Endowment* 3(1), 2010. The nested column format Parquet was built on.
- C. E. Shannon, "A Mathematical Theory of Communication", *Bell System Technical Journal* 27, 1948. The source coding theorem.
- [Apache Arrow: reading and writing Parquet files with pyarrow](https://arrow.apache.org/docs/python/parquet.html).

## Glossary

- **Column file (columnar format)**: a file that stores each column's values together, such as Parquet or ORC.
- **Row group**: a block of rows (here 50,000) stored column by column; the unit a reader skips.
- **Column chunk**: one column's values inside one row group.
- **Dictionary coding**: store each distinct value once and replace values by small integer codes.
- **Bit-packing**: store each code in exactly ⌈log₂ V⌉ bits.
- **Run**: a maximal stretch of equal neighbouring values.
- **Run-length coding**: store (value, length) for each run.
- **Delta coding**: store the differences between neighbouring values; tiny for values that grow steadily.
- **Statistics (min/max)**: the smallest and largest value of each column chunk, kept in the file footer.
- **Data skipping**: not reading row groups or files whose statistics show they cannot match a filter.
- **Projection**: reading only the columns a query needs.
- **Entropy**: the average number of bits per value below which no code can go, for independent values with given frequencies.
- **Bloom filter**: a small structure that says "definitely not here" or "maybe here" for an exact value.
