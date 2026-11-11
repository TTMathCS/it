# 11. Structured Streaming for data engineers

*Red Rock Supply's order files never stop arriving, and a data engineer's job is to load each one exactly once, in
order, without rereading everything every hour. Structured Streaming is the Spark engine that does this. It powers
Auto Loader, streaming tables in Lakeflow pipelines and most bronze-to-silver jobs on Databricks. This chapter runs real
streams on Apache Spark 4.2 with Delta Lake 4.4.1: JSON order files dropped into a folder in controlled batches, a
Delta table as the sink, and every piece an interviewer pokes at: the checkpoint folder file by file, triggers and what
they cost, output modes, watermarks with a late order that is counted and a later one that is dropped, stateful
operators and their state, `foreachBatch` with `MERGE`, and what "exactly-once" really rests on. Most streaming
interview questions are "what happens when" questions, so you will see the failures too.*

!!! abstract "In this chapter"
    **You will learn:**

    - the model: an unbounded input table, a result table, micro-batches and incremental execution
    - `readStream` and `writeStream`, the sources (files, Delta tables, Kafka, Auto Loader) and the sinks
    - what is inside a checkpoint (`offsets/`, `commits/`, `metadata`, `sources/`, `state/`), listed from a real run,
      why each query needs its own, and which query changes break a restart
    - triggers (default, `processingTime`, `availableNow`, the deprecated `once`, real-time mode, continuous) and the
      cost trade-off; rate limits with `maxFilesPerTrigger` and `maxBytesPerTrigger`
    - output modes (append, update, complete) and which queries allow which
    - event time, watermarks and late data, in a deterministic run
    - reading a Delta table as a stream: the append-only rule, `skipChangeCommits`, `ignoreDeletes`, the change data
      feed
    - `foreachBatch` with `MERGE`, and idempotent writes with `txnAppId` and `txnVersion`
    - exactly-once end to end: replayable source, checkpoint, idempotent sink
    - stateful operators: tumbling, sliding and session windows, deduplication, stream-static and stream-stream joins
    - the state store (RocksDB on Databricks), reading state, and why state grows
    - monitoring with `lastProgress`, `StreamingQueryListener` and observable metrics

    **You need:** [3. Apache Spark](03-Apache-Spark.md) (DataFrames, lazy evaluation),
    [4. Delta Lake](04-Delta-Lake.md) (the transaction log), [7. The medallion architecture](07-Medallion-Architecture.md)
    and [9. Building silver](09-Building-Silver.md) (streaming reads of bronze, `MERGE`, Change Data Feed).

    **Levels:** sections 11.1 to 11.4 beginner, 11.5 to 11.10 intermediate, 11.11 to 11.13 expert.

## 11.1 The model: an unbounded table, processed in micro-batches

*Level: beginner.*

Red Rock Supply's web shop writes order events as JSON files into a landing folder, a few files an hour. A batch job
that reads the whole folder every hour wastes more time each day, and a job that tries to remember "which files did I
already load" in a control table is code you have to write, test and get right after every crash.

Structured Streaming solves this with one idea. The Apache Spark guide puts it this way: "treat a live data stream as
a table that is being continuously appended", then "express your streaming computation as standard batch-like query
as on a static table, and Spark runs it as an *incremental* query on the *unbounded* input table"
([Structured Streaming Programming Guide, getting started](https://spark.apache.org/docs/4.2.0/streaming/getting-started.html)).
Three terms follow from that:

- **Input table**: every new order event is a new row appended to an endless (unbounded) table.
- **Result table**: what your query (a filter, a cast, a `groupBy`) would return over the input table so far.
- **Incremental execution**: Spark never recomputes the result from scratch. Each time it runs, it reads only the
  rows that arrived since the last run, combines them with what it kept from before (the **state**, for aggregations
  and joins), and writes the changed part of the result to a **sink** (a Delta table, Kafka, a function).

By default each run is a **micro-batch**: a small, ordinary Spark job over the new rows. Databricks calls micro-batch
mode the default and describes it as "designed for analytical pipelines and extract, transform, and load (ETL)
workloads", with latency "measured in seconds or minutes". Databricks also has **real-time mode**, which "processes
records as they arrive, with end-to-end latency as low as five milliseconds", for operational workloads such as fraud
detection; both modes use the same APIs
([Structured Streaming concepts](https://docs.databricks.com/aws/en/structured-streaming/concepts)).

"Streaming" does not mean "always running". The most common data engineering use is a stream that starts on a
schedule, processes everything new, and stops (section 11.4). You get incremental loading and exactly-once
bookkeeping without writing any of it yourself.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Three micro-batches on a time line. Each one writes offsets N to the checkpoint, reads the new files, writes to the sink, then writes commits N. The checkpoint folder holds metadata, offsets, commits, sources and state.">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="20" y="28" width="180" height="28" rx="4"/>
<rect x="230" y="28" width="180" height="28" rx="4"/>
<rect x="440" y="28" width="180" height="28" rx="4"/>
<rect x="20" y="78" width="180" height="118" rx="6"/>
<rect x="230" y="78" width="180" height="118" rx="6"/>
<rect x="440" y="78" width="180" height="118" rx="6"/>
<line x1="110" y1="56" x2="110" y2="74"/><line x1="320" y1="56" x2="320" y2="74"/><line x1="530" y1="56" x2="530" y2="74"/>
<line x1="20" y1="214" x2="610" y2="214"/>
<rect x="20" y="236" width="600" height="56" rx="6"/>
<line x1="110" y1="196" x2="110" y2="232" stroke-dasharray="4 3"/>
<line x1="320" y1="196" x2="320" y2="232" stroke-dasharray="4 3"/>
<line x1="530" y1="196" x2="530" y2="232" stroke-dasharray="4 3"/>
</g>
<g fill="currentColor">
<path d="M106,70 L110,78 L114,70 Z"/><path d="M316,70 L320,78 L324,70 Z"/><path d="M526,70 L530,78 L534,70 Z"/>
<path d="M610,210 L620,214 L610,218 Z"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="320" y="18" font-size="14">New order files land in the folder over time</text>
<text x="110" y="47">orders_01.json</text><text x="320" y="47">orders_02.json</text><text x="530" y="47">orders_03.json</text>
<text x="110" y="98" font-size="14">micro-batch 0</text><text x="320" y="98" font-size="14">micro-batch 1</text><text x="530" y="98" font-size="14">micro-batch 2</text>
<text x="110" y="122">1. write offsets/0</text><text x="320" y="122">1. write offsets/1</text><text x="530" y="122">1. write offsets/2</text>
<text x="110" y="142">2. read the new rows</text><text x="320" y="142">2. read the new rows</text><text x="530" y="142">2. read the new rows</text>
<text x="110" y="162">3. write to the sink</text><text x="320" y="162">3. write to the sink</text><text x="530" y="162">3. write to the sink</text>
<text x="110" y="182">4. write commits/0</text><text x="320" y="182">4. write commits/1</text><text x="530" y="182">4. write commits/2</text>
<text x="600" y="232" text-anchor="end">time</text>
<text x="320" y="258">Checkpoint: metadata (query id), offsets/N (input planned for batch N),</text>
<text x="320" y="280">commits/N (batch N done), sources/0 (files seen), state/ (stateful queries only)</text>
</g>
</svg>
<figcaption>Figure 11.1. Each micro-batch records what it is about to read before it runs and records that it finished after the sink write. A restart reads the checkpoint and continues from there.</figcaption>
</figure>

!!! tip "In the interview"
    **"What is Structured Streaming?"** The Spark API for incremental processing: you write a normal DataFrame or
    SQL query, and Spark treats the source as an unbounded table and runs the query repeatedly over only the new data,
    usually as micro-batches. A checkpoint records which input each batch read and which batches finished, so a
    restart continues where it stopped. On Databricks it also runs Auto Loader and the streaming tables of Lakeflow
    pipelines (formerly Delta Live Tables,
    [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)).

## 11.2 readStream and writeStream: a first stream

*Level: beginner.*

A streaming query has three parts: a **source** read with `spark.readStream`, ordinary transformations, and a
**sink** written with `df.writeStream`, which returns a running `StreamingQuery` instead of a result.

The local examples use a landing folder of Red Rock Supply order files. Each file is written under a hidden temporary
name and then renamed into place, because Spark's file source reads files "in the order of file modification time" and
"the files must be atomically placed in the given directory, which in most file systems, can be achieved by file move
operations" ([Spark: APIs on DataFrames and Datasets](https://spark.apache.org/docs/4.2.0/streaming/apis-on-dataframes-and-datasets.html)).

### A file stream needs a schema, and actions do not work

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
ORDER_SCHEMA = ("order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING, "
                "amount DECIMAL(10,2), currency STRING, "
                "items ARRAY<STRUCT<product_id: INT, qty: INT, unit_price: DECIMAL(10,2)>>")

spark.readStream.format("json").load(landing)          # no schema: fails

orders = (spark.readStream
          .format("json")
          .schema(ORDER_SCHEMA)
          .load(landing))
print("isStreaming:", orders.isStreaming)
orders.count()                                         # an action: fails
```

```text
error: Schema must be specified when creating a streaming source DataFrame. If some files already exist in the directory, then depending on the file format you may be able to create a static DataFrame on that directory with 'spark.read.load(directory)' and infer schema from it.
isStreaming: True
count() error: Queries with streaming sources must be executed with writeStream.start(), or from a streaming table or flow definition within a Spark Declarative Pipeline.; FileSource[...
```

A batch read can infer a schema by sampling files; a stream cannot, because the files that will define the schema have
not arrived yet. (Auto Loader on Databricks adds schema inference and evolution for streams; that is chapter 8.)
`count()`, `show()` and `collect()` are actions that return one answer, which makes no sense for an endless table;
you see streaming results only through a sink.

### Three scheduled runs into a Delta table

The function below is what a scheduled job would run: read everything new, append it to the Delta table
`bronze_orders` (on Databricks, `shop.bronze.orders`), stop. It adds the source file name from the hidden `_metadata`
column, as chapter 8 does for bronze.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql import functions as F

def run(**reader_opts):
    src = spark.readStream.format("json").schema(ORDER_SCHEMA)
    for k, v in reader_opts.items():
        src = src.option(k, v)
    df = src.load(landing).select("*",
                                  F.col("_metadata.file_name").alias("_source_file"),
                                  F.current_timestamp().alias("_ingest_ts"))
    q = (df.writeStream
         .format("delta")
         .option("checkpointLocation", checkpoint)
         .trigger(availableNow=True)
         .toTable("bronze_orders"))
    q.awaitTermination()
    batches = [(p["batchId"], p["numInputRows"]) for p in q.recentProgress]
    print(f"run: (batchId, rows) = {batches}; "
          f"bronze_orders has {spark.read.table('bronze_orders').count()} rows")
    return q

run()                                # orders_2026-03-01_01.json has landed (3 orders)
run()                                # nothing new
# orders_2026-03-01_02.json and _03.json land (2 orders each)
q = run(maxFilesPerTrigger=1)        # one file per micro-batch
```

```text
run: (batchId, rows) = [(0, 3)]; bronze_orders has 3 rows
run: (batchId, rows) = [(1, 0)]; bronze_orders has 3 rows
run: (batchId, rows) = [(1, 2), (2, 2)]; bronze_orders has 7 rows
```

```text
+--------+-----------+-------------------+-------+------+-------------------------+
|order_id|customer_id|order_ts           |status |amount|_source_file             |
+--------+-----------+-------------------+-------+------+-------------------------+
|1001    |7          |2026-03-01 10:15:00|PLACED |59.90 |orders_2026-03-01_01.json|
|1002    |8          |2026-03-01 11:00:00|PLACED |120.00|orders_2026-03-01_01.json|
|1003    |9          |2026-03-01 12:30:00|PLACED |45.50 |orders_2026-03-01_01.json|
|1004    |7          |2026-03-01 13:05:00|PLACED |35.50 |orders_2026-03-01_02.json|
|1001    |7          |2026-03-01 13:20:00|SHIPPED|59.90 |orders_2026-03-01_02.json|
|1005    |10         |2026-03-01 14:10:00|PLACED |80.00 |orders_2026-03-01_03.json|
|1002    |8          |2026-03-01 14:45:00|SHIPPED|120.00|orders_2026-03-01_03.json|
+--------+-----------+-------------------+-------+------+-------------------------+
```

Read the three lines slowly. The first run read the 3 orders of the first file as batch 0. The second run found
nothing: its progress report shows batch 1 with 0 rows, nothing was written, and no batch 1 was committed (the next
run reused the number). The third run read two new files as two micro-batches because of `maxFilesPerTrigger=1`. No
file was read twice, and you wrote no bookkeeping code. Bronze keeps both events of order 1001 (`PLACED` and
`SHIPPED`): bronze is an append-only history, and silver (chapter 9) picks the latest.

The same ingestion in Databricks SQL is a streaming table. The `STREAM` keyword asks for an incremental read;
`read_files` here uses Auto Loader:

*Databricks only, not run here. Syntax from [Load data in pipelines](https://docs.databricks.com/aws/en/ldp/load).*

```sql
CREATE OR REFRESH STREAMING TABLE shop.bronze.orders
AS SELECT * FROM STREAM read_files(
  '/Volumes/shop/bronze/landing/orders/',
  format => 'json'
);
```

### Streaming sources

| Source | How you read it | Notes |
| --- | --- | --- |
| Files (JSON, CSV, Parquet, ORC, text) | `spark.readStream.format("json").schema(...).load(path)` | Open-source file source; replayable; needs a schema |
| Auto Loader | `format("cloudFiles")` | Databricks only; file discovery state kept in RocksDB in the checkpoint; chapter 8 |
| Delta table | `spark.readStream.table("shop.bronze.orders")` | Append-only expectation; section 11.7 |
| Kafka | `format("kafka")` | Offsets per partition; `key` and `value` arrive as binary |
| Rate, socket | `format("rate")`, `format("socket")` | For testing only; the socket source is not fault-tolerant |

Auto Loader, in one paragraph: it "provides a Structured Streaming source called `cloudFiles`" that "automatically
processes new files as they arrive", and as files are discovered "their metadata is persisted in a scalable key-value
store (RocksDB) in the *checkpoint location*" so that data "is processed exactly once"
([What is Auto Loader?](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/)). Everything in
this chapter about checkpoints, triggers and sinks applies to it unchanged. Its own options (schema inference and
evolution, the rescued data column, file notification mode) are in
[chapter 8](08-Bronze-Ingestion.md).

**Kafka.** No Kafka broker runs in this environment, so the Kafka code is copied from the Databricks page and labeled.
The reader returns `key` and `value` as `binary` plus `topic`, `partition`, `offset`, `timestamp` and `timestampType`;
you cast `value` to a string and parse it. For scheduled loads Databricks recommends "Kafka with
`Trigger.AvailableNow`", and the rate limit for Kafka is `maxOffsetsPerTrigger`
([Connect to Apache Kafka](https://docs.databricks.com/aws/en/structured-streaming/kafka);
[batch size](https://docs.databricks.com/aws/en/structured-streaming/batch-size)).

*Databricks only, not run here (no Kafka broker). Syntax from [Connect to Apache Kafka](https://docs.databricks.com/aws/en/structured-streaming/kafka).*

```python
from pyspark.sql.functions import from_json, col

value_schema = "order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING, amount DECIMAL(10,2)"
orders = (spark.readStream
          .format("kafka")
          .option("kafka.bootstrap.servers", "<bootstrap-server>:9092")
          .option("subscribe", "orders")
          .option("startingOffsets", "latest")
          .load()
          .select(from_json(col("value").cast("string"), value_schema).alias("v"))
          .select("v.*"))

(orders.writeStream
   .format("delta")
   .option("checkpointLocation", "/Volumes/shop/bronze/checkpoints/orders_kafka")
   .trigger(availableNow=True)
   .toTable("shop.bronze.orders_kafka"))
```

### Sinks

- **Delta table**: `writeStream.toTable(name)` (or `.format("delta").start(path)`). The normal choice; exactly-once
  (section 11.9).
- **Kafka**: `format("kafka")` with a `topic`. Spark lists the Kafka sink as fault-tolerant "at-least-once".
- **`foreachBatch`**: your function receives each micro-batch as a DataFrame; used for `MERGE` and for several
  outputs (section 11.8).
- **`console` and `memory`**: for tests. Databricks notes that some sinks, such as the `memory` sink and notebook
  `display()`, create a temporary checkpoint when you give none, which does not "ensure any fault tolerance or data
  consistency guarantees"
  ([Structured Streaming checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints)).

## 11.3 Checkpoints: what is inside, and why each query needs its own

*Level: beginner.*

The checkpoint is the stream's memory. Databricks lists what it holds: **offsets** ("the source offsets processed in
each micro-batch"), **commits** ("a record of which micro-batches have been committed to the sink, enabling
exactly-once semantics"), **state** (for aggregations, joins, deduplication and custom stateful operators) and
**metadata** ("the unique query ID")
([Structured Streaming checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints)). Here is the
real folder after the three runs above (the listing hides Hadoop's `.crc` checksum files):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
metadata
commits/
commits/0
commits/1
commits/2
offsets/
offsets/0
offsets/1
offsets/2
sources/
sources/0/
sources/0/0
sources/0/1
sources/0/2
--- metadata
{"id":"cdb53715-b6e3-48d5-b804-4d14ca0d1757"}
--- offsets/2
v1
{"batchWatermarkMs":0,"batchTimestampMs":1794380001439,"conf":{"spark.sql.streaming.stateStore.providerClass":"org.apache.spark.sql.execution.streaming.state.HDFSBackedStateStoreProvider", ... ,"spark.sql.shuffle.partitions":"4", ...}}
{"logOffset":2}
--- commits/2
v1
{"nextBatchWatermarkMs":0}
--- sources/0/2
v1
{"path":"file:///.../landing/orders/orders_2026-03-01_03.json","timestamp":1794376347406,"batchId":2}
```

(The `offsets/2` line is shortened with `...`; the full line is in `src/ch11/s1_basics.out`.) What each file means:

| File | Written | Holds |
| --- | --- | --- |
| `metadata` | once, at the first start | the query `id`, which stays the same across restarts |
| `offsets/N` | before batch N runs | the source position batch N will read up to (`logOffset` for files, offsets for Kafka, table version for Delta), the watermark, and the SQL settings fixed for this query, such as `spark.sql.shuffle.partitions` |
| `commits/N` | after batch N's sink write | that batch N finished, and the watermark for the next batch |
| `sources/0/N` | file source only | the files assigned to batch N |
| `state/` | stateful queries only | the state store files (section 11.12) |

The order matters. Offsets are written first (a **write-ahead log**), commits last. If the job dies between the two,
the restart finds an `offsets/N` without a `commits/N` and runs batch N again with exactly the same input. Databricks
states the rule from the other side: "Structured Streaming requires idempotent micro-batches", and micro-batches "must
contain the same data on repeat executions"
([triggers](https://docs.databricks.com/aws/en/structured-streaming/triggers);
[batch size](https://docs.databricks.com/aws/en/structured-streaming/batch-size)). That is also why a rate-limit
change does not apply to a batch that was already planned.

The `conf` in the offsets file explains a classic surprise. Databricks: "The number of shuffle partitions is fixed at
the time the checkpoint is created. Changing `spark.sql.shuffle.partitions` has no effect on a streaming query that
already has a checkpoint" (Databricks Runtime 18 LTS and above can repartition state on demand)
([What is stateful streaming?](https://docs.databricks.com/aws/en/structured-streaming/stateful-streaming)).

### Delete the checkpoint and the stream starts over

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
shutil.rmtree(checkpoint)
run()
spark.sql("""SELECT order_id, status, count(*) AS copies FROM bronze_orders
             GROUP BY order_id, status ORDER BY order_id, status""").show()
```

```text
run: (batchId, rows) = [(0, 7)]; bronze_orders has 14 rows
+--------+-------+------+
|order_id|status |copies|
+--------+-------+------+
|1001    |PLACED |2     |
|1001    |SHIPPED|2     |
|1002    |PLACED |2     |
|1002    |SHIPPED|2     |
|1003    |PLACED |2     |
|1004    |PLACED |2     |
|1005    |PLACED |2     |
+--------+-------+------+
```

A new checkpoint means a new query: batch 0 again, all 7 old rows read again, and every order now appears twice in
bronze. "When you delete the files in a checkpoint directory or change to a new checkpoint location, the next run of
the query begins fresh" ([checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints)). A Delta
source is the same: a new checkpoint starts from "a complete snapshot of the table" by default
([Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)).

### One checkpoint per query

"Each query must have a different checkpoint location. Multiple queries should never share the same location"
([checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints)). Two runs show why. First, a
second query that writes to a new table `orders_copy` reuses the checkpoint of the query that loaded `bronze_orders`;
second, the same checkpoint is started twice at once:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
q2 = (spark.readStream.format("json").schema(ORDER_SCHEMA).load(landing)
      .writeStream.format("delta").option("checkpointLocation", shared)   # bronze's checkpoint
      .trigger(availableNow=True).toTable("orders_copy"))
q2.awaitTermination()
print("orders_copy rows:", spark.read.table("orders_copy").count())

live = (...).option("checkpointLocation", f"{base}/chk/live").trigger(processingTime="5 seconds").toTable("orders_live")
live.processAllAvailable()
second = (...).option("checkpointLocation", f"{base}/chk/live").trigger(processingTime="5 seconds").toTable("orders_live_2")
print("same checkpoint started twice: first isActive =", live.isActive, "| second isActive =", second.isActive)
```

```text
orders_copy rows: 0 | batches with data: []
same checkpoint started twice: first isActive = False | second isActive = True
```

The copy query believed every file was already done, because the checkpoint said so: `orders_copy` stayed empty and
no error was raised. Starting the same checkpoint twice did not fail either: Spark stopped the first run, because
`spark.sql.streaming.stopActiveRunOnRestart` defaults to `true` ("we will stop the old streaming query run to start
the new one", [Spark configuration](https://spark.apache.org/docs/4.2.0/configuration.html)). Both mistakes are silent.

On Databricks, put checkpoints in a Unity Catalog volume (the docs use `/Volumes/catalog/schema/volume/path`), one
folder per query. A folder next to the table such as `<table-name>/_checkpoints` is also safe, because `VACUUM` "skips
any directories that begin with `_`"
([Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)).

### Which query changes a checkpoint survives

The checkpoint page gives the rules. In short:

| Change between restarts | Allowed? |
| --- | --- |
| Add or remove a filter; change a projection with the same output schema | Allowed |
| Change rate limits (`maxFilesPerTrigger`, `maxOffsetsPerTrigger`) or the trigger interval | Allowed |
| Change the number or type of sources | Not allowed by default (sources are identified by position); with source evolution (Databricks Runtime 18.2 and above, every source named with `.name()`, turned on when the checkpoint is created, not on an existing one), you can reorder, add and remove sources |
| Change the Kafka topic or the input path | Generally not allowed, results unpredictable |
| Change the output directory of a file sink | Not allowed |
| Change a stateful operation: grouping keys, aggregates, dedup keys, join keys or type | Not allowed |

Section 11.12 shows the real error when an aggregation changes.

!!! tip "In the interview"
    **"Our stream restarted and reprocessed everything. Why?"** It started with an empty or different checkpoint: the
    folder was deleted, the path changed (for example a path built from a run id or a new environment), or no
    `checkpointLocation` was set and a temporary one was used. A new checkpoint is a new query, so a file source reads
    every file again and a Delta source starts from the full snapshot. Fix: one fixed, durable checkpoint per query,
    and never share one between queries.

## 11.4 Triggers, rate limits and cost

*Level: beginner.*

The trigger decides when the next micro-batch starts. The Databricks trigger page lists the modes
([Configure Structured Streaming trigger intervals](https://docs.databricks.com/aws/en/structured-streaming/triggers)):

| Trigger | Python | Behavior | Use |
| --- | --- | --- | --- |
| Unspecified (default) | none | "Equivalent to processingTime trigger with 0 ms intervals"; Databricks quotes "3-5 second latency" | General streaming |
| Processing time | `.trigger(processingTime='10 seconds')` | A micro-batch at most every interval; if a batch runs long, the next starts right after; no new data, no batch | Balance cost and latency |
| Available now | `.trigger(availableNow=True)` | Processes everything available at start, possibly in several batches, then stops | Scheduled incremental batch |
| Once | `.trigger(once=True)` | One batch with everything, then stops | Deprecated in Databricks Runtime 11.3 LTS and above; use `availableNow` |
| Real-time mode | `.trigger(realTime='5 minutes')` | Databricks only; the interval is the length of a long-running batch and the checkpoint interval, records are processed as they arrive | Sub-second operational workloads |
| Continuous | `.trigger(continuous='1 second')` | Apache Spark's experimental continuous processing | "Not supported" on Databricks; use real-time mode |

Why `availableNow` replaced `once`: `once` puts everything into one batch, while `availableNow` splits the backlog by
the source's rate limits (for example `maxFilesPerTrigger`) and, the Spark guide adds, advances the watermark per batch
and runs a final no-data batch if needed, which keeps state small and lets stateful results come out before the query
stops ([Spark: APIs on DataFrames and Datasets](https://spark.apache.org/docs/4.2.0/streaming/apis-on-dataframes-and-datasets.html)).
You will see that final no-data batch in section 11.6.

Here are a running `processingTime` query, the deprecated `once`, and `continuous` on a file source:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
live = (bronze.writeStream.format("delta")
        .queryName("bronze_orders_live")
        .option("checkpointLocation", chk2)
        .trigger(processingTime="2 seconds")
        .toTable("bronze_orders_live"))
live.processAllAvailable()          # wait until the current backlog is in (a testing helper)
print("active queries:", [s.name for s in spark.streams.active])
# ... a new file lands ...
live.processAllAvailable()
print("rows in bronze_orders_live:", spark.read.table("bronze_orders_live").count())
live.stop()                          # a processingTime query runs until you stop it

q1 = bronze.writeStream.format("delta").option("checkpointLocation", chk3).trigger(once=True).toTable("bronze_once")
q1.awaitTermination()

orders.writeStream.format("console").option("checkpointLocation", chk4).trigger(continuous="1 second").start()
```

```text
active queries: ['bronze_orders_live']
rows in bronze_orders_live: 8
after stop, isActive: False | active queries: 0
batches with once=True: [(0, 8)]
error: Continuous processing does not support StreamingRelation operations.; FileSource[...]
```

`processAllAvailable()` is, in PySpark's own docstring, "intended for testing". Continuous processing in open-source
Spark supports only a few sources (the file source is not one of them). Databricks does not support it and points to
real-time mode instead.

### The cost trade-off

A default trigger polls the source all the time. Databricks warns that it "checks for new data every few
milliseconds. This can generate a high volume of cloud storage API calls per day and result in unexpected charges
from your cloud provider" ([triggers](https://docs.databricks.com/aws/en/structured-streaming/triggers)). The choice
is a trade between latency and money:

- Order files arrive a few times an hour and the business reads the dashboard in the morning: a scheduled job with
  `availableNow` (hourly or daily). The cluster exists only while it runs.
- Fresh data within a minute matters: an always-on stream with `processingTime='1 minute'`, on jobs compute, scheduled
  as a continuous job in Lakeflow Jobs (formerly Databricks Jobs,
  [rename note](https://docs.databricks.com/aws/en/release-notes/product/2025/june)). Databricks: "Don't run Structured Streaming workloads using all-purpose compute", schedule
  "using `Continuous` mode", and "Don't enable autoscaling for Structured Streaming jobs"
  ([Production considerations for Structured Streaming](https://docs.databricks.com/aws/en/structured-streaming/production)).
- Sub-second decisions (fraud): real-time mode, which "requires dedicated compute resources"
  ([Real-time mode concepts](https://docs.databricks.com/aws/en/structured-streaming/real-time/)).

On **serverless** notebooks and jobs, only `Trigger.AvailableNow()` and the deprecated `Trigger.Once()` are
supported; any other trigger, including the default, raises `INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED`. For continuous
streaming on serverless, use a Lakeflow pipeline in continuous mode
([Serverless compute limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations)). You can change
the trigger between runs with the same checkpoint
([triggers](https://docs.databricks.com/aws/en/structured-streaming/triggers)).

### Rate limits

Rate limits (Databricks calls them admission controls) cap how much one micro-batch reads, so a large backlog does not
become one huge batch that spills or runs out of memory:

| Option | Source | Default and rule (from the cited page) |
| --- | --- | --- |
| `maxFilesPerTrigger` | Delta table | 1000 ([Delta streaming](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)) |
| `maxBytesPerTrigger` | Delta table | Not set; a "soft max" that a batch may exceed to make progress. With both set, the batch stops at whichever limit is reached first |
| `cloudFiles.maxFilesPerTrigger`, `cloudFiles.maxBytesPerTrigger` | Auto Loader | Same options as Delta ([batch size](https://docs.databricks.com/aws/en/structured-streaming/batch-size)) |
| `maxFilesPerTrigger`, `maxBytesPerTrigger` | Open-source file source | No max by default; the two cannot be set together ([Spark guide](https://spark.apache.org/docs/4.2.0/streaming/apis-on-dataframes-and-datasets.html)) |
| `maxOffsetsPerTrigger` | Kafka | Per Kafka source ([batch size](https://docs.databricks.com/aws/en/structured-streaming/batch-size)) |

You saw `maxFilesPerTrigger=1` split two files into two batches above; section 11.7 shows it on a Delta source.
Changing a rate limit between runs is allowed.

!!! tip "In the interview"
    **"How would you run a streaming ingestion cheaply?"** If the business does not need data within minutes, run the
    stream as a scheduled job with `trigger(availableNow=True)`: it processes everything new in rate-limited batches
    and stops, with the same checkpoint and exactly-once bookkeeping as an always-on stream. `Trigger.Once` is
    deprecated for this. The default trigger polls continuously and can produce large cloud storage API bills.

## 11.5 Output modes

*Level: intermediate.*

The **output mode** says which rows of the result table a trigger writes to the sink. For a plain
select-filter-cast query it does not matter: every new input row produces one output row once. It matters when a row
of the result can change, which happens with aggregations. Databricks defines the three modes
([Select an output mode for Structured Streaming](https://docs.databricks.com/aws/en/structured-streaming/output-mode)):

- **Append** (the default): "operators only emit rows that don't change in future triggers". For an aggregation that
  means a row is written once, when the watermark says it is final.
- **Update**: "operators emit all rows that changed during the trigger, even if the emitted record might change in a
  subsequent trigger".
- **Complete**: "only works with streaming aggregations"; all rows ever produced are emitted every trigger.

Which queries allow which mode (the first four rows are from the Spark guide's compatibility matrix; the matrix has no
session window row, see the last row):

| Query | Append | Update | Complete |
| --- | --- | --- | --- |
| No aggregation (select, filter) | Yes | Yes | No |
| Aggregation on event time with a watermark | Yes | Yes | Yes (state never dropped) |
| Other aggregations (no watermark) | No | Yes | Yes |
| Joins (Spark's matrix lists joins as append only; Databricks: "Joins only support the append output mode") | Yes | No | No |
| Session window aggregation | Yes (the Spark guide restricts only update mode) | No (Spark guide: "Update mode" as output mode is not supported) | Yes (from the run in 11.11, not from a doc page) |

And the sink has a say too: "Delta Lake, which backs all Unity Catalog managed tables, supports append and complete
modes but not update mode", while Kafka supports all three
([output mode](https://docs.databricks.com/aws/en/structured-streaming/output-mode)). Four mistakes, run:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
plain_agg = stream().groupBy("customer_id").agg(F.count("*").alias("orders"))
plain_agg.writeStream.format("delta").outputMode("append").option(...).toTable("bad1")
plain_agg.writeStream.format("delta").outputMode("update").option(...).toTable("bad2")
stream().orderBy("order_ts").writeStream.format("console").option(...).start()
stream().limit(5).writeStream.format("console").outputMode("update").option(...).start()
```

```text
append, no watermark: [STREAMING_OUTPUT_MODE.UNSUPPORTED_OPERATION] Invalid streaming output mode: append. This output mode is not supported for streaming aggregations without watermark on streaming DataFrames/DataSets. SQLSTATE: 42KDE
update into a Delta sink: [DELTA_UNSUPPORTED_OUTPUT_MODE] Data source org.apache.spark.sql.delta.sources.DeltaDataSource does not support Update output mode
sort without aggregation: Sorting is not supported on streaming DataFrames/Datasets, unless it is on aggregated DataFrame/Dataset in Complete output mode; ~Sort [...]
limit in update mode: Limits are not supported on streaming DataFrames/Datasets in Update output mode; ~LocalLimit 5 [...]
```

So a running "orders per customer" total into a Delta table has two honest options: `complete` (rewrite the whole
small table every trigger), or `update` through `foreachBatch` with a `MERGE` (section 11.8). Databricks also notes that
complete mode "can perform poorly as data scales" and suggests materialized views for that kind of result.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 270" role="img" aria-label="State of a 10-minute windowed order count after run 2 of the watermark demo, and what each output mode writes: append writes only the window that became final, update writes the windows that changed, complete writes all windows.">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="20" y="40" width="250" height="150" rx="6"/>
<line x1="20" y1="72" x2="270" y2="72"/>
<rect x="330" y="30" width="290" height="62" rx="6"/>
<rect x="330" y="104" width="290" height="62" rx="6"/>
<rect x="330" y="178" width="290" height="80" rx="6"/>
<line x1="270" y1="115" x2="324" y2="61"/><line x1="270" y1="115" x2="324" y2="135"/><line x1="270" y1="115" x2="324" y2="215"/>
</g>
<g fill="currentColor" font-size="13">
<text x="145" y="61" text-anchor="middle" font-size="14">State after run 2</text>
<text x="34" y="96">10:00-10:10  3 orders (changed)</text>
<text x="34" y="120">10:10-10:20  1 order (unchanged)</text>
<text x="34" y="144">10:20-10:30  1 order (new)</text>
<text x="34" y="176">watermark now 10:16</text>
<text x="342" y="54" font-size="14">Append writes</text>
<text x="342" y="78">10:00-10:10 = 3 (final: 10:10 &lt; 10:16)</text>
<text x="342" y="128" font-size="14">Update writes</text>
<text x="342" y="152">10:00-10:10 = 3 and 10:20-10:30 = 1</text>
<text x="342" y="202" font-size="14">Complete writes</text>
<text x="342" y="226">all three windows, every trigger,</text>
<text x="342" y="246">and never drops old state</text>
</g>
</svg>
<figcaption>Figure 11.2. One state, three output modes. The numbers are from the run in section 11.6.</figcaption>
</figure>

!!! tip "In the interview"
    **"Append, update or complete?"** Append writes each result row once, when it can no longer change, so an
    aggregation in append mode needs a watermark and its output is delayed by the watermark. Update writes rows that
    changed this trigger (lowest latency, but the sink must handle updates; a Delta sink does not, so you use
    `foreachBatch` with `MERGE`). Complete rewrites the whole result every trigger and keeps all state forever, so it
    is only for small aggregates.

## 11.6 Event time, watermarks and late data

*Level: intermediate.*

**Processing time** is when Spark sees a row. **Event time** is when the thing happened, a column in the data
(`order_ts`). Reports group by event time: "orders between 10:00 and 10:10" means orders placed then, not files that
happened to arrive then. Events arrive late and out of order (a phone offline, an upstream retry), so a window can
receive rows long after it ended.

A streaming aggregation must keep each open window in state until it is sure no more rows will come. Without a limit,
state grows forever. A **watermark** is that limit. `withWatermark("order_ts", "10 minutes")` tells Spark: the
watermark is the latest event time seen minus 10 minutes; a window that ends before the watermark is final, its state
is dropped, and rows for it are no longer accepted. The guarantee works in one direction only: data less late than the
threshold "is guaranteed to be aggregated", while later data "is not guaranteed to be dropped; it may or may not get
aggregated" ([Spark guide](https://spark.apache.org/docs/4.2.0/streaming/apis-on-dataframes-and-datasets.html)).

Two mechanics decide what really happens, and both explain interview puzzles:

1. The watermark is computed at the **end** of a micro-batch, from the maximum event time in that batch, and is used
   by the **next** batch. Within one batch, every row is judged against the watermark from before the batch.
2. So the result can depend on where batch boundaries fall. A late row in the same batch as the newer rows is
   accepted; the same row one batch later may be dropped.

The run below makes that deterministic: one file per `availableNow` run, a 10-minute tumbling window (a **tumbling
window** is a fixed-size, non-overlapping interval: 10:00-10:10, 10:10-10:20, ...), a 10-minute watermark, and the
same query written in all three output modes. Each mode writes to a `foreachBatch` function that prints what it
received.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
windowed = (stream()
            .withWatermark("order_ts", "10 minutes")
            .groupBy(F.window("order_ts", "10 minutes"))
            .agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue"))
            .select(F.date_format("window.start", "HH:mm").alias("start"),
                    F.date_format("window.end", "HH:mm").alias("end"), "orders", "revenue"))

for mode in ["append", "update", "complete"]:
    q = (windowed.writeStream.outputMode(mode)
         .foreachBatch(printer(mode))
         .option("checkpointLocation", f"{base}/chk/win_{mode}")
         .trigger(availableNow=True).start())
    q.awaitTermination()
# and the same query in append mode into the Delta table gold_orders_10min
```

```text
-- run 1: 10:01, 10:04, 10:12
   append   batch 0: nothing emitted
   append   batch 1: nothing emitted
   progress batch 0: rows=3 eventTime.max=2026-03-01T10:12:00.000Z watermark=1970-01-01T00:00:00.000Z
   progress batch 1: rows=0 eventTime.max=None watermark=2026-03-01T10:02:00.000Z
   update   batch 0: ['10:00-10:10 orders=2 revenue=30.00', '10:10-10:20 orders=1 revenue=30.00']
   update   batch 1: nothing emitted
   complete batch 0: ['10:00-10:10 orders=2 revenue=30.00', '10:10-10:20 orders=1 revenue=30.00']
-- run 2: 10:07 (late) and 10:26
   append   batch 2: nothing emitted
   append   batch 3: ['10:00-10:10 orders=3 revenue=70.00']
   progress batch 2: rows=2 eventTime.max=2026-03-01T10:26:00.000Z watermark=2026-03-01T10:02:00.000Z
   progress batch 3: rows=0 eventTime.max=None watermark=2026-03-01T10:16:00.000Z
   update   batch 2: ['10:00-10:10 orders=3 revenue=70.00', '10:20-10:30 orders=1 revenue=50.00']
   update   batch 3: nothing emitted
   complete batch 1: ['10:00-10:10 orders=3 revenue=70.00', '10:10-10:20 orders=1 revenue=30.00', '10:20-10:30 orders=1 revenue=50.00']
-- run 3: 10:05 (too late) and 10:33
   append   batch 4: nothing emitted
   append   batch 5: ['10:10-10:20 orders=1 revenue=30.00']
   progress batch 4: rows=2 eventTime.max=2026-03-01T10:33:00.000Z watermark=2026-03-01T10:16:00.000Z
   progress batch 5: rows=0 eventTime.max=None watermark=2026-03-01T10:23:00.000Z
   update   batch 4: ['10:30-10:40 orders=1 revenue=70.00']
   update   batch 5: nothing emitted
   complete batch 2: ['10:00-10:10 orders=4 revenue=130.00', '10:10-10:20 orders=1 revenue=30.00', '10:20-10:30 orders=1 revenue=50.00', '10:30-10:40 orders=1 revenue=70.00']
```

```text
>>> SELECT * FROM gold_orders_10min ORDER BY start
+-----+-----+------+-------+
|start|end  |orders|revenue|
+-----+-----+------+-------+
|10:00|10:10|3     |70.00  |
|10:10|10:20|1     |30.00  |
+-----+-----+------+-------+
```

Walk through it:

- **Run 1.** The batch saw a maximum of 10:12, so after it the watermark became 10:12 - 10 min = 10:02. Nothing is
  final yet, so append wrote nothing. Update wrote both windows. Batch 1 is the no-data batch `availableNow` runs to
  apply the new watermark before stopping.
- **Run 2.** Order 1104 at 10:07 is late: it arrived after a 10:12 order. It was judged against the watermark in force,
  10:02, and 10:07 is later than 10:02, so it was **counted**: window 10:00-10:10 went from 2 to 3 orders. After the
  batch the watermark moved to 10:26 - 10 min = 10:16. Window 10:00-10:10 ends at 10:10, before 10:16, so it became
  final and append wrote it, once, in the no-data batch 3.
- **Run 3.** Order 1106 at 10:05 belongs to the window that is already closed (10:05 is before the watermark 10:16 in
  force), so it was **dropped**: append and update never show it, and the Delta table keeps 3 orders for 10:00-10:10.
  The watermark moved to 10:23, which finalized 10:10-10:20.
- **Complete mode counted the too-late order** (10:00-10:10 = 4 orders, revenue 130.00). Databricks: in complete mode,
  "Aggregation state isn't dropped" ([watermarks](https://docs.databricks.com/aws/en/structured-streaming/watermarks)),
  so nothing is ever too late, and nothing is ever cleaned up.

Now the batch-boundary effect. The same three files, read by a new query with a new checkpoint in one `availableNow`
run, land in a single micro-batch:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
   update   batch 0: ['10:00-10:10 orders=4 revenue=130.00', '10:10-10:20 orders=1 revenue=30.00', '10:20-10:30 orders=1 revenue=50.00', '10:30-10:40 orders=1 revenue=70.00']
   update   batch 1: nothing emitted
   batches: [(0, 7), (1, 0)]
```

Four orders in 10:00-10:10 this time: in one batch there was no earlier watermark, so the 10:05 order was not late.
Same data, same query, different answer. That is the "may or may not get aggregated" in the guarantee, and it is why a
replay or backfill of a windowed stream can give slightly different numbers than the original run.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 260" role="img" aria-label="Event time axis from 10:00 to 10:40 with 10-minute windows. Run 1 has orders at 10:01, 10:04 and 10:12 and no watermark yet. Run 2 has the watermark 10:02 in force: the late 10:07 order is counted, plus 10:26. Run 3 has the watermark 10:16 in force: the 10:05 order is dropped, 10:33 is counted.">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<line x1="60" y1="210" x2="600" y2="210"/>
<line x1="60" y1="36" x2="60" y2="214" stroke-dasharray="2 4"/><line x1="195" y1="36" x2="195" y2="214" stroke-dasharray="2 4"/>
<line x1="330" y1="36" x2="330" y2="214" stroke-dasharray="2 4"/><line x1="465" y1="36" x2="465" y2="214" stroke-dasharray="2 4"/>
<line x1="600" y1="36" x2="600" y2="214" stroke-dasharray="2 4"/>
<line x1="60" y1="70" x2="600" y2="70" stroke-opacity="0.35"/>
<line x1="60" y1="125" x2="600" y2="125" stroke-opacity="0.35"/>
<line x1="60" y1="180" x2="600" y2="180" stroke-opacity="0.35"/>
<line x1="87" y1="110" x2="87" y2="140" stroke-width="2.5"/>
<line x1="276" y1="165" x2="276" y2="195" stroke-width="2.5"/>
<circle cx="154.5" cy="125" r="6"/>
<line x1="121" y1="174" x2="133" y2="186" stroke-width="2"/><line x1="133" y1="174" x2="121" y2="186" stroke-width="2"/>
</g>
<g fill="currentColor">
<circle cx="73.5" cy="70" r="5"/><circle cx="114" cy="70" r="5"/><circle cx="222" cy="70" r="5"/>
<circle cx="154.5" cy="125" r="3"/><circle cx="411" cy="125" r="5"/>
<circle cx="505.5" cy="180" r="5"/>
</g>
<g fill="currentColor" font-size="13">
<text x="10" y="74">run 1</text><text x="10" y="129">run 2</text><text x="10" y="184">run 3</text>
<text x="127" y="28" text-anchor="middle">window 10:00-10:10</text><text x="397" y="28" text-anchor="middle">window 10:20-10:30</text>
<text x="250" y="56">no watermark yet</text>
<text x="87" y="104" text-anchor="middle">wm 10:02</text>
<text x="166" y="148">10:07 late, counted</text>
<text x="276" y="159" text-anchor="middle">wm 10:16</text>
<text x="127" y="203" text-anchor="middle">10:05 dropped</text>
<text x="60" y="230" text-anchor="middle">10:00</text><text x="195" y="230" text-anchor="middle">10:10</text>
<text x="330" y="230" text-anchor="middle">10:20</text><text x="465" y="230" text-anchor="middle">10:30</text>
<text x="600" y="230" text-anchor="end">10:40</text>
<text x="330" y="252" text-anchor="middle">event time (order_ts); "wm" = watermark in force during that run</text>
</g>
</svg>
<figcaption>Figure 11.3. Each run is judged against the watermark left by the run before it: 10:07 is after 10:02 and counts; 10:05 is before 10:16, in a window already closed, and is dropped.</figcaption>
</figure>

### Rules that make watermarks work

- Call `withWatermark` **before** the aggregation, on the **same** event-time column the aggregation groups by (or
  windows on). The output mode must be append or update; "Complete mode requires all aggregate data to be preserved,
  and hence cannot use watermarking to drop intermediate state" (Spark guide). Databricks adds: in `groupBy()` and
  `window()`, "reference columns by name" so the event-time marker is kept
  ([watermarks](https://docs.databricks.com/aws/en/structured-streaming/watermarks)).
- The event-time column must be `TIMESTAMP` (or `TIMESTAMP_NTZ`); window durations go "from microseconds up to days.
  Month durations and longer are not supported".
- Choosing the delay is a trade-off. "Shorter watermarks lower query latency" and keep less state but tolerate less
  late data; longer ones do the opposite. Databricks suggests "a small multiple of your latency SLA, such as 2x" as a
  starting point for operational workloads
  ([production](https://docs.databricks.com/aws/en/structured-streaming/production)).
- With several inputs (a union or a join), each input gets its own watermark and Spark uses the **minimum** as the
  global watermark by default (`spark.sql.streaming.multipleWatermarkPolicy`, default `min`), so a slow input delays
  output instead of making the fast input's data late.
- A Delta source's first run reads the initial snapshot "based on which file was last modified", which can make
  records look late and get dropped; Databricks Runtime 11.3 LTS and above offers the `withEventTimeOrder` option for
  that ([Delta streaming](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)).

!!! tip "In the interview"
    **"What is a watermark and what happens to late data?"** It is the latest event time seen minus a delay you set.
    It tells Spark when a window is final, so it can write it (append mode) and drop its state. Rows less late than
    the threshold relative to the latest data are guaranteed to be counted; rows older than the watermark in force are
    dropped, although that side is not strictly guaranteed. The watermark is updated after each micro-batch, so where
    batch boundaries fall can change whether a borderline row counts.

## 11.7 Reading a Delta table as a stream

*Level: intermediate.*

Silver reads bronze, gold reads silver: in a medallion design most streams read a Delta table. Chapter 9 shows the
basics and the `UPDATE` failure ([9.2](09-Building-Silver.md)); this section adds the rules and the other options.

The rule: "Structured Streaming only accepts append inputs and throws an exception if any modifications occur on the
source Delta Lake table", meaning an `UPDATE`, `DELETE`, `MERGE INTO` or `OVERWRITE`. Databricks lists four ways out:
`skipChangeCommits` (process appends only and ignore commits that change existing rows; recommended "for most
workloads that do not use change data feeds"), a full refresh of the downstream table, the change data feed, or a
materialized view ([Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)).
There are also two legacy options: `ignoreChanges` (Databricks Runtime 11.3 LTS and lower; replaced by
`skipChangeCommits` in 12.2 LTS and above) and `ignoreDeletes`, which "only handles transactions that delete data at
partition boundaries".

The run below streams a `bronze_orders` table partitioned by `order_date` (one file per day) into four silver tables,
then deletes data two ways:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def run(name, **opts):
    reader = spark.readStream
    for k, v in opts.items():
        reader = reader.option(k, v)
    q = (reader.table("bronze_orders").writeStream
         .option("checkpointLocation", f"{base}/chk/{name}")
         .trigger(availableNow=True).toTable(name))
    q.awaitTermination()

run("silver_a", maxFilesPerTrigger=1)        # three daily files
run("silver_b"); run("silver_c")

spark.sql("DELETE FROM bronze_orders WHERE order_date = DATE'2026-03-01'")   # a whole partition
# ... one new order is appended ...
run("silver_a")
run("silver_b", ignoreDeletes="true")

spark.sql("DELETE FROM bronze_orders WHERE order_id = 1904")                  # one row inside a partition
# ... one new order is appended ...
run("silver_b", ignoreDeletes="true")
run("silver_c", skipChangeCommits="true")
```

```text
== 1. Rate limit: maxFilesPerTrigger=1 on a Delta source
   silver_a: (batchId, rows) [(0, 2), (1, 2), (2, 1)]; table has 5 rows
   silver_b: (batchId, rows) [(0, 5)]; table has 5 rows
   silver_c: (batchId, rows) [(0, 5)]; table has 5 rows

== 2. Delete a whole partition (2026-03-01), then run the streams again
   silver_a: failed: [STREAM_FAILED] Query [...] terminated with exception: [DELTA_SOURCE_IGNORE_DELETE] Detected deleted data (for example order_date=2026-03-01/part-...
   silver_b: (batchId, rows) [(1, 1)]; table has 6 rows

== 3. Delete one order inside a partition, then run again
   silver_b: failed: [STREAM_FAILED] Query [...] terminated with exception: [DELTA_SOURCE_TABLE_IGNORE_CHANGES] Detected a data update (for example DELETE (Map(predica...
   silver_c: (batchId, rows) [(1, 2)]; table has 7 rows
```

What happened:

- `maxFilesPerTrigger=1` turned the three daily files into three micro-batches.
- The partition drop failed the plain stream; `ignoreDeletes` accepted it and read the new order.
- Deleting one order rewrote the file that also held order 1903, a change and not a pure delete, so `ignoreDeletes`
  failed. `skipChangeCommits` skipped both delete commits and read the two new orders.
- Silver still contains the deleted orders. Neither option deletes anything downstream; if silver must forget order
  1904 (for example a GDPR request), you delete it there yourself or use the change data feed.

`startingVersion` and `startingTimestamp` start a **new** stream at a table version instead of at the full snapshot.
"These settings apply to new streaming queries only"; once the checkpoint has progress, they are ignored. In the run,
a new query with `startingVersion=6` (version 6 was the second delete) read only order 1907.

Two more warnings from the same page. A stream reading a Delta table "must run at least one time within the source
table's retention window" (7 days for files removed by `VACUUM`, 30 days for the log by default), or it fails with
`DELTA_FILE_NOT_FOUND_DETAILED` and needs a full refresh; do not set `spark.sql.files.ignoreMissingFiles` to get around
it. And the source schema: if it changes after the stream starts, the query fails, and "for most schema changes, you
can restart the stream".

### Streaming the change data feed

When the source really has updates and deletes (a silver customers table), stream its **change data feed** (CDF):
"Databricks recommends streaming from the CDC feed of a Delta Lake table rather than directly from the table whenever
possible" ([Delta streaming](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)). "When the stream first starts, change data feed returns the latest snapshot of the table as `INSERT`
records and then returns future changes as change data"
([Use change data feed on Databricks](https://docs.databricks.com/aws/en/delta/delta-change-data-feed)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
spark.sql("""CREATE TABLE silver_customers (customer_id INT, name STRING, city STRING)
             USING DELTA TBLPROPERTIES (delta.enableChangeDataFeed = true)""")
spark.sql("INSERT INTO silver_customers VALUES (7, 'Ana Ruiz', 'Calgary'), (8, 'Ben Okafor', 'Banff')")

def cdf_run():
    q = (spark.readStream.option("readChangeFeed", "true").table("silver_customers")
         .writeStream.option("checkpointLocation", f"{base}/chk/cdf")
         .trigger(availableNow=True).toTable("customer_changes"))
    q.awaitTermination()

cdf_run()                                                    # the snapshot, as inserts
spark.sql("UPDATE silver_customers SET city = 'Canmore' WHERE customer_id = 7")
spark.sql("DELETE FROM silver_customers WHERE customer_id = 8")
cdf_run()                                                    # the two changes
```

```text
+-----------+----------+-------+----------------+---------------+
|customer_id|name      |city   |_change_type    |_commit_version|
+-----------+----------+-------+----------------+---------------+
|7          |Ana Ruiz  |Calgary|insert          |1              |
|8          |Ben Okafor|Banff  |insert          |1              |
|7          |Ana Ruiz  |Canmore|update_postimage|2              |
|7          |Ana Ruiz  |Calgary|update_preimage |2              |
|8          |Ben Okafor|Banff  |delete          |3              |
+-----------+----------+-------+----------------+---------------+
```

A downstream table applies these rows with a `MERGE` in `foreachBatch`: drop `update_preimage`, keep the latest change
per key, then update, insert or delete. Chapter 9 runs that pattern in full
([9.11](09-Building-Silver.md)).

!!! tip "In the interview"
    **"Someone ran an UPDATE on the bronze table and the silver stream fails. What do you do?"** A Delta streaming
    source accepts appends only. If the change does not need to flow downstream, restart with
    `skipChangeCommits=true` (and fix silver separately if needed). If downstream must see updates and deletes,
    read the change data feed and apply it with `MERGE`. For a small table, a full refresh of the downstream table and
    its checkpoint is also acceptable.

## 11.8 foreachBatch with MERGE

*Level: intermediate.*

`foreachBatch(fn)` calls `fn(batch_df, batch_id)` once per micro-batch with an ordinary (non-streaming) DataFrame.
Inside you can use any batch API. Databricks: "You must use `foreachBatch` for Delta Lake merge operations in
Structured Streaming" ([Use foreachBatch to write to arbitrary data sinks](https://docs.databricks.com/aws/en/structured-streaming/foreach)).
It is the standard way to get update semantics into a Delta table, to upsert change data, and to write to systems
that have no streaming sink.

The writer below keeps `orders_current` (one row per order, latest status) and also appends every event to
`orders_log`. It deduplicates the batch first (a `MERGE` fails if two source rows match one target row) and guards
the update with the event time, the out-of-order rule from chapter 9.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql.window import Window

APP_ID = "red-rock-orders-current"          # a stable id for this writer

def process(batch_df, batch_id):
    if batch_df.isEmpty():                  # empty micro-batches can happen
        return
    (batch_df.select("order_id", "status", "order_ts", F.lit(batch_id).alias("batch_id"))
     .write.format("delta").mode("append")
     .option("txnAppId", APP_ID).option("txnVersion", batch_id)   # idempotent append
     .saveAsTable("orders_log_safe"))
    latest = (batch_df
              .withColumn("rn", F.row_number().over(
                  Window.partitionBy("order_id").orderBy(F.col("order_ts").desc())))
              .where("rn = 1").select("order_id", "status", "order_ts"))
    latest.createOrReplaceTempView("updates")
    batch_df.sparkSession.sql("""
        MERGE INTO orders_current_safe t
        USING updates s
        ON t.order_id = s.order_id
        WHEN MATCHED AND s.order_ts > t.order_ts THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *""")

(spark.readStream.format("json").schema(ORDER_SCHEMA)
   .option("maxFilesPerTrigger", 1).load(landing)
   .writeStream.foreachBatch(process)
   .option("checkpointLocation", f"{base}/chk/safe")
   .trigger(availableNow=True).start())
```

Points that the Databricks pages make (the foreachBatch page, and the `MERGE` section of
[Delta streaming](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)) and interviewers ask about:

- Use the `sparkSession` of the batch DataFrame for SQL inside the function (`batch_df.sparkSession.sql`).
- Handle empty DataFrames: an `OPTIMIZE` with nothing to do on a Delta source, or file pruning, can produce an empty
  micro-batch.
- `foreachBatch` gives "only at-least-once write guarantees" (next section).
- For several outputs, Databricks recommends "a separate streaming write for each sink" instead, because writes inside
  `foreachBatch` run one after another.
- `merge` reads its input more than once, which can multiply the input-rate metrics; the page suggests caching the
  batch DataFrame before the `MERGE` and uncaching after.
- On errors, "allow the streaming query to fail fast" and let the job retry the whole batch; do not catch and retry
  inside the function.

The same thing in SQL needs no `foreachBatch` in a Lakeflow pipeline: `AUTO CDC` (formerly `APPLY CHANGES`, see
[The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc)) applies a change feed to a streaming table; that is
chapter 14.

## 11.9 Exactly-once, end to end

*Level: intermediate.*

"Exactly-once" in Structured Streaming means: after any failure and restart, every input record affects the output
exactly once. The Spark guide names the three parts it needs: sources with offsets that can be replayed, "checkpointing
and write-ahead logs to record the offset range of the data being processed in each trigger", and sinks "designed to be
idempotent for handling reprocessing". "Together, using replayable sources and idempotent sinks, Structured Streaming
can ensure **end-to-end exactly-once semantics** under any failure"
([getting started](https://spark.apache.org/docs/4.2.0/streaming/getting-started.html)). An **idempotent** write is one
you can repeat with the same result.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 270" role="img" aria-label="Exactly-once needs three links: a replayable source, a checkpoint with offsets written before and commits written after each batch, and an idempotent sink such as Delta's transaction id. foreachBatch is at-least-once unless the writes are made idempotent.">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="10" y="30" width="190" height="80" rx="6"/>
<rect x="225" y="30" width="190" height="80" rx="6"/>
<rect x="440" y="30" width="190" height="80" rx="6"/>
<line x1="200" y1="70" x2="219" y2="70"/><line x1="415" y1="70" x2="434" y2="70"/>
<rect x="170" y="140" width="300" height="40" rx="6"/>
<line x1="320" y1="110" x2="320" y2="134"/>
<rect x="10" y="204" width="620" height="58" rx="6" stroke-dasharray="5 3"/>
</g>
<g fill="currentColor">
<path d="M219,66 L225,70 L219,74 Z"/><path d="M434,66 L440,70 L434,74 Z"/><path d="M316,134 L320,140 L324,134 Z"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="105" y="54" font-size="14">Replayable source</text>
<text x="105" y="76">files, Kafka offsets,</text>
<text x="105" y="96">Delta table versions</text>
<text x="320" y="54" font-size="14">Checkpoint</text>
<text x="320" y="76">offsets/N before a batch,</text>
<text x="320" y="96">commits/N after it</text>
<text x="535" y="54" font-size="14">Idempotent sink</text>
<text x="535" y="76">Delta: txn action with</text>
<text x="535" y="96">app id + batch version</text>
<text x="320" y="165" font-size="14">Exactly-once results</text>
<text x="320" y="227">foreachBatch is at-least-once: a replayed batch can repeat its writes.</text>
<text x="320" y="249">Fix: txnAppId + txnVersion on Delta writes, or a MERGE that gives the same result.</text>
</g>
</svg>
<figcaption>Figure 11.4. Exactly-once is a chain. Break any link (a non-replayable source, a lost checkpoint, a non-idempotent write) and you get duplicates or gaps.</figcaption>
</figure>

### How the Delta sink makes a replay harmless

Databricks: "The Delta Lake transaction log guarantees exactly-once processing, even when there are other streams or
batch queries running concurrently against the table"
([Delta streaming](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)). The mechanism is visible in
the table history and log of the first stream in this chapter:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from delta.tables import DeltaTable
(DeltaTable.forName(spark, "bronze_orders").history()
 .selectExpr("version", "operation", "operationParameters.outputMode AS outputMode",
             "operationParameters.queryId AS queryId", "operationParameters.epochId AS epochId",
             "operationMetrics.numOutputRows AS rows")
 .orderBy("version").show(truncate=False))
# then print the "txn" action from _delta_log/00000000000000000001.json and ...03.json
```

```text
+-------+----------------+----------+------------------------------------+-------+----+
|version|operation       |outputMode|queryId                             |epochId|rows|
+-------+----------------+----------+------------------------------------+-------+----+
|0      |CREATE TABLE    |NULL      |NULL                                |NULL   |NULL|
|1      |STREAMING UPDATE|Append    |cdb53715-b6e3-48d5-b804-4d14ca0d1757|0      |3   |
|2      |STREAMING UPDATE|Append    |cdb53715-b6e3-48d5-b804-4d14ca0d1757|1      |2   |
|3      |STREAMING UPDATE|Append    |cdb53715-b6e3-48d5-b804-4d14ca0d1757|2      |2   |
+-------+----------------+----------+------------------------------------+-------+----+

version 1 txn action: {"appId": "cdb53715-b6e3-48d5-b804-4d14ca0d1757", "version": 0, "lastUpdated": 1794379928957}
version 3 txn action: {"appId": "cdb53715-b6e3-48d5-b804-4d14ca0d1757", "version": 2, "lastUpdated": 1794380030325}
query id from metadata file: cdb53715-b6e3-48d5-b804-4d14ca0d1757
```

Each micro-batch is one Delta commit, and the commit carries a `txn` action: the query id from the checkpoint's
`metadata` file and the batch id. If batch 2 is replayed after a crash, Delta sees that this query already committed
batch 2 and skips the write. That is also why the "delete the checkpoint" run duplicated everything: a new checkpoint
is a new query id, so Delta had no reason to skip anything. (This is what open-source Delta 4.4.1 wrote here.
Databricks documents the guarantee rather than the log details, and notes that a Delta sink may show empty commits with
`epochId = -1` on the first batch of each run, which "are intentional and do not indicate an error".)

Exactly-once is about processing, not about your data. If the upstream system sends the same order twice, both rows
are processed exactly once each; removing duplicates in the data is your job (deduplication, section 11.11, or `MERGE`).

### foreachBatch: a crash in the middle of a batch

Inside `foreachBatch`, Spark cannot know what your function already wrote. The run below makes batch 1 crash after its
first write (the append to the log), retries the query with the same checkpoint, and compares a writer without the
transaction options ("naive") with the one shown in 11.8 ("safe"):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
if CRASH["on"] and batch_id == 1:           # inside process(), right after the append
    raise RuntimeError("simulated crash after write 1 of batch 1")
```

```text
== 1. Batch 1 crashes after its first write
   naive: query failed: [STREAM_FAILED] Query [...] terminated with exception: [FOREACH_BATCH_USER_F...
   safe: query failed: [STREAM_FAILED] Query [...] terminated with exception: [FOREACH_BATCH_USER_F...
== 2. The job is retried (same checkpoint): batch 1 is replayed
   naive: batches [1]
   safe: batches [1]
>>> SELECT batch_id, order_id, status, count(*) AS copies FROM orders_log_naive GROUP BY ALL ORDER BY batch_id, order_id
+--------+--------+-------+------+
|batch_id|order_id|status |copies|
+--------+--------+-------+------+
|0       |1801    |PLACED |1     |
|0       |1802    |PLACED |1     |
|1       |1801    |SHIPPED|2     |
|1       |1803    |PLACED |2     |
+--------+--------+-------+------+

>>> SELECT batch_id, order_id, status, count(*) AS copies FROM orders_log_safe GROUP BY ALL ORDER BY batch_id, order_id
+--------+--------+-------+------+
|batch_id|order_id|status |copies|
+--------+--------+-------+------+
|0       |1801    |PLACED |1     |
|0       |1802    |PLACED |1     |
|1       |1801    |SHIPPED|1     |
|1       |1803    |PLACED |1     |
+--------+--------+-------+------+
```

The naive log has batch 1 twice. The safe log has it once: on the replay, Delta saw `txnAppId` and `txnVersion = 1`
already committed and skipped the append (its history has one `WRITE` per batch, no third one). Both `orders_current`
tables are correct (1801 `SHIPPED`, 1802 and 1803 `PLACED`) because the guarded `MERGE` gives the same result when
repeated. Databricks' rule for Delta targets in `foreachBatch`: "You must use the `txnAppId` and `txnVersion` write
options, binding `txnVersion` to `batchId`"
([foreachBatch](https://docs.databricks.com/aws/en/structured-streaming/foreach)).

### The txnAppId trap

"If you delete the streaming checkpoint and restart the query with a new checkpoint, you must provide a different
`txnAppId`. New checkpoints start with a batch ID of `0`"
([Delta streaming](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)). Here the checkpoint is deleted,
a new order 1804 lands, and the writer restarts with the same `APP_ID`. The new run reads all three files in one batch,
batch 0:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
== 3. The trap: delete the checkpoint but keep the same txnAppId
   safe: batches [0]
>>> SELECT count(*) AS log_rows, count_if(order_id = 1804) AS has_1804 FROM orders_log_safe
+--------+--------+
|log_rows|has_1804|
+--------+--------+
|4       |0       |
+--------+--------+

>>> SELECT * FROM orders_current_safe ORDER BY order_id
+--------+-------+-------------------+
|order_id|status |order_ts           |
+--------+-------+-------------------+
|1801    |SHIPPED|2026-03-01 11:00:00|
|1802    |PLACED |2026-03-01 10:05:00|
|1803    |PLACED |2026-03-01 11:10:00|
|1804    |PLACED |2026-03-01 12:00:00|
+--------+-------+-------------------+
```

Order 1804 is missing from the log, silently: Delta had already seen version 1 for this app id, so it skipped the new
batch 0, new data included. The `MERGE` (no transaction options) did apply it, so the two tables now disagree. When
you reset a checkpoint, change the `txnAppId` too, for example by putting a version in it.

!!! tip "In the interview"
    **"How do you get exactly-once into Delta from a stream?"** Replayable source plus checkpoint plus idempotent sink.
    The Delta sink is idempotent by itself: each micro-batch commit records the query id and batch id, so a replayed
    batch is skipped. `foreachBatch` is at-least-once, so make each write idempotent: `txnAppId` plus
    `txnVersion = batch_id` on Delta writes, or a `MERGE` whose result does not change when it runs twice. If you reset
    the checkpoint, change the `txnAppId`.

## 11.10 Auto Loader and Lakeflow pipelines: the same engine, managed

*Level: intermediate.*

Most Databricks teams do not hand-write all of this. Two products wrap it:

- **Auto Loader** (`cloudFiles`, chapter 8) is a smarter file source: scalable file discovery, schema inference and
  evolution, its state in the checkpoint. You still choose the checkpoint, trigger and sink when you use it from
  `readStream`.
- **Lakeflow pipelines** (formerly Delta Live Tables, [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt))
  define **streaming tables**. "Pipelines manage orchestration, checkpoints, and recovery, and you define
  transformations in SQL or Python" ([concepts](https://docs.databricks.com/aws/en/structured-streaming/concepts)). A
  streaming table is "a Delta table with additional support for streaming or incremental data processing", and "Each
  input row is handled only once" ([Streaming tables](https://docs.databricks.com/aws/en/ldp/streaming-tables)).

The Python form is a function that returns a streaming DataFrame; the pipeline adds the `writeStream` part:

*Databricks only, not run here. Syntax from [Load data in pipelines](https://docs.databricks.com/aws/en/ldp/load).*

```python
from pyspark import pipelines as dp

@dp.table
def orders_bronze():
    return (spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "json")
            .load("/Volumes/shop/bronze/landing/orders/"))
```

What carries over from this chapter, because it is the same engine underneath:

- A query change applies only to new rows. The streaming tables page: change `SELECT LOWER(name)` to
  `SELECT UPPER(name)` and "existing rows will not update to be uppercase, but new rows will be uppercase". A **full
  refresh** reprocesses everything: it "truncates the streaming table, removes all checkpoint data, and restarts the
  streaming process with new checkpoints"; with a Kafka source whose retention has passed, older data "cannot be
  reprocessed" ([Full refresh for streaming tables](https://docs.databricks.com/aws/en/ldp/full-refresh-st)).
- State still needs bounds: streaming tables "expect streams that are naturally bounded or bounded with a watermark".
- A stream-static join in a streaming table does not recompute when the dimension changes (section 11.11).
- **Backfill**: add a one-time flow that appends historical data into the same streaming table, an append flow with
  the `ONCE` option (`once=True` in Python), and make sure downstream handles duplicates
  ([Backfilling historical data with pipelines](https://docs.databricks.com/aws/en/ldp/flows-backfill)).

Chapter 13 covers pipelines in full.

## 11.11 Stateful operations: windows, deduplication and joins

*Level: expert.*

A **stateless** query (select, filter, cast, stream-static join) keeps nothing between micro-batches except the
checkpoint's offsets. A **stateful** query keeps intermediate results: Databricks lists "streaming aggregation,
`distinct`, `dropDuplicates`, stream-stream joins, and custom stateful applications"
([What is stateful streaming?](https://docs.databricks.com/aws/en/structured-streaming/stateful-streaming)). State is
where streaming jobs get slow, expensive and fragile, so every stateful operator below is shown with its bound.

### Sliding and session windows

A **sliding window** has a fixed length and a slide shorter than the length, so windows overlap and one row can count
in several windows. A **session window** has no fixed length: it "opens when a row arrives and closes after a gap
duration that contains no new rows" ([watermarks](https://docs.databricks.com/aws/en/structured-streaming/watermarks)).
Six orders, two customers:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
# customer 7 at 09:00, 09:10, 09:25, 10:30; customer 8 at 09:05, 09:50
sliding = (stream(win_dir)
           .groupBy(F.window("order_ts", "30 minutes", "15 minutes"))
           .agg(F.count("*").alias("orders")))

sessions = (stream(win_dir)
            .groupBy("customer_id", F.session_window("order_ts", "20 minutes"))
            .agg(F.count("*").alias("orders"), F.sum("amount").alias("spent")))
# both written in complete mode through foreachBatch; then sessions again in update mode
```

```text
== 1. Sliding windows: 30 minutes long, every 15 minutes
      {'start': '08:45', 'end': '09:15', 'orders': 3}
      {'start': '09:00', 'end': '09:30', 'orders': 4}
      {'start': '09:15', 'end': '09:45', 'orders': 1}
      {'start': '09:30', 'end': '10:00', 'orders': 1}
      {'start': '09:45', 'end': '10:15', 'orders': 1}
      {'start': '10:15', 'end': '10:45', 'orders': 1}
      {'start': '10:30', 'end': '11:00', 'orders': 1}

== 2. Session windows per customer, 20-minute gap
      {'customer_id': 7, 'start': '09:00', 'end': '09:45', 'orders': 3, 'spent': Decimal('80.00')}
      {'customer_id': 7, 'start': '10:30', 'end': '10:50', 'orders': 1, 'spent': Decimal('60.00')}
      {'customer_id': 8, 'start': '09:05', 'end': '09:25', 'orders': 1, 'spent': Decimal('20.00')}
      {'customer_id': 8, 'start': '09:50', 'end': '10:10', 'orders': 1, 'spent': Decimal('50.00')}
   session window in update mode: [STREAMING_OUTPUT_MODE.UNSUPPORTED_OPERATION] Invalid streaming output mode: update. This output mode is not supported for session window streaming aggregations on streaming DataFrames/DataSets. SQLST...
```

In the sliding version the six orders produce seven windows whose counts add up to twelve, because each order falls in
two windows (the `batch 0:` lines of the output are left out here). Customer
7's first session runs from 09:00 to 09:45: each order within 20 minutes of the previous one extends it, and it ends 20
minutes after the last order (09:25). These ran in complete mode for display; in production give them a watermark and
use append mode so state is dropped (session windows do not support update mode, as the error shows).

### Deduplication

An upstream retry resends order events. Two tools, one difference that matters in production: whether state is
bounded.

- `dropDuplicates(["order_id", "status"])` with no watermark: "the query stores the data from all the past records as
  state" (Spark guide). Correct forever, and state grows forever.
- `withWatermark(...).dropDuplicates(["order_id", "status", "order_ts"])`: bounded, but only if the event time is part
  of the key, which fails when a resend carries a new timestamp.
- `withWatermark(...).dropDuplicatesWithinWatermark(["order_id", "status"])` (Databricks Runtime 13.3 LTS and above;
  "New in version 3.5.0" in the [PySpark API reference](https://spark.apache.org/docs/4.2.0/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.dropDuplicatesWithinWatermark.html)): removes duplicates "even when fields differ across duplicate records, such as event time
  or arrival time", and drops state after the watermark passes. "To guarantee queries drop all duplicates, set the
  watermark threshold to be greater than the maximum timestamp difference between duplicate events"
  ([watermarks](https://docs.databricks.com/aws/en/structured-streaming/watermarks)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
no_wm = stream(dup_dir).dropDuplicates(["order_id", "status"])
within = (stream(dup_dir).withWatermark("order_ts", "30 minutes")
          .dropDuplicatesWithinWatermark(["order_id", "status"]))
# run 1: 1401 at 10:00:00, its resend at 10:00:05, 1402 at 10:02
# run 2: another resend of 1401 at 10:00:09, 1403 at 10:20
# run 3: 1404 at 12:00, 1405 at 12:01
```

```text
-- run 1
   dropDuplicates (no watermark)       batch 0: in=3 stateRows=2 watermark=-
      emitted: [(1401, 'PLACED', '10:00:00'), (1402, 'PLACED', '10:02:00')]
   dropDuplicatesWithinWatermark 30min batch 0: in=3 stateRows=2 watermark=1970-01-01T00:00:00.000Z
   dropDuplicatesWithinWatermark 30min batch 1: in=0 stateRows=2 watermark=2026-03-01T09:32:00.000Z
-- run 2
   dropDuplicates (no watermark)       batch 1: in=2 stateRows=3 watermark=-
      emitted: [(1403, 'PLACED', '10:20:00')]
   dropDuplicatesWithinWatermark 30min batch 2: in=2 stateRows=3 watermark=2026-03-01T09:32:00.000Z
   dropDuplicatesWithinWatermark 30min batch 3: in=0 stateRows=3 watermark=2026-03-01T09:50:00.000Z
-- run 3
   dropDuplicates (no watermark)       batch 2: in=2 stateRows=5 watermark=-
      emitted: [(1404, 'PLACED', '12:00:00'), (1405, 'PLACED', '12:01:00')]
   dropDuplicatesWithinWatermark 30min batch 4: in=2 stateRows=5 watermark=2026-03-01T09:50:00.000Z
   dropDuplicatesWithinWatermark 30min batch 5: in=0 stateRows=2 watermark=2026-03-01T11:31:00.000Z
```

(The `within` query emitted the same rows as `no_wm`; those lines are in `s3_stateful.out`.) Both queries removed both
resends of 1401, even the one with a different timestamp and the one in a later batch. The difference is `stateRows`
(`stateOperators.numRowsTotal` in the progress report): 2, 3, 5 for the unbounded version, and it would keep growing
with every order Red Rock Supply ever receives; 2 at the end for the bounded version, because the watermark of 11:31
evicted every key older than that.

### Stream-static join

Joining the order stream to the `products` dimension is **stream-static**: "only newly received records from the
streaming source are joined with the current version of the static table", it is stateless, and "If you update the
static table between runs, re-processing the same streaming data can produce different results"
([Work with joins on Databricks](https://docs.databricks.com/aws/en/transform/join)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
enriched = items_stream().join(spark.read.table("products"), "product_id", "left")
# run 1, then: INSERT INTO products VALUES (9, 'Headlamp', 'Lighting', 45.00); a new order lands; run 2
```

```text
-- run 1 (product 9 is not in products yet)
   {'order_id': 1601, 'product_id': 3, 'name': 'Trail Pack 30L'}
   {'order_id': 1602, 'product_id': 5, 'name': 'Camp Stove'}
   {'order_id': 1603, 'product_id': 9, 'name': None}
-- run 2 (product 9 added; only the new order sees it)
   {'order_id': 1604, 'product_id': 9, 'name': 'Headlamp'}
```

Order 1603 keeps `name = None` forever: the stream never revisits it. If late-arriving dimension rows must fix old
facts, use a materialized view or a separate repair step.

### Stream-stream joins

Joining orders to payments, both streams, is **stream-stream**: either side can arrive first, so Spark buffers both
sides in state. Without limits that state "will keep growing indefinitely". The bound needs two things: a watermark on
both inputs, and an event-time condition so old rows can never match again, for example a payment within 30 minutes
of the order (Spark guide). Inner joins work without them (with unbounded state); outer and semi joins require them,
because Spark must know when a row will never match before it can emit the `NULL` side. Joins support append mode only
([watermarks](https://docs.databricks.com/aws/en/structured-streaming/watermarks)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
o = (spark.readStream.format("json").schema(ORDER_SCHEMA).load(orders_dir)
     .select("order_id", "order_ts", F.col("amount").alias("order_amount"))
     .withWatermark("order_ts", "1 hour"))
p = (spark.readStream.format("json").schema(PAY_SCHEMA).load(pay_dir)
     .select(F.col("order_id").alias("pay_order_id"), "paid_ts", "payment_id")
     .withWatermark("paid_ts", "1 hour"))
cond = F.expr("pay_order_id = order_id AND "
              "paid_ts >= order_ts AND paid_ts <= order_ts + INTERVAL 30 MINUTES")
joined = o.join(p, cond, "left_outer")       # and "inner"
```

```text
-- run 1: orders [1701, 1702, 1703], payments for [1701]
   inner      batch 0: [(1701, '10:00', 9001, '10:03')]
   left_outer batch 0: [(1701, '10:00', 9001, '10:03')]
   left_outer watermark after run: 2026-03-01T09:03:00.000Z; rows in join state: 4
-- run 2: orders [1704], payments for [1702, 1704]
   inner      batch 2: [(1702, '10:05', 9002, '10:20'), (1704, '11:30', 9004, '11:31')]
   left_outer batch 2: [(1702, '10:05', 9002, '10:20'), (1704, '11:30', 9004, '11:31')]
   left_outer watermark after run: 2026-03-01T10:30:00.000Z; rows in join state: 5
-- run 3: orders [1705], payments for [1705]
   inner      batch 4: [(1705, '13:00', 9005, '13:02')]
   left_outer batch 4: [(1705, '13:00', 9005, '13:02')]
   left_outer batch 5: [(1703, '10:10', None, None)]
   left_outer watermark after run: 2026-03-01T12:00:00.000Z; rows in join state: 3
```

(Lines for empty batches and the inner join's state are left out here; they are in `s4_joins.out`.) Order 1703 was
never paid. The left outer join could only say so after the watermark passed 10:10 + 30 minutes: after run 1 the
global watermark was 09:03 (the minimum of the two inputs: 10:10 - 1 h and 10:03 - 1 h), after run 2 it was 10:30, and
only in run 3, at 12:00, did the unmatched row come out with `NULL`s. Payment 9002 for order 1702 arrived a run later
than its order and still matched, because the order was waiting in state. The Spark guide warns that outer results
may be delayed when one input receives no data for a while. Without watermarks the outer join is refused:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
error: Stream-stream LeftOuter join between two streaming DataFrame/Datasets is not supported without a watermark in the join keys, or a watermark on the nullable side and an appropriate range condition; ~Join LeftOuter, ...
```

### Several stateful operators and custom state

In Databricks Runtime 13.3 LTS and above you can chain stateful operators (a windowed aggregation feeding a join, for
example), with "only the append output mode" supported
([stateful streaming](https://docs.databricks.com/aws/en/structured-streaming/stateful-streaming)). When no built-in
operator fits, `transformWithState` (Databricks Runtime 16.2 and above; in Apache Spark, "since the Spark 4.0 release", per the [Spark guide](https://spark.apache.org/docs/4.2.0/streaming/apis-on-dataframes-and-datasets.html)) runs your own
`StatefulProcessor` per key, with `ValueState`, `ListState` and `MapState` variables, timers, a time-to-live per
value, and schema evolution of the state. Databricks recommends it over the legacy `mapGroupsWithState` and
`flatMapGroupsWithState`, but also recommends "using built-in Structured Streaming operators instead of custom logic"
for aggregations, deduplication and joins
([Build a custom stateful application with transformWithState](https://docs.databricks.com/aws/en/stateful-applications/)).

!!! tip "In the interview"
    **"Our streaming job's state keeps growing. Why, and how do you fix it?"** Some stateful operator has no bound: an
    aggregation or `dropDuplicates` without a watermark, a stream-stream join without watermarks and a time-range
    condition, or complete mode, which never drops state. Check `stateOperators.numRowsTotal` in the progress report
    batch after batch. Fix: add a watermark on the event-time column used by the operator, use
    `dropDuplicatesWithinWatermark`, add a time condition to joins, and use append or update mode. A stateful change
    usually needs a new checkpoint.

## 11.12 The state store, and changing a stateful query

*Level: expert.*

State lives in a **state store**: a versioned key-value store per operator and shuffle partition, saved into the
checkpoint's `state/` folder at each batch. Open-source Spark's default keeps it in executor memory, backed by files
(the HDFS-backed provider); with millions of keys that causes long garbage collection pauses, which is why Spark also
ships a RocksDB provider that keeps state in native memory and on local disk (Spark guide). On Databricks, "RocksDB is
the default state store provider in Databricks Runtime 17.3 LTS and above", and changelog checkpointing (upload only
the changed records each batch) "is enabled by default in Databricks Runtime 17.3 LTS and above"
([Configure RocksDB state store on Databricks](https://docs.databricks.com/aws/en/structured-streaming/rocksdb-state-store)).
For older runtimes the RocksDB page sets `com.databricks.sql.streaming.state.RocksDBStateStoreProvider`; open-source
Spark's class is `org.apache.spark.sql.execution.streaming.state.RocksDBStateStoreProvider`, which the Databricks
`transformWithState` page also uses. "The state management scheme can't be
changed between query restarts"; switching needs a new checkpoint
([stateful streaming](https://docs.databricks.com/aws/en/structured-streaming/stateful-streaming)).

Here is the checkpoint of the bounded dedup query with each provider (partition 0 only):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
HDFS-backed (open-source default)          RocksDB
state/                                     state/
state/0/0/                                 state/0/0/
state/0/0/1.delta ... state/0/0/6.delta    state/0/0/1.zip
state/0/0/_metadata/schema                 state/0/0/2.zip
                                           state/0/0/_metadata/schema
```

`state/0` is operator 0, the next level is the shuffle partition, the files are versions (one per batch for the
HDFS-backed store, snapshots for RocksDB), and `_metadata/schema` stores the key and value schema. That stored schema is
what makes a changed query fail.

### Reading the state

You can read state as a table with a batch query; on Databricks also as the SQL function `read_statestore`
([Read Structured Streaming state information](https://docs.databricks.com/aws/en/structured-streaming/read-state),
which lists runtime and access-mode requirements and says it does not work for Lakeflow pipelines, streaming tables or
materialized views). Open-source Spark marks this data source experimental.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
st = spark.read.format("statestore").load(f"{base}/chk/dedup_within")
st.select("key", "value").orderBy("key").show(truncate=False)
```

```text
-- dedup_nowm: 5 keys in state
+--------------+------+
|key           |value |
+--------------+------+
|{1401, PLACED}|{NULL}|
|{1402, PLACED}|{NULL}|
|{1403, PLACED}|{NULL}|
|{1404, PLACED}|{NULL}|
|{1405, PLACED}|{NULL}|
+--------------+------+

-- dedup_within: 2 keys in state
+--------------+------------------+
|key           |value             |
+--------------+------------------+
|{1404, PLACED}|{1772368200000000}|
|{1405, PLACED}|{1772368260000000}|
+--------------+------------------+
```

The unbounded dedup remembers every key; the bounded one keeps two keys, each with an expiry time in microseconds
(1772368200000000 is 2026-03-01 12:30 UTC: the 12:00 order plus the 30-minute delay).

### Changing a stateful query

Version 1 counts orders per day. Version 2 adds a revenue sum, version 3 adds `currency` to the grouping key, and
version 4 only adds a filter. Each restarts on version 1's checkpoint:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
v1 = stream(agg_dir).groupBy(F.to_date("order_ts").alias("day")).agg(F.count("*").alias("orders"))
v2 = (stream(agg_dir).groupBy(F.to_date("order_ts").alias("day"))
      .agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue")))
v3 = (stream(agg_dir).groupBy(F.to_date("order_ts").alias("day"), "currency")
      .agg(F.count("*").alias("orders")))
v4 = (stream(agg_dir).where("amount > 0")
      .groupBy(F.to_date("order_ts").alias("day")).agg(F.count("*").alias("orders")))
```

```text
   restart with an added aggregate: [STREAM_FAILED] Query [...] terminated with exception: [STATE_STORE_VALUE_SCHEMA_NOT_COMPATIBLE] Provided value schema does not match existing state value schema. Please check number and type of fields. Existing value_schema=StructType(StructField(count,LongType,false)) and new value_schema=StructType(StructField(count,LongType,false),StructField(sum,DecimalType(20,2),true),StructField(isEmpty,BooleanType,false)). If you want to force running the query without schema validation, please set spark.sql.streaming.stateStore.stateSchemaCheck to false. However, please note that running the query with incompatible schema could cause non-deterministic behavior. ...
   restart with an added grouping key: [STREAM_FAILED] Query [...] terminated with exception: [STATE_STORE_KEY_SCHEMA_NOT_COMPATIBLE] Provided key schema does not match existing state key schema. Please check number and type of fields. Existing key_schema=StructType(StructField(_groupingexpression,DateType,true)) and new key_schema=StructType(StructField(_groupingexpression,DateType,true),StructField(currency,StringType,true)). ...
   batch 1:
      {'day': datetime.date(2026, 3, 1), 'orders': 2}
   (v4 added only a filter: it restarts and continues)
```

This is the Databricks rule in action: "any changes (that is, additions, deletions, or schema modifications) to the
stateful operations of a streaming query are not allowed between restarts"
([checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints)). Do not reach for
`stateSchemaCheck=false`; the message itself warns of non-deterministic behavior. The real options:

1. Start the new version with a new checkpoint and rebuild its output from the source (a full refresh), if the source
   still holds all the history (Delta retention, Kafka retention).
2. Start the new version with a new checkpoint writing to a new table, from a chosen point (`startingVersion` on a
   Delta source), and keep the old table for the past.
3. For custom state, `transformWithState` supports state schema evolution.

!!! warning "Access modes and dedup state"
    Databricks warns that `dropDuplicates()` and `dropDuplicatesWithinWatermark()` "can fail to restart due to a state
    schema compatibility check when changing between compute access modes". Moving between dedicated and no isolation,
    or between standard and serverless, is allowed; do not try other combinations
    ([checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints)).

## 11.13 Monitoring and running streams in production

*Level: expert.*

Every micro-batch produces a **progress report** (`StreamingQueryProgress`). You read it three ways:
`query.lastProgress` and `query.recentProgress` in code, a **`StreamingQueryListener`** that receives events for every
query in the session, and, on Databricks, the **Streaming** tab of the Spark UI. Give each query a `.queryName(...)` so you can tell them apart
([Monitoring Structured Streaming queries on Databricks](https://docs.databricks.com/aws/en/structured-streaming/stream-monitoring)).

The run below attaches a listener and an **observable metric**: `observe()` adds named aggregates that are computed
for each micro-batch and reported with its progress, which makes a cheap data quality counter.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql.streaming import StreamingQueryListener

class OrdersListener(StreamingQueryListener):
    def onQueryStarted(self, event):
        events.append(f"started   name={event.name}")
    def onQueryProgress(self, event):
        p = event.progress
        obs = p.observedMetrics.get("orders_quality")
        events.append(f"progress  batch={p.batchId} rows={p.numInputRows} "
                      f"observed={obs.asDict() if obs else None}")
    def onQueryIdle(self, event):
        events.append("idle")
    def onQueryTerminated(self, event):
        events.append(f"terminated exception={event.exception}")

spark.streams.addListener(OrdersListener())

orders = (spark.readStream.format("json").schema(ORDER_SCHEMA).load(landing)
          .observe("orders_quality",
                   F.count(F.lit(1)).alias("rows"),
                   F.count_if(F.col("amount") <= 0).alias("bad_amount"),
                   F.count_if(F.col("customer_id").isNull()).alias("no_customer")))
q = (orders.writeStream.format("delta").queryName("bronze_orders_ingest")
     .option("checkpointLocation", f"{base}/chk/bronze_orders")
     .trigger(availableNow=True).toTable("bronze_orders"))
q.awaitTermination()
```

```text
== lastProgress (selected fields)
name: bronze_orders_ingest | batchId: 0 | numInputRows: 3
inputRowsPerSecond / processedRowsPerSecond present: True / True
observedMetrics: {'orders_quality': Row(rows=3, bad_amount=1, no_customer=1)}
sources[0].numInputRows: 3
durationMs: ['addBatch', 'commitOffsets', 'getBatch', 'latestOffset', 'queryPlanning', 'triggerExecution', 'walCommit']

== Listener events
  started   name=bronze_orders_ingest
  progress  batch=0 rows=3 observed={'rows': 3, 'bad_amount': 1, 'no_customer': 1}
  terminated exception=None
```

What to watch, with the field names from the Databricks metrics reference:

| Question | Metric |
| --- | --- |
| Is it keeping up? | `inputRowsPerSecond` against `processedRowsPerSecond`; `durationMs.triggerExecution` against the trigger interval |
| How far behind is it? | Kafka: `avgOffsetsBehindLatest`, `maxOffsetsBehindLatest`, `estimatedTotalBytesBehindLatest`; Delta: `numFilesOutstanding`, `numBytesOutstanding` |
| Is state growing? | `stateOperators.numRowsTotal`, `memoryUsedBytes`, `numRowsDroppedByWatermark` |
| Is the watermark moving? | `eventTime.watermark`, `eventTime.max` |
| Is the data sane? | your `observedMetrics` |

Facts from the same page worth knowing: `id` "persists across restarts" while `runId` is new on every start; in retries
"a given batch ID may be executed more than once"; `onQueryIdle` is delivered when the query waits for data; and
listener code should stay light, because "Processing latency with listeners can significantly affect query processing
speeds". `StreamingQueryListener` is available in Python and Scala in Databricks Runtime 11.3 LTS and above.

Production habits from Databricks
([Production considerations for Structured Streaming](https://docs.databricks.com/aws/en/structured-streaming/production)):

- Run streams as scheduled Lakeflow Jobs (formerly Databricks Jobs) on jobs compute or as Lakeflow pipelines, not on
  all-purpose compute, and configure them to restart automatically on failure (the docs recommend the job's
  continuous mode for always-on streams).
- In jobs, do not call `awaitTermination()`; the jobs service already keeps the run alive while a stream is active.
  Use it in local programs and interactive notebooks.
- After an out-of-memory failure on an oversized micro-batch, the restart reruns the same planned batch, so lowering
  the rate limit does not help that batch; "you might need to scale up the compute".

## 11.14 Practice questions

*Level: mixed.*

**Q1. In one or two sentences, what is the "unbounded table" model of Structured Streaming?**

??? success "Answer"
    New data is treated as rows appended to an endless input table. You write a normal query over it, and Spark runs
    that query incrementally, each trigger processing only the new rows and updating a result table that a sink
    receives.

    **Why:** it is why the same DataFrame or SQL code works for batch and streaming, and why only some operations
    (sorting, `limit`, outer joins without bounds) are restricted: they cannot be computed incrementally.

**Q2. A file stream fails with "Schema must be specified when creating a streaming source DataFrame". Why, and what
are the fixes?**

??? success "Answer"
    The open-source file source cannot infer a schema for a stream. Pass one with `.schema(...)` (a DDL string or a
    `StructType`). Alternatively infer it once from existing files with a batch read and reuse it, or on Databricks use
    Auto Loader, which infers and evolves the schema and stores it.

    **Why:** the files that would define the schema may not exist yet when the stream starts; the run in 11.2 shows the
    exact message.

**Q3. Scenario: the stream restarted and reprocessed everything, and bronze now has every order twice. Why?**

??? success "Answer"
    The query started with an empty or different checkpoint: someone deleted the folder, the path changed between
    environments or runs, or no `checkpointLocation` was given and a temporary one was used. A new checkpoint is a new
    query (new id): the file source reads every file again, a Delta source reads the full snapshot, and the Delta sink
    does not skip anything because the transaction id is new. To repair, deduplicate bronze (or rebuild it), then keep
    one fixed checkpoint per query.

    **Why:** section 11.3's run deleted the checkpoint and got 14 rows from 7 orders.

**Q4. Name the folders and files in a checkpoint and what each holds.**

??? success "Answer"
    `metadata` (the query id), `offsets/N` (the input range planned for batch N, the watermark and fixed SQL settings,
    written before the batch), `commits/N` (batch N finished, written after the sink write), `sources/0/` (for file
    sources: which files each batch took), and `state/` for stateful queries (state store files per operator and
    partition, with the state schema).

    **Why:** Databricks lists offsets, commits, state and metadata; the listing in 11.3 is from a real run.

**Q5. Two different streams were given the same checkpoint path by mistake. The second one writes to a new table.
What do you expect?**

??? success "Answer"
    Wrong, silent results. The second query reads the first one's offsets and believes that data is done, so it skips
    it: in 11.3, `orders_copy` received 0 rows and no error. If both run at the same time, starting the second stops the
    first (`spark.sql.streaming.stopActiveRunOnRestart` is `true` by default). Give every query its own checkpoint.

    **Why:** Databricks: "Multiple queries should never share the same location."

**Q6. What does this print? The stream has already processed every file in the folder, and no new file has
arrived.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
q = (spark.readStream.format("json").schema(ORDER_SCHEMA).load(landing)
     .writeStream.option("checkpointLocation", chk).trigger(availableNow=True).toTable("bronze_orders"))
q.awaitTermination()
print([(p["batchId"], p["numInputRows"]) for p in q.recentProgress])
```

??? success "Answer"
    One progress entry with the next batch id and 0 rows, for example `[(1, 0)]` after one earlier batch. Nothing is
    written and no batch is committed; the next run that finds data reuses that batch id.

    **Why:** this is the second run in 11.2: `[(1, 0)]`, then the third run's first batch was batch 1. The block
    itself, run here after one batch, printed `[(1, 0)]` (`src/ch11/s8_questions.out`).

**Q7. What is the difference between `trigger(availableNow=True)` and `trigger(once=True)`?**

??? success "Answer"
    Both process what is available and stop. `once` does it in a single micro-batch and is deprecated (Databricks
    Runtime 11.3 LTS and above). `availableNow` splits the backlog into several batches by the source's rate limits,
    processes uncommitted batches first, advances the watermark per batch and runs a final no-data batch so stateful
    results come out.

    **Why:** one huge batch can run out of memory on a large backlog; rate-limited batches cannot.

**Q8. Scenario: an always-on stream with no trigger set reads a landing folder that gets three files a day. The
cloud bill shows millions of storage list requests. Why, and what would you change?**

??? success "Answer"
    No trigger means `processingTime` 0: the query checks for new data every few milliseconds, all day. Run it as a
    scheduled job with `availableNow` (for example hourly), or at least set a `processingTime` interval that matches
    how fresh the data must be.

    **Why:** Databricks warns that the default "can generate a high volume of cloud storage API calls per day and
    result in unexpected charges".

**Q9. A job on serverless compute fails with `INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED`. Why?**

??? success "Answer"
    Serverless notebooks and jobs support only `Trigger.AvailableNow()` (recommended) and the deprecated
    `Trigger.Once()`. The query used the default or a `processingTime` trigger. Set `availableNow=True`; for
    continuous processing on serverless, use a Lakeflow pipeline (formerly Delta Live Tables,
    [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) in continuous mode.

    **Why:** from the Databricks serverless limitations page.

**Q10. Real-time mode and continuous processing both sound "continuous". What is the difference on Databricks?**

??? success "Answer"
    Continuous processing (`trigger(continuous=...)`) is Apache Spark's experimental mode; Databricks does not support
    it. Real-time mode (`trigger(realTime=...)`) is Databricks' low-latency mode, with end-to-end latency "as low as
    five milliseconds", for operational workloads; it needs dedicated compute. A Lakeflow pipeline's (formerly Delta
    Live Tables) "continuous" pipeline mode is a third, unrelated thing.

    **Why:** the triggers page says the continuous trigger is "Not supported" and points to real-time mode.

**Q11. You must run a Kafka-to-bronze stream hourly without large batches after a weekend outage. Which options do
you set?**

??? success "Answer"
    `trigger(availableNow=True)` from a scheduled job, plus `maxOffsetsPerTrigger` on the Kafka source to cap each
    micro-batch. The backlog is processed in several bounded batches, then the query stops.

    **Why:** Databricks recommends Kafka with `AvailableNow` for incremental batch loading; `maxOffsetsPerTrigger` is
    Kafka's admission control. (`maxFilesPerTrigger` and `maxBytesPerTrigger` are for files, Delta and Auto Loader.)

**Q12. What do `maxFilesPerTrigger` and `maxBytesPerTrigger` do on a Delta source, and what are the defaults?**

??? success "Answer"
    They cap each micro-batch: `maxFilesPerTrigger` by number of new files (default 1000), `maxBytesPerTrigger` by
    approximate size (no default; a soft limit that can be exceeded so the stream makes progress). With both, the batch
    stops at whichever is reached first. You can change them between runs with the same checkpoint.

    **Why:** from the Delta streaming page. On the open-source file source the two cannot be combined.

**Q13. Which output modes can you use for `orders.groupBy("customer_id").count()` written to a Delta table, and why?**

??? success "Answer"
    Only complete. Append is refused for an aggregation without a watermark (the rows can still change), and update is
    not supported by the Delta sink. For update semantics into Delta, write with `foreachBatch` and `MERGE` in update
    mode.

    **Why:** both errors are in 11.5: `STREAMING_OUTPUT_MODE.UNSUPPORTED_OPERATION` and `DELTA_UNSUPPORTED_OUTPUT_MODE`.

**Q14. Why does a windowed aggregation in append mode write nothing for a while, even though data is flowing?**

??? success "Answer"
    Append mode writes a window only when it is final, that is when the watermark passes the window's end. With a
    10-minute window and a 10-minute watermark, the 10:00-10:10 window comes out only after an event at 10:20 or later
    has been seen and a batch has run with the new watermark.

    **Why:** Databricks: "All writes are delayed based on the lateness threshold." In 11.6 the 10:00-10:10 window
    appeared in run 2, not run 1.

**Q15. Find the bug.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
counts = (orders.groupBy(F.window("order_ts", "10 minutes")).count()
          .withWatermark("order_ts", "10 minutes"))
counts.writeStream.outputMode("append").toTable("gold_orders_10min")
```

??? success "Answer"
    The watermark is applied after the aggregation, and on a column that no longer exists in the result. It must come
    before the aggregation, on the column the window uses. Run here, the bug fails at once with
    ``[UNRESOLVED_COLUMN.WITH_SUGGESTION] A column, variable, or function parameter with name `order_ts` cannot be
    resolved``, because the aggregate has only `window` and `count`. The fix:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    counts = (orders.withWatermark("order_ts", "10 minutes")
              .groupBy(F.window("order_ts", "10 minutes")).count())
    ```

    Also set a `checkpointLocation`.

    **Why:** the Spark guide's conditions: "`withWatermark` must be called before the aggregation" and on the same
    column as the aggregation's timestamp.

**Q16. The latest event time seen is 10:26 and the watermark delay is 10 minutes. In the next micro-batch, an order at
10:05 and one at 10:18 arrive, for 10-minute tumbling windows. What happens to each?**

??? success "Answer"
    The watermark in force is 10:16. The 10:05 order belongs to window 10:00-10:10, which ended before 10:16: it is
    dropped. The 10:18 order belongs to 10:10-10:20, which ends after 10:16: it is still open, so the order is counted.

    **Why:** watermark = max event time - delay, computed after the previous batch; windows ending before it are
    closed. This is run 3 of 11.6 (10:05 dropped).

**Q17. The same three files gave 3 orders for 10:00-10:10 in the scheduled runs and 4 orders in a replay. Which result
is wrong?**

??? success "Answer"
    Neither is a bug; they differ because of batch boundaries. In the replay all files were in one micro-batch, so
    there was no earlier watermark and the 10:05 order was not late. In the scheduled runs it arrived after the
    watermark had moved to 10:16 and was dropped.

    **Why:** the watermark guarantee is one-sided: data more delayed than the threshold "may or may not get
    aggregated". If every late row must count, use a longer watermark or a batch recomputation (a materialized view).

**Q18. In the demo, complete mode counted the too-late 10:05 order. Why?**

??? success "Answer"
    Complete mode keeps all aggregation state forever and rewrites the whole result, so no window is ever closed and
    nothing is dropped as late. The price is unbounded state.

    **Why:** Databricks: in complete mode "Aggregation state isn't dropped."

**Q19. What is the difference between `dropDuplicates(["order_id"])`, `withWatermark(...).dropDuplicates(["order_id",
"order_ts"])` and `withWatermark(...).dropDuplicatesWithinWatermark(["order_id"])` on a stream?**

??? success "Answer"
    The first keeps every key seen in state forever (correct, unbounded). The second is bounded by the watermark but
    only catches duplicates with the same timestamp. The third (Databricks Runtime 13.3 LTS and above) deduplicates on
    `order_id` even when the timestamps differ, and drops each key from state once the watermark passes; set the delay
    longer than the largest time gap between duplicates.

    **Why:** in 11.11 the unbounded state went 2, 3, 5 rows; the bounded one ended at 2.

**Q20. Write the PySpark that deduplicates order events by `order_id` and `status`, where a resend can arrive up to
an hour later with a new `order_ts`, and appends the result to `silver_order_events`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    (spark.readStream.table("bronze_orders")
       .withWatermark("order_ts", "2 hours")
       .dropDuplicatesWithinWatermark(["order_id", "status"])
       .writeStream
       .option("checkpointLocation", "/Volumes/shop/silver/checkpoints/order_events")
       .trigger(availableNow=True)
       .toTable("silver_order_events"))
    ```

    **Why:** the watermark delay (2 hours) is longer than the largest gap between duplicates (1 hour), as Databricks
    advises; the event time can differ between copies, which `dropDuplicates` with the timestamp in the key would
    miss. Run here with a local checkpoint folder on a resend 40 minutes later with a new `order_ts`, it kept one
    row per `(order_id, status)` (`src/ch11/s8_questions.out`).

**Q21. A stream-static join enriches orders with `products`. A product row is fixed in the dimension. Which orders see
the fix?**

??? success "Answer"
    Only orders processed after the fix. Each micro-batch joins its new rows to the current version of the static
    table; rows already written are never revisited. In 11.11 order 1603 kept `name = None`.

    **Why:** stream-static joins are stateless. If old facts must reflect dimension changes, use a materialized view or
    a separate repair job.

**Q22. A left outer stream-stream join of orders to payments shows no unpaid orders (rows with NULL payment) even
hours later. Why?**

??? success "Answer"
    An unmatched row is emitted only when the watermark passes its time limit (order time plus the join's time range).
    The global watermark is the minimum of both inputs' watermarks, so if the payments stream is quiet or behind, the
    watermark does not move and outer rows wait. Check `eventTime.watermark`; the Spark guide warns that outer output
    may be delayed if an input receives no data. If you set no watermark at all, the query is refused.

    **Why:** in 11.11, order 1703's NULL row came out only in run 3, when the watermark reached 12:00.

**Q23. Scenario: we changed the aggregation (added a `sum`) and the stream fails on restart. Why, and what are the
options?**

??? success "Answer"
    The stored state schema no longer matches: the error is `STATE_STORE_VALUE_SCHEMA_NOT_COMPATIBLE` (or
    `..._KEY_SCHEMA_...` for a new grouping key). Changing stateful operations between restarts is not allowed. Options:
    a new checkpoint plus a full rebuild from the source (if retention allows), or a new checkpoint writing to a new
    table from a chosen starting point while the old table keeps history. Do not disable the schema check.

    **Why:** run in 11.12; a filter-only change (v4) restarted fine.

**Q24. You raised `spark.sql.shuffle.partitions` from 200 to 400 for a slow stateful stream. Nothing changed. Why?**

??? success "Answer"
    The number of shuffle partitions is stored in the checkpoint (it is in the `conf` of each `offsets/N` file) and
    fixed when the checkpoint is created. A new checkpoint is needed, or, in Databricks Runtime 18 LTS and above, on-demand
    state repartitioning.

    **Why:** Databricks: "Changing `spark.sql.shuffle.partitions` has no effect on a streaming query that already has a
    checkpoint."

**Q25. Where is streaming state stored on Databricks, and what does RocksDB change?**

??? success "Answer"
    In a state store per operator and partition, checkpointed to the `state/` folder of the checkpoint. RocksDB keeps
    state in native memory and local disk instead of the JVM heap, avoiding garbage collection pauses with many keys;
    it is the default provider in Databricks Runtime 17.3 LTS and above, with changelog checkpointing on by default.
    The provider cannot be changed for an existing checkpoint.

    **Why:** from the RocksDB and stateful streaming pages.

**Q26. Why must every Delta `MERGE` run from a stream go through `foreachBatch`, and what must you check in it?**

??? success "Answer"
    There is no streaming `MERGE` sink; `foreachBatch` gives you each micro-batch as a batch DataFrame, on which
    `MERGE` works. Check that: the batch is deduplicated per key before the `MERGE`, empty batches are handled, the
    `MERGE` is idempotent (a guard such as `WHEN MATCHED AND s.order_ts > t.order_ts`), and SQL uses
    `batch_df.sparkSession`.

    **Why:** Databricks: "You must use `foreachBatch` for Delta Lake merge operations"; restarts can apply the same batch
    twice.

**Q27. Find the bug: a `foreachBatch` function appends each batch to two Delta tables. After a cluster failure, one
table has duplicates.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def write_both(df, batch_id):
    df.write.format("delta").mode("append").saveAsTable("orders_log")
    df.write.format("delta").mode("append").saveAsTable("orders_audit")
```

??? success "Answer"
    `foreachBatch` is at-least-once: the batch failed after the first write and was replayed, so `orders_log` got it
    twice. Make the writes idempotent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    APP_ID = "red-rock-orders-v1"
    def write_both(df, batch_id):
        for t in ["orders_log", "orders_audit"]:
            (df.write.format("delta").mode("append")
               .option("txnAppId", APP_ID).option("txnVersion", batch_id)
               .saveAsTable(t))
    ```

    **Why:** the run in 11.9 reproduces it: the naive log had batch 1 twice, the safe one once. The fixed function,
    called twice here with `batch_id` 0, left 4 rows in each table, not 8. One `txnAppId` serves both tables, as in
    the dead-letter-queue example on the [foreachBatch page](https://docs.databricks.com/aws/en/structured-streaming/foreach),
    which writes the main table and the DLQ table with the same `app_id`. Databricks also
    recommends separate streaming writes per sink instead of several writes in one `foreachBatch`.

**Q28. A team reset a stream's checkpoint and kept the same `txnAppId`. New orders are missing from the target, with no
error. Why?**

??? success "Answer"
    A new checkpoint starts again at batch 0. Delta remembers the highest `txnVersion` committed for that `txnAppId`
    and skips any write with a version it has already seen, so the new batches were skipped, new data included. Use a
    new `txnAppId` whenever the checkpoint is reset.

    **Why:** the run in 11.9 lost order 1804 from the log this way; Databricks documents the rule.

**Q29. Explain "exactly-once end to end". What does it not cover?**

??? success "Answer"
    A replayable source (offsets that can be read again), a checkpoint with a write-ahead log of offsets and a commit
    log, and an idempotent sink together ensure that after any failure each input record affects the output once. It
    does not remove duplicates that are in the source data, and it does not hold for sinks that are only at-least-once
    (Kafka, `foreach`, an unguarded `foreachBatch`).

    **Why:** the Spark guide's definition; the Delta sink's `txn` action is shown in 11.9.

**Q30. Someone ran `UPDATE` on the bronze orders table, and the silver stream now fails with
`DELTA_SOURCE_TABLE_IGNORE_CHANGES`. Give the options.**

??? success "Answer"
    Restart with `skipChangeCommits=true` (process appends only; fix silver separately if the change matters); or
    read the change data feed and apply changes with `MERGE`; or, for small data, a full refresh (delete the downstream
    table and checkpoint and restart); or use a materialized view instead of a stream.

    **Why:** the four approaches on the Delta streaming page; a Delta streaming source expects appends only.

**Q31. What is the difference between `ignoreDeletes` and `skipChangeCommits`?**

??? success "Answer"
    `ignoreDeletes` is a legacy option that tolerates only deletes at partition boundaries (whole files removed).
    `skipChangeCommits` ignores every commit that changes existing rows (updates, deletes, merges) and still processes
    appends. In 11.7, `ignoreDeletes` survived a partition drop but failed on a single-row delete; `skipChangeCommits`
    survived both.

    **Why:** Databricks recommends `skipChangeCommits` "unless you are certain that deletes are always full partition
    drops". Neither propagates the deletes downstream.

**Q32. You start a new stream with `readChangeFeed=true` on `silver_customers`. What does the first run return?**

??? success "Answer"
    The current snapshot of the table, as `insert` rows, then later changes as `update_preimage`,
    `update_postimage` and `delete` rows with `_commit_version` and `_commit_timestamp`. To skip the snapshot, set
    `startingVersion` on the new stream.

    **Why:** run in 11.7; the CDF page states it.

**Q33. Scenario: a stream reading a Delta table was paused for six weeks. On restart it fails with
`DELTA_FILE_NOT_FOUND_DETAILED`. Why, and what now?**

??? success "Answer"
    The versions it still had to read were removed: data files by `VACUUM` (7 days by default) or log entries (30 days
    by default). It needs a full refresh (or a new stream from a chosen version plus a separate backfill). Do not set
    `spark.sql.files.ignoreMissingFiles`, which silently gives wrong results. Prevent it by running the stream within
    the retention window or raising the source's retention.

    **Why:** from the warning on the Delta streaming page.

**Q34. Scenario: how do you backfill a streaming table with three years of historical order files?**

??? success "Answer"
    In a Lakeflow pipeline (formerly Delta Live Tables,
    [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)), add a one-time append flow (`once=True`, or `ONCE` in SQL)
    that reads the historical files and appends them to the same bronze streaming table; downstream streams pick the
    rows up. Make sure the schemas match and downstream tolerates duplicates. With plain Structured Streaming, run a
    separate job with its own checkpoint (or a batch append) into the same Delta table; Delta's transaction log keeps
    concurrent writers safe. Keep the live stream's source bounded (for example `modifiedAfter` on Auto Loader) so the
    two do not overlap.

    **Why:** the Databricks backfill page uses exactly this pattern; a full refresh is the other option when logic
    changed, but it reprocesses everything.

**Q35. A Lakeflow streaming table's query changed from `LOWER(name)` to `UPPER(name)`. What do old and new rows look
like, and how do you make them consistent?**

??? success "Answer"
    Old rows stay lowercase, new rows are uppercase: each input row is processed once, with the query that was current
    then. A full refresh reprocesses all source data with the new query (if the source still has it).

    **Why:** the streaming tables page uses this example.

**Q36. Which metrics tell you a stream is falling behind, and which tell you state is growing?**

??? success "Answer"
    Falling behind: `processedRowsPerSecond` below `inputRowsPerSecond`, `durationMs.triggerExecution` longer than the
    trigger interval, Kafka `maxOffsetsBehindLatest` or `estimatedTotalBytesBehindLatest` rising, Delta
    `numFilesOutstanding` or `numBytesOutstanding` rising. State: `stateOperators.numRowsTotal` and `memoryUsedBytes`
    rising batch after batch, and an `eventTime.watermark` that does not move.

    **Why:** all are fields of `StreamingQueryProgress` documented on the Databricks monitoring page; read them from
    `lastProgress`, a `StreamingQueryListener` or the Streaming tab.

**Q37. Write a `StreamingQueryListener` that records each batch's id and row count, and say where it should send
them.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    from pyspark.sql.streaming import StreamingQueryListener

    class ProgressLogger(StreamingQueryListener):
        def onQueryStarted(self, event): pass
        def onQueryProgress(self, event):
            p = event.progress
            log(p.name, p.batchId, p.numInputRows)      # your fast sink
        def onQueryIdle(self, event): pass
        def onQueryTerminated(self, event): pass

    spark.streams.addListener(ProgressLogger())
    ```

    Send to something fast (a queue such as Kafka, or a light logging call) and keep the code small.

    **Why:** Databricks warns that listener processing latency "can significantly affect query processing speeds".
    Run here with `log` appending to a Python list, it recorded `('bronze_orders_ingest', 0, 4)`; `log` stands for
    your sink.

**Q38. In a production job, should you call `query.awaitTermination()`?**

??? success "Answer"
    Not in a job of Lakeflow Jobs (formerly Databricks Jobs, under the old Workflows menu item;
    [rename note](https://docs.databricks.com/aws/en/release-notes/product/2025/june)): the Jobs service keeps the run
    alive while a stream is active, and blocking calls interfere with its tracking of the query and its notifications. Use it in local programs (so the process does not
    exit) and in interactive notebooks.

    **Why:** from "When to use `awaitTermination()`" in the Databricks production page. The scripts in this chapter
    are local programs, so they do call it.

## Sources

- [Structured Streaming concepts](https://docs.databricks.com/aws/en/structured-streaming/concepts) (last updated Oct 27, 2026)
- [Configure Structured Streaming trigger intervals](https://docs.databricks.com/aws/en/structured-streaming/triggers) (last updated Nov 10, 2026)
- [Structured Streaming checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints) (last updated Sep 11, 2026)
- [Select an output mode for Structured Streaming](https://docs.databricks.com/aws/en/structured-streaming/output-mode) (last updated Sep 11, 2026)
- [Apply watermarks to control data processing thresholds](https://docs.databricks.com/aws/en/structured-streaming/watermarks) (last updated Sep 11, 2026)
- [What is stateful streaming?](https://docs.databricks.com/aws/en/structured-streaming/stateful-streaming) (last updated Oct 9, 2026)
- [Configure RocksDB state store on Databricks](https://docs.databricks.com/aws/en/structured-streaming/rocksdb-state-store) (last updated Nov 6, 2026)
- [Read Structured Streaming state information](https://docs.databricks.com/aws/en/structured-streaming/read-state) (last updated Sep 11, 2026)
- [Build a custom stateful application with transformWithState](https://docs.databricks.com/aws/en/stateful-applications/) (last updated Nov 6, 2026)
- [Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake) (last updated Oct 15, 2026)
- [Use foreachBatch to write to arbitrary data sinks](https://docs.databricks.com/aws/en/structured-streaming/foreach) (last updated Nov 5, 2026)
- [Configure Structured Streaming batch size on Databricks](https://docs.databricks.com/aws/en/structured-streaming/batch-size) (last updated Sep 16, 2026)
- [Monitoring Structured Streaming queries on Databricks](https://docs.databricks.com/aws/en/structured-streaming/stream-monitoring) (last updated Oct 27, 2026)
- [Production considerations for Structured Streaming](https://docs.databricks.com/aws/en/structured-streaming/production) (last updated Nov 5, 2026)
- [Real-time mode concepts](https://docs.databricks.com/aws/en/structured-streaming/real-time/) (last updated Oct 13, 2026)
- [Connect to Apache Kafka](https://docs.databricks.com/aws/en/structured-streaming/kafka) (last updated Sep 11, 2026)
- [Work with joins on Databricks](https://docs.databricks.com/aws/en/transform/join) (last updated Sep 11, 2026)
- [Use change data feed on Databricks](https://docs.databricks.com/aws/en/delta/delta-change-data-feed) (last updated Oct 9, 2026)
- [Serverless compute limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations) (last updated Nov 5, 2026)
- [What is Auto Loader?](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/) (last updated Oct 15, 2026)
- [Load data in pipelines](https://docs.databricks.com/aws/en/ldp/load) (last updated Oct 19, 2026)
- [Streaming tables](https://docs.databricks.com/aws/en/ldp/streaming-tables) (last updated Oct 9, 2026)
- [Full refresh for streaming tables](https://docs.databricks.com/aws/en/ldp/full-refresh-st) (last updated Sep 11, 2026)
- [Backfilling historical data with pipelines](https://docs.databricks.com/aws/en/ldp/flows-backfill) (last updated Oct 5, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026)
- [Structured Streaming Programming Guide: getting started, Apache Spark 4.2.0](https://spark.apache.org/docs/4.2.0/streaming/getting-started.html) (no last-updated date shown; version 4.2.0)
- [Structured Streaming Programming Guide: APIs on DataFrames and Datasets, Apache Spark 4.2.0](https://spark.apache.org/docs/4.2.0/streaming/apis-on-dataframes-and-datasets.html) (no last-updated date shown; version 4.2.0)
- [Spark Configuration, Apache Spark 4.2.0](https://spark.apache.org/docs/4.2.0/configuration.html) (no last-updated date shown; version 4.2.0)
- [pyspark.sql.DataFrame.dropDuplicatesWithinWatermark, PySpark 4.2.0](https://spark.apache.org/docs/4.2.0/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.dropDuplicatesWithinWatermark.html) (no last-updated date shown; version 4.2.0)
