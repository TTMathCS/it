# 24. The data engineer interview

*This chapter is a question bank. It gathers the questions a data engineer interview on Databricks and the
medallion architecture is likely to ask, each with a model answer, the reasoning behind it, and a link to the
chapter that teaches it. It starts with how such interviews usually run and how to answer well, then goes topic by
topic, then works through troubleshooting scenarios and two full system designs, and ends with a one-page cheat
sheet. Read a question, answer it out loud, and only then open the answer.*

!!! abstract "In this chapter"
    **You will learn:**

    - how data engineering interviews usually run, and a simple method for answering any question;
    - 146 interview questions with model answers and explanations, grouped by topic: platform, Spark, Delta Lake,
      medallion, ingestion, streaming, Lakeflow pipelines (formerly Delta Live Tables), Unity Catalog,
      Databricks SQL, troubleshooting, and migration, cost and table formats;
    - two complete system design walkthroughs: late events from Kafka to dashboards, and daily CDC of 50 tables with
      SCD Type 2;
    - a template for telling your own past project in medallion terms, with a filled-in example;
    - a cheat sheet of commands, renamed products and checked numbers, plus a 20-question mock round.

    **You need:** the earlier chapters help, but every answer links to the chapter that teaches the topic. If the
    interview is soon, read 24.1, 24.5, 24.11, 24.15 and the cheat sheet first.

    **Levels:** section 24.1 beginner; sections 24.2 to 24.10 beginner to intermediate; sections 24.11 to 24.14
    intermediate to expert; 24.15 beginner; 24.16 and 24.17 review.

How to use the answers: each answer box holds the model answer first (what you would say in about a minute), then
**Why** (the reasoning an interviewer probes next), then a **Learn more** link. Code marked *Run here* was run on
Apache Spark 4.2 with Delta Lake 4.4.1 and the output is real; the scripts and their output are in
`src/ch24/`. Code marked *Databricks only* needs a workspace and was checked against the linked official page.

## 24.1 How data engineering interviews usually run

*Level: beginner.*

Every company runs its own process, and the names and order of rounds vary. What follows is a common pattern, not
a description of any particular employer. Ask the recruiter which rounds you will have and what each one covers;
that is a normal question and the answer tells you what to practice.

| Round | What it usually tests | How to prepare | Where in this book |
| --- | --- | --- | --- |
| Screen (recruiter or hiring manager) | Motivation, a short tour of your past projects, logistics | A two-minute story of one pipeline you built: sources, volume, tools, one problem you solved | 24.1, 24.15 |
| Online coding test | SQL (joins, window functions, deduplication, aggregation, NULL handling) and Python (lists, dictionaries, string and JSON parsing); sometimes PySpark | Timed practice on a laptop, no autocomplete | Chapters 17 to 21, the [SQL course](../../databases/sql/index.md) |
| Technical deep dive | Spark, Delta Lake, streaming, and the projects on your CV, with many "why" and "what happens when" follow-ups | Sections 24.2 to 24.12 | Chapters 3, 4, 11, 22 |
| System design | Design a data pipeline end to end and defend the trade-offs | Sections 24.13 and 24.14 | Chapters 7, 12 to 15 |
| Behavioral | Ownership, incidents, disagreement, prioritization | Four or five true stories told with STAR | 24.1, 24.15 |

### A method that works for any technical question

Interviewers rarely grade the first sentence. They grade how you think. A five-step habit keeps you from rushing
into a wrong answer.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 150" role="img" aria-label="Five boxes in a row joined by arrows: Clarify, Assume, Design, Trade-offs, Verify">
<defs><marker id="a24a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="6" y="30" width="112" height="84" rx="8"/>
<rect x="132" y="30" width="112" height="84" rx="8"/>
<rect x="258" y="30" width="112" height="84" rx="8"/>
<rect x="384" y="30" width="112" height="84" rx="8"/>
<rect x="510" y="30" width="112" height="84" rx="8"/>
<line x1="118" y1="72" x2="130" y2="72" marker-end="url(#a24a)"/>
<line x1="244" y1="72" x2="256" y2="72" marker-end="url(#a24a)"/>
<line x1="370" y1="72" x2="382" y2="72" marker-end="url(#a24a)"/>
<line x1="496" y1="72" x2="508" y2="72" marker-end="url(#a24a)"/>
</g>
<g fill="currentColor" text-anchor="middle" font-size="13">
<text x="62" y="56" font-size="15" font-weight="600">1. Clarify</text>
<text x="62" y="80">inputs, outputs,</text>
<text x="62" y="98">volume, latency</text>
<text x="188" y="56" font-size="15" font-weight="600">2. Assume</text>
<text x="188" y="80">say it aloud,</text>
<text x="188" y="98">write it down</text>
<text x="314" y="56" font-size="15" font-weight="600">3. Design</text>
<text x="314" y="80">simplest version</text>
<text x="314" y="98">that works</text>
<text x="440" y="56" font-size="15" font-weight="600">4. Trade-offs</text>
<text x="440" y="80">cost, latency,</text>
<text x="440" y="98">complexity</text>
<text x="566" y="56" font-size="15" font-weight="600">5. Verify</text>
<text x="566" y="80">tests, failures,</text>
<text x="566" y="98">monitoring</text>
</g>
</svg>
<figcaption>Figure 24.1. A five-step habit for technical and design questions.</figcaption>
</figure>

1. **Clarify.** Ask about inputs (format, volume, arrival pattern), outputs (who reads them, how fresh), and rules
   (duplicates, late data, deletes, history). "How late can an event arrive?" and "Do we need history?" change the
   whole design.
2. **State assumptions.** If the interviewer says "you decide", say what you assume: "I'll assume 50 million events a
   day, dashboards refreshed every 15 minutes, and events up to two days late."
3. **Design the simplest version that works.** Start with one path from source to consumer. Add complexity only
   when a requirement forces it.
4. **Name the trade-offs.** Every choice costs something: a shorter watermark lowers latency and drops more late
   data; a continuous pipeline is fresher and costs more than a triggered one. Saying the cost of your own choice
   is the strongest signal of experience.
5. **Verify.** Say how you would test it (small data, known answers), what happens on failure and rerun
   (idempotency), and how you would notice problems (expectations, alerts, history tables).

For SQL and Python coding questions, the same habit becomes: restate the task, ask about NULLs, ties and
duplicates, write the query, then run it in your head on a three-row example including one edge case.

For behavioral questions use **STAR**: Situation (one sentence), Task (your responsibility), Action (what *you*
did, in detail), Result (a number if you have one, and what you learned). Prepare true stories for: a pipeline
incident you fixed, a disagreement about a design, a time you simplified something, a time you missed a deadline or
made a mistake.

!!! tip "In the interview"
    **"What if I do not know the answer?"** Say what you do know and how you would find out: "I don't remember the
    exact default; I know it exists to protect concurrent readers, and I would check the table property in the
    docs before changing it." Interviewers trust a candidate who marks the edge of their knowledge more than one
    who invents a number.

!!! warning "Old and new product names"
    Databricks has renamed several products, and interviewers most often use the old names: Delta Live Tables,
    `APPLY CHANGES`, Workflows, Asset Bundles, Delta Sharing. Answer with both: "Lakeflow pipelines, formerly Delta
    Live Tables." Every answer in this chapter gives both names; the full list, with the official page that shows
    each rename, is in the cheat sheet (24.16).

## 24.2 Lakehouse and platform basics

*Level: beginner.*

**Q1. What is a data lakehouse, and what problem does it solve?**

??? success "Answer"
    A lakehouse is a data management system that combines the benefits of a data lake (cheap object storage, open
    file formats, any kind of data, direct access for machine learning) with those of a data warehouse (ACID
    transactions, schemas, governance, fast SQL). On Databricks it rests on three pieces: Apache Spark as the
    engine, with compute decoupled from storage; Delta Lake as the storage layer that adds ACID transactions and
    schema enforcement to Parquet files; and Unity Catalog for governance.

    **Why:** before lakehouses, many teams kept raw data in a lake and copied a curated part into a separate
    warehouse for BI. That meant two copies, two security models, extra pipelines and stale reports. A lakehouse
    keeps one copy in open formats and serves BI, data engineering and ML from it.

    **Learn more:** [Chapter 1](01-What-Is-Databricks.md).

**Q2. What are the control plane and the compute plane?**

??? success "Answer"
    The control plane holds the backend services Databricks manages in its own account, including the web
    application. The compute plane is where your data is processed. For classic compute, the compute plane is in
    your own cloud account (the "classic compute plane"); for serverless compute, it runs in a serverless compute
    plane in the Databricks account.

    **Why:** this comes up in security and networking questions ("where does our data get processed?") and explains
    why serverless starts faster: the machines are already in a pool Databricks manages.

    **Learn more:** [Chapter 1](01-What-Is-Databricks.md), [Chapter 6](06-Compute.md).

**Q3. What is Delta Lake in one sentence, and is it the default?**

??? success "Answer"
    Delta Lake is open-source software that extends Parquet data files with a file-based transaction log, giving
    ACID transactions and scalable metadata handling. Yes: Delta Lake is the default format for all operations on
    Databricks, so a plain `CREATE TABLE` creates a Delta table. Unity Catalog managed tables can also use Apache
    Iceberg.

    **Why:** "Delta is just Parquet" is a common wrong answer. The data files are Parquet; the transaction log
    (`_delta_log`) is what makes commits atomic and enables time travel, `MERGE` and schema enforcement.

    **Learn more:** [Chapter 4](04-Delta-Lake.md).

**Q4. Name the main kinds of compute and say when you would use each.**

??? success "Answer"
    - **Serverless compute** for notebooks, jobs and pipelines: Databricks provisions and scales it; nothing to
      configure; fast start.
    - **Classic compute** that you configure yourself: *all-purpose* compute for interactive work and *job compute*
      that exists only for a job run. Both can use standard or dedicated access mode (formerly shared or single user access mode).
    - **SQL warehouses** for SQL and BI workloads (dashboards, ad hoc queries). Photon is their default engine.

    Run scheduled production work on job compute or serverless, not on an all-purpose cluster: the cost guidance
    says non-interactive workloads cost significantly less on job compute than on all-purpose compute.

    **Why:** the follow-up is often a limitation. One worth knowing: in serverless notebooks and jobs, Structured
    Streaming supports only `Trigger.AvailableNow()` and `Trigger.Once()` (Databricks recommends `AvailableNow`).
    A continuously running stream needs classic compute or a pipeline.

    **Learn more:** [Chapter 6](06-Compute.md).

**Q5. What is the difference between standard and dedicated access mode?**

??? success "Answer"
    Standard access mode (formerly *shared*) is multi-user compute; Lakeguard isolates users from each other.
    Dedicated access mode (formerly *single user*) is assigned to one user or one group. For classic compute,
    Databricks recommends standard access mode unless the workload depends on one of its limitations; for example,
    standard compute does not support Databricks Runtime for ML, GPU-enabled compute, or spark-submit tasks.

    **Why:** an interviewer wants to hear that you pick the mode from the workload, and that you know the old names
    still appear in older code and blog posts.

    **Learn more:** [Chapter 6](06-Compute.md).

**Q6. What is Photon, and when does it not help?**

??? success "Answer"
    Photon is Databricks' native, vectorized query engine written in C++. The Spark optimizer (Catalyst) still plans
    the query; Photon takes over execution and processes data in columnar batches. For an operation it does not
    support, it falls back to the Spark runtime transparently. It is enabled on serverless compute, SQL warehouses
    and serverless pipelines, and Databricks enables it by default for classic all-purpose compute, jobs compute and
    classic pipelines.

    It helps little for very short queries: the docs say queries that normally finish in under two seconds see no
    meaningful improvement, because planning and scheduling dominate. It does not support stateful streaming
    (it supports stateless streaming into Delta or Parquet sinks).

    **Why:** "turn on Photon" is not a fix for every slow job. If the time goes into a Python UDF, a skewed join or
    reading millions of tiny files, a faster executor does not remove the cause.

    **Learn more:** [Chapter 6](06-Compute.md), Chapter 22.

**Q7. Managed or external table in Unity Catalog: what is the difference, and which is the default?**

??? success "Answer"
    A **managed** table lets Unity Catalog handle both governance and the files: they live in the managed storage
    location of the schema or catalog, and Databricks maintains them (predictive optimization, automatic file
    sizing). It is the default and recommended table type. An **external** table stores its files at a path you
    choose inside a registered external location; Unity Catalog governs it but does not manage the data's
    lifecycle, layout or optimization.

    Dropping them differs: dropping an external table removes only the metadata and the files stay. Dropping a
    managed table removes it; by default it can be recovered with `UNDROP` for 7 days, after which the files are
    purged.

    **Why:** choose external only when the files must live at a specific path for another system, and remember that
    many automatic features (predictive optimization, automatic liquid clustering) are for managed tables only.

    **Learn more:** [Chapter 5](05-Unity-Catalog.md), Chapter 20.

**Q8. Explain account, workspace, metastore, catalog and schema.**

??? success "Answer"
    The **account** is the top level: identities, workspaces, metastores, billing. A **workspace** is where people
    run notebooks, jobs and pipelines. A Unity Catalog **metastore** is the central governance system for data
    assets; it is attached to workspaces, and one metastore can be linked to several workspaces in the same region
    so they see the same data. Inside it, data uses a three-level namespace: `catalog.schema.object`, for example
    `shop.silver.orders`.

    **Why:** the medallion layers usually map onto this namespace: one catalog per environment or domain, and
    schemas `bronze`, `silver`, `gold` inside it (24.5).

    **Learn more:** Chapter 2, [Chapter 5](05-Unity-Catalog.md).

**Q9. What is Lakeflow? Give the old names too.**

??? success "Answer"
    Lakeflow is the name on Databricks' data engineering products:

    - **Lakeflow Connect**: managed ingestion connectors (for example for enterprise applications such as
      Salesforce and databases such as SQL Server), plus ingestion with SQL and Spark APIs.
    - **Lakeflow pipelines** ("Spark Declarative Pipelines on Lakeflow"), formerly **Delta Live Tables (DLT)**:
      declarative pipelines of streaming tables and materialized views, built on open-source Apache Spark
      Declarative Pipelines. The Python module is `pyspark.pipelines` (formerly `import dlt`).
    - **Lakeflow Jobs**, formerly **Databricks Workflows**: orchestration of tasks.

    **Why:** interviewers who learned the platform a few years ago will say DLT and Workflows. Answer with both names
    once and move on.

    **Learn more:** Chapter 13, Chapter 15.

**Q10. What is predictive optimization?**

??? success "Answer"
    A Databricks service that automatically runs `OPTIMIZE`, `VACUUM` and `ANALYZE` on Unity Catalog managed tables
    when it judges them worthwhile, and collects statistics when data is written. It is enabled by default, runs on
    serverless compute and is billed under a serverless jobs SKU. Databricks recommends it for all managed tables.

    **Why:** it changes the classic answer "schedule a nightly OPTIMIZE and VACUUM job". For managed tables you
    mostly check that it is on and watch its history system table
    (`system.storage.predictive_optimization_operations_history`). One safety detail: even if
    `delta.deletedFileRetentionDuration` is set below 7 days, predictive optimization keeps data files for at least
    7 days when it runs `VACUUM FULL`.

    **Learn more:** Chapter 22.

**Q11. Can other engines read tables managed by Databricks? Why does it matter?**

??? success "Answer"
    Yes. The Delta transaction log is an open protocol that any system can implement. Unity Catalog managed tables
    are reachable from external engines through open APIs: the Unity REST API for Delta clients and the Iceberg
    REST Catalog for Iceberg clients, both with credential vending (temporary, scoped credentials). To share with
    other organizations, OpenSharing (formerly Delta Sharing) shares live data without copying it.

    **Why:** open formats avoid lock-in and let one copy serve several tools. In a design answer, it is the reason
    you do not need to export data for a partner.

    **Learn more:** Chapter 23.

**Q12. What does Databricks add on top of open-source Apache Spark? Give concrete examples.**

??? success "Answer"
    Databricks runs Spark on the Databricks Runtime and adds, among others: Photon; Auto Loader (`cloudFiles`);
    Lakeflow pipelines (formerly Delta Live Tables) with features such as `AUTO CDC` (formerly `APPLY CHANGES`); Unity Catalog; serverless compute; predictive
    optimization; the disk cache (formerly the Delta cache); automatic liquid clustering. Some defaults differ too. In open-source Spark,
    `spark.sql.autoBroadcastJoinThreshold` is 10 MB and the adaptive threshold defaults to the same value; on
    Databricks, AQE uses `spark.databricks.adaptive.autoBroadcastJoinThreshold`, documented at 30 MB.

    **Why:** shows you know which knowledge transfers to any Spark platform and which is Databricks-specific. A good
    example: `AUTO CDC` is part of Lakeflow pipelines and is not supported by open-source Spark Declarative
    Pipelines.

    **Learn more:** [Chapter 3](03-Apache-Spark.md).

## 24.3 Spark internals

*Level: intermediate.*

**Q13. What is lazy evaluation? What is the difference between a transformation and an action?**

??? success "Answer"
    A transformation (`filter`, `select`, `join`, `groupBy`) only adds a step to a plan; it computes nothing. An
    action (`count`, `collect`, `show`, a write) asks for a result, and only then does Spark run jobs. The Spark guide
    puts it this way: transformations "do not compute their results right away"; they are computed "when an action
    requires a result".

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    orders = (spark.range(0, 1_000_000)
              .withColumn("customer_id", (F.col("id") % 1000).cast("int"))
              .withColumn("amount", (F.col("id") % 97).cast("decimal(10,2)")))
    big = orders.filter("amount > 50").select("id", "customer_id", "amount")
    print("type:", type(big).__name__)   # still just a plan
    print("rows:", big.count())          # the action runs the job
    ```

    ```text
    type: DataFrame
    rows: 474214
    ```

    **Why:** laziness lets the optimizer see the whole query before running it, so it can push filters down, prune
    columns and pick join strategies. The practical trap: an error in a transformation (for example a bad cast in
    ANSI mode) only appears when an action runs, sometimes many cells later.

    **Learn more:** [Chapter 3](03-Apache-Spark.md).

**Q14. What is a narrow versus a wide transformation? How do you spot a shuffle in a plan?**

??? success "Answer"
    In a **narrow** transformation each output partition depends on one input partition (`filter`, `select`,
    `withColumn`), so no data moves between machines. A **wide** transformation needs rows with the same key
    together (`groupBy`, `join`, `distinct`, window functions with `PARTITION BY`, `repartition`), so Spark
    shuffles: it redistributes data across partitions, which "typically involves copying data across executors and
    machines". In a physical plan a shuffle shows as an `Exchange` node.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    big.explain()                                                     # narrow
    orders.groupBy("customer_id").agg(F.sum("amount").alias("total")).explain()   # wide
    ```

    ```text
    == Physical Plan ==
    *(1) Project [id#0L, cast((id#0L % 1000) as int) AS customer_id#1, cast((id#0L % 97) as decimal(10,2)) AS amount#2]
    +- *(1) Filter (cast((id#0L % 97) as decimal(10,2)) > 50.00)
       +- *(1) Range (0, 1000000, step=1, splits=2)

    == Physical Plan ==
    AdaptiveSparkPlan isFinalPlan=false
    +- HashAggregate(keys=[customer_id#1], functions=[sum(amount#2)])
       +- Exchange hashpartitioning(customer_id#1, 4), ENSURE_REQUIREMENTS, [plan_id=66]
          +- HashAggregate(keys=[customer_id#1], functions=[partial_sum(amount#2)])
             +- Project [cast((id#0L % 1000) as int) AS customer_id#1, cast((id#0L % 97) as decimal(10,2)) AS amount#2]
                +- Range (0, 1000000, step=1, splits=2)
    ```

    **Why:** shuffles are usually the most expensive part of a job (network, disk, memory). Notice the two
    `HashAggregate` nodes: Spark pre-aggregates on each partition (`partial_sum`) before the shuffle, so less data
    crosses the network. The `4` in `hashpartitioning(customer_id#1, 4)` is the local test setting of
    `spark.sql.shuffle.partitions`.

    **Learn more:** [Chapter 3](03-Apache-Spark.md).

**Q15. What are a job, a stage and a task?**

??? success "Answer"
    A **job** is the parallel computation started by one action (such as `save` or `collect`). Each job is divided
    into **stages**, sets of tasks that depend on each other, like the map and reduce steps of MapReduce; in practice
    a new stage begins at each shuffle. A **task** is the unit of work sent to one executor, and a stage runs one
    task per partition.

    **Why:** this vocabulary is how you read the Spark UI. "The job is slow" becomes "stage 7 has 200 tasks and three
    of them take 20 minutes", which points straight at skew (Q21).

    **Learn more:** [Chapter 3](03-Apache-Spark.md).

**Q16. What decides how many partitions a DataFrame has?**

??? success "Answer"
    When reading files, Spark packs file data into partitions up to `spark.sql.files.maxPartitionBytes` (128 MB by
    default in open-source Spark). After a shuffle, the count starts from `spark.sql.shuffle.partitions` (default
    200). Adaptive query execution then coalesces small post-shuffle partitions toward a target size
    (`spark.sql.adaptive.advisoryPartitionSizeInBytes`, 64 MB on Databricks). On Databricks you can also set
    `spark.sql.shuffle.partitions` to `auto` so the number is chosen from the plan and input size. You can change
    it explicitly with `repartition` or `coalesce`.

    **Why:** too few partitions means big tasks that spill and idle cores; too many means scheduling overhead and,
    when writing, many small files. One streaming catch: you cannot change `spark.sql.shuffle.partitions` between
    restarts from the same checkpoint.

    **Learn more:** [Chapter 3](03-Apache-Spark.md), Chapter 22.

**Q17. `repartition` or `coalesce`: what is the difference?**

??? success "Answer"
    `repartition(n)` always does a full shuffle and can raise or lower the partition count, giving evenly sized
    partitions (optionally by a column). `coalesce(n)` only lowers the count; going from 1000 to 100 partitions it
    does not shuffle, each new partition simply claims 10 old ones. Asking `coalesce` for more partitions leaves the
    count unchanged.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    df = spark.range(0, 1000, numPartitions=8)
    print("start:", df.rdd.getNumPartitions())
    print("repartition(4):", df.repartition(4).rdd.getNumPartitions())
    print("coalesce(2):", df.coalesce(2).rdd.getNumPartitions())
    ```

    ```text
    start: 8
    repartition(4): 4
    coalesce(2): 2
    ```

    **Why:** the trap is `coalesce(1)` before a write "to get one file". The PySpark docs warn that a drastic
    coalesce can make the computation run on fewer nodes than you want (one node for `numPartitions=1`), because the
    upstream work is no longer parallel. `repartition` adds a shuffle but keeps the upstream stages parallel.

    **Learn more:** [Chapter 3](03-Apache-Spark.md).

**Q18. What join strategies does Spark use, and how does it choose?**

??? success "Answer"
    - **Broadcast hash join:** the small side is copied to every executor and the big side is not shuffled. Spark
      chooses it when a side is below `spark.sql.autoBroadcastJoinThreshold` (10 MB by default in open-source Spark)
      or when you give the `BROADCAST` hint.
    - **Sort-merge join:** both sides are shuffled by the key and sorted; the default for two large tables.
    - **Shuffle hash join:** both sides shuffled, a hash table built per partition.
    - **Broadcast nested loop** and **cartesian** joins for non-equality joins.

    Join hints are `BROADCAST`, `MERGE`, `SHUFFLE_HASH` and `SHUFFLE_REPLICATE_NL`. At runtime, AQE can turn a
    sort-merge join into a broadcast join once it sees the real size.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    customers = spark.range(0, 1000).withColumnRenamed("id", "customer_id") \
        .withColumn("country", F.lit("CA"))
    orders.join(F.broadcast(customers), "customer_id").explain()
    ```

    ```text
    == Physical Plan ==
    AdaptiveSparkPlan isFinalPlan=false
    +- Project [customer_id#1, id#0L, amount#2, CA AS country#21]
       +- BroadcastHashJoin [cast(customer_id#1 as bigint)], [customer_id#20L], Inner, BuildRight, false, false
          :- Project [id#0L, cast((id#0L % 1000) as int) AS customer_id#1, cast((id#0L % 97) as decimal(10,2)) AS amount#2]
          :  +- Filter isnotnull(cast((id#0L % 1000) as int))
          :     +- Range (0, 1000000, step=1, splits=2)
          +- BroadcastExchange HashedRelationBroadcastMode(List(input[0, bigint, false]),false), [plan_id=96]
             +- Project [id#19L AS customer_id#20L]
                +- Range (0, 1000, step=1, splits=2)
    ```

    **Why:** the big side (`Range (0, 1000000 ...)`) has no `Exchange` above it: it was not shuffled. That is the
    whole point of a broadcast join. Also notice the `cast(customer_id#1 as bigint)`: the keys had different types,
    so Spark added a cast. Mismatched key types are worth fixing in silver.

    **Learn more:** Chapter 22.

**Q19. A small dimension table is not being broadcast. Why might that be?**

??? success "Answer"
    Check, in order: (1) its estimated size is above the threshold, often because statistics are missing or stale,
    so the optimizer overestimates it; (2) the join type cannot broadcast that side, for example the left side of a
    `LEFT OUTER JOIN`; (3) at runtime AQE refuses to switch when most partitions are empty
    (`spark.sql.adaptive.nonEmptyPartitionRatioForBroadcastJoin`). Fix with fresh statistics (`ANALYZE TABLE`, or
    predictive optimization on managed tables) or a `BROADCAST` hint when you know the table is small.

    **Why:** the Databricks AQE FAQ says a broadcast join planned before the query runs usually beats one AQE
    plans at runtime, because AQE may only switch after it has already shuffled both sides. So a hint is still
    worth adding when you know the data. Never broadcast something large: every executor holds a copy.

    **Learn more:** Chapter 22.

**Q20. What is adaptive query execution (AQE), and what can it not do?**

??? success "Answer"
    AQE re-optimizes a query while it runs, using real statistics collected at the end of each shuffle or broadcast
    exchange. It has four main features: it switches sort-merge joins to broadcast hash joins, coalesces small
    post-shuffle partitions, splits skewed partitions in sort-merge and shuffle hash joins, and propagates empty
    relations. It is on by default (on Databricks and in open-source Spark 4.2).

    It does not apply to streaming queries, it needs at least one exchange or subquery, it does not reorder joins
    (collect statistics for the cost-based optimizer instead), and it never handles skew in broadcast joins.

    **Why:** you see AQE in a plan as `AdaptiveSparkPlan isFinalPlan=false` (Q14's output). `SQL EXPLAIN` does not
    run the query, so it shows only the initial plan; the Spark UI or `DataFrame.explain()` after execution shows
    what AQE actually did.

    **Learn more:** Chapter 22.

**Q21. What is data skew? How do you detect it and fix it?**

??? success "Answer"
    Skew means data is unevenly spread across partitions, usually because a few key values hold most of the rows
    (a "guest" customer, a NULL key, one huge seller). Symptom: a stage that sits at "197 of 200 tasks" while three
    tasks run for a long time. Confirm in the Spark UI: sort the stage's tasks by duration or input size; one or a
    few are far larger than the median.

    Fixes, roughly in order:

    1. Let AQE skew handling work. It treats a partition as skewed when it is larger than 5 times the median
       partition size **and** larger than 256 MB (the defaults), and only in sort-merge and shuffle hash joins.
       It cannot split the right side of a `LEFT OUTER` join, and does nothing for `FULL OUTER`.
    2. Broadcast the small side, which removes the shuffle entirely.
    3. Handle the hot key separately: filter out NULL keys that will never match, or process the top key in its own
       query and `UNION ALL` the results.
    4. Salt the key: add a random number `0..N-1`, aggregate or join on `(key, salt)`, then combine.

    Two-step aggregation with a salt gives the same totals:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    SALT = 8
    salted = skewed.withColumn("salt", (F.rand(seed=1) * SALT).cast("int"))
    partial = salted.groupBy("customer_id", "salt").count()          # hot key spread over 8 tasks
    final = partial.groupBy("customer_id").agg(F.sum("count").alias("count"))
    final.orderBy(F.desc("count")).show(3)
    ```

    ```text
    +-----------+-----+
    |customer_id|count|
    +-----------+-----+
    |          7|90000|
    |         39| 2000|
    |         19| 2000|
    +-----------+-----+
    only showing top 3 rows
    ```

    **Why:** customer 7 holds 90% of the rows. Without the salt, one task would count all 90,000; with it, eight
    tasks share the work and a second, tiny aggregation adds the partial counts. The Databricks skew hint page is marked
    as retired documentation, and the AQE page says AQE skew handling "usually performs better than the skew join
    hint".

    **Learn more:** Chapter 22.

**Q22. `cache()` or the Databricks disk cache: what is the difference, and when would you cache?**

??? success "Answer"
    `df.cache()`/`persist()` is the Apache Spark cache: you call it in code, it keeps blocks of a DataFrame in memory
    (or disk, depending on the storage level), it is lazy (filled by the next action) and you release it with
    `unpersist()`. The Databricks **disk cache** (formerly Delta cache) is automatic: when a worker reads a Parquet
    or Delta file from cloud storage it keeps a local copy on its SSD, and it detects file changes so it never serves
    stale data. Databricks recommends the disk cache for repeated reads of Parquet and Delta data.

    Cache a DataFrame only when you reuse an expensive result several times in one job, and unpersist it after.
    Two Databricks details: `CACHE SELECT` is ignored on SQL warehouses and Databricks Runtime 14.2 and above, and on
    serverless compute `df.cache()` works differently (it materializes a snapshot; a Public Preview feature).

    **Why:** caching everything wastes memory and can make jobs slower. Caching is also lost when a worker is
    decommissioned, for example during autoscaling.

    **Learn more:** Chapter 22.

**Q23. Why can `collect()` crash a job, and what do you use instead?**

??? success "Answer"
    `collect()` brings every row of the DataFrame to the driver, a single machine. On a large DataFrame the driver
    runs out of memory; the Spark guide warns exactly about this and suggests `take()` when you only need a few rows.
    Instead: aggregate in Spark and collect only the small result; use `take(n)`/`limit(n)`; write the result to a
    table; or use `display()` in a notebook, which shows a sample.

    **Why:** the same applies to `toPandas()`, and to loops that call `collect()` on each item. A driver
    out-of-memory error is almost always caused by code, not by data size alone (Q127).

    **Learn more:** [Chapter 3](03-Apache-Spark.md).

**Q24. Why are Python UDFs slow, and what are the alternatives?**

??? success "Answer"
    A plain Python UDF is a black box to the optimizer and runs in a separate Python process, so each row has to be
    serialized from the JVM to Python and back. Built-in functions run inside the engine, are optimized by Catalyst
    and can be executed by Photon. Alternatives in order of preference: (1) a built-in function or SQL expression
    (including higher-order functions such as `transform`, Q107); (2) a pandas UDF, which Spark executes using Arrow
    to transfer data in batches and pandas to work on it (vectorized); (3) a SQL UDF.

    **Why:** an interviewer often shows a UDF that does `upper()` or parses a date and asks what you would change.
    The answer is: delete it and use the built-in.

    **Learn more:** Chapter 19, Chapter 21.

**Q25. What happens between writing a DataFrame query and running it?**

??? success "Answer"
    Spark builds an unresolved logical plan from your code, resolves names and types against the catalog, applies
    rule-based optimizations (filter pushdown, column pruning, constant folding), chooses a physical plan (join
    strategies, aggregation methods), generates code, and runs it as jobs, stages and tasks. With AQE the physical
    plan can change during execution. `df.explain()` shows the plan; `explain("formatted")` or `explain(True)` show
    more detail.

    **Why:** this is why the DataFrame API and SQL perform the same: both become the same plan. It also explains why
    a filter written after a join can still be applied before it.

    **Learn more:** [Chapter 3](03-Apache-Spark.md).

**Q26. What runs on the driver and what runs on the executors?**

??? success "Answer"
    The driver runs your program's main code, builds plans, schedules tasks and receives results of actions such as
    `collect()`. Executors are processes on worker nodes that run tasks and keep data in memory or on disk. Code
    inside transformations (for example a UDF, or `foreach`) runs on the executors.

    **Why:** two classic bugs follow from this. A `print` inside `foreach` prints to the executor logs, not your
    notebook. A Python list appended to inside a UDF stays empty on the driver.

    **Learn more:** [Chapter 3](03-Apache-Spark.md).

**Q27. What is the difference between partition pruning and data skipping?**

??? success "Answer"
    **Partition pruning** works on partitioned tables: a filter on the partition column skips whole directories.
    **Data skipping** works at file level: Delta records statistics (such as minimum and maximum values) per data
    file in the transaction log, by default for the first 32 columns, and a query skips files whose value ranges
    cannot match the filter. Liquid clustering and Z-ordering make data skipping effective by putting similar values
    in the same files.

    **Why:** this is why Databricks now recommends liquid clustering over partitioning for most tables (and not
    partitioning tables under 1 TB at all): you get file skipping on the columns you filter by, without the
    small-file problem of over-partitioning. Filtering on a column that has no statistics (beyond the first 32)
    gets no skipping, except that on managed tables predictive optimization also collects statistics on
    frequently filtered columns beyond the first 32.

    **Learn more:** Chapter 22.

**Q28. What is spill, and how do you reduce it?**

??? success "Answer"
    Spill happens when a task's in-memory data structures for a shuffle, sort or aggregation do not fit in memory, so
    Spark writes them to local disk, adding disk I/O and garbage collection. The Spark UI shows "spill (memory)" and
    "spill (disk)" per stage. Reduce it by making partitions smaller (more shuffle partitions, or let AQE size them),
    fixing skew so one task is not huge, selecting fewer columns earlier, or using workers with more memory.

    **Why:** spill is often the hidden cause of a stage that is slow but not obviously skewed. It is also a reason
    the default 200 shuffle partitions is wrong for very large inputs.

    **Learn more:** Chapter 22.

## 24.4 Delta Lake

*Level: intermediate.*

**Q29. How does the Delta transaction log work?**

??? success "Answer"
    Every Delta table has a `_delta_log` directory next to its Parquet data files. Each commit writes one JSON file
    named with the next version number, zero-padded to 20 digits (`00000000000000000000.json`, then `...01.json`).
    A commit lists *actions*: files added, files removed, metadata (schema, properties), protocol changes. The
    current state of the table is the set of data files that the log says are valid. Periodically a checkpoint
    (a Parquet file, for example `00000000000000000042.checkpoint.parquet`) stores the full replay of all actions
    up to that version, so a reader starts from the newest checkpoint and applies only the JSON commits after it.

    **Why:** the commit file is the unit of atomicity. Data files written by a failed job are never listed in the
    log, so readers never see them; `VACUUM` later deletes them. Time travel is just "rebuild the state as of an
    older version", which is why it needs both the old log entries and the old data files.

    **Learn more:** [Chapter 4](04-Delta-Lake.md).

**Q30. How does Delta Lake provide each of the ACID properties?**

??? success "Answer"
    - **Atomicity:** a transaction becomes visible only when its entry is committed to the log; until then its data
      files are not part of the table.
    - **Consistency:** optimistic concurrency control. A writer reads the latest version (if needed), writes new
      files, then validates that nothing conflicting was committed meanwhile; if something was, it fails with a
      concurrent modification exception instead of corrupting the table.
    - **Isolation:** snapshot isolation for reads and write-serializable isolation for writes by default.
    - **Durability:** data and log live in cloud object storage, which is highly durable.

    By default each SQL statement is its own atomic transaction on one table. Databricks also supports
    multi-statement, multi-table transactions with `BEGIN ATOMIC ... END;` on tables with catalog commits enabled.

    **Why:** there are no locks, so readers never block writers and deadlock cannot happen. The cost is that two
    conflicting writers cannot both win (Q31).

    **Learn more:** [Chapter 4](04-Delta-Lake.md).

**Q31. Two jobs write to the same Delta table at the same time. What happens?**

??? success "Answer"
    Both write their data files. When each tries to commit, Delta checks whether the other's committed changes
    conflict with what it read. Under the default WriteSerializable isolation level, blind appends (`INSERT`s that
    do not read the table) cannot conflict with each other. Operations that read and rewrite the same data (two
    `MERGE`s, `UPDATE` plus `DELETE` on the same rows) can conflict, and the later commit fails with an exception
    such as `ConcurrentAppendException`; the table is never corrupted. When an `INSERT` and a `MERGE` collide, the
    `MERGE` is the one that fails, so retry logic belongs on the `UPDATE`, `DELETE` or `MERGE`. A metadata change
    (for example `ALTER TABLE`, or a write that changes the schema) can make all concurrent writes fail, including
    `INSERT`s.

    Fixes: make the writers touch disjoint data and say so in the predicate (for example a date or region condition
    in the `MERGE ON` clause); serialize the jobs in one Lakeflow Job (formerly Databricks Workflows); retry the failed one; on Databricks Runtime 14.3 LTS
    and above, tables without partitions and with deletion vectors enabled get row-level concurrency, which detects
    conflicts per row instead of per file.

    **Why:** the interviewer is checking you know Delta uses optimistic concurrency, not locks, and that "add a
    retry" is only part of the answer.

    **Learn more:** [Chapter 4](04-Delta-Lake.md), Chapter 22.

**Q32. What is time travel, and what limits how far back you can go?**

??? success "Answer"
    You can query an older version of a table by version number or timestamp:

    The table had 3 rows at version 1; a `DELETE` at version 2 left 1.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT count(*) AS n FROM silver_orders VERSION AS OF 1;
    ```

    ```text
    +---+
    |n  |
    +---+
    |3  |
    +---+
    ```

    `TIMESTAMP AS OF '2026-03-01'` works the same way. Databricks also accepts `silver_orders@v1` and a
    `@yyyyMMddHHmmssSSS` timestamp; open-source Spark 4.2 rejects the `@v` form with a parse error (tried here).

    Two table properties set the limits: `delta.logRetentionDuration` (how long history is kept, default 30 days) and
    `delta.deletedFileRetentionDuration` (how old unreferenced data files must be before `VACUUM` deletes them,
    default 7 days). To read a version you need both its log entries and its data files. In Databricks Runtime
    18.0 and above, time travel to a version older than `deletedFileRetentionDuration` is blocked.

    **Why:** Databricks says not to use table history as a long-term backup. If you need 30 days of time travel,
    raise `deletedFileRetentionDuration` to 30 days and accept the extra storage.

    **Learn more:** [Chapter 4](04-Delta-Lake.md), Chapter 20.

**Q33. What is the difference between `RESTORE` and a time travel query?**

??? success "Answer"
    A time travel query only reads an old version. `RESTORE TABLE t TO VERSION AS OF n` (or `TIMESTAMP AS OF`) makes
    an old version current again by committing a new version that adds back the old files and removes the newer
    ones. History is kept, so you can even restore "forward" again.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    RESTORE TABLE silver_orders TO VERSION AS OF 1;
    ```

    ```text
    +------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
    |table_size_after_restore|num_of_files_after_restore|num_removed_files|num_restored_files|removed_files_size|restored_files_size|
    +------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
    |3560                    |2                         |1                |2                 |1788              |3560               |
    +------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
    ```

    **Why:** `RESTORE` is all or nothing for the table. To undo a mistake that affected only some rows while keeping
    later good writes, insert or merge the missing rows back from the old version instead (Q124).

    **Learn more:** Chapter 20.

**Q34. What does `VACUUM` do, and what are the risks?**

??? success "Answer"
    `VACUUM` deletes data files that the current table version no longer references and that are older than the
    retention threshold (7 days by default). It also removes files left by failed transactions. It does not delete
    log files; those are cleaned up automatically after checkpoints. `VACUUM t DRY RUN` lists what would be deleted.
    On Databricks, `VACUUM t LITE` (Public Preview) uses the transaction log instead of listing the directory,
    which is cheaper on large tables.

    The risks: after `VACUUM`, time travel to versions whose files were removed is gone; and with a too-short
    retention it could delete files a long-running writer has not committed yet. A safety check blocks short
    retention:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    VACUUM silver_orders RETAIN 0 HOURS;
    ```

    ```text
    ERROR: [DELTA_VACUUM_RETENTION_PERIOD_TOO_SHORT] The specified VACUUM retention period is too low and may corrupt this Delta table if any writes are in progress.
    ```

    **Why:** two more traps. `VACUUM` deletes everything in the table directory that Delta does not manage, except
    directories starting with `_` or `.`, so never keep a streaming checkpoint in the table folder unless it is named
    like `_checkpoints`. And on Unity Catalog managed tables predictive optimization runs `VACUUM` for you.

    **Learn more:** [Chapter 4](04-Delta-Lake.md), Chapter 22.

**Q35. What does `OPTIMIZE` do?**

??? success "Answer"
    `OPTIMIZE` rewrites many small data files into fewer larger ones (bin-packing compaction). On a table with liquid
    clustering it also groups data by the clustering keys; on a table without clustering, `ZORDER BY (cols)` can
    co-locate values. It does not change the data, so readers see the same results before and after (snapshot
    isolation), and running it twice has no extra effect. `OPTIMIZE t WHERE <partition predicate>` limits it to some
    partitions; `OPTIMIZE t FULL` (Databricks Runtime 16.0 and above) forces reclustering of all data.

    Twenty single-row inserts made twenty files:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    sql("DESCRIBE DETAIL bronze_events").select("numFiles").show()   # before: 20
    sql("OPTIMIZE bronze_events")
    sql("DESCRIBE DETAIL bronze_events").select("numFiles").show()   # after
    ```

    ```text
    +--------+
    |numFiles|
    +--------+
    |      20|
    +--------+

    +--------+
    |numFiles|
    +--------+
    |       1|
    +--------+
    ```

    **Why:** the old files are not deleted by `OPTIMIZE`; they stay for time travel until `VACUUM` removes them.
    Databricks suggests starting with a daily `OPTIMIZE` if you schedule it yourself, or letting predictive
    optimization decide for managed tables. `OPTIMIZE` on a table used as a streaming source does not affect the
    stream.

    **Learn more:** Chapter 22.

**Q36. Partitioning, Z-ordering or liquid clustering: which and why?**

??? success "Answer"
    Databricks recommends **liquid clustering** for all new tables, including streaming tables and materialized
    views. It replaces partitioning and `ZORDER`: data is organized by clustering keys (up to four), you can change
    the keys later without rewriting existing data, and with `CLUSTER BY AUTO` on Unity Catalog managed tables
    Databricks chooses the keys from query patterns. Clustering cannot be combined with partitioning or `ZORDER` on
    the same table.

    Partitioning still has a place only for very large tables: the guidance is not to partition tables under 1 TB,
    and to make sure each partition holds at least 1 GB. Z-ordering is the older technique for tables without
    liquid clustering.

    **Why:** over-partitioning (by date *and* customer, for example) creates thousands of tiny files and slow
    queries. Liquid clustering helps exactly where partitioning fails: high-cardinality filter columns, skewed
    data, changing access patterns and concurrent writers.

    *Databricks only, not run here. Syntax from [Use liquid clustering for tables](https://docs.databricks.com/aws/en/delta/clustering).*

    ```sql
    CREATE TABLE shop.silver.orders (order_id INT, customer_id INT, order_ts TIMESTAMP)
    CLUSTER BY (customer_id, order_ts);

    ALTER TABLE shop.silver.orders CLUSTER BY AUTO;   -- managed tables only
    ```

    **Learn more:** Chapter 22.

**Q37. How do you choose clustering keys, and what happens when you change them?**

??? success "Answer"
    Pick the columns that appear most often in query filters (and in `MERGE` join conditions). If two columns are
    highly correlated, keep only one. Use at most four keys; on tables under about 10 TB, more keys can make
    single-column filters slower. Keys need statistics, and by default Delta collects statistics only for the first
    32 columns.

    Changing keys with `ALTER TABLE t CLUSTER BY (new_cols)` is a metadata change: existing data is not rewritten,
    new writes and later `OPTIMIZE` runs cluster by the new keys, and `OPTIMIZE t FULL` reclusters everything.

    **Why:** that flexibility is the main advantage over partitioning, where changing the partition column means
    rewriting the whole table.

    **Learn more:** Chapter 22.

**Q38. What are deletion vectors?**

??? success "Answer"
    Without deletion vectors, changing one row means rewriting the whole Parquet file that contains it. With
    deletion vectors, `DELETE`, `UPDATE` and `MERGE` mark rows as removed in a small metadata file, and readers skip
    those rows at query time. Writes become much cheaper. The rows are physically removed later by `OPTIMIZE`,
    `REORG TABLE ... APPLY (PURGE)`, or auto compaction. You enable them with the table property
    `delta.enableDeletionVectors = true`, and a workspace setting can enable them for new tables.

    **Why:** two follow-ups. Enabling them upgrades the table protocol, so old clients that do not support deletion
    vectors cannot read the table. And for a GDPR erasure, a soft delete is not enough: run
    `REORG TABLE ... APPLY (PURGE)` and then `VACUUM` once the retention period has passed (Q131).

    **Learn more:** Chapter 22.

**Q39. What is Change Data Feed (CDF), and what does it return?**

??? success "Answer"
    CDF exposes row-level changes between versions of a table. Each change row carries the data plus
    `_change_type` (`insert`, `update_preimage`, `update_postimage`, `delete`), `_commit_version` and
    `_commit_timestamp`. You read it with `table_changes('t', start_version)` in SQL or
    `spark.read.option("readChangeFeed", "true")` (or `readStream`) in Python. The classic ("legacy") form is turned on
    per table with `delta.enableChangeDataFeed = true`; Databricks also has an automatic form (Databricks Runtime 19
    and above, Unity Catalog tables with row tracking) that computes changes at read time.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    ALTER TABLE silver_orders SET TBLPROPERTIES (delta.enableChangeDataFeed = true);
    UPDATE silver_orders SET status = 'CANCELLED' WHERE order_id = 1004;
    SELECT order_id, status, _change_type, _commit_version
    FROM table_changes('silver_orders', 7) ORDER BY _commit_version, _change_type;
    ```

    ```text
    +--------+---------+----------------+---------------+
    |order_id|status   |_change_type    |_commit_version|
    +--------+---------+----------------+---------------+
    |1004    |CANCELLED|update_postimage|7              |
    |1004    |PLACED   |update_preimage |7              |
    +--------+---------+----------------+---------------+
    ```

    **Why:** CDF is how you propagate updates and deletes incrementally from silver to gold, instead of re-reading
    the whole table. Databricks recommends streaming from a table's change feed rather than from the table itself
    when the table receives updates. CDF files live in `_change_data` and are removed by `VACUUM`, so CDF history is
    limited like time travel.

    **Learn more:** [Chapter 9](09-Building-Silver.md), Chapter 20.

**Q40. What is the difference between schema enforcement and schema evolution?**

??? success "Answer"
    **Schema enforcement** (on by default for Delta tables): every inserted column must exist in the target, and
    types must match; Databricks attempts a safe cast and otherwise rejects the write. **Schema evolution** lets a
    write change the table schema, for example to add new columns: per write with `.option("mergeSchema", "true")`,
    with `MERGE WITH SCHEMA EVOLUTION` (and `INSERT WITH SCHEMA EVOLUTION` in Databricks Runtime 18.1 and above), or
    session-wide with the legacy setting `spark.databricks.delta.schema.autoMerge.enabled`. Databricks recommends
    enabling it per operation, not per session.

    An extra column `channel` is rejected, then accepted with `mergeSchema`:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    new_cols = spark.createDataFrame([(1005, 9, "PLACED", "web")],
        "order_id INT, customer_id INT, status STRING, channel STRING")
    new_cols.write.format("delta").mode("append").saveAsTable("silver_orders")      # fails
    new_cols.write.format("delta").mode("append").option("mergeSchema", "true") \
        .saveAsTable("silver_orders")                                               # works
    ```

    ```text
    ERROR: [DELTA_METADATA_MISMATCH] A metadata mismatch was detected when writing to the Delta table.
    +--------+---------+-------+
    |order_id|status   |channel|
    +--------+---------+-------+
    |1001    |PLACED   |NULL   |
    |1002    |DELIVERED|NULL   |
    |1003    |SHIPPED  |NULL   |
    |1004    |PLACED   |NULL   |
    |1005    |PLACED   |web    |
    +--------+---------+-------+
    ```

    **Why:** enforcement protects silver and gold from surprise columns; evolution is a deliberate choice. Note that
    any schema change ends streams that read the table; they must be restarted.

    **Learn more:** [Chapter 4](04-Delta-Lake.md), [Chapter 9](09-Building-Silver.md).

**Q41. A column must change from `INT` to `BIGINT`. How do you do it without rewriting the table?**

??? success "Answer"
    Use type widening (Databricks Runtime 15.4 LTS and above): set `delta.enableTypeWidening = true`, then
    `ALTER TABLE t ALTER COLUMN c TYPE BIGINT`. No data files are rewritten. Supported changes include `BYTE` to
    `SHORT`/`INT`/`BIGINT`, `SHORT` to `INT`/`BIGINT`, `INT` to `BIGINT`, `FLOAT` to `DOUBLE`, `DECIMAL` to a larger
    precision and scale, and `DATE` to `TIMESTAMP_NTZ`. With type widening enabled, schema evolution can also widen
    types automatically during a `MERGE` or `mergeSchema` write.

    **Why:** enabling it upgrades the table protocol, and afterwards only Databricks Runtime 15.4 LTS and above can
    read the table, which matters if other engines read it. A change that is not widening (for example `STRING` to
    `INT`) still needs a rewrite with `overwriteSchema`.

    **Learn more:** [Chapter 4](04-Delta-Lake.md).

**Q42. How do you rename or drop a column on a Delta table?**

??? success "Answer"
    Enable column mapping on the table, then `ALTER TABLE t RENAME COLUMN old TO new` or
    `ALTER TABLE t DROP COLUMN c`. With column mapping these are metadata-only operations: no data is rewritten.
    Without column mapping you would rewrite the table with `overwriteSchema`.

    **Why:** a dropped column with column mapping is a "soft delete": the old values remain in the files until
    `REORG TABLE ... APPLY (PURGE)` rewrites them. That matters for sensitive data.

    **Learn more:** [Chapter 4](04-Delta-Lake.md).

**Q43. A `MERGE` fails with "multiple source rows matched". Why, and how do you fix it?**

??? success "Answer"
    The source has more than one row for the same key, so the update is ambiguous: which source row should win?
    Delta raises `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`. Fix the source: keep one row per key,
    usually the latest by an ordering column. (An unconditional `DELETE` is allowed with multiple matches, because it
    is not ambiguous.)

    Order 1002 appears twice in `updates`:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    MERGE INTO silver_orders t USING updates s ON t.order_id = s.order_id
    WHEN MATCHED THEN UPDATE SET t.status = s.status;
    -- ERROR: [DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE] Cannot perform Merge as
    --        multiple source rows matched and attempted to modify the same ...

    MERGE INTO silver_orders t
    USING (SELECT * FROM updates
           QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY ingest_ts DESC) = 1) s
    ON t.order_id = s.order_id
    WHEN MATCHED THEN UPDATE SET t.status = s.status
    WHEN NOT MATCHED THEN INSERT (order_id, status) VALUES (s.order_id, s.status);
    ```

    ```text
    +-----------------+----------------+----------------+-----------------+
    |num_affected_rows|num_updated_rows|num_deleted_rows|num_inserted_rows|
    +-----------------+----------------+----------------+-----------------+
    |2                |1               |0               |1                |
    +-----------------+----------------+----------------+-----------------+
    ```

    **Why:** the deeper point is that `MERGE` only deduplicates *against the target*; duplicates *within* the new
    batch must be removed first. The same error appears in streaming `foreachBatch` merges when one micro-batch holds
    two events for one key.

    **Learn more:** [Chapter 9](09-Building-Silver.md), [SQL course: MERGE](../../databases/sql/17-Insert-Update-Delete-Merge.md).

**Q44. What makes a `MERGE` slow, and how do you speed it up?**

??? success "Answer"
    A `MERGE` must find the target files that contain matching keys and rewrite them. It is slow when it scans the
    whole target, when it rewrites many large files to change a few rows, or when the source has skew. Speed-ups:

    1. Add a selective condition to the `ON` clause (for example `AND t.order_date >= current_date() - INTERVAL 7 DAYS`)
       so fewer files are candidates.
    2. Cluster the target on the merge key (liquid clustering) so matching rows sit in few files.
    3. Enable deletion vectors so changed rows are marked, not whole files rewritten.
    4. Keep the source small: only new or changed rows, deduplicated.
    5. If you use `WHEN NOT MATCHED BY SOURCE`, give it a condition; otherwise it can touch the whole target.

    Databricks' optimized `MERGE` implementation, low shuffle merge, is on by default: it processes unmodified rows
    separately so they are not shuffled and the existing layout is preserved.

    **Why:** the interviewer wants a method (measure, then reduce the files touched), not a magic setting.

    **Learn more:** Chapter 22.

**Q45. Shallow clone or deep clone?**

??? success "Answer"
    A **deep clone** copies data and metadata into an independent table (including stream metadata, so a stream can
    continue on the clone). A **shallow clone** copies only metadata and points at the source's data files, so it
    is fast and cheap. Use a shallow clone to test a risky change on production-like data; use a deep clone for an
    independent copy, for example a backup or a migration. To give another organization read access, Databricks
    recommends OpenSharing (formerly Delta Sharing) rather than clones.

    **Why:** a shallow clone depends on the source's files, so `VACUUM` on the source can affect it (Unity Catalog
    has its own rules for managed shallow clones).

    **Learn more:** Chapter 20.

## 24.5 Medallion architecture

*Level: beginner to intermediate.*

**Q46. Explain the medallion architecture.**

??? success "Answer"
    It is a data design pattern that organizes a lakehouse into layers of increasing quality: **bronze** (raw data
    as ingested), **silver** (cleaned, validated, deduplicated, conformed) and **gold** (business-level models and
    aggregates for BI, ML and applications). Data moves bronze to silver to gold, so it is also called a
    multi-hop architecture. Databricks recommends it as a best practice, not a requirement.

    | | Bronze | Silver | Gold |
    | --- | --- | --- | --- |
    | Work done | Raw ingestion | Cleaning and validation | Dimensional modeling and aggregation |
    | Main users | Data engineers, data operations, compliance and audit | Data engineers, analysts, data scientists | Business analysts, BI developers, ML engineers, executives |

    **Why:** each layer has one job, which makes failures easy to locate and lets you rebuild a later layer from an
    earlier one without going back to the source.

    **Learn more:** [Chapter 7](07-Medallion-Architecture.md).

**Q47. What belongs in bronze, and why store fields as strings or `VARIANT` there?**

??? success "Answer"
    Bronze keeps the raw state of each source, appended incrementally, with as little cleanup as possible, plus
    metadata columns such as the source file name (`_metadata.file_name`) and ingestion time. It is the single
    source of truth for reprocessing and audit, and it is meant for the pipelines that build silver, not for
    analysts. Databricks recommends storing most fields as `STRING`, `VARIANT` or binary in bronze, so an unexpected
    schema change does not drop data.

    **Why:** if bronze casts `amount` to `DECIMAL` and a source starts sending `"12.50 CAD"`, the row fails or the
    value becomes NULL and is lost. Kept as text, it can be fixed in silver later.

    **Learn more:** [Chapter 7](07-Medallion-Architecture.md), [Chapter 8](08-Bronze-Ingestion.md).

**Q48. The source system keeps all its data. Why keep a bronze copy at all?**

??? success "Answer"
    Because you cannot count on replaying the source. Kafka topics have retention limits, files get deleted by
    lifecycle rules, and databases overwrite rows. The Lakeflow docs spell out the consequence: a full refresh of a
    streaming table reprocesses only what the source still has, so records no longer in a Kafka topic or no longer
    in the source directory are dropped from the target. A bronze table lets you rebuild silver and gold after a bug
    fix or a logic change, and shows exactly what you received and when.

    **Why:** "replay from bronze" is the safety net in almost every troubleshooting answer.

    **Learn more:** [Chapter 7](07-Medallion-Architecture.md).

**Q49. What happens in the silver layer?**

??? success "Answer"
    Schema enforcement and type casting, handling of NULLs and missing values, deduplication, resolving
    out-of-order and late-arriving data, data quality checks (with quarantine of bad records), controlled schema
    evolution, and joins that enrich records. Silver should always contain at least one validated, non-aggregated
    representation of each record. Modeling often starts here too: flattening nested data or keeping it as
    `VARIANT`, structs, maps and arrays.

    **Why:** silver is "the trustworthy detailed data". Analysts and data scientists who need row-level detail use
    silver; aggregated business views go to gold.

    **Learn more:** [Chapter 9](09-Building-Silver.md).

**Q50. Why not write cleaned data straight from ingestion into silver?**

??? success "Answer"
    Databricks advises against it: writing directly from ingestion into silver introduces failures from schema
    changes or corrupt records in the source. With bronze in between, ingestion only has to land the data, which
    almost never fails, and the cleaning logic can fail, be fixed and rerun from bronze without losing anything.

    **Why:** it separates "did we receive it?" from "is it valid?". Those are different failure modes with different
    owners.

    **Learn more:** [Chapter 7](07-Medallion-Architecture.md).

**Q51. Should silver read bronze as a stream or as a batch?**

??? success "Answer"
    Assuming bronze is append-only, read it as a stream (Structured Streaming, a streaming table, or a stream with an
    `availableNow` trigger on a schedule). Each run then processes only new records, tracked by a checkpoint. Batch
    reads fit small datasets such as small dimension tables.

    **Why:** a stream does not mean "always running". `trigger(availableNow=True)` in a daily job gives incremental
    processing with batch-like cost. The trap: a streaming read of a table that receives updates or deletes fails
    (Q82).

    **Learn more:** [Chapter 9](09-Building-Silver.md), [Chapter 11](11-Structured-Streaming.md).

**Q52. What does the gold layer contain, and how is it modeled?**

??? success "Answer"
    Gold holds business-aligned datasets: dimensional models (facts and dimensions in a star schema) and
    aggregates such as daily sales by store, built for dashboards, reports, ML features and applications. It
    usually has fewer, smaller, heavily used tables, optimized for query speed; materialized views are a common way
    to keep aggregates fresh. Some organizations have several gold areas by domain (finance, HR).

    **Why:** expect a follow-up on modeling: grain of a fact table, conformed dimensions, SCD Type 2 dimensions,
    and why gold avoids huge historical detail (that stays in silver).

    **Learn more:** Chapter 10, [SQL course: data modelling](../../databases/sql/19-Data-Modelling.md).

**Q53. How do the layers map onto Unity Catalog?**

??? success "Answer"
    A common layout is one catalog per environment or domain and one schema per layer, for example `shop.bronze`,
    `shop.silver`, `shop.gold`; the Databricks medallion page uses `ops.bronze`, `ops.silver`, `ops.gold`. Privileges
    follow the layers: engineers and service principals write bronze and silver; analysts get `SELECT` on gold (and
    maybe silver); almost nobody reads bronze. Unity Catalog best practices suggest catalogs that correspond to an
    environment, team or business unit, and catalogs bound to specific workspaces when isolation is needed.

    **Why:** the layout makes privileges simple: grant on the schema and every current and future table inherits it.

    **Learn more:** [Chapter 5](05-Unity-Catalog.md), [Chapter 7](07-Medallion-Architecture.md).

**Q54. What are common medallion anti-patterns?**

??? success "Answer"
    From experience, the mistakes that come up most:

    - Cleaning or filtering in bronze, so the raw record is lost.
    - Analysts querying bronze because silver is late or missing fields.
    - Silver that only holds aggregates, so detail has to be rebuilt from bronze.
    - Full recomputation of every layer every day when incremental processing would do.
    - No business key or no deduplication rule, so duplicates flow to gold.
    - One gold table per dashboard with copied logic, instead of shared facts and dimensions.
    - Extra layers added by habit ("platinum", "silver2") that add latency and cost without a clear job.
    - Business logic hidden in the BI tool instead of gold.

    **Why:** naming what goes wrong shows you have run such a system, not only read about it.

    **Learn more:** [Chapter 7](07-Medallion-Architecture.md).

**Q55. When might you not use a full bronze-silver-gold design?**

??? success "Answer"
    The pattern is a recommendation, not a rule. Fewer layers can be right when the source is already clean and
    modeled (for example a curated table shared with you), when a small team needs one simple report, or for an
    operational low-latency path where every hop adds delay. Even then, keep a raw landing copy if the source cannot
    be replayed (Q48).

    **Why:** interviewers like a candidate who can say "it depends" and then say on what.

    **Learn more:** [Chapter 7](07-Medallion-Architecture.md).

**Q56. Where do data quality checks go in a medallion pipeline?**

??? success "Answer"
    - **Bronze:** structural checks only: was the file parseable, how many records have `_rescued_data`, did the
      expected files arrive. Never drop data here.
    - **Silver:** record-level rules (not NULL keys, valid ranges, valid status values), with bad rows quarantined to
      a side table rather than silently dropped. In Lakeflow pipelines (formerly Delta Live Tables) these are expectations (warn, drop, fail).
    - **Gold:** business reconciliation: totals match the source system, no duplicate keys in dimensions, every fact
      row finds its dimension row.

    **Why:** the quarantine pattern keeps bad rows visible and fixable; a dropped row is a silent data loss.

    **Learn more:** Chapter 14.

**Q57. How do you deduplicate when building silver?**

??? success "Answer"
    Define the business key (for example `order_id`) and the rule that picks the winner (latest `ingest_ts`, or the
    highest source sequence number). Then: deduplicate the new batch within itself with
    `QUALIFY row_number() OVER (PARTITION BY key ORDER BY ts DESC) = 1`, and apply it to silver with `MERGE` so it is
    also deduplicated against existing rows. For pure "insert if new" logs, an insert-only `MERGE`
    (`WHEN NOT MATCHED THEN INSERT`) is enough. In a stream, `dropDuplicatesWithinWatermark` removes duplicates that
    arrive within the watermark.

    **Why:** the Delta docs make the key point: merge deduplicates new data against the table, but duplicates inside
    the new dataset are inserted unless you remove them first.

    **Learn more:** [Chapter 9](09-Building-Silver.md), [SQL course: duplicates](../../databases/sql/22-Duplicates-and-Incremental-Loads.md).

**Q58. How do you handle late and out-of-order data across the layers?**

??? success "Answer"
    - **Bronze:** append everything, late or not, with the event time and the ingestion time.
    - **Silver:** apply changes in event order, not arrival order. With `MERGE`, update only when the incoming
      record is newer (`WHEN MATCHED AND s.event_ts > t.event_ts THEN UPDATE`). With Lakeflow pipelines (formerly Delta Live Tables), `AUTO CDC` (formerly `APPLY CHANGES`)
      with `SEQUENCE BY` handles out-of-order events for you.
    - **Gold:** recompute only the periods the late data touches, for example with `INSERT INTO ... REPLACE WHERE`
      for the affected dates, or use a materialized view, which is correct at each refresh even when data arrives
      late or out of order.
    - **Streaming aggregates:** a watermark defines how long to wait; data later than that may be dropped from the
      streaming aggregate, so keep a batch correction path for very late data.

    **Why:** the interviewer is checking that you separate *event time* from *processing time*.

    **Learn more:** [Chapter 9](09-Building-Silver.md), [Chapter 11](11-Structured-Streaming.md).

**Q59. What are SCD Type 1 and Type 2, and where do they live?**

??? success "Answer"
    **SCD Type 1** overwrites a changed attribute and keeps only the current state. **SCD Type 2** keeps history: a
    change closes the current row (sets its end time) and inserts a new current row, so you can see the record as it
    was at any time. In `AUTO CDC` (formerly `APPLY CHANGES`) the validity columns are `__START_AT` and `__END_AT`, and active rows have
    `__END_AT = NULL`; with hand-written `MERGE` you usually add `valid_from`, `valid_to` and `is_current`.

    Type 2 tables typically sit in silver (the history of an entity, built from a CDC feed) and feed gold dimensions;
    the exact placement is a team convention.

    **Why:** the follow-up is "how do you build Type 2 with one `MERGE`?" (Q112) or "with `AUTO CDC`?" (Q88).

    **Learn more:** [Chapter 9](09-Building-Silver.md), Chapter 14.

**Q60. How do you keep a medallion pipeline's cost under control?**

??? success "Answer"
    Match freshness to need. Continuous ingestion has lower latency and higher cost; triggered incremental runs
    (scheduled `availableNow` streams or triggered pipelines) cost less; plain batch with your own incremental
    bookkeeping is cheapest to run but needs more engineering. Then: process incrementally instead of recomputing,
    run production on job compute or serverless, let predictive optimization handle `OPTIMIZE`/`VACUUM` on managed
    tables, cluster big tables on their filter columns, and tag compute so costs can be attributed.

    **Why:** "make it real-time" is rarely free. Ask how fresh the dashboard really needs to be.

    **Learn more:** [Chapter 7](07-Medallion-Architecture.md), Chapter 23.

## 24.6 Ingestion

*Level: intermediate.*

**Q61. What is Auto Loader, and how does it know which files it already loaded?**

??? success "Answer"
    Auto Loader is a Structured Streaming source called `cloudFiles` that incrementally processes new files as they
    arrive in cloud storage (S3, ADLS, GCS, Unity Catalog volumes). It supports JSON, CSV, XML, Parquet, Avro, ORC,
    text and binary files. As it discovers files it stores their metadata in a RocksDB key-value store inside the
    stream's checkpoint location, which gives exactly-once processing; after a failure it resumes from the
    checkpoint.

    *Databricks only, not run here. Syntax from [Configure schema inference and evolution in Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema).*

    ```python
    (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", "/Volumes/shop/bronze/_meta/orders_schema")
        .load("/Volumes/shop/bronze/landing/orders/")
        .writeStream
        .option("checkpointLocation", "/Volumes/shop/bronze/_meta/orders_chk")
        .trigger(availableNow=True)
        .toTable("shop.bronze.orders"))
    ```

    **Why:** inside a Lakeflow pipeline (formerly Delta Live Tables) you do not set the schema or checkpoint location; the pipeline manages them.

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md).

**Q62. Auto Loader or `COPY INTO`?**

??? success "Answer"
    `COPY INTO` is a SQL command that loads files from a location into a Delta table. It is retriable and
    idempotent: files already loaded are skipped on later runs. Auto Loader is a streaming source with schema
    inference and evolution, the rescued data column, file notification mode, and scale to millions of files per
    hour.

    Today Databricks recommends Auto Loader for most ingestion, and for SQL users recommends streaming tables
    (`CREATE STREAMING TABLE ... read_files`, which uses Auto Loader) as the scalable alternative to `COPY INTO`;
    the options reference labels `COPY INTO` as legacy. `COPY INTO` does not support the rescued data column.

    **Why:** the older rule of thumb "COPY INTO for thousands of files, Auto Loader for millions" still shows up in
    interviews. Say that the current docs point SQL users to streaming tables, and that both are idempotent.

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md).

**Q63. Directory listing or file notification mode?**

??? success "Answer"
    In **directory listing** mode (the default) Auto Loader lists the input directory to find new files; it needs
    no extra setup beyond read access. In **file notification** mode it uses cloud notification and queue services;
    with *file events* enabled on the Unity Catalog external location, no extra permissions are needed. Databricks
    recommends file notification mode with file events for most workloads because it is faster and scales better.
    You can switch modes between restarts and keep exactly-once guarantees.

    **Why:** neither mode guarantees the order in which files are processed. Design for out-of-order files
    (sequence by an event time or version in the data, not by arrival).

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md).

**Q64. How does Auto Loader infer a schema?**

??? success "Answer"
    On first read it samples the first 50 GB or 1000 files it finds, whichever comes first, and stores the schema in
    a `_schemas` directory under `cloudFiles.schemaLocation`. For formats without types (JSON, CSV, XML) it infers
    every column as `STRING` by default, including nested JSON fields; set `cloudFiles.inferColumnTypes` to `true` to
    infer real types. For Parquet and Avro it merges the file schemas, choosing the widest type on conflicts.

    **Why:** all-strings in bronze is deliberate: it avoids failures when a value does not fit an inferred type.
    Types are applied in silver.

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md).

**Q65. A new column appears in the source files. What does Auto Loader do?**

??? success "Answer"
    It depends on `cloudFiles.schemaEvolutionMode`:

    | Mode | Behavior on a new column |
    | --- | --- |
    | `addNewColumns` (default when no schema is given) | Updates the stored schema, then the stream fails with `UnknownFieldException`; a restart continues with the new schema |
    | `addNewColumnsWithTypeWidening` | Like `addNewColumns`, and also widens types such as `int` to `long` (Public Preview) |
    | `rescue` | Never changes the schema, never fails; new columns go to the rescued data column |
    | `failOnNewColumns` | Fails until you update the schema or remove the file |
    | `none` (default when you provide a schema) | Ignores new columns; no rescue unless `rescuedDataColumn` is set |

    **Why:** the failure in `addNewColumns` is by design. Databricks recommends running the stream in a Lakeflow Job (formerly Databricks Workflows)
    with retries so it restarts automatically and picks up the new schema.

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md).

**Q66. What is the rescued data column?**

??? success "Answer"
    When Auto Loader infers the schema it adds a column `_rescued_data`. Any value that does not fit the schema goes
    there instead of being dropped: a column missing from the schema, a type mismatch, or a case mismatch in the
    column name. It is a JSON blob containing the rescued columns and the source file path of the record.

    **Why:** monitor it. A daily count of rows `WHERE _rescued_data IS NOT NULL` is an early warning that a source
    changed. With the rescued data column, type mismatches do not make `DROPMALFORMED` drop records or `FAILFAST`
    fail; only truly corrupt records (malformed JSON or CSV) do.

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md).

**Q67. What are schema hints?**

??? success "Answer"
    `cloudFiles.schemaHints` overrides the inferred type of the columns you know, using SQL schema syntax, for
    example `.option("cloudFiles.schemaHints", "order_ts TIMESTAMP, amount DECIMAL(10,2)")`. Columns you do not
    mention are still inferred. A hint can also add a column that does not yet exist in the sample.

    **Why:** hints give you types for important columns without giving up inference and evolution for the rest.
    Note that `addNewColumns` is not allowed when you provide a full schema, but works with schema hints.

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md).

**Q68. What is in an ingestion stream's checkpoint, and what happens if you delete it?**

??? success "Answer"
    For Auto Loader, the checkpoint holds the record of discovered files (RocksDB) plus the usual Structured
    Streaming offsets and commits. Each ingestion stream needs its own checkpoint, including one per source location
    when several locations feed one table. If you delete the checkpoint or point the stream at a new one, the next
    run starts fresh: it reprocesses every file still in the directory, which creates duplicates in an append-only
    bronze table.

    **Why:** a common incident (Q136). Treat checkpoint paths as part of the table's identity: put them in config,
    never change them casually, never share them between streams.

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md), [Chapter 11](11-Structured-Streaming.md).

**Q69. What is the `_metadata` column?**

??? success "Answer"
    A hidden column available for all file formats that describes the input file of each row. You must select it
    explicitly. Its fields include `file_path`, `file_name`, `file_size` and `file_modification_time`. Databricks
    recommends selecting specific fields (for example `_metadata.file_name`) rather than the whole struct, because new
    fields may be added.

    **Why:** storing the source file and its modification time in bronze makes debugging ("which file brought this
    bad row?") and targeted reprocessing possible.

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md).

**Q70. How do SQL users ingest files incrementally?**

??? success "Answer"
    With a streaming table that reads with `read_files` and the `STREAM` keyword. In a streaming table query,
    `read_files` uses Auto Loader under the hood.

    *Databricks only, not run here. Syntax from [`read_files` table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/read_files).*

    ```sql
    CREATE OR REFRESH STREAMING TABLE shop.bronze.orders AS
    SELECT *, _metadata.file_name AS source_file
    FROM STREAM read_files('/Volumes/shop/bronze/landing/orders/', format => 'json');
    ```

    **Why:** a standalone streaming table created in Databricks SQL is refreshed by a pipeline that Databricks
    creates and manages for you (pipeline type `MV/ST`).

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md), Chapter 13.

**Q71. How do you ingest from Kafka?**

??? success "Answer"
    Read with the `kafka` format (or `read_kafka` in SQL). Each row has `key` and `value` as binary plus `topic`,
    `partition`, `offset`, `timestamp` and `timestampType`. In bronze, store the raw `value` (cast to string, or
    parsed into `VARIANT`) with the topic, partition, offset and Kafka timestamp; parse and type it in silver.

    *Databricks only, not run here. Syntax from [Connect to Apache Kafka](https://docs.databricks.com/aws/en/structured-streaming/kafka).*

    ```python
    raw = (spark.readStream.format("kafka")
           .option("kafka.bootstrap.servers", "<server:port>")
           .option("subscribe", "orders")
           .option("startingOffsets", "latest")
           .load())
    bronze = raw.selectExpr("CAST(value AS STRING) AS raw", "topic", "partition",
                            "offset", "timestamp AS kafka_ts")
    ```

    **Why:** `(topic, partition, offset)` uniquely identifies a message, which is useful for deduplication. Kafka
    retention is limited, which is why bronze must be kept (Q48).

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md), [Chapter 11](11-Structured-Streaming.md).

## 24.7 Structured Streaming

*Level: intermediate.*

**Q72. How does Structured Streaming process a stream?**

??? success "Answer"
    It treats a stream as a table that keeps growing and lets you write the same DataFrame or SQL query you would
    write for a static table. Spark runs that query incrementally. In the default micro-batch engine, each trigger
    checks the sources for new data, records the offsets it is about to process in the checkpoint, processes them as
    a small batch job, writes the result to the sink and records the commit. Stateful operators (aggregations,
    stream-stream joins, deduplication) keep their state between micro-batches, also in the checkpoint.

    **Why:** the follow-up is usually "so what is different from batch?" Answer: sources and sinks must support
    streaming, you choose a trigger and an output mode, and stateful queries need a watermark so that state does not
    grow forever (Q77).

    **Learn more:** [Chapter 11](11-Structured-Streaming.md).

**Q73. Which triggers exist, and which one would you pick?**

??? success "Answer"
    | Trigger | Behavior | Typical use |
    | --- | --- | --- |
    | Not set (default) | Same as `processingTime` with a 0 ms interval; Databricks describes it as general-purpose streaming with 3-5 second latency | Rarely the right choice in production; see the warning below |
    | `processingTime='10 seconds'` | Fixed-interval micro-batches | Near-real-time with controlled cost |
    | `availableNow=True` | Processes everything available now, in one or more batches, then stops | Scheduled incremental batch (hourly, daily) |
    | `realTime` | Real-time mode, sub-second latency, as low as five milliseconds according to the page | Ultra-low-latency operational workloads |

    `Trigger.Once` is deprecated in Databricks Runtime 11.3 LTS and above; use `AvailableNow`. Spark's experimental
    continuous processing trigger is not supported or recommended by Databricks. Serverless notebooks and jobs
    accept only `AvailableNow` (recommended) and the deprecated `Once`; a default or `processingTime` trigger raises
    `INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED`. For continuous work on serverless, use a pipeline in continuous mode.

    **Why:** the default trigger checks for new data every few milliseconds, which can generate a high volume of
    cloud storage API calls and an unexpected bill. Always set a trigger that matches the latency requirement.

    **Learn more:** [Chapter 11](11-Structured-Streaming.md).

**Q74. Why run a streaming query with `availableNow` from a daily job instead of writing a batch job?**

??? success "Answer"
    Because the checkpoint remembers what was already processed. Each run picks up exactly the new files, Kafka
    offsets or Delta versions since the last run, processes them and stops, so the cluster is not kept running. A
    plain batch job would have to work out "what is new since yesterday" itself, usually with a high-water-mark
    column, and get it right after failures and reruns. Batch size can still be capped with options such as
    `maxFilesPerTrigger` or `maxBytesPerTrigger`, so a large backlog is split into several micro-batches.

    **Why:** this is the standard answer to "we only need fresh data once a day": incremental, idempotent and cheap.
    Databricks also recommends `AvailableNow` for incremental batch loading from Kafka.

    **Learn more:** [Chapter 11](11-Structured-Streaming.md).

**Q75. What is in a checkpoint, and when do you need a new one?**

??? success "Answer"
    A checkpoint directory holds the **offsets** processed in each micro-batch (so the query resumes where it left
    off), the **commits** of micro-batches written to the sink (for exactly-once), the **state** of stateful
    operators, and **metadata** such as the query ID; configuration is stored with the offset log. Each query needs
    its own checkpoint location; two queries must never share one.

    Changes that generally require a new checkpoint: the number or type of input sources, subscribed Kafka topics or
    Auto Loader paths, the type of stateful operations, the state schema, and the output sink type. Changing the
    trigger interval is allowed with the same checkpoint.

    **Why:** deleting a checkpoint or pointing the query at a new location makes the next run start fresh, which
    reprocesses everything the source still holds (Q136).

    **Learn more:** [Chapter 11](11-Structured-Streaming.md).

**Q76. Show that a checkpoint gives exactly-once loading of files.**

??? success "Answer"
    Run the same file-to-Delta stream three times with the same checkpoint: once after the first file lands, once
    with no new file, and once after a second file lands.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    def run_bronze():
        q = (spark.readStream.schema(schema).json(landing)
             .withColumn("source_file", F.col("_metadata.file_name"))
             .writeStream.format("delta")
             .option("checkpointLocation", os.path.join(wd, "chk_bronze"))
             .trigger(availableNow=True)
             .toTable("bronze_orders"))
        q.awaitTermination()

    run_bronze()   # f1.json (2 rows) is new         -> count 2
    run_bronze()   # nothing new                     -> count 2
    run_bronze()   # after f2.json (2 rows) lands    -> count 4
    ```

    ```text
    >>> SELECT count(*) AS n FROM bronze_orders
    +---+
    |n  |
    +---+
    |2  |
    +---+
    >>> SELECT count(*) AS n FROM bronze_orders
    +---+
    |n  |
    +---+
    |2  |
    +---+
    >>> SELECT count(*) AS n FROM bronze_orders
    +---+
    |n  |
    +---+
    |4  |
    +---+
    ```

    The second run wrote nothing, and the third added only the two rows of the new file.

    **Why:** exactly-once into Delta needs both halves: a replayable source with offsets in the checkpoint, and an
    idempotent sink. The Delta transaction log guarantees exactly-once processing for streaming writes, even with
    other streams or batch jobs writing to the table. Exactly-once is about processing; it does not remove
    duplicates that already exist in the source data (Q81).

    **Learn more:** [Chapter 11](11-Structured-Streaming.md), [Chapter 8](08-Bronze-Ingestion.md).

**Q77. What is a watermark? Walk through what happens to late events.**

??? success "Answer"
    A watermark tells a stateful query how late data may arrive: `withWatermark("event_ts", "10 minutes")` means
    the watermark is the latest event time seen minus 10 minutes. Records within the threshold are always processed.
    When a window ends before the watermark, its state is dropped, and later records for it are discarded. Records
    outside the threshold *might* still be processed, but this is not guaranteed.

    The script below feeds five one-file micro-batches into a 5-minute windowed count with a 10-minute watermark.
    The file `e3` carries a late 10:03 event, and `e5` a very late 10:04 event.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    q = (spark.readStream.schema("event_ts TIMESTAMP, page STRING")
         .option("maxFilesPerTrigger", 1).json(events)
         .withWatermark("event_ts", "10 minutes")
         .groupBy(F.window("event_ts", "5 minutes"))
         .count()
         .writeStream.outputMode("update").foreachBatch(save_counts)
         .option("checkpointLocation", os.path.join(wd, "chk_views"))
         .trigger(availableNow=True).start())
    ```

    ```text
    batch | input rows | watermark used         (file: event times)
    0 | 2 | 1970-01-01T00:00:00.000Z            e1: 10:00, 10:02
    1 | 1 | 2026-03-01T09:52:00.000Z            e2: 10:31
    2 | 1 | 2026-03-01T10:21:00.000Z            e3: 10:03 (late)
    3 | 1 | 2026-03-01T10:21:00.000Z            e4: 10:40
    4 | 1 | 2026-03-01T10:30:00.000Z            e5: 10:04 (very late)
    +--------+-------------------+-----+
    |batch_id|window_start       |views|
    +--------+-------------------+-----+
    |0       |2026-03-01 10:00:00|2    |
    |1       |2026-03-01 10:30:00|1    |
    |2       |2026-03-01 10:00:00|3    |
    |3       |2026-03-01 10:40:00|1    |
    +--------+-------------------+-----+
    ```

    (The file and event-time notes on the right were added to the printed progress lines for reading.) The
    watermark is computed at the end of each micro-batch and used by the next one. The late 10:03 event was still
    counted in batch 2 (the 10:00 window went from 2 to 3), because the window's state had not yet been dropped. By
    batch 4 that state was gone, and the 10:04 event was read (1 input row) but produced no output: it was dropped.

    **Why:** the precise answer is one-sided: on-time data is guaranteed to count, late data is neither guaranteed
    to count nor guaranteed to be dropped. A longer watermark tolerates later data but keeps more state and delays
    output in append mode; a shorter one does the opposite. If late corrections matter for correctness, land every
    event in bronze and recompute the affected windows in batch (design 24.13).

    **Learn more:** [Chapter 11](11-Structured-Streaming.md).

**Q78. Append, update or complete output mode: what is the difference?**

??? success "Answer"
    For a windowed aggregation with a watermark:

    | Mode | What is written | State |
    | --- | --- | --- |
    | Append | A window's row is written once, after the watermark passes it; all writes are delayed by the lateness threshold | Old state dropped after the threshold |
    | Update | Rows are written as results change, and a window can be written again when new data arrives | Old state dropped after the threshold |
    | Complete | The whole result is rewritten on every trigger | Never dropped |

    Streams into Delta run in append mode by default, and complete mode replaces the whole table each batch. The
    Delta documentation writes update-mode aggregations through `foreachBatch` with a `MERGE`, as in Q77.

    **Why:** append is the safe default for sinks that cannot update rows, at the cost of latency. Complete mode
    keeps all state forever, so it only suits small result sets. Stream-stream joins support append mode only.

    **Learn more:** [Chapter 11](11-Structured-Streaming.md).

**Q79. What is `foreachBatch`, and what guarantee does it give?**

??? success "Answer"
    `foreachBatch(fn)` calls your function once per micro-batch with a normal (batch) DataFrame and the `batchId`.
    It lets you use batch-only operations such as `MERGE`, or write one stream to a sink without streaming support.
    It gives only **at-least-once** write guarantees: after a failure the same batch can run again. You make it
    exactly-once by making the function idempotent, for example a `MERGE` that gives the same result when replayed,
    or Delta writes with the `txnAppId` and `txnVersion` options, binding `txnVersion` to `batchId`.

    Upsert of the latest status per order from the bronze stream:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    def upsert(batch_df, batch_id):
        w = Window.partitionBy("order_id").orderBy(F.col("status_rank").desc())
        latest = batch_df.withColumn("rn", F.row_number().over(w)).filter("rn = 1")
        latest.createOrReplaceTempView("batch_updates")
        batch_df.sparkSession.sql("""
            MERGE INTO silver_orders t USING batch_updates s ON t.order_id = s.order_id
            WHEN MATCHED THEN UPDATE SET t.status = s.status
            WHEN NOT MATCHED THEN INSERT (order_id, status, order_ts)
                                  VALUES (s.order_id, s.status, s.order_ts)""")

    rank = F.when(F.col("status") == "SHIPPED", 2).otherwise(1)
    (spark.readStream.table("bronze_orders").withColumn("status_rank", rank)
         .writeStream.foreachBatch(upsert)
         .option("checkpointLocation", os.path.join(wd, "chk_silver"))
         .trigger(availableNow=True).start().awaitTermination())
    ```

    ```text
    +--------+-------+
    |order_id|status |
    +--------+-------+
    |1001    |PLACED |
    |1002    |SHIPPED|
    |1003    |PLACED |
    +--------+-------+
    ```

    Order 1002 appeared twice in the micro-batch (`PLACED` and `SHIPPED`); deduplicating inside the batch first
    avoids the multiple-source-rows error (Q125).

    **Why:** Databricks advises against catching and retrying exceptions inside the function: let errors propagate
    so the orchestrator retries the whole batch. To write one stream to several tables, Databricks recommends
    several streaming writers, because writing multiple sinks in one `foreachBatch` serializes them.

    **Learn more:** [Chapter 11](11-Structured-Streaming.md), [Chapter 9](09-Building-Silver.md).

**Q80. What do you need to know about stream-stream joins?**

??? success "Answer"
    Both sides are kept in state so that a new row on one side can match old rows on the other. They support only
    append mode. For inner joins, Databricks recommends a watermark on each side so state for old records can be
    discarded; without watermarks the query tries to join every key from both sides on each trigger. For outer
    joins a watermark is mandatory, and unmatched rows (with nulls) are only written after the lateness threshold
    passes. With several inputs, the default global watermark is the minimum of the per-input watermarks, so the
    query moves at the pace of the slowest stream.

    **Why:** a stream-static join (stream joined to a Delta dimension table) needs no join state and is the simpler
    choice when one side changes slowly.

    **Learn more:** [Chapter 11](11-Structured-Streaming.md).

**Q81. Kafka sometimes delivers the same event twice. How do you deduplicate a stream?**

??? success "Answer"
    Structured Streaming guarantees exactly-once processing but does not deduplicate records from data sources. Use
    a unique event ID with a watermark so the deduplication state is bounded:

    *Databricks only, not run here. Syntax from [Apply watermarks to control data processing thresholds](https://docs.databricks.com/aws/en/structured-streaming/watermarks).*

    ```python
    (spark.readStream.table("shop.bronze.events")
        .withWatermark("event_ts", "1 hour")
        .dropDuplicatesWithinWatermark(["event_id"]))
    ```

    `dropDuplicatesWithinWatermark` (Databricks Runtime 13.3 LTS and above) removes duplicates on the given fields
    even when other fields, such as the event time, differ between the copies. `dropDuplicates()` without a
    watermark keeps every key in state forever.

    **Why:** the trade-off is the window: a duplicate arriving after the watermark is not caught. If duplicates can
    be days apart, `MERGE` on the event ID into silver (insert only when not matched) is the safer second line.

    **Learn more:** [Chapter 11](11-Structured-Streaming.md), [Chapter 9](09-Building-Silver.md).

**Q82. Your stream reads a Delta table, and someone runs an `UPDATE` on that source table. The stream fails. Why,
and what are the options?**

??? success "Answer"
    A Delta streaming source expects appends. A commit that rewrites existing files (`UPDATE`, `MERGE`, `DELETE`)
    would otherwise re-emit rows already processed, so the stream fails. Options from the Delta streaming page:

    - `skipChangeCommits`: ignore commits that delete or modify existing records and process only appends. It
      replaces `ignoreChanges` (Databricks Runtime 12.2 LTS and above); the legacy `ignoreDeletes` handles only full
      partition drops.
    - Full refresh: delete the checkpoint and output table and restart from the beginning, if changes are rare and
      the data is small; downstream tables must be reprocessed too.
    - Change data feed: stream the row-level changes (insert, update, delete) and handle each type; the most robust
      approach.
    - Materialized views, which propagate changes automatically at higher latency (available only in Lakeflow
      pipelines and Databricks SQL).

    **Why:** this comes up in medallion designs: silver is often updated by `MERGE`, so a gold stream reading silver
    needs CDF or `skipChangeCommits`. A schema change on the source table also fails the stream; for most schema
    changes, restarting it resolves the mismatch.

    **Learn more:** [Chapter 11](11-Structured-Streaming.md), [Chapter 4](04-Delta-Lake.md).

## 24.8 Lakeflow pipelines (formerly Delta Live Tables)

*Level: intermediate.*

**Q83. What are Lakeflow pipelines, and what do they give you over hand-written Spark jobs?**

??? success "Answer"
    Lakeflow pipelines ("Spark Declarative Pipelines on Lakeflow", formerly Delta Live Tables) are a declarative
    framework for batch and streaming pipelines in SQL or Python. You declare datasets (streaming tables,
    materialized views, views) and the queries that define them; the pipeline works out the dependency graph and
    runs it. Compared with Spark jobs orchestrated by hand, you get automatic orchestration (flows run in the right
    order with maximum parallelism, and transient failures are retried progressively: task, then flow, then the whole
    pipeline), declarative CDC with `AUTO CDC` (formerly `APPLY CHANGES`), built-in data quality (expectations), incremental refresh of
    materialized views, and automatic table maintenance. All pipeline tables are Delta tables.

    They are built on open-source Apache Spark Declarative Pipelines and add Databricks features on top; for
    example, the `AUTO CDC` APIs are not supported by the open-source version. In Python, import
    `from pyspark import pipelines as dp` (older code uses `import dlt`).

    **Why:** the trade-off is control. A pipeline owns its tables (a table defined by one pipeline cannot be updated
    by another), and some low-level stream settings are managed for you.

    **Learn more:** Chapter 13.

**Q84. Streaming table, materialized view or view: how do you choose?**

??? success "Answer"
    | Dataset | How records are processed | Use it for |
    | --- | --- | --- |
    | Streaming table | Each input record processed once, assuming an append-only source | Ingestion, append-only and low-latency incremental processing |
    | Materialized view | Results kept equal to the current result of the query; refreshed incrementally when possible | Aggregations, joins, sources that receive updates and deletes, results read by many consumers |
    | View | Evaluated on demand, not stored | Intermediate steps and checks inside one pipeline |

    **Why:** the key difference is what happens to old rows. A streaming table never re-reads a row it already
    processed, so if you change its query, existing rows keep the old logic until a full refresh. A materialized
    view is always correct at refresh time, even for late or out-of-order data, but may cost more per refresh.

    **Learn more:** Chapter 13.

**Q85. What is a flow?**

??? success "Answer"
    A flow reads from a source, applies your logic and writes to a target. Pipelines expose the Structured Streaming
    *append* and *update* flow types, plus two of their own: the `AUTO CDC` (formerly `APPLY CHANGES`) flow (for CDC feeds, SCD Type 1 and 2)
    and the materialized view flow (a batch flow that processes only new and changed source data when it can).
    Several flows can write into one streaming table, for example one per region or one for a one-time backfill.

    **Why:** multiple flows into one target is how you add a new source to an existing table without a full
    refresh.

    **Learn more:** Chapter 13.

**Q86. What are expectations, and what are the three actions on a failing record?**

??? success "Answer"
    An expectation is a named SQL boolean constraint on a dataset that is checked for every record:

    | Action | SQL | Python | Effect |
    | --- | --- | --- | --- |
    | warn (default) | `EXPECT (...)` | `@dp.expect` | Invalid records are written; the violation is counted |
    | drop | `EXPECT (...) ON VIOLATION DROP ROW` | `@dp.expect_or_drop` | Invalid records are dropped; the count is logged |
    | fail | `EXPECT (...) ON VIOLATION FAIL UPDATE` | `@dp.expect_or_fail` | The update fails; a table update is rolled back atomically |

    *Databricks only, not run here. Syntax from [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations).*

    ```sql
    CREATE OR REFRESH STREAMING TABLE shop.silver.orders (
      CONSTRAINT valid_id     EXPECT (order_id IS NOT NULL) ON VIOLATION DROP ROW,
      CONSTRAINT valid_amount EXPECT (amount >= 0)
    ) AS SELECT * FROM STREAM(shop.bronze.orders_parsed);
    ```

    **Why:** metrics for warn and drop appear in the pipeline UI and the event log; for fail, no metrics are recorded
    because the update stops. Constraints cannot call custom Python functions, external services, or subqueries on
    other tables. Grouping several expectations with `expect_all`, `expect_all_or_drop` and `expect_all_or_fail` is
    Python-only.

    **Learn more:** Chapter 14.

**Q87. Expectations can drop bad rows, but how do you keep them for later inspection?**

??? success "Answer"
    Use the quarantine pattern. The documented version computes a flag such as
    `is_quarantined = NOT(rule1 AND rule2 ...)` on every row in a temporary table (with the rules attached through
    `expect_all`, so the metrics are still recorded), then defines two views on it: valid rows
    (`is_quarantined = false`) continue to silver, invalid rows (`is_quarantined = true`) go to a quarantine table
    that someone reviews. A simpler variant writes the same source into two tables, one with
    `expect_or_drop(rule)` and one filtered on `NOT rule`.

    **Why:** dropping is invisible data loss; quarantining makes bad data a work item with an owner.

    **Learn more:** Chapter 14.

**Q88. What is `AUTO CDC`, and how do you build an SCD Type 2 table with it?**

??? success "Answer"
    `AUTO CDC` (which replaces `APPLY CHANGES` with the same syntax; `APPLY CHANGES` still works) applies a CDC feed
    to a streaming table. You give the key columns, a sequencing column that orders events, optional delete and
    truncate conditions, and SCD Type 1 or 2. It handles out-of-order events for you: a late update with an older
    sequence value does not overwrite a newer one. For SCD Type 2 the target gets `__START_AT` and `__END_AT`
    columns; the current row has `__END_AT` NULL.

    *Databricks only, not run here. Syntax from [The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc).*

    ```sql
    CREATE OR REFRESH STREAMING TABLE shop.silver.customers_history;

    CREATE FLOW customers_cdc AS AUTO CDC INTO shop.silver.customers_history
    FROM stream(shop.bronze.customers_cdc)
    KEYS (customer_id)
    APPLY AS DELETE WHEN operation = "DELETE"
    SEQUENCE BY sequence_num
    COLUMNS * EXCEPT (operation, sequence_num)
    STORED AS SCD TYPE 2;
    ```

    **Why:** the sequencing column must be sortable and never NULL; to break ties, sequence by a struct such as
    `STRUCT(event_ts, id)`. `AUTO CDC` requires serverless pipelines or the Pro or Advanced edition. To stream from
    an `AUTO CDC` target downstream, read its change feed.

    **Learn more:** Chapter 14.

**Q89. The source database has no CDC feed, only daily full extracts. What do you use?**

??? success "Answer"
    `AUTO CDC FROM SNAPSHOT`. It compares consecutive snapshots to work out inserts, updates and deletes (a key
    missing from the newer snapshot is treated as deleted), then applies them as SCD Type 1 or Type 2. Snapshots can
    come from a Delta table, files in cloud storage, or JDBC. For SCD Type 1 targets you can also combine one snapshot
    flow with `AUTO CDC` (formerly `APPLY CHANGES`) flows when a source provides periodic snapshots plus a lower-latency change feed.

    **Why:** hand-written snapshot diffing (a full outer join of yesterday and today) is error-prone with deletes and
    reappearing keys; the API handles those cases.

    **Learn more:** Chapter 14.

**Q90. Triggered or continuous pipeline mode?**

??? success "Answer"
    **Triggered** mode refreshes all tables with the data available when the update starts, then stops; it suits
    refreshes every 10 minutes, hourly or daily. **Continuous** mode keeps running and processes data as it
    arrives; it suits freshness between about 10 seconds and a few minutes, and costs more because compute stays up.
    The mode is independent of table type: both streaming tables and materialized views work in either. For
    continuous pipelines, Databricks recommends running them from a continuous job rather than setting the pipeline
    mode to continuous.

    **Why:** standalone materialized views and streaming tables (created in Databricks SQL) always refresh in
    triggered mode.

    **Learn more:** Chapter 13, Chapter 15.

**Q91. What is the difference between a refresh, a full refresh and resetting checkpoints?**

??? success "Answer"
    | Update type | Materialized view | Streaming table |
    | --- | --- | --- |
    | Refresh (default) | Brought up to date, incrementally when cheaper | Processes only new records |
    | Full refresh | Recomputed | Data cleared, checkpoints cleared, everything reprocessed from the source |
    | Reset streaming flow checkpoints | Not applicable | Checkpoints cleared, data kept, everything reprocessed |

    **Why:** a full refresh of a streaming table can lose data. It reprocesses only what the source still holds, so
    records past Kafka retention or files removed by a lifecycle rule are dropped from the target. Databricks
    recommends a full refresh only when the sources still contain the data needed to rebuild the table. This is the
    strongest argument for keeping bronze.

    **Learn more:** Chapter 13.

**Q92. You changed the query of a streaming table (for example `lower(name)` to `upper(name)`). What happens to existing rows?**

??? success "Answer"
    Nothing. A streaming table never re-reads rows it has already appended, so existing rows keep the old logic and
    only new rows get the new logic. To apply the new logic to all rows, run a full refresh of that table (if the
    source still has all the data), or use a materialized view if the dataset should always reflect the current
    query.

    **Why:** the Databricks docs give the same kind of example (add `UPPER()` to a field, and only rows processed
    after the change are uppercase), and it tests whether you understand "process each record once".

    **Learn more:** Chapter 13.

**Q93. How do you build a materialized view outside a pipeline, and who refreshes it?**

??? success "Answer"
    In Databricks SQL you can create a standalone materialized view or streaming table directly, for example
    `CREATE OR REPLACE MATERIALIZED VIEW shop.gold.weekly_sales AS SELECT ...`. Databricks creates and manages a
    pipeline to refresh it (it shows in **Jobs & Pipelines** with pipeline type `MV/ST`, while pipeline-defined
    tables have type `ETL`). Expectations work there too, with `CONSTRAINT ... EXPECT` in the `CREATE` statement.

    **Why:** standalone objects are good for a few gold aggregates owned by analysts; a full Lakeflow pipeline (formerly Delta Live Tables) is
    better when many datasets depend on each other and need one schedule, one owner and one set of tests.

    **Learn more:** Chapter 10, Chapter 13.

## 24.9 Unity Catalog and governance

*Level: intermediate.*

**Q94. What is Unity Catalog, and what does it give a data engineer?**

??? success "Answer"
    Unity Catalog is the governance layer for data and AI in Databricks. It enforces access control when anyone
    queries a table or uses a model, tracks lineage automatically, logs activity for audit, and makes assets
    discoverable in Catalog Explorer. Assets use a three-level namespace `catalog.schema.object`. It is enabled
    automatically for workspaces created after November 8, 2023, and also exists as an open-source project.

    **Why:** for a data engineer, it means one place to grant access to bronze, silver and gold, lineage for impact
    analysis before changing a column, and system tables for audit and cost.

    **Learn more:** [Chapter 5](05-Unity-Catalog.md).

**Q95. What securable objects does Unity Catalog have?**

??? success "Answer"
    The metastore is at the top. Under it are catalogs, then schemas, then data and AI objects: tables, views,
    materialized views, volumes, functions (including registered models) and others. Some objects sit directly under
    the metastore: storage credentials, external locations, connections (for Lakehouse Federation), shares,
    recipients and providers (for OpenSharing, formerly Delta Sharing).

    **Why:** storage credentials and external locations are how Unity Catalog governs access to cloud storage
    paths, instead of handing cloud keys to every cluster.

    **Learn more:** [Chapter 5](05-Unity-Catalog.md).

**Q96. What privileges does a user need to read a table? How does inheritance work?**

??? success "Answer"
    `SELECT` on the table, plus `USE CATALOG` on its catalog and `USE SCHEMA` on its schema. Privileges are
    inherited downward: `SELECT` granted on a schema applies to all current and future tables in it, and on a
    catalog to everything in the catalog.

    *Databricks only, not run here. Syntax from [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant).*

    ```sql
    GRANT USE CATALOG ON CATALOG shop TO `analysts`;
    GRANT USE SCHEMA ON SCHEMA shop.gold TO `analysts`;
    GRANT SELECT ON SCHEMA shop.gold TO `analysts`;
    ```

    **Why:** grant to groups, not users, and grant at the schema level so new gold tables are covered
    automatically. Writing needs `MODIFY` (which also requires `SELECT` and the usage privileges). Unity Catalog best
    practices say to run production jobs as service principals and reserve direct `MODIFY` on production tables for
    them.

    **Learn more:** [Chapter 5](05-Unity-Catalog.md), Chapter 23.

**Q97. What is the difference between `BROWSE`, `SELECT` and `MANAGE`?**

??? success "Answer"
    `BROWSE` lets a user discover objects and see their metadata without access to the data, and it does not need
    `USE CATALOG` or `USE SCHEMA`; for tables it is granted at catalog level. Databricks recommends granting `BROWSE`
    on catalogs to all account users so people can find data and request access. `SELECT` reads data. `MANAGE` lets
    a non-owner manage privileges and perform owner-like actions on an object; like `READ METADATA`, it is not
    included in `ALL PRIVILEGES` and must be granted explicitly.

    **Why:** `BROWSE` is the answer to "people cannot find data, but we do not want to give everyone read access".

    **Learn more:** [Chapter 5](05-Unity-Catalog.md).

**Q98. How do you restrict which rows or column values a user sees?**

??? success "Answer"
    Three tools:

    1. **Row filters and column masks** on one table: a SQL UDF attached with `ALTER TABLE ... SET ROW FILTER` or
       `ALTER TABLE ... ALTER COLUMN ... SET MASK`, evaluated at query time.
    2. **ABAC policies**: row filter and column mask policies attached at catalog, schema or table level that apply
       automatically to tables and columns carrying governed tags. Databricks recommends ABAC for consistent rules
       across many tables.
    3. **Dynamic views**: a view that filters or masks with functions such as `is_account_group_member()`, used to
       share a curated slice.

    *Databricks only, not run here. Syntax from [Manually apply row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/manually-apply).*

    ```sql
    CREATE FUNCTION ssn_mask(ssn STRING)
      RETURN CASE WHEN is_account_group_member('HumanResourceDept') THEN ssn ELSE '***-**-****' END;
    ALTER TABLE users ALTER COLUMN ssn SET MASK ssn_mask;
    ```

    **Why:** keep filter and mask functions simple. The row filter page says functions with fewer expressions
    perform better, prefers simple `CASE` expressions over mapping tables or subqueries, and warns that Databricks
    cannot optimize away columns passed as UDF arguments, so complex UDFs slow queries.

    **Learn more:** Chapter 21, Chapter 23.

**Q99. What lineage does Unity Catalog capture?**

??? success "Answer"
    Unity Catalog captures lineage automatically for queries run on Databricks, down to the column level, across all
    workspaces attached to the metastore: which jobs, notebooks and queries write a table, which tables and
    dashboards read it, plus models, file paths and registered external assets. You see it in Catalog Explorer and
    can query it in the system tables `system.access.table_lineage` and `system.access.column_lineage`. Limits worth
    knowing: UDF lineage is captured at table level only, and temporary tables do not appear (lineage connects the
    permanent tables around them).

    **Why:** lineage answers "if I change this silver column, what breaks?" before you change it.

    **Learn more:** Chapter 23.

**Q100. How do you find out who read or changed a table last week?**

??? success "Answer"
    Query the audit log system table `system.access.audit` for access events, and run `DESCRIBE HISTORY` on the table
    for every write (operation, user, time, parameters, metrics). The query history system table
    (`system.query.history`) shows the SQL statements themselves.

    **Why:** `DESCRIBE HISTORY` covers changes to one table; the audit log covers reads, permission changes and
    other account activity.

    **Learn more:** Chapter 23.

**Q101. What are volumes?**

??? success "Answer"
    Volumes are Unity Catalog objects that govern non-tabular files (CSV and JSON landing files, images, PDFs) in
    cloud storage, with paths like `/Volumes/<catalog>/<schema>/<volume>/...`. Managed volumes live in the schema's managed
    storage location (usually in your own cloud account; Unity Catalog manages the files, see
    [chapter 5](05-Unity-Catalog.md)); external volumes add governance to an existing cloud location. Their privileges are `READ VOLUME` and
    `WRITE VOLUME`. Databricks recommends volumes for governing all non-tabular data.

    **Why:** a landing zone for raw files is usually a volume, and Auto Loader can read from it.

    **Learn more:** [Chapter 5](05-Unity-Catalog.md), [Chapter 8](08-Bronze-Ingestion.md).

**Q102. How does Unity Catalog control access to cloud storage?**

??? success "Answer"
    A **storage credential** wraps a cloud identity that can reach storage. An **external location** combines a
    storage path with a storage credential. Privileges on the external location (`READ FILES`, `WRITE FILES`,
    `CREATE EXTERNAL TABLE`, `CREATE EXTERNAL VOLUME`) decide who can use that path. External tables and external
    volumes live inside external locations.

    **Why:** users never see the cloud keys; access is granted and audited in one place.

    **Learn more:** [Chapter 5](05-Unity-Catalog.md).

**Q103. How do you share gold tables with a partner company?**

??? success "Answer"
    Use OpenSharing (formerly Delta Sharing), an open protocol for sharing live data without copying it. You create a
    share, add tables (and other assets) to it, create a recipient and grant the recipient `SELECT` on the share.
    With Databricks-to-Databricks sharing the recipient sees the data in their own Unity Catalog; the open protocol
    also serves recipients on other platforms. Databricks recommends OpenSharing for read-only access across
    organizations.

    **Why:** it avoids nightly exports and stale copies, and access can be revoked at any time.

    **Learn more:** Chapter 23.

**Q104. How do you find which jobs cost the most?**

??? success "Answer"
    Query the billable usage system table `system.billing.usage`, which has columns such as `usage_date`,
    `sku_name`, `usage_quantity`, `usage_unit` and `usage_metadata` (which holds IDs such as `job_id`), and join with
    `system.billing.list_prices` for prices. Aggregate with `SUM(usage_quantity)` so correction records
    (`RETRACTION` and `RESTATEMENT`) cancel out correctly.

    *Databricks only, not run here. Syntax from [Billable usage system table reference](https://docs.databricks.com/aws/en/admin/system-tables/billing).*

    ```sql
    SELECT usage_metadata.job_id, sku_name, SUM(usage_quantity) AS dbus
    FROM system.billing.usage
    WHERE usage_date >= current_date() - INTERVAL 30 DAYS
      AND usage_metadata.job_id IS NOT NULL
    GROUP BY ALL
    ORDER BY dbus DESC
    LIMIT 20;
    ```

    **Why:** also tag compute (business unit, project) so costs can be attributed. Several products (for example
    predictive optimization and serverless jobs) share a SKU; `billing_origin_product` tells them apart.

    **Learn more:** Chapter 23.

## 24.10 Databricks SQL specifics

*Level: intermediate.* The SQL in this section ran on Spark 4.2 + Delta 4.4.1 unless marked otherwise. The table
`silver_orders` here was parsed from three raw JSON events and still holds both versions of order 1001 (`PLACED`
and `SHIPPED`).

**Q105. A bronze column holds raw JSON text. Extract fields with `VARIANT`.**

??? success "Answer"
    Parse once with `parse_json` into a `VARIANT`, then navigate with the `:` path operator and cast with `::`.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT parse_json(raw):order_id::int             AS order_id,
           parse_json(raw):items[0].product_id::int  AS first_product,
           parse_json(raw):status::string            AS status
    FROM bronze_orders_raw ORDER BY ingest_ts;
    ```

    ```text
    +--------+-------------+-------+
    |order_id|first_product|status |
    +--------+-------------+-------+
    |1001    |3            |PLACED |
    |1002    |1            |PLACED |
    |1001    |3            |SHIPPED|
    +--------+-------------+-------+
    ```

    **Why:** `VARIANT` holds semi-structured data without a fixed schema, which is why the medallion docs suggest it
    for bronze. The `:` operator works on a `VARIANT` or on a `STRING` holding JSON; if the path does not exist, the
    result is NULL, not an error.

    **Learn more:** [Chapter 18](18-Semi-Structured-Data.md).

**Q106. Keep only the latest row per order without a subquery.**

??? success "Answer"
    `QUALIFY` filters on a window function the way `HAVING` filters on an aggregate.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, status, ingest_ts FROM silver_orders
    QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY ingest_ts DESC) = 1
    ORDER BY order_id;
    ```

    ```text
    +--------+-------+-------------------+
    |order_id|status |ingest_ts          |
    +--------+-------+-------------------+
    |1001    |SHIPPED|2026-03-02 08:00:00|
    |1002    |PLACED |2026-03-01 11:01:00|
    +--------+-------+-------------------+
    ```

    **Why:** use `row_number()` (exactly one row) rather than `rank()` (ties keep several rows). If two events can
    share a timestamp, add a tie-breaker to `ORDER BY` so reruns pick the same row.

    **Learn more:** [Chapter 17](17-Databricks-SQL-vs-Standard.md), [SQL course: ranking](../../databases/sql/13-Window-Functions-Ranking.md).

**Q107. Compute line totals, filter items and sum quantities inside an array column without exploding it.**

??? success "Answer"
    Higher-order functions take a lambda: `transform` maps each element, `filter` keeps some, `aggregate` folds them
    into one value, `exists` tests whether any element matches.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id,
           transform(items, i -> i.qty * i.unit_price)  AS line_totals,
           filter(items, i -> i.qty >= 2)               AS multi_qty,
           aggregate(items, 0, (acc, i) -> acc + i.qty) AS units,
           exists(items, i -> i.product_id = 5)         AS has_p5
    FROM silver_orders WHERE status = 'PLACED' ORDER BY order_id;
    ```

    ```text
    +--------+--------------+---------------+-----+------+
    |order_id|line_totals   |multi_qty      |units|has_p5|
    +--------+--------------+---------------+-----+------+
    |1001    |[59.90]       |[{3, 2, 29.95}]|2    |false |
    |1002    |[80.00, 40.00]|[{5, 4, 10.00}]|5    |true  |
    +--------+--------------+---------------+-----+------+
    ```

    **Why:** this keeps one row per order (no explode followed by a `GROUP BY` to put rows back together) and replaces
    Python UDFs over arrays (Q24).

    **Learn more:** [Chapter 18](18-Semi-Structured-Data.md).

**Q108. Turn the `items` array into one row per item.**

??? success "Answer"
    Use `explode` (in the `SELECT` list or with `LATERAL VIEW`). `posexplode` also returns the position; `inline`
    explodes an array of structs straight into columns.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, item.product_id, item.qty
    FROM silver_orders LATERAL VIEW explode(items) t AS item
    WHERE status = 'PLACED' ORDER BY order_id, item.product_id;
    ```

    ```text
    +--------+----------+---+
    |order_id|product_id|qty|
    +--------+----------+---+
    |1001    |3         |2  |
    |1002    |1         |1  |
    |1002    |5         |4  |
    +--------+----------+---+
    ```

    **Why:** `explode` produces no rows for an empty or NULL array, so those orders disappear; `explode_outer` (or
    `LATERAL VIEW OUTER`) keeps them with NULLs. That difference is a common "find the bug" question when order counts
    drop after flattening.

    **Learn more:** [Chapter 18](18-Semi-Structured-Data.md).

**Q109. Select all columns except two, and group by every non-aggregated column without listing them.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT * EXCEPT (items, ingest_ts) FROM silver_orders WHERE order_id = 1002;

    SELECT customer_id, currency, count(*) AS n, sum(amount) AS total
    FROM silver_orders GROUP BY ALL ORDER BY ALL;
    ```

    ```text
    +--------+-----------+-------------------+------+------+--------+
    |order_id|customer_id|order_ts           |status|amount|currency|
    +--------+-----------+-------------------+------+------+--------+
    |1002    |8          |2026-03-01 11:00:00|PLACED|120.00|CAD     |
    +--------+-----------+-------------------+------+------+--------+

    +-----------+--------+---+------+
    |customer_id|currency|n  |total |
    +-----------+--------+---+------+
    |7          |CAD     |2  |119.80|
    |8          |CAD     |1  |120.00|
    +-----------+--------+---+------+
    ```

    **Why:** look at customer 7: `n = 2` and `119.80`, because this table still has both events of order 1001. A sum
    over undeduplicated data double-counts. That is the kind of detail an interviewer hopes you notice.

    **Learn more:** [Chapter 17](17-Databricks-SQL-vs-Standard.md).

**Q110. For each order, return the latest status and count the `PLACED` events, in one `GROUP BY`.**

??? success "Answer"
    `max_by(value, ordering)` returns the value from the row with the largest ordering value; `count_if(cond)`
    counts rows where the condition is true.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, max_by(status, ingest_ts) AS latest_status,
           count_if(status = 'PLACED') AS placed_events
    FROM silver_orders GROUP BY order_id ORDER BY order_id;
    ```

    ```text
    +--------+-------------+-------------+
    |order_id|latest_status|placed_events|
    +--------+-------------+-------------+
    |1001    |SHIPPED      |1            |
    |1002    |PLACED       |1            |
    +--------+-------------+-------------+
    ```

    **Why:** `max_by` is an aggregate alternative to `QUALIFY` when you need one column from the latest row together
    with other aggregates.

    **Learn more:** Chapter 19.

**Q111. Make a target table mirror a full snapshot: update changed rows, insert new ones, delete missing ones.**

??? success "Answer"
    `MERGE` with `WHEN NOT MATCHED BY SOURCE` handles target rows that have no match in the source.

    The target had products 1, 3 and 5; the snapshot has 1 (new price), 3 and 6.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    MERGE INTO silver_products t
    USING (SELECT * FROM VALUES (1, 'Tent', 85.00), (3, 'Headlamp', 29.95), (6, 'Rope', 15.00)
           AS s(product_id, name, price)) s
    ON t.product_id = s.product_id
    WHEN MATCHED AND t.price <> s.price THEN UPDATE SET t.price = s.price
    WHEN NOT MATCHED THEN INSERT *
    WHEN NOT MATCHED BY SOURCE THEN DELETE;
    ```

    ```text
    +-----------------+----------------+----------------+-----------------+
    |num_affected_rows|num_updated_rows|num_deleted_rows|num_inserted_rows|
    +-----------------+----------------+----------------+-----------------+
    |3                |1               |1               |1                |
    +-----------------+----------------+----------------+-----------------+
    ```

    **Why:** only use an unconditional `NOT MATCHED BY SOURCE ... DELETE` when the source really is the complete
    set; with an incremental source it would delete everything not in today's batch. Databricks recommends adding a
    condition to limit the target rows touched. `WHEN MATCHED AND t.price <> s.price` avoids rewriting unchanged rows.

    **Learn more:** Chapter 20.

**Q112. Write an SCD Type 2 update with a single `MERGE`.**

??? success "Answer"
    Stage the source twice: once keyed by `customer_id` (to close the current row) and once with a NULL key (so it
    never matches and becomes the new current row). Only changed customers get the second copy.

    Customer 7 moved, 8 did not change, 9 is new.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    MERGE INTO dim_customer t
    USING (
      SELECT c.customer_id AS merge_key, c.* FROM customer_changes c
      UNION ALL
      SELECT NULL AS merge_key, c.* FROM customer_changes c
      JOIN dim_customer d ON c.customer_id = d.customer_id
      WHERE d.is_current AND d.city <> c.city
    ) s
    ON t.customer_id = s.merge_key AND t.is_current
    WHEN MATCHED AND t.city <> s.city THEN
      UPDATE SET t.is_current = false, t.valid_to = s.updated_at
    WHEN NOT MATCHED THEN
      INSERT (customer_id, city, valid_from, valid_to, is_current)
      VALUES (s.customer_id, s.city, s.updated_at, NULL, true);
    ```

    ```text
    +-----------+-------+-------------------+-------------------+----------+
    |customer_id|city   |valid_from         |valid_to           |is_current|
    +-----------+-------+-------------------+-------------------+----------+
    |7          |Calgary|2026-01-01 00:00:00|2026-03-05 00:00:00|false     |
    |7          |Canmore|2026-03-05 00:00:00|NULL               |true      |
    |8          |Banff  |2026-01-01 00:00:00|NULL               |true      |
    |9          |Jasper |2026-03-05 00:00:00|NULL               |true      |
    +-----------+-------+-------------------+-------------------+----------+
    ```

    **Why:** one `MERGE` is one atomic commit, so readers never see a customer with no current row or two current
    rows. If a tracked column can be NULL, `t.city <> s.city` misses a change from or to NULL; use the null-safe form
    `NOT (t.city <=> s.city)`. In a Lakeflow pipeline (formerly Delta Live Tables), `AUTO CDC ... STORED AS SCD TYPE 2` (formerly `APPLY CHANGES`) does all of this and also
    handles out-of-order changes (Q88).

    **Learn more:** [Chapter 9](09-Building-Silver.md), [SQL course: SCD](../../databases/sql/19-Data-Modelling.md).

**Q113. A daily load must replace exactly one day of a gold table. Which statement?**

??? success "Answer"
    `INSERT INTO ... REPLACE WHERE <predicate>` atomically replaces the rows matching the predicate with the query
    result, in one commit. It is idempotent: rerunning it for the same day gives the same table.

    A late order for March 1 arrived after gold was built:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    INSERT INTO gold_daily_sales REPLACE WHERE order_date = DATE'2026-03-01'
    SELECT to_date(order_ts), count(*), sum(amount) FROM silver_orders
    WHERE to_date(order_ts) = DATE'2026-03-01' GROUP BY ALL;
    ```

    ```text
    before                               after
    +----------+------+-------+          +----------+------+-------+
    |order_date|orders|revenue|          |order_date|orders|revenue|
    +----------+------+-------+          +----------+------+-------+
    |2026-03-01|2     |179.90 |          |2026-03-01|3     |219.90 |
    |2026-03-02|1     |35.50  |          |2026-03-02|1     |35.50  |
    +----------+------+-------+          +----------+------+-------+
    ```

    (The two results are printed one after the other in `ch24_delta.out`; they are placed side by side here.)

    **Why:** compared with `DELETE` then `INSERT`, there is no moment where the day is missing, and a failure leaves
    the old data in place. Make sure the query only produces rows that match the predicate.

    **Learn more:** Chapter 20.

**Q114. Show the ways to query an older version of a table, and how to see its changes.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Work with table history](https://docs.databricks.com/aws/en/delta/history).*

    ```sql
    SELECT * FROM shop.silver.orders VERSION AS OF 12;
    SELECT * FROM shop.silver.orders TIMESTAMP AS OF '2026-03-01T00:00:00Z';
    SELECT * FROM shop.silver.orders@v12;                    -- Databricks shorthand
    SELECT * FROM table_changes('shop.silver.orders', 12);   -- needs change data feed
    ```

    The `VERSION AS OF` and `table_changes` forms ran locally in Q32 and Q39; the `@v` form failed to parse in
    open-source Spark 4.2.

    **Why:** neither the version nor the timestamp can be a subquery, and the retention limits from Q32 apply.

    **Learn more:** Chapter 20.

**Q115. What is SQL pipe syntax?**

??? success "Answer"
    A way to write a query as a top-to-bottom chain of steps joined by `|>`, starting from `FROM`. Each step takes
    the previous result.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    FROM silver_orders
    |> WHERE status = 'PLACED'
    |> AGGREGATE count(*) AS orders, sum(amount) AS revenue GROUP BY currency;
    ```

    ```text
    +--------+------+-------+
    |currency|orders|revenue|
    +--------+------+-------+
    |CAD     |2     |179.90 |
    +--------+------+-------+
    ```

    **Why:** it reads in the order the data flows, which some teams find clearer for long transformations. It is
    optional; standard SQL gives the same result.

    **Learn more:** [Chapter 17](17-Databricks-SQL-vs-Standard.md).

## 24.11 Scenarios and troubleshooting

*Level: expert.*

Scenario questions have no single right answer. The interviewer wants a calm, ordered investigation: what you
look at first, what each finding would mean, and how you would stop it from happening again. Answer in steps.

**Q116. A daily job that took 20 minutes now takes two hours. What do you do?**

??? success "Answer"
    1. **Find what changed.** Compare the run history: did input volume grow, did the code, the runtime version or
       the cluster change? A sudden jump usually has a cause you can name.
    2. **Find the slow part.** In the Spark UI (or the query profile on SQL warehouses), find the stage that takes
       the time. Do not tune the whole job.
    3. **Read that stage.** Compare the slowest task with the median: one task far longer than the rest means skew
       (Q123). Large spill means too little memory per task (Q128). Many tiny tasks or a huge number of files means
       a small-files problem (Q118). A large shuffle on a join with a small table means a missing broadcast (Q19).
       Reading far more data than the query needs means pruning and data skipping are not working (Q134).
    4. **Fix the cause, one change at a time,** and measure again.
    5. **Prevent it:** alert on job duration, and keep table maintenance (`OPTIMIZE`, clustering, predictive
       optimization) running.

    **Why:** the trap is to answer "add more nodes". Bigger compute hides skew and small files for a while and
    raises cost. Say that you would check the data and the plan first.

    **Learn more:** Chapter 22.

**Q117. A job failed halfway and was rerun. Now silver has duplicate rows. Why, and how do you make the load safe
to rerun?**

??? success "Answer"
    The first attempt committed part of its writes before failing (for example, one task in the job had already
    appended its data), and the rerun appended the same rows again. A plain `INSERT` is not idempotent. The fix is
    to make every write give the same result no matter how often it runs:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    load = "SELECT * FROM VALUES (1, 10.00), (2, 20.00) AS s(payment_id, amount)"
    for run in range(2):                       # the same load, twice
        sql(f"INSERT INTO silver_payments {load}")
    # count -> 4

    sql("TRUNCATE TABLE silver_payments")
    for run in range(2):                       # the same load, twice, as MERGE
        sql(f"""MERGE INTO silver_payments t USING ({load}) s ON t.payment_id = s.payment_id
                WHEN NOT MATCHED THEN INSERT *""")
    # count -> 2
    ```

    ```text
    rows_after_two_appends = 4
    rows_after_two_merges  = 2
    ```

    Idempotent patterns: `MERGE` on the business key; `INSERT ... REPLACE WHERE` for a date slice (Q113);
    streaming with a checkpoint (Q76); `txnAppId` and `txnVersion` for batch writes that may be retried; in a
    Lakeflow Job (formerly Databricks Workflows), repair the run so only the failed tasks run again. Then clean up the existing duplicates once,
    for example by rewriting the table from a `QUALIFY row_number() ... = 1` query (Q106).

    **Why:** "make every step safe to run twice" is the single most valued habit in data engineering interviews.

    **Learn more:** [Chapter 9](09-Building-Silver.md), Chapter 15,
    [SQL course: duplicates and incremental loads](../../databases/sql/22-Duplicates-and-Incremental-Loads.md).

**Q118. Queries on a bronze table get slower every week. The table has hundreds of thousands of tiny files. What
happened, and what do you do?**

??? success "Answer"
    1. **Confirm:** `DESCRIBE DETAIL` shows `numFiles` and `sizeInBytes`; divide to get the average file size.
    2. **Cause:** frequent small appends (a stream with a short trigger interval, or many small batch inserts) each
       write new small files. Every query must open them all, and planning reads more metadata.
    3. **Fix now:** run `OPTIMIZE` to compact them (Q35 shows 20 files becoming 1).
    4. **Fix for good:** enable predictive optimization on managed tables, use liquid clustering, use a longer
       trigger interval or `availableNow` where latency allows, and avoid partitioning small tables on
       high-cardinality columns (each partition gets its own files).
    5. **Afterward:** old files stay until `VACUUM` removes them after the retention period.

    **Why:** tiny files also raise cloud storage API costs, especially with the default streaming trigger (Q73).

    **Learn more:** Chapter 22, [Chapter 4](04-Delta-Lake.md).

**Q119. An order from yesterday arrives today. Yesterday's revenue in gold is now wrong. How do you correct it
without rebuilding the whole table?**

??? success "Answer"
    1. Find which business dates the new silver rows touch: for example, the distinct `order_date` values in rows
       ingested since the last gold run (an ingest timestamp column in silver makes this easy; CDF works too).
    2. Recompute gold only for those dates and replace them atomically with `INSERT INTO ... REPLACE WHERE
       order_date IN (...)`; Q113 shows one day going from 2 orders to 3.
    3. Or define gold as a materialized view and let the refresh handle it.
    4. Tell consumers that recent days can still change, and how far back (for example, "the last 7 days are
       provisional").

    **Why:** a streaming aggregate with a watermark would drop events this late (Q77). Late data is a business
    question first ("how late can it be, and must it count?"), then a design choice.

    **Learn more:** Chapter 10, Chapter 20.

**Q120. The source team changed `amount` from a number to text such as `'12.50 CAD'`. The silver load fails. What
do you do?**

??? success "Answer"
    The write fails because the value cannot be cast to the table's `DECIMAL(10,2)` column. That is schema
    enforcement protecting silver, which is good.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    bad_type = spark.createDataFrame([(1006, "12.50 CAD")], "order_id INT, amount STRING")
    bad_type.write.format("delta").mode("append").saveAsTable("silver_orders")
    ```

    ```text
    ERROR: [CAST_INVALID_INPUT] The value '12.50 CAD' of the type "STRING" cannot be cast to "DECIMAL(10,2)"
    because it is malformed. Correct the value as per the syntax, or change its target type. Use `try_cast` to
    tolerate malfor...
    ```

    Steps:

    1. Bronze is unaffected if it stores the raw value (string or `VARIANT`), so no data is lost (Q47).
    2. Agree with the source team what the new format means: is the currency now inside the field?
    3. Change the silver transformation: split the text, cast with `try_cast`, and send rows where the cast returns
       `NULL` to a quarantine table instead of failing the load or silently writing `NULL`s.
    4. Reprocess the affected bronze rows into silver.
    5. Add a data contract or an expectation so the next change is caught at the boundary.

    **Why:** do not "fix" it by changing the silver column to `STRING`; that pushes the problem to every consumer.

    **Learn more:** [Chapter 9](09-Building-Silver.md), [Chapter 4](04-Delta-Lake.md).

**Q121. The monthly Databricks bill doubled. How do you find out why?**

??? success "Answer"
    1. **Find where:** query `system.billing.usage` by day and by `billing_origin_product`, `sku_name` and
       `usage_metadata.job_id` / `dlt_pipeline_id` / `warehouse_id` (Q104 has the query). Find when the jump
       started and which job, pipeline or warehouse owns it. Sum `usage_quantity` so correction records cancel out.
    2. **Usual causes:** a pipeline switched from triggered to continuous mode; a stream left on the default
       trigger; a full refresh of a large table; scheduled jobs running on all-purpose compute instead of job
       compute; autoscaling limits raised; a warehouse that never stops; a job that now reprocesses everything
       because its checkpoint was reset (Q136).
    3. **Fix** the specific cause, then add guard rails: tags (`custom_tags`) per team or project, budgets and
       alerts, compute policies, and a weekly cost review.

    **Why:** the interviewer wants to see that you measure first with the system tables instead of guessing.

    **Learn more:** Chapter 23, [Chapter 6](06-Compute.md).

**Q122. An Auto Loader stream stopped overnight after a new column appeared in the files. How should this be
handled?**

??? success "Answer"
    This is expected behavior in the default `addNewColumns` mode: when Auto Loader detects a new column, it
    updates the schema in the schema location (adding the column at the end) and stops the stream with an
    `UnknownFieldException`. Restarting the stream picks up the new schema. Databricks recommends running Auto
    Loader streams in Lakeflow Jobs (formerly Databricks Workflows) configured to restart automatically after such schema changes; in a Lakeflow
    pipeline, Databricks manages the schema location and checkpoints for you.

    Steps: confirm the error is `UnknownFieldException`; restart (or check why the automatic retry did not
    happen); decide whether silver needs the new column; if you never want the stream to stop, choose another
    `cloudFiles.schemaEvolutionMode` (such as `rescue`, which keeps unknown fields in `_rescued_data`) and accept
    that new columns then need an explicit change.

    **Why:** a stream reading a Delta table also fails when the source schema changes; for most schema changes a
    restart resolves it (Q82).

    **Learn more:** [Chapter 8](08-Bronze-Ingestion.md).

**Q123. One stage of a join has 199 tasks that finish in seconds and one that runs for an hour. What is going on?**

??? success "Answer"
    Data skew: one join key (often `NULL`, a default value or a very large customer) holds a large share of the
    rows, so one task gets them all.

    1. Confirm: count rows per join key and look at the top keys (Q21 shows one key with 90,000 of the rows).
    2. If the key is junk (`NULL`, `-1`), filter it out or handle it separately before the join.
    3. Check that AQE skew join handling is on (it is by default) and look at whether it split the partition.
    4. If one side is small enough, broadcast it, which removes the shuffle.
    5. Otherwise salt the hot key: add a random suffix on the big side and replicate the small side once per
       suffix (Q21 has the code).

    **Why:** more memory or more nodes does not help; the one task still gets all the data for its key.

    **Learn more:** Chapter 22, [Chapter 3](03-Apache-Spark.md).

**Q124. Someone ran a `DELETE` without a `WHERE` clause on a silver table an hour ago. Recover the data.**

??? success "Answer"
    1. Stop the writers that depend on the table, so nothing builds on the bad version.
    2. `DESCRIBE HISTORY` to find the last good version (the one before the `DELETE`).
    3. Check it: `SELECT count(*) ... VERSION AS OF n`.
    4. Restore: `RESTORE TABLE ... TO VERSION AS OF n` (Q33 shows the run). `RESTORE` is itself a new commit, so it
       can be undone.
    5. If good writes happened after the bad one, do not restore the whole table; re-insert only the missing rows
       from the old version instead:

    *Databricks only, not run here. Syntax from [Work with table history](https://docs.databricks.com/aws/en/delta/history).*

    ```sql
    INSERT INTO shop.silver.orders
    SELECT * FROM shop.silver.orders VERSION AS OF 41
    EXCEPT ALL
    SELECT * FROM shop.silver.orders;
    ```

    6. If the table was dropped rather than emptied, a managed Unity Catalog table can be recovered with
       `UNDROP TABLE` within 7 days.
    7. Afterward: tighten `MODIFY` privileges, and check whether downstream streams now need attention (a stream
       reading this table fails on the `DELETE` and the restore; see Q82).

    **Why:** time travel only works within the retention window and only if `VACUUM` has not removed the files.
    Mention that, and that `RESTORE` is not a substitute for backups of very old data.

    **Learn more:** [Chapter 4](04-Delta-Lake.md).

**Q125. A streaming `MERGE` into silver suddenly fails with "multiple source rows matched". Nothing in the code
changed. Why?**

??? success "Answer"
    The code always had the bug; the data changed. A micro-batch now contains two changes for the same key (for
    example, `PLACED` and `SHIPPED` for one order arriving together, or a duplicate delivery). A `MERGE` cannot
    update one target row from two source rows. Fix: deduplicate the source inside `foreachBatch` before the
    `MERGE`, keeping the latest row per key by a sequence column or event time (Q79 does this; Q43 shows the error
    and the `QUALIFY` fix). Or use `AUTO CDC` (formerly `APPLY CHANGES`) in a pipeline, which orders changes by a sequence column for you.

    **Why:** small test data rarely contains two changes for one key in the same batch, so this bug often appears
    first in production.

    **Learn more:** [Chapter 9](09-Building-Silver.md), Chapter 14.

**Q126. A nightly `MERGE` job sometimes fails with `ConcurrentAppendException`. What is happening?**

??? success "Answer"
    Another write committed files that your `MERGE` had read, between the moment your `MERGE` read the table and
    the moment it tried to commit. Delta's optimistic concurrency then fails one of them.

    1. Find the other writer in `DESCRIBE HISTORY` (look at the commits around the failure time).
    2. Under the default WriteSerializable isolation, `INSERT`s that only append (blind appends) never conflict with
       each other, and when an `INSERT` and a `MERGE` collide, the `MERGE` is the one that fails. So retry logic
       belongs on the `UPDATE`, `DELETE` or `MERGE`, not on the `INSERT`.
    3. Make the writers touch disjoint data and say so explicitly in the `MERGE` condition (for example, add the
       date or region to the `ON` clause), so Delta can tell they do not overlap.
    4. Or schedule the conflicting jobs so they do not run at the same time.
    5. On Databricks Runtime 14.3 LTS and above, tables without partitions and with deletion vectors enabled get
       row-level concurrency, which resolves conflicts when the writers change different rows of the same file.

    **Why:** a metadata change, such as `ALTER TABLE` or a write that changes the schema, can make all concurrent
    writes fail, including `INSERT`s. Schedule schema changes outside load windows.

    **Learn more:** [Chapter 4](04-Delta-Lake.md), Chapter 22.

**Q127. A notebook crashes with a driver out-of-memory error. What do you check?**

??? success "Answer"
    1. Look for code that brings data to the driver: `collect()`, `toPandas()`, a large `show()`, or a Python loop
       over rows.
    2. Look for a broadcast of a table that is not actually small (the broadcast is built through the driver), for
       example a forced broadcast hint on a table that has grown.
    3. Look for very large query plans built in a loop (thousands of `withColumn` or `union` calls).
    4. Fix by keeping the work distributed: write results to a table, use `limit()` or `take(n)` to look at
       samples, aggregate before collecting, and replace row loops with DataFrame operations.
    5. Only after that, consider a bigger driver.

    **Why:** the driver is a single machine. Anything that scales with data volume must run on the executors.

    **Learn more:** [Chapter 3](03-Apache-Spark.md), Chapter 22.

**Q128. Executors fail with out-of-memory errors, or tasks spill heavily, during a large aggregation. What do you
do?**

??? success "Answer"
    1. In the Spark UI, check whether all tasks spill (partitions too large for the memory per task) or only a few
       (skew; see Q123).
    2. If all: make partitions smaller, for example by letting AQE coalesce from a higher number of shuffle
       partitions or by setting more shuffle partitions; select only needed columns before the shuffle; filter
       early.
    3. If a few: fix the skew.
    4. Check for exploding joins (a many-to-many key creates far more rows than expected).
    5. Then consider memory-optimized instances.

    **Why:** spill is not an error, but it is slow; an OOM is often the same problem one step further.

    **Learn more:** Chapter 22.

**Q129. A streaming aggregation gets slower every day, and its checkpoint keeps growing. Why?**

??? success "Answer"
    Its state is growing without bound. Usual causes: no watermark on the aggregation, deduplication or
    stream-stream join; a watermark on a column the aggregation does not group by (state for an aggregation can only
    be cleaned when it groups by the event-time column or a window on it); complete output mode, which never drops
    state; or a very long watermark.

    Fix: add or shorten the watermark, group by a window on the event-time column, use append or update mode, and
    use `dropDuplicatesWithinWatermark` instead of `dropDuplicates` without a watermark. Databricks recommends the
    RocksDB state store with changelog checkpointing for stateful streams. Changing stateful operations usually
    needs a new checkpoint (Q75), so plan the restart.

    **Why:** state is the hidden cost of streaming. An interviewer expects you to connect "slower every day" with
    "state grows forever".

    **Learn more:** [Chapter 11](11-Structured-Streaming.md).

**Q130. A stream into bronze writes thousands of tiny files per hour and the cloud storage bill went up. What do you
change?**

??? success "Answer"
    Set an explicit trigger. The default trigger checks for new data every few milliseconds and can generate a high
    volume of cloud storage API calls; each micro-batch also writes small files. Use a `processingTime` interval
    that matches the real latency need, or `availableNow` on a schedule if minutes or hours are fine. Compact with
    `OPTIMIZE` or predictive optimization. For Auto Loader, consider file notification mode, which avoids listing
    the input directory repeatedly.

    **Why:** latency costs money. Ask what freshness the consumer actually needs before choosing the trigger.

    **Learn more:** [Chapter 11](11-Structured-Streaming.md), [Chapter 8](08-Bronze-Ingestion.md).

**Q131. A customer asks to have their data deleted (GDPR). Their rows are in bronze, silver and gold. How do you
remove them for real?**

??? success "Answer"
    A `DELETE` alone is not enough: old versions keep the rows for time travel, and with deletion vectors the
    `DELETE` may only mark rows as deleted.

    *Databricks only, not run here. Syntax from [Deletion vectors in Databricks](https://docs.databricks.com/aws/en/delta/deletion-vectors).*

    ```sql
    DELETE FROM shop.silver.customers WHERE customer_id = 4711;
    REORG TABLE shop.silver.customers APPLY (PURGE);   -- rewrite files that hold soft-deleted rows
    VACUUM shop.silver.customers;                      -- remove old files after the retention period
    ```

    Steps:

    1. Find every table that holds the customer's data; Unity Catalog lineage helps find downstream copies.
    2. Delete in every layer, including bronze. If bronze is append-only raw data, design for this early (for
       example, keep personal data in a separate table keyed by customer, so one delete covers it).
    3. Run `REORG TABLE ... APPLY (PURGE)` where deletion vectors are enabled, then `VACUUM` once the retention
       threshold has passed, so the old files are physically removed. Change data feed files in `_change_data` are
       also removed by `VACUUM`.
    4. Streams reading these tables will fail on the `DELETE`; use `skipChangeCommits` on them (Q82).
    5. Record what was deleted and when.

    **Why:** the interviewer checks that you know time travel retains deleted data until `VACUUM`, and that
    deletes ripple into streaming consumers.

    **Learn more:** [Chapter 4](04-Delta-Lake.md), Chapter 23.

**Q132. The silver table is updated with `MERGE` every hour. A gold stream reading silver keeps failing. How do you
redesign it?**

??? success "Answer"
    A Delta streaming source accepts only appends; each `MERGE` rewrites files and fails the stream. Options, from
    most to least common: enable change data feed on silver and stream the changes into gold, applying updates and
    deletes explicitly (Databricks recommends streaming from the change feed whenever possible); make gold a
    materialized view that is refreshed incrementally; use `skipChangeCommits` if gold only needs new rows and
    updates do not matter. See Q82 for the full list.

    **Why:** this is the most common real-world surprise when people first chain streams through a medallion
    architecture.

    **Learn more:** [Chapter 11](11-Structured-Streaming.md), Chapter 10.

**Q133. A pipeline expectation with `ON VIOLATION FAIL UPDATE` stopped the 3 a.m. run. What do you do?**

??? success "Answer"
    1. The failing update was rolled back atomically, so the target table still holds the last good data;
       consumers see stale but correct data.
    2. Open the pipeline's event log (or the monitoring UI) to see which expectation failed and on which records.
    3. Decide: is the data wrong (fix upstream or exclude the rows), or is the rule wrong (fix the rule)?
    4. Rerun. Scheduled updates already retry recoverable failures, but a data quality failure fails again until
       the data or the rule changes; re-run only what failed.
    5. Long term, reserve `FAIL UPDATE` for rules where bad data must never land (for example, a broken key), and
       use drop plus a quarantine table for the rest (Q87), so one bad row does not stop the whole pipeline.

    **Why:** the trade-off is freshness versus correctness. Say which tables deserve which policy.

    **Learn more:** Chapter 14, Chapter 13.

**Q134. A filter on a large table is slow even though you run `OPTIMIZE` every night. Why might data skipping not
work?**

??? success "Answer"
    1. **No statistics on the column:** for external tables, statistics are collected on the first 32 columns of
       the schema by default; a filter on column 40 skips nothing. Move the column, or set
       `delta.dataSkippingStatsColumns` (on managed tables with predictive optimization, statistics columns are
       chosen for you).
    2. **Data not clustered on the column:** min/max statistics only help if each file holds a narrow range. Use
       liquid clustering on the columns used in filters.
    3. **Filter hides the column:** a function or a cast on the column (for example `date_format(order_ts, ...)`)
       can prevent skipping; filter on the raw column with a range instead.
    4. **Check the query profile:** compare files or bytes read with the table size to see whether pruning happened.

    **Why:** `OPTIMIZE` compacts files; without clustering on the filter column it does not make filters faster.

    **Learn more:** Chapter 22.

**Q135. You must backfill two years of history into a pipeline that already processes new data every day. How?**

??? success "Answer"
    1. Model the backfill as its own one-time flow writing into the same target as the regular incremental flow;
       this is the pattern the Databricks backfill page describes (an append flow with the `ONCE` option, which
       runs each backfill exactly once).
    2. For a CDC target, use `AUTO CDC` (formerly `APPLY CHANGES`) with a `once` flow for the initial load, then the regular flow for ongoing
       changes.
    3. For a plain stream, process the history with `availableNow` and cap the batch size (`maxFilesPerTrigger`,
       `maxBytesPerTrigger`) so it runs in manageable micro-batches.
    4. Load in chunks (for example a month at a time), validate counts and totals against the source after each
       chunk, and make each chunk idempotent so a failed chunk can simply be rerun.
    5. Run the backfill on separate compute, so it does not slow the daily load.

    **Why:** avoid a full refresh of a streaming table as a backfill method: it truncates the table, and data the
    source no longer retains is lost (Q91).

    **Learn more:** Chapter 13, Chapter 14.

**Q136. After a deployment, a stream reprocessed all its source data and silver is full of duplicates. What
happened?**

??? success "Answer"
    The checkpoint location changed (a renamed path, a new environment variable, a different job parameter) or
    the checkpoint was deleted. A query with a new checkpoint starts fresh and reads everything the source still
    has.

    1. Stop the stream. Confirm by comparing the configured checkpoint path with the old one.
    2. Restore the old checkpoint path if it still exists, and restart.
    3. Clean silver: restore it to the version before the duplicates (Q124), or deduplicate it.
    4. Prevent it: keep checkpoint paths fixed per table in configuration (for example in a Declarative Automation Bundle, formerly Databricks Asset Bundle), never
       derived from things that change between deployments, and make silver writes idempotent (`MERGE` on the key)
       so a replay cannot create duplicates.

    **Why:** if the stream started from the latest offsets instead, the opposite happens: data is skipped. Either
    way, the checkpoint is part of the table's state and must be treated like data.

    **Learn more:** [Chapter 11](11-Structured-Streaming.md), Chapter 16.

**Q137. The finance team says the gold revenue does not match the source system. How do you investigate?**

??? success "Answer"
    1. **Pin down the definitions:** same date range, same time zone, same currency, same status filter (are
       cancelled orders included?), gross or net.
    2. **Compare layer by layer:** row counts and sums per day in source, bronze, silver and gold. The first layer
       where the numbers diverge contains the cause.
    3. **Typical causes:** dropped rows in silver (an expectation with drop, a failed cast, an inner join to a
       dimension with missing keys), duplicates (Q117), late data not yet in gold (Q119), time zone boundaries,
       SCD Type 2 joins without a date condition (one order joins several customer versions).
    4. **Fix and prevent:** add automated reconciliation checks (counts and totals per day, compared with the
       source) to the pipeline and alert on differences.

    **Why:** the answer shows method. Saying "I would compare the layers to find where the numbers split" is
    stronger than guessing a cause.

    **Learn more:** Chapter 10, Chapter 14.

## 24.12 Migration, cost control and table formats

*Level: intermediate to expert.*

**Q138. How would you migrate an existing data warehouse and its ETL (for example SQL Server with SSIS, or Oracle
with Informatica) to Databricks?**

??? success "Answer"
    In phases, with a reconciliation gate before anything is switched off:

    1. **Assess.** Inventory sources, warehouse tables, ETL packages or mappings, stored procedures, schedules,
       reports and their consumers, SLAs and dependencies. Classify each by size and complexity. Pick a first slice:
       one subject area with clear business value and manageable complexity.
    2. **Build the foundation.** Unity Catalog catalogs per environment (or per domain), storage, groups and
       grants, networking to the sources, compute policies, and CI/CD with Declarative Automation Bundles (formerly
       Databricks Asset Bundles). Decide naming and the medallion layout once.
    3. **Move the data.** Load history into bronze and silver Delta tables (a one-time bulk load), then set up
       incremental ingestion: a Lakeflow Connect database connector where the source is supported (the connector
       page lists MySQL, PostgreSQL and SQL Server), otherwise an existing CDC tool writing to cloud storage and
       read with Auto Loader, or scheduled JDBC reads.
    4. **Convert the logic.** SSIS packages and Informatica mappings are not SQL code, so they are rebuilt, not
       copied: as SQL or PySpark in Lakeflow pipelines (formerly Delta Live Tables) or notebooks, orchestrated by
       Lakeflow Jobs (formerly Databricks Workflows). Stored procedures in T-SQL or PL/SQL are converted to
       Databricks SQL; Databricks documents a code converter for dialects such as T-SQL and Oracle. Replace
       truncate-and-reload and row-by-row loops with set-based, incremental logic (`MERGE`, `AUTO CDC` (formerly
       `APPLY CHANGES`)).
    5. **Run in parallel and reconcile.** Run old and new side by side for several cycles. Compare row counts,
       sums of key measures and per-day totals for every table, and have the business sign off on the reports.
    6. **Cut over.** Repoint reports and BI tools to SQL warehouses, switch the schedules, keep the old system
       read-only for an agreed period, and have a rollback plan.
    7. **Decommission and optimize.** Turn off the old jobs, then tune cost (Q140) and table layout.

    Differences to plan for, from the Databricks migration page: Unity Catalog uses three-level names
    (`catalog.schema.table`); primary and foreign keys are informational only, not enforced; data types and
    numeric precision can differ, so decide target types explicitly. Transactions are traditionally per table,
    with each statement its own transaction; the warehouse migration page still says so, while newer pages describe
    multi-table transactions on tables with catalog commits, so check what your workspace supports before
    porting procedures that rely on `BEGIN TRANSACTION`.

    **Why:** the interviewer is checking for risk management: phases, a first slice, parallel runs and
    reconciliation. "Lift and shift everything over a weekend" is the wrong answer. Databricks notes that SQL
    workloads usually need little refactoring, but pipelines written in other languages (an SSIS package, for
    example) may need heavy refactoring.

    **Learn more:** [Chapter 7](07-Medallion-Architecture.md), Chapter 12,
    [Chapter 17](17-Databricks-SQL-vs-Standard.md).

**Q139. Serverless or classic compute: how do you decide, from a cost point of view?**

??? success "Answer"
    | | Serverless | Classic |
    | --- | --- | --- |
    | Who runs the machines | Databricks, in its account | Your cloud account |
    | What you pay | DBUs; for serverless the DBU price already includes the virtual machine cost | DBUs plus the cloud provider's virtual machines, disks and network |
    | Start-up and idle time | Fast start-up and scaling, minimal idle time | Slower start-up; idle time costs money unless auto-termination is set |
    | Control | Fewer knobs; streaming in serverless jobs only with `AvailableNow` (or the deprecated `Once`) | Instance types, spot instances, pools, init scripts |

    Serverless suits bursty and short workloads: interactive notebooks, short jobs, and BI on serverless SQL
    warehouses, which start and scale in seconds, so they can be stopped when idle. Non-serverless warehouses take
    minutes to start, and the docs note that users then tend to leave them running. Classic compute suits workloads
    that need its controls.

    **Why:** do not claim one is always cheaper. Measure: run the job both ways and compare the cost per run in
    `system.billing.usage` (Q104).

    **Learn more:** [Chapter 6](06-Compute.md), Chapter 23.

**Q140. A team runs all its scheduled ETL notebooks on one large all-purpose cluster that stays on all day. What do
you change?**

??? success "Answer"
    1. **Move scheduled work to job compute** (or serverless jobs). The Databricks cost guide says non-interactive
       workloads cost significantly less on job compute than on all-purpose compute. Each job can get its own
       compute (isolation), and a multitask job can reuse one compute resource across tasks so the start-up time
       is paid once.
    2. **Set auto-termination** on the remaining interactive compute: after the configured inactivity period (in
       minutes) Databricks terminates it.
    3. **Turn on autoscaling** with sensible minimum and maximum workers; it can reduce cost compared with a
       statically sized cluster. For streaming, autoscaling has limitations when scaling down; Databricks
       recommends Lakeflow pipelines (formerly Delta Live Tables) with enhanced autoscaling instead.
    4. **Enforce it with compute policies:** require autoscaling and auto-termination, limit instance types and
       maximum workers.
    5. **Other levers:** spot instances for workers with an on-demand driver; pools to cut start-up time (no DBUs
       are charged while instances sit idle in a pool, but the cloud provider still bills them).

    **Why:** this is the most common cost finding in real workspaces; the interviewer wants the specific levers,
    not "use smaller clusters".

    **Learn more:** [Chapter 6](06-Compute.md), Chapter 15.

**Q141. Photon makes the job faster. Does that mean it is cheaper?**

??? success "Answer"
    Not automatically. Photon instance types consume DBUs at a different rate than the same instance type without
    Photon, so the question is whether the job is faster by more than the rate difference. The Databricks cost
    guide says to evaluate regularly run jobs to see whether they are not only faster but also cheaper with Photon.
    Photon helps most on longer queries over large data. It brings no meaningful gain for queries that normally
    finish in under two seconds, it does not support UDFs, RDD or Dataset APIs (that work falls back to Spark), and
    it does not support stateful streaming. SQL warehouses come with Photon by default.

    **Why:** cost per run is the metric, not run time. Compare both in the job's run history and in
    `system.billing.usage`.

    **Learn more:** [Chapter 6](06-Compute.md), Chapter 22.

**Q142. How do you right-size a classic cluster for a batch job?**

??? success "Answer"
    1. **Know what drives size:** Databricks runs one executor per worker, so think in total executor cores
       (maximum parallelism), total executor memory (how much fits before spilling) and local storage (spill and
       caching). Ask: how much data is read, how complex is the work, where is the data read from, how is it laid
       out, and how much parallelism is needed?
    2. **Start from a standard:** the cost guide suggests, for example, a medium cluster (8-16 workers) with
       memory-optimized instances and autoscaling for batch ETL, and small clusters (2-4 workers) with autoscaling
       for development.
    3. **Pick the instance family from the workload:** memory-optimized for heavy shuffle and spill;
       compute-optimized for streaming and maintenance jobs such as `OPTIMIZE` and `VACUUM`; storage-optimized for
       workloads that benefit from caching.
    4. **Measure and adjust:** look at CPU use, spill and idle executors in the Spark UI and the cluster metrics.
       Low CPU with no spill means the cluster is too big; heavy spill means more memory per core.
    5. **Fix the job before sizing up:** skew, small files and missing broadcasts are not solved by more workers
       (Q116).

    **Why:** right-sizing is a loop, not a one-time guess. Compute policies with T-shirt sizes make the standard
    the default for everyone.

    **Learn more:** [Chapter 6](06-Compute.md), Chapter 22.

**Q143. What does predictive optimization cost, and when would you still schedule `OPTIMIZE` yourself?**

??? success "Answer"
    Predictive optimization automatically runs `OPTIMIZE`, `VACUUM` and `ANALYZE` on Unity Catalog managed tables
    (Delta Lake and Iceberg). It is enabled by default, inherited from the account, and can be turned on or off per
    catalog, schema or table. It runs on serverless compute for jobs and is billed under a serverless jobs SKU. The
    system table `system.storage.predictive_optimization_operations_history` shows what it ran and what it cost.
    Even if `delta.deletedFileRetentionDuration` is set below 7 days, it keeps data files for at least 7 days when it
    runs `VACUUM FULL`.

    You still run maintenance yourself on external tables (it covers managed tables only), or when you need it at
    a specific moment, for example `OPTIMIZE ... FULL` to recluster after changing clustering keys.

    **Why:** the trade-off is a small, visible compute cost against small files, stale statistics and storage
    kept for old files. On managed tables, hand-written maintenance jobs that repeat the same work are usually
    redundant.

    **Learn more:** Chapter 22, [Chapter 4](04-Delta-Lake.md).

**Q144. How do you show each team what it spends on Databricks?**

??? success "Answer"
    1. **Tag** workspaces, clusters, SQL warehouses and pools, for example with business unit, project and
       environment tags. Custom tags propagate to `system.billing.usage` (the `custom_tags` column) and to the
       cloud provider's resources. Tags apply only to future usage, so set them from the start.
    2. **Serverless usage** is attributed with usage policies, which apply tags to the serverless activity of the
       users assigned to them.
    3. **Report** from `system.billing.usage` grouped by tag, product and job, or with the cost management
       dashboards from the account console.
    4. **Control** with budgets and email alerts when a monthly budget is reached, and review costs monthly with
       each team.

    **Why:** cost questions in interviews are really about ownership: who sees the bill, and what they can do
    about it.

    **Learn more:** Chapter 23.

**Q145. Delta Lake, Apache Iceberg or Apache Hudi: what is the difference?**

??? success "Answer"
    All three are open table formats: Parquet data files plus a metadata layer that adds ACID transactions, time
    travel and schema evolution on object storage. The differences that come up in interviews:

    | | Delta Lake | Apache Iceberg | Apache Hudi |
    | --- | --- | --- | --- |
    | Metadata | A transaction log of ordered JSON commits plus Parquet checkpoints in `_delta_log` | New metadata files written for each table change; a catalog returns the current metadata | A timeline of changes, plus indexes maintained by writes |
    | Known for | Default on Databricks; deletion vectors, change data feed, liquid clustering | Hidden partitioning and partition evolution; a REST catalog API supported by many engines | Fast upserts and deletes using record-level indexes; incremental and change data capture queries |
    | On Databricks | Default table format | Managed Iceberg tables in Unity Catalog (Databricks Runtime 16.4 LTS and above); foreign Iceberg tables are read-only | Not covered by the Databricks pages used here |

    Hudi is usually described with two table types, copy-on-write and merge-on-read, which trade write cost against
    read cost.

    **Why:** the honest answer to "which is best?" is that it depends on the engines and the catalog the company
    uses. On Databricks, Delta is the default, and interoperability features (Iceberg reads on Delta tables, Q146,
    and the Iceberg REST catalog for managed Iceberg tables) reduce the lock-in question.

    **Learn more:** [Chapter 4](04-Delta-Lake.md), [Chapter 5](05-Unity-Catalog.md).

**Q146. Other teams query with an Iceberg engine. How can they read your Delta tables on Databricks?**

??? success "Answer"
    Enable **Iceberg reads** (UniForm) on the Delta table. Databricks then generates Iceberg metadata asynchronously
    alongside the Delta metadata, without rewriting the Parquet files, so one copy of the data serves both Delta and
    Iceberg clients. Unity Catalog can act as the Iceberg catalog for those clients.

    *Databricks only, not run here. Syntax from [Read Delta Lake tables with Iceberg clients](https://docs.databricks.com/aws/en/delta/uniform).*

    ```sql
    ALTER TABLE shop.gold.daily_sales SET TBLPROPERTIES(
      'delta.columnMapping.mode' = 'name',
      'delta.enableIcebergCompatV2' = 'true',
      'delta.universalFormat.enabledFormats' = 'iceberg');
    ```

    Requirements and limits from that page: the table is registered in Unity Catalog (managed or external), column
    mapping is enabled, writes use Databricks Runtime 14.3 LTS or above (enabling it on an existing table needs
    15.4 LTS or above), Iceberg clients can only read, and deletion vectors cannot be enabled on the table (use
    `REORG TABLE ... APPLY (UPGRADE UNIFORM(ICEBERG_COMPAT_VERSION=2))` on a table that has them). Data files use
    Zstandard compression, and metadata generation runs on the writing compute.

    If external engines must also **write**, use a managed Iceberg table in Unity Catalog instead: external engines
    read and write it through the Iceberg REST Catalog API.

    **Why:** the follow-up is usually "what do you give up?": deletion vectors on that table, and writes from
    the Iceberg side.

    **Learn more:** [Chapter 4](04-Delta-Lake.md), [Chapter 5](05-Unity-Catalog.md).

## 24.13 System design 1: late-arriving events from Kafka to dashboards

*Level: expert.*

**The question.** "An online store publishes clickstream events and order events to Kafka. Product managers want
dashboards of page views and orders per product, refreshed every few minutes. Events can arrive late, for example
from mobile apps that were offline. Design the pipeline."

**1. Clarify.** Ask, and write down the answers (or your assumptions):

| Question | Assumption for this walkthrough |
| --- | --- |
| Volume? | About 50 million events a day, peaks five times the average |
| Freshness? | Dashboards within 5 minutes |
| How late can events arrive? | Most within minutes; some mobile events up to 3 days |
| Must late events count? | In daily numbers yes; in the live tiles, approximate is fine |
| Duplicates? | Producers retry, so the same event can arrive twice; each event has an `event_id` |
| History? | Keep raw events for reprocessing; Kafka retention is limited (assume 7 days) |

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Kafka feeds a bronze streaming table, then silver, then two gold paths: a live windowed aggregate and a daily corrected aggregate, both read by dashboards on a SQL warehouse. Late events beyond the watermark reach the corrected path.">
<defs><marker id="a24b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="6" y="100" width="96" height="80" rx="8"/>
<rect x="124" y="100" width="110" height="80" rx="8"/>
<rect x="256" y="100" width="118" height="80" rx="8"/>
<rect x="398" y="30" width="122" height="80" rx="8"/>
<rect x="398" y="170" width="122" height="80" rx="8"/>
<rect x="540" y="100" width="94" height="80" rx="8"/>
<line x1="102" y1="140" x2="122" y2="140" marker-end="url(#a24b)"/>
<line x1="234" y1="140" x2="254" y2="140" marker-end="url(#a24b)"/>
<line x1="374" y1="125" x2="396" y2="80" marker-end="url(#a24b)"/>
<line x1="374" y1="155" x2="396" y2="200" marker-end="url(#a24b)"/>
<line x1="520" y1="80" x2="538" y2="120" marker-end="url(#a24b)"/>
<line x1="520" y1="200" x2="538" y2="160" marker-end="url(#a24b)"/>
</g>
<g fill="currentColor" text-anchor="middle" font-size="12">
<text x="54" y="126" font-size="14" font-weight="600">Kafka</text>
<text x="54" y="146">clicks,</text>
<text x="54" y="162">orders</text>
<text x="179" y="126" font-size="14" font-weight="600">Bronze</text>
<text x="179" y="146">raw value +</text>
<text x="179" y="162">topic, offset</text>
<text x="315" y="126" font-size="14" font-weight="600">Silver</text>
<text x="315" y="146">parse, dedupe,</text>
<text x="315" y="162">expectations</text>
<text x="459" y="56" font-size="14" font-weight="600">Gold live</text>
<text x="459" y="76">5-min windows,</text>
<text x="459" y="92">watermark</text>
<text x="459" y="196" font-size="14" font-weight="600">Gold daily</text>
<text x="459" y="216">recompute dates</text>
<text x="459" y="232">that changed</text>
<text x="587" y="126" font-size="14" font-weight="600">Dashboards</text>
<text x="587" y="146">SQL</text>
<text x="587" y="162">warehouse</text>
<text x="320" y="282" font-size="12">Late events beyond the watermark still land in bronze and silver, and are counted by the daily path.</text>
</g>
</svg>
<figcaption>Figure 24.2. Late events: a fast path for live tiles and a corrected path for daily numbers.</figcaption>
</figure>

**2. Layers.**

- **Bronze:** a streaming table that reads both topics and stores the raw message value (string or binary),
  `topic`, `partition`, `offset`, the Kafka `timestamp` and an ingest time. No parsing, so nothing is lost when the
  event format changes. Bronze outlives Kafka retention, so it is the replay source.
- **Silver:** parse the JSON (into columns or `VARIANT`), cast types, apply expectations (event ID and event time
  must be present; invalid rows go to a quarantine table), and deduplicate on `event_id` with
  `dropDuplicatesWithinWatermark` plus a `MERGE` on `event_id` for duplicates that arrive later than the watermark.
  Silver keeps every valid event, however late.
- **Gold live:** a streaming windowed aggregation (page views and orders per product per 5 minutes) with a watermark
  of, for example, 30 minutes. It is fast and bounded in state, and accepts that very late events are not counted
  here.
- **Gold daily:** a table of daily metrics per product, recomputed only for the dates that received new silver
  rows since the last run (`INSERT ... REPLACE WHERE`), or a materialized view. This is the number of record.
- **Serving:** dashboards on a SQL warehouse read the gold tables. Recent days are marked provisional.

*Databricks only, not run here. Syntax from [Connect to Apache Kafka](https://docs.databricks.com/aws/en/structured-streaming/kafka).*

```python
bronze = (spark.readStream.format("kafka")
    .option("kafka.bootstrap.servers", "<server:port>")
    .option("subscribe", "clicks,orders")
    .option("startingOffsets", "earliest")
    .load()
    .selectExpr("CAST(value AS STRING) AS raw", "topic", "partition", "offset",
                "timestamp AS kafka_ts", "current_timestamp() AS ingest_ts"))
```

**3. Tools.** A Lakeflow pipeline (formerly Delta Live Tables) holds bronze, silver and gold live as streaming tables (continuous mode or a short
`processingTime` trigger, because of the 5-minute freshness requirement); gold daily is a materialized view or a
scheduled job. Unity Catalog holds the three layers as schemas, with product managers granted `SELECT` on gold only.

**4. Data quality.** Expectations in silver (warn on odd values, drop plus quarantine for broken rows, fail only for
something like an unreadable message format); a daily reconciliation that compares order counts in gold with the
order system.

**5. Idempotency and exactly-once.** Checkpoints make the Kafka-to-bronze and bronze-to-silver streams exactly-once
in processing; deduplication by `event_id` handles producer retries, which exactly-once processing does not remove;
gold daily is a replace of whole dates, so reruns are safe.

**6. Backfills and replays.** Bronze is the replay source. To fix a silver bug, reprocess silver from bronze for the
affected period, then recompute gold daily for those dates. Avoid a full refresh of the Kafka bronze table: with
limited retention, older messages cannot be read again.

**7. Monitoring.** Kafka lag (`avgOffsetsBehindLatest`, `maxOffsetsBehindLatest`), batch duration against the
trigger interval, state size of the windowed aggregation, expectation metrics from the event log, freshness of each
gold table (latest event time), and job or pipeline failures with alerts.

**8. Cost.** The live path runs all the time, which is the main cost. If product managers accept 15 minutes instead
of 5, a scheduled `availableNow` run is much cheaper than a continuously running stream. Keep the watermark only as
long as the live tiles need; longer watermarks hold more state.

**9. Trade-offs to say out loud.**

| Choice | Gain | Cost |
| --- | --- | --- |
| Two gold paths | Fast tiles and correct daily numbers | Two definitions of a metric to keep consistent |
| Longer watermark | More late events counted live | More state, slower output in append mode |
| `VARIANT` in silver | Absorbs event schema changes | Typed columns still needed for key fields |
| Continuous vs scheduled | Lower latency | Higher cost |

!!! tip "In the interview"
    If asked "why not one stream with a 3-day watermark?", say that 3 days of 5-minute windows per product is a lot
    of state for little gain, and that late events are also not guaranteed to be counted (Q77). Landing every event
    in silver and recomputing the affected days is simpler and exact.

## 24.14 System design 2: daily CDC of 50 tables into a medallion lakehouse with SCD Type 2

*Level: expert.*

**The question.** "We have an operational database with 50 tables (orders, customers, products and so on). Load
the changes every day into the lakehouse. The business needs the current state of every table, full history for
customers and products, and star-schema gold tables for reporting."

**1. Clarify.**

| Question | Assumption for this walkthrough |
| --- | --- |
| Which database, and is CDC enabled? | SQL Server with CDC enabled; one table set also has only nightly full extracts |
| Volume? | Most tables small; `orders` and `order_lines` have a few million changes a day |
| Deletes? | Rows are hard-deleted in the source; deletes must be reflected |
| History? | SCD Type 2 for customers and products; SCD Type 1 (current state) for the rest |
| Freshness? | Available by 6 a.m. each day |
| Source load? | The database team does not want heavy queries on the production database |

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Source database changes flow through a Lakeflow Connect ingestion gateway or CDC files into bronze change tables, then AUTO CDC builds SCD Type 1 and SCD Type 2 silver tables, then gold star schema tables feed BI. A config list of 50 tables drives the flows and a daily Lakeflow Job runs the pipeline.">
<defs><marker id="a24c" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="6" y="70" width="96" height="90" rx="8"/>
<rect x="124" y="70" width="110" height="90" rx="8"/>
<rect x="256" y="70" width="110" height="90" rx="8"/>
<rect x="388" y="20" width="112" height="70" rx="8"/>
<rect x="388" y="140" width="112" height="70" rx="8"/>
<rect x="522" y="70" width="112" height="90" rx="8"/>
<rect x="124" y="230" width="376" height="54" rx="8" stroke-dasharray="5 4"/>
<line x1="102" y1="115" x2="122" y2="115" marker-end="url(#a24c)"/>
<line x1="234" y1="115" x2="254" y2="115" marker-end="url(#a24c)"/>
<line x1="366" y1="100" x2="386" y2="60" marker-end="url(#a24c)"/>
<line x1="366" y1="130" x2="386" y2="170" marker-end="url(#a24c)"/>
<line x1="500" y1="60" x2="520" y2="100" marker-end="url(#a24c)"/>
<line x1="500" y1="170" x2="520" y2="130" marker-end="url(#a24c)"/>
<line x1="311" y1="230" x2="311" y2="162" marker-end="url(#a24c)"/>
</g>
<g fill="currentColor" text-anchor="middle" font-size="12">
<text x="54" y="100" font-size="14" font-weight="600">Source DB</text>
<text x="54" y="120">50 tables,</text>
<text x="54" y="136">CDC on</text>
<text x="179" y="100" font-size="14" font-weight="600">Ingest</text>
<text x="179" y="120">gateway or</text>
<text x="179" y="136">CDC files</text>
<text x="311" y="100" font-size="14" font-weight="600">Bronze</text>
<text x="311" y="120">change rows,</text>
<text x="311" y="136">append only</text>
<text x="444" y="46" font-size="14" font-weight="600">Silver SCD 1</text>
<text x="444" y="66">current state</text>
<text x="444" y="166" font-size="14" font-weight="600">Silver SCD 2</text>
<text x="444" y="186">full history</text>
<text x="578" y="100" font-size="14" font-weight="600">Gold</text>
<text x="578" y="120">star schema,</text>
<text x="578" y="136">BI and reports</text>
<text x="312" y="252" font-size="13" font-weight="600">Config: table, keys, sequence column, SCD type</text>
<text x="312" y="272">drives AUTO CDC flows; a daily Lakeflow Job runs the pipeline</text>
</g>
</svg>
<figcaption>Figure 24.3. Daily CDC of many tables: one generic pattern, driven by configuration.</figcaption>
</figure>

**2. Ingestion options.**

| Option | When |
| --- | --- |
| Lakeflow Connect database connector (MySQL, PostgreSQL, SQL Server) | Source supported; uses an ingestion gateway and staging storage to capture changes continuously, while the ingestion pipeline can run on a schedule |
| CDC files from an existing tool (for example a log-based replication tool) landing in cloud storage, read with Auto Loader | The company already runs such a tool, or the source is not supported by a managed connector |
| Daily full extracts, processed with `AUTO CDC FROM SNAPSHOT` | No CDC on the source; changes are derived by comparing snapshots |
| Query-based connector or JDBC reads with a high-water-mark column | No CDC, but a reliable "last modified" column exists; misses hard deletes |

For this design: the managed connector for the CDC-enabled tables (least custom code, low load on the source), and
`AUTO CDC FROM SNAPSHOT` for the one table set that only has full extracts.

**3. Layers.**

- **Bronze:** one append-only table per source table holding every change row: the columns, the operation (insert,
  update, delete), a sequence value (a log sequence number or commit timestamp from the source) and ingest metadata.
  Bronze is the audit trail and the replay source.
- **Silver:** one `AUTO CDC` (formerly `APPLY CHANGES`) flow per table. SCD Type 1 targets for most tables (current state; deletes applied),
  SCD Type 2 for customers and products, where the pipeline adds `__START_AT` and `__END_AT` from the sequence
  column. `AUTO CDC` handles out-of-order changes by the sequence column, which must be monotonically increasing,
  with one distinct update per key at each value, and never `NULL`.
- **Gold:** a star schema: facts (orders, order lines) and dimensions (customer, product) as materialized views or
  scheduled tables. Facts join the SCD Type 2 dimension on the key and the validity range (order time between
  `__START_AT` and `__END_AT`), so each order sees the customer as they were at the time.

*Databricks only, not run here. Syntax from [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc).*

```sql
CREATE OR REFRESH STREAMING TABLE silver_customers;

CREATE FLOW customers_cdc AS AUTO CDC INTO
  silver_customers
FROM
  stream(shop.bronze.customers_changes)
KEYS
  (customer_id)
APPLY AS DELETE WHEN
  operation = "DELETE"
SEQUENCE BY
  commit_seq
COLUMNS * EXCEPT
  (operation, commit_seq)
STORED AS
  SCD TYPE 2;
```

**4. Fifty tables without fifty copies of code.** Keep a configuration list (table name, key columns, sequence
column, SCD type, columns excluded from history) and generate the flows from it in the pipeline's Python source, or
generate the SQL files from it. Adding table 51 becomes a configuration change, reviewed like code.

**5. Data quality.** Expectations on bronze-to-silver: keys not null, sequence value not null (`AUTO CDC` does not
support `NULL` sequencing values), operation in the known set. Daily reconciliation per table: row counts of silver
current state against counts from the source (or from the snapshot), alerting on differences. Gold checks:
no fact rows without a dimension match (or a default "unknown" member).

**6. Idempotency.** Bronze writes are checkpointed streams; `AUTO CDC` applies changes by sequence, so a change
replayed or arriving out of order gives the same result; gold is recomputed or refreshed, not appended. The daily
Lakeflow Job (formerly Databricks Workflows) retries failed tasks, and a repair run re-runs only what failed.

**7. Backfills.** Initial hydration with an `AUTO CDC` `once` flow, then the regular flow for ongoing changes. For
a table with periodic full snapshots plus a CDC feed, a one-time `AUTO CDC FROM SNAPSHOT` flow can be combined with
`AUTO CDC` flows into the same SCD Type 1 target. Be careful with full refreshes: if the source CDC log has expired,
the change history cannot be read again, and an SCD Type 2 table rebuilt only from current data loses its past
versions. Keep bronze for as long as history matters.

**8. Deletes and late changes.** With SCD Type 2, deleted rows are kept for a while as tombstones so that
out-of-order changes are handled correctly; the retention is set with the `pipelines.cdc.tombstoneGCThresholdInSeconds`
table property (the default retention is two days, according to the Auto Loader page). Set it above the longest
expected delay.

**9. Monitoring.** Pipeline event log and monitoring UI (row counts, expectation metrics, backlog), failure
notifications on the job, a freshness check ("did every table get today's changes by 6 a.m.?"),
`system.billing.usage` for the pipeline's cost, and Unity Catalog lineage to see what a failed table affects.

**10. Cost.** Triggered mode once a day, serverless or job compute (not all-purpose), predictive optimization for
table maintenance, and a gateway sized for the change volume.

**11. Trade-offs to say out loud.**

| Choice | Gain | Cost |
| --- | --- | --- |
| Managed connector | Little code, CDC handled, low source load | Depends on supported sources and connector features |
| `AUTO CDC` vs hand-written `MERGE` | Ordering, deletes and SCD Type 2 handled for you | Pipeline owns the target; less low-level control |
| SCD Type 2 everywhere | Full history | Bigger tables, harder joins; use only where history is needed |
| Daily vs continuous | Cheap, simple | Data is up to a day old |

!!! warning "A common design mistake"
    Building SCD Type 2 from daily snapshots by hand with `MERGE`, and then rerunning a day, can close and reopen
    versions twice. If you hand-write it (Q112), make the merge key and the change condition exact and test a
    rerun. With `AUTO CDC`, ordering by the sequence column makes reruns safe.

## 24.15 Telling your own project in medallion terms

*Level: beginner.*

Almost every interview asks "Tell me about a data pipeline you built." If your experience is with SQL, a
traditional warehouse and data migrations rather than Databricks, you already have the material: the medallion
layers existed in your projects under other names. Tell the story in your own terms, and name the medallion
equivalent as you go. That shows you understand the concepts without claiming experience you do not have.

| What your project probably called it | Medallion or Databricks term |
| --- | --- |
| Landing area, staging tables, raw extracts | Bronze |
| Cleansed layer, ODS, integration layer, conformed tables | Silver |
| Data marts, star schemas, reporting views, cubes | Gold |
| ETL package or mapping (SSIS, Informatica) | Pipeline: Lakeflow pipelines (formerly Delta Live Tables) or notebook tasks |
| Scheduler (SQL Server Agent, a job scheduler) | Lakeflow Jobs (formerly Databricks Workflows) |
| Row-count and checksum reconciliation | Data quality checks and expectations |
| Slowly changing dimension logic in procedures | SCD Type 2, `MERGE` or `AUTO CDC` (formerly `APPLY CHANGES`) |

### The template

Prepare one project in eight parts. Say each part in two or three sentences; the whole story should take about two
minutes, with details ready for follow-up questions.

1. **Situation.** The business, the problem, and your role. One sentence each.
2. **Sources.** Which systems, what formats, how much data, how often, and how changes were detected (full extract,
   timestamp column, CDC).
3. **Landing (bronze).** How raw data arrived and was kept: as received, with load metadata, and whether you could
   reload from it.
4. **Cleaning (silver).** Types, deduplication, keys, conforming codes across sources, handling of late or changed
   records, history (SCD).
5. **Business marts (gold).** Which facts and dimensions, which reports or users depended on them, and how they
   were refreshed.
6. **Data quality.** What you checked (counts, totals, keys, rules), where, and what happened when a check failed.
7. **Scale.** Rows, tables, volume per day, load window, number of users. Approximate numbers are fine; say they
   are approximate.
8. **Results.** What improved, with a number if you have one, and one thing you would do differently, ideally in
   Databricks terms.

### A filled-in example: a warehouse migration

The figures below are an example; use your own.

1. **Situation.** "A distribution company's reporting warehouse on SQL Server was loaded nightly by about 40 SSIS
   packages, and the load no longer finished before the start of the business day. I was one of three engineers
   on the migration to a new platform; I owned the sales and inventory subject areas."
2. **Sources.** "An ERP database, an e-commerce database and daily CSV files from two logistics partners. The ERP
   tables had a last-modified column, so we loaded changes only; the CSV files were full daily snapshots."
3. **Landing (bronze).** "Every extract landed unchanged in staging tables with the load date and the source file
   name, and we kept 90 days of it, so we could reload a day without touching the source. In medallion terms that
   was our bronze layer."
4. **Cleaning (silver).** "We cast types, mapped product codes from the two systems to one product key, removed
   duplicate partner rows by keeping the latest record per shipment, and kept customer history as SCD Type 2. That
   is silver."
5. **Business marts (gold).** "A sales star schema (daily sales fact, customer, product and date dimensions) and an
   inventory snapshot fact, used by about 150 report users. That is gold."
6. **Data quality.** "After each load we compared row counts and sales totals per day with the source and failed
   the load if they differed by more than an agreed tolerance. Rows with unknown product codes went to a review
   table instead of being dropped."
7. **Scale.** "Roughly 200 tables, about 30 million changed rows a night, a few terabytes in total."
8. **Results.** "We replaced the full reloads of the largest tables with incremental loads, and the nightly window
   went from about six hours to under two. During the parallel run, the reconciliation checks found three
   differences before go-live, all traced to time zone handling. On Databricks I would build the same layers with
   Auto Loader for the partner files, `AUTO CDC` (formerly `APPLY CHANGES`) for the SCD Type 2 dimension, and
   expectations with a quarantine table instead of my hand-written checks."

!!! warning "Stay accurate about what you did"
    Do not rename your past tools as Databricks features you used. "We called it staging; in medallion terms that
    is bronze" is honest and shows understanding. Interviewers probe details, and a story that falls apart under
    two follow-up questions costs more than a modest one.

!!! tip "In the interview"
    Expect the follow-ups: "What was the hardest bug?", "How did you know the data was right?", "What would you
    change?". Prepare one concrete answer for each before the interview; Q117, Q119 and Q137 give the technical
    vocabulary.

## 24.16 Cheat sheet

*Level: review.*

**Commands to know by heart.** All run on Databricks; the ones marked with an asterisk were also run in this
chapter on Apache Spark 4.2 with Delta Lake 4.4.1.

| Task | Command |
| --- | --- |
| Table history* | `DESCRIBE HISTORY t` |
| Files, size, properties* | `DESCRIBE DETAIL t` |
| Time travel* | `SELECT ... FROM t VERSION AS OF 5` / `TIMESTAMP AS OF '2026-03-01'` |
| Undo* | `RESTORE TABLE t TO VERSION AS OF 5` |
| Recover a dropped managed table | `UNDROP TABLE t` (within 7 days) |
| Remove old files* | `VACUUM t` (default retention 7 days) |
| Compact* | `OPTIMIZE t` |
| Liquid clustering | `ALTER TABLE t CLUSTER BY (col1, col2)` or `CLUSTER BY AUTO` |
| Physically drop soft-deleted rows | `REORG TABLE t APPLY (PURGE)` |
| Change data feed* | `ALTER TABLE t SET TBLPROPERTIES (delta.enableChangeDataFeed = true)`; `table_changes('t', 7)` |
| Upsert and mirror* | `MERGE INTO ... WHEN MATCHED ... WHEN NOT MATCHED ... WHEN NOT MATCHED BY SOURCE` |
| Replace a slice* | `INSERT INTO t REPLACE WHERE order_date = DATE'2026-03-01' SELECT ...` |
| Latest row per key* | `QUALIFY row_number() OVER (PARTITION BY k ORDER BY ts DESC) = 1` |
| JSON path* | `parse_json(raw):items[0].product_id::int` |
| Grant | ``GRANT SELECT ON TABLE c.s.t TO `analysts` `` |
| Incremental file ingest (SQL) | `CREATE OR REFRESH STREAMING TABLE ... AS SELECT * FROM STREAM read_files(...)` |
| CDC with history | `AUTO CDC INTO ... KEYS (...) SEQUENCE BY ... STORED AS SCD TYPE 2` |
| Streaming basics* | `.trigger(availableNow=True)`, `.withWatermark("ts", "10 minutes")`, `foreachBatch`, `checkpointLocation` |
| Streaming dedup | `.dropDuplicatesWithinWatermark(["event_id"])` |
| Delta source with updates | `.option("skipChangeCommits", "true")` |
| Read a plan* | `df.explain()`: `Exchange` = shuffle, `BroadcastHashJoin` = broadcast |

**Renamed products.** Interviewers often use the older name. The last column links the official page that shows
the rename; where the product's page does not mention the old name, it says "unknown" (pages read Nov 11, 2026).

| Name today | Older name | Product page | Page that shows the rename |
| --- | --- | --- | --- |
| Lakeflow pipelines (Spark Declarative Pipelines on Lakeflow); Python `from pyspark import pipelines as dp` | Delta Live Tables (DLT); `import dlt` | [Lakeflow Spark Declarative Pipelines](https://docs.databricks.com/aws/en/ldp/) | [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) |
| `AUTO CDC` | `APPLY CHANGES` (still available) | [The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc) | Same page: "The `AUTO CDC` APIs replace the `APPLY CHANGES` APIs and have the same syntax." |
| Lakeflow Jobs | Databricks Jobs; the menu item was called Workflows | [Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/) | [Release notes, June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026): "The product known as Databricks Jobs is now Lakeflow Jobs", and "The **Pipelines** and **Workflows** items in the left navigation have been removed" |
| Declarative Automation Bundles | Databricks Asset Bundles | [Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/) | Same page: "formerly known as Databricks Asset Bundles" |
| OpenSharing | Delta Sharing | [What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/) | Not the docs page; the Databricks blog [From Delta Sharing to OpenSharing](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next): "Delta Sharing has evolved into OpenSharing" |
| Standard / dedicated access mode | Shared / single user access mode | [Standard compute requirements and limitations](https://docs.databricks.com/aws/en/compute/access-mode-limitations) | [Manually apply row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/manually-apply): "Standard access mode (formerly shared access mode)", "Dedicated access mode (formerly single user access mode)" |
| Disk cache | Delta cache (also DBIO cache) | [Optimize performance with caching](https://docs.databricks.com/aws/en/optimizations/disk-cache) | Same page: "formerly referred to as the Delta cache and the DBIO cache" |

**Numbers worth knowing** (each from the page cited in the question that uses it).

| Number | Value | Where |
| --- | --- | --- |
| `VACUUM` default retention | 7 days | Q34 |
| Default log retention (`delta.logRetentionDuration`) | 30 days | Q32 |
| `UNDROP TABLE` window | 7 days | Q124 |
| Statistics collected by default (external tables) | First 32 columns | Q134 |
| Liquid clustering keys | Up to 4 | Q36 |
| Auto Loader schema inference sample | First 50 GB or 1,000 files, whichever first | Q64 |
| Broadcast threshold, open-source Spark (`autoBroadcastJoinThreshold`) | 10 MB | Q18 |
| AQE broadcast threshold on Databricks | 30 MB | Q18 |
| `spark.sql.shuffle.partitions` default | 200 | Q16 |
| AQE advisory partition size | 64 MB | Q16 |
| `spark.sql.files.maxPartitionBytes` | 128 MB | Q16 |
| AQE skew: partition larger than 5x the median and 256 MB | 5x, 256 MB | Q21 |
| Partitioning guidance | Not under 1 TB; at least 1 GB per partition | Q36 |
| `AUTO CDC` tombstone retention default | Two days | 24.14 |
| Default trigger | `processingTime` 0 ms, 3-5 s latency | Q73 |

!!! warning "Names change"
    Product names on Databricks change often. If an interviewer uses an older name (DLT, Workflows, Delta cache),
    answer with both names; it shows you follow the platform.

## 24.17 Practice questions

*Level: review.*

A mock round: answer each in under a minute, out loud, then check. The full answers are in the question banks
above.

**M1. In one sentence each: bronze, silver, gold.**

??? success "Answer"
    Bronze keeps the raw data as received, plus ingest metadata, for audit and replay. Silver holds cleaned,
    typed, deduplicated and conformed records. Gold holds business-level aggregates and star-schema tables for
    consumers. See Q46.

**M2. What does this plan line tell you: `Exchange hashpartitioning(customer_id#1, 4)`?**

??? success "Answer"
    A shuffle: rows are redistributed into 4 partitions by `customer_id`, typically for a `groupBy` or a join on
    that column. It marks a stage boundary and is usually the expensive part of the query. See Q14.

**M3. True or false: `VACUUM` makes queries faster.**

??? success "Answer"
    False, in general. `VACUUM` removes files no longer referenced by the table (after the retention period) to
    save storage; it does not change the current version. `OPTIMIZE` and clustering affect query speed. After
    `VACUUM`, time travel to versions that needed those files fails. See Q34.

**M4. A `MERGE` fails with "multiple source rows matched". Fix it in one line.**

??? success "Answer"
    Deduplicate the source first, for example
    `USING (SELECT * FROM updates QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY ingest_ts DESC) = 1) s`.
    See Q43.

**M5. Which trigger would you use for a stream that only needs to run once an hour?**

??? success "Answer"
    `availableNow=True`, scheduled hourly by a job: it processes everything new since the last run and stops.
    See Q74.

**M6. What two things together give exactly-once from files into Delta?**

??? success "Answer"
    The checkpoint (which records source offsets and commits) and the Delta sink, whose transaction log makes the
    write idempotent. See Q76.

**M7. Does a watermark guarantee that late events are dropped?**

??? success "Answer"
    No. Events within the threshold are guaranteed to be processed; events beyond it might still be processed, but
    this is not guaranteed. Q77 shows a late event being counted and a later one being dropped.

**M8. Which expectation action keeps bad rows in the target table?**

??? success "Answer"
    The default, warn (`EXPECT` without `ON VIOLATION`): invalid rows are written and counted in the metrics.
    `DROP ROW` removes them; `FAIL UPDATE` stops the update. See Q86.

**M9. Write the SQL to keep the latest row per `order_id` by `ingest_ts`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, status, ingest_ts FROM silver_orders
    QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY ingest_ts DESC) = 1
    ORDER BY order_id;
    ```

    This is the query from Q106, with its output there. See also the
    [SQL course on window functions](../../databases/sql/13-Window-Functions-Ranking.md).

**M10. What privileges does a user need to `SELECT` from `shop.gold.sales`?**

??? success "Answer"
    `USE CATALOG` on `shop`, `USE SCHEMA` on `shop.gold`, and `SELECT` on the table (or on a parent, since
    privileges are inherited). See Q96.

**M11. Your stream reads a Delta table that is updated with `MERGE`. Name two options.**

??? success "Answer"
    Stream the table's change data feed, or set `skipChangeCommits` if only appends matter. Also possible: a
    materialized view, or a full refresh when changes are rare. See Q82.

**M12. Why is a Python UDF slower than a built-in function?**

??? success "Answer"
    Rows must be serialized and sent to a Python process and back, and the optimizer cannot see inside the UDF.
    Built-in functions run inside the engine (and can use Photon). Pandas UDFs reduce the cost by moving data in
    batches with Arrow. See Q24.

**M13. What is the difference between `repartition(4)` and `coalesce(4)`?**

??? success "Answer"
    `repartition` does a full shuffle and can increase or decrease the number of partitions, producing even
    partitions. `coalesce` only merges existing partitions without a shuffle, so it can only decrease them and can
    leave them uneven. See Q17.

**M14. How do you find out who dropped a table yesterday?**

??? success "Answer"
    Query the audit log system table, `system.access.audit`, for the delete event on that table in the time range.
    See Q100.

**M15. A rerun created duplicates. Name two ways to make the load idempotent.**

??? success "Answer"
    `MERGE` on the business key instead of `INSERT`; `INSERT ... REPLACE WHERE` for a date slice; also a
    checkpointed stream, or `txnAppId`/`txnVersion` options. Q117 shows 4 rows after two appends and 2 after two
    merges.

**M16. What are `__START_AT` and `__END_AT`?**

??? success "Answer"
    The validity columns that `AUTO CDC` (formerly `APPLY CHANGES`) adds to an SCD Type 2 target, filled from the sequence column. A row with
    `__END_AT` set to `NULL` is the current version. See Q88.

**M17. Find the bug: `df.filter(F.year("order_ts") == 2026)` reads the whole table although the table is
clustered by `order_ts`.**

??? success "Answer"
    Wrapping the column in a function can prevent data skipping. Filter on a range of the raw column instead:
    `order_ts >= '2026-01-01' AND order_ts < '2027-01-01'`. Check the query profile to confirm fewer files are read.
    See Q134.

**M18. Why might a broadcast join not happen for a small table?**

??? success "Answer"
    The planner's size estimate is above the threshold (missing or stale statistics, or the table is only small
    after a filter the planner cannot estimate), the join type does not allow broadcasting that side, or the
    threshold was changed. A `BROADCAST` hint or AQE at runtime can still choose it. See Q19.

**M19. What happens to a streaming table on a full refresh?**

??? success "Answer"
    It is truncated, its checkpoints are removed, and it is rebuilt from the data the source still has. Data that
    the source no longer retains (for example expired Kafka messages) is lost. See Q91.

**M20. Give three questions you would ask before designing any pipeline.**

??? success "Answer"
    How fresh must the data be? How late and how duplicated can the input be? Is history needed (SCD Type 2), and
    must deletes be reflected? Others: volume and growth, who consumes it, and what happens if it is wrong. See 24.1.

## Sources

Databricks documentation:

- [What is a data lakehouse?](https://docs.databricks.com/aws/en/lakehouse/) (last updated Oct 29, 2026)
- [High-level architecture](https://docs.databricks.com/aws/en/getting-started/high-level-architecture) (last updated Oct 29, 2026)
- [What is Delta Lake in Databricks?](https://docs.databricks.com/aws/en/delta/) (last updated Sep 11, 2026)
- [What are ACID guarantees on Databricks?](https://docs.databricks.com/aws/en/lakehouse/acid) (last updated Oct 19, 2026)
- [Work with table history](https://docs.databricks.com/aws/en/delta/history) (last updated Nov 6, 2026)
- [Remove unused data files with vacuum](https://docs.databricks.com/aws/en/delta/vacuum) (last updated Nov 6, 2026)
- [Optimize data file layout](https://docs.databricks.com/aws/en/delta/optimize) (last updated Sep 11, 2026)
- [Deletion vectors in Databricks](https://docs.databricks.com/aws/en/delta/deletion-vectors) (last updated Nov 6, 2026)
- [Use Delta Lake change data feed on Databricks](https://docs.databricks.com/aws/en/delta/delta-change-data-feed) (last updated Oct 9, 2026)
- [Update table schema](https://docs.databricks.com/aws/en/delta/update-schema) (last updated Sep 11, 2026)
- [Upsert into a Delta Lake table using merge](https://docs.databricks.com/aws/en/delta/merge) (last updated Sep 11, 2026)
- [Type widening](https://docs.databricks.com/aws/en/delta/type-widening) (last updated Oct 30, 2026)
- [Use liquid clustering for tables](https://docs.databricks.com/aws/en/delta/clustering) (last updated Nov 2, 2026)
- [Clone a table on Databricks](https://docs.databricks.com/aws/en/delta/clone) (last updated Sep 11, 2026)
- [Read Delta Lake tables with Iceberg clients](https://docs.databricks.com/aws/en/delta/uniform) (last updated Sep 11, 2026)
- [What is Apache Iceberg in Databricks?](https://docs.databricks.com/aws/en/iceberg/) (last updated Nov 4, 2026)
- [Data skipping](https://docs.databricks.com/aws/en/delta/data-skipping) (last updated Oct 20, 2026)
- [When to partition tables on Databricks](https://docs.databricks.com/aws/en/tables/partitions) (last updated Sep 11, 2026)
- [Unity Catalog managed tables](https://docs.databricks.com/aws/en/tables/managed) (last updated Nov 9, 2026)
- [Work with external tables](https://docs.databricks.com/aws/en/tables/external) (last updated Oct 6, 2026)
- [Schema enforcement](https://docs.databricks.com/aws/en/tables/schema-enforcement) (last updated Sep 11, 2026)
- [Configure Delta Lake to control data file size](https://docs.databricks.com/aws/en/tables/tune-file-size) (last updated Sep 11, 2026)
- [Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe) (last updated Oct 12, 2026)
- [Optimize performance with caching on Databricks](https://docs.databricks.com/aws/en/optimizations/disk-cache) (last updated Oct 22, 2026)
- [Skew join optimization using skew hints](https://docs.databricks.com/aws/en/optimizations/skew-join) (last updated May 13, 2024)
- [Low shuffle merge on Databricks](https://docs.databricks.com/aws/en/optimizations/low-shuffle-merge) (last updated Oct 12, 2026)
- [Predictive optimization for Unity Catalog managed tables](https://docs.databricks.com/aws/en/optimizations/predictive-optimization) (last updated Nov 6, 2026)
- [Isolation levels and write conflicts on Databricks](https://docs.databricks.com/aws/en/optimizations/isolation/) (last updated Oct 12, 2026)
- [Row-level concurrency](https://docs.databricks.com/aws/en/optimizations/isolation/row-level-concurrency) (last updated Oct 12, 2026)
- [Compute](https://docs.databricks.com/aws/en/compute/) (last updated Nov 5, 2026)
- [Compute configuration reference](https://docs.databricks.com/aws/en/compute/configure) (last updated Nov 6, 2026)
- [Connect to serverless compute](https://docs.databricks.com/aws/en/compute/serverless/) (last updated Oct 22, 2026)
- [What is Photon?](https://docs.databricks.com/aws/en/compute/photon) (last updated Sep 11, 2026)
- [Standard compute requirements and limitations](https://docs.databricks.com/aws/en/compute/access-mode-limitations) (last updated Nov 5, 2026)
- [Serverless compute limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations) (last updated Nov 5, 2026)
- [DataFrame caching on serverless compute](https://docs.databricks.com/aws/en/compute/serverless/dataframe-cache) (last updated Oct 22, 2026)
- [Best practices for cost optimization](https://docs.databricks.com/aws/en/lakehouse-architecture/cost-optimization/best-practices) (last updated Oct 29, 2026)
- [Migrate data applications to Databricks](https://docs.databricks.com/aws/en/migration/) (last updated Sep 11, 2026)
- [Migrate your data warehouse to the Databricks lakehouse](https://docs.databricks.com/aws/en/migration/warehouse-to-lakehouse) (last updated Sep 11, 2026)
- [Migrate ETL pipelines to Databricks](https://docs.databricks.com/aws/en/migration/etl) (last updated Sep 11, 2026)
- [Catalog commits](https://docs.databricks.com/aws/en/tables/features/catalog-commits) (last updated Nov 9, 2026)
- [What is the medallion lakehouse architecture?](https://docs.databricks.com/aws/en/lakehouse/medallion) (last updated Oct 29, 2026)
- [Standard connectors in Lakeflow Connect](https://docs.databricks.com/aws/en/ingestion/) (last updated Oct 15, 2026)
- [What is Auto Loader?](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/) (last updated Oct 15, 2026)
- [Configure schema inference and evolution in Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema) (last updated Nov 5, 2026)
- [Auto Loader file detection modes](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/file-detection-modes) (last updated Sep 11, 2026)
- [Get started using COPY INTO to load data](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/copy-into/) (last updated Oct 6, 2026)
- [File metadata column](https://docs.databricks.com/aws/en/ingestion/file-metadata-column) (last updated Sep 11, 2026)
- [Spark API options reference](https://docs.databricks.com/aws/en/spark/api-options) (last updated Nov 5, 2026)
- [read_files table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/read_files) (last updated Nov 10, 2026)
- [Lakeflow Connect connector concepts](https://docs.databricks.com/aws/en/ingestion/lakeflow-connect/) (last updated Nov 3, 2026)
- [Configure Structured Streaming trigger intervals](https://docs.databricks.com/aws/en/structured-streaming/triggers) (last updated Nov 10, 2026)
- [Apply watermarks to control data processing thresholds](https://docs.databricks.com/aws/en/structured-streaming/watermarks) (last updated Sep 11, 2026)
- [Use foreachBatch to write to arbitrary data sinks](https://docs.databricks.com/aws/en/structured-streaming/foreach) (last updated Nov 5, 2026)
- [Structured Streaming checkpoints](https://docs.databricks.com/aws/en/structured-streaming/checkpoints) (last updated Sep 11, 2026)
- [Delta table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake) (last updated Oct 15, 2026)
- [What is stateful streaming?](https://docs.databricks.com/aws/en/structured-streaming/stateful-streaming) (last updated Oct 9, 2026)
- [Connect to Apache Kafka](https://docs.databricks.com/aws/en/structured-streaming/kafka) (last updated Sep 11, 2026)
- [Lakeflow Spark Declarative Pipelines](https://docs.databricks.com/aws/en/ldp/) (last updated Oct 22, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [How to use Spark Declarative Pipelines on Lakeflow](https://docs.databricks.com/aws/en/ldp/concepts/how-to-use-pipelines) (last updated Oct 22, 2026)
- [Pipeline concepts](https://docs.databricks.com/aws/en/ldp/concepts/) (last updated Nov 5, 2026)
- [Streaming tables](https://docs.databricks.com/aws/en/ldp/streaming-tables) (last updated Oct 9, 2026)
- [Materialized views](https://docs.databricks.com/aws/en/ldp/materialized-views) (last updated Oct 15, 2026)
- [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations) (last updated Oct 26, 2026)
- [Expectation recommendations and advanced patterns](https://docs.databricks.com/aws/en/ldp/expectation-patterns) (last updated Oct 26, 2026)
- [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc) (last updated Nov 9, 2026)
- [AUTO CDC INTO (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-apply-changes-into) (last updated Nov 9, 2026)
- [Triggered vs. continuous pipeline mode](https://docs.databricks.com/aws/en/ldp/concepts/pipeline-mode) (last updated Sep 14, 2026)
- [Run a pipeline update](https://docs.databricks.com/aws/en/ldp/updates) (last updated Sep 11, 2026)
- [Full refresh for streaming tables](https://docs.databricks.com/aws/en/ldp/full-refresh-st) (last updated Sep 11, 2026)
- [Change data capture and snapshots](https://docs.databricks.com/aws/en/ldp/what-is-change-data-capture) (last updated Nov 9, 2026)
- [What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) (last updated Sep 11, 2026)
- [Unity Catalog privileges and securable objects](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/privileges) (last updated Nov 6, 2026)
- [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) (last updated Oct 30, 2026)
- [Row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/) (last updated Nov 6, 2026)
- [Manually apply row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/manually-apply) (last updated Oct 8, 2026)
- [Unity Catalog attribute-based access control (ABAC)](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/) (last updated Oct 22, 2026)
- [View data lineage using Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage) (last updated Nov 4, 2026)
- [What are Unity Catalog volumes?](https://docs.databricks.com/aws/en/volumes/) (last updated Oct 12, 2026)
- [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant) (last updated Sep 11, 2026)
- [RESTORE](https://docs.databricks.com/aws/en/sql/language-manual/delta-restore) (last updated Sep 11, 2026)
- [UNDROP TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-undrop-table) (last updated Nov 5, 2026)
- [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into) (last updated Sep 11, 2026)
- [QUALIFY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-qualify) (last updated Sep 11, 2026)
- [: (colon sign) operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/colonsign) (last updated Sep 11, 2026)
- [VARIANT type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/variant-type) (last updated Sep 11, 2026)
- [INSERT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-dml-insert-into) (last updated Oct 21, 2026)
- [transform function](https://docs.databricks.com/aws/en/sql/language-manual/functions/transform) (last updated Sep 11, 2026)
- [table_changes table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/table_changes) (last updated Oct 15, 2026)
- [max_by aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/max_by) (last updated Nov 5, 2026)
- [Monitor account activity with system tables](https://docs.databricks.com/aws/en/admin/system-tables/) (last updated Nov 9, 2026)
- [Billable usage system table reference](https://docs.databricks.com/aws/en/admin/system-tables/billing) (last updated Nov 6, 2026)
- [Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/) (last updated Nov 5, 2026)
- [Automating jobs with schedules and triggers](https://docs.databricks.com/aws/en/jobs/triggers) (last updated Nov 6, 2026)
- [Troubleshoot and repair job failures](https://docs.databricks.com/aws/en/jobs/repair-job-failures) (last updated Nov 5, 2026)
- [What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/) (last updated Oct 27, 2026)
- [Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/) (last updated Nov 5, 2026)
- [Query profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile) (last updated Sep 11, 2026)
- [From Delta Sharing to OpenSharing: what changed, what's next](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next) (Databricks blog, dated Nov 5, 2026)

Apache Spark and Delta Lake (these pages show no last-updated date; the Spark pages are the 4.3.0 documentation,
read Nov 11, 2026):

- [Performance Tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html) (read Nov 11, 2026)
- [RDD Programming Guide](https://spark.apache.org/docs/latest/rdd-programming-guide.html) (read Nov 11, 2026)
- [Cluster Mode Overview](https://spark.apache.org/docs/latest/cluster-overview.html) (read Nov 11, 2026)
- [Structured Streaming Programming Guide: API using Datasets and DataFrames](https://spark.apache.org/docs/latest/streaming/apis-on-dataframes-and-datasets.html) (read Nov 11, 2026)
- [pyspark.sql.DataFrame.coalesce](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.coalesce.html) (read Nov 11, 2026)
- [Apache Arrow in PySpark](https://spark.apache.org/docs/latest/api/python/tutorial/sql/arrow_pandas.html) (read Nov 11, 2026)
- [Delta Transaction Log Protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md) (read Nov 11, 2026)
- [Apache Hudi README](https://github.com/apache/hudi/blob/master/README.md) (read Nov 11, 2026; hudi.apache.org could not be reached from here)
