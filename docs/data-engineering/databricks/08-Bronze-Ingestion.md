# 8. Into bronze: ingestion

*Every pipeline starts by getting data in: files dropped in cloud storage, rows changing in an operational
database, records from a SaaS application, messages on a Kafka topic. This chapter covers the Databricks ways to do
that and how to choose between them, then goes deep on the one interviewers ask about most, Auto Loader: schema
inference and evolution, the rescued data column, file detection modes, backfills, rate limits and the checkpoint
that gives exactly-once loading. It also covers `COPY INTO`, `read_files` and streaming tables, the `_metadata`
column, Kafka, Lakeflow Connect managed connectors, how to design the bronze table, and what goes wrong. Auto
Loader exists only on Databricks, so the core behavior (each file loaded once across runs, corrupt records kept,
duplicates from renamed files) is shown with the open-source file source on Spark 4.2, with every difference
stated.*

!!! abstract "In this chapter"
    **You will learn:**

    - the ingestion options (managed connectors, Auto Loader, `COPY INTO`, `read_files`, streaming tables, Kafka and
      other message buses, file upload, Lakehouse Federation) and the official guidance for choosing
    - where files should land: Unity Catalog volumes and external locations
    - Auto Loader in depth: `cloudFiles`, `schemaLocation`, inference (strings by default), schema hints, evolution,
      the rescued data column, directory listing vs file notification with file events, backfills, triggers, rate
      limits, `includeExistingFiles`, `cleanSource`, and how the checkpoint gives exactly-once file loading
    - `COPY INTO` (now labelled legacy on two official pages), its options, and when to use it instead of Auto Loader
    - `read_files` in batch SQL and with `STREAM` in streaming tables, and the defaults that differ from Auto Loader
    - the `_metadata` column and the ingest metadata columns every bronze table should carry
    - the shape of Kafka rows and how to parse them, and what Lakeflow Connect does for databases and SaaS apps
    - how to design a bronze table, keep reruns and replays safe, and diagnose the common failures

    **You need:** [7. The medallion architecture](07-Medallion-Architecture.md) (what bronze is for, the schema
    evolution modes table, the rescued data column), [4. Delta Lake](04-Delta-Lake.md) and
    [5. Unity Catalog](05-Unity-Catalog.md) (volumes, external locations). [11. Structured
    Streaming](11-Structured-Streaming.md) explains checkpoints and triggers in general.

    **Levels:** sections 8.1 to 8.3 beginner, 8.4 to 8.11 intermediate, 8.12 to 8.14 expert.

## 8.1 The ingestion problem and the options

*Level: beginner.*

Red Rock Supply has four kinds of incoming data. The web shop writes one JSON file of orders every few minutes to
cloud storage. Customer records live in a PostgreSQL database that changes all day. Support tickets live in a SaaS
application. The warehouse scanners publish stock movements to a Kafka topic. Each needs a different tool, and the
interview question is rarely "what is Auto Loader" but "which tool would you use here, and why".

Databricks groups its ingestion tools under the name **Lakeflow Connect**. Its overview page organizes connectors by
source type: database connectors (MySQL, PostgreSQL, Oracle and SQL Server, using change data capture), SaaS
connectors (Salesforce, HubSpot, Jira, Workday and many more), file connectors (cloud object storage and services
such as Google Drive and SharePoint), streaming connectors (message buses such as Kafka and RabbitMQ), query-based
connectors (query a database directly, without change data capture), and direct write with the Zerobus Ingest API.

The same page describes **layers of the ETL stack**, and gives the one rule worth quoting in an interview:
"Databricks recommends starting with the most managed layer. If it doesn't satisfy your requirements (for example,
if it doesn't support your data source), drop down to the next layer." The layers, from most customizable to most
managed, per the "Ingest with SQL and Spark APIs" page:

| Layer | What it is | What you manage |
| --- | --- | --- |
| Structured Streaming | The Spark streaming engine, "end-to-end fault tolerance with exactly-once processing guarantees" | Code, checkpoints, schema location, scheduling, retries |
| Lakeflow pipelines (formerly Delta Live Tables) | "extend Structured Streaming, offering a declarative framework"; they manage "orchestration, monitoring, data quality, errors, and more" | The dataset definitions |
| Managed connectors | "build on Lakeflow pipelines", adding "source-specific authentication, CDC, edge case handling, long-term API maintenance, automated retries, automated schema evolution" | Mostly configuration |

For files and message buses, the "Choose an option" table on that page crosses source with how much customization
you want:

| Source | More customization | Some customization | More automation |
| --- | --- | --- | --- |
| Cloud object storage | Auto Loader with Structured Streaming (Python, Scala) | Auto Loader with Lakeflow pipelines (Python, SQL) | Auto Loader with Databricks SQL (SQL) |
| SFTP servers | Ingest files from SFTP servers (Python, SQL) | N/A | N/A |
| Apache Kafka, Amazon Kinesis, Google Pub/Sub, Apache Pulsar | Structured Streaming with that source (Python, Scala) | Lakeflow pipelines with that source (Python, SQL) | Databricks SQL with that source (SQL) |

Two sentences from that page settle the `COPY INTO` question before we reach it: "SQL examples for incremental
ingestion from cloud object storage use `CREATE STREAMING TABLE` syntax. It offers SQL users a scalable ingestion
experience, therefore it's the recommended alternative to `COPY INTO`."

The other options on the Lakeflow Connect overview page:

- **Create or modify a table using file upload** (the Add data UI): upload small CSV, TSV, JSON, Avro, Parquet,
  Excel or text files from your computer into a managed Delta table. Limits on that page: up to 10 files at a time,
  total under 2 gigabytes, no `zip` or `tar`. Good for a one-off lookup table, not for a pipeline.
- **Ingestion partners and DIY ingestion**: third-party tools, or your own code in any language Databricks runs.
- **Ingestion alternatives**: if you do not want to copy the data at all, **Lakehouse Federation** lets you "query
  external data sources without moving your data", and **OpenSharing** (formerly Delta Sharing) shares data across
  platforms. The federation page adds: "When your source supports both Lakehouse Federation and Lakeflow Connect,
  Databricks recommends Lakeflow Connect if performance on higher data volumes and lower latency are priorities."

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 380" role="img" aria-label="Ingestion options map: SaaS apps and databases go through Lakeflow Connect managed connectors, files in cloud storage through Auto Loader, read_files or COPY INTO, message buses through the Kafka, Kinesis or Pub/Sub sources, laptop files through the file upload UI, all landing in bronze Delta tables; an external database can instead be queried in place with Lakehouse Federation">
<g fill="currentColor" font-size="13" text-anchor="middle" font-weight="bold">
<text x="90" y="18">Source</text>
<text x="335" y="18">Tool</text>
<text x="570" y="18">Lands in</text>
</g>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="10" y="30" width="160" height="40" rx="5"/>
<rect x="10" y="82" width="160" height="40" rx="5"/>
<rect x="10" y="134" width="160" height="40" rx="5"/>
<rect x="10" y="186" width="160" height="40" rx="5"/>
<rect x="10" y="238" width="160" height="40" rx="5"/>
<rect x="10" y="300" width="160" height="40" rx="5"/>
<rect x="200" y="30" width="270" height="40" rx="5"/>
<rect x="200" y="82" width="270" height="40" rx="5"/>
<rect x="200" y="134" width="270" height="40" rx="5"/>
<rect x="200" y="186" width="270" height="40" rx="5"/>
<rect x="200" y="238" width="270" height="40" rx="5"/>
<rect x="200" y="300" width="270" height="40" rx="5" stroke-dasharray="5 4"/>
<rect x="510" y="30" width="120" height="248" rx="6"/>
<rect x="510" y="300" width="120" height="40" rx="5" stroke-dasharray="5 4"/>
<line x1="170" y1="50" x2="192" y2="50"/>
<line x1="170" y1="102" x2="192" y2="102"/>
<line x1="170" y1="154" x2="192" y2="154"/>
<line x1="170" y1="206" x2="192" y2="206"/>
<line x1="170" y1="258" x2="192" y2="258"/>
<line x1="170" y1="320" x2="192" y2="320"/>
<line x1="470" y1="50" x2="502" y2="50"/>
<line x1="470" y1="102" x2="502" y2="102"/>
<line x1="470" y1="154" x2="502" y2="154"/>
<line x1="470" y1="206" x2="502" y2="206"/>
<line x1="470" y1="258" x2="502" y2="258"/>
<line x1="470" y1="320" x2="502" y2="320"/>
</g>
<g fill="currentColor">
<polygon points="200,50 191,45 191,55"/>
<polygon points="200,102 191,97 191,107"/>
<polygon points="200,154 191,149 191,159"/>
<polygon points="200,206 191,201 191,211"/>
<polygon points="200,258 191,253 191,263"/>
<polygon points="200,320 191,315 191,325"/>
<polygon points="510,50 501,45 501,55"/>
<polygon points="510,102 501,97 501,107"/>
<polygon points="510,154 501,149 501,159"/>
<polygon points="510,206 501,201 501,211"/>
<polygon points="510,258 501,253 501,263"/>
<polygon points="510,320 501,315 501,325"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="90" y="55">SaaS application</text>
<text x="90" y="107">Database (CDC)</text>
<text x="90" y="159">Cloud storage files</text>
<text x="90" y="211">Message bus</text>
<text x="90" y="263">Files on a laptop</text>
<text x="90" y="325">External database</text>
<text x="335" y="55">Lakeflow Connect SaaS connector</text>
<text x="335" y="107">Lakeflow Connect database connector</text>
<text x="335" y="159">Auto Loader, read_files, COPY INTO</text>
<text x="335" y="211">Kafka, Kinesis, Pub/Sub source</text>
<text x="335" y="263">File upload (Add data UI)</text>
<text x="335" y="325">Lakehouse Federation</text>
<text x="570" y="146">Bronze</text>
<text x="570" y="164">Delta tables</text>
<text x="570" y="318">No copy:</text>
<text x="570" y="334">query in place</text>
</g>
</svg>
<figcaption>Figure 8.1. The ingestion options by source. Everything above the dashed row copies data into bronze
tables; Lakehouse Federation queries the source where it lives. Start with the most managed tool that supports the
source.</figcaption>
</figure>

A decision table you can say out loud:

| Situation | First choice | Why |
| --- | --- | --- |
| SaaS app or relational database with a managed connector | Lakeflow Connect managed connector | Handles authentication, CDC, retries and schema evolution for you |
| Files arriving continuously or on a schedule in S3, ADLS, GCS or a volume | Auto Loader in a Lakeflow pipeline (Python) or a streaming table with `STREAM read_files` (SQL) | Incremental, each file once, schema inference and evolution |
| Same, but you need full control of the stream code | Auto Loader with Structured Streaming | "More customization" column of the table above |
| Kafka, Kinesis, Pub/Sub, Pulsar | The Structured Streaming source, in a pipeline or streaming table where possible | Message bus sources keep offsets in the checkpoint |
| A few thousand files, loaded by a SQL user, re-run safely | `COPY INTO` still works, but the docs recommend streaming tables instead | See 8.8 |
| A one-off small file from a laptop | File upload UI | No pipeline needed |
| Ad hoc reads of an operational database, no copy wanted | Lakehouse Federation | Query in place, read-only |

!!! tip "In the interview"
    **"How do you get data into Databricks?"** Start from the source. Databricks' own rule is to start with the most
    managed layer and drop down only when it does not fit: a Lakeflow Connect managed connector for supported SaaS
    apps and databases, Auto Loader (in a Lakeflow pipeline, formerly Delta Live Tables, per
    [What happened to DLT?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt), or a streaming table) for
    files in cloud storage, the Kafka or Kinesis source for message buses, and plain Structured Streaming when you
    need full control. `COPY INTO` is the older SQL command; for SQL users the docs now recommend streaming tables.

## 8.2 Where files land: volumes and external locations

*Level: beginner.*

Files from outside systems need a governed landing place. In Unity Catalog there are two (chapter
[5. Unity Catalog](05-Unity-Catalog.md) covers them fully):

- An **external location** links a cloud storage path (for example `s3://rrs-landing/`) with a storage credential,
  and Unity Catalog grants privileges on it, such as `READ FILES`.
- A **volume** is a catalog object at the third level of the namespace (`catalog.schema.volume`) for non-tabular
  files, read with the path `/Volumes/<catalog>/<schema>/<volume>/<path>/<file-name>`. A managed volume lives in
  Unity Catalog's managed storage; an external volume is registered on an existing cloud path. The volumes page lists
  "Register landing areas for raw data produced by external systems" and "Register staging locations for ingestion.
  For example, using Auto Loader, `COPY INTO`, or CTAS" among its use cases, and recommends external volumes for
  files that external systems also read or write.

The "Load data in pipelines" page gives the practical rule: "For files, land data in a Unity Catalog volume rather
than an ungoverned bucket path, so lineage and access control extend back to the landing zone." Two privileges matter
for reading: `read_files` needs "the `READ FILES` privilege on the external location or the `READ VOLUME` privilege on
the volume". Two features need an external location rather than just a path: file notification mode with file
events (8.6) is enabled on an external location, and the pipelines load page notes that "To load files with Auto
Loader in a Unity Catalog enabled pipeline, you must use external locations."

In the examples below the Red Rock Supply web shop writes to `/Volumes/shop/bronze/landing/orders/`, and the
checkpoints live in a separate folder of the same volume.

## 8.3 Auto Loader: the basics

*Level: beginner.*

**Auto Loader** "incrementally and efficiently processes new data files as they arrive in cloud storage". It is a
Structured Streaming source called `cloudFiles`: you give it a directory, and it processes new files as they arrive,
"with the option of also processing existing files in that directory". It reads from S3 (`s3://`), ADLS
(`abfss://`), GCS (`gs://`), Unity Catalog volumes (`/Volumes/`) and Azure Blob Storage (`wasbs://`), and ingests
`JSON`, `CSV`, `XML`, `PARQUET`, `AVRO`, `ORC`, `TEXT` and `BINARYFILE` files, including pre-compressed ones.

The minimal Red Rock Supply bronze stream, in Python with Structured Streaming:

*Databricks only, not run here. Syntax from [Configure schema inference and evolution in Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema) and [Configure Auto Loader for production workloads](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/production).*

```python
from pyspark.sql import functions as F

landing = "/Volumes/shop/bronze/landing/orders/"
meta    = "/Volumes/shop/bronze/_meta/orders/"           # schema location and checkpoint

(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "json")                  # required
    .option("cloudFiles.schemaLocation", meta)            # where the inferred schema is kept
    .load(landing)
    .select("*",
            F.col("_metadata.file_name").alias("_source_file"),
            F.col("_metadata.file_modification_time").alias("_file_modified_at"),
            F.current_timestamp().alias("_ingested_at"))
    .writeStream
    .option("checkpointLocation", meta)                   # which files are done
    .trigger(availableNow=True)                           # process what is there, then stop
    .toTable("shop.bronze.orders"))
```

Three settings carry the weight:

- **`cloudFiles.format`** is required (the options reference lists its default as "None (required option)").
- **`cloudFiles.schemaLocation`** "enables schema inference and evolution". Auto Loader stores the inferred schema in
  a `_schemas` directory there and tracks changes over time. The schema page says you "can choose to use the same
  directory you specify for the `checkpointLocation`", as above.
- **`checkpointLocation`** is the stream's memory. The Auto Loader overview: "As files are discovered, their metadata
  is persisted in a scalable key-value store (RocksDB) in the checkpoint location of your Auto Loader pipeline. This
  key-value store ensures that data is processed exactly once." After a failure, Auto Loader "can resume from where it
  left off" and "continue to provide exactly-once guarantees when writing data into Delta Lake".

The same table in a **Lakeflow pipeline** needs no schema location and no checkpoint: "You do not need to provide a
schema or checkpoint location because Lakeflow pipelines automatically manage these settings for your pipelines."
Databricks recommends this form: "Databricks recommends Auto Loader in Lakeflow pipelines for incremental data
ingestion."

*Databricks only, not run here. Syntax from [Load data in pipelines](https://docs.databricks.com/aws/en/ldp/load).*

```python
from pyspark import pipelines as dp

@dp.table
def orders_bronze():
    return (spark.readStream.format("cloudFiles")
              .option("cloudFiles.format", "json")
              .load("/Volumes/shop/bronze/landing/orders/"))
```

```sql
CREATE OR REFRESH STREAMING TABLE orders_bronze
AS SELECT * FROM STREAM read_files(
  '/Volumes/shop/bronze/landing/orders/',
  format => 'json'
);
```

(The Python form replaces the old `import dlt` and `@dlt.table`; the page "What happened to Delta Live Tables (DLT)?"
says `import dlt` "can be replaced with `from pyspark import pipelines as dp`".)

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Auto Loader flow: files in a landing folder are discovered by the cloudFiles source and written in micro-batches to a bronze Delta table; the source keeps its inferred schema in the schema location and its record of processed files in RocksDB inside the checkpoint location">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="10" y="50" width="160" height="64" rx="6"/>
<rect x="230" y="50" width="180" height="64" rx="6"/>
<rect x="470" y="50" width="160" height="64" rx="6"/>
<rect x="110" y="200" width="210" height="80" rx="6" stroke-dasharray="5 4"/>
<rect x="350" y="200" width="250" height="80" rx="6" stroke-dasharray="5 4"/>
<line x1="170" y1="82" x2="222" y2="82"/>
<line x1="410" y1="82" x2="462" y2="82"/>
<line x1="290" y1="114" x2="230" y2="192"/>
<line x1="350" y1="114" x2="460" y2="192"/>
</g>
<g fill="currentColor">
<polygon points="230,82 221,77 221,87"/>
<polygon points="470,82 461,77 461,87"/>
<polygon points="225,199 226,188 234,194"/>
<polygon points="466,199 455,194 463,188"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="196" y="40">new files</text>
<text x="436" y="40">micro-batch</text>
<text x="90" y="78">Landing folder</text>
<text x="90" y="98">volume or bucket</text>
<text x="320" y="78">Auto Loader</text>
<text x="320" y="98">format("cloudFiles")</text>
<text x="550" y="78">Bronze table</text>
<text x="550" y="98">append-only Delta</text>
<text x="215" y="224">cloudFiles.schemaLocation</text>
<text x="215" y="244">_schemas: inferred schema</text>
<text x="215" y="264">and each evolution</text>
<text x="475" y="224">checkpointLocation</text>
<text x="475" y="244">RocksDB: every file seen</text>
<text x="475" y="264">plus offsets and commits</text>
</g>
</svg>
<figcaption>Figure 8.2. Auto Loader keeps two kinds of state: the schema (in the schema location) and the list of
files already processed (in RocksDB inside the checkpoint). Lose the checkpoint and the stream forgets which files
it loaded.</figcaption>
</figure>

Why not just use Spark's own file source (`spark.readStream.format("json").load(dir)`)? The Auto Loader page lists
its benefits over it: scalability ("can discover billions of files efficiently"), performance (discovery cost "scales
with the number of files that are being ingested instead of the number of directories"), schema inference and
evolution with rescued data, and cost (native cloud listing APIs, and file notification mode that avoids listing).

!!! tip "In the interview"
    **"How does Auto Loader guarantee each file is loaded once?"** It records every discovered file in a RocksDB
    key-value store inside the stream's checkpoint location, and Structured Streaming commits each micro-batch to
    Delta together with its progress. On restart it reads the checkpoint and skips files already recorded. The
    guarantee is per file path and per checkpoint: a new checkpoint, or the same data under a new file name, is
    loaded again.

## 8.4 The pattern, run here with the open-source file source

*Level: intermediate.*

Auto Loader is not part of Apache Spark, but Spark's own streaming file source records processed files in its
checkpoint too, so the central behavior can be run here. The script `src/ch08/ch08_autoloader_emulation.py` lands
Red Rock Supply order files in a folder, then runs a bronze stream with `availableNow` several times, the way a
scheduled job would.

First the bronze table. Every payload column is `STRING` (the reason is in 8.5), followed by the corrupt record
column and the ingest metadata. `_ingest_date` is a generated column used as the clustering key:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE bronze_orders (
  order_id          STRING,
  customer_id       STRING,
  order_ts          STRING,
  status            STRING,
  amount            STRING,
  currency          STRING,
  items             STRING,
  _corrupt_record   STRING,
  _source_file      STRING,
  _file_modified_at TIMESTAMP,
  _ingested_at      TIMESTAMP,
  _ingest_date      DATE GENERATED ALWAYS AS (CAST(_ingested_at AS DATE))
) USING DELTA
CLUSTER BY (_ingest_date)
```

The stream. Unlike Auto Loader, Spark's file source needs the schema up front: the Spark guide says "Structured
Streaming from file based sources requires you to specify the schema, rather than rely on Spark to infer it
automatically".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
BRONZE_SCHEMA = ("order_id STRING, customer_id STRING, order_ts STRING, status STRING, "
                 "amount STRING, currency STRING, items STRING, _corrupt_record STRING")

def run_bronze():
    """One scheduled run: pick up every file not yet recorded in the checkpoint, then stop."""
    q = (spark.readStream
         .schema(BRONZE_SCHEMA)
         .option("columnNameOfCorruptRecord", "_corrupt_record")
         .json(LANDING)
         .select("*",
                 F.col("_metadata.file_name").alias("_source_file"),
                 F.col("_metadata.file_modification_time").alias("_file_modified_at"),
                 F.current_timestamp().alias("_ingested_at"))
         .writeStream
         .format("delta")          # open-source Spark defaults to parquet; Databricks to Delta
         .option("checkpointLocation", CHK)
         .trigger(availableNow=True)
         .toTable("bronze_orders"))
    q.awaitTermination()
    commits = sorted(int(f) for f in os.listdir(os.path.join(CHK, "commits")) if f.isdigit())
    print("micro-batches committed in the checkpoint so far:", commits)
```

**Run 1.** Two files are waiting: `orders_20260301_0900.json` (orders 1001 and 1002) and `orders_20260301_1800.json`
(order 1003).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
micro-batches committed in the checkpoint so far: [0]
>>> SELECT order_id, amount, substr(items, 1, 45) AS items_raw, _source_file, _file_modified_at FROM bronze_orders ORDER BY order_id
+--------+------+---------------------------------------------+-------------------------+-------------------+
|order_id|amount|items_raw                                    |_source_file             |_file_modified_at  |
+--------+------+---------------------------------------------+-------------------------+-------------------+
|1001    |59.90 |[{"product_id": 3, "qty": 2, "unit_price": "2|orders_20260301_0900.json|2026-03-01 09:00:00|
|1002    |120.00|[{"product_id": 8, "qty": 1, "unit_price": "1|orders_20260301_0900.json|2026-03-01 09:00:00|
|1003    |35.50 |[{"product_id": 5, "qty": 1, "unit_price": "3|orders_20260301_1800.json|2026-03-01 18:00:00|
+--------+------+---------------------------------------------+-------------------------+-------------------+
```

Declaring the nested `items` array as `STRING` kept its JSON text exactly as it arrived, spaces included.

**Run 2.** Nothing new landed. No new micro-batch was committed and the table is unchanged:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
micro-batches committed in the checkpoint so far: [0]
>>> SELECT _source_file, count(*) AS rows FROM bronze_orders GROUP BY ALL ORDER BY ALL
+-------------------------+----+
|_source_file             |rows|
+-------------------------+----+
|orders_20260301_0900.json|2   |
|orders_20260301_1800.json|1   |
+-------------------------+----+
```

**Run 3.** A new file with one good order and one line cut off mid-record:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
micro-batches committed in the checkpoint so far: [0, 1]
>>> SELECT order_id, amount, _corrupt_record, _source_file FROM bronze_orders WHERE _source_file = 'orders_20260302_0900.json'
+--------+------+-------------------------------------------------------------------------------------+-------------------------+
|order_id|amount|_corrupt_record                                                                      |_source_file             |
+--------+------+-------------------------------------------------------------------------------------+-------------------------+
|1004    |89.00 |NULL                                                                                 |orders_20260302_0900.json|
|NULL    |NULL  |{"order_id": 1005, "customer_id": 9, "order_ts": "2026-03-02T08:30:00Z", "amount": "4|orders_20260302_0900.json|
+--------+------+-------------------------------------------------------------------------------------+-------------------------+
```

Only the new file was read, and the broken line is kept whole in `_corrupt_record` with its source file, instead of
failing the stream or disappearing.

**Run 4.** The web shop re-sends the same file under a new name, `orders_20260302_0900_retry.json`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
micro-batches committed in the checkpoint so far: [0, 1, 2]
>>> SELECT order_id, count(*) AS copies, collect_list(_source_file) AS files FROM bronze_orders WHERE order_id IS NOT NULL GROUP BY order_id HAVING count(*) > 1
+--------+------+------------------------------------------------------------+
|order_id|copies|files                                                       |
+--------+------+------------------------------------------------------------+
|1004    |2     |[orders_20260302_0900_retry.json, orders_20260302_0900.json]|
+--------+------+------------------------------------------------------------+
```

A new path is a new file. Auto Loader behaves the same way: its FAQ says it "normally ingests each file only once
based on its file path". Exactly-once is about files, not about records, which is why deduplication belongs in
silver ([9. Building silver](09-Building-Silver.md)).

**Run 5.** An already loaded file is overwritten in place with a different amount for order 1001:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
micro-batches committed in the checkpoint so far: [0, 1, 2]
>>> SELECT order_id, amount, _source_file FROM bronze_orders WHERE order_id = '1001'
+--------+------+-------------------------+
|order_id|amount|_source_file             |
+--------+------+-------------------------+
|1001    |59.90 |orders_20260301_0900.json|
+--------+------+-------------------------+
```

The open-source source ignored the changed file, because its path was already recorded. Auto Loader's default
(`cloudFiles.allowOverwrites` = `false`) also processes each file once, but its FAQ is more careful: "When a file is
appended to or overwritten, Auto Loader cannot guarantee which file version will be processed." The lesson is the
same: treat landed files as immutable, and send corrections as new files.

**Run 6.** A file arrives with a new field, `"channel": "mobile"`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
micro-batches committed in the checkpoint so far: [0, 1, 2, 3]
>>> SELECT order_id, amount, _source_file FROM bronze_orders WHERE order_id = '1006'
+--------+------+-------------------------+
|order_id|amount|_source_file             |
+--------+------+-------------------------+
|1006    |15.00 |orders_20260303_0900.json|
+--------+------+-------------------------+
bronze columns: ['order_id', 'customer_id', 'order_ts', 'status', 'amount', 'currency', 'items', '_corrupt_record', '_source_file', '_file_modified_at', '_ingested_at', '_ingest_date']
```

The `channel` value is silently gone: with a fixed schema the open-source source drops unknown fields. This is the
gap Auto Loader's schema evolution and rescued data column close (8.5).

**What the checkpoint remembers.** The open-source file source writes one log file per batch under
`<checkpoint>/sources/0/`, listing the files of that batch (the full working path is shortened to `<work>` here):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
files in <checkpoint>/sources/0: ['.0.crc', '.1.crc', '.2.crc', '.3.crc', '0', '1', '2', '3']
v1
{"path":"file://<work>/landing/orders/orders_20260303_0900.json","timestamp":1772528400000,"batchId":3}
```

Auto Loader keeps the same kind of record in RocksDB instead of these log files, and on Databricks you can query it
with `SELECT * FROM cloud_files_state('path/to/checkpoint')` (available in Databricks Runtime 11.3 LTS and above, per
the production page).

| | Open-source file source (run here) | Auto Loader (`cloudFiles`, Databricks) |
| --- | --- | --- |
| Schema | Must be given (unless `spark.sql.streaming.schemaInference` is set) | Inferred and stored in `cloudFiles.schemaLocation`, or given |
| New column | Dropped silently with a fixed schema (run 6) | Default `addNewColumns`: stream fails, schema updated, restart continues |
| Unparsed data | `_corrupt_record` only | `_rescued_data` for mismatches, plus `_corrupt_record` if enabled |
| File state | Log files under `sources/` in the checkpoint | RocksDB in the checkpoint; `cloud_files_state` to inspect |
| Discovery | Spark lists the input path (the Spark guide speaks of "listing from the input source" and of the cost "to list source files") | Optimized directory listing, or file notification with file events |
| Rate limit | `maxFilesPerTrigger` or `maxBytesPerTrigger`, not both, no default limit | `cloudFiles.maxFilesPerTrigger` (default 1000) and `cloudFiles.maxBytesPerTrigger`, both allowed |
| Clean up processed files | `cleanSource` (`archive`, `delete`, default `off`) | `cloudFiles.cleanSource` (`OFF`, `MOVE`, `DELETE`), Databricks Runtime 16.4 and above |

The open-source column comes from the Spark 4.2 Structured Streaming guide; the Auto Loader column from the pages
cited in this chapter.

## 8.5 Schema inference, hints, evolution and rescued data

*Level: intermediate.*

Chapter 7 already has the evolution modes table and the rescued data column (see
[7.5 Bronze in depth](07-Medallion-Architecture.md#75-bronze-in-depth-schema-drift-and-raw-storage)). This section
adds how inference works, schema hints, and the details that show up in scenario questions.

### Inference: strings by default for JSON, CSV and XML

Verified on the schema page: "For formats that don't encode data types (JSON, CSV, and XML), Auto Loader infers all
columns as strings (including nested fields in JSON files)." Parquet and Avro keep their encoded types. The options
reference confirms `cloudFiles.inferColumnTypes` defaults to `false`; setting it to `true` gives the Spark
DataFrameReader behavior of "selecting data types for columns in JSON, CSV, and XML sources based on sample data".

The difference is easy to see here. Spark's normal JSON reader infers types; its `primitivesAsString` option turns
every leaf into a string, which is what Auto Loader's default produces:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
spark.read.json(LANDING).printSchema()
spark.read.option("primitivesAsString", "true").json(LANDING).printSchema()
```

```text
root
 |-- amount: string (nullable = true)
 |-- currency: string (nullable = true)
 |-- customer_id: long (nullable = true)
 |-- items: array (nullable = true)
 |    |-- element: struct (containsNull = true)
 |    |    |-- product_id: long (nullable = true)
 |    |    |-- qty: long (nullable = true)
 |    |    |-- unit_price: string (nullable = true)
 |-- order_id: long (nullable = true)
 |-- order_ts: string (nullable = true)
 |-- status: string (nullable = true)

root
 |-- amount: string (nullable = true)
 |-- currency: string (nullable = true)
 |-- customer_id: string (nullable = true)
 |-- items: array (nullable = true)
 |    |-- element: struct (containsNull = true)
 |    |    |-- product_id: string (nullable = true)
 |    |    |-- qty: string (nullable = true)
 |    |    |-- unit_price: string (nullable = true)
 |-- order_id: string (nullable = true)
 |-- order_ts: string (nullable = true)
 |-- status: string (nullable = true)
```

The first schema is the normal reader, the second the all-strings version. Note that `amount` is a string even with
type inference, because the source sends `"59.90"` in quotes. Inference reads
the JSON, not your intentions.

Why strings? The schema page: "By default, Auto Loader schema inference seeks to avoid schema evolution issues due to
type mismatches." If day 1 infers `order_id` as a number and day 30 sends `"A-1001"`, a typed column would reject or
null the value; a string column keeps it. Typing happens in silver.

How much data is sampled: the schema page says Auto Loader "samples the first 50 GB or 1000 files that it discovers,
whichever limit is crossed first", configurable with `spark.databricks.cloudFiles.schemaInference.sampleSize.numBytes`
and `...numFiles`. (The FAQ describes the same sample as "the most recent (by file modification time) 50 GB of data or
1000 files"; the two pages disagree on first vs most recent, so treat which files are sampled as not verified.) If the
source directory is empty, the FAQ says you must provide a schema, since there is nothing to infer from. For CSV,
inference "assumes that the files contain headers"; set `.option("header", "false")` if they do not.

### Schema hints

A **schema hint** fixes the type of some columns while the rest is still inferred, in SQL DDL syntax:

*Databricks only, not run here. Syntax from [Configure schema inference and evolution in Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema).*

```python
(spark.readStream.format("cloudFiles")
   .option("cloudFiles.format", "json")
   .option("cloudFiles.schemaLocation", meta)
   .option("cloudFiles.schemaHints",
           "order_ts TIMESTAMP, amount DECIMAL(10,2), items.element.qty INT")
   .load(landing))
```

Facts from the schema page that interviewers like:

- Hints can reach into nested types: `users.element.id INT` for array elements, `ids MAP<STRING,INT>`, `names.key INT`
  and `prices.value INT` for map keys and values (Array and Map hints need Databricks Runtime 9.1 LTS and above).
- A hint can add a column that is "not present at the start of the stream".
- "Auto Loader uses schema hints only if you *do not* provide a schema." If you pass `.schema(...)`, hints are ignored.
- For Parquet, a hint "doesn't cast the column"; it tells the reader to read the column as that type, and a mismatch
  goes to the rescued data column.
- Hints work "whether `cloudFiles.inferColumnTypes` is enabled or disabled".

For bronze, keep hints few. Hinting `amount DECIMAL(10,2)` means a value like `"12.O0"` lands in `_rescued_data`
rather than in the column; that is safe, but the bronze row no longer shows the bad value in place. Many teams keep
bronze all-string and type in silver.

### Evolution: what the default mode actually does

The default mode `addNewColumns` (default "when a schema is not specified, `none` otherwise", per the options
reference) works like this, per the schema page: "When Auto Loader detects a new column, the stream stops with an
`UnknownFieldException`. Before your stream throws this error, Auto Loader performs schema inference on the latest
micro-batch of data and updates the schema location with the latest schema by merging new columns to the end of the
schema. The data types of existing columns remain unchanged." The next start reads the new schema and continues.
So the failure is by design, and the fix is a restart, which is why the docs recommend running Auto Loader streams
under Lakeflow Jobs so "they restart automatically".

Three details that are easy to miss:

- "`addNewColumns` is not allowed when the schema of the stream is provided, but does work if you provide your schema
  as a schema hint." If you want evolution, give your known columns as hints, not as `.schema()`.
- `addNewColumnsWithTypeWidening` (Public Preview, Databricks Runtime 16.4 and above) also widens types such as `int`
  to `long`; "Unsupported type changes (for example, `int` to `string`) are added to the rescued data column."
- Partition columns from Hive-style paths (`/date=2026-03-01/`) are inferred but "Auto Loader does not consider
  partition columns for schema evolution"; a new path level such as `hour=01` is ignored unless you list it in
  `cloudFiles.partitionColumns`.

The best practices page gives a one-line choice per situation:

| Situation | Recommendation (Auto Loader best practices page) |
| --- | --- |
| Schema is known and fixed | Provide an explicit schema with `.schema()` |
| Unknown, additive changes expected | `schemaEvolutionMode`: `addNewColumns` |
| Unknown, type changes expected | `addNewColumnsWithTypeWidening` |
| Strict schema contract required | `failOnNewColumns` |
| Arbitrary or unpredictable schema | Ingest as `Variant` type (`.option("singleVariantColumn", "data")`) |

The `VARIANT` route is covered in [18. Nested and semi-structured data](18-Semi-Structured-Data.md).

### `_rescued_data` vs `_corrupt_record`

They catch different problems:

- **`_rescued_data`** is added automatically when Auto Loader infers the schema. It holds a JSON blob of values that
  parsed but did not fit: "The column is missing from the schema", "Type mismatches", "Case mismatches", plus "the
  source file path of the record".
- **`_corrupt_record`** holds lines that cannot be parsed at all, such as truncated JSON. The best practices page:
  "`_corrupt_record` captures rows that cannot be parsed at all. Enable it using `columnNameOfCorruptRecord`", and
  "Databricks recommends `columnNameOfCorruptRecord` over `badRecordsPath` to avoid potential race conditions that can
  miss corrupted records."

*Databricks only, not run here. Syntax from [Auto Loader best practices](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/best-practices).*

```python
(spark.readStream.format("cloudFiles")
   .option("cloudFiles.format", "json")
   .option("cloudFiles.schemaHints", "_corrupt_record string")
   .option("columnNameOfCorruptRecord", "_corrupt_record")
   .load(landing))
```

With the rescued data column on, the schema page says type mismatches no longer drop records in `DROPMALFORMED` mode
or throw in `FAILFAST` mode; "Only corrupt records fail or throw errors, such as incomplete or malformed JSON or
CSV."

Open-source Spark has no rescued data column, so a type mismatch is treated as a corrupt record. The file below holds
a good order, a line cut off mid-record, and an amount typed with the letter O (`"12.O0"`), read with a typed schema
in each parser mode:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
TYPED = "order_id INT, amount DECIMAL(10,2), currency STRING, _corrupt_record STRING"
spark.read.schema(TYPED).json(BAD).show(truncate=False)                                # PERMISSIVE (default)
spark.read.schema(TYPED).option("mode", "DROPMALFORMED").json(BAD).show(truncate=False)
spark.read.schema(TYPED).option("mode", "FAILFAST").json(BAD).collect()
```

```text
+--------+------+--------+--------------------------------------------------------+
|order_id|amount|currency|_corrupt_record                                         |
+--------+------+--------+--------------------------------------------------------+
|NULL    |NULL  |NULL    |{"order_id": 1008, "amount": "12.50", "curr             |
|1007    |59.90 |CAD     |NULL                                                    |
|1009    |NULL  |CAD     |{"order_id": 1009, "amount": "12.O0", "currency": "CAD"}|
+--------+------+--------+--------------------------------------------------------+

+--------+------+--------+---------------+
|order_id|amount|currency|_corrupt_record|
+--------+------+--------+---------------+
|1007    |59.90 |CAD     |NULL           |
+--------+------+--------+---------------+

ERROR: [MALFORMED_RECORD_IN_PARSING.WITHOUT_SUGGESTION] Malformed records are detected in record parsing: [null,null,null,{"order_id": 1008, "amount": "12.50", "curr].
```

`DROPMALFORMED` silently lost two of three orders, and `FAILFAST` stopped at the first bad line. With an all-string
schema, only the truly broken line is corrupt and the odd amount is kept as text for silver to judge:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
+--------+------+--------+-------------------------------------------+
|order_id|amount|currency|_corrupt_record                            |
+--------+------+--------+-------------------------------------------+
|NULL    |NULL  |NULL    |{"order_id": 1008, "amount": "12.50", "curr|
|1007    |59.90 |CAD     |NULL                                       |
|1009    |12.O0 |CAD     |NULL                                       |
+--------+------+--------+-------------------------------------------+
```

!!! warning "Never use `DROPMALFORMED` in bronze"
    Bronze exists to keep what arrived. A mode that drops rows without a trace defeats it. Keep `PERMISSIVE` with a
    corrupt record column (and on Auto Loader, the rescued data column), and alert when either is not null.

!!! tip "In the interview"
    **"Your Auto Loader stream failed after the source added a column. What happened?"** That is the default
    `addNewColumns` mode working as designed: Auto Loader merged the new column into the schema in the schema
    location, then stopped with `UnknownFieldException`. Restart it (a job with retries does this automatically)
    and it continues with the new column. If the team wants no failures, use `rescue` mode or ingest as `VARIANT`;
    if it wants a strict contract, use `failOnNewColumns`.

## 8.6 File detection: directory listing vs file notification

*Level: intermediate.*

To find new files, Auto Loader can list the directory, or be told about new files by the cloud. The "Compare Auto
Loader file detection modes" page: "Auto Loader uses directory listing mode by default", and "Databricks recommends
file notification mode using file events instead of directory listing mode for most workloads." You can switch modes
"across stream restarts and still obtain exactly-once data processing guarantees".

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 290" role="img" aria-label="Directory listing compared with file notification: in directory listing the stream sends LIST calls over the whole landing folder and gets back all file names; in file notification the storage sends an event per new file to a file events service or queue, and the stream reads only new file names from it">
<line x1="320" y1="10" x2="320" y2="280" stroke="currentColor" stroke-width="1" stroke-dasharray="4 4"/>
<g fill="currentColor" font-size="14" text-anchor="middle" font-weight="bold">
<text x="160" y="22">Directory listing (default)</text>
<text x="480" y="22">File notification (recommended)</text>
</g>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="60" y="40" width="200" height="44" rx="6"/>
<rect x="60" y="200" width="200" height="60" rx="6"/>
<rect x="360" y="40" width="240" height="44" rx="6"/>
<rect x="360" y="120" width="240" height="44" rx="6"/>
<rect x="360" y="200" width="240" height="60" rx="6"/>
<line x1="130" y1="84" x2="130" y2="192"/>
<line x1="190" y1="200" x2="190" y2="92"/>
<line x1="480" y1="200" x2="480" y2="172"/>
<line x1="480" y1="120" x2="480" y2="92"/>
</g>
<g fill="currentColor">
<polygon points="130,200 125,190 135,190"/>
<polygon points="190,84 185,94 195,94"/>
<polygon points="480,164 475,174 485,174"/>
<polygon points="480,84 475,94 485,94"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="160" y="67">Auto Loader stream</text>
<text x="160" y="226">Storage: landing/</text>
<text x="160" y="246">old and new files</text>
<text x="480" y="67">Auto Loader stream</text>
<text x="480" y="147">File events service or queue</text>
<text x="480" y="226">Storage: landing/</text>
<text x="480" y="246">new file written</text>
</g>
<g fill="currentColor" font-size="13">
<text x="122" y="145" text-anchor="end">LIST</text>
<text x="198" y="145" text-anchor="start">all names</text>
<text x="488" y="190" text-anchor="start">event per file</text>
<text x="488" y="110" text-anchor="start">new names only</text>
</g>
</svg>
<figcaption>Figure 8.3. Directory listing asks the storage for every file name on each run, so its cost grows with
the folder. File notification receives one event per new file, so its cost grows with the new files only.</figcaption>
</figure>

**Directory listing** needs no setup beyond read access, which is why it is the default. Auto Loader optimizes it:
with a flattened listing it reduces API calls to "the number of files in storage divided by the number of results
returned by each API call" (1000 per call on S3, 5000 on ADLS, 1024 on GCS). Its weakness is that every run lists the
whole directory. The directory listing page warns against continuous triggers such as `Trigger.ProcessingTime`, "where
directory listing mode continuously lists the entire directory and can significantly increase `LIST` API costs". The
old incremental listing optimization (`cloudFiles.useIncrementalListing`) "is deprecated".

**File notification** comes in two forms:

- **File events (recommended).** You enable file events once on the Unity Catalog external location, and every
  stream on it sets `cloudFiles.useManagedFileEvents` to `true`. There is "a single file notification queue for all
  streams that process files from a given external location", Databricks sets up the cloud subscriptions, and it
  tunes and cleans up for you. It needs Databricks Runtime 14.3 LTS or above.
- **Classic file notification.** `cloudFiles.useNotifications` = `true`: Auto Loader creates a notification service
  and queue per stream (SNS and SQS on AWS, Event Grid and Queue Storage on Azure, Pub/Sub on GCS), which needs
  elevated cloud permissions and is limited per bucket (100 per S3 bucket, for example).

*Databricks only, not run here. Syntax from [Auto Loader best practices](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/best-practices).*

```python
(spark.readStream.format("cloudFiles")
   .option("cloudFiles.format", "json")
   .option("cloudFiles.useManagedFileEvents", "true")   # path must be in an external location with file events
   .load("/Volumes/shop/bronze/landing/orders/"))
```

The best practices page compares the three:

| Mode | Setup | Scalability | Cost | When to use |
| --- | --- | --- | --- | --- |
| File events (recommended) | Low (one-time permission setup) | Millions of files per hour | Lowest | Default for most workloads |
| Classic file notification | High (21+ cloud configuration options) | Millions of files per hour | Medium | When file events are unavailable |
| Directory listing | None | Limited by directory size | Highest (LIST API costs) | Small directories, one-time backfills, or when security policies prevent file events |

Two caveats on file events. First, the file events service caches recent files; "If Auto Loader runs infrequently,
this cache can expire, and Auto Loader falls back to directory listing", so "invoke Auto Loader at least once every
seven days". Second, a full listing still happens on the first run when `includeExistingFiles` is `true`, and the FAQ
says that even with it set to `false` the first run lists the directory to get a valid read position.

!!! warning "Order is never guaranteed"
    "Auto Loader does not guarantee the order in which files are discovered or processed, regardless of whether you
    use directory listing or file notification mode." Do not rely on file name order for correctness. The Auto
    Loader page suggests soft deletes instead of hard deletes, and comparing update timestamps before applying an
    upsert (the `>` guard in [9.7](09-Building-Silver.md#97-late-and-out-of-order-data-in-merge)).

### Backfills: `cloudFiles.backfillInterval`

Cloud notification systems deliver events "at least one time", yet "a file can still be missed". A **backfill**, in
the production page's words, "is an asynchronous directory listing that Auto Loader runs alongside normal file
discovery to catch files that discovery missed". Set it with a duration such as `1 day` or `1 week`; "There is no
default." A backfill "ingests only files that weren't already processed", checking the checkpoint, so it does not
create duplicates.

When to set it: "Set a backfill interval when you use classic file notification mode and have strict data
completeness or service-level agreement (SLA) requirements." When not to: with file events, the setting is
unsupported, because Databricks does a full listing when file events are first enabled and "then continues to
backfill about every 24 hours while a stream is ingesting".

!!! tip "In the interview"
    **"Millions of small files arrive every day. How do you ingest them?"** Use Auto Loader with file notification
    mode on file events, so discovery cost follows the new files rather than the size of the folder; run it in a
    Lakeflow pipeline or as an `availableNow` job triggered by file arrival; let the rate limits split the backlog
    into micro-batches; and consider `cloudFiles.cleanSource` to move processed files out of the landing folder.
    Directory listing on a huge folder with a continuous trigger is the expensive anti-pattern.

## 8.7 Controlling runs: triggers, rate limits, existing files and cleanup

*Level: intermediate.*

### Triggers

A Structured Streaming **trigger** decides when micro-batches run (chapter 11 covers all of them). For ingestion, two
matter:

- **`availableNow=True`**: "The `AvailableNow` trigger instructs Auto Loader to process all files that arrived
  **before** the query start time. New files that arrive after the stream starts are ignored until the next
  trigger." It can split the work into several micro-batches, then stops. This is the batch-like way to run Auto
  Loader on a schedule. (`Trigger.Once` is deprecated in Databricks Runtime 11.3 LTS and above.)
- A continuous run (no trigger, or `processingTime`) for low latency, which costs more.

The production page: "If your workload doesn't have low-latency requirements, you can reduce compute costs by using
Lakeflow Jobs to schedule Auto Loader as batch jobs using `Trigger.AvailableNow`", and these jobs "can be triggered
using file arrival triggers". The best practices page recommends, for most use cases, "a file arrival trigger with
file events enabled".

### Rate limits

| Option | Default | Notes (options reference and production page) |
| --- | --- | --- |
| `cloudFiles.maxFilesPerTrigger` | `1000` | Maximum new files per micro-batch; a hard limit |
| `cloudFiles.maxBytesPerTrigger` | None | A soft maximum such as `10g`; a file is never split, so "If you have files that are 3 GB each, Databricks processes 12 GB in a micro-batch" |

With both set, Auto Loader consumes "up to the lower limit ... whichever is reached first". Neither has an effect with
the deprecated `Trigger.Once()`, and "In Databricks Runtime 18.0 and above, this option is dynamically configured and
does not need to be set manually" (said of each). Rate limits matter most for the first run over a large backlog:
smaller micro-batches commit progress more often, and a failed micro-batch has to complete in full before the stream
moves on (the triggers page: "The previous unsuccessful batch must complete").

Here the open-source file source's `maxFilesPerTrigger` shows how `availableNow` splits a backlog. Three backfill
files, one file per batch, written with `foreachBatch` so each batch can stamp its **batch id** (the micro-batch
number Structured Streaming passes to the function):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def write_batch(batch_df, batch_id):
    (batch_df
     .select("order_id", "amount", F.col("_metadata.file_name").alias("_source_file"))
     .withColumn("_batch_id", F.lit(batch_id))
     .write.format("delta").mode("append")
     .option("txnAppId", "bronze_orders_backfill")   # same id for every run of this stream
     .option("txnVersion", batch_id)                 # Delta skips a (txnAppId, txnVersion) it has seen
     .saveAsTable("bronze_orders_backfill"))

q = (spark.readStream.schema(BRONZE_SCHEMA)
     .option("maxFilesPerTrigger", 1)
     .json(LANDING2)
     .select("*", "_metadata")          # reference _metadata before foreachBatch
     .writeStream
     .foreachBatch(write_batch)
     .option("checkpointLocation", CHK2)
     .trigger(availableNow=True)
     .start())
q.awaitTermination()
print("rows read per batch:", [p["numInputRows"] for p in q.recentProgress])
```

```text
rows read per batch: [1, 1, 1]
>>> SELECT _batch_id, order_id, _source_file FROM bronze_orders_backfill ORDER BY _batch_id
+---------+--------+----------------------+
|_batch_id|order_id|_source_file          |
+---------+--------+----------------------+
|0        |2001    |orders_backfill_1.json|
|1        |2002    |orders_backfill_2.json|
|2        |2003    |orders_backfill_3.json|
+---------+--------+----------------------+
```

The `txnAppId`/`txnVersion` options make the `foreachBatch` write idempotent: the foreachBatch page says that for
Delta tables "You must use the `txnAppId` and `txnVersion` write options, binding `txnVersion` to `batchId`, to
guarantee idempotency". Replaying batch 1 by hand, as a retry after a crash would, writes nothing:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
replay = (spark.read.schema(BRONZE_SCHEMA).json(os.path.join(LANDING2, "orders_backfill_2.json"))
          .select("*", "_metadata"))
write_batch(replay, 1)
```

```text
>>> SELECT count(*) AS rows FROM bronze_orders_backfill
+----+
|rows|
+----+
|3   |
+----+

+-------+------------+------------+
|version|operation   |rows_written|
+-------+------------+------------+
|0      |CREATE TABLE|NULL        |
|1      |WRITE       |1           |
|2      |WRITE       |1           |
|3      |WRITE       |1           |
+-------+------------+------------+
```

No version 4: Delta recognized the pair (`bronze_orders_backfill`, 1) and skipped the write. A plain `toTable` sink
does not need this, because the Delta sink already commits each batch once; it matters as soon as you write inside
`foreachBatch`.

### Existing files, file age and overwrites

- **`cloudFiles.includeExistingFiles`** (default `true`): whether to load files already in the folder when the stream
  first starts. "This option is evaluated only when you start a stream for the first time. Changing this option after
  restarting the stream has no effect." The read_files example: a streaming table with
  `includeExistingFiles => false` "will most likely be empty ... after being first created".
- **`cloudFiles.maxFileAge`** (no default): how long a file event is tracked for deduplication. The minimum is
  "14 days"; Databricks recommends a conservative value "such as 90 days" and does not recommend tuning it "unless you
  are ingesting data at the order of millions of files an hour", because aggressive values cause "duplicate ingestion
  or missing files". If set on the first start, older files are not ingested at all.
- **`cloudFiles.allowOverwrites`** (default `false`): with `true`, a changed file is reprocessed in full ("Auto Loader
  will reprocess the entire file even when it is appended to or partially updated"), so you must handle the duplicate
  records. Databricks recommends "using Auto Loader to ingest immutable files only".

### Cleaning up the landing folder: `cloudFiles.cleanSource`

A landing folder that keeps every file forever costs storage and slows directory listing. `cloudFiles.cleanSource`
(Databricks Runtime 16.4 and above) takes `OFF` (default), `MOVE` or `DELETE`. Files become candidates after
`cloudFiles.cleanSource.retentionDuration` (default `30 days`; "Must be greater than 7 days for `DELETE`. No minimum
restriction for `MOVE`."), and `MOVE` needs `cloudFiles.cleanSource.moveDestination`.

*Databricks only, not run here. Syntax from [Configure Auto Loader for production workloads](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/production).*

```python
(spark.readStream.format("cloudFiles")
   .option("cloudFiles.format", "json")
   .option("cloudFiles.cleanSource", "MOVE")
   .option("cloudFiles.cleanSource.moveDestination", "/Volumes/shop/bronze/landing/archive/orders/")
   .option("cloudFiles.cleanSource.retentionDuration", "14 days")
   .option("cloudFiles.schemaLocation", meta)
   .load("/Volumes/shop/bronze/landing/orders/"))
```

Rules from the clean source page: the move destination must not be inside the source directory ("the archived files
are ingested again") and must be in the same external location, volume or DBFS mount; do not use clean source when
several streams read the same directory ("The fastest stream cleans up the files, so the slower streams never ingest
them"); and cleanup runs only when there is a batch to process. The production page adds that with `foreachBatch`,
files become candidates "as soon as your `foreachBatch` operation returns successfully even if your operation only
consumed a subset of the files", and that if you can use file events, they are the better way to reduce discovery
cost; clean source is for when you must stay on directory listing.

### The checkpoint is not optional storage

From the production page and the FAQ:

- Do not put the checkpoint under a cloud lifecycle policy: "If files in the checkpoint location are cleaned
  according to the policy, the stream state is corrupted. If this happens, you must restart the stream from scratch."
- "Changing the checkpoint location effectively means that you have abandoned the previous stream and started a new
  stream." With the default `includeExistingFiles=true`, a new stream loads every file in the folder again.
- Each source needs its own checkpoint: "If you have more than one source data location being loaded into the target
  table, each Auto Loader ingestion workload requires a separate streaming checkpoint."
- The FAQ allows several streams on different directories of one bucket "as long as they are not parent-child
  directories" (`prod-logs/` and `prod-logs/usage/` would not work).

## 8.8 `COPY INTO`

*Level: intermediate.*

`COPY INTO` is a SQL command that "Loads data from a file location into a Delta table. This is a retryable and
idempotent operation. Files in the source location that have already been loaded are skipped. This is true even if
the files have been modified since they were loaded." (SQL reference.) It is a batch command: each run lists the
source, skips files it has already loaded into that table, and loads the rest.

**Its status today.** The COPY INTO pages themselves do not carry a "legacy" label (the SQL reference page title is
simply "`COPY INTO`"). But the File metadata column page (last updated Sep 11, 2026) titles its example "Use in COPY
INTO (legacy)" and links to the reference as "COPY INTO (legacy)", and the Spark API options reference (last updated
Nov 5, 2026) writes "`COPY INTO` (legacy)" throughout, for example "Not supported for `COPY INTO` (legacy)". The
getting-started page says: "For a more scalable
and robust file ingestion experience, Databricks recommends that SQL users use streaming tables." And the ingestion
page calls `CREATE STREAMING TABLE` "the recommended alternative to `COPY INTO`". So: still supported and still asked
about, but no longer the recommended path.

The syntax, from the SQL reference:

*Databricks only, not run here. Syntax from [COPY INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-copy-into).*

```text
COPY INTO target_table [ BY POSITION | ( col_name [ , <col_name> ... ] ) ]
  FROM { source_clause |
         ( SELECT expression_list FROM source_clause ) }
  FILEFORMAT = data_source
  [ VALIDATE [ ALL | num_rows ROWS ] ]
  [ FILES = ( file_name [, ...] ) | PATTERN = glob_pattern ]
  [ FORMAT_OPTIONS ( { data_source_reader_option = value } [, ...] ) ]
  [ COPY_OPTIONS ( { copy_option = value } [, ...] ) ]
```

| Part | Meaning |
| --- | --- |
| `target_table` | An existing Delta table |
| `FROM (SELECT ...)` | Transform while loading, for example add `_metadata` fields or cast; only global aggregates, no `GROUP BY` |
| `FILEFORMAT` | The SQL reference lists `CSV`, `JSON`, `AVRO`, `ORC`, `PARQUET`, `TEXT`, `BINARYFILE`; XML also works: the getting-started page lists it, and the "Read and write XML files" page shows `FILEFORMAT = XML` |
| `FILES` | Explicit file names, "with a limit of 1000 files"; cannot be combined with `PATTERN` |
| `PATTERN` | A glob such as `'2026/03/*/orders_*.json'` |
| `VALIDATE` | Check parsing, schema and constraints without writing (Databricks Runtime 10.4 LTS and above) |
| `FORMAT_OPTIONS` | Reader options for the format, for example `'multiLine' = 'true'`, `'header' = 'true'`, `'inferSchema' = 'true'`, `'ignoreCorruptFiles' = 'true'` |
| `COPY_OPTIONS` | `'force' = 'true'` turns idempotency off ("files are loaded regardless of whether they've been loaded before"); `'mergeSchema' = 'true'` lets the target schema evolve; both default to `false` |

*Databricks only, not run here. Syntax from [COPY INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-copy-into), [Get started using COPY INTO to load data](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/copy-into/) and [File metadata column](https://docs.databricks.com/aws/en/ingestion/file-metadata-column).*

```sql
-- Placeholder table: the schema is inferred on the first load (Databricks Runtime 11.3 LTS and above)
CREATE TABLE IF NOT EXISTS shop.bronze.orders_copy;

COPY INTO shop.bronze.orders_copy
FROM (
  SELECT *, _metadata.file_name AS _source_file, current_timestamp() AS _ingested_at
  FROM '/Volumes/shop/bronze/landing/orders/'
)
FILEFORMAT = JSON
PATTERN = 'orders_2026*.json'
FORMAT_OPTIONS ('mergeSchema' = 'true')
COPY_OPTIONS ('mergeSchema' = 'true');
```

Points from the pages:

- A schemaless placeholder table "is not usable outside `COPY INTO`. `INSERT INTO` and `MERGE INTO` are not supported
  to write data into schemaless Delta tables" until `COPY INTO` has loaded data.
- In `FORMAT_OPTIONS`, `inferSchema` decides whether to infer types or "assume all columns are of `StringType`", and
  `mergeSchema` merges the schemas of several source files. In `COPY_OPTIONS`, `mergeSchema` evolves the target table.
- Corrupt files skipped with `ignoreCorruptFiles` "aren't tracked by `COPY INTO`, so they can be reloaded in a
  subsequent run if the corruption is fixed".
- Concurrent `COPY INTO` runs on the same table are allowed on distinct sets of files, but "a single `COPY INTO`
  command with multiple files typically performs better", and "When ingesting directories with a very large number
  of files, Databricks recommends using Auto Loader when possible."
- In Databricks Runtime 15.2 and above, `VACUUM` cleans up unreferenced metadata files created by `COPY INTO`.

### An idempotent batch load, emulated here

`COPY INTO` does not exist in open-source Spark. The emulation below reproduces only its visible contract: load
files whose path is not yet in the table, and a `force` switch. It is a teaching emulation, not how `COPY INTO` is
built (`COPY INTO` keeps its own record of loaded files and also ignores later modifications).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def load_new_files(src, table, force=False):
    incoming = (spark.read.schema("order_id STRING, amount STRING").json(src)
                .select("order_id", "amount",
                        F.col("_metadata.file_path").alias("_source_path"),
                        F.current_timestamp().alias("_ingested_at")))
    if not force:
        already = spark.table(table).select("_source_path").distinct()
        incoming = incoming.join(already, "_source_path", "left_anti")
    incoming = incoming.select("order_id", "amount", "_source_path", "_ingested_at")
    n = incoming.count()
    incoming.write.format("delta").mode("append").saveAsTable(table)
    print(f"rows loaded: {n}")
```

Four calls: the first load, the same call again, a new file, then `force=True`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
======== B1. first load ========
rows loaded: 3
======== B2. same command again: nothing new ========
rows loaded: 0
======== B3. a third file lands ========
rows loaded: 1
======== B4. force=True: every file again (like COPY_OPTIONS ('force' = 'true')) ========
rows loaded: 4
>>> SELECT regexp_extract(_source_path, '[^/]+$', 0) AS file, count(*) AS rows FROM bronze_orders_batch GROUP BY ALL ORDER BY ALL
+-------------------------+----+
|file                     |rows|
+-------------------------+----+
|orders_20260301_0900.json|4   |
|orders_20260301_1800.json|2   |
|orders_20260302_0900.json|2   |
+-------------------------+----+
```

The emulation also shows a weakness the real command does not have: the anti-join reads the whole target table on
every run, and two concurrent runs could both load the same file. That is the work `COPY INTO` and Auto Loader do for
you.

### `COPY INTO` or Auto Loader?

| | `COPY INTO` | Auto Loader |
| --- | --- | --- |
| Interface | SQL statement, batch | Streaming source (Python, Scala; SQL via `STREAM read_files`) |
| Idempotency | Skips files already loaded into the table | Checkpoint (RocksDB) records files |
| Discovery | Lists the source on each run | Directory listing or file notification with file events |
| Very many files | Docs recommend Auto Loader "when possible" | Built for "billions of files" |
| Schema | Infer, `mergeSchema`; schemaless placeholder table | Inference with schema location, hints, evolution modes, rescued data |
| Official status | Recommended alternative: streaming tables; labelled legacy on the File metadata column and Spark API options pages | Recommended for incremental file ingestion |

!!! tip "In the interview"
    **"COPY INTO or Auto Loader?"** Both load each file once. `COPY INTO` is a simple, re-runnable SQL batch command,
    fine for a few thousand files loaded on demand. Auto Loader is a streaming source with scalable discovery
    (file events), schema inference and evolution, and rescued data, and it is what Databricks recommends for
    ongoing ingestion; SQL users get it through streaming tables with `STREAM read_files`, which the docs call the
    recommended alternative to `COPY INTO`.

## 8.9 `read_files` and streaming tables

*Level: intermediate.*

`read_files` is a table-valued function (Databricks SQL and Databricks Runtime 13.3 LTS and above) that "Reads files
under a provided location and returns the data in tabular form". It reads `JSON`, `CSV`, `XML`, `TEXT`,
`BINARYFILE`, `PARQUET`, `AVRO` and `ORC`, "Can detect the file format automatically and infer a unified schema across
all files", and needs named arguments for options (`format => 'json'`). Option names with dots need backticks.

As a batch query it is the quickest way to look at landed files:

*Databricks only, not run here. Syntax from [read_files table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/read_files).*

```sql
SELECT *, _metadata.file_name
FROM read_files('/Volumes/shop/bronze/landing/orders/',
                format => 'json',
                schemaHints => 'order_id INT');
```

Defaults that differ from Auto Loader (verified on the read_files page):

| Option | `read_files` default | Auto Loader default |
| --- | --- | --- |
| `inferColumnTypes` | `true` ("This is the opposite of the default behavior of Auto Loader") | `false` (strings) |
| `useStrictGlobber` | `true` ("This is the opposite of the default for Auto Loader") | `false` |
| Rescued data column | provided by default; drop it with `schemaEvolutionMode => 'none'` | added when inferring |

Without a `schema`, batch `read_files` infers "a unified schema across the discovered files, which requires reading
all the files unless a `LIMIT` statement is used".

With the **`STREAM`** keyword inside a **streaming table**, `read_files` "leverages Auto Loader": "You must use the
`STREAM` keyword with `read_files`." In a streaming query it "uses a sample of the data to infer the schema, and can
evolve the schema as it processes more data". A **standalone streaming table** is "a table registered to Unity
Catalog with extra support for streaming or incremental data processing, defined outside of a Lakeflow pipeline. A
pipeline is automatically created for each streaming table." It can be created from a SQL warehouse and refreshed on
a schedule; the refresh runs on serverless pipelines, not on the warehouse.

*Databricks only, not run here. Syntax from [Use standalone streaming tables](https://docs.databricks.com/aws/en/sql/mv-st/streaming) and [read_files table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/read_files).*

```sql
CREATE OR REFRESH STREAMING TABLE shop.bronze.orders
  SCHEDULE EVERY 1 hour
AS SELECT *,
          _metadata.file_name              AS _source_file,
          _metadata.file_modification_time AS _file_modified_at,
          current_timestamp()              AS _ingested_at
FROM STREAM read_files(
  '/Volumes/shop/bronze/landing/orders/',
  format => 'json',
  inferColumnTypes => false,          -- keep bronze as strings, like Auto Loader's default
  includeExistingFiles => true
);
```

Streaming options such as `includeExistingFiles`, `maxFilesPerTrigger`, `maxBytesPerTrigger`, `allowOverwrites`,
`useManagedFileEvents` and `cleanSource` are passed the same way (named arguments, backticks for dotted names such as
`` `cleanSource.moveDestination` ``). For streaming tables on serverless SQL warehouses, the read_files page says not
to set `maxBytesPerTrigger` or `maxFilesPerTrigger`, "to leverage dynamic admission control".

!!! tip "In the interview"
    **"How does a SQL-only team do incremental file ingestion?"** A streaming table:
    `CREATE OR REFRESH STREAMING TABLE ... AS SELECT ... FROM STREAM read_files(path, format => 'json')`. The
    `STREAM` keyword makes `read_files` use Auto Loader underneath, so files are loaded once and the schema can
    evolve, and `SCHEDULE EVERY` refreshes it. Watch one trap: `read_files` infers column types by default, the
    opposite of Auto Loader.

## 8.10 The `_metadata` column and ingest metadata

*Level: intermediate.*

Every file-based source exposes a hidden **`_metadata`** struct. The File metadata column page lists its fields:

| Field | Type | Meaning | Minimum Databricks Runtime |
| --- | --- | --- | --- |
| `file_path` | `STRING` | File path of the input file | 10.5 |
| `file_name` | `STRING` | Name with extension | 10.5 |
| `file_size` | `LONG` | Length in bytes | 10.5 |
| `file_modification_time` | `TIMESTAMP` | Last modification time | 10.5 |
| `file_block_start` | `LONG` | Start offset of the block being read | 13.0 |
| `file_block_length` | `LONG` | Length of the block being read | 13.0 |

Open-source Spark 4.2 has the same six fields for file sources:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
spark.read.json(LANDING).select("_metadata").printSchema()
(spark.read.json(LANDING)
 .select("order_id",
         F.regexp_replace("_metadata.file_path", "^.*/landing/", ".../landing/").alias("file_path"),
         "_metadata.file_name", "_metadata.file_size", "_metadata.file_modification_time",
         "_metadata.file_block_start", "_metadata.file_block_length")
 .orderBy("order_id").show(truncate=False))
print(spark.read.json(LANDING).columns)
```

```text
root
 |-- _metadata: struct (nullable = false)
 |    |-- file_path: string (nullable = false)
 |    |-- file_name: string (nullable = false)
 |    |-- file_size: long (nullable = false)
 |    |-- file_block_start: long (nullable = false)
 |    |-- file_block_length: long (nullable = false)
 |    |-- file_modification_time: timestamp (nullable = false)

+--------+--------------------------------------------+-------------------------+---------+----------------------+----------------+-----------------+
|order_id|file_path                                   |file_name                |file_size|file_modification_time|file_block_start|file_block_length|
+--------+--------------------------------------------+-------------------------+---------+----------------------+----------------+-----------------+
|1001    |.../landing/orders/orders_20260301_0900.json|orders_20260301_0900.json|391      |2026-03-01 09:00:00   |0               |391              |
|1002    |.../landing/orders/orders_20260301_0900.json|orders_20260301_0900.json|391      |2026-03-01 09:00:00   |0               |391              |
|1003    |.../landing/orders/orders_20260301_1800.json|orders_20260301_1800.json|194      |2026-03-01 18:00:00   |0               |194              |
+--------+--------------------------------------------+-------------------------+---------+----------------------+----------------+-----------------+

['amount', 'currency', 'customer_id', 'items', 'order_id', 'order_ts', 'status']
```

(The `regexp_replace` only shortens the long working path for printing.) The last line shows that `SELECT *` does
not include `_metadata`: "you must explicitly select it". Rules from the page:

- "Databricks recommends selecting specific fields from the column", because "New fields might be added to the
  `_metadata` column in future releases" and a whole-struct column could then cause schema evolution errors.
- "If the data source contains a column named `_metadata`, queries return the column from the data source", so
  rename yours (the page suggests `source_metadata`).
- With `foreachBatch`, "you must reference it in the streaming read DataFrame before the `foreachBatch` function. If
  you only reference the file metadata column inside the `foreachBatch` function, the column is not included."
  That is why the run in 8.7 has `.select("*", "_metadata")` before `foreachBatch`.

### The ingest metadata columns

A bronze row should answer "where did this come from and when did we load it" without looking anywhere else. A
practical set (names are a convention, not a Databricks standard):

| Column | Source | Used for |
| --- | --- | --- |
| `_source_file` (or full `_source_path`) | `_metadata.file_name` / `file_path` | Tracing a bad row to its file; finding duplicate files; reloading one file |
| `_file_modified_at` | `_metadata.file_modification_time` | Spotting late files; tie-breaks |
| `_file_size` | `_metadata.file_size` | Spotting truncated uploads |
| `_ingested_at` | `current_timestamp()` | Load audits, retention, clustering |
| `_ingest_date` | generated from `_ingested_at` | Clustering key and retention deletes |
| `_batch_id` | `batch_id` in `foreachBatch` | Tying rows to one micro-batch for replay or rollback |
| `topic`, `partition`, `offset` | Kafka columns | The unique key of a message (8.11) |

## 8.11 Message buses: Kafka, Kinesis, Event Hubs

*Level: intermediate.*

For a message bus the source keeps **offsets** (positions in each partition) in the checkpoint instead of file names.
The Kafka source reads with `format("kafka")`, and the "Connect to Apache Kafka" page gives its row schema:

| Column | Type |
| --- | --- |
| `key` | `binary` |
| `value` | `binary` |
| `topic` | `string` |
| `partition` | `int` |
| `offset` | `long` |
| `timestamp` | `timestamp` |
| `timestampType` | `int` |

"The `key` and the `value` are always deserialized as byte arrays with the `ByteArrayDeserializer`. Use DataFrame
operations (such as `cast("string")` or `from_avro`) to explicitly deserialize the keys and values."

*Databricks only, not run here (no Kafka broker). Syntax from [Connect to Apache Kafka](https://docs.databricks.com/aws/en/connect/streaming/kafka/) and [Ingest data as semi-structured variant type](https://docs.databricks.com/aws/en/ingestion/variant).*

```python
from pyspark.sql.functions import col, parse_json

(spark.readStream
   .format("kafka")
   .option("kafka.bootstrap.servers", "<server:port>")
   .option("subscribe", "rrs.orders")
   .option("startingOffsets", "earliest")      # only used the first time the query starts
   .load()
   .select(col("key").cast("string").alias("key"),
           parse_json(col("value").cast("string")).alias("value"),
           "topic", "partition", "offset", col("timestamp").alias("kafka_ts"))
   .writeStream
   .option("checkpointLocation", "/Volumes/shop/bronze/_meta/orders_kafka/")
   .trigger(availableNow=True)
   .toTable("shop.bronze.orders_kafka"))
```

```sql
CREATE OR REFRESH STREAMING TABLE shop.bronze.orders_kafka AS
SELECT * FROM STREAM read_kafka(
  bootstrapServers => '<server:port>',
  subscribe => 'rrs.orders'
);
```

Kafka options that come up (options reference):

| Option | Default | Note |
| --- | --- | --- |
| `subscribe`, `subscribePattern`, `assign` | None | Exactly one of them is required |
| `startingOffsets` | `latest` (streaming), `earliest` (batch) | "For streaming queries, this option only applies when a new query starts. Resumed queries always use the checkpoint." |
| `failOnDataLoss` | `true` | Fail if data might have been lost, for example offsets truncated by retention |
| `kafka.group.id` | None | "Use with caution: queries sharing the same group ID interfere with each other" |
| `minPartitions`, `maxRecordsPerPartition` | None | Split Kafka partitions for more parallelism |

`read_kafka` is available in Databricks Runtime 13.3 LTS and above, and "Streaming with SQL is supported only in
Lakeflow pipelines or with streaming tables in Databricks SQL". For incremental batch loads, "Databricks recommends
using Kafka with `Trigger.AvailableNow`".

The parsing step can run here on rows built by hand with the same schema as the Kafka source (no broker involved;
offset 42 holds a truncated message):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
kafka_df.printSchema()
bronze_kafka = kafka_df.select(F.col("key").cast("string").alias("key"),
                               F.col("value").cast("string").alias("value"),
                               "topic", "partition", "offset", F.col("timestamp").alias("kafka_ts"))

ORDER_DDL = ("order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING, amount DECIMAL(10,2), "
             "currency STRING, items ARRAY<STRUCT<product_id: INT, qty: INT, unit_price: DECIMAL(10,2)>>")
(bronze_kafka.select("partition", "offset", F.from_json("value", ORDER_DDL).alias("o"))
 .select("partition", "offset", "o.order_id", "o.amount", "o.order_ts", F.size("o.items").alias("n_items"))
 .orderBy("partition", "offset").show(truncate=False))

(bronze_kafka.select("partition", "offset", F.try_parse_json("value").alias("v"))
 .selectExpr("partition", "offset", "v:order_id::int AS order_id", "v:amount::decimal(10,2) AS amount",
             "v:items[0].product_id::int AS first_product", "v IS NULL AS unparsable")
 .orderBy("partition", "offset").show(truncate=False))
```

```text
root
 |-- key: binary (nullable = true)
 |-- value: binary (nullable = true)
 |-- topic: string (nullable = true)
 |-- partition: integer (nullable = true)
 |-- offset: long (nullable = true)
 |-- timestamp: timestamp (nullable = true)
 |-- timestampType: integer (nullable = true)

+---------+------+--------+------+-------------------+-------+
|partition|offset|order_id|amount|order_ts           |n_items|
+---------+------+--------+------+-------------------+-------+
|0        |41    |1001    |59.90 |2026-03-01 10:15:00|1      |
|0        |42    |NULL    |NULL  |NULL               |NULL   |
|1        |17    |1002    |120.00|2026-03-01 11:02:00|1      |
+---------+------+--------+------+-------------------+-------+

+---------+------+--------+------+-------------+----------+
|partition|offset|order_id|amount|first_product|unparsable|
+---------+------+--------+------+-------------+----------+
|0        |41    |1001    |59.90 |3            |false     |
|0        |42    |NULL    |NULL  |NULL         |true      |
|1        |17    |1002    |120.00|8            |false     |
+---------+------+--------+------+-------------+----------+
```

`try_parse_json` returns `NULL` for the broken message instead of failing the stream; `parse_json` (as in the
Databricks example above) would fail on it. In bronze, keep the raw `value` string next to any parsed form, so a
message that does not parse is still stored. `(topic, partition, offset)` identifies a message uniquely, so it is
the natural key for deduplicating replays downstream.

**Kinesis** has its own Structured Streaming source and a `read_kinesis` table-valued function. **Azure Event Hubs**
is reached through the Kafka source; the Kafka page lists "cloud-specific options for AWS MSK, Azure Event Hubs, and
Google Cloud Managed Kafka" among its authentication methods. **Google Pub/Sub** and **Apache Pulsar** have sources
too (8.1 table).

## 8.12 Lakeflow Connect managed connectors

*Level: expert.*

A **managed connector** creates an ingestion pipeline for you from a source system into Unity Catalog streaming
tables. The concepts page: "Managed connectors produce ingestion pipelines that are governed by Unity Catalog and
powered by serverless compute and Lakeflow pipelines, using efficient incremental reads and writes". Connectors are in
"various release states", so check the release state of each one before promising it in a design.

**Database connectors** use change data capture. The supported list on the managed database connectors page: MySQL
(CDC), PostgreSQL (CDC), Microsoft SQL Server ("change data capture (CDC) or full snapshot") and Oracle ("LogMiner for
change data capture"). Their components:

| Component | What it does |
| --- | --- |
| Connection | A Unity Catalog securable object that stores authentication details |
| Ingestion gateway | Extracts snapshots, change logs and metadata; "runs on classic compute, and it runs continuously to capture changes before change logs can be truncated in the source" |
| Staging storage | A Unity Catalog volume holding extracted data until it is applied; "Data is automatically purged from staging after 30 days" |
| Ingestion pipeline | Moves data from staging to the destination tables on serverless compute, on whatever schedule you choose |

The design point interviewers probe: the gateway runs all the time, so "you provision and pay for its classic compute
even when your ingestion pipeline is idle", while the pipeline that applies changes can run hourly or daily.

**SaaS connectors** (Salesforce, HubSpot, Jira, Workday and many others) use a connection, an ingestion pipeline and
destination tables; they handle "source-specific authentication, incremental reads, schema evolution, and automated
retries". **Query-based connectors** query a database on a schedule "without a gateway or staging storage", for
sources where CDC is not set up. **Streaming connectors** read message buses into streaming tables on serverless
compute.

Incremental behavior, from the concepts page: the first run ingests all selected data; later runs use the source's
change tracking "to ingest only the data that's changed from the prior run, when possible". Pipelines can be deployed
with Declarative Automation Bundles ("formerly known as Databricks Asset Bundles", per
[What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/)), and each schedule you add creates a Lakeflow job. On failure the connector
"automatically retries with exponential backoff", and when it needs you (for example expired credentials) it stores
the last cursor position to resume.

Where managed connectors sit relative to `AUTO CDC` (formerly `APPLY CHANGES`, per
[The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc)): a database connector delivers the
changes for you; when you receive CDC files yourself (for example from a tool that writes change records to cloud
storage), you ingest them with Auto Loader into bronze and apply them with `AUTO CDC` in a Lakeflow pipeline
(chapter [14](14-Data-Quality-and-CDC.md)).

!!! tip "In the interview"
    **"How would you replicate a PostgreSQL orders table into the lakehouse?"** If Lakeflow Connect's PostgreSQL
    connector fits, use it: a connection, an ingestion gateway that reads the change log continuously on classic
    compute, a staging volume, and a serverless ingestion pipeline that applies changes to streaming tables on a
    schedule. If you only need occasional queries and no copy, Lakehouse Federation reads it in place; Databricks
    recommends Lakeflow Connect when volume and latency matter.

## 8.13 Designing the bronze table

*Level: expert.*

Chapter 7 states the principles (keep everything as received, add metadata, judge nothing). Here they become a
table design.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 260" role="img" aria-label="Bronze table columns in three groups: payload columns as received (order_id, customer_id, order_ts, amount, items as raw JSON text), bad data kept (_rescued_data, _corrupt_record), and ingest metadata (_source_file, _file_modified_at, _ingested_at, _ingest_date used for clustering, _batch_id or Kafka offsets); the table is append-only, clustered by ingest date and access restricted">
<g fill="currentColor" font-size="14" text-anchor="middle" font-weight="bold">
<text x="110" y="24">Payload, as received</text>
<text x="320" y="24">Bad data, kept</text>
<text x="530" y="24">Ingest metadata</text>
</g>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="10" y="36" width="200" height="30"/>
<rect x="10" y="66" width="200" height="30"/>
<rect x="10" y="96" width="200" height="30"/>
<rect x="10" y="126" width="200" height="30"/>
<rect x="10" y="156" width="200" height="30"/>
<rect x="225" y="36" width="190" height="30" stroke-dasharray="5 4"/>
<rect x="225" y="66" width="190" height="30" stroke-dasharray="5 4"/>
<rect x="430" y="36" width="200" height="30"/>
<rect x="430" y="66" width="200" height="30"/>
<rect x="430" y="96" width="200" height="30"/>
<rect x="430" y="126" width="200" height="30"/>
<rect x="430" y="156" width="200" height="30"/>
<rect x="10" y="206" width="620" height="40" rx="6"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="110" y="56">order_id STRING</text>
<text x="110" y="86">customer_id STRING</text>
<text x="110" y="116">order_ts STRING</text>
<text x="110" y="146">amount STRING</text>
<text x="110" y="176">items (raw JSON text)</text>
<text x="320" y="56">_rescued_data</text>
<text x="320" y="86">_corrupt_record</text>
<text x="530" y="56">_source_file</text>
<text x="530" y="86">_file_modified_at</text>
<text x="530" y="116">_ingested_at</text>
<text x="530" y="146">_ingest_date (CLUSTER BY)</text>
<text x="530" y="176">_batch_id or Kafka offsets</text>
<text x="320" y="231">Append-only Delta table, CLUSTER BY (_ingest_date), access restricted</text>
</g>
</svg>
<figcaption>Figure 8.4. A bronze table in three groups of columns. The payload is stored as received (strings, or
one VARIANT column), bad data is kept rather than dropped, and the metadata says where each row came from.</figcaption>
</figure>

**Append-only.** Bronze receives inserts only. No `MERGE`, no deduplication, no updates. Two reasons: replays and
audits need the original arrivals, and downstream streams read bronze as a stream, which works cleanly only when the
source table is append-only (chapter [9.2](09-Building-Silver.md#92-reading-bronze-batch-or-stream)).

**Keep the raw payload.** Three ways, from chapter 7: all-string columns (Auto Loader's default), one `VARIANT`
column (`singleVariantColumn`), or the raw line as one string. The run in 8.4 kept even the nested `items` array as
its original JSON text.

**Metadata columns** as in 8.10, at least the source file and the ingest timestamp.

**Layout.** Most bronze reads filter on load time ("what arrived since yesterday"), so cluster by ingest date. The
"Load data in pipelines" page recommends `CLUSTER BY` (liquid clustering) "to keep query performance good as tables
grow without hand-tuning partitions". The `CREATE TABLE` in 8.4 ran here with a generated `_ingest_date` column as
the clustering key. Partitioning and liquid clustering are compared in chapter
[22](22-Performance-Tuning.md).

**Retention.** Bronze grows forever unless you decide otherwise. Decide how long raw rows must stay (for replays,
audits, legal holds), delete older rows by `_ingest_date`, and remember that `DELETE` in Delta only removes the rows
from the current version; the files stay until `VACUUM` removes them after the retention period (chapter
[4](04-Delta-Lake.md)). Separately, decide what happens to the landing files: `cloudFiles.cleanSource` or a cloud
lifecycle rule on the landing folder (never on the checkpoint).

**Personal data.** Bronze holds every field the source sent, including emails, names and addresses that silver might
mask or drop. Treat bronze as the most sensitive layer: grant it to the ingestion service principal and a few
engineers only, and expose silver and gold to everyone else (chapter
[7.4](07-Medallion-Architecture.md#74-mapping-the-layers-to-unity-catalog)). A deletion request for a customer has to
reach bronze too, which is another reason to know your retention and `VACUUM` story.

## 8.14 Idempotency, replays and common failures

*Level: expert.*

**Idempotent** means running the same load twice gives the same result as running it once. Bronze ingestion is
idempotent at the file level when the checkpoint (Auto Loader, file source, Kafka offsets) or the load history
(`COPY INTO`) survives. It is not idempotent at the record level: the same order in two files is two rows. That
split of responsibility is the core design:

- Bronze: each file or message once, enforced by the tool.
- Silver: each business record once, enforced by your `MERGE` and deduplication
  ([9.6](09-Building-Silver.md#96-deduplication) and [9.8](09-Building-Silver.md#98-idempotency-prove-a-rerun-changes-nothing)).

**Replays.** Sometimes you must reload on purpose: a parsing bug, a lost checkpoint, a new column you want for old
data. Options:

1. Reprocess from bronze into silver (bronze kept the raw payload, so no reload from source is needed). This is the
   usual answer and the reason to keep raw data.
2. Reload specific files: with `COPY INTO`, `FILES = (...)` plus `'force' = 'true'`; with Auto Loader, a separate
   one-off stream or batch read of those paths into bronze. Expect duplicates in bronze and let silver absorb them.
3. Start a new checkpoint (full reload). Every file is read again (with the default `includeExistingFiles=true`),
   so bronze gets a second copy of everything. Do this into a new table or after truncating, never into the live
   bronze table by accident.

### Common failures

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Stream fails with `UnknownFieldException` | A new column, default `addNewColumns` mode | Restart (jobs with retries do it); or choose `rescue`, `failOnNewColumns`, or `VARIANT` deliberately |
| Values land in `_rescued_data` | Type or case mismatch with the stored schema, or a hinted type that does not fit | Inspect in silver; widen types (`addNewColumnsWithTypeWidening`) or fix the source |
| Rows with only `_corrupt_record` set | Truncated or malformed lines | Alert on non-null; reprocess the file once fixed (a fixed file under the same path is not reloaded by default; land it under a new name) |
| Whole files fail to read | Corrupt file (bad compression, wrong format) | `ignoreCorruptFiles` (`COPY INTO` reports skipped files); find them with `VALIDATE` |
| Duplicate orders in bronze | Same data sent again under a new file name (run 4), a new checkpoint, or `force` | Expected; deduplicate in silver by business key |
| A corrected file was not picked up | It overwrote an already loaded path (run 5) | Send corrections as new files; `allowOverwrites` only with duplicate handling downstream |
| Files missing | Classic notifications missed events; `maxFileAge` too aggressive; `cleanSource` with two streams on one folder | `backfillInterval` (classic mode) or file events; conservative `maxFileAge`; one stream per folder |
| Late files | Upstream delay; Auto Loader has no time window, so late files load when discovered | Bronze is fine; handle event-time lateness in silver with timestamp guards and restate gold |
| Discovery slow and `LIST` costs high | Directory listing over a huge folder, often with a continuous trigger | File events; `availableNow` with file arrival triggers; `cleanSource` |
| Stream restarted "from scratch" | Checkpoint deleted by a lifecycle policy, or a new checkpoint path | Protect the checkpoint path; it is the stream's identity |
| Kafka query fails on data loss | Retention removed offsets the checkpoint still points at | Investigate the gap; `failOnDataLoss=false` only as a conscious choice |
| Stream on file events did a full listing | It had not run for over seven days | Run at least every seven days |

!!! tip "In the interview"
    **"The same file was uploaded twice with a new name. What happens and what do you do?"** Auto Loader tracks files
    by path, so the copy is a new file and its rows load again; bronze now has duplicates, which is acceptable
    because bronze is a faithful log of what arrived. Silver deduplicates by the business key (order id plus an
    ordering column), so the result is unchanged. If it happens often, also find the duplicate files with
    `_source_file` and `_file_size` and fix the sender.

## 8.15 Practice questions

*Level: mixed.*

**Q1. What is Databricks' general rule for choosing an ingestion layer?**

??? success "Answer"
    "Databricks recommends starting with the most managed layer. If it doesn't satisfy your requirements (for
    example, if it doesn't support your data source), drop down to the next layer." In order: managed connectors
    (Lakeflow Connect), then Lakeflow pipelines (formerly Delta Live Tables; see
    [What happened to DLT?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)), then Structured Streaming.

    **Why:** the more managed the layer, the less code you own for authentication, CDC, retries and schema evolution.

**Q2. Name the three layers of ingestion products and one thing each adds over the one below it.**

??? success "Answer"
    Structured Streaming (fault tolerance, exactly-once processing with Spark APIs); Lakeflow pipelines (formerly
    Delta Live Tables: declarative
    definitions, with orchestration, monitoring, data quality and error handling managed for you); managed connectors
    (source-specific authentication, CDC, edge cases, API maintenance, retries, automated schema evolution).

    **Why:** each layer is built on the one below, which is why you can drop down when a source is not supported.

**Q3. Which option is required for every Auto Loader stream, and which is required to infer the schema?**

??? success "Answer"
    `cloudFiles.format` is required ("None (required option)"). `cloudFiles.schemaLocation` is "required to infer the
    schema". In Lakeflow pipelines (formerly Delta Live Tables) the schema location and checkpoint are managed for
    you.

    **Why:** the schema location is where Auto Loader stores the inferred schema and its changes between runs; without
    it there is nowhere to remember the schema.

**Q4. A JSON file holds `{"order_id": 1001, "amount": "59.90"}`. What types does Auto Loader infer for the two
fields by default, and with `cloudFiles.inferColumnTypes = true`?**

??? success "Answer"
    By default both are `STRING`: "For formats that don't encode data types (JSON, CSV, and XML), Auto Loader infers
    all columns as strings." With `inferColumnTypes` true, `order_id` becomes a numeric type (Spark's JSON reader
    inferred `long` in the run in 8.5) but `amount` stays `STRING`, because the value is quoted text in the JSON.

    **Why:** inference reads the data as it is. A number sent as a quoted string is a string to any JSON parser.

**Q5. You switch a team from Auto Loader in Python to `read_files` in SQL and the bronze columns suddenly have
types. Why?**

??? success "Answer"
    `read_files` defaults `inferColumnTypes` to `true`, "the opposite of the default behavior of Auto Loader". Pass
    `inferColumnTypes => false` to keep strings.

    **Why:** the two share the Auto Loader engine but not all defaults; `useStrictGlobber` is also opposite
    (`true` in `read_files`).

**Q6. Scenario: an Auto Loader stream fails overnight with `UnknownFieldException` right after the source added a
`channel` field. What happened and what do you do?**

??? success "Answer"
    The default schema evolution mode `addNewColumns` saw a new column, merged it into the schema in the schema
    location, and stopped the stream on purpose. Restarting it continues with the new column; run the stream as a
    job in Lakeflow Jobs (formerly Databricks Jobs, under the old Workflows menu item; the
    [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) say "The product
    known as Databricks Jobs is now Lakeflow Jobs") with retries so this is automatic. If
    failures are not acceptable, use `rescue` (new columns go to `_rescued_data`) or ingest as `VARIANT`; if a
    strict contract is wanted, `failOnNewColumns`.

    **Why:** the docs: "Before your stream throws this error, Auto Loader performs schema inference on the latest
    micro-batch of data and updates the schema location". The failure is the signal; the restart is the fix.

**Q7. You give an Auto Loader stream an explicit `.schema(...)` and set `cloudFiles.schemaEvolutionMode` to
`addNewColumns`. What happens, and how do you keep known types while still allowing evolution?**

??? success "Answer"
    "`addNewColumns` is not allowed when the schema of the stream is provided". With a provided schema the default is
    `none`. Give the known columns as `cloudFiles.schemaHints` instead and let inference handle the rest; evolution
    "does work if you provide your schema as a schema hint".

    **Why:** a provided schema is a contract; hints are a partial override of inference.

**Q8. Scenario: the web shop's retry logic sometimes uploads the same orders file again as
`orders_20260302_0900_retry.json`. What does Auto Loader do, and where do you fix it?**

??? success "Answer"
    It loads the copy, because it "normally ingests each file only once based on its file path" and the path is new.
    Bronze gets duplicate rows (the run in 8.4 showed order 1004 twice). Fix in silver: deduplicate by business key
    with `row_number()` / `QUALIFY` or `MERGE` on `order_id`. Optionally detect duplicate files by comparing
    `_file_size` and content of rows across `_source_file` values, and fix the sender.

    **Why:** exactly-once in Auto Loader is per file path, not per record; record-level uniqueness is silver's job.

**Q9. Scenario: millions of small JSON files arrive daily in one S3 prefix, and the directory-listing stream is
getting slower and more expensive. What do you change?**

??? success "Answer"
    Move to file notification mode with file events: enable file events on the external location and set
    `cloudFiles.useManagedFileEvents` to `true`. Run as `availableNow` on a file arrival trigger or in a pipeline,
    keep the rate limits (default 1000 files per micro-batch), and consider `cloudFiles.cleanSource` to move processed
    files out. Run the stream at least every seven days so the file events cache does not expire.

    **Why:** listing cost grows with the folder ("Limited by directory size", "Highest (LIST API costs)"); file
    events scale to "Millions of files per hour" at the lowest cost.

**Q10. COPY INTO or Auto Loader: a SQL analyst needs to load about 2,000 CSV files once, and re-run the load
safely if it fails halfway. Which, and what would you say about the long term?**

??? success "Answer"
    `COPY INTO` works well: one SQL statement, idempotent and retryable, skipping files already loaded. For ongoing
    ingestion, the docs recommend streaming tables (`CREATE OR REFRESH STREAMING TABLE ... FROM STREAM read_files(...)`),
    calling them "the recommended alternative to `COPY INTO`", and two official pages (File metadata column, Spark
    API options reference) now label `COPY INTO` as legacy. For very large directories, the `COPY INTO` reference itself recommends Auto Loader "when possible".

    **Why:** both are exactly-once per file; Auto Loader adds scalable discovery, schema evolution and rescued data.

**Q11. A file already loaded by `COPY INTO` is overwritten with corrected data. You run `COPY INTO` again. What is
loaded?**

??? success "Answer"
    Nothing from that file. Files already loaded "are skipped. This is true even if the files have been modified
    since they were loaded." To reload it, use `FILES = ('that_file.csv')` with `COPY_OPTIONS ('force' = 'true')`,
    and expect the old rows to remain unless you delete them first.

    **Why:** with `force` set to `true`, "idempotency is disabled and files are loaded regardless of whether they've
    been loaded before" (SQL reference).

**Q12. What does the second call print?**

```python
load_new_files(SRC, "bronze_orders_batch")   # prints: rows loaded: 3
load_new_files(SRC, "bronze_orders_batch")
```

??? success "Answer"
    `rows loaded: 0` (the run in 8.8). The anti-join on `_source_path` removes every file already in the table.

    **Why:** idempotent loading means a rerun with no new files changes nothing; `force=True` loaded all 4 rows again.

**Q13. Write the PySpark Auto Loader stream that loads Red Rock Supply order JSON files from
`/Volumes/shop/bronze/landing/orders/` into `shop.bronze.orders` with the source file name and ingest time, as a
scheduled batch-like run.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Configure schema inference and evolution in Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema).*

    ```python
    from pyspark.sql import functions as F
    meta = "/Volumes/shop/bronze/_meta/orders/"
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", meta)
        .load("/Volumes/shop/bronze/landing/orders/")
        .select("*",
                F.col("_metadata.file_name").alias("_source_file"),
                F.current_timestamp().alias("_ingested_at"))
        .writeStream
        .option("checkpointLocation", meta)
        .trigger(availableNow=True)
        .toTable("shop.bronze.orders"))
    ```

    **Why:** `availableNow` processes everything that arrived before the start, possibly in several micro-batches,
    and stops; scheduled by a job, it is incremental batch.

**Q14. Write the same as a SQL streaming table that refreshes every hour.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Use standalone streaming tables](https://docs.databricks.com/aws/en/sql/mv-st/streaming).*

    ```sql
    CREATE OR REFRESH STREAMING TABLE shop.bronze.orders
      SCHEDULE EVERY 1 hour
    AS SELECT *, _metadata.file_name AS _source_file, current_timestamp() AS _ingested_at
    FROM STREAM read_files('/Volumes/shop/bronze/landing/orders/',
                           format => 'json',
                           inferColumnTypes => false);
    ```

    **Why:** `STREAM read_files` uses Auto Loader; without `STREAM` it would be a one-time batch read.

**Q15. Find the bug: the bronze table never gets `_source_file`.**

```python
def write_batch(df, batch_id):
    (df.withColumn("_source_file", F.col("_metadata.file_name"))
       .write.mode("append").saveAsTable("shop.bronze.orders"))

(spark.readStream.format("cloudFiles").option("cloudFiles.format", "json")
   .option("cloudFiles.schemaLocation", meta).load(landing)
   .writeStream.foreachBatch(write_batch).option("checkpointLocation", meta).start())
```

??? success "Answer"
    `_metadata` is referenced only inside `foreachBatch`. The docs: "you must reference it in the streaming read
    DataFrame before the `foreachBatch` function. If you only reference the file metadata column inside the
    `foreachBatch` function, the column is not included." Add `.select("*", "_metadata")` after `.load(landing)`.
    Also add `txnAppId`/`txnVersion` to the write so a retried batch is not appended twice.

    **Why:** the hidden column must be requested in the source query to be carried through.

**Q16. Find the bug.**

```python
.option("cloudFiles.useManagedFileEvents", "true")
.option("cloudFiles.backfillInterval", "1 day")
```

??? success "Answer"
    `cloudFiles.backfillInterval` is unsupported with file events ("Do not use when `cloudFiles.useManagedFileEvents`
    is set to `true`"). Remove it: Databricks backfills external locations with file events automatically, with a
    full listing when file events are enabled and then about every 24 hours while a stream is ingesting.

    **Why:** backfill intervals are for directory listing and classic notification mode, where you must schedule the
    safety-net listing yourself.

**Q17. Find the bug: the team adds `.option("cloudFiles.includeExistingFiles", "false")` to a stream that has
been running for a month, to stop it reading an old folder of files someone just copied in.**

??? success "Answer"
    It has no effect. "This option is evaluated only when you start a stream for the first time. Changing this option
    after restarting the stream has no effect." The copied files are new paths and will load. Move them elsewhere, or
    filter them out (for example by path), or accept and deduplicate in silver.

    **Why:** the option decides only the initial backlog of a brand-new stream.

**Q18. Find the bug.**

```python
.option("cloudFiles.cleanSource", "MOVE")
.option("cloudFiles.cleanSource.moveDestination", "/Volumes/shop/bronze/landing/orders/archive/")
.load("/Volumes/shop/bronze/landing/orders/")
```

??? success "Answer"
    The move destination is inside the source directory, so "the archived files are ingested again". Use a sibling
    path such as `/Volumes/shop/bronze/landing/archive/orders/`, in the same volume or external location.

    **Why:** the move gives each file a new path, and a new path under the load path looks like a new file.

**Q19. Find the bug: a cloud lifecycle rule deletes everything older than 30 days under
`s3://rrs-bronze/_meta/`, where the Auto Loader checkpoints live.**

??? success "Answer"
    The rule will delete checkpoint files. "If files in the checkpoint location are cleaned according to the policy,
    the stream state is corrupted. If this happens, you must restart the stream from scratch", which reloads every
    file and duplicates bronze. Exclude checkpoint paths from lifecycle rules; apply them to landing or archive
    folders instead.

    **Why:** the checkpoint is the stream's memory of which files it has loaded.

**Q20. What are the default values of `cloudFiles.maxFilesPerTrigger` and `cloudFiles.maxBytesPerTrigger`, and
which is a hard limit?**

??? success "Answer"
    `maxFilesPerTrigger` defaults to 1000 and is a hard limit; `maxBytesPerTrigger` has no default and is a soft
    limit (a file is never split, so 3 GB files can make a 12 GB micro-batch). With both set, the lower one reached
    first wins. In Databricks Runtime 18.0 and above both are configured dynamically.

    **Why:** rate limits keep the first run over a large backlog from becoming one giant, fragile micro-batch.

**Q21. An `availableNow` run starts at 02:00 and takes 40 minutes. A file lands at 02:10. When is it loaded?**

??? success "Answer"
    In the next run. `AvailableNow` processes "all files that arrived before the query start time. New files that
    arrive after the stream starts are ignored until the next trigger."

    **Why:** the run takes a snapshot of available input at start, so it always terminates.

**Q22. What is the difference between `_rescued_data` and `_corrupt_record`?**

??? success "Answer"
    `_rescued_data` holds values from records that parsed but did not fit the schema: columns missing from the schema,
    type mismatches, case mismatches, plus the source file path. `_corrupt_record` holds whole records that could not
    be parsed at all, such as truncated JSON; enable it with `columnNameOfCorruptRecord` (recommended over
    `badRecordsPath`).

    **Why:** one is schema drift, the other is broken data. Both should be null in normal operation and alerted on.

**Q23. What does this return on open-source Spark for a file with a good line, a truncated line and a line with
`"amount": "12.O0"`?**

```python
spark.read.schema("order_id INT, amount DECIMAL(10,2), currency STRING, _corrupt_record STRING") \
     .json(BAD).count()
spark.read.schema("order_id INT, amount DECIMAL(10,2), currency STRING, _corrupt_record STRING") \
     .option("mode", "DROPMALFORMED").json(BAD).count()
```

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    3, then 2. PERMISSIVE keeps all three rows. With DROPMALFORMED, `count()` drops only the truncated line: the
    count needs no columns, so Spark never converts `amount` and does not notice that `12.O0` is not a decimal. When
    the columns are actually read, as with `.show()` in 8.5, DROPMALFORMED keeps only order 1007 (1 row).

    **Why:** open-source Spark has no rescued data column, so a type mismatch counts as malformed, but only when the
    column is parsed. Never use `count()` on a raw read to measure how many records are bad. Auto Loader with the
    rescued data column would keep the `12.O0` row and rescue the value.

**Q24. Kafka: what type is the `value` column, and write the code to keep it raw and also parse it into a
`VARIANT` safely.**

??? success "Answer"
    `binary`. Cast it to string, keep it, and parse with `try_parse_json` so a bad message gives `NULL` instead of an
    error:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1 (on hand-built rows with the Kafka schema, 8.11).*

    ```python
    bronze = (kafka_df.select(F.col("value").cast("string").alias("value"),
                              "topic", "partition", "offset")
              .withColumn("v", F.try_parse_json("value")))
    ```

    **Why:** "The `key` and the `value` are always deserialized as byte arrays". `parse_json`, used in the Databricks
    example, fails on malformed JSON; `try_parse_json` returned `NULL` for the truncated message at offset 42.

**Q25. A Kafka stream is started with `startingOffsets = "earliest"`, stopped, and restarted a week later with
`startingOffsets = "latest"`. Where does it resume?**

??? success "Answer"
    From the offsets stored in its checkpoint. "For streaming queries, this option only applies when a new query
    starts. Resumed queries always use the checkpoint." The default for streaming is `latest` and for batch
    `earliest`.

    **Why:** offsets in the checkpoint are what makes a Kafka stream exactly-once into Delta; the option only seeds a
    new query.

**Q26. What column combination uniquely identifies a Kafka message, and why store it in bronze?**

??? success "Answer"
    `(topic, partition, offset)`. Storing it lets silver deduplicate a replay (for example after a new checkpoint
    re-read the topic) and trace any row back to its message.

    **Why:** offsets are unique and ordered within a partition, and partitions within a topic.

**Q27. In a Lakeflow Connect database connector, why does the ingestion gateway run continuously on classic compute
while the ingestion pipeline can run hourly?**

??? success "Answer"
    The gateway must capture changes "before change logs can be truncated in the source", so it runs all the time and
    writes to a staging volume. The ingestion pipeline (serverless) applies staged changes to the destination tables on
    any schedule. The cost consequence: you pay for the gateway's classic compute even when the pipeline is idle.

    **Why:** source change logs (binlog, WAL, CDC tables) have limited retention; staging decouples capture from apply.

**Q28. When would you choose Lakehouse Federation over a Lakeflow Connect connector?**

??? success "Answer"
    When you want to query the external database in place without copying, for ad hoc reporting or a proof of
    concept; federation is read-only. When the source supports both, "Databricks recommends Lakeflow Connect if
    performance on higher data volumes and lower latency are priorities."

    **Why:** federation pushes queries down over JDBC to the source each time; ingestion copies once and serves from
    Delta.

**Q29. A colleague wants to load a 40 MB Excel file of product categories once. What do you suggest?**

??? success "Answer"
    The file upload UI ("Create or modify a table using file upload"): it creates a managed Delta table from small
    files (up to 10 files, under 2 GB in total; one Excel file at a time, needing a SQL warehouse, serverless compute
    or Databricks Runtime 17.1 and above for Excel). No pipeline is needed for a one-off.

    **Why:** the most managed option that fits is the right one.

**Q30. Which privileges does a user need to read landed files with `read_files`?**

??? success "Answer"
    `READ FILES` on the external location, or `READ VOLUME` on the volume that holds the files.

    **Why:** `read_files` reads only through Unity Catalog external locations or volumes.

**Q31. What happens if you point an existing Auto Loader job at a new, empty checkpoint folder?**

??? success "Answer"
    It becomes a new stream: "Changing the checkpoint location effectively means that you have abandoned the previous
    stream and started a new stream." With the default `includeExistingFiles=true` it loads every file in the folder
    again, duplicating bronze.

    **Why:** the record of processed files lives only in the old checkpoint.

**Q32. Why is tuning `cloudFiles.maxFileAge` risky, and what value does Databricks suggest?**

??? success "Answer"
    It expires file tracking: too aggressive a value causes "duplicate ingestion or missing files" (old files
    re-processed after their record expires, or files older than the age ignored, also on the first start). The
    minimum is "14 days"; Databricks recommends a conservative setting "such as 90 days", and only for ingestion "at
    the order of millions of files an hour".

    **Why:** it trades checkpoint size for correctness.

**Q33. Why must a stream using file events run at least once every seven days?**

??? success "Answer"
    The file events service caches recently created files; "If Auto Loader runs infrequently, this cache can expire,
    and Auto Loader falls back to directory listing to discover files and update the cache."

    **Why:** the cheap incremental discovery depends on the cache still holding the stream's position.

**Q34. Does Auto Loader process files in order of arrival? How do you design for that?**

??? success "Answer"
    No: it "does not guarantee the order in which files are discovered or processed, regardless of whether you use
    directory listing or file notification mode". Design silver to be order-independent: compare update timestamps
    before applying an upsert, prefer soft deletes, or use `AUTO CDC` (formerly `APPLY CHANGES`; see
    [The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc)) in a Lakeflow pipeline (formerly Delta Live
    Tables) with a sequence column.

    **Why:** lexical file names help discovery efficiency but not processing order.

**Q35. Should you deduplicate in bronze? Give two reasons.**

??? success "Answer"
    No. Bronze is append-only and faithful: (1) replays and audits need what actually arrived, including duplicates
    and bad records; (2) streams from bronze to silver work cleanly only on an append-only source. Deduplicate in
    silver by business key.

    **Why:** separating "each file once" (bronze, by the tool) from "each record once" (silver, by your logic) keeps
    both simple and rerunnable.

**Q36. You write to Delta inside `foreachBatch` with a plain append. The job crashes after the write but before the
checkpoint commit, and the batch is retried. What happens, and how do you prevent it?**

??? success "Answer"
    The batch is appended twice. Use the Delta write options `txnAppId` (a fixed id for the stream) and `txnVersion`
    (the batch id). The run in 8.7 replayed batch 1 by hand with the same pair and Delta wrote nothing (no new table
    version).

    **Why:** the foreachBatch page: "You must use the `txnAppId` and `txnVersion` write options, binding `txnVersion`
    to `batchId`, to guarantee idempotency".

**Q37. A `COPY INTO` into a new placeholder table created with `CREATE TABLE IF NOT EXISTS t;` works, but an
`INSERT INTO t` run before it fails. Why?**

??? success "Answer"
    A schemaless placeholder table "is not usable outside `COPY INTO`. `INSERT INTO` and `MERGE INTO` are not
    supported to write data into schemaless Delta tables." The schema is inferred on the first `COPY INTO` (with
    `mergeSchema` true in `COPY_OPTIONS`); after that the table is queryable.

    **Why:** an empty table has no columns for `INSERT` to match.

**Q38. Scenario: order files for March 1 keep arriving on March 4 because a store's connection was down. Does Auto
Loader need any setting for late files, and where is lateness handled?**

??? success "Answer"
    No setting: Auto Loader has no time window, so a late file is loaded whenever it is discovered, with its own
    `_ingested_at` and `_file_modified_at`. Lateness is an event-time problem for silver and gold: `MERGE` with a
    timestamp guard so older updates do not overwrite newer ones, and restating the affected gold days (chapter 9
    and chapter 7's worked example).

    **Why:** bronze records arrival; business time lives in the payload (`order_ts`).

**Q39. Why does the bronze table in 8.4 store every payload column as `STRING`, even `items`, which is an array?**

??? success "Answer"
    So that nothing can fail to fit. A typed bronze turns a bad value into `NULL` or a corrupt row (shown in 8.5,
    where `12.O0` broke the typed read), while strings keep it for silver to judge. Declaring `items` as `STRING`
    kept the array's JSON text exactly as received (run 1). This matches Auto Loader's default of inferring strings
    "to avoid schema evolution issues due to type mismatches".

    **Why:** bronze's job is to keep data; typing and validation are silver's job.

**Q40. What is `cloud_files_state` and when would you use it?**

??? success "Answer"
    A table-valued function that returns metadata about the files an Auto Loader stream has discovered, given its
    checkpoint: `SELECT * FROM cloud_files_state('path/to/checkpoint')` (Databricks Runtime 11.3 LTS and above).
    Use it to answer "was this file ingested, and when?" when a row seems missing.

    **Why:** the RocksDB state in the checkpoint is not human-readable; this function exposes it.

## Sources

- [Ingest with SQL and Spark APIs](https://docs.databricks.com/aws/en/ingestion/) (last updated Oct 15, 2026)
- [What is Lakeflow Connect?](https://docs.databricks.com/aws/en/ingestion/overview) (last updated Nov 5, 2026)
- [Lakeflow Connect connector concepts](https://docs.databricks.com/aws/en/ingestion/lakeflow-connect/) (last updated Nov 3, 2026)
- [Managed database connectors](https://docs.databricks.com/aws/en/ingestion/lakeflow-connect/cdc-overview) (last updated Sep 11, 2026)
- [Managed SaaS connectors](https://docs.databricks.com/aws/en/ingestion/lakeflow-connect/saas-overview) (last updated Nov 3, 2026)
- [Create or modify a table using file upload](https://docs.databricks.com/aws/en/ingestion/create-or-modify-table) (last updated Nov 10, 2026)
- [Connect to external databases and catalogs](https://docs.databricks.com/aws/en/query-federation/) (last updated Sep 29, 2026)
- [What are Unity Catalog volumes?](https://docs.databricks.com/aws/en/volumes/) (last updated Oct 12, 2026)
- [Load data in pipelines](https://docs.databricks.com/aws/en/ldp/load) (last updated Oct 19, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc) (last updated Nov 9, 2026)
- [Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/) (last updated Nov 5, 2026)
- [June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (platform release notes: "Databricks Jobs is now Lakeflow Jobs"; last updated Oct 29, 2026)
- [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (last updated Nov 5, 2026)
- [What is Auto Loader?](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/) (last updated Oct 15, 2026)
- [Configure schema inference and evolution in Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema) (last updated Nov 5, 2026)
- [Spark API options reference](https://docs.databricks.com/aws/en/spark/api-options) (Auto Loader and Kafka options; last updated Nov 5, 2026)
- [Compare Auto Loader file detection modes](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/file-detection-modes) (last updated Sep 11, 2026)
- [Configure Auto Loader streams in directory listing mode](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/directory-listing-mode) (last updated Sep 11, 2026)
- [Configure Auto Loader streams in file notification mode](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/file-notification-mode) (last updated Oct 7, 2026)
- [Configure Auto Loader for production workloads](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/production) (last updated Nov 5, 2026)
- [Auto Loader best practices](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/best-practices) (last updated Oct 7, 2026)
- [Clean up processed files with Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/clean-source) (last updated Sep 11, 2026)
- [Auto Loader FAQ](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/faq) (last updated Oct 22, 2026)
- [Get started using COPY INTO to load data](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/copy-into/) (last updated Oct 6, 2026)
- [COPY INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-copy-into) (SQL reference; last updated Sep 11, 2026)
- [Common data loading patterns using COPY INTO](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/copy-into/examples) (last updated Sep 9, 2024)
- [Read and write XML files](https://docs.databricks.com/aws/en/query/formats/xml) (last updated Oct 30, 2026)
- [read_files table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/read_files) (last updated Nov 10, 2026)
- [Use standalone streaming tables](https://docs.databricks.com/aws/en/sql/mv-st/streaming) (last updated Oct 15, 2026)
- [File metadata column](https://docs.databricks.com/aws/en/ingestion/file-metadata-column) (last updated Sep 11, 2026)
- [Use foreachBatch to write to arbitrary data sinks](https://docs.databricks.com/aws/en/structured-streaming/foreach) (last updated Nov 5, 2026)
- [Configure Structured Streaming trigger intervals](https://docs.databricks.com/aws/en/structured-streaming/triggers) (last updated Nov 10, 2026)
- [Connect to Apache Kafka](https://docs.databricks.com/aws/en/connect/streaming/kafka/) (last updated Sep 11, 2026)- [Connect to Amazon Kinesis](https://docs.databricks.com/aws/en/connect/streaming/kinesis/) (last updated Nov 4, 2026)
- [Ingest data as semi-structured variant type](https://docs.databricks.com/aws/en/ingestion/variant) (last updated Sep 11, 2026)
- [Structured Streaming Programming Guide: APIs on DataFrames and Datasets](https://spark.apache.org/docs/4.2.0/streaming/apis-on-dataframes-and-datasets.html) (Apache Spark 4.2.0 documentation; the page shows no update date)
