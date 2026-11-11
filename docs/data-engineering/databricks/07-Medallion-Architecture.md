# 7. The medallion architecture explained

*Almost every Databricks data engineering team organizes its tables into bronze, silver and gold layers, and almost
every Databricks interview asks about it. This chapter explains what each layer holds and why, how the layers map to
Unity Catalog, how schema drift, duplicates, late data and change data capture are handled at each hop, why loads
must be safe to rerun, and when three layers are the wrong answer. It ends with a small pipeline for the Red Rock
Supply shop that was run end to end, so every claim about reruns and restatements comes with real output.*

!!! abstract "In this chapter"
    **You will learn:**

    - what bronze (raw), silver (validated) and gold (enriched) mean in the official Databricks description, what
      belongs in each layer, and who reads each one
    - how to lay the layers out in Unity Catalog (catalogs and schemas) and grant access per layer
    - how bronze absorbs schema drift (raw strings, `VARIANT`, ingest metadata, the rescued data column) and how
      silver enforces a schema
    - deduplication, late and out-of-order data, change data capture (CDC) and slowly changing dimensions (SCD)
    - how to make every load idempotent with `MERGE`, and the "multiple source rows matched" trap
    - data quality with expectations and the quarantine pattern
    - what gold looks like (dimensional models, aggregates, materialized views) and the cost vs latency choice
    - anti-patterns, and when the three-layer model does not fit
    - the same idea under other names, and how medallion relates to Kimball star schemas, Data Vault and data mesh
    - short answers to the questions interviewers push on: where deduplication and business logic belong, backfills,
      reruns, schema drift, late data, and how many layers is too many

    **You need:** 4. Delta Lake (transaction log, `MERGE`, time travel) and
    5. Unity Catalog (catalog.schema.table). 3. Apache Spark helps for
    the streaming parts.

    **Levels:** sections 7.1 to 7.3 beginner, 7.4 to 7.8 intermediate, 7.9 to 7.13 expert.

## 7.1 The problem: one messy table for everyone

*Level: beginner.*

Imagine Red Rock Supply loads its order events straight from the web shop's JSON files into one table called
`orders`, cleaning as it goes: it casts `amount` to a decimal, drops rows that fail, removes duplicates, and sums up
revenue in the same job. Three things go wrong within a month.

1. **A bad value disappears.** One file carries `"amount": "12.O0"` (a letter O instead of a zero). The cast turns it
   into `NULL` or fails the job. Either way, the original text is gone, so nobody can find out what the customer was
   actually charged.
2. **A rule changes and history cannot be rebuilt.** Finance decides that cancelled orders must be excluded from
   revenue. The old raw files were deleted after loading, so last year's numbers cannot be recomputed with the new rule.
3. **Everybody reads the same table for different reasons.** Auditors want every event as received, analysts want one
   clean row per order, the executive dashboard wants daily totals. One table cannot be all three at once.

The fix is to split the work into stages, each with one job and one kind of reader. Keep the data exactly as it
arrived; build a cleaned, trustworthy copy from it; build business-ready tables from that. Each stage is stored as its
own tables, so each can be rebuilt from the one before. Databricks calls this the **medallion architecture**.

## 7.2 Bronze, silver and gold: the official description

*Level: beginner.*

The Databricks documentation describes the medallion architecture as "a series of data layers that denote the
quality of data stored in the lakehouse", and describes it as a data design pattern whose goal is "to incrementally
and progressively improve the structure and quality of data as it flows through each layer". The page names the
three layers:

- **Bronze (raw):** raw data ingestion.
- **Silver (validated):** data cleaning and validation.
- **Gold (enriched):** dimensional modeling and aggregation.

The same page says medallion architectures "are sometimes also referred to as *multi-hop architectures*", because
data hops from one layer to the next. It also says: "Following the medallion architecture is a recommended best
practice but not a requirement." Keep that sentence ready for the interview; it shows you know the layers are a
convention, not a feature you switch on.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 255" role="img" aria-label="Sources feed bronze, bronze feeds silver, silver feeds gold, gold serves users. Quality increases left to right, and silver and gold can be rebuilt from bronze." font-family="sans-serif" font-size="13" fill="currentColor">
<defs><marker id="m71" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<text x="319" y="20" text-anchor="middle">quality, structure and trust increase at each hop</text>
<line x1="150" y1="30" x2="490" y2="30" stroke="currentColor" marker-end="url(#m71)"/>
<rect x="13" y="45" width="105" height="105" rx="6" fill="none" stroke="currentColor"/>
<text x="65" y="68" text-anchor="middle" font-weight="bold" font-size="14">Sources</text>
<text x="65" y="92" text-anchor="middle">files</text>
<text x="65" y="111" text-anchor="middle">Kafka</text>
<text x="65" y="130" text-anchor="middle">databases</text>
<rect x="140" y="45" width="105" height="105" rx="6" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="192" y="68" text-anchor="middle" font-weight="bold" font-size="14">Bronze</text>
<text x="192" y="92" text-anchor="middle">raw</text>
<text x="192" y="111" text-anchor="middle">append-only</text>
<text x="192" y="130" text-anchor="middle">+ ingest info</text>
<rect x="267" y="45" width="105" height="105" rx="6" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="319" y="68" text-anchor="middle" font-weight="bold" font-size="14">Silver</text>
<text x="319" y="92" text-anchor="middle">validated</text>
<text x="319" y="111" text-anchor="middle">deduplicated</text>
<text x="319" y="130" text-anchor="middle">typed</text>
<rect x="394" y="45" width="105" height="105" rx="6" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="446" y="68" text-anchor="middle" font-weight="bold" font-size="14">Gold</text>
<text x="446" y="92" text-anchor="middle">enriched</text>
<text x="446" y="111" text-anchor="middle">aggregated</text>
<text x="446" y="130" text-anchor="middle">modeled</text>
<rect x="521" y="45" width="105" height="105" rx="6" fill="none" stroke="currentColor"/>
<text x="573" y="68" text-anchor="middle" font-weight="bold" font-size="14">Users</text>
<text x="573" y="92" text-anchor="middle">dashboards</text>
<text x="573" y="111" text-anchor="middle">ML models</text>
<text x="573" y="130" text-anchor="middle">apps</text>
<line x1="119" y1="97" x2="138" y2="97" stroke="currentColor" marker-end="url(#m71)"/>
<line x1="246" y1="97" x2="265" y2="97" stroke="currentColor" marker-end="url(#m71)"/>
<line x1="373" y1="97" x2="392" y2="97" stroke="currentColor" marker-end="url(#m71)"/>
<line x1="500" y1="97" x2="519" y2="97" stroke="currentColor" marker-end="url(#m71)"/>
<path d="M446,151 C446,240 192,240 192,156" fill="none" stroke="currentColor" stroke-dasharray="5 4" marker-end="url(#m71)"/>
<text x="319" y="247" text-anchor="middle">rebuild silver and gold from bronze when the logic changes</text>
</svg>
<figcaption>Figure 7.1. The medallion (multi-hop) flow. Each hop improves the data; because bronze keeps everything, the later layers can always be recomputed.</figcaption>
</figure>

### Who uses each layer

The official page gives the intended users of each layer. This table copies it.

| | Bronze | Silver | Gold |
| --- | --- | --- | --- |
| What happens here | Raw data ingestion | Data cleaning and validation | Dimensional modeling and aggregation |
| Intended users | Data engineers, data operations, compliance and audit teams | Data engineers, data analysts (a refined dataset that still keeps the detail needed for in-depth analysis), data scientists | Business analysts and BI developers, data scientists and ML engineers, executives and decision makers, operational teams |

The page's example is a business operations team with one catalog called `ops`:

- `ops.bronze` ingests raw data from cloud storage, Kafka and Salesforce, with "no data cleanup or validation".
- `ops.silver` cleans and validates: customers and transactions are cleaned "by dropping nulls and quarantining
  invalid records", then joined into `customer_transactions`; Salesforce accounts and opportunities are joined into
  `account_opportunities`; `leads_raw` becomes `leads_cleaned`.
- `ops.gold` "is designed for business users" and "contains fewer datasets than silver and bronze":
  `customer_spending`, `account_performance`, `sales_pipeline_summary` and a highly aggregated `business_summary`
  for the executive staff.

Notice two details that interviewers like. Silver already contains joins (`customer_transactions`), so silver is not
"one table per source". And gold is smaller than silver: it holds what the business asks for, not a copy of everything.

!!! tip "In the interview"
    **"What is the medallion architecture?"** A layered design pattern for a lakehouse: bronze keeps raw data as
    received, silver holds validated, deduplicated, typed records, and gold holds business-level models and aggregates
    for BI and ML. Data quality improves at each hop, and because bronze keeps the full history, silver and gold can be
    rebuilt when logic changes. Databricks calls it a recommended best practice, not a requirement; it is also called
    multi-hop architecture.

## 7.3 What belongs in each layer, and why

*Level: beginner.*

The "why" for each layer comes from one question: what must this layer guarantee to the layer after it?

### Bronze: keep everything, exactly as received

The official page lists what bronze data typically looks like. It:

- "Contains and maintains the raw state of the data source in its original formats."
- "Is appended incrementally and grows over time."
- "Is intended for consumption by workloads that enrich data for silver tables, not for access by analysts and data
  scientists."
- "Serves as the single source of truth, preserving the data's fidelity."
- "Enables reprocessing and auditing by retaining all historical data."
- Can mix streaming and batch sources: cloud object storage, message buses such as Kafka and Kinesis, and federated
  systems.

Bronze does as little as possible. The docs say "Minimal data validation is performed in the bronze layer" and, to
protect against dropped data, "Databricks recommends storing most fields as string, VARIANT, or binary to protect
against unexpected schema changes". Metadata columns are added, "such as the provenance or source of the data (for
example, `_metadata.file_name`)". The guarantee bronze gives: **nothing that arrived is lost**.

### Silver: one trustworthy row per business record

Silver is built by reading bronze (or other silver tables) and writing silver tables. The docs list the operations
performed in silver: schema enforcement, handling of null and missing values, deduplication, resolution of
out-of-order and late-arriving data, data quality checks, schema evolution, type casting and joins. Silver "should
always include at least one validated, non-aggregated representation of each record". Silver is also where data
modeling starts, including the choice of how to store nested data: as `VARIANT`, as JSON strings, as structs, maps
and arrays, or flattened and normalized into several tables. The guarantee silver gives: **every row has passed the
rules, has the right types, and appears once**.

### Gold: answer business questions fast

Gold "represents highly refined views of the data that drive downstream analytics, dashboards, ML, and
applications". It is "often highly aggregated and filtered for specific time periods or geographic regions", aligned
with business logic, and optimized for query performance. The docs add that, because gold models a business domain,
"some customers create multiple gold layers to meet different business needs, such as HR, finance, and IT". The
guarantee gold gives: **the numbers match the business definition, and dashboards are fast**.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Three columns comparing what bronze, silver and gold store, who reads each, and each layer's rule." font-family="sans-serif" font-size="13" fill="currentColor">
<rect x="10" y="10" width="200" height="280" rx="6" fill="none" stroke="currentColor"/>
<rect x="220" y="10" width="200" height="280" rx="6" fill="none" stroke="currentColor"/>
<rect x="430" y="10" width="200" height="280" rx="6" fill="none" stroke="currentColor"/>
<text x="110" y="34" text-anchor="middle" font-weight="bold" font-size="15">Bronze (raw)</text>
<text x="320" y="34" text-anchor="middle" font-weight="bold" font-size="15">Silver (validated)</text>
<text x="530" y="34" text-anchor="middle" font-weight="bold" font-size="15">Gold (enriched)</text>
<text x="22" y="60" font-weight="bold">Stores</text>
<text x="232" y="60" font-weight="bold">Stores</text>
<text x="442" y="60" font-weight="bold">Stores</text>
<text x="22" y="82">JSON line as STRING,</text>
<text x="22" y="102">or VARIANT, or binary</text>
<text x="22" y="122">_source_file, _ingested_at</text>
<text x="22" y="142">_rescued_data column</text>
<text x="22" y="162">every version, appended</text>
<text x="232" y="82">typed columns, NOT NULL</text>
<text x="232" y="102">one row per order</text>
<text x="232" y="122">quarantine table beside it</text>
<text x="232" y="142">CDC applied: SCD 1 or 2</text>
<text x="232" y="162">joined, conformed values</text>
<text x="442" y="82">daily_sales, customer_ltv</text>
<text x="442" y="102">facts and dimensions</text>
<text x="442" y="122">materialized views</text>
<text x="442" y="142">business names, measures</text>
<text x="442" y="162">tuned for dashboards</text>
<line x1="20" y1="178" x2="200" y2="178" stroke="currentColor" stroke-dasharray="3 3"/>
<line x1="230" y1="178" x2="410" y2="178" stroke="currentColor" stroke-dasharray="3 3"/>
<line x1="440" y1="178" x2="620" y2="178" stroke="currentColor" stroke-dasharray="3 3"/>
<text x="22" y="200" font-weight="bold">Read by</text>
<text x="232" y="200" font-weight="bold">Read by</text>
<text x="442" y="200" font-weight="bold">Read by</text>
<text x="22" y="222">data engineers,</text>
<text x="22" y="242">operations, audit</text>
<text x="232" y="222">data engineers,</text>
<text x="232" y="242">analysts, data scientists</text>
<text x="442" y="222">BI, executives,</text>
<text x="442" y="242">ML engineers, apps</text>
<text x="22" y="274" font-style="italic">Rule: lose nothing</text>
<text x="232" y="274" font-style="italic">Rule: trust every row</text>
<text x="442" y="274" font-style="italic">Rule: answer the question</text>
</svg>
<figcaption>Figure 7.2. What each layer stores for the Red Rock Supply orders, who reads it, and the one rule it must keep.</figcaption>
</figure>

### Why not do it all in one step?

Each split buys something specific:

| Split | What it buys |
| --- | --- |
| Raw kept apart from clean | Reprocessing and audit: a bug fix or new rule is applied by rerunning silver over bronze. A failed parse never loses data. |
| Clean kept apart from aggregated | One validated detail table feeds many gold tables, so "what is an order?" is answered once, not in every report. |
| Each layer its own tables | Different access: analysts can read gold without seeing raw personal data in bronze. Different refresh speeds and costs per layer. |
| Small steps | Each step is easier to test, monitor and restart than one large job. |

The cost is storage and extra jobs. On cloud object storage, storage is usually the cheap part, and the docs' advice
is to optimize gold for queries while large amounts of history are "typically accessed in the [silver] layer and not
materialized in the gold layer". Section 7.11 covers when the cost is not worth it.

!!! tip "In the interview"
    **"Why not clean the data as you load it into bronze?"** Because cleaning is a decision that can be wrong or can
    change. If bronze keeps the data exactly as it arrived (fields as strings or `VARIANT`, plus source file and load
    time), a bad parse never loses data, and when the rules change you replay silver from bronze. Databricks recommends
    minimal validation in bronze for exactly this reason.

## 7.4 Mapping the layers to Unity Catalog

*Level: intermediate.*

Unity Catalog names every table with three levels, `catalog.schema.table` (see chapter 5).
The layers have to fit into those levels together with environments (development, staging, production) and teams.
Two pages guide the choice:

- The medallion page's example puts all three layers in **one catalog, one schema per layer**: `ops.bronze`,
  `ops.silver`, `ops.gold`.
- The Unity Catalog best practices page says "Catalogs are the primary unit of data isolation" and that "Often, this
  means that catalogs correspond to an environment scope, team, business unit, or some combination of these." It also
  says a catalog can be bound to specific workspaces when work environments and data share the same isolation needs.

Combining the two gives the layout most teams use, and the one this book uses: **a catalog per environment (or per
environment and domain), with a schema per layer inside it**.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 290" role="img" aria-label="Left: catalogs shop_dev and shop_prod, each with bronze, silver and gold schemas. Right: the docs example, one ops catalog with bronze, silver and gold schemas and the users of each." font-family="sans-serif" font-size="13" fill="currentColor">
<text x="160" y="24" text-anchor="middle" font-weight="bold">Catalog per environment,</text>
<text x="160" y="42" text-anchor="middle" font-weight="bold">schema per layer</text>
<rect x="25" y="60" width="120" height="30" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="85" y="80" text-anchor="middle">shop_dev</text>
<line x1="45" y1="90" x2="45" y2="188" stroke="currentColor"/>
<line x1="45" y1="118" x2="60" y2="118" stroke="currentColor"/>
<line x1="45" y1="153" x2="60" y2="153" stroke="currentColor"/>
<line x1="45" y1="188" x2="60" y2="188" stroke="currentColor"/>
<rect x="60" y="105" width="85" height="26" rx="4" fill="none" stroke="currentColor"/>
<rect x="60" y="140" width="85" height="26" rx="4" fill="none" stroke="currentColor"/>
<rect x="60" y="175" width="85" height="26" rx="4" fill="none" stroke="currentColor"/>
<text x="102" y="123" text-anchor="middle">bronze</text>
<text x="102" y="158" text-anchor="middle">silver</text>
<text x="102" y="193" text-anchor="middle">gold</text>
<rect x="170" y="60" width="130" height="30" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="235" y="80" text-anchor="middle">shop_prod</text>
<line x1="190" y1="90" x2="190" y2="188" stroke="currentColor"/>
<line x1="190" y1="118" x2="205" y2="118" stroke="currentColor"/>
<line x1="190" y1="153" x2="205" y2="153" stroke="currentColor"/>
<line x1="190" y1="188" x2="205" y2="188" stroke="currentColor"/>
<rect x="205" y="105" width="85" height="26" rx="4" fill="none" stroke="currentColor"/>
<rect x="205" y="140" width="85" height="26" rx="4" fill="none" stroke="currentColor"/>
<rect x="205" y="175" width="85" height="26" rx="4" fill="none" stroke="currentColor"/>
<text x="247" y="123" text-anchor="middle">bronze</text>
<text x="247" y="158" text-anchor="middle">silver</text>
<text x="247" y="193" text-anchor="middle">gold</text>
<text x="160" y="228" text-anchor="middle">same schema and table names in each</text>
<text x="160" y="246" text-anchor="middle">catalog: code moves by one parameter</text>
<line x1="320" y1="15" x2="320" y2="250" stroke="currentColor" stroke-dasharray="4 4"/>
<text x="480" y="24" text-anchor="middle" font-weight="bold">Docs example: one catalog,</text>
<text x="480" y="42" text-anchor="middle" font-weight="bold">schema per layer</text>
<rect x="345" y="60" width="100" height="30" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="395" y="80" text-anchor="middle">ops</text>
<line x1="365" y1="90" x2="365" y2="188" stroke="currentColor"/>
<line x1="365" y1="118" x2="380" y2="118" stroke="currentColor"/>
<line x1="365" y1="153" x2="380" y2="153" stroke="currentColor"/>
<line x1="365" y1="188" x2="380" y2="188" stroke="currentColor"/>
<rect x="380" y="105" width="85" height="26" rx="4" fill="none" stroke="currentColor"/>
<rect x="380" y="140" width="85" height="26" rx="4" fill="none" stroke="currentColor"/>
<rect x="380" y="175" width="85" height="26" rx="4" fill="none" stroke="currentColor"/>
<text x="422" y="123" text-anchor="middle">bronze</text>
<text x="422" y="158" text-anchor="middle">silver</text>
<text x="422" y="193" text-anchor="middle">gold</text>
<text x="475" y="123">engineers, audit</text>
<text x="475" y="158">engineers, analysts, DS</text>
<text x="475" y="193">business users</text>
<text x="320" y="278" text-anchor="middle">Grants follow the tree: USE CATALOG, then USE SCHEMA and SELECT on the gold schema.</text>
</svg>
<figcaption>Figure 7.3. Two layouts. Left: the layout used in this book, a catalog per environment with a schema per layer. Right: the example on the Databricks medallion page.</figcaption>
</figure>

| Layout | Example name | Strengths | Weaknesses |
| --- | --- | --- | --- |
| One catalog, schema per layer (docs example) | `ops.silver.customer_transactions` | Simple; matches the docs | Dev and prod need separate catalogs anyway, so most teams add an environment level |
| Catalog per environment, schema per layer | `shop_prod.silver.orders` | Environments isolated at the catalog (the primary isolation unit); a catalog can be bound to the production workspace; code switches environment with one parameter | More catalogs to manage |
| Catalog per environment and domain | `sales_prod.gold.daily_sales` | Domain teams own their catalogs (fits "data as a product") | Cross-domain joins span catalogs |
| Catalog per layer, schema per domain | `silver.sales.orders` | Seen in practice; one place to grant "all of gold" | Not the pattern shown on the pages checked; environments still need a separate split |

The last row is a pattern teams use; no Databricks page I checked recommends or rejects it, so present it as an
option, not as guidance.

### Access control per layer

Layers make access control simple, because privileges in Unity Catalog are inherited down the tree: a `SELECT` grant
on a schema covers the tables in it. To read a table, a user also needs `USE CATALOG` on its catalog and `USE SCHEMA`
on its schema. A typical policy:

*Databricks only, not run here. Syntax from [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant).*

```sql
-- analysts read gold (and silver for detail), never bronze
GRANT USE CATALOG ON CATALOG shop_prod TO `analysts`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop_prod.gold   TO `analysts`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop_prod.silver TO `analysts`;

-- only the pipeline's service principal writes
GRANT USE SCHEMA, MODIFY, SELECT ON SCHEMA shop_prod.silver TO `etl-service-principal`;
```

The UC best practices page backs the second part: "Reserve direct `MODIFY` access to production tables for service
principals", run jobs as service principals, and give ownership of production catalogs and schemas to groups, not
individual users. Bronze often holds raw personal data (emails, addresses); keeping analysts out of bronze is both
the docs' intent ("not for access by analysts and data scientists") and a privacy control.

!!! tip "In the interview"
    **"How would you lay out bronze, silver and gold in Unity Catalog?"** Catalogs are the isolation unit, so I use a
    catalog per environment, for example `shop_dev` and `shop_prod`, with `bronze`, `silver` and `gold` schemas in
    each, the shape of the docs' `ops.bronze`/`ops.silver`/`ops.gold` example. Same table names in every catalog, so a
    job only changes the catalog parameter. Grants follow layers: analysts get `SELECT` on gold (and maybe silver),
    only service principals write to production.

## 7.5 Bronze in depth: schema drift and raw storage

*Level: intermediate.*

**Schema drift** means the shape of incoming data changes without warning: a new field appears, a field disappears,
a number arrives as text, a field changes case. **Schema evolution** is the controlled response: changing the table's
schema to accept the new shape. Bronze is designed so that drift never breaks ingestion and never loses data.

### Three ways bronze stores data safely

1. **Everything as strings.** When Auto Loader infers a schema for JSON, CSV or XML, it infers all columns as strings
   by default, including nested JSON fields, "to avoid schema evolution issues due to type mismatches" (Auto Loader
   schema page). Typed formats (Parquet, Avro) keep their encoded types. The option `cloudFiles.inferColumnTypes` set
   to `true` switches to type inference.
2. **One `VARIANT` column.** With the `singleVariantColumn` option, Auto Loader loads each whole record into one
   `VARIANT` column. The docs call this pattern robust to most ingestion scenarios, with caveats: malformed records
   cannot be encoded as `VARIANT`, a `VARIANT` value holds records up to 16 MB, and because the whole record is one
   column, no schema evolution occurs and `rescuedDataColumn` is not supported (variant ingestion page; `VARIANT`
   ingestion of JSON needs Databricks Runtime 15.3 and above). Chapter 18 covers querying `VARIANT`.
3. **The raw line as one `STRING`** (or binary). The simplest form, and what the worked example in 7.10 uses.

Then add **metadata columns**. Every file-based source has a hidden `_metadata` struct column with `file_path`,
`file_name`, `file_size`, `file_modification_time`, `file_block_start` and `file_block_length`. You must select it
explicitly, and the docs recommend selecting specific fields rather than the whole struct, because new fields might
be added in future releases. Add your own load timestamp too. These columns answer the audit question "which file did
this row come from, and when did we load it?", and silver uses them to break ties between duplicates.

*Databricks only, not run here. Syntax from [Configure schema inference and evolution in Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema), [File metadata column](https://docs.databricks.com/aws/en/ingestion/file-metadata-column) and [Configure Structured Streaming trigger intervals](https://docs.databricks.com/aws/en/structured-streaming/triggers).*

```python
from pyspark.sql import functions as F

(spark.readStream.format("cloudFiles")
   .option("cloudFiles.format", "json")
   # where Auto Loader keeps the inferred schema and its changes over time
   .option("cloudFiles.schemaLocation", "/Volumes/shop_prod/bronze/_meta/orders_schema")
   .load("/Volumes/shop_prod/bronze/landing/orders/")
   .select("*",
           F.col("_metadata.file_name").alias("_source_file"),
           F.col("_metadata.file_modification_time").alias("_file_modified_at"),
           F.current_timestamp().alias("_ingested_at"))
   .writeStream
   .option("checkpointLocation", "/Volumes/shop_prod/bronze/_meta/orders_checkpoint")
   .trigger(availableNow=True)
   .toTable("shop_prod.bronze.orders"))
```

Auto Loader records the files it has seen in its checkpoint (a RocksDB key-value store), which "ensures that data is
processed exactly once", so rerunning this job does not reload old files (Auto Loader overview page). Chapter 8 covers
Auto Loader, `COPY INTO` and `read_files` in full.

### What happens when a new column appears

Auto Loader's behavior is set by `cloudFiles.schemaEvolutionMode`. The modes, from the Auto Loader schema page:

| Mode | Behavior on reading a new column |
| --- | --- |
| `addNewColumns` (default when no schema is provided) | Stream fails with an `UnknownFieldException` after adding the new columns to the schema. Restarting resumes with the updated schema. Existing columns do not change type. |
| `addNewColumnsWithTypeWidening` | Like `addNewColumns`, and also widens supported types (such as `int` to `long`); unsupported changes go to the rescued data column. Public Preview, Databricks Runtime 16.4 and above. |
| `rescue` | Never evolves the schema and never fails; new columns are recorded in the rescued data column. |
| `failOnNewColumns` | Stream fails and does not restart until you update the schema or remove the file. |
| `none` (default when you provide a schema) | Does not evolve; new columns are ignored; data is not rescued unless `rescuedDataColumn` is set. |

The fail-then-restart behavior of the default mode surprises people. The docs recommend running Auto Loader streams
as Lakeflow Jobs (formerly Databricks Workflows) so they restart automatically after such a schema change. In
Lakeflow pipelines (formerly Delta Live Tables), Databricks manages the schema location and checkpoints for you.

### The rescued data column

When Auto Loader infers the schema, it adds a column named `_rescued_data`. It catches data that does not fit the
schema instead of dropping it: columns missing from the schema, type mismatches and case mismatches. The column holds
a JSON blob with the rescued columns and the source file path of the record. Only truly corrupt records (incomplete or
malformed JSON or CSV) fail or go to `badRecordsPath`. In silver you can check `_rescued_data IS NOT NULL` to find
rows that need attention.

### Why typing at bronze loses data: a run

The open-source engine here does not have Auto Loader, but it shows the core problem. The file holds orders 1002 and
1003; 1003 has the typo `"amount": "12.O0"`. First read it with a typed schema, the way a careless bronze job would:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
typed = (spark.read
         .schema("order_id INT, amount DECIMAL(10,2), _corrupt_record STRING")
         .json(LANDING))
typed.createOrReplaceTempView("typed_read")
show("SELECT order_id, amount, _corrupt_record IS NOT NULL AS flagged_corrupt FROM typed_read ORDER BY order_id")

typed_no_corrupt = spark.read.schema("order_id INT, amount DECIMAL(10,2)").json(LANDING)
typed_no_corrupt.createOrReplaceTempView("typed_read2")
show("SELECT order_id, amount FROM typed_read2 ORDER BY order_id")
```

```text
+--------+------+---------------+
|order_id|amount|flagged_corrupt|
+--------+------+---------------+
|1002    |120.00|false          |
|1003    |NULL  |true           |
+--------+------+---------------+

+--------+------+
|order_id|amount|
+--------+------+
|1002    |120.00|
|1003    |NULL  |
+--------+------+
```

Without a `_corrupt_record` column, the value `12.O0` silently became `NULL` and the original text is gone. Now keep
the line as a string and type it later:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT get_json_object(value, '$.order_id') AS order_id,
       get_json_object(value, '$.amount')   AS amount_raw,
       try_cast(get_json_object(value, '$.amount') AS DECIMAL(10,2)) AS amount_typed
FROM text.`<landing folder>` ORDER BY order_id
```

```text
+--------+----------+------------+
|order_id|amount_raw|amount_typed|
+--------+----------+------------+
|1002    |120.00    |120.00      |
|1003    |12.O0     |NULL        |
+--------+----------+------------+
```

The raw text survives, and silver can decide what to do with it. Note `try_cast`: with ANSI mode on (as in this Spark
4.2 engine), a plain `CAST` of a malformed string fails the whole query:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT CAST('12.O0' AS DECIMAL(10,2))
```

```text
ERROR: [CAST_INVALID_INPUT] The value '12.O0' of the type "STRING" cannot be cast to "DECIMAL(10,2)" because it is malformed. Correct the value as per the syntax, or change its target type. Use `try_cast` to tolerate malformed 
```

!!! warning "Bronze is not a dumping ground"
    "Raw" does not mean "anything goes". Bronze still needs the metadata columns, a checkpoint so files load once, a
    retention decision (bronze holds personal data too), and access control. And bronze tables are Delta tables, not
    loose files: Auto Loader and `COPY INTO` land data in a table with a transaction log.

## 7.6 Silver in depth: enforce, deduplicate, order, model

*Level: intermediate.*

### Read bronze, do not ingest directly into silver

The docs are explicit: "Databricks does not recommend writing to silver tables directly from ingestion. If you write
directly from ingestion, you'll introduce failures due to schema changes or corrupt records in data sources." Bronze
is the shock absorber; silver reads from it.

**How should silver read bronze?** "Assuming all sources are append-only, configure most reads from bronze as
streaming reads. Batch reads should be reserved for small datasets (for example, small dimensional tables)." A
streaming read of a Delta table processes only the new commits since the last run, tracked in a checkpoint, so each
run costs in proportion to the new data, not the whole table. With the `AvailableNow` trigger the stream processes
everything available and stops, which gives incremental batch jobs on a schedule (see
chapter 11).

The phrase "assuming all sources are append-only" matters. The Delta streaming page says a streaming read of a Delta
table "only accepts append inputs and throws an exception if any modifications occur on the source": an `UPDATE`,
`DELETE`, `MERGE INTO` or `OVERWRITE` on the source table fails the stream. Bronze is append-only, so streaming from
bronze is safe. Silver is often updated with `MERGE`, so a plain stream from silver to gold breaks. The documented
ways out are `skipChangeCommits` (ignore the changes; process appends only), a full refresh, streaming from the
table's change data feed ("Databricks recommends streaming from the CDC feed of a Delta Lake table rather than
directly from the table whenever possible"), or a materialized view.

### Schema enforcement

Silver tables have a declared schema, and Delta enforces it on write: columns must exist in the target and types must
match (Databricks attempts a safe cast) ("Schema enforcement" page). Delta also enforces `NOT NULL` column
constraints. Both are your last line of defense when a rule is missed upstream. Both ran here (`day2` is a one-row
view with the silver columns plus `channel`; each refused statement ran inside `try`/`except`, see `traps_demo.py`
sections 4 and 5):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
# day2 has the silver columns plus a new column, channel
sql("INSERT INTO silver_orders SELECT * FROM day2")                                  # refused
spark.table("day2").write.format("delta").mode("append").saveAsTable("silver_orders") # refused
spark.table("day2").write.format("delta").mode("append") \
     .option("mergeSchema", "true").saveAsTable("silver_orders")                      # evolves
show("SELECT * FROM silver_orders ORDER BY order_id")

sql("CREATE TABLE silver_strict (order_id INT NOT NULL, customer_id INT NOT NULL) USING DELTA")
sql("INSERT INTO silver_strict VALUES (1006, NULL)")                                  # refused
```

```text
ERROR: [DELTA_METADATA_MISMATCH] A metadata mismatch was detected when writing to the Delta table.
ERROR: [DELTA_METADATA_MISMATCH] A metadata mismatch was detected when writing to the Delta table.
+--------+------+-------------------+-------+
|order_id|amount|updated_at         |channel|
+--------+------+-------------------+-------+
|1002    |120.00|2026-03-01 11:02:00|NULL   |
|1004    |35.50 |2026-03-01 16:20:00|NULL   |
|1005    |89.00 |2026-03-02 09:05:00|app    |
+--------+------+-------------------+-------+

ERROR: [DELTA_NOT_NULL_CONSTRAINT_VIOLATED] NOT NULL constraint violated for column: customer_id.
```

The error classes above are from open-source Delta 4.4.1; Databricks applies the same rules, but its error text can
differ. On Databricks, schema evolution is asked for per write: the `mergeSchema` option, `MERGE WITH SCHEMA
EVOLUTION`, or `INSERT WITH SCHEMA EVOLUTION` (Databricks Runtime 18.1 and above). Databricks recommends these
per-operation forms over the session-wide setting `spark.databricks.delta.schema.autoMerge.enabled` ("Update table
schemas with schema evolution" page).

So the full answer to "a source added a column overnight" is layer by layer: bronze takes it in (raw string, or Auto
Loader evolves the schema and restarts, or the value lands in `_rescued_data`); silver ignores it until someone
decides it belongs there, because silver selects named columns and enforces its schema; when it is wanted, you add it
to silver deliberately (with schema evolution or `ALTER TABLE ... ADD COLUMN`) and backfill it from bronze; gold
changes only if a business measure needs it.

### Deduplication

Duplicates come from many places: a source re-sends a file, a producer retries a Kafka message, a job reruns after a
failure, two systems both send the same customer. Silver removes them, in two places:

- **Within the batch:** keep one row per business key, usually the newest, with
  `QUALIFY row_number() OVER (PARTITION BY key ORDER BY updated_at DESC) = 1` (`QUALIFY` is covered in
  chapter 17; window functions in the
  [SQL course](../../databases/sql/13-Window-Functions-Ranking.md)).
- **Against the table:** `MERGE` on the business key, so a row already in silver is updated or skipped, not added again.

You need both. The Delta merge page warns: "The dataset containing the new logs needs to be deduplicated within
itself... if there is duplicate data within the new dataset, it is inserted." Section 7.9 shows both failure modes
running.

### Late and out-of-order data

**Late data** arrives after the period it belongs to: a correction for a March 1 order arrives on March 2.
**Out-of-order data** arrives in a different order from the order events happened: version 3 of a record arrives
before version 2. Arrival order is not event order, so silver must never let "last loaded" win. It needs a column
that orders versions of the same record: an `updated_at` timestamp, a sequence number, a log position from the source
database. The `MERGE` then updates only when the incoming version is newer:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
```

With that guard, an older version that arrives late is ignored, and replaying the same version changes nothing. For
streaming aggregations, Structured Streaming uses watermarks to decide how long to wait for late events
(chapter 11).

### Change data capture and slowly changing dimensions

**Change data capture (CDC)** "treats a database as a set of changes, rather than as a complete static database"
(the Databricks CDC page). Each change row carries the operation (insert, update, delete) and "a column that can be
used to deterministically order each row in the CDC feed so that you can handle out-of-order updates". CDC feeds land
in bronze as they come; silver applies them to build the current or historical state.

**Slowly changing dimensions (SCD)** define how those changes are kept:

- **SCD Type 1** "overwrites old data with new data whenever changes occur, keeping only the latest version of each
  record. History is not retained." Use it when only the current value matters (a corrected email typo).
- **SCD Type 2** "maintains a complete historical record by creating multiple versions of data over time". Use it
  when history matters: if customer 7 moves from Calgary to Denver, sales before the move should still count for
  Calgary.

What SCD Type 2 looks like for that customer:

| customer_id | city | __START_AT | __END_AT |
| --- | --- | --- | --- |
| 7 | Calgary | 2025-06-01 | 2026-02-10 |
| 7 | Denver | 2026-02-10 | NULL |

`__START_AT` and `__END_AT` are the column names that Lakeflow's `AUTO CDC` produces; active records have
`__END_AT = NULL`. The CDC page also describes a third option, **bitemporal** tables, which "extends SCD Type 2 to save
history across two timelines: when each change took effect, and when your system learned about it". After a late
correction, SCD Type 2 rewrites history; a bitemporal table also remembers what the table said before the fix, which
matters for reproducing past reports. Bitemporal requires `AUTO CDC` with a system time column
(`SYSTEM SEQUENCE BY`).

In a Lakeflow pipeline (formerly Delta Live Tables), the whole SCD Type 2 job is one statement (`AUTO CDC` replaces `APPLY CHANGES`, with the same
syntax):

*Databricks only, not run here. Syntax from [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc).*

```sql
CREATE OR REFRESH STREAMING TABLE customers_history;

CREATE FLOW customers_scd2 AS AUTO CDC INTO
  customers_history
FROM
  stream(shop_prod.bronze.customers_cdc)
KEYS
  (customer_id)
APPLY AS DELETE WHEN
  operation = "DELETE"
SEQUENCE BY
  updated_at
COLUMNS * EXCEPT
  (operation)
STORED AS
  SCD TYPE 2;
```

Hand-written SCD Type 1 and Type 2 with `MERGE` (run here) are in [chapter 9](09-Building-Silver.md); `AUTO CDC` in
detail, including `AUTO CDC FROM SNAPSHOT` for sources that only send full snapshots, is in
chapter 14. The generic SCD theory is in the
[SQL course data modelling chapter](../../databases/sql/19-Data-Modelling.md).

!!! tip "In the interview"
    **"How do you handle out-of-order CDC events?"** Never trust arrival order. Every change needs a sequencing column
    (a source timestamp or log sequence number). In a hand-written `MERGE`, deduplicate the batch to the latest version
    per key and update only when the incoming sequence is greater than the stored one. In a Lakeflow pipeline,
    `AUTO CDC ... SEQUENCE BY` does this for you, for SCD Type 1 or Type 2.

## 7.7 Data quality: expectations and quarantine

*Level: intermediate.*

Validation happens when data enters silver. The "Guiding principles" page puts it this way: "The validation of new
data happens at the time of data entry into the curated layer". The question is what to do with a row that fails.

### Expectations in Lakeflow pipelines

In Lakeflow pipelines (formerly Delta Live Tables), a data quality rule is an **expectation**: a named SQL Boolean condition attached to a
streaming table, materialized view or temporary view. Each expectation has an action on invalid records (expectations page):

| Action | SQL | Python (`from pyspark import pipelines as dp`) | Result |
| --- | --- | --- | --- |
| warn (default) | `EXPECT` | `dp.expect` | Invalid records are written to the target |
| drop | `EXPECT ... ON VIOLATION DROP ROW` | `dp.expect_or_drop` | Invalid records are dropped; the count is logged |
| fail | `EXPECT ... ON VIOLATION FAIL UPDATE` | `dp.expect_or_fail` | The update fails; a table update is rolled back atomically |

*Databricks only, not run here. Syntax from [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations).*

```sql
CREATE OR REFRESH STREAMING TABLE orders_clean (
  CONSTRAINT valid_order_id  EXPECT (order_id IS NOT NULL)       ON VIOLATION DROP ROW,
  CONSTRAINT valid_amount    EXPECT (amount >= 0)                ON VIOLATION DROP ROW,
  CONSTRAINT known_currency  EXPECT (currency IN ('CAD', 'USD'))
) AS SELECT * FROM STREAM(shop_prod.bronze.orders_parsed);
```

The pipeline records pass and fail counts for warn and drop, so data quality becomes a monitored metric. Fail records
no metrics, because the update stops. Chapter 14 covers expectations in depth.

### The quarantine pattern

Dropping a row keeps silver clean, but the row is gone from silver and someone may need to fix it. **Quarantine**
routes invalid rows to a separate table instead, with the reason they failed, so that:

- silver contains only valid rows;
- nothing is lost (bronze also has it, but the quarantine table is the to-do list);
- the quarantine row count is a data quality metric you can alert on;
- after a fix (in the source or in the rules), the rows can be reprocessed.

The docs show this pattern for pipelines: the expectation-patterns page computes an `is_quarantined` flag from the
rules and splits valid and invalid rows into separate views. Outside pipelines, the foreachBatch page writes invalid
rows to what it calls a dead-letter queue table. Some teams call it an error table or reject table; the idea is the
same. The worked example in 7.10 builds one by hand, with an array of failed rule names per row.

!!! tip "In the interview"
    **"Drop, fail or quarantine?"** Fail when a bad row means the whole batch is wrong (a broken file, a key that must
    never be null in finance data). Drop when the row has no value and nobody will fix it. Quarantine when the row is
    real business data with a fixable problem, which is most of the time for orders and customers. Whatever you choose,
    count the bad rows and alert on the count.

## 7.8 Gold: models, aggregates and the cost of freshness

*Level: intermediate.*

### Dimensional models

The docs say gold is "where you'll model your data for reporting and analytics using a dimensional model by
establishing relationships and defining measures". A **dimensional model** splits data into **facts** (events with
measures: an order line with quantity and amount) and **dimensions** (the context: customer, product, date). A star
schema is one fact table joined to dimension tables. Databricks' data modeling page says star and snowflake schemas
"perform well on Databricks, as there are fewer joins present in standard queries and fewer keys to keep in sync",
and Databricks "recommends against using a heavily normalized model such as third normal form (3NF)" for a new
lakehouse. The same page notes that primary and foreign keys "are informational and not enforced", so the pipeline,
not the database, keeps them correct. Chapter 10 builds the Red Rock Supply star schema.

### Aggregates and materialized views

Many gold tables are pre-aggregated: daily sales, revenue per customer, weekly bookings. The docs' example is a
materialized view, so that analysts "don't need to recreate frequently used" aggregates. A **materialized view** is a
Unity Catalog managed table that stores the result of its query and is refreshed as sources change, incrementally
when the query and sources allow it, otherwise by a full refresh. Created from a Databricks SQL warehouse, it is
maintained by an automatically created serverless pipeline.

*Databricks only, not run here. Syntax from [What is the medallion lakehouse architecture?](https://docs.databricks.com/aws/en/lakehouse/medallion) and [Use standalone materialized views](https://docs.databricks.com/aws/en/sql/mv-st/materialized).*

```sql
CREATE OR REPLACE MATERIALIZED VIEW shop_prod.gold.daily_sales AS
SELECT to_date(order_ts) AS order_date,
       currency,
       count(*)    AS orders,
       sum(amount) AS revenue
FROM shop_prod.silver.orders
WHERE status <> 'CANCELLED'
GROUP BY ALL;
```

### Which construct for which layer

A Databricks page, "When to use REPLACE WHERE vs. materialized views", maps constructs to medallion layers. This
table copies it:

| Layer | Construct Databricks recommends | Why (from the page) |
| --- | --- | --- |
| Bronze (raw ingestion) | Lakeflow Connect or Auto Loader | Lands raw records incrementally, without reprocessing history |
| Silver (facts) | Incremental `REPLACE WHERE` flow | Overwrites only the affected time windows or partitions for fact updates, late data and corrections |
| Silver (dimensions) | `AUTO CDC` flow | Applies inserts, updates and deletes, with SCD Type 1 or Type 2 |
| Gold (aggregations and data models) | Incremental `REPLACE WHERE` flow | Recomputes only the predicate range, avoiding full-table recomputes |
| Query acceleration and serving | Materialized view | Serves precomputed results to dashboards and keeps them current |

The idea behind `REPLACE WHERE`: for data that changes in bounded ranges (a day, a week), delete and recompute only
that range. The cost of each refresh "depends on the size of the range, not the size of the table". The plain Delta
statement `INSERT INTO ... REPLACE WHERE` does the same thing by hand, and the worked example uses it to restate a
day after a late correction.

### Cost vs latency

Fresher data costs more. The medallion page lists three ingestion frequencies:

| Ingestion frequency | Cost | Latency | Typical setup (from the page) |
| --- | --- | --- | --- |
| Continuous incremental | Higher | Lower | A streaming table or Structured Streaming notebook reading with `spark.readStream`, running continuously (a continuous pipeline, or a job with a continuous trigger) |
| Triggered incremental | Lower | Higher | The same streaming code, started by a scheduled or file arrival trigger; in a notebook, an `AvailableNow` trigger (the page writes `Trigger.Available`) |
| Batch with manual incremental logic | Lower | Highest, because runs are infrequent | `spark.read` with your own incremental logic, for example overwriting a whole partition by a `datetime` field; needs extensive upstream setup |

Most medallion pipelines are triggered incremental: the code is streaming code, but it runs on a schedule with
`AvailableNow` and stops, so you get incremental processing without paying for a cluster that runs all day. The
triggers page warns that leaving the trigger unset (the default, a `processingTime` of 0) checks for new data
constantly and "can generate a high volume of cloud storage API calls per day". Different layers can run at different
speeds: bronze every few minutes, gold once an hour for a dashboard nobody opens at night.

!!! tip "In the interview"
    **"Materialized view or table for gold?"** A materialized view when it is a query over silver that dashboards hit
    often: Databricks keeps it current, incrementally where possible. A table maintained by a `REPLACE WHERE` flow (or
    `MERGE`) when the refresh must be predictable and bounded, for example recomputing only the last seven days, or
    when I need exact control over corrections. Databricks' own mapping uses `REPLACE WHERE` for gold aggregates and
    materialized views for serving.

## 7.9 Idempotent loads: why every hop must survive a rerun

*Level: expert.*

A load is **idempotent** when running it twice on the same input leaves the same result as running it once. It
matters because reruns are normal: a job fails halfway and is retried, an orchestrator repairs a run, someone reruns
yesterday by hand, a stream replays a batch. The foreachBatch page states that `foreachBatch()` "provides only
at-least-once write guarantees", so the same micro-batch can be written twice. If the write is not idempotent, every
retry adds duplicates.

The tools, layer by layer:

| Layer | Idempotency comes from |
| --- | --- |
| Bronze | The ingestion checkpoint: Auto Loader (or a Structured Streaming file source) remembers which files it has read; `COPY INTO` also skips files it already loaded (chapter 8) |
| Silver | `MERGE` on the business key, with a deduplicated source and a "newer wins" guard; or Delta's `txnAppId` and `txnVersion` write options bound to the batch ID, which the foreachBatch page says Delta uses to skip a replayed batch |
| Gold | Recompute and replace a range (`REPLACE WHERE`, a partition overwrite) or the whole table (`CREATE OR REPLACE`, a materialized view) instead of appending totals |

### A plain append is not rerun safe

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
sql("CREATE TABLE silver_append (order_id INT, amount DECIMAL(10,2)) USING DELTA")
for run in (1, 2):
    sql("""INSERT INTO silver_append
           SELECT order_id, amount FROM VALUES (1001, 59.90), (1002, 120.00) AS v(order_id, amount)""")
    print(f"after run {run}:")
    show("SELECT order_id, count(*) AS copies FROM silver_append GROUP BY ALL ORDER BY ALL")
```

```text
after run 1:
+--------+------+
|order_id|copies|
+--------+------+
|1001    |1     |
|1002    |1     |
+--------+------+

after run 2:
+--------+------+
|order_id|copies|
+--------+------+
|1001    |2     |
|1002    |2     |
+--------+------+
```

### MERGE needs a deduplicated source: two failure modes

`MERGE` matches source rows to target rows on a key (generic `MERGE` is in the
[SQL course](../../databases/sql/17-Insert-Update-Delete-Merge.md)). If the source has two rows for one key, two
different things happen depending on whether the key already exists in the target. Here is a batch where the source
re-sent order 1002:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver_orders (order_id INT, amount DECIMAL(10,2), updated_at TIMESTAMP) USING DELTA;

CREATE OR REPLACE TEMP VIEW batch_with_dup AS
SELECT * FROM VALUES
  (1002, 120.00, TIMESTAMP'2026-03-01 11:02:00'),
  (1002, 120.00, TIMESTAMP'2026-03-01 11:02:00'),
  (1004,  35.50, TIMESTAMP'2026-03-01 16:20:00')
AS v(order_id, amount, updated_at);

-- 3a: the target is empty
MERGE INTO silver_orders t USING batch_with_dup s ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *;

SELECT order_id, count(*) AS copies FROM silver_orders GROUP BY ALL ORDER BY ALL;
```

```text
+--------+------+
|order_id|copies|
+--------+------+
|1002    |2     |
|1004    |1     |
+--------+------+
```

No error: neither copy of 1002 matched anything, so both were inserted, exactly as the Delta merge page warns. Next,
with one 1002 already in the target, the same `MERGE` runs again:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
MERGE INTO silver_orders t USING batch_with_dup s ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *;
```

```text
ERROR: [DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE] Cannot perform Merge as multiple source rows matched and attempted to modify the same
```

The `MERGE INTO` reference explains: the operation fails "if more than one row in the source table matches the same
row in the target table", because "it is unclear which source row should be used to update the matched target row".
(Databricks allows multiple matches only when the matched rows are unconditionally deleted.) The fix is to
deduplicate the source first, then merge with a newer-wins guard. Run twice, it leaves one row per order:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
MERGE INTO silver_orders t
USING (SELECT * FROM batch_with_dup
       QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY updated_at DESC) = 1) s
ON t.order_id = s.order_id
WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
-- run a second time, then:
SELECT order_id, count(*) AS copies FROM silver_orders GROUP BY ALL ORDER BY ALL;
```

```text
+--------+------+
|order_id|copies|
+--------+------+
|1002    |1     |
|1004    |1     |
+--------+------+
```

(Before this step the script reset 1002 to one copy; see `traps_demo.py`.) The SQL course chapter on
[duplicates and incremental loads](../../databases/sql/22-Duplicates-and-Incremental-Loads.md) covers the generic
patterns.

!!! warning "Three ways a MERGE stops being idempotent"
    1. **No dedup of the source:** duplicates inserted into an empty target, or the multiple-match error later.
    2. **No newer-wins guard:** `WHEN MATCHED THEN UPDATE SET *` lets a late, older version overwrite a newer one.
    3. **Non-deterministic values in the update:** setting `loaded_at = current_timestamp()` on every match makes
       every rerun "update" every row. Carry the bronze ingest time through instead, or update only when the business
       columns changed.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 290" role="img" aria-label="A bronze batch passes rules, deduplication and a MERGE into silver. A table of three commits shows a replay of the same input inserting zero rows and updating zero rows." font-family="sans-serif" font-size="13" fill="currentColor">
<defs><marker id="m74" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<rect x="13" y="20" width="105" height="80" rx="6" fill="none" stroke="currentColor"/>
<text x="65" y="42" text-anchor="middle" font-weight="bold">bronze batch</text>
<text x="65" y="64" text-anchor="middle">5 raw rows</text>
<text x="65" y="84" text-anchor="middle">1002 twice</text>
<rect x="140" y="20" width="105" height="80" rx="6" fill="none" stroke="currentColor"/>
<text x="192" y="42" text-anchor="middle" font-weight="bold">rules</text>
<text x="192" y="64" text-anchor="middle">1003 fails</text>
<text x="192" y="84" text-anchor="middle">to quarantine</text>
<rect x="267" y="20" width="105" height="80" rx="6" fill="none" stroke="currentColor"/>
<text x="319" y="42" text-anchor="middle" font-weight="bold">dedup</text>
<text x="319" y="64" text-anchor="middle">latest row</text>
<text x="319" y="84" text-anchor="middle">per order_id</text>
<rect x="394" y="20" width="105" height="80" rx="6" fill="none" stroke="currentColor"/>
<text x="446" y="42" text-anchor="middle" font-weight="bold">MERGE</text>
<text x="446" y="64" text-anchor="middle">ON order_id</text>
<text x="446" y="84" text-anchor="middle">newer wins</text>
<rect x="521" y="20" width="105" height="80" rx="6" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="573" y="42" text-anchor="middle" font-weight="bold">silver</text>
<text x="573" y="64" text-anchor="middle">one row</text>
<text x="573" y="84" text-anchor="middle">per order</text>
<line x1="119" y1="60" x2="138" y2="60" stroke="currentColor" marker-end="url(#m74)"/>
<line x1="246" y1="60" x2="265" y2="60" stroke="currentColor" marker-end="url(#m74)"/>
<line x1="373" y1="60" x2="392" y2="60" stroke="currentColor" marker-end="url(#m74)"/>
<line x1="500" y1="60" x2="519" y2="60" stroke="currentColor" marker-end="url(#m74)"/>
<text x="20" y="150" font-weight="bold">commit</text>
<text x="90" y="150" font-weight="bold">what ran</text>
<text x="350" y="150" font-weight="bold">source rows</text>
<text x="460" y="150" font-weight="bold">inserted</text>
<text x="550" y="150" font-weight="bold">updated</text>
<line x1="15" y1="158" x2="625" y2="158" stroke="currentColor"/>
<text x="20" y="180">v1</text>
<text x="90" y="180">run 1: day 1 files</text>
<text x="350" y="180">3</text>
<text x="460" y="180">3</text>
<text x="550" y="180">0</text>
<text x="20" y="205">v2</text>
<text x="90" y="205">replay all of bronze (same input)</text>
<text x="350" y="205">3</text>
<text x="460" y="205" font-weight="bold">0</text>
<text x="550" y="205" font-weight="bold">0</text>
<text x="20" y="230">v3</text>
<text x="90" y="230">run 2: day 2 file</text>
<text x="350" y="230">2</text>
<text x="460" y="230">1</text>
<text x="550" y="230">1</text>
<text x="320" y="272" text-anchor="middle">Replaying the same input changes nothing: the silver MERGE is idempotent.</text>
</svg>
<figcaption>Figure 7.4. The silver step of the worked example, and the commit history it produced (real numbers from section 7.10). The replay in v2 inserted and updated nothing.</figcaption>
</figure>

!!! tip "In the interview"
    **"How do you make a pipeline safe to rerun?"** Bronze: let the ingestion checkpoint (Auto Loader) track files.
    Silver: deduplicate each batch to one row per key, then `MERGE` on the key with a sequence guard, so a replay
    inserts and updates nothing. Gold: recompute and replace a bounded range instead of appending. Then I prove it by
    rerunning and checking the Delta history's operation metrics: zero rows inserted and updated.

## 7.10 Worked example: Red Rock Supply, end to end

*Level: expert.*

This example runs the whole flow on the local Spark 4.2 + Delta 4.4.1 engine. The full script is
`src/ch07/medallion_demo.py` and its output is `medallion_demo.out`. Local differences from Databricks:

- There is no Unity Catalog, so `shop_prod.bronze.orders` becomes `bronze.orders` (schemas `bronze`, `silver`,
  `gold` in the local catalog).
- There is no Auto Loader, so bronze uses the open-source Structured Streaming file source with a checkpoint, which
  also tracks which files it has read. On Databricks you would use `cloudFiles` as in 7.5.
- The streaming write says `.format("delta")` because open-source Spark's default table format is Parquet; on
  Databricks, managed tables use Delta Lake by default.

### The landing files

Three JSON-lines files arrive. They contain one duplicate, one bad record and one late correction:

| File | Rows |
| --- | --- |
| `orders_20260301_0900.json` | 1001 (59.90), 1002 (120.00), **1003 with `"amount": "12.O0"`** (bad) |
| `orders_20260301_1800.json` | **1002 again** (the source re-sent it), 1004 (35.50) |
| `orders_20260302_0900.json` (arrives on day 2) | **1001 corrected to 49.90**, `updated_at` 2026-03-02 08:30, still placed on March 1; 1005 (89.00); both rows carry a **new field, `channel`** |

Each event has the shape of the shared dataset plus an `updated_at` timestamp, which orders versions of the same
order:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```json
{"order_id": 1001, "customer_id": 7, "order_ts": "2026-03-01T10:15:00Z", "status": "PLACED", "amount": "59.90", "currency": "CAD", "updated_at": "2026-03-01T10:15:00Z", "items": [{"product_id": 3, "qty": 2, "unit_price": "29.95"}]}
```

### Bronze: raw line plus ingest metadata

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
sql("""
CREATE TABLE bronze.orders (
  raw                  STRING     COMMENT 'the JSON line exactly as received',
  _source_file         STRING,
  _file_modified_at    TIMESTAMP,
  _ingested_at         TIMESTAMP
) USING DELTA
""")

def load_bronze():
    from pyspark.sql import functions as F
    q = (spark.readStream.format("text").load(LANDING)
         .select(F.col("value").alias("raw"),
                 F.col("_metadata.file_name").alias("_source_file"),
                 F.col("_metadata.file_modification_time").alias("_file_modified_at"),
                 F.current_timestamp().alias("_ingested_at"))
         .writeStream
         .format("delta")   # open-source Spark defaults to parquet; Databricks defaults to Delta
         .option("checkpointLocation", os.path.join(CHK, "bronze_orders"))
         .trigger(availableNow=True)
         .toTable("bronze.orders"))
    q.awaitTermination()
```

After the two day-1 files land and `load_bronze()` runs:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> SELECT _source_file, count(*) AS rows FROM bronze.orders GROUP BY ALL ORDER BY ALL
+-------------------------+----+
|_source_file             |rows|
+-------------------------+----+
|orders_20260301_0900.json|3   |
|orders_20260301_1800.json|2   |
+-------------------------+----+

>>> SELECT substr(raw, 1, 60) AS raw_start, _source_file FROM bronze.orders ORDER BY _source_file, raw
+------------------------------------------------------------+-------------------------+
|raw_start                                                   |_source_file             |
+------------------------------------------------------------+-------------------------+
|{"order_id": 1001, "customer_id": 7, "order_ts": "2026-03-01|orders_20260301_0900.json|
|{"order_id": 1002, "customer_id": 12, "order_ts": "2026-03-0|orders_20260301_0900.json|
|{"order_id": 1003, "customer_id": 7, "order_ts": "2026-03-01|orders_20260301_0900.json|
|{"order_id": 1002, "customer_id": 12, "order_ts": "2026-03-0|orders_20260301_1800.json|
|{"order_id": 1004, "customer_id": 3, "order_ts": "2026-03-01|orders_20260301_1800.json|
+------------------------------------------------------------+-------------------------+
```

All five lines are there, including the duplicate and the bad record. Bronze judged nothing.

### Silver: parse, type, check, quarantine, deduplicate, MERGE

Silver has a strict schema (`NOT NULL` on the key columns) and a quarantine table beside it:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.orders (
  order_id      INT            NOT NULL,
  customer_id   INT            NOT NULL,
  order_ts      TIMESTAMP      NOT NULL,
  order_date    DATE           NOT NULL,
  status        STRING,
  amount        DECIMAL(10,2)  NOT NULL,
  currency      STRING,
  updated_at    TIMESTAMP      NOT NULL,
  _source_file  STRING,
  _ingested_at  TIMESTAMP
) USING DELTA;

CREATE TABLE silver.orders_quarantine (
  raw           STRING,
  failed_rules  ARRAY<STRING>,
  _source_file  STRING,
  _ingested_at  TIMESTAMP
) USING DELTA;
```

One view parses the JSON with an explicit schema (all strings, as in bronze), types each field with `try_cast` so a
bad value becomes `NULL` instead of failing the job, and lists the rules each row breaks. The `filter` higher-order
function keeps only the non-null rule names (chapter 18):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE OR REPLACE TEMP VIEW {out} AS
WITH parsed AS (
  SELECT raw, _source_file, _ingested_at,
         from_json(raw, 'order_id STRING, customer_id STRING, order_ts STRING, status STRING,
                         amount STRING, currency STRING, updated_at STRING') AS j
  FROM {src}
),
typed AS (
  SELECT raw, _source_file, _ingested_at,
         try_cast(j.order_id    AS INT)            AS order_id,
         try_cast(j.customer_id AS INT)            AS customer_id,
         try_cast(j.order_ts    AS TIMESTAMP)      AS order_ts,
         upper(j.status)                           AS status,
         try_cast(j.amount      AS DECIMAL(10,2))  AS amount,
         upper(j.currency)                         AS currency,
         try_cast(j.updated_at  AS TIMESTAMP)      AS updated_at
  FROM parsed
)
SELECT *,
       filter(array(
         CASE WHEN order_id    IS NULL THEN 'order_id_missing_or_not_int' END,
         CASE WHEN customer_id IS NULL THEN 'customer_id_missing' END,
         CASE WHEN order_ts    IS NULL THEN 'order_ts_not_a_timestamp' END,
         CASE WHEN amount IS NULL OR amount < 0 THEN 'amount_invalid' END,
         CASE WHEN currency NOT IN ('CAD', 'USD') OR currency IS NULL THEN 'currency_invalid' END,
         CASE WHEN updated_at  IS NULL THEN 'updated_at_missing' END
       ), x -> x IS NOT NULL) AS failed_rules
FROM typed
```

(`{src}` and `{out}` are filled in by Python.) The silver step is a `foreachBatch` function over a streaming read of
bronze. Each of its three writes is safe to repeat:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
def upsert_silver(batch_df, batch_id):
    """foreachBatch function: safe to run twice on the same input."""
    s = batch_df.sparkSession
    batch_df.createOrReplaceTempView("bronze_batch")
    s.sql(PARSE_AND_CHECK.format(src="bronze_batch", out="checked"))

    # 1. bad rows to quarantine (MERGE on the raw text + file, so a replay does not add them twice)
    s.sql("""
      MERGE INTO silver.orders_quarantine q
      USING (SELECT DISTINCT raw, failed_rules, _source_file, _ingested_at
             FROM checked WHERE size(failed_rules) > 0) b
      ON q.raw = b.raw AND q._source_file = b._source_file
      WHEN NOT MATCHED THEN INSERT *
    """)

    # 2. good rows: keep only the latest version of each order inside this batch
    s.sql("""
      CREATE OR REPLACE TEMP VIEW latest AS
      SELECT order_id, customer_id, order_ts, to_date(order_ts) AS order_date, status, amount,
             currency, updated_at, _source_file, _ingested_at
      FROM checked
      WHERE size(failed_rules) = 0
      QUALIFY row_number() OVER (PARTITION BY order_id
                                 ORDER BY updated_at DESC, _ingested_at DESC, _source_file DESC) = 1
    """)

    # 3. upsert: insert new orders, update only when the incoming version is newer
    s.sql("""
      MERGE INTO silver.orders t
      USING latest s
      ON t.order_id = s.order_id
      WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
      WHEN NOT MATCHED THEN INSERT *
    """)


def load_silver():
    q = (spark.readStream.table("bronze.orders")
         .writeStream
         .foreachBatch(upsert_silver)
         .option("checkpointLocation", os.path.join(CHK, "silver_orders"))
         .trigger(availableNow=True)
         .start())
    q.awaitTermination()
```

After `load_silver()`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> SELECT order_id, customer_id, order_ts, status, amount, updated_at, _source_file FROM silver.orders ORDER BY order_id
+--------+-----------+-------------------+------+------+-------------------+-------------------------+
|order_id|customer_id|order_ts           |status|amount|updated_at         |_source_file             |
+--------+-----------+-------------------+------+------+-------------------+-------------------------+
|1001    |7          |2026-03-01 10:15:00|PLACED|59.90 |2026-03-01 10:15:00|orders_20260301_0900.json|
|1002    |12         |2026-03-01 11:02:00|PLACED|120.00|2026-03-01 11:02:00|orders_20260301_1800.json|
|1004    |3          |2026-03-01 16:20:00|PLACED|35.50 |2026-03-01 16:20:00|orders_20260301_1800.json|
+--------+-----------+-------------------+------+------+-------------------+-------------------------+

>>> SELECT get_json_object(raw, '$.order_id') AS order_id, get_json_object(raw, '$.amount') AS amount, failed_rules, _source_file FROM silver.orders_quarantine
+--------+------+----------------+-------------------------+
|order_id|amount|failed_rules    |_source_file             |
+--------+------+----------------+-------------------------+
|1003    |12.O0 |[amount_invalid]|orders_20260301_0900.json|
+--------+------+----------------+-------------------------+
```

Five bronze rows became three silver rows and one quarantined row: 1002 appears once (the tie on `updated_at` was
broken by the file name, so the evening copy won), and 1003 waits in quarantine with its original text and the
reason.

### Gold: daily sales with REPLACE WHERE

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
sql("""
CREATE TABLE gold.daily_sales (
  order_date  DATE,
  currency    STRING,
  orders      BIGINT,
  revenue     DECIMAL(20,2)
) USING DELTA
""")


def refresh_gold(from_date):
    """Recompute only the days that can have changed, and replace exactly those days."""
    sql(f"""
      INSERT INTO gold.daily_sales
      REPLACE WHERE order_date >= DATE'{from_date}'
      SELECT order_date, currency, count(*) AS orders, sum(amount) AS revenue
      FROM silver.orders
      WHERE order_date >= DATE'{from_date}' AND status <> 'CANCELLED'
      GROUP BY ALL
    """)
```

```text
>>> SELECT * FROM gold.daily_sales ORDER BY ALL
+----------+--------+------+-------+
|order_date|currency|orders|revenue|
+----------+--------+------+-------+
|2026-03-01|CAD     |3     |215.40 |
+----------+--------+------+-------+
```

`INSERT INTO ... REPLACE WHERE` deletes the rows that match the predicate and inserts the query result in one atomic
commit, so a rerun replaces the day instead of adding it twice. Here the date is fixed for clarity; a real job would
compute the earliest `order_date` among the silver rows changed since the last run.

### Rerun with nothing new

All three steps run again with no new files:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> SELECT count(*) AS bronze_rows FROM bronze.orders
+-----------+
|bronze_rows|
+-----------+
|5          |
+-----------+

>>> SELECT count(*) AS silver_rows FROM silver.orders
+-----------+
|silver_rows|
+-----------+
|3          |
+-----------+

>>> SELECT * FROM gold.daily_sales ORDER BY ALL
+----------+--------+------+-------+
|order_date|currency|orders|revenue|
+----------+--------+------+-------+
|2026-03-01|CAD     |3     |215.40 |
+----------+--------+------+-------+
```

Nothing changed. Bronze read no files (the checkpoint knew them). Silver did not even call the `foreachBatch`
function: a separate test in `traps_demo.py` (section 6) shows that an `AvailableNow` stream with no new commits calls
`foreachBatch` zero times. Gold replaced March 1 with the same numbers.

### Replay: what if the checkpoint were lost?

Checkpoints protect you only while they exist. The real test of idempotency is to push all of bronze through the
silver logic again, as if the checkpoint had been deleted:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
upsert_silver(spark.table("bronze.orders"), -1)
```

```text
>>> SELECT count(*) AS silver_rows, sum(amount) AS total FROM silver.orders
+-----------+------+
|silver_rows|total |
+-----------+------+
|3          |215.40|
+-----------+------+

>>> SELECT count(*) AS quarantine_rows FROM silver.orders_quarantine
+---------------+
|quarantine_rows|
+---------------+
|1              |
+---------------+

>>> history of silver.orders
+-------+------------+-----------+--------+-------+
|version|operation   |source_rows|inserted|updated|
+-------+------------+-----------+--------+-------+
|0      |CREATE TABLE|NULL       |NULL    |NULL   |
|1      |MERGE       |3          |3       |0      |
|2      |MERGE       |3          |0       |0      |
+-------+------------+-----------+--------+-------+
```

Version 2 is the replay: three source rows, zero inserted, zero updated. The quarantine table still has one row. The
history line comes from `DESCRIBE HISTORY` and its `operationMetrics` map (`numSourceRows`,
`numTargetRowsInserted`, `numTargetRowsUpdated`), which is a quick way to prove idempotency in a test.

### Day 2: a late correction and a new column

The day-2 file lands and bronze loads it. Before silver runs, a drift check compares the keys in bronze with the keys
silver knows about:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT k AS unexpected_key, count(*) AS rows, min(_source_file) AS first_seen_in
FROM (SELECT explode(json_object_keys(raw)) AS k, _source_file FROM bronze.orders)
WHERE k NOT IN ('order_id','customer_id','order_ts','status','amount','currency','updated_at','items')
GROUP BY k
```

```text
+--------------+----+-------------------------+
|unexpected_key|rows|first_seen_in            |
+--------------+----+-------------------------+
|channel       |2   |orders_20260302_0900.json|
+--------------+----+-------------------------+
```

Bronze kept `channel` inside the raw line, silver will ignore it (its `from_json` schema does not list it), and the
check tells the team a decision is needed. Then silver runs:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> SELECT order_id, order_date, amount, updated_at, _source_file FROM silver.orders ORDER BY order_id
+--------+----------+------+-------------------+-------------------------+
|order_id|order_date|amount|updated_at         |_source_file             |
+--------+----------+------+-------------------+-------------------------+
|1001    |2026-03-01|49.90 |2026-03-02 08:30:00|orders_20260302_0900.json|
|1002    |2026-03-01|120.00|2026-03-01 11:02:00|orders_20260301_1800.json|
|1004    |2026-03-01|35.50 |2026-03-01 16:20:00|orders_20260301_1800.json|
|1005    |2026-03-02|89.00 |2026-03-02 09:05:00|orders_20260302_0900.json|
+--------+----------+------+-------------------+-------------------------+

>>> history of silver.orders
+-------+------------+-----------+--------+-------+
|version|operation   |source_rows|inserted|updated|
+-------+------------+-----------+--------+-------+
|0      |CREATE TABLE|NULL       |NULL    |NULL   |
|1      |MERGE       |3          |3       |0      |
|2      |MERGE       |3          |0       |0      |
|3      |MERGE       |2          |1       |1      |
+-------+------------+-----------+--------+-------+
```

Order 1001 was updated in place (its newer `updated_at` passed the guard), 1005 was inserted, and 1001 kept its
`order_date` of March 1. That last point is why a late correction changes a past day in gold.

### Restating March 1 in gold

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
refresh_gold("2026-03-01")
```

```text
>>> SELECT 'before' AS v, * FROM gold.daily_sales ORDER BY ALL
+------+----------+--------+------+-------+
|v     |order_date|currency|orders|revenue|
+------+----------+--------+------+-------+
|before|2026-03-01|CAD     |3     |215.40 |
+------+----------+--------+------+-------+

>>> SELECT 'after' AS v, * FROM gold.daily_sales ORDER BY ALL
+-----+----------+--------+------+-------+
|v    |order_date|currency|orders|revenue|
+-----+----------+--------+------+-------+
|after|2026-03-01|CAD     |3     |205.40 |
|after|2026-03-02|CAD     |1     |89.00  |
+-----+----------+--------+------+-------+

>>> history of gold.daily_sales
+-------+------------+---------------------------------+
|version|operation   |predicate                        |
+-------+------------+---------------------------------+
|0      |CREATE TABLE|NULL                             |
|1      |WRITE       |(order_date >= DATE '2026-03-01')|
|2      |WRITE       |(order_date >= DATE '2026-03-01')|
|3      |WRITE       |(order_date >= DATE '2026-03-01')|
+-------+------------+---------------------------------+

>>> SELECT * FROM gold.daily_sales VERSION AS OF 1 ORDER BY ALL
+----------+--------+------+-------+
|order_date|currency|orders|revenue|
+----------+--------+------+-------+
|2026-03-01|CAD     |3     |215.40 |
+----------+--------+------+-------+
```

March 1 revenue was restated from 215.40 to 205.40 (59.90 replaced by 49.90), and March 2 appeared. Delta time travel
still shows what the dashboard said before (version 1), which answers the auditor's "what did we report on March 1?"
as long as the old version has not been removed by `VACUUM` (chapter 4). If you must reproduce past reports long
term, that is the case for a bitemporal design or an explicit snapshot table, not for time travel.

## 7.11 Anti-patterns, and when three layers do not fit

*Level: expert.*

### Anti-patterns

- **Cleaning in bronze.** Casting, filtering or deduplicating on the way in. Lost values cannot be recovered, and
  replay is impossible. Bronze keeps raw data plus metadata; rules belong in silver.
- **Ingesting straight into silver.** The docs warn this introduces "failures due to schema changes or corrupt records
  in data sources". Without bronze, a schema change stops the pipeline and there is nothing to replay from.
- **Plain appends into silver.** Every retry creates duplicates (section 7.9). Use `MERGE` with a deduplicated source.
- **Trusting arrival order.** Updating with whatever arrived last lets an old event overwrite a new one. Use a
  sequence column.
- **Streaming from a table that is updated.** A stream from a silver table that `MERGE` modifies fails. Use the change
  data feed, `skipChangeCommits` with care, a materialized view, or a batch `REPLACE WHERE`.
- **Gold copies everywhere.** Each team copies gold into its own tables and adds its own logic. The "Guiding
  principles" page warns that copies that "become operational with downstream business data products dependent on
  them... become data silos", which drift out of sync. Share one governed table (grants, views, OpenSharing,
  formerly Delta Sharing, for partners) instead of copying it.
- **Too many layers.** `bronze`, `bronze_clean`, `silver_stage`, `silver_1`, `silver_2`, `gold_pre`, `gold`. Each hop
  adds latency, storage, cost and a place for bugs. Add a layer only when it has its own consumers or its own
  guarantee.
- **Silver as a copy of bronze.** One silver table per bronze table with only renamed columns. Silver should be
  modeled around business entities (the docs' `customer_transactions` joins two sources).
- **Analysts in bronze.** If people build reports on bronze, the layers exist on paper only. Grant per layer.
- **No quality metrics.** Rules that silently drop rows. Count dropped and quarantined rows and alert on them.

### When the three-layer model does not fit

The medallion architecture is "a recommended best practice but not a requirement". Cases where a strict three-layer
build is the wrong call:

- **Small data, small team.** A few thousand rows a day from one system: one raw table and one view or materialized
  view may be enough. You can keep the idea (raw kept, clean derived) without three sets of jobs.
- **A single source that is already clean.** A well-modeled table from an operational database, received through
  CDC, may need only bronze (the change feed) and one silver table built by `AUTO CDC`; a separate gold may just be a
  view.
- **Real-time serving.** When an application needs a decision in milliseconds (fraud scoring, for example), writing
  through three Delta tables adds latency at every hop. The triggers page describes a real-time mode for Structured
  Streaming that targets sub-second end-to-end latency; such paths usually process events directly, and land them in
  bronze in parallel for history and analytics.
- **Exploration and one-off analysis.** A data scientist testing an idea does not need a production medallion
  pipeline. Promote it when it becomes a product.
- **Data that is already a gold-level product.** A partner shares a curated table through OpenSharing: you can query
  it directly rather than copy it into bronze.

!!! tip "In the interview"
    **"When would you not use the medallion architecture?"** When the layers cost more than they give: tiny data from
    one clean source, a millisecond real-time path, or a one-off analysis. Even then I keep the core idea: land raw
    data unchanged so I can replay, and derive clean data from it. The number of layers should follow the guarantees
    and the consumers, not a template; Databricks itself calls the pattern a best practice, not a requirement.

## 7.12 Other names and related approaches

*Level: expert.*

### The same idea under other names

Interviewers and job ads use several vocabularies for layered pipelines. Know which words are Databricks' and which
are general field terms.

| Term | Whose term | What it usually means |
| --- | --- | --- |
| Medallion; bronze, silver, gold | Databricks documentation | The three layers described in this chapter |
| Multi-hop architecture | Databricks documentation (the medallion page, and "layered (or multi-hop) architecture" on the "Guiding principles" page); also used widely in the field | The same layered design: data hops from one quality level to the next |
| Ingest, curated, final layer | Databricks "Guiding principles" page | An ingest layer from which "rebuilding the subsequent layers ... is possible", a curated layer of cleansed data that is "a sound, reliable foundation", and a final layer of data products built around business or project needs |
| Raw, staging, curated (also raw/refined/serving, raw/curated/consumption) | Common field terms, not Databricks terms | Roughly bronze, silver, gold. Check what a team means by "staging": in many warehouse teams it is a temporary area emptied on every load, which is not the same as an append-only bronze that keeps all history |
| Landing zone, raw zone | Common field terms, not Databricks medallion layers | The storage location (often a Unity Catalog volume) where source systems drop files before ingestion. The UC best practices page mentions external volumes for "landing areas for raw data produced by external systems". In this book the landing folder is the input to bronze, not a layer |
| Platinum (or diamond) | Field term, not on the Databricks medallion page | An extra layer above gold for very specific products: ML feature tables, partner extracts, executive summaries. Many teams simply call these gold |

### Kimball star schemas

The medallion architecture says how data moves from raw to refined; it does not say how to model the tables.
Ralph Kimball's dimensional modeling answers that question for analytics: **fact tables** at a declared grain (one
row per order line, for example), **dimension tables** for context, **conformed dimensions** shared by several fact
tables (one `dim_customer` used by orders and returns), and slowly changing dimensions, whose Type 1 and Type 2 come
from this tradition. The two fit together: **gold is often a Kimball star schema**, built from silver. The Databricks
medallion page says gold is where you "model your data for reporting and analytics using a dimensional model", and
the data modeling page says star and snowflake schemas perform well on Databricks. Chapter 10 builds one; the generic
theory is in the [SQL course](../../databases/sql/19-Data-Modelling.md).

### Data Vault

Data Vault, created by Dan Linstedt, is a modeling method for the integration layer. It splits data into **hubs**
(one row per business key, such as a customer number), **links** (relationships between hubs, such as customer to
order) and **satellites** (descriptive attributes with their history, insert-only). Some teams use it as their silver
layer: bronze lands raw data, a "raw vault" in silver integrates the sources by business key while keeping full
history, and gold publishes Kimball star schemas built from the vault. Its strengths are auditability and adding new
sources without remodeling existing tables. Its cost is many more tables and joins; the Databricks data modeling page
warns that joins "can introduce processing bottlenecks" and recommends against heavily normalized models for new
lakehouses, which is why query-facing gold stays dimensional even when silver is a vault. None of the Databricks pages
used for this chapter discusses Data Vault, so treat this as field practice: a choice for large, many-source
integration problems, not a default.

### Data mesh

Data mesh, described by Zhamak Dehghani, is an organizational approach rather than a pipeline pattern: domain teams
(sales, finance, logistics) own their data **as products**, on a shared self-service platform, under federated
governance. Medallion fits inside it: each domain runs its own bronze, silver and gold and publishes its gold (and
sometimes silver) tables as data products for other domains. Databricks pages support the pieces without using the
term: the medallion page notes that "some customers create multiple gold layers to meet different business needs,
such as HR, finance, and IT"; the "Guiding principles" page describes "data as a product" offered by one business unit
"and consumed by other parties with proper permission control" in a self-service way; the UC best practices page says
catalogs often correspond to a team or business unit. In Unity Catalog that becomes a catalog per domain (per
environment), grants for other domains, and OpenSharing (formerly Delta Sharing) for partners outside the company.

!!! tip "In the interview"
    **"Is medallion an alternative to a star schema?"** No, they answer different questions. Medallion organizes data
    by quality (raw, validated, business-ready); Kimball says how to model analytical tables. Gold is often a Kimball
    star schema built from silver. Data Vault, if used, usually sits in silver as the integration layer, and data mesh
    decides who owns each domain's layers.

## 7.13 The questions interviewers push on

*Level: expert.*

These are the follow-up questions that separate "I know the diagram" from "I have run this". Each answer points back
to the section with the detail; each is also a practice question.

### Where does deduplication belong?

In **silver**. The docs list deduplication among silver's operations ("Is where you perform data cleansing,
deduplication, and normalization"). Bronze keeps duplicates on purpose: they are evidence of how the source behaves,
and a deduplication rule applied at bronze can never be undone. What bronze does prevent is loading the same *file*
twice, through the ingestion checkpoint; that is file-level idempotency, not record deduplication. In silver,
deduplicate twice: within each batch (latest version per key) and against the table (`MERGE` on the key). Gold should
not need to deduplicate; if it does, a silver rule is missing (7.6, 7.9).

### Where does business logic belong?

Split it by kind:

- **Silver:** technical and entity-level rules that every consumer needs: types, null handling, valid value checks,
  deduplication, conformed codes (one spelling of each country), and joins that build a business entity (the docs'
  `customer_transactions`). The docs: silver "enhances data quality by correcting errors and inconsistencies".
- **Gold:** business definitions and measures: what counts as revenue (net of cancellations? in which currency?),
  fiscal calendars, KPIs, customer segments. The docs: gold "aligns with business logic and requirements".

Define each business rule once, in one gold table or view, rather than in every dashboard. If two teams need
different definitions, give them two named, documented gold tables, not two private copies.

### How do you reprocess or backfill?

Reprocessing means running corrected logic over data already loaded; a backfill loads history (or a new column) that
was missing. Both depend on bronze holding the full history, which is the main reason bronze exists.

- **A bug in silver or gold logic:** fix the code, then rebuild silver from bronze, then gold from silver. Outside
  pipelines: run the silver logic over the affected bronze range in batch (the replay in 7.10 shows the mechanics),
  or build a new silver table from bronze with a new checkpoint and swap it in; then recompute the affected gold range
  with `REPLACE WHERE`. Watch the newer-wins guard: reprocessed rows carry the same `updated_at` as the rows already
  stored, so `WHEN MATCHED AND s.updated_at > t.updated_at` skips them. For a one-off reprocessing, update when the
  values differ, or rebuild the table.
- **In Lakeflow pipelines (formerly Delta Live Tables):** a *full refresh* of a streaming table "clears data from
  streaming tables, clears checkpoints from flows, and reprocesses all records from the data source"; a materialized
  view simply recomputes. The "Run a pipeline update" page warns that a full refresh "can result in dropped records if
  input data is no longer available", for example Kafka records past retention or files removed by a storage lifecycle
  policy. So refresh silver and gold (their source, bronze, still has everything), and protect bronze: the same page
  says the table property `pipelines.reset.allowed` set to `false` prevents full refreshes of a table.
- **A new column:** add it to silver deliberately, then fill history from bronze's raw records with a batch `MERGE`
  over bronze. With `VARIANT` or raw-string bronze, the value is already there.

### How do you make reruns safe?

Bronze: the ingestion checkpoint loads each file once. Silver: deduplicate the batch, `MERGE` on the key with a
newer-wins guard (or `txnAppId`/`txnVersion` in `foreachBatch`). Gold: replace a range or the whole result, never
append totals. Prove it by rerunning and reading the operation metrics in `DESCRIBE HISTORY` (7.9, 7.10).

### How do you handle schema drift?

Bronze absorbs it (strings or `VARIANT`, Auto Loader schema evolution, `_rescued_data`); silver enforces its schema
and changes only by decision, with per-write schema evolution and a backfill from bronze; gold changes only when a
measure needs it. Detect drift with a check, as the worked example did with `json_object_keys` (7.5, 7.6, 7.10).

### How do you handle late and out-of-order data?

Order versions by a source sequence or timestamp, never by arrival; in silver, keep the latest version per key and
update only when the incoming version is newer (`AUTO CDC ... SEQUENCE BY` in pipelines). Late facts keep their
original business date, so gold recomputes the affected dates (`REPLACE WHERE` or a materialized view refresh). If you
must also show what was reported before the correction, use time travel short term, or a bitemporal design (7.6,
7.10).

### How many layers is too many?

As many as there are distinct guarantees with their own consumers, and no more. Three is the default because there are
three guarantees: nothing lost (bronze), every row trusted (silver), business questions answered (gold). An extra
persisted layer is justified when it has its own readers or its own service level (for example a vault in silver, or a
partner extract above gold). A layer that nobody reads except the next job should usually be a temporary view inside
that job. Every hop adds latency, storage, compute and a place for bugs (7.11).

## 7.14 Practice questions

*Level: mixed.*

**Q1. In one sentence each, what are bronze, silver and gold?**

??? success "Answer"
    Bronze holds raw data exactly as ingested, appended incrementally, with metadata about its source. Silver holds
    cleaned, validated, deduplicated and typed records, at least one non-aggregated row per business record. Gold holds
    business-level data: dimensional models and aggregates for BI, ML and applications.

    **Why:** the official page names them bronze (raw), silver (validated) and gold (enriched), and assigns raw
    ingestion, cleaning and validation, and dimensional modeling and aggregation to them. The same page says the
    pattern is also called a multi-hop architecture.

**Q2. Where does deduplication belong, and why not in bronze or gold?**

??? success "Answer"
    In silver: deduplicate each batch to the latest version per key, then `MERGE` on the key against the table. Not in
    bronze, because bronze keeps the data as received (duplicates are evidence of source behavior, and a wrong rule
    there cannot be undone). Bronze only avoids loading the same file twice, through its checkpoint. Gold should not
    need it; duplicates in gold mean a silver rule is missing.

    **Why:** the medallion page lists deduplication among silver operations.

**Q3. Is the medallion architecture required on Databricks? Does any feature turn it on?**

??? success "Answer"
    No. The docs call it "a recommended best practice but not a requirement". It is a naming and design convention:
    you create the catalogs, schemas, tables and pipelines yourself. Nothing in the platform enforces it.

    **Why it matters:** an interviewer may test whether you think "bronze" is a product feature. It is not.

**Q4. Which users does Databricks list for the bronze layer, and who should not query it?**

??? success "Answer"
    Data engineers, data operations, and compliance and audit teams. Analysts and data scientists should not: the docs
    say bronze "is intended for consumption by workloads that enrich data for silver tables, not for access by analysts
    and data scientists".

    **Why:** bronze is unvalidated and may hold raw personal data; reports built on it inherit every data problem.

**Q5. Why does Databricks recommend storing most bronze fields as STRING, VARIANT or binary?**

??? success "Answer"
    To protect against unexpected schema changes and dropped data. A string accepts any value; a typed column turns a
    malformed value into `NULL` or an error, and the original is lost. Typing is done later, in silver, where a failed
    cast can be detected and quarantined.

    **Why:** section 7.5 shows `"12.O0"` becoming `NULL` under a typed read, while the string version kept it.

**Q6. Scenario: a colleague asks, "Why not clean the data in bronze and save a layer?" What do you answer?**

??? success "Answer"
    Cleaning encodes decisions that can be wrong or can change. If bronze is cleaned, a bad rule silently destroys data,
    and a new rule cannot be applied to history because the raw data is gone. With raw bronze, I fix the rule and
    replay silver from bronze. Bronze is also the audit record of what the source actually sent.

    **Why:** the docs describe bronze as the single source of truth that "enables reprocessing and auditing by retaining
    all historical data", with minimal validation.

**Q7. Which metadata columns would you add to a bronze table, and why?**

??? success "Answer"
    From the hidden `_metadata` column: `file_name` or `file_path`, and `file_modification_time`; plus your own load
    timestamp (`current_timestamp()`), and for Kafka the topic, partition and offset. They answer "where did this row
    come from and when did we load it", support debugging and audits, and give silver a tie-breaker when deduplicating.

    **Why:** the medallion page names `_metadata.file_name` as an example of provenance metadata; the file metadata page
    recommends selecting specific fields rather than the whole struct, since new fields may be added.

**Q8. What is `_rescued_data`, and when does a value land in it?**

??? success "Answer"
    A column Auto Loader adds when it infers the schema. It keeps data that does not fit the schema instead of dropping
    it: columns missing from the schema, type mismatches, and case mismatches. It holds a JSON blob with the rescued
    columns and the source file path of the record.

    **Why:** with it, type mismatches no longer cause `DROPMALFORMED` to drop records or `FAILFAST` to fail; only truly
    corrupt records (malformed JSON or CSV) do.

**Q9. Scenario: a source added a new column overnight. What happens in each layer?**

??? success "Answer"
    Bronze: with Auto Loader's default `addNewColumns` mode, the stream adds the column to the schema and stops with an
    `UnknownFieldException`; after a restart (automatic when run as a Lakeflow Job, formerly a Databricks Workflows job, with retries) the new column is
    loaded. With `rescue` mode the values go to `_rescued_data`; with a raw string or `VARIANT` bronze, nothing breaks
    at all.
    Silver: nothing changes, because silver selects named columns and Delta enforces its schema. The team decides
    whether the column belongs in silver; if so, add it deliberately (schema evolution or `ALTER TABLE`) and backfill
    from bronze.
    Gold: unchanged unless a business measure needs the column.

    **Why:** bronze absorbs drift, silver changes only by decision. The worked example detected `channel` with a
    `json_object_keys` check before deciding.

**Q10. What is Auto Loader's default schema evolution mode when you do not provide a schema, and when you do?**

??? success "Answer"
    Without a schema: `addNewColumns`. With a schema provided: `none` (new columns are ignored, and data is not rescued
    unless `rescuedDataColumn` is set). `addNewColumns` is not allowed when a schema is provided, but works if the
    schema is given as schema hints.

    **Why:** both defaults are stated on the Auto Loader schema page; mixing them up is a common interview trap.

**Q11. Why should silver read bronze as a stream? When is a batch read fine?**

??? success "Answer"
    A streaming read of an append-only Delta table processes only new commits since the last run (tracked in a
    checkpoint), so each run costs in proportion to new data, and with `AvailableNow` it runs as a scheduled
    incremental batch. Databricks recommends streaming reads from bronze "assuming all sources are append-only", and
    batch reads only for small datasets such as small dimension tables.

    **Why:** re-reading all of bronze every run gets slower and more expensive as bronze grows forever.

**Q12. Scenario: gold reads silver with `spark.readStream.table("shop_prod.silver.orders")`. The stream fails the day after silver starts using MERGE. Why, and what are the options?**

??? success "Answer"
    A streaming read of a Delta table accepts only appends; an `UPDATE`, `DELETE`, `MERGE` or overwrite on the source
    fails the stream. Options from the Delta streaming page: `skipChangeCommits` (process appends only, ignoring
    updates, so corrections do not reach gold), a full refresh, streaming the table's change data feed (recommended
    when possible) and handling each change type, or a materialized view. A batch `REPLACE WHERE` over recent dates is
    another common answer.

    **Why:** this is exactly why the docs' streaming advice says "assuming all sources are append-only".

**Q13. What does the second `show` print?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
sql("CREATE TABLE silver_append (order_id INT, amount DECIMAL(10,2)) USING DELTA")
for run in (1, 2):
    sql("""INSERT INTO silver_append
           SELECT order_id, amount FROM VALUES (1001, 59.90), (1002, 120.00) AS v(order_id, amount)""")
    show("SELECT order_id, count(*) AS copies FROM silver_append GROUP BY ALL ORDER BY ALL")
```

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +--------+------+
    |order_id|copies|
    +--------+------+
    |1001    |2     |
    |1002    |2     |
    +--------+------+
    ```

    **Why:** `INSERT INTO` appends unconditionally; running the load twice doubles the data. That is the definition of a
    load that is not idempotent. Use `MERGE` on the key instead (output from `traps_demo.out`, section 2).

**Q14. A MERGE into silver fails with `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`. Why, and how do you fix it?**

??? success "Answer"
    The source has more than one row for the same key, and that key exists in the target, so the update is ambiguous:
    Delta cannot tell which source row should win. Fix: deduplicate the source first, keeping the latest version per
    key, and add a newer-wins guard:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    MERGE INTO silver_orders t
    USING (SELECT * FROM batch_with_dup
           QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY updated_at DESC) = 1) s
    ON t.order_id = s.order_id
    WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *;
    ```

    **Why:** the `MERGE INTO` reference says the operation fails when more than one source row matches the same target
    row, and recommends preprocessing the source. Databricks allows multiple matches only for an unconditional delete.

**Q15. The target table is empty and the MERGE source has two identical rows for order 1002. Does the MERGE fail?**

??? success "Answer"
    No. Neither row matches anything in the empty target, so both go through `WHEN NOT MATCHED THEN INSERT` and 1002 is
    inserted twice. The next run that matches 1002 then fails with the multiple-match error, or a later dedup is needed.

    **Why:** the Delta merge page warns that duplicates within the new dataset are inserted. Section 7.9 shows the
    output: `1002 | 2`.

**Q16. Find the bug. Late events sometimes arrive after newer ones.**

*Databricks only, not run here. Syntax from [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into).*

```sql
MERGE INTO shop_prod.silver.orders t
USING latest_batch s ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

??? success "Answer"
    `WHEN MATCHED THEN UPDATE SET *` has no ordering guard: an older version that arrives late overwrites the newer row
    already in silver. Fix: `WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *` (or compare a source
    sequence number). The worked example in 7.10 uses this guard.

    **Why:** arrival order is not event order. The CDC page stresses a column that deterministically orders changes so
    out-of-order updates are handled.

**Q17. What does "idempotent load" mean, and name one technique per layer.**

??? success "Answer"
    Running the load twice on the same input gives the same result as running it once. Bronze: an ingestion checkpoint
    that tracks loaded files (Auto Loader; `COPY INTO` also skips loaded files). Silver: `MERGE` on the key with a
    deduplicated source and a newer-wins guard, or `txnAppId`/`txnVersion` in `foreachBatch`. Gold: replace a range or
    the whole result (`REPLACE WHERE`, `CREATE OR REPLACE`, a materialized view) rather than appending.

    **Why:** retries and repairs are routine; without idempotency each one corrupts the data.

**Q18. What delivery guarantee does `foreachBatch` give, and how do you get exactly-once results into Delta?**

??? success "Answer"
    At-least-once: a micro-batch can be written more than once after a failure. Make the write idempotent: `MERGE` with
    a deduplicated source, or Delta's `txnAppId` and `txnVersion` options with `txnVersion` bound to the batch ID, so
    Delta skips a batch it has already written.

    **Why:** the foreachBatch page states the at-least-once guarantee and documents the two options for idempotent
    Delta writes.

**Q19. SCD Type 1 or Type 2 for the customer's city, if regional sales must show where the customer lived at the time of each order?**

??? success "Answer"
    Type 2. Type 1 overwrites the city, so all past orders would move to the new city. Type 2 keeps one row per version
    with a validity period, so each order joins to the version valid at its order time.

    **Why:** the CDC page: Type 1 keeps only the current state; Type 2 "maintains a complete historical record". Use Type
    1 for corrections where history is meaningless (an email typo). In a Type 2 table built by `AUTO CDC`, the current
    row for each key is the one with `__END_AT IS NULL` (`__START_AT` and `__END_AT` come from the `SEQUENCE BY`
    column).

**Q20. How does the medallion architecture relate to Kimball star schemas, Data Vault and data mesh?**

??? success "Answer"
    They answer different questions and combine. Medallion organizes data by quality. Kimball dimensional modeling
    says how to model analytical tables, and gold is often a Kimball star schema. Data Vault (hubs, links, satellites)
    is an integration modeling method that some teams use in silver, with star schemas built from it in gold. Data mesh
    is organizational: domain teams own their data as products, and each domain can run its own bronze, silver and
    gold and publish gold tables to others.

    **Why:** Databricks pages describe gold as a dimensional model and mention multiple gold layers per business need
    and "data as a product"; they do not discuss Data Vault or data mesh by name, so present those as field practice.

**Q21. What is a bitemporal table, and when is SCD Type 2 not enough?**

??? success "Answer"
    A bitemporal table tracks two timelines: when each change took effect (business time) and when the system learned
    about it (system time). SCD Type 2 rewrites history after a late or corrected change and no longer shows what the
    table said before. When you must reproduce what you reported at a past date (regulatory reporting, financial
    audits), you need bitemporal. On Databricks it requires `AUTO CDC` with `SYSTEM SEQUENCE BY`.

    **Why:** described on the Databricks "Change data capture and snapshots" page.

**Q22. Name the three expectation actions, the default, and the SQL syntax of each.**

??? success "Answer"
    Warn (default): `CONSTRAINT name EXPECT (cond)`, invalid rows are written and counted. Drop:
    `EXPECT (cond) ON VIOLATION DROP ROW`, invalid rows are removed and counted. Fail:
    `EXPECT (cond) ON VIOLATION FAIL UPDATE`, the update fails (rolled back atomically for a table update). Python:
    `dp.expect`, `dp.expect_or_drop`, `dp.expect_or_fail`.

    **Why:** from "Manage data quality with pipeline expectations".

**Q23. Why quarantine invalid rows instead of dropping them?**

??? success "Answer"
    Dropping keeps silver clean but hides the problem; quarantine keeps silver clean and keeps the row, with the failed
    rules, in a table people can review, fix and reprocess. Its row count is a quality metric to alert on.

    **Why:** the Databricks expectation-patterns page documents a quarantine pattern (an `is_quarantined` flag splitting
    valid and invalid rows), and the foreachBatch page writes invalid rows to a dead-letter queue table.

**Q24. Scenario: the business wants yesterday's numbers restated after a late correction arrived today. How?**

??? success "Answer"
    1. Bronze appends the correction like any event.
    2. Silver's `MERGE` updates the order because its `updated_at` is newer; the order keeps its original `order_date`.
    3. Gold recomputes the affected dates: `INSERT INTO gold.daily_sales REPLACE WHERE order_date >= <earliest changed
       date> SELECT ...` (or a materialized view refresh). The worked example restated March 1 from 215.40 to 205.40.
    4. For the audit trail, time travel (`VERSION AS OF`) shows what gold said before, while old versions are retained;
       if past reports must be reproducible long term, use a bitemporal design or snapshot tables.

    **Why:** facts change in bounded ranges, and the Databricks construct mapping recommends `REPLACE WHERE` for exactly
    "fact updates, late-arriving data, and corrections".

**Q25. What kind of data model belongs in gold, and what does Databricks say about 3NF?**

??? success "Answer"
    Dimensional models (facts and dimensions, star or snowflake schemas) and aggregates aligned with business
    definitions. Databricks "recommends against using a heavily normalized model such as third normal form (3NF)" for a
    new lakehouse, because star and snowflake schemas need fewer joins and fewer keys kept in sync, and wide tables let
    file statistics skip data.

    **Why:** medallion page (dimensional modeling in gold) and the data modeling page.

**Q26. Materialized view or `REPLACE WHERE` flow: when do you use each?**

??? success "Answer"
    `REPLACE WHERE` for batch overwrites of a bounded range: periodic recompute of a time window, late data, corrections,
    compliance deletions; cost depends on the range size. Materialized view for a serving layer: precomputed results
    for dashboards, kept current automatically, incrementally where the query allows (otherwise a full refresh, so
    refresh cost is harder to predict).

    **Why:** "When to use REPLACE WHERE vs. materialized views".

**Q27. Compare continuous, triggered and batch ingestion for cost and latency.**

??? success "Answer"
    Continuous incremental: higher cost, lower latency (always running). Triggered incremental: lower cost, higher
    latency (streaming code started on a schedule or file arrival, `AvailableNow` in notebooks). Batch with manual
    incremental logic: lower cost, highest latency, plus extensive custom setup (for example partition overwrites).

    **Why:** the medallion page's ingestion frequency table. Triggered incremental is the common middle ground.

**Q28. How would you organize dev and prod medallion tables in Unity Catalog?**

??? success "Answer"
    A catalog per environment (`shop_dev`, `shop_prod`), with `bronze`, `silver` and `gold` schemas inside each, and the
    same table names, so code changes environment through one catalog parameter. Bind the production catalog to the
    production workspace if isolation requires it; production writes by service principals only.

    **Why:** the UC best practices page calls catalogs the primary isolation unit, often per environment, team or
    business unit; the medallion page's example uses a schema per layer (`ops.bronze`, `ops.silver`, `ops.gold`).

**Q29. Write the grants so the `analysts` group can read every table in production gold.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant).*

    ```sql
    GRANT USE CATALOG ON CATALOG shop_prod TO `analysts`;
    GRANT USE SCHEMA, SELECT ON SCHEMA shop_prod.gold TO `analysts`;
    ```

    **Why:** `SELECT` granted on a schema is inherited by its tables (and future tables), and reading also requires
    `USE CATALOG` and `USE SCHEMA` on the parents (Unity Catalog privileges reference).

**Q30. Scenario: marketing, finance and sales each copy `gold.daily_sales` into their own schema every night and add their own adjustments. What is wrong?**

??? success "Answer"
    The copies become data silos: they drift out of sync, each team's "revenue" means something different, storage and
    compute are wasted, and corrections in the original do not reach the copies. Keep one governed gold table; give
    access with grants, views or row filters, and put shared business logic in gold itself. If teams truly need
    different models, build separate domain gold tables from silver, owned and documented.

    **Why:** the "Guiding principles" page warns against operational copies that become silos.

**Q31. When would you not build three layers?**

??? success "Answer"
    Small data from one clean source (a raw table plus a view may do), a millisecond real-time path (process events
    directly, land them in bronze in parallel), exploration and one-off analysis, or consuming a curated partner table
    shared with OpenSharing. Keep the core idea anyway: keep raw data so you can replay.

    **Why:** the pattern is a best practice, not a requirement; each layer costs latency, storage and jobs.

**Q32. Scenario: a design has bronze, bronze_clean, silver_stage, silver, silver_enriched, gold_pre and gold. What do you say?**

??? success "Answer"
    Ask what guarantee and which consumers each layer has. Layers with no consumer of their own (`bronze_clean`,
    `silver_stage`, `gold_pre`) usually collapse into views or into the step that follows. Every extra hop adds latency,
    storage, cost and failure points. Intermediate steps can be temporary views inside the same job.

    **Why:** too many layers is a recognized anti-pattern; the layer count should follow the guarantees.

**Q33. Are "landing zone", "staging", "platinum layer" and "multi-hop" Databricks terms?**

??? success "Answer"
    "Multi-hop" is: the Databricks medallion page gives it as another name for the medallion architecture. The others
    are field terms, not Databricks medallion layers. A landing zone is the storage location where files arrive before
    ingestion (the UC best practices page mentions external volumes for "landing areas for raw data"); "staging" often
    means a temporary area emptied on each load, so check whether a team's staging keeps history like bronze; a
    platinum layer is a name some teams use for highly specialized products above gold.

    **Why:** say clearly what is official and what is convention; interviewers notice.

**Q34. In the worked example, silver.orders has `customer_id INT NOT NULL`. What happens if a row with a null customer reaches the write?**

??? success "Answer"
    The write fails. Run here, open-source Delta reported
    `[DELTA_NOT_NULL_CONSTRAINT_VIOLATED] NOT NULL constraint violated for column: customer_id.` and wrote nothing. In
    the example this cannot happen, because the rule `customer_id_missing` sends such rows to quarantine first.

    **Why:** Delta enforces `NOT NULL` on write. The constraint is the last line of defense; the quarantine rules are the
    first.

**Q35. In the worked example, rerun 1 (no new files) left no new version in silver's history. Why?**

??? success "Answer"
    The silver stream's checkpoint showed no new bronze commits, so the `AvailableNow` run processed nothing and
    `foreachBatch` was never called; no `MERGE` ran, so no commit. `traps_demo.py` section 6 shows it: the second run
    printed no batch at all, and the third run (after one new row) printed `batch_id=1, rows=1`.

    **Why:** idempotency at the stream level comes from the checkpoint; the `MERGE` design covers the case where the
    checkpoint is lost (the replay, version 2).

**Q36. Gold in the worked example is written with `INSERT INTO`. Why is it still safe to rerun?**

??? success "Answer"
    It is `INSERT INTO ... REPLACE WHERE order_date >= ...`: in one atomic commit, Delta removes the rows matching the
    predicate and inserts the recomputed rows. Running it twice replaces the same days with the same numbers. The gold
    history shows three `WRITE` commits with the same predicate and the table never doubled.

    **Why:** replacing a range is idempotent; appending totals is not.

**Q37. Why does silver.orders keep `_source_file` and `_ingested_at` from bronze?**

??? success "Answer"
    Lineage and debugging: for any silver row you can find the exact file and load that produced it, and go back to the
    raw line in bronze. The deduplication also uses them as tie-breakers when two versions have the same `updated_at`
    (the example kept 1002 from the evening file). Because they are carried from bronze, not recomputed, a replay
    writes the same values and stays idempotent.

**Q38. Find the bug. This job is the whole pipeline for orders.**

*Databricks only, not run here. Syntax from [Ingest data as semi-structured variant type](https://docs.databricks.com/aws/en/ingestion/variant).*

```python
(spark.read.json("/Volumes/shop_prod/bronze/landing/orders/")
   .dropDuplicates(["order_id"])
   .write.mode("append")
   .saveAsTable("shop_prod.silver.orders"))
```

??? success "Answer"
    Several problems. It writes straight from ingestion into silver (no bronze, so schema changes or corrupt records
    break the job and there is nothing to replay). `spark.read.json` infers types, so a malformed value can become
    `NULL` or land in a corrupt-record column, and the original is not kept. It rereads every file on every run (no
    checkpoint), and `mode("append")` writes all of them again, duplicating the table on each run. `dropDuplicates`
    only removes duplicates inside this read, keeps an arbitrary row per key, and does not compare with the target.
    Fix: Auto Loader into bronze with metadata; silver as a stream from bronze with dedup to the latest version and a
    guarded `MERGE`.

    **Why:** the docs advise against writing silver directly from ingestion; sections 7.5 to 7.10 show each fix.

**Q39. Where does business logic belong: silver or gold?**

??? success "Answer"
    Both, split by kind. Silver holds the rules every consumer needs: types, null handling, validity checks,
    deduplication, conformed codes, joins that build an entity. Gold holds business definitions and measures: what
    counts as revenue, fiscal calendars, KPIs, segments, each defined once. In the worked example, "amount must be a
    valid non-negative decimal" is a silver rule; "revenue excludes cancelled orders" is a gold rule.

    **Why:** the docs say silver corrects "errors and inconsistencies" and gold "aligns with business logic and
    requirements". Putting business definitions in dashboards instead gives every report its own number.

**Q40. Scenario: a bug in the silver logic has been producing wrong amounts for three weeks. How do you fix the data?**

??? success "Answer"
    Fix the code, then reprocess from bronze, which still holds every raw record: run the idempotent silver `MERGE`
    over the last three weeks of bronze in batch (or rebuild silver from bronze with a new checkpoint and swap it in),
    then recompute the affected gold dates with `REPLACE WHERE`. If the update guard compares `updated_at`, the
    corrected rows have the same timestamps, so for this one-off reprocessing use a `MERGE` that updates when the
    values differ, or rebuild the table. In a Lakeflow pipeline (formerly Delta Live Tables), run a full refresh of the
    silver and gold tables, but not of bronze if its source no longer has the data: a full refresh of a streaming table
    clears it and reprocesses only what the source still holds. Protect bronze with `pipelines.reset.allowed = false`.

    **Why:** reprocessing is the main reason bronze keeps raw history; the "Run a pipeline update" page documents the
    full refresh behavior, the dropped-records risk and the property.

## Sources

- [What is the medallion lakehouse architecture?](https://docs.databricks.com/aws/en/lakehouse/medallion) (last updated Oct 29, 2026)
- [Guiding principles](https://docs.databricks.com/aws/en/lakehouse-architecture/guiding-principles) (last updated Oct 29, 2026)
- [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) (last updated Oct 30, 2026)
- [Unity Catalog privileges reference](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/privileges-reference) (last updated Nov 6, 2026)
- [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant) (last updated Sep 11, 2026)
- [What is Auto Loader?](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/) (last updated Oct 15, 2026)
- [Configure schema inference and evolution in Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema) (last updated Nov 5, 2026)
- [File metadata column](https://docs.databricks.com/aws/en/ingestion/file-metadata-column) (last updated Sep 11, 2026)
- [Ingest data as semi-structured variant type](https://docs.databricks.com/aws/en/ingestion/variant) (last updated Sep 11, 2026)
- [Schema enforcement](https://docs.databricks.com/aws/en/tables/schema-enforcement) (last updated Sep 11, 2026)
- [Update table schemas with schema evolution](https://docs.databricks.com/aws/en/tables/update-schema) (last updated Sep 11, 2026)
- [Upsert into a Delta Lake table using merge](https://docs.databricks.com/aws/en/delta/merge) (last updated Sep 11, 2026)
- [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into) (last updated Sep 11, 2026)
- [INSERT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-dml-insert-into) (last updated Oct 21, 2026)
- [Use foreachBatch to write to arbitrary data sinks](https://docs.databricks.com/aws/en/structured-streaming/foreach) (last updated Nov 5, 2026)
- [Delta Lake table streaming reads and writes](https://docs.databricks.com/aws/en/structured-streaming/delta-lake) (last updated Oct 15, 2026)
- [Configure Structured Streaming trigger intervals](https://docs.databricks.com/aws/en/structured-streaming/triggers) (last updated Nov 10, 2026)
- [Use change data feed on Databricks](https://docs.databricks.com/aws/en/tables/features/change-data-feed) (last updated Oct 9, 2026)
- [Change data capture and snapshots](https://docs.databricks.com/aws/en/data-engineering/what-is-cdc) (last updated Nov 9, 2026)
- [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc) (last updated Nov 9, 2026)
- [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations) (last updated Oct 26, 2026)
- [Expectation recommendations and advanced patterns](https://docs.databricks.com/aws/en/ldp/expectation-patterns) (last updated Oct 26, 2026)
- [Use standalone materialized views](https://docs.databricks.com/aws/en/sql/mv-st/materialized) (last updated Nov 5, 2026)
- [When to use REPLACE WHERE vs. materialized views](https://docs.databricks.com/aws/en/sql/mv-st/replace-where-vs-materialized-views) (last updated Oct 15, 2026)
- [Data modeling](https://docs.databricks.com/aws/en/transform/data-modeling) (last updated Sep 11, 2026)
- [Run a pipeline update](https://docs.databricks.com/aws/en/ldp/updates) (last updated Sep 11, 2026)
