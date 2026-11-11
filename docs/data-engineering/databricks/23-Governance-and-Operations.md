# 23. Governance and operations

*A data platform that loads data correctly is half the job. The other half is knowing where personal data lives,
proving who changed or read it, erasing a customer for real when asked, keeping secrets out of code, keeping
developers away from production, and noticing a broken job before the business does. This chapter turns those duties
into concrete Databricks tools and Delta Lake mechanics, runs the parts open-source Delta can show (a full
right-to-be-forgotten delete, audit queries over table history, clones as backups), and gives the interview answers
for "how do you handle a GDPR delete?", "who changed this table?" and "how do you keep prod safe?".*

!!! abstract "In this chapter"
    **You will learn:**

    - tags, governed tags and Data Classification to find personal data, and how tags drive ABAC policies
    - three audit sources (table history, the audit log system table, query history) and which question each answers
    - a right-to-be-forgotten delete on Delta end to end: `MERGE` delete, time travel, change data feed, deletion
      vectors, `REORG ... APPLY (PURGE)`, `VACUUM`, and what is still on disk at each step
    - secrets (workspace secret scopes and Unity Catalog secrets), service principals and least privilege
    - dev, staging and prod with catalogs, workspace binding and service principals
    - monitoring and alerting: jobs system tables, job notifications, SQL alerts, data quality monitoring
      (anomaly detection and data profiling, formerly Lakehouse Monitoring)
    - cost guard rails in brief, OpenSharing and clean rooms, Lakehouse Federation, Iceberg interoperability
    - backups with clones and what disaster recovery does and does not protect

    **You need:** [Chapter 4](04-Delta-Lake.md) (transaction log, time travel, `VACUUM`),
    [Chapter 5](05-Unity-Catalog.md) (namespace, grants, row filters, column masks, ABAC, lineage),
    [Chapter 6](06-Compute.md) (cost and `system.billing.usage`). [Chapter 11](11-Structured-Streaming.md) helps
    for the streaming parts.

    **Levels:** sections 23.1 to 23.3 beginner, 23.4 to 23.9 intermediate, 23.10 expert.

**About the examples.** Almost everything in this chapter is a Databricks service: Unity Catalog tags, system
tables, secrets, alerts, data quality monitoring, OpenSharing. Those blocks are labeled "Databricks only, not run
here" and copy their syntax from the page named in the label. What open-source Delta Lake can honestly show was
run on Apache Spark 4.2.0 with Delta Lake 4.4.1: the erasure lifecycle on disk, audit questions answered from
`DESCRIBE HISTORY`, `RESTORE`, and clones. Locally there is no Unity Catalog, so the layers are plain schemas
(`bronze`, `silver`, `gold`, `ops`, `backup`) standing in for `shop.bronze`, `shop.silver` and so on. Scripts and
full output: `src/ch23/ch23_01_gdpr_delete.py`, `ch23_02_audit_clone.py` and `ch23_03_practice.py`, each with its
`.out` file.

## 23.1 The problem: what governance and operations cover

*Level: beginner.*

Red Rock Supply's platform is live: bronze, silver and gold in the `shop` catalog, nightly jobs, analysts on a SQL
warehouse. Then the questions start arriving, and none of them is about loading data:

| Question | Tool on Databricks | Section |
| --- | --- | --- |
| Which tables and columns hold personal data? | tags, governed tags, Data Classification | 23.2 |
| Who changed `shop.silver.orders` last night? Who read customer emails? | `DESCRIBE HISTORY`, `system.access.audit`, `system.query.history` | 23.3 |
| Customer 7 asked to be forgotten. Is she really gone? | `MERGE` delete, `REORG ... APPLY (PURGE)`, `VACUUM` | 23.4 |
| Where does the Postgres password live? Who runs the prod job? | secrets, service principals | 23.5 |
| Can a developer break production? | catalogs per environment, workspace binding | 23.6 |
| Did the 3 a.m. job fail? Is the orders table late or short? | jobs system tables, notifications, SQL alerts, data quality monitoring | 23.7 |
| Why did the bill double? | tags, budgets, policies ([Chapter 6](06-Compute.md)) | 23.8 |
| A partner wants our gold data; we want their Postgres data | OpenSharing, clean rooms, Lakehouse Federation | 23.9 |
| What if someone corrupts silver, or the region goes down? | time travel, clones, disaster recovery | 23.10 |

Grants (who may read or write what) are the foundation of all of this and are taught in
[Chapter 5](05-Unity-Catalog.md); this chapter assumes them and builds the practice on top.

## 23.2 Tags and classification: finding the personal data

*Level: beginner.*

**The problem.** A GDPR request or a security review starts with "where is this person's data?". In a lakehouse
with hundreds of tables, nobody knows by heart which columns hold emails, names or addresses.

**Tags.** "Tags are attributes that include keys and optional values that you can use to organize and categorize
securable objects in Unity Catalog" ([Apply tags to Unity Catalog securable objects](https://docs.databricks.com/aws/en/database-objects/tags)).
They can be set on catalogs, schemas, tables, table columns, volumes, views, functions, secrets and more. Red Rock
tags its personal-data columns once:

*Databricks only, not run here. Syntax from [Apply tags to Unity Catalog securable objects](https://docs.databricks.com/aws/en/database-objects/tags) and [SET TAG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-set-tag).*

```sql
-- Databricks Runtime 13.3 and above
ALTER TABLE shop.silver.customers ALTER COLUMN email SET TAGS ('pii' = 'email');
-- Databricks Runtime 16.1 and above: SET TAG / UNSET TAG
SET TAG ON COLUMN shop.silver.customers.name pii = name;
SET TAG ON TABLE shop.silver.customers data_owner = crm_team;

-- every column tagged pii in the shop catalog
SELECT schema_name, table_name, column_name, tag_value
FROM shop.information_schema.column_tags
WHERE tag_name = 'pii';
```

`SET TAG` "Applies to: Databricks SQL Databricks Runtime 16.1 and above"; if a tag with the same key already exists
on the object, it raises an error rather than overwriting. You need `APPLY TAG` on the object plus `USE SCHEMA` and
`USE CATALOG` on its parents (or ownership). Constraints worth remembering from the tags page: keys are case
sensitive; at most 50 tags per object; tag keys may not contain `. , - = / :`; and one `ALTER TABLE` can tag only
one column.

!!! warning "Never put personal data in a tag"
    "Tag data is stored as plain text and may be replicated globally. Do not use tag names, values, or descriptors
    that could compromise the security of your resources." Tag a column `pii = email`; never tag a row or table with
    a customer's email or name.

**Governed tags** are "account-level tags with built-in rules for consistency and control": an admin defines the
allowed values and who may assign the tag, and governed tags are marked with a lock in the UI
([Governed tags](https://docs.databricks.com/aws/en/admin/governed-tags/)). Tags applied to a catalog or schema are
inherited by the objects inside it, "except individual table columns". **System tags** are governed tags predefined
by Databricks (for example the classification classes) that users cannot modify. Assigning a governed tag also
needs the `ASSIGN` permission on it. One operational trap from the tags page: dropping a column that carries a
governed tag fails; you must `UNSET TAG` first, and "To permanently delete the column's data, follow the steps in
Drop columns. Otherwise, time travel might expose the data."

**Data Classification** automates the search. It "uses an agent to automatically classify and tag tables in your
catalog", uses an LLM to assist, scans incrementally, and needs serverless compute and `MANAGE` (or ownership) on
the catalog to enable ([Data Classification](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-classification)).
Detections land in the system table `system.data_classification.results` (Public Preview), one row per detected
column with `class_tag` (for example `class.us_ssn`), `confidence` (`HIGH` or `LOW`), `frequency` and up to five
`samples` ([Data classification system table reference](https://docs.databricks.com/aws/en/admin/system-tables/data-classification)).
Because that table holds sample values, grant it carefully.

*Databricks only, not run here. Syntax from [Data classification system table reference](https://docs.databricks.com/aws/en/admin/system-tables/data-classification).*

```sql
SELECT schema_name, table_name, column_name, class_tag, confidence, frequency
FROM system.data_classification.results
WHERE catalog_name = 'shop'
  AND confidence = 'HIGH';
```

**From tags to protection.** Tags matter because ABAC policies use them: a column mask policy attached to
`shop.silver` with `MATCH COLUMNS has_tag_value('pii', 'email')` masks every tagged email column, including in tables
created next month. [Chapter 5, section 5.7](05-Unity-Catalog.md) shows that policy (`mask_pii_email`) and the
`CREATE POLICY` syntax. The chain is: classification (or a person) tags the column, the tag matches the policy,
the policy masks the data. ABAC also has `GRANT` policies and, in Beta, `DENY` policies
([Attribute-based access control in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/)).

!!! tip "In the interview"
    **"How do you know where PII is in your lakehouse?"** Tag it, and do not rely on memory. I turn on Data
    Classification for the catalog so detected columns get system classification tags, review
    `system.data_classification.results`, and add our own governed tag such as `pii` with fixed values. Then an
    ABAC column mask policy on the schema masks every tagged column for everyone outside an exception group, and
    `information_schema.column_tags` gives me the list of PII columns when a deletion request or an audit comes.

## 23.3 Audit: who changed or read what

*Level: beginner.*

**The problem.** At 8 a.m. every order in `silver.orders` says `CANCELLED`. Someone ran an `UPDATE` without a
`WHERE` clause. You need to know what happened, when, by whom, and how to undo it. A different day, security asks
who read customer emails last month. These are different questions with different sources:

| Source | What it records | Scope | Notes |
| --- | --- | --- | --- |
| `DESCRIBE HISTORY t` | every commit to one table: version, timestamp, user, operation, parameters (predicate), metrics (rows), `userMetadata` | one Delta or Iceberg table | kept as long as the log (`delta.logRetentionDuration`, 30 days by default); runs in open-source Delta too |
| `system.access.audit` (Public Preview) | account and workspace events: permission changes, table credential grants, secret reads, logins | whole account; regional for workspace-level events, global for account-level events | free retention 395 days; filter on `event_date` |
| `system.query.history` | SQL statements with user, status, duration, rows read and written | SQL warehouses, serverless notebooks and jobs, Lakeflow pipelines | free retention 365 days; `statement_text` redacted unless admin |

(Retention figures from the [System tables reference](https://docs.databricks.com/aws/en/admin/system-tables/),
Nov 9, 2026; history retention from [Work with table history](https://docs.databricks.com/aws/en/tables/history),
Nov 6, 2026.)

### Table history: answering "what happened to this table?"

`DESCRIBE HISTORY` returns 14 columns, including `userName`, `operation`, `operationParameters`, `job` and
`notebook` (populated "only for commits written from a Lakeflow job" or "from a Databricks notebook"),
`operationMetrics` and `userMetadata`, "the user-defined commit metadata if it was specified"
([Table history schema and operation metrics](https://docs.databricks.com/aws/en/tables/history-schema)). That last
column is a cheap habit worth adopting: label each write with the job run or ticket that caused it. The writer
option `userMetadata` works on classic and serverless compute; the SQL session setting
`spark.databricks.delta.commitInfo.userMetadata` works on classic compute but "The SparkSession configuration keys
for commit metadata are not supported on serverless compute" ([Enrich tables with custom metadata](https://docs.databricks.com/aws/en/tables/operations/custom-metadata)).

Here is the bad morning, replayed: a labeled nightly load, a labeled fix, the unlabeled mistake, then a delete.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
orders.write.format("delta").mode("append") \
    .option("userMetadata", "job=nightly_load run=812").saveAsTable("silver.orders")      # version 1
sql("SET spark.databricks.delta.commitInfo.userMetadata=ticket=OPS-311 fix shipped status")
sql("UPDATE silver.orders SET status = 'SHIPPED' WHERE order_id = 1002")                 # version 2
sql("RESET spark.databricks.delta.commitInfo.userMetadata")
sql("UPDATE silver.orders SET status = 'CANCELLED'")              # version 3: the mistake, no WHERE
sql("DELETE FROM silver.orders WHERE order_id = 1004")            # version 4

hist = sql("DESCRIBE HISTORY silver.orders")
(hist.select("version", "operation",
             F.col("operationParameters")["predicate"].alias("predicate"),
             F.coalesce(F.col("operationMetrics")["numUpdatedRows"],
                        F.col("operationMetrics")["numDeletedRows"],
                        F.col("operationMetrics")["numOutputRows"]).alias("rows"),
             "userMetadata")
     .orderBy("version").show(truncate=False))

# writes that touched every row: UPDATE or DELETE with an empty predicate
(hist.where(F.col("operation").isin("UPDATE", "DELETE"))
     .where(F.col("operationParameters")["predicate"].isNull()
            | (F.col("operationParameters")["predicate"] == "[]"))
     .select("version", "timestamp", "operation", "operationParameters", "readVersion")
     .show(truncate=False))
```

Output (from `ch23_02_audit_clone.out`):

```text
+-------+------------+--------------------------+----+---------------------------------+
|version|operation   |predicate                 |rows|userMetadata                     |
+-------+------------+--------------------------+----+---------------------------------+
|0      |CREATE TABLE|NULL                      |NULL|NULL                             |
|1      |WRITE       |NULL                      |4   |job=nightly_load run=812         |
|2      |UPDATE      |["(order_id#288 = 1002)"] |1   |ticket=OPS-311 fix shipped status|
|3      |UPDATE      |[]                        |4   |NULL                             |
|4      |DELETE      |["(order_id#1514 = 1004)"]|1   |NULL                             |
+-------+------------+--------------------------+----+---------------------------------+

+-------+-----------------------+---------+-------------------+-----------+
|version|timestamp              |operation|operationParameters|readVersion|
+-------+-----------------------+---------+-------------------+-----------+
|3      |2026-11-11 08:29:35.161|UPDATE   |{predicate -> []}  |2          |
+-------+-----------------------+---------+-------------------+-----------+
```

Version 3 has an empty predicate and touched 4 rows: that is the culprit (the `#288` in predicates is Spark's
internal column id). On Databricks `userName`, `job` and `notebook` would also say who ran it and from where. The
history is a DataFrame, so audit questions are ordinary filters; this works the same with `DeltaTable.history()`.

To see the damage, compare the two versions, then roll back:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, v2.status AS before, v3.status AS after
FROM silver.orders VERSION AS OF 2 v2 JOIN silver.orders VERSION AS OF 3 v3 USING (order_id)
WHERE v2.status <> v3.status ORDER BY order_id;

RESTORE TABLE silver.orders TO VERSION AS OF 2;
```

```text
+--------+-------+---------+
|order_id|before |after    |
+--------+-------+---------+
|1001    |PLACED |CANCELLED|
|1002    |SHIPPED|CANCELLED|
|1003    |SHIPPED|CANCELLED|
|1004    |PLACED |CANCELLED|
+--------+-------+---------+

+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
|table_size_after_restore|num_of_files_after_restore|num_removed_files|num_restored_files|removed_files_size|restored_files_size|
+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
|3471                    |2                         |2                |2                 |3602              |3471               |
+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
```

The history then ends with `5 | RESTORE | {version -> 2, timestamp -> NULL}`: a restore is itself a new, audited
commit. Note that it also brings back order 1004, which version 4 had deleted on purpose; restoring to a version
undoes everything after it, so check what else happened in between.

### The audit log system table: reads, grants and secrets

Table history only sees writes to one table. Reads, permission changes and secret access are in
`system.access.audit`. Its columns include `event_time`, `event_date` ("filter on `event_date` rather than
`event_time`"), `user_identity` (with `email`), `service_name` (for example `unityCatalog`), `action_name`,
`request_params` (a map), `response`, `audit_level` and `identity_metadata` with `run_by` and `run_as`
([Audit log system table reference](https://docs.databricks.com/aws/en/admin/system-tables/audit-logs)). The event
names and their request parameters are in the [Audit log reference](https://docs.databricks.com/aws/en/admin/account-settings/audit-logs):
for Unity Catalog, `updatePermissions` (with `securable_type`, `securable_full_name`, `changes`) and
`generateTemporaryTableCredential`, which is "Logged whenever a temporary credential is granted for a table. You
can use this event to determine who queried what and when" (with `table_full_name` and `operation`); secret reads
are `getSecret` under the `secrets` service.

*Databricks only, not run here. Columns and event names from [Audit log system table reference](https://docs.databricks.com/aws/en/admin/system-tables/audit-logs) and [Audit log reference](https://docs.databricks.com/aws/en/admin/account-settings/audit-logs).*

```sql
-- who changed permissions on anything in the shop catalog this week
SELECT event_time, user_identity.email,
       request_params['securable_type']      AS securable_type,
       request_params['securable_full_name'] AS object,
       request_params['changes']             AS changes
FROM system.access.audit
WHERE service_name = 'unityCatalog'
  AND action_name = 'updatePermissions'
  AND (request_params['securable_full_name'] = 'shop'
       OR request_params['securable_full_name'] LIKE 'shop.%')
  AND event_date >= current_date() - INTERVAL 7 DAYS
ORDER BY event_time DESC;

-- who was given credentials to read the customers table in the last 30 days
SELECT event_date, user_identity.email, request_params['operation'] AS operation, count(*) AS events
FROM system.access.audit
WHERE action_name = 'generateTemporaryTableCredential'
  AND request_params['table_full_name'] = 'shop.silver.customers'
  AND event_date >= current_date() - INTERVAL 30 DAYS
GROUP BY ALL
ORDER BY event_date DESC;
```

Things the page warns about: "Account-level audit logs record `workspace_id` as `0`"; some `request_params` keys
holding SQL definitions are omitted unless you are an account admin or in the `databricks_pii_access` group; and
querying the table from dedicated access mode needs Databricks Runtime 15.4 LTS or above with serverless enabled.
Like every system table, access is granted with `USE CATALOG`, `USE SCHEMA` and `SELECT` on the system schemas, and
"System tables are read-only and cannot be modified" ([System tables reference](https://docs.databricks.com/aws/en/admin/system-tables/)).

### Query history: the statement itself

`system.query.history` has one row per statement with `executed_by`, `statement_type`, `execution_status`
(`FINISHED`, `FAILED`, `CANCELED`), `statement_text`, `start_time`, `total_duration_ms`, `read_rows`,
`written_rows` and more ([Query history system table reference](https://docs.databricks.com/aws/en/admin/system-tables/query-history)).
Two limits change how you use it: it covers "SQL warehouses, serverless compute for notebooks and jobs, and
Lakeflow pipelines", so a statement on a classic all-purpose cluster is not there (use table history and the
audit log for those); and `statement_text` "returns `<REDACTED>` unless you are an account admin or a member of the
`databricks_pii_access` account-level group". Records "are typically available within one hour".

*Databricks only, not run here. Columns from [Query history system table reference](https://docs.databricks.com/aws/en/admin/system-tables/query-history).*

```sql
SELECT start_time, executed_by, statement_type, execution_status, written_rows, statement_text
FROM system.query.history
WHERE statement_type <> 'SELECT'
  AND statement_text LIKE '%shop.silver.orders%'
  AND start_time >= current_timestamp() - INTERVAL 1 DAY
ORDER BY start_time;
```

!!! tip "In the interview"
    **"How do you find who changed a table?"** Start with `DESCRIBE HISTORY` on the table: each commit has the
    version, time, user, operation, predicate, row metrics and, on Databricks, the job or notebook that wrote it. A
    commit with an empty predicate and a large `numUpdatedRows` is the usual suspect; compare it with the previous
    version using `VERSION AS OF` and `RESTORE` if needed. For reads and grants, which history does not record, I
    query `system.access.audit` (`generateTemporaryTableCredential`, `updatePermissions`), and
    `system.query.history` for the SQL text on warehouses and serverless. Going forward I make writers set
    `userMetadata` and run production jobs as service principals, so history points at a job, not a person.

## 23.4 The right to be forgotten on Delta

*Level: intermediate.*

**The problem.** GDPR and CCPA "require companies to permanently and completely delete all personally
identifiable information (PII) collected about a customer upon their explicit request", usually within a fixed
period such as one month ([Prepare your data for GDPR compliance](https://docs.databricks.com/aws/en/security/privacy/gdpr-delta)).
Delta Lake makes this harder than it looks, because its best features keep old data on purpose: time travel keeps
old versions, deletion vectors hide rows without rewriting files, and the change data feed records the deleted row
itself.

The Databricks blueprint, mostly in its own words:

- "We recommend that you start GDPR and CCPA compliance by deleting data in the bronze layer first, driven by a
  scheduled job that queries a table of deletion requests. After data is deleted from the bronze layer, changes can
  be propagated to silver and gold layers."
- "When deleting a large number of records together at one time, we recommend using the `MERGE` command."
- "For tables with deletion vectors enabled, after deleting records, you must also run
  `REORG TABLE ... APPLY (PURGE)` to permanently delete underlying records. This includes Delta Lake tables,
  materialized views, and streaming tables."
- Then regular maintenance removes the old files once they pass the retention threshold. "The recommended way is"
  predictive optimization; without it (and outside Lakeflow pipelines, which maintain their own tables), run
  `VACUUM`.
- "GDPR and CCPA apply to all data, including data in sources outside of Delta Lake, such as Kafka, files, and
  databases."
- "Complete deletion is preferable to obfuscation": pseudonymization and masking leave a re-identification risk.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="A deletion request flows from a control table through bronze, silver and gold; below, the four stages of the files in one table: delete, purge, retention, vacuum">
<defs><marker id="a231" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g font-size="13" fill="currentColor" stroke="none">
<rect x="10" y="12" width="140" height="74" rx="6" fill="none" stroke="currentColor"/>
<text x="80" y="34" text-anchor="middle" font-weight="bold">ops.gdpr_requests</text>
<text x="80" y="54" text-anchor="middle">control table:</text>
<text x="80" y="72" text-anchor="middle">customer_id 7</text>
<rect x="170" y="12" width="140" height="74" rx="6" fill="none" stroke="currentColor"/>
<text x="240" y="34" text-anchor="middle" font-weight="bold">bronze</text>
<text x="240" y="54" text-anchor="middle">MERGE ... WHEN</text>
<text x="240" y="72" text-anchor="middle">MATCHED THEN DELETE</text>
<rect x="330" y="12" width="140" height="74" rx="6" fill="none" stroke="currentColor"/>
<text x="400" y="34" text-anchor="middle" font-weight="bold">silver</text>
<text x="400" y="54" text-anchor="middle">same delete by key,</text>
<text x="400" y="72" text-anchor="middle">customers, orders</text>
<rect x="490" y="12" width="140" height="74" rx="6" fill="none" stroke="currentColor"/>
<text x="560" y="34" text-anchor="middle" font-weight="bold">gold</text>
<text x="560" y="54" text-anchor="middle">recompute, or</text>
<text x="560" y="72" text-anchor="middle">refresh the MV</text>
<rect x="10" y="100" width="620" height="28" rx="6" fill="none" stroke="currentColor" stroke-dasharray="5 4"/>
<text x="320" y="119" text-anchor="middle">Also in scope: landing files, Kafka topics, clones, backups, archived change feeds</text>
<text x="10" y="160" font-weight="bold">What happens to the files of one table</text>
<rect x="8" y="172" width="145" height="100" rx="6" fill="none" stroke="currentColor"/>
<text x="80" y="194" text-anchor="middle" font-weight="bold">1. DELETE / MERGE</text>
<text x="80" y="214" text-anchor="middle">current version</text>
<text x="80" y="232" text-anchor="middle">hides the row; old</text>
<text x="80" y="250" text-anchor="middle">files and CDF files</text>
<text x="80" y="268" text-anchor="middle">still hold it</text>
<rect x="168" y="172" width="145" height="100" rx="6" fill="none" stroke="currentColor"/>
<text x="240" y="194" text-anchor="middle" font-weight="bold">2. REORG PURGE</text>
<text x="240" y="214" text-anchor="middle">rewrites files that</text>
<text x="240" y="232" text-anchor="middle">carry deletion</text>
<text x="240" y="250" text-anchor="middle">vectors</text>
<rect x="328" y="172" width="145" height="100" rx="6" fill="none" stroke="currentColor"/>
<text x="400" y="194" text-anchor="middle" font-weight="bold">3. Retention</text>
<text x="400" y="214" text-anchor="middle">default 7 days;</text>
<text x="400" y="232" text-anchor="middle">time travel to old</text>
<text x="400" y="250" text-anchor="middle">versions still work</text>
<rect x="488" y="172" width="145" height="100" rx="6" fill="none" stroke="currentColor"/>
<text x="560" y="194" text-anchor="middle" font-weight="bold">4. VACUUM</text>
<text x="560" y="214" text-anchor="middle">deletes old data</text>
<text x="560" y="232" text-anchor="middle">and CDF files; old</text>
<text x="560" y="250" text-anchor="middle">versions now fail</text>
</g>
<g stroke="currentColor" fill="none" stroke-width="1.5">
<line x1="150" y1="49" x2="168" y2="49" marker-end="url(#a231)"/>
<line x1="310" y1="49" x2="328" y2="49" marker-end="url(#a231)"/>
<line x1="470" y1="49" x2="488" y2="49" marker-end="url(#a231)"/>
<line x1="153" y1="222" x2="166" y2="222" marker-end="url(#a231)"/>
<line x1="313" y1="222" x2="326" y2="222" marker-end="url(#a231)"/>
<line x1="473" y1="222" x2="486" y2="222" marker-end="url(#a231)"/>
</g>
</svg>
<figcaption>Figure 23.1. A right-to-be-forgotten request: delete by key in every layer, starting at bronze (top), and the four stages the files of each table go through before the data is physically gone (bottom).</figcaption>
</figure>

### The whole lifecycle, run here

Red Rock's `silver.customers` has the change data feed and deletion vectors enabled and its three rows in one data
file (so the delete has to touch a file that also holds other customers). Customer 7, Maya Chen, asks to be
forgotten. The request goes into a control table, and a `MERGE` deletes her from customers and orders:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.customers (customer_id INT, name STRING, email STRING, city STRING,
  country STRING, updated_at TIMESTAMP) USING DELTA
  TBLPROPERTIES (delta.enableChangeDataFeed = true, delta.enableDeletionVectors = true);
-- ... insert customers 7, 8, 9 (version 1) and four orders ...

CREATE TABLE ops.gdpr_requests (customer_id INT, requested_at TIMESTAMP, processed_at TIMESTAMP) USING DELTA;
INSERT INTO ops.gdpr_requests VALUES (7, TIMESTAMP'2026-03-05 08:00:00', NULL);

MERGE INTO silver.customers AS t
USING (SELECT customer_id FROM ops.gdpr_requests WHERE processed_at IS NULL) AS r
ON t.customer_id = r.customer_id
WHEN MATCHED THEN DELETE;                                   -- version 2
-- the same MERGE on silver.orders deletes her 2 orders
```

```text
+-----------------+----------------+----------------+-----------------+
|num_affected_rows|num_updated_rows|num_deleted_rows|num_inserted_rows|
+-----------------+----------------+----------------+-----------------+
|1                |0               |1               |0                |
+-----------------+----------------+----------------+-----------------+
```

The PySpark version (run on `bronze.customers` in the same script) uses the `DeltaTable` API:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from delta.tables import DeltaTable

requests = spark.table("ops.gdpr_requests").select("customer_id")
(DeltaTable.forName(spark, "bronze.customers").alias("t")
    .merge(requests.alias("r"), "t.customer_id = r.customer_id")
    .whenMatchedDelete()
    .execute())
```

A query on the current table no longer returns her. Now look underneath, step by step.

**Step 1: the history and the deletion vector.** The `MERGE` did not rewrite the data file. It added a deletion
vector that marks her row as deleted:

```text
+-------+------------+--------------------+-----------------------------+---------------------+
|version|operation   |numTargetRowsDeleted|numTargetDeletionVectorsAdded|numTargetFilesRemoved|
+-------+------------+--------------------+-----------------------------+---------------------+
|0      |CREATE TABLE|NULL                |NULL                         |NULL                 |
|1      |WRITE       |NULL                |NULL                         |NULL                 |
|2      |MERGE       |1                   |1                            |0                    |
+-------+------------+--------------------+-----------------------------+---------------------+
```

**Step 2: time travel and the change data feed still show her.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT customer_id, name, email FROM silver.customers VERSION AS OF 1 WHERE customer_id = 7;
SELECT customer_id, email, _change_type, _commit_version FROM table_changes('silver.customers', 2);
```

```text
+-----------+---------+---------------------+
|customer_id|name     |email                |
+-----------+---------+---------------------+
|7          |Maya Chen|maya.chen@example.com|
+-----------+---------+---------------------+

+-----------+---------------------+------------+---------------+
|customer_id|email                |_change_type|_commit_version|
+-----------+---------------------+------------+---------------+
|7          |maya.chen@example.com|delete      |2              |
+-----------+---------------------+------------+---------------+
```

The change feed is double-edged. It is how downstream tables learn about the delete (a consumer reading
`_change_type = 'delete'` can apply it to silver and gold), but the delete record carries the whole row, email
included, in a file under `_change_data`. That is the write-time form, which `delta.enableChangeDataFeed` turns on
and this run uses; Databricks now calls it legacy change data feed and also offers an automatic change data feed
that computes changes at read time ([Chapter 4](04-Delta-Lake.md),
[Use change data feed on Databricks](https://docs.databricks.com/aws/en/tables/features/change-data-feed)).

**Step 3: what is physically on disk.** The script reads every Parquet file in the table folder directly,
ignoring the Delta log, as someone with storage access could, and counts rows that still hold her email. It also
searches the JSON commit files in `_delta_log` for the email text:

```text
parquet files on disk: 2 (of which in _change_data: 1); rows holding the email: 2
_delta_log JSON files that contain the email text: ['00000000000000000001.json', '00000000000000000002.json']
  add.stats.minValues.email = ava.novak@example.com | maxValues.email = maya.chen@example.com
```

Two copies of her row: the original data file (only masked by the deletion vector) and the change data file. And
the log itself mentions her email, as the `maxValues` statistic of the email column that each `add` action stores
for data skipping. The Delta protocol notes that with deletion vectors these statistics "may be somewhat outdated,
i.e. not reflecting deleted rows yet" ([Delta transaction log protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md)).

**Step 4: purge the soft delete.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
REORG TABLE silver.customers APPLY (PURGE);
```

```text
+-------+------------+-----------------------------------------+---------------+-------------+-------------------------+
|version|operation   |predicate                                |numRemovedFiles|numAddedFiles|numDeletionVectorsRemoved|
+-------+------------+-----------------------------------------+---------------+-------------+-------------------------+
|0      |CREATE TABLE|NULL                                     |NULL           |NULL         |NULL                     |
|1      |WRITE       |NULL                                     |NULL           |NULL         |NULL                     |
|2      |MERGE       |["(customer_id#2627 = customer_id#2633)"]|NULL           |NULL         |NULL                     |
|3      |REORG       |[]                                       |1              |1            |1                        |
+-------+------------+-----------------------------------------+---------------+-------------+-------------------------+

parquet files on disk: 3 (of which in _change_data: 1); rows holding the email: 2
```

The purge rewrote the file without her row, so the current version is
clean. But the old file is still on disk, unreferenced, and so is the change data file: still 2 copies.

**Step 5: VACUUM, and why it waits.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
VACUUM silver.customers DRY RUN;      -- default retention: nothing is old enough yet
VACUUM silver.customers RETAIN 0 HOURS;
```

```text
>>> VACUUM silver.customers DRY RUN  (count of files it would delete)
0
>>> VACUUM silver.customers RETAIN 0 HOURS
ERROR: [DELTA_VACUUM_RETENTION_PERIOD_TOO_SHORT] The specified VACUUM retention period is too low and may corrupt this Delta table if any writes are in progress.
```

`VACUUM` deletes only files that are unreferenced by the current version and older than the retention threshold,
`delta.deletedFileRetentionDuration`, "which defaults to 7 days" ([VACUUM](https://docs.databricks.com/aws/en/sql/language-manual/delta-vacuum)).
The files are minutes old, so nothing qualifies, and a zero-hour retention is refused by a safety check. For the
demo only, the script turns the check off (`spark.databricks.delta.retentionDurationCheck.enabled = false`) and runs
it again:

```text
>>> VACUUM silver.customers RETAIN 0 HOURS
Deleted 3 files and directories in a total of 2 directories.
parquet files on disk: 1 (of which in _change_data: 0); rows holding the email: 0
```

**Step 6: the old versions are gone.**

```text
>>> SELECT customer_id, name, email FROM silver.customers VERSION AS OF 1 WHERE customer_id = 7
ERROR: [FAILED_READ_FILE.FILE_NOT_EXIST] Encountered error while reading file file:<work>/warehouse/silver.db/customers/part-00000-4aa0bbab-30c1-4306-93d1-e241bcfcb016-c000.snappy.parquet. File does not exis
>>> SELECT customer_id, email, _change_type FROM table_changes('silver.customers', 2)
ERROR: [FAILED_READ_FILE.FILE_NOT_EXIST] Encountered error while reading file file:<work>/warehouse/silver.db/customers/_change_data/cdc-00000-4ee0d1d3-fcf9-4daa-8a2b-38128fe8f0f3.c000.snappy.parquet. File d
_delta_log JSON files that contain the email text: ['00000000000000000001.json', '00000000000000000002.json']
```

No data file holds her row any more; time travel and the change feed for those versions fail. The last line is
the subtle one: `VACUUM` skips directories that begin with an underscore, "which includes the `_delta_log`"
([VACUUM](https://docs.databricks.com/aws/en/sql/language-manual/delta-vacuum)), and log files "are deleted
automatically and asynchronously after checkpoint operations and are not governed by `VACUUM`", with a default
retention of 30 days ([Remove unused data files with vacuum](https://docs.databricks.com/aws/en/tables/operations/vacuum)).
In this open-source run the old commit files still carry her email as a column statistic until log cleanup removes
them. Whether Databricks Runtime writes string statistics the same way is not verified here, but the safe plan is
the same: count the erasure as complete only after the log retention (`delta.logRetentionDuration`, 30 days by
default) has also passed. The GDPR page puts it the same way: "By default, Delta Lake retains table history,
including deleted records, for 30 days".

Finally the script rebuilds gold from the cleaned silver (her CAD revenue rows disappear) and sets `processed_at`
on the request, which is the record that the erasure was done.

!!! warning "Never shorten retention in production to speed up an erasure"
    The zero-hour `VACUUM` above is a demo. The vacuum page says "Databricks strongly recommends setting a retention
    interval of at least 7 days", because a running job may still be writing files that a short retention would
    delete. Plan the erasure around the normal retention instead: the old data and change files can go 7 days after
    the purge, and the log keeps old commits for 30 days by default, so start each request early in its deadline
    window.

### Databricks specifics

- **Predictive optimization** "automatically runs `OPTIMIZE`, `VACUUM`, and `ANALYZE` on Unity Catalog managed
  tables", and if `delta.deletedFileRetentionDuration` is below 7 days it "still retains data files for a minimum of
  7 days" ([Predictive optimization for Unity Catalog managed tables](https://docs.databricks.com/aws/en/optimizations/predictive-optimization)).
  You still need the `REORG ... APPLY (PURGE)` step for tables with deletion vectors.
- **Time travel is capped** by the file retention: "In Databricks Runtime 18.0 and above, time travel queries are
  blocked if they request a version older than the `deletedFileRetentionDuration` table property (default 7
  days). For Unity Catalog managed tables, this applies to Databricks Runtime 12.2 LTS and above"
  ([Work with table history](https://docs.databricks.com/aws/en/tables/history)).
- **Dropped columns are soft deletes too**: with column mapping, dropping a column (for example removing an email
  column you no longer need) does not rewrite files; `REORG TABLE ... APPLY (PURGE)` and `VACUUM` remove the data
  (vacuum page, "Purge metadata-only deletes to force data rewrite").
- **Materialized views** "automatically handle deletions in sources", but "You must refresh a materialized view and
  run maintenance to ensure that deletions are completely processed."
- **Streaming tables and streams** that read a table you deleted from break, because a Delta streaming source
  expects appends. The GDPR page's recommended method: delete in the source, delete in the streaming table, and set
  `skipChangeCommits` on the streaming read; or stream from the change feed and apply deletes explicitly; or fully
  refresh the streaming table if the upstream data is still available ([Chapter 11](11-Structured-Streaming.md)).
- **Shallow clones under Unity Catalog keep files alive.** "Running `VACUUM` on the source of a shallow clone
  doesn't break the cloned table", because Unity Catalog counts files that clones reference as still valid
  ([Shallow clone for Unity Catalog tables](https://docs.databricks.com/aws/en/tables/operations/clone-unity-catalog)).
  A dev shallow clone of `shop.silver.customers` therefore keeps the deleted customer's old files from being
  vacuumed. Drop or re-create such clones as part of the erasure, and allow for the page's note that Databricks
  keeps the link from a dropped shallow clone to the base table's files "for 7 days after dropping a shallow cloned
  table to support the `UNDROP` operation". (Shallow clone for Unity Catalog tables is in Public Preview; this is
  documented behavior, not run here.)

**Design for erasure.** The GDPR page suggests severing the link between PII and the rest: "if you are using a
non-natural key such as `user_id` instead of a natural key like email, you can delete PII data, which leaves non-PII
data in place". For Red Rock, orders reference `customer_id`, and email and name live only in the customers table,
so erasing the customer row removes the personal data while order counts and revenue by country stay correct
(whether to keep her anonymous orders is a legal decision, not a technical one). Delete by key, not by email
literal, so the email itself does not end up in query text.

!!! tip "In the interview"
    **"How do you handle a GDPR delete in a lakehouse?"** Requests go into a control table; a scheduled job reads
    it and runs a `MERGE ... WHEN MATCHED THEN DELETE` by customer key in bronze first, then silver and gold
    (gold aggregates are recomputed or refreshed; materialized views handle deletes on refresh). A delete alone is
    not erasure: old versions keep the rows for time travel, deletion vectors only mark rows, and the change data
    feed (in its legacy, write-time form) stores the deleted row. So on tables with deletion vectors I run
    `REORG TABLE ... APPLY (PURGE)`, and
    `VACUUM` (or predictive optimization) removes the old data and change files after the retention period, 7 days
    by default; the transaction log ages out after 30 days by default. Streams on those tables need
    `skipChangeCommits` or a change-feed design. I also cover what Delta does not: landing files, Kafka topics,
    clones, backups and exports, and I record when each request was processed. I use lineage
    ([Chapter 5](05-Unity-Catalog.md)) and the `pii` tags to find every table in scope.

## 23.5 Secrets, service principals and least privilege

*Level: intermediate.*

**Secrets.** "A Databricks secret stores a sensitive value, such as a password, API key, or hashing salt, so that
notebooks, jobs, and functions can use it without the value appearing in code." There are two places to keep them
([Secret management](https://docs.databricks.com/aws/en/security/secrets/)):

| | Workspace secret scope | Secret in Unity Catalog |
| --- | --- | --- |
| Name | `scope` + `key` | `catalog.schema.secret` |
| Available in | one workspace | every workspace attached to the metastore |
| Access control | per scope ("a user who can read one secret in a scope can read all of them") | per secret, with privileges such as `READ SECRET`, `WRITE SECRET`, `CREATE SECRET`, `REFERENCE SECRET` |
| `dbutils.secrets` | yes | yes, on serverless environment version 4+ or Databricks Runtime 17.3 LTS+ |
| SQL warehouses | yes, with the `secret()` function | only through a Unity Catalog Python or Scala UDF that declares the secret |

*Databricks only, not run here. Syntax from [Workspace secret scopes](https://docs.databricks.com/aws/en/security/secrets/workspace-secret-scopes) and [Secrets in Unity Catalog](https://docs.databricks.com/aws/en/security/secrets/unity-catalog-secrets).*

```bash
databricks secrets create-scope red-rock-etl
databricks secrets put-secret red-rock-etl pg-password          # prompts for the value
databricks secrets put-acl red-rock-etl etl-service-principals READ
```

*Databricks only, not run here. Syntax from [Workspace secret scopes](https://docs.databricks.com/aws/en/security/secrets/workspace-secret-scopes) and [Secrets in Unity Catalog](https://docs.databricks.com/aws/en/security/secrets/unity-catalog-secrets).*

```python
# workspace secret scope
password = dbutils.secrets.get(scope="red-rock-etl", key="pg-password")
# Unity Catalog secret
password = dbutils.secrets.get(catalog="shop", schema="etl_secrets", key="pg_password")
```

*Databricks only, not run here. Syntax from [Secrets in Unity Catalog](https://docs.databricks.com/aws/en/security/secrets/unity-catalog-secrets).*

```sql
-- Unity Catalog secret: let the job's service principal read every secret in the schema
GRANT USE CATALOG ON CATALOG shop TO `etl-service-principal`;
GRANT USE SCHEMA, READ SECRET ON SCHEMA shop.etl_secrets TO `etl-service-principal`;
```

In SQL, `secret(scope, key)` returns the value ("Applies to: Databricks SQL preview Databricks Runtime 11.3 LTS and
above", [secret function](https://docs.databricks.com/aws/en/sql/language-manual/functions/secret)); a Lakehouse
Federation connection takes `password secret('<secret-scope>','<secret-key-password>')` instead of a plain string
(section 23.9).

**Redaction is not protection.** When a value read with `dbutils.secrets.get()` is displayed, Databricks replaces
it with `[REDACTED]`. But the page is blunt: "Redaction applies only to literal secret values. The secret redaction
functionality does not prevent deliberate and arbitrary transformations of a secret literal", and "Although
Databricks attempts to redact secret values in notebook outputs, it is not possible to fully prevent these users
from viewing secret contents." Anyone who can read the secret can see it. So: grant secret access to the service
principal that runs the job, not to every developer; never print, log or write a secret to a table (Databricks
SQL also tries to block DML that would save an unencrypted secret); and remember that the REST API and CLI return
values unredacted. Every read is audited (`getSecret` in `system.access.audit`).

**Service principals.** "A service principal is a specialized identity in Databricks designed for automation and
programmatic access", with API-only access ([Service principals](https://docs.databricks.com/aws/en/admin/users-groups/service-principals)).
Running jobs as one "prevents jobs from failing if a user leaves your organization or a group is modified". Two
roles matter: the service principal **manager** manages it, and the service principal **user** role lets someone run
jobs as it; managers do not inherit the user role. The Unity Catalog best practices make it a rule: "Use service
principals to run jobs. ... If you use users to run jobs that write into production, you risk overwriting
production data by accident", and "Reserve direct `MODIFY` access to production tables for service principals"
([Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices)).

**Least privilege**, applied: each job's service principal gets exactly the privileges its layer needs (the bronze
loader writes bronze and reads the landing volume; the silver job reads bronze and writes silver), humans get
`SELECT` and `BROWSE` in production, ownership of production catalogs and schemas goes to groups, and nobody holds
`ALL PRIVILEGES` on `shop` "just in case". The `GRANT` statements themselves are in
[Chapter 5, section 5.6](05-Unity-Catalog.md).

## 23.6 Separating dev, staging and prod

*Level: intermediate.*

**The problem.** A developer tests a new silver `MERGE` and points it at the production table by mistake. In a
lakehouse where everything is one `SELECT` away, separation has to be built into names, bindings and identities.

**Catalogs per environment, one metastore.** Unity Catalog allows one metastore per region, and the best practices
say "Use your single-region metastore for all software development lifecycle scopes and business units, for
example, dev, test, prod". Catalogs then carry the separation: "Often, this means that catalogs correspond to an
environment scope, team, business unit, or some combination of these." Red Rock uses `shop_dev`, `shop_staging`
and `shop_prod`, each with the same `bronze`, `silver`, `gold` schemas, so code only changes the catalog name, set
per target by the bundle (Declarative Automation Bundles, formerly Databricks Asset Bundles, per the
[bundles page](https://docs.databricks.com/aws/en/dev-tools/bundles/); Chapter 16).

**Binding.** "When work environments and data both have the same isolation requirements, you can bind a catalog to
a specific workspace." With `shop_prod` bound to the production workspace, "Access from an unbound workspace is
denied, even for users with explicit privilege grants on the catalog"
([Workspace-catalog binding](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/workspace-catalog-binding);
the CLI commands are in [Chapter 5, section 5.9](05-Unity-Catalog.md)). A binding can also be read-only, which is
useful for letting the dev workspace read production gold for comparisons.

**Identities.** Production is written only by service principals deployed through CI/CD; humans read it. Developers
own `shop_dev`. Staging is written by the CI service principal running the same bundle as production.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="One Unity Catalog metastore holds three workspaces, dev, staging and prod, each with its own catalog; a Git repository and CI/CD deploy the same bundle to all three">
<defs><marker id="a232" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g font-size="13" fill="currentColor" stroke="none">
<rect x="10" y="10" width="620" height="200" rx="8" fill="none" stroke="currentColor"/>
<text x="20" y="30" font-weight="bold">One Unity Catalog metastore per region</text>
<rect x="25" y="42" width="180" height="155" rx="6" fill="none" stroke="currentColor"/>
<text x="115" y="62" text-anchor="middle" font-weight="bold">dev workspace</text>
<rect x="35" y="72" width="160" height="44" rx="4" fill="none" stroke="currentColor" stroke-dasharray="4 3"/>
<text x="115" y="90" text-anchor="middle">catalog shop_dev</text>
<text x="115" y="108" text-anchor="middle">bronze silver gold</text>
<text x="115" y="140" text-anchor="middle">engineers read</text>
<text x="115" y="158" text-anchor="middle">and write</text>
<text x="115" y="184" text-anchor="middle">sample or masked data</text>
<rect x="230" y="42" width="180" height="155" rx="6" fill="none" stroke="currentColor"/>
<text x="320" y="62" text-anchor="middle" font-weight="bold">staging workspace</text>
<rect x="240" y="72" width="160" height="44" rx="4" fill="none" stroke="currentColor" stroke-dasharray="4 3"/>
<text x="320" y="90" text-anchor="middle">catalog shop_staging</text>
<text x="320" y="108" text-anchor="middle">bronze silver gold</text>
<text x="320" y="140" text-anchor="middle">CI service principal</text>
<text x="320" y="158" text-anchor="middle">writes; tests run</text>
<text x="320" y="184" text-anchor="middle">engineers read</text>
<rect x="435" y="42" width="180" height="155" rx="6" fill="none" stroke="currentColor"/>
<text x="525" y="62" text-anchor="middle" font-weight="bold">prod workspace</text>
<rect x="445" y="72" width="160" height="44" rx="4" fill="none" stroke="currentColor" stroke-dasharray="4 3"/>
<text x="525" y="90" text-anchor="middle">catalog shop_prod</text>
<text x="525" y="108" text-anchor="middle">bronze silver gold</text>
<text x="525" y="140" text-anchor="middle">prod service principal</text>
<text x="525" y="158" text-anchor="middle">only writer; humans read</text>
<text x="525" y="184" text-anchor="middle">bound to this workspace</text>
<rect x="10" y="244" width="150" height="44" rx="6" fill="none" stroke="currentColor"/>
<text x="85" y="263" text-anchor="middle" font-weight="bold">Git</text>
<text x="85" y="280" text-anchor="middle">one codebase</text>
<rect x="200" y="244" width="430" height="44" rx="6" fill="none" stroke="currentColor"/>
<text x="415" y="263" text-anchor="middle" font-weight="bold">CI/CD deploys one bundle</text>
<text x="415" y="280" text-anchor="middle">same code to dev, staging and prod targets</text>
</g>
<g stroke="currentColor" fill="none" stroke-width="1.5">
<line x1="160" y1="266" x2="198" y2="266" marker-end="url(#a232)"/>
<line x1="230" y1="244" x2="115" y2="213" marker-end="url(#a232)"/>
<line x1="320" y1="244" x2="320" y2="213" marker-end="url(#a232)"/>
<line x1="525" y1="244" x2="525" y2="213" marker-end="url(#a232)"/>
</g>
</svg>
<figcaption>Figure 23.2. Environment separation: one metastore, one catalog per environment, production bound to its own workspace and written only by a service principal, and the same code deployed to every target from Git.</figcaption>
</figure>

**Production data in dev?** Usually a small sample or a masked copy. A shallow clone is the tempting shortcut
("To test a workflow on a production table without corrupting the table, create a shallow clone",
[Clone a table on Databricks](https://docs.databricks.com/aws/en/tables/operations/clone)), and changes to the clone
do not touch the source. But a clone of `customers` carries the personal data into dev, where more people can read
it, and under Unity Catalog it also keeps erased rows' files alive (section 23.4). Clone gold or orders, not
customers, or mask before copying.

!!! tip "In the interview"
    **"How do you keep prod safe?"** Four layers. Separate catalogs per environment (`shop_dev`, `shop_staging`,
    `shop_prod`) in one metastore, with the prod catalog bound to the prod workspace. Production is written only by
    service principals through CI/CD (Declarative Automation Bundles, formerly Databricks Asset Bundles), and humans
    get read access, so nobody can run a manual `UPDATE` there. Groups own production objects, not individuals.
    And recovery is ready: table history and `RESTORE` for bad writes, alerts on failed jobs, and a tested backup
    and DR plan.

## 23.7 Monitoring, alerting and observability

*Level: intermediate.*

**The problem.** A job that fails loudly is the easy case. The hard cases are the job that succeeds with half the
rows, the table nobody updated since Tuesday, and the stream slowly falling behind. Monitoring needs signals, checks
on them, notifications, and someone who responds.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 260" role="img" aria-label="A loop of five boxes: jobs and pipelines produce signals, checks evaluate them, notifications go out, people respond, and the fixes go back into the jobs">
<defs><marker id="a233" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g font-size="13" fill="currentColor" stroke="none">
<rect x="10" y="20" width="180" height="80" rx="6" fill="none" stroke="currentColor"/>
<text x="100" y="44" text-anchor="middle" font-weight="bold">1. Jobs and pipelines</text>
<text x="100" y="66" text-anchor="middle">write bronze to gold</text>
<text x="100" y="86" text-anchor="middle">on a schedule</text>
<rect x="230" y="20" width="180" height="80" rx="6" fill="none" stroke="currentColor"/>
<text x="320" y="44" text-anchor="middle" font-weight="bold">2. Signals</text>
<text x="320" y="66" text-anchor="middle">system tables, history,</text>
<text x="320" y="86" text-anchor="middle">event log, DQ results</text>
<rect x="450" y="20" width="180" height="80" rx="6" fill="none" stroke="currentColor"/>
<text x="540" y="44" text-anchor="middle" font-weight="bold">3. Checks</text>
<text x="540" y="66" text-anchor="middle">SQL alerts, anomaly</text>
<text x="540" y="86" text-anchor="middle">detection, expectations</text>
<rect x="450" y="160" width="180" height="80" rx="6" fill="none" stroke="currentColor"/>
<text x="540" y="184" text-anchor="middle" font-weight="bold">4. Notify</text>
<text x="540" y="206" text-anchor="middle">email, Slack, Teams,</text>
<text x="540" y="226" text-anchor="middle">PagerDuty, webhook</text>
<rect x="230" y="160" width="180" height="80" rx="6" fill="none" stroke="currentColor"/>
<text x="320" y="184" text-anchor="middle" font-weight="bold">5. Respond</text>
<text x="320" y="206" text-anchor="middle">repair run, RESTORE,</text>
<text x="320" y="226" text-anchor="middle">backfill, fix the code</text>
</g>
<g stroke="currentColor" fill="none" stroke-width="1.5">
<line x1="190" y1="60" x2="228" y2="60" marker-end="url(#a233)"/>
<line x1="410" y1="60" x2="448" y2="60" marker-end="url(#a233)"/>
<line x1="540" y1="100" x2="540" y2="158" marker-end="url(#a233)"/>
<line x1="450" y1="200" x2="412" y2="200" marker-end="url(#a233)"/>
<polyline points="230,200 100,200 100,102" marker-end="url(#a233)"/>
</g>
</svg>
<figcaption>Figure 23.3. The monitoring loop: every job leaves signals, checks turn signals into a state, a state change notifies someone, and the response feeds back into the jobs.</figcaption>
</figure>

**Job notifications (immediate).** A job or a task can notify on start, success, failure, duration over a threshold,
and streaming backlog over a threshold, to email or to system destinations (Slack, Microsoft Teams, PagerDuty,
webhooks) that an admin configures, at most three system destinations per event type
([Add notifications on a job](https://docs.databricks.com/aws/en/jobs/notifications)). Two details catch people:
"Job-level notifications aren't sent when failed tasks are retried", so use task notifications to hear about every
failed attempt; and a run that ends "Succeeded with failures" counts as success. These are Lakeflow Jobs, formerly
Databricks Jobs, whose menu item used to be Workflows
([June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june)).

**Jobs system tables (trends and fleet view).** `system.lakeflow` holds `jobs`, `job_tasks`, `job_run_timeline`,
`job_task_run_timeline`, `pipelines` and `pipeline_update_timeline` ("The `lakeflow` schema was previously known as
`workflow`"). `jobs` is a slowly changing dimension, so take the latest row per job; `job_run_timeline` has
`result_state` (`SUCCEEDED`, `FAILED`, `SKIPPED`, `CANCELLED`, `TIMED_OUT`, `ERROR`, `BLOCKED`) and
`termination_code`, and a run longer than an hour is split into hourly rows with `result_state` only on the last
one ([Jobs system table reference](https://docs.databricks.com/aws/en/admin/system-tables/jobs)). Records "are
typically available within one hour", which makes these tables right for daily reports and trends, and job
notifications right for paging.

*Databricks only, not run here. Syntax from [Jobs system table reference](https://docs.databricks.com/aws/en/admin/system-tables/jobs).*

```sql
WITH jobs AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY workspace_id, job_id ORDER BY change_time DESC) AS rn
  FROM system.lakeflow.jobs QUALIFY rn = 1
)
SELECT r.job_id, jobs.name, r.run_id, r.period_end_time, r.result_state, r.termination_code
FROM system.lakeflow.job_run_timeline r
LEFT JOIN jobs USING (workspace_id, job_id)
WHERE r.result_state IN ('FAILED', 'ERROR', 'TIMED_OUT')
  AND r.period_end_time >= current_timestamp() - INTERVAL 7 DAYS
ORDER BY r.period_end_time DESC;
```

**SQL alerts (any condition you can query).** "Databricks SQL alerts run queries on a schedule and notify you when
a condition that you define is met against the query result." Evaluations resolve to `OK`, `TRIGGERED` or `ERROR`
(the latest version has no `UNKNOWN` state), and an alert can run as a task inside a job
([Databricks SQL alerts](https://docs.databricks.com/aws/en/sql/user/alerts/)). Alert configuration and
evaluations are themselves in `system.alert.alerts` and `system.alert.alert_evaluation_history`
([System tables reference](https://docs.databricks.com/aws/en/admin/system-tables/)). Red Rock alerts on "the number of
failed job runs in the last day is above 0" (the query above), on "silver orders loaded today is below 50% of the
7-day average", and on the cost queries of [Chapter 6](06-Compute.md).

**Data quality monitoring (data you did not write a rule for).** The product name changed: data quality monitoring
now has two capabilities, **anomaly detection** and **data profiling**, and "Data profiling was formerly known as
Lakehouse Monitoring" ([Data quality monitoring](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-quality-monitoring/)).

- **Anomaly detection** is enabled per schema (or for many schemas from the catalog) with `MANAGE`. It learns each
  table's history and checks **freshness** ("If a commit is unusually late, the table is marked as stale") and
  **completeness** ("If the number of rows committed over the last 24 hours is less than the lower bound of this
  range, a table is marked as incomplete"). Intelligent scanning picks how often to scan each table; results show as
  health indicators in Catalog Explorer and in `system.data_quality_monitoring.table_results`
  ([Anomaly detection](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-quality-monitoring/anomaly-detection/)).
- **Data profiling** attaches a profile to one table (time series, inference or snapshot), computes summary
  statistics and drift over time into two metric tables (profile metrics and drift metrics) plus a dashboard, and
  supports custom metrics and alerts; snapshot profiles are limited to 4 TB
  ([Data profiling](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-quality-monitoring/data-profiling/)).

Both run on serverless compute, billed under the `DATA_QUALITY_MONITORING` billing product, and data quality
monitoring "**does not** modify any tables it monitors, nor does it add overhead to any jobs that populate these
tables".

*Databricks only, not run here. Syntax from [Data quality monitoring results system table reference](https://docs.databricks.com/aws/en/admin/system-tables/data-quality-monitoring).*

```sql
WITH latest_rows AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY table_id ORDER BY event_time DESC) AS rn
  FROM system.data_quality_monitoring.table_results
  WHERE catalog_name = 'shop_prod' AND schema_name = 'silver'
)
SELECT table_name, status, freshness.status AS freshness, completeness.status AS completeness
FROM latest_rows
WHERE rn = 1 AND status = 'Unhealthy';
```

Only account admins can read that table at first, and it contains sample values, so grant it with care.

**Inside pipelines.** Expectations in Lakeflow pipelines (formerly Delta Live Tables;
[What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) record passed and dropped rows
in the pipeline event log ([Chapter 13](13-Declarative-Pipelines.md), [Chapter 14](14-Data-Quality-and-CDC.md));
the system tables reference also lists a pipeline events table in Beta. Rules you know in advance belong there;
anomaly detection catches what you did not anticipate.

**A home-made freshness check.** Without any of these services, the table history already answers "when was this
table last written, and how much came in?". This is the kind of query an alert can wrap:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from delta.tables import DeltaTable
from pyspark.sql import functions as F
(DeltaTable.forName(spark, "silver.orders").history()
   .where("operation IN ('WRITE', 'MERGE', 'UPDATE', 'DELETE', 'RESTORE')")
   .agg(F.max("timestamp").alias("last_commit"),
        F.count("*").alias("commits"),
        F.sum(F.col("operationMetrics")["numOutputRows"].cast("long")).alias("rows_appended"))
   .show(truncate=False))
```

```text
+-----------------------+-------+-------------+
|last_commit            |commits|rows_appended|
+-----------------------+-------+-------------+
|2026-11-11 08:30:59.885|6      |4            |
+-----------------------+-------+-------------+
```

!!! tip "In the interview"
    **"How do you monitor your pipelines?"** Three layers. Job and task notifications on failure and on duration
    thresholds go to the on-call channel (Lakeflow Jobs, formerly Databricks Jobs or Workflows). Data checks: rules
    I know as expectations in the pipeline (Lakeflow pipelines, formerly Delta Live Tables), and anomaly detection
    from data quality monitoring for freshness and completeness I did not write rules for; data profiling (formerly
    Lakehouse Monitoring) on the key gold tables for drift. Fleet view: SQL alerts and a dashboard over
    `system.lakeflow.job_run_timeline`, `system.billing.usage` and `system.data_quality_monitoring.table_results`.
    Every alert has an owner and a runbook entry.

## 23.8 Cost governance in one page

*Level: intermediate.*

[Chapter 6](06-Compute.md) covers cost in depth (`system.billing.usage`, list prices, compute policies, serverless
usage policies). The governance view is about making the cheap, attributable choice the default:

| Control | What it does | Limit to know |
| --- | --- | --- |
| Tags on compute, warehouses, pools | flow into `system.billing.usage.custom_tags` for chargeback | missing tags cannot be added to past usage ([Chapter 6](06-Compute.md)) |
| Compute policies | fix or limit cluster settings, require tags, cap `dbus_per_hour` | apply to classic compute, not serverless |
| Serverless usage policies | attribute serverless usage to a team's tags | Public Preview ([Chapter 6](06-Compute.md)) |
| Budgets | "track account-wide spending, or apply filters to track the spending of specific teams, projects, or workspaces", with email or webhook alerts at up to four monthly thresholds | measured "in USD and use the list price of the SKU"; the only "Block usage" option on the page is for Unity Gateway requests, so a budget warns, it does not stop a runaway cluster ([Create and monitor budgets](https://docs.databricks.com/aws/en/admin/account-settings/budgets)) |
| SQL alerts on billing system tables | page someone when daily spend jumps | an alert after the fact, not a limit |

!!! warning "Budgets alert; policies prevent"
    A budget email arrives after the money is spent. If a cost must never happen (a 100-node all-purpose
    cluster, an untagged job), prevent it with a compute policy and permissions; use budgets and alerts for
    everything you cannot prevent.

## 23.9 Sharing and interoperability

*Level: intermediate.*

### OpenSharing (formerly Delta Sharing)

"OpenSharing is the secure data sharing platform in Databricks that lets you share data and AI assets with users
outside your organization, regardless of whether they use Databricks" ([What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/);
the rename from Delta Sharing is in the [Databricks blog, Nov 5, 2026](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next)).
A **share** is "a read-only collection of tables and table partitions" (plus views, volumes, models and notebooks
for Databricks recipients); a **recipient** represents the receiving organization; both are Unity Catalog
securables. Databricks-to-Databricks sharing needs no token and supports notebook, volume and model sharing; open
sharing serves any platform with a bearer token or OIDC federation. Sharing between metastores in the same account
is enabled by default; sharing outside the account needs OpenSharing enabled on the metastore.

*Databricks only, not run here. Syntax from [Create shares for OpenSharing](https://docs.databricks.com/aws/en/opensharing/create-share), [Create data recipients](https://docs.databricks.com/aws/en/opensharing/create-recipient) and [Manage access to OpenSharing data shares](https://docs.databricks.com/aws/en/opensharing/grant-access).*

```sql
CREATE SHARE IF NOT EXISTS red_rock_partner COMMENT "Daily revenue for our logistics partner";
ALTER SHARE red_rock_partner ADD TABLE shop_prod.gold.daily_revenue
  AS gold.daily_revenue WITHOUT HISTORY;
CREATE RECIPIENT IF NOT EXISTS trailhead_logistics USING ID '<sharing-identifier>';
GRANT SELECT ON SHARE red_rock_partner TO RECIPIENT trailhead_logistics;
```

Governance points: share gold or a view, never raw customers; access can be revoked at any time; and history is a
choice. `WITH HISTORY` lets recipients "perform time travel queries, streaming reads, and run transactions", and it
is the default for tables on Databricks Runtime 16.2 and above (and the default for whole schemas on any runtime). For a table that
holds personal data, that means recipients can also reach older versions until those versions age out, which is
one more reason to share aggregated gold. Recipients who need `table_changes()` need change data feed enabled
before the table is shared `WITH HISTORY`.

### Clean rooms

Clean rooms use OpenSharing and serverless compute "to provide a secure and privacy-protecting environment where
multiple parties can work together on sensitive enterprise data without direct access to each other's data"
([What is Databricks Clean Rooms?](https://docs.databricks.com/aws/en/clean-rooms/)). Collaborators see only column
names and types of each other's tables, and code runs only after every collaborator approves the notebook (a
"no-trust" model, with packaged clean rooms as an exception). Limits: at most ten collaborators, no new collaborators
after creation, and no renaming. Use case for Red Rock: measure overlap between its customers and a partner's
loyalty members without either side seeing the other's list.

### Lakehouse Federation

"Lakehouse Federation is the Databricks query federation platform. It provides governed, read-only access to
external data through Unity Catalog foreign catalogs" ([Connect to external databases and catalogs](https://docs.databricks.com/aws/en/query-federation/)).
**Query federation** pushes queries down to a database over JDBC (Postgres, MySQL and others); **catalog
federation** reads foreign tables (for example from Hive metastore or Glue) directly in object storage. The page
recommends Lakeflow Connect over query federation when "performance on higher data volumes and lower latency are
priorities".

*Databricks only, not run here. Syntax from [Run federated queries on PostgreSQL](https://docs.databricks.com/aws/en/query-federation/postgresql).*

```sql
CREATE CONNECTION red_rock_pg TYPE postgresql
OPTIONS (
  host '<hostname>',
  port '<port>',
  user secret ('red-rock-etl','pg-user'),
  password secret ('red-rock-etl','pg-password')
);
CREATE FOREIGN CATALOG IF NOT EXISTS shop_ops_pg USING CONNECTION red_rock_pg
OPTIONS (database 'operations');
```

The password comes from a secret, and access to `shop_ops_pg` tables is granted like any other catalog's.

### Iceberg interoperability

Databricks supports Apache Iceberg tables "managed by Unity Catalog" and by foreign catalogs such as AWS Glue,
needing Databricks Runtime 16.4 LTS or above ([What is Apache Iceberg in Databricks?](https://docs.databricks.com/aws/en/iceberg/)).
Two ways to serve Iceberg clients (Spark, Flink, Trino and others through the Iceberg REST Catalog API):

- **Managed Iceberg tables**: create the table as Iceberg in Unity Catalog; predictive optimization maintains it.
- **Iceberg reads on Delta tables** (UniForm): Databricks generates Iceberg metadata next to the Delta metadata
  "without rewriting the Parquet data files" ([Read Delta Lake tables with Iceberg clients](https://docs.databricks.com/aws/en/delta/uniform)).

*Databricks only, not run here. Syntax from [Read Delta Lake tables with Iceberg clients](https://docs.databricks.com/aws/en/delta/uniform).*

```sql
ALTER TABLE shop_prod.gold.daily_revenue SET TBLPROPERTIES(
  'delta.columnMapping.mode' = 'name',
  'delta.enableIcebergCompatV2' = 'true',
  'delta.universalFormat.enabledFormats' = 'iceberg');
```

The trade-off that matters here: "You cannot enable deletion vectors on a table with Iceberg reads enabled", so
an existing table with deletion vectors needs `REORG` to purge them first, and writes then fall back to rewriting
files.

!!! tip "In the interview"
    **"How do you share gold tables with a partner?"** OpenSharing, formerly Delta Sharing: create a share, add the
    gold table or a view (with an alias, and `WITHOUT HISTORY` if they need only the current state), create a
    recipient and grant `SELECT` on the share. No copies, no exports, revocable at any time
    (`REVOKE SELECT ON SHARE ... FROM RECIPIENT ...`), and with Databricks-to-Databricks sharing both sides get
    auditing and usage tracking. If the partner must combine their data with ours without either side seeing the other's rows,
    that is a clean room. If we need to read their Postgres instead, that is Lakehouse Federation, read-only, with
    the credentials in a secret.

## 23.10 Backup, clones and disaster recovery

*Level: expert.*

**Time travel is not a backup.** "Don't use table history as a long-term backup solution for data archival. Use only
the past 7 days for time travel operations unless you have set both data and log retention configurations to a
larger value" ([Work with table history](https://docs.databricks.com/aws/en/tables/history)). It also lives in the
same storage as the table, so it does not survive the loss of that storage.

**Clones.** A deep clone (`CLONE` or `DEEP CLONE`) "Copies both the data and metadata from the source table to the
clone target"; a shallow clone "Copies only the metadata" and references the source files
([Clone a table on Databricks](https://docs.databricks.com/aws/en/tables/operations/clone)). For archiving, the page
shows a deep clone re-synced on a schedule ("You can sync deep clones incrementally to maintain an updated state of
a source table for disaster recovery") and a clone with long retention properties:

*Databricks only, not run here. Syntax from [Clone a table on Databricks](https://docs.databricks.com/aws/en/tables/operations/clone).*

```sql
-- monthly archive of silver orders, with ten years of time travel on the copy
CREATE OR REPLACE TABLE shop_backup.silver.orders CLONE shop_prod.silver.orders
TBLPROPERTIES (
  delta.logRetentionDuration = '3650 days',
  delta.deletedFileRetentionDuration = '3650 days'
);
-- the exact table version a model or a report was built from
CREATE TABLE shop_backup.silver.orders_v15 CLONE shop_prod.silver.orders VERSION AS OF 15;
```

The same page notes what a clone does not copy: Unity Catalog tags, and the source's history ("A cloned table has
an independent history from its source table"). Keep that in mind for audit: the archive's history starts at the
clone.

**What open-source Delta 4.4.1 can do.** The local engine accepts only shallow clones, so a physical backup there
is a `CREATE TABLE ... AS SELECT` from a pinned version, which copies data but not table properties:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE backup.orders_deep DEEP CLONE silver.orders;
CREATE TABLE backup.orders_deep CLONE silver.orders;
-- PySpark: DeltaTable.forName(spark, 'silver.orders').clone('backup.orders_deep', isShallow=False)
CREATE TABLE backup.orders_dev SHALLOW CLONE silver.orders VERSION AS OF 2;
CREATE TABLE backup.orders_20260305 USING DELTA AS SELECT * FROM silver.orders VERSION AS OF 5;
```

```text
ERROR: [PARSE_SYNTAX_ERROR] Syntax error at or near 'DEEP'. SQLSTATE: 42601 (line 1, pos 32)
ERROR: [PARSE_SYNTAX_ERROR] Syntax error at or near 'CLONE'. SQLSTATE: 42601 (line 1, pos 32)
ERROR: [DELTA_UNSUPPORTED_DEEP_CLONE] Deep clone is not supported by this Delta version.
+-----------------+-------------------+-----------------+----------------+------------------+-----------------+
|source_table_size|source_num_of_files|num_removed_files|num_copied_files|removed_files_size|copied_files_size|
+-----------------+-------------------+-----------------+----------------+------------------+-----------------+
|3471             |2                  |0                |0               |0                 |0                |
+-----------------+-------------------+-----------------+----------------+------------------+-----------------+
```

`num_copied_files` is 0: the shallow clone copied nothing. Its history has one commit, `CLONE` with
`{source -> spark_catalog.silver.orders, sourceVersion -> 2}`. Then the script deletes customer 7's orders from the
source and runs `VACUUM ... RETAIN 0 HOURS` on it (demo setting as in 23.4):

```text
+-----------+------------------+--------------+
|source_rows|shallow_clone_rows|ctas_copy_rows|
+-----------+------------------+--------------+
|2          |4                 |4             |
+-----------+------------------+--------------+

>>> SELECT count(*) AS n FROM backup.orders_dev
+---+
|n  |
+---+
|4  |
+---+

>>> SELECT order_id, status FROM backup.orders_dev ORDER BY order_id
ERROR: [FAILED_READ_FILE.FILE_NOT_EXIST] Encountered error while reading file file:<work>/warehouse/silver.db/orders/part-00001-b7ae6f24-163d-4958-bd4a-3e0e9570dfcb-c000.snappy.parquet. File does not exist.
>>> SELECT order_id, status FROM backup.orders_20260305 ORDER BY order_id
+--------+-------+
|order_id|status |
+--------+-------+
|1001    |PLACED |
|1002    |SHIPPED|
|1003    |SHIPPED|
|1004    |PLACED |
+--------+-------+
```

Outside Unity Catalog, `VACUUM` on the source broke the shallow clone, exactly as the clone page describes for the
Hive metastore ("this raises a `FileNotFoundException`"); the physical copy survived. Note the trap in the first
query: `count(*)` on the broken clone still returned 4, because Delta answers it from the row counts in the log
without opening any data file. Only reading real columns exposed the missing files. Under Unity Catalog the
documented behavior (not run here) is the opposite, as section 23.4 explained: the source's `VACUUM` keeps the
files the clone needs. Either way, a shallow clone is a test copy, not a backup.

**Backups and erasure.** Every backup copy of `customers` is in scope of a deletion request. Either apply the same
`MERGE` delete to archives, keep archives short-lived enough to age out within the deadline, or keep personal data
out of long-term archives by archiving the tables keyed by `customer_id` only.

**Disaster recovery** "replicates workspaces, data, and configurations across cloud regions so your teams keep
working when a regional outage takes your primary deployment offline" ([Disaster recovery](https://docs.databricks.com/aws/en/admin/disaster-recovery)).
The vocabulary: **RPO** is "The maximum period of data loss your service can tolerate"; **RTO** is "The maximum time
within which a business process must be restored". Databricks also provides availability-zone redundancy within a
region; DR is for losing a whole region. The page's points that come up in interviews:

- **Active-passive** is "the most common, the simplest, and the most cost-effective"; **active-active** runs
  everything in both regions and "offers the lowest RTO and RPO" at the highest cost.
- For data, "use Delta Deep Clone" (or cloud replication) to copy managed table data; do not rely on
  geo-redundant replication of the workspace root bucket. Code, jobs and permissions are deployed to both regions
  through CI/CD, treating the workspace "as infrastructure-as-code".
- **Managed disaster recovery** replicates Unity Catalog metadata, managed Delta table data, grants and
  workspace assets on a continuous schedule and handles failover (replication of row filters, column masks and
  ABAC policies is in Private Preview, and such tables are flagged "Failed to replicate"); it is gated ("Apply for access
  through your Databricks account team") ([Managed disaster recovery](https://docs.databricks.com/aws/en/admin/managed-disaster-recovery)).
  Its status is in `system.replication.states`.
- "A DR solution does **not** mitigate data corruption. Corrupted data in the primary region is replicated to the
  secondary region and is corrupted in both regions." Bad `UPDATE`s are fixed with time travel and `RESTORE` or
  from a backup clone, not by failing over.

!!! tip "In the interview"
    **"What is your backup and DR strategy for the lakehouse?"** Separate the failure modes. A bad write: table
    history and `RESTORE`, within the 7-day file retention. Longer-term recovery or audit needs: scheduled deep
    clones into a backup catalog with long retention properties. A regional outage: an active-passive secondary
    region with data replicated by deep clone or managed DR and code deployed by CI/CD to both, sized to an agreed
    RPO and RTO, and tested with failover drills. DR replicates corruption, so it never replaces backups. And
    backups are in scope for deletion requests.

## 23.11 Practice questions

**Q1. You need to know who changed `shop.silver.orders` last night, who granted an analyst access to it, and the
exact SQL that ran. Which source answers each?**

??? success "Answer"
    The change: `DESCRIBE HISTORY shop.silver.orders` (version, timestamp, user, operation, predicate, row metrics,
    job or notebook). The grant: `system.access.audit`, `action_name = 'updatePermissions'` under
    `service_name = 'unityCatalog'`, with `request_params['securable_full_name']` and `request_params['changes']`.
    The SQL: `system.query.history` (`statement_text`), if it ran on a SQL warehouse, serverless compute or a
    Lakeflow pipeline.

    **Why:** table history only records writes to one table; permission changes and reads are account events; and
    query history does not cover classic all-purpose clusters.

**Q2. After `DELETE FROM shop.silver.customers WHERE customer_id = 7`, the customer no longer appears in queries.
Is her data gone? List where it can still be.**

??? success "Answer"
    No. It is still in: the old data files (readable with `VERSION AS OF` until `VACUUM` removes them after the
    retention, 7 days by default); the original file itself if deletion vectors are enabled, since the delete only
    marked the row; the change data feed files under `_change_data` if legacy CDF (`delta.enableChangeDataFeed`) is
    on; the transaction log JSON (in the
    open-source run, as a column statistic) until log cleanup, 30 days by default; and outside the table in
    bronze, landing files, Kafka topics, clones, backups and exports.

    **Why:** Delta keeps old versions on purpose for time travel and concurrency. Erasure needs the full sequence:
    delete in every layer, `REORG TABLE ... APPLY (PURGE)` where deletion vectors are on, then `VACUUM` after the
    retention period.

**Q3. What does the last query return?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE c (customer_id INT, email STRING) USING DELTA;      -- version 0
INSERT INTO c VALUES (7, 'maya.chen@example.com'), (8, 'liam.ortiz@example.com');  -- version 1
DELETE FROM c WHERE customer_id = 7;                              -- version 2
SELECT email FROM c VERSION AS OF 1 WHERE customer_id = 7;
```

??? success "Answer"
    `maya.chen@example.com` (from `ch23_03_practice.out`). Version 1 still references the file that contains her
    row, and no `VACUUM` has run.

    ```text
    +---------------------+
    |email                |
    +---------------------+
    |maya.chen@example.com|
    +---------------------+
    ```

    **Why:** time travel reads the files listed in the old version of the log. Only `VACUUM` (after the retention
    period) removes those files, and on Databricks Runtime 18.0 and above time travel past
    `deletedFileRetentionDuration` is blocked anyway.

**Q4. Write the deletion job: delete every customer listed in the request table (and not yet processed) from a
customers table, in SQL and in PySpark.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (Local schema names; on Databricks the tables are
    `shop.silver.customers`, `shop.bronze.customers` and `shop.ops.gdpr_requests`.)

    ```sql
    MERGE INTO silver.customers AS t
    USING (SELECT customer_id FROM ops.gdpr_requests WHERE processed_at IS NULL) AS r
    ON t.customer_id = r.customer_id
    WHEN MATCHED THEN DELETE;
    ```

    ```python
    from delta.tables import DeltaTable
    requests = spark.table("ops.gdpr_requests").select("customer_id")
    (DeltaTable.forName(spark, "bronze.customers").alias("t")
        .merge(requests.alias("r"), "t.customer_id = r.customer_id")
        .whenMatchedDelete()
        .execute())
    ```

    Both ran in `ch23_01_gdpr_delete.py` (steps G3 and G14); the SQL deleted 1 customer row, and bronze kept only
    customer 8. In a real job, add `.where("processed_at IS NULL")` to the PySpark request read, as the SQL does
    (in the script the request had already been marked processed when the bronze step ran).
    Then repeat for every table with the key, and set `processed_at` on the requests only after all layers succeed.

    **Why:** the GDPR page recommends `MERGE` for deleting many records at once and a scheduled job driven by a
    table of requests. Keep one row per customer in the control table, and delete by key, not by email, so the
    email does not end up in query text and logs.

**Q5. The customers table has deletion vectors enabled. The erasure job runs `DELETE` and then `VACUUM` after 7
days. Is the row physically gone?**

??? success "Answer"
    Not necessarily. With deletion vectors the `DELETE` only marks the row in a deletion vector; the data file that
    holds it is still part of the current version, so `VACUUM` will not remove it. Run
    `REORG TABLE shop.silver.customers APPLY (PURGE)` after the delete, which rewrites files that carry deletion
    vectors; then `VACUUM` after the retention removes the old file. In the local run, `MERGE` added 1 deletion
    vector and removed 0 files, and only `REORG` removed the file (`numDeletionVectorsRemoved` 1).

    **Why:** the GDPR page: "For tables with deletion vectors enabled, after deleting records, you must also run
    `REORG TABLE ... APPLY (PURGE)` to permanently delete underlying records."

**Q6. In the local run, `VACUUM silver.customers RETAIN 0 HOURS` fails with `DELTA_VACUUM_RETENTION_PERIOD_TOO_SHORT`.
Should you turn off the check to finish a GDPR request faster?**

??? success "Answer"
    No. The check protects concurrent and long-running writers: files a running job wrote but has not committed yet
    look unreferenced, and a short retention can delete them and corrupt the table. Databricks "strongly recommends
    setting a retention interval of at least 7 days". Plan the deadline around it instead: process requests as soon
    as they arrive, purge, and let the 7-day file retention (and the 30-day default log retention) run their course.

    **Why:** the error message says it directly: the retention "is too low and may corrupt this Delta table if any
    writes are in progress". On managed tables, predictive optimization keeps at least 7 days regardless.
    (`RETAIN n HOURS` is open-source Delta syntax; the current Databricks `VACUUM` reference shows no `RETAIN`
    clause and sets the window with `delta.deletedFileRetentionDuration`; see [Chapter 4](04-Delta-Lake.md).)

**Q7. After the VACUUM, a downstream job calls `table_changes('shop.silver.customers', 2)` and fails with
`FAILED_READ_FILE.FILE_NOT_EXIST`. Why?**

??? success "Answer"
    With legacy change data feed (`delta.enableChangeDataFeed`, as in the local run), the change data for version 2
    was stored in a file under `_change_data`, and `VACUUM` deleted it once it passed
    the retention threshold. The change feed for that version is gone, exactly as in step G12 of the local run.

    **Why:** "The `VACUUM` command deletes change data files" (change data feed page). CDF is not a permanent
    archive; consumers must read changes within the retention window, and if you archive changes, the archive
    holds personal data and is in scope for erasure.

**Q8. Does the change data feed help or hurt with GDPR?**

??? success "Answer"
    Both. It helps propagate the delete: a silver or gold consumer reading the feed sees `_change_type = 'delete'`
    for the customer and can apply it downstream; the GDPR page calls streaming from change feeds "a more robust
    streaming implementation" than streaming from the table. It hurts because the delete record carries the whole row, PII included, in
    `_change_data` files with legacy change data feed (the local run showed the email in the feed) until `VACUUM`
    removes them.

    **Why:** an interviewer wants to hear that the feed is part of the data you must erase, not just a tool.

**Q9. A streaming job reads `shop.bronze.customers` with `spark.readStream.table(...)`. After the weekly erasure job,
it fails. What are the fixes?**

??? success "Answer"
    A Delta streaming source expects appends; a `DELETE` or `MERGE` commit breaks it. Options from the GDPR page:
    (1) delete in the source, delete in the target streaming table, and set `skipChangeCommits` to `true` on the
    streaming read so delete commits are skipped; (2) stream from the change feed and apply deletes explicitly; (3)
    fully refresh the streaming table, only if the upstream data is still available to reprocess.

    **Why:** with `skipChangeCommits` the stream ignores the delete, so you must delete in the target yourself;
    otherwise the person stays in silver. See [Chapter 11](11-Structured-Streaming.md).

**Q10. Gold `daily_revenue` is a materialized view over silver. What do you do for an erasure?**

??? success "Answer"
    Nothing special in the definition: "Materialized views automatically handle deletions in sources". But "You
    must refresh a materialized view and run maintenance to ensure that deletions are completely processed", and a
    delete in the source may make the refresh fully recompute.

    **Why:** a materialized view's stored result still holds the old rows until it is refreshed, and its old files
    until maintenance (or `VACUUM`) removes them; with deletion vectors, `REORG ... APPLY (PURGE)` applies to
    materialized views too.

**Q11. Scenario: a developer created `shop_dev.silver.customers` as a Unity Catalog shallow clone of
`shop_prod.silver.customers` last month. You erase customer 7 in prod, purge and vacuum after 7 days. Is her data
gone from storage?**

??? success "Answer"
    No. The clone still references the old prod files that contain her row, and Unity Catalog keeps them: "Running
    `VACUUM` on the source of a shallow clone doesn't break the cloned table", because valid files include files
    "necessary for returning queries for both shallow cloned tables and the source table". The dev clone also shows
    her to anyone who can read `shop_dev`. Drop the clone (or delete from it as well) as part of the erasure, then
    vacuum, remembering that Databricks keeps a dropped shallow clone's link to the base files for 7 days to support
    `UNDROP` (documented on the Unity Catalog shallow clone page, a Public Preview feature; not run here).

    **Why:** outside Unity Catalog the opposite happens (the local run: `VACUUM` on the source broke the clone with
    `FILE_NOT_EXIST`). Either way, clones of personal data belong in the erasure inventory.

**Q12. Find the bug: an erasure runbook says "run `DELETE`, then `VACUUM` immediately; the data is gone".**

??? success "Answer"
    `VACUUM` with the default retention only deletes files that have been unreferenced for longer than 7 days. Files
    made obsolete by today's delete stay. In the local run, `VACUUM ... DRY RUN` right after the delete found 0
    files to delete. The runbook must say: delete, purge deletion vectors, then `VACUUM` once the retention has
    passed (or let predictive optimization do it), and count the log retention too.

    **Why:** "removes data files that are no longer referenced by a Delta table version in the last 7 days"
    (VACUUM reference).

**Q13. Write a query that lists the failed job runs of the last 7 days with the job name.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Jobs system table reference](https://docs.databricks.com/aws/en/admin/system-tables/jobs).*

    ```sql
    WITH jobs AS (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY workspace_id, job_id ORDER BY change_time DESC) AS rn
      FROM system.lakeflow.jobs QUALIFY rn = 1
    )
    SELECT r.job_id, jobs.name, r.run_id, r.period_end_time, r.result_state, r.termination_code
    FROM system.lakeflow.job_run_timeline r
    LEFT JOIN jobs USING (workspace_id, job_id)
    WHERE r.result_state IN ('FAILED', 'ERROR', 'TIMED_OUT')
      AND r.period_end_time >= current_timestamp() - INTERVAL 7 DAYS;
    ```

    **Why:** `jobs` is an SCD2 table (latest row per `workspace_id, job_id`); `job_id` is only unique within a
    workspace; and `result_state` is filled only on the last hourly slice of a long run, so filtering on it never
    double-counts.

**Q14. Your query on `system.query.history` shows `<REDACTED>` in `statement_text`. Why, and is that a bug?**

??? success "Answer"
    Not a bug. `statement_text` returns `<REDACTED>` "unless you are an account admin or a member of the
    `databricks_pii_access` account-level group". Statement text can contain literals such as emails, so it is
    treated as sensitive. Ask an admin for membership, or for a dynamic view over the table, which the page
    recommends for sharing query history.

    **Why:** the same rule masks SQL definitions in some `request_params` keys of the audit log table.

**Q15. Analysts run SQL on a classic all-purpose cluster. Their queries are missing from `system.query.history`.
Why, and where else can you look?**

??? success "Answer"
    Query history covers SQL warehouses, serverless compute for notebooks and jobs, and Lakeflow pipelines; it does
    not cover classic all-purpose compute. For those users, look at `system.access.audit` (for example
    `generateTemporaryTableCredential` events show who got access to which table and when) and at
    `DESCRIBE HISTORY` for writes.

    **Why:** knowing the coverage of each system table prevents wrong conclusions such as "nobody read the table".

**Q16. Write a query that shows who accessed `shop.silver.customers` in the last 30 days, with the operation each credential was granted for.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Audit log system table reference](https://docs.databricks.com/aws/en/admin/system-tables/audit-logs).*

    ```sql
    SELECT event_date, user_identity.email, request_params['operation'] AS operation, count(*) AS events
    FROM system.access.audit
    WHERE action_name = 'generateTemporaryTableCredential'
      AND request_params['table_full_name'] = 'shop.silver.customers'
      AND event_date >= current_date() - INTERVAL 30 DAYS
    GROUP BY ALL;
    ```

    **Why:** the audit log reference says "You can use this event to determine who queried what and when". Filter
    on `event_date`, which the reference recommends for performance.

**Q17. What is the difference between a tag and a governed tag?**

??? success "Answer"
    Any user with `APPLY TAG` can set an ordinary tag with any key and value. A governed tag is an account-level tag
    with a tag policy: admins define allowed values and who may assign it (`ASSIGN` permission), it is enforced in
    every workspace, and it is marked with a lock. System tags are governed tags predefined by Databricks (for
    example for data classification). ABAC policies use governed tags as their attributes.

    **Why:** if anyone can set or remove the tag that a masking policy depends on, the policy is only as strong as
    the weakest tagger; governed tags close that gap.

**Q18. A colleague tags the customers table with `deleted_customer = maya.chen@example.com` to track erasures. What
is wrong?**

??? success "Answer"
    Tags are metadata stored "as plain text" that "may be replicated globally"; the tags page says not to use tag
    names or values that contain personal or sensitive information. The erasure itself would leak the email. Track
    requests by key in a governed control table (`ops.gdpr_requests`) with restricted access. (The key `deleted_customer`
    is fine; the value is the problem.)

    **Why:** governance metadata spreads further than data: search, information schema, exports.

**Q19. What does Data Classification do, and where do you see its results?**

??? success "Answer"
    It scans tables in enabled catalogs (incrementally, with "intelligent scanning", using an LLM to assist),
    detects sensitive classes such as email addresses, and can tag matching columns with system classification
    tags automatically. Results are in the UI and in `system.data_classification.results` (Public Preview), with
    `class_tag`, `confidence` (`HIGH`/`LOW`), `frequency` and up to five `samples`. It needs serverless compute and
    `MANAGE` on the catalog to enable.

    **Why:** the results table holds sample values, so access to it must be limited.

**Q20. What is Lakehouse Monitoring called now, and how is it different from anomaly detection?**

??? success "Answer"
    It is **data profiling** ("Data profiling was formerly known as Lakehouse Monitoring"), one of the two
    capabilities of **data quality monitoring**. Data profiling is configured per table (time series, inference or
    snapshot), computes summary statistics and drift into a profile metrics table and a drift metrics table, and
    creates a dashboard. **Anomaly detection** is enabled per schema and automatically checks the tables'
    **freshness** (is a commit unusually late?) and **completeness** (fewer rows than predicted in the last 24
    hours?), with intelligent scanning that "prioritizes important tables and skips low-impact ones", and results in
    `system.data_quality_monitoring.table_results`.

    **Why:** use anomaly detection for broad, rule-free coverage; data profiling for deep statistics on a few key
    tables.

**Q21. Anomaly detection flags `shop_prod.silver.orders` as "incomplete" this morning. What does that mean and what
do you check?**

??? success "Answer"
    The rows committed in the last 24 hours are below the lower bound of the range predicted from the table's
    history. Check the upstream job run (`system.lakeflow.job_run_timeline` or the job UI), the bronze table's
    history for the last load's `numOutputRows`, rescued or quarantined rows, and whether the source simply sent
    less data (a holiday, an outage at the source).

    **Why:** the check measures volume, not correctness; it tells you where to look, not what broke.

**Q22. A job has a failure notification at job level. A task failed twice and succeeded on its third retry. Did
anyone get notified?**

??? success "Answer"
    No. "Job-level notifications aren't sent when failed tasks are retried", and the run ended successfully. To hear
    about each failed attempt, add task-level notifications (optionally "Mute notifications until the last retry"
    if you only want the final failure).

    **Why:** silent retries hide flaky tasks that cost money and eventually fail for real; trend them from
    `system.lakeflow.job_task_run_timeline`.

**Q23. What states can a (current) Databricks SQL alert evaluation have, and how is that different from legacy
alerts?**

??? success "Answer"
    `OK`, `TRIGGERED` or `ERROR`. The latest alerts dropped the legacy `UNKNOWN` status, and each alert owns its query
    (an existing saved query cannot be reused). Alerts can also run as a task in a job, so downstream tasks can
    branch on the result.

    **Why:** an alert in `ERROR` (its query failed) is not the same as `OK`; route errors to someone too.

**Q24. A notebook prints `[REDACTED]` for a secret. Is the secret safe from people who can run that notebook?**

??? success "Answer"
    No. Redaction "applies only to literal secret values" and "does not prevent deliberate and arbitrary
    transformations of a secret literal"; anyone with read access to the secret can recover it (for example by
    transforming it before printing), and the REST API returns values unredacted. Protect secrets with access
    control: give `READ` on the scope (or `READ SECRET` on a Unity Catalog secret) only to the job's service
    principal. Every read is audited.

    **Why:** redaction prevents accidents, not insiders.

**Q25. When would you use a Unity Catalog secret instead of a workspace secret scope?**

??? success "Answer"
    When the secret is needed in several workspaces (Unity Catalog secrets are available in every workspace
    attached to the metastore), when you want per-secret privileges rather than all-or-nothing per scope, or when a
    Unity Catalog Python or Scala UDF must use it (callers need only `EXECUTE`). Keep workspace scopes where Unity
    Catalog secrets are not supported, for example Spark configuration properties and environment variables on
    compute, or the `secret()` function on SQL warehouses.

    **Why:** the comparison table on the Secret management page lists exactly these differences.

**Q26. Why should production jobs run as a service principal, not as the engineer who built them?**

??? success "Answer"
    The job keeps working when the engineer leaves or changes groups; the service principal can be given exactly
    the privileges the job needs; humans can then have read-only access to production, so a manual mistake cannot
    overwrite it; and history and audit logs show a stable job identity. The Unity Catalog best practices say to use
    service principals to run jobs and to "Reserve direct `MODIFY` access to production tables for service
    principals."

    **Why:** least privilege is only possible if automation and people have different identities.

**Q27. Design dev, staging and prod for Red Rock Supply in Unity Catalog.**

??? success "Answer"
    One metastore in the region, as Databricks recommends for all SDLC scopes. Three catalogs, `shop_dev`,
    `shop_staging`, `shop_prod`, each with `bronze`, `silver`, `gold`. Three workspaces, with each catalog bound to
    its workspace (`shop_prod` only to the prod workspace; optionally read-only binding of prod into dev).
    Production written only by a service principal deployed through CI/CD with Declarative Automation Bundles
    (formerly Databricks Asset Bundles) whose targets change only the catalog and identity; groups own production
    objects; developers get read access to prod gold at most; dev uses sampled or masked data rather than clones of
    customer tables.

    **Why:** separation by catalog keeps code identical across environments, binding blocks cross-workspace access
    even with grants, and identities keep humans from writing prod.

**Q28. Will an account budget stop a runaway all-purpose cluster?**

??? success "Answer"
    No. Budgets track spending in USD at list price and send email or webhook alerts at thresholds; the only
    "Block usage" option on the budgets page is for Unity Gateway requests. To prevent the cluster, use compute
    policies (`dbus_per_hour`, worker limits, auto-termination) and limit who can create unrestricted compute; to
    detect it fast, a SQL alert on billing data. See [Chapter 6](06-Compute.md).

    **Why:** prevention is a policy; a budget is a smoke alarm.

**Q29. Write the SQL to share `shop_prod.gold.daily_revenue` with a partner on another Databricks account, without
history.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Create shares for OpenSharing](https://docs.databricks.com/aws/en/opensharing/create-share).*

    ```sql
    CREATE SHARE IF NOT EXISTS red_rock_partner;
    ALTER SHARE red_rock_partner ADD TABLE shop_prod.gold.daily_revenue
      AS gold.daily_revenue WITHOUT HISTORY;
    CREATE RECIPIENT IF NOT EXISTS trailhead_logistics USING ID '<sharing-identifier>';
    GRANT SELECT ON SHARE red_rock_partner TO RECIPIENT trailhead_logistics;
    ```

    The sharing identifier comes from the recipient's metastore. To stop sharing, revoke the grant or remove the table
    from the share. The revoke is
    `REVOKE SELECT ON SHARE red_rock_partner FROM RECIPIENT trailhead_logistics;`

    **Why:** OpenSharing (formerly Delta Sharing) shares live data without copies; on Databricks Runtime 16.2 and
    above a table is added `WITH HISTORY` by default, so say `WITHOUT HISTORY` explicitly if the partner should not
    time travel.

**Q30. OpenSharing or a clean room?**

??? success "Answer"
    OpenSharing when one side gives the other read access to data. A clean room when several parties need to
    compute on their combined sensitive data without seeing each other's rows: collaborators see only column names
    and types, every notebook must be approved by all collaborators before it runs, and results come back as
    output tables. Clean rooms are built on OpenSharing and serverless compute and allow at most ten collaborators.

    **Why:** the question is "who may see the rows?". In sharing, the recipient does; in a clean room, nobody
    outside the owner does.

**Q31. What is Lakehouse Federation, and when would you not use it?**

??? success "Answer"
    Governed, read-only access to external data through Unity Catalog foreign catalogs: query federation pushes
    queries to databases such as PostgreSQL over JDBC; catalog federation reads tables of external catalogs directly
    from object storage. It is good for ad hoc and BI access and for migrations. Avoid it for heavy, frequent or
    low-latency loads from operational databases: Databricks recommends Lakeflow Connect "if performance on higher
    data volumes and lower latency are priorities". And it is read-only.

    **Why:** every federated query also loads the source database, which the owners of that database will not like.

**Q32. An external team wants to read `shop_prod.gold.daily_revenue` with an Iceberg client. The table has deletion
vectors. What happens when you enable Iceberg reads?**

??? success "Answer"
    You cannot have both: "You cannot enable deletion vectors on a table with Iceberg reads enabled." Use `REORG`
    to purge and turn off deletion vectors while enabling Iceberg reads (the page documents an upgrade path with
    `REORG`), or create the table as a managed Iceberg table instead. Iceberg reads also need column mapping and
    a Unity Catalog table.

    **Why:** table features decide which readers can use a table. Iceberg reads keep one copy of the Parquet files
    for both formats, and the page lists deletion vectors as incompatible with them, so decide early which engines
    must read a table.

**Q33. Is time travel a backup?**

??? success "Answer"
    No. The history page says "Don't use table history as a long-term backup solution for data archival" and to
    rely on only the past 7 days unless both retentions are raised. Time travel lives in the same storage as the
    table, is cut by `VACUUM`, and on Databricks Runtime 18.0 and above is blocked beyond
    `deletedFileRetentionDuration`. Use it for quick undo (`RESTORE`), and deep clones into a separate catalog for
    backups.

    **Why:** a backup must survive the failure it protects against; time travel does not survive a dropped bucket
    or a short retention.

**Q34. What does the last query return on the local engine, and why?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.orders (order_id INT, customer_id INT, status STRING) USING DELTA;
INSERT INTO silver.orders VALUES (1001, 7, 'PLACED'), (1002, 8, 'PLACED');     -- version 1
INSERT INTO silver.orders VALUES (1003, 7, 'SHIPPED'), (1004, 9, 'PLACED');    -- version 2
CREATE TABLE backup.orders_dev SHALLOW CLONE silver.orders VERSION AS OF 2;
DELETE FROM silver.orders WHERE customer_id = 7;
SET spark.databricks.delta.retentionDurationCheck.enabled = false;  -- demo only
VACUUM silver.orders RETAIN 0 HOURS;
SELECT order_id, status FROM backup.orders_dev;
```

??? success "Answer"
    An error (from `ch23_03_practice.out`):

    ```text
    ERROR: [FAILED_READ_FILE.FILE_NOT_EXIST] Encountered error while reading file file:<work>/warehouse/silver.db/orders/part-00000-c32351a9-b9ac-4836-9495-2c897238821f-c000.snappy.parquet. File does not exist.
    ```

    The shallow clone points at the source's files. The delete made the files that held customer 7's orders
    unreferenced in the source, and `VACUUM` with zero retention deleted them. In the longer run of section 23.10,
    a `count(*)` on the broken clone still returned 4, because Delta answers it from the log's row counts without
    opening data files.

    **Why:** outside Unity Catalog a shallow clone depends on the source's files. Under Unity Catalog, per the shallow
    clone page (not run here), `VACUUM` on the source keeps files that clones reference, so the clone keeps working
    (and keeps the deleted data).

**Q35. Your manager says "we have DR to another region, so we do not need backups". Respond.**

??? success "Answer"
    DR protects against losing a region, not against bad data: "A DR solution does not mitigate data corruption.
    Corrupted data in the primary region is replicated to the secondary region and is corrupted in both regions."
    A bad `UPDATE` or a buggy job is fixed with time travel and `RESTORE` within the retention window, or from a
    backup clone kept with longer retention. DR and backups answer different RPO and RTO questions and both are
    needed.

    **Why:** most real incidents are human or code errors, not regional outages.

**Q36. You set the session config `spark.databricks.delta.commitInfo.userMetadata` in a serverless notebook, but
`DESCRIBE HISTORY` shows `userMetadata` as NULL. Why, and how do you fix it?**

??? success "Answer"
    "The SparkSession configuration keys for commit metadata are not supported on serverless compute." Use the
    DataFrameWriter option instead: `df.write.option("userMetadata", "job=nightly_load run=812")...`. On classic
    compute (and in the local run) the session setting works, and the writer option wins if both are set.

    **Why:** commit labels only help an audit if they are reliably written; choose the mechanism that works on the
    compute you run.

**Q37. For how long can you query `system.access.audit`, `system.query.history` and `system.billing.usage`?**

??? success "Answer"
    Free retention per the system tables reference: audit 395 days, query history 365 days, billable usage
    indefinite. Account admins can configure a retention from 30 to 3,650 days for supported tables (Beta), which
    excludes tables with a 365-day or indefinite retention.

    **Why:** if auditors need several years of access history, plan for configurable retention or copy what you
    need into your own governed tables inside Databricks (the reference warns: "Databricks highly discourages you from moving this data outside the platform").

## Sources

- [System tables reference](https://docs.databricks.com/aws/en/admin/system-tables/) (last updated Nov 9, 2026)
- [Audit log system table reference](https://docs.databricks.com/aws/en/admin/system-tables/audit-logs) (last updated Nov 3, 2026)
- [Audit log reference](https://docs.databricks.com/aws/en/admin/account-settings/audit-logs) (last updated Nov 10, 2026)
- [Query history system table reference](https://docs.databricks.com/aws/en/admin/system-tables/query-history) (last updated Nov 4, 2026)
- [Jobs system table reference](https://docs.databricks.com/aws/en/admin/system-tables/jobs) (last updated Nov 6, 2026)
- [Data quality monitoring results system table reference](https://docs.databricks.com/aws/en/admin/system-tables/data-quality-monitoring) (last updated Nov 2, 2026)
- [Data classification system table reference](https://docs.databricks.com/aws/en/admin/system-tables/data-classification) (last updated Sep 11, 2026)
- [Apply tags to Unity Catalog securable objects](https://docs.databricks.com/aws/en/database-objects/tags) (last updated Oct 26, 2026)
- [SET TAG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-set-tag) (last updated Oct 12, 2026)
- [COLUMN_TAGS](https://docs.databricks.com/aws/en/sql/language-manual/information-schema/column_tags) (last updated Sep 11, 2026)
- [Governed tags](https://docs.databricks.com/aws/en/admin/governed-tags/) (last updated Oct 12, 2026)
- [Data Classification](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-classification) (last updated Oct 29, 2026)
- [Attribute-based access control in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/) (last updated Oct 22, 2026)
- [Table history schema and operation metrics](https://docs.databricks.com/aws/en/tables/history-schema) (last updated Sep 11, 2026)
- [Enrich tables with custom metadata](https://docs.databricks.com/aws/en/tables/operations/custom-metadata) (last updated Sep 11, 2026)
- [Work with table history](https://docs.databricks.com/aws/en/tables/history) (last updated Nov 6, 2026)
- [Prepare your data for GDPR compliance](https://docs.databricks.com/aws/en/security/privacy/gdpr-delta) (last updated Oct 9, 2026)
- [Deletion vectors in Databricks](https://docs.databricks.com/aws/en/tables/features/deletion-vectors) (last updated Nov 6, 2026)
- [Remove unused data files with vacuum](https://docs.databricks.com/aws/en/tables/operations/vacuum) (last updated Nov 6, 2026)
- [VACUUM](https://docs.databricks.com/aws/en/sql/language-manual/delta-vacuum) (last updated Sep 11, 2026)
- [Use change data feed on Databricks](https://docs.databricks.com/aws/en/tables/features/change-data-feed) (last updated Oct 9, 2026)
- [Predictive optimization for Unity Catalog managed tables](https://docs.databricks.com/aws/en/optimizations/predictive-optimization) (last updated Nov 6, 2026)
- [Clone a table on Databricks](https://docs.databricks.com/aws/en/tables/operations/clone) (last updated Sep 11, 2026)
- [Shallow clone for Unity Catalog tables](https://docs.databricks.com/aws/en/tables/operations/clone-unity-catalog) (last updated Sep 16, 2026)
- [Delta transaction log protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md) (GitHub; no last-updated date shown)
- [Secret management](https://docs.databricks.com/aws/en/security/secrets/) (last updated Nov 6, 2026)
- [Workspace secret scopes](https://docs.databricks.com/aws/en/security/secrets/workspace-secret-scopes) (last updated Nov 6, 2026)
- [Secrets in Unity Catalog](https://docs.databricks.com/aws/en/security/secrets/unity-catalog-secrets) (last updated Nov 6, 2026)
- [secret function](https://docs.databricks.com/aws/en/sql/language-manual/functions/secret) (last updated Nov 6, 2026)
- [Service principals](https://docs.databricks.com/aws/en/admin/users-groups/service-principals) (last updated Oct 12, 2026)
- [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) (last updated Oct 30, 2026)
- [Workspace-catalog binding](https://docs.databricks.com/aws/en/data-governance/unity-catalog/access-control/workspace-catalog-binding) (last updated Sep 11, 2026)
- [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (last updated Nov 5, 2026)
- [Add notifications on a job](https://docs.databricks.com/aws/en/jobs/notifications) (last updated Nov 6, 2026)
- [Databricks SQL alerts](https://docs.databricks.com/aws/en/sql/user/alerts/) (last updated Nov 5, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [Data quality monitoring](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-quality-monitoring/) (last updated Sep 11, 2026)
- [Anomaly detection](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-quality-monitoring/anomaly-detection/) (last updated Nov 2, 2026)
- [Data profiling](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-quality-monitoring/data-profiling/) (last updated Sep 11, 2026)
- [Create and monitor budgets](https://docs.databricks.com/aws/en/admin/account-settings/budgets) (last updated Nov 10, 2026)
- [What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/) (last updated Oct 27, 2026)
- [Create shares for OpenSharing](https://docs.databricks.com/aws/en/opensharing/create-share) (last updated Oct 29, 2026)
- [Create data recipients for OpenSharing (Databricks-to-Databricks sharing)](https://docs.databricks.com/aws/en/opensharing/create-recipient) (last updated Sep 22, 2026)
- [Manage access to OpenSharing data shares (for providers)](https://docs.databricks.com/aws/en/opensharing/grant-access) (last updated Sep 11, 2026)
- [From Delta Sharing to OpenSharing: what changed, what's next](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next) (Databricks blog, Nov 5, 2026)
- [What is Databricks Clean Rooms?](https://docs.databricks.com/aws/en/clean-rooms/) (last updated Nov 4, 2026)
- [Connect to external databases and catalogs](https://docs.databricks.com/aws/en/query-federation/) (last updated Sep 29, 2026)
- [Run federated queries on PostgreSQL](https://docs.databricks.com/aws/en/query-federation/postgresql) (last updated Nov 5, 2026)
- [What is Apache Iceberg in Databricks?](https://docs.databricks.com/aws/en/iceberg/) (last updated Nov 4, 2026)
- [Read Delta Lake tables with Iceberg clients](https://docs.databricks.com/aws/en/delta/uniform) (last updated Sep 11, 2026)
- [Disaster recovery](https://docs.databricks.com/aws/en/admin/disaster-recovery) (last updated Nov 4, 2026)
- [Managed disaster recovery](https://docs.databricks.com/aws/en/admin/managed-disaster-recovery) (last updated Nov 4, 2026)
- [Databricks platform release notes, June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026; Lakeflow Jobs rename)
