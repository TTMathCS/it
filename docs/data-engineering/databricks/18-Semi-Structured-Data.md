# 18. Nested and semi-structured data

*Real data rarely arrives as flat rows. A Red Rock Supply order is one JSON document with a list of items, a
shipping address and a bag of tags, and a data engineer has to land it, query it, flatten it into tables and
sometimes put it back together. This chapter covers the Databricks tools for that work: the complex types
`STRUCT`, `ARRAY` and `MAP`; JSON kept as text; the `VARIANT` type that Databricks now recommends over JSON strings;
`explode` and its relatives; and the higher-order functions that work on arrays without exploding them. Interviewers
like this topic because it shows quickly whether you understand row counts, NULLs and types, not only syntax.*

!!! abstract "In this chapter"
    **You will learn:**

    - how `STRUCT`, `ARRAY` and `MAP` model one order, how to build them and how to read from them safely;
    - how to parse JSON strings with `from_json`, `get_json_object`, `json_tuple` and the `:` operator, and turn
      data back into JSON with `to_json`;
    - what `VARIANT` is, why Databricks recommends it over JSON strings, and how to query it with `:`, `::`,
      `variant_get`, `try_variant_get`, `schema_of_variant` and `variant_explode`;
    - how `explode`, `explode_outer`, `posexplode` and `inline` change row counts, and why the table-valued form in
      `FROM` replaces `LATERAL VIEW`;
    - how to flatten an order into `order_items` rows and rebuild the nested array;
    - higher-order functions with lambdas (`transform`, `filter`, `exists`, `forall`, `aggregate`, `zip_with`,
      `array_sort`, the map functions) and the array set functions;
    - the same tasks in the PySpark DataFrame API.

    **You need:** [Chapter 3 (Apache Spark)](03-Apache-Spark.md), [Chapter 4 (Delta Lake)](04-Delta-Lake.md) and
    [Chapter 7 (the medallion architecture)](07-Medallion-Architecture.md). [Chapter 8](08-Bronze-Ingestion.md) shows
    how the JSON files reach bronze; this chapter starts once they are there.

    **Levels:** sections 18.1 to 18.3 beginner, 18.4 to 18.7 intermediate, 18.8 to 18.10 expert.

All runnable examples use six lines of Red Rock Supply order JSON, saved as a file and loaded into a Delta table
`bronze_orders_raw` with one `STRING` column `raw` per line. Locally there is no Unity Catalog, so tables have
one-part names (`bronze_orders_raw`, `silver_orders`); on Databricks they would be `shop.bronze.orders_raw` and so
on. The first line is the brief's sample order with two fields added: a `ship_to` object and a `tags` object.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```json
{"order_id": 1001, "customer_id": 7, "order_ts": "2026-03-01T10:15:00Z", "status": "PLACED", "amount": "59.90", "currency": "CAD", "items": [{"product_id": 3, "qty": 2, "unit_price": "29.95"}], "ship_to": {"street": "12 Canyon Rd", "city": "Calgary", "region": "AB", "country": "CA"}, "tags": {"channel": "web", "promo": "SPRING10"}}
```

The other lines are chosen to break things: order 1002 has two items, 1003 has an empty `items` array, 1004 has
three items, an extra `gift_note` field and a `gift` tag, 1005 has no `items` key at all, no street and
`"tags": null`, and line 6 (order 1006) is cut off in the middle, as happens when a producer crashes. The full data
and the helper code are in `src/ch18/ch18_data.py`.

## 18.1 Why nested data needs its own tools

*Level: beginner.*

A relational model would split one order into an `orders` row, several `order_items` rows and maybe a `tags` table.
The source system does not do that for you: it sends one document per order. You can either flatten it immediately
or keep it nested for a while. Both are legitimate, and Databricks gives you four ways to store the nested part.
The page [Model semi-structured data](https://docs.databricks.com/aws/en/semi-structured/) compares them; this table
copies its wording:

| Approach | Best for | Schema handling | Performance |
| --- | --- | --- | --- |
| Variant | Semi-structured JSON that benefits from optimized storage | Flexible, with similar applications to JSON strings | Optimized encoding that outperforms JSON strings on read and write |
| JSON strings | Capturing a complete, accurate representation of raw source data | No type information and no pre-processing required | Worst on read, because the entire string is parsed for every query |
| Structs | Data with well-known schemas where you want validated data | Enforced on write; requires pre-processing; less flexible for schema evolution | Best on read, but degrades past hundreds of columns |
| Maps and arrays | Semi-structured datasets with around 500 fields | Keys and values are typed and enforced on write | Balanced on read and write, but statistics can't be collected |

Three points from the same page matter for design questions:

- In a Delta table, each field of a struct becomes its own Parquet column, so struct fields can be clustering keys
  and get statistics for data skipping. You cannot partition by a struct field.
- Statistics, partitioning and clustering are not available for fields inside JSON strings or maps, so the page
  advises storing fields that you filter on often as separate top-level columns.
- Whichever pattern you choose, Databricks recommends storing the data as Delta tables.

The rest of the chapter goes from typed shapes (structs, arrays, maps) to untyped ones (JSON strings, `VARIANT`),
then to the operations that move data between nested and flat.

## 18.2 STRUCT, ARRAY and MAP

*Level: beginner.*

A **STRUCT** is a fixed set of named fields, each with its own type, like a row inside a column: the shipping
address. An **ARRAY** is an ordered list of elements of one type: the order lines. A **MAP** is a set of key-value
pairs where all keys share one type and all values share one type: free-form tags. The type pages define the
syntax as `STRUCT < [fieldName [:] fieldType [NOT NULL] [COLLATE collationName] [COMMENT str] [, ...] ] >`,
`ARRAY < elementType >` and `MAP <keyType, valueType>`. Map keys "must be unique and not be NULL", and "`MAP` is
not a comparable data type" ([MAP type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/map-type)).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 290" role="img" aria-label="Order 1002 drawn as three shapes: a struct with four named fields, an array with two indexed struct elements, and a map with one key and value">
<text x="320" y="22" text-anchor="middle" font-size="15" fill="currentColor">Order 1002: three nested shapes in one row</text>
<rect x="15" y="40" width="190" height="170" rx="6" fill="none" stroke="currentColor"/>
<text x="110" y="62" text-anchor="middle" font-size="14" fill="currentColor">STRUCT ship_to</text>
<line x1="15" y1="72" x2="205" y2="72" stroke="currentColor"/>
<text x="27" y="96" font-size="13" fill="currentColor">street: 4 Banff Ave</text>
<text x="27" y="122" font-size="13" fill="currentColor">city: Banff</text>
<text x="27" y="148" font-size="13" fill="currentColor">region: AB</text>
<text x="27" y="174" font-size="13" fill="currentColor">country: CA</text>
<text x="27" y="198" font-size="13" fill="currentColor">(fixed names, own types)</text>
<rect x="225" y="40" width="200" height="170" rx="6" fill="none" stroke="currentColor"/>
<text x="325" y="62" text-anchor="middle" font-size="14" fill="currentColor">ARRAY items</text>
<line x1="225" y1="72" x2="425" y2="72" stroke="currentColor"/>
<rect x="237" y="84" width="176" height="44" rx="4" fill="none" stroke="currentColor"/>
<text x="245" y="111" font-size="13" fill="currentColor">[0] {1, 1, 149.00}</text>
<rect x="237" y="138" width="176" height="44" rx="4" fill="none" stroke="currentColor"/>
<text x="245" y="165" font-size="13" fill="currentColor">[1] {5, 3, 12.50}</text>
<text x="245" y="200" font-size="13" fill="currentColor">(ordered, one type)</text>
<rect x="445" y="40" width="180" height="170" rx="6" fill="none" stroke="currentColor"/>
<text x="535" y="62" text-anchor="middle" font-size="14" fill="currentColor">MAP tags</text>
<line x1="445" y1="72" x2="625" y2="72" stroke="currentColor"/>
<text x="457" y="111" font-size="13" fill="currentColor">channel -&gt; mobile</text>
<text x="457" y="200" font-size="13" fill="currentColor">(keys unique, not NULL)</text>
<text x="110" y="238" text-anchor="middle" font-size="13" fill="currentColor">ship_to.city</text>
<text x="325" y="238" text-anchor="middle" font-size="13" fill="currentColor">items[0].qty</text>
<text x="325" y="258" text-anchor="middle" font-size="13" fill="currentColor">element_at(items, 1).qty</text>
<text x="535" y="238" text-anchor="middle" font-size="13" fill="currentColor">tags['channel']</text>
<text x="320" y="282" text-anchor="middle" font-size="13" fill="currentColor">Array brackets count from 0; element_at counts from 1.</text>
</svg>
<figcaption>Figure 18.1. One order row holds a struct, an array of structs and a map, each read with its own syntax.</figcaption>
</figure>

### Constructors

`named_struct('name', value, ...)` builds a struct with the names you give. `struct(expr, ...)` takes names from
column references or `AS` aliases and otherwise names the fields `col1`, `col2` and so on
([struct function](https://docs.databricks.com/aws/en/sql/language-manual/functions/struct)). `array(...)` and
`map(key, value, ...)` build the other two. Availability, as the pages state it: `struct`, `named_struct` and `map`
apply to "Databricks SQL Databricks Runtime"; `array` to "Databricks SQL Databricks Runtime 11.3 LTS and above".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT named_struct('city', 'Calgary', 'region', 'AB')      AS ship_to,
       array(3, 5, 8)                                       AS product_ids,
       map('channel', 'web', 'promo', 'SPRING10')           AS tags;

SELECT typeof(named_struct('city', 'Calgary', 'region', 'AB')) AS t_struct,
       typeof(array(3, 5, 8))                                  AS t_array,
       typeof(map('channel', 'web'))                           AS t_map;
```

```text
+-------------+-----------+-----------------------------------+
|ship_to      |product_ids|tags                               |
+-------------+-----------+-----------------------------------+
|{Calgary, AB}|[3, 5, 8]  |{channel -> web, promo -> SPRING10}|
+-------------+-----------+-----------------------------------+

+---------------------------------+----------+------------------+
|t_struct                         |t_array   |t_map             |
+---------------------------------+----------+------------------+
|struct<city:string,region:string>|array<int>|map<string,string>|
+---------------------------------+----------+------------------+
```

Columns can be declared with these types directly. The table below holds three orders written with constructors:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE orders_nested (
  order_id INT,
  ship_to  STRUCT<street: STRING, city: STRING, region: STRING, country: STRING>,
  items    ARRAY<STRUCT<product_id: INT, qty: INT, unit_price: DECIMAL(10,2)>>,
  tags     MAP<STRING, STRING>
) USING DELTA;

INSERT INTO orders_nested VALUES
  (1001, named_struct('street', '12 Canyon Rd', 'city', 'Calgary', 'region', 'AB', 'country', 'CA'),
         array(named_struct('product_id', 3, 'qty', 2, 'unit_price', 29.95)),
         map('channel', 'web', 'promo', 'SPRING10')),
  (1002, named_struct('street', '4 Banff Ave', 'city', 'Banff', 'region', 'AB', 'country', 'CA'),
         array(named_struct('product_id', 1, 'qty', 1, 'unit_price', 149.00),
               named_struct('product_id', 5, 'qty', 3, 'unit_price', 12.50)),
         map('channel', 'mobile')),
  (1003, named_struct('street', '12 Canyon Rd', 'city', 'Calgary', 'region', 'AB', 'country', 'CA'),
         array(),
         map('channel', 'web'));

SELECT * FROM orders_nested ORDER BY order_id;
```

```text
+--------+-------------------------------+-------------------------------+-----------------------------------+
|order_id|ship_to                        |items                          |tags                               |
+--------+-------------------------------+-------------------------------+-----------------------------------+
|1001    |{12 Canyon Rd, Calgary, AB, CA}|[{3, 2, 29.95}]                |{channel -> web, promo -> SPRING10}|
|1002    |{4 Banff Ave, Banff, AB, CA}   |[{1, 1, 149.00}, {5, 3, 12.50}]|{channel -> mobile}                |
|1003    |{12 Canyon Rd, Calgary, AB, CA}|[]                             |{channel -> web}                   |
+--------+-------------------------------+-------------------------------+-----------------------------------+
```

### Reading values: dot, brackets and element_at

- `struct.field` reads a field. The [dot sign page](https://docs.databricks.com/aws/en/sql/language-manual/functions/dotsign)
  says Databricks checks that the field exists when the statement is compiled. `struct['field']` also worked on the
  local engine (the run below), but the [bracket sign page](https://docs.databricks.com/aws/en/sql/language-manual/functions/bracketsign)
  documents brackets only for arrays and maps, so that form is not verified on Databricks.
- `array[i]` counts from **0**. `element_at(array, i)` counts from **1**, and a negative index counts from the end.
- `map['key']`, `map.key` (string keys only) and `element_at(map, key)` read a map value; a missing key gives NULL.
- `array_of_structs.field` returns an array of that field from every element, for example `items.product_id`.
- `struct.*` expands a struct into one column per field.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id,
       ship_to.city,
       ship_to['region']                AS region,
       items[0].qty                     AS first_qty,
       element_at(items, 1).qty         AS first_qty_1based,
       element_at(items, -1).product_id AS last_product,
       items.product_id                 AS all_products,
       tags['promo']                    AS promo,
       tags.channel                     AS channel
FROM orders_nested WHERE order_id IN (1001, 1002) ORDER BY order_id;
```

```text
+--------+-------+------+---------+----------------+------------+------------+--------+-------+
|order_id|city   |region|first_qty|first_qty_1based|last_product|all_products|promo   |channel|
+--------+-------+------+---------+----------------+------------+------------+--------+-------+
|1001    |Calgary|AB    |2        |2               |3           |[3]         |SPRING10|web    |
|1002    |Banff  |AB    |1        |1               |5           |[1, 5]      |NULL    |mobile |
+--------+-------+------+---------+----------------+------------+------------+--------+-------+
```

The query filtered out order 1003 on purpose. Run the same thing over the whole table and the empty array in 1003
stops the query:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, items[0].qty AS first_qty FROM orders_nested;
-- ERROR: [INVALID_ARRAY_INDEX] The index 0 is out of bounds. The array has 0 elements.
-- Use the SQL function `get()` to tolerate accessing element at invalid index and return NULL instead.

SELECT order_id, get(items, 0).qty                  AS first_qty,
                 try_element_at(items, 1).qty       AS first_qty_1based,
                 try_element_at(items, -1).product_id AS last_product
FROM orders_nested ORDER BY order_id;
```

```text
+--------+---------+----------------+------------+
|order_id|first_qty|first_qty_1based|last_product|
+--------+---------+----------------+------------+
|1001    |2        |2               |3           |
|1002    |1        |1               |5           |
|1003    |NULL     |NULL            |NULL        |
+--------+---------+----------------+------------+
```

The rules come from the function pages. `array[i]` out of bounds raises `INVALID_ARRAY_INDEX`
([bracket sign](https://docs.databricks.com/aws/en/sql/language-manual/functions/bracketsign)).
`element_at` raises `INVALID_INDEX_OF_ZERO` for index 0 and `INVALID_ARRAY_INDEX_IN_ELEMENT_AT` when the index is
past the end ([element_at](https://docs.databricks.com/aws/en/sql/language-manual/functions/element_at)).
`get(array, index)` counts from 0 and returns NULL outside the bounds; it applies to "Databricks SQL Databricks
Runtime 11.3 LTS and above" ([get](https://docs.databricks.com/aws/en/sql/language-manual/functions/get)).
`try_element_at` counts from 1 and returns NULL; it applies to "Databricks SQL Databricks Runtime 10.4 LTS and above"
([try_element_at](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_element_at)). The pages add
that in Databricks Runtime, with `spark.sql.ansi.enabled` set to `false`, the bracket operator returns NULL instead
of failing, and `element_at` returns NULL when `spark.sql.ansi.failOnElementNotExists` is `false`. The local engine
runs with ANSI mode on, which is the behavior shown here.

!!! warning "One short array fails the whole job"
    `items[0]` works in every test where each order has at least one line, then fails in production on the first
    cancelled order with an empty array. In silver code, use `get`, `try_element_at`, or a `size(items) > 0` guard.

### size and cardinality

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, size(items) AS n_items, cardinality(tags) AS n_tags,
       map_keys(tags) AS tag_keys, map_values(tags) AS tag_values
FROM orders_nested ORDER BY order_id;

SELECT size(CAST(NULL AS ARRAY<INT>)) AS size_of_null;
```

```text
+--------+-------+------+----------------+---------------+
|order_id|n_items|n_tags|tag_keys        |tag_values     |
+--------+-------+------+----------------+---------------+
|1001    |1      |2     |[channel, promo]|[web, SPRING10]|
|1002    |2      |1     |[channel]       |[mobile]       |
|1003    |0      |1     |[channel]       |[web]          |
+--------+-------+------+----------------+---------------+

+------------+
|size_of_null|
+------------+
|NULL        |
+------------+
```

`size` and `cardinality` both return the number of elements of an array or entries of a map. The
[size page](https://docs.databricks.com/aws/en/sql/language-manual/functions/size) notes that in Databricks
Runtime, when `spark.sql.ansi.enabled` is `false`, `size(NULL)` returns `-1` instead of `NULL` (its example shows
`-1`). With ANSI on, as here, it is NULL. A test such as `size(items) > 0` therefore treats a NULL array the same
in both modes (`-1 > 0` and `NULL > 0` both reject the row), but `size(items) = 0` does not.

Two more errors to know: building a map with a duplicate key raises `DUPLICATED_MAP_KEY`, and comparing maps
raises a type error, because `MAP` is not comparable:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT map('channel', 'web', 'channel', 'store');
-- ERROR: [DUPLICATED_MAP_KEY] Duplicate map key channel was found, please check the input data. ...

SELECT * FROM orders_nested WHERE tags = map('channel', 'web');
-- ERROR: [DATATYPE_MISMATCH.INVALID_ORDERING_TYPE] Cannot resolve "(tags = map(channel, web))" due to data type
-- mismatch: The `=` does not support ordering on type "MAP<STRING, STRING>".
```

!!! tip "In the interview"
    **"When would you use a STRUCT and when a MAP?"** A struct has a fixed, known set of fields, each with its own
    type, and Delta stores each field as its own column, so it gets statistics and can be a clustering key. A map
    is for an open-ended set of keys that all share one value type, such as tags or attributes; the keys are data,
    not schema, and statistics cannot be collected on it. Address is a struct; tags are a map.

## 18.3 JSON kept as a string

*Level: beginner.*

The simplest bronze table stores each JSON document as a `STRING`. Ingestion cannot fail on a type problem and the
raw record is kept exactly, which is why the semi-structured page lists Kafka messages, REST API responses and
upstream records you do not control as good uses. The cost comes later: every query parses the text again.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE bronze_orders_raw USING DELTA AS
SELECT value AS raw FROM text.`<landing folder>/orders.json`;

SELECT substr(raw, 1, 60) AS raw_start, length(raw) AS len FROM bronze_orders_raw;
```

```text
+------------------------------------------------------------+---+
|raw_start                                                   |len|
+------------------------------------------------------------+---+
|{"order_id": 1001, "customer_id": 7, "order_ts": "2026-03-01|333|
|{"order_id": 1002, "customer_id": 12, "order_ts": "2026-03-0|368|
|{"order_id": 1003, "customer_id": 7, "order_ts": "2026-03-02|264|
|{"order_id": 1004, "customer_id": 7, "order_ts": "2026-03-02|458|
|{"order_id": 1005, "customer_id": 33, "order_ts": "2026-03-0|210|
|{"order_id": 1006, "customer_id": 7, "status": "PLACED", "am|102|
+------------------------------------------------------------+---+
```

(On Databricks you would load files with Auto Loader or `read_files`; see [Chapter 8](08-Bronze-Ingestion.md).)

### from_json: text to typed struct

`from_json(jsonStr, schema [, options])` returns a struct shaped by the schema you give, written like a column list
in `CREATE TABLE` ([from_json](https://docs.databricks.com/aws/en/sql/language-manual/functions/from_json)). It
applies to "Databricks SQL Databricks Runtime"; the page adds that before Databricks Runtime 12.2 the schema had to be
a literal. `schema_of_json` infers a schema from one sample document and returns it in DDL form, which is a quick way
to draft the schema:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT schema_of_json('{"order_id": 1001, "amount": "59.90", "items": [{"product_id": 3, "qty": 2}],
                        "tags": {"channel": "web"}}') AS inferred;
```

```text
+------------------------------------------------------------------------------------------------------------------------------+
|inferred                                                                                                                      |
+------------------------------------------------------------------------------------------------------------------------------+
|STRUCT<amount: STRING, items: ARRAY<STRUCT<product_id: BIGINT, qty: BIGINT>>, order_id: BIGINT, tags: STRUCT<channel: STRING>>|
+------------------------------------------------------------------------------------------------------------------------------+
```

Inference guesses: `amount` is a string because the source quotes it, integers become `BIGINT`, and `tags` becomes a
struct with one field because the sample had one key. For silver you write the schema yourself, choosing a `MAP` for
the open-ended tags and `DECIMAL` for money:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE OR REPLACE TEMP VIEW parsed AS
SELECT from_json(raw,
  'order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING,
   amount DECIMAL(10,2), currency STRING,
   items ARRAY<STRUCT<product_id: INT, qty: INT, unit_price: DECIMAL(10,2)>>,
   ship_to STRUCT<street: STRING, city: STRING, region: STRING, country: STRING>,
   tags MAP<STRING, STRING>') AS o
FROM bronze_orders_raw;

SELECT o.order_id, o.order_ts, o.amount, o.items, o.ship_to.city, o.tags FROM parsed;
```

```text
+--------+-------------------+------+--------------------------------------------+-------+-----------------------------------+
|order_id|order_ts           |amount|items                                       |city   |tags                               |
+--------+-------------------+------+--------------------------------------------+-------+-----------------------------------+
|1001    |2026-03-01 10:15:00|59.90 |[{3, 2, 29.95}]                             |Calgary|{channel -> web, promo -> SPRING10}|
|1002    |2026-03-01 11:02:00|186.50|[{1, 1, 149.00}, {5, 3, 12.50}]             |Banff  |{channel -> mobile}                |
|1003    |2026-03-02 09:30:00|0.00  |[]                                          |Calgary|{channel -> web}                   |
|1004    |2026-03-02 14:45:00|136.94|[{2, 1, 89.99}, {3, 1, 29.95}, {8, 4, 4.25}]|Moab   |{channel -> store, gift -> yes}    |
|1005    |2026-03-03 08:05:00|45.00 |NULL                                        |Canmore|NULL                               |
|NULL    |NULL               |NULL  |NULL                                        |NULL   |NULL                               |
+--------+-------------------+------+--------------------------------------------+-------+-----------------------------------+
```

Read the last two rows carefully. Order 1005 had no `items` key and `"tags": null`; both became NULL. Line 6 is
malformed, and in the default `PERMISSIVE` mode `from_json` returned a struct whose fields are all NULL: no error, no
warning. The `gift_note` field of order 1004 is gone, because the schema does not name it. That is the trade-off of
structs in one picture: clean types, but anything outside the schema or broken is silently dropped unless you keep
the raw text next to it.

Two details from the from_json page. Field names in the schema "are case-sensitive and must match the names in
`jsonStr` exactly", and the `mode` option can be set to `FAILFAST`, which raises `MALFORMED_RECORD_IN_PARSING`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT from_json('{"order_id": 1001}', 'order_id INT') AS right_case,
       from_json('{"order_id": 1001}', 'Order_ID INT') AS wrong_case;

SELECT from_json('{"order_id": 1006, "items": [', 'order_id INT', map('mode', 'FAILFAST'));
-- ERROR: [MALFORMED_RECORD_IN_PARSING.WITHOUT_SUGGESTION] Malformed records are detected in record parsing: [null].
-- Parse Mode: FAILFAST. ...
```

```text
+----------+----------+
|right_case|wrong_case|
+----------+----------+
|{1001}    |{NULL}    |
+----------+----------+
```

The PySpark form is the same function with the same schema string:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql import functions as F

orders = (spark.table("bronze_orders_raw")
          .select(F.from_json("raw", SILVER_SCHEMA).alias("o"))   # SILVER_SCHEMA = the DDL string above
          .select("o.*")
          .where(F.col("order_id").isNotNull()))
orders.select("order_id", "ship_to.city", F.col("tags")["channel"].alias("channel"),
              F.size("items").alias("n_items")).orderBy("order_id").show(truncate=False)
```

```text
+--------+-------+-------+-------+
|order_id|city   |channel|n_items|
+--------+-------+-------+-------+
|1001    |Calgary|web    |1      |
|1002    |Banff  |mobile |2      |
|1003    |Calgary|web    |0      |
|1004    |Moab   |store  |3      |
|1005    |Canmore|NULL   |NULL   |
+--------+-------+-------+-------+
```

### get_json_object and json_tuple: pick a few fields

`get_json_object(expr, path)` takes a JSONPath rooted at `$` and always returns a `STRING`. Its page now carries a
tip: "For new code, Databricks recommends using the VARIANT data type with the `:` operator to query JSON data"
([get_json_object](https://docs.databricks.com/aws/en/sql/language-manual/functions/get_json_object)). It is still
everywhere in existing code, so know how it behaves:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT get_json_object(raw, '$.order_id')            AS order_id,
       get_json_object(raw, '$.ship_to.city')        AS city,
       get_json_object(raw, '$.items[0].unit_price') AS first_price,
       get_json_object(raw, '$.items[*].product_id') AS product_ids,
       typeof(get_json_object(raw, '$.order_id'))    AS t
FROM bronze_orders_raw;
```

```text
+--------+-------+-----------+-----------+------+
|order_id|city   |first_price|product_ids|t     |
+--------+-------+-----------+-----------+------+
|1001    |Calgary|29.95      |3          |string|
|1002    |Banff  |149.00     |[1,5]      |string|
|1003    |Calgary|NULL       |NULL       |string|
|1004    |Moab   |89.99      |[2,3,8]    |string|
|1005    |Canmore|NULL       |NULL       |string|
|NULL    |NULL   |NULL       |NULL       |string|
+--------+-------+-----------+-----------+------+
```

Look at `product_ids` for order 1001: `3`, not `[3]`. With one matching element, `[*]` returned the bare value
here; with two or more it returned a JSON array. Code that later parses this column as `ARRAY<INT>` breaks on
single-item orders. This was observed on the local engine; the Databricks page does not show the one-element case.

`json_tuple(jsonStr, path1, ...)` extracts several top-level fields at once. Its page says that in Databricks SQL and
Databricks Runtime 12.2 LTS and above, calling it in the `SELECT` list or from `LATERAL VIEW` "is deprecated" and that you should invoke it
as a table reference:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT j.*
FROM bronze_orders_raw b,
     LATERAL json_tuple(b.raw, 'order_id', 'status', 'currency') AS j(order_id, status, currency);
```

```text
+--------+---------+--------+
|order_id|status   |currency|
+--------+---------+--------+
|1001    |PLACED   |CAD     |
|1002    |SHIPPED  |CAD     |
|1003    |CANCELLED|CAD     |
|1004    |PLACED   |USD     |
|1005    |PLACED   |CAD     |
|NULL    |NULL     |NULL    |
+--------+---------+--------+
```

### The `:` operator on a STRING column (Databricks only)

Databricks SQL adds a shorthand: `column:path` reads a field out of a JSON string with a
[JSON path expression](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-json-path-expression). The
[`:` operator page](https://docs.databricks.com/aws/en/sql/language-manual/functions/colonsign) says the argument
can be "A `VARIANT` expression or `STRING` expression with valid JSON" and "The result matches the type of
`jsonExpr`", so on a string column you get a string back and cast it with `::`. On a STRING, identifiers are
matched case-insensitively, bracketed names `['name']` are matched case-sensitively, and `[*]` selects all array
elements. The open-source Spark 4.2 parser here rejects `'{"a":1}':a` (it reads `:a` as a parameter marker), so this
block is Databricks only:

*Databricks only, not run here. Syntax from [Query JSON strings](https://docs.databricks.com/aws/en/semi-structured/json) and [`:` (colon sign) operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/colonsign).*

```sql
SELECT raw:order_id::INT              AS order_id,
       raw:ship_to.city               AS city,          -- STRING
       raw:items[0].unit_price::DECIMAL(10,2) AS first_price,
       raw:items[*].product_id        AS product_ids,   -- JSON text of an array
       raw:['gift_note']              AS gift_note      -- bracket form: case-sensitive
FROM shop.bronze.orders_raw;
```

Per the Query JSON strings page, a JSON `null` value comes back as a SQL `NULL`, and if one record contains two keys
that differ only in case (`{"foo":"bar", "Foo":"bar"}`), the case-insensitive path raises an error asking you to use
brackets.

### to_json: back to text

`to_json` turns a struct (and, in Databricks SQL and Databricks Runtime 15.3 and above, a `VARIANT`) into a JSON
string ([to_json](https://docs.databricks.com/aws/en/sql/language-manual/functions/to_json)). Arrays and maps work
too, as the page's examples show. `to_json(struct(*))` turns a whole row into one document, which is the usual way to
write an outgoing message:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, to_json(ship_to) AS ship_json, to_json(items) AS items_json, to_json(tags) AS tags_json
FROM (SELECT o.* FROM parsed) WHERE order_id IN (1001, 1005);

SELECT to_json(struct(*)) AS row_json
FROM (SELECT o.order_id, o.status, o.amount FROM parsed WHERE o.order_id = 1001);
```

```text
+--------+-----------------------------------------------------------------------+---------------------------------------------+------------------------------------+
|order_id|ship_json                                                              |items_json                                   |tags_json                           |
+--------+-----------------------------------------------------------------------+---------------------------------------------+------------------------------------+
|1001    |{"street":"12 Canyon Rd","city":"Calgary","region":"AB","country":"CA"}|[{"product_id":3,"qty":2,"unit_price":29.95}]|{"channel":"web","promo":"SPRING10"}|
|1005    |{"city":"Canmore","region":"AB","country":"CA"}                        |NULL                                         |NULL                                |
+--------+-----------------------------------------------------------------------+---------------------------------------------+------------------------------------+

+--------------------------------------------------+
|row_json                                          |
+--------------------------------------------------+
|{"order_id":1001,"status":"PLACED","amount":59.90}|
+--------------------------------------------------+
```

`to_json` left out the NULL `street` of order 1005 instead of writing `"street":null`. Consumers that expect every
key must handle a missing key.

!!! tip "In the interview"
    **"from_json returns NULLs for some rows. What happened?"** In the default `PERMISSIVE` mode a malformed record
    becomes a struct of NULLs, and a field whose name differs in case from the schema is also NULL, because schema
    names are case-sensitive. Keep the raw string next to the parsed struct, count rows where the key field is NULL,
    and use `FAILFAST` in a test run if you would rather fail than lose data.

## 18.4 VARIANT: what it is and why Databricks recommends it

*Level: intermediate.*

`VARIANT` is a data type that "Represents semi-structured data"; it can store JSON objects, arrays and scalars in
"an optimized encoding that outperforms JSON strings for reads and writes"
([VARIANT type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/variant-type),
[Model semi-structured data](https://docs.databricks.com/aws/en/semi-structured/)). Unlike a JSON string, the value
is parsed once, when it is written, and each value keeps its JSON type (number, string, boolean, object, array).
Unlike a struct, there is no schema to declare, so a new field in the feed is simply kept.

The recommendation is stated plainly on the [Query variant data](https://docs.databricks.com/aws/en/semi-structured/variant)
page: "Databricks recommends using `VARIANT` over JSON strings for semi-structured data." The
[comparison page](https://docs.databricks.com/aws/en/semi-structured/variant-json-diff) adds that users new to
Databricks "should use variant over JSON strings whenever storing semi-structured data that requires flexibility for
changing or unknown schema", and that its read and write performance lets it replace structs and arrays "in some use
cases". The [ingestion page](https://docs.databricks.com/aws/en/ingestion/variant) describes loading whole JSON
records into one `VARIANT` column with Auto Loader and says the pattern "is robust to most ingestion scenarios",
with two caveats: malformed records cannot be encoded as `VARIANT`, and size limits apply.

That is why `VARIANT` fits bronze: bronze should accept whatever the source sends, keep it complete, and still be
cheap to query while silver is being built. (The docs make the recommendation for semi-structured data in general;
naming the layer is this book's reading of it.)

Availability, as the pages state it, and they do not all agree:

| Page | Says |
| --- | --- |
| [VARIANT type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/variant-type) | Applies to: Databricks SQL, Databricks Runtime 15.3 and above |
| [Query variant data](https://docs.databricks.com/aws/en/semi-structured/variant) | "available in Databricks Runtime 15.4 and above" |
| [Variant type support for Apache Iceberg and Delta Lake](https://docs.databricks.com/aws/en/tables/features/variant) | "You must use Databricks Runtime 15.4 LTS or above to read and write tables with variant support enabled." |
| Function pages (`parse_json`, `try_parse_json`, `variant_get`, `try_variant_get`, `schema_of_variant`, `schema_of_variant_agg`, `variant_explode`, `variant_explode_outer`, `is_variant_null`, `to_variant_object`) | Applies to: Databricks SQL, Databricks Runtime 15.3 and above |

In practice: the functions arrive in 15.3, Delta tables with `VARIANT` columns need 15.4 LTS or above.

### Delta tables with a VARIANT column

Creating a table with a `VARIANT` column enables the Delta table feature `variantType`; for an existing table the
page gives `ALTER TABLE table_name SET TBLPROPERTIES('delta.feature.variantType' = 'supported')` and warns that it
"upgrades the table writer protocol", which can affect external Delta clients
([Variant type support](https://docs.databricks.com/aws/en/tables/features/variant)). The local Delta 4.4.1 engine
shows the same feature:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT parse_json(raw) FROM bronze_orders_raw;
-- ERROR: [MALFORMED_RECORD_IN_PARSING.WITHOUT_SUGGESTION] Malformed records are detected in record parsing:
-- {"order_id": 1006, "customer_id": 7, "status": "PLACED", "amount": "12.50", "items": [{"product_id": 8. ...

CREATE TABLE bronze_orders (order_json VARIANT, raw STRING) USING DELTA;
INSERT INTO bronze_orders SELECT try_parse_json(raw), raw FROM bronze_orders_raw;

SELECT order_json:order_id AS order_id, order_json IS NULL AS parse_failed, substr(raw, 1, 40) AS raw_start
FROM bronze_orders;
SHOW TBLPROPERTIES bronze_orders;
```

```text
+--------+------------+----------------------------------------+
|order_id|parse_failed|raw_start                               |
+--------+------------+----------------------------------------+
|1001    |false       |{"order_id": 1001, "customer_id": 7, "or|
|1002    |false       |{"order_id": 1002, "customer_id": 12, "o|
|1003    |false       |{"order_id": 1003, "customer_id": 7, "or|
|1004    |false       |{"order_id": 1004, "customer_id": 7, "or|
|1005    |false       |{"order_id": 1005, "customer_id": 33, "o|
|NULL    |true        |{"order_id": 1006, "customer_id": 7, "st|
+--------+------------+----------------------------------------+

+-------------------------+---------+
|key                      |value    |
+-------------------------+---------+
|delta.feature.appendOnly |supported|
|delta.feature.invariants |supported|
|delta.feature.variantType|supported|
|delta.minReaderVersion   |3        |
|delta.minWriterVersion   |7        |
+-------------------------+---------+
```

`parse_json(jsonStr)` returns a `VARIANT` and raises `MALFORMED_RECORD_IN_PARSING` on invalid JSON;
`try_parse_json(jsonStr)` returns NULL instead
([parse_json](https://docs.databricks.com/aws/en/sql/language-manual/functions/parse_json),
[try_parse_json](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_parse_json)). One bad line
must not stop a bronze load, so bronze uses `try_parse_json` and keeps the raw text for the rows where it returned
NULL (or sends them to a quarantine table, see [Chapter 9](09-Building-Silver.md)).

On Databricks, Auto Loader can write each whole record into a single `VARIANT` column with the
`singleVariantColumn` option; the page notes that rescued data is then not supported and no schema evolution happens,
because the whole record is one column:

*Databricks only, not run here. Syntax from [Ingest data as semi-structured variant type](https://docs.databricks.com/aws/en/ingestion/variant).*

```python
(spark.readStream
  .format("cloudFiles")
  .option("cloudFiles.format", "json")
  .option("singleVariantColumn", "order_json")
  .load("/Volumes/shop/bronze/landing/orders")
  .writeStream
  .option("checkpointLocation", checkpoint_path)
  .toTable("shop.bronze.orders"))
```

The same page lists the file formats that can be ingested as `VARIANT`: JSON from Databricks Runtime 15.3, XML and
CSV from 16.4.

### Limits

From [Variant type support for Apache Iceberg and Delta Lake](https://docs.databricks.com/aws/en/tables/features/variant)
(last updated Sep 11, 2026):

- You can't use variant columns to partition a table, and a variant column can't be a clustering key (the Query
  variant data page adds Z-order keys).
- You can't use variant columns with `GROUP BY` or `ORDER BY`, call `DISTINCT` on them, or use them with
  `INTERSECT`, `UNION` or `EXCEPT`.
- You can't use column generation to create a variant column.
- Variant columns don't support `minValues` or `maxValues` statistics.
- A variant column can't contain a value larger than 128 MiB (16 MiB in Databricks Runtime 17.1 and below). The
  ingestion page, updated the same day, still says "`VARIANT` type can only hold records up to 16 MB in size", so the
  pages disagree; check the limit for your runtime.
- Iceberg v2 tables do not support `VARIANT` columns; Iceberg v3 does
  ([VARIANT type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/variant-type)).

No min/max statistics means no data skipping on values inside the variant. The ingestion page's note follows from
that: "Databricks recommends extracting frequently queried fields and storing them as non-variant columns to
accelerate queries and optimize storage layout." A common bronze table therefore has `order_id`, `order_ts` and
an ingest timestamp as plain columns next to the `VARIANT`.

!!! tip "In the interview"
    **"Why VARIANT instead of a JSON string in bronze?"** Both accept any JSON without a schema, so ingestion is
    robust to new fields and type changes. A JSON string is parsed again on every query; `VARIANT` is parsed once on
    write into an optimized encoding, and Databricks documents it as faster on both read and write, with
    case-sensitive paths and typed values. The limits: no partitioning, clustering, grouping or min/max statistics on
    the variant itself, so pull the fields you filter on into ordinary columns.

## 18.5 Querying VARIANT

*Level: intermediate.*

### The `:` path, case sensitivity and `::` casts

The same `:` syntax works on `VARIANT`, and this time it runs on the local engine too. The result is a `VARIANT`,
shown with JSON quoting:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE OR REPLACE TEMP VIEW v AS
SELECT order_json AS o FROM bronze_orders WHERE order_json IS NOT NULL;

SELECT o:order_id, o:ship_to.city, o:items[0].unit_price, o:tags.promo, o:['gift_note'],
       typeof(o:order_id) AS t
FROM v;

SELECT o:status AS lower_case, o:Status AS mixed_case FROM v WHERE o:order_id::INT = 1001;
```

```text
+--------+---------+----------+----------+---------------+-------+
|order_id|city     |unit_price|promo     |gift_note      |t      |
+--------+---------+----------+----------+---------------+-------+
|1001    |"Calgary"|"29.95"   |"SPRING10"|NULL           |variant|
|1002    |"Banff"  |"149.00"  |NULL      |NULL           |variant|
|1003    |"Calgary"|NULL      |NULL      |NULL           |variant|
|1004    |"Moab"   |"89.99"   |NULL      |"Happy trails!"|variant|
|1005    |"Canmore"|NULL      |NULL      |NULL           |variant|
+--------+---------+----------+----------+---------------+-------+

+----------+----------+
|lower_case|mixed_case|
+----------+----------+
|"PLACED"  |NULL      |
+----------+----------+
```

Notes on this output:

- `gift_note`, which `from_json` dropped, is still there: nothing outside a schema is lost.
- `unit_price` is `"29.95"` with quotes, because the source sent it as a JSON string. `VARIANT` keeps the source's
  types; it does not fix them.
- On a `VARIANT`, path identifiers are case-sensitive ("For `VARIANT` types, it is case-sensitive", from the JSON path
  expression page). On a STRING column they are case-insensitive. Moving from JSON strings to `VARIANT` can therefore
  change results, which the comparison page lists as a breaking difference, together with "The `[*]` syntax is not
  support[ed]" for `VARIANT`.
- For names with spaces, dots, colons or brackets, the Query variant data page recommends the `['name']` form; it
  warns that backticks do not escape periods or square brackets and such a name "returns `NULL` when escaped with
  backticks".

To get typed values, cast with `::` (a synonym for `cast`,
[`::` operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/coloncolonsign)):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT o:order_id::INT              AS order_id,
       o:order_ts::TIMESTAMP        AS order_ts,
       o:amount::DECIMAL(10,2)      AS amount,
       o:ship_to.city::STRING       AS city,
       typeof(o:amount::DECIMAL(10,2)) AS t
FROM v;

SELECT o:status::INT FROM v;
-- ERROR: [INVALID_VARIANT_CAST] The variant value `"PLACED"` cannot be cast into `"INT"`.
-- Please use `try_variant_get` instead.
```

```text
+--------+-------------------+------+-------+-------------+
|order_id|order_ts           |amount|city   |t            |
+--------+-------------------+------+-------+-------------+
|1001    |2026-03-01 10:15:00|59.90 |Calgary|decimal(10,2)|
|1002    |2026-03-01 11:02:00|186.50|Banff  |decimal(10,2)|
|1003    |2026-03-02 09:30:00|0.00  |Calgary|decimal(10,2)|
|1004    |2026-03-02 14:45:00|136.94|Moab   |decimal(10,2)|
|1005    |2026-03-03 08:05:00|45.00 |Canmore|decimal(10,2)|
+--------+-------------------+------+-------+-------------+
```

### variant_get, try_variant_get and `?::`

`variant_get(variantExpr, path, type)` does path and cast in one call; the path is a JSON path rooted at `$`, as in
the page's examples. If the path is missing it returns NULL; if the value cannot be cast it raises
`INVALID_VARIANT_CAST`. `try_variant_get` returns NULL in both cases
([variant_get](https://docs.databricks.com/aws/en/sql/language-manual/functions/variant_get),
[try_variant_get](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_variant_get)):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT variant_get(o, '$.items[0].qty', 'int')        AS first_qty,
       variant_get(o, '$.ship_to.street', 'string')   AS street,
       try_variant_get(o, '$.status', 'int')          AS status_as_int
FROM v;

SELECT variant_get(o, '$.status', 'int') FROM v;
-- ERROR: [INVALID_VARIANT_CAST] The variant value `"PLACED"` cannot be cast into `"INT"`.
-- Please use `try_variant_get` instead.
```

```text
+---------+------------+-------------+
|first_qty|street      |status_as_int|
+---------+------------+-------------+
|2        |12 Canyon Rd|NULL         |
|1        |4 Banff Ave |NULL         |
|NULL     |12 Canyon Rd|NULL         |
|1        |80 Main St  |NULL         |
|NULL     |NULL        |NULL         |
+---------+------------+-------------+
```

Databricks also has `expr ?:: type`, a synonym for `try_cast`; its page says "Applies to: Databricks Runtime 15.3
and above" ([`?::` operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/questiondoublecolonsign)).
The try_variant_get page shows `...:data[1].a ?::STRING` as synonymous with `try_variant_get`. The local parser does
not accept `?::`:

*Databricks only, not run here. Syntax from [try_variant_get](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_variant_get).*

```sql
SELECT order_json:status ?::INT AS status_as_int   -- NULL instead of an error
FROM shop.bronze.orders;
```

You can cast a whole sub-tree into a typed shape in one step, which is how silver gets its `items` array:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT o:order_id::INT AS order_id,
       o:items::ARRAY<STRUCT<product_id: INT, qty: INT, unit_price: DECIMAL(10,2)>> AS items
FROM v;
```

```text
+--------+--------------------------------------------+
|order_id|items                                       |
+--------+--------------------------------------------+
|1001    |[{3, 2, 29.95}]                             |
|1002    |[{1, 1, 149.00}, {5, 3, 12.50}]             |
|1003    |[]                                          |
|1004    |[{2, 1, 89.99}, {3, 1, 29.95}, {8, 4, 4.25}]|
|1005    |NULL                                        |
+--------+--------------------------------------------+
```

The string `"29.95"` cast to `DECIMAL(10,2)` because normal casting rules apply to each value
([Query variant data, casting rules](https://docs.databricks.com/aws/en/semi-structured/variant)).

### schema_of_variant and schema_of_variant_agg

`schema_of_variant` describes one value; `schema_of_variant_agg` merges the schemas of a group, using the least common
type and falling back to `VARIANT` when there is none
([schema_of_variant_agg](https://docs.databricks.com/aws/en/sql/language-manual/functions/schema_of_variant_agg)).
Run the aggregate over bronze before you write the silver schema; it shows every field that has ever arrived:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT o:order_id::INT AS order_id, schema_of_variant(o:items) AS items_schema FROM v;
SELECT schema_of_variant_agg(o) AS all_orders_schema FROM v;
```

```text
+--------+------------------------------------------------------------------+
|order_id|items_schema                                                      |
+--------+------------------------------------------------------------------+
|1001    |ARRAY<OBJECT<product_id: BIGINT, qty: BIGINT, unit_price: STRING>>|
|1002    |ARRAY<OBJECT<product_id: BIGINT, qty: BIGINT, unit_price: STRING>>|
|1003    |ARRAY<VOID>                                                       |
|1004    |ARRAY<OBJECT<product_id: BIGINT, qty: BIGINT, unit_price: STRING>>|
|1005    |NULL                                                              |
+--------+------------------------------------------------------------------+

all_orders_schema:
OBJECT<amount: STRING, currency: STRING, customer_id: BIGINT, gift_note: STRING,
       items: ARRAY<OBJECT<product_id: BIGINT, qty: BIGINT, unit_price: STRING>>, order_id: BIGINT,
       order_ts: STRING, ship_to: OBJECT<city: STRING, country: STRING, region: STRING, street: STRING>,
       status: STRING, tags: OBJECT<channel: STRING, gift: STRING, promo: STRING>>
```

(The second result is one long string; it is wrapped here for reading.)

### Two kinds of NULL

A `VARIANT` can hold a JSON `null`. That is a **variant null**, a stored value, and it is not a SQL `NULL`. A missing
path gives a SQL `NULL`. `is_variant_null` tests for the first, `IS NULL` for the second, and casting a variant null
to a type gives SQL `NULL` (JSON path expression page). Order 1005 has `"tags": null` and no `items` key:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT o:order_id::INT          AS order_id,
       o:tags IS NULL           AS tags_is_sql_null,
       is_variant_null(o:tags)  AS tags_is_variant_null,
       o:items IS NULL          AS items_is_sql_null,
       o:tags::STRING IS NULL   AS tags_cast_is_null
FROM v WHERE o:order_id::INT IN (1004, 1005);
```

```text
+--------+----------------+--------------------+-----------------+-----------------+
|order_id|tags_is_sql_null|tags_is_variant_null|items_is_sql_null|tags_cast_is_null|
+--------+----------------+--------------------+-----------------+-----------------+
|1004    |false           |false               |false            |false            |
|1005    |false           |true                |true             |true             |
+--------+----------------+--------------------+-----------------+-----------------+
```

!!! warning "WHERE o:tags IS NULL misses JSON nulls"
    A filter `WHERE o:tags IS NULL` finds orders with no `tags` key but not orders that sent `"tags": null`. Cast
    first (`o:tags::STRING IS NULL`) or test both conditions. JSON strings behave differently: on a STRING column, a
    JSON `null` comes back as a SQL `NULL` (Query JSON strings page).

### Grouping and ordering need a cast

Because `VARIANT` cannot be grouped or ordered, cast before `GROUP BY`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT o:status, count(*) FROM v GROUP BY o:status;
-- ERROR: [GROUP_EXPRESSION_TYPE_IS_NOT_ORDERABLE] The expression "variant_get(o, $.status)" cannot be used as a
-- grouping expression because its data type "VARIANT" is not an orderable data type.

SELECT o:status::STRING AS status, count(*) AS n FROM v GROUP BY ALL ORDER BY status;
```

```text
+---------+---+
|status   |n  |
+---------+---+
|CANCELLED|1  |
|PLACED   |3  |
|SHIPPED  |1  |
+---------+---+
```

### variant_explode

`variant_explode(input)` is a table-valued function that returns `pos`, `key` and `value` for each element of a
`VARIANT` array or each field of a `VARIANT` object; for an array, `key` is NULL. A NULL input, or one that is not an
array or object, produces no rows; `variant_explode_outer` produces one row of NULLs instead
([variant_explode](https://docs.databricks.com/aws/en/sql/language-manual/functions/variant_explode),
[variant_explode_outer](https://docs.databricks.com/aws/en/sql/language-manual/functions/variant_explode_outer)).
Both apply to Databricks SQL and Databricks Runtime 15.3 and above; the `variant_explode` page adds named
parameter invocation in Databricks SQL and Databricks Runtime 16.1 and above. Because it is a generator, it goes in `FROM`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT v.o:order_id::INT AS order_id, e.pos, e.key, e.value
FROM v, LATERAL variant_explode(v.o:items) AS e;

SELECT e.key, e.value
FROM v, LATERAL variant_explode(v.o:tags) AS e
WHERE v.o:order_id::INT = 1004;
```

```text
+--------+---+----+----------------------------------------------+
|order_id|pos|key |value                                         |
+--------+---+----+----------------------------------------------+
|1001    |0  |NULL|{"product_id":3,"qty":2,"unit_price":"29.95"} |
|1002    |0  |NULL|{"product_id":1,"qty":1,"unit_price":"149.00"}|
|1002    |1  |NULL|{"product_id":5,"qty":3,"unit_price":"12.50"} |
|1004    |0  |NULL|{"product_id":2,"qty":1,"unit_price":"89.99"} |
|1004    |1  |NULL|{"product_id":3,"qty":1,"unit_price":"29.95"} |
|1004    |2  |NULL|{"product_id":8,"qty":4,"unit_price":"4.25"}  |
+--------+---+----+----------------------------------------------+

+-------+-------+
|key    |value  |
+-------+-------+
|channel|"store"|
|gift   |"yes"  |
+-------+-------+
```

### Converting back: to_json, to_variant_object and CAST

`to_json(variant)` gives a JSON string. `parse_json` and `to_json` are inverses only logically: the pages warn that
whitespace is not preserved, key order is arbitrary and trailing zeros may be dropped. `to_variant_object` turns a
struct, map or array into a `VARIANT`, and `CAST(x AS VARIANT)` works for scalars:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT to_json(o:ship_to) AS ship_json, typeof(to_json(o:ship_to)) AS t FROM v WHERE o:order_id::INT = 1005;
SELECT to_variant_object(named_struct('city', 'Moab', 'region', 'UT')) AS v_obj,
       CAST(59.90 AS VARIANT) AS v_num, schema_of_variant(CAST(59.90 AS VARIANT)) AS s;
```

```text
+-----------------------------------------------+------+
|ship_json                                      |t     |
+-----------------------------------------------+------+
|{"city":"Canmore","country":"CA","region":"AB"}|string|
+-----------------------------------------------+------+

+-----------------------------+-----+------------+
|v_obj                        |v_num|s           |
+-----------------------------+-----+------------+
|{"city":"Moab","region":"UT"}|59.9 |DECIMAL(3,1)|
+-----------------------------+-----+------------+
```

The keys came back in alphabetical order and `59.90` became `59.9`, exactly the caveats the pages list.

In PySpark, the same functions are in `pyspark.sql.functions`, and `selectExpr` accepts the `:` syntax:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
v = (spark.table("bronze_orders_raw")
     .select(F.try_parse_json("raw").alias("v")).where(F.col("v").isNotNull()))
(v.select(F.variant_get("v", "$.order_id", "int").alias("order_id"),
          F.variant_get("v", "$.ship_to.city", "string").alias("city"),
          F.try_variant_get("v", "$.status", "int").alias("status_as_int"))
  .orderBy("order_id").show(truncate=False))
v.selectExpr("v:order_id::INT AS order_id", "v:items[0].qty::INT AS first_qty").orderBy("order_id").show()
```

```text
+--------+-------+-------------+
|order_id|city   |status_as_int|
+--------+-------+-------------+
|1001    |Calgary|NULL         |
|1002    |Banff  |NULL         |
|1003    |Calgary|NULL         |
|1004    |Moab   |NULL         |
|1005    |Canmore|NULL         |
+--------+-------+-------------+

+--------+---------+
|order_id|first_qty|
+--------+---------+
|    1001|        2|
|    1002|        1|
|    1003|     NULL|
|    1004|        1|
|    1005|     NULL|
+--------+---------+
```

Note that `v:items[0]` on the empty array of order 1003 returned NULL, unlike `items[0]` on a typed `ARRAY` in 18.2:
the Query variant data page says that if "the array-index is out of bounds, the result is null".

| Task | JSON string (`STRING`) | `VARIANT` |
| --- | --- | --- |
| Read a field | `raw:a.b` (Databricks), `get_json_object(raw, '$.a.b')` | `v:a.b`, `variant_get(v, '$.a.b', 'type')` |
| Result type | `STRING` | `VARIANT` |
| Field name case | identifiers case-insensitive, `['name']` case-sensitive | always case-sensitive |
| `[*]` on arrays | supported | not supported |
| JSON `null` | SQL `NULL` | variant null (`IS NULL` is false) |
| Cast failure | `::` raises, `try_cast` / `?::` return NULL | `::` and `variant_get` raise, `try_variant_get` / `?::` return NULL |
| Schema | `schema_of_json` | `schema_of_variant`, `schema_of_variant_agg` |
| Explode | `from_json` to an array, then `explode` | `variant_explode` |

## 18.6 Exploding arrays and maps

*Level: intermediate.*

To turn an order's lines into rows you need a **generator**: a function that returns zero or more rows for each
input row. `explode(collection)` returns one row per array element (column `col`) or per map entry (columns `key`
and `value`). If the collection is NULL, no rows are produced
([explode](https://docs.databricks.com/aws/en/sql/language-manual/functions/explode)). An empty array produces no
rows either. `explode_outer` produces one row of NULLs for a NULL collection, and the run below shows it does the
same for an empty array.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Five order rows on the left become six item rows on the right after explode; orders 1003 and 1005 disappear, explode_outer keeps them as NULL rows">
<text x="120" y="22" text-anchor="middle" font-size="14" fill="currentColor">silver_orders (5 rows)</text>
<rect x="20" y="34" width="200" height="34" fill="none" stroke="currentColor"/>
<text x="30" y="56" font-size="13" fill="currentColor">1001  items: 1</text>
<rect x="20" y="68" width="200" height="34" fill="none" stroke="currentColor"/>
<text x="30" y="90" font-size="13" fill="currentColor">1002  items: 2</text>
<rect x="20" y="102" width="200" height="34" fill="none" stroke="currentColor" stroke-dasharray="4 3"/>
<text x="30" y="124" font-size="13" fill="currentColor">1003  items: [] (empty)</text>
<rect x="20" y="136" width="200" height="34" fill="none" stroke="currentColor"/>
<text x="30" y="158" font-size="13" fill="currentColor">1004  items: 3</text>
<rect x="20" y="170" width="200" height="34" fill="none" stroke="currentColor" stroke-dasharray="4 3"/>
<text x="30" y="192" font-size="13" fill="currentColor">1005  items: NULL</text>
<line x1="230" y1="120" x2="370" y2="120" stroke="currentColor" stroke-width="1.5"/>
<polygon points="370,114 382,120 370,126" fill="currentColor"/>
<text x="305" y="108" text-anchor="middle" font-size="14" fill="currentColor">explode(items)</text>
<text x="305" y="142" text-anchor="middle" font-size="13" fill="currentColor">one row per element</text>
<text x="505" y="22" text-anchor="middle" font-size="14" fill="currentColor">result (6 rows)</text>
<rect x="400" y="34" width="210" height="28" fill="none" stroke="currentColor"/>
<text x="410" y="53" font-size="13" fill="currentColor">1001  {3, 2, 29.95}</text>
<rect x="400" y="62" width="210" height="28" fill="none" stroke="currentColor"/>
<text x="410" y="81" font-size="13" fill="currentColor">1002  {1, 1, 149.00}</text>
<rect x="400" y="90" width="210" height="28" fill="none" stroke="currentColor"/>
<text x="410" y="109" font-size="13" fill="currentColor">1002  {5, 3, 12.50}</text>
<rect x="400" y="118" width="210" height="28" fill="none" stroke="currentColor"/>
<text x="410" y="137" font-size="13" fill="currentColor">1004  {2, 1, 89.99}</text>
<rect x="400" y="146" width="210" height="28" fill="none" stroke="currentColor"/>
<text x="410" y="165" font-size="13" fill="currentColor">1004  {3, 1, 29.95}</text>
<rect x="400" y="174" width="210" height="28" fill="none" stroke="currentColor"/>
<text x="410" y="193" font-size="13" fill="currentColor">1004  {8, 4, 4.25}</text>
<text x="320" y="238" text-anchor="middle" font-size="13" fill="currentColor">1003 and 1005 give no rows; explode_outer keeps them as NULL rows (8).</text>
<text x="320" y="262" text-anchor="middle" font-size="13" fill="currentColor">Order-level columns (amount, ship_to) are copied onto every item row:</text>
<text x="320" y="282" text-anchor="middle" font-size="13" fill="currentColor">1002's amount now appears twice and 1004's three times.</text>
</svg>
<figcaption>Figure 18.2. explode turns one order row into one row per item and repeats the order's other columns.</figcaption>
</figure>

### The four generators

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- silver_orders: the typed table built with from_json in 18.3 (good lines only)
SELECT order_id, explode(items) AS item FROM silver_orders ORDER BY order_id;
SELECT order_id, explode_outer(items) AS item FROM silver_orders ORDER BY order_id;
```

```text
explode                          explode_outer
+--------+--------------+        +--------+--------------+
|order_id|item          |        |order_id|item          |
+--------+--------------+        +--------+--------------+
|1001    |{3, 2, 29.95} |        |1001    |{3, 2, 29.95} |
|1002    |{1, 1, 149.00}|        |1002    |{1, 1, 149.00}|
|1002    |{5, 3, 12.50} |        |1002    |{5, 3, 12.50} |
|1004    |{2, 1, 89.99} |        |1003    |NULL          |
|1004    |{3, 1, 29.95} |        |1004    |{2, 1, 89.99} |
|1004    |{8, 4, 4.25}  |        |1004    |{3, 1, 29.95} |
+--------+--------------+        |1004    |{8, 4, 4.25}  |
                                 |1005    |NULL          |
                                 +--------+--------------+
```

(The two results were printed one after the other; they are placed side by side here.)

`posexplode` adds a 0-based `pos` column, which becomes the line number. `inline(input)` takes an array of structs and
returns one column per struct field, so you skip the `item.field` step
([posexplode](https://docs.databricks.com/aws/en/sql/language-manual/functions/posexplode),
[inline](https://docs.databricks.com/aws/en/sql/language-manual/functions/inline)). Each also has an `_outer` form.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, posexplode(items) AS (pos, item) FROM silver_orders ORDER BY order_id, pos;
SELECT order_id, inline(items) FROM silver_orders ORDER BY order_id, product_id;
```

```text
+--------+---+--------------+
|order_id|pos|item          |
+--------+---+--------------+
|1001    |0  |{3, 2, 29.95} |
|1002    |0  |{1, 1, 149.00}|
|1002    |1  |{5, 3, 12.50} |
|1004    |0  |{2, 1, 89.99} |
|1004    |1  |{3, 1, 29.95} |
|1004    |2  |{8, 4, 4.25}  |
+--------+---+--------------+

+--------+----------+---+----------+
|order_id|product_id|qty|unit_price|
+--------+----------+---+----------+
|1001    |3         |2  |29.95     |
|1002    |1         |1  |149.00    |
|1002    |5         |3  |12.50     |
|1004    |2         |1  |89.99     |
|1004    |3         |1  |29.95     |
|1004    |8         |4  |4.25      |
+--------+----------+---+----------+
```

Exploding a map gives one row per entry, with the key and value as two columns:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT o.order_id, t.tag_key, t.tag_value
FROM silver_orders AS o, LATERAL explode(o.tags) AS t(tag_key, tag_value)
ORDER BY o.order_id, t.tag_key;
```

```text
+--------+-------+---------+
|order_id|tag_key|tag_value|
+--------+-------+---------+
|1001    |channel|web      |
|1001    |promo  |SPRING10 |
|1002    |channel|mobile   |
|1003    |channel|web      |
|1004    |channel|store    |
|1004    |gift   |yes      |
+--------+-------+---------+
```

### Where the generator goes: SELECT list, LATERAL VIEW or FROM

There are three ways to call a generator, and the docs have a clear preference. Every generator page (explode,
explode_outer, posexplode, posexplode_outer, inline, inline_outer, json_tuple) says the same thing:

- **Databricks Runtime 12.1 and earlier:** the function can only be the root of an expression in the `SELECT` list
  or follow `LATERAL VIEW`, and a second generator in the same `SELECT` list raises
  `UNSUPPORTED_GENERATOR.MULTI_GENERATOR`.
- **Databricks SQL and Databricks Runtime 12.2 LTS and above:** "Invocation from the LATERAL VIEW clause or the
  `SELECT` list is deprecated. Instead, invoke `explode` as a table_reference."

The [LATERAL VIEW page](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-lateral-view)
repeats it: "In Databricks SQL and starting with Databricks Runtime 12.2 this clause is deprecated." The replacement
is a [table-valued function in FROM](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-tvf),
with the keyword `LATERAL` so that it can refer to columns of the table before it:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- recommended: table-valued function in FROM
SELECT o.order_id, i.product_id, i.qty, i.unit_price
FROM silver_orders AS o,
     LATERAL inline(o.items) AS i
ORDER BY o.order_id, i.product_id;

SELECT o.order_id, p.pos + 1 AS line_no, p.col.product_id
FROM silver_orders AS o,
     LATERAL posexplode(o.items) AS p
ORDER BY o.order_id, line_no;

-- deprecated but common in older code
SELECT order_id, item.product_id, item.qty
FROM silver_orders
LATERAL VIEW explode(items) t AS item
ORDER BY order_id, item.product_id;

SELECT order_id, item
FROM silver_orders
LATERAL VIEW OUTER explode(items) t AS item
WHERE order_id IN (1003, 1005) ORDER BY order_id;
```

```text
(first query: the same 6 rows as inline above)

+--------+-------+----------+
|order_id|line_no|product_id|
+--------+-------+----------+
|1001    |1      |3         |
|1002    |1      |1         |
|1002    |2      |5         |
|1004    |1      |2         |
|1004    |2      |3         |
|1004    |3      |8         |
+--------+-------+----------+

(LATERAL VIEW explode: order_id, product_id, qty for the same 6 lines)

+--------+----+
|order_id|item|
+--------+----+
|1003    |NULL|
|1005    |NULL|
+--------+----+
```

Why the `FROM` form is better: it reads like a join (each order joined to its own lines), the generator's output
gets an alias and column names like any table, several generators can be combined explicitly, and there is no
special clause to learn. `LATERAL VIEW OUTER` has no direct keyword in the `FROM` form; use the `_outer` function
(`LATERAL explode_outer(o.items)`). See [Chapter 17](17-Databricks-SQL-vs-Standard.md) for `LATERAL VIEW` among the
other Databricks SQL extensions.

!!! note "Two generators in one SELECT list"
    The open-source Spark 4.2 engine here accepted `SELECT order_id, explode(items), explode(tags) FROM
    silver_orders` and returned every item paired with every tag of the same order (10 rows). The Databricks pages
    only say this raises `MULTI_GENERATOR` on Databricks Runtime 12.1 and earlier and that `SELECT`-list generators
    are deprecated from 12.2; the behavior on current runtimes is not verified here. Write it in `FROM` with two
    `LATERAL` calls, so the cross product is visible in the code.

In PySpark, `F.explode`, `F.explode_outer`, `F.posexplode` and `F.inline` are column functions used inside
`select`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
(orders.select("order_id", F.explode("items").alias("item"))
       .select("order_id", "item.product_id", "item.qty").orderBy("order_id", "product_id")
       .show(truncate=False))
print("explode rows:", orders.select(F.explode("items")).count(),
      "| explode_outer rows:", orders.select(F.explode_outer("items")).count())
orders.select("order_id", F.posexplode("items").alias("pos", "item")).where("order_id = 1004").show(truncate=False)
orders.select("order_id", F.inline("items")).where("order_id = 1002").show(truncate=False)
```

```text
+--------+----------+---+
|order_id|product_id|qty|
+--------+----------+---+
|1001    |3         |2  |
|1002    |1         |1  |
|1002    |5         |3  |
|1004    |2         |1  |
|1004    |3         |1  |
|1004    |8         |4  |
+--------+----------+---+

explode rows: 6 | explode_outer rows: 8
+--------+---+-------------+
|order_id|pos|item         |
+--------+---+-------------+
|1004    |0  |{2, 1, 89.99}|
|1004    |1  |{3, 1, 29.95}|
|1004    |2  |{8, 4, 4.25} |
+--------+---+-------------+

+--------+----------+---+----------+
|order_id|product_id|qty|unit_price|
+--------+----------+---+----------+
|1002    |1         |1  |149.00    |
|1002    |5         |3  |12.50     |
+--------+----------+---+----------+
```

### Performance: explode multiplies rows

`explode` changes the grain of the data. Every order-level column is copied onto every item row, so a table of
orders with an average of ten lines becomes ten times as many rows, and any order-level measure summed after the
explode is counted once per line. With our five orders:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT count(*) AS order_rows, sum(amount) AS total_amount FROM silver_orders;

SELECT count(*) AS exploded_rows, sum(o.amount) AS wrong_total, sum(i.qty * i.unit_price) AS item_total
FROM silver_orders AS o, LATERAL inline(o.items) AS i;
```

```text
+----------+------------+
|order_rows|total_amount|
+----------+------------+
|5         |428.34      |
+----------+------------+

+-------------+-----------+----------+
|exploded_rows|wrong_total|item_total|
+-------------+-----------+----------+
|6            |843.72     |383.34    |
+-------------+-----------+----------+
```

`wrong_total` counts order 1002 twice and 1004 three times. `item_total` is correct at item grain, but it is
45.00 short of the order total, because order 1005 has an amount and no items. Both numbers are "right" for some
question; the bug is mixing grains.

Practical rules that follow:

- Explode once, in silver, into an `order_items` table, rather than in every gold query.
- Aggregate order-level measures from the order table, item-level measures from the item table.
- When you only need a value per order (a count, a total, a yes/no), use a higher-order function (18.8) on the array.
  It keeps one row per order and needs no `GROUP BY` afterwards.
- Filter orders before exploding, not after.

The docs give no measured cost for explode; these rules follow from the row counts, not from a cited benchmark.

!!! tip "In the interview"
    **"What is the difference between explode and explode_outer?"** `explode` returns one row per element and no
    row at all when the array is NULL (and, as tested, when it is empty), so those parent rows disappear.
    `explode_outer` keeps them with NULL in the element column. Use `explode_outer` when the parent row must survive,
    for example when counting orders with zero lines. Then add the follow-up yourself: either way, order-level
    columns are repeated, so never sum them after the explode.

## 18.7 Flattening an order into rows and back

*Level: intermediate.*

Silver usually keeps the order at order grain and writes its lines to a separate table. `posexplode` gives a stable
line number, which you need later to rebuild the array in the original order:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver_order_items USING DELTA AS
SELECT o.order_id, p.pos + 1 AS line_no,
       p.col.product_id, p.col.qty, p.col.unit_price
FROM silver_orders AS o, LATERAL posexplode(o.items) AS p;

SELECT * FROM silver_order_items ORDER BY order_id, line_no;
```

```text
+--------+-------+----------+---+----------+
|order_id|line_no|product_id|qty|unit_price|
+--------+-------+----------+---+----------+
|1001    |1      |3         |2  |29.95     |
|1002    |1      |1         |1  |149.00    |
|1002    |2      |5         |3  |12.50     |
|1004    |1      |2         |1  |89.99     |
|1004    |2      |3         |1  |29.95     |
|1004    |3      |8         |4  |4.25      |
+--------+-------+----------+---+----------+
```

This is the brief's `order_items(order_id, product_id, qty, unit_price)` table plus a line number.

Going back, `collect_list` (synonym `array_agg`) gathers values of a group into an array. Two facts from its
[page](https://docs.databricks.com/aws/en/sql/language-manual/functions/collect_list): "The order of elements in the
array is non-deterministic", and "`NULL` values are excluded". `collect_list` applies to all versions; `array_agg` to
"Databricks SQL Databricks Runtime 10.4 LTS and above".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id,
       array_agg(named_struct('product_id', product_id, 'qty', qty, 'unit_price', unit_price)) AS items_any_order
FROM silver_order_items GROUP BY order_id ORDER BY order_id;
```

```text
+--------+--------------------------------------------+
|order_id|items_any_order                             |
+--------+--------------------------------------------+
|1001    |[{3, 2, 29.95}]                             |
|1002    |[{1, 1, 149.00}, {5, 3, 12.50}]             |
|1004    |[{2, 1, 89.99}, {3, 1, 29.95}, {8, 4, 4.25}]|
+--------+--------------------------------------------+
```

The order looks right here, on six rows in one task. On a real cluster the rows of one order can arrive from several
partitions in any order. To make it deterministic, collect structs whose **first field** is the sort key, sort the
array (structs compare field by field, so `array_sort` sorts by `line_no`), then drop the key with `transform`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id,
       transform(
         array_sort(collect_list(struct(line_no, product_id, qty, unit_price))),
         x -> named_struct('product_id', x.product_id, 'qty', x.qty, 'unit_price', x.unit_price)
       ) AS items
FROM silver_order_items GROUP BY order_id ORDER BY order_id;

SELECT to_json(named_struct('order_id', order_id,
                            'items', collect_list(named_struct('product_id', product_id, 'qty', qty)))) AS order_json
FROM silver_order_items WHERE order_id = 1002 GROUP BY order_id;
```

```text
+--------+--------------------------------------------+
|order_id|items                                       |
+--------+--------------------------------------------+
|1001    |[{3, 2, 29.95}]                             |
|1002    |[{1, 1, 149.00}, {5, 3, 12.50}]             |
|1004    |[{2, 1, 89.99}, {3, 1, 29.95}, {8, 4, 4.25}]|
+--------+--------------------------------------------+

+-----------------------------------------------------------------------------+
|order_json                                                                   |
+-----------------------------------------------------------------------------+
|{"order_id":1002,"items":[{"product_id":1,"qty":1},{"product_id":5,"qty":3}]}|
+-----------------------------------------------------------------------------+
```

Orders 1003 and 1005 are missing from the rebuilt result, because they have no rows in `silver_order_items`. If the
nested output must contain every order, start from `silver_orders` and `LEFT JOIN` the rebuilt arrays.

The same in PySpark:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
items = orders.select("order_id", F.posexplode("items").alias("pos", "item"))
(items.groupBy("order_id")
      .agg(F.array_sort(F.collect_list(F.struct("pos", "item.product_id", "item.qty"))).alias("items"))
      .orderBy("order_id").show(truncate=False))
```

```text
+--------+---------------------------------+
|order_id|items                            |
+--------+---------------------------------+
|1001    |[{0, 3, 2}]                      |
|1002    |[{0, 1, 1}, {1, 5, 3}]           |
|1004    |[{0, 2, 1}, {1, 3, 1}, {2, 8, 4}]|
+--------+---------------------------------+
```

!!! warning "collect_list order is not guaranteed"
    `collect_list` / `array_agg` order is non-deterministic, and the complex-types page says the same for
    `collect_set`. A test on a laptop that "always" returns the right order proves nothing. Sort explicitly: put
    the key first in a struct and `array_sort`, or use a comparator (18.8).

## 18.8 Higher-order functions and lambdas

*Level: expert.*

Exploding and regrouping is a lot of machinery for "the total of this order's lines". A **higher-order function**
takes an array (or map) and a **lambda function**, a small inline function written `x -> expr` or
`(x, y) -> expr`, and applies the lambda to the elements inside the row
([Higher-order functions](https://docs.databricks.com/aws/en/semi-structured/higher-order-functions)). The row count
does not change. The [lambda page](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-lambda-functions)
sets the rules: the body is "Any simple expression referencing `paramN`, which does not contain a subquery or a SQL
user-defined function"; parameter types are set by the calling function; and the result type must match what the
caller expects. All the functions in this section apply to "Databricks SQL Databricks Runtime", with no minimum
version on their pages.

### transform, filter, exists, forall

- `transform(array, x -> ...)` returns a new array with one result per element. A second lambda parameter is the
  0-based index.
- `filter(array, x -> bool)` keeps the elements where the lambda is true (also accepts an index parameter).
- `exists(array, x -> bool)` is true if any element matches; `forall(array, x -> bool)` if all match.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE OR REPLACE TEMP VIEW o AS SELECT * FROM silver_orders WHERE items IS NOT NULL;

SELECT order_id,
       transform(items, i -> i.qty * i.unit_price)                      AS line_totals,
       transform(items, (i, idx) -> concat(idx + 1, ':', i.product_id)) AS numbered
FROM o ORDER BY order_id;

SELECT order_id,
       filter(items, i -> i.qty >= 2)          AS multi_qty_lines,
       exists(items, i -> i.product_id = 3)    AS has_product_3,
       forall(items, i -> i.unit_price >= 10)  AS all_lines_10_plus
FROM o ORDER BY order_id;
```

```text
+--------+---------------------+---------------+
|order_id|line_totals          |numbered       |
+--------+---------------------+---------------+
|1001    |[59.90]              |[1:3]          |
|1002    |[149.00, 37.50]      |[1:1, 2:5]     |
|1003    |[]                   |[]             |
|1004    |[89.99, 29.95, 17.00]|[1:2, 2:3, 3:8]|
+--------+---------------------+---------------+

+--------+---------------+-------------+-----------------+
|order_id|multi_qty_lines|has_product_3|all_lines_10_plus|
+--------+---------------+-------------+-----------------+
|1001    |[{3, 2, 29.95}]|true         |true             |
|1002    |[{5, 3, 12.50}]|false        |true             |
|1003    |[]             |false        |true             |
|1004    |[{8, 4, 4.25}] |true         |false            |
+--------+---------------+-------------+-----------------+
```

Order 1003 has no lines, and `forall` returned `true` for it: a condition holds for every element of an empty set.
If "all lines over 10" should exclude empty orders, add `size(items) > 0`.

NULL elements follow three-valued logic, as the [exists](https://docs.databricks.com/aws/en/sql/language-manual/functions/exists)
and [forall](https://docs.databricks.com/aws/en/sql/language-manual/functions/forall) pages show: if no element
gives true and one gives NULL, `exists` returns NULL. `array_contains` cannot look for a NULL; its page says to use
`exists(arr, x -> x IS NULL)` instead
([array_contains](https://docs.databricks.com/aws/en/sql/language-manual/functions/array_contains)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT array_contains(array(1, NULL, 3), 2)        AS contains_2,
       exists(array(1, NULL, 3), x -> x IS NULL)   AS has_null,
       exists(array(1, NULL, 3), x -> x % 2 = 0)   AS has_even,
       forall(array(2, NULL, 8), x -> x % 2 = 0)   AS all_even,
       array_distinct(array(1, NULL, 1, NULL))     AS dedup;
```

```text
+----------+--------+--------+--------+---------+
|contains_2|has_null|has_even|all_even|dedup    |
+----------+--------+--------+--------+---------+
|NULL      |true    |NULL    |NULL    |[1, NULL]|
+----------+--------+--------+--------+---------+
```

### aggregate (reduce)

`aggregate(expr, start, merge [, finish])`, synonym `reduce`, folds an array into one value. The merge lambda takes
the accumulator and the element; "The accumulator and the result must be of the type of `start`", and the optional
finish lambda converts the final state
([aggregate](https://docs.databricks.com/aws/en/sql/language-manual/functions/aggregate)). That type rule is the most
common bug with this function:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT aggregate(items, 0, (acc, i) -> acc + i.qty * i.unit_price) FROM o;
-- ERROR: [DATATYPE_MISMATCH.UNEXPECTED_INPUT_TYPE] Cannot resolve "aggregate(items, 0, lambdafunction(...)) ..."

SELECT order_id, amount,
       aggregate(items, CAST(0 AS DECIMAL(10,2)),
                 (acc, i) -> CAST(acc + i.qty * i.unit_price AS DECIMAL(10,2))) AS items_total,
       reduce(items, 0, (acc, i) -> acc + i.qty)                                AS total_qty,
       aggregate(items, named_struct('n', 0, 'q', 0),
                 (acc, i) -> named_struct('n', acc.n + 1, 'q', acc.q + i.qty),
                 acc -> CASE WHEN acc.n = 0 THEN NULL ELSE acc.q / acc.n END)    AS avg_qty_per_line
FROM o ORDER BY order_id;
```

```text
+--------+------+-----------+---------+----------------+
|order_id|amount|items_total|total_qty|avg_qty_per_line|
+--------+------+-----------+---------+----------------+
|1001    |59.90 |59.90      |2        |2.0             |
|1002    |186.50|186.50     |4        |2.0             |
|1003    |0.00  |0.00       |0        |NULL            |
|1004    |136.94|136.94     |6        |2.0             |
+--------+------+-----------+---------+----------------+
```

The first query fails because `start` is an `INT` while `acc + qty * unit_price` is a `DECIMAL`. Starting at `0.0`
fails too (the literal is `DECIMAL(2,1)`, and the sum has a wider type). Give `start` the type you want and cast
the merge result to the same type. The integer sum of `qty` works with `0` because `INT + INT` stays `INT`. The third
column shows the pattern for an average: a struct accumulator (count and sum) and a finish lambda.

`items_total` equals `amount` for every order, which is a good silver data-quality check: one row per order, no
explode, no join.

### zip_with, arrays_zip and array_sort with a comparator

`zip_with(a, b, (x, y) -> ...)` merges two arrays element by element; "If one array is shorter, nulls are appended at
the end" ([zip_with](https://docs.databricks.com/aws/en/sql/language-manual/functions/zip_with)). `arrays_zip`
returns an array of structs pairing the nth elements. `array_sort(array, func)` sorts with a comparator that "must
return -1, 0, or 1"; it raises `COMPARATOR_RETURNS_NULL` if the comparator returns NULL, and without a comparator
sorts ascending with NULLs at the end
([array_sort](https://docs.databricks.com/aws/en/sql/language-manual/functions/array_sort)). The older `sort_array`
puts NULLs first in ascending order.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id,
       zip_with(items.qty, items.unit_price, (q, p) -> q * p) AS line_totals,
       arrays_zip(items.product_id, items.qty)                AS pid_qty
FROM o WHERE order_id = 1004;

SELECT order_id,
       array_sort(items, (a, b) -> CASE WHEN a.unit_price > b.unit_price THEN -1
                                        WHEN a.unit_price < b.unit_price THEN 1
                                        ELSE 0 END)  AS by_price_desc,
       array_sort(items.product_id)                  AS product_ids_asc
FROM o WHERE order_id = 1004;
```

```text
+--------+---------------------+------------------------+
|order_id|line_totals          |pid_qty                 |
+--------+---------------------+------------------------+
|1004    |[89.99, 29.95, 17.00]|[{2, 1}, {3, 1}, {8, 4}]|
+--------+---------------------+------------------------+

+--------+--------------------------------------------+---------------+
|order_id|by_price_desc                               |product_ids_asc|
+--------+--------------------------------------------+---------------+
|1004    |[{2, 1, 89.99}, {3, 1, 29.95}, {8, 4, 4.25}]|[2, 3, 8]      |
+--------+--------------------------------------------+---------------+
```

### The same in PySpark

PySpark has `F.transform`, `F.filter`, `F.exists`, `F.forall`, `F.aggregate` and the others, taking Python lambdas
that build column expressions. The Spark docs for
[transform](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.transform.html)
say the function can use `Column` methods and functions from `pyspark.sql.functions`, and that "Python
`UserDefinedFunctions` are not supported" inside it.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
(orders.where(F.col("items").isNotNull())
       .select("order_id",
               F.transform("items", lambda i: i["qty"] * i["unit_price"]).alias("line_totals"),
               F.filter("items", lambda i: i["qty"] >= 2).alias("multi_qty"),
               F.exists("items", lambda i: i["product_id"] == 3).alias("has_3"),
               F.aggregate("items", F.lit(0), lambda acc, i: acc + i["qty"]).alias("total_qty"))
       .orderBy("order_id").show(truncate=False))
```

```text
+--------+---------------------+---------------+-----+---------+
|order_id|line_totals          |multi_qty      |has_3|total_qty|
+--------+---------------------+---------------+-----+---------+
|1001    |[59.90]              |[{3, 2, 29.95}]|true |2        |
|1002    |[149.00, 37.50]      |[{5, 3, 12.50}]|false|4        |
|1003    |[]                   |[]             |false|0        |
|1004    |[89.99, 29.95, 17.00]|[{8, 4, 4.25}] |true |6        |
+--------+---------------------+---------------+-----+---------+
```

!!! tip "In the interview"
    **"How would you compute each order's total from its items array?"** Either explode the items, multiply, and
    `GROUP BY order_id`, or use `aggregate(items, CAST(0 AS DECIMAL(10,2)), (acc, i) -> CAST(acc + i.qty *
    i.unit_price AS DECIMAL(10,2)))`. The higher-order function keeps one row per order, needs no shuffle for a
    regroup, and cannot double count. Mention the type rule: the accumulator must keep the type of `start`.

## 18.9 Map functions and array set functions

*Level: expert.*

### Map functions

- `map_filter(map, (k, v) -> bool)` keeps matching entries.
- `transform_keys(map, (k, v) -> newKey)` and `transform_values(map, (k, v) -> newValue)` rewrite one side.
  `transform_keys` raises `DUPLICATED_MAP_KEY` if two entries get the same new key.
- `map_from_entries(array of 2-field structs)` and `map_from_arrays(keys, values)` build maps; both raise
  `DUPLICATED_MAP_KEY` on duplicate keys. `map_entries`, `map_keys` and `map_values` go the other way; the pages
  describe their results as unordered.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id,
       map_filter(tags, (k, v) -> k <> 'promo')       AS without_promo,
       transform_keys(tags, (k, v) -> upper(k))       AS upper_keys,
       transform_values(tags, (k, v) -> upper(v))     AS upper_values,
       map_from_entries(transform(items, i -> struct(i.product_id, i.qty))) AS qty_by_product,
       map_entries(tags)                              AS entries
FROM o WHERE order_id IN (1001, 1004) ORDER BY order_id;

SELECT map_from_entries(array(struct(3, 2), struct(3, 1)));
-- ERROR: [DUPLICATED_MAP_KEY] Duplicate map key 3 was found, please check the input data. ...
```

```text
+--------+-------------------------------+-----------------------------------+-----------------------------------+------------------------+-----------------------------------+
|order_id|without_promo                  |upper_keys                         |upper_values                       |qty_by_product          |entries                            |
+--------+-------------------------------+-----------------------------------+-----------------------------------+------------------------+-----------------------------------+
|1001    |{channel -> web}               |{CHANNEL -> web, PROMO -> SPRING10}|{channel -> WEB, promo -> SPRING10}|{3 -> 2}                |[{channel, web}, {promo, SPRING10}]|
|1004    |{channel -> store, gift -> yes}|{CHANNEL -> store, GIFT -> yes}    |{channel -> STORE, gift -> YES}    |{2 -> 1, 3 -> 1, 8 -> 4}|[{channel, store}, {gift, yes}]    |
+--------+-------------------------------+-----------------------------------+-----------------------------------+------------------------+-----------------------------------+
```

`qty_by_product` is only safe if a product never appears on two lines of the same order. If it can, sum first, or
the job fails on the first such order with `DUPLICATED_MAP_KEY`.

### Array set functions

`array_distinct` removes duplicates; `array_union`, `array_intersect` and `array_except` return arrays without
duplicates; `array_contains` tests one value; `arrays_overlap` tests whether two arrays share an element. The NULL
rules matter: `array_contains` returns NULL "if `value` is not matched to any other element" and the array has a
NULL, and `arrays_overlap` returns NULL when the arrays share no non-null element, are both non-empty and either
contains a NULL ([arrays_overlap](https://docs.databricks.com/aws/en/sql/language-manual/functions/arrays_overlap)).
That page also says that "In Databricks SQL, the result is the least common type of `array1` and `array2`. In
Databricks Runtime, the result is BOOLEAN `true` if there is overlap"; the wording looks like a documentation slip,
and both of its examples return booleans.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT customer_id,
       flatten(collect_list(items.product_id))                 AS all_products,
       array_distinct(flatten(collect_list(items.product_id))) AS distinct_products
FROM silver_orders GROUP BY customer_id ORDER BY customer_id;

SELECT array_union(a.items.product_id, b.items.product_id)     AS union_ids,
       array_intersect(a.items.product_id, b.items.product_id) AS both_orders,
       array_except(b.items.product_id, a.items.product_id)    AS only_in_1004,
       arrays_overlap(a.items.product_id, b.items.product_id)  AS overlap
FROM silver_orders a, silver_orders b
WHERE a.order_id = 1001 AND b.order_id = 1004;

SELECT order_id, array_contains(items.product_id, 3) AS has_3 FROM silver_orders ORDER BY order_id;
```

```text
+-----------+------------+-----------------+
|customer_id|all_products|distinct_products|
+-----------+------------+-----------------+
|7          |[3, 2, 3, 8]|[3, 2, 8]        |
|12         |[1, 5]      |[1, 5]           |
|33         |[]          |[]               |
+-----------+------------+-----------------+

+---------+-----------+------------+-------+
|union_ids|both_orders|only_in_1004|overlap|
+---------+-----------+------------+-------+
|[3, 2, 8]|[3]        |[2, 8]      |true   |
+---------+-----------+------------+-------+

+--------+-----+
|order_id|has_3|
+--------+-----+
|1001    |true |
|1002    |false|
|1003    |false|
|1004    |true |
|1005    |NULL |
+--------+-----+
```

Customer 7 placed orders 1001, 1003 and 1004 (1004 is a gift shipped to Moab). `flatten` turned the list of arrays
into one array; the element order inside it depends on `collect_list` and is not guaranteed. Customer 33's only order
has a NULL `items` array, which `collect_list` skips, so the result is an empty array rather than NULL. Order 1005
gets NULL from `array_contains`, because the array itself is NULL.

## 18.10 Choosing a shape in the medallion flow

*Level: expert.*

Putting the chapter together, the shapes map onto the layers like this:

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 270" role="img" aria-label="Medallion flow: JSON files into bronze with a VARIANT column and raw text, into silver with typed columns and an exploded order items table, into gold aggregates">
<rect x="10" y="50" width="120" height="150" rx="6" fill="none" stroke="currentColor"/>
<text x="70" y="74" text-anchor="middle" font-size="14" fill="currentColor">JSON files</text>
<text x="20" y="102" font-size="13" fill="currentColor">one order</text>
<text x="20" y="122" font-size="13" fill="currentColor">per line;</text>
<text x="20" y="142" font-size="13" fill="currentColor">new fields,</text>
<text x="20" y="162" font-size="13" fill="currentColor">bad lines</text>
<line x1="130" y1="125" x2="150" y2="125" stroke="currentColor" stroke-width="1.5"/>
<polygon points="150,119 160,125 150,131" fill="currentColor"/>
<rect x="160" y="50" width="145" height="150" rx="6" fill="none" stroke="currentColor"/>
<text x="232" y="74" text-anchor="middle" font-size="14" fill="currentColor">Bronze</text>
<text x="170" y="102" font-size="13" fill="currentColor">order_json VARIANT</text>
<text x="170" y="122" font-size="13" fill="currentColor">raw STRING</text>
<text x="170" y="142" font-size="13" fill="currentColor">try_parse_json</text>
<text x="170" y="162" font-size="13" fill="currentColor">no schema to fail</text>
<text x="170" y="182" font-size="13" fill="currentColor">+ key columns</text>
<line x1="305" y1="125" x2="325" y2="125" stroke="currentColor" stroke-width="1.5"/>
<polygon points="325,119 335,125 325,131" fill="currentColor"/>
<rect x="335" y="50" width="160" height="150" rx="6" fill="none" stroke="currentColor"/>
<text x="415" y="74" text-anchor="middle" font-size="14" fill="currentColor">Silver</text>
<text x="345" y="102" font-size="13" fill="currentColor">orders: v:a::TYPE</text>
<text x="345" y="122" font-size="13" fill="currentColor">ship_to STRUCT</text>
<text x="345" y="142" font-size="13" fill="currentColor">tags MAP</text>
<text x="345" y="162" font-size="13" fill="currentColor">order_items via</text>
<text x="345" y="182" font-size="13" fill="currentColor">LATERAL posexplode</text>
<line x1="495" y1="125" x2="515" y2="125" stroke="currentColor" stroke-width="1.5"/>
<polygon points="515,119 525,125 515,131" fill="currentColor"/>
<rect x="525" y="50" width="105" height="150" rx="6" fill="none" stroke="currentColor"/>
<text x="577" y="74" text-anchor="middle" font-size="14" fill="currentColor">Gold</text>
<text x="535" y="102" font-size="13" fill="currentColor">daily sales,</text>
<text x="535" y="122" font-size="13" fill="currentColor">product mix:</text>
<text x="535" y="142" font-size="13" fill="currentColor">flat columns</text>
<text x="320" y="232" text-anchor="middle" font-size="13" fill="currentColor">Flexible and complete on the left; typed, validated and fast to filter on the right.</text>
<text x="320" y="254" text-anchor="middle" font-size="13" fill="currentColor">Explode once, in silver; gold reads flat tables.</text>
</svg>
<figcaption>Figure 18.3. Where each nested shape usually lives in a medallion pipeline for Red Rock Supply orders.</figcaption>
</figure>

- **Bronze**: a `VARIANT` column (or, on older runtimes and in existing code, a JSON string) holding the whole record,
  the raw text for records that fail to parse, and a few top-level columns extracted for filtering and incremental
  processing (`order_id`, `order_ts`, ingest time). `try_parse_json` so that one bad line cannot stop the load.
- **Silver**: typed columns cast from the variant (`v:order_ts::TIMESTAMP`), a `STRUCT` for the address, a `MAP` or
  extracted columns for the tags, and a separate `order_items` table exploded once with line numbers. Run
  `schema_of_variant_agg` over bronze before writing the silver schema, and keep a check such as
  `aggregate(items ...) = amount`.
- **Gold**: flat aggregates; no nested parsing in BI queries.

What the docs say about cost, and nothing more: JSON strings are "Worst on read, because the entire string is parsed
for every query"; `VARIANT` has an "Optimized encoding that outperforms JSON strings on read and write"; structs are
"Best on read, but degrade[] past hundreds of columns"; maps and arrays are balanced, but "statistics can't be
collected" ([Model semi-structured data](https://docs.databricks.com/aws/en/semi-structured/)). The pages give no
numbers for these differences, so neither does this chapter. Where a field is used in filters, a plain column beats
all of them, because only plain columns (and struct fields) get the statistics that data skipping uses (see
[Chapter 22](22-Performance-Tuning.md)).

!!! tip "In the interview"
    **"The source adds a field `loyalty_tier` next week. What happens in each layer?"** A `VARIANT` or JSON string in
    bronze keeps it with no change. A `from_json` with a fixed schema silently drops it, so silver will not see it
    until someone adds it to the schema; `schema_of_variant_agg` over bronze shows when it started to arrive.
    Because bronze kept the full record, you can backfill silver from bronze instead of asking the source to resend.

## 18.11 Practice questions

Questions marked with outputs were run on the local engine (`src/ch18/ex7_practice.py` and `.out`). The
[SQL course](../../databases/sql/index.md) covers the generic joins and aggregates these build on.

**Q1. Name the three complex types and which part of a Red Rock Supply order each one models.**

??? success "Answer"
    `STRUCT` for the shipping address (fixed fields with their own types), `ARRAY` (of structs) for the order lines
    (an ordered list of one element type), `MAP` for tags (open-ended keys, all values the same type).

    **Why:** the choice follows from whether the set of fields is fixed (struct) or data-driven (map), and whether
    order and repetition matter (array).

**Q2. What does `SELECT element_at(array(10, 20, 30), 1), array(10, 20, 30)[1]` return?**

??? success "Answer"
    `10` and `20`.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +---+---+
    |a  |b  |
    +---+---+
    |10 |20 |
    +---+---+
    ```

    **Why:** `element_at` counts from 1, brackets from 0. Mixing them up is an off-by-one bug that type checks cannot
    catch.

**Q3. What does `SELECT size(array()), size(map('a', 1)), cardinality(array(1, NULL))` return?**

??? success "Answer"
    `0`, `1`, `2`.

    **Why:** NULL elements still count as elements. Only a NULL array itself makes `size` return NULL (or `-1` in
    Databricks Runtime with `spark.sql.ansi.enabled = false`, per the size page).

**Q4. Find the bug: `SELECT order_id, items[0].product_id AS first_product FROM silver_orders` worked in testing
and fails in production with `INVALID_ARRAY_INDEX`.**

??? success "Answer"
    Some order in production has an empty `items` array (a cancelled order). With ANSI behavior the bracket
    operator raises an error when the index is out of bounds. Fix: `get(items, 0).product_id` (0-based, NULL when out
    of bounds) or `try_element_at(items, 1).product_id` (1-based).

    **Why:** one bad row fails the whole query; test data rarely contains the edge case.

**Q5. Write the SQL: from `silver_orders`, return `order_id`, the shipping city and the `channel` tag.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, ship_to.city, tags['channel'] AS channel FROM silver_orders ORDER BY order_id;
    ```

    ```text
    +--------+-------+-------+
    |order_id|city   |channel|
    +--------+-------+-------+
    |1001    |Calgary|web    |
    |1002    |Banff  |mobile |
    |1003    |Calgary|web    |
    |1004    |Moab   |store  |
    |1005    |Canmore|NULL   |
    +--------+-------+-------+
    ```

    **Why:** dot for struct fields, brackets (or `element_at`, or `tags.channel` for string keys) for map values. A
    missing map key returns NULL.

**Q6. What is the difference between `ship_to.city` and `raw:ship_to.city`?**

??? success "Answer"
    `.` reads a field of a typed `STRUCT` column, checked when the query is compiled. `:` navigates a JSON document
    stored in a `STRING` (Databricks only, returns a `STRING`) or a `VARIANT` (returns a `VARIANT`); a missing path
    just returns NULL.

    **Why:** the first needs a schema up front; the second works on schemaless data and moves type checks to run
    time.

**Q7. What does `SELECT from_json('{"Qty": 2}', 'qty INT')` return?**

??? success "Answer"
    A struct with a NULL field.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +------+
    |parsed|
    +------+
    |{NULL}|
    +------+
    ```

    **Why:** schema field names in `from_json` are case-sensitive and must match the JSON exactly. There is no error,
    so this bug is silent.

**Q8. Write the SQL: parse `bronze_orders_raw.raw` and return `order_id`, `amount` as `DECIMAL(10,2)` and the
shipping city, skipping lines that do not parse.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT o.order_id, o.amount, o.ship_to.city
    FROM (SELECT from_json(raw, 'order_id INT, amount DECIMAL(10,2),
                                ship_to STRUCT<city: STRING>') AS o
          FROM bronze_orders_raw)
    WHERE o.order_id IS NOT NULL ORDER BY o.order_id;
    ```

    ```text
    +--------+------+-------+
    |order_id|amount|city   |
    +--------+------+-------+
    |1001    |59.90 |Calgary|
    |1002    |186.50|Banff  |
    |1003    |0.00  |Calgary|
    |1004    |136.94|Moab   |
    |1005    |45.00 |Canmore|
    +--------+------+-------+
    ```

    **Why:** the schema can list only the fields you need. The malformed line becomes a struct of NULLs in
    `PERMISSIVE` mode, so filtering on the key removes it (and you should count or quarantine those rows rather than
    drop them unseen).

**Q9. What do these return? `get_json_object('{"items":[{"n":1}]}', '$.items[*].n')` and the same on
`'{"items":[{"n":1},{"n":2}]}'`.**

??? success "Answer"
    `1` and `[1,2]`.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +--------+---------+
    |one_item|two_items|
    +--------+---------+
    |1       |[1,2]    |
    +--------+---------+
    ```

    **Why:** on this engine a single match comes back as a bare value, not a one-element array, so parsing the result
    as an array fails for one-item orders. Prefer `from_json` to a typed array, or `VARIANT`. (The Databricks page
    does not show the one-element case; not verified on Databricks.)

**Q10. Why does Databricks recommend `VARIANT` over JSON strings?**

??? success "Answer"
    Both store semi-structured data without a schema, but `VARIANT` is parsed once into an "optimized encoding that
    outperforms JSON strings for reads and writes", while a JSON string is parsed in full by every query. `VARIANT`
    also keeps value types and has case-sensitive, well-defined path semantics.

    **Why:** for bronze, you get the robustness of a string (new fields and type changes do not break ingestion) with
    better read performance.

**Q11. What do `parse_json('{"Status": "PLACED"}'):status` and `parse_json('{"Status": "PLACED"}'):Status`
return? What would `'{"Status": "PLACED"}':status` return on Databricks?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +----------+----------+
    |lower_path|exact_path|
    +----------+----------+
    |NULL      |"PLACED"  |
    +----------+----------+
    ```

    On a STRING the identifier is matched case-insensitively, so the third returns `PLACED` (a `STRING`). That one
    is Databricks only and was not run here; the rule is from the JSON path expression page.

    **Why:** `VARIANT` paths are case-sensitive; JSON-string paths are not. Migrating from strings to `VARIANT` can
    turn values into NULLs.

**Q12. Find the bug: `SELECT order_json:status, count(*) FROM shop.bronze.orders GROUP BY order_json:status`.**

??? success "Answer"
    `VARIANT` cannot be used in `GROUP BY` (`GROUP_EXPRESSION_TYPE_IS_NOT_ORDERABLE`). Cast it:
    `SELECT order_json:status::STRING AS status, count(*) FROM shop.bronze.orders GROUP BY ALL`.

    **Why:** the documented limits: no `GROUP BY`, `ORDER BY`, `DISTINCT` or set operators on variant columns.

**Q13. What do `parse_json('null') IS NULL`, `is_variant_null(parse_json('null'))` and
`parse_json('null')::INT IS NULL` return?**

??? success "Answer"
    `false`, `true`, `true`.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +-----+----+----+
    |a    |b   |c   |
    +-----+----+----+
    |false|true|true|
    +-----+----+----+
    ```

    **Why:** a JSON `null` stored in a `VARIANT` is a value (variant null), not a missing value (SQL `NULL`). Casting
    it to a type turns it into a SQL `NULL`.

**Q14. Write the SQL: load `bronze_orders_raw` into a `VARIANT` bronze table without failing on bad lines, and
flag the bad ones.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    CREATE TABLE bronze_orders (order_json VARIANT, raw STRING, parse_ok BOOLEAN) USING DELTA;
    INSERT INTO bronze_orders
    SELECT try_parse_json(raw), raw, try_parse_json(raw) IS NOT NULL FROM bronze_orders_raw;
    SELECT parse_ok, count(*) AS n FROM bronze_orders GROUP BY parse_ok ORDER BY parse_ok;
    ```

    ```text
    +--------+---+
    |parse_ok|n  |
    +--------+---+
    |false   |1  |
    |true    |5  |
    +--------+---+
    ```

    **Why:** `parse_json` raises `MALFORMED_RECORD_IN_PARSING` on the first bad line; `try_parse_json` returns NULL,
    and keeping `raw` means nothing is lost.

**Q15. Compare `v:qty::INT`, `variant_get(v, '$.qty', 'int')`, `try_variant_get(v, '$.qty', 'int')` and
`v:qty ?::INT`.**

??? success "Answer"
    The first two raise `INVALID_VARIANT_CAST` when the value cannot be cast and return NULL when the path is
    missing. The last two return NULL in both cases. `?::` is Databricks syntax (Databricks Runtime 15.3 and above per
    its page); the others ran here.

    **Why:** in silver you usually want the strict form inside tests and the tolerant form plus a quarantine check in
    the pipeline, so one bad value does not stop the job.

**Q16. What does `schema_of_variant_agg` return for `{"qty": 1}` and `{"qty": 2.5}`? And if a third row has
`{"qty": "three"}`?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +--------------------------+
    |s                         |
    +--------------------------+
    |OBJECT<qty: DECIMAL(21,1)>|
    +--------------------------+

    +--------------------+
    |s                   |
    +--------------------+
    |OBJECT<qty: VARIANT>|
    +--------------------+
    ```

    **Why:** the function merges field types using the least common type, and "When no such type exists, the type is
    derived as a `VARIANT`". A `VARIANT` in the result is a sign of a type conflict in the source.

**Q17. List the limitations of `VARIANT` columns that affect table design.**

??? success "Answer"
    No partitioning, no clustering key (and no Z-order), no `GROUP BY`/`ORDER BY`/`DISTINCT`/set operators, no
    generated variant columns, no `minValues`/`maxValues` statistics, a maximum value size (128 MiB, or 16 MiB in
    Databricks Runtime 17.1 and below, per the Delta feature page), and Delta tables with variant support need
    Databricks Runtime 15.4 LTS or above to read and write.

    **Why:** these push you to extract filter and join keys into ordinary columns next to the variant.

**Q18. How many rows do `explode(items)` and `explode_outer(items)` return over `silver_orders` (items counts 1, 2,
empty, 3, NULL)?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +------------+------------------+
    |explode_rows|explode_outer_rows|
    +------------+------------------+
    |6           |8                 |
    +------------+------------------+
    ```

    **Why:** `explode` drops the empty and NULL arrays; `explode_outer` keeps each of them as one row with a NULL
    element.

**Q19. Find the bug: revenue reported from this query is almost double the finance number.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT sum(o.amount) AS revenue
FROM silver_orders AS o, LATERAL explode(o.items) AS t(item)
WHERE o.status <> 'CANCELLED';
```

??? success "Answer"
    `amount` is an order-level column; after the explode it is repeated once per line, so multi-line orders are
    counted several times. Sum at order grain:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT sum(amount) AS revenue FROM silver_orders WHERE status <> 'CANCELLED';
    ```

    ```text
    buggy query: 843.72     fixed query: 428.34
    ```

    **Why:** explode changes the grain. Measures must be aggregated at the grain they belong to.

**Q20. Write the SQL: flatten `silver_orders` into `order_id, line_no, product_id, qty, unit_price` with line
numbers starting at 1, using the form the docs recommend.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (This is the query that built `silver_order_items` in 18.7; its output is shown there.)

    ```sql
    SELECT o.order_id, p.pos + 1 AS line_no, p.col.product_id, p.col.qty, p.col.unit_price
    FROM silver_orders AS o, LATERAL posexplode(o.items) AS p;
    ```

    **Why:** a table-valued generator in `FROM` replaces `LATERAL VIEW` and `SELECT`-list generators, which are
    deprecated in Databricks SQL and Databricks Runtime 12.2 LTS and above. `posexplode` gives the 0-based position.

**Q21. A colleague's code uses `LATERAL VIEW explode(items) t AS item`. Is it wrong?**

??? success "Answer"
    It still works, but the LATERAL VIEW page says the clause is deprecated in Databricks SQL and from Databricks
    Runtime 12.2. The equivalent is `FROM t, LATERAL explode(t.items) AS x(item)`; `LATERAL VIEW OUTER` becomes
    `LATERAL explode_outer(...)`.

    **Why:** interviewers check that you know both forms and which one is current.

**Q22. What does `SELECT * FROM explode(map('web', 2, 'store', 1)) AS t(channel, n)` return?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +-------+---+
    |channel|n  |
    +-------+---+
    |web    |2  |
    |store  |1  |
    +-------+---+
    ```

    **Why:** exploding a map yields two columns, `key` and `value` by default, renamed here by the alias list.

**Q23. Write the SQL: rebuild each order's `items` array from `silver_order_items`, in line order.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (Output in 18.7.)

    ```sql
    SELECT order_id,
           transform(array_sort(collect_list(struct(line_no, product_id, qty, unit_price))),
                     x -> named_struct('product_id', x.product_id, 'qty', x.qty, 'unit_price', x.unit_price)) AS items
    FROM silver_order_items GROUP BY order_id;
    ```

    **Why:** `collect_list` order is non-deterministic; putting `line_no` first in the struct lets `array_sort`
    order the elements, and `transform` removes the helper field.

**Q24. Why is `collect_list(product_id)` without sorting a problem in a test that compares arrays?**

??? success "Answer"
    The collect_list page says "The order of elements in the array is non-deterministic". The test may pass on one
    partition layout and fail on another. Sort the array, or compare with `array_sort` on both sides, or compare as
    sets with `array_except` in both directions.

    **Why:** distributed aggregation merges partial results in whatever order tasks finish.

**Q25. What does `SELECT transform(array(1, 2, 3), (x, i) -> x * i)` return?**

??? success "Answer"
    `[0, 2, 6]`.

    **Why:** the second lambda parameter is the 0-based index: 1·0, 2·1, 3·2.

**Q26. Find the bug: `aggregate(items, 0, (acc, i) -> acc + i.qty * i.unit_price)` fails with
`DATATYPE_MISMATCH.UNEXPECTED_INPUT_TYPE`.**

??? success "Answer"
    The accumulator must keep the type of `start`. `start` is `INT`, the merge result is `DECIMAL`. Fix:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (Output in 18.8.)

    ```sql
    aggregate(items, CAST(0 AS DECIMAL(10,2)),
              (acc, i) -> CAST(acc + i.qty * i.unit_price AS DECIMAL(10,2)))
    ```

    The result matches `amount` for every order (18.8).

    **Why:** decimal arithmetic widens the result type, so casting `start` alone is not enough; cast the merge result
    too.

**Q27. What do `exists(array(1, NULL, 3), x -> x = 2)`, `forall(array(1, NULL), x -> x > 0)` and
`array_contains(array(1, NULL), 1)` return?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +----+----+----+
    |a   |b   |c   |
    +----+----+----+
    |NULL|NULL|true|
    +----+----+----+
    ```

    **Why:** with no definite true (for `exists`) or false (for `forall`), a NULL comparison makes the result NULL.
    `array_contains` found 1, so the NULL element does not matter.

**Q28. Write the SQL: orders that have at least one line with `qty >= 3`, without exploding.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id FROM silver_orders WHERE exists(items, i -> i.qty >= 3) ORDER BY order_id;
    ```

    ```text
    +--------+
    |order_id|
    +--------+
    |1002    |
    |1004    |
    +--------+
    ```

    **Why:** `exists` keeps one row per order; exploding and filtering would need a `DISTINCT` afterwards.

**Q29. Write the SQL: flag orders whose `amount` does not equal the sum of their lines.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, amount, items_total, amount = items_total AS matches
    FROM (SELECT order_id, amount,
                 aggregate(items, CAST(0 AS DECIMAL(10,2)),
                           (acc, i) -> CAST(acc + i.qty * i.unit_price AS DECIMAL(10,2))) AS items_total
          FROM silver_orders)
    ORDER BY order_id;
    ```

    ```text
    +--------+------+-----------+-------+
    |order_id|amount|items_total|matches|
    +--------+------+-----------+-------+
    |1001    |59.90 |59.90      |true   |
    |1002    |186.50|186.50     |true   |
    |1003    |0.00  |0.00       |true   |
    |1004    |136.94|136.94     |true   |
    |1005    |45.00 |NULL       |NULL   |
    +--------+------+-----------+-------+
    ```

    **Why:** order 1005 has no `items` array, so the check returns NULL, not false. A data-quality rule written as
    `WHERE NOT matches` would miss it; use `WHERE matches IS NOT TRUE`.

**Q30. What do `array_sort(array('b', NULL, 'a'))` and `sort_array(array('b', NULL, 'a'))` return?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +------------+------------+
    |a           |b           |
    +------------+------------+
    |[a, b, NULL]|[NULL, a, b]|
    +------------+------------+
    ```

    **Why:** both pages say so: `array_sort` places NULLs at the end; `sort_array` places them first in ascending
    order.

**Q31. Write the SQL: remove the `promo` tag and upper-case the remaining tag keys.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, transform_keys(map_filter(tags, (k, v) -> k <> 'promo'), (k, v) -> upper(k)) AS tags
    FROM silver_orders ORDER BY order_id;
    ```

    ```text
    +--------+-------------------------------+
    |order_id|tags                           |
    +--------+-------------------------------+
    |1001    |{CHANNEL -> web}               |
    |1002    |{CHANNEL -> mobile}            |
    |1003    |{CHANNEL -> web}               |
    |1004    |{CHANNEL -> store, GIFT -> yes}|
    |1005    |NULL                           |
    +--------+-------------------------------+
    ```

    **Why:** `map_filter` and `transform_keys` both take a two-parameter lambda `(key, value)`. A NULL map stays
    NULL.

**Q32. Find the bug: `transform_keys(tags, (k, v) -> 'tag')` works on some orders and fails on others.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    ERROR: [DUPLICATED_MAP_KEY] Duplicate map key tag was found, please check the input data. ...
    ```

    Orders with one tag produce one key; orders with two tags produce `tag` twice, and map keys must be unique.

    **Why:** the transform_keys page says it raises `DUPLICATED_MAP_KEY` when the lambda produces duplicate keys.
    Make the new key unique or aggregate values first.

**Q33. Write the SQL: a map from `product_id` to `qty` for each order.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, map_from_arrays(items.product_id, items.qty) AS qty_by_product
    FROM silver_orders WHERE size(items) > 0 ORDER BY order_id;
    ```

    ```text
    +--------+------------------------+
    |order_id|qty_by_product          |
    +--------+------------------------+
    |1001    |{3 -> 2}                |
    |1002    |{1 -> 1, 5 -> 3}        |
    |1004    |{2 -> 1, 3 -> 1, 8 -> 4}|
    +--------+------------------------+
    ```

    `map_from_entries(transform(items, i -> struct(i.product_id, i.qty)))` is equivalent.

    **Why:** either fails with `DUPLICATED_MAP_KEY` if a product appears on two lines of one order; mention that.

**Q34. What does `SELECT arrays_zip(array(1, 2), array('a'))` return?**

??? success "Answer"
    `[{1, a}, {2, NULL}]`.

    **Why:** "Arrays that are shorter than the largest array are extended with null elements" (arrays_zip page).
    `zip_with` does the same before applying its lambda.

**Q35. Write the SQL: customers who have bought both product 3 and product 8, across all their orders.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id
    FROM silver_orders
    GROUP BY customer_id
    HAVING array_contains(flatten(collect_list(items.product_id)), 3)
       AND array_contains(flatten(collect_list(items.product_id)), 8);
    ```

    ```text
    +-----------+
    |customer_id|
    +-----------+
    |7          |
    +-----------+
    ```

    **Why:** `items.product_id` gives each order's product ids, `collect_list` gathers them per customer and
    `flatten` merges the arrays. On a large table a join on `silver_order_items` with
    `count(DISTINCT product_id) = 2` is the more familiar alternative.

**Q36. Write the PySpark: explode the items of `silver_orders` into columns and add `line_total`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    from pyspark.sql import functions as F
    (spark.table("silver_orders")
          .select("order_id", F.inline("items"))
          .withColumn("line_total", F.col("qty") * F.col("unit_price"))
          .orderBy("order_id", "product_id").show())
    ```

    ```text
    +--------+----------+---+----------+----------+
    |order_id|product_id|qty|unit_price|line_total|
    +--------+----------+---+----------+----------+
    |    1001|         3|  2|     29.95|     59.90|
    |    1002|         1|  1|    149.00|    149.00|
    |    1002|         5|  3|     12.50|     37.50|
    |    1004|         2|  1|     89.99|     89.99|
    |    1004|         3|  1|     29.95|     29.95|
    |    1004|         8|  4|      4.25|     17.00|
    +--------+----------+---+----------+----------+
    ```

    **Why:** `F.inline` turns an array of structs into one column per field; `F.explode("items")` followed by
    `select("item.*")` is the two-step equivalent.

**Q37. What does `SELECT to_json(parse_json('{"b": 1, "a": 0.10}'))` return, and why does it matter?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +---------------+
    |round_trip     |
    +---------------+
    |{"a":0.1,"b":1}|
    +---------------+
    ```

    **Why:** the pages warn that `to_json(parse_json(s))` is not an exact inverse: whitespace, key order and trailing
    zeros can change. Do not use string equality of re-serialized JSON for change detection; keep the raw text if you
    need byte-for-byte audit.

**Q38. Which orders does `WHERE forall(items, i -> i.unit_price < 50)` return from `silver_orders`?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +--------+------+
    |order_id|amount|
    +--------+------+
    |1001    |59.90 |
    |1003    |0.00  |
    +--------+------+
    ```

    **Why:** order 1003 has an empty array, and `forall` over an empty array is `true`. Order 1005 has a NULL array,
    so `forall` returns NULL and `WHERE` drops it. Add `size(items) > 0` if empty orders should not count.

**Q39. Scenario: analysts complain that queries on the bronze JSON-string table are slow, and they always filter
on order date and status. What do you change?**

??? success "Answer"
    Store the record as `VARIANT` instead of a string (Databricks Runtime 15.4 LTS or above for Delta tables), and
    extract `order_ts`, `status` and `order_id` into ordinary typed columns next to it, at ingestion. Better still,
    point analysts at silver, where those fields are typed columns and can be clustering keys.

    **Why:** JSON strings are re-parsed by every query, and neither JSON strings nor variant values get min/max
    statistics, so filters cannot skip files. The docs recommend extracting frequently queried fields as non-variant
    columns.

## Sources

- [Model semi-structured data](https://docs.databricks.com/aws/en/semi-structured/) (last updated Jun 11, 2026)
- [Query variant data](https://docs.databricks.com/aws/en/semi-structured/variant) (last updated Sep 11, 2026)
- [How is variant different than JSON strings?](https://docs.databricks.com/aws/en/semi-structured/variant-json-diff) (last updated Sep 11, 2026)
- [Ingest data as semi-structured variant type](https://docs.databricks.com/aws/en/ingestion/variant) (last updated Sep 11, 2026)
- [Variant type support for Apache Iceberg and Delta Lake](https://docs.databricks.com/aws/en/tables/features/variant) (last updated Sep 11, 2026)
- [Query JSON strings](https://docs.databricks.com/aws/en/semi-structured/json) (last updated Jun 12, 2024)
- [Transform complex data types](https://docs.databricks.com/aws/en/semi-structured/complex-types) (last updated Sep 11, 2026)
- [Higher-order functions](https://docs.databricks.com/aws/en/semi-structured/higher-order-functions) (last updated Sep 11, 2026)
- [`VARIANT` type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/variant-type) (last updated Sep 11, 2026)
- [`STRUCT` type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/struct-type) (last updated Sep 11, 2026)
- [`ARRAY` type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/array-type) (last updated Sep 11, 2026)
- [`MAP` type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/map-type) (last updated Sep 11, 2026)
- [JSON path expression](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-json-path-expression) (last updated Sep 11, 2026)
- [Lambda functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-lambda-functions) (last updated Sep 11, 2026)
- [LATERAL VIEW clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-lateral-view) (last updated Sep 11, 2026)
- [Table-valued function (TVF) invocation](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-tvf) (last updated Sep 11, 2026)
- Operator pages, each last updated Sep 11, 2026: [`:` (colon sign)](https://docs.databricks.com/aws/en/sql/language-manual/functions/colonsign), [`::` (colon colon sign)](https://docs.databricks.com/aws/en/sql/language-manual/functions/coloncolonsign), [`?::` (question double colon sign)](https://docs.databricks.com/aws/en/sql/language-manual/functions/questiondoublecolonsign), [`.` (dot sign)](https://docs.databricks.com/aws/en/sql/language-manual/functions/dotsign), [`[ ]` (bracket sign)](https://docs.databricks.com/aws/en/sql/language-manual/functions/bracketsign)
- Function pages, each last updated Sep 11, 2026: [struct](https://docs.databricks.com/aws/en/sql/language-manual/functions/struct), [named_struct](https://docs.databricks.com/aws/en/sql/language-manual/functions/named_struct), [array](https://docs.databricks.com/aws/en/sql/language-manual/functions/array), [map](https://docs.databricks.com/aws/en/sql/language-manual/functions/map), [element_at](https://docs.databricks.com/aws/en/sql/language-manual/functions/element_at), [try_element_at](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_element_at), [get](https://docs.databricks.com/aws/en/sql/language-manual/functions/get), [size](https://docs.databricks.com/aws/en/sql/language-manual/functions/size), [cardinality](https://docs.databricks.com/aws/en/sql/language-manual/functions/cardinality), [from_json](https://docs.databricks.com/aws/en/sql/language-manual/functions/from_json), [schema_of_json](https://docs.databricks.com/aws/en/sql/language-manual/functions/schema_of_json), [get_json_object](https://docs.databricks.com/aws/en/sql/language-manual/functions/get_json_object), [json_tuple](https://docs.databricks.com/aws/en/sql/language-manual/functions/json_tuple), [to_json](https://docs.databricks.com/aws/en/sql/language-manual/functions/to_json), [parse_json](https://docs.databricks.com/aws/en/sql/language-manual/functions/parse_json), [try_parse_json](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_parse_json), [variant_get](https://docs.databricks.com/aws/en/sql/language-manual/functions/variant_get), [try_variant_get](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_variant_get), [schema_of_variant](https://docs.databricks.com/aws/en/sql/language-manual/functions/schema_of_variant), [schema_of_variant_agg](https://docs.databricks.com/aws/en/sql/language-manual/functions/schema_of_variant_agg), [variant_explode](https://docs.databricks.com/aws/en/sql/language-manual/functions/variant_explode), [variant_explode_outer](https://docs.databricks.com/aws/en/sql/language-manual/functions/variant_explode_outer), [is_variant_null](https://docs.databricks.com/aws/en/sql/language-manual/functions/is_variant_null), [to_variant_object](https://docs.databricks.com/aws/en/sql/language-manual/functions/to_variant_object), [explode](https://docs.databricks.com/aws/en/sql/language-manual/functions/explode), [explode_outer](https://docs.databricks.com/aws/en/sql/language-manual/functions/explode_outer), [posexplode](https://docs.databricks.com/aws/en/sql/language-manual/functions/posexplode), [posexplode_outer](https://docs.databricks.com/aws/en/sql/language-manual/functions/posexplode_outer), [inline](https://docs.databricks.com/aws/en/sql/language-manual/functions/inline), [inline_outer](https://docs.databricks.com/aws/en/sql/language-manual/functions/inline_outer), [collect_list](https://docs.databricks.com/aws/en/sql/language-manual/functions/collect_list), [array_agg](https://docs.databricks.com/aws/en/sql/language-manual/functions/array_agg), [transform](https://docs.databricks.com/aws/en/sql/language-manual/functions/transform), [filter](https://docs.databricks.com/aws/en/sql/language-manual/functions/filter), [exists](https://docs.databricks.com/aws/en/sql/language-manual/functions/exists), [forall](https://docs.databricks.com/aws/en/sql/language-manual/functions/forall), [aggregate](https://docs.databricks.com/aws/en/sql/language-manual/functions/aggregate), [reduce](https://docs.databricks.com/aws/en/sql/language-manual/functions/reduce), [zip_with](https://docs.databricks.com/aws/en/sql/language-manual/functions/zip_with), [arrays_zip](https://docs.databricks.com/aws/en/sql/language-manual/functions/arrays_zip), [array_sort](https://docs.databricks.com/aws/en/sql/language-manual/functions/array_sort), [sort_array](https://docs.databricks.com/aws/en/sql/language-manual/functions/sort_array), [map_filter](https://docs.databricks.com/aws/en/sql/language-manual/functions/map_filter), [transform_keys](https://docs.databricks.com/aws/en/sql/language-manual/functions/transform_keys), [transform_values](https://docs.databricks.com/aws/en/sql/language-manual/functions/transform_values), [map_from_entries](https://docs.databricks.com/aws/en/sql/language-manual/functions/map_from_entries), [map_from_arrays](https://docs.databricks.com/aws/en/sql/language-manual/functions/map_from_arrays), [map_entries](https://docs.databricks.com/aws/en/sql/language-manual/functions/map_entries), [map_keys](https://docs.databricks.com/aws/en/sql/language-manual/functions/map_keys), [map_values](https://docs.databricks.com/aws/en/sql/language-manual/functions/map_values), [array_distinct](https://docs.databricks.com/aws/en/sql/language-manual/functions/array_distinct), [array_union](https://docs.databricks.com/aws/en/sql/language-manual/functions/array_union), [array_intersect](https://docs.databricks.com/aws/en/sql/language-manual/functions/array_intersect), [array_except](https://docs.databricks.com/aws/en/sql/language-manual/functions/array_except), [array_contains](https://docs.databricks.com/aws/en/sql/language-manual/functions/array_contains), [arrays_overlap](https://docs.databricks.com/aws/en/sql/language-manual/functions/arrays_overlap), [flatten](https://docs.databricks.com/aws/en/sql/language-manual/functions/flatten)
- [pyspark.sql.functions.transform](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.transform.html) and [pyspark.sql.functions.explode](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.explode.html), Apache Spark documentation (no last-updated date shown)
