# 20. Tables in Databricks SQL

*A data engineer spends a surprising share of the day writing DDL and DML: creating the silver table with the right columns and keys, choosing how it is laid out, adding a column when the source grows one, reloading one day of data without touching the rest, and checking afterwards what the table looks like and who changed it. This chapter is the reference for that work in Databricks SQL. It goes from `CREATE TABLE` to `MERGE`, `CLONE`, views and `DESCRIBE`, and for each statement it shows what the open-source engine really does and where Databricks adds or changes something. Interviewers like this ground because small choices have large consequences: `CREATE OR REPLACE` versus `DROP` and `CREATE`, `REPLACE WHERE` versus `MERGE`, partitioning versus liquid clustering, an identity column on a table that two jobs write to.*

!!! abstract "In this chapter"
    **You will learn:**

    - the kinds of tables and views in Databricks (managed, external, temporary, clones, views, materialized views, streaming tables) and what `DROP` does to each
    - every `CREATE TABLE` form: column list, CTAS, `CREATE OR REPLACE`, `IF NOT EXISTS`, `LIKE`, `LOCATION`, `SHALLOW CLONE` and `DEEP CLONE`, and the PySpark equivalents
    - column properties: `NOT NULL`, `DEFAULT`, generated columns, identity columns; enforced `CHECK` constraints and informational `PRIMARY KEY` / `FOREIGN KEY` / `UNIQUE`
    - partitioning versus liquid clustering (`CLUSTER BY`, `CLUSTER BY AUTO`, changing keys), as DDL
    - table properties (`TBLPROPERTIES`) and the table features they switch on: change data feed, deletion vectors, column mapping, type widening, append-only
    - `ALTER TABLE`: add, move, comment, retype, rename and drop columns; rename tables; tags
    - loading data: `INSERT INTO`, `INSERT OVERWRITE`, `BY NAME`, `REPLACE WHERE`, `REPLACE USING`, `REPLACE ON`, dynamic partition overwrite, and how to choose between them and `MERGE`
    - `UPDATE`, `DELETE`, `TRUNCATE` and every `MERGE` clause, including `WHEN NOT MATCHED BY SOURCE` and `WITH SCHEMA EVOLUTION`
    - `DESCRIBE TABLE EXTENDED`, `DESCRIBE DETAIL`, `DESCRIBE HISTORY`, `SHOW CREATE TABLE`, `SHOW TBLPROPERTIES`, comments and tags, `UNDROP`

    **You need:** [4. Delta Lake](04-Delta-Lake.md) (the transaction log, time travel, schema evolution, column mapping), [5. Unity Catalog](05-Unity-Catalog.md) (catalogs, schemas, managed storage), and generic DDL/DML from the SQL course: [Insert, update, delete, merge](../../databases/sql/17-Insert-Update-Delete-Merge.md).

    **Levels:** sections 20.1 to 20.4 beginner, 20.5 to 20.12 intermediate, 20.13 expert.

**About the examples.** All "Run here" examples use the Red Rock Supply tables (`customers`, `products`, `orders`, `order_items`). On Databricks they live in Unity Catalog as `shop.silver.orders` and so on. Locally there is no Unity Catalog, so the scripts create schemas called `silver`, `gold` and `dev` in Spark's built-in catalog and write `USING DELTA` (open-source Spark's default format is Parquet; on Databricks, "If `USING` is omitted, the default is `DELTA`" ([CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using))). The scripts and their full output are in `src/ch20/`: `ch20_01_create`, `ch20_02_columns`, `ch20_03_layout_alter`, `ch20_04_dml`, `ch20_05_clone_views_describe`, `ch20_06_answers` and `ch20_07_extras`, each with a `.out` file. Error messages in the outputs are shortened to their first line by the scripts.

**What this chapter does not repeat.** How the transaction log, time travel, `RESTORE`, `VACUUM` and deletion vectors work is in [chapter 4](04-Delta-Lake.md). MERGE patterns for deduplication, late data and SCD types 1 and 2 are in [chapter 9](09-Building-Silver.md). Why liquid clustering is faster, and how to tune it, is in [chapter 22](22-Performance-Tuning.md). Privileges on tables are in [chapter 5](05-Unity-Catalog.md) and [chapter 23](23-Governance-and-Operations.md). Views as a programming tool (dynamic views, row filters, column masks) are in [chapter 21](21-Programming-in-SQL.md).

## 20.1 Kinds of tables, and what DROP does to each
*Level: beginner.*

The first question for any new table is not its columns but **who owns the files**. That decides what `DROP TABLE` deletes, which features the table gets, and who can read it outside Databricks.

- A **managed table** has no `LOCATION` clause. Unity Catalog picks the folder (inside the managed storage of the schema or catalog) and manages "all read, write, storage, and optimization responsibilities". Databricks calls managed tables "the default and recommended table type" ([Unity Catalog managed tables for Delta Lake and Apache Iceberg](https://docs.databricks.com/aws/en/tables/managed)).
- An **external table** has a `LOCATION` you choose, inside a registered external location. Unity Catalog manages its metadata but "doesn't manage the data's lifecycle, optimization, storage location, or layout" ([Work with external tables](https://docs.databricks.com/aws/en/tables/external)). Use it for data that must stay where it is, for example files in a format a managed table cannot use, or files that non-Databricks tools read directly.
- A **clone** is a new table made from an existing one at some version. A **shallow clone** copies only the metadata and points at the source's data files; a **deep clone** copies the files too.
- A **temporary table** (Databricks SQL and Databricks Runtime 18.1 and above) and a **temporary view** live only for the session.
- A **view** stores a query, not data. A **materialized view** stores the query's result and refreshes it. A **streaming table** is a Delta table fed incrementally by a stream. Both are created and refreshed by Lakeflow pipelines (formerly Delta Live Tables, see [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)); section 20.11 covers them.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 330" role="img" aria-label="Four table names in the catalog and where their data files live. A managed table's files are in the schema's managed storage and are deleted after DROP. A shallow clone points at the same files and keeps only the files it changes in its own folder. An external table's files are at a path you chose and stay after DROP. A deep clone has its own full copy of the files.">
<defs><marker id="a201" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g font-size="13" fill="currentColor">
<text x="20" y="24" font-weight="bold">Name in the catalog</text>
<text x="330" y="24" font-weight="bold">Data files in cloud storage</text>
<rect x="20" y="40" width="220" height="48" rx="5" fill="none" stroke="currentColor" stroke-width="1.5"/>
<text x="30" y="60">shop.silver.orders (managed)</text>
<text x="30" y="78">DROP: files deleted later</text>
<rect x="330" y="40" width="290" height="48" rx="5" fill="none" stroke="currentColor" stroke-width="1.5"/>
<text x="340" y="60">schema's managed storage</text>
<text x="340" y="78">files A  B  C  (Unity Catalog picks the folder)</text>
<line x1="240" y1="64" x2="326" y2="64" stroke="currentColor" marker-end="url(#a201)"/>
<rect x="20" y="115" width="220" height="48" rx="5" fill="none" stroke="currentColor"/>
<text x="30" y="135">dev.orders_test</text>
<text x="30" y="153">SHALLOW CLONE of orders</text>
<line x1="240" y1="128" x2="400" y2="92" stroke="currentColor" stroke-dasharray="5 4" marker-end="url(#a201)"/>
<text x="248" y="103">reads A B C</text>
<rect x="450" y="120" width="170" height="40" rx="5" fill="none" stroke="currentColor"/>
<text x="460" y="144">own folder: changed files</text>
<line x1="240" y1="148" x2="446" y2="148" stroke="currentColor" marker-end="url(#a201)"/>
<rect x="20" y="190" width="220" height="48" rx="5" fill="none" stroke="currentColor"/>
<text x="30" y="210">shop.bronze.orders_raw</text>
<text x="30" y="228">(external)  DROP: files stay</text>
<rect x="330" y="190" width="290" height="48" rx="5" fill="none" stroke="currentColor"/>
<text x="340" y="210">s3://red-rock/raw/orders/</text>
<text x="340" y="228">the LOCATION you gave</text>
<line x1="240" y1="214" x2="326" y2="214" stroke="currentColor" marker-end="url(#a201)"/>
<rect x="20" y="265" width="220" height="48" rx="5" fill="none" stroke="currentColor"/>
<text x="30" y="285">archive.orders_2026</text>
<text x="30" y="303">DEEP CLONE of orders</text>
<rect x="330" y="265" width="290" height="48" rx="5" fill="none" stroke="currentColor"/>
<text x="340" y="285">its own copy: files A' B' C'</text>
<text x="340" y="303">independent of the source</text>
<line x1="240" y1="289" x2="326" y2="289" stroke="currentColor" marker-end="url(#a201)"/>
</g>
</svg>
<figcaption>Figure 20.1. Managed, external and cloned tables. The catalog entry is the name; the arrows show which files each name reads. A shallow clone reads the source's files and writes only its own changes; a deep clone owns a full copy.</figcaption>
</figure>

| | Managed | External | Shallow clone | Deep clone |
| --- | --- | --- | --- | --- |
| Created with | `CREATE TABLE t (...)` or CTAS, no `LOCATION` | `... LOCATION 's3://...'` | `CREATE TABLE t SHALLOW CLONE src` | `CREATE TABLE t [DEEP] CLONE src` |
| Who chooses the folder | Unity Catalog | you | as the source (managed clone of managed, external of external in Unity Catalog) | as for any new table |
| Data files | its own | its own, at your path | the source's, plus its own changes | its own full copy |
| `DROP TABLE` (Unity Catalog) | removed; `UNDROP` possible during the recovery period (default 7 days), files deleted after it | metadata removed, files stay | clone removed; source untouched | removed like any managed/external table |
| Only here | predictive optimization, automatic liquid clustering, catalog commits, automatic file deletion after `DROP` | readable by any tool that can read the path | cheap test copy of production | archive, disaster recovery copy |

The `DROP` behavior comes from [Drop or replace a table](https://docs.databricks.com/aws/en/tables/operations/drop-table) (last updated Oct 19, 2026) and the "managed only" features from the managed tables page. The clone rows come from [Shallow clone for Unity Catalog tables](https://docs.databricks.com/aws/en/tables/operations/clone-unity-catalog) and are covered in section 20.10.

!!! tip "In the interview"
    **"Managed or external, and what happens when you drop them?"** Managed tables are the default: Unity Catalog chooses the storage, optimizes the table (predictive optimization) and, on `DROP`, keeps the table recoverable with `UNDROP` for a recovery period (7 days by default) before an asynchronous purge deletes the files. External tables have a `LOCATION` you own; `DROP` removes only the catalog entry and the files stay. Choose external only when the files must live at a fixed path or be read by other tools directly.

## 20.2 CREATE TABLE: the forms
*Level: beginner.*

The full syntax from the reference, for orientation (only the top lines; the rest is explained piece by piece below):

*Databricks only, not run here. Syntax from [CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using).*

```sql
{ { [CREATE OR] REPLACE { TEMP | TEMPORARY } TABLE | CREATE [EXTERNAL] TABLE [ IF NOT EXISTS ] | CREATE { TEMP | TEMPORARY } TABLE}
  table_name
  [ table_specification ]
  [ USING data_source ]
  [ table_clauses ]
  [ AS query ] }

table_clauses
  { OPTIONS clause |
    PARTITIONED BY clause |
    CLUSTER BY clause |
    clustered_by_clause |
    LOCATION path [ WITH ( CREDENTIAL credential_name ) ] |
    COMMENT table_comment |
    TBLPROPERTIES clause |
    DEFAULT COLLATION default_collation_name |
    WITH { ROW FILTER clause } } [...]
```

The `CREATE OR REPLACE` form is spelled `[CREATE OR] REPLACE` in the reference; for permanent tables the parameter list says "If specified, replaces the table and its content if it already exists. This clause is only supported for Delta and Apache Iceberg tables."

### A column list (managed table)

The silver orders table, with a table comment:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE SCHEMA silver;
CREATE TABLE silver.orders (
  order_id    INT,
  customer_id INT,
  order_ts    TIMESTAMP,
  status      STRING,
  amount      DECIMAL(10,2),
  currency    STRING)
USING DELTA
COMMENT 'Cleaned orders, one row per order';
```

```text
silver.orders: ('MANAGED', '<work>/warehouse/silver.db/orders')
```

The script reads `Type` and `Location` from `DESCRIBE TABLE EXTENDED`. With no `LOCATION`, the table is managed and lives under the schema's folder.

### CTAS: the schema comes from the query

`CREATE TABLE ... AS SELECT` (CTAS) creates and fills the table in one transaction. The column names and types come from the query, so you shape them there:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE gold.daily_revenue USING DELTA AS
SELECT CAST(order_ts AS DATE) AS order_date, currency, SUM(amount) AS revenue, COUNT(*) AS orders
FROM silver.orders WHERE status <> 'CANCELLED'
GROUP BY ALL;

CREATE TABLE gold.bad (order_date DATE, revenue DECIMAL(20,2)) USING DELTA AS
SELECT CAST(order_ts AS DATE), amount FROM silver.orders;           -- column list + AS
```

```text
>>> SELECT * FROM gold.daily_revenue ORDER BY order_date, currency
+----------+--------+-------+------+
|order_date|currency|revenue|orders|
+----------+--------+-------+------+
|2026-03-01|CAD     |179.90 |2     |
|2026-03-02|USD     |15.50  |1     |
+----------+--------+-------+------+

+----------+-------------+-------+
|col_name  |data_type    |comment|
+----------+-------------+-------+
|order_date|date         |NULL   |
|currency  |string       |NULL   |
|revenue   |decimal(20,2)|NULL   |
|orders    |bigint       |NULL   |
+----------+-------------+-------+

=== 3. CTAS with a column list is not allowed ===
>>> CREATE TABLE gold.bad (order_date DATE, revenue DECIMAL(20,2)) USING DELTA AS SELECT CAST(order_ts AS DATE), amount FROM silver.orders
   ParseException: Operation not allowed: Schema may not be specified in a Create Table As Select (CTAS) statement.
```

Two things to notice. `SUM` of a `DECIMAL(10,2)` became `DECIMAL(20,2)` and `COUNT(*)` became `BIGINT`: CTAS takes whatever types the query produces. And CTAS cannot also carry a column list; the reference says "When you specify a `query` you must not also specify a `table_specification`". That rule has a consequence you meet in section 20.3: identity columns, generated columns, `NOT NULL`, defaults and key constraints need a column list, so a table that needs them is created first and filled with `INSERT` afterwards. (The Constraints page says the same for keys: "CTAS statements don't support this constraint clause" ([Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints)).) `CLUSTER BY`, `PARTITIONED BY`, `COMMENT` and `TBLPROPERTIES` are table clauses, not part of the column list, so they do work with CTAS; the clustering page shows `CREATE TABLE table2 CLUSTER BY (col0) AS SELECT * FROM table1` and the local engine accepted the same shape (`ch20_01_create.out`, section 11).

### IF NOT EXISTS and CREATE OR REPLACE

`IF NOT EXISTS` makes a create idempotent: if the name exists, nothing happens, even if the definition differs. `CREATE OR REPLACE` swaps the table's definition and content in one commit. The two cannot be combined ("`CREATE OR REPLACE TABLE IF NOT EXISTS` is not allowed").

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE IF NOT EXISTS gold.daily_revenue (x INT) USING DELTA;   -- table exists: skipped
CREATE TABLE gold.daily_revenue (x INT) USING DELTA;                 -- table exists: error

CREATE OR REPLACE TABLE gold.daily_revenue USING DELTA AS
SELECT CAST(order_ts AS DATE) AS order_date, SUM(amount) AS revenue
FROM silver.orders WHERE status <> 'CANCELLED' GROUP BY ALL;

DESCRIBE HISTORY gold.daily_revenue;
SELECT * FROM gold.daily_revenue VERSION AS OF 0;
CREATE OR REPLACE TABLE IF NOT EXISTS gold.x (a INT) USING DELTA;
```

```text
>>> CREATE TABLE IF NOT EXISTS gold.daily_revenue (x INT) USING DELTA
OK
columns still: ['order_date', 'currency', 'revenue', 'orders']
>>> CREATE TABLE gold.daily_revenue (x INT) USING DELTA
   AnalysisException: [TABLE_OR_VIEW_ALREADY_EXISTS] Cannot create table or view `gold`.`daily_revenue` because it already exists.

>>> SELECT * FROM gold.daily_revenue ORDER BY order_date
+----------+-------+
|order_date|revenue|
+----------+-------+
|2026-03-01|179.90 |
|2026-03-02|15.50  |
+----------+-------+

+-------+---------------------------------+
|version|operation                        |
+-------+---------------------------------+
|0      |CREATE TABLE AS SELECT           |
|1      |CREATE OR REPLACE TABLE AS SELECT|
+-------+---------------------------------+

version 0 is still readable:
>>> SELECT * FROM gold.daily_revenue VERSION AS OF 0 ORDER BY order_date, currency
+----------+--------+-------+------+
|order_date|currency|revenue|orders|
+----------+--------+-------+------+
|2026-03-01|CAD     |179.90 |2     |
|2026-03-02|USD     |15.50  |1     |
+----------+--------+-------+------+

=== 6. OR REPLACE and IF NOT EXISTS together ===
>>> CREATE OR REPLACE TABLE IF NOT EXISTS gold.x (a INT) USING DELTA
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'NOT'. SQLSTATE: 42601 (line 1, pos 27)
```

The replaced table has a new schema (two columns instead of four), yet it is the same table: version 1 in the same history, and version 0 is still there for time travel. That is the whole argument for `CREATE OR REPLACE` over `DROP` + `CREATE`. Databricks lists the advantages: "Table contents are replaced, but the table identity is maintained", "The table history is retained, and you can revert the table to an earlier version with the `RESTORE` command", "The operation is a single transaction, so there is never a time when the table doesn't exist", and concurrent readers continue undisturbed ([Drop or replace a table](https://docs.databricks.com/aws/en/tables/operations/drop-table)). The CREATE TABLE page adds that `REPLACE` "preserves the table history and granted privileges, row filters, and column masks", and that "Databricks strongly recommends using `REPLACE` instead of dropping and re-creating tables".

!!! warning "DROP then CREATE in a production job"
    The drop-and-recreate pattern "can result in an error, dropped records, or corrupted results" for concurrent operations, for every table type and with or without Unity Catalog ([Drop or replace a table](https://docs.databricks.com/aws/en/tables/operations/drop-table)). A reader that runs between the two statements finds no table; grants on the old table are gone; a stream reading the old table loses its source. Use `CREATE OR REPLACE TABLE ... AS SELECT`.

### CREATE TABLE LIKE: copy the definition, not the rows

`LIKE` creates an empty table with the definition of another one. On Databricks it works for Delta in Databricks SQL and Databricks Runtime 13.3 LTS and above ([CREATE TABLE LIKE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-like)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
ALTER TABLE silver.orders SET TBLPROPERTIES ('delta.appendOnly' = 'false', 'quality' = 'silver');
CREATE TABLE silver.orders_empty LIKE silver.orders;
SELECT count(*) AS n FROM silver.orders_empty;
```

```text
>>> SELECT count(*) AS n FROM silver.orders_empty
+---+
|n  |
+---+
|0  |
+---+

properties copied: {'delta.appendOnly': 'false', 'quality': 'silver'}
format: delta | description (table comment): Cleaned orders, one row per order
```

The LIKE page has a table of what carries over when the source is a Delta table and the target is Delta: comment, columns, partition columns, configuration (table properties), table constraints and the Delta protocol, yes; row filters, column masks and governed tags, no. It warns that `LIKE` "does not carry over access controls from the source table", so attribute-based (ABAC) policies that match the source through governed tags do not match the copy until you tag it. The run agrees on the parts the open-source engine has: zero rows, properties and comment copied.

### External tables: LOCATION

Add `LOCATION` and the table is external. On Databricks the path must be inside an external location you have `CREATE EXTERNAL TABLE` on ([Work with external tables](https://docs.databricks.com/aws/en/tables/external)).

*Databricks only, not run here. Syntax from [Work with external tables](https://docs.databricks.com/aws/en/tables/external).*

```sql
CREATE TABLE shop.bronze.orders_raw
(
  order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING, amount STRING, currency STRING
)
LOCATION 's3://red-rock-lake/bronze/orders_raw';
```

Locally, any folder works. The run creates an external `customers` table, drops both kinds, and registers the external folder again:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.customers (customer_id INT, name STRING, email STRING, city STRING,
                               country STRING, updated_at TIMESTAMP)
USING DELTA LOCATION '<work>/lake/silver/customers';
-- ... INSERT two rows ...
DROP TABLE silver.orders_empty;      -- managed
DROP TABLE silver.customers;         -- external
CREATE TABLE silver.customers USING DELTA LOCATION '<work>/lake/silver/customers';
SELECT customer_id, name, city FROM silver.customers ORDER BY customer_id;
```

```text
silver.customers: ('EXTERNAL', '<work>/lake/silver/customers')
silver.orders   : ('MANAGED', '<work>/warehouse/silver.db/orders')

=== 9. DROP TABLE: managed loses its files, external keeps them ===
managed folder exists after DROP : False
external folder exists after DROP: True
>>> SELECT customer_id, name, city FROM silver.customers ORDER BY customer_id
+-----------+--------+---------+
|customer_id|name    |city     |
+-----------+--------+---------+
|3          |Bo Chen |Flagstaff|
|7          |Ana Ruiz|Moab     |
+-----------+--------+---------+
```

The re-registration needs no column list: "For Delta tables, the table inherits its configuration from the `LOCATION` if data already exists at that path", and anything you do specify "must exactly match the existing data" ([CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using)).

!!! warning "Open source deletes managed files at once; Unity Catalog waits"
    The local managed folder vanished immediately because this is Spark's built-in catalog (it behaves like the legacy Hive metastore, where "the underlying data is deleted"). In Unity Catalog a dropped managed table is "marked for deletion" and can be recovered with `UNDROP` during the recovery period ([Drop or replace a table](https://docs.databricks.com/aws/en/tables/operations/drop-table)). Section 20.10 shows `UNDROP`.

### Temporary tables

*Databricks only, not run here. Syntax from [CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using).*

```sql
CREATE TEMP TABLE temp_1 (a INT);
INSERT INTO temp_1 VALUES (1);
CREATE OR REPLACE TEMP TABLE temp_1 (a VARCHAR(100));
```

A temporary table "persists data temporarily during the session", its name must be unqualified, and "Databricks drops temporary tables automatically when the session ends" (Databricks SQL and Databricks Runtime 18.1 and above, per the same page). It cannot have `USING`, `LOCATION`, `PARTITIONED BY`, `CLUSTER BY`, row filters, generated columns or column masks. Open-source Spark 4.2 has no such thing: `CREATE TEMP TABLE tmp_orders (order_id INT)` failed with `ParseException: CREATE TEMPORARY TABLE without a provider is not allowed.` (`ch20_01_create.out`). Do not confuse it with a temporary view (section 20.11), which stores no data.

### The same in PySpark

Three DataFrame-side ways to create Delta tables: `saveAsTable`, the `DeltaTable` builder (needed for Delta-only options), and the `writeTo` (DataFrameWriterV2) API.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from delta.tables import DeltaTable

df = spark.table("silver.orders").where("status = 'PLACED'")
df.write.format("delta").mode("overwrite").saveAsTable("silver.orders_placed")   # CTAS-like

(DeltaTable.createIfNotExists(spark)                                             # CREATE TABLE IF NOT EXISTS
    .tableName("silver.products")
    .addColumn("product_id", "INT", nullable=False)
    .addColumn("name", "STRING")
    .addColumn("category", "STRING")
    .addColumn("price", "DECIMAL(10,2)")
    .property("quality", "silver")
    .comment("Product catalog")
    .execute())

df.writeTo("silver.orders_placed2").using("delta").createOrReplace()            # CREATE OR REPLACE ... AS
```

```text
silver.orders_placed -> 2 rows, ['order_id:int', 'customer_id:int', 'order_ts:timestamp']
silver.products -> 0 rows, ['product_id:int', 'name:string', 'category:string']
silver.orders_placed2 -> 2 rows, ['order_id:int', 'customer_id:int', 'order_ts:timestamp']
```

`DeltaTable` also has `create`, `replace` and `createOrReplace`, and `addColumn` takes `generatedAlwaysAs=` for generated columns; the managed tables page recommends the builder "for Delta-specific options like generated columns and table properties". On Databricks you can leave out `.format("delta")` and `.using("delta")`.

!!! tip "In the interview"
    **"How do you rebuild a gold table every night?"** `CREATE OR REPLACE TABLE gold.x AS SELECT ...`. It is one atomic commit, readers never see a missing table, grants and history are kept, and you can time travel or `RESTORE` to last night's version. `DROP` + `CREATE` loses all of that and can break concurrent readers. In PySpark: `df.writeTo("gold.x").createOrReplace()` or `df.write.mode("overwrite").saveAsTable("gold.x")` (the latter needs `.option("overwriteSchema", "true")` when the columns change, or Delta rejects the write with `DELTA_METADATA_MISMATCH`).

## 20.3 Columns: NOT NULL, DEFAULT, generated and identity
*Level: beginner.*

The column list takes, per column, `column_identifier column_type [ column_properties ]`, where the properties are:

*Databricks only, not run here. Syntax from [CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using).*

```sql
column_properties
  { NOT NULL |
    COLLATE collation_name |
    GENERATED ALWAYS AS ( expr ) |
    GENERATED { ALWAYS | BY DEFAULT } AS IDENTITY [ ( [ START WITH start | INCREMENT BY step ] [ ...] ) ] |
    DEFAULT default_expression |
    COMMENT column_comment |
    column_constraint |
    MASK clause } [ ... ]
```

Column types are the normal Databricks SQL types (`INT`, `BIGINT`, `DECIMAL(p,s)`, `STRING`, `DATE`, `TIMESTAMP`, `TIMESTAMP_NTZ`, `BOOLEAN`, `ARRAY`, `MAP`, `STRUCT`, `VARIANT`, ...). [Chapter 19](19-Function-Toolbox.md) covers `DECIMAL` and the two timestamp types, [chapter 18](18-Semi-Structured-Data.md) the nested types and `VARIANT`. For money, use `DECIMAL(10,2)`-style types, never `DOUBLE`.

### NOT NULL

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.customers (
  customer_id INT NOT NULL,
  name        STRING NOT NULL,
  email       STRING, city STRING, country STRING, updated_at TIMESTAMP)
USING DELTA;
INSERT INTO silver.customers (customer_id, name) VALUES (7, NULL);
INSERT INTO silver.customers (customer_id, name) VALUES (7, 'Ana Ruiz');
ALTER TABLE silver.customers ALTER COLUMN email SET NOT NULL;
ALTER TABLE silver.customers ALTER COLUMN name DROP NOT NULL;
```

```text
>>> INSERT INTO silver.customers (customer_id, name) VALUES (7, NULL)
   DeltaInvariantViolationException: [DELTA_NOT_NULL_CONSTRAINT_VIOLATED] NOT NULL constraint violated for column: name.
>>> INSERT INTO silver.customers (customer_id, name) VALUES (7, 'Ana Ruiz')
OK
>>> ALTER TABLE silver.customers ALTER COLUMN email SET NOT NULL
   AnalysisException: Cannot change nullable column to non-nullable: email.; line 1 pos 0;
>>> ALTER TABLE silver.customers ALTER COLUMN name DROP NOT NULL
OK
```

The whole `INSERT` fails; nothing is written. `DROP NOT NULL` works on both engines. `SET NOT NULL` on an existing column is where they differ: Databricks documents it ("Databricks verifies that all existing rows satisfy the constraint before adding a `NOT NULL` constraint to a table" ([Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints))), but open-source Delta 4.4.1 refused it even on a column whose only value was `NULL`-free. On Databricks:

*Databricks only, not run here. Syntax from [Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints).*

```sql
ALTER TABLE shop.silver.customers ALTER COLUMN email SET NOT NULL;
ALTER TABLE shop.silver.customers ALTER COLUMN email DROP NOT NULL;
```

The same page notes that a `NOT NULL` field inside a struct needs a `NOT NULL` parent, and "Columns nested within array or map types don't accept `NOT NULL` constraints".

### DEFAULT

A default fills a column when an `INSERT` or `MERGE ... INSERT` does not give a value, and wherever an `INSERT`, `UPDATE` or `MERGE` gives the keyword `DEFAULT`. "If no default is specified `DEFAULT NULL` is applied for nullable columns" (Databricks SQL and Databricks Runtime 11.3 LTS and above, [CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using)). The expression may use literals and built-in functions, but no aggregates, window functions, generators or subqueries.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.orders_d (
  order_id INT, status STRING DEFAULT 'PLACED', currency STRING DEFAULT 'CAD')
USING DELTA;                                           -- 1: no feature property

CREATE TABLE silver.orders (
  order_id    INT NOT NULL,
  customer_id INT,
  order_ts    TIMESTAMP DEFAULT current_timestamp(),
  status      STRING DEFAULT 'PLACED',
  amount      DECIMAL(10,2),
  currency    STRING DEFAULT 'CAD')
USING DELTA
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');

INSERT INTO silver.orders (order_id, customer_id, order_ts, amount)
  VALUES (1001, 7, TIMESTAMP'2026-03-01 10:15:00', 59.90);                 -- omitted columns
INSERT INTO silver.orders VALUES (1002, 3, TIMESTAMP'2026-03-01 11:02:00', DEFAULT, 120.00, 'USD');
UPDATE silver.orders SET currency = DEFAULT WHERE order_id = 1002;

ALTER TABLE silver.orders ADD COLUMN channel STRING DEFAULT 'web';         -- 2
ALTER TABLE silver.orders ADD COLUMN channel STRING;
ALTER TABLE silver.orders ALTER COLUMN channel SET DEFAULT 'web';
INSERT INTO silver.orders (order_id, customer_id, amount) VALUES (1003, 7, 15.50);
```

```text
>>> CREATE TABLE silver.orders_d ( order_id INT, status STRING DEFAULT 'PLACED', currency STRING DEFAULT 'CAD') USING DELTA
   AnalysisException: [WRONG_COLUMN_DEFAULTS_FOR_DELTA_FEATURE_NOT_ENABLED] Failed to execute CREATE TABLE command because it assigned a column DEFAULT value,
>>> SELECT order_id, status, currency FROM silver.orders ORDER BY order_id
+--------+------+--------+
|order_id|status|currency|
+--------+------+--------+
|1001    |PLACED|CAD     |
|1002    |PLACED|CAD     |
+--------+------+--------+

>>> ALTER TABLE silver.orders ADD COLUMN channel STRING DEFAULT 'web'
   AnalysisException: [WRONG_COLUMN_DEFAULTS_FOR_DELTA_ALTER_TABLE_ADD_COLUMN_NOT_SUPPORTED] Failed to execute the command because DEFAULT values are not supported when adding new
>>> ALTER TABLE silver.orders ADD COLUMN channel STRING
OK
>>> ALTER TABLE silver.orders ALTER COLUMN channel SET DEFAULT 'web'
OK
>>> SELECT order_id, status, currency, channel FROM silver.orders ORDER BY order_id
+--------+------+--------+-------+
|order_id|status|currency|channel|
+--------+------+--------+-------+
|1001    |PLACED|CAD     |NULL   |
|1002    |PLACED|CAD     |NULL   |
|1003    |PLACED|CAD     |web    |
+--------+------+--------+-------+
```

Three lessons:

1. **Open-source Delta needs the `allowColumnDefaults` table feature** before a table may have defaults (first error). The Databricks ALTER TABLE page shows the same property, `TBLPROPERTIES('delta.feature.allowColumnDefaults' = 'supported')`, in one of its examples ([ALTER TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-table)), but the CREATE TABLE page does not mention it. Whether a Databricks workspace requires it is **not verified**; if `CREATE TABLE` with a `DEFAULT` fails there with the same error, add the property.
2. **You cannot add a column and its default in one step** on a Delta table. Both the ALTER TABLE page ("When you add a column to an existing Delta Lake table, you cannot define a `DEFAULT` value ... After adding a column, you can optionally define a default value for new rows using `ALTER COLUMN`") and the run agree.
3. **A default set later applies only to new rows**: 1001 and 1002 kept `NULL` in `channel`. Here the Databricks pages disagree with each other. The ALTER TABLE ... COLUMN page says under `SET DEFAULT` both "When you set a default using `ALTER COLUMN`, existing rows are not affected by that change" and "When you define the default for a newly added column, the default applies to all pre-existing rows" ([ALTER TABLE ... COLUMN clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-table-manage-column), last updated Oct 30, 2026), while its own `ADD COLUMN` note says a default cannot be defined when adding a Delta column, "All columns added to Delta tables are treated as `NULL` for existing rows", and a default defined afterwards "is only applied for new rows inserted into the table". The second `SET DEFAULT` sentence seems to describe formats where `ADD COLUMN ... DEFAULT` is allowed (the page lists `CSV`, `JSON`, `PARQUET` and `ORC` sources for `DEFAULT`); for Delta, the run shows existing rows staying `NULL`.

### Generated columns

A **generated column** is computed from other columns of the same row whenever a row is written, and stored like any other column. Its expression must be deterministic: literals, columns of the table, and built-in functions, but no aggregates, window functions, generators, subqueries or UDFs. Databricks marks the feature Public Preview ([Delta Lake generated columns](https://docs.databricks.com/aws/en/tables/features/generated-columns)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.events (
  order_id   INT,
  order_ts   TIMESTAMP,
  order_date DATE GENERATED ALWAYS AS (CAST(order_ts AS DATE)),
  order_year INT  GENERATED ALWAYS AS (YEAR(order_ts)))
USING DELTA;
INSERT INTO silver.events (order_id, order_ts) VALUES (1001, TIMESTAMP'2026-03-01 23:59:00');
INSERT INTO silver.events VALUES (1002, TIMESTAMP'2026-03-02 08:00:00', DATE'2026-03-02', 2026);
INSERT INTO silver.events VALUES (1003, TIMESTAMP'2026-03-02 08:00:00', DATE'2026-03-05', 2026);
CREATE TABLE silver.bad_gen (ts TIMESTAMP,
  loaded TIMESTAMP GENERATED ALWAYS AS (current_timestamp())) USING DELTA;
```

```text
>>> INSERT INTO silver.events VALUES (1002, TIMESTAMP'2026-03-02 08:00:00', DATE'2026-03-02', 2026)
OK
>>> INSERT INTO silver.events VALUES (1003, TIMESTAMP'2026-03-02 08:00:00', DATE'2026-03-05', 2026)
   DeltaInvariantViolationException: [DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint Generated Column (order_date <=> CAST(order_ts AS DATE)) violated by row with values:
      - order_date : 20517
      - order_ts : 1772438400000000
>>> SELECT * FROM silver.events ORDER BY order_id
+--------+-------------------+----------+----------+
|order_id|order_ts           |order_date|order_year|
+--------+-------------------+----------+----------+
|1001    |2026-03-01 23:59:00|2026-03-01|2026      |
|1002    |2026-03-02 08:00:00|2026-03-02|2026      |
+--------+-------------------+----------+----------+

>>> CREATE TABLE silver.bad_gen (ts TIMESTAMP, loaded TIMESTAMP GENERATED ALWAYS AS (current_timestamp())) USING DELTA
   AnalysisException: [DELTA_UNSUPPORTED_EXPRESSION_GENERATED_COLUMN] current_timestamp() cannot be used in a generated column
```

You may supply a value, but it must agree with the expression: the page says it must satisfy `(<value> <=> <generation expression>) IS TRUE` or the write fails, and the error shows Delta enforcing exactly that as a `CHECK` constraint. (The numbers in the error are the internal forms of the date and timestamp.) A "load time" column therefore cannot be generated; use `DEFAULT current_timestamp()` or set it in the `SELECT`.

Generated columns were the classic way to partition by date when the data has a timestamp: `PARTITIONED BY (order_date)` with `order_date` generated from `order_ts`, and Delta derives partition filters from a filter on `order_ts` (section 20.5 shows it). With liquid clustering you do not need that trick; the clustering page says to "Use the original column as a clustering key, and don't create a generated column" ([Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering)).

### Identity columns

An **identity column** gives each new row a unique `BIGINT`, the usual surrogate key for a dimension (`customer_sk`). Two forms:

- `GENERATED ALWAYS AS IDENTITY`: the table always assigns the value; you cannot supply one.
- `GENERATED BY DEFAULT AS IDENTITY`: assigned when you do not supply a value.

Both take `(START WITH start INCREMENT BY step)`; both default to 1 and `step` cannot be 0 ([CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using), Databricks SQL and Databricks Runtime 10.4 LTS and above).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.customer_keys (
  customer_sk BIGINT GENERATED ALWAYS AS IDENTITY,
  customer_id INT,
  name        STRING)
USING DELTA;
INSERT INTO silver.customer_keys (customer_id, name) VALUES (7, 'Ana Ruiz'), (3, 'Bo Chen');
INSERT INTO silver.customer_keys (customer_id, name) VALUES (9, 'Cy Park');
INSERT INTO silver.customer_keys VALUES (100, 11, 'Dee Lowe');
UPDATE silver.customer_keys SET customer_sk = 50 WHERE customer_id = 9;
CREATE TABLE silver.bad_id (k INT GENERATED ALWAYS AS IDENTITY) USING DELTA;
```

```text
>>> SELECT * FROM silver.customer_keys ORDER BY customer_sk
+-----------+-----------+--------+
|customer_sk|customer_id|name    |
+-----------+-----------+--------+
|1          |7          |Ana Ruiz|
|2          |3          |Bo Chen |
|3          |9          |Cy Park |
+-----------+-----------+--------+

>>> INSERT INTO silver.customer_keys VALUES (100, 11, 'Dee Lowe')
   AnalysisException: [DELTA_IDENTITY_COLUMNS_EXPLICIT_INSERT_NOT_SUPPORTED] Providing values for GENERATED ALWAYS AS IDENTITY column customer_sk is not supported.
>>> UPDATE silver.customer_keys SET customer_sk = 50 WHERE customer_id = 9
   AnalysisException: [DELTA_IDENTITY_COLUMNS_UPDATE_NOT_SUPPORTED] UPDATE on IDENTITY column customer_sk is not supported.
>>> CREATE TABLE silver.bad_id (k INT GENERATED ALWAYS AS IDENTITY) USING DELTA
   UnsupportedOperationException: [DELTA_IDENTITY_COLUMNS_UNSUPPORTED_DATA_TYPE] DataType integer is not supported for IDENTITY columns.
```

`BY DEFAULT` with a start and a step, and what happens when you insert your own value:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.product_keys (
  product_sk BIGINT GENERATED BY DEFAULT AS IDENTITY (START WITH 100 INCREMENT BY 10),
  product_id INT)
USING DELTA;
INSERT INTO silver.product_keys (product_id) VALUES (1), (2);
INSERT INTO silver.product_keys VALUES (500, 3);                 -- our own value
INSERT INTO silver.product_keys (product_id) VALUES (4);
ALTER TABLE silver.product_keys ALTER COLUMN product_sk SYNC IDENTITY;
INSERT INTO silver.product_keys (product_id) VALUES (5);
```

```text
>>> SELECT * FROM silver.product_keys ORDER BY product_id
+----------+----------+
|product_sk|product_id|
+----------+----------+
|100       |1         |
|110       |2         |
|500       |3         |
|120       |4         |
+----------+----------+

>>> ALTER TABLE silver.product_keys ALTER COLUMN product_sk SYNC IDENTITY
OK
>>> SELECT * FROM silver.product_keys ORDER BY product_id
+----------+----------+
|product_sk|product_id|
+----------+----------+
|100       |1         |
|110       |2         |
|500       |3         |
|120       |4         |
|510       |5         |
+----------+----------+
```

After our manual 500, the generator carried on at 120: it does not look at the data. If it had kept going it would eventually produce 500 again. `SYNC IDENTITY` "evaluates the state and updates the metadata to be consistent with the actual data", so the next value became 510 ([ALTER TABLE ... COLUMN clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-table-manage-column)).

The rules from the generated columns page, all of which you should know:

- Values are "unique and increment in the direction of the specified step ... but are not guaranteed to be contiguous". Gaps are normal.
- Identity columns are `BIGINT` only.
- You cannot partition by an identity column, `UPDATE` it, or use `ALTER TABLE` to `ADD`, `REPLACE` or `CHANGE` one. A table that needs one must be created with it.
- CTAS cannot declare one: create the table, then `INSERT ... SELECT` (`ch20_02_columns.out`, section 6, shows the CTAS error and the two-step version).
- **"Declaring an identity column on a Delta Lake table disables concurrent transactions. Only use identity columns in use cases where concurrent writes to the target table aren't required."**

!!! warning "Identity columns and parallel writers"
    The last rule is the one that hurts in production. If two jobs (or two streams) append to the same dimension, an identity column makes them conflict. Alternatives: let one job own the writes, or derive a key from the business key (for example `xxhash64(customer_id)`, see [chapter 19](19-Function-Toolbox.md#1911-hashing-and-ids)), accepting a hash instead of a sequence.

!!! tip "In the interview"
    **"How do you create surrogate keys in Delta?"** `BIGINT GENERATED ALWAYS AS IDENTITY` in the `CREATE TABLE` (not CTAS: create the table, then `INSERT ... SELECT`). Values are unique but can have gaps, and declaring one disables concurrent transactions on the table, so one writer only. `BY DEFAULT` lets you load existing keys; run `ALTER COLUMN ... SYNC IDENTITY` afterwards so new values start above them. `monotonically_increasing_id()` is not a substitute: it is unique only within one DataFrame computation.

## 20.4 Constraints: CHECK, and keys that are not enforced
*Level: beginner.*

Databricks has two families of constraints ([Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints), last updated Nov 6, 2026):

- **Enforced**: `NOT NULL` and `CHECK`. "When a constraint is violated, the transaction fails with an error."
- **Informational**: `PRIMARY KEY`, `FOREIGN KEY` and `UNIQUE`. They "define relationships between fields in tables and aren't enforced."

All of them need Delta Lake.

### CHECK constraints

A `CHECK` constraint is added with `ALTER TABLE ... ADD CONSTRAINT name CHECK (condition)`, after the table exists. It is not part of `CREATE TABLE` on Databricks ("To add a check constraint to a Delta Lake table use ALTER TABLE after the table has been created", [CONSTRAINT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-constraint)), and the local engine refused an inline `CHECK` too.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.order_items (order_id INT, product_id INT, qty INT, unit_price DECIMAL(10,2)) USING DELTA;
INSERT INTO silver.order_items VALUES (1001, 3, 2, 29.95), (1002, 1, 0, 249.00);

ALTER TABLE silver.order_items ADD CONSTRAINT qty_positive CHECK (qty > 0);   -- existing row has qty 0
DELETE FROM silver.order_items WHERE qty = 0;
ALTER TABLE silver.order_items ADD CONSTRAINT qty_positive CHECK (qty > 0);
ALTER TABLE silver.order_items ADD CONSTRAINT price_ok CHECK (unit_price >= 0 AND unit_price < 10000);

INSERT INTO silver.order_items VALUES (1003, 2, -1, 39.95);
INSERT INTO silver.order_items VALUES (1003, 2, NULL, 39.95);
UPDATE silver.order_items SET qty = 0 WHERE order_id = 1001;
SHOW TBLPROPERTIES silver.order_items;
```

```text
>>> ALTER TABLE silver.order_items ADD CONSTRAINT qty_positive CHECK (qty > 0)
   AnalysisException: [DELTA_NEW_CHECK_CONSTRAINT_VIOLATION] 1 rows in spark_catalog.silver.order_items violate the new CHECK constraint (qty > 0)
>>> ALTER TABLE silver.order_items ADD CONSTRAINT qty_positive CHECK (qty > 0)
OK
>>> ALTER TABLE silver.order_items ADD CONSTRAINT price_ok CHECK (unit_price >= 0 AND unit_price < 10000)
OK
>>> INSERT INTO silver.order_items VALUES (1003, 2, -1, 39.95)
   DeltaInvariantViolationException: [DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint qty_positive (qty > 0) violated by row with values:
      - qty : -1
>>> INSERT INTO silver.order_items VALUES (1003, 2, NULL, 39.95)
   DeltaInvariantViolationException: [DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint qty_positive (qty > 0) violated by row with values:
      - qty : null
>>> UPDATE silver.order_items SET qty = 0 WHERE order_id = 1001
   DeltaInvariantViolationException: [DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint qty_positive (qty > 0) violated by row with values:
      - qty : 0
+------------------------------+--------------------------------------+
|key                           |value                                 |
+------------------------------+--------------------------------------+
|delta.constraints.price_ok    |unit_price >= 0 AND unit_price < 10000|
|delta.constraints.qty_positive|qty > 0                               |
+------------------------------+--------------------------------------+
```

Points that come up in interviews:

- **Existing rows are checked first.** "Delta Lake verifies the validity of the check constraint against both new and existing data. If any existing row violates the constraint an error will be raised" ([ADD CONSTRAINT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-table-add-constraint)). Clean up (or quarantine) the bad rows, then add the constraint.
- **`NULL` fails a `CHECK`.** In standard SQL a `CHECK` whose condition is unknown (`NULL > 0`) passes. In Databricks "For a `CHECK` constraint to be satisfied in Databricks it must evaluate to `true`", and the run confirms that `qty = NULL` was rejected. Write `CHECK (qty IS NULL OR qty > 0)` if `NULL` is allowed.
- **Every write is checked**, `UPDATE` and `MERGE` included, and the whole statement fails: no partial writes, no "drop the bad row". For "keep the good rows, set the bad ones aside", use the quarantine pattern ([chapter 9](09-Building-Silver.md#95-the-quarantine-pattern)) or pipeline expectations ([chapter 14](14-Data-Quality-and-CDC.md)).
- Constraints are stored as table properties named `delta.constraints.<name>`, so `SHOW TBLPROPERTIES` and `DESCRIBE DETAIL` show them. `ALTER TABLE ... DROP CONSTRAINT [IF EXISTS] name` removes one.
- The expression may use deterministic built-in functions only (no UDFs, aggregates, window functions or generators), and the table's default collation must be `UTF8_BINARY` when the constraint is added.

### Informational PRIMARY KEY, FOREIGN KEY and UNIQUE

Key constraints document the model and help the optimizer, but Databricks does not check them: "Databricks does not enforce primary key, foreign key, or unique constraints. Confirm key constraints before adding a primary key, foreign key, or unique constraint. Your ingest process may provide such assurance, or you can run checks against your data" ([CONSTRAINT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-constraint), last updated Oct 29, 2026). They exist only in Unity Catalog ("not supported for tables in the `hive_metastore` catalog"), and the open-source engine refused them with `[UNSUPPORTED_FEATURE.TABLE_OPERATION] ... does not support table constraint` (`ch20_02_columns.out`, section 8).

*Databricks only, not run here. Syntax from [CONSTRAINT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-constraint) and [Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints).*

```sql
CREATE TABLE shop.silver.customers (
  customer_id INT NOT NULL,
  name        STRING,
  email       STRING,
  CONSTRAINT customers_pk PRIMARY KEY (customer_id));

CREATE TABLE shop.silver.orders (
  order_id    INT NOT NULL PRIMARY KEY,
  customer_id INT,
  order_ts    TIMESTAMP,
  amount      DECIMAL(10,2),
  CONSTRAINT orders_customers_fk FOREIGN KEY (customer_id) REFERENCES shop.silver.customers);

-- or afterwards; a primary key before the foreign key that references it
ALTER TABLE shop.silver.customers ADD CONSTRAINT customers_email_uq UNIQUE (email);
ALTER TABLE shop.silver.customers DROP CONSTRAINT customers_email_uq;
```

What each piece means, from the CONSTRAINT clause page:

- A table has at most one primary key; its columns are "implicitly defined as `NOT NULL`" (the `ADD CONSTRAINT` page instead asks for columns already "defined as `NOT NULL`", so declare them `NOT NULL` and both readings are satisfied).
- A foreign key references the parent's primary key (or, in Databricks Runtime 18.2 and above, a `UNIQUE` constraint); without a column list it maps by position to the parent key. Types must match.
- `UNIQUE` (Databricks Runtime 18.2 and above, Unity Catalog only): a table can have several; `NULL`s count as distinct.
- Options: `NOT ENFORCED`, `DEFERRABLE`, `INITIALLY DEFERRED` (all implied), `RELY` / `NORELY` (default `NORELY`). With `RELY`, "Databricks may exploit the constraint to rewrite and optimize queries. It is the user's responsibility to ensure the constraint is satisfied. Relying on a constraint that is not satisfied may lead to incorrect query results." Those optimizations need pro or serverless SQL warehouses or serverless compute.
- `UNDROP` does not bring key constraints back (section 20.10), and renaming a key column drops keys that use it.

The pages disagree about the release status of key constraints. The Constraints page says primary and foreign keys are "available for Unity Catalog and Delta Lake tables in Databricks Runtime 13.3 LTS and above. GA in Databricks Runtime 15.2 and above", with `UNIQUE` in Public Preview in 18.2 and above. The ADD CONSTRAINT clause page (last updated Sep 11, 2026) still puts a "Public Preview" banner on the whole `key_constraint` clause, "Applies to: Databricks SQL Databricks Runtime 11.3 LTS and above". The newer page (Nov 6, 2026) is probably the current state; in an interview, "informational, not enforced, Unity Catalog only" is the safe answer.

!!! tip "In the interview"
    **"Does Databricks enforce primary keys?"** No. `PRIMARY KEY`, `FOREIGN KEY` and `UNIQUE` are informational: duplicates and orphans are accepted. They document the model for BI tools and, with `RELY`, let the optimizer skip work such as redundant `DISTINCT`s or joins, which gives wrong answers if the data breaks them. Enforced constraints are `NOT NULL` and `CHECK`; uniqueness is your pipeline's job (deduplicate before `MERGE`, check with a `GROUP BY ... HAVING count(*) > 1` test).

## 20.5 Data layout: partitioning versus liquid clustering
*Level: intermediate.*

A query such as "all orders of customer 7" should read only the files that can contain customer 7. Delta keeps minimum and maximum values per column for every data file and skips files whose range cannot match ([chapter 4](04-Delta-Lake.md)). How the rows are spread over the files decides how much can be skipped, and the table DDL gives two ways to control it:

- **Partitioning** (`PARTITIONED BY`): one folder per distinct value of the partition columns. A filter on a partition column skips whole folders. The columns are fixed when the table is created.
- **Liquid clustering** (`CLUSTER BY`): no folders. You name up to four clustering keys, and `OPTIMIZE` (or predictive optimization on Databricks) rewrites files so that rows with nearby key values sit in the same files, which makes the per-file ranges narrow. The keys can be changed later.

Databricks' position is clear: "Liquid clustering is a data layout optimization technique that replaces table partitioning and `ZORDER`" ([Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering)). This section is about the DDL. Why clustering is faster, and how to tune file sizes and `OPTIMIZE`, is in [chapter 22](22-Performance-Tuning.md).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 330" role="img" aria-label="Left: a table partitioned by order_date has one folder per date, each with its own files. A filter on order_date reads one folder. Right: a table clustered by customer_id has no folders; OPTIMIZE groups rows so that each file covers a narrow range of customer_id, and a filter on customer_id = 7 reads only the file whose range contains 7.">
<defs><marker id="a202" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g font-size="13" fill="currentColor">
<text x="20" y="24" font-weight="bold">PARTITIONED BY (order_date)</text>
<text x="340" y="24" font-weight="bold">CLUSTER BY (customer_id)</text>
<rect x="20" y="40" width="280" height="56" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="30" y="60">order_date=2026-03-01/</text>
<text x="30" y="82">part-0001.parquet  part-0002.parquet</text>
<rect x="20" y="106" width="280" height="56" rx="5" fill="none" stroke="currentColor" stroke-dasharray="5 4"/>
<text x="30" y="126">order_date=2026-03-02/</text>
<text x="30" y="148">part-0003.parquet</text>
<rect x="20" y="172" width="280" height="56" rx="5" fill="none" stroke="currentColor" stroke-dasharray="5 4"/>
<text x="30" y="192">order_date=2026-03-03/</text>
<text x="30" y="214">part-0004.parquet</text>
<text x="20" y="252">WHERE order_date = '2026-03-01'</text>
<text x="20" y="270">reads one folder (solid box)</text>
<text x="20" y="296">one folder per value; fixed keys;</text>
<text x="20" y="314">many values, many small files</text>
<rect x="340" y="40" width="280" height="40" rx="5" fill="none" stroke="currentColor" stroke-dasharray="5 4"/>
<text x="350" y="65">file A   customer_id 1 to 3</text>
<rect x="340" y="90" width="280" height="40" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="350" y="115">file B   customer_id 4 to 7</text>
<rect x="340" y="140" width="280" height="40" rx="5" fill="none" stroke="currentColor" stroke-dasharray="5 4"/>
<text x="350" y="165">file C   customer_id 8 to 9</text>
<line x1="480" y1="200" x2="480" y2="134" stroke="currentColor" marker-end="url(#a202)"/>
<text x="340" y="218">WHERE customer_id = 7</text>
<text x="340" y="236">skips A and C by their min/max values</text>
<text x="340" y="270">no folders; OPTIMIZE groups rows by key;</text>
<text x="340" y="288">up to four keys; change them with</text>
<text x="340" y="306">ALTER TABLE ... CLUSTER BY</text>
</g>
</svg>
<figcaption>Figure 20.2. Partitioning splits the table into folders by value; liquid clustering keeps one folder and narrows each file's range of the clustering keys. Both let a filter skip data; only clustering lets you change the keys later.</figcaption>
</figure>

### Partitioning, and the generated date column

The classic pattern partitions orders by a date that is generated from the timestamp, so that writers do not have to fill it:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.orders_part (
  order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING,
  amount DECIMAL(10,2), currency STRING,
  order_date DATE GENERATED ALWAYS AS (CAST(order_ts AS DATE)))
USING DELTA
PARTITIONED BY (order_date);

INSERT INTO silver.orders_part (order_id, customer_id, order_ts, status, amount, currency) VALUES
  (1001, 7, TIMESTAMP'2026-03-01 10:15:00', 'PLACED',    59.90, 'CAD'),
  (1002, 3, TIMESTAMP'2026-03-01 11:02:00', 'SHIPPED',  120.00, 'CAD'),
  (1003, 7, TIMESTAMP'2026-03-02 09:40:00', 'PLACED',    15.50, 'USD'),
  (1004, 9, TIMESTAMP'2026-03-03 16:20:00', 'CANCELLED', 42.00, 'CAD');

SELECT partitionColumns, clusteringColumns, numFiles FROM (DESCRIBE DETAIL silver.orders_part);
SELECT order_id, order_date FROM silver.orders_part WHERE order_ts >= '2026-03-02' ORDER BY order_id;
EXPLAIN SELECT order_id FROM silver.orders_part WHERE order_ts >= '2026-03-02';
```

```text
+----------------+-----------------+--------+
|partitionColumns|clusteringColumns|numFiles|
+----------------+-----------------+--------+
|[order_date]    |[]               |3       |
+----------------+-----------------+--------+

folders: ['order_date=2026-03-01', 'order_date=2026-03-02', 'order_date=2026-03-03']
+--------+----------+
|order_id|order_date|
+--------+----------+
|1003    |2026-03-02|
|1004    |2026-03-03|
+--------+----------+

PartitionFilters in plan: PartitionFilters: [((order_date#1625 >= 2026-03-02) OR isnull((order_date#1625 >= 2026-03-02)))]
```

(The script reads `DESCRIBE DETAIL` with `selectExpr`, lists the table folder with Python, and keeps only the `PartitionFilters` part of the plan.) Three dates gave three folders and three files. The query filters on `order_ts`, not on `order_date`, yet the plan has a partition filter on `order_date`: "When you partition a table using a generated column and query on the base column, Delta Lake automatically derives partition filters if possible" ([Delta Lake generated columns](https://docs.databricks.com/aws/en/tables/features/generated-columns)). The `OR isnull(...)` part keeps any partition whose value is `NULL`, so the derived filter can never drop a row that the real filter would keep.

**Where the partition column goes in a CTAS.** The Databricks pages say that a partition column is moved to the end of a Delta table when the table has no column list: "For Delta tables, if you omit the table definition, Databricks places partitioning columns at the end of the table, even if you list them earlier in the column specification" ([CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using)), and "Unless you define a Delta Lake table partitioning columns referencing the columns in the column specification are always moved to the end of the table" ([Partitions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-partition)). The open-source run did not move it:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.orders_by_status USING DELTA PARTITIONED BY (status) AS
SELECT order_id, status, amount FROM silver.orders_part;

CREATE TABLE silver.p2 (order_id INT, status STRING, amount DECIMAL(10,2))
USING DELTA PARTITIONED BY (status);
```

```text
CTAS column order: ['order_id', 'status', 'amount']
column-list order: ['order_id', 'status', 'amount']
```

Not verified on Databricks. If column order matters to a consumer (positional `INSERT`, CSV exports), select the columns by name instead of relying on `SELECT *`.

### Liquid clustering

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.orders (
  order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING,
  amount DECIMAL(10,2), currency STRING)
USING DELTA
CLUSTER BY (customer_id);
INSERT INTO silver.orders VALUES ...;            -- the same four orders

DESCRIBE DETAIL silver.orders;                   -- partitionColumns, clusteringColumns, protocol, features
ALTER TABLE silver.orders CLUSTER BY (customer_id, order_ts);
OPTIMIZE silver.orders;
DESCRIBE HISTORY silver.orders;
ALTER TABLE silver.orders CLUSTER BY NONE;
```

```text
+----------------+-----------------+----------------+----------------+
|partitionColumns|clusteringColumns|minReaderVersion|minWriterVersion|
+----------------+-----------------+----------------+----------------+
|[]              |[customer_id]    |1               |7               |
+----------------+-----------------+----------------+----------------+

tableFeatures: ['appendOnly', 'clustering', 'domainMetadata', 'invariants']
>>> ALTER TABLE silver.orders CLUSTER BY (customer_id, order_ts)
OK
+-----------------------+
|clusteringColumns      |
+-----------------------+
|[customer_id, order_ts]|
+-----------------------+

>>> OPTIMIZE silver.orders
OK
+-------+------------+-----------------------------------------------------------------------------------------------------------+
|version|operation   |operationParameters                                                                                        |
+-------+------------+-----------------------------------------------------------------------------------------------------------+
|0      |CREATE TABLE|{partitionBy -> [], clusterBy -> ["customer_id"], description -> NULL, isManaged -> true, properties -> {}}|
|1      |WRITE       |{mode -> Append, partitionBy -> []}                                                                        |
|2      |CLUSTER BY  |{oldClusteringColumns -> customer_id, newClusteringColumns -> customer_id,order_ts}                        |
|3      |OPTIMIZE    |{clusterBy -> ["customer_id","order_ts"], predicate -> [], auto -> false, isFull -> false, zOrderBy -> []} |
+-------+------------+-----------------------------------------------------------------------------------------------------------+

>>> ALTER TABLE silver.orders CLUSTER BY NONE
OK
+-----------------+
|clusteringColumns|
+-----------------+
|[]               |
+-----------------+
```

What the output shows:

- **Changing keys is a metadata commit** (version 2, `CLUSTER BY`). "When you change clustering keys, subsequent `OPTIMIZE` and write operations use the new clustering approach, but existing data is not rewritten" (clustering page). `CLUSTER BY NONE` likewise "does not rewrite clustered data, but prevents future `OPTIMIZE` operations from using clustering keys".
- **`OPTIMIZE` is incremental** (`isFull -> false`): it "only rewrites data as necessary to accommodate data that needs clustering". To recluster everything after a key change, run `OPTIMIZE ... FULL` (Databricks Runtime 16.0 and above), or `OPTIMIZE ... FULL WHERE <predicate>` for a slice (Databricks Runtime 18.1 and above).
- **Clustering changes the protocol.** Locally the table needed writer version 7 with the `clustering` and `domainMetadata` features (the keys are stored as domain metadata in the log). On Databricks expect more: "Delta Lake tables with liquid clustering enabled use Delta writer version 7 and reader version 3. Delta clients that don't support these protocols cannot read these tables. You can't downgrade table protocol versions" (clustering page), and "enabling liquid clustering automatically enables checkpoint V2" ([Delta Lake feature compatibility and protocols](https://docs.databricks.com/aws/en/tables/features/feature-compatibility)). Check this before you cluster a table that an external tool reads.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from delta.tables import DeltaTable

src.writeTo("silver.orders_lc0").using("delta").clusterBy("customer_id").create()
src.write.format("delta").clusterBy("customer_id").saveAsTable("silver.orders_lc1")
(DeltaTable.create(spark).tableName("silver.orders_lc2")
    .addColumn("order_id", "INT").addColumn("customer_id", "INT").addColumn("order_date", "DATE")
    .clusterBy("order_date", "customer_id").execute())

spark.sql("ALTER TABLE silver.orders_lc CLUSTER BY (order_date)")   # was CLUSTER BY (customer_id)
spark.sql("OPTIMIZE silver.orders_lc FULL")
```

```text
writeTo().clusterBy(): AnalysisException: [DELTA_OPERATION_NOT_ALLOWED] Operation not allowed: `Partitioning by expressions` is not supported for Delta tables
write.clusterBy().saveAsTable(): AnalysisException: [DELTA_OPERATION_NOT_ALLOWED] Operation not allowed: `Partitioning by expressions` is not supported for Delta tables
DeltaTable builder clusterBy: ['order_date', 'customer_id']
>>> OPTIMIZE silver.orders_lc FULL
OK
+-------+------+--------------+
|version|isFull|clusterBy     |
+-------+------+--------------+
|3      |true  |["order_date"]|
+-------+------+--------------+
```

(`src` is a DataFrame of the four orders; the script wraps each call in `try` and prints the error.) Databricks documents all three Python forms, `df.write.clusterBy(...)`, `df.writeTo(...).using("delta").clusterBy(...).create()` ("available in Databricks Runtime 14.2 and above") and the `DeltaTable` builder; open-source Delta 4.4.1 accepted only the builder. The clustering page adds that with DataFrame APIs "you can only specify clustering columns during table creation or when using `overwrite` mode"; an append cannot change them. `OPTIMIZE ... FULL` ran here and recorded `isFull -> true` with the new key.

### What clustering does not allow

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> CREATE TABLE silver.bad1 (...) USING DELTA PARTITIONED BY (status) CLUSTER BY (customer_id)
   ParseException: Operation not allowed: Clustering and partitioning cannot both be specified. Please remove PARTITIONED BY if you want to create a Delta table with clustering. (line 1, pos 167)
>>> ALTER TABLE silver.orders_part CLUSTER BY (customer_id)
   AnalysisException: [DELTA_ALTER_TABLE_CLUSTER_BY_ON_PARTITIONED_TABLE_NOT_ALLOWED] ALTER TABLE CLUSTER BY cannot be applied to a partitioned table.
>>> CREATE TABLE silver.bad2 (a INT, b INT, c INT, d INT, e INT) USING DELTA CLUSTER BY (a, b, c, d, e)
   AnalysisException: [DELTA_CLUSTER_BY_INVALID_NUM_COLUMNS] CLUSTER BY supports up to 4 clustering columns, but the table has 5 clustering columns. Please remove the extra clustering columns.
>>> CREATE TABLE silver.bad3 (id INT, tags ARRAY<STRING>) USING DELTA CLUSTER BY (tags)
   AnalysisException: [DELTA_CLUSTERING_COLUMNS_DATATYPE_NOT_SUPPORTED] CLUSTER BY is not supported because the following column(s): tags : ARRAY<STRING> don't support data skipping.
>>> CREATE TABLE silver.orders_auto (...) USING DELTA CLUSTER BY AUTO
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'AUTO': missing '('. SQLSTATE: 42601 (line 1, pos 161)
>>> ALTER TABLE silver.orders_part REPLACE PARTITIONED BY WITH CLUSTER BY (customer_id)
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'PARTITIONED'. SQLSTATE: 42601 (line 1, pos 39)
```

(The column lists are shortened here; the `.out` file has the full statements.) The first four are rules on both engines: clustering "is not compatible with partitioning or `ZORDER`", "You can specify **up to four clustering keys**", and "Clustering keys must be columns that have statistics collected. By default, Delta Lake tables collect statistics for the first 32 columns" (clustering page). A key that is column 40 of a wide table therefore needs `delta.dataSkippingNumIndexedCols` (or `delta.dataSkippingStatsColumns`) changed first. The last two statements are Databricks features that the open-source parser does not know.

### Automatic clustering and converting a partitioned table

*Databricks only, not run here. Syntax from [Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering) and [CLUSTER BY clause (TABLE)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-cluster-by).*

```sql
-- Databricks chooses (and later changes) the keys from the query history
CREATE OR REPLACE TABLE shop.silver.orders (order_id INT, customer_id INT, order_ts TIMESTAMP,
  status STRING, amount DECIMAL(10,2), currency STRING) CLUSTER BY AUTO;
ALTER TABLE shop.silver.orders CLUSTER BY AUTO;

-- recluster only the files of a slice after a key change (18.1+)
OPTIMIZE shop.silver.orders FULL WHERE order_ts >= '2026-01-01';

-- convert a partitioned table in place (18.1+); the partition columns become hierarchical keys
ALTER TABLE shop.silver.orders_part REPLACE PARTITIONED BY WITH CLUSTER BY (order_date, customer_id);
```

The facts behind these lines, all from the clustering page unless noted:

- `CLUSTER BY AUTO` needs Databricks Runtime 15.4 LTS and above and works only on Unity Catalog managed tables, through predictive optimization. "Running `CREATE OR REPLACE table_name` without `CLUSTER BY AUTO` turns off automatic clustering and does not preserve clustering columns." The `AUTO` keyword is "Applies to: Databricks SQL Databricks Runtime 15.4 and above" on the [CLUSTER BY clause (TABLE)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-cluster-by) page.
- `REPLACE PARTITIONED BY WITH CLUSTER BY` (Databricks Runtime 18.1 and above) converts in place for managed and external tables; after it "the table supports reads with Databricks Runtime 13.3 LTS and above". Before 18.1 the way out of partitioning was to rebuild the table with a CTAS that has `CLUSTER BY`.
- Hierarchical clustering (Databricks Runtime 17.1 and above) puts some keys first through the `delta.liquid.hierarchicalClusteringColumns` property; a conversion sets the old partition columns as hierarchical keys.

**The pages disagree on the version.** The [CLUSTER BY clause (TABLE)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-cluster-by) page (last updated Oct 30, 2026) says "Applies to: Databricks SQL Databricks Runtime 13.3 LTS and above". The [clustering page](https://docs.databricks.com/aws/en/tables/clustering) (last updated Nov 2, 2026) says "Liquid clustering is generally available for Delta Lake tables with Databricks Runtime 15.4 LTS and above". Both can be true: the clause exists from 13.3 LTS, and general availability starts at 15.4 LTS. In an interview, "15.4 LTS and above" is the answer for production use.

### Which one to choose

The partitioning page gives rules of thumb ([When to partition tables on Databricks](https://docs.databricks.com/aws/en/tables/partitions), last updated Sep 11, 2026):

- "With less than 1 TB of data, don't partition."
- "With more than 1 TB to 100 TB of data, use liquid clustering instead of partitioning."
- With 100 TB or more, partitioning "might improve performance, but Databricks recommends using liquid clustering first".
- If you do partition, "verify that each partition contains at least 1 GB of data".
- An unpartitioned, unclustered Delta table is not unordered: Databricks "automatically clusters data in unpartitioned tables by ingestion time".

For Red Rock Supply's `orders`, which is small and filtered by customer and date, that means `CLUSTER BY (customer_id, order_ts)` or `CLUSTER BY AUTO`, not partitions. With clustering there is no need for the generated `order_date`: the clustering page says to "Use the original column as a clustering key, and don't create a generated column".

!!! tip "In the interview"
    **"Partitioning or liquid clustering for a new table?"** Liquid clustering. Partitioning fixes the key at creation, makes one folder per value (small files when the column has many values) and only helps filters on that column. Clustering keys (up to four) can change with `ALTER TABLE ... CLUSTER BY`, new keys apply to new writes and `OPTIMIZE`, and `OPTIMIZE FULL` reclusters old data. Databricks' own guidance: do not partition below 1 TB; between 1 and 100 TB use clustering. The cost is the protocol upgrade (writer 7, reader 3 on Databricks), which older external readers may not support.

## 20.6 Table properties and table features
*Level: intermediate.*

`TBLPROPERTIES` is a key-value map stored with the table. Keys that start with `delta.` change how Delta behaves; any other key is a free label for your own use (an owner, a quality tier). Set them in `CREATE TABLE ... TBLPROPERTIES (...)`, change them with `ALTER TABLE ... SET TBLPROPERTIES`, remove them with `UNSET TBLPROPERTIES`, and read them with `SHOW TBLPROPERTIES`. One rule matters in production: "All operations that set or update table properties conflict with other concurrent write operations, causing them to fail" ([Table properties reference](https://docs.databricks.com/aws/en/tables/table-properties), last updated Nov 5, 2026). Change properties when no job is writing.

The properties a data engineer sets most often, with the defaults from that page:

| Property | What it does | Default |
| --- | --- | --- |
| `delta.appendOnly` | `true` blocks `UPDATE` and `DELETE` | `false` |
| `delta.enableChangeDataFeed` | records row-level changes for `table_changes` and streaming | `false` |
| `delta.enableDeletionVectors` | marks deleted rows in a side file instead of rewriting the data file | depends on workspace admin settings and runtime version |
| `delta.columnMapping.mode` | `name` or `id` allows renaming and dropping columns without rewrites | `none` |
| `delta.enableTypeWidening` | allows widening column types without rewrites | `false` |
| `delta.logRetentionDuration` | how long history (the log) is kept | `interval 30 days` |
| `delta.deletedFileRetentionDuration` | how long removed data files are kept before `VACUUM` may delete them | `interval 1 week` |
| `delta.dataSkippingNumIndexedCols` | how many leading columns get statistics | `32` |
| `delta.isolationLevel` | `Serializable` or `WriteSerializable` | `WriteSerializable` |

### A label, and a property that changes behavior

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.order_events (order_id INT, status STRING, event_ts TIMESTAMP)
USING DELTA
TBLPROPERTIES ('delta.appendOnly' = 'true', 'owner_team' = 'data-eng');
INSERT INTO silver.order_events VALUES (1001, 'PLACED', TIMESTAMP'2026-03-01 10:15:00');
DELETE FROM silver.order_events WHERE order_id = 1001;
UPDATE silver.order_events SET status = 'X';
SHOW TBLPROPERTIES silver.order_events;

ALTER TABLE silver.order_events SET TBLPROPERTIES ('delta.appendOnly' = 'false');
ALTER TABLE silver.order_events UNSET TBLPROPERTIES ('owner_team');
DELETE FROM silver.order_events WHERE order_id = 1001;
SHOW TBLPROPERTIES silver.order_events;
```

```text
>>> DELETE FROM silver.order_events WHERE order_id = 1001
   UnsupportedOperationException: [DELTA_CANNOT_MODIFY_APPEND_ONLY] This table is configured to only allow appends. If you would like to permit updates or deletes, use 'ALTER TABLE null SET TBLPROPERTIES (delta.appendOnly=false)'.
>>> UPDATE silver.order_events SET status = 'X'
   UnsupportedOperationException: [DELTA_CANNOT_MODIFY_APPEND_ONLY] This table is configured to only allow appends. If you would like to permit updates or deletes, use 'ALTER TABLE null SET TBLPROPERTIES (delta.appendOnly=false)'.
+----------------------+--------+
|key                   |value   |
+----------------------+--------+
|delta.appendOnly      |true    |
|delta.minReaderVersion|1       |
|delta.minWriterVersion|2       |
|owner_team            |data-eng|
+----------------------+--------+

>>> DELETE FROM silver.order_events WHERE order_id = 1001
OK
+----------------------+-----+
|key                   |value|
+----------------------+-----+
|delta.appendOnly      |false|
|delta.minReaderVersion|1    |
|delta.minWriterVersion|2    |
+----------------------+-----+
```

(The script hides `delta.feature.*` keys. The `null` in the message is where the open-source engine should have printed the table name.) An append-only table suits an event log or a bronze table that must never lose rows. The protocol versions show up as properties too: they are what `DESCRIBE DETAIL` reports as `minReaderVersion` and `minWriterVersion`.

To give every new table in a session the same property, Databricks reads `spark.databricks.delta.properties.defaults.<conf>`:

*Databricks only, not run here. Syntax from [Table properties reference](https://docs.databricks.com/aws/en/tables/table-properties).*

```sql
SET spark.databricks.delta.properties.defaults.appendOnly = true;
```

### Properties that are table features

Some properties switch on a **table feature**: a capability that readers and writers must understand, recorded in the table's protocol. Turning one on upgrades the protocol, and the upgrade is one-way: "Turning off a table feature does not result in a protocol downgrade. You must drop the feature to fully remove it from the protocol. Not all table features can be dropped" ([Delta Lake feature compatibility and protocols](https://docs.databricks.com/aws/en/tables/features/feature-compatibility)). Change data feed and deletion vectors are the two most common:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.customers (customer_id INT, name STRING, city STRING)
USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true', 'delta.enableDeletionVectors' = 'true');
INSERT INTO silver.customers VALUES (3, 'Bo Chen', 'Flagstaff'), (7, 'Ana Ruiz', 'Moab'), (9, 'Cy Park', 'Bend');
UPDATE silver.customers SET city = 'Sedona' WHERE customer_id = 7;
DELETE FROM silver.customers WHERE customer_id = 9;

SELECT customer_id, city, _change_type, _commit_version
FROM table_changes('silver.customers', 1)
ORDER BY _commit_version, customer_id, _change_type;
```

```text
+-----------+---------+----------------+---------------+
|customer_id|city     |_change_type    |_commit_version|
+-----------+---------+----------------+---------------+
|3          |Flagstaff|insert          |1              |
|7          |Moab     |insert          |1              |
|9          |Bend     |insert          |1              |
|7          |Sedona   |update_postimage|2              |
|7          |Moab     |update_preimage |2              |
|9          |Bend     |delete          |3              |
+-----------+---------+----------------+---------------+

+-------+------------+---------+-------------+
|version|operation   |dvs_added|files_removed|
+-------+------------+---------+-------------+
|0      |CREATE TABLE|NULL     |NULL         |
|1      |WRITE       |NULL     |NULL         |
|2      |UPDATE      |1        |1            |
|3      |DELETE      |0        |1            |
+-------+------------+---------+-------------+

protocol: 3 7 ['appendOnly', 'changeDataFeed', 'deletionVectors', 'invariants']
```

- **Change data feed.** `table_changes(table_str, start [, end])` returns the table's columns plus `_change_type` (`insert`, `update_preimage`, `update_postimage`, `delete`), `_commit_version` and `_commit_timestamp` ([table_changes table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/table_changes)). An update gives two rows, the old and the new values. The feed "only records changes that occur after change data feed was enabled", and "The `VACUUM` command deletes change data files" ([Use change data feed on Databricks](https://docs.databricks.com/aws/en/tables/features/change-data-feed)), so it is not a permanent audit log. Chapter [14](14-Data-Quality-and-CDC.md) uses it to feed silver and gold incrementally.
- **Deletion vectors.** The `UPDATE` added one deletion vector: instead of rewriting the data file without Ana's old row, Delta wrote the new row to a new file and marked the old row as deleted in a small side file. The data file is logically replaced, which is why it also counts as removed. A second run that printed more metrics (`ch20_07_extras`, section 2) shows the `DELETE` with `numDeletionVectorsRemoved` 1, one file removed and none added: the file that held customer 9 had no live row left, so it was dropped whole, together with its deletion vector. To rewrite the files physically, run `REORG TABLE ... APPLY (PURGE)` ([Deletion vectors in Databricks](https://docs.databricks.com/aws/en/tables/features/deletion-vectors)). Whether new tables get deletion vectors by default depends on the workspace: "Default settings vary by region".
- **Protocol.** The table moved to reader version 3 and writer version 7 with the `changeDataFeed` and `deletionVectors` features, so a client that does not support deletion vectors can no longer read it.
- **Retention.** History is kept for `delta.logRetentionDuration` (30 days) and removed files for `delta.deletedFileRetentionDuration` (7 days). Time travel needs both the log entry and the files, so it works for 7 days by default. [Chapter 4](04-Delta-Lake.md) has the details.

Column mapping and type widening are also table features; they come with the `ALTER TABLE` statements they enable in section 20.7.

!!! tip "In the interview"
    **"What is a table feature, and why should I care before enabling one?"** Features such as change data feed, deletion vectors, column mapping, type widening and liquid clustering are recorded in the table's protocol (`minReaderVersion`, `minWriterVersion`, `tableFeatures` in `DESCRIBE DETAIL`). Enabling one upgrades the protocol for good, so every engine that reads the table (an older runtime, an external Spark, a BI connector) must support it. Removing one takes `ALTER TABLE ... DROP FEATURE`, and not every feature can be dropped. Also, any property change conflicts with concurrent writes, so schedule it.

## 20.7 ALTER TABLE: columns, types, names and tags
*Level: intermediate.*

Sources change: the shop adds a sales channel, an ID outgrows `INT`, a column gets a clearer name. `ALTER TABLE` handles each of these, and the question an interviewer asks is always the same: **does this rewrite the data, and does it need a table feature?**

| Change | Statement | Rewrites data? | Needs |
| --- | --- | --- | --- |
| Add a column | `ADD COLUMN(S) ... FIRST` or `... AFTER col` | no; old rows read `NULL` here (defaults: section 20.3) | nothing |
| Move a column, change its comment | `ALTER COLUMN c FIRST` or `ALTER COLUMN c AFTER col`, `ALTER COLUMN c COMMENT '...'` | no | nothing |
| Widen a type (`INT` to `BIGINT`, more decimal precision) | `ALTER COLUMN c TYPE t` | no | type widening |
| Any other type change | rewrite the table (`CREATE OR REPLACE TABLE ... AS SELECT CAST(...)`) | yes | nothing |
| Rename or drop a column | `RENAME COLUMN`, `DROP COLUMN(S)` | no | column mapping |
| Rename the table | `RENAME TO` | no | nothing |

### Adding, moving and commenting columns

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
ALTER TABLE silver.orders ADD COLUMNS (
  channel STRING COMMENT 'web or store' AFTER status,
  row_id  BIGINT FIRST);
ALTER TABLE silver.orders ALTER COLUMN row_id AFTER currency;
ALTER TABLE silver.orders ALTER COLUMN amount COMMENT 'order total, tax included';
ALTER TABLE silver.orders ALTER COLUMN status COMMENT 'lifecycle state', currency COMMENT 'ISO 4217';
DESCRIBE TABLE silver.orders;
```

```text
after ADD COLUMNS: ['row_id', 'order_id', 'customer_id', 'order_ts', 'status', 'channel', 'amount', 'currency']
>>> ALTER TABLE silver.orders ALTER COLUMN status COMMENT 'lifecycle state', currency COMMENT 'ISO 4217'
OK
+-----------+-------------+-------------------------+
|col_name   |data_type    |comment                  |
+-----------+-------------+-------------------------+
|order_id   |int          |NULL                     |
|customer_id|int          |NULL                     |
|order_ts   |timestamp    |NULL                     |
|status     |string       |lifecycle state          |
|channel    |string       |web or store             |
|amount     |decimal(10,2)|order total, tax included|
|currency   |string       |ISO 4217                 |
|row_id     |bigint       |NULL                     |
+-----------+-------------+-------------------------+
```

`FIRST` and `AFTER` place a new column; `ALTER COLUMN ... AFTER` moves an existing one. Several columns can be changed in one `ALTER COLUMN` statement, separated by commas. Existing rows read `NULL` in the new columns. Section 20.3 shows what happens when the added column has a `DEFAULT` (and where the docs disagree); to fill old rows, run an `UPDATE`.

### Changing a column type: type widening

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
ALTER TABLE silver.orders ALTER COLUMN customer_id TYPE BIGINT;     -- before enabling the feature
ALTER TABLE silver.orders SET TBLPROPERTIES ('delta.enableTypeWidening' = 'true');
ALTER TABLE silver.orders ALTER COLUMN customer_id TYPE BIGINT;
ALTER TABLE silver.orders ALTER COLUMN amount TYPE DECIMAL(12,2);
ALTER TABLE silver.orders ALTER COLUMN amount TYPE DECIMAL(12,4);
ALTER TABLE silver.orders ALTER COLUMN order_id TYPE STRING;
ALTER TABLE silver.orders ALTER COLUMN customer_id TYPE INT;
SELECT order_id, customer_id, amount FROM silver.orders ORDER BY order_id;
```

```text
>>> ALTER TABLE silver.orders ALTER COLUMN customer_id TYPE BIGINT
   AnalysisException: [DELTA_UNSUPPORTED_ALTER_TABLE_CHANGE_COL_OP] ALTER TABLE CHANGE COLUMN is not supported for changing column customer_id from INT to BIGINT
>>> ALTER TABLE silver.orders SET TBLPROPERTIES ('delta.enableTypeWidening' = 'true')
OK
>>> ALTER TABLE silver.orders ALTER COLUMN customer_id TYPE BIGINT
OK
>>> ALTER TABLE silver.orders ALTER COLUMN amount TYPE DECIMAL(12,2)
OK
>>> ALTER TABLE silver.orders ALTER COLUMN amount TYPE DECIMAL(12,4)
   AnalysisException: [NOT_SUPPORTED_CHANGE_COLUMN] ALTER TABLE ALTER/CHANGE COLUMN is not supported for changing `spark_catalog`.`silver`.`orders`'s column `amount` with type "DECIMAL(12,2)" to `amount` with type "DECIMAL(12,4)". SQLSTATE: 0A000; line 1 pos 0;
>>> ALTER TABLE silver.orders ALTER COLUMN order_id TYPE STRING
   AnalysisException: [DELTA_UNSUPPORTED_ALTER_TABLE_CHANGE_COL_OP] ALTER TABLE CHANGE COLUMN is not supported for changing column order_id from INT to STRING
>>> ALTER TABLE silver.orders ALTER COLUMN customer_id TYPE INT
   AnalysisException: [NOT_SUPPORTED_CHANGE_COLUMN] ALTER TABLE ALTER/CHANGE COLUMN is not supported for changing `spark_catalog`.`silver`.`orders`'s column `customer_id` with type "BIGINT" to `customer_id` with type "INT". SQLSTATE: 0A000; line 1 pos 0;
schema now: ['order_id:int', 'customer_id:bigint', 'order_ts:timestamp', 'status:string', 'channel:string', 'amount:decimal(12,2)', 'currency:string', 'row_id:bigint']
+--------+-----------+------+
|order_id|customer_id|amount|
+--------+-----------+------+
|1001    |7          |59.90 |
|1002    |3          |120.00|
|1003    |7          |15.50 |
|1004    |9          |42.00 |
+--------+-----------+------+

protocol: 3 7 ['appendOnly', 'clustering', 'domainMetadata', 'invariants', 'typeWidening']
```

Type widening is "Available on Delta Lake tables in Databricks Runtime 15.4 LTS and above" and changes the type "without rewriting data files" ([Type widening](https://docs.databricks.com/aws/en/tables/features/type-widening), last updated Oct 30, 2026). The allowed changes are `BYTE` to `SHORT`, `INT` or `BIGINT`; `SHORT` to `INT` or `BIGINT`; `INT` to `BIGINT`; `FLOAT` to `DOUBLE`; `DECIMAL` to a greater precision and scale; `DATE` to `TIMESTAMP_NTZ`; and `VOID` to any type. Narrowing (`BIGINT` back to `INT`) and changes of kind (`INT` to `STRING`) are refused.

The decimal rule explains the run: "If you also increase the scale, the total precision must increase by a corresponding amount. If you want to add two decimal places to a field with `decimal(10,1)`, the minimum target is `decimal(12,3)`." From `DECIMAL(12,2)`, adding two decimal places needs `DECIMAL(14,4)`; `DECIMAL(12,4)` would leave two fewer digits before the point. (From the original `DECIMAL(10,2)`, `DECIMAL(12,4)` would have been allowed.)

Points to know:

- **Readers.** "Tables with type widening enabled can only be read by Databricks Runtime 15.4 LTS and above." The run shows the protocol at 3/7 with the `typeWidening` feature.
- **Turning it off.** Setting the property to `false` "prevents future type changes to the table, but doesn't remove the type widening table feature or undo previous type changes"; `ALTER TABLE ... DROP FEATURE 'typeWidening'` removes it and rewrites files that do not match the current schema.
- **Automatic widening.** With the feature on, a write that runs with automatic schema evolution (for example `saveAsTable` with `mergeSchema`, or `MERGE` with schema evolution) can widen a column to match the incoming data; "Without type widening enabled, schema evolution always attempts to downcast data to match column types in the target table" (type widening page).
- **Anything else needs a rewrite.** `INT` to `STRING`, or narrowing, means a new table: `CREATE OR REPLACE TABLE ... AS SELECT CAST(order_id AS STRING) AS order_id, ...` (keeps the history, as section 20.2 showed) or a DataFrame overwrite with `overwriteSchema` ([chapter 4](04-Delta-Lake.md)).

### Renaming and dropping columns: column mapping

Delta data files are Parquet, and Parquet stores column names in every file. A plain Delta table therefore cannot rename or drop a column without rewriting everything. **Column mapping** gives each column a stable internal name (or ID) in the log, so a rename or drop only changes metadata: "Delta Lake column mapping enables metadata-only changes to rename or drop columns without rewriting data files" ([Rename and drop columns with Delta Lake column mapping](https://docs.databricks.com/aws/en/tables/features/column-mapping), last updated Sep 11, 2026).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.orders (order_id INT, customer_id INT, order_date DATE, status STRING,
  amount DECIMAL(10,2), currency STRING) USING DELTA;
INSERT INTO silver.orders VALUES ...;            -- four orders
ALTER TABLE silver.orders DROP COLUMN currency;  -- without column mapping
ALTER TABLE silver.orders SET TBLPROPERTIES ('delta.columnMapping.mode' = 'name');
ALTER TABLE silver.orders RENAME COLUMN status TO order_status;
ALTER TABLE silver.orders DROP COLUMN currency;
SELECT * FROM silver.orders ORDER BY order_id;
DESCRIBE HISTORY silver.orders;
```

```text
before: (1, 2, ['appendOnly', 'invariants']) | parquet files: 2
>>> ALTER TABLE silver.orders DROP COLUMN currency
   AnalysisException: [DELTA_UNSUPPORTED_DROP_COLUMN] DROP COLUMN is not supported for your Delta table.
after columnMapping.mode = name: (2, 7, ['appendOnly', 'columnMapping', 'invariants'])
>>> ALTER TABLE silver.orders RENAME COLUMN status TO order_status
OK
>>> ALTER TABLE silver.orders DROP COLUMN currency
OK
>>> SELECT * FROM silver.orders ORDER BY order_id
+--------+-----------+----------+------------+------+
|order_id|customer_id|order_date|order_status|amount|
+--------+-----------+----------+------------+------+
|1001    |7          |2026-03-01|PLACED      |59.90 |
|1002    |3          |2026-03-01|SHIPPED     |120.00|
|1003    |7          |2026-03-02|PLACED      |15.50 |
|1004    |9          |2026-03-03|CANCELLED   |42.00 |
+--------+-----------+----------+------------+------+

parquet files now: 2
+-------+-----------------+
|version|operation        |
+-------+-----------------+
|0      |CREATE TABLE     |
|1      |WRITE            |
|2      |SET TBLPROPERTIES|
|3      |RENAME COLUMN    |
|4      |DROP COLUMNS     |
+-------+-----------------+
```

The script prints `(minReaderVersion, minWriterVersion, tableFeatures)` from `DESCRIBE DETAIL` and counts the Parquet files in the table folder. The table still has the same two data files after the rename and the drop: nothing was rewritten, and `currency` is still physically in those files until they are rewritten for another reason (`REORG TABLE ... APPLY (PURGE)` forces it). Facts from the Databricks pages:

- Column mapping needs "reader version 2 or above, and writer version 5 or above", and "Reading tables with column mapping enabled requires Databricks Runtime 10.4 LTS and above" (column mapping page). Locally the protocol became 2/7 with the `columnMapping` feature.
- The `RENAME COLUMN` clause is Public Preview, "Applies to: Databricks SQL Databricks Runtime 10.4 LTS and above"; `DROP COLUMN` is Public Preview, 11.3 LTS and above, and "When you drop a column or field, you must drop dependent check constraints and generated columns" ([ALTER TABLE ... COLUMN clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-table-manage-column), last updated Oct 30, 2026).
- "Non-additive schema changes, such as column renames or drops, can break streaming reads. Use a `schemaTrackingLocation`" (column mapping page). A downstream stream that reads this table needs it, or it stops at the change.

[Chapter 4](04-Delta-Lake.md) covers column mapping modes and the streaming option in more depth.

### Renaming a table

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
ALTER TABLE silver.orders RENAME TO silver.orders_v2;
ALTER TABLE silver.orders_v2 RENAME TO silver.orders;
```

```text
>>> ALTER TABLE silver.orders RENAME TO silver.orders_v2
OK
>>> ALTER TABLE silver.orders_v2 RENAME TO silver.orders
OK
```

A rename changes the catalog entry only. Views and jobs that use the old name break, so check lineage first ([chapter 23](23-Governance-and-Operations.md)).

### Tags

A **tag** is a key-value label on a catalog, schema, table, view, volume or column, stored in Unity Catalog (not in the Delta log). Tags drive search, cost reports and, with governed tags, access policies. Locally there is no Unity Catalog, and both forms failed to parse:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> ALTER TABLE silver.orders SET TAGS ('domain' = 'sales')
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'TAGS'. SQLSTATE: 42601 (line 1, pos 30)
>>> SET TAG ON TABLE silver.orders domain = sales
   ParseException: [INVALID_SET_SYNTAX] Expected format is 'SET', 'SET key', or 'SET key=value'. If you want to include special characters in key, or include semicolon in value, please use backquotes, e.g., SET `key`=`value`. SQLSTATE: 42000
```

*Databricks only, not run here. Syntax from [ALTER TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-table) and [SET TAG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-set-tag).*

```sql
-- ALTER TABLE form, Databricks Runtime 13.3 LTS and above
ALTER TABLE shop.silver.orders SET TAGS ('domain' = 'sales', 'tier' = 'silver');
ALTER TABLE shop.silver.orders UNSET TAGS ('tier');
ALTER TABLE shop.silver.customers ALTER COLUMN email SET TAGS ('pii' = 'email');

-- SET TAG form, Databricks Runtime 16.1 and above; the value is optional
SET TAG ON TABLE shop.silver.orders cost_center = sales;
SET TAG ON COLUMN shop.silver.customers.email pii;
UNSET TAG ON TABLE shop.silver.orders cost_center;
```

To tag an object you must own it or have `APPLY TAG` on it plus `USE SCHEMA` and `USE CATALOG` on its parents; a governed tag also needs `ASSIGN` (SET TAG page). Tags are not copied by `CLONE` (section 20.10). Querying tags (`information_schema.table_tags`) and tag policies are in [chapter 23](23-Governance-and-Operations.md).

!!! tip "In the interview"
    **"A column `customer_id INT` needs to become `BIGINT`, and `status` should be renamed `order_status`. How, and what does it cost?"** Enable type widening (`delta.enableTypeWidening = true`, Databricks Runtime 15.4 LTS and above) and run `ALTER COLUMN customer_id TYPE BIGINT`: no files are rewritten. Enable column mapping (`delta.columnMapping.mode = 'name'`) and run `RENAME COLUMN`: also metadata only. Both upgrade the protocol, so older or external readers may no longer read the table, and the rename can break downstream streams unless they use a `schemaTrackingLocation`. A change that is not a widening, such as `INT` to `STRING`, still needs a full rewrite.

## 20.8 Loading data: INSERT, OVERWRITE and the REPLACE family
*Level: intermediate.*

A load does one of four things: add rows, replace the whole table, replace a known slice (one day), or replace the rows that match the incoming batch on some key. Databricks has a statement for each. The generic `INSERT` is in the SQL course ([Insert, update, delete, merge](../../databases/sql/17-Insert-Update-Delete-Merge.md)); this section covers what Delta and Databricks add.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 400" role="img" aria-label="A decision tree for loading a batch into a Delta table. Only new rows: INSERT INTO. Replace the whole table: INSERT OVERWRITE or CREATE OR REPLACE TABLE AS SELECT. Replace a slice you can describe with a fixed predicate: INSERT INTO REPLACE WHERE. Replace the rows whose key values appear in the batch: INSERT INTO REPLACE USING, or REPLACE ON for null-safe or custom matching. Row-by-row insert, update and delete with conditions: MERGE INTO.">
<defs><marker id="a203" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g font-size="13" fill="currentColor">
<rect x="200" y="12" width="240" height="34" rx="5" fill="none" stroke="currentColor" stroke-width="1.5"/>
<text x="232" y="34">A batch of orders arrives</text>
<line x1="320" y1="46" x2="320" y2="66" stroke="currentColor"/>
<line x1="80" y1="66" x2="560" y2="66" stroke="currentColor"/>
<line x1="80" y1="66" x2="80" y2="86" stroke="currentColor" marker-end="url(#a203)"/>
<line x1="240" y1="66" x2="240" y2="86" stroke="currentColor" marker-end="url(#a203)"/>
<line x1="400" y1="66" x2="400" y2="86" stroke="currentColor" marker-end="url(#a203)"/>
<line x1="560" y1="66" x2="560" y2="86" stroke="currentColor" marker-end="url(#a203)"/>
<text x="20" y="104">only new rows?</text>
<text x="180" y="104">whole table?</text>
<text x="330" y="104">a fixed slice?</text>
<text x="490" y="104">rows by key?</text>
<rect x="10" y="116" width="140" height="44" rx="5" fill="none" stroke="currentColor"/>
<text x="20" y="143">INSERT INTO</text>
<rect x="170" y="116" width="140" height="62" rx="5" fill="none" stroke="currentColor"/>
<text x="180" y="138">INSERT OVERWRITE</text>
<text x="180" y="156">or CREATE OR</text>
<text x="180" y="172">REPLACE ... AS</text>
<rect x="330" y="116" width="140" height="62" rx="5" fill="none" stroke="currentColor"/>
<text x="340" y="138">INSERT INTO</text>
<text x="340" y="156">REPLACE WHERE</text>
<text x="340" y="172">order_date = ...</text>
<rect x="490" y="116" width="140" height="62" rx="5" fill="none" stroke="currentColor"/>
<text x="500" y="138">INSERT INTO</text>
<text x="500" y="156">REPLACE USING (k)</text>
<text x="500" y="172">or REPLACE ON</text>
<text x="330" y="204">source rows outside the predicate:</text>
<text x="330" y="222">error; empty source: slice deleted</text>
<text x="490" y="248">empty source:</text>
<text x="490" y="266">nothing deleted</text>
<text x="20" y="294">need per-row conditions (update some, delete some, insert the rest)?</text>
<line x1="320" y1="300" x2="320" y2="314" stroke="currentColor" marker-end="url(#a203)"/>
<rect x="180" y="316" width="280" height="62" rx="5" fill="none" stroke="currentColor" stroke-width="1.5"/>
<text x="196" y="340">MERGE INTO ... ON key</text>
<text x="196" y="360">WHEN [NOT] MATCHED [BY SOURCE]</text>
</g>
</svg>
<figcaption>Figure 20.3. Choosing a load statement. The REPLACE forms delete and insert in one atomic commit; MERGE decides row by row. REPLACE USING needs Databricks Runtime 16.3 and above, REPLACE ON 17.1 and above.</figcaption>
</figure>

### INSERT INTO: by position, by column list, BY NAME

The `orders` table here has columns `(order_id, customer_id, order_date, status, amount, currency)`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO silver.orders (order_id, customer_id, order_date, amount)
VALUES (1005, 2, DATE'2026-03-03', 88.00);

INSERT INTO silver.orders BY NAME
SELECT 'CAD' AS currency, 1006 AS order_id, 4 AS customer_id, DATE'2026-03-04' AS order_date,
       'PLACED' AS status, 19.99 AS amount;

-- the same SELECT by position (no BY NAME)
INSERT INTO silver.orders
SELECT 'CAD' AS currency, 1007 AS order_id, 4 AS customer_id, DATE'2026-03-04' AS order_date,
       'PLACED' AS status, 19.99 AS amount;

SELECT * FROM silver.orders WHERE order_id >= 1005 ORDER BY order_id;
```

```text
>>> INSERT INTO silver.orders BY NAME SELECT 'CAD' AS currency, 1006 AS order_id, 4 AS customer_id, DATE'2026-03-04' AS order_date, 'PLACED' AS status, 19.99 AS amount
OK
-- the same SELECT by position (no BY NAME):
>>> INSERT INTO silver.orders SELECT 'CAD' AS currency, 1007 AS order_id, 4 AS customer_id, DATE'2026-03-04' AS order_date, 'PLACED' AS status, 19.99 AS amount
   AnalysisException: [DATATYPE_MISMATCH.CAST_WITH_FUNC_SUGGESTION] Cannot resolve "customer_id" due to data type mismatch: cannot cast "INT" to "DATE".
+--------+-----------+----------+------+------+--------+
|order_id|customer_id|order_date|status|amount|currency|
+--------+-----------+----------+------+------+--------+
|1005    |2          |2026-03-03|NULL  |88.00 |NULL    |
|1006    |4          |2026-03-04|PLACED|19.99 |CAD     |
+--------+-----------+----------+------+------+--------+
```

- A **column list** fills the listed columns; the others get their default, here `NULL` (1005).
- **`BY NAME`** matches the query's column names to the table's, whatever their order (Databricks SQL and Databricks Runtime 13.3 LTS and above). Without it, columns match by position: the third query column, `customer_id`, landed on `order_date` and failed. A positional insert that does not fail, because the types happen to be compatible, silently puts values in the wrong columns, which is worse. One limit, from [INSERT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-dml-insert-into) (last updated Oct 21, 2026): "For nested struct fields, resolution is by name on Parquet (and other non-Delta) tables and by position on Delta Lake Lake tables."

In PySpark, `df.write.mode("append").saveAsTable(...)` matches columns by name for a Delta table, while `df.write.insertInto(...)` matches by position.

### INSERT OVERWRITE: replace every row

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.orders_cad USING DELTA AS SELECT * FROM silver.orders WHERE currency = 'CAD';
INSERT OVERWRITE silver.orders_cad
SELECT * FROM silver.orders WHERE currency = 'CAD' AND status = 'PLACED';
SELECT order_id, status FROM silver.orders_cad ORDER BY order_id;
```

```text
+--------+------+
|order_id|status|
+--------+------+
|1001    |PLACED|
|1006    |PLACED|
+--------+------+
```

All earlier rows are gone; the old version stays reachable by time travel. `INSERT OVERWRITE` keeps the table's schema and properties. To also change the schema, use `CREATE OR REPLACE TABLE ... AS SELECT` (section 20.2).

### REPLACE WHERE: replace a slice atomically

Reloading one day is the most common partial overwrite. `INSERT INTO ... REPLACE WHERE <predicate>` deletes the rows that match the predicate and inserts the query's rows, in one commit (Databricks SQL and Databricks Runtime 12.2 LTS and above, Delta only). The batch `fixed_0301` holds the corrected rows for 1 March: order 1001 is now `SHIPPED`, order 1002 was cancelled at the source and is missing, and order 1008 is new.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- orders holds 1001, 1002 (2026-03-01), 1003 (03-02), 1004 (03-03)
INSERT INTO silver.orders REPLACE WHERE order_date = DATE'2026-03-01'
SELECT * FROM fixed_0301;
SELECT * FROM silver.orders ORDER BY order_id;

-- a source row outside the predicate
INSERT INTO silver.orders REPLACE WHERE order_date = DATE'2026-03-01'
SELECT 1009, 5, DATE'2026-03-05', 'PLACED', 10.00, 'CAD';

-- an empty source
INSERT INTO silver.orders REPLACE WHERE order_date = DATE'2026-03-02'
SELECT * FROM fixed_0301 WHERE false;
SELECT order_id, order_date FROM silver.orders ORDER BY order_id;
```

```text
+--------+-----------+----------+---------+------+--------+
|order_id|customer_id|order_date|status   |amount|currency|
+--------+-----------+----------+---------+------+--------+
|1001    |7          |2026-03-01|SHIPPED  |59.90 |CAD     |
|1003    |7          |2026-03-02|PLACED   |15.50 |USD     |
|1004    |9          |2026-03-03|CANCELLED|42.00 |CAD     |
|1008    |5          |2026-03-01|PLACED   |33.00 |CAD     |
+--------+-----------+----------+---------+------+--------+

-- a source row outside the predicate:
>>> INSERT INTO silver.orders REPLACE WHERE order_date = DATE'2026-03-01' SELECT 1009, 5, DATE'2026-03-05', 'PLACED', 10.00, 'CAD'
   AnalysisException: [DELTA_REPLACE_WHERE_MISMATCH] Written data does not conform to partial table overwrite condition or constraint '(order_date = DATE '2026-03-01')'.
-- an empty source: rows matching the predicate are deleted
+--------+----------+
|order_id|order_date|
+--------+----------+
|1001    |2026-03-01|
|1004    |2026-03-03|
|1008    |2026-03-01|
+--------+----------+

+-------+---------+--------------------------------+
|version|operation|predicate                       |
+-------+---------+--------------------------------+
|6      |WRITE    |(order_date = DATE '2026-03-01')|
|7      |WRITE    |(order_date = DATE '2026-03-02')|
+-------+---------+--------------------------------+
```

Three behaviors to remember:

1. **The whole slice is replaced**, so order 1002, absent from the batch, is deleted. That is the point: a `MERGE` would have left it.
2. **Every inserted row must match the predicate.** "If any row falls outside it, the `INSERT` fails and writes nothing" ([INSERT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-dml-insert-into)). On classic compute, `spark.databricks.delta.replaceWhere.constraintCheck.enabled = false` turns the check off.
3. **An empty source deletes the slice.** The 2 March reload with no rows removed order 1003. "For empty source queries, `REPLACE WHERE` might delete table rows" ([Selectively overwrite data with Delta Lake](https://docs.databricks.com/aws/en/delta/selective-overwrite), last updated Sep 11, 2026). Guard the job: fail it when the extract is empty but should not be.

The predicate may use only table columns and a limited set of operators: `AND`, `OR`, `NOT`, `IN` with literals, comparisons (`=`, `<=>`, `>`, `<`, `>=`, `<=`), `TRUE`/`FALSE`, `startsWith`, `endsWith`, `contains`, `IS [NOT] NULL` (INSERT page). It does not need to be on a partition column. The history records each replace as a `WRITE` with the predicate.

The PySpark form is the `replaceWhere` writer option:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
(spark.table("fixed_0301").write.format("delta").mode("overwrite")
    .option("replaceWhere", "order_date = '2026-03-01'")
    .saveAsTable("silver.orders"))
spark.sql("SELECT order_id, order_date, status FROM silver.orders ORDER BY order_id").show()
```

```text
+--------+----------+---------+
|order_id|order_date|status   |
+--------+----------+---------+
|1001    |2026-03-01|SHIPPED  |
|1003    |2026-03-02|PLACED   |
|1004    |2026-03-03|CANCELLED|
|1008    |2026-03-01|PLACED   |
+--------+----------+---------+
```

### Partitioned tables: PARTITION overwrite and dynamic partition overwrite

On a partitioned table there are two older ways to replace part of it. The table `orders_pN` below is the same data partitioned by `order_date`; each statement ran on a fresh copy.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- 1. static: name the partition
INSERT OVERWRITE silver.orders_p1 PARTITION (order_date = '2026-03-01')
SELECT order_id, customer_id, status, amount, currency FROM fixed_0301;

-- 2. no PARTITION clause, default (static) mode
INSERT OVERWRITE silver.orders_p2 SELECT * FROM fixed_0301;

-- 3. no PARTITION clause, dynamic mode
SET spark.sql.sources.partitionOverwriteMode = dynamic;
INSERT OVERWRITE silver.orders_p3 SELECT * FROM fixed_0301;
```

```text
>>> SELECT order_id, order_date, status FROM silver.orders_p1 ORDER BY order_id
+--------+----------+---------+
|order_id|order_date|status   |
+--------+----------+---------+
|1001    |2026-03-01|SHIPPED  |
|1003    |2026-03-02|PLACED   |
|1004    |2026-03-03|CANCELLED|
|1008    |2026-03-01|PLACED   |
+--------+----------+---------+

-- INSERT OVERWRITE without PARTITION, static mode (the default): every partition is replaced
>>> SELECT order_id, order_date, status FROM silver.orders_p2 ORDER BY order_id
+--------+----------+-------+
|order_id|order_date|status |
+--------+----------+-------+
|1001    |2026-03-01|SHIPPED|
|1008    |2026-03-01|PLACED |
+--------+----------+-------+

-- the same statement with partitionOverwriteMode = dynamic: only partitions present in the source
>>> SELECT order_id, order_date, status FROM silver.orders_p3 ORDER BY order_id
+--------+----------+---------+
|order_id|order_date|status   |
+--------+----------+---------+
|1001    |2026-03-01|SHIPPED  |
|1003    |2026-03-02|PLACED   |
|1004    |2026-03-03|CANCELLED|
|1008    |2026-03-01|PLACED   |
+--------+----------+---------+
```

Case 2 is the trap: forgetting the `PARTITION` clause in static mode wiped 2 and 3 March. Dynamic mode (case 3) replaces only the partitions that appear in the source. On Databricks this mode is legacy and limited: it is Public Preview, "only available for classic compute, not Databricks SQL warehouses or serverless compute" (the same page's summary table narrows this to SQL and lists the Python and Scala writer as supported on all compute types), and the page warns: "When possible, use `INSERT REPLACE USING` instead of partition overwrite `INSERT OVERWRITE PARTITION` and `spark.sql.sources.partitionOverwriteMode=dynamic`. Partition overwrite may use stale data when partitioning changes" (selective overwrite page).

### REPLACE USING and REPLACE ON

`REPLACE USING (cols)` is dynamic overwrite without partitions: it "Atomically deletes rows from `table_name` that match a row in `query` on the specified columns, then inserts the rows from `query`" (Databricks SQL and Databricks Runtime 16.3 and above, INSERT page). Reload 1 and 5 March by sending only those dates, and every other date is untouched. `REPLACE ON <condition>` (Databricks SQL and Databricks Runtime 17.1 and above) does the same with any condition that may reference both the table and the query, for example a null-safe match.

The open-source SQL parser accepts both forms, but Delta 4.4.1 does not implement them:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> INSERT INTO silver.orders REPLACE USING (order_date) SELECT * FROM fixed_0301
   AnalysisException: [UNSUPPORTED_FEATURE.TABLE_OPERATION] The feature is not supported: Table `spark_catalog`.`silver`.`orders` does not support INSERT INTO ... REPLACE ON/USING. Please check the current catalog and namespace to make sure the qualified table name is expected, and
>>> INSERT INTO silver.orders AS t REPLACE ON t.order_id <=> s.order_id (SELECT * FROM fixed_0301) AS s
   AnalysisException: [UNSUPPORTED_FEATURE.TABLE_OPERATION] The feature is not supported: Table `spark_catalog`.`silver`.`orders` does not support INSERT INTO ... REPLACE ON/USING. Please check the current catalog and namespace to make sure the qualified table name is expected, and
```

*Databricks only, not run here. Syntax from [INSERT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-dml-insert-into) and [Selectively overwrite data with Delta Lake](https://docs.databricks.com/aws/en/delta/selective-overwrite).*

```sql
-- replace every order of the dates present in the batch
INSERT INTO shop.silver.orders REPLACE USING (order_date)
SELECT * FROM fixed_batch;

-- replace by key, treating NULL keys as equal
INSERT INTO shop.silver.orders AS t
REPLACE ON t.order_id <=> s.order_id
(SELECT * FROM fixed_batch) AS s;
```

The rules, from the INSERT and selective overwrite pages:

- `REPLACE USING` matches "using regular equality comparison, where `NULL` values are treated as not equal to anything", so target rows with a `NULL` key are never removed. Use `REPLACE ON` with `<=>` when `NULL`s must match.
- In Databricks Runtime 16.3 to 17.1, `REPLACE USING` "requires a partitioned table" and the columns "must include all of the table's partition columns"; from 17.2 any table, clustered ones included, and any columns.
- An empty source deletes nothing for both forms ("If the `query` is empty, no deletions occur"), unlike `REPLACE WHERE`.
- `BY NAME` with either form needs Databricks Runtime 18.1 and above.
- The Python and Scala writer options `replaceUsing` and `replaceOn` are documented for Databricks Runtime 18.2 and above.

That last point has a twist: the `replaceUsing` writer option already works in open-source Delta 4.4.1. The batch below carries 1 and 5 March:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
src = spark.table("fixed_0301").unionByName(spark.sql(
    "SELECT 1012 AS order_id, 6 AS customer_id, DATE'2026-03-05' AS order_date, 'PLACED' AS status, "
    "CAST(5.00 AS DECIMAL(10,2)) AS amount, 'CAD' AS currency"))
(src.write.format("delta").mode("overwrite")
    .option("replaceUsing", "order_date").saveAsTable("silver.orders"))
```

```text
replaceUsing option: accepted
>>> SELECT order_id, order_date, status FROM silver.orders ORDER BY order_id
+--------+----------+---------+
|order_id|order_date|status   |
+--------+----------+---------+
|1001    |2026-03-01|SHIPPED  |
|1003    |2026-03-02|PLACED   |
|1004    |2026-03-03|CANCELLED|
|1008    |2026-03-01|PLACED   |
|1012    |2026-03-05|PLACED   |
+--------+----------+---------+

+-------+---------+------------------------------------------------------------------------+
|version|operation|operationParameters                                                     |
+-------+---------+------------------------------------------------------------------------+
|13     |WRITE    |{mode -> Overwrite, partitionBy -> [], replaceUsingCols -> (order_date)}|
+-------+---------+------------------------------------------------------------------------+
```

1 March was replaced (1002 gone, 1008 in), 5 March was added, and 2 and 3 March were untouched, on a table with no partitions.

### Schema evolution on write

By default a write whose source has an extra column fails (schema enforcement, [chapter 4](04-Delta-Lake.md)). To let the table grow the column, opt in per write:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
extra = spark.sql("""SELECT 1005 AS order_id, 2 AS customer_id, DATE'2026-03-03' AS order_date,
                            'PLACED' AS status, CAST(88.00 AS DECIMAL(10,2)) AS amount,
                            'CAD' AS currency, 'web' AS channel""")
extra.write.format("delta").mode("append").saveAsTable("silver.orders_se")              # extra column
extra.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable("silver.orders_se")

# new_cols: one more order with channel and a new column promo
spark.sql("""MERGE WITH SCHEMA EVOLUTION INTO silver.orders_se AS t USING new_cols AS s
             ON t.order_id = s.order_id
             WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *""")
spark.sql("INSERT WITH SCHEMA EVOLUTION INTO silver.orders_se SELECT * FROM new_cols")
```

```text
append without mergeSchema: AnalysisException: [DELTA_METADATA_MISMATCH] A metadata mismatch was detected when writing to the Delta table.
append with mergeSchema = true, columns: ['order_id', 'customer_id', 'order_date', 'status', 'amount', 'currency', 'channel']
>>> MERGE WITH SCHEMA EVOLUTION INTO silver.orders_se AS t USING new_cols AS s ON t.order_id = s.order_id WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *
OK
after MERGE WITH SCHEMA EVOLUTION, columns: ['order_id', 'customer_id', 'order_date', 'status', 'amount', 'currency', 'channel', 'promo']
>>> INSERT WITH SCHEMA EVOLUTION INTO silver.orders_se SELECT * FROM new_cols
OK
```

The plain append failed; with `mergeSchema` the table gained `channel`, and `MERGE WITH SCHEMA EVOLUTION` added `promo`. New columns are added at the end, and existing rows read `NULL` in them. The `INSERT WITH SCHEMA EVOLUTION` form also parsed and ran here, although by then there was no new column left to add. On Databricks, `INSERT WITH SCHEMA EVOLUTION` is "Applies to: Databricks Runtime 18.1 and above" (INSERT page), and the `MERGE` form has two documented versions (section 20.9). "Databricks recommends enabling schema evolution for each write operation using the `WITH SCHEMA EVOLUTION` syntax or the `mergeSchema` option rather than setting a Spark configuration" ([Update table schemas with schema evolution](https://docs.databricks.com/aws/en/tables/update-schema)). With type widening enabled, the same options can also widen a column's type (section 20.7).

### Which statement to use

| Statement | Deletes | Empty source | Where |
| --- | --- | --- | --- |
| `INSERT INTO` | nothing | no change | everywhere |
| `INSERT OVERWRITE` | every row | table emptied | everywhere |
| `INSERT INTO ... REPLACE WHERE p` | rows matching `p` | rows matching `p` deleted | Databricks SQL, Databricks Runtime 12.2 LTS and above; open-source Delta |
| `INSERT OVERWRITE ... PARTITION (...)` | the named partition | partition emptied | partitioned tables |
| dynamic `partitionOverwriteMode` | partitions present in the source | no change | legacy; in SQL, classic compute only |
| `INSERT INTO ... REPLACE USING (cols)` | rows whose `cols` equal a source row's | no change | Databricks SQL, Databricks Runtime 16.3 and above |
| `INSERT INTO ... REPLACE ON cond` | rows matching a source row by `cond` | no change | Databricks SQL, Databricks Runtime 17.1 and above |
| `MERGE INTO` | what its clauses say | depends on `NOT MATCHED BY SOURCE` | everywhere |

!!! tip "In the interview"
    **"How do you reprocess one day of orders without duplicates?"** Make the load idempotent by replacing the day rather than appending: `INSERT INTO silver.orders REPLACE WHERE order_date = '2026-03-01' SELECT ...` deletes that day and inserts the batch in one commit, so a rerun gives the same result and rows dropped at the source disappear. If the batch can contain several days, `REPLACE USING (order_date)` (Databricks Runtime 16.3 and above) replaces exactly the days present. Watch the empty-batch case: `REPLACE WHERE` with no rows deletes the day. `MERGE` is the answer when rows must be updated, inserted or deleted individually by key, not when a whole slice is reloaded.

## 20.9 UPDATE, DELETE, TRUNCATE and MERGE
*Level: intermediate.*

These are standard SQL statements ([Insert, update, delete, merge](../../databases/sql/17-Insert-Update-Delete-Merge.md)); on Delta each one is a single atomic commit that rewrites (or, with deletion vectors, marks) only the files holding affected rows. How Delta finds and rewrites those files, and how MERGE works inside, is in [chapter 4](04-Delta-Lake.md); MERGE patterns for deduplication, late data and slowly changing dimensions are in [chapter 9](09-Building-Silver.md). This section is the syntax and the rules that differ between engines.

### UPDATE and DELETE, and subqueries

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- orders: 1001 (customer 7), 1002 (3), 1003 (7), 1004 (9); blocked holds customer 9
UPDATE silver.orders SET status = 'SHIPPED', amount = amount + 0 WHERE order_id = 1003;
DELETE FROM silver.orders WHERE customer_id IN (SELECT customer_id FROM blocked);
DELETE FROM silver.orders AS o WHERE EXISTS (SELECT 1 FROM blocked b WHERE b.customer_id = o.customer_id);
UPDATE silver.orders o SET status = 'HOLD' FROM blocked b WHERE o.customer_id = b.customer_id;
DELETE FROM silver.orders WHERE customer_id = 9;
SELECT order_id, customer_id, status FROM silver.orders ORDER BY order_id;
```

```text
>>> DELETE FROM silver.orders WHERE customer_id IN (SELECT customer_id FROM blocked)
   AnalysisException: [DELTA_UNSUPPORTED_SUBQUERY] Subqueries are not supported in the DELETE (condition = (spark_catalog.silver.orders.customer_id IN (listquery()))).
>>> DELETE FROM silver.orders AS o WHERE EXISTS (SELECT 1 FROM blocked b WHERE b.customer_id = o.customer_id)
   AnalysisException: [DELTA_UNSUPPORTED_SUBQUERY] Subqueries are not supported in the DELETE (condition = exists(o.customer_id)).
>>> UPDATE silver.orders o SET status = 'HOLD' FROM blocked b WHERE o.customer_id = b.customer_id
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'FROM'. SQLSTATE: 42601 (line 1, pos 43)
>>> SELECT order_id, customer_id, status FROM silver.orders ORDER BY order_id
+--------+-----------+-------+
|order_id|customer_id|status |
+--------+-----------+-------+
|1001    |7          |PLACED |
|1002    |3          |SHIPPED|
|1003    |7          |SHIPPED|
+--------+-----------+-------+
```

Two differences from what you may expect:

- **Subqueries in `WHERE`.** Open-source Delta 4.4.1 refused them. Databricks accepts them: "The `WHERE` predicate supports subqueries, including `IN`, `NOT IN`, `EXISTS`, `NOT EXISTS`, and scalar subqueries", except nested subqueries and "`NOT IN` subquery inside an `OR`" ([DELETE FROM](https://docs.databricks.com/aws/en/sql/language-manual/delta-delete-from); [UPDATE](https://docs.databricks.com/aws/en/sql/language-manual/delta-update) has the same list). Both pages recommend `NOT EXISTS` over `NOT IN`, which "can be slow".
- **No `UPDATE ... FROM`** on either engine: "Databricks SQL does not support the `UPDATE ... FROM ... JOIN` syntax used in some other SQL dialects ... To update a table based on a join with another table or subquery, use MERGE INTO instead" (UPDATE page).

*Databricks only, not run here. Syntax from [DELETE FROM](https://docs.databricks.com/aws/en/sql/language-manual/delta-delete-from) and [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into).*

```sql
DELETE FROM shop.silver.orders AS o
WHERE EXISTS (SELECT 1 FROM shop.silver.blocked_customers b WHERE b.customer_id = o.customer_id);

-- the "UPDATE ... FROM" of other dialects, written as MERGE
MERGE INTO shop.silver.orders AS o
USING shop.silver.blocked_customers AS b
ON o.customer_id = b.customer_id
WHEN MATCHED THEN UPDATE SET o.status = 'HOLD';
```

Open-source Delta has no such restriction on `MERGE` (the MERGE runs below use temporary views as sources), so there the workaround for a subquery `DELETE` is a `MERGE ... WHEN MATCHED THEN DELETE`.

### TRUNCATE

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.scratch USING DELTA AS SELECT * FROM silver.orders;
TRUNCATE TABLE silver.scratch;
```

```text
after TRUNCATE: 0 rows; ['CREATE TABLE AS SELECT', 'TRUNCATE']
```

`TRUNCATE` removes all rows in one commit and keeps the schema, properties and history (so time travel to the earlier version still works until `VACUUM`). "Delta Lake does not support partition clauses for `TRUNCATE`" ([TRUNCATE TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-truncate-table)); to empty one partition, use `DELETE ... WHERE`. Practice question 33 compares `TRUNCATE`, `DELETE` without `WHERE` and an empty `INSERT OVERWRITE`.

### MERGE: the full syntax

*Databricks only, not run here. Syntax from [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into).*

```sql
MERGE [ WITH SCHEMA EVOLUTION ] INTO target_table_name [target_alias]
   USING source_table_reference [source_alias]
   ON merge_condition
   { WHEN MATCHED [ AND matched_condition ] THEN matched_action |
     WHEN NOT MATCHED [BY TARGET] [ AND not_matched_condition ] THEN not_matched_action |
     WHEN NOT MATCHED BY SOURCE [ AND not_matched_by_source_condition ] THEN not_matched_by_source_action } [...]

matched_action
 { DELETE |
   UPDATE SET * [ EXCEPT ( column [, ...] ) ] |
   UPDATE SET { column = { expr | DEFAULT } } [, ...] }

not_matched_action
 { INSERT * [ EXCEPT ( column [, ...] ) ] |
   INSERT (column1 [, ...] ) VALUES ( expr | DEFAULT ] [, ...] )

not_matched_by_source_action
 { DELETE |
   UPDATE SET { column = { expr | DEFAULT } } [, ...] }
```

(The unbalanced bracket in `INSERT ... VALUES` is copied as the page has it.) The three kinds of clause:

| Clause | Fires for | Allowed actions | Version line on the MERGE INTO page |
| --- | --- | --- | --- |
| `WHEN MATCHED` | a target row that matches a source row | `UPDATE`, `DELETE` | none for the clause |
| `WHEN NOT MATCHED [BY TARGET]` | a source row with no target row | `INSERT` | `BY TARGET` alias: 12.2 LTS or above |
| `WHEN NOT MATCHED BY SOURCE` | a target row with no source row | `UPDATE`, `DELETE` | 12.2 LTS or above |

### MERGE with every clause

The batch says: 1001 shipped, 1003 cancelled, 1010 is new, 1011 is new but already cancelled. The target holds 1001 to 1004, where 1004 was cancelled earlier.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- target: 1001 (03-01, PLACED), 1002 (03-01, SHIPPED), 1003 (03-02, PLACED), 1004 (03-03, CANCELLED)
-- batch:  1001 SHIPPED, 1003 CANCELLED, 1010 PLACED, 1011 CANCELLED
MERGE INTO silver.orders AS t
USING batch AS s
ON t.order_id = s.order_id
WHEN MATCHED AND s.status = 'CANCELLED' THEN DELETE
WHEN MATCHED THEN UPDATE SET t.status = s.status, t.amount = s.amount
WHEN NOT MATCHED AND s.status <> 'CANCELLED' THEN INSERT *
WHEN NOT MATCHED BY SOURCE AND t.order_date < DATE'2026-03-02' THEN UPDATE SET t.status = 'ARCHIVED'
WHEN NOT MATCHED BY SOURCE AND t.status = 'CANCELLED' THEN DELETE;

SELECT * FROM silver.orders ORDER BY order_id;
SELECT operationMetrics FROM (DESCRIBE HISTORY silver.orders) WHERE operation = 'MERGE';
```

```text
+--------+-----------+----------+--------+------+--------+
|order_id|customer_id|order_date|status  |amount|currency|
+--------+-----------+----------+--------+------+--------+
|1001    |7          |2026-03-01|SHIPPED |59.90 |CAD     |
|1002    |3          |2026-03-01|ARCHIVED|120.00|CAD     |
|1010    |8          |2026-03-04|PLACED  |75.00 |CAD     |
+--------+-----------+----------+--------+------+--------+

+-------+-------+--------+-----------+-----------+--------+--------+
|updated|deleted|inserted|matched_upd|matched_del|nmbs_upd|nmbs_del|
+-------+-------+--------+-----------+-----------+--------+--------+
|2      |2      |1       |1          |1          |1       |1       |
+-------+-------+--------+-----------+-----------+--------+--------+
```

(The script selects seven keys of `operationMetrics`, such as `numTargetRowsMatchedUpdated` and `numTargetRowsNotMatchedBySourceDeleted`, under short names.) Row by row:

- 1001 matched, not cancelled: second `MATCHED` clause, updated to `SHIPPED`.
- 1003 matched and cancelled: first `MATCHED` clause, deleted.
- 1010 not in the target, not cancelled: inserted. 1011 is cancelled, so no `NOT MATCHED` clause applies and it is skipped.
- 1002 is not in the batch and dated 1 March: first `NOT MATCHED BY SOURCE` clause, set to `ARCHIVED`.
- 1004 is not in the batch and cancelled: second `NOT MATCHED BY SOURCE` clause, deleted.

The metrics agree: two updates (one matched, one not matched by source), two deletes (one of each), one insert.

### The rules

**Clause order.** Clauses of the same kind are evaluated in order, the first whose condition is true wins, and "Each `WHEN MATCHED` clause, except the last one, must have a `matched_condition`" (MERGE INTO page). The same holds for the other two kinds. A row that no clause accepts is left alone (target) or skipped (source).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> MERGE INTO silver.orders AS t USING batch AS s ON t.order_id = s.order_id WHEN MATCHED THEN UPDATE SET * WHEN MATCHED AND s.status = 'CANCELLED' THEN DELETE
   ParseException: [NON_LAST_MATCHED_CLAUSE_OMIT_CONDITION] When there are more than one MATCHED clauses in a MERGE statement, only the last MATCHED clause can omit the condition. SQLSTATE: 42613
```

**`NOT MATCHED BY SOURCE` sees only the target.** There is no source row, so its condition and `SET` expressions "may only reference columns from the target table, otherwise the query will throw an analysis error" (MERGE INTO page). Open-source Delta 4.4.1 rejects it too, but with an internal error instead of the documented analysis error:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> MERGE INTO silver.orders AS t USING batch AS s ON t.order_id = s.order_id WHEN NOT MATCHED BY SOURCE THEN UPDATE SET t.status = s.status
   SparkException: [INTERNAL_ERROR] Cannot find main error class 'DELTA_MERGE_UNRESOLVED_EXPRESSION' SQLSTATE: XX000
```

It is also expensive: "Adding a `WHEN NOT MATCHED BY SOURCE` clause to update or delete target rows when the `merge_condition` evaluates to false can lead to a large number of target rows being modified", so add a condition that limits it (here, the date).

**One source row per target row.** `MERGE` fails "if more than one row in the source table matches the same row in the target table", with `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`. The exception: "Databricks allows multiple matches when matches are unconditionally deleted" (MERGE INTO page).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- dup_batch: (1001, 'SHIPPED'), (1001, 'DELIVERED')
MERGE INTO silver.orders_m AS t USING dup_batch AS s ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET t.status = s.status;

MERGE INTO silver.orders_m AS t USING dup_batch AS s ON t.order_id = s.order_id
WHEN MATCHED THEN DELETE;
```

```text
>>> MERGE INTO silver.orders_m AS t USING dup_batch AS s ON t.order_id = s.order_id WHEN MATCHED THEN UPDATE SET t.status = s.status
   UnsupportedOperationException: [DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE] Cannot perform Merge as multiple source rows matched and attempted to modify the same
>>> MERGE INTO silver.orders_m AS t USING dup_batch AS s ON t.order_id = s.order_id WHEN MATCHED THEN DELETE
OK
+--------+
|order_id|
+--------+
|1002    |
|1003    |
|1004    |
+--------+
```

The update could not choose between `SHIPPED` and `DELIVERED`; the unconditional delete has nothing to choose, so it ran. Deduplicate the source before a MERGE ([chapter 9](09-Building-Silver.md)).

**`UPDATE SET *` and `INSERT *`** copy every target column from the source column of the same name; the source must have all of them. `* EXCEPT (cols)` (Databricks SQL and Databricks Runtime 12.2 LTS and above) leaves columns out. The open-source parser does not accept it:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> MERGE INTO silver.orders AS t USING batch AS s ON t.order_id = s.order_id WHEN MATCHED THEN UPDATE SET * EXCEPT (currency) WHEN NOT MATCHED THEN INSERT * EXCEPT (currency)
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'EXCEPT'. SQLSTATE: 42601 (line 2, pos 42)
```

What happens to the excluded columns is stated the same way for both actions: "Excluded target columns are set to `null`" (MERGE INTO page), and "Excluded columns are set to `null`" ([Update table schemas with schema evolution](https://docs.databricks.com/aws/en/tables/update-schema)). For `INSERT * EXCEPT` that is clearly what happens (the page's examples show it). For `UPDATE SET * EXCEPT` it would mean the excluded column of a matched row is overwritten with `NULL`, not kept. Not verified here; test it on your runtime before relying on either reading, or write an explicit `UPDATE SET col = s.col, ...` list.

**`DEFAULT`** in `UPDATE SET col = DEFAULT` or `INSERT ... VALUES (DEFAULT)` uses the column default (Databricks SQL and Databricks Runtime 11.3 LTS and above).

### MERGE WITH SCHEMA EVOLUTION

`MERGE WITH SCHEMA EVOLUTION INTO ...` lets `UPDATE SET *` and `INSERT *` add the source's new columns to the target. The pages give different versions: the [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into) page (last updated Sep 11, 2026) says "Applies to: Databricks Runtime 15.2 or above", while [Update table schemas with schema evolution](https://docs.databricks.com/aws/en/tables/update-schema) (last updated Sep 11, 2026) says "In Databricks Runtime 15.4 LTS and above, you can specify schema evolution in a merge statement using SQL or table APIs". Chapter 4 uses 15.4 LTS. Open-source Delta 4.4.1 ran it (section 20.8).

### The same MERGE in PySpark

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from delta.tables import DeltaTable
from pyspark.sql import functions as F

(DeltaTable.forName(spark, "silver.orders").alias("t")
    .merge(spark.table("batch").alias("s"), "t.order_id = s.order_id")
    .whenMatchedDelete(condition="s.status = 'CANCELLED'")
    .whenMatchedUpdate(set={"status": "s.status", "amount": "s.amount"})
    .whenNotMatchedInsertAll(condition="s.status <> 'CANCELLED'")
    .whenNotMatchedBySourceUpdate(condition="t.order_date < DATE'2026-03-02'",
                                  set={"status": F.lit("ARCHIVED")})
    .whenNotMatchedBySourceDelete(condition="t.status = 'CANCELLED'")
    .execute())
spark.sql("SELECT * FROM silver.orders ORDER BY order_id").show()
```

```text
+--------+-----------+----------+--------+------+--------+
|order_id|customer_id|order_date|status  |amount|currency|
+--------+-----------+----------+--------+------+--------+
|1001    |7          |2026-03-01|SHIPPED |59.90 |CAD     |
|1002    |3          |2026-03-01|ARCHIVED|120.00|CAD     |
|1010    |8          |2026-03-04|PLACED  |75.00 |CAD     |
+--------+-----------+----------+--------+------+--------+
```

The builder calls follow the SQL clauses one for one, in the same order.

!!! tip "In the interview"
    **"Your MERGE fails with 'multiple source rows matched the same target row'. Why, and what do you do?"** The batch has two rows with the same key (a retry, or two events for one order), and MERGE refuses to guess which one wins. Deduplicate the source first, keeping the latest row per key, for example `QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY event_ts DESC) = 1` ([window functions](../../databases/sql/13-Window-Functions-Ranking.md)). The one case Databricks allows is an unconditional `WHEN MATCHED THEN DELETE`. And if the question is "how do I delete target rows that vanished from a full snapshot?", the answer is `WHEN NOT MATCHED BY SOURCE THEN DELETE`.

## 20.10 CLONE, time travel, RESTORE and UNDROP
*Level: intermediate.*

Three tools recover or copy a table at a point in time. **Time travel** reads an old version, **RESTORE** makes an old version current again, and **CLONE** makes a new table from a version. **UNDROP** brings back a dropped table in Unity Catalog. How versions and retention work is in [chapter 4](04-Delta-Lake.md); this section is about the table-level statements.

### SHALLOW CLONE

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- silver.orders: three orders written in two commits (versions 1 and 2)
CREATE TABLE dev.orders_shallow SHALLOW CLONE silver.orders;
UPDATE dev.orders_shallow SET status = 'TEST' WHERE order_id = 1001;
SELECT order_id, status FROM silver.orders WHERE order_id = 1001;
SELECT order_id, status FROM dev.orders_shallow WHERE order_id = 1001;
```

```text
+-----------------+-------------------+-----------------+----------------+------------------+-----------------+
|source_table_size|source_num_of_files|num_removed_files|num_copied_files|removed_files_size|copied_files_size|
+-----------------+-------------------+-----------------+----------------+------------------+-----------------+
|5254             |3                  |0                |0               |0                 |0                |
+-----------------+-------------------+-----------------+----------------+------------------+-----------------+

source files : 3
clone's own folder has 0 parquet files
+--------+------+
|order_id|status|
+--------+------+
|1001    |PLACED|
+--------+------+

+--------+------+
|order_id|status|
+--------+------+
|1001    |TEST  |
+--------+------+

clone's own folder now has 1 parquet file(s)
```

`CLONE` returns one row of metrics: `num_copied_files` is "0 for shallow clones" ([Clone a table on Databricks](https://docs.databricks.com/aws/en/tables/operations/clone), last updated Sep 11, 2026). The clone's folder starts empty; its log points at the source's three files. The `UPDATE` wrote one new file into the clone's folder and left the source alone, which makes a shallow clone a cheap place to test a change on production data.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE dev.orders_v1 SHALLOW CLONE silver.orders VERSION AS OF 1;
SELECT count(*) AS rows_at_v1 FROM dev.orders_v1;
DESCRIBE HISTORY dev.orders_shallow;
SHOW TBLPROPERTIES dev.orders_shallow;
CREATE OR REPLACE TABLE dev.orders_shallow SHALLOW CLONE silver.orders;
```

```text
+----------+
|rows_at_v1|
+----------+
|2         |
+----------+

+-------+---------+---------------------------+--------------+
|version|operation|source                     |source_version|
+-------+---------+---------------------------+--------------+
|0      |CLONE    |spark_catalog.silver.orders|2             |
|1      |UPDATE   |NULL                       |NULL          |
+-------+---------+---------------------------+--------------+

clone properties: {'delta.logRetentionDuration': 'interval 60 days', 'quality': 'silver'}
clone description (table comment): None
>>> CREATE OR REPLACE TABLE dev.orders_shallow SHALLOW CLONE silver.orders
   DeltaIllegalStateException: [DELTA_UNSUPPORTED_NON_EMPTY_CLONE] The clone destination table is non-empty. Please TRUNCATE or DELETE FROM the table before running CLONE.
```

(The script prints the two properties set on the source and the `description` column of `DESCRIBE DETAIL`.)

- A clone can start from any version (`VERSION AS OF`, `TIMESTAMP AS OF`).
- **The clone has its own history**, starting at version 0 with a `CLONE` entry that names the source and its version. "A cloned table has an independent history from its source table. Time travel queries on a cloned table don't work with the same inputs as on the source table" (clone page).
- **Copied:** the schema, partitioning and "invariants, nullability" (clone page) and the table properties, which the run confirms (`quality` and the 60-day log retention). **Not copied:** history and Unity Catalog tags (the clone page has an example for both), and the table comment: "Metadata not cloned are the table description, user-defined commit metadata, Delta Lake table history, and Unity Catalog properties, such as tags" (clone page). The run agrees: the clone's `description` is `None`.
- **Replacing a shallow clone.** The open-source engine refused `CREATE OR REPLACE` over the existing clone. Unity Catalog refuses it too: "You cannot use `CREATE OR REPLACE` to overwrite an existing shallow clone. Use `DROP TABLE` followed by `CREATE TABLE`, or use a new table name" ([Shallow clone for Unity Catalog tables](https://docs.databricks.com/aws/en/tables/operations/clone-unity-catalog), last updated Sep 16, 2026). Outside Unity Catalog, the general clone page says the opposite fix for a broken shallow clone: "To repair, run clone with `replace` on the shallow clone."

Shallow clones in Unity Catalog have their own rules (Public Preview; clone-unity-catalog page):

- Managed tables need Databricks Runtime 13.3 LTS and above, external tables 14.3 LTS and above, and a clone is the same kind as its source: managed to managed, external to external.
- "You cannot nest shallow clones", and you "cannot share shallow clones using OpenSharing" (formerly Delta Sharing; see [the OpenSharing announcement](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next)).
- `VACUUM` on the source does not break a Unity Catalog clone, because Unity Catalog tracks the shared files. Outside Unity Catalog it does: "If you run `VACUUM` on the source table, clients can no longer read those data files and this raises a `FileNotFoundException`" (clone page).
- Dropping the source: the clones "keep reading until the base table's data files are deleted", and `UNDROP` on the source during its recovery period saves them. Where the workspace protects base tables, a plain `DROP` fails with `CANNOT_DROP_BASE_TABLE_REFERENCED_BY_SHALLOW_CLONE` and needs `DROP TABLE ... FORCE` ([DROP TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-drop-table)).

### DEEP CLONE

Open-source Delta Lake 4.4.1 has only shallow clone. Both deep-clone spellings fail to parse, and the Python API refuses it too (`DeltaTable.clone(..., isShallow=False)` raised `[DELTA_UNSUPPORTED_DEEP_CLONE] Deep clone is not supported by this Delta version.`). Everything below about deep clones comes from the Databricks pages, not from a run.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> CREATE TABLE dev.orders_deep DEEP CLONE silver.orders
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'DEEP'. SQLSTATE: 42601 (line 1, pos 29)
>>> CREATE TABLE dev.orders_deep2 CLONE silver.orders
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'CLONE'. SQLSTATE: 42601 (line 1, pos 30)
```

*Databricks only, not run here. Syntax from [CREATE TABLE CLONE](https://docs.databricks.com/aws/en/sql/language-manual/delta-clone) and [Clone a table on Databricks](https://docs.databricks.com/aws/en/tables/operations/clone).*

```sql
-- general form
CREATE TABLE [IF NOT EXISTS] table_name
   [SHALLOW | DEEP] CLONE source_table_name [TBLPROPERTIES clause] [LOCATION path]
[CREATE OR] REPLACE TABLE table_name
   [SHALLOW | DEEP] CLONE source_table_name [TBLPROPERTIES clause] [LOCATION path]

-- a full, independent copy; DEEP is the default
CREATE TABLE shop.archive.orders_2026_03 DEEP CLONE shop.silver.orders;
-- freeze the version a model was trained on
CREATE TABLE shop.ml.orders_train CLONE shop.silver.orders VERSION AS OF 15;
-- re-running the clone syncs it incrementally
CREATE OR REPLACE TABLE shop.archive.orders CLONE shop.silver.orders;
```

"When you specify `DEEP CLONE` (default) Databricks will make a complete, independent copy of the source table" ([CREATE TABLE CLONE](https://docs.databricks.com/aws/en/sql/language-manual/delta-clone)), including "stream metadata. A stream that writes to the source table can be stopped and continued on the clone target from where it left off" (clone page). Re-running the clone keeps an archive or disaster-recovery copy in sync: "You can sync deep clones incrementally to maintain an updated state of a source table for disaster recovery", and the page's monthly archive example is `CREATE OR REPLACE TABLE archive_table CLONE my_prod_table` (clone page). Its section on Hive metastore tables adds that for existing Delta tables, "cloning creates a new incremental commit that includes only new metadata and data from the source table since the last clone". Streaming tables and materialized views cannot be the source or target of `CLONE`.

| | Shallow clone | Deep clone | CTAS |
| --- | --- | --- | --- |
| Data files | referenced, not copied | copied | written from the query result |
| Copies schema, partitioning, invariants, nullability, properties (`CHECK` constraints are properties) | yes | yes, plus stream and `COPY INTO` metadata | no; you restate them |
| Copies the table comment, tags | no | no | no |
| History | new, starts with `CLONE` | new, starts with `CLONE` | new |
| Re-run | (Unity Catalog: drop and recreate) | incremental sync | full rewrite |
| Typical use | test or debug on production data | archive, disaster recovery, ML snapshot | reshape the data |

### Time travel and RESTORE

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- orders_m: version 1 wrote four orders, version 2 (the MERGE above) deleted 1001
SELECT count(*) AS rows_now FROM silver.orders_m;
SELECT count(*) AS rows_v1  FROM silver.orders_m VERSION AS OF 1;
RESTORE TABLE silver.orders_m TO VERSION AS OF 1;
SELECT count(*) AS rows_after_restore FROM silver.orders_m;
DESCRIBE HISTORY silver.orders_m;
```

```text
+--------+
|rows_now|
+--------+
|3       |
+--------+

+-------+
|rows_v1|
+-------+
|4      |
+-------+

+------------------+
|rows_after_restore|
+------------------+
|4                 |
+------------------+

+-------+------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|version|operation   |operationParameters                                                                                                                                                 |
+-------+------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|0      |CREATE TABLE|{partitionBy -> [], clusterBy -> [], description -> NULL, isManaged -> true, properties -> {}}                                                                      |
|1      |WRITE       |{mode -> Append, partitionBy -> []}                                                                                                                                 |
|2      |MERGE       |{predicate -> ["(order_id#14874 = order_id#14882)"], matchedPredicates -> [{"actionType":"delete"}], notMatchedPredicates -> [], notMatchedBySourcePredicates -> []}|
|3      |RESTORE     |{version -> 1, timestamp -> NULL}                                                                                                                                   |
+-------+------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------+
```

`VERSION AS OF n` or `TIMESTAMP AS OF <expr>` after a table name reads an old version; `RESTORE TABLE ... TO VERSION AS OF n` (or `TO TIMESTAMP AS OF`) makes it current again as a **new** commit, version 3 here, so the bad version stays in history and the restore itself can be undone. Two limits from [Work with table history](https://docs.databricks.com/aws/en/tables/history) (last updated Nov 6, 2026): "Use only the past 7 days for time travel operations unless you have set both data and log retention configurations to a larger value", and "In Databricks Runtime 18.0 and above, time travel queries are blocked if they request a version older than the `deletedFileRetentionDuration` table property (default 7 days). For Unity Catalog managed tables, this applies to Databricks Runtime 12.2 LTS and above." The mechanics and the DataFrame options (`versionAsOf`, `timestampAsOf`) are in [chapter 4](04-Delta-Lake.md).

### UNDROP

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> UNDROP TABLE dev.orders_v1
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'UNDROP'. SQLSTATE: 42601 (line 1, pos 0)
>>> SHOW TABLES DROPPED IN dev
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'DROPPED'. SQLSTATE: 42601 (line 1, pos 12)
```

*Databricks only, not run here. Syntax from [UNDROP](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-undrop-table) and [Unity Catalog managed tables for Delta Lake and Apache Iceberg](https://docs.databricks.com/aws/en/tables/managed).*

```sql
DROP TABLE shop.silver.orders;
UNDROP TABLE shop.silver.orders;              -- the most recently dropped table of that name

SHOW TABLES DROPPED IN shop.silver;           -- several dropped tables with one name: find the ID
UNDROP TABLE WITH ID '6ca7be55-8f58-47a7-85ee-7a59082fd17a';

ALTER CATALOG shop RETAIN DROPPED TO 30 DAYS; -- recovery period (Public Preview)
ALTER SCHEMA shop.silver RETAIN DROPPED TO 7 DAYS;
```

From the UNDROP page (last updated Nov 5, 2026) and the DROP TABLE page:

- "Applies to: Databricks SQL Databricks Runtime 12.2 LTS and above", for managed and external tables, materialized views and streaming tables in Unity Catalog. "By default, this feature supports recovering dropped relations within a 7 day recovery period." The period can be set per catalog or schema "to 0 (to disable recovery) or 7 to 30 days" (Public Preview), and the schema setting wins.
- If a table with the same name exists, rename it first. Privileges, column spec and properties come back; "Primary and foreign key constraints are not recovered by the `UNDROP` command."
- A materialized view or streaming table "created with Databricks SQL" cannot be undropped; one created by a pipeline can, while its pipeline still exists. Temporary tables cannot be undropped.
- After the period, "An asynchronous purge process permanently deletes the underlying data files" of a managed table.

!!! tip "In the interview"
    **"Someone ran a bad UPDATE on silver.orders an hour ago; someone else dropped gold.daily_revenue. Recover both."** For the update: find the version before it in `DESCRIBE HISTORY`, check it with `SELECT ... VERSION AS OF n`, then `RESTORE TABLE silver.orders TO VERSION AS OF n` (a new commit; the bad version stays in history). For the drop: `UNDROP TABLE gold.daily_revenue` within the recovery period (7 days by default, Unity Catalog only); re-add any primary or foreign keys afterwards. For a test copy of production use a shallow clone; for a backup that survives `VACUUM` and source deletion, a deep clone.

## 20.11 Views, temporary views, materialized views and streaming tables
*Level: intermediate.*

A **view** stores a query; every read runs it. A **temporary view** is the same but lives only in the session. A **materialized view** stores the query's result and refreshes it. A **streaming table** is a Delta table that a streaming query appends to, processing each input row once. Views as a programming tool (dynamic views, row filters, column masks) are in [chapter 21](21-Programming-in-SQL.md); pipelines that build materialized views and streaming tables are in [chapter 13](13-Declarative-Pipelines.md).

### Views and temporary views

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE VIEW silver.v_open_orders
COMMENT 'Orders not yet shipped'
AS SELECT order_id, customer_id, amount FROM silver.orders WHERE status = 'PLACED';

CREATE OR REPLACE TEMP VIEW big_orders AS
SELECT * FROM silver.orders WHERE amount > 50;

SELECT * FROM silver.v_open_orders ORDER BY order_id;
SHOW VIEWS IN silver;
SHOW VIEWS;
CREATE VIEW silver.v_open_orders AS SELECT 1 AS x;
CREATE VIEW IF NOT EXISTS silver.v_open_orders AS SELECT 1 AS x;
CREATE OR REPLACE VIEW IF NOT EXISTS silver.v_x AS SELECT 1 AS x;
```

```text
+--------+-----------+------+
|order_id|customer_id|amount|
+--------+-----------+------+
|1001    |7          |59.90 |
|1003    |7          |15.50 |
+--------+-----------+------+

+---------+-------------+-----------+
|namespace|viewName     |isTemporary|
+---------+-------------+-----------+
|silver   |v_open_orders|false      |
|         |big_orders   |true       |
+---------+-------------+-----------+

+---------+----------+-----------+
|namespace|viewName  |isTemporary|
+---------+----------+-----------+
|         |big_orders|true       |
+---------+----------+-----------+

>>> CREATE VIEW silver.v_open_orders AS SELECT 1 AS x
   AnalysisException: [TABLE_OR_VIEW_ALREADY_EXISTS] Cannot create table or view `spark_catalog`.`silver`.`v_open_orders` because it already exists.
>>> CREATE VIEW IF NOT EXISTS silver.v_open_orders AS SELECT 1 AS x
OK
>>> CREATE OR REPLACE VIEW IF NOT EXISTS silver.v_x AS SELECT 1 AS x
   ParseException: [CREATE_VIEW_WITH_IF_NOT_EXISTS_AND_REPLACE] CREATE VIEW silver.v_x with both IF NOT EXISTS and REPLACE is not allowed. SQLSTATE: 42601
```

- `SHOW VIEWS` lists temporary views in every schema listing (empty `namespace`, `isTemporary` true).
- `IF NOT EXISTS` on an existing view does nothing, silently: the view still has its old query. `OR REPLACE` and `IF NOT EXISTS` together are an error.
- Where a temporary view lives depends on the tool: "In notebooks and jobs, temporary views are scoped to the notebook or script level", and "In Databricks SQL, temporary views are scoped to the query level. Multiple statements within the same query can use the temp view, but it cannot be referenced in other queries, even within the same dashboard" ([What is a view?](https://docs.databricks.com/aws/en/views/), last updated Oct 15, 2026). A temporary view "is created in the `system.session` schema" ([CREATE VIEW](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-view)). Global temporary views (`global_temp`) are a legacy feature.

In PySpark, `df.createOrReplaceTempView("big_orders")` makes the same temporary view.

### When the table under a view changes

A view stores its column list at creation. What happens when the table gains a column depends on the view's **schema binding** mode (Databricks Runtime 15.3 and above, CREATE VIEW page):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE VIEW silver.v_star AS SELECT * FROM silver.orders;
CREATE VIEW silver.v_star_evo WITH SCHEMA EVOLUTION AS SELECT * FROM silver.orders;
ALTER TABLE silver.orders ADD COLUMN channel STRING;
```

```text
v_star columns     : ['order_id', 'customer_id', 'order_date', 'status', 'amount', 'currency']
v_star_evo columns : ['order_id', 'customer_id', 'order_date', 'status', 'amount', 'currency', 'channel']
  v_star_evo Type = VIEW
  v_star_evo View Schema Mode = EVOLUTION
  v_star View Schema Mode = COMPENSATION
```

| Mode | What the view does when the query's columns change |
| --- | --- |
| `BINDING` | invalid, except extra columns from `*` (ignored) and type changes that implicit casting can absorb |
| `COMPENSATION` (default) | the same, but type changes are allowed if an explicit ANSI cast can convert them |
| `TYPE EVOLUTION` | adopts type changes into its definition |
| `EVOLUTION` | also adopts renamed, added and dropped columns, if the view has no explicit column list |

So `SELECT *` in a default view does **not** pick up new columns; `v_star` kept six. Recreate the view, or create it `WITH SCHEMA EVOLUTION`. The clause is "not supported for temporary views, metric views, or materialized views".

### Materialized views and streaming tables

Open-source Spark 4.2 knows the statements but runs them only inside a pipeline:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> CREATE MATERIALIZED VIEW silver.mv_daily AS SELECT order_date, sum(amount) AS revenue FROM silver.orders GROUP BY ALL
   UnsupportedOperationException: [UNSUPPORTED_FEATURE.CREATE_PIPELINE_DATASET_QUERY_EXECUTION] The feature is not supported: Direct execution of a CREATE ... MATERIALIZED VIEW query. To create a pipeline dataset, create and execute a pipeline with a SQL file containing your query attached in
>>> CREATE STREAMING TABLE silver.st_orders AS SELECT * FROM STREAM(silver.orders)
   UnsupportedOperationException: [UNSUPPORTED_FEATURE.CREATE_PIPELINE_DATASET_QUERY_EXECUTION] The feature is not supported: Direct execution of a CREATE ... STREAMING TABLE query. To create a pipeline dataset, create and execute a pipeline with a SQL file containing your query attached in th
```

On Databricks you can create both straight from the SQL editor; Databricks then runs a pipeline for you: "Create and refresh operations on materialized views and streaming tables are powered by serverless Lakeflow pipelines" ([CREATE MATERIALIZED VIEW](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-materialized-view), last updated Oct 15, 2026). Lakeflow pipelines were formerly called Delta Live Tables ([What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)).

*Databricks only, not run here. Syntax from [CREATE MATERIALIZED VIEW](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-materialized-view) and [CREATE STREAMING TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-streaming-table).*

```sql
CREATE OR REPLACE MATERIALIZED VIEW shop.gold.daily_revenue
  CLUSTER BY (order_date)
  SCHEDULE EVERY 1 HOUR
AS SELECT CAST(order_ts AS DATE) AS order_date, currency, sum(amount) AS revenue
   FROM shop.silver.orders
   GROUP BY ALL;

CREATE OR REFRESH STREAMING TABLE shop.bronze.orders_raw
AS SELECT * FROM STREAM read_files('s3://red-rock/raw/orders/', format => 'json');

REFRESH MATERIALIZED VIEW shop.gold.daily_revenue;
```

| | View | Materialized view | Streaming table |
| --- | --- | --- | --- |
| Stores data | no | yes, the query result | yes, appended rows |
| Freshness | always current | as of the last refresh | as of the last refresh |
| Each read costs | the full query | a table read | a table read |
| Created where | anywhere | Pro or Serverless SQL warehouse, or a pipeline | a pipeline, or Databricks SQL with Unity Catalog |
| Refresh | none | `REFRESH`, `SCHEDULE`, `TRIGGER ON UPDATE` | `REFRESH`, `SCHEDULE`, `TRIGGER ON UPDATE` |
| Typical layer | thin access layer | gold aggregates | bronze ingestion |

Facts behind the table: "Materialized views can only be created using a Pro or Serverless SQL warehouse, or within a pipeline" (CREATE MATERIALIZED VIEW); "Streaming tables are only supported in Lakeflow pipelines and on Databricks SQL with Unity Catalog. Running this command on supported Databricks Runtime compute only parses the syntax" ([CREATE STREAMING TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-streaming-table), last updated Nov 10, 2026). A materialized view refresh can be incremental when the query allows it; [chapter 13](13-Declarative-Pipelines.md) covers refresh modes and `TRIGGER ON UPDATE`.

!!! tip "In the interview"
    **"View, materialized view or streaming table for a gold revenue table?"** A view recomputes on every read: fine for light queries, costly for a dashboard that aggregates millions of rows. A materialized view stores the aggregate and refreshes it on a schedule or when sources change, often incrementally: the usual gold choice. A streaming table is for append-style ingestion (bronze, or silver fed by a stream), processing each new row once. Both are managed by Lakeflow pipelines, formerly Delta Live Tables ([rename](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)), even when created from the SQL editor.

## 20.12 DESCRIBE, SHOW and comments
*Level: intermediate.*

When you inherit a table, five statements tell you what it is: `DESCRIBE TABLE [EXTENDED]` (columns and metadata), `DESCRIBE DETAIL` (one row of Delta facts), `DESCRIBE HISTORY` (every commit), `SHOW TBLPROPERTIES` and `SHOW CREATE TABLE`. Comments are what you leave for the next person.

### Comments

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
COMMENT ON TABLE silver.orders IS 'Cleaned orders, one row per order';
COMMENT ON COLUMN silver.orders.amount IS 'Order total in currency';
ALTER TABLE silver.orders ALTER COLUMN currency COMMENT 'ISO 4217 code';
DESCRIBE TABLE silver.orders;
```

```text
>>> COMMENT ON COLUMN silver.orders.amount IS 'Order total in currency'
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'COLUMN'. SQLSTATE: 42601 (line 1, pos 11)
+-----------+-------------+-------------+
|col_name   |data_type    |comment      |
+-----------+-------------+-------------+
|order_id   |int          |NULL         |
|customer_id|int          |NULL         |
|order_date |date         |NULL         |
|status     |string       |NULL         |
|amount     |decimal(10,2)|NULL         |
|currency   |string       |ISO 4217 code|
|channel    |string       |NULL         |
+-----------+-------------+-------------+
```

`COMMENT ON TABLE` works on both engines. `COMMENT ON COLUMN` is "Applies to: Databricks SQL Databricks Runtime 16.1 and above" ([COMMENT ON](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-comment), last updated Oct 9, 2026); the open-source parser does not have it, but `ALTER TABLE ... ALTER COLUMN ... COMMENT` does the same everywhere. Table comments can also be given at creation (`COMMENT '...'`) and are what `DESCRIBE DETAIL` shows as `description`. In Unity Catalog, comments are searchable and appear in Catalog Explorer.

### DESCRIBE TABLE EXTENDED

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
DESCRIBE TABLE EXTENDED silver.orders;
DESCRIBE TABLE EXTENDED silver.orders AS JSON;
```

```text
  # Detailed Table Information   
  Catalog                        spark_catalog
  Namespace                      silver
  Database                       silver
  Table                          orders
  Type                           MANAGED
  Comment                        Cleaned orders, one row per order
  Location                       <work>/warehouse/silver.db/orders
  Provider                       delta
  Is_managed_location            true
  Table Properties               [delta.logRetentionDuration=interval 60 days,delta.minReaderVersion=1,delta.minWriterVersi

>>> DESCRIBE TABLE EXTENDED silver.orders AS JSON
   AnalysisException: [NOT_SUPPORTED_COMMAND_FOR_V2_TABLE] DESCRIBE TABLE AS JSON is not supported for v2 tables. SQLSTATE: 0A000
```

(The script prints only the block after `# Detailed Table Information` and cuts long values at 90 characters.) `EXTENDED` adds the metadata block: catalog, schema, type (`MANAGED`, `EXTERNAL`, `VIEW`), comment, location, provider and properties; for a partitioned table a `# Partition Information` section comes first. Do not parse this text in code: "The non-JSON output of `DESCRIBE TABLE` can change, and new columns might be appended over time ... For programmatic consumption, use `DESCRIBE TABLE ... AS JSON`" ([DESCRIBE TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-describe-table), last updated Oct 29, 2026). `AS JSON` is "Applies to: Databricks SQL Databricks Runtime 16.2 and above" and "Only supported when `EXTENDED` format is specified"; open-source Spark refuses it for Delta (a "v2" table to Spark).

### DESCRIBE DETAIL and DESCRIBE HISTORY

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT format, name, description, numFiles, sizeInBytes > 0 AS has_bytes, minReaderVersion, minWriterVersion
FROM (DESCRIBE DETAIL silver.orders);
SELECT version, operation, operationParameters, operationMetrics['numOutputRows'] AS rows
FROM (DESCRIBE HISTORY silver.orders) ORDER BY version;
```

```text
+------+---------------------------+---------------------------------+--------+---------+----------------+----------------+
|format|name                       |description                      |numFiles|has_bytes|minReaderVersion|minWriterVersion|
+------+---------------------------+---------------------------------+--------+---------+----------------+----------------+
|delta |spark_catalog.silver.orders|Cleaned orders, one row per order|3       |true     |1               |2               |
+------+---------------------------+---------------------------------+--------+---------+----------------+----------------+

+-------+-----------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----+
|version|operation        |operationParameters                                                                                                                                                       |rows|
+-------+-----------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----+
|0      |CREATE TABLE     |{partitionBy -> [], clusterBy -> [], description -> Cleaned orders, isManaged -> true, properties -> {"delta.logRetentionDuration":"interval 60 days","quality":"silver"}}|NULL|
|1      |WRITE            |{mode -> Append, partitionBy -> []}                                                                                                                                       |2   |
|2      |WRITE            |{mode -> Append, partitionBy -> []}                                                                                                                                       |1   |
|3      |ADD COLUMNS      |{columns -> [{"column":{"name":"channel","type":"string","nullable":true,"metadata":{}}}]}                                                                                |NULL|
|4      |SET TBLPROPERTIES|{properties -> {"comment":"Cleaned orders, one row per order"}}                                                                                                           |NULL|
|5      |CHANGE COLUMN    |{column -> {"name":"currency","type":"string","nullable":true,"metadata":{"comment":"ISO 4217 code"}}}                                                                    |NULL|
+-------+-----------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----+
```

The script runs these through `sql(...).selectExpr(...)`; the SQL above is the same query. `DESCRIBE DETAIL` is one row with the format, location, `numFiles`, `sizeInBytes`, `partitionColumns`, `clusteringColumns`, protocol and `tableFeatures` ([Review table details with describe detail](https://docs.databricks.com/aws/en/tables/operations/table-details)); it is the quickest check for small files (`sizeInBytes / numFiles`). `DESCRIBE HISTORY` lists each commit with its operation, parameters, metrics, user and time; "Table history is retained for 30 days" by default ([DESCRIBE HISTORY](https://docs.databricks.com/aws/en/sql/language-manual/delta-describe-history)). Note that `COMMENT ON TABLE` shows up as `SET TBLPROPERTIES` with a `comment` key, and a column comment as `CHANGE COLUMN`: every metadata change is a commit. The PySpark equivalents are `DeltaTable.forName(spark, "silver.orders").detail()` and `.history()`.

### SHOW CREATE TABLE

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> SHOW CREATE TABLE silver.orders
   AnalysisException: [DELTA_OPERATION_NOT_ALLOWED] Operation not allowed: `SHOW CREATE TABLE` is not supported for Delta tables;
>>> SHOW CREATE TABLE silver.v_open_orders
OK
CREATE VIEW silver.v_open_orders (
  order_id,
  customer_id,
  amount)
COMMENT 'Orders not yet shipped'
WITH SCHEMA COMPENSATION
AS SELECT order_id, customer_id, amount FROM silver.orders WHERE status = 'PLACED'

>>> SHOW CREATE TABLE big_orders
   AnalysisException: [EXPECT_PERMANENT_VIEW_NOT_TEMP] 'SHOW CREATE TABLE' expects a permanent view but `big_orders` is a temp view. SQLSTATE: 42809; line 1 pos 18
```

Open-source Delta does not support `SHOW CREATE TABLE` on a Delta table; Databricks does, and it is the fastest way to copy a table's DDL into a migration script (it "Returns the statement that was used to create a given table or view"; the Constraints page also names it as one way to see a table's constraints). On materialized views and streaming tables it needs Databricks Runtime 14.1 or above ([SHOW CREATE TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-show-create-table)). For views it works on both engines and shows the stored column list and schema binding mode; temporary views have no stored DDL.

!!! tip "In the interview"
    **"You inherit a table nobody documented. What do you run?"** `DESCRIBE TABLE EXTENDED` for columns, type (managed or external), location and properties; `DESCRIBE DETAIL` for file count, size, partitioning or clustering and the protocol and features; `DESCRIBE HISTORY` for who writes to it, how often and with which operations (and whether someone ran `OPTIMIZE` or `VACUUM`); `SHOW CREATE TABLE` for the DDL to recreate it. For anything a program parses, use `DESCRIBE TABLE EXTENDED ... AS JSON` (Databricks Runtime 16.2 and above), since the text layout can change.

## 20.13 Expert notes: protocols, engine differences and where the docs disagree
*Level: expert.*

### What each DDL choice does to the protocol

Every run in this chapter printed the table's protocol from `DESCRIBE DETAIL`. Collected in one place (open-source Delta 4.4.1; the Databricks pages are quoted where they say something different):

| Table created with | minReader / minWriter here | Features added | Note |
| --- | --- | --- | --- |
| plain columns, `NOT NULL` | 1 / 2 | `appendOnly`, `invariants` | the baseline |
| `CHECK` constraint | 1 / 3 | `checkConstraints` | |
| `DEFAULT` | 1 / 7 | `allowColumnDefaults` | open source needs the feature set explicitly (section 20.3) |
| generated column | 1 / 7 | `generatedColumns` | |
| identity column | 1 / 7 | `identityColumns` | |
| `CLUSTER BY` | 1 / 7 | `clustering`, `domainMetadata` | Databricks: "writer version 7 and reader version 3" |
| column mapping | 2 / 7 | `columnMapping` | Databricks: "reader version 2 or above, and writer version 5 or above" |
| change data feed and deletion vectors | 3 / 7 | `changeDataFeed`, `deletionVectors` | |
| type widening | 3 / 7 | `typeWidening` | readable only by Databricks Runtime 15.4 LTS and above |

Reader version 1 means any Delta reader can read the table; reader 3 means the reader must support each listed feature. Before enabling a feature on a table that Trino, an older runtime or another tool reads, check the feature against that client ([Delta Lake feature compatibility and protocols](https://docs.databricks.com/aws/en/tables/features/feature-compatibility)).

### Open-source engine versus Databricks

The open-source engine ran most of this chapter. These are the places where it did something different from what the Databricks pages document:

| Statement | Open-source Spark 4.2 + Delta 4.4.1 | Databricks (page) |
| --- | --- | --- |
| `USING` omitted | Parquet table | Delta table (CREATE TABLE [USING]) |
| `DEFAULT` | needs `delta.feature.allowColumnDefaults` | documented without it; not verified |
| `ALTER COLUMN ... SET NOT NULL` | refused | supported (Constraints) |
| `PRIMARY KEY`, `FOREIGN KEY` | refused | informational, Unity Catalog |
| `CLUSTER BY AUTO`, `REPLACE PARTITIONED BY` | parse error | 15.4 / 18.1 and above |
| DataFrame `clusterBy` | refused; `DeltaTable` builder works | all three APIs (clustering page) |
| `DELETE`/`UPDATE` with a subquery | refused | supported, with exceptions |
| `REPLACE USING`, `REPLACE ON` in SQL | refused | 16.3 / 17.1 and above |
| `replaceUsing` writer option | works | documented for 18.2 and above |
| `INSERT WITH SCHEMA EVOLUTION` | works | 18.1 and above |
| `MERGE ... * EXCEPT` | parse error | 12.2 LTS and above |
| `NOT MATCHED BY SOURCE` with a source column | internal error | analysis error |
| `DEEP CLONE` | parse error; Python API `DELTA_UNSUPPORTED_DEEP_CLONE` (only shallow clone exists) | supported (default kind of `CLONE`) |
| `COMMENT ON COLUMN` | parse error | 16.1 and above |
| `DESCRIBE ... AS JSON` | refused | 16.2 and above |
| `SHOW CREATE TABLE` on Delta | refused | supported |
| `UNDROP`, tags, `TEMP TABLE` | errors | Unity Catalog / 18.1 and above |
| `CREATE MATERIALIZED VIEW`, `STREAMING TABLE` | only inside a pipeline | from a SQL warehouse too |

### Where the Databricks pages disagree

Shown in the sections above; collected here because an interviewer may quote either version:

1. **Key constraints status** (section 20.4): GA in 15.2 on the Constraints page; "Public Preview" banner on the ADD CONSTRAINT page.
2. **Default of a new column with `DEFAULT`** (section 20.3): the ALTER TABLE ... COLUMN page contradicts itself.
3. **Liquid clustering version** (section 20.5): 13.3 LTS on the CLUSTER BY clause page, GA 15.4 LTS on the clustering page.
4. **`MERGE WITH SCHEMA EVOLUTION`** (section 20.9): 15.2 on the MERGE INTO page, 15.4 LTS on the schema evolution page.
5. **Partition columns in a CTAS** (section 20.5): the docs say they move to the end; open source kept the query order. Not verified on Databricks.
6. **`UPDATE SET * EXCEPT`** (section 20.9): the pages say excluded columns are set to `NULL`. Not verified.
7. **Replacing a shallow clone** (section 20.10): "run clone with `replace`" on the general clone page; not allowed for Unity Catalog shallow clones.

### Three habits that prevent incidents

- **Prefer `CREATE OR REPLACE` to `DROP` and `CREATE`.** The replace is one commit: readers never see a missing table, and the history (and time travel to the old data) survives (section 20.2).
- **Make loads idempotent.** A job that appends will duplicate on rerun. `REPLACE WHERE`, `REPLACE USING` or a `MERGE` on a deduplicated batch give the same table after one run or three ([Duplicates and incremental loads](../../databases/sql/22-Duplicates-and-Incremental-Loads.md)).
- **Treat properties and features as schema changes.** They conflict with concurrent writers and can lock out readers, so they belong in a reviewed migration, not in an ad hoc notebook cell.

## 20.14 Practice questions
*Level: all levels.*

Questions marked "run here" have answers that come from the chapter's scripts (`src/ch20/`).

**Q1. You drop a managed table and an external table in Unity Catalog. What happens to the data files of each, and can you get either table back?**

??? success "Answer"
    The managed table's catalog entry goes away at once, but its files stay for the recovery period (7 days by default, configurable to 0 or 7 to 30 days), during which `UNDROP TABLE` restores it; after that an asynchronous purge deletes the files. The external table's entry goes away and its files stay at the `LOCATION` for good; `UNDROP` can also restore the entry within the recovery period, and otherwise you recreate the table over the same path.

    **Why:** Unity Catalog owns a managed table's storage and lifecycle; for an external table it owns only the metadata ([DROP TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-drop-table), [UNDROP](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-undrop-table)).

**Q2. A nightly job runs `DROP TABLE gold.daily_revenue; CREATE TABLE gold.daily_revenue AS SELECT ...`. Give two reasons to replace it with `CREATE OR REPLACE TABLE ... AS SELECT`.**

??? success "Answer"
    1. `CREATE OR REPLACE` is a single commit: a query running at the same time sees the old table or the new one, never "table not found" or an empty table.
    2. It keeps the table's history, so yesterday's data stays reachable with time travel (and `RESTORE`) until retention removes it. A `DROP` starts a new table with no history. The replace also keeps "the table identity" ([Drop or replace a table](https://docs.databricks.com/aws/en/tables/operations/drop-table)).

    **Why:** section 20.2 shows the history of a replaced table continuing from the old versions.

**Q3. (Run here.) Why does this fail, and how do you get a table with an identity key filled from `silver.customer_keys`?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.ck2 (sk BIGINT GENERATED ALWAYS AS IDENTITY, name STRING)
USING DELTA AS SELECT name FROM silver.customer_keys;
```

??? success "Answer"
    ```text
    ParseException: Operation not allowed: Schema may not be specified in a Create Table As Select (CTAS) statement.
    ```

    A CTAS takes its schema from the query, so it cannot declare an identity column (or a generated column, default or constraint). Create the table first, then load it:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    CREATE TABLE silver.ck2 (sk BIGINT GENERATED ALWAYS AS IDENTITY, name STRING) USING DELTA;
    INSERT INTO silver.ck2 (name) SELECT name FROM silver.customer_keys;
    ```

    ```text
       rows: 3 | distinct sk: 3
    ```

    **Why:** column properties need a column list; `ch20_02_columns.out`, section 6.

**Q4. What does `CREATE TABLE silver.orders_empty LIKE silver.orders` copy from a Delta source, and what does it not?**

??? success "Answer"
    It creates an empty table with the source's columns, comment, partition columns, table properties, table constraints and Delta protocol. It does not copy the rows, row filters, column masks, governed tags or access controls. The run here confirmed zero rows, the properties and the comment.

    **Why:** the [CREATE TABLE LIKE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-like) page lists what carries over (section 20.2). Use `LIKE` for an empty staging table with the same definition; use a clone when you also want the data.

**Q5. (Run here.) Write the DDL for `silver.orders`: `order_id` required, `order_ts` required, `order_date` derived from `order_ts`, `status` defaulting to `PLACED`, `currency` defaulting to `CAD`, amounts never negative, clustered for queries by date and customer, with change data feed on.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    CREATE TABLE silver.orders (
      order_id    INT           NOT NULL COMMENT 'business key from the shop',
      customer_id INT,
      order_ts    TIMESTAMP     NOT NULL,
      order_date  DATE          GENERATED ALWAYS AS (CAST(order_ts AS DATE)),
      status      STRING        DEFAULT 'PLACED',
      amount      DECIMAL(10,2),
      currency    STRING        DEFAULT 'CAD')
    USING DELTA
    CLUSTER BY (order_date, customer_id)
    COMMENT 'Cleaned Red Rock Supply orders, one row per order'
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true',
                   'delta.feature.allowColumnDefaults' = 'supported');
    ALTER TABLE silver.orders ADD CONSTRAINT amount_not_negative CHECK (amount >= 0);

    INSERT INTO silver.orders (order_id, customer_id, order_ts, amount)
    VALUES (1001, 7, TIMESTAMP'2026-03-01 10:15:00', 59.90);
    SELECT * FROM silver.orders;
    INSERT INTO silver.orders (order_id, customer_id, order_ts, amount)
    VALUES (1002, 3, TIMESTAMP'2026-03-01 11:02:00', -5.00);
    ```

    ```text
    +--------+-----------+-------------------+----------+------+------+--------+
    |order_id|customer_id|order_ts           |order_date|status|amount|currency|
    +--------+-----------+-------------------+----------+------+------+--------+
    |1001    |7          |2026-03-01 10:15:00|2026-03-01|PLACED|59.90 |CAD     |
    +--------+-----------+-------------------+----------+------+------+--------+

    >>> INSERT INTO silver.orders (order_id, customer_id, order_ts, amount) VALUES (1002, 3, TIMESTAMP'2026-03-01 11:02:00', -5.00)
       DeltaInvariantViolationException: [DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint amount_not_negative (amount >= 0) violated by row with values:
          - amount : -5.00
    clusteringColumns: ['order_date', 'customer_id'] | features: ['allowColumnDefaults', 'appendOnly', 'changeDataFeed', 'checkConstraints', 'clustering', 'domainMetadata', 'generatedColumns', 'invariants']
    ```

    The `CHECK` is added with `ALTER TABLE` because the open-source engine refused it inside `CREATE TABLE` (section 20.4), and the `allowColumnDefaults` feature line is needed here for `DEFAULT` (section 20.3; whether Databricks needs it is not verified). On Databricks you would also drop the generated `order_date` and cluster by `order_ts` directly, as the clustering page advises; it is kept here to show both column kinds.

    **Why:** each clause maps to one requirement, and the run shows the defaults and the generated date filled in and the negative amount rejected.

**Q6. (Run here.) What does the last query print?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.product_keys (
  product_sk BIGINT GENERATED BY DEFAULT AS IDENTITY (START WITH 100 INCREMENT BY 10),
  product_id INT) USING DELTA;
INSERT INTO silver.product_keys (product_id) VALUES (1);
INSERT INTO silver.product_keys VALUES (7, 2);
INSERT INTO silver.product_keys (product_id) VALUES (3);
SELECT * FROM silver.product_keys ORDER BY product_id;
```

??? success "Answer"
    ```text
    +----------+----------+
    |product_sk|product_id|
    +----------+----------+
    |100       |1         |
    |7         |2         |
    |110       |3         |
    +----------+----------+
    ```

    **Why:** `BY DEFAULT` accepts the explicit 7; generated values continue from the identity's own high-water mark (100, then 110), not from the explicit value. With `GENERATED ALWAYS` the second insert would fail with `DELTA_IDENTITY_COLUMNS_EXPLICIT_INSERT_NOT_SUPPORTED`. After loading explicit values above the high-water mark, run `ALTER TABLE ... ALTER COLUMN product_sk SYNC IDENTITY`.

**Q7. Two jobs append to `silver.dim_customer`, which has `customer_sk BIGINT GENERATED ALWAYS AS IDENTITY`. What goes wrong, and what are your options?**

??? success "Answer"
    The jobs conflict: "Declaring an identity column on a Delta Lake table disables concurrent transactions" ([Delta Lake generated columns](https://docs.databricks.com/aws/en/tables/features/generated-columns); [CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using) says the same "on a table"), so one of two overlapping appends fails. Options: let one job own all writes (for example, the other job writes to staging and the owner merges it), or drop the sequence and derive the key from the business key, for example `xxhash64(customer_id)`.

    **Why:** identity values must stay unique across all writers, and Delta guarantees that by not allowing concurrent transactions on the table. Values are also not guaranteed to be consecutive, so never rely on "no gaps".

**Q8. Can a column `loaded_at TIMESTAMP GENERATED ALWAYS AS (current_timestamp())` record when each row was loaded?**

??? success "Answer"
    No. The run gave `[DELTA_UNSUPPORTED_EXPRESSION_GENERATED_COLUMN] current_timestamp() cannot be used in a generated column`. Generated columns must be deterministic functions of other columns of the same row. Use `loaded_at TIMESTAMP DEFAULT current_timestamp()` or set the value in the `SELECT` of the load.

    **Why:** a generated column must give the same value whenever it is recomputed (Delta checks a supplied value against the expression), which a clock function cannot (`ch20_02_columns.out`, section 4).

**Q9. (Run here.) `order_items` has `CHECK (qty > 0)`. What happens to `INSERT INTO silver.order_items VALUES (1003, 2, NULL, 39.95)`?**

??? success "Answer"
    It fails:

    ```text
    DeltaInvariantViolationException: [DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint qty_positive (qty > 0) violated by row with values:
       - qty : null
    ```

    **Why:** in Databricks a `CHECK` must evaluate to `true`; `NULL > 0` is unknown, so it fails. In standard SQL an unknown `CHECK` passes. If `NULL` is allowed, write `CHECK (qty IS NULL OR qty > 0)`.

**Q10. A colleague declared `PRIMARY KEY (order_id)` on `shop.silver.orders` and says duplicates are now impossible. Are they right?**

??? success "Answer"
    No. Databricks does not enforce primary key, foreign key or unique constraints; a duplicate `order_id` is accepted. Keys are informational: they document the model and, with `RELY`, let the optimizer rewrite queries. Uniqueness must come from the pipeline (deduplicate, then `MERGE` on the key) and be tested (`GROUP BY order_id HAVING count(*) > 1`).

    **Why:** [CONSTRAINT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-constraint), section 20.4. Only `NOT NULL` and `CHECK` are enforced.

**Q11. What does `RELY` on a primary key do, and what is the risk?**

??? success "Answer"
    It tells the optimizer it may assume the constraint holds and use it to rewrite queries (for example remove a redundant `DISTINCT` or join). If the data actually has duplicates, those rewritten queries return wrong results, silently. Only declare `RELY` when the pipeline guarantees the key; the optimizations need pro or serverless SQL warehouses or serverless compute.

    **Why:** "Relying on a constraint that is not satisfied may lead to incorrect query results" ([CONSTRAINT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-constraint)).

**Q12. A new 200 GB `orders` table is queried by date range and by customer. Partition by date, or cluster?**

??? success "Answer"
    Cluster: `CLUSTER BY (order_ts, customer_id)`, or `CLUSTER BY AUTO` on a Unity Catalog managed table. Do not partition.

    **Why:** the partitioning page says "With less than 1 TB of data, don't partition", and each partition should hold at least 1 GB; daily partitions of a 200 GB table would be small and many. Clustering serves both filters and its keys can change later ([When to partition tables on Databricks](https://docs.databricks.com/aws/en/tables/partitions)).

**Q13. You run `ALTER TABLE silver.orders CLUSTER BY (order_ts)` on a table clustered by `customer_id`. Is the existing data rewritten? How do you recluster it?**

??? success "Answer"
    No. Changing keys is a metadata commit (`CLUSTER BY` in the history); "existing data is not rewritten", and new writes and `OPTIMIZE` use the new keys. A plain `OPTIMIZE` is incremental; `OPTIMIZE silver.orders FULL` (Databricks Runtime 16.0 and above; it also ran here) reclusters existing files with the new keys, and `OPTIMIZE ... FULL WHERE <predicate>` (18.1 and above) does it for a slice.

    **Why:** [Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering); runs in section 20.5.

**Q14. (Run here.) What happens?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.bad1 (order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING,
  amount DECIMAL(10,2), currency STRING)
USING DELTA PARTITIONED BY (status) CLUSTER BY (customer_id);
```

??? success "Answer"
    ```text
    ParseException: Operation not allowed: Clustering and partitioning cannot both be specified. Please remove PARTITIONED BY if you want to create a Delta table with clustering.
    ```

    **Why:** clustering "is not compatible with partitioning or `ZORDER`". Likewise `ALTER TABLE ... CLUSTER BY` on a partitioned table fails (`DELTA_ALTER_TABLE_CLUSTER_BY_ON_PARTITIONED_TABLE_NOT_ALLOWED`); on Databricks Runtime 18.1 and above convert with `ALTER TABLE ... REPLACE PARTITIONED BY WITH CLUSTER BY (...)`, otherwise rebuild with a CTAS.

**Q15. You want to cluster a 60-column table by `region_code`, which is column 45. What two limits do you check?**

??? success "Answer"
    1. At most four clustering keys.
    2. Clustering keys must have statistics, and by default Delta collects them for the first 32 columns only. Column 45 has none, so first raise `delta.dataSkippingNumIndexedCols` or list the column in `delta.dataSkippingStatsColumns`, which "takes precedence over `dataSkippingNumIndexedCols`" ([Table properties reference](https://docs.databricks.com/aws/en/tables/table-properties)).

    **Why:** "Clustering keys must be columns that have statistics collected. By default, Delta Lake tables collect statistics for the first 32 columns" (clustering page).

**Q16. (Run here.) `orders_part` is partitioned by `order_date DATE GENERATED ALWAYS AS (CAST(order_ts AS DATE))`. A query filters only on `order_ts >= '2026-03-02'`. Are partitions pruned?**

??? success "Answer"
    Yes. The plan contains:

    ```text
    PartitionFilters: [((order_date#1625 >= 2026-03-02) OR isnull((order_date#1625 >= 2026-03-02)))]
    ```

    **Why:** "When you partition a table using a generated column and query on the base column, Delta Lake automatically derives partition filters if possible" ([Delta Lake generated columns](https://docs.databricks.com/aws/en/tables/features/generated-columns)). The `OR isnull` keeps a possible `NULL` partition so no row is lost.

**Q17. (Run here.) A table has `'delta.appendOnly' = 'true'`. What does `DELETE FROM silver.order_events WHERE order_id = 1001` do, and how do you allow it?**

??? success "Answer"
    ```text
    UnsupportedOperationException: [DELTA_CANNOT_MODIFY_APPEND_ONLY] This table is configured to only allow appends. ...
    ```

    `UPDATE` fails the same way (and so would a `MERGE` that updates or deletes). Allow it with `ALTER TABLE silver.order_events SET TBLPROPERTIES ('delta.appendOnly' = 'false')`; the next `DELETE` worked.

    **Why:** `delta.appendOnly = true` "disable[s] `UPDATE` and `DELETE` operations" ([Table properties and table options](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-tblproperties)). Changing it is itself a commit that conflicts with concurrent writes.

**Q18. (Run here.) Change data feed is on. In one commit, `UPDATE silver.customers SET city = 'Sedona' WHERE customer_id = 7` changes one row. How many rows does `table_changes` return for that commit, and with which `_change_type`?**

??? success "Answer"
    Two:

    ```text
    |7          |Sedona   |update_postimage|2              |
    |7          |Moab     |update_preimage |2              |
    ```

    **Why:** an update is recorded as the row before (`update_preimage`) and after (`update_postimage`); inserts and deletes give one row each (`insert`, `delete`). The feed starts when the property is enabled and its files are removed by `VACUUM`, so it is not a permanent history ([Use change data feed on Databricks](https://docs.databricks.com/aws/en/tables/features/change-data-feed)).

**Q19. `delta.logRetentionDuration` is 30 days, but `SELECT * FROM silver.orders VERSION AS OF 120` (10 days old) fails. Why?**

??? success "Answer"
    Log retention is not enough; the version's data files must also still exist. Either `VACUUM` (run by a job, by hand, or by predictive optimization on a managed table) has removed files older than `delta.deletedFileRetentionDuration`, 7 days by default, or, on Databricks Runtime 18.0 and above (12.2 LTS and above for Unity Catalog managed tables), the query was blocked outright because the version is older than `deletedFileRetentionDuration`. To travel further back, raise both properties before you need it.

    **Why:** "Use only the past 7 days for time travel operations unless you have set both data and log retention configurations to a larger value" ([Work with table history](https://docs.databricks.com/aws/en/tables/history)).

**Q20. (Run here.) With `delta.enableTypeWidening = true`, which of these succeed on a table where `customer_id INT` and `amount DECIMAL(12,2)`: (a) `customer_id` to `BIGINT`, (b) `amount` to `DECIMAL(12,4)`, (c) `amount` to `DECIMAL(14,4)`, (d) `order_id INT` to `STRING`?**

??? success "Answer"
    (a) succeeds. (b) fails (`NOT_SUPPORTED_CHANGE_COLUMN`). (c) is allowed by the rule (the run did not try it). (d) fails (`DELTA_UNSUPPORTED_ALTER_TABLE_CHANGE_COL_OP`).

    **Why:** widening allows `INT` to `BIGINT` and decimals with greater precision and scale, where adding scale needs the same added precision: "If you want to add two decimal places to a field with `decimal(10,1)`, the minimum target is `decimal(12,3)`". (b) adds two decimal places without adding precision; (c) adds two of each. `INT` to `STRING` is not a widening; it needs a rewrite ([Type widening](https://docs.databricks.com/aws/en/tables/features/type-widening)).

**Q21. (Run here.) `ALTER TABLE silver.orders RENAME COLUMN channel TO sales_channel` fails with `DELTA_UNSUPPORTED_RENAME_COLUMN`. Fix it without rewriting the data.**

??? success "Answer"
    Enable column mapping, then rename: `ALTER TABLE silver.orders SET TBLPROPERTIES ('delta.columnMapping.mode' = 'name')` followed by `ALTER TABLE silver.orders RENAME COLUMN channel TO sales_channel`. The run in section 20.7 did the same steps on another copy of the table, renaming `status` and dropping `currency`:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    ALTER TABLE silver.orders SET TBLPROPERTIES ('delta.columnMapping.mode' = 'name');
    ALTER TABLE silver.orders RENAME COLUMN status TO order_status;
    ALTER TABLE silver.orders DROP COLUMN currency;
    ```

    ```text
    after columnMapping.mode = name: (2, 7, ['appendOnly', 'columnMapping', 'invariants'])
    >>> ALTER TABLE silver.orders RENAME COLUMN status TO order_status
    OK
    >>> ALTER TABLE silver.orders DROP COLUMN currency
    OK
    ```

    **Why:** Parquet files store column names, so Delta needs column mapping to map a logical name to the physical one; then renames and drops are metadata-only (the run's file count stayed at 2). It upgrades the protocol (reader 2, writer 5 or above on Databricks), so check external readers first.

**Q22. After `ALTER TABLE silver.orders DROP COLUMN currency`, the streaming job that reads `silver.orders` fails. Why, and what is the fix?**

??? success "Answer"
    A rename or drop is a non-additive schema change; a stream reading the table cannot continue across it without knowing how the schema evolved. Give the streaming read a `schemaTrackingLocation` option (one per stream), so Delta records the schema changes and the stream can proceed after a restart.

    **Why:** "Non-additive schema changes, such as column renames or drops, can break streaming reads. Use a `schemaTrackingLocation`" ([Rename and drop columns with Delta Lake column mapping](https://docs.databricks.com/aws/en/tables/features/column-mapping)).

**Q23. Write the statement that reloads the orders of 1 March 2026 from `staging.orders_0301` so that a rerun gives the same result and orders removed at the source disappear.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    INSERT INTO silver.orders REPLACE WHERE order_date = DATE'2026-03-01'
    SELECT * FROM fixed_0301;
    ```

    (The run used the view `fixed_0301`; replace it with the staging table.) In section 20.8 this removed 1002, updated 1001 and added 1008 in one commit.

    **Why:** `REPLACE WHERE` deletes the slice and inserts the batch atomically, so it is idempotent, and rows missing from the batch are removed. An append would duplicate on rerun; a `MERGE` would not remove 1002.

**Q24. (Run here.) The 1 March batch accidentally contains an order dated 5 March. What does the `REPLACE WHERE order_date = DATE'2026-03-01'` load do?**

??? success "Answer"
    It fails and writes nothing:

    ```text
    AnalysisException: [DELTA_REPLACE_WHERE_MISMATCH] Written data does not conform to partial table overwrite condition or constraint '(order_date = DATE '2026-03-01')'.
    ```

    **Why:** by default every inserted row must match the predicate. On classic compute `spark.databricks.delta.replaceWhere.constraintCheck.enabled = false` changes this to "overwrite rows inside the predicate range and insert rows outside it" ([INSERT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-dml-insert-into)). Usually the failure is what you want.

**Q25. The extract for 2 March comes back empty by mistake. What does each load do: (a) `REPLACE WHERE order_date = '2026-03-02'`, (b) `REPLACE USING (order_date)`, (c) `MERGE` with only `WHEN MATCHED` and `WHEN NOT MATCHED` clauses?**

??? success "Answer"
    (a) Deletes every 2 March order (the run removed 1003). (b) Deletes nothing: there are no source rows to match. (c) Changes nothing.

    **Why:** "For empty source queries, `REPLACE WHERE` might delete table rows", while for `REPLACE USING` and `REPLACE ON` an empty source "does not delete any table rows" ([Selectively overwrite data with Delta Lake](https://docs.databricks.com/aws/en/delta/selective-overwrite)). Guard `REPLACE WHERE` jobs with a row-count check. (A `MERGE` with `WHEN NOT MATCHED BY SOURCE THEN DELETE` and no condition would delete the whole table.)

**Q26. (Run here.) `orders_p2` is partitioned by `order_date` and holds 1, 2 and 3 March. With default settings, what is left after `INSERT OVERWRITE silver.orders_p2 SELECT * FROM fixed_0301` (rows for 1 March only)?**

??? success "Answer"
    Only the 1 March rows:

    ```text
    +--------+----------+-------+
    |order_id|order_date|status |
    +--------+----------+-------+
    |1001    |2026-03-01|SHIPPED|
    |1008    |2026-03-01|PLACED |
    +--------+----------+-------+
    ```

    **Why:** without a `PARTITION` clause, static mode (the default for `spark.sql.sources.partitionOverwriteMode`) overwrites the whole table. Name the partition (`PARTITION (order_date = '2026-03-01')`), use `REPLACE WHERE`, or on Databricks `REPLACE USING (order_date)`; dynamic partition overwrite is legacy and, in SQL, classic compute only.

**Q27. (Run here.) Why does this insert fail, and what one-word change fixes it?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO silver.orders
SELECT 'CAD' AS currency, 1007 AS order_id, 4 AS customer_id, DATE'2026-03-04' AS order_date,
       'PLACED' AS status, 19.99 AS amount;
```

??? success "Answer"
    ```text
    AnalysisException: [DATATYPE_MISMATCH.CAST_WITH_FUNC_SUGGESTION] Cannot resolve "customer_id" due to data type mismatch: cannot cast "INT" to "DATE".
    ```

    `INSERT INTO silver.orders BY NAME SELECT ...` works: it matches columns by name.

    **Why:** without `BY NAME` (Databricks Runtime 13.3 LTS and above), columns match by position, so `customer_id` (third) went to `order_date`. When types happen to fit, a positional insert silently fills the wrong columns, which is worse than an error.

**Q28. (Run here.) `silver.products` must mirror a full daily snapshot: changed products updated, new ones inserted, products missing from the snapshot deleted, and unchanged rows not rewritten. Write the MERGE.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    -- target: 1 Trail Tent 2P 249.00, 2 Headlamp 300 39.95, 3 Merino Socks 29.95
    -- snapshot: 1 at 229.00, 3 unchanged, 4 Water Filter 59.00 (new); 2 is gone
    MERGE INTO silver.products AS t
    USING products_snapshot AS s
    ON t.product_id = s.product_id
    WHEN MATCHED AND (t.name, t.category, t.price) IS DISTINCT FROM (s.name, s.category, s.price)
      THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *
    WHEN NOT MATCHED BY SOURCE THEN DELETE;
    ```

    ```text
    +----------+-------------+--------+------+
    |product_id|name         |category|price |
    +----------+-------------+--------+------+
    |1         |Trail Tent 2P|camping |229.00|
    |3         |Merino Socks |clothing|29.95 |
    |4         |Water Filter |camping |59.00 |
    +----------+-------------+--------+------+

    +-------+--------+-------+
    |updated|inserted|deleted|
    +-------+--------+-------+
    |      1|       1|      1|
    +-------+--------+-------+
    ```

    **Why:** `WHEN NOT MATCHED BY SOURCE THEN DELETE` removes what the snapshot no longer has; the `IS DISTINCT FROM` condition (null-safe) skips product 3, so only one row is updated and change data feed records no fake updates. Only use an unconditional `NOT MATCHED BY SOURCE THEN DELETE` when the source really is the full set.

**Q29. (Run here.) Find the bug.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
MERGE INTO silver.orders AS t USING batch AS s ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN MATCHED AND s.status = 'CANCELLED' THEN DELETE;
```

??? success "Answer"
    ```text
    ParseException: [NON_LAST_MATCHED_CLAUSE_OMIT_CONDITION] When there are more than one MATCHED clauses in a MERGE statement, only the last MATCHED clause can omit the condition.
    ```

    Put the conditional clause first: `WHEN MATCHED AND s.status = 'CANCELLED' THEN DELETE WHEN MATCHED THEN UPDATE SET *`.

    **Why:** clauses are tried in order and the first match wins, so an unconditional clause first would make the later ones unreachable; Databricks rejects it.

**Q30. (Run here.) A MERGE fails with `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`. The batch holds `(1001, 'SHIPPED')` and `(1001, 'DELIVERED')`. Fix it.**

??? success "Answer"
    Deduplicate the batch to one row per key before the MERGE, keeping the latest event:

    *Databricks only, not run here. Syntax from [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into).*

    ```sql
    MERGE INTO shop.silver.orders AS t
    USING (SELECT * FROM shop.bronze.order_events
           QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY event_ts DESC) = 1) AS s
    ON t.order_id = s.order_id
    WHEN MATCHED THEN UPDATE SET t.status = s.status
    WHEN NOT MATCHED THEN INSERT *;
    ```

    **Why:** with two source rows for one target row, the update is ambiguous; the run in section 20.9 shows the error, and that an unconditional `WHEN MATCHED THEN DELETE` with the same batch is allowed. The table and column names in this answer are illustrative; `QUALIFY` is covered in [chapter 17](17-Databricks-SQL-vs-Standard.md).

**Q31. Can a `WHEN NOT MATCHED BY SOURCE` clause set `t.status = s.status`?**

??? success "Answer"
    No. A `NOT MATCHED BY SOURCE` row has no source row, so its condition and actions "may only reference columns from the target table". Databricks raises an analysis error; open-source Delta 4.4.1 failed with `[INTERNAL_ERROR] Cannot find main error class 'DELTA_MERGE_UNRESOLVED_EXPRESSION'`. Use a literal or a target expression (`SET t.status = 'ARCHIVED'`).

    **Why:** [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into); section 20.9.

**Q32. Rewrite this for Databricks: `UPDATE orders o SET status = 'HOLD' FROM blocked b WHERE o.customer_id = b.customer_id`.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into).*

    ```sql
    MERGE INTO shop.silver.orders AS o
    USING shop.silver.blocked_customers AS b
    ON o.customer_id = b.customer_id
    WHEN MATCHED THEN UPDATE SET o.status = 'HOLD';
    ```

    Or, on Databricks, `UPDATE shop.silver.orders SET status = 'HOLD' WHERE customer_id IN (SELECT customer_id FROM shop.silver.blocked_customers)`. (If `blocked` can hold the same customer twice, deduplicate it for the MERGE version.)

    **Why:** "Databricks SQL does not support the `UPDATE ... FROM ... JOIN` syntax" and points to `MERGE INTO` ([UPDATE](https://docs.databricks.com/aws/en/sql/language-manual/delta-update)); the open-source run gave a parse error at `FROM`.

**Q33. (Run here.) Three tables with the same rows are emptied with `TRUNCATE TABLE`, `DELETE FROM` (no `WHERE`) and `INSERT OVERWRITE ... SELECT ... WHERE false`. What does the last `DESCRIBE HISTORY` entry say for each, and can you time travel back?**

??? success "Answer"
    ```text
    TRUNCATE TABLE silver.t1                                       rows left=0  operation=TRUNCATE
    DELETE FROM silver.t2                                          rows left=0  operation=DELETE
    INSERT OVERWRITE silver.t3 SELECT * FROM silver.t3 WHERE false rows left=0  operation=WRITE
    ```

    All three are ordinary commits, so `VERSION AS OF` the previous version (or `RESTORE`) brings the rows back until `VACUUM` removes the files.

    **Why:** on Delta none of them deletes files immediately; each writes a commit that removes the old files from the current version. The operation name in the history is how you tell later what someone ran.

**Q34. Write the PySpark that reloads 1 March in `silver.orders` from a DataFrame `fixed_df`, atomically.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    (fixed_df.write.format("delta").mode("overwrite")
        .option("replaceWhere", "order_date = '2026-03-01'")
        .saveAsTable("silver.orders"))
    ```

    Section 20.8 shows the result (`fixed_df` was `spark.table("fixed_0301")`). For "replace the dates present in the batch", the option is `.option("replaceUsing", "order_date")`, documented on Databricks for Runtime 18.2 and above; open-source Delta 4.4.1 already accepted it.

    **Why:** `replaceWhere` is the writer form of `REPLACE WHERE`, with the same rules (rows outside the predicate fail the write).

**Q35. (Run here.) `v_star` is `CREATE VIEW silver.v_star AS SELECT * FROM silver.orders`. You add a column `channel` to `orders`. Does `SELECT * FROM silver.v_star` return it?**

??? success "Answer"
    No:

    ```text
    v_star columns     : ['order_id', 'customer_id', 'order_date', 'status', 'amount', 'currency']
    v_star_evo columns : ['order_id', 'customer_id', 'order_date', 'status', 'amount', 'currency', 'channel']
    ```

    **Why:** a view stores its column list at creation; in the default `SCHEMA COMPENSATION` mode extra columns from `*` are ignored. A view created `WITH SCHEMA EVOLUTION` (`v_star_evo`, Databricks Runtime 15.3 and above) adopts added, dropped and renamed columns. Otherwise recreate the view.

**Q36. In a Databricks SQL dashboard, query A creates a temporary view and query B reads it. Query B fails. Why?**

??? success "Answer"
    In Databricks SQL a temporary view lives only for the query that created it: "Multiple statements within the same query can use the temp view, but it cannot be referenced in other queries, even within the same dashboard" ([What is a view?](https://docs.databricks.com/aws/en/views/)). Use a permanent view (or a CTE inside query B). In a notebook, a temporary view lives as long as the notebook's session.

    **Why:** temporary views are session objects (`system.session`), and the scope of a "session" depends on the tool.

**Q37. (Run here.) You create a shallow clone of `silver.orders` and update one row in the clone. How many data files did the clone copy, and does the source change?**

??? success "Answer"
    Zero files copied (`num_copied_files = 0`); the clone's folder was empty until the `UPDATE`, which wrote one new file there. The source still shows the old value (`PLACED` against the clone's `TEST`).

    **Why:** a shallow clone copies only metadata and references the source's files; writes to the clone go to the clone's own folder. Clones have their own history (version 0 is `CLONE`).

**Q38. Your shallow clone of a production table started failing with `FileNotFoundException`. What happened, and would it happen in Unity Catalog?**

??? success "Answer"
    Someone ran `VACUUM` on the source, which deleted old files the clone still referenced. Outside Unity Catalog this breaks the clone ("To repair, run clone with `replace` on the shallow clone", or use a deep clone). With Unity Catalog tables on both sides, `VACUUM` on the source "doesn't break the cloned table", because Unity Catalog tracks the files the clone uses.

    **Why:** [Clone a table on Databricks](https://docs.databricks.com/aws/en/tables/operations/clone) and [Shallow clone for Unity Catalog tables](https://docs.databricks.com/aws/en/tables/operations/clone-unity-catalog).

**Q39. For a monthly archive of `silver.orders`, why `DEEP CLONE` rather than `CREATE TABLE ... AS SELECT * FROM silver.orders`?**

??? success "Answer"
    A deep clone copies the data and the table definition (schema, partitioning, invariants, nullability and table properties, which include `CHECK` constraints, plus stream and `COPY INTO` metadata) without restating them, and re-running `CREATE OR REPLACE TABLE archive.orders CLONE silver.orders` syncs the archive incrementally instead of copying everything again. A CTAS rewrites everything every time and loses the properties and constraints. Neither keeps the table comment or tags, so set those on the archive.

    **Why:** "You can sync deep clones incrementally to maintain an updated state of a source table for disaster recovery", and the page's monthly archive example is exactly that `CREATE OR REPLACE ... CLONE` ([Clone a table on Databricks](https://docs.databricks.com/aws/en/tables/operations/clone)). Use `VERSION AS OF` to archive an exact version. Deep clone is Databricks only; open-source Delta 4.4.1 has only shallow clone (section 20.10).

**Q40. `shop.gold.customer_ltv` was dropped 10 days ago, and its primary key matters to a BI tool. Can you get it back?**

??? success "Answer"
    Only if the recovery period of its schema or catalog was raised above 10 days (`ALTER SCHEMA ... RETAIN DROPPED TO n DAYS`, configurable to 7 to 30 days, Public Preview); the default is 7 days, so by default it is gone. If it is still recoverable, `UNDROP TABLE shop.gold.customer_ltv` brings back the data, privileges and properties, but not the primary and foreign keys: re-add them with `ALTER TABLE ... ADD CONSTRAINT`.

    **Why:** [UNDROP](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-undrop-table) and [DROP TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-drop-table).

**Q41. A dashboard runs a heavy daily-revenue aggregation over `shop.silver.orders` on every page load. What do you replace the view with, and where can you create it?**

??? success "Answer"
    A materialized view: `CREATE OR REPLACE MATERIALIZED VIEW shop.gold.daily_revenue SCHEDULE EVERY 1 HOUR AS SELECT ...`, so the dashboard reads stored results and the refresh does the work (incrementally when possible). It "can only be created using a Pro or Serverless SQL warehouse, or within a pipeline", and its refreshes run on serverless Lakeflow pipelines (formerly Delta Live Tables, [rename](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)).

    **Why:** a view recomputes on every read; a materialized view trades freshness (as of the last refresh) for cheap reads ([CREATE MATERIALIZED VIEW](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-materialized-view)).

**Q42. Which statement tells you: (a) how many files a table has and its total size, (b) who ran the last `DELETE` and when, (c) whether it is managed or external, (d) the DDL to recreate it?**

??? success "Answer"
    (a) `DESCRIBE DETAIL` (`numFiles`, `sizeInBytes`). (b) `DESCRIBE HISTORY` (operation, user, timestamp, metrics). (c) `DESCRIBE TABLE EXTENDED` (`Type`), or the location in `DESCRIBE DETAIL`. (d) `SHOW CREATE TABLE` (on Databricks; open-source Delta does not support it for Delta tables).

    **Why:** section 20.12. For code that parses the result, use `DESCRIBE TABLE EXTENDED ... AS JSON` (Databricks Runtime 16.2 and above).

**Q43. An external Spark job with an old Delta reader suddenly cannot read `silver.customers` after you enabled deletion vectors. Why, and can you just set the property back to `false`?**

??? success "Answer"
    Deletion vectors raised the table's protocol to reader version 3 with the `deletionVectors` feature (the run showed `3 7 ['appendOnly', 'changeDataFeed', 'deletionVectors', 'invariants']`), and the old reader does not support it. Setting the property to `false` stops new deletion vectors but does not lower the protocol. Drop the feature with `ALTER TABLE ... DROP FEATURE deletionVectors`, or upgrade the reader.

    **Why:** "Turning off a table feature does not result in a protocol downgrade. You must drop the feature to fully remove it from the protocol" ([Delta Lake feature compatibility and protocols](https://docs.databricks.com/aws/en/tables/features/feature-compatibility)).

## Sources

- [CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using) (last updated Nov 6, 2026)
- [CREATE TABLE LIKE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-like) (last updated Sep 11, 2026)
- [CREATE TABLE CLONE](https://docs.databricks.com/aws/en/sql/language-manual/delta-clone) (last updated Sep 11, 2026)
- [CONSTRAINT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-constraint) (last updated Oct 29, 2026)
- [ADD CONSTRAINT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-table-add-constraint) (last updated Sep 11, 2026)
- [CLUSTER BY clause (TABLE)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-cluster-by) (last updated Oct 30, 2026)
- [Partitions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-partition) (last updated Sep 11, 2026)
- [ALTER TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-table) (last updated Sep 11, 2026)
- [ALTER TABLE ... COLUMN clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-table-manage-column) (last updated Oct 30, 2026)
- [INSERT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-dml-insert-into) (last updated Oct 21, 2026)
- [MERGE INTO](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into) (last updated Sep 11, 2026)
- [UPDATE](https://docs.databricks.com/aws/en/sql/language-manual/delta-update) (last updated Sep 11, 2026)
- [DELETE FROM](https://docs.databricks.com/aws/en/sql/language-manual/delta-delete-from) (last updated Sep 11, 2026)
- [TRUNCATE TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-truncate-table) (last updated Sep 11, 2026)
- [CREATE VIEW](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-view) (last updated Oct 29, 2026)
- [CREATE MATERIALIZED VIEW](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-materialized-view) (last updated Oct 15, 2026)
- [CREATE STREAMING TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-streaming-table) (last updated Nov 10, 2026)
- [DESCRIBE TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-describe-table) (last updated Oct 29, 2026)
- [DESCRIBE HISTORY](https://docs.databricks.com/aws/en/sql/language-manual/delta-describe-history) (last updated Sep 11, 2026)
- [SHOW CREATE TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-show-create-table) (last updated Sep 11, 2026)
- [COMMENT ON](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-comment) (last updated Oct 9, 2026)
- [SET TAG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-set-tag) (last updated Oct 12, 2026)
- [DROP TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-drop-table) (last updated Nov 4, 2026)
- [UNDROP](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-undrop-table) (last updated Nov 5, 2026)
- [table_changes table-valued function](https://docs.databricks.com/aws/en/sql/language-manual/functions/table_changes) (last updated Oct 15, 2026)
- [Unity Catalog managed tables for Delta Lake and Apache Iceberg](https://docs.databricks.com/aws/en/tables/managed) (last updated Nov 9, 2026)
- [Work with external tables](https://docs.databricks.com/aws/en/tables/external) (last updated Oct 6, 2026)
- [Drop or replace a table](https://docs.databricks.com/aws/en/tables/operations/drop-table) (last updated Oct 19, 2026)
- [Clone a table on Databricks](https://docs.databricks.com/aws/en/tables/operations/clone) (last updated Sep 11, 2026)
- [Shallow clone for Unity Catalog tables](https://docs.databricks.com/aws/en/tables/operations/clone-unity-catalog) (last updated Sep 16, 2026)
- [Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints) (last updated Nov 6, 2026)
- [Delta Lake generated columns](https://docs.databricks.com/aws/en/tables/features/generated-columns) (last updated Sep 11, 2026)
- [Use liquid clustering for tables](https://docs.databricks.com/aws/en/tables/clustering) (last updated Nov 2, 2026)
- [When to partition tables on Databricks](https://docs.databricks.com/aws/en/tables/partitions) (last updated Sep 11, 2026)
- [Table properties reference](https://docs.databricks.com/aws/en/tables/table-properties) (last updated Nov 5, 2026)
- [Table properties and table options](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-tblproperties) (last updated Sep 11, 2026)
- [Delta Lake feature compatibility and protocols](https://docs.databricks.com/aws/en/tables/features/feature-compatibility) (last updated Oct 28, 2026)
- [Use change data feed on Databricks](https://docs.databricks.com/aws/en/tables/features/change-data-feed) (last updated Oct 9, 2026)
- [Deletion vectors in Databricks](https://docs.databricks.com/aws/en/tables/features/deletion-vectors) (last updated Nov 6, 2026)
- [Type widening](https://docs.databricks.com/aws/en/tables/features/type-widening) (last updated Oct 30, 2026)
- [Rename and drop columns with Delta Lake column mapping](https://docs.databricks.com/aws/en/tables/features/column-mapping) (last updated Sep 11, 2026)
- [Selectively overwrite data with Delta Lake](https://docs.databricks.com/aws/en/delta/selective-overwrite) (last updated Sep 11, 2026)
- [Update table schemas with schema evolution](https://docs.databricks.com/aws/en/tables/update-schema) (last updated Sep 11, 2026)
- [Work with table history](https://docs.databricks.com/aws/en/tables/history) (last updated Nov 6, 2026)
- [Review table details with describe detail](https://docs.databricks.com/aws/en/tables/operations/table-details) (last updated Sep 11, 2026)
- [What is a view?](https://docs.databricks.com/aws/en/views/) (last updated Oct 15, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [From Delta Sharing to OpenSharing: what changed, what's next](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next) (Databricks blog, posted Nov 5, 2026)
