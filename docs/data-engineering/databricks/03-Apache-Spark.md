# 3. Apache Spark for data engineers

*Every cluster and SQL warehouse on Databricks runs Apache Spark, so a data engineer interview almost always has a Spark round: what the driver and executors do, why a job has three stages and not one, why one task runs for twenty minutes while the others finish in seconds, why `collect()` killed the driver. This chapter teaches the engine from the inside, using the Red Rock Supply orders. Every plan, stage count and error you see below came from a real run, so you learn to read the evidence an interviewer puts in front of you, not only the definitions.*

!!! abstract "In this chapter"
    **You will learn:**

    - why Spark exists and how a Spark application is built: driver, executors, cores, tasks and the cluster manager
    - the SparkSession, DataFrames, schemas, `Row` objects, and where RDDs still appear
    - lazy evaluation: transformations and actions, the four plans, Catalyst and Tungsten, and how to read `explain()`
    - narrow and wide transformations, shuffles, and how an action becomes jobs, stages and tasks
    - partitions: how many you get, `repartition` vs `coalesce`, `spark.sql.shuffle.partitions`, partition pruning
    - join strategies (broadcast hash, sort-merge, shuffle hash), hints and `spark.sql.autoBroadcastJoinThreshold`
    - adaptive query execution (AQE) and data skew, with the Databricks differences
    - caching and storage levels, and the actions that pull data to the driver
    - Python UDFs vs pandas UDFs vs built-in functions
    - the DataFrame API side by side with SQL, reading and writing CSV, JSON and Parquet
    - the Spark UI, the Databricks query profile, Spark Connect and Databricks Connect

    **You need:** basic Python and SQL. General SQL is in the [SQL course](../../databases/sql/index.md). Compute types on Databricks are in [chapter 6](06-Compute.md).

    **Levels:** sections 3.1 to 3.4, 3.12 and 3.13 beginner, 3.5 to 3.7 and 3.9 to 3.11 intermediate, 3.8 and 3.14 expert.

**About the examples.** The "Run here" examples ran on a local Apache Spark 4.2.0 engine with Delta Lake 4.4.1, in local mode with two cores (`local[2]`). They use the Red Rock Supply tables (`customers`, `products`, `orders`, `order_items`) and, where a plan only shows its shape on more data, a larger set of generated Red Rock Supply orders (`silver.orders_big`, 200,000 to 400,000 rows, and `silver.customers_big`, 1,000 customers). On Databricks these would be Unity Catalog tables such as `shop.silver.orders`; locally there is no Unity Catalog, so they live in a schema called `silver`. The scripts are in `src/ch03/` with their full output in the matching `.out` files. To keep plans readable, long `FileScan` lines are shortened with `...` (the file path and some scan details); nothing else in a plan is changed. Most local runs set `spark.sql.shuffle.partitions` to 4 so plans stay small; the built-in default is 200 (section 3.6).

## 3.1 Why Spark
*Level: beginner.*

**The problem.** Red Rock Supply started with a few thousand orders a day, and one Python script on one machine summed them. Then the shop grew. Once the order history is hundreds of gigabytes, one machine runs out of memory, and a nightly job that read every file one by one takes all night. You need to split the data into pieces, process the pieces at the same time on many machines, and put the answers back together, without writing that plumbing yourself.

**The tool.** Apache Spark does exactly that. Its documentation describes it as "a unified analytics engine for large-scale data processing" with "high-level APIs in Java, Scala, Python and R, and an optimized engine that supports general execution graphs", plus Spark SQL, pandas API on Spark, MLlib and Structured Streaming on top. You write a query once, as SQL or as DataFrame code, and Spark splits the data into **partitions** (chunks of rows), runs the same work on every partition in parallel, moves data between machines when a step needs it, and hands you the result.

A little history, from the Apache Spark project page: Spark "started as a research project at the UC Berkeley AMPLab in 2009, and was open sourced in early 2010", then moved to the Apache Software Foundation in 2013. The Databricks page "Apache Spark on Databricks" says "the Databricks company was founded by the original creators of Apache Spark" and that Spark is "the technology powering compute clusters and SQL warehouses" on Databricks. The Databricks Runtime adds its own optimizations on top, including Photon, a native vectorized engine ([chapter 6](06-Compute.md)).

!!! tip "In the interview"
    **"Why would you use Spark instead of pandas?"** pandas runs on one machine and needs the data in that machine's memory. Spark splits the data into partitions and processes them in parallel on many executors, so it scales with the cluster, and the same code runs on a laptop or on hundreds of cores. For a few megabytes pandas is simpler; for data that does not fit on one machine, or for pipelines that must scale, Spark is the tool.

## 3.2 Cluster architecture: driver, executors, cores and tasks
*Level: beginner.*

A Spark **application** is your program plus the processes that run it. The Spark "Cluster Mode Overview" page names the parts:

| Term | What it is (wording from the Spark docs, shortened) |
| --- | --- |
| **Driver program** | "The process running the main() function of the application and creating the SparkContext." In a notebook, the driver is where your Python cell runs. |
| **Cluster manager** | "An external service for acquiring resources on the cluster (e.g. standalone manager, YARN, Kubernetes)." |
| **Worker node** | "Any node that can run application code in the cluster." |
| **Executor** | "A process launched for an application on a worker node, that runs tasks and keeps data in memory or disk storage across them. Each application has its own executors." |
| **Task** | "A unit of work that will be sent to one executor." |
| **Job** | "A parallel computation consisting of multiple tasks that gets spawned in response to a Spark action (e.g. `save`, `collect`)." |
| **Stage** | "Each job gets divided into smaller sets of tasks called stages that depend on each other (similar to the map and reduce stages in MapReduce)." |

The flow: the driver connects to a cluster manager, the cluster manager starts executors on worker nodes, the driver sends your code to the executors, and then "SparkContext sends tasks to the executors to run." Executors run tasks "in multiple threads", one thread per task. How many tasks an executor runs at once depends on its **cores**: `spark.executor.cores` sets "the number of cores to use on each executor" (default: 1 in YARN mode, all available cores on the worker in standalone mode), and `spark.task.cpus` (default 1) is the "number of cores to allocate for each task". So with the defaults, an executor with 4 cores runs 4 tasks at the same time, and a cluster with 10 such executors runs 40 tasks at once. Each task processes one partition.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Spark cluster: the driver asks the cluster manager for executors, sends tasks to executors on two worker nodes, and receives results back">
<defs><marker id="a31" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="20" y="70" width="170" height="160" rx="8"/>
<rect x="235" y="20" width="170" height="60" rx="8"/>
<rect x="450" y="20" width="170" height="125" rx="8" stroke-dasharray="5 4"/>
<rect x="465" y="48" width="140" height="88" rx="6"/>
<rect x="450" y="160" width="170" height="125" rx="8" stroke-dasharray="5 4"/>
<rect x="465" y="188" width="140" height="88" rx="6"/>
<rect x="477" y="84" width="34" height="22"/><rect x="518" y="84" width="34" height="22"/><rect x="559" y="84" width="34" height="22"/>
<rect x="477" y="224" width="34" height="22"/><rect x="518" y="224" width="34" height="22"/><rect x="559" y="224" width="34" height="22"/>
<line x1="190" y1="100" x2="233" y2="64" marker-end="url(#a31)"/>
<line x1="405" y1="50" x2="448" y2="50" marker-end="url(#a31)"/>
<line x1="405" y1="70" x2="448" y2="188" marker-end="url(#a31)"/>
<line x1="190" y1="140" x2="463" y2="100" marker-end="url(#a31)"/>
<line x1="190" y1="160" x2="463" y2="230" marker-end="url(#a31)"/>
<line x1="463" y1="262" x2="192" y2="208" stroke-dasharray="4 3" marker-end="url(#a31)"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="105" y="95" font-size="15" font-weight="bold">Driver</text>
<text x="105" y="118">SparkSession</text>
<text x="105" y="138">builds the plan</text>
<text x="105" y="158">splits it into</text>
<text x="105" y="176">stages and tasks</text>
<text x="105" y="196">schedules tasks</text>
<text x="105" y="216">gets results</text>
<text x="120" y="52">asks for executors</text>
<text x="320" y="45" font-size="14" font-weight="bold">Cluster manager</text>
<text x="320" y="66">starts executors</text>
<text x="535" y="40">Worker node 1</text>
<text x="535" y="72" font-weight="bold">Executor</text>
<text x="494" y="100">task</text><text x="535" y="100">task</text><text x="576" y="100">task</text>
<text x="535" y="126">cache + shuffle</text>
<text x="535" y="180">Worker node 2</text>
<text x="535" y="212" font-weight="bold">Executor</text>
<text x="494" y="240">task</text><text x="535" y="240">task</text><text x="576" y="240">task</text>
<text x="535" y="266">cache + shuffle</text>
<text x="300" y="110">sends tasks</text>
<text x="300" y="256">results, status</text>
</g>
</svg>
<figcaption>Figure 3.1. The driver plans the work and schedules tasks; the cluster manager starts executors on worker nodes; each executor runs one task per core at a time, keeps cached data and shuffle files, and reports back to the driver.</figcaption>
</figure>

Three consequences that interviewers probe:

- **Each application has its own executors.** The overview page says this isolates applications, but "data cannot be shared across different Spark applications ... without writing it to an external storage system". Two notebooks on two clusters share data through tables, not memory.
- **The driver is a single process.** Anything you bring back to it (`collect()`, `toPandas()`) must fit in its memory (section 3.10). The driver is also where scheduling happens, so a driver that is busy or out of memory stalls the whole application.
- **Deploy mode** says where the driver runs: "In 'cluster' mode, the framework launches the driver inside of the cluster. In 'client' mode, the submitter launches the driver outside of the cluster."

**Local mode.** The runs in this book use `local[2]`: driver and executor in one JVM on one machine, with 2 threads. The Spark overview page explains that `--master local[N]` runs "locally with N threads". That is why the local runs below show 2 tasks in a scan stage.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
print("version:", spark.version)
print("master:", spark.sparkContext.master)
print("defaultParallelism:", spark.sparkContext.defaultParallelism)
```
```text
version: 4.2.0
master: local[2]
defaultParallelism: 2
```

**On Databricks.** You do not start the driver or executors yourself. A **compute resource** (classic compute, often still called a cluster; serverless compute; or a SQL warehouse) is the set of machines, and Databricks deploys Spark onto them. The "Apache Spark on Databricks" page says you "don't need to configure or initialize a Spark context or Spark session, as these are managed for you by Databricks": a notebook already has `spark`. On classic compute the driver node and worker nodes are the machines you choose; on serverless compute Databricks chooses them. [Chapter 6](06-Compute.md) covers compute types, access modes and sizing.

!!! tip "In the interview"
    **"Explain the Spark architecture."** A Spark application has one driver and many executors. The driver runs your program, turns your DataFrame or SQL code into a plan, splits it into stages and tasks, and schedules the tasks. Executors are processes on worker nodes that run the tasks, one per core at a time, and keep cached data and shuffle files. A cluster manager (standalone, YARN, Kubernetes, or Databricks itself) starts the executors. Each task processes one partition, so partitions are the unit of parallelism.

## 3.3 SparkSession, DataFrames, schemas and Row
*Level: beginner.*

**The SparkSession** is your entry point: `spark.read`, `spark.sql`, `spark.table`, `spark.createDataFrame` and `spark.conf` all hang off it. In a script you build it with `SparkSession.builder...getOrCreate()`; on Databricks it already exists.

**A DataFrame** is a distributed table with named, typed columns. The Spark SQL guide says a DataFrame "is conceptually equivalent to a table in a relational database or a data frame in R/Python, but with richer optimizations under the hood". In Scala a DataFrame is a `Dataset[Row]`; "Python does not have the support for the Dataset API", so in PySpark you work with DataFrames.

Every DataFrame has a **schema**: column names, types and nullability. You can print it, read it as a DDL-like string, or build it as a `StructType`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
orders = spark.createDataFrame(ORDERS, "order_id INT, customer_id INT, order_ts TIMESTAMP, "
                                       "status STRING, amount DECIMAL(10,2), currency STRING")
orders.printSchema()
print(orders.schema.simpleString())

from pyspark.sql.types import StructType, StructField, IntegerType, StringType, DecimalType
schema = StructType([
    StructField("product_id", IntegerType(), nullable=False),
    StructField("name", StringType()),
    StructField("category", StringType()),
    StructField("price", DecimalType(10, 2)),
])
spark.createDataFrame(products.rdd, schema).printSchema()
```
```text
root
 |-- order_id: integer (nullable = true)
 |-- customer_id: integer (nullable = true)
 |-- order_ts: timestamp (nullable = true)
 |-- status: string (nullable = true)
 |-- amount: decimal(10,2) (nullable = true)
 |-- currency: string (nullable = true)

struct<order_id:int,customer_id:int,order_ts:timestamp,status:string,amount:decimal(10,2),currency:string>
root
 |-- product_id: integer (nullable = false)
 |-- name: string (nullable = true)
 |-- category: string (nullable = true)
 |-- price: decimal(10,2) (nullable = true)
```

**`Row`** is how one record comes back to Python: `collect()`, `first()` and `take()` return `Row` objects. You read fields by attribute, by name, or turn the row into a dict.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
from pyspark.sql import Row
first = orders.orderBy("order_id").first()
print(first)
print(first.order_id, first["status"], first.asDict()["currency"])
r = Row(order_id=2001, customer_id=4, status="PLACED")
print(spark.createDataFrame([r, Row(order_id=2002, customer_id=1, status="SHIPPED")]).collect())
```
```text
Row(order_id=1001, customer_id=1, order_ts=datetime.datetime(2026, 3, 1, 10, 15), status='SHIPPED', amount=Decimal('59.90'), currency='CAD')
1001 SHIPPED CAD
[Row(order_id=2001, customer_id=4, status='PLACED'), Row(order_id=2002, customer_id=1, status='SHIPPED')]
```

**RDDs, briefly.** The RDD (resilient distributed dataset) is Spark's older, lower-level API: a distributed collection of arbitrary objects with functions such as `map` and `reduceByKey`. Every DataFrame still runs on RDDs underneath, and `df.rdd` exposes them.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
rdd = orders.rdd
print(type(rdd).__name__, "partitions:", rdd.getNumPartitions())
print(rdd.map(lambda row: (row.currency, float(row.amount))).reduceByKey(lambda a, b: a + b).collect())
```
```text
RDD partitions: 2
[('USD', 476.95), ('CAD', 645.4)]
```

Use DataFrames (or SQL) for data engineering work. The Spark SQL guide explains why: unlike the RDD API, Spark SQL interfaces "provide Spark with more information about the structure of both the data and the computation", and Spark uses that information "to perform extra optimizations". An RDD lambda is a black box to the optimizer; a DataFrame expression is not.

!!! warning "RDDs are not available everywhere on Databricks"
    The serverless compute limitations page says: "Only Spark Connect APIs are supported. Spark RDD APIs are not supported." Code that calls `df.rdd`, `sc.parallelize` or `spark.sparkContext` fails there. Section 3.14 explains Spark Connect.

!!! tip "In the interview"
    **"DataFrame or RDD?"** DataFrames. They have a schema, so Catalyst can optimize them (filter pushdown, column pruning, join selection) and Tungsten can run them efficiently; RDD functions are opaque Python or JVM code. RDDs are only for rare low-level needs, and they are not supported on Databricks serverless compute, which runs Spark Connect.

## 3.4 Lazy evaluation, the four plans, Catalyst and Tungsten
*Level: beginner.*

**The problem.** If Spark ran each line of your code immediately, it would read the orders table for the filter, write a temporary result, read it again for the next step, and so on. It could never see that you only need two columns, or that a filter could be applied while reading the files.

**The tool: lazy evaluation.** Spark splits operations into two kinds. The Databricks page "Apache Spark on Databricks" defines them:

- **Transformations** "add some processing logic to the plan. Examples include reading data, joins, aggregations, and type casting." `select`, `filter`, `withColumn`, `join`, `groupBy().agg()`, `orderBy`, `union`, `distinct`, `repartition` are transformations. They return a new DataFrame and run nothing.
- **Actions** "trigger processing logic to evaluate and output a result. Examples include writes, displaying or previewing results, manual caching, or getting the count of rows." `show`, `count`, `collect`, `take`, `first`, `toPandas`, `write...save`/`saveAsTable` are actions.

The Spark RDD guide gives the reason: transformations "just remember the transformations applied to some base dataset", and they "are only computed when an action requires a result to be returned to the driver program. This design enables Spark to run more efficiently."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
import time
from pyspark.sql import functions as F

t0 = time.time()
shipped = (orders.filter(F.col("status") == "SHIPPED")
           .withColumn("amount_cents", (F.col("amount") * 100).cast("int"))
           .select("order_id", "customer_id", "amount_cents"))
print("built a 3-step DataFrame in %.3f s, nothing ran yet" % (time.time() - t0))
print("count() is an action, it runs the job:", shipped.count())

bad = orders.withColumn("currency_num", F.col("currency").cast("int"))
print("transformation accepted:", bad.columns)
bad.show()                       # the cast error appears only here

orders.select("order_total")     # but a missing column fails at once
```
```text
built a 3-step DataFrame in 0.340 s, nothing ran yet
count() is an action, it runs the job: 4
transformation accepted: ['order_id', 'customer_id', 'order_ts', 'status', 'amount', 'currency', 'currency_num']
ERROR at the action: [CAST_INVALID_INPUT] The value 'CAD' of the type "STRING" cannot be cast to "INT" because it is malformed. ... SQLSTATE: 22018
ERROR at the transformation: [UNRESOLVED_COLUMN.WITH_SUGGESTION] A column, variable, or function parameter with name `order_total` cannot be resolved. Did you mean one of the following? [`order_ts`, `order_id`, `amount`, `currency`, `status`]. SQLSTATE: 42703;
```

Two different errors, at two different moments. The bad cast is a **runtime** error: the data is only read when an action runs, so the error shows up at `show()`. The missing column is an **analysis** error: in classic Spark, building a DataFrame resolves its names against the schema right away, so `select("order_total")` fails on the spot. Under Spark Connect (serverless, standard access mode, Databricks Connect) even that analysis is deferred, so the same line would only fail at the next action or schema access (section 3.14).

!!! note "cache() on Databricks"
    The Databricks page lists "manual caching" among actions. In open-source Spark `cache()` only marks the DataFrame and the cache is filled by the next action (section 3.9). On Databricks serverless compute, the DataFrame caching page says "Databricks computes the DataFrame when you call `cache()`". Both views appear in interviews; know which platform the question is about.

### The four plans

When an action runs, Spark turns your code into a sequence of plans. `explain(extended=True)` (or SQL `EXPLAIN EXTENDED`) prints them all. The Spark `EXPLAIN` page describes them: the **parsed logical plan** is "a unresolved plan that extracted from the query"; the **analyzed logical plan** "translates unresolvedAttribute and unresolvedRelation into fully typed objects"; the **optimized logical plan** is the result of the optimizer's rules; the **physical plan** says how each step will actually run.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 250" role="img" aria-label="Your code becomes a parsed plan, an analyzed plan, an optimized plan and a physical plan; only an action executes it">
<defs><marker id="a32" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="10" y="20" width="190" height="64" rx="8"/>
<rect x="225" y="20" width="190" height="64" rx="8"/>
<rect x="440" y="20" width="190" height="64" rx="8"/>
<rect x="440" y="150" width="190" height="64" rx="8"/>
<rect x="225" y="150" width="190" height="64" rx="8"/>
<rect x="10" y="150" width="190" height="64" rx="8" stroke-dasharray="5 4"/>
<line x1="200" y1="52" x2="223" y2="52" marker-end="url(#a32)"/>
<line x1="415" y1="52" x2="438" y2="52" marker-end="url(#a32)"/>
<line x1="535" y1="84" x2="535" y2="148" marker-end="url(#a32)"/>
<line x1="440" y1="182" x2="417" y2="182" marker-end="url(#a32)"/>
<line x1="225" y1="182" x2="202" y2="182" marker-end="url(#a32)"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="105" y="46" font-size="14" font-weight="bold">Your code</text>
<text x="105" y="68">DataFrame calls or SQL</text>
<text x="320" y="46" font-size="14" font-weight="bold">Parsed logical plan</text>
<text x="320" y="68">names not resolved yet</text>
<text x="535" y="46" font-size="14" font-weight="bold">Analyzed logical plan</text>
<text x="535" y="68">columns and types known</text>
<text x="300" y="120">explain(extended=True) prints these four plans</text>
<text x="535" y="176" font-size="14" font-weight="bold">Optimized logical plan</text>
<text x="535" y="198">Catalyst rewrite rules</text>
<text x="320" y="176" font-size="14" font-weight="bold">Physical plan</text>
<text x="320" y="198">join strategy, Exchanges</text>
<text x="105" y="176" font-size="14" font-weight="bold">Execution</text>
<text x="105" y="198">only after an action</text>
<text x="105" y="238">AQE can re-plan between stages</text>
</g>
</svg>
<figcaption>Figure 3.2. Transformations only build plans. Catalyst analyzes and optimizes the logical plan and picks a physical plan; nothing runs until an action. With AQE on, the physical plan can still change at stage boundaries while the query runs (section 3.8).</figcaption>
</figure>

Here are the four plans for "total CAD spending per customer, only customers above 100", on the `silver.orders` Delta table:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
q = (spark.table("silver.orders")
     .filter(F.col("currency") == "CAD")
     .groupBy("customer_id")
     .agg(F.sum("amount").alias("total"))
     .filter(F.col("total") > 100))
q.explain(extended=True)
q.show()
```
```text
== Parsed Logical Plan ==
'Filter '`>`('total, 100)
+- Aggregate [customer_id#1393], [customer_id#1393, sum(amount#1396) AS total#1399]
   +- Filter (currency#1397 = CAD)
      +- SubqueryAlias spark_catalog.silver.orders
         +- Relation spark_catalog.silver.orders[order_id#1392,customer_id#1393,order_ts#1394,status#1395,amount#1396,currency#1397] parquet

== Analyzed Logical Plan ==
customer_id: int, total: decimal(20,2)
Filter (total#1399 > cast(cast(100 as decimal(3,0)) as decimal(20,2)))
+- Aggregate [customer_id#1393], [customer_id#1393, sum(amount#1396) AS total#1399]
   +- Filter (currency#1397 = CAD)
      +- SubqueryAlias spark_catalog.silver.orders
         +- Relation spark_catalog.silver.orders[order_id#1392,customer_id#1393,order_ts#1394,status#1395,amount#1396,currency#1397] parquet

== Optimized Logical Plan ==
Filter (isnotnull(total#1399) AND (total#1399 > 100.00))
+- Aggregate [customer_id#1393], [customer_id#1393, sum(amount#1396) AS total#1399]
   +- Project [customer_id#1393, amount#1396]
      +- Filter (isnotnull(currency#1397) AND (currency#1397 = CAD))
         +- Relation spark_catalog.silver.orders[order_id#1392,customer_id#1393,order_ts#1394,status#1395,amount#1396,currency#1397] parquet

== Physical Plan ==
AdaptiveSparkPlan isFinalPlan=false
+- Filter (isnotnull(total#1399) AND (total#1399 > 100.00))
   +- HashAggregate(keys=[customer_id#1393], functions=[sum(amount#1396)], output=[customer_id#1393, total#1399])
      +- Exchange hashpartitioning(customer_id#1393, 4), ENSURE_REQUIREMENTS, [plan_id=343]
         +- HashAggregate(keys=[customer_id#1393], functions=[partial_sum(amount#1396)], output=[customer_id#1393, sum#1669, isEmpty#1670])
            +- Project [customer_id#1393, amount#1396]
               +- Filter (isnotnull(currency#1397) AND (currency#1397 = CAD))
                  +- FileScan parquet spark_catalog.silver.orders[customer_id#1393,amount#1396,currency#1397] ... PushedFilters: [IsNotNull(currency), EqualTo(currency,CAD)], ReadSchema: struct<customer_id:int,amount:decimal(10,2),currency:string>

+-----------+------+
|customer_id| total|
+-----------+------+
|          1|327.40|
|          4|318.00|
+-----------+------+
```

How to read it, bottom up (each plan is a tree; the leaves are at the bottom):

1. **Parsed:** the names still have a leading `'` (`'Filter`, `'total`): not resolved yet.
2. **Analyzed:** every column has a type and an ID (`total#1399`), and the literal `100` got a cast to `decimal(20,2)` to match `sum(amount)`. Here a wrong column name would fail.
3. **Optimized:** the optimizer added `isnotnull` checks and a `Project [customer_id, amount]`: only two of the six columns are needed after the filter. That is **column pruning**.
4. **Physical:** the scan reads only three columns (`ReadSchema`), and the `currency = 'CAD'` filter is handed to the Parquet reader (`PushedFilters`), which is **predicate pushdown**. The aggregate is split in two: a `partial_sum` before the `Exchange` and the final `sum` after it. The `Exchange hashpartitioning(customer_id, 4)` is a shuffle (section 3.5). `AdaptiveSparkPlan isFinalPlan=false` means AQE may still change the plan at run time (section 3.8). The table is a Delta table, and the plan says `parquet` because Delta stores its data as Parquet files ([chapter 4](04-Delta-Lake.md)).

`explain()` with no argument prints only the physical plan. `explain(mode="formatted")` splits it into an outline and node details, which is easier to read for long plans:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
po = spark.read.parquet(path)          # the orders written as plain Parquet files
q2 = po.filter((F.col("currency") == "CAD") & (F.col("amount") > 100)).select("order_id", "amount")
q2.explain()
q2.explain(mode="formatted")
```
```text
== Physical Plan ==
*(1) Project [order_id#1752, amount#1756]
+- *(1) Filter (((isnotnull(currency#1757) AND isnotnull(amount#1756)) AND (currency#1757 = CAD)) AND (amount#1756 > 100.00))
   +- *(1) ColumnarToRow
      +- FileScan parquet [order_id#1752,amount#1756,currency#1757] Batched: true, DataFilters: [...], Format: Parquet, Location: ..., PartitionFilters: [], PushedFilters: [IsNotNull(currency), IsNotNull(amount), EqualTo(currency,CAD), GreaterThan(amount,100.0...

== Physical Plan ==
* Project (4)
+- * Filter (3)
   +- * ColumnarToRow (2)
      +- Scan parquet  (1)


(1) Scan parquet
Output [3]: [order_id#1752, amount#1756, currency#1757]
Batched: true
Location: InMemoryFileIndex [...]
PushedFilters: [IsNotNull(currency), IsNotNull(amount), EqualTo(currency,CAD), GreaterThan(amount,100.00)]
ReadSchema: struct<order_id:int,amount:decimal(10,2),currency:string>

(2) ColumnarToRow [codegen id : 1]
Input [3]: [order_id#1752, amount#1756, currency#1757]

(3) Filter [codegen id : 1]
Input [3]: [order_id#1752, amount#1756, currency#1757]
Condition : (((isnotnull(currency#1757) AND isnotnull(amount#1756)) AND (currency#1757 = CAD)) AND (amount#1756 > 100.00))

(4) Project [codegen id : 1]
Output [2]: [order_id#1752, amount#1756]
Input [3]: [order_id#1752, amount#1756, currency#1757]
```

The `*(1)` prefix in the simple plan and the `[codegen id : 1]` lines in the formatted plan mark operators that Spark compiles together into one piece of generated code (here, filter and project fused into the scan's loop). The Spark "Web UI" page calls this **whole-stage code generation** and says those operations are "annotated with the code generation id", which lets you match a stage's DAG in the Stages tab to the matching query in the SQL tab.

### Catalyst and Tungsten, briefly

- **Catalyst** is the optimizer. The Databricks glossary page describes it as "the query optimization framework inside Spark SQL that turns user queries into efficient execution plans", with rules for "analysis, logical optimization, physical planning, and code generation", and techniques "like predicate pushdown, column pruning and join reordering". The parsed, analyzed, optimized and physical plans above are Catalyst's stages. The Databricks Photon page confirms that even with Photon, "the Apache Spark query optimizer (Catalyst) still plans your query".
- **Tungsten** is the execution side. The Databricks glossary page calls it "a project in Apache Spark that focuses on making Spark applications more efficient by improving how they use memory and CPU", with "explicit memory management, cache aware computation, code generation". The fused `*(1)` code generation above is the visible part.

!!! tip "In the interview"
    **"What happens when you call an action?"** Spark takes the logical plan built by your transformations, resolves names and types against the catalog (analysis), lets Catalyst rewrite it (pushdown, pruning, constant folding), chooses a physical plan (join strategies, where shuffles go), generates code, then the driver splits the physical plan into stages at shuffle boundaries and sends one task per partition to the executors. `explain(extended=True)` shows the four plans.

## 3.5 Narrow and wide transformations, shuffles, jobs, stages and tasks
*Level: intermediate.*

**The problem.** To sum orders per customer, all rows of customer 7 must end up in the same task. But the files were written in order-ID order, so customer 7's rows are spread over every input partition.

**Narrow vs wide.** A **narrow** transformation computes each output partition from one input partition: `filter`, `select`, `withColumn`, `cast`, a map-side `explode`. No data moves between executors. A **wide** transformation needs rows from many input partitions in one output partition: `groupBy().agg()`, `join` (unless one side is broadcast), `distinct`, `orderBy`, window functions with `PARTITION BY`, `repartition`. That requires a **shuffle**. The Spark RDD guide describes it: "The shuffle is Spark's mechanism for re-distributing data so that it's grouped differently across partitions. This typically involves copying data across executors and machines, making the shuffle a complex and costly operation." It "involves disk I/O, data serialization, and network I/O": map tasks write shuffle files, reduce tasks read the blocks they need.

In a physical plan, every shuffle is an **`Exchange`** node, and every `Exchange` is a **stage boundary**. Spark runs everything between two exchanges as one stage, a chain of narrow work done in one pass over each partition. A **job** is what one action starts; it has one or more stages; each stage has one **task per partition**.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 290" role="img" aria-label="One job with two stages: stage 5 has two tasks that scan and partially aggregate; a shuffle moves data; stage 6 has four tasks that finish the aggregate">
<defs><marker id="a33" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="10" y="28" width="620" height="222" rx="10" stroke-dasharray="6 4"/>
<rect x="25" y="45" width="255" height="190" rx="8"/>
<rect x="360" y="45" width="255" height="190" rx="8"/>
<rect x="55" y="118" width="80" height="44" rx="4"/>
<rect x="170" y="118" width="80" height="44" rx="4"/>
<rect x="372" y="118" width="50" height="44" rx="4"/>
<rect x="433" y="118" width="50" height="44" rx="4"/>
<rect x="494" y="118" width="50" height="44" rx="4"/>
<rect x="555" y="118" width="50" height="44" rx="4"/>
<line x1="320" y1="36" x2="320" y2="244" stroke-dasharray="3 3"/>
<line x1="282" y1="130" x2="358" y2="124" marker-end="url(#a33)"/>
<line x1="282" y1="130" x2="358" y2="156" marker-end="url(#a33)"/>
<line x1="282" y1="152" x2="358" y2="124" marker-end="url(#a33)"/>
<line x1="282" y1="152" x2="358" y2="156" marker-end="url(#a33)"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="320" y="20" font-size="14" font-weight="bold">Job 4: one action, collect() of a groupBy</text>
<text x="152" y="70" font-size="14" font-weight="bold">Stage 5 (map side)</text>
<text x="152" y="92">scan + partial aggregate</text>
<text x="95" y="145">task 1</text>
<text x="210" y="145">task 2</text>
<text x="152" y="198">1 task per input partition</text>
<text x="152" y="218">writes shuffle files</text>
<text x="487" y="70" font-size="14" font-weight="bold">Stage 6 (reduce side)</text>
<text x="487" y="92">final aggregate</text>
<text x="397" y="145">t1</text><text x="458" y="145">t2</text><text x="519" y="145">t3</text><text x="580" y="145">t4</text>
<text x="487" y="198">1 task per shuffle partition</text>
<text x="487" y="218">(shuffle partitions = 4)</text>
<text x="320" y="272">Exchange = shuffle = stage boundary</text>
</g>
</svg>
<figcaption>Figure 3.3. The groupBy run below: one action starts one job; the Exchange splits it into a map stage (one task per input partition) and a reduce stage (one task per shuffle partition). Every map task can send rows to every reduce task.</figcaption>
</figure>

### Counting jobs, stages and tasks from real runs

The script `ex02_stages.py` runs several queries on `silver.orders_big` (200,000 orders in 8 Parquet files, read as 2 input partitions) and `silver.customers_big` (1,000 customers), and counts what each action started with Spark's status tracker. For these runs AQE is off, broadcast joins are off and `spark.sql.shuffle.partitions` is 4, so the plans stay exactly as Catalyst wrote them. (Plain Parquet tables are used here so that no Delta transaction-log reads add extra jobs to the counts.)

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
spark.conf.set("spark.sql.adaptive.enabled", "false")
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
spark.conf.set("spark.sql.shuffle.partitions", "4")
big = spark.table("silver.orders_big")
cust = spark.table("silver.customers_big")

q1 = big.filter(F.col("amount") > 304).select("order_id", "amount")                 # narrow only
q2 = big.groupBy("customer_id").agg(F.count("*").alias("orders"), F.sum("amount").alias("total"))
q3 = big.join(cust, "customer_id").groupBy("customer_id").agg(F.sum("amount").alias("total"))
q4 = big.join(cust, "customer_id").groupBy("city").agg(F.sum("amount").alias("total"))
q5 = big.orderBy(F.col("amount").desc())
# each one is collected inside JobCounter(spark, "<label>"), see ex02_stages.py
```
```text
[narrow] jobs=1 stages run=1 tasks=2
  job 3 (SUCCEEDED): stage 4: 2 tasks
[groupBy] jobs=1 stages run=2 tasks=6
  job 4 (SUCCEEDED): stage 5: 2 tasks, stage 6: 4 tasks
[join+groupBy same key] jobs=1 stages run=3 tasks=8
  job 5 (SUCCEEDED): stage 7: 2 tasks, stage 8: 2 tasks, stage 9: 4 tasks
[join+groupBy city] jobs=1 stages run=4 tasks=12
  job 6 (SUCCEEDED): stage 10: 2 tasks, stage 11: 2 tasks, stage 12: 4 tasks, stage 13: 4 tasks
[orderBy] jobs=2 stages run=3 tasks=8
  job 7 (SUCCEEDED): stage 14: 2 tasks
  job 8 (SUCCEEDED): stage 15: 2 tasks, stage 16: 4 tasks
```

| Query | Exchanges in the plan | Stages | Tasks | Why |
| --- | --- | --- | --- | --- |
| filter + select | 0 | 1 | 2 | Narrow only: one pass over the 2 input partitions. |
| groupBy customer | 1 | 2 | 2 + 4 | Map stage per input partition, reduce stage per shuffle partition. |
| join, then groupBy the join key | 2 | 3 | 2 + 2 + 4 | Each join side is shuffled by `customer_id` (2 map stages), the join and the aggregate share one reduce stage: the data is already partitioned by `customer_id`, so the groupBy needs no new shuffle. |
| join, then groupBy `city` | 3 | 4 | 2 + 2 + 4 + 4 | The groupBy key differs from the join key, so a third shuffle by `city` is needed. |
| orderBy | 1 | 3 (in 2 jobs) | 2 + 2 + 4 | A global sort uses `Exchange rangepartitioning`. |

Here is the plan for the third query. Count the `Exchange` nodes; there is none above the `SortMergeJoin`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
q3.explain()
```
```text
== Physical Plan ==
*(5) HashAggregate(keys=[customer_id#15], functions=[sum(amount#18)])
+- *(5) HashAggregate(keys=[customer_id#15], functions=[partial_sum(amount#18)])
   +- *(5) Project [customer_id#15, amount#18]
      +- *(5) SortMergeJoin [customer_id#15], [customer_id#20], Inner
         :- *(2) Sort [customer_id#15 ASC NULLS FIRST], false, 0
         :  +- Exchange hashpartitioning(customer_id#15, 4), ENSURE_REQUIREMENTS, [plan_id=185]
         :     +- *(1) Filter isnotnull(customer_id#15)
         :        +- *(1) ColumnarToRow
         :           +- FileScan parquet spark_catalog.silver.orders_big[customer_id#15,amount#18] ... ReadSchema: struct<customer_id:int,amount:decimal(10,2)>
         +- *(4) Sort [customer_id#20 ASC NULLS FIRST], false, 0
            +- Exchange hashpartitioning(customer_id#20, 4), ENSURE_REQUIREMENTS, [plan_id=194]
               +- *(3) Filter isnotnull(customer_id#20)
                  +- *(3) ColumnarToRow
                     +- FileScan parquet spark_catalog.silver.customers_big[customer_id#20] ... ReadSchema: struct<customer_id:int>
```

The `orderBy` row is worth a remark. Its plan has one `Exchange rangepartitioning(amount DESC NULLS LAST, 4)`, but the run started two jobs: a short job of 2 tasks first, then the sort job. Range partitioning needs boundaries (which amounts go to partition 1, 2, 3, 4), and the extra job is Spark sampling the data to choose them. That explanation comes from how Spark's range partitioner works; it is not described on the documentation pages cited in this chapter, so treat it as background, not as a documented guarantee. With AQE on (the default), the job count changes again: AQE runs each shuffle stage on its own and re-plans after it, so the Spark UI shows more, smaller jobs for one action (section 3.8).

!!! tip "In the interview"
    **"How does Spark decide the number of stages and tasks?"** Stages are cut at shuffle boundaries: every `Exchange` in the physical plan ends a stage, so stages = exchanges + 1 for a simple linear plan (a join adds one map stage per shuffled side). Tasks per stage = partitions of that stage: input splits for a scan stage, `spark.sql.shuffle.partitions` (or what AQE coalesces it to) for a stage after a shuffle. A stage can only start when the stages it reads from have finished.

!!! warning "Fewer shuffles is the first tuning rule"
    Most slow Spark jobs are slow in a shuffle: too much data moved, too few or too many shuffle partitions, or one huge partition (skew). Before tuning settings, look at the plan: can a broadcast join remove a shuffle? Can you filter or select fewer columns before the shuffle? Is a `repartition` really needed?

## 3.6 Partitions
*Level: intermediate.*

A **partition** is a chunk of rows processed by one task. Too few partitions and most cores sit idle; too many and the scheduling overhead of tiny tasks dominates. There are three places where the partition count is decided:

| Where | Setting (default, from the Spark configuration page) | What it means |
| --- | --- | --- |
| Reading files | `spark.sql.files.maxPartitionBytes` = 128 MB | "The maximum number of bytes to pack into a single partition when reading files" (Parquet, JSON, ORC and other file sources). Small files are packed together; large splittable files are split. |
| After a shuffle (joins, aggregations) | `spark.sql.shuffle.partitions` = **200** | "The default number of partitions to use when shuffling data for joins or aggregations." AQE can coalesce them at run time. |
| RDD operations and new data | `spark.default.parallelism` | In local mode, the number of cores; on a cluster, "total number of cores on all executor nodes or 2, whichever is larger". |

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
print("value set by the local helper:", spark.conf.get("spark.sql.shuffle.partitions"))
spark.conf.unset("spark.sql.shuffle.partitions")
print("after unset (the built-in default):", spark.conf.get("spark.sql.shuffle.partitions"))

path = ".../orders_one_file"             # one Parquet file of 400,000 generated orders
print("maxPartitionBytes default:", spark.conf.get("spark.sql.files.maxPartitionBytes"))
print("read partitions:", spark.read.parquet(path).rdd.getNumPartitions())
spark.conf.set("spark.sql.files.maxPartitionBytes", "1mb")
print("read partitions with maxPartitionBytes=1mb:", spark.read.parquet(path).rdd.getNumPartitions())
```
```text
value set by the local helper: 4
after unset (the built-in default): 200
one parquet file of 4.1 MB
maxPartitionBytes default: 134217728b
read partitions: 2
read partitions with maxPartitionBytes=1mb: 5
```

The 4.1 MB file is far below 128 MB, yet it was read as 2 partitions: Spark also aims for a minimum number of file partitions, `spark.sql.files.minPartitionNum`, which the configuration page calls "suggested (not guaranteed)" and which defaults to `spark.sql.leafNodeDefaultParallelism`, itself the default parallelism (2 here, one per core). The exact split-size formula that combines these settings is not on the configuration page, so it is not verified here. Lowering `maxPartitionBytes` to 1 MB gave 5 partitions.

### repartition vs coalesce

| | `repartition(n)` / `repartition(n, cols)` | `coalesce(n)` |
| --- | --- | --- |
| Shuffle | Yes, a full shuffle (`Exchange`) | No. The PySpark docs: it "results in a narrow dependency", each new partition "will claim" several current ones |
| Direction | Up or down | Only down; asking for more "will stay at the current number of partitions" |
| Balance | Even (round robin), or by hash of the columns | Can be uneven: it merges neighbors |
| Use it for | More parallelism, even partitions, co-locating keys before a write | Fewer output files cheaply at the end of a job |

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
spark.conf.set("spark.sql.shuffle.partitions", "4")
spark.conf.set("spark.sql.adaptive.enabled", "false")
orders = gen_orders(spark, 100_000)                 # 2 partitions in local[2]

r8 = orders.repartition(8)
r8.explain()
c2 = r8.coalesce(2)
c2.explain()
print(r8.coalesce(16).rdd.getNumPartitions())
rc = orders.repartition("currency")
rc.explain()
```
```text
== Physical Plan ==
Exchange RoundRobinPartitioning(8), REPARTITION_BY_NUM, [plan_id=20]
+- *(1) Project [...]
   +- *(1) Range (0, 100000, step=1, splits=2)
partitions: 8 rows per partition: [12500, 12500, 12500, 12500, 12500, 12500, 12500, 12500]

== Physical Plan ==
Coalesce 2
+- Exchange RoundRobinPartitioning(8), REPARTITION_BY_NUM, [plan_id=105]
   +- ...
partitions: 2 rows per partition: [50000, 50000]

8

== Physical Plan ==
Exchange hashpartitioning(currency#6, 4), REPARTITION_BY_COL, [plan_id=211]
+- ...
partitions: 4 rows per partition: [33334, 66666]
```

Read the last result carefully: `repartition("currency")` made 4 partitions (the shuffle partition setting), but only 2 hold rows, because there are only two currencies and all rows with the same value hash to the same partition. Repartitioning by a low-cardinality column gives empty partitions and, with uneven values, skew.

!!! warning "coalesce(1) to get one file"
    `df.coalesce(1).write...` gives a single output file, but the coalesce is narrow, so the work before it may also run in one task. The PySpark docs warn that a drastic coalesce "may result in your computation taking place on fewer nodes than you like" and suggest `repartition()` instead, which adds a shuffle but keeps the upstream work parallel. On Databricks, the "Long Spark stage with one task" page lists `repartition(1)` or `coalesce(1)` as a common cause of a one-task stage. Most tables never need a single file.

### partitionBy on write, and partition pruning

`partitionBy` on a writer stores each value of a column in its own folder (`order_date=2026-03-02/`). When a query filters on that column, Spark lists only the matching folders: **partition pruning**. The plan shows it under `PartitionFilters`, separate from `PushedFilters` (row-group filters inside the files).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
daily = orders.withColumn("order_date", F.to_date("order_ts")).filter(F.col("order_date") <= "2026-03-05")
daily.repartition(4).write.mode("overwrite").partitionBy("order_date").parquet(out)
by_date = spark.read.parquet(out)
q = by_date.filter((F.col("order_date") == "2026-03-02") & (F.col("currency") == "CAD"))
q.explain()
```
```text
folders: ['order_date=2026-03-01', 'order_date=2026-03-02', 'order_date=2026-03-03', 'order_date=2026-03-04', 'order_date=2026-03-05']
files in one folder: 4
== Physical Plan ==
*(1) Filter (isnotnull(currency#71) AND (currency#71 = CAD))
+- *(1) ColumnarToRow
   +- FileScan parquet [order_id#66,...,order_date#72] ... PartitionFilters: [isnotnull(order_date#72), (order_date#72 = 2026-03-02)], PushedFilters: [IsNotNull(currency), EqualTo(currency,CAD)], ...
rows: 2880
```

Note "files in one folder: 4": each of the 4 partitions of the DataFrame wrote one file into every date folder it had rows for. Partitions times folders is how small-file problems start. Pruning only works when the filter is on the partition column itself; a filter on `order_ts` does not prune `order_date` folders (practice question 15).

!!! note "Partitioning tables on Databricks"
    Folder partitioning is a Spark and Hive idea, and Delta tables support it, but the Databricks page "When to partition tables on Databricks" says "Databricks recommends liquid clustering for all managed tables" and "most tables on Databricks with less than 100 TB of data don't need partitioning". Table layout (partitioning, liquid clustering, Z-order, file sizes) is covered in [chapter 22](22-Performance-Tuning.md). The partitions in this section are in-memory partitions of a DataFrame, which every Spark job has.

!!! tip "In the interview"
    **"What is spark.sql.shuffle.partitions and how do you set it?"** It is the number of partitions after a shuffle for joins and aggregations; the default is 200. 200 is too many for a small job (200 tiny tasks) and too few for terabytes (huge partitions that spill). With AQE (on by default since Spark 3.2), Spark coalesces small post-shuffle partitions at run time, so you can leave it at a generous value; on Databricks you can also set it to `auto` (section 3.8).

## 3.7 Joins: broadcast hash, sort-merge, shuffle hash
*Level: intermediate.*

**The problem.** To join 200,000 orders to 1,000 customers, matching rows must meet in the same task. Spark can either move the small table to every task, or shuffle both tables so that equal keys land in the same partition. Which one it picks decides whether the join takes seconds or minutes.

| Strategy | How it works | Shuffle | Typical case |
| --- | --- | --- | --- |
| **Broadcast hash join** (BHJ) | The small side is collected and sent whole to every executor; each task builds a hash table of it and streams its partition of the big side through. | None on the big side | One side small: dimension tables, lookups |
| **Sort-merge join** (SMJ) | Both sides are shuffled by the join key, sorted within each partition, then merged. | Both sides | Two large tables; the default for big equi-joins |
| **Shuffle hash join** (SHJ) | Both sides shuffled by key; each task builds a hash table of its partition of the smaller side. | Both sides | Large tables where one side's partitions fit in memory |
| **Broadcast nested loop join** | One side broadcast; every pair of rows compared. | None | Non-equi conditions (`<`, `BETWEEN`) or no condition; expensive |

**When does Spark broadcast?** When the estimated size of a side is below `spark.sql.autoBroadcastJoinThreshold`, which the Spark configuration page defines as "the maximum size in bytes for a table that will be broadcast to all worker nodes when performing a join", default **10 MB**. "By setting this value to -1 broadcasting can be disabled." The estimate comes from statistics (file sizes, table statistics), so a stale or missing estimate can cause the wrong choice.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Left: broadcast hash join copies the small customers table to each executor and does not shuffle orders. Right: sort-merge join shuffles both orders and customers by customer_id, sorts and merges">
<defs><marker id="a34" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<line x1="320" y1="10" x2="320" y2="292" stroke-dasharray="2 4"/>
<rect x="95" y="36" width="130" height="30" rx="4"/>
<rect x="20" y="130" width="85" height="100" rx="6"/>
<rect x="118" y="130" width="85" height="100" rx="6"/>
<rect x="216" y="130" width="85" height="100" rx="6"/>
<line x1="160" y1="66" x2="64" y2="127" stroke-dasharray="5 3" marker-end="url(#a34)"/>
<line x1="160" y1="66" x2="160" y2="127" stroke-dasharray="5 3" marker-end="url(#a34)"/>
<line x1="160" y1="66" x2="256" y2="127" stroke-dasharray="5 3" marker-end="url(#a34)"/>
<rect x="345" y="36" width="120" height="30" rx="4"/>
<rect x="495" y="36" width="120" height="30" rx="4"/>
<rect x="340" y="130" width="85" height="100" rx="6"/>
<rect x="438" y="130" width="85" height="100" rx="6"/>
<rect x="536" y="130" width="85" height="100" rx="6"/>
<line x1="405" y1="66" x2="382" y2="127" marker-end="url(#a34)"/>
<line x1="405" y1="66" x2="480" y2="127" marker-end="url(#a34)"/>
<line x1="405" y1="66" x2="578" y2="127" marker-end="url(#a34)"/>
<line x1="555" y1="66" x2="382" y2="127" marker-end="url(#a34)"/>
<line x1="555" y1="66" x2="480" y2="127" marker-end="url(#a34)"/>
<line x1="555" y1="66" x2="578" y2="127" marker-end="url(#a34)"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="160" y="24" font-size="15" font-weight="bold">Broadcast hash join</text>
<text x="160" y="56">customers (small)</text>
<text x="62" y="158">orders p1</text><text x="62" y="180">+ customers</text><text x="62" y="202">hash join</text>
<text x="160" y="158">orders p2</text><text x="160" y="180">+ customers</text><text x="160" y="202">hash join</text>
<text x="258" y="158">orders p3</text><text x="258" y="180">+ customers</text><text x="258" y="202">hash join</text>
<text x="160" y="258">big side is not shuffled</text>
<text x="160" y="280">plan: BroadcastExchange</text>
<text x="480" y="24" font-size="15" font-weight="bold">Sort-merge join</text>
<text x="405" y="56">orders</text>
<text x="555" y="56">customers</text>
<text x="382" y="158">keys hash 0</text><text x="382" y="180">sort both</text><text x="382" y="202">merge</text>
<text x="480" y="158">keys hash 1</text><text x="480" y="180">sort both</text><text x="480" y="202">merge</text>
<text x="578" y="158">keys hash 2</text><text x="578" y="180">sort both</text><text x="578" y="202">merge</text>
<text x="480" y="258">both sides shuffled by key</text>
<text x="480" y="280">plan: Exchange + Sort</text>
</g>
</svg>
<figcaption>Figure 3.4. A broadcast hash join sends the small table to every executor and leaves the big table where it is. A sort-merge join shuffles both tables by the join key so equal keys meet in the same partition, then sorts and merges each partition.</figcaption>
</figure>

### Watching the plan change

The same join, four ways. AQE is off here so that you see the static plans.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
print(spark.conf.get("spark.sql.autoBroadcastJoinThreshold"))
spark.conf.set("spark.sql.adaptive.enabled", "false")

def join_df():
    return orders.join(cust, "customer_id").select("order_id", "amount", "city")

join_df().explain()                                              # 1. defaults
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
join_df().explain()                                              # 2. broadcasting off
orders.join(F.broadcast(cust), "customer_id").select("order_id", "amount", "city").explain()   # 3. hint
orders.join(cust.hint("shuffle_hash"), "customer_id").select("order_id", "amount", "city").explain()  # 4.
```
```text
10485760b

== Physical Plan ==                                      (1. defaults)
*(2) Project [order_id#14, amount#18, city#23]
+- *(2) BroadcastHashJoin [customer_id#15], [customer_id#20], Inner, BuildRight, false, false
   :- *(2) Filter isnotnull(customer_id#15)
   :  +- *(2) ColumnarToRow
   :     +- FileScan parquet spark_catalog.silver.orders_big[order_id#14,customer_id#15,amount#18] ...
   +- BroadcastExchange HashedRelationBroadcastMode(List(cast(input[0, int, false] as bigint)),false), [plan_id=95]
      +- *(1) Filter isnotnull(customer_id#20)
         +- *(1) ColumnarToRow
            +- FileScan parquet spark_catalog.silver.customers_big[customer_id#20,city#23] ...

== Physical Plan ==                                      (2. threshold -1)
*(5) Project [order_id#14, amount#18, city#23]
+- *(5) SortMergeJoin [customer_id#15], [customer_id#20], Inner
   :- *(2) Sort [customer_id#15 ASC NULLS FIRST], false, 0
   :  +- Exchange hashpartitioning(customer_id#15, 4), ENSURE_REQUIREMENTS, [plan_id=153]
   :     +- *(1) Filter isnotnull(customer_id#15)
   :        +- *(1) ColumnarToRow
   :           +- FileScan parquet spark_catalog.silver.orders_big[order_id#14,customer_id#15,amount#18] ...
   +- *(4) Sort [customer_id#20 ASC NULLS FIRST], false, 0
      +- Exchange hashpartitioning(customer_id#20, 4), ENSURE_REQUIREMENTS, [plan_id=162]
         +- *(3) Filter isnotnull(customer_id#20)
            +- *(3) ColumnarToRow
               +- FileScan parquet spark_catalog.silver.customers_big[customer_id#20,city#23] ...

== Physical Plan ==                                      (3. broadcast hint, threshold still -1)
*(2) Project [order_id#14, amount#18, city#23]
+- *(2) BroadcastHashJoin [customer_id#15], [customer_id#20], Inner, BuildRight, false, false
   ...
   +- BroadcastExchange HashedRelationBroadcastMode(List(cast(input[0, int, false] as bigint)),false), [plan_id=228]
      ...

== Physical Plan ==                                      (4. shuffle_hash hint)
*(3) Project [order_id#14, amount#18, city#23]
+- *(3) ShuffledHashJoin [customer_id#15], [customer_id#20], Inner, BuildRight
   :- Exchange hashpartitioning(customer_id#15, 4), ENSURE_REQUIREMENTS, [plan_id=257]
   :  +- ...
   +- Exchange hashpartitioning(customer_id#20, 4), ENSURE_REQUIREMENTS, [plan_id=263]
      +- ...
```

What each plan tells you:

1. **`BroadcastHashJoin ... BuildRight`** with a `BroadcastExchange` on the customers side: customers (right side) was under 10 MB, so it is the build side and orders is never shuffled. One stage does scan and join.
2. **`SortMergeJoin`** with an `Exchange hashpartitioning(customer_id, 4)` and a `Sort` on each side: two shuffles and two sorts.
3. The **hint wins** over the disabled threshold. The Spark tuning page says a `BROADCAST` hint makes Spark prefer broadcasting that side "even if the size of table 't1' suggested by the statistics is above the configuration `spark.sql.autoBroadcastJoinThreshold`".
4. **`ShuffledHashJoin`**: both sides shuffled, no `Sort` nodes; a hash table is built from each partition of the customers side.

The same hint in SQL:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT /*+ BROADCAST(c) */ o.order_id, o.amount, c.city
FROM silver.orders_big o JOIN silver.customers_big c ON o.customer_id = c.customer_id;
```

Its plan, printed with `EXPLAIN`, is the same `BroadcastHashJoin ... BuildRight` as plan 3 (full output in `ex04_joins.out`). Spark accepts `BROADCAST`, `BROADCASTJOIN` and `MAPJOIN` for broadcast, plus `MERGE` (`SHUFFLE_MERGE`, `MERGEJOIN`), `SHUFFLE_HASH` and `SHUFFLE_REPLICATE_NL`. When both sides carry different hints, the Spark tuning page gives the priority "`BROADCAST` hint over the `MERGE` hint over the `SHUFFLE_HASH` hint over the `SHUFFLE_REPLICATE_NL` hint", and it warns: "there is no guarantee that Spark will choose the join strategy specified in the hint since a specific strategy may not support all join types." The Databricks Hints page lists the same join hints with the same priority.

A non-equi join cannot hash or sort-merge on a key:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
orders.join(F.broadcast(cust), orders.customer_id < cust.customer_id).select("order_id").explain()
```
```text
== Physical Plan ==
*(2) Project [order_id#14]
+- *(2) BroadcastNestedLoopJoin BuildRight, Inner, (customer_id#15 < customer_id#20)
   ...
   +- BroadcastExchange IdentityBroadcastMode, [plan_id=326]
      ...
```

!!! warning "A DataFrame keeps its plan"
    In these runs the join is rebuilt with `join_df()` after each configuration change. A DataFrame object plans itself once; calling `explain()` again on the same object after `spark.conf.set(...)` showed the old broadcast plan in a first attempt of this script. Build a new DataFrame (or rerun the cell that defines it) after changing a setting.

!!! warning "Broadcasting something big"
    A broadcast side is collected and copied to every executor. Hinting `BROADCAST` on a large table can exhaust driver or executor memory; the Databricks "Spark memory issues" page lists "a large broadcast" among the common causes and says to "check for broadcast join hints on large tables". The broadcast also has a timeout, `spark.sql.broadcastTimeout`, default 300 seconds.

!!! tip "In the interview"
    **"How do you make a join between a big fact table and a small dimension faster?"** Make it a broadcast hash join: the dimension is copied to every executor and the fact table is not shuffled. Spark does this automatically when the dimension's estimated size is under `spark.sql.autoBroadcastJoinThreshold` (10 MB by default); otherwise use `F.broadcast(dim)` or `/*+ BROADCAST(d) */`. Check with `explain()`: `BroadcastHashJoin` and `BroadcastExchange` instead of `SortMergeJoin` with two `Exchange` nodes. Only broadcast what fits comfortably in memory.

## 3.8 Adaptive query execution and data skew
*Level: expert.*

**The problem.** Catalyst plans a query before it runs, from estimates. The Databricks AQE page lists how those estimates go wrong: "if table statistics are missing or stale, if the data is skewed, or for later steps in a complex query". A plan built on wrong estimates "might use a slow join strategy, create too many small tasks after a shuffle, or create a few oversized tasks that hold up the whole stage."

**The tool: adaptive query execution (AQE).** AQE re-optimizes the plan while the query runs. At the end of each shuffle or broadcast exchange, the engine knows the real size of the data produced so far, and AQE uses that to change the rest of the plan. The Spark tuning page says AQE "is enabled by default since Apache Spark 3.2.0", controlled by `spark.sql.adaptive.enabled` (default `true`). Its main features in open-source Spark:

| Feature | What it does | Key settings and defaults (Spark 4.2 docs) |
| --- | --- | --- |
| Coalescing post-shuffle partitions | Merges small shuffle partitions into fewer, larger ones | `spark.sql.adaptive.coalescePartitions.enabled` = true; `spark.sql.adaptive.advisoryPartitionSizeInBytes` = 64 MB; `...coalescePartitions.minPartitionSize` = 1 MB; `...coalescePartitions.parallelismFirst` = true |
| Converting sort-merge join to broadcast join | If one side turns out small at run time, switches to a broadcast hash join and reads shuffle files locally | `spark.sql.adaptive.autoBroadcastJoinThreshold` (none: same as `spark.sql.autoBroadcastJoinThreshold`); `spark.sql.adaptive.localShuffleReader.enabled` = true |
| Converting sort-merge join to shuffled hash join | When all post-shuffle partitions are small enough | `spark.sql.adaptive.maxShuffledHashJoinLocalMapThreshold` = 0 (off) |
| Optimizing skew join | Splits (and replicates if needed) skewed partitions into evenly sized tasks | `spark.sql.adaptive.skewJoin.enabled` = true; `...skewedPartitionFactor` = 5.0; `...skewedPartitionThresholdInBytes` = 256 MB |

A note on `parallelismFirst`: the Spark page says that when it is true (the default), Spark ignores the 64 MB advisory size when coalescing and only respects the 1 MB minimum, "to maximize the parallelism", and recommends setting it to false "on a busy cluster".

AQE applies to queries with at least one exchange or subquery, and not to streaming queries (Databricks AQE page). It cannot change a plan that has not started: the Databricks page notes that SQL `EXPLAIN` "doesn't run the query, so AQE can't re-optimize it", while `DataFrame.explain()` after the query has run shows the initial plan and the final plan.

### AQE coalescing partitions

Section 3.5's groupBy, run again with AQE on and the default 200 shuffle partitions:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.shuffle.partitions", "200")
q6 = big.groupBy("customer_id").agg(F.count("*").alias("orders"))
rows = q6.collect()        # counted with JobCounter
q6.explain()               # after the action: the final plan
```
```text
[groupBy AQE] jobs=2 stages run=2 tasks=3
  job 9 (SUCCEEDED): stage 17: 2 tasks
  job 10 (SUCCEEDED): stage 18: skipped, stage 19: 1 tasks
== Physical Plan ==
AdaptiveSparkPlan isFinalPlan=true
+- == Final Plan ==
   ResultQueryStage 1
   +- *(2) HashAggregate(keys=[customer_id#15], functions=[count(1)])
      +- AQEShuffleRead coalesced
         +- ShuffleQueryStage 0
            +- Exchange hashpartitioning(customer_id#15, 200), ENSURE_REQUIREMENTS, [plan_id=547]
               +- *(1) HashAggregate(keys=[customer_id#15], functions=[partial_count(1)])
                  +- *(1) ColumnarToRow
                     +- FileScan parquet spark_catalog.silver.orders_big[customer_id#15] ...
+- == Initial Plan ==
   HashAggregate(keys=[customer_id#15], functions=[count(1)])
   +- Exchange hashpartitioning(customer_id#15, 200), ENSURE_REQUIREMENTS, [plan_id=533]
      +- HashAggregate(keys=[customer_id#15], functions=[partial_count(1)])
         +- FileScan parquet spark_catalog.silver.orders_big[customer_id#15] ...
```

The plan asked for 200 shuffle partitions, but the shuffle wrote only a few kilobytes, so AQE read it back as one coalesced partition: the reduce stage ran **1 task instead of 200**. `AQEShuffleRead coalesced` is the node that shows it (the Databricks AQE page still describes it as a `CustomShuffleReader` node with the `Coalesced` property). Note also the shape of the run: two jobs, the first runs the map stage (`ShuffleQueryStage 0`), then AQE re-plans and a second job runs the rest; the map stage shows as "skipped" in the second job because its output already exists.

### AQE switching a sort-merge join to a broadcast join

Here broadcasting is off at planning time (`spark.sql.autoBroadcastJoinThreshold = -1`) but allowed for AQE (`spark.sql.adaptive.autoBroadcastJoinThreshold = 10MB`). Catalyst cannot know that only Canadian customers survive the filter, so it plans a sort-merge join; after the shuffle, AQE sees how small the customers side really is.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
spark.conf.set("spark.sql.adaptive.autoBroadcastJoinThreshold", "10MB")
canada = cust.filter(F.col("country") == "CA")
ja = orders.join(canada, "customer_id").groupBy("city").agg(F.sum("amount").alias("total"))
ja.explain()           # before
print(sorted(ja.collect()))
ja.explain()           # after
```
```text
== Physical Plan ==
AdaptiveSparkPlan isFinalPlan=false
+- HashAggregate(keys=[city#23], functions=[sum(amount#18)])
   +- Exchange hashpartitioning(city#23, 4), ENSURE_REQUIREMENTS, [plan_id=461]
      +- HashAggregate(keys=[city#23], functions=[partial_sum(amount#18)])
         +- Project [amount#18, city#23]
            +- SortMergeJoin [customer_id#15], [customer_id#20], Inner
               :- Sort [customer_id#15 ASC NULLS FIRST], false, 0
               :  +- Exchange hashpartitioning(customer_id#15, 4), ENSURE_REQUIREMENTS, [plan_id=453]
               :     +- ...
               +- Sort [customer_id#20 ASC NULLS FIRST], false, 0
                  +- Exchange hashpartitioning(customer_id#20, 4), ENSURE_REQUIREMENTS, [plan_id=454]
                     +- ...

[Row(city='Boulder', total=Decimal('4978572.00')), Row(city='Denver', total=Decimal('5010428.00')), Row(city='Vancouver', total=Decimal('5010000.00'))]

== Physical Plan ==
AdaptiveSparkPlan isFinalPlan=true
+- == Final Plan ==
   ResultQueryStage 4
   +- *(4) HashAggregate(keys=[city#23], functions=[sum(amount#18)])
      +- AQEShuffleRead coalesced
         +- ShuffleQueryStage 3
            +- Exchange hashpartitioning(city#23, 4), ENSURE_REQUIREMENTS, [plan_id=626]
               +- *(3) HashAggregate(keys=[city#23], functions=[partial_sum(amount#18)])
                  +- *(3) Project [amount#18, city#23]
                     +- *(3) BroadcastHashJoin [customer_id#15], [customer_id#20], Inner, BuildRight, false, false
                        :- AQEShuffleRead local
                        :  +- ShuffleQueryStage 0
                        :     +- Exchange hashpartitioning(customer_id#15, 4), ENSURE_REQUIREMENTS, [plan_id=494]
                        :        +- ...
                        +- BroadcastQueryStage 2
                           +- BroadcastExchange HashedRelationBroadcastMode(List(cast(input[0, int, true] as bigint)),false), [plan_id=562]
                              +- AQEShuffleRead local
                                 +- ShuffleQueryStage 1
                                    +- Exchange hashpartitioning(customer_id#20, 4), ENSURE_REQUIREMENTS, [plan_id=513]
                                       +- ...
+- == Initial Plan ==
   (the SortMergeJoin plan shown above)
```

The final plan has a `BroadcastHashJoin` where the initial plan had a `SortMergeJoin`, the `Sort` nodes are gone, and `AQEShuffleRead local` means each task reads the shuffle files locally instead of fetching them over the network. Both sides were still shuffled, though: AQE only learns the real size after the shuffle. The Spark page puts it plainly: this "is not as efficient as planning a broadcast hash join in the first place". That is why the Databricks AQE FAQ still recommends a broadcast hint "if you know your query well".

When the whole script was run again later on the same busy machine, AQE made the same switch but broadcast the other side (`BuildLeft`: the orders shuffle output was also small enough here). The lesson is the switch from sort-merge to broadcast; which side AQE picks can differ from run to run when both sides are small.

### Data skew

**Skew** means one key has far more rows than the others. All rows of one key go to one shuffle partition, so one task does most of the work while the other cores wait. The Databricks "Skew and spill" page tells you how to spot it in the Spark UI: in the stage's **Summary Metrics**, "compare the **Max** duration to the 75th percentile duration ... If the Max duration exceeds the 75th percentile by 50% or more, the stage might have skew."

To see skew here, the script generates 400,000 orders where 60% belong to customer 7, then joins them to customers with a forced sort-merge join and 8 shuffle partitions:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
sk = spark.table("silver.orders_skewed")
sk.groupBy("customer_id").count().orderBy(F.desc("count")).show(3)

spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
spark.conf.set("spark.sql.adaptive.autoBroadcastJoinThreshold", "-1")
spark.conf.set("spark.sql.shuffle.partitions", "8")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "false")

def skew_join():
    return (sk.join(cust, "customer_id").groupBy("country")
            .agg(F.count("*").alias("orders"), F.sum("amount").alias("total"),
                 F.max("order_ts").alias("last_ts")))

spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "false")
skew_join().collect()                                    # run 1: skew handling off

spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "256KB")  # demo only
spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "256KB")              # demo only
js = skew_join()
js.collect()                                             # run 2: skew handling on
js.explain()
```
```text
+-----------+------+
|customer_id| count|
+-----------+------+
|          7|240521|
|        355|   187|
|        232|   187|
+-----------+------+
only showing top 3 rows

[skew off] jobs=4 stages run=4 tasks=20
  job 12 (SUCCEEDED): stage 17: skipped, stage 18: skipped, stage 19: 8 tasks
[skew on] jobs=4 stages run=4 tasks=21
  job 16 (SUCCEEDED): stage 26: skipped, stage 27: skipped, stage 28: 9 tasks

== Physical Plan ==
AdaptiveSparkPlan isFinalPlan=true
+- == Final Plan ==
   ...
                  +- *(5) SortMergeJoin(skew=true) [customer_id#62], [customer_id#20], Inner
                     :- *(3) Sort [customer_id#62 ASC NULLS FIRST], false, 0
                     :  +- AQEShuffleRead skewed
                     :     +- ShuffleQueryStage 0
                     :        +- Exchange hashpartitioning(customer_id#62, 8), ENSURE_REQUIREMENTS, [plan_id=1003]
                     +- *(4) Sort [customer_id#20 ASC NULLS FIRST], false, 0
                        +- AQEShuffleRead
                           +- ShuffleQueryStage 1
                              +- Exchange hashpartitioning(customer_id#20, 8), ENSURE_REQUIREMENTS, [plan_id=1020]
```

(Only the join stage of each run is shown above; the full job list is in `ex04_joins.out`.) With skew handling on, the join stage ran **9 tasks instead of 8**: AQE split the partition holding customer 7 into two pieces and replicated the matching customers partition for each piece. The plan shows it as `SortMergeJoin(skew=true)` and `AQEShuffleRead skewed` (the Databricks page describes the same signal as "a `SortMergeJoin` node with the `isSkew` field set to `true`"). The two thresholds were lowered only because this demo data is tiny. With the defaults, a partition counts as skewed only if it is larger than **both** `skewedPartitionFactor` (5) times the median partition size **and** `skewedPartitionThresholdInBytes` (256 MB).

The Databricks AQE page adds limits worth knowing: AQE handles skew "only in shuffle-based joins, which are sort merge joins and shuffle hash joins. It never optimizes skew in broadcast joins", and the join type decides which side can be split (for example a `LEFT OUTER` join can be optimized on the left side only, a `FULL OUTER` join on neither side).

**Salting**, when AQE cannot help (a skewed aggregation, a `FULL OUTER` join, or older runtimes): add a random "salt" column so the hot key is spread over several partitions, then combine. Here is the effect on the partition sizes when the skewed orders are repartitioned by key:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
def part_sizes(df):
    return sorted((r[1] for r in df.groupBy(F.spark_partition_id()).count().collect()), reverse=True)

print(part_sizes(sk.repartition(8, "customer_id")))
salted = sk.withColumn("salt", (F.rand(1) * 8).cast("int"))
print(part_sizes(salted.repartition(8, "customer_id", "salt")))

# salted join: the big side gets salt 0-7, the small side is copied once per salt value
cust_salted = cust.withColumn("salt", F.explode(F.sequence(F.lit(0), F.lit(7))))
print(sk.join(cust, "customer_id").count(), salted.join(cust_salted, ["customer_id", "salt"]).count())
```
```text
[260456, 21622, 21447, 21374, 20051, 19482, 17905, 17663]
[80306, 80294, 80089, 50198, 49530, 20488, 20014, 19081]
400000 400000
```

The largest partition went from 260,456 rows to about 80,000. It is not perfectly even because the 8 salted keys of customer 7 are hashed into 8 partitions and some collide; more salt values spread it further. The salted join returns the same 400,000 rows, because every order still finds exactly one copy of its customer. For aggregations, salt in two steps: aggregate by `(key, salt)`, then by `key` (practice question 25).

### Databricks differences

The Databricks AQE page (last updated Oct 12, 2026) documents Databricks settings and defaults. Some names also exist in open-source Spark (`spark.sql.shuffle.partitions`), but the values below, such as `auto` and `30MB`, are what Databricks documents. Labeled Databricks only:

| Databricks setting | Default (Databricks page) | What it does |
| --- | --- | --- |
| `spark.databricks.optimizer.adaptive.enabled` | `true` | Turns AQE on or off |
| `spark.sql.shuffle.partitions` | `200`, or `auto` | "Set it to `auto` to enable auto-optimized shuffle, which sets this number based on the query plan and the query input data size." |
| `spark.databricks.adaptive.autoBroadcastJoinThreshold` | `30MB` | "The size threshold for switching a sort merge join to a broadcast hash join at runtime." |
| `spark.databricks.adaptive.emptyRelationPropagation.enabled` | `true` | Dynamic empty relation propagation: parts of the plan known to return no rows are replaced |
| `spark.sql.adaptive.coalescePartitions.minPartitionNum` | "Two times the number of cluster cores" | Minimum partitions after coalescing; the page says "Don't set this property" |

The Databricks page lists AQE's four major features as changing sort-merge join to broadcast hash join, coalescing partitions, handling skew "in sort merge join and shuffle hash join", and detecting and propagating empty relations.

*Databricks only, not run here. Syntax from [Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe).*
```python
spark.conf.set("spark.sql.shuffle.partitions", "auto")   # auto-optimized shuffle
```

The older Databricks `SKEW` join hint still has a page, but it is marked as retired, and it says "Skew join hints are not required. Databricks handles skew by default by using adaptive query execution (AQE)."

!!! tip "In the interview"
    **"What is AQE and what does it do?"** Adaptive query execution re-optimizes a query while it runs, using the real sizes measured at each shuffle or broadcast. It coalesces small shuffle partitions, switches a sort-merge join to a broadcast join when a side turns out small, and splits skewed partitions in sort-merge and shuffle hash joins (the Databricks page also lists empty-relation propagation as a fourth feature). It is on by default since Spark 3.2 and on Databricks. It cannot reorder joins, cannot help a broadcast join's skew, and only kicks in after a shuffle, so a planned broadcast is still better than a runtime switch.

## 3.9 Caching and persistence
*Level: intermediate.*

**The problem.** A notebook builds `enriched` = orders joined to customers with a derived date, then computes five different reports from it. Without caching, each report's action re-reads the files and redoes the join, because transformations are recomputed for every action.

**The tool.** `cache()` and `persist()` keep a DataFrame's computed partitions on the executors after the first action that computes it, so later actions read them instead of recomputing.

| | `df.cache()` | `df.persist(level)` | SQL `CACHE TABLE` |
| --- | --- | --- | --- |
| Storage level | the default: `MEMORY_AND_DISK_DESER` for DataFrames (PySpark docs) | the level you pass | `MEMORY_AND_DISK` unless `OPTIONS ('storageLevel' ...)` |
| When it fills | at the next action (lazy) | at the next action (lazy) | right away, unless `CACHE LAZY TABLE` |
| Remove | `df.unpersist()` | `df.unpersist()` | `UNCACHE TABLE` |

The storage levels trade memory for CPU and disk: `MEMORY_ONLY` (partitions that do not fit are recomputed when needed), `MEMORY_AND_DISK` (they spill to disk instead), `DISK_ONLY`, and `_2` variants that replicate each partition on two nodes. The RDD guide notes that for RDDs the default is `MEMORY_ONLY`; for DataFrames the PySpark docs say "the default storage level has changed to MEMORY_AND_DISK_DESER to match Scala in 3.0". Cached partitions are evicted "in a least-recently-used (LRU) fashion" when memory runs short, and a lost cached partition is simply recomputed from its lineage.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
enriched = (orders.join(cust, "customer_id")
            .withColumn("order_date", F.to_date("order_ts"))
            .select("order_id", "order_date", "city", "status", "amount"))
enriched.cache()
print("is_cached:", enriched.is_cached, "| storageLevel:", enriched.storageLevel)
n1 = enriched.count()                                              # fills the cache
n2 = enriched.filter(F.col("status") == "SHIPPED").count()         # reads the cache
enriched.filter(F.col("status") == "SHIPPED").groupBy("city").count().explain()
enriched.unpersist()

from pyspark import StorageLevel
daily = orders.groupBy(F.to_date("order_ts").alias("order_date")).agg(F.sum("amount").alias("revenue"))
daily.persist(StorageLevel.DISK_ONLY)
print("storageLevel:", daily.storageLevel)
daily.persist(StorageLevel.MEMORY_ONLY)            # a second persist() with another level
print("storageLevel now:", daily.storageLevel)
```
```text
is_cached: True | storageLevel: Disk Memory Deserialized 1x Replicated
first action (computes and fills the cache): 400000 rows in 6.82 s
second action (reads the cache): 200000 rows in 1.60 s
== Physical Plan ==
AdaptiveSparkPlan isFinalPlan=false
+- HashAggregate(keys=[city#23], functions=[count(1)])
   +- Exchange hashpartitioning(city#23, 4), ENSURE_REQUIREMENTS, [plan_id=255]
      +- HashAggregate(keys=[city#23], functions=[partial_count(1)])
         +- Project [city#23]
            +- Filter (isnotnull(status#17) AND (status#17 = SHIPPED))
               +- InMemoryTableScan [city#23, status#17], [isnotnull(status#17), (status#17 = SHIPPED)]
                     +- InMemoryRelation [order_id#14, order_date#28, city#23, status#17, amount#18], StorageLevel(disk, memory, deserialized, 1 replicas)
                           +- AdaptiveSparkPlan isFinalPlan=true
                              ...  (the join that filled the cache)
storageLevel: Disk Serialized 1x Replicated
storageLevel now: Disk Serialized 1x Replicated
```

Four things to notice:

- Right after `cache()`, before any action, `is_cached` is already `True` and the level is set: `cache()` marks the DataFrame. The work happens in the first `count()`.
- The plan of a query built on the cached DataFrame reads **`InMemoryTableScan`** over an **`InMemoryRelation`**: no file scan, no join. That is how you confirm in `explain()` that a cache is used.
- The timings (6.82 s, then 1.60 s on a loaded two-core machine) only show the direction; real gains depend on how expensive the cached step was.
- The second `persist()` with another level was silently ignored. The PySpark docs say `persist` "can only be used to assign a new storage level if the DataFrame does not have a storage level set yet". Call `unpersist()` first.

SQL has the same tools; `CACHE TABLE` is eager unless you add `LAZY`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CACHE TABLE silver.customers_big;
UNCACHE TABLE silver.customers_big;
CACHE LAZY TABLE ca_customers OPTIONS ('storageLevel' 'DISK_ONLY')
  SELECT * FROM silver.customers_big WHERE country = 'CA';
SELECT count(*) AS ca_customers FROM ca_customers;
UNCACHE TABLE ca_customers;
```
```text
isCached: True
isCached after UNCACHE: False
isCached ca_customers: True
+------------+
|ca_customers|
+------------+
|         500|
+------------+
```

**When not to cache.**

- The data is used once. Caching costs a full computation plus memory or disk; it only pays back on reuse.
- The source is already fast to read. On Databricks, the "Optimize performance with caching" page recommends the automatic **disk cache** (formerly called the Delta cache) "instead of the Apache Spark cache for repeated reads of Parquet and Delta Lake data". The disk cache stores copies of remote Parquet files on the workers' local disks and detects file changes by itself.
- In production pipelines. The "Apache Spark on Databricks" page warns that "manually caching data or returning preview results in production pipelines can interrupt these optimizations and lead to increases in cost and latency." A cache can also go stale. In open-source Spark, a write made through the same Spark session refreshes the cache (in a small local check, `ch03_cache_probe.py`, a cached Parquet table and a cached Delta table both showed the new row after an `INSERT INTO`), but writes by other jobs or clusters are not detected, unlike the Databricks disk cache above.
- When you forget to release it. Cached blocks hold executor memory that joins and aggregations need; call `unpersist()`.

!!! note "Caching on Databricks serverless"
    The serverless limitations page says `df.cache()`, `df.persist()` and `df.unpersist()` are supported, but `spark.catalog.cacheTable()`, `uncacheTable()`, `clearCache()`, `CACHE TABLE` and `UNCACHE TABLE` are not and raise an exception. The DataFrame caching page (Public Preview) says that on serverless "Databricks computes the DataFrame when you call `cache()` and materializes the result as a snapshot", and that after `unpersist()` the DataFrame "and DataFrames built from it can no longer be used".

!!! tip "In the interview"
    **"cache() vs persist()?"** `cache()` is `persist()` with the default storage level, which for DataFrames is `MEMORY_AND_DISK_DESER` (RDDs default to `MEMORY_ONLY`). `persist()` lets you choose: memory only, memory and disk, disk only, replicated. Both are lazy in open-source Spark: the cache fills on the next action. Cache only data you reuse several times, check `InMemoryTableScan` in the plan, and `unpersist()` when done.

## 3.10 Actions that pull data to the driver
*Level: intermediate.*

**The problem.** A data engineer writes `rows = spark.table("shop.silver.orders").collect()` to "loop over the orders in Python". On a few thousand rows it works. On the full table the notebook hangs and the driver dies.

`collect()` returns "all the records in the DataFrame as a list of `Row`", and the PySpark docs warn that it "should only be used if the resulting list is expected to be small, as all the data is loaded into the driver's memory." `toPandas()` carries the same warning. The driver is one process; the Spark configuration page gives open-source defaults of `spark.driver.memory` = 1g and `spark.driver.maxResultSize` = 1g, the "limit of total size of serialized results of all partitions for each Spark action (e.g. collect)". If the results go over that limit, "jobs will be aborted"; if the limit is high, the driver itself can run out of memory. (Databricks sizes the driver from the node type you choose; [chapter 6](06-Compute.md).)

This session started with `spark.driver.maxResultSize=1m` (the smallest value the page allows) to show the failure on 400,000 orders:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
print("take(3):", orders.select("order_id", "amount").take(3))
print("first():", orders.select("order_id").first())
print(sorted(orders.groupBy("currency").agg(F.count("*").alias("n")).collect()))
rows = orders.collect()
pdf = orders.toPandas()
print(orders.groupBy("status").agg(F.count("*").alias("n")).orderBy("status").toPandas())
```
```text
take(3): [Row(order_id=100000, amount=Decimal('5.00')), Row(order_id=100001, amount=Decimal('5.01')), Row(order_id=100002, amount=Decimal('5.02'))]
first(): Row(order_id=100000)
[Row(currency='CAD', n=266666), Row(currency='USD', n=133334)]
collect() of all orders -> ERROR: org.apache.spark.SparkException: Job aborted due to stage failure: Total size of serialized results of 1 tasks (5.6 MiB) is bigger than spark.driver.maxResultSize (1024.0 KiB)
toPandas() of all orders -> ERROR: Caused by: org.apache.spark.SparkException: Job aborted due to stage failure: Total size of serialized results of 1 tasks (9.8 MiB) is bigger than spark.driver.maxResultSize (1024.0 KiB)
      status       n
0  CANCELLED  100000
1     PLACED  100000
2    SHIPPED  200000
```

`take`, `first`, `show` and `limit(n).collect()` bring back a bounded number of rows. A `collect()` or `toPandas()` after an aggregation is fine, because the result is small. The full-table `collect()` and `toPandas()` failed with the `maxResultSize` error; with a large limit they would have tried to fit everything into the driver's memory instead.

**What to do instead.** Keep the work in Spark: write the result to a table (`saveAsTable`, Delta), aggregate or filter before collecting, use `foreachBatch` or `foreachPartition` for side effects on executors, and use `display()`/`show()` (which fetch a limited number of rows) for looking at data.

!!! warning "Driver OOM is not only collect()"
    Other things that load data into the driver: `toPandas()`, broadcasting a large table (the driver collects the broadcast side first), Python loops over `collect()` results, and very large query plans (thousands of columns or a loop that keeps adding `withColumn`). On Databricks, "Debugging with the Spark UI" points to the driver's thread dump when "the driver appears to be hanging".

!!! tip "In the interview"
    **"Your job fails with an out-of-memory error on the driver. What do you check?"** First, what returns data to the driver: `collect()`, `toPandas()`, a broadcast of a big table, a huge `show()`. Replace them with writes to a table, aggregations before collecting, or `limit`. `spark.driver.maxResultSize` (1g by default in open-source Spark) caps the result size per action; raising it only moves the problem unless the driver also has the memory. If executors, not the driver, run out of memory, look at skew, too few shuffle partitions, large broadcasts and UDFs instead (section 3.14).

## 3.11 UDFs vs built-in functions
*Level: intermediate.*

**The problem.** The order-size band (small under 50, medium under 200, large otherwise) is easy in Python, so someone wraps it in a UDF (user-defined function). The job gets slower, and `explain()` shows a node nobody recognizes.

Built-in functions (`F.when`, `F.upper`, `F.to_date`, everything in `pyspark.sql.functions` and the SQL function reference) run inside the JVM engine: Catalyst can see what they do and optimize around them, and code generation compiles them into the stage. A **Python UDF** is a black box: Spark must ship rows from the JVM executor to a Python worker process, run your function, and ship the results back. The Databricks UDF page puts the rule directly: "Built-in Apache Spark functions are optimized for distributed processing and offer better performance at scale", and Databricks recommends Apache Spark methods for "operations on large datasets and any workloads that run regularly or continuously, including ETL jobs".

Three common kinds of scalar Python UDF in Spark 4.2:

| Kind | How data moves | Plan node in this run |
| --- | --- | --- |
| Pickled Python UDF (`udf(..., useArrow=False)`) | Rows pickled to Python, called one row at a time | `BatchEvalPython` |
| Arrow-optimized Python UDF (`udf(...)`; Arrow is the default "since Spark 4.2") | Rows sent in Apache Arrow batches, function still called per row | `ArrowEvalPython` |
| pandas UDF (`@pandas_udf`), "also known as vectorized UDF" | Arrow batches, function called once per batch with pandas Series | `ArrowEvalPython` |

The PySpark Arrow guide says: "Since Spark 4.2, Arrow optimization is enabled by default for regular Python UDFs", controlled by `spark.sql.execution.pythonUDF.arrow.enabled`. Whether a given Databricks Runtime version uses the same default is not verified here.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
import pandas as pd
from pyspark.sql.functions import udf, pandas_udf

def band_py(amount):
    if amount is None:
        return None
    return "small" if amount < 50 else ("medium" if amount < 200 else "large")

band_udf = udf(band_py, "string")                          # Arrow by default in Spark 4.2
band_udf_pickled = udf(band_py, "string", useArrow=False)  # classic pickled UDF

@pandas_udf("string")
def band_pandas(amount: pd.Series) -> pd.Series:
    a = amount.astype("float64")
    out = pd.Series("large", index=a.index)
    out[a < 200] = "medium"
    out[a < 50] = "small"
    out[a.isna()] = None
    return out

band_builtin = (F.when(F.col("amount").isNull(), None)
                .when(F.col("amount") < 50, "small")
                .when(F.col("amount") < 200, "medium")
                .otherwise("large"))

orders = gen_orders(spark, 100_000)
for col in [band_builtin, band_udf("amount"), band_udf_pickled("amount"), band_pandas("amount")]:
    orders.select("order_id", col.alias("band")).explain()
```
```text
== Physical Plan ==                                   (built-in)
*(1) Project [order_id#1, CASE WHEN isnull(amount#5) THEN null WHEN (amount#5 < 50.00) THEN small WHEN (amount#5 < 200.00) THEN medium ELSE large END AS band#10]
+- *(1) Project [...]
   +- *(1) Range (0, 100000, step=1, splits=2)

== Physical Plan ==                                   (Python UDF, Arrow)
*(2) Project [cast((id#0L + 100000) as int) AS order_id#1, pythonUDF0#12 AS band#11]
+- ArrowEvalPython [band_py(...)#7], [pythonUDF0#12], 101
   +- *(1) Range (0, 100000, step=1, splits=2)

== Physical Plan ==                                   (Python UDF, pickled)
*(2) Project [cast((id#0L + 100000) as int) AS order_id#1, pythonUDF0#14 AS band#13]
+- BatchEvalPython [band_py(...)#8], [pythonUDF0#14]
   +- *(1) Range (0, 100000, step=1, splits=2)

== Physical Plan ==                                   (pandas UDF)
*(2) Project [cast((id#0L + 100000) as int) AS order_id#1, pythonUDF0#16 AS band#15]
+- ArrowEvalPython [band_pandas(...)#9], [pythonUDF0#16], 200
   +- *(1) Range (0, 100000, step=1, splits=2)
```

The built-in version is one generated `CASE WHEN` inside the same `*(1)` stage; every UDF version adds a separate Python evaluation node that breaks the generated code into two pieces (`*(1)` and `*(2)`). All four give the same answer. A rough timing on 2,000,000 generated orders (local, two cores, a busy machine, second run of each):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
for name, col in versions.items():
    q = gen_orders(spark, 2_000_000).select(col.alias("band")).groupBy("band").count()
    q.collect()     # timed
```
```text
built-in when/otherwise    2.19 s
Python UDF (Arrow)         7.76 s
Python UDF (pickled)       7.25 s
pandas UDF                 4.88 s
```

Treat the numbers as a direction, not a benchmark: the built-in function was the fastest, the vectorized pandas UDF came next, and the two row-at-a-time UDFs were the slowest. A second run on the same busy machine gave 1.67 s, 4.64 s, 8.57 s and 3.82 s: the same order for the built-in and pandas versions, while the Arrow and pickled UDFs swapped places, so do not read anything into the gap between those two. The Databricks pandas UDF page claims vectorized operations "can increase performance up to 100x compared to row-at-a-time Python UDFs"; this small local run does not show anything near that, which is a good reminder to measure your own workload.

!!! warning "UDF traps"
    - **Return type.** `udf(f)` without a return type returns `StringType` (practice question 30).
    - **Nulls.** A Python UDF receives `None` for nulls and must handle it. The Databricks Python UDF page warns that a `WHERE x IS NOT NULL` clause "does not guarantee" the UDF is called only after nulls are filtered out; make the UDF null-aware.
    - **Memory and parallelism.** The Databricks Spark UI guide lists UDFs as a cause of executor memory problems ("each task that runs a UDF might load all the data in its partition into memory") and suggests `repartition()` before an expensive UDF when the stage has fewer tasks than cores.

!!! tip "In the interview"
    **"Why are Python UDFs slow, and what do you do about it?"** Each row (or Arrow batch) has to be serialized from the JVM to a Python worker and back, and the function is opaque to Catalyst, so no pushdown, no code generation through it. First choice: rewrite with built-in functions (`when`, `regexp_extract`, `transform`, and so on). If you need Python, use a pandas UDF, which processes Arrow batches with vectorized pandas code. In `explain()`, UDFs show up as `BatchEvalPython` or `ArrowEvalPython` nodes.

## 3.12 The DataFrame API side by side with SQL
*Level: beginner.*

Spark SQL and the DataFrame API are two front ends to the same engine. The Spark SQL guide says: "When computing a result, the same execution engine is used, independent of which API/language you are using to express the computation." Interviews ask for both, so here is a compact reference using the Red Rock Supply tables (registered as temp views with `createOrReplaceTempView`, so SQL can see them). Each pair below ran and returned the same rows (`ex07_api_sql.out`).

| Task | DataFrame API (PySpark) | SQL |
| --- | --- | --- |
| Pick columns | `orders.select("order_id", "amount")` | `SELECT order_id, amount FROM orders` |
| Filter | `orders.filter((F.col("status") == "SHIPPED") & (F.col("amount") > 100))` | `WHERE status = 'SHIPPED' AND amount > 100` |
| Derived column | `.withColumn("order_date", F.to_date("order_ts"))` | `to_date(order_ts) AS order_date` |
| CASE | `F.when(c >= 200, "large").when(c >= 50, "medium").otherwise("small")` | `CASE WHEN amount >= 200 THEN 'large' ... END` |
| Null default | `F.coalesce("status", F.lit("UNKNOWN"))` | `coalesce(status, 'UNKNOWN')` |
| Aggregate | `.groupBy("customer_id").agg(F.count("*").alias("n_orders"), F.sum("amount").alias("total"))` | `SELECT customer_id, count(*) AS n_orders, sum(amount) AS total ... GROUP BY customer_id` |
| HAVING | `.filter(F.col("n_orders") >= 2)` after the `agg` | `HAVING count(*) >= 2` |
| Sort | `.orderBy(F.col("total").desc())` | `ORDER BY total DESC` |
| Inner join | `orders.join(customers, "customer_id")` | `FROM orders o JOIN customers c ON o.customer_id = c.customer_id` |
| Anti join | `customers.join(cancelled, "customer_id", "left_anti")` | `WHERE NOT EXISTS (SELECT 1 ...)` or `LEFT ANTI JOIN` |
| Window | `F.sum("amount").over(Window.partitionBy("customer_id").orderBy("order_ts"))` | `sum(amount) OVER (PARTITION BY customer_id ORDER BY order_ts)` |
| Top 1 per group | `F.row_number().over(w)` then `.filter("rn = 1")` | `QUALIFY row_number() OVER (...) = 1` |
| SQL inside the API | `orders.selectExpr("amount * 100 AS cents")`, `F.expr("cents > 20000")` | |
| DataFrame to SQL and back | `df.createOrReplaceTempView("cad_orders")`, `spark.sql("SELECT ...")` returns a DataFrame | |

Two of the runs in full. Aggregation with HAVING:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
(orders.groupBy("customer_id")
       .agg(F.count("*").alias("n_orders"), F.sum("amount").alias("total"),
            F.round(F.avg("amount"), 2).alias("avg_amount"))
       .filter(F.col("n_orders") >= 2)
       .orderBy(F.col("total").desc())
       .show())
```
```sql
SELECT customer_id, count(*) AS n_orders, sum(amount) AS total,
       round(avg(amount), 2) AS avg_amount
FROM orders GROUP BY customer_id HAVING count(*) >= 2 ORDER BY total DESC;
```
```text
+-----------+--------+------+----------+
|customer_id|n_orders|total |avg_amount|
+-----------+--------+------+----------+
|1          |3       |327.40|109.13    |
|2          |2       |278.95|139.48    |
|3          |2       |198.00|99.00     |
+-----------+--------+------+----------+
same rows: True
```

Window functions: a running total per customer and a rank by amount:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
from pyspark.sql.window import Window
w_running = Window.partitionBy("customer_id").orderBy("order_ts").rowsBetween(Window.unboundedPreceding, 0)
w_rank = Window.partitionBy("customer_id").orderBy(F.col("amount").desc())
(orders.select("customer_id", "order_id", "amount",
               F.sum("amount").over(w_running).alias("running_total"),
               F.row_number().over(w_rank).alias("rn"))
       .orderBy("customer_id", "order_id").show())
```
```sql
SELECT customer_id, order_id, amount,
       sum(amount) OVER (PARTITION BY customer_id ORDER BY order_ts
                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
       row_number() OVER (PARTITION BY customer_id ORDER BY amount DESC) AS rn
FROM orders ORDER BY customer_id, order_id;
```
```text
+-----------+--------+------+-------------+---+
|customer_id|order_id|amount|running_total|rn |
+-----------+--------+------+-------------+---+
|1          |1001    |59.90 |59.90        |3  |
|1          |1003    |189.50|249.40       |1  |
|1          |1008    |78.00 |327.40       |2  |
|2          |1002    |249.00|249.00       |1  |
|2          |1006    |29.95 |278.95       |2  |
|3          |1004    |39.00 |39.00        |2  |
|3          |1007    |159.00|198.00       |1  |
|4          |1005    |318.00|318.00       |1  |
+-----------+--------+------+-------------+---+
same rows: True
```

Window functions themselves are taught in the SQL course ([window functions and ranking](../../databases/sql/13-Window-Functions-Ranking.md)); `QUALIFY` and other Databricks SQL extras are in [chapter 17](17-Databricks-SQL-vs-Standard.md).

**One engine, one plan.** The script compares the optimized logical plans of the DataFrame version and the SQL version of "customers whose total is above 100" (expression IDs removed):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
df_q = orders.groupBy("customer_id").agg(F.sum("amount").alias("total")).filter(F.col("total") > 100)
sql_q = spark.sql("SELECT customer_id, sum(amount) AS total FROM orders "
                  "GROUP BY customer_id HAVING sum(amount) > 100")
```
```text
Filter (isnotnull(total) AND (total > 100.00))
+- Aggregate [customer_id], [customer_id, sum(amount) AS total]
   +- Project [customer_id, amount]
      +- LogicalRDD [order_id, customer_id, order_ts, status, amount, currency], false
same optimized plan: True
```

So "is SQL faster than PySpark?" has a short answer: no, for the same logic they compile to the same plan. The exception is Python UDFs and RDD code, which leave the optimized engine.

!!! tip "In the interview"
    **"Is there a performance difference between Spark SQL and the DataFrame API?"** No. Both build the same logical plan, Catalyst optimizes it the same way, and the same physical operators run. Choose by readability and testability: SQL for set-based transformations analysts can read, the DataFrame API when you need functions, loops over columns, or unit tests. Python UDFs and RDD lambdas are what make PySpark slower, not the API itself.

## 3.13 Reading and writing files
*Level: beginner.*

Bronze layers read raw files; [chapter 8](08-Bronze-Ingestion.md) covers the Databricks ingestion tools (Auto Loader, `COPY INTO`, `read_files`). Underneath, they use the same Spark readers, with the same options and pitfalls.

**Schema inference vs explicit schema.** The CSV reader's defaults are `header` = false and `inferSchema` = false, and inference "requires one extra pass over the data" (Spark CSV page). Watch what each choice does with a Red Rock Supply file that has one bad amount (`N/A`):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
spark.read.csv(csv_dir).printSchema()                                   # no options
inf = spark.read.option("header", True).option("inferSchema", True).csv(csv_dir)
inf.printSchema()
inf.show()
schema = ("order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING, "
          "amount DECIMAL(10,2), currency STRING")
spark.read.option("header", True).schema(schema).csv(csv_dir).show()   # explicit, PERMISSIVE
```
```text
root
 |-- _c0: string (nullable = true)
 |-- _c1: string (nullable = true)
 |-- _c2: string (nullable = true)
 |-- _c3: string (nullable = true)
 |-- _c4: string (nullable = true)
 |-- _c5: string (nullable = true)

root
 |-- order_id: integer (nullable = true)
 |-- customer_id: integer (nullable = true)
 |-- order_ts: timestamp (nullable = true)
 |-- status: string (nullable = true)
 |-- amount: string (nullable = true)
 |-- currency: string (nullable = true)

+--------+-----------+-------------------+---------+------+--------+
|order_id|customer_id|           order_ts|   status|amount|currency|
+--------+-----------+-------------------+---------+------+--------+
|    1001|          1|2026-03-01 10:15:00|  SHIPPED| 59.90|     CAD|
|    1002|          2|2026-03-01 11:05:00|  SHIPPED|249.00|     USD|
|    1003|          1|2026-03-02 09:40:00|   PLACED|   N/A|     CAD|
|    1004|          3|2026-03-02 14:20:00|CANCELLED| 39.00|     USD|
+--------+-----------+-------------------+---------+------+--------+

+--------+-----------+-------------------+---------+------+--------+
|order_id|customer_id|           order_ts|   status|amount|currency|
+--------+-----------+-------------------+---------+------+--------+
|    1001|          1|2026-03-01 10:15:00|  SHIPPED| 59.90|     CAD|
|    1002|          2|2026-03-01 11:05:00|  SHIPPED|249.00|     USD|
|    1003|          1|2026-03-02 09:40:00|   PLACED|  NULL|     CAD|
|    1004|          3|2026-03-02 14:20:00|CANCELLED| 39.00|     USD|
+--------+-----------+-------------------+---------+------+--------+
```

Without options, the header became a data row and every column is `_c0` ... `_c5` strings. With inference, one bad value turned the whole `amount` column into a string. With an explicit schema, `amount` is `DECIMAL(10,2)` and the bad value became `NULL`, silently. Explicit schemas are faster (no inference pass) and stable (a new file cannot change your types), which is why production pipelines use them. The Databricks "Long Spark stage with one task" page also lists "schema inference on a large file" as a cause of slow stages.

**Parse modes** decide what happens to a malformed record. The CSV and JSON pages define three: `PERMISSIVE` (the default) "puts the malformed string into a field configured by `columnNameOfCorruptRecord`, and sets malformed fields to `null`", `DROPMALFORMED` "ignores the whole corrupted records", and `FAILFAST` "throws an exception when it meets corrupted records".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
(spark.read.option("header", True).schema(schema + ", _corrupt_record STRING")
 .csv(csv_dir).show(truncate=False))
spark.read.option("header", True).option("mode", "DROPMALFORMED").schema(schema).csv(csv_dir).show()
spark.read.option("header", True).option("mode", "FAILFAST").schema(schema).csv(csv_dir).show()
```
```text
+--------+-----------+-------------------+---------+------+--------+------------------------------------------+
|order_id|customer_id|order_ts           |status   |amount|currency|_corrupt_record                           |
+--------+-----------+-------------------+---------+------+--------+------------------------------------------+
|1001    |1          |2026-03-01 10:15:00|SHIPPED  |59.90 |CAD     |NULL                                      |
|1002    |2          |2026-03-01 11:05:00|SHIPPED  |249.00|USD     |NULL                                      |
|1003    |1          |2026-03-02 09:40:00|PLACED   |NULL  |CAD     |1003,1,2026-03-02T09:40:00Z,PLACED,N/A,CAD|
|1004    |3          |2026-03-02 14:20:00|CANCELLED|39.00 |USD     |NULL                                      |
+--------+-----------+-------------------+---------+------+--------+------------------------------------------+

+--------+-----------+-------------------+---------+------+--------+
|order_id|customer_id|           order_ts|   status|amount|currency|
+--------+-----------+-------------------+---------+------+--------+
|    1001|          1|2026-03-01 10:15:00|  SHIPPED| 59.90|     CAD|
|    1002|          2|2026-03-01 11:05:00|  SHIPPED|249.00|     USD|
|    1004|          3|2026-03-02 14:20:00|CANCELLED| 39.00|     USD|
+--------+-----------+-------------------+---------+------+--------+

ERROR: org.apache.spark.SparkException: [FAILED_READ_FILE.NO_HINT] Encountered error while reading file file:///.../orders_2026-03-01.csv.  SQLSTATE: KD001
cause: Caused by: org.apache.spark.SparkException: [MALFORMED_RECORD_IN_PARSING.WITHOUT_SUGGESTION] Malformed records are detected in record parsing: [1003,1,1772444400000000,PLACED,null,CAD].
```

`PERMISSIVE` with a `_corrupt_record` column is the basis of the quarantine pattern ([chapter 9](09-Building-Silver.md)): keep every row, and route rows with a non-null `_corrupt_record` to a quarantine table.

**JSON.** The Spark JSON reader expects JSON Lines by default: "Each line must contain a separate, self-contained valid JSON object" (use `multiLine` for one document spread over lines). Red Rock Supply's raw events have quoted amounts and a nested `items` array; one line is broken (a missing comma):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
ji = spark.read.json(json_dir)                       # inferred
ji.printSchema()
event_schema = """order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING,
                  amount DECIMAL(10,2), currency STRING,
                  items ARRAY<STRUCT<product_id: INT, qty: INT, unit_price: DECIMAL(10,2)>>"""
je = spark.read.schema(event_schema).option("mode", "DROPMALFORMED").json(json_dir)
(je.select("order_id", F.explode("items").alias("item"))
   .select("order_id", "item.product_id", "item.qty", "item.unit_price").show())
```
```text
root
 |-- _corrupt_record: string (nullable = true)
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

+--------+----------+---+----------+
|order_id|product_id|qty|unit_price|
+--------+----------+---+----------+
|    1001|         3|  2|     29.95|
|    1002|         1|  1|    249.00|
|    1005|         5|  2|    159.00|
+--------+----------+---+----------+
```

Inference made `amount` a string (it is quoted in the file), integers `long`, `order_ts` a string, sorted the columns alphabetically, and added `_corrupt_record` for the broken line. The explicit schema gives the types you want. Nested data and `explode` are covered in depth in [chapter 18](18-Semi-Structured-Data.md).

**Parquet** stores the schema in the file. The Spark Parquet page: reading and writing Parquet "automatically preserves the schema of the original data", though "all columns are automatically converted to be nullable for compatibility reasons". Parquet is also the default data source "unless otherwise configured by `spark.sql.sources.default`" (load/save page). Delta tables are Parquet files plus a transaction log ([chapter 4](04-Delta-Lake.md)), and on Databricks Delta is the default table format.

**Save modes** decide what a write does when the target exists. The Spark load/save page lists `errorifexists` (default), `append`, `overwrite` and `ignore`, and warns: "these save modes do not utilize any locking and are not atomic. Additionally, when performing an `Overwrite`, the data will be deleted before writing out the new data."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
good.write.parquet(out)                      # default mode
good.write.parquet(out)                      # again
good.write.mode("append").parquet(out)
good.write.mode("ignore").parquet(out)
good.write.mode("overwrite").parquet(out)
```
```text
first write, rows: 3
second write, default mode -> ERROR: [PATH_ALREADY_EXISTS] Path file:/.../silver_orders_parquet already exists. Set mode as "overwrite" to overwrite the existing path. SQLSTATE: 42K04
after append: 6
after ignore: 6
after overwrite: 3
```

Two scenario facts follow. A job that appends is **not idempotent**: rerun it after a partial failure and you get duplicates (here, 6 rows from 3). And a plain-Parquet overwrite deletes first, so a failure in the middle can leave the folder empty or half-written. Delta tables fix the second problem with atomic commits and give you `MERGE` and `INSERT ... REPLACE WHERE` for the first ([chapter 4](04-Delta-Lake.md), chapter 20).

**Files per write.** Each partition writes its own file (per folder, with `partitionBy`): the 1-partition DataFrame wrote 1 file, and after `repartition(3)` the same rows wrote 3 files.

!!! tip "In the interview"
    **"Should you infer schemas in production?"** No. Inference costs an extra pass over the data, can pick the wrong type from one bad value (one `N/A` turned `amount` into a string), and can change between runs as files change. Use an explicit schema (a DDL string or `StructType`), choose the parse mode deliberately (`PERMISSIVE` with a `_corrupt_record` column to quarantine, `FAILFAST` when bad data must stop the pipeline), and on Databricks let Auto Loader manage schema evolution with its rescued data column ([chapter 8](08-Bronze-Ingestion.md)).

## 3.14 The Spark UI, the query profile, and Spark Connect
*Level: expert.*

### The Spark UI

Every Spark application has a web UI; the Spark cluster overview page says it is "typically on port 4040" of the driver and "displays information about running tasks, executors, and storage usage". The Spark "Web UI" page describes its tabs:

| Tab | What you look for |
| --- | --- |
| **Jobs** | One row per job (per action, more with AQE); duration, failed jobs, the event timeline. Long gaps between jobs mean the driver was busy (Python code, planning, listing files). |
| **Stages** | Per stage: Input, Output, Shuffle Read, Shuffle Write, task count. The stage detail page has **Summary Metrics** (min, 25th percentile, median, 75th percentile, max of task duration, shuffle read size, spill) and the DAG of the stage. Skipped stages reuse earlier output. |
| **Storage** | Cached DataFrames and tables: storage level, fraction cached, size in memory and on disk. |
| **Environment** | The effective Spark configuration: check that `spark.sql.shuffle.partitions` and other settings are what you think. |
| **Executors** | Memory, disk, task counts, GC time per executor; links to logs and thread dumps. |
| **SQL / DataFrame** | One row per query with its plan visualization and per-operator metrics (`number of output rows`, `data size`, `shuffle bytes written`, spill, time). With AQE you see the plan change as stages finish. |

The metrics map directly onto the problems in this chapter: **Shuffle Read/Write** (how much moved), "Shuffle spill (memory)" and "Shuffle spill (disk)" (not enough execution memory), task-duration spread in Summary Metrics (skew), and the task count of a stage (parallelism).

**On Databricks** (Databricks only), you open it from the compute page: select your compute, then the **Spark UI** tab. The Databricks guide "Diagnose cost and performance issues using the Spark UI" (last updated Oct 12, 2026) gives an order of steps:

1. Start with the **jobs timeline**: failing jobs, long gaps between jobs, or many small jobs each have their own page.
2. **Find the longest stage** in the longest job and note its Input, Output, Shuffle Read, Shuffle Write and task count. A single task "means the stage runs with no parallelism".
3. **Look for skew or spill** on the stage page: spill statistics at the top; skew if the Max task duration exceeds the 75th percentile by 50% or more.
4. Check whether the stage is **I/O bound**.
5. Look for **other causes**: reading or writing many small files ("files should be at least 8 MB"), slow UDFs, Cartesian joins, exploding joins.

The guide's fixes for each pattern, in short: for spill, `spark.sql.shuffle.partitions=auto`, fewer rows or columns held in memory, or instances with more memory; for skew, AQE skew handling, its thresholds, salting, liquid clustering of the source, or the `REBALANCE` hint for writes; for a one-task stage, remove `repartition(1)`/`coalesce(1)`, add `PARTITION BY` to a window, avoid unsplittable files such as gzip, specify schemas, and use `multiLine` only when needed.

### The query profile (Databricks only)

For SQL that runs on a SQL warehouse (and serverless compute), Databricks shows a **query profile** instead of making you read the Spark UI. The "Query profile" page (last updated Sep 11, 2026): you open it from **Query History**, click a query, then **See query profile**. It shows a DAG of operators with **Time spent**, **Memory peak** and **Rows** per operator, a **Top operators** panel with the most expensive operators, and the summary metrics (wall-clock duration broken into scheduling, optimization and file pruning, and execution; aggregated task time; I/O). The page lists the common operators as Scan, Join, Union, Shuffle ("expensive with regard to resources because they move data between executors"), Hash/Sort (aggregation) and Filter, and says the profile helps you find "exploding joins or full table scans". Databricks may also show **performance insights** for a query. A query answered from the query cache has no profile. To see a profile you must own the query or have at least CAN MONITOR on the warehouse. [Chapter 22](22-Performance-Tuning.md) reads a query profile in depth.

### Spark Connect and Databricks Connect

**Spark Connect**, introduced in Apache Spark 3.4, splits Spark into a thin client and a server. The Spark Connect overview: the client "translates DataFrame operations into unresolved logical query plans which are encoded using protocol buffers", sends them over gRPC, and results come back "as Apache Arrow-encoded row batches". Consequences listed on that page: the client "does not run in the same process as the Spark driver", the protocol "does not support all the execution APIs of Spark, most importantly RDDs", and the client "does not have access to the static Spark configuration or the SparkContext".

**On Databricks**, the "Compare Spark Connect to Spark Classic" page (last updated Sep 11, 2026) says Spark Connect is used in Scala notebooks on Databricks Runtime 13.3 and above and Python notebooks on Databricks Runtime 14.3 and above, both on standard compute (standard access mode, formerly called shared access mode, per the Unity Catalog best practices page); in serverless compute; in Databricks Connect; and in Lakeflow pipelines with environment versions configured. The differences it lists matter in interviews:

| Aspect | Spark Classic | Spark Connect |
| --- | --- | --- |
| Query execution | Lazy | Lazy |
| Schema analysis | Eager (a bad column fails when the DataFrame is built) | Lazy (it fails at the next action or schema access, such as `df.columns`) |
| Temporary views | the view's plan is embedded in the DataFrame | looked up by name at execution, so replacing a view changes DataFrames built on it |
| UDF serialization | at creation | at execution (a UDF captures variable values as they are when the action runs) |

The page's advice: use unique temp view names, wrap UDF definitions in a function to capture values early, and avoid calling `df.columns` or `df.schema` in loops (each access is a round trip to the server).

**Databricks Connect** is "a client library for the Databricks Runtime" that lets you run Spark code from an IDE or application on Databricks compute. Its page says "Databricks Connect is built on open-source Spark Connect", and for Databricks Runtime 13.3 LTS and above it "is an extension of Spark Connect with additions and modifications to support working with Databricks compute modes and Unity Catalog". General Python code runs locally; DataFrame operations and UDFs run on Databricks compute; results come back on `collect()`, `show()` or `toPandas()`. Chapter 16 uses it for testing.

*Databricks only, not run here. Syntax from [Tutorial: Run Python code on serverless compute](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/python/tutorial-serverless).*
```python
from databricks.connect import DatabricksSession

spark = DatabricksSession.builder.serverless().profile("<profile-name>").getOrCreate()
df = spark.read.table("samples.nyctaxi.trips")
df.show(5)
```

!!! tip "In the interview"
    **"A job got slower. How do you find out why?"** Open the Spark UI (or the query profile for SQL warehouse queries). In the jobs timeline find the longest job, then its longest stage, and read its Input, Shuffle Read/Write and task count. One task means no parallelism (`coalesce(1)`, a window without `PARTITION BY`, a gzip file). Many tasks with Max far above the 75th percentile means skew. Spill means not enough memory per task (too few shuffle partitions, too-big partitions). Then check the SQL tab's plan for a sort-merge join that should be a broadcast, a `BroadcastNestedLoopJoin`, a Python UDF node, or a scan reading far more files than expected.

## 3.15 Practice questions
*Level: mixed.*

**Q1. In a Databricks notebook you run `big = spark.table("shop.silver.orders").filter(F.col("amount") > 100)` followed by `print(big.count())`. Which parts run on the driver and which on the executors?**

??? success "Answer"
    The Python cell, building the DataFrame, analysis, Catalyst optimization, physical planning and scheduling run on the **driver**. The `count()` action makes the driver split the plan into stages and send one task per partition to the **executors**, which read the files, evaluate `amount > 100` and count rows per partition. The partial counts come back to the driver (through a small shuffle and final aggregation), and the driver prints the number.

    **Why:** the driver plans and schedules; executors process partitions. Only results of actions travel back to the driver.

**Q2. Classify each as a transformation or an action: `filter`, `groupBy().agg()`, `count()`, `show()`, `write.saveAsTable()`, `join`, `collect()`, `withColumn`, `take(5)`, `cache()`.**

??? success "Answer"
    Transformations: `filter`, `groupBy().agg()`, `join`, `withColumn`. Actions: `count()`, `show()`, `write.saveAsTable()`, `collect()`, `take(5)`.

    `cache()` is the tricky one. In open-source Spark it only marks the DataFrame; the cache is filled by the next action (the run in section 3.9 shows `is_cached: True` before any action). The Databricks "Apache Spark on Databricks" page lists "manual caching" among actions, and on serverless compute the caching page says Databricks computes the DataFrame when you call `cache()`. Say which platform you mean.

**Q3. This code runs without error, but the next line fails. Why does the error appear only at `show()`?**

```python
bad = orders.withColumn("currency_num", F.col("currency").cast("int"))
bad.show()
```

??? success "Answer"
    `withColumn` is a lazy transformation: Spark only checks that `currency` exists and that a cast to `int` is allowed for strings. The values are only read when an action runs, and with ANSI mode on (the Spark 4 default) casting `'CAD'` to `INT` raises `[CAST_INVALID_INPUT]` at that moment (section 3.4). Fix: `try_cast` (returns `NULL`) or clean the data first.

    **Why:** analysis errors (unknown column, wrong type for a function) appear when the DataFrame is built in Spark Classic; data errors appear when an action reads the data.

**Q4. On Databricks serverless compute, `df2 = df.select("order_total")` (a column that does not exist) does not raise an error. On a classic dedicated cluster it does. Why?**

??? success "Answer"
    Serverless compute runs Spark Connect. The "Compare Spark Connect to Spark Classic" page says Spark Connect defers analysis: the client only builds an unresolved plan, and the error appears when something needs the resolved plan, such as an action or a schema access (`df2.columns`, `df2.show()`). Spark Classic analyzes eagerly, so the `select` fails immediately (the local run in section 3.4 shows `UNRESOLVED_COLUMN.WITH_SUGGESTION` at the transformation).

**Q5. What does this `explain()` tell you, and how could the query be faster if `customers_big` is small?**

```text
*(5) Project [order_id#14, amount#18, city#23]
+- *(5) SortMergeJoin [customer_id#15], [customer_id#20], Inner
   :- *(2) Sort [customer_id#15 ASC NULLS FIRST], false, 0
   :  +- Exchange hashpartitioning(customer_id#15, 4), ENSURE_REQUIREMENTS, [plan_id=153]
   :     +- ... FileScan parquet spark_catalog.silver.orders_big[...]
   +- *(4) Sort [customer_id#20 ASC NULLS FIRST], false, 0
      +- Exchange hashpartitioning(customer_id#20, 4), ENSURE_REQUIREMENTS, [plan_id=162]
         +- ... FileScan parquet spark_catalog.silver.customers_big[...]
```

??? success "Answer"
    It is a sort-merge join: both tables are shuffled by `customer_id` into 4 partitions (two `Exchange` nodes), sorted, and merged. There is no `AdaptiveSparkPlan` at the top, so AQE is off and cannot switch it at run time. The job has 3 stages: one map stage per side, then the join stage.

    If `customers_big` is small, a broadcast hash join removes both shuffles of the big side: `orders.join(F.broadcast(cust), "customer_id")` or `/*+ BROADCAST(c) */`, or raise `spark.sql.autoBroadcastJoinThreshold` (it was `-1` in this run, which disables automatic broadcasts). Verify with `explain()`: `BroadcastHashJoin` with a `BroadcastExchange`.

**Q6. With AQE off and broadcasts disabled, how many stages does this create, and why not four?**

```python
big.join(cust, "customer_id").groupBy("customer_id").agg(F.sum("amount"))
```

??? success "Answer"
    Three stages (the run in section 3.5: 2 + 2 + 4 tasks). Each side of the sort-merge join is shuffled by `customer_id` (two map stages); the join and the aggregation then run in one stage, because the data is already hash-partitioned by `customer_id`, which is exactly what the `groupBy("customer_id")` needs. The plan has no `Exchange` above the `SortMergeJoin`.

**Q7. Same setup, but grouping by `city` instead. How many stages and tasks with 2 input partitions per table and `spark.sql.shuffle.partitions = 4`?**

??? success "Answer"
    Four stages and 12 tasks: 2 (scan orders) + 2 (scan customers) + 4 (join, partial aggregate by city) + 4 (final aggregate by city). Grouping by a different key than the join key needs a third shuffle, `Exchange hashpartitioning(city, 4)`. The run in section 3.5 printed `jobs=1 stages run=4 tasks=12`.

**Q8. A table is read as 8 input partitions. With AQE off and the default `spark.sql.shuffle.partitions`, how many tasks does `df.groupBy("customer_id").count().collect()` run, in how many stages?**

??? success "Answer"
    2 stages and 208 tasks: 8 map tasks (one per input partition) and 200 reduce tasks (the default shuffle partitions is 200). Most of those 200 tasks may process almost nothing on a small table, which is why AQE's partition coalescing exists: in the AQE run in section 3.8 the 200 planned partitions were read as 1 (`AQEShuffleRead coalesced`).

**Q9. After a query ran, its plan shows `AdaptiveSparkPlan isFinalPlan=true`, `AQEShuffleRead coalesced` and, under it, `Exchange hashpartitioning(customer_id, 200)`. What happened?**

??? success "Answer"
    AQE was on. The shuffle was planned with 200 partitions, but after the map stage ran, AQE saw the real shuffle sizes and merged contiguous small partitions into fewer, larger ones ("coalesced"), so the reduce stage ran fewer tasks than 200 (1 task in the section 3.8 run). `isFinalPlan=true` means the query finished and this is the plan that actually ran; `explain()` before the action shows `isFinalPlan=false` and the initial plan.

**Q10. You need one CSV file for a partner. What is the difference between `df.coalesce(1).write.csv(...)` and `df.repartition(1).write.csv(...)`?**

??? success "Answer"
    Both write one file. `coalesce(1)` is narrow (no shuffle), so Spark can collapse the work before it into the same single task: the whole computation may run on one core. `repartition(1)` adds a shuffle, so the upstream work still runs in parallel and only the final write is one task. The PySpark `coalesce` docs describe exactly this and suggest `repartition()` for a drastic reduction. For big data, prefer writing many files, or make sure the upstream work is cheap.

**Q11. What does this print?**

```python
print(orders.repartition(10).coalesce(20).rdd.getNumPartitions())
```

??? success "Answer"
    `10`. `coalesce` can only reduce the number of partitions; asking for more "will stay at the current number of partitions" (PySpark docs). The run in `ex09_practice.out` printed `10`. Use `repartition(20)` to increase.

**Q12. With `spark.sql.shuffle.partitions = 4` and AQE off, `orders.repartition("currency")` has 4 partitions but only 2 contain rows. Why, and why can this be a problem?**

??? success "Answer"
    Repartitioning by a column hashes each value to one partition, and there are only two currencies (CAD and USD), so only two partitions get rows; in the run they held 33,334 and 66,666 rows. The other partitions are empty tasks, and the two full ones are uneven (two thirds of orders are CAD). Repartitioning by a low-cardinality or skewed column limits parallelism to the number of distinct values and creates skew. Choose a higher-cardinality key, or add a salt.

**Q13. What is the default of `spark.sql.shuffle.partitions`, and why can it be wrong in both directions? What does Databricks offer?**

??? success "Answer"
    200 (Spark configuration page; the local run printed `200` after `unset`). For a small job, 200 partitions means 200 tiny tasks with more scheduling overhead than work. For terabytes, 200 partitions means each partition is very large, which causes spill and slow tasks. AQE coalescing (on by default) fixes the "too many" case at run time. On Databricks you can also set it to `auto` ("auto-optimized shuffle, which sets this number based on the query plan and the query input data size", Databricks AQE page), which the Databricks Spark UI guide recommends for spill.

**Q14. What does `PartitionFilters` vs `PushedFilters` vs `DataFilters` mean in a `FileScan` line?**

??? success "Answer"
    `PartitionFilters` are conditions on partition columns (folder names like `order_date=2026-03-02`): Spark lists only the matching folders, which is partition pruning. `PushedFilters` are conditions handed to the file reader, for example Parquet, which can skip row groups using their min/max statistics. `DataFilters` are the conditions on data columns as Spark sees them; the ones the source can use appear in `PushedFilters`, and Spark still applies the full condition in a `Filter` node above the scan. In section 3.6, `order_date = 2026-03-02` was a partition filter and `currency = CAD` a pushed filter.

**Q15. Find the bug. The orders were written with `partitionBy("order_date")`. This query reads every folder. Why?**

```python
od = spark.read.parquet(by_date)
od.filter((F.col("order_ts") >= "2026-03-02") & (F.col("order_ts") < "2026-03-03")).count()
```

??? success "Answer"
    The filter is on `order_ts`, a data column, not on the partition column `order_date`. Spark cannot know which folders hold which timestamps, so it lists all of them. The run printed `PartitionFilters: []` for this query and `PartitionFilters: [isnotnull(order_date), (order_date = 2026-03-02)]` for `filter(F.col("order_date") == "2026-03-02")`, both returning 2 rows. Fix: filter on the partition column (you can keep the timestamp filter too). The same rule applies to Delta tables partitioned by a date column.

**Q16. Name the join strategies Spark can choose for an equi-join and when each is used.**

??? success "Answer"
    - **Broadcast hash join**: one side's estimated size is under `spark.sql.autoBroadcastJoinThreshold` (10 MB default), or it has a `BROADCAST` hint. No shuffle of the big side.
    - **Sort-merge join**: the usual choice for two large tables; both sides shuffled and sorted.
    - **Shuffle hash join**: both sides shuffled, a hash table built per partition of the smaller side; chosen with a `SHUFFLE_HASH` hint or when conditions favor it (for example AQE when all post-shuffle partitions are small enough and `spark.sql.adaptive.maxShuffledHashJoinLocalMapThreshold` allows).
    - Non-equi conditions use a **broadcast nested loop join** (or a cartesian product), which compares every pair and is slow.

**Q17. Write PySpark that joins `order_items` to `products` as a broadcast join even when automatic broadcasting is turned off, and show how you verify it.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```python
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
    p7 = items.join(F.broadcast(products), "product_id")
    p7.explain()
    ```
    ```text
    == Physical Plan ==
    *(2) Project [product_id#17, order_id#16, qty#18, unit_price#19, name#7, category#8, price#9]
    +- *(2) BroadcastHashJoin [product_id#17], [product_id#6], Inner, BuildRight, false, false
       :- *(2) Filter isnotnull(product_id#17)
       :  +- *(2) Scan ExistingRDD[order_id#16,product_id#17,qty#18,unit_price#19]
       +- BroadcastExchange HashedRelationBroadcastMode(List(cast(input[0, int, false] as bigint)),false), [plan_id=492]
          +- *(1) Filter isnotnull(product_id#6)
             +- *(1) Scan ExistingRDD[product_id#6,name#7,category#8,price#9]
    ```
    `BroadcastHashJoin ... BuildRight` and `BroadcastExchange` on the products side confirm it. The SQL form is `SELECT /*+ BROADCAST(p) */ ... FROM order_items i JOIN products p ON i.product_id = p.product_id`.

**Q18. A colleague adds `/*+ BROADCAST(o) */` on a 40 GB orders table "to avoid the shuffle". What can go wrong?**

??? success "Answer"
    The hint is honored even above the threshold, so Spark tries to collect 40 GB and copy it to every executor. That can exhaust driver and executor memory or exceed `spark.sql.broadcastTimeout` (300 s by default). The Databricks "Spark memory issues" page lists "a large broadcast" as a common cause and says to check for broadcast hints on large tables. Broadcast the small side (usually the dimension), never the fact table.

**Q19. On Databricks, a customers table is well below `spark.databricks.adaptive.autoBroadcastJoinThreshold`, but AQE does not broadcast it in `orders LEFT OUTER JOIN customers`... and in `customers LEFT OUTER JOIN orders` it is not broadcast either. Explain both.**

??? success "Answer"
    The Databricks AQE FAQ says "some join types can't broadcast one side. For example, AQE can't broadcast the left side of a `LEFT OUTER JOIN`." In `orders LEFT OUTER JOIN customers`, customers is the right side and can be broadcast, so if it is not, check the other cause on the page: AQE does not switch if the percentage of non-empty partitions is below `spark.sql.adaptive.nonEmptyPartitionRatioForBroadcastJoin`; also remember AQE only switches after the shuffle. In `customers LEFT OUTER JOIN orders`, customers is the left side, which a left outer join cannot broadcast (all left rows must be kept, including unmatched ones). Rewrite the join order if the semantics allow, or accept a shuffle join.

**Q20. Why is this job slow? A join stage has 200 tasks; 199 finish in about 5 seconds and one runs for 20 minutes.**

??? success "Answer"
    Data skew: one join key (or a few) has far more rows than the others, so one shuffle partition is huge. Confirm on the stage page: Summary Metrics Max duration far above the 75th percentile (the Databricks guide uses "50% or more"), and much larger Shuffle Read for that task. Fixes: make sure AQE skew join handling is on (default) and that the partition passes both thresholds (factor 5 x median and 256 MB by default; lower them if needed); filter out junk keys such as `NULL` or `-1` before the join if they are not needed; broadcast the other side if it is small (broadcast joins have no shuffle skew); salt the key; for a skewed source table, liquid clustering.

**Q21. In a final plan you see `SortMergeJoin(skew=true)` and `AQEShuffleRead skewed`, and the join stage ran 9 tasks with 8 shuffle partitions. Explain.**

??? success "Answer"
    AQE detected a skewed partition on one side of the sort-merge join after the shuffle and split it into two smaller pieces, replicating the matching partition of the other side for each piece. That turned 8 partitions into 9 tasks. `AQEShuffleRead skewed` is the reader that serves the split pieces. This is the section 3.8 run, where 60% of orders belonged to customer 7.

**Q22. What are the default thresholds for AQE skew detection, and which joins can AQE de-skew?**

??? success "Answer"
    A partition is skewed only if it is larger than `spark.sql.adaptive.skewJoin.skewedPartitionFactor` (default 5) times the median partition size **and** larger than `spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes` (default 256 MB). AQE handles skew only in shuffle-based joins (sort-merge and, per the Databricks page, shuffle hash joins), never in broadcast joins, and the join type limits the side: both sides for `INNER`, only the left for `LEFT OUTER`/`LEFT SEMI`/`LEFT ANTI`, only the right for `RIGHT OUTER`, neither for `FULL OUTER` (Databricks AQE page).

**Q23. Why can a skewed `groupBy("customer_id").sum("amount")` be less of a problem than a skewed join on the same key?**

??? success "Answer"
    `sum` can be partially aggregated before the shuffle: the plans in this chapter show `partial_sum` in the map stage, so each map task sends one row per customer per partition, not every order. The hot key's reduce task receives a few partial sums, not millions of rows. A join cannot pre-combine rows, so all rows of the hot key go to one task. Aggregations that cannot be combined early (for example `collect_list`) and window functions over a hot partition key still suffer from skew.

**Q24. Why is this job slow? The longest stage has exactly one task while the cluster has 64 cores.**

??? success "Answer"
    The stage has no parallelism. Common causes from the Databricks "Long Spark stage with one task" page: `repartition(1)` or `coalesce(1)`; a window function without `PARTITION BY` (one task sees every row); an unsplittable file such as a large gzip file; the `multiLine` option on JSON/CSV; schema inference on a large file; an expensive UDF on small data that landed in one partition. Fix the cause (add `PARTITION BY`, remove the coalesce, ingest gzip files once into Delta, give a schema, `repartition()` before the UDF). Adding workers does not help a one-task stage.

**Q25. Write a two-step salted aggregation of order count and revenue per customer for a skewed `customer_id`, and check that it matches the plain aggregation.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```python
    sk = gen_orders(spark, 200_000, skew_customer=7, skew_share=0.6)
    step1 = (sk.withColumn("salt", (F.rand(3) * 16).cast("int"))
             .groupBy("customer_id", "salt").agg(F.count("*").alias("n"), F.sum("amount").alias("s")))
    step2 = step1.groupBy("customer_id").agg(F.sum("n").alias("orders"), F.sum("s").alias("revenue"))
    check = sk.groupBy("customer_id").agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue"))
    print("customer 7:", step2.filter("customer_id = 7").collect())
    print("matches the plain groupBy:", sorted(step2.collect()) == sorted(check.collect()))
    ```
    ```text
    customer 7: [Row(customer_id=7, orders=120356, revenue=Decimal('18044171.03'))]
    matches the plain groupBy: True
    ```
    Step 1 spreads the hot key over up to 16 groups (and so up to 16 tasks); step 2 adds the partial results. This works for sums and counts; for averages, carry sum and count and divide at the end.

**Q26. Why is this job slow? The stage page shows a large "Shuffle spill (disk)".**

??? success "Answer"
    Spill means tasks ran out of execution memory for a shuffle, join, sort or aggregation and wrote data to disk, which is slow. Usual causes: too few shuffle partitions for the data volume (each partition too big), skew, wide rows, too little memory per core. Fixes from the Databricks "Skew and spill" page: `spark.sql.shuffle.partitions=auto` on Databricks (or more shuffle partitions), reduce the rows and columns held in memory (filter and select before the shuffle), use instances with more memory, and limit streaming batch sizes.

**Q27. What does this print, before any action has run?**

```python
c = orders.filter("currency = 'CAD'")
print(c.storageLevel)
c.cache()
print(c.storageLevel, c.is_cached)
```

??? success "Answer"
    ```text
    Serialized 1x Replicated
    Disk Memory Deserialized 1x Replicated True
    ```
    (from `ex09_practice.out`). Before `cache()` the DataFrame has no storage level. `cache()` immediately sets the default DataFrame level, `MEMORY_AND_DISK_DESER` ("Disk Memory Deserialized"), and `is_cached` becomes `True`, but no data is cached yet: that happens at the first action.

**Q28. When should you not cache a DataFrame?**

??? success "Answer"
    When it is used only once (the cache costs a full computation plus storage); when the source is a Parquet or Delta table that is cheap to re-read (on Databricks the automatic disk cache already speeds up repeated reads, and Databricks recommends it over the Spark cache for that); in production pipelines, where the Databricks page warns that manual caching "can interrupt these optimizations"; when the data must reflect new writes from other jobs or clusters (the Spark cache does not detect them); and when memory is tight, because cached blocks compete with execution memory. If you do cache, `unpersist()` when done. On serverless compute, `CACHE TABLE` and `spark.catalog.cacheTable()` are not supported at all.

**Q29. A pipeline does `rows = spark.table("shop.silver.orders").collect()` and then loops in Python to compute daily totals. It crashes the driver. Explain and rewrite.**

??? success "Answer"
    `collect()` brings every row to the driver, one process with limited memory; results above `spark.driver.maxResultSize` (1g by default in Spark) abort the job (the run in section 3.10 failed with "Total size of serialized results ... is bigger than spark.driver.maxResultSize"), and below it the driver can still run out of memory. The loop also runs on one core. Keep the work in Spark:

    ```python
    daily = (spark.table("shop.silver.orders")
             .groupBy(F.to_date("order_ts").alias("order_date"))
             .agg(F.sum("amount").alias("revenue")))
    daily.write.mode("overwrite").saveAsTable("shop.gold.daily_revenue")
    ```
    *Databricks only, not run here. Syntax from [PySpark basics](https://docs.databricks.com/aws/en/pyspark/basics).* It uses Unity Catalog three-level names; the same groupBy-then-write pattern runs locally in practice question 37.

**Q30. What is the column type of `double_amount`, and what does the first row show?**

```python
double_it = udf(lambda a: float(a) * 2)
orders.select("order_id", double_it("amount").alias("double_amount")).show(2)
```

??? success "Answer"
    ```text
    root
     |-- order_id: integer (nullable = true)
     |-- double_amount: string (nullable = true)

    +--------+-------------+
    |order_id|double_amount|
    +--------+-------------+
    |    1001|        119.8|
    |    1002|        498.0|
    +--------+-------------+
    ```
    A `udf` without `returnType` defaults to `StringType` (PySpark `udf` docs), so the doubled amount comes back as the string `"119.8"`. Declare the type, `udf(f, "double")`, or better, use a built-in expression: `F.col("amount") * 2`, which also keeps the decimal type.

**Q31. Rewrite this UDF with built-in functions and explain what changes in the plan.**

```python
@udf("string")
def band(amount):
    return "small" if amount < 50 else ("medium" if amount < 200 else "large")
```

??? success "Answer"
    ```python
    band_builtin = (F.when(F.col("amount").isNull(), None)
                    .when(F.col("amount") < 50, "small")
                    .when(F.col("amount") < 200, "medium")
                    .otherwise("large"))
    ```
    The UDF plan has an `ArrowEvalPython` (or `BatchEvalPython`) node, a Python worker, and the generated code is split around it. The built-in plan is a single `CASE WHEN` inside the same code-generated `Project` (section 3.11). The original UDF also crashes on `None` (`None < 50` raises a `TypeError` in Python); the built-in version handles nulls. In the section 3.11 timing, the built-in version took 2.19 s against 7 to 8 s for the Python UDFs.

**Q32. What is a pandas UDF and why is it usually faster than a regular Python UDF?**

??? success "Answer"
    A pandas UDF (vectorized UDF) receives whole batches of rows as pandas Series, transferred with Apache Arrow, and returns a Series. The function is called once per batch, so Python's per-row call overhead disappears and pandas/NumPy run vectorized code. The Databricks pandas UDF page says it "can increase performance up to 100x compared to row-at-a-time Python UDFs". It still pays the JVM-to-Python transfer, so a built-in function is better when one exists. Since Spark 4.2 regular Python UDFs also use Arrow for transfer by default, but they still call your function row by row.

**Q33. Write PySpark and SQL for: revenue per city from SHIPPED orders, top 2 cities.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```python
    (orders.filter(F.col("status") == "SHIPPED")
     .join(customers, "customer_id")
     .groupBy("city").agg(F.sum("amount").alias("revenue"))
     .orderBy(F.col("revenue").desc())
     .limit(2)
     .show())
    ```
    ```sql
    SELECT c.city, sum(o.amount) AS revenue
    FROM orders o JOIN customers c USING (customer_id)
    WHERE o.status = 'SHIPPED'
    GROUP BY c.city ORDER BY revenue DESC LIMIT 2;
    ```
    ```text
    +---------+-------+
    |     city|revenue|
    +---------+-------+
    |Vancouver| 318.00|
    |   Denver| 249.00|
    +---------+-------+
    ```
    Both returned the same rows. Filtering before the join is good practice, though Catalyst would push the filter below the join anyway.

**Q34. Write PySpark that keeps only the latest order per customer (ties broken by the higher `order_id`).**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```python
    from pyspark.sql.window import Window
    w = Window.partitionBy("customer_id").orderBy(F.col("order_ts").desc(), F.col("order_id").desc())
    latest = (orders.withColumn("rn", F.row_number().over(w))
              .filter("rn = 1").drop("rn")
              .select("customer_id", "order_id", "order_ts", "status"))
    latest.orderBy("customer_id").show()
    ```
    ```text
    +-----------+--------+-------------------+-------+
    |customer_id|order_id|           order_ts| status|
    +-----------+--------+-------------------+-------+
    |          1|    1008|2026-03-04 19:10:00|   NULL|
    |          2|    1006|2026-03-03 17:30:00| PLACED|
    |          3|    1007|2026-03-04 12:00:00|SHIPPED|
    |          4|    1005|2026-03-03 08:55:00|SHIPPED|
    +-----------+--------+-------------------+-------+
    ```
    `row_number` (not `rank`) guarantees exactly one row per customer. In Databricks SQL the same is `QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY order_ts DESC, order_id DESC) = 1` ([chapter 17](17-Databricks-SQL-vs-Standard.md)). The window needs a shuffle by `customer_id`.

**Q35. Raw order events arrive as JSON lines with a nested `items` array and quoted decimals. Read them with an explicit schema and produce one row per item with a line total; check that line totals add up to the order amount.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```python
    event_schema = """order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING,
                      amount DECIMAL(10,2), currency STRING,
                      items ARRAY<STRUCT<product_id: INT, qty: INT, unit_price: DECIMAL(10,2)>>"""
    ev = spark.read.schema(event_schema).json(events_dir)
    lines = (ev.select("order_id", F.explode("items").alias("i"))
             .select("order_id", "i.product_id", "i.qty", "i.unit_price",
                     (F.col("i.qty") * F.col("i.unit_price")).alias("line_total")))
    lines.show()
    (lines.groupBy("order_id").agg(F.sum("line_total").alias("items_total"))
     .join(ev.select("order_id", "amount"), "order_id").show())
    ```
    ```text
    +--------+----------+---+----------+----------+
    |order_id|product_id|qty|unit_price|line_total|
    +--------+----------+---+----------+----------+
    |    1001|         3|  2|     29.95|     59.90|
    |    1009|         1|  1|    249.00|    249.00|
    |    1009|         4|  1|     39.00|     39.00|
    +--------+----------+---+----------+----------+

    +--------+-----------+------+
    |order_id|items_total|amount|
    +--------+-----------+------+
    |    1001|      59.90| 59.90|
    |    1009|     288.00|288.00|
    +--------+-----------+------+
    ```
    The explicit schema turns the quoted `"59.90"` into `DECIMAL(10,2)` directly (inference would keep it a string). `explode` makes one row per array element.

**Q36. Write PySpark for each order's share (in percent) of its customer's total spending. Why is there no `orderBy` in the window?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```python
    p8 = (orders.withColumn("customer_total", F.sum("amount").over(Window.partitionBy("customer_id")))
          .withColumn("share_pct", F.round(F.col("amount") / F.col("customer_total") * 100, 1))
          .select("customer_id", "order_id", "amount", "customer_total", "share_pct")
          .orderBy("customer_id", "order_id"))
    p8.show()
    ```
    ```text
    +-----------+--------+------+--------------+---------+
    |customer_id|order_id|amount|customer_total|share_pct|
    +-----------+--------+------+--------------+---------+
    |          1|    1001| 59.90|        327.40|     18.3|
    |          1|    1003|189.50|        327.40|     57.9|
    |          1|    1008| 78.00|        327.40|     23.8|
    |          2|    1002|249.00|        278.95|     89.3|
    |          2|    1006| 29.95|        278.95|     10.7|
    |          3|    1004| 39.00|        198.00|     19.7|
    |          3|    1007|159.00|        198.00|     80.3|
    |          4|    1005|318.00|        318.00|    100.0|
    +-----------+--------+------+--------------+---------+
    ```
    Without `orderBy`, the window frame is the whole partition, so `sum` is the customer's total. Adding `orderBy("order_ts")` would change the default frame to "from the start up to the current row" and give a running total instead (section 3.12). SQL: `amount / sum(amount) OVER (PARTITION BY customer_id) * 100`.

**Q37. Write PySpark that computes daily order counts and revenue and writes them as Parquet partitioned by `order_date`, so that rerunning the job does not duplicate data.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```python
    daily = (orders.withColumn("order_date", F.to_date("order_ts"))
             .groupBy("order_date").agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue")))
    for run in (1, 2):                                   # run it twice on purpose
        daily.write.mode("overwrite").partitionBy("order_date").parquet(out)
    spark.read.parquet(out).orderBy("order_date").show()
    ```
    ```text
    folders: ['order_date=2026-03-01', 'order_date=2026-03-02', 'order_date=2026-03-03', 'order_date=2026-03-04']
    +------+-------+----------+
    |orders|revenue|order_date|
    +------+-------+----------+
    |     2| 308.90|2026-03-01|
    |     2| 228.50|2026-03-02|
    |     2| 347.95|2026-03-03|
    |     2| 237.00|2026-03-04|
    +------+-------+----------+
    ```
    `overwrite` makes the rerun idempotent: the second run replaced the data instead of adding rows. With `append` the second run would double every count. On Databricks you would write a Delta table instead, where the overwrite is atomic ([chapter 4](04-Delta-Lake.md)).

**Q38. You read a CSV with `header=True, inferSchema=True` and `amount` comes back as `string`. Why, and what is the production fix?**

??? success "Answer"
    Inference scans the values, and at least one value in the column is not a number (in section 3.13, one `N/A`), so the only type that fits every value is string. Production fix: give an explicit schema with `amount DECIMAL(10,2)`, and decide what happens to bad values: `PERMISSIVE` plus a `_corrupt_record` column to quarantine them, `DROPMALFORMED` to drop them, or `FAILFAST` to stop the job. With `PERMISSIVE` and no corrupt-record column, the bad value silently becomes `NULL`.

**Q39. A nightly job writes `df.write.parquet(path)`. It worked for a month, and tonight's retry after a failure ended with `[PATH_ALREADY_EXISTS]`. Why, and what are the options?**

??? success "Answer"
    The default save mode is `errorifexists`: the failed run had already created the folder, so the retry refuses to write (the section 3.13 run shows the same error). Options: `mode("overwrite")` if the job rewrites the whole output (idempotent, but in plain Parquet the old data is deleted first, not atomically), `mode("append")` only if duplicates are handled, or better, a Delta table with an atomic overwrite, `INSERT ... REPLACE WHERE` for one day, or `MERGE` on a key (chapter 20).

**Q40. What is Spark Connect, how is Databricks Connect related to it, and what changes for your code?**

??? success "Answer"
    Spark Connect (Apache Spark 3.4 and later) is a client-server protocol: the client turns DataFrame operations into unresolved logical plans, sends them over gRPC, and receives results as Arrow batches. Databricks Connect "is built on open-source Spark Connect"; for Databricks Runtime 13.3 LTS and above it is "an extension of Spark Connect" that adds support for Databricks compute modes and Unity Catalog, so you can run Spark code from an IDE against Databricks compute. Code changes: no RDDs or `SparkContext`; analysis errors appear at the action or schema access, not when the DataFrame is built; temp views are looked up by name at execution; Python UDFs are serialized when the action runs; and frequent `df.columns` calls cost a round trip each. Serverless compute and standard access mode (formerly shared) notebooks also run on Spark Connect.

## Sources

Databricks documentation (AWS):

- [Apache Spark overview](https://docs.databricks.com/aws/en/spark/) (last updated Sep 11, 2026)
- [Apache Spark on Databricks](https://docs.databricks.com/aws/en/spark/faq) (last updated Sep 11, 2026)
- [PySpark basics](https://docs.databricks.com/aws/en/pyspark/basics) (last updated Sep 14, 2026)
- [Compute](https://docs.databricks.com/aws/en/compute/) (last updated Nov 5, 2026)
- [Serverless compute limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations) (last updated Nov 5, 2026)
- [Cache DataFrames on serverless compute](https://docs.databricks.com/aws/en/compute/serverless/dataframe-cache) (last updated Oct 22, 2026)
- [Optimize performance with caching on Databricks](https://docs.databricks.com/aws/en/optimizations/disk-cache) (last updated Oct 22, 2026)
- [Adaptive query execution](https://docs.databricks.com/aws/en/optimizations/aqe) (last updated Oct 12, 2026)
- [Skew join optimization using skew hints](https://docs.databricks.com/aws/en/optimizations/skew-join) (last updated May 13, 2024; marked retired)
- [Hints](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-hints) (last updated Oct 12, 2026)
- [When to partition tables on Databricks](https://docs.databricks.com/aws/en/tables/partitions) (last updated Sep 11, 2026)
- [What is Photon?](https://docs.databricks.com/aws/en/compute/photon) (last updated Sep 11, 2026)
- [What are user-defined functions (UDFs)?](https://docs.databricks.com/aws/en/udf/) (last updated Sep 22, 2026)
- [pandas user-defined functions](https://docs.databricks.com/aws/en/udf/pandas) (last updated Sep 11, 2026)
- [Python scalar user-defined functions (UDFs)](https://docs.databricks.com/aws/en/udf/python) (last updated Nov 6, 2026)
- [Debugging with the Spark UI](https://docs.databricks.com/aws/en/compute/troubleshooting/debugging-spark-ui) (last updated Sep 11, 2026)
- [Diagnose cost and performance issues using the Spark UI](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/) (last updated Oct 12, 2026)
- [Diagnosing a long job in Spark](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/long-spark-stage) (last updated Oct 12, 2026)
- [Skew and spill](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/long-spark-stage-page) (last updated Oct 12, 2026)
- [Long Spark stage with one task](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/one-spark-task) (last updated Oct 12, 2026)
- [Slow Spark stage with little I/O](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/slow-spark-stage-low-io) (last updated Oct 12, 2026)
- [Spark memory issues](https://docs.databricks.com/aws/en/optimizations/spark-ui-guide/spark-memory-issues) (last updated Oct 12, 2026)
- [Query profile](https://docs.databricks.com/aws/en/sql/user/queries/query-profile) (last updated Sep 11, 2026)
- [Compare Spark Connect to Spark Classic](https://docs.databricks.com/aws/en/spark/connect-vs-classic) (last updated Sep 11, 2026)
- [Databricks Connect](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/) (last updated Sep 11, 2026)
- [Tutorial: Run Python code on serverless compute](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/python/tutorial-serverless) (last updated Sep 11, 2026)
- [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) (last updated Oct 30, 2026), for the access mode names

Databricks glossary (no date shown):

- [What is a Catalyst Optimizer?](https://www.databricks.com/glossary/catalyst-optimizer)
- [What is Tungsten?](https://www.databricks.com/glossary/tungsten)

Apache Spark documentation, version 4.2.0 (the pages show no last-updated date):

- [Apache Spark - A Unified engine for large-scale data analytics](https://spark.apache.org/docs/4.2.0/index.html)
- [Cluster Mode Overview](https://spark.apache.org/docs/4.2.0/cluster-overview.html)
- [Spark Configuration](https://spark.apache.org/docs/4.2.0/configuration.html)
- [Performance Tuning](https://spark.apache.org/docs/4.2.0/sql-performance-tuning.html)
- [RDD Programming Guide](https://spark.apache.org/docs/4.2.0/rdd-programming-guide.html)
- [Spark SQL, DataFrames and Datasets Guide](https://spark.apache.org/docs/4.2.0/sql-programming-guide.html)
- [EXPLAIN](https://spark.apache.org/docs/4.2.0/sql-ref-syntax-qry-explain.html)
- [Hints](https://spark.apache.org/docs/4.2.0/sql-ref-syntax-qry-select-hints.html)
- [CACHE TABLE](https://spark.apache.org/docs/4.2.0/sql-ref-syntax-aux-cache-cache-table.html)
- [Generic Load/Save Functions](https://spark.apache.org/docs/4.2.0/sql-data-sources-load-save-functions.html)
- [CSV Files](https://spark.apache.org/docs/4.2.0/sql-data-sources-csv.html)
- [JSON Files](https://spark.apache.org/docs/4.2.0/sql-data-sources-json.html)
- [Parquet Files](https://spark.apache.org/docs/4.2.0/sql-data-sources-parquet.html)
- [Web UI](https://spark.apache.org/docs/4.2.0/web-ui.html)
- [Spark Connect Overview](https://spark.apache.org/docs/4.2.0/spark-connect-overview.html)
- [Apache Arrow in PySpark](https://spark.apache.org/docs/4.2.0/api/python/tutorial/sql/arrow_pandas.html)
- PySpark API reference: [DataFrame.cache](https://spark.apache.org/docs/4.2.0/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.cache.html), [DataFrame.persist](https://spark.apache.org/docs/4.2.0/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.persist.html), [DataFrame.coalesce](https://spark.apache.org/docs/4.2.0/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.coalesce.html), [DataFrame.collect](https://spark.apache.org/docs/4.2.0/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.collect.html), [DataFrame.toPandas](https://spark.apache.org/docs/4.2.0/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.toPandas.html), [DataFrame.explain](https://spark.apache.org/docs/4.2.0/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.explain.html), [functions.udf](https://spark.apache.org/docs/4.2.0/api/python/reference/pyspark.sql/api/pyspark.sql.functions.udf.html), [StorageLevel](https://spark.apache.org/docs/4.2.0/api/python/reference/api/pyspark.StorageLevel.html)
- [Apache Spark project history](https://spark.apache.org/history.html) (spark.apache.org, no date shown)
