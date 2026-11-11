# 22. Performance tuning

*"This job is slow, what do you check?" is one of the most common questions in a data engineer interview, and one of the easiest to answer badly: a list of tricks ("add a broadcast hint, cache it, repartition") sounds like guessing. This chapter gives you a method instead. First find where the time goes (scan, shuffle, skew, spill, small files, the driver), then apply the fix for that cause: file layout with `OPTIMIZE`, liquid clustering and data skipping; deletion vectors and predictive optimization for maintenance; Photon and caching for the engine; AQE, join strategies and salting for shuffles; and the specific levers for `MERGE`, streaming and SQL warehouses. Every layout effect below was measured on a real engine, with file counts before and after.*

!!! abstract "In this chapter"
    **You will learn:**

    - a step-by-step method for a slow job, using the Spark UI and the Databricks query profile
    - the small-files problem, `OPTIMIZE`, auto compaction, optimized writes and target file size
    - when partitioning helps and when it hurts (Databricks' size guidance)
    - data skipping with per-file min/max statistics, and which columns get statistics
    - Z-ordering vs liquid clustering (`CLUSTER BY`, `CLUSTER BY AUTO`, changing keys, `OPTIMIZE FULL`)
    - deletion vectors, predictive optimization, Photon, the disk cache vs the Spark cache
    - AQE on Databricks, broadcast joins and hints, skew joins and salting, spill and shuffle partitions
    - faster `MERGE`, streaming admission control and state, and SQL warehouse sizing

    **You need:** [3. Apache Spark for data engineers](03-Apache-Spark.md) (partitions, shuffles, join strategies, AQE basics, caching, UDFs, `collect()`) and [4. Delta Lake](04-Delta-Lake.md) (the transaction log, `OPTIMIZE`, deletion vectors). [9. Building silver](09-Building-Silver.md) helps for the `MERGE` section.

    **Levels:** sections 22.1 to 22.3 beginner, 22.4 to 22.12 intermediate, 22.13 to 22.17 expert.

All runnable examples ran on Apache Spark 4.2 with Delta Lake 4.4.1, on a laptop-sized local engine (`local[2]`). The data is tiny, so the numbers that matter here are file counts, rows per partition and plan shapes, not seconds. Tables have one-part names (`orders`) because there is no Unity Catalog locally; on Databricks you would write `shop.silver.orders`. The scripts and their full output are in `src/ch22/`. Everything marked *Databricks only* (Photon, predictive optimization, the disk cache, the query profile, `CLUSTER BY AUTO`, SQL warehouses) was checked against the official page linked next to it.

## 22.1 A method for a slow job
*Level: beginner.*

**The problem.** A nightly job that took 20 minutes now takes two hours. Changing settings at random wastes days and can make things worse. The Databricks optimization overview names the usual root causes: "reading more data than a query needs, shuffling data between nodes, choosing a poor query plan, or rewriting files that didn't change" ([Optimization recommendations on Databricks](https://docs.databricks.com/aws/en/optimizations/)). It also says where to start: "use the Spark UI to find the bottleneck before you change configuration".

**The tool: the Spark UI diagnosis order.** Databricks publishes a diagnosis guide for the Spark UI with five steps, in this order ([Diagnose cost and performance issues using the Spark UI](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/)):

1. Use the jobs timeline to identify major issues (failing jobs, gaps between jobs, many small jobs, or one long job).
2. Look at the longest stage.
3. Look for skew or spill.
4. Determine whether the longest stage is I/O bound.
5. Look for other causes of slow stage runtime.

Figure 22.1 turns those pages into one decision tree. Each check is something you read off a screen, and each leaf is a section of this chapter.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 460" role="img" aria-label="Decision tree for a slow job. From the jobs timeline: gaps between jobs point to the driver; a longest stage with one task means no parallelism; a maximum task time at least 1.5 times the 75th percentile means skew; spill means memory pressure; about 3 MB per second per core means the stage is I/O bound; otherwise look for small files, Python UDFs or an exploding join.">
<rect x="20" y="14" width="600" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="1.5"/>
<text x="320" y="40" font-size="14" font-weight="bold" text-anchor="middle" fill="currentColor">Slow job: open the jobs timeline, then the longest stage</text>
<line x1="155" y1="54" x2="155" y2="72" stroke="currentColor" stroke-width="1.4"/><polygon points="150,71 160,71 155,78" fill="currentColor"/>
<rect x="20" y="78" width="270" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="155" y="106" font-size="13" text-anchor="middle" fill="currentColor">Gaps between Spark jobs?</text>
<rect x="340" y="78" width="280" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="480" y="97" font-size="13" text-anchor="middle" fill="currentColor">Driver: Python loops, huge plans,</text>
<text x="480" y="115" font-size="13" text-anchor="middle" fill="currentColor">many concurrent jobs (22.15)</text>
<line x1="290" y1="101" x2="334" y2="101" stroke="currentColor" stroke-width="1.4"/><polygon points="333,96 333,106 340,101" fill="currentColor"/>
<text x="315" y="95" font-size="13" text-anchor="middle" fill="currentColor">yes</text>
<line x1="155" y1="124" x2="155" y2="136" stroke="currentColor" stroke-width="1.4"/><polygon points="150,135 160,135 155,142" fill="currentColor"/>
<text x="165" y="137" font-size="13" text-anchor="start" fill="currentColor">no</text>
<rect x="20" y="142" width="270" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="155" y="170" font-size="13" text-anchor="middle" fill="currentColor">Longest stage has one task?</text>
<rect x="340" y="142" width="280" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="480" y="161" font-size="13" text-anchor="middle" fill="currentColor">No parallelism: gzip, window with no</text>
<text x="480" y="179" font-size="13" text-anchor="middle" fill="currentColor">PARTITION BY, coalesce(1) (22.15)</text>
<line x1="290" y1="165" x2="334" y2="165" stroke="currentColor" stroke-width="1.4"/><polygon points="333,160 333,170 340,165" fill="currentColor"/>
<text x="315" y="159" font-size="13" text-anchor="middle" fill="currentColor">yes</text>
<line x1="155" y1="188" x2="155" y2="200" stroke="currentColor" stroke-width="1.4"/><polygon points="150,199 160,199 155,206" fill="currentColor"/>
<text x="165" y="201" font-size="13" text-anchor="start" fill="currentColor">no</text>
<rect x="20" y="206" width="270" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="155" y="234" font-size="13" text-anchor="middle" fill="currentColor">Max task time ≥ 1.5 × p75?</text>
<rect x="340" y="206" width="280" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="480" y="225" font-size="13" text-anchor="middle" fill="currentColor">Skew: AQE skew join first,</text>
<text x="480" y="243" font-size="13" text-anchor="middle" fill="currentColor">then salting (22.14)</text>
<line x1="290" y1="229" x2="334" y2="229" stroke="currentColor" stroke-width="1.4"/><polygon points="333,224 333,234 340,229" fill="currentColor"/>
<text x="315" y="223" font-size="13" text-anchor="middle" fill="currentColor">yes</text>
<line x1="155" y1="252" x2="155" y2="264" stroke="currentColor" stroke-width="1.4"/><polygon points="150,263 160,263 155,270" fill="currentColor"/>
<text x="165" y="265" font-size="13" text-anchor="start" fill="currentColor">no</text>
<rect x="20" y="270" width="270" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="155" y="298" font-size="13" text-anchor="middle" fill="currentColor">Spill in the stage details?</text>
<rect x="340" y="270" width="280" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="480" y="289" font-size="13" text-anchor="middle" fill="currentColor">Memory: shuffle partitions = auto,</text>
<text x="480" y="307" font-size="13" text-anchor="middle" fill="currentColor">fewer columns, more memory (22.15)</text>
<line x1="290" y1="293" x2="334" y2="293" stroke="currentColor" stroke-width="1.4"/><polygon points="333,288 333,298 340,293" fill="currentColor"/>
<text x="315" y="287" font-size="13" text-anchor="middle" fill="currentColor">yes</text>
<line x1="155" y1="316" x2="155" y2="328" stroke="currentColor" stroke-width="1.4"/><polygon points="150,327 160,327 155,334" fill="currentColor"/>
<text x="165" y="329" font-size="13" text-anchor="start" fill="currentColor">no</text>
<rect x="20" y="334" width="270" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="155" y="362" font-size="13" text-anchor="middle" fill="currentColor">About 3 MB/s per core?</text>
<rect x="340" y="334" width="280" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="480" y="353" font-size="13" text-anchor="middle" fill="currentColor">I/O bound: read less (22.5 to 22.7),</text>
<text x="480" y="371" font-size="13" text-anchor="middle" fill="currentColor">shuffle less (22.13)</text>
<line x1="290" y1="357" x2="334" y2="357" stroke="currentColor" stroke-width="1.4"/><polygon points="333,352 333,362 340,357" fill="currentColor"/>
<text x="315" y="351" font-size="13" text-anchor="middle" fill="currentColor">yes</text>
<line x1="155" y1="380" x2="155" y2="392" stroke="currentColor" stroke-width="1.4"/><polygon points="150,391 160,391 155,398" fill="currentColor"/>
<text x="165" y="393" font-size="13" text-anchor="start" fill="currentColor">no</text>
<rect x="20" y="398" width="270" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="155" y="426" font-size="13" text-anchor="middle" fill="currentColor">Otherwise: little I/O, still slow</text>
<rect x="340" y="398" width="280" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="480" y="417" font-size="13" text-anchor="middle" fill="currentColor">Small files (22.3), Python UDFs,</text>
<text x="480" y="435" font-size="13" text-anchor="middle" fill="currentColor">exploding or Cartesian join</text>
<line x1="290" y1="421" x2="334" y2="421" stroke="currentColor" stroke-width="1.4"/><polygon points="333,416 333,426 340,421" fill="currentColor"/>
<text x="315" y="415" font-size="13" text-anchor="middle" fill="currentColor"></text>
</svg>
<figcaption>Figure 22.1. The Databricks Spark UI diagnosis order as one decision tree. Answer each check from the Spark UI (or the query profile); the first yes names the cause and the section of this chapter that fixes it.</figcaption>
</figure>

What each check means, with the thresholds the guide gives:

- **Gaps between jobs.** A gap is a period when no Spark job runs, but you still pay for the cluster. Common causes are "no work" (an idle all-purpose cluster), a complex execution plan ("calling `withColumn()` in a loop creates a very expensive plan"), non-Spark code such as a Python loop running on the driver, or an overloaded driver ([Gaps between Spark jobs](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/spark-job-gaps)). The driver page adds the most common cause of an overloaded driver: "Too many concurrent operations", for example threads running many Spark jobs at once ([Spark driver overloaded](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/spark-driver-overloaded)).
- **One task.** "A long-running stage with only one task has no parallelism ... Adding workers doesn't help." The listed causes: an expensive UDF on small data, a window function without `PARTITION BY`, an unsplittable file such as gzip, the `multiLine` option on JSON or CSV, schema inference on a large file, and `repartition(1)` or `coalesce(1)` ([Long Spark stage with one task](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/one-spark-task)).
- **Skew.** On the stage page, open **Summary Metrics** and compare the **Max** task duration with the 75th percentile. "If the Max duration exceeds the 75th percentile by 50% or more, the stage might have skew" ([Skew and spill](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/long-spark-stage-page)).
- **Spill.** "Spill happens when Spark runs low on execution memory, which Spark uses for shuffles, joins, sorts, and aggregations. Spark then writes data from memory to disk." If the stage details show no spill statistics, there was no spill (same page).
- **High I/O.** The guide's rule of thumb: "Each CPU core can read and write about 3 MB per second." Take the largest of the stage's Input, Output, Shuffle Read and Shuffle Write, divide by the total worker cores, then by the stage duration in seconds; a result around 3 MB per second means the stage might be I/O bound ([Spark stage high I/O](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/long-spark-stage-io)). Then the fix depends on which column is large: input (read less), output (rewrite less), or shuffle.
- **Slow with little I/O.** Reading or writing many small files ("Files should be at least 8 MB"), slow UDFs, a Cartesian join, or an exploding join or `explode()` ([Slow Spark stage with little I/O](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/slow-spark-stage-low-io)).

Section 3.14 of [chapter 3](03-Apache-Spark.md) tours the Spark UI tabs themselves; this chapter is about what to do with what you see there.

!!! tip "In the interview"
    **"A job got slow. Walk me through how you would investigate."** Do not guess; measure. Open the jobs timeline: gaps mean the driver (non-Spark code, huge plans), one long job means find its longest stage. In that stage: one task means no parallelism; Max far above the 75th percentile means skew; spill means memory; large input or shuffle means I/O, so read less (data skipping, clustering) or shuffle less (broadcast); little I/O means small files, UDFs or an exploding join. Then fix that one cause and measure again.

## 22.2 The query profile and performance insights
*Level: beginner.*

On SQL warehouses and serverless compute you usually do not open the Spark UI; you open the **query profile**. It shows each operator of the executed plan with metrics such as "the time spent, number of rows processed, rows processed, and memory consumption", so you can "identify the slowest part of a query execution at a glance" and spot "exploding joins or full table scans" ([Query profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile)). Facts from that page worth knowing:

- **Access.** You must own the query or have at least CAN MONITOR on the SQL warehouse that ran it. It opens from **Query History**, the SQL editor, a notebook attached to a SQL warehouse or serverless compute ("See performance"), the pipelines UI and the jobs UI.
- **What to read first.** **Top operators** lists the longest-running operators. The summary shows wall-clock duration broken into scheduling, optimization and file pruning, and execution; **Aggregated task time** (all cores together, which can be far longer than wall-clock time); and the I/O read and written. Filter icons next to metrics show the percent of data pruned during scanning.
- **The DAG** can show **Time spent**, **Memory peak** or **Rows** per operator. Some metrics are hidden by default; **Enable verbose mode** shows them.
- **No profile from the cache.** "A query profile is not available for queries that run from the query cache." Change the query slightly (for example the `LIMIT`) to force a real run.

The profile also lists **performance insights**: findings ranked "by their estimated effect on total task duration", each with a recommendation ([Query performance insights](https://docs.databricks.com/aws/en/sql/user/queries/performance-insights)). The names map almost one-to-one to the causes in this chapter:

| Insight | What it reports | Section |
| --- | --- | --- |
| `DATA_FILE_SIZE` | The scan reads many small files | 22.3, 22.4 |
| `COVERAGE_STATS_DELTA` | Data skipping statistics are missing or unusable for the filters ("Unused: Statistics can't be used because the filter converts the data type") | 22.6 |
| `COVERAGE_FILTER_KEYS_CLUSTERING` / `..._PARTITIONING` | The table's clustering or partition keys are not used in the filters | 22.5, 22.7 |
| `MANUAL_DATA_LAYOUT` | A manually optimized table that could use automatic liquid clustering | 22.7 |
| `COVERAGE_PHOTON` | An operation Photon cannot run, so it fell back to the standard engine | 22.10 |
| `COVERAGE_STATS_OPTIMIZER` | Cost-based optimizer statistics are missing | 22.13 |
| `DATA_SKEW` | "Data is distributed unevenly"; recommends "key salting or pre-aggregation" | 22.14 |
| `DATA_SPILL` | Data spilled to disk; recommends a larger warehouse or less data per row | 22.15 |
| `EXPLODING_JOIN` / `SELECTIVE_JOIN` | A join outputs far more rows / far fewer rows than it reads | 22.1, 22.13 |
| `WIDE_PROJECTION` | The query reads every column | 22.6 |
| `EXCESSIVE_QUEUE_TIME` | The query waited in the warehouse queue | 22.12 |
| `CONCURRENT_WRITE` | Concurrent writes to the table conflict | 22.8 |

The same page lists "applied accelerations" that need no action, such as `HISTORY_BASED_JOIN_STRATEGY` (a broadcast join chosen from measurements of earlier similar queries) and `AUTO_LIQUID_CLUSTERING`.

!!! tip "In the interview"
    **"Spark UI or query profile?"** Both show the executed plan with metrics. The query profile is the Databricks view for SQL warehouses and serverless compute, organized by operator with top operators, pruning percentages and performance insights; the Spark UI is the Apache Spark view on classic clusters, organized by jobs, stages and tasks. The diagnosis is the same: find the most expensive operator or stage, then ask whether it is reading, shuffling, skewed or spilling.

## 22.3 The small-files problem, made visible
*Level: beginner.*

**The problem.** Every write task writes at least one file. A job that appends a few rows every few minutes, a streaming query with frequent micro-batches, or a table partitioned on a column with many values all produce thousands of tiny files. Each file costs a storage request, a footer to read, a task slot to schedule and statistics to keep in the log, so a query over many tiny files spends its time opening files, not reading data.

Here is the problem on a real table: Red Rock Supply's `orders`, loaded by 40 small appends of 25 rows each, then compacted with `OPTIMIZE`. The query in the middle filters on `status`, which every file contains, so it cannot skip files; its scan metric "number of files read" shows how many files it opened.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
for i in range(40):                      # 40 small appends, like a job that runs every few minutes
    sql("INSERT INTO orders " + ORDERS_SELECT.format(lo=i * 25, hi=(i + 1) * 25))

spark.sql("DESCRIBE DETAIL orders").selectExpr(
    "numFiles", "sizeInBytes", "round(sizeInBytes / numFiles) AS avg_file_bytes").show()
files_read("SELECT * FROM orders WHERE status = 'CANCELLED'")   # scan metric: number of files read

spark.sql("OPTIMIZE orders")
# ... the same DESCRIBE DETAIL, DESCRIBE HISTORY and files_read again
```

```text
+--------+-----------+--------------+
|numFiles|sizeInBytes|avg_file_bytes|
+--------+-----------+--------------+
|80      |163728     |2047.0        |
+--------+-----------+--------------+
files read by SELECT * FROM orders WHERE status = 'CANCELLED': [80]

>>> OPTIMIZE orders            (metrics start with numFilesAdded, numFilesRemoved)
|.../warehouse/orders|{1, 80, {18716, 18716, 18716.0, 1, 18716}, {2030, 2059, 2046.6, 80, 163728}, ...}|

+--------+-----------+--------------+
|numFiles|sizeInBytes|avg_file_bytes|
+--------+-----------+--------------+
|1       |18716      |18716.0       |
+--------+-----------+--------------+
+-------+---------+---------------+-------------+
|version|operation|numRemovedFiles|numAddedFiles|
+-------+---------+---------------+-------------+
|41     |OPTIMIZE |80             |1            |
+-------+---------+---------------+-------------+
files read by SELECT * FROM orders WHERE status = 'CANCELLED': [1]
rows still the same: 1000
```

Read it line by line:

- **80 files, not 40.** Each `INSERT` ran as two tasks on this two-core engine, and each task wrote its own file. On a cluster with hundreds of cores, one small write can create hundreds of files.
- **163,728 bytes became 18,716.** The same 1,000 rows take a ninth of the space in one file, because every Parquet file carries its own footer, schema and column metadata. With tiny files, that overhead is most of the file. (The exact byte counts move by a few bytes between runs because the generated rows differ slightly; a rerun gave 18,703.)
- **80 files read became 1.** Same rows, same answer, one file to open.
- **`OPTIMIZE` changed no data.** It is version 41 in the history, with 80 files removed and 1 added. The 80 old files are still on storage for time travel until `VACUUM` deletes them (chapter 4, section 4.8).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 304" role="img" aria-label="Before OPTIMIZE: 80 tiny files of about 2 KB, 163,728 bytes in all, and a filter reads 80 files. After OPTIMIZE, version 41: one file of 18,716 bytes holding the same 1,000 rows, and the filter reads 1 file. The old files remain until VACUUM.">
<text x="24" y="30" font-size="14" font-weight="bold" text-anchor="start" fill="currentColor">Before: 40 small appends</text>
<rect x="24" y="44" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="46" y="44" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="68" y="44" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="90" y="44" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="112" y="44" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="134" y="44" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="156" y="44" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="178" y="44" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="44" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="222" y="44" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="24" y="60" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="46" y="60" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="68" y="60" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="90" y="60" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="112" y="60" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="134" y="60" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="156" y="60" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="178" y="60" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="60" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="222" y="60" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="24" y="76" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="46" y="76" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="68" y="76" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="90" y="76" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="112" y="76" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="134" y="76" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="156" y="76" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="178" y="76" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="76" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="222" y="76" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="24" y="92" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="46" y="92" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="68" y="92" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="90" y="92" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="112" y="92" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="134" y="92" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="156" y="92" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="178" y="92" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="92" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="222" y="92" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="24" y="108" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="46" y="108" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="68" y="108" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="90" y="108" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="112" y="108" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="134" y="108" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="156" y="108" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="178" y="108" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="108" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="222" y="108" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="24" y="124" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="46" y="124" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="68" y="124" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="90" y="124" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="112" y="124" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="134" y="124" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="156" y="124" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="178" y="124" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="124" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="222" y="124" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="24" y="140" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="46" y="140" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="68" y="140" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="90" y="140" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="112" y="140" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="134" y="140" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="156" y="140" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="178" y="140" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="140" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="222" y="140" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="24" y="156" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="46" y="156" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="68" y="156" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="90" y="156" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="112" y="156" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="134" y="156" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="156" y="156" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="178" y="156" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="156" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="222" y="156" width="18" height="12" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<text x="24" y="196" font-size="13" text-anchor="start" fill="currentColor">80 files, 163,728 bytes in all</text>
<text x="24" y="214" font-size="13" text-anchor="start" fill="currentColor">(2,047 bytes per file on average)</text>
<text x="24" y="240" font-size="13" text-anchor="start" fill="currentColor">WHERE status = &#x27;CANCELLED&#x27;</text>
<text x="24" y="258" font-size="13" text-anchor="start" fill="currentColor">reads 80 files</text>
<line x1="262" y1="110" x2="376" y2="110" stroke="currentColor" stroke-width="1.4"/><polygon points="375,105 375,115 382,110" fill="currentColor"/>
<text x="322" y="100" font-size="14" font-weight="bold" text-anchor="middle" fill="currentColor">OPTIMIZE</text>
<text x="322" y="132" font-size="13" text-anchor="middle" fill="currentColor">version 41</text>
<text x="400" y="30" font-size="14" font-weight="bold" text-anchor="start" fill="currentColor">After: one compacted file</text>
<rect x="400" y="44" width="150" height="124" rx="4" fill="currentColor" fill-opacity="0.15" stroke="currentColor" stroke-width="1.5"/>
<text x="475" y="102" font-size="14" font-weight="bold" text-anchor="middle" fill="currentColor">1 file</text>
<text x="475" y="122" font-size="13" text-anchor="middle" fill="currentColor">18,716 bytes</text>
<text x="400" y="196" font-size="13" text-anchor="start" fill="currentColor">same 1,000 rows</text>
<text x="400" y="214" font-size="13" text-anchor="start" fill="currentColor">(Parquet overhead paid once)</text>
<text x="400" y="240" font-size="13" text-anchor="start" fill="currentColor">WHERE status = &#x27;CANCELLED&#x27;</text>
<text x="400" y="258" font-size="13" text-anchor="start" fill="currentColor">reads 1 file</text>
<text x="24" y="290" font-size="13" text-anchor="start" fill="currentColor">The 80 old files stay on storage for time travel until VACUUM deletes them.</text>
</svg>
<figcaption>Figure 22.2. The small-files run from section 22.3: forty appends wrote 80 tiny files; <code>OPTIMIZE</code> replaced them with one file. Same rows, one file to open, a ninth of the bytes.</figcaption>
</figure>

In PySpark, the same compaction is `DeltaTable.forName(spark, "orders").optimize().executeCompaction()`; Databricks shows this form on its `OPTIMIZE` page ([Optimize data file layout](https://docs.databricks.com/aws/en/tables/operations/optimize)). That page also says what `OPTIMIZE` guarantees: bin-packing is "idempotent, meaning that if it is run twice on the same dataset, the second run has no effect"; readers are not interrupted because of snapshot isolation; and "Performing `OPTIMIZE` on a table that is a streaming source does not affect any current or future streams".

**How often, and on what.** Databricks recommends predictive optimization for Unity Catalog managed tables so that `OPTIMIZE` "runs automatically when it is cost effective" (section 22.9). Without it, the recommendation is to "start by running `OPTIMIZE` on a daily basis, preferably at night when spot prices are low, and then adjust". `OPTIMIZE` is CPU intensive ("large amounts of Parquet decoding and encoding"), so Databricks recommends **compute optimized** instance types, and says `OPTIMIZE` also benefits from attached SSDs (same page).

!!! warning "OPTIMIZE has a cost, and it is not a cure for every slow query"
    `OPTIMIZE` rewrites data, so it uses compute and, until `VACUUM`, doubles the storage of what it rewrote. It fixes small files and, with clustering, layout. It does not fix a skewed join, a spill, a Python UDF or a missing broadcast. If a query is still slow after `OPTIMIZE`, go back to section 22.1 and measure.

## 22.4 File size on Databricks: auto compaction, optimized writes, target size
*Level: intermediate.*

Running `OPTIMIZE` after the fact is one fix. The other is to write fewer, larger files in the first place. Databricks has three settings for that, described on [Control data file size](https://docs.databricks.com/aws/en/tables/tune-file-size). The first lines of that page matter most: "Manual tuning recommendations don't apply to Unity Catalog managed tables, which use automatic file size tuning. For new tables, use Unity Catalog managed tables with default settings." The settings below are for external tables and legacy workloads.

- **Auto compaction** "combines small files within table partitions to reduce small file problems. It runs synchronously on the cluster that performs the write, after the write succeeds, and only compacts files that haven't been compacted previously." It is independent of predictive optimization: auto compaction runs on the writing cluster, predictive optimization runs later on serverless compute.
- **Optimized writes** "improve file size as data is written". They are "most effective for partitioned tables, as they reduce the number of small files written to each partition", at the cost of possibly higher write latency "because data is shuffled before being written". If you use them, Databricks recommends that you do not run `coalesce(n)` or `repartition(n)` just before a write.
- **Target file size**: the table property `delta.targetFileSize` (for example `100mb`), default none. With Unity Catalog managed tables and SQL warehouses or Databricks Runtime 11.3 LTS and above, "only `OPTIMIZE` commands respect the `targetFileSize` setting".

| Setting | Table property | Session setting | Values |
| --- | --- | --- | --- |
| Auto compaction | `delta.autoOptimize.autoCompact` | `spark.databricks.delta.autoCompact.enabled` | `auto` (recommended, tunes the target size), `legacy` / `true` (128 MB target, no dynamic sizing), `false` |
| Optimized writes | `delta.autoOptimize.optimizeWrite` | `spark.databricks.delta.optimizeWrite.enabled` | `true` (128 MB target), `false` |
| Target file size | `delta.targetFileSize` | (set on the table) | a size such as `104857600` or `100mb` |

Which operations already get them, by default, per the same page:

- "Auto compaction and optimized writes are always enabled for `MERGE`, `UPDATE`, and `DELETE` operations. You can't turn off this functionality."
- Optimized writes are also on for `CTAS` and `INSERT` on SQL warehouses, and, in Databricks Runtime 13.3 LTS and above, for `CTAS` and `INSERT` into partitioned tables registered in Unity Catalog.

*Databricks only, not run here. Syntax from [Control data file size](https://docs.databricks.com/aws/en/tables/tune-file-size).*

```sql
-- An external table written by a frequent small-batch job
ALTER TABLE shop.bronze.orders_raw SET TBLPROPERTIES (
  'delta.autoOptimize.autoCompact'   = 'auto',
  'delta.autoOptimize.optimizeWrite' = 'true'
);
```

**Autotuning by table size.** When you have not set a target, Databricks picks one from the table size: "For tables smaller than 2.56 TB, the autotuned target file size is 256 MB. For tables with a size between 2.56 TB and 10 TB, the target size grows linearly from 256 MB to 1 GB. For tables larger than 10 TB, the target file size is 1 GB." A separate setting caps `OPTIMIZE` output: `spark.databricks.delta.optimize.maxFileSize`, default `1073741824` (1 GB) ([OPTIMIZE](https://docs.databricks.com/aws/en/sql/language-manual/delta-optimize)). Auto compaction and optimized writes "are not a full replacement for `OPTIMIZE`"; for tables larger than 1 TB Databricks recommends running `OPTIMIZE` on a schedule anyway ([Control data file size](https://docs.databricks.com/aws/en/tables/tune-file-size)).

**How to tell auto compaction ran.** It appears in the table history as an `OPTIMIZE` with `operationParameters.auto` set to `true`; a manual `OPTIMIZE` has `false` (same page). Open-source Delta implements the same table property, so you can see that history entry here. The 40 small appends from section 22.3, repeated on a table with the property set:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE orders_ac (...same columns...) USING DELTA
TBLPROPERTIES ('delta.autoOptimize.autoCompact' = 'true');
-- 40 small INSERTs, then:
DESCRIBE HISTORY orders_ac;   -- OPTIMIZE rows only
```

```text
numFiles = 29 (instead of 80)
+-------+---------+----+---------------+-------------+
|version|operation|auto|numRemovedFiles|numAddedFiles|
+-------+---------+----+---------------+-------------+
|2      |OPTIMIZE |true|2              |1            |
|28     |OPTIMIZE |true|51             |1            |
+-------+---------+----+---------------+-------------+
```

Nobody ran `OPTIMIZE`, yet two compactions appear with `auto = true`: the writer ran them after its own commits. When and how much open-source Delta compacts is decided by its own thresholds, which this chapter does not compare with Databricks' `auto` mode; the point is how to recognize auto compaction in a table's history.

!!! tip "In the interview"
    **"What is the difference between auto compaction, optimized writes and OPTIMIZE?"** Optimized writes shuffle data before writing so each partition gets fewer, larger files; auto compaction compacts small files synchronously on the writing cluster right after a successful write; `OPTIMIZE` is a separate command (or a predictive optimization job) that rewrites existing files and, on clustered tables, reclusters them. On Unity Catalog managed tables Databricks tunes file sizes automatically, so you mostly leave these alone; on external tables you can set them with table properties.

## 22.5 Partitioning: when it helps and when it hurts
*Level: intermediate.*

A **partitioned table** stores each value of the partition column in its own folder (`status=PLACED/`, `status=CANCELLED/`), and a filter on that column reads only the matching folders. That is "partition pruning". In Hive and plain Parquet lakes, partitioning by date was the standard way to make tables fast. Databricks' guidance today is very different, and interviewers like to test whether you know it ([When to partition tables on Databricks](https://docs.databricks.com/aws/en/tables/partitions)):

> Most tables on Databricks with less than 100 TB of data don't need partitioning. Databricks uses Delta Lake for all tables by default and automatically clusters data in unpartitioned tables by ingestion time, so you get partitioning-like performance without manual tuning.

The page's minimum size recommendations:

- "With less than 1 TB of data, don't partition."
- "With more than 1 TB to 100 TB of data, use liquid clustering instead of partitioning. Partitioning likely negatively affects performance more often than it helps."
- "With 100 TB or more of data, partitioning might improve performance, but Databricks recommends using liquid clustering first and verifying performance improvements."
- "For partitions, verify that each partition contains at least 1 GB of data. Tables with fewer, larger partitions tend to outperform tables with many smaller partitions."

Why partitioning hurts when it is wrong:

- **It multiplies files.** Every write task writes one file per partition value it sees. A high-cardinality column gives many partitions with tiny files each.
- **`OPTIMIZE` cannot fix it.** "You cannot combine files across partition boundaries" ([When to partition tables on Databricks](https://docs.databricks.com/aws/en/tables/partitions)). The best `OPTIMIZE` can do is one file per partition.
- **It is fixed.** The warning on the same page: "An ineffective partitioning strategy might negatively affect query performance and require a full rewrite of data to fix."
- **It only works for some columns.** "Partitioning works well only for low or known cardinality fields (for example, date fields or physical locations), but not for fields with high cardinality such as timestamps."

The run below partitions 1,000 orders by `customer_id` (500 distinct values) to show the first two points:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
orders_1000.write.format("delta").partitionBy("customer_id").saveAsTable("orders_by_customer")
spark.sql("DESCRIBE DETAIL orders_by_customer").selectExpr("numFiles", "sizeInBytes").show()
spark.sql("OPTIMIZE orders_by_customer")
```

```text
+--------+-----------+--------------+
|numFiles|sizeInBytes|avg_file_bytes|
+--------+-----------+--------------+
|1000    |1790719    |1791.0        |
+--------+-----------+--------------+
files read by SELECT * (full scan): [1000]
>>> OPTIMIZE orders_by_customer   (metrics start with numFilesAdded, numFilesRemoved)
|.../warehouse/orders_by_customer|{500, 1000, ...}|
+--------+-----------+--------------+
|numFiles|sizeInBytes|avg_file_bytes|
+--------+-----------+--------------+
|500     |920442     |1841.0        |
+--------+-----------+--------------+
```

One thousand rows became 1,000 files: two write tasks times 500 partitions. `OPTIMIZE` merged each partition's two files into one and stopped at 500, one per partition, still about 1.8 KB each. Compare section 22.3, where the same kind of rows in an unpartitioned table compacted into a single file.

Other rules from the partitions page: partition columns must be top-level columns of a supported type (not struct, map, array or variant, and not a struct field); with Delta, "Transactions are not defined by partition boundaries", so you do not partition for atomicity; and "You cannot Z-order on fields used for partitioning". To move an existing partitioned table to liquid clustering, Databricks Runtime 18.1 and above has `ALTER TABLE ... REPLACE PARTITIONED BY WITH CLUSTER BY` (section 22.7).

!!! tip "In the interview"
    **"Would you partition this 500 GB orders table by order date?"** No. Databricks' guidance is not to partition tables under 1 TB, and to prefer liquid clustering up to 100 TB; partitions should each hold at least 1 GB. Unpartitioned Delta tables already get ingestion-time clustering, so date filters skip files through statistics. If queries filter on date and customer, I would use liquid clustering on those columns, or `CLUSTER BY AUTO` on a Unity Catalog managed table.

## 22.6 Data skipping: per-file min/max statistics
*Level: intermediate.*

**The problem.** A filter like `WHERE customer_id = 42` on an unpartitioned table seems to need a full scan. It does not, if the engine knows which files cannot contain 42.

**The tool: file statistics.** When Delta writes a data file, it records statistics for it in the transaction log: "minimum and maximum values, null counts, and total records". At query time Databricks uses them "to skip irrelevant files" ([Data skipping](https://docs.databricks.com/aws/en/tables/data-skipping)). Here are the real statistics of one file, read from the `add` action in `_delta_log/00000000000000000001.json`. The table `orders` was loaded as eight daily batches, one file per day, with customers spread across every day:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
first_add = [json.loads(line)["add"] for line in open(log_dir + "/00000000000000000001.json")
             if '"add"' in line][0]
print(json.dumps(json.loads(first_add["stats"]), indent=1))
```

```text
{
 "numRecords": 5000,
 "minValues": {
  "order_id": 0,
  "customer_id": 1,
  "order_ts": "2026-03-01T08:00:00.000Z",
  "status": "CANCELLED",
  "amount": 9.9,
  "currency": "CAD"
 },
 "maxValues": {
  "order_id": 4999,
  "customer_id": 500,
  "order_ts": "2026-03-01T09:23:19.000Z",
  "status": "PLACED",
  "amount": 105.9,
  "currency": "CAD"
 },
 "nullCount": {
  "order_id": 0, "customer_id": 0, "order_ts": 0, "status": 0, "amount": 0, "currency": 0
 }
}
```

(The `nullCount` block is printed on one line here to save space.) Now two queries against the eight files:

```text
orders: 8 files, min/max of customer_id per file:
   customer_id 1 .. 500   (5000 rows)      <- the same for all 8 files
files read, filter on order_ts (last day): [1]
files read, filter on customer_id = 42   : [8]
```

The date filter read one file: each file holds one day, so seven files have a `maxValues.order_ts` before March 8 and are skipped without being opened. This is what Databricks means by **ingestion time clustering**: data arrives in time order, so time filters skip well without any tuning ([When to partition tables on Databricks](https://docs.databricks.com/aws/en/tables/partitions)). The customer filter read all eight, because every file's range `1 .. 500` contains 42. Statistics only help when the values you filter on are **clustered**: close values in the same files. Section 22.7 fixes that.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 400" role="img" aria-label="Two panels of eight files drawn as bars over customer_id 1 to 500. Before Z-ordering every file spans 1 to 500, so a filter on customer_id 42 reads all 8 files. After OPTIMIZE ZORDER BY customer_id each file covers a narrow range, and only file 1, covering 1 to 67, is read.">
<text x="20" y="26" font-size="14" font-weight="bold" text-anchor="start" fill="currentColor">Before: 8 daily loads; every file spans customer_id 1 to 500</text>
<text x="24" y="48" font-size="13" text-anchor="start" fill="currentColor">file 1</text>
<rect x="120" y="38" width="480" height="10" rx="1" fill="currentColor" fill-opacity="0.3" stroke="currentColor" stroke-width="1"/>
<text x="24" y="62" font-size="13" text-anchor="start" fill="currentColor">file 2</text>
<rect x="120" y="52" width="480" height="10" rx="1" fill="currentColor" fill-opacity="0.3" stroke="currentColor" stroke-width="1"/>
<text x="24" y="76" font-size="13" text-anchor="start" fill="currentColor">file 3</text>
<rect x="120" y="66" width="480" height="10" rx="1" fill="currentColor" fill-opacity="0.3" stroke="currentColor" stroke-width="1"/>
<text x="24" y="90" font-size="13" text-anchor="start" fill="currentColor">file 4</text>
<rect x="120" y="80" width="480" height="10" rx="1" fill="currentColor" fill-opacity="0.3" stroke="currentColor" stroke-width="1"/>
<text x="24" y="104" font-size="13" text-anchor="start" fill="currentColor">file 5</text>
<rect x="120" y="94" width="480" height="10" rx="1" fill="currentColor" fill-opacity="0.3" stroke="currentColor" stroke-width="1"/>
<text x="24" y="118" font-size="13" text-anchor="start" fill="currentColor">file 6</text>
<rect x="120" y="108" width="480" height="10" rx="1" fill="currentColor" fill-opacity="0.3" stroke="currentColor" stroke-width="1"/>
<text x="24" y="132" font-size="13" text-anchor="start" fill="currentColor">file 7</text>
<rect x="120" y="122" width="480" height="10" rx="1" fill="currentColor" fill-opacity="0.3" stroke="currentColor" stroke-width="1"/>
<text x="24" y="146" font-size="13" text-anchor="start" fill="currentColor">file 8</text>
<rect x="120" y="136" width="480" height="10" rx="1" fill="currentColor" fill-opacity="0.3" stroke="currentColor" stroke-width="1"/>
<text x="20" y="170" font-size="13" text-anchor="start" fill="currentColor">Filter customer_id = 42: 42 is inside every range, so all 8 files are read.</text>
<text x="20" y="212" font-size="14" font-weight="bold" text-anchor="start" fill="currentColor">After OPTIMIZE ZORDER BY (customer_id): narrow ranges per file</text>
<text x="24" y="234" font-size="13" text-anchor="start" fill="currentColor">file 1</text>
<rect x="120.0" y="224" width="63.5" height="10" rx="1" fill="currentColor" fill-opacity="0.3" stroke="currentColor" stroke-width="1"/>
<text x="24" y="248" font-size="13" text-anchor="start" fill="currentColor">file 2</text>
<rect x="183.5" y="238" width="53.9" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<text x="24" y="262" font-size="13" text-anchor="start" fill="currentColor">file 3</text>
<rect x="237.4" y="252" width="61.5" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<text x="24" y="276" font-size="13" text-anchor="start" fill="currentColor">file 4</text>
<rect x="298.9" y="266" width="55.8" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<text x="24" y="290" font-size="13" text-anchor="start" fill="currentColor">file 5</text>
<rect x="354.7" y="280" width="57.7" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<text x="24" y="304" font-size="13" text-anchor="start" fill="currentColor">file 6</text>
<rect x="412.4" y="294" width="62.5" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<text x="24" y="318" font-size="13" text-anchor="start" fill="currentColor">file 7</text>
<rect x="474.9" y="308" width="67.4" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<text x="24" y="332" font-size="13" text-anchor="start" fill="currentColor">file 8</text>
<rect x="542.3" y="322" width="57.7" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<text x="20" y="356" font-size="13" text-anchor="start" fill="currentColor">Filter customer_id = 42: only file 1 (1 to 67) can match; 7 files skipped.</text>
<line x1="159.4" y1="34" x2="159.4" y2="154" stroke="currentColor" stroke-width="1.4" stroke-dasharray="4 3"/>
<line x1="159.4" y1="220" x2="159.4" y2="340" stroke="currentColor" stroke-width="1.4" stroke-dasharray="4 3"/>
<line x1="120" y1="372" x2="600" y2="372" stroke="currentColor" stroke-width="1"/>
<text x="120" y="390" font-size="13" text-anchor="middle" fill="currentColor">1</text>
<text x="159.4" y="390" font-size="13" text-anchor="middle" fill="currentColor">42</text>
<text x="600" y="390" font-size="13" text-anchor="middle" fill="currentColor">500</text>
<text x="380" y="390" font-size="13" text-anchor="middle" fill="currentColor">customer_id (min to max per file, from _delta_log stats)</text>
</svg>
<figcaption>Figure 22.3. Data skipping uses each file's min and max from the <code>_delta_log</code> statistics. Shaded bars are files the filter must read; the dashed line is <code>customer_id = 42</code>. Ranges are from the section 22.6 and 22.7 runs.</figcaption>
</figure>

**Which columns get statistics.** Statistics cost write time and log space, so Delta does not collect them on every column. For Unity Catalog external tables, "statistics are collected on the first 32 columns defined in your table schema by default"; for managed tables, predictive optimization also collects them on further columns that are frequently used in filters ([Data skipping](https://docs.databricks.com/aws/en/tables/data-skipping)). Two table properties change the default:

| Property | Databricks Runtime | Effect |
| --- | --- | --- |
| `delta.dataSkippingNumIndexedCols` | All supported versions | Number of leading columns with statistics. "Depends on column order." |
| `delta.dataSkippingStatsColumns` | 13.3 LTS and above | Explicit list of columns. "Supersedes `dataSkippingNumIndexedCols`." |

Both exist in open-source Delta too. One small insert into a table with each property:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE orders_2cols (...) USING DELTA
TBLPROPERTIES ('delta.dataSkippingNumIndexedCols' = '2');
CREATE TABLE orders_named (...) USING DELTA
TBLPROPERTIES ('delta.dataSkippingStatsColumns' = 'customer_id,order_ts');
```

```text
dataSkippingNumIndexedCols = 2: {"numRecords":50,"minValues":{"order_id":0,"customer_id":1},"maxValues":{"order_id":49,"customer_id":490},"nullCount":{"order_id":0,"customer_id":0}}
dataSkippingStatsColumns = customer_id,order_ts: {"numRecords":50,"minValues":{"customer_id":1,"order_ts":"2026-03-01T08:00:00.000Z"},"maxValues":{"customer_id":490,"order_ts":"2026-03-01T08:00:49.000Z"},"nullCount":{"customer_id":0,"order_ts":0}}
```

With the first property, only the first two columns in the schema got statistics, so a filter on `order_ts` could no longer skip anything. With the second, exactly the listed columns got them. Three rules from the Data skipping page:

- Changing these properties "doesn't automatically recompute statistics for existing data". In Databricks Runtime 14.3 LTS and above, recompute with `ANALYZE TABLE table_name COMPUTE DELTA STATISTICS`.
- "Long strings are truncated during statistics collection", so you may exclude long string columns that are rarely filtered.
- Clustering keys and `ZORDER BY` columns must have statistics; Z-ordering a column without them "is ineffective and uses unnecessary compute resources".

!!! warning "A filter that wraps the column can lose skipping"
    Statistics are min/max of the stored column. The `COVERAGE_STATS_DELTA` insight has a status "Unused: Statistics can't be used because the filter converts the data type" ([Query performance insights](https://docs.databricks.com/aws/en/sql/user/queries/performance-insights)). Prefer a range on the raw column (`order_ts >= '2026-03-08' AND order_ts < '2026-03-09'`) over a converted one when you depend on skipping, and check the files-pruned figure in the query profile.

## 22.7 Z-ordering and liquid clustering
*Level: intermediate.*

To make `customer_id = 42` skip files, the rows of each customer must sit together. There are two ways to arrange that: the older `OPTIMIZE ... ZORDER BY`, and **liquid clustering**. Databricks is clear about which to use: "Databricks recommends using liquid clustering instead of partitions, `ZORDER`, or other data layout approaches" ([Optimize data file layout](https://docs.databricks.com/aws/en/tables/operations/optimize)), and liquid clustering "replaces table partitioning and `ZORDER`" ([Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering)).

### Z-ordering

**Z-ordering** rewrites files so that rows close on the chosen columns land in the same files; data skipping then uses the narrower min/max ranges ([Data skipping](https://docs.databricks.com/aws/en/tables/data-skipping)). Use it on a column "commonly used in query predicates" with "high cardinality"; you can list several columns, but "the effectiveness drops with each extra column". The same eight-file table, after `OPTIMIZE orders ZORDER BY (customer_id)`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
spark.sql("OPTIMIZE orders ZORDER BY (customer_id)")
# PySpark: DeltaTable.forName(spark, "orders").optimize().executeZOrderBy("customer_id")
```

```text
orders: 8 files, min/max of customer_id per file:
   customer_id 1 .. 67   (5287 rows)
   customer_id 67 .. 123   (4552 rows)
   customer_id 123 .. 187   (5048 rows)
   customer_id 187 .. 245   (4661 rows)
   customer_id 245 .. 305   (4818 rows)
   customer_id 305 .. 370   (5212 rows)
   customer_id 370 .. 440   (5544 rows)
   customer_id 440 .. 500   (4878 rows)
files read, filter on customer_id = 42   : [1]
files read, filter on order_ts (last day): [8]
```

The customer filter now reads one file instead of eight. But look at the last line: the date filter, which read one file before, now reads all eight. Z-ordering on `customer_id` scattered each day's orders across every file. A layout favors the columns it is built on, which is why the choice of keys matters. (To get eight output files from this small table, the script lowered `spark.databricks.delta.optimize.maxFileSize` to 60,000 bytes; the default is 1 GB.) The exact row counts per file (and, further down, the boundary timestamps of the time-ordered files) move a little between runs; two reruns gave, for example, 5,307 and 5,305 rows for the first file. The key ranges and the files-read results stayed the same.

Z-order facts from the docs: it is "not idempotent but aims to be an incremental operation" ([Data skipping](https://docs.databricks.com/aws/en/tables/data-skipping)); it works inside partitions only; you cannot Z-order a partition column; predictive optimization "does not run `ZORDER`" and "ignores Z-ordered files" ([Predictive optimization for Unity Catalog managed tables](https://docs.databricks.com/aws/en/optimizations/predictive-optimization)); and every new write lands outside the Z-order until the next `OPTIMIZE ZORDER BY`.

### Liquid clustering

**Liquid clustering** makes the layout a property of the table: you declare clustering keys with `CLUSTER BY`, and `OPTIMIZE` (or predictive optimization) keeps the data clustered on them, incrementally. "Unlike traditional partitioning, you can redefine clustering keys without rewriting existing data" ([Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering)). Availability, as the page states it: "Liquid clustering is generally available for Delta Lake tables with Databricks Runtime 15.4 LTS and above, and for managed Apache Iceberg tables in Databricks Runtime 16.4 LTS and above." It also applies to streaming tables and materialized views.

The same eight daily loads into a clustered table:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE orders_lc (order_id INT, customer_id INT, order_ts TIMESTAMP,
                        status STRING, amount DECIMAL(10,2), currency STRING)
USING DELTA CLUSTER BY (customer_id);
-- eight daily appends, then:
OPTIMIZE orders_lc;
```

In PySpark, the `DeltaTable` builder takes `clusterBy` (run here in `ch22_extras.py`; `DESCRIBE DETAIL` then showed `clusteringColumns` `['customer_id']`):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from delta.tables import DeltaTable
(DeltaTable.create(spark).tableName("orders_lc")
    .addColumns(spark.table("orders").schema)
    .clusterBy("customer_id")
    .execute())
```

The Databricks page also shows creating a clustered table straight from a DataFrame. Open-source Delta 4.4.1 refused this form here with `DELTA_OPERATION_NOT_ALLOWED` ("Partitioning by expressions is not supported for Delta tables"), so treat it as Databricks syntax:

*Databricks only, not run here. Syntax from [Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering).*

```python
df.write.clusterBy("customer_id").saveAsTable("orders_lc")
# DataFrameWriterV2 (Databricks Runtime 14.2 and above):
df.writeTo("orders_lc").using("delta").clusterBy("customer_id").create()
```

```text
+--------+-----------------+
|numFiles|clusteringColumns|
+--------+-----------------+
|8       |[customer_id]    |
+--------+-----------------+
before OPTIMIZE, files read for customer_id = 42: [8]
orders_lc: 8 files, min/max of customer_id per file:
   customer_id 1 .. 59   (4668 rows)
   customer_id 59 .. 122   (5060 rows)
   customer_id 122 .. 189   (5342 rows)
   customer_id 189 .. 253   (5161 rows)
   customer_id 253 .. 313   (4744 rows)
   customer_id 313 .. 374   (4921 rows)
   customer_id 374 .. 438   (5102 rows)
   customer_id 438 .. 500   (5002 rows)
after OPTIMIZE, files read for customer_id = 42: [1]
```

Before `OPTIMIZE` the appends were not clustered: each daily append wrote one file holding every customer (on Databricks, clustering on write only starts above a size threshold, see below; open-source Delta's behavior here was not checked), so the filter read all eight files. After `OPTIMIZE`, each file covers a narrow customer range and the filter reads one.

**Changing the keys.** Suppose the analysts now filter by time, not customer. With partitioning you would rewrite the table. With liquid clustering, `ALTER TABLE ... CLUSTER BY` changes the keys; "existing data is not rewritten", and to recluster old data you run `OPTIMIZE ... FULL` (Databricks Runtime 16.0 and above) ([Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering)):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
ALTER TABLE orders_lc CLUSTER BY (order_ts);
OPTIMIZE orders_lc;          -- incremental: only data that still needs clustering
OPTIMIZE orders_lc FULL;     -- recluster everything on the new key
```

```text
+--------+-----------------+
|numFiles|clusteringColumns|
+--------+-----------------+
|8       |[order_ts]       |
+--------+-----------------+
after plain OPTIMIZE, files read for last day: [8]
orders_lc: 9 files, min/max of order_ts per file:
   order_ts 2026-03-01T08:00:00.000Z .. 2026-03-01T09:14:39.000Z   (4478 rows)
   ...
   order_ts 2026-03-07T16:26:00.000Z .. 2026-03-08T08:02:39.000Z   (4777 rows)
   order_ts 2026-03-08T08:02:02.000Z .. 2026-03-08T17:59:59.000Z   (4851 rows)
after OPTIMIZE FULL, files read for last day: [2]
+-------+----------+-----------------------------------------------------------------------------------------------+---------------+-------------+
|version|operation |operationParameters                                                                            |numRemovedFiles|numAddedFiles|
+-------+----------+-----------------------------------------------------------------------------------------------+---------------+-------------+
|9      |OPTIMIZE  |{clusterBy -> ["customer_id"], predicate -> [], auto -> false, isFull -> false, zOrderBy -> []}|8              |8            |
|10     |CLUSTER BY|{oldClusteringColumns -> customer_id, newClusteringColumns -> order_ts}                        |NULL           |NULL         |
|11     |OPTIMIZE  |{clusterBy -> ["order_ts"], predicate -> [], auto -> false, isFull -> true, zOrderBy -> []}    |8              |9            |
+-------+----------+-----------------------------------------------------------------------------------------------+---------------+-------------+
```

The history tells the story. Version 10 is the key change, a metadata-only commit. The plain `OPTIMIZE` after it wrote no version at all: the files were already clustered (on the old key), so there was nothing incremental to do, and the last-day filter still read all eight files. Only `OPTIMIZE FULL` (version 11, `isFull -> true`) rewrote the files by `order_ts`, after which the filter read two files (the day boundary fell inside one file). This matches the Databricks page: run `OPTIMIZE FULL` "when you enable clustering for the first time or change clustering keys", and expect it to take hours on a large table that was not clustered on those keys.

What the open-source engine refused, which matches the Databricks rules:

```text
ERROR for: OPTIMIZE orders_lc ZORDER BY (customer_id)
   [DELTA_CLUSTERING_WITH_ZORDER_BY] OPTIMIZE command for Delta table with clustering cannot specify ZORDER BY. Please remove ZORDER BY (customer_id).
ERROR for: CREATE TABLE orders_pc (...) USING DELTA PARTITIONED BY (status) CLUSTER BY (customer_id)
   Operation not allowed: Clustering and partitioning cannot both be specified. Please remove PARTITIONED BY if you want to create a Delta table with clustering.
ERROR for: CREATE TABLE orders_auto (...) USING DELTA CLUSTER BY AUTO
   [PARSE_SYNTAX_ERROR] Syntax error at or near 'AUTO': missing '('. SQLSTATE: 42601
```

"Clustering is not compatible with partitioning or `ZORDER`" ([Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering)). `CLUSTER BY AUTO` is a Databricks feature, so open-source Delta 4.4.1 does not parse it.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 360" role="img" aria-label="Left: a table partitioned by customer_id has 500 folders with tiny files; 1,000 rows wrote 1,000 files and OPTIMIZE cannot go below 500. Right: a liquid clustered table keeps 8 files in one folder, each covering a range of customer_id, and the keys can be changed with ALTER TABLE and OPTIMIZE FULL.">
<text x="20" y="26" font-size="14" font-weight="bold" text-anchor="start" fill="currentColor">PARTITIONED BY (customer_id)</text>
<text x="20" y="46" font-size="13" text-anchor="start" fill="currentColor">one folder per value, fixed at creation</text>
<rect x="20" y="60" width="270" height="36" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="30" y="83" font-size="13" text-anchor="start" fill="currentColor">customer_id=1/</text>
<rect x="170" y="70" width="22" height="16" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="70" width="22" height="16" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="20" y="104" width="270" height="36" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="30" y="127" font-size="13" text-anchor="start" fill="currentColor">customer_id=2/</text>
<rect x="170" y="114" width="22" height="16" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="114" width="22" height="16" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="20" y="148" width="270" height="36" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="30" y="171" font-size="13" text-anchor="start" fill="currentColor">customer_id=3/</text>
<rect x="170" y="158" width="22" height="16" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="158" width="22" height="16" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<text x="155" y="206" font-size="13" text-anchor="middle" fill="currentColor">... 500 folders ...</text>
<rect x="20" y="216" width="270" height="36" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="30" y="239" font-size="13" text-anchor="start" fill="currentColor">customer_id=500/</text>
<rect x="170" y="226" width="22" height="16" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<rect x="200" y="226" width="22" height="16" rx="1" fill="none" stroke="currentColor" stroke-width="1"/>
<text x="20" y="282" font-size="13" text-anchor="start" fill="currentColor">1,000 rows wrote 1,000 tiny files.</text>
<text x="20" y="300" font-size="13" text-anchor="start" fill="currentColor">OPTIMIZE stops at 500: it cannot merge</text>
<text x="20" y="318" font-size="13" text-anchor="start" fill="currentColor">files across folders.</text>
<text x="20" y="342" font-size="13" text-anchor="start" fill="currentColor">Changing it means a full rewrite.</text>
<line x1="320" y1="14" x2="320" y2="350" stroke="currentColor" stroke-width="1" stroke-dasharray="3 4"/>
<text x="340" y="26" font-size="14" font-weight="bold" text-anchor="start" fill="currentColor">CLUSTER BY (customer_id)</text>
<text x="340" y="46" font-size="13" text-anchor="start" fill="currentColor">one folder; key ranges live in file stats</text>
<rect x="340" y="60" width="134" height="38" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="407" y="84" font-size="13" text-anchor="middle" fill="currentColor">1 to 59</text>
<rect x="482" y="60" width="134" height="38" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="549" y="84" font-size="13" text-anchor="middle" fill="currentColor">59 to 122</text>
<rect x="340" y="108" width="134" height="38" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="407" y="132" font-size="13" text-anchor="middle" fill="currentColor">122 to 189</text>
<rect x="482" y="108" width="134" height="38" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="549" y="132" font-size="13" text-anchor="middle" fill="currentColor">189 to 253</text>
<rect x="340" y="156" width="134" height="38" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="407" y="180" font-size="13" text-anchor="middle" fill="currentColor">253 to 313</text>
<rect x="482" y="156" width="134" height="38" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="549" y="180" font-size="13" text-anchor="middle" fill="currentColor">313 to 374</text>
<rect x="340" y="204" width="134" height="38" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="407" y="228" font-size="13" text-anchor="middle" fill="currentColor">374 to 438</text>
<rect x="482" y="204" width="134" height="38" rx="4" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="549" y="228" font-size="13" text-anchor="middle" fill="currentColor">438 to 500</text>
<text x="340" y="282" font-size="13" text-anchor="start" fill="currentColor">40,000 rows: 8 files after OPTIMIZE,</text>
<text x="340" y="300" font-size="13" text-anchor="start" fill="currentColor">each covering a range of customer_id.</text>
<text x="340" y="318" font-size="13" text-anchor="start" fill="currentColor">ALTER TABLE ... CLUSTER BY changes keys;</text>
<text x="340" y="342" font-size="13" text-anchor="start" fill="currentColor">OPTIMIZE FULL reclusters old files.</text>
</svg>
<figcaption>Figure 22.4. Partitioning versus liquid clustering on the same key. Left: the 1,000-row run from section 22.5. Right: the 40,000-row run from section 22.7. Partitioning fixes physical folders; liquid clustering records ranges in per-file statistics and can change its keys later.</figcaption>
</figure>

### Choosing keys, and the Databricks-only parts

Rules from the liquid clustering page:

- Choose keys from "the columns most frequently used in query filters". "If two columns are highly correlated, you only need to include one of them."
- "You can specify **up to four clustering keys**." On tables under 10 TB, more keys can hurt single-column filters ("filtering with four keys performs worse than filtering with two keys").
- Keys must be columns with statistics (the first 32 by default, section 22.6). Supported types include date, timestamp, string, integer types, float, double and decimal; a struct field (`struct_col.field`) works, maps and arrays do not.
- When migrating: use the partition columns, the `ZORDER BY` columns, or both, as keys; for a generated column such as a date derived from a timestamp, "use the original column as a clustering key, and don't create a generated column".
- **Clustering on write** happens for `INSERT INTO`, CTAS/RTAS, `COPY INTO` from Parquet and `spark.write.mode("append")`, but only when the data in the transaction exceeds a threshold. For Unity Catalog managed tables it is 64 MB for one key, 256 MB for two, 512 MB for three and 1 GB for four (four times higher for other Delta tables). "Because not all operations apply liquid clustering, Databricks recommends frequently running `OPTIMIZE`."
- Without predictive optimization, "For tables experiencing many updates or inserts, Databricks recommends scheduling an `OPTIMIZE` job every one or two hours." With predictive optimization, "Databricks recommends disabling any scheduled OPTIMIZE jobs."
- Liquid tables use Delta writer version 7 and reader version 3; older clients cannot read them, and the protocol cannot be downgraded.

**Automatic liquid clustering** lets Databricks choose the keys: "In Databricks Runtime 15.4 LTS and above, you can enable automatic liquid clustering for Unity Catalog managed Delta Lake tables." It "requires predictive optimization for automatic key selection and clustering operations, and runs asynchronously". It analyzes the table's query history, can change keys when patterns change, and only does so "when the predicted cost savings from data skipping improvements outweigh the data clustering cost". It might select no keys if the table is too small, already well clustered, rarely queried, or written by runtimes older than 15.4 LTS.

*Databricks only, not run here. Syntax from [Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering).*

```sql
CREATE OR REPLACE TABLE shop.silver.orders (order_id INT, customer_id INT, order_ts TIMESTAMP,
  status STRING, amount DECIMAL(10,2), currency STRING) CLUSTER BY AUTO;

ALTER TABLE shop.silver.orders CLUSTER BY (customer_id, order_ts);  -- give hints first ...
ALTER TABLE shop.silver.orders CLUSTER BY AUTO;                     -- ... then let Databricks take over
ALTER TABLE shop.silver.orders CLUSTER BY NONE;                     -- turn clustering off (no rewrite)

-- Databricks Runtime 18.1 and above: convert a partitioned table in place
ALTER TABLE shop.silver.orders_by_day REPLACE PARTITIONED BY WITH CLUSTER BY (order_ts, customer_id);
OPTIMIZE shop.silver.orders_by_day;

-- Databricks Runtime 18.1 and above: recluster only part of the table
OPTIMIZE shop.silver.orders FULL WHERE order_ts >= '2026-01-01';
```

Two traps from the same page: running `CREATE OR REPLACE` on an auto-clustered table without `CLUSTER BY AUTO` "turns off automatic clustering and does not preserve clustering columns"; and with the DataFrame API you can set clustering (or `clusterByAuto`) only when creating or overwriting a table, not in `append` mode. Since Databricks Runtime 17.1, **hierarchical clustering** (`delta.liquid.hierarchicalClusteringColumns`) can prioritize low-cardinality keys such as a date over the others.

| | Partitioning | Z-order | Liquid clustering |
| --- | --- | --- | --- |
| How it is set | `PARTITIONED BY` at creation | Each `OPTIMIZE ... ZORDER BY` run | `CLUSTER BY` (or `AUTO`) on the table |
| Good columns | Low, known cardinality (dates, regions) | High cardinality filter columns | Low or high cardinality, up to 4 keys |
| Changing it | Rewrite the table | Run `OPTIMIZE` with new columns | `ALTER TABLE ... CLUSTER BY`, then `OPTIMIZE FULL` for old data |
| New writes | Go into partition folders | Not Z-ordered until next `OPTIMIZE` | Clustered on write above a size threshold, else by `OPTIMIZE` |
| Maintenance | `OPTIMIZE` within partitions | Manual; predictive optimization ignores Z-ordered files | Incremental `OPTIMIZE`; predictive optimization runs it |
| Databricks advice | Only above ~100 TB, after trying clustering | Replaced by liquid clustering | Recommended for all new tables |

!!! tip "In the interview"
    **"Z-order or liquid clustering?"** Liquid clustering for new tables, per the docs. Z-order is a one-off rewrite you must repeat after new data arrives, cannot be combined with clustering, and is ignored by predictive optimization. Liquid clustering is a table property: keys can change without a rewrite, `OPTIMIZE` is incremental, writes above a threshold are clustered as they land, and `CLUSTER BY AUTO` on Unity Catalog managed tables picks keys from the query history. After changing keys, run `OPTIMIZE FULL` to recluster existing data.

## 22.8 Deletion vectors: cheap writes, a little extra read work
*Level: intermediate.*

**The problem.** Delta files are immutable. Without help, deleting one order from a 5,000-row file means rewriting the 4,999 rows that did not change. On a large table, a `MERGE` that touches a few rows in many files rewrites most of the table.

**The tool.** "Deletion vectors mark rows as modified in metadata instead, and reads apply the deletion vector entries at query time to resolve the current table state" ([Deletion vectors in Databricks](https://docs.databricks.com/aws/en/tables/features/deletion-vectors)). Chapter 4 (section 4.9) showed the `deletion_vector_...bin` file and its log entry. Here the question is the cost: the same `DELETE`, `UPDATE` and `MERGE` on two copies of `orders` (eight files of 5,000 rows), one with deletion vectors off and one with them on.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE orders_nodv (...) USING DELTA TBLPROPERTIES ('delta.enableDeletionVectors' = 'false');
CREATE TABLE orders_dv   (...) USING DELTA TBLPROPERTIES ('delta.enableDeletionVectors' = 'true');
-- on each table:
DELETE FROM t WHERE order_id = 39999;
UPDATE t SET status = 'SHIPPED' WHERE order_id = 39998;
MERGE INTO t USING updates s                    -- 50 changed orders from the last day
  ON t.order_id = s.order_id AND t.order_ts >= '2026-03-08'
  WHEN MATCHED THEN UPDATE SET t.status = s.status;
```

```text
DELETE       numRemovedFiles numAddedFiles numCopiedRows numDeletedRows numDeletionVectorsAdded
orders_nodv  1               1             4999          1              0
orders_dv    0               0             0             1              1

UPDATE       numRemovedFiles numAddedFiles numCopiedRows numUpdatedRows numDeletionVectorsAdded
orders_nodv  1               1             4998          1              0
orders_dv    1               1             0             1              1

MERGE        numTargetFilesRemoved numTargetFilesAdded numTargetRowsCopied numTargetRowsUpdated numTargetDeletionVectorsAdded
orders_nodv  1                     1                   4949                50                   0
orders_dv    0                     1                   0                   50                   1
```

(These are the `operationMetrics` from `DESCRIBE HISTORY`, reshaped into one block; the full tables are in `ch22_dv_merge.out`.) Without deletion vectors every statement copied the unchanged rows of the file: 4,999, 4,998 and 4,949 rows rewritten to change 1, 1 and 50. With deletion vectors, `numCopiedRows` is 0 every time: the `DELETE` wrote no data file at all, and the `UPDATE` and `MERGE` wrote only a small new file holding the changed rows, plus a deletion vector marking the old versions.

**The read side.** Readers now apply the deletion vectors: every scan of that file must skip the marked rows. That cost grows as vectors accumulate, until the files are rewritten. The Databricks page lists three ways to apply them physically: `OPTIMIZE`, `REORG TABLE ... APPLY (PURGE)`, or a write with auto compaction. Its caveat: "File compaction events don't have strict guarantees for resolving changes recorded in deletion vectors."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
REORG TABLE orders_dv APPLY (PURGE);
```

```text
+-------+---------+---------------+-------------+-------------------------+
|version|operation|numRemovedFiles|numAddedFiles|numDeletionVectorsRemoved|
+-------+---------+---------------+-------------+-------------------------+
|12     |REORG    |1              |1            |1                        |
+-------+---------+---------------+-------------+-------------------------+
```

All three changes hit the same day-8 file, so one file carried the (combined) deletion vector, and `REORG` rewrote just that one file. `APPLY (PURGE)` "only rewrites files that contain soft-deleted data" ([REORG TABLE](https://docs.databricks.com/aws/en/sql/language-manual/delta-reorg-table)). The query result before and after was identical (50 `DELIVERED`, 1 `SHIPPED`, 39,948 `PLACED`). For a GDPR-style delete, purge is not enough: the old file still exists, so run `VACUUM` after the purge as well (chapter 4, section 4.8).

**On Databricks**, deletion vectors matter even more:

- **Predictive I/O for updates.** On Photon compute, "Predictive I/O for updates are used automatically for all tables that have deletion vectors enabled", on serverless and pro SQL warehouses and clusters running Databricks Runtime 14.0 and above ([What is predictive I/O?](https://docs.databricks.com/aws/en/optimizations/predictive-io)).
- **Row-level concurrency.** "In Databricks Runtime 14.2 and above, tables with deletion vectors support row-level concurrency" ([Deletion vectors in Databricks](https://docs.databricks.com/aws/en/tables/features/deletion-vectors)), which reduces write conflicts. The [Row-level concurrency](https://docs.databricks.com/aws/en/optimizations/isolation/row-level-concurrency) page itself gives Databricks Runtime 14.3 LTS and above, for unpartitioned tables ([chapter 4](04-Delta-Lake.md)); the two pages disagree on the first version, so it is not verified.
- **Client support.** With Photon, `MERGE`, `UPDATE` and `DELETE` write deletion vectors from Databricks Runtime 12.2 LTS; without Photon, `DELETE` from 12.2 LTS, `UPDATE` from 14.1 and `MERGE` from 14.3 LTS. Reading needs 12.2 LTS or above (same page).
- **Enabling.** Delta tables need deletion vectors enabled explicitly, by property or by the workspace setting **Auto-Enable Deletion Vectors**, whose default "varies by region" ([Auto-enable deletion vectors](https://docs.databricks.com/aws/en/admin/workspace-settings/deletion-vectors)). Enabling upgrades the table protocol, and "clients without deletion vector support can't read the table". In Databricks Runtime 16.4 LTS and above you can drop the feature again.

!!! tip "In the interview"
    **"What do deletion vectors trade off?"** Write cost for read cost. A `DELETE`, `UPDATE` or `MERGE` marks changed rows in a small vector instead of rewriting whole Parquet files, so writes that touch few rows get much cheaper; readers then filter the marked rows until `OPTIMIZE`, `REORG ... APPLY (PURGE)` or auto compaction rewrites the files. On Databricks they also enable predictive I/O for updates on Photon and row-level concurrency. The protocol upgrade can lock out older readers.

## 22.9 Predictive optimization
*Level: intermediate.*

Sections 22.3 to 22.8 all end with "run `OPTIMIZE`" or "collect statistics". **Predictive optimization** does that maintenance for you: it "automatically runs `OPTIMIZE`, `VACUUM`, and `ANALYZE` on Unity Catalog managed tables (Delta Lake and Iceberg) on Databricks and refreshes their full-text search indexes" ([Predictive optimization for Unity Catalog managed tables](https://docs.databricks.com/aws/en/optimizations/predictive-optimization)). The page says it "is enabled by default".

| Operation | What it does |
| --- | --- |
| `OPTIMIZE` | Compacts files; "Triggers incremental clustering for enabled tables". Does **not** run `ZORDER`, and ignores Z-ordered files |
| `VACUUM` | Deletes files no longer referenced, using `delta.deletedFileRetentionDuration` (default 7 days) |
| `ANALYZE` | Collects statistics, including data skipping statistics on frequently filtered columns beyond the first 32 |
| `REFRESH INDEX` | Keeps full-text search indexes up to date |

Requirements, exactly as listed:

- "Your Databricks workspace must be on the Premium plan or above in a supported region."
- "You must use SQL warehouses or Databricks Runtime 12.2 LTS or above."
- "Only Unity Catalog managed tables are supported."

It does not run on external tables or on tables loaded as OpenSharing recipients (formerly Delta Sharing; the rename is announced in the Databricks blog post [From Delta Sharing to OpenSharing](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next); product docs: [What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/)). It runs on serverless compute for jobs, billed under a serverless jobs SKU, and its operations are recorded in the system table `system.storage.predictive_optimization_operations_history`. If you want time travel longer than 7 days, set `delta.deletedFileRetentionDuration` before enabling it; below 7 days it still keeps files for at least 7 days.

*Databricks only, not run here. Syntax from [Predictive optimization for Unity Catalog managed tables](https://docs.databricks.com/aws/en/optimizations/predictive-optimization).*

```sql
ALTER CATALOG shop ENABLE PREDICTIVE OPTIMIZATION;
ALTER SCHEMA shop.bronze INHERIT PREDICTIVE OPTIMIZATION;
ALTER TABLE shop.silver.orders DISABLE PREDICTIVE OPTIMIZATION;
DESCRIBE TABLE EXTENDED shop.silver.orders;   -- shows the Predictive Optimization field
```

The setting inherits from account to catalog to schema to table, and an explicit `DISABLE` stays in force even if the account is enabled later. To find out why a table was skipped, Databricks Runtime 18 LTS and above returns a `predictive_optimization_evaluations` field from `DESCRIBE TABLE EXTENDED ... AS JSON`, and Catalog Explorer's **History** tab shows *Not applied* rows with the reason (results can take up to 24 hours).

!!! tip "In the interview"
    **"Do you still schedule OPTIMIZE and VACUUM jobs?"** Not for Unity Catalog managed tables with predictive optimization: it runs `OPTIMIZE`, `VACUUM` and `ANALYZE` when it predicts a benefit, on serverless compute, and Databricks recommends disabling scheduled `OPTIMIZE` jobs for such tables. I still schedule maintenance for external tables, which it does not cover, and for Z-ordered tables, since it does not run `ZORDER`.

## 22.10 Photon
*Level: intermediate.*

**Photon** is "the Databricks-native vectorized query engine". For supported operations it replaces the JVM-based Spark SQL execution with "a native C++ runtime"; Catalyst still plans the query, and Photon processes data "in columnar batches rather than row by row" ([What is Photon?](https://docs.databricks.com/aws/en/compute/photon)). It needs no code change.

What it accelerates, per that page: scans (filter pushdown, dictionary pruning, row-group skipping), hash joins and aggregations and a columnar shuffle, writes through its native Parquet writer (including `UPDATE`, `DELETE`, `MERGE INTO`, `INSERT` and CTAS), window functions, sorts, and SQL and DataFrame code in every language. Two Databricks features require it: **predictive I/O** and **dynamic file pruning in `MERGE`, `UPDATE` and `DELETE`** (sections 22.8 and 22.16).

When it does not help:

- "Photon doesn't support UDFs (User Defined Functions), RDD APIs, or Dataset APIs." Unsupported operations fall back to the Spark runtime "for the remainder of that operation"; results stay correct.
- "Photon doesn't improve queries that normally run in under two seconds", because planning and scheduling dominate.
- "Stateful streaming is not supported. Photon supports stateless streaming only."

**Where it is on.** "Photon is enabled on serverless compute, SQL warehouses, and serverless Lakeflow pipelines." For classic compute and classic pipelines it is on by default in the UI (the **Use Photon Acceleration** checkbox), but through the Clusters or Jobs API you must set `runtime_engine` to `PHOTON`. Lakeflow pipelines were formerly Delta Live Tables ([What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)).

**Cost.** "Photon instance types consume DBUs at a different rate than the same instance type running the non-Photon runtime." So Photon is a price/performance trade: it pays off when the query runs long enough on supported operators to finish sufficiently faster. Check how much of a query actually ran in Photon: in the Spark UI, Photon operators are orange in the SQL/DataFrame DAG; in the query profile, Execution Details shows "the percentage of task time spent in Photon".

!!! tip "In the interview"
    **"We turned on Photon and the job is not faster. Why?"** Check how much of it runs in Photon. Python UDFs, RDD code and some expressions fall back to the JVM engine; stateful streaming is not supported; queries under about two seconds see no gain. Also check that the bottleneck is CPU at all: Photon will not fix skew, small files or a driver-side Python loop. Since Photon compute bills DBUs at a different rate, measure cost per run, not only runtime.

## 22.11 Caching: disk cache, Spark cache, result cache
*Level: intermediate.*

Databricks has several caches, and interviewers like to see that you know which one you mean ([Optimize performance with caching on Databricks](https://docs.databricks.com/aws/en/optimizations/disk-cache)).

- **The disk cache** (formerly the **Delta cache** or **DBIO cache**): "When a node fetches a Parquet data file from remote storage, it automatically stores a copy on its local storage in a fast intermediate format." It works for all Parquet files including Delta tables, is on by default on worker types that support it (SSD workers, using "at most half of the space available on the local SSDs"), and invalidates itself automatically when files change. It is controlled by `spark.databricks.io.cache.enabled`.
- **The Apache Spark cache** (`df.cache()`, `persist()`, `CACHE TABLE`): in-memory blocks of any DataFrame, triggered by your code, evicted with `unpersist()` or LRU. Chapter 3, section 3.9 covers its mechanics.
- **The query result cache** on SQL warehouses: per-warehouse local result cache plus, on serverless, a remote result cache shared by all warehouses in the workspace; both last 24 hours and "are invalidated when the underlying tables are updated" ([Query caching](https://docs.databricks.com/aws/en/sql/user/queries/query-caching)). `SET use_cached_result = false` turns it off, which Databricks says to use "only in testing or benchmarking".

| | Disk cache | Spark cache |
| --- | --- | --- |
| Stored as | Local files on a worker | In-memory blocks (depends on storage level) |
| Applies to | Parquet/Delta files read from cloud storage | Any DataFrame or RDD |
| Triggered | Automatically on first read | Manually, in code |
| Evicted | LRU or on any file change; cluster restart | LRU or `unpersist`; lost when a worker is decommissioned |

Databricks' advice is direct: use the disk cache "instead of the Apache Spark cache for repeated reads of Parquet and Delta Lake data" (disk cache page), and the Delta best practices page has a section titled "Do not use Spark caching with Delta Lake", giving two reasons: "You lose any data skipping that can come from additional filters added on top of the cached `DataFrame`", and "The data that gets cached might not be updated if the table is accessed using a different identifier" ([Best practices: Delta Lake](https://docs.databricks.com/aws/en/delta/best-practices)). The Spark cache still has a place for an expensive computed result (a big join or aggregation) reused several times in one job.

Two version-specific facts: "In SQL warehouses and Databricks Runtime 14.2 and above, the `CACHE SELECT` command is ignored" in favor of an enhanced disk caching algorithm (disk cache page); and on serverless compute, `df.cache()` works differently. It is a Public Preview feature that requires environment version 5 or above, and "Databricks computes the DataFrame when you call `cache()` and materializes the result as a snapshot", so later reads see that snapshot "even if the source tables change" ([Cache DataFrames on serverless compute](https://docs.databricks.com/aws/en/compute/serverless/dataframe-cache)). On classic compute, Spark's `cache()` is lazy.

!!! tip "In the interview"
    **"Should I cache this Delta table to speed up my notebook?"** Usually no. The disk cache (formerly the Delta cache) already keeps the Parquet files on local SSD after the first read, automatically and consistently. `df.cache()` on a table loses data skipping for later filters and can serve stale data. Cache with Spark only an expensive intermediate result you reuse several times, and `unpersist()` it afterwards.

## 22.12 SQL warehouses: sizing and scaling
*Level: intermediate.*

A **SQL warehouse** is the compute behind Databricks SQL. There are three types, with different performance features ([SQL warehouse types](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-types)):

| Type | Photon | Predictive I/O | Intelligent Workload Management | Startup |
| --- | --- | --- | --- | --- |
| Serverless | Yes | Yes | Yes | "typically between 2 and 6 seconds" |
| Pro | Yes | Yes | No | "typically approximately 4 minutes" |
| Classic | Yes | No | No | "typically approximately 4 minutes" |

Two separate knobs control a warehouse ([SQL warehouse sizing, scaling, and queuing behavior](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-behavior)):

- **Cluster size** (2X-Small to 5X-Large) is the power of *one* cluster: how big a single query can be. Grow it when queries spill: "If queries are spilling to disk, increase the cluster size. Check for spills in the query profile."
- **Number of clusters** (minimum and maximum) is concurrency: how many queries run at once. Grow it when queries queue: "Monitor the **Peak Queued Queries** metric"; "A consistent value above 0 indicates that you may need a larger cluster size or more clusters."

For **serverless**, Intelligent Workload Management (IWM) predicts each query's needs, admits it if capacity exists or queues it, and the autoscaler adds clusters when wait times grow. Databricks' sizing advice: "Start with a single larger warehouse and let serverless features manage concurrency and performance. It is usually more efficient to size down if necessary than to start small and scale up."

For **classic and pro**, "Databricks recommends one cluster for every 10 concurrent queries", and autoscaling follows fixed rules: add 1 cluster for 2-6 minutes of estimated query load, 2 for 6-12 minutes, 3 for 12-22 minutes, then one more per extra 15 minutes; scale up if a query waits 5 minutes; scale down after 15 minutes of low load. The queue holds at most 1,000 queries for any warehouse type.

!!! tip "In the interview"
    **"Dashboards are slow every morning at 9. Bigger warehouse?"** First check whether queries are slow or waiting. Queue time (Peak Queued Queries, the `EXCESSIVE_QUEUE_TIME` insight) means concurrency: raise the maximum number of clusters. Long execution with bytes spilled to disk means each query lacks memory: raise the cluster size. If neither, look at the queries themselves (files read, pruning, joins) in the query profile.

## 22.13 AQE on Databricks and join strategies
*Level: expert.*

Chapter 3 (sections 3.7 and 3.8) runs the three join strategies, AQE's partition coalescing, its runtime switch from sort-merge to broadcast join, and its skew join, on open-source Spark. This section adds what is specific to Databricks and how to tune joins there.

**AQE on Databricks** "is enabled by default" and has four features: switching sort-merge joins to broadcast hash joins, coalescing post-shuffle partitions, splitting skewed partitions in sort-merge and shuffle hash joins, and propagating empty relations ([Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe)). It applies to queries that are not streaming and that have at least one exchange or subquery. The Databricks-specific settings and defaults on that page:

| Property | Default | Meaning |
| --- | --- | --- |
| `spark.databricks.optimizer.adaptive.enabled` | `true` | Turns AQE on or off |
| `spark.sql.shuffle.partitions` | `200` | Shuffle partitions; set to `auto` for **auto-optimized shuffle** ("sets this number based on the query plan and the query input data size") |
| `spark.databricks.adaptive.autoBroadcastJoinThreshold` | `30MB` | Runtime threshold to switch a sort-merge join to a broadcast hash join |
| `spark.databricks.adaptive.emptyRelationPropagation.enabled` | `true` | Dynamic empty relation propagation |
| `spark.sql.adaptive.advisoryPartitionSizeInBytes` | `64MB` | Target size after coalescing |
| `spark.sql.adaptive.skewJoin.skewedPartitionFactor` | `5` | Skewed if larger than 5 times the median partition ... |
| `spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes` | `256MB` | ... and larger than 256 MB |

Note the two broadcast thresholds. `spark.sql.autoBroadcastJoinThreshold` is the planning-time threshold; the Apache Spark default is 10 MB ([Spark SQL performance tuning](https://spark.apache.org/docs/4.2.0/sql-performance-tuning.html)). The 30 MB value above is Databricks' runtime threshold used by AQE. Also, `spark.sql.shuffle.partitions = auto` is Databricks only: open-source Spark 4.2 rejected it here (see the practice questions).

**How to see what AQE did.** Compare the initial and final plans (`DataFrame.explain()` after the query ran; SQL `EXPLAIN` shows only the initial plan because it does not run the query). The Databricks page names the signs: a different join node; "a `CustomShuffleReader` node with the `Coalesced` property" for coalescing; "a `SortMergeJoin` node with the `isSkew` field set to `true`" for skew. Open-source Spark 4.2 prints them differently, so know both. The skew join from `ch22_joins_aqe.py`, final plan lines only (the script lowered `skewedPartitionThresholdInBytes` to 4 KB so this small demo counts as skewed; the default is 256 MB):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
-- skewJoin.enabled = false, final plan:
   +- *(5) SortMergeJoin [customer_id], [customer_id], Inner
-- skewJoin.enabled = true, final plan:
   +- *(5) SortMergeJoin(skew=true) [customer_id], [customer_id], Inner
      :  +- AQEShuffleRead skewed
         +- AQEShuffleRead
```

and coalescing of 200 shuffle partitions prints `AQEShuffleRead coalesced` (the Databricks page's `CustomShuffleReader ... Coalesced`).

**Broadcast hints: a plan change.** A broadcast hash join copies the small side to every executor, so the big side is never shuffled. When the optimizer cannot see that a side is small (missing statistics, a filter it cannot estimate), a hint forces it. Revenue by product category joins `order_items` to the 40-row `products` table; with automatic broadcasting turned off, the planner picks a sort-merge join, and the hint changes it:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
spark.conf.set("spark.sql.adaptive.enabled", "false")          # static plan, to isolate the hint
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")   # no automatic broadcast
q = """SELECT p.category, sum(i.qty * i.unit_price) AS revenue
       FROM order_items i JOIN products p ON i.product_id = p.product_id GROUP BY p.category"""
spark.sql(q).explain()
spark.sql(q.replace("SELECT p.category", "SELECT /*+ BROADCAST(p) */ p.category")).explain()

# PySpark
items, products = spark.table("order_items"), spark.table("products")
(items.join(F.broadcast(products), "product_id")
      .groupBy("category").agg(F.sum(F.col("qty") * F.col("unit_price")).alias("revenue"))).explain()
```

```text
-- no hint (join lines only)
   +- *(5) SortMergeJoin [product_id], [product_id], Inner
      :  +- Exchange hashpartitioning(product_id, 4), ENSURE_REQUIREMENTS, [plan_id=280]
         +- Exchange hashpartitioning(product_id, 4), ENSURE_REQUIREMENTS, [plan_id=289]
-- BROADCAST(p) hint, and the same with F.broadcast()
   +- *(2) BroadcastHashJoin [product_id], [product_id], Inner, BuildRight, false, false
      +- BroadcastExchange HashedRelationBroadcastMode(List(cast(input[0, int, false] as bigint)),false), [plan_id=419]
[Row(category='Camping', revenue=Decimal('7485000.00')), Row(category='Climbing', revenue=Decimal('7185000.00'))]
```

Without the hint, both sides are shuffled by `product_id` (two `Exchange` nodes) and sorted. With it, `order_items` is read where it is and joined against a broadcast copy of `products` (`BuildRight`). Same answer, one shuffle fewer.

Join hint rules from the Databricks [Hints](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-hints) reference: the strategies are `BROADCAST`, `MERGE`, `SHUFFLE_HASH` and `SHUFFLE_REPLICATE_NL`; when both sides carry different hints, Databricks SQL prefers "`BROADCAST` over `MERGE` over `SHUFFLE_HASH` over `SHUFFLE_REPLICATE_NL`"; and "Databricks SQL is not guaranteed to use the join strategy suggested by the hint" because not every strategy supports every join type. The partitioning hints are `COALESCE`, `REPARTITION`, `REPARTITION_BY_RANGE` and `REBALANCE`; `REBALANCE` splits skewed output partitions before a write so files are "not too small and not too big", and is "ignored if AQE is not enabled".

**Should you still hint with AQE on?** The AQE page answers: "Yes, if you know your query well. A broadcast join that the optimizer plans before the query runs usually performs better than one that AQE plans at runtime", because AQE may only switch after both sides are already shuffled. Its FAQ also explains why AQE sometimes does not broadcast a small table: the join type cannot broadcast that side ("AQE can't broadcast the left side of a `LEFT OUTER JOIN`"), or the table has many empty partitions (`spark.sql.adaptive.nonEmptyPartitionRatioForBroadcastJoin`). And "AQE doesn't reorder joins at runtime": join order comes from the **cost-based optimizer**, which needs table and column statistics (`ANALYZE TABLE`, or predictive optimization on managed tables) ([Cost-based optimizer](https://docs.databricks.com/aws/en/optimizations/cbo)).

!!! warning "Broadcasting a big table"
    A broadcast side is collected and copied to every executor. Hinting `BROADCAST` on a table that is not small, or raising the threshold too far, causes memory errors; the Spark memory issues page lists "A large broadcast" as a common cause and says to "Check for broadcast join hints on large tables" ([Spark memory issues](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/spark-memory-issues)).

**Dynamic file pruning** is a Databricks join optimization for Delta tables: "At runtime, the optimizer pushes the filter results from one side of the join down to the scan of the Delta Lake table and skips files that can't contain matching rows" ([Dynamic file pruning](https://docs.databricks.com/aws/en/optimizations/dynamic-file-pruning)). It is on by default, applies only to joins on Delta tables, and by default triggers only when the large table is at least 10 GB and has at least 10 files (`spark.databricks.optimizer.deltaTableSizeThreshold`, `spark.databricks.optimizer.deltaTableFilesThreshold`). Its effect depends on clustering: "If the values you join on are spread across every file, dynamic file pruning skips few files", so cluster the large table on the join columns.

!!! tip "In the interview"
    **"How do you make a fact-to-dimension join faster?"** Broadcast the dimension so the fact table is not shuffled: Databricks does it automatically below the thresholds (AQE switches at runtime up to 30 MB by default), and a `BROADCAST` hint plans it up front, which the docs say usually beats a runtime switch. If the join is selective, cluster the fact table on the join key so dynamic file pruning can skip files. Keep statistics current so the cost-based optimizer orders multi-way joins well.

## 22.14 Skew: AQE first, salting second
*Level: expert.*

**Skew** is one key holding far more rows than the rest; after a shuffle, one task gets that key and runs for 40 minutes while the others finish in seconds. On the Spark UI it is Max far above the 75th percentile in a stage's Summary Metrics; in the query profile it is the `DATA_SKEW` insight.

The Databricks fixes, in order of effort ([Skew and spill](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/long-spark-stage-page)):

1. **Check whether AQE handles it.** AQE splits a skewed partition of a sort-merge or shuffle hash join, but only if it exceeds both thresholds (5 times the median and 256 MB by default). It "never optimizes skew in broadcast joins", and the join type limits which side it can split ([Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe)):

    | Join type | Left side split | Right side split |
    | --- | --- | --- |
    | `INNER`, `CROSS` | Yes | Yes |
    | `LEFT OUTER`, `LEFT SEMI`, `LEFT ANTI` | Yes | No |
    | `RIGHT OUTER` | No | Yes |
    | `FULL OUTER` | No | No |

2. **Adjust the AQE thresholds** if the skewed partitions are smaller than them.
3. **Salt skewed keys or pre-aggregate**: "append a random bucket suffix to the skewed keys, and then group and aggregate in two stages."
4. **Cluster the source table** with liquid clustering, if the skew comes from the stored layout.
5. **Rebalance output partitions** with the `REBALANCE` hint when the skewed stage writes a table.

The old `SKEW` join hint is documented only on a retired page: "Skew join hints are not required. Databricks handles skew by default by using adaptive query execution (AQE)" ([Skew join optimization using skew hints](https://docs.databricks.com/aws/en/archive/legacy/skew-join)). The AQE page agrees: "Use AQE skew join handling."

**Salting, shown.** AQE skew handling covers joins only; a skewed `GROUP BY` or a `FULL OUTER` join needs salting. In this Red Rock Supply data, customer 7 (a reseller account) places 80% of 300,000 orders. Shuffling by `customer_id` into eight partitions:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def rows_per_partition(df, label):
    sizes = [r["n"] for r in df.groupBy(F.spark_partition_id().alias("p"))
                                .agg(F.count("*").alias("n")).orderBy("p").collect()]
    print(f"{label}: rows per partition = {sizes}")

N, SALTS = 8, 16
rows_per_partition(orders.repartition(N, "customer_id"), "by customer_id")

salted = orders.withColumn("salt", F.col("order_id") % SALTS)   # or (F.rand() * SALTS).cast("int")
rows_per_partition(salted.repartition(N, "customer_id", "salt"), "by (customer_id, salt)")
stage1 = salted.groupBy("customer_id", "salt").agg(F.sum("amount").alias("part_sum"))
stage2 = stage1.groupBy("customer_id").agg(F.sum("part_sum").alias("revenue"))
plain = orders.groupBy("customer_id").agg(F.sum("amount").alias("revenue"))
print("salted result equals plain result:", sorted(stage2.collect()) == sorted(plain.collect()))
```

```text
by customer_id: rows per partition = [7254, 7260, 7632, 247764, 7338, 7650, 7620, 7482]
by (customer_id, salt): rows per partition = [52380, 22026, 37296, 52578, 22746, 22272, 37566, 53136]
salted result equals plain result: True
```

One partition held 247,764 of the 300,000 rows; after salting, the largest holds 53,136, so the slowest task has about a fifth of the work. Stage 1 sums each (customer, salt) slice in parallel; stage 2 adds the at most 16 partial sums per customer, which is tiny. The partitions are not perfectly even because 16 salt values of one key are hashed into 8 partitions and some collide; more salt values spread better, at the cost of more partial rows. The same in SQL:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
WITH salted AS (
  SELECT customer_id, amount, order_id % 16 AS salt FROM orders),
partial AS (
  SELECT customer_id, salt, sum(amount) AS part_sum FROM salted GROUP BY customer_id, salt)
SELECT customer_id, sum(part_sum) AS revenue
FROM partial WHERE customer_id IN (7, 8, 9) GROUP BY customer_id ORDER BY customer_id;
```

```text
+-----------+-----------+
|customer_id|revenue    |
+-----------+-----------+
|7          |13895359.00|
|8          |297.40     |
|9          |303.40     |
+-----------+-----------+
```

Salting only works for aggregates you can combine in two steps (`sum`, `count`, `min`, `max`; an average as sum and count). A median or an exact `count(DISTINCT)` does not split that way.

**A salted join.** For a join, salt the big side and copy each row of the small side once per salt value, then join on the key plus the salt:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
o_salted = orders.withColumn("salt", F.col("order_id") % SALTS)
c_salted = customers.withColumn("salt", F.explode(F.sequence(F.lit(0), F.lit(SALTS - 1))))
joined_salted = o_salted.join(c_salted, ["customer_id", "salt"]).drop("salt")
```

```text
customers rows: 50000 -> salted customers rows: 800000
plain join output: rows per partition = [7254, 7260, 7632, 247764, 7338, 7650, 7620, 7482]
salted join output: rows per partition = [52380, 22026, 37296, 52578, 22746, 22272, 37566, 53136]
same answer: True
```

The cost is visible in the second line: the small side grew 16 times. Prefer AQE skew handling for joins (it needs no code), and if the small side is small enough, a broadcast join has no shuffle and so no skew at all.

!!! tip "In the interview"
    **"One task runs 40 minutes while the others take seconds. What do you do?"** That is skew: confirm it in the stage's Summary Metrics (Max far above the 75th percentile) and find the hot key with a `GROUP BY key ORDER BY count DESC`. If it is a sort-merge join, check that AQE skew handling applies (both thresholds, a supported join type, not a broadcast join) and lower the thresholds if needed. If it is an aggregation or a `FULL OUTER` join, salt the key and aggregate in two stages, or filter the hot key out and process it separately. If the skew is in the stored table, liquid clustering helps.

## 22.15 Spill, memory, shuffle partitions, and the driver
*Level: expert.*

**Spill** is execution data written to local disk because it did not fit in memory: sort buffers, hash tables for joins and aggregations, shuffle data. The query still succeeds, but disk I/O replaces memory access, so a stage can slow down many times. You see it as spill statistics on the Spark UI stage page, as "Bytes spilled to disk" in the query profile, and as the `DATA_SPILL` insight.

The fixes from [Skew and spill](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/long-spark-stage-page):

- **Use auto-optimized shuffle**: `spark.sql.shuffle.partitions=auto`, "so that Spark picks the number of shuffle partitions based on the query plan and input data size". A fixed 200 partitions over a 2 TB shuffle means about 10 GB per task, which spills; the same 200 over 20 MB means tiny tasks (AQE coalescing fixes that case).
- **Reduce the data held in memory**: fewer rows or columns, or smaller large columns (strings, arrays, maps, structs). Select only the columns you need before a join.
- **Increase executor memory**: memory-heavier instances, and for complex joins "fewer, larger workers to reduce the amount of data shuffled".
- **Limit the streaming batch size** if the stage belongs to a stream (section 22.17).
- On a SQL warehouse: "If queries are spilling to disk, increase the cluster size" (section 22.12).

When memory runs out completely, executors are lost and tasks retried, with generic errors such as "ExecutorLostFailure ... Remote RPC client disassociated". Databricks' test: double the memory per core (the ratio, "not the total memory") and see whether the failure goes away. The common causes it lists: too few shuffle partitions, a large broadcast, UDFs (each task may load its whole partition into memory), a window function without `PARTITION BY`, skew, and large streaming state ([Spark memory issues](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/spark-memory-issues)).

*Databricks only, not run here. Setting from [Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe).*

```python
spark.conf.set("spark.sql.shuffle.partitions", "auto")   # auto-optimized shuffle (Databricks)
```

**UDFs and the driver.** Two more Databricks-documented performance points, both covered with runs in chapter 3 (sections 3.10 and 3.11):

- **Prefer built-in functions.** "Built-in functions and SQL UDFs are the most efficient options." Python and pandas UDFs "must serialize data and move it out of the JVM to the Python interpreter", and "Pandas UDFs are up to 100x faster than Python UDFs because they use Apache Arrow to reduce serialization costs" ([What are user-defined functions (UDFs)?](https://docs.databricks.com/aws/en/udf/)). Photon cannot run UDFs at all. If a UDF stage has fewer tasks than cores, `repartition()` before it ([Slow Spark stage with little I/O](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/slow-spark-stage-low-io)).
- **Keep work off the driver.** `collect()` and `toPandas()` bring every row to the single driver process; Python loops over the result run with the workers idle, and show up as gaps in the jobs timeline. Aggregate or write with Spark instead, and bring back only small results (`limit`, `take`, an aggregate).

!!! tip "In the interview"
    **"What is spill and how do you fix it?"** Spill is Spark writing execution data (sorts, joins, aggregations, shuffles) to disk because it did not fit in executor memory; it shows in the stage details or as bytes spilled in the query profile. Fix the cause: partitions too large (use `spark.sql.shuffle.partitions=auto` on Databricks, or more partitions), too much data per row (prune columns), skew (one partition too large), or too little memory per core (bigger instances, a larger warehouse size).

## 22.16 MERGE performance
*Level: expert.*

`MERGE` is the workhorse of silver and gold (chapter 9), and the most common slow write. It works in two phases: find the target files that contain matching rows (a join between source and target), then rewrite those files with the changes. Both phases can be made cheaper ([Best practices: Delta Lake](https://docs.databricks.com/aws/en/delta/best-practices)):

- **Reduce the search space.** "By default, the `merge` operation searches the entire Delta Lake table to find matches in the source table." Add known constraints on the target to the `ON` clause, for example `events.date = current_date() AND events.country = 'USA'`, so only matching partitions or files are scanned. This "also reduces the chances of conflicts with other concurrent operations". With a clustered or ingestion-ordered table, a range on the clustering column prunes files through statistics the same way.
- **Compact files.** Many small target files make the match phase slow.
- **Control shuffle partitions.** `spark.sql.shuffle.partitions` sets the parallelism of `MERGE`'s shuffles and the number of output files.
- **Optimized writes** for partitioned tables, where `MERGE` can otherwise write many small files (on Databricks they are always on for `MERGE`, section 22.4).
- **Low shuffle merge**, "the optimized Databricks implementation of `MERGE`", is on by default: it "processes unmodified rows separately from modified rows, without shuffles" and "tries to preserve the existing layout of unmodified rows, including liquid clustering layout" ([Low shuffle merge on Databricks](https://docs.databricks.com/aws/en/optimizations/low-shuffle-merge)). It helps most "when a `MERGE` updates a relatively small number of rows in a large table".

Two more Databricks levers:

- **Deletion vectors** (section 22.8): the run above showed a 50-row `MERGE` copying 4,949 unchanged rows without them and 0 with them. On Photon, predictive I/O for updates builds on them.
- **Dynamic file pruning in `MERGE`**: uses "the join key values from the source to skip target files when the merge condition compares a source column with a target column for equality". It requires Photon-enabled compute and, by default, a target of at least 10 GB and 10 files ([Dynamic file pruning](https://docs.databricks.com/aws/en/optimizations/dynamic-file-pruning)). Liquid clustering on the merge key makes it skip more files.

*Databricks only, not run here. Pattern from [Best practices: Delta Lake](https://docs.databricks.com/aws/en/delta/best-practices).*

```sql
-- Late updates only ever touch the last 3 days: say so in the ON clause
MERGE INTO shop.silver.orders AS t
USING updates AS s
  ON  t.order_id = s.order_id
  AND t.order_ts >= current_date() - INTERVAL 3 DAYS
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

!!! warning "A pruning predicate changes the result if it is wrong"
    The extra condition in `ON` is part of the match. If an update arrives for an order older than 3 days, the row does not match, and `WHEN NOT MATCHED THEN INSERT` inserts a duplicate. Only add a target predicate you can guarantee from the data (for example, from how late updates can be), or route older updates separately. The same applies to a source-side filter. Chapter 9 (section 9.7) covers late data in `MERGE`.

!!! tip "In the interview"
    **"A MERGE of 10,000 changed rows into a 5 TB table takes hours. What do you change?"** Make it scan less and rewrite less. Add a target predicate to the `ON` clause (a date range, a clustering key) so only relevant files are searched; cluster the table on the merge key and run on Photon so dynamic file pruning skips files; enable deletion vectors so matched files are not rewritten in full; make sure the source is deduplicated and small. Then check the history metrics (`numTargetRowsCopied`, files removed and added) to confirm.

## 22.17 Streaming performance
*Level: expert.*

Structured Streaming runs as a series of micro-batches (chapter 11). Its performance levers are how often a batch runs, how big each batch is, and how much state it keeps.

**Trigger interval.** "By default, if you don't set a trigger mode, Structured Streaming sets the trigger mode to `processingTime` and the interval to `0`, which checks for new data every few milliseconds. This can generate a high volume of cloud storage API calls per day and result in unexpected charges" ([Configure Structured Streaming trigger intervals](https://docs.databricks.com/aws/en/structured-streaming/triggers)). Choose:

- `.trigger(processingTime="1 minute")` to balance latency and cost;
- `.trigger(availableNow=True)` for scheduled incremental batches ("`Trigger.Once` is deprecated" from Databricks Runtime 11.3 LTS);
- real-time mode (`.trigger(realTime=...)`) for sub-second latency; Apache Spark's experimental continuous processing is not supported on Databricks.

On serverless compute, notebooks and jobs support only `AvailableNow` and `Once` triggers ([Production considerations for Structured Streaming](https://docs.databricks.com/aws/en/structured-streaming/production)).

**Batch size: admission control.** A stream that was down for a day, or a first run over a large backlog, can try to read everything in one micro-batch, then spill or run out of memory. `maxFilesPerTrigger` sets "an upper-bound for the number of files processed in each micro-batch" and `maxBytesPerTrigger` "a 'soft max'"; with both, the batch stops at whichever limit comes first; Auto Loader uses `cloudFiles.maxFilesPerTrigger` and `cloudFiles.maxBytesPerTrigger`, and Kafka has `maxOffsetsPerTrigger` ([Configure Structured Streaming batch size on Databricks](https://docs.databricks.com/aws/en/structured-streaming/batch-size)). For a Delta source, the default `maxFilesPerTrigger` is 1000 and `maxBytesPerTrigger` "is not set by default" ([Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)). A `bronze_orders` table of ten files, read three ways with `availableNow`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
q = (spark.readStream.format("delta")
       .option("maxFilesPerTrigger", "3")            # or maxBytesPerTrigger, or nothing
       .table("bronze_orders")
       .writeStream.format("delta")
       .option("checkpointLocation", chk)
       .trigger(availableNow=True)
       .toTable("silver_orders_max_files_3"))
q.awaitTermination()
print([p["numInputRows"] for p in q.recentProgress if p["numInputRows"] > 0])
```

```text
bronze_orders files: 10
default                      options={}  rows per micro-batch: [1000]
max_files_3                  options={'maxFilesPerTrigger': '3'}  rows per micro-batch: [300, 300, 300, 100]
max_bytes_small              options={'maxBytesPerTrigger': '1b'}  rows per micro-batch: [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
```

The default took all ten files (under the 1,000-file default) in one batch. Three files per trigger gave four batches. A one-byte `maxBytesPerTrigger` still processed one whole file per batch: it is a soft limit, and "a batch processes approximately this amount of data and may process more than the limit in order to make the streaming query move forward" ([Configure Structured Streaming batch size on Databricks](https://docs.databricks.com/aws/en/structured-streaming/batch-size)). `availableNow` respects these limits, processing the backlog in several right-sized batches. You can change admission control without resetting the checkpoint, but a micro-batch already planned before the stop runs with the old settings.

**State.** Stateful queries (aggregations, deduplication, stream-stream joins) keep state in a state store. "RocksDB is the default state store provider in Databricks Runtime 17.3 LTS and above"; below that, set `spark.sql.streaming.stateStore.providerClass` to `com.databricks.sql.streaming.state.RocksDBStateStoreProvider`. **Changelog checkpointing** writes only changed state records at each checkpoint; Databricks recommends it "for all Structured Streaming stateful queries", and it is on by default in 17.3 LTS and above ([Configure RocksDB state store on Databricks](https://docs.databricks.com/aws/en/structured-streaming/rocksdb-state-store)). Keep state bounded with watermarks (chapter 11); state that grows forever is a memory problem waiting to happen.

Other production rules from [Production considerations for Structured Streaming](https://docs.databricks.com/aws/en/structured-streaming/production): run streams as scheduled Lakeflow Jobs (formerly Databricks Jobs, whose menu item was Workflows; see the [June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june) release notes) on jobs compute, not on all-purpose compute; "Don't enable autoscaling for Structured Streaming jobs"; remove `display` and `count` calls from production notebooks. Two engine facts to remember: AQE does not apply to streaming queries, and "For Structured Streaming, you can't change" `spark.sql.shuffle.partitions` "between query restarts from the same checkpoint location" ([Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe)), so the number of state partitions is fixed when the stream first starts. Photon supports stateless streaming only.

!!! tip "In the interview"
    **"A stream fell behind after an outage and now each batch runs out of memory. What do you do?"** Cap the batch size with admission control: `maxFilesPerTrigger` or `maxBytesPerTrigger` on a Delta source (`cloudFiles.` versions for Auto Loader, `maxOffsetsPerTrigger` for Kafka). The stream then drains the backlog in several normal-sized batches. Note that the batch planned before the failure must still complete, so you may need bigger compute once. For stateful queries, use RocksDB with changelog checkpointing and a watermark to bound state. Choose a trigger interval deliberately: the default polls continuously and can raise storage API costs.

## 22.18 Practice questions
*Level: mixed.*

**Q1. A query on `orders` filters `WHERE order_ts >= '2026-03-01' AND order_ts < '2026-03-02'` but the query profile shows almost no files pruned. Name three possible causes and how to check each.**

??? success "Answer"
    1. **The data is not clustered by time.** If each file holds a full range of dates (for example after a `MERGE`-heavy history, or a Z-order on another column, as in section 22.7 where Z-ordering by `customer_id` made a one-file date query read all 8 files), every file's min/max overlaps the filter. Check the min/max per file (or the files-pruned figure); fix with liquid clustering on `order_ts` and `OPTIMIZE` (or `OPTIMIZE FULL` after changing keys).
    2. **The column has no statistics.** By default only the first 32 columns get them. Check the column position and `delta.dataSkippingNumIndexedCols` / `delta.dataSkippingStatsColumns`; fix the property and run `ANALYZE TABLE ... COMPUTE DELTA STATISTICS` (existing files are not recomputed automatically).
    3. **The filter is not usable for skipping.** A filter that converts the column's type is reported by `COVERAGE_STATS_DELTA` as "Unused". Rewrite it as a range on the raw column.

    **Why:** data skipping can only skip a file when its stored min/max for that column proves no row matches.

**Q2. One task in a stage runs 40 minutes while the other 199 take a few seconds. What is happening and what do you try, in order?**

??? success "Answer"
    Data skew: one shuffle partition holds a hot key. Confirm on the stage page: Max duration far above the 75th percentile (Databricks says 50% or more suggests skew). Find the key with `SELECT key, count(*) ... GROUP BY key ORDER BY 2 DESC LIMIT 10`. Then: (1) if it is a sort-merge or shuffle hash join, check AQE skew handling applies (partition over 5 times the median and over 256 MB by default, a join type whose skewed side can be split, not a broadcast join) and lower the thresholds if needed; (2) for an aggregation or `FULL OUTER` join, salt the key and aggregate in two stages, or handle the hot key separately; (3) if the skew comes from the stored layout, liquid clustering.

    **Why:** all rows of one key go to one partition, so one core does most of the work no matter how big the cluster is.

**Q3. OPTIMIZE ran last night, but queries filtering on `customer_id` are still slow. Why might that be?**

??? success "Answer"
    Plain bin-packing `OPTIMIZE` only fixes file sizes; it does not co-locate customers, so every file still spans all customer ids and nothing is skipped (section 22.6). Other causes: the slowness is not in the scan at all (a skewed join, spill, a Python UDF, queueing on the warehouse); the table is partitioned on a high-cardinality column so `OPTIMIZE` cannot merge across partitions; clustering keys were changed but `OPTIMIZE FULL` was not run; or new data arrived after the run. Fix the layout with liquid clustering on `customer_id` (or `CLUSTER BY AUTO`), and look at the query profile to confirm where time goes.

    **Why:** `OPTIMIZE` fixes small files, and with clustering, layout. It is not a general cure.

**Q4. A table partitioned by `customer_id` has 2 million files averaging 40 KB. You run `OPTIMIZE`. What happens to the file count, and what is the real fix?**

??? success "Answer"
    `OPTIMIZE` cannot combine files across partition boundaries, so the best it can do is one file per partition; with a partition per customer, you still have about one file per customer (section 22.5's run: 1,000 files became 500, one per partition). The real fix is to stop partitioning on a high-cardinality column: recreate or convert the table with liquid clustering on `customer_id` (`ALTER TABLE ... REPLACE PARTITIONED BY WITH CLUSTER BY (customer_id)` on Databricks Runtime 18.1 and above), then `OPTIMIZE`.

    **Why:** Databricks says partitioning "works well only for low or known cardinality fields", and partitions should hold at least 1 GB.

**Q5. Your team wants to partition a new 400 GB `orders` table by `order_date`. What does Databricks recommend instead, and why?**

??? success "Answer"
    Do not partition: "With less than 1 TB of data, don't partition." Use liquid clustering on the columns queries filter by (for example `CLUSTER BY (order_ts, customer_id)`), or `CLUSTER BY AUTO` on a Unity Catalog managed table with predictive optimization. Even without clustering, an unpartitioned Delta table gets ingestion-time clustering, so date filters already skip files.

    **Why:** small partitions create small files, cannot be compacted across, and fixing a wrong partitioning needs a full rewrite.

**Q6. What does this print?** A Delta table has 8 files, each holding exactly one day of orders, and customers spread over all days. Then `OPTIMIZE orders ZORDER BY (customer_id)` runs (producing 8 files).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (`ch22_skipping.py`, where `files_read` is defined)

```python
files_read("SELECT * FROM orders WHERE order_ts >= '2026-03-08'")   # before, after
files_read("SELECT * FROM orders WHERE customer_id = 42")           # before, after
```

??? success "Answer"
    From the section 22.6/22.7 run: date filter `[1]` before and `[8]` after; customer filter `[8]` before and `[1]` after.

    **Why:** before, each file's `order_ts` range is one day but its `customer_id` range is the full 1..500. Z-ordering by customer narrows the customer ranges but spreads each day over every file. A layout helps the columns it is built on.

**Q7. Can you use `ZORDER BY` on a liquid clustered table? On a partition column? What does predictive optimization do with Z-ordered tables?**

??? success "Answer"
    No: "You can't use `ZORDER` in combination with liquid clustering" (the run in section 22.7 failed with `DELTA_CLUSTERING_WITH_ZORDER_BY`). No: "You cannot Z-order on fields used for partitioning" (open-source Delta refused it too, with `DELTA_ZORDERING_ON_PARTITION_COLUMN`, in `ch22_extras.out`). Predictive optimization does not run `ZORDER` and "ignores Z-ordered files". Migrate Z-ordered tables to liquid clustering using the `ZORDER BY` columns as clustering keys.

**Q8. You changed a table's clustering keys from `customer_id` to `order_ts` and ran `OPTIMIZE`. Date queries are no faster. Why?**

??? success "Answer"
    Changing keys does not rewrite existing data, and plain `OPTIMIZE` is incremental: it skipped files that were already clustered (on the old key). In the section 22.7 run, the plain `OPTIMIZE` after the key change wrote no new version and the date filter still read 8 files; `OPTIMIZE orders_lc FULL` (history `isFull -> true`) reclustered and the filter dropped to 2. On Databricks, `OPTIMIZE ... FULL` needs Runtime 16.0 and above; on 18.1 and above, `OPTIMIZE ... FULL WHERE` reclusters a range.

**Q9. You set `CLUSTER BY AUTO` on a table a month ago, and `DESCRIBE TABLE` still shows no clustering columns. Give possible reasons.**

??? success "Answer"
    From the liquid clustering page: the table is too small to benefit; it already has an effective layout (earlier keys or a natural insertion order matching the queries); it is not queried often; or workloads run on runtimes older than 15.4 LTS. Also check the prerequisites: it must be a Unity Catalog managed table with predictive optimization enabled, since automatic liquid clustering "requires predictive optimization". The History tab in Catalog Explorer shows an `AUTO LIQUID` row marked *Not applied* with the reason.

**Q10. What does predictive optimization run, on which tables, and what does it need?**

??? success "Answer"
    It runs `OPTIMIZE` (compaction and incremental clustering, never `ZORDER`), `VACUUM`, `ANALYZE` and `REFRESH INDEX` on Unity Catalog managed tables. Requirements: Premium plan or above in a supported region, SQL warehouses or Databricks Runtime 12.2 LTS or above, Unity Catalog managed tables only. Not on external tables or tables received through OpenSharing (formerly Delta Sharing). It runs on serverless jobs compute, billed under a serverless jobs SKU, and is enabled by default.

**Q11. Predictive optimization is on for `shop.silver`, and you also have a nightly job that runs `OPTIMIZE` and `VACUUM` on its tables. Keep it?**

??? success "Answer"
    For the managed tables, no: Databricks recommends disabling scheduled `OPTIMIZE` jobs when predictive optimization is used, since it runs the operations when it predicts a benefit. Keep jobs only for what it does not cover: external tables, Z-ordered tables (it does not run `ZORDER`), or a special retention need. Set `delta.deletedFileRetentionDuration` if you need time travel longer than 7 days.

**Q12. After enabling deletion vectors, `DELETE`s got much faster, but over weeks a frequently read table got slower. Why, and what fixes it?**

??? success "Answer"
    Every read must apply the deletion vectors, filtering out marked rows, and that work grows as vectors accumulate. Rewrite files to apply them: `OPTIMIZE` (or predictive optimization), `REORG TABLE ... APPLY (PURGE)`, or writes with auto compaction. In the section 22.8 run, `REORG ... APPLY (PURGE)` rewrote exactly the one file that carried a vector.

    **Why:** deletion vectors trade write cost for read cost until files are rewritten.

**Q13. A customer asks to be deleted (GDPR). The table has deletion vectors. After `DELETE`, is their data gone from storage?**

??? success "Answer"
    No. The `DELETE` only marked the rows in a deletion vector; the Parquet file still contains them, and older table versions reference it. Run `REORG TABLE ... APPLY (PURGE)` to rewrite the files without the rows, then `VACUUM` once the retention period allows, so the old files are physically deleted.

**Q14. What does this print?** The same one-row delete on two copies of a 5,000-row-per-file table:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (`ch22_dv_merge.py`)

```sql
DELETE FROM orders_nodv WHERE order_id = 39999;  -- deletion vectors off
DELETE FROM orders_dv   WHERE order_id = 39999;  -- deletion vectors on
-- then: DESCRIBE HISTORY ... operationMetrics.numCopiedRows, numDeletionVectorsAdded
```

??? success "Answer"
    From section 22.8: `orders_nodv` copied 4,999 rows (1 file removed, 1 added, 0 vectors); `orders_dv` copied 0 rows (0 files removed or added, 1 deletion vector added).

    **Why:** without deletion vectors, the file holding the row is rewritten with every other row; with them, only the row's position is recorded.

**Q15. Photon is enabled on a job cluster but a Python-heavy job is not faster. Why? How do you check?**

??? success "Answer"
    Photon "doesn't support UDFs (User Defined Functions), RDD APIs, or Dataset APIs"; those parts fall back to the JVM engine. Queries under about two seconds see no gain, and stateful streaming is not supported. Check the share of work in Photon: orange operators in the Spark UI SQL DAG, or the Photon percentage in the query profile, and the `COVERAGE_PHOTON` insight. Replace UDFs with built-in functions where possible.

**Q16. When is Photon not worth its cost?**

??? success "Answer"
    Photon compute consumes DBUs at a different rate, so it pays off only when it shortens the run enough: long scans, joins, aggregations and writes on supported operators. It is a poor fit for workloads dominated by Python UDFs, RDD code, stateful streaming, very short queries, or time spent outside Spark (driver loops, waiting on external systems). Measure cost per run with and without it.

**Q17. A colleague calls `spark.table("shop.silver.orders").cache()` at the top of every notebook "to make it faster". What is wrong with that on Databricks?**

??? success "Answer"
    Databricks recommends against Spark caching of Delta tables: later filters on the cached DataFrame lose data skipping, and the cache can be stale if the table is changed through another identifier. The disk cache (formerly the Delta cache) already caches the Parquet files on local SSD automatically and invalidates on change. Cache only an expensive intermediate result reused several times, and `unpersist()` it. On serverless compute, `cache()` (Public Preview) materializes a snapshot immediately, which is a different behavior again.

**Q18. Someone runs `CACHE SELECT * FROM shop.gold.daily_sales` on a SQL warehouse before a demo. What does it do?**

??? success "Answer"
    Nothing: "In SQL warehouses and Databricks Runtime 14.2 and above, the `CACHE SELECT` command is ignored. An enhanced disk caching algorithm is used instead." Repeated queries may also be served by the query result cache, which is invalidated when the tables change.

**Q19. A query profile is "not available" for a dashboard query that returned instantly. Why, and how do you get one?**

??? success "Answer"
    The result came from the query result cache, and "A query profile is not available for queries that run from the query cache." Make a trivial change (for example to the `LIMIT`) to force a real run. In testing only, `SET use_cached_result = false` disables the result cache.

**Q20. Find the bug: a join of `order_items` (2 billion rows) with `customers_history` (80 GB) fails with executor and driver out-of-memory errors.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (on tiny tables in `ch22_answers.py`, only to confirm that the hint forces a `BroadcastHashJoin`)

```sql
SELECT /*+ BROADCAST(h) */ i.*, h.city
FROM order_items i JOIN customers_history h ON i.customer_id = h.customer_id;
```

??? success "Answer"
    The hint forces an 80 GB table to be collected and copied to every executor. Remove the hint and let a sort-merge join (with AQE) run, or broadcast only a small, filtered projection (for example the current row per customer with just `customer_id, city`). The Spark memory issues page lists "A large broadcast" as a common cause and says to check for broadcast hints on large tables.

    **Why:** a broadcast side must fit in memory on the driver while it is built and on every executor.

**Q21. `customers` is 8 MB, below every broadcast threshold, but AQE keeps a sort-merge join for `customers LEFT OUTER JOIN orders`. Why?**

??? success "Answer"
    The join type decides which side can be broadcast: "AQE can't broadcast the left side of a `LEFT OUTER JOIN`" ([Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe)). A left outer join must keep every customer, even those with no orders, so the engine streams the left (preserved) side and can build a hash table only from the right side, which here is the large `orders`. Writing it as `orders RIGHT OUTER JOIN customers` changes nothing, because `customers` is still the preserved side. If the question only needs customers that have orders, an inner join lets `customers` be broadcast; otherwise accept the shuffle. Another documented reason AQE skips a broadcast: too many empty partitions (`spark.sql.adaptive.nonEmptyPartitionRatioForBroadcastJoin`).

**Q22. AQE skew join is enabled (the default), but a skewed join stage still has one huge task. List the reasons from the docs.**

??? success "Answer"
    The skewed partition is not above both thresholds (5 times the median and 256 MB by default); the join is a broadcast join, which AQE never skew-optimizes; the join type does not allow splitting that side (for example the right side of a `LEFT OUTER`, either side of a `FULL OUTER`); or the skew is in an aggregation or window, not a join. Fixes: lower `skewedPartitionFactor` / `skewedPartitionThresholdInBytes`, change the join shape, or salt.

**Q23. Write PySpark that computes revenue per customer from a skewed `orders` DataFrame using a salted two-stage aggregation with 16 salt buckets.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1 (the section 22.14 script).*

    ```python
    from pyspark.sql import functions as F
    SALTS = 16
    salted = orders.withColumn("salt", (F.rand() * SALTS).cast("int"))   # the run used order_id % SALTS
    revenue = (salted.groupBy("customer_id", "salt").agg(F.sum("amount").alias("part_sum"))
                     .groupBy("customer_id").agg(F.sum("part_sum").alias("revenue")))
    ```

    In the run, the largest shuffle partition fell from 247,764 rows to 53,136 and the result equaled the unsalted one.

    **Why:** the hot key is split across up to 16 groups in stage 1; stage 2 adds at most 16 partial sums per customer. This works for combinable aggregates (`sum`, `count`, `min`, `max`), not for an exact median.

**Q24. A stage shows "Spill (Disk): 120 GB". What does it mean and what do you try?**

??? success "Answer"
    Execution data for a sort, join, aggregation or shuffle did not fit in memory and was written to disk, which slows the stage. Try: `spark.sql.shuffle.partitions=auto` (or more partitions) so each task holds less; select fewer columns and avoid carrying large strings or arrays through the shuffle; fix skew if one partition is the cause; use instances with more memory per core; on a SQL warehouse, increase the cluster size; for a stream, cap the batch size.

**Q25. A job leaves `spark.sql.shuffle.partitions` at 200 for a join that shuffles 3 TB. Why is that a problem, and what does Databricks recommend?**

??? success "Answer"
    3 TB over 200 partitions is about 15 GB per task: tasks spill or fail with memory errors, and the stage has too little parallelism for a large cluster. AQE can coalesce partitions that are too small but does not split ordinary large ones. Databricks recommends `spark.sql.shuffle.partitions = auto` (auto-optimized shuffle), which sets the number from the query plan and input size. Note `auto` is Databricks only: open-source Spark 4.2 rejected it in `ch22_extras.py`.

**Q26. The longest stage of a job has exactly one task. Name four causes.**

??? success "Answer"
    From the Databricks guide: a window function without `PARTITION BY`; an unsplittable input such as a large gzip file; `repartition(1)` or `coalesce(1)`; an expensive UDF on input small enough to land in one partition; the `multiLine` option on JSON or CSV; schema inference on a large file. Adding workers does not help a one-task stage; fix the cause (add `PARTITION BY`, ingest the gzip once into Delta, remove the `coalesce(1)`, `repartition()` before the UDF).

**Q27. The jobs timeline shows long gaps between Spark jobs and the workers are idle. What could the driver be doing?**

??? success "Answer"
    Running non-Spark code (a Python loop over `collect()` results, pandas work), building a huge plan (for example `withColumn()` called in a loop hundreds of times), coordinating too many concurrent queries or threads, or nothing at all (an idle all-purpose cluster). Check the driver load in the cluster metrics. Fixes: move the work into Spark, replace `withColumn` loops with one `select`/`selectExpr`, reduce concurrency or enlarge the driver, use serverless for intermittent work.

**Q28. Find the bug.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (`ch22_answers.py`, 300 string columns, 10 rows)

```python
for c in cols_to_clean:                      # 300 columns
    df = df.withColumn(c, F.trim(F.col(c)))
```

??? success "Answer"
    Each `withColumn` adds a projection to the plan; 300 of them make planning very expensive, which shows up as gaps with no Spark jobs (Databricks: "calling `withColumn()` in a loop creates a very expensive plan"). Build all expressions and apply them in one `select`:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (`ch22_answers.py`)

    ```python
    df = df.select([F.trim(F.col(c)).alias(c) if c in cols_to_clean else F.col(c) for c in df.columns])
    ```

    ```text
    Q28 same rows: True
    Q28 build + optimize plan: withColumn loop 9.8 s, one select 0.6 s
    ```

    Same result; building and optimizing the plan took 9.8 seconds for the loop and 0.6 seconds for the single `select` on this laptop engine (a rerun on a busier machine took 24.4 s and 1.4 s: the gap, not the numbers, is the point), before a single row was read. Databricks' own advice is the same pattern: "Use `selectExpr()` to combine multiple `withColumn()` calls into one expression, or convert the code to SQL".

**Q29. A Python UDF that normalizes city names is the slowest step of a silver job. What are your options, best first?**

??? success "Answer"
    1. Rewrite it with built-in functions (`trim`, `initcap`, `regexp_replace`, a mapping join): built-ins and SQL UDFs are the most efficient, and Photon can run them. 2. If Python is needed, use a pandas UDF: Databricks says they are "up to 100x faster than Python UDFs" thanks to Arrow. 3. If the UDF stage has fewer tasks than cores, `repartition()` before it. Chapter 3, section 3.11 times these variants.

**Q30. A `MERGE` of 10,000 updates into a 5 TB `orders` table takes two hours. Updates only ever concern orders from the last 3 days. What do you change?**

??? success "Answer"
    Add the guaranteed constraint to the `ON` clause (`AND t.order_ts >= current_date() - INTERVAL 3 DAYS`) so only recent files are searched; keep the table clustered on `order_ts` (liquid clustering) so that range maps to few files; enable deletion vectors so matched files are not rewritten in full; run on Photon so dynamic file pruning can skip target files using the source keys; deduplicate the source. Confirm with the `MERGE` metrics in `DESCRIBE HISTORY`.

    **Why:** by default `MERGE` searches the entire table for matches, and without deletion vectors it rewrites every unchanged row of each touched file.

**Q31. You add `AND t.order_ts >= current_date() - INTERVAL 3 DAYS` to a MERGE's `ON` clause. Next week, duplicates appear in silver. Why?**

??? success "Answer"
    An update arrived for an order older than 3 days. The extra predicate is part of the match condition, so the old row did not match, and `WHEN NOT MATCHED THEN INSERT` inserted the update as a new row. Only use pruning predicates that the data guarantees, or handle out-of-window updates separately.

**Q32. `MERGE` into a partitioned table writes thousands of tiny files per run. Why, and what fixes it?**

??? success "Answer"
    Each shuffle task can write a file in every partition it touches, so files multiply by partitions (the Delta best practices page describes exactly this). Optimized writes fix it by shuffling before the write; on Databricks they are always on for `MERGE` ("You can't turn off this functionality"), so if you see this, check which engine wrote the files (open-source Delta, for example), and reconsider partitioning (liquid clustering instead). `spark.sql.shuffle.partitions` also sets how many output files `MERGE` writes.

**Q33. Dynamic file pruning did not apply to a `MERGE` on Databricks. Give three reasons.**

??? success "Answer"
    The compute is not Photon-enabled ("Dynamic file pruning in `MERGE`, `UPDATE`, and `DELETE` statements requires Photon-enabled compute"); the target is below the default thresholds (10 GB, 10 files); the merge condition does not compare a source column with a target column for equality; or the join keys are spread across every file, so there is nothing to skip (cluster the target on the key).

**Q34. After a weekend outage, a streaming job restarts and its first micro-batch runs out of memory. You add `maxFilesPerTrigger = 500` and restart. The same batch fails again. Why?**

??? success "Answer"
    The micro-batch was already planned before the stop, and planned batches must re-run with the same data: "If a microbatch is planned when a stream stops, any change to admission controls does not take effect until after the planned microbatch is completed." Scale up compute once to finish that batch (in rare cases restart with a new checkpoint, which Databricks mentions for failed transactions); later batches use the new limit.

**Q35. What does this print?** A Delta table `bronze_orders` has 10 files of 100 rows each.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (`ch22_streaming.py`, written there as a small helper)

```python
q = (spark.readStream.format("delta").option("maxFilesPerTrigger", "3")
       .table("bronze_orders").writeStream.format("delta")
       .option("checkpointLocation", chk).trigger(availableNow=True).toTable("silver_orders"))
q.awaitTermination()
print([p["numInputRows"] for p in q.recentProgress if p["numInputRows"] > 0])
```

??? success "Answer"
    `[300, 300, 300, 100]` (the section 22.17 run). `availableNow` processes everything available, but in batches of at most 3 files.

**Q36. A team's streaming job runs with no trigger set on an always-on cluster, and the cloud storage bill rose sharply. Explain.**

??? success "Answer"
    With no trigger, Structured Streaming uses `processingTime` with a `0` interval, checking for new data every few milliseconds, which "can generate a high volume of cloud storage API calls per day and result in unexpected charges". Set a `processingTime` interval that matches the latency need, or run on a schedule with `availableNow`.

**Q37. A stateful streaming aggregation spends most of each batch on checkpointing state. What do you configure on Databricks?**

??? success "Answer"
    Use the RocksDB state store (the default from Databricks Runtime 17.3 LTS) and enable changelog checkpointing (`spark.sql.streaming.stateStore.rocksdb.changelogCheckpointing.enabled`, default on from 17.3 LTS), which writes only changed records. Bound the state with a watermark. The production page also mentions asynchronous state checkpointing when checkpointing is the bottleneck.

**Q38. You want to raise `spark.sql.shuffle.partitions` for a running stream with large state. Can you just change it and restart?**

??? success "Answer"
    No: "For Structured Streaming, you can't change this value between query restarts from the same checkpoint location." The number of state partitions is fixed by the checkpoint. Changing it requires a new checkpoint (and reprocessing or rebuilding state), so choose it before the first start.

**Q39. A serverless SQL warehouse shows a Peak Queued Queries value above 0 every morning, and query profiles show no spill. What do you change? What would you change if they showed heavy spill instead?**

??? success "Answer"
    Queueing without spill is a concurrency problem: raise the maximum number of clusters so the autoscaler can add more. Heavy spill (bytes spilled to disk, `DATA_SPILL`) means each query lacks memory: raise the cluster size (for example Medium to Large). Databricks' serverless advice is to start with a larger warehouse and size down.

**Q40. How many clusters should a pro SQL warehouse have for about 40 concurrent queries, by the Databricks rule of thumb? Why might you choose serverless instead?**

??? success "Answer"
    "Databricks recommends one cluster for every 10 concurrent queries" for classic and pro, so about 4 clusters at peak (set as the maximum). Serverless starts in seconds rather than about 4 minutes, and with Intelligent Workload Management it scales up faster and scales down quickly "to minimize costs when demand is low". It still bills while it runs, so idle time before it stops is not free.

**Q41. Find the bug.** An engineer wants to compact only one customer's data in an unpartitioned, unclustered table:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (`ch22_extras.py`; it fails, as the answer shows)

```sql
OPTIMIZE orders WHERE customer_id = 7;
```

??? success "Answer"
    `OPTIMIZE ... WHERE` accepts only predicates on partition (or clustering) columns: "Only filters on partition / clustering key attributes are supported" ([OPTIMIZE](https://docs.databricks.com/aws/en/sql/language-manual/delta-optimize)). Open-source Delta 4.4.1 rejected it too (see `ch22_extras.out`). Run `OPTIMIZE orders` (bin-packing is idempotent, so already compacted files are left alone), or on a liquid table with `customer_id` as a key use `OPTIMIZE orders FULL WHERE ...` (Databricks Runtime 18.1 and above).

**Q42. `DESCRIBE HISTORY` shows an `OPTIMIZE` row with `operationParameters.auto = true` that nobody scheduled. What is it?**

??? success "Answer"
    Auto compaction: it runs synchronously on the writing cluster after a write and is recorded as `OPTIMIZE` with `auto` set to `true`; a manual `OPTIMIZE` has `false`. Section 22.4 shows two such rows produced by 40 small inserts with `delta.autoOptimize.autoCompact` set.

**Q43. A table has 60 columns, and the most common filter is on `loyalty_tier`, column 47. Filters never skip files. Fix it.**

??? success "Answer"
    Statistics are collected only on the first 32 columns by default, so column 47 has none. Either set `delta.dataSkippingStatsColumns` to include `loyalty_tier` (Databricks Runtime 13.3 LTS and above) or move it into the first 32 columns, then run `ANALYZE TABLE t COMPUTE DELTA STATISTICS` (14.3 LTS and above) to recompute stats for existing files. On a Unity Catalog managed table, predictive optimization may also add statistics for frequently filtered columns beyond the first 32.

**Q44. Explain the trade-off of Z-ordering on five columns, and the liquid clustering equivalent.**

??? success "Answer"
    Z-order effectiveness "drops with each extra column": with five columns, each column's values are less co-located, so each filter skips fewer files. Liquid clustering allows at most four keys, and on tables under 10 TB more keys make single-column filters worse. Pick the one to three columns most used in filters; drop a key that is highly correlated with another.

## Sources

- [Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe) (last updated Oct 12, 2026)
- [Auto-enable deletion vectors](https://docs.databricks.com/aws/en/admin/workspace-settings/deletion-vectors) (last updated Sep 11, 2026)
- [Best practices: Delta Lake](https://docs.databricks.com/aws/en/delta/best-practices) (last updated Oct 30, 2026)
- [Cache DataFrames on serverless compute](https://docs.databricks.com/aws/en/compute/serverless/dataframe-cache) (last updated Oct 22, 2026)
- [Configure RocksDB state store on Databricks](https://docs.databricks.com/aws/en/structured-streaming/rocksdb-state-store) (last updated Nov 6, 2026)
- [Configure Structured Streaming batch size on Databricks](https://docs.databricks.com/aws/en/structured-streaming/batch-size) (last updated Sep 16, 2026)
- [Configure Structured Streaming trigger intervals](https://docs.databricks.com/aws/en/structured-streaming/triggers) (last updated Nov 10, 2026)
- [Control data file size](https://docs.databricks.com/aws/en/tables/tune-file-size) (last updated Sep 11, 2026)
- [Cost-based optimizer](https://docs.databricks.com/aws/en/optimizations/cbo) (last updated Oct 12, 2026)
- [Data skipping](https://docs.databricks.com/aws/en/tables/data-skipping) (last updated Oct 20, 2026)
- [Deletion vectors in Databricks](https://docs.databricks.com/aws/en/tables/features/deletion-vectors) (last updated Nov 6, 2026)
- [Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake) (last updated Oct 15, 2026)
- [Diagnose cost and performance issues using the Spark UI](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/) (last updated Oct 12, 2026)
- [Dynamic file pruning](https://docs.databricks.com/aws/en/optimizations/dynamic-file-pruning) (last updated Oct 12, 2026)
- [From Delta Sharing to OpenSharing: what changed, what's next](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next) (Databricks blog, published Nov 5, 2026)
- [Gaps between Spark jobs](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/spark-job-gaps) (last updated Oct 12, 2026)
- [Hints](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-hints) (last updated Oct 12, 2026)
- [June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026)
- [Long Spark stage with one task](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/one-spark-task) (last updated Oct 12, 2026)
- [Low shuffle merge on Databricks](https://docs.databricks.com/aws/en/optimizations/low-shuffle-merge) (last updated Oct 12, 2026)
- [What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/) (last updated Oct 27, 2026)
- [Optimization recommendations on Databricks](https://docs.databricks.com/aws/en/optimizations/) (last updated Oct 12, 2026)
- [OPTIMIZE](https://docs.databricks.com/aws/en/sql/language-manual/delta-optimize) (last updated Nov 2, 2026)
- [Optimize data file layout](https://docs.databricks.com/aws/en/tables/operations/optimize) (last updated Sep 11, 2026)
- [Optimize performance with caching on Databricks](https://docs.databricks.com/aws/en/optimizations/disk-cache) (last updated Oct 22, 2026)
- [Predictive optimization for Unity Catalog managed tables](https://docs.databricks.com/aws/en/optimizations/predictive-optimization) (last updated Nov 6, 2026)
- [Production considerations for Structured Streaming](https://docs.databricks.com/aws/en/structured-streaming/production) (last updated Nov 5, 2026)
- [Query caching](https://docs.databricks.com/aws/en/sql/user/queries/query-caching) (last updated Sep 11, 2026)
- [Query performance insights](https://docs.databricks.com/aws/en/sql/user/queries/performance-insights) (last updated Oct 8, 2026)
- [Query profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile) (last updated Sep 11, 2026)
- [REORG TABLE](https://docs.databricks.com/aws/en/sql/language-manual/delta-reorg-table) (last updated Sep 11, 2026)
- [Skew and spill](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/long-spark-stage-page) (last updated Oct 12, 2026)
- [Skew join optimization using skew hints](https://docs.databricks.com/aws/en/archive/legacy/skew-join) (last updated May 13, 2024)
- [Slow Spark stage with little I/O](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/slow-spark-stage-low-io) (last updated Oct 12, 2026)
- [Spark driver overloaded](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/spark-driver-overloaded) (last updated Oct 12, 2026)
- [Spark memory issues](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/spark-memory-issues) (last updated Oct 12, 2026)
- [Spark SQL performance tuning](https://spark.apache.org/docs/4.2.0/sql-performance-tuning.html)
- [Spark stage high I/O](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/long-spark-stage-io) (last updated Oct 12, 2026)
- [SQL warehouse sizing, scaling, and queuing behavior](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-behavior) (last updated Nov 5, 2026)
- [SQL warehouse types](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-types) (last updated Oct 30, 2026)
- [Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering) (last updated Nov 2, 2026)
- [What are user-defined functions (UDFs)?](https://docs.databricks.com/aws/en/udf/) (last updated Sep 22, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [What is Photon?](https://docs.databricks.com/aws/en/compute/photon) (last updated Sep 11, 2026)
- [What is predictive I/O?](https://docs.databricks.com/aws/en/optimizations/predictive-io) (last updated Oct 12, 2026)
- [When to partition tables on Databricks](https://docs.databricks.com/aws/en/tables/partitions) (last updated Sep 11, 2026)
