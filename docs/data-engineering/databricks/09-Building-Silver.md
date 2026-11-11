# 9. Building silver

*Bronze keeps everything exactly as it arrived; silver is where the data becomes trustworthy. This chapter builds
the Red Rock Supply silver layer step by step: reading bronze as a batch and as a stream, casting and cleaning,
schema enforcement and evolution, the quarantine pattern, deduplication, late and out-of-order data, slowly changing
dimensions with `MERGE`, idempotent reruns, and Change Data Feed to pass changes on to gold. Every example was run
on Apache Spark 4.2 with Delta Lake 4.4.1, so you can see what really happens, including the errors. Interviewers
probe this layer harder than any other, because it is where pipelines silently go wrong.*

!!! abstract "In this chapter"
    **You will learn:**

    - how to read bronze in batch and as a stream, and what breaks a stream from a Delta table
    - how to cast and clean safely with `try_cast`, `try_to_timestamp`, `trim`, `upper`, `nullif`, `coalesce`
    - what Delta schema enforcement rejects, what it silently casts, and how `mergeSchema`,
      `WITH SCHEMA EVOLUTION` and `overwriteSchema` differ
    - the quarantine pattern: valid rows to silver, invalid rows with a reason to a quarantine table
    - deduplication with `dropDuplicates`, `row_number` and `QUALIFY`, and why event time beats ingest time
    - the out-of-order guard in `MERGE` (`WHEN MATCHED AND s.updated_at > t.updated_at`) and why it is `>`, not `>=`
    - the "multiple source rows matched" error, reproduced and fixed
    - how to prove a rerun changes nothing
    - SCD Type 1 and SCD Type 2 with `MERGE`, over several real loads
    - Change Data Feed: turning it on, `table_changes`, `readChangeFeed`, and propagating updates and deletes

    **You need:** [4. Delta Lake](04-Delta-Lake.md) (transaction log, `MERGE`, time travel),
    [7. The medallion architecture](07-Medallion-Architecture.md) and 8. Into bronze.
    Generic `MERGE` syntax is in the SQL course:
    [Insert, update, delete, merge](../../databases/sql/17-Insert-Update-Delete-Merge.md).

    **Levels:** sections 9.1 to 9.3 beginner, 9.4 to 9.9 intermediate, 9.10 and 9.11 expert.

## 9.1 What silver is for

*Level: beginner.*

The bronze table `shop.bronze.orders` from chapter 8 holds every order event Red Rock Supply received, as strings,
with two metadata columns: `_source_file` (which file the row came from) and `_ingest_ts` (when it was loaded).
Nothing was fixed there on purpose: if a cleaning rule is wrong, you can rerun silver from bronze and lose nothing.

Analysts cannot use bronze directly. `amount` is a string, one row says `"abc"`, a currency is written `cad`, the same
event was delivered twice, and order 1002 appears three times with three different statuses. Silver is the layer
that answers "what is true about each order and each customer right now" (and, for some tables, "what was true at
any moment in the past").

The Databricks description of the medallion architecture lists the work done in silver: schema enforcement, handling
of null and missing values, deduplication, resolution of out-of-order and late-arriving data, data quality checks,
schema evolution, type casting and joins. It also says silver "should always include at least one validated,
non-aggregated representation of each record", and that Databricks does not recommend writing to silver directly from
ingestion ([medallion architecture](https://docs.databricks.com/aws/en/lakehouse/medallion)).

This chapter builds four silver tables. Locally there is no Unity Catalog, so the run-here code uses flat names; on
Databricks they would live in the `shop.silver` schema.

| Local name (run here) | On Databricks | Holds |
| --- | --- | --- |
| `bronze_orders` | `shop.bronze.orders` | raw order events (input) |
| `silver_order_events` | `shop.silver.order_events` | every valid event, typed, one row per event |
| `quarantine_orders` | `shop.silver.orders_quarantine` | rejected events with the reason |
| `silver_orders` | `shop.silver.orders` | one row per order, its latest state |
| `silver_customers` / `silver_customers_scd2` | `shop.silver.customers` | customers as SCD Type 1 and Type 2 |

One addition to the shared dataset: each raw order event carries `updated_at`, the time the order service recorded
that status. Without an event-time column there is no way to tell which of two events is newer, and sections 9.6
and 9.7 depend on it. The shared `customers` table already has `updated_at`.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Silver flow: bronze is read as a stream, typed and validated, valid rows go to silver order events and then by MERGE to silver orders, invalid rows go to a quarantine table with reasons">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="20" y="40" width="150" height="60" rx="6"/>
<rect x="220" y="40" width="180" height="60" rx="6"/>
<rect x="450" y="40" width="170" height="60" rx="6" stroke-dasharray="5 4"/>
<rect x="220" y="200" width="180" height="60" rx="6"/>
<rect x="450" y="200" width="170" height="60" rx="6"/>
<line x1="170" y1="70" x2="212" y2="70"/>
<line x1="400" y1="70" x2="442" y2="70"/>
<line x1="310" y1="100" x2="310" y2="192"/>
<line x1="400" y1="230" x2="442" y2="230"/>
</g>
<g fill="currentColor">
<polygon points="220,70 210,65 210,75"/>
<polygon points="450,70 440,65 440,75"/>
<polygon points="310,200 305,190 315,190"/>
<polygon points="450,230 440,225 440,235"/>
</g>
<g fill="currentColor" font-size="14" text-anchor="middle">
<text x="95" y="66">bronze_orders</text>
<text x="310" y="66">type + validate</text>
<text x="535" y="66">quarantine_orders</text>
<text x="310" y="226">silver_order_events</text>
<text x="535" y="226">silver_orders</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="95" y="86">raw strings, append-only</text>
<text x="310" y="86">try_cast, trim, rules</text>
<text x="535" y="86">raw values + reasons</text>
<text x="310" y="246">valid, one row per event</text>
<text x="535" y="246">latest state per order</text>
<text x="195" y="30">stream</text>
<text x="425" y="30">errors</text>
<text x="425" y="285">dedupe + guarded MERGE</text>
</g>
<g fill="currentColor" font-size="13">
<text x="320" y="150">no errors</text>
</g>
</svg>
<figcaption>Figure 9.1. The silver flow for Red Rock Supply orders. Every bronze row ends up in exactly one of
silver_order_events or quarantine_orders; silver_orders is then maintained from the valid events by MERGE.</figcaption>
</figure>

!!! tip "In the interview"
    **"What happens in your silver layer?"** Silver turns raw bronze records into typed, validated, deduplicated
    records with one trustworthy row per business entity (or per event), keeps invalid rows aside with a reason
    instead of dropping them, and applies late or repeated data so that reruns give the same result. Business
    aggregates belong in gold.

## 9.2 Reading bronze: batch or stream

*Level: beginner.*

There are two ways to read a bronze Delta table. A **batch read** (`spark.read.table`) sees the whole table as of one
version. A **streaming read** (`spark.readStream.table`) remembers, in a **checkpoint** folder, which table versions it
has already processed, so each run reads only rows added since the last run. Run with the `availableNow` trigger, a
stream processes everything new and then stops, which makes it a good fit for a scheduled job (chapter 11 covers
triggers in depth).

Databricks gives a clear rule: "Assuming all sources are append-only, configure most reads from bronze as streaming
reads. Batch reads should be reserved for small datasets (for example, small dimensional tables)"
([medallion architecture](https://docs.databricks.com/aws/en/lakehouse/medallion)). Bronze is normally append-only,
so a stream gives incremental processing for free.

First a batch read of bronze after the first file landed:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
bronze = spark.read.table("bronze_orders")          # shop.bronze.orders on Databricks
bronze.printSchema()
bronze.select("order_id", "customer_id", "order_ts", "status", "amount", "currency").show(truncate=False)
```

```text
root
 |-- order_id: string (nullable = true)
 |-- customer_id: string (nullable = true)
 |-- order_ts: string (nullable = true)
 |-- status: string (nullable = true)
 |-- amount: string (nullable = true)
 |-- currency: string (nullable = true)
 |-- updated_at: string (nullable = true)
 |-- items: string (nullable = true)
 |-- _source_file: string (nullable = true)
 |-- _ingest_ts: timestamp (nullable = true)

+--------+-----------+--------------------+--------+------+--------+
|order_id|customer_id|order_ts            |status  |amount|currency|
+--------+-----------+--------------------+--------+------+--------+
|1001    |7          |2026-03-01T10:15:00Z|PLACED  |59.90 |CAD     |
|1002    |8          |2026-03-01T11:00:00Z| placed |120.00|cad     |
|1003    |9          |2026-03-01 12:30:00 |PLACED  |abc   |CAD     |
|1004    |NULL       |2026-03-01T12:45:00Z|PLACED  |15.00 |CAD     |
|1005    |7          |03/01/2026 13:05    |Placed  |35.5  |usd     |
|1006    |10         |not a date          |PLACED  |80.00 |CAD     |
|1007    |8          |2026-03-01T15:20:00Z|PLACED  |-5.00 |        |
+--------+-----------+--------------------+--------+------+--------+
```

(The `items` array stays in bronze as raw JSON; splitting it into `order_items` is a chapter 18 and chapter 12 topic.)

Now the same data as a stream. The function below is run three times: on the first file, again with nothing new,
and after the second file lands.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def run_stream(extra_options=None):
    reader = spark.readStream
    for k, v in (extra_options or {}).items():
        reader = reader.option(k, v)
    q = (reader.table("bronze_orders")
         .selectExpr(*CLEAN_EXPRS)                 # the cleaning expressions of section 9.3
         .writeStream
         .option("checkpointLocation", checkpoint)
         .trigger(availableNow=True)
         .toTable("silver_orders_typed"))
    q.awaitTermination()
    rows = sum(p["numInputRows"] for p in q.recentProgress)
    print(f"stream run read {rows} new bronze rows; silver_orders_typed now has "
          f"{spark.read.table('silver_orders_typed').count()} rows")

run_stream()                                        # first file only
run_stream()                                        # nothing new
load_bronze(spark, base, "orders_2026-03-02.json")
run_stream()                                        # only the second file
```

```text
stream run read 7 new bronze rows; silver_orders_typed now has 7 rows
stream run read 0 new bronze rows; silver_orders_typed now has 7 rows
stream run read 3 new bronze rows; silver_orders_typed now has 10 rows
```

The checkpoint is what makes the second run read nothing. Delete it and the stream starts over from the whole table.

### What breaks a stream from a Delta table

A Delta streaming source expects appends only. Databricks states that if an `UPDATE`, `DELETE`, `MERGE INTO` or
`OVERWRITE` modifies the source table, "the stream fails with an error"
([Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)).
Here someone fixes a currency in bronze, then the job runs again:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
sql("UPDATE bronze_orders SET currency = 'CAD' WHERE order_id = '1007'")
run_stream()                                   # fails
run_stream({"skipChangeCommits": "true"})      # ignores the UPDATE commit, keeps going
```

```text
stream error: [DELTA_SOURCE_TABLE_IGNORE_CHANGES] Detected a data update (for example UPDATE (Map(predicate -> "[\"(order_id#3164 = 100
stream run read 0 new bronze rows; silver_orders_typed now has 10 rows
```

(The script cuts the long error message.) The same page lists four ways out: `skipChangeCommits` (ignore commits
that change existing rows and process only appends; Databricks recommends it "for most workloads that do not use
change data feeds"), a full refresh of the downstream table, reading the Change Data Feed instead (section 9.11), or a
materialized view. In Databricks Runtime 12.2 LTS and above, `skipChangeCommits` replaces the older `ignoreChanges`
option. `skipChangeCommits` does not propagate the change: silver still has the old currency for 1007 until you fix
it separately.

On Databricks the same stream reads and writes Unity Catalog tables, with the checkpoint in a volume:

*Databricks only, not run here. Syntax from [Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake).*

```python
(spark.readStream
   .option("skipChangeCommits", "true")
   .table("shop.bronze.orders")
   .selectExpr(*CLEAN_EXPRS)
   .writeStream
   .option("checkpointLocation", "/Volumes/shop/silver/checkpoints/orders_typed")
   .trigger(availableNow=True)
   .toTable("shop.silver.orders_typed"))
```

!!! warning "Retention and slow streams"
    Databricks warns that a stream reading a Delta table must run at least once within the source table's retention
    window (by default 7 days for files removed by `VACUUM` and 30 days for the transaction log), or it fails with
    `DELTA_FILE_NOT_FOUND_DETAILED` and needs a full refresh. Do not set `spark.sql.files.ignoreMissingFiles` to
    work around it ([Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)).

## 9.3 Casting, cleaning and nulls

*Level: beginner.*

### `cast` fails the query, `try_cast` returns NULL

With ANSI mode on (as in this Spark 4.2 engine), a plain `CAST` of a malformed string stops the whole query. One bad
row out of millions would fail the job. `try_cast` returns `NULL` for that row instead
([try_cast](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_cast), Databricks Runtime 10.4 LTS
and above):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT cast('abc' AS DECIMAL(10,2)) AS amount;
SELECT try_cast('abc' AS DECIMAL(10,2)) AS bad,
       try_cast(' 59.90 ' AS DECIMAL(10,2)) AS padded,
       try_cast('35.5' AS DECIMAL(10,2)) AS short;
```

```text
cast error: [CAST_INVALID_INPUT] The value 'abc' of the type "STRING" cannot be cast to "DECIMAL(10,2)" because it is malformed. Correct the value as per the syntax, or change its target type. Use `try_cast` to tolerate malformed input and return NULL instead. SQLSTATE: 22018
+----+------+-----+
|bad |padded|short|
+----+------+-----+
|NULL|59.90 |35.50|
+----+------+-----+
```

`try_cast` is not magic: the cast combination itself must be valid. The reference says that if the source and target
types are not a valid cast combination, a `DATATYPE_MISMATCH` error is returned.

### Timestamps in several formats

`to_timestamp(expr, fmt)` raises an error when the text does not match; `try_to_timestamp` returns `NULL`
([to_timestamp](https://docs.databricks.com/aws/en/sql/language-manual/functions/to_timestamp),
[try_to_timestamp](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_to_timestamp), Databricks
Runtime 11.3 LTS and above). The `to_timestamp` page adds that in Databricks Runtime with `spark.sql.ansi.enabled` set
to `false`, `to_timestamp` returns `NULL` instead of an error. Chaining `try_to_timestamp` calls inside `coalesce`
accepts several formats, the first one that parses wins:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT s,
       try_to_timestamp(s) AS no_format,
       coalesce(try_to_timestamp(s), try_to_timestamp(s, 'MM/dd/yyyy HH:mm')) AS two_formats
FROM VALUES ('2026-03-01T10:15:00Z'), ('2026-03-01 12:30:00'), ('03/01/2026 13:05'), ('not a date') AS v(s)
```

```text
to_timestamp error: [CAST_INVALID_INPUT] The value 'not a date' of the type "STRING" cannot be cast to "TIMESTAMP" because it is malformed. Correct the value as per the syntax, or change its target type. Use `try_cast` to tolerate malformed input and return NULL instead. SQLSTATE: 22018
+--------------------+-------------------+-------------------+
|s                   |no_format          |two_formats        |
+--------------------+-------------------+-------------------+
|2026-03-01T10:15:00Z|2026-03-01 10:15:00|2026-03-01 10:15:00|
|2026-03-01 12:30:00 |2026-03-01 12:30:00|2026-03-01 12:30:00|
|03/01/2026 13:05    |NULL               |2026-03-01 13:05:00|
|not a date          |NULL               |NULL               |
+--------------------+-------------------+-------------------+
```

(The first line came from `SELECT to_timestamp('not a date')`.) The session time zone here is UTC, so
`2026-03-01T10:15:00Z` shows as 10:15. With another session time zone the displayed value shifts; the stored instant
does not.

!!! warning "Ambiguous formats"
    `03/01/2026` is March 1 in `MM/dd/yyyy` and January 3 in `dd/MM/yyyy`. Nothing in the data tells you which. Agree
    the format with the source team and write it down; do not guess per row.

### The cleaning query

Standardizing means making equal things look equal: trim spaces, one case for codes, and empty strings turned into
`NULL` so that "missing" has one representation. `nullif(x, '')` returns `NULL` when `x` is the empty string.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE OR REPLACE TEMP VIEW orders_typed AS
SELECT
  try_cast(order_id AS INT)                         AS order_id,
  try_cast(customer_id AS INT)                      AS customer_id,
  coalesce(try_to_timestamp(order_ts),
           try_to_timestamp(order_ts, 'MM/dd/yyyy HH:mm')) AS order_ts,
  upper(trim(status))                               AS status,
  try_cast(amount AS DECIMAL(10,2))                 AS amount,
  nullif(upper(trim(currency)), '')                 AS currency,
  try_to_timestamp(updated_at)                      AS updated_at,
  _source_file,
  _ingest_ts
FROM bronze_orders;

SELECT * EXCEPT (_source_file, _ingest_ts) FROM orders_typed ORDER BY order_id;
SELECT count(*) AS total_rows,
       count_if(customer_id IS NULL) AS no_customer,
       count_if(order_ts IS NULL)    AS bad_ts,
       count_if(amount IS NULL)      AS bad_amount,
       count_if(currency IS NULL)    AS no_currency
FROM orders_typed;
```

```text
+--------+-----------+-------------------+------+------+--------+-------------------+
|order_id|customer_id|order_ts           |status|amount|currency|updated_at         |
+--------+-----------+-------------------+------+------+--------+-------------------+
|1001    |7          |2026-03-01 10:15:00|PLACED|59.90 |CAD     |2026-03-01 10:15:00|
|1002    |8          |2026-03-01 11:00:00|PLACED|120.00|CAD     |2026-03-01 11:00:00|
|1003    |9          |2026-03-01 12:30:00|PLACED|NULL  |CAD     |2026-03-01 12:30:00|
|1004    |NULL       |2026-03-01 12:45:00|PLACED|15.00 |CAD     |2026-03-01 12:45:00|
|1005    |7          |2026-03-01 13:05:00|PLACED|35.50 |USD     |2026-03-01 13:05:00|
|1006    |10         |NULL               |PLACED|80.00 |CAD     |2026-03-01 14:00:00|
|1007    |8          |2026-03-01 15:20:00|PLACED|-5.00 |NULL    |2026-03-01 15:20:00|
+--------+-----------+-------------------+------+------+--------+-------------------+

+----------+-----------+------+----------+-----------+
|total_rows|no_customer|bad_ts|bad_amount|no_currency|
+----------+-----------+------+----------+-----------+
|7         |1          |1     |1         |1          |
+----------+-----------+------+----------+-----------+
```

The same cleaning with the DataFrame API (Spark 4 has `Column.try_cast` and `F.try_to_timestamp`). The script
compares it with the SQL view and finds no difference:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql import functions as F

typed_df = spark.read.table("bronze_orders").select(
    F.col("order_id").try_cast("int").alias("order_id"),
    F.col("customer_id").try_cast("int").alias("customer_id"),
    F.coalesce(F.try_to_timestamp("order_ts"),
               F.try_to_timestamp("order_ts", F.lit("MM/dd/yyyy HH:mm"))).alias("order_ts"),
    F.upper(F.trim("status")).alias("status"),
    F.col("amount").try_cast("decimal(10,2)").alias("amount"),
    F.nullif(F.upper(F.trim("currency")), F.lit("")).alias("currency"),
    F.try_to_timestamp("updated_at").alias("updated_at"),
    "_source_file", "_ingest_ts")
print("rows that differ from the SQL version:",
      typed_df.exceptAll(spark.table("orders_typed")).count()
      + spark.table("orders_typed").exceptAll(typed_df).count())
```

```text
rows that differ from the SQL version: 0
```

### Nulls: decide, do not default

Every `NULL` in the typed result means one of two things: the source did not send a value (1004 has no customer), or
the value was there but could not be read (1003's `abc`). The table cannot tell them apart unless you keep the raw
value next to it, which is what the quarantine table in section 9.5 does.

Filling nulls (`coalesce(currency, 'CAD')`, `fillna`) is a business decision, not a cleaning step. Filling a missing
currency with `CAD` would make a US order look Canadian. Fill only when there is a documented rule; otherwise reject
the row or keep the `NULL` and let consumers see it.

!!! warning "try_cast hides problems if you stop there"
    `try_cast` keeps the job running, but every bad value becomes a `NULL` that looks just like a missing one. Always
    pair it with a rule that checks "raw value present but typed value NULL" and routes the row somewhere visible.

## 9.4 Schema enforcement and schema evolution

*Level: intermediate.*

**Schema enforcement** means a Delta table rejects writes that do not fit its schema. **Schema evolution** means the
table's schema is allowed to change as part of a write. Silver wants strict enforcement by default (a surprise column
should stop the job, not slip in) and evolution only when you choose it.

The Databricks rules for `INSERT` are: every inserted column must exist in the target table, and column data types
must match, with Databricks attempting to "safely cast column data types to match the target table". For `MERGE`, the
target columns of an action must exist, and with `INSERT *` or `UPDATE SET *` the source must have every target
column, while extra source columns are ignored
([Schema enforcement](https://docs.databricks.com/aws/en/tables/schema-enforcement)).

All of the following ran against one table, `silver_orders_demo (order_id INT NOT NULL, status STRING, amount
DECIMAL(10,2))`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
extra = spark.sql("SELECT 1002 AS order_id, 'PLACED' AS status, "
                  "CAST(120.00 AS DECIMAL(10,2)) AS amount, 'SPRING10' AS coupon_code")
extra.write.format("delta").mode("append").saveAsTable("silver_orders_demo")      # 1
extra.write.format("delta").mode("append").option("mergeSchema", "true") \
     .saveAsTable("silver_orders_demo")                                           # 2
# amount sent as a STRING: '35.50', then 'abc'
df.write.format("delta").mode("append").saveAsTable("silver_orders_demo")         # 3, 4
```

```text
append without mergeSchema: FAILED -> [DELTA_METADATA_MISMATCH] A metadata mismatch was detected when writing to the Delta table.
append with mergeSchema: OK
append amount '35.50' as STRING: OK
append amount 'abc' as STRING: FAILED -> [CAST_INVALID_INPUT] The value 'abc' of the type "STRING" cannot be cast to "DECIMAL(10,2)" because it is malformed. Correct the value as per the syntax, or change its target type. Use `try_cast` to t
```

Two lessons. An unexpected column fails the write until you opt in with `mergeSchema`; after that, the old rows get
`NULL` in the new column. And schema enforcement checks types, not values: a string column was cast into
`DECIMAL(10,2)` without complaint when the value was `'35.50'`, and the whole write failed when one value was
`'abc'`. Type your data with `try_cast` and validate it before writing to silver; do not rely on the table to do it.

SQL `INSERT`, `NOT NULL` and `CHECK` constraints:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO silver_orders_demo (order_id, gift_wrap) VALUES (1004, true);         -- unknown column
INSERT INTO silver_orders_demo (order_id, status) VALUES (1004, 'PLACED');        -- amount left out
INSERT INTO silver_orders_demo (order_id, status) VALUES (NULL, 'PLACED');        -- order_id is NOT NULL
ALTER TABLE silver_orders_demo ADD CONSTRAINT amount_ok CHECK (amount >= 0);
ALTER TABLE silver_orders_demo ADD CONSTRAINT amount_ok CHECK (amount IS NULL OR amount >= 0);
INSERT INTO silver_orders_demo (order_id, status, amount) VALUES (1007, 'PLACED', -5.00);
```

```text
INSERT unknown column: FAILED -> [UNRESOLVED_COLUMN.WITH_SUGGESTION] A column, variable, or function parameter with name `gift_wrap` cannot be resolved. Did you mean one of the following? [`order_id`, `status`, `amount`, `coupon_code
INSERT only some columns: OK
INSERT NULL into NOT NULL order_id: FAILED -> [DELTA_NOT_NULL_CONSTRAINT_VIOLATED] NOT NULL constraint violated for column: order_id.
ADD CONSTRAINT CHECK (amount >= 0): FAILED -> [DELTA_NEW_CHECK_CONSTRAINT_VIOLATION] 1 rows in spark_catalog.default.silver_orders_demo violate the new CHECK constraint (amount >= 0)
ADD CONSTRAINT CHECK (amount IS NULL OR amount >= 0): OK
INSERT amount -5.00: FAILED -> [DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint amount_ok ((amount IS NULL) OR (amount >= 0)) violated by row with values:
```

The first `CHECK` was refused because order 1004 has a `NULL` amount: a `CHECK` expression "must be true for each
input row" ([Constraints](https://docs.databricks.com/aws/en/tables/constraints)), and `NULL >= 0` is `NULL`, not
true. Say what you mean about nulls in the constraint itself.

### MERGE: ignored columns, evolution, and missing columns

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- src has order_id, status, amount, coupon_code and an extra column: carrier
MERGE INTO silver_orders_demo t USING src s ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

MERGE WITH SCHEMA EVOLUTION INTO silver_orders_demo t USING src s ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

```text
MERGE ... UPDATE SET * / INSERT *: OK
+--------+-------+------+-----------+
|order_id|status |amount|coupon_code|
+--------+-------+------+-----------+
|1001    |SHIPPED|59.90 |NULL       |
|1002    |PLACED |120.00|SPRING10   |
|1003    |PLACED |35.50 |NULL       |
|1004    |PLACED |NULL  |NULL       |
|1005    |PLACED |35.50 |NULL       |
+--------+-------+------+-----------+

MERGE WITH SCHEMA EVOLUTION: OK
+--------+-------+------+-----------+-------+
|order_id|status |amount|coupon_code|carrier|
+--------+-------+------+-----------+-------+
|1001    |SHIPPED|59.90 |NULL       |UPS    |
|1002    |PLACED |120.00|SPRING10   |NULL   |
|1003    |PLACED |35.50 |NULL       |NULL   |
|1004    |PLACED |NULL  |NULL       |NULL   |
|1005    |PLACED |35.50 |NULL       |NULL   |
+--------+-------+------+-----------+-------+
```

Without evolution the `carrier` column was silently dropped. That is documented behavior, and it is a trap: if the
source team adds a column you need, nothing fails and nothing arrives. With `WITH SCHEMA EVOLUTION` the column was
added. The opposite case, a source missing a target column, failed here with `UPDATE SET *`; the local build reported
`[INTERNAL_ERROR] Cannot find main error class 'DELTA_MERGE_UNRESOLVED_EXPRESSION'`, which names the error Databricks
documents for unresolvable `MERGE` columns (the exact error Databricks raises for this missing-source-column case is
not verified). With schema evolution on, Databricks documents that target columns
missing from the source are left unchanged by `UPDATE SET *` and set to `NULL` by `INSERT *`
([Update table schemas](https://docs.databricks.com/aws/en/tables/update-schema)).

Changing a column's type is not evolution in this sense. It needs a rewrite with `overwriteSchema`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
df8 = spark.read.table("silver_orders_demo").withColumn("order_id", F.col("order_id").cast("bigint"))
df8.write.format("delta").mode("overwrite").saveAsTable("silver_orders_demo")
df8.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("silver_orders_demo")
```

```text
overwrite with order_id BIGINT, no overwriteSchema: FAILED -> [DELTA_FAILED_TO_MERGE_FIELDS] Failed to merge fields 'order_id' and 'order_id'
overwrite with order_id BIGINT and overwriteSchema: OK
```

(Databricks also has type widening for some type changes without a rewrite; see chapter 22 and the
[schema evolution page](https://docs.databricks.com/aws/en/tables/update-schema).)

| Want | Tool | Notes from the docs |
| --- | --- | --- |
| Add new source columns on append | `.option("mergeSchema", "true")` | per write; batch or streaming |
| Add new source columns in `INSERT` SQL | `INSERT WITH SCHEMA EVOLUTION INTO ...` | Databricks Runtime 18.1 and above; earlier, use `mergeSchema` |
| Add new source columns in `MERGE` | `MERGE WITH SCHEMA EVOLUTION INTO ...` or `.withSchemaEvolution()` | see the version note below |
| Session-wide evolution | `spark.databricks.delta.schema.autoMerge.enabled` | called legacy; "Databricks doesn't recommend this approach for production" |
| Change type, rename by rewrite, drop columns by rewrite | `.option("overwriteSchema", "true")` with `mode("overwrite")` | replaces schema and partitioning |

The `WITH SCHEMA EVOLUTION` clause of `MERGE` is marked "Databricks Runtime 15.2 or above" on the
[MERGE INTO reference](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into), while the
[schema evolution page](https://docs.databricks.com/aws/en/tables/update-schema) says "Databricks Runtime 15.4 LTS
and above". The exact first version is therefore not verified; on any current runtime both pages agree it works.

!!! warning "Schema changes stop streams"
    The schema evolution page warns that updating a table schema terminates any streams reading from that table; they
    must be restarted. Evolving silver's schema will stop the gold streams that read it.

!!! tip "In the interview"
    **"A new column appeared in the source. What happens in your pipeline?"** A Delta append without `mergeSchema`
    fails with a metadata mismatch, which is what you want in silver: someone decides. A `MERGE` with
    `UPDATE SET *` silently ignores the extra column unless you use `MERGE WITH SCHEMA EVOLUTION`. I enable
    evolution per write, never with the session-wide setting, and I keep the new column in bronze either way, so I can
    backfill it later.

## 9.5 The quarantine pattern

*Level: intermediate.*

Dropping bad rows hides problems; failing the job on one bad row blocks every good row behind it. The **quarantine
pattern** does neither: each row is checked against a list of rules, rows that pass go to silver, and rows that fail
go to a quarantine table together with the reasons. The medallion page describes exactly this: customer and
transaction data "is cleaned by dropping nulls and quarantining invalid records"
([medallion architecture](https://docs.databricks.com/aws/en/lakehouse/medallion)).

Three design choices matter:

1. **Collect every reason, not the first.** An array of failed rules tells the source team everything at once.
2. **Keep the raw values.** The typed value of `abc` is `NULL`; only the raw string tells you what was sent. Keep
   `_source_file` and `_ingest_ts` too, so the row can be traced and replayed.
3. **Make the split exhaustive.** Every bronze row must land in exactly one of the two tables. Check it with counts.

Here the validated stream is defined once and written twice, each write with its own checkpoint. Databricks
recommends "configuring a separate streaming write for each sink you want to update instead of using `foreachBatch`"
([Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
VALIDATED_SQL = """
WITH typed AS (
  SELECT
    order_id AS raw_order_id, customer_id AS raw_customer_id, order_ts AS raw_order_ts,
    amount AS raw_amount, currency AS raw_currency,
    try_cast(order_id AS INT)                          AS order_id,
    try_cast(customer_id AS INT)                       AS customer_id,
    coalesce(try_to_timestamp(order_ts),
             try_to_timestamp(order_ts, 'MM/dd/yyyy HH:mm')) AS order_ts,
    upper(trim(status))                                AS status,
    try_cast(amount AS DECIMAL(10,2))                  AS amount,
    nullif(upper(trim(currency)), '')                  AS currency,
    try_to_timestamp(updated_at)                       AS updated_at,
    _source_file, _ingest_ts
  FROM bronze_stream
)
SELECT *,
  filter(array(
    CASE WHEN order_id IS NULL THEN 'order_id missing or not an integer' END,
    CASE WHEN customer_id IS NULL THEN 'customer_id missing' END,
    CASE WHEN order_ts IS NULL THEN concat('order_ts not a timestamp: ', raw_order_ts) END,
    CASE WHEN amount IS NULL THEN concat('amount not a number: ', raw_amount) END,
    CASE WHEN amount < 0 THEN 'amount negative' END,
    CASE WHEN currency IS NULL OR currency NOT IN ('CAD', 'USD') THEN 'currency missing or unknown' END
  ), x -> x IS NOT NULL) AS dq_errors
FROM typed
"""
spark.readStream.table("bronze_orders").createOrReplaceTempView("bronze_stream")
validated = spark.sql(VALIDATED_SQL)

valid = (validated.where("size(dq_errors) = 0")
         .select("order_id", "customer_id", "order_ts", "status", "amount", "currency",
                 "updated_at", "_source_file", "_ingest_ts"))
invalid = (validated.where("size(dq_errors) > 0")
           .selectExpr("raw_order_id", "raw_customer_id", "raw_order_ts", "raw_amount",
                       "raw_currency", "dq_errors", "_source_file", "_ingest_ts"))

for df, table in [(valid, "silver_order_events"), (invalid, "quarantine_orders")]:
    (df.writeStream
       .option("checkpointLocation", f"{base}/checkpoints/{table}")
       .trigger(availableNow=True)
       .toTable(table)
       .awaitTermination())
```

Each `CASE` without an `ELSE` yields `NULL` when its rule passes, and `filter(..., x -> x IS NOT NULL)` keeps only the
messages of failed rules (higher-order functions are covered in chapter 18). Because the split is `size(dq_errors) = 0`
versus `> 0`, and `size` of an array is never `NULL` here, every row goes to exactly one side.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, customer_id, order_ts, status, amount, currency, updated_at
FROM silver_order_events ORDER BY order_id, updated_at;
SELECT raw_order_id, dq_errors, _source_file FROM quarantine_orders ORDER BY raw_order_id;
SELECT (SELECT count(*) FROM bronze_orders)       AS bronze_rows,
       (SELECT count(*) FROM silver_order_events) AS silver_rows,
       (SELECT count(*) FROM quarantine_orders)   AS quarantined_rows;
```

```text
+--------+-----------+-------------------+-------+------+--------+-------------------+
|order_id|customer_id|order_ts           |status |amount|currency|updated_at         |
+--------+-----------+-------------------+-------+------+--------+-------------------+
|1001    |7          |2026-03-01 10:15:00|PLACED |59.90 |CAD     |2026-03-01 10:15:00|
|1001    |7          |2026-03-01 10:15:00|PLACED |59.90 |CAD     |2026-03-01 10:15:00|
|1002    |8          |2026-03-01 11:00:00|PLACED |120.00|CAD     |2026-03-01 11:00:00|
|1002    |8          |2026-03-01 11:00:00|SHIPPED|120.00|CAD     |2026-03-02 09:00:00|
|1005    |7          |2026-03-01 13:05:00|PLACED |35.50 |USD     |2026-03-01 13:05:00|
|1008    |9          |2026-03-02 08:10:00|PLACED |42.00 |CAD     |2026-03-02 08:10:00|
+--------+-----------+-------------------+-------+------+--------+-------------------+

+------------+----------------------------------------------+----------------------+
|raw_order_id|dq_errors                                     |_source_file          |
+------------+----------------------------------------------+----------------------+
|1003        |[amount not a number: abc]                    |orders_2026-03-01.json|
|1004        |[customer_id missing]                         |orders_2026-03-01.json|
|1006        |[order_ts not a timestamp: not a date]        |orders_2026-03-01.json|
|1007        |[amount negative, currency missing or unknown]|orders_2026-03-01.json|
+------------+----------------------------------------------+----------------------+

+-----------+-----------+----------------+
|bronze_rows|silver_rows|quarantined_rows|
+-----------+-----------+----------------+
|10         |6          |4               |
+-----------+-----------+----------------+
```

10 = 6 + 4: nothing was lost. Order 1007 failed two rules and both are listed. The silver events still contain
duplicates (1001 twice, 1002 twice); that is the next section's job.

What happens to quarantined rows? Someone reads the reasons, the source is fixed (or a rule is corrected), and the
corrected records are sent again, so they arrive in bronze like any other event and flow through the same code. Do
not edit silver by hand.

!!! warning "The NULL hole in a split"
    Writing the split as `WHERE amount >= 0` for silver and `WHERE NOT (amount >= 0)` for quarantine loses every row
    whose amount is `NULL`: both conditions are `NULL`, so the row goes nowhere (Q8 shows a run). Build the list of
    errors first and split on its size, or wrap each condition in `coalesce(..., false)`.

In Lakeflow pipelines ([formerly Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) the same idea is expressed with expectations, and Databricks
documents a quarantine pattern for them; see chapter 14 and
[Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations).

!!! tip "In the interview"
    **"How do you handle bad records?"** I never silently drop them. Each record is checked against rules; valid
    ones go to silver, invalid ones go to a quarantine table with every failed rule, the raw values, the source file
    and the ingest time. I reconcile counts (bronze = silver + quarantine) on every run and alert when the quarantine
    rate jumps. In a Lakeflow pipeline ([formerly Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) I would use expectations for the same thing.

## 9.6 Deduplication

*Level: intermediate.*

Duplicates reach silver for two different reasons, and they need different fixes:

- **The same event delivered twice** (a retry, a file sent again). Both rows say the same thing.
- **Several versions of the same entity** (order 1002 was `PLACED`, then `SHIPPED`). Both rows are real; you want
  the latest one in a "current state" table, and all of them in an event table.

The generic SQL techniques are in the SQL course,
[Duplicates and incremental loads](../../databases/sql/22-Duplicates-and-Incremental-Loads.md) and
[ranking window functions](../../databases/sql/13-Window-Functions-Ranking.md). Here is what they do on the Red Rock
Supply events, plus one late event from a third file: a `PACKED` status for 1002 that happened at 08:00 on March 2
(before `SHIPPED` at 09:00) but was ingested on March 3.

### `dropDuplicates`: exact copies only

`dropDuplicates()` with no arguments compares every column. With a column list it keeps one row per combination,
and the Spark docs do not say which one
([DataFrame.dropDuplicates](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.dropDuplicates.html)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
events = spark.read.table("silver_order_events")
BUSINESS_COLS = ["order_id", "customer_id", "order_ts", "status", "amount", "currency", "updated_at"]
print("rows before:", events.count(), " after dropDuplicates():", events.dropDuplicates().count())
print("rows after dropDuplicates(BUSINESS_COLS):", events.dropDuplicates(BUSINESS_COLS).count())
events.dropDuplicates(["order_id"]).select("order_id", "status", "updated_at").orderBy("order_id").show()
```

```text
rows before: 7  after dropDuplicates(): 7
rows after dropDuplicates(BUSINESS_COLS): 6
+--------+------+-------------------+
|order_id|status|         updated_at|
+--------+------+-------------------+
|    1001|PLACED|2026-03-01 10:15:00|
|    1002|PLACED|2026-03-01 11:00:00|
|    1005|PLACED|2026-03-01 13:05:00|
|    1008|PLACED|2026-03-02 08:10:00|
+--------+------+-------------------+
```

`dropDuplicates()` removed nothing: the re-delivered 1001 has a different `_source_file` and `_ingest_ts`, so the
rows are not identical. Comparing only the business columns removes the copy. `dropDuplicates(["order_id"])` gives
one row per order, but for 1002 it happened to keep `PLACED`, the oldest status. Use it only when any row of the group
is acceptable.

On a stream, `dropDuplicates` keeps all seen keys as state across micro-batches unless you bound it with a watermark
(same Spark page; chapter 11 covers watermarks and `dropDuplicatesWithinWatermark`).

### Keep the latest: `row_number` and `QUALIFY`

To keep the newest row per key, number the rows inside each key from newest to oldest and keep number 1. Order by
**event time** (`updated_at`), and add a tie-breaker so the result is deterministic. The `row_number` reference says it
plainly: "If the order is not unique, the result is non-deterministic"
([row_number](https://docs.databricks.com/aws/en/sql/language-manual/functions/row_number)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql import Window, functions as F

w = Window.partitionBy("order_id").orderBy(F.col("updated_at").desc(), F.col("_ingest_ts").desc())
(events.withColumn("rn", F.row_number().over(w))
       .where("rn = 1").drop("rn")
       .select("order_id", "status", "updated_at", "_source_file").orderBy("order_id").show(truncate=False))
```

```text
+--------+-------+-------------------+----------------------+
|order_id|status |updated_at         |_source_file          |
+--------+-------+-------------------+----------------------+
|1001    |PLACED |2026-03-01 10:15:00|orders_2026-03-02.json|
|1002    |SHIPPED|2026-03-02 09:00:00|orders_2026-03-02.json|
|1005    |PLACED |2026-03-01 13:05:00|orders_2026-03-01.json|
|1008    |PLACED |2026-03-02 08:10:00|orders_2026-03-02.json|
+--------+-------+-------------------+----------------------+
```

In Databricks SQL, `QUALIFY` filters on a window function without a subquery
([QUALIFY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-qualify)):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, status, updated_at, _source_file
FROM silver_order_events
QUALIFY row_number() OVER (PARTITION BY order_id
                           ORDER BY updated_at DESC, _ingest_ts DESC) = 1
ORDER BY order_id
```

The output is the same four rows as above. Now the mistake: ordering by ingest time, "the row we loaded last".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, status, updated_at, _source_file
FROM silver_order_events
QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY _ingest_ts DESC) = 1
ORDER BY order_id
```

```text
+--------+------+-------------------+----------------------+
|order_id|status|updated_at         |_source_file          |
+--------+------+-------------------+----------------------+
|1001    |PLACED|2026-03-01 10:15:00|orders_2026-03-02.json|
|1002    |PACKED|2026-03-02 08:00:00|orders_2026-03-03.json|
|1005    |PLACED|2026-03-01 13:05:00|orders_2026-03-01.json|
|1008    |PLACED|2026-03-02 08:10:00|orders_2026-03-02.json|
+--------+------+-------------------+----------------------+
```

Order 1002 went back from `SHIPPED` to `PACKED`, because the late file was loaded last. Ingest time tells you when
you heard about something, not when it happened. Use it only as a tie-breaker.

When you only need a few columns of the latest row, `max_by(value, ordering)` does it without a window:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, max_by(status, updated_at) AS status, max(updated_at) AS updated_at
FROM silver_order_events GROUP BY order_id ORDER BY order_id
```

```text
+--------+-------+-------------------+
|order_id|status |updated_at         |
+--------+-------+-------------------+
|1001    |PLACED |2026-03-01 10:15:00|
|1002    |SHIPPED|2026-03-02 09:00:00|
|1005    |PLACED |2026-03-01 13:05:00|
|1008    |PLACED |2026-03-02 08:10:00|
+--------+-------+-------------------+
```

### Ties

When two events carry the same `updated_at`, `rank` gives both rank 1 (so "keep rank 1" keeps both), and
`row_number` picks one arbitrarily unless the ordering is unique. The right tie-breaker is a sequence number from the
source (a log position or change counter), here called `seq`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, status, updated_at, seq,
       rank()       OVER (PARTITION BY order_id ORDER BY updated_at DESC) AS rnk,
       row_number() OVER (PARTITION BY order_id ORDER BY updated_at DESC, seq DESC) AS rn
FROM VALUES (2001, 'PAID',    TIMESTAMP '2026-03-05 10:00:00', 41),
            (2001, 'SHIPPED', TIMESTAMP '2026-03-05 10:00:00', 42) AS v(order_id, status, updated_at, seq)
```

```text
+--------+-------+-------------------+---+---+---+
|order_id|status |updated_at         |seq|rnk|rn |
+--------+-------+-------------------+---+---+---+
|2001    |SHIPPED|2026-03-05 10:00:00|42 |1  |1  |
|2001    |PAID   |2026-03-05 10:00:00|41 |1  |2  |
+--------+-------+-------------------+---+---+---+
```

!!! tip "In the interview"
    **"How do you deduplicate and keep the latest record?"** `row_number() OVER (PARTITION BY key ORDER BY
    event_time DESC, tie_breaker DESC) = 1`, with `QUALIFY` in Databricks SQL or a `Window` in PySpark. Order by the
    event time from the source, never by ingest time, and make the order unique. `dropDuplicates` is for exact copies;
    with a subset of columns it keeps an unspecified row.

## 9.7 Late and out-of-order data in MERGE

*Level: intermediate.*

Deduplicating inside one batch is not enough. `silver_orders` keeps one row per order across all batches, and a late
event can arrive in a later batch than a newer one. A `MERGE` that blindly applies the incoming row lets old data
overwrite new data.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 280" role="img" aria-label="Three files arrive in order: PLACED, then SHIPPED, then a late PACKED event that happened before SHIPPED. A naive MERGE ends with PACKED; a guarded MERGE keeps SHIPPED">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="20" y="40" width="180" height="56" rx="6"/>
<rect x="230" y="40" width="180" height="56" rx="6"/>
<rect x="440" y="40" width="180" height="56" rx="6" stroke-dasharray="5 4"/>
<line x1="200" y1="68" x2="222" y2="68"/>
<line x1="410" y1="68" x2="432" y2="68"/>
<rect x="20" y="180" width="280" height="64" rx="6"/>
<rect x="320" y="180" width="300" height="64" rx="6"/>
<line x1="500" y1="96" x2="170" y2="172"/>
<line x1="530" y1="96" x2="470" y2="172"/>
</g>
<g fill="currentColor">
<polygon points="230,68 220,63 220,73"/>
<polygon points="440,68 430,63 430,73"/>
<polygon points="162,174 173,167 175,177"/>
<polygon points="468,180 465,169 475,171"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="320" y="24">order 1002, in the order the files were loaded</text>
<text x="110" y="64">file 1: PLACED</text>
<text x="110" y="84">updated_at Mar 1 11:00</text>
<text x="320" y="64">file 2: SHIPPED</text>
<text x="320" y="84">updated_at Mar 2 09:00</text>
<text x="530" y="64">file 3 (late): PACKED</text>
<text x="530" y="84">updated_at Mar 2 08:00</text>
<text x="160" y="205">Naive: WHEN MATCHED UPDATE</text>
<text x="160" y="228">status = PACKED (wrong)</text>
<text x="470" y="205">Guarded: s.updated_at &gt; t.updated_at</text>
<text x="470" y="228">08:00 &gt; 09:00 is false: stays SHIPPED</text>
</g>
</svg>
<figcaption>Figure 9.2. The out-of-order guard. Arrival order and event order differ; only the event time in the
WHEN MATCHED condition protects the newer state.</figcaption>
</figure>

Batch A (the latest event per order from the first two files) loads `silver_orders`. A shallow clone keeps an
identical copy for the naive version. Then batch B arrives: the late `PACKED` event for 1002 and a genuinely newer
`SHIPPED` event for 1005.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- naive, applied to the clone
MERGE INTO silver_orders_naive AS t
USING batch_b AS s
ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

-- guarded, applied to silver_orders
MERGE INTO silver_orders AS t
USING batch_b AS s
ON t.order_id = s.order_id
WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

```text
+--------+------------+-------------------+--------------+-------------------+
|order_id|naive_status|naive_updated_at   |guarded_status|guarded_updated_at |
+--------+------------+-------------------+--------------+-------------------+
|1001    |PLACED      |2026-03-01 10:15:00|PLACED        |2026-03-01 10:15:00|
|1002    |PACKED      |2026-03-02 08:00:00|SHIPPED       |2026-03-02 09:00:00|
|1005    |SHIPPED     |2026-03-03 10:00:00|SHIPPED       |2026-03-03 10:00:00|
|1008    |PLACED      |2026-03-02 08:10:00|PLACED        |2026-03-02 08:10:00|
+--------+------------+-------------------+--------------+-------------------+
```

The guard is one condition on `WHEN MATCHED`. The `MERGE INTO` reference says that if no `WHEN MATCHED` condition is
true for a matched pair, "the target row is left unchanged"
([MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into)); the reference's own example
is `WHEN MATCHED AND target.updated_at < source.updated_at THEN UPDATE SET *`.

The same guarded merge with the Python `DeltaTable` builder, on a batch D that cancels 1001 (newer) and resends an old
`PLACED` for 1002 (older):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from delta.tables import DeltaTable

(DeltaTable.forName(spark, "silver_orders").alias("t")
   .merge(spark.table("batch_d").alias("s"), "t.order_id = s.order_id")
   .whenMatchedUpdateAll(condition="s.updated_at > t.updated_at")
   .whenNotMatchedInsertAll()
   .execute())
```

```text
+--------+---------+-------------------+
|order_id|status   |updated_at         |
+--------+---------+-------------------+
|1001    |CANCELLED|2026-03-04 12:00:00|
|1002    |SHIPPED  |2026-03-02 09:00:00|
|1005    |SHIPPED  |2026-03-03 10:00:00|
|1008    |SHIPPED  |2026-03-04 09:00:00|
+--------+---------+-------------------+
```

(1008 is `SHIPPED` because of batch C, coming up next.)

### Why `>` and not `>=`

With `>=`, a rerun of the same batch matches every row with equal timestamps and rewrites it with identical values.
The table looks the same, but the files are rewritten and, if Change Data Feed is on, every such row produces an
`update_preimage` / `update_postimage` pair that downstream consumers have to process. Section 9.11 shows this in a
real run. Equal timestamps on genuinely different data are a tie, and ties need a sequence column, not `>=`.

!!! warning "What the guard does not do"
    The guard keeps the newest state per key. It does not record history and it does not handle a late event that
    should be inserted *between* two history rows. For that you need SCD Type 2 (section 9.10) or `AUTO CDC`
    ([formerly `APPLY CHANGES`](https://docs.databricks.com/aws/en/ldp/cdc)) in a Lakeflow pipeline, which Databricks recommends "to ensure that out of order
    records are handled correctly when processing CDC feeds"
    ([Upsert into a Delta Lake table using merge](https://docs.databricks.com/aws/en/delta/merge)).

### The "multiple source rows matched" error

Batch C contains two events for order 1008 (`PAID`, then `SHIPPED`):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
MERGE INTO silver_orders AS t
USING batch_c AS s
ON t.order_id = s.order_id
WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

```text
MERGE error: [DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE] Cannot perform Merge as multiple source rows matched and attempted to modify the same target row in the Delta table in possibly conflicting ways. By SQL semantics of Merge, when multiple source rows match on the same target row, the result may be ambiguous as it is unclear
```

Two source rows want to update the same target row, and SQL `MERGE` semantics give no rule for which one wins, so
Delta refuses. The failed `MERGE` changes nothing (no new table version appears in the history below). The fix is to
make the source unique per key before merging, keeping the latest event:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
MERGE INTO silver_orders AS t
USING (
  SELECT * FROM batch_c
  QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY updated_at DESC) = 1
) AS s
ON t.order_id = s.order_id
WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

```text
+--------+-------+-------------------+
|order_id|status |updated_at         |
+--------+-------+-------------------+
|1001    |PLACED |2026-03-01 10:15:00|
|1002    |SHIPPED|2026-03-02 09:00:00|
|1005    |SHIPPED|2026-03-03 10:00:00|
|1008    |SHIPPED|2026-03-04 09:00:00|
+--------+-------+-------------------+
```

Two details from the docs that interviewers like:

- **Which conditions count.** "In Databricks Runtime 16.0 and above, `MERGE` evaluates conditions specified in the
  `WHEN MATCHED` and `ON` clauses to determine duplicate matches. In Databricks Runtime 15.4 LTS and below, `MERGE`
  operations only consider conditions specified in the `ON` clause"
  ([Upsert into a Delta Lake table using merge](https://docs.databricks.com/aws/en/delta/merge)). Open-source Delta
  4.4.1 behaves like the older rule: a test where only one of two source rows passed the `WHEN MATCHED` condition
  still failed here (`src/ch09/s8_practice.out`). Do not rely on conditions to save you; deduplicate the source.
- **Deletes are exempt.** "Databricks allows multiple matches when matches are unconditionally deleted"
  ([MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into)). The same test with
  `WHEN MATCHED THEN DELETE` succeeded here too.

One source row matching *many* target rows is not an error. That is allowed, and section 9.10 shows how it corrupts
an SCD Type 2 table when the `ON` clause is too loose.

!!! tip "In the interview"
    **"How do you stop late data from overwriting newer data?"** I deduplicate the batch to the latest event per key
    by event time, then `MERGE` with `WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE`. Strictly greater, so
    a rerun is a no-op. If I need history or must slot a late event between existing versions, I use SCD Type 2, or
    `AUTO CDC` ([formerly `APPLY CHANGES`](https://docs.databricks.com/aws/en/ldp/cdc)) with `SEQUENCE BY` in a Lakeflow pipeline ([formerly Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)).

## 9.8 Idempotency: prove a rerun changes nothing

*Level: intermediate.*

A load is **idempotent** when running it twice on the same input leaves the table exactly as running it once. Jobs
get retried after failures, people rerun yesterday's job by hand, and a stream restarts from its last checkpoint and
replays a micro-batch. Databricks says it directly for streams: verify that a `merge` inside `foreachBatch` is
idempotent, "otherwise, restarts of the streaming query can apply the operation on the same batch of data multiple
times" ([Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake)).

The test is simple: remember the table version, run the same batch again, and compare the table with that version
using time travel.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
v_before = sql("DESCRIBE HISTORY silver_orders").agg({"version": "max"}).first()[0]
sql(GUARDED_MERGE.format(target="silver_orders", source=FIXED_SOURCE))     # batch C again
sql("DESCRIBE HISTORY silver_orders").orderBy("version").selectExpr(
    "version", "operation",
    "operationMetrics['numTargetRowsInserted'] AS inserted",
    "operationMetrics['numTargetRowsUpdated'] AS updated",
    "operationMetrics['numSourceRows'] AS source_rows").show()
show(f"""SELECT count(*) AS rows_that_differ FROM (
           (SELECT * FROM silver_orders EXCEPT ALL SELECT * FROM silver_orders VERSION AS OF {v_before})
           UNION ALL
           (SELECT * FROM silver_orders VERSION AS OF {v_before} EXCEPT ALL SELECT * FROM silver_orders))""")
```

```text
+-------+------------+--------+-------+-----------+
|version|   operation|inserted|updated|source_rows|
+-------+------------+--------+-------+-----------+
|      0|CREATE TABLE|    NULL|   NULL|       NULL|
|      1|       MERGE|       4|      0|          4|
|      2|       MERGE|       0|      1|          2|
|      3|       MERGE|       0|      1|          1|
|      4|       MERGE|       0|      0|          1|
+-------+------------+--------+-------+-----------+

+----------------+
|rows_that_differ|
+----------------+
|0               |
+----------------+
```

Version 4 is the rerun: a commit was recorded, but it inserted and updated nothing, and the data equals version 3.
The batch C failure from section 9.7 left no version at all. Compare with a plain append of batch A, run twice:

```text
after run 1: 4 rows
after run 2: 8 rows
```

(from the same script, `src/ch09/s5_late_merge.out`). What makes a silver load idempotent:

| Ingredient | Why |
| --- | --- |
| `MERGE` on a business key instead of append | a replayed row matches itself instead of being added again |
| source deduplicated per key | no "multiple source rows matched", and the same winner every time |
| strict `>` guard on event time | equal rows are not rewritten; older rows never win |
| deterministic logic (no `current_timestamp()` in keys or guards) | the same input gives the same output |
| streaming checkpoints | a restarted stream resumes where it stopped |

For plain appends inside `foreachBatch`, Delta offers the `txnAppId` and `txnVersion` writer options so a replayed
batch is recognized and skipped; Databricks warns that a new checkpoint needs a new `txnAppId`
([Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake);
chapter 11 shows it).

!!! tip "In the interview"
    **"The table has duplicates after a rerun. Why?"** The load appends instead of merging on a key, or the merge key
    is not the real business key, or the source batch was not deduplicated, or a new checkpoint made the stream
    reprocess everything. I prove idempotency by rerunning the same batch and comparing the table with the previous
    version using `VERSION AS OF` and `EXCEPT ALL`.

## 9.9 SCD Type 1 with MERGE

*Level: intermediate.*

A **slowly changing dimension** (SCD) is a table of things that change now and then, like customers who move. **Type
1** keeps only the current values: an update overwrites. **Type 2** keeps history: an update closes the old row and
adds a new one. The modeling background is in the SQL course,
[Data modelling](../../databases/sql/19-Data-Modelling.md).

Type 1 is the guarded `MERGE` of section 9.7, applied to customers. Four loads arrive (all from
`src/ch09/ch09_customers.py`): load 1 is the first export; in load 2 Ava (7) moves to Banff, Ben (8) is re-sent
unchanged and Dev (10) is new; load 3 moves Ava to Canmore, carries a stale Ava record dated February that arrived
late, and changes Chloe's (9) email; load 4 holds only a stale Ben record from December 2025.

Each load is first reduced to one row per customer (the view `customer_updates_latest`, using the `QUALIFY` of
section 9.6), then merged:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver_customers (
  customer_id INT, name STRING, email STRING, city STRING, country STRING, updated_at TIMESTAMP)
USING DELTA
TBLPROPERTIES (delta.enableChangeDataFeed = true);   -- used in section 9.11

MERGE INTO silver_customers AS t
USING customer_updates_latest AS s
ON t.customer_id = s.customer_id
WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

After load 2 and after load 4:

```text
+-----------+---------+---------------------+-------------------+
|customer_id|city     |email                |updated_at         |
+-----------+---------+---------------------+-------------------+
|7          |Banff    |ava.chen@example.com |2026-03-01 10:00:00|
|8          |Denver   |ben.ortiz@example.com|2026-01-10 14:30:00|
|9          |Moab     |chloe.m@example.com  |2026-01-20 08:00:00|
|10         |Vancouver|dev.patel@example.com|2026-03-02 11:00:00|
+-----------+---------+---------------------+-------------------+

+-----------+---------+------------------------+-------------------+
|customer_id|city     |email                   |updated_at         |
+-----------+---------+------------------------+-------------------+
|7          |Canmore  |ava.chen@example.com    |2026-04-10 16:00:00|
|8          |Denver   |ben.ortiz@example.com   |2026-01-10 14:30:00|
|9          |Moab     |chloe.martin@example.com|2026-04-12 09:30:00|
|10         |Vancouver|dev.patel@example.com   |2026-03-02 11:00:00|
+-----------+---------+------------------------+-------------------+
```

The stale February Ava record never reached the `MERGE` (the in-batch deduplication kept Canmore), and the stale
December Ben record in load 4 was matched but failed the guard, so Ben stays in Denver. Ben's unchanged re-send in
load 2 also did nothing, because its `updated_at` was equal, not greater.

The PySpark form is the `DeltaTable` builder shown in section 9.7 with `"t.customer_id = s.customer_id"` as the
condition.

## 9.10 SCD Type 2 with MERGE

*Level: expert.*

A Type 2 customer table has one row per version of a customer, with three extra columns: `valid_from` (when this
version became true), `valid_to` (when it stopped being true, `NULL` while current; some teams use a far-future date
such as `9999-12-31` instead) and `is_current`. When Ava moves, two things must happen in one atomic step: her current
row is closed (`is_current = false`, `valid_to = ` the change time), and a new current row is inserted.

One `MERGE` cannot both update and insert for the same source row: a source row either matches (update) or does not
(insert). The classic trick, shown in the Delta Lake documentation's SCD Type 2 example
([Delta Lake: table deletes, updates, and merges](https://github.com/delta-io/delta/blob/master/docs/src/content/docs/delta-update.mdx)),
is to feed every changed customer **twice**:

1. once with a `merge_key` equal to `customer_id`, so it matches the current row and closes it (new customers do not
   match and are inserted);
2. once more with `merge_key = NULL`. `t.customer_id = NULL` is never true, so this copy never matches and is inserted
   as the new current row.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 280" role="img" aria-label="The merge key pattern: copy 1 of each row has merge_key equal to customer_id and closes the current row or inserts a new customer; copy 2 of each changed row has a NULL merge key, never matches, and is inserted as the new current row">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="20" y="40" width="260" height="70" rx="6"/>
<rect x="20" y="180" width="260" height="70" rx="6"/>
<rect x="360" y="40" width="260" height="70" rx="6"/>
<rect x="360" y="180" width="260" height="70" rx="6"/>
<line x1="280" y1="75" x2="352" y2="75"/>
<line x1="280" y1="215" x2="352" y2="215"/>
<line x1="280" y1="100" x2="354" y2="178" stroke-dasharray="5 4"/>
</g>
<g fill="currentColor">
<polygon points="360,75 350,70 350,80"/>
<polygon points="360,215 350,210 350,220"/>
<polygon points="359,184 348,180 355,172"/>
</g>
<g fill="currentColor" font-size="14" text-anchor="middle">
<text x="150" y="66">copy 1: merge_key = id</text>
<text x="150" y="206">copy 2: merge_key = NULL</text>
<text x="490" y="66">matches current row</text>
<text x="490" y="206">never matches</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="150" y="90">every incoming customer</text>
<text x="150" y="230">changed customers only</text>
<text x="490" y="90">UPDATE: is_current = false,</text>
<text x="490" y="106">valid_to = s.updated_at</text>
<text x="490" y="230">INSERT the new current row</text>
<text x="312" y="150" text-anchor="end">new customer:</text>
<text x="312" y="166" text-anchor="end">no match</text>
</g>
</svg>
<figcaption>Figure 9.3. The staged source of an SCD Type 2 MERGE. The NULL-key copy is what lets one MERGE both close
the old version and insert the new one.</figcaption>
</figure>

The full statement (the script fills in the table name and the `ON` extra):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver_customers_scd2 (
  customer_id INT, name STRING, email STRING, city STRING, country STRING,
  valid_from TIMESTAMP, valid_to TIMESTAMP, is_current BOOLEAN)
USING DELTA;

MERGE INTO silver_customers_scd2 AS t
USING (
  -- (1) every incoming row, keyed by customer_id
  SELECT u.customer_id AS merge_key, u.* FROM customer_updates_latest u
  UNION ALL
  -- (2) a second copy of each CHANGED customer with a NULL key
  SELECT NULL AS merge_key, u.*
  FROM customer_updates_latest u
  JOIN silver_customers_scd2 c ON c.customer_id = u.customer_id AND c.is_current
  WHERE u.updated_at > c.valid_from
    AND NOT (c.name <=> u.name AND c.email <=> u.email AND c.city <=> u.city AND c.country <=> u.country)
) AS s
ON t.customer_id = s.merge_key AND t.is_current
WHEN MATCHED AND s.updated_at > t.valid_from
     AND NOT (t.name <=> s.name AND t.email <=> s.email AND t.city <=> s.city AND t.country <=> s.country)
  THEN UPDATE SET is_current = false, valid_to = s.updated_at
WHEN NOT MATCHED
  THEN INSERT (customer_id, name, email, city, country, valid_from, valid_to, is_current)
       VALUES (s.customer_id, s.name, s.email, s.city, s.country, s.updated_at, NULL, true);
```

Points worth saying out loud:

- `AND t.is_current` in the `ON` clause makes each customer match at most one target row, the current one.
- `<=>` is the null-safe equality operator: `NULL <=> NULL` is true. With `<>`, a change from `NULL` to a value
  gives `NULL`, which counts as "no change" (Q31 shows the run).
- `s.updated_at > t.valid_from` is the out-of-order guard of section 9.7, applied to SCD Type 2.
- The source must still be unique per `customer_id` for copy (1), which is why `customer_updates_latest` is used.

Here is the staged source for load 3, then the table after each load:

```text
+---------+-----------+-------+------------------------+-------------------+
|merge_key|customer_id|city   |email                   |updated_at         |
+---------+-----------+-------+------------------------+-------------------+
|7        |7          |Canmore|ava.chen@example.com    |2026-04-10 16:00:00|
|9        |9          |Moab   |chloe.martin@example.com|2026-04-12 09:30:00|
|NULL     |7          |Canmore|ava.chen@example.com    |2026-04-10 16:00:00|
|NULL     |9          |Moab   |chloe.martin@example.com|2026-04-12 09:30:00|
+---------+-----------+-------+------------------------+-------------------+
```

After load 1:

```text
+-----------+-------+---------------------+-------------------+--------+----------+
|customer_id|city   |email                |valid_from         |valid_to|is_current|
+-----------+-------+---------------------+-------------------+--------+----------+
|7          |Calgary|ava.chen@example.com |2026-01-05 09:00:00|NULL    |true      |
|8          |Denver |ben.ortiz@example.com|2026-01-10 14:30:00|NULL    |true      |
|9          |Moab   |chloe.m@example.com  |2026-01-20 08:00:00|NULL    |true      |
+-----------+-------+---------------------+-------------------+--------+----------+
```

After load 2 (Ava moved, Ben unchanged, Dev new):

```text
+-----------+---------+---------------------+-------------------+-------------------+----------+
|customer_id|city     |email                |valid_from         |valid_to           |is_current|
+-----------+---------+---------------------+-------------------+-------------------+----------+
|7          |Calgary  |ava.chen@example.com |2026-01-05 09:00:00|2026-03-01 10:00:00|false     |
|7          |Banff    |ava.chen@example.com |2026-03-01 10:00:00|NULL               |true      |
|8          |Denver   |ben.ortiz@example.com|2026-01-10 14:30:00|NULL               |true      |
|9          |Moab     |chloe.m@example.com  |2026-01-20 08:00:00|NULL               |true      |
|10         |Vancouver|dev.patel@example.com|2026-03-02 11:00:00|NULL               |true      |
+-----------+---------+---------------------+-------------------+-------------------+----------+
```

After load 3 (Ava moved again, Chloe's email changed, the stale Ava record was dropped by the in-batch dedup):

```text
+-----------+---------+------------------------+-------------------+-------------------+----------+
|customer_id|city     |email                   |valid_from         |valid_to           |is_current|
+-----------+---------+------------------------+-------------------+-------------------+----------+
|7          |Calgary  |ava.chen@example.com    |2026-01-05 09:00:00|2026-03-01 10:00:00|false     |
|7          |Banff    |ava.chen@example.com    |2026-03-01 10:00:00|2026-04-10 16:00:00|false     |
|7          |Canmore  |ava.chen@example.com    |2026-04-10 16:00:00|NULL               |true      |
|8          |Denver   |ben.ortiz@example.com   |2026-01-10 14:30:00|NULL               |true      |
|9          |Moab     |chloe.m@example.com     |2026-01-20 08:00:00|2026-04-12 09:30:00|false     |
|9          |Moab     |chloe.martin@example.com|2026-04-12 09:30:00|NULL               |true      |
|10         |Vancouver|dev.patel@example.com   |2026-03-02 11:00:00|NULL               |true      |
+-----------+---------+------------------------+-------------------+-------------------+----------+
```

Load 4 (the stale December Ben record) left the table exactly as above.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 260" role="img" aria-label="Timeline of customer 7: before load 3 Calgary from January 5 to March 1 and Banff open-ended; after load 3 Banff is closed on April 10 and Canmore is the open current row">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="114" y="40" width="190" height="34" rx="4"/>
<rect x="304" y="40" width="316" height="34" rx="4" stroke-dasharray="5 4"/>
<rect x="114" y="130" width="190" height="34" rx="4"/>
<rect x="304" y="130" width="138" height="34" rx="4"/>
<rect x="442" y="130" width="178" height="34" rx="4" stroke-dasharray="5 4"/>
<line x1="100" y1="215" x2="625" y2="215"/>
<line x1="100" y1="210" x2="100" y2="220"/>
<line x1="207" y1="210" x2="207" y2="220"/>
<line x1="304" y1="210" x2="304" y2="220"/>
<line x1="410" y1="210" x2="410" y2="220"/>
<line x1="514" y1="210" x2="514" y2="220"/>
</g>
<g fill="currentColor" font-size="13">
<text x="10" y="62">before</text>
<text x="10" y="80">load 3</text>
<text x="10" y="152">after</text>
<text x="10" y="170">load 3</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="209" y="62">Calgary</text>
<text x="462" y="62">Banff (is_current, valid_to NULL)</text>
<text x="209" y="152">Calgary</text>
<text x="373" y="152">Banff</text>
<text x="531" y="152">Canmore (is_current)</text>
<text x="100" y="238">Jan 1</text>
<text x="207" y="238">Feb 1</text>
<text x="304" y="238">Mar 1</text>
<text x="410" y="238">Apr 1</text>
<text x="514" y="238">May 1</text>
<text x="442" y="190">Apr 10: Banff closed, Canmore opened</text>
</g>
</svg>
<figcaption>Figure 9.4. Customer 7 (Ava) in silver_customers_scd2 before and after load 3. Dashed bars are open
(valid_to NULL, is_current true). Each version's valid_to equals the next version's valid_from, so there are no gaps
or overlaps.</figcaption>
</figure>

### Rerun and as-of queries

Rerunning load 3 must change nothing:

```text
+-------+------------+--------+-------+
|version|   operation|inserted|updated|
+-------+------------+--------+-------+
|      0|CREATE TABLE|    NULL|   NULL|
|      1|       MERGE|       3|      0|
|      2|       MERGE|       2|      1|
|      3|       MERGE|       2|      2|
|      4|       MERGE|       0|      0|
|      5|       MERGE|       0|      0|
+-------+------------+--------+-------+

+----------------+
|rows_that_differ|
+----------------+
|0               |
+----------------+
```

Version 2 inserted two rows (Ava's new Banff row and Dev) and updated one (closed Calgary). Version 3 inserted two and
closed two. Versions 4 (load 4) and 5 (load 3 again) touched nothing. Without the change check and the
`updated_at > valid_from` guard, the rerun would have closed Ava's Canmore row and opened an identical one.

The point of Type 2 is answering "what was true then". Where did each customer live on March 15?

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT customer_id, city FROM silver_customers_scd2
WHERE valid_from <= TIMESTAMP'2026-03-15 00:00:00'
  AND (valid_to IS NULL OR valid_to > TIMESTAMP'2026-03-15 00:00:00')
ORDER BY customer_id
```

```text
+-----------+---------+
|customer_id|city     |
+-----------+---------+
|7          |Banff    |
|8          |Denver   |
|9          |Moab     |
|10         |Vancouver|
+-----------+---------+
```

The interval is half-open: `valid_from` included, `valid_to` excluded, so a moment equal to a change time belongs to
exactly one version. Gold fact tables join to the version that was current at the order time this way (chapter 10).

### The bug: a loose `ON` clause

Drop `AND t.is_current` from the `ON` clause and Ava moves to Jasper:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- same MERGE, but: ON t.customer_id = s.merge_key
```

```text
+-----------+-------+-------------------+-------------------+----------+
|customer_id|city   |valid_from         |valid_to           |is_current|
+-----------+-------+-------------------+-------------------+----------+
|7          |Calgary|2026-01-05 09:00:00|2026-05-01 08:00:00|false     |
|7          |Banff  |2026-03-01 10:00:00|2026-05-01 08:00:00|false     |
|7          |Canmore|2026-04-10 16:00:00|2026-05-01 08:00:00|false     |
|7          |Jasper |2026-05-01 08:00:00|NULL               |true      |
+-----------+-------+-------------------+-------------------+----------+
```

No error: one source row may match many target rows. But every historical row was "closed" again and history now
says Ava lived in Calgary until May. The as-of query for March 15 would return three cities for her.

!!! warning "Limits of the hand-written Type 2 MERGE"
    This `MERGE` assumes changes arrive in order per customer. A late change dated between two existing versions is
    ignored (the guard rejects it), not slotted into history. Deletes are not handled. Handling both correctly is
    what `AUTO CDC` ([formerly `APPLY CHANGES`](https://docs.databricks.com/aws/en/ldp/cdc)) does with `SEQUENCE BY` and `STORED AS SCD TYPE 2` in Lakeflow
    pipelines ([formerly Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)); see chapter 14 and
    [The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc). That page also says the `AUTO CDC` APIs are not
    supported by open-source Apache Spark Declarative Pipelines, so it cannot be run here.

!!! tip "In the interview"
    **"Write an SCD Type 2 MERGE."** Stage the source as a union: every row with `merge_key = customer_id`, plus a
    second copy of each changed row with `merge_key = NULL`. `MERGE ... ON t.customer_id = s.merge_key AND
    t.is_current`; when matched and changed, set `is_current = false, valid_to = s.updated_at`; when not matched,
    insert with `valid_from = s.updated_at, valid_to = NULL, is_current = true`. Detect changes with `<=>`, guard with
    `s.updated_at > t.valid_from`, and deduplicate the source first. In a Lakeflow pipeline ([formerly Delta Live
    Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) I would use `AUTO CDC ... STORED AS SCD TYPE 2` ([formerly `APPLY CHANGES`](https://docs.databricks.com/aws/en/ldp/cdc)) instead.

## 9.11 Change Data Feed: passing changes on from silver

*Level: expert.*

Gold tables built from silver have the same problem silver had with bronze, made worse: silver is updated and
deleted, not only appended, so a plain stream from it fails (section 9.2), and re-reading the whole table every run
does not scale. **Change Data Feed** (CDF) records row-level changes between versions of a Delta table: each change
row carries the row data plus metadata saying whether it was inserted, updated or deleted
([Use change data feed](https://docs.databricks.com/aws/en/delta/delta-change-data-feed)).

### Two kinds of CDF on Databricks

The CDF page (last updated Oct 9, 2026) describes two approaches:

- **Legacy change data feed** materializes changes during writes, works only on Delta tables, and must be turned on
  per table with the table property `delta.enableChangeDataFeed = true` (in `CREATE TABLE ... TBLPROPERTIES` or
  `ALTER TABLE ... SET TBLPROPERTIES`). This is what open-source Delta has and what runs here.
- **Automatic change data feed** computes changes at query time from row tracking (Delta) or row lineage (Iceberg v3)
  and needs no per-table setting. It requires Databricks Runtime 19 or above and a Unity Catalog table (a managed Delta
  table with row tracking enabled or Iceberg v3, or an external Delta table with row tracking enabled). Only Databricks
  readers can query it for Delta tables. Databricks recommends migrating to it; you cannot use both on one table, and
  migrating means unsetting `delta.enableChangeDataFeed`.

Both use the same reading APIs: `table_changes()` in SQL and the `readChangeFeed` option in Python.

### What a change row looks like

Besides the table's columns, the feed has three metadata columns: `_change_type` (`insert`, `update_preimage`,
`update_postimage`, `delete`; preimage is the row before an update, postimage after), `_commit_version` and
`_commit_timestamp`. A table that already has columns with those names cannot use CDF.

`silver_customers` from section 9.9 was created with `delta.enableChangeDataFeed = true`. Its history after the four
loads, a `>=` rerun and a `>` rerun (coming up), a newer record for Ben and a GDPR delete of Chloe:

```text
+-------+------------+
|version|   operation|
+-------+------------+
|      0|CREATE TABLE|
|      1|       MERGE|
|      2|       MERGE|
|      3|       MERGE|
|      4|       MERGE|
|      5|       MERGE|
|      6|       MERGE|
|      7|       MERGE|
|      8|      DELETE|
+-------+------------+
```

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT customer_id, city, email, _change_type, _commit_version
FROM table_changes('silver_customers', 2, 4)
ORDER BY _commit_version, customer_id, _change_type
```

```text
+-----------+---------+------------------------+----------------+---------------+
|customer_id|city     |email                   |_change_type    |_commit_version|
+-----------+---------+------------------------+----------------+---------------+
|7          |Banff    |ava.chen@example.com    |update_postimage|2              |
|7          |Calgary  |ava.chen@example.com    |update_preimage |2              |
|10         |Vancouver|dev.patel@example.com   |insert          |2              |
|7          |Canmore  |ava.chen@example.com    |update_postimage|3              |
|7          |Banff    |ava.chen@example.com    |update_preimage |3              |
|9          |Moab     |chloe.martin@example.com|update_postimage|3              |
|9          |Moab     |chloe.m@example.com     |update_preimage |3              |
+-----------+---------+------------------------+----------------+---------------+
```

Version 4 (the stale Ben record) produced no change rows: the guard stopped it. Start and end versions are inclusive,
and a batch read needs a starting version; timestamps can be given instead as strings
([Use change data feed](https://docs.databricks.com/aws/en/delta/delta-change-data-feed),
[table_changes](https://docs.databricks.com/aws/en/sql/language-manual/functions/table_changes)). The DataFrame
reader:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
(spark.read.option("readChangeFeed", "true")
   .option("startingVersion", 7).option("endingVersion", 8)
   .table("silver_customers")
   .select("customer_id", "city", "_change_type", "_commit_version", "_commit_timestamp")
   .orderBy("_commit_version", "customer_id", "_change_type").show(truncate=False))
```

```text
+-----------+-------+----------------+---------------+-----------------------+
|customer_id|city   |_change_type    |_commit_version|_commit_timestamp      |
+-----------+-------+----------------+---------------+-----------------------+
|8          |Boulder|update_postimage|7              |2026-11-11 05:37:17.312|
|8          |Denver |update_preimage |7              |2026-11-11 05:37:17.312|
|9          |Moab   |delete          |8              |2026-11-11 05:37:23.916|
+-----------+-------+----------------+---------------+-----------------------+
```

Note that `_commit_timestamp` is when the change was committed to silver, not when it happened at the source. For
business time, use `updated_at`.

### The `>=` guard, seen in the feed

Section 9.7 claimed that `>=` produces spurious updates. Rerunning load 3 with `>=` (version 5) and then with `>`
(version 6):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT customer_id, city, email, _change_type, _commit_version
FROM table_changes('silver_customers', 5)        -- run right after the '>=' rerun
ORDER BY customer_id, _change_type
```

```text
+-----------+-------+------------------------+----------------+---------------+
|customer_id|city   |email                   |_change_type    |_commit_version|
+-----------+-------+------------------------+----------------+---------------+
|7          |Canmore|ava.chen@example.com    |update_postimage|5              |
|7          |Canmore|ava.chen@example.com    |update_preimage |5              |
|9          |Moab   |chloe.martin@example.com|update_postimage|5              |
|9          |Moab   |chloe.martin@example.com|update_preimage |5              |
+-----------+-------+------------------------+----------------+---------------+

-- the same rerun with '>' commits a MERGE with no change rows:
change rows in version 6 : 0
```

Pre- and postimages are identical: nothing changed, but every downstream consumer receives two updates.

### Propagating changes downstream

Databricks recommends combining CDF with Structured Streaming, because then the stream tracks which versions it has
processed. When such a stream first starts, it returns the current snapshot of the table as `insert` rows, then later
changes; `startingVersion` skips the snapshot when the target already has it
([Use change data feed](https://docs.databricks.com/aws/en/delta/delta-change-data-feed)).

Here a small downstream table, `gold_customer_directory`, is kept in sync with `foreachBatch` and `MERGE`. Inside each
micro-batch: drop the preimages, keep the last change per key, delete on `delete`, upsert otherwise.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def apply_changes(batch_df, batch_id):
    batch_df.createOrReplaceTempView("cdf_batch")
    batch_df.sparkSession.sql("""
        MERGE INTO gold_customer_directory AS g
        USING (
          SELECT * FROM cdf_batch
          WHERE _change_type IN ('insert', 'update_postimage', 'delete')
          QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY _commit_version DESC) = 1
        ) AS c
        ON g.customer_id = c.customer_id
        WHEN MATCHED AND c._change_type = 'delete' THEN DELETE
        WHEN MATCHED THEN UPDATE SET name = c.name, city = c.city, country = c.country
        WHEN NOT MATCHED AND c._change_type != 'delete' THEN
          INSERT (customer_id, name, city, country) VALUES (c.customer_id, c.name, c.city, c.country)
    """)
    print(f"   micro-batch {batch_id}: {batch_df.count()} change rows")

def propagate():
    (spark.readStream
        .option("readChangeFeed", "true")
        .table("silver_customers")
        .writeStream
        .foreachBatch(apply_changes)
        .option("checkpointLocation", f"{base}/checkpoints/gold_customer_directory")
        .trigger(availableNow=True)
        .start()
        .awaitTermination())

propagate()          # first start: the snapshot as inserts
# ... Ben moves to Boulder (version 7), Chloe is deleted (version 8) ...
propagate()          # only versions 7 and 8
```

```text
   micro-batch 0: 4 change rows
+-----------+------------+---------+-------+
|customer_id|name        |city     |country|
+-----------+------------+---------+-------+
|7          |Ava Chen    |Canmore  |CA     |
|8          |Ben Ortiz   |Denver   |US     |
|9          |Chloe Martin|Moab     |US     |
|10         |Dev Patel   |Vancouver|CA     |
+-----------+------------+---------+-------+

   micro-batch 1: 3 change rows
+-----------+---------+---------+-------+
|customer_id|name     |city     |country|
+-----------+---------+---------+-------+
|7          |Ava Chen |Canmore  |CA     |
|8          |Ben Ortiz|Boulder  |US     |
|10         |Dev Patel|Vancouver|CA     |
+-----------+---------+---------+-------+
```

The second run read only the three change rows of versions 7 and 8, applied Ben's move and Chloe's delete, and
nothing else. This merge is idempotent for the same reasons as in section 9.8, which matters because a restarted
stream can replay a micro-batch.

On Databricks the stream would read `shop.silver.customers` and write `shop.gold.customer_directory` (or a gold table
maintained by a Lakeflow pipeline, chapter 13). For SCD processing of a change feed, Databricks points to `AUTO CDC`
([formerly `APPLY CHANGES`](https://docs.databricks.com/aws/en/ldp/cdc)) rather than hand-written logic ([The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc)).

### Hard deletes and replays

After Chloe was deleted, load 3 was replayed by mistake:

```text
+-----------+---------+------------------------+-------------------+
|customer_id|city     |email                   |updated_at         |
+-----------+---------+------------------------+-------------------+
|7          |Canmore  |ava.chen@example.com    |2026-04-10 16:00:00|
|8          |Boulder  |ben.ortiz@example.com   |2026-05-02 10:00:00|
|9          |Moab     |chloe.martin@example.com|2026-04-12 09:30:00|
|10         |Vancouver|dev.patel@example.com   |2026-03-02 11:00:00|
+-----------+---------+------------------------+-------------------+
```

Chloe is back: with her row gone, there was nothing for the guard to compare against, so `WHEN NOT MATCHED THEN
INSERT` brought her back. A hard delete removes the evidence that she was deleted. The usual fixes are a soft delete
(keep the row with a `deleted_at` or `is_deleted` flag and its timestamp, so the guard still works), a separate
table of deleted keys that the load checks, or `AUTO CDC` in a Lakeflow pipeline, which handles deletes in the feed.

### Before CDF was turned on, and retention

The feed only records changes made after it was enabled. Reading an earlier version fails:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE no_cdf_yet (id INT) USING DELTA;
INSERT INTO no_cdf_yet VALUES (1);
ALTER TABLE no_cdf_yet SET TBLPROPERTIES (delta.enableChangeDataFeed = true);
INSERT INTO no_cdf_yet VALUES (2);
SELECT * FROM table_changes('no_cdf_yet', 0);
SELECT id, _change_type, _commit_version FROM table_changes('no_cdf_yet', 3);
```

```text
table_changes from 0: [DELTA_MISSING_CHANGE_DATA] Error getting change data for range [0 , 3] as change data was not recorded for version [0]. If you've enabled change data feed on this table, use `DESCRIBE HISTORY` to see when it was first e
+---+------------+---------------+
|id |_change_type|_commit_version|
+---+------------+---------------+
|2  |insert      |3              |
+---+------------+---------------+
```

The CDF page also says the feed "is not intended to serve as a permanent record of all changes to a table": change
records are only readable within the retention window, `VACUUM` deletes change data files with the legacy feed, and
for a permanent history you copy the feed into your own table (for example with an `availableNow` stream). On tables
with column mapping, a feed query cannot span a non-additive schema change such as a rename, drop or type change.

| | `skipChangeCommits` | Change Data Feed | Full re-read |
| --- | --- | --- | --- |
| Sees inserts | yes | yes | yes |
| Sees updates and deletes | no, ignores those commits | yes, as change rows | yes, by recomputing |
| Cost per run | small | small | the whole table |
| Typical use | append-only sources with rare manual fixes | silver to gold propagation | small tables |

!!! tip "In the interview"
    **"How do you propagate updates and deletes from silver to gold incrementally?"** Turn on Change Data Feed on the
    silver table (or use automatic change data feed on Databricks Runtime 19 and above), stream it with
    `readChangeFeed`, and in `foreachBatch` drop `update_preimage` rows, keep the latest change per key by
    `_commit_version`, and `MERGE` into gold with a `DELETE` branch for `delete` rows. Or let a Lakeflow pipeline
    ([formerly Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) do it with `AUTO CDC` ([formerly `APPLY CHANGES`](https://docs.databricks.com/aws/en/ldp/cdc)) or a materialized view.

## 9.12 Practice questions

*Level: mixed.*

**Q1. In two sentences, what is the silver layer for, and what does not belong in it?**

??? success "Answer"
    Silver holds validated, typed, deduplicated records, with at least one non-aggregated representation of each
    record, built from bronze so it can always be rebuilt. Business aggregates and report-shaped tables belong in
    gold, and raw unvalidated data belongs in bronze.

    **Why:** the Databricks medallion page lists cleaning, deduplication, out-of-order handling, quality checks and
    type casting as silver work, and says aggregate representations are "typically" in gold.

**Q2. Your bronze table is append-only. Should silver read it as a batch or as a stream, and why?**

??? success "Answer"
    As a stream (for example with the `availableNow` trigger on a schedule). The checkpoint remembers which table
    versions were processed, so each run reads only new rows. Batch reads are for small tables such as small
    dimensions.

    **Why:** Databricks: "Assuming all sources are append-only, configure most reads from bronze as streaming reads."
    The section 9.2 run read 7 rows, then 0, then 3.

**Q3. A colleague ran `UPDATE` on bronze to fix a currency. The next silver stream run fails. Why, and what are your
options?**

??? success "Answer"
    A Delta streaming source accepts appends only; an `UPDATE`, `DELETE`, `MERGE` or overwrite on the source makes the
    stream fail (the run showed `DELTA_SOURCE_TABLE_IGNORE_CHANGES`). Options: set `skipChangeCommits` to ignore such
    commits (the fix is then not propagated, so apply it in silver separately), fully refresh the downstream table,
    read the source's Change Data Feed instead, or use a materialized view.

    **Why:** these four are the approaches on the Databricks page for Delta streaming. Better still: never update
    bronze; send a correction as a new event.

**Q4. What do these return in an ANSI-mode session: `cast('abc' AS INT)`, `try_cast('abc' AS INT)`,
`try_cast('42' AS INT)`?**

??? success "Answer"
    The first fails with `CAST_INVALID_INPUT`; the second returns `NULL`; the third returns `42`.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT try_cast('abc' AS INT) AS a, try_cast('42' AS INT) AS b, try_cast('3.7' AS INT) AS c
    ```

    ```text
    +----+---+----+
    |a   |b  |c   |
    +----+---+----+
    |NULL|42 |NULL|
    +----+---+----+
    ```

    **Why:** `try_cast` returns `NULL` instead of an error for malformed input. Note that `'3.7'` is not a valid
    integer string here either; cast to a decimal first if you mean to round.

**Q5. Order timestamps arrive as ISO strings and sometimes as `03/01/2026 13:05`. Write one expression that parses
both and returns NULL for anything else.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    coalesce(try_to_timestamp(order_ts), try_to_timestamp(order_ts, 'MM/dd/yyyy HH:mm'))
    ```

    **Why:** `try_to_timestamp` returns `NULL` when the text does not fit, so `coalesce` takes the first format that
    works (section 9.3 shows the run). `to_timestamp` would raise an error on the first bad value under ANSI mode.

**Q6. Why does the quarantine table keep the raw string values instead of the typed ones?**

??? success "Answer"
    Because the typed value of an unreadable field is `NULL`, which hides what was actually sent. With the raw value
    (`abc`, `not a date`) the source team can see the problem, and the row can be corrected and replayed. Keep
    `_source_file` and `_ingest_ts` too, for tracing.

**Q7. Write PySpark that splits a typed DataFrame `typed` into valid rows and invalid rows with an array of reasons,
for two rules: `customer_id` present, `amount` not negative.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    from pyspark.sql import functions as F

    checked = typed.withColumn("dq_errors", F.filter(F.array(
        F.when(F.col("customer_id").isNull(), F.lit("customer_id missing")),
        F.when(F.col("amount") < 0, F.lit("amount negative")),
    ), lambda x: x.isNotNull()))
    valid = checked.where(F.size("dq_errors") == 0).drop("dq_errors")
    invalid = checked.where(F.size("dq_errors") > 0)
    ```

    On three test rows (`src/ch09/s8_practice.out`):

    ```text
    +--------+-----------+------+
    |order_id|customer_id|amount|
    +--------+-----------+------+
    |    1001|          7| 59.90|
    +--------+-----------+------+

    +--------+-----------+------+---------------------+
    |order_id|customer_id|amount|dq_errors            |
    +--------+-----------+------+---------------------+
    |1004    |NULL       |15.00 |[customer_id missing]|
    |1007    |8          |-5.00 |[amount negative]    |
    +--------+-----------+------+---------------------+
    ```

    **Why:** `F.when` without `otherwise` gives `NULL` when the rule passes; `F.filter` keeps only the failed rules;
    the split on `size` is exhaustive. This is the DataFrame form of the section 9.5 SQL.

**Q8. Bronze has 10 rows, silver 6, quarantine 3. The rules are written as `WHERE amount >= 0` for silver and
`WHERE NOT (amount >= 0)` for quarantine. Where did the missing row go?**

??? success "Answer"
    Nowhere. A row with a `NULL` amount makes both conditions `NULL`, so neither filter keeps it.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    WITH typed AS (
      SELECT * FROM VALUES (1001, 59.90BD), (1003, CAST(NULL AS DECIMAL(10,2))), (1007, -5.00BD)
      AS v(order_id, amount))
    SELECT count_if(amount >= 0)       AS valid_rows,
           count_if(NOT (amount >= 0)) AS invalid_rows,
           count(*)                    AS total_rows
    FROM typed
    ```

    ```text
    +----------+------------+----------+
    |valid_rows|invalid_rows|total_rows|
    +----------+------------+----------+
    |1         |1           |3         |
    +----------+------------+----------+
    ```

    With `coalesce(amount >= 0, false)` in both places the counts become 1 and 2 (same script,
    `src/ch09/s8_practice.out`). **Why:** SQL three-valued logic. Split on an error list's size, or make every
    condition null-proof, and reconcile counts on every run.

**Q9. A DataFrame append to a silver Delta table fails with `DELTA_METADATA_MISMATCH`. What is the likely cause and
what are the two possible fixes?**

??? success "Answer"
    The DataFrame has a column the table does not (in the section 9.4 run, `coupon_code`). Either drop or rename the
    column so it matches, or, if the new column is wanted, write with `.option("mergeSchema", "true")`, which adds it
    to the end of the schema with `NULL` for existing rows.

    **Why:** schema enforcement rejects unknown columns on write; evolution must be asked for per write (Databricks
    recommends that over the session-wide `spark.databricks.delta.schema.autoMerge.enabled`).

**Q10. What is the difference between `mergeSchema` and `overwriteSchema`?**

??? success "Answer"
    `mergeSchema` adds new columns (and supported changes) during an append or other write while keeping existing
    data. `overwriteSchema` is used with `mode("overwrite")` to replace the table's schema (and partitioning)
    entirely, for example to change a column type or rename by rewriting.

    **Why:** in the run, changing `order_id` to `BIGINT` with a plain overwrite failed with
    `DELTA_FAILED_TO_MERGE_FIELDS`; with `overwriteSchema` it worked.

**Q11. The source table gains a `carrier` column. Your silver load is `MERGE ... WHEN MATCHED THEN UPDATE SET * WHEN
NOT MATCHED THEN INSERT *`. What happens to `carrier`?**

??? success "Answer"
    It is silently ignored: the `MERGE` succeeds and the target schema does not change. Only with `MERGE WITH SCHEMA
    EVOLUTION INTO ...` (or `.withSchemaEvolution()` in the Python builder) is the column added.

    **Why:** Databricks schema enforcement for `MERGE`: with `INSERT *` / `UPDATE SET *`, "enforcement ignores
    columns in the source dataset that aren't present in the target table". Section 9.4 shows both runs.

**Q12. "Delta has schema enforcement, so a string amount can never get into my `DECIMAL` column." True?**

??? success "Answer"
    Not quite. In the run, appending a `STRING` column with value `'35.50'` to a `DECIMAL(10,2)` column succeeded (the
    value was cast), and the value `'abc'` failed the whole write with `CAST_INVALID_INPUT`. Schema enforcement checks
    types and attempts safe casts; it does not validate values row by row.

    **Why:** the Databricks page says it "attempts to safely cast column data types". Type and validate with
    `try_cast` and rules before writing.

**Q13. You add `CHECK (amount >= 0)` to a silver table and it fails with `DELTA_NEW_CHECK_CONSTRAINT_VIOLATION`,
although no amount is negative. Why?**

??? success "Answer"
    Some rows have a `NULL` amount. A `CHECK` expression must be true for every row, and `NULL >= 0` is `NULL`. Write
    `CHECK (amount IS NULL OR amount >= 0)` if nulls are allowed, or add `NOT NULL` if they are not.

    **Why:** shown in section 9.4; Databricks verifies existing rows before adding the constraint.

**Q14. `events.dropDuplicates()` did not remove a duplicate that was delivered twice. Why?**

??? success "Answer"
    `dropDuplicates()` compares every column, and the two copies differ in metadata columns such as `_source_file`
    and `_ingest_ts`. Compare only the business columns: `dropDuplicates(["order_id", "status", "updated_at", ...])`.

**Q15. Find the bug: "keep the latest status per order" written as `events.dropDuplicates(["order_id"])`.**

??? success "Answer"
    `dropDuplicates` with a subset keeps one row per key, but not a defined one; in the run it kept 1002's oldest
    status, `PLACED`. Use a window:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    w = Window.partitionBy("order_id").orderBy(F.col("updated_at").desc(), F.col("_ingest_ts").desc())
    latest = events.withColumn("rn", F.row_number().over(w)).where("rn = 1").drop("rn")
    ```

**Q16. Find the bug.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT * FROM silver_order_events
QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY updated_at) = 1
```

??? success "Answer"
    The order is ascending, so row 1 is the *oldest* event. On two events for order 1002 it kept `PLACED`:

    ```text
    +--------+------+-------------------+
    |order_id|status|updated_at         |
    +--------+------+-------------------+
    |1002    |PLACED|2026-03-01 11:00:00|
    +--------+------+-------------------+
    ```

    (`src/ch09/s8_practice.out`, on a two-row `VALUES` list.) Use `ORDER BY updated_at DESC`, plus a tie-breaker
    such as `_ingest_ts DESC` or a source sequence number.

**Q17. For deduplication, when would `rank()` give a different result from `row_number()`?**

??? success "Answer"
    When two rows tie on the ordering. `rank()` gives both rank 1, so `= 1` keeps both; `row_number()` keeps exactly
    one, chosen arbitrarily unless the order is unique. Fix ties with a real tie-breaker (a sequence number), as in the
    section 9.6 run where `seq` decided between `PAID` and `SHIPPED`.

**Q18. Write Databricks SQL that keeps the latest row per customer from `customer_updates`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT * FROM customer_updates
    QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY updated_at DESC) = 1
    ```

    **Why:** this is exactly the `customer_updates_latest` view used by the SCD runs (`src/ch09/ch09_customers.py`).
    Add a tie-breaker if `updated_at` can repeat for one customer.

**Q19. You must pick "the latest event" for each order. Event time (`updated_at`) or ingest time (`_ingest_ts`)?
Why?**

??? success "Answer"
    Event time. Ingest time says when you received the event; a late file has a newer ingest time but older facts. In
    the run, ordering by `_ingest_ts` turned order 1002 from `SHIPPED` back to `PACKED`. Use ingest time only to break
    ties.

**Q20. Find the bug in this silver load, which runs every hour.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
MERGE INTO silver_orders_naive AS t
USING batch_b AS s
ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

??? success "Answer"
    Nothing stops an older event that arrives late from overwriting a newer one. Add the guard:
    `WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *`.

    **Why:** section 9.7: without the guard, a late `PACKED` event replaced `SHIPPED`.

**Q21. Why should the guard be `s.updated_at > t.updated_at` and not `>=`?**

??? success "Answer"
    With `>=`, rerunning a batch rewrites every row whose timestamp is equal, with identical values. The data looks
    the same, but files are rewritten and Change Data Feed emits an `update_preimage`/`update_postimage` pair per row.
    The run in section 9.11 showed four spurious change rows with `>=` and zero with `>`.

**Q22. A `MERGE` into silver fails with `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`. Why, and how do you
fix it?**

??? success "Answer"
    The source has two or more rows with the same key that match one target row and try to modify it, and SQL merge
    semantics cannot say which wins. Deduplicate the source to one row per key first:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    USING (SELECT * FROM batch_c
           QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY updated_at DESC) = 1) AS s
    ```

    **Why:** reproduced and fixed in section 9.7. On Databricks Runtime 16.0 and above, conditions in `WHEN MATCHED`
    also count when deciding whether there are duplicate matches (15.4 LTS and below look only at `ON`); open-source
    Delta 4.4.1 still failed when only one row passed the condition. Deduplicating is the reliable fix.

**Q23. Does a `MERGE` fail if one source row matches several target rows?**

??? success "Answer"
    No. Only several source rows matching one target row is ambiguous. One source row matching many target rows is
    allowed, which is exactly why a loose `ON` clause in an SCD Type 2 merge silently closes every historical row
    (section 9.10, the Jasper run).

**Q24. A cleanup `MERGE ... WHEN MATCHED THEN DELETE` uses a source with duplicate keys. Does it fail?**

??? success "Answer"
    No. "Databricks allows multiple matches when matches are unconditionally deleted", because deleting a row twice is
    not ambiguous. The open-source run here (`src/ch09/s8_practice.out`) also succeeded. Add a condition to the
    `DELETE` and the duplicate check applies again.

**Q25. How do you prove that a silver load is idempotent?**

??? success "Answer"
    Note the table version, run the same batch again, then compare the table with that version both ways:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT count(*) FROM (
      (SELECT * FROM silver_orders EXCEPT ALL SELECT * FROM silver_orders VERSION AS OF 3)
      UNION ALL
      (SELECT * FROM silver_orders VERSION AS OF 3 EXCEPT ALL SELECT * FROM silver_orders))
    ```

    Zero means identical. Also check `DESCRIBE HISTORY` `operationMetrics`: the rerun's `numTargetRowsInserted` and
    `numTargetRowsUpdated` should be 0 (section 9.8). A new version is still committed; that is fine.

**Q26. Your streaming job does a `MERGE` in `foreachBatch`. Why does it have to be idempotent, and what helps when
the batch function does plain appends instead?**

??? success "Answer"
    After a failure, a restarted stream can run the same micro-batch again, so the batch function may see the same
    data twice. A guarded `MERGE` on a key absorbs that. For appends, Delta's `txnAppId` and `txnVersion` writer
    options let Delta recognize and skip a batch it already wrote; a new checkpoint needs a new `txnAppId`.

    **Why:** both points are on the Databricks page "Delta Lake table streaming reads and writes".

**Q27. Scenario: after someone reran yesterday's job, `silver_orders` has two rows for many orders. List likely
causes.**

??? success "Answer"
    The load appends (`INSERT INTO` or `mode("append")`) instead of merging on `order_id`; or the `MERGE` key is
    wrong (for example `order_id` plus `_ingest_ts`, which never matches a replay); or the stream got a new
    checkpoint and reprocessed all of bronze into an append-only table. The section 9.8 run shows 4 rows becoming 8
    with a blind append.

**Q28. When would you choose SCD Type 1 and when Type 2 for Red Rock Supply customers?**

??? success "Answer"
    Type 1 when only the current value matters (a typo fix in a name, a current email for marketing). Type 2 when
    reports must reflect the value at the time of an event, such as revenue by the city the customer lived in when
    they ordered. Many teams keep both: a Type 1 table for operational use and a Type 2 table for analysis.

**Q29. In the SCD Type 2 `MERGE`, why is each changed customer in the source twice, once with a `NULL` merge key?**

??? success "Answer"
    A source row can either match (and update) or not match (and insert), never both. The copy with
    `merge_key = customer_id` matches the current row and closes it. The copy with `merge_key = NULL` can never
    satisfy `t.customer_id = s.merge_key`, so it is always inserted as the new current row. Both happen in one atomic
    `MERGE`.

**Q30. Find the bug.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1. The section 9.10 statement, with its staging subquery written as
`staged` for space; the run is the Jasper example in `src/ch09/s7_scd2.out`.*

```sql
MERGE INTO silver_customers_scd2 AS t
USING staged AS s
ON t.customer_id = s.merge_key
WHEN MATCHED AND s.updated_at > t.valid_from
     AND NOT (t.name <=> s.name AND t.email <=> s.email AND t.city <=> s.city AND t.country <=> s.country)
  THEN UPDATE SET is_current = false, valid_to = s.updated_at
WHEN NOT MATCHED
  THEN INSERT (customer_id, name, email, city, country, valid_from, valid_to, is_current)
       VALUES (s.customer_id, s.name, s.email, s.city, s.country, s.updated_at, NULL, true)
```

??? success "Answer"
    The `ON` clause lacks `AND t.is_current`, so the incoming row matches every historical row of the customer and
    closes them all again. In the run, Ava's Calgary, Banff and Canmore rows all got `valid_to = 2026-05-01`. Add
    `AND t.is_current` to `ON`.

**Q31. Find the bug in this change check: `WHEN MATCHED AND (t.email <> s.email OR t.city <> s.city)`.**

??? success "Answer"
    If either side is `NULL`, `<>` returns `NULL`, and the change is missed (a customer who had no email and now has
    one is not versioned). Use null-safe comparison: `NOT (t.email <=> s.email AND t.city <=> s.city)`.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT old_email, new_email,
           old_email <> new_email        AS with_not_equal,
           NOT (old_email <=> new_email) AS with_null_safe
    FROM VALUES (CAST(NULL AS STRING), 'ava.chen@example.com'),
                ('ava.chen@example.com', 'ava.chen@example.com'),
                ('chloe.m@example.com', 'chloe.martin@example.com') AS v(old_email, new_email)
    ```

    ```text
    +--------------------+------------------------+--------------+--------------+
    |old_email           |new_email               |with_not_equal|with_null_safe|
    +--------------------+------------------------+--------------+--------------+
    |NULL                |ava.chen@example.com    |NULL          |true          |
    |ava.chen@example.com|ava.chen@example.com    |false         |false         |
    |chloe.m@example.com |chloe.martin@example.com|true          |true          |
    +--------------------+------------------------+--------------+--------------+
    ```

**Q32. Write the query: which city did each customer live in on 2026-03-15, from the Type 2 table?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id, city FROM silver_customers_scd2
    WHERE valid_from <= TIMESTAMP'2026-03-15 00:00:00'
      AND (valid_to IS NULL OR valid_to > TIMESTAMP'2026-03-15 00:00:00')
    ```

    **Why:** half-open intervals (`valid_from` included, `valid_to` excluded) put each moment in exactly one
    version. The run returned Banff for Ava.

**Q33. A customer change dated February 15 arrives after the April change was already applied to the Type 2 table.
What does the section 9.10 `MERGE` do with it, and what would handle it properly?**

??? success "Answer"
    It ignores it: the guard `s.updated_at > t.valid_from` is false against the current (April) row, and no `NULL`-key
    copy is staged. History stays consistent but misses that version. Inserting it between existing versions means
    splitting an existing interval, which the simple pattern does not do. `AUTO CDC` ([formerly `APPLY CHANGES`](https://docs.databricks.com/aws/en/ldp/cdc)) with
    `SEQUENCE BY` in a Lakeflow pipeline ([formerly Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) is Databricks' tool for out-of-order CDC into
    SCD Type 2.

**Q34. How do you turn on Change Data Feed for a new and for an existing table, and what columns does it add?**

??? success "Answer"
    `CREATE TABLE ... TBLPROPERTIES (delta.enableChangeDataFeed = true)` or
    `ALTER TABLE ... SET TBLPROPERTIES (delta.enableChangeDataFeed = true)`. The feed adds `_change_type` (`insert`,
    `update_preimage`, `update_postimage`, `delete`), `_commit_version` and `_commit_timestamp`.

    **Why:** this is the legacy (per-table) feed, the only kind in open-source Delta. On Databricks Runtime 19 and above
    with Unity Catalog tables that have row tracking, automatic change data feed needs no property, and the two cannot
    be used together.

**Q35. What is the difference between `table_changes('silver_customers', 2, 4)` and
`spark.read.option("readChangeFeed", "true").option("startingVersion", 2).option("endingVersion", 4)`? Are the ends
inclusive?**

??? success "Answer"
    They return the same change rows, one in SQL and one in the DataFrame API. Start and end versions are inclusive.
    A batch read needs a starting version; omit the end to read to the latest version. Timestamps can be used instead
    of versions.

**Q36. `SELECT * FROM table_changes('orders_silver', 0)` fails with `DELTA_MISSING_CHANGE_DATA`. Why?**

??? success "Answer"
    The feed was enabled after version 0, and change data exists only for commits made after it was enabled. Use
    `DESCRIBE HISTORY` to find the version where `delta.enableChangeDataFeed` was set and start from the version after
    it. The section 9.11 run shows the error and the working read from version 3.

**Q37. Write the `MERGE` used inside `foreachBatch` to apply a silver change feed (with deletes) to a gold table keyed
by `customer_id`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    MERGE INTO gold_customer_directory AS g
    USING (
      SELECT * FROM cdf_batch
      WHERE _change_type IN ('insert', 'update_postimage', 'delete')
      QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY _commit_version DESC) = 1
    ) AS c
    ON g.customer_id = c.customer_id
    WHEN MATCHED AND c._change_type = 'delete' THEN DELETE
    WHEN MATCHED THEN UPDATE SET name = c.name, city = c.city, country = c.country
    WHEN NOT MATCHED AND c._change_type != 'delete' THEN
      INSERT (customer_id, name, city, country) VALUES (c.customer_id, c.name, c.city, c.country)
    ```

    **Why:** preimages are dropped; one micro-batch can hold several commits for a key, so only the last change
    (highest `_commit_version`) is applied, which also avoids the multiple-match error. Section 9.11 ran this.

**Q38. A customer was hard-deleted from silver for privacy reasons. A week later an old batch is replayed and the
customer is back. Why, and how do you prevent it?**

??? success "Answer"
    With the row gone, the replayed record matches nothing, so `WHEN NOT MATCHED THEN INSERT` adds it again; the guard
    has nothing to compare with. Prevent it with soft deletes (keep the key with a deletion flag and timestamp so the
    guard rejects older records), a table of deleted keys checked by the load, or `AUTO CDC` ([formerly
    `APPLY CHANGES`](https://docs.databricks.com/aws/en/ldp/cdc)) handling deletes in a Lakeflow pipeline
    ([formerly Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)). Section 9.11 reproduced the
    resurrection.

**Q39. A new stream with `readChangeFeed` on a large silver table starts by emitting millions of `insert` rows,
although the downstream table is already loaded. Why, and what do you do?**

??? success "Answer"
    On first start, a CDF stream returns the table's current snapshot as `insert` records and then later changes.
    If the downstream table already holds everything up to version N, start the new stream with
    `.option("startingVersion", N + 1)` (only for a new checkpoint; it is ignored once the checkpoint has progress),
    and make sure that version is still within the retention window.

**Q40. Scenario: gold daily sales are recomputed from all of silver every hour and the job keeps getting slower. Silver
orders are updated (status changes) and occasionally deleted. Outline an incremental design.**

??? success "Answer"
    Turn on Change Data Feed on `shop.silver.orders` (or rely on automatic change data feed on Databricks Runtime 19
    and above), stream it with `readChangeFeed` and `availableNow`, and in `foreachBatch` find the affected keys
    (order dates or orders), then recompute only those days in gold with a `MERGE` or `INSERT ... REPLACE WHERE`.
    Keep every step idempotent. Alternatives: a materialized view, which handles upstream changes by recomputing, or a
    Lakeflow pipeline ([formerly Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)). Chapter 10 builds the gold side.

    **Why:** a plain stream from silver fails on updates, and full recomputation grows with the table; the feed gives
    only the changed rows.

## Sources

- [What is the medallion lakehouse architecture?](https://docs.databricks.com/aws/en/lakehouse/medallion) (last updated Oct 29, 2026)
- [Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake) (last updated Oct 15, 2026)
- [try_cast function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_cast) (last updated Oct 28, 2026)
- [to_timestamp function](https://docs.databricks.com/aws/en/sql/language-manual/functions/to_timestamp) (last updated Oct 30, 2026)
- [try_to_timestamp function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_to_timestamp) (last updated Oct 30, 2026)
- [Schema enforcement](https://docs.databricks.com/aws/en/tables/schema-enforcement) (last updated Sep 11, 2026)
- [Update table schemas with schema evolution](https://docs.databricks.com/aws/en/tables/update-schema) (last updated Sep 11, 2026)
- [Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints) (last updated Nov 6, 2026)
- [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into) (last updated Sep 11, 2026)
- [Upsert into a Delta Lake table using merge](https://docs.databricks.com/aws/en/delta/merge) (last updated Sep 11, 2026)
- [QUALIFY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-qualify) (last updated Sep 11, 2026)
- [row_number ranking window function](https://docs.databricks.com/aws/en/sql/language-manual/functions/row_number) (last updated Sep 11, 2026)
- [Use change data feed on Databricks](https://docs.databricks.com/aws/en/delta/delta-change-data-feed) (last updated Oct 9, 2026)
- [table_changes table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/table_changes) (last updated Oct 15, 2026)
- [Table properties reference](https://docs.databricks.com/aws/en/delta/table-properties) (last updated Nov 5, 2026)
- [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc) (last updated Nov 9, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations) (last updated Oct 26, 2026)
- [pyspark.sql.DataFrame.dropDuplicates](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.dropDuplicates.html) (Apache Spark docs; no date shown)
- [Delta Lake docs source: Table deletes, updates, and merges (SCD Type 2 example)](https://github.com/delta-io/delta/blob/master/docs/src/content/docs/delta-update.mdx) (delta.io documentation source on GitHub; no date shown; docs.delta.io itself was not reachable)
