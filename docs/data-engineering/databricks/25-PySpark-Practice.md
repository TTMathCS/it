# 25. PySpark coding practice

*Many data engineer interviews include a live coding round: you get a small DataFrame and a question such as
"top two orders per customer" or "sessionize these clicks", and you write the PySpark while the interviewer
watches. This chapter is a workbook of 62 such tasks on the Red Rock Supply data, from a simple filter to an SCD
Type 2 merge. Each task shows its input and the expected output; the solution is hidden until you open it, with
the Databricks SQL that gives the same answer, the reason it works and the mistakes interviewers look for. Every
solution and every SQL equivalent was run on Apache Spark 4.2 with Delta Lake 4.4.1, and a script checked that
the two return the same columns, types and rows.*

!!! abstract "In this chapter"
    **You will learn:**

    - a method for live coding tasks: clarify, sketch the output, write in small steps, test the edge cases
    - a one-page PySpark cheat sheet: `col`, `lit`, `when`, `select`, `withColumn(s)`, `filter`, `groupBy`/`agg`,
      the join types (including `left_semi` and `left_anti`), `Window`, `explode`, `from_json`, `union` vs
      `unionByName`, `dropDuplicates`, `fillna`, `cast`, write modes
    - 62 tasks in ten groups: basics, aggregation, joins, window functions, deduplication, nested data, dates and
      sessions, data quality, Delta Lake from PySpark, and performance rewrites
    - for each task, the DataFrame code and the equivalent Databricks SQL side by side
    - the traps that cost candidates the most: NULLs in filters and `NOT IN`, duplicate join keys, the default
      window frame, `dropDuplicates` keeping an arbitrary row, `explode` dropping empty arrays, Python float
      literals in decimal arithmetic

    **You need:** [3. Apache Spark for data engineers](03-Apache-Spark.md) (DataFrames, lazy evaluation, joins
    and shuffles). The SQL side is explained in [17. Databricks SQL vs standard SQL](17-Databricks-SQL-vs-Standard.md),
    [18. Nested and semi-structured data](18-Semi-Structured-Data.md) and
    [19. The function toolbox](19-Function-Toolbox.md); the silver-layer patterns behind the deduplication and merge
    tasks are in [9. Building silver](09-Building-Silver.md).

    **Levels:** sections 25.1 to 25.4 beginner, 25.5 to 25.10 intermediate, 25.11 and 25.12 expert.

## 25.1 How to use this workbook

*Level: beginner.*

### What a live coding round looks like

The interviewer shares a notebook or a plain editor with one or two small DataFrames already defined, describes
the result they want, and watches you write it. Often there is no cluster, so you cannot run the code; sometimes
there is. Either way they look at four things: whether you ask the right questions before you type, whether
the code is correct on the awkward rows (NULLs, duplicates, ties, empty input), whether you know the DataFrame API
without searching for it, and whether you can say what the code costs (a shuffle, a broadcast, a Python UDF).

The tasks here are the kinds of questions those rounds use. Do them in order inside a group, because the groups
get harder. For each task:

1. Read the statement and the input, and look at the expected output.
2. Write your own solution first, in a notebook or on paper. Say out loud what each step does.
3. Open the solution and compare. Read "Why it works" and "Common mistakes" even when you got it right; they are
   the follow-up questions an interviewer asks.
4. Then write the SQL version yourself. Databricks interviews often ask for both, and Spark runs both through the
   same optimizer, so they compile to the same kind of plan.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 260" role="img" aria-label="Four steps for a live coding task: clarify, sketch input and output, write in small steps, test edge cases, with a loop from testing back to writing">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="10" y="40" width="140" height="130" rx="8"/>
<rect x="170" y="40" width="140" height="130" rx="8"/>
<rect x="330" y="40" width="140" height="130" rx="8"/>
<rect x="490" y="40" width="140" height="130" rx="8"/>
<path d="M150 105 L166 105"/>
<path d="M310 105 L326 105"/>
<path d="M470 105 L486 105"/>
<path d="M560 170 C560 230 400 230 400 174"/>
</g>
<g fill="currentColor">
<path d="M170 105 l-7 -4 v8 z"/>
<path d="M330 105 l-7 -4 v8 z"/>
<path d="M490 105 l-7 -4 v8 z"/>
<path d="M400 170 l-4 8 h8 z"/>
</g>
<g fill="currentColor" font-family="sans-serif" font-size="13" text-anchor="middle">
<text x="80" y="66" font-size="15" font-weight="bold">1. Clarify</text>
<text x="80" y="98">grain of the result</text>
<text x="80" y="118">keys, NULLs, ties</text>
<text x="80" y="138">batch or stream?</text>
<text x="240" y="66" font-size="15" font-weight="bold">2. Sketch</text>
<text x="240" y="98">3 to 5 input rows</text>
<text x="240" y="118">the rows you expect</text>
<text x="240" y="138">column names, types</text>
<text x="400" y="66" font-size="15" font-weight="bold">3. Write</text>
<text x="400" y="98">one step at a time</text>
<text x="400" y="118">name each step</text>
<text x="400" y="138">show() as you go</text>
<text x="560" y="66" font-size="15" font-weight="bold">4. Test</text>
<text x="560" y="98">NULLs, duplicates</text>
<text x="560" y="118">ties, empty input</text>
<text x="560" y="138">explain the cost</text>
<text x="480" y="248">found a wrong row: fix and rerun</text>
</g>
</svg>
<figcaption>Figure 25.1. A method for live coding tasks. Most lost points come from skipping step 1 (what is one
row of the result? what happens to NULLs and ties?) or step 4.</figcaption>
</figure>

The questions worth asking in step 1, because they change the code:

| Question | Why it changes the code |
| --- | --- |
| What is one row of the result (per customer, per order, per day)? | Decides the `groupBy` keys or the window partition. |
| Is the key unique in each input? | A duplicate key on either side of a join multiplies rows (Task 21). |
| What should happen to NULLs? | `status != 'X'` drops NULL rows (Task 6); `NOT IN` with a NULL returns nothing (Task 18). |
| How are ties broken? | `row_number` picks an arbitrary row among ties unless the ordering is complete (Tasks 27 and 36). |
| Should days with no data appear? | Then you need a calendar to join to (Task 46). |
| Is the input large? | Decides broadcast or not, and whether a Python UDF is acceptable (Tasks 22 and 59). |

!!! tip "In the interview"
    **"You have 20 minutes. Where do you start?"** Repeat the task in your own words, ask what one output row
    represents and how NULLs, duplicates and ties should be handled, and write down three or four input rows with
    the rows you expect back. Then build the answer one named step at a time (`daily = ...`, `ranked = ...`),
    checking each step. Finish by walking through an edge case and naming the expensive operations (shuffles,
    Python UDFs, `collect()`).

### How each task is laid out

Each task gives the statement in bold, the input, and the expected output. The input is either the four base
tables of 25.2 or a small DataFrame built inline in the task. The solution box holds:

- the PySpark solution, which leaves its answer in a DataFrame called `result`;
- the equivalent Databricks SQL, run against temp views of the same data;
- a note that both were run and compared. The scripts (in `src/ch25/`, one per group) assert that the PySpark
  and SQL answers have the same column names, the same column types and the same rows, in the same order where the
  task asks for one. The expected output you see is the real output of that run;
- why the solution works, and the mistakes candidates make.

Every code block in this chapter carries the label *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* None of the
tasks needs a Databricks workspace: they use only Apache Spark and Delta Lake APIs that Databricks also has. Two
local differences: there is no Unity Catalog, so tables are temp views or tables in the default schema (on
Databricks they would be `shop.silver.orders` and so on); and the session time zone is set to UTC, so timestamps
print in UTC.

### The cheat sheet

The block below is a one-screen reminder of the API that the tasks use. It runs as written on the base tables of
25.2 (`WORK` is a folder you can write to; on Databricks, use a Unity Catalog volume or a table).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# select, derived columns, CASE logic
o = (orders
     .select("order_id", "customer_id", "order_ts", "status", "amount")
     .withColumn("order_date", F.to_date("order_ts"))
     .withColumns({"status": F.coalesce("status", F.lit("UNKNOWN")),      # NULL -> default
                   "size": F.when(F.col("amount") < 50, "small")         # CASE WHEN
                            .when(F.col("amount") < 200, "medium")
                            .otherwise("large")}))

# filter: & | ~ with each condition in parentheses
big_shipped = o.filter((F.col("status") == "SHIPPED") & (F.col("amount") >= 100))

# group and aggregate (one row per group)
per_customer = orders.groupBy("customer_id").agg(
    F.count("*").alias("n_orders"),
    F.sum("amount").alias("total"),
    F.countDistinct("currency").alias("n_currencies"),
    F.count_if(F.col("status") == "SHIPPED").alias("n_shipped"))

# joins: inner, left, right, full, left_semi (keep matches), left_anti (keep non-matches)
named = orders.join(customers.select("customer_id", "name"), on="customer_id", how="inner")
no_orders = customers.join(orders, on="customer_id", how="left_anti")
lines = order_items.join(F.broadcast(products), on="product_id")         # broadcast hint

# window functions: rank, previous row, running total
w = Window.partitionBy("customer_id").orderBy("order_ts")
ranked = (orders
          .withColumn("n", F.row_number().over(w))
          .withColumn("prev_amount", F.lag("amount").over(w))
          .withColumn("running", F.sum("amount").over(
              w.rowsBetween(Window.unboundedPreceding, Window.currentRow))))

# JSON string -> struct/array, then one row per array element
raw = spark.createDataFrame([(1001, '[{"product_id": 3, "qty": 2}, {"product_id": 4, "qty": 1}]')],
                            "order_id INT, items STRING")
parsed = raw.withColumn("items", F.from_json("items", "ARRAY<STRUCT<product_id: INT, qty: INT>>"))
flat = parsed.select("order_id", F.explode("items").alias("it")).select("order_id", "it.*")

# union matches columns by POSITION; unionByName matches them by NAME
a = customers.select("city", "country")
b = customers.select("country", "city")
wrong = a.union(b)          # countries land in the city column, no error
right = a.unionByName(b)

# clean-up helpers
one_per_customer = orders.dropDuplicates(["customer_id"])    # an arbitrary row per key
filled = orders.fillna({"status": "UNKNOWN"})
as_text = orders.withColumn("amount", F.col("amount").cast("string"))

# write modes: "error"/"errorifexists" (default), "append", "overwrite", "ignore"
per_customer.write.format("delta").mode("overwrite").save(f"{WORK}/per_customer")

big_shipped.show()
ranked.filter("customer_id = 1").show()
flat.show()
wrong.where("city IN ('CA', 'US')").show()     # the rows that came from b
print("union rows:", wrong.count(), " unionByName rows:", right.count())
print("rows written:", spark.read.format("delta").load(f"{WORK}/per_customer").count())
```

What it printed:

```text
+--------+-----------+-------------------+-------+------+----------+------+
|order_id|customer_id|           order_ts| status|amount|order_date|  size|
+--------+-----------+-------------------+-------+------+----------+------+
|    1002|          2|2026-03-01 11:05:00|SHIPPED|249.00|2026-03-01| large|
|    1005|          4|2026-03-03 08:55:00|SHIPPED|318.00|2026-03-03| large|
|    1007|          3|2026-03-04 12:00:00|SHIPPED|159.00|2026-03-04|medium|
+--------+-----------+-------------------+-------+------+----------+------+

+--------+-----------+-------------------+-------+------+--------+---+-----------+-------+
|order_id|customer_id|           order_ts| status|amount|currency|  n|prev_amount|running|
+--------+-----------+-------------------+-------+------+--------+---+-----------+-------+
|    1001|          1|2026-03-01 10:15:00|SHIPPED| 59.90|     CAD|  1|       NULL|  59.90|
|    1003|          1|2026-03-02 09:40:00| PLACED|189.50|     CAD|  2|      59.90| 249.40|
|    1008|          1|2026-03-04 19:10:00|   NULL| 78.00|     CAD|  3|     189.50| 327.40|
+--------+-----------+-------------------+-------+------+--------+---+-----------+-------+

+--------+----------+---+
|order_id|product_id|qty|
+--------+----------+---+
|    1001|         3|  2|
|    1001|         4|  1|
+--------+----------+---+

+----+---------+
|city|  country|
+----+---------+
|  CA|  Calgary|
|  US|   Denver|
|  US|     Moab|
|  CA|Vancouver|
+----+---------+

union rows: 8  unionByName rows: 8
rows written: 4
```

Points to remember from it:

- `F.col("x")` refers to a column, `F.lit(5)` is a constant. Most functions also accept a column name as a plain
  string, but comparisons need `F.col("x") == 5`.
- Combine conditions with `&`, `|` and `~`, and put each condition in parentheses: Python gives `&` a higher
  precedence than `==`, so `F.col("a") == 1 & F.col("b") == 2` does not mean what it seems to.
- `withColumns({...})` adds or replaces several columns in one projection. A loop of `withColumn` calls builds a
  deep plan (Task 62).
- `F.when(...).when(...).otherwise(...)` is `CASE WHEN`. Without `otherwise`, rows that match no branch get NULL.
- `how=` in `join` accepts `inner`, `left`, `right`, `full`, `left_semi`, `left_anti` and `cross` (with aliases
  such as `left_outer` and `anti`) ([DataFrame.join](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.join.html)).
- `union` "resolves columns by position (not by name)"
  ([DataFrame.union](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.union.html)).
  In the run, `a.union(b)` put the country codes into the `city` column without any error. Use `unionByName`,
  which also has `allowMissingColumns=True` to fill missing columns with NULL
  ([DataFrame.unionByName](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.unionByName.html)).
- Write modes are `append`, `overwrite`, `error`/`errorifexists` and `ignore`; the default is `errorifexists`
  ([Generic Load/Save Functions](https://spark.apache.org/docs/latest/sql-data-sources-load-save-functions.html)).
- The engine here runs with ANSI mode on. `spark.sql.ansi.enabled` is "enabled by default in Apache Spark 4.0
  and Databricks Runtime 17.0 and above"
  ([ANSI compliance in Databricks Runtime](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-ansi-compliance)).
  With it, a `cast` of a bad string fails the query, so use `try_cast` (Task 4).

## 25.2 The base tables

*Level: beginner.*

These four DataFrames are the Red Rock Supply data used throughout the book (chapters 3 and 17 use the same rows).
Run this block once; most tasks start from it. It also registers each DataFrame as a temp view, so the SQL
versions can say `FROM orders`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from datetime import datetime as dt
from decimal import Decimal as D

from pyspark.sql import functions as F
from pyspark.sql.window import Window

customers = spark.createDataFrame([
    (1, "Ana Lopez",    "ana@example.com",   "Calgary",   "CA", dt(2026, 1, 5, 9, 0)),
    (2, "Ben Okafor",   "ben@example.com",   "Denver",    "US", dt(2026, 1, 7, 12, 30)),
    (3, "Chloe Martin", "chloe@example.com", "Moab",      "US", dt(2026, 1, 9, 16, 45)),
    (4, "Dev Patel",    "dev@example.com",   "Vancouver", "CA", dt(2026, 1, 11, 8, 15)),
], "customer_id INT, name STRING, email STRING, city STRING, country STRING, updated_at TIMESTAMP")

products = spark.createDataFrame([
    (1, "Trail Tent 2P",     "Camping", D("249.00")),
    (2, "Down Sleeping Bag", "Camping", D("189.50")),
    (3, "Trekking Poles",    "Hiking",  D("29.95")),
    (4, "Headlamp",          "Hiking",  D("39.00")),
    (5, "Rain Shell",        "Apparel", D("159.00")),
], "product_id INT, name STRING, category STRING, price DECIMAL(10,2)")

orders = spark.createDataFrame([
    (1001, 1, dt(2026, 3, 1, 10, 15), "SHIPPED",   D("59.90"),  "CAD"),
    (1002, 2, dt(2026, 3, 1, 11, 5),  "SHIPPED",   D("249.00"), "USD"),
    (1003, 1, dt(2026, 3, 2, 9, 40),  "PLACED",    D("189.50"), "CAD"),
    (1004, 3, dt(2026, 3, 2, 14, 20), "CANCELLED", D("39.00"),  "USD"),
    (1005, 4, dt(2026, 3, 3, 8, 55),  "SHIPPED",   D("318.00"), "CAD"),
    (1006, 2, dt(2026, 3, 3, 17, 30), "PLACED",    D("29.95"),  "USD"),
    (1007, 3, dt(2026, 3, 4, 12, 0),  "SHIPPED",   D("159.00"), "USD"),
    (1008, 1, dt(2026, 3, 4, 19, 10), None,        D("78.00"),  "CAD"),
], "order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING, amount DECIMAL(10,2), currency STRING")

order_items = spark.createDataFrame([
    (1001, 3, 2, D("29.95")), (1002, 1, 1, D("249.00")), (1003, 2, 1, D("189.50")),
    (1004, 4, 1, D("39.00")), (1005, 5, 2, D("159.00")), (1006, 3, 1, D("29.95")),
    (1007, 5, 1, D("159.00")), (1008, 4, 2, D("39.00")),
], "order_id INT, product_id INT, qty INT, unit_price DECIMAL(10,2)")

# The same four tables as SQL views, for the SQL versions of each task
for name, df in [("customers", customers), ("products", products),
                 ("orders", orders), ("order_items", order_items)]:
    df.createOrReplaceTempView(name)
```

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
customers.show()
products.show()
orders.show()
order_items.show()
```

```text
+-----------+------------+-----------------+---------+-------+-------------------+
|customer_id|        name|            email|     city|country|         updated_at|
+-----------+------------+-----------------+---------+-------+-------------------+
|          1|   Ana Lopez|  ana@example.com|  Calgary|     CA|2026-01-05 09:00:00|
|          2|  Ben Okafor|  ben@example.com|   Denver|     US|2026-01-07 12:30:00|
|          3|Chloe Martin|chloe@example.com|     Moab|     US|2026-01-09 16:45:00|
|          4|   Dev Patel|  dev@example.com|Vancouver|     CA|2026-01-11 08:15:00|
+-----------+------------+-----------------+---------+-------+-------------------+

+----------+-----------------+--------+------+
|product_id|             name|category| price|
+----------+-----------------+--------+------+
|         1|    Trail Tent 2P| Camping|249.00|
|         2|Down Sleeping Bag| Camping|189.50|
|         3|   Trekking Poles|  Hiking| 29.95|
|         4|         Headlamp|  Hiking| 39.00|
|         5|       Rain Shell| Apparel|159.00|
+----------+-----------------+--------+------+

+--------+-----------+-------------------+---------+------+--------+
|order_id|customer_id|           order_ts|   status|amount|currency|
+--------+-----------+-------------------+---------+------+--------+
|    1001|          1|2026-03-01 10:15:00|  SHIPPED| 59.90|     CAD|
|    1002|          2|2026-03-01 11:05:00|  SHIPPED|249.00|     USD|
|    1003|          1|2026-03-02 09:40:00|   PLACED|189.50|     CAD|
|    1004|          3|2026-03-02 14:20:00|CANCELLED| 39.00|     USD|
|    1005|          4|2026-03-03 08:55:00|  SHIPPED|318.00|     CAD|
|    1006|          2|2026-03-03 17:30:00|   PLACED| 29.95|     USD|
|    1007|          3|2026-03-04 12:00:00|  SHIPPED|159.00|     USD|
|    1008|          1|2026-03-04 19:10:00|     NULL| 78.00|     CAD|
+--------+-----------+-------------------+---------+------+--------+

+--------+----------+---+----------+
|order_id|product_id|qty|unit_price|
+--------+----------+---+----------+
|    1001|         3|  2|     29.95|
|    1002|         1|  1|    249.00|
|    1003|         2|  1|    189.50|
|    1004|         4|  1|     39.00|
|    1005|         5|  2|    159.00|
|    1006|         3|  1|     29.95|
|    1007|         5|  1|    159.00|
|    1008|         4|  2|     39.00|
+--------+----------+---+----------+
```

Things worth noticing before you start, because the tasks use them: order 1008 has a NULL `status`; customer 1
has three orders, customer 4 only one; every order has exactly one line in `order_items`, and its `amount` equals
`qty * unit_price`; and units sold tie at 3 for three products.

## 25.3 Basics: select, filter, derived columns

*Level: beginner.*

These are warm-ups, but each hides one trap that interviewers like: ordering, decimal types, the order of `when`
branches, unsafe casts, regular expressions in `split`, NULLs in a filter, and the numbering of weekdays.
Chapter 3 explains the DataFrame API they use ([3. Apache Spark](03-Apache-Spark.md)).

**Task 1. From `orders`, list `order_id`, `customer_id` and `amount` of the `SHIPPED` orders with an amount of at
least 100, largest amount first.**

Input: `orders` (25.2). Expected output:

```text
+--------+-----------+------+
|order_id|customer_id|amount|
+--------+-----------+------+
|1005    |4          |318.00|
|1002    |2          |249.00|
|1007    |3          |159.00|
+--------+-----------+------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders
              .filter((F.col("status") == "SHIPPED") & (F.col("amount") >= 100))
              .select("order_id", "customer_id", "amount")
              .orderBy(F.col("amount").desc()))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, customer_id, amount
    FROM orders
    WHERE status = 'SHIPPED' AND amount >= 100
    ORDER BY amount DESC;
    ```

    Both versions were run in `t01_basics.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** `filter` keeps the rows where the whole condition is true; `&` needs each side in
    parentheses. `orderBy(F.col("amount").desc())` sorts the final result. `filter` and `where` are the same
    method.

    **Common mistakes:** writing `F.col("status") == "SHIPPED" & F.col("amount") >= 100` without parentheses.
    Python applies `&` before `==` and `>=`, so this is not the intended condition, and it fails with an error
    (Q4 in 25.13 shows the message); using Python's `and`, which fails the same way; sorting before the filter and assuming the order survives later
    shuffles. Only the last `orderBy` defines the order of the output.

**Task 2. Add `amount_cad`: CAD amounts stay as they are, USD amounts are converted at 1 USD = 1.35 CAD and
rounded to 2 decimals.**

Input: `orders`. Expected output:

```text
+--------+--------+------+----------+
|order_id|currency|amount|amount_cad|
+--------+--------+------+----------+
|1001    |CAD     |59.90 |59.90     |
|1002    |USD     |249.00|336.15    |
|1003    |CAD     |189.50|189.50    |
|1004    |USD     |39.00 |52.65     |
|1005    |CAD     |318.00|318.00    |
|1006    |USD     |29.95 |40.43     |
|1007    |USD     |159.00|214.65    |
|1008    |CAD     |78.00 |78.00     |
+--------+--------+------+----------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders
              .withColumn("amount_cad",
                          F.when(F.col("currency") == "USD", F.round(F.col("amount") * F.lit(D("1.35")), 2))
                           .otherwise(F.col("amount")))
              .select("order_id", "currency", "amount", "amount_cad")
              .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, currency, amount,
           CASE WHEN currency = 'USD' THEN round(amount * 1.35, 2) ELSE amount END AS amount_cad
    FROM orders
    ORDER BY order_id;
    ```

    Both versions were run in `t01_basics.py`, which asserts that they return the same columns, column types and 8 rows in the same order. The output is the expected output above.

    **Why it works:** `F.when(cond, value).otherwise(other)` is `CASE WHEN`. `D` is `decimal.Decimal`, imported in
    the setup block, so `F.lit(D("1.35"))` is a `DECIMAL` literal, the same type the SQL literal `1.35` gets.

    **Common mistakes:** writing `F.col("amount") * 1.35`. A Python float becomes a `DOUBLE`, so the result is a
    floating-point number, not a decimal. The script showed the difference:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    as_float = orders.select(F.round(F.col("amount") * 1.35, 2).alias("x"))   # Python float literal
    print("with D('1.35'):", result.schema["amount_cad"].dataType)
    print("with 1.35:     ", as_float.schema["x"].dataType)
    ```

    ```text
    with D('1.35'): DecimalType(13,2)
    with 1.35:      DoubleType()
    ```

    For money, keep decimals end to end. In SQL the literal `1.35` is already a decimal.

**Task 3. For each order, show `amount`, a `size` bucket (`small` under 50, `medium` under 200, otherwise `large`),
and `status` with NULL replaced by `UNKNOWN`.**

Input: `orders`. Expected output:

```text
+--------+------+------+---------+
|order_id|amount|size  |status   |
+--------+------+------+---------+
|1001    |59.90 |medium|SHIPPED  |
|1002    |249.00|large |SHIPPED  |
|1003    |189.50|medium|PLACED   |
|1004    |39.00 |small |CANCELLED|
|1005    |318.00|large |SHIPPED  |
|1006    |29.95 |small |PLACED   |
|1007    |159.00|medium|SHIPPED  |
|1008    |78.00 |medium|UNKNOWN  |
+--------+------+------+---------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders
              .withColumns({
                  "size": F.when(F.col("amount") < 50, "small")
                           .when(F.col("amount") < 200, "medium")
                           .otherwise("large"),
                  "status": F.coalesce(F.col("status"), F.lit("UNKNOWN")),
              })
              .select("order_id", "amount", "size", "status")
              .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, amount,
           CASE WHEN amount < 50 THEN 'small'
                WHEN amount < 200 THEN 'medium'
                ELSE 'large' END            AS size,
           coalesce(status, 'UNKNOWN')      AS status
    FROM orders
    ORDER BY order_id;
    ```

    Both versions were run in `t01_basics.py`, which asserts that they return the same columns, column types and 8 rows in the same order. The output is the expected output above.

    **Why it works:** `when` branches are tested in order and the first true one wins, so the second branch only
    sees amounts of 50 or more. `coalesce` returns its first non-NULL argument. `withColumns` replaces the existing
    `status` column because a key in the dictionary has the same name.

    **Common mistakes:** putting the widest branch first (`amount < 200` before `amount < 50`), which makes
    `small` unreachable; forgetting `otherwise`, which leaves NULL; writing `F.coalesce("status", "UNKNOWN")`,
    where the second string is read as a column name, not a value. Use `F.lit("UNKNOWN")`.

**Task 4. The raw feed has every column as a string. Type it: `order_id` as INT, `amount` as DECIMAL(10,2) after
trimming spaces, `order_ts` as TIMESTAMP, `status` trimmed and in capitals. Bad values must become NULL instead of
failing the job.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
raw_orders = spark.createDataFrame([
    ("1001", " 59.90 ", "2026-03-01 10:15:00", "shipped "),
    ("1009", "abc",     "2026-03-05 08:00:00", "Placed"),
    ("1010", "12.5",    "not a date",          "PLACED"),
    (None,   "20.00",   "2026-03-05 09:30:00", "PLACED"),
], "order_id STRING, amount STRING, order_ts STRING, status STRING")
raw_orders.createOrReplaceTempView("raw_orders")
```

Expected output:

```text
+--------+------+-------------------+-------+
|order_id|amount|order_ts           |status |
+--------+------+-------------------+-------+
|1001    |59.90 |2026-03-01 10:15:00|SHIPPED|
|1009    |NULL  |2026-03-05 08:00:00|PLACED |
|1010    |12.50 |NULL               |PLACED |
|NULL    |20.00 |2026-03-05 09:30:00|PLACED |
+--------+------+-------------------+-------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (raw_orders
              .select(
                  F.col("order_id").try_cast("int").alias("order_id"),
                  F.trim("amount").try_cast("decimal(10,2)").alias("amount"),
                  F.try_to_timestamp("order_ts").alias("order_ts"),
                  F.upper(F.trim("status")).alias("status"))
              .orderBy(F.col("order_id").asc_nulls_last()))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT try_cast(order_id AS INT)                  AS order_id,
           try_cast(trim(amount) AS DECIMAL(10,2))    AS amount,
           try_to_timestamp(order_ts)                 AS order_ts,
           upper(trim(status))                        AS status
    FROM raw_orders
    ORDER BY order_id ASC NULLS LAST;
    ```

    Both versions were run in `t01_basics.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** `try_cast` (a `Column` method since Spark 4.0) and `try_to_timestamp` return NULL for values
    they cannot convert, instead of raising an error
    ([Column.try_cast](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.Column.try_cast.html)).
    With ANSI mode on, a plain `cast` of `'abc'` fails the whole query:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    try:
        raw_orders.select(F.col("amount").cast("decimal(10,2)")).collect()
    except Exception as e:
        print(type(e).__name__, str(e).split(".")[0])
    ```

    ```text
    NumberFormatException [CAST_INVALID_INPUT] The value 'abc' of the type "STRING" cannot be cast to "DECIMAL(10,2)" because it is malformed
    ```

    **Common mistakes:** using `cast` and only finding out at run time; forgetting `trim`, so `' 59.90 '` fails
    to convert; and silently turning bad values into NULLs without counting them. In a real silver job you keep
    the bad rows with a reason (Task 51 and [9. Building silver](09-Building-Silver.md)).

**Task 5. From `customers`, return `customer_id`, the first name, the email domain and the city in capitals.**

Input: `customers`. Expected output:

```text
+-----------+----------+------------+---------+
|customer_id|first_name|email_domain|city     |
+-----------+----------+------------+---------+
|1          |Ana       |example.com |CALGARY  |
|2          |Ben       |example.com |DENVER   |
|3          |Chloe     |example.com |MOAB     |
|4          |Dev       |example.com |VANCOUVER|
+-----------+----------+------------+---------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (customers
              .select(
                  "customer_id",
                  F.split("name", " ").getItem(0).alias("first_name"),
                  F.substring_index("email", "@", -1).alias("email_domain"),
                  F.upper("city").alias("city"))
              .orderBy("customer_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id,
           split(name, ' ')[0]               AS first_name,
           substring_index(email, '@', -1)  AS email_domain,
           upper(city)                       AS city
    FROM customers
    ORDER BY customer_id;
    ```

    Both versions were run in `t01_basics.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** `split` returns an array and `getItem(0)` (or `[0]` in SQL) takes the first element;
    `substring_index(s, '@', -1)` returns everything after the last `@`.

    **Common mistakes:** `split`'s second argument is a regular expression, not a plain string. Splitting on `"."`
    splits on every character:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    spark.createDataFrame([("a.b.c",)], "s STRING").select(
        F.split("s", ".").alias("split_dot"),
        F.split("s", "[.]").alias("split_escaped")).show()
    ```

    ```text
    +------------+-------------+
    |   split_dot|split_escaped|
    +------------+-------------+
    |[, , , , , ]|    [a, b, c]|
    +------------+-------------+
    ```

    Escape it as `"[.]"` or `"\\."`. Also, arrays in `split` results start at index 0, while `element_at` starts
    at 1.

**Task 6. List every order that is not cancelled. Order 1008 has no status yet and must be kept.**

Input: `orders`. Expected output:

```text
+--------+-------+
|order_id|status |
+--------+-------+
|1001    |SHIPPED|
|1002    |SHIPPED|
|1003    |PLACED |
|1005    |SHIPPED|
|1006    |PLACED |
|1007    |SHIPPED|
|1008    |NULL   |
+--------+-------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders
              .filter(~F.col("status").eqNullSafe("CANCELLED"))
              .select("order_id", "status")
              .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, status
    FROM orders
    WHERE status IS DISTINCT FROM 'CANCELLED'
    ORDER BY order_id;
    ```

    Both versions were run in `t01_basics.py`, which asserts that they return the same columns, column types and 7 rows in the same order. The output is the expected output above.

    **Why it works:** in SQL logic, `NULL != 'CANCELLED'` is NULL, not true, and `filter` keeps only true rows.
    `eqNullSafe` (SQL `<=>`) treats NULL as a comparable value, so `NOT (status <=> 'CANCELLED')` is true for the
    NULL row. `IS DISTINCT FROM` is the standard SQL spelling of the same test.

    **Common mistakes:** the natural filter loses order 1008 without any warning:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    print("status != 'CANCELLED' keeps", orders.filter(F.col("status") != "CANCELLED").count(), "rows")
    print("NULL-safe version keeps   ", result.count(), "rows")
    ```

    ```text
    status != 'CANCELLED' keeps 6 rows
    NULL-safe version keeps    7 rows
    ```

    Interviewers add a NULL row to the input precisely to see whether you notice. The SQL course covers NULL
    logic in general ([SQL course](../../databases/sql/index.md)).

**Task 7. For each order, show the order date, the hour, the short day name, and whether it was placed on a
weekend.**

Input: `orders`. Expected output:

```text
+--------+----------+----+--------+----------+
|order_id|order_date|hour|day_name|is_weekend|
+--------+----------+----+--------+----------+
|1001    |2026-03-01|10  |Sun     |true      |
|1002    |2026-03-01|11  |Sun     |true      |
|1003    |2026-03-02|9   |Mon     |false     |
|1004    |2026-03-02|14  |Mon     |false     |
|1005    |2026-03-03|8   |Tue     |false     |
|1006    |2026-03-03|17  |Tue     |false     |
|1007    |2026-03-04|12  |Wed     |false     |
|1008    |2026-03-04|19  |Wed     |false     |
+--------+----------+----+--------+----------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders
              .withColumns({
                  "order_date": F.to_date("order_ts"),
                  "hour": F.hour("order_ts"),
                  "day_name": F.date_format("order_ts", "EEE"),
                  "is_weekend": F.dayofweek("order_ts").isin(1, 7),   # 1 = Sunday, 7 = Saturday
              })
              .select("order_id", "order_date", "hour", "day_name", "is_weekend")
              .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id,
           to_date(order_ts)               AS order_date,
           hour(order_ts)                  AS hour,
           date_format(order_ts, 'EEE')    AS day_name,
           dayofweek(order_ts) IN (1, 7)   AS is_weekend
    FROM orders
    ORDER BY order_id;
    ```

    Both versions were run in `t01_basics.py`, which asserts that they return the same columns, column types and 8 rows in the same order. The output is the expected output above.

    **Why it works:** `to_date` drops the time; `date_format` with the pattern `EEE` gives the short day name;
    `dayofweek` numbers days from 1 (Sunday) to 7 (Saturday). March 1, 2026 is a Sunday.

    **Common mistakes:** assuming `dayofweek` starts on Monday; and forgetting that `order_ts` is in UTC, so "weekend" may differ in the
    customer's local time (Task 49).

## 25.4 Aggregation: totals, conditional counts, pivot

*Level: beginner.*

`groupBy(...).agg(...)` returns one row per group. The traps are about what you count (`count("*")` counts rows,
`count(col)` skips NULLs), where a condition goes (before the grouping or after it), and how `pivot`, `unpivot`
and `rollup` change the shape. The functions are listed in [19. The function toolbox](19-Function-Toolbox.md).

**Task 8. Per currency: number of orders, revenue, and average amount rounded to 2 decimals.**

Input: `orders`. Expected output:

```text
+--------+--------+-------+----------+
|currency|n_orders|revenue|avg_amount|
+--------+--------+-------+----------+
|CAD     |4       |645.40 |161.35    |
|USD     |4       |476.95 |119.24    |
+--------+--------+-------+----------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders
              .groupBy("currency")
              .agg(F.count("*").alias("n_orders"),
                   F.sum("amount").alias("revenue"),
                   F.round(F.avg("amount"), 2).alias("avg_amount"))
              .orderBy("currency"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT currency,
           count(*)              AS n_orders,
           sum(amount)           AS revenue,
           round(avg(amount), 2) AS avg_amount
    FROM orders
    GROUP BY currency
    ORDER BY currency;
    ```

    Both versions were run in `t02_agg.py`, which asserts that they return the same columns, column types and 2 rows in the same order. The output is the expected output above.

    **Why it works:** each aggregate gets an `alias`, otherwise the column is called `sum(amount)` and so on
    (Q6 in 25.13). `avg` of a decimal is a decimal with more scale, which `round` brings back to 2.

    **Common mistakes:** forgetting the aliases and then referring to `revenue` later; and `count("amount")`
    when you mean the number of orders: it skips rows where `amount` is NULL.

**Task 9. Customers who spent 200 or more in total: show their number of orders, total and largest order, the
biggest spender first.**

Input: `orders`. Expected output:

```text
+-----------+--------+------+-------+
|customer_id|n_orders|total |largest|
+-----------+--------+------+-------+
|1          |3       |327.40|189.50 |
|4          |1       |318.00|318.00 |
|2          |2       |278.95|249.00 |
+-----------+--------+------+-------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders
              .groupBy("customer_id")
              .agg(F.count("*").alias("n_orders"),
                   F.sum("amount").alias("total"),
                   F.max("amount").alias("largest"))
              .filter(F.col("total") >= 200)            # a filter after agg is SQL's HAVING
              .orderBy(F.col("total").desc()))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id,
           count(*)    AS n_orders,
           sum(amount) AS total,
           max(amount) AS largest
    FROM orders
    GROUP BY customer_id
    HAVING sum(amount) >= 200
    ORDER BY total DESC;
    ```

    Both versions were run in `t02_agg.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** a `filter` after `agg` works on the aggregated columns, which is what SQL's `HAVING` does.
    A `filter` before `groupBy` is SQL's `WHERE`: it removes rows before they are counted.

    **Common mistakes:** filtering `amount >= 200` before grouping, which finds big orders, not big customers;
    and in SQL, putting the aggregate condition in `WHERE`, which is an error because `WHERE` runs before the
    grouping.

**Task 10. Per customer, count orders by status (`SHIPPED`, `PLACED`, `CANCELLED`, no status) and sum the
amount of shipped orders, in one pass.**

Input: `orders`. Expected output:

```text
+-----------+-------+------+---------+---------+--------------+
|customer_id|shipped|placed|cancelled|no_status|shipped_amount|
+-----------+-------+------+---------+---------+--------------+
|1          |1      |1     |0        |1        |59.90         |
|2          |1      |1     |0        |0        |249.00        |
|3          |1      |0     |1        |0        |159.00        |
|4          |1      |0     |0        |0        |318.00        |
+-----------+-------+------+---------+---------+--------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders
              .groupBy("customer_id")
              .agg(F.count_if(F.col("status") == "SHIPPED").alias("shipped"),
                   F.count_if(F.col("status") == "PLACED").alias("placed"),
                   F.count_if(F.col("status") == "CANCELLED").alias("cancelled"),
                   F.count_if(F.col("status").isNull()).alias("no_status"),
                   F.sum(F.when(F.col("status") == "SHIPPED", F.col("amount"))
                          .otherwise(0)).alias("shipped_amount"))
              .orderBy("customer_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id,
           count_if(status = 'SHIPPED')                         AS shipped,
           count_if(status = 'PLACED')                          AS placed,
           count_if(status = 'CANCELLED')                       AS cancelled,
           count_if(status IS NULL)                             AS no_status,
           sum(CASE WHEN status = 'SHIPPED' THEN amount ELSE 0 END) AS shipped_amount
    FROM orders
    GROUP BY customer_id
    ORDER BY customer_id;
    ```

    Both versions were run in `t02_agg.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** `count_if(cond)` counts rows where the condition is true; `sum(when(cond, x).otherwise(0))`
    is the portable form that works in every SQL dialect. One `groupBy` computes all of them in one scan, instead
    of one query per status. Databricks SQL also accepts the standard `FILTER` clause:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    # The same counts with the FILTER clause (SQL only)
    spark.sql("""SELECT customer_id, count(*) FILTER (WHERE status = 'SHIPPED') AS shipped
                 FROM orders GROUP BY customer_id ORDER BY customer_id""").show()
    ```

    ```text
    +-----------+-------+
    |customer_id|shipped|
    +-----------+-------+
    |          1|      1|
    |          2|      1|
    |          3|      1|
    |          4|      1|
    +-----------+-------+
    ```

    **Common mistakes:** `count(F.when(cond, 1))` works too (NULLs are not counted), but
    `count(F.when(cond, 1).otherwise(0))` counts every row, because 0 is not NULL; and
    `count_if(status = 'SHIPPED')` does not count the NULL-status row as "not shipped" or as anything; it needs
    its own `IS NULL` test.

**Task 11. Per product category: the number of orders, the number of distinct customers and the units sold.**

Input: `order_items`, `products`, `orders`. Expected output:

```text
+--------+--------+-----------+-----+
|category|n_orders|n_customers|units|
+--------+--------+-----------+-----+
|Apparel |2       |2          |3    |
|Camping |2       |2          |2    |
|Hiking  |4       |3          |6    |
+--------+--------+-----------+-----+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    lines = (order_items
             .join(products, "product_id")
             .join(orders, "order_id"))
    result = (lines
              .groupBy("category")
              .agg(F.countDistinct("order_id").alias("n_orders"),
                   F.countDistinct("customer_id").alias("n_customers"),
                   F.sum("qty").alias("units"))
              .orderBy("category"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT p.category,
           count(DISTINCT oi.order_id)   AS n_orders,
           count(DISTINCT o.customer_id) AS n_customers,
           sum(oi.qty)                   AS units
    FROM order_items oi
    JOIN products p ON p.product_id = oi.product_id
    JOIN orders o   ON o.order_id = oi.order_id
    GROUP BY p.category
    ORDER BY p.category;
    ```

    Both versions were run in `t02_agg.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** after the joins there is one row per order line. `countDistinct("customer_id")` counts
    customer 1 once in Hiking although she has two Hiking orders. For very large data,
    `approx_count_distinct` trades a small error for much less memory
    ([19. The function toolbox](19-Function-Toolbox.md)).

    **Common mistakes:** `F.count("order_id")` instead of `countDistinct` gives the number of lines, which only
    equals the number of orders while every order has one line in the category; and joining `orders` to
    `order_items` and then summing `orders.amount`, which repeats the amount once per line.

**Task 12. Pivot: one row per order date, one column per category (`Apparel`, `Camping`, `Hiking`) holding the
revenue (`qty * unit_price`).**

Input: `order_items`, `products`, `orders`. Expected output:

```text
+----------+-------+-------+------+
|order_date|Apparel|Camping|Hiking|
+----------+-------+-------+------+
|2026-03-01|NULL   |249.00 |59.90 |
|2026-03-02|NULL   |189.50 |39.00 |
|2026-03-03|318.00 |NULL   |29.95 |
|2026-03-04|159.00 |NULL   |78.00 |
+----------+-------+-------+------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    lines = (order_items
             .join(products.select("product_id", "category"), "product_id")
             .join(orders.select("order_id", "order_ts"), "order_id")
             .select(F.to_date("order_ts").alias("order_date"), "category",
                     (F.col("qty") * F.col("unit_price")).alias("revenue")))
    result = (lines
              .groupBy("order_date")
              .pivot("category", ["Apparel", "Camping", "Hiking"])   # list the values: one pass less
              .agg(F.sum("revenue"))
              .orderBy("order_date"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT * FROM (
      SELECT to_date(o.order_ts) AS order_date, p.category, oi.qty * oi.unit_price AS revenue
      FROM order_items oi
      JOIN products p ON p.product_id = oi.product_id
      JOIN orders o   ON o.order_id = oi.order_id
    )
    PIVOT (sum(revenue) FOR category IN ('Apparel', 'Camping', 'Hiking'))
    ORDER BY order_date;
    ```

    Both versions were run in `t02_agg.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** `groupBy(rows).pivot(column, values).agg(value)` turns each distinct value of the pivot
    column into a column. Passing the list of values is faster: without it, Spark "will eagerly compute the
    distinct values in `pivot_col`" first
    ([GroupedData.pivot](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.GroupedData.pivot.html)).
    The SQL `PIVOT` clause always needs the list
    ([PIVOT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-pivot)).

    **Common mistakes:** expecting 0 where there were no sales; the cells are NULL, so add `.fillna(0)` if the
    report needs zeros; and in SQL, leaving extra columns in the subquery, which silently become extra grouping
    columns.

**Task 13. Unpivot: the targets table has one column per month. Turn it into one row per category and month,
keeping the missing target for Hiking in March.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
targets = spark.createDataFrame([
    ("Apparel", 500, 650, 700),
    ("Camping", 1200, 1100, 1500),
    ("Hiking",  300, 350, None),
], "category STRING, jan INT, feb INT, mar INT")
targets.createOrReplaceTempView("targets")
```

Expected output:

```text
+--------+-----+------+
|category|month|target|
+--------+-----+------+
|Apparel |feb  |650   |
|Apparel |jan  |500   |
|Apparel |mar  |700   |
|Camping |feb  |1100  |
|Camping |jan  |1200  |
|Camping |mar  |1500  |
|Hiking  |feb  |350   |
|Hiking  |jan  |300   |
|Hiking  |mar  |NULL  |
+--------+-----+------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (targets
              .unpivot("category", ["jan", "feb", "mar"], "month", "target")
              .orderBy("category", "month"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT category, month, target
    FROM targets
    UNPIVOT INCLUDE NULLS (target FOR month IN (jan, feb, mar))
    ORDER BY category, month;
    ```

    Both versions were run in `t02_agg.py`, which asserts that they return the same columns, column types and 9 rows in the same order. The output is the expected output above.

    **Why it works:** `DataFrame.unpivot(ids, values, variableColumnName, valueColumnName)` (alias `melt`) keeps
    the id columns and makes one row per value column
    ([DataFrame.unpivot](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.unpivot.html)).

    **Common mistakes:** the two APIs treat NULLs differently. SQL `UNPIVOT` defaults to `EXCLUDE NULLS`
    ([UNPIVOT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-unpivot)),
    while `DataFrame.unpivot` keeps them:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    default = spark.sql("SELECT * FROM targets UNPIVOT (target FOR month IN (jan, feb, mar))")
    print("SQL UNPIVOT default rows:", default.count(), "  DataFrame.unpivot rows:", result.count())
    ```

    ```text
    SQL UNPIVOT default rows: 8   DataFrame.unpivot rows: 9
    ```

    That is why the SQL above says `INCLUDE NULLS`. Note also that `month` sorts alphabetically (`feb`, `jan`,
    `mar`); add a month number if order matters.

**Task 14. Order count and revenue by country and city, with a subtotal per country and a grand total.**

Input: `orders`, `customers`. Expected output:

```text
+-------+---------+-----+--------+-------+
|country|city     |level|n_orders|revenue|
+-------+---------+-----+--------+-------+
|CA     |Calgary  |0    |3       |327.40 |
|CA     |Vancouver|0    |1       |318.00 |
|CA     |NULL     |1    |4       |645.40 |
|US     |Denver   |0    |2       |278.95 |
|US     |Moab     |0    |2       |198.00 |
|US     |NULL     |1    |4       |476.95 |
|NULL   |NULL     |3    |8       |1122.35|
+-------+---------+-----+--------+-------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders
              .join(customers, "customer_id")
              .rollup("country", "city")
              .agg(F.grouping_id().alias("level"),          # 0 = city, 1 = country total, 3 = grand total
                   F.count("*").alias("n_orders"),
                   F.sum("amount").alias("revenue"))
              .orderBy(F.col("country").asc_nulls_last(), F.col("city").asc_nulls_last()))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT c.country, c.city,
           grouping_id()  AS level,
           count(*)       AS n_orders,
           sum(o.amount)  AS revenue
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    GROUP BY ROLLUP (c.country, c.city)
    ORDER BY c.country ASC NULLS LAST, c.city ASC NULLS LAST;
    ```

    Both versions were run in `t02_agg.py`, which asserts that they return the same columns, column types and 7 rows in the same order. The output is the expected output above.

    **Why it works:** `rollup("country", "city")` computes the groupings (country, city), (country) and () in one
    pass. The rolled-up column is NULL in subtotal rows. `grouping_id()` is a bit mask of which columns were
    rolled up: 0 for a city row, 1 when `city` is rolled up, 3 when both are.

    **Common mistakes:** using `city IS NULL` to find subtotal rows; if the data has a real NULL city, you cannot
    tell the two apart, which is what `grouping_id()` (or `grouping("city")`) is for. `cube` would add the
    (city) grouping as well.

**Task 15. Each category's revenue and its share of total revenue in percent.**

Input: `order_items`, `products`. Expected output:

```text
+--------+-------+----+
|category|revenue|pct |
+--------+-------+----+
|Apparel |477.00 |42.5|
|Camping |438.50 |39.1|
|Hiking  |206.85 |18.4|
+--------+-------+----+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    by_cat = (order_items
              .join(products, "product_id")
              .groupBy("category")
              .agg(F.sum(F.col("qty") * F.col("unit_price")).alias("revenue")))
    result = (by_cat
              .withColumn("pct", F.round(100 * F.col("revenue") / F.sum("revenue").over(Window.partitionBy()), 1))
              .orderBy(F.col("revenue").desc()))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT p.category,
           sum(oi.qty * oi.unit_price) AS revenue,
           round(100 * sum(oi.qty * oi.unit_price) / sum(sum(oi.qty * oi.unit_price)) OVER (), 1) AS pct
    FROM order_items oi
    JOIN products p ON p.product_id = oi.product_id
    GROUP BY p.category
    ORDER BY revenue DESC;
    ```

    Both versions were run in `t02_agg.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** after the `groupBy` there are three rows; `F.sum("revenue").over(Window.partitionBy())`
    adds the grand total to each of them without another join. In SQL, `sum(sum(x)) OVER ()` is a window over
    the aggregated rows.

    **Common mistakes:** a window with no partition moves all rows to one partition; here that is three rows and
    harmless, but on a large table do it after the aggregation, as here, or join to a one-row total instead.

## 25.5 Joins

*Level: intermediate.*

Joins are where wrong answers look right: the code runs, the numbers are plausible, and they are wrong because
a key was duplicated, a NULL did not match, or a row without a partner vanished. Chapter 3 explains how Spark
executes joins (broadcast and sort-merge) ([3. Apache Spark](03-Apache-Spark.md)).

**Task 16. For each order line, show the order id, the customer's name, the product's name, the quantity and the
line total.**

Input: `order_items`, `orders`, `customers`, `products`. Expected output:

```text
+--------+------------+-----------------+---+----------+
|order_id|customer    |product          |qty|line_total|
+--------+------------+-----------------+---+----------+
|1001    |Ana Lopez   |Trekking Poles   |2  |59.90     |
|1002    |Ben Okafor  |Trail Tent 2P    |1  |249.00    |
|1003    |Ana Lopez   |Down Sleeping Bag|1  |189.50    |
|1004    |Chloe Martin|Headlamp         |1  |39.00     |
|1005    |Dev Patel   |Rain Shell       |2  |318.00    |
|1006    |Ben Okafor  |Trekking Poles   |1  |29.95     |
|1007    |Chloe Martin|Rain Shell       |1  |159.00    |
|1008    |Ana Lopez   |Headlamp         |2  |78.00     |
+--------+------------+-----------------+---+----------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (order_items.alias("oi")
              .join(orders.alias("o"), F.col("oi.order_id") == F.col("o.order_id"))
              .join(customers.alias("c"), F.col("o.customer_id") == F.col("c.customer_id"))
              .join(products.alias("p"), F.col("oi.product_id") == F.col("p.product_id"))
              .select(F.col("oi.order_id"),
                      F.col("c.name").alias("customer"),
                      F.col("p.name").alias("product"),
                      F.col("oi.qty"),
                      (F.col("oi.qty") * F.col("oi.unit_price")).alias("line_total"))
              .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT oi.order_id, c.name AS customer, p.name AS product, oi.qty,
           oi.qty * oi.unit_price AS line_total
    FROM order_items oi
    JOIN orders o    ON o.order_id = oi.order_id
    JOIN customers c ON c.customer_id = o.customer_id
    JOIN products p  ON p.product_id = oi.product_id
    ORDER BY oi.order_id;
    ```

    Both versions were run in `t03_joins.py`, which asserts that they return the same columns, column types and 8 rows in the same order. The output is the expected output above.

    **Why it works:** aliases (`.alias("oi")`) let you name each side, exactly like table aliases in SQL. Both
    `customers` and `products` have a `name` column, so the output renames them.

    **Common mistakes:** joining with `on="customer_id"` is shorter and keeps one key column, but with explicit
    conditions both key columns survive and an unqualified `select("order_id")` fails as ambiguous (Q5 in 25.13).

**Task 17. List every customer with the number of orders and the total spent, including a new customer with no
orders (0 orders, total 0).**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
new_customer = spark.createDataFrame(
    [(5, "Eve Tremblay", "eve@example.com", "Banff", "CA", dt(2026, 3, 2, 18, 0))],
    customers.schema)
customers5 = customers.unionByName(new_customer)
customers5.createOrReplaceTempView("customers5")
```

Expected output:

```text
+-----------+------------+--------+------+
|customer_id|name        |n_orders|total |
+-----------+------------+--------+------+
|1          |Ana Lopez   |3       |327.40|
|2          |Ben Okafor  |2       |278.95|
|3          |Chloe Martin|2       |198.00|
|4          |Dev Patel   |1       |318.00|
|5          |Eve Tremblay|0       |0.00  |
+-----------+------------+--------+------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (customers5
              .join(orders, "customer_id", "left")
              .groupBy("customer_id", "name")
              .agg(F.count("order_id").alias("n_orders"),                      # not count("*")
                   F.coalesce(F.sum("amount"), F.lit(0)).alias("total"))
              .orderBy("customer_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT c.customer_id, c.name,
           count(o.order_id)              AS n_orders,
           coalesce(sum(o.amount), 0)     AS total
    FROM customers5 c
    LEFT JOIN orders o ON o.customer_id = c.customer_id
    GROUP BY c.customer_id, c.name
    ORDER BY c.customer_id;
    ```

    Both versions were run in `t03_joins.py`, which asserts that they return the same columns, column types and 5 rows in the same order. The output is the expected output above.

    **Why it works:** the left join keeps Eve with NULLs in the order columns. `count("order_id")` skips NULLs,
    so she gets 0; `sum` of only NULLs is NULL, which `coalesce` turns into 0.

    **Common mistakes:** `count("*")` counts the row the left join produced, so Eve gets 1 order:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    wrong = (customers5.join(orders, "customer_id", "left")
             .groupBy("customer_id").agg(F.count("*").alias("n_orders")))
    wrong.filter("customer_id = 5").show()
    ```

    ```text
    +-----------+--------+
    |customer_id|n_orders|
    +-----------+--------+
    |          5|       1|
    +-----------+--------+
    ```

    Also, an inner join (the default `how`) drops Eve entirely.

**Task 18. Find the customers who have never ordered.**

Input: `customers5` from Task 17 and `orders`. Expected output:

```text
+-----------+------------+-----+
|customer_id|name        |city |
+-----------+------------+-----+
|5          |Eve Tremblay|Banff|
+-----------+------------+-----+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (customers5
              .join(orders, "customer_id", "left_anti")
              .select("customer_id", "name", "city")
              .orderBy("customer_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT c.customer_id, c.name, c.city
    FROM customers5 c
    WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id)
    ORDER BY c.customer_id;
    ```

    Both versions were run in `t03_joins.py`, which asserts that they return the same columns, column types and 1 rows in the same order. The output is the expected output above.

    **Why it works:** `left_anti` returns the rows of the left side that have no match on the right, and only the
    left side's columns. `NOT EXISTS` and `LEFT ANTI JOIN` are the SQL forms.

    **Common mistakes:** `NOT IN (subquery)` is the classic trap. If the subquery returns a single NULL,
    `x NOT IN (...)` is never true, so the query returns nothing:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    # The NOT IN trap: one NULL in the subquery makes NOT IN return no rows at all
    orders_with_null = orders.unionByName(spark.createDataFrame(
        [(1009, None, dt(2026, 3, 5, 9, 0), "PLACED", D("10.00"), "CAD")], orders.schema))
    orders_with_null.createOrReplaceTempView("orders_with_null")
    spark.sql("""SELECT customer_id FROM customers5
                 WHERE customer_id NOT IN (SELECT customer_id FROM orders_with_null)""").show()
    print("left_anti still finds:",
          [r.customer_id for r in customers5.join(orders_with_null, "customer_id", "left_anti").collect()])
    ```

    ```text
    +-----------+
    |customer_id|
    +-----------+
    +-----------+

    left_anti still finds: [5]
    ```

    `left_anti` and `NOT EXISTS` do not have this problem. Interviewers ask about it often.

!!! tip "In the interview"
    **"Find the rows in A that have no match in B."** In PySpark, `A.join(B, key, "left_anti")`; in SQL,
    `NOT EXISTS` or `LEFT ANTI JOIN`. Mention why not `NOT IN`: a single NULL in B's key makes it return nothing.
    If you also need B's unmatched rows, use a full outer join and test which side is NULL (Task 23).

**Task 19. Find the order lines whose product is not in the catalog (orphan rows).**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
new_items = spark.createDataFrame([(1009, 3, 1, D("29.95")), (1009, 9, 1, D("15.00")),
                                   (1010, 12, 3, D("4.50"))], order_items.schema)
items_all = order_items.unionByName(new_items)
items_all.createOrReplaceTempView("items_all")
```

Expected output:

```text
+--------+----------+---+
|order_id|product_id|qty|
+--------+----------+---+
|1009    |9         |1  |
|1010    |12        |3  |
+--------+----------+---+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (items_all
              .join(products, "product_id", "left_anti")
              .select("order_id", "product_id", "qty")
              .orderBy("order_id", "product_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT i.order_id, i.product_id, i.qty
    FROM items_all i
    LEFT ANTI JOIN products p ON p.product_id = i.product_id
    ORDER BY i.order_id, i.product_id;
    ```

    Both versions were run in `t03_joins.py`, which asserts that they return the same columns, column types and 2 rows in the same order. The output is the expected output above.

    **Why it works:** the same anti join, pointed the other way: lines without a parent. Run it as a data
    quality check before loading silver, because an inner join later would drop these lines and make revenue
    look smaller (Task 54 turns this into a report).

    **Common mistakes:** checking orphans with a left join and `filter(F.col("name").isNull())` works only if
    `name` can never be NULL in `products`; testing the join key itself (`products.product_id IS NULL`) is
    safer, and the anti join avoids the question.

**Task 20. List the customers who bought at least one Camping product, each customer once.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
items_more = order_items.unionByName(spark.createDataFrame(
    [(1003, 1, 1, D("249.00"))], order_items.schema))      # order 1003 also gets a tent
items_more.createOrReplaceTempView("items_more")
```

Expected output:

```text
+-----------+----------+
|customer_id|name      |
+-----------+----------+
|1          |Ana Lopez |
|2          |Ben Okafor|
+-----------+----------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    camping_buys = (items_more
                    .join(products.filter(F.col("category") == "Camping"), "product_id")
                    .join(orders, "order_id")
                    .select("customer_id"))
    result = (customers
              .join(camping_buys, "customer_id", "left_semi")
              .select("customer_id", "name")
              .orderBy("customer_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT c.customer_id, c.name
    FROM customers c
    WHERE EXISTS (
      SELECT 1
      FROM items_more i
      JOIN products p ON p.product_id = i.product_id
      JOIN orders o   ON o.order_id = i.order_id
      WHERE p.category = 'Camping' AND o.customer_id = c.customer_id)
    ORDER BY c.customer_id;
    ```

    Both versions were run in `t03_joins.py`, which asserts that they return the same columns, column types and 2 rows in the same order. The output is the expected output above.

    **Why it works:** `left_semi` keeps each left row that has at least one match and never repeats it, like
    `WHERE EXISTS`. Ana bought two Camping products (order 1003 has a tent and a sleeping bag in this input),
    yet she appears once.

    **Common mistakes:** an inner join followed by `select` repeats the customer once per match:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    inner = customers.join(camping_buys, "customer_id").select("customer_id", "name")
    print("inner join rows:", inner.count(), "  semi join rows:", result.count())
    ```

    ```text
    inner join rows: 3   semi join rows: 2
    ```

    `distinct()` after the inner join fixes the count but does more work and hides the intent.

**Task 21. Compute revenue per product. The price list has two rows for product 3 (a price change), and the
total must still equal the revenue in `order_items`.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
price_list = spark.createDataFrame([
    (3, "Trekking Poles", "Hiking",  D("29.95"), dt(2026, 1, 1)),
    (3, "Trekking Poles", "Hiking",  D("27.50"), dt(2026, 4, 1)),   # a price change: 2 rows for key 3
    (4, "Headlamp",       "Hiking",  D("39.00"), dt(2026, 1, 1)),
    (5, "Rain Shell",     "Apparel", D("159.00"), dt(2026, 1, 1)),
], "product_id INT, name STRING, category STRING, list_price DECIMAL(10,2), valid_from TIMESTAMP")
price_list.createOrReplaceTempView("price_list")
```

Expected output:

```text
+----------+--------------+-------+
|product_id|name          |revenue|
+----------+--------------+-------+
|3         |Trekking Poles|89.85  |
|4         |Headlamp      |117.00 |
|5         |Rain Shell    |477.00 |
+----------+--------------+-------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    latest = (price_list
              .withColumn("rn", F.row_number().over(
                  Window.partitionBy("product_id").orderBy(F.col("valid_from").desc())))
              .filter("rn = 1")
              .drop("rn"))
    result = (order_items
              .join(latest, "product_id")
              .groupBy("product_id", "name")
              .agg(F.sum(F.col("qty") * F.col("unit_price")).alias("revenue"))
              .orderBy("product_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    WITH latest AS (
      SELECT * FROM price_list
      QUALIFY row_number() OVER (PARTITION BY product_id ORDER BY valid_from DESC) = 1
    )
    SELECT oi.product_id, l.name, sum(oi.qty * oi.unit_price) AS revenue
    FROM order_items oi
    JOIN latest l ON l.product_id = oi.product_id
    GROUP BY oi.product_id, l.name
    ORDER BY oi.product_id;
    ```

    Both versions were run in `t03_joins.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** the join key must be unique on the side you look up. Keeping the latest row per
    `product_id` (or joining on the price valid at the order time) makes it unique, so each order line matches
    once.

    **Common mistakes:** joining straight to the price list doubles product 3's revenue, and nothing fails:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    naive = (order_items.join(price_list, "product_id")
             .groupBy("product_id").agg(F.sum(F.col("qty") * F.col("unit_price")).alias("revenue"))
             .orderBy("product_id"))
    naive.show()
    dupes = price_list.groupBy("product_id").count().filter("count > 1")
    dupes.show()
    ```

    ```text
    +----------+-------+
    |product_id|revenue|
    +----------+-------+
    |         3| 179.70|
    |         4| 117.00|
    |         5| 477.00|
    +----------+-------+

    +----------+-----+
    |product_id|count|
    +----------+-----+
    |         3|    2|
    +----------+-----+
    ```

    Check uniqueness before a join (`groupBy(key).count().filter("count > 1")`). "Revenue doubled after a
    release" is a standard scenario question, and this is the usual cause.

**Task 22. Revenue per category, joining `order_items` to the small `products` table with a broadcast join.**

Input: `order_items`, `products`. Expected output:

```text
+--------+-------+
|category|revenue|
+--------+-------+
|Apparel |477.00 |
|Camping |438.50 |
|Hiking  |206.85 |
+--------+-------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (order_items
              .join(F.broadcast(products), "product_id")
              .groupBy("category")
              .agg(F.sum(F.col("qty") * F.col("unit_price")).alias("revenue"))
              .orderBy("category"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT /*+ BROADCAST(p) */ p.category, sum(oi.qty * oi.unit_price) AS revenue
    FROM order_items oi
    JOIN products p ON p.product_id = oi.product_id
    GROUP BY p.category
    ORDER BY p.category;
    ```

    Both versions were run in `t03_joins.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** `F.broadcast(df)` (SQL hint `/*+ BROADCAST(p) */`) asks Spark to copy the small table to
    every executor, so the large side is joined where it sits, without a shuffle. To see the hint at work, the
    script turned off automatic broadcasting and printed the join operator chosen:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")      # turn automatic broadcast off
    def join_nodes(df):
        plan = df._jdf.queryExecution().executedPlan().toString()
        return sorted({w for w in ["BroadcastHashJoin", "SortMergeJoin", "ShuffledHashJoin"] if w in plan})
    plain = order_items.join(products, "product_id")
    hinted = order_items.join(F.broadcast(products), "product_id")
    print("no hint:  ", join_nodes(plain))
    print("with hint:", join_nodes(hinted))
    spark.conf.unset("spark.sql.autoBroadcastJoinThreshold")
    print("threshold default:", spark.conf.get("spark.sql.autoBroadcastJoinThreshold"))
    ```

    ```text
    no hint:   ['SortMergeJoin']
    with hint: ['BroadcastHashJoin']
    threshold default: 10485760b
    ```

    Spark broadcasts on its own when it estimates a table below `spark.sql.autoBroadcastJoinThreshold`, which
    defaults to 10485760 bytes (10 MB); the `BROADCAST` hint is honored "even if the size of table ... suggested
    by the statistics is above" that setting
    ([Performance Tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html)).

    **Common mistakes:** broadcasting a table that is not small: the whole table is sent to every executor and
    must fit in memory there. Chapter 22 covers join strategies in depth
    ([22. Performance tuning](22-Performance-Tuning.md)).

**Task 23. Reconcile orders with payments: list the orders without a payment, the payments without an order, and
the orders paid with a different amount. Cancelled orders need no payment; order 1008 (no status) does.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
payments = spark.createDataFrame([
    (1001, D("59.90")), (1002, D("249.00")), (1003, D("180.00")),   # 1003 underpaid
    (1005, D("318.00")), (1007, D("159.00")), (1099, D("42.00")),   # 1099: no such order
], "order_id INT, paid DECIMAL(10,2)")
payments.createOrReplaceTempView("payments")
```

Expected output:

```text
+--------+------+------+---------------------+
|order_id|amount|paid  |issue                |
+--------+------+------+---------------------+
|1003    |189.50|180.00|amount mismatch      |
|1006    |29.95 |NULL  |missing payment      |
|1008    |78.00 |NULL  |missing payment      |
|1099    |NULL  |42.00 |payment without order|
+--------+------+------+---------------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    o = orders.filter(~F.col("status").eqNullSafe("CANCELLED")).select("order_id", "amount")
    result = (o.join(payments, "order_id", "full")         # USING-style join: one order_id column
              .withColumn("issue", F.when(F.col("paid").isNull(), "missing payment")
                                    .when(F.col("amount").isNull(), "payment without order")
                                    .when(F.col("amount") != F.col("paid"), "amount mismatch"))
              .filter(F.col("issue").isNotNull())
              .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT * FROM (
      SELECT order_id, o.amount, p.paid,
             CASE WHEN p.paid IS NULL     THEN 'missing payment'
                  WHEN o.amount IS NULL   THEN 'payment without order'
                  WHEN o.amount <> p.paid THEN 'amount mismatch' END AS issue
      FROM (SELECT order_id, amount FROM orders WHERE status IS DISTINCT FROM 'CANCELLED') o
      FULL OUTER JOIN payments p USING (order_id)
    )
    WHERE issue IS NOT NULL
    ORDER BY order_id;
    ```

    Both versions were run in `t03_joins.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** a full outer join keeps unmatched rows from both sides, which is exactly what a
    reconciliation needs. Joining on the column name (`"order_id"` in PySpark, `USING (order_id)` in SQL) merges
    the two keys into one non-NULL `order_id` column. The `when` chain classifies each row, and rows that match
    no branch (NULL `issue`) are the good ones.

    **Common mistakes:** filtering with `status != 'CANCELLED'`, which also removes order 1008 and hides a missing
    payment (Task 6 again); joining on `o.order_id == p.order_id` and then selecting `o.order_id`, which is NULL
    for payment-only rows (use `coalesce` of both keys); and comparing amounts with `!=` before handling NULLs.

**Task 24. List the pairs of customers who live in the same country, each pair once.**

Input: `customers`. Expected output:

```text
+-------+----------+------------+
|country|customer_a|customer_b  |
+-------+----------+------------+
|CA     |Ana Lopez |Dev Patel   |
|US     |Ben Okafor|Chloe Martin|
+-------+----------+------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    c1, c2 = customers.alias("c1"), customers.alias("c2")
    result = (c1.join(c2, (F.col("c1.country") == F.col("c2.country"))
                          & (F.col("c1.customer_id") < F.col("c2.customer_id")))
              .select(F.col("c1.country"),
                      F.col("c1.name").alias("customer_a"),
                      F.col("c2.name").alias("customer_b"))
              .orderBy("country"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT c1.country, c1.name AS customer_a, c2.name AS customer_b
    FROM customers c1
    JOIN customers c2
      ON c1.country = c2.country AND c1.customer_id < c2.customer_id
    ORDER BY c1.country;
    ```

    Both versions were run in `t03_joins.py`, which asserts that they return the same columns, column types and 2 rows in the same order. The output is the expected output above.

    **Why it works:** a self join needs two aliases. `c1.customer_id < c2.customer_id` removes the pairs of a
    customer with itself and keeps only one of (A, B) and (B, A).

    **Common mistakes:** using `!=` instead of `<` (each pair twice), or forgetting the inequality (each customer
    paired with itself); and joining `customers` to itself without aliases, which makes every column reference
    ambiguous ([DataFrame.join](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.join.html)
    shows the same problem for self joins).

**Task 25. Tag each order with the promotion that was running at the order time, or NULL if none.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
promos = spark.createDataFrame([
    ("SPRING10", dt(2026, 3, 1), dt(2026, 3, 2, 23, 59, 59)),
    ("GEARUP",   dt(2026, 3, 4), dt(2026, 3, 4, 12, 0)),
], "promo STRING, starts TIMESTAMP, ends TIMESTAMP")
promos.createOrReplaceTempView("promos")
```

Expected output:

```text
+--------+-------------------+--------+
|order_id|order_ts           |promo   |
+--------+-------------------+--------+
|1001    |2026-03-01 10:15:00|SPRING10|
|1002    |2026-03-01 11:05:00|SPRING10|
|1003    |2026-03-02 09:40:00|SPRING10|
|1004    |2026-03-02 14:20:00|SPRING10|
|1005    |2026-03-03 08:55:00|NULL    |
|1006    |2026-03-03 17:30:00|NULL    |
|1007    |2026-03-04 12:00:00|GEARUP  |
|1008    |2026-03-04 19:10:00|NULL    |
+--------+-------------------+--------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders
              .join(promos, F.col("order_ts").between(F.col("starts"), F.col("ends")), "left")
              .select("order_id", "order_ts", "promo")
              .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT o.order_id, o.order_ts, p.promo
    FROM orders o
    LEFT JOIN promos p ON o.order_ts BETWEEN p.starts AND p.ends
    ORDER BY o.order_id;
    ```

    Both versions were run in `t03_joins.py`, which asserts that they return the same columns, column types and 8 rows in the same order. The output is the expected output above.

    **Why it works:** a join condition can be any boolean expression, here a range (`between` includes both
    ends). The left join keeps orders outside every promotion.

    **Common mistakes:** without an equality in the condition, Spark cannot use a hash or sort-merge join and
    falls back to a nested loop:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    plan = result._jdf.queryExecution().executedPlan().toString()
    print([w for w in ["BroadcastNestedLoopJoin", "CartesianProduct", "BroadcastHashJoin", "SortMergeJoin"]
           if w in plan])
    ```

    ```text
    ['BroadcastNestedLoopJoin']
    ```

    That is fine with a small promotions table that is broadcast, and very slow if both sides are large. If
    promotions could overlap, an order would match twice; say how you would pick one (for example the latest
    start, with a window as in 25.6).

## 25.6 Window functions

*Level: intermediate.*

A window function computes a value for each row from a group of related rows (the partition), without collapsing
them the way `groupBy` does. In PySpark you describe the window once with
`Window.partitionBy(...).orderBy(...)` and apply functions with `.over(w)`. The ranking functions, frames and the
`QUALIFY` clause are explained in [19. The function toolbox](19-Function-Toolbox.md) and, for generic SQL, in the
SQL course ([Window functions and ranking](../../databases/sql/13-Window-Functions-Ranking.md)). PySpark has no
`QUALIFY`: you add the window column, then `filter` on it.

**Task 26. For each customer, return their two largest orders, with a rank column.**

Input: `orders`. Expected output:

```text
+-----------+--------+------+---+
|customer_id|order_id|amount|rn |
+-----------+--------+------+---+
|1          |1003    |189.50|1  |
|1          |1008    |78.00 |2  |
|2          |1002    |249.00|1  |
|2          |1006    |29.95 |2  |
|3          |1007    |159.00|1  |
|3          |1004    |39.00 |2  |
|4          |1005    |318.00|1  |
+-----------+--------+------+---+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    w = Window.partitionBy("customer_id").orderBy(F.col("amount").desc(), F.col("order_id"))
    result = (orders
              .withColumn("rn", F.row_number().over(w))
              .filter(F.col("rn") <= 2)
              .select("customer_id", "order_id", "amount", "rn")
              .orderBy("customer_id", "rn"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id, order_id, amount,
           row_number() OVER (PARTITION BY customer_id ORDER BY amount DESC, order_id) AS rn
    FROM orders
    QUALIFY rn <= 2
    ORDER BY customer_id, rn;
    ```

    Both versions were run in `t04_windows.py`, which asserts that they return the same columns, column types and 7 rows in the same order. The output is the expected output above.

    **Why it works:** `row_number` numbers the rows 1, 2, 3 within each customer in the window's order; keeping
    `rn <= 2` gives the top two. Adding `order_id` to the ordering makes it complete, so the result is the same
    on every run even if two orders have the same amount.

    **Common mistakes:** `groupBy("customer_id").agg(max("amount"))` gives the top one only and loses the other
    columns; ordering ascending by mistake; and using `rank` when the task says "exactly two" (with ties `rank`
    can return more rows, see the next task).

!!! tip "In the interview"
    **"Top N per group in PySpark?"** Add `row_number()` (or `rank`/`dense_rank`, depending on how ties should
    count) over `Window.partitionBy(group).orderBy(metric desc, tie_breaker)`, filter `<= N`, drop the helper
    column. PySpark has no `QUALIFY`; in Databricks SQL, `QUALIFY row_number() OVER (...) <= N` does it in one
    clause. Say which tie rule you chose and why.

**Task 27. Rank all products by units sold, showing `row_number`, `rank` and `dense_rank` side by side.**

Input: `order_items`, `products`. Expected output:

```text
+----------+-----------------+-----+----------+----+----------+
|product_id|name             |units|row_number|rank|dense_rank|
+----------+-----------------+-----+----------+----+----------+
|3         |Trekking Poles   |3    |1         |1   |1         |
|4         |Headlamp         |3    |2         |1   |1         |
|5         |Rain Shell       |3    |3         |1   |1         |
|1         |Trail Tent 2P    |1    |4         |4   |2         |
|2         |Down Sleeping Bag|1    |5         |4   |2         |
+----------+-----------------+-----+----------+----+----------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    units = (order_items
             .join(products, "product_id")
             .groupBy("product_id", "name")
             .agg(F.sum("qty").alias("units")))
    w = Window.orderBy(F.col("units").desc())      # no partitionBy: one ranking over all products
    result = (units
              .withColumns({
                  "row_number": F.row_number().over(Window.orderBy(F.col("units").desc(), "product_id")),
                  "rank": F.rank().over(w),
                  "dense_rank": F.dense_rank().over(w)})
              .orderBy("row_number"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    WITH units AS (
      SELECT p.product_id, p.name, sum(oi.qty) AS units
      FROM order_items oi JOIN products p ON p.product_id = oi.product_id
      GROUP BY p.product_id, p.name
    )
    SELECT *,
           row_number() OVER (ORDER BY units DESC, product_id) AS row_number,
           rank()       OVER (ORDER BY units DESC)             AS rank,
           dense_rank() OVER (ORDER BY units DESC)             AS dense_rank
    FROM units
    ORDER BY row_number;
    ```

    Both versions were run in `t04_windows.py`, which asserts that they return the same columns, column types and 5 rows in the same order. The output is the expected output above.

    **Why it works:** three products tie at 3 units and two at 1. `row_number` always gives 1, 2, 3, ... (ties
    broken here by `product_id`); `rank` gives ties the same number and then skips (1, 1, 1, 4, 4); `dense_rank`
    does not skip (1, 1, 1, 2, 2).

    **Common mistakes:** "top 3 products" is ambiguous with ties: `row_number <= 3` returns exactly three,
    `rank <= 3` returns every product tied for the top places, `dense_rank <= 3` returns the top three distinct
    values. Ask which one is wanted. Also, `row_number` without a tie-breaker picks among tied rows in no defined
    order, so it can change between runs.

**Task 28. A running total of spend per customer, in order time.**

Input: `orders`. Expected output:

```text
+-----------+--------+-------------------+------+-------------+
|customer_id|order_id|order_ts           |amount|running_total|
+-----------+--------+-------------------+------+-------------+
|1          |1001    |2026-03-01 10:15:00|59.90 |59.90        |
|1          |1003    |2026-03-02 09:40:00|189.50|249.40       |
|1          |1008    |2026-03-04 19:10:00|78.00 |327.40       |
|2          |1002    |2026-03-01 11:05:00|249.00|249.00       |
|2          |1006    |2026-03-03 17:30:00|29.95 |278.95       |
|3          |1004    |2026-03-02 14:20:00|39.00 |39.00        |
|3          |1007    |2026-03-04 12:00:00|159.00|198.00       |
|4          |1005    |2026-03-03 08:55:00|318.00|318.00       |
+-----------+--------+-------------------+------+-------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    w = (Window.partitionBy("customer_id").orderBy("order_ts")
         .rowsBetween(Window.unboundedPreceding, Window.currentRow))
    result = (orders
              .withColumn("running_total", F.sum("amount").over(w))
              .select("customer_id", "order_id", "order_ts", "amount", "running_total")
              .orderBy("customer_id", "order_ts"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id, order_id, order_ts, amount,
           sum(amount) OVER (PARTITION BY customer_id ORDER BY order_ts
                             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
    FROM orders
    ORDER BY customer_id, order_ts;
    ```

    Both versions were run in `t04_windows.py`, which asserts that they return the same columns, column types and 8 rows in the same order. The output is the expected output above.

    **Why it works:** with `rowsBetween(unboundedPreceding, currentRow)` the frame is every row from the start of
    the partition up to the current row, so the sum runs.

    **Common mistakes:** relying on the default frame. When the window has an `orderBy` and no frame, Spark uses
    `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, so rows with the same ordering value are summed together
    ([Window](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.Window.html)).
    The script shows it on two rows that share `t = 2`:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    # Default frame with ORDER BY is RANGE ... CURRENT ROW: rows with the same order value share a total
    same_time = spark.createDataFrame([(1, 1, 10), (1, 2, 20), (1, 2, 5)], "c INT, t INT, x INT")
    wd = Window.partitionBy("c").orderBy("t")
    same_time.select("t", "x",
                     F.sum("x").over(wd).alias("default_frame"),
                     F.sum("x").over(wd.rowsBetween(Window.unboundedPreceding, Window.currentRow))
                      .alias("rows_frame")).orderBy("t", "x").show()
    ```

    ```text
    +---+---+-------------+----------+
    |  t|  x|default_frame|rows_frame|
    +---+---+-------------+----------+
    |  1| 10|           10|        10|
    |  2|  5|           35|        35|
    |  2| 20|           35|        30|
    +---+---+-------------+----------+
    ```

    The default frame gives both tied rows 35. The `ROWS` frame gives 30 and 35, and which tied row gets which
    depends on their order, which is arbitrary; add a tie-breaker column to the `orderBy` to make it stable.

**Task 29. For each order, show the previous order's amount for the same customer, the change, and the id of the
customer's next order.**

Input: `orders`. Expected output:

```text
+-----------+--------+------+-----------+-------+-------------+
|customer_id|order_id|amount|prev_amount|change |next_order_id|
+-----------+--------+------+-----------+-------+-------------+
|1          |1001    |59.90 |NULL       |NULL   |1003         |
|1          |1003    |189.50|59.90      |129.60 |1008         |
|1          |1008    |78.00 |189.50     |-111.50|NULL         |
|2          |1002    |249.00|NULL       |NULL   |1006         |
|2          |1006    |29.95 |249.00     |-219.05|NULL         |
|3          |1004    |39.00 |NULL       |NULL   |1007         |
|3          |1007    |159.00|39.00      |120.00 |NULL         |
|4          |1005    |318.00|NULL       |NULL   |NULL         |
+-----------+--------+------+-----------+-------+-------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    w = Window.partitionBy("customer_id").orderBy("order_ts")
    result = (orders
              .withColumn("prev_amount", F.lag("amount").over(w))
              .withColumn("change", F.col("amount") - F.col("prev_amount"))
              .withColumn("next_order_id", F.lead("order_id").over(w))
              .select("customer_id", "order_id", "amount", "prev_amount", "change", "next_order_id")
              .orderBy("customer_id", "order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id, order_id, amount,
           lag(amount)   OVER w          AS prev_amount,
           amount - lag(amount) OVER w   AS change,
           lead(order_id) OVER w         AS next_order_id
    FROM orders
    WINDOW w AS (PARTITION BY customer_id ORDER BY order_ts)
    ORDER BY customer_id, order_id;
    ```

    Both versions were run in `t04_windows.py`, which asserts that they return the same columns, column types and 8 rows in the same order. The output is the expected output above.

    **Why it works:** `lag(col)` reads the value one row back in the window order and `lead(col)` one row
    ahead; at the edges they return NULL (or a default you pass as the third argument). The SQL `WINDOW w AS (...)`
    clause names the window once.

    **Common mistakes:** a window without `partitionBy` would compare Ana's order with Ben's; and `lag` with no
    `orderBy` is an error in Spark, because "previous" has no meaning without an order.

**Task 30. Return each customer's first order (id, time and amount).**

Input: `orders`. Expected output:

```text
+-----------+--------+-------------------+------+
|customer_id|order_id|order_ts           |amount|
+-----------+--------+-------------------+------+
|1          |1001    |2026-03-01 10:15:00|59.90 |
|2          |1002    |2026-03-01 11:05:00|249.00|
|3          |1004    |2026-03-02 14:20:00|39.00 |
|4          |1005    |2026-03-03 08:55:00|318.00|
+-----------+--------+-------------------+------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    w = Window.partitionBy("customer_id").orderBy("order_ts", "order_id")
    result = (orders
              .withColumn("rn", F.row_number().over(w))
              .filter("rn = 1")
              .select("customer_id", "order_id", "order_ts", "amount")
              .orderBy("customer_id"))

    # Same answer without a window: min_by picks the value at the smallest order_ts
    alt_min_by = (orders.groupBy("customer_id")
                  .agg(F.min_by("order_id", "order_ts").alias("order_id"),
                       F.min("order_ts").alias("order_ts"),
                       F.min_by("amount", "order_ts").alias("amount"))
                  .orderBy("customer_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id, order_id, order_ts, amount
    FROM orders
    QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY order_ts, order_id) = 1
    ORDER BY customer_id;
    ```

    Both versions were run in `t04_windows.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    The solution also shows a version without a window: `min_by(x, ord)` returns the value of `x` on the row
    with the smallest `ord`. The script checked that it returns the same rows as the `row_number` version.

    **Why it works:** `row_number() = 1` in time order is the first order. `min_by` does it in a `groupBy`, which
    is shorter when you need only a few columns.

    **Common mistakes:** `groupBy("customer_id").agg(F.min("order_ts"), F.min("order_id"), F.min("amount"))`
    takes each minimum independently, so the amount may come from a different order than the time. That is the
    bug interviewers hope to see you avoid.

**Task 31. Daily revenue has no row for March 3. Compute a 3-row moving average and a 3-calendar-day moving
average and explain the difference.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
daily = spark.createDataFrame([
    (dt(2026, 3, 1).date(), D("308.90")), (dt(2026, 3, 2).date(), D("228.50")),
    (dt(2026, 3, 4).date(), D("237.00")), (dt(2026, 3, 5).date(), D("120.00")),
], "day DATE, revenue DECIMAL(10,2)")                 # no orders on March 3
daily.createOrReplaceTempView("daily")
```

Expected output:

```text
+----------+-------+---------+---------+
|day       |revenue|ma_3_rows|ma_3_days|
+----------+-------+---------+---------+
|2026-03-01|308.90 |308.90   |308.90   |
|2026-03-02|228.50 |268.70   |268.70   |
|2026-03-04|237.00 |258.13   |232.75   |
|2026-03-05|120.00 |195.17   |178.50   |
+----------+-------+---------+---------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    by_rows = Window.orderBy("day").rowsBetween(-2, Window.currentRow)
    by_days = Window.orderBy(F.unix_date("day")).rangeBetween(-2, Window.currentRow)
    result = (daily
              .withColumn("ma_3_rows", F.round(F.avg("revenue").over(by_rows), 2))
              .withColumn("ma_3_days", F.round(F.avg("revenue").over(by_days), 2))
              .orderBy("day"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT day, revenue,
           round(avg(revenue) OVER (ORDER BY day ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2)
             AS ma_3_rows,
           round(avg(revenue) OVER (ORDER BY unix_date(day) RANGE BETWEEN 2 PRECEDING AND CURRENT ROW), 2)
             AS ma_3_days
    FROM daily
    ORDER BY day;
    ```

    Both versions were run in `t04_windows.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** `rowsBetween(-2, 0)` takes the current row and the two rows before it, whatever their
    dates. `rangeBetween(-2, 0)` takes the rows whose ordering value is within 2 of the current one, so it needs
    a number: `unix_date(day)` is the number of days since 1970-01-01. On March 4 the row frame averages
    March 1, 2 and 4 (258.13); the day frame averages March 2 and 4 only (232.75), because March 3 has no row.

    **Common mistakes:** using a row frame when the business means calendar days, which is wrong whenever a day is
    missing; or filling missing days with 0 first (Task 46) without deciding whether a day without sales should
    pull the average down.

**Task 32. Show each order's share of its customer's total spend, in percent.**

Input: `orders`. Expected output:

```text
+-----------+--------+------+--------------+-----+
|customer_id|order_id|amount|customer_total|pct  |
+-----------+--------+------+--------------+-----+
|1          |1001    |59.90 |327.40        |18.3 |
|1          |1003    |189.50|327.40        |57.9 |
|1          |1008    |78.00 |327.40        |23.8 |
|2          |1002    |249.00|278.95        |89.3 |
|2          |1006    |29.95 |278.95        |10.7 |
|3          |1004    |39.00 |198.00        |19.7 |
|3          |1007    |159.00|198.00        |80.3 |
|4          |1005    |318.00|318.00        |100.0|
+-----------+--------+------+--------------+-----+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    by_customer = Window.partitionBy("customer_id")            # no orderBy: the frame is the whole group
    result = (orders
              .withColumn("customer_total", F.sum("amount").over(by_customer))
              .withColumn("pct", F.round(100 * F.col("amount") / F.col("customer_total"), 1))
              .select("customer_id", "order_id", "amount", "customer_total", "pct")
              .orderBy("customer_id", "order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id, order_id, amount,
           sum(amount) OVER (PARTITION BY customer_id)                          AS customer_total,
           round(100 * amount / sum(amount) OVER (PARTITION BY customer_id), 1) AS pct
    FROM orders
    ORDER BY customer_id, order_id;
    ```

    Both versions were run in `t04_windows.py`, which asserts that they return the same columns, column types and 8 rows in the same order. The output is the expected output above.

    **Why it works:** a window with `partitionBy` and no `orderBy` covers the whole partition, so
    `sum(...).over(by_customer)` is the customer total on every row.

    **Common mistakes:** adding `.orderBy("order_ts")` to that window "for neatness": the default frame then
    becomes a running total and the percentages are wrong (Task 28).

**Task 33. Return each customer's second-largest order. Customers with only one order do not appear.**

Input: `orders`. Expected output:

```text
+-----------+--------+------+
|customer_id|order_id|amount|
+-----------+--------+------+
|1          |1008    |78.00 |
|2          |1006    |29.95 |
|3          |1004    |39.00 |
+-----------+--------+------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    w = Window.partitionBy("customer_id").orderBy(F.col("amount").desc())
    result = (orders
              .withColumn("dr", F.dense_rank().over(w))
              .filter("dr = 2")
              .select("customer_id", "order_id", "amount")
              .orderBy("customer_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id, order_id, amount
    FROM orders
    QUALIFY dense_rank() OVER (PARTITION BY customer_id ORDER BY amount DESC) = 2
    ORDER BY customer_id;
    ```

    Both versions were run in `t04_windows.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** `dense_rank` gives the largest amount 1 and the next distinct amount 2. Dev (customer 4) has
    one order, so he has no row with rank 2.

    **Common mistakes:** `row_number` returns the second row even if it has the same amount as the first, which
    is not the "second-largest amount"; ask which meaning is wanted. If two orders tie for second place,
    `dense_rank = 2` returns both.

## 25.7 Deduplication

*Level: intermediate.*

There are two kinds of duplicates, and interviewers check that you know which one you have. **Exact duplicates**
are identical in every column, typically the same message delivered twice. **Key duplicates** share a business
key (here `order_id`) but differ in other columns: several status updates of one order, or the same event from two
files. Chapter 9 covers both in a silver pipeline ([9. Building silver](09-Building-Silver.md)); the SQL course
has the generic patterns ([Duplicates and incremental loads](../../databases/sql/22-Duplicates-and-Incremental-Loads.md)).

The four tasks share this input, a stream of order status events as they arrived in bronze:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
events = spark.createDataFrame([
    (1001, "PLACED",    dt(2026, 3, 1, 10, 15), "orders_0301.json"),
    (1001, "PLACED",    dt(2026, 3, 1, 10, 15), "orders_0301.json"),   # delivered twice: exact copy
    (1001, "SHIPPED",   dt(2026, 3, 2, 8, 0),   "orders_0302.json"),
    (1002, "PLACED",    dt(2026, 3, 1, 11, 5),  "orders_0301.json"),
    (1002, "PLACED",    dt(2026, 3, 1, 11, 5),  "orders_0302.json"),   # same event, another file
    (1003, "PLACED",    dt(2026, 3, 2, 9, 40),  "orders_0302.json"),
    (1003, "CANCELLED", dt(2026, 3, 2, 9, 40),  "orders_0302.json"),   # same timestamp as PLACED
], "order_id INT, status STRING, updated_at TIMESTAMP, source_file STRING")
events.createOrReplaceTempView("events")
```

**Task 34. Remove the exact duplicate rows.**

Expected output:

```text
+--------+---------+-------------------+----------------+
|order_id|status   |updated_at         |source_file     |
+--------+---------+-------------------+----------------+
|1001    |PLACED   |2026-03-01 10:15:00|orders_0301.json|
|1001    |SHIPPED  |2026-03-02 08:00:00|orders_0302.json|
|1002    |PLACED   |2026-03-01 11:05:00|orders_0301.json|
|1002    |PLACED   |2026-03-01 11:05:00|orders_0302.json|
|1003    |PLACED   |2026-03-02 09:40:00|orders_0302.json|
|1003    |CANCELLED|2026-03-02 09:40:00|orders_0302.json|
+--------+---------+-------------------+----------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = events.dropDuplicates()           # same as events.distinct()
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT DISTINCT * FROM events;
    ```

    Both versions were run in `t05_dedup.py`, which asserts that they return the same columns, column types and 6 rows. The output is the expected output above.

    **Why it works:** `dropDuplicates()` with no columns (or `distinct()`) compares all columns. Only the first
    1001 `PLACED` row had an identical copy:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    print("before:", events.count(), " after:", result.count())
    ```

    ```text
    before: 7  after: 6
    ```

    **Common mistakes:** stopping here. Order 1002's two `PLACED` rows differ only in `source_file`, so they are
    not exact duplicates, and order 1001 still has two statuses.

**Task 35. For each order with more than one row, report how many rows it has, how many distinct rows, and how
many distinct events (status and time, ignoring the file).**

Expected output:

```text
+--------+------+---------------+-----------------+
|order_id|n_rows|n_distinct_rows|n_distinct_events|
+--------+------+---------------+-----------------+
|1001    |3     |2              |2                |
|1002    |2     |2              |1                |
|1003    |2     |2              |2                |
+--------+------+---------------+-----------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (events
              .groupBy("order_id")
              .agg(F.count("*").alias("n_rows"),
                   F.countDistinct("status", "updated_at", "source_file").alias("n_distinct_rows"),
                   F.countDistinct("status", "updated_at").alias("n_distinct_events"))
              .filter(F.col("n_rows") > 1)
              .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id,
           count(*)                                           AS n_rows,
           count(DISTINCT status, updated_at, source_file)    AS n_distinct_rows,
           count(DISTINCT status, updated_at)                 AS n_distinct_events
    FROM events
    GROUP BY order_id
    HAVING count(*) > 1
    ORDER BY order_id;
    ```

    Both versions were run in `t05_dedup.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** comparing the counts tells you what kind of duplicates you have. For 1001, three rows but
    two distinct rows: one exact copy. For 1002, two distinct rows but one distinct event: the same event from two
    files. For 1003, two real events at the same time: not a duplicate at all, but a tie you must resolve.

    **Common mistakes:** `countDistinct` with several columns skips rows where any of them is NULL; if the columns
    can be NULL, count distinct `struct(...)` values instead or fill the NULLs first.

**Task 36. Keep the latest status of each order. When two events have the same time, `CANCELLED` beats
`SHIPPED`, which beats `PLACED`.**

Expected output:

```text
+--------+---------+-------------------+
|order_id|status   |updated_at         |
+--------+---------+-------------------+
|1001    |SHIPPED  |2026-03-02 08:00:00|
|1002    |PLACED   |2026-03-01 11:05:00|
|1003    |CANCELLED|2026-03-02 09:40:00|
+--------+---------+-------------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    priority = (F.when(F.col("status") == "CANCELLED", 3)
                 .when(F.col("status") == "SHIPPED", 2)
                 .when(F.col("status") == "PLACED", 1)
                 .otherwise(0))
    w = Window.partitionBy("order_id").orderBy(F.col("updated_at").desc(), priority.desc())
    result = (events
              .withColumn("rn", F.row_number().over(w))
              .filter("rn = 1")
              .select("order_id", "status", "updated_at")
              .orderBy("order_id"))

    # Same answer with an aggregate: max_by returns the row (as a struct) with the largest ordering key
    alt_max_by = (events
                  .groupBy("order_id")
                  .agg(F.max_by(F.struct("status", "updated_at"),
                                F.struct("updated_at", priority)).alias("latest"))
                  .select("order_id", "latest.*")
                  .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, status, updated_at
    FROM events
    QUALIFY row_number() OVER (
      PARTITION BY order_id
      ORDER BY updated_at DESC,
               CASE status WHEN 'CANCELLED' THEN 3 WHEN 'SHIPPED' THEN 2 WHEN 'PLACED' THEN 1 ELSE 0 END DESC
    ) = 1
    ORDER BY order_id;
    ```

    Both versions were run in `t05_dedup.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    The second version uses `max_by` with a struct: structs compare field by field, so the struct
    `(updated_at, priority)` orders by time, then priority. The script checked that both versions agree.

    **Why it works:** `row_number` over `updated_at DESC` puts the latest event first; the priority expression
    breaks the tie for order 1003 deterministically. In SQL, `QUALIFY` filters on the window result directly.

    **Common mistakes:** `dropDuplicates(["order_id"])` keeps one row per order, but the documentation does not
    say which one ([DataFrame.dropDuplicates](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.dropDuplicates.html)).
    In this run it kept `PLACED` for order 1001, which is the old status:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    # The common shortcut: it keeps one row per order, but which row is not defined
    events.dropDuplicates(["order_id"]).select("order_id", "status", "updated_at").orderBy("order_id").show()
    ```

    ```text
    +--------+------+-------------------+
    |order_id|status|         updated_at|
    +--------+------+-------------------+
    |    1001|PLACED|2026-03-01 10:15:00|
    |    1002|PLACED|2026-03-01 11:05:00|
    |    1003|PLACED|2026-03-02 09:40:00|
    +--------+------+-------------------+
    ```

    Sorting the DataFrame first does not fix it, because nothing in the API promises which row survives. Use a
    window with a complete ordering. In a `MERGE` source, this deduplication is what prevents the "multiple source rows matched" error
    (Q24 in 25.13).

**Task 37. Keep one row per event (order, status and time), with the first file the event arrived in and the
number of copies.**

Expected output:

```text
+--------+---------+-------------------+----------------+------+
|order_id|status   |updated_at         |first_file      |copies|
+--------+---------+-------------------+----------------+------+
|1001    |PLACED   |2026-03-01 10:15:00|orders_0301.json|2     |
|1001    |SHIPPED  |2026-03-02 08:00:00|orders_0302.json|1     |
|1002    |PLACED   |2026-03-01 11:05:00|orders_0301.json|2     |
|1003    |CANCELLED|2026-03-02 09:40:00|orders_0302.json|1     |
|1003    |PLACED   |2026-03-02 09:40:00|orders_0302.json|1     |
+--------+---------+-------------------+----------------+------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (events
              .groupBy("order_id", "status", "updated_at")
              .agg(F.min("source_file").alias("first_file"),
                   F.count("*").alias("copies"))
              .orderBy("order_id", "updated_at", "status"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, status, updated_at,
           min(source_file) AS first_file,
           count(*)         AS copies
    FROM events
    GROUP BY order_id, status, updated_at
    ORDER BY order_id, updated_at, status;
    ```

    Both versions were run in `t05_dedup.py`, which asserts that they return the same columns, column types and 5 rows in the same order. The output is the expected output above.

    **Why it works:** grouping by the columns that define "the same event" collapses the copies; `min` chooses a
    file deterministically (file names here sort by date), and `count` keeps the evidence of how many copies
    arrived.

    **Common mistakes:** `dropDuplicates(["order_id", "status", "updated_at"])` gives the same rows but an
    arbitrary `source_file`, which makes lineage questions ("which file did this come from?") unanswerable.

## 25.8 Nested data: JSON, structs and arrays

*Level: intermediate.*

Order events arrive as JSON with a nested `customer` object and an `items` array. The tasks read them with an
explicit schema, flatten the structs, explode the array, deal with records that do not parse, rebuild arrays
from rows, and work inside arrays without exploding them. The SQL side of all of this (`from_json`, `explode`,
`LATERAL VIEW`, the higher-order functions) is in [18. Nested and semi-structured data](18-Semi-Structured-Data.md).

The input for Tasks 38, 39, 40 and 43 is one JSON Lines file written by this block. It also registers
the file's raw lines as the view `raw_lines` (one string column, `value`) for the SQL versions, and defines the
schema:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
import json, os
landing = f"{WORK}/landing/orders"            # on Databricks: a volume path such as /Volumes/shop/bronze/landing
os.makedirs(landing, exist_ok=True)
records = [
    {"order_id": 1001, "customer": {"id": 1, "name": "Ana Lopez", "address": {"city": "Calgary", "country": "CA"}},
     "order_ts": "2026-03-01T10:15:00Z", "status": "SHIPPED", "amount": "59.90", "currency": "CAD",
     "items": [{"product_id": 3, "qty": 2, "unit_price": "29.95"}]},
    {"order_id": 1009, "customer": {"id": 4, "name": "Dev Patel", "address": {"city": "Vancouver", "country": "CA"}},
     "order_ts": "2026-03-05T09:30:00Z", "status": "PLACED", "amount": "308.90", "currency": "CAD",
     "items": [{"product_id": 1, "qty": 1, "unit_price": "249.00"},
               {"product_id": 3, "qty": 2, "unit_price": "29.95"}]},
    {"order_id": 1010, "customer": {"id": 2, "name": "Ben Okafor", "address": {"city": "Denver", "country": "US"}},
     "order_ts": "2026-03-05T12:00:00Z", "status": "CANCELLED", "amount": "0.00", "currency": "USD",
     "items": []},
]
with open(f"{landing}/orders_0305.json", "w") as f:
    f.write("\n".join(json.dumps(r) for r in records) + "\n")

spark.read.text(landing).createOrReplaceTempView("raw_lines")   # one row per line, column "value"

order_schema = """
    order_id INT,
    customer STRUCT<id: INT, name: STRING, address: STRUCT<city: STRING, country: STRING>>,
    order_ts TIMESTAMP, status STRING, amount DECIMAL(10,2), currency STRING,
    items ARRAY<STRUCT<product_id: INT, qty: INT, unit_price: DECIMAL(10,2)>>"""
```

**Task 38. Read the order files with an explicit schema: amounts as DECIMAL(10,2), `order_ts` as TIMESTAMP, the
items as an array of structs.**

Expected output:

```text
root
 |-- order_id: integer (nullable = true)
 |-- customer: struct (nullable = true)
 |    |-- id: integer (nullable = true)
 |    |-- name: string (nullable = true)
 |    |-- address: struct (nullable = true)
 |    |    |-- city: string (nullable = true)
 |    |    |-- country: string (nullable = true)
 |-- order_ts: timestamp (nullable = true)
 |-- status: string (nullable = true)
 |-- amount: decimal(10,2) (nullable = true)
 |-- currency: string (nullable = true)
 |-- items: array (nullable = true)
 |    |-- element: struct (containsNull = true)
 |    |    |-- product_id: integer (nullable = true)
 |    |    |-- qty: integer (nullable = true)
 |    |    |-- unit_price: decimal(10,2) (nullable = true)
```

```text
+--------+-------------------------------+-------------------+---------+------+--------+-------------------------------+
|order_id|customer                       |order_ts           |status   |amount|currency|items                          |
+--------+-------------------------------+-------------------+---------+------+--------+-------------------------------+
|1001    |{1, Ana Lopez, {Calgary, CA}}  |2026-03-01 10:15:00|SHIPPED  |59.90 |CAD     |[{3, 2, 29.95}]                |
|1009    |{4, Dev Patel, {Vancouver, CA}}|2026-03-05 09:30:00|PLACED   |308.90|CAD     |[{1, 1, 249.00}, {3, 2, 29.95}]|
|1010    |{2, Ben Okafor, {Denver, US}}  |2026-03-05 12:00:00|CANCELLED|0.00  |USD     |[]                             |
+--------+-------------------------------+-------------------+---------+------+--------+-------------------------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = spark.read.schema(order_schema).json(landing)
    result.printSchema()
    result.createOrReplaceTempView("orders_raw")          # used by the next tasks
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT j.*
    FROM (SELECT from_json(value, 'order_id INT,
                    customer STRUCT<id: INT, name: STRING, address: STRUCT<city: STRING, country: STRING>>,
                    order_ts TIMESTAMP, status STRING, amount DECIMAL(10,2), currency STRING,
                    items ARRAY<STRUCT<product_id: INT, qty: INT, unit_price: DECIMAL(10,2)>>') AS j
          FROM raw_lines);
    ```

    Both versions were run in `t06_nested.py`, which asserts that they return the same columns, column types and 3 rows. The output is the expected output above.

    **Why it works:** with `.schema(...)` the reader does not sample the files to guess types, and it converts as
    it reads: the quoted `"59.90"` becomes a decimal and the ISO string with `Z` a timestamp. The SQL version
    parses the same lines with `from_json` and the same schema string. On Databricks you would more often read
    the files with Auto Loader or `read_files` into bronze ([8. Into bronze](08-Bronze-Ingestion.md)).

    **Common mistakes:** relying on inference. Without a schema, the same file gives strings for both money and
    time:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    inferred = spark.read.json(landing)
    print([(f.name, f.dataType.simpleString()) for f in inferred.schema.fields if f.name in ("amount", "order_ts")])
    ```

    ```text
    [('amount', 'string'), ('order_ts', 'string')]
    ```

    Inference also costs an extra pass over the data, and a new file can change the inferred types.

**Task 39. Flatten every struct column (at any depth) into top-level columns named `parent_child`, leaving the
`items` array aside.**

Input: `orders_raw` from Task 38. Expected output:

```text
+--------+-----------+-------------+---------------------+------------------------+-------------------+---------+------+--------+
|order_id|customer_id|customer_name|customer_address_city|customer_address_country|order_ts           |status   |amount|currency|
+--------+-----------+-------------+---------------------+------------------------+-------------------+---------+------+--------+
|1001    |1          |Ana Lopez    |Calgary              |CA                      |2026-03-01 10:15:00|SHIPPED  |59.90 |CAD     |
|1009    |4          |Dev Patel    |Vancouver            |CA                      |2026-03-05 09:30:00|PLACED   |308.90|CAD     |
|1010    |2          |Ben Okafor   |Denver               |US                      |2026-03-05 12:00:00|CANCELLED|0.00  |USD     |
+--------+-----------+-------------+---------------------+------------------------+-------------------+---------+------+--------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    from pyspark.sql.types import StructType

    def flatten(df):
        """Replace each struct column by its fields, named parent_child, until no struct is left."""
        while True:
            structs = [f for f in df.schema.fields if isinstance(f.dataType, StructType)]
            if not structs:
                return df
            cols = []
            for f in df.schema.fields:
                if isinstance(f.dataType, StructType):
                    cols += [F.col(f"`{f.name}`.`{c.name}`").alias(f"{f.name}_{c.name}")
                             for c in f.dataType.fields]
                else:
                    cols.append(F.col(f"`{f.name}`"))
            df = df.select(cols)

    orders_raw = spark.table("orders_raw")
    result = flatten(orders_raw.drop("items")).orderBy("order_id")

    # The same columns written by hand
    alt_explicit = (orders_raw
                    .select("order_id",
                            F.col("customer.id").alias("customer_id"),
                            F.col("customer.name").alias("customer_name"),
                            F.col("customer.address.city").alias("customer_address_city"),
                            F.col("customer.address.country").alias("customer_address_country"),
                            "order_ts", "status", "amount", "currency")
                    .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id,
           customer.id               AS customer_id,
           customer.name             AS customer_name,
           customer.address.city     AS customer_address_city,
           customer.address.country  AS customer_address_country,
           order_ts, status, amount, currency
    FROM orders_raw
    ORDER BY order_id;
    ```

    Both versions were run in `t06_nested.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** each pass replaces every struct column by its fields; `address` is itself a struct, so the
    loop runs until no struct is left. Backticks in `F.col("`a`.`b`")` protect names that contain dots or spaces.
    The hand-written `alt_explicit` returns the same columns, which the script checked. For one level,
    `select("customer.*")` is the shortcut.

    **Common mistakes:** `select("customer.*", "customer.address.*")` keeps the struct `address` and can produce
    duplicate column names (two structs with a field `id`), which fail later; prefix the names as here. Arrays are
    not structs: flattening `items` needs `explode` (next task).

**Task 40. Produce one row per order line with a line number, keeping orders that have no items as one row with
NULLs.**

Input: `orders_raw`. Expected output:

```text
+--------+-------+----------+----+----------+
|order_id|line_no|product_id|qty |unit_price|
+--------+-------+----------+----+----------+
|1001    |1      |3         |2   |29.95     |
|1009    |1      |1         |1   |249.00    |
|1009    |2      |3         |2   |29.95     |
|1010    |NULL   |NULL      |NULL|NULL      |
+--------+-------+----------+----+----------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (spark.table("orders_raw")
              .select("order_id", F.posexplode_outer("items").alias("pos", "item"))
              .select("order_id",
                      (F.col("pos") + 1).alias("line_no"),
                      "item.product_id", "item.qty", "item.unit_price")
              .orderBy("order_id", "line_no"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT o.order_id, t.pos + 1 AS line_no, t.item.product_id, t.item.qty, t.item.unit_price
    FROM orders_raw o
    LATERAL VIEW OUTER posexplode(o.items) t AS pos, item
    ORDER BY o.order_id, line_no;
    ```

    Both versions were run in `t06_nested.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** `posexplode_outer` returns the position (from 0) and the element of each array entry, and
    for an empty or NULL array it still returns one row with NULLs
    ([posexplode_outer](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.posexplode_outer.html)).
    `item.*`-style access (`"item.product_id"`) then flattens the struct.

    **Common mistakes:** plain `explode` drops the cancelled order 1010, whose array is empty:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    print("explode rows:", spark.table("orders_raw").select(F.explode("items")).count(),
          "  explode_outer rows:", spark.table("orders_raw").select(F.explode_outer("items")).count())
    ```

    ```text
    explode rows: 3   explode_outer rows: 4
    ```

    If the order must still be counted (for example "orders with no items" as a quality check), you need the
    `_outer` form.

**Task 41. A bronze table holds raw JSON strings. Parse them and flag the rows that are not valid for the schema.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
bronze = spark.createDataFrame([
    (1, '{"order_id": 1001, "amount": "59.90"}'),
    (2, '{"order_id": 1002, "amount": 249.00'),          # broken JSON: no closing brace
    (3, '{"order_id": "x1003", "amount": "189.50"}'),    # order_id is not a number
    (4, None),
], "line INT, payload STRING")
bronze.createOrReplaceTempView("bronze")
```

Expected output:

```text
+----+--------+------+-----+
|line|order_id|amount|bad  |
+----+--------+------+-----+
|1   |1001    |59.90 |false|
|2   |NULL    |NULL  |true |
|3   |NULL    |189.50|true |
|4   |NULL    |NULL  |true |
+----+--------+------+-----+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    schema = "order_id INT, amount DECIMAL(10,2), _corrupt_record STRING"
    result = (bronze
              .withColumn("j", F.from_json("payload", schema,
                                           {"columnNameOfCorruptRecord": "_corrupt_record"}))
              .select("line", "j.order_id", "j.amount",
                      (F.col("payload").isNull() | F.col("j._corrupt_record").isNotNull()).alias("bad"))
              .orderBy("line"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT line, j.order_id, j.amount,
           (payload IS NULL OR j._corrupt_record IS NOT NULL) AS bad
    FROM (SELECT line, payload,
                 from_json(payload, 'order_id INT, amount DECIMAL(10,2), _corrupt_record STRING',
                           map('columnNameOfCorruptRecord', '_corrupt_record')) AS j
          FROM bronze)
    ORDER BY line;
    ```

    Both versions were run in `t06_nested.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** `from_json` accepts the JSON data source options
    ([from_json](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.from_json.html)).
    In the default `PERMISSIVE` mode, a string field named by `columnNameOfCorruptRecord` that is part of the
    schema receives the malformed record's text, and the malformed fields are set to NULL
    ([JSON Files](https://spark.apache.org/docs/latest/sql-data-sources-json.html)).
    Line 2 is broken JSON; line 3 is valid JSON with a value of the wrong type, and both land there. A NULL payload
    gives a NULL struct, which the extra `payload IS NULL` test catches.

    **Common mistakes:** testing `j IS NULL` to find bad rows. Without the corrupt-record column, a broken record
    gives a struct of NULLs, not NULL, and a type mismatch gives a partly filled struct (line 3 keeps its amount):

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    bronze.select("line", F.from_json("payload", "order_id INT, amount DECIMAL(10,2)").alias("j")).show()
    ```

    ```text
    +----+--------------+
    |line|             j|
    +----+--------------+
    |   1| {1001, 59.90}|
    |   2|  {NULL, NULL}|
    |   3|{NULL, 189.50}|
    |   4|          NULL|
    +----+--------------+
    ```

    Testing "all fields NULL" would miss line 3. Keep the raw string in bronze so a bad row can be fixed and
    replayed.

**Task 42. Collect order lines back into one row per order: the sorted product names, the items as an array of
structs, the units, and the items as a JSON string.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
lines = spark.createDataFrame([
    (1001, 3, 2), (1009, 3, 2), (1009, 1, 1), (1003, 2, 1),
], "order_id INT, product_id INT, qty INT")
lines.createOrReplaceTempView("lines")
```

Expected output:

```text
+--------+-------------------------------+----------------+-----+---------------------------------------------------+
|order_id|products                       |items           |units|items_json                                         |
+--------+-------------------------------+----------------+-----+---------------------------------------------------+
|1001    |[Trekking Poles]               |[{3, 2}]        |2    |[{"product_id":3,"qty":2}]                         |
|1003    |[Down Sleeping Bag]            |[{2, 1}]        |1    |[{"product_id":2,"qty":1}]                         |
|1009    |[Trail Tent 2P, Trekking Poles]|[{1, 1}, {3, 2}]|3    |[{"product_id":1,"qty":1},{"product_id":3,"qty":2}]|
+--------+-------------------------------+----------------+-----+---------------------------------------------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (lines
              .join(products, "product_id")
              .groupBy("order_id")
              .agg(F.array_sort(F.collect_list("name")).alias("products"),
                   F.array_sort(F.collect_list(F.struct("product_id", "qty"))).alias("items"),
                   F.sum("qty").alias("units"))
              .withColumn("items_json", F.to_json("items"))
              .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id,
           array_sort(collect_list(p.name))                     AS products,
           array_sort(collect_list(struct(l.product_id, l.qty))) AS items,
           sum(l.qty)                                            AS units,
           to_json(array_sort(collect_list(struct(l.product_id, l.qty)))) AS items_json
    FROM lines l
    JOIN products p ON p.product_id = l.product_id
    GROUP BY order_id
    ORDER BY order_id;
    ```

    Both versions were run in `t06_nested.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** `collect_list` gathers the values of a group into an array; `struct(...)` inside it builds
    an array of structs, and `to_json` serializes it. `array_sort` sorts structs by their first field, then the
    next.

    **Common mistakes:** trusting the order of `collect_list`: "The order of elements in the array is
    non-deterministic" ([collect_list](https://docs.databricks.com/aws/en/sql/language-manual/functions/collect_list)),
    so sort the array (or sort a struct whose first field is the
    sort key). `collect_set` removes duplicates, which is wrong for order lines where the same product can appear
    twice. And a group with millions of values builds a huge array in one task.

**Task 43. Without exploding, compute for each order the number of items, the total of `qty * unit_price` over
its items, the products ordered with a quantity of 2 or more, and whether the total matches `amount`.**

Input: `orders_raw`. Expected output:

```text
+--------+------+-------+-----------+------------------+-------+
|order_id|amount|n_items|items_total|multi_qty_products|matches|
+--------+------+-------+-----------+------------------+-------+
|1001    |59.90 |1      |59.90      |[3]               |true   |
|1009    |308.90|2      |308.90     |[3]               |true   |
|1010    |0.00  |0      |0.00       |[]                |true   |
+--------+------+-------+-----------+------------------+-------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    line_total = lambda acc, x: (acc + x["qty"] * x["unit_price"]).cast("decimal(10,2)")
    result = (spark.table("orders_raw")
              .select("order_id", "amount",
                      F.size("items").alias("n_items"),
                      F.aggregate("items", F.lit(0).cast("decimal(10,2)"), line_total).alias("items_total"),
                      F.transform(F.filter("items", lambda x: x["qty"] >= 2),
                                  lambda x: x["product_id"]).alias("multi_qty_products"))
              .withColumn("matches", F.col("amount") == F.col("items_total"))
              .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, amount,
           size(items) AS n_items,
           aggregate(items, CAST(0 AS DECIMAL(10,2)),
                     (acc, x) -> CAST(acc + x.qty * x.unit_price AS DECIMAL(10,2))) AS items_total,
           transform(filter(items, x -> x.qty >= 2), x -> x.product_id)          AS multi_qty_products,
           amount = aggregate(items, CAST(0 AS DECIMAL(10,2)),
                              (acc, x) -> CAST(acc + x.qty * x.unit_price AS DECIMAL(10,2))) AS matches
    FROM orders_raw
    ORDER BY order_id;
    ```

    Both versions were run in `t06_nested.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** higher-order functions take a Python lambda (a SQL lambda `x -> ...` in SQL) and run it on
    every element inside the array, row by row, with no explode, shuffle or regroup.
    `aggregate(array, start, merge)` folds the array into one value
    ([aggregate](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.aggregate.html));
    `filter` keeps elements and `transform` maps them.

    **Common mistakes:** the start value and the merge result must have the same type. `qty * unit_price` widens
    the decimal, so without the `cast` in the lambda the query fails:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    try:
        spark.table("orders_raw").select(
            F.aggregate("items", F.lit(0).cast("decimal(10,2)"),
                        lambda acc, x: acc + x["qty"] * x["unit_price"])).collect()
    except Exception as e:
        import re
        msg = str(e)
        print(msg.split("]")[0] + "]")
        print(re.search(r'The third parameter requires the "[^"]+" type', msg).group(0) + ",",
              re.search(r'has the type "[^"]+"', msg).group(0))
    ```

    ```text
    [DATATYPE_MISMATCH.UNEXPECTED_INPUT_TYPE]
    The third parameter requires the "DECIMAL(10,2)" type, has the type "DECIMAL(22,2)"
    ```

    Starting from `F.lit(0)` (an INT) fails the same way. Chapter 18 has more on lambdas
    ([18. Nested and semi-structured data](18-Semi-Structured-Data.md)).

## 25.9 Dates, time and sessions

*Level: intermediate.*

Time questions are popular because they combine windows with date functions: buckets by day, week and month,
gaps between events, calendars with missing days, sessions, and streaks. Two facts matter in all of them: the
data here is stored in UTC (the session time zone is UTC), and `date_trunc('week', ...)` starts weeks on Monday.
The date functions are in [19. The function toolbox](19-Function-Toolbox.md).

**Task 44. Revenue and order count by day, by week and by month, in one result with a `grain` column.**

Input: `orders`. Expected output:

```text
+-----+------------+--------+-------+
|grain|period_start|n_orders|revenue|
+-----+------------+--------+-------+
|day  |2026-03-01  |2       |308.90 |
|day  |2026-03-02  |2       |228.50 |
|day  |2026-03-03  |2       |347.95 |
|day  |2026-03-04  |2       |237.00 |
|month|2026-03-01  |8       |1122.35|
|week |2026-02-23  |2       |308.90 |
|week |2026-03-02  |6       |813.45 |
+-----+------------+--------+-------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    def by_period(unit):
        return (orders
                .groupBy(F.date_trunc(unit, "order_ts").cast("date").alias("period_start"))
                .agg(F.count("*").alias("n_orders"), F.sum("amount").alias("revenue"))
                .withColumn("grain", F.lit(unit)))

    result = (by_period("day").unionByName(by_period("week")).unionByName(by_period("month"))
              .select("grain", "period_start", "n_orders", "revenue")
              .orderBy("grain", "period_start"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT 'day' AS grain, CAST(date_trunc('day', order_ts) AS DATE) AS period_start,
           count(*) AS n_orders, sum(amount) AS revenue
    FROM orders GROUP BY 2
    UNION ALL
    SELECT 'week', CAST(date_trunc('week', order_ts) AS DATE), count(*), sum(amount)
    FROM orders GROUP BY 2
    UNION ALL
    SELECT 'month', CAST(date_trunc('month', order_ts) AS DATE), count(*), sum(amount)
    FROM orders GROUP BY 2
    ORDER BY grain, period_start;
    ```

    Both versions were run in `t07_dates.py`, which asserts that they return the same columns, column types and 7 rows in the same order. The output is the expected output above.

    **Why it works:** `date_trunc(unit, ts)` rounds a timestamp down to the start of the unit. The weekly rows
    show that weeks start on Monday: Sunday March 1 belongs to the week of Monday February 23, which is why the
    first week has only two orders. The same function feeds all three grains, so `unionByName` can stack them.

    **Common mistakes:** grouping by `weekofyear` alone, which merges the same week number of different years;
    assuming a week starts on Sunday or on the 1st of the month; and grouping by the raw timestamp, which gives
    one group per second.

**Task 45. For each order, the days and hours since the same customer's previous order.**

Input: `orders`. Expected output:

```text
+-----------+--------+-------------------+---------------+----------------+
|customer_id|order_id|order_ts           |days_since_prev|hours_since_prev|
+-----------+--------+-------------------+---------------+----------------+
|1          |1001    |2026-03-01 10:15:00|NULL           |NULL            |
|1          |1003    |2026-03-02 09:40:00|1              |23.4            |
|1          |1008    |2026-03-04 19:10:00|2              |57.5            |
|2          |1002    |2026-03-01 11:05:00|NULL           |NULL            |
|2          |1006    |2026-03-03 17:30:00|2              |54.4            |
|3          |1004    |2026-03-02 14:20:00|NULL           |NULL            |
|3          |1007    |2026-03-04 12:00:00|2              |45.7            |
|4          |1005    |2026-03-03 08:55:00|NULL           |NULL            |
+-----------+--------+-------------------+---------------+----------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    w = Window.partitionBy("customer_id").orderBy("order_ts")
    result = (orders
              .withColumn("prev_ts", F.lag("order_ts").over(w))
              .withColumn("days_since_prev", F.datediff(F.to_date("order_ts"), F.to_date("prev_ts")))
              .withColumn("hours_since_prev",
                          F.round((F.unix_timestamp("order_ts") - F.unix_timestamp("prev_ts")) / 3600, 1))
              .select("customer_id", "order_id", "order_ts", "days_since_prev", "hours_since_prev")
              .orderBy("customer_id", "order_ts"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id, order_id, order_ts,
           datediff(to_date(order_ts), to_date(lag(order_ts) OVER w))                    AS days_since_prev,
           round((unix_timestamp(order_ts) - unix_timestamp(lag(order_ts) OVER w)) / 3600, 1) AS hours_since_prev
    FROM orders
    WINDOW w AS (PARTITION BY customer_id ORDER BY order_ts)
    ORDER BY customer_id, order_ts;
    ```

    Both versions were run in `t07_dates.py`, which asserts that they return the same columns, column types and 8 rows in the same order. The output is the expected output above.

    **Why it works:** `lag` fetches the previous order time in the customer's window. `datediff(end, start)`
    counts calendar-day boundaries between the two dates; the difference of `unix_timestamp` values is in
    seconds, so dividing by 3600 gives hours. Ana's second order is 1 calendar day but 23.4 hours after the first.

    **Common mistakes:** swapping the arguments of `datediff`, which gives negative numbers (Q19 in 25.13); and
    answering "days" with calendar days when the business means 24-hour periods, or the reverse. Ask.

**Task 46. Daily revenue for March 1 to 7, with a row (0 orders, revenue 0) for days without orders.**

Input: `orders`. Expected output:

```text
+----------+--------+-------+
|day       |n_orders|revenue|
+----------+--------+-------+
|2026-03-01|2       |308.90 |
|2026-03-02|2       |228.50 |
|2026-03-03|2       |347.95 |
|2026-03-04|2       |237.00 |
|2026-03-05|0       |0.00   |
|2026-03-06|0       |0.00   |
|2026-03-07|0       |0.00   |
+----------+--------+-------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    days = spark.range(1).select(
        F.explode(F.sequence(F.lit("2026-03-01").cast("date"), F.lit("2026-03-07").cast("date"))).alias("day"))
    daily = (orders
             .groupBy(F.to_date("order_ts").alias("day"))
             .agg(F.count("*").alias("n_orders"), F.sum("amount").alias("revenue")))
    result = (days
              .join(daily, "day", "left")
              .fillna(0, subset=["n_orders", "revenue"])
              .orderBy("day"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    WITH days AS (
      SELECT explode(sequence(DATE'2026-03-01', DATE'2026-03-07', INTERVAL 1 DAY)) AS day
    ),
    daily AS (
      SELECT to_date(order_ts) AS day, count(*) AS n_orders, sum(amount) AS revenue
      FROM orders GROUP BY 1
    )
    SELECT d.day, coalesce(x.n_orders, 0) AS n_orders, coalesce(x.revenue, 0) AS revenue
    FROM days d LEFT JOIN daily x ON x.day = d.day
    ORDER BY d.day;
    ```

    Both versions were run in `t07_dates.py`, which asserts that they return the same columns, column types and 7 rows in the same order. The output is the expected output above.

    **Why it works:** `sequence(start, stop, step)` builds an array, and `explode` turns it into a one-column
    calendar. The PySpark version leaves out the step and got one day per element in this run, which matches the
    documented default for `DATE` sequences, `INTERVAL '1' DAY`
    ([sequence function](https://docs.databricks.com/aws/en/sql/language-manual/functions/sequence)); the SQL
    version passes `INTERVAL 1 DAY` explicitly, which is clearer. A left join from the calendar keeps every day; `fillna`
    (or `coalesce` in SQL) turns the missing counts into 0.

    **Common mistakes:** grouping the orders and expecting empty days to appear; joining the calendar on the
    timestamp instead of the date; and joining from the orders side (`orders.join(days, ..., "left")`), which keeps
    the orders, not the days.

**Task 47. Group each customer's click events into sessions: a gap of more than 30 minutes since the previous
event starts a new session. Return each session's start, end and number of events.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
clicks = spark.createDataFrame([
    (1, dt(2026, 3, 1, 10, 0)), (1, dt(2026, 3, 1, 10, 10)), (1, dt(2026, 3, 1, 10, 40)),  # 30-min gap
    (1, dt(2026, 3, 1, 11, 30)), (1, dt(2026, 3, 1, 11, 45)),                              # 50-min gap
    (2, dt(2026, 3, 1, 9, 0)), (2, dt(2026, 3, 1, 9, 31)), (2, dt(2026, 3, 1, 9, 50)),     # 31-min gap
], "customer_id INT, event_ts TIMESTAMP")
clicks.createOrReplaceTempView("clicks")
```

Expected output:

```text
+-----------+----------+-------------------+-------------------+--------+
|customer_id|session_no|session_start      |session_end        |n_events|
+-----------+----------+-------------------+-------------------+--------+
|1          |1         |2026-03-01 10:00:00|2026-03-01 10:40:00|3       |
|1          |2         |2026-03-01 11:30:00|2026-03-01 11:45:00|2       |
|2          |1         |2026-03-01 09:00:00|2026-03-01 09:00:00|1       |
|2          |2         |2026-03-01 09:31:00|2026-03-01 09:50:00|2       |
+-----------+----------+-------------------+-------------------+--------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    w = Window.partitionBy("customer_id").orderBy("event_ts")
    gap_min = (F.unix_timestamp("event_ts") - F.unix_timestamp(F.lag("event_ts").over(w))) / 60
    flagged = clicks.withColumn("new_session", F.when(gap_min.isNull() | (gap_min > 30), 1).otherwise(0))
    numbered = flagged.withColumn(
        "session_no", F.sum("new_session").over(w.rowsBetween(Window.unboundedPreceding, Window.currentRow)))
    result = (numbered
              .groupBy("customer_id", "session_no")
              .agg(F.min("event_ts").alias("session_start"),
                   F.max("event_ts").alias("session_end"),
                   F.count("*").alias("n_events"))
              .orderBy("customer_id", "session_no"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    WITH flagged AS (
      SELECT customer_id, event_ts,
             CASE WHEN lag(event_ts) OVER w IS NULL
                    OR (unix_timestamp(event_ts) - unix_timestamp(lag(event_ts) OVER w)) / 60 > 30
                  THEN 1 ELSE 0 END AS new_session
      FROM clicks
      WINDOW w AS (PARTITION BY customer_id ORDER BY event_ts)
    ),
    numbered AS (
      SELECT *, sum(new_session) OVER (PARTITION BY customer_id ORDER BY event_ts
                                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS session_no
      FROM flagged
    )
    SELECT customer_id, session_no,
           min(event_ts) AS session_start, max(event_ts) AS session_end, count(*) AS n_events
    FROM numbered
    GROUP BY customer_id, session_no
    ORDER BY customer_id, session_no;
    ```

    Both versions were run in `t07_dates.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** three steps. Flag an event as a session start when it is the customer's first or comes more
    than 30 minutes after the previous one; a running sum of the flags numbers the sessions (1, 1, 1, 2, 2 for
    customer 1); then group by the number. The 10:40 event is exactly 30 minutes after 10:10, which is not "more
    than 30", so it stays in session 1; customer 2's 31-minute gap starts a new one.

    **Common mistakes:** not asking whether exactly 30 minutes splits the session; forgetting the first event
    (its `lag` is NULL, and `NULL > 30` is not true, so without the `isNull` test the first session gets number
    0); and ordering the window by an unrelated column. Spark also has a built-in `session_window`, which returns
    the same groups here; its window `end` is the last event plus the gap, not the last event
    ([session_window](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.session_window.html)):

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    # Spark's built-in session_window, for comparison
    (clicks.groupBy("customer_id", F.session_window("event_ts", "30 minutes").alias("s"))
           .agg(F.count("*").alias("n_events"))
           .select("customer_id", "s.start", "s.end", "n_events")
           .orderBy("customer_id", "start")
           .show())
    ```

    ```text
    +-----------+-------------------+-------------------+--------+
    |customer_id|              start|                end|n_events|
    +-----------+-------------------+-------------------+--------+
    |          1|2026-03-01 10:00:00|2026-03-01 11:10:00|       3|
    |          1|2026-03-01 11:30:00|2026-03-01 12:15:00|       2|
    |          2|2026-03-01 09:00:00|2026-03-01 09:30:00|       1|
    |          2|2026-03-01 09:31:00|2026-03-01 10:20:00|       2|
    +-----------+-------------------+-------------------+--------+
    ```

    It is most useful in streaming aggregations with a watermark
    ([11. Structured Streaming](11-Structured-Streaming.md)); in a batch interview the window version shows that
    you understand the logic.

**Task 48. Find each customer's streaks of consecutive days with at least one order (gaps and islands).**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
order_days = spark.createDataFrame([
    (1, "2026-03-01"), (1, "2026-03-02"), (1, "2026-03-03"), (1, "2026-03-05"),
    (1, "2026-03-06"), (1, "2026-03-09"), (2, "2026-03-02"), (2, "2026-03-03"),
    (2, "2026-03-03"),                                                   # two orders on one day
], "customer_id INT, day STRING").withColumn("day", F.to_date("day"))
order_days.createOrReplaceTempView("order_days")
```

Expected output:

```text
+-----------+------------+----------+----+
|customer_id|streak_start|streak_end|days|
+-----------+------------+----------+----+
|1          |2026-03-01  |2026-03-03|3   |
|1          |2026-03-05  |2026-03-06|2   |
|1          |2026-03-09  |2026-03-09|1   |
|2          |2026-03-02  |2026-03-03|2   |
+-----------+------------+----------+----+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    d = order_days.distinct()
    w = Window.partitionBy("customer_id").orderBy("day")
    islands = d.withColumn("grp", F.date_sub("day", F.row_number().over(w)))   # constant within a streak
    result = (islands
              .groupBy("customer_id", "grp")
              .agg(F.min("day").alias("streak_start"),
                   F.max("day").alias("streak_end"),
                   F.count("*").alias("days"))
              .drop("grp")
              .orderBy("customer_id", "streak_start"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    WITH d AS (SELECT DISTINCT customer_id, day FROM order_days),
    islands AS (
      SELECT customer_id, day,
             date_sub(day, row_number() OVER (PARTITION BY customer_id ORDER BY day)) AS grp
      FROM d
    )
    SELECT customer_id, min(day) AS streak_start, max(day) AS streak_end, count(*) AS days
    FROM islands
    GROUP BY customer_id, grp
    ORDER BY customer_id, streak_start;
    ```

    Both versions were run in `t07_dates.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** within a run of consecutive days, the date and the row number both go up by 1, so
    `day - row_number` is the same for every day of the run and changes after a gap. That constant (`grp`)
    identifies the island; grouping by it gives the start, end and length.

    **Common mistakes:** skipping `distinct()`: customer 2 has two orders on March 3, and a repeated day would
    shift the row numbers and split the streak. `dense_rank` over the non-distinct days also works. The same
    trick finds consecutive IDs or months (use a month index instead of a date).

**Task 49. The timestamps are stored in UTC. Report each order's local time and local date in Calgary
(`America/Edmonton`).**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
late_orders = spark.createDataFrame([
    (2001, dt(2026, 3, 1, 23, 30)), (2002, dt(2026, 3, 2, 3, 30)), (2003, dt(2026, 3, 2, 15, 0)),
], "order_id INT, order_ts TIMESTAMP")                     # stored in UTC
late_orders.createOrReplaceTempView("late_orders")
```

Expected output:

```text
+--------+-------------------+----------+-------------------+----------+
|order_id|order_ts           |utc_date  |local_ts           |local_date|
+--------+-------------------+----------+-------------------+----------+
|2001    |2026-03-01 23:30:00|2026-03-01|2026-03-01 16:30:00|2026-03-01|
|2002    |2026-03-02 03:30:00|2026-03-02|2026-03-01 20:30:00|2026-03-01|
|2003    |2026-03-02 15:00:00|2026-03-02|2026-03-02 08:00:00|2026-03-02|
+--------+-------------------+----------+-------------------+----------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    local_ts = F.from_utc_timestamp("order_ts", "America/Edmonton")    # Calgary's time zone
    result = (late_orders
              .select("order_id", "order_ts",
                      F.to_date("order_ts").alias("utc_date"),
                      local_ts.alias("local_ts"),
                      F.to_date(local_ts).alias("local_date"))
              .orderBy("order_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, order_ts,
           to_date(order_ts)                                         AS utc_date,
           from_utc_timestamp(order_ts, 'America/Edmonton')          AS local_ts,
           to_date(from_utc_timestamp(order_ts, 'America/Edmonton')) AS local_date
    FROM late_orders
    ORDER BY order_id;
    ```

    Both versions were run in `t07_dates.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** `from_utc_timestamp(ts, tz)` shifts a UTC timestamp to the wall-clock time of the zone,
    using that zone's rules for the date (UTC-7 in early March, before daylight saving time starts). Order 2002 was
    placed on March 2 in UTC but on the evening of March 1 in Calgary, so a "daily revenue in local time" report
    puts it on March 1.

    **Common mistakes:** using a fixed offset such as `-07:00`, which breaks when daylight saving time starts;
    and forgetting that the result depends on the session time zone. These runs use UTC:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    print("session time zone:", spark.conf.get("spark.sql.session.timeZone"))
    ```

    ```text
    session time zone: UTC
    ```

    Ask which time zone the business reports in before you build daily aggregates.

## 25.10 Data quality checks

*Level: intermediate.*

Data engineering interviews increasingly include a "this feed is dirty, make it safe" task. The tools are the
same functions as before, applied to every column at once and producing a report instead of a result table. In a
Lakeflow pipeline ([formerly Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) the same
rules would be written as expectations ([14. Data quality and CDC](14-Data-Quality-and-CDC.md)); here they are
plain DataFrame code.

Tasks 50 and 51 use this raw batch:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
incoming = spark.createDataFrame([
    (1011, 1,    "2026-03-06 10:00:00", "PLACED",  "45.00",  "CAD"),
    (1012, None, "2026-03-06 11:00:00", "PLACED",  "12.00",  "CAD"),
    (1013, 2,    "yesterday",           "PLACED",  "80.00",  "USD"),
    (1014, 3,    "2026-03-06 12:30:00", None,      "-5.00",  "EUR"),
    (None, 4,    "2026-03-06 13:00:00", "SHIPPED", "abc",    "CAD"),
    (1015, 4,    "2026-03-06 14:00:00", "SHIPPED", "120.00", "USD"),
    (1016, 1,    "2026-03-06 15:00:00", "PLACED",  "30.00",  None),
], "order_id INT, customer_id INT, order_ts STRING, status STRING, amount STRING, currency STRING")
incoming.createOrReplaceTempView("incoming")
```

**Task 50. Count the NULLs in every column, in one pass over the data, without naming the columns by hand.**

Expected output:

```text
+--------+-----------+--------+------+------+--------+
|order_id|customer_id|order_ts|status|amount|currency|
+--------+-----------+--------+------+------+--------+
|1       |1          |0       |1     |0     |1       |
+--------+-----------+--------+------+------+--------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = incoming.select([F.count_if(F.col(c).isNull()).alias(c) for c in incoming.columns])
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT count_if(order_id IS NULL)    AS order_id,
           count_if(customer_id IS NULL) AS customer_id,
           count_if(order_ts IS NULL)    AS order_ts,
           count_if(status IS NULL)      AS status,
           count_if(amount IS NULL)      AS amount,
           count_if(currency IS NULL)    AS currency
    FROM incoming;
    ```

    Both versions were run in `t08_quality.py`, which asserts that they return the same columns, column types and 1 rows. The output is the expected output above.

    **Why it works:** a Python list comprehension builds one `count_if(col IS NULL)` per column, and a single
    `select` computes them all in one scan. This works for any DataFrame, which is the point of the task. The
    SQL has to list the columns (or be generated from `df.columns`).

    **Common mistakes:** a loop of `df.filter(col.isNull()).count()` runs one job per column; and counting empty
    strings as present: if `''` should count as missing, test `F.col(c).isNull() | (F.trim(c) == "")` for string
    columns.

**Task 51. Split the batch into valid rows (typed, ready for silver) and invalid rows with every reason they
failed. Rules: `order_id` and `customer_id` present, `order_ts` a valid timestamp, `amount` a positive number,
currency `CAD` or `USD`.**

Expected output (the invalid rows):

```text
valid: 2  invalid: 5
```

```text
+--------+------+--------+-------------------------------------+
|order_id|amount|currency|reasons                              |
+--------+------+--------+-------------------------------------+
|NULL    |abc   |CAD     |order_id missing; amount not a number|
|1012    |12.00 |CAD     |customer_id missing                  |
|1013    |80.00 |USD     |bad order_ts                         |
|1014    |-5.00 |EUR     |amount not positive; unknown currency|
|1016    |30.00 |NULL    |unknown currency                     |
+--------+------+--------+-------------------------------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    amount = F.col("amount").try_cast("decimal(10,2)")
    ts = F.try_to_timestamp("order_ts")
    checks = [
        (F.col("order_id").isNull(), "order_id missing"),
        (F.col("customer_id").isNull(), "customer_id missing"),
        (ts.isNull(), "bad order_ts"),
        (amount.isNull(), "amount not a number"),
        (amount <= 0, "amount not positive"),
        (~F.coalesce(F.col("currency").isin("CAD", "USD"), F.lit(False)), "unknown currency"),
    ]
    reasons = F.concat_ws("; ", *[F.when(cond, F.lit(msg)) for cond, msg in checks])  # NULLs are skipped
    checked = incoming.withColumn("reasons", F.nullif(reasons, F.lit("")))

    valid = (checked.filter(F.col("reasons").isNull())
             .select("order_id", "customer_id", ts.alias("order_ts"), "status",
                     amount.alias("amount"), "currency"))
    invalid = checked.filter(F.col("reasons").isNotNull())
    result = invalid.select("order_id", "amount", "currency", "reasons").orderBy("order_id")
    print("valid:", valid.count(), " invalid:", invalid.count())
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, amount, currency, reasons
    FROM (
      SELECT *, nullif(concat_ws('; ',
               CASE WHEN order_id IS NULL THEN 'order_id missing' END,
               CASE WHEN customer_id IS NULL THEN 'customer_id missing' END,
               CASE WHEN try_to_timestamp(order_ts) IS NULL THEN 'bad order_ts' END,
               CASE WHEN try_cast(amount AS DECIMAL(10,2)) IS NULL THEN 'amount not a number' END,
               CASE WHEN try_cast(amount AS DECIMAL(10,2)) <= 0 THEN 'amount not positive' END,
               CASE WHEN NOT coalesce(currency IN ('CAD', 'USD'), false) THEN 'unknown currency' END), '')
               AS reasons
      FROM incoming)
    WHERE reasons IS NOT NULL
    ORDER BY order_id;
    ```

    Both versions were run in `t08_quality.py`, which asserts that they return the same columns, column types and 5 rows in the same order. The output is the expected output above.

    **Why it works:** each rule is a condition and a message. `when(cond, msg)` is NULL when the rule passes, and
    `concat_ws` skips NULLs, so `reasons` lists only the failed rules; `nullif(reasons, '')` makes a clean row
    NULL. One pass labels every row, and the valid and invalid sets are two filters on the same column, so no row
    can be in both or in neither.

    **Common mistakes:** reporting only the first failed rule (row `NULL / abc` fails two); writing two separate
    filters for valid and invalid rows with conditions that do not exactly mirror each other (NULLs make `~cond`
    differ from "not valid": for a NULL currency, both `isin` and `~isin` are NULL, which is why the currency
    rule wraps `isin` in `coalesce(..., false)`; order 1016 is caught only because of it); and dropping invalid rows
    instead of keeping them in a quarantine table with the reason ([9. Building silver](09-Building-Silver.md)).

**Task 52. A new version of the feed arrives. Compare its schema with the expected `orders` schema and list the
columns that are missing, added or changed type.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
expected = orders                                              # the silver orders schema
incoming_v2 = spark.createDataFrame(
    [(1016, 1, "2026-03-07 09:00:00", "PLACED", 45.0, "CAD", "web")],
    "order_id BIGINT, customer_id INT, order_ts STRING, status STRING, amount DOUBLE, "
    "currency STRING, channel STRING")
```

Expected output:

```text
+--------+-------------+------+------------+
|column  |expected     |actual|change      |
+--------+-------------+------+------------+
|amount  |decimal(10,2)|double|type changed|
|channel |NULL         |string|added       |
|order_id|int          |bigint|type changed|
|order_ts|timestamp    |string|type changed|
+--------+-------------+------+------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    exp = {f.name: f.dataType.simpleString() for f in expected.schema.fields}
    got = {f.name: f.dataType.simpleString() for f in incoming_v2.schema.fields}
    rows = ([(c, exp[c], None, "missing") for c in exp if c not in got]
            + [(c, None, got[c], "added") for c in got if c not in exp]
            + [(c, exp[c], got[c], "type changed") for c in exp if c in got and exp[c] != got[c]])
    result = spark.createDataFrame(rows, "column STRING, expected STRING, actual STRING, change STRING") \
                  .orderBy("column")

    # For the SQL version: the two column lists as views
    spark.createDataFrame(list(exp.items()), "column STRING, type STRING").createOrReplaceTempView("exp_cols")
    spark.createDataFrame(list(got.items()), "column STRING, type STRING").createOrReplaceTempView("got_cols")
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT coalesce(e.column, g.column) AS column, e.type AS expected, g.type AS actual,
           CASE WHEN g.column IS NULL THEN 'missing'
                WHEN e.column IS NULL THEN 'added'
                ELSE 'type changed' END AS change
    FROM exp_cols e
    FULL OUTER JOIN got_cols g ON e.column = g.column
    WHERE e.type IS DISTINCT FROM g.type
    ORDER BY column;
    ```

    Both versions were run in `t08_quality.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** `df.schema.fields` gives each column's name and type; `simpleString()` turns a type into
    text such as `decimal(10,2)`. Comparing two dictionaries finds the three kinds of change. The SQL version
    needs the column lists as tables (here two small views built from the dictionaries; on Databricks you would
    read `information_schema.columns` for tables in Unity Catalog), and a full outer join finds the differences.

    **Common mistakes:** comparing `df1.schema == df2.schema`, which only says "different", not how; and
    forgetting that nullability is part of a `StructField`, so two schemas with the same names and types can
    still compare unequal. Delta's schema enforcement and evolution decide what happens when such a batch is
    written ([4. Delta Lake](04-Delta-Lake.md)).

**Task 53. In a unit test, list the rows that differ between the expected and the actual gold output,
counting duplicates.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
expected_gold = spark.createDataFrame([
    (dt(2026, 3, 1).date(), D("308.90")), (dt(2026, 3, 2).date(), D("228.50")),
    (dt(2026, 3, 3).date(), D("347.95")), (dt(2026, 3, 4).date(), D("237.00")),
], "day DATE, revenue DECIMAL(20,2)")
actual_gold = spark.createDataFrame([
    (dt(2026, 3, 1).date(), D("308.90")), (dt(2026, 3, 2).date(), D("228.50")),
    (dt(2026, 3, 3).date(), D("318.00")), (dt(2026, 3, 4).date(), D("237.00")),
    (dt(2026, 3, 4).date(), D("237.00")),                                      # duplicated row
], "day DATE, revenue DECIMAL(20,2)")
expected_gold.createOrReplaceTempView("expected_gold")
actual_gold.createOrReplaceTempView("actual_gold")
```

Expected output:

```text
+----------+-------+-------------------+
|day       |revenue|side               |
+----------+-------+-------------------+
|2026-03-03|318.00 |extra in actual    |
|2026-03-03|347.95 |missing from actual|
|2026-03-04|237.00 |extra in actual    |
+----------+-------+-------------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    missing = expected_gold.exceptAll(actual_gold).withColumn("side", F.lit("missing from actual"))
    extra = actual_gold.exceptAll(expected_gold).withColumn("side", F.lit("extra in actual"))
    result = missing.unionByName(extra).orderBy("day", "side")
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT *, 'missing from actual' AS side FROM (SELECT * FROM expected_gold EXCEPT ALL SELECT * FROM actual_gold)
    UNION ALL
    SELECT *, 'extra in actual' AS side FROM (SELECT * FROM actual_gold EXCEPT ALL SELECT * FROM expected_gold)
    ORDER BY day, side;
    ```

    Both versions were run in `t08_quality.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** `exceptAll` returns the rows of the first DataFrame that are not in the second, keeping
    duplicates ([DataFrame.exceptAll](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.exceptAll.html)),
    like SQL `EXCEPT ALL`. Running it both ways finds missing rows and extra rows. An empty result means the two
    DataFrames hold the same multiset of rows.

    **Common mistakes:** `subtract` (SQL `EXCEPT`) removes duplicates, so it does not see the repeated March 4
    row:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    print("subtract (set semantics) finds:", actual_gold.subtract(expected_gold).count(), "row;",
          "exceptAll finds:", actual_gold.exceptAll(expected_gold).count(), "rows")
    ```

    ```text
    subtract (set semantics) finds: 1 row; exceptAll finds: 2 rows
    ```

    Chapter 16 shows how such checks become PySpark unit tests ([16. CI/CD and testing](16-CICD-and-Testing.md)).

**Task 54. Produce a one-row quality report for a batch of orders: rows, NULL keys, duplicate keys, orders for
unknown customers, and non-positive amounts. Stop the pipeline if any check fails.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
batch = orders.unionByName(spark.createDataFrame([
    (1005, 4, dt(2026, 3, 3, 8, 55), "SHIPPED", D("318.00"), "CAD"),    # duplicate key
    (1009, 9, dt(2026, 3, 5, 9, 0), "PLACED", D("15.00"), "CAD"),       # unknown customer
    (None, 2, dt(2026, 3, 5, 10, 0), "PLACED", D("20.00"), "USD"),      # NULL key
], orders.schema))
batch.createOrReplaceTempView("batch")
```

Expected output:

```text
+------+---------+--------------+-----------------+--------------------+
|n_rows|null_keys|duplicate_keys|unknown_customers|non_positive_amounts|
+------+---------+--------------+-----------------+--------------------+
|11    |1        |1             |1                |0                   |
+------+---------+--------------+-----------------+--------------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (batch.alias("b")
              .join(customers.alias("c"), F.col("b.customer_id") == F.col("c.customer_id"), "left")
              .agg(F.count("*").alias("n_rows"),
                   F.count_if(F.col("b.order_id").isNull()).alias("null_keys"),
                   (F.count("b.order_id") - F.countDistinct("b.order_id")).alias("duplicate_keys"),
                   F.count_if(F.col("c.customer_id").isNull()).alias("unknown_customers"),
                   F.count_if(F.col("b.amount") <= 0).alias("non_positive_amounts")))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT count(*)                                  AS n_rows,
           count_if(b.order_id IS NULL)              AS null_keys,
           count(b.order_id) - count(DISTINCT b.order_id) AS duplicate_keys,
           count_if(c.customer_id IS NULL)           AS unknown_customers,
           count_if(b.amount <= 0)                   AS non_positive_amounts
    FROM batch b
    LEFT JOIN customers c ON c.customer_id = b.customer_id;
    ```

    Both versions were run in `t08_quality.py`, which asserts that they return the same columns, column types and 1 rows. The output is the expected output above.

    **Why it works:** one left join and one aggregation compute every metric in a single job.
    `count(order_id) - countDistinct(order_id)` is the number of surplus rows for repeated keys (NULL keys excluded, since both
    functions skip NULLs). The report is a small DataFrame, so reading its one row on the driver is fine:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    report = result.first()
    problems = {k: v for k, v in report.asDict().items() if k != "n_rows" and v > 0}
    print("problems:", problems)
    # In a pipeline you would stop here: if problems: raise ValueError(f"quality check failed: {problems}")
    ```

    ```text
    problems: {'null_keys': 1, 'duplicate_keys': 1, 'unknown_customers': 1}
    ```

    **Common mistakes:** computing each metric with its own `count()` (five jobs instead of one); and joining to
    `customers` with an inner join, which removes exactly the rows the "unknown customer" check is looking for.

## 25.11 Delta Lake from PySpark

*Level: expert.*

These tasks write Delta tables, so each uses two copies of the same table: the PySpark version changes one, the
SQL version changes the other, and the script checks that both end up identical. On Databricks the tables would be
Unity Catalog tables such as `shop.silver.customers`; the `DeltaTable` Python API and the SQL statements are the
same there ([Upsert into a Delta Lake table using merge](https://docs.databricks.com/aws/en/delta/merge)).
Chapters 4 and 9 explain `MERGE`, time travel and SCD in depth ([4. Delta Lake](04-Delta-Lake.md),
[9. Building silver](09-Building-Silver.md)).

**Task 55. Upsert a batch of customer updates: update a customer only if the update is newer than the stored
row, insert new customers.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
for t in ["customers_py", "customers_sql"]:          # one table per version, same starting rows
    customers.write.format("delta").mode("overwrite").saveAsTable(t)

updates = spark.createDataFrame([
    (2, "Ben Okafor",   "ben@example.com",   "Boulder", "US", dt(2026, 3, 10, 9, 0)),  # moved
    (3, "Chloe Martin", "chloe@example.com", "Moab",    "US", dt(2025, 12, 1, 0, 0)),  # older: ignore
    (5, "Eve Tremblay", "eve@example.com",   "Banff",   "CA", dt(2026, 3, 2, 18, 0)),  # new
], customers.schema)
updates.createOrReplaceTempView("updates")
```

Expected output (the table after the merge):

```text
+-----------+------------+-----------------+---------+-------+-------------------+
|customer_id|name        |email            |city     |country|updated_at         |
+-----------+------------+-----------------+---------+-------+-------------------+
|1          |Ana Lopez   |ana@example.com  |Calgary  |CA     |2026-01-05 09:00:00|
|2          |Ben Okafor  |ben@example.com  |Boulder  |US     |2026-03-10 09:00:00|
|3          |Chloe Martin|chloe@example.com|Moab     |US     |2026-01-09 16:45:00|
|4          |Dev Patel   |dev@example.com  |Vancouver|CA     |2026-01-11 08:15:00|
|5          |Eve Tremblay|eve@example.com  |Banff    |CA     |2026-03-02 18:00:00|
+-----------+------------+-----------------+---------+-------+-------------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    from delta.tables import DeltaTable

    target = DeltaTable.forName(spark, "customers_py")
    (target.alias("t")
     .merge(updates.alias("s"), "t.customer_id = s.customer_id")
     .whenMatchedUpdateAll(condition="s.updated_at > t.updated_at")
     .whenNotMatchedInsertAll()
     .execute())
    result = spark.table("customers_py").orderBy("customer_id")
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    MERGE INTO customers_sql t
    USING updates s
    ON t.customer_id = s.customer_id
    WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *
    WHEN NOT MATCHED THEN INSERT *;

    SELECT * FROM customers_sql ORDER BY customer_id;
    ```

    Both versions were run in `t09_delta.py`, which asserts that they return the same columns, column types and 5 rows in the same order. The output is the expected output above.

    **Why it works:** `merge` matches source rows to target rows on the condition; `whenMatchedUpdateAll` with a
    condition updates only when it is true, and `whenNotMatchedInsertAll` inserts the rest. Ben moved to Boulder;
    Chloe's update is older than the stored row, so it is ignored; Eve is new. The history shows what happened:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    m = (spark.sql("DESCRIBE HISTORY customers_py").filter("operation = 'MERGE'")
         .select("version", "operationMetrics").first())
    print("version", m.version, {k: m.operationMetrics[k] for k in
          ["numSourceRows", "numTargetRowsUpdated", "numTargetRowsInserted", "numTargetRowsCopied"]})
    ```

    ```text
    version 1 {'numSourceRows': '3', 'numTargetRowsUpdated': '1', 'numTargetRowsInserted': '1', 'numTargetRowsCopied': '3'}
    ```

    **Common mistakes:** no `updated_at` guard, so a late, older update overwrites newer data; using `>=`, which
    rewrites identical rows on every rerun; and a source with two rows for one key, which fails the merge (Q24 in
    25.13). The Databricks page says to "preprocess the source table to eliminate the possibility of multiple
    matches" ([Upsert into a Delta Lake table using merge](https://docs.databricks.com/aws/en/delta/merge)).

**Task 56. Apply SCD Type 2 to a customer dimension: when a customer's attributes change, close the current row
(`valid_to`, `is_current = false`) and insert a new current row; insert new customers; leave unchanged customers
alone.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
for t in ["dim_customer_py", "dim_customer_sql"]:
    (customers.select("customer_id", "name", "city", "country",
                      F.col("updated_at").alias("valid_from"),
                      F.lit(None).cast("timestamp").alias("valid_to"),
                      F.lit(True).alias("is_current"))
     .write.format("delta").mode("overwrite").saveAsTable(t))

changes = spark.createDataFrame([
    (2, "Ben Okafor",   "Boulder",   "US", dt(2026, 3, 10, 9, 0)),   # city changed
    (4, "Dev Patel",    "Vancouver", "CA", dt(2026, 3, 10, 9, 0)),   # no change
    (5, "Eve Tremblay", "Banff",     "CA", dt(2026, 3, 2, 18, 0)),   # new customer
], "customer_id INT, name STRING, city STRING, country STRING, updated_at TIMESTAMP")
changes.createOrReplaceTempView("changes")
```

Expected output (the dimension after the merge):

```text
+-----------+------------+---------+-------+-------------------+-------------------+----------+
|customer_id|name        |city     |country|valid_from         |valid_to           |is_current|
+-----------+------------+---------+-------+-------------------+-------------------+----------+
|1          |Ana Lopez   |Calgary  |CA     |2026-01-05 09:00:00|NULL               |true      |
|2          |Ben Okafor  |Denver   |US     |2026-01-07 12:30:00|2026-03-10 09:00:00|false     |
|2          |Ben Okafor  |Boulder  |US     |2026-03-10 09:00:00|NULL               |true      |
|3          |Chloe Martin|Moab     |US     |2026-01-09 16:45:00|NULL               |true      |
|4          |Dev Patel   |Vancouver|CA     |2026-01-11 08:15:00|NULL               |true      |
|5          |Eve Tremblay|Banff    |CA     |2026-03-02 18:00:00|NULL               |true      |
+-----------+------------+---------+-------+-------------------+-------------------+----------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    from delta.tables import DeltaTable

    dim = DeltaTable.forName(spark, "dim_customer_py")
    same = "t.name <=> s.name AND t.city <=> s.city AND t.country <=> s.country"

    current = spark.table("dim_customer_py").filter("is_current")
    changed = (changes.alias("s")
               .join(current.alias("t"), F.col("s.customer_id") == F.col("t.customer_id"))
               .filter(f"NOT ({same})")
               .select("s.*"))
    # Rows with merge_key NULL never match, so they are inserted as the new version
    staged = (changes.withColumn("merge_key", F.col("customer_id"))
              .unionByName(changed.withColumn("merge_key", F.lit(None).cast("int"))))

    (dim.alias("t")
     .merge(staged.alias("s"), "t.customer_id = s.merge_key AND t.is_current")
     .whenMatchedUpdate(condition=f"NOT ({same})",
                        set={"valid_to": "s.updated_at", "is_current": "false"})
     .whenNotMatchedInsert(values={
         "customer_id": "s.customer_id", "name": "s.name", "city": "s.city", "country": "s.country",
         "valid_from": "s.updated_at", "valid_to": "NULL", "is_current": "true"})
     .execute())
    result = spark.table("dim_customer_py").orderBy("customer_id", "valid_from")
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    MERGE INTO dim_customer_sql t
    USING (
      SELECT c.customer_id AS merge_key, c.* FROM changes c
      UNION ALL
      SELECT NULL AS merge_key, c.*
      FROM changes c
      JOIN dim_customer_sql d ON d.customer_id = c.customer_id AND d.is_current
      WHERE NOT (d.name <=> c.name AND d.city <=> c.city AND d.country <=> c.country)
    ) s
    ON t.customer_id = s.merge_key AND t.is_current
    WHEN MATCHED AND NOT (t.name <=> s.name AND t.city <=> s.city AND t.country <=> s.country) THEN
      UPDATE SET valid_to = s.updated_at, is_current = false
    WHEN NOT MATCHED THEN
      INSERT (customer_id, name, city, country, valid_from, valid_to, is_current)
      VALUES (s.customer_id, s.name, s.city, s.country, s.updated_at, NULL, true);

    SELECT * FROM dim_customer_sql ORDER BY customer_id, valid_from;
    ```

    Both versions were run in `t09_delta.py`, which asserts that they return the same columns, column types and 6 rows in the same order. The output is the expected output above.

    **Why it works:** one `MERGE` must both update the old row and insert the new version of the same customer,
    but a source row can either match or not match. The trick, from the Delta Lake documentation, is to send the
    changed customers twice: once with `merge_key = customer_id`, which matches and closes the current row, and
    once with `merge_key = NULL`, which never matches and is inserted as the new version
    ([Delta Lake: Table deletes, updates, and merges](https://github.com/delta-io/delta/blob/master/docs/src/content/docs/delta-update.mdx)).
    New customers match nothing and are inserted; Dev is unchanged, so the update condition is false and nothing
    happens. `<=>` compares NULL attributes safely.

    **Common mistakes:** comparing attributes with `<>`, which treats a change from NULL to a value as "no
    change"; staging unchanged customers with `merge_key = NULL`, which inserts duplicate current rows; and not
    restricting the match to `is_current`, which would also update historical rows. Lakeflow pipelines
    ([formerly Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) can do SCD Type 2
    declaratively with `AUTO CDC` ([formerly `APPLY CHANGES`](https://docs.databricks.com/aws/en/ldp/cdc))
    ([14. Data quality and CDC](14-Data-Quality-and-CDC.md)); the generic SCD concepts are in the SQL course
    ([Data modelling](../../databases/sql/19-Data-Modelling.md)).

!!! tip "In the interview"
    **"How would you implement SCD Type 2 in PySpark?"** With one Delta `MERGE`: stage the changed rows
    twice, once keyed by the business key to close the current row and once with a NULL key so they are
    inserted as the new version; insert new keys; compare attributes NULL-safely and match only current
    rows. Then add: in a Delta Live Tables pipeline (now Lakeflow pipelines) I would use `APPLY CHANGES`
    (now `AUTO CDC`) with `STORED AS SCD TYPE 2` instead of writing the merge by hand.

**Task 57. A table was updated and then had a row deleted. Using time travel, show what changed since version 0.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
orders.write.format("delta").mode("overwrite").saveAsTable("orders_tt")             # version 0
spark.sql("UPDATE orders_tt SET status = 'SHIPPED' WHERE order_id = 1003")         # version 1
spark.sql("DELETE FROM orders_tt WHERE order_id = 1004")                            # version 2
```

Expected output:

```text
+--------+---------+------+------+
|order_id|status   |amount|change|
+--------+---------+------+------+
|1003    |PLACED   |189.50|before|
|1003    |SHIPPED  |189.50|after |
|1004    |CANCELLED|39.00 |before|
+--------+---------+------+------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    v0 = spark.read.option("versionAsOf", 0).table("orders_tt")
    now = spark.table("orders_tt")
    result = (v0.exceptAll(now).withColumn("change", F.lit("before"))
              .unionByName(now.exceptAll(v0).withColumn("change", F.lit("after")))
              .select("order_id", "status", "amount", "change")
              .orderBy("order_id", F.col("change").desc()))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, status, amount, change FROM (
      SELECT *, 'before' AS change FROM (SELECT * FROM orders_tt VERSION AS OF 0 EXCEPT ALL SELECT * FROM orders_tt)
      UNION ALL
      SELECT *, 'after' AS change FROM (SELECT * FROM orders_tt EXCEPT ALL SELECT * FROM orders_tt VERSION AS OF 0)
    )
    ORDER BY order_id, change DESC;
    ```

    Both versions were run in `t09_delta.py`, which asserts that they return the same columns, column types and 3 rows in the same order. The output is the expected output above.

    **Why it works:** every Delta commit creates a table version; reading with `versionAsOf` (SQL
    `VERSION AS OF`) returns the table as it was then
    ([Work with table history](https://docs.databricks.com/aws/en/delta/history)). `exceptAll` in both directions
    lists the old and new versions of changed rows. The history confirms the versions:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    spark.sql("DESCRIBE HISTORY orders_tt").select("version", "operation").orderBy("version").show(truncate=False)
    ```

    ```text
    +-------+---------------------------------+
    |version|operation                        |
    +-------+---------------------------------+
    |0      |CREATE OR REPLACE TABLE AS SELECT|
    |1      |UPDATE                           |
    |2      |DELETE                           |
    +-------+---------------------------------+
    ```

    **Common mistakes:** expecting time travel to work forever: `VACUUM` removes old data files and log
    retention limits how far back you can go (chapter 4); and using time travel as a change feed for a pipeline,
    which is what Change Data Feed is for ([9. Building silver](09-Building-Silver.md)).

**Task 58. A gold table holds revenue per day. Order 1006 turns out to be a test order; recompute March 3 and
replace only that day's rows, so that rerunning the job gives the same table.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
daily = (orders.groupBy(F.to_date("order_ts").alias("day"))
         .agg(F.sum("amount").alias("revenue")))
for t in ["gold_daily_py", "gold_daily_sql"]:
    daily.write.format("delta").mode("overwrite").saveAsTable(t)

# Order 1006 (March 3) turned out to be a test order: recompute March 3 without it
fixed = (orders.filter("order_id <> 1006 AND to_date(order_ts) = DATE'2026-03-03'")
         .groupBy(F.to_date("order_ts").alias("day"))
         .agg(F.sum("amount").alias("revenue")))
fixed.createOrReplaceTempView("fixed")
```

Expected output (the table after running the fix twice):

```text
+----------+-------+
|day       |revenue|
+----------+-------+
|2026-03-01|308.90 |
|2026-03-02|228.50 |
|2026-03-03|318.00 |
|2026-03-04|237.00 |
+----------+-------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    for attempt in range(2):                      # run twice: the second run changes nothing
        (fixed.write.format("delta")
         .mode("overwrite")
         .option("replaceWhere", "day = DATE'2026-03-03'")
         .saveAsTable("gold_daily_py"))
    result = spark.table("gold_daily_py").orderBy("day")
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    INSERT INTO gold_daily_sql REPLACE WHERE day = DATE'2026-03-03'
    SELECT * FROM fixed;

    INSERT INTO gold_daily_sql REPLACE WHERE day = DATE'2026-03-03'
    SELECT * FROM fixed;

    SELECT * FROM gold_daily_sql ORDER BY day;
    ```

    Both versions were run in `t09_delta.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** `mode("overwrite")` with `replaceWhere` atomically replaces only the rows that match the
    predicate (SQL `INSERT INTO ... REPLACE WHERE`), so the other days stay as they are and a rerun replaces March
    3 with the same row again ([Selectively overwrite data with Delta Lake](https://docs.databricks.com/aws/en/delta/selective-overwrite)).
    The write also checks that the new data matches the predicate:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    bad = spark.createDataFrame([(dt(2026, 3, 4).date(), D("1.00"))], "day DATE, revenue DECIMAL(20,2)")
    try:
        (bad.write.format("delta").mode("overwrite")
         .option("replaceWhere", "day = DATE'2026-03-03'").saveAsTable("gold_daily_py"))
    except Exception as e:
        print(type(e).__name__ + ":", str(e).split("\n")[0][:160])
    ```

    ```text
    AnalysisException: [DELTA_REPLACE_WHERE_MISMATCH] Written data does not conform to partial table overwrite condition or constraint 'day = DATE'2026-03-03''.
    ```

    **Common mistakes:** a plain `mode("overwrite")`, which replaces the whole table with one day; `append`, which
    adds a second March 3 row on every rerun; and on Databricks, not knowing the newer options: the same page
    lists `REPLACE USING` and `REPLACE ON` for dynamic overwrites, with their minimum runtime versions.

## 25.12 Performance-flavored tasks

*Level: expert.*

These tasks are about how, not what: the result is easy, and the interviewer wants the version that scales and an
explanation of why. Chapter 22 goes deeper into each topic ([22. Performance tuning](22-Performance-Tuning.md)).

**Task 59. A colleague wrote a Python UDF to bucket amounts. Rewrite it with built-in functions and show that the
results are the same.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql.types import StringType

@F.udf(returnType=StringType())
def size_udf(amount):                       # the colleague's version
    if amount is None:
        return None
    return "small" if amount < 50 else "medium" if amount < 200 else "large"
```

Expected output:

```text
+--------+------+------+
|order_id|amount|size  |
+--------+------+------+
|1001    |59.90 |medium|
|1002    |249.00|large |
|1003    |189.50|medium|
|1004    |39.00 |small |
|1005    |318.00|large |
|1006    |29.95 |small |
|1007    |159.00|medium|
|1008    |78.00 |medium|
+--------+------+------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    size_builtin = (F.when(F.col("amount") < 50, "small")
                     .when(F.col("amount") < 200, "medium")
                     .when(F.col("amount").isNotNull(), "large"))
    result = orders.select("order_id", "amount", size_builtin.alias("size")).orderBy("order_id")

    with_udf = orders.select("order_id", "amount", size_udf("amount").alias("size")).orderBy("order_id")
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, amount,
           CASE WHEN amount < 50 THEN 'small'
                WHEN amount < 200 THEN 'medium'
                WHEN amount IS NOT NULL THEN 'large' END AS size
    FROM orders
    ORDER BY order_id;
    ```

    Both versions were run in `t10_perf.py`, which asserts that they return the same columns, column types and 8 rows in the same order. The output is the expected output above.

    **Why it works:** built-in functions run inside the JVM as part of Spark's generated code. A Python UDF sends
    each batch of rows to a Python worker process and back, and the optimizer cannot look inside it. The script
    checked that the UDF and the built-in version return the same rows, and printed the Python step in each plan:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    def python_nodes(df):
        plan = df._jdf.queryExecution().executedPlan().toString()
        return [n for n in ["BatchEvalPython", "ArrowEvalPython"] if n in plan]
    print("UDF plan:     ", python_nodes(with_udf))
    print("built-in plan:", python_nodes(result))
    ```

    ```text
    UDF plan:      ['ArrowEvalPython']
    built-in plan: []
    ```

    `ArrowEvalPython` means the UDF ran with Arrow batches: in this engine
    `spark.sql.execution.pythonUDF.arrow.enabled` is `true` (Q29 in 25.13). Arrow makes the transfer cheaper but
    does not remove it. Databricks says built-in functions and SQL UDFs "are the most efficient options"
    ([What are user-defined functions (UDFs)?](https://docs.databricks.com/aws/en/udf/)).

    **Common mistakes:** keeping the UDF "because it is clearer"; and in the UDF, forgetting `None` (the
    built-in `when` chain returns NULL for a NULL amount without extra code, while the Python function would
    fail on `None < 50`).

**Task 60. A notebook computes customer totals by looping over `orders.collect()` in Python. Rewrite it so the
work stays on the cluster.**

Input: `orders`. Expected output:

```text
+-----------+------+
|customer_id|total |
+-----------+------+
|1          |327.40|
|2          |278.95|
|3          |198.00|
|4          |318.00|
+-----------+------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders.groupBy("customer_id")
              .agg(F.sum("amount").alias("total"))
              .orderBy("customer_id"))

    # The anti-pattern: every row travels to the driver, the loop runs in one Python process
    totals = {}
    for row in orders.collect():
        totals[row.customer_id] = totals.get(row.customer_id, 0) + row.amount
    from_driver = spark.createDataFrame(sorted(totals.items()), result.schema)
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id, sum(amount) AS total FROM orders GROUP BY customer_id ORDER BY customer_id;
    ```

    Both versions were run in `t10_perf.py`, which asserts that they return the same columns, column types and 4 rows in the same order. The output is the expected output above.

    **Why it works:** `groupBy` runs on the executors in parallel and returns only one row per customer. The loop
    brings every row to the driver; the API notes say `collect()` "should only be used if the resulting list is
    expected to be small, as all the data is loaded into the driver's memory"
    ([DataFrame.collect](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.collect.html)).
    The script checked that both give the same totals. For "is there any row?", use `isEmpty()` instead of
    `count() > 0`:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    big = orders.filter(F.col("amount") > 1000)
    print("any order over 1000?", not big.isEmpty())      # stops at the first row; count() reads everything
    ```

    ```text
    any order over 1000? False
    ```

    **Common mistakes:** `toPandas()` has the same problem as `collect()`; `count()` in a loop or before every
    write starts a full job each time; and `collect()` on a large table to "look at the data" instead of
    `show()` or `limit(20)`.

**Task 61. Write 20,000 orders as a Delta table partitioned by `order_date` (5 dates), with one file per date
instead of one file per date per task.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
import glob

many = spark.range(0, 20000, numPartitions=8).select(
    (F.col("id") + 100000).cast("int").alias("order_id"),
    F.date_add(F.lit("2026-03-01").cast("date"), (F.col("id") % 5).cast("int")).alias("order_date"),
    ((F.col("id") % 300) + 5).cast("decimal(10,2)").alias("amount"))
many.createOrReplaceTempView("many")

def files_per_date(path):
    files = glob.glob(f"{path}/order_date=*/*.parquet")
    return len(files) / len(glob.glob(f"{path}/order_date=*"))
```

Expected output (rows per date, read back from the written table):

```text
+----------+------+
|order_date|n_rows|
+----------+------+
|2026-03-01|4000  |
|2026-03-02|4000  |
|2026-03-03|4000  |
|2026-03-04|4000  |
|2026-03-05|4000  |
+----------+------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    # Without repartition: each of the 8 tasks writes a file into every date folder it has rows for
    many.write.format("delta").mode("overwrite").partitionBy("order_date").save(f"{WORK}/no_repart")

    # With repartition on the partition column: all rows of a date are in one task, so one file per date
    (many.repartition("order_date")
         .write.format("delta").mode("overwrite").partitionBy("order_date").save(f"{WORK}/repart"))

    result = (spark.read.format("delta").load(f"{WORK}/repart")
              .groupBy("order_date").agg(F.count("*").alias("n_rows"))
              .orderBy("order_date"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    CREATE TABLE many_sql USING DELTA PARTITIONED BY (order_date)
    AS SELECT * FROM many DISTRIBUTE BY order_date;

    SELECT order_date, count(*) AS n_rows FROM many_sql GROUP BY order_date ORDER BY order_date;
    ```

    Both versions were run in `t10_perf.py`, which asserts that they return the same columns, column types and 5 rows in the same order. The output is the expected output above.

    **Why it works:** with `partitionBy`, each task writes one file into every date folder it holds rows for. The
    input has 8 partitions, each with all 5 dates, so the plain write produces 8 files per date. `repartition(col)`
    (SQL `DISTRIBUTE BY`) first shuffles all rows of a date into the same task, so each date gets one file:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    sql_path = spark.sql("DESCRIBE DETAIL many_sql").first().location.replace("file:", "")
    print("files per date, no repartition:  ", files_per_date(f"{WORK}/no_repart"))
    print("files per date, repartition:     ", files_per_date(f"{WORK}/repart"))
    print("files per date, SQL DISTRIBUTE BY:", files_per_date(sql_path))
    ```

    ```text
    files per date, no repartition:   8.0
    files per date, repartition:      1.0
    files per date, SQL DISTRIBUTE BY: 1.0
    ```

    **Common mistakes:** `coalesce(1)` before the write: one file per date, but the whole write runs in a single
    task ([DataFrame.coalesce](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.coalesce.html)
    warns that a drastic coalesce "may result in your computation taking place on fewer nodes than you like");
    `repartition(col)` on a skewed column, which makes one huge task; and partitioning by a high-cardinality
    column at all. On Databricks, optimized writes do this shuffle for you. They are on by default for `MERGE`,
    `UPDATE` and `DELETE` with subqueries, for `CTAS` and `INSERT` on SQL warehouses, and, in Databricks Runtime
    13.3 LTS and above, for `CTAS` and `INSERT` into partitioned Unity Catalog tables, which is the case in this
    task. Databricks recommends not running `coalesce(n)` or
    `repartition(n)` just before a write when optimized writes are used
    ([Control data file size](https://docs.databricks.com/aws/en/tables/tune-file-size)).
    Partitioning versus liquid clustering is in chapter 22.

**Task 62. Add flag columns `is_placed`, `is_shipped` and `is_cancelled` (false for a NULL status). Then explain
why a loop of `withColumn` calls is a problem when there are many columns.**

Input: `orders`. Expected output:

```text
+--------+---------+---------+----------+------------+
|order_id|status   |is_placed|is_shipped|is_cancelled|
+--------+---------+---------+----------+------------+
|1001    |SHIPPED  |false    |true      |false       |
|1002    |SHIPPED  |false    |true      |false       |
|1003    |PLACED   |true     |false     |false       |
|1004    |CANCELLED|false    |false     |true        |
|1005    |SHIPPED  |false    |true      |false       |
|1006    |PLACED   |true     |false     |false       |
|1007    |SHIPPED  |false    |true      |false       |
|1008    |NULL     |false    |false     |false       |
+--------+---------+---------+----------+------------+
```

??? success "Solution"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    statuses = ["PLACED", "SHIPPED", "CANCELLED"]
    result = (orders
              .withColumns({f"is_{s.lower()}": F.col("status").eqNullSafe(s) for s in statuses})
              .select("order_id", "status", "is_placed", "is_shipped", "is_cancelled")
              .orderBy("order_id"))

    looped = orders
    for s in statuses:
        looped = looped.withColumn(f"is_{s.lower()}", F.col("status").eqNullSafe(s))
    looped = looped.select("order_id", "status", "is_placed", "is_shipped", "is_cancelled").orderBy("order_id")
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT order_id, status,
           status <=> 'PLACED'    AS is_placed,
           status <=> 'SHIPPED'   AS is_shipped,
           status <=> 'CANCELLED' AS is_cancelled
    FROM orders
    ORDER BY order_id;
    ```

    Both versions were run in `t10_perf.py`, which asserts that they return the same columns, column types and 8 rows in the same order. The output is the expected output above.

    **Why it works:** `withColumns` adds all columns in one projection, and `eqNullSafe` returns false (not
    NULL) for a NULL status. The loop gives the same rows (the script checked), but each `withColumn` "introduces
    a projection internally", and calling it in loops "can generate big plans which can cause performance issues
    and even StackOverflowException"
    ([DataFrame.withColumn](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.withColumn.html)).
    The script counted the projections in the plan:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    def projects(df):
        return df._jdf.queryExecution().logical().toString().count("Project [")
    loop100 = orders
    for i in range(100):
        loop100 = loop100.withColumn(f"c{i}", F.lit(i))
    once100 = orders.withColumns({f"c{i}": F.lit(i) for i in range(100)})
    print("Project nodes in the plan, 100 x withColumn:", projects(loop100))
    print("Project nodes in the plan, 1 x withColumns: ", projects(once100))
    ```

    ```text
    Project nodes in the plan, 100 x withColumn: 100
    Project nodes in the plan, 1 x withColumns:  1
    ```

    **Common mistakes:** the same applies to `withColumnRenamed` and `drop` in loops; use one `select` (or
    `withColumnsRenamed`) instead.

## 25.13 Practice questions

*Level: mixed.*

Short questions of the kind that follow a coding task: "what does this print", "find the bug", and "what would
you do if". Answers that show code were run in `t11_practice.py`; the others point to the task where the
behavior was shown.

**Q1. The task is "return the latest status of each order". What do you ask before writing any code?**

??? success "Answer"
    What "latest" is measured by (event time such as `updated_at`, or arrival time); what to do with ties (two
    events with the same time); whether NULL timestamps can occur and where they sort; whether exact duplicate
    rows exist; and whether the result is one row per order or the full history with a flag.

    **Why:** each answer changes the window ordering or the tie-breaker. Without a complete ordering,
    `row_number` picks among tied rows arbitrarily (Task 36).

**Q2. On the base `orders` table, what does `orders.filter(F.col("status") != "CANCELLED").count()` return, and
why is it not 7?**

??? success "Answer"
    6. Order 1008 has a NULL status, `NULL != 'CANCELLED'` is NULL, and `filter` keeps only rows where the
    condition is true. Use `~F.col("status").eqNullSafe("CANCELLED")` (SQL `IS DISTINCT FROM`) to get 7
    (Task 6).

    **Why:** comparisons with NULL return NULL in SQL logic, and PySpark column expressions follow the same rules.

**Q3. What does `F.split(F.lit("a.b.c"), ".")` return?**

??? success "Answer"
    An array of six empty strings, as Task 5 showed. The pattern is a regular expression, and `.` matches every
    character, so every character is a separator. Use `"[.]"` or `"\\."`.

    **Why:** `split` takes a Java regular expression, not a literal string.

**Q4. Find the bug: `orders.filter(F.col("status") == "SHIPPED" & F.col("amount") >= 100)`.**

??? success "Answer"
    Python's `&` binds more tightly than `==` and `>=`, so the condition is not grouped as intended, and Python
    then needs the truth value of a column, which PySpark refuses. Using `and` fails the same way:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    for label, make in [
        ("no parentheses", lambda: orders.filter(F.col("status") == "SHIPPED" & F.col("amount") >= 100)),
        ("python and",     lambda: orders.filter((F.col("status") == "SHIPPED") and (F.col("amount") >= 100))),
    ]:
        try:
            make().count()
        except Exception as e:
            print(f"{label}: {type(e).__name__}: {str(e).splitlines()[0][:110]}")
    ```

    ```text
    no parentheses: PySparkValueError: [CANNOT_CONVERT_COLUMN_INTO_BOOL] Cannot convert column into bool: please use '&' for 'and', '|' for 'or', '~'
    python and: PySparkValueError: [CANNOT_CONVERT_COLUMN_INTO_BOOL] Cannot convert column into bool: please use '&' for 'and', '|' for 'or', '~'
    ```

    Fix: `(F.col("status") == "SHIPPED") & (F.col("amount") >= 100)`.

    **Why:** the error is raised in Python before Spark sees the query; the message tells you to use `&`, `|`
    and `~`, but the real fix here is the parentheses.

**Q5. Find the bug: `orders.join(customers, orders.customer_id == customers.customer_id).select("customer_id")`.**

??? success "Answer"
    Both inputs have a `customer_id` column, and a join on an expression keeps both, so the name is ambiguous:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    try:
        orders.join(customers, orders.customer_id == customers.customer_id).select("customer_id").collect()
    except Exception as e:
        print(str(e).split(".")[0])
    print(orders.join(customers, "customer_id").select("customer_id").count(), "rows with on='customer_id'")
    ```

    ```text
    [AMBIGUOUS_REFERENCE] Reference `customer_id` is ambiguous, could be: [`customer_id`, `customer_id`]
    8 rows with on='customer_id'
    ```

    Fix: join with `on="customer_id"` (one key column survives), or select `orders.customer_id` explicitly, or
    use aliases as in Task 16.

    **Why:** an expression join can compare columns with different names, so Spark cannot merge the two keys;
    a join on column names can, like SQL `USING`.

**Q6. What are the column names of `orders.groupBy("customer_id").agg(F.sum("amount"))`?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    print(orders.groupBy("customer_id").agg(F.sum("amount")).columns)
    ```

    ```text
    ['customer_id', 'sum(amount)']
    ```

    **Why:** without an alias, the column is named after the expression. A name with parentheses is awkward to
    reference later (`F.col("sum(amount)")`), so always `alias` aggregates.

**Q7. Write PySpark and SQL that return the customers whose every order is `SHIPPED`. An order without a status
does not count as shipped.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    result = (orders.groupBy("customer_id")
              .agg(F.every(F.coalesce(F.col("status") == "SHIPPED", F.lit(False))).alias("all_shipped"))
              .filter("all_shipped")
              .select("customer_id"))
    ```

    Databricks SQL equivalent:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id
    FROM orders
    GROUP BY customer_id
    HAVING every(coalesce(status = 'SHIPPED', false));
    ```

    Both versions were run in `t11_practice.py`, which asserts that they return the same columns, column types and 1 rows in the same order. The output is the expected output above.

    Result: customer 4 only.

    **Why:** `every` (alias `bool_and`) is true when the condition is true for all rows of the group. The
    condition is NULL for a NULL status, and aggregate functions skip NULLs, so without `coalesce(..., false)`
    a customer whose only other order has no status could pass. Here customer 1 fails anyway because of order
    1003, but the guard is what the task statement asks for.

**Q8. What does `F.when(F.col("amount") > 100, "big")` return for an order of 59.90?**

??? success "Answer"
    NULL:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    orders.select("order_id", "amount",
                  F.when(F.col("amount") > 100, "big").alias("size")).filter("order_id <= 1003").show()
    ```

    ```text
    +--------+------+----+
    |order_id|amount|size|
    +--------+------+----+
    |    1001| 59.90|NULL|
    |    1002|249.00| big|
    |    1003|189.50| big|
    +--------+------+----+
    ```

    **Why:** a `when` chain without `otherwise` is a `CASE` without `ELSE`, which returns NULL when no branch
    matches.

**Q9. Column `a` is 10 and column `b` is NULL. What is `F.col("a") + F.col("b")`?**

??? success "Answer"
    NULL. Wrap the nullable side in `coalesce`:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    spark.createDataFrame([(10, None)], "a INT, b INT").select(
        (F.col("a") + F.col("b")).alias("a_plus_b"),
        (F.col("a") + F.coalesce("b", F.lit(0))).alias("with_coalesce")).show()
    ```

    ```text
    +--------+-------------+
    |a_plus_b|with_coalesce|
    +--------+-------------+
    |    NULL|           10|
    +--------+-------------+
    ```

    **Why:** arithmetic with NULL gives NULL. Aggregates are different: `sum` skips NULLs (Task 17).

**Q10. What is the difference between `union` and `unionByName`, and which should a pipeline use?**

??? success "Answer"
    `union` matches columns by position, `unionByName` by name. With `union`, two DataFrames whose columns are in
    different orders are combined silently and wrongly if the types are compatible (the cheat sheet in 25.1 put
    country codes into `city`). Pipelines should use `unionByName`, with `allowMissingColumns=True` when one side
    may lack a column.

    **Why:** column order changes easily (a `select` rewritten, a schema evolved), and positional matching hides
    the change instead of failing.

**Q11. After a release, the revenue per product doubled for one product only. Nothing failed. What is your first
suspicion, and how do you confirm it?**

??? success "Answer"
    A duplicate key on the lookup side of a join, for example a product that now has two rows in a price or
    product table. Confirm with `df.groupBy("product_id").count().filter("count > 1")`, then fix by making the key
    unique (latest row per key) or joining on the validity period (Task 21).

    **Why:** a join returns one row per matching pair, so two matching rows on the right double every left row.

**Q12. When do you use `left_semi` instead of an inner join, and `left_anti` instead of `NOT IN`?**

??? success "Answer"
    `left_semi` when you only need to know that a match exists: it returns each left row once and only the left
    columns, while an inner join repeats the row per match (Task 20). `left_anti` (or `NOT EXISTS`) instead of
    `NOT IN` because `NOT IN` returns no rows at all when the subquery contains a NULL (Task 18).

    **Why:** both are about semantics, not speed: duplicates from an inner join and the three-valued logic of
    `NOT IN` give wrong answers silently.

**Q13. After `customers.join(orders, "customer_id", "left")`, how many orders does
`groupBy("customer_id").agg(F.count("*"))` report for a customer with no orders?**

??? success "Answer"
    1, because the left join produced one row for that customer (with NULL order columns). `F.count("order_id")`
    reports 0 (Task 17).

    **Why:** `count("*")` counts rows; `count(col)` counts non-NULL values.

**Q14. Units sold are 3, 3, 3, 1, 1 for five products. What do `row_number`, `rank` and `dense_rank` return
(ordered by units descending)?**

??? success "Answer"
    `row_number`: 1, 2, 3, 4, 5. `rank`: 1, 1, 1, 4, 4. `dense_rank`: 1, 1, 1, 2, 2 (Task 27).

    **Why:** `rank` leaves gaps after ties (the next rank is the number of rows before it plus one);
    `dense_rank` does not; `row_number` never ties.

**Q15. Find the bug: a column called `customer_total` is computed as
`F.sum("amount").over(Window.partitionBy("customer_id").orderBy("order_ts"))`.**

??? success "Answer"
    With an `orderBy` and no frame, the window frame is from the start of the partition to the current row, so
    this is a running total, not the customer total. Remove the `orderBy` (Task 32), or set
    `rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)`.

    **Why:** the default frame depends on whether the window is ordered (Task 28).

**Q16. What happens with `F.lag("amount").over(Window.partitionBy("customer_id"))`?**

??? success "Answer"
    The query fails:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    try:
        orders.withColumn("prev", F.lag("amount").over(Window.partitionBy("customer_id"))).collect()
    except Exception as e:
        print(str(e).split(".")[0])
    ```

    ```text
    [WINDOW_FUNCTION_FRAME_NOT_ORDERED] Window function lag requires the window to be ordered
    ```

    **Why:** "previous row" only means something in an order. Ranking functions (`row_number`, `rank`) need an
    order for the same reason.

**Q17. When does `rowsBetween(-2, 0)` give a different moving average from `rangeBetween(-2, 0)` on a date
number?**

??? success "Answer"
    When days are missing (or a day has several rows). The row frame always takes the two previous rows; the
    range frame takes rows whose day is within two days. In Task 31, with March 3 missing, the March 4 averages
    were 258.13 and 232.75.

    **Why:** `ROWS` counts rows, `RANGE` compares values of the ordering column.

**Q18. A colleague deduplicates order events with `events.dropDuplicates(["order_id"])` to keep the latest
status. What do you tell them?**

??? success "Answer"
    That `dropDuplicates` keeps one row per key, but nothing says which one; in Task 36 it kept the old `PLACED`
    status of order 1001. Use `row_number()` over `partitionBy("order_id").orderBy(updated_at desc, tie-breaker)`
    and keep row 1, or `max_by` with a struct.

    **Why:** "latest" is an ordering requirement, and `dropDuplicates` takes no ordering.

**Q19. What do `datediff(DATE'2026-03-04', DATE'2026-03-01')` and the swapped call return?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    spark.range(1).select(
        F.datediff(F.lit("2026-03-04").cast("date"), F.lit("2026-03-01").cast("date")).alias("end_first"),
        F.datediff(F.lit("2026-03-01").cast("date"), F.lit("2026-03-04").cast("date")).alias("start_first")).show()
    ```

    ```text
    +---------+-----------+
    |end_first|start_first|
    +---------+-----------+
    |        3|         -3|
    +---------+-----------+
    ```

    **Why:** `datediff(end, start)` returns end minus start in days; the end date comes first.

**Q20. What is the difference between `explode`, `explode_outer` and `posexplode`?**

??? success "Answer"
    `explode` returns one row per array element and no row for an empty or NULL array; `explode_outer` returns
    one row with NULL for those; `posexplode` (and `posexplode_outer`) also returns the element's position,
    starting at 0 (Task 40).

    **Why:** the difference matters when an order with no items must still be counted.

**Q21. `from_json` parses `'{"order_id": 1002, "amount": 249.00'` (a missing brace) with the schema
`order_id INT, amount DECIMAL(10,2)`. What comes back?**

??? success "Answer"
    A struct whose fields are all NULL, not a NULL struct (Task 41). Add a `_corrupt_record STRING` field to the
    schema and the `columnNameOfCorruptRecord` option to capture the raw text and detect the row.

    **Why:** in `PERMISSIVE` mode malformed fields are set to NULL rather than failing the query, so a test for
    `j IS NULL` misses them.

**Q22. Why give an explicit schema when reading JSON in a pipeline?**

??? success "Answer"
    Inference costs an extra pass over the data, can change when a new file arrives, and reads quoted numbers and
    timestamps as strings (Task 38 showed `amount` and `order_ts` inferred as `string`). An explicit schema reads
    in one pass and converts types as it reads.

    **Why:** silver needs stable types; on Databricks, Auto Loader adds schema tracking and evolution on top of
    this ([8. Into bronze](08-Bronze-Ingestion.md)).

**Q23. Find the bug: `F.aggregate("items", F.lit(0), lambda acc, x: acc + x["qty"] * x["unit_price"])`.**

??? success "Answer"
    The start value is an INT, while the merge returns a wider DECIMAL, and `aggregate` requires both to have
    the same type, so analysis fails with `DATATYPE_MISMATCH`. Start from `F.lit(0).cast("decimal(10,2)")` and
    cast the merge result to the same type (Task 43).

    **Why:** decimal multiplication widens precision; the accumulator's type must stay fixed through the fold.

**Q24. A `MERGE` into the customers table fails with "multiple source rows matched". Show the error and the fix.**

??? success "Answer"
    The source has two rows for customer 2. Deduplicate the source to one row per key (the latest), then merge:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    from delta.tables import DeltaTable
    customers.write.format("delta").mode("overwrite").saveAsTable("cust_q")
    src = spark.createDataFrame([
        (2, "Ben Okafor", "ben@example.com", "Boulder", "US", dt(2026, 3, 10, 9, 0)),
        (2, "Ben Okafor", "ben@example.com", "Golden",  "US", dt(2026, 3, 11, 9, 0)),
    ], customers.schema)
    try:
        (DeltaTable.forName(spark, "cust_q").alias("t")
         .merge(src.alias("s"), "t.customer_id = s.customer_id")
         .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    except Exception as e:
        print(str(e).split(".")[0])

    latest = src.withColumn("rn", F.row_number().over(
        Window.partitionBy("customer_id").orderBy(F.col("updated_at").desc()))).filter("rn = 1").drop("rn")
    (DeltaTable.forName(spark, "cust_q").alias("t")
     .merge(latest.alias("s"), "t.customer_id = s.customer_id")
     .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    spark.table("cust_q").filter("customer_id = 2").select("customer_id", "city").show()
    ```

    ```text
    [DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE] Cannot perform Merge as multiple source rows matched and attempted to modify the same
    target row in the Delta table in possibly conflicting ways
    +-----------+------+
    |customer_id|  city|
    +-----------+------+
    |          2|Golden|
    +-----------+------+
    ```

    **Why:** with two source rows for one target row, the update is ambiguous; Databricks documents this and
    says to "preprocess the source table to eliminate the possibility of multiple matches"
    ([Upsert into a Delta Lake table using merge](https://docs.databricks.com/aws/en/delta/merge)).

**Q25. In Task 55 the merge updates only `WHEN MATCHED AND s.updated_at > t.updated_at`. Why `>` and not `>=`?**

??? success "Answer"
    With `>=`, rerunning the same batch matches rows whose timestamps are equal and rewrites them, creating new
    data files and a new table version for no change. With `>`, a rerun updates nothing, and an older late event
    cannot overwrite a newer row.

    **Why:** idempotent reruns are a standard interview topic; chapter 9 shows the same guard in a silver
    pipeline ([9. Building silver](09-Building-Silver.md)).

**Q26. A daily job recomputes yesterday's gold rows. Compare `append`, `overwrite` and `overwrite` with
`replaceWhere` for reruns.**

??? success "Answer"
    `append` adds a second copy of the day on each rerun; `overwrite` replaces the whole table with one day;
    `overwrite` with `replaceWhere "day = ..."` replaces only that day, atomically, and checks that the new rows
    match the predicate (Task 58).

    **Why:** a rerun must leave the table in the same state as one run.

**Q27. When is a Python UDF acceptable?**

??? success "Answer"
    When no built-in function or combination of them can express the logic, for example calling a Python
    library. Otherwise built-ins are faster, because the data stays in the JVM and the optimizer understands
    them (Task 59). If you need Python, a pandas UDF processes batches of rows at once
    ([What are user-defined functions (UDFs)?](https://docs.databricks.com/aws/en/udf/)).

    **Why:** each Python UDF call moves rows between the JVM and a Python worker process.

**Q28. Why is `collect()` dangerous, and what do you use instead to test "is this DataFrame empty"?**

??? success "Answer"
    `collect()` loads every row into the driver's memory, which fails or slows down on large data (Task 60).
    For emptiness use `df.isEmpty()`; for a look at the data, `show()` or `limit(n)`.

    **Why:** the driver is a single machine; the data belongs on the executors.

**Q29. In this engine, what is `spark.sql.execution.pythonUDF.arrow.enabled`, and what does it change?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    print("spark.sql.execution.pythonUDF.arrow.enabled =",
          spark.conf.get("spark.sql.execution.pythonUDF.arrow.enabled"))
    ```

    ```text
    spark.sql.execution.pythonUDF.arrow.enabled = true
    ```

    When it is true, regular Python UDFs exchange data with the Python worker in Arrow batches (the plan shows
    `ArrowEvalPython` instead of `BatchEvalPython`, Task 59)
    ([pyspark.sql.functions.udf](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.udf.html)).
    The default on Databricks was not verified for this book; check it with `spark.conf.get` on your cluster.

    **Why:** Arrow lowers the serialization cost, but the rows still leave the JVM.

**Q30. `repartition(1)` or `coalesce(1)` before writing a single file: which, and what is the catch?**

??? success "Answer"
    `coalesce(1)` avoids a shuffle but can pull the whole upstream computation into one task; `repartition(1)`
    adds a shuffle but keeps the upstream stages parallel
    ([DataFrame.coalesce](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.coalesce.html)).
    The catch for both: one task writes all the data. On Databricks, when optimized writes are on, Databricks
    recommends not running `coalesce(n)` or `repartition(n)` just before a write (Task 61).

    **Why:** `coalesce` is a narrow dependency, so the stage before it runs with the reduced number of tasks.

**Q31. What do `countDistinct("a", "b")` and `countDistinct(struct("a", "b"))` return for the rows (1, 'x'),
(1, NULL), (2, 'y')?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    pairs = spark.createDataFrame([(1, "x"), (1, None), (2, "y")], "a INT, b STRING")
    pairs.select(F.countDistinct("a", "b").alias("distinct_pairs"),
                 F.countDistinct(F.struct("a", "b")).alias("distinct_structs")).show()
    ```

    ```text
    +--------------+----------------+
    |distinct_pairs|distinct_structs|
    +--------------+----------------+
    |             2|               3|
    +--------------+----------------+
    ```

    **Why:** with several columns, a row where any column is NULL is not counted; a struct with a NULL field is
    itself not NULL, so it is counted (Task 35).

**Q32. In a sessionization task with a 30-minute gap, two events are exactly 30 minutes apart. Same session or
not?**

??? success "Answer"
    It depends on the definition, so ask. With "more than 30 minutes starts a new session", they are in the same
    session (Task 47). Spark's `session_window` grouped them into one session too in the run. Write the rule
    with `>` or `>=` deliberately and test the boundary.

    **Why:** boundary cases are where interviewers check that you test, not just write.

**Q33. Why is `pivot("category")` slower than `pivot("category", ["Apparel", "Camping", "Hiking"])`?**

??? success "Answer"
    Without the list, Spark must first run a job to find the distinct values, to know the output columns; with
    the list it skips that job (Task 12). The list also keeps the output schema stable when a new category
    appears.

    **Why:** the result schema has to be known before the query runs.

**Q34. The daily revenue chart has gaps: days without orders do not appear. Fix it.**

??? success "Answer"
    Build a calendar of all days with `sequence` and `explode`, left join the daily totals to it, and fill the
    missing totals with 0 (Task 46).

    **Why:** `groupBy` can only produce groups that exist in the data.

## Sources

Databricks documentation:

- [ANSI compliance in Databricks Runtime](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-ansi-compliance) (last updated Sep 11, 2026)
- [PIVOT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-pivot) (last updated Sep 11, 2026)
- [UNPIVOT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-unpivot) (last updated Sep 11, 2026)
- [collect_list aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/collect_list) (last updated Sep 11, 2026)
- [sequence function](https://docs.databricks.com/aws/en/sql/language-manual/functions/sequence) (last updated Sep 11, 2026)
- [Upsert into a Delta Lake table using merge](https://docs.databricks.com/aws/en/delta/merge) (last updated Sep 11, 2026)
- [Work with table history](https://docs.databricks.com/aws/en/delta/history) (last updated Nov 6, 2026)
- [Selectively overwrite data with Delta Lake](https://docs.databricks.com/aws/en/delta/selective-overwrite) (last updated Sep 11, 2026)
- [Control data file size](https://docs.databricks.com/aws/en/tables/tune-file-size) (last updated Sep 11, 2026)
- [What are user-defined functions (UDFs)?](https://docs.databricks.com/aws/en/udf/) (last updated Sep 22, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc) (last updated Nov 9, 2026)

Apache Spark documentation (spark.apache.org; these pages show no last-updated date; read Nov 11, 2026):

- [DataFrame.join](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.join.html)
- [DataFrame.union](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.union.html)
  and [DataFrame.unionByName](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.unionByName.html)
- [DataFrame.unpivot](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.unpivot.html)
- [DataFrame.exceptAll](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.exceptAll.html)
- [DataFrame.dropDuplicates](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.dropDuplicates.html)
- [DataFrame.collect](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.collect.html)
- [DataFrame.coalesce](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.coalesce.html)
- [DataFrame.withColumn](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.withColumn.html)
- [Column.try_cast](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.Column.try_cast.html)
- [GroupedData.pivot](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.GroupedData.pivot.html)
- [Window](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.Window.html)
- [functions.from_json](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.from_json.html),
  [functions.posexplode_outer](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.posexplode_outer.html),
  [functions.aggregate](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.aggregate.html),
  [functions.session_window](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.session_window.html),
  [functions.udf](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.udf.html)
- [Generic Load/Save Functions](https://spark.apache.org/docs/latest/sql-data-sources-load-save-functions.html) (save modes)
- [JSON Files](https://spark.apache.org/docs/latest/sql-data-sources-json.html) (`mode`, `columnNameOfCorruptRecord`)
- [Performance Tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html) (broadcast threshold and join hints)

Delta Lake documentation:

- [Delta Lake: Table deletes, updates, and merges](https://github.com/delta-io/delta/blob/master/docs/src/content/docs/delta-update.mdx)
  (documentation source on GitHub, SCD Type 2 example with a merge key; no date shown; read Nov 11, 2026)
