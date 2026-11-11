# 4. Delta Lake

*Every table you create on Databricks is a Delta Lake table unless you ask for something else, so Delta is the ground the whole medallion architecture stands on. This chapter opens a Delta table up: the Parquet files, the transaction log beside them, and how that log gives you transactions, schema checks, updates, time travel and safe concurrent writers on plain cloud storage. Interviewers ask about Delta in almost every data engineer interview, and they like "what happens when" questions: two jobs write at once, someone deletes every row, `VACUUM` runs with zero retention. You will run each of those here and see the real result.*

!!! abstract "In this chapter"
    **You will learn:**

    - why a folder of Parquet files is not a table you can trust, and what Delta adds
    - what is inside `_delta_log`: JSON commits, actions (`add`, `remove`, `metaData`, `protocol`, `commitInfo`), checkpoints
    - how ACID transactions and optimistic concurrency work, and what happens when two writers collide
    - reading and writing Delta in SQL and PySpark, by name and by path
    - schema enforcement, schema evolution (`mergeSchema`, `ALTER TABLE ADD COLUMNS`) and column mapping
    - `UPDATE`, `DELETE`, `MERGE` basics; time travel, `DESCRIBE HISTORY`, `DESCRIBE DETAIL`, `RESTORE`
    - `VACUUM` and retention, `OPTIMIZE` and small files, deletion vectors
    - table features and protocol versions, and how Databricks Delta differs from open-source Delta

    **You need:** 3. Apache Spark for data engineers (DataFrames, lazy evaluation). Generic SQL `UPDATE`/`DELETE`/`MERGE` is in the SQL course: [Insert, update, delete, merge](../../databases/sql/17-Insert-Update-Delete-Merge.md).

    **Levels:** sections 4.1 to 4.4 beginner, 4.5 to 4.9 intermediate, 4.10 expert.

All runnable examples in this chapter ran on Apache Spark 4.2 with Delta Lake 4.4.1. Locally there is no Unity Catalog, so tables have one-part names (`orders`) instead of `shop.silver.orders`, and every `CREATE TABLE` says `USING DELTA`, because open-source Spark's default format is Parquet. On Databricks you can leave `USING DELTA` out. The scripts and their full output are in `src/ch04/`.

## 4.1 The problem with a folder of Parquet files
*Level: beginner.*

Parquet is a columnar file format: fast to scan, compressed, with the schema stored in each file. A data lake used to be "a folder of Parquet files per table". Spark treats the folder as a table by reading every file in it. That works until you need any of the things a database gives you for free:

- **No transactions.** A write is many files created one by one. If the job dies halfway, some files are there and some are not. A reader that lists the folder in the middle of a write sees half a result.
- **Overwrite is delete-then-write.** To overwrite a Parquet folder, Spark removes the old files and then writes new ones. If the new write fails, the old data is already gone.
- **No `UPDATE`, `DELETE` or `MERGE`.** Files are immutable. Changing one row means rewriting files yourself and swapping them in by hand, which is exactly the unsafe partial-write problem again.
- **No schema check.** Any job can drop a file with different columns or types into the folder. You find out when a reader fails, possibly days later.

Here is all of that on a real engine: a three-row Red Rock Supply `orders` folder, an overwrite job that fails on one bad record, then the same steps on a Delta table.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
orders.write.mode("overwrite").parquet(pq_path)            # 3 rows

def broken_rewrite(df):  # simulates a job that dies on one bad record
    return df.withColumn("amount",
        F.expr("CASE WHEN order_id = 1003 THEN raise_error('bad record 1003') ELSE amount END"))

broken_rewrite(orders).write.mode("overwrite").parquet(pq_path)              # fails
broken_rewrite(orders).write.format("delta").mode("overwrite").save(dl_path) # fails

sql(f"UPDATE parquet.`{pq_path}` SET status = 'CANCELLED' WHERE order_id = 1002")
bad.write.mode("append").parquet(pq_path)                  # customer_id and amount are STRING
bad.write.format("delta").mode("append").save(dl_path)
```

Output (from `ch04_01_parquet_problem.out`; the script cuts long error lines):

```text
=== 1. Parquet folder: an overwrite that fails halfway ===
rows before: 3
overwrite failed: [USER_RAISED_EXCEPTION] bad record 1003 SQLSTATE: P0001
reading the folder now fails: AnalysisException [UNABLE_TO_INFER_SCHEMA] Unable to infer schema for Parquet. It must be specified manually. SQLSTATE: 42KD9
files left in the folder: []

=== 2. Delta table: the same failed overwrite ===
rows before: 3
overwrite failed: [USER_RAISED_EXCEPTION] bad record 1003 SQLSTATE: P0001
rows after failed overwrite: 3
commits in _delta_log: ['00000000000000000000.json']

=== 3. Parquet folder: no UPDATE ===
UnsupportedOperationException: [UNSUPPORTED_FEATURE.TABLE_OPERATION] The feature is not supported: Table `unknown` does not support UPDATE TABLE. Please check the current catalog and namespace to make sure the qualified table name 

=== 4. Parquet folder: no schema check on append ===
append with different column types succeeded; files: 4
reading back fails:
   [FAILED_READ_FILE.PARQUET_COLUMN_DATA_TYPE_MISMATCH] Encountered error while reading file <file> Data type mismatches when reading Parquet column [customer_id]. Expected Spark type int, actual Parquet
   [customer_id], physicalType: BINARY, logicalType: int

=== 5. Delta table: the same append is rejected ===
AnalysisException: [DELTA_FAILED_TO_MERGE_FIELDS] Failed to merge fields 'customer_id' and 'customer_id'
```

Read the result line by line. The failed Parquet overwrite left an **empty folder**: the three good rows were deleted before the new write started, and the new write never finished. The same failure on Delta changed nothing: the table still has 3 rows and still has only one commit, `00000000000000000000.json`, because a Delta write only becomes visible when its commit file is written, and the failed job never got that far. Parquet has no `UPDATE`. Parquet happily accepted a file with `customer_id` as a string, and the folder became unreadable; Delta rejected the same append before writing anything.

Delta Lake exists to fix exactly these problems. The official description: Delta Lake "extends Parquet data files with a file-based transaction log for ACID transactions and scalable metadata handling" ([What is Delta Lake in Databricks?](https://docs.databricks.com/aws/en/delta/)).

!!! tip "In the interview"
    **"Why not just store Parquet files in S3?"** Plain Parquet folders have no transactions: a failed or concurrent write can leave partial results, an overwrite deletes data before the new data is safe, there is no row-level `UPDATE`/`DELETE`/`MERGE`, and nothing checks the schema of new files. Delta keeps the same Parquet files but adds a transaction log that makes every write atomic, enforces the schema, and records versions you can query later.

## 4.2 What a Delta table is: data files plus a transaction log
*Level: beginner.*

A Delta table is a folder that holds two things:

1. **Data files**: ordinary Parquet files, usually named `part-...snappy.parquet`.
2. **The transaction log**: a subfolder named `_delta_log`. Each change to the table is a **commit**, written as one JSON file named with the version number padded to 20 digits: `00000000000000000000.json` is version 0, `00000000000000000001.json` is version 1, and so on.

The log, not the folder listing, is the truth about what the table contains. A Parquet file sitting in the folder is part of the table only if the log says so. The Delta protocol states it directly: readers "only see one consistent snapshot of a table at time by using the transaction log to selectively choose which data files to process" ([Delta Transaction Log Protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md)).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="A Delta table folder holds Parquet data files and a _delta_log folder of numbered JSON commits, a Parquet checkpoint and a _last_checkpoint file. The log entries point at the data files.">
<rect x="10" y="10" width="620" height="280" rx="8" fill="none" stroke="currentColor" stroke-width="1.5"/>
<text x="24" y="34" font-size="15" font-weight="bold" fill="currentColor">orders/  (the table folder in cloud storage)</text>
<text x="24" y="62" font-size="14" fill="currentColor">Data files (Parquet)</text>
<rect x="24" y="74" width="250" height="34" rx="4" fill="none" stroke="currentColor"/>
<text x="34" y="96" font-size="13" fill="currentColor">part-00000-7638...parquet</text>
<rect x="24" y="116" width="250" height="34" rx="4" fill="none" stroke="currentColor"/>
<text x="34" y="138" font-size="13" fill="currentColor">part-00001-b031...parquet</text>
<rect x="24" y="158" width="250" height="34" rx="4" fill="none" stroke="currentColor"/>
<text x="34" y="180" font-size="13" fill="currentColor">part-00000-fab0...parquet</text>
<text x="24" y="222" font-size="13" fill="currentColor">Files stay on disk after they leave the</text>
<text x="24" y="240" font-size="13" fill="currentColor">table, until VACUUM deletes them.</text>
<rect x="340" y="48" width="276" height="226" rx="6" fill="none" stroke="currentColor" stroke-width="1.5"/>
<text x="354" y="70" font-size="14" font-weight="bold" fill="currentColor">_delta_log/  (transaction log)</text>
<text x="354" y="96" font-size="13" fill="currentColor">00000000000000000000.json  v0</text>
<text x="354" y="118" font-size="13" fill="currentColor">00000000000000000001.json  v1</text>
<text x="354" y="140" font-size="13" fill="currentColor">...</text>
<text x="354" y="162" font-size="13" fill="currentColor">00000000000000000010.json  v10</text>
<text x="354" y="184" font-size="13" fill="currentColor">...00010.checkpoint.parquet  v10</text>
<text x="354" y="206" font-size="13" fill="currentColor">00000000000000000011.json  v11</text>
<text x="354" y="228" font-size="13" fill="currentColor">_last_checkpoint</text>
<text x="354" y="256" font-size="13" fill="currentColor">(.crc checksum file per version)</text>
<line x1="340" y1="110" x2="280" y2="92" stroke="currentColor" stroke-width="1.2"/>
<line x1="340" y1="114" x2="280" y2="134" stroke="currentColor" stroke-width="1.2"/>
<polygon points="280,92 290,90 287,98" fill="currentColor"/>
<polygon points="280,134 289,130 289,138" fill="currentColor"/>
<text x="286" y="60" font-size="13" fill="currentColor">add</text>
</svg>
<figcaption>Figure 4.1. A Delta table is a folder of ordinary Parquet data files plus a <code>_delta_log</code> folder. Each numbered JSON file is one commit (one table version); its <code>add</code> and <code>remove</code> actions say which data files belong to the table. File names are shortened from the run in section 4.2 (the third file is the copy written by the <code>UPDATE</code>).</figcaption>
</figure>

### Looking inside a real `_delta_log`

The script below creates an `orders` table, inserts twice and updates one row: four commits, versions 0 to 3.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE orders (
  order_id INT, customer_id INT, order_ts TIMESTAMP,
  status STRING, amount DECIMAL(10,2), currency STRING)
USING DELTA;                                                     -- version 0
INSERT INTO orders VALUES
  (1001, 7, TIMESTAMP'2026-03-01 10:15:00', 'PLACED', 59.90, 'CAD'),
  (1002, 3, TIMESTAMP'2026-03-01 11:02:00', 'PLACED', 120.00, 'CAD');  -- version 1
INSERT INTO orders VALUES
  (1003, 7, TIMESTAMP'2026-03-02 09:40:00', 'PLACED', 15.50, 'CAD');   -- version 2
UPDATE orders SET status = 'SHIPPED' WHERE order_id = 1001;            -- version 3
```

The table folder afterwards (from `ch04_02_delta_log.out`):

```text
  part-00000-763838d5-e8db-47fd-9ae2-5a70e6df9aed-c000.snappy.parquet
  part-00000-7d485e09-087b-4c5e-8cd5-656b15a1ae55-c000.snappy.parquet
  part-00000-fab00414-18e1-4695-8dad-04e1b46e6ca3-c000.snappy.parquet
  part-00001-b0312ec0-67ab-4ca8-8609-24e104698a72-c000.snappy.parquet
  _delta_log/00000000000000000000.crc
  _delta_log/00000000000000000000.json
  _delta_log/00000000000000000001.crc
  _delta_log/00000000000000000001.json
  _delta_log/00000000000000000002.crc
  _delta_log/00000000000000000002.json
  _delta_log/00000000000000000003.crc
  _delta_log/00000000000000000003.json
```

Four data files for three rows. Version 1 wrote two files (Spark used two tasks), version 2 wrote one, and the `UPDATE` wrote a fourth: a new copy of the file that held order 1001. The old file is still on disk. Each version also has a `.crc` file, a version checksum file that the protocol describes as optional table-state metrics written after the commit; readers must keep working without it.

Each commit file is newline-delimited JSON: one **action** per line. Here are versions 0, 1 and 3 from the same run (the script keeps only the main fields, trims long lines, and replaces the table `id` and the deletion timestamp with placeholders):

```text
--- _delta_log/00000000000000000000.json ---
{"commitInfo": {"operation": "CREATE TABLE", "operationParameters": {"partitionBy": "[]", "clusterBy": "[]", "description": null, "isManaged": "true", "properties": "{}"}, "isBlindAppend": true, "operationMetrics": {}}}
{"metaData": {"id": "<uuid>", "format": {"provider": "parquet", "options": {}}, "schemaString": "{\"type\":\"struct\",\"fields\":[{\"name\":\"order_id\",\"type\":\"integer\",\"nullable\":true,\"metadata\":{}},{\"name\":\"customer_id\",\"type\":\"integer\",\"nullable\":true,\"metadata\":{}},{\"name\":\"order_ts\",\"type\":\"timestamp\",\"nullable\":true,\"metadata\":{}},{\"name\":\"status\",\"type\":\"string\",\"nullable\":true,\"metadata\":{}},{\"name\":\"amount\",\"type\":\"decimal(10,2)\",\"nullable\":true,\"metadata\":{}},{\"name\":\"currency\",\"type\":\"string\",\"nullable\":true,\"metada
{"protocol": {"minReaderVersion": 1, "minWriterVersion": 2}}

--- _delta_log/00000000000000000001.json ---
{"commitInfo": {"operation": "WRITE", "operationParameters": {"mode": "Append", "partitionBy": "[]"}, "readVersion": 0, "isBlindAppend": true, "operationMetrics": {"numFiles": "2", "numOutputRows": "2", "numOutputBytes": "3576"}}}
{"add": {"path": "part-00000-763838d5-e8db-47fd-9ae2-5a70e6df9aed-c000.snappy.parquet", "size": 1788, "dataChange": true, "stats": "{\"numRecords\":1,\"minValues\":{\"order_id\":1001,\"customer_id\":7,\"order_ts\":\"2026-03-01T10:15:00.000Z\",\"status\":\"PLACED\",\"amount\":59.90,\"currency\":\"CAD\"},\"maxValues\":{\"order_id\":1001,\"customer_id\":7,\"order_ts\":\"2026-03-01T10:15:00.000Z\",\"status\":\"PLACED\",\"amount\":59.90,\"currency\":\"CAD\"},\"nullCount\":{\"order_id\":0,\"customer_id\":0,\"order_ts\":0,\"status\":0,\"amount\":0,\"currency\":0}}"}}
{"add": {"path": "part-00001-b0312ec0-67ab-4ca8-8609-24e104698a72-c000.snappy.parquet", "size": 1788, "dataChange": true, "stats": "{\"numRecords\":1,\"minValues\":{\"order_id\":1002,\"customer_id\":3,\"order_ts\":\"2026-03-01T11:02:00.000Z\",\"status\":\"PLACED\",\"amount\":120.00,\"currency\":\"CAD\"},\"maxValues\":{\"order_id\":1002,\"customer_id\":3,\"order_ts\":\"2026-03-01T11:02:00.000Z\",\"status\":\"PLACED\",\"amount\":120.00,\"currency\":\"CAD\"},\"nullCount\":{\"order_id\":0,\"customer_id\":0,\"order_ts\":0,\"status\":0,\"amount\":0,\"currency\":0}}"}}

--- _delta_log/00000000000000000003.json ---
{"commitInfo": {"operation": "UPDATE", "operationParameters": {"predicate": "[\"(order_id#398 = 1001)\"]"}, "readVersion": 2, "isBlindAppend": false, "operationMetrics": {"numRemovedFiles": "1", "numRemovedBytes": "1788", "numCopiedRows": "0", "numDeletionVectorsAdded": "0", "executionTimeMs": "32001", "numDeletionVectorsUpdated": "0", "scanTimeMs": "30611", "numAddedFiles": "1", "numUpdatedRows": "1", "numDeletionVectorsRemoved": "0", "numAddedChangeFiles": "0", "numAddedBytes": "1795", "rewriteTimeMs": "1388"}}}
{"add": {"path": "part-00000-fab00414-18e1-4695-8dad-04e1b46e6ca3-c000.snappy.parquet", "size": 1795, "dataChange": true, "stats": "{\"numRecords\":1,\"minValues\":{\"order_id\":1001,\"customer_id\":7,\"order_ts\":\"2026-03-01T10:15:00.000Z\",\"status\":\"SHIPPED\",\"amount\":59.90,\"currency\":\"CAD\"},\"maxValues\":{\"order_id\":1001,\"customer_id\":7,\"order_ts\":\"2026-03-01T10:15:00.000Z\",\"status\":\"SHIPPED\",\"amount\":59.90,\"currency\":\"CAD\"},\"nullCount\":{\"order_id\":0,\"customer_id\":0,\"order_ts\":0,\"status\":0,\"amount\":0,\"currency\":0}}"}}
{"remove": {"path": "part-00000-763838d5-e8db-47fd-9ae2-5a70e6df9aed-c000.snappy.parquet", "dataChange": true, "deletionTimestamp": "<epoch ms>"}}
```

The five action types you see most often:

| Action | What it records | Seen in |
| --- | --- | --- |
| `protocol` | The minimum reader and writer versions (and table features) a client needs to use the table | version 0 here: `minReaderVersion` 1, `minWriterVersion` 2 |
| `metaData` | The schema (as a JSON string), partition columns, table properties (`configuration`), the table id | version 0; any later schema or property change writes a new one |
| `add` | A data file that is now part of the table, with its size, `dataChange` flag and column statistics (`numRecords`, min, max, null counts) | every write |
| `remove` | A data file that is no longer part of the table, with a deletion timestamp | `UPDATE`, `DELETE`, `MERGE`, overwrite, `OPTIMIZE` |
| `commitInfo` | Who/what/when: the operation (`WRITE`, `UPDATE`, ...), its parameters, the version it read (`readVersion`), whether it was a blind append, and operation metrics | every commit; this is what `DESCRIBE HISTORY` shows |

Three details are worth noticing in the real output:

- The `UPDATE` (version 3) did not edit a file. It **added** a new file holding the changed row and **removed** the old file. This "copy-on-write" rewrite is how Delta changes rows unless deletion vectors are enabled (section 4.9).
- The `stats` inside each `add` hold min and max values per column. Readers use them to skip files that cannot match a filter (data skipping, chapter 22) without opening the files.
- `commitInfo` of version 3 has `"readVersion": 2` and `"isBlindAppend": false`: the update read version 2 before writing. Version 1 has `"isBlindAppend": true`: an insert that did not read the table. This difference matters for concurrency (section 4.5).

### Snapshots and checkpoints

The state of the table at a version is called a **snapshot**. To build it, a reader replays the actions in version order. The protocol's reconciliation rules: the latest `protocol` and latest `metaData` win, and the live files are the `add` actions not cancelled by a later `remove`. Removed files stay in the snapshot as **tombstones**, which "only exist for the benefit of the VACUUM command"; queries read only the `add` actions ([Delta Transaction Log Protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md)).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Four commits v0 to v3, each a list of actions. Replaying them in order gives the snapshot at version 3: the latest protocol and metadata plus the files added and not later removed.">
<g font-size="13" fill="currentColor">
<rect x="10" y="20" width="145" height="128" rx="6" fill="none" stroke="currentColor"/>
<text x="20" y="40" font-weight="bold">v0  CREATE TABLE</text>
<text x="20" y="62">commitInfo</text>
<text x="20" y="82">metaData (schema)</text>
<text x="20" y="102">protocol (1, 2)</text>
<rect x="165" y="20" width="145" height="128" rx="6" fill="none" stroke="currentColor"/>
<text x="175" y="40" font-weight="bold">v1  WRITE</text>
<text x="175" y="62">commitInfo</text>
<text x="175" y="82">add  file A</text>
<text x="175" y="102">add  file B</text>
<rect x="320" y="20" width="145" height="128" rx="6" fill="none" stroke="currentColor"/>
<text x="330" y="40" font-weight="bold">v2  WRITE</text>
<text x="330" y="62">commitInfo</text>
<text x="330" y="82">add  file C</text>
<rect x="475" y="20" width="155" height="128" rx="6" fill="none" stroke="currentColor"/>
<text x="485" y="40" font-weight="bold">v3  UPDATE</text>
<text x="485" y="62">commitInfo</text>
<text x="485" y="82">add     file D</text>
<text x="485" y="102">remove  file A</text>
<text x="485" y="124">(D = A with the new</text>
<text x="485" y="140">status value)</text>
</g>
<line x1="155" y1="84" x2="165" y2="84" stroke="currentColor"/>
<line x1="310" y1="84" x2="320" y2="84" stroke="currentColor"/>
<line x1="465" y1="84" x2="475" y2="84" stroke="currentColor"/>
<line x1="320" y1="158" x2="320" y2="186" stroke="currentColor" stroke-width="1.5"/>
<polygon points="314,180 326,180 320,190" fill="currentColor"/>
<text x="330" y="178" font-size="13" fill="currentColor">replay in version order</text>
<rect x="60" y="196" width="520" height="92" rx="6" fill="none" stroke="currentColor" stroke-width="1.5"/>
<g font-size="13" fill="currentColor">
<text x="74" y="218" font-weight="bold">Snapshot at version 3</text>
<text x="74" y="240">protocol: latest seen (1, 2)     metaData: latest seen (the schema)</text>
<text x="74" y="260">live files: A, B, C, D minus removed A  =  B, C, D</text>
<text x="74" y="280">tombstone: A (kept for VACUUM and time travel, not read by queries)</text>
</g>
</svg>
<figcaption>Figure 4.2. Snapshot reconstruction. A reader replays the commits (or starts from the newest checkpoint and replays only the later commits): the latest <code>protocol</code> and <code>metaData</code> win, and the live files are every <code>add</code> not cancelled by a later <code>remove</code>.</figcaption>
</figure>

Replaying thousands of small JSON files would get slow, so Delta periodically writes a **checkpoint**: a Parquet file that holds the complete reconciled state at one version. A reader starts from the newest checkpoint and replays only the commits after it. The file `_last_checkpoint` points to the newest checkpoint so readers do not have to list the folder. After 8 more small inserts in the same script:

```text
files in _delta_log:
  00000000000000000000.crc
  00000000000000000000.json
  00000000000000000001.crc
  00000000000000000001.json
  00000000000000000002.crc
  00000000000000000002.json
  00000000000000000003.crc
  00000000000000000003.json
  00000000000000000004.crc
  00000000000000000004.json
  00000000000000000005.crc
  00000000000000000005.json
  00000000000000000006.crc
  00000000000000000006.json
  00000000000000000007.crc
  00000000000000000007.json
  00000000000000000008.crc
  00000000000000000008.json
  00000000000000000009.crc
  00000000000000000009.json
  00000000000000000010.checkpoint.parquet
  00000000000000000010.crc
  00000000000000000010.json
  00000000000000000011.crc
  00000000000000000011.json
  _last_checkpoint
  _staged_commits

_last_checkpoint: {"version":10,"size":13,"sizeInBytes":27143,"numOfAddFiles":10,"checkpointSchema":{"type":"struct","fields":[{"name":"txn","type":{"type":"struct","fields":[{"name":"appId","type":"string","nullable":

=== What the checkpoint 00000000000000000010.checkpoint.parquet holds (one row per action) ===
+--------+-----+
|  action|count|
+--------+-----+
|     add|   10|
|metaData|    1|
|protocol|    1|
|  remove|    1|
+--------+-----+
```

In this open-source run the checkpoint appeared at version 10 (the open-source default interval was not verified from documentation; this is only what the run did). On Databricks you should not rely on any interval: "Databricks optimizes checkpointing frequency for data size and workload. The checkpoint frequency is subject to change without notice" ([Work with table history](https://docs.databricks.com/aws/en/tables/history)). The empty `_staged_commits` folder belongs to the catalog-managed commit mechanism in the newer protocol (section 4.10); you never touch it. (Why Delta 4.4.1 creates it for an ordinary table: not verified.)

!!! warning "Never edit the files of a Delta table by hand"
    Do not delete, copy in or rewrite Parquet files or log files in a Delta folder with storage tools. The log would point at files that are gone, or ignore files you added. Databricks says to "avoid interacting directly with data and transaction log files in Delta Lake file directories" ([What is Delta Lake in Databricks?](https://docs.databricks.com/aws/en/delta/)) and not to use `rm -rf` to drop a Delta table ([Delta Lake limitations on S3](https://docs.databricks.com/aws/en/delta/s3-limitations)). Use `DROP TABLE`, `DELETE`, `VACUUM`.

!!! tip "In the interview"
    **"What is in `_delta_log`?"** Numbered JSON commit files, one per table version, each listing actions: `add` and `remove` for data files, `metaData` for schema and properties, `protocol` for required client features, `commitInfo` for the operation and metrics. Periodically a Parquet checkpoint stores the full state so readers do not replay every JSON file, and `_last_checkpoint` points to it. A snapshot is the replay of these actions; the live files are the adds not cancelled by later removes.

## 4.3 Reading and writing Delta tables
*Level: beginner.*

You use Delta through the normal Spark SQL and DataFrame APIs. There are two ways to name a table:

- **By name**, through the catalog: `shop.silver.orders` on Databricks with Unity Catalog, or a one-part name locally.
- **By path**: the storage folder itself, as ``delta.`/path/to/table` `` in SQL or `.format("delta").load(path)` in PySpark.

On Databricks, path-based access has limits: "To access Unity Catalog managed tables, use a fully-qualified table name. Path-based access is only supported for volumes and external tables, not for managed tables" ([Tutorial: Create and manage Delta Lake tables](https://docs.databricks.com/aws/en/delta/tutorial)). In practice, use names.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
# Named table (on Databricks, .format("delta") is the default and can be left out)
products.write.format("delta").mode("overwrite").saveAsTable("products")
# Path only, no catalog entry
products.write.format("delta").mode("overwrite").save(ext_path)

spark.sql("SELECT * FROM products ORDER BY product_id").show()
spark.read.format("delta").load(ext_path).count()
spark.sql(f"SELECT count(*) AS n FROM delta.`{ext_path}`").show()

# Register an existing Delta folder under a name: an external table
spark.sql(f"CREATE TABLE products_ext USING DELTA LOCATION '{ext_path}'")

# Append, forgetting format("delta") first
more.write.mode("append").saveAsTable("products")
more.write.format("delta").mode("append").saveAsTable("products")
```

```text
>>> SELECT * FROM products ORDER BY product_id
+----------+-------------+--------+------+
|product_id|name         |category|price |
+----------+-------------+--------+------+
|1         |Trail Tent 2P|camping |249.00|
|2         |Headlamp 300 |lighting|39.95 |
|3         |Merino Socks |clothing|29.95 |
+----------+-------------+--------+------+

read by path with PySpark: 3 rows
>>> SELECT count(*) AS n FROM delta.`<work>/lake/products`
+---+
|  n|
+---+
|  3|
+---+

>>> CREATE TABLE products_ext USING DELTA LOCATION '<work>/lake/products'
>>> SELECT name, price FROM products_ext WHERE category = 'lighting'
+------------+-----+
|name        |price|
+------------+-----+
|Headlamp 300|39.95|
+------------+-----+

append WITHOUT format('delta') (open-source Spark's default source is Parquet):
  AnalysisException: The format of the existing table spark_catalog.default.products is `DeltaDataSource`. It doesn't match the specified format `ParquetDataSourceV2`.
>>> SELECT count(*) AS after_append FROM products
+------------+
|after_append|
+------------+
|4           |
+------------+
```

The failed append is a real open-source gotcha: Spark's default data source is Parquet, so `saveAsTable` without `.format("delta")` asks for a Parquet table and clashes with the existing Delta table. On Databricks Delta is the default format, so the same line works there ([What is Delta Lake in Databricks?](https://docs.databricks.com/aws/en/delta/)).

SQL has the same verbs as any warehouse: `CREATE TABLE ... AS SELECT` (CTAS), `INSERT INTO`, `INSERT OVERWRITE`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE camping_products USING DELTA AS
SELECT * FROM products WHERE category = 'camping';
INSERT OVERWRITE camping_products
SELECT * FROM products WHERE category = 'camping' AND price < 100;
```

```text
>>> SELECT product_id, name FROM camping_products ORDER BY product_id
+----------+-------------+
|product_id|name         |
+----------+-------------+
|1         |Trail Tent 2P|
|4         |Water Filter |
+----------+-------------+

>>> SELECT product_id, name FROM camping_products ORDER BY product_id
+----------+------------+
|product_id|name        |
+----------+------------+
|4         |Water Filter|
+----------+------------+
```

For operations that are awkward as DataFrame writes, Python has the `DeltaTable` class (`delta.tables.DeltaTable`, `forName` or `forPath`) with `update`, `delete`, `merge`, `history`, `optimize`, `vacuum` and more. The Databricks docs point to the open-source Delta Lake API documentation for it ([What is Delta Lake in Databricks?](https://docs.databricks.com/aws/en/delta/)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from delta.tables import DeltaTable
dt = DeltaTable.forName(spark, "products")
dt.update(condition="product_id = 2", set={"price": "35.00"})
dt.toDF().orderBy("product_id").show()
```

```text
+----------+-------------+--------+------+
|product_id|         name|category| price|
+----------+-------------+--------+------+
|         1|Trail Tent 2P| camping|249.00|
|         2| Headlamp 300|lighting| 35.00|
|         3| Merino Socks|clothing| 29.95|
|         4| Water Filter| camping| 59.00|
+----------+-------------+--------+------+
```

### Managed and external tables, in one paragraph

`products` above is a **managed** table: the catalog chose its location and owns its files. `products_ext` is an **external** table: you gave the location, and dropping the table removes only the catalog entry, not the files. On Databricks, Unity Catalog managed tables are "the default and recommended table type", and some features exist only for them, such as predictive optimization and catalog commits ([Unity Catalog managed tables for Delta Lake and Apache Iceberg](https://docs.databricks.com/aws/en/tables/managed)). For external tables, Unity Catalog manages metadata but "doesn't manage the data's lifecycle, optimization, storage location, or layout" ([Work with external tables](https://docs.databricks.com/aws/en/tables/external)). Chapter 5 covers both in depth.

```text
>>> DESCRIBE DETAIL products  -- columns: format, name, numFiles, minReaderVersion, minWriterVersion
+------+------------------------------+--------+----------------+----------------+
|format|name                          |numFiles|minReaderVersion|minWriterVersion|
+------+------------------------------+--------+----------------+----------------+
|delta |spark_catalog.default.products|3       |1               |2               |
+------+------------------------------+--------+----------------+----------------+

products: Type = MANAGED
products_ext: Type = EXTERNAL
```

## 4.4 UPDATE, DELETE and MERGE
*Level: beginner.*

The SQL is standard (see [the SQL course](../../databases/sql/17-Insert-Update-Delete-Merge.md)). What is different is what happens underneath: each statement is one atomic commit, and changed rows are written to new files while the old files are marked `remove` in the log (unless deletion vectors are on, section 4.9).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE orders (order_id INT, customer_id INT, status STRING, amount DECIMAL(10,2))
USING DELTA;                                                                -- v0
INSERT INTO orders VALUES (1001, 7, 'PLACED', 59.90), (1002, 3, 'PLACED', 120.00),
                          (1003, 7, 'PLACED', 15.50), (1004, 9, 'PLACED', 42.00);  -- v1
UPDATE orders SET status = 'SHIPPED' WHERE order_id IN (1001, 1002);        -- v2
DELETE FROM orders WHERE order_id = 1004;                                   -- v3

CREATE OR REPLACE TEMP VIEW order_updates AS
SELECT * FROM VALUES (1003, 7, 'CANCELLED', 15.50), (1005, 2, 'PLACED', 88.00)
  AS s(order_id, customer_id, status, amount);

MERGE INTO orders AS t
USING order_updates AS s
ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET t.status = s.status
WHEN NOT MATCHED THEN INSERT *;                                             -- v4
```

```text
>>> SELECT * FROM orders ORDER BY order_id
+--------+-----------+---------+------+
|order_id|customer_id|status   |amount|
+--------+-----------+---------+------+
|1001    |7          |SHIPPED  |59.90 |
|1002    |3          |SHIPPED  |120.00|
|1003    |7          |CANCELLED|15.50 |
|1005    |2          |PLACED   |88.00 |
+--------+-----------+---------+------+

>>> DESCRIBE HISTORY orders  -- columns: version, operation, operationMetrics.numOutputRows, operationMetrics.numUpdatedRows, operationMetrics.numDeletedRows, operationMetrics.numTargetRowsInserted
+-------+------------+-------------+--------------+--------------+---------------------+
|version|operation   |numOutputRows|numUpdatedRows|numDeletedRows|numTargetRowsInserted|
+-------+------------+-------------+--------------+--------------+---------------------+
|0      |CREATE TABLE|NULL         |NULL          |NULL          |NULL                 |
|1      |WRITE       |4            |NULL          |NULL          |NULL                 |
|2      |UPDATE      |NULL         |2             |NULL          |NULL                 |
|3      |DELETE      |NULL         |NULL          |1             |NULL                 |
|4      |MERGE       |2            |NULL          |NULL          |1                    |
+-------+------------+-------------+--------------+--------------+---------------------+
```

`MERGE` matched order 1003 (updated to `CANCELLED`) and inserted the new order 1005, in one commit. The operation metrics come straight from each commit's `commitInfo`. `MERGE` is the workhorse of silver and gold layers: deduplication, upserts, SCD Type 2 and `WHEN NOT MATCHED BY SOURCE` are covered in [chapter 9](09-Building-Silver.md) and chapter 20.

The same three statements in PySpark, with the `DeltaTable` API (a fresh copy of the table in `ch04_11_deltatable_api.py`, starting from the same four rows):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from delta.tables import DeltaTable
from pyspark.sql import functions as F

dt = DeltaTable.forName(spark, "orders")
dt.update(condition=F.col("order_id").isin(1001, 1002), set={"status": F.lit("SHIPPED")})
dt.delete(F.col("order_id") == 1004)
(dt.alias("t")
   .merge(updates.alias("s"), "t.order_id = s.order_id")
   .whenMatchedUpdate(set={"status": "s.status"})
   .whenNotMatchedInsertAll()
   .execute())
dt.toDF().orderBy("order_id").show()
```

```text
+--------+-----------+---------+------+
|order_id|customer_id|   status|amount|
+--------+-----------+---------+------+
|    1001|          7|  SHIPPED| 59.90|
|    1002|          3|  SHIPPED|120.00|
|    1003|          7|CANCELLED| 15.50|
|    1005|          2|   PLACED| 88.00|
+--------+-----------+---------+------+
```

Same result: the API writes the same kind of `UPDATE`, `DELETE` and `MERGE` commits to the log.

!!! warning "A MERGE source with duplicate keys"
    If more than one source row matches the same target row, `MERGE` fails with `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`, because the update is ambiguous ([`MERGE INTO`](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into)). Deduplicate the source first. Chapter 9 shows the error and the fix.

## 4.5 ACID transactions and optimistic concurrency
*Level: intermediate.*

ACID is four promises a transaction makes. Databricks defines them for Delta tables like this ([What are ACID guarantees on Databricks?](https://docs.databricks.com/aws/en/lakehouse/acid)):

| Letter | Meaning | How Delta delivers it |
| --- | --- | --- |
| **A**tomicity | "all transactions either succeed or fail completely." | Data files are written first; the commit file is written last. Files from a failed transaction are never referenced by the log, so they "will not corrupt the table state". |
| **C**onsistency | How simultaneous operations observe the data | Optimistic concurrency control: every commit is validated against commits that happened since it read the table. |
| **I**solation | How simultaneous operations may conflict | Snapshot isolation for reads, write-serializable isolation for writes (both defaults). |
| **D**urability | Committed changes are permanent | Data and log live in cloud object storage and inherit its durability. |

### Scope of a transaction

"By default, each SQL statement executes as its own atomic transaction against one table." Databricks can also group statements across tables with `BEGIN ATOMIC ... END;`, but only for tables with catalog commits enabled ([What are ACID guarantees on Databricks?](https://docs.databricks.com/aws/en/lakehouse/acid)); catalog commits are a Unity Catalog managed table feature (section 4.10). Outside that, an `INSERT` into silver and an `INSERT` into gold in the same notebook are two separate transactions: one can succeed while the other fails.

### Optimistic concurrency, step by step

Delta takes no locks. Databricks describes three stages for every write ([What are ACID guarantees on Databricks?](https://docs.databricks.com/aws/en/lakehouse/acid)):

1. **Read**: read the latest table version to find which files must be rewritten. Append-only writes skip this.
2. **Write**: write the new data files into the table folder. Nobody sees them yet.
3. **Validate and commit**: check whether anything committed since the snapshot conflicts with this change. If not, commit the next version. If yes, fail with a concurrent modification exception.

The commit itself relies on one rule from the protocol: "Writers MUST never overwrite an existing log entry", using atomic primitives of the storage system where possible ([Delta Transaction Log Protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md)). If writers A and B both try to create version 6, only one succeeds. The other sees that version 6 exists, reads what it changed, and decides: no overlap, so retry the commit as version 7; overlap, so fail. On S3, Databricks picks the commit mechanism for you, and external writers "must use atomic S3 conditional writes or an equivalent commit mechanism compatible with every writer" ([Delta Lake limitations on S3](https://docs.databricks.com/aws/en/delta/s3-limitations)).

"Optimistic" means the writer assumes it will not collide and only checks at the end. There are no locks, so "deadlock is not a possibility" ([What are ACID guarantees on Databricks?](https://docs.databricks.com/aws/en/lakehouse/acid)). The price is that a writer can do all its work and then fail at commit time, so production jobs need retries.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 270" role="img" aria-label="Two writers read version 5 at the same time. Writer A commits version 6 first. Writer B finds version 6 already exists, checks whether A's changes conflict with what B read, then either commits as version 7 or fails with a concurrent modification exception.">
<g font-size="13" fill="currentColor">
<text x="10" y="56" font-weight="bold">Writer A</text>
<text x="10" y="176" font-weight="bold">Writer B</text>
<line x1="80" y1="52" x2="620" y2="52" stroke="currentColor"/>
<line x1="80" y1="172" x2="620" y2="172" stroke="currentColor"/>
<rect x="90" y="32" width="110" height="40" rx="4" fill="none" stroke="currentColor"/>
<text x="100" y="50">1. read v5</text>
<text x="100" y="66">(snapshot)</text>
<rect x="215" y="32" width="130" height="40" rx="4" fill="none" stroke="currentColor"/>
<text x="225" y="50">2. write new</text>
<text x="225" y="66">Parquet files</text>
<rect x="360" y="32" width="150" height="40" rx="4" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="370" y="50">3. commit: create</text>
<text x="370" y="66">..006.json  OK</text>
<rect x="90" y="152" width="110" height="40" rx="4" fill="none" stroke="currentColor"/>
<text x="100" y="170">1. read v5</text>
<text x="100" y="186">(snapshot)</text>
<rect x="215" y="152" width="130" height="40" rx="4" fill="none" stroke="currentColor"/>
<text x="225" y="170">2. write new</text>
<text x="225" y="186">Parquet files</text>
<rect x="360" y="152" width="150" height="40" rx="4" fill="none" stroke="currentColor"/>
<text x="370" y="170">3. ..006.json exists:</text>
<text x="370" y="186">check A's changes</text>
<line x1="435" y1="72" x2="435" y2="148" stroke="currentColor" stroke-dasharray="4 3"/>
<text x="442" y="114">v6 already taken</text>
<line x1="510" y1="165" x2="540" y2="140" stroke="currentColor"/>
<line x1="510" y1="180" x2="540" y2="210" stroke="currentColor"/>
<text x="545" y="138">no conflict:</text>
<text x="545" y="154">commit as v7</text>
<text x="545" y="214">conflict:</text>
<text x="545" y="230">exception,</text>
<text x="545" y="246">retry the job</text>
</g>
</svg>
<figcaption>Figure 4.3. Optimistic concurrency. Nobody takes a lock. Each writer reads a snapshot, writes its files, and then tries to commit the next version number. Only one writer can create a given commit file; the loser checks whether the winner's changes touch what it read, then commits at the next version or fails.</figcaption>
</figure>

### Two writers on a real table

The script starts two statements at the same instant from two threads, first two blind `INSERT`s, then two `UPDATE`s of different rows that live in the same data file (the table was compacted to one file first).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
race("Two blind appends",
     "INSERT INTO orders VALUES (2001, 'PLACED')",
     "INSERT INTO orders VALUES (2002, 'PLACED')")
race("Two UPDATEs of different rows that live in the same file",
     "UPDATE orders SET status = 'SHIPPED' WHERE order_id = 1001",
     "UPDATE orders SET status = 'CANCELLED' WHERE order_id = 1002")
```

```text
--- Two blind appends ---
  A: INSERT INTO orders VALUES (2001, 'PLACED')
     -> committed
  B: INSERT INTO orders VALUES (2002, 'PLACED')
     -> committed
--- Two UPDATEs of different rows that live in the same file ---
  A: UPDATE orders SET status = 'SHIPPED' WHERE order_id = 1001
     -> FAILED: io.delta.exceptions.ConcurrentAppendException
  B: UPDATE orders SET status = 'CANCELLED' WHERE order_id = 1002
     -> committed
>>> SELECT * FROM orders ORDER BY order_id
+--------+---------+
|order_id|status   |
+--------+---------+
|1001    |PLACED   |
|1002    |CANCELLED|
|1003    |PLACED   |
|2001    |PLACED   |
|2002    |PLACED   |
+--------+---------+

>>> DESCRIBE HISTORY orders  -- columns: version, operation, readVersion, isolationLevel, isBlindAppend
+-------+------------+-----------+-----------------+-------------+
|version|operation   |readVersion|isolationLevel   |isBlindAppend|
+-------+------------+-----------+-----------------+-------------+
|0      |CREATE TABLE|NULL       |Serializable     |true         |
|1      |WRITE       |0          |Serializable     |true         |
|2      |OPTIMIZE    |1          |SnapshotIsolation|false        |
|3      |WRITE       |2          |Serializable     |true         |
|4      |WRITE       |2          |Serializable     |true         |
|5      |UPDATE      |4          |Serializable     |false        |
+-------+------------+-----------+-----------------+-------------+
```

The two appends both committed: neither read the table, so neither can be invalidated by the other. The history shows it: versions 3 and 4 both have `readVersion` 2, so both started from the same snapshot, and the second simply committed at the next version. The two updates touched different rows, but both had to rewrite the same file. The first to commit won. The second failed with `ConcurrentAppendException`: the winner's commit added a file (its rewritten copy of the data) to an unpartitioned table that the loser had read, so the loser's view of the table was out of date. Its work is lost; the job must retry. (The exact timing of a race depends on the machine; the outcome pattern is what matters.)

Which pairs can conflict is listed in Databricks' conflict matrix ([Row-level concurrency](https://docs.databricks.com/aws/en/optimizations/isolation/row-level-concurrency)). Under the default `WriteSerializable` level, without row-level concurrency:

| Operation pair | Can they conflict? |
| --- | --- |
| `INSERT` + `INSERT` | Cannot conflict |
| `INSERT` + `UPDATE`/`DELETE`/`MERGE` | Cannot conflict (under `Serializable` they can; then the `UPDATE`/`DELETE`/`MERGE` fails, not the `INSERT`) |
| `UPDATE`/`DELETE`/`MERGE` + `UPDATE`/`DELETE`/`MERGE` | Can conflict when they touch the same files |
| `UPDATE`/`DELETE`/`MERGE` + `OPTIMIZE` | Cannot conflict with deletion vectors enabled, unless `ZORDER BY` is used; can conflict otherwise |

"INSERT" here means a blind append; an `INSERT` with a subquery that reads the same table behaves like `MERGE`. Any metadata change (`ALTER TABLE`, a schema change, a protocol upgrade) "might cause all concurrent write operations to fail" ([Isolation levels and write conflicts](https://docs.databricks.com/aws/en/optimizations/isolation/)).

The exceptions you will meet, from the "Conflict exceptions" section of [Row-level concurrency](https://docs.databricks.com/aws/en/optimizations/isolation/row-level-concurrency):

| Exception | Cause |
| --- | --- |
| `ConcurrentAppendException` | Another operation added files in a partition (or anywhere in an unpartitioned table) that your operation read (the run above) |
| `ConcurrentDeleteReadException` | Another operation removed a file your operation read |
| `ConcurrentDeleteDeleteException` | Another operation removed a file your operation also removes, for example two compactions |
| `MetadataChangedException` | Another transaction changed the table metadata (`ALTER TABLE`, schema change) |
| `ConcurrentTransactionException` | Two streaming queries with the same checkpoint location wrote at the same time |
| `ProtocolChangedException` | The protocol was upgraded, or several writers created or replaced the table at once |

How to reduce conflicts: partition or cluster so concurrent jobs touch disjoint files, put explicit partition filters in `MERGE` conditions, and on Databricks use deletion vectors, which enable **row-level concurrency** on Databricks Runtime 14.3 LTS and above for unpartitioned tables: two writes to different rows of the same file no longer conflict ([Row-level concurrency](https://docs.databricks.com/aws/en/optimizations/isolation/row-level-concurrency)). By that page's conflict matrix, the two `UPDATE`s above (different rows) would then not conflict; this was not run here, because row-level concurrency is a Databricks Runtime feature.

### WriteSerializable and Serializable

Databricks supports two isolation levels, set with the table property `delta.isolationLevel` ([Isolation levels (WriteSerializable and Serializable)](https://docs.databricks.com/aws/en/optimizations/isolation/isolation-levels)):

- **WriteSerializable (default on Databricks)**: writes are serializable, reads are not. A long `DELETE` that started before a concurrent `INSERT` can still commit after it; the inserted rows are untouched even if they match the delete condition. The table ends up as if the insert ran after the delete, while the history lists the insert first.
- **Serializable**: the strongest level. In the same scenario the `DELETE` fails with a conflict and must be retried. Blind appends can now conflict too, which lowers write throughput.

Reads always use snapshot isolation: a query sees one consistent version from start to finish, even while other jobs commit.

!!! note "Open-source default differs"
    In the open-source run above, `DESCRIBE HISTORY` recorded `isolationLevel` as `Serializable` for the writes (and `SnapshotIsolation` for `OPTIMIZE`). Databricks documents `WriteSerializable` as its default ([Table properties reference](https://docs.databricks.com/aws/en/tables/table-properties)). This is an observation from the run; the open-source concurrency documentation does not name a default isolation level, so the open-source default is not verified. Know which engine an interviewer is asking about.

!!! tip "In the interview"
    **"Two jobs write to the same Delta table at the same time. What happens?"** Delta uses optimistic concurrency: both read a snapshot and write their files, then race to create the next commit file, which only one can create. The loser checks the winner's commit: if it does not touch what the loser read (two blind appends, for example), the loser commits at the next version; if it does (two updates rewriting the same file), the loser fails with an exception such as `ConcurrentAppendException` or `ConcurrentDeleteReadException` and must retry. The table is never corrupted. To reduce conflicts, make jobs touch disjoint data (partitioning or clustering, explicit filters) and use deletion vectors for row-level concurrency on Databricks.

## 4.6 Schema enforcement and schema evolution
*Level: intermediate.*

**Schema enforcement** (also called schema validation) means a write must match the table's schema or it is rejected. For inserts, Databricks enforces that "all inserted columns must exist in the target table" and that column types match, attempting "to safely cast column data types to match the target table" ([Schema enforcement](https://docs.databricks.com/aws/en/tables/schema-enforcement)). **Schema evolution** is the opposite permission: you explicitly allow a write or a DDL statement to change the schema.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
spark.sql("CREATE TABLE customers (customer_id INT, name STRING, email STRING, city STRING) USING DELTA")
spark.sql("INSERT INTO customers VALUES (7, 'Ana Ruiz', 'ana@example.com', 'Moab')")

spark.sql("INSERT INTO customers (customer_id, phone) VALUES (8, '555-0100')")   # 1
extra.write.format("delta").mode("append").saveAsTable("customers")                # 2: extra column country
wrong.write.format("delta").mode("append").saveAsTable("customers")                # 3: customer_id 'nine'
spark.sql("INSERT INTO t_cast VALUES (1, 42)")                                     # 4: INT into BIGINT
```

```text
1) INSERT naming a column that does not exist:
AnalysisException: [UNRESOLVED_COLUMN.WITH_SUGGESTION] A column, variable, or function parameter with name `phone` cannot be resolved. Did you mean one of the following? [`customer_id`, `name`, `email`, `city`]. SQLSTATE: 42703; line 1 pos 0
2) DataFrame append with an extra column, no mergeSchema:
AnalysisException: [DELTA_METADATA_MISMATCH] A metadata mismatch was detected when writing to the Delta table.
3) Append where a column type cannot be cast safely (STRING into INT):
NumberFormatException: [CAST_INVALID_INPUT] The value 'nine' of the type "STRING" cannot be cast to "INT" because it is malformed. Correct the value as per the syntax, or change its target type. Use `try_cast` to tolerate malformed input and return NULL
4) INSERT of an INT literal into a BIGINT-safe column is cast for you:
OK (no error)
```

Case 3 shows the "safe cast" rule at work: Delta tried to cast the string column to `INT`, and the value `'nine'` failed under ANSI mode. Case 4 is a cast that always works, so it succeeds silently.

### Schema evolution

Databricks lists four ways to let a write change the schema ([Update table schemas with schema evolution](https://docs.databricks.com/aws/en/tables/update-schema)):

- `INSERT WITH SCHEMA EVOLUTION INTO ...` (Databricks Runtime 18.1 and above)
- `MERGE WITH SCHEMA EVOLUTION INTO ...` in SQL (Databricks Runtime 15.4 LTS and above), or `.withSchemaEvolution()` in the `DeltaTable` API
- the `mergeSchema` write option: `.option("mergeSchema", "true")`
- the session setting `spark.databricks.delta.schema.autoMerge.enabled = true` (legacy)

Databricks recommends the per-write forms over the session setting. New columns "are added to the end of the table schema", and existing rows read `NULL` for them.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
extra.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable("customers")
spark.sql("ALTER TABLE customers ADD COLUMNS (updated_at TIMESTAMP COMMENT 'last change' AFTER city)")
```

```text
5) Same append with mergeSchema = true:
>>> SELECT * FROM customers ORDER BY customer_id
+-----------+--------+---------------+---------+-------+
|customer_id|name    |email          |city     |country|
+-----------+--------+---------------+---------+-------+
|7          |Ana Ruiz|ana@example.com|Moab     |NULL   |
|8          |Bo Chen |bo@example.com |Flagstaff|US     |
+-----------+--------+---------------+---------+-------+

6) ALTER TABLE ADD COLUMNS:
>>> SELECT * FROM customers ORDER BY customer_id
+-----------+--------+---------------+---------+----------+-------+
|customer_id|name    |email          |city     |updated_at|country|
+-----------+--------+---------------+---------+----------+-------+
|7          |Ana Ruiz|ana@example.com|Moab     |NULL      |NULL   |
|8          |Bo Chen |bo@example.com |Flagstaff|NULL      |US     |
+-----------+--------+---------------+---------+----------+-------+
```

`mergeSchema` added `country` at the end; `ALTER TABLE ADD COLUMNS` placed `updated_at` where we asked with `AFTER city` (new columns are nullable by default). Neither rewrote any data file: old files simply lack the column and readers fill in `NULL`.

What about the SQL clauses on open-source Spark? A syntax check in the same engine:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
=== 1. INSERT WITH SCHEMA EVOLUTION (Databricks Runtime 18.1+ syntax) ===
>>> INSERT WITH SCHEMA EVOLUTION INTO customers SELECT * FROM incoming WHERE customer_id = 8
OK
=== 2. MERGE WITH SCHEMA EVOLUTION (SQL) ===
>>> MERGE WITH SCHEMA EVOLUTION INTO customers AS t USING incoming AS s ON t.customer_id = s.customer_id WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *
OK
>>> SELECT * FROM customers ORDER BY customer_id
+-----------+--------+---------+
|customer_id|name    |city     |
+-----------+--------+---------+
|7          |Ana Ruiz|Moab     |
|8          |Bo Chen |Flagstaff|
+-----------+--------+---------+

=== 3. MERGE with schema evolution through the Python DeltaTable API ===
>>> SELECT * FROM customers2 ORDER BY customer_id
+-----------+--------+---------+
|customer_id|name    |city     |
+-----------+--------+---------+
|7          |Ana Ruiz|Moab     |
|8          |Bo Chen |Flagstaff|
+-----------+--------+---------+

=== 4. Querying DESCRIBE output as a subquery ===
>>> SELECT version, operation FROM (DESCRIBE HISTORY customers2)
   ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near 'customers2': extra input 'customers2'. SQLSTATE: 42601 (line 1, pos 49)
Open-source alternative: DataFrame methods on the DESCRIBE result
+-------+------------+
|version|operation   |
+-------+------------+
|0      |CREATE TABLE|
|1      |WRITE       |
|2      |MERGE       |
+-------+------------+
```

All three schema evolution forms worked on open-source Spark 4.2 with Delta 4.4.1 (the `INSERT WITH SCHEMA EVOLUTION` clause is listed for Databricks Runtime 18.1 and above on Databricks). The last check shows that open-source Spark does not accept `DESCRIBE HISTORY` as a subquery, which comes up again in section 4.7.

!!! warning "Schema changes and running jobs"
    "Schema updates conflict with all concurrent write operations", and "updating a table schema terminates any streams reading from that table"; you must restart them ([Update table schemas with schema evolution](https://docs.databricks.com/aws/en/tables/update-schema)). Turning on `mergeSchema` everywhere also means a typo in an upstream column name silently becomes a new column. Enable evolution per write, where you expect new columns, typically in bronze.

### Renaming and dropping columns: column mapping

Parquet files store columns by name. Renaming a column would make old files unreadable under the new name, so by default Delta refuses:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
ALTER TABLE customers RENAME COLUMN city TO town;      -- fails
ALTER TABLE customers SET TBLPROPERTIES ('delta.columnMapping.mode' = 'name');
ALTER TABLE customers RENAME COLUMN city TO town;      -- works
ALTER TABLE customers DROP COLUMN email;               -- works
```

```text
7) Rename a column without column mapping:
AnalysisException: [DELTA_UNSUPPORTED_RENAME_COLUMN] Column rename is not supported for your Delta table. 
>>> DESCRIBE DETAIL customers  -- columns: minReaderVersion, minWriterVersion, tableFeatures
+----------------+----------------+------------------------+
|minReaderVersion|minWriterVersion|tableFeatures           |
+----------------+----------------+------------------------+
|1               |2               |[appendOnly, invariants]|
+----------------+----------------+------------------------+

8) Turn on column mapping (name mode), then rename and drop:
>>> DESCRIBE DETAIL customers  -- columns: minReaderVersion, minWriterVersion, tableFeatures
+----------------+----------------+---------------------------------------+
|minReaderVersion|minWriterVersion|tableFeatures                          |
+----------------+----------------+---------------------------------------+
|2               |7               |[appendOnly, columnMapping, invariants]|
+----------------+----------------+---------------------------------------+

>>> SELECT * FROM customers ORDER BY customer_id
+-----------+--------+---------+----------+-------+
|customer_id|name    |town     |updated_at|country|
+-----------+--------+---------+----------+-------+
|7          |Ana Ruiz|Moab     |NULL      |NULL   |
|8          |Bo Chen |Flagstaff|NULL      |US     |
+-----------+--------+---------+----------+-------+

>>> DESCRIBE HISTORY customers  -- columns: version, operation
+-------+-----------------+
|version|operation        |
+-------+-----------------+
|0      |CREATE TABLE     |
|1      |WRITE            |
|2      |WRITE            |
|3      |ADD COLUMNS      |
|4      |SET TBLPROPERTIES|
|5      |RENAME COLUMN    |
|6      |DROP COLUMNS     |
+-------+-----------------+
```

**Column mapping** stores a separate physical name (or id) for each column in the table metadata, so a rename or drop is a metadata-only change. The requirements and modes from [Rename and drop columns with Delta Lake column mapping](https://docs.databricks.com/aws/en/tables/features/column-mapping):

- It needs reader version 2 or above and writer version 5 or above (the run shows the protocol going from 1/2 to 2/7, with `columnMapping` in the table features).
- Modes: `none` (default), `name` (can be set on new and existing tables), `id` (only at table creation). Databricks recommends `id` mode for most cases; `name` mode is set automatically when you enable Iceberg reads.
- Column names may then contain spaces and characters such as `,;{}()=`.
- `DROP COLUMN` does not delete the data in the files. To purge it, run `REORG TABLE ... APPLY (PURGE)` and then `VACUUM`.
- Renames and drops can break streaming reads (use `schemaTrackingLocation`) and downstream change data feed readers.

To change a column's type (beyond what type widening allows, below) or to restructure the table, rewrite it with the `overwriteSchema` option:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
(spark.read.table("t_cast")
   .selectExpr("id", "CAST(amount AS DECIMAL(12,2)) AS amount")
   .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
   .saveAsTable("t_cast"))
```

```text
9) Changing a column type: rewrite with overwriteSchema
+--------+-------------+-------+
|col_name|    data_type|comment|
+--------+-------------+-------+
|      id|          int|   NULL|
|  amount|decimal(12,2)|   NULL|
+--------+-------------+-------+
```

**Type widening** is a table feature (Databricks Runtime 15.4 LTS and above, `delta.enableTypeWidening`) that allows changes such as `INT` to `BIGINT` or a wider `DECIMAL` "without rewriting data files" ([Type widening](https://docs.databricks.com/aws/en/tables/features/type-widening)). Like column mapping it upgrades the protocol.

!!! tip "In the interview"
    **"What is the difference between schema enforcement and schema evolution?"** Enforcement rejects writes whose columns or types do not fit the table (Delta tries a safe cast first). Evolution is an explicit opt-in that lets a write add new columns: `mergeSchema` on a DataFrame write, `WITH SCHEMA EVOLUTION` on `INSERT`/`MERGE`, or `ALTER TABLE ADD COLUMNS` as DDL. Renames and drops need column mapping; type changes need type widening or a rewrite with `overwriteSchema`.

## 4.7 Time travel, DESCRIBE HISTORY, DESCRIBE DETAIL and RESTORE
*Level: intermediate.*

Because every version is a set of `add` actions, and old files are not deleted right away, Delta can read the table as of any version still covered by both its log entries and its data files. This is **time travel**.

### Syntax

From [Work with table history](https://docs.databricks.com/aws/en/tables/history). The `VERSION AS OF`, `TIMESTAMP AS OF` and reader options also run on open-source Delta (next example); the `@` forms are Databricks syntax.

*Databricks only, not run here. Syntax from [Work with table history](https://docs.databricks.com/aws/en/tables/history).*

```sql
SELECT * FROM orders VERSION AS OF 3;
SELECT * FROM orders TIMESTAMP AS OF '2026-03-01T10:15:00.000Z';
SELECT * FROM orders TIMESTAMP AS OF date_sub(current_date(), 1);
SELECT * FROM orders@v3;                   -- Databricks: version shorthand
SELECT * FROM orders@20260301101500000;    -- Databricks: yyyyMMddHHmmssSSS
```

*Databricks only, not run here. Syntax from [Work with table history](https://docs.databricks.com/aws/en/tables/history).*

```python
spark.read.option("versionAsOf", 3).table("orders")
spark.read.option("timestampAsOf", "2026-03-01").table("orders")
```

Neither the timestamp nor the version can be a subquery.

### Running it on the `orders` table from section 4.4

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
spark.sql("SELECT * FROM orders VERSION AS OF 1 ORDER BY order_id").show()
spark.sql("SELECT count(*) AS n FROM orders@v3")              # Databricks syntax
spark.read.table("orders@v3").count()
ts_v2 = spark.sql("DESCRIBE HISTORY orders").where("version = 2").first().timestamp
spark.sql(f"SELECT order_id, status FROM orders TIMESTAMP AS OF '{ts_v2}' ORDER BY order_id").show()
spark.read.option("versionAsOf", 2).table("orders").count()
spark.sql("SELECT * FROM orders VERSION AS OF 99")
```

```text
=== Time travel ===
>>> SELECT * FROM orders VERSION AS OF 1 ORDER BY order_id
+--------+-----------+------+------+
|order_id|customer_id|status|amount|
+--------+-----------+------+------+
|1001    |7          |PLACED|59.90 |
|1002    |3          |PLACED|120.00|
|1003    |7          |PLACED|15.50 |
|1004    |9          |PLACED|42.00 |
+--------+-----------+------+------+

The @v shorthand (documented for Databricks) in open-source Spark SQL:
ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near '@'. SQLSTATE: 42601 (line 1, pos 32)
spark.read.table('orders@v3') -> ParseException: [PARSE_SYNTAX_ERROR] Syntax error at or near '@'. SQLSTATE: 42601 (line 1, pos 6)
timestamp of version 2: 2026-11-11 05:41:44.071000
>>> SELECT order_id, status FROM orders TIMESTAMP AS OF '2026-11-11 05:41:44.071000' ORDER BY order_id
+--------+-------+
|order_id|status |
+--------+-------+
|1001    |SHIPPED|
|1002    |SHIPPED|
|1003    |PLACED |
|1004    |PLACED |
+--------+-------+

PySpark versionAsOf=2: 4 rows
Asking for a version that does not exist:
AnalysisException: [DELTA_VERSION_NOT_FOUND] Cannot time travel Delta table to version 99. Available versions: [0, 4].
```

The `@v` shorthand is documented for Databricks but did not parse in open-source Spark SQL; on open-source, use `VERSION AS OF`.

### DESCRIBE HISTORY

`DESCRIBE HISTORY` returns one row per commit, newest first, with the version, timestamp, user, operation, `operationParameters`, `readVersion`, `isolationLevel`, `isBlindAppend` and `operationMetrics`. It reads the `commitInfo` actions you saw in section 4.2. `DESCRIBE HISTORY t LIMIT 1` returns only the last operation. History is kept as long as `delta.logRetentionDuration`, 30 days by default ([Work with table history](https://docs.databricks.com/aws/en/tables/history)). On Databricks you can query it like a table, `SELECT ... FROM (DESCRIBE HISTORY t)`, as the docs do; open-source Spark 4.2 rejected that form with a syntax error (output above in section 4.6), so the scripts filter the result with DataFrame methods instead.

### Scenario: someone ran DELETE without WHERE

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
DELETE FROM orders;                         -- the mistake (v5)
DESCRIBE HISTORY orders;                    -- find the last good version
RESTORE TABLE orders TO VERSION AS OF 4;    -- v6
```

```text
=== Oops: DELETE without WHERE ===
>>> SELECT count(*) AS rows_now FROM orders
+--------+
|rows_now|
+--------+
|0       |
+--------+

>>> DESCRIBE HISTORY orders  -- columns: version, operation, operationParameters
+-------+---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|version|operation|operationParameters                                                                                                                                                                      |
+-------+---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|4      |MERGE    |{predicate -> ["(order_id#2650 = order_id#2658)"], matchedPredicates -> [{"actionType":"update"}], notMatchedPredicates -> [{"actionType":"insert"}], notMatchedBySourcePredicates -> []}|
|5      |DELETE   |{predicate -> ["true"]}                                                                                                                                                                  |
+-------+---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

Recover with RESTORE to the version before the bad DELETE:
>>> RESTORE TABLE orders TO VERSION AS OF 4
+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
|table_size_after_restore|num_of_files_after_restore|num_removed_files|num_restored_files|removed_files_size|restored_files_size|
+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
|2554                    |2                         |0                |2                 |0                 |2554               |
+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+

>>> SELECT * FROM orders ORDER BY order_id
+--------+-----------+---------+------+
|order_id|customer_id|status   |amount|
+--------+-----------+---------+------+
|1001    |7          |SHIPPED  |59.90 |
|1002    |3          |SHIPPED  |120.00|
|1003    |7          |CANCELLED|15.50 |
|1005    |2          |PLACED   |88.00 |
+--------+-----------+---------+------+

>>> DESCRIBE HISTORY orders  -- columns: version, operation, operationParameters
+-------+---------+---------------------------------+
|version|operation|operationParameters              |
+-------+---------+---------------------------------+
|5      |DELETE   |{predicate -> ["true"]}          |
|6      |RESTORE  |{version -> 4, timestamp -> NULL}|
+-------+---------+---------------------------------+
```

The PySpark version of the same recovery, with `history()`, `restoreToVersion()` and the `versionAsOf` reader option:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
dt.history().select("version", "operation", "operationMetrics.numUpdatedRows",
                    "operationMetrics.numDeletedRows").orderBy("version").show()
dt.history(1).select("version", "operation").show()        # like DESCRIBE HISTORY ... LIMIT 1
spark.read.option("versionAsOf", 0).table("orders").count()
dt.delete()                                                # the mistake
dt.restoreToVersion(3).show()                              # restoreToTimestamp(...) also exists
```

```text
=== history() ===
+-------+--------------------+--------------+--------------+
|version|           operation|numUpdatedRows|numDeletedRows|
+-------+--------------------+--------------+--------------+
|      0|CREATE TABLE AS S...|          NULL|          NULL|
|      1|              UPDATE|             2|          NULL|
|      2|              DELETE|          NULL|             1|
|      3|               MERGE|          NULL|          NULL|
+-------+--------------------+--------------+--------------+

+-------+---------+
|version|operation|
+-------+---------+
|      3|    MERGE|
+-------+---------+

=== time travel with reader options ===
versionAsOf 0: 4 rows
=== oops: delete everything, then restoreToVersion ===
rows now: 0
+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
|table_size_after_restore|num_of_files_after_restore|num_removed_files|num_restored_files|removed_files_size|restored_files_size|
+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
|                    2554|                         2|                0|                 2|                 0|               2554|
+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+

rows after restore: 4
```

Three things to notice:

1. `RESTORE` did not rewind the log. It wrote a **new** commit (version 6) whose `add` actions point back at the data files of version 4. The bad `DELETE` stays in the history for auditing, and you could even restore to version 5 again.
2. `RESTORE` returns metrics: size and file count after the restore, files removed and restored ([RESTORE](https://docs.databricks.com/aws/en/sql/language-manual/delta-restore)).
3. It only worked because the files of version 4 were still on disk. After `VACUUM` removes them, "you can't restore a table to an older version that references those files" ([Work with table history](https://docs.databricks.com/aws/en/tables/history)). Section 4.8 shows that failure.

Instead of restoring the whole table you can repair part of it with time travel as the source, as the docs show: `INSERT INTO my_table SELECT * FROM my_table TIMESTAMP AS OF date_sub(current_date(), 1) WHERE userId = 111`, or a `MERGE` from an older version.

On Databricks, `RESTORE` needs the `MODIFY` privilege on the table, and timestamps for it use `yyyy-MM-dd HH:mm:ss` or `yyyy-MM-dd`. One more trap: restore log entries have `dataChange = true`, so a streaming query reading the table treats the restored files as new data and may produce duplicates downstream ([Work with table history](https://docs.databricks.com/aws/en/tables/history)).

!!! warning "Time travel is not a backup"
    "Don't use table history as a long-term backup solution for data archival. Use only the past 7 days for time travel operations unless you have set both data and log retention configurations to a larger value." And in Databricks Runtime 18.0 and above (12.2 LTS and above for Unity Catalog managed tables), time travel queries "are blocked if they request a version older than the `deletedFileRetentionDuration` table property (default 7 days)" ([Work with table history](https://docs.databricks.com/aws/en/tables/history)).

### DESCRIBE DETAIL

`DESCRIBE DETAIL` returns one row of metadata about the current version: `format`, `id`, `name`, `location`, `createdAt`, `lastModified`, `partitionColumns`, `clusteringColumns`, `numFiles`, `sizeInBytes`, `properties`, `minReaderVersion`, `minWriterVersion`, `tableFeatures` ([Review table details with describe detail](https://docs.databricks.com/aws/en/tables/operations/table-details)). It is the quickest way to answer "how many files does this table have?" (small files) and "which features does it use?" (compatibility).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
DESCRIBE DETAIL orders;
```

```text
>>> DESCRIBE DETAIL orders  -- columns: format, name, numFiles, sizeInBytes, minReaderVersion, minWriterVersion, tableFeatures
+------+----------------------------+--------+-----------+----------------+----------------+------------------------+
|format|name                        |numFiles|sizeInBytes|minReaderVersion|minWriterVersion|tableFeatures           |
+------+----------------------------+--------+-----------+----------------+----------------+------------------------+
|delta |spark_catalog.default.orders|2       |2554       |1               |2               |[appendOnly, invariants]|
+------+----------------------------+--------+-----------+----------------+----------------+------------------------+
```

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 260" role="img" aria-label="A timeline of versions 0 to 6. Time travel can read any version whose log entries and data files still exist. VACUUM deletes data files that were removed from the table longer ago than the retention threshold, so older versions can no longer be read.">
<g font-size="13" fill="currentColor">
<line x1="30" y1="110" x2="610" y2="110" stroke="currentColor" stroke-width="1.5"/>
<polygon points="610,104 622,110 610,116" fill="currentColor"/>
<circle cx="60" cy="110" r="6" fill="currentColor"/><text x="48" y="96">v0</text>
<circle cx="140" cy="110" r="6" fill="currentColor"/><text x="128" y="96">v1</text>
<circle cx="220" cy="110" r="6" fill="currentColor"/><text x="208" y="96">v2</text>
<circle cx="300" cy="110" r="6" fill="currentColor"/><text x="288" y="96">v3</text>
<circle cx="380" cy="110" r="6" fill="currentColor"/><text x="368" y="96">v4</text>
<circle cx="460" cy="110" r="6" fill="currentColor"/><text x="448" y="96">v5</text>
<circle cx="540" cy="110" r="6" fill="currentColor"/><text x="528" y="96">v6</text>
<text x="500" y="140">current</text>
<text x="60" y="40">VERSION AS OF 1, TIMESTAMP AS OF '...', orders@v1</text>
<line x1="140" y1="48" x2="140" y2="84" stroke="currentColor"/>
<polygon points="134,80 146,80 140,88" fill="currentColor"/>
<rect x="30" y="160" width="300" height="34" rx="4" fill="none" stroke="currentColor" stroke-dasharray="5 3"/>
<text x="40" y="182">files removed before (now - retention)</text>
<text x="40" y="216">VACUUM deletes these files, so v0 to v3</text>
<text x="40" y="234">can no longer be read or restored.</text>
<rect x="340" y="160" width="270" height="34" rx="4" fill="none" stroke="currentColor"/>
<text x="350" y="182">inside the retention window: kept</text>
<text x="350" y="216">The history still lists them</text>
<text x="350" y="234">until log retention removes them.</text>
</g>
</svg>
<figcaption>Figure 4.4. Time travel needs both the log entries and the data files of a version. Log entries are cleaned up after <code>delta.logRetentionDuration</code> (30 days by default); <code>VACUUM</code> deletes unreferenced data files older than <code>delta.deletedFileRetentionDuration</code> (7 days by default).</figcaption>
</figure>

## 4.8 VACUUM and retention
*Level: intermediate.*

Old data files are what make time travel possible, but they also cost storage, and they still contain deleted rows (a privacy problem if a customer asked to be forgotten). `VACUUM` deletes data files that are no longer referenced by the table and are older than a retention threshold.

The rules, from [Remove unused data files with vacuum](https://docs.databricks.com/aws/en/tables/operations/vacuum) and the [VACUUM](https://docs.databricks.com/aws/en/sql/language-manual/delta-vacuum) reference:

- The default retention threshold is **7 days**, set by the table property `delta.deletedFileRetentionDuration`. Files are judged by when they were logically removed in the log, not by their storage modification time.
- `VACUUM` does **not** delete log files. Log files are removed automatically after checkpoints, governed by `delta.logRetentionDuration` (30 days by default). So after a `VACUUM`, `DESCRIBE HISTORY` still lists old versions that can no longer be read.
- It skips directories whose names start with `_` (such as `_delta_log`), but it removes files it does not recognize elsewhere in the table folder, including uncommitted files left by failed jobs. Keep things like streaming checkpoints out of table folders, or in a folder named like `_checkpoints`.
- `VACUUM t DRY RUN` lists (up to 1,000) files it would delete.
- Databricks documents `LITE` and `FULL` modes (the vacuum guide says LITE is in Public Preview in Databricks Runtime 16.4 LTS and above, the SQL reference says 16.1 and above; which is right was not verified) (`VACUUM t LITE` also ran on open-source Delta 4.4.1 in `ch04_06_vacuum.py`). `FULL` (default) lists the whole folder; `LITE` uses the transaction log to find expired files, is faster on large tables, but does not delete files the log never referenced.
- "Predictive optimization automatically runs `VACUUM` on Unity Catalog managed tables."

### Scenario: VACUUM with 0 hours

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
VACUUM orders DRY RUN;                     -- nothing is 7 days old yet
VACUUM orders RETAIN 0 HOURS;              -- blocked by the safety check
SET spark.databricks.delta.retentionDurationCheck.enabled = false;
VACUUM orders RETAIN 0 HOURS;
SELECT * FROM orders VERSION AS OF 1;      -- old version
RESTORE TABLE orders TO VERSION AS OF 1;
```

```text
data files on disk: 4
>>> DESCRIBE DETAIL orders  -- columns: numFiles
+--------+
|numFiles|
+--------+
|1       |
+--------+

1) VACUUM with the default retention (nothing is old enough yet):
>>> VACUUM orders DRY RUN
+----+
|path|
+----+
+----+

2) VACUUM ... RETAIN 0 HOURS with the safety check on:
IllegalArgumentException: [DELTA_VACUUM_RETENTION_PERIOD_TOO_SHORT] The specified VACUUM retention period is too low and may corrupt this Delta table if any writes are in progress. If no operations (insert, upsert, delete, optimize) are running, you can disable this safety check by setting: delta.retentionDurationCheck.enabled = false Otherwise, use a retention period of at least 168 hours.
3) Time travel to version 1 still works:
>>> SELECT * FROM orders VERSION AS OF 1 ORDER BY order_id
+--------+------+
|order_id|status|
+--------+------+
|1001    |PLACED|
|1002    |PLACED|
+--------+------+

4) Turn the safety check off and vacuum with 0 hours:
>>> VACUUM orders RETAIN 0 HOURS DRY RUN   (file names only)
  part-00000-2befb861-8eb4-4492-87a8-cb1007c6ae9b-c000.snappy.parquet
  part-00001-41ce272c-d3a2-48c1-a93a-6acbcb6e77ce-c000.snappy.parquet
  part-00000-ddc940d4-71c3-4642-bfe7-179bd185413d-c000.snappy.parquet
Deleted 3 files and directories in a total of 1 directories.
data files on disk after VACUUM: 1
>>> SELECT * FROM orders ORDER BY order_id
+--------+-------+
|order_id|status |
+--------+-------+
|1001    |SHIPPED|
+--------+-------+

5) Time travel to version 1 after VACUUM RETAIN 0 HOURS:
Py4JJavaError: An error occurred while calling o93.showString. : org.apache.spark.SparkException: [FAILED_READ_FILE.FILE_NOT_EXIST] Encountered error while reading file file:/.../warehouse/orders/part-00000-2befb861-8eb4-4492-87a8-cb1007c6ae9b-c000.snappy.parquet. File does not exist. It is possible the underlying files have been updated. You can explicitly invalidate the cache in Spark by running 'REFRESH TABLE tableName' command in SQL or by recreating the Dataset/DataFrame involved. SQLSTATE: KD001 Caused by: java.io.FileNotFoundException: File file:/.../warehouse/orders/part-00000-2befb861-8eb4-4492-87a8-cb1007c6ae9b-c000.snappy.parquet does not exist ... 1 more
6) RESTORE to version 1 after VACUUM:
IllegalArgumentException: Not all files from version 1 are available in file system. Missed files (top 100 files): part-00000-2befb861-8eb4-4492-87a8-cb1007c6ae9b-c000.snappy.parquet,part-00001-41ce272c-d3a2-48c1-a93a-6acbcb6e77ce-c000.snappy.parquet. Please use more recent version or timestamp for restoring. To disable check update option spark.sql.files.ignoreMissingFiles
7) The history is still there (log retention is separate from VACUUM):
>>> DESCRIBE HISTORY orders  -- columns: version, operation
+-------+------------+
|version|operation   |
+-------+------------+
|0      |CREATE TABLE|
|1      |WRITE       |
|2      |UPDATE      |
|3      |DELETE      |
|4      |VACUUM START|
|5      |VACUUM END  |
+-------+------------+
```

The DRY RUN listed the three files no longer used by version 3, `VACUUM` deleted them, and the log recorded `VACUUM START` and `VACUUM END` commits. What was lost: every data file not used by the **current** version. The current table still reads fine. Time travel and `RESTORE` to any earlier version now fail with a missing-file error, while the history still lists those versions. That is exactly why Databricks "strongly recommends setting a retention interval of at least 7 days": besides time travel, a job that runs longer than the retention window might have its not-yet-committed files deleted ([Remove unused data files with vacuum](https://docs.databricks.com/aws/en/tables/operations/vacuum)).

!!! note "RETAIN on Databricks"
    `VACUUM ... RETAIN n HOURS` is open-source Delta syntax and ran here. The current Databricks `VACUUM` reference shows no `RETAIN` clause and says the retention window "is determined by the `delta.deletedFileRetentionDuration` table property"; the vacuum guide says that in Databricks Runtime 18.0 and above (12.2 LTS and above for Unity Catalog managed tables) you use that property to control retention. On Databricks, change retention with `ALTER TABLE ... SET TBLPROPERTIES ('delta.deletedFileRetentionDuration' = '30 days')`. Whether Databricks still accepts the `RETAIN` clause was not verified.

To keep 30 days of time travel, raise both properties, as the docs advise (in Databricks Runtime 18.0 and above, `logRetentionDuration` must be at least `deletedFileRetentionDuration`):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (step 8 of `ch04_06_vacuum.py`)

```sql
ALTER TABLE orders SET TBLPROPERTIES (
  'delta.deletedFileRetentionDuration' = 'interval 30 days',
  'delta.logRetentionDuration'         = 'interval 30 days');
```

In PySpark, `DeltaTable.vacuum()` takes an optional retention in hours (`dt.vacuum(168)`) and returns an empty DataFrame; `optimize().executeCompaction()` and `detail()` mirror `OPTIMIZE` and `DESCRIBE DETAIL`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
dt.optimize().executeCompaction().select("metrics.numFilesAdded", "metrics.numFilesRemoved").show()
dt.detail().select("numFiles", "minReaderVersion", "minWriterVersion").show()
dt.vacuum()                                                # default retention
```

```text
=== optimize, detail, vacuum ===
+-------------+---------------+
|numFilesAdded|numFilesRemoved|
+-------------+---------------+
|            1|              2|
+-------------+---------------+

+--------+----------------+----------------+
|numFiles|minReaderVersion|minWriterVersion|
+--------+----------------+----------------+
|       1|               1|               2|
+--------+----------------+----------------+

Deleted 0 files and directories in a total of 1 directories.
vacuum() with the default retention returns: DataFrame[]
+-------+--------------------+
|version|           operation|
+-------+--------------------+
|      0|CREATE TABLE AS S...|
|      1|              UPDATE|
|      2|              DELETE|
|      3|               MERGE|
|      4|              DELETE|
|      5|             RESTORE|
|      6|            OPTIMIZE|
|      7|        VACUUM START|
|      8|          VACUUM END|
+-------+--------------------+
```

!!! warning "Disk cache can hide a VACUUM"
    On Databricks, a cluster's disk cache may still hold data from files that `VACUUM` deleted, so an old version might still be readable on that cluster until it restarts ([Remove unused data files with vacuum](https://docs.databricks.com/aws/en/tables/operations/vacuum)). Do not treat "it still worked" as proof that the files exist.

!!! tip "In the interview"
    **"Why does VACUUM limit time travel?"** Time travel reads the data files that an old version's `add` actions point to. `VACUUM` deletes files that the current version no longer references once they have been removed for longer than `delta.deletedFileRetentionDuration` (default 7 days). After that, the old version's log entries may still exist (log retention defaults to 30 days) but its files are gone, so reading or restoring it fails.

## 4.9 OPTIMIZE, small files and deletion vectors
*Level: intermediate.*

### Small files

Every write creates at least one file per task. Streaming micro-batches and frequent small inserts therefore produce thousands of tiny files, and reading a table means opening each one. `OPTIMIZE` rewrites small files into fewer, larger ones (bin-packing). It changes no data, so readers before and after get the same rows, and it is idempotent: a second run on the same data does nothing ([Optimize data file layout](https://docs.databricks.com/aws/en/tables/operations/optimize)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- six tiny INSERTs, then:
DESCRIBE DETAIL order_items;   -- numFiles
OPTIMIZE order_items;
DESCRIBE DETAIL order_items;
OPTIMIZE order_items;          -- again
```

```text
>>> DESCRIBE DETAIL order_items  -- columns: numFiles, sizeInBytes
+--------+-----------+
|numFiles|sizeInBytes|
+--------+-----------+
|6       |7386       |
+--------+-----------+

>>> OPTIMIZE order_items
|file:/.../warehouse/order_items|{1, 6, {1363, 1363, 1363.0, 1, 1363}, {1231, 1231, 1231.0, 6, 7386}, 1, NULL, NULL, 1, 1, 6, 0, false, 0, 0, 1794374573875, 0, 2, 0, NULL, NULL, 4, 4}|

>>> DESCRIBE DETAIL order_items  -- columns: numFiles, sizeInBytes
+--------+-----------+
|numFiles|sizeInBytes|
+--------+-----------+
|1       |1363       |
+--------+-----------+

>>> DESCRIBE HISTORY order_items  -- columns: version, operation, operationMetrics.numRemovedFiles, operationMetrics.numAddedFiles
+-------+---------+---------------+-------------+
|version|operation|numRemovedFiles|numAddedFiles|
+-------+---------+---------------+-------------+
|7      |OPTIMIZE |6              |1            |
+-------+---------+---------------+-------------+

  add    dataChange=False
  remove dataChange=False
  remove dataChange=False
  remove dataChange=False
  remove dataChange=False
  remove dataChange=False
  remove dataChange=False
>>> OPTIMIZE order_items
|file:/.../warehouse/order_items|{0, 0, {NULL, NULL, 0.0, 0, 0}, {NULL, NULL, 0.0, 0, 0}, 0, NULL, NULL, 0, 1, 1, 1, false, 0, 0, 1794374598487, 0, 2, 0, NULL, NULL, 4, 4}|
```

`OPTIMIZE` returns one row per table with the path and a `metrics` struct (shown here without the wide table borders, path shortened); the struct starts with the number of files added and removed: `{1, 6, ...}` the first time, `{0, 0, ...}` the second. The `OPTIMIZE` commit has `add` and `remove` actions with `dataChange=false`. That flag tells streaming readers the commit only rearranged existing data, so they can skip it (the protocol describes `dataChange = false` as "only rearranges existing data or adds new statistics"). The six small files are not deleted: they are now unreferenced, and `VACUUM` removes them after the retention period.

On Databricks, predictive optimization runs `OPTIMIZE` automatically on Unity Catalog managed tables, and Databricks recommends liquid clustering over partitioning or `ZORDER BY` for data layout ([Optimize data file layout](https://docs.databricks.com/aws/en/tables/operations/optimize)). File sizing, auto compaction, liquid clustering and Z-order are in chapter 22.

### Deletion vectors

Without deletion vectors, changing one row means rewriting the whole Parquet file that holds it, as the `UPDATE` in section 4.2 did. **Deletion vectors** "mark rows as modified in metadata instead, and reads apply the deletion vector entries at query time" ([Deletion vectors in Databricks](https://docs.databricks.com/aws/en/tables/features/deletion-vectors)). A deletion vector is a small file (or an inline value in the log) listing the positions of rows in a data file that are no longer valid. An `UPDATE` marks the old row deleted and writes only the new version of the row to a new file.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE orders_dv (order_id INT, status STRING) USING DELTA
TBLPROPERTIES ('delta.enableDeletionVectors' = true);
INSERT INTO orders_dv SELECT id, 'PLACED' FROM range(1001, 2001);   -- 1,000 rows
DELETE FROM orders_dv WHERE order_id = 1500;
REORG TABLE orders_dv APPLY (PURGE);
```

```text
=== Default table protocol for a new table in open-source Delta 4.4.1 ===
>>> DESCRIBE DETAIL order_items  -- columns: minReaderVersion, minWriterVersion, tableFeatures
+----------------+----------------+------------------------+
|minReaderVersion|minWriterVersion|tableFeatures           |
+----------------+----------------+------------------------+
|1               |2               |[appendOnly, invariants]|
+----------------+----------------+------------------------+

=== Deletion vectors ===
>>> DESCRIBE DETAIL orders_dv  -- columns: numFiles, minReaderVersion, minWriterVersion, tableFeatures
+--------+----------------+----------------+-----------------------------------------+
|numFiles|minReaderVersion|minWriterVersion|tableFeatures                            |
+--------+----------------+----------------+-----------------------------------------+
|2       |3               |7               |[appendOnly, deletionVectors, invariants]|
+--------+----------------+----------------+-----------------------------------------+

new files in the table folder after DELETE of one row:
  .deletion_vector_f42fb4bd-09fd-4389-8fe2-b0cca2e4aec0.bin.crc
  deletion_vector_f42fb4bd-09fd-4389-8fe2-b0cca2e4aec0.bin
>>> DESCRIBE HISTORY orders_dv  -- columns: version, operation, operationMetrics.numDeletedRows, operationMetrics.numDeletionVectorsAdded, operationMetrics.numRemovedFiles, operationMetrics.numAddedFiles
+-------+---------+--------------+-----------------------+---------------+-------------+
|version|operation|numDeletedRows|numDeletionVectorsAdded|numRemovedFiles|numAddedFiles|
+-------+---------+--------------+-----------------------+---------------+-------------+
|2      |DELETE   |1             |1                      |0              |0            |
+-------+---------+--------------+-----------------------+---------------+-------------+

  add.deletionVector = {"storageType": "u", "pathOrInlineDv": "]E)O+3h)kFKk^y/Qu5F)", "offset": 1, "sizeInBytes": 34, "cardinality": 1}
>>> SELECT count(*) AS n FROM orders_dv
+---+
|n  |
+---+
|999|
+---+

=== REORG ... APPLY (PURGE) rewrites files to drop soft-deleted rows ===
>>> REORG TABLE orders_dv APPLY (PURGE)
|file:/.../warehouse/orders_dv|{1, 1, {2781, 2781, 2781.0, 1, 2781}, {2785, 2785, 2785.0, 1, 2785}, 1, NULL, NULL, 1, 1, 2, 1, false, 0, 0, 1794374650120, 0, 2, 0, NULL, {1, 1}, 2, 2}|

>>> DESCRIBE HISTORY orders_dv  -- columns: version, operation, operationParameters
+-------+---------+-----------------------------------------+
|version|operation|operationParameters                      |
+-------+---------+-----------------------------------------+
|2      |DELETE   |{predicate -> ["(order_id#4447 = 1500)"]}|
|3      |REORG    |{predicate -> [], applyPurge -> true}    |
+-------+---------+-----------------------------------------+
```

Deleting one row of 1,000 wrote only a tiny `deletion_vector_...bin` file (the hidden `.crc` next to it is the local file system's checksum, not part of Delta), and the commit metrics show one deletion vector added and no files removed or added. The log re-added the same data file with a `deletionVector` descriptor attached (`storageType` `u` means a file referenced by a UUID-based relative path). Readers skip the marked row. The data is still physically in the Parquet file. To rewrite files and drop soft-deleted rows, run `OPTIMIZE` or `REORG TABLE ... APPLY (PURGE)`. To remove the data from storage completely (a GDPR request, for example), run `REORG TABLE ... APPLY (PURGE)` and then `VACUUM` after the retention period.

Deletion vectors also enable row-level concurrency (section 4.5) and, on Photon, predictive I/O for updates.

**Default status (check this in your workspace):**

- The deletion vectors page says that for Delta Lake tables "you must explicitly enable deletion vectors", with the table property `delta.enableDeletionVectors`.
- A workspace admin setting, **Auto-Enable Deletion Vectors**, decides whether new tables get them automatically on SQL warehouses and Databricks Runtime 14.0 and above. Its options are Default, New UC managed and Databricks SQL tables, All new tables, and Disabled. "The default value ... varies by region", and after Databricks' rollout completes, the Default option changes from Disabled to All new tables ([Auto-enable deletion vectors](https://docs.databricks.com/aws/en/admin/workspace-settings/deletion-vectors)).
- The table properties reference sums it up: default "depends on workspace admin settings and Databricks Runtime version" ([Table properties reference](https://docs.databricks.com/aws/en/tables/table-properties)).
- Which setting a given workspace has cannot be known from the docs; check the admin settings page.
- Open-source Delta 4.4.1: a plain `CREATE TABLE` did not enable them (the default table above has only `appendOnly` and `invariants` features); we set the property ourselves.

!!! warning "Deletion vectors upgrade the protocol"
    Enabling deletion vectors moves the table to reader version 3 and writer version 7 with the `deletionVectors` feature, as the output shows. "After upgrading, clients without deletion vector support can't read the table." Open-source Delta reads them from 2.3.0 and writes `DELETE` from 2.4.0 and `UPDATE` from 3.0.0; Databricks Runtime 12.2 LTS and above reads them ([Deletion vectors in Databricks](https://docs.databricks.com/aws/en/tables/features/deletion-vectors)). Check every external reader before you turn them on.

!!! tip "In the interview"
    **"What are deletion vectors and why use them?"** They record deleted or updated rows as a small bitmap next to the data file instead of rewriting the file, so `DELETE`, `UPDATE` and `MERGE` that touch few rows are much cheaper. Reads filter the marked rows. The cost is extra work at read time until files are rewritten by `OPTIMIZE` or `REORG ... APPLY (PURGE)`, and a protocol upgrade that older clients cannot read. On Databricks they also enable row-level concurrency.

## 4.10 Going deeper: protocols, table features, and Databricks vs open-source Delta
*Level: expert.*

### Protocol versions and table features

Every table's `protocol` action states what a client must support. From [Delta Lake feature compatibility and protocols](https://docs.databricks.com/aws/en/tables/features/feature-compatibility):

- `minReaderVersion` is 1, 2 or 3; `minWriterVersion` is 2 to 7.
- Older features were bundled into numbered versions, for example `CHECK` constraints at writer 3, change data feed and generated columns at writer 4, column mapping at reader 2 / writer 5, identity columns at writer 6.
- **Table features** replace the numbers with named flags once a table is at reader 3 and writer 7: `readerFeatures` and `writerFeatures` lists in the protocol. A **writer feature** (such as `CHECK` constraints or in-commit timestamps) only affects writers; a **reader feature** (such as deletion vectors, column mapping, liquid clustering, type widening, variant) affects both. A client cannot write to a table it cannot read.
- Enabling a feature upgrades the protocol automatically: by syntax (`CLUSTER BY` enables liquid clustering, `GENERATED ALWAYS AS` enables generated columns), by a property (`delta.enableDeletionVectors`), or as a dependency (liquid clustering enables checkpoint V2).
- "Most protocol version upgrades are irreversible." Some features can be removed with `ALTER TABLE ... DROP FEATURE`, which downgrades the protocol; turning a feature off does not. Databricks recommends never setting `minReaderVersion` or `minWriterVersion` by hand.
- Every protocol change conflicts with all concurrent writes and stops streams that read the table.

You saw this happen in the runs: a new open-source table started at 1/2 with `[appendOnly, invariants]` (the legacy features writer version 2 implies), column mapping moved it to 2/7, and deletion vectors to 3/7. `DESCRIBE DETAIL` shows `minReaderVersion`, `minWriterVersion` and `tableFeatures`.

### Checkpoints, in more detail

The protocol allows several checkpoint formats: classic single-file `n.checkpoint.parquet` (what the run produced), multi-part, and UUID-named **V2 checkpoints** that can reference sidecar files in `_delta_log/_sidecars`. A checkpoint contains the reconciled actions up to its version plus unexpired `remove` tombstones, but not `commitInfo`; that is why `DESCRIBE HISTORY` reads the JSON files. Metadata cleanup may delete old JSON files only if a checkpoint covers the oldest kept version ([Delta Transaction Log Protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md)). On Databricks, checkpoint V2 is among the features automatic upgrades turn on for Unity Catalog managed tables ([Automatic upgrades](https://docs.databricks.com/aws/en/tables/automatic-upgrades)).

### Catalog commits and multi-table transactions

With **catalog commits** (table feature `catalogManaged`, Databricks Runtime 16.4 LTS and above), commits are coordinated by Unity Catalog instead of only by files in storage. Databricks lists it among features "unique to Unity Catalog managed tables", enabling multi-statement transactions across tables, faster query planning and safe writes from external engines ([Unity Catalog managed tables for Delta Lake and Apache Iceberg](https://docs.databricks.com/aws/en/tables/managed)). The open protocol describes the same mechanism as catalog-managed tables, where recent commits can live in the catalog or in `_delta_log/_staged_commits` before they are published as normal JSON files ([Delta Transaction Log Protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md)).

### Change data feed (pointer)

Change data feed records row-level changes (insert, update preimage and postimage, delete) between versions, readable with `table_changes()` or `readChangeFeed`. Databricks now has two forms: automatic (computed at read time from row tracking, Databricks Runtime 19 and above, and "for Delta Lake, only Databricks readers can query automatic change data feed") and legacy (materialized at write time in `_change_data`, enabled per table with `delta.enableChangeDataFeed`) ([Use change data feed on Databricks](https://docs.databricks.com/aws/en/tables/features/change-data-feed)). [Chapter 9](09-Building-Silver.md) uses it to build silver incrementally; chapter 20 covers `table_changes` and `CLONE`.

### Databricks Delta vs open-source Delta

Delta Lake is open source, and the transaction log has "a well-defined open protocol that can be used by any system to read the log" ([What is Delta Lake in Databricks?](https://docs.databricks.com/aws/en/delta/)). The same table can be read by open-source Spark, Trino, DuckDB and others, as long as they support its table features. The Databricks docs do not publish one complete list of differences. These are the items the docs themselves describe as Databricks features:

| Feature | What the docs say |
| --- | --- |
| Disk cache (formerly "Delta cache") | "Disk caching behavior is a proprietary Databricks feature"; renamed because people thought it was part of the Delta protocol ([Optimize performance with caching on Databricks](https://docs.databricks.com/aws/en/optimizations/disk-cache)) |
| Photon | "the Databricks-native vectorized query engine", including a native Parquet writer for Delta writes ([What is Photon?](https://docs.databricks.com/aws/en/compute/photon)) |
| Low shuffle merge | "the optimized Databricks implementation of `MERGE`", enabled by default ([Low shuffle merge on Databricks](https://docs.databricks.com/aws/en/optimizations/low-shuffle-merge)) |
| Predictive optimization | Runs `OPTIMIZE`, `VACUUM` and `ANALYZE` automatically on Unity Catalog managed tables ([Predictive optimization for Unity Catalog managed tables](https://docs.databricks.com/aws/en/optimizations/predictive-optimization)) |
| Catalog commits, multi-statement transactions, automatic liquid clustering, metadata caching | Listed as unique to Unity Catalog managed tables ([Unity Catalog managed tables for Delta Lake and Apache Iceberg](https://docs.databricks.com/aws/en/tables/managed)) |
| Automatic change data feed | "For Delta Lake, only Databricks readers can query automatic change data feed" ([Use change data feed on Databricks](https://docs.databricks.com/aws/en/tables/features/change-data-feed)) |
| Automatic upgrades | Databricks turns on features such as checkpoint V2, row tracking, catalog commits and in-commit timestamps on Unity Catalog managed tables after verifying client compatibility ([Automatic upgrades](https://docs.databricks.com/aws/en/tables/automatic-upgrades)) |

Row-level concurrency and predictive I/O are documented on Databricks pages with Databricks Runtime requirements; whether open-source Delta has an equivalent was not verified here.

### Defaults: Databricks vs open-source

| Setting | Databricks (docs) | Open-source Delta 4.4.1 (seen in this chapter's runs) |
| --- | --- | --- |
| Default table format | Delta for all tables | Parquet (Spark's default source); you write `USING DELTA` / `.format("delta")` |
| Isolation level | `WriteSerializable` | `DESCRIBE HISTORY` recorded `Serializable` (observed; the open-source concurrency docs do not name a default level, so not verified as a documented default) |
| Deletion vectors on new tables | Depends on workspace setting and runtime; rolling out to "All new tables" | Off unless `delta.enableDeletionVectors = true` |
| `deletedFileRetentionDuration` (VACUUM, time travel) | 7 days | 7 days: the protocol text says "default 7 days", and the safety-check error asked for "a retention period of at least 168 hours" |
| `logRetentionDuration` (history) | 30 days | 30 days: the open-source Delta Lake docs say "The default is `interval 30 days`" ([Table batch reads and writes, docs source on GitHub](https://github.com/delta-io/delta/blob/master/docs/src/content/docs/delta-batch.mdx)) |
| Checkpoint frequency | Chosen by Databricks, "subject to change without notice" | A checkpoint appeared at version 10 (documented default not verified) |
| `VACUUM` retention | Table property (no `RETAIN` clause in the current reference) | `RETAIN n HOURS` works |
| Querying `DESCRIBE HISTORY` as a subquery | Supported | Syntax error |
| `@v` time travel shorthand | Supported | Syntax error in SQL |

!!! tip "In the interview"
    **"Is Delta Lake proprietary?"** No. Delta Lake is open source with an open log protocol, and Databricks contributes to it. Databricks adds platform features around it: Photon, the disk cache, low shuffle merge, predictive optimization, automatic upgrades, catalog commits and multi-statement transactions for Unity Catalog managed tables. A table written on Databricks can be read elsewhere as long as the reader supports the table's features; deletion vectors, column mapping or liquid clustering can lock older readers out.

## 4.11 Practice questions
*Level: mixed.*

**Q1. What two parts make up a Delta table on storage, and which one decides what rows the table contains?**

??? success "Answer"
    Parquet data files and the `_delta_log` folder (JSON commits plus Parquet checkpoints). The log decides: a data file is part of the current table only if an `add` action for it has not been cancelled by a later `remove`.

    **Why:** listing the folder is not enough. The folder can hold files from failed writes, files removed by an `UPDATE` or `OPTIMIZE`, and files kept for time travel. That is why you must never add or delete files by hand.

**Q2. Name the five common actions in a commit file and say what each records.**

??? success "Answer"
    `protocol` (minimum reader/writer versions and table features), `metaData` (schema, partition columns, table properties, table id), `add` (a data file joins the table, with size and column statistics), `remove` (a data file leaves the table, with a deletion timestamp), `commitInfo` (operation, parameters, read version, metrics).

    **Why:** `DESCRIBE HISTORY` is built from `commitInfo`, `DESCRIBE DETAIL` from `protocol` and `metaData`, and queries from the live `add` actions.

**Q3. A new table gets one `INSERT` that writes two files, a second `INSERT` that writes one file, then an `UPDATE` that changes one row in the first file. How many data files are on disk, and how many are in the current version?**

??? success "Answer"
    Four on disk, three live. The `UPDATE` wrote a new file with the changed row (`add`) and marked the old file `remove`. The old file stays on disk for time travel until `VACUUM` deletes it after the retention period. This is exactly the run in section 4.2: four `part-...parquet` files, one of them tombstoned in version 3.

    **Why:** without deletion vectors, Delta never edits a Parquet file in place; it rewrites whole files (copy-on-write).

**Q4. What is a checkpoint, and what is `_last_checkpoint` for?**

??? success "Answer"
    A checkpoint is a Parquet file in `_delta_log` holding the full reconciled table state (protocol, metadata, live `add` files, unexpired tombstones) at one version. Readers load the newest checkpoint and replay only the later JSON commits instead of all of them. `_last_checkpoint` names the newest checkpoint so readers can find it without listing the folder.

    **Why:** replaying thousands of small JSON files is slow. On Databricks the checkpoint frequency is chosen automatically and "subject to change without notice", so never depend on a fixed interval.

**Q5. A nightly job overwrites a table and fails halfway. What does the table contain afterwards if it is a plain Parquet folder? If it is a Delta table?**

??? success "Answer"
    Parquet folder: possibly nothing. In the section 4.1 run the old files were deleted before the new write started, and the folder ended up empty and unreadable. Delta table: exactly what it had before. The failed job never wrote its commit file, so its new files are not referenced and the previous version stays current.

    **Why:** Delta's atomicity comes from the commit file being the last step. Leftover files from the failed job are invisible and are later cleaned up by `VACUUM`.

**Q6. A notebook runs `INSERT INTO silver.orders ...` and then `INSERT INTO gold.daily_sales ...`. The second statement fails. What state is `silver.orders` in?**

??? success "Answer"
    The silver insert is committed. By default each SQL statement is its own atomic transaction against one table, so the two inserts are independent. Make the job idempotent (for example `MERGE` or `INSERT ... REPLACE WHERE` on rerun), or on Databricks use a multi-statement transaction (`BEGIN ATOMIC ... END;`), which requires catalog commits on the participating Unity Catalog managed tables.

    **Why:** "transactional" in Delta means per table and per commit unless you use the multi-table transaction feature.

**Q7. Two jobs run `INSERT INTO orders VALUES ...` on the same table at the same moment. What happens?**

??? success "Answer"
    Both commit, one as version N and the other as N+1. Blind appends do not read the table, so a concurrent append cannot invalidate them; the loser of the race for version N simply retries its commit as N+1. The section 4.5 run shows both `INSERT`s committing.

    **Why:** the conflict matrix lists `INSERT` + `INSERT` as "cannot conflict" under both isolation levels.

**Q8. Two `MERGE` jobs update different countries of an `events` table partitioned by `country`, yet one fails with `ConcurrentAppendException`. Why, and how do you fix it?**

??? success "Answer"
    The `MERGE` condition does not restrict the target to one partition, so each job reads the whole table, and the other job's new files land in data it read. Add explicit partition predicates to the merge condition, for example `... AND t.country = 'CA'`, so each job reads only its own partition.

    **Why:** Databricks documents this exact fix ("Avoid conflicts with explicit partition filters"). A conflict happens only when two operations touch the same set of files; filters make the sets disjoint.

**Q9. A long `DELETE FROM orders WHERE status = 'TEST'` starts. While it runs, another job inserts a row with `status = 'TEST'` and commits first. What happens under WriteSerializable and under Serializable?**

??? success "Answer"
    WriteSerializable (the Databricks default): the `DELETE` commits, and the newly inserted `TEST` row survives, because the result is as if the insert happened after the delete. The history still lists the insert first. Serializable: the `DELETE` fails with a conflict and must be retried.

    **Why:** WriteSerializable only requires that writes can be ordered serially, not that the order matches the history. Choose Serializable if a delete must remove every matching row present at commit time.

**Q10. Under Serializable isolation, an `INSERT` and an `UPDATE` touching the same rows conflict. Which one fails?**

??? success "Answer"
    The `UPDATE`. "Only the operation that reads the affected data fails"; a blind append does not read, so retry logic belongs on the `UPDATE`, `DELETE` or `MERGE`.

    **Why:** the append never depended on the data the other job changed.

**Q11. Find the bug. On open-source Spark with Delta, this fails with "The format of the existing table ... is `DeltaDataSource`. It doesn't match the specified format `ParquetDataSourceV2`". The same code works on Databricks.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (from `ch04_03_read_write.py`)

```python
new_rows.write.mode("append").saveAsTable("products")
```

??? success "Answer"
    Add `.format("delta")`: `new_rows.write.format("delta").mode("append").saveAsTable("products")`.

    **Why:** open-source Spark's default data source is Parquet, so the write asks for a Parquet table. On Databricks Delta is the default format, so the format can be left out. This error came from the section 4.3 run.

**Q12. Can you read a Unity Catalog managed table with `spark.read.format("delta").load("s3://.../path")`?**

??? success "Answer"
    No. On Databricks, managed tables must be accessed by their fully qualified name; "path-based access is only supported for volumes and external tables, not for managed tables."

    **Why:** Unity Catalog governs managed tables through names (permissions, lineage, catalog commits). Use `spark.read.table("shop.silver.orders")`.

**Q13. Bronze receives a new JSON field `channel`. Write the PySpark append that adds the column to `bronze_orders` instead of failing.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (`ch04_10_answers.py`)

    ```python
    (df.write.format("delta")
       .mode("append")
       .option("mergeSchema", "true")
       .saveAsTable("bronze_orders"))
    ```

    On Databricks Runtime 18.1 and above the SQL form is `INSERT WITH SCHEMA EVOLUTION INTO bronze_orders SELECT ...`.

    **Why:** without the option, schema enforcement rejects the write (the run showed `DELTA_METADATA_MISMATCH`). The new column goes at the end of the schema, and old rows read `NULL`.

**Q14. After the append in Q13, what does `SELECT channel FROM bronze_orders` return for rows written before the change?**

??? success "Answer"
    `NULL`. The old Parquet files do not contain the column, and readers fill missing columns with `NULL`. In the section 4.6 run, Ana Ruiz's row shows `country = NULL` after `mergeSchema` added `country`.

    **Why:** schema evolution is a metadata change; it does not rewrite old files.

**Q15. `ALTER TABLE customers RENAME COLUMN city TO town` fails with `DELTA_UNSUPPORTED_RENAME_COLUMN`. Fix it.**

??? success "Answer"
    Enable column mapping, then rename:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (`ch04_04_schema.py`)

    ```sql
    ALTER TABLE customers SET TBLPROPERTIES ('delta.columnMapping.mode' = 'name');
    ALTER TABLE customers RENAME COLUMN city TO town;
    ```

    **Why:** Parquet stores columns by name, so a rename needs a mapping from logical to physical names. Column mapping requires reader version 2 and writer version 5 or above, so check external readers first; it can also break streaming reads (use `schemaTrackingLocation`) and change data feed consumers.

**Q16. You dropped a column containing personal data with `ALTER TABLE ... DROP COLUMN`. Is the data gone from storage?**

??? success "Answer"
    No. With column mapping the drop is metadata-only; the values are still in the Parquet files. Run `REORG TABLE t APPLY (PURGE)` to rewrite the current files without the column, then `VACUUM` after the retention period to delete the old files.

    **Why:** both steps are needed: `REORG` cleans the current version, `VACUUM` removes the older files that time travel could still read.

**Q17. What is the difference between column mapping `name` and `id` mode?**

??? success "Answer"
    Both allow metadata-only renames and drops and special characters in names. `name` mode can be set on new or existing tables. `id` mode can only be set when the table is created. Databricks recommends `id` mode for most cases for compatibility; `name` mode is set automatically when Iceberg reads are enabled without a mode.

    **Why:** existing tables can only move to `name` mode, which is why the run used it.

**Q18. A column `qty INT` must become `BIGINT`. What are your options on Databricks?**

??? success "Answer"
    Enable type widening (`delta.enableTypeWidening = true`, Databricks Runtime 15.4 LTS and above) and widen the type without rewriting files; `INT` to `BIGINT` is a supported change. Otherwise rewrite the table: read it, cast the column, and write with `.mode("overwrite").option("overwriteSchema", "true")`.

    **Why:** type widening upgrades the protocol (external readers must support it); the rewrite is universal but rewrites all data and conflicts with concurrent writes.

**Q19. A `MERGE` fails with `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`. Why?**

??? success "Answer"
    Two or more source rows match the same target row, so the update is ambiguous. Deduplicate the source first, for example keep the latest row per key with `QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY updated_at DESC) = 1`.

    **Why:** the `MERGE INTO` reference describes this error and says to preprocess the source. Chapter 9 works through it.

**Q20. Write a query that returns `orders` as it was at a given time, in SQL and in PySpark.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (`ch04_10_answers.py`, on its `silver_orders` table)

    ```sql
    SELECT * FROM orders TIMESTAMP AS OF '2026-11-11 05:38:19';
    ```

    ```python
    spark.read.option("timestampAsOf", "2026-11-11 05:38:19").table("orders")
    ```

    For "yesterday at this time" use an expression, as the Databricks history page shows: `TIMESTAMP AS OF current_timestamp() - INTERVAL 1 DAY` (or `date_sub(current_date(), 1)` for yesterday's date). In the run, the timestamp taken before an `INSERT` returned 1 row while the current table had 2.

    **Why:** the timestamp can be any expression castable to a timestamp, but not a subquery. It works only if that version's log entries and data files still exist (and, on Databricks Runtime 18.0 and above, the version is within `deletedFileRetentionDuration`).

**Q21. Someone ran `DELETE FROM silver.orders` without a `WHERE`. Recover the table.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1* (`ch04_05_dml_history.py`, with the local table name `orders`).

    ```sql
    DESCRIBE HISTORY silver.orders;                     -- find the version before the DELETE
    RESTORE TABLE silver.orders TO VERSION AS OF 4;     -- that version
    ```

    In the section 4.7 run, version 5 was the bad `DELETE` and `RESTORE ... VERSION AS OF 4` brought back all four rows.

    **Why:** the deleted data files are still on disk until `VACUUM` removes them after the retention period. Act within the retention window, tell downstream streaming consumers (restored files count as new data), and you need `MODIFY` on the table.

**Q22. After the `RESTORE` in Q21, is the bad `DELETE` gone from `DESCRIBE HISTORY`?**

??? success "Answer"
    No. `RESTORE` adds a new commit (version 6 in the run) with operation `RESTORE` and parameters `{version -> 4, ...}`. The `DELETE` stays at version 5.

    **Why:** the log is append-only. History is an audit trail; restoring is just another change.

**Q23. Only customer 111's rows were deleted by mistake yesterday; other changes since then must be kept. `RESTORE` would undo them. What do you do?**

??? success "Answer"
    Re-insert just those rows from an older version:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (`ch04_10_answers.py`, with `VERSION AS OF 1` instead of yesterday's timestamp)

    ```sql
    INSERT INTO my_table
    SELECT * FROM my_table TIMESTAMP AS OF date_sub(current_date(), 1)
    WHERE userId = 111;
    ```

    **Why:** time travel works as a normal table source in `INSERT` or `MERGE`, so you can repair part of a table. This example is from the Databricks history page.

**Q24. `VACUUM orders RETAIN 0 HOURS` ran with the safety check disabled. What is lost, and what still works?**

??? success "Answer"
    Lost: every data file not referenced by the current version, so all time travel and `RESTORE` to earlier versions fail with missing files. Still works: queries on the current version, and `DESCRIBE HISTORY`, which still lists the old versions because log files are not removed by `VACUUM`. The section 4.8 run shows exactly this. A further risk: if a write was in progress, its not-yet-committed files could have been deleted.

    **Why:** `VACUUM` deletes unreferenced files older than the retention period; with 0 hours, every unreferenced file qualifies immediately.

**Q25. What are the default retention periods, and what do you set to keep 30 days of time travel?**

??? success "Answer"
    `delta.deletedFileRetentionDuration` defaults to 7 days (what `VACUUM` keeps); `delta.logRetentionDuration` defaults to 30 days (how long history is kept). For 30 days of time travel set `delta.deletedFileRetentionDuration = 'interval 30 days'` and keep `logRetentionDuration` at least 30 days.

    **Why:** time travel needs both the log entries and the data files. In Databricks Runtime 18.0 and above, `logRetentionDuration` must be at least `deletedFileRetentionDuration`. Longer retention costs storage.

**Q26. Why does Delta refuse `VACUUM ... RETAIN 0 HOURS` by default?**

??? success "Answer"
    A safety check (`spark.databricks.delta.retentionDurationCheck.enabled`) blocks retention shorter than the configured threshold. Concurrent or long-running writers may have written files they have not committed yet; to `VACUUM` those look unreferenced, so a short retention can delete them and break the writer. It also protects readers using older snapshots and time travel.

    **Why:** the run produced `DELTA_VACUUM_RETENTION_PERIOD_TOO_SHORT`. Databricks strongly recommends at least 7 days.

**Q27. `DESCRIBE HISTORY` lists version 3, but `SELECT * FROM t VERSION AS OF 3` fails with a file-not-found error. How is that possible?**

??? success "Answer"
    `VACUUM` deleted the data files of version 3, but the log entries (which history reads) are kept separately for `logRetentionDuration`. History says the version existed; the files needed to read it are gone.

    **Why:** two separate retention mechanisms: log cleanup after checkpoints, and `VACUUM` for data files.

**Q28. A customer asks to be forgotten. The `customers` table has deletion vectors enabled. List the steps to remove the data physically.**

??? success "Answer"
    1. `DELETE FROM customers WHERE customer_id = 42;` (writes a deletion vector; data still in the file).
    2. `REORG TABLE customers APPLY (PURGE);` (rewrites files that have soft-deleted rows).
    3. After the files expire, `VACUUM customers` to delete the old files from storage.
    Also check other copies: older tables, clones, change data feed files. (Steps 1 to 3 ran in `ch04_10_answers.py`; the `VACUUM` dry run there deletes nothing yet because the files are not 7 days old.)

    **Why:** with deletion vectors a delete is a soft delete. `VACUUM` only removes files older than the retention threshold, so it must run after the `REORG` with enough delay.

**Q29. Does `OPTIMIZE` change query results? What do its log entries look like, and what does a streaming reader do with them?**

??? success "Answer"
    No; it only rewrites small files into larger ones. Its commit has `add` and `remove` actions with `dataChange=false` (seen in the section 4.9 run). Streaming readers skip such commits, so `OPTIMIZE` on a streaming source does not cause duplicates.

    **Why:** `dataChange=false` means the commit "only rearranges existing data or adds new statistics."

**Q30. After running `OPTIMIZE` on a table with thousands of small files, storage usage went up. Why?**

??? success "Answer"
    `OPTIMIZE` writes new large files and marks the small ones `remove`, but it does not delete them. Both copies exist until `VACUUM` deletes the old files after the retention period.

    **Why:** the old files are still needed for time travel to versions before the `OPTIMIZE`.

**Q31. A table has 1 GB Parquet files. You delete one row. What is written with and without deletion vectors?**

??? success "Answer"
    Without: the whole file containing the row is rewritten without it (a new file of about 1 GB plus a `remove` of the old one). With deletion vectors: a small deletion vector file marks the row's position, and the log re-adds the same data file with a `deletionVector` descriptor. The section 4.9 run deleted 1 of 1,000 rows and wrote only one small `.bin` file.

    **Why:** deletion vectors trade a cheap write for a little extra work at read time until a later `OPTIMIZE` or `REORG` rewrites the file.

**Q32. After you enabled deletion vectors, an external tool can no longer read the table. Why, and what can you do?**

??? success "Answer"
    Enabling deletion vectors upgraded the protocol to reader version 3 / writer version 7 with the `deletionVectors` reader feature. Clients without support cannot read it. Upgrade the client (open-source Delta reads deletion vectors from 2.3.0), or on Databricks Runtime 16.4 LTS and above run `ALTER TABLE t DROP FEATURE deletionVectors`, which rewrites files and downgrades the protocol.

    **Why:** "most protocol version upgrades are irreversible"; turning the property off does not downgrade the protocol, only `DROP FEATURE` does.

**Q33. What is the difference between a reader feature and a writer feature?**

??? success "Answer"
    A writer feature (for example `CHECK` constraints or in-commit timestamps) changes how data must be written; older clients can still read the table. A reader feature (for example deletion vectors, column mapping, type widening) changes how data must be read, so clients must support it to read or write. Table features require `minReaderVersion` 3 (for reader features) and `minWriterVersion` 7.

    **Why:** this decides who breaks when you enable a feature: only writers, or everyone.

**Q34. After a `RESTORE`, a downstream streaming job that reads the table produced duplicate rows. Why?**

??? success "Answer"
    `RESTORE` re-adds the old data files with `dataChange = true`, so the stream sees them as newly added data and processes them again.

    **Why:** Databricks warns that restore "might result in duplicate data for downstream workloads". Plan a downstream fix (rebuild or deduplicate) when you restore a streaming source.

**Q35. On Databricks Runtime 18, a time travel query to a version 10 days old fails, although `logRetentionDuration` is 30 days and `VACUUM` has not run. Why?**

??? success "Answer"
    In Databricks Runtime 18.0 and above (12.2 LTS and above for Unity Catalog managed tables), time travel is blocked for versions older than `delta.deletedFileRetentionDuration`, 7 days by default. Raise that property if you need 10 days.

    **Why:** Databricks ties time travel to the data retention window so queries do not depend on whether `VACUUM` happened to run.

**Q36. What causes `ConcurrentTransactionException`?**

??? success "Answer"
    Two streaming queries using the same checkpoint location started at the same time and both tried to write to the Delta table. Never run two streams with the same checkpoint location.

    **Why:** the checkpoint plus the transaction identifiers in the log make streaming writes exactly-once; two streams sharing one checkpoint break that.

**Q37. How do you check whether a table suffers from small files, and which table features it uses?**

??? success "Answer"
    `DESCRIBE DETAIL t`: `numFiles` and `sizeInBytes` give the average file size; `minReaderVersion`, `minWriterVersion` and `tableFeatures` show the protocol. In the section 4.9 run, six tiny inserts gave `numFiles = 6`, and `OPTIMIZE` brought it to 1.

    **Why:** many files far smaller than the target size mean slow reads; run `OPTIMIZE` (or let predictive optimization do it on Unity Catalog managed tables).

**Q38. In a commit's `commitInfo`, what do `readVersion` and `isBlindAppend` tell you?**

??? success "Answer"
    `readVersion` is the table version the operation read before writing (the snapshot it validated against). `isBlindAppend = true` means the operation only added data without reading the table, such as a plain `INSERT`. In the section 4.2 run the `UPDATE` had `readVersion 2` and `isBlindAppend false`; the inserts were blind appends.

    **Why:** blind appends cannot conflict with other writes under WriteSerializable, while operations that read can.

**Q39. Is Delta Lake a Databricks-only format? Name three things Databricks adds on top.**

??? success "Answer"
    No. Delta Lake is open source with an open transaction log protocol, and other engines can read and write it if they support the table's features. Databricks adds, for example, Photon (Databricks-native engine), the disk cache ("a proprietary Databricks feature"), low shuffle merge, predictive optimization, automatic upgrades, and for Unity Catalog managed tables catalog commits and multi-statement transactions.

    **Why:** interviewers check that you separate the open format from the platform features around it.

## Sources

- [What is Delta Lake in Databricks?](https://docs.databricks.com/aws/en/delta/) (last updated Sep 11, 2026)
- [What are ACID guarantees on Databricks?](https://docs.databricks.com/aws/en/lakehouse/acid) (last updated Oct 19, 2026)
- [Isolation levels and write conflicts](https://docs.databricks.com/aws/en/optimizations/isolation/) (last updated Oct 12, 2026)
- [Isolation levels (WriteSerializable and Serializable)](https://docs.databricks.com/aws/en/optimizations/isolation/isolation-levels) (last updated Oct 12, 2026)
- [Row-level concurrency](https://docs.databricks.com/aws/en/optimizations/isolation/row-level-concurrency) (last updated Oct 12, 2026)
- [Work with table history](https://docs.databricks.com/aws/en/tables/history) (last updated Nov 6, 2026)
- [RESTORE](https://docs.databricks.com/aws/en/sql/language-manual/delta-restore) (last updated Sep 11, 2026)
- [Remove unused data files with vacuum](https://docs.databricks.com/aws/en/tables/operations/vacuum) (last updated Nov 6, 2026)
- [VACUUM](https://docs.databricks.com/aws/en/sql/language-manual/delta-vacuum) (last updated Sep 11, 2026)
- [Optimize data file layout](https://docs.databricks.com/aws/en/tables/operations/optimize) (last updated Sep 11, 2026)
- [Deletion vectors in Databricks](https://docs.databricks.com/aws/en/tables/features/deletion-vectors) (last updated Nov 6, 2026)
- [Auto-enable deletion vectors](https://docs.databricks.com/aws/en/admin/workspace-settings/deletion-vectors) (last updated Sep 11, 2026)
- [Schema enforcement](https://docs.databricks.com/aws/en/tables/schema-enforcement) (last updated Sep 11, 2026)
- [Update table schemas with schema evolution](https://docs.databricks.com/aws/en/tables/update-schema) (last updated Sep 11, 2026)
- [Rename and drop columns with Delta Lake column mapping](https://docs.databricks.com/aws/en/tables/features/column-mapping) (last updated Sep 11, 2026)
- [Type widening](https://docs.databricks.com/aws/en/tables/features/type-widening) (last updated Oct 30, 2026)
- [Delta Lake feature compatibility and protocols](https://docs.databricks.com/aws/en/tables/features/feature-compatibility) (last updated Oct 28, 2026)
- [Drop a Delta Lake table feature and downgrade table protocol](https://docs.databricks.com/aws/en/tables/features/drop-feature) (last updated Oct 28, 2026)
- [Review table details with describe detail](https://docs.databricks.com/aws/en/tables/operations/table-details) (last updated Sep 11, 2026)
- [Table properties reference](https://docs.databricks.com/aws/en/tables/table-properties) (last updated Nov 5, 2026)
- [Tutorial: Create and manage Delta Lake tables](https://docs.databricks.com/aws/en/delta/tutorial) (last updated Oct 6, 2026)
- [`MERGE INTO`](https://docs.databricks.com/aws/en/sql/language-manual/delta-merge-into) (last updated Sep 11, 2026)
- [Unity Catalog managed tables for Delta Lake and Apache Iceberg](https://docs.databricks.com/aws/en/tables/managed) (last updated Nov 9, 2026)
- [Work with external tables](https://docs.databricks.com/aws/en/tables/external) (last updated Oct 6, 2026)
- [Delta Lake limitations on S3](https://docs.databricks.com/aws/en/delta/s3-limitations) (last updated Nov 2, 2026)
- [Use change data feed on Databricks](https://docs.databricks.com/aws/en/tables/features/change-data-feed) (last updated Oct 9, 2026)
- [Automatic upgrades](https://docs.databricks.com/aws/en/tables/automatic-upgrades) (last updated Nov 9, 2026)
- [Optimize performance with caching on Databricks](https://docs.databricks.com/aws/en/optimizations/disk-cache) (last updated Oct 22, 2026)
- [What is Photon?](https://docs.databricks.com/aws/en/compute/photon) (last updated Sep 11, 2026)
- [Low shuffle merge on Databricks](https://docs.databricks.com/aws/en/optimizations/low-shuffle-merge) (last updated Oct 12, 2026)
- [Predictive optimization for Unity Catalog managed tables](https://docs.databricks.com/aws/en/optimizations/predictive-optimization) (last updated Nov 6, 2026)
- [Delta Transaction Log Protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md) (open-source specification on GitHub, master branch; the page shows no last-updated date; read Nov 11, 2026)
- [Table batch reads and writes](https://github.com/delta-io/delta/blob/master/docs/src/content/docs/delta-batch.mdx) (open-source Delta Lake documentation source on GitHub, master branch; no last-updated date shown; read Nov 11, 2026)
- [Concurrency control](https://github.com/delta-io/delta/blob/master/docs/src/content/docs/concurrency-control.mdx) (open-source Delta Lake documentation source on GitHub, master branch; no last-updated date shown; read Nov 11, 2026)
