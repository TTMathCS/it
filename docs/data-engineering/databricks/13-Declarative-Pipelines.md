# 13. Lakeflow Spark Declarative Pipelines

*Most data engineering on Databricks ends up as a pipeline: files land, a bronze table picks them up, silver cleans them, gold summarizes them. Chapters 8 to 12 built those steps by hand with Structured Streaming and Delta. This chapter shows the declarative way, the product interviewers still call Delta Live Tables (DLT): you declare the tables and the queries that fill them, and the engine works out the order, the checkpoints, the retries and which rows to reprocess. You will learn the building blocks, the SQL and Python syntax, what an update and a full refresh really do, and you will run a small pipeline with the open-source engine to see the behavior for yourself.*

!!! abstract "In this chapter"
    **You will learn:**

    - where the name Delta Live Tables went, and the two names to use in an interview
    - declarative versus procedural pipelines, and when each fits
    - streaming tables, materialized views, views, flows and sinks, and when to use each
    - how a pipeline is configured (source files, target catalog and schema, serverless or classic, channel, triggered or continuous) and how an update runs
    - refresh, full refresh and checkpoint reset, and why a full refresh can lose data
    - incremental refresh of materialized views, standalone materialized views and streaming tables, the event log
    - a small Red Rock Supply pipeline run with open-source Spark Declarative Pipelines 4.2

    **You need:** [Delta Lake](04-Delta-Lake.md), [The medallion architecture](07-Medallion-Architecture.md), [Into bronze: ingestion](08-Bronze-Ingestion.md) (Auto Loader and `read_files`) and [Structured Streaming](11-Structured-Streaming.md) (checkpoints, triggers).

    **Levels:** sections 13.1 to 13.3 beginner, 13.4 to 13.8 intermediate, 13.9 to 13.11 expert.

Expectations (data quality rules) and `AUTO CDC` (formerly `APPLY CHANGES`) belong to these pipelines too; they have their own chapter, [Data quality and change data capture in pipelines](14-Data-Quality-and-CDC.md). Here they are only mentioned.

## 13.1 From Delta Live Tables to Lakeflow pipelines

*Level: beginner.*

The product has had three names, and you will hear all of them. The official page "What happened to Delta Live Tables (DLT)?" (last updated Sep 11, 2026) says:

> The product formerly known as Delta Live Tables (DLT) has been updated to Lakeflow pipelines. If you have previously used DLT, there is no migration required to use Lakeflow pipelines: your code will still work.

The documentation section itself is titled **Spark Declarative Pipelines on Lakeflow**, and calls the product **Lakeflow pipelines** for short. Behind the new name, Databricks donated the declarative engine to Apache Spark ("We're donating Declarative Pipelines ... to Apache Spark", Databricks blog, Jun 12, 2025): **Apache Spark Declarative Pipelines (SDP)**, part of open-source Spark from version 4.1. The overview page says "Lakeflow pipelines are built on Apache Spark Declarative Pipelines and are interoperable with it. They extend it with additional functionality and run on the performance-optimized Databricks Runtime."

| You may hear | What it is today | Where the name still shows |
| --- | --- | --- |
| Delta Live Tables, DLT | Lakeflow pipelines (Spark Declarative Pipelines on Lakeflow) | The page notes that "the classic SKUs for Lakeflow pipelines still begin with `DLT`, and event log schemas with `dlt` in the name have not changed" |
| `import dlt`, `@dlt.table`, `@dlt.view` | `from pyspark import pipelines as dp`, `@dp.table`, `@dp.materialized_view`, `@dp.temporary_view` | Old names "can still be used, but Databricks recommends moving to the new names" |
| `APPLY CHANGES INTO`, `dlt.apply_changes` | `AUTO CDC INTO`, `dp.create_auto_cdc_flow` | Chapter 14 |
| Apache Spark Declarative Pipelines | the open-source framework underneath, `pyspark.pipelines`, `spark-pipelines` CLI | Section 13.11 |

The Python rename is not only cosmetic. In the old `dlt` module, `@dlt.table` made a streaming table or a materialized view depending on whether the function returned a streaming or a batch DataFrame. In the new module, `@dp.table` is for streaming tables and `@dp.materialized_view` is for materialized views, and `@view` became `@temporary_view`.

!!! tip "In the interview"
    **"Have you used Delta Live Tables?"** Answer with both names: "Yes, Delta Live Tables, which Databricks now calls Lakeflow pipelines or Spark Declarative Pipelines. Old DLT code still runs without migration; the new Python module is `pyspark.pipelines`, imported as `dp`, with `@dp.table` for streaming tables and `@dp.materialized_view` for materialized views. The core engine is now open source in Apache Spark as Spark Declarative Pipelines, and Databricks adds features such as AUTO CDC, expectations and the event log on top."

## 13.2 Declarative versus procedural

*Level: beginner.*

Start from the problem. In chapter 11 you wrote a bronze-to-silver stream by hand: a `readStream`, a `writeStream` with a checkpoint path, a trigger, and a job that runs the streams in the right order and restarts them when they fail. Add a gold aggregate and a second source and you also need to decide what runs first, what to do when one step fails, and how to rebuild a table when its logic changes. That code is *procedural*: you say how, step by step.

The page "Procedural vs. declarative data processing in Databricks" (last updated Nov 5, 2026) defines the two:

- "With procedural programming you specify how tasks should be accomplished by defining explicit sequences of operations."
- "Declarative programming focuses on what needs to be achieved, leaving the underlying system to determine the best way to execute the task."

In a declarative pipeline you write only the *definitions*: "the table `silver_orders` is this query over `bronze_orders`". The pipeline reads all the definitions, builds the dependency graph, and runs it. The page's comparison table:

| Aspect | Procedural processing | Declarative processing |
| --- | --- | --- |
| Control | Full control over execution | Execution handled by system |
| Complexity | Can be complex and verbose | Generally simpler and more concise |
| Optimization | Requires manual tuning | System handles optimization |
| Flexibility | High, but requires expertise | Lower, but easier to use |
| Use cases | Custom pipelines, performance tuning | SQL queries, managed pipelines |

It places "Apache Spark and Lakeflow Jobs" on the procedural side and pipelines on the declarative side. The "Pipeline concepts" page (last updated Nov 5, 2026) lists what you get compared with hand-written Spark and Structured Streaming code orchestrated by Lakeflow Jobs:

- **Automatic orchestration**: flows run "in the correct order with maximum parallelism", and transient failures are retried "progressively: from the Spark task, to the flow, to the entire pipeline".
- **Declarative processing**: a few declarative lines replace manual Spark and Structured Streaming code; `AUTO CDC` handles change data capture "without manual code for out-of-order events or streaming concepts like watermarks".
- **Incremental processing**: you write materialized views with batch semantics and the engine "reprocesses only new or changed source data when possible".

Choose procedural code when, in the words of the same page, "fine-grained control over execution logic is required", when "transformations involve complex business rules that are difficult to express declaratively", or when "performance optimizations necessitate manual tuning". A typical example is a `foreachBatch` that writes one micro-batch to three systems with custom error handling.

!!! tip "In the interview"
    **"Why would you use DLT instead of a Structured Streaming job scheduled by Workflows?"** "With Delta Live Tables, now Lakeflow pipelines, I declare tables and their queries; the pipeline builds the dependency graph, manages checkpoints, retries failures at task, flow and pipeline level, and gives me data quality expectations, AUTO CDC and an event log. With plain Structured Streaming plus Lakeflow Jobs (formerly Workflows) I write and order every stream, checkpoint and retry myself, which is more work but gives full control. I pick the pipeline for standard ingest-clean-aggregate work and hand-written code for unusual sinks or logic the declarative model cannot express."

## 13.3 The building blocks

*Level: beginner.*

A pipeline produces *datasets* and moves data with *flows*. The "Pipeline concepts" page names three dataset types and how each processes records:

| Dataset type | How records are processed (quoted from the docs) |
| --- | --- |
| Streaming table | "Each record is processed exactly one time, assuming an append-only source." Suited "for ingestion and incremental processing of continuously growing data." |
| Materialized view | "Results are recomputed as needed to reflect the current state of the data." Suited "for transformations, aggregations, or pre-computing results consumed by multiple downstream datasets." |
| View | "Evaluated on demand, not persisted." For "intermediate transformations and checks that do not need to be published to a catalog." |

**Streaming table.** "A streaming table is a Delta table with additional support for streaming or incremental data processing" (page "Streaming tables", last updated Oct 9, 2026). It is a Unity Catalog managed table that is also a streaming target. It is owned by one pipeline: "Tables defined by a pipeline can't be changed or updated by any other pipeline." One or more flows write into it.

**Materialized view.** A Unity Catalog managed table that stores the result of a query and is refreshed by the pipeline. It is "always correct at the time of their update. All required data is processed, even if it arrives late or out of order" (page "Materialized views", last updated Oct 15, 2026). Its flow is always defined implicitly by its query.

**View.** In a pipeline, a temporary view (`CREATE TEMPORARY VIEW`, `@dp.temporary_view`) is private to the pipeline and not added to the catalog. There is also `CREATE VIEW` in pipeline SQL, which publishes a normal view to Unity Catalog; its reference page lists limits such as "Views cannot have streaming queries, or be used as a streaming source" and "Expectations, in the form of `CONSTRAINT` clauses, are not supported."

**Flow.** "A flow reads data from a source, applies user-defined processing logic, and writes the result into a target." When you write `CREATE STREAMING TABLE ... AS SELECT`, the pipeline creates a *default flow* with the same name as the table. You can also define flows separately, so several flows write into one table (section 13.6). Flow types: *append* (the default), *AUTO CDC* (formerly apply changes; chapter 14) and *update* (Public Preview, Python only, writes to sinks).

**Sink.** A streaming target outside the pipeline's managed tables: an external Delta table, a Kafka or Azure Event Hubs topic, a Python custom data source, or custom `ForEachBatch`/`ForEach` code. The "Sinks" page (last updated Oct 25, 2026) lists the limits: "Sinks are only available in Python. SQL is not supported", "Only streaming queries are supported", "Pipeline expectations are not supported for sinks" and "Running a full refresh does not clean up previously written data in sinks."

### When to use which

The "Pipeline concepts" page gives the decision rules. Paraphrased:

| Use a ... | when |
| --- | --- |
| View | you want to break a complex query into parts, validate intermediate results with expectations, or avoid storing results nobody reads outside the pipeline |
| Materialized view | several downstream queries read it; other pipelines, jobs or users query it; you want to inspect results during development; the query aggregates or joins, or "the source data can change due to updates and deletes rather than only growing" |
| Streaming table | the source grows continuously or incrementally; results should be computed incrementally; the pipeline "needs high throughput and low latency" |

The deciding question is usually: **is the source append-only?** Files landing in storage and events on Kafka are append-only, so they go into streaming tables. A join to a dimension that changes, or an aggregate that must stay correct when rows are corrected, belongs in a materialized view. The streaming tables page states the trade-off bluntly: "Joins in streaming tables do not recompute when dimensions change. This characteristic can be good for 'fast-but-wrong' scenarios. If you want your view to always be correct, you might want to use a materialized view."

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Streaming table versus materialized view refresh behavior">
<rect x="8" y="8" width="304" height="284" rx="8" fill="none" stroke="currentColor"/>
<rect x="328" y="8" width="304" height="284" rx="8" fill="none" stroke="currentColor"/>
<text x="160" y="32" text-anchor="middle" font-size="15" font-weight="bold" fill="currentColor">Streaming table</text>
<text x="480" y="32" text-anchor="middle" font-size="15" font-weight="bold" fill="currentColor">Materialized view</text>
<text x="30" y="58" font-size="13" fill="currentColor">append-only source</text>
<rect x="30" y="66" width="40" height="26" fill="none" stroke="currentColor"/><text x="50" y="84" text-anchor="middle" font-size="13" fill="currentColor">r1</text>
<rect x="74" y="66" width="40" height="26" fill="none" stroke="currentColor"/><text x="94" y="84" text-anchor="middle" font-size="13" fill="currentColor">r2</text>
<rect x="118" y="66" width="40" height="26" fill="none" stroke="currentColor"/><text x="138" y="84" text-anchor="middle" font-size="13" fill="currentColor">r3</text>
<line x1="166" y1="60" x2="166" y2="100" stroke="currentColor" stroke-dasharray="4 3"/>
<rect x="174" y="66" width="40" height="26" fill="none" stroke="currentColor"/><text x="194" y="84" text-anchor="middle" font-size="13" fill="currentColor">r4</text>
<rect x="218" y="66" width="40" height="26" fill="none" stroke="currentColor"/><text x="238" y="84" text-anchor="middle" font-size="13" fill="currentColor">r5</text>
<text x="166" y="116" text-anchor="middle" font-size="13" fill="currentColor">checkpoint after update 1</text>
<line x1="94" y1="124" x2="94" y2="150" stroke="currentColor"/><path d="M89 144 L94 152 L99 144" fill="none" stroke="currentColor"/>
<line x1="216" y1="124" x2="216" y2="150" stroke="currentColor"/><path d="M211 144 L216 152 L221 144" fill="none" stroke="currentColor"/>
<text x="94" y="168" text-anchor="middle" font-size="13" fill="currentColor">update 1: r1-r3</text>
<text x="216" y="168" text-anchor="middle" font-size="13" fill="currentColor">update 2: r4-r5</text>
<text x="30" y="200" font-size="13" fill="currentColor">Each row is read once and appended.</text>
<text x="30" y="222" font-size="13" fill="currentColor">A changed query applies to new rows only.</text>
<text x="30" y="244" font-size="13" fill="currentColor">Full refresh: truncate, clear checkpoints,</text>
<text x="30" y="264" font-size="13" fill="currentColor">replay whatever the source still holds.</text>
<rect x="350" y="52" width="260" height="44" fill="none" stroke="currentColor"/>
<text x="480" y="71" text-anchor="middle" font-size="13" fill="currentColor">source tables: rows inserted,</text>
<text x="480" y="88" text-anchor="middle" font-size="13" fill="currentColor">updated or deleted</text>
<line x1="480" y1="96" x2="480" y2="128" stroke="currentColor"/><path d="M475 122 L480 130 L485 122" fill="none" stroke="currentColor"/>
<text x="490" y="117" font-size="13" fill="currentColor">refresh</text>
<rect x="350" y="132" width="260" height="44" fill="none" stroke="currentColor"/>
<text x="480" y="151" text-anchor="middle" font-size="13" fill="currentColor">result = defining query over</text>
<text x="480" y="168" text-anchor="middle" font-size="13" fill="currentColor">the current source data</text>
<text x="350" y="200" font-size="13" fill="currentColor">Incremental when possible (serverless</text>
<text x="350" y="222" font-size="13" fill="currentColor">only), otherwise full recompute.</text>
<text x="350" y="244" font-size="13" fill="currentColor">Same result either way; a full refresh</text>
<text x="350" y="264" font-size="13" fill="currentColor">just recomputes everything.</text>
</svg>
<figcaption>Figure 13.1. A streaming table reads each new source row once and appends it; a materialized view always equals its query over the current source.</figcaption>
</figure>

!!! tip "In the interview"
    **"When would you pick a materialized view over a streaming table?"** "When the result must always match the source: aggregates, joins to dimensions that change, or sources with updates and deletes. A streaming table reads each row once, so corrections upstream and dimension changes never reach rows it already wrote. I use streaming tables for append-only ingestion and low-latency transforms, and materialized views for gold aggregates and joins. In Delta Live Tables terms, now Lakeflow pipelines, that is the classic bronze and silver as streaming tables, gold as materialized views."

## 13.4 Pipelines: source files, the graph and the settings

*Level: intermediate.*

"A pipeline is a collection of source code files and a configuration" (page "What are pipelines?", last updated Oct 15, 2026). The source files declare datasets and flows; the configuration says how and where the pipeline runs.

**Source files.** Python or SQL; "A single pipeline can mix Python and SQL source files, but each file can contain only one language." New pipelines keep code in a `transformations` folder, and because the pipeline analyzes dependencies across all files, "you can organize source code across files in any order." The limitations page caps a pipeline at 100 source files when the configuration lists only individual files, or 50 source entries (files or folders) with up to 1,000 files referenced in total when it includes folders.

**The graph.** "Pipelines automatically infer dependencies between datasets and arrange them in a directed acyclic graph (DAG). The graph determines evaluation order: upstream datasets are computed before downstream ones." You never write "run bronze, then silver": the graph comes from the table names your queries read. A dataset can be defined only once, so a cycle or a second definition of the same table is an error at planning time.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 270" role="img" aria-label="Pipeline graph from landing files through bronze and silver streaming tables to gold materialized views">
<defs><marker id="a131" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="currentColor"/></marker></defs>
<rect x="8" y="40" width="122" height="44" rx="4" fill="none" stroke="currentColor" stroke-dasharray="2 2"/>
<text x="69" y="66" text-anchor="middle" font-size="13" fill="currentColor">landing/web</text>
<rect x="8" y="150" width="122" height="44" rx="4" fill="none" stroke="currentColor" stroke-dasharray="2 2"/>
<text x="69" y="176" text-anchor="middle" font-size="13" fill="currentColor">landing/mobile</text>
<rect x="165" y="95" width="135" height="50" rx="6" fill="none" stroke="currentColor"/>
<text x="232" y="116" text-anchor="middle" font-size="13" fill="currentColor">bronze_orders</text>
<text x="232" y="134" text-anchor="middle" font-size="13" fill="currentColor">streaming table</text>
<rect x="325" y="95" width="130" height="50" rx="6" fill="none" stroke="currentColor"/>
<text x="390" y="116" text-anchor="middle" font-size="13" fill="currentColor">silver_orders</text>
<text x="390" y="134" text-anchor="middle" font-size="13" fill="currentColor">streaming table</text>
<rect x="478" y="10" width="155" height="50" rx="6" fill="none" stroke="currentColor" stroke-dasharray="6 4"/>
<text x="555" y="31" text-anchor="middle" font-size="13" fill="currentColor">valid_orders</text>
<text x="555" y="49" text-anchor="middle" font-size="13" fill="currentColor">temporary view</text>
<rect x="478" y="95" width="155" height="50" rx="6" fill="none" stroke="currentColor"/>
<text x="555" y="116" text-anchor="middle" font-size="13" fill="currentColor">gold_daily_sales</text>
<text x="555" y="134" text-anchor="middle" font-size="13" fill="currentColor">materialized view</text>
<rect x="478" y="180" width="155" height="50" rx="6" fill="none" stroke="currentColor"/>
<text x="555" y="201" text-anchor="middle" font-size="13" fill="currentColor">gold_customer_totals</text>
<text x="555" y="219" text-anchor="middle" font-size="13" fill="currentColor">materialized view</text>
<line x1="130" y1="62" x2="165" y2="108" stroke="currentColor" marker-end="url(#a131)"/>
<line x1="130" y1="172" x2="165" y2="132" stroke="currentColor" marker-end="url(#a131)"/>
<line x1="300" y1="120" x2="325" y2="120" stroke="currentColor" marker-end="url(#a131)"/>
<line x1="455" y1="110" x2="478" y2="40" stroke="currentColor" marker-end="url(#a131)"/>
<line x1="555" y1="60" x2="555" y2="95" stroke="currentColor" marker-end="url(#a131)"/>
<line x1="455" y1="132" x2="478" y2="200" stroke="currentColor" marker-end="url(#a131)"/>
<text x="232" y="258" text-anchor="middle" font-size="14" font-weight="bold" fill="currentColor">Bronze</text>
<text x="390" y="258" text-anchor="middle" font-size="14" font-weight="bold" fill="currentColor">Silver</text>
<text x="555" y="258" text-anchor="middle" font-size="14" font-weight="bold" fill="currentColor">Gold</text>
<text x="69" y="120" text-anchor="middle" font-size="13" fill="currentColor">two append</text>
<text x="69" y="137" text-anchor="middle" font-size="13" fill="currentColor">flows</text>
</svg>
<figcaption>Figure 13.2. The graph of the Red Rock Supply pipeline run in section 13.11. Nobody wrote the order down: it comes from the table names each query reads. Dashed: not stored.</figcaption>
</figure>

**Target catalog and schema.** The configuration sets a default catalog and schema; "This default catalog and schema are used for all dataset definitions and table reads, unless overridden within the query" (page "Set the target catalog and schema", last updated Sep 11, 2026). Fully qualified names such as `shop.gold.daily_sales` publish to other schemas, which is how one pipeline can fill `shop.bronze`, `shop.silver` and `shop.gold`. Pipelines created before February 5, 2025 may use the legacy `LIVE` virtual schema (`SELECT * FROM LIVE.orders`); "In new pipelines, the `LIVE` schema syntax is silently ignored."

**Settings.** The main ones, from "Configure pipelines" (last updated Oct 12, 2026) and the "Pipeline properties reference" (last updated Oct 19, 2026):

| Setting | Values and default | Notes |
| --- | --- | --- |
| Compute | serverless (default for new pipelines) or classic | Serverless needs Unity Catalog and the `ADVANCED` edition; incremental refresh of materialized views needs serverless (section 13.8). Classic is for the legacy Hive metastore, private networking serverless does not support, or regions without serverless. |
| `channel` | `current` (default) or `preview` | The runtime version. The release notes page (last updated Oct 16, 2026) lists CURRENT as Databricks Runtime 18 and PREVIEW as Databricks Runtime 19. Pipelines are "versionless": Databricks upgrades the runtime automatically. |
| `edition` | `CORE`, `PRO`, `ADVANCED` (default) | Core: streaming ingest. Pro: adds CDC. Advanced: adds expectations. |
| `continuous` | `false` (default) = triggered, `true` = continuous | See below. |
| `development` | `false` (default) | "A flag indicating whether to run the pipeline in `development` or `production` mode." See below. |
| Run as | a user, a service principal or an account group | Owns the published tables; Databricks calls a service principal "a best practice". |
| `configuration`, parameters | key-value pairs | Spark settings and values the code reads; parameters (Beta) are referenced from SQL as `:name`. |

**Triggered or continuous.** "If the pipeline uses triggered mode, the system stops after refreshing all tables based on the data available when the update started." Continuous mode "processes new data as it arrives" and needs an always-running cluster (page "Triggered vs. continuous pipeline mode", last updated Sep 14, 2026). The page's guide: triggered fits updates "every 10 minutes, hourly, or daily", continuous fits "between every 10 seconds and a few minutes". For continuous production pipelines, Databricks now "recommends running continuous pipelines with a continuous job rather than setting the value of **Pipeline mode** to continuous", and the job's mode overrides the pipeline's setting. Pipeline mode is independent of table type: streaming tables and materialized views both refresh in either mode.

**Development and production.** Older DLT material describes a development/production toggle; the properties reference still lists the `development` flag (default `false`). The current "Run a pipeline update" page (last updated Sep 11, 2026) describes the two behaviors by how an update starts, shown in figure 13.3. How the `development` flag interacts with these trigger-based behaviors today is not stated on the pages I checked: not verified.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 250" role="img" aria-label="Update run behavior: debugging-focused versus automatic retry">
<rect x="8" y="8" width="304" height="234" rx="8" fill="none" stroke="currentColor"/>
<rect x="328" y="8" width="304" height="234" rx="8" fill="none" stroke="currentColor"/>
<text x="160" y="32" text-anchor="middle" font-size="15" font-weight="bold" fill="currentColor">Fast-start, debugging-focused</text>
<text x="480" y="32" text-anchor="middle" font-size="15" font-weight="bold" fill="currentColor">Automatic retry and restart</text>
<text x="160" y="56" text-anchor="middle" font-size="13" fill="currentColor">(the classic "development mode")</text>
<text x="480" y="56" text-anchor="middle" font-size="13" fill="currentColor">(the classic "production mode")</text>
<text x="24" y="88" font-size="13" fill="currentColor">Used for: Run now in the editor or the</text>
<text x="24" y="106" font-size="13" fill="currentColor">monitoring UI, triggered pipelines</text>
<text x="24" y="138" font-size="13" fill="currentColor">- reuses the cluster (by default it</text>
<text x="24" y="156" font-size="13" fill="currentColor">  runs for two hours)</text>
<text x="24" y="180" font-size="13" fill="currentColor">- pipeline retries disabled, so errors</text>
<text x="24" y="198" font-size="13" fill="currentColor">  show up at once</text>
<text x="344" y="88" font-size="13" fill="currentColor">Used for: Jobs, the Pipelines API, and</text>
<text x="344" y="106" font-size="13" fill="currentColor">every continuous pipeline update</text>
<text x="344" y="138" font-size="13" fill="currentColor">- restarts the cluster on recoverable</text>
<text x="344" y="156" font-size="13" fill="currentColor">  errors (memory leaks, stale credentials)</text>
<text x="344" y="180" font-size="13" fill="currentColor">- retries specific errors</text>
<text x="344" y="204" font-size="13" fill="currentColor">- cluster shuts down right after the run</text>
</svg>
<figcaption>Figure 13.3. Two run behaviors from the "Run a pipeline update" page. A failure that clears itself on retry in a scheduled run will stop an interactive run immediately. The names in brackets are the ones older Delta Live Tables material used; the current page does not use them.</figcaption>
</figure>

!!! warning "Same code, different retry behavior"
    The how-to guide warns that "manually triggered updates disable automatic retries so you see errors immediately, while scheduled updates retry recoverable failures. A production alert might therefore clear itself on retry where the same failure won't during interactive development." Do not read a green scheduled run as proof that a flaky source is healthy.

!!! tip "In the interview"
    **"What is the difference between development and production mode in DLT?"** "In Delta Live Tables, now Lakeflow pipelines, interactive runs reuse the cluster and turn off retries so you see errors fast; production runs from a job or the API restart the cluster on recoverable errors, retry, and shut the cluster down when done. Today's docs describe it as update run behavior chosen by how the update starts; the pipeline JSON still has a `development` flag, default false."

## 13.5 Writing pipelines in SQL and Python

*Level: intermediate.*

Every example in this section needs a Databricks workspace. The syntax is copied from the current reference pages; section 13.11 runs the open-source equivalents.

### SQL

The statements are in the "Pipeline SQL language reference" (last updated Sep 11, 2026). The shapes you need:

*Databricks only, not run here. Syntax from [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table).*

```sql
CREATE [OR REFRESH] [PRIVATE] STREAMING TABLE
  table_name
  [ table_specification ]
  [ table_clauses ]
  [ {flow_clause | AS query} ]
```

*Databricks only, not run here. Syntax from [CREATE MATERIALIZED VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-materialized-view).*

```sql
CREATE [OR REFRESH] [PRIVATE] MATERIALIZED VIEW
  view_name
  [ column_list ]
  [ view_clauses ]
  AS query
```

Key points from those pages:

- `OR REFRESH` "creates the table, or updates an existing table and its content". It is the normal form in pipeline code.
- A streaming table's query "must be a **streaming** query. Use the STREAM keyword to use streaming semantics to read from the source." `STREAM(bronze)` and `STREAM bronze` both appear in the docs. A materialized view reads without `STREAM`.
- `read_files` is how SQL calls Auto Loader: "You must also use the `STREAM` keyword to configure a streaming read with `read_files`" (page "Develop Lakeflow pipelines code with SQL", last updated Oct 15, 2026).
- `PRIVATE` makes a dataset that is "not added to the catalog" and only visible inside the pipeline. Private tables and views "were previously created with the `TEMPORARY` parameter".
- In a materialized view, expressions that are not plain column references need an alias: `SUM(col2) AS sum_col2` is allowed, `SUM(col2)` is not.
- The old `CREATE OR REFRESH LIVE TABLE` form for materialized views "is deprecated. Instead, use `CREATE OR REFRESH MATERIALIZED VIEW`."

Flows defined on their own use `CREATE FLOW`, including the `INSERT ... BY NAME` form:

*Databricks only, not run here. Syntax from [CREATE FLOW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-flow).*

```sql
CREATE FLOW flow_name [COMMENT comment] AS
{
  AUTO CDC [ONCE] INTO target_table create_auto_cdc_flow_spec |
  AUTO CDC [ONCE] INTO target_table create_auto_cdc_from_snapshot_spec |
  INSERT [ONCE] INTO target_table BY NAME [ replace_using_spec | REPLACE WHERE condition ] query
}
```

The same flow can also sit inline in the table definition: `CREATE OR REFRESH STREAMING TABLE raw_data FLOW INSERT BY NAME SELECT * FROM STREAM read_files('abfss://my_path');` is, per the reference, identical to `AS SELECT ...`. Newer flow kinds such as `REPLACE WHERE` (rewrite only the rows matching a predicate) and `REPLACE USING` (Beta, Databricks Runtime 18.2 and above) exist too; they are beyond an interview's usual scope.

### Python

"The Lakeflow pipelines Python interface is defined in the `pyspark.pipelines` module, imported as `dp`" (page "Lakeflow pipelines Python language reference", last updated Oct 25, 2026). The decorators:

| Python | Makes | Function returns |
| --- | --- | --- |
| `@dp.table` | streaming table | a streaming DataFrame (`spark.readStream...`) |
| `@dp.materialized_view` | materialized view | a batch DataFrame (`spark.read...`) |
| `@dp.temporary_view` | temporary view | a batch or streaming DataFrame |
| `dp.create_streaming_table("name")` | an empty streaming table that flows write into | (not a decorator) |
| `@dp.append_flow(target="name")` | an append flow into a table or sink | a streaming DataFrame (a batch one with `once=True`) |
| `dp.create_sink(name, format, options)` | a sink | (not a decorator) |

The table name defaults to the function name; `name=` overrides it, and can be fully qualified: the docs show fully qualified names in `@dp.materialized_view(name=...)` ("Set the target catalog and schema"), `@dp.table(name=...)` ("Move tables between pipelines", last updated Nov 2, 2026) and `dp.create_streaming_table(...)` (the AUTO CDC page, last updated Nov 9, 2026). For `@dp.append_flow(target=...)` it follows from the pipeline's three-tier name resolution but no example shows it: not verified. The `@dp.table` page adds a trap: "The `@table` operator in the `pyspark.pipelines` module still works in this way", meaning a batch DataFrame under `@dp.table` still makes a materialized view, "but Databricks recommends using the `@materialized_view` operator to create materialized views."

The reference also lists coding rules that interviewers like to test. A pipeline "evaluates its source code multiple times during planning and runs", so a dataset function must only build and return a DataFrame. Never call `collect()`, `count()`, `toPandas()`, `save()`, `saveAsTable()`, `start()` or `toTable()` inside one. The limitations page adds that `pivot()` is not supported, because it "requires the eager loading of input data to compute the output schema".

The legacy form, which you will still meet in existing code:

*Databricks only, not run here. Legacy `dlt` form; names from [What happened to `@dlt`?](https://docs.databricks.com/aws/en/ldp/developer/python-ref#dlt-or-pipeline).*

```python
import dlt

@dlt.table                      # streaming DataFrame -> streaming table
def bronze_orders():
    return spark.readStream.format("cloudFiles").option("cloudFiles.format", "json").load("/Volumes/shop/bronze/landing/orders/")

@dlt.table                      # batch DataFrame -> materialized view (same decorator!)
def gold_daily_sales():
    return spark.read.table("silver_orders").groupBy("currency").count()

@dlt.view                       # now @dp.temporary_view
def valid_orders():
    return spark.read.table("silver_orders").where("status <> 'CANCELLED'")
```

### A full medallion pipeline on Databricks

Here is the Red Rock Supply pipeline as Databricks would run it: bronze with Auto Loader, silver as a streaming table, gold as a materialized view, each in its own schema of catalog `shop`.

*Databricks only, not run here. Syntax from [Load data in pipelines](https://docs.databricks.com/aws/en/ldp/load), [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table), [CREATE MATERIALIZED VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-materialized-view) and [Set the target catalog and schema](https://docs.databricks.com/aws/en/ldp/target-schema).*

```sql
-- transformations/orders.sql
CREATE OR REFRESH STREAMING TABLE shop.bronze.orders
  COMMENT 'Raw order events, one row per JSON record'
AS SELECT *
FROM STREAM read_files('/Volumes/shop/bronze/landing/orders/', format => 'json');

CREATE OR REFRESH STREAMING TABLE shop.silver.orders
AS SELECT
  order_id,
  customer_id,
  CAST(order_ts AS TIMESTAMP)   AS order_ts,
  upper(status)                 AS status,
  CAST(amount AS DECIMAL(10,2)) AS amount,
  currency
FROM STREAM(shop.bronze.orders)
WHERE order_id IS NOT NULL;

CREATE OR REFRESH MATERIALIZED VIEW shop.gold.daily_sales
AS SELECT
  CAST(order_ts AS DATE) AS order_date,
  currency,
  count(*)               AS orders,
  sum(amount)            AS revenue
FROM shop.silver.orders
WHERE status <> 'CANCELLED'
GROUP BY ALL;
```

The same pipeline in Python. Note `amount` is cast to `DECIMAL`, not `DOUBLE`: section 13.8 explains why that matters for incremental refresh.

*Databricks only, not run here. Syntax from [Load data in pipelines](https://docs.databricks.com/aws/en/ldp/load), [table](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-table) and [materialized_view](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-materialized-view).*

```python
from pyspark import pipelines as dp
from pyspark.sql import functions as F

@dp.table(name="shop.bronze.orders", comment="Raw order events, one row per JSON record")
def bronze_orders():
    return (spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "json")
            .load("/Volumes/shop/bronze/landing/orders/"))

@dp.table(name="shop.silver.orders")
def silver_orders():
    return (spark.readStream.table("shop.bronze.orders")
            .where("order_id IS NOT NULL")
            .select("order_id", "customer_id",
                    F.col("order_ts").cast("timestamp").alias("order_ts"),
                    F.upper("status").alias("status"),
                    F.col("amount").cast("decimal(10,2)").alias("amount"),
                    "currency"))

@dp.materialized_view(name="shop.gold.daily_sales")
def gold_daily_sales():
    return (spark.read.table("shop.silver.orders")
            .where("status <> 'CANCELLED'")
            .groupBy(F.col("order_ts").cast("date").alias("order_date"), "currency")
            .agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue")))
```

In a real pipeline you would add expectations on silver (drop rows without `order_id` instead of filtering them silently, so the drop count shows up in the event log) and use `AUTO CDC` for the customers dimension; both are in [chapter 14](14-Data-Quality-and-CDC.md). Deduplication of re-delivered orders in a streaming table needs a watermark ([chapter 11](11-Structured-Streaming.md)).

!!! tip "In the interview"
    **"Write a DLT pipeline from JSON files to a daily sales table."** Say the names first: "In Lakeflow pipelines, formerly Delta Live Tables, bronze is a streaming table over `STREAM read_files(...)`, which is Auto Loader; silver is a streaming table over `STREAM(bronze)` that casts and cleans; gold is a materialized view that aggregates silver. I don't schedule the steps; the pipeline infers bronze, silver, gold from the table names."

## 13.6 Flows in depth: many sources, one table

*Level: intermediate.*

The problem: orders arrive from the web shop and from the mobile app, in two folders. The obvious query is `SELECT ... FROM STREAM(web) UNION ALL SELECT ... FROM STREAM(mobile)`. Now a third channel opens. Changing the query of a streaming table changes its flow, and the full-refresh page lists "Modifying the source tables read by the streaming query" among the changes that require a full refresh.

Flows avoid this. You create the target once and add one append flow per source. The "Flows" page (last updated Sep 11, 2026) lists three uses for separate flows:

- "Add streaming sources that append to an existing streaming table without requiring a full refresh."
- "Backfill a streaming table with missing historical data."
- "Combine data from multiple sources without using a `UNION` clause."

Each flow has its own checkpoint, named after the flow. The "Use flows" page (last updated Oct 30, 2026) spells out what that means: "If an existing flow in a pipeline is renamed, the checkpoint does not carry over, and the renamed flow is effectively an entirely new flow", and "You cannot reuse a flow name in a pipeline".

*Databricks only, not run here. Syntax from [CREATE FLOW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-flow) and [Use flows in Lakeflow pipelines](https://docs.databricks.com/aws/en/ldp/flow-examples).*

```sql
CREATE OR REFRESH STREAMING TABLE shop.bronze.orders;

CREATE FLOW orders_web AS
INSERT INTO shop.bronze.orders BY NAME
SELECT * FROM STREAM read_files('/Volumes/shop/bronze/landing/web/', format => 'json');

CREATE FLOW orders_mobile AS
INSERT INTO shop.bronze.orders BY NAME
SELECT * FROM STREAM read_files('/Volumes/shop/bronze/landing/mobile/', format => 'json');

-- one-time backfill of last year's export, a batch read (no STREAM)
CREATE FLOW orders_backfill_2025 AS
INSERT ONCE INTO shop.bronze.orders BY NAME
SELECT * FROM read_files('/Volumes/shop/bronze/archive/2025/', format => 'json');
```

*Databricks only, not run here. Syntax from [append_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-append-flow) and [create_streaming_table](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-streaming-table).*

```python
from pyspark import pipelines as dp

dp.create_streaming_table("shop.bronze.orders")

@dp.append_flow(target="shop.bronze.orders")
def orders_web():
    return (spark.readStream.format("cloudFiles").option("cloudFiles.format", "json")
            .load("/Volumes/shop/bronze/landing/web/"))

@dp.append_flow(target="shop.bronze.orders")
def orders_mobile():
    return (spark.readStream.format("cloudFiles").option("cloudFiles.format", "json")
            .load("/Volumes/shop/bronze/landing/mobile/"))

@dp.append_flow(target="shop.bronze.orders", once=True)
def orders_backfill_2025():
    return spark.read.format("json").load("/Volumes/shop/bronze/archive/2025/")
```

`ONCE` (`once=True`) marks "a batch query whose data should be inserted into the target only once, unless the target is fully refreshed": after a full refresh it runs again to recreate the data. Expectations cannot sit on an `@append_flow`; "define the expectations on the target table as part of the `create_streaming_table()` function".

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 250" role="img" aria-label="Three flows writing into one streaming table, each with its own checkpoint">
<defs><marker id="a133" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="currentColor"/></marker></defs>
<rect x="8" y="20" width="150" height="44" rx="4" fill="none" stroke="currentColor" stroke-dasharray="2 2"/>
<text x="83" y="47" text-anchor="middle" font-size="13" fill="currentColor">landing/web</text>
<rect x="8" y="100" width="150" height="44" rx="4" fill="none" stroke="currentColor" stroke-dasharray="2 2"/>
<text x="83" y="127" text-anchor="middle" font-size="13" fill="currentColor">landing/mobile</text>
<rect x="8" y="180" width="150" height="44" rx="4" fill="none" stroke="currentColor" stroke-dasharray="2 2"/>
<text x="83" y="207" text-anchor="middle" font-size="13" fill="currentColor">archive/2025 (batch)</text>
<rect x="200" y="20" width="200" height="44" rx="6" fill="none" stroke="currentColor"/>
<text x="300" y="38" text-anchor="middle" font-size="13" fill="currentColor">flow orders_web</text>
<text x="300" y="55" text-anchor="middle" font-size="13" fill="currentColor">append, own checkpoint</text>
<rect x="200" y="100" width="200" height="44" rx="6" fill="none" stroke="currentColor"/>
<text x="300" y="118" text-anchor="middle" font-size="13" fill="currentColor">flow orders_mobile</text>
<text x="300" y="135" text-anchor="middle" font-size="13" fill="currentColor">append, own checkpoint</text>
<rect x="200" y="180" width="200" height="44" rx="6" fill="none" stroke="currentColor" stroke-dasharray="6 4"/>
<text x="300" y="198" text-anchor="middle" font-size="13" fill="currentColor">flow orders_backfill_2025</text>
<text x="300" y="215" text-anchor="middle" font-size="13" fill="currentColor">append ONCE</text>
<rect x="450" y="95" width="180" height="54" rx="6" fill="none" stroke="currentColor"/>
<text x="540" y="118" text-anchor="middle" font-size="13" fill="currentColor">shop.bronze.orders</text>
<text x="540" y="137" text-anchor="middle" font-size="13" fill="currentColor">streaming table</text>
<line x1="158" y1="42" x2="200" y2="42" stroke="currentColor" marker-end="url(#a133)"/>
<line x1="158" y1="122" x2="200" y2="122" stroke="currentColor" marker-end="url(#a133)"/>
<line x1="158" y1="202" x2="200" y2="202" stroke="currentColor" marker-end="url(#a133)"/>
<line x1="400" y1="42" x2="450" y2="108" stroke="currentColor" marker-end="url(#a133)"/>
<line x1="400" y1="122" x2="450" y2="122" stroke="currentColor" marker-end="url(#a133)"/>
<line x1="400" y1="202" x2="450" y2="136" stroke="currentColor" marker-end="url(#a133)"/>
</svg>
<figcaption>Figure 13.4. Several flows, one target. Adding a fourth source is a new flow, not a change to an existing query, so no full refresh is needed. A ONCE flow runs one time and again only after a full refresh.</figcaption>
</figure>

!!! tip "In the interview"
    **"How do you add a new Kafka topic to an existing DLT streaming table without reprocessing?"** "In Lakeflow pipelines, formerly Delta Live Tables, I add a new append flow (`@dp.append_flow` or `CREATE FLOW ... INSERT INTO ... BY NAME`) that targets the existing table. It gets its own checkpoint, so the existing flows and data are untouched. Editing a UNION in the existing query would change the flow's sources, which needs a full refresh."

## 13.7 Updates: refresh, full refresh and checkpoint reset

*Level: intermediate.*

An *update* is one run of the pipeline. The "Run a pipeline update" page lists what it does: it "starts a cluster with the correct configuration", "discovers all the defined tables and views and checks for any analysis errors such as invalid column names, missing dependencies, and syntax errors", and "creates or updates tables and views with the most recent data available". The event log schema records these phases as update states, among them `WAITING_FOR_RESOURCES`, `INITIALIZING`, `SETTING_UP_TABLES`, `RUNNING` and `COMPLETED`; flows run only after the setup. A *dry run* (Public Preview) stops after validation: it "resolves the definitions of datasets and flows defined in the pipeline but does not materialize or publish any datasets".

Updates start manually (editor, pipelines list), on a schedule ("You can schedule updates for pipelines using jobs"), or through the REST API and CLI. The three kinds of refresh, from the page "How do pipelines refresh?" (last updated Sep 11, 2026):

| Update type | Materialized view | Streaming table |
| --- | --- | --- |
| Refresh (default) | "Updates results to reflect the current results of the defining query." Incremental when cheaper. | "Processes new records through the logic defined in streaming tables and flows." |
| Full refresh | "Recomputes results to reflect the current results of the defining query." | "Clears data from streaming tables, clears checkpoints from flows, and reprocesses all records from the data source." |
| Reset streaming flow checkpoints | "Not applicable to materialized views." | "Clears checkpoints from flows but does not clear data from streaming tables, then reprocesses all records from the data source." |

A default refresh of a streaming table "trades data correctness for lower time and resource costs": rows already written keep whatever logic was in force when they were written. The streaming tables page gives the example: change `SELECT LOWER (name)` to `SELECT UPPER (name)` and "existing rows will not update to be uppercase, but new rows will be uppercase". Section 13.11 reproduces exactly this.

### The full refresh warning

The "Run a pipeline update" page warns:

> Using a full refresh with streaming tables resets all state processing and checkpoint information and can result in dropped records if input data is no longer available.

And the page "Full refresh for streaming tables" (last updated Sep 11, 2026) opens with: "A full refresh of a streaming table discards all existing data and metadata and restarts the stream from the beginning. Specifically, it truncates the streaming table, removes all checkpoint data, and restarts the streaming process with new checkpoints for every flow writing to the table."

The danger is the source, not the table. If the Kafka topic keeps 24 hours, or a lifecycle rule deletes landing files after 30 days, a full refresh rebuilds the table from what is left and the rest is gone. The updates page lists the outcomes: Kafka with short retention, "Records no longer present in the Kafka source are dropped from the target table"; files under a lifecycle policy, "Data files no longer present in the source directory are dropped from the target table".

What forces a full refresh (from the full-refresh page): incompatible schema changes (renaming columns without column mapping, narrowing or incompatible type changes, dropping columns), moving from partitioning to clustering, changing the source tables, source type or location, changing aggregation or join keys or adding and removing aggregations, joins or deduplication, and a lost or corrupt checkpoint. Also: "If the streaming table has dependent downstream tables, the pipeline fails until those tables are also fully refreshed, unless the streaming table has skipChangeCommits enabled."

How to protect history:

- Keep **bronze raw and stable**: the page recommends streaming raw data into a bronze streaming table with "flexible column types (variant or string, for example)", so bronze itself never needs a full refresh and downstream tables can be rebuilt from it.
- **Block it**: "To prevent full refreshes from being run on a table or view, set the table property `pipelines.reset.allowed` to `false`."
- **Use a flow or a checkpoint reset instead**: a new flow for a new source, or a reset of selected flows' checkpoints (through the REST API's `reset_checkpoint_selection`, with fully qualified flow names), keeps the table's data, though both "may lead to duplicate data".
- If a full refresh is unavoidable, check the source still holds the history, and use a `ONCE` flow to backfill from an archive.

*Databricks only, not run here. Syntax from [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table) and [Pipeline properties reference](https://docs.databricks.com/aws/en/ldp/properties) (`pipelines.reset.allowed`, default `true`).*

```sql
CREATE OR REFRESH STREAMING TABLE shop.bronze.orders
  TBLPROPERTIES ('pipelines.reset.allowed' = 'false')
AS SELECT * FROM STREAM read_files('/Volumes/shop/bronze/landing/orders/', format => 'json');
```

### Selective refresh

By default every table refreshes on every update. You can also run "a single source file, or a single table" from the editor, pick tables with **Select tables for refresh**, or use **Refresh failed tables**, which refreshes the failed tables and their downstream dependencies. Each supports a normal or a full refresh. Pipelines retain 60 days of past updates in the UI.

!!! warning "A full refresh that wipes history"
    A full refresh of a streaming table is not a "rerun". It truncates the table and replays the source. Anything the source no longer holds is gone from the table, and from every table rebuilt from it. Set `pipelines.reset.allowed = false` on bronze tables fed by short-retention sources.

!!! tip "In the interview"
    **"Someone ran a full refresh on a DLT streaming table and months of data disappeared. Why, and how do you prevent it?"** "In Lakeflow pipelines, formerly Delta Live Tables, a full refresh truncates the streaming table, clears every flow's checkpoint and replays the source. Our source, Kafka with 7 days retention (or a landing folder with a lifecycle rule), only had the last week, so that is all that came back. To prevent it: keep a raw bronze streaming table with flexible types so it never needs a full refresh, set `pipelines.reset.allowed` to false on it, and use a new flow or a checkpoint reset instead of a full refresh when logic changes."

## 13.8 Incremental refresh of materialized views

*Level: intermediate.*

A materialized view promises the same result as running its query from scratch. Recomputing a year of orders every hour to add one hour of data is wasteful, so Databricks tries to update only what changed. The page "Incremental refresh for materialized views" (last updated Oct 28, 2026) states the conditions:

- **Serverless only.** "Incremental refresh is only available when the compute you are connected to is serverless." "Materialized views that do not use serverless pipelines are always fully recomputed." Standalone materialized views always refresh on a serverless pipeline; pipeline materialized views need the pipeline set to serverless.
- **Cost-based.** "Databricks runs a cost analysis to choose the cheaper option between an incremental refresh and a full recompute." The output is the same either way.
- **Supported sources.** Delta tables, materialized views, streaming tables (including `AUTO CDC` targets) and Unity Catalog managed Iceberg tables. Some operations need **row tracking** on the sources; Databricks also recommends deletion vectors: `ALTER TABLE <table-name> SET TBLPROPERTIES (delta.enableRowTracking = true, delta.enableDeletionVectors = true);`
- **Supported query shapes.** The page's table marks as supported, among others: `SELECT` expressions with deterministic functions, `GROUP BY`, CTEs, `UNION ALL`, `WHERE`/`HAVING`, inner, left, right and full outer joins, window functions with `PARTITION BY`, and `QUALIFY`. Not incremental: recursive CTEs; non-deterministic functions other than time functions such as `current_date()` in `WHERE`; and floating point sums: "Aggregations that sum floating-point values, such as `SUM`, `AVG`, and covariance, can produce non-deterministic results over `FLOAT` or `DOUBLE` columns and force a full refresh. Cast these columns to `DECIMAL`".

You can see what happened: the **Incrementalization** column in the pipeline UI shows *Incremental*, *Full recompute* or *No change*, and the event log records the technique (`ROW_BASED`, `PARTITION_OVERWRITE`, `GROUP_AGGREGATE`, `FULL_RECOMPUTE`, `NO_OP` and others) under `event_type = 'planning_information'`. Before creating a view, `EXPLAIN CREATE MATERIALIZED VIEW` tells you whether the query can be incrementalized.

You can also pin the behavior with a **refresh policy** (Beta in the reference): `AUTO` (default), `INCREMENTAL` (prefer incremental, fall back to full), `INCREMENTAL STRICT` (fail instead of a full recompute) or `FULL`.

*Databricks only, not run here. Syntax from [Incremental refresh for materialized views](https://docs.databricks.com/aws/en/ldp/incremental-refresh).*

```sql
CREATE OR REFRESH MATERIALIZED VIEW shop.gold.daily_sales
  REFRESH POLICY INCREMENTAL STRICT
AS SELECT CAST(order_ts AS DATE) AS order_date, currency, sum(amount) AS revenue
FROM shop.silver.orders
GROUP BY ALL;

-- which technique did the last refreshes use?
SELECT timestamp, message
FROM event_log(TABLE(shop.gold.daily_sales))
WHERE event_type = 'planning_information'
ORDER BY timestamp DESC;
```

Interviewers sometimes call this engine "Enzyme". The current incremental refresh pages do not use that name; the only place I found it is a configuration key, `pipelines.enzyme.enabled`, mentioned on the "Configure pipelines" page. Treat "Enzyme" as an informal name: not verified as a product term.

!!! tip "In the interview"
    **"Is a DLT materialized view recomputed from scratch every time?"** "Not necessarily. In Lakeflow pipelines, formerly Delta Live Tables, on serverless compute Databricks refreshes a materialized view incrementally when the query and sources allow it and a cost model says it is cheaper; otherwise it recomputes in full, with the same result. On classic compute it is always a full recompute. Row tracking on the sources, deterministic expressions and DECIMAL instead of DOUBLE in sums keep it incremental, and `REFRESH POLICY INCREMENTAL STRICT` makes a non-incremental refresh fail instead of silently costing more."

## 13.9 Standalone streaming tables and materialized views in Databricks SQL

*Level: expert.*

Not every materialized view needs a pipeline. "You can also define standalone materialized views and streaming tables outside of a Lakeflow pipeline using simple query syntax, and Databricks manages the underlying pipelines for you" (page "Standalone materialized views and streaming tables", last updated Oct 15, 2026). You create them from a SQL warehouse, or from a notebook on serverless general compute. This section was previously called "Pipelines for Databricks SQL".

*Databricks only, not run here. Syntax from [Use standalone streaming tables](https://docs.databricks.com/aws/en/sql/mv-st/streaming), [Use standalone materialized views](https://docs.databricks.com/aws/en/views/materialized) and [REFRESH (MATERIALIZED VIEW or STREAMING TABLE)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-refresh-full).*

```sql
-- refresh every hour from new files in a volume (Auto Loader through read_files)
CREATE OR REFRESH STREAMING TABLE shop.bronze.orders_sql
  SCHEDULE EVERY 1 hour
AS SELECT * FROM STREAM read_files('/Volumes/shop/bronze/landing/orders/', format => 'json');

-- refresh whenever the source table changes
CREATE OR REPLACE MATERIALIZED VIEW shop.gold.daily_sales_sql
  TRIGGER ON UPDATE
AS SELECT CAST(order_ts AS DATE) AS order_date, currency, sum(amount) AS revenue
FROM shop.silver.orders
GROUP BY ALL;

REFRESH MATERIALIZED VIEW shop.gold.daily_sales_sql;          -- synchronous by default
REFRESH MATERIALIZED VIEW shop.gold.daily_sales_sql ASYNC;    -- return at once
REFRESH STREAMING TABLE shop.bronze.orders_sql FULL;          -- truncate and replay
```

What surprises people:

- The work does not run on the warehouse. "When you run `CREATE MATERIALIZED VIEW` or `REFRESH MATERIALIZED VIEW`, Databricks automatically creates and runs a serverless pipeline", billed as serverless Lakeflow pipelines DBUs; "The cluster size of your warehouse does not limit the compute or cost used by the refresh." The pipeline shows in **Jobs & Pipelines** with type `MV/ST`; pipeline datasets show type `ETL`.
- Standalone tables "run only in triggered mode": on a `SCHEDULE`, `TRIGGER ON UPDATE`, a manual `REFRESH`, or a SQL task in a job.
- The REFRESH page repeats the warning: full refresh is "not recommended" on sources "such as Kafka" with short retention, "as the full refresh truncates the existing data".
- Use a full pipeline instead when you author tables and flows in Python (a single standalone dataset can also be defined with the `@materialized_view` or `@table` decorator in a notebook on serverless general compute), or need sinks, several stages with private intermediate datasets, `create_auto_cdc_from_snapshot_flow()`, or continuous execution (page "Standalone pipelines vs. Lakeflow pipelines", last updated Oct 15, 2026). A standalone table cannot be moved into a pipeline: "recreate the table in the target pipeline".

For batch ETL that overwrites a time window, Databricks now points to a `REPLACE WHERE` flow on a streaming table rather than a materialized view, and keeps materialized views for "a query-acceleration layer that serves precomputed results to dashboards and reports" (page "When to use REPLACE WHERE vs. materialized views", last updated Oct 15, 2026).

## 13.10 Monitoring and limitations

*Level: expert.*

**Monitoring.** The page "Monitor pipelines" (last updated Sep 21, 2026) describes three layers: the **Jobs & Pipelines list** (last five runs per pipeline), the **pipeline monitoring UI** (graph colored by status, row counts, data quality metrics, streaming backlog), and the **event log**, "the ground truth underneath both". The event log "contains all information related to a pipeline, including audit logs, data quality checks, pipeline progress, and data lineage" (page "Pipeline event log", last updated Nov 3, 2026). By default it is a hidden Delta table queried through a table-valued function. Databricks now recommends the `pipeline_events` system table (Beta) for events across all pipelines in a region.

*Databricks only, not run here. Syntax from [Pipeline event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs).*

```sql
SELECT timestamp, event_type, message
FROM event_log('<pipeline-id>')
ORDER BY timestamp DESC;
```

Two warnings from that page: "Do not delete the event log or the parent catalog or schema where the event log is published", and "Events are delivered to the event log on a best-effort basis, so delivery of every event isn't guaranteed." `flow_progress` events carry each flow's metrics, including the expectation results covered in chapter 14.

**Limitations worth remembering** (pages "Pipeline limitations", last updated Oct 22, 2026, and the CREATE STREAMING TABLE reference):

| Limitation | Detail |
| --- | --- |
| One owner per dataset | Datasets "can be defined only once", so they are "the target of only a single operation across all pipelines", except streaming tables written by several append flows. |
| Size | 1,000 concurrent pipeline updates per workspace; 1,000 datasets per pipeline (an update "might run out of memory or other resources before reaching that limit"). |
| Time travel | "supported only with streaming tables, and are _not_ supported with materialized views". |
| `pivot()` | Not supported. |
| Identity columns | Not supported on `AUTO CDC` targets; "might be recomputed during updates to a materialized views", so use them only on streaming tables. |
| Commands on streaming tables | `ALTER TABLE` is not allowed (use `CREATE OR REFRESH` or `ALTER STREAMING TABLE`); `CLONE`, `COPY INTO`, `ANALYZE TABLE`, `RESTORE`, `TRUNCATE`, `GENERATE MANIFEST`, `[CREATE OR] REPLACE TABLE` are not supported; schema evolution through `INSERT INTO` or `MERGE` is not supported. |
| External readers | "By default, materialized views and streaming tables can be accessed only by Databricks clients and applications." |
| Materialized view `sum` | When only `NULL`s remain in a column, a `sum` over it returns zero instead of `NULL`. |

All pipeline tables are Delta tables, with ACID transactions, time travel (streaming tables only) and schema enforcement, and pipelines run `OPTIMIZE` and `VACUUM` through predictive optimization.

## 13.11 Run here: open-source Spark Declarative Pipelines

*Level: expert.*

Apache Spark 4.2 ships the declarative engine: the Python module `pyspark.pipelines` and the `spark-pipelines` command. The Databricks page "Apache Spark Declarative Pipelines" (last updated Oct 9, 2026) compares the two:

| Capability | Open-source SDP | Lakeflow pipelines |
| --- | --- | --- |
| Pipelines in SQL and Python; streaming tables; materialized views; temporary views; append flows | yes | yes |
| Sinks (Delta, Apache Kafka, Azure Event Hubs) | yes | yes |
| Automatic orchestration and dependency resolution | yes | yes |
| AUTO CDC (SCD Type 1 and 2) and AUTO CDC from snapshot | no | yes |
| Data quality expectations | no | yes |
| Queryable event log | no | yes |
| Update flows and `foreachBatch` sinks | no | yes |
| Continuous mode | no | yes |

The Python reference adds that "Code written with the open-source `pipelines` module runs without modification on Databricks", and that `dp.create_auto_cdc_flow`, `dp.create_auto_cdc_from_snapshot_flow` and `@dp.expect(...)` "are not part of Apache Spark". Missing in open source as well: Auto Loader, `read_files`, serverless compute, incremental refresh of materialized views, Unity Catalog, the editor and the monitoring UI.

!!! warning "Open source is catching up on AUTO CDC"
    Open-source Spark added it in **4.2.0**: the [Spark 4.2.0 release notes](https://spark.apache.org/releases/spark-release-4-2-0.html) list "Auto CDC in Spark Declarative Pipelines for declarative SCD Type 1 upserts" (SPARK-56249). The Apache Spark **4.3.0** programming guide (the "latest" docs on spark.apache.org) is the first guide with a section, "Change Data Capture (CDC) with Auto CDC", documenting `create_auto_cdc_flow` and `CREATE FLOW ... AS AUTO CDC INTO` for SCD Type 1 and saying "SCD Type 2 is also supported" with its documentation still to come. The 4.2.0 guide has no such section, and the Databricks pages above still say AUTO CDC is Databricks only. In an interview, "AUTO CDC and expectations are what Databricks adds on top of open-source SDP" is the answer the Databricks docs support; you can add that open-source Spark 4.2 introduced an Auto CDC flow for SCD Type 1. I tried it on 4.2 (`src/ch13/ch13_autocdc_probe.py`): the module has `create_auto_cdc_flow` and the engine accepted the definition and ran the source flow, but with both a default (Parquet) target and a Delta Lake 4.4.1 target the Auto CDC flow failed before it could start, with `` [AUTOCDC_TARGET_DOES_NOT_SUPPORT_MERGE] Cannot start AutoCDC flow: the target table `spark_catalog`.`default`.`customers` (format: delta) does not support row-level operations. AutoCDC requires a target backed by a connector that supports MERGE. `` The 4.3 guide explains why: the target's connector must implement the DSv2 `SupportsRowLevelOperations` interface, and "Supporting the `MERGE INTO` SQL statement is not on its own sufficient". So on this machine, AUTO CDC does not run.

### Creating the project

`spark-pipelines init` makes a project folder with a spec file and two example files:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
$ spark-pipelines init --name redrock_pipeline
Pipeline project 'redrock_pipeline' created successfully. To run your pipeline:
cd 'redrock_pipeline'
spark-pipelines run

redrock_pipeline/pipeline-storage
redrock_pipeline/spark-pipeline.yml
redrock_pipeline/transformations/example_python_materialized_view.py
redrock_pipeline/transformations/example_sql_materialized_view.sql
```

The spec file names the pipeline, the source globs and a `storage` folder for checkpoints. The Spark 4.2 guide lists its fields: `name`, `libraries` and `storage` are required; `database` (alias `schema`), `catalog` and `configuration` are optional. On Databricks, the same information lives in the pipeline settings, and the properties reference maps one to the other (`schema` there is `database` here, and `storage` is legacy on Databricks).

I replaced the examples with four files that build the graph in figure 13.2. They are in `src/ch13/redrock_pipeline/transformations/`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
# transformations/bronze.py
from pyspark import pipelines as dp
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

LANDING = spark.conf.get("redrock.landing")  # set in spark-pipeline.yml -> configuration

ORDER_SCHEMA = """
    order_id INT, customer_id INT, order_ts STRING, status STRING,
    amount STRING, currency STRING,
    items ARRAY<STRUCT<product_id: INT, qty: INT, unit_price: STRING>>
"""

dp.create_streaming_table("bronze_orders", comment="Raw Red Rock Supply orders, as received")


def read_orders(channel: str) -> DataFrame:
    return (
        spark.readStream.schema(ORDER_SCHEMA)
        .json(f"{LANDING}/{channel}")
        .withColumn("channel", F.lit(channel))
        .withColumn("source_file", F.element_at(F.split(F.col("_metadata.file_path"), "/"), -1))
    )


@dp.append_flow(target="bronze_orders")
def orders_web() -> DataFrame:
    return read_orders("web")


@dp.append_flow(target="bronze_orders")
def orders_mobile() -> DataFrame:
    return read_orders("mobile")
```

There is no Auto Loader in open source, so each flow uses the plain Structured Streaming file source with an explicit schema. `spark` is not imported: "Starting in Spark 4.2, the framework injects spark into each pipeline file's module namespace."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- transformations/silver.sql
CREATE STREAMING TABLE silver_orders AS
SELECT
  order_id,
  customer_id,
  CAST(order_ts AS TIMESTAMP)    AS order_ts,
  upper(status)                  AS status,
  CAST(amount AS DECIMAL(10,2))  AS amount,
  currency,
  channel
FROM STREAM(bronze_orders)
WHERE order_id IS NOT NULL;

-- transformations/gold.sql
CREATE TEMPORARY VIEW valid_orders AS
SELECT * FROM silver_orders
WHERE upper(status) <> 'CANCELLED';

CREATE MATERIALIZED VIEW gold_daily_sales AS
SELECT
  CAST(order_ts AS DATE) AS order_date,
  currency,
  count(*)               AS orders,
  sum(amount)            AS revenue
FROM valid_orders
GROUP BY ALL;
```

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
# transformations/gold_customers.py
from pyspark import pipelines as dp
from pyspark.sql import DataFrame
from pyspark.sql import functions as F


@dp.materialized_view(comment="Orders and spend per customer")
def gold_customer_totals() -> DataFrame:
    return (
        spark.table("silver_orders")
        .groupBy("customer_id")
        .agg(F.count("*").alias("orders"), F.sum("amount").alias("total_amount"))
    )
```

Open-source SQL uses `CREATE STREAMING TABLE` and `CREATE MATERIALIZED VIEW` without `OR REFRESH`, as in the Spark guide.

### Making it work locally

Two things had to be solved before a second run would work, and both are worth knowing because they show what Databricks does for you. The error lines below were copied from the terminal while setting up (`src/ch13/setup_errors.txt`):

1. **The catalog must persist between runs.** With Spark's default in-memory catalog, the first run succeeded and the second failed with `[LOCATION_ALREADY_EXISTS] Cannot name the managed table as spark_catalog.default.example_python_materialized_view, as its associated location ... already exists.` The table files survived but the catalog entry did not. A Derby-backed Hive metastore fixed it. On Databricks, Unity Catalog plays this role.
2. **Delta needs static settings at session start.** `spark-pipelines` runs the pipeline through a local Spark Connect session. Putting `spark.sql.extensions` in the spec's `configuration` failed with `[CANNOT_MODIFY_STATIC_CONFIG]`, because that map is also applied as SQL configuration on every flow; passing `--jars` on the command line gave `[DATA_SOURCE_NOT_FOUND] Failed to find the data source: delta`. A `spark-defaults.conf` in `SPARK_CONF_DIR` worked. Declaring `format="delta"` on a single dataset worked on the first run and failed on the second with `[DELTA_CANNOT_CHANGE_PROVIDER] 'provider' is a reserved table property, and cannot be altered.`; setting `spark.sql.sources.default` to `delta` instead worked on every run.

The settings and the spec used (`<scratch>` stands for the local working folder, here and in the logs below):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
conf/spark-defaults.conf:
spark.jars <scratch>/jars/delta-spark_2.13-4.4.1.jar,<scratch>/jars/delta-storage-4.4.1.jar
spark.sql.extensions io.delta.sql.DeltaSparkSessionExtension
spark.sql.catalog.spark_catalog org.apache.spark.sql.delta.catalog.DeltaCatalog
spark.sql.catalogImplementation hive
spark.hadoop.javax.jdo.option.ConnectionURL jdbc:derby:;databaseName=<scratch>/work/ch13_sdp/metastore_db;create=true
spark.sql.warehouse.dir <scratch>/work/ch13_sdp/warehouse
spark.sql.sources.default delta
spark.sql.shuffle.partitions 2
spark.sql.session.timeZone UTC
spark.ui.enabled false
spark-pipeline.yml:
name: redrock_pipeline
storage: file://<scratch>/work/ch13_sdp/redrock_pipeline/pipeline-storage
libraries:
  - glob:
      include: transformations/**
configuration:
  redrock.landing: file://<scratch>/work/ch13_sdp/landing
```

The driver script `src/ch13/ch13_sdp_demo.py` writes these two files, lands JSON files, calls `spark-pipelines` and reads the resulting Delta tables back with a separate Spark session. Every output below is from `src/ch13/ch13_sdp_demo.out`.

### Run 1: the first update

Lines starting with `$` are the commands; the indented lines are the progress messages `spark-pipelines` printed (the script cuts the `spark_catalog.default.` prefix, tags every bracketed error class as `ERROR` and cuts that message at 400 characters). The first tagged line in every run is not a failure: it is a client warning (`UserWarning: Failed to set spark.sql.catalogImplementation ...`) printed when the client copies settings onto its Spark Connect session. The value is already in force from `spark-defaults.conf`, and the run goes on. Flows that do not depend on each other run in parallel, so the order of their QUEUED, RUNNING and COMPLETED lines changes from run to run (a full rerun of the script printed them in a different order, with the same results).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
##### STEP 1: first run
landed web/orders_001.json (3 orders)
landed mobile/orders_001.json (2 orders)
$ spark-pipelines run
   ERROR: [CANNOT_MODIFY_STATIC_CONFIG] Cannot modify the value of the static Spark config: "spark.sql.catalogImplementation". SQLSTATE: 46110
   Found 4 files matching glob 'transformations/**/*'
   Flow gold_customer_totals is QUEUED.
   Flow orders_mobile is QUEUED.
   Flow silver_orders is QUEUED.
   Flow gold_daily_sales is QUEUED.
   Flow orders_web is QUEUED.
   Flow orders_mobile is STARTING.
   Flow orders_mobile is RUNNING.
   Flow orders_web is STARTING.
   Flow orders_web is RUNNING.
   Flow orders_web has COMPLETED.
   Flow orders_mobile has COMPLETED.
   Flow silver_orders is STARTING.
   Flow silver_orders is RUNNING.
   Flow silver_orders has COMPLETED.
   Flow gold_daily_sales is PLANNING.
   Flow gold_daily_sales is STARTING.
   Flow gold_daily_sales is RUNNING.
   Flow gold_customer_totals is PLANNING.
   Flow gold_customer_totals is STARTING.
   Flow gold_customer_totals is RUNNING.
   Flow gold_daily_sales has COMPLETED.
   Flow gold_customer_totals has COMPLETED.
   Run is COMPLETED.
   (exit code 0)
========== tables after step 1
--- bronze_orders (streaming table, 2 append flows)
+--------+-------+------+-------+---------------+
|order_id|status |amount|channel|source_file    |
+--------+-------+------+-------+---------------+
|1001    |PLACED |59.90 |web    |orders_001.json|
|1002    |placed |120.00|web    |orders_001.json|
|1003    |SHIPPED|35.50 |web    |orders_001.json|
|2001    |PLACED |15.25 |mobile |orders_001.json|
|2002    |PLACED |89.99 |mobile |orders_001.json|
+--------+-------+------+-------+---------------+
--- silver_orders (streaming table)
+--------+-----------+-------------------+-------+------+--------+-------+
|order_id|customer_id|order_ts           |status |amount|currency|channel|
+--------+-----------+-------------------+-------+------+--------+-------+
|1001    |7          |2026-03-01 10:15:00|PLACED |59.90 |CAD     |web    |
|1002    |3          |2026-03-01 11:02:00|PLACED |120.00|CAD     |web    |
|1003    |9          |2026-03-01 16:40:00|SHIPPED|35.50 |USD     |web    |
|2001    |7          |2026-03-01 18:05:00|PLACED |15.25 |CAD     |mobile |
|2002    |12         |2026-03-02 09:30:00|PLACED |89.99 |CAD     |mobile |
+--------+-----------+-------------------+-------+------+--------+-------+
--- gold_daily_sales (materialized view, SQL)
+----------+--------+------+-------+
|order_date|currency|orders|revenue|
+----------+--------+------+-------+
|2026-03-01|CAD     |3     |195.15 |
|2026-03-01|USD     |1     |35.50  |
|2026-03-02|CAD     |1     |89.99  |
+----------+--------+------+-------+
--- gold_customer_totals (materialized view, Python)
+-----------+------+------------+
|customer_id|orders|total_amount|
+-----------+------+------------+
|3          |1     |120.00      |
|7          |2     |75.15       |
|9          |1     |35.50       |
|12         |1     |89.99       |
+-----------+------+------------+
```

Nobody wrote the order down. Both bronze flows ran first, then silver, then the two gold materialized views, exactly the graph in figure 13.2. `placed` in bronze became `PLACED` in silver, and the 2026-03-01 CAD revenue is 59.90 + 120.00 + 15.25 = 195.15.

### Run 2: a new file arrives

A second web file arrives and the pipeline runs again with no options:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
##### STEP 2: a new web file arrives, plain run
landed web/orders_002.json (2 orders)
$ spark-pipelines run
   ... (progress lines as in run 1) ...
   Run is COMPLETED.
   (exit code 0)
--- bronze_orders
+--------+---------+-------+---------------+
|order_id|status   |channel|source_file    |
+--------+---------+-------+---------------+
|1001    |PLACED   |web    |orders_001.json|
|1002    |placed   |web    |orders_001.json|
|1003    |SHIPPED  |web    |orders_001.json|
|1004    |PLACED   |web    |orders_002.json|
|1005    |CANCELLED|web    |orders_002.json|
|2001    |PLACED   |mobile |orders_001.json|
|2002    |PLACED   |mobile |orders_001.json|
+--------+---------+-------+---------------+
--- gold_daily_sales
+----------+--------+------+-------+
|order_date|currency|orders|revenue|
+----------+--------+------+-------+
|2026-03-01|CAD     |3     |195.15 |
|2026-03-01|USD     |1     |35.50  |
|2026-03-02|CAD     |2     |131.99 |
+----------+--------+------+-------+
--- Delta history of bronze_orders (operation per version)
+-------+-----------------+
|version|operation        |
+-------+-----------------+
|0      |CREATE TABLE     |
|1      |STREAMING UPDATE |
|2      |STREAMING UPDATE |
|3      |SET TBLPROPERTIES|
|4      |STREAMING UPDATE |
+-------+-----------------+
--- Delta history of gold_daily_sales (operation per version)
+-------+------------+
|version|operation   |
+-------+------------+
|0      |CREATE TABLE|
|1      |WRITE       |
|2      |TRUNCATE    |
|3      |WRITE       |
+-------+------------+
```

The Delta history shows the difference between the two kinds of table. Run 1 wrote bronze twice (versions 1 and 2, one `STREAMING UPDATE` per flow); run 2 wrote it once (version 4): the web flow read only `orders_002.json`, and the mobile flow had nothing new, so it committed nothing. Version 3 is a table property change the engine made at the start of run 2. The materialized view, in contrast, was emptied and rewritten (`TRUNCATE`, then `WRITE`): the open-source engine recomputes materialized views in full on every update. Incremental refresh is a Databricks feature, and on Databricks only on serverless (section 13.8).

### Run 3: change the silver logic

Now the silver query changes from `upper(status)` to `lower(status)` (the docs' own `LOWER`/`UPPER` example), a mobile file with order 2003 (`"status": "Placed"`) arrives, and the pipeline runs normally:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
##### STEP 3: silver logic changed from upper(status) to lower(status), new mobile file, plain run
landed mobile/orders_002.json (1 orders)
$ spark-pipelines run
   ... (progress lines as in run 1) ...
   Run is COMPLETED.
   (exit code 0)
--- silver_orders
+--------+---------+------+-------+
|order_id|status   |amount|channel|
+--------+---------+------+-------+
|1001    |PLACED   |59.90 |web    |
|1002    |PLACED   |120.00|web    |
|1003    |SHIPPED  |35.50 |web    |
|1004    |PLACED   |42.00 |web    |
|1005    |CANCELLED|64.00 |web    |
|2001    |PLACED   |15.25 |mobile |
|2002    |PLACED   |89.99 |mobile |
|2003    |placed   |18.75 |mobile |
+--------+---------+------+-------+
```

The seven old rows keep the old logic; only order 2003 went through the new query. This is the streaming table contract: each input row is processed once. Bringing the old rows up to date needs a full refresh, which is where the trouble starts.

### Run 4: dry run

Before the full refresh, a quick check of the dry run. A misspelled column (`amout`) in `gold_customers.py`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
##### STEP 4: dry-run with a typo (amount -> amout) in gold_customers.py
$ spark-pipelines dry-run
   ERROR: [CANNOT_MODIFY_STATIC_CONFIG] Cannot modify the value of the static Spark config: "spark.sql.catalogImplementation". SQLSTATE: 46110
   Found 4 files matching glob 'transformations/**/*'
   ERROR: [UNRESOLVED_COLUMN.WITH_SUGGESTION] A column, variable, or function parameter with name `amout` cannot be resolved. Did you mean one of the following? [`amount`, `status`, `channel`, `order_ts`, `currency`]. SQLSTATE: 42703;
   (exit code 1)
```

The error appeared before any data was read or written. The typo was then reverted.

### Run 5: a file expires, then a full refresh of bronze

A retention policy deletes the oldest web file, `orders_001.json` (orders 1001 to 1003). Then someone runs a full refresh of bronze, to "start clean":

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
##### STEP 5: web/orders_001.json is deleted by a retention policy, then full refresh of bronze only
deleted web/orders_001.json
$ spark-pipelines run --full-refresh bronze_orders
   ERROR: [CANNOT_MODIFY_STATIC_CONFIG] Cannot modify the value of the static Spark config: "spark.sql.catalogImplementation". SQLSTATE: 46110
   Found 4 files matching glob 'transformations/**/*'
   Flow orders_web is QUEUED.
   Flow orders_mobile is QUEUED.
   Flow 'silver_orders' is EXCLUDED.
   Flow 'gold_customer_totals' is EXCLUDED.
   Flow 'gold_daily_sales' is EXCLUDED.
   Flow orders_web is STARTING.
   Flow orders_web is RUNNING.
   Flow orders_mobile is STARTING.
   Flow orders_mobile is RUNNING.
   Flow orders_mobile has COMPLETED.
   Flow orders_web has COMPLETED.
   Run is COMPLETED.
   (exit code 0)
--- bronze_orders
+--------+---------+-------+---------------+
|order_id|status   |channel|source_file    |
+--------+---------+-------+---------------+
|1004    |PLACED   |web    |orders_002.json|
|1005    |CANCELLED|web    |orders_002.json|
|2001    |PLACED   |mobile |orders_001.json|
|2002    |PLACED   |mobile |orders_001.json|
|2003    |Placed   |mobile |orders_002.json|
+--------+---------+-------+---------------+
--- silver_orders
+--------+---------+-------+
|order_id|status   |channel|
+--------+---------+-------+
|1001    |PLACED   |web    |
|1002    |PLACED   |web    |
|1003    |SHIPPED  |web    |
|1004    |PLACED   |web    |
|1005    |CANCELLED|web    |
|2001    |PLACED   |mobile |
|2002    |PLACED   |mobile |
|2003    |placed   |mobile |
+--------+---------+-------+
--- gold_daily_sales
+----------+--------+------+-------+
|order_date|currency|orders|revenue|
+----------+--------+------+-------+
|2026-03-01|CAD     |3     |195.15 |
|2026-03-01|USD     |1     |35.50  |
|2026-03-02|CAD     |2     |131.99 |
|2026-03-02|USD     |1     |18.75  |
+----------+--------+------+-------+
```

Three things to notice:

- Bronze was truncated and rebuilt from the files still in the landing folder. Orders 1001, 1002 and 1003 are gone from it. Nothing warned about it.
- In open source, `--full-refresh bronze_orders` refreshed only bronze: the flows of the other datasets were reported as `EXCLUDED`. The 4.2 guide only says the option lists "datasets to reset and recompute"; the Spark 4.2.0 source ([PipelinesHandler.scala](https://github.com/apache/spark/blob/v4.2.0/sql/connect/server/src/main/scala/org/apache/spark/sql/connect/pipelines/PipelinesHandler.scala)) confirms the behavior: with only `--full-refresh` given, every other dataset gets a `NoTables` refresh filter. Silver and gold still contain the lost orders, so the layers now disagree.
- Bronze's own raw rows were never transformed, so they still show `Placed` for 2003.

### Run 6: the next update fails

The next normal update:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
##### STEP 6: a plain run after the bronze-only full refresh
$ spark-pipelines run
   ERROR: [CANNOT_MODIFY_STATIC_CONFIG] Cannot modify the value of the static Spark config: "spark.sql.catalogImplementation". SQLSTATE: 46110
   Found 4 files matching glob 'transformations/**/*'
   Flow orders_web is QUEUED.
   Flow gold_daily_sales is QUEUED.
   Flow orders_mobile is QUEUED.
   Flow silver_orders is QUEUED.
   Flow gold_customer_totals is QUEUED.
   Flow orders_mobile is STARTING.
   Flow orders_mobile is RUNNING.
   Flow orders_web is STARTING.
   Flow orders_web is RUNNING.
   Flow orders_web has COMPLETED.
   Flow orders_mobile has COMPLETED.
   Flow silver_orders is STARTING.
   Flow silver_orders is RUNNING.
   ERROR: [DELTA_SOURCE_IGNORE_DELETE] Detected deleted data (for example part-00000-83f55792-f6c6-4c25-997a-29c4346dee8c-c000.snappy.parquet) from streaming source at version 7. This is currently not supported. If you'd like to ignore deletes, set the option 'ignoreDeletes' to 'true'. The source table can be found at path file:<scratch>/work/ch
   Flow silver_orders has COMPLETED.
   Flow 'silver_orders' has FAILED.
   ERROR: [STREAM_FAILED] Query [id = 3fcc7f7c-f675-49b7-9745-79f6188ac8db, runId = 97361f86-3f23-493f-ac49-0a542dd7b799] terminated with exception: [DELTA_SOURCE_IGNORE_DELETE] Detected deleted data (for example part-00000-83f55792-f6c6-4c25-997a-29c4346dee8c-c000.snappy.parquet) from streaming source at version 7. This is currently not supported. If you'd like to ignore deletes, set the option 'ignoreDele
   Flow silver_orders is STARTING.
   Flow silver_orders is RUNNING.
   Flow silver_orders has COMPLETED.
   Flow 'silver_orders' has FAILED.
   ERROR: [STREAM_FAILED] Query [id = 3fcc7f7c-f675-49b7-9745-79f6188ac8db, runId = 038279af-c424-45c1-a488-a676e166d83c] terminated with exception: [DELTA_SOURCE_IGNORE_DELETE] Detected deleted data (for example part-00000-83f55792-f6c6-4c25-997a-29c4346dee8c-c000.snappy.parquet) from streaming source at version 7. This is currently not supported. If you'd like to ignore deletes, set the option 'ignoreDele
   Flow silver_orders is STARTING.
   Flow silver_orders is RUNNING.
   Flow silver_orders has COMPLETED.
   Flow 'silver_orders' has FAILED more than 2 times and will not be restarted.
   ERROR: [STREAM_FAILED] Query [id = 3fcc7f7c-f675-49b7-9745-79f6188ac8db, runId = b529aef0-670b-441d-b17d-ebf57b8c339f] terminated with exception: [DELTA_SOURCE_IGNORE_DELETE] Detected deleted data (for example part-00000-83f55792-f6c6-4c25-997a-29c4346dee8c-c000.snappy.parquet) from streaming source at version 7. This is currently not supported. If you'd like to ignore deletes, set the option 'ignoreDele
   Flow 'gold_daily_sales' SKIPPED due to upstream failure(s).
   Flow 'gold_customer_totals' SKIPPED due to upstream failure(s).
   (exit code 1)
--- silver_orders
+--------+---------+-------+
|order_id|status   |channel|
+--------+---------+-------+
|1001    |PLACED   |web    |
|1002    |PLACED   |web    |
|1003    |SHIPPED  |web    |
|1004    |PLACED   |web    |
|1005    |CANCELLED|web    |
|2001    |PLACED   |mobile |
|2002    |PLACED   |mobile |
|2003    |placed   |mobile |
+--------+---------+-------+
```

This is the Databricks warning in action: "If the streaming table has dependent downstream tables, the pipeline fails until those tables are also fully refreshed, unless the streaming table has skipChangeCommits enabled." Silver reads bronze as a Delta stream, and a truncated source is not an append (`DELTA_SOURCE_IGNORE_DELETE`). The engine retried the flow, gave up after the third failure ("FAILED more than 2 times and will not be restarted") and skipped both gold views "due to upstream failure(s)". Silver is unchanged.

### Run 7: full refresh of everything

The way out is a full refresh of everything downstream as well (here the whole pipeline):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
##### STEP 7: full refresh of the whole pipeline
$ spark-pipelines run --full-refresh-all
   ... (progress lines as in run 1) ...
   Run is COMPLETED.
   (exit code 0)
========== tables after step 7
--- bronze_orders (streaming table, 2 append flows)
+--------+---------+------+-------+---------------+
|order_id|status   |amount|channel|source_file    |
+--------+---------+------+-------+---------------+
|1004    |PLACED   |42.00 |web    |orders_002.json|
|1005    |CANCELLED|64.00 |web    |orders_002.json|
|2001    |PLACED   |15.25 |mobile |orders_001.json|
|2002    |PLACED   |89.99 |mobile |orders_001.json|
|2003    |Placed   |18.75 |mobile |orders_002.json|
+--------+---------+------+-------+---------------+
--- silver_orders (streaming table)
+--------+-----------+-------------------+---------+------+--------+-------+
|order_id|customer_id|order_ts           |status   |amount|currency|channel|
+--------+-----------+-------------------+---------+------+--------+-------+
|1004    |3          |2026-03-02 12:00:00|placed   |42.00 |CAD     |web    |
|1005    |9          |2026-03-02 13:10:00|cancelled|64.00 |CAD     |web    |
|2001    |7          |2026-03-01 18:05:00|placed   |15.25 |CAD     |mobile |
|2002    |12         |2026-03-02 09:30:00|placed   |89.99 |CAD     |mobile |
|2003    |12         |2026-03-02 20:45:00|placed   |18.75 |USD     |mobile |
+--------+-----------+-------------------+---------+------+--------+-------+
--- gold_daily_sales (materialized view, SQL)
+----------+--------+------+-------+
|order_date|currency|orders|revenue|
+----------+--------+------+-------+
|2026-03-01|CAD     |1     |15.25  |
|2026-03-02|CAD     |2     |131.99 |
|2026-03-02|USD     |1     |18.75  |
+----------+--------+------+-------+
--- gold_customer_totals (materialized view, Python)
+-----------+------+------------+
|customer_id|orders|total_amount|
+-----------+------+------------+
|3          |1     |42.00       |
|7          |1     |15.25       |
|9          |1     |64.00       |
|12         |2     |108.74      |
+-----------+------+------------+
```

Every table is consistent again, and every silver row now uses `lower(status)`. But orders 1001 to 1003 are gone from every layer: 2026-03-01 CAD revenue fell from 195.15 to 15.25, and customer 7 lost order 1001. Their only copy was a landing file that no longer exists. This is exactly the interview scenario "a full refresh wiped history", reproduced in seven commands. On Databricks the cure is the same as in section 13.7: a raw bronze table that is never fully refreshed (`pipelines.reset.allowed = false`, which the properties reference says also exists in open-source SDP), and full refreshes only for tables whose sources still hold all the data.

## 13.12 Practice questions

**Q1. An interviewer asks whether you have used Delta Live Tables. What is it called today, and does old DLT code still run?**

??? success "Answer"
    Delta Live Tables (DLT) is now **Lakeflow pipelines**, documented as Spark Declarative Pipelines on Lakeflow, built on open-source Apache Spark Declarative Pipelines. The official "What happened to Delta Live Tables (DLT)?" page says "there is no migration required to use Lakeflow pipelines: your code will still work."

    **Why:** Databricks contributed the declarative engine to Apache Spark (from Spark 4.1) and renamed the product around it. The `dlt` name survives in the classic SKUs and the event log schemas. Say both names in the interview.

**Q2. Rewrite this legacy code with the current module. What does each decorator become?**

*Databricks only, not run here. Legacy `dlt` form; names from [What happened to `@dlt`?](https://docs.databricks.com/aws/en/ldp/developer/python-ref#dlt-or-pipeline).*

```python
import dlt

@dlt.table
def bronze(): return spark.readStream.table("raw_orders")

@dlt.table
def gold(): return spark.read.table("silver_orders").groupBy("currency").count()

@dlt.view
def tmp(): return spark.read.table("silver_orders")
```

??? success "Answer"
    *Databricks only, not run here. Names from [What happened to `@dlt`?](https://docs.databricks.com/aws/en/ldp/developer/python-ref#dlt-or-pipeline).*

    ```python
    from pyspark import pipelines as dp

    @dp.table                     # streaming DataFrame -> streaming table
    def bronze(): return spark.readStream.table("raw_orders")

    @dp.materialized_view         # batch DataFrame -> materialized view
    def gold(): return spark.read.table("silver_orders").groupBy("currency").count()

    @dp.temporary_view            # was @dlt.view
    def tmp(): return spark.read.table("silver_orders")
    ```

    **Why:** In `dlt`, `@dlt.table` made either kind of table depending on the DataFrame. The new module separates them: `@dp.table` for streaming tables, `@dp.materialized_view` for materialized views, and `@view` became `@temporary_view`.

**Q3. In one sentence each, how do a streaming table, a materialized view and a view process records?**

??? success "Answer"
    From "Pipeline concepts": a streaming table processes each record "exactly one time, assuming an append-only source"; a materialized view's "results are recomputed as needed to reflect the current state of the data"; a view is "evaluated on demand, not persisted".

    **Why:** This one line decides almost every design choice: append-only data goes into streaming tables, results that must track corrections go into materialized views, and intermediate steps nobody outside the pipeline reads can stay views.

**Q4. Scenario: a full refresh of a DLT streaming table fed by Kafka (7 days retention) left only one week of data. Why, and how do you avoid it next time?**

??? success "Answer"
    In Lakeflow pipelines (formerly Delta Live Tables) a full refresh "truncates the streaming table, removes all checkpoint data, and restarts the streaming process with new checkpoints for every flow writing to the table." The table is rebuilt from what Kafka still holds: seven days. Everything older is gone.

    Avoid it: (1) land Kafka into a raw bronze streaming table with flexible types (string or variant) so it never needs a full refresh, and rebuild downstream tables from bronze; (2) set `TBLPROPERTIES ('pipelines.reset.allowed' = 'false')` on that bronze table; (3) when logic or sources change, add a new flow or reset selected flow checkpoints instead of a full refresh; (4) if a full refresh is unavoidable, check the source retention first and backfill from an archive with a `ONCE` flow.

    **Why:** The updates page warns that a full refresh "can result in dropped records if input data is no longer available". Section 13.11 reproduces this with a deleted landing file.

**Q5. When would you pick a materialized view over a streaming table?**

??? success "Answer"
    When the result must always equal the query over the current data: aggregations, joins with dimensions that change, or sources that get updates and deletes, not only appends. Also when several consumers read the result or it must be queryable outside the pipeline.

    **Why:** A streaming table reads each row once. "Joins in streaming tables do not recompute when dimensions change", whereas materialized views "automatically recompute joins when dimensions change". Pick a streaming table for append-only ingestion and low-latency transforms.

**Q6. Delta Live Tables versus a plain Structured Streaming job scheduled with Jobs: what do you gain and lose?**

??? success "Answer"
    Gain with Lakeflow pipelines (formerly DLT): the dependency graph is inferred from the code, checkpoints are managed per flow, retries go from task to flow to pipeline, plus expectations, AUTO CDC (formerly APPLY CHANGES), an event log, lineage, materialized views with incremental refresh on serverless, and full/selective refresh from the UI.

    Lose: fine control. Procedural code with Lakeflow Jobs (formerly Workflows) lets you write any `foreachBatch` logic, choose checkpoint locations, and order steps exactly. Dataset functions in a pipeline must only return a DataFrame, `pivot()` is not supported, and tables belong to one pipeline.

    **Why:** The "Procedural vs. declarative" page puts Spark plus Lakeflow Jobs on the procedural side ("Full control over execution") and pipelines on the declarative side ("Execution handled by system").

**Q7. What does this print? A pipeline's silver streaming table used `upper(status)`. Orders 1001 to 1005 are already in it. You change the query to `lower(status)`, a file with order 2003 (status `Placed`) arrives, and you run a normal update. What is the `status` of orders 1001 and 2003 in silver?**

??? success "Answer"
    Order 1001 stays `PLACED`; order 2003 is `placed`. Section 13.11 ran exactly this:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +--------+---------+------+-------+
    |order_id|status   |amount|channel|
    +--------+---------+------+-------+
    |1001    |PLACED   |59.90 |web    |
    |1002    |PLACED   |120.00|web    |
    |1003    |SHIPPED  |35.50 |web    |
    |1004    |PLACED   |42.00 |web    |
    |1005    |CANCELLED|64.00 |web    |
    |2001    |PLACED   |15.25 |mobile |
    |2002    |PLACED   |89.99 |mobile |
    |2003    |placed   |18.75 |mobile |
    +--------+---------+------+-------+
    ```

    **Why:** A default refresh of a streaming table processes only new records "using the current definition of the table. Older records are not reprocessed." To apply the new logic to old rows you need a full refresh (or a checkpoint reset, which keeps the old rows too and can duplicate them).

**Q8. Find the bug.**

*Databricks only, not run here. Syntax from [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table).*

```sql
CREATE OR REFRESH STREAMING TABLE shop.silver.orders
AS SELECT order_id, upper(status) AS status
FROM shop.bronze.orders;
```

??? success "Answer"
    The query of a streaming table "must be a **streaming** query. Use the STREAM keyword": `FROM STREAM(shop.bronze.orders)`.

    *Databricks only, not run here. Syntax from [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table).*

    ```sql
    CREATE OR REFRESH STREAMING TABLE shop.silver.orders
    AS SELECT order_id, upper(status) AS status
    FROM STREAM(shop.bronze.orders);
    ```

    **Why:** Without `STREAM` the source is read as a batch. If you wanted batch semantics, the right object is a materialized view.

**Q9. Find the bug in this pipeline function.**

*Databricks only, not run here. Syntax from [Lakeflow pipelines Python language reference](https://docs.databricks.com/aws/en/ldp/developer/python-ref).*

```python
@dp.materialized_view
def gold_daily_sales():
    df = spark.read.table("silver_orders").groupBy("currency").count()
    print("rows:", df.count())
    return df
```

??? success "Answer"
    Remove the `count()` (and the `print`). The Python reference lists `collect()`, `count()`, `toPandas()`, `save()`, `saveAsTable()`, `start()` and `toTable()` as operations that "should never be used in pipeline code".

    **Why:** "A pipeline evaluates its source code multiple times during planning and runs", so side effects run several times and an action forces a Spark job during planning. A dataset function should only build and return a DataFrame; use the event log or event hooks for monitoring.

**Q10. What does `@dp.table` create when the function returns a batch DataFrame from `spark.read.table(...)`?**

??? success "Answer"
    A materialized view. The `@table` page says the `@table` operator in `pyspark.pipelines` "still works in this way" (as in old `dlt`), "but Databricks recommends using the `@materialized_view` operator to create materialized views."

    **Why:** Backward compatibility with `@dlt.table`. Use `@dp.materialized_view` so the intent is visible in the code.

**Q11. Write the SQL for one streaming table `shop.bronze.orders` fed by two folders (web and mobile) and a one-time backfill from an archive folder.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [CREATE FLOW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-flow).*

    ```sql
    CREATE OR REFRESH STREAMING TABLE shop.bronze.orders;

    CREATE FLOW orders_web AS
    INSERT INTO shop.bronze.orders BY NAME
    SELECT * FROM STREAM read_files('/Volumes/shop/bronze/landing/web/', format => 'json');

    CREATE FLOW orders_mobile AS
    INSERT INTO shop.bronze.orders BY NAME
    SELECT * FROM STREAM read_files('/Volumes/shop/bronze/landing/mobile/', format => 'json');

    CREATE FLOW orders_backfill AS
    INSERT ONCE INTO shop.bronze.orders BY NAME
    SELECT * FROM read_files('/Volumes/shop/bronze/archive/', format => 'json');
    ```

    **Why:** Separate flows let each source keep its own checkpoint. `ONCE` reads a batch query one time, and again only after a full refresh.

**Q12. Write the same thing in Python.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [append_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-append-flow).*

    ```python
    from pyspark import pipelines as dp

    dp.create_streaming_table("shop.bronze.orders")

    def landing(folder):
        return (spark.readStream.format("cloudFiles").option("cloudFiles.format", "json")
                .load(f"/Volumes/shop/bronze/landing/{folder}/"))

    @dp.append_flow(target="shop.bronze.orders")
    def orders_web():
        return landing("web")

    @dp.append_flow(target="shop.bronze.orders")
    def orders_mobile():
        return landing("mobile")

    @dp.append_flow(target="shop.bronze.orders", once=True)
    def orders_backfill():
        return spark.read.format("json").load("/Volumes/shop/bronze/archive/")
    ```

    **Why:** `dp.create_streaming_table` declares the target without a query; each `@dp.append_flow` adds a source. With `once=True` the function must return a batch DataFrame. The open-source version of the first two flows ran in section 13.11 (4.2 has no `once` argument).

**Q13. Why use two append flows rather than one query with `UNION ALL` to combine two streaming sources?**

??? success "Answer"
    Adding or removing a source in a `UNION` changes the flow's sources, and "Modifying the source tables read by the streaming query" requires a full refresh. With one flow per source, a new source is a new flow with a new checkpoint; existing data and checkpoints are untouched.

    **Why:** The flows page lists "Combine data from multiple sources without using a `UNION` clause" and adding sources "without requiring a full refresh" as the reasons separate flows exist.

**Q14. You rename the flow `orders_web` to `orders_webshop`. What happens on the next update?**

??? success "Answer"
    The renamed flow starts with no checkpoint and reads its whole source again, so the streaming table gets duplicates of everything already loaded from that folder (unless the source has expired data).

    **Why:** "Flows are identified by a _flow name_, and this name is used to identify streaming checkpoints... If an existing flow in a pipeline is renamed, the checkpoint does not carry over, and the renamed flow is effectively an entirely new flow."

**Q15. What is the difference between a full refresh and a checkpoint reset of a streaming table?**

??? success "Answer"
    Full refresh: clears the table's data and its flows' checkpoints, then reprocesses everything the source holds. Checkpoint reset: clears the checkpoints of selected flows but keeps the table's data, then reprocesses the source through those flows. Reset is triggered through the REST API with `reset_checkpoint_selection` and fully qualified flow names.

    **Why:** A reset keeps history when the source has lost old data, at the price of possible duplicates for data still in the source. A full refresh gives a clean table only if the source still has everything.

**Q16. How do you stop anyone from running a full refresh on a bronze table?**

??? success "Answer"
    Set the table property `pipelines.reset.allowed` to `false` (default `true`).

    *Databricks only, not run here. Syntax from [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table).*

    ```sql
    CREATE OR REFRESH STREAMING TABLE shop.bronze.orders
      TBLPROPERTIES ('pipelines.reset.allowed' = 'false')
    AS SELECT * FROM STREAM read_files('/Volumes/shop/bronze/landing/orders/', format => 'json');
    ```

    **Why:** The updates page: "To prevent full refreshes from being run on a table or view, set the table property `pipelines.reset.allowed` to `false`." The properties reference notes the property is also available in open-source SDP.

**Q17. You fully refreshed only the bronze streaming table, and the next update failed in silver. Why?**

??? success "Answer"
    Silver is a streaming table that reads bronze as a stream. A full refresh rewrites bronze (truncate and reload), which is not an append, so silver's stream cannot continue. The docs: "If the streaming table has dependent downstream tables, the pipeline fails until those tables are also fully refreshed, unless the streaming table has skipChangeCommits enabled." Fully refresh bronze and silver together; the same page adds that "Downstream materialized views must also be fully refreshed." Section 13.11 shows the open-source engine doing the same: after a bronze-only full refresh, the next run failed in silver with `[DELTA_SOURCE_IGNORE_DELETE] Detected deleted data ... from streaming source`.

    **Why:** Streaming reads from Delta require an append-only source; truncation is a change to existing data.

**Q18. A gold materialized view in a pipeline on classic compute is recomputed from scratch on every update. Is something broken?**

??? success "Answer"
    No. "Materialized views that do not use serverless pipelines are always fully recomputed." Incremental refresh needs a serverless pipeline. Switch the pipeline to serverless (it needs Unity Catalog and the `ADVANCED` edition).

    **Why:** The incremental refresh engine runs only on serverless pipelines. The result is the same either way; only cost and time differ.

**Q19. On serverless, a materialized view `SELECT customer_id, SUM(amount_double) AS spend FROM orders GROUP BY customer_id` always does a full recompute. Why, and what do you change?**

??? success "Answer"
    Sums over `FLOAT` or `DOUBLE` "can produce non-deterministic results ... and force a full refresh". Cast to `DECIMAL`: `SUM(CAST(amount_double AS DECIMAL(18,2)))`. Also check that the source has row tracking enabled (`delta.enableRowTracking = true`).

    **Why:** Incremental refresh must give the same result as a full recompute; floating point addition in a different order may not. Check the outcome in the Incrementalization column or the `planning_information` events.

**Q20. How do you make sure a materialized view never silently falls back to an expensive full recompute?**

??? success "Answer"
    Add `REFRESH POLICY INCREMENTAL STRICT` (Python: `refresh_policy='incremental_strict'`). The refresh then fails if it cannot be incremental.

    **Why:** The default `AUTO` picks by cost. `INCREMENTAL STRICT` is "recommended when users prefer the update to fail, allowing them to debug the issue rather than proceed with a full refresh."

**Q21. Triggered or continuous: which do you choose for an hourly dashboard, and how do you run a continuous pipeline in production?**

??? success "Answer"
    Triggered for an hourly dashboard: it processes the data available at start and stops, so compute runs only during the update; the docs place triggered at "every 10 minutes, hourly, or daily". For a continuous pipeline in production, Databricks "recommends running continuous pipelines with a continuous job rather than setting the value of **Pipeline mode** to continuous", and leaving the pipeline's own mode as triggered.

    **Why:** Continuous mode keeps a cluster running, "usually the largest cost factor", so it should be reserved for a proven latency need (seconds to minutes).

**Q22. A pipeline fails when you click Run in the editor but the same pipeline succeeds when its job runs at night. How can that be?**

??? success "Answer"
    Updates started from the editor or monitoring UI use "fast-start, debugging-focused behavior": cluster reuse and no pipeline retries. Updates from Jobs or the API use automatic retry and restart behavior: the page lists "Restarts the cluster for specific recoverable errors" and retries. A transient error (a cluster start failure, stale credentials) is retried at night but shown immediately in the editor.

    **Why:** This is the old development versus production mode distinction in Delta Live Tables, now described as update run behavior. A green scheduled run can hide a flaky dependency.

**Q23. What three things does a pipeline update do, and what does a dry run skip?**

??? success "Answer"
    It starts a cluster with the right configuration, discovers all tables and views and checks for analysis errors (invalid columns, missing dependencies, syntax), then creates or updates the datasets with the latest data. A dry run "resolves the definitions of datasets and flows defined in the pipeline but does not materialize or publish any datasets."

    **Why:** Validation before data movement is part of the declarative model; the event log records the update states, from `INITIALIZING` and `SETTING_UP_TABLES` to `RUNNING` and `COMPLETED`.

**Q24. Can you run `MERGE`, `TRUNCATE`, `RESTORE` or `CLONE` against a pipeline's streaming table?**

??? success "Answer"
    `TRUNCATE`, `RESTORE`, `COPY INTO`, `ANALYZE TABLE`, `GENERATE MANIFEST`, `[CREATE OR] REPLACE TABLE` and `CREATE TABLE ... CLONE <streaming_table>` are listed as not supported, and "Evolving the table schema through DML commands like `INSERT INTO`, and `MERGE` is not supported." `ALTER TABLE` is disallowed; use `CREATE OR REFRESH` or `ALTER STREAMING TABLE`.

    **Why:** The pipeline owns the table's definition and checkpoints. Change it through the pipeline code; use `AUTO CDC` (chapter 14) for upserts.

**Q25. Can a second pipeline write into a streaming table that the first pipeline defines?**

??? success "Answer"
    No. "Tables defined by a pipeline can't be changed or updated by any other pipeline." Datasets "can be defined only once", so they are the target of a single operation across all pipelines; the exception is that one streaming table can take several append flows inside its pipeline.

    **Why:** One owner per dataset keeps checkpoints, lineage and refresh semantics consistent. Another pipeline can read the table; to write from a second source, add an append flow in the owning pipeline.

**Q26. Does Delta time travel work on pipeline tables?**

??? success "Answer"
    On streaming tables yes, on materialized views no: time travel queries "are supported only with streaming tables, and are _not_ supported with materialized views".

    **Why:** The limitations page states the rule without a reason. A likely one (not verified): a materialized view's table is rewritten by the pipeline's refreshes, full or incremental, so its versions are not a meaningful series of user changes.

**Q27. When do you write to a sink instead of a streaming table, and what are the catches?**

??? success "Answer"
    When the output must leave the pipeline's managed tables: a Kafka or Event Hubs topic for low-latency consumers, reverse ETL, an external Delta table, or a custom Python data source. Catches: Python only, streaming queries only, only `append_flow` and `update_flow` can write to sinks, no expectations, and "Running a full refresh does not clean up previously written data in sinks."

    **Why:** The pipeline does not own the sink's data, so it cannot truncate it; exactly-once stops at the edge, and the how-to guide says to treat such writes as at-least-once and make them idempotent.

**Q28. Old pipeline code contains `SELECT * FROM LIVE.silver_orders` and `CREATE OR REFRESH LIVE TABLE`. What do these mean today?**

??? success "Answer"
    `LIVE.` is the legacy virtual schema for referring to datasets of the same pipeline; "In new pipelines, the `LIVE` schema syntax is silently ignored." `CREATE OR REFRESH LIVE TABLE` for a materialized view "is deprecated. Instead, use `CREATE OR REFRESH MATERIALIZED VIEW`." Pipelines created before February 5, 2025 may still use the legacy publishing mode.

    **Why:** Since the default publishing mode, a pipeline resolves names with normal three-level Unity Catalog rules, so a plain or fully qualified name is enough.

**Q29. A silver streaming table joins orders to the customers table to add the city. A customer moves from Calgary to Banff. What happens to that customer's existing silver rows, and what would you use if they must show the new city?**

??? success "Answer"
    Nothing: existing rows keep Calgary, and only orders processed after the change get Banff. "Joins in streaming tables do not recompute when dimensions change." If every row must show the current city, do the join in a materialized view, which recomputes joins when dimensions change.

    **Why:** A streaming table processes each input row once. For history-aware dimensions, keep customers as an SCD Type 2 table (chapter 14) and join on the validity range.

**Q30. Which product edition does a pipeline need for expectations, for CDC, and for serverless?**

??? success "Answer"
    `CORE` covers streaming ingest; `PRO` adds CDC; `ADVANCED` adds expectations. Serverless pipelines require `ADVANCED`. `ADVANCED` is the default edition.

    **Why:** From "Configure pipelines": "If your pipeline includes features not supported by the selected product edition, such as expectations, you receive an error message".

**Q31. What does Databricks add on top of open-source Spark Declarative Pipelines?**

??? success "Answer"
    Per the Databricks comparison page: AUTO CDC (SCD Type 1 and 2, and from snapshots), data quality expectations, a queryable event log, update flows and `foreachBatch` sinks, and continuous mode; plus the platform around it (serverless compute and incremental refresh of materialized views, Auto Loader, Unity Catalog, the editor and monitoring UI). Shared: streaming tables, materialized views, temporary views, append flows, sinks, automatic orchestration. Note that the Apache Spark 4.3.0 guide now documents an open-source Auto CDC flow, so this line is moving.

    **Why:** "Code written with the open-source `pipelines` module runs without modification on Databricks", but not the other way around.

**Q32. Why is `pivot()` not supported in pipelines?**

??? success "Answer"
    "The `pivot` operation in Spark requires the eager loading of input data to compute the output schema. This capability is not supported in pipelines." The output columns depend on the data, so the pipeline cannot know the dataset's schema when it builds the graph. List the pivot values explicitly with conditional aggregation instead (`sum(CASE WHEN currency = 'CAD' THEN amount END) AS cad_revenue`).

    **Why:** The pipeline analyzes every dataset's schema before it runs anything.

**Q33. How do you see what a pipeline did in its last updates, programmatically?**

??? success "Answer"
    Query the event log: `SELECT timestamp, event_type, message FROM event_log('<pipeline-id>')`, or `event_log(TABLE(catalog.schema.table))` for a table, or publish the event log to a named Unity Catalog table. For many pipelines, Databricks recommends the `pipeline_events` system table (Beta).

    **Why:** The event log is "the ground truth" under the UI: update states, flow progress, data quality metrics, lineage, and `planning_information` events that show how materialized views were refreshed.

**Q34. You create a standalone materialized view from a small SQL warehouse. Where does the refresh run, and how is it billed?**

??? success "Answer"
    On a serverless pipeline that Databricks creates for the view, billed as serverless Lakeflow pipelines DBUs. "The cluster size of your warehouse does not limit the compute or cost used by the refresh." The pipeline appears in Jobs & Pipelines with type `MV/ST`.

    **Why:** Standalone materialized views and streaming tables are pipelines managed for you. They run only in triggered mode, via `SCHEDULE`, `TRIGGER ON UPDATE`, `REFRESH` or a SQL task in a job.

**Q35. When do you choose a standalone materialized view over a Lakeflow pipeline?**

??? success "Answer"
    Standalone: a single table to accelerate a dashboard or a simple transform, written in SQL from a warehouse, refreshed on a schedule or when sources change. Pipeline: several stages with dependencies, Python, sinks, private intermediate datasets, `create_auto_cdc_from_snapshot_flow()`, or continuous execution.

    **Why:** Both produce Unity Catalog managed tables with the same semantics; "The difference is how much of the pipeline you author and operate."

**Q36. Your bronze streaming table parses Kafka JSON into strict types. A producer changes a field from integer to string. What breaks, and what design avoids it?**

??? success "Answer"
    An incompatible type change in the target needs a full refresh, and with Kafka retention that loses history. Design: keep bronze raw, with flexible column types (the payload as string or `VARIANT`), and parse into typed columns in silver. If silver needs a full refresh, it rebuilds from bronze, which still holds everything.

    **Why:** This is the full-refresh page's own best practice for sources with short retention.

**Q37. The engineer who created a production pipeline leaves the company and the pipeline starts failing. What should have been set up?**

??? success "Answer"
    The pipeline's run-as identity should be a service principal (or an account group), not a person. Change **Run as** in the pipeline settings; in Unity Catalog pipelines the owner of the published tables changes to the new identity.

    **Why:** "Running pipelines as service principals is considered a best practice because they are not tied to individual users."

**Q38. What does `spark-pipelines dry-run` catch in open-source SDP?**

??? success "Answer"
    Errors that would stop a run, without reading or writing data: "Syntax errors", "Analysis errors – e.g. selecting from a table or a column that doesn't exist" and "Graph validation errors - e.g. cyclic dependencies". In section 13.11, a misspelled column was reported before anything ran:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    [UNRESOLVED_COLUMN.WITH_SUGGESTION] A column, variable, or function parameter with name `amout` cannot be resolved. Did you mean one of the following? [`amount`, `status`, `channel`, `order_ts`, `currency`]. SQLSTATE: 42703;
    ```

    **Why:** The graph and every dataset's schema are resolved before execution. Databricks has the same idea as the dry run button (Public Preview).

**Q39. Can you add an identity column as a surrogate key in a gold materialized view?**

??? success "Answer"
    Not reliably. The limitations page says identity columns "might be recomputed during updates to a materialized views" and recommends using them "only with streaming tables"; the standalone materialized view page says "Materialized views do not support identity columns or surrogate keys." Generate keys in a streaming table, or use a deterministic hash of the business key.

    **Why:** A recomputed materialized view would hand out new identity values, breaking joins from fact tables.

**Q40. True or false: in a pipeline, a streaming table can only be fed by one source.**

??? success "Answer"
    False. A streaming table can have any number of append flows, or several AUTO CDC flows (a table targeted by AUTO CDC flows "can only be targeted by other auto CDC flows"). A materialized view is different: "you always define the flows implicitly as part of the materialized view definition", so you cannot add a separate flow to it (the Spark guide puts it as "exactly one batch flow").

    **Why:** For streaming tables, flows are separate objects from the table; that is what makes adding sources and backfills possible without a full refresh.

## Sources

- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [Spark Declarative Pipelines on Lakeflow](https://docs.databricks.com/aws/en/ldp/) (last updated Oct 22, 2026)
- [Pipeline concepts](https://docs.databricks.com/aws/en/ldp/concepts/) (last updated Nov 5, 2026)
- [How to use Spark Declarative Pipelines on Lakeflow](https://docs.databricks.com/aws/en/ldp/concepts/how-to-use-pipelines) (last updated Oct 22, 2026)
- [Apache Spark Declarative Pipelines](https://docs.databricks.com/aws/en/ldp/concepts/spark-declarative-pipelines) (last updated Oct 9, 2026)
- [Procedural vs. declarative data processing in Databricks](https://docs.databricks.com/aws/en/data-engineering/procedural-vs-declarative) (last updated Nov 5, 2026)
- [What are pipelines?](https://docs.databricks.com/aws/en/ldp/concepts/pipelines) (last updated Oct 15, 2026)
- [Streaming tables](https://docs.databricks.com/aws/en/ldp/streaming-tables) (last updated Oct 9, 2026)
- [Materialized views](https://docs.databricks.com/aws/en/ldp/materialized-views) (last updated Oct 15, 2026)
- [Load and process data incrementally with Lakeflow pipeline flows](https://docs.databricks.com/aws/en/ldp/concepts/flows) (last updated Sep 11, 2026)
- [Use flows in Lakeflow pipelines](https://docs.databricks.com/aws/en/ldp/flow-examples) (last updated Oct 30, 2026)
- [Sinks in Lakeflow pipelines](https://docs.databricks.com/aws/en/ldp/concepts/sinks) (last updated Oct 25, 2026)
- [Configure pipelines](https://docs.databricks.com/aws/en/ldp/configure-pipeline) (last updated Oct 12, 2026)
- [Pipeline properties reference](https://docs.databricks.com/aws/en/ldp/properties) (last updated Oct 19, 2026)
- [Set the target catalog and schema](https://docs.databricks.com/aws/en/ldp/target-schema) (last updated Sep 11, 2026)
- [LIVE schema (legacy)](https://docs.databricks.com/aws/en/ldp/live-schema) (last updated Oct 9, 2026)
- [Move tables between pipelines](https://docs.databricks.com/aws/en/ldp/move-table) (last updated Nov 2, 2026)
- [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc) (last updated Nov 9, 2026)
- [Bringing Declarative Pipelines to the Apache Spark Open Source Project](https://www.databricks.com/blog/bringing-declarative-pipelines-apache-spark-open-source-project) (Databricks blog, Jun 12, 2025)
- [Configure a serverless pipeline](https://docs.databricks.com/aws/en/ldp/serverless) (last updated Oct 12, 2026)
- [Serverless vs. classic compute for pipelines](https://docs.databricks.com/aws/en/ldp/concepts/serverless-vs-classic-compute) (last updated Oct 13, 2026)
- [Lakeflow pipelines release notes and the release upgrade process](https://docs.databricks.com/aws/en/release-notes/dlt/) (last updated Oct 16, 2026)
- [Triggered vs. continuous pipeline mode](https://docs.databricks.com/aws/en/ldp/concepts/pipeline-mode) (last updated Sep 14, 2026)
- [Run a pipeline update](https://docs.databricks.com/aws/en/ldp/updates) (last updated Sep 11, 2026)
- [How do pipelines refresh?](https://docs.databricks.com/aws/en/ldp/concepts/refresh) (last updated Sep 11, 2026)
- [Full refresh for streaming tables](https://docs.databricks.com/aws/en/ldp/full-refresh-st) (last updated Sep 11, 2026)
- [Incremental refresh for materialized views](https://docs.databricks.com/aws/en/ldp/incremental-refresh) (last updated Oct 28, 2026)
- [Pipeline SQL language reference](https://docs.databricks.com/aws/en/ldp/developer/sql-ref) (last updated Sep 11, 2026)
- [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table) (last updated Oct 2, 2026)
- [CREATE MATERIALIZED VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-materialized-view) (last updated Oct 9, 2026)
- [CREATE FLOW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-flow) (last updated Oct 15, 2026)
- [CREATE TEMPORARY VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-temporary-view) (last updated Sep 11, 2026)
- [CREATE VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-view) (last updated Sep 14, 2026)
- [Develop Lakeflow pipelines code with SQL](https://docs.databricks.com/aws/en/ldp/developer/sql-dev) (last updated Oct 15, 2026)
- [Lakeflow pipelines Python language reference](https://docs.databricks.com/aws/en/ldp/developer/python-ref) (last updated Oct 25, 2026)
- [Develop pipeline code with Python](https://docs.databricks.com/aws/en/ldp/developer/python-dev) (last updated Oct 15, 2026)
- [table](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-table) (last updated Oct 15, 2026)
- [materialized_view](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-materialized-view) (last updated Oct 15, 2026)
- [temporary_view](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-view) (last updated Sep 11, 2026)
- [create_streaming_table](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-streaming-table) (last updated Oct 9, 2026)
- [append_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-append-flow) (last updated Nov 2, 2026)
- [Load data in pipelines](https://docs.databricks.com/aws/en/ldp/load) (last updated Oct 19, 2026)
- [Standalone materialized views and streaming tables](https://docs.databricks.com/aws/en/sql/mv-st/) (last updated Oct 15, 2026)
- [Standalone pipelines vs. Lakeflow pipelines](https://docs.databricks.com/aws/en/ldp/concepts/standalone-pipelines) (last updated Oct 15, 2026)
- [Use standalone materialized views](https://docs.databricks.com/aws/en/views/materialized) (last updated Nov 5, 2026)
- [Use standalone streaming tables](https://docs.databricks.com/aws/en/sql/mv-st/streaming) (last updated Oct 15, 2026)
- [When to use REPLACE WHERE vs. materialized views](https://docs.databricks.com/aws/en/sql/mv-st/replace-where-vs-materialized-views) (last updated Oct 15, 2026)
- [REFRESH (MATERIALIZED VIEW or STREAMING TABLE)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-refresh-full) (last updated Oct 15, 2026)
- [Monitor pipelines](https://docs.databricks.com/aws/en/ldp/observability) (last updated Sep 21, 2026)
- [Pipeline event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs) (last updated Nov 3, 2026)
- [Pipeline event log schema](https://docs.databricks.com/aws/en/ldp/monitor-event-log-schema) (last updated Nov 10, 2026)
- [Pipeline limitations](https://docs.databricks.com/aws/en/ldp/limitations) (last updated Oct 22, 2026)
- [Spark Declarative Pipelines Programming Guide, Apache Spark 4.2.0](https://spark.apache.org/docs/4.2.0/declarative-pipelines-programming-guide.html) (no date shown; version 4.2.0)
- [Spark 4.2.0 release notes](https://spark.apache.org/releases/spark-release-4-2-0.html) (no date shown; read Nov 11, 2026)
- [Spark Declarative Pipelines Programming Guide, Apache Spark latest (4.3.0)](https://spark.apache.org/docs/latest/declarative-pipelines-programming-guide.html) (no date shown; version 4.3.0, read Nov 11, 2026)
- [PipelinesHandler.scala, Apache Spark v4.2.0 source](https://github.com/apache/spark/blob/v4.2.0/sql/connect/server/src/main/scala/org/apache/spark/sql/connect/pipelines/PipelinesHandler.scala) (tag v4.2.0, read Nov 11, 2026)
