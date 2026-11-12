# 24. JSON and arrays

*Much of the data a data engineer loads arrives as JSON: events from an app, responses from an API, logs. This
chapter reads JSON with SQL: picking out fields, telling a missing key from a null, turning a list inside a document
into rows, and building JSON from rows. Most of it runs the same on PostgreSQL and SQLite. It ends with PostgreSQL's
array type, which SQLite does not have.*

!!! abstract "In this chapter"
    **You will learn:**

    - storing JSON: PostgreSQL's `JSONB` and SQLite's JSON functions on text
    - the `->` and `->>` operators, which both databases share, and why `->>` needs a cast
    - missing keys versus JSON `null`
    - turning a JSON array into rows (`jsonb_array_elements`, `json_each`), and rows back into JSON
    - changing a value inside a document, and indexing JSON
    - PostgreSQL arrays: `ARRAY_AGG`, `UNNEST`, `ANY`, and splitting a string into rows
    - when JSON belongs in a column and when it should be flattened into tables

    **You need:** [chapter 7](07-Aggregation-Group-By-Having.md) and [chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md).

## 24.1 Storing JSON { #storing }

An app sends one JSON document per event. Users, carts and purchases all have different fields, which is why they
were sent as JSON instead of fixed columns.

<!-- sql setup -->
```sql
CREATE TABLE events (
  event_id INTEGER PRIMARY KEY,
  payload  JSONB NOT NULL
);
INSERT INTO events VALUES
  (1, '{"type": "view", "user": {"id": 1, "country": "CA"}, "page": "/lamp"}'),
  (2, '{"type": "cart", "user": {"id": 1, "country": "CA"},
        "items": [{"sku": "LAMP", "qty": 1}, {"sku": "NOTE", "qty": 3}]}'),
  (3, '{"type": "purchase", "user": {"id": 1, "country": "CA"},
        "items": [{"sku": "LAMP", "qty": 1}, {"sku": "NOTE", "qty": 3}], "total": 34.25}'),
  (4, '{"type": "view", "user": {"id": 2}, "page": "/chair"}'),
  (5, '{"type": "purchase", "user": {"id": 2, "country": "NG"},
        "items": [{"sku": "CHAIR", "qty": 1}], "total": 149.00, "coupon": null}');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

The same `CREATE TABLE` means different things on the two databases:

- **PostgreSQL** has two JSON types. `JSONB` (used here) stores the document parsed into a binary form: it checks
  that the text is valid JSON, is fast to query, and can be indexed, but does not keep spaces, key order or
  duplicate keys. `JSON` keeps the exact text and parses it again on every use. Use `JSONB` unless you must keep
  the text exactly as sent.
- **SQLite** has no JSON type. `JSONB` here is just a type name, and the documents are stored as text. Its JSON
  functions read that text when called (SQLite 3.45+ also has a binary form, made with the `jsonb()` function).

## 24.2 Reading fields: -> and ->> { #arrows }

Both databases have two arrow operators (SQLite since 3.38):

| Operator | Returns | Example |
| --- | --- | --- |
| `->` | a piece of JSON (an object, an array, a JSON value) | `payload -> 'user'` gives `{"id": 1, "country": "CA"}` |
| `->>` | a plain SQL value | `payload ->> 'type'` gives the text `view` |

Chain them to go deeper, with a number to pick an element of an array (counting from 0):

<!-- sql -->
```sql
SELECT event_id,
       payload ->> 'type'                                AS type,
       CAST(payload -> 'user' ->> 'id' AS INTEGER)        AS user_id,
       payload -> 'user' ->> 'country'                   AS country,
       payload -> 'items' -> 0 ->> 'sku'                 AS first_sku
FROM events
ORDER BY event_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| event_id | type | user_id | country | first_sku |
| --- | --- | --- | --- | --- |
| 1 | view | 1 | CA | *NULL* |
| 2 | cart | 1 | CA | LAMP |
| 3 | purchase | 1 | CA | LAMP |
| 4 | view | 2 | *NULL* | *NULL* |
| 5 | purchase | 2 | NG | CHAIR |
<!-- /result -->

Two things to notice:

- **A missing key gives NULL**, with no error: event 4's user has no country, views have no items.
- **Cast what you extract.** On PostgreSQL `->>` always returns text, even for `1` or `34.25`; on SQLite it returns
  a number for a JSON number. `CAST(... AS INTEGER)` or `AS NUMERIC(10,2)` gives the same type on both, and is
  needed anyway before you compare or add numbers on PostgreSQL.

<!-- sql -->
```sql
SELECT payload -> 'user' ->> 'country'               AS country,
       COUNT(*)                                      AS purchases,
       SUM(CAST(payload ->> 'total' AS NUMERIC(10,2))) AS revenue
FROM events
WHERE payload ->> 'type' = 'purchase'
GROUP BY payload -> 'user' ->> 'country'
ORDER BY country;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| country | purchases | revenue |
| --- | --- | --- |
| CA | 1 | 34.25 |
| NG | 1 | 149.00 |
<!-- /result -->

Other ways to write the same path: PostgreSQL also has `payload #>> '{user,country}'` and
`jsonb_extract_path_text(payload, 'user', 'country')`; SQLite has `json_extract(payload, '$.user.country')`, and its
arrows accept the same `'$.user.country'` paths. MySQL uses `payload->>'$.user.country'`; SQL Server
`JSON_VALUE(payload, '$.user.country')`; Databricks `payload:user.country` on a string.

## 24.3 Missing key or JSON null? { #null }

Event 5 has `"coupon": null`; the other events have no `coupon` key at all. `->>` gives SQL NULL for both. When the
difference matters ("the field was sent empty" versus "the app version did not send the field"), ask for the JSON
type of the value: it is `'null'` for a JSON null and SQL NULL for a missing key.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT event_id,
           payload ->> 'coupon'                 AS coupon,
           jsonb_typeof(payload -> 'coupon')    AS json_type,
           payload ? 'coupon'                   AS has_key
    FROM events
    WHERE payload ->> 'type' = 'purchase'
    ORDER BY event_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | event_id | coupon | json_type | has_key |
    | --- | --- | --- | --- |
    | 3 | *NULL* | *NULL* | false |
    | 5 | *NULL* | null | true |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite -->
    ```sql
    SELECT event_id,
           payload ->> 'coupon'                    AS coupon,
           json_type(payload, '$.coupon')          AS json_type,
           json_type(payload, '$.coupon') IS NOT NULL AS has_key
    FROM events
    WHERE payload ->> 'type' = 'purchase'
    ORDER BY event_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 2 rows.</p>

    | event_id | coupon | json_type | has_key |
    | --- | --- | --- | --- |
    | 3 | *NULL* | *NULL* | 0 |
    | 5 | *NULL* | null | 1 |
    <!-- /result -->

PostgreSQL's `?` operator tests whether a key exists (some database drivers treat `?` as a parameter marker; then
write `jsonb_exists(payload, 'coupon')` or escape it as `??`).

## 24.4 Turning a JSON array into rows { #explode }

Each purchase holds a list of items. To count units per product, the list must become rows: one row per item, next
to its event. This is often called **exploding** or **flattening** the array, and it is the most common JSON task in
data pipelines. PostgreSQL uses the set-returning function `jsonb_array_elements`; SQLite the table-valued function
`json_each`. Both are joined to their event row like a table.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT e.event_id,
           item ->> 'sku'                  AS sku,
           CAST(item ->> 'qty' AS INTEGER) AS qty
    FROM events e
    CROSS JOIN LATERAL jsonb_array_elements(e.payload -> 'items') AS item
    WHERE e.payload ->> 'type' = 'purchase'
    ORDER BY e.event_id, sku;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | event_id | sku | qty |
    | --- | --- | --- |
    | 3 | LAMP | 1 |
    | 3 | NOTE | 3 |
    | 5 | CHAIR | 1 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    SELECT e.event_id,
           j.value ->> 'sku'                  AS sku,
           CAST(j.value ->> 'qty' AS INTEGER) AS qty
    FROM events e
    CROSS JOIN json_each(e.payload, '$.items') AS j
    WHERE e.payload ->> 'type' = 'purchase'
    ORDER BY e.event_id, sku;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 3 rows.</p>

    | event_id | sku | qty |
    | --- | --- | --- |
    | 3 | LAMP | 1 |
    | 3 | NOTE | 3 |
    | 5 | CHAIR | 1 |
    <!-- /result -->

`LATERAL` lets the function on the right use `e`, the row on the left ([chapter 27](27-Grouping-Sets-Rollup-Cube-Lateral.md)
covers it); PostgreSQL also accepts the comma form `FROM events e, jsonb_array_elements(e.payload -> 'items') AS item`
without the word. A `CROSS JOIN` drops events whose array is missing or empty; when they must stay, use `LEFT JOIN
LATERAL ... ON true` on PostgreSQL or `LEFT JOIN json_each(...) ON true` on SQLite. `json_each` also returns the
element's position (`j.key`) and type; PostgreSQL gives the position with `WITH ORDINALITY`. Databricks and Spark
call this `explode`.

Once exploded, it is ordinary SQL:

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT item ->> 'sku'                       AS sku,
           SUM(CAST(item ->> 'qty' AS INTEGER)) AS units
    FROM events e
    CROSS JOIN LATERAL jsonb_array_elements(e.payload -> 'items') AS item
    WHERE e.payload ->> 'type' = 'purchase'
    GROUP BY item ->> 'sku'
    ORDER BY units DESC, sku;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | sku | units |
    | --- | --- |
    | NOTE | 3 |
    | CHAIR | 1 |
    | LAMP | 1 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    SELECT j.value ->> 'sku'                       AS sku,
           SUM(CAST(j.value ->> 'qty' AS INTEGER)) AS units
    FROM events e
    CROSS JOIN json_each(e.payload, '$.items') AS j
    WHERE e.payload ->> 'type' = 'purchase'
    GROUP BY j.value ->> 'sku'
    ORDER BY units DESC, sku;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 3 rows.</p>

    | sku | units |
    | --- | --- |
    | NOTE | 3 |
    | CHAIR | 1 |
    | LAMP | 1 |
    <!-- /result -->

## 24.5 Building JSON from rows { #build }

The opposite direction: one JSON document per customer, with their orders in a list, as an API might need. The
functions differ by name, and so does the text they print (PostgreSQL's `jsonb` adds spaces), so each database has
its own block.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT jsonb_build_object(
             'customer', c.name,
             'orders',   jsonb_agg(o.order_id ORDER BY o.order_id)
           ) AS doc
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    WHERE c.customer_id IN (2, 4)
    GROUP BY c.customer_id, c.name
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | doc |
    | --- |
    | {"orders": [102, 106, 113], "customer": "Ben Okafor"} |
    | {"orders": [105, 112], "customer": "Dana Kim"} |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite -->
    ```sql
    SELECT json_object(
             'customer', c.name,
             'orders',   json_group_array(o.order_id ORDER BY o.order_id)
           ) AS doc
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
    WHERE c.customer_id IN (2, 4)
    GROUP BY c.customer_id, c.name
    ORDER BY c.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 2 rows.</p>

    | doc |
    | --- |
    | {"customer":"Ben Okafor","orders":[102,106,113]} |
    | {"customer":"Dana Kim","orders":[105,112]} |
    <!-- /result -->

`jsonb_agg` and `json_group_array` are aggregates like `STRING_AGG`: they collect a group's values into a JSON array.
`ORDER BY` inside an aggregate needs SQLite 3.44+. Notice that PostgreSQL printed `orders` before `customer`: `jsonb`
does not keep the order keys were written in (it stores shorter keys first). JSON objects have no order by
definition, so nothing should depend on it.

## 24.6 Changing a value inside a document { #modify }

PostgreSQL's `jsonb_set` replaces the value at a path, `||` merges two objects (the right one wins), and `-` removes
a key. SQLite has `json_set`, `json_insert`, `json_replace` and `json_remove`.

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    UPDATE events
    SET payload = jsonb_set(payload, '{user,country}', '"BR"') - 'page'
    WHERE event_id = 4;
    SELECT payload FROM events WHERE event_id = 4;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

    | payload |
    | --- |
    | {"type": "view", "user": {"id": 2, "country": "BR"}} |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite -->
    ```sql
    UPDATE events
    SET payload = json_remove(json_set(payload, '$.user.country', 'BR'), '$.page')
    WHERE event_id = 4;
    SELECT payload FROM events WHERE event_id = 4;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

    | payload |
    | --- |
    | {"type":"view","user":{"id":2,"country":"BR"}} |
    <!-- /result -->

On PostgreSQL the new value is JSON (`'"BR"'`, with the quotes); on SQLite it is an SQL value (`'BR'`) that the
function turns into JSON. Note also that SQLite's output loses the original spacing: its JSON functions return
compact text.

## 24.7 Finding and indexing JSON { #index }

Filtering on a field with `->>` works everywhere, but reads every document. Two ways to make it fast:

- **An index on the expression**, on both databases: `CREATE INDEX events_type ON events ((payload ->> 'type'));`
  on PostgreSQL (note the double brackets), `CREATE INDEX events_type ON events (payload ->> 'type');` on SQLite.
  The query must use the same expression to benefit.
- **A GIN index on the whole document** (PostgreSQL only): `CREATE INDEX events_doc ON events USING GIN (payload);`
  serves the **containment** operator `@>`, "does the document contain this piece of JSON?", for any key:

<!-- sql pg -->
```sql
SELECT event_id
FROM events
WHERE payload @> '{"items": [{"sku": "NOTE"}]}'
ORDER BY event_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

| event_id |
| --- |
| 2 |
| 3 |
<!-- /result -->

Events 2 and 3 contain an item with `sku` NOTE; `@>` matches inside arrays without exploding them. On SQLite the
same question needs `EXISTS (SELECT 1 FROM json_each(payload, '$.items') j WHERE j.value ->> 'sku' = 'NOTE')`.
[Chapter 25](25-Indexes-and-Explain.md) shows how to check that a query uses an index.

## 24.8 PostgreSQL arrays { #arrays }

PostgreSQL columns can hold arrays of any type: `INTEGER[]`, `TEXT[]`. SQLite has no array type; use a JSON array
there. The useful parts:

<!-- sql pg -->
```sql
SELECT c.customer_id,
       ARRAY_AGG(o.order_id ORDER BY o.order_id)        AS order_ids,
       CARDINALITY(ARRAY_AGG(o.order_id))               AS orders,
       (ARRAY_AGG(o.order_id ORDER BY o.order_id))[1]   AS first_order
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
WHERE c.customer_id IN (1, 2)
GROUP BY c.customer_id
ORDER BY c.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

| customer_id | order_ids | orders | first_order |
| --- | --- | --- | --- |
| 1 | {101,103,110,115,120} | 5 | 101 |
| 2 | {102,106,113} | 3 | 102 |
<!-- /result -->

`ARRAY_AGG(x ORDER BY x)` is an aggregate that collects a group's values into one array; `CARDINALITY(array)` is the
number of elements in it; `array[1]` is its first element. PostgreSQL arrays count from **1**, not 0 like JSON arrays. `UNNEST` turns an array back into rows, and `= ANY(array)`
tests membership:

<!-- sql pg -->
```sql
SELECT product_id, name
FROM products
WHERE product_id = ANY (ARRAY[2, 4, 6])
ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

| product_id | name |
| --- | --- |
| 2 | Notebook |
| 4 | Coffee mug |
| 6 | Office chair |
<!-- /result -->

### Splitting a string into rows { #split-rows }

A column like `'home,office,gift'` (several values in one text, which a well-designed table would not have) is a
common test task: one row per value. PostgreSQL splits it into an array and unnests it. SQLite has no split
function; a common trick turns the text into a JSON array and uses `json_each`.

<!-- sql setup -->
```sql
CREATE TABLE product_tags (product_id INTEGER PRIMARY KEY, tags VARCHAR(100));
INSERT INTO product_tags VALUES (1, 'home,office'), (3, 'office,gift,pen'), (10, 'gift');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT p.product_id, t.tag
    FROM product_tags p
    CROSS JOIN LATERAL UNNEST(STRING_TO_ARRAY(p.tags, ',')) AS t(tag)
    ORDER BY p.product_id, t.tag;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 6 rows.</p>

    | product_id | tag |
    | --- | --- |
    | 1 | home |
    | 1 | office |
    | 3 | gift |
    | 3 | office |
    | 3 | pen |
    | 10 | gift |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    SELECT p.product_id, j.value AS tag
    FROM product_tags p
    CROSS JOIN json_each('["' || REPLACE(p.tags, ',', '","') || '"]') AS j
    ORDER BY p.product_id, tag;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 6 rows.</p>

    | product_id | tag |
    | --- | --- |
    | 1 | home |
    | 1 | office |
    | 3 | gift |
    | 3 | office |
    | 3 | pen |
    | 10 | gift |
    <!-- /result -->

The SQLite trick builds `["office","gift","pen"]` from the text. It breaks if a value contains a double quote or a
backslash; for messy text, a recursive CTE that cuts at each comma is safer ([chapter 11](11-CTEs-and-Recursive-CTEs.md)).
PostgreSQL 14+ also has `STRING_TO_TABLE(p.tags, ',')`, which returns the rows directly.

## 24.9 JSON column or real columns? { #design }

| Keep it as JSON when | Flatten it into columns and tables when |
| --- | --- |
| the shape changes often or differs per row (events from many app versions) | the same fields are in every row |
| you mostly store and pass it on, and read a few fields | you filter, join and aggregate on the fields |
| you need the original document for audit or replay | you need constraints: types, `NOT NULL`, foreign keys |

The usual pipeline does both: land the raw JSON as it came (the **bronze** layer, in medallion terms), then flatten
the fields that matter into typed columns and child tables (one row per item) for analysis. A JSON array inside a
column breaks first normal form ([chapter 19](19-Data-Modelling.md#normal-forms)); that is fine for landing, not for
the tables people query.

## 24.10 Summary { #summary }

- PostgreSQL: use `JSONB`. SQLite: JSON is text, read by JSON functions.
- `->` returns JSON, `->>` returns a plain value; chain them, with numbers (from 0) for array elements. Cast what
  you extract.
- A missing key and a JSON `null` both give SQL NULL with `->>`; tell them apart with `jsonb_typeof` / `?` on
  PostgreSQL, `json_type` on SQLite.
- Explode arrays into rows with `jsonb_array_elements` (with `LATERAL`) or `json_each`; build JSON with
  `jsonb_build_object` / `jsonb_agg` or `json_object` / `json_group_array`.
- Index JSON with an expression index, or (PostgreSQL) a GIN index for `@>`.
- PostgreSQL arrays count from 1: `ARRAY_AGG`, `UNNEST`, `= ANY`, `STRING_TO_ARRAY`.
- Land raw JSON; flatten what you query into typed columns.

!!! question "Asked aloud: JSON and semi-structured data"
    ??? note "JSON or JSONB in PostgreSQL?"
        `JSONB` almost always: it is stored parsed, so queries are faster and it can be indexed (GIN), and it is
        validated on insert. `JSON` keeps the exact text (spaces, key order, duplicate keys) and is re-parsed on each
        use; use it only when the original text must be preserved byte for byte.

    ??? note "How do you flatten a nested JSON array into rows?"
        Join each row to a function that returns one row per element: `jsonb_array_elements` with `LATERAL` in
        PostgreSQL, `json_each` in SQLite, `explode` in Spark and Databricks, `FLATTEN` in Snowflake, `UNNEST` in
        BigQuery. Then pick fields from each element. Use an outer join if rows with an empty array must stay.

    ??? note "How do you handle schema changes in incoming JSON?"
        Land the raw document unchanged, so nothing is lost. Extract fields with operators that return NULL for a
        missing key instead of failing, monitor the share of NULLs per field to notice when a field disappears or is
        renamed, and add new fields to the flattened tables when they are needed (schema evolution in lakehouse
        tables).

    ??? note "Why not keep everything as JSON?"
        Without columns there are no types, constraints or foreign keys, so bad data gets in silently; every query
        must parse and cast; indexes must be planned per path; and columnar engines compress and skip typed columns
        much better. JSON is a good landing format and a poor analysis format.

    ??? note "What is the difference between -> and ->>?"
        `->` returns the value as JSON (so you can keep navigating into it); `->>` returns it as a plain SQL value
        (text in PostgreSQL), for comparing, grouping or casting. The last step of a path is usually `->>`.

    ??? note "Array column or a child table?"
        A child table (one row per element) is the normalized design: each element can be indexed, constrained and
        joined. A PostgreSQL array column is convenient for small lists that are always read whole (tags), and avoids a
        join, but filtering inside it needs `ANY` or a GIN index, and elements cannot have foreign keys.

## Practice { #practice }

**24.1** Count the events of each type, and for each type how many had a user with no `country`. Order by type.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT payload ->> 'type' AS type,
           COUNT(*) AS events,
           SUM(CASE WHEN payload -> 'user' ->> 'country' IS NULL THEN 1 ELSE 0 END) AS no_country
    FROM events
    GROUP BY payload ->> 'type'
    ORDER BY type;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | type | events | no_country |
    | --- | --- | --- |
    | cart | 1 | 0 |
    | purchase | 2 | 0 |
    | view | 2 | 1 |
    <!-- /result -->

    `->>` takes a field out of a JSON value as text; `->` takes it out as JSON, so you can go one level deeper
    (`payload -> 'user' ->> 'country'`). A missing field gives NULL, which the `CASE` counts.


**24.2** For each purchase, return the event, the number of items (lines) in it and the total units, using the
items array, not the `total` field.

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        SELECT e.event_id,
               COUNT(*)                             AS products,
               SUM(CAST(item ->> 'qty' AS INTEGER)) AS units
        FROM events e
        CROSS JOIN LATERAL jsonb_array_elements(e.payload -> 'items') AS item
        WHERE e.payload ->> 'type' = 'purchase'
        GROUP BY e.event_id
        ORDER BY e.event_id;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

        | event_id | products | units |
        | --- | --- | --- |
        | 3 | 2 | 4 |
        | 5 | 1 | 1 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        SELECT e.event_id,
               COUNT(*)                                AS products,
               SUM(CAST(j.value ->> 'qty' AS INTEGER)) AS units
        FROM events e
        CROSS JOIN json_each(e.payload, '$.items') AS j
        WHERE e.payload ->> 'type' = 'purchase'
        GROUP BY e.event_id
        ORDER BY e.event_id;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 2 rows.</p>

        | event_id | products | units |
        | --- | --- | --- |
        | 3 | 2 | 4 |
        | 5 | 1 | 1 |
        <!-- /result -->

    PostgreSQL also has `jsonb_array_length(payload -> 'items')` and SQLite `json_array_length(payload, '$.items')` for
    the number of elements without exploding.

**24.3** Using `product_tags`, list each tag with the number of products that have it, most used first.

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        SELECT t.tag, COUNT(*) AS products
        FROM product_tags p
        CROSS JOIN LATERAL UNNEST(STRING_TO_ARRAY(p.tags, ',')) AS t(tag)
        GROUP BY t.tag
        ORDER BY products DESC, t.tag;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

        | tag | products |
        | --- | --- |
        | gift | 2 |
        | office | 2 |
        | home | 1 |
        | pen | 1 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        SELECT j.value AS tag, COUNT(*) AS products
        FROM product_tags p
        CROSS JOIN json_each('["' || REPLACE(p.tags, ',', '","') || '"]') AS j
        GROUP BY j.value
        ORDER BY products DESC, tag;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 4 rows.</p>

        | tag | products |
        | --- | --- |
        | gift | 2 |
        | office | 2 |
        | home | 1 |
        | pen | 1 |
        <!-- /result -->

    Both versions first turn the comma-separated text into one row per tag, then count. PostgreSQL:
    `STRING_TO_ARRAY` splits the text into an array and `UNNEST` turns the array into rows. SQLite has no
    arrays, so the text is rewritten as a JSON array and `json_each` returns one row per element.


**24.4** Return the ids of the events whose items include `NOTE`, on SQLite (without `@>`).

??? success "Answer"
    <!-- sql sqlite -->
    ```sql
    SELECT e.event_id
    FROM events e
    WHERE EXISTS (SELECT 1 FROM json_each(e.payload, '$.items') AS j
                  WHERE j.value ->> 'sku' = 'NOTE')
    ORDER BY e.event_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 2 rows.</p>

    | event_id |
    | --- |
    | 2 |
    | 3 |
    <!-- /result -->

    The same as the `@>` query in [24.7](#index): events 2 and 3. `EXISTS` keeps each event once, however many
    matching items it has; a join to `json_each` would repeat an event that had `NOTE` twice.

**Next:** [25. Indexes and EXPLAIN](25-Indexes-and-Explain.md).
