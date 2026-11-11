# 5. Unity Catalog

*Every table, view, volume and file a Databricks data engineer touches is governed by Unity Catalog: it decides
what a name like `shop.silver.orders` points to, where the files live, who may read or write them, and what
depends on what. This chapter builds the model from the three-level name up to row filters, lineage and the
migration off the legacy Hive metastore, and lays out the Red Rock Supply catalog with grants per layer and per
team. Interviewers use Unity Catalog to test whether you understand ownership and access, so the chapter spends
time on the questions they push on: managed vs external, "why can this user see the schema but not the table",
row-level security, lineage and migration.*

!!! abstract "In this chapter"
    **You will learn:**

    - the metastore, the three-level namespace `catalog.schema.object`, the default catalog, and how names resolve
    - the object hierarchy and which objects are securable, including the ones that sit directly under the metastore
    - managed vs external tables: who owns the files, what `DROP TABLE` does, `UNDROP` and the recovery period
    - managed storage locations at metastore, catalog and schema level; storage credentials and external locations;
      managed and external volumes and `/Volumes` paths
    - `GRANT`, `REVOKE`, `SHOW GRANTS`, usage privileges, inheritance, ownership, `MANAGE` and `BROWSE`
    - row filters, column masks, dynamic views and ABAC policies
    - `information_schema`, system tables and lineage
    - workspace-catalog binding and the access modes (standard and dedicated, formerly shared and single user)
    - the `hive_metastore` catalog and the upgrade paths (`SYNC`, clone, federation, `SET MANAGED`, UCX)
    - a complete catalog design for Red Rock Supply: catalog `shop`, schemas `bronze`, `silver`, `gold`, grants per
      layer and per team

    **You need:** [4. Delta Lake](04-Delta-Lake.md) (tables are folders of Parquet files plus a transaction log).
    [7. The medallion architecture](07-Medallion-Architecture.md) explains the layers this chapter secures.

    **Levels:** sections 5.1 to 5.3 beginner, 5.4 to 5.9 intermediate, 5.10 and 5.11 expert.

Most of Unity Catalog exists only in a Databricks workspace, so most code here is labeled "Databricks only" with
syntax copied from the official page it links. What open-source Apache Spark 4.2 with Delta Lake 4.4.1 can honestly
show was run: multi-part names in the session catalog, managed vs external tables and what `DROP TABLE` does to
their files, schema storage folders, and a masking view. The open-source Unity Catalog server is not installed in
this environment, so nothing here was run against Unity Catalog itself. Scripts and full output are in
`src/ch05/`.

## 5.1 The problem: who may read what, and where is it?

*Level: beginner.*

Red Rock Supply has two Databricks workspaces, one for development and one for production. The data team loads
raw order files into bronze, cleans them into silver and builds daily sales in gold. Within a month, four questions
come up that nobody can answer quickly:

1. **Who can read customer emails?** Emails sit in `silver.customers`. Analysts need the city and country, not
   the email.
2. **Where are the files, and who may touch them directly?** If someone can list the storage bucket, every table
   permission is beside the point.
3. **Can the development workspace read production data?** It should not, even for a user who has read access in
   production.
4. **What breaks if we rename `amount` in silver?** Some gold table, job or dashboard reads it, but which?

Unity Catalog is the Databricks answer to all four. The overview page calls it "the unified governance layer for
data and AI built into Databricks": when enabled, it enforces access control when you query a table or call a
model, tracks lineage as data is used, and logs activity for auditing
([What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/)). The same page says
"Unity Catalog is automatically enabled for all Databricks workspaces created after November 8, 2023", and that an
open-source implementation exists.

Before Unity Catalog, each workspace had its own Hive metastore. The docs call it "a workspace-level object", and
its permissions refer to the local users and groups of that workspace
([Work with the legacy Hive metastore alongside Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/hive-metastore)).
Two workspaces meant two sets of tables and two sets of permissions. Unity Catalog moves governance up to the
account: one metastore per region, shared by the workspaces in that region, with account-level groups.

!!! tip "In the interview"
    **"What is Unity Catalog and why does a data engineer care?"** It is the governance layer of Databricks: one
    place, above the workspaces, that names every table, view, volume, function and model as
    `catalog.schema.object`, enforces who can read and write them, records lineage down to the column, and logs
    access for audit. For a data engineer it means I grant access per layer (for example `SELECT` on the gold
    schema), I can check what depends on a silver column before changing it, and production writes happen through
    service principals with grants, not through storage keys.

## 5.2 The metastore and the three-level namespace

*Level: beginner.*

### The metastore

The **metastore** is the top-level container of Unity Catalog. The securable objects reference states its scope
plainly: "A metastore is scoped to a single cloud region. Your organization requires one metastore per region in
which it operates. A single metastore can be attached to multiple workspaces in the same region. Permission grants
in a metastore apply to all workspaces attached to that metastore"
([Unity Catalog securable objects reference](https://docs.databricks.com/aws/en/data-governance/unity-catalog/securable-objects)).
So Red Rock's development and production workspaces, both in one region, share one metastore. A grant made in
either workspace is the same grant in both. Keeping the development workspace away from production data is a
separate setting, workspace-catalog binding (section 5.9).

### Three levels: catalog, schema, object

Inside the metastore, every data and AI asset has a three-part name, `catalog.schema.object`:

- a **catalog** is the top layer for data; it contains schemas;
- a **schema** (also called a database) sits in a catalog and contains tables, views, volumes, functions and
  models;
- the **object** is the table, view, volume, function or model itself.

`shop.silver.orders` is the `orders` table in the `silver` schema of the `shop` catalog. That is the layout this
book uses for Red Rock Supply: catalog `shop`, schemas `bronze`, `silver` and `gold`.
[Chapter 7](07-Medallion-Architecture.md) adds an environment level (`shop_dev`, `shop_prod`); the shape is the
same.

Names follow a few rules from the requirements page: object names cannot exceed 255 characters; a period, a space,
a forward slash and ASCII control characters are not allowed; "Unity Catalog stores all object names as
lowercase"; and names with special characters such as hyphens must be escaped with backticks
([Unity Catalog requirements and limitations](https://docs.databricks.com/aws/en/data-governance/unity-catalog/requirements)).

### The current catalog and schema

You rarely type three parts. Each session has a current catalog and a current schema, and shorter names resolve
against them. `USE CATALOG` sets the catalog, and the reference adds a detail that surprises people: "Setting the
catalog also resets the current schema to `default`"
([USE CATALOG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-use-catalog)).

*Databricks only, not run here. Syntax from [USE CATALOG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-use-catalog) and [USE SCHEMA](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-use-schema).*

```sql
USE CATALOG shop;                          -- current schema is now shop.default
USE SCHEMA silver;
SELECT current_catalog(), current_schema();  -- shop, silver
SELECT count(*) FROM orders;               -- shop.silver.orders
SELECT * FROM gold.daily_sales;            -- shop.gold.daily_sales
SELECT * FROM shop.gold.daily_sales;       -- fully qualified: works from anywhere
```

The statement is `{ USE | SET } CATALOG catalog_name`. When nothing sets a catalog, the **default catalog**
applies. The default catalog page gives the order in which a command without a catalog is resolved: first a
catalog set for the session with `USE CATALOG` or a JDBC setting, then the Spark configuration
`spark.databricks.sql.initial.catalog.namespace` on the cluster, then the workspace default catalog. It adds that
"The pipeline configuration for Lakeflow pipelines sets a default catalog that overrides the workspace default",
and that compute which does not meet the Unity Catalog requirements uses `hive_metastore` as the default catalog
([Manage the default catalog](https://docs.databricks.com/aws/en/catalogs/default)).

!!! warning "`USE CATALOG` the statement vs `USE CATALOG` the privilege"
    The same two words name two different things. The **statement** `USE CATALOG shop` changes your session's
    current catalog. The **privilege** `USE CATALOG`, granted with `GRANT USE CATALOG ON CATALOG shop TO ...`, is
    what allows a principal to interact with objects in the catalog at all. The USE CATALOG reference page opens
    with a note separating the two. Running the statement does not grant anything.

!!! tip "In the interview"
    **"Production code says `SELECT * FROM orders`. Is that a problem?"** It depends on the session's current
    catalog and schema, which come from `USE` statements, the cluster's Spark configuration, the pipeline's
    configured catalog or the workspace default. The same code can read a different table in another workspace or
    pipeline. In jobs I either fully qualify names or set the catalog and schema explicitly from a parameter, so
    switching dev to prod is one parameter and nothing depends on a workspace default.

### What the local engine can show

Open-source Spark has a **session catalog** named `spark_catalog`; the book's helper configures it with Delta
Lake's catalog class. It accepts names with up to three parts, `spark_catalog.schema.table`, so the mechanics of
qualified names, `USE` and `current_schema()` can be run here. What it lacks is everything that makes a catalog
governed.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SHOW CATALOGS;
SELECT current_catalog() AS cat, current_schema() AS sch;
CREATE SCHEMA IF NOT EXISTS spark_catalog.silver COMMENT 'silver layer of Red Rock Supply';
CREATE TABLE spark_catalog.silver.orders (
  order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING,
  amount DECIMAL(10,2), currency STRING) USING DELTA;
INSERT INTO spark_catalog.silver.orders VALUES
  (1001, 7, TIMESTAMP'2026-03-01 10:15:00', 'PLACED',  59.90, 'CAD'),
  (1002, 9, TIMESTAMP'2026-03-01 11:02:00', 'SHIPPED', 249.00, 'CAD');
SELECT order_id, amount FROM spark_catalog.silver.orders ORDER BY order_id;  -- three parts
USE spark_catalog.silver;
SELECT current_catalog() AS cat, current_schema() AS sch;
SELECT count(*) AS n FROM orders;                                           -- one part
```

```text
>>> SHOW CATALOGS
+-------------+
|catalog      |
+-------------+
|spark_catalog|
+-------------+

>>> SELECT current_catalog() AS cat, current_schema() AS sch
+-------------+-------+
|cat          |sch    |
+-------------+-------+
|spark_catalog|default|
+-------------+-------+

>>> SELECT order_id, amount FROM spark_catalog.silver.orders ORDER BY order_id
+--------+------+
|order_id|amount|
+--------+------+
|1001    |59.90 |
|1002    |249.00|
+--------+------+

>>> SELECT current_catalog() AS cat, current_schema() AS sch
+-------------+------+
|cat          |sch   |
+-------------+------+
|spark_catalog|silver|
+-------------+------+

>>> SELECT count(*) AS n FROM orders
+---+
|n  |
+---+
|2  |
+---+
```

The PySpark catalog API gives the same information as objects, which is handy in tests:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
print("currentCatalog():", spark.catalog.currentCatalog())
print("currentDatabase():", spark.catalog.currentDatabase())
print("listCatalogs():", [c.name for c in spark.catalog.listCatalogs()])
print("listTables('silver'):",
      [(t.catalog, t.namespace, t.name, t.tableType) for t in spark.catalog.listTables("silver")])
print("spark.table('spark_catalog.silver.orders').count():", spark.table("spark_catalog.silver.orders").count())
```

```text
currentCatalog(): spark_catalog
currentDatabase(): silver
listCatalogs(): ['spark_catalog']
listTables('silver'): [('spark_catalog', ['silver'], 'orders', 'MANAGED')]
spark.table('spark_catalog.silver.orders').count(): 2
```

And this is what happens when the Unity Catalog statements of this chapter are sent to open-source Spark 4.2:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
=== 5. USE CATALOG / SET CATALOG on the one catalog that exists ===
>>> USE CATALOG spark_catalog
  ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'spark_catalog': extra input 'spark_catalog'. SQLSTATE: 42601 (line 1, pos 12)

>>> SET CATALOG spark_catalog
  OK (no result)

>>> SELECT current_catalog() AS cat, current_schema() AS sch
+-------------+------+
|cat          |sch   |
+-------------+------+
|spark_catalog|silver|
+-------------+------+

=== 6. Unity Catalog statements: are they here? ===
>>> CREATE CATALOG shop
  ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'CATALOG'. SQLSTATE: 42601 (line 1, pos 7)

>>> USE CATALOG shop
  ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'shop': extra input 'shop'. SQLSTATE: 42601 (line 1, pos 12)

>>> SELECT * FROM shop.silver.orders
  AnalysisException: [REQUIRES_SINGLE_PART_NAMESPACE] spark_catalog requires a single-part namespace, but got identifier `shop`.`silver`.`orders`. SQLSTATE: 42K05

>>> SELECT table_name FROM information_schema.tables
  AnalysisException: [TABLE_OR_VIEW_NOT_FOUND] The table or view `information_schema`.`tables` cannot be found. Verify the spelling and correctness of the schema and catalog.

>>> SELECT table_name FROM system.information_schema.tables
  AnalysisException: [REQUIRES_SINGLE_PART_NAMESPACE] spark_catalog requires a single-part namespace, but got identifier `system`.`information_schema`.`tables`. SQLSTATE: 42K05

>>> SELECT table_name FROM spark_catalog.information_schema.tables
  AnalysisException: [TABLE_OR_VIEW_NOT_FOUND] The table or view `spark_catalog`.`information_schema`.`tables` cannot be found. Verify the spelling and correctness of the schema and catalog.

>>> GRANT SELECT ON TABLE spark_catalog.silver.orders TO `analysts`
  ParseException: [INVALID_STATEMENT_OR_CLAUSE] The statement or clause: GRANT is not valid. SQLSTATE: 42601

>>> SHOW GRANTS ON TABLE spark_catalog.silver.orders
  ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'ON': missing 'FUNCTIONS'. SQLSTATE: 42601 (line 1, pos 12)

>>> CREATE VOLUME spark_catalog.bronze.landing
  ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'VOLUME'. SQLSTATE: 42601 (line 1, pos 7)

>>> UNDROP TABLE spark_catalog.silver.orders
  ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'UNDROP'. SQLSTATE: 42601 (line 1, pos 0)

>>> CREATE SCHEMA spark_catalog.tmp_m MANAGED LOCATION '/tmp/x'
  ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'MANAGED'. SQLSTATE: 42601 (line 1, pos 34)

>>> ALTER TABLE spark_catalog.silver.orders SET ROW FILTER f ON (currency)
  ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'ROW'. SQLSTATE: 42601 (line 1, pos 44)

```

Two things to take from this run. First, open-source Spark 4.2 here rejected `USE CATALOG` and accepted
`SET CATALOG`; Databricks accepts both. Second, `CREATE CATALOG`, `GRANT`, volumes, `UNDROP`, `MANAGED LOCATION`,
row filters and `information_schema` are not in this open-source engine at all. They are Unity Catalog features,
so every example of them below is labeled Databricks only.

## 5.3 The object hierarchy and securable objects

*Level: beginner.*

A **securable object** is "an object defined in Unity Catalog on which privileges can be granted to a principal
(user, service principal, or group)"
([Unity Catalog securable objects reference](https://docs.databricks.com/aws/en/data-governance/unity-catalog/securable-objects)).
Everything you grant on is one. They form a tree.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 290" role="img" aria-label="The metastore at the top. Under it, the catalog shop with schemas bronze, silver and gold; under gold, tables, views, volumes, functions and models. Also directly under the metastore: storage credentials, external locations, service credentials, connections, external metadata, shares, recipients, providers and clean rooms." font-family="sans-serif" font-size="13" fill="currentColor">
<rect x="200" y="12" width="240" height="32" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="320" y="33" text-anchor="middle" font-weight="bold">Metastore (one per region)</text>
<polyline points="320,44 320,60 130,60 130,80" fill="none" stroke="currentColor"/>
<polyline points="320,60 510,60 510,80" fill="none" stroke="currentColor"/>
<rect x="40" y="80" width="180" height="32" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="130" y="101" text-anchor="middle">catalog: shop</text>
<line x1="130" y1="112" x2="130" y2="126" stroke="currentColor"/>
<line x1="60" y1="126" x2="240" y2="126" stroke="currentColor"/>
<line x1="60" y1="126" x2="60" y2="140" stroke="currentColor"/>
<line x1="150" y1="126" x2="150" y2="140" stroke="currentColor"/>
<line x1="240" y1="126" x2="240" y2="140" stroke="currentColor"/>
<rect x="20" y="140" width="80" height="28" rx="4" fill="none" stroke="currentColor"/>
<rect x="110" y="140" width="80" height="28" rx="4" fill="none" stroke="currentColor"/>
<rect x="200" y="140" width="80" height="28" rx="4" fill="none" stroke="currentColor"/>
<text x="60" y="159" text-anchor="middle">bronze</text>
<text x="150" y="159" text-anchor="middle">silver</text>
<text x="240" y="159" text-anchor="middle">gold</text>
<text x="292" y="159">schemas</text>
<line x1="240" y1="168" x2="240" y2="184" stroke="currentColor"/>
<line x1="55" y1="184" x2="359" y2="184" stroke="currentColor"/>
<line x1="55" y1="184" x2="55" y2="196" stroke="currentColor"/>
<line x1="131" y1="184" x2="131" y2="196" stroke="currentColor"/>
<line x1="207" y1="184" x2="207" y2="196" stroke="currentColor"/>
<line x1="283" y1="184" x2="283" y2="196" stroke="currentColor"/>
<line x1="359" y1="184" x2="359" y2="196" stroke="currentColor"/>
<rect x="20" y="196" width="70" height="28" rx="4" fill="none" stroke="currentColor"/>
<rect x="96" y="196" width="70" height="28" rx="4" fill="none" stroke="currentColor"/>
<rect x="172" y="196" width="70" height="28" rx="4" fill="none" stroke="currentColor"/>
<rect x="248" y="196" width="70" height="28" rx="4" fill="none" stroke="currentColor"/>
<rect x="324" y="196" width="70" height="28" rx="4" fill="none" stroke="currentColor"/>
<text x="55" y="215" text-anchor="middle">tables</text>
<text x="131" y="215" text-anchor="middle">views</text>
<text x="207" y="215" text-anchor="middle">volumes</text>
<text x="283" y="215" text-anchor="middle">functions</text>
<text x="359" y="215" text-anchor="middle">models</text>
<rect x="400" y="80" width="220" height="162" rx="5" fill="none" stroke="currentColor"/>
<text x="510" y="100" text-anchor="middle" font-weight="bold">directly under the metastore</text>
<text x="415" y="122">storage credentials</text>
<text x="415" y="140">external locations</text>
<text x="415" y="158">service credentials</text>
<text x="415" y="176">connections</text>
<text x="415" y="194">external metadata</text>
<text x="415" y="212">shares, recipients, providers</text>
<text x="415" y="230">clean rooms</text>
<text x="207" y="258" text-anchor="middle">three-level name of a gold table:</text>
<text x="207" y="278" text-anchor="middle" font-weight="bold">shop.gold.daily_sales</text>
</svg>
<figcaption>Figure 5.1. The Unity Catalog object hierarchy. Data and AI objects live at the third level of catalog.schema.object; the objects on the right govern storage, external systems and sharing, and sit directly under the metastore.</figcaption>
</figure>

| Object | Lives in | What it is | Key privileges |
| --- | --- | --- | --- |
| Metastore | the account, one per region | top-level container | `CREATE CATALOG`, `CREATE EXTERNAL LOCATION`, `CREATE STORAGE CREDENTIAL`, ... (do not inherit) |
| Catalog | metastore | first level; "typically by organizational units or software development lifecycle scopes" | `USE CATALOG`, `CREATE SCHEMA`, `BROWSE`, plus anything granted to apply to its children |
| Schema | catalog | second level; "a single use case, project, or team sandbox" | `USE SCHEMA`, `CREATE TABLE`, `CREATE VOLUME`, `CREATE FUNCTION`, ... |
| Table | schema | structured data: managed, external or foreign | `SELECT`, `MODIFY` (and `INSERT`, `UPDATE`, `DELETE` in Beta) |
| View, materialized view, metric view | schema | saved query; materialized views also store results | `SELECT`; `REFRESH` for materialized views |
| Volume | schema | files of any format in cloud storage, managed or external | `READ VOLUME`, `WRITE VOLUME` |
| Function | schema | UDFs, stored procedures, registered models | `EXECUTE` |
| Model | schema | AI model with versions | `EXECUTE`, `APPLY TAG`, `CREATE MODEL VERSION` |
| Storage credential | metastore | a cloud identity (an IAM role on AWS) | `CREATE EXTERNAL LOCATION`, `CREATE EXTERNAL TABLE` |
| External location | metastore | a storage path plus a storage credential | `READ FILES`, `WRITE FILES`, `CREATE EXTERNAL TABLE`, `CREATE EXTERNAL VOLUME`, `CREATE MANAGED STORAGE` |

The quotes and privileges come from the securable objects reference and the
[privileges reference](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/privileges-reference).
The reference also lists newer schema-level objects (services, secrets, features) and, under the metastore,
service credentials, connections (for Lakehouse Federation), external metadata (for custom lineage), shares,
recipients and providers for [OpenSharing](https://docs.databricks.com/aws/en/opensharing/) (formerly Delta
Sharing; the rename is announced in the
[Databricks blog, Nov 5, 2026](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next)),
and clean rooms. A data engineer works mostly with the first eight rows and the two storage objects.

Catalogs and schemas are **container objects**: "privileges granted on them can affect their children through
inheritance" ([Unity Catalog permissions model concepts](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/permissions-concepts)).
Tables, views, volumes and functions are leaves.

### Catalogs you will find in a workspace

Besides the catalogs you create, the catalogs page lists what Databricks provisions
([What are catalogs in Databricks?](https://docs.databricks.com/aws/en/catalogs/)):

- **Standard catalogs**, like `shop`: the normal kind.
- **Foreign catalogs**: used only for Lakehouse Federation; they mirror a database in an external system.
- **`hive_metastore`**: the legacy per-workspace Hive metastore surfaced as a catalog (section 5.10). The page says
  "The Hive metastore is deprecated, and all Databricks workspaces should migrate to Unity Catalog."
- **The workspace catalog**: created in new workspaces, usually named after the workspace, and accessible to all
  users of that workspace (and only that workspace) by default.
- **`__databricks_internal`**: internal state for features such as Lakeflow pipelines; "Do not query, modify, or
  delete objects" in it.

Two more appear in examples: the `system` catalog that holds system tables (section 5.8), and `samples`, which
the GRANT page describes as available to all workspaces but read-only
([GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant)).

## 5.4 Managed vs external tables

*Level: intermediate.*

Red Rock's bronze team faces a choice on day one. New silver and gold tables could live wherever Databricks
decides. But a partner system already writes Delta files to a folder in Red Rock's bucket, and that system keeps
writing there. Should the table point at the partner's folder, or should the data be copied into a location that
Databricks controls? That choice is managed vs external.

**Managed** and **external** describe who controls the files. The managed-vs-external page defines both
([Managed versus external assets in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/managed-versus-external)):

- "**Managed assets**: Unity Catalog controls both governance (access control, auditing, lineage) and the
  underlying file storage lifecycle (file optimization, how they are organized, and when they are deleted)."
- "**External assets**: Unity Catalog controls governance only. The underlying file storage lifecycle is
  controlled by you or an external system."

Both are governed: grants, audit and lineage apply to external tables too. And managed does not mean the data
moves to Databricks: "The data files always remain in your cloud account. Unity Catalog determines where within
your account they are stored, but does not transfer them to Databricks or own them." The distinction applies to
tables and volumes only. Views, functions and models have no managed or external variant.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 265" role="img" aria-label="Left: a managed table. Unity Catalog holds metadata and governance and also picks the storage path in the managed storage location and owns the file lifecycle; DROP TABLE purges the files after the recovery period. Right: an external table. Unity Catalog holds metadata and governance; the files are at your path inside an external location and you own their lifecycle; DROP TABLE removes the metadata and the files stay." font-family="sans-serif" font-size="13" fill="currentColor">
<defs><marker id="ar52" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<text x="160" y="24" text-anchor="middle" font-weight="bold">Managed table</text>
<text x="480" y="24" text-anchor="middle" font-weight="bold">External table</text>
<rect x="20" y="36" width="280" height="46" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="160" y="55" text-anchor="middle">Unity Catalog</text>
<text x="160" y="73" text-anchor="middle">metadata, grants, lineage, audit</text>
<rect x="340" y="36" width="280" height="46" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="480" y="55" text-anchor="middle">Unity Catalog</text>
<text x="480" y="73" text-anchor="middle">metadata, grants, lineage, audit</text>
<line x1="160" y1="82" x2="160" y2="110" stroke="currentColor" marker-end="url(#ar52)"/>
<line x1="480" y1="82" x2="480" y2="110" stroke="currentColor" marker-end="url(#ar52)"/>
<rect x="20" y="112" width="280" height="70" rx="5" fill="none" stroke="currentColor"/>
<text x="160" y="134" text-anchor="middle">managed storage location</text>
<text x="160" y="152" text-anchor="middle">path chosen by Unity Catalog</text>
<text x="160" y="170" text-anchor="middle">Unity Catalog owns the files</text>
<rect x="340" y="112" width="280" height="70" rx="5" fill="none" stroke="currentColor" stroke-dasharray="5 3"/>
<text x="480" y="134" text-anchor="middle">your path in an external location</text>
<text x="480" y="152" text-anchor="middle">s3://.../bronze/orders_ext</text>
<text x="480" y="170" text-anchor="middle">you own the files</text>
<line x1="320" y1="15" x2="320" y2="255" stroke="currentColor" stroke-dasharray="4 4"/>
<text x="160" y="212" text-anchor="middle" font-weight="bold">DROP TABLE</text>
<text x="160" y="232" text-anchor="middle">files purged after the recovery</text>
<text x="160" y="250" text-anchor="middle">period (7 days by default)</text>
<text x="480" y="212" text-anchor="middle" font-weight="bold">DROP TABLE</text>
<text x="480" y="232" text-anchor="middle">metadata removed, files stay</text>
<text x="480" y="250" text-anchor="middle">delete them yourself if needed</text>
</svg>
<figcaption>Figure 5.2. Managed vs external tables in Unity Catalog. Both are governed the same way; they differ in who picks the path and who owns the files' lifecycle.</figcaption>
</figure>

| Property | Managed table | External table |
| --- | --- | --- |
| Storage path | set by Unity Catalog, inside the managed storage location of the schema, catalog or metastore | set by you with `LOCATION`, on a path covered by an external location |
| File lifecycle (layout, optimization, deletion) | Unity Catalog | you or another system |
| `DROP TABLE` | files "permanently deleted after the recovery period (7 days by default)" | "Data files remain in place" |
| Formats | Delta or Apache Iceberg | Delta, CSV, JSON, Avro, Parquet, ORC, text |
| Path-based access (``delta.`s3://...` ``) | not supported | supported, but names are recommended |
| Predictive optimization, catalog commits, multi-statement transactions, automatic liquid clustering | yes (unique to managed tables) | no |
| Privileges to create | `USE CATALOG`, `USE SCHEMA`, `CREATE TABLE` | the same plus `CREATE EXTERNAL TABLE` on the external location |
| Databricks recommends | "the default and recommended table type" | when existing data is in a format managed tables do not support, or non-Databricks clients need direct access |

Sources for the table: the managed-vs-external page, [Unity Catalog managed tables for Delta Lake and Apache Iceberg](https://docs.databricks.com/aws/en/tables/managed),
[Work with external tables](https://docs.databricks.com/aws/en/tables/external) and the requirements page. One
page disagrees on formats: [Upgrade Hive tables and views to Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/migrate)
(last updated Oct 6, 2026) says "Managed tables always use the Delta table format". The two newer pages, managed tables
(Nov 9, 2026) and managed-vs-external (Oct 30, 2026), say Delta or Apache Iceberg, as does the requirements page
(Sep 16, 2026), and the table follows them. On path-based access the managed tables page is blunt: "Path-based access to Unity Catalog managed tables isn't
supported because it bypasses Unity Catalog access controls and prevents managed table features from working
properly." External engines reach managed tables through open APIs instead (the Unity REST API and the Iceberg REST
Catalog, with credential vending), which is why the managed-vs-external page says managed tables "do not cause
vendor lock-in".

### Creating each kind

The only syntactic difference is `LOCATION`: no location means managed.

*Databricks only, not run here. Syntax from [Unity Catalog managed tables for Delta Lake and Apache Iceberg](https://docs.databricks.com/aws/en/tables/managed) and [Work with external tables](https://docs.databricks.com/aws/en/tables/external).*

```sql
-- managed: Unity Catalog picks the path (Delta by default; add USING iceberg for Iceberg)
CREATE TABLE shop.silver.orders (
  order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING,
  amount DECIMAL(10,2), currency STRING);

-- external: you give a path inside an external location
CREATE TABLE shop.bronze.partner_orders (
  order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING,
  amount DECIMAL(10,2), currency STRING)
LOCATION 's3://rr-lake/bronze/partner_orders';
```

*Databricks only, not run here. Syntax from [Work with external tables](https://docs.databricks.com/aws/en/tables/external).*

```python
# managed
df.write.saveAsTable("shop.silver.orders")
# external: the path option makes it external
df.write.option("path", "s3://rr-lake/bronze/partner_orders").saveAsTable("shop.bronze.partner_orders")
```

### What DROP TABLE does, run locally

The ownership rule can be shown on the local engine, because open-source Spark's session catalog has managed and
external tables too: a table created without `LOCATION` is managed and lives in the warehouse folder; a table with
`LOCATION` is external.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE SCHEMA bronze;
CREATE TABLE bronze.orders_managed (
  order_id INT, customer_id INT, status STRING, amount DECIMAL(10,2)) USING DELTA;
CREATE TABLE bronze.orders_external (
  order_id INT, customer_id INT, status STRING, amount DECIMAL(10,2))
USING DELTA LOCATION '<work>/lake/bronze/orders_ext';
-- two rows inserted into each, then:
DROP TABLE bronze.orders_managed;
DROP TABLE bronze.orders_external;
-- the external folder is still there, so register it again (no column list needed)
CREATE TABLE bronze.orders_external USING DELTA LOCATION '<work>/lake/bronze/orders_ext';
SELECT * FROM bronze.orders_external ORDER BY order_id;
```

```text
=== 1. A managed table: no LOCATION, the catalog picks the folder ===
  bronze.orders_managed: Type = MANAGED, Location = <work>/warehouse/bronze.db/orders_managed
  <work>/warehouse/bronze.db/orders_managed: 2 parquet file(s), _delta_log json: ['00000000000000000000.json', '00000000000000000001.json']

=== 2. An external table: LOCATION is a folder we chose ===
  bronze.orders_external: Type = EXTERNAL, Location = <work>/lake/bronze/orders_ext
  <work>/lake/bronze/orders_ext: 2 parquet file(s), _delta_log json: ['00000000000000000000.json', '00000000000000000001.json']

=== 3. The same two kinds from PySpark ===
  orders_external: tableType = EXTERNAL
  orders_managed: tableType = MANAGED
  products_external: tableType = EXTERNAL
  products_managed: tableType = MANAGED

=== 4. DROP TABLE on both ===
after DROP TABLE bronze.orders_managed:
  <work>/warehouse/bronze.db/orders_managed: folder does not exist
after DROP TABLE bronze.orders_external:
  <work>/lake/bronze/orders_ext: 2 parquet file(s), _delta_log json: ['00000000000000000000.json', '00000000000000000001.json']

=== 5. The external data is still there: register it again (no column list needed) ===
>>> SELECT * FROM bronze.orders_external ORDER BY order_id
+--------+-----------+-------+------+
|order_id|customer_id|status |amount|
+--------+-----------+-------+------+
|1001    |7          |PLACED |59.90 |
|1002    |9          |SHIPPED|249.00|
+--------+-----------+-------+------+

>>> DESCRIBE HISTORY bronze.orders_external  -- columns: version, operation
+-------+------------+
|version|operation   |
+-------+------------+
|1      |WRITE       |
|0      |CREATE TABLE|
+-------+------------+
```

(The `Type` and `Location` lines come from `DESCRIBE TABLE EXTENDED`; the file lists come from the script reading
the folders. `<work>` stands for the run's scratch folder.) The re-registered external table kept its full Delta
history, because the history is in the `_delta_log` folder, not in the catalog. The same tables written from
PySpark get the same types: `saveAsTable` alone gives `MANAGED`, `.option("path", ...)` gives `EXTERNAL` (section
3 of the script's output).

!!! warning "Locally the managed folder vanished at once; on Databricks it does not"
    Open-source Spark deleted the managed table's folder immediately and has no `UNDROP` (section 5.2 showed the
    parse error). Unity Catalog keeps a dropped managed table's files through a recovery period so `UNDROP` can
    bring the table back, and purges them asynchronously afterwards. Only the ownership rule (managed: the catalog
    deletes the files; external: it does not) carries over from the local run.

### UNDROP and the recovery period

On Databricks, `DROP TABLE` "Deletes the table and removes the directory associated with the table from the file
system if the table is not an `EXTERNAL` table", and for an external table "only the associated metadata
information is removed" ([DROP TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-drop-table)).
Dropping requires `MANAGE` on the table, ownership of it, or ownership of its schema, catalog or metastore. The
same page continues: Unity Catalog supports `UNDROP TABLE` "to recover dropped managed or external tables. By
default, tables are recoverable for 7 days after being dropped, and you can configure the recovery period at the
catalog or schema level to 0 (to disable recovery) or 7 to 30 days. Configuring the recovery period is in Public
Preview."

The `UNDROP` reference ([UNDROP](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-undrop-table))
adds the details that matter in practice:

- **Applies to:** Databricks SQL, Databricks Runtime 12.2 LTS and above. It recovers tables, materialized views
  and streaming tables (materialized views and streaming tables only if created by an ETL pipeline that still
  exists).
- By default it recovers "the most recently dropped relation owned by the user of the given relation name". If
  several dropped tables share a name, find the ID with `SHOW TABLES DROPPED` and use `UNDROP TABLE WITH ID`. If a
  live table now has the name, rename it first.
- Privileges and properties come back; "Primary and foreign key constraints are not recovered".
- To undrop an external table you also need `CREATE EXTERNAL TABLE` on the external location or storage
  credential, which must still exist. What an undrop of an external table restores beyond its metadata is not
  described on the page (not verified).
- The parent schema and catalog must exist. Catalogs, schemas, views, functions and models "Cannot be recovered
  after delete" ([Object storage lifecycle in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/object-storage-lifecycle)).

*Databricks only, not run here. Syntax from [UNDROP](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-undrop-table), [CREATE SCHEMA](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-schema) and [ALTER SCHEMA](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-schema).*

```sql
DROP TABLE shop.silver.orders;                -- oops
UNDROP TABLE shop.silver.orders;              -- within the recovery period

SHOW TABLES DROPPED IN shop.silver;           -- several dropped tables named orders?
UNDROP TABLE WITH ID '6ca7be55-8f58-47a7-85ee-7a59082fd17a';

-- recovery period (Public Preview, Databricks Runtime 17.3 and above): 0 hours or 7 to 30 days
CREATE SCHEMA shop.scratch RETAIN DROPPED FOR 7 DAYS;
ALTER SCHEMA shop.silver RETAIN DROPPED TO 30 DAYS;
```

Note the two spellings: `RETAIN DROPPED FOR` in `CREATE CATALOG`/`CREATE SCHEMA`, `RETAIN DROPPED TO` in
`ALTER CATALOG`/`ALTER SCHEMA`. A schema-level setting overrides the catalog-level one, and the setting applies
only to tables dropped after it is configured. Not every page mentions the setting: the object storage lifecycle
page (Nov 5, 2026) describes the recovery window as a flat 7 days ("For 7 days after the delete"), while DROP TABLE
(Nov 4, 2026), UNDROP (Nov 5, 2026) and the managed tables page (Nov 9, 2026, the newest) give 7 days as the
default with the configurable period in Public Preview. This chapter follows the newer pages.

When the files actually disappear is described differently on two pages. CREATE CATALOG and CREATE SCHEMA (last
updated Sep 16, 2026) say that after the recovery period "data files for managed tables are deleted from your cloud
storage within 48 hours". The newer object storage lifecycle page (Nov 5, 2026) says the purge "can delete the data
files at any point from 7 days up to about 30 days after the delete" and advises allowing up to 30 days; the newest
page, the managed tables page (Nov 9, 2026), says only that "an asynchronous purge process deletes the underlying
data files" and gives no timing. If you track when storage is reclaimed, plan for the longer figure. That page also notes that on customer-provided storage your bucket's versioning or soft-delete
rules may keep files longer still.

!!! warning "DROP SCHEMA CASCADE is not the same in the Hive metastore"
    In Unity Catalog, dropping a schema with `CASCADE` deletes the files of its managed tables but not of its
    external tables. The CREATE SCHEMA page warns that for a schema in the workspace-level Hive metastore,
    "dropping that schema using the `CASCADE` option causes all files in that schema location to be deleted
    recursively, regardless of the table type (managed or external)." `RESTRICT` is the default on `DROP SCHEMA`
    and `DROP CATALOG`, and the lifecycle page recommends keeping it to prevent accidental recursive deletion.

The local run shows the Unity Catalog-like half of this: with the external folders outside the schema folder, a
`CASCADE` drop removed the managed table's folder and left the external ones.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> DROP SCHEMA bronze
  AnalysisException: [SCHEMA_NOT_EMPTY] Cannot drop a schema `bronze` because it contains objects.

>>> DROP SCHEMA bronze CASCADE
schemas now: ['default']
external folders after CASCADE:
  <work>/lake/bronze/orders_ext: 2 parquet file(s), _delta_log json: ['00000000000000000000.json', '00000000000000000001.json']
  <work>/lake/bronze/products_ext: 2 parquet file(s), _delta_log json: ['00000000000000000000.json']
managed products folder after CASCADE:
  <work>/warehouse/bronze.db/products_managed: folder does not exist
```

### Converting external to managed

Because Databricks recommends managed tables, it provides an in-place conversion, `ALTER TABLE ... SET MANAGED`
([Convert external or foreign Delta Lake tables to Unity Catalog managed tables](https://docs.databricks.com/aws/en/tables/convert-to-managed)).
For an external Delta table it copies the data and log to the managed location, then switches with a brief writer
downtime, keeps name, permissions, views and history, redirects path-based reads and writes, and can be rolled
back with `UNSET MANAGED` within 14 days. It needs Databricks Runtime 17.3 LTS or above (or serverless) and
ownership or `MANAGE` on the table. For a foreign table (from Hive metastore federation) the syntax is
`SET MANAGED MOVE` or `SET MANAGED COPY` (section 5.10). The page also mentions CTAS as an alternative but
recommends `SET MANAGED`.

*Databricks only, not run here. Syntax from [Convert external or foreign Delta Lake tables to Unity Catalog managed tables](https://docs.databricks.com/aws/en/tables/convert-to-managed).*

```sql
ALTER TABLE shop.bronze.partner_orders SET MANAGED;      -- external Delta table: no MOVE/COPY
ALTER TABLE shop.bronze.partner_orders UNSET MANAGED;    -- roll back, within 14 days
```

!!! tip "In the interview"
    **"Managed or external, and what happens on DROP?"** Both are governed by Unity Catalog; the difference is
    who owns the files. A managed table lives in the managed storage location Unity Catalog chooses; Unity
    Catalog optimizes and deletes its files, and after `DROP TABLE` they are purged once the recovery period ends
    (7 days by default), so `UNDROP` works inside that window. An external table points at my path in an external
    location; `DROP TABLE` removes only the metadata and the files stay. I default to managed, because Databricks
    recommends it and features such as predictive optimization and automatic liquid clustering are managed-only.
    I use external when another system must write or read the files directly, or the format is one managed
    tables do not support, and I convert later with `ALTER TABLE ... SET MANAGED`.

## 5.5 Where the files live: managed storage, credentials, external locations and volumes

*Level: intermediate.*

Every table and volume is ultimately files in a bucket. Unity Catalog never hands users the bucket's keys.
Instead, three objects connect it to storage: managed storage locations decide where managed data goes, storage
credentials hold the cloud identity, and external locations scope that identity to a path.

### Managed storage locations

A **managed storage location** is where managed tables and managed volumes keep their files. It can be set on the
metastore, a catalog or a schema, and "Managed storage locations at lower levels in the hierarchy override storage
locations defined at higher levels" ([Specify a managed storage location in Unity Catalog](https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/managed-storage)).
The rule for a new managed table: the schema's location if it has one, else the catalog's, else the metastore's.
The same page says:

- "Databricks recommends that you assign managed storage at the catalog level for logical data isolation, with
  metastore-level and schema-level as options."
- "New workspaces that are enabled for Unity Catalog automatically are created without a metastore-level managed
  storage location"; the workspace catalog they get does have one.
- A catalog or schema location must be contained within an external location, and setting it needs the
  `CREATE MANAGED STORAGE` privilege on that external location. The `MANAGED LOCATION` string "Must be 150
  characters or fewer".
- Unity Catalog adds hashed subdirectories, for example
  `<storage-root>/__unitystorage/catalogs/00000000-0000-0000-0000-000000000000`, so every managed object gets a
  unique path.
- `ALTER CATALOG ... SET MANAGED LOCATION` and `ALTER SCHEMA ... SET MANAGED LOCATION` (Databricks SQL, Databricks
  Runtime 18.1 and above) affect only new managed objects: "Existing managed objects are not moved".

*Databricks only, not run here. Syntax from [CREATE CATALOG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-catalog) and [CREATE SCHEMA](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-schema).*

```sql
CREATE CATALOG IF NOT EXISTS shop
  MANAGED LOCATION 's3://rr-lake/managed/shop'
  COMMENT 'Red Rock Supply';
CREATE SCHEMA IF NOT EXISTS shop.gold
  MANAGED LOCATION 's3://rr-lake/managed/shop_gold';   -- optional, overrides the catalog's
```

In Unity Catalog, `CREATE SCHEMA ... LOCATION` is not supported; the CREATE SCHEMA page says to use
`MANAGED LOCATION`. `LOCATION` is the Hive metastore form. Open-source Spark has only the `LOCATION` form, and it
behaves like a schema-level storage root: managed tables of that schema go under it. That much can be run here.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE SCHEMA bronze COMMENT 'raw Red Rock Supply data, as received';
CREATE SCHEMA silver COMMENT 'cleaned and conformed';
CREATE SCHEMA gold COMMENT 'business-level tables' LOCATION '<work>/storage/gold';
CREATE TABLE silver.customers (customer_id INT, name STRING, email STRING,
  city STRING, country STRING, updated_at TIMESTAMP) USING DELTA;
CREATE TABLE gold.daily_sales (sales_date DATE, orders INT, revenue DECIMAL(12,2)) USING DELTA;
-- then DESCRIBE SCHEMA EXTENDED and DESCRIBE TABLE EXTENDED on each
```

```text
  bronze: Location = <work>/warehouse/bronze.db
  silver: Location = <work>/warehouse/silver.db
  gold: Location = <work>/storage/gold

  silver.customers: Type = MANAGED, Location = <work>/warehouse/silver.db/customers
  gold.daily_sales: Type = MANAGED, Location = <work>/storage/gold/daily_sales
```

`gold.daily_sales` is still a managed table; it just lands under the gold schema's folder. In Unity Catalog the
same idea is `MANAGED LOCATION`, with the extra rules above (must be inside an external location, needs
`CREATE MANAGED STORAGE`, hashed subfolders).

### Storage credentials and external locations

A **storage credential** "stores the authentication information required to access a specific path in cloud
storage": "an IAM role on AWS, a service principal on Azure, or a service account on GCP". An **external
location** "pairs a storage credential with a cloud storage path" (securable objects reference). Several external
locations can share one credential. External locations are used for external tables, external volumes and managed
storage locations alike ([Connect to cloud object storage using Unity Catalog](https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/)).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 225" role="img" aria-label="An IAM role in the AWS account is wrapped by a storage credential. An external location combines the storage credential with the path s3://rr-lake/. The external location is used by external tables, external volumes and managed storage locations." font-family="sans-serif" font-size="13" fill="currentColor">
<defs><marker id="ar53" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<rect x="10" y="60" width="130" height="50" rx="5" fill="none" stroke="currentColor" stroke-dasharray="5 3"/>
<text x="75" y="81" text-anchor="middle">IAM role</text>
<text x="75" y="99" text-anchor="middle">(AWS account)</text>
<rect x="165" y="60" width="130" height="50" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="230" y="81" text-anchor="middle">storage</text>
<text x="230" y="99" text-anchor="middle">credential</text>
<rect x="330" y="60" width="135" height="50" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="397" y="81" text-anchor="middle">external location</text>
<text x="397" y="99" text-anchor="middle">s3://rr-lake/</text>
<line x1="140" y1="85" x2="163" y2="85" stroke="currentColor" marker-end="url(#ar53)"/>
<line x1="295" y1="85" x2="328" y2="85" stroke="currentColor" marker-end="url(#ar53)"/>
<rect x="495" y="20" width="135" height="40" rx="5" fill="none" stroke="currentColor"/>
<text x="562" y="45" text-anchor="middle">external table</text>
<rect x="495" y="75" width="135" height="40" rx="5" fill="none" stroke="currentColor"/>
<text x="562" y="100" text-anchor="middle">external volume</text>
<rect x="495" y="130" width="135" height="40" rx="5" fill="none" stroke="currentColor"/>
<text x="562" y="155" text-anchor="middle">managed location</text>
<line x1="465" y1="80" x2="493" y2="42" stroke="currentColor" marker-end="url(#ar53)"/>
<line x1="465" y1="88" x2="493" y2="95" stroke="currentColor" marker-end="url(#ar53)"/>
<line x1="465" y1="96" x2="493" y2="148" stroke="currentColor" marker-end="url(#ar53)"/>
<text x="320" y="196" text-anchor="middle">Privileges on the external location: CREATE EXTERNAL TABLE,</text>
<text x="320" y="215" text-anchor="middle">CREATE EXTERNAL VOLUME, CREATE MANAGED STORAGE, READ FILES, WRITE FILES</text>
</svg>
<figcaption>Figure 5.3. From cloud identity to governed path. Users never see the IAM role; they get privileges on the external location, or better, on the tables and volumes inside it.</figcaption>
</figure>

On AWS the storage credential is created in Catalog Explorer or with the CLI; the credentials reference shows the
CLI form. The external location and the grants are SQL.

*Databricks only, not run here. Syntax from [Credentials](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-storage-credentials), [CREATE EXTERNAL LOCATION](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-location) and [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant).*

```bash
databricks storage-credentials create --json '{"name": "rr_lake_cred", "aws_iam_role": {"role_arn": "arn:aws:iam::123456789:role/rr-lake-access"}}'
```

```sql
CREATE EXTERNAL LOCATION rr_lake URL 's3://rr-lake/'
  WITH (STORAGE CREDENTIAL rr_lake_cred)
  COMMENT 'Red Rock Supply lake bucket';

GRANT CREATE EXTERNAL TABLE  ON EXTERNAL LOCATION rr_lake TO `data_engineers`;
GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION rr_lake TO `data_platform_admins`;
```

Creating the external location requires `CREATE EXTERNAL LOCATION` on the metastore and on the storage credential.
The privileges reference recommends granting `CREATE EXTERNAL TABLE` on an external location rather than on a
storage credential, "because it's scoped to a path". For direct file access it recommends against `READ FILES` and
`WRITE FILES` and for volumes with `READ VOLUME` and `WRITE VOLUME` instead. If you do use them, note that
"`WRITE FILES` requires `READ FILES` to also be granted on the same external location".

The reference pages are not consistent on storage credentials. The [Credentials](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-storage-credentials)
reference (Sep 11, 2026) writes its example as `CREATE EXTERNAL LOCATION ... WITH (CREDENTIAL ...)` and grants
`READ FILES ON STORAGE CREDENTIAL`, while the CREATE EXTERNAL LOCATION syntax (Sep 11, 2026) is
`WITH (STORAGE CREDENTIAL ...)`. The privileges reference (Nov 6, 2026) is itself split: its summary table lists
`READ FILES` and `WRITE FILES` for storage credentials, but the detailed `READ FILES` and `WRITE FILES` entries name
only external locations. The code above uses the syntax page's form; whether the shorter `WITH (CREDENTIAL ...)`
spelling is accepted was not verified. Grant file access on external locations (or better, volumes), not on
credentials.

!!! warning "Nobody but Unity Catalog should touch managed storage directly"
    The cloud storage page warns against giving users or service principals direct access to the buckets used as
    Unity Catalog managed storage: access controls can be circumvented, auditing and lineage do not capture the
    access, and outside writes "could result in data corruption". A bucket policy that lets an analyst list the
    managed storage path quietly bypasses every grant in this chapter.

### Volumes

Tables govern rows. **Volumes** govern files: "Volumes are Unity Catalog objects that enable governance over
non-tabular datasets", and "Databricks recommends using volumes to govern access to all non-tabular data"
([What are Unity Catalog volumes?](https://docs.databricks.com/aws/en/volumes/)). For a data engineer the main use
is the landing area: the page lists "landing areas for raw data produced by external systems" and "staging
locations for ingestion", for example with Auto Loader or `COPY INTO` ([chapter 8](08-Bronze-Ingestion.md)).

| | Managed volume | External volume |
| --- | --- | --- |
| Storage | "Created inside the UC-managed storage for the schema" | "Registered against an existing cloud object storage path" |
| On drop | Unity Catalog deletes the files (the page says "7-day retention on delete"; `UNDROP VOLUME` within 7 days) | "Data remains in cloud storage when you drop the volume" |
| Access | "All access goes through UC" | "UC governs access, but external tools can use direct URIs" |
| Typical use | Databricks-only workloads | files that other systems also read or write |

Files in a volume have one path format in every language:

```text
/Volumes/<catalog>/<schema>/<volume>/<path>/<file-name>
```

`dbfs:/Volumes/...` also works with Spark. The `/<catalog>/<schema>/<volume>` part "maps to the three Unity Catalog
object names", and those directories cannot be created or deleted with file commands. Volumes need a SQL warehouse
or Databricks Runtime 13.3 LTS or above. One rule interviewers like: "You can't register files in volumes as tables
in Unity Catalog. Volumes are intended for path-based data access only." To query JSON in a volume as a table, you
ingest it into a table.

*Databricks only, not run here. Syntax from [CREATE VOLUME](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-volume) and [Work with files in Unity Catalog volumes](https://docs.databricks.com/aws/en/volumes/volume-files).*

```sql
-- managed volume for the raw order files
CREATE VOLUME IF NOT EXISTS shop.bronze.landing COMMENT 'raw order JSON from the web shop';
-- external volume over a folder the partner writes to
CREATE EXTERNAL VOLUME shop.bronze.partner_drop
  LOCATION 's3://rr-lake/partner_drop'
  COMMENT 'files written by the partner system';

GRANT READ VOLUME, WRITE VOLUME ON VOLUME shop.bronze.landing TO `etl_sp`;
GRANT READ VOLUME ON VOLUME shop.bronze.landing TO `data_engineers`;
```

```python
raw = spark.read.format("json").load("/Volumes/shop/bronze/landing/orders/")
```

Creating a volume needs `USE CATALOG`, `USE SCHEMA` and `CREATE VOLUME` on the schema, plus
`CREATE EXTERNAL VOLUME` on the external location for an external one. In the grants, `etl_sp` is shown as a plain
name for readability; a real service principal is addressed by its application ID in backticks (section 5.6).

## 5.6 Privileges: GRANT, REVOKE, inheritance and ownership

*Level: intermediate.*

### Principals

Privileges are granted to **principals**: users, service principals and groups. Groups must be **account
groups**. The requirements page: "workspace-level groups ... cannot be used in Unity Catalog `GRANT` statements".
The principal reference spells out two special names: `` `account users` ``, "The root group to which all users in
the account belong", and `users`, the workspace root group, which you "cannot grant ... privileges on securable
objects in Unity Catalog because it is a workspace-local group"
([Principal](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-principal)). Users are written as
`` `name@domain` `` and service principals by application ID, both in backticks.

The best practices page sets the defaults a reviewer expects: "Avoid direct grants to users whenever possible",
"Use groups to assign ownership to most securable objects", "Use service principals to run jobs", and "Reserve
direct `MODIFY` access to production tables for service principals"
([Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices)).

### Nothing is allowed until granted

"A user or group must be explicitly granted a privilege to perform an action" (permissions concepts page). There is
no `DENY` statement: comparing Unity Catalog with legacy table ACLs, the Hive metastore page says "No support for
`DENY`: ... Privileges that are not granted are implicitly denied." (Explicit denials do exist as ABAC DENY
policies, in Beta, per the [ABAC overview](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/);
they are policies, not a `DENY` statement.)

### Usage privileges: the three-part rule

To do anything with an object in a schema, a principal needs three things. The permissions concepts page lists
them for reading a table:

1. `USE CATALOG` on the parent catalog
2. `USE SCHEMA` on the parent schema
3. the privilege for the operation, such as `SELECT`, `MODIFY` or `EXECUTE`

"All three are required. Having only the `SELECT` privilege on a table is not sufficient to read it if you lack
`USE CATALOG` or `USE SCHEMA` on its parent objects." The reason is control: "Because only catalog and schema owners
or users with the `MANAGE` privilege can grant these usage privileges, this prevents table owners from granting
access outside approved boundaries." `USE CATALOG` and `USE SCHEMA` by themselves give no access to data.

| Operation | Required privileges |
| --- | --- |
| Read a table or view | `USE CATALOG`, `USE SCHEMA`, `SELECT` |
| Write a table | `USE CATALOG`, `USE SCHEMA`, `MODIFY` (the privileges reference adds: "The user must also have `SELECT` on the table") |
| Create a schema | `USE CATALOG`, `CREATE SCHEMA` on the catalog |
| Create a table | `USE CATALOG`, `USE SCHEMA`, `CREATE TABLE` on the schema (or catalog) |
| Run a function | `USE CATALOG`, `USE SCHEMA`, `EXECUTE` |
| Read files in a volume | `USE CATALOG`, `USE SCHEMA`, `READ VOLUME` |

(From the permissions concepts page and the [privileges reference](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/privileges-reference).
`INSERT`, `UPDATE` and `DELETE` exist as finer-grained children of `MODIFY`, in Beta.) One default to know: "All
users have `USE CATALOG` on the `main` catalog by default" (privileges reference).

### Inheritance

"When you grant a privilege on a parent object, that privilege automatically applies to all current and future
child objects" (permissions concepts page). A privilege on a catalog applies to all its schemas and their tables,
views, volumes and functions; a privilege on a schema applies to everything in that schema. That is why grants in
a medallion layout go on schemas: a new gold table is readable the moment it is created.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Catalog shop with USE CATALOG granted to analysts. Schema gold with USE SCHEMA and SELECT granted to analysts; its tables daily_sales, product_revenue and a future table inherit SELECT. Schema silver has no grant, so analysts cannot read it." font-family="sans-serif" font-size="13" fill="currentColor">
<rect x="20" y="20" width="150" height="30" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="95" y="40" text-anchor="middle">catalog shop</text>
<text x="200" y="40">analysts: USE CATALOG (granted here)</text>
<line x1="40" y1="50" x2="40" y2="265" stroke="currentColor"/>
<line x1="40" y1="95" x2="60" y2="95" stroke="currentColor"/>
<line x1="40" y1="265" x2="60" y2="265" stroke="currentColor"/>
<rect x="60" y="80" width="150" height="30" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="135" y="100" text-anchor="middle">schema gold</text>
<text x="240" y="100">analysts: USE SCHEMA, SELECT (granted here)</text>
<line x1="80" y1="110" x2="80" y2="224" stroke="currentColor"/>
<line x1="80" y1="144" x2="100" y2="144" stroke="currentColor"/>
<line x1="80" y1="184" x2="100" y2="184" stroke="currentColor"/>
<line x1="80" y1="224" x2="100" y2="224" stroke="currentColor"/>
<rect x="100" y="130" width="170" height="28" rx="4" fill="none" stroke="currentColor"/>
<rect x="100" y="170" width="170" height="28" rx="4" fill="none" stroke="currentColor"/>
<rect x="100" y="210" width="170" height="28" rx="4" fill="none" stroke="currentColor" stroke-dasharray="5 3"/>
<text x="185" y="149" text-anchor="middle">daily_sales</text>
<text x="185" y="189" text-anchor="middle">product_revenue</text>
<text x="185" y="229" text-anchor="middle">next new table (future)</text>
<text x="300" y="149">SELECT inherited from gold</text>
<text x="300" y="189">SELECT inherited from gold</text>
<text x="300" y="229">SELECT inherited when created</text>
<rect x="60" y="250" width="150" height="30" rx="5" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="135" y="270" text-anchor="middle">schema silver</text>
<text x="240" y="270">no grant: analysts cannot read silver</text>
</svg>
<figcaption>Figure 5.4. Privilege inheritance for the analysts group. Grants on a container flow down to all current and future children; the usage privileges (USE CATALOG, USE SCHEMA) are still needed at each level above the data.</figcaption>
</figure>

Two exceptions to remember:

- "Privileges granted on a metastore do not inherit to child objects." `CREATE CATALOG` on the metastore lets a
  user create catalogs, not read data. The one exception is `READ METADATA`, which inherits down from the
  metastore (permissions concepts page).
- Ownership does not inherit (below).

### GRANT, REVOKE, SHOW GRANTS

*Databricks only, not run here. Syntax from [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant), [REVOKE](https://docs.databricks.com/aws/en/sql/language-manual/security-revoke), [SHOW GRANTS](https://docs.databricks.com/aws/en/sql/language-manual/security-show-grant) and [Privileges and securable objects in Unity Catalog](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-privileges).*

```sql
-- GRANT privilege_types ON securable_object TO principal
GRANT USE CATALOG ON CATALOG shop TO `analysts`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop.gold TO `analysts`;

-- REVOKE privilege_types ON securable_object FROM principal
REVOKE SELECT ON SCHEMA shop.gold FROM `analysts`;

-- SHOW GRANTS [ principal ] ON securable_object
SHOW GRANTS ON SCHEMA shop.gold;
SHOW GRANTS `analysts` ON TABLE shop.gold.daily_sales;
```

The securable object keywords are `CATALOG`, `SCHEMA` (or `DATABASE`), `TABLE` (optional), `VIEW`,
`MATERIALIZED VIEW`, `VOLUME`, `FUNCTION`, `PROCEDURE`, `EXTERNAL LOCATION`, `[STORAGE | SERVICE] CREDENTIAL`,
`CONNECTION`, `SHARE`, `CLEAN ROOM`, `EXTERNAL METADATA` and `METASTORE` (with no name: it means the metastore
attached to the workspace). Behaviors worth knowing:

- `SHOW GRANTS` "Displays all privileges (inherited, denied, and granted) that affect the securable object", with
  columns `principal`, `actionType`, `objectType`, `objectKey`.
- `REVOKE` removes an **explicitly** granted privilege. If a user reads a table through a schema-level grant,
  revoking `SELECT` on the table changes nothing; revoke it where it was granted. And "A `REVOKE` statement
  succeeds even if the specified privileges were not granted in the first place", so a successful `REVOKE` proves
  nothing.
- `ALL PRIVILEGES` "expands to all available privileges at the time permissions checks are made" and "does not
  include the `EXTERNAL USE SCHEMA`, `EXTERNAL USE LOCATION`, `MANAGE`, or `READ METADATA` privileges".

### Ownership, MANAGE and BROWSE

"Every securable object in Unity Catalog has an owner. ... The principal that creates an object becomes its
initial owner" (permissions concepts page). The owner has all capabilities on the object, can grant and revoke,
transfer ownership and drop it, but Databricks does not record this as `ALL PRIVILEGES`, so owners do not appear
with it in `SHOW GRANTS`. Ownership does not inherit: owning a catalog does not make you owner of its schemas,
though the catalog owner can manage all of them. A job running as a service principal therefore owns the tables
it creates, and best practice is to transfer production objects to a group
([Manage privileges in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/)):

*Databricks only, not run here. Syntax from [Manage privileges in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/) and [ALTER SCHEMA](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-schema).*

```sql
ALTER SCHEMA shop.gold OWNER TO `data_platform_admins`;
ALTER TABLE shop.gold.daily_sales OWNER TO `data_platform_admins`;
```

| | Owner | `MANAGE` privilege |
| --- | --- | --- |
| How many | exactly one principal | any number of principals |
| Data access (`SELECT`, ...) | implied | not included; can grant it to themselves |
| Grant, revoke, transfer ownership, drop | yes | yes |
| Children | can manage them (implied) | `MANAGE` on a container is granted on all children |
| In `ALL PRIVILEGES`? | n/a | no, "To avoid accidental privilege escalation" |

(Permissions concepts page.) `MANAGE` also has reduced usage requirements: `MANAGE` on a catalog needs no usage
privileges at all, but data access still needs `USE CATALOG` and `USE SCHEMA`.

**`BROWSE`** answers "people cannot find data, but we will not give everyone read access". It "allows users to
discover objects and view their metadata without granting access to the underlying data", needs no
`USE CATALOG`/`USE SCHEMA`, is granted at the catalog level only for data objects (it can also be granted
directly on external locations, external metadata and clean rooms), and "Databricks recommends granting `BROWSE` on
catalogs to the `All account users` group" (permissions concepts page). In SQL that group is
`` `account users` ``.

!!! tip "In the interview"
    **"How would you give the analytics team read access to gold only?"** Grant to their account group, at the
    schema level so future gold tables are covered: `GRANT USE CATALOG ON CATALOG shop TO analysts` and
    `GRANT USE SCHEMA, SELECT ON SCHEMA shop.gold TO analysts`. Nothing on bronze or silver, so they cannot read
    those even though they have `USE CATALOG`; `USE CATALOG` alone gives no data. I would also grant `BROWSE` on
    the catalog to `account users` so people can discover and request other tables. Writes to gold stay with the
    pipeline's service principal, and the schema is owned by a group, not a person.

!!! tip "In the interview"
    **"A user can see the schema but cannot query a table in it. What is missing?"** First `SELECT`, on the
    table or on the schema or catalog above it. Seeing a schema in Catalog Explorer can come from `BROWSE`, which
    shows metadata without `USE CATALOG` or `USE SCHEMA`, so I also check the usage privileges: all three of
    `USE CATALOG`, `USE SCHEMA` and `SELECT` are required. I run `SHOW GRANTS` for the user's group on the table,
    schema and catalog. If grants are fine, I check the compute: it must be a SQL warehouse or use standard or
    dedicated access mode to read Unity Catalog data. (Workspace-catalog binding is an unlikely cause here: in a
    workspace the catalog is not bound to, its child objects are not visible at all.)

## 5.7 Row-level security and column masking

*Level: intermediate.*

Grants work on whole objects. Red Rock needs finer control on `silver.customers`: support staff see email
addresses, analysts do not; and a regional analyst group should see only Canadian customers. Unity Catalog offers
three tools ([Row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/)):

| Approach | Applies to | Managed with | Best for |
| --- | --- | --- | --- |
| Table-level row filters and column masks | one table and its columns | `ALTER TABLE` by the owner or a user with `MANAGE` | table-specific logic |
| ABAC policies | tables and columns matched by governed tags | `CREATE POLICY` on a catalog, schema or table | the same rule across many tables |
| Dynamic views | a view over base tables | the view's SQL | sharing a curated or transformed slice |

The access control page states the preference: "Databricks recommends using attribute-based access control (ABAC)
to centralize and scale access control based on governed tags. Use row filters and column masks only when you need
per-table logic or haven't adopted ABAC yet"
([Access control in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/)).

### Row filters and column masks on one table

A **row filter** is a SQL UDF returning a boolean; rows where it returns `FALSE` are excluded. A **column mask** is
a SQL UDF that receives the column value and returns it or a masked version. "Each table can have only one row
filter", and each column one mask
([Manually apply row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/manually-apply)).

*Databricks only, not run here. Syntax from [Manually apply row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/manually-apply).*

```sql
-- row filter: data admins see everything, everyone else only Canadian customers
CREATE FUNCTION shop.silver.ca_only(country STRING)
RETURN IF(is_account_group_member('data_admins'), true, country = 'CA');
ALTER TABLE shop.silver.customers SET ROW FILTER shop.silver.ca_only ON (country);

-- column mask: only support sees the email
CREATE FUNCTION shop.silver.email_mask(email STRING)
RETURN CASE WHEN is_account_group_member('support') THEN email ELSE '***REDACTED***' END;
ALTER TABLE shop.silver.customers ALTER COLUMN email SET MASK shop.silver.email_mask;

-- remove them (drop the filter BEFORE dropping its function)
ALTER TABLE shop.silver.customers DROP ROW FILTER;
ALTER TABLE shop.silver.customers ALTER COLUMN email DROP MASK;
```

Rules from the same page and the overview:

- To assign a filter or mask you need `EXECUTE` on the function plus `USE SCHEMA` and `USE CATALOG`; on an
  existing table you must be the owner or have both `MANAGE` and `SELECT` on it.
- "You must perform the `ALTER TABLE ... DROP ROW FILTER` command before you drop the function. If you don't, the
  table will be in an inaccessible state."
- `REPLACE TABLE` keeps an existing row filter, and keeps masks on columns with the same names.
- Compute: a SQL warehouse, standard access mode on Databricks Runtime 12.2 LTS or above, or dedicated access mode
  on Databricks Runtime 15.4 LTS or above (with serverless compute enabled in the workspace, because the filtering
  runs there). "Databricks Runtime versions below 12.2 LTS do not support row filters or column masks. These
  runtimes fail securely, meaning that if you try to access tables from these runtimes, no data is returned."
- Limits: "You cannot apply row-level security or column masks to a view"; OpenSharing providers cannot share
  tables with table-level row filters or column masks.
- Keep the UDFs simple: the overview recommends simple `CASE` expressions over mapping tables or subqueries, few
  arguments, deterministic expressions that cannot throw errors (`try_divide` rather than ANSI division), and SQL
  over Python UDFs. It also warns that with ANSI mode off, a parameter type that does not match the column
  silently turns values into `NULL`, which can make a filter return all rows.

### Dynamic views

A **dynamic view** filters or masks inside the view's SQL, with functions such as `is_account_group_member()`
(account groups, recommended) and `session_user()`. `is_member()` checks workspace-level groups and is "provided for
compatibility with the existing Hive metastore. Avoid using it with views against Unity Catalog data"
([Create a dynamic view](https://docs.databricks.com/aws/en/views/dynamic)). Views work for this because of how
Unity Catalog resolves them: a reader needs `SELECT` on the view, and "The user doesn't need privileges on the
underlying tables that the view queries. The view owner's privileges are used to resolve the underlying tables at
query time" (securable objects reference). Grant analysts the view, not the table.

*Databricks only, not run here. Syntax from [Create a dynamic view](https://docs.databricks.com/aws/en/views/dynamic).*

```sql
CREATE VIEW shop.gold.customers_for_analysts AS
SELECT
  customer_id,
  name,
  CASE WHEN is_account_group_member('support') THEN email ELSE 'REDACTED' END AS email,
  city,
  country
FROM shop.silver.customers;

GRANT SELECT ON VIEW shop.gold.customers_for_analysts TO `analysts`;
```

The masking logic itself is ordinary SQL and runs on the local engine, which shows what is and is not Unity
Catalog's job:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE FUNCTION silver.mask_email(email STRING)
RETURNS STRING
RETURN regexp_replace(email, '^[^@]+', '***');

CREATE VIEW gold.customers_masked AS
SELECT customer_id, name, silver.mask_email(email) AS email, city, country
FROM silver.customers;

SELECT * FROM gold.customers_masked ORDER BY customer_id;
SELECT customer_id, email FROM silver.customers ORDER BY customer_id;  -- around the view
```

```text
>>> SELECT * FROM gold.customers_masked ORDER BY customer_id
+-----------+----------+---------------+---------+-------+
|customer_id|name      |email          |city     |country|
+-----------+----------+---------------+---------+-------+
|7          |Ana Ruiz  |***@example.com|Calgary  |CA     |
|9          |Ben Okafor|***@example.com|Vancouver|CA     |
+-----------+----------+---------------+---------+-------+

>>> SELECT customer_id, email FROM silver.customers ORDER BY customer_id
+-----------+----------------------+
|customer_id|email                 |
+-----------+----------------------+
|7          |ana.ruiz@example.com  |
|9          |ben.okafor@example.com|
+-----------+----------------------+
```

The PySpark equivalent of the masking expression, also run here, gives the same result:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql import functions as F
(spark.table("silver.customers")
    .select("customer_id", "name",
            F.regexp_replace("email", r"^[^@]+", "***").alias("email"), "city", "country")
    .orderBy("customer_id")
    .show(truncate=False))
```

```text
+-----------+----------+---------------+---------+-------+
|customer_id|name      |email          |city     |country|
+-----------+----------+---------------+---------+-------+
|7          |Ana Ruiz  |***@example.com|Calgary  |CA     |
|9          |Ben Okafor|***@example.com|Vancouver|CA     |
+-----------+----------+---------------+---------+-------+
```

Locally anyone can read `silver.customers` directly, as the second query shows. What Unity Catalog adds is the
enforcement: analysts get `SELECT` on the view and nothing on the table, or the mask is attached to the column so
that every query path applies it.

### ABAC policies

With dozens of tables carrying emails, per-table masks do not scale. **Attribute-based access control** attaches
policies to a catalog, schema or table (a metastore too, in Beta); they apply automatically to tables and columns
that carry the matching governed tags ([Attribute-based access control in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/)).

*Databricks only, not run here. Syntax from [Create and manage row filter and column mask policies](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/policies).*

```sql
CREATE FUNCTION shop.silver.redact(v STRING) RETURNS STRING
  RETURN '***REDACTED***';

CREATE POLICY mask_pii_email
ON SCHEMA shop.silver
COLUMN MASK shop.silver.redact
TO `account users` EXCEPT `support`
FOR TABLES
MATCH COLUMNS has_tag_value('pii', 'email') AS email_col
ON COLUMN email_col;
```

Any table in `shop.silver` whose column is tagged `pii = email` is masked for everyone except `support`, including
tables created next month. The row filters and column masks page adds that ABAC policies "can be defined by
higher-level admins, so table owners can't override or remove them". [Chapter 23](23-Governance-and-Operations.md) covers tags and ABAC in
depth.

!!! tip "In the interview"
    **"How do you implement row-level security on Databricks?"** Three options. For one table, a row filter: a SQL
    UDF such as `IF(is_account_group_member('data_admins'), true, country = 'CA')` attached with
    `ALTER TABLE ... SET ROW FILTER`; column masks work the same way per column. For a rule across many tables,
    an ABAC policy on the catalog or schema that targets tagged columns, which Databricks recommends because new
    tables are covered automatically and table owners cannot remove it. For sharing a curated slice, a dynamic
    view, granting `SELECT` on the view only, since the view owner's privileges resolve the base table. I keep the
    UDFs simple `CASE` logic for performance, and I use `is_account_group_member`, not `is_member`, which checks
    workspace groups.

## 5.8 Finding out what exists: information_schema, system tables and lineage

*Level: intermediate.*

### information_schema

**Applies to:** Databricks SQL, Databricks Runtime 10.4 LTS and above, Unity Catalog only
([Information schema](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-information-schema)).
There are two kinds:

- `system.information_schema`, which "provides metadata about objects across all catalogs in the metastore. It
  does not contain metadata about `hive_metastore` objects."
- an `information_schema` inside every catalog, describing that catalog only (`shop.information_schema`).

Both "automatically filter results to include only the objects you have Unity Catalog privileges to access", and
unlike other system tables they need no `SELECT` grant. Two people running the same query can therefore get
different rows, which is correct behavior, not a bug. Views include `CATALOGS`, `SCHEMATA`, `TABLES`, `COLUMNS`,
`VIEWS`, `VOLUMES`, `ROUTINES`, the privilege views (`CATALOG_PRIVILEGES`, `SCHEMA_PRIVILEGES`,
`TABLE_PRIVILEGES`, `VOLUME_PRIVILEGES`, ...), the tag views, and `ROW_FILTERS` and `COLUMN_MASKS`. The notes on
the page: identifiers other than column and tag names are stored lowercase, so compare with lowercase literals
rather than wrapping columns in `LOWER()`; filter selectively (by catalog and schema) to avoid timeouts; `LIMIT`
is not pushed down.

*Databricks only, not run here. Syntax from [Information schema](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-information-schema), [TABLES](https://docs.databricks.com/aws/en/sql/language-manual/information-schema/tables) and [TABLE_PRIVILEGES](https://docs.databricks.com/aws/en/sql/language-manual/information-schema/table_privileges).*

```sql
-- every gold table: type, owner, format, last change
SELECT table_name, table_type, table_owner, data_source_format, last_altered
FROM shop.information_schema.tables
WHERE table_schema = 'gold'
ORDER BY table_name;

-- who can read gold tables, and where each grant comes from
SELECT grantee, table_name, privilege_type, inherited_from
FROM shop.information_schema.table_privileges
WHERE table_schema = 'gold';
```

`TABLE_TYPE` values include `MANAGED`, `EXTERNAL`, `VIEW`, `MATERIALIZED_VIEW`, `STREAMING_TABLE` and `FOREIGN`.
`INHERITED_FROM` names "The ancestor relation that the privilege is inherited from", which is how you find a
schema-level grant that a table-level `REVOKE` did not remove.

Open-source Spark 4.2 has no `information_schema` (the run in 5.2 got `TABLE_OR_VIEW_NOT_FOUND`); locally the
equivalents are `SHOW SCHEMAS`, `SHOW TABLES`, `DESCRIBE TABLE EXTENDED` and `spark.catalog.listTables()`.

### System tables

System tables are "a Databricks-hosted analytical store of your account's operational data found in the `system`
catalog" ([System tables reference](https://docs.databricks.com/aws/en/admin/system-tables/)). They need a Unity
Catalog-enabled workspace, are read-only, and are governed like any other table: "Users with both the account
admin and metastore admin roles have access to system tables by default. To allow other users to query system
tables, the admin must grant users the following permissions: `USE CATALOG` on the system catalog, `USE SCHEMA` on
the system schemas, and `SELECT` on the system schemas." The ones a data engineer meets first:

| Table | Holds | Free retention (per the reference) |
| --- | --- | --- |
| `system.access.audit` (Public Preview) | audit events | 395 days |
| `system.access.table_lineage` | one record per read or write event on a Unity Catalog table or path | 395 days |
| `system.access.column_lineage` | column-level read and write events (with a source) | 395 days |
| `system.query.history` | queries on SQL warehouses and serverless notebooks and jobs | 365 days |
| `system.billing.usage` | billable usage | indefinite |

### Lineage

"Unity Catalog captures lineage automatically for queries run on Databricks, down to the column level, and
aggregates it across all workspaces attached to the metastore"
([Lineage in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage)). It
records which notebooks, jobs, pipelines and queries write a table and which tables, dashboards and models read it.
You view it on a table's **Lineage** tab in Catalog Explorer or query the lineage system tables. Requirements and
limits worth knowing:

- Tables must be registered in Unity Catalog, and queries must go through the DataFrame API or Databricks SQL
  interfaces. Viewing lineage needs at least `BROWSE` on the parent catalog.
- "Lineage data captured before September 1, 2024 is not available."
- "Lineage is not preserved for renamed catalogs, schemas, tables, views, or columns."
- RDDs and global temp views are not captured; UDF lineage is table-level only.
- If the source or target is referenced by path, Catalog Explorer does not show column lineage, but
  `system.access.column_lineage` records it under `source_path`/`target_path`.
- The lineage system tables keep a rolling 395 days; Catalog Explorer and the lineage API keep lineage captured
  after September 1, 2024 indefinitely
  ([Lineage system tables reference](https://docs.databricks.com/aws/en/admin/system-tables/lineage)).

*Databricks only, not run here. Syntax from [Lineage system tables reference](https://docs.databricks.com/aws/en/admin/system-tables/lineage).*

```sql
-- impact analysis: what was written from shop.silver.orders in the last 30 days?
SELECT DISTINCT target_table_full_name, entity_type
FROM system.access.table_lineage
WHERE source_table_full_name = 'shop.silver.orders'
  AND target_table_full_name IS NOT NULL
  AND event_date >= current_date() - INTERVAL 30 DAYS;

-- which downstream columns come from silver.orders.amount?
SELECT DISTINCT target_table_full_name, target_column_name
FROM system.access.column_lineage
WHERE source_table_full_name = 'shop.silver.orders'
  AND source_column_name = 'amount';
```

`entity_type` is `NOTEBOOK`, `JOB`, `PIPELINE`, `DASHBOARD_V3`, `DBSQL_QUERY` and similar, or NULL. A read-only
event has a source and no target, so the `IS NOT NULL` filter keeps only writes.

!!! tip "In the interview"
    **"How do you know what breaks if you change a silver column?"** Unity Catalog lineage. It is captured
    automatically at column level for anything run on Databricks, notebooks, jobs, Lakeflow pipelines (formerly
    [Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) and SQL queries, across all workspaces on the
    metastore. I check the column's lineage in Catalog Explorer, or query `system.access.column_lineage` for
    downstream tables and `system.access.table_lineage` for the jobs and notebooks involved. The caveats I mention:
    lineage is not preserved across renames, UDFs give only table-level lineage, path-based references hide
    column lineage in the UI, and the system tables keep 395 days.

## 5.9 Where data may be used: workspace binding and access modes

*Level: intermediate.*

### Workspace-catalog binding

Because one metastore serves every workspace in a region, "all catalogs are accessible by default from any
workspace attached to the same metastore". **Workspace-catalog binding** restricts a catalog to chosen workspaces,
optionally read-only, and "Access from an unbound workspace is denied, even for users with explicit privilege
grants on the catalog" ([Workspace-catalog binding](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/workspace-catalog-binding)).
That answers Red Rock's third question: bind `shop` (or `shop_prod`) to the production workspace, and a developer
with `SELECT` cannot read it from the development workspace. Other points from the page:

- The default workspace catalog of a new workspace is bound to that workspace only.
- Information schema queries, lineage and Catalog Explorer show only catalogs assigned to the current workspace.
- External locations, storage credentials and service credentials can be bound too.
- Binding needs metastore admin, catalog ownership or `MANAGE` on the catalog. It is set in Catalog Explorer
  (Workspaces tab) or with the CLI.

*Databricks only, not run here. Syntax from [Workspace-catalog binding](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/workspace-catalog-binding).*

```bash
databricks catalogs update shop --isolation-mode ISOLATED --profile <profile-name>
databricks workspace-bindings update-bindings catalog shop \
  --json '{"add": [{"workspace_id": <prod-workspace-id>, "binding_type": <binding-type>}]}' \
  --profile <profile-name>
```

The default `isolation-mode` is `OPEN`. `<binding-type>` is either `"BINDING_TYPE_READ_WRITE"` (the default) or
`"BINDING_TYPE_READ_ONLY"`.

### Access modes

Compute must be configured for Unity Catalog. "Unity Catalog is supported on clusters that run Databricks Runtime
11.3 LTS or above", SQL warehouses support it by default, and "If a cluster is not configured with standard or
dedicated access mode, the cluster can't access data in Unity Catalog" (requirements page). The names changed: the
best practices page speaks of "standard access mode (formerly shared access mode) or dedicated access mode
(formerly single-user or assigned access mode)".

| Access mode | Old name | Who uses it | Languages |
| --- | --- | --- | --- |
| Standard | shared | "multiple users with data isolation among users" | Python, SQL, Scala |
| Dedicated | single user, assigned | "a single user or group" | Python, SQL, Scala, R |

(From the [Compute configuration reference](https://docs.databricks.com/aws/en/compute/configure).) The same page
says the access mode is **Auto** by default, which "defaults to **Standard** unless a machine learning runtime, a
GPU instance type, or a Databricks Runtime lower than 14.3 is selected, in which case **Dedicated** is used", and
"Databricks recommends that you use standard access mode unless your required functionality is not supported".
Standard compute does not support, among others, Databricks Runtime for ML, GPU-enabled compute, R or the RDD APIs
([Standard compute requirements and limitations](https://docs.databricks.com/aws/en/compute/standard-limitations)).
Reading tables with row filters, column masks or dynamic views on dedicated compute needs Databricks Runtime 15.4
LTS or above (section 5.7). [Chapter 6](06-Compute.md) covers compute choices.

## 5.10 The hive_metastore catalog and upgrading to Unity Catalog

*Level: expert.*

### What hive_metastore is

When a workspace that predates Unity Catalog is attached to a metastore, its old per-workspace Hive metastore does
not disappear. "The Unity Catalog metastore is additive", and "The Hive metastore appears as a top-level catalog
called `hive_metastore` in the three-level namespace", so `hive_metastore.sales.sales_raw` works and can even be
joined with Unity Catalog tables ([Work with the legacy Hive metastore alongside Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/hive-metastore)).
A join with legacy data "will only work on the workspace where that data resides". Tables there "do not benefit
from the full set of security and governance features provided by Unity Catalog, such as built-in auditing,
lineage, and access control".

The same page lists how the legacy table ACL model differs, which interviewers use as a "what changed" question:

- Unity Catalog is account-level; the Hive metastore is workspace-level, with workspace-local groups.
- `USE CATALOG` and `USE SCHEMA` are required for all operations; with legacy table ACLs, `USAGE` on the root
  catalog was not required.
- A Unity Catalog view owner needs only `SELECT` on the referenced tables (plus usage privileges); a legacy view
  owner had to own them.
- No `ANY FILE` or `ANONYMOUS FUNCTION` securables, no `DENY`, no `READ_METADATA` privilege in the legacy sense.

During a migration, the default catalog matters. Older workspaces often have `hive_metastore` as the default, and
the default catalog page suggests keeping it during migration "to avoid impacting existing code that references the
Hive metastore". Code with two-part names (`sales.sales_raw`) silently reads the Hive table until the default
changes, which is one more reason to qualify names.

### The upgrade path

The upgrade page lists the steps ([Upgrade a Databricks workspace to Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/upgrade/)):
provision identities at the account level; convert workspace-local groups to account groups; attach the workspace
to a metastore (create one for the region if none exists); upgrade Hive tables and views; grant account principals
access; update queries and jobs to the new names; migrate files off DBFS; move compute to supported runtimes; and
disable legacy features.

For the tables there are two routes.

**Option 1 (the recommended approach on the upgrade page): federate, then upgrade in place.** Hive metastore
federation creates a foreign catalog in Unity Catalog that mirrors the Hive metastore. Then each foreign table is
upgraded in place, which lets you "migrate tables without data movement while preserving table history,
configuration, permissions, and views". For
`SET MANAGED`, the convert page requires Delta format, Databricks Runtime 17.3 or above, and an **external** HMS
table ("The command fails if the table is a managed HMS table").

*Databricks only, not run here. Syntax from [Upgrade a Databricks workspace to Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/upgrade/).*

```sql
ALTER TABLE <foreign_catalog>.<schema>.<table_name> SET MANAGED MOVE;  -- to a UC managed table
ALTER TABLE <foreign_catalog>.<schema>.<table_name> SET EXTERNAL;      -- or to a UC external table
ALTER CATALOG <foreign_catalog> DROP CONNECTION;                       -- when federation is no longer needed
```

`MOVE` disables access to the source table in the external catalog; `COPY` keeps it.

**Option 2: upgrade directly** ([Upgrade Hive tables and views to Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/migrate)):

| Tool | Hive table in | Result in Unity Catalog | Notes |
| --- | --- | --- | --- |
| `SYNC` | external, or managed but stored outside DBFS root (with `AS EXTERNAL`) | external | metadata only, no copy; `DRY RUN` checks first; can be rerun to pick up changes |
| Upgrade wizard (Catalog Explorer) | managed or external | external only | runs `SYNC` on the tables you select |
| `CREATE TABLE ... DEEP CLONE` (CTAS for tables clone cannot handle) | managed Delta tables for clone, including those in the DBFS root; CTAS for the rest | managed | copies data; "Table history is not migrated when you run `CREATE TABLE CLONE`" |
| UCX (Databricks Labs) | managed or external | managed or external | assessment plus workflows for identities, permissions, storage and tables; the only option for a bulk upgrade to managed tables; "not supported directly by Databricks" |

*Databricks only, not run here. Syntax from [SYNC](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-sync).*

```sql
-- check first, then upgrade one table or a whole schema
SYNC TABLE shop.bronze.web_orders FROM hive_metastore.sales.web_orders DRY RUN;
SYNC TABLE shop.bronze.web_orders FROM hive_metastore.sales.web_orders SET OWNER `data_platform_admins`;
SYNC SCHEMA shop.bronze FROM hive_metastore.sales;
```

`SYNC` "performs a write operation (`ALTER TABLE`) to each source table it upgrades to add some additional table
properties for its bookkeeping", so the compute needs write access to the source location. For a table in the DBFS
root it returns the status `DBFS_ROOT_LOCATION` and the page recommends a `DEEP CLONE` instead.

!!! tip "In the interview"
    **"How would you migrate from hive_metastore to Unity Catalog?"** First the foundations: account-level
    identities and groups, a metastore for the region, storage credentials and external locations for the
    existing paths. Then the tables: the docs recommend federating the Hive metastore as a foreign catalog and
    upgrading tables in place with `ALTER TABLE ... SET MANAGED MOVE` (or `SET EXTERNAL`), which keeps history and
    permissions; `SET MANAGED` needs Delta tables that are external in the Hive metastore. Without federation, external tables go across with `SYNC` (dry run first) as UC external
    tables, and managed tables in the DBFS root are copied with `DEEP CLONE` or CTAS, losing history. UCX helps
    plan and run it at scale. Then re-grant to account groups, switch jobs to three-part names and volumes, keep
    `hive_metastore` as the default catalog until the code is switched, and finally disable legacy access.

## 5.11 Putting it together: the Red Rock Supply catalog

*Level: expert.*

This is the complete design, with the four questions of 5.1 answered. It uses one catalog `shop` to keep names
short; with environments, repeat it per catalog (`shop_dev`, `shop_prod`) as in
[chapter 7](07-Medallion-Architecture.md) and bind the production catalog to the production workspace.

**Principals** (all account-level):

| Principal | Kind | Role |
| --- | --- | --- |
| `data_platform_admins` | group | owns the catalog and schemas, manages grants |
| `etl_sp` | service principal | runs the production jobs and pipelines; the only writer |
| `data_engineers` | group | develops pipelines; reads every layer |
| `data_science` | group | reads silver and gold |
| `analysts` | group | reads gold only |
| `support` | group | sees unmasked customer emails |
| `` `account users` `` | built-in group | can discover (browse) everything |

**Grants per layer and team:**

| | bronze | silver | gold | landing volume |
| --- | --- | --- | --- | --- |
| `etl_sp` | `USE SCHEMA`, `CREATE TABLE`, `SELECT`, `MODIFY` | same | same | `READ VOLUME`, `WRITE VOLUME` |
| `data_engineers` | `USE SCHEMA`, `SELECT` | `USE SCHEMA`, `SELECT` | `USE SCHEMA`, `SELECT` | `READ VOLUME` |
| `data_science` | none | `USE SCHEMA`, `SELECT` | `USE SCHEMA`, `SELECT` | none |
| `analysts` | none | none | `USE SCHEMA`, `SELECT` | none |

Everyone in the table also gets `USE CATALOG` on `shop`, and `` `account users` `` gets `BROWSE`.

*Databricks only, not run here. Syntax from [CREATE CATALOG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-catalog), [CREATE SCHEMA](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-schema), [CREATE VOLUME](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-volume), [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant) and [Manage privileges in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/).*

```sql
-- 1. Containers (run by a member of data_platform_admins)
CREATE CATALOG IF NOT EXISTS shop MANAGED LOCATION 's3://rr-lake/managed/shop';
CREATE SCHEMA IF NOT EXISTS shop.bronze COMMENT 'raw, as received';
CREATE SCHEMA IF NOT EXISTS shop.silver COMMENT 'cleaned, deduplicated, conformed';
CREATE SCHEMA IF NOT EXISTS shop.gold   COMMENT 'business-level tables for BI';
CREATE VOLUME IF NOT EXISTS shop.bronze.landing COMMENT 'raw order JSON';

ALTER CATALOG shop OWNER TO `data_platform_admins`;
ALTER SCHEMA shop.bronze OWNER TO `data_platform_admins`;
ALTER SCHEMA shop.silver OWNER TO `data_platform_admins`;
ALTER SCHEMA shop.gold   OWNER TO `data_platform_admins`;

-- 2. Discovery for everyone, usage for the teams
GRANT BROWSE ON CATALOG shop TO `account users`;
GRANT USE CATALOG ON CATALOG shop TO `etl_sp`;
GRANT USE CATALOG ON CATALOG shop TO `data_engineers`;
GRANT USE CATALOG ON CATALOG shop TO `data_science`;
GRANT USE CATALOG ON CATALOG shop TO `analysts`;

-- 3. The writer: the pipeline's service principal, per layer
GRANT USE SCHEMA, CREATE TABLE, SELECT, MODIFY ON SCHEMA shop.bronze TO `etl_sp`;
GRANT USE SCHEMA, CREATE TABLE, SELECT, MODIFY ON SCHEMA shop.silver TO `etl_sp`;
GRANT USE SCHEMA, CREATE TABLE, SELECT, MODIFY ON SCHEMA shop.gold   TO `etl_sp`;
GRANT READ VOLUME, WRITE VOLUME ON VOLUME shop.bronze.landing TO `etl_sp`;

-- 4. Readers, per layer
GRANT USE SCHEMA, SELECT ON SCHEMA shop.bronze TO `data_engineers`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop.silver TO `data_engineers`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop.gold   TO `data_engineers`;
GRANT READ VOLUME ON VOLUME shop.bronze.landing TO `data_engineers`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop.silver TO `data_science`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop.gold   TO `data_science`;
GRANT USE SCHEMA, SELECT ON SCHEMA shop.gold   TO `analysts`;

-- 5. Check
SHOW GRANTS ON SCHEMA shop.gold;
```

Then the column mask and row filter from 5.7 on `shop.silver.customers` (or an ABAC policy on `shop.silver`), and
the binding from 5.9. Why each choice:

- **Schema-level grants**, so new tables in a layer need no new grants (inheritance, 5.6).
- **Only `etl_sp` has `MODIFY`**, following "Reserve direct `MODIFY` access to production tables for service
  principals". Engineers develop in a dev catalog where they have write access.
- **Groups own everything.** Tables created by `etl_sp` are owned by it; transfer them to `data_platform_admins`
  with `ALTER TABLE ... OWNER TO`, or have the platform team own the schemas so they can manage the tables anyway.
- **Bronze is closed to analysts and data science.** Bronze holds raw emails and addresses, and the medallion page
  quoted in [chapter 7](07-Medallion-Architecture.md) describes bronze as not for analysts.
- **Managed tables and a managed volume**, the defaults Databricks recommends; one external volume only if the
  partner system must write files directly.

## 5.12 Practice questions

*Level: mixed.*

**Q1. In `shop.gold.daily_sales`, name each level, and say what contains the catalog.**

??? success "Answer"
    `shop` is the catalog, `gold` the schema, `daily_sales` the table. The catalog lives in a Unity Catalog
    metastore, the top-level container, one per cloud region.

    **Why:** Unity Catalog's three-level namespace is `catalog.schema.object`; the metastore is above it and is
    "scoped to a single cloud region" (securable objects reference).

**Q2. Red Rock opens a second workspace in another cloud region. Can it use the same metastore?**

??? success "Answer"
    No. A metastore can be attached to multiple workspaces in the **same** region; another region needs its own
    metastore. To use data across regions, the best practices page points to sharing with
    [OpenSharing](https://docs.databricks.com/aws/en/opensharing/) (formerly Delta Sharing; the rename is announced in
    the [Databricks blog, Nov 5, 2026](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next)).

    **Why:** "Your organization requires one metastore per region in which it operates. A single metastore can be
    attached to multiple workspaces in the same region."

**Q3. What is the difference between running `USE CATALOG shop` and running `GRANT USE CATALOG ON CATALOG shop TO analysts`?**

??? success "Answer"
    The first is a statement that sets the session's current catalog (and resets the current schema to
    `default`). The second grants the `USE CATALOG` privilege, which the analysts need to interact with any object
    in `shop`. Running the statement grants nothing, and having the privilege does not change anyone's current
    catalog.

    **Why:** the USE CATALOG reference page separates the command from the privilege of the same name.

**Q4. A job runs `SELECT * FROM orders` with no `USE` statement. How does Databricks decide which catalog to use?**

??? success "Answer"
    In order: a catalog set for the session (`USE CATALOG` or a JDBC setting); then the cluster's
    `spark.databricks.sql.initial.catalog.namespace`; then the workspace default catalog. In a Lakeflow pipeline (formerly [Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)),
    the pipeline's configured catalog overrides the workspace default. The schema is the session's current schema
    (`default` unless set). Compute that is not Unity Catalog-capable uses `hive_metastore`.

    **Why:** Manage the default catalog page. Fully qualified names avoid the question entirely.

**Q5. Which Unity Catalog objects come in managed and external variants?**

??? success "Answer"
    Tables and volumes only. Views, functions and models do not have managed and external variants.

    **Why:** the managed-vs-external page: "The distinction between managed and external applies to tables and
    volumes only."

**Q6. What does this local run print for the external table after the `DROP` and re-register, and why?**

```sql
CREATE TABLE bronze.orders_external (order_id INT, customer_id INT, status STRING, amount DECIMAL(10,2))
USING DELTA LOCATION '<work>/lake/bronze/orders_ext';
INSERT INTO bronze.orders_external VALUES (1001, 7, 'PLACED', 59.90), (1002, 9, 'SHIPPED', 249.00);
DROP TABLE bronze.orders_external;
CREATE TABLE bronze.orders_external USING DELTA LOCATION '<work>/lake/bronze/orders_ext';
SELECT count(*) FROM bronze.orders_external;
```

??? success "Answer"
    `2`. The section 5.4 run showed both rows back after re-registering, and `DESCRIBE HISTORY` still showed
    versions 0 (`CREATE TABLE`) and 1 (`WRITE`).

    **Why:** dropping an external table removes only the catalog entry. The Parquet files and the `_delta_log`
    stay in the folder, and the log carries the schema and history, so `CREATE TABLE ... LOCATION` without a
    column list picks everything up again.

**Q7. On Databricks, a managed table was dropped by mistake three days ago. Recover it.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [UNDROP](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-undrop-table).*

    ```sql
    UNDROP TABLE shop.silver.orders;
    ```

    Then recreate any primary and foreign key constraints with `ALTER TABLE ... ADD CONSTRAINT`, because
    `UNDROP` does not restore them. Ownership goes back to the previous owner; privileges and properties are
    recovered.

    **Why:** the default recovery period is 7 days (configurable per catalog or schema to 0 hours or 7 to 30 days,
    Public Preview). `UNDROP` needs Databricks Runtime 12.2 LTS or above and the parent schema and catalog must
    exist.

**Q8. Someone dropped `shop.silver.orders`, then a job recreated an empty `shop.silver.orders`. You need the old one back. How?**

??? success "Answer"
    *Databricks only, not run here. Syntax from [UNDROP](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-undrop-table).*

    ```sql
    SHOW TABLES DROPPED IN shop.silver;                    -- find the tableid of the dropped one
    ALTER TABLE shop.silver.orders RENAME TO orders_empty;  -- free the name
    UNDROP TABLE WITH ID '<tableid>';
    ```

    **Why:** `UNDROP` cannot restore over an existing name; the reference says to rename the existing relation
    first, and to use `SHOW TABLES DROPPED` plus `UNDROP TABLE WITH ID` when several dropped tables share a name.

**Q9. Find the bug. This was run in a Unity Catalog workspace:**

```sql
CREATE SCHEMA shop.silver LOCATION 's3://rr-lake/managed/silver';
```

??? success "Answer"
    `LOCATION` is not supported for schemas in Unity Catalog; it is the Hive metastore form. Use
    `MANAGED LOCATION`, with a path inside an external location on which you have `CREATE MANAGED STORAGE`:

    *Databricks only, not run here. Syntax from [CREATE SCHEMA](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-schema).*

    ```sql
    CREATE SCHEMA shop.silver MANAGED LOCATION 's3://rr-lake/managed/silver';
    ```

    **Why:** CREATE SCHEMA: "`LOCATION` is not supported in Unity Catalog. If you want to specify a storage
    location for a schema in Unity Catalog, use `MANAGED LOCATION`." Often you do not need either, because the
    catalog's managed location is used.

**Q10. `shop` has a managed location, `shop.gold` has none, the metastore has one too. Where do the files of a new managed table in `shop.gold` go?**

??? success "Answer"
    Under the catalog's managed location (in a hashed `__unitystorage` subfolder).

    **Why:** the lowest level that has a location wins: schema, else catalog, else metastore.

**Q11. List the privileges needed to create an external table `shop.bronze.partner_orders` at `s3://rr-lake/bronze/partner_orders`.**

??? success "Answer"
    `CREATE EXTERNAL TABLE` on an external location that covers the path, `USE CATALOG` on `shop`, `USE SCHEMA`
    on `shop.bronze`, and `CREATE TABLE` on `shop.bronze`.

    **Why:** Work with external tables, prerequisites. Granting `CREATE EXTERNAL TABLE` on the external location
    rather than the storage credential is recommended because it is scoped to a path.

**Q12. What is the difference between a storage credential and an external location?**

??? success "Answer"
    A storage credential holds a cloud identity (an IAM role on AWS). An external location pairs a storage path
    with a storage credential and governs access to that path. Several external locations can share a credential.
    Users get privileges on external locations (or on tables and volumes inside them), never the credential's
    keys.

    **Why:** securable objects reference and the cloud storage overview; the split lets admins control who may
    create locations (privileges on the credential) separately from who may use a path (privileges on the
    location).

**Q13. A user has `WRITE FILES` on an external location but gets `PERMISSION_DENIED` when writing files. Why?**

??? success "Answer"
    `WRITE FILES` also requires `READ FILES` on the same external location. Grant both, or better, give the user a
    volume with `WRITE VOLUME`.

    **Why:** privileges reference: "Any principal that has the `WRITE FILES` privilege only on an external location
    receives a `PERMISSION_DENIED` error when attempting to write files", and Databricks recommends volumes over
    direct file privileges.

**Q14. Write the SQL to create a managed volume `landing` in `shop.bronze`, let `etl_sp` write to it and `data_engineers` read it. Then give the path of a file `orders/2026-03-01.json` in it.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [CREATE VOLUME](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-volume) and [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant).*

    ```sql
    CREATE VOLUME shop.bronze.landing;
    GRANT READ VOLUME, WRITE VOLUME ON VOLUME shop.bronze.landing TO `etl_sp`;
    GRANT READ VOLUME ON VOLUME shop.bronze.landing TO `data_engineers`;
    ```

    Path: `/Volumes/shop/bronze/landing/orders/2026-03-01.json`. Both principals also need `USE CATALOG` on `shop`
    and `USE SCHEMA` on `shop.bronze`.

    **Why:** volume paths are `/Volumes/<catalog>/<schema>/<volume>/<path>`, and reading files in a volume needs
    the usage privileges plus `READ VOLUME`.

**Q15. Can you register the JSON files in `shop.bronze.landing` as a Unity Catalog table so analysts can query them?**

??? success "Answer"
    No. Volumes are for path-based access only; you ingest the files into a table (for example a bronze table with
    Auto Loader or `COPY INTO`) and grant on that table.

    **Why:** volumes page: "You can't register files in volumes as tables in Unity Catalog."

**Q16. Scenario: an analyst can see the `shop.gold` schema in Catalog Explorer, but `SELECT * FROM shop.gold.daily_sales` fails with a permission error. What is missing?**

??? success "Answer"
    Most likely `SELECT` (on the table, or on `shop.gold` or `shop` to inherit it). Because seeing objects can come
    from `BROWSE`, also check `USE CATALOG` on `shop` and `USE SCHEMA` on `shop.gold`: all three are required to
    read. Fix with `GRANT USE SCHEMA, SELECT ON SCHEMA shop.gold TO analysts` (plus `USE CATALOG`). If grants look
    right, check that the query runs on a SQL warehouse or on compute with standard or dedicated access mode.

    **Why:** `BROWSE` shows metadata "without needing `USE CATALOG` or `USE SCHEMA`" and gives no data access;
    reading needs `USE CATALOG`, `USE SCHEMA` and `SELECT`.

**Q17. The owner of `shop.gold.daily_sales` granted Maria `SELECT` on it. Maria still cannot read it. Why, and who can fix it?**

??? success "Answer"
    Maria lacks `USE CATALOG` on `shop` or `USE SCHEMA` on `shop.gold`. The table owner cannot fix that; only the
    catalog or schema owner (or someone with `MANAGE` on them) can grant the usage privileges.

    **Why:** usage privileges are the boundary that "prevents table owners from granting access outside approved
    boundaries" (permissions concepts page).

**Q18. Write the grants so the `analysts` group can read every current and future table in gold, and nothing else in `shop`.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant).*

    ```sql
    GRANT USE CATALOG ON CATALOG shop TO `analysts`;
    GRANT USE SCHEMA, SELECT ON SCHEMA shop.gold TO `analysts`;
    ```

    **Why:** `SELECT` on a schema applies to all current and future tables and views in it. `USE CATALOG` alone
    gives no data in bronze or silver.

**Q19. Find the bug: `GRANT SELECT ON SCHEMA shop.gold TO users;` fails.**

??? success "Answer"
    `users` is the workspace-local root group and cannot be granted privileges on Unity Catalog objects. Use an
    account group, or `` `account users` `` (with backticks, because of the space) for everyone in the account.

    **Why:** Principal reference page, and the requirement that only account-level groups appear in Unity Catalog
    `GRANT` statements.

**Q20. A metastore admin grants Lee `CREATE CATALOG` on the metastore. Can Lee read the tables in `shop`?**

??? success "Answer"
    No. Metastore-level privileges do not inherit to child objects; `CREATE CATALOG` only allows creating catalogs.
    Lee would own any catalog Lee creates, but needs grants for `shop`.

    **Why:** "Privileges granted on a metastore do not inherit to child objects" (permissions concepts page).
    `READ METADATA` is the one exception.

**Q21. `analysts` were granted `ALL PRIVILEGES` on `shop.gold`. Can they grant `SELECT` on gold tables to the `finance` group?**

??? success "Answer"
    No. Granting privileges needs ownership or `MANAGE`, and `ALL PRIVILEGES` does not include `MANAGE`. (They can
    read and write gold, which is probably more than intended: `ALL PRIVILEGES` on a schema implies all
    schema-level privileges, including `MODIFY`.)

    **Why:** `ALL PRIVILEGES` excludes `EXTERNAL USE SCHEMA`, `EXTERNAL USE LOCATION`, `MANAGE` and
    `READ METADATA` "to avoid accidental data exfiltration or privilege escalation" (GRANT page).

**Q22. A nightly job running as service principal `etl_sp` creates `shop.gold.product_revenue`. Who owns it, and what should you do?**

??? success "Answer"
    `etl_sp` owns it, because the creator becomes the initial owner. Transfer ownership to a group:

    *Databricks only, not run here. Syntax from [Manage privileges in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/).*

    ```sql
    ALTER TABLE shop.gold.product_revenue OWNER TO `data_platform_admins`;
    ```

    **Why:** best practices: "Use groups to assign ownership to most securable objects" and "Creators should
    reassign ownership to appropriate groups." A schema owner can manage the table even without owning it.

**Q23. You ran `REVOKE SELECT ON TABLE shop.gold.daily_sales FROM analysts`. It succeeded, but analysts can still read the table. Why?**

??? success "Answer"
    Their `SELECT` comes from the schema (or catalog), not from the table. `REVOKE` removes only an explicit grant
    on the object named, and succeeds even if nothing was granted there. Find the source with `SHOW GRANTS` or the
    `inherited_from` column of `information_schema.table_privileges`, then revoke at that level (or move the table
    to a schema they cannot read).

    **Why:** REVOKE "Revokes an explicitly granted or denied privilege" and "succeeds even if the specified
    privileges were not granted in the first place"; grants on a schema apply to all its tables.

**Q24. What is the difference between being the owner of a schema and having `MANAGE` on it?**

??? success "Answer"
    Both can grant and revoke, transfer ownership and drop. The owner is exactly one principal and implicitly has
    all capabilities, including data access. `MANAGE` can be granted to many principals and does not include data
    access (holders can grant it to themselves). Neither shows as `ALL PRIVILEGES` in `SHOW GRANTS`.

    **Why:** permissions concepts page, "Ownership versus the `MANAGE` privilege".

**Q25. Write a column mask so only the `support` group sees `email` in `shop.silver.customers`.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Manually apply row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/manually-apply).*

    ```sql
    CREATE FUNCTION shop.silver.email_mask(email STRING)
    RETURN CASE WHEN is_account_group_member('support') THEN email ELSE '***REDACTED***' END;
    ALTER TABLE shop.silver.customers ALTER COLUMN email SET MASK shop.silver.email_mask;
    ```

    **Why:** a column mask is a SQL UDF that takes the column value and returns it or a masked value; it applies to
    every query on the table, unlike a view, which users could go around if they had `SELECT` on the table.

**Q26. Write a row filter so that everyone except `data_admins` sees only customers with `country = 'CA'`.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Manually apply row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/manually-apply).*

    ```sql
    CREATE FUNCTION shop.silver.ca_only(country STRING)
    RETURN IF(is_account_group_member('data_admins'), true, country = 'CA');
    ALTER TABLE shop.silver.customers SET ROW FILTER shop.silver.ca_only ON (country);
    ```

    **Why:** rows where the filter returns `FALSE` are excluded at query time. A table can have only one row
    filter, so combine conditions inside the function.

**Q27. Find the bug. After these statements, every query on `shop.silver.customers` fails:**

```sql
DROP FUNCTION shop.silver.ca_only;
```

??? success "Answer"
    The function was still attached as the table's row filter. Fix the table with
    `ALTER TABLE shop.silver.customers DROP ROW FILTER;` and, in future, drop the filter before the function.

    **Why:** "You must perform the `ALTER TABLE ... DROP ROW FILTER` command before you drop the function. If you
    don't, the table will be in an inaccessible state."

**Q28. When would you pick a row filter, an ABAC policy, or a dynamic view?**

??? success "Answer"
    Row filter or column mask: logic specific to one table. ABAC policy: the same rule across many tables, driven
    by governed tags, applied automatically to new tables and not removable by table owners (Databricks'
    recommended approach). Dynamic view: exposing a curated, joined or transformed slice to users who should not
    see the base tables.

    **Why:** Row filters and column masks overview and the access control page.

**Q29. A dynamic view uses `is_member('support')`. What is wrong with that on Unity Catalog?**

??? success "Answer"
    `is_member()` checks workspace-level groups, not account groups, so it can give the wrong answer for Unity
    Catalog access. Use `is_account_group_member('support')`.

    **Why:** Create a dynamic view: `is_member()` "is provided for compatibility with the existing Hive metastore.
    Avoid using it with views against Unity Catalog data."

**Q30. An admin and an analyst run `SELECT count(*) FROM system.information_schema.tables` and get different numbers. Bug?**

??? success "Answer"
    No. The information schema filters rows to the objects each user has privileges to access. It also excludes
    `hive_metastore` objects, and in a workspace only shows catalogs bound to that workspace.

    **Why:** Information schema page ("automatically filter results") and the workspace-catalog binding page.

**Q31. Write a query listing every table in `shop.gold` with its type and owner.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [TABLES](https://docs.databricks.com/aws/en/sql/language-manual/information-schema/tables).*

    ```sql
    SELECT table_name, table_type, table_owner
    FROM shop.information_schema.tables
    WHERE table_schema = 'gold';
    ```

    **Why:** each catalog has its own `information_schema`; identifiers are stored lowercase, so compare with
    `'gold'` directly instead of `LOWER(table_schema)`.

**Q32. On the local Spark 4.2 engine, `SELECT table_name FROM information_schema.tables` fails. Why, and what do you use instead?**

??? success "Answer"
    The run in 5.2 returned `TABLE_OR_VIEW_NOT_FOUND`: open-source Spark 4.2 has no information schema; it is a
    Unity Catalog feature. Locally use `SHOW TABLES IN silver`, `DESCRIBE TABLE EXTENDED`, or
    `spark.catalog.listTables("silver")`.

    **Why:** the Databricks information schema "Applies to: Databricks SQL, Databricks Runtime 10.4 LTS and above,
    Unity Catalog only".

**Q33. You plan to rename `shop.silver.orders.amount`. How do you find what depends on it, and what are the caveats?**

??? success "Answer"
    Open the column's lineage in Catalog Explorer, or query
    `system.access.column_lineage WHERE source_table_full_name = 'shop.silver.orders' AND source_column_name = 'amount'`,
    and `system.access.table_lineage` to find the jobs and notebooks. Caveats: lineage before September 1, 2024 is
    not available; the system tables keep 395 days; UDFs give table-level lineage only; path-based references hide
    column lineage in the UI; and after the rename, lineage is not preserved, so capture it first.

    **Why:** Lineage in Unity Catalog, limitations section.

**Q34. An analyst gets a permission error on `system.access.table_lineage`. Why?**

??? success "Answer"
    System tables are governed by Unity Catalog. Only users with both the account admin and metastore admin roles
    have access by default; others need `USE CATALOG` on `system`, `USE SCHEMA` on the system schema and `SELECT`
    on it.

    **Why:** System tables reference, "Grant access to system tables". The information schema is the exception and
    needs no `SELECT` grant.

**Q35. A developer with `SELECT` on `shop_prod.gold.daily_sales` gets an error querying it from the development workspace, but the same query works in production. Why?**

??? success "Answer"
    `shop_prod` is bound to the production workspace. Workspace-catalog binding overrides grants: access from an
    unbound workspace is denied even with explicit privileges.

    **Why:** "Workspace binding supersedes individual privilege grants" (securable objects reference).

**Q36. A cluster can query `hive_metastore` tables but sees no Unity Catalog catalogs. What do you check?**

??? success "Answer"
    The access mode and runtime. Unity Catalog needs standard (formerly shared) or dedicated (formerly single
    user) access mode on Databricks Runtime 11.3 LTS or above, or a SQL warehouse. (The rename is on the
    [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices)
    page.) Compute that is not Unity
    Catalog-capable falls back to `hive_metastore` as its default catalog.

    **Why:** requirements page ("If a cluster is not configured with standard or dedicated access mode, the cluster
    can't access data in Unity Catalog") and the default catalog page.

**Q37. Upgrade the Hive external table `hive_metastore.sales.web_orders` (Delta, in `s3://rr-lake/legacy/web_orders`) to Unity Catalog without copying data, using SQL only.**

??? success "Answer"
    Make sure an external location covers `s3://rr-lake/legacy/` and you have `CREATE EXTERNAL TABLE` on it, then:

    *Databricks only, not run here. Syntax from [SYNC](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-sync).*

    ```sql
    SYNC TABLE shop.bronze.web_orders FROM hive_metastore.sales.web_orders DRY RUN;
    SYNC TABLE shop.bronze.web_orders FROM hive_metastore.sales.web_orders;
    ```

    The result is a Unity Catalog external table on the same files; convert it later with
    `ALTER TABLE ... SET MANAGED` if you want a managed table.

    **Why:** `SYNC` upgrades Hive external tables to Unity Catalog external tables; `DRY RUN` returns
    `DRY_RUN_SUCCESS` if the table can be upgraded. Note that `SYNC` writes table properties to the source table.

**Q38. A Hive managed table lives in the DBFS root. `SYNC` returns `DBFS_ROOT_LOCATION`. What now, and what do you lose?**

??? success "Answer"
    Copy it into Unity Catalog with `CREATE TABLE ... DEEP CLONE` (or CTAS) into a managed table. The table
    history is not migrated: the new table starts at version 0, so time travel to pre-migration versions is gone.

    **Why:** `SYNC` cannot upgrade Hive managed tables stored in workspace storage; the migrate page says "Table
    history is not migrated when you run `CREATE TABLE CLONE`".

**Q39. You converted the external table `shop.bronze.partner_orders` to managed with `SET MANAGED`, and the partner's tool, which writes by path, broke a week later. Can you undo the conversion?**

??? success "Answer"
    Yes, within 14 days: `ALTER TABLE shop.bronze.partner_orders UNSET MANAGED;` points the table back at the
    original external location and keeps the writes made after conversion. Run `UNSET MANAGED` before any drop.

    **Why:** Convert external or foreign Delta Lake tables to Unity Catalog managed tables: rollback "within 14
    days by using the `UNSET MANAGED` command". The deeper fix is to give external writers access through the open
    APIs, or keep that table external.

**Q40. What does `DROP SCHEMA shop.bronze CASCADE` do to (a) its managed tables, (b) its external tables, (c) its managed volume `landing`? Can you get the schema back?**

??? success "Answer"
    (a) Managed tables are dropped and their files purged after the recovery period. (b) External tables lose
    their metadata; their files stay. (c) The managed volume is dropped and its files deleted (managed volume
    behavior). The schema itself cannot be recovered: schemas "Cannot be recovered after delete". `UNDROP` needs
    the parent schema to exist; whether recreating the schema lets you undrop the cascaded tables is not stated on
    the pages checked (not verified). Use the default `RESTRICT` to avoid this.

    **Why:** Object storage lifecycle: "Dropping a catalog or schema with `CASCADE` removes the contained tables and
    volumes, each according to its own managed-or-external behavior", and the recovery table on the same page.

## Sources

- [What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) (last updated Sep 11, 2026)
- [Unity Catalog securable objects reference](https://docs.databricks.com/aws/en/data-governance/unity-catalog/securable-objects) (last updated Nov 6, 2026)
- [Managed versus external assets in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/managed-versus-external) (last updated Oct 30, 2026)
- [Unity Catalog requirements and limitations](https://docs.databricks.com/aws/en/data-governance/unity-catalog/requirements) (last updated Sep 16, 2026)
- [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) (last updated Oct 30, 2026)
- [Access control in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/) (last updated Oct 15, 2026)
- [Unity Catalog permissions model concepts](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/permissions-concepts) (last updated Nov 9, 2026)
- [Unity Catalog privileges reference](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/privileges-reference) (last updated Nov 6, 2026)
- [Manage privileges in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/manage-privileges/) (last updated Oct 15, 2026)
- [Workspace-catalog binding](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/workspace-catalog-binding) (last updated Sep 11, 2026)
- [What are catalogs in Databricks?](https://docs.databricks.com/aws/en/catalogs/) (last updated Sep 11, 2026)
- [Manage the default catalog](https://docs.databricks.com/aws/en/catalogs/default) (last updated Sep 11, 2026)
- [Unity Catalog managed tables for Delta Lake and Apache Iceberg](https://docs.databricks.com/aws/en/tables/managed) (last updated Nov 9, 2026)
- [Work with external tables](https://docs.databricks.com/aws/en/tables/external) (last updated Oct 6, 2026)
- [Convert external or foreign Delta Lake tables to Unity Catalog managed tables](https://docs.databricks.com/aws/en/tables/convert-to-managed) (last updated Nov 9, 2026)
- [Object storage lifecycle in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/object-storage-lifecycle) (last updated Nov 5, 2026)
- [Specify a managed storage location in Unity Catalog](https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/managed-storage) (last updated Sep 11, 2026)
- [Connect to cloud object storage using Unity Catalog](https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/) (last updated Sep 11, 2026)
- [What are Unity Catalog volumes?](https://docs.databricks.com/aws/en/volumes/) (last updated Oct 12, 2026)
- [Work with files in Unity Catalog volumes](https://docs.databricks.com/aws/en/volumes/volume-files) (last updated Nov 10, 2026)
- [Row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/) (last updated Nov 6, 2026)
- [Manually apply row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/manually-apply) (last updated Oct 8, 2026)
- [Create a dynamic view](https://docs.databricks.com/aws/en/views/dynamic) (last updated Oct 6, 2026)
- [Attribute-based access control in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/) (last updated Oct 22, 2026)
- [Create and manage row filter and column mask policies](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/policies) (last updated Oct 15, 2026)
- [Information schema](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-information-schema) (last updated Sep 11, 2026)
- [TABLES](https://docs.databricks.com/aws/en/sql/language-manual/information-schema/tables) (last updated Sep 11, 2026)
- [TABLE_PRIVILEGES](https://docs.databricks.com/aws/en/sql/language-manual/information-schema/table_privileges) (last updated Sep 11, 2026)
- [System tables reference](https://docs.databricks.com/aws/en/admin/system-tables/) (last updated Nov 9, 2026)
- [Lineage in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage) (last updated Nov 4, 2026)
- [Lineage system tables reference](https://docs.databricks.com/aws/en/admin/system-tables/lineage) (last updated Nov 4, 2026)
- [Compute configuration reference](https://docs.databricks.com/aws/en/compute/configure) (last updated Nov 6, 2026)
- [Standard compute requirements and limitations](https://docs.databricks.com/aws/en/compute/standard-limitations) (last updated Nov 5, 2026)
- [Work with the legacy Hive metastore alongside Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/hive-metastore) (last updated Sep 11, 2026)
- [Upgrade a Databricks workspace to Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/upgrade/) (last updated Oct 9, 2026)
- [Upgrade Hive tables and views to Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/migrate) (last updated Oct 6, 2026)
- [SYNC](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-sync) (last updated Sep 11, 2026)
- [GRANT](https://docs.databricks.com/aws/en/sql/language-manual/security-grant) (last updated Sep 11, 2026)
- [REVOKE](https://docs.databricks.com/aws/en/sql/language-manual/security-revoke) (last updated Sep 11, 2026)
- [SHOW GRANTS](https://docs.databricks.com/aws/en/sql/language-manual/security-show-grant) (last updated Sep 11, 2026)
- [Privileges and securable objects in Unity Catalog](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-privileges) (last updated Sep 11, 2026)
- [Principal](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-principal) (last updated Sep 11, 2026)
- [USE CATALOG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-use-catalog) (last updated Oct 29, 2026)
- [USE SCHEMA](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-use-schema) (last updated Sep 11, 2026)
- [CREATE CATALOG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-catalog) (last updated Sep 16, 2026)
- [CREATE SCHEMA](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-schema) (last updated Sep 16, 2026)
- [ALTER SCHEMA](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-schema) (last updated Sep 16, 2026)
- [ALTER CATALOG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-catalog) (last updated Sep 16, 2026)
- [CREATE VOLUME](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-volume) (last updated Sep 11, 2026)
- [CREATE EXTERNAL LOCATION](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-location) (last updated Sep 11, 2026)
- [Credentials](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-storage-credentials) (last updated Sep 11, 2026)
- [DROP TABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-drop-table) (last updated Nov 4, 2026)
- [UNDROP](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-undrop-table) (last updated Nov 5, 2026)
- [What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/) (last updated Oct 27, 2026) and the Databricks blog post [From Delta Sharing to OpenSharing: what changed, what's next](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next) (Nov 5, 2026), for the rename only
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026), for the rename of Delta Live Tables only
