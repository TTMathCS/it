# 10. Building gold

*Silver tells you what is true about each order and each customer; gold answers the questions the business actually
asks: how much did we sell yesterday, in which category, to which kind of customer. This chapter builds the Red Rock
Supply gold layer from the silver tables of chapter 9: a star schema with dimensions and surrogate keys, a fact table
at a declared grain, an aggregate table, and the incremental loads that keep them right when silver changes. It then
covers the Databricks-only serving side (materialized views, metric views, SQL warehouses, sharing) and how to test
gold. Interviewers use gold to check whether you can model data, not only move it: expect "what is the grain?",
"star schema or one big table?" and "how do you restate yesterday's numbers?".*

!!! abstract "In this chapter"
    **You will learn:**

    - what gold is for: tables for BI, ML features and data products, and what Databricks says belongs there
    - dimensional modelling on the lakehouse: facts, dimensions, conformed dimensions, informational keys
    - how to choose and declare the grain of a fact table, and the fan-out bug that breaks it
    - surrogate keys with identity columns versus hashes, the unknown member, and SCD Type 1 and Type 2 in dimensions
    - a fact table with a point-in-time join to an SCD Type 2 dimension, in SQL and PySpark
    - aggregate tables, additive and non-additive measures, and star schema versus one big table
    - incremental gold: full rebuild, `MERGE`, `INSERT ... REPLACE WHERE` to restate a day, and time travel to show the
      old number
    - materialized views and `REPLACE WHERE` flows on Databricks, and how they refresh
    - Unity Catalog metric views (the semantic layer), run here on open-source Spark 4.2
    - serving gold: SQL warehouses, Photon, liquid clustering, `RELY` constraints, OpenSharing and feature tables
    - testing gold: grain, keys and reconciliation with silver

    **You need:** [7. The medallion architecture](07-Medallion-Architecture.md) and
    [9. Building silver](09-Building-Silver.md) (its silver tables are the input here, including the SCD Type 2
    customers). [4. Delta Lake](04-Delta-Lake.md) for `MERGE` and time travel. The generic theory of star schemas and
    slowly changing dimensions is in the SQL course:
    [Data modelling](../../databases/sql/19-Data-Modelling.md).

    **Levels:** sections 10.1 to 10.3 beginner, 10.4 to 10.6 and 10.8 to 10.11 intermediate, 10.7 and 10.12 expert.

## 10.1 What gold is for

*Level: beginner.*

Silver holds one validated row per business record: every order, every order line, every version of every customer.
That is the right shape for correctness and the wrong shape for a dashboard. A revenue chart over silver must join
four tables, filter cancelled orders, pick the right customer version and aggregate, every time someone opens it.
Each analyst writes that query slightly differently, so two dashboards disagree about yesterday's revenue.

Gold fixes both problems. It holds tables shaped for the questions people ask, built once by the data team, with the
business rules (what counts as revenue, which currency, which customer version) decided in one place. The Databricks
medallion page describes the gold layer as "highly refined views of the data that drive downstream analytics,
dashboards, ML, and applications", and lists three properties: it "consists of aggregated data tailored for
analytics and reporting", "aligns with business logic and requirements", and "is optimized for performance in queries
and dashboards" ([medallion architecture](https://docs.databricks.com/aws/en/lakehouse/medallion)). The same page
names the method: gold "is where you'll model your data for reporting and analytics using a dimensional model by
establishing relationships and defining measures".

Gold has several kinds of reader, and each wants a slightly different table:

| Reader | What they need from gold | Typical table |
| --- | --- | --- |
| BI dashboards and analysts | fast, consistent answers; names a business user understands | star schema, aggregate tables, metric views |
| Data scientists and ML | one row per entity (customer, product) with features, correct as of a point in time | feature tables keyed by entity |
| Other teams or partners | a stable, documented contract they can rely on | a data product: a set of gold tables shared with OpenSharing (formerly Delta Sharing) |
| Applications | low-latency lookups of a precomputed value | a small aggregate or serving table |

The medallion page also notes that, because gold models a business domain, "some customers create multiple gold
layers to meet different business needs, such as HR, finance, and IT". For Red Rock Supply, one sales domain is
enough: `shop.gold` holds the star schema and its aggregates.

!!! tip "In the interview"
    **"What goes in gold that does not go in silver?"** Business-level tables: a dimensional model (facts and
    dimensions), aggregates such as daily sales, and the business definitions of measures like revenue. Silver keeps
    one validated, non-aggregated row per record and is the source of truth; gold is derived from it and can always
    be rebuilt from it. If a rule is about correctness of a record, it belongs in silver; if it is about how the
    business counts, it belongs in gold.

## 10.2 Dimensional modelling on the lakehouse

*Level: beginner.*

A **dimensional model** splits data into two kinds of table. A **fact table** records business events with numbers
you add up (the **measures**: quantity, amount). A **dimension table** describes the context of those events (who,
what, when, where) with attributes you filter and group by (city, category, day of week). A **star schema** is one
fact table with its dimensions around it, joined by keys; a **snowflake schema** normalizes the dimensions further
(a product dimension pointing to a separate category table). The generic theory, including fact table types and
slowly changing dimensions, is in the SQL course chapter
[Data modelling](../../databases/sql/19-Data-Modelling.md); this chapter covers what changes on Databricks.

Four Databricks facts shape the model, all from the page
[Data modeling](https://docs.databricks.com/aws/en/transform/data-modeling):

1. **Prefer star or snowflake to 3NF.** Databricks "recommends against using a heavily normalized model such as third
   normal form (3NF)" for a new lakehouse. Star and snowflake schemas "perform well on Databricks, as there are fewer
   joins present in standard queries and fewer keys to keep in sync", and "having more data fields in a single table
   allows the query optimizer to skip large amounts of data using file-level statistics".
2. **Keys are informational.** "Primary and foreign keys are informational and not enforced." Nothing stops a fact
   row from pointing at a customer key that does not exist; your pipeline and your tests (section 10.12) must.
3. **Transactions are per table by default.** "By default, Databricks scopes transactions to individual tables", so
   loading a dimension and then a fact is two transactions, and "downstream queries need to be tolerant of state
   mismatch due to failed or delayed transactions". The same page says tables with catalog commits enabled can take
   part in multi-statement, multi-table transactions; this chapter does not use them.
4. **Filters on a dimension may not skip fact data.** The optimizer "can also fail to skip records in a table when
   filter parameters are on a field in another table, which can result in a full table scan". This is one argument
   for copying the most-filtered attributes (often the date) onto the fact table.

The Red Rock Supply star schema built in this chapter:

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Silver tables orders, order_items, customers and products feed a gold star schema: fact_order_lines in the middle joined to dim_date, dim_customer and dim_product, with a daily_sales aggregate built from the fact">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="20" y="35" width="150" height="40" rx="5"/>
<rect x="20" y="90" width="150" height="40" rx="5"/>
<rect x="20" y="145" width="150" height="40" rx="5"/>
<rect x="20" y="200" width="150" height="40" rx="5"/>
<rect x="365" y="35" width="130" height="44" rx="5"/>
<rect x="226" y="120" width="124" height="52" rx="5"/>
<rect x="360" y="114" width="140" height="64" rx="5" stroke-width="2.5"/>
<rect x="514" y="120" width="116" height="52" rx="5"/>
<rect x="360" y="226" width="140" height="50" rx="5" stroke-dasharray="5 4"/>
<line x1="430" y1="114" x2="430" y2="79"/>
<line x1="360" y1="146" x2="350" y2="146"/>
<line x1="500" y1="146" x2="514" y2="146"/>
<line x1="430" y1="178" x2="430" y2="218"/>
<line x1="174" y1="146" x2="216" y2="146"/>
</g>
<g fill="currentColor">
<polygon points="430,226 425,216 435,216"/>
<polygon points="225,146 215,141 215,151"/>
</g>
<g fill="currentColor" font-size="14" text-anchor="middle">
<text x="95" y="24">silver</text>
<text x="430" y="24">gold</text>
<text x="95" y="60">orders</text>
<text x="95" y="115">order_items</text>
<text x="95" y="170">customers (SCD 2)</text>
<text x="95" y="225">products</text>
<text x="430" y="55">dim_date</text>
<text x="288" y="142">dim_customer</text>
<text x="430" y="137">fact_order_lines</text>
<text x="572" y="142">dim_product</text>
<text x="430" y="247">daily_sales</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="195" y="136">build</text>
<text x="430" y="71">date_key</text>
<text x="288" y="160">SCD 2, hash key</text>
<text x="430" y="155">one row per</text>
<text x="430" y="170">order line</text>
<text x="572" y="160">SCD 1, identity</text>
<text x="430" y="265">day x currency</text>
</g>
</svg>
<figcaption>Figure 10.1. From silver to a gold star schema. The fact table sits in the middle at the grain of one order
line; each dimension gives it context; the dashed box is an aggregate built from the fact, not from silver.</figcaption>
</figure>

A **conformed dimension** is one dimension shared by several fact tables, with the same keys and the same meaning.
If Red Rock Supply later adds a `fact_returns` table, it must use the same `dim_customer` and `dim_date`, so that
"revenue minus returns by city" joins two facts through shared dimensions instead of comparing two different ideas of
a city. In Unity Catalog the usual way to make that real is one owner and one location for each conformed dimension
(here `shop.gold.dim_customer`), with every fact in the domain pointing at it.

## 10.3 Grain first

*Level: beginner.*

The **grain** of a fact table is what one row means, stated in business words: "one row per order line", "one row
per order", "one row per product per store per day". Declaring it first decides everything else: which dimensions
can attach (a customer belongs to an order, so it attaches to an order line too; a warehouse shelf might not), which
measures are valid (a line has a quantity; a whole order has a shipping fee), and what a unique key looks like
(`order_id, product_id` for order lines).

Red Rock Supply's silver data has measures at two grains: `silver.orders.amount` is an **order-level** (header)
measure, and `qty * unit_price` in `silver.order_items` is a **line-level** measure. The classic mistake is to join
the two and sum the header measure. Here is the silver input, then the mistake:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_id, customer_id, order_ts, status, amount, currency FROM silver.orders ORDER BY order_id;
SELECT * FROM silver.order_items ORDER BY order_id, product_id;
```

```text
+--------+-----------+-------------------+---------+------+--------+
|order_id|customer_id|order_ts           |status   |amount|currency|
+--------+-----------+-------------------+---------+------+--------+
|1001    |7          |2026-03-01 10:15:00|PLACED   |59.90 |CAD     |
|1002    |8          |2026-03-01 11:00:00|SHIPPED  |120.00|CAD     |
|1005    |7          |2026-03-01 13:05:00|PLACED   |35.50 |USD     |
|1008    |9          |2026-03-02 08:10:00|PLACED   |42.00 |CAD     |
|1009    |10         |2026-03-02 12:30:00|PLACED   |158.00|CAD     |
|1010    |8          |2026-03-02 15:00:00|CANCELLED|40.00 |CAD     |
|1011    |11         |2026-03-03 10:00:00|PLACED   |30.00 |CAD     |
|1012    |7          |2026-03-03 12:00:00|PLACED   |69.95 |CAD     |
+--------+-----------+-------------------+---------+------+--------+

+--------+----------+---+----------+
|order_id|product_id|qty|unit_price|
+--------+----------+---+----------+
|1001    |3         |2  |29.95     |
|1002    |5         |1  |120.00    |
|1005    |4         |1  |35.50     |
|1008    |7         |3  |14.00     |
|1009    |1         |4  |5.00      |
|1009    |2         |1  |18.00     |
|1009    |5         |1  |120.00    |
|1010    |6         |1  |40.00     |
|1011    |8         |2  |15.00     |
|1012    |3         |1  |29.95     |
|1012    |6         |1  |40.00     |
+--------+----------+---+----------+
```

These are the chapter 9 silver tables with a few more orders. Customer 11 has no row in `silver.customers` yet; that
is deliberate (section 10.5).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
-- wrong: amount is a header measure, the join repeats it once per line
SELECT o.order_date, sum(o.amount) AS revenue_wrong
FROM silver.orders o JOIN silver.order_items i ON i.order_id = o.order_id
WHERE o.status <> 'CANCELLED' GROUP BY ALL ORDER BY ALL;

-- right: sum the header measure at the header grain ...
SELECT order_date, sum(amount) AS revenue_right
FROM silver.orders WHERE status <> 'CANCELLED' GROUP BY ALL ORDER BY ALL;

-- ... or sum the line measure at the line grain
SELECT o.order_date, sum(i.qty * i.unit_price) AS revenue_from_lines
FROM silver.orders o JOIN silver.order_items i ON i.order_id = o.order_id
WHERE o.status <> 'CANCELLED' GROUP BY ALL ORDER BY ALL;
```

```text
+----------+-------------+
|order_date|revenue_wrong|
+----------+-------------+
|2026-03-01|215.40       |
|2026-03-02|516.00       |
|2026-03-03|169.90       |
+----------+-------------+

+----------+-------------+
|order_date|revenue_right|
+----------+-------------+
|2026-03-01|215.40       |
|2026-03-02|200.00       |
|2026-03-03|99.95        |
+----------+-------------+

+----------+------------------+
|order_date|revenue_from_lines|
+----------+------------------+
|2026-03-01|215.40            |
|2026-03-02|200.00            |
|2026-03-03|99.95             |
+----------+------------------+
```

March 1 looks right by luck: every order that day has exactly one line. On March 2, order 1009 has three lines, so
its 158.00 is counted three times (42.00 + 3 x 158.00 = 516.00). This is called **fan-out**: a join to a finer grain
multiplies the coarser rows. The fix is a rule, not a trick: a measure is summed only at the grain where it lives.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 290" role="img" aria-label="Order 1009 at three grains: one header row of 158.00, three line rows of 120.00, 18.00 and 20.00, and one daily row of 200.00 for March 2; joining the header to the lines repeats 158.00 three times">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="15" y="44" width="185" height="34" rx="4"/>
<rect x="225" y="44" width="190" height="34" rx="4"/>
<rect x="225" y="78" width="190" height="34" rx="4"/>
<rect x="225" y="112" width="190" height="34" rx="4"/>
<rect x="440" y="44" width="185" height="34" rx="4"/>
<rect x="15" y="180" width="610" height="96" rx="6" stroke-dasharray="5 4"/>
<line x1="415" y1="95" x2="434" y2="70"/>
</g>
<g fill="currentColor">
<polygon points="440,62 430,64 437,72"/>
</g>
<g fill="currentColor" font-size="14" text-anchor="middle">
<text x="107" y="30">orders (header)</text>
<text x="320" y="30">order_items (line)</text>
<text x="532" y="30">daily_sales (day)</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="107" y="66">1009 | 158.00</text>
<text x="320" y="66">1009 | tent | 120.00</text>
<text x="320" y="100">1009 | headlamp | 18.00</text>
<text x="320" y="134">1009 | stakes | 20.00</text>
<text x="532" y="66">03-02 | CAD | 200.00</text>
<text x="532" y="98">orders 1008 + 1009</text>
<text x="320" y="206">Join orders to order_items, then sum(o.amount):</text>
<text x="320" y="230">158.00 is repeated on all 3 lines, so March 2 shows 516.00, not 200.00</text>
<text x="320" y="256">Rule: sum a measure only at the grain where it lives</text>
</g>
</svg>
<figcaption>Figure 10.2. One order at three grains. The line grain is the finest the data supports, so the fact table
uses it; the daily table is a coarser grain built from it. Summing a header measure after a join to the lines
multiplies it.</figcaption>
</figure>

How to choose the grain:

- **Start from the finest grain the source supports** (here, the order line). A fine-grained fact can always be
  rolled up; a coarse one cannot be broken down. "Revenue by category" needs lines, because one order can hold a tent
  and a headlamp.
- **One grain per fact table.** Header-only measures (a shipping fee, an order-level discount) either go into a
  separate order-grain fact, or are allocated down to lines by an agreed rule. Never mix the two in one table.
- **Write the grain in the table comment** and make it testable: "one row per (`order_id`, `product_sk`)" is a
  uniqueness check (section 10.12).
- **Aggregates are extra tables, not the fact.** `daily_sales` (one row per day and currency) is built from the line
  fact, so it can be rebuilt when a rule changes.

!!! tip "In the interview"
    **"How do you choose the grain of a fact table?"** I start from the business process and pick the most atomic
    event the source records, here one order line, because it can answer every coarser question and the reverse is
    not true. I state the grain in one sentence, make it the unique key and test it, attach only dimensions that are
    true at that grain, and keep header-level measures in their own fact or allocate them explicitly. Daily or
    monthly summaries are separate aggregate tables built from the atomic fact.

## 10.4 Dimensions and surrogate keys

*Level: intermediate.*

A **natural key** (or business key) is the identifier the source system uses: `customer_id = 7`. A **surrogate key**
is a key the warehouse makes up for a dimension row: `customer_sk`. Gold dimensions use surrogate keys for three
reasons. A Type 2 dimension has several rows per customer (one per version), so `customer_id` is no longer unique
there. Two sources may reuse the same natural key for different things. And a surrogate key lets the fact point at
a special "unknown" row instead of `NULL` when the dimension row is missing.

### A date dimension

The simplest dimension is generated, not loaded. `sequence` plus `explode` makes one row per day; the key is the
date as a number, `yyyymmdd`, which is readable and sorts correctly:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE gold.dim_date (
  date_key    INT  NOT NULL,
  date        DATE NOT NULL,
  year        INT, month INT, day INT,
  day_name    STRING,
  is_weekend  BOOLEAN
) USING DELTA;

INSERT INTO gold.dim_date
SELECT CAST(date_format(d, 'yyyyMMdd') AS INT) AS date_key,
       d                                       AS date,
       year(d), month(d), day(d),
       date_format(d, 'EEEE')                  AS day_name,
       dayofweek(d) IN (1, 7)                  AS is_weekend
FROM (SELECT explode(sequence(DATE'2026-01-01', DATE'2026-12-31', INTERVAL 1 DAY)) AS d);

SELECT * FROM gold.dim_date WHERE date BETWEEN DATE'2026-02-28' AND DATE'2026-03-04' ORDER BY date_key;
```

```text
+--------+----------+----+-----+---+---------+----------+
|date_key|date      |year|month|day|day_name |is_weekend|
+--------+----------+----+-----+---+---------+----------+
|20260228|2026-02-28|2026|2    |28 |Saturday |true      |
|20260301|2026-03-01|2026|3    |1  |Sunday   |true      |
|20260302|2026-03-02|2026|3    |2  |Monday   |false     |
|20260303|2026-03-03|2026|3    |3  |Tuesday  |false     |
|20260304|2026-03-04|2026|3    |4  |Wednesday|false     |
+--------+----------+----+-----+---+---------+----------+
```

The full year has 365 rows. `dayofweek` returns 1 for Sunday and 7 for Saturday, hence `IN (1, 7)`.

### Identity columns: a counter for each new row

Delta Lake **identity columns** assign a value to every inserted row. The syntax, from
[CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using),
is `GENERATED { ALWAYS | BY DEFAULT } AS IDENTITY [ ( [ START WITH start ] [ INCREMENT BY step ] ) ]`; it applies to
Databricks SQL and Databricks Runtime 10.4 LTS and above, only to Delta tables, and only to `BIGINT` columns. The
assigned values "are unique but are not guaranteed to be contiguous". `ALWAYS` refuses values you supply;
`BY DEFAULT` uses your value when you give one.

`dim_product` is a Type 1 dimension (attributes are overwritten in place, no history), so a `MERGE` keyed on the
natural key keeps it current, and the identity column numbers each new product:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE gold.dim_product (
  product_sk  BIGINT GENERATED ALWAYS AS IDENTITY,
  product_id  INT NOT NULL,
  name        STRING,
  category    STRING,
  list_price  DECIMAL(10,2)
) USING DELTA;

MERGE INTO gold.dim_product AS t
USING silver.products AS s
ON t.product_id = s.product_id
WHEN MATCHED AND NOT (t.name <=> s.name AND t.category <=> s.category AND t.list_price <=> s.price)
  THEN UPDATE SET name = s.name, category = s.category, list_price = s.price
WHEN NOT MATCHED
  THEN INSERT (product_id, name, category, list_price) VALUES (s.product_id, s.name, s.category, s.price);

SELECT * FROM gold.dim_product ORDER BY product_id;
```

```text
+----------+----------+----------------+---------+----------+
|product_sk|product_id|name            |category |list_price|
+----------+----------+----------------+---------+----------+
|2         |1         |Tent stakes (8) |Camping  |5.00      |
|4         |2         |Headlamp        |Lighting |18.00     |
|6         |3         |Trail socks     |Apparel  |29.95     |
|8         |4         |Water filter    |Hydration|35.50     |
|1         |5         |Two-person tent |Camping  |120.00    |
|3         |6         |Trekking poles  |Hiking   |40.00     |
|5         |7         |Energy bars (12)|Food     |14.00     |
|7         |8         |Carabiner set   |Climbing |15.00     |
+----------+----------+----------------+---------+----------+
```

The keys are unique, but not in `product_id` order: products 1 to 4 got the even keys and 5 to 8 the odd ones, which
suggests each of the two parallel write tasks drew its own sequence of values (an inference from the output;
Databricks only promises unique values). That is fine: a surrogate key carries no meaning. Trying to set or change it
fails:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO gold.dim_product VALUES (99, 99, 'Test', 'Test', 1.00);
UPDATE gold.dim_product SET product_sk = 100 WHERE product_id = 1;
```

```text
[DELTA_IDENTITY_COLUMNS_EXPLICIT_INSERT_NOT_SUPPORTED] Providing values for GENERATED ALWAYS AS IDENTITY column product_sk is not supported.
[DELTA_IDENTITY_COLUMNS_UPDATE_NOT_SUPPORTED] UPDATE on IDENTITY column product_sk is not supported.
```

Now silver changes: the headlamp's price goes from 18.00 to 21.00 and a new product 9 appears. The same `MERGE`
updates one row in place (Type 1) and inserts one, which gets the next free key. A rerun with nothing new touches
nothing:

```text
>>> MERGE INTO gold.dim_product ...   (after the silver change)
+-----------------+----------------+----------------+-----------------+
|num_affected_rows|num_updated_rows|num_deleted_rows|num_inserted_rows|
+-----------------+----------------+----------------+-----------------+
|2                |1               |0               |1                |
+-----------------+----------------+----------------+-----------------+

+----------+----------+----------------+---------+----------+
|product_sk|product_id|name            |category |list_price|
+----------+----------+----------------+---------+----------+
|2         |1         |Tent stakes (8) |Camping  |5.00      |
|4         |2         |Headlamp        |Lighting |21.00     |
...
|9         |9         |Bear canister   |Camping  |79.00     |
+----------+----------+----------------+---------+----------+

>>> MERGE INTO gold.dim_product ...   (rerun, nothing new)
+-----------------+----------------+----------------+-----------------+
|num_affected_rows|num_updated_rows|num_deleted_rows|num_inserted_rows|
+-----------------+----------------+----------------+-----------------+
|0                |0               |0               |0                |
+-----------------+----------------+----------------+-----------------+
```

The `WHEN MATCHED AND NOT (... <=> ...)` condition is what makes the rerun a no-op: without it, every product would
be "updated" to the same values on every run, writing new files for nothing. `<=>` is null-safe equality (chapter 9,
section 9.10).

The weakness of identity keys shows when a dimension is **rebuilt**. Here the same nine products are loaded into a
fresh table:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO gold.dim_product_rebuilt (product_id, name, category, list_price)
SELECT product_id, name, category, price FROM silver.products ORDER BY name;
```

```text
+----------+----------------+---------+----------------+
|product_id|name            |sk_before|sk_after_rebuild|
+----------+----------------+---------+----------------+
|1         |Tent stakes (8) |2        |5               |
|2         |Headlamp        |4        |4               |
|3         |Trail socks     |6        |6               |
|4         |Water filter    |8        |9               |
|5         |Two-person tent |1        |8               |
|6         |Trekking poles  |3        |7               |
|7         |Energy bars (12)|5        |3               |
|8         |Carabiner set   |7        |2               |
|9         |Bear canister   |9        |1               |
+----------+----------------+---------+----------------+
```

Every fact row that stored `product_sk = 1` meant the tent; after the rebuild, 1 is the bear canister. An identity
key is a record of load history, not a function of the data, so a dimension with identity keys must never be
dropped and reloaded on its own: either rebuild every fact that points to it in the same run, or never rebuild it.

!!! warning "Identity columns and concurrency"
    Databricks says: "Declaring an identity column on a Delta Lake table disables concurrent transactions. Only use
    identity columns in use cases where concurrent writes to the target table aren't required"
    ([Delta Lake generated columns](https://docs.databricks.com/aws/en/delta/generated-columns)). The same page lists
    the other limits: you cannot partition by an identity column, cannot `ALTER TABLE` to add, replace or change one,
    cannot update its value, and cannot declare one in a CTAS (create the table first, then `INSERT`). In Lakeflow
    pipelines, identity columns "are not supported with tables that are the target of AUTO CDC processing" and "might
    be recomputed during updates to a materialized views", so Databricks "recommends using identity columns in
    pipelines only with streaming tables" ([Pipeline limitations](https://docs.databricks.com/aws/en/ldp/limitations)).

### Hash keys: the same input always gives the same key

The alternative is to **compute** the surrogate key from the natural key (and, for Type 2, the version start). The
same inputs always give the same key, on every run and after any rebuild, and no coordination between writers is
needed. `dim_customer` takes the SCD Type 2 history that silver already keeps (chapter 9, section 9.10) and gives
each version a key with `xxhash64`, which returns a `BIGINT`. One extra row, key `-1`, is the **unknown member**:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE gold.dim_customer (
  customer_sk BIGINT NOT NULL,
  customer_id INT,
  name STRING, email STRING, city STRING, country STRING,
  valid_from  TIMESTAMP,
  valid_to    TIMESTAMP,
  is_current  BOOLEAN
) USING DELTA;

MERGE INTO gold.dim_customer AS t
USING (
  SELECT xxhash64(customer_id, valid_from) AS customer_sk, *
  FROM silver.customers
  UNION ALL
  SELECT -1, NULL, 'Unknown customer', NULL, NULL, NULL, NULL, NULL, NULL
) AS s
ON t.customer_sk = s.customer_sk
WHEN MATCHED AND NOT (t.valid_to <=> s.valid_to AND t.is_current <=> s.is_current
                      AND t.email <=> s.email AND t.city <=> s.city)
  THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

```text
+-----------------+----------------+----------------+-----------------+
|num_affected_rows|num_updated_rows|num_deleted_rows|num_inserted_rows|
+-----------------+----------------+----------------+-----------------+
|8                |0               |0               |8                |
+-----------------+----------------+----------------+-----------------+

+--------------------+-----------+---------+------------------------+-------------------+-------------------+----------+
|customer_sk         |customer_id|city     |email                   |valid_from         |valid_to           |is_current|
+--------------------+-----------+---------+------------------------+-------------------+-------------------+----------+
|-1                  |NULL       |NULL     |NULL                    |NULL               |NULL               |NULL      |
|5472907325412269299 |7          |Calgary  |ava.chen@example.com    |2026-01-05 09:00:00|2026-03-01 10:00:00|false     |
|-1435483106282796086|7          |Banff    |ava.chen@example.com    |2026-03-01 10:00:00|2026-04-10 16:00:00|false     |
|-7238947835605265590|7          |Canmore  |ava.chen@example.com    |2026-04-10 16:00:00|NULL               |true      |
|-8423982228499656852|8          |Denver   |ben.ortiz@example.com   |2026-01-10 14:30:00|NULL               |true      |
|8549487990814550448 |9          |Moab     |chloe.m@example.com     |2026-01-20 08:00:00|2026-04-12 09:30:00|false     |
|4440432580874565620 |9          |Moab     |chloe.martin@example.com|2026-04-12 09:30:00|NULL               |true      |
|-3420216544118607680|10         |Vancouver|dev.patel@example.com   |2026-03-02 11:00:00|NULL               |true      |
+--------------------+-----------+---------+------------------------+-------------------+-------------------+----------+
```

A rerun inserts and updates nothing (`num_affected_rows = 0`), and `xxhash64(7, TIMESTAMP'2026-03-01 10:00:00')`
computed on its own returns `-1435483106282796086`, the key of Ava's Banff version: same input, same key.

The two kinds of dimension change map to two `MERGE` shapes:

- **SCD Type 1** (`dim_product`): match on the natural key, overwrite the attributes. History is lost on purpose.
- **SCD Type 2** (`dim_customer`): the versions already exist in silver, so gold matches on the version's surrogate
  key and only ever updates `valid_to` and `is_current` of a version that was closed. If silver does not keep
  history, the Type 2 logic itself (close the old row, insert the new one) is the `MERGE` of chapter 9, section 9.10,
  or `AUTO CDC ... STORED AS SCD TYPE 2` (formerly `APPLY CHANGES`) in a Lakeflow pipeline
  ([chapter 14](14-Data-Quality-and-CDC.md)).

Identity or hash? A side-by-side:

| | Identity column | Hash of natural key (+ version start) |
| --- | --- | --- |
| Key size | `BIGINT`, small numbers | `BIGINT` with `xxhash64`; a 64-character string with `sha2(..., 256)` |
| Same key after a rebuild | No (shown above) | Yes |
| Concurrent writers | Not allowed: identity "disables concurrent transactions" | No restriction from the key |
| Lookup needed to load a fact | Yes: join to the dimension to find the key | No: the fact can compute the key itself (for Type 1) |
| In Lakeflow pipelines | Recommended only on streaming tables; not supported on `AUTO CDC` targets | Works in any query |
| Collisions | None | Possible; must be tested |

On collisions: `xxhash64` gives 64 bits. If it behaves like a random function, the chance that **any** two of `n`
keys collide is about n^2 / 2^65 for small values: roughly 3 in a million for `n` = 10 million, and about 3% for
`n` = 1 billion. That is why the uniqueness test in section 10.12 runs on the dimension key, and why very large
dimensions often use `sha2(..., 256)` strings instead (bigger keys, slower joins, collisions practically ruled out).
Always hash with a separator, for example `concat_ws('|', ...)`, or pass the columns as separate arguments as
`xxhash64(a, b)` does: `concat(1, 23)` and `concat(12, 3)` are both `'123'` (practice question Q41).

!!! tip "In the interview"
    **"Identity column or hash for surrogate keys on Databricks?"** Identity columns give small, readable keys but
    they depend on load order, change if the table is rebuilt, and Databricks says they disable concurrent
    transactions on the table, and recommends them in [Lakeflow pipelines, formerly Delta Live
    Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) only on streaming
    tables. A hash of the natural key
    (plus `valid_from` for SCD Type 2) is deterministic, so rebuilds and backfills reproduce the same keys and
    parallel jobs need no coordination; the cost is a collision risk that I test with a uniqueness check. For gold
    that I want to be able to rebuild from silver, I prefer hashes.

## 10.5 The fact table

*Level: intermediate.*

The fact table has one row per order line. Its columns are the foreign keys to the dimensions (`product_sk`,
`customer_sk`, `date_key`), the **degenerate dimension** `order_id` (an identifier with no dimension table of its own,
kept so you can count orders and trace a line back to silver), a few attributes analysts filter on constantly
(`order_date`, `status`, `currency`), and the measures.

The key step is the lookup of `customer_sk`. Customers are Type 2, so the fact must point at the version that was
true **when the order was placed** (the "as-was" view): `order_ts` must fall in `[valid_from, valid_to)`. An order
whose customer is not in the dimension yet gets `-1`, the unknown member, instead of a `NULL` that would silently
drop the row from inner joins.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE gold.fact_order_lines (
  order_id     INT    NOT NULL,
  product_sk   BIGINT NOT NULL,
  customer_sk  BIGINT NOT NULL,
  date_key     INT    NOT NULL,
  order_date   DATE   NOT NULL,
  order_ts     TIMESTAMP,
  status       STRING,
  currency     STRING,
  qty          INT,
  unit_price   DECIMAL(10,2),
  line_amount  DECIMAL(12,2)
) USING DELTA
CLUSTER BY (order_date);

INSERT INTO gold.fact_order_lines
SELECT i.order_id,
       p.product_sk,
       coalesce(c.customer_sk, -1)                        AS customer_sk,
       CAST(date_format(o.order_date, 'yyyyMMdd') AS INT) AS date_key,
       o.order_date, o.order_ts, o.status, o.currency,
       i.qty, i.unit_price,
       CAST(i.qty * i.unit_price AS DECIMAL(12,2))        AS line_amount
FROM silver.order_items i
JOIN silver.orders      o ON o.order_id = i.order_id
JOIN gold.dim_product   p ON p.product_id = i.product_id
LEFT JOIN gold.dim_customer c
  ON  c.customer_id = o.customer_id
  AND o.order_ts >= c.valid_from
  AND (o.order_ts < c.valid_to OR c.valid_to IS NULL);
```

```text
+--------+----------+--------------------+--------+---------+--------+---+----------+-----------+
|order_id|product_sk|customer_sk         |date_key|status   |currency|qty|unit_price|line_amount|
+--------+----------+--------------------+--------+---------+--------+---+----------+-----------+
|1001    |6         |-1435483106282796086|20260301|PLACED   |CAD     |2  |29.95     |59.90      |
|1002    |1         |-8423982228499656852|20260301|SHIPPED  |CAD     |1  |120.00    |120.00     |
|1005    |8         |-1435483106282796086|20260301|PLACED   |USD     |1  |35.50     |35.50      |
|1008    |5         |8549487990814550448 |20260302|PLACED   |CAD     |3  |14.00     |42.00      |
|1009    |1         |-3420216544118607680|20260302|PLACED   |CAD     |1  |120.00    |120.00     |
|1009    |2         |-3420216544118607680|20260302|PLACED   |CAD     |4  |5.00      |20.00      |
|1009    |4         |-3420216544118607680|20260302|PLACED   |CAD     |1  |18.00     |18.00      |
|1010    |3         |-8423982228499656852|20260302|CANCELLED|CAD     |1  |40.00     |40.00      |
|1011    |7         |-1                  |20260303|PLACED   |CAD     |2  |15.00     |30.00      |
|1012    |3         |-1435483106282796086|20260303|PLACED   |CAD     |1  |40.00     |40.00      |
|1012    |6         |-1435483106282796086|20260303|PLACED   |CAD     |1  |29.95     |29.95      |
+--------+----------+--------------------+--------+---------+--------+---+----------+-----------+
```

Which version did each order get?

```text
+--------+-------------------+-----------+---------+---------------------+-------------------+-------------------+
|order_id|order_ts           |customer_id|city     |email                |valid_from         |valid_to           |
+--------+-------------------+-----------+---------+---------------------+-------------------+-------------------+
|1001    |2026-03-01 10:15:00|7          |Banff    |ava.chen@example.com |2026-03-01 10:00:00|2026-04-10 16:00:00|
|1002    |2026-03-01 11:00:00|8          |Denver   |ben.ortiz@example.com|2026-01-10 14:30:00|NULL               |
|1005    |2026-03-01 13:05:00|7          |Banff    |ava.chen@example.com |2026-03-01 10:00:00|2026-04-10 16:00:00|
|1008    |2026-03-02 08:10:00|9          |Moab     |chloe.m@example.com  |2026-01-20 08:00:00|2026-04-12 09:30:00|
|1009    |2026-03-02 12:30:00|10         |Vancouver|dev.patel@example.com|2026-03-02 11:00:00|NULL               |
|1010    |2026-03-02 15:00:00|8          |Denver   |ben.ortiz@example.com|2026-01-10 14:30:00|NULL               |
|1011    |2026-03-03 10:00:00|NULL       |NULL     |NULL                 |NULL               |NULL               |
|1012    |2026-03-03 12:00:00|7          |Banff    |ava.chen@example.com |2026-03-01 10:00:00|2026-04-10 16:00:00|
+--------+-------------------+-----------+---------+---------------------+-------------------+-------------------+
```

Ava moved from Calgary to Banff at 10:00 on March 1; order 1001 was placed at 10:15, so it belongs to Banff, not to
Calgary and not to her current town, Canmore. Order 1011's customer is unknown for now.

Things to notice in the build:

- `JOIN gold.dim_product` is an inner join on purpose here: every silver line has a valid product, because silver
  checked it. If that were not guaranteed, it would be a left join with an unknown product member, like customers.
- The half-open interval (`>= valid_from` and `< valid_to`) matches the chapter 9 convention that a closed version's
  `valid_to` equals the next version's `valid_from`; with `<=` an order at exactly the change time would match two
  versions and be duplicated.
- An order placed **before** the first known version of its customer gets no match. Teams either map it to the
  unknown member (as here) or to the earliest version; pick one and document it.
- `CLUSTER BY (order_date)` makes the table a liquid clustering table on the column most queries filter on; the local
  `DESCRIBE DETAIL` shows `clusteringColumns = [order_date]`. Choosing keys is covered in
  [chapter 22](22-Performance-Tuning.md).

The same build in PySpark, compared row by row with the SQL result:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql import functions as F

items = spark.table("silver.order_items")
orders = spark.table("silver.orders")
prod = spark.table("gold.dim_product").select("product_id", "product_sk")
cust = spark.table("gold.dim_customer").alias("c")

fact_df = (
    items.join(orders, "order_id")
    .join(prod, "product_id")
    .join(cust,
          (F.col("c.customer_id") == orders.customer_id)
          & (orders.order_ts >= F.col("c.valid_from"))
          & ((orders.order_ts < F.col("c.valid_to")) | F.col("c.valid_to").isNull()),
          "left")
    .select(
        "order_id", "product_sk",
        F.coalesce(F.col("c.customer_sk"), F.lit(-1).cast("bigint")).alias("customer_sk"),
        F.date_format("order_date", "yyyyMMdd").cast("int").alias("date_key"),
        "order_date", "order_ts", "status", "currency", "qty", "unit_price",
        (F.col("qty") * F.col("unit_price")).cast("decimal(12,2)").alias("line_amount"))
)
gold = spark.table("gold.fact_order_lines")
print("rows only in PySpark result:", fact_df.exceptAll(gold).count())
print("rows only in SQL result:    ", gold.exceptAll(fact_df).count())
```

```text
rows only in PySpark result: 0
rows only in SQL result:     0
```

With the star in place, "as-was" and "as-is" are both one join away. Revenue by the city the customer lived in when
ordering, next to the city they live in now:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT c.city AS city_at_order, cur.city AS city_now, sum(f.line_amount) AS revenue
FROM gold.fact_order_lines f
JOIN gold.dim_customer c        ON c.customer_sk = f.customer_sk
LEFT JOIN gold.dim_customer cur ON cur.customer_id = c.customer_id AND cur.is_current
WHERE f.status <> 'CANCELLED' AND f.currency = 'CAD'
GROUP BY ALL ORDER BY ALL;
```

```text
+-------------+---------+-------+
|city_at_order|city_now |revenue|
+-------------+---------+-------+
|NULL         |NULL     |30.00  |
|Banff        |Canmore  |129.85 |
|Denver       |Denver   |120.00 |
|Moab         |Moab     |42.00  |
|Vancouver    |Vancouver|158.00 |
+-------------+---------+-------+
```

The `NULL` row is order 1011 on the unknown member: its revenue is still counted, which is the point of `-1`. It is
also a **late-arriving dimension**: the fact arrived before its customer. Section 10.7 fixes it when customer 11
reaches silver.

!!! warning "A `NULL` foreign key loses revenue quietly"
    If the fact stored `customer_sk = NULL` for order 1011, every report that inner-joins `dim_customer` would drop
    its 30.00 without an error. The unknown member keeps the total right and makes the gap visible as one row
    labelled "Unknown customer", which a check can count (section 10.12).


## 10.6 Aggregates, and star schema versus one big table

*Level: intermediate.*

### An aggregate table

Most dashboards ask the same few questions: revenue per day, per week, per category. An **aggregate table**
precomputes them at a coarser grain. `gold.daily_sales` has one row per order date and currency. Its grain matters
as much as the fact's: currency is part of it because adding Canadian and US dollars gives a number that means
nothing.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE gold.daily_sales (
  order_date  DATE   NOT NULL,
  currency    STRING NOT NULL,
  orders      BIGINT,
  units       BIGINT,
  revenue     DECIMAL(22,2),
  customers   BIGINT
) USING DELTA;

INSERT INTO gold.daily_sales
SELECT f.order_date, f.currency,
       count(DISTINCT f.order_id)    AS orders,
       sum(f.qty)                    AS units,
       sum(f.line_amount)            AS revenue,
       count(DISTINCT c.customer_id) AS customers
FROM gold.fact_order_lines f
JOIN gold.dim_customer c ON c.customer_sk = f.customer_sk
WHERE f.status <> 'CANCELLED'
GROUP BY f.order_date, f.currency;
```

```text
+----------+--------+------+-----+-------+---------+
|order_date|currency|orders|units|revenue|customers|
+----------+--------+------+-----+-------+---------+
|2026-03-01|CAD     |2     |3    |179.90 |2        |
|2026-03-01|USD     |1     |1    |35.50  |1        |
|2026-03-02|CAD     |2     |9    |200.00 |2        |
|2026-03-03|CAD     |2     |4    |99.95  |1        |
+----------+--------+------+-----+-------+---------+
```

March 3 shows one customer for two orders: order 1011 sits on the unknown member, whose `customer_id` is `NULL`, and
`count(DISTINCT ...)` ignores `NULL`. The revenue is complete; the customer count is not, until the late customer
arrives.

The same aggregate in PySpark (the run compared it with the SQL table: 0 differing rows both ways):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql import functions as F

f = spark.table("gold.fact_order_lines")
c = spark.table("gold.dim_customer").select("customer_sk", "customer_id")
daily_df = (f.where(F.col("status") != "CANCELLED")
            .join(c, "customer_sk")
            .groupBy("order_date", "currency")
            .agg(F.count_distinct("order_id").alias("orders"),
                 F.sum("qty").alias("units"),
                 F.sum("line_amount").alias("revenue"),
                 F.count_distinct("customer_id").alias("customers")))
```

### Additive, semi-additive and non-additive measures

Before rolling an aggregate up further, ask how each measure adds. An **additive** measure (revenue, units) can be
summed across every dimension. A **semi-additive** measure (a stock level, an account balance) can be summed across
some dimensions but not across time: the stock at month end is the last day's value, not the sum of 30 days. A
**non-additive** measure (a distinct count, a ratio, an average) cannot be summed at all. Rolling `daily_sales` up to
the whole period:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT currency, sum(revenue) AS revenue_from_daily, sum(orders) AS orders_from_daily,
       sum(customers) AS customers_summed_from_daily
FROM gold.daily_sales GROUP BY currency ORDER BY currency;

SELECT f.currency, sum(f.line_amount) AS revenue, count(DISTINCT f.order_id) AS orders,
       count(DISTINCT c.customer_id) AS customers_true
FROM gold.fact_order_lines f JOIN gold.dim_customer c ON c.customer_sk = f.customer_sk
WHERE f.status <> 'CANCELLED' GROUP BY f.currency ORDER BY f.currency;
```

```text
+--------+------------------+-----------------+---------------------------+
|currency|revenue_from_daily|orders_from_daily|customers_summed_from_daily|
+--------+------------------+-----------------+---------------------------+
|CAD     |479.85            |6                |5                          |
|USD     |35.50             |1                |1                          |
+--------+------------------+-----------------+---------------------------+

+--------+-------+------+--------------+
|currency|revenue|orders|customers_true|
+--------+-------+------+--------------+
|CAD     |479.85 |6     |4             |
|USD     |35.50  |1     |1             |
+--------+-------+------+--------------+
```

Revenue and orders roll up correctly (an order belongs to one day, so distinct orders per day do add up). Customers
do not: Ava bought on March 1 and March 3, so she is counted on both days, and the sum says 5 customers where there
were 4. A distinct count must be computed from the fact at the grain the question asks for, or stored in a mergeable
form (for example a sketch for approximate counts), or defined once in a metric view (section 10.9) that always
computes it from the detail.

!!! warning "Count distinct customers, not distinct surrogate keys"
    In a Type 2 dimension one customer has several keys. `count(DISTINCT customer_sk)` counts customer **versions**:
    if Ava ordered once in Banff and once in Canmore it returns 2 for one person (practice question Q15 runs it).
    Count `customer_id` from the dimension instead.

### One big table

The other common gold shape is **one big table** (OBT): the fact joined to all its dimensions once and stored wide,
so a query needs no joins at all:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE gold.sales_obt USING DELTA AS
SELECT f.order_id, f.order_date, d.day_name, d.is_weekend, f.order_ts, f.status, f.currency,
       p.product_id, p.name AS product_name, p.category,
       c.customer_id, c.name AS customer_name, c.city AS customer_city, c.country AS customer_country,
       f.qty, f.unit_price, f.line_amount
FROM gold.fact_order_lines f
JOIN gold.dim_date d     ON d.date_key = f.date_key
JOIN gold.dim_product p  ON p.product_sk = f.product_sk
JOIN gold.dim_customer c ON c.customer_sk = f.customer_sk;

SELECT category, customer_country, sum(line_amount) AS revenue
FROM gold.sales_obt
WHERE status <> 'CANCELLED' AND currency = 'CAD'
GROUP BY ALL ORDER BY ALL;
```

```text
+--------+----------------+-------+
|category|customer_country|revenue|
+--------+----------------+-------+
|Apparel |CA              |89.85  |
|Camping |CA              |140.00 |
|Camping |US              |120.00 |
|Climbing|NULL            |30.00  |
|Food    |US              |42.00  |
|Hiking  |CA              |40.00  |
|Lighting|CA              |18.00  |
+--------+----------------+-------+
```

Which one? Databricks' own guidance supports both: star and snowflake schemas "perform well on Databricks", and "having
more data fields in a single table allows the query optimizer to skip large amounts of data using file-level
statistics" ([Data modeling](https://docs.databricks.com/aws/en/transform/data-modeling)), which is the OBT's main
advantage. The trade-offs:

| | Star schema | One big table |
| --- | --- | --- |
| Queries | joins (simple, on keys) | no joins; filter any column directly |
| Data skipping | filters on dimension columns may not skip fact files (Databricks notes this) | every attribute is on the table, so file statistics and clustering apply to it |
| A dimension attribute changes (Type 1) | update one dimension row | rewrite every fact row that carries it |
| As-was and as-is | both available (version key plus current row) | only what was copied in; adding "as-is" means another column and a rewrite |
| Conformed across facts | yes, shared dimensions | each OBT has its own copy, which can drift |
| Storage | compact | wide and repetitive (compression helps) |
| Semantic layer / BI tools | maps directly to a star model | maps to one flat model |

A pattern that works well on Databricks: keep the star as the governed model, and build an OBT (or a materialized
view, section 10.8) **from the star** for the few heaviest dashboards. The OBT is then a derived, rebuildable serving
table, not the source of truth.

!!! tip "In the interview"
    **"Star schema or one big table on Databricks?"** Both are fine on Delta; the choice is about change and reuse. I
    keep a star schema as the core model because dimensions are shared, Type 1 changes touch one row, and I can
    answer both as-was and as-is questions. For a hot dashboard I add a wide table or a materialized view built from
    the star, because one table with the filter columns on it gets the most out of data skipping and liquid
    clustering, and Databricks' data modeling page notes that filters on another table's columns may not skip data.
    What I avoid is a heavily normalized 3NF model, which Databricks recommends against for a new lakehouse.


## 10.7 Incremental gold: rebuild, MERGE, REPLACE WHERE

*Level: expert.*

Silver changes every day: new orders, corrected orders, late customers. Gold has three ways to follow:

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Three ways to refresh gold: a full rebuild reads all of silver and rewrites the table; an incremental load finds changed keys or days and rewrites only those with MERGE or INSERT REPLACE WHERE; a materialized view refresh lets Databricks choose incremental or full and always returns the query result">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="15" y="45" width="190" height="50" rx="5"/>
<rect x="15" y="130" width="190" height="50" rx="5"/>
<rect x="15" y="215" width="190" height="60" rx="5"/>
<rect x="225" y="45" width="190" height="50" rx="5"/>
<rect x="225" y="130" width="190" height="50" rx="5"/>
<rect x="225" y="215" width="190" height="60" rx="5"/>
<rect x="435" y="45" width="190" height="50" rx="5"/>
<rect x="435" y="130" width="190" height="50" rx="5"/>
<rect x="435" y="215" width="190" height="60" rx="5"/>
<line x1="110" y1="95" x2="110" y2="122"/>
<line x1="110" y1="180" x2="110" y2="207"/>
<line x1="320" y1="95" x2="320" y2="122"/>
<line x1="320" y1="180" x2="320" y2="207"/>
<line x1="530" y1="95" x2="530" y2="122"/>
<line x1="530" y1="180" x2="530" y2="207"/>
</g>
<g fill="currentColor">
<polygon points="110,130 105,120 115,120"/>
<polygon points="110,215 105,205 115,205"/>
<polygon points="320,130 315,120 325,120"/>
<polygon points="320,215 315,205 325,205"/>
<polygon points="530,130 525,120 535,120"/>
<polygon points="530,215 525,205 535,205"/>
</g>
<g fill="currentColor" font-size="14" text-anchor="middle">
<text x="110" y="28">Full rebuild</text>
<text x="320" y="28">Incremental, by hand</text>
<text x="530" y="28">Materialized view</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="110" y="75">read all of silver</text>
<text x="110" y="160">recompute every row</text>
<text x="110" y="240">overwrite the table;</text>
<text x="110" y="258">cost grows with history</text>
<text x="320" y="66">find changed keys</text>
<text x="320" y="84">or changed days</text>
<text x="320" y="151">MERGE, or INSERT</text>
<text x="320" y="169">... REPLACE WHERE</text>
<text x="320" y="240">rewrite only those;</text>
<text x="320" y="258">cost grows with change</text>
<text x="530" y="75">source tables change</text>
<text x="530" y="151">Databricks picks</text>
<text x="530" y="169">incremental or full</text>
<text x="530" y="240">same result as</text>
<text x="530" y="258">running the query</text>
</g>
</svg>
<figcaption>Figure 10.3. Full rebuild, incremental by hand, and materialized view refresh. The first two run here; the
third is Databricks only (section 10.8), refreshes incrementally only on serverless compute, and otherwise
recomputes.</figcaption>
</figure>

- **Full rebuild** (`CREATE OR REPLACE TABLE ... AS SELECT`, or `INSERT OVERWRITE`): simplest and always correct, and
  Delta keeps the previous version for time travel. Cost grows with the size of history, and it breaks identity keys
  (section 10.4). Fine for small dimensions and small aggregates.
- **Incremental by hand**: work out what changed, then `MERGE` the changed rows (row-level) or
  `INSERT ... REPLACE WHERE` the changed days (range-level). Cost grows with the size of the change.
- **Materialized view**: declare the query; Databricks decides how to refresh it (section 10.8).

The run below takes the gold layer built so far and applies **day 4** to silver: order 1001 (March 1) is corrected
from two pairs of socks to one, order 1012 (March 3) loses its socks line, a new order 1013 arrives for March 4, and
customer 11 finally reaches `silver.customers`.

```text
>>> SELECT order_id, customer_id, order_date, status, amount, updated_at FROM silver.orders
    WHERE updated_at > TIMESTAMP'2026-03-03 23:59:59' ORDER BY order_id
+--------+-----------+----------+------+------+-------------------+
|order_id|customer_id|order_date|status|amount|updated_at         |
+--------+-----------+----------+------+------+-------------------+
|1001    |7          |2026-03-01|PLACED|29.95 |2026-03-04 08:00:00|
|1012    |7          |2026-03-03|PLACED|40.00 |2026-03-04 08:05:00|
|1013    |10         |2026-03-04|PLACED|43.00 |2026-03-04 09:00:00|
+--------+-----------+----------+------+------+-------------------+
```

### Step 1: dimensions first

The same `dim_customer` `MERGE` as before inserts one row, Eli Novak (customer 11). Dimensions always load before
facts, so that a fact never looks up a key that is about to exist.

### Step 2: which orders changed?

Here the watermark is a timestamp: everything with `updated_at` after the last run. In production you would read
silver's Change Data Feed instead ([chapter 9, section 9.11](09-Building-Silver.md)), which also reports deletes.
One more source of change is easy to forget: fact rows parked on the unknown member, which can now be resolved.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE OR REPLACE TEMP VIEW changed_orders AS
SELECT order_id FROM silver.orders WHERE updated_at > TIMESTAMP'2026-03-03 23:59:59'
UNION
SELECT order_id FROM gold.fact_order_lines WHERE customer_sk = -1;
```

```text
changed orders: [1001, 1011, 1012, 1013]
```

### Step 3: MERGE the changed orders into the fact

The source of the `MERGE` is the fact query from section 10.5, limited to the changed orders. The key is the grain,
`(order_id, product_sk)`. Three clauses cover the three kinds of change: a line that changed (update), a new line
(insert), and a line that no longer exists in silver (delete):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
MERGE INTO gold.fact_order_lines AS t
USING (
  SELECT ...                                   -- the fact query of section 10.5
  WHERE o.order_id IN (1001, 1011, 1012, 1013)
) AS s
ON t.order_id = s.order_id AND t.product_sk = s.product_sk
WHEN MATCHED AND NOT (t.customer_sk <=> s.customer_sk AND t.qty <=> s.qty AND t.unit_price <=> s.unit_price
                      AND t.status <=> s.status AND t.order_date <=> s.order_date AND t.currency <=> s.currency)
  THEN UPDATE SET *
WHEN NOT MATCHED
  THEN INSERT *
WHEN NOT MATCHED BY SOURCE AND t.order_id IN (1001, 1011, 1012, 1013)
  THEN DELETE;
```

```text
+-----------------+----------------+----------------+-----------------+
|num_affected_rows|num_updated_rows|num_deleted_rows|num_inserted_rows|
+-----------------+----------------+----------------+-----------------+
|5                |2               |1               |2                |
+-----------------+----------------+----------------+-----------------+

+--------+----------+--------------------+----------+---+-----------+
|order_id|product_sk|customer_sk         |order_date|qty|line_amount|
+--------+----------+--------------------+----------+---+-----------+
|1001    |6         |-1435483106282796086|2026-03-01|1  |29.95      |
|1011    |7         |-531082494202069440 |2026-03-03|2  |30.00      |
|1012    |3         |-1435483106282796086|2026-03-03|1  |40.00      |
|1013    |5         |-3420216544118607680|2026-03-04|2  |28.00      |
|1013    |7         |-3420216544118607680|2026-03-04|1  |15.00      |
+--------+----------+--------------------+----------+---+-----------+
```

Two updates (1001's quantity, 1011's customer key moving from `-1` to Eli's version), one delete (1012's socks line)
and two inserts (order 1013). Order 1012's remaining line was matched but unchanged, so the `AND NOT (...)` guard
left it alone.

!!! warning "`WHEN NOT MATCHED BY SOURCE` without a condition deletes the whole table"
    The source holds only four orders. An unconditional `WHEN NOT MATCHED BY SOURCE THEN DELETE` would treat every
    other fact row as "gone from the source" and delete it. Always limit that clause to the slice the source
    represents (here `t.order_id IN (...)`; often a date range).

### Step 4: which days must be restated?

An aggregate row must be recomputed if any of its input rows changed. The changed orders' dates, taken **before and
after** the `MERGE` (an order whose date was corrected affects both its old and its new day):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT order_date FROM gold.fact_order_lines VERSION AS OF 1 WHERE order_id IN (1001, 1011, 1012, 1013)
UNION
SELECT order_date FROM gold.fact_order_lines WHERE order_id IN (1001, 1011, 1012, 1013)
ORDER BY 1;
```

```text
+----------+
|order_date|
+----------+
|2026-03-01|
|2026-03-03|
|2026-03-04|
+----------+
```

### Step 5: restate those days with INSERT ... REPLACE WHERE

`INSERT INTO ... REPLACE WHERE predicate query` deletes the rows that match the predicate and inserts the query's
rows, in one atomic commit. On Databricks it "applies to" Databricks SQL and Databricks Runtime 12.2 LTS and above,
for Delta Lake tables ([INSERT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-dml-insert-into));
open-source Delta runs it too:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO gold.daily_sales
REPLACE WHERE order_date IN (DATE'2026-03-01', DATE'2026-03-03', DATE'2026-03-04')
SELECT f.order_date, f.currency,
       count(DISTINCT f.order_id)    AS orders,
       sum(f.qty)                    AS units,
       sum(f.line_amount)            AS revenue,
       count(DISTINCT c.customer_id) AS customers
FROM gold.fact_order_lines f
JOIN gold.dim_customer c ON c.customer_sk = f.customer_sk
WHERE f.status <> 'CANCELLED' AND f.order_date IN (DATE'2026-03-01', DATE'2026-03-03', DATE'2026-03-04')
GROUP BY f.order_date, f.currency;

SELECT * FROM gold.daily_sales ORDER BY ALL;
```

```text
+----------+--------+------+-----+-------+---------+
|order_date|currency|orders|units|revenue|customers|
+----------+--------+------+-----+-------+---------+
|2026-03-01|CAD     |2     |2    |149.95 |2        |
|2026-03-01|USD     |1     |1    |35.50  |1        |
|2026-03-02|CAD     |2     |9    |200.00 |2        |
|2026-03-03|CAD     |2     |3    |70.00  |2        |
|2026-03-04|CAD     |1     |3    |43.00  |1        |
+----------+--------+------+-----+-------+---------+
```

March 1 dropped from 179.90 to 149.95 (one pair of socks less), March 3 now counts two customers (Eli is known),
March 4 appeared, and March 2 was not touched. Time travel still shows what the dashboard said before:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT 'before' AS v, * FROM gold.daily_sales VERSION AS OF 1 WHERE order_date = DATE'2026-03-01'
UNION ALL
SELECT 'after', * FROM gold.daily_sales WHERE order_date = DATE'2026-03-01'
ORDER BY ALL;
```

```text
+------+----------+--------+------+-----+-------+---------+
|v     |order_date|currency|orders|units|revenue|customers|
+------+----------+--------+------+-----+-------+---------+
|after |2026-03-01|CAD     |2     |2    |149.95 |2        |
|after |2026-03-01|USD     |1     |1    |35.50  |1        |
|before|2026-03-01|CAD     |2     |3    |179.90 |2        |
|before|2026-03-01|USD     |1     |1    |35.50  |1        |
+------+----------+--------+------+-----+-------+---------+
```

The fact table's history records the `MERGE` with the same counts, and rerunning step 5 with nothing new writes a
new version with identical rows:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
(spark.sql("DESCRIBE HISTORY gold.fact_order_lines")
 .selectExpr("version", "operation",
             "operationMetrics['numTargetRowsInserted'] AS numTargetRowsInserted",
             "operationMetrics['numTargetRowsUpdated'] AS numTargetRowsUpdated",
             "operationMetrics['numTargetRowsDeleted'] AS numTargetRowsDeleted")
 .orderBy("version").show(truncate=False))
```

```text
+-------+------------+---------------------+--------------------+--------------------+
|version|operation   |numTargetRowsInserted|numTargetRowsUpdated|numTargetRowsDeleted|
+-------+------------+---------------------+--------------------+--------------------+
|0      |CREATE TABLE|NULL                 |NULL                |NULL                |
|1      |WRITE       |NULL                 |NULL                |NULL                |
|2      |MERGE       |2                    |2                   |1                   |
+-------+------------+---------------------+--------------------+--------------------+

>>> rerun of step 5, then: rows that differ from the previous version
+------------+
|rows_changed|
+------------+
|0           |
+------------+
```

Time travel answers "what did we report on March 1?" only while the old version's files exist; `VACUUM` removes them
after the retention period ([chapter 4](04-Delta-Lake.md)). If finance must reproduce past reports for years, keep an
explicit snapshot (for example a `daily_sales_published` table with a `published_at` column) rather than relying on
time travel.

### Two REPLACE WHERE traps

**Trap 1: rows outside the predicate.** By default "every row that `query` returns must match `boolean_expression`.
If any row falls outside it, the `INSERT` fails and writes nothing"
([INSERT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-dml-insert-into)). Forgetting the
same filter in the `SELECT`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO gold.daily_sales
REPLACE WHERE order_date = DATE'2026-03-01'
SELECT ... FROM gold.fact_order_lines f JOIN gold.dim_customer c ON c.customer_sk = f.customer_sk
WHERE f.status <> 'CANCELLED'                     -- no date filter: every day comes back
GROUP BY f.order_date, f.currency;
```

```text
[DELTA_REPLACE_WHERE_MISMATCH] Written data does not conform to partial table overwrite condition or constraint '(order_date = DATE '2026-03-01')'.
```

This failure is a feature: it stops a job from writing other days' rows into a window it did not delete.

**Trap 2: an empty source deletes the day.** The selective overwrite page warns: "For empty source queries,
`REPLACE WHERE` might delete table rows"
([Selectively overwrite data with Delta Lake](https://docs.databricks.com/aws/en/delta/selective-overwrite)). Here the
job reads a staging view that is empty because an upstream step failed:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO gold.daily_sales
REPLACE WHERE order_date = DATE'2026-03-02'
SELECT f.order_date, f.currency, count(DISTINCT f.order_id), sum(f.qty), sum(f.line_amount),
       count(DISTINCT c.customer_id)
FROM fact_staging f JOIN gold.dim_customer c ON c.customer_sk = f.customer_sk
WHERE f.status <> 'CANCELLED' AND f.order_date = DATE'2026-03-02'
GROUP BY f.order_date, f.currency;
```

```text
>>> SELECT * FROM gold.daily_sales ORDER BY ALL
+----------+--------+------+-----+-------+---------+
|order_date|currency|orders|units|revenue|customers|
+----------+--------+------+-----+-------+---------+
|2026-03-01|CAD     |2     |2    |149.95 |2        |
|2026-03-01|USD     |1     |1    |35.50  |1        |
|2026-03-03|CAD     |2     |3    |70.00  |2        |
|2026-03-04|CAD     |1     |3    |43.00  |1        |
+----------+--------+------+-----+-------+---------+
```

No error, and March 2 is gone: the predicate deleted its row and the empty query inserted nothing. Delta can undo it,
because the previous version still exists:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
RESTORE TABLE gold.daily_sales TO VERSION AS OF 3;
SELECT * FROM gold.daily_sales ORDER BY ALL;
```

```text
+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
|table_size_after_restore|num_of_files_after_restore|num_removed_files|num_restored_files|removed_files_size|restored_files_size|
+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+
|3777                    |2                         |0                |1                 |0                 |1800               |
+------------------------+--------------------------+-----------------+------------------+------------------+-------------------+

+----------+--------+------+-----+-------+---------+
|order_date|currency|orders|units|revenue|customers|
+----------+--------+------+-----+-------+---------+
|2026-03-01|CAD     |2     |2    |149.95 |2        |
|2026-03-01|USD     |1     |1    |35.50  |1        |
|2026-03-02|CAD     |2     |9    |200.00 |2        |
|2026-03-03|CAD     |2     |3    |70.00  |2        |
|2026-03-04|CAD     |1     |3    |43.00  |1        |
+----------+--------+------+-----+-------+---------+
```

The guard is cheap: count the source rows (or compare with the silver row count for that day) before the write, and
fail the job instead of writing nothing over something. The same page documents two newer forms, `REPLACE USING`
(SQL in Databricks Runtime 16.3 and above) and `REPLACE ON` (SQL in Databricks Runtime 17.1 and above), which "do not
delete data" for empty source queries; they were not tested here.

### Proof: incremental equals a full rebuild

The strongest test of an incremental load is to compare it with a full rebuild from the same silver. In the Python
below, `FACT_SELECT` and `DAILY_SELECT` are the fact query of section 10.5 and the aggregate query of section 10.6
kept as strings with a `{where}` slot for the filter (`src/ch10/ch10_gold.py`):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
sql("CREATE TABLE gold.fact_full USING DELTA AS " + FACT_SELECT.format(where="true"))
sql("CREATE TABLE gold.daily_full USING DELTA AS "
    + DAILY_SELECT.format(where="true").replace("gold.fact_order_lines", "gold.fact_full"))
for inc, full in (("gold.fact_order_lines", "gold.fact_full"), ("gold.daily_sales", "gold.daily_full")):
    a = spark.table(inc)
    b = spark.table(full).select(*a.columns)
    print(f"{inc}: rows only in incremental = {a.exceptAll(b).count()}, only in full rebuild = {b.exceptAll(a).count()}")
```

```text
gold.fact_order_lines: rows only in incremental = 0, only in full rebuild = 0
gold.daily_sales: rows only in incremental = 0, only in full rebuild = 0
```

Run this comparison in tests and from time to time in production (on a recent window if the table is large): it
catches every class of incremental bug at once, from a missed change to a wrong delete.

The same restatement from PySpark uses the `replaceWhere` writer option
([Selectively overwrite data with Delta Lake](https://docs.databricks.com/aws/en/delta/selective-overwrite)):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
day = "2026-03-02"
restated = spark.sql(DAILY_SELECT.format(where=f"f.order_date = DATE'{day}'"))
(restated.write.format("delta").mode("overwrite")
    .option("replaceWhere", f"order_date = DATE'{day}'")
    .saveAsTable("gold.daily_sales"))
(spark.sql("DESCRIBE HISTORY gold.daily_sales")
 .select("version", "operation", "operationParameters.predicate").orderBy("version").show(truncate=False))
```

On a freshly built `gold.daily_sales` (in `s5_practice.py`), the commit records the predicate in its history, and
only March 2 was rewritten:

```text
+-------+------------+-----------------------------+
|version|operation   |predicate                    |
+-------+------------+-----------------------------+
|0      |CREATE TABLE|NULL                         |
|1      |WRITE       |NULL                         |
|2      |WRITE       |order_date = DATE'2026-03-02'|
+-------+------------+-----------------------------+

+----------+--------+------+-----+-------+---------+
|order_date|currency|orders|units|revenue|customers|
+----------+--------+------+-----+-------+---------+
|2026-03-01|CAD     |2     |3    |179.90 |2        |
|2026-03-01|USD     |1     |1    |35.50  |1        |
|2026-03-02|CAD     |2     |9    |200.00 |2        |
|2026-03-03|CAD     |2     |4    |99.95  |1        |
+----------+--------+------+-----+-------+---------+
```

!!! tip "In the interview"
    **"Finance says yesterday's revenue was wrong and silver has been fixed. How do you restate yesterday in gold?"**
    I recompute the affected fact rows (a `MERGE` of the changed orders, or a `REPLACE WHERE` on yesterday's date),
    then rerun the aggregate for exactly that day with
    `INSERT INTO gold.daily_sales REPLACE WHERE order_date = yesterday SELECT ... WHERE order_date = yesterday`. It is
    one atomic Delta commit, so dashboards see either the old
    or the new number, and a rerun gives the same result. Before writing I check the source is not empty, because
    `REPLACE WHERE` with an empty query deletes the day. Delta time travel (`VERSION AS OF`) still shows the number we
    published, for as long as the old files are kept. In [Lakeflow pipelines, formerly Delta Live
    Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) the same
    pattern is a `REPLACE WHERE` flow, and a one-off restatement is a predicate override on the update (or
    `REFRESH STREAMING TABLE ... WHERE` for a standalone streaming table in Databricks SQL).


## 10.8 Materialized views and REPLACE WHERE flows on Databricks

*Level: intermediate.*

Section 10.7 kept gold current with code you own: find the changes, `MERGE`, restate the days, guard against empty
sources. Databricks offers two declarative alternatives in which you write the query and the platform does the
bookkeeping. Chapter 7 (section 7.8) has Databricks' table mapping constructs to medallion layers; in short,
Databricks recommends an incremental `REPLACE WHERE` flow for "aggregations and data models" in gold and a
materialized view for "query acceleration and serving"
([When to use REPLACE WHERE vs. materialized
views](https://docs.databricks.com/aws/en/sql/mv-st/replace-where-vs-materialized-views)).

### Materialized views

A **materialized view** stores the result of its query and is refreshed when sources change. Defined in Databricks
SQL (a "standalone" materialized view), it is "a Unity Catalog managed table that physically stores the results of a
query, defined outside of a Lakeflow pipeline", and "a serverless pipeline is automatically created for every
standalone materialized view" to run its refreshes
([Use standalone materialized views](https://docs.databricks.com/aws/en/views/materialized)). Standalone
materialized views "run only in triggered mode": they refresh when asked, on a schedule, or when a source changes.

*Databricks only, not run here. Syntax from [Use standalone materialized views](https://docs.databricks.com/aws/en/views/materialized) and [REFRESH POLICY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-materialized-view-refresh-policy).*

```sql
-- refresh whenever an upstream table changes
CREATE OR REPLACE MATERIALIZED VIEW shop.gold.daily_sales_by_category
  TRIGGER ON UPDATE
AS SELECT f.order_date, p.category, f.currency,
          count(DISTINCT f.order_id) AS orders,
          sum(f.line_amount)         AS revenue
   FROM shop.gold.fact_order_lines f
   JOIN shop.gold.dim_product p ON p.product_sk = f.product_sk
   WHERE f.status <> 'CANCELLED'
   GROUP BY f.order_date, p.category, f.currency;

-- or nightly at 03:30 UTC (six-field cron: seconds minutes hours day-of-month month day-of-week)
CREATE OR REPLACE MATERIALIZED VIEW shop.gold.daily_sales_by_category
  SCHEDULE CRON '0 30 3 * * ?' AT TIME ZONE 'UTC'
AS SELECT ...;

-- fail instead of silently recomputing everything (Databricks SQL, Databricks Runtime 17.3 and above)
CREATE MATERIALIZED VIEW IF NOT EXISTS shop.gold.daily_sales_by_category
  REFRESH POLICY INCREMENTAL STRICT
AS SELECT ...;

REFRESH MATERIALIZED VIEW shop.gold.daily_sales_by_category;        -- synchronous by default
REFRESH MATERIALIZED VIEW shop.gold.daily_sales_by_category ASYNC;
REFRESH MATERIALIZED VIEW shop.gold.daily_sales_by_category FULL;   -- recompute everything
```

How a refresh works, from [Incremental refresh for materialized
views](https://docs.databricks.com/aws/en/ldp/incremental-refresh):

- **Same result either way.** "Materialized views guarantee equivalent results to batch queries"; an incremental
  refresh and a full recompute produce the same output.
- **Incremental only on serverless.** "Only materialized views updated using serverless pipelines can use incremental
  refresh. Materialized views that do not use serverless pipelines are always fully recomputed."
- **Cost-based by default.** "Databricks runs a cost analysis to choose the cheaper option between an incremental
  refresh and a full recompute." The `REFRESH POLICY` clause overrides this: `AUTO` (default), `INCREMENTAL` (prefer
  incremental, fall back to full), `INCREMENTAL STRICT` (fail rather than recompute), `FULL`.
- **The query shape decides.** Joins (inner, left, right, full outer), `GROUP BY`, `WHERE`, `UNION ALL`, CTEs, window
  functions with `PARTITION BY` and `QUALIFY` are listed as incrementally refreshable; some of them need **row
  tracking** on the source tables. Non-deterministic functions other than time functions in `WHERE` are not, and
  sums over `FLOAT` or `DOUBLE` "can produce non-deterministic results ... and force a full refresh", so the page
  advises casting to `DECIMAL`. The gold tables here already use `DECIMAL`.
- **Prepare the sources.** Databricks recommends enabling row tracking and deletion vectors on every source table
  (`ALTER TABLE ... SET TBLPROPERTIES (delta.enableRowTracking = true, delta.enableDeletionVectors = true)`).
- **Check what happened.** `EXPLAIN CREATE MATERIALIZED VIEW` tells you before creating whether a query can be
  incrementalized; afterwards the pipeline event log records the technique per update (`FULL_RECOMPUTE`, `NO_OP`,
  or an incremental one such as `ROW_BASED` or `GROUP_AGGREGATE`).

Inside a Lakeflow pipeline (formerly Delta Live Tables) the same object is declared with
`CREATE OR REFRESH MATERIALIZED VIEW` in SQL or the `@dp.materialized_view` decorator in Python, and the pipeline
must run on serverless compute for incremental refresh; [chapter 13](13-Declarative-Pipelines.md) covers pipelines,
refresh and full refresh in depth.

*Databricks only, not run here. Syntax from [Incremental refresh for materialized views](https://docs.databricks.com/aws/en/ldp/incremental-refresh) and [materialized_view](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-materialized-view).*

```python
from pyspark import pipelines as dp
from pyspark.sql import functions as F

@dp.materialized_view(refresh_policy="incremental")
def daily_sales_by_category():
    f = spark.read.table("shop.gold.fact_order_lines")
    p = spark.read.table("shop.gold.dim_product")
    return (f.where(F.col("status") != "CANCELLED")
             .join(p, "product_sk")
             .groupBy("order_date", "category", "currency")
             .agg(F.count_distinct("order_id").alias("orders"),
                  F.sum("line_amount").alias("revenue")))
```

Open-source Spark 4.2 also has materialized views, but only inside a Spark Declarative Pipelines project (chapter 13,
section 13.11 runs one); a direct statement is refused:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE MATERIALIZED VIEW mv1 AS SELECT d, sum(v) FROM s GROUP BY d;
```

```text
[UNSUPPORTED_FEATURE.CREATE_PIPELINE_DATASET_QUERY_EXECUTION] The feature is not supported: Direct execution of a CREATE ... MATERIALIZED VIEW query. To create a pipeline dataset, create and execute a pipeline with a SQL file containing your query attached in the pipeline definition. SQLSTATE: 0A000
```

!!! warning "Identity keys inside a materialized view"
    Because a materialized view may be fully recomputed at any refresh, Databricks warns that identity columns "might
    be recomputed during updates to a materialized views" and recommends them in pipelines "only with streaming
    tables" ([Pipeline limitations](https://docs.databricks.com/aws/en/ldp/limitations)). A materialized view that
    builds a dimension should derive its keys with a hash, or reference a dimension table maintained elsewhere.

### REPLACE WHERE flows

A **`REPLACE WHERE` flow** is the declarative form of section 10.7's step 5. You define a target streaming table, a
predicate (for example "the last 7 days") and a query; at each refresh "all rows in the target table that match the
predicate are deleted, the source query is recomputed for that same predicate range, and the new results are
inserted" ([REPLACE WHERE flows for standalone streaming
tables](https://docs.databricks.com/aws/en/sql/mv-st/flows-replace-where)).

*Databricks only, not run here. Syntax from [REPLACE WHERE flows for standalone streaming tables](https://docs.databricks.com/aws/en/sql/mv-st/flows-replace-where).*

```sql
CREATE OR REFRESH STREAMING TABLE shop.gold.daily_sales_7d
  SCHEDULE EVERY 1 DAY
  FLOW REPLACE WHERE order_date >= date_add(current_date(), -7) BY NAME
SELECT f.order_date, f.currency,
       count(DISTINCT f.order_id) AS orders,
       sum(f.line_amount)         AS revenue
FROM shop.gold.fact_order_lines f
WHERE f.status <> 'CANCELLED'
GROUP BY f.order_date, f.currency;

-- one-off restatement of an older range, without changing the definition
REFRESH STREAMING TABLE shop.gold.daily_sales_7d WHERE order_date BETWEEN '2026-01-01' AND '2026-01-31';
```

Points from that page worth knowing:

- "`BY NAME` is required." The predicate does not have to be repeated in the query: "The pipeline engine
  automatically applies it when reading from the source."
- Incremental refresh of the window "requires serverless compute", a predicate on base source columns, a
  deterministic predicate, and no outside DML in the current window. Keep the predicate column in the `GROUP BY` and
  use a moving lower bound only; a moving upper bound "can shift the window to include previously excluded rows,
  triggering a one-off fallback to full recomputation".
- **Full refresh is dangerous here.** "If a pipeline has been running for a year with a 7-day predicate, a full
  refresh results in the table containing only the last 7 days of data." Block it with the table property
  `pipelines.reset.allowed = 'false'`.
- In a Lakeflow pipeline the Python form is `@dp.table(replace_where=...)`, and a one-off restatement is a predicate
  override passed with the pipeline update
  ([Batch processing with REPLACE WHERE flows](https://docs.databricks.com/aws/en/ldp/flows-replace-where)).

The release status of `REPLACE WHERE` flows is not verified: the selective overwrite page (last updated Sep 11, 2026)
shows a "Beta" label next to its mention of them, while the two flow pages (last updated Oct 15, 2026) show no
release label in the text fetched for this chapter. Check the page before relying on them in production.

!!! tip "In the interview"
    **"Would you build gold aggregates as materialized views or as tables you MERGE into?"** A materialized view (in
    Databricks SQL or in [Lakeflow pipelines, formerly Delta Live
    Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) when the gold table is a query over
    silver or the star that readers hit often: I declare it, Databricks keeps it equal to the query and refreshes it
    incrementally on serverless when the query allows, otherwise it recomputes. When I need predictable cost or
    control over corrections, a table maintained by `REPLACE WHERE` (or a `REPLACE WHERE` flow) on a bounded window,
    or a `MERGE`. Databricks' own mapping recommends an incremental `REPLACE WHERE` flow for gold aggregations and
    data models, and materialized views for query acceleration and serving. I would not put identity keys in a
    materialized view, and I would set `REFRESH POLICY INCREMENTAL STRICT` if a surprise full recompute would break
    the SLA.

## 10.9 Metric views: the semantic layer

*Level: intermediate.*

Section 10.6 showed that "customers" cannot be summed from daily rows, and "revenue per customer" cannot be averaged
from daily ratios. Store those as columns and every dashboard that regroups them is wrong; leave them out and every
analyst writes their own definition. A **semantic layer** solves this: measures and dimensions are defined once, as
expressions over the detail, and the engine computes each measure correctly for whatever grouping the query asks for.

On Databricks this is **Unity Catalog metric views**. The docs call metric views "the core implementation of Unity
Catalog semantics", and explain the difference from a normal view: "Standard views lock in aggregations and
groupings at creation time. With a metric view, you define the metric once ... and users can group by any available
field. The query engine generates the correct computation"
([Unity Catalog metric views](https://docs.databricks.com/aws/en/uc-semantics/metric-views/)). A metric view is a
Unity Catalog securable created with `CREATE VIEW ... WITH METRICS LANGUAGE YAML`, and queried with the `MEASURE`
aggregate function. Version facts from
[Metric view feature availability](https://docs.databricks.com/aws/en/uc-semantics/metric-views/feature-availability):
"Metric views were introduced in Databricks Runtime 16.4"; the newest YAML specification version the page lists is 1.1
(0.1 was the
"initial release"); individual features need later runtimes. The page's version table is the place to check.

The Red Rock Supply star as a metric view, written to the shape of the example on
[Create a metric view](https://docs.databricks.com/aws/en/uc-semantics/metric-views/create):

*Databricks only, not run here. Syntax from [Create a metric view](https://docs.databricks.com/aws/en/uc-semantics/metric-views/create) and [Query metric views](https://docs.databricks.com/aws/en/uc-semantics/metric-views/query).*

```sql
CREATE OR REPLACE VIEW shop.gold.sales_metrics WITH METRICS LANGUAGE YAML AS
$$
  version: 1.1
  comment: "Red Rock Supply sales KPIs"
  source: shop.gold.fact_order_lines
  joins:
    - name: product
      source: shop.gold.dim_product
      'on': source.product_sk = product.product_sk
    - name: customer
      source: shop.gold.dim_customer
      'on': source.customer_sk = customer.customer_sk
  filter: source.status <> 'CANCELLED'
  fields:
    - name: Order Date
      expr: source.order_date
    - name: Currency
      expr: source.currency
    - name: Category
      expr: product.category
    - name: Customer City
      expr: customer.city
  measures:
    - name: Revenue
      expr: SUM(source.line_amount)
    - name: Orders
      expr: COUNT(DISTINCT source.order_id)
    - name: Customers
      expr: COUNT(DISTINCT customer.customer_id)
    - name: Revenue per Customer
      expr: SUM(source.line_amount) / COUNT(DISTINCT customer.customer_id)
$$;

SELECT `Order Date`, `Currency`, MEASURE(`Revenue`), MEASURE(`Customers`)
FROM shop.gold.sales_metrics
GROUP BY ALL
ORDER BY `Order Date`;
```

Rules from [Query metric views](https://docs.databricks.com/aws/en/uc-semantics/metric-views/query): "All measure
evaluations in a metric view query must use the `MEASURE` aggregate function"; you must list columns "rather than
using `SELECT *`"; and "Metric views cannot be directly joined with other tables at query time" (wrap the metric
view query in a CTE, then join). Metric views are used from AI/BI dashboards, Genie Agents, alerts, JDBC/ODBC and
external BI tools. **Materialization** can precompute chosen groupings into materialized views that a managed Lakeflow
pipeline keeps fresh, with the optimizer rewriting queries to use them; it requires serverless compute and
Databricks Runtime 17.3 or above, and is not allowed when the view or its sources use row filters, column masks or
ABAC policies ([Materialization for metric
views](https://docs.databricks.com/aws/en/uc-semantics/metric-views/materialization)).

Apache Spark 4.2 added metric views to open source: its release notes list "Metric views — declarative semantic
modeling with a `CREATE VIEW ... WITH METRICS` surface" (SPARK-54119)
([Spark Release 4.2.0](https://spark.apache.org/releases/spark-release-4-2-0.html)). The local engine accepted
YAML version 0.1 with the older `dimensions` keyword and rejected 1.1; joins were not tested, so the source here is
the one big table from section 10.6:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE OR REPLACE VIEW gold.sales_metrics WITH METRICS LANGUAGE YAML AS $$
version: 0.1
source: gold.sales_obt
filter: status <> 'CANCELLED'
dimensions:
  - name: order_date
    expr: order_date
  - name: currency
    expr: currency
  - name: category
    expr: category
measures:
  - name: revenue
    expr: SUM(line_amount)
  - name: orders
    expr: COUNT(DISTINCT order_id)
  - name: customers
    expr: COUNT(DISTINCT customer_id)
  - name: revenue_per_customer
    expr: SUM(line_amount) / COUNT(DISTINCT customer_id)
$$;

SELECT order_date, MEASURE(revenue) AS revenue, MEASURE(customers) AS customers
FROM gold.sales_metrics WHERE currency = 'CAD' GROUP BY ALL ORDER BY ALL;

SELECT currency, MEASURE(revenue) AS revenue, MEASURE(customers) AS customers,
       MEASURE(revenue_per_customer) AS revenue_per_customer
FROM gold.sales_metrics GROUP BY ALL ORDER BY ALL;
```

```text
+----------+-------+---------+
|order_date|revenue|customers|
+----------+-------+---------+
|2026-03-01|179.90 |2        |
|2026-03-02|200.00 |2        |
|2026-03-03|99.95  |1        |
+----------+-------+---------+

+--------+-------+---------+----------------------+
|currency|revenue|customers|revenue_per_customer  |
+--------+-------+---------+----------------------+
|CAD     |479.85 |4        |119.962500000000000000|
|USD     |35.50  |1        |35.500000000000000000 |
+--------+-------+---------+----------------------+
```

The same definition answers both groupings correctly: per day, the customer counts are 2, 2 and 1; over the whole
period it is 4 for CAD, not the 5 that summing daily rows gave in section 10.6, and the ratio is computed from the
totals (479.85 / 4), not averaged from daily ratios. Note that order 1011 (unknown customer, 30.00) is in the revenue
but not in the customer count, so "revenue per customer" is slightly overstated until the late customer arrives; a
semantic layer makes a definition consistent, not automatically correct. Treating a measure like a column fails:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT currency, sum(revenue) FROM gold.sales_metrics GROUP BY currency;
SELECT * FROM gold.sales_metrics;
```

```text
[MISSING_ATTRIBUTES.RESOLVED_ATTRIBUTE_MISSING_FROM_INPUT] Resolved attribute(s) "revenue" missing from "order_id", "day_name", "is_weekend", "order_ts", "status", "product_id", "product_name", "customer_id", "customer_name", "customer_city", "customer_country", "qty", "unit_price", "line_amount", "order_date", "currency", "category" ...
[INTERNAL_ERROR] The Spark SQL phase planning failed with an internal error. You hit a bug in Spark or the Spark plugins you use. ...
```

A measure is not a column of the view: `revenue` exists only inside `MEASURE()`. The `SELECT *` rule holds locally
too, but open-source Spark 4.2 reports it as an internal planning error rather than a clear message; the documented
rule is the one quoted above.

!!! tip "In the interview"
    **"What is a semantic layer, and does Databricks have one?"** It is where business metrics are defined once (the
    formula for revenue, active customers, margin) and computed correctly for any grouping, so dashboards and tools
    stop redefining them. On Databricks it is Unity Catalog metric views: YAML over a source table or star schema,
    created with `CREATE VIEW ... WITH METRICS`, queried with `MEASURE()`, governed like any Unity Catalog object, and
    optionally materialized. They matter most for non-additive measures such as distinct counts and ratios, which an
    aggregate table cannot roll up.

## 10.10 Serving gold to BI

*Level: intermediate.*

Gold is read far more than it is written, by people waiting for a dashboard. Four levers matter; the tuning details
are in [chapter 22](22-Performance-Tuning.md).

**The compute: a SQL warehouse.** BI tools and the SQL editor run on SQL warehouses. "Databricks recommends using
serverless SQL warehouses when available"
([Connect to a SQL warehouse](https://docs.databricks.com/aws/en/compute/sql-warehouse/)); the three types are
serverless, pro and classic, and only serverless has Intelligent Workload Management
([SQL warehouse types](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-types)). [Chapter
6](06-Compute.md) (section 6.4)
compares them.

**The engine: Photon.** "Photon is the default engine for all SQL warehouses"
([What is Photon?](https://docs.databricks.com/aws/en/compute/photon)), so gold served from a warehouse gets the
vectorized engine without configuration.

**The layout: liquid clustering on the filter columns.** Dashboards filter by date, then by a few attributes. The
clustering page says to "choose clustering keys based on the columns most commonly used in query filters", allows "up
to four clustering keys", and recommends automatic liquid clustering (`CLUSTER BY AUTO`, for Unity Catalog managed
tables in Databricks Runtime 15.4 LTS and above) to pick keys from the query history
([Use liquid clustering for tables](https://docs.databricks.com/aws/en/delta/clustering)). The fact table here is
clustered by `order_date` (section 10.5); this is also why copying the date onto the fact matters: a filter on
`dim_date` alone may not skip fact files (section 10.2).

**The model: informational keys the optimizer can trust.** Primary and foreign keys are not enforced on Databricks,
but declared with `RELY` they let the optimizer "rewrite queries, for example, by removing a `DISTINCT` operation on a
key column or eliminating a join that doesn't change the result"
([Optimize queries with RELY](https://docs.databricks.com/aws/en/sql/user/queries/query-optimization-constraints)).
A dashboard query that left-joins `dim_customer` but uses no customer column can skip the join entirely. `RELY`
optimizations "require pro or serverless SQL warehouses, or serverless compute". Primary and foreign keys are
"available for Unity Catalog and Delta Lake tables in Databricks Runtime 13.3 LTS and above", GA in 15.2 and above
([Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints)).

*Databricks only, not run here. Syntax from [Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints) and [Optimize queries with RELY](https://docs.databricks.com/aws/en/sql/user/queries/query-optimization-constraints).*

```sql
ALTER TABLE shop.gold.dim_customer ADD CONSTRAINT dim_customer_pk PRIMARY KEY (customer_sk) RELY;
ALTER TABLE shop.gold.dim_product  ADD CONSTRAINT dim_product_pk  PRIMARY KEY (product_sk) RELY;
ALTER TABLE shop.gold.fact_order_lines
  ADD CONSTRAINT fact_customer_fk FOREIGN KEY (customer_sk) REFERENCES shop.gold.dim_customer;
```

Each primary key column must be "a column of the subject relation defined as `NOT NULL`"
([ADD CONSTRAINT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-table-add-constraint)).
`customer_sk` is declared `NOT NULL`, but `product_sk` in section 10.4 is not (locally the identity column shows as
nullable), so declare it `NOT NULL` when creating `dim_product` before adding its primary key.

Locally, open-source Delta refuses the constraint
(`[UNSUPPORTED_FEATURE.TABLE_OPERATION] ... does not support table constraint`), which is why the keys are tested by
queries in section 10.12 instead.

!!! warning "`RELY` on a key that is not unique gives wrong answers"
    The `RELY` page is explicit: "It is the user's responsibility to check whether a constraint is satisfied. Relying
    on a constraint that is not satisfied can lead to incorrect query results." Run the uniqueness tests of section
    10.12 on every load before (or instead of) trusting `RELY`. A hash key collision is exactly such a case.

## 10.11 Data products, sharing and ML features

*Level: intermediate.*

A **data product** is a set of gold tables managed like a product for its consumers: an owner, a documented
contract (schema, grain, definitions, freshness), tests, and changes announced instead of surprises. It is a way of
working (it comes from the data mesh idea in chapter 7, section 7.12), not a Databricks object. Unity Catalog supplies
the pieces: comments and tags on tables and columns, lineage, grants per schema, and certification. The Unity Catalog
semantics page lists "Certification and deprecation: Signals that mark a data asset as trusted or outdated"
([Unity Catalog semantics](https://docs.databricks.com/aws/en/uc-semantics/)). Inside the organization, consumers of
the same metastore simply get `SELECT` on `shop.gold`.

**Sharing outside the organization: OpenSharing.** "OpenSharing is the secure data sharing platform in Databricks
that lets you share data and AI assets with users outside your organization, regardless of whether they use
Databricks" ([What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/)). It is the new name of Delta
Sharing: a Databricks blog post of November 5, 2026 says "Delta Sharing has evolved into OpenSharing" and that
"Existing Delta Sharing setups keep working"
([From Delta Sharing to
OpenSharing](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next)).
Data is shared without copying it: a **share** is "a read-only collection of tables and table partitions" (the
same page lists views, materialized views, metric views, volumes, models and notebook files as other assets a share
can hold; notebooks, volumes and models need a Databricks recipient), a **recipient** is the organization it
is shared with, and a provider grants the recipient access to the share. With Databricks-to-Databricks sharing the
recipient needs no token; with open sharing the provider issues a bearer token or uses OIDC federation, and the
recipient can read with Spark, pandas, Power BI and other clients.

*Databricks only, not run here. Syntax from [Create shares for OpenSharing](https://docs.databricks.com/aws/en/opensharing/create-share), [ALTER SHARE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-share), [CREATE RECIPIENT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-recipient) and [GRANT ON SHARE](https://docs.databricks.com/aws/en/sql/language-manual/security-grant-share).*

```sql
CREATE SHARE IF NOT EXISTS red_rock_sales COMMENT "Daily sales for our distribution partner";

ALTER SHARE red_rock_sales ADD TABLE shop.gold.daily_sales WITH HISTORY;

-- a Databricks recipient, identified by its metastore's sharing identifier
CREATE RECIPIENT IF NOT EXISTS partner_org USING ID '<cloud>:<region>:<metastore-uuid>';

GRANT SELECT ON SHARE red_rock_sales TO RECIPIENT partner_org;
```

Share the aggregate or a view, not the raw fact, when the partner should not see order-level or customer-level
data. `WITH HISTORY` lets the recipient use time travel and streaming reads; the `ALTER SHARE` page says it is "the
default" on Databricks SQL and Databricks Runtime 16.2 and above, and that a recipient who wants `table_changes()`
needs Change Data Feed enabled on the table before it is shared.

**Gold for machine learning.** Models need one row per entity (a customer) with features, and training data must use
feature values **as of** each label's time, or the model learns from the future. Gold already has the pieces: the
fact table holds events with timestamps, and the SCD Type 2 dimension says what was true when. Databricks Feature
Store builds on them: a **feature table** is a Delta table in Unity Catalog "that has a primary key", which you
populate yourself; for new projects Databricks recommends **Feature Views**, declared features whose pipelines
Databricks manages; and the Feature Store provides "point-in-time feature joins"
([Databricks Feature Store](https://docs.databricks.com/aws/en/machine-learning/feature-store/)). A gold
`customer_ltv`-style aggregate (orders, revenue, first and last order date per customer, practice question Q22) is a
typical source for such features.

## 10.12 Testing gold

*Level: expert.*

Gold is where a wrong number becomes a wrong decision, and Databricks does not enforce keys (section 10.2), so the
tests are yours. They fall into three groups:

- **Shape**: the grain is unique; keys are not null; every foreign key finds its dimension row; each Type 2 customer
  has exactly one current row.
- **Reconciliation**: gold adds up to silver. Lines match silver order items, each order's lines add up to its
  silver amount, the aggregate equals the fact grouped again, and total revenue per currency equals silver's.
- **Plausibility**: no negative quantities, no gaps in dates, the number of fact rows on the unknown member is small
  (a warning, not a failure: late customers are normal).

Each check below is a query that returns the number of offending rows; 0 passes. The script runs them all and raises
if any "fail" check finds rows, so the job (a task in Lakeflow Jobs, formerly Databricks Jobs, chapter 15) stops
before a dashboard reads bad
data.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
CHECKS = [
    ("fact grain unique (order_id, product_sk)", "fail", """
        SELECT count(*) FROM (SELECT order_id, product_sk FROM gold.fact_order_lines
                              GROUP BY ALL HAVING count(*) > 1)"""),
    ("fact -> dim_customer (no orphans)", "fail", """
        SELECT count(*) FROM gold.fact_order_lines f
        LEFT ANTI JOIN gold.dim_customer c ON c.customer_sk = f.customer_sk"""),
    # ... the same for dim_product and dim_date
    ("dim_customer: one current row per customer", "fail", """
        SELECT count(*) FROM (SELECT customer_id FROM gold.dim_customer WHERE customer_id IS NOT NULL
                              GROUP BY customer_id HAVING count_if(is_current) <> 1)"""),
    ("lines: silver order_items == fact", "fail", """
        SELECT count(*) FROM (
          SELECT i.order_id, i.product_id, i.qty FROM silver.order_items i
          FULL OUTER JOIN (SELECT f.order_id, p.product_id, f.qty FROM gold.fact_order_lines f
                           JOIN gold.dim_product p ON p.product_sk = f.product_sk) g
            ON g.order_id = i.order_id AND g.product_id = i.product_id
          WHERE NOT (i.qty <=> g.qty))"""),
    ("order totals: sum(lines) == silver.orders.amount", "fail", """
        SELECT count(*) FROM silver.orders o
        LEFT JOIN (SELECT order_id, sum(line_amount) AS lines FROM gold.fact_order_lines GROUP BY order_id) f
          ON f.order_id = o.order_id
        WHERE NOT (o.amount <=> f.lines)"""),
    ("daily_sales == fact, per day and currency", "fail", """
        SELECT count(*) FROM (
          (SELECT * FROM gold.daily_sales EXCEPT ALL (<the daily query over the fact>))
          UNION ALL
          ((<the daily query over the fact>) EXCEPT ALL SELECT * FROM gold.daily_sales))"""),
    ("total revenue: silver == daily_sales", "fail", """
        SELECT count(*) FROM (
          SELECT currency, sum(amount) AS r FROM silver.orders WHERE status <> 'CANCELLED' GROUP BY currency) s
        FULL OUTER JOIN (SELECT currency, sum(revenue) AS r FROM gold.daily_sales GROUP BY currency) g
          USING (currency)
        WHERE NOT (s.r <=> g.r)"""),
    ("no negative quantities or amounts", "fail", """
        SELECT count(*) FROM gold.fact_order_lines WHERE qty <= 0 OR line_amount < 0"""),
    ("fact rows on the unknown customer", "warn", """
        SELECT count(*) FROM gold.fact_order_lines WHERE customer_sk = -1"""),
]

def run_checks():
    rows = []
    for name, level, q in CHECKS:
        bad = spark.sql(q).first()[0]
        status = "PASS" if bad == 0 else ("WARN" if level == "warn" else "FAIL")
        rows.append((name, bad, status))
    spark.createDataFrame(rows, "check STRING, bad_rows BIGINT, status STRING").show(truncate=False)
    failed = [r[0] for r in rows if r[2] == "FAIL"]
    if failed:
        raise AssertionError(f"{len(failed)} gold check(s) failed: {failed}")
```

The `<=>` comparisons matter: with `=`, a silver order with no fact lines at all compares `amount = NULL`, which is
`NULL`, not true, and the `WHERE NOT (...)` would let it through. The `FULL OUTER JOIN` catches lines missing on
either side. On the gold layer as built in sections 10.4 to 10.6:

```text
+------------------------------------------------+--------+------+
|check                                           |bad_rows|status|
+------------------------------------------------+--------+------+
|fact grain unique (order_id, product_sk)        |0       |PASS  |
|fact -> dim_customer (no orphans)               |0       |PASS  |
|fact -> dim_product (no orphans)                |0       |PASS  |
|fact -> dim_date (no orphans)                   |0       |PASS  |
|dim_customer: one current row per customer      |0       |PASS  |
|lines: silver order_items == fact               |0       |PASS  |
|order totals: sum(lines) == silver.orders.amount|0       |PASS  |
|daily_sales == fact, per day and currency       |0       |PASS  |
|total revenue: silver == daily_sales            |0       |PASS  |
|no negative quantities or amounts               |0       |PASS  |
|fact rows on the unknown customer               |1       |WARN  |
+------------------------------------------------+--------+------+
```

Order 1011 is the one fact row on the unknown customer: a warning, as intended.

Now two realistic failures. First, someone reruns the March 2 fact load as a plain `INSERT` instead of
`REPLACE WHERE`, so March 2's lines are in the fact twice:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO gold.fact_order_lines
SELECT ...                                   -- the fact query from section 10.5
WHERE o.order_date = DATE'2026-03-02';       -- March 2 was already loaded
```

```text
+------------------------------------------------+--------+------+
|check                                           |bad_rows|status|
+------------------------------------------------+--------+------+
|fact grain unique (order_id, product_sk)        |5       |FAIL  |
|fact -> dim_customer (no orphans)               |0       |PASS  |
|fact -> dim_product (no orphans)                |0       |PASS  |
|fact -> dim_date (no orphans)                   |0       |PASS  |
|dim_customer: one current row per customer      |0       |PASS  |
|lines: silver order_items == fact               |0       |PASS  |
|order totals: sum(lines) == silver.orders.amount|3       |FAIL  |
|daily_sales == fact, per day and currency       |2       |FAIL  |
|total revenue: silver == daily_sales            |0       |PASS  |
|no negative quantities or amounts               |0       |PASS  |
|fact rows on the unknown customer               |1       |WARN  |
+------------------------------------------------+--------+------+
AssertionError: 3 gold check(s) failed: ['fact grain unique (order_id, product_sk)', 'order totals: sum(lines) == silver.orders.amount', 'daily_sales == fact, per day and currency']
```

One mistake, three failing checks. The grain test names the cause (the five March 2 lines now appear twice), the
order totals show the damage (orders 1008, 1009 and 1010 add up to twice their amount), and `daily_sales` no longer
matches the fact it was built from. Two checks you might expect to fail pass. The line reconciliation joins on
`(order_id, product_id)`, so each duplicate finds the same silver line with the same quantity: duplicates are
invisible to it, which is why the grain check is listed first. The silver-to-`daily_sales` total passes because the
aggregate has not been rebuilt yet; rebuilt from the doubled fact, it would fail too. The repair is
the idempotent form, `INSERT INTO gold.fact_order_lines REPLACE WHERE order_date = DATE'2026-03-02' SELECT ...`.
Second, silver corrects order 1008 from three boxes of energy bars to two, and the gold refresh does not run:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
UPDATE silver.order_items SET qty = 2 WHERE order_id = 1008;
UPDATE silver.orders SET amount = 28.00 WHERE order_id = 1008;
```

```text
+------------------------------------------------+--------+------+
|check                                           |bad_rows|status|
+------------------------------------------------+--------+------+
|fact grain unique (order_id, product_sk)        |0       |PASS  |
|fact -> dim_customer (no orphans)               |0       |PASS  |
|fact -> dim_product (no orphans)                |0       |PASS  |
|fact -> dim_date (no orphans)                   |0       |PASS  |
|dim_customer: one current row per customer      |0       |PASS  |
|lines: silver order_items == fact               |1       |FAIL  |
|order totals: sum(lines) == silver.orders.amount|1       |FAIL  |
|daily_sales == fact, per day and currency       |0       |PASS  |
|total revenue: silver == daily_sales            |1       |FAIL  |
|no negative quantities or amounts               |0       |PASS  |
|fact rows on the unknown customer               |1       |WARN  |
+------------------------------------------------+--------+------+
AssertionError: 3 gold check(s) failed: ['lines: silver order_items == fact', 'order totals: sum(lines) == silver.orders.amount', 'total revenue: silver == daily_sales']
```

This time the shape checks pass and only reconciliation sees it: gold is internally consistent but no longer agrees
with silver. Both kinds of check are needed.

The order-total reconciliation in PySpark, for a test suite written with DataFrames (the run below is on the good
build, before the two breaks):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql import functions as F

lines = (spark.table("gold.fact_order_lines").groupBy("order_id")
         .agg(F.sum("line_amount").alias("lines")))
mismatch = (spark.table("silver.orders").join(lines, "order_id", "left")
            .where(~F.col("amount").eqNullSafe(F.col("lines"))))
print("orders whose lines do not add up:", mismatch.count())
```

```text
orders whose lines do not add up: 0
```

On Databricks, the same rules can live closer to the data: expectations on a Lakeflow pipeline table, `CHECK` and
`NOT NULL` constraints on Delta tables ([chapter 14](14-Data-Quality-and-CDC.md)). Cross-table checks such as
reconciliation and orphan keys are not row rules, so they stay as queries like these, run after each load.

!!! tip "In the interview"
    **"How do you test a gold layer?"** Three layers of checks after every load: shape (grain uniqueness, non-null
    keys, no orphan foreign keys, one current row per Type 2 key), reconciliation with silver (row counts and sums by
    day and currency must match, and each order's lines must add up to the order total), and plausibility (no
    negative amounts, unknown-member rows below a threshold). A failing check fails the job before the dashboard
    refreshes. And I regularly compare the incremental result with a full rebuild on a recent window.

## 10.13 Practice questions

*Level: mixed.*

**Q1. In two sentences, what is the gold layer for, according to Databricks, and how does it differ from silver?**

??? success "Answer"
    Gold holds business-level tables, "highly refined views of the data that drive downstream analytics, dashboards,
    ML, and applications": dimensional models, aggregates and defined measures, optimized for queries. Silver keeps
    one validated, non-aggregated row per record and is the source gold is rebuilt from.

    **Why:** the medallion page lists gold as aggregated, aligned with business logic and optimized for performance,
    and says gold "is where you'll model your data for reporting and analytics using a dimensional model".

**Q2. Sort these columns of an order-line table into facts (measures), dimension keys and attributes: `qty`,
`customer_sk`, `line_amount`, `order_date`, `product_sk`, `unit_price`, `status`, `order_id`.**

??? success "Answer"
    Measures: `qty`, `line_amount` (additive). `unit_price` is a non-additive measure (you average or recompute it,
    never sum it). Dimension keys: `customer_sk`, `product_sk`, and `date_key` derived from `order_date`.
    `order_id` is a degenerate dimension (an identifier kept on the fact, with no table of its own). `status` and
    `order_date` are attributes kept on the fact because almost every query filters on them.

    **Why:** facts are numbers you aggregate; dimensions are context you filter and group by. Putting the most-filtered
    attributes on the fact helps data skipping, because filters on another table's columns may not skip fact files.

**Q3. What is the grain of a fact table, and why do you decide it before anything else?**

??? success "Answer"
    The grain is what one row means in business words, for example "one row per order line". It decides which
    dimensions can attach, which measures are valid, the unique key, and which questions the table can answer. Choose
    the most atomic grain the source supports, because a fine grain can be rolled up and a coarse one cannot be split.

    **Why:** mixing grains (an order total on a line table) is the root of double counting.

**Q4. What does this return for 2026-03-02, and why?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT o.order_date, sum(o.amount)
FROM silver.orders o JOIN silver.order_items i ON i.order_id = o.order_id
WHERE o.status <> 'CANCELLED' GROUP BY ALL;
```

??? success "Answer"
    516.00 instead of 200.00 (the run in section 10.3). Order 1009 has three lines, so the join repeats its header
    amount 158.00 three times: 42.00 + 3 x 158.00 = 516.00. Fix: sum `amount` from `silver.orders` alone, or sum
    `qty * unit_price` at the line grain.

    **Why:** a join to a finer grain multiplies the coarser rows (fan-out); a measure may only be summed at the grain
    where it lives.

**Q5. Red Rock Supply starts charging a 9.00 shipping fee per order. Where does it go in the gold model?**

??? success "Answer"
    Not as a column repeated on every order line. Either a separate fact at the order grain (`fact_orders`, one row
    per order, with the fee), or an allocation to lines by an agreed rule (for example in proportion to line amount),
    documented and tested so the allocated pieces add back up to 9.00 per order.

    **Why:** a header measure on a line-grain table is double counted as soon as someone sums it.

**Q6. What is a conformed dimension? Give an example from Red Rock Supply.**

??? success "Answer"
    A dimension shared by several fact tables with the same keys and meaning. `gold.dim_customer` and `gold.dim_date`
    used by both `fact_order_lines` and a future `fact_returns`, so "net revenue by city" joins two facts through the
    same customer versions and the same calendar.

    **Why:** two separate customer dimensions would give two answers to "which city", and the facts could not be
    compared.

**Q7. The source already has `customer_id`. Why add a surrogate key in gold?**

??? success "Answer"
    In a Type 2 dimension one customer has several rows, so `customer_id` is not unique there; the version key is.
    A surrogate key also isolates gold from source key reuse or merges between systems, and lets the fact point at a
    special unknown member (`-1`) instead of `NULL`.

    **Why:** the fact must reference one dimension row exactly, including the version valid at the event time.

**Q8. Identity column or hash for a surrogate key on Databricks? Give two arguments each way.**

??? success "Answer"
    Identity: small sequential `BIGINT`s, no collision risk. Against: values depend on load order and change on a
    rebuild (section 10.4 showed product 1 going from key 2 to key 5), and Databricks says declaring one "disables
    concurrent transactions" on the table. Hash (`xxhash64`, or `sha2` for very large tables): deterministic, so
    rebuilds and backfills reproduce the same keys and a fact can compute a Type 1 key without a lookup; parallel
    writers need no coordination. Against: collisions are possible and must be tested, and `sha2` strings are larger
    to store and join.

    **Why:** the trade-off is stability versus compactness; gold layers that must be rebuildable from silver often
    favor hashes.

**Q9. Two jobs load new products into `gold.dim_product`, which has an identity column, at the same time. What does
Databricks say about this?**

??? success "Answer"
    It is not supported: "Declaring an identity column on a Delta Lake table disables concurrent transactions. Only
    use identity columns in use cases where concurrent writes to the target table aren't required." Serialize the
    writers (one task loads the dimension), or switch to a hash key.

    **Why:** the identity counter is table-level state; Databricks documents concurrent transactions as unsupported on
    such tables.

**Q10. Write a dimension whose surrogate key is generated, but which also has a fixed `-1` unknown member. Show what
it contains.**

??? success "Answer"
    Use `GENERATED BY DEFAULT AS IDENTITY`, which accepts an explicit value when you give one:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    CREATE TABLE gold.dim_channel (
      channel_sk BIGINT GENERATED BY DEFAULT AS IDENTITY,
      channel    STRING NOT NULL) USING DELTA;
    INSERT INTO gold.dim_channel VALUES (-1, 'Unknown');
    INSERT INTO gold.dim_channel (channel) VALUES ('web');
    INSERT INTO gold.dim_channel (channel) VALUES ('mobile');
    SELECT * FROM gold.dim_channel ORDER BY channel_sk;
    ```

    ```text
    +----------+-------+
    |channel_sk|channel|
    +----------+-------+
    |-1        |Unknown|
    |1         |web    |
    |2         |mobile |
    +----------+-------+
    ```

    **Why:** with `GENERATED ALWAYS` the explicit `-1` is rejected
    (`DELTA_IDENTITY_COLUMNS_EXPLICIT_INSERT_NOT_SUPPORTED`, section 10.4). Values are "unique but are not guaranteed
    to be contiguous", so never rely on them being 1, 2, 3.

**Q11. Can you declare an identity column in a `CREATE TABLE ... AS SELECT`?**

??? success "Answer"
    No. Create the table with its schema first, then `INSERT ... SELECT`. Locally the parser rejects any schema in a
    CTAS:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    CREATE TABLE x (sk BIGINT GENERATED ALWAYS AS IDENTITY, name STRING) USING DELTA
    AS SELECT 'tent' AS name;
    ```

    ```text
    Operation not allowed: Schema may not be specified in a Create Table As Select (CTAS) statement.
    == SQL (line 1, position 1) ==
    CREATE TABLE x (sk BIGINT GENERATED ALWAYS AS IDENTITY, name STRING) USING DELTA
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
              AS SELECT 'tent' AS name
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ```

    **Why:** Databricks: "You cannot define schema, identity column constraints, or any other table specifications
    when using a `CREATE TABLE table_name AS SELECT` (CTAS) statement."

**Q12. A teammate "cleans up" `gold.dim_product` (identity keys) with `CREATE OR REPLACE TABLE` and a reload, but
leaves the fact table alone. What breaks?**

??? success "Answer"
    The reload assigns new identity values in whatever order the rows are written, so existing `product_sk` values in
    the fact now point at different products (in section 10.4, key 1 moved from the tent to the bear canister).
    Revenue by category becomes silently wrong; nothing fails. Fix: restore the dimension to its previous version with
    `RESTORE TABLE ... TO VERSION AS OF`, and either never rebuild identity dimensions alone or switch to hash keys.

    **Why:** an identity key records load history, not the data.

**Q13. Why does the fact table use `-1` for an unknown customer instead of `NULL`?**

??? success "Answer"
    `NULL` foreign keys drop rows from every inner join to the dimension, so revenue disappears without an error. A
    `-1` row in `dim_customer` ("Unknown customer") keeps the totals right, makes the gap visible in reports, and is
    easy to count in a check and to fix later (section 10.7 re-resolved order 1011 when customer 11 arrived).

    **Why:** the fact's totals must not depend on the dimension being complete.

**Q14. Write the join condition that picks the customer version valid when an order was placed. Why `<` for
`valid_to` and not `<=`?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    LEFT JOIN gold.dim_customer c
      ON  c.customer_id = o.customer_id
      AND o.order_ts >= c.valid_from
      AND (o.order_ts < c.valid_to OR c.valid_to IS NULL)
    ```

    A closed version's `valid_to` equals the next version's `valid_from`. With `<=`, an order placed exactly at the
    change time would match both versions and appear twice in the fact. The half-open interval
    `[valid_from, valid_to)` gives exactly one match. `valid_to IS NULL` is the current version.

    **Why:** this is the "as-was" lookup; section 10.5 used it to put order 1001 (10:15) on Ava's Banff version
    (from 10:00).

**Q15. What do these two counts return, and which one answers "how many customers"?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT count(DISTINCT customer_sk) AS distinct_customer_sk, count(DISTINCT customer_id) AS distinct_customer_id
FROM VALUES (1001, -1435483106282796086, 7),
            (1020, -7238947835605265590, 7) AS t(order_id, customer_sk, customer_id);
```

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +--------------------+--------------------+
    |distinct_customer_sk|distinct_customer_id|
    +--------------------+--------------------+
    |2                   |1                   |
    +--------------------+--------------------+
    ```

    `customer_id` answers the question. The two keys are two versions of Ava (Banff and Canmore), so counting
    surrogate keys counts versions.

    **Why:** in a Type 2 dimension the surrogate key identifies a version, not a person.

**Q16. `gold.daily_sales` has a `customers` column. Summed over March 1 to 3 (CAD) it gives 5; the true number is 4.
Why, and how should "customers per month" be computed?**

??? success "Answer"
    A distinct count is non-additive: Ava bought on March 1 and March 3 and is counted in both days. Compute it from
    the fact at the grain asked (`count(DISTINCT customer_id)` grouped by month), store a mergeable sketch for
    approximate counts, or define it once in a metric view, which always computes it from the detail (section 10.9
    returned 4).

    **Why:** sums of distinct counts double count anyone who appears in more than one group.

**Q17. Your analysts want one wide table so they never write joins; your architect wants a star schema. What do you
do on Databricks?**

??? success "Answer"
    Keep the star schema as the governed model (shared dimensions, Type 1 changes touch one row, both as-was and as-is
    are possible) and build a wide table or a materialized view from the star for the heaviest dashboards. The wide
    table benefits from data skipping and clustering on every attribute; Databricks notes that filters on another
    table's columns may not skip data. It is rebuildable because it is derived.

    **Why:** Databricks' data modeling page supports both: star and snowflake "perform well on Databricks", and more
    fields in one table lets the optimizer skip data using file statistics.

**Q18. A new team proposes a fully normalized (3NF) gold model on Databricks. What does Databricks recommend?**

??? success "Answer"
    Databricks "recommends against using a heavily normalized model such as third normal form (3NF)" for a new
    lakehouse; star or snowflake schemas "perform well on Databricks, as there are fewer joins present in standard
    queries and fewer keys to keep in sync". An existing 3NF model can be queried, but evaluate performance before
    migrating it as is.

    **Why:** from the page [Data modeling](https://docs.databricks.com/aws/en/transform/data-modeling).

**Q19. Are primary and foreign keys enforced on Databricks? What does `RELY` add, and what is the risk?**

??? success "Answer"
    No: "Primary and foreign keys are informational and not enforced." (`NOT NULL` and `CHECK` constraints are
    enforced.) With `RELY`, the optimizer may use a primary key or unique constraint to remove a `DISTINCT` or to
    eliminate a join that cannot change the result; this needs a pro or serverless SQL warehouse or serverless
    compute. The risk: "Relying on a constraint that is not satisfied can lead to incorrect query results", so test
    uniqueness on every load.

    **Why:** the database does not check the key; the optimizer simply believes you.

**Q20. Write the SQL: for each day, the top product category by CAD revenue (cancelled orders excluded), using the
star schema.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT f.order_date, p.category, sum(f.line_amount) AS revenue
    FROM gold.fact_order_lines f
    JOIN gold.dim_product p ON p.product_sk = f.product_sk
    WHERE f.status <> 'CANCELLED' AND f.currency = 'CAD'
    GROUP BY ALL
    QUALIFY row_number() OVER (PARTITION BY f.order_date ORDER BY revenue DESC, p.category) = 1
    ORDER BY f.order_date;
    ```

    ```text
    +----------+--------+-------+
    |order_date|category|revenue|
    +----------+--------+-------+
    |2026-03-01|Camping |120.00 |
    |2026-03-02|Camping |140.00 |
    |2026-03-03|Hiking  |40.00  |
    +----------+--------+-------+
    ```

    **Why:** `QUALIFY` filters on a window function computed over the grouped rows; the second sort key makes ties
    deterministic. The window orders by the `revenue` alias: locally, repeating the aggregate inside the window
    (`ORDER BY sum(f.line_amount)`) failed with `UNRESOLVED_COLUMN`. Window functions are covered in the SQL course
    ([Window functions](../../databases/sql/13-Window-Functions-Ranking.md)).

**Q21. Write Q20 in PySpark.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    f = spark.table("gold.fact_order_lines")
    p = spark.table("gold.dim_product")
    by_cat = (f.where((F.col("status") != "CANCELLED") & (F.col("currency") == "CAD"))
              .join(p, "product_sk")
              .groupBy("order_date", "category").agg(F.sum("line_amount").alias("revenue")))
    w = Window.partitionBy("order_date").orderBy(F.col("revenue").desc(), "category")
    (by_cat.withColumn("rn", F.row_number().over(w)).where("rn = 1").drop("rn")
     .orderBy("order_date").show(truncate=False))
    ```

    ```text
    +----------+--------+-------+
    |order_date|category|revenue|
    +----------+--------+-------+
    |2026-03-01|Camping |120.00 |
    |2026-03-02|Camping |140.00 |
    |2026-03-03|Hiking  |40.00  |
    +----------+--------+-------+
    ```

    **Why:** PySpark has no `QUALIFY`; compute the row number in a column and filter on it.

**Q22. Write the SQL for a customer lifetime value table: per customer, orders, revenue, first and last order date,
labelled with the customer's current name and city (CAD only).**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT cur.customer_id, cur.name, cur.city AS city_now,
           count(DISTINCT f.order_id) AS orders, sum(f.line_amount) AS revenue,
           min(f.order_date) AS first_order, max(f.order_date) AS last_order
    FROM gold.fact_order_lines f
    JOIN gold.dim_customer v   ON v.customer_sk = f.customer_sk
    JOIN gold.dim_customer cur ON cur.customer_id = v.customer_id AND cur.is_current
    WHERE f.status <> 'CANCELLED' AND f.currency = 'CAD'
    GROUP BY ALL ORDER BY revenue DESC;
    ```

    ```text
    +-----------+------------+---------+------+-------+-----------+----------+
    |customer_id|name        |city_now |orders|revenue|first_order|last_order|
    +-----------+------------+---------+------+-------+-----------+----------+
    |10         |Dev Patel   |Vancouver|1     |158.00 |2026-03-02 |2026-03-02|
    |7          |Ava Chen    |Canmore  |2     |129.85 |2026-03-01 |2026-03-03|
    |8          |Ben Ortiz   |Denver   |1     |120.00 |2026-03-01 |2026-03-01|
    |9          |Chloe Martin|Moab     |1     |42.00  |2026-03-02 |2026-03-02|
    +-----------+------------+---------+------+-------+-----------+----------+
    ```

    **Why:** the fact points at the version valid at order time (`v`); joining again to the current row (`cur`) gives
    the "as-is" labels. Order 1011, on the unknown member, has no current row and drops out of this inner join; use a
    left join and label it if it must be counted.

**Q23. Write monthly revenue from `gold.daily_sales`. Which of its columns can you not roll up this way?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT date_trunc('MONTH', order_date) AS month, currency, sum(revenue) AS revenue, sum(orders) AS orders
    FROM gold.daily_sales GROUP BY ALL ORDER BY ALL;
    ```

    ```text
    +-------------------+--------+-------+------+
    |month              |currency|revenue|orders|
    +-------------------+--------+-------+------+
    |2026-03-01 00:00:00|CAD     |479.85 |6     |
    |2026-03-01 00:00:00|USD     |35.50  |1     |
    +-------------------+--------+-------+------+
    ```

    `revenue`, `units` and `orders` add up (an order has one date). `customers` does not (Q16).

    **Why:** only additive measures can be re-aggregated from an aggregate table.

**Q24. Write the SQL: CAD revenue by category, split into weekend and weekday orders.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT p.category, d.is_weekend, sum(f.line_amount) AS revenue
    FROM gold.fact_order_lines f
    JOIN gold.dim_date d    ON d.date_key = f.date_key
    JOIN gold.dim_product p ON p.product_sk = f.product_sk
    WHERE f.status <> 'CANCELLED' AND f.currency = 'CAD'
    GROUP BY ALL ORDER BY ALL;
    ```

    ```text
    +--------+----------+-------+
    |category|is_weekend|revenue|
    +--------+----------+-------+
    |Apparel |false     |29.95  |
    |Apparel |true      |59.90  |
    |Camping |false     |140.00 |
    |Camping |true      |120.00 |
    |Climbing|false     |30.00  |
    |Food    |false     |42.00  |
    |Hiking  |false     |40.00  |
    |Lighting|false     |18.00  |
    +--------+----------+-------+
    ```

    **Why:** calendar attributes live in `dim_date`, so "weekend" is a join, not a date calculation repeated in every
    report. March 1, 2026 is a Sunday.

**Q25. Silver corrected yesterday's orders after gold was published. Walk through restating yesterday.**

??? success "Answer"
    1. Refresh the dimensions first. 2. Find the changed orders (silver's Change Data Feed or an `updated_at`
    watermark, plus fact rows on the unknown member). 3. Rebuild their fact lines: `MERGE` on the grain key with a
    `WHEN NOT MATCHED BY SOURCE` limited to those orders, or `REPLACE WHERE` on yesterday's date. 4. Recompute the
    aggregate for exactly the affected dates with
    `INSERT INTO gold.daily_sales REPLACE WHERE order_date = ... SELECT ... WHERE order_date = ...`, after checking
    the source is not empty. 5. Run the reconciliation checks. The old
    number stays readable with `VERSION AS OF` until `VACUUM` removes its files.

    **Why:** each step is idempotent and atomic, so a rerun gives the same result and readers never see a half-written
    day (section 10.7).

**Q26. What happens here, and is it good or bad?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO gold.daily_sales
REPLACE WHERE order_date = DATE'2026-03-01'
SELECT ... FROM gold.fact_order_lines ... GROUP BY f.order_date, f.currency;   -- no date filter
```

??? success "Answer"
    It fails with `DELTA_REPLACE_WHERE_MISMATCH` and writes nothing (section 10.7, trap 1), because the query returns
    rows for other dates. That is good: by default every row the query returns must match the predicate, which stops
    a job from adding other days' rows into a window it did not delete. Fix: add
    `WHERE f.order_date = DATE'2026-03-01'` to the query.

    **Why:** the `INSERT` page: "If any row falls outside it, the `INSERT` fails and writes nothing." On classic
    compute a configuration can relax the check; do not.

**Q27. A nightly `REPLACE WHERE order_date = yesterday` ran after an upstream failure left the staging table empty.
What happened to yesterday in gold, and how do you prevent and repair it?**

??? success "Answer"
    Yesterday's rows were deleted and nothing was inserted (section 10.7, trap 2: March 2 disappeared). Repair:
    `RESTORE TABLE gold.daily_sales TO VERSION AS OF <version before the run>` (or rerun once the source is back).
    Prevent: count the source rows for the day (or compare with silver) and fail the job if it is empty or far below
    normal; run the reconciliation checks after the write.

    **Why:** Databricks warns "For empty source queries, `REPLACE WHERE` might delete table rows."

**Q28. Find the bug. The fact's grain is one row per order line (`gold.fact_copy` is a copy of
`gold.fact_order_lines`).**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
MERGE INTO gold.fact_copy AS t
USING (<fact query for order 1009>) AS s
ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

??? success "Answer"
    The `ON` clause uses only `order_id`, but an order has several lines. Each target line of order 1009 matches all
    three source lines, and Delta refuses to update one target row from several source rows:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    [DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE] Cannot perform Merge as multiple source rows matched and attempted to modify the ...
    ```

    Fix: match on the full grain key, `ON t.order_id = s.order_id AND t.product_sk = s.product_sk`.

    **Why:** a `MERGE` key must be the table's grain; anything coarser produces multiple matches (the same error as in
    chapter 9, section 9.7, for a different reason).

**Q29. What does this `MERGE` do to the rest of the fact table?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
MERGE INTO gold.fact_copy AS t
USING (<fact query for order 1009 only>) AS s
ON t.order_id = s.order_id AND t.product_sk = s.product_sk
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE;
```

??? success "Answer"
    It deletes every row that is not in the source, which is every order except 1009:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +-----------+
    |rows_before|
    +-----------+
    |11         |
    +-----------+

    +-----------------+----------------+----------------+-----------------+
    |num_affected_rows|num_updated_rows|num_deleted_rows|num_inserted_rows|
    +-----------------+----------------+----------------+-----------------+
    |11               |3               |8               |0                |
    +-----------------+----------------+----------------+-----------------+

    +----------+-----------+
    |rows_after|orders_left|
    +----------+-----------+
    |3         |[1009]     |
    +----------+-----------+
    ```

    Fix: limit the clause to the slice the source represents,
    `WHEN NOT MATCHED BY SOURCE AND t.order_id IN (<changed orders>) THEN DELETE` (or a date range).

    **Why:** "not matched by source" means "not in this source", and a partial source makes everything else look
    deleted.

**Q30. Order 1005 is corrected: its order date moves from March 1 to March 2. Which days of `daily_sales` must be
restated, and how do you find them?**

??? success "Answer"
    Both March 1 (the order must leave it) and March 2 (it must arrive). Take the changed orders' dates from the fact
    before the change (`VERSION AS OF` the previous version, or the pre-image rows of a Change Data Feed) and after it,
    and union them; section 10.7, step 4, does exactly this.

    **Why:** restating only the new date would leave the order counted on both days.

**Q31. Write the PySpark that restates one day of `gold.daily_sales`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    day = "2026-03-02"
    restated = spark.sql(DAILY_SELECT.format(where=f"f.order_date = DATE'{day}'"))
    (restated.write.format("delta").mode("overwrite")
        .option("replaceWhere", f"order_date = DATE'{day}'")
        .saveAsTable("gold.daily_sales"))
    (spark.sql("DESCRIBE HISTORY gold.daily_sales")
     .select("version", "operation", "operationParameters.predicate").orderBy("version").show(truncate=False))
    ```

    ```text
    +-------+------------+-----------------------------+
    |version|operation   |predicate                    |
    +-------+------------+-----------------------------+
    |0      |CREATE TABLE|NULL                         |
    |1      |WRITE       |NULL                         |
    |2      |WRITE       |order_date = DATE'2026-03-02'|
    +-------+------------+-----------------------------+
    ```

    **Why:** `mode("overwrite")` with `replaceWhere` is the DataFrame form of `INSERT ... REPLACE WHERE`; without the
    option, `overwrite` would replace the whole table.

**Q32. When is a full rebuild of a gold table the right choice?**

??? success "Answer"
    When the table is small (most dimensions, small aggregates), when a business rule changed and every row must be
    recomputed anyway, or as a periodic check that the incremental path still matches. It is simple, always correct
    for the current silver, and Delta keeps the previous version. Avoid it for large facts (cost grows with history)
    and for dimensions with identity keys (keys change).

    **Why:** incremental logic is extra code that can be wrong; use it where the cost of a rebuild justifies it.

**Q33. A materialized view over the fact is fully recomputed on every refresh, although the query only filters and
groups. Name three likely causes.**

??? success "Answer"
    It is refreshed on classic compute (incremental refresh needs serverless; "Materialized views that do not use
    serverless pipelines are always fully recomputed"); a source table lacks row tracking, which some incremental
    operations require; or the query has something not incrementalizable (a non-deterministic function, a `FLOAT` or
    `DOUBLE` sum, which the page says can "force a full refresh", a recursive CTE). The cost model may also simply
    have judged a full recompute cheaper. Check with `EXPLAIN CREATE MATERIALIZED VIEW` and the event log's
    `planning_information` events.

    **Why:** from [Incremental refresh for materialized
    views](https://docs.databricks.com/aws/en/ldp/incremental-refresh).

**Q34. A dashboard SLA cannot tolerate a surprise full recompute of a large materialized view. What do you set?**

??? success "Answer"
    `REFRESH POLICY INCREMENTAL STRICT` (Databricks SQL and Databricks Runtime 17.3 and above;
    `refresh_policy = 'incremental_strict'` in [Lakeflow pipelines, formerly Delta Live
    Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)). If incrementalization
    is not possible, the refresh fails with
    `MATERIALIZED_VIEW_NOT_INCREMENTALIZABLE` instead of recomputing, so you can fix the cause. `INCREMENTAL` would
    prefer incremental but fall back to full; `AUTO` (the default) lets the cost model decide.

    **Why:** the refresh policy turns an invisible cost spike into a visible failure.

**Q35. A gold table has been a standalone streaming table with
`FLOW REPLACE WHERE order_date >= date_add(current_date(), -7)` for a year. Someone runs
`REFRESH STREAMING TABLE ... FULL`. What is left?**

??? success "Answer"
    Only the last 7 days. A full refresh "clears all existing data and re-executes the flow using only its defined
    predicate". Prevent it with `TBLPROPERTIES (pipelines.reset.allowed = 'false')`; to reload old ranges use a
    one-off predicate override (`REFRESH STREAMING TABLE ... WHERE ...`) instead.

    **Why:** the flow only ever recomputes its predicate window; history outside it exists only because earlier
    refreshes wrote it.

**Q36. In a pipeline in Lakeflow pipelines (formerly Delta Live Tables), you want a materialized view that builds
`dim_product` with an identity column. Good idea?**

??? success "Answer"
    No. Databricks says identity columns "might be recomputed during updates to a materialized views" and recommends
    them in pipelines "only with streaming tables"; they are also not supported on `AUTO CDC` (formerly
    `APPLY CHANGES`, [rename](https://docs.databricks.com/aws/en/ldp/cdc)) targets. A recomputed key would re-point every fact. Derive the key with a hash of the natural
    key instead. (Rename: [What happened to Delta Live
    Tables?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt))

    **Why:** a materialized view may be fully recomputed at any refresh; its keys must be a function of the data.

**Q37. What is a Unity Catalog metric view, how do you query it, and why does `SELECT *` fail?**

??? success "Answer"
    A view that defines measures (aggregate expressions) and fields (dimensions) once, in YAML, over a source table or
    star, created with `CREATE VIEW ... WITH METRICS LANGUAGE YAML`. You select fields, wrap each measure in
    `MEASURE()`, and `GROUP BY` the fields; the engine computes each measure for that grouping. `SELECT *` fails
    because a measure is not a column: it has no value until a grouping is given (Databricks: specify columns "rather
    than using `SELECT *`"). Section 10.9 ran one on open-source Spark 4.2.

    **Why:** metric views keep non-additive measures (distinct counts, ratios) correct at any grain.

**Q38. Daily "revenue per customer" for CAD was 89.95, 100.00 and 99.95 on March 1 to 3 (before day 4). A report
averages them to 96.63 for the period. What is the right number and why?**

??? success "Answer"
    479.85 / 4 = 119.96, the value the metric view returned in section 10.9. A ratio must be recomputed from its
    numerator and denominator at the target grain: total revenue divided by distinct customers over the period. The
    average of daily ratios weighs each day equally and double counts customers who bought on several days.

    **Why:** ratios are non-additive; store the numerator and denominator, or define the ratio in a metric view.

**Q39. Analysts say the sales dashboard on gold is slow. What do you check first on Databricks?**

??? success "Answer"
    The query profile first (chapter 22). Then: the warehouse type and size (Databricks recommends serverless SQL
    warehouses where available; Photon is the default engine on all SQL warehouses); whether the tables are clustered
    on the columns the dashboard filters by (liquid clustering, or `CLUSTER BY AUTO`); whether filters hit dimension
    columns only, so the fact cannot skip files (copy the date onto the fact, or serve a wide table); and whether the
    query recomputes a heavy aggregate that should be an aggregate table, a materialized view or a metric view
    materialization.

    **Why:** most gold slowness is layout and model, not engine.

**Q40. A distribution partner, who does not use Databricks, needs Red Rock Supply's daily sales every morning. How
do you give it to them?**

??? success "Answer"
    With OpenSharing ([formerly Delta
    Sharing](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next)),
    open sharing protocol: `CREATE SHARE`, `ALTER SHARE ... ADD TABLE shop.gold.daily_sales`, create a recipient
    (authenticated by a bearer token or OIDC federation), `GRANT SELECT ON SHARE ... TO RECIPIENT ...`. The partner
    reads the live table with Spark, pandas, Power BI or another connector; nothing is copied or exported. Share the
    aggregate or a view, not the order-level fact.

    **Why:** OpenSharing shares "regardless of whether they use Databricks"; Databricks-to-Databricks sharing would
    need no token if the partner were on Databricks with Unity Catalog.

**Q41. Find the bug in this surrogate key: `md5(concat(customer_id, region_code)) AS customer_sk`.**

??? success "Answer"
    Concatenating without a separator makes different inputs equal: `(1, '23')` and `(12, '3')` both become `'123'`:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT md5(concat(1, 23)) = md5(concat(12, 3))                   AS md5_concat_collides,
           md5(concat_ws('|', 1, 23)) = md5(concat_ws('|', 12, 3)) AS md5_with_separator_collides,
           xxhash64(1, 23) = xxhash64(12, 3)                       AS xxhash64_collides;
    ```

    ```text
    +-------------------+---------------------------+-----------------+
    |md5_concat_collides|md5_with_separator_collides|xxhash64_collides|
    +-------------------+---------------------------+-----------------+
    |true               |false                      |false            |
    +-------------------+---------------------------+-----------------+
    ```

    Fix: hash with a separator (`concat_ws('|', ...)`), or pass the columns as separate arguments to `xxhash64`. Also
    note `concat` returns `NULL` if any input is `NULL`; `concat_ws` skips `NULL`s, so decide how `NULL` parts are
    encoded (for example `coalesce(col, '~')`).

    **Why:** the key must be unique by construction before collisions of the hash itself even matter.

**Q42. Which gold checks catch (a) a fact load rerun as a plain `INSERT`, and (b) a silver correction that gold did
not pick up?**

??? success "Answer"
    (a) The grain uniqueness check names the cause; the order-total check and the aggregate-versus-fact check show
    the damage. The line reconciliation does not fail, because each duplicate joins to the same silver line with the
    same quantity. (b) Only reconciliation checks (lines, order totals, total revenue against silver): gold is
    internally consistent, so every shape check passes. Section 10.12 ran both.

    **Why:** shape checks prove gold is well-formed; only reconciliation proves it is right.

**Q43. Finance's export says March 1 revenue was 179.90 CAD; the dashboard says 149.95. Nobody changed the dashboard.
How do you investigate?**

??? success "Answer"
    Look at `DESCRIBE HISTORY gold.daily_sales` for writes since finance's export, and compare the row with
    `VERSION AS OF` the earlier version: here the 179.90 is version 1 and the restatement (a `WRITE` with the
    `order_date` predicate) changed it. Then trace the cause in silver: order 1001's `updated_at` and amount changed on
    March 4 (one pair of socks instead of two). Both numbers were correct for their time; agree with finance which
    one is the reporting basis, and if published numbers must be reproducible, keep a published snapshot table.

    **Why:** Delta history and time travel explain a changed number; reconciliation checks confirm the current one.

## Sources

- [What is the medallion lakehouse architecture?](https://docs.databricks.com/aws/en/lakehouse/medallion) (last updated Oct 29, 2026)
- [Data modeling](https://docs.databricks.com/aws/en/transform/data-modeling) (last updated Sep 11, 2026)
- [CREATE TABLE [USING]](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-table-using) (last updated Nov 6, 2026)
- [Delta Lake generated columns](https://docs.databricks.com/aws/en/delta/generated-columns) (identity columns; last updated Sep 11, 2026)
- [Pipeline limitations](https://docs.databricks.com/aws/en/ldp/limitations) (last updated Oct 22, 2026)
- [Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints) (last updated Nov 6, 2026)
- [ADD CONSTRAINT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-table-add-constraint) (last updated Sep 11, 2026)
- [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc) (last updated Nov 10, 2026)
- [Optimize queries with `RELY` on primary key and unique constraints](https://docs.databricks.com/aws/en/sql/user/queries/query-optimization-constraints) (last updated Oct 26, 2026)
- [`INSERT`](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-dml-insert-into) (last updated Oct 21, 2026)
- [Selectively overwrite data with Delta Lake](https://docs.databricks.com/aws/en/delta/selective-overwrite) (last updated Sep 11, 2026)
- [When to use REPLACE WHERE vs. materialized views](https://docs.databricks.com/aws/en/sql/mv-st/replace-where-vs-materialized-views) (last updated Oct 15, 2026)
- [REPLACE WHERE flows for standalone streaming tables](https://docs.databricks.com/aws/en/sql/mv-st/flows-replace-where) (last updated Oct 15, 2026)
- [Batch processing with REPLACE WHERE flows](https://docs.databricks.com/aws/en/ldp/flows-replace-where) (last updated Oct 15, 2026)
- [Use standalone materialized views](https://docs.databricks.com/aws/en/views/materialized) (last updated Nov 5, 2026)
- [Incremental refresh for materialized views](https://docs.databricks.com/aws/en/ldp/incremental-refresh) (last updated Oct 28, 2026)
- [REFRESH POLICY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-materialized-view-refresh-policy) (last updated Sep 11, 2026)
- [materialized_view](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-materialized-view) (last updated Oct 15, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [Unity Catalog metric views](https://docs.databricks.com/aws/en/uc-semantics/metric-views/) (last updated Oct 29, 2026)
- [Unity Catalog semantics](https://docs.databricks.com/aws/en/uc-semantics/) (last updated Nov 9, 2026)
- [Create a metric view](https://docs.databricks.com/aws/en/uc-semantics/metric-views/create) (last updated Oct 12, 2026)
- [Query metric views](https://docs.databricks.com/aws/en/uc-semantics/metric-views/query) (last updated Nov 9, 2026)
- [Metric view feature availability](https://docs.databricks.com/aws/en/uc-semantics/metric-views/feature-availability) (last updated Nov 9, 2026)
- [Metric view YAML syntax reference](https://docs.databricks.com/aws/en/uc-semantics/metric-views/yaml-reference) (last updated Oct 28, 2026)
- [Materialization for metric views](https://docs.databricks.com/aws/en/uc-semantics/metric-views/materialization) (last updated Oct 28, 2026)
- [Spark Release 4.2.0](https://spark.apache.org/releases/spark-release-4-2-0.html) (Apache Spark release notes; no date shown)
- [Connect to a SQL warehouse](https://docs.databricks.com/aws/en/compute/sql-warehouse/) (last updated Oct 9, 2026)
- [SQL warehouse types](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-types) (last updated Oct 30, 2026)
- [What is Photon?](https://docs.databricks.com/aws/en/compute/photon) (last updated Sep 11, 2026)
- [Use liquid clustering for tables](https://docs.databricks.com/aws/en/delta/clustering) (last updated Nov 2, 2026)
- [What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/) (last updated Oct 27, 2026)
- [From Delta Sharing to OpenSharing: what changed, what's next](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next) (Databricks blog, November 5, 2026)
- [Create shares for OpenSharing](https://docs.databricks.com/aws/en/opensharing/create-share) (last updated Oct 29, 2026)
- [ALTER SHARE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-alter-share) (last updated Sep 11, 2026)
- [CREATE RECIPIENT](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-recipient) (last updated Sep 11, 2026)
- [GRANT ON SHARE](https://docs.databricks.com/aws/en/sql/language-manual/security-grant-share) (last updated Sep 11, 2026)
- [Databricks Feature Store](https://docs.databricks.com/aws/en/machine-learning/feature-store/) (last updated Nov 10, 2026)
