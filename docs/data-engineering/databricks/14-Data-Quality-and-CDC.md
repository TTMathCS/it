# 14. Data quality and change data capture in pipelines

*Two jobs fill most of a data engineer's week once the pipeline exists: keeping bad rows out of the tables people
trust, and keeping copies of source tables in step with the systems that change them. This chapter covers both. It
starts with where checks belong in the medallion flow, then expectations in Lakeflow pipelines (formerly Delta Live
Tables), the quarantine pattern, Delta `CHECK` constraints, and a plain-PySpark check suite you can run anywhere. The
second half is change data capture: what a change feed contains, `AUTO CDC` (formerly `APPLY CHANGES`) for SCD Type 1
and Type 2, how the sequencing column fixes out-of-order events, and `AUTO CDC FROM SNAPSHOT` for sources that only
send full copies. Interviewers ask "how do you handle bad records?" and "how do you apply CDC with late updates and
deletes?" in almost every data engineering loop; by the end you can answer both with code and with the exact names.*

!!! abstract "In this chapter"
    **You will learn:**

    - where data-quality checks go in bronze, silver and gold, and the four things you can do with a bad row
    - expectations: `CONSTRAINT ... EXPECT (...)` with the default warn, `ON VIOLATION DROP ROW` and
      `ON VIOLATION FAIL UPDATE`, and the six Python decorators from `@dp.expect` to `@dp.expect_all_or_fail`
    - where expectations can be attached, how their metrics reach the pipeline event log, and how to query them
    - the documented quarantine pattern (an inverse rule and a flag column), and the `NULL` trap in it
    - rules kept in a table and applied with `expect_all_or_drop`
    - Delta `NOT NULL` and `CHECK` constraints, run here, including what happens to a whole batch with one bad row
    - a data-quality check suite in plain PySpark that returns a report table
    - change data capture: operations, sequence numbers, deletes, late events, snapshots
    - `AUTO CDC ... INTO` in SQL and `dp.create_auto_cdc_flow` in Python, SCD Type 1 and Type 2, `__START_AT` and
      `__END_AT`, `TRACK HISTORY ON`, tombstones for deletes
    - an emulation of `AUTO CDC` with `MERGE` on Delta Lake 4.4.1 that reproduces the documented results
    - `AUTO CDC FROM SNAPSHOT`, and what open-source Spark does with `create_auto_cdc_flow` today

    **You need:** [7. The medallion architecture](07-Medallion-Architecture.md),
    [9. Building silver](09-Building-Silver.md) (quarantine, the out-of-order guard, SCD Type 1 and Type 2 with
    `MERGE`, Change Data Feed) and [13. Lakeflow Spark Declarative Pipelines](13-Declarative-Pipelines.md)
    (streaming tables, materialized views, flows). The generic SCD background is in the SQL course,
    [Data modelling](../../databases/sql/19-Data-Modelling.md).

    **Levels:** sections 14.1 to 14.3 beginner, 14.4 to 14.10 intermediate, 14.11 to 14.15 expert.

## 14.1 Where checks go in the medallion flow

*Level: beginner.*

A pipeline that only ever sees clean data does not exist. Orders arrive with an amount of `abc`, a customer that is
not in the customer table, a currency nobody sells in, the same order twice. The question is not whether to check,
but where, and what to do when a check fails.

Databricks describes the layers by their quality: "The terms bronze (raw), silver (validated), and gold (enriched)
describe the quality of the data in each of these layers", and lists "Data quality checks and enforcement" among
the operations performed in silver tables, while in bronze "Minimal data validation is performed"
([What is the medallion lakehouse architecture?](https://docs.databricks.com/aws/en/lakehouse/medallion)). That
gives a simple placement:

| Layer | Checks that belong here | Why |
| --- | --- | --- |
| Bronze | Structural only: the file parsed, metadata columns are present, the row count of a load is not zero | Bronze must keep everything; a rule that drops rows here loses data you cannot get back |
| Silver | Row rules: keys not `NULL`, values castable, ranges, allowed values, one row per key, the customer exists | Silver is the first layer people trust; this is where a bad row is stopped or set aside |
| Gold | Table rules: totals reconcile with silver, no day is missing, aggregates are within a normal range | Errors here come from joins and logic, not from single rows |

When a row fails a rule, you have four choices:

| Choice | What happens | Use it when |
| --- | --- | --- |
| Keep and count (warn) | The row is written; the failure is counted | The rule is new, or the issue is cosmetic (a missing phone number) |
| Drop | The row is not written; the drop is counted | The row is useless and nobody needs to see it (a heartbeat test record) |
| Quarantine | The row goes to a separate table with the reason | The row matters and someone must fix it (an order with a bad amount) |
| Fail | Nothing is written; the run stops | One bad row means the whole batch is wrong (a missing primary key in a finance feed) |

The first three never block good rows. Fail does, which is why it is reserved for rules that, when broken, mean the
input itself cannot be trusted. [Chapter 9](09-Building-Silver.md) builds the quarantine choice by hand; the rest of
this chapter shows the Databricks feature for all four and the plain-Spark tools you can use outside a pipeline.

!!! tip "In the interview"
    **"Where do you put data-quality checks?"** Bronze keeps every record as received, with only structural checks,
    so nothing is lost. Row-level rules run on the way into silver: I keep, drop, quarantine or fail depending on how
    much a bad row matters, and I never silently drop business records. Gold gets table-level checks such as
    reconciliation with silver. In Lakeflow pipelines (formerly Delta Live Tables,
    [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) the row rules are expectations.

## 14.2 Expectations in Lakeflow pipelines

*Level: beginner.*

The Databricks page defines them: "Expectations are optional clauses in pipeline materialized view, streaming
table, or view creation statements that apply data quality checks on each record passing through a query"
([Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations)). An
expectation has three parts:

1. **A name**, unique within the dataset, used to track it in the metrics.
2. **A constraint**: a SQL Boolean expression evaluated for each row.
3. **An action** for rows that fail: warn (the default), drop, or fail.

The three actions, from the same page:

| Action | SQL | Python | Result |
| --- | --- | --- | --- |
| warn (default) | `EXPECT` | `dp.expect` | "Invalid records are written to the target." |
| drop | `EXPECT ... ON VIOLATION DROP ROW` | `dp.expect_or_drop` | "Invalid records are dropped before data is written to the target. The count of dropped records is logged alongside other dataset metrics." |
| fail | `EXPECT ... ON VIOLATION FAIL UPDATE` | `dp.expect_or_fail` | "Invalid records prevent the update from succeeding. Manual intervention is required before reprocessing." |

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 270" role="img" aria-label="Eight order rows pass through the expectation valid_amount. With warn all eight are written and two are counted as failed; with drop six are written and two dropped and counted; with fail the flow update fails and is rolled back">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="16" y="105" width="130" height="60" rx="6"/>
<rect x="176" y="90" width="176" height="90" rx="6"/>
<rect x="392" y="20" width="232" height="66" rx="6"/>
<rect x="392" y="102" width="232" height="66" rx="6"/>
<rect x="392" y="184" width="232" height="66" rx="6"/>
<line x1="146" y1="135" x2="168" y2="135"/>
<line x1="352" y1="120" x2="384" y2="58"/>
<line x1="352" y1="135" x2="384" y2="135"/>
<line x1="352" y1="150" x2="384" y2="212"/>
</g>
<g fill="currentColor">
<polygon points="176,135 166,130 166,140"/>
<polygon points="390,53 379,55 386,63"/>
<polygon points="392,135 382,130 382,140"/>
<polygon points="390,217 386,207 379,215"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="81" y="131">8 order rows</text>
<text x="81" y="149">from bronze</text>
<text x="264" y="114">valid_amount</text>
<text x="264" y="134">amount IS NOT NULL</text>
<text x="264" y="152">AND amount &gt;= 0</text>
<text x="264" y="170">(6 pass, 2 fail)</text>
<text x="508" y="46">warn: EXPECT</text>
<text x="508" y="68">all 8 written, 2 counted failed</text>
<text x="508" y="128">drop: ON VIOLATION DROP ROW</text>
<text x="508" y="150">6 written, 2 dropped, counted</text>
<text x="508" y="210">fail: ON VIOLATION FAIL UPDATE</text>
<text x="508" y="232">flow update fails, rolled back</text>
</g>
</svg>
<figcaption>Figure 14.1. One expectation, three actions. The counts are the Red Rock orders of section 14.3; the fail
case writes nothing and records no metrics.</figcaption>
</figure>

Here are the Red Rock Supply silver orders with four expectations. The pipeline's default catalog and schema are
`shop.silver`; bronze is read with its full name.

*Databricks only, not run here. Syntax from [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations).*

```sql
CREATE OR REFRESH STREAMING TABLE silver_orders (
  CONSTRAINT valid_order_id    EXPECT (order_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT valid_customer_id EXPECT (customer_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_amount      EXPECT (amount IS NOT NULL AND amount >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT valid_currency    EXPECT (currency IN ('CAD', 'USD'))
)
AS SELECT
  try_cast(order_id AS INT)            AS order_id,
  try_cast(customer_id AS INT)         AS customer_id,
  try_to_timestamp(order_ts)           AS order_ts,
  upper(status)                        AS status,
  try_cast(amount AS DECIMAL(10,2))    AS amount,
  currency
FROM STREAM(shop.bronze.orders);
```

The same table in Python. Expectation decorators "come after a `@dp.table()`, `@dp.materialized_view` or
`@dp.temporary_view()` decorator and before a dataset definition function"
([Expectations, Python reference](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-expectations)).

*Databricks only, not run here. Syntax from [Expectations (Python reference)](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-expectations).*

```python
from pyspark import pipelines as dp
from pyspark.sql import functions as F

@dp.table(name="silver_orders")
@dp.expect_or_fail("valid_order_id", "order_id IS NOT NULL")
@dp.expect_all_or_drop({
    "valid_customer_id": "customer_id IS NOT NULL",
    "valid_amount": "amount IS NOT NULL AND amount >= 0",
})
@dp.expect("valid_currency", "currency IN ('CAD', 'USD')")
def silver_orders():
    return spark.readStream.table("shop.bronze.orders").select(
        F.expr("try_cast(order_id AS INT)").alias("order_id"),
        F.expr("try_cast(customer_id AS INT)").alias("customer_id"),
        F.expr("try_to_timestamp(order_ts)").alias("order_ts"),
        F.upper("status").alias("status"),
        F.expr("try_cast(amount AS DECIMAL(10,2))").alias("amount"),
        "currency",
    )
```

The `dp` module "includes six decorators": `expect`, `expect_or_drop`, `expect_or_fail` take one name and one
constraint; `expect_all`, `expect_all_or_drop`, `expect_all_or_fail` take a dictionary `{name: constraint}`. Only
Python can group expectations this way: "While both SQL and Python support multiple expectations in a single
dataset, only Python allows you to group multiple expectations and specify collective actions"
([expectations page](https://docs.databricks.com/aws/en/ldp/expectations)). In SQL you list several `CONSTRAINT`
clauses separated by commas, each with its own action.

### What a constraint may contain

The constraint is ordinary SQL, including functions and `CASE`, but it "cannot contain the following: Custom Python
functions, External service calls, Subqueries referencing other tables"
([expectations page](https://docs.databricks.com/aws/en/ldp/expectations)). So an expectation can check that
`customer_id IS NOT NULL`, but not that the customer exists in `silver_customers`. Cross-table rules need a join
first (section 14.5 shows the documented validation-table patterns) or a check outside the pipeline (section 14.9).

!!! warning "Write rules that can never be NULL"
    The pages say a constraint "must evaluate to true or false for each record". They do not say what happens when it
    evaluates to `NULL` (for example `amount >= 0` when `amount` is `NULL`); that is **not verified** here. Do not
    depend on it: write `amount IS NOT NULL AND amount >= 0`, or wrap the rule in `coalesce(..., false)`. Section 14.5
    shows how a nullable rule loses a row in the quarantine pattern, and section 14.7 shows that a Delta `CHECK`
    constraint rejects a `NULL` result.

### Where expectations can be attached

From the pages, word for word where it matters:

- Pipeline datasets: "Expectations are optional clauses in pipeline materialized view, streaming table, or view
  creation statements". The limitations list narrows "view" to temporary views: "only streaming tables,
  materialized views, and temporary views support expectations"
  ([expectations page](https://docs.databricks.com/aws/en/ldp/expectations)).
- Databricks SQL outside a pipeline: "You can also define expectations on streaming tables and materialized views
  backed by a standalone pipeline created in Databricks SQL" with the same `CONSTRAINT ... EXPECT` clause (same
  page).
- A streaming table declared with `dp.create_streaming_table()` takes `expect_all`, `expect_all_or_drop` and
  `expect_all_or_fail` as parameters, which "Provides the same behavior and uses the same syntax as expectation
  decorator functions, but implemented as a parameter"
  ([create_streaming_table](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-streaming-table)). This
  is how you attach rules to an `AUTO CDC` target in Python; in SQL, "You define data quality constraints for the
  target using the same `CONSTRAINT` clause as other pipeline queries"
  ([AUTO CDC INTO](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-apply-changes-into)).
- Not supported: sinks ("The flow type, such as sinks, does not support expectations") and
  `AUTO CDC FROM SNAPSHOT` ("Expectations are not supported with `AUTO CDC FROM SNAPSHOT`") (expectations page, Limitations).

Expectations also need the right pipeline edition. "Configure pipelines" says the `Advanced` edition "includes data
quality constraints with expectations", that "Serverless pipelines require the `Advanced` edition", and that a
pipeline using a feature its edition lacks, "such as expectations", fails with an error message explaining why
([Configure pipelines](https://docs.databricks.com/aws/en/ldp/configure-pipeline)).

### What fail really stops

`expect_or_fail` stops "execution immediately when a record fails validation. If the operation is a table update,
the system atomically rolls back the transaction". It does not stop the whole pipeline in every case: "In a triggered
pipeline, the failure of a single flow does not cause other parallel flows to fail. In a continuous pipeline, an
expectation failure stops the flow, all dependent flows, and the pipeline emits a message explaining why it
stopped" ([expectations page](https://docs.databricks.com/aws/en/ldp/expectations)). The error names the flow, the
expectation and the offending record:

*Databricks only, not run here. Message copied from [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations).*

```text
[EXPECTATION_VIOLATION.VERBOSITY_ALL] Flow 'sensor-pipeline' failed to meet the expectation. Violated expectations: 'temperature_in_valid_range'. Input data: '{"id":"TEMP_001","temperature":-500,"timestamp_ms":"1710498600"}'. Output record: '{"sensor_id":"TEMP_001","temperature":-500,"change_time":"2024-03-15 10:30:00"}'. Missing input data: false
```

(That message is the example printed on the expectations page, not a Red Rock run.) The page's advice afterwards:
"you must fix the pipeline code to handle the invalid data correctly before re-running the pipeline". Because a
failed expectation stops the update, "metrics are not recorded" for `fail`.

!!! tip "In the interview"
    **"What are DLT expectations?"** In Lakeflow pipelines (formerly Delta Live Tables,
    [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) an expectation is a named SQL Boolean rule on
    a streaming table, materialized view or temporary view: `CONSTRAINT name EXPECT (rule)`. The default keeps the
    row and counts it, `ON VIOLATION DROP ROW` drops it, `ON VIOLATION FAIL UPDATE` fails the flow and rolls the
    update back. In Python they are `@dp.expect`, `@dp.expect_or_drop`, `@dp.expect_or_fail` and the `expect_all`
    variants that take a dictionary (old code says `@dlt.expect`).

## 14.3 The three actions, seen on a laptop

*Level: beginner.*

Expectations need a Lakeflow pipeline on Databricks. Open-source Spark Declarative Pipelines 4.2 has no expectation
decorators at all (section 14.15 shows the module's exports), and the Python reference marks expectations as not
available in Apache Spark ([Lakeflow pipelines Python language reference](https://docs.databricks.com/aws/en/ldp/developer/python-ref)).
To see the behavior anyway, here is a small plain-PySpark imitation: it is **not** the Databricks feature, only the
same three actions and the same two counters (`passed_records`, `failed_records`) applied to eight Red Rock orders.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
RULES = {
    "valid_order_id": "order_id IS NOT NULL",
    "valid_customer_id": "customer_id IS NOT NULL",
    "valid_amount": "amount IS NOT NULL AND amount >= 0",
    "valid_currency": "currency IN ('CAD', 'USD')",
}

def apply_expectations(df, rules, action):
    """'warn' keeps every row, 'drop' removes failing rows, 'fail' raises on the first failure."""
    all_ok = F.lit(True)
    for rule in rules.values():
        all_ok = all_ok & F.coalesce(F.expr(rule), F.lit(False))
    if action == "warn":
        return df
    if action == "drop":
        return df.where(all_ok)
    checks = [F.coalesce(F.expr(r), F.lit(False)).alias(n) for n, r in rules.items()]
    bad = df.where(~all_ok).select("*", *checks).limit(1).collect()
    if bad:                                   # 'fail': nothing is written
        row = bad[0].asDict()
        failed = [n for n in rules if not row.pop(n)]
        raise RuntimeError(f"Expectation violated: {failed}. Input data: {row}")
    return df
```

The input `typed` is the bronze orders cast with `try_cast` (full script: `src/ch14/s2_quality.py`). The counts per
rule, then the three actions:

```text
### metrics for the four rules (what the event log would count)
+-----------------+--------------+--------------+
|expectation      |passed_records|failed_records|
+-----------------+--------------+--------------+
|valid_order_id   |8             |0             |
|valid_customer_id|7             |1             |
|valid_amount     |6             |2             |
|valid_currency   |7             |1             |
+-----------------+--------------+--------------+

### warn: rows written = 8
### drop: rows written = 5
### fail: Expectation violated: ['valid_amount', 'valid_currency']. Input data: {'order_id': 1007, 'customer_id': 9, 'order_ts': datetime.datetime(2026, 3, 1, 14, 0), 'status': 'PLACED', 'amount': Decimal('-5.00'), 'currency': 'EUR'}
```

Two things to notice. The per-rule failures add up to 4, but only 3 rows are dropped: order 1007 fails two rules and
is dropped once. The event log keeps the same two views apart: per-expectation `passed_records` and
`failed_records`, and a separate `dropped_records` for the flow (section 14.4). And in drop mode the row simply
disappears; nothing tells the source team what was wrong with it. That is the gap the quarantine pattern fills.

## 14.4 Expectation metrics in the event log

*Level: intermediate.*

For `warn` and `drop` actions the metrics appear in the pipeline UI: open the pipeline under **Jobs & Pipelines**,
click a dataset with an expectation, and select the **Data quality** tab
([expectations page](https://docs.databricks.com/aws/en/ldp/expectations)). That tab "is not available" for
streaming tables and materialized views created in Databricks SQL; for those you query the event log (same page).

The event log is a hidden Delta table that every pipeline writes; it "contains all information related to a
pipeline, including audit logs, data quality checks, pipeline progress, and data lineage". The pipeline's run-as
user can read it with the `event_log()` function, and you can also publish it under a name of your choice in the
pipeline's advanced settings ([Pipeline event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs)).
Where the numbers live:

- events with `event_type = 'flow_progress'` carry the data-quality details;
- `details:flow_progress.data_quality.expectations` is an array with one entry per expectation: `name`, `dataset`,
  `passed_records`, `failed_records`;
- `details:flow_progress.data_quality.dropped_records` counts rows dropped because they failed one or more
  expectations.

The schema page adds a detail worth knowing: `failed_records` "Tracks whether the expectation was met, but does not
describe what happens to the records (warn, fail, or drop the records)"
([Pipeline event log schema](https://docs.databricks.com/aws/en/ldp/monitor-event-log-schema)). The documented
query for the last update, which assumes a view `event_log_raw` over the event log table:

*Databricks only, not run here. Syntax from [Pipeline event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs).*

```sql
SELECT * FROM event_log(<pipelineId>);     -- as the run-as user, by pipeline ID

WITH latest_update AS (
  SELECT origin.pipeline_id, origin.update_id AS latest_update_id
  FROM event_log_raw AS origin
  WHERE origin.event_type = 'create_update'
  ORDER BY timestamp DESC
  LIMIT 1
)
SELECT
  row_expectations.dataset AS dataset,
  row_expectations.name AS expectation,
  SUM(row_expectations.passed_records) AS passing_records,
  SUM(row_expectations.failed_records) AS failing_records
FROM (
  SELECT explode(
           from_json(details:flow_progress:data_quality:expectations,
                     "array<struct<name: string, dataset: string, passed_records: int, failed_records: int>>")
         ) row_expectations
  FROM event_log_raw, latest_update
  WHERE event_type = 'flow_progress'
    AND origin.update_id = latest_update.latest_update_id
)
GROUP BY row_expectations.dataset, row_expectations.name;
```

The `:` path operator reads into the JSON string column `details` ([chapter 18](18-Semi-Structured-Data.md)). The
same page notes that Databricks recommends the `pipeline_events` system table, which "contains events for all
pipelines across the workspaces in a region" and "is in Beta", and that events "are delivered to the event log on a
best-effort basis". Gaps you should expect, from the Limitations list of the expectations page: no metrics when a
flow has no updates in a run, when the flow type does not support expectations, or for a view that was never
queried; and a view read by several datasets "might have multiple sets of data quality metrics".

!!! tip "In the interview"
    **"How do you monitor DLT data quality?"** Lakeflow pipelines (formerly Delta Live Tables,
    [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) write passed and failed counts for every
    `warn` and `drop` expectation into the pipeline event log, in `flow_progress` events under
    `details:flow_progress.data_quality`. I query that (or the `pipeline_events` system table) to trend failure
    rates and alert on a jump. `fail` expectations record no metrics; their error message names the expectation and
    the record.

## 14.5 Quarantine with expectations

*Level: intermediate.*

Drop loses the row; fail blocks everything. Quarantine keeps the bad rows, separately. The documented pattern
([Expectation recommendations and advanced patterns](https://docs.databricks.com/aws/en/ldp/expectation-patterns))
has three steps:

1. Write the rules once, as a dictionary.
2. Build a **quarantine rule** that is the inverse of all rules together: `NOT(rule1 AND rule2 AND ...)`.
3. Compute an `is_quarantined` flag with that rule in one private table that also carries the expectations as
   `expect_all` (warn, so the metrics are recorded and nothing is dropped), partitioned by the flag. Two views then
   read the valid side and the invalid side.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 290" role="img" aria-label="Bronze orders flow into one flagged private table that records expectation metrics and computes is_quarantined as NOT of all rules. A valid view selects is_quarantined false, five rows, for silver; an invalid view selects is_quarantined true, three rows, for the quarantine table">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="16" y="112" width="150" height="60" rx="6"/>
<rect x="200" y="92" width="210" height="100" rx="6"/>
<rect x="446" y="28" width="178" height="70" rx="6"/>
<rect x="446" y="186" width="178" height="70" rx="6"/>
<line x1="166" y1="142" x2="192" y2="142"/>
<line x1="410" y1="120" x2="438" y2="72"/>
<line x1="410" y1="164" x2="438" y2="212"/>
</g>
<g fill="currentColor">
<polygon points="200,142 190,137 190,147"/>
<polygon points="442,65 432,68 440,76"/>
<polygon points="442,219 440,208 432,216"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="91" y="138">bronze orders</text>
<text x="91" y="156">8 rows</text>
<text x="305" y="116">orders_flagged (private)</text>
<text x="305" y="136">expect_all(rules): metrics</text>
<text x="305" y="156">is_quarantined =</text>
<text x="305" y="174">NOT (all rules)</text>
<text x="535" y="52">valid view</text>
<text x="535" y="70">is_quarantined = false</text>
<text x="535" y="88">5 rows, to silver</text>
<text x="535" y="210">invalid view</text>
<text x="535" y="228">is_quarantined = true</text>
<text x="535" y="246">3 rows, to quarantine</text>
<text x="320" y="282">A rule that can be NULL makes the flag NULL: that row lands in neither view.</text>
</g>
</svg>
<figcaption>Figure 14.2. The documented quarantine pattern: one flag, two views. Every row must get a flag of true or
false, or it disappears.</figcaption>
</figure>

The pattern adapted to Red Rock orders. The page's own example uses `temporary=True`; the current
`@dp.table` reference names this parameter `private` ("Private tables were previously created with the `temporary`
parameter", [table](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-table)).

*Databricks only, not run here. Syntax from [Expectation recommendations and advanced patterns](https://docs.databricks.com/aws/en/ldp/expectation-patterns).*

```python
from pyspark import pipelines as dp
from pyspark.sql.functions import expr

rules = {
    "valid_order_id": "(order_id IS NOT NULL)",
    "valid_customer_id": "(customer_id IS NOT NULL)",
    "valid_amount": "(amount IS NOT NULL AND amount >= 0)",
    "valid_currency": "(currency IN ('CAD', 'USD'))",
}
quarantine_rules = "NOT({0})".format(" AND ".join(rules.values()))

@dp.table(private=True, partition_cols=["is_quarantined"])
@dp.expect_all(rules)
def orders_flagged():
    return spark.readStream.table("orders_typed").withColumn("is_quarantined", expr(quarantine_rules))

@dp.temporary_view
def valid_orders():
    return spark.read.table("orders_flagged").filter("is_quarantined = false")

@dp.temporary_view
def invalid_orders():
    return spark.read.table("orders_flagged").filter("is_quarantined = true")
```

`orders_typed` is the casting step of section 14.2 as its own view. In SQL the page uses the flag column the same way,
with `CREATE OR REFRESH TEMPORARY STREAMING TABLE ... PARTITIONED BY (is_quarantined)`; today's keyword for that is
`PRIVATE` ("Private streaming tables were previously created with the `TEMPORARY` parameter",
[CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table)).

The same split runs here with plain PySpark and Delta: the flag, a table partitioned by it, two reads.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
quarantine_rule = "NOT ({0})".format(" AND ".join(f"({r})" for r in RULES.values()))
flagged = typed.withColumn("is_quarantined", F.expr(quarantine_rule))
flagged.write.format("delta").partitionBy("is_quarantined").saveAsTable("orders_quarantine_split")
valid = spark.table("orders_quarantine_split").where("is_quarantined = false")
invalid = spark.table("orders_quarantine_split").where("is_quarantined = true")
```

```text
### valid rows
+--------+-----------+-------------------+-------+------+--------+
|order_id|customer_id|order_ts           |status |amount|currency|
+--------+-----------+-------------------+-------+------+--------+
|1001    |7          |2026-03-01 10:15:00|PLACED |59.90 |CAD     |
|1002    |8          |2026-03-01 11:00:00|PLACED |120.00|CAD     |
|1002    |8          |2026-03-02 09:00:00|SHIPPED|120.00|CAD     |
|1005    |7          |2026-03-01 13:05:00|PLACED |35.50 |USD     |
|1006    |12         |2026-03-01 13:30:00|PLACED |42.00 |CAD     |
+--------+-----------+-------------------+-------+------+--------+

### quarantined rows
+--------+-----------+-------------------+------+------+--------+
|order_id|customer_id|order_ts           |status|amount|currency|
+--------+-----------+-------------------+------+------+--------+
|1003    |9          |2026-03-01 11:30:00|PLACED|NULL  |CAD     |
|1004    |NULL       |2026-03-01 12:00:00|PLACED|15.00 |CAD     |
|1007    |9          |2026-03-01 14:00:00|PLACED|-5.00 |EUR     |
+--------+-----------+-------------------+------+------+--------+
```

8 = 5 + 3. Two problems are still in the valid side (1002 twice, customer 12 who does not exist); no row rule can
see them, and section 14.9 catches both.

### The NULL hole

Now the same split with the shorter rule `amount >= 0`. Order 1003 has `amount = NULL` (it was `abc`), so the rule is
`NULL`, `NOT (NULL)` is `NULL`, and the row matches neither `is_quarantined = false` nor `= true`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
### naive rule 'amount >= 0': how rows split
+--------------+-----+
|is_quarantined|count|
+--------------+-----+
|          NULL|    1|
|         false|    6|
|          true|    1|
+--------------+-----+

+--------+------+--------------+
|order_id|amount|is_quarantined|
+--------+------+--------------+
|    1003|  NULL|          NULL|
+--------+------+--------------+
```

The row is silently gone from both sides. Chapter 9 hit the same trap with plain `WHERE` filters
([section 9.5](09-Building-Silver.md#95-the-quarantine-pattern)). The fix is the same: rules that cannot be `NULL`,
and a count check that bronze equals valid plus quarantined.

### Two-table variant, and the validation tables

Many teams write the quarantine as two real tables instead of one flagged table: silver gets
`@dp.expect_all_or_drop(rules)`, and a quarantine table reads the same source with
`@dp.expect_or_drop("quarantined", quarantine_rules)`, so each keeps exactly the rows the other drops, as long as
no rule can evaluate to `NULL` (how a drop expectation treats a `NULL` result is not verified, see the warning in
section 14.2). That variant
is built from the documented decorators but is not an example on the patterns page.

The patterns page also shows **validation tables**: a materialized view whose only job is to fail when a property
across tables is broken. Row-count equality (`CONSTRAINT no_rows_dropped EXPECT (a_count == b_count)`), missing
records after a join, and primary-key uniqueness (`CONSTRAINT unique_pk EXPECT (num_entries = 1)` over a
`GROUP BY pk`) are its three examples. Their Python versions use `@dp.expect_or_fail`; the SQL versions on the page
show only `EXPECT` (warn), so add `ON VIOLATION FAIL UPDATE` if you write them in SQL. Read the warning that comes with them:
"A validation table doesn't gate its downstream tables. Reading a validation table from another dataset doesn't
make that dataset wait for the validation result". To stop gold when silver is wrong, "split the validation logic
and the downstream work into separate pipelines and orchestrate them with a job, making the downstream pipeline's
task depend on the validation pipeline's task" ([patterns page](https://docs.databricks.com/aws/en/ldp/expectation-patterns)).
Jobs are [chapter 15](15-Lakeflow-Jobs.md).

!!! tip "In the interview"
    **"How do you quarantine bad records in DLT?"** In Lakeflow pipelines (formerly Delta Live Tables,
    [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) I keep the rules in one dictionary, build the
    inverse rule `NOT(rule1 AND rule2 ...)`, and add an `is_quarantined` flag in one private table that carries the
    rules as `expect_all`, so the metrics are recorded and nothing is lost. Two views split valid and invalid rows.
    I make sure no rule can evaluate to `NULL` and reconcile the counts.

## 14.6 Rules in a table: portable expectations

*Level: intermediate.*

Rules written inside each pipeline file drift apart: the same "valid email" rule ends up spelled three ways. The
patterns page recommends to "Store expectation definitions separately from pipeline logic" and "Add custom tags to
create groups of related expectations", and shows two ways: a Delta table of rules, or a Python module. In both, a
function returns a dictionary for a tag and an `expect_all_or_drop` decorator applies it. Adapted to Red Rock:

*Databricks only, not run here. Syntax from [Expectation recommendations and advanced patterns](https://docs.databricks.com/aws/en/ldp/expectation-patterns).*

```sql
CREATE OR REPLACE TABLE shop.ops.dq_rules AS
SELECT col1 AS name, col2 AS constraint, col3 AS tag
FROM VALUES
  ('valid_order_id',  'order_id IS NOT NULL',                 'orders'),
  ('valid_amount',    'amount IS NOT NULL AND amount >= 0',   'orders'),
  ('valid_email',     "email LIKE '%@%'",                     'customers');
```

```python
from pyspark import pipelines as dp
from pyspark.sql.functions import col

def get_rules(tag):
    rows = spark.read.table("shop.ops.dq_rules").filter(col("tag") == tag).collect()
    return {row["name"]: row["constraint"] for row in rows}

@dp.table
@dp.expect_all_or_drop(get_rules("orders"))
def silver_orders():
    return spark.readStream.table("orders_typed")
```

The rules are read when the pipeline code is evaluated, so a changed rule takes effect on the next update. One
restriction: "Dynamically loading expectations from a file is not supported in SQL", so this is a Python pattern
(same page). Keep the rules table under change control like code: a typo in a constraint string breaks the pipeline
the same way a typo in code does.

## 14.7 Delta CHECK and NOT NULL constraints

*Level: intermediate.*

Expectations exist only inside Lakeflow pipelines. A Delta table written by a notebook, a job or a `MERGE` can
protect itself with **enforced constraints**: "`NOT NULL`: indicates that values in specific columns cannot be null"
and "`CHECK`: indicates that a specified boolean expression must be true for each input row". "When a constraint is
violated, the transaction fails with an error"
([Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints)). These are Delta Lake features,
so they run here.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE silver.orders (
  order_id    INT NOT NULL,
  customer_id INT NOT NULL,
  order_ts    TIMESTAMP,
  status      STRING,
  amount      DECIMAL(10,2),
  currency    STRING)
USING DELTA;

ALTER TABLE silver.orders ADD CONSTRAINT amount_not_negative CHECK (amount >= 0);
ALTER TABLE silver.orders ADD CONSTRAINT known_currency CHECK (currency IN ('CAD', 'USD'));
SHOW TBLPROPERTIES silver.orders;
```

```text
+-------------------------------------+-----------------------------+
|key                                  |value                        |
+-------------------------------------+-----------------------------+
|delta.constraints.amount_not_negative|amount >= 0                  |
|delta.constraints.known_currency     |currency IN ( 'CAD' , 'USD' )|
|delta.minReaderVersion               |1                            |
|delta.minWriterVersion               |3                            |
+-------------------------------------+-----------------------------+
```

The constraints live in the table properties, and the writer protocol is now 3: "Adding a constraint upgrades the
table writer protocol if the current writer version is less than 3" (constraints page). (Locally the schema is
`silver`; on Databricks it would be `shop.silver.orders`.) After a good two-row insert, here is a batch where one row
of two is bad, a `NULL` customer, `NULL` values against both `CHECK`s, and a `MERGE`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO silver.orders VALUES
  (1005, 7, TIMESTAMP'2026-03-01 13:05:00', 'PLACED', 35.50, 'USD'),
  (1007, 9, TIMESTAMP'2026-03-01 14:00:00', 'PLACED', -5.00, 'CAD');
INSERT INTO silver.orders VALUES (1004, NULL, TIMESTAMP'2026-03-01 12:00:00', 'PLACED', 10.00, 'CAD');
INSERT INTO silver.orders VALUES (1009, 9, TIMESTAMP'2026-03-02 09:00:00', 'PLACED', NULL, 'CAD');
INSERT INTO silver.orders VALUES (1010, 9, TIMESTAMP'2026-03-02 09:30:00', 'PLACED', 12.00, NULL);
MERGE INTO silver.orders t USING order_updates s      -- order 1002 refunded with amount -120.00
ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

```text
[DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint amount_not_negative (amount >= 0) violated by row with values:
 - amount : -5.00
[DELTA_NOT_NULL_CONSTRAINT_VIOLATED] NOT NULL constraint violated for column: customer_id.
[DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint amount_not_negative (amount >= 0) violated by row with values:
 - amount : null
[DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint known_currency (currency IN ('CAD', 'USD')) violated by row with values:
 - currency : null

>>> SELECT order_id, amount, currency FROM silver.orders ORDER BY order_id
+--------+------+--------+
|order_id|amount|currency|
+--------+------+--------+
|1001    |59.90 |CAD     |
|1002    |120.00|CAD     |
+--------+------+--------+

[DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint amount_not_negative (amount >= 0) violated by row with values:
 - amount : -120.00
```

(Each error is the exception message without its Java class name, in the order of the run in
`src/ch14/s1_constraints.out`; the `SELECT` ran before the `MERGE`.) Three
lessons:

1. **All or nothing.** Order 1005 was valid, but it is not in the table: the whole `INSERT` failed with 1007. A
   constraint is a fail action for the entire write, never a drop.
2. **NULL fails a CHECK.** In standard SQL a `CHECK` whose result is unknown passes. Here `amount >= 0` with a `NULL`
   amount was rejected, which matches the Databricks wording "must be true for each input row". If `NULL` is
   allowed, say so: `CHECK (amount IS NULL OR amount >= 0)`.
3. **Every write path is covered.** The `MERGE` was rejected like the `INSERT`.

Adding a constraint checks the rows already in the table ("`ALTER TABLE ADD CONSTRAINT` verifies that all existing
rows satisfy the constraint before adding the constraint to the table", constraints page):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO silver.order_items VALUES (1001, 3, 2, 29.95), (1002, 5, 0, 120.00);
ALTER TABLE silver.order_items ADD CONSTRAINT qty_positive CHECK (qty > 0);
```

```text
[DELTA_NEW_CHECK_CONSTRAINT_VIOLATION] 1 rows in spark_catalog.silver.order_items violate the new CHECK constraint (qty > 0)
```

`ALTER TABLE ... DROP CONSTRAINT name` removes one. Primary key, foreign key and unique constraints are different:
they "are informational only and aren't enforced" (constraints page). A `PRIMARY KEY` on `order_id` does not stop a
duplicate; the check suite in section 14.9 does.

| | Expectations | Delta `CHECK` / `NOT NULL` |
| --- | --- | --- |
| Where | Lakeflow pipeline datasets, Databricks SQL streaming tables and materialized views | Any Delta table, any writer |
| Actions | warn, drop, fail | fail the whole write only |
| Metrics | passed/failed counts in the event log | none; an error message |
| Cross-table rules | no subqueries; use a validation table | no user-defined, aggregate or window functions |
| Runs on open-source Spark + Delta | no | yes (shown above) |

!!! tip "In the interview"
    **"Expectations or table constraints?"** Expectations (DLT expectations; Lakeflow pipelines were formerly Delta
    Live Tables, [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) are for the flow: they can keep,
    drop or fail and they count. A Delta `CHECK` or `NOT NULL` constraint is a last line of defense on the table
    itself: any writer that breaks it fails, the whole transaction rolls back, and a `NULL` result counts as a
    violation. I use both: expectations or a quarantine step to route bad rows, and constraints so no other job can
    write them later.

## 14.8 Expectation rules versus table rules: what cannot be a row rule

*Level: intermediate.*

Four of the most common checks cannot be written as a per-row expectation or a `CHECK` constraint, because each
needs more than one row or more than one table:

| Check | Why a row rule cannot do it | Where it goes |
| --- | --- | --- |
| Uniqueness of a key | Needs a `GROUP BY` across rows | Validation materialized view (`num_entries = 1`), or a suite |
| Referential integrity | Needs the other table; subqueries are not allowed | Join first and expect on the joined column, or a suite |
| Freshness | Needs `max(order_ts)` over the table and the clock | A suite or a monitoring job |
| Row-count reconciliation | Needs counts of two or three tables | Validation materialized view (`a_count == b_count`), or a suite |

The patterns page covers the first and last inside a pipeline. The next section does all four in plain PySpark,
which works in any job, on any platform, and in a unit test.

## 14.9 A data-quality check suite in plain PySpark

*Level: intermediate.*

A **check suite** is a function that runs a list of checks against tables and returns one row per check: what was
checked, how many rows failed, pass or fail, and how serious it is. Storing the report in a Delta table gives you a
history to trend; failing the job on an `error` row stops bad data reaching gold. This one checks the five valid
orders from section 14.5 against customers and order items.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
AS_OF = datetime(2026, 3, 2, 12, 0, 0)   # in production: datetime.now(timezone.utc)

def check(name, table, failed, total, severity="error", detail=""):
    return (name, table, int(failed), int(total), "PASS" if failed == 0 else "FAIL", severity, detail)

def run_suite():
    o = spark.table("silver_orders")
    c = spark.table("silver_customers")
    oi = spark.table("silver_order_items")
    n_o = o.count()
    res = []
    for col in ["order_id", "customer_id", "order_ts"]:                       # nulls
        res.append(check(f"not_null:{col}", "silver_orders", o.where(F.col(col).isNull()).count(), n_o))
    dup_keys = o.groupBy("order_id").count().where("count > 1")             # uniqueness
    res.append(check("unique:order_id", "silver_orders", dup_keys.count(), n_o,
                     detail=str(sorted(r.order_id for r in dup_keys.collect()))))
    orphans = o.join(c, "customer_id", "left_anti")                          # referential integrity
    res.append(check("fk:customer_id->silver_customers", "silver_orders", orphans.count(), n_o,
                     detail=str(sorted(r.order_id for r in orphans.collect()))))
    res.append(check("range:amount>=0", "silver_orders", o.where("amount < 0").count(), n_o))
    res.append(check("accepted:currency", "silver_orders",
                     o.where("currency NOT IN ('CAD','USD') OR currency IS NULL").count(), n_o))
    res.append(check("range:qty>0", "silver_order_items", oi.where("qty <= 0").count(), oi.count(),
                     severity="warn"))
    latest = o.agg(F.max("order_ts")).first()[0]                             # freshness
    lag_h = (AS_OF - latest).total_seconds() / 3600
    res.append(check("freshness:order_ts<24h", "silver_orders", int(lag_h > 24), 1,
                     detail=f"latest={latest}, lag_hours={lag_h:.1f}"))
    b, s, q = (spark.table(t).count() for t in ["bronze_orders", "silver_orders", "quarantine_orders"])
    res.append(check("reconcile:bronze=silver+quarantine", "silver_orders", abs(b - s - q), b,
                     detail=f"bronze={b}, silver={s}, quarantine={q}"))   # row-count reconciliation
    return spark.createDataFrame(res, "check STRING, table STRING, failed_rows INT, total_rows INT, "
                                      "status STRING, severity STRING, detail STRING")

report = run_suite().withColumn("run_ts", F.lit(AS_OF))
report.write.format("delta").mode("append").saveAsTable("dq_results")
blocking = report.where("status = 'FAIL' AND severity = 'error'").count()
```

```text
### data-quality report
+----------------------------------+------------------+-----------+----------+------+--------+-----------------------------------------+
|check                             |table             |failed_rows|total_rows|status|severity|detail                                   |
+----------------------------------+------------------+-----------+----------+------+--------+-----------------------------------------+
|not_null:order_id                 |silver_orders     |0          |5         |PASS  |error   |                                         |
|not_null:customer_id              |silver_orders     |0          |5         |PASS  |error   |                                         |
|not_null:order_ts                 |silver_orders     |0          |5         |PASS  |error   |                                         |
|unique:order_id                   |silver_orders     |1          |5         |FAIL  |error   |[1002]                                   |
|fk:customer_id->silver_customers  |silver_orders     |1          |5         |FAIL  |error   |[1006]                                   |
|range:amount>=0                   |silver_orders     |0          |5         |PASS  |error   |                                         |
|accepted:currency                 |silver_orders     |0          |5         |PASS  |error   |                                         |
|range:qty>0                       |silver_order_items|1          |3         |FAIL  |warn    |                                         |
|freshness:order_ts<24h            |silver_orders     |0          |1         |PASS  |error   |latest=2026-03-02 09:00:00, lag_hours=3.0|
|reconcile:bronze=silver+quarantine|silver_orders     |0          |8         |PASS  |error   |bronze=8, silver=5, quarantine=3         |
+----------------------------------+------------------+-----------+----------+------+--------+-----------------------------------------+

blocking failures: 2
-> the job would stop here, before gold is refreshed
```

The suite found what the row rules could not: order 1002 twice (deduplication is missing; chapter 9, section 9.6) and
order 1006 for customer 12, who does not exist. The `warn` on `qty = 0` is recorded but does not block.

Design notes that interviewers like to hear:

- **Report, then decide.** The suite never raises inside a check; it returns rows. The caller decides what blocks.
  That keeps every result, even when the first check fails.
- **The freshness clock is a parameter.** A fixed `AS_OF` makes the check testable; production passes the current
  time.
- **Reconcile with the right formula.** Here bronze = silver + quarantine holds because silver is not yet
  deduplicated. After deduplication the formula becomes bronze = distinct events in silver + duplicates removed +
  quarantine; write the formula that matches your steps, or the check fails every day and people learn to ignore it.
- **Each check is one Spark job or more.** Ten `count()` calls are ten scans; on large tables compute several checks
  in one aggregation (the `expectation_metrics` helper in `src/ch14/s2_quality.py` does all rules in one `agg`).

!!! warning "A left join is not a referential-integrity check"
    `o.join(c, "customer_id", "left")` keeps every order and fills customer columns with `NULL` for orphans, so it
    looks fine. Use `left_anti` (rows of the left side with no match) and count them, as above.

## 14.10 Change data capture: what arrives and why it is hard

*Level: intermediate.*

Red Rock's customer table lives in an operational database. Copying all of it every night is slow and loses
everything that happened between copies. **Change data capture** (CDC) instead "treats a database as a set of
changes"; a CDC feed contains "only the modified records", and each record includes "The operation type (`INSERT`,
`UPDATE`, `DELETE`)", "The data values for the record" and "A sequence number or timestamp for deterministic
ordering" ([Change data capture and snapshots](https://docs.databricks.com/aws/en/data-engineering/what-is-cdc), the
"CDC concepts page" below).
Databases such as SQL Server, MySQL and Oracle produce such feeds, tools such as Debezium or Oracle GoldenGate carry
them out of the database, and a Delta table with Change Data Feed enabled produces one too (same page; Change Data
Feed is chapter 9, section 9.11).

Here is the Red Rock feed used in the rest of the chapter, in the style of a log-based tool: an operation code
(`c` create, `u` update, `d` delete) and `lsn`, a log sequence number that increases with every committed change in
the source. These are Debezium's codes: its change events carry an `op` field whose valid values are `c` (create),
`u` (update), `d` (delete), `r` (read, snapshots only) and `t` (truncate)
([Debezium connector for PostgreSQL](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)).
Nothing below depends on them; any feed with an operation column works the same way.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
+-----------+------------+------------------------+---------+-------+---+---+--------+
|customer_id|name        |email                   |city     |country|op |lsn|batch_id|
+-----------+------------+------------------------+---------+-------+---+---+--------+
|7          |Ava Chen    |ava.chen@example.com    |Calgary  |CA     |c  |100|1       |
|8          |Ben Ortiz   |ben.ortiz@example.com   |Denver   |US     |c  |101|1       |
|9          |Chloe Martin|chloe.m@example.com     |Moab     |US     |c  |102|1       |
|7          |Ava Chen    |ava.chen@example.com    |Banff    |CA     |u  |110|1       |
|10         |Dev Patel   |dev.patel@example.com   |Vancouver|CA     |c  |120|2       |
|8          |Ben Ortiz   |ben.o@example.com       |Denver   |US     |u  |121|2       |
|9          |NULL        |NULL                    |NULL     |NULL   |d  |125|2       |
|7          |Ava Chen    |ava.chen@example.com    |Canmore  |CA     |u  |130|2       |
|9          |Chloe Martin|chloe.martin@example.com|Moab     |US     |u  |115|3       |
|7          |Ava Chen    |ava.chen@example.com    |Cochrane |CA     |u  |118|3       |
+-----------+------------+------------------------+---------+-------+---+---+--------+
```

`batch_id` is the order in which the records landed in bronze. Batch 3 is the interesting one: both of its events
are **late**. Ava's move to Cochrane happened at `lsn` 118, before her move to Canmore (130) that already arrived in
batch 2. Chloe's email change happened at 115, before her delete at 125. Applying a feed like this correctly means
solving five problems at once:

1. **Ordering.** Arrival order is not event order. Only the sequence column says which change is newer.
2. **Deletes.** A delete must remove the row, and a late update for a deleted key must not bring it back.
3. **Several changes per key in one batch.** Ava has two events in batch 1; a `MERGE` source needs one row per key.
4. **Replays.** The same batch can be delivered twice; applying it again must change nothing.
5. **History.** Some tables need only the current state; others need every version with its validity range.

The last point is the **slowly changing dimension** (SCD) type. **SCD Type 1** keeps only the current row per key.
**SCD Type 2** keeps one row per version; in `AUTO CDC` the validity range is in two added columns, `__START_AT` and
`__END_AT`, and "Active records have `__END_AT = NULL`" (CDC concepts page).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="The change feed for customer 7, in arrival order: lsn 100 Calgary, 110 Banff, 130 Canmore, 118 Cochrane late. SCD Type 1 keeps one row, Canmore. SCD Type 2 keeps four rows ordered by lsn: Calgary 100 to 110, Banff 110 to 118, Cochrane 118 to 130, Canmore 130 to NULL">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="16" y="60" width="210" height="170" rx="6"/>
<rect x="276" y="20" width="348" height="70" rx="6"/>
<rect x="276" y="116" width="348" height="168" rx="6"/>
<line x1="226" y1="110" x2="268" y2="60"/>
<line x1="226" y1="180" x2="268" y2="190"/>
</g>
<g fill="currentColor">
<polygon points="272,55 262,58 268,66"/>
<polygon points="276,191 266,185 265,195"/>
</g>
<g fill="currentColor" font-size="13">
<text x="121" y="84" text-anchor="middle">feed for customer 7</text>
<text x="121" y="102" text-anchor="middle">(arrival order)</text>
<text x="32" y="132">lsn 100  c  Calgary</text>
<text x="32" y="156">lsn 110  u  Banff</text>
<text x="32" y="180">lsn 130  u  Canmore</text>
<text x="32" y="204">lsn 118  u  Cochrane (late)</text>
<text x="450" y="44" text-anchor="middle">SCD Type 1: one row per key</text>
<text x="450" y="70" text-anchor="middle">7  Ava Chen  Canmore</text>
<text x="450" y="140" text-anchor="middle">SCD Type 2: one row per version</text>
<text x="300" y="166">city</text>
<text x="430" y="166">__START_AT</text>
<text x="530" y="166">__END_AT</text>
<text x="300" y="190">Calgary</text>
<text x="430" y="190">100</text>
<text x="530" y="190">110</text>
<text x="300" y="212">Banff</text>
<text x="430" y="212">110</text>
<text x="530" y="212">118</text>
<text x="300" y="234">Cochrane</text>
<text x="430" y="234">118</text>
<text x="530" y="234">130</text>
<text x="300" y="256">Canmore</text>
<text x="430" y="256">130</text>
<text x="530" y="256">NULL</text>
</g>
</svg>
<figcaption>Figure 14.3. One feed, two targets. SCD Type 1 ignores the late Cochrane event because a newer change is
already applied; SCD Type 2 slots it into history at its sequence position. Both results are from the run in section
14.13.</figcaption>
</figure>

## 14.11 AUTO CDC (formerly APPLY CHANGES)

*Level: expert.*

Writing those five rules by hand in `MERGE` is what chapter 9 did, and the CDC page is blunt about it: "Historically,
teams have relied on custom `MERGE INTO` logic ... This approach is complex and error-prone"
([Change data capture and snapshots](https://docs.databricks.com/aws/en/data-engineering/what-is-cdc)). Lakeflow
pipelines provide two APIs instead: `AUTO CDC` for change feeds and `AUTO CDC FROM SNAPSHOT` for full snapshots. On
the name: "The `AUTO CDC` APIs replace the `APPLY CHANGES` APIs and have the same syntax. The `APPLY CHANGES` APIs
are still available, but Databricks recommends using the `AUTO CDC` APIs in their place"
([The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc), the "CDC page" below). In Python, `create_auto_cdc_flow()` "replaces the
previous function `apply_changes()`. The two functions have the same signature"
([create_auto_cdc_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes)).

Requirements, from the CDC page: the pipeline must be serverless or use the `Pro` or `Advanced` edition; you declare
a target **streaming table** first and then add the flow; the source "must be a **streaming** source"
([AUTO CDC INTO](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-apply-changes-into)).

### The SQL syntax

*Databricks only, not run here. Syntax from [AUTO CDC INTO (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-apply-changes-into).*

```sql
CREATE OR REFRESH STREAMING TABLE table_name;

CREATE FLOW flow_name AS AUTO CDC [ONCE] INTO table_name
FROM source
KEYS (keys)
[IGNORE NULL UPDATES [ON {columnList | * EXCEPT (exceptColumnList)}]]
[APPLY AS DELETE WHEN condition]
[APPLY AS TRUNCATE WHEN condition]
SEQUENCE BY orderByColumn
[SYSTEM SEQUENCE BY systemOrderByColumn]
[COLUMNS {columnList | * EXCEPT (exceptColumnList)}]
[STORED AS {SCD TYPE 1 | SCD TYPE 2 | BITEMPORAL}]
[TRACK HISTORY ON {columnList | * EXCEPT (exceptColumnList)}]
[COLUMNS TO UPDATE columnName]
```

The Red Rock customers, current state and full history, from the feed in bronze (pipeline default schema
`shop.silver`):

*Databricks only, not run here. Syntax from [The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc).*

```sql
CREATE OR REFRESH STREAMING TABLE customers_current;

CREATE FLOW customers_current_cdc AS AUTO CDC INTO customers_current
FROM STREAM(shop.bronze.customers_cdc)
KEYS (customer_id)
APPLY AS DELETE WHEN op = 'd'
SEQUENCE BY lsn
COLUMNS * EXCEPT (op, lsn, batch_id)
STORED AS SCD TYPE 1;

CREATE OR REFRESH STREAMING TABLE customers_history;

CREATE FLOW customers_history_cdc AS AUTO CDC INTO customers_history
FROM STREAM(shop.bronze.customers_cdc)
KEYS (customer_id)
APPLY AS DELETE WHEN op = 'd'
SEQUENCE BY lsn
COLUMNS * EXCEPT (op, lsn, batch_id)
STORED AS SCD TYPE 2;
```

### The Python API

*Databricks only, not run here. Syntax from [create_auto_cdc_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes).*

```python
from pyspark import pipelines as dp
from pyspark.sql.functions import col, expr

@dp.temporary_view
def customers_changes():
    return spark.readStream.table("shop.bronze.customers_cdc")

dp.create_streaming_table("customers_history")

dp.create_auto_cdc_flow(
    target="customers_history",
    source="customers_changes",
    keys=["customer_id"],
    sequence_by=col("lsn"),
    apply_as_deletes=expr("op = 'd'"),
    except_column_list=["op", "lsn", "batch_id"],
    stored_as_scd_type=2,
)
```

The parameters you will be asked about, all from the Python reference (the SQL clause is in brackets):

| Parameter | Meaning |
| --- | --- |
| `target` | The streaming table to update; create it first with `create_streaming_table()` |
| `source` | The dataset that holds the CDC records |
| `keys` (`KEYS`) | Required. "The column or combination of columns that uniquely identify a row in the source data" |
| `sequence_by` (`SEQUENCE BY`) | Required. The logical order of events; a column, or `struct(...)` of several columns to break ties: "it orders by the first struct field first, then by the second field if there's a tie" |
| `apply_as_deletes` (`APPLY AS DELETE WHEN`) | When an event is a delete rather than an upsert |
| `apply_as_truncates` (`APPLY AS TRUNCATE WHEN`) | When an event truncates the whole table; "supported only for SCD type 1" |
| `column_list` / `except_column_list` (`COLUMNS`) | Which columns land in the target; default all |
| `stored_as_scd_type` (`STORED AS`) | `1`, `2` or `"bitemporal"`; "The default is SCD type 1" |
| `track_history_column_list` / `track_history_except_column_list` (`TRACK HISTORY ON`) | SCD Type 2 only: which columns create a new version when they change |
| `ignore_null_updates` (`IGNORE NULL UPDATES`) | `True` keeps the existing value when an update carries `NULL`; "Defaults to `False`" |
| `columns_to_update` (`COLUMNS TO UPDATE`) | A source column of type `array<string>` naming the columns each record updates; for partial updates with explicit `NULL`s |
| `name`, `once` (`ONCE`) | Flow name (default: the target name); a one-time flow such as a backfill |

Default behavior for inserts and updates is an **upsert**: "update any rows in the target table that match the
specified key(s) or insert a new row when a matching record does not exist in the target table"
([create_auto_cdc_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes)).

### What the SCD Type 2 target looks like

The target gets `__START_AT` and `__END_AT`, filled from the sequence column: "For SCD Type 2, the pipeline
propagates sequencing values to the `__START_AT` and `__END_AT` columns of the target table"
([Change data capture and snapshots](https://docs.databricks.com/aws/en/data-engineering/what-is-cdc)). Sequencing
by `lsn` gives `BIGINT` ranges; sequencing by a timestamp gives timestamp ranges. If you declare the target's schema
yourself, "you must also include the `__START_AT` and `__END_AT` columns with the same data type as the
`sequence_by` field" ([AUTO CDC INTO](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-apply-changes-into)).
To rename them for consumers, the advanced page suggests a view
(`__START_AT AS valid_from, __END_AT AS valid_to`) over the target
([Advanced AUTO CDC topics](https://docs.databricks.com/aws/en/ldp/cdc-advanced)).

`TRACK HISTORY ON` narrows what creates a version. With `TRACK HISTORY ON * EXCEPT (email)`, a new email would
overwrite the current row instead of opening a new version: "changes to untracked columns update the current version
in place rather than creating a new historical record" (CDC concepts page).

### Deletes, tombstones, truncates

A delete in SCD Type 1 removes the row; in SCD Type 2 it closes the current version (its `__END_AT` becomes the
delete's sequence value) and no new version opens. To survive late events, a deleted key is remembered for a while:
"the deleted row is temporarily retained as a tombstone in the underlying Delta table, and a view is created in the
metastore that filters out these tombstones. The retention interval defaults to two days, and can be configured with
the `pipelines.cdc.tombstoneGCThresholdInSeconds` table property"
([create_auto_cdc_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes)). The same
paragraph warns that Auto Loader "does not guarantee file processing order", so set the threshold above the longest
delay you expect between an event and its processing. A truncate (`APPLY AS TRUNCATE WHEN`) clears the whole SCD
Type 1 table at that sequence point; "SCD type 2 does not support the truncate operation".

### Around the target

Facts from the advanced page that come up in design questions
([Advanced AUTO CDC topics](https://docs.databricks.com/aws/en/ldp/cdc-advanced)):

- **Downstream streaming.** "To stream data from the target of an AUTO CDC process, read from its change feed" (CDC
  page, Limitations). The target is not append-only, so a plain stream of it is the wrong tool; its change data feed
  is readable on Databricks Runtime 15.2 and above when the target is published to Unity Catalog.
- **Manual fixes.** Targets published to Unity Catalog accept `INSERT`, `UPDATE`, `DELETE` and `MERGE`, but you
  must keep valid `__START_AT` and `__END_AT` values yourself.
- **Metrics.** `AUTO CDC` records `num_upserted_rows` and `num_deleted_rows`; "The `num_output_rows` metric, output
  for non-CDC flows, is not captured for `AUTO CDC` queries". `AUTO CDC FROM SNAPSHOT` does not record these two.
- **Hive metastore only:** the target is a view over an internal table named `__apply_changes_storage_<target>`; do
  not modify that table directly.

!!! tip "In the interview"
    **"How does APPLY CHANGES work?"** `APPLY CHANGES` was renamed `AUTO CDC` with the same syntax
    ([AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)); in Python `dlt.apply_changes` became
    `dp.create_auto_cdc_flow`, in Lakeflow pipelines (formerly Delta Live Tables,
    [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)). You create a target streaming table, then a
    flow with `KEYS`, `SEQUENCE BY`, optional `APPLY AS DELETE WHEN`, `COLUMNS * EXCEPT (...)` and
    `STORED AS SCD TYPE 1` or `2`. It upserts by key in sequence order, drops or slots in late events, keeps
    tombstones for deletes, and for Type 2 maintains `__START_AT` and `__END_AT`. It needs the Pro or Advanced
    edition, or serverless.

## 14.12 How the sequence column fixes out-of-order events

*Level: expert.*

`AUTO CDC` "automatically handles out-of-sequence records by processing events in the order defined by the
sequencing column" ([Change data capture and snapshots](https://docs.databricks.com/aws/en/data-engineering/what-is-cdc)).
What that means differs by SCD type, and the comparison table on that page states it exactly:

- SCD Type 1: "Applied in sequence order. Late changes older than the current version are dropped."
- SCD Type 2: "Inserted into history in sequence order."

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 260" role="img" aria-label="Top row, arrival order: lsn 100 Calgary batch 1, lsn 110 Banff batch 1, lsn 130 Canmore batch 2, lsn 118 Cochrane batch 3. Bottom row, sequence order: 100 Calgary, 110 Banff, 118 Cochrane, 130 Canmore, with SCD Type 2 ranges 100 to 110, 110 to 118, 118 to 130, 130 to NULL. The lines for 118 and 130 cross">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="30" y="44" width="130" height="48" rx="6"/>
<rect x="180" y="44" width="130" height="48" rx="6"/>
<rect x="330" y="44" width="130" height="48" rx="6"/>
<rect x="480" y="44" width="130" height="48" rx="6" stroke-dasharray="5 4"/>
<rect x="30" y="170" width="130" height="48" rx="6"/>
<rect x="180" y="170" width="130" height="48" rx="6"/>
<rect x="330" y="170" width="130" height="48" rx="6"/>
<rect x="480" y="170" width="130" height="48" rx="6"/>
<line x1="95" y1="92" x2="95" y2="162"/>
<line x1="245" y1="92" x2="245" y2="162"/>
<line x1="395" y1="92" x2="541" y2="164"/>
<line x1="545" y1="92" x2="399" y2="164"/>
</g>
<g fill="currentColor">
<polygon points="95,170 90,160 100,160"/>
<polygon points="245,170 240,160 250,160"/>
<polygon points="545,170 534,167 540,158"/>
<polygon points="395,170 400,158 406,167"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="320" y="26">arrival order (how the batches landed)</text>
<text x="95" y="64">lsn 100 Calgary</text>
<text x="95" y="82">batch 1</text>
<text x="245" y="64">lsn 110 Banff</text>
<text x="245" y="82">batch 1</text>
<text x="395" y="64">lsn 130 Canmore</text>
<text x="395" y="82">batch 2</text>
<text x="545" y="64">lsn 118 Cochrane</text>
<text x="545" y="82">batch 3 (late)</text>
<text x="95" y="190">Calgary</text>
<text x="95" y="208">100 to 110</text>
<text x="245" y="190">Banff</text>
<text x="245" y="208">110 to 118</text>
<text x="395" y="190">Cochrane</text>
<text x="395" y="208">118 to 130</text>
<text x="545" y="190">Canmore</text>
<text x="545" y="208">130 to NULL</text>
<text x="320" y="248">sequence order (SEQUENCE BY lsn): the order AUTO CDC applies, with SCD 2 ranges</text>
</g>
</svg>
<figcaption>Figure 14.4. The sequence column, not the arrival order, decides. In SCD Type 1 the late Cochrane event
loses to Canmore (130 &gt; 118); in SCD Type 2 it becomes the 118 to 130 version and shortens Banff to end at 118.</figcaption>
</figure>

Rules for the sequence column, from the pages:

- It "must be a sortable data type", and "`NULL` sequencing values are not supported" (CDC page, Limitations).
- It "must be a monotonically increasing representation of the correct event order, with one distinct update per key
  at each sequencing value" (CDC concepts page). Two events for one key with the same value are a problem the API does
  not solve for you; add a tie-breaker with `struct(...)`.
- A transaction log position (an LSN) or a commit sequence number is the safest choice. An `updated_at` set by an
  application can repeat or go backwards.

A delete that arrives before an older update is the classic trap: if the deleted key were simply gone, the late
update would insert it again. That is why the tombstone exists, and why its retention must exceed the lateness you
expect. After the tombstone is garbage-collected, a very late update for that key would presumably be treated as
new; that is an inference from the tombstone description, **not verified** on any page.

## 14.13 Emulating AUTO CDC with MERGE on Delta 4.4.1

*Level: expert.*

`AUTO CDC` needs a Lakeflow pipeline on Databricks. To see its results here, this section rebuilds the same behavior
with plain Delta `MERGE`. **This is an emulation**, written for this chapter: it reproduces the documented outputs,
not the internal implementation. As a check, the same code was run on the sample data of the Databricks AUTO CDC page
and produced exactly the tables printed there (shown at the end of the section).

Chapter 9 already built SCD Type 1 and Type 2 with `MERGE` from full customer records ordered by `updated_at`
([sections 9.9 and 9.10](09-Building-Silver.md#99-scd-type-1-with-merge)). Three things are new here: explicit
delete events, tombstones so a late update cannot resurrect a deleted customer, and SCD Type 2 that **inserts** a late
version into the middle of history. Chapter 9's Type 2 `MERGE` guards with `s.updated_at > t.valid_from` and so
ignores a late version; `AUTO CDC` does not.

### SCD Type 1: the naive MERGE, and the sequence-guarded one

Both read one batch, keep the latest event per key (an in-batch deduplication with `QUALIFY`), then merge. The naive
one applies whatever arrives:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
MERGE INTO customers_naive AS t
USING (
  SELECT * FROM customers_cdc WHERE batch_id = 3
  QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY lsn DESC) = 1
) AS s
ON t.customer_id = s.customer_id
WHEN MATCHED AND s.op = 'd' THEN DELETE
WHEN MATCHED THEN UPDATE SET name = s.name, email = s.email, city = s.city, country = s.country
WHEN NOT MATCHED AND s.op <> 'd' THEN INSERT (customer_id, name, email, city, country)
  VALUES (s.customer_id, s.name, s.email, s.city, s.country)
```

The guarded one keeps the last applied `lsn` and a `__deleted` flag in the stored table, and a view hides the
tombstones, as the API reference describes for `AUTO CDC`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
CREATE TABLE customers_scd1_store (customer_id INT, name STRING, email STRING, city STRING,
  country STRING, __lsn BIGINT, __deleted BOOLEAN) USING DELTA;
CREATE VIEW customers_scd1 AS
  SELECT * EXCEPT (__lsn, __deleted) FROM customers_scd1_store WHERE NOT __deleted;

MERGE INTO customers_scd1_store AS t
USING (
  SELECT * FROM customers_cdc WHERE batch_id = 3
  QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY lsn DESC) = 1
) AS s
ON t.customer_id = s.customer_id
WHEN MATCHED AND s.lsn > t.__lsn AND s.op = 'd' THEN
  UPDATE SET __deleted = true, __lsn = s.lsn
WHEN MATCHED AND s.lsn > t.__lsn THEN
  UPDATE SET name = s.name, email = s.email, city = s.city, country = s.country, __deleted = false, __lsn = s.lsn
WHEN NOT MATCHED THEN
  INSERT (customer_id, name, email, city, country, __lsn, __deleted)
  VALUES (s.customer_id, s.name, s.email, s.city, s.country, s.lsn, s.op = 'd')
```

A delete for a key never seen inserts a tombstone too, so an even older insert arriving later is also blocked. After
batches 1, 2 and 3 (the script runs the same statement with `batch_id` 1, 2, 3):

```text
========== after batch 3
>>> SELECT customer_id, name, email, city FROM customers_naive ORDER BY customer_id
+-----------+------------+------------------------+---------+
|customer_id|name        |email                   |city     |
+-----------+------------+------------------------+---------+
|7          |Ava Chen    |ava.chen@example.com    |Cochrane |
|8          |Ben Ortiz   |ben.o@example.com       |Denver   |
|9          |Chloe Martin|chloe.martin@example.com|Moab     |
|10         |Dev Patel   |dev.patel@example.com   |Vancouver|
+-----------+------------+------------------------+---------+

>>> SELECT customer_id, name, email, city FROM customers_scd1 ORDER BY customer_id
+-----------+---------+---------------------+---------+
|customer_id|name     |email                |city     |
+-----------+---------+---------------------+---------+
|7          |Ava Chen |ava.chen@example.com |Canmore  |
|8          |Ben Ortiz|ben.o@example.com    |Denver   |
|10         |Dev Patel|dev.patel@example.com|Vancouver|
+-----------+---------+---------------------+---------+

>>> SELECT customer_id, email, city, __lsn, __deleted FROM customers_scd1_store ORDER BY customer_id
+-----------+---------------------+---------+-----+---------+
|customer_id|email                |city     |__lsn|__deleted|
+-----------+---------------------+---------+-----+---------+
|7          |ava.chen@example.com |Canmore  |130  |false    |
|8          |ben.o@example.com    |Denver   |121  |false    |
|9          |chloe.m@example.com  |Moab     |125  |true     |
|10         |dev.patel@example.com|Vancouver|120  |false    |
+-----------+---------------------+---------+-----+---------+
```

The naive table has two wrong rows: Ava is back in Cochrane (118 overwrote 130) and Chloe, deleted at 125, is alive
again with an email from 115. The guarded table is right: both late events failed `s.lsn > t.__lsn`, and Chloe's
tombstone (`__deleted = true`, `__lsn = 125`) is what blocked her resurrection. Running batch 3 a second time changed
nothing (3 rows in `customers_scd1`, the same as before).

The same guarded `MERGE` with the PySpark `DeltaTable` builder, run over the same three batches with the same result
(`src/ch14/s5_scd1_pyspark.py`):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from delta.tables import DeltaTable
from pyspark.sql import Window, functions as F

COLS = ["name", "email", "city", "country"]
target = DeltaTable.forName(spark, "customers_scd1_store")
latest = (spark.table("customers_cdc").where(F.col("batch_id") == batch)
          .withColumn("rn", F.row_number().over(
              Window.partitionBy("customer_id").orderBy(F.col("lsn").desc())))
          .where("rn = 1"))
(target.alias("t")
 .merge(latest.alias("s"), "t.customer_id = s.customer_id")
 .whenMatchedUpdate(condition="s.lsn > t.__lsn AND s.op = 'd'",
                    set={"__deleted": "true", "__lsn": "s.lsn"})
 .whenMatchedUpdate(condition="s.lsn > t.__lsn",
                    set={**{c: f"s.{c}" for c in COLS}, "__deleted": "false", "__lsn": "s.lsn"})
 .whenNotMatchedInsert(values={"customer_id": "s.customer_id", **{c: f"s.{c}" for c in COLS},
                               "__lsn": "s.lsn", "__deleted": "s.op = 'd'"})
 .execute())
```

### SCD Type 2: rebuild the touched keys, then one MERGE

A late event can change the middle of a key's history: Cochrane at 118 must shorten Banff and start before Canmore.
Patching that with conditions is error-prone, so the emulation recomputes the whole history of every key the batch
touches from the change log in bronze, then applies the difference with one `MERGE`. Step 1, the versions:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
WITH ev AS (           -- every event so far for the keys this batch touches
  SELECT * FROM customers_cdc
  WHERE batch_id <= 3
    AND customer_id IN (SELECT customer_id FROM customers_cdc WHERE batch_id = 3)
),
marked AS (
  SELECT *, lag(op) OVER w AS prev_op,
         (lag(name) OVER w <=> name AND lag(email) OVER w <=> email
          AND lag(city) OVER w <=> city AND lag(country) OVER w <=> country) AS same_as_prev
  FROM ev
  WINDOW w AS (PARTITION BY customer_id ORDER BY lsn)
),
changes AS (           -- deletes, and upserts that change at least one column
  SELECT * FROM marked
  WHERE op = 'd' OR prev_op IS NULL OR prev_op = 'd' OR NOT same_as_prev
)
SELECT customer_id, name, email, city, country,
       lsn AS __START_AT,
       lead(lsn) OVER (PARTITION BY customer_id ORDER BY lsn) AS __END_AT,
       op
FROM changes
```

Each change opens a version that ends at the next change of the same key, delete included; a delete itself opens no
version. An update that changes nothing is skipped, matching "SCD Type 2 creates a new version whenever any column
value changes" (CDC page). Step 2, saved as the view `scd2_rebuilt`, is merged on `(key, __START_AT)`; versions of
touched keys that no longer exist are deleted with `WHEN NOT MATCHED BY SOURCE`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
MERGE INTO customers_scd2 AS t
USING (SELECT * FROM scd2_rebuilt WHERE op <> 'd') AS s
ON t.customer_id = s.customer_id AND t.__START_AT = s.__START_AT
WHEN MATCHED AND NOT (t.name <=> s.name AND t.email <=> s.email AND t.city <=> s.city
                      AND t.country <=> s.country AND t.__END_AT <=> s.__END_AT) THEN
  UPDATE SET name = s.name, email = s.email, city = s.city, country = s.country, __END_AT = s.__END_AT
WHEN NOT MATCHED THEN
  INSERT (customer_id, name, email, city, country, __START_AT, __END_AT)
  VALUES (s.customer_id, s.name, s.email, s.city, s.country, s.__START_AT, s.__END_AT)
WHEN NOT MATCHED BY SOURCE AND t.customer_id IN (7, 9) THEN
  DELETE
```

The key list in the last clause is the batch's keys, filled in by the script. After batch 2 and after batch 3:

```text
========== after batch 2
>>> SELECT customer_id, name, email, city, __START_AT, __END_AT FROM customers_scd2 ORDER BY customer_id, __START_AT
+-----------+------------+---------------------+---------+----------+--------+
|customer_id|name        |email                |city     |__START_AT|__END_AT|
+-----------+------------+---------------------+---------+----------+--------+
|7          |Ava Chen    |ava.chen@example.com |Calgary  |100       |110     |
|7          |Ava Chen    |ava.chen@example.com |Banff    |110       |130     |
|7          |Ava Chen    |ava.chen@example.com |Canmore  |130       |NULL    |
|8          |Ben Ortiz   |ben.ortiz@example.com|Denver   |101       |121     |
|8          |Ben Ortiz   |ben.o@example.com    |Denver   |121       |NULL    |
|9          |Chloe Martin|chloe.m@example.com  |Moab     |102       |125     |
|10         |Dev Patel   |dev.patel@example.com|Vancouver|120       |NULL    |
+-----------+------------+---------------------+---------+----------+--------+

========== after batch 3
>>> SELECT customer_id, name, email, city, __START_AT, __END_AT FROM customers_scd2 ORDER BY customer_id, __START_AT
+-----------+------------+------------------------+---------+----------+--------+
|customer_id|name        |email                   |city     |__START_AT|__END_AT|
+-----------+------------+------------------------+---------+----------+--------+
|7          |Ava Chen    |ava.chen@example.com    |Calgary  |100       |110     |
|7          |Ava Chen    |ava.chen@example.com    |Banff    |110       |118     |
|7          |Ava Chen    |ava.chen@example.com    |Cochrane |118       |130     |
|7          |Ava Chen    |ava.chen@example.com    |Canmore  |130       |NULL    |
|8          |Ben Ortiz   |ben.ortiz@example.com   |Denver   |101       |121     |
|8          |Ben Ortiz   |ben.o@example.com       |Denver   |121       |NULL    |
|9          |Chloe Martin|chloe.m@example.com     |Moab     |102       |115     |
|9          |Chloe Martin|chloe.martin@example.com|Moab     |115       |125     |
|10         |Dev Patel   |dev.patel@example.com   |Vancouver|120       |NULL    |
+-----------+------------+------------------------+---------+----------+--------+
```

Batch 3 rewrote history in two places. Ava's Banff version now ends at 118 and a Cochrane version fills 118 to 130.
Chloe, already deleted, gained a version from 115 to 125 with her new email, and her history still ends at the delete
(125); no current row for her appears. A point-in-time query reads the table as it was at any sequence value:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT customer_id, email, city FROM customers_scd2
WHERE __START_AT <= 115 AND (__END_AT IS NULL OR __END_AT > 115) ORDER BY customer_id;
```

```text
+-----------+------------------------+------+
|customer_id|email                   |city  |
+-----------+------------------------+------+
|7          |ava.chen@example.com    |Banff |
|8          |ben.ortiz@example.com   |Denver|
|9          |chloe.martin@example.com|Moab  |
+-----------+------------------------+------+
```

Replaying batch 3 left 9 rows and the same current rows: the rebuild yields the same versions, every `MATCHED`
condition is false, and nothing is written.

### The check against the documentation

The AUTO CDC page publishes eight sample events for users 123 to 126 (with an out-of-order update at sequence 5 after
the events at 6) and the expected SCD Type 1 and Type 2 tables ([The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc)).
Mapping `INSERT`/`UPDATE`/`DELETE` to `c`/`u`/`d` and `sequenceNum` to `lsn`, the same two statements give:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
>>> SELECT * FROM users_scd1 ORDER BY userId
+------+--------+-----------+
|userId|name    |city       |
+------+--------+-----------+
|124   |Raul    |Oaxaca     |
|125   |Mercedes|Guadalajara|
|126   |Lily    |Cancun     |
+------+--------+-----------+

>>> SELECT * FROM users_scd2 ORDER BY userId, __START_AT
+------+--------+-----------+----------+--------+
|userId|name    |city       |__START_AT|__END_AT|
+------+--------+-----------+----------+--------+
|123   |Isabel  |Monterrey  |1         |5       |
|123   |Isabel  |Chihuahua  |5         |6       |
|124   |Raul    |Oaxaca     |1         |NULL    |
|125   |Mercedes|Tijuana    |2         |5       |
|125   |Mercedes|Mexicali   |5         |6       |
|125   |Mercedes|Guadalajara|6         |NULL    |
|126   |Lily    |Cancun     |2         |NULL    |
+------+--------+-----------+----------+--------+
```

Both match the tables on the page row for row. What the emulation leaves out, and `AUTO CDC` handles: tombstone
garbage collection, truncates, `TRACK HISTORY ON`, partial updates (`IGNORE NULL UPDATES`, `COLUMNS TO UPDATE`),
schema handling, and the cost: the rebuild rereads the change log of every touched key, which grows without limit.

| | Chapter 9 `MERGE` | This emulation | `AUTO CDC` |
| --- | --- | --- | --- |
| Input | full records with `updated_at` | change events with `op` and `lsn` | change events, any sequence column |
| Deletes | not handled (no delete events) | tombstones in SCD 1, closing version in SCD 2 | tombstones, `APPLY AS DELETE WHEN` |
| Late event, SCD 1 | ignored by the `>` guard | ignored by the `>` guard | "dropped" |
| Late event, SCD 2 | ignored by the guard | inserted into history | "Inserted into history in sequence order" |
| Code you maintain | two statements | two statements plus the rebuild | one flow definition |

!!! tip "In the interview"
    **"How would you implement CDC without APPLY CHANGES?"** `APPLY CHANGES` is now `AUTO CDC`
    ([AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)); without it I deduplicate each batch to the
    latest event per key by the sequence column, then `MERGE` with a guard `s.seq > t.seq`. Deletes become tombstones
    so a late update cannot resurrect the row, and a view hides them. For SCD Type 2 with late events I rebuild the
    versions of touched keys from the change log with `lead()` and merge on key plus start. I can explain it, but I
    would use `AUTO CDC` in a Lakeflow pipeline (formerly Delta Live Tables,
    [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) where available.

## 14.14 Snapshots: AUTO CDC FROM SNAPSHOT

*Level: expert.*

Some sources have no change feed. Red Rock's product catalog comes from a supplier as a full export every night: every
product, no operation column, no sequence number. The CDC concepts page lists the usual reasons a source cannot
provide CDC (load on the production database, legacy systems, teams that do not own the source) and the answer for
them: `AUTO CDC FROM SNAPSHOT` "compares _consecutive snapshots_, generates a synthetic change feed, and applies SCD
Type 1 or Type 2 logic into the target table"
([Change data capture and snapshots](https://docs.databricks.com/aws/en/data-engineering/what-is-cdc)).

*Databricks only, not run here. Syntax from [create_auto_cdc_from_snapshot_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes-from-snapshot).*

```python
from pyspark import pipelines as dp

@dp.temporary_view(name="products_snapshot")
def products_snapshot():
    return spark.read.table("shop.bronze.products_latest")    # replaced by each nightly export

dp.create_streaming_table("products_history")

dp.create_auto_cdc_from_snapshot_flow(
    target="products_history",
    source="products_snapshot",
    keys=["product_id"],
    stored_as_scd_type=2,
)
```

The `source` is "Either the name of a table or view to snapshot periodically or a Python lambda function that returns
the snapshot DataFrame to be processed and the snapshot version". With a table or view, the snapshot "is read at the
time of the pipeline run, and the ingestion time is used as the snapshot version"
([Change data capture and snapshots](https://docs.databricks.com/aws/en/data-engineering/what-is-cdc)). With a
function, you return `(DataFrame, version)` for the next snapshot after the given one, or `None` when there is none;
"If the first invocation returns `None`, the pipeline update fails"
([create_auto_cdc_from_snapshot_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes-from-snapshot)).
The old Python name was `apply_changes_from_snapshot()` (same page).

In SQL the snapshot form is part of `CREATE FLOW`: a required `FROM SNAPSHOT (snapshot_query)` and an optional
`WITH VERSION (version_query)` that returns the next version, with `current_snapshot_version()` and
`last_snapshot_version()` to refer to it:

*Databricks only, not run here. Syntax from [CREATE FLOW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-flow).*

```sql
CREATE OR REFRESH STREAMING TABLE products_history;

CREATE FLOW products_snapshot_flow AS
AUTO CDC INTO products_history
FROM SNAPSHOT (
  SELECT product_id, name, category, price
  FROM shop.bronze.products_export
  WHERE export_version = (SELECT version FROM current_snapshot_version())
)
WITH VERSION (
  SELECT DISTINCT export_version AS version
  FROM shop.bronze.products_export
  WHERE NOT EXISTS (SELECT 1 FROM last_snapshot_version())
     OR export_version > (SELECT version FROM last_snapshot_version())
  ORDER BY version
  LIMIT 1
)
KEYS (product_id)
STORED AS SCD TYPE 2;
```

Here `shop.bronze.products_export` keeps every nightly export with an `export_version` number. The version query
follows the page's examples (they select the next version from a version table or from `list_files`) adapted to that
table; it was not run. The rules that matter:

- The version query "must return exactly one column of an orderable type and either 0 or 1 rows"; zero rows means no
  new snapshot. One pipeline update processes versions in order until the version query returns no rows.
- "Every version returned after a successful commit must be greater than the previously committed version"; a
  non-increasing version fails the update with `APPLY_CHANGES_FROM_SNAPSHOT_ERROR.OUT_OF_ORDER_SNAPSHOT_VERSION`.
- Without `WITH VERSION`, the snapshot query "runs only during the initial load"; a later update on a non-empty
  target fails with `AUTO_CDC_FROM_SNAPSHOT_NON_EMPTY_TARGET_WITHOUT_VERSION`
  ([CREATE FLOW](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-flow)).
- Keys present in the old snapshot but absent from the new one are deletes: "Rows with keys present in the target but
  no longer present in the source are deleted" (Python reference).
- Snapshots lose intermediate states: "if you get daily snapshots, and a user changes their address twice in one day
  (from `A` to `B`, then from `B` to `C`), your change feed might go directly from `A` to `C`" (CDC concepts page).
- "Expectations are not supported with `AUTO CDC FROM SNAPSHOT`" (expectations page). Check the snapshot before it
  reaches the flow.

For SCD Type 1 targets you can also combine one snapshot flow with one or more `AUTO CDC` flows into the same target,
"when a source provides periodic authoritative snapshots and a lower-latency CDC feed between snapshots"; this
requires triggered mode, the same number of keys in the same order in all flows, exactly the same data type for the
snapshot version and the sequencing column, and no expectations on the snapshot flow, and is not supported for SCD Type 2
([The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc)).

### The same idea, run here

The core of a snapshot flow is a diff: a full outer join of the previous and the new snapshot on the key. The diff
below produces a change feed in the same shape as the customer feed, with the snapshot version as `lsn`, and the SCD
Type 2 statements of section 14.13 apply it unchanged. Day 1 has three products; on day 2 the tent is cheaper, the
socks are gone and a water filter is new.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
INSERT INTO products_cdc
WITH old AS (SELECT * FROM products_snapshot WHERE snapshot_version = 1),
     new AS (SELECT * FROM products_snapshot WHERE snapshot_version = 2)
SELECT coalesce(n.product_id, o.product_id) AS product_id,
       n.name, n.category, n.price,
       CASE WHEN o.product_id IS NULL THEN 'c'
            WHEN n.product_id IS NULL THEN 'd'
            ELSE 'u' END AS op,
       CAST(2 AS BIGINT) AS lsn,
       2 AS batch_id
FROM old o FULL OUTER JOIN new n ON o.product_id = n.product_id
WHERE o.product_id IS NULL OR n.product_id IS NULL
   OR NOT (o.name <=> n.name AND o.category <=> n.category AND o.price <=> n.price);
```

```text
derived change feed for snapshot 2:
>>> SELECT * FROM products_cdc WHERE batch_id = 2 ORDER BY product_id
+----------+-------------+--------+------+---+---+--------+
|product_id|name         |category|price |op |lsn|batch_id|
+----------+-------------+--------+------+---+---+--------+
|1         |Trail Tent 2P|camping |229.00|u  |2  |2       |
|3         |NULL         |NULL    |NULL  |d  |2  |2       |
|4         |Water Filter |camping |49.00 |c  |2  |2       |
+----------+-------------+--------+------+---+---+--------+

>>> SELECT * FROM products_scd2 ORDER BY product_id, __START_AT
+----------+-------------+--------+------+----------+--------+
|product_id|name         |category|price |__START_AT|__END_AT|
+----------+-------------+--------+------+----------+--------+
|1         |Trail Tent 2P|camping |249.00|1         |2       |
|1         |Trail Tent 2P|camping |229.00|2         |NULL    |
|2         |Headlamp 300 |lighting|39.95 |1         |NULL    |
|3         |Merino Socks |clothing|29.95 |1         |2       |
|4         |Water Filter |camping |49.00 |2         |NULL    |
+----------+-------------+--------+------+----------+--------+
```

The headlamp did not change, so it is not in the feed and keeps one open version. This is the same pattern as the
snapshot example on the AUTO CDC page, where user 1 disappears and is ended at version 1 while users 2 and 3 get new
versions. The `<=>` (null-safe equality) matters: with `=`, a change from `NULL` to a value would compare as `NULL`
and be missed.

!!! tip "In the interview"
    **"The source only sends a full snapshot every day, no change flags. How do you build SCD Type 2?"** In Lakeflow
    pipelines (formerly Delta Live Tables, [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) I use
    `AUTO CDC FROM SNAPSHOT` (in old Python code `dlt.apply_changes_from_snapshot`,
    [reference](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes-from-snapshot))
    with the product key and `STORED AS SCD TYPE 2`; it diffs consecutive snapshots, treats missing keys as deletes
    and needs increasing versions. Without it, I diff the two snapshots with a full outer join and null-safe
    comparison and feed the result into the same SCD 2 `MERGE`. Either way, changes inside one day are invisible.

## 14.15 Does AUTO CDC run in open-source Spark?

*Level: expert.*

Databricks says no: "The `AUTO CDC` APIs are not supported by Apache Spark Declarative Pipelines"
([The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc)), and the Python reference marks both "Apply Changes
(CDC)" and "Expectations" as not available in Apache Spark
([Lakeflow pipelines Python language reference](https://docs.databricks.com/aws/en/ldp/developer/python-ref)). Yet
the installed `pyspark.pipelines` 4.2 module exports a `create_auto_cdc_flow` (the
[Spark 4.2.0 release notes](https://spark.apache.org/releases/spark-release-4-2-0.html) list "Auto CDC in Spark Declarative Pipelines for declarative SCD Type
1 upserts"), and the latest Apache Spark guide
(version 4.3.0) documents an open-source Auto CDC flow for SCD Type 1, adding that "SCD Type 2 is also supported" with
its documentation tracked separately
([Spark Declarative Pipelines Programming Guide](https://spark.apache.org/docs/latest/declarative-pipelines-programming-guide.html)).
What happens here:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
import pyspark
from pyspark import pipelines as dp

print("pyspark", pyspark.__version__)
print("pyspark.pipelines exports:", sorted(dp.__all__))
print("has expect / expect_or_drop / expect_or_fail / expect_all:",
      [hasattr(dp, n) for n in ("expect", "expect_or_drop", "expect_or_fail", "expect_all")])
print("has create_auto_cdc_from_snapshot_flow:", hasattr(dp, "create_auto_cdc_from_snapshot_flow"))
try:
    dp.create_auto_cdc_flow(target="customers", source="customer_changes", keys=["customer_id"],
                            sequence_by="lsn", stored_as_scd_type=2)
except Exception as e:
    print("stored_as_scd_type=2 ->", type(e).__name__ + ":", str(e).splitlines()[0])
```

```text
pyspark 4.2.0
pyspark.pipelines exports: ['append_flow', 'create_auto_cdc_flow', 'create_sink', 'create_streaming_table', 'materialized_view', 'table', 'temporary_view']
has expect / expect_or_drop / expect_or_fail / expect_all: [False, False, False, False]
has create_auto_cdc_from_snapshot_flow: False
stored_as_scd_type=2 -> PySparkTypeError: [NOT_EXPECTED_TYPE] Argument `stored_as_scd_type` should be Literal[1, '1'], got int.
```

Then a real one-file pipeline with `spark-pipelines run`: a streaming table of change events, a Delta streaming
table as target, and an SCD Type 1 `create_auto_cdc_flow(...)` with `apply_as_deletes="op = 'd'"` and
`except_column_list=["op", "lsn"]` (full script: `src/ch14/s4_autocdc_probe.py`):

```text
##### spark-pipelines run  (streaming table format: delta)
   Flow customer_changes is QUEUED.
   Flow customers is QUEUED.
   Flow customer_changes is STARTING.
   Flow customer_changes is RUNNING.
   Flow customer_changes has COMPLETED.
   ERROR: [AUTOCDC_TARGET_DOES_NOT_SUPPORT_MERGE] Cannot start AutoCDC flow: the target table `spark_catalog`.`default`.`customers` (format: delta) does not support row-level operations. AutoCDC requires a target backed by a connector that supports MERGE. SQLSTATE: 0A000
   Flow 'customers' has FAILED.
   Flow 'customers' has FAILED.
   Flow 'customers' has FAILED.
   Flow 'customers' has FAILED.
   Flow 'customers' has FAILED.
   Flow 'customers' has FAILED more than 2 times and will not be restarted.
   (exit code 1)
```

The open-source guide explains the error: the target's connector must implement the DSv2 `SupportsRowLevelOperations`
interface, and "Supporting the `MERGE INTO` SQL statement is not on its own sufficient: a connector can implement
MERGE through its own planner extension". Delta Lake 4.4.1 supports `MERGE` (this chapter used it throughout) but,
as the run shows, not through that interface. So on this machine: no expectations, Auto CDC only as SCD Type 1 in the
Python signature, and even that fails at run time with a Delta target. The answer for an interview stays the
Databricks one: `AUTO CDC` and expectations are Databricks features; open-source Spark is starting to add Auto CDC.

## 14.16 Practice questions

*Level: mixed.*

**Q1. A streaming table has `CONSTRAINT valid_amount EXPECT (amount >= 0)` and nothing else. A row arrives with
`amount = -5`. What happens to the row, and where can you see it?**

??? success "Answer"
    The row is written to the target. With no `ON VIOLATION` clause the action is warn, the default: "Invalid
    records are written to the target." The failure is counted: the expectation's `failed_records` goes up in the
    pipeline's **Data quality** tab and in the event log (`details:flow_progress.data_quality.expectations`).

    **Why:** warn exists so you can measure a rule before enforcing it. Change the clause to
    `ON VIOLATION DROP ROW` or `FAIL UPDATE` once the rule is trusted.

**Q2. Name the six Python expectation decorators and say which ones SQL has no direct equivalent for.**

??? success "Answer"
    `@dp.expect`, `@dp.expect_or_drop`, `@dp.expect_or_fail` (one rule each) and `@dp.expect_all`,
    `@dp.expect_all_or_drop`, `@dp.expect_all_or_fail` (a dictionary `{name: constraint}`). SQL has the first three
    as `EXPECT`, `EXPECT ... ON VIOLATION DROP ROW` and `EXPECT ... ON VIOLATION FAIL UPDATE`; the grouped
    `expect_all` forms are Python only ("only Python allows you to group multiple expectations and specify collective
    actions"). In SQL you list several `CONSTRAINT` clauses instead. Old code from Delta Live Tables (now Lakeflow
    pipelines, [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) uses `@dlt.expect` and friends.

    **Why:** a dictionary lets you keep rules in one place (or a rules table) and apply them to several datasets.

**Q3. On which objects can you attach expectations, and where are they not supported?**

??? success "Answer"
    Streaming tables, materialized views and temporary views in a pipeline; streaming tables and materialized views
    created in Databricks SQL; and a streaming table declared with `dp.create_streaming_table(...)` through its
    `expect_all*` parameters (used for `AUTO CDC` targets; `AUTO CDC` was formerly `APPLY CHANGES`, [AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)). Not supported: sinks, and `AUTO CDC FROM SNAPSHOT` flows.

    **Why:** the expectations page lists sinks and `AUTO CDC FROM SNAPSHOT` under Limitations without giving a
    reason, so learn them as documented limits.

**Q4. Find the bug: `CONSTRAINT customer_exists EXPECT (customer_id IN (SELECT customer_id FROM silver_customers))`.**

??? success "Answer"
    A constraint cannot contain "Subqueries referencing other tables". Join first and expect on the result, for
    example a view `orders LEFT JOIN silver_customers` that exposes `c.customer_id AS matched_customer_id`, then
    `CONSTRAINT customer_exists EXPECT (matched_customer_id IS NOT NULL)`. The documented "missing record detection"
    pattern does this with a materialized view and `expect_or_fail`.

    **Why:** expectations are row-level checks on one dataset's output; cross-table logic belongs in the query.

**Q5. An expectation with `ON VIOLATION FAIL UPDATE` stopped the pipeline at 2 am. What do you do?**

??? success "Answer"
    1. Read the error: `EXPECTATION_VIOLATION` names the flow, the violated expectation and the input record.
    2. Know the blast radius: the flow's update was rolled back atomically. In a triggered pipeline, other parallel
       flows still ran; in a continuous pipeline the flow and its dependent flows stopped. Downstream tables did not
       get new data from that flow.
    3. Decide whether the data or the rule is wrong. Bad data: fix it at the source and resend, or change the action
       to drop or quarantine for that rule so good rows flow while the bad ones wait. Wrong rule: fix the rule.
    4. The docs: "you must fix the pipeline code to handle the invalid data correctly before re-running". Rerunning
       unchanged reads the same records and fails again.
    5. Afterwards, ask whether `FAIL UPDATE` was the right action; it fits rules where one bad row means the whole
       input is untrustworthy, not ordinary dirty rows.

    **Why:** fail stops at the first bad record and records no metrics, so the error message is your main evidence.

**Q6. In a triggered pipeline, silver_orders fails on an expectation. Will gold_daily_sales, which reads it, still
refresh? And a validation table that fails, does it block its readers?**

??? success "Answer"
    The failing flow's update is rolled back; "the failure of a single flow does not cause other parallel flows to
    fail". A dataset that depends on the failed one gets no new input from it. A separate validation table does not
    gate anything: "Reading a validation table from another dataset doesn't make that dataset wait for the validation
    result". To block gold, put validation and gold in separate pipelines and, in a job (Lakeflow Jobs, formerly
    Databricks Jobs, [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june)),
    make the gold pipeline's task depend on the validation pipeline's task.

    **Why:** "Expectations enforce data quality, not orchestration."

**Q7. Which event-log field holds the per-expectation counts, and which holds the dropped rows?**

??? success "Answer"
    In `flow_progress` events, `details:flow_progress.data_quality.expectations` is an array of
    `{name, dataset, passed_records, failed_records}`; `details:flow_progress.data_quality.dropped_records` is the
    number of rows dropped by one or more expectations. Query with `event_log(<pipelineId>)` or a published event log
    table, `explode(from_json(..., 'array<struct<...>>'))`, and group by dataset and name.

    **Why:** a row that fails two drop rules is counted once in `dropped_records` but once per rule in
    `failed_records` (the section 14.3 run: 4 rule failures, 3 rows dropped).

**Q8. Why do `fail` expectations never show up in the metrics?**

??? success "Answer"
    "Because `fail` causes the update to fail when an invalid record is detected, metrics are not recorded." The
    update stops at the first violation and is rolled back, so there is no completed count to record. The evidence is
    the error message with the record.

**Q9. Write the quarantine pattern in Python for two rules: `order_id IS NOT NULL` and
`amount IS NOT NULL AND amount >= 0`.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Expectation recommendations and advanced patterns](https://docs.databricks.com/aws/en/ldp/expectation-patterns).*

    ```python
    from pyspark import pipelines as dp
    from pyspark.sql.functions import expr

    rules = {"valid_order_id": "(order_id IS NOT NULL)",
             "valid_amount": "(amount IS NOT NULL AND amount >= 0)"}
    quarantine_rules = "NOT({0})".format(" AND ".join(rules.values()))

    @dp.table(private=True, partition_cols=["is_quarantined"])
    @dp.expect_all(rules)
    def orders_flagged():
        return spark.readStream.table("orders_typed").withColumn("is_quarantined", expr(quarantine_rules))

    @dp.temporary_view
    def valid_orders():
        return spark.read.table("orders_flagged").filter("is_quarantined = false")

    @dp.temporary_view
    def invalid_orders():
        return spark.read.table("orders_flagged").filter("is_quarantined = true")
    ```

    **Why:** `expect_all` (warn) records the metrics without dropping anything; the flag decides the side. The page's
    own example says `temporary=True`, the former name of `private=True`.

**Q10. With the rule `amount >= 0` in the quarantine pattern, bronze has 8 rows, valid has 6 and quarantine has 1.
Where is the eighth?**

??? success "Answer"
    Its `amount` is `NULL` (here the string `abc` cast with `try_cast`). `amount >= 0` is `NULL`, `NOT(NULL)` is
    `NULL`, so `is_quarantined` is `NULL` and the row matches neither `= false` nor `= true`. The section 14.5 run
    shows exactly this split (`NULL` 1, false 6, true 1). Fix: `amount IS NOT NULL AND amount >= 0`, or
    `coalesce(rule, false)`, and a count check bronze = valid + quarantine.

**Q11. Your pipeline fails with an error about expectations not being supported by the product edition. Why?**

??? success "Answer"
    Expectations need the `Advanced` edition ("includes data quality constraints with expectations"); `Core` and
    `Pro` do not include them. `Pro` adds CDC. Serverless pipelines always use `Advanced`. Change the edition in the
    pipeline settings.

**Q12. How do you share one set of rules across ten pipelines?**

??? success "Answer"
    Store them outside the pipeline code: a Delta table `(name, constraint, tag)` or a Python module, and a function
    `get_rules(tag)` that returns `{name: constraint}`, applied with `@dp.expect_all_or_drop(get_rules("orders"))`.
    This is Python only: "Dynamically loading expectations from a file is not supported in SQL."

    **Why:** the patterns page recommends storing definitions separately and tagging them, so rules can be updated and
    audited without editing each pipeline.

**Q13. A Delta table has `CHECK (amount >= 0)`. An `INSERT` of 1,000 rows contains one row with `amount = -5`. How many
rows are written?**

??? success "Answer"
    None. "When a constraint is violated, the transaction fails with an error." The section 14.7 run inserted 1005
    (valid) and 1007 (negative) together; neither is in the table, and the error was
    `[DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint amount_not_negative (amount >= 0) violated by row with values: - amount : -5.00`.

    **Why:** a constraint protects the table, not the flow. To keep the 999 good rows, filter or quarantine before
    the write.

**Q14. What does this return on Delta Lake: a table with `CHECK (currency IN ('CAD','USD'))` receives a row with
`currency = NULL`?**

??? success "Answer"
    An error (section 14.7 run):
    `[DELTA_VIOLATE_CONSTRAINT_WITH_VALUES] CHECK constraint known_currency (currency IN ('CAD', 'USD')) violated by row with values: - currency : null`. The Databricks wording is "must be true for
    each input row"; `NULL` is not true. In the SQL standard an unknown `CHECK` result passes, so this surprises
    people. Allow it explicitly with `CHECK (currency IS NULL OR currency IN ('CAD','USD'))` if `NULL` is acceptable.

**Q15. You run `ALTER TABLE silver.order_items ADD CONSTRAINT qty_positive CHECK (qty > 0)` and it fails. Why, and what
are your options?**

??? success "Answer"
    Existing rows are checked first; one row has `qty = 0`:
    `[DELTA_NEW_CHECK_CONSTRAINT_VIOLATION] 1 rows in spark_catalog.silver.order_items violate the new CHECK constraint (qty > 0)`.
    Fix or remove the violating rows (after deciding what `qty = 0` means), or choose a rule that matches the
    real data, then add the constraint.

**Q16. Does `CONSTRAINT pk PRIMARY KEY (order_id)` stop duplicate orders on Databricks?**

??? success "Answer"
    No. Primary key, foreign key and unique constraints "are informational only and aren't enforced". Only
    `NOT NULL` and `CHECK` are enforced. Duplicates are prevented by `MERGE` on the key, deduplication before the
    write, and detected by a uniqueness check (section 14.9) or a validation view with `EXPECT (num_entries = 1)`.

**Q17. When do you use expectations and when Delta constraints?**

??? success "Answer"
    Expectations inside Lakeflow pipelines (formerly Delta Live Tables, [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)), where you want per-row routing (keep, drop,
    fail) and metrics. Delta `CHECK`/`NOT NULL` constraints on any Delta table, as a guard that no writer (a notebook,
    another job, a manual `UPDATE`) can break; they only fail the whole transaction and give no metrics. Many teams
    use both on silver.

**Q18. Write a PySpark check that returns the keys that are not unique in `silver_orders`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    dup_keys = spark.table("silver_orders").groupBy("order_id").count().where("count > 1")
    ```

    In the section 14.9 run this found `[1002]`. In SQL:
    `SELECT order_id FROM silver_orders GROUP BY order_id HAVING count(*) > 1`.

**Q19. Write a referential-integrity check: orders whose customer does not exist.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    orphans = spark.table("silver_orders").join(spark.table("silver_customers"), "customer_id", "left_anti")
    ```

    The run found order 1006 (customer 12). SQL:
    `SELECT o.* FROM silver_orders o LEFT ANTI JOIN silver_customers c USING (customer_id)` or `WHERE NOT EXISTS (...)`. Do not use `NOT IN` with a subquery that can return `NULL`: one
    `NULL` makes `NOT IN` return no rows.

**Q20. Your freshness check passes in tests and fails every Monday in production. What is a likely cause, and how do
you write freshness checks?**

??? success "Answer"
    A fixed threshold (24 hours) on data that has a weekly pattern: no orders are loaded on Sunday, so Monday morning
    the latest `order_ts` is older than 24 hours. Make the threshold match the source's schedule (or compare with the
    expected arrival time), and pass the "now" as a parameter so tests use a fixed `AS_OF` and production uses the
    current time. Also check what clock and time zone `order_ts` uses.

**Q21. Reconciliation says bronze = 1,000 but silver + quarantine = 960. Silver is deduplicated. Is it a bug?**

??? success "Answer"
    Not necessarily. If 40 bronze rows were duplicates removed by deduplication, the right formula is bronze =
    silver + quarantine + duplicates removed. Count the duplicates in the same run (for example rows with
    `row_number() > 1`) and reconcile all four numbers. If the gap is not explained by duplicates, rows were lost,
    often by a nullable split rule (Q10) or an inner join.

**Q22. What does a CDC record contain, and how is it different from Delta's Change Data Feed?**

??? success "Answer"
    The operation (`INSERT`, `UPDATE`, `DELETE`), the row's values, and a sequence number or timestamp for ordering.
    Delta's Change Data Feed is one such feed, produced by a Delta table itself (`_change_type`, `_commit_version`,
    `_commit_timestamp`; chapter 9, section 9.11). `AUTO CDC` (formerly `APPLY CHANGES`, [AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)) consumes feeds from source databases (for example via
    Debezium or Oracle GoldenGate) or from Delta tables with Change Data Feed enabled.

**Q23. Updates arrive out of order. How does AUTO CDC (APPLY CHANGES) handle them, for SCD Type 1 and for Type 2?**

??? success "Answer"
    `AUTO CDC` (formerly `APPLY CHANGES`, [AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)) orders
    events by `SEQUENCE BY`, not by arrival. SCD Type 1: "Late changes older than the current version are dropped."
    SCD Type 2: late changes are "Inserted into history in sequence order", so a version can appear between two
    existing ones and the neighbor's `__END_AT` changes (section 14.13: Banff 110 to 118, Cochrane 118 to 130).

    **Why:** the sequence column is the only reliable statement of event order; arrival order depends on networks,
    retries and file processing order.

**Q24. The source sends deletes. What do you configure, and what happens to a late update for a deleted key?**

??? success "Answer"
    `APPLY AS DELETE WHEN op = 'd'` (Python `apply_as_deletes=expr("op = 'd'")`). SCD Type 1 removes the row; SCD
    Type 2 closes the current version at the delete's sequence value. A delete is kept as a tombstone, by default for
    two days (`pipelines.cdc.tombstoneGCThresholdInSeconds`), so a late, older update is recognized as stale and does
    not bring the row back. Set the threshold above the longest delay you expect. `APPLY AS TRUNCATE WHEN` exists for
    whole-table truncates, SCD Type 1 only.

**Q25. What does this produce? Feed for customer 9: `c` at 102 (chloe.m), `d` at 125, then a late `u` at 115
(chloe.martin). SCD Type 1 and SCD Type 2 targets.**

??? success "Answer"
    SCD Type 1: no row for customer 9; the delete at 125 is newer than the update at 115, and the tombstone blocks the
    update. SCD Type 2: two closed versions, `chloe.m` 102 to 115 and `chloe.martin` 115 to 125, and no open version.
    This is the section 14.13 result for Chloe. A naive `MERGE` without a guard or tombstone resurrected her.

**Q26. Write the AUTO CDC SQL for an SCD Type 2 customer history from `shop.bronze.customers_cdc`, excluding `op`,
`lsn` and `batch_id`, where an email change should not create a new version.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [AUTO CDC INTO (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-apply-changes-into).*

    ```sql
    CREATE OR REFRESH STREAMING TABLE customers_history;

    CREATE FLOW customers_history_cdc AS AUTO CDC INTO customers_history
    FROM STREAM(shop.bronze.customers_cdc)
    KEYS (customer_id)
    APPLY AS DELETE WHEN op = 'd'
    SEQUENCE BY lsn
    COLUMNS * EXCEPT (op, lsn, batch_id)
    STORED AS SCD TYPE 2
    TRACK HISTORY ON * EXCEPT (email);
    ```

    **Why:** `TRACK HISTORY ON * EXCEPT (email)` makes email changes update the current version in place. Before the
    rename this was `APPLY CHANGES INTO` with the same clauses ([AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)).

**Q27. Write the same flow in Python.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [create_auto_cdc_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes).*

    ```python
    from pyspark import pipelines as dp
    from pyspark.sql.functions import col, expr

    @dp.temporary_view
    def customers_changes():
        return spark.readStream.table("shop.bronze.customers_cdc")

    dp.create_streaming_table("customers_history")
    dp.create_auto_cdc_flow(
        target="customers_history",
        source="customers_changes",
        keys=["customer_id"],
        sequence_by=col("lsn"),
        apply_as_deletes=expr("op = 'd'"),
        except_column_list=["op", "lsn", "batch_id"],
        stored_as_scd_type=2,
        track_history_except_column_list=["email"],
    )
    ```

    Old code: `import dlt` and `dlt.apply_changes(...)` with the same arguments (APPLY CHANGES became AUTO CDC,
    [AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc); Delta Live Tables became Lakeflow pipelines, [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)).

**Q28. Find the bug: the SCD Type 2 target was declared with a schema, `__START_AT TIMESTAMP, __END_AT TIMESTAMP`, and
the flow uses `SEQUENCE BY lsn` where `lsn` is `BIGINT`.**

??? success "Answer"
    The types must match: "For SCD type 2 tables, when specifying the schema of the target table, you must also
    include the `__START_AT` and `__END_AT` columns with the same data type as the `sequence_by` field." Declare them
    `BIGINT`, or sequence by a timestamp column if you want time ranges.

**Q29. A full snapshot of the product catalog arrives every night, with no change flags. Which API, and what are its
limits?**

??? success "Answer"
    `AUTO CDC FROM SNAPSHOT` (`dp.create_auto_cdc_from_snapshot_flow`, formerly `apply_changes_from_snapshot` in Delta Live Tables, now Lakeflow pipelines, [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt); in
    SQL `CREATE FLOW ... AS AUTO CDC INTO ... FROM SNAPSHOT (...) [WITH VERSION (...)] KEYS (...)`). It diffs
    consecutive snapshots, treats keys missing from the new snapshot as deleted, and writes SCD Type 1 or 2. Limits:
    changes between two snapshots are invisible (A to B to C shows as A to C); versions must increase; expectations
    are not supported on the flow; it does not record `num_upserted_rows`/`num_deleted_rows`.

**Q30. Snapshot 3 arrives after snapshot 4 was processed. What happens?**

??? success "Answer"
    Versions must increase: "Every version returned after a successful commit must be greater than the previously
    committed version"; a non-increasing version fails the update
    (`APPLY_CHANGES_FROM_SNAPSHOT_ERROR.OUT_OF_ORDER_SNAPSHOT_VERSION`). The documented version-function and
    `WITH VERSION` examples avoid this by only selecting versions greater than `last_snapshot_version()`, so the late
    snapshot 3 is skipped. If snapshot 3 matters, you need a full refresh, which "clears the persisted version
    state".

**Q31. Two change events for the same customer carry the same `lsn`. What happens and how do you prevent it?**

??? success "Answer"
    The sequence column must have "one distinct update per key at each sequencing value"; with a tie the order is not
    defined by your data, so the result can differ between runs. Use a column that is unique per key (a log position)
    or a tie-breaker: `SEQUENCE BY STRUCT(commit_ts, op_seq)` in SQL, `sequence_by=struct("commit_ts", "op_seq")` in
    Python; the struct "orders by the first struct field first, then by the second field if there's a tie".

**Q32. Can the sequence column contain NULLs?**

??? success "Answer"
    No. "`NULL` sequencing values are not supported." Filter or fix them before the flow (an expectation with
    `ON VIOLATION DROP ROW` or a quarantine on the source view works), and alert on them: a `NULL` sequence usually
    means a broken extract.

**Q33. Find the bug in this hand-written SCD Type 1 CDC merge.**

```sql
MERGE INTO customers t
USING (SELECT * FROM batch QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY lsn DESC) = 1) s
ON t.customer_id = s.customer_id
WHEN MATCHED AND s.op = 'd' THEN DELETE
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED AND s.op <> 'd' THEN INSERT *
```

??? success "Answer"
    Two bugs, both shown in the section 14.13 run of the naive version. (1) No sequence guard: a late, older event
    overwrites a newer one (Ava back in Cochrane). Add `AND s.lsn > t.lsn` to both `WHEN MATCHED` branches. (2) The
    delete removes the row, so a late update for that key no longer matches and is inserted (Chloe resurrected). Keep
    a tombstone instead (`__deleted = true` with the delete's `lsn`) and filter it in a view. Also, `UPDATE SET *`
    copies `op` and `lsn` columns only if the target has them; list the columns.

**Q34. The source sends only the columns that changed; the rest are NULL. What goes wrong with the default settings,
and what are the options?**

??? success "Answer"
    By default `NULL` columns in an update overwrite the target: `ignore_null_updates` "Defaults to `False`". With
    `ignore_null_updates=True` (SQL `IGNORE NULL UPDATES`) nulls keep the old value, but then an intentional `NULL`
    cannot be applied. For that, use `IGNORE NULL UPDATES ON` a column list (or `ON * EXCEPT (...)`) for a fixed set
    of columns, or `COLUMNS TO UPDATE` with a source `array<string>` column naming the columns each record really
    sets. `COLUMNS TO UPDATE` cannot be combined with `IGNORE NULL UPDATES`.

**Q35. How do you stream changes from an AUTO CDC target into gold?**

??? success "Answer"
    (AUTO CDC, formerly APPLY CHANGES: [AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)) Read the target's change data feed: "To stream data from the target of an AUTO CDC process, read from its change
    feed." The target is updated and deleted in place, so a plain streaming read is not append-only. The CDF of an
    `AUTO CDC` target requires Unity Catalog and Databricks Runtime 15.2 or above. Alternatively, build gold as a
    materialized view over the target, which has no append-only requirement.

**Q36. You must load ten years of an existing database table and then keep it in sync from its CDC feed. How?**

??? success "Answer"
    (AUTO CDC, formerly APPLY CHANGES: [AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)) Load the history once, then process the feed. The CDC page: "For initial hydration from a source with a change
    feed, use `AUTO CDC` with a `once` flow and then continue processing the change feed" (`AUTO CDC ONCE INTO` in
    SQL, `once=True` in Python, which takes a batch source). A `ONCE` flow is not re-run on later updates, "except in
    the case of a full refresh". For SCD Type 1 targets you can alternatively combine a one-time
    `AUTO CDC FROM SNAPSHOT` flow with the `AUTO CDC` feed flow in the same target (triggered mode, the same keys in
    the same order, and the same data type for the snapshot version and the sequencing column).

**Q37. Compare chapter 9's SCD Type 2 MERGE with AUTO CDC SCD Type 2 when a late change arrives.**

??? success "Answer"
    (AUTO CDC, formerly APPLY CHANGES: [AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)) Chapter 9 guards with `s.updated_at > t.valid_from` against the current row, so a change older than the current
    version is ignored: history stays as it was, and the late change is lost. `AUTO CDC` inserts it into history in
    sequence order and adjusts the neighbors' ranges. The emulation in section 14.13 does the same by rebuilding the
    touched keys' versions from the change log. Which is right depends on the requirement; for audit-quality history,
    the late change must be kept.

**Q38. Does AUTO CDC work in open-source Apache Spark? What did you see when you tried?**

??? success "Answer"
    (AUTO CDC, formerly APPLY CHANGES: [AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)) Databricks: "The `AUTO CDC` APIs are not supported by Apache Spark Declarative Pipelines." The open-source module
    in Spark 4.2 exports `create_auto_cdc_flow`, but only `stored_as_scd_type=1` passes its type check (2 raises
    `PySparkTypeError`), there is no snapshot flow and no expectation decorators. A real `spark-pipelines run` with a
    Delta target failed with `[AUTOCDC_TARGET_DOES_NOT_SUPPORT_MERGE]`: the open-source flow needs a connector that
    implements DSv2 `SupportsRowLevelOperations`, and Delta 4.4.1 implements `MERGE` another way. The Spark 4.2.0
    release notes announce open-source Auto CDC for SCD Type 1, and the Spark 4.3 guide documents it for such
    connectors.

**Q39. Why does AUTO CDC need the target to be a streaming table, and what happens if you point it at a table created
with `CREATE TABLE ... FLOW`?**

??? success "Answer"
    (AUTO CDC, formerly APPLY CHANGES: [AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)) `AUTO CDC` flows apply changes into a streaming table you declare first ("You must declare a target streaming
    table to apply the changes into"). A managed table created with `CREATE TABLE ... FLOW` "doesn't support change
    data capture: an `AUTO CDC ... INTO` flow against a managed table fails with
    `MANAGED_TABLE_DOES_NOT_SUPPORT_CDC`" ([CREATE FLOW](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-flow)).

**Q40. An interviewer asks: "Why not just MERGE the CDC feed yourself?" Give a balanced answer.**

??? success "Answer"
    A hand-written `MERGE` works and runs anywhere Delta runs, and chapter 9 and section 14.13 show how. But it must
    handle in-batch deduplication, a sequence guard, delete tombstones and their cleanup, late versions in SCD Type
    2, partial updates, replays and schema changes; each is a place for a bug, and the Databricks page calls the
    custom approach "complex and error-prone". `AUTO CDC` (formerly `APPLY CHANGES`, [AUTO CDC APIs page](https://docs.databricks.com/aws/en/ldp/cdc)) does all of that from one
    declaration, with metrics, but needs a Lakeflow pipeline (formerly Delta Live Tables, [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) on the Pro or Advanced edition or serverless. I would
    use `AUTO CDC` on Databricks and keep the `MERGE` approach for platforms without it.

## Sources

- [What is the medallion lakehouse architecture?](https://docs.databricks.com/aws/en/lakehouse/medallion) (last updated Oct 29, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations) (last updated Oct 26, 2026)
- [Expectation recommendations and advanced patterns](https://docs.databricks.com/aws/en/ldp/expectation-patterns) (last updated Oct 26, 2026)
- [Expectations (Python reference)](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-expectations) (last updated Sep 11, 2026)
- [Lakeflow pipelines Python language reference](https://docs.databricks.com/aws/en/ldp/developer/python-ref) (last updated Oct 25, 2026)
- [table](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-table) (last updated Oct 15, 2026)
- [temporary_view](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-view) (last updated Sep 11, 2026)
- [create_streaming_table](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-streaming-table) (last updated Oct 9, 2026)
- [CREATE STREAMING TABLE (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-streaming-table) (last updated Oct 2, 2026)
- [Configure pipelines](https://docs.databricks.com/aws/en/ldp/configure-pipeline) (last updated Oct 12, 2026)
- [Pipeline event log](https://docs.databricks.com/aws/en/ldp/monitor-event-logs) (last updated Nov 3, 2026)
- [Pipeline event log schema](https://docs.databricks.com/aws/en/ldp/monitor-event-log-schema) (last updated Nov 10, 2026)
- [Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints) (last updated Nov 6, 2026)
- [Change data capture and snapshots](https://docs.databricks.com/aws/en/data-engineering/what-is-cdc) (last updated Nov 9, 2026)
- [The AUTO CDC APIs: Simplify change data capture with pipelines](https://docs.databricks.com/aws/en/ldp/cdc) (last updated Nov 9, 2026)
- [AUTO CDC INTO (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-apply-changes-into) (last updated Nov 9, 2026)
- [create_auto_cdc_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes) (last updated Nov 9, 2026)
- [create_auto_cdc_from_snapshot_flow](https://docs.databricks.com/aws/en/ldp/developer/ldp-python-ref-apply-changes-from-snapshot) (last updated Oct 5, 2026)
- [CREATE FLOW (pipelines)](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-flow) (last updated Oct 15, 2026)
- [Advanced AUTO CDC topics](https://docs.databricks.com/aws/en/ldp/cdc-advanced) (last updated Nov 9, 2026)
- [Replicate an external RDBMS table using AUTO CDC](https://docs.databricks.com/aws/en/ldp/database-replication) (last updated Oct 9, 2026)
- [Spark 4.2.0 release notes](https://spark.apache.org/releases/spark-release-4-2-0.html) (the page shows no update date; read Nov 11, 2026)
- [Spark Declarative Pipelines Programming Guide](https://spark.apache.org/docs/latest/declarative-pipelines-programming-guide.html) (Apache Spark 4.3.0 documentation; the page shows no update date)
- [Debezium connector for PostgreSQL](https://debezium.io/documentation/reference/stable/connectors/postgresql.html) (no update date shown; read Nov 11, 2026 from its source file in the Debezium GitHub repository)
- [Databricks platform release notes, June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026)
