# 12. A complete medallion project

*Chapters 7 to 11 each looked at one hop of the medallion architecture. This chapter builds the whole thing once,
end to end, for the Red Rock Supply shop: three days of raw files with the problems real feeds have, a bronze layer
that loads only new files, a silver layer that types, checks, quarantines, deduplicates and keeps customer history,
a gold star schema with daily sales and customer lifetime value, and data tests after every layer. Everything ran on
the local Spark 4.2 + Delta Lake 4.4.1 engine, including a rerun that changes nothing and a full rebuild from bronze.
Then the same project is shown as one Lakeflow job and as one Lakeflow pipeline, with an honest comparison. "Walk me
through a pipeline you built" is the most common open question in a data engineer interview; this is a project you
can walk through.*

!!! abstract "In this chapter"
    **You will learn:**

    - how the pieces of chapters 7 to 11 fit into one small, copyable project, and its folder layout
    - bronze: incremental file ingestion with a streaming `availableNow` read and a checkpoint (the open-source
      stand-in for Auto Loader), with the Auto Loader version beside it
    - silver: parsing, typing, rule checks with reasons, a quarantine table, deduplication by key, an out-of-order
      guard, idempotent `MERGE`, child rows (order lines) replaced with their parent, customers as SCD Type 2
    - gold: a star schema (one fact, three dimensions) with stable surrogate keys, an "unknown customer" member,
      and aggregates restated only for the dates that changed, found from the change data feed
    - a data test suite that runs after every layer and fails loudly, with real output
    - reruns, restatements, backfills and a full rebuild, each proved with counts and Delta history
    - the same project as one Lakeflow job (Declarative Automation Bundles YAML) and as one Lakeflow pipeline (SQL
      with streaming tables, expectations and `AUTO CDC`), and when to choose which
    - a Unity Catalog layout with grants per layer, and how to present the project in an interview

    **You need:** [7. The medallion architecture](07-Medallion-Architecture.md),
    [9. Building silver](09-Building-Silver.md) (dedup, `MERGE`, SCD Type 2),
    [4. Delta Lake](04-Delta-Lake.md) (history, time travel, `RESTORE`). [8. Bronze ingestion](08-Bronze-Ingestion.md),
    [10. Building gold](10-Building-Gold.md), [11. Structured Streaming](11-Structured-Streaming.md) and
    [14. Data quality and CDC](14-Data-Quality-and-CDC.md) go deeper on single hops.

    **Levels:** sections 12.1 to 12.3 beginner; 12.4 to 12.7, 12.10 and 12.12 intermediate; 12.8, 12.9 and 12.11
    expert; 12.13 (the interview) and 12.14 (practice) mix all levels.

## 12.1 The project at a glance

*Level: beginner.*

**The business.** Red Rock Supply sells outdoor gear online, in Canadian and US dollars. Every order event (placed,
shipped, corrected) is written by the order system as one JSON line into a file in a landing folder. Every morning
customer service exports the whole customer list as a CSV snapshot, and the product list arrives as a CSV file. The
business wants two answers they can trust: **sales per day and product category**, and **lifetime value per
customer**. Finance also wants to know what a report said before a number was corrected.

**The plan.** Four steps, run every day in this order:

1. **Bronze** copies each new landing file into a Delta table, exactly as received, with the file name and the
   ingest time. It judges nothing.
2. **Silver** turns raw lines into typed rows, checks rules, moves bad events to a quarantine table with the reasons,
   keeps the latest version of each order, explodes order lines, and keeps every version of each customer (SCD Type
   2).
3. **Gold** builds a small star schema (`fact_order_lines` with `dim_customer`, `dim_product`, `dim_date`) and two
   aggregates (`daily_sales`, `customer_ltv`).
4. **Tests** run after each layer: counts that must reconcile, keys that must be unique, facts that must have a
   dimension row, sums that must match. A failed test stops the run.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 350" role="img" aria-label="Data flow of the Red Rock Supply project: landing files (orders JSON, customers CSV, products CSV) go to three bronze tables, then to five silver tables (orders, order_items, orders_quarantine, customers SCD2, products), then to gold (dim_date, dim_product, dim_customer, fact_order_lines, daily_sales, customer_ltv); checks run after each layer">
<g fill="currentColor" font-size="14" font-weight="bold" text-anchor="middle">
<text x="70" y="24">landing</text>
<text x="230" y="24">bronze</text>
<text x="400" y="24">silver</text>
<text x="567" y="24">gold</text>
</g>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="10" y="50" width="120" height="26" rx="4"/>
<rect x="10" y="170" width="120" height="26" rx="4"/>
<rect x="10" y="250" width="120" height="26" rx="4"/>
<rect x="165" y="50" width="130" height="26" rx="4"/>
<rect x="165" y="170" width="130" height="26" rx="4"/>
<rect x="165" y="250" width="130" height="26" rx="4"/>
<rect x="330" y="40" width="140" height="26" rx="4"/>
<rect x="330" y="76" width="140" height="26" rx="4"/>
<rect x="330" y="112" width="140" height="26" rx="4" stroke-dasharray="5 3"/>
<rect x="330" y="170" width="140" height="26" rx="4"/>
<rect x="330" y="250" width="140" height="26" rx="4"/>
<rect x="505" y="40" width="125" height="26" rx="4"/>
<rect x="505" y="76" width="125" height="26" rx="4"/>
<rect x="505" y="112" width="125" height="26" rx="4"/>
<rect x="505" y="148" width="125" height="26" rx="4" stroke-width="2.5"/>
<rect x="505" y="200" width="125" height="26" rx="4"/>
<rect x="505" y="236" width="125" height="26" rx="4"/>
<line x1="130" y1="63" x2="157" y2="63"/>
<line x1="130" y1="183" x2="157" y2="183"/>
<line x1="130" y1="263" x2="157" y2="263"/>
<line x1="295" y1="63" x2="312" y2="63"/>
<line x1="312" y1="53" x2="312" y2="125"/>
<line x1="312" y1="53" x2="322" y2="53"/>
<line x1="312" y1="89" x2="322" y2="89"/>
<line x1="312" y1="125" x2="322" y2="125"/>
<line x1="295" y1="183" x2="322" y2="183"/>
<line x1="295" y1="263" x2="322" y2="263"/>
<line x1="470" y1="53" x2="487" y2="53"/>
<line x1="470" y1="89" x2="487" y2="89"/>
<line x1="470" y1="183" x2="487" y2="183"/>
<line x1="470" y1="263" x2="487" y2="263"/>
<line x1="487" y1="53" x2="487" y2="263"/>
<line x1="487" y1="53" x2="497" y2="53"/>
<line x1="487" y1="89" x2="497" y2="89"/>
<line x1="487" y1="125" x2="497" y2="125"/>
<line x1="487" y1="161" x2="497" y2="161"/>
<line x1="487" y1="213" x2="497" y2="213"/>
<line x1="487" y1="249" x2="497" y2="249"/>
<rect x="165" y="296" width="130" height="40" rx="4" stroke-dasharray="3 3"/>
<rect x="330" y="296" width="140" height="40" rx="4" stroke-dasharray="3 3"/>
<rect x="505" y="296" width="125" height="40" rx="4" stroke-dasharray="3 3"/>
</g>
<g fill="currentColor">
<polygon points="165,63 157,59 157,67"/>
<polygon points="165,183 157,179 157,187"/>
<polygon points="165,263 157,259 157,267"/>
<polygon points="330,53 322,49 322,57"/>
<polygon points="330,89 322,85 322,93"/>
<polygon points="330,125 322,121 322,129"/>
<polygon points="330,183 322,179 322,187"/>
<polygon points="330,263 322,259 322,267"/>
<polygon points="505,53 497,49 497,57"/>
<polygon points="505,89 497,85 497,93"/>
<polygon points="505,125 497,121 497,129"/>
<polygon points="505,161 497,157 497,165"/>
<polygon points="505,213 497,209 497,217"/>
<polygon points="505,249 497,245 497,253"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="70" y="68">orders_*.json</text>
<text x="70" y="188">customers_*.csv</text>
<text x="70" y="268">products_*.csv</text>
<text x="230" y="68">orders (raw line)</text>
<text x="230" y="188">customers</text>
<text x="230" y="268">products</text>
<text x="400" y="58">orders</text>
<text x="400" y="94">order_items</text>
<text x="400" y="130">orders_quarantine</text>
<text x="400" y="188">customers (SCD 2)</text>
<text x="400" y="268">products (SCD 1)</text>
<text x="567" y="58">dim_date</text>
<text x="567" y="94">dim_product</text>
<text x="567" y="130">dim_customer</text>
<text x="567" y="166">fact_order_lines</text>
<text x="567" y="218">daily_sales</text>
<text x="567" y="254">customer_ltv</text>
<text x="230" y="313">checks: every</text>
<text x="230" y="329">line arrived</text>
<text x="400" y="313">checks: reconcile,</text>
<text x="400" y="329">unique keys, SCD 2</text>
<text x="567" y="313">checks: orphans,</text>
<text x="567" y="329">sums match</text>
</g>
</svg>
<figcaption>Figure 12.1. The data flow. Bronze keeps every line; silver splits good events (orders, order_items) from
bad ones (the dashed quarantine table); gold builds the dimensions and the fact from silver, and daily_sales and
customer_ltv from the fact. A set of checks (dashed, bottom) runs after each layer.</figcaption>
</figure>

**Tables per layer.** Locally there is no Unity Catalog, so the tables live in schemas `bronze`, `silver` and `gold`
of the local catalog; on Databricks they are `shop.bronze.orders`, `shop.silver.orders` and so on (section 12.12).

| Layer | Table | One row per | Written by |
| --- | --- | --- | --- |
| bronze | `orders` | line in a landing file | streaming append |
| bronze | `customers`, `products` | CSV row | streaming append |
| silver | `orders` | order (latest version) | `MERGE` with out-of-order guard |
| silver | `order_items` | order and product | `MERGE` that also deletes dropped lines |
| silver | `orders_quarantine` | bad event, with reasons | insert-only `MERGE` |
| silver | `customers` | version of a customer (SCD Type 2) | staged `MERGE` of chapter 9 |
| silver | `products` | product (SCD Type 1) | `MERGE` |
| gold | `dim_date`, `dim_product`, `dim_customer` | date, product, customer version | `MERGE` |
| gold | `fact_order_lines` | order line | `INSERT ... REPLACE WHERE` for changed dates |
| gold | `daily_sales` | date, category, currency | `INSERT ... REPLACE WHERE` for changed dates |
| gold | `customer_ltv` | customer and currency | `MERGE` |

**The folder layout.** The code is a normal Python package plus the Databricks files, laid out as a bundle project
(section 12.10), so the same folder runs locally and deploys to a workspace. It is in `src/ch12/`:

```text
src/ch12/
├── databricks.yml                 bundle: name, catalog variable, dev and prod targets   (Databricks only)
├── resources/
│   ├── redrock_job.yml            the Lakeflow job: bronze -> silver -> gold -> tests     (Databricks only)
│   └── redrock_pipeline.yml       the declarative alternative                            (Databricks only)
├── setup/
│   └── unity_catalog.sql          catalog, schemas, volumes, grants                      (Databricks only)
├── src/
│   ├── redrock/
│   │   ├── config.py              paths: landing folder, checkpoints
│   │   ├── landing.py             makes the three days of raw files (the "source systems")
│   │   ├── bronze.py              load_bronze()
│   │   ├── silver.py              load_silver(): orders, order_items, quarantine, customers, products
│   │   ├── gold.py                load_gold(): dimensions, fact, daily_sales, customer_ltv
│   │   ├── checks.py              run_checks(layer): the data tests
│   │   └── pipeline.py            run_all(): bronze, checks, silver, checks, gold, checks
│   ├── run_task.py                entry point for one job task                           (Databricks only)
│   └── pipeline/
│       └── redrock_pipeline.sql   the whole flow as one Lakeflow pipeline                (Databricks only)
├── run_demo.py   -> demo.out      three days, rerun, failing test, full rebuild (run here)
├── practice.py   -> practice.out  the "extend the project" solutions (run here)
└── practice_q8.py -> practice_q8.out  MERGE with a duplicate source key (run here)
```

Two rules shaped the code, and both are worth saying in an interview:

- **Every step can run twice.** Bronze remembers files through its checkpoint; every silver and gold write is a
  `MERGE` with a guard or a `REPLACE WHERE` of a known range. Section 12.9 proves it.
- **Nothing is lost silently.** A bad line goes to quarantine with the reason, an unknown customer is flagged and kept,
  and a check fails the run if counts do not reconcile.

## 12.2 Landing: three days of files with real problems

*Level: beginner.*

A pipeline that only ever sees clean data proves little. `landing.py` writes three days of files, and each day
carries problems that real feeds have:

| Day | File | What is wrong with it (on purpose) |
| --- | --- | --- |
| 1 | `orders_20260301_0900.json` | the third line is cut off: malformed JSON |
| 1 | `orders_20260301_1800.json` | order 1002 is sent again (an exact duplicate); 1003 is sent again in full |
| 2 | `orders_20260302_1800.json` | a new optional field `channel`; order 1005 is for customer 99, who does not exist; order 1002 changes to `SHIPPED` |
| 2 | `customers_20260302.csv` | Ana (customer 1) moved from Calgary to Banff; Erin (customer 5) is new |
| 3 | `orders_20260303_1800.json` | a **late correction of a day 1 order**: 1001 now has 1 item, not 2 (29.95, not 59.90); an old `PLACED` version of 1002 arrives **after** the newer `SHIPPED` one; order 1008 has an item with `qty` 0 |
| 3 | `customers_20260303.csv` | Ben's email changed, sent as ` Ben.Okafor@Example.com ` (spaces, capitals) |

Each order event has the shared Red Rock Supply shape (chapter 7) plus `updated_at`, the time the source system
changed the order. `updated_at` is what orders the versions of one order; `order_ts` (when the order was placed) never
changes, which is why a correction made on March 3 changes March 1 sales. The generator, shortened:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def event(order_id, customer_id, order_ts, status, amount, currency, updated_at, items, channel=None):
    """One order event, shaped like the source system sends it (amounts and prices as strings)."""
    e = {"order_id": order_id, "customer_id": customer_id, "order_ts": order_ts, "status": status,
         "amount": amount, "currency": currency, "updated_at": updated_at,
         "items": [{"product_id": p, "qty": q, "unit_price": u} for p, q, u in items]}
    if channel is not None:
        e["channel"] = channel
    return json.dumps(e)

E1001 = event(1001, 1, "2026-03-01T10:15:00Z", "PLACED", "59.90", "CAD", "2026-03-01T10:15:00Z", [(3, 2, "29.95")])
E1002 = event(1002, 2, "2026-03-01T11:05:00Z", "PLACED", "249.00", "USD", "2026-03-01T11:05:00Z", [(1, 1, "249.00")])
E1003 = event(1003, 1, "2026-03-01T13:40:00Z", "PLACED", "189.50", "CAD", "2026-03-01T13:40:00Z", [(2, 1, "189.50")])

ORDER_FILES = {
    1: {
        "orders_20260301_0900.json": [E1001, E1002, E1003[:70]],   # third line is cut off
        "orders_20260301_1800.json": [E1002, E1003],               # 1002 re-sent; 1003 sent again in full
    },
    # days 2 and 3: see landing.py
}

def _write(folder, name, lines):
    os.makedirs(folder, exist_ok=True)
    tmp = os.path.join(folder, "." + name + ".tmp")      # write, then rename: readers never see half a file
    with open(tmp, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.rename(tmp, os.path.join(folder, name))
```

Writing to a hidden temporary name and renaming is how a well-behaved producer avoids a reader picking up half a
file: Spark's file sources skip files whose names start with `.` or `_`. Day 1 as it lands (lines cut at 110
characters for the page):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
--- landing/orders/orders_20260301_0900.json
    {"order_id": 1001, "customer_id": 1, "order_ts": "2026-03-01T10:15:00Z", "status": "PLACED", "amount": "59....
    {"order_id": 1002, "customer_id": 2, "order_ts": "2026-03-01T11:05:00Z", "status": "PLACED", "amount": "249...
    {"order_id": 1003, "customer_id": 1, "order_ts": "2026-03-01T13:40:00Z
--- landing/orders/orders_20260301_1800.json
    {"order_id": 1002, "customer_id": 2, "order_ts": "2026-03-01T11:05:00Z", "status": "PLACED", "amount": "249...
    {"order_id": 1003, "customer_id": 1, "order_ts": "2026-03-01T13:40:00Z", "status": "PLACED", "amount": "189...
--- landing/customers/customers_20260301.csv
    customer_id,name,email,city,country,updated_at
    1,Ana Lopez,ana@example.com,Calgary,CA,2026-01-05 09:00:00
    2,Ben Okafor,ben@example.com,Denver,US,2026-01-07 12:30:00
    3,Chloe Martin,chloe@example.com,Moab,US,2026-01-09 16:45:00
    4,Dev Patel,dev@example.com,Vancouver,CA,2026-01-11 08:15:00
--- landing/products/products_20260301.csv
    product_id,name,category,price
    1,Trail Tent 2P,Camping,249.00
    2,Down Sleeping Bag,Camping,189.50
    3,Trekking Poles,Hiking,29.95
    4,Headlamp,Hiking,39.00
    5,Rain Shell,Apparel,159.00
```

## 12.3 Bronze: load each new file once

*Level: beginner.*

**The problem.** Files keep arriving. Reading the whole folder every day would load day 1 again on day 2, and
tracking "which files did I already load" by hand is a classic source of duplicates and gaps.

**The tool.** A Structured Streaming file source with a **checkpoint** remembers every file it has read. With
`trigger(availableNow=True)` the stream processes everything new at that moment and then stops, so a daily job gets
"only new files" without any bookkeeping of its own. This is what Auto Loader does on Databricks (the Databricks
version is at the end of this section). Bronze keeps each order line as one string column, `raw`, so nothing can fail or be dropped at this step:
not the cut-off line, not an unknown field. Typing is silver's job ([chapter 7](07-Medallion-Architecture.md) shows
what goes wrong when bronze types too early).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
ALL_STRINGS_CUSTOMERS = "customer_id STRING, name STRING, email STRING, city STRING, country STRING, updated_at STRING"

def _with_ingest_metadata(df):
    return (df.withColumn("_file_name", F.col("_metadata.file_name"))
              .withColumn("_file_modification_time", F.col("_metadata.file_modification_time"))
              .withColumn("_ingested_at", F.current_timestamp()))

def _run_once(df, table):
    """Append the new files' rows to the table, then stop. Returns the number of rows added."""
    q = (df.writeStream
           .format("delta")                       # open-source Spark's default format is Parquet
           .outputMode("append")
           .option("checkpointLocation", checkpoint("bronze_" + table))
           .trigger(availableNow=True)
           .toTable("bronze." + table))
    q.awaitTermination()
    return sum(p["numInputRows"] for p in q.recentProgress)

def load_bronze(spark):
    create_tables(spark)
    orders = (spark.readStream.format("text").load(ORDERS_IN)     # text: one row per line, nothing lost
                   .select(F.col("value").alias("raw")))
    customers = (spark.readStream.format("csv").option("header", True)
                      .schema(ALL_STRINGS_CUSTOMERS).load(CUSTOMERS_IN))
    products = (spark.readStream.format("csv").option("header", True)
                     .schema(ALL_STRINGS_PRODUCTS).load(PRODUCTS_IN))
    return {
        "bronze.orders": _run_once(_with_ingest_metadata(orders), "orders"),
        "bronze.customers": _run_once(_with_ingest_metadata(customers), "customers"),
        "bronze.products": _run_once(_with_ingest_metadata(products), "products"),
    }
```

`create_tables` declares the three tables up front with `CREATE TABLE IF NOT EXISTS ... USING DELTA` (`raw STRING`
plus the three metadata columns), so the schema is written down rather than inferred. The CSV readers use an explicit
all-string schema because a streaming file source needs a schema, and because typing belongs to silver. The
`_metadata` column is the hidden file metadata column (file name, path, size, modification time); open-source Spark
has it for file sources, and on Databricks the [File metadata column](https://docs.databricks.com/aws/en/ingestion/file-metadata-column)
page documents the same fields.

After day 1 (`run_demo.py` prints the job log of every day; section 12.7 shows day 3), bronze has every line,
including the cut-off one and the duplicate:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> SELECT _file_name, substr(raw, 1, 60) AS raw_start, _ingested_at FROM bronze.orders ORDER BY _file_name, raw
+-------------------------+------------------------------------------------------------+-----------------------+
|_file_name               |raw_start                                                   |_ingested_at           |
+-------------------------+------------------------------------------------------------+-----------------------+
|orders_20260301_0900.json|{"order_id": 1001, "customer_id": 1, "order_ts": "2026-03-01|2026-11-11 08:59:50.832|
|orders_20260301_0900.json|{"order_id": 1002, "customer_id": 2, "order_ts": "2026-03-01|2026-11-11 08:59:50.832|
|orders_20260301_0900.json|{"order_id": 1003, "customer_id": 1, "order_ts": "2026-03-01|2026-11-11 08:59:50.832|
|orders_20260301_1800.json|{"order_id": 1002, "customer_id": 2, "order_ts": "2026-03-01|2026-11-11 08:59:50.832|
|orders_20260301_1800.json|{"order_id": 1003, "customer_id": 1, "order_ts": "2026-03-01|2026-11-11 08:59:50.832|
+-------------------------+------------------------------------------------------------+-----------------------+
```

All five rows got the same `_ingested_at`: `current_timestamp()` is fixed once per micro-batch, so it identifies the
load, not the row. The timestamp itself is the time of the run, so a re-run prints a different one; everything
else in the demo's output was identical on a second run.

### The Databricks version: Auto Loader

On Databricks the reader becomes Auto Loader (`cloudFiles`), which adds what the open-source file source lacks:
scalable file discovery (directory listing or file notification), schema inference and evolution, and the rescued
data column ([chapter 8](08-Bronze-Ingestion.md)). The direct translation of the code above keeps the raw line:

*Databricks only, not run here. Syntax from [Common data loading patterns](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/patterns) and [What is Auto Loader?](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/).*

```python
orders = (spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "text")
            .load("/Volumes/shop/bronze/landing/orders")
            .select(F.col("value").alias("raw"),
                    F.col("_metadata.file_name").alias("_file_name"),
                    F.col("_metadata.file_modification_time").alias("_file_modification_time"),
                    F.current_timestamp().alias("_ingested_at")))

(orders.writeStream
   .option("checkpointLocation", "/Volumes/shop/bronze/checkpoints/bronze_orders")
   .trigger(availableNow=True)
   .toTable("shop.bronze.orders"))
```

The more common Auto Loader shape parses JSON at bronze and lets the rescued data column catch what does not fit.
With a known schema, the patterns page's "Prevent data loss in well-structured data" example uses
`cloudFiles.schemaEvolutionMode` set to `rescue`, which "collect[s] all new fields as well as data type mismatches in
`_rescued_data`":

*Databricks only, not run here. Syntax from [Common data loading patterns](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/patterns).*

```python
(spark.readStream.format("cloudFiles")
   .schema(expected_schema)                       # all fields as STRING, items as an array of structs
   .option("cloudFiles.format", "json")
   .option("cloudFiles.schemaEvolutionMode", "rescue")
   .load("/Volumes/shop/bronze/landing/orders")
   .writeStream
   .option("checkpointLocation", "/Volumes/shop/bronze/checkpoints/bronze_orders_json")
   .toTable("shop.bronze.orders_json"))
```

With that shape, day 2's `channel` field would land in `_rescued_data` until you add it to the schema. The rescued
data column is for new fields and type mismatches; it does not hold a malformed line. The Auto Loader schema page
says that with a rescued data column "Only corrupt records fail or throw errors, such as incomplete or malformed JSON
or CSV", so a cut-off line like day 1's follows the parser mode instead (the options page: in `PERMISSIVE` mode the
raw text is kept only if the schema has a `columnNameOfCorruptRecord` field, default `_corrupt_record`). Keeping the
raw text, as this project does, sidesteps both questions. Two more notes. Switching from the open-source file source
to Auto Loader changes the source of the stream, and the Spark Structured Streaming guide lists a change of source
type between restarts as "not allowed", so the Auto Loader stream gets a new checkpoint, and you decide which files
it should skip (`cloudFiles.includeExistingFiles` is `true` by default, which would load every existing file again).
And on Databricks you can write the same bronze table in SQL with `STREAM read_files(...)` inside a streaming table
(section 12.11).

!!! tip "In the interview"
    **"How do you make sure each file is loaded exactly once?"** The stream's checkpoint records which files were
    read, so a rerun with `availableNow` reads only new files. The Delta sink records which micro-batch it has
    committed, so a batch that is retried after a failure is not written twice: exactly-once writes, not just
    at-least-once. On Databricks the reader is Auto Loader (`cloudFiles`); the open-source file source behaves the
    same for this purpose. I keep bronze as raw as possible (the line as a string,
    plus file name and ingest time) so nothing is dropped before silver can judge it.

## 12.4 Silver orders: parse, check, quarantine, deduplicate, MERGE

*Level: intermediate.*

Silver orders is where most of the work happens. Each run reads only the new bronze rows (a stream over the bronze
Delta table, again `availableNow` with a checkpoint) and hands each micro-batch to a `foreachBatch` function, because
`MERGE` is not a streaming sink: the Databricks foreachBatch page says "You must use `foreachBatch` for Delta Lake
merge operations in Structured Streaming". The function does four things, each safe to repeat.

### Step 0: parse, type and list the rules each line breaks

One SQL query parses the JSON with an explicit all-string schema, types each field with `try_cast` (a bad value
becomes `NULL` instead of failing the job, [chapter 9](09-Building-Silver.md)), and builds an array of the rules each
row breaks:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
ORDER_JSON_SCHEMA = """order_id STRING, customer_id STRING, order_ts STRING, status STRING,
    amount STRING, currency STRING, updated_at STRING, channel STRING,
    items ARRAY<STRUCT<product_id: STRING, qty: STRING, unit_price: STRING>>,
    _corrupt_record STRING"""   # from_json puts a line it cannot parse here (PERMISSIVE mode)

CHECK_ORDERS = """
WITH parsed AS (
  SELECT raw, _file_name, _ingested_at, from_json(raw, '__ORDER_JSON_SCHEMA__') AS j
  FROM {src}                          -- filled in with CHECK_ORDERS.format(src=...)
),
typed AS (
  SELECT raw, _file_name, _ingested_at, j,
         try_cast(j.order_id    AS INT)            AS order_id,
         try_cast(j.customer_id AS INT)            AS customer_id,
         try_cast(j.order_ts    AS TIMESTAMP)      AS order_ts,
         upper(trim(j.status))                     AS status,
         try_cast(j.amount      AS DECIMAL(10,2))  AS amount,
         upper(trim(j.currency))                   AS currency,
         lower(trim(j.channel))                    AS channel,
         try_cast(j.updated_at  AS TIMESTAMP)      AS updated_at,
         transform(j.items, i -> named_struct(
             'product_id', try_cast(i.product_id AS INT),
             'qty',        try_cast(i.qty AS INT),
             'unit_price', try_cast(i.unit_price AS DECIMAL(10,2)))) AS items
  FROM parsed
)
SELECT * EXCEPT (j),
  CASE WHEN j._corrupt_record IS NOT NULL THEN array('malformed_json')
  ELSE filter(array(
    CASE WHEN order_id    IS NULL THEN 'order_id_missing' END,
    CASE WHEN customer_id IS NULL THEN 'customer_id_missing' END,
    CASE WHEN order_ts    IS NULL THEN 'order_ts_invalid' END,
    CASE WHEN updated_at  IS NULL THEN 'updated_at_invalid' END,
    CASE WHEN amount IS NULL OR amount < 0 THEN 'amount_invalid' END,
    CASE WHEN currency IS NULL OR currency NOT IN ('CAD', 'USD') THEN 'currency_invalid' END,
    CASE WHEN items IS NULL OR size(items) = 0 THEN 'no_items' END,
    CASE WHEN exists(items, i -> i.product_id IS NULL OR i.qty IS NULL OR i.qty <= 0
                                 OR i.unit_price IS NULL OR i.unit_price < 0) THEN 'item_invalid' END,
    CASE WHEN amount <> aggregate(items, CAST(0 AS DECIMAL(12,2)),
                                  (acc, i) -> CAST(acc + i.qty * i.unit_price AS DECIMAL(12,2)))
         THEN 'amount_mismatch' END
  ), r -> r IS NOT NULL) END AS failed_rules
FROM typed
""".replace("__ORDER_JSON_SCHEMA__", ORDER_JSON_SCHEMA)
```

Four details matter:

- **Malformed lines.** `from_json` in its default `PERMISSIVE` mode does not return `NULL` for a line it cannot parse:
  it returns a struct whose fields are all `NULL`. A first version of this query tested `j IS NULL` and flagged the
  cut-off line with seven "missing" rules instead of the real reason. Adding a `_corrupt_record STRING` field to the
  schema makes `from_json` put the unparsable text there, so the rule is exact. (Checked here: the struct for the
  cut-off line was `{NULL, NULL, {"order_id": 1003, "amo}`.)
- **Numbers in a string schema.** The JSON has `"order_id": 1001` (a number) but the schema says `STRING`; Spark's JSON
  parser returns the number's text, and `try_cast` types it. Reading everything as a string first means a type change
  in the source becomes a quarantined row, not a failed job.
- **Higher-order functions** (`transform`, `exists`, `filter`, `aggregate`, [chapter 18](18-Semi-Structured-Data.md))
  check the nested items without exploding them first.
- **The `aggregate` type trap.** The first run failed with `DATATYPE_MISMATCH.UNEXPECTED_INPUT_TYPE`: "The third
  parameter requires the "DECIMAL(12,2)" type, however ... has the type "DECIMAL(22,2)"". `acc + qty * unit_price`
  widens the decimal, and `aggregate` requires the merge function to return exactly the start value's type. The
  `CAST(... AS DECIMAL(12,2))` inside the lambda fixes it.

### Steps 1 to 4: the foreachBatch function

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def upsert_orders(batch_df, batch_id):
    """foreachBatch function for bronze.orders. Safe to run twice on the same rows."""
    s = batch_df.sparkSession
    batch_df.persist()        # the batch is read by several statements: read the source once
    batch_df.createOrReplaceTempView("bronze_batch")
    s.sql(f"CREATE OR REPLACE TEMP VIEW checked AS {CHECK_ORDERS.format(src='bronze_batch')}")

    # 1. bad events to quarantine, with the reasons; insert-only, so a replay adds nothing
    s.sql("""
        MERGE INTO silver.orders_quarantine q
        USING (SELECT DISTINCT raw, failed_rules, _file_name, _ingested_at, current_timestamp() AS _quarantined_at
               FROM checked WHERE size(failed_rules) > 0) b
        ON q.raw = b.raw AND q._file_name = b._file_name
        WHEN NOT MATCHED THEN INSERT *""")

    # 2. good events: the latest version of each order inside this batch
    s.sql("""
        CREATE OR REPLACE TEMP VIEW latest AS
        SELECT * FROM checked
        WHERE size(failed_rules) = 0
        QUALIFY row_number() OVER (PARTITION BY order_id
                                   ORDER BY updated_at DESC, _ingested_at DESC, _file_name DESC) = 1""")

    # 3. orders: insert new ones; update only if the incoming version is newer (out-of-order guard)
    s.sql("""
        MERGE INTO silver.orders t
        USING (SELECT order_id, customer_id, order_ts, to_date(order_ts) AS order_date, status, amount,
                      currency, channel, updated_at, _file_name, _ingested_at
               FROM latest) s
        ON t.order_id = s.order_id
        WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *""")

    # 4. items: replace the lines of every order whose version won step 3, in one MERGE:
    #    new lines are upserted, lines the new version no longer has are deleted
    s.sql("""
        MERGE INTO silver.order_items t
        USING (
          WITH accepted AS (            -- versions that are now in silver.orders
            SELECT l.* FROM latest l
            JOIN silver.orders o ON o.order_id = l.order_id AND o.updated_at = l.updated_at
          ),
          new_lines AS (
            SELECT a.order_id, i.product_id, i.qty, i.unit_price,
                   CAST(i.qty * i.unit_price AS DECIMAL(12,2)) AS line_amount,
                   a.updated_at AS order_updated_at, false AS _delete
            FROM accepted a LATERAL VIEW explode(a.items) x AS i
          ),
          gone_lines AS (               -- lines in silver that the new version dropped
            SELECT t.*, true AS _delete
            FROM silver.order_items t
            JOIN accepted a ON a.order_id = t.order_id
            LEFT ANTI JOIN new_lines n ON n.order_id = t.order_id AND n.product_id = t.product_id
          )
          SELECT * FROM new_lines UNION ALL SELECT * FROM gone_lines
        ) s
        ON t.order_id = s.order_id AND t.product_id = s.product_id
        WHEN MATCHED AND s._delete THEN DELETE
        WHEN MATCHED AND s.order_updated_at > t.order_updated_at THEN
          UPDATE SET qty = s.qty, unit_price = s.unit_price, line_amount = s.line_amount,
                     order_updated_at = s.order_updated_at
        WHEN NOT MATCHED AND NOT s._delete THEN
          INSERT (order_id, product_id, qty, unit_price, line_amount, order_updated_at)
          VALUES (s.order_id, s.product_id, s.qty, s.unit_price, s.line_amount, s.order_updated_at)""")
    batch_df.unpersist()
```

Why each step is written this way:

1. **Quarantine is insert-only, keyed on the raw text and the file.** Replaying a batch (a lost checkpoint, a full
   rebuild) adds nothing. Each row keeps the original line and an array of reasons, so someone can fix the source and
   replay it.
2. **Dedup inside the batch first.** One batch can hold the same order twice (day 1 has 1002 twice, both in the same
   run). `MERGE` fails with "multiple source rows matched" if two source rows hit one target row
   ([chapter 7](07-Medallion-Architecture.md) runs that error), so the source must be unique per key. The tie-breakers
   after `updated_at` make the choice deterministic.
3. **The out-of-order guard** `s.updated_at > t.updated_at` makes an older version arriving later (day 3's stale 1002)
   a no-op, and makes a replay of the same version a no-op too. `>` rather than `>=` is what makes the replay touch
   nothing ([chapter 9](09-Building-Silver.md), "Why `>` and not `>=`").
4. **Order lines follow their order.** Lines are children of an order version, so they are written only for versions
   that actually won step 3 (the join back to `silver.orders` on `updated_at`). Joining back, instead of remembering
   "what step 3 accepted" in Python, keeps the step correct if the job dies between steps 3 and 4: on the retry, step
   3 changes nothing and step 4 still sees the accepted version. The `gone_lines` part deletes lines that a correction
   removed; without it a stale line would stay and the order's lines would no longer add up to its amount (practice
   question 12 shows the case run).

`batch_df.persist()` is there because the batch feeds several statements; without it each statement re-reads the
source. An earlier run of this project, whose output was not kept, showed the stream reporting 15 input rows for a
5-row batch (3 statements × 5 rows), as if `numInputRows` counted every read of the source; treat that as not
verified.

The same "latest version, then explode the items" logic in the DataFrame API, which interviews often ask for
(practice question 17 checks that it returns exactly the rows in `silver.order_items`):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql import functions as F
from pyspark.sql.window import Window

w = Window.partitionBy("order_id").orderBy(F.col("updated_at").desc(), F.col("_ingested_at").desc(),
                                          F.col("_file_name").desc())
latest_df = (checked.where(F.size("failed_rules") == 0)
                    .withColumn("rn", F.row_number().over(w))
                    .where("rn = 1").drop("rn"))
lines_df = (latest_df.select("order_id", F.explode("items").alias("i"))
                     .select("order_id", "i.product_id", "i.qty", "i.unit_price",
                             (F.col("i.qty") * F.col("i.unit_price")).cast("decimal(12,2)").alias("line_amount")))
```

After day 1, silver holds three orders, three lines and one quarantined event:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> SELECT order_id, customer_id, order_ts, status, amount, currency, channel, updated_at, _file_name FROM silver.orders ORDER BY order_id
+--------+-----------+-------------------+------+------+--------+-------+-------------------+-------------------------+
|order_id|customer_id|order_ts           |status|amount|currency|channel|updated_at         |_file_name               |
+--------+-----------+-------------------+------+------+--------+-------+-------------------+-------------------------+
|1001    |1          |2026-03-01 10:15:00|PLACED|59.90 |CAD     |NULL   |2026-03-01 10:15:00|orders_20260301_0900.json|
|1002    |2          |2026-03-01 11:05:00|PLACED|249.00|USD     |NULL   |2026-03-01 11:05:00|orders_20260301_1800.json|
|1003    |1          |2026-03-01 13:40:00|PLACED|189.50|CAD     |NULL   |2026-03-01 13:40:00|orders_20260301_1800.json|
+--------+-----------+-------------------+------+------+--------+-------+-------------------+-------------------------+

>>> SELECT order_id, product_id, qty, unit_price, line_amount FROM silver.order_items ORDER BY ALL
+--------+----------+---+----------+-----------+
|order_id|product_id|qty|unit_price|line_amount|
+--------+----------+---+----------+-----------+
|1001    |3         |2  |29.95     |59.90      |
|1002    |1         |1  |249.00    |249.00     |
|1003    |2         |1  |189.50    |189.50     |
+--------+----------+---+----------+-----------+

>>> SELECT substr(raw, 1, 50) AS raw_start, failed_rules, _file_name FROM silver.orders_quarantine
+--------------------------------------------------+----------------+-------------------------+
|raw_start                                         |failed_rules    |_file_name               |
+--------------------------------------------------+----------------+-------------------------+
|{"order_id": 1003, "customer_id": 1, "order_ts": "|[malformed_json]|orders_20260301_0900.json|
+--------------------------------------------------+----------------+-------------------------+
```

Five bronze lines became three orders: the duplicate 1002 collapsed into one row (the copy from the evening file won
the tie on `_file_name`), the cut-off 1003 went to quarantine with the exact reason, and the complete 1003 from the
evening file became a normal order. The `channel` column is `NULL` for day 1: the field did not exist yet.

!!! warning "A quarantine is only useful if someone reads it"
    Quarantined rows are invisible to every report. Give the table an owner, alert on its growth (the silver checks
    below count it), and keep the raw text so a fixed row can be replayed. The silver reconciliation check
    (`bronze = valid + quarantined`) is what proves nothing fell between the two.

## 12.5 Silver customers and products: SCD Type 2 and Type 1

*Level: intermediate.*

Customers arrive as a full snapshot every day. Silver keeps every version (SCD Type 2) with the staged `MERGE` of
[chapter 9](09-Building-Silver.md): each changed customer is fed twice, once with its key (to close the current row)
and once with a `NULL` key (to insert the new current row). The statement is chapter 9's, pointed at
`silver.customers`. What this project adds is the loop around it:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def upsert_customers(batch_df, batch_id):
    """foreachBatch function for bronze.customers. A batch can hold several daily snapshots
    (for example during a rebuild); they are applied one by one, oldest first, or history is lost."""
    s = batch_df.sparkSession
    batch_df.persist()        # the batch is read by several statements: read the source once
    batch_df.createOrReplaceTempView("customers_batch")
    s.sql("""
        CREATE OR REPLACE TEMP VIEW customers_clean AS
        SELECT try_cast(customer_id AS INT)            AS customer_id,
               trim(name)                              AS name,
               lower(trim(email))                      AS email,
               trim(city)                              AS city,
               upper(trim(country))                    AS country,
               try_cast(updated_at AS TIMESTAMP)       AS updated_at,
               to_date(regexp_extract(_file_name, '([0-9]{8})', 1), 'yyyyMMdd') AS snapshot_date
        FROM customers_batch""")
    dates = [r.snapshot_date for r in
             s.sql("SELECT DISTINCT snapshot_date FROM customers_clean ORDER BY 1").collect()]
    for d in dates:
        s.sql(f"""
            CREATE OR REPLACE TEMP VIEW snapshot_rows AS
            SELECT customer_id, name, email, city, country, updated_at
            FROM customers_clean
            WHERE snapshot_date = DATE'{d}' AND customer_id IS NOT NULL AND updated_at IS NOT NULL
            QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY updated_at DESC) = 1""")
        s.sql(SCD2_MERGE)
    batch_df.unpersist()
```

**Why the loop.** On a normal day the batch holds one snapshot. During a rebuild (section 12.9) it holds all of them.
If the three snapshots went into one `MERGE`, the dedup would keep only Ana's latest row (Banff) and her Calgary
version would never exist: the rebuild would silently produce less history than the daily runs did. Applying the
snapshots one at a time, in date order, gives the same history whatever the batch size. The cleaning (`trim`,
`lower(email)`) happens before the change check, so day 3's ` Ben.Okafor@Example.com ` becomes one real change
(a new address), and a snapshot that only differs by stray spaces would cause none.

Products are a short reference list: SCD Type 1, a `MERGE` that updates a product only when a value changed
(`WHEN MATCHED AND NOT (t.name <=> s.name AND ...)`), so a re-sent identical file touches nothing.

!!! tip "In the interview"
    **"Your customer source is a daily full snapshot, not a change feed. How do you build SCD Type 2?"** Compare each
    snapshot with the current rows and close and open versions with a staged `MERGE` (changed rows fed twice, once
    with a `NULL` merge key), with null-safe change detection (`<=>`) and an `updated_at > valid_from` guard. Apply
    snapshots one at a time in order, or a backfill collapses history. Deletes need a rule (a customer missing from
    the snapshot), which this `MERGE` does not have. In a Lakeflow pipeline (formerly Delta Live Tables) the built-in
    answer is `AUTO CDC ... FROM SNAPSHOT` (the `AUTO CDC` APIs replace the `APPLY CHANGES` APIs, with the same
    syntax), which compares snapshots for you and treats keys absent from a snapshot as deleted ([The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc)).

## 12.6 Gold: a star schema and two aggregates

*Level: intermediate.*

Gold answers the two business questions. A **star schema** ([chapter 10](10-Building-Gold.md), and
[Data modelling](../../databases/sql/19-Data-Modelling.md) in the SQL course) puts the measurable events in a fact
table at a stated grain and the descriptive attributes in dimension tables around it.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 310" role="img" aria-label="Star schema: fact_order_lines in the center, one row per order line, linked to dim_customer (SCD 2, customer_sk), dim_product (product_id) and dim_date (date_key); daily_sales and customer_ltv are built from the fact">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="220" y="100" width="200" height="118" rx="5" stroke-width="2.5"/>
<rect x="10" y="80" width="175" height="122" rx="5"/>
<rect x="455" y="90" width="175" height="76" rx="5"/>
<rect x="235" y="250" width="170" height="52" rx="5"/>
<rect x="190" y="12" width="120" height="44" rx="5" stroke-dasharray="5 3"/>
<rect x="330" y="12" width="120" height="44" rx="5" stroke-dasharray="5 3"/>
<line x1="220" y1="150" x2="185" y2="140"/>
<line x1="420" y1="140" x2="455" y2="128"/>
<line x1="320" y1="218" x2="320" y2="250"/>
<line x1="270" y1="100" x2="255" y2="60" stroke-dasharray="4 3"/>
<line x1="370" y1="100" x2="385" y2="60" stroke-dasharray="4 3"/>
</g>
<g fill="currentColor">
<polygon points="255,56 251,66 260,64"/>
<polygon points="385,56 380,64 389,66"/>
</g>
<g fill="currentColor" font-size="14" font-weight="bold" text-anchor="middle">
<text x="320" y="120">fact_order_lines</text>
<text x="97" y="100">dim_customer</text>
<text x="542" y="110">dim_product</text>
<text x="320" y="270">dim_date</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="320" y="140">grain: one order line</text>
<text x="320" y="158">order_id, product_id</text>
<text x="320" y="176">customer_sk, date_key</text>
<text x="320" y="194">qty, unit_price, line_amount</text>
<text x="320" y="211">currency, status</text>
<text x="97" y="119">(SCD 2) customer_sk</text>
<text x="97" y="137">customer_id, name,</text>
<text x="97" y="155">email, city, country</text>
<text x="97" y="173">valid_from, valid_to</text>
<text x="97" y="191">-1 = unknown customer</text>
<text x="542" y="130">(SCD 1) product_id</text>
<text x="542" y="148">name, category, price</text>
<text x="320" y="290">date_key, day_name, ...</text>
<text x="250" y="31">daily_sales</text>
<text x="250" y="48">date, category</text>
<text x="390" y="31">customer_ltv</text>
<text x="390" y="48">customer, currency</text>
</g>
</svg>
<figcaption>Figure 12.2. The gold star schema. The fact table has one row per order line and points at the customer
version that was valid when the order was placed. The two aggregates (dashed) are built from the fact, not from
silver, so they cannot disagree with it.</figcaption>
</figure>

### Dimensions with keys that survive a rebuild

`dim_date` is a calendar (one row per day of 2026, inserted once). `dim_product` copies silver products. The
interesting one is `dim_customer`, one row per customer **version**, with a surrogate key:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- customer_sk is a hash of (customer_id, valid_from): the same version always gets the same key,
-- so a full rebuild gives the same keys and facts never point at the wrong version.
-- customer_sk = -1 is the "unknown customer" member: facts whose customer is not in silver use it.
MERGE INTO gold.dim_customer t
USING (
  SELECT xxhash64(customer_id, valid_from) AS customer_sk, customer_id, name, email, city, country,
         valid_from, valid_to, is_current
  FROM silver.customers
  UNION ALL
  SELECT -1, NULL, 'Unknown customer', NULL, NULL, NULL, NULL, NULL, false
) s
ON t.customer_sk = s.customer_sk
WHEN MATCHED AND NOT (t.email <=> s.email AND t.city <=> s.city AND t.name <=> s.name
                      AND t.country <=> s.country AND t.valid_to <=> s.valid_to
                      AND t.is_current <=> s.is_current) THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE
```

Three design choices to defend:

- **A hash key, not an identity column.** An identity column (`GENERATED ALWAYS AS IDENTITY`) assigns values as rows
  are inserted, so a rebuild can hand out different values to the same customer version, and every fact would need
  re-keying. A hash
  of the natural key plus `valid_from` is the same on every run. The trade-off is a 64-bit hash: collisions are
  possible in theory; a uniqueness check on `customer_sk` (practice question 15) is the safety net.
- **An unknown member.** Order 1005 is for customer 99, who is in no snapshot. Dropping the order would understate
  revenue; a `NULL` key would vanish from inner joins. Pointing it at `-1, 'Unknown customer'` keeps the revenue in
  every report and makes the problem countable (a WARN check).
- **The `MERGE` touches only real changes.** The change condition and `WHEN NOT MATCHED BY SOURCE THEN DELETE` keep the
  dimension equal to silver while a rerun updates zero rows (section 12.9 shows the history).

### Facts: recompute only the dates that changed

**The problem.** A correction on March 3 changes a March 1 order, so "load today's orders" is not enough: gold must
recompute every date that any changed order belongs to, and only those, because rewriting all history every day
does not scale.

**The tool.** Silver orders has Delta's **change data feed** turned on
(`TBLPROPERTIES (delta.enableChangeDataFeed = true)`), so a stream can read just the rows that changed since its last
run ([chapter 9](09-Building-Silver.md)). The gold stream collects their `order_date` values and replaces exactly those
dates with `INSERT INTO ... REPLACE WHERE`, which deletes the rows matching the predicate and inserts the query
result in one atomic commit:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def refresh_dates(spark, dates):
    """Recompute the fact rows and daily sales of the given order dates, replacing exactly those dates."""
    if not dates:
        return
    in_list = ", ".join(f"DATE'{d}'" for d in sorted(dates))
    spark.sql(f"""
        INSERT INTO gold.fact_order_lines
        REPLACE WHERE order_date IN ({in_list})
        SELECT i.order_id, i.product_id,
               coalesce(c.customer_sk, -1)                         AS customer_sk,
               o.customer_id,
               CAST(date_format(o.order_date, 'yyyyMMdd') AS INT)  AS date_key,
               o.order_date, o.order_ts, o.status, o.currency,
               i.qty, i.unit_price, i.line_amount
        FROM silver.order_items i
        JOIN silver.orders o ON o.order_id = i.order_id
        LEFT JOIN (SELECT *, valid_from = min(valid_from) OVER (PARTITION BY customer_id) AS is_first
                   FROM gold.dim_customer) c
          ON  c.customer_id = o.customer_id                -- the customer version valid at order time;
          AND (o.order_ts >= c.valid_from OR c.is_first)   -- an order older than the first version we
          AND (o.order_ts < c.valid_to OR c.valid_to IS NULL)   -- know of gets that first version
        WHERE o.order_date IN ({in_list})""")
    spark.sql(f"""
        INSERT INTO gold.daily_sales
        REPLACE WHERE order_date IN ({in_list})
        SELECT f.order_date, p.category, f.currency,
               count(DISTINCT f.order_id) AS orders, sum(f.qty) AS units, sum(f.line_amount) AS revenue
        FROM gold.fact_order_lines f
        JOIN gold.dim_product p ON p.product_id = f.product_id
        WHERE f.order_date IN ({in_list}) AND f.status <> 'CANCELLED'
        GROUP BY ALL""")


def _refresh_changed_dates(batch_df, batch_id):
    """foreachBatch over silver.orders' change feed: which order dates changed since the last run?
    Pre-images count too, so an order that moved to another date refreshes both dates."""
    dates = [r.order_date for r in batch_df.select("order_date").distinct().collect()]
    refresh_dates(batch_df.sparkSession, dates)


def refresh_facts(spark):
    q = (spark.readStream
           .option("readChangeFeed", "true")
           .table("silver.orders")
           .writeStream
           .foreachBatch(_refresh_changed_dates)
           .option("checkpointLocation", checkpoint("gold_facts"))
           .trigger(availableNow=True)
           .start())
    q.awaitTermination()
    return sum(p["numInputRows"] for p in q.recentProgress)
```

Points worth saying out loud:

- **The point-in-time join.** A fact row gets the customer version valid at `order_ts`: the half-open interval
  `valid_from <= order_ts < valid_to` of chapter 9. Ana's day-1 orders point at her Calgary version and her day-2
  order at her Banff version (output below). The `is_first` branch handles an order older than the first version
  silver knows about (a customer whose first snapshot arrived late): it takes that first version rather than
  falling to `-1`.
- **`REPLACE WHERE` rules.** The INSERT page says "By default, every row that `query` returns must match
  `boolean_expression`. If any row falls outside it, the `INSERT` fails and writes nothing", so the query filters on
  the same date list. Rerunning the same dates rewrites the same rows; nothing is appended twice.
- **The first run of the stream.** When a change-feed stream starts with no checkpoint, the change data feed page
  says it "returns the latest snapshot of the table as `INSERT` records and then returns future changes". That is
  what makes a full rebuild of gold work with the same code (section 12.9).
- **Aggregates come from the fact.** `daily_sales` is computed from `fact_order_lines` joined to `dim_product`, so
  the two cannot disagree, and a gold check proves it.

`customer_ltv` is small (one row per customer and currency), so it is recomputed in full every run and written with a
change-detecting `MERGE`, like the dimensions. Revenue is kept per currency: adding CAD to USD would be a silent error,
and an interviewer who sees a single "revenue" column across currencies will ask about it.

After day 2, the point-in-time join at work (customer 99 is the unknown member):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> SELECT f.order_id, f.order_ts, f.customer_id, f.customer_sk, d.city AS city_at_order_time FROM gold.fact_order_lines f JOIN gold.dim_customer d ON d.customer_sk = f.customer_sk WHERE f.customer_id IN (1, 99) ORDER BY f.order_id, f.product_id
+--------+-------------------+-----------+--------------------+------------------+
|order_id|order_ts           |customer_id|customer_sk         |city_at_order_time|
+--------+-------------------+-----------+--------------------+------------------+
|1001    |2026-03-01 10:15:00|1          |-6086522907012478620|Calgary           |
|1003    |2026-03-01 13:40:00|1          |-6086522907012478620|Calgary           |
|1005    |2026-03-02 14:20:00|99         |-1                  |NULL              |
|1007    |2026-03-02 18:30:00|1          |-4318048261544325655|Banff             |
|1007    |2026-03-02 18:30:00|1          |-4318048261544325655|Banff             |
+--------+-------------------+-----------+--------------------+------------------+
```

Order 1007 appears twice because it has two lines (products 1 and 3), and the fact has one row per line. Both rows
point at the Banff version: Ana moved at 08:00 on March 2, and the order was placed at 18:30 that day.

!!! tip "In the interview"
    **"How do you load a fact table incrementally when old facts can change?"** Find what changed, not what is new:
    I read the change data feed of the silver table, collect the affected business dates (from pre- and post-images,
    so a moved order refreshes both dates), and replace exactly those dates with `INSERT INTO ... REPLACE WHERE`, one
    atomic commit per run. Facts look up the dimension version valid at the event time, use a deterministic surrogate
    key so a rebuild gives the same keys, and point unknown customers at a `-1` member so revenue is never dropped.

## 12.7 Data tests after every layer

*Level: intermediate.*

**The problem.** A pipeline can succeed and still be wrong: a join that duplicates rows, a filter that drops a
day, a `MERGE` that never deletes. Nobody notices until a report disagrees with finance.

**The tool.** A small suite of checks, each a SQL query that returns one number (a count of bad rows, or a difference
between two counts) and the value it must have. A **FAIL** check raises an exception, which fails the job task and
stops everything downstream; a **WARN** check is printed and the run continues. The suite runs after each layer, so a
problem is caught at the layer that caused it:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def silver_checks():
    checked_all = CHECK_ORDERS.format(src="bronze.orders")
    return [
        ("bronze.orders = valid + quarantined",
         f"""SELECT (SELECT count(*) FROM bronze.orders)
                  - (SELECT count_if(size(failed_rules) = 0) FROM ({checked_all}))
                  - (SELECT count(*) FROM silver.orders_quarantine)""", 0, "FAIL"),
        ("silver.orders = distinct valid order_ids",
         f"""SELECT (SELECT count(*) FROM silver.orders)
                  - (SELECT count(DISTINCT order_id) FROM ({checked_all}) WHERE size(failed_rules) = 0)""",
         0, "FAIL"),
        ("duplicate order_id in silver.orders",
         "SELECT count(*) - count(DISTINCT order_id) FROM silver.orders", 0, "FAIL"),
        ("orders whose amount <> sum of their lines",
         """SELECT count(*) FROM silver.orders o
            LEFT JOIN (SELECT order_id, sum(line_amount) AS lines FROM silver.order_items GROUP BY order_id) i
              ON i.order_id = o.order_id
            WHERE i.lines IS NULL OR o.amount <> i.lines""", 0, "FAIL"),
        ("customer versions with a gap or overlap",
         """SELECT count(*) FROM (
              SELECT valid_to, lead(valid_from) OVER (PARTITION BY customer_id ORDER BY valid_from) AS next_from
              FROM silver.customers)
            WHERE NOT (valid_to <=> next_from)""", 0, "FAIL"),
        ("orders for an unknown customer (flagged, kept)",
         "SELECT count(*) FROM silver.orders o LEFT ANTI JOIN silver.customers c ON c.customer_id = o.customer_id",
         0, "WARN"),
        # ... and: duplicate order lines, lines without an order, customers with <> 1 current row (checks.py)
    ]


def run_checks(spark, layer):
    rows, failed = [], []
    for name, query, expected, level in LAYERS[layer]():
        got = spark.sql(query).first()[0]
        status = "PASS" if got == expected else level
        rows.append((layer, name, got, expected, status))
        if status == "FAIL":
            failed.append(f"{name}: got {got}, expected {expected}")
    # ... print one line per check ...
    if failed:
        raise DataTestError(f"{len(failed)} {layer} check(s) failed: " + "; ".join(failed))
```

The full list, by layer:

| Layer | Check | Level | Catches |
| --- | --- | --- | --- |
| bronze | rows in bronze = data lines in the landing files (per source) | FAIL | a file skipped or loaded twice |
| bronze | rows without file name or ingest time | FAIL | lineage lost |
| bronze | JSON fields not in the contract | WARN | schema drift (a new field nobody announced) |
| silver | bronze = valid + quarantined | FAIL | rows that vanished between the layers |
| silver | silver orders = distinct valid order ids | FAIL | dedup or `MERGE` bugs |
| silver | unique `order_id`; unique (`order_id`, `product_id`) | FAIL | duplicates |
| silver | amount = sum of lines; no line without an order | FAIL | parent and children out of step |
| silver | one current row per customer; no gaps or overlaps in versions | FAIL | SCD Type 2 bugs |
| silver | orders for an unknown customer | WARN | referential problems, kept and flagged |
| gold | unique fact grain; fact rows = silver lines | FAIL | fan-out joins, missed dates |
| gold | facts without a `dim_customer`, `dim_product` or `dim_date` row | FAIL | orphan facts |
| gold | fact revenue = silver order amounts, per currency | FAIL | lost or doubled revenue |
| gold | `daily_sales` revenue = fact revenue, per currency | FAIL | aggregate out of step |
| gold | facts pointing at the unknown customer | WARN | late or missing dimension rows |

The day 3 run of the whole job, with every check:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
[bronze] done
    bronze.orders: 4 rows read
    bronze.customers: 5 rows read
    bronze.products: 0 rows read
  PASS  bronze  every landing line is in bronze.orders           got 14, expected 14
  PASS  bronze  every landing row is in bronze.customers         got 14, expected 14
  PASS  bronze  every landing row is in bronze.products          got 5, expected 5
  PASS  bronze  bronze rows without file name or ingest time     got 0, expected 0
  PASS  bronze  order fields not in the contract (schema drift)  got 0, expected 0
[silver] done
    bronze.products  -> silver.products: 0 rows read
    bronze.customers -> silver.customers: 5 rows read
    bronze.orders    -> silver.orders/order_items/orders_quarantine: 4 rows read
  PASS  silver  bronze.orders = valid + quarantined                     got 0, expected 0
  PASS  silver  silver.orders = distinct valid order_ids                got 0, expected 0
  PASS  silver  duplicate order_id in silver.orders                     got 0, expected 0
  PASS  silver  duplicate (order_id, product_id) in silver.order_items  got 0, expected 0
  PASS  silver  orders whose amount <> sum of their lines               got 0, expected 0
  PASS  silver  order_items without an order                            got 0, expected 0
  PASS  silver  customers with <> 1 current row                         got 0, expected 0
  PASS  silver  customer versions with a gap or overlap                 got 0, expected 0
  WARN  silver  orders for an unknown customer (flagged, kept)          got 1, expected 0
[gold] done
    silver.orders change rows -> gold facts: 3 rows read
  PASS  gold    duplicate (order_id, product_id) in fact_order_lines   got 0, expected 0
  PASS  gold    fact rows - silver.order_items rows                    got 0, expected 0
  PASS  gold    facts with no dim_customer row                         got 0, expected 0
  PASS  gold    facts with no dim_product row                          got 0, expected 0
  PASS  gold    facts with no dim_date row                             got 0, expected 0
  PASS  gold    currencies where fact revenue <> silver order amounts  got 0, expected 0
  PASS  gold    currencies where daily_sales revenue <> fact revenue   got 0, expected 0
  WARN  gold    facts pointing at the unknown customer (-1)            got 1, expected 0
```

The two WARNs are the unknown customer 99, kept and flagged at both layers. Everything else reconciles: 14 bronze
order lines = 12 valid events + 2 quarantined, and the 12 valid events hold 8 distinct orders (1001 to 1007 and 1009).

**Failing loudly.** To see a FAIL, the demo appends a copy of order 1009 to `silver.orders`, the kind of thing a
hand-run `INSERT` or a job that used `append` instead of `MERGE` does. The silver checks stop the run, and Delta's
`RESTORE` puts the table back:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
good_version = latest_version("silver.orders")
sql("INSERT INTO silver.orders SELECT * FROM silver.orders WHERE order_id = 1009")
try:
    run_checks(spark, "silver")
except DataTestError as e:
    print(f"DataTestError: {e}")
sql(f"RESTORE TABLE silver.orders TO VERSION AS OF {good_version}")
history("silver.orders")           # version, operation and row counts per commit (section 12.8)
run_checks(spark, "silver")        # the same checks, after the restore
```

```text
  PASS  silver  bronze.orders = valid + quarantined                     got 0, expected 0
  FAIL  silver  silver.orders = distinct valid order_ids                got 1, expected 0
  FAIL  silver  duplicate order_id in silver.orders                     got 1, expected 0
  PASS  silver  duplicate (order_id, product_id) in silver.order_items  got 0, expected 0
  PASS  silver  orders whose amount <> sum of their lines               got 0, expected 0
  PASS  silver  order_items without an order                            got 0, expected 0
  PASS  silver  customers with <> 1 current row                         got 0, expected 0
  PASS  silver  customer versions with a gap or overlap                 got 0, expected 0
  WARN  silver  orders for an unknown customer (flagged, kept)          got 1, expected 0
DataTestError: 2 silver check(s) failed: silver.orders = distinct valid order_ids: got 1, expected 0; duplicate order_id in silver.orders: got 1, expected 0
>>> SELECT version, operation, operationMetrics['numSourceRows'] AS source_rows, operationMetrics['numTargetRowsInserted'] AS inserted, operationMetrics['numTargetRowsUpdated'] AS updated, operationMetrics['numTargetRowsDeleted'] AS deleted, operationMetrics['numOutputRows'] AS output_rows FROM history_silver_orders ORDER BY version
+-------+------------+-----------+--------+-------+-------+-----------+
|version|operation   |source_rows|inserted|updated|deleted|output_rows|
+-------+------------+-----------+--------+-------+-------+-----------+
|0      |CREATE TABLE|NULL       |NULL    |NULL   |NULL   |NULL       |
|1      |MERGE       |3          |3       |0      |0      |3          |
|2      |MERGE       |5          |4       |1      |0      |7          |
|3      |MERGE       |3          |1       |1      |0      |8          |
|4      |WRITE       |NULL       |NULL    |NULL   |NULL   |1          |
|5      |RESTORE     |NULL       |NULL    |NULL   |NULL   |NULL       |
+-------+------------+-----------+--------+-------+-------+-----------+

  PASS  silver  bronze.orders = valid + quarantined                     got 0, expected 0
  PASS  silver  silver.orders = distinct valid order_ids                got 0, expected 0
  PASS  silver  duplicate order_id in silver.orders                     got 0, expected 0
  PASS  silver  duplicate (order_id, product_id) in silver.order_items  got 0, expected 0
  PASS  silver  orders whose amount <> sum of their lines               got 0, expected 0
  PASS  silver  order_items without an order                            got 0, expected 0
  PASS  silver  customers with <> 1 current row                         got 0, expected 0
  PASS  silver  customer versions with a gap or overlap                 got 0, expected 0
  WARN  silver  orders for an unknown customer (flagged, kept)          got 1, expected 0
```

`RESTORE` is itself a new commit (the version after the bad `INSERT`), so the history keeps the mistake and the fix.
In a job, the exception fails the silver task and the gold task never starts (its dependency did not succeed), so
no dashboard reads the duplicate.

!!! warning "Tests that cannot fail are decoration"
    Each check here was written against a specific failure, and the FAIL above was produced on purpose to prove the
    check fires. Run a new check once against data you broke on purpose before trusting it. On Databricks, the
    pipeline equivalent of a FAIL check is an expectation with `ON VIOLATION FAIL UPDATE`; reconciliation across
    tables (bronze = silver + quarantine) still needs a query like these.

## 12.8 Day 2 and day 3: the problems, and a restated March 1

*Level: expert.*

Days 2 and 3 bring every problem from the landing table of section 12.2. Each is handled by one piece of the design,
and each leaves a trace in the output:

| Problem | Handled by | Where it shows |
| --- | --- | --- |
| New optional field `channel` (day 2) | the field is in the silver schema; older rows get `NULL` | silver orders, day 2 |
| Order 1005 for unknown customer 99 | kept and counted (WARN); gold points it at `-1` | the WARN lines; the fact table in section 12.6 |
| 1002 changes to `SHIPPED` | `MERGE` updates it (newer `updated_at`) | silver orders, day 2 |
| Ana moves to Banff | SCD Type 2: Calgary closed, Banff opened | silver customers, day 2 |
| Correction of 1001 (a day 1 order) | `MERGE` updates it; its line is replaced; gold restates March 1 | day 3 and the restatement below |
| Stale `PLACED` event for 1002 | out-of-order guard ignores it | 1002 still `SHIPPED` on day 3 |
| 1008 has an item with `qty` 0 | rule `item_invalid` sends it to quarantine | quarantine, day 3 |
| Ben's email with spaces and capitals | trimmed and lowercased before the SCD comparison | silver customers, day 3 |

### Day 2

After the day 2 run (its log has the first WARN, for order 1005), silver orders shows the new field, the unknown
customer and the status change:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, customer_id, order_date, status, amount, channel, updated_at
FROM silver.orders ORDER BY order_id
```

```text
+--------+-----------+----------+-------+------+-------+-------------------+
|order_id|customer_id|order_date|status |amount|channel|updated_at         |
+--------+-----------+----------+-------+------+-------+-------------------+
|1001    |1          |2026-03-01|PLACED |59.90 |NULL   |2026-03-01 10:15:00|
|1002    |2          |2026-03-01|SHIPPED|249.00|web    |2026-03-02 10:00:00|
|1003    |1          |2026-03-01|PLACED |189.50|NULL   |2026-03-01 13:40:00|
|1004    |3          |2026-03-02|PLACED |68.95 |web    |2026-03-02 09:40:00|
|1005    |99         |2026-03-02|PLACED |39.00 |app    |2026-03-02 14:20:00|
|1006    |5          |2026-03-02|PLACED |159.00|web    |2026-03-02 16:00:00|
|1007    |1          |2026-03-02|PLACED |278.95|app    |2026-03-02 18:30:00|
+--------+-----------+----------+-------+------+-------+-------------------+
```

`channel` is `NULL` for the three day 1 orders and filled from day 2, with no schema change at the table: the
contract already listed the field as optional. Order 1002 is now `SHIPPED`, taken from the newer event, and order
1005 is there although customer 99 is unknown. The customers table has two versions for Ana, the Calgary one closed at
the moment the Banff one starts, and a first version for Erin:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT customer_id, name, email, city, valid_from, valid_to, is_current
FROM silver.customers ORDER BY customer_id, valid_from
```

```text
+-----------+------------+-----------------+---------+-------------------+-------------------+----------+
|customer_id|name        |email            |city     |valid_from         |valid_to           |is_current|
+-----------+------------+-----------------+---------+-------------------+-------------------+----------+
|1          |Ana Lopez   |ana@example.com  |Calgary  |2026-01-05 09:00:00|2026-03-02 08:00:00|false     |
|1          |Ana Lopez   |ana@example.com  |Banff    |2026-03-02 08:00:00|NULL               |true      |
|2          |Ben Okafor  |ben@example.com  |Denver   |2026-01-07 12:30:00|NULL               |true      |
|3          |Chloe Martin|chloe@example.com|Moab     |2026-01-09 16:45:00|NULL               |true      |
|4          |Dev Patel   |dev@example.com  |Vancouver|2026-01-11 08:15:00|NULL               |true      |
|5          |Erin Walsh  |erin@example.com |Boise    |2026-03-02 15:00:00|NULL               |true      |
+-----------+------------+-----------------+---------+-------------------+-------------------+----------+
```

### Day 3

Day 3's file holds a correction of order 1001 (one item instead of two, 29.95 instead of 59.90), an old version of
1002, a new order 1009, and order 1008 with a zero quantity. The day 3 job log is in section 12.7. The orders it
touched:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, order_date, status, amount, updated_at, _file_name
FROM silver.orders WHERE order_id IN (1001, 1002, 1009) ORDER BY order_id;

SELECT order_id, product_id, qty, line_amount, order_updated_at FROM silver.order_items WHERE order_id = 1001;

SELECT get_json_object(raw, '$.order_id') AS order_id, failed_rules, _file_name
FROM silver.orders_quarantine ORDER BY 1;
```

```text
+--------+----------+-------+------+-------------------+-------------------------+
|order_id|order_date|status |amount|updated_at         |_file_name               |
+--------+----------+-------+------+-------------------+-------------------------+
|1001    |2026-03-01|PLACED |29.95 |2026-03-03 08:30:00|orders_20260303_1800.json|
|1002    |2026-03-01|SHIPPED|249.00|2026-03-02 10:00:00|orders_20260302_1800.json|
|1009    |2026-03-03|PLACED |189.50|2026-03-03 12:10:00|orders_20260303_1800.json|
+--------+----------+-------+------+-------------------+-------------------------+

+--------+----------+---+-----------+-------------------+
|order_id|product_id|qty|line_amount|order_updated_at   |
+--------+----------+---+-----------+-------------------+
|1001    |3         |1  |29.95      |2026-03-03 08:30:00|
+--------+----------+---+-----------+-------------------+

+--------+----------------+-------------------------+
|order_id|failed_rules    |_file_name               |
+--------+----------------+-------------------------+
|NULL    |[malformed_json]|orders_20260301_0900.json|
|1008    |[item_invalid]  |orders_20260303_1800.json|
+--------+----------------+-------------------------+
```

Order 1001 keeps `order_date` 2026-03-01 (it was placed then) but now carries the March 3 version, and its line was
replaced, not added to: one line, qty 1. Order 1002 is still `SHIPPED` from the day 2 file: the stale `PLACED` event
from day 3 lost to the out-of-order guard. The quarantine holds two rows with exact reasons; the cut-off line has no
`order_id` to show because it never parsed.

The table history shows what each day's `MERGE` did, from the operation metrics Delta records with every commit:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def history_view(table):
    """DESCRIBE HISTORY as a temp view: open-source Spark cannot use DESCRIBE HISTORY as a subquery."""
    view = "history_" + table.replace(".", "_")
    sql(f"DESCRIBE HISTORY {table}").createOrReplaceTempView(view)
    return view

show(f"""SELECT version, operation,
                operationMetrics['numSourceRows']          AS source_rows,
                operationMetrics['numTargetRowsInserted']  AS inserted,
                operationMetrics['numTargetRowsUpdated']   AS updated,
                operationMetrics['numTargetRowsDeleted']   AS deleted,
                operationMetrics['numOutputRows']          AS output_rows
         FROM {history_view('silver.orders')} ORDER BY version""")
```

```text
+-------+------------+-----------+--------+-------+-------+-----------+
|version|operation   |source_rows|inserted|updated|deleted|output_rows|
+-------+------------+-----------+--------+-------+-------+-----------+
|0      |CREATE TABLE|NULL       |NULL    |NULL   |NULL   |NULL       |
|1      |MERGE       |3          |3       |0      |0      |3          |
|2      |MERGE       |5          |4       |1      |0      |7          |
|3      |MERGE       |3          |1       |1      |0      |8          |
+-------+------------+-----------+--------+-------+-------+-----------+
```

Read version 3 (day 3): three source rows (1001, 1002 and 1009; 1008 went to quarantine), one insert (1009), one
update (1001), and the stale 1002 neither inserted nor updated. `output_rows` counts every row written to new data
files, including unchanged rows copied out of the files the `MERGE` rewrote, which is why it is larger than
inserted plus updated. (`DESCRIBE HISTORY` cannot be used as a subquery in open-source Spark, a parse error here,
hence the temporary view.)

Ben's email change became a new version, and only one: the export's spaces and capitals were cleaned before the
comparison, so the stored value is `ben.okafor@example.com`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT customer_id, email, city, valid_from, valid_to, is_current
FROM silver.customers WHERE customer_id IN (1, 2) ORDER BY customer_id, valid_from
```

```text
+-----------+----------------------+-------+-------------------+-------------------+----------+
|customer_id|email                 |city   |valid_from         |valid_to           |is_current|
+-----------+----------------------+-------+-------------------+-------------------+----------+
|1          |ana@example.com       |Calgary|2026-01-05 09:00:00|2026-03-02 08:00:00|false     |
|1          |ana@example.com       |Banff  |2026-03-02 08:00:00|NULL               |true      |
|2          |ben@example.com       |Denver |2026-01-07 12:30:00|2026-03-03 09:30:00|false     |
|2          |ben.okafor@example.com|Denver |2026-03-03 09:30:00|NULL               |true      |
+-----------+----------------------+-------+-------------------+-------------------+----------+
```

### March 1, restated

The correction of 1001 reached gold through the change data feed (the day 3 log: "silver.orders change rows -> gold
facts: 3 rows read", the update's pre-image and post-image for 1001 and the insert of 1009). Their order dates are
March 1 and March 3, so gold replaced exactly those two dates. Finance's question, "what did the March 1 report say
before the correction?", is answered by time travel to the version of `daily_sales` written on day 2 (version 2, kept
in `v_day2` by the demo):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT * FROM gold.daily_sales VERSION AS OF 2 WHERE order_date = DATE'2026-03-01' ORDER BY ALL;
SELECT * FROM gold.daily_sales WHERE order_date = DATE'2026-03-01' ORDER BY ALL;
```

```text
+----------+--------+--------+------+-----+-------+
|order_date|category|currency|orders|units|revenue|
+----------+--------+--------+------+-----+-------+
|2026-03-01|Camping |CAD     |1     |1    |189.50 |
|2026-03-01|Camping |USD     |1     |1    |249.00 |
|2026-03-01|Hiking  |CAD     |1     |2    |59.90  |
+----------+--------+--------+------+-----+-------+

+----------+--------+--------+------+-----+-------+
|order_date|category|currency|orders|units|revenue|
+----------+--------+--------+------+-----+-------+
|2026-03-01|Camping |CAD     |1     |1    |189.50 |
|2026-03-01|Camping |USD     |1     |1    |249.00 |
|2026-03-01|Hiking  |CAD     |1     |1    |29.95  |
+----------+--------+--------+------+-----+-------+
```

Hiking in CAD on March 1 went from 2 units and 59.90 to 1 unit and 29.95; the other two rows did not change. The
history of `daily_sales` shows that each run replaced only the dates that changed, with the predicate recorded in
each commit:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT version, operation, operationParameters['predicate'] AS predicate,
       operationMetrics['numOutputRows'] AS rows_written
FROM history_gold_daily_sales ORDER BY version
```

```text
+-------+------------+------------------------------------------------------+------------+
|version|operation   |predicate                                             |rows_written|
+-------+------------+------------------------------------------------------+------------+
|0      |CREATE TABLE|NULL                                                  |NULL        |
|1      |WRITE       |(order_date = DATE '2026-03-01')                      |3           |
|2      |WRITE       |(order_date IN (DATE '2026-03-01', DATE '2026-03-02'))|7           |
|3      |WRITE       |(order_date IN (DATE '2026-03-01', DATE '2026-03-03'))|8           |
+-------+------------+------------------------------------------------------+------------+
```

Version 2 (day 2) also rewrote March 1, although no March 1 number changed: order 1002 went to `SHIPPED`, which is a
change to a March 1 order, so March 1 was recomputed and came out the same. That is the price of driving gold by
changed rows rather than changed numbers, and it is small: one date. Version 3 (day 3) is the restatement: March 1
(the correction) and March 3 (order 1009). The whole table and the lifetime values after day 3:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT * FROM gold.daily_sales ORDER BY ALL;
SELECT * FROM gold.customer_ltv ORDER BY ALL;
```

```text
+----------+--------+--------+------+-----+-------+
|order_date|category|currency|orders|units|revenue|
+----------+--------+--------+------+-----+-------+
|2026-03-01|Camping |CAD     |1     |1    |189.50 |
|2026-03-01|Camping |USD     |1     |1    |249.00 |
|2026-03-01|Hiking  |CAD     |1     |1    |29.95  |
|2026-03-02|Apparel |USD     |1     |1    |159.00 |
|2026-03-02|Camping |CAD     |1     |1    |249.00 |
|2026-03-02|Hiking  |CAD     |2     |2    |68.95  |
|2026-03-02|Hiking  |USD     |1     |2    |68.95  |
|2026-03-03|Camping |USD     |1     |1    |189.50 |
+----------+--------+--------+------+-----+-------+

+-----------+--------+------------+------+------+-------+----------------+---------------+
|customer_id|currency|name        |city  |orders|revenue|first_order_date|last_order_date|
+-----------+--------+------------+------+------+-------+----------------+---------------+
|1          |CAD     |Ana Lopez   |Banff |3     |498.40 |2026-03-01      |2026-03-02     |
|2          |USD     |Ben Okafor  |Denver|2     |438.50 |2026-03-01      |2026-03-03     |
|3          |USD     |Chloe Martin|Moab  |1     |68.95  |2026-03-02      |2026-03-02     |
|5          |USD     |Erin Walsh  |Boise |1     |159.00 |2026-03-02      |2026-03-02     |
+-----------+--------+------------+------+------+-------+----------------+---------------+
```

Ana's CAD lifetime value is 29.95 + 189.50 + 278.95 = 498.40 (the corrected 1001, 1003 and 1007), and her city is
Banff, the current version. Customer 99's order is in `daily_sales` but not in `customer_ltv`, which excludes the
unknown member on purpose: a lifetime value for "unknown" would mean nothing. Dev (customer 4) has no row: his only
order, 1008, is in quarantine.

!!! warning "Time travel is not an audit trail"
    `VERSION AS OF` reaches back only as far as the table's retained history and data files; `VACUUM` and log
    retention remove old versions ([chapter 4](04-Delta-Lake.md)). If finance must be able to show a published number
    years later, write each published report (date, version, figures) to its own append-only table.

!!! tip "In the interview"
    **"A correction arrives for an order from last week. How does it reach the dashboard, and can you show the old
    number?"** Silver applies it with `MERGE` because its `updated_at` is newer. The change data feed of silver orders
    carries the update, with the order's business date. Gold recomputes exactly that date with `INSERT INTO ...
    REPLACE WHERE order_date IN (...)` in one atomic commit, so dashboards see either the old or the new day, never a
    half-written one. The old number is still readable with `VERSION AS OF` until retention removes it, and
    `DESCRIBE HISTORY` shows which commit replaced which dates.

## 12.9 Reruns, backfills and a full rebuild

*Level: expert.*

"Is it idempotent?" is the question every pipeline design gets, and "yes, because it uses `MERGE`" is not an answer.
This section proves three properties with counts and Delta history: a rerun with no new data changes nothing; a
correction or backfill changes only the dates it should (section 12.8 showed the correction; Q23 runs a backfill);
and silver and gold can be rebuilt from bronze into exactly the same tables.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 330" role="img" aria-label="Three ways the same code runs again. Rerun: no new files, every stream reads zero rows, every MERGE changes zero rows. Restatement: a late correction updates one silver order, the change data feed names its date, REPLACE WHERE rewrites only that date, and time travel still shows the old number. Full rebuild: drop silver and gold and their checkpoints, the streams replay all of bronze, customers are applied snapshot by snapshot, and the result equals the tables before">
<g fill="currentColor" font-size="14" font-weight="bold">
<text x="10" y="22">Rerun (no new files)</text>
<text x="10" y="132">Restatement (a late correction)</text>
<text x="10" y="242">Full rebuild (from bronze)</text>
</g>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="10" y="34" width="140" height="56" rx="5"/>
<rect x="170" y="34" width="140" height="56" rx="5"/>
<rect x="330" y="34" width="140" height="56" rx="5"/>
<rect x="490" y="34" width="140" height="56" rx="5" stroke-width="2.5"/>
<rect x="10" y="144" width="140" height="56" rx="5"/>
<rect x="170" y="144" width="140" height="56" rx="5"/>
<rect x="330" y="144" width="140" height="56" rx="5"/>
<rect x="490" y="144" width="140" height="56" rx="5" stroke-width="2.5"/>
<rect x="10" y="254" width="140" height="56" rx="5"/>
<rect x="170" y="254" width="140" height="56" rx="5"/>
<rect x="330" y="254" width="140" height="56" rx="5"/>
<rect x="490" y="254" width="140" height="56" rx="5" stroke-width="2.5"/>
<line x1="150" y1="62" x2="162" y2="62"/>
<line x1="310" y1="62" x2="322" y2="62"/>
<line x1="470" y1="62" x2="482" y2="62"/>
<line x1="150" y1="172" x2="162" y2="172"/>
<line x1="310" y1="172" x2="322" y2="172"/>
<line x1="470" y1="172" x2="482" y2="172"/>
<line x1="150" y1="282" x2="162" y2="282"/>
<line x1="310" y1="282" x2="322" y2="282"/>
<line x1="470" y1="282" x2="482" y2="282"/>
<line x1="10" y1="110" x2="630" y2="110" stroke-dasharray="4 4"/>
<line x1="10" y1="220" x2="630" y2="220" stroke-dasharray="4 4"/>
</g>
<g fill="currentColor">
<polygon points="170,62 162,58 162,66"/>
<polygon points="330,62 322,58 322,66"/>
<polygon points="490,62 482,58 482,66"/>
<polygon points="170,172 162,168 162,176"/>
<polygon points="330,172 322,168 322,176"/>
<polygon points="490,172 482,168 482,176"/>
<polygon points="170,282 162,278 162,286"/>
<polygon points="330,282 322,278 322,286"/>
<polygon points="490,282 482,278 482,286"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="80" y="57">bronze checkpoints:</text>
<text x="80" y="75">0 new files</text>
<text x="240" y="57">silver streams:</text>
<text x="240" y="75">0 rows read</text>
<text x="400" y="57">dimension MERGEs:</text>
<text x="400" y="75">0 rows changed</text>
<text x="560" y="57">same rows,</text>
<text x="560" y="75">checks pass</text>
<text x="80" y="167">MERGE updates</text>
<text x="80" y="185">order 1001</text>
<text x="240" y="167">change data feed:</text>
<text x="240" y="185">date 2026-03-01</text>
<text x="400" y="167">REPLACE WHERE</text>
<text x="400" y="185">that date only</text>
<text x="560" y="167">new number; old one</text>
<text x="560" y="185">by VERSION AS OF</text>
<text x="80" y="277">drop silver, gold</text>
<text x="80" y="295">and checkpoints</text>
<text x="240" y="277">streams replay</text>
<text x="240" y="295">all of bronze</text>
<text x="400" y="277">snapshots applied</text>
<text x="400" y="295">one at a time</text>
<text x="560" y="277">EXCEPT ALL with the</text>
<text x="560" y="295">old tables: 0 rows</text>
</g>
</svg>
<figcaption>Figure 12.4. The same code, run three ways. A rerun finds nothing new and changes nothing; a late
correction rewrites only the dates it touches, while time travel keeps the old answer; a full rebuild replays bronze
and must produce the same tables. Each lane is proved with real output in sections 12.8 and 12.9.</figcaption>
</figure>

### A rerun with no new files

The demo runs the whole job a fourth time with no new files and compares, per table, the row count, the latest
version, and the rows changed by any commit made during the rerun (from the operation metrics):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def rows_changed_since(table, version):
    """Rows inserted + updated + deleted by the MERGE commits after `version`, plus rows written by
    any other commit (a plain write has no 'unchanged' rows, so every row it writes counts)."""
    return sql(f"""
        SELECT coalesce(sum(CASE WHEN operation = 'MERGE'
                                 THEN int(operationMetrics['numTargetRowsInserted'])
                                    + int(operationMetrics['numTargetRowsUpdated'])
                                    + int(operationMetrics['numTargetRowsDeleted'])
                                 ELSE coalesce(int(operationMetrics['numOutputRows']), 0) END), 0)
        FROM {history_view(table)} WHERE version > {version}""").first()[0]

before = state()          # {table: (row count, latest version)}
run_all(spark)
after = state()
```

```text
table                        rows before rows after version before version after rows changed by new commits
bronze.orders                         14         14              3             3                           0
bronze.customers                      14         14              3             3                           0
bronze.products                        5          5              1             1                           0
silver.orders                          8          8              3             3                           0
silver.order_items                    10         10              3             3                           0
silver.orders_quarantine               2          2              2             2                           0
silver.customers                       7          7              3             3                           0
silver.products                        5          5              1             1                           0
gold.dim_date                        365        365              1             1                           0
gold.dim_product                       5          5              3             4                           0
gold.dim_customer                      8          8              3             4                           0
gold.fact_order_lines                 10         10              3             3                           0
gold.daily_sales                       8          8              3             3                           0
gold.customer_ltv                      4          4              3             4                           0
```

Every stream read 0 rows (the log: "bronze.orders: 0 rows read", "silver.orders change rows -> gold facts: 0 rows
read"), every check passed with the same two WARNs, and no table has a changed row. Three tables did get a new
version: `dim_product`, `dim_customer` and `customer_ltv`, the three refreshed on every run by a `MERGE` of the
whole source that includes `WHEN NOT MATCHED BY SOURCE THEN DELETE`. (`dim_date`, whose `MERGE` only inserts, made no
commit at all.) The history of `dim_customer` shows what that commit did:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
+-------+------------+-----------+--------+-------+-------+-----------+
|version|operation   |source_rows|inserted|updated|deleted|output_rows|
+-------+------------+-----------+--------+-------+-------+-----------+
|0      |CREATE TABLE|NULL       |NULL    |NULL   |NULL   |NULL       |
|1      |MERGE       |5          |5       |0      |0      |5          |
|2      |MERGE       |7          |2       |1      |0      |7          |
|3      |MERGE       |8          |1       |1      |0      |8          |
|4      |MERGE       |8          |0       |0      |0      |8          |
+-------+------------+-----------+--------+-------+-------+-----------+
```

Version 4 is the rerun: 8 source rows, nothing inserted, updated or deleted, so the change condition did its job. But
`output_rows` is 8: the `MERGE` still committed and wrote all 8 rows out again. A `WHEN NOT MATCHED BY SOURCE` clause
has to consider every target row, and here the table's data was rewritten although no row changed. For an 8-row
dimension that is nothing. For a dimension with
millions of rows, it is worth skipping the `MERGE` when the source has not changed (for example, read silver's change
data feed first) instead of relying on the change condition alone. "Idempotent" means the data does not change; it
does not mean the run costs nothing.

### A full rebuild from bronze

**The problem.** A bug is found in silver logic, or a rule changes, and every silver and gold row must be
recomputed. Bronze is the one layer that is never rebuilt: it is the record of what arrived.

**The tool.** Because every layer is incremental by checkpoint, a rebuild is: drop the silver and gold tables, delete
their checkpoints (not bronze's), and run the same code. The silver streams then start from the beginning of the
bronze tables, and the gold change-feed stream starts with the latest snapshot of `silver.orders` as `INSERT` rows
(section 12.6). No separate "backfill code path" exists to drift away from the daily one. The demo first copies every
silver and gold table aside, so the rebuilt tables can be compared with them:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
for t in rebuilt:          # every silver and gold table
    sql(f"CREATE OR REPLACE TABLE before_rebuild.{t.replace('.', '__')} USING DELTA AS SELECT * FROM {t}")

for t in rebuilt:
    sql(f"DROP TABLE {t}")
for name in os.listdir(CHECKPOINTS):
    if name.startswith(("silver_", "gold_")):
        shutil.rmtree(os.path.join(CHECKPOINTS, name))

load_silver(spark)
run_checks(spark, "silver")
load_gold(spark)
run_checks(spark, "gold")

for t in rebuilt:          # rows in one table and not the other, both ways, duplicates counted
    cols = "* EXCEPT (_quarantined_at)" if t == "silver.orders_quarantine" else "*"
    diff = sql(f"""SELECT (SELECT count(*) FROM (SELECT {cols} FROM {t} EXCEPT ALL SELECT {cols} FROM {old}))
                        + (SELECT count(*) FROM (SELECT {cols} FROM {old} EXCEPT ALL SELECT {cols} FROM {t}))""")
```

```text
dropped: silver.orders, silver.order_items, silver.orders_quarantine, silver.customers, silver.products, gold.dim_date, gold.dim_product, gold.dim_customer, gold.fact_order_lines, gold.daily_sales, gold.customer_ltv
checkpoints left: ['bronze_customers', 'bronze_orders', 'bronze_products']
  PASS  silver  bronze.orders = valid + quarantined                     got 0, expected 0
  PASS  silver  silver.orders = distinct valid order_ids                got 0, expected 0
  PASS  silver  duplicate order_id in silver.orders                     got 0, expected 0
  PASS  silver  duplicate (order_id, product_id) in silver.order_items  got 0, expected 0
  PASS  silver  orders whose amount <> sum of their lines               got 0, expected 0
  PASS  silver  order_items without an order                            got 0, expected 0
  PASS  silver  customers with <> 1 current row                         got 0, expected 0
  PASS  silver  customer versions with a gap or overlap                 got 0, expected 0
  WARN  silver  orders for an unknown customer (flagged, kept)          got 1, expected 0
  PASS  gold    duplicate (order_id, product_id) in fact_order_lines   got 0, expected 0
  PASS  gold    fact rows - silver.order_items rows                    got 0, expected 0
  PASS  gold    facts with no dim_customer row                         got 0, expected 0
  PASS  gold    facts with no dim_product row                          got 0, expected 0
  PASS  gold    facts with no dim_date row                             got 0, expected 0
  PASS  gold    currencies where fact revenue <> silver order amounts  got 0, expected 0
  PASS  gold    currencies where daily_sales revenue <> fact revenue   got 0, expected 0
  WARN  gold    facts pointing at the unknown customer (-1)            got 1, expected 0

table                        rows before rows after rows that differ
silver.orders                          8          8                0
silver.order_items                    10         10                0
silver.orders_quarantine               2          2                0
silver.customers                       7          7                0
silver.products                        5          5                0
gold.dim_date                        365        365                0
gold.dim_product                       5          5                0
gold.dim_customer                      8          8                0
gold.fact_order_lines                 10         10                0
gold.daily_sales                       8          8                0
gold.customer_ltv                      4          4                0
bronze versions unchanged: True
```

Eleven tables dropped and rebuilt, the same checks passed with the same two WARNs, and `EXCEPT ALL` in both
directions finds 0 differing rows in every table, including the surrogate keys in `dim_customer` and the fact (they
are hashes of the customer version, section 12.6) and the restated March 1 in `daily_sales`. The only column left out
of the comparison is `_quarantined_at`, the time a row was quarantined, which is different by design. The bronze
tables kept their versions: nothing in the rebuild wrote to them.

The rebuild is also where the one-snapshot-at-a-time loop of section 12.5 earns its place. All three customer
snapshots arrived in one batch, and `upsert_customers` applied them in date order, one `MERGE` each:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
+-------+------------+-----------+--------+-------+-------+-----------+
|version|operation   |source_rows|inserted|updated|deleted|output_rows|
+-------+------------+-----------+--------+-------+-------+-----------+
|0      |CREATE TABLE|NULL       |NULL    |NULL   |NULL   |NULL       |
|1      |MERGE       |4          |4       |0      |0      |4          |
|2      |MERGE       |6          |2       |1      |0      |6          |
|3      |MERGE       |6          |1       |1      |0      |7          |
+-------+------------+-----------+--------+-------+-------+-----------+
```

Version 1 is the March 1 snapshot (4 customers inserted). Version 2 is March 2: Ana's Calgary row closed (1
updated), her Banff row and Erin inserted (2). Version 3 is March 3: Ben's old row closed and his new one inserted.
The source has one row more than the snapshot on days 2 and 3, the extra copy of the changed customer that the staged
`MERGE` of chapter 9 needs. Had the three snapshots been merged at once, the `MERGE` would have seen three rows for
customer 1 in one source and failed, or, after a dedup, kept only the latest and lost the Calgary version. The
history starts at version 0 again because the table was dropped and created anew.

Two cautions for a real rebuild. Run it into new tables or a new schema and swap when the checks pass, rather than
dropping production tables first, so readers never see empty tables; the drop here keeps the demo short. And
time travel on the old tables ends with the drop: the history starts again at version 0.

!!! tip "In the interview"
    **"How do you backfill or rebuild your pipeline?"** Bronze is never rebuilt; it is the record of what arrived. A
    backfill of a date range in gold is the same function the daily run uses, given a list of dates, writing with
    `REPLACE WHERE`, so it is idempotent. A full rebuild of silver and gold drops those tables and their streaming
    checkpoints and replays bronze through the same code; customer snapshots are applied one at a time in order so
    SCD Type 2 history comes out the same. I prove it: `EXCEPT ALL` both ways against a copy of the old tables
    returned 0 rows for every table, and a rerun with no new data changed 0 rows according to `DESCRIBE HISTORY`.

## 12.10 Orchestration: one Lakeflow job

*Level: intermediate.*

Locally, `run_all()` calls the steps in order. In production the steps become **tasks** of one Lakeflow job
(formerly Databricks Jobs; the June 2025 release notes say "The product known as Databricks Jobs is now Lakeflow
Jobs" and that the Workflows menu item was removed, see [June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june)).
Each task depends on the one before it. Splitting the layers into tasks, rather than one big script, buys three
things: the run page shows which layer failed, a **repair run** reruns only the failed task and what follows it
([chapter 15](15-Lakeflow-Jobs.md)), and a failed check stops downstream tasks, because a task's default run-if
condition is "All succeeded: All dependencies have run and succeeded" ([Configure task dependencies](https://docs.databricks.com/aws/en/jobs/run-if)).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 260" role="img" aria-label="Top: a Lakeflow job with four tasks in a chain, bronze, silver, gold, tests, each running one layer and its checks. Bottom: the declarative alternative, a job with one pipeline task that runs a Lakeflow pipeline of streaming tables, AUTO CDC flows and materialized views">
<g fill="currentColor" font-size="14" font-weight="bold">
<text x="20" y="24">Job redrock_medallion: hand-written code, four tasks</text>
<text x="20" y="176">Alternative: job redrock_pipeline_daily, one pipeline task</text>
</g>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="20" y="42" width="120" height="44" rx="6"/>
<rect x="180" y="42" width="120" height="44" rx="6"/>
<rect x="340" y="42" width="120" height="44" rx="6"/>
<rect x="500" y="42" width="120" height="44" rx="6"/>
<line x1="140" y1="64" x2="172" y2="64"/>
<line x1="300" y1="64" x2="332" y2="64"/>
<line x1="460" y1="64" x2="492" y2="64"/>
<line x1="10" y1="150" x2="630" y2="150" stroke-dasharray="4 4"/>
<rect x="20" y="190" width="600" height="58" rx="6"/>
</g>
<g fill="currentColor">
<polygon points="180,64 172,60 172,68"/>
<polygon points="340,64 332,60 332,68"/>
<polygon points="500,64 492,60 492,68"/>
</g>
<g fill="currentColor" font-size="14" text-anchor="middle">
<text x="80" y="69">bronze</text>
<text x="240" y="69">silver</text>
<text x="400" y="69">gold</text>
<text x="560" y="69">tests</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="80" y="108">load_bronze()</text>
<text x="80" y="126">+ bronze checks</text>
<text x="240" y="108">load_silver()</text>
<text x="240" y="126">+ silver checks</text>
<text x="400" y="108">load_gold()</text>
<text x="400" y="126">+ gold checks</text>
<text x="560" y="108">all checks</text>
<text x="560" y="126">once more</text>
<text x="320" y="214">pipeline task: one Lakeflow pipeline update</text>
<text x="320" y="236">bronze streaming tables, silver AUTO CDC flows and expectations, gold materialized views</text>
</g>
</svg>
<figcaption>Figure 12.3. Two ways to orchestrate the same flow. Top: a job with four Python tasks; a failed check fails
its task and the tasks after it do not run. Bottom: a job with one pipeline task; the pipeline works out the order of
its tables itself from the queries.</figcaption>
</figure>

The job, in Declarative Automation Bundles form (formerly Databricks Asset Bundles), so it is versioned in Git and
deployed with `databricks bundle deploy` ([chapter 16](16-CICD-and-Testing.md)):

*Databricks only, not run here. Syntax from [Declarative Automation Bundles resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources) and [Bundle configuration examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples).*

```yaml
# resources/redrock_job.yml
resources:
  jobs:
    redrock_medallion:
      name: redrock_medallion

      schedule:
        quartz_cron_expression: '0 0 6 * * ?'   # every day at 06:00
        timezone_id: UTC

      email_notifications:
        on_failure:
          - data-team@example.com

      tasks:
        - task_key: bronze
          spark_python_task:
            python_file: ../src/run_task.py
            parameters: ['--catalog=${var.catalog}', '--layer=bronze']
          environment_key: default

        - task_key: silver
          depends_on:
            - task_key: bronze
          spark_python_task:
            python_file: ../src/run_task.py
            parameters: ['--catalog=${var.catalog}', '--layer=silver']
          environment_key: default

        - task_key: gold
          depends_on:
            - task_key: silver
          spark_python_task:
            python_file: ../src/run_task.py
            parameters: ['--catalog=${var.catalog}', '--layer=gold']
          environment_key: default

        - task_key: tests
          depends_on:
            - task_key: gold
          spark_python_task:
            python_file: ../src/run_task.py
            parameters: ['--catalog=${var.catalog}', '--layer=tests']
          environment_key: default

      environments:
        - environment_key: default
          spec:
            environment_version: '2'
```

The bundle's root file names the bundle, pulls in the resource files and sets the catalog per target, so the same
code deploys to `shop_dev` and to `shop`:

*Databricks only, not run here. Syntax from [Declarative Automation Bundles configuration](https://docs.databricks.com/aws/en/dev-tools/bundles/settings) and [Bundle configuration examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples).*

```yaml
# databricks.yml
bundle:
  name: redrock_medallion

include:
  - resources/*.yml

variables:
  catalog:
    description: Unity Catalog catalog that holds the bronze, silver and gold schemas
    default: shop_dev

targets:
  dev:
    mode: development
    default: true
    workspace:
      host: https://<your-workspace-url>
    variables:
      catalog: shop_dev
  prod:
    mode: production
    workspace:
      host: https://<your-workspace-url>
    variables:
      catalog: shop
```

Notes on the YAML, each checked against the pages named above:

- **Serverless.** The examples page says that for "Python script, Python wheel, and dbt tasks, `environment_key` is
  required for serverless compute", and shows the `environments` block with `environment_version: '2'`; the value is
  copied from that example. Choose the current environment version for a real job.
- **`${var.catalog}`** is a bundle variable, substituted at deploy time. Jobs also have their own job parameters,
  referenced with a double-brace syntax at run time ([chapter 15](15-Lakeflow-Jobs.md)); a bundle variable is enough
  here because the catalog only changes per target.
- **`mode`.** The targets also differ by mode. Deploying `dev` in development mode prefixes resource names with
  `[dev <your user name>]` and "Pauses all schedules and triggers on deployed resources", so the 06:00 schedule runs
  only from `prod`; an explicit `pause_status: UNPAUSED` on a job's `schedule` would override that pause. In
  production mode, if you do not deploy as a service principal, the CLI "Validates that the `run_as` and
  `permissions` mappings are specified" ([Declarative Automation Bundles deployment modes](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes)).
- **Not in this file, but needed in production:** the run-as identity (a service principal, the `run_as` mapping in the
  bundle configuration reference) and retries. The task page says "For most configurations, the default setting does
  not retry any tasks on task failure" and that "Serverless jobs auto-optimize retries by default"
  ([Configure and edit tasks in Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/configure-task)). Every task
  here is idempotent, so a retry is safe.

Each task runs one small entry point. `USE CATALOG` makes the code's two-part names (`silver.orders`) resolve to
`shop.silver.orders`, and the landing and checkpoint paths point at volumes:

*Databricks only, not run here. Syntax from [USE CATALOG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-use-catalog).*

```python
# src/run_task.py
parser = argparse.ArgumentParser()
parser.add_argument("--catalog", required=True)
parser.add_argument("--layer", required=True, choices=["bronze", "silver", "gold", "tests"])
args = parser.parse_args()

os.environ["REDROCK_BASE"] = f"/Volumes/{args.catalog}/bronze"   # volumes landing/ and checkpoints/

spark = SparkSession.builder.getOrCreate()
spark.sql(f"USE CATALOG {args.catalog}")

if args.layer == "bronze":
    load_bronze(spark)
    run_checks(spark, "bronze")
elif args.layer == "silver":
    load_silver(spark)
    run_checks(spark, "silver")
elif args.layer == "gold":
    load_gold(spark)
    run_checks(spark, "gold")
else:  # tests: the whole suite once more, after every layer is written
    for layer in ("bronze", "silver", "gold"):
        run_checks(spark, layer)
```

How `run_task.py` finds the `redrock` package once deployed (the folder layout of the synced files, or packaging
`redrock` as a wheel as in the examples page's "Job with multiple wheel files") is not verified here; test it with
`databricks bundle validate`, `deploy` and `run` in a dev target before relying on it.

!!! tip "In the interview"
    **"How is your pipeline orchestrated?"** One Lakeflow job (formerly Databricks Jobs, under the Workflows menu) with a task per layer,
    bronze, silver, gold, then tests, chained with `depends_on`, so a failed check stops downstream tasks and a
    repair run restarts from the failed task. The job is defined in a Declarative Automation Bundle (formerly
    Databricks Asset Bundle) in Git, with a dev target (development mode, schedule paused) and a prod target, each
    with its own catalog, and runs as a service principal on a daily schedule. Every task is idempotent, which is what makes retries and repairs safe.

## 12.11 The declarative version: one Lakeflow pipeline

*Level: expert.*

Everything in sections 12.3 to 12.6 can also be written as one Lakeflow pipeline (formerly Delta Live Tables; see
[What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)). Instead of
writing the order of steps, checkpoints and `MERGE` statements, you declare tables: **streaming tables** for
incremental ingestion and appends, **flows** such as `AUTO CDC` (formerly `APPLY CHANGES`, see
[The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc)) for "keep the latest version" and SCD Type 2, and
**materialized views** for gold. The pipeline works out the dependency order, manages checkpoints, and records
expectation results. [Chapter 13](13-Declarative-Pipelines.md) and [chapter 14](14-Data-Quality-and-CDC.md) cover
the pieces; here is the whole project in one SQL file, shortened where it repeats section 12.4.

*Databricks only, not run here. Syntax from [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table), [CREATE TEMPORARY VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-temporary-view), [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations), [AUTO CDC INTO (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-apply-changes-into), [The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc) and [CREATE MATERIALIZED VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-materialized-view).*

```sql
-- bronze: read_files in a streaming table uses Auto Loader
CREATE OR REFRESH STREAMING TABLE bronze.orders
COMMENT 'Raw order events, one row per JSON line, as received'
AS SELECT value                              AS raw,
          _metadata.file_name                AS _file_name,
          _metadata.file_modification_time   AS _file_modification_time,
          current_timestamp()                AS _ingested_at
FROM STREAM read_files('/Volumes/shop/bronze/landing/orders/', format => 'text');

-- silver: parse and type (the query of section 12.4, without the failed_rules array)
CREATE TEMPORARY VIEW orders_checked AS
WITH typed AS (
  SELECT raw, _file_name, _ingested_at,
         from_json(raw, 'order_id STRING, customer_id STRING, ... , _corrupt_record STRING') AS j
  FROM STREAM(bronze.orders)
)
SELECT raw, _file_name, _ingested_at,
       j._corrupt_record IS NOT NULL                    AS is_malformed,
       try_cast(j.order_id AS INT)                      AS order_id,
       -- ... the other typed columns of section 12.4 ...
FROM typed;

-- valid events: each rule is an expectation; a row that breaks one is dropped (and counted)
CREATE OR REFRESH STREAMING TABLE silver.order_events (
  CONSTRAINT well_formed     EXPECT (NOT is_malformed AND order_id IS NOT NULL
                                     AND customer_id IS NOT NULL AND order_ts IS NOT NULL
                                     AND updated_at IS NOT NULL)                ON VIOLATION DROP ROW,
  CONSTRAINT valid_amount    EXPECT (amount >= 0)                               ON VIOLATION DROP ROW,
  CONSTRAINT known_currency  EXPECT (currency IN ('CAD', 'USD'))                ON VIOLATION DROP ROW,
  CONSTRAINT valid_items     EXPECT (size(items) > 0 AND NOT exists(items, i -> i.product_id IS NULL
                                     OR i.qty IS NULL OR i.qty <= 0 OR i.unit_price IS NULL)) ON VIOLATION DROP ROW
)
AS SELECT * EXCEPT (is_malformed) FROM STREAM(orders_checked);

-- the rows the expectations drop, kept with the raw text (the quarantine pattern)
CREATE OR REFRESH STREAMING TABLE silver.orders_quarantine
AS SELECT raw, _file_name, _ingested_at
FROM STREAM(orders_checked)
WHERE NOT coalesce(NOT is_malformed AND order_id IS NOT NULL AND customer_id IS NOT NULL
                   AND order_ts IS NOT NULL AND updated_at IS NOT NULL AND amount >= 0
                   AND currency IN ('CAD', 'USD') AND size(items) > 0
                   AND NOT exists(items, i -> i.product_id IS NULL OR i.qty IS NULL
                                              OR i.qty <= 0 OR i.unit_price IS NULL), false);

-- latest version of each order: AUTO CDC does the dedup and the out-of-order guard
CREATE OR REFRESH STREAMING TABLE silver.orders;

CREATE FLOW orders_cdc AS AUTO CDC INTO silver.orders
FROM STREAM(silver.order_events)
KEYS (order_id)
SEQUENCE BY updated_at
COLUMNS * EXCEPT (raw, items)
STORED AS SCD TYPE 1;

-- customers: SCD Type 2 from the daily snapshot files (customers_YYYYMMDD.csv)
CREATE OR REFRESH STREAMING TABLE silver.customers;

CREATE FLOW customers_snapshot_flow AS
AUTO CDC INTO silver.customers
FROM SNAPSHOT (
  SELECT CAST(customer_id AS INT) AS customer_id, trim(name) AS name, lower(trim(email)) AS email,
         trim(city) AS city, upper(trim(country)) AS country
  FROM read_files('/Volumes/shop/bronze/landing/customers/', format => 'csv', header => true)
  WHERE _metadata.file_name = CONCAT(
    'customers_', CAST((SELECT version FROM current_snapshot_version()) AS STRING), '.csv')
)
WITH VERSION (
  WITH snapshot_files AS (
    SELECT CAST(REGEXP_EXTRACT(path, 'customers_([0-9]+)[.]csv$', 1) AS BIGINT) AS version
    FROM list_files('/Volumes/shop/bronze/landing/customers/')
    WHERE path RLIKE 'customers_[0-9]+[.]csv$'
  )
  SELECT version FROM snapshot_files
  WHERE (NOT EXISTS (SELECT 1 FROM last_snapshot_version())
         OR version > (SELECT version FROM last_snapshot_version()))
  ORDER BY version
  LIMIT 1
)
KEYS (customer_id)
STORED AS SCD TYPE 2;

-- gold: materialized views; recomputed by the pipeline when their inputs change
CREATE OR REFRESH MATERIALIZED VIEW gold.daily_sales
AS SELECT f.order_date, p.category, f.currency, count(DISTINCT f.order_id) AS orders,
          sum(f.qty) AS units, sum(f.line_amount) AS revenue
   FROM gold.fact_order_lines f
   JOIN gold.dim_product p ON p.product_id = f.product_id
   WHERE f.status <> 'CANCELLED'
   GROUP BY ALL;
-- ... order_items (AUTO CDC keyed on order_id, product_id), products, the dimensions,
--     fact_order_lines and customer_ltv: see src/pipeline/redrock_pipeline.sql
```

How this maps to the hand-written version, and what the pages say:

- **Bronze** is one statement. The `read_files` page says "`read_files` leverages Auto Loader when used in a
  streaming table query. You must use the `STREAM` keyword with `read_files`", and that the `TEXT` format "Returns a
  fixed schema with a single `value` (`STRING`) column".
- **The shared parse.** The temporary view `orders_checked` reads `STREAM(bronze.orders)`, and two streaming tables
  read the view with `STREAM(orders_checked)`. The temporary view page does not say whether a view over a stream can
  be read this way, so this is not verified. If a workspace refuses it, make `orders_checked` a streaming table, or
  repeat the parse in both tables.
- **Expectations** replace the `failed_rules` array. Each `CONSTRAINT ... EXPECT ... ON VIOLATION DROP ROW` drops a
  failing row and records it; the expectations page says the drop action means "Invalid records are dropped before
  data is written to the target. The count of dropped records is logged alongside other dataset metrics". Dropped
  rows are not kept anywhere by default, so the quarantine table is a second streaming table with the inverse
  condition, the pattern the [Expectation recommendations and advanced patterns](https://docs.databricks.com/aws/en/ldp/expectation-patterns)
  page shows (it uses an `is_quarantined` flag). The `coalesce(..., false)` makes a row whose rule evaluates to `NULL`
  count as bad; how an expectation itself treats a `NULL` result is not covered here (not verified).
- **`AUTO CDC ... STORED AS SCD TYPE 1`** replaces steps 2 and 3 of `upsert_orders`: `KEYS` is the merge key,
  `SEQUENCE BY` is the out-of-order guard ("The pipeline processing uses this sequencing to handle change events
  that arrive out of order").
- **`AUTO CDC ... FROM SNAPSHOT ... STORED AS SCD TYPE 2`** replaces `upsert_customers`. It is the shape of the
  "Example: Process periodic snapshots" on the AUTO CDC page, pointed at the customer files (the page's example keeps
  the version as a fixed-width string; here the `yyyyMMdd` number is cast to `BIGINT`): the `WITH VERSION` query
  picks the next snapshot number after `last_snapshot_version()`, and the page says that "If several hourly files
  arrive between pipeline updates, both implementations process each available file in version order during the
  next update", which is the pipeline's answer to the one-snapshot-at-a-time loop of section 12.5. The page says the API "compares
  snapshots to determine changes", and in its example a key missing from the new snapshot is ended (deleted). Two
  differences from the hand-written table: `__START_AT` and `__END_AT` hold the snapshot **version** (here
  `20260302`), not the customer's `updated_at`, so history has day granularity; and deletes are handled.
- **Gold** becomes materialized views, so the March 1 restatement needs no code: a materialized view's results "are
  recalculated to reflect changes in upstream datasets" ([CREATE MATERIALIZED VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-materialized-view)).
  Whether a refresh is incremental or a full recompute is decided by the platform
  ([Materialized views](https://docs.databricks.com/aws/en/ldp/materialized-views)).
- **Requirements.** The AUTO CDC page says the CDC APIs need "serverless Lakeflow pipelines or the Lakeflow pipelines
  `Pro` or `Advanced` editions", and "The `AUTO CDC` APIs are not supported by Apache Spark Declarative Pipelines",
  the open-source engine. That holds for Databricks' full `AUTO CDC` APIs, SCD Type 2 and `FROM SNAPSHOT` included,
  which this file uses. Open-source Spark 4.2.0 did add a narrower flow: its
  [release notes](https://spark.apache.org/releases/spark-release-4-2-0.html) list "Auto CDC in Spark Declarative
  Pipelines for declarative SCD Type 1 upserts" (SPARK-56249). A local try of that flow against a Delta Lake 4.4.1
  target failed with `AUTOCDC_TARGET_DOES_NOT_SUPPORT_MERGE` ([chapter 13](13-Declarative-Pipelines.md)). This file
  was not run here.
- **Names.** The file uses two-part names (`silver.orders`). The [Set the target catalog and schema](https://docs.databricks.com/aws/en/ldp/target-schema)
  page says the pipeline's default catalog and schema "are used for all dataset definitions and table reads, unless
  overridden within the query", so with the bundle setting `catalog: ${var.catalog}` they should land in `shop` or
  `shop_dev` (my reading of the page, not verified on a workspace). The volume paths still say `shop`; the
  [Use parameters with pipelines](https://docs.databricks.com/aws/en/ldp/parameters) page shows how to pass such
  values per environment.

The bundle resource for the pipeline, and a job that refreshes it daily:

*Databricks only, not run here. Syntax from [Declarative Automation Bundles resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources) and [Bundle configuration examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples).*

```yaml
# resources/redrock_pipeline.yml
resources:
  pipelines:
    redrock_pipeline:
      name: redrock_pipeline
      catalog: ${var.catalog}
      schema: silver
      serverless: true
      libraries:
        - glob:
            include: ../src/pipeline/**

  jobs:
    redrock_pipeline_daily:
      name: redrock_pipeline_daily
      schedule:
        quartz_cron_expression: '0 0 6 * * ?'
        timezone_id: UTC
      tasks:
        - task_key: refresh_pipeline
          pipeline_task:
            pipeline_id: ${resources.pipelines.redrock_pipeline.id}
```

### Hand-written or declarative: an honest comparison

| Question | Hand-written job (this chapter's code) | Lakeflow pipeline |
| --- | --- | --- |
| Where does it run? | Any Spark with Delta: here, on Databricks, elsewhere | Databricks (the full `AUTO CDC` APIs, SCD Type 2 and snapshots included, are Databricks only; open-source Spark 4.2 adds only a narrower SCD Type 1 Auto CDC flow, and lacks other parts) |
| Dedup and out-of-order guard | Your `QUALIFY` + `MERGE ... WHEN MATCHED AND s.updated_at > t.updated_at` | `AUTO CDC ... KEYS ... SEQUENCE BY` |
| SCD Type 2 | Staged `MERGE`; in-order changes only; no deletes | `STORED AS SCD TYPE 2`, out-of-order handling, deletes (`APPLY AS DELETE WHEN`, or missing keys in snapshots) |
| Quality rules | Checks you write; full control (cross-table reconciliation) | Expectations per row with metrics in the event log; cross-table checks still need queries |
| Incremental gold | Your change-feed stream + `REPLACE WHERE` | Materialized views refreshed by the pipeline |
| Checkpoints, order of steps | Yours to manage (and to delete for a rebuild) | Managed; full refresh is a pipeline option |
| Debugging | Plain Python and SQL, step through locally | Pipeline UI, event log, graph; less local control |
| Cost of a mistake | Bugs in `MERGE` logic are yours (section 12.9 tests them) | Fewer lines to get wrong; behavior is the platform's |
| Interview signal | Shows you understand the mechanics | Shows you know the platform's managed path |

A fair summary: the declarative pipeline removes most of the code in sections 12.4 to 12.6 and handles cases the
hand-written `MERGE` does not (late changes slotted into history, deletes). The hand-written version runs anywhere,
is easy to test locally, and makes every decision visible, which is why interviews still ask you to write the `MERGE`.
Many teams use both: a pipeline for ingestion and silver, plain jobs where they need custom logic.

!!! tip "In the interview"
    **"Would you build this with Delta Live Tables?"** Today it is called Lakeflow pipelines (formerly Delta Live
    Tables), and yes for a new Databricks project: streaming tables with `read_files` for bronze, expectations for
    rules, `AUTO CDC` (formerly `APPLY CHANGES`) for dedup and SCD Type 2, materialized views for gold. I would still
    keep reconciliation checks as a separate task, because expectations judge rows, not totals across tables. And I
    can write the `MERGE` by hand when the platform is not Databricks or the logic does not fit.

## 12.12 Unity Catalog layout and grants

*Level: intermediate.*

Locally the project uses three schemas. On Databricks it uses the layout of [chapter 7](07-Medallion-Architecture.md):
a catalog per environment (`shop` for production, `shop_dev` for development) with one schema per layer, plus two
volumes for files. Grants follow the layers: the source system may only drop files, the job's service principal is
the only writer, engineers read everything, analysts read gold.

*Databricks only, not run here. Syntax from [CREATE VOLUME](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-volume), [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant) and [Unity Catalog privileges reference](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/privileges).*

```sql
CREATE CATALOG IF NOT EXISTS shop;
CREATE SCHEMA  IF NOT EXISTS shop.bronze COMMENT 'raw data as received, plus ingest metadata';
CREATE SCHEMA  IF NOT EXISTS shop.silver COMMENT 'typed, validated, deduplicated; SCD2 customers';
CREATE SCHEMA  IF NOT EXISTS shop.gold   COMMENT 'star schema and aggregates for BI';

CREATE VOLUME IF NOT EXISTS shop.bronze.landing     COMMENT 'files dropped by the source systems';
CREATE VOLUME IF NOT EXISTS shop.bronze.checkpoints COMMENT 'streaming checkpoints of the job';

-- the order system only drops files
GRANT USE CATALOG  ON CATALOG shop               TO `order-system`;
GRANT USE SCHEMA   ON SCHEMA  shop.bronze        TO `order-system`;
GRANT WRITE VOLUME ON VOLUME  shop.bronze.landing TO `order-system`;

-- the job runs as a service principal and is the only writer
GRANT USE CATALOG ON CATALOG shop TO `redrock-etl`;
GRANT USE SCHEMA, CREATE TABLE, SELECT, MODIFY ON SCHEMA shop.bronze TO `redrock-etl`;
GRANT USE SCHEMA, CREATE TABLE, SELECT, MODIFY ON SCHEMA shop.silver TO `redrock-etl`;
GRANT USE SCHEMA, CREATE TABLE, SELECT, MODIFY ON SCHEMA shop.gold   TO `redrock-etl`;
GRANT READ VOLUME, WRITE VOLUME ON VOLUME shop.bronze.landing     TO `redrock-etl`;
GRANT READ VOLUME, WRITE VOLUME ON VOLUME shop.bronze.checkpoints TO `redrock-etl`;

-- data engineers read every layer (to debug), write nothing in production
GRANT USE CATALOG ON CATALOG shop TO `data-engineers`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop.bronze TO `data-engineers`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop.silver TO `data-engineers`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop.gold   TO `data-engineers`;

-- analysts and BI tools read gold only
GRANT USE CATALOG ON CATALOG shop TO `analysts`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop.gold TO `analysts`;
```

What the privileges page says about the pieces used here: `MODIFY` "allows a user to insert, update, and delete data
in the table" and "The user must also have `SELECT` on the table, `USE SCHEMA` on the parent schema, and `USE CATALOG`
on the parent catalog"; `WRITE VOLUME` "Allows a user to add, remove, or modify files and directories stored inside
a volume" (with `USE CATALOG` and `USE SCHEMA`); privileges granted on a schema are inherited by the objects in it, so
`SELECT ON SCHEMA shop.gold` covers tables created later. `CREATE TABLE` is granted on the schema, as that page
recommends ("Databricks recommends granting `CREATE TABLE` at the schema level"). The principal names are examples:
in practice they are groups, and the job's identity is a service principal (the Unity Catalog best practices page:
"Reserve direct `MODIFY` access to production tables for service principals", quoted in chapter 7).

Two layout decisions to mention: the landing volume sits in the `bronze` schema because the files are the rawest
form of bronze and should be governed with it; and checkpoints get their own volume, outside the landing folder, so
the file source never reads its own bookkeeping as data.

!!! tip "In the interview"
    **"How do you secure the layers?"** Catalog per environment, schema per layer, volumes for files. The source
    system can only write to the landing volume; the job's service principal is the only principal with `MODIFY`;
    engineers get `SELECT` on all layers for debugging; analysts get `USE CATALOG`, `USE SCHEMA` and `SELECT` on gold
    only. Bronze often holds personal data as received, which is one more reason analysts never see it.

## 12.13 Presenting this project in an interview

*Level: mixed.*

"Walk me through a pipeline you built" is an invitation to show judgment, not to recite code. Interviewers listen
for four things: that you knew what the business needed, that you expected bad data, that your loads are safe to
repeat, and that you can prove the numbers. A two-minute version of this project that hits all four:

> **The business.** "An online outdoor shop needed daily sales by category and lifetime value per customer, in two
> currencies, and finance needed to know when a past number changed."
>
> **The sources and their problems.** "Order events arrived as JSON lines in files, customers as a daily CSV snapshot.
> The feed had duplicates, a cut-off line, an order for a customer we did not know, events arriving out of order,
> and corrections to orders from earlier days."
>
> **The design.** "Medallion layers in Unity Catalog, one schema each. Bronze loads each new file once with a
> streaming `availableNow` read and a checkpoint (Auto Loader on Databricks) and keeps the raw line. Silver parses
> and types with `try_cast`, records every broken rule in an array, sends bad rows to a quarantine table with the
> reasons, keeps the latest version of each order with a `MERGE` that ignores older versions, and keeps customer
> history as SCD Type 2. Gold is a star schema at order-line grain with a hash surrogate key, an unknown-customer
> member, and aggregates built from the fact."
>
> **Incremental and safe to repeat.** "Gold reads silver's change data feed, finds the business dates that changed,
> and rewrites only those dates with `REPLACE WHERE`. So a correction to a March 1 order on March 3 restates March 1,
> and time travel still shows what the report said before. I proved a rerun changes zero rows and a full rebuild
> from bronze gives identical tables."
>
> **Quality and operations.** "After each layer a set of checks runs: bronze reconciles with the files, silver with
> bronze plus quarantine, gold revenue with silver per currency. A failed check fails the task, so gold never
> publishes bad numbers. It runs as a Lakeflow job (formerly Databricks Jobs) with a task per layer, defined in a
> Declarative Automation Bundle (formerly Databricks Asset Bundles); I also wrote the declarative version as a
> Lakeflow pipeline (formerly Delta Live Tables) with `AUTO CDC` (formerly `APPLY CHANGES`), and I can explain the
> trade-off."

Then stop and let them choose where to dig. The follow-ups this project invites, and where the answer is:

| They ask | The short answer | Section |
| --- | --- | --- |
| "How do you avoid loading a file twice?" | The stream checkpoint records read files; the Delta sink commits each batch once | 12.3 |
| "What if the same order arrives twice, or out of order?" | Dedup inside the batch with `QUALIFY`, then `MERGE ... WHEN MATCHED AND s.updated_at > t.updated_at` | 12.4 |
| "What happens to bad records?" | Quarantine table with raw text and an array of reasons; a check proves bronze = valid + quarantined | 12.4, 12.7 |
| "How do you handle a customer who moves?" | SCD Type 2 with a staged `MERGE`; facts join the version valid at order time | 12.5, 12.6 |
| "An order arrives for a customer you do not have yet?" | Keep it, point it at the `-1` member, count it with a WARN, re-key when the customer arrives | 12.6, Q16 |
| "How do you load a fact incrementally when history changes?" | Change data feed of silver gives changed dates; `REPLACE WHERE` rewrites exactly those | 12.6, 12.8 |
| "Can you rerun it? Backfill it? Rebuild it?" | Yes, and the history and `EXCEPT ALL` outputs prove it | 12.9 |
| "How do you know the numbers are right?" | Reconciliation checks after every layer, written against specific failures | 12.7 |
| "Why not Delta Live Tables?" | Lakeflow pipelines (formerly Delta Live Tables) would replace most of the code; the comparison table | 12.11 |
| "Who can see what?" | Schema per layer, the job's service principal is the only writer, analysts read gold | 12.12 |

Three habits make the story credible:

- **Say the numbers.** "14 bronze lines, 12 valid events, 8 orders, 2 quarantined" sounds like something you ran.
  "We had lots of data quality checks" does not.
- **Name a trade-off you chose.** For example: the hash surrogate key is stable across rebuilds but can collide in
  theory, so a uniqueness check guards it; or: the hand-written SCD Type 2 cannot slot a late change into the middle
  of history, which `AUTO CDC` can.
- **Say what you would do next.** Scale and operations are fair game: the Auto Loader file notification mode for
  large landing folders ([chapter 8](08-Bronze-Ingestion.md)), clustering the fact table by `order_date`
  ([chapter 22](22-Performance-Tuning.md)), an alert on quarantine growth, a delete rule for customers missing from a
  snapshot, and masking personal data before it leaves silver ([chapter 5](05-Unity-Catalog.md)).

!!! warning "Do not claim what you did not build"
    If the project ran locally, say so: "I built it on open-source Spark and Delta, and wrote the Databricks job and
    pipeline definitions from the documentation." Interviewers probe details; an honest scope survives the probing,
    an inflated one does not.

## 12.14 Practice questions

*Level: mixed.*

Questions 1 to 6 are beginner, 7 to 20 intermediate, 21 to 30 expert. The answers with code were run: the "extend
the project" questions (12, 15 to 20, 23, 24) by `practice.py`, which continues from the state `run_demo.py` left and
adds a fourth day of files (whole output in `practice.out`), and question 8 by `practice_q8.py`.

**Q1. Bronze stores each order line as one string column, `raw`. Name two things that would go wrong if bronze
parsed the JSON into typed columns instead.**

??? success "Answer"
    First, the cut-off line of day 1 would fail or turn into a row of `NULL`s, and the original text, which is what
    someone needs to fix and replay it, would be gone. Second, a type change in the source (say `amount` sent as
    `"59.9 CAD"`) would fail the load or silently become `NULL` before any rule could record why. With the raw line
    kept, bronze never fails on content, and silver records exactly which rule each line broke, while the raw text
    stays available for a replay. The cost is that every reader of bronze has to parse; that is why nobody but silver
    reads it.

**Q2. What does `trigger(availableNow=True)` with a checkpoint give the bronze load that a daily
`spark.read.text(landing_folder)` would not? Which check in this project would catch the mistake?**

??? success "Answer"
    The checkpoint records which files the stream has read, so each run processes only files that are new since the
    last run, then stops. A batch read of the folder reads every file every day: on day 2, day 1's lines would be
    appended to bronze a second time. The bronze check "every landing line is in bronze.orders" compares bronze with
    the number of data lines in the landing files and would fail (15 rows against 10 lines on day 2). Silver would
    hide part of the damage (the `MERGE` guard ignores versions it already has), which is exactly why the check sits
    at the layer that caused the problem.

**Q3. `landing.py` writes each file under a name starting with `.` and then renames it. Why?**

??? success "Answer"
    So that a reader never sees half a file. Spark's file sources skip names starting with `.` or `_`, so the stream
    picks up the file only after the rename, when it is complete. The Spark Structured Streaming guide states the rule
    for the file source: "Note that the files must be atomically placed in the given directory, which in most file
    systems, can be achieved by file move operations." A producer that writes in place risks a run that starts in the
    middle of the write and loads a truncated file.

**Q4. State the grain (one row per what) of `fact_order_lines`, `daily_sales`, `customer_ltv` and `dim_customer`.**

??? success "Answer"
    `fact_order_lines`: one row per order line, that is per (`order_id`, `product_id`). `daily_sales`: one row per
    (order date, product category, currency). `customer_ltv`: one row per (customer, currency). `dim_customer`: one
    row per customer **version** (SCD Type 2), plus the `-1` unknown member. The gold checks test the fact grain
    directly ("duplicate (order_id, product_id) in fact_order_lines").

**Q5. Each order event has `order_ts` and `updated_at`. Which one decides which version of an order wins, and which
one decides the date the sale is reported on?**

??? success "Answer"
    `updated_at` (when the source system changed the order) orders the versions: the `QUALIFY` keeps the highest
    `updated_at` in a batch, and the `MERGE` updates only if the incoming `updated_at` is newer. `order_ts` (when the
    order was placed) gives `order_date`, the date sales are reported on. That split is why a correction made on
    March 3 (`updated_at` March 3) changes March 1 sales (`order_ts` March 1).

**Q6. Why do `daily_sales` and `customer_ltv` keep a `currency` column instead of one revenue figure?**

??? success "Answer"
    Red Rock Supply sells in CAD and USD, and adding the two is a silent error: 100 CAD plus 100 USD is not 200 of
    anything. Converting needs an exchange rate for each date, which is a business decision (which rate, which day)
    and its own table. Until that exists, gold keeps revenue per currency, and the gold check "fact revenue = silver
    order amounts" is done per currency too.

**Q7. Without the `_corrupt_record STRING` field in the schema, what does `from_json` return for the cut-off line,
and what would the quarantine row have said?**

??? success "Answer"
    In the default `PERMISSIVE` mode, `from_json` returns a struct whose fields are all `NULL`, not a `NULL` struct.
    So a test like `j IS NULL` never fires, and the line breaks every "missing" rule at once: the first version of
    this project quarantined it with seven reasons (`order_id_missing`, `customer_id_missing`, and so on) instead of
    the real one. With the field in the schema, the unparsable text lands in `j._corrupt_record`, and the rule
    `malformed_json` is exact. On Databricks, Auto Loader follows the same idea through the
    `columnNameOfCorruptRecord` option (section 12.3).

**Q8. Day 1 brings order 1002 twice in the same run. What happens if the orders `MERGE` runs without the `QUALIFY`
step?**

??? success "Answer"
    The first time, nothing fails: 1002 is not in the table, and each `WHEN NOT MATCHED` source row inserts a row, so
    silver gets a duplicate `order_id` (the check "duplicate order_id in silver.orders" would fail). The next time the
    two rows arrive, the `MERGE` fails, even though the guard is false and no row would change. `practice_q8.py`
    runs both steps on a two-row source:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    merge = """MERGE INTO t USING s ON t.order_id = s.order_id
               WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
               WHEN NOT MATCHED THEN INSERT *"""
    for attempt in (1, 2):
        try:
            sql(merge)
            print(f"MERGE {attempt}: OK")
        except Exception as e:
            print(f"MERGE {attempt}: " + str(e).splitlines()[0][:110])
        show("SELECT * FROM t")
    ```

    ```text
    MERGE 1: OK
    >>> SELECT * FROM t
    +--------+-----------+
    |order_id|updated_at |
    +--------+-----------+
    |1002    |03-01 11:05|
    |1002    |03-01 11:05|
    +--------+-----------+

    MERGE 2: [DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE] Cannot perform Merge as multiple source rows matched 
    >>> SELECT * FROM t
    +--------+-----------+
    |order_id|updated_at |
    +--------+-----------+
    |1002    |03-01 11:05|
    |1002    |03-01 11:05|
    +--------+-----------+
    ```

    A `MERGE` source must be unique per key, so the batch is deduplicated first, keeping the latest `updated_at`, with
    `_ingested_at` and `_file_name` as tie-breakers so the choice is deterministic. [Chapter 9](09-Building-Silver.md)
    shows the same error with two different versions of one order.

**Q9. The orders `MERGE` updates only `WHEN MATCHED AND s.updated_at > t.updated_at`. What would change with `>=`?**

??? success "Answer"
    With `>=`, replaying a version silver already has (a rerun after a lost checkpoint, a full rebuild into existing
    tables) would update the row again with the same values. The data would not change, but the `MERGE` would report
    updated rows, the change data feed would carry update rows, and gold would recompute those dates for nothing. With
    `>`, the replay matches nothing, and the rerun of section 12.9 shows zero rows changed. An older version (the
    stale 1002) is ignored with either operator; `>=` only differs on an exact tie.

**Q10. Trace day 3's stale event for order 1002 (status `PLACED`, `updated_at` March 1) through silver. Which
tables does it change?**

??? success "Answer"
    None. It passes every rule, so it is not quarantined and counts as a valid event in the reconciliation check
    (bronze = valid + quarantined). It survives the in-batch `QUALIFY` (it is the only 1002 in that batch), but the
    orders `MERGE` finds `s.updated_at` (March 1) not greater than `t.updated_at` (the `SHIPPED` version, March 2), so
    the row is untouched. The items step only writes lines for versions that are in `silver.orders` (the join on
    `updated_at`), so the stale version's line is not written either. The day 3 output shows 1002 still `SHIPPED`.

**Q11. The items `MERGE` finds the accepted order versions by joining back to `silver.orders` on `order_id` and
`updated_at`. Why not collect the accepted ids in Python after step 3 and pass them in?**

??? success "Answer"
    Because the job can die between step 3 and step 4. On the retry, step 3 changes nothing (the versions are
    already there, and the guard is `>`), so a list of "what step 3 changed" would be empty and the lines would never
    be written. Joining back asks the table what is true now, so step 4 is correct whether or not step 3 just ran.
    The general rule: derive each step's input from the tables, not from what an earlier step remembers.

**Q12. Extend the project: on day 4 a correction removes a line from order 1007 (it now has only product 1). Show
that silver deletes the dropped line.**

??? success "Answer"
    The day 4 file holds the corrected 1007 (`updated_at` March 4, one line, amount 249.00) and a new order 1010.
    The `gone_lines` part of the items `MERGE` (section 12.4) deletes the line that the new version no longer has:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    e1007 = event(1007, 1, "2026-03-02T18:30:00Z", "PLACED", "249.00", "CAD", "2026-03-04T09:00:00Z",
                  [(1, 1, "249.00")], channel="app")
    # e1010: a new order 1010 that carries an extra field, "gift_wrap" (question 20)
    _write(ORDERS_IN, "orders_20260304_1800.json", [e1007, json.dumps(e1010)])
    run_all(spark)
    ```

    ```text
    >>> SELECT order_id, product_id, qty, line_amount, order_updated_at FROM silver.order_items WHERE order_id = 1007
    +--------+----------+---+-----------+-------------------+
    |order_id|product_id|qty|line_amount|order_updated_at   |
    +--------+----------+---+-----------+-------------------+
    |1007    |1         |1  |249.00     |2026-03-04 09:00:00|
    +--------+----------+---+-----------+-------------------+

    >>> SELECT version, operation, operationMetrics['numTargetRowsInserted'] AS inserted, operationMetrics['numTargetRowsUpdated'] AS updated, operationMetrics['numTargetRowsDeleted'] AS deleted FROM history_silver_order_items ORDER BY version DESC LIMIT 1
    +-------+---------+--------+-------+-------+
    |version|operation|inserted|updated|deleted|
    +-------+---------+--------+-------+-------+
    |2      |MERGE    |1       |1      |1      |
    +-------+---------+--------+-------+-------+
    ```

    Order 1007 now has one line. The last commit of `silver.order_items` shows all three branches of the items
    `MERGE`: 1 row inserted (order 1010's line), 1 updated (1007's product 1 line, which now carries the March 4
    version) and 1 deleted (1007's product 3 line, which the correction dropped). The version number is low because
    the full rebuild of section 12.9 created the table again. Without the `gone_lines` part, the product 3 line would
    stay, and the silver check `orders whose amount <> sum of their lines` would fail (249.00 against 278.95).

**Q13. Why does `upsert_customers` apply the snapshots one at a time, in date order, instead of merging the whole
batch at once?**

??? success "Answer"
    On a normal day the batch holds one snapshot, but in a rebuild (or after a missed day) it holds several. The SCD
    Type 2 `MERGE` compares the source with the **current** row, so it needs one row per customer in the source. Fed
    two snapshots at once, it would either fail with "multiple source rows matched" or, after a dedup, keep only the
    last snapshot and lose the versions in between: in the rebuild, Ana's Calgary version would never be created, and
    after a missed day, a change that was reverted the next day would vanish. Applying snapshots in order replays history as it happened; the rebuild in
    section 12.9 produces the same `silver.customers` as the day-by-day runs.

**Q14. Day 3 sends Ben's email as ` Ben.Okafor@Example.com `. What does the clean step do with it, and why does it
matter for SCD Type 2?**

??? success "Answer"
    It trims and lowercases the email before the change detection, so Ben gets one new version for a real change
    (`ben@example.com` to `ben.okafor@example.com`). Without it, formatting noise in the export (spaces, capitals)
    would count as a change: a new version on every day the export formats it differently, and history that says
    the customer changed when nothing did. Normalize before you compare; the change condition with `<=>` then only
    sees real changes.

**Q15. Extend the project: `customer_sk` is a 64-bit hash, so a collision is possible in theory. Add a gold check
that would catch one, and a second check that warns when a date between the first and last order has no
`daily_sales` row.**

??? success "Answer"
    A check is a (name, query, expected value, level) tuple, so extending the suite is adding two tuples:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    def gold_checks_extended():
        return _original_gold_checks() + [
            ("duplicate customer_sk in dim_customer",
             "SELECT count(*) - count(DISTINCT customer_sk) FROM gold.dim_customer", 0, "FAIL"),
            ("dates between first and last order with no daily_sales row",
             """SELECT count(*) FROM gold.dim_date d
                WHERE d.date BETWEEN (SELECT min(order_date) FROM gold.daily_sales)
                                 AND (SELECT max(order_date) FROM gold.daily_sales)
                  AND NOT EXISTS (SELECT 1 FROM gold.daily_sales s WHERE s.order_date = d.date)""", 0, "WARN"),
        ]

    checks.LAYERS["gold"] = gold_checks_extended
    run_checks(spark, "gold")
    ```

    ```text
      PASS  gold    duplicate (order_id, product_id) in fact_order_lines        got 0, expected 0
      PASS  gold    fact rows - silver.order_items rows                         got 0, expected 0
      PASS  gold    facts with no dim_customer row                              got 0, expected 0
      PASS  gold    facts with no dim_product row                               got 0, expected 0
      PASS  gold    facts with no dim_date row                                  got 0, expected 0
      PASS  gold    currencies where fact revenue <> silver order amounts       got 0, expected 0
      PASS  gold    currencies where daily_sales revenue <> fact revenue        got 0, expected 0
      PASS  gold    facts pointing at the unknown customer (-1)                 got 0, expected 0
      PASS  gold    duplicate customer_sk in dim_customer                       got 0, expected 0
      PASS  gold    dates between first and last order with no daily_sales row  got 0, expected 0
    ```

    The missing-date check is a WARN, not a FAIL: a day without sales can be real (a holiday), but it is worth a look.
    A real collision would also show up in the existing "facts with no dim_customer row" check only by luck, which is
    why the key itself is tested.

**Q16. Extend the project: on day 4 customer 99 finally appears in the snapshot. The silver WARN goes away, but
order 1005's fact row still points at `-1`. Why, and how do you fix it?**

??? success "Answer"
    Gold only recomputes dates whose orders changed, and no order on March 2 changed: the new customer arrived in
    `silver.customers`, not in `silver.orders`. So the fact row keeps its `-1` key (a **late-arriving dimension**).
    The fix is a re-key step: find the dates of facts that point at `-1` but whose customer now exists, and refresh
    those dates with the same `refresh_dates` function:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    dates = [r.order_date for r in sql("""
        SELECT DISTINCT f.order_date FROM gold.fact_order_lines f
        JOIN silver.customers c ON c.customer_id = f.customer_id
        WHERE f.customer_sk = -1""").collect()]
    print("dates to re-key:", dates)
    refresh_dates(spark, dates)
    refresh_ltv(spark)
    ```

    ```text
    >>> SELECT order_id, customer_id, customer_sk FROM gold.fact_order_lines WHERE order_id = 1005
    +--------+-----------+-----------+
    |order_id|customer_id|customer_sk|
    +--------+-----------+-----------+
    |1005    |99         |-1         |
    +--------+-----------+-----------+

    dates to re-key: [datetime.date(2026, 3, 2)]
    >>> SELECT f.order_id, f.order_ts, f.customer_sk, d.name, d.valid_from FROM gold.fact_order_lines f JOIN gold.dim_customer d ON d.customer_sk = f.customer_sk WHERE f.order_id = 1005
    +--------+-------------------+--------------------+--------+-------------------+
    |order_id|order_ts           |customer_sk         |name    |valid_from         |
    +--------+-------------------+--------------------+--------+-------------------+
    |1005    |2026-03-02 14:20:00|-6631395208366157837|Gus Hale|2026-03-04 10:00:00|
    +--------+-------------------+--------------------+--------+-------------------+

      PASS  gold    duplicate (order_id, product_id) in fact_order_lines   got 0, expected 0
      PASS  gold    fact rows - silver.order_items rows                    got 0, expected 0
      PASS  gold    facts with no dim_customer row                         got 0, expected 0
      PASS  gold    facts with no dim_product row                          got 0, expected 0
      PASS  gold    facts with no dim_date row                             got 0, expected 0
      PASS  gold    currencies where fact revenue <> silver order amounts  got 0, expected 0
      PASS  gold    currencies where daily_sales revenue <> fact revenue   got 0, expected 0
      PASS  gold    facts pointing at the unknown customer (-1)            got 0, expected 0
    ```

    The morning run's log showed the split: the silver check "orders for an unknown customer" went to `PASS ... got 0`,
    while the gold check "facts pointing at the unknown customer (-1)" stayed `WARN ... got 1`. After the re-key,
    order 1005 points at Gus Hale's version and every gold check passes. Note that his only version starts on March 4,
    after the order was placed on March 2; the `is_first` branch of the point-in-time join (section 12.6) gives an
    order older than a customer's first known version that first version, instead of `-1`. In production the re-key
    step belongs in the gold task, after the dimensions are refreshed, so it runs every day.

**Q17. Extend the project: write the silver "latest version, then explode the lines" step in PySpark and prove it
gives the same rows as `silver.order_items`.**

??? success "Answer"
    The DataFrame version is in section 12.4 (`Window.partitionBy("order_id")` with `row_number`, then `explode`).
    Run over all of bronze after day 4 and compared with the incrementally built table in both directions with
    `exceptAll` (which, unlike `subtract`, keeps duplicates, so a doubled row would show):

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    silver_lines = spark.table("silver.order_items").select("order_id", "product_id", "qty", "unit_price", "line_amount")
    print("rows only in PySpark result:", lines_df.exceptAll(silver_lines).count())
    print("rows only in silver.order_items:", silver_lines.exceptAll(lines_df).count())
    ```

    ```text
    rows only in PySpark result: 0
    rows only in silver.order_items: 0
    ```

    Zero both ways: four days of incremental `MERGE`s, including a correction that removed a line, ended where a
    one-shot computation over all of bronze ends. This is a useful test to keep: an incremental table should equal the
    same logic run in full.

**Q18. Extend the project: write `daily_sales` in PySpark from the fact and the product dimension, and compare it
with the table built by `REPLACE WHERE`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    f = spark.table("gold.fact_order_lines")
    p = spark.table("gold.dim_product")
    ds = (f.where(F.col("status") != "CANCELLED")
           .join(p, "product_id")
           .groupBy("order_date", "category", "currency")
           .agg(F.countDistinct("order_id").alias("orders"),
                F.sum("qty").alias("units"),
                F.sum("line_amount").alias("revenue")))
    gold_ds = spark.table("gold.daily_sales")
    print("rows only in PySpark result:", ds.exceptAll(gold_ds).count())
    print("rows only in gold.daily_sales:", gold_ds.exceptAll(ds).count())
    ```

    ```text
    rows only in PySpark result: 0
    rows only in gold.daily_sales: 0
    ```

    `count(DISTINCT order_id)` matters: an order with two lines in the same category counts once in `orders` and
    twice in the lines. `exceptAll` compares by column position, so the column order must match the table's.

**Q19. Extend the project: the quarantine needs an owner. Write the query they would look at each morning: rows per
reason, with the files they came from.**

??? success "Answer"
    `failed_rules` is an array, so explode it first; a row that broke two rules counts under both:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT reason, count(*) AS rows, collect_set(_file_name) AS files
    FROM silver.orders_quarantine LATERAL VIEW explode(failed_rules) r AS reason
    GROUP BY reason ORDER BY reason
    ```

    ```text
    >>> SELECT reason, count(*) AS rows, collect_set(_file_name) AS files FROM silver.orders_quarantine LATERAL VIEW explode(failed_rules) r AS reason GROUP BY reason ORDER BY reason
    +--------------+----+---------------------------+
    |reason        |rows|files                      |
    +--------------+----+---------------------------+
    |item_invalid  |1   |[orders_20260303_1800.json]|
    |malformed_json|1   |[orders_20260301_0900.json]|
    +--------------+----+---------------------------+
    ```

**Q20. Extend the project: order 1010 on day 4 carries a field nobody announced, `gift_wrap`. What does each layer
do with it, and which check notices?**

??? success "Answer"
    Bronze keeps it (it is part of the raw line). Silver ignores it: `from_json` with an explicit schema drops fields
    that are not in the schema, so the order loads normally. The bronze WARN check "order fields not in the contract"
    compares the JSON keys with the contract list (`ORDER_FIELDS`) and flags it, without stopping the run:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    [bronze] done
        bronze.orders: 2 rows read
        bronze.customers: 0 rows read
        bronze.products: 0 rows read
      PASS  bronze  every landing line is in bronze.orders           got 16, expected 16
      PASS  bronze  every landing row is in bronze.customers         got 20, expected 20
      PASS  bronze  every landing row is in bronze.products          got 5, expected 5
      PASS  bronze  bronze rows without file name or ingest time     got 0, expected 0
      WARN  bronze  order fields not in the contract (schema drift)  got 1, expected 0
    ```

    and the query behind it, run on its own to see where the field came from:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT k AS unexpected_field, count(*) AS rows, min(_file_name) AS first_file
    FROM (SELECT explode(json_object_keys(raw)) AS k, _file_name FROM bronze.orders)
    WHERE k NOT IN ('order_id','customer_id','order_ts','status','amount','currency',
                    'updated_at','channel','items')
    GROUP BY k
    ```

    ```text
    >>> SELECT k AS unexpected_field, count(*) AS rows, min(_file_name) AS first_file FROM (SELECT explode(json_object_keys(raw)) AS k, _file_name FROM bronze.orders) WHERE k NOT IN ('order_id','customer_id','order_ts','status','amount','currency', 'updated_at','channel','items') GROUP BY k
    +----------------+----+-------------------------+
    |unexpected_field|rows|first_file               |
    +----------------+----+-------------------------+
    |gift_wrap       |1   |orders_20260304_1800.json|
    +----------------+----+-------------------------+
    ```

    WARN is the right level: the data is not wrong, the contract is out of date. Someone decides whether `gift_wrap`
    joins the schema (and silver) or is ignored. On Databricks, Auto Loader with `schemaEvolutionMode` `rescue` would
    put the field in `_rescued_data` (section 12.3).

**Q21. `refresh_dates` filters its query with `WHERE o.order_date IN (...)`, the same list as the `REPLACE WHERE`
predicate. What happens if you forget the filter?**

??? success "Answer"
    The `INSERT` fails and writes nothing. The INSERT page says "By default, every row that `query` returns must match
    `boolean_expression`. If any row falls outside it, the `INSERT` fails and writes nothing". Without the filter the
    query returns rows for every date, most of them outside the predicate. That check is a safety net: without it, the
    statement would delete one date and insert all dates, duplicating the rest of the table. Keep the predicate and
    the filter built from the same list, as the code does with `in_list`.

**Q22. A correction changes an order's `order_ts` from March 1 to March 2. Which gold dates must be recomputed, and
does this project do it?**

??? success "Answer"
    Both: March 1 must lose the order and March 2 must gain it. It does, because `_refresh_changed_dates` reads every
    change row of the feed, including the `update_preimage` row, which carries the old `order_date` (March 1), as well
    as the `update_postimage` row with the new one (March 2). Filtering the feed to post-images only, a common
    shortcut, would leave the order counted on March 1 and on March 2.

**Q23. Extend the project: finance asks for a backfill of gold for March 1 to 3 "to be safe". Run it and prove that
nothing changed.**

??? success "Answer"
    A backfill is the same `refresh_dates` call with an explicit list of dates. Compare the table with its previous
    version in both directions:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    v = sql("DESCRIBE HISTORY gold.daily_sales LIMIT 1").first().version
    refresh_dates(spark, ["2026-03-01", "2026-03-02", "2026-03-03"])
    ```

    ```text
    >>> SELECT count(*) AS rows_that_differ FROM ( (SELECT * FROM gold.daily_sales EXCEPT ALL SELECT * FROM gold.daily_sales VERSION AS OF 3) UNION ALL (SELECT * FROM gold.daily_sales VERSION AS OF 3 EXCEPT ALL SELECT * FROM gold.daily_sales))
    +----------------+
    |rows_that_differ|
    +----------------+
    |0               |
    +----------------+

    >>> SELECT version, operation, operationParameters['predicate'] AS predicate FROM history_gold_daily_sales WHERE version > 3 ORDER BY version
    +-------+---------+-------------------------------------------------------------------------+
    |version|operation|predicate                                                                |
    +-------+---------+-------------------------------------------------------------------------+
    |4      |WRITE    |(order_date IN (DATE '2026-03-01', DATE '2026-03-02', DATE '2026-03-03'))|
    +-------+---------+-------------------------------------------------------------------------+
    ```

    Zero rows differ, and the history shows one commit that replaced exactly the three dates. A backfill through the
    same `REPLACE WHERE` function is safe to repeat, and a date range you did not list is not touched.

**Q24. Extend the project: which orders changed in the last commit to `silver.orders`, and how?**

??? success "Answer"
    Read the change data feed for that one version with `table_changes` (open-source Delta has it too):

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    last = sql("DESCRIBE HISTORY silver.orders LIMIT 1").first().version
    show(f"""SELECT order_id, order_date, amount, _change_type, _commit_version
             FROM table_changes('silver.orders', {last}) ORDER BY order_id, _change_type""")
    ```

    ```text
    >>> SELECT order_id, order_date, amount, _change_type, _commit_version FROM table_changes('silver.orders', 2) ORDER BY order_id, _change_type
    +--------+----------+------+----------------+---------------+
    |order_id|order_date|amount|_change_type    |_commit_version|
    +--------+----------+------+----------------+---------------+
    |1007    |2026-03-02|249.00|update_postimage|2              |
    |1007    |2026-03-02|278.95|update_preimage |2              |
    |1010    |2026-03-04|39.00 |insert          |2              |
    +--------+----------+------+----------------+---------------+
    ```

    The day 4 commit updated 1007 (the pre-image has the old amount 278.95, the post-image 249.00) and inserted 1010.
    These are the rows the gold stream read on day 4 ("silver.orders change rows -> gold facts: 3 rows read"), and their
    `order_date` values, March 2 and March 4, are the dates gold refreshed. Version 2 is the day 4 commit because the
    rebuild created the table again.

**Q25. Someone deletes the gold stream's checkpoint (`gold_facts`) but leaves every table. What does the next run
do, and is the result correct?**

??? success "Answer"
    The change-feed stream starts as if new, and the change data feed page says that a stream with no checkpoint
    "returns the latest snapshot of the table as `INSERT` records and then returns future changes". So the first batch
    holds every order, `_refresh_changed_dates` collects every order date, and `refresh_dates` rewrites all of them
    with `REPLACE WHERE`. The result is correct (the same rows), just more work than a normal day. This is the same
    path the full rebuild takes on purpose (section 12.9).

**Q26. Someone deletes the silver orders checkpoint but leaves the tables. What does the next run do?**

??? success "Answer"
    The stream re-reads all of `bronze.orders` and hands it to `upsert_orders`. Every step is written to absorb that:
    the quarantine `MERGE` is insert-only on (raw text, file), so known bad rows match and nothing is added; the
    `QUALIFY` keeps the newest version of each order, which silver already has, so the orders `MERGE` guard (`>`)
    updates nothing; the items `MERGE` finds the same lines with the same `order_updated_at` and nothing to delete.
    No rows change and gold sees no changes. This follows from the code rather than from a separate run; the rerun
    and rebuild in section 12.9 exercise the same paths.

**Q27. After the full rebuild, every fact row has the same `customer_sk` as before. Why is that not luck?**

??? success "Answer"
    The key is `xxhash64(customer_id, valid_from)`: a function of the customer version, not of the order in which rows
    were inserted. The rebuild applies the same snapshots in the same order, so each version gets the same
    `valid_from`, hence the same key, and the facts look up the same keys. An identity column would hand out values in
    insert order, and any difference in the replay (another order of batches, another number of snapshots per batch)
    would give a version a different number. The `-1` member is a constant for the same reason.

**Q28. Name two things `AUTO CDC` (formerly `APPLY CHANGES`) handles for customers that this project's hand-written
SCD Type 2 `MERGE` does not.**

??? success "Answer"
    Deletes: `AUTO CDC ... FROM SNAPSHOT` treats keys absent from a newer snapshot as deleted and ends their current
    row, and change-feed sources can use `APPLY AS DELETE WHEN`; the hand-written `MERGE` has no delete rule. And
    out-of-order changes: with `SEQUENCE BY`, `AUTO CDC` handles change events that arrive out of order ("The pipeline
    processing uses this sequencing to handle change events that arrive out of order", [AUTO CDC INTO
    (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-apply-changes-into)), while the hand-written `MERGE` can only add a version after
    the current one, so a change older than the current version would need a separate repair. A third, smaller one:
    `TRACK HISTORY ON` chooses which columns create a new version.

**Q29. The job's gold task fails after bronze and silver succeeded. What do you do, and why is it safe?**

??? success "Answer"
    Fix the cause and start a **repair run**, which reruns the failed task and the tasks that depend on it, not the
    tasks that already succeeded ([chapter 15](15-Lakeflow-Jobs.md)). It is safe because every gold step can run
    twice. If the failure came inside the change-feed batch, the stream had not committed its checkpoint for that
    batch, so the retry sees the same changes, and `REPLACE WHERE` rewrites the same dates whether or not part of the
    work happened before the failure. If it came after the batch committed (in `refresh_ltv` or the gold checks), the
    dates were already rewritten, and the dimensions and `customer_ltv` are recomputed in full on every run. One
    catch: a committed batch is not replayed, so if the fix changes the fact logic itself, refresh the affected dates
    explicitly with `refresh_dates` (the backfill of Q23). Rerunning the whole job would also be safe (bronze and
    silver would find nothing new), just slower.

**Q30. Analysts ask for `SELECT` on `silver.customers` to look up customers' emails. What do you answer?**

??? success "Answer"
    No direct access to silver: the layout of section 12.12 gives analysts gold only, and silver holds every version
    of every customer as loaded. Ask what they need. If it is a current customer list, `gold.dim_customer_current`
    (a view over `dim_customer` with the current rows only, created in `gold.py`) already has it. Note that `dim_customer` carries the email too, so if emails are personal data that analysts
    should not see, protect the column in gold (a column mask, [chapter 5](05-Unity-Catalog.md)) or leave it out of
    gold, rather than widening grants on silver.

## Sources

- [What is Auto Loader?](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/) (last updated Oct 15, 2026)
- [Common data loading patterns](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/patterns) (last updated Sep 11, 2026)
- [Configure schema inference and evolution in Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema) (last updated Nov 5, 2026)
- [Spark API options reference](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/options) (last updated Nov 5, 2026)
- [File metadata column](https://docs.databricks.com/aws/en/ingestion/file-metadata-column) (last updated Sep 11, 2026)
- [Use foreachBatch to write to arbitrary data sinks](https://docs.databricks.com/aws/en/structured-streaming/foreach) (last updated Nov 5, 2026)
- [Structured Streaming APIs on DataFrames and Datasets](https://spark.apache.org/docs/4.2.0/streaming/apis-on-dataframes-and-datasets.html) (Apache Spark 4.2.0 docs; the page shows no last-updated date)
- [`MERGE INTO`](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into) (last updated Sep 11, 2026)
- [`INSERT`](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-dml-insert-into) (last updated Oct 21, 2026)
- [Use change data feed on Databricks](https://docs.databricks.com/aws/en/delta/delta-change-data-feed) (last updated Oct 9, 2026)
- [`table_changes` table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/table_changes) (last updated Oct 15, 2026)
- [DESCRIBE HISTORY](https://docs.databricks.com/aws/en/sql/language-manual/delta-describe-history) (last updated Sep 11, 2026)
- [RESTORE](https://docs.databricks.com/aws/en/sql/language-manual/delta-restore) (last updated Sep 11, 2026)
- [Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/) (last updated Nov 5, 2026)
- [June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (release notes; last updated Oct 29, 2026)
- [Configure task dependencies](https://docs.databricks.com/aws/en/jobs/run-if) (last updated Nov 2, 2026)
- [Configure and edit tasks in Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/configure-task) (last updated Nov 5, 2026)
- [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (last updated Nov 5, 2026)
- [Declarative Automation Bundles configuration](https://docs.databricks.com/aws/en/dev-tools/bundles/settings) (last updated Sep 11, 2026)
- [Declarative Automation Bundles resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources) (last updated Nov 10, 2026)
- [Bundle configuration examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples) (last updated Oct 29, 2026)
- [Declarative Automation Bundles deployment modes](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes) (last updated Nov 4, 2026)
- [USE CATALOG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-use-catalog) (last updated Oct 29, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table) (last updated Oct 2, 2026)
- [CREATE TEMPORARY VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-temporary-view) (last updated Sep 11, 2026)
- [CREATE MATERIALIZED VIEW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-materialized-view) (last updated Oct 9, 2026)
- [Materialized views](https://docs.databricks.com/aws/en/ldp/materialized-views) (last updated Oct 15, 2026)
- [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations) (last updated Oct 26, 2026)
- [Expectation recommendations and advanced patterns](https://docs.databricks.com/aws/en/ldp/expectation-patterns) (last updated Oct 26, 2026)
- [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc) (last updated Nov 10, 2026)
- [AUTO CDC INTO (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-apply-changes-into) (last updated Nov 9, 2026)
- [Spark 4.2.0 release notes](https://spark.apache.org/releases/spark-release-4-2-0.html) (no date shown; read Nov 11, 2026)
- [`read_files` table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/read_files) (last updated Nov 10, 2026)
- [Set the target catalog and schema](https://docs.databricks.com/aws/en/ldp/target-schema) (last updated Sep 11, 2026)
- [Use parameters with pipelines](https://docs.databricks.com/aws/en/ldp/parameters) (last updated Nov 5, 2026)
- [CREATE VOLUME](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-volume) (last updated Sep 11, 2026)
- [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant) (last updated Sep 11, 2026)
- [Unity Catalog privileges reference](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/privileges) (last updated Nov 6, 2026)
- [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) (last updated Oct 30, 2026)
