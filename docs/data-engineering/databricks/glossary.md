# Glossary

*This glossary gives a short, plain definition of each term the book uses, and links to the chapter that teaches it.
Databricks renamed many products in 2025 and 2026, and interviewers often still use the old names, so the first
table lists old and new names side by side, each with the official page that states the rename. Defaults, limits and
version numbers below come from the chapters, which cite the official pages; when a page and this glossary disagree,
trust the page.*

## Old names and new names

The dates are each page's own "last updated" date, read on Nov 11, 2026 (for the blog post, its publication date).
In an interview, say both names once: "Lakeflow pipelines, formerly Delta Live Tables".

| Old name (still heard) | Name today | Official page that states the rename |
| --- | --- | --- |
| Delta Live Tables (DLT) | Lakeflow pipelines (the docs section is called "Spark Declarative Pipelines on Lakeflow"), built on open-source Apache Spark Declarative Pipelines | [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (Sep 11, 2026): "The product formerly known as Delta Live Tables (DLT) has been updated to Lakeflow pipelines." |
| `import dlt` (Python) | `from pyspark import pipelines as dp`; `@dlt.view` is now `@dp.temporary_view`, and `@dp.table` (streaming tables) and `@dp.materialized_view` replace the one `@dlt.table` | Same page (Sep 11, 2026): "references to `import dlt` can be replaced with `from pyspark import pipelines as dp`" |
| `APPLY CHANGES` (Python `apply_changes()`) | `AUTO CDC` (Python `create_auto_cdc_flow()`); the old APIs still work | [The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc) (Nov 9, 2026): "The `AUTO CDC` APIs replace the `APPLY CHANGES` APIs and have the same syntax"; [create_auto_cdc_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes) (Nov 9, 2026): it "replaces the previous function `apply_changes()`" |
| `TEMPORARY` tables in pipelines (Python `temporary=True`) | `PRIVATE` tables (Python `private=True`) | [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table) (Oct 2, 2026): "Private streaming tables were previously created with the `TEMPORARY` parameter"; [CREATE MATERIALIZED VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-materialized-view) (Oct 9, 2026); [table](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-table) (Oct 15, 2026): "Private tables were previously created with the `temporary` parameter" |
| Databricks Jobs (the left menu item was "Workflows") | Lakeflow Jobs (the menu item is now "Jobs & Pipelines") | [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (Oct 29, 2026): "The product known as Databricks Jobs is now Lakeflow Jobs" |
| Databricks Asset Bundles (DABs) | Declarative Automation Bundles | [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (Nov 5, 2026): "formerly known as Databricks Asset Bundles" |
| Delta Sharing | OpenSharing | Databricks blog, [From Delta Sharing to OpenSharing: what changed, what's next](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next) (published Nov 5, 2026): "Delta Sharing has evolved into OpenSharing". The docs page [What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/) (Oct 27, 2026) uses the new name but does not mention the old one. |
| Shared access mode; single user (assigned) access mode | Standard access mode; dedicated access mode | [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) (Oct 30, 2026): "standard access mode (formerly shared access mode) or dedicated access mode (formerly single-user or assigned access mode)" |
| Delta cache (also DBIO cache) | Disk cache | [Optimize performance with caching on Databricks](https://docs.databricks.com/aws/en/optimizations/disk-cache) (Oct 22, 2026): "formerly referred to as the Delta cache and the DBIO cache" |
| Repos | Git folders | [What happened to Databricks Repos?](https://docs.databricks.com/aws/en/repos/what-happened-repos) (Sep 11, 2026): "Repos are now called Git folders." |
| Genie Spaces | Genie Agents | [Genie Agents](https://docs.databricks.com/aws/en/genie-agents/) (Nov 2, 2026): "Genie Agents were formerly known as Genie Spaces." |
| Lakehouse Monitoring | Data profiling, one of the two capabilities of data quality monitoring (the other is anomaly detection) | [Data quality monitoring](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-quality-monitoring/) (Sep 11, 2026): "Data profiling was formerly known as Lakehouse Monitoring." |
| `workflow` system schema | `system.lakeflow` | [Jobs system table reference](https://docs.databricks.com/aws/en/admin/system-tables/jobs) (Nov 6, 2026): "The `lakeflow` schema was previously known as `workflow`. The content of both schemas is identical." |
| Community Edition | Free Edition (a replacement rather than a pure rename) | [Sign up for Databricks Free Edition](https://docs.databricks.com/aws/en/getting-started/free-edition) (Sep 11, 2026): "Free Edition replaced the legacy Databricks Community Edition, which was retired in 2025." |

## A

### ABAC policies

Attribute-based access control in Unity Catalog: a policy attached to a catalog, schema or table that applies a row
filter or column mask automatically to every table or column carrying a matching governed tag. It replaces writing
one mask per table. See [chapter 5](05-Unity-Catalog.md#abac-policies).

### Access mode

A setting on every compute resource that decides who can use it and what data they can reach. The two modes in use
are standard (formerly shared) and dedicated (formerly single user); the UI default, Auto, picks standard unless an ML
runtime, a GPU instance type or a runtime below 14.3 is chosen. See [chapter 6](06-Compute.md#66-access-modes).

### ACID transactions

Atomicity, consistency, isolation and durability: a write either commits completely or leaves no trace, and every
reader sees one consistent version of the table. Delta Lake provides them through its transaction log. See
[chapter 4](04-Delta-Lake.md#45-acid-transactions-and-optimistic-concurrency).

### Adaptive query execution

AQE re-optimizes a Spark query while it runs, using the real data sizes measured at each shuffle or broadcast: it
coalesces small shuffle partitions, switches a sort-merge join to a broadcast join when one side turns out small, and
splits skewed partitions. It is on by default in Apache Spark (since 3.2.0) and on Databricks. See
[chapter 3](03-Apache-Spark.md#38-adaptive-query-execution-and-data-skew) and
[chapter 22](22-Performance-Tuning.md#2213-aqe-on-databricks-and-join-strategies).

### All-purpose compute

Classic compute created by a person for interactive work. Several notebooks can attach to it, and it runs until
someone stops it or auto-termination fires; scheduled jobs belong on job compute or serverless instead. See
[chapter 6](06-Compute.md#63-all-purpose-compute-vs-job-compute).

### ANSI mode

SQL-standard behavior in which invalid operations (division by zero, a bad cast, an overflow) raise an error instead
of silently returning NULL or a wrapped value. It is on by default in Apache Spark 4.0, Databricks Runtime 17.0 and
above, serverless compute, and SQL warehouses of accounts created on or after October 19, 2022. See
[chapter 17](17-Databricks-SQL-vs-Standard.md#172-ansi-mode-errors-instead-of-silent-nulls).

### Apache Spark

The open-source distributed engine under Databricks. A driver plans the work and executors run it in parallel over
partitions of the data, whether you write SQL or DataFrame code. See [chapter 3](03-Apache-Spark.md).

### AUTO CDC

The Lakeflow pipelines API (formerly `APPLY CHANGES`, same syntax) that applies a change feed to a target table as
SCD Type 1 or Type 2, ordering events by a sequence column so that out-of-order changes land correctly. The Databricks
page says its AUTO CDC APIs are not supported by open-source Spark Declarative Pipelines; Apache Spark 4.2.0 added a
narrower open-source Auto CDC flow for SCD Type 1 upserts. See
[chapter 14](14-Data-Quality-and-CDC.md#1411-auto-cdc-formerly-apply-changes) and
[section 14.15](14-Data-Quality-and-CDC.md#1415-does-auto-cdc-run-in-open-source-spark).

### AUTO CDC FROM SNAPSHOT

The AUTO CDC variant for sources that have no change feed: it compares consecutive full snapshots, generates the
changes, and applies SCD Type 1 or Type 2 logic. The old Python name was `apply_changes_from_snapshot()`. See
[chapter 14](14-Data-Quality-and-CDC.md#1414-snapshots-auto-cdc-from-snapshot).

### Auto compaction

A Databricks setting that combines small files right after a successful write, on the cluster that wrote them, and
only compacts files not compacted before. It is separate from predictive optimization. See
[chapter 22](22-Performance-Tuning.md#224-file-size-on-databricks-auto-compaction-optimized-writes-target-size).

### Auto Loader

Databricks' incremental file ingestion: a Structured Streaming source called `cloudFiles` that processes new files as
they arrive in cloud storage or a volume, with schema inference and evolution, and a checkpoint that remembers which
files were loaded. In SQL it is used through `STREAM read_files(...)`. See
[chapter 8](08-Bronze-Ingestion.md#83-auto-loader-the-basics).

### Available now trigger

The Structured Streaming trigger `availableNow`: process everything available at start, possibly in several
micro-batches, then stop. It is the usual way to run a stream as a scheduled incremental batch, and it replaces the
deprecated `once` trigger. See [chapter 11](11-Structured-Streaming.md#114-triggers-rate-limits-and-cost).

## B

### Backfill

Running a pipeline again for past periods, for example days that were missed. Lakeflow Jobs has a Run backfill
action (one run per interval, at most 100 runs per backfill); the job must take its date as a parameter instead of
reading the current date. See [chapter 15](15-Lakeflow-Jobs.md#1512-backfills) and
[chapter 7](07-Medallion-Architecture.md#how-do-you-reprocess-or-backfill).

### Broadcast hash join

A join in which the small side is copied whole to every executor, so the large side is never shuffled. Spark picks
it when a side's estimated size is below `spark.sql.autoBroadcastJoinThreshold`, 10 MB by default in Apache Spark;
Databricks' adaptive threshold for switching at run time is documented at 30 MB. See
[chapter 3](03-Apache-Spark.md#37-joins-broadcast-hash-sort-merge-shuffle-hash) and
[chapter 22](22-Performance-Tuning.md#2213-aqe-on-databricks-and-join-strategies).

### Bronze layer

The first medallion layer: raw data kept as received, appended incrementally with ingest metadata, so you can
reprocess and audit. It feeds the jobs that build silver and is not meant for analysts. See
[chapter 7](07-Medallion-Architecture.md#bronze-keep-everything-exactly-as-received) and
[chapter 8](08-Bronze-Ingestion.md#813-designing-the-bronze-table).

### Business key

The identifier a source system uses for a record, such as an order number or a customer number; also called a
natural key. Silver deduplicates and merges on it; gold dimensions add a surrogate key beside it. See
[chapter 9](09-Building-Silver.md#96-deduplication) and
[chapter 10](10-Building-Gold.md#104-dimensions-and-surrogate-keys).

## C

### Catalog

The top level for data inside a Unity Catalog metastore. It contains schemas (also called databases), which hold
tables, views, volumes, functions and models, so every table has a three-part name such as `shop.silver.orders`. See
[chapter 5](05-Unity-Catalog.md#three-levels-catalog-schema-object).

### Catalyst

Spark's query optimizer. It turns a query into parsed, analyzed, optimized and physical plans, using techniques such
as predicate pushdown, column pruning and join reordering. See
[chapter 3](03-Apache-Spark.md#catalyst-and-tungsten-briefly).

### Change data capture

CDC moves only the changes of a source (inserts, updates and deletes, each with a sequence number or timestamp)
instead of full copies. The hard parts are out-of-order events, deletes and history. See
[chapter 14](14-Data-Quality-and-CDC.md#1410-change-data-capture-what-arrives-and-why-it-is-hard).

### Change data feed

CDF is a Delta feature that records row-level changes between table versions, with the extra columns
`_change_type`, `_commit_version` and `_commit_timestamp`; you read it with `table_changes()` in SQL or the
`readChangeFeed` option. The legacy form is turned on per table with `delta.enableChangeDataFeed`; Databricks also has
an automatic form (Databricks Runtime 19 and above, Unity Catalog tables). See
[chapter 9](09-Building-Silver.md#911-change-data-feed-passing-changes-on-from-silver).

### CHECK constraint

An enforced Delta constraint: a Boolean expression every row must satisfy, so a write with a violating row fails as a
whole. `NOT NULL` is the other enforced kind; primary and foreign keys are informational only. See
[chapter 14](14-Data-Quality-and-CDC.md#147-delta-check-and-not-null-constraints).

### Checkpoint (streaming)

The folder where a streaming query keeps its offsets, commits, state and metadata, so it can restart where it stopped.
Each query needs its own checkpoint; a new or deleted checkpoint makes the query start over. See
[chapter 11](11-Structured-Streaming.md#113-checkpoints-what-is-inside-and-why-each-query-needs-its-own).

### Classic compute

Compute you create, configure and manage yourself (all-purpose, job and classic pipeline compute), deployed in your
cloud account; a resource is one driver plus zero or more workers, still often called a cluster. You choose the
runtime, instance types, autoscaling (minimum and maximum workers) and auto-termination (10 to 10,000 minutes of
inactivity). See [chapter 6](06-Compute.md#62-serverless-vs-classic-compute) and
[chapter 6, section 6.8](06-Compute.md#68-sizing-classic-compute).

### Clone

`DEEP CLONE` (or plain `CLONE`) copies a Delta table's data and metadata; `SHALLOW CLONE` copies only the metadata and
points at the source's files. Clones are used for test copies, experiments and backups. See
[chapter 23](23-Governance-and-Operations.md#2310-backup-clones-and-disaster-recovery) and
chapter 20.

### Column mapping

A Delta table feature (`delta.columnMapping.mode = 'name'`) that lets you rename and drop columns without rewriting
data files, because the log maps logical column names to physical ones. See
[chapter 4](04-Delta-Lake.md#renaming-and-dropping-columns-column-mapping).

### Column mask

A SQL function attached to a column that returns the value, or a masked version, depending on who runs the query.
Each column can have one mask. See [chapter 5](05-Unity-Catalog.md#row-filters-and-column-masks-on-one-table) and
[chapter 21](21-Programming-in-SQL.md#row-filters-and-column-masks).

### Control plane and compute plane

The control plane holds the backend services and the web application, in the Databricks account. The compute plane is
where data is processed: classic compute runs in your cloud account, serverless compute in a serverless compute plane
in the Databricks account. See
[chapter 1](01-What-Is-Databricks.md#14-account-workspace-control-plane-and-compute-plane).

### COPY INTO

A SQL command that loads files into a Delta table and skips files already loaded, so a rerun is safe. It is a batch
command; two official pages now label it legacy, and Auto Loader is recommended for very many files. See
[chapter 8](08-Bronze-Ingestion.md#88-copy-into).

## D

### Data lake

Cheap cloud object storage (S3, ADLS, GCS) holding files of any kind. On its own it has no transactions and no schema
checks. See [chapter 1](01-What-Is-Databricks.md#12-data-warehouse-data-lake-and-lakehouse).

### Data mesh

An organizational approach: domain teams own their data as products on a shared platform under federated governance.
Each domain can run its own bronze, silver and gold. See [chapter 7](07-Medallion-Architecture.md#data-mesh).

### Data profiling

Formerly Lakehouse Monitoring; one of the two capabilities of data quality monitoring. It attaches a profile to one
table and computes summary statistics and drift over time into metric tables and a dashboard. See
[chapter 23](23-Governance-and-Operations.md#237-monitoring-alerting-and-observability).

### Data quality monitoring

The Unity Catalog feature with two capabilities: anomaly detection (freshness and completeness, per schema) and data
profiling (statistics per table). It covers problems you did not write a rule for. See
[chapter 23](23-Governance-and-Operations.md#237-monitoring-alerting-and-observability).

### Data skipping

Delta records per-file statistics (minimum, maximum, null count, record count) in the log, and a query skips files
whose ranges cannot match its filter. For Unity Catalog external tables, statistics cover the first 32 columns by
default. See [chapter 22](22-Performance-Tuning.md#226-data-skipping-per-file-minmax-statistics).

### Data Vault

A modeling method for the integration layer: hubs (business keys), links (relationships) and satellites (attributes
with history). Some teams use it in silver; the Databricks pages used in this book do not discuss it. See
[chapter 7](07-Medallion-Architecture.md#data-vault).

### Data warehouse

A database built for analytics: clean, structured tables and fast SQL for business intelligence reports. See
[chapter 1](01-What-Is-Databricks.md#12-data-warehouse-data-lake-and-lakehouse).

### Databricks CLI

The `databricks` command-line tool for workspace files, jobs, secrets and bundles; `databricks auth login` signs in
with OAuth and saves a configuration profile. See [chapter 2](02-Workspace-Tour.md#the-cli).

### Databricks Connect

A library that lets code in an IDE or a CI runner send DataFrame operations to Databricks compute, while general
Python code runs locally. It is built on Spark Connect. See [chapter 2](02-Workspace-Tour.md#databricks-connect) and
[chapter 16](16-CICD-and-Testing.md#integration-tests-in-staging).

### Databricks Runtime

DBR: the set of components that runs on classic compute, Apache Spark plus Databricks additions such as Delta Lake,
Photon and connectors; serverless compute and SQL warehouses are versioned by Databricks. LTS (long-term support)
versions get fixes for years, and Databricks recommends the latest LTS for production job compute. See
[chapter 6](06-Compute.md#67-databricks-runtime-versions).

### DBU

A Databricks unit, "units of processing capability per hour based on VM instance type", the basis of billing. On
classic compute you also pay the cloud provider for the machines; for serverless the DBU price includes them. See
[chapter 1](01-What-Is-Databricks.md#15-how-databricks-bills-dbus) and
[chapter 6](06-Compute.md#610-what-drives-cost-and-how-to-keep-it-down).

### dbutils

Databricks utilities available in notebooks: `fs` for files, `secrets`, `widgets`, `notebook.run` and `notebook.exit`,
and `jobs.taskValues`. `%run` runs another notebook inline, while `dbutils.notebook.run()` starts it as a separate run
and gets one string back. See [chapter 2](02-Workspace-Tour.md#27-dbutils).

### Declarative Automation Bundles

Formerly Databricks Asset Bundles (DABs): a folder of source files plus YAML that describes jobs, pipelines and other
resources, deployed per target (dev, staging, prod) with `databricks bundle validate`, `deploy` and `run`. It is
infrastructure as code for Databricks. See [chapter 16](16-CICD-and-Testing.md#163-declarative-automation-bundles) and
[chapter 15](15-Lakeflow-Jobs.md#1510-jobs-as-code-bundles-cli-and-rest-api).

### Dedicated access mode

Formerly single user (or assigned) access mode: compute assigned to one user or one group. Use it for what standard
mode does not allow, such as R, RDD APIs, GPUs and the ML runtime. See [chapter 6](06-Compute.md#66-access-modes).

### Deduplication

Keeping one row per business key. `dropDuplicates` removes exact copies only; to keep the latest version, rank rows
with `row_number()` per key and keep rank 1, often with `QUALIFY`. A stream can use
`dropDuplicatesWithinWatermark`. See [chapter 9](09-Building-Silver.md#96-deduplication) and
[chapter 11](11-Structured-Streaming.md#deduplication).

### Deletion vectors

A Delta feature: `DELETE`, `UPDATE` and `MERGE` mark changed rows in a small side file instead of rewriting the whole
data file, and reads apply the marks. Writes get cheaper, reads do a little more work, and `REORG TABLE ... APPLY
(PURGE)` rewrites the files. See [chapter 4](04-Delta-Lake.md#deletion-vectors) and
[chapter 22](22-Performance-Tuning.md#228-deletion-vectors-cheap-writes-a-little-extra-read-work).

### Delta Lake

The open table format under Databricks tables: Parquet data files (a compressed columnar format) plus a transaction
log, which gives ACID transactions, schema enforcement, time travel and `MERGE`. It is the default table format on
Databricks. See [chapter 4](04-Delta-Lake.md).

### Delta Live Tables

DLT, the old name of Lakeflow pipelines. Existing DLT code keeps working without migration. See
[chapter 13](13-Declarative-Pipelines.md#131-from-delta-live-tables-to-lakeflow-pipelines).

### DESCRIBE HISTORY and DESCRIBE DETAIL

`DESCRIBE HISTORY` lists a Delta table's commits, newest first, with version, time, user, operation and metrics.
`DESCRIBE DETAIL` returns one row about the current version: location, number of files, size, clustering columns and
protocol versions. See
[chapter 4](04-Delta-Lake.md#47-time-travel-describe-history-describe-detail-and-restore).

### Dimension table

A table that gives context to facts: customer, product, date. Its rows are what reports filter and group by. Facts
plus dimensions make a dimensional model; Databricks says star and snowflake schemas perform well and recommends
against third normal form for a new lakehouse. See
[chapter 7](07-Medallion-Architecture.md#dimensional-models) and
[chapter 10](10-Building-Gold.md#104-dimensions-and-surrogate-keys).

### Directory listing and file notification

The two ways Auto Loader finds new files. Directory listing, the default, lists the folder; file notification
receives an event per new file, and Databricks recommends it (using file events) for most workloads. See
[chapter 8](08-Bronze-Ingestion.md#86-file-detection-directory-listing-vs-file-notification).

### Disk cache

Formerly the Delta cache (or DBIO cache): Databricks keeps copies of remote Parquet files on the workers' local disks,
automatically, and notices when files change; Databricks recommends it over the Spark cache for repeated reads of
Delta tables. SQL warehouses also have a query result cache, kept 24 hours and invalidated when the tables change.
See [chapter 22](22-Performance-Tuning.md#2211-caching-disk-cache-spark-cache-result-cache).

### Driver

The Spark process that runs your program or notebook cell, plans queries and sends tasks to executors. Anything you
`collect()` must fit in its memory. See
[chapter 3](03-Apache-Spark.md#32-cluster-architecture-driver-executors-cores-and-tasks).

## E

### Event log

A hidden Delta table each Lakeflow pipeline writes, with audit, data quality, progress and lineage events; you query
it with `event_log()`. Delivery is best effort. See [chapter 13](13-Declarative-Pipelines.md#1310-monitoring-and-limitations)
and [chapter 14](14-Data-Quality-and-CDC.md#144-expectation-metrics-in-the-event-log).

### Exactly-once

After any failure and restart, every input record affects the output exactly once. Structured Streaming needs a
replayable source, a checkpoint and an idempotent sink for it; `foreachBatch` is at-least-once unless your writes are
idempotent. See [chapter 11](11-Structured-Streaming.md#119-exactly-once-end-to-end).

### Executor

A process on a worker node that runs tasks and keeps data in memory or on disk; on Databricks one runs per worker
node. See [chapter 3](03-Apache-Spark.md#32-cluster-architecture-driver-executors-cores-and-tasks).

### Expectations

Named data quality rules on Lakeflow pipeline datasets: a SQL Boolean constraint plus an action for failing rows, warn
(the default: keep the row and count it), drop or fail. Their metrics go to the event log. See
[chapter 14](14-Data-Quality-and-CDC.md#142-expectations-in-lakeflow-pipelines).

### Explode

`explode` turns each element of an array (or entry of a map) into its own row; `explode_outer` keeps rows whose array
is empty or NULL, and `posexplode` adds the position. Exploding changes the grain, so totals at order level are counted
once per item. See [chapter 18](18-Semi-Structured-Data.md#186-exploding-arrays-and-maps).

### External location

A Unity Catalog object that pairs a storage credential (an IAM role on AWS, a service principal on Azure, a service
account on GCP) with a cloud storage path. External tables, external volumes and managed storage locations sit inside
one. See [chapter 5](05-Unity-Catalog.md#storage-credentials-and-external-locations).

### External table

A table whose governance Unity Catalog handles while you (or another system) own the files at a path you chose.
`DROP TABLE` removes only the metadata. See [chapter 5](05-Unity-Catalog.md#54-managed-vs-external-tables).

## F

### Fact table

A table of events with measures, at a declared grain such as one row per order line, with keys to dimension tables.
See [chapter 10](10-Building-Gold.md#105-the-fact-table) and [chapter 7](07-Medallion-Architecture.md#kimball-star-schemas).

### Flow

In a Lakeflow pipeline, the unit that reads a source, applies your logic and writes a target. Several append flows
can write into one streaming table, each with its own checkpoint named after the flow, so renaming a flow makes it a
new flow that reads its source again. See [chapter 13](13-Declarative-Pipelines.md#133-the-building-blocks) and
[chapter 13](13-Declarative-Pipelines.md#136-flows-in-depth-many-sources-one-table).

### foreachBatch

A streaming sink that calls your function once per micro-batch with an ordinary DataFrame and the batch id; it is how
you `MERGE` a stream into a Delta table. It is at-least-once unless the writes are idempotent, for example with
Delta's `txnAppId` and `txnVersion` write options. See
[chapter 11](11-Structured-Streaming.md#118-foreachbatch-with-merge) and
[chapter 11](11-Structured-Streaming.md#the-txnappid-trap).

### Free Edition

Databricks Free Edition: a no-cost, serverless-only, quota-limited workspace for learning. It replaced Community
Edition, which was retired in 2025. See [chapter 2](02-Workspace-Tour.md#25-practising-for-free-databricks-free-edition).

### Full refresh

A Lakeflow pipeline update that, for a streaming table, clears its data and checkpoints and reprocesses everything the
source still holds. If the source has expired old data (a Kafka topic with short retention), that history is lost. See
[chapter 13](13-Declarative-Pipelines.md#the-full-refresh-warning).

## G

### Generated column

A Delta column whose value is computed from other columns of the same row with `GENERATED ALWAYS AS (expression)`,
for example a date derived from a timestamp. See chapter 20 and
[chapter 4](04-Delta-Lake.md#protocol-versions-and-table-features).

### Genie Agents

Formerly Genie Spaces: a natural-language chat over curated data, part of Databricks AI/BI. See
[chapter 1](01-What-Is-Databricks.md#13-the-pieces-of-the-platform-in-todays-names).

### Git folders

Formerly Repos: workspace folders synced with a remote Git repository, so you can branch, commit and pull from the
workspace. Old `/Repos` paths keep working. See [chapter 2](02-Workspace-Tour.md#28-git-folders) and
[chapter 16](16-CICD-and-Testing.md#git-and-git-folders).

### Gold layer

The medallion layer of refined, business-aligned tables for dashboards, analytics and ML: usually dimensional models
and aggregates, optimized for queries. See
[chapter 7](07-Medallion-Architecture.md#gold-answer-business-questions-fast) and
[chapter 10](10-Building-Gold.md#101-what-gold-is-for).

### Grain

What one row of a table means, in business words: "one row per order line". Joins and `explode` can change it, and
measures must be summed at the grain they belong to. See
[chapter 10](10-Building-Gold.md#103-grain-first) and
[chapter 18](18-Semi-Structured-Data.md#performance-explode-multiplies-rows).

### GROUP BY ALL

Groups by every SELECT-list expression that is not an aggregate (Databricks Runtime 12.2 LTS and above); `ORDER BY
ALL` sorts by every SELECT-list expression. Adding a column to the SELECT list silently changes the grain. See
[chapter 17](17-Databricks-SQL-vs-Standard.md#group-by-all-and-order-by-all).

### GROUPING SETS, ROLLUP and CUBE

Several groupings in one query, with subtotal rows: `ROLLUP (a, b)` gives `(a, b)`, `(a)` and the grand total; `CUBE`
gives every combination. `grouping()` and `grouping_id()` tell which level a row belongs to. See
[chapter 19](19-Function-Toolbox.md#198-grouping-sets-rollup-and-cube).

## H

### Higher-order functions

Functions that take an array or map plus a lambda (`x -> expr`) and work inside each row: `transform`, `filter`,
`exists`, `forall` and `aggregate`. The row count does not change. See
[chapter 18](18-Semi-Structured-Data.md#188-higher-order-functions-and-lambdas).

### Hive metastore

The legacy per-workspace metastore from before Unity Catalog. In a Unity Catalog workspace it appears as a catalog
named `hive_metastore`. See [chapter 5](05-Unity-Catalog.md#what-hive_metastore-is).

## I

### Iceberg

Apache Iceberg, another open table format. Databricks supports managed Iceberg tables in Unity Catalog, and Iceberg
reads of Delta tables (UniForm), which adds Iceberg metadata without rewriting the Parquet files. See
[chapter 23](23-Governance-and-Operations.md#iceberg-interoperability).

### Idempotent

An operation you can repeat with the same result. Every hop of a pipeline must survive a rerun or retry: `MERGE` on a
key, `REPLACE WHERE` on a slice, checkpoints for streams. A plain `INSERT` is not idempotent. See
[chapter 7](07-Medallion-Architecture.md#79-idempotent-loads-why-every-hop-must-survive-a-rerun) and
[chapter 15](15-Lakeflow-Jobs.md#158-failures-repair-runs-and-idempotent-tasks).

### IDENTIFIER clause

Turns a string constant or parameter into a table, column, function, schema or catalog name, without SQL injection
risk (Databricks Runtime 13.3 LTS and above). A parameter marker alone cannot stand for a name. See
[chapter 17](17-Databricks-SQL-vs-Standard.md#the-identifier-clause).

### Identity column

A Delta `BIGINT` column whose values Delta assigns to each inserted row, declared `GENERATED ALWAYS AS IDENTITY` (or
`BY DEFAULT`); the values are unique but not guaranteed to be contiguous. It is one way to make surrogate keys. In a pipeline, Databricks recommends them only on streaming tables, because a materialized
view can recompute the values on refresh. See [chapter 10](10-Building-Gold.md#identity-columns-a-counter-for-each-new-row),
[chapter 19](19-Function-Toolbox.md#monotonically_increasing_id-is-not-a-sequence) and
[chapter 13](13-Declarative-Pipelines.md#1312-practice-questions).

### Incremental refresh

A materialized view refresh that processes only what changed. It needs serverless compute and supported query
shapes; a cost model chooses between incremental and full recompute, with the same result either way. See
[chapter 13](13-Declarative-Pipelines.md#138-incremental-refresh-of-materialized-views).

### Isolation level

How Delta treats concurrent writes. Databricks' default is WriteSerializable (writes are serializable, a blind append
does not conflict); Serializable is stricter. Reads always see one snapshot. See
[chapter 4](04-Delta-Lake.md#writeserializable-and-serializable).

## J

### Job compute

Classic compute created by the job scheduler for one job run; it terminates when the run ends. It costs less than
all-purpose compute for scheduled work. See [chapter 6](06-Compute.md#63-all-purpose-compute-vs-job-compute).

### Job parameters

Key-value pairs set on a Lakeflow job, with defaults you can override per run; they are pushed down to tasks that take
key-value parameters. Notebooks read them as widgets. See
[chapter 15](15-Lakeflow-Jobs.md#154-parameters-dynamic-value-references-and-task-values).

### Job, stage and task (Spark)

A Spark job is what one action starts. It is split into stages at shuffle boundaries, and each stage runs one task per
partition on the executors. See
[chapter 3](03-Apache-Spark.md#35-narrow-and-wide-transformations-shuffles-jobs-stages-and-tasks).

### Job, task and trigger (Lakeflow Jobs)

A Lakeflow job holds tasks (notebooks, pipelines, scripts, SQL and more) whose dependencies form a directed acyclic
graph, plus a trigger that starts it; one job run executes the graph once. Run if conditions, If/else condition tasks
and For each tasks add branches and loops, and dynamic value references (placeholders in double curly braces) fill in
values when a run starts. See [chapter 15](15-Lakeflow-Jobs.md#151-jobs-tasks-and-triggers) and
[chapter 15](15-Lakeflow-Jobs.md#153-the-task-graph-dependencies-run-if-branches-and-loops).

### Job triggers

What starts a Lakeflow job: a schedule (Quartz cron syntax), file arrival in a Unity Catalog volume or external
location (checked about every minute), a table update on monitored tables, or continuous (a new run whenever the last
one ends, for always-on streaming). Without a trigger a job runs only when started by hand or through the API. See
[chapter 15](15-Lakeflow-Jobs.md#155-triggers).

## K

### Kafka

Apache Kafka, a message bus. Spark reads it with `format("kafka")`, and the stream's checkpoint stores offsets per
partition instead of file names. Kafka keeps messages only for its retention period, which limits replays. See
[chapter 8](08-Bronze-Ingestion.md#811-message-buses-kafka-kinesis-event-hubs).

## L

### Lakeflow Connect

The ingestion part of Lakeflow: managed connectors for databases (with change data capture), SaaS applications and
files, which create ingestion pipelines into Unity Catalog streaming tables on serverless compute. See
[chapter 8](08-Bronze-Ingestion.md#812-lakeflow-connect-managed-connectors).

### Lakeflow Jobs

Formerly Databricks Jobs (the Workflows menu item): Databricks' orchestrator, which runs jobs made of tasks with
dependencies, triggers, parameters, retries and notifications. See [chapter 15](15-Lakeflow-Jobs.md).

### Lakeflow pipelines

Formerly Delta Live Tables: declarative pipelines in SQL or Python made of streaming tables, materialized views,
views and flows; the pipeline builds the dependency graph and manages checkpoints. They are built on Apache Spark
Declarative Pipelines and add expectations, AUTO CDC, the event log and serverless incremental refresh. See
[chapter 13](13-Declarative-Pipelines.md).

### Lakehouse

"A data management system that combines the benefits of data lakes and data warehouses": data in open formats in
cloud object storage, with a metadata layer that adds transactions, governance and fast queries. On Databricks it rests
on Spark, Delta Lake and Unity Catalog. See
[chapter 1](01-What-Is-Databricks.md#12-data-warehouse-data-lake-and-lakehouse).

### Lakehouse Federation

Governed, read-only access to external databases and catalogs through Unity Catalog foreign catalogs, either by
pushing queries down to the database (query federation) or by reading foreign tables in storage (catalog federation).
See [chapter 23](23-Governance-and-Operations.md#lakehouse-federation).

### Late-arriving data

Events that arrive after newer events for the same key, or after their time window. Streams handle them with
watermarks; `MERGE` needs a "newer wins" guard; AUTO CDC uses a sequence column. See
[chapter 9](09-Building-Silver.md#97-late-and-out-of-order-data-in-merge) and
[chapter 11](11-Structured-Streaming.md#116-event-time-watermarks-and-late-data).

### LATERAL VIEW

A Hive-style clause that applies a generator such as `explode` to each row and joins the generated rows back to it.
See [chapter 17](17-Databricks-SQL-vs-Standard.md#lateral-view-and-table-valued-functions) and
[chapter 18](18-Semi-Structured-Data.md#where-the-generator-goes-select-list-lateral-view-or-from).

### Lazy evaluation

Spark transformations only build a plan; nothing runs until an action asks for a result. Seeing the whole plan lets
Spark read only the needed columns and push filters down to the files. See
[chapter 3](03-Apache-Spark.md#34-lazy-evaluation-the-four-plans-catalyst-and-tungsten).

### Lineage

Unity Catalog records automatically, down to the column level, which notebooks, jobs, pipelines and queries read and
write each table, across all workspaces on the metastore. See [chapter 5](05-Unity-Catalog.md#lineage).

### Liquid clustering

Clustering keys declared on the table with `CLUSTER BY`; `OPTIMIZE` or predictive optimization keeps the data
clustered incrementally, and the keys can change without rewriting existing data. Databricks recommends it instead of
partitioning and Z-ordering; it is generally available for Delta tables on Databricks Runtime 15.4 LTS and above. See
[chapter 22](22-Performance-Tuning.md#liquid-clustering).

## M

### Managed table

A table whose governance and file lifecycle are both controlled by Unity Catalog; the files stay in your cloud
account. `DROP TABLE` deletes the files after a recovery period (7 days by default), during which `UNDROP` works.
Predictive optimization works only on managed tables. See [chapter 5](05-Unity-Catalog.md#54-managed-vs-external-tables).

### Materialized view

A table that stores the result of a query and is refreshed by a pipeline, correct as of its last refresh even when
data arrived late. On serverless it can refresh incrementally; it can also be created standalone from Databricks SQL.
See [chapter 13](13-Declarative-Pipelines.md#133-the-building-blocks).

### max_by and min_by

Aggregates that return the value of one expression on the row where another is largest or smallest, for example the
latest status per customer. With ties the result is non-deterministic. See
[chapter 19](19-Function-Toolbox.md#max_by-and-min_by-the-value-at-the-max).

### Medallion architecture

A data design pattern of three layers, bronze (raw), silver (validated) and gold (enriched), that improves the
structure and quality of data step by step. Databricks calls it a recommended best practice, not a requirement. See
[chapter 7](07-Medallion-Architecture.md).

### MERGE

An upsert in one atomic Delta commit: update matched rows, insert unmatched ones, and optionally delete target rows
missing from the source (`WHEN NOT MATCHED BY SOURCE`). If several source rows match one target row it fails, so
deduplicate the source first. See [chapter 4](04-Delta-Lake.md#44-update-delete-and-merge) and
[chapter 9](09-Building-Silver.md#the-multiple-source-rows-matched-error).

### Metastore

The top-level container of Unity Catalog. There is one per cloud region, it can be attached to many workspaces in that
region, and its grants apply in all of them. See [chapter 5](05-Unity-Catalog.md#the-metastore).

### Metric views

A Unity Catalog object that defines business measures and dimensions once (in YAML) so that dashboards, Genie Agents
and SQL queries compute them the same way; it is created with `CREATE VIEW ... WITH METRICS LANGUAGE YAML` and its measures are queried with the `MEASURE`
function. See [chapter 10](10-Building-Gold.md#109-metric-views-the-semantic-layer).

## N

### Narrow and wide transformations

A narrow transformation (`filter`, `select`) builds each output partition from one input partition, with no data
movement. A wide one (`groupBy`, most joins, `distinct`, `orderBy`) needs rows from many partitions and causes a
shuffle. See [chapter 3](03-Apache-Spark.md#35-narrow-and-wide-transformations-shuffles-jobs-stages-and-tasks).

### Null-safe equality

The `<=>` operator, a synonym for `IS NOT DISTINCT FROM`: true when both sides are NULL, false when only one is. The
plain `=` returns NULL when either side is NULL. See [chapter 17](17-Databricks-SQL-vs-Standard.md).

## O

### OpenSharing

Formerly Delta Sharing: Databricks' platform for sharing data and AI assets with other organizations, whether or not
they use Databricks; a share (a read-only collection of tables and more) and a recipient are Unity Catalog objects.
Clean rooms build on it so that several parties can work on combined data without seeing each other's raw data. See
[chapter 23](23-Governance-and-Operations.md#239-sharing-and-interoperability).

### Optimistic concurrency

Delta writers take no locks: each reads the latest version, writes new files, then checks at commit time whether a
concurrent commit conflicts. On a conflict the write fails and must be retried. See
[chapter 4](04-Delta-Lake.md#optimistic-concurrency-step-by-step).

### OPTIMIZE

Rewrites many small files into fewer large ones without changing the data; a second run on the same data does
nothing. With `ZORDER BY` or liquid clustering it also co-locates related rows. See
[chapter 4](04-Delta-Lake.md#small-files) and
[chapter 22](22-Performance-Tuning.md#223-the-small-files-problem-made-visible).

### Optimized writes

A Databricks setting that shuffles data before writing so each partition gets fewer, larger files; most useful for
partitioned tables, at some cost in write latency. See
[chapter 22](22-Performance-Tuning.md#224-file-size-on-databricks-auto-compaction-optimized-writes-target-size).

### Output mode

Which rows of a streaming result are written at each trigger: append (the default, rows that will not change),
complete (the whole result) or update (changed rows only). It matters for aggregations. See
[chapter 11](11-Structured-Streaming.md#115-output-modes).

## P

### Parameter markers

Typed placeholders in SQL, named (`:name`) or unnamed (`?`), whose values are passed separately from the SQL text,
which prevents SQL injection; one statement cannot mix the two kinds. `EXECUTE IMMEDIATE` runs SQL held in a string
and binds markers with `USING`. See [chapter 17](17-Databricks-SQL-vs-Standard.md#parameter-markers) and
[chapter 21](21-Programming-in-SQL.md#215-dynamic-sql-without-sql-injection).

### Partition (Spark)

A chunk of rows processed by one task. Too few partitions leave cores idle; too many create tiny tasks. See
[chapter 3](03-Apache-Spark.md#36-partitions).

### Partitioning (tables)

Storing each value of a column in its own folder so filters on it read only matching folders (partition pruning).
Databricks says tables under 1 TB should not be partitioned and recommends liquid clustering for 1 to 100 TB. See
[chapter 22](22-Performance-Tuning.md#225-partitioning-when-it-helps-and-when-it-hurts).

### Photon

The Databricks-native vectorized query engine, written in C++, which processes data in columnar batches. It is on in
serverless compute, SQL warehouses and serverless pipelines, does not run UDFs or RDD code (it falls back to Spark),
and is not part of open-source Spark. See [chapter 6](06-Compute.md#65-photon) and
[chapter 22](22-Performance-Tuning.md#2210-photon).

### Pipeline

In Lakeflow, "a collection of source code files and a configuration": the files declare datasets and flows, and the
pipeline infers the dependency graph and runs it in order. One run is called an update. See
[chapter 13](13-Declarative-Pipelines.md#134-pipelines-source-files-the-graph-and-the-settings).

### PIVOT and UNPIVOT

`PIVOT` turns row values into columns (one column per currency, for example); `UNPIVOT` turns columns back into rows.
See [chapter 17](17-Databricks-SQL-vs-Standard.md#176-reshaping-pivot-unpivot-lateral-view-and-table-valued-functions).

### Predictive optimization

Databricks runs `OPTIMIZE`, `VACUUM` and `ANALYZE` automatically on Unity Catalog managed tables, so you do not schedule
that maintenance yourself. The page says it is enabled by default; it needs the Premium plan or above. See
[chapter 22](22-Performance-Tuning.md#229-predictive-optimization).

### Private table

A pipeline dataset declared `PRIVATE` (Python `private=True`), formerly `TEMPORARY`: it is used inside the pipeline but
not published to the catalog. See [chapter 13](13-Declarative-Pipelines.md#sql).

### Privileges

Permissions in Unity Catalog, given with `GRANT` and taken away with `REVOKE`. Nothing is allowed until granted;
reading a table needs `USE CATALOG`, `USE SCHEMA` and `SELECT`; a grant on a catalog or schema applies to all current
and future objects inside. See [chapter 5](05-Unity-Catalog.md#56-privileges-grant-revoke-inheritance-and-ownership).

## Q

### QUALIFY

Filters rows on the result of a window function, as `HAVING` does for aggregates (Databricks Runtime 10.4 LTS and
above). Its everyday use is keeping the latest row per key. See [chapter 17](17-Databricks-SQL-vs-Standard.md#qualify).

### Quarantine pattern

Rows that fail the data rules go to a separate quarantine table with the reasons, instead of being dropped silently or
failing the whole load. See [chapter 9](09-Building-Silver.md#95-the-quarantine-pattern) and
[chapter 14](14-Data-Quality-and-CDC.md#145-quarantine-with-expectations).

### Query profile

The per-operator view of an executed query on SQL warehouses and serverless compute: time, rows and memory for each
step, opened for example from Query History. It is not available for queries served from the result cache. See
[chapter 22](22-Performance-Tuning.md#222-the-query-profile-and-performance-insights).

## R

### read_files

A table-valued function (Databricks Runtime 13.3 LTS and above) that reads files in a location and returns rows,
detecting the format and schema. Wrapped in `STREAM`, it is Auto Loader in SQL. See
[chapter 8](08-Bronze-Ingestion.md#89-read_files-and-streaming-tables).

### Recursive CTE

A `WITH RECURSIVE` query that refers to itself: a base case plus a step joined with `UNION ALL`, repeated until the step
returns no rows. Used for date spines and hierarchies. See
[chapter 21](21-Programming-in-SQL.md#218-recursive-ctes-series-and-hierarchies).

### Repair run

Rerunning only the failed or canceled tasks of a Lakeflow job run, plus the tasks that depend on them, with the
current settings. It works for jobs with two or more tasks. See
[chapter 15](15-Lakeflow-Jobs.md#158-failures-repair-runs-and-idempotent-tasks).

### Repartition and coalesce

`repartition(n)` reshuffles data into n even partitions, up or down; `coalesce(n)` only reduces the count, merging
neighbor partitions without a shuffle, which can leave them uneven. See
[chapter 3](03-Apache-Spark.md#repartition-vs-coalesce).

### REPLACE WHERE

`INSERT INTO ... REPLACE WHERE condition` atomically replaces the rows matching the condition with the query's
result, for example one day of a gold table; in PySpark it is the `replaceWhere` option. Rerunning it gives the same
table. See [chapter 7](07-Medallion-Architecture.md#gold-daily-sales-with-replace-where) and
[chapter 15](15-Lakeflow-Jobs.md#158-failures-repair-runs-and-idempotent-tasks).

### Rescued data column

`_rescued_data`, which Auto Loader adds when it infers the schema: it keeps values that parsed but did not fit (a
column missing from the schema, a type or case mismatch) together with the source file path. Lines that cannot be
parsed at all go to `_corrupt_record` instead. See
[chapter 8](08-Bronze-Ingestion.md#85-schema-inference-hints-evolution-and-rescued-data).

### RESTORE

`RESTORE TABLE ... TO VERSION AS OF` (or `TIMESTAMP AS OF`) brings a Delta table back to an earlier version, recorded as
a new commit; the usual fix after a bad `DELETE`. The old data files must not have been vacuumed. See
[chapter 4](04-Delta-Lake.md#scenario-someone-ran-delete-without-where).

### Row filter

A SQL function attached to a table that returns a Boolean for each row; rows where it returns false are hidden from
that user, and a table can have one. A dynamic view does the same inside a view's SQL, with functions such as
`is_account_group_member()`. See [chapter 5](05-Unity-Catalog.md#57-row-level-security-and-column-masking) and
[chapter 21](21-Programming-in-SQL.md#219-views-dynamic-views-row-filters-and-column-masks).

### Run as

The identity whose privileges a Lakeflow job's tasks use, separate from the job's owner. Databricks recommends a
service principal, so jobs keep working when people leave. See
[chapter 15](15-Lakeflow-Jobs.md#159-run-as-service-principals-and-job-permissions).

## S

### Salting

A fix for skew: add a random salt to the hot key on the big side and copy the small side once per salt value, so one
key's rows spread over several tasks. Try AQE's skew handling first. See [chapter 3](03-Apache-Spark.md#data-skew) and
[chapter 22](22-Performance-Tuning.md#2214-skew-aqe-first-salting-second).

### SCD Type 1

A slowly changing dimension (SCD) is a dimension whose rows change now and then, like a customer who moves. Type 1
keeps only current values: an update overwrites the row, and no history is kept. See
[chapter 9](09-Building-Silver.md#99-scd-type-1-with-merge).

### SCD Type 2

A slowly changing dimension that keeps history: a change closes the current row (a `valid_to` time,
`is_current = false`) and inserts a new current row. AUTO CDC stores the range in `__START_AT` and `__END_AT`. See
[chapter 9](09-Building-Silver.md#910-scd-type-2-with-merge) and
[chapter 14](14-Data-Quality-and-CDC.md#what-the-scd-type-2-target-looks-like).

### Schema enforcement

A write must match the table's schema (columns that exist, compatible types) or it is rejected. Delta does this on
every write. See [chapter 4](04-Delta-Lake.md#46-schema-enforcement-and-schema-evolution).

### Schema evolution

Explicitly letting a write change the table's schema, for example with the `mergeSchema` option or `MERGE WITH SCHEMA
EVOLUTION`; new columns are added at the end and old rows read NULL for them. Auto Loader's default mode stops the
stream on a new column and picks it up on restart. See [chapter 4](04-Delta-Lake.md#schema-evolution) and
[chapter 8](08-Bronze-Ingestion.md#evolution-what-the-default-mode-actually-does).

### Secrets

Passwords and keys kept out of code: workspace secret scopes, or Unity Catalog secrets (`catalog.schema.secret`), read
in notebooks with `dbutils.secrets`. See [chapter 2](02-Workspace-Tour.md#secrets) and
[chapter 23](23-Governance-and-Operations.md#235-secrets-service-principals-and-least-privilege).

### Sequence column

The column that orders change events in AUTO CDC (`SEQUENCE BY`). In SCD Type 1, changes older than the current
version are dropped; in SCD Type 2, they are inserted into history in sequence order. See
[chapter 14](14-Data-Quality-and-CDC.md#1412-how-the-sequence-column-fixes-out-of-order-events).

### Serverless compute

Compute that Databricks allocates and manages for notebooks, jobs, pipelines and SQL warehouses; it starts fast and
runs in the Databricks account. The DBU price includes the machines, and serverless notebooks and jobs support only
the `availableNow` trigger for streams (plus the deprecated `once`). See [chapter 6](06-Compute.md#62-serverless-vs-classic-compute).

### Service principal

An identity for automated tools and applications rather than a person. Production jobs should run as one, and CI should
deploy as one. See [chapter 15](15-Lakeflow-Jobs.md#159-run-as-service-principals-and-job-permissions) and
[chapter 16](16-CICD-and-Testing.md#who-deploys-and-who-runs).

### Shuffle

Moving rows between executors so that rows with the same key meet, shown as an `Exchange` in the plan. Each shuffle is
a stage boundary and costs network and disk. See
[chapter 3](03-Apache-Spark.md#35-narrow-and-wide-transformations-shuffles-jobs-stages-and-tasks).

### Silver layer

The validated medallion layer: typed, cleaned, deduplicated data with one row per business record, built from bronze.
Late and out-of-order data and SCDs are handled here. See
[chapter 7](07-Medallion-Architecture.md#silver-one-trustworthy-row-per-business-record) and
[chapter 9](09-Building-Silver.md).

### Sink

Where a stream writes. In Structured Streaming: a Delta table, Kafka, or your own code through `foreachBatch`. In a
Lakeflow pipeline, a sink is a target outside the pipeline's tables (an external Delta table, Kafka, Event Hubs or
custom code), defined in Python only. See [chapter 11](11-Structured-Streaming.md#sinks) and
[chapter 13](13-Declarative-Pipelines.md#133-the-building-blocks).

### Skew

One key with far more rows than the rest, so one task does most of the work after a shuffle. In the Spark UI the
stage's maximum task time is far above the 75th percentile. See [chapter 3](03-Apache-Spark.md#data-skew) and
[chapter 22](22-Performance-Tuning.md#2214-skew-aqe-first-salting-second).

### skipChangeCommits

An option on a Delta streaming source that ignores commits that changed existing rows and processes only appends;
without it, an `UPDATE` or `DELETE` on the source makes the stream fail. The change itself is not passed on. See
[chapter 9](09-Building-Silver.md#what-breaks-a-stream-from-a-delta-table).

### Small-files problem

Many tiny files make queries slow, because time goes into opening files rather than reading data. Frequent small
appends, streams and over-partitioned tables cause it; `OPTIMIZE`, auto compaction and optimized writes fix it. See
[chapter 22](22-Performance-Tuning.md#223-the-small-files-problem-made-visible).

### Sort-merge join

Spark's default join for two large tables: both sides are shuffled by the key, sorted, then merged. See
[chapter 3](03-Apache-Spark.md#37-joins-broadcast-hash-sort-merge-shuffle-hash).

### Spark cache

`cache()`, `persist()` and `CACHE TABLE` keep a computed DataFrame on the executors for reuse. Databricks advises
against caching Delta tables this way (filters lose data skipping, data can go stale) and prefers the disk cache. See
[chapter 3](03-Apache-Spark.md#39-caching-and-persistence) and
[chapter 22](22-Performance-Tuning.md#2211-caching-disk-cache-spark-cache-result-cache).

### Spark Connect

A client-server protocol (Apache Spark 3.4 and later): the client sends unresolved query plans over gRPC and gets
results back as Arrow batches. Standard access mode and Databricks Connect use it. See
[chapter 3](03-Apache-Spark.md#spark-connect-and-databricks-connect).

### Spark Declarative Pipelines

The open-source declarative pipeline engine in Apache Spark (from 4.1): the `pyspark.pipelines` module and the
`spark-pipelines` command. Lakeflow pipelines are built on it; expectations and the event log are Databricks
additions. See [chapter 13](13-Declarative-Pipelines.md#1311-run-here-open-source-spark-declarative-pipelines).

### Spark UI

The web UI that shows a Spark application's jobs, stages, tasks, storage and SQL plans with their metrics; on
Databricks it opens from the compute page. See [chapter 3](03-Apache-Spark.md#the-spark-ui).

### Spill

Data written to local disk during a sort, join or aggregation because it did not fit in memory; the query still
succeeds but slows down. Fixes include auto-optimized shuffle partitions and selecting fewer columns. See
[chapter 22](22-Performance-Tuning.md#2215-spill-memory-shuffle-partitions-and-the-driver).

### SQL scripting

Procedural SQL in a `BEGIN ... END` block with local variables, `IF`, `CASE`, loops and error handlers (Databricks
Runtime 16.3 and above, SQL warehouses). See
[chapter 21](21-Programming-in-SQL.md#212-sql-scripts-blocks-local-variables-and-scope).

### SQL warehouse

The compute behind Databricks SQL: SQL only, Photon always on, used by the SQL editor, dashboards and BI tools. It
comes in three types: serverless (the default choice, with Intelligent Workload Management to queue queries and add
clusters), pro and classic. See [chapter 6](06-Compute.md#64-sql-warehouses) and
[chapter 17](17-Databricks-SQL-vs-Standard.md#171-where-databricks-sql-runs).

### Standard access mode

Formerly shared access mode: many users share one compute resource, and Lakeguard runs each user's code in full
isolation; Unity Catalog row filters and column masks are enforced directly. It does not support R or RDD APIs. See
[chapter 6](06-Compute.md#66-access-modes).

### Star schema

One fact table joined to dimension tables (a snowflake schema normalizes the dimensions further). It comes from
Ralph Kimball's dimensional modeling, which also gives conformed dimensions (one dimension shared by several fact
tables) and slowly changing dimensions; gold is often a Kimball star schema. See
[chapter 7](07-Medallion-Architecture.md#kimball-star-schemas) and
[chapter 10](10-Building-Gold.md#102-dimensional-modelling-on-the-lakehouse).

### Stateful operations

Streaming operations that remember data between micro-batches: windowed aggregations, deduplication and
stream-stream joins. The state lives in a state store saved in the checkpoint (RocksDB is the default provider in
Databricks Runtime 17.3 LTS and above), and watermarks keep it from growing forever. See
[chapter 11](11-Structured-Streaming.md#1111-stateful-operations-windows-deduplication-and-joins) and
[chapter 11](11-Structured-Streaming.md#1112-the-state-store-and-changing-a-stateful-query).

### Stored procedure

A SQL script saved under a name in Unity Catalog, with parameters, run with `CALL` (Databricks Runtime 17.0 and
above). You can grant others the right to run it without giving them direct write access. See
[chapter 21](21-Programming-in-SQL.md#217-stored-procedures-create-procedure-and-call).

### Streaming table

"A Delta table with additional support for streaming or incremental data processing": each record of an append-only
source is processed once. It is owned by one pipeline and fed by one or more flows. See
[chapter 13](13-Declarative-Pipelines.md#133-the-building-blocks).

### Structured Streaming

Spark's streaming engine: you write a batch-like query over a table that keeps growing, and Spark runs it
incrementally in micro-batches, tracking progress in a checkpoint. See [chapter 11](11-Structured-Streaming.md).

### Surrogate key

A key generated in the warehouse instead of taken from the source, so that a dimension can hold several versions of one
business key. Use an identity column or a deterministic hash of the business key, not `monotonically_increasing_id`.
See [chapter 10](10-Building-Gold.md#104-dimensions-and-surrogate-keys) and
[chapter 19](19-Function-Toolbox.md#monotonically_increasing_id-is-not-a-sequence).

### System tables

Read-only tables in the `system` catalog about your account: billing (`system.billing.usage`), audit
(`system.access.audit`), jobs and pipelines (`system.lakeflow`) and more; `system.information_schema` describes the
objects in all catalogs. They need Unity Catalog, and access must be granted. See
[chapter 5](05-Unity-Catalog.md#58-finding-out-what-exists-information_schema-system-tables-and-lineage) and
[chapter 15](15-Lakeflow-Jobs.md#1511-monitoring-runs-with-system-tables).

## T

### Table features

Named capabilities in a Delta table's protocol (such as deletion vectors, column mapping or liquid clustering) that a
client must support to read or write the table. Enabling one upgrades the protocol, often for good. See
[chapter 4](04-Delta-Lake.md#protocol-versions-and-table-features).

### Tags

Keys with optional values attached to Unity Catalog objects, down to columns, to organize and find data such as
personal data. Governed tags are account-level tags with rules on allowed values and on who may assign them; ABAC
policies select tables and columns by them. See
[chapter 23](23-Governance-and-Operations.md#232-tags-and-classification-finding-the-personal-data).

### Task values

Small results (valid JSON, at most 48 KiB) that one Lakeflow Jobs task passes to later tasks, set and read with
`dbutils.jobs.taskValues` in Python notebooks. See
[chapter 15](15-Lakeflow-Jobs.md#154-parameters-dynamic-value-references-and-task-values).

### Testing pyramid

Many fast tests at the bottom, fewer slow ones on top: unit tests of business logic in `src/` modules with pytest,
bundle validation, then integration tests that run the deployed job in a staging workspace. Data tests (for example
`assert_true` checks in a job task) run against the real tables after each load and fail the run when the data is
wrong. See [chapter 16](16-CICD-and-Testing.md#166-the-testing-pyramid-for-data-pipelines) and
[chapter 16](16-CICD-and-Testing.md#168-data-tests-and-integration-tests).

### Time travel

Querying an earlier version of a Delta table with `VERSION AS OF` or `TIMESTAMP AS OF`. It reaches back only as far as
`VACUUM` and log retention allow, so it is not a backup. See
[chapter 4](04-Delta-Lake.md#47-time-travel-describe-history-describe-detail-and-restore) and
[chapter 23](23-Governance-and-Operations.md#2310-backup-clones-and-disaster-recovery).

### TIMESTAMP and TIMESTAMP_NTZ

`TIMESTAMP` is an instant, stored in UTC and shown in the session time zone, so the displayed date can change with
the zone. `TIMESTAMP_NTZ` holds date and time fields with no time zone: what you insert is what you read. See
[chapter 19](19-Function-Toolbox.md#session-time-zone-timestamp-and-timestamp_ntz).

### Transaction log

The `_delta_log` folder of a Delta table: one JSON file per commit, and from time to time a checkpoint, a Parquet file
with the full table state at one version so readers replay only the later commits. The log, not the folder listing,
decides which data files belong to the table. See
[chapter 4](04-Delta-Lake.md#42-what-a-delta-table-is-data-files-plus-a-transaction-log) and
[chapter 4](04-Delta-Lake.md#snapshots-and-checkpoints).

### Transformations and actions

Transformations (`select`, `filter`, `join`, `groupBy`) add steps to the plan and run nothing; actions (`count`,
`show`, `collect`, writes) make Spark run the plan. See
[chapter 3](03-Apache-Spark.md#34-lazy-evaluation-the-four-plans-catalyst-and-tungsten).

### Trigger (streaming)

Decides when a stream runs its next micro-batch: unspecified (as soon as the last one ends), a processing-time
interval, available now (process what is there, then stop), or Databricks' real-time mode. The `once` trigger is
deprecated. See [chapter 11](11-Structured-Streaming.md#114-triggers-rate-limits-and-cost).

### try_ functions

Functions such as `try_cast`, `try_divide` and `try_to_timestamp` that do the same work as their strict versions but
return NULL instead of raising an error, which is useful for cleaning bad input under ANSI mode. See
[chapter 19](19-Function-Toolbox.md#the-try_-family) and
[chapter 9](09-Building-Silver.md#cast-fails-the-query-try_cast-returns-null).

## U

### UNDROP

Brings back a dropped managed table within the recovery period, 7 days by default. See
[chapter 5](05-Unity-Catalog.md#undrop-and-the-recovery-period).

### Unity Catalog

Databricks' governance layer for data and AI: the `catalog.schema.object` namespace, access control, auditing,
lineage and discovery, shared by all workspaces attached to a metastore. It is enabled automatically for workspaces
created after November 8, 2023. See [chapter 5](05-Unity-Catalog.md).

### User-defined function

A UDF is your own function called from SQL or DataFrames. Python UDFs are a black box to the optimizer and move rows to
a Python process, so built-in functions are faster; SQL UDFs and Unity Catalog Python UDFs can be stored and granted.
See [chapter 3](03-Apache-Spark.md#311-udfs-vs-built-in-functions) and
[chapter 21](21-Programming-in-SQL.md#216-user-defined-functions-sql-and-python).

## V

### VACUUM

Deletes data files no longer referenced by a Delta table and older than the retention threshold (7 days by default).
It does not delete log files, and versions whose files are gone can no longer be read. See
[chapter 4](04-Delta-Lake.md#48-vacuum-and-retention).

### VARIANT

A data type for semi-structured data such as JSON, stored in an optimized encoding parsed once at write time; a new
field in the feed is simply kept. You read fields with the `:` path and cast with `::`; for JSON kept as a string,
`from_json` parses it into a typed struct. See
[chapter 18](18-Semi-Structured-Data.md#184-variant-what-it-is-and-why-databricks-recommends-it) and
[chapter 18](18-Semi-Structured-Data.md#183-json-kept-as-a-string).

### Volume

A Unity Catalog object that governs non-tabular files, reached under paths like `/Volumes/catalog/schema/volume/`.
It is the usual landing area for raw files. See [chapter 5](05-Unity-Catalog.md#volumes) and
[chapter 8](08-Bronze-Ingestion.md#82-where-files-land-volumes-and-external-locations).

## W

### Watermark

A limit on how late data may be in a stream, based on event time (when the event happened, a column in the data):
the latest event time seen minus a threshold. Windows older than the watermark are final and their state is dropped;
data later than the threshold may or may not be counted. See
[chapter 11](11-Structured-Streaming.md#116-event-time-watermarks-and-late-data).

### Widgets

Input parameters on a notebook (text, dropdown, combobox, multiselect) whose values are always strings. A job passes
its parameters to a notebook task through them. See [chapter 2](02-Workspace-Tour.md#26-widgets-and-parameters).

### Window functions

Functions computed over related rows without collapsing them: ranking, `lag` and `lead`, running totals. With
`ORDER BY` and no frame, the default frame runs from the start of the partition to the current row (a range frame).
See [chapter 19](19-Function-Toolbox.md#199-window-functions-in-depth).

### Workload identity federation

CI authentication without a stored secret: the CI system's signed token is exchanged for Databricks OAuth tokens as
a service principal, after a federation policy says which issuer and subject to trust. Databricks calls it the most
secure option; the older OAuth machine-to-machine way needs an OAuth secret that must be stored and rotated. See
[chapter 16](16-CICD-and-Testing.md#165-authentication-for-ci).

### Workspace

A Databricks workspace is "the collaboration environment where users run compute workloads": notebooks, files,
jobs, pipelines and dashboards. Workspaces sit under one account, the top-level construct where identities,
workspaces, metastores and billing are managed; a company often has separate dev and prod workspaces. See
[chapter 1](01-What-Is-Databricks.md#14-account-workspace-control-plane-and-compute-plane) and
[chapter 2](02-Workspace-Tour.md#21-the-workspace-map).

### Workspace-catalog binding

Restricting a catalog to chosen workspaces, optionally read-only. Access from other workspaces is denied even to users
with grants, which keeps development workspaces away from production data. See
[chapter 5](05-Unity-Catalog.md#workspace-catalog-binding).

## Z

### Z-ordering

`OPTIMIZE ... ZORDER BY (col)` rewrites files so rows with close values share files, which narrows the min and max
ranges data skipping uses. It suits high-cardinality filter columns; Databricks now recommends liquid clustering
instead. See [chapter 22](22-Performance-Tuning.md#z-ordering).

## Sources

- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc) (last updated Nov 9, 2026)
- [create_auto_cdc_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes) (last updated Nov 9, 2026)
- [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table) (last updated Oct 2, 2026)
- [CREATE MATERIALIZED VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-materialized-view) (last updated Oct 9, 2026)
- [table](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-table) (last updated Oct 15, 2026)
- [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026)
- [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (last updated Nov 5, 2026)
- [From Delta Sharing to OpenSharing: what changed, what's next](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next) (Databricks blog, published Nov 5, 2026)
- [What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/) (last updated Oct 27, 2026)
- [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) (last updated Oct 30, 2026)
- [Optimize performance with caching on Databricks](https://docs.databricks.com/aws/en/optimizations/disk-cache) (last updated Oct 22, 2026)
- [What happened to Databricks Repos?](https://docs.databricks.com/aws/en/repos/what-happened-repos) (last updated Sep 11, 2026)
- [Genie Agents](https://docs.databricks.com/aws/en/genie-agents/) (last updated Nov 2, 2026)
- [Data quality monitoring](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-quality-monitoring/) (last updated Sep 11, 2026)
- [Jobs system table reference](https://docs.databricks.com/aws/en/admin/system-tables/jobs) (last updated Nov 6, 2026)
- [Sign up for Databricks Free Edition](https://docs.databricks.com/aws/en/getting-started/free-edition) (last updated Sep 11, 2026)
- [Apache Spark 4.2.0 release notes](https://spark.apache.org/releases/spark-release-4-2-0.html) (no date shown; read Nov 11, 2026), for the open-source Auto CDC flow
