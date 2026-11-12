# 19. The function toolbox

*Most of a data engineer's SQL is not clever joins. It is turning a raw string into a timestamp, bucketing events by week, cleaning an email column, counting only the shipped orders, picking the latest row per key and computing a running total. Databricks SQL ships several hundred built-in functions for this work, and many of them have twins with different argument orders, different return types or different behavior when something goes wrong. This chapter walks through the functions you will use every week on Red Rock Supply data, shows the traps that break pipelines (argument order in `datediff`, `mm` versus `MM`, the default window frame with `last_value`, `concat` with `NULL`), and gives you the PySpark `F.*` version next to the SQL. Interviewers use exactly these functions for live coding: top-N per group, running totals, gaps and islands, sessionization.*

!!! abstract "In this chapter"
    **You will learn:**

    - how to find a function and read its "Applies to" label
    - dates and times: truncating, adding, differences (and their argument orders), building, extracting
    - parsing and formatting with datetime patterns, unix time, session time zones, `TIMESTAMP` versus `TIMESTAMP_NTZ`
    - strings and regular expressions for cleaning bronze data
    - rounding, `DECIMAL` precision, integer division and the `try_` family under ANSI mode
    - conditional and `NULL`-handling functions
    - aggregates: the `count` family, `FILTER (WHERE ...)`, `max_by`/`min_by`, `collect_list`, `listagg`, approximate and exact percentiles
    - `GROUPING SETS`, `ROLLUP`, `CUBE` with `grouping()` and `grouping_id()`
    - window functions in depth: ranking, `lag`/`lead`, frames, `ROWS` versus `RANGE`, the default-frame trap, the `WINDOW` clause
    - the classic window patterns: deduplication, change detection, gaps and islands, sessionization
    - hashing and ids, and why `monotonically_increasing_id` is not a sequence
    - a short look at AI functions (Databricks only)

    **You need:** [chapter 17](17-Databricks-SQL-vs-Standard.md) (ANSI mode, `QUALIFY`, `GROUP BY ALL`, `IS DISTINCT FROM`), and window function basics from the SQL course ([Window functions and ranking](../../databases/sql/13-Window-Functions-Ranking.md)). Arrays, maps, JSON, `VARIANT` and higher-order functions such as `transform` are in [chapter 18](18-Semi-Structured-Data.md); this chapter does not repeat them.

    **Levels:** sections 19.1, 19.2, 19.4 and 19.6 beginner; 19.3, 19.5, 19.7, 19.8, 19.11 and 19.12 intermediate; 19.9 and 19.10 expert.

**About the examples.** All "Run here" examples use the Red Rock Supply tables in schemas `silver` and `bronze` of Spark's built-in catalog (on Databricks: `shop.silver.orders` in Unity Catalog). The `orders` table holds the eight orders from chapter 17 (1001 to 1008, order 1008 with a `NULL` status) plus eight more (1009 to 1016), so that window functions have repeat customers, ties and gaps to work on. `bronze.orders_raw` and `bronze.customers_raw` hold raw strings as they arrive in the JSON files. The session time zone is `UTC`, which is also the system default on Databricks. Scripts and full outputs are in `src/ch19/` (`ex01_dates.py` to `ex11_practice.py`, each with a `.out` file). Long result tables are trimmed to the rows that matter, and error lines are shortened to the error class and its first sentence.

## 19.1 Finding a function and reading its label
*Level: beginner.*

**The problem.** You remember that "there is a function that returns the value from the row with the latest timestamp", but not its name, or whether it exists on the runtime your job uses.

The SQL reference has an [alphabetical list of built-in functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-functions-builtin-alpha) and a [page grouped by category](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-functions-builtin) (string, numeric, date and time, aggregate, window and so on). From SQL itself, `SHOW FUNCTIONS` "returns the list of functions after applying an optional regex pattern", and `DESCRIBE FUNCTION` returns the function name, implementing class and usage.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SHOW FUNCTIONS LIKE 'try_to*';
DESCRIBE FUNCTION date_trunc;
```

Output (from `ex01_dates.out`, trimmed):
```text
+----------------+
|function        |
+----------------+
|try_to_binary   |
|try_to_date     |
|try_to_number   |
|try_to_time     |
|try_to_timestamp|
+----------------+
+------------------------------------------------------------------------------------------------------------------------+
|function_desc                                                                                                           |
+------------------------------------------------------------------------------------------------------------------------+
|Function: date_trunc                                                                                                    |
|Class: org.apache.spark.sql.catalyst.expressions.TruncTimestamp                                                         |
|Usage: \n    date_trunc(fmt, ts) - Returns timestamp `ts` truncated to the unit specified by the format model `fmt`.\n  |
+------------------------------------------------------------------------------------------------------------------------+
```

Every function page starts with an **"Applies to"** label (chapter 17, section 17.1 explains how to read it). Most functions in this chapter say "Databricks SQL Databricks Runtime", which means all versions of both. When a page names a version, this chapter quotes it, because it decides whether the function exists on the cluster your job runs on. For example, `listagg` says "Databricks SQL Databricks Runtime 16.4 and later", so a job pinned to Databricks Runtime 15.4 LTS cannot use it.

!!! tip "In the interview"
    **"How do you check whether a function is available on your runtime?"** Look at the "Applies to" label on its SQL reference page: it lists Databricks SQL (warehouses) and the minimum Databricks Runtime version. On a running cluster, `SHOW FUNCTIONS LIKE 'name*'` and `DESCRIBE FUNCTION name` answer it directly.

## 19.2 Dates and times: truncate, add, subtract, extract
*Level: beginner.*

### Current values

`current_date()` returns a `DATE` and `current_timestamp()` a `TIMESTAMP`, both evaluated "at the start of query evaluation", so every row of one query sees the same value. The parentheses are optional (`current_date` works too), and `now()` is a synonym of `current_timestamp()`. The `current_timestamp` page adds an optional `precision` argument that is "available only in Databricks Runtime 19 and above".

!!! warning "Same query, same value; different query, different value"
    Because the value is fixed at the start of the query, `current_timestamp()` is safe inside one statement. But a pipeline that computes "yesterday" in one query and filters in another can straddle midnight. Compute the date once (a job parameter, or a session variable from [chapter 17](17-Databricks-SQL-vs-Standard.md)) and reuse it, which also makes reruns reproducible.

### date_trunc and trunc: two functions, two return types

Reports group by day, week or month. You get there by **truncating**: replacing a timestamp with the start of the bucket that contains it.

| | `date_trunc(unit, expr)` | `trunc(expr, unit)` |
| --- | --- | --- |
| Argument order | unit first | unit second |
| Returns | `TIMESTAMP` | `DATE` |
| Units | `YEAR`, `QUARTER`, `MONTH`, `WEEK`, `DAY`, `HOUR`, `MINUTE`, `SECOND`, `MILLISECOND`, `MICROSECOND` (plus short forms such as `'MM'`, `'DD'`) | `YEAR`, `QUARTER`, `MONTH`, `WEEK` (plus short forms) |
| Unknown unit | `NULL` | `NULL` |
| Applies to | Databricks SQL, Databricks Runtime | Databricks SQL, Databricks Runtime |

Both pages say `WEEK` truncates "to the Monday of the week".

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 330" role="img" aria-label="Nested buckets for YEAR, QUARTER, MONTH, WEEK, DAY and HOUR around the timestamp 2026-03-04 19:10. date_trunc returns the left edge of each bucket.">
<text x="320" y="22" text-anchor="middle" font-size="14" fill="currentColor">order 1008: TIMESTAMP '2026-03-04 19:10:00' (a Wednesday)</text>
<line x1="330" y1="32" x2="330" y2="262" stroke="currentColor" stroke-dasharray="4 3"/>
<text x="16" y="62" font-size="13" fill="currentColor">YEAR</text>
<rect x="100" y="44" width="300" height="26" fill="none" stroke="currentColor"/>
<circle cx="100" cy="57" r="4" fill="currentColor"/>
<text x="420" y="62" font-size="13" fill="currentColor">2026-01-01 00:00:00</text>
<text x="16" y="98" font-size="13" fill="currentColor">QUARTER</text>
<rect x="110" y="80" width="270" height="26" fill="none" stroke="currentColor"/>
<circle cx="110" cy="93" r="4" fill="currentColor"/>
<text x="420" y="98" font-size="13" fill="currentColor">2026-01-01 00:00:00</text>
<text x="16" y="134" font-size="13" fill="currentColor">MONTH</text>
<rect x="230" y="116" width="140" height="26" fill="none" stroke="currentColor"/>
<circle cx="230" cy="129" r="4" fill="currentColor"/>
<text x="420" y="134" font-size="13" fill="currentColor">2026-03-01 00:00:00</text>
<text x="16" y="170" font-size="13" fill="currentColor">WEEK</text>
<rect x="290" y="152" width="70" height="26" fill="none" stroke="currentColor"/>
<circle cx="290" cy="165" r="4" fill="currentColor"/>
<text x="420" y="170" font-size="13" fill="currentColor">2026-03-02 00:00:00 (Monday)</text>
<text x="16" y="206" font-size="13" fill="currentColor">DAY</text>
<rect x="318" y="188" width="24" height="26" fill="none" stroke="currentColor"/>
<circle cx="318" cy="201" r="4" fill="currentColor"/>
<text x="420" y="206" font-size="13" fill="currentColor">2026-03-04 00:00:00</text>
<text x="16" y="242" font-size="13" fill="currentColor">HOUR</text>
<rect x="326" y="224" width="8" height="26" fill="none" stroke="currentColor"/>
<circle cx="326" cy="237" r="3" fill="currentColor"/>
<text x="420" y="242" font-size="13" fill="currentColor">2026-03-04 19:00:00</text>
<text x="16" y="290" font-size="13" fill="currentColor">date_trunc(unit, ts) returns the left edge (dot) of the bucket that holds ts, as a TIMESTAMP.</text>
<text x="16" y="312" font-size="13" fill="currentColor">trunc(date, unit) returns a DATE and knows only YEAR, QUARTER, MONTH and WEEK.</text>
</svg>
<figcaption>Figure 19.1. Truncation returns the start of the bucket that contains the timestamp. The dashed line is order 1008.</figcaption>
</figure>

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, order_ts,
       date_trunc('MONTH', order_ts) AS dt_month,
       date_trunc('WEEK',  order_ts) AS dt_week,
       date_trunc('HOUR',  order_ts) AS dt_hour,
       trunc(order_ts, 'MM')         AS tr_month,
       typeof(date_trunc('MONTH', order_ts)) AS t1,
       typeof(trunc(order_ts, 'MM'))         AS t2
FROM silver.orders WHERE order_id IN (1001, 1008, 1014) ORDER BY order_id;

SELECT date_trunc('MS', TIMESTAMP'2026-03-04 19:10:00') AS bad_unit,
       trunc(DATE'2026-03-04', 'DAY') AS trunc_day;

SELECT date_trunc(order_ts, 'MONTH') FROM silver.orders;   -- arguments swapped
```

Output (from `ex01_dates.out`):
```text
+--------+-------------------+-------------------+-------------------+-------------------+----------+---------+----+
|order_id|order_ts           |dt_month           |dt_week            |dt_hour            |tr_month  |t1       |t2  |
+--------+-------------------+-------------------+-------------------+-------------------+----------+---------+----+
|1001    |2026-03-01 10:15:00|2026-03-01 00:00:00|2026-02-23 00:00:00|2026-03-01 10:00:00|2026-03-01|timestamp|date|
|1008    |2026-03-04 19:10:00|2026-03-01 00:00:00|2026-03-02 00:00:00|2026-03-04 19:00:00|2026-03-01|timestamp|date|
|1014    |2026-04-01 03:20:00|2026-04-01 00:00:00|2026-03-30 00:00:00|2026-04-01 03:00:00|2026-04-01|timestamp|date|
+--------+-------------------+-------------------+-------------------+-------------------+----------+---------+----+

+--------+---------+
|bad_unit|trunc_day|
+--------+---------+
|NULL    |NULL     |
+--------+---------+

ERROR: [CAST_INVALID_INPUT] The value 'MONTH' of the type "STRING" cannot be cast to "TIMESTAMP" because it is malformed.
```

Three lessons. Order 1001 (Sunday, March 1) falls in the week that started Monday, February 23, so a weekly report puts it in February's last week. A misspelled unit returns `NULL` silently, even with ANSI mode on, and `trunc(..., 'DAY')` is also `NULL` because `trunc` has no `DAY` unit (use `CAST(ts AS DATE)` or `date_trunc('DAY', ts)`). And swapping the arguments of `date_trunc` fails, because Spark tries to read `'MONTH'` as a timestamp.

A weekly revenue report, in SQL and PySpark:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT date_trunc('WEEK', order_ts) AS week_start, count(*) AS orders, sum(amount) AS revenue
FROM silver.orders GROUP BY ALL ORDER BY week_start;
```
```python
from pyspark.sql import functions as F

(spark.table("silver.orders")
 .groupBy(F.date_trunc("week", "order_ts").alias("week_start"))
 .agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue"))
 .orderBy("week_start"))
```

Output (both give the same rows, from `ex01_dates.out`):
```text
+-------------------+------+-------+
|week_start         |orders|revenue|
+-------------------+------+-------+
|2026-02-23 00:00:00|2     |308.90 |
|2026-03-02 00:00:00|10    |1320.90|
|2026-03-09 00:00:00|1     |59.90  |
|2026-03-30 00:00:00|2     |477.00 |
|2026-04-06 00:00:00|1     |189.50 |
+-------------------+------+-------+
```

Note that PySpark's `F.date_trunc(format, timestamp)` keeps SQL's unit-first order, while `F.trunc(date, format)` keeps `trunc`'s date-first order.

### Adding time

There are two families, and the names overlap:

| Function | Arguments | Returns | Applies to |
| --- | --- | --- | --- |
| `date_add(startDate, numDays)`, `date_sub(startDate, numDays)` | date, days | `DATE` | Databricks SQL, Databricks Runtime |
| `dateadd(startDate, numDays)` | date, days | `DATE` | Databricks SQL, Databricks Runtime |
| `add_months(startDate, numMonths)` | date, months | `DATE` | Databricks SQL, Databricks Runtime |
| `timestampadd(unit, value, expr)` | unit, amount, timestamp | `TIMESTAMP` | Databricks SQL, Databricks Runtime 10.4 LTS and above |
| `dateadd(unit, value, expr)` | same, synonym of `timestampadd` | `TIMESTAMP` | Databricks SQL, Databricks Runtime 10.4 LTS and above |
| `date_add(unit, value, expr)` | same, synonym of `timestampadd` | `TIMESTAMP` | Databricks SQL, Databricks Runtime 13.3 LTS and above |

So `date_add` with two arguments adds days and returns a `DATE`, while `date_add` with three arguments takes a unit and returns a `TIMESTAMP`. For `MONTH`, `QUARTER` and `YEAR`, "the day portion of the result will be adjusted to result in a valid date", and `add_months` rounds down to the end of the month the same way.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT date_add(DATE'2026-03-31', 1)        AS date_add_days,
       date_sub(DATE'2026-03-31', 31)       AS date_sub_days,
       add_months(DATE'2026-03-31', -1)     AS add_months_m1,
       DATE'2026-03-31' + INTERVAL 1 MONTH  AS plus_interval;

SELECT timestampadd(HOUR, 36, TIMESTAMP'2026-03-01 10:15:00') AS tsadd_hours,
       dateadd(MONTH, -1, TIMESTAMP'2026-03-31 08:00:00')     AS dateadd_unit,
       date_add(MINUTE, 30, TIMESTAMP'2026-03-04 19:10:00')   AS date_add_unit,
       typeof(dateadd(DAY, 1, DATE'2026-03-31'))              AS t_unit_form,
       typeof(date_add(DATE'2026-03-31', 1))                  AS t_days_form;
```

Output (from `ex01_dates.out`, trimmed; the script also has a `dateadd(DATE'2026-03-31', 1)` column, 2026-04-01):
```text
+-------------+-------------+-------------+-------------+
|date_add_days|date_sub_days|add_months_m1|plus_interval|
+-------------+-------------+-------------+-------------+
|2026-04-01   |2026-02-28   |2026-02-28   |2026-04-30   |
+-------------+-------------+-------------+-------------+

+-------------------+-------------------+-------------------+-----------+-----------+
|tsadd_hours        |dateadd_unit       |date_add_unit      |t_unit_form|t_days_form|
+-------------------+-------------------+-------------------+-----------+-----------+
|2026-03-02 22:15:00|2026-02-28 08:00:00|2026-03-04 19:40:00|timestamp  |date       |
+-------------------+-------------------+-------------------+-----------+-----------+
```

In PySpark: `F.date_add(col, 1)`, `F.add_months(col, -1)` and `F.timestamp_add("HOUR", F.lit(36), col)` gave the same values (`ex01_dates.out`).

### Differences between two dates: watch the argument order

This is the most common date bug in interviews and in production.

| Call | Order | Returns | Applies to (as the page states it) |
| --- | --- | --- | --- |
| `datediff(endDate, startDate)` | **end first** | `INTEGER` days | "Databricks SQL preview Databricks Runtime 11.3 LTS and above" |
| `date_diff(endDate, startDate)` | **end first** | `INTEGER` days | Databricks SQL, Databricks Runtime 13.3 LTS and above |
| `timestampdiff(unit, start, end)` | unit, **start first** | `BIGINT` | Databricks SQL, Databricks Runtime 10.4 LTS and above |
| `datediff(unit, start, end)` | unit, **start first** | `BIGINT` (synonym of `timestampdiff`) | Databricks SQL, Databricks Runtime 10.4 LTS and above |
| `date_diff(unit, start, end)` | unit, **start first** | `BIGINT` (synonym of `timestampdiff`) | Databricks SQL, Databricks Runtime 13.3 LTS and above |
| `months_between(expr1, expr2 [, roundOff])` | later first for a positive result | `DOUBLE` | Databricks SQL, Databricks Runtime |

The two-argument forms put the **end** first (like subtraction: end minus start). The three-argument forms put the **start** first. Get it wrong and the sign flips.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT datediff(DATE'2026-03-31', DATE'2026-03-01')            AS datediff_end_start,
       datediff(DATE'2026-03-01', DATE'2026-03-31')            AS datediff_swapped,
       date_diff(DATE'2026-03-31', DATE'2026-03-01')           AS date_diff_2arg,
       datediff(DAY, DATE'2026-03-01', DATE'2026-03-31')       AS datediff_unit_start_end,
       timestampdiff(DAY, DATE'2026-03-01', DATE'2026-03-31')  AS timestampdiff_day;
```

Output (from `ex01_dates.out`; the `date_diff(DAY, ...)` column, also 30, is left out):
```text
+------------------+----------------+--------------+-----------------------+-----------------+
|datediff_end_start|datediff_swapped|date_diff_2arg|datediff_unit_start_end|timestampdiff_day|
+------------------+----------------+--------------+-----------------------+-----------------+
|30                |-30             |30            |30                     |30               |
+------------------+----------------+--------------+-----------------------+-----------------+
```

The second trap is **what** is counted. `timestampdiff` "counts whole elapsed units based on UTC with a DAY being 86400 seconds", and "one month is considered elapsed when the calendar month has increased and the calendar day and time is equal or greater to the start". `datediff` counts calendar days between the dates. `months_between` is different again: when both dates are on the same day of the month, or both are the last day of a month, "time of day is ignored"; otherwise it uses "31 days per month" and rounds to 8 digits.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT timestampdiff(HOUR, TIMESTAMP'2026-03-04 19:10:00', TIMESTAMP'2026-03-05 19:09:59') AS hours,
       timestampdiff(DAY,  TIMESTAMP'2026-03-04 19:10:00', TIMESTAMP'2026-03-05 19:09:59') AS days,
       datediff(DATE(TIMESTAMP'2026-03-05 19:09:59'), DATE(TIMESTAMP'2026-03-04 19:10:00')) AS calendar_days,
       timestampdiff(MONTH, TIMESTAMP'2026-01-31 00:00:00', TIMESTAMP'2026-02-28 00:00:00') AS months_jan31_feb28,
       months_between(DATE'2026-02-28', DATE'2026-01-31') AS months_between_eom,
       months_between(DATE'2026-03-15', DATE'2026-01-31') AS months_between_mid;
```

Output (from `ex01_dates.out`, trimmed):
```text
+-----+----+-------------+------------------+------------------+------------------+
|hours|days|calendar_days|months_jan31_feb28|months_between_eom|months_between_mid|
+-----+----+-------------+------------------+------------------+------------------+
|23   |0   |1            |0                 |1.0               |1.48387097        |
+-----+----+-------------+------------------+------------------+------------------+
```

One second short of 24 hours is 0 elapsed days but 1 calendar day. January 31 to February 28 is 0 elapsed months for `timestampdiff` (the day, 28, is smaller than 31) but exactly 1.0 for `months_between`, because both are the last day of their month. Pick the function that matches the business rule ("customer tenure in whole months" versus "billing months"), and write the rule down.

In PySpark: `F.datediff(end, start)` (end first, like SQL), `F.timestamp_diff("DAY", start, end)` and `F.months_between(d1, d2)`.

!!! tip "In the interview"
    **"How many days between two timestamps?"** Ask which kind of day. `datediff(end, start)` counts calendar-date boundaries (end first). `timestampdiff(DAY, start, end)` counts whole 24-hour periods (start first). From 19:10 one day to 19:09 the next, the first gives 1 and the second 0. For hours or minutes, use `timestampdiff(HOUR, start, end)` or subtract `unix_timestamp` values.

### Calendar helpers and building dates

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT last_day(DATE'2026-02-10')          AS last_day_feb,
       next_day(DATE'2026-03-04', 'MON')    AS next_monday,
       next_day(DATE'2026-03-02', 'MO')     AS next_monday_from_monday,
       make_date(2026, 3, 31)                AS made,
       make_timestamp(2026, 3, 31, 23, 59, 59.5)                  AS made_ts,
       make_timestamp(2026, 3, 31, 18, 0, 0, 'America/Edmonton')  AS made_ts_tz,
       make_timestamp_ntz(2026, 3, 31, 18, 0, 0)                  AS made_ntz;
SELECT make_date(2026, 2, 30);
SELECT try_make_timestamp(2026, 2, 30, 0, 0, 0);
```

Output (from `ex01_dates.out`):
```text
+------------+-----------+-----------------------+----------+---------------------+-------------------+-------------------+
|last_day_feb|next_monday|next_monday_from_monday|made      |made_ts              |made_ts_tz         |made_ntz           |
+------------+-----------+-----------------------+----------+---------------------+-------------------+-------------------+
|2026-02-28  |2026-03-09 |2026-03-09             |2026-03-31|2026-03-31 23:59:59.5|2026-04-01 00:00:00|2026-03-31 18:00:00|
+------------+-----------+-----------------------+----------+---------------------+-------------------+-------------------+

ERROR: [DATETIME_FIELD_OUT_OF_BOUNDS.WITH_SUGGESTION] Invalid date 'FEBRUARY 30'.
+---------+
|try_feb30|
+---------+
|NULL     |
+---------+
```

`next_day` returns "the first date which is later than" the input, so from Monday March 2 the next Monday is March 9, not March 2. `make_timestamp` with a time zone reads the fields as wall-clock time in that zone: 18:00 in Edmonton (UTC-6 in March 2026) is 00:00 UTC the next day.

`make_date` behaves differently by product. Its page says: "In Databricks SQL, if any of the arguments is out of bounds, the result is `NULL`. In Databricks Runtime, if any of the arguments are out of bounds, Databricks raises DATETIME_FIELD_OUT_OF_BOUNDS unless spark.sql.ansi.enabled is `false`". Open-source Spark here raised the error. `try_make_timestamp` (Applies to: Databricks SQL Databricks Runtime) returns `NULL` instead.

A bad day name in `next_day` raised `ILLEGAL_DAY_OF_WEEK` here; the Databricks page names the error `INVALID_PARAMETER_VALUE`. Either way it is an error under ANSI mode, not a `NULL`.

### extract and date_part

`extract(field FROM source)` is the SQL-standard form; `date_part('field', source)` is the same with a string field. Two details matter: `SECOND` returns `DECIMAL(8, 6)` (it includes fractions), and the day-of-week numbering depends on the field you ask for.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_ts,
       extract(YEAR FROM order_ts)          AS y,
       extract(QUARTER FROM order_ts)       AS q,
       extract(WEEK FROM order_ts)          AS iso_week,
       extract(DAYOFWEEK FROM order_ts)     AS dow_sun1,
       extract(DAYOFWEEK_ISO FROM order_ts) AS dow_mon1,
       date_part('HOUR', order_ts)          AS h,
       typeof(extract(SECOND FROM order_ts)) AS s_type
FROM silver.orders WHERE order_id IN (1001, 1009) ORDER BY order_id;
```

Output (from `ex01_dates.out`, trimmed):
```text
+-------------------+----+---+--------+--------+--------+---+------------+
|order_ts           |y   |q  |iso_week|dow_sun1|dow_mon1|h  |s_type      |
+-------------------+----+---+--------+--------+--------+---+------------+
|2026-03-01 10:15:00|2026|1  |9       |1       |7       |10 |decimal(8,6)|
|2026-03-04 19:25:00|2026|1  |10      |4       |3       |19 |decimal(8,6)|
+-------------------+----+---+--------+--------+--------+---+------------+
```

| Field or function | Sunday | Monday | Saturday |
| --- | --- | --- | --- |
| `extract(DAYOFWEEK ...)`, `dayofweek()` | 1 | 2 | 7 |
| `extract(DAYOFWEEK_ISO ...)` | 7 | 1 | 6 |
| `weekday()` | 6 | 0 | 5 |

`WEEK` is the ISO 8601 week ("a week is considered to start on a Monday and week 1 is the first week with >3 days"), so early January dates can belong to week 52 or 53 of the previous year. Pair it with `YEAROFWEEK`, never with `YEAR`, when you build a "year-week" key. PySpark has `F.year`, `F.quarter`, `F.weekofyear`, `F.dayofweek` and `F.hour`, with the same numbering.

## 19.3 Parsing, formatting and time zones
*Level: intermediate.*

### to_date, to_timestamp and their try_ versions

**The problem.** Bronze data arrives as strings, often in more than one format. `bronze.orders_raw.order_ts` holds ISO 8601 with `Z`, a plain `yyyy-MM-dd HH:mm:ss`, a European `dd/MM/yyyy HH:mm`, an ISO string with a `-05:00` offset, a unix epoch and one garbage value.

`to_date(expr [, fmt])` and `to_timestamp(expr [, fmt])` parse strings. Without `fmt`, each is a synonym for `cast(expr AS DATE)` or `cast(expr AS TIMESTAMP)`. With `fmt`, the string must match the pattern. Under ANSI mode a failure raises an error: `CAST_INVALID_INPUT` without a format, `CANNOT_PARSE_TIMESTAMP` with one. The `try_` versions return `NULL` instead:

| Function | Applies to |
| --- | --- |
| `to_date`, `to_timestamp` | Databricks SQL, Databricks Runtime |
| `try_to_timestamp(expr [, fmt])` | Databricks SQL, Databricks Runtime 11.3 LTS and above |
| `try_to_date(expr [, fmt])` | Databricks SQL, Databricks Runtime 17.2 and above |
| `try_cast(expr AS DATE)` | Databricks SQL, Databricks Runtime 10.4 LTS and above |

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT to_date('01/03/2026', 'dd/MM/yyyy')                AS d3,
       to_timestamp('2026-03-01T10:15:00Z')               AS ts_iso_z,
       to_timestamp('2026-03-02T14:20:00-05:00')          AS ts_offset,
       to_timestamp('02/03/2026 09:40', 'dd/MM/yyyy HH:mm') AS ts_fmt;
SELECT to_date('01/03/2026');                                       -- no format
SELECT to_timestamp('2026-03-01 10:15', 'yyyy-MM-dd HH:mm:ss');     -- format mismatch
SELECT try_to_timestamp('2026-03-01 10:15', 'yyyy-MM-dd HH:mm:ss') AS try_fmt_mismatch;
SELECT try_to_date('31/03/2026', 'dd/MM/yyyy') AS ok, try_to_date('31/02/2026', 'dd/MM/yyyy') AS bad;
```

Output (from `ex02_parse_tz.out`):
```text
+----------+-------------------+-------------------+-------------------+
|d3        |ts_iso_z           |ts_offset          |ts_fmt             |
+----------+-------------------+-------------------+-------------------+
|2026-03-01|2026-03-01 10:15:00|2026-03-02 19:20:00|2026-03-02 09:40:00|
+----------+-------------------+-------------------+-------------------+
ERROR: [CAST_INVALID_INPUT] The value '01/03/2026' of the type "STRING" cannot be cast to "DATE" because it is malformed.
ERROR: [CANNOT_PARSE_TIMESTAMP] Text '2026-03-01 10:15' could not be parsed at index 16.
+----------------+
|try_fmt_mismatch|
+----------------+
|NULL            |
+----------------+
+----------+----+
|ok        |bad |
+----------+----+
|2026-03-31|NULL|
+----------+----+
```

The string with `-05:00` became 19:20 in the `UTC` session: a `TIMESTAMP` stores an instant, so the offset is applied and then dropped.

The standard silver pattern for a column with several formats is a `coalesce` of `try_` parsers, most specific first, so the first parser that succeeds wins and the rest return `NULL`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, order_ts AS raw,
       coalesce(
         try_to_timestamp(order_ts),
         try_to_timestamp(order_ts, 'dd/MM/yyyy HH:mm'),
         timestamp_seconds(try_cast(order_ts AS BIGINT))
       ) AS order_ts_clean
FROM bronze.orders_raw ORDER BY order_id;
```
```python
(spark.table("bronze.orders_raw")
 .select("order_id", F.col("order_ts").alias("raw"),
         F.coalesce(
             F.try_to_timestamp(F.col("order_ts")),
             F.try_to_timestamp(F.col("order_ts"), F.lit("dd/MM/yyyy HH:mm")),
             F.timestamp_seconds(F.col("order_ts").try_cast("bigint")),
         ).alias("order_ts_clean"))
 .orderBy("order_id"))
```

Output (SQL and PySpark agree, from `ex02_parse_tz.out`):
```text
+--------+-------------------------+-------------------+
|order_id|raw                      |order_ts_clean     |
+--------+-------------------------+-------------------+
|1001    |2026-03-01T10:15:00Z     |2026-03-01 10:15:00|
|1002    |2026-03-01 11:05:00      |2026-03-01 11:05:00|
|1003    |02/03/2026 09:40         |2026-03-02 09:40:00|
|1004    |2026-03-02T14:20:00-05:00|2026-03-02 19:20:00|
|1005    |1772528100               |2026-03-03 08:55:00|
|1006    |not a date               |NULL               |
|1007    |2026-03-04 12:00:00      |2026-03-04 12:00:00|
+--------+-------------------------+-------------------+
```

!!! warning "A NULL from a try_ function is a data quality signal, not a fix"
    The `try_` functions stop the job from failing, but order 1006 now has no timestamp. Count those rows (`count_if(order_ts_clean IS NULL)`) and send them to a quarantine table or an expectation ([chapter 14](14-Data-Quality-and-CDC.md)), instead of letting them disappear from daily totals. Also note the order of the `coalesce`: `dd/MM/yyyy` and `MM/dd/yyyy` both parse `02/03/2026`, so a column that mixes them cannot be fixed by guessing. Ask the source which format it sends.

### Datetime patterns and their traps

The [Datetime patterns](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-datetime-pattern) page lists the letters used by `to_date`, `to_timestamp`, `date_format`, `unix_timestamp`, `from_unixtime` and the CSV and JSON readers. The ones you use daily:

| Letter | Meaning | Example |
| --- | --- | --- |
| `y` | year | `yyyy` = 2026 |
| `M` / `L` | month-of-year | `MM` = 03, `MMM` = Mar, `MMMM` = March |
| `d` | day-of-month | `dd` = 04 |
| `D` | day-of-year | `D` = 63 |
| `E` | day-of-week (text) | `EEE` = Wed, `EEEE` = Wednesday |
| `H` | hour-of-day (0-23) | `HH` = 19 |
| `h` | clock-hour-of-am-pm (1-12) | `hh` = 07, with `a` = PM |
| `m` | minute-of-hour | `mm` = 10 |
| `s` | second-of-minute | `ss` = 00 |
| `S` | fraction-of-second | `SSS` = 000 |
| `a` | am-pm-of-day | PM |
| `X`, `x`, `Z`, `O` | zone offset | `XXX` = -06:00, `Z` for zero with `X` |
| `'...'` | literal text | `'T'` |

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_ts,
       date_format(order_ts, 'yyyy-MM-dd')   AS iso_day,
       date_format(order_ts, 'yyyy-mm-dd')   AS trap_mm_minutes,
       date_format(order_ts, 'dd MMM yyyy')  AS short_month,
       date_format(order_ts, 'EEEE, MMMM d') AS long_names,
       date_format(order_ts, 'hh:mm a')      AS clock12,
       date_format(order_ts, 'yyyy-DD')      AS trap_DD
FROM silver.orders WHERE order_id IN (1001, 1014) ORDER BY order_id;
SELECT date_format(DATE'2026-12-31', 'YYYY-MM-dd');
SELECT date_format(DATE'2026-03-01', 'EEEEE');
SELECT to_date('Sun 2026-03-01', 'EEE yyyy-MM-dd');
```

Output (from `ex02_parse_tz.out`, trimmed):
```text
+-------------------+----------+---------------+-----------+------------------+--------+-------+
|order_ts           |iso_day   |trap_mm_minutes|short_month|long_names        |clock12 |trap_DD|
+-------------------+----------+---------------+-----------+------------------+--------+-------+
|2026-03-01 10:15:00|2026-03-01|2026-15-01     |01 Mar 2026|Sunday, March 1   |10:15 AM|2026-60|
|2026-04-01 03:20:00|2026-04-01|2026-20-01     |01 Apr 2026|Wednesday, April 1|03:20 AM|2026-91|
+-------------------+----------+---------------+-----------+------------------+--------+-------+
ERROR: [INCONSISTENT_BEHAVIOR_CROSS_VERSION.DATETIME_PATTERN_RECOGNITION] You may get a different result due to the upgrading to Spark >= 3.0: Fail to recognize 'YYYY-MM-dd' pattern in the DateTimeFormatter.
ERROR: [INCONSISTENT_BEHAVIOR_CROSS_VERSION.DATETIME_PATTERN_RECOGNITION] ... Fail to recognize 'EEEEE' pattern in the DateTimeFormatter.
ERROR: [INCONSISTENT_BEHAVIOR_CROSS_VERSION.DATETIME_PATTERN_RECOGNITION] ... Fail to recognize 'EEE yyyy-MM-dd' pattern in the DateTimeFormatter.
```

The traps, in order of how often they bite:

1. **`mm` is minutes, `MM` is months.** `'yyyy-mm-dd'` runs without error and writes the minutes where the month should be (`2026-15-01`). Nothing fails, so the bug reaches the report.
2. **`DD` is day-of-year, `dd` is day-of-month.** `'yyyy-DD'` gave `2026-60` for March 1.
3. **`hh` is the 12-hour clock.** Without `a` you cannot tell 03:20 from 15:20. Use `HH` in data.
4. **`Y` is not in the pattern table.** Week-based year (`YYYY` in Java and some other tools) is not listed on the Datetime patterns page, and Spark 4.2 here rejected `'YYYY-MM-dd'` with `INCONSISTENT_BEHAVIOR_CROSS_VERSION`. That is better than a silent wrong year: in Java's formatter with `Locale.US`, week-based year turns December 31, 2026 into 2027 (a Java 21 one-liner here; with an ISO-week locale such as `Locale.UK` it stays 2026, so the result even depends on the locale).
5. **Text fields have letter limits.** "5 or more letters will fail" for text fields like `E`, which is why `'EEEEE'` errored.
6. **Some letters only format.** The page says "Symbols of 'E', 'F', 'q' and 'Q' can only be used for datetime formatting, e.g. `date_format`. They are not allowed used for datetime parsing, e.g. `to_timestamp`." Parsing `'Sun 2026-03-01'` with `EEE` failed here.

Two more rules from the page: two-letter years parse "using the base value of 2000", so `'yy'` turns `'99'` into 2099, and "Databricks supports datetime of micro-of-second precision, which has up to 6 significant digits, but can parse nano-of-second with exceeded part truncated."

!!! tip "In the interview"
    **"A report shows months like 15 and 20. What happened?"** The format string used `mm` (minutes) instead of `MM` (months), for example `date_format(ts, 'yyyy-mm-dd')`. Spark does not reject it because both are valid letters. Fix the pattern to `yyyy-MM-dd`, and add a test that checks a known timestamp formats to a known string.

### Unix time

A **unix timestamp** is the number of seconds since 1970-01-01 00:00:00 UTC. Event streams often send it.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT unix_timestamp(TIMESTAMP'2026-03-03 08:55:00') AS secs,
       from_unixtime(1772528100)                       AS from_unix_string,
       typeof(from_unixtime(1772528100))               AS t,
       timestamp_seconds(1772528100)                   AS as_timestamp,
       typeof(timestamp_seconds(1772528100))           AS t2,
       unix_timestamp('03/03/2026', 'dd/MM/yyyy')      AS parse_and_convert;
```

Output (from `ex02_parse_tz.out`, trimmed):
```text
+----------+-------------------+------+-------------------+---------+-----------------+
|secs      |from_unix_string   |t     |as_timestamp       |t2       |parse_and_convert|
+----------+-------------------+------+-------------------+---------+-----------------+
|1772528100|2026-03-03 08:55:00|string|2026-03-03 08:55:00|timestamp|1772496000       |
+----------+-------------------+------+-------------------+---------+-----------------+
```

`from_unixtime` returns a **`STRING`** (formatted with `'yyyy-MM-dd HH:mm:ss'` unless you pass `fmt`), so a column built with it sorts and compares as text. Use `timestamp_seconds` (or `timestamp_millis` for milliseconds) when you want a real `TIMESTAMP`. `unix_timestamp` with a string uses the default `fmt` `'yyyy-MM-dd HH:mm:ss'`; both `unix_timestamp` and `from_unixtime` read and write wall-clock time in the session time zone. In PySpark: `F.unix_timestamp`, `F.from_unixtime`, `F.timestamp_seconds`.

### Session time zone, TIMESTAMP and TIMESTAMP_NTZ

The `TIMESTAMP` type (also written `TIMESTAMP_LTZ`, "local time zone") "represents an absolute point in time". Its page says: "Timestamps with local timezone are internally normalized and persisted in UTC. Whenever the value or a portion of it is extracted the local session timezone is applied." So the stored instant never changes, but what you *see* (the display, `CAST(... AS DATE)`, `extract`, `date_trunc`, `date_format`) depends on the **session time zone**.

On a SQL warehouse the session time zone is the `TIMEZONE` parameter (Applies to: Databricks SQL), whose "system default is `UTC`". `SET TIME ZONE 'America/Edmonton'` (Applies to: Databricks SQL Databricks Runtime) changes it for the session. Region IDs "must have the form 'area/city'" (such as `'America/Los_Angeles'`), and zone offsets such as `'-06:00'` are also accepted; the page warns that "other short names are not recommended to use because they can be ambiguous".

Order 1014 was placed at 03:20 UTC on April 1, which was still March 31 in Calgary:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, order_ts, CAST(order_ts AS DATE) AS order_date,
       date_format(order_ts, 'yyyy-MM-dd HH:mm XXX')    AS with_offset,
       from_utc_timestamp(order_ts, 'America/Edmonton') AS edmonton_wall_clock,
       unix_timestamp(order_ts) AS epoch
FROM silver.orders WHERE order_id = 1014;

SET TIME ZONE 'America/Edmonton';
SELECT order_id, order_ts, CAST(order_ts AS DATE) AS order_date,
       date_format(order_ts, 'yyyy-MM-dd HH:mm XXX') AS with_offset,
       date_trunc('MONTH', order_ts) AS month_bucket,
       unix_timestamp(order_ts) AS epoch
FROM silver.orders WHERE order_id = 1014;
SET TIME ZONE 'UTC';
```

Output (from `ex02_parse_tz.out`, trimmed; the script also computes `to_utc_timestamp`):
```text
-- session time zone UTC
+--------+-------------------+----------+------------------+-------------------+----------+
|order_id|order_ts           |order_date|with_offset       |edmonton_wall_clock|epoch     |
+--------+-------------------+----------+------------------+-------------------+----------+
|1014    |2026-04-01 03:20:00|2026-04-01|2026-04-01 03:20 Z|2026-03-31 21:20:00|1775013600|
+--------+-------------------+----------+------------------+-------------------+----------+
-- session time zone America/Edmonton
+--------+-------------------+----------+-----------------------+-------------------+----------+
|order_id|order_ts           |order_date|with_offset            |month_bucket       |epoch     |
+--------+-------------------+----------+-----------------------+-------------------+----------+
|1014    |2026-03-31 21:20:00|2026-03-31|2026-03-31 21:20 -06:00|2026-03-01 00:00:00|1775013600|
+--------+-------------------+----------+-----------------------+-------------------+----------+
```

The epoch is the same in both sessions: the instant did not change. But the order's date, and its monthly bucket, moved from April to March. A gold table of "daily sales" is only correct for the time zone the business reports in, so make the time zone explicit: set it in the job, or convert with `from_utc_timestamp(ts, 'America/Edmonton')` before you truncate.

`from_utc_timestamp(expr, timeZone)` "returns the timestamp at `timeZone` for a timestamp `expr` at UTC": it shifts the wall-clock reading. `to_utc_timestamp(expr, timeZone)` is the reverse. Both return `TIMESTAMP`, so the result is a shifted instant, which is fine for display and bucketing but wrong if you later treat it as a true UTC instant again.

**`TIMESTAMP_NTZ`** ("no time zone") is the other type. It holds the fields year to second "without taking any time zone into account": what you insert is what you read, in every session. Its page says "Applies to: Databricks SQL Databricks Runtime 13.3 LTS and above" and "This feature is in Public Preview".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE TABLE silver.tz_demo (id INT, ts TIMESTAMP, ts_ntz TIMESTAMP_NTZ) USING DELTA;
INSERT INTO silver.tz_demo VALUES
  (1, TIMESTAMP'2026-03-31 21:20:00', TIMESTAMP_NTZ'2026-03-31 21:20:00');   -- session in UTC
SET TIME ZONE 'America/Edmonton';
SELECT id, ts, ts_ntz FROM silver.tz_demo;
SELECT convert_timezone('America/Edmonton', 'UTC', TIMESTAMP_NTZ'2026-03-31 21:20:00') AS convert_tz;
SET TIME ZONE 'UTC';
SHOW TBLPROPERTIES silver.tz_demo;
```

Output (from `ex02_parse_tz.out`, trimmed):
```text
+---+-------------------+-------------------+
|id |ts                 |ts_ntz             |
+---+-------------------+-------------------+
|1  |2026-03-31 15:20:00|2026-03-31 21:20:00|
+---+-------------------+-------------------+
+-------------------+
|convert_tz         |
+-------------------+
|2026-04-01 03:20:00|
+-------------------+
+--------------------------+---------+
|key                       |value    |
+--------------------------+---------+
|delta.feature.timestampNtz|supported|
|delta.minReaderVersion    |3        |
|delta.minWriterVersion    |7        |
...
```

The `TIMESTAMP` column moved six hours when the session changed; the `TIMESTAMP_NTZ` column did not. `convert_timezone([sourceTz, ] targetTz, sourceTs)` (Applies to: Databricks SQL Databricks Runtime 13.3 LTS and above) converts an NTZ wall-clock reading from one zone to another.

Creating the table turned on the Delta table feature `timestampNtz`, which upgrades the table protocol. The `TIMESTAMP_NTZ` page says support "is enabled automatically when you create a new Delta table with a column of `TIMESTAMP_NTZ` type", but "it is not enabled automatically when you add a column of `TIMESTAMP_NTZ` type to an existing table"; then you run `ALTER TABLE ... SET TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported')`. It also notes that schema inference for CSV and JSON files still gives `TIMESTAMP`, not `TIMESTAMP_NTZ`.

| | `TIMESTAMP` (`TIMESTAMP_LTZ`) | `TIMESTAMP_NTZ` |
| --- | --- | --- |
| Meaning | an instant | a wall-clock reading |
| Stored as | UTC, displayed in the session time zone | the fields as written |
| Changes with `SET TIME ZONE` | display and date parts change | nothing changes |
| Good for | event times from systems (orders, clicks, CDC) | local business times with no zone (store opening hours, a birthday party at 18:00 "local") |
| Applies to | Databricks SQL, Databricks Runtime | Databricks SQL, Databricks Runtime 13.3 LTS and above (Public Preview) |

!!! tip "In the interview"
    **"Daily sales in gold do not match the finance report for the last day of the month. Why?"** Most likely time zones. `order_ts` is a `TIMESTAMP` stored in UTC, and the job grouped by `CAST(order_ts AS DATE)` in a UTC session, while finance counts days in local time. An order at 03:20 UTC on April 1 is a March 31 order in Calgary. Convert to the reporting zone first (`from_utc_timestamp`, or `SET TIME ZONE` for the job), then truncate, and document the zone in the table comment.

## 19.4 Strings and regular expressions
*Level: beginner.*

**The problem.** `bronze.customers_raw` has names with extra spaces and random case, emails with leading or trailing spaces and one written as `chloe(at)example.com`, and phone numbers in four formats. Silver needs one clean value per column.

### Concatenation and NULL

`concat(expr1, ...)` and the `||` operator are synonyms. `concat_ws(sep, expr1, ...)` joins with a separator, and its page says "`exprN` that are NULL are ignored". The difference matters when a column can be `NULL`, as `status` is for order 1008.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT concat('RRS-', order_id)                AS c1,
       'RRS-' || order_id                      AS c2,
       concat('RRS-', status)                  AS concat_null,
       'RRS-' || status                        AS pipes_null,
       concat_ws('-', 'RRS', order_id, status) AS concat_ws_skips_null,
       concat_ws('|', array('a', 'b'), 'c')    AS ws_with_array
FROM silver.orders WHERE order_id IN (1007, 1008) ORDER BY order_id;
```
```python
(spark.table("silver.orders").where("order_id IN (1007, 1008)").orderBy("order_id")
 .select(F.concat(F.lit("RRS-"), "status").alias("concat_null"),
         F.concat_ws("-", F.lit("RRS"), "order_id", "status").alias("concat_ws")))
```

Output (SQL; the PySpark columns match, from `ex03_strings.out`):
```text
+--------+--------+-----------+-----------+--------------------+-------------+
|c1      |c2      |concat_null|pipes_null |concat_ws_skips_null|ws_with_array|
+--------+--------+-----------+-----------+--------------------+-------------+
|RRS-1007|RRS-1007|RRS-SHIPPED|RRS-SHIPPED|RRS-1007-SHIPPED    |a|b|c        |
|RRS-1008|RRS-1008|NULL       |NULL       |RRS-1008            |a|b|c        |
+--------+--------+-----------+-----------+--------------------+-------------+
```

One `NULL` argument makes the whole `concat` result `NULL`. `concat_ws` drops it, together with its separator. That is convenient for display strings, and a trap for row hashes (section 19.11). `concat_ws` also flattens an `ARRAY<STRING>` argument.

### Substrings and positions: everything is 1-based

`substring(expr, pos [, len])` (synonym `substr`) says "`pos` is 1 based. If `pos` is negative the start is determined by counting characters ... from the end." `instr(str, substr)` returns "the (1-based) index of the first occurrence", and 0 when not found. `locate(substr, str)` and `position(substr IN str)` do the same with the arguments the other way round.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT email,
       substring(email, 1, 3)                     AS sub_1_3,
       substr(email, -11)                         AS last_11,
       left(email, 3) AS left3, right(email, 3)   AS right3,
       instr(email, '@')                          AS instr_at,
       locate('@', email)                         AS locate_at,
       position('@' IN email)                     AS position_at,
       substring(email, 1, instr(email, '@') - 1) AS user_part,
       substring(email, 0, 3)                     AS sub_from_0
FROM silver.customers WHERE customer_id IN (1, 3) ORDER BY customer_id;
SELECT instr('ana@example.com', 'x@') AS not_found, substring('abc', 5) AS past_end;
```

Output (from `ex03_strings.out`):
```text
+-----------------+-------+-----------+-----+------+--------+---------+-----------+---------+----------+
|email            |sub_1_3|last_11    |left3|right3|instr_at|locate_at|position_at|user_part|sub_from_0|
+-----------------+-------+-----------+-----+------+--------+---------+-----------+---------+----------+
|ana@example.com  |ana    |example.com|ana  |com   |4       |4        |4          |ana      |ana       |
|chloe@example.com|chl    |example.com|chl  |com   |6       |6        |6          |chloe    |chl       |
+-----------------+-------+-----------+-----+------+--------+---------+-----------+---------+----------+
+---------+--------+
|not_found|past_end|
+---------+--------+
|0        |        |
+---------+--------+
```

`substring(email, 0, 3)` returned the same three characters as position 1 here. Do not rely on that; write 1. A start past the end gives an empty string, not `NULL` and not an error.

### split, split_part and the regex trap

`split(str, regex [, limit])` returns an `ARRAY<STRING>`, and its second argument "is a regular expression". `split_part(str, delim, partNum)` (Applies to: Databricks SQL Databricks Runtime 11.3 LTS and above) splits on a plain delimiter and returns one part, counting from 1 (negative counts from the end). Its page says a `partNum` beyond the number of parts returns an empty string and `partNum` 0 raises `INVALID_INDEX_OF_ZERO`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT email,
       split(email, '@')          AS parts,
       split(email, '@')[1]       AS domain_0based,
       split_part(email, '@', 2)  AS domain_split_part,
       split_part(email, '.', -1) AS tld,
       split('a.b.c', '.')        AS split_dot_regex,
       split('a.b.c', '[.]')      AS split_dot_escaped
FROM silver.customers WHERE customer_id = 1;
SELECT split_part('a,b,c', ',', 0) AS part0;
```
```python
(spark.table("silver.customers").where("customer_id = 1").select(
    F.split("email", "@").getItem(1).alias("domain"),
    F.split_part("email", F.lit("@"), F.lit(2)).alias("split_part"),
    F.substring_index("email", "@", -1).alias("substring_index")))
```

Output (from `ex03_strings.out`; the PySpark row returns `example.com` three times):
```text
+---------------+------------------+-------------+-----------------+---+---------------+-----------------+
|email          |parts             |domain_0based|domain_split_part|tld|split_dot_regex|split_dot_escaped|
+---------------+------------------+-------------+-----------------+---+---------------+-----------------+
|ana@example.com|[ana, example.com]|example.com  |example.com      |com|[, , , , , ]   |[a, b, c]        |
+---------------+------------------+-------------+-----------------+---+---------------+-----------------+
ERROR: [INVALID_INDEX_OF_ZERO] The index 0 is invalid. An index shall be either < 0 or > 0 (the first element has index 1). SQLSTATE: 22003
```

Two traps in one row. `split(email, '@')[1]` is the **second** element, because the `[ ]` subscript on an array is 0-based while `split_part` is 1-based. And `split('a.b.c', '.')` returned six empty strings: `.` is the regex for "any character", so every character is a separator. Escape it (`'[.]'` or `'\\.'`) or use `split_part`, which takes a plain delimiter.

### Regular expressions

The regex functions take a regular expression (the function pages link the supported syntax): `regexp_extract(str, regexp [, idx])` returns one capture group (default 1, 0 for the whole match), `regexp_extract_all` returns every match as an array, `regexp_replace(str, regexp, rep)` replaces every match, and `rlike` / `regexp_like` test for a match. Applies to: `rlike` "Databricks SQL Databricks Runtime 10.0" (as written on its page), `regexp_like` "Databricks SQL Databricks Runtime 10.4 LTS and above", the others all versions.

The `regexp_extract` page states the rules you need for cleaning: "If `str`, `regexp`, or `idx` is `NULL`, the result is `NULL`. If `regexp` does not match any part of `str`, the result is an empty string", and "If `idx` is greater than the number of capture groups defined in `regexp`, Databricks raises an error."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT email, phone,
       regexp_extract(email, '^([^@]+)@(.+)$', 2)  AS domain,
       regexp_replace(phone, '[^0-9]', '')         AS phone_digits,
       regexp_extract_all(phone, r'(\d+)', 1)      AS digit_groups,
       email RLIKE r'^[a-z0-9.]+@[a-z0-9]+\.[a-z]+$'                        AS ok_raw,
       regexp_like(lower(trim(email)), r'^[a-z0-9.]+@[a-z0-9]+\.[a-z]+$')   AS ok_cleaned
FROM bronze.customers_raw ORDER BY customer_id;
```
```python
(spark.table("bronze.customers_raw").orderBy("customer_id").select(
    F.regexp_extract("email", r"^([^@]+)@(.+)$", 2).alias("domain"),
    F.regexp_replace("phone", r"[^0-9]", "").alias("phone_digits"),
    F.lower(F.trim("email")).rlike(r"^[a-z0-9.]+@[a-z0-9]+\.[a-z]+$").alias("ok_cleaned")))
```

Output (SQL; the PySpark columns match, from `ex03_strings.out`):
```text
+--------------------+-----------------+------------+------------+-------------------+------+----------+
|email               |phone            |domain      |phone_digits|digit_groups       |ok_raw|ok_cleaned|
+--------------------+-----------------+------------+------------+-------------------+------+----------+
|Ana@Example.COM     |+1 (403) 555-0101|Example.COM |14035550101 |[1, 403, 555, 0101]|false |true      |
| ben@example.com    |303.555.0102     |example.com |3035550102  |[303, 555, 0102]   |false |true      |
|chloe(at)example.com|435-555-0103     |            |4355550103  |[435, 555, 0103]   |false |false     |
|dev@example.com     |NULL             |example.com |NULL        |NULL               |false |true      |
+--------------------+-----------------+------------+------------+-------------------+------+----------+
```

Every raw email fails the lowercase pattern (Ana has capitals, Ben a leading space, Dev a trailing space you cannot see in the table). After `lower(trim(email))` only Chloe's address fails, which is the row to quarantine. `regexp_extract` returned an empty string, not `NULL`, for Chloe's domain: test with `= ''` or wrap it in `nullif(..., '')`.

**Backslashes.** In a normal SQL string literal the backslash is an escape character, so a regex `\d` must be written `'\\d'`. The function pages recommend a raw literal instead: "When using literals, use `raw-literal` (`r` prefix) to avoid escape character pre-processing."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT regexp_extract('order 1001', '(\\d+)', 1) AS escaped_literal,
       regexp_extract('order 1001', r'(\d+)', 1)  AS raw_literal,
       regexp_extract('order 1001', '(\d+)', 1)   AS single_backslash;
SELECT regexp_replace('2026-03-01', r'(\d{4})-(\d{2})-(\d{2})', '$3/$2/$1') AS reorder;
SELECT regexp_extract('abc', r'(a)', 2) AS bad_group;
```

Output (from `ex03_strings.out`, trimmed):
```text
+---------------+-----------+----------------+
|escaped_literal|raw_literal|single_backslash|
+---------------+-----------+----------------+
|1001           |1001       |d               |
+---------------+-----------+----------------+
+----------+
|reorder   |
+----------+
|01/03/2026|
+----------+
ERROR: [INVALID_PARAMETER_VALUE.REGEX_GROUP_INDEX] The value of parameter(s) `idx` in `regexp_extract` is invalid: Expects group index between 0 and 1, but got 2. SQLSTATE: 22023
```

The single-backslash version did not fail. The string parser turned `'\d'` into `d`, so the regex `(d+)` matched the letter "d" in "order". This is the most common silent regex bug in Spark SQL. In PySpark, use Python raw strings (`r"\d+"`) and the pattern reaches Spark unchanged.

### Cleaning names: trim, case, padding, translate

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT '[' || name || ']'                                  AS raw,
       '[' || trim(name) || ']'                            AS trimmed,
       initcap(trim(name))                                 AS initcap_once,
       initcap(regexp_replace(trim(name), r'\s+', ' '))    AS clean_name,
       lower(trim(email))                                  AS email_clean
FROM bronze.customers_raw ORDER BY customer_id;
SELECT lpad(CAST(order_id AS STRING), 8, '0') AS lpad8,
       rpad(status, 10, '.')                  AS rpad10,
       lpad('1234567890', 4, '0')             AS lpad_truncates,
       btrim('xxRRSxx', 'x')                  AS btrim_chars,
       trim(BOTH '0' FROM '0010100')          AS trim_chars,
       translate('29,95', ',', '.')           AS comma_to_dot,
       translate('$318.00', '$', '')          AS drop_dollar
FROM silver.orders WHERE order_id = 1001;
```
```python
(spark.table("bronze.customers_raw").orderBy("customer_id").select(
    F.initcap(F.regexp_replace(F.trim("name"), r"\s+", " ")).alias("clean_name"),
    F.lower(F.trim("email")).alias("email_clean"),
    F.lpad("customer_id", 6, "0").alias("cust_code")))
```

Output (from `ex03_strings.out`, trimmed):
```text
+--------------+--------------+------------+------------+--------------------+
|raw           |trimmed       |initcap_once|clean_name  |email_clean         |
+--------------+--------------+------------+------------+--------------------+
|[  ana LOPEZ ]|[ana LOPEZ]   |Ana Lopez   |Ana Lopez   |ana@example.com     |
|[ben  okafor] |[ben  okafor] |Ben  Okafor |Ben Okafor  |ben@example.com     |
|[CHLOE MARTIN]|[CHLOE MARTIN]|Chloe Martin|Chloe Martin|chloe(at)example.com|
|[dev patel]   |[dev patel]   |Dev Patel   |Dev Patel   |dev@example.com     |
+--------------+--------------+------------+------------+--------------------+
+--------+----------+--------------+-----------+----------+------------+-----------+
|lpad8   |rpad10    |lpad_truncates|btrim_chars|trim_chars|comma_to_dot|drop_dollar|
+--------+----------+--------------+-----------+----------+------------+-----------+
|00001001|SHIPPED...|1234          |RRS        |101       |29.95       |318.00     |
+--------+----------+--------------+-----------+----------+------------+-----------+
```

The PySpark version returns the same `clean_name` and `email_clean`, plus `cust_code` `000001` to `000004`. Notes from the pages and the output:

- `trim` removes only the ends. The double space inside "ben  okafor" survives `trim` and `initcap`; collapse it with `regexp_replace(..., r'\s+', ' ')`.
- `initcap` uppercases the first letter of each word and lowercases the rest, so "McDonald" becomes "Mcdonald". Fine for a display column, wrong as a join key. Join on `lower(trim(...))` instead.
- `lpad` page: "If `expr` is longer than `len`, the return value is shortened to `len` characters." `lpad('1234567890', 4, '0')` silently cut the value to `1234`, so check the length of ids before you pad them.
- `translate(expr, from, to)` replaces characters one for one. "If `to` has a shorter length than `from` unmatched characters are removed", which is how `'$'` to `''` deletes the dollar sign.
- `btrim(str, trimStr)` (Applies to: Databricks SQL Databricks Runtime 10.4 LTS and above) and `trim(BOTH ... FROM ...)` remove a set of characters from both ends.

### Formatting numbers as text, and fuzzy matching

`format_string(strfmt, obj, ...)` and `printf` (the two pages give the same description) use "the `java.util.Formatter` class with `Locale.US`". `format_number(expr, scale)` adds thousands separators.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT format_string('Order %d: %s %.2f', order_id, currency, CAST(amount AS DOUBLE)) AS fmt,
       printf('%08d', order_id)        AS printf_pad,
       format_number(amount * 1000, 2) AS format_number
FROM silver.orders WHERE order_id = 1005;
SELECT format_string('%.2f', amount) AS decimal_with_f FROM silver.orders WHERE order_id = 1005;
```

Output (from `ex03_strings.out`, error line shortened; the cause line is from the Spark log of the same run, excerpt in `ex03_strings_log_excerpt.txt`):
```text
+----------------------+----------+-------------+
|fmt                   |printf_pad|format_number|
+----------------------+----------+-------------+
|Order 1005: CAD 318.00|00001005  |318,000.00   |
+----------------------+----------+-------------+
ERROR: An error occurred while calling o240.showString. : org.apache.spark.SparkException: Job aborted due to stage failure: ...
java.util.IllegalFormatConversionException: f != org.apache.spark.sql.types.Decimal
```

Locally, `%.2f` failed on the `DECIMAL(10,2)` column and worked after `CAST(amount AS DOUBLE)`. The Databricks page does not mention this, and it was not tested on Databricks (not verified). For money, `format_number` or `CAST(amount AS STRING)` keeps the exact `DECIMAL` value.

`levenshtein(str1, str2 [, maxDistance])` returns the edit distance. The `maxDistance` argument is marked "Applies to: Databricks SQL Databricks Runtime 13.3 LTS and above", and when `maxDistance` "is less than the distance between the two strings the function returns -1".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT levenshtein('Ana Lopez', 'Anna Lopez')          AS d1,
       levenshtein('Trekking Poles', 'Treking Poles')  AS d2,
       levenshtein('kitten', 'sitting', 2)             AS capped;
SELECT p.name FROM silver.products p
WHERE levenshtein(lower(p.name), lower('trekin poles')) <= 2;
```

Output (from `ex03_strings.out`):
```text
+---+---+------+
|d1 |d2 |capped|
+---+---+------+
|1  |1  |-1    |
+---+---+------+
+--------------+
|name          |
+--------------+
|Trekking Poles|
+--------------+
```

### Collation: case-insensitive comparison without lower()

Strings compare byte by byte by default (`UTF8_BINARY`). The [Collation](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-collation) page (Applies to: Databricks SQL Databricks Runtime 16.1 and above) adds named collations. `UTF8_LCASE` is "a lightweight, case-insensitive collation that converts strings to lowercase before comparing them using `UTF8_BINARY`". `UNICODE` and locale collations (the page's examples include `DE`, `fr_CAN` and `de_CI_AI`) take modifiers such as `CI` (case-insensitive) and `AI` (accent-insensitive); the `AI` and `RTRIM` modifiers say "Applies to: Databricks SQL Databricks Runtime 16.2 and above". The page's comparison table shows the difference: `'Cafe' = 'Café'` is false under `UTF8_LCASE` and true under `UNICODE_CI_AI`. You attach a collation to an expression with `COLLATE`, or to a column in its type definition; a `DEFAULT COLLATION` clause sets the default for an object, which otherwise "is inherited from the containing schema".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT 'ana@example.com' = 'ANA@EXAMPLE.COM'                     AS binary_eq,
       'ana@example.com' COLLATE UTF8_LCASE = 'ANA@EXAMPLE.COM'  AS lcase_eq,
       collation('x' COLLATE UTF8_LCASE)                         AS coll;
```

Output (from `ex03_strings.out`):
```text
+---------+--------+-------------------------+
|binary_eq|lcase_eq|coll                     |
+---------+--------+-------------------------+
|false    |true    |SYSTEM.BUILTIN.UTF8_LCASE|
+---------+--------+-------------------------+
```

A column's collation applies wherever that column is compared, including sorting: the page shows `ORDER BY col COLLATE UTF8_LCASE` as equivalent to `ORDER BY LOWER(col) COLLATE UTF8_BINARY`. The `collate` and `collation` functions are "Applies to: Databricks SQL Databricks Runtime 16.1 and above". The Collation page also points to [limitations when using collations with Delta Lake tables](https://docs.databricks.com/aws/en/tables/features/collation#limitations); read them before you change a column's collation on a shared table.

!!! tip "In the interview"
    **"Clean an email column and extract the domain."** `lower(trim(email))`, validate with `regexp_like(..., r'^...$')` using a raw literal, extract with `split_part(email, '@', 2)` (1-based) or `regexp_extract(email, '^([^@]+)@(.+)$', 2)`, and send the rows that do not match to quarantine instead of returning an empty domain. Mention the two traps: `split(x, '.')` treats the dot as a regex, and `'\d'` in a normal string literal becomes `d`.

## 19.5 Numbers, DECIMAL and the try_ family
*Level: intermediate.*

**The problem.** `amount` is `DECIMAL(10,2)` money. You need to round, divide, sum and average it without losing cents and without a job that fails at 3 a.m. on one bad row. ANSI mode is on in these examples (the Spark 4 default; for the defaults on SQL warehouses, Databricks Runtime and serverless see [chapter 17](17-Databricks-SQL-vs-Standard.md), section 17.2), so overflow and division by zero raise errors.

### Rounding: round, bround, ceil, floor

`round(expr [, targetScale])` uses "`HALF_UP` rounding mode"; `bround` uses "`HALF_EVEN` rounding mode", also known as "banker's rounding", where "the digit `5` is rounded towards an even digit". `ceil` (Applies to: Databricks SQL Databricks Runtime 11.3 LTS and above) and `floor` (Applies to: Databricks SQL Databricks Runtime 10.4 LTS and above) take an optional `targetScale` too; without it, a `DECIMAL(p, s)` input returns `DECIMAL(p - s + 1, 0)`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT round(2.5) AS r25, bround(2.5) AS b25, round(3.5) AS r35, bround(3.5) AS b35,
       round(2.25, 1) AS r225, bround(2.25, 1) AS b225,
       round(1234.5, -2) AS r_neg, ceil(29.95) AS ceil_, floor(29.95) AS floor_,
       ceil(29.951, 2) AS ceil_scale, floor(-29.95) AS floor_neg,
       typeof(ceil(29.95)) AS t_ceil, typeof(round(29.95, 1)) AS t_round;
SELECT 0.1 + 0.2 AS dec_sum, typeof(0.1 + 0.2) AS t;
```
```python
spark.range(1).select(F.round(F.lit(2.5), 0).alias("round"), F.bround(F.lit(2.5), 0).alias("bround"),
                      F.ceil(F.lit(29.95)).alias("ceil"), F.floor(F.lit(29.95)).alias("floor"))
```

Output (from `ex04_numbers_try.out`, trimmed):
```text
+---+---+---+---+----+----+-----+-----+------+----------+---------+------------+------------+
|r25|b25|r35|b35|r225|b225|r_neg|ceil_|floor_|ceil_scale|floor_neg|t_ceil      |t_round     |
+---+---+---+---+----+----+-----+-----+------+----------+---------+------------+------------+
|3  |2  |4  |4  |2.3 |2.2 |1200 |30   |29    |29.96     |-30      |decimal(3,0)|decimal(4,1)|
+---+---+---+---+----+----+-----+-----+------+----------+---------+------------+------------+
+-------+------------+
|dec_sum|t           |
+-------+------------+
|0.3    |decimal(2,1)|
+-------+------------+
+-----+------+----+-----+
|round|bround|ceil|floor|
+-----+------+----+-----+
|3.0  |2.0   |30  |29   |
+-----+------+----+-----+
```

A literal such as `2.5` or `0.1` is a `DECIMAL` in Spark SQL, so `0.1 + 0.2` is exactly `0.3`. In PySpark, `F.lit(2.5)` is a `DOUBLE`, which is why the result prints `3.0`. Keep money in `DECIMAL`: a `DOUBLE` cannot hold most decimal fractions exactly.

### Division, div, mod and pmod

| Expression | Result here | Result type | Note |
| --- | --- | --- | --- |
| `7 / 2` | `3.5` | `double` | `/` is never integer division in Spark SQL |
| `7 div 2` | `3` | `BIGINT` (page) | integral part |
| `-7 div 2` | `-3` | | truncates toward zero |
| `7 % 3`, `mod(7, 3)` | `1` | `int` here | the `mod` page says `DOUBLE` unless both are `DECIMAL`; locally `typeof(mod(7, 3))` is `int` (not verified on Databricks) |
| `mod(-7, 3)` | `-1` | | sign follows the dividend |
| `pmod(-7, 3)` | `2` | | "positive remainder" |
| `7 div 0`, `mod(7, 0)` | error | | `DIVIDE_BY_ZERO`, `REMAINDER_BY_ZERO` |
| `try_divide(7, 0)`, `try_mod(7, 0)` | `NULL` | | `try_mod`: Databricks Runtime 15.3 and above |

(Values from `ex04_numbers_try.out`.)

`pmod` is the one you want for bucketing: `hash(x) % 4` is negative for half of the hashes (practice question 16), `pmod(hash(x), 4)` is always 0 to 3.

### DECIMAL precision and scale

`DECIMAL(p, s)` holds `p` digits, `s` of them after the point; the [DECIMAL type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/decimal-type) page gives a maximum precision of 38 and the example "a DECIMAL(5, 2) has a range of -999.99 to 999.99". Arithmetic widens the type, and aggregates widen it more. The `sum` page: "If `expr` is `DECIMAL(p, s)` the result is `DECIMAL(p + min(10, 31-p), s)`". The `avg` page: "`DECIMAL(p + 4, s + 4)`".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT typeof(amount) AS t_amount, typeof(amount * qty) AS t_amount_x_int,
       typeof(unit_price * unit_price) AS t_dec_x_dec, typeof(amount / 3) AS t_div,
       typeof(sum(amount) OVER ()) AS t_sum, typeof(avg(amount) OVER ()) AS t_avg
FROM silver.orders JOIN silver.order_items USING (order_id) LIMIT 1;
SELECT sum(amount) AS total, avg(amount) AS mean FROM silver.orders;
SELECT CAST(123456.789 AS DECIMAL(5,2)) AS too_big;
SELECT try_cast(123456.789 AS DECIMAL(5,2)) AS try_too_big, CAST(5.345 AS DECIMAL(3,2)) AS rounds_half_up;
SELECT CAST(999999999999999999999999999999999999.99 AS DECIMAL(38,2)) * 10 AS dec_overflow;
SELECT try_multiply(CAST(999999999999999999999999999999999999.99 AS DECIMAL(38,2)), 10) AS try_mult;
```

Output (from `ex04_numbers_try.out`):
```text
+-------------+--------------+-------------+-------------+-------------+-------------+
|t_amount     |t_amount_x_int|t_dec_x_dec  |t_div        |t_sum        |t_avg        |
+-------------+--------------+-------------+-------------+-------------+-------------+
|decimal(10,2)|decimal(21,2) |decimal(21,4)|decimal(14,6)|decimal(20,2)|decimal(14,6)|
+-------------+--------------+-------------+-------------+-------------+-------------+
+-------+----------+
|total  |mean      |
+-------+----------+
|2356.20|147.262500|
+-------+----------+
ERROR: [NUMERIC_VALUE_OUT_OF_RANGE.WITH_SUGGESTION]  123456.789 cannot be represented as Decimal(5, 2). If necessary set "spark.sql.ansi.enabled" to "false" to bypass this error, and return NULL instead. SQLSTATE: 22003
+-----------+--------------+
|try_too_big|rounds_half_up|
+-----------+--------------+
|NULL       |5.35          |
+-----------+--------------+
ERROR: [NUMERIC_VALUE_OUT_OF_RANGE.WITH_SUGGESTION]  9999999999999999999999999999999999999.90 cannot be represented as Decimal(38, 2). ...
+--------+
|try_mult|
+--------+
|NULL    |
+--------+
```

`sum` of `DECIMAL(10,2)` is `DECIMAL(20,2)` (10 + min(10, 21)) and `avg` is `DECIMAL(14,6)`, as the pages say. A cast that does not fit fails under ANSI; in this run a cast that only lost scale rounded half up (`5.345` became `5.35`). Choose the target precision of a gold column from the largest value the business can produce, not from today's data.

### Integer overflow

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT 2147483647 + 1 AS int_overflow;
SELECT try_add(2147483647, 1) AS try_int, 2147483647L + 1 AS as_bigint;
SELECT sum(c) AS s FROM VALUES (9223372036854775807L), (1L) AS t(c);
SELECT try_sum(c) AS s FROM VALUES (9223372036854775807L), (1L) AS t(c);
```

Output (from `ex04_numbers_try.out`):
```text
ERROR: [ARITHMETIC_OVERFLOW] overflow. Use 'try_add' to tolerate overflow and return NULL instead. If necessary set "spark.sql.ansi.enabled" to "false" to bypass this error. SQLSTATE: 22003
+-------+----------+
|try_int|as_bigint |
+-------+----------+
|NULL   |2147483648|
+-------+----------+
ERROR: [ARITHMETIC_OVERFLOW] overflow. Use 'try_add' to tolerate overflow and return NULL instead. ...
+----+
|s   |
+----+
|NULL|
+----+
```

The `sum` page warns that with ANSI off "an overflow of `BIGINT` does not cause an error but 'wraps' the result instead". A wrapped total is a wrong number nobody notices, which is worse than a failed job. That is one reason ANSI mode is the default.

### The try_ family

Each `try_` function does the same work as its strict twin but returns `NULL` where the twin raises an error.

| Strict | Tolerant | Applies to (tolerant) | Error it avoids |
| --- | --- | --- | --- |
| `cast(x AS t)` | `try_cast(x AS t)` | Databricks SQL, Databricks Runtime 10.4 LTS and above | `CAST_INVALID_INPUT`, overflow |
| `a + b`, `a - b`, `a * b` | `try_add`, `try_subtract`, `try_multiply` | Databricks SQL, Databricks Runtime 10.4 LTS and above | `ARITHMETIC_OVERFLOW` |
| `a / b` | `try_divide` | Databricks SQL, Databricks Runtime 10.4 LTS and above | `DIVIDE_BY_ZERO` |
| `mod(a, b)` | `try_mod` | Databricks SQL, Databricks Runtime 15.3 and above | `REMAINDER_BY_ZERO` |
| `sum`, `avg` | `try_sum`, `try_avg` | Databricks SQL, Databricks Runtime 11.3 LTS and above | overflow |
| `element_at(arr, i)` | `try_element_at` | Databricks SQL, Databricks Runtime 10.4 LTS and above | `INVALID_ARRAY_INDEX_IN_ELEMENT_AT` |
| `to_number(s, fmt)` | `try_to_number(s, fmt)` | Databricks SQL, Databricks Runtime 11.3 LTS and above | `INVALID_FORMAT` |
| `to_timestamp`, `to_date` | `try_to_timestamp`, `try_to_date` | 11.3 LTS and above; 17.2 and above | parse errors (section 19.3) |

Two details from the pages: `try_cast` only tolerates bad values "provided that the cast from the type of `sourceExpr` to `targetType` is supported" (a type pair that `cast` does not support at all is still an error), and `try_multiply` returns 0 if either argument is 0.

`bronze.orders_raw.amount` holds `'59.90'`, `' 249.00 '`, `'189.5'`, `'39'`, `'$318.00'`, a European `'29,95'` and a valid `'159.00'`; `customer_id` holds one `'x7'`. `to_number(expr, fmt)` parses formatted numbers: `$` or `L` for a currency sign, `9` or `0` for digits, `,` or `G` for grouping, `.` or `D` for the decimal point.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, customer_id, amount AS raw_amount,
       try_cast(customer_id AS INT)                        AS cust_try_cast,
       try_cast(trim(amount) AS DECIMAL(10,2))             AS amt_try_cast,
       try_to_number(trim(amount), '$999,999.99')          AS amt_try_to_number,
       coalesce(try_cast(trim(amount) AS DECIMAL(10,2)),
                try_to_number(trim(amount), '$999,999.99'),
                try_cast(translate(trim(amount), ',', '.') AS DECIMAL(10,2))) AS amount_clean
FROM bronze.orders_raw ORDER BY order_id;
SELECT CAST('x7' AS INT) AS strict_cast;
SELECT to_number('$318.00', '999.99') AS strict_to_number;
```
```python
(spark.table("bronze.orders_raw").orderBy("order_id").select(
    "order_id",
    F.col("customer_id").try_cast("int").alias("cust"),
    F.coalesce(F.trim("amount").try_cast("decimal(10,2)"),
               F.try_to_number(F.trim("amount"), F.lit("$999,999.99"))).alias("amount_clean")))
```

Output (from `ex04_numbers_try.out`):
```text
+--------+-----------+----------+-------------+------------+-----------------+------------+
|order_id|customer_id|raw_amount|cust_try_cast|amt_try_cast|amt_try_to_number|amount_clean|
+--------+-----------+----------+-------------+------------+-----------------+------------+
|1001    |1          |59.90     |1            |59.90       |NULL             |59.90       |
|1002    |2          | 249.00   |2            |249.00      |NULL             |249.00      |
|1003    |1          |189.5     |1            |189.50      |NULL             |189.50      |
|1004    |3          |39        |3            |39.00       |NULL             |39.00       |
|1005    |4          |$318.00   |4            |NULL        |318.00           |318.00      |
|1006    |2          |29,95     |2            |NULL        |NULL             |29.95       |
|1007    |x7         |159.00    |NULL         |159.00      |NULL             |159.00      |
+--------+-----------+----------+-------------+------------+-----------------+------------+
ERROR: [CAST_INVALID_INPUT] The value 'x7' of the type "STRING" cannot be cast to "INT" because it is malformed. ...
ERROR: [INVALID_FORMAT.MISMATCH_INPUT] The format is invalid: 999.99. The input "STRING" $318.00 does not match the format. SQLSTATE: 42601
```

The PySpark version has only the first two parsers, so it returns `NULL` for order 1006 (`29,95`) and the same values for the rest. The `coalesce` of `try_` parsers is the same pattern as for timestamps in section 19.3: the most specific parser first, a `NULL` only when every parser failed. Note what `'$999,999.99'` did: it parsed `$318.00` but returned `NULL` for `59.90`, because the format requires the dollar sign.

Count the failures in the same job, so a bad batch is visible:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT count(*) AS rows_,
       count_if(try_cast(customer_id AS INT) IS NULL) AS bad_customer_id,
       count_if(try_to_timestamp(order_ts) IS NULL
                AND try_to_timestamp(order_ts, 'dd/MM/yyyy HH:mm') IS NULL
                AND try_cast(order_ts AS BIGINT) IS NULL) AS bad_ts
FROM bronze.orders_raw;
```

Output (from `ex04_numbers_try.out`):
```text
+-----+---------------+------+
|rows_|bad_customer_id|bad_ts|
+-----+---------------+------+
|7    |1              |1     |
+-----+---------------+------+
```

### element_at, maps and arrays

`element_at` on a map returns `NULL` for a missing key, but on an array it raises an error for an index out of bounds; the `[ ]` subscript raises too. `try_element_at` returns `NULL` for both (from `ex04_numbers_try.out`):

```text
SELECT element_at(map('CAD', 1.0, 'USD', 1.36), 'EUR')   -> NULL
SELECT element_at(array(10, 20, 30), 5)                   -> ERROR: [INVALID_ARRAY_INDEX_IN_ELEMENT_AT] The index 5 is out of bounds. The array has 3 elements. ...
SELECT array(10, 20, 30)[5]                               -> ERROR: [INVALID_ARRAY_INDEX] The index 5 is out of bounds. The array has 3 elements. ...
SELECT try_element_at(array(10, 20, 30), 5),
       try_element_at(map('CAD', 1.0, 'USD', 1.36), 'EUR') -> NULL, NULL
```

The rest of the array and map functions are in [chapter 18](18-Semi-Structured-Data.md).

!!! tip "In the interview"
    **"When do you use `try_cast` and when `cast`?"** `cast` in silver code that should fail loudly on a broken contract (a column that must always be a number); `try_cast` (and `try_to_timestamp`, `try_to_number`) at the bronze-to-silver boundary where bad values are expected, always paired with a count or a quarantine of the rows that became `NULL`. Turning ANSI mode off to make a job pass is the wrong fix, because it also hides overflow and wraps `BIGINT` sums.

## 19.6 Conditional and NULL functions
*Level: beginner.*

### CASE, if, iff, decode

`CASE` has two forms: the simple form `CASE expr WHEN opt THEN res ... END` compares `expr = opt`, and the searched form `CASE WHEN cond THEN res ... END` tests conditions. `if(cond, expr1, expr2)` is the two-branch shortcut, and the `if` page says it "is a synonym for `iff` function". `decode(expr, key1, value1, ..., defValue)` is a lookup; its page says "For this function `NULL` matches `NULL`."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, status, amount,
       CASE WHEN amount >= 200 THEN 'large' WHEN amount >= 50 THEN 'medium' ELSE 'small' END AS size_band,
       CASE status WHEN 'SHIPPED' THEN 1 WHEN 'PLACED' THEN 0 END                          AS shipped_flag,
       if(status = 'CANCELLED', 0, amount)                                                 AS net_amount,
       decode(status, 'SHIPPED', 'S', 'PLACED', 'P', NULL, 'unknown', 'other')             AS decoded
FROM silver.orders WHERE order_id IN (1001, 1003, 1004, 1008) ORDER BY order_id;
SELECT iff(1 > 0, 'yes', 'no') AS iff_test;
```
```python
(spark.table("silver.orders").where("order_id IN (1001, 1003, 1004, 1008)").orderBy("order_id")
 .select("order_id", "amount",
         F.when(F.col("amount") >= 200, "large").when(F.col("amount") >= 50, "medium").otherwise("small").alias("size_band"),
         F.when(F.col("status") == "CANCELLED", 0).otherwise(F.col("amount")).alias("net_amount")))
```

Output (SQL; the PySpark columns match, from `ex05_conditional.out`):
```text
+--------+---------+------+---------+------------+----------+-------+
|order_id|status   |amount|size_band|shipped_flag|net_amount|decoded|
+--------+---------+------+---------+------------+----------+-------+
|1001    |SHIPPED  |59.90 |medium   |1           |59.90     |S      |
|1003    |PLACED   |189.50|medium   |0           |189.50    |P      |
|1004    |CANCELLED|39.00 |small    |NULL        |0.00      |other  |
|1008    |NULL     |78.00 |medium   |NULL        |78.00     |unknown|
+--------+---------+------+---------+------------+----------+-------+
ERROR: [UNRESOLVED_ROUTINE] Cannot resolve routine `iff` on search path [`system`.`builtin`, `system`.`session`, `spark_catalog`.`default`]. SQLSTATE: 42883
```

- A `CASE` without `ELSE` returns `NULL` when nothing matches (order 1004's `shipped_flag`).
- `if(status = 'CANCELLED', 0, amount)` returned the amount for order 1008: `NULL = 'CANCELLED'` is `NULL`, not true, so the `else` branch ran.
- `iff` exists on Databricks (its page: "Applies to: Databricks SQL Databricks Runtime"), but not in Apache Spark 4.2, which is why it failed here. Use `if` or `CASE` in code that must run on both.

**The `CASE status WHEN NULL` trap.** The simple form compares with `=`, and `NULL = NULL` is never true:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, status,
       CASE status WHEN NULL THEN 'missing' ELSE 'present' END       AS simple_case_null,
       CASE WHEN status IS NULL THEN 'missing' ELSE 'present' END    AS searched_case_null
FROM silver.orders WHERE order_id IN (1007, 1008) ORDER BY order_id;
```

Output (from `ex05_conditional.out`):
```text
+--------+-------+----------------+------------------+
|order_id|status |simple_case_null|searched_case_null|
+--------+-------+----------------+------------------+
|1007    |SHIPPED|present         |present           |
|1008    |NULL   |present         |missing           |
+--------+-------+----------------+------------------+
```

### coalesce, nvl, nvl2, nullif, ifnull, nullifzero, zeroifnull

| Function | Returns | Synonyms (from the pages) |
| --- | --- | --- |
| `coalesce(e1, e2, ...)` | the first non-`NULL` argument | |
| `nvl(e1, e2)`, `ifnull(e1, e2)` | `e2` if `e1` is `NULL` | "a synonym for `coalesce(expr1, expr2)`" |
| `nvl2(e1, e2, e3)` | `e2` if `e1` is not `NULL`, else `e3` | `CASE WHEN expr1 IS NOT NULL ...` |
| `nullif(e1, e2)` | `NULL` if `e1 = e2`, else `e1` | |
| `nullifzero(e)` | `NULL` if `e` is 0 | "Applies to: Databricks Runtime 16.0 and above" |
| `zeroifnull(e)` | 0 if `e` is `NULL` | "Applies to: Databricks Runtime 16.0 and above" |

The two Snowflake-style helpers `nullifzero` and `zeroifnull` say "Databricks Runtime 16.0 and above" with no Databricks SQL in the label; they ran here on Spark 4.2.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, status,
       coalesce(status, 'UNKNOWN')                AS coalesce_,
       nvl(status, 'UNKNOWN')                     AS nvl_,
       nvl2(status, 'has status', 'no status')    AS nvl2_,
       nullif(status, 'PLACED')                   AS nullif_,
       ifnull(status, 'UNKNOWN')                  AS ifnull_
FROM silver.orders WHERE order_id IN (1003, 1008) ORDER BY order_id;
SELECT nullifzero(0) AS nz, zeroifnull(CAST(NULL AS INT)) AS zn;
```
```python
(spark.table("silver.orders").where("order_id IN (1003, 1008)").orderBy("order_id")
 .select("order_id", F.coalesce("status", F.lit("UNKNOWN")).alias("status_clean"),
         F.nullif(F.col("status"), F.lit("PLACED")).alias("nullif_")))
spark.table("silver.orders").where("order_id IN (1003, 1008)").fillna({"status": "UNKNOWN"})
```

Output (from `ex05_conditional.out`, trimmed):
```text
+--------+------+---------+-------+----------+-------+-------+
|order_id|status|coalesce_|nvl_   |nvl2_     |nullif_|ifnull_|
+--------+------+---------+-------+----------+-------+-------+
|1003    |PLACED|PLACED   |PLACED |has status|NULL   |PLACED |
|1008    |NULL  |UNKNOWN  |UNKNOWN|no status |NULL   |UNKNOWN|
+--------+------+---------+-------+----------+-------+-------+
+----+---+
|nz  |zn |
+----+---+
|NULL|0  |
+----+---+
```

**Arithmetic with a NULL is NULL.** A `LEFT JOIN` to an optional discount table gives `NULL` discounts, and `amount - discount` silently erases the amount:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT o.order_id, o.amount, d.discount,
       o.amount - d.discount              AS naive,
       o.amount - coalesce(d.discount, 0) AS safe
FROM silver.orders o
LEFT JOIN VALUES (1001, 5.00), (1002, 10.00) AS d(order_id, discount) USING (order_id)
WHERE o.order_id IN (1001, 1003) ORDER BY o.order_id;
```

Output (from `ex05_conditional.out`):
```text
+--------+------+--------+-----+------+
|order_id|amount|discount|naive|safe  |
+--------+------+--------+-----+------+
|1001    |59.90 |5.00    |54.90|54.90 |
|1003    |189.50|NULL    |NULL |189.50|
+--------+------+--------+-----+------+
```

**coalesce stops early.** The `coalesce` page: "Unlike for regular functions where all arguments are evaluated before invoking the function, `coalesce` evaluates arguments left to right until a non-null value is found."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT coalesce(1, 1/0) AS short_circuit_ok;
SELECT coalesce(NULL, 1/0) AS evaluated_error;
```

Output (from `ex05_conditional.out`):
```text
+----------------+
|short_circuit_ok|
+----------------+
|1.0             |
+----------------+
ERROR: [DIVIDE_BY_ZERO] Division by zero. Use `try_divide` to tolerate divisor being 0 and return NULL instead. ...
```

**Safe division.** The classic pattern is `x / nullif(y, 0)`: the divisor becomes `NULL` when it is 0, and the result is `NULL` instead of an error. `try_divide(x, y)` does the same in one call.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT customer_id, sum(amount) AS revenue,
       count_if(status = 'CANCELLED') AS cancelled,
       round(sum(amount) / nullif(count_if(status = 'CANCELLED'), 0), 2) AS rev_per_cancel
FROM silver.orders GROUP BY customer_id ORDER BY customer_id;
```

Output (from `ex05_conditional.out`):
```text
+-----------+-------+---------+--------------+
|customer_id|revenue|cancelled|rev_per_cancel|
+-----------+-------+---------+--------------+
|1          |525.40 |0        |NULL          |
|2          |786.45 |0        |NULL          |
|3          |257.90 |1        |257.90        |
|4          |786.45 |1        |786.45        |
+-----------+-------+---------+--------------+
```

### greatest and least skip NULLs

`greatest` "Returns the greatest value of all arguments, skipping null values", and `least` does the same for the smallest. That is unlike `+`, and the same as the `max` aggregate.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT greatest(1, NULL, 3) AS g, least(1, NULL, 3) AS l, greatest(NULL, NULL) AS all_null,
       1 + NULL AS plus_null, max(x) AS max_agg
FROM VALUES (1), (NULL), (3) AS t(x);
SELECT c.customer_id, c.updated_at, max(o.order_ts) AS last_order,
       greatest(c.updated_at, max(o.order_ts)) AS last_activity
FROM silver.customers c LEFT JOIN silver.orders o USING (customer_id)
GROUP BY ALL ORDER BY c.customer_id;
```

Output (from `ex05_conditional.out`, first rows):
```text
+---+---+--------+---------+-------+
|g  |l  |all_null|plus_null|max_agg|
+---+---+--------+---------+-------+
|3  |1  |NULL    |NULL     |3      |
+---+---+--------+---------+-------+
+-----------+-------------------+-------------------+-------------------+
|customer_id|updated_at         |last_order         |last_activity      |
+-----------+-------------------+-------------------+-------------------+
|1          |2026-01-05 09:00:00|2026-04-01 03:20:00|2026-04-01 03:20:00|
|2          |2026-01-07 12:30:00|2026-04-02 08:00:00|2026-04-02 08:00:00|
...
```

`greatest(updated_at, last_order)` is the usual "last activity" column; a customer with no orders still gets `updated_at` instead of `NULL`. In PySpark it is `F.greatest` and `F.least`.

!!! tip "In the interview"
    **"Why does `WHERE status <> 'CANCELLED'` lose rows?"** Because `NULL <> 'CANCELLED'` is `NULL`, and `WHERE` keeps only true. Order 1008 disappears. Write `WHERE status IS DISTINCT FROM 'CANCELLED'` or `WHERE coalesce(status, '') <> 'CANCELLED'` ([chapter 17](17-Databricks-SQL-vs-Standard.md) covers `IS DISTINCT FROM`). The same logic explains `CASE status WHEN NULL` and `amount - NULL`.

## 19.7 Aggregates
*Level: intermediate.*

**The problem.** A gold table needs, per currency: the number of orders, the number shipped, shipped revenue, revenue excluding cancellations, the last status per customer, the list of order ids, and a median order value. One pass over the data, no self-joins.

### The count family

| Expression | Counts |
| --- | --- |
| `count(*)`, `count(1)` | rows |
| `count(expr)` | rows where `expr` is not `NULL` ("all rows for which all `exprN` are not `NULL`") |
| `count(DISTINCT expr, ...)` | distinct non-`NULL` values (or combinations) |
| `count_if(cond)` | rows where `cond` is true |

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT count(*) AS star, count(1) AS one, count(status) AS non_null_status,
       count(DISTINCT status) AS distinct_status,
       count(DISTINCT customer_id, currency) AS distinct_pairs,
       count_if(status = 'SHIPPED') AS shipped, count_if(status IS NULL) AS null_status,
       sum(CASE WHEN status = 'SHIPPED' THEN 1 ELSE 0 END) AS shipped_case
FROM silver.orders;
```
```python
spark.table("silver.orders").agg(
    F.count("*").alias("star"), F.count("status").alias("non_null_status"),
    F.count_distinct("status").alias("distinct_status"),
    F.count_if(F.col("status") == "SHIPPED").alias("shipped"),
    F.sum(F.when(F.col("status") == "SHIPPED", 1).otherwise(0)).alias("shipped_when"))
```

Output (from `ex06_aggregates.out`; PySpark gives 16, 15, 3, 9, 9):
```text
+----+---+---------------+---------------+--------------+-------+-----------+------------+
|star|one|non_null_status|distinct_status|distinct_pairs|shipped|null_status|shipped_case|
+----+---+---------------+---------------+--------------+-------+-----------+------------+
|16  |16 |15             |3              |4             |9      |1          |9           |
+----+---+---------------+---------------+--------------+-------+-----------+------------+
```

`count(status)` skipped order 1008, and `count(DISTINCT status)` counts SHIPPED, PLACED and CANCELLED but not `NULL`.

### NULLs in sum and avg

Aggregates skip `NULL` inputs. That is usually what you want, until a `CASE` without `ELSE` turns rows into `NULL`s and changes the denominator of an average:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT avg(CASE WHEN status = 'SHIPPED' THEN amount END)                     AS avg_shipped_only,
       round(sum(CASE WHEN status = 'SHIPPED' THEN amount END) / count(*), 6) AS sum_over_all_rows,
       avg(CASE WHEN status = 'SHIPPED' THEN amount ELSE 0 END)              AS avg_with_zeros,
       sum(CASE WHEN status = 'NOPE' THEN amount END)                        AS sum_of_no_rows,
       coalesce(sum(CASE WHEN status = 'NOPE' THEN amount END), 0)           AS sum_or_zero
FROM silver.orders;
```

Output (from `ex06_aggregates.out`):
```text
+----------------+-----------------+--------------+--------------+-----------+
|avg_shipped_only|sum_over_all_rows|avg_with_zeros|sum_of_no_rows|sum_or_zero|
+----------------+-----------------+--------------+--------------+-----------+
|182.366667      |102.581250       |102.581250    |NULL          |0.00       |
+----------------+-----------------+--------------+--------------+-----------+
```

The first column is "average shipped order value" (9 rows); the third is "shipped revenue per order" (16 rows). Both are correct answers to different questions, so say which one you mean. A `sum` over no rows is `NULL`, not 0; wrap it in `coalesce(..., 0)` when a report needs a zero.

### FILTER (WHERE ...): conditional aggregates in one pass

Every aggregate accepts `FILTER (WHERE cond)`, and the GROUP BY page says "When a `FILTER` clause is attached to an aggregate function, only the matching rows are passed to that function." It replaces the `sum(CASE WHEN ... THEN x END)` idiom and reads better. PySpark has no `FILTER`; aggregate a `when()` column instead (a `when` without `otherwise` is `NULL` for the other rows, and aggregates skip `NULL`s).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT currency, count(*) AS orders,
       count(*)    FILTER (WHERE status = 'SHIPPED')          AS shipped,
       sum(amount) FILTER (WHERE status = 'SHIPPED')          AS shipped_revenue,
       sum(amount) FILTER (WHERE status <> 'CANCELLED')       AS revenue_not_cancelled,
       avg(amount) FILTER (WHERE order_ts >= TIMESTAMP'2026-03-04') AS avg_since_mar4
FROM silver.orders GROUP BY currency ORDER BY currency;
```
```python
(spark.table("silver.orders").groupBy("currency").agg(
    F.count("*").alias("orders"),
    F.count(F.when(F.col("status") == "SHIPPED", 1)).alias("shipped"),
    F.sum(F.when(F.col("status") == "SHIPPED", F.col("amount"))).alias("shipped_revenue"))
 .orderBy("currency"))
```

Output (from `ex06_aggregates.out`; PySpark returns the first four columns with the same values):
```text
+--------+------+-------+---------------+---------------------+--------------+
|currency|orders|shipped|shipped_revenue|revenue_not_cancelled|avg_since_mar4|
+--------+------+-------+---------------+---------------------+--------------+
|CAD     |9     |4      |665.90         |1044.35              |124.075000    |
|USD     |7     |5      |975.40         |1005.35              |181.600000    |
+--------+------+-------+---------------+---------------------+--------------+
```

Look at `revenue_not_cancelled` for CAD: 1044.35, while CAD revenue minus the cancelled order 1016 would be 1122.35. The 78.00 of order 1008 is missing because `NULL <> 'CANCELLED'` is not true. `FILTER` follows the same three-valued logic as `WHERE` (section 19.6).

### max_by and min_by: "the value at the max"

`max_by(expr, ordExpr)` "Returns the value of an expression associated with the largest value of a second expression in a group." It answers "the latest status per customer" without a window function and a join. The page adds: "If multiple rows have the same maximum value of `ordExpr`, the result is non-deterministic." A third argument `limit` returns an array of up to `limit` values; that form is marked "Applies to: Databricks SQL Databricks Runtime 18.1 and above" (it also ran here on Spark 4.2).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT customer_id, max(order_ts) AS last_ts,
       max_by(status, order_ts)   AS last_status,
       max_by(order_id, amount)   AS biggest_order,
       min_by(order_id, order_ts) AS first_order
FROM silver.orders GROUP BY customer_id ORDER BY customer_id;
SELECT customer_id, max_by(order_id, amount, 2) AS top2_orders
FROM silver.orders GROUP BY customer_id ORDER BY customer_id;
```
```python
(spark.table("silver.orders").groupBy("customer_id").agg(
    F.max_by("status", "order_ts").alias("last_status"),
    F.min_by("order_id", "order_ts").alias("first_order")).orderBy("customer_id"))
```

Output (from `ex06_aggregates.out`):
```text
+-----------+-------------------+-----------+-------------+-----------+
|customer_id|last_ts            |last_status|biggest_order|first_order|
+-----------+-------------------+-----------+-------------+-----------+
|1          |2026-04-01 03:20:00|PLACED     |1003         |1001       |
|2          |2026-04-02 08:00:00|SHIPPED    |1015         |1002       |
|3          |2026-03-15 13:10:00|SHIPPED    |1007         |1004       |
|4          |2026-04-06 11:15:00|CANCELLED  |1005         |1005       |
+-----------+-------------------+-----------+-------------+-----------+
+-----------+------------+
|customer_id|top2_orders |
+-----------+------------+
|1          |[1003, 1014]|
|2          |[1015, 1002]|
|3          |[1007, 1013]|
|4          |[1005, 1012]|
+-----------+------------+
```

### first, last and any_value are not "earliest" and "latest"

`first(expr)`, `last(expr)` and `any_value(expr)` (Applies to: Databricks SQL Databricks Runtime 11.3 LTS and above) all say "This function is non-deterministic." They return a value from whatever row the engine sees first, and an `ORDER BY` in a subquery does not promise that order to the outer aggregate:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT customer_id, first(status) AS first_respect_nulls, first(status, true) AS first_ignore_nulls,
       last(status) IGNORE NULLS AS last_ignore_nulls, any_value(currency) AS any_currency
FROM (SELECT * FROM silver.orders WHERE customer_id = 1 ORDER BY order_ts DESC)
GROUP BY customer_id;
```

Output (from `ex06_aggregates.out`):
```text
+-----------+-------------------+------------------+-----------------+------------+
|customer_id|first_respect_nulls|first_ignore_nulls|last_ignore_nulls|any_currency|
+-----------+-------------------+------------------+-----------------+------------+
|1          |PLACED             |PLACED            |SHIPPED          |CAD         |
+-----------+-------------------+------------------+-----------------+------------+
```

This small local run happened to follow the subquery's order, but nothing guarantees it on a cluster with many partitions. Use `max_by`/`min_by` for "value at the latest time", and `any_value` only for a column that has one value per group anyway (such as a customer's currency).

### collect_list, collect_set, array_agg, listagg and string_agg

`collect_list` (synonym `array_agg`, Applies to: Databricks SQL Databricks Runtime 10.4 LTS and above for the `array_agg` name) builds an array; `collect_set` removes duplicates. Both pages: "The order of elements in the array is non-deterministic. `NULL` values are excluded." `listagg` and its alias `string_agg` (both "Applies to: Databricks SQL Databricks Runtime 16.4 and later") build a delimited string, with an optional `WITHIN GROUP (ORDER BY ...)` that fixes the order.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT customer_id,
       collect_list(status)                 AS statuses_no_nulls,
       collect_set(currency)                AS currencies,
       array_sort(collect_list(order_id))   AS order_ids_sorted,
       size(array_agg(DISTINCT status))     AS n_distinct_status
FROM silver.orders GROUP BY customer_id ORDER BY customer_id;
SELECT customer_id,
       listagg(CAST(order_id AS STRING), ',') WITHIN GROUP (ORDER BY order_id) AS orders_csv,
       string_agg(status, ' > ') WITHIN GROUP (ORDER BY status)              AS statuses
FROM silver.orders GROUP BY customer_id ORDER BY customer_id;
```
```python
(spark.table("silver.orders").groupBy("customer_id").agg(
    F.array_sort(F.collect_list("order_id")).alias("order_ids"),
    F.collect_set("currency").alias("currencies"),
    F.listagg(F.col("order_id").cast("string"), F.lit(",")).alias("listagg_any_order"))
 .orderBy("customer_id"))
```

Output (from `ex06_aggregates.out`):
```text
+-----------+-------------------------------------+----------+------------------------------+-----------------+
|customer_id|statuses_no_nulls                    |currencies|order_ids_sorted              |n_distinct_status|
+-----------+-------------------------------------+----------+------------------------------+-----------------+
|1          |[PLACED, PLACED, SHIPPED, SHIPPED]   |[CAD]     |[1001, 1003, 1008, 1009, 1014]|2                |
|2          |[SHIPPED, SHIPPED, SHIPPED, PLACED]  |[USD]     |[1002, 1006, 1010, 1015]      |2                |
|3          |[SHIPPED, SHIPPED, CANCELLED]        |[USD]     |[1004, 1007, 1013]            |2                |
|4          |[SHIPPED, SHIPPED, PLACED, CANCELLED]|[CAD]     |[1005, 1011, 1012, 1016]      |3                |
+-----------+-------------------------------------+----------+------------------------------+-----------------+
+-----------+------------------------+--------------------------------------+
|customer_id|orders_csv              |statuses                              |
+-----------+------------------------+--------------------------------------+
|1          |1001,1003,1008,1009,1014|PLACED > PLACED > SHIPPED > SHIPPED   |
|2          |1002,1006,1010,1015     |PLACED > SHIPPED > SHIPPED > SHIPPED  |
|3          |1004,1007,1013          |CANCELLED > SHIPPED > SHIPPED         |
|4          |1005,1011,1012,1016     |CANCELLED > PLACED > SHIPPED > SHIPPED|
+-----------+------------------------+--------------------------------------+
```

The PySpark `F.listagg` call without an order returned, for customer 1, `1009,1014,1001,1003,1008`: the order rows happened to arrive in. Customer 1 has five orders but only four statuses in the list, because order 1008's `NULL` was dropped.

To order the list by a **different** column, the portable way is to sort an array of structs and keep one field (`transform` is in [chapter 18](18-Semi-Structured-Data.md)):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT customer_id,
       transform(array_sort(collect_list(struct(order_ts, order_id))), x -> x.order_id) AS orders_by_time
FROM silver.orders GROUP BY customer_id ORDER BY customer_id;
SELECT customer_id,
       listagg(CAST(order_id AS STRING), ',') WITHIN GROUP (ORDER BY order_ts) AS by_other_column
FROM silver.orders GROUP BY customer_id ORDER BY customer_id;
```

Both returned `[1001, 1003, 1008, 1009, 1014]` (as a string in the second case) for customer 1 here. But the `listagg` page says "The column references within `sortKey` must also be present in `expr`", which `ORDER BY order_ts` does not satisfy. Apache Spark 4.2 accepted it; whether Databricks rejects it was not tested (not verified). The `struct` version works on both.

### Approximate and exact statistics

| Function | Result | Note from the page |
| --- | --- | --- |
| `approx_count_distinct(expr [, relativeSD])` | `BIGINT` | HyperLogLog++, "accurate within a default value of 5%" |
| `median(expr)` | `DOUBLE` | Applies to: Databricks SQL Databricks Runtime 11.3 LTS and above; synonym for `percentile_cont(0.5) WITHIN GROUP (ORDER BY expr)` |
| `percentile(expr, p)` | `DOUBLE` or `ARRAY<DOUBLE>` | exact |
| `percentile_approx(expr, p [, accuracy])` | the type of `expr` here | `accuracy` "is set to `10000`" when omitted; "`1.0/accuracy` is the relative error" |
| `mode(expr [, deterministic])` | type of `expr` | Applies to: Databricks SQL Databricks Runtime 11.3 LTS and above; the `deterministic` argument "In Databricks SQL and Databricks Runtime 14.1 and above" |
| `stddev`, `variance` | `DOUBLE` | sample versions; `stddev_pop`, `var_pop` for the population |

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT count(DISTINCT customer_id) AS exact_customers,
       approx_count_distinct(customer_id) AS approx_customers,
       median(amount) AS median_amt, percentile(amount, 0.5) AS p50_exact,
       percentile(amount, array(0.25, 0.75)) AS quartiles,
       percentile_approx(amount, 0.5) AS p50_approx, approx_percentile(amount, 0.9, 100) AS p90_approx,
       mode(amount) AS most_common_amt,
       round(stddev(amount), 2) AS stddev_samp, round(stddev_pop(amount), 2) AS stddev_pop,
       round(variance(amount), 2) AS var_samp
FROM silver.orders;
SELECT typeof(median(amount)) AS t_median, typeof(percentile_approx(amount, 0.5)) AS t_papprox FROM silver.orders;
SELECT stddev(amount) AS one_row_stddev FROM silver.orders WHERE order_id = 1001;
```
```python
spark.table("silver.orders").agg(
    F.approx_count_distinct("customer_id").alias("approx_customers"),
    F.percentile_approx("amount", 0.5).alias("p50_approx"),
    F.median("amount").alias("median"), F.mode("amount").alias("mode"))
```

Output (from `ex06_aggregates.out`):
```text
+---------------+----------------+----------+---------+-----------------+----------+----------+---------------+-----------+----------+--------+
|exact_customers|approx_customers|median_amt|p50_exact|quartiles        |p50_approx|p90_approx|most_common_amt|stddev_samp|stddev_pop|var_samp|
+---------------+----------------+----------+---------+-----------------+----------+----------+---------------+-----------+----------+--------+
|4              |4               |159.0     |159.0    |[54.675, 204.375]|159.0     |318.0     |189.50         |101.87     |98.63     |10377.26|
+---------------+----------------+----------+---------+-----------------+----------+----------+---------------+-----------+----------+--------+
+--------+-------------+
|t_median|t_papprox    |
+--------+-------------+
|double  |decimal(10,2)|
+--------+-------------+
+--------------+
|one_row_stddev|
+--------------+
|NULL          |
+--------------+
```

The exact `percentile` interpolates between rows (54.675 is not an order amount), while `percentile_approx` "returns the expression which is the smallest value in the ordered group ... such that no more than `percentile` of `expr` values is less than the value or equal to that value", so it is always an actual value. The `stddev` page: "If any group consists of only one row, the function returns `NULL` for that group." `mode` found 189.50 (three orders); with a tie the page says the result "is non-deterministic" unless you pass `true` as the `deterministic` argument.

### Boolean aggregates

`bool_and` (synonym `every`) is true when all values are true; `bool_or` (synonyms `some`, `any`) when at least one is.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT customer_id,
       bool_and(status = 'SHIPPED')    AS all_shipped,
       every(currency = 'CAD')         AS all_cad,
       bool_or(status = 'CANCELLED')   AS any_cancelled,
       some(amount > 300)              AS any_over_300
FROM silver.orders GROUP BY customer_id ORDER BY customer_id;
```

Output (from `ex06_aggregates.out`):
```text
+-----------+-----------+-------+-------------+------------+
|customer_id|all_shipped|all_cad|any_cancelled|any_over_300|
+-----------+-----------+-------+-------------+------------+
|1          |false      |true   |false        |false       |
|2          |false      |false  |false        |true        |
|3          |false      |false  |true         |false       |
|4          |false      |true   |true         |true        |
+-----------+-----------+-------+-------------+------------+
```

!!! tip "In the interview"
    **"Get each customer's latest order status."** Three answers, and say when each fits. `max_by(status, order_ts)` with `GROUP BY customer_id` is shortest when you need one column. `QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY order_ts DESC) = 1` returns the whole latest row (section 19.10). A join to `max(order_ts)` is the portable SQL answer but returns two rows on a tie. Then mention ties: `max_by` and `row_number` both pick one row arbitrarily, so add a tiebreaker column (such as `order_id`) to the ordering for a stable result.

## 19.8 GROUPING SETS, ROLLUP and CUBE
*Level: intermediate.*

**The problem.** Finance wants one table with revenue per currency and category, a subtotal per currency, and a grand total. Three `GROUP BY` queries joined with `UNION ALL` scan the data three times and need `NULL` placeholders in each leg.

The [GROUP BY](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-groupby) page describes `GROUPING SETS` as "a shorthand for a `UNION ALL` where each leg of the `UNION ALL` operator performs aggregation of each grouping set". Two more shorthands build the list of grouping sets for you:

- `ROLLUP (a, b)` is `GROUPING SETS ((a, b), (a), ())`: "The N elements of a `ROLLUP` specification result in N+1 `GROUPING SETS`." Use it for hierarchies (year, month, day; country, city).
- `CUBE (a, b)` is every combination, `((a, b), (a), (b), ())`: "The N elements of a `CUBE` specification results in 2^N `GROUPING SETS`."

In a subtotal row, the columns that were not grouped are `NULL`. Two functions tell you which level a row belongs to: `grouping(col)` "is 1 for a specified row if the row represents a subtotal over the grouping of `col`, or 0 if it is not", and `grouping_id(col1, ...)` combines them into one number where "`col1` is represented by the highest order bit".

The examples use the non-cancelled order lines (`qty * unit_price` per line), joined to `products` for the category:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT currency, category, sum(line_amount) AS revenue,
       grouping(currency) AS g_cur, grouping(category) AS g_cat,
       grouping_id(currency, category) AS gid
FROM (SELECT o.currency, p.category, oi.qty * oi.unit_price AS line_amount
      FROM silver.orders o
      JOIN silver.order_items oi USING (order_id)
      JOIN silver.products p USING (product_id)
      WHERE o.status <> 'CANCELLED' OR o.status IS NULL)
GROUP BY GROUPING SETS ((currency, category), (currency), ())
ORDER BY gid, currency, category;
```

Output (from `ex07_grouping_sets.out`):
```text
+--------+--------+-------+-----+-----+---+
|currency|category|revenue|g_cur|g_cat|gid|
+--------+--------+-------+-----+-----+---+
|CAD     |Apparel |477.00 |0    |0    |0  |
|CAD     |Camping |438.50 |0    |0    |0  |
|CAD     |Hiking  |206.85 |0    |0    |0  |
|USD     |Apparel |477.00 |0    |0    |0  |
|USD     |Camping |438.50 |0    |0    |0  |
|USD     |Hiking  |89.85  |0    |0    |0  |
|CAD     |NULL    |1122.35|0    |1    |1  |
|USD     |NULL    |1005.35|0    |1    |1  |
|NULL    |NULL    |2127.70|1    |1    |3  |
+--------+--------+-------+-----+-----+---+
```

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 360" role="img" aria-label="The result of GROUPING SETS ((currency, category), (currency), ()) drawn as three stacked blocks: six detail rows with gid 0, two currency subtotal rows with gid 1 and NULL category, and one grand total row with gid 3 and both columns NULL.">
<text x="20" y="24" font-size="14" fill="currentColor">GROUP BY GROUPING SETS ((currency, category), (currency), ())</text>
<text x="40" y="52" font-size="13" fill="currentColor">currency</text>
<text x="140" y="52" font-size="13" fill="currentColor">category</text>
<text x="240" y="52" font-size="13" fill="currentColor">revenue</text>
<text x="320" y="52" font-size="13" fill="currentColor">gid</text>
<rect x="30" y="60" width="320" height="132" fill="none" stroke="currentColor"/>
<text x="40" y="80" font-size="13" fill="currentColor">CAD</text><text x="140" y="80" font-size="13" fill="currentColor">Apparel</text><text x="240" y="80" font-size="13" fill="currentColor">477.00</text><text x="320" y="80" font-size="13" fill="currentColor">0</text>
<text x="40" y="100" font-size="13" fill="currentColor">CAD</text><text x="140" y="100" font-size="13" fill="currentColor">Camping</text><text x="240" y="100" font-size="13" fill="currentColor">438.50</text><text x="320" y="100" font-size="13" fill="currentColor">0</text>
<text x="40" y="120" font-size="13" fill="currentColor">CAD</text><text x="140" y="120" font-size="13" fill="currentColor">Hiking</text><text x="240" y="120" font-size="13" fill="currentColor">206.85</text><text x="320" y="120" font-size="13" fill="currentColor">0</text>
<text x="40" y="140" font-size="13" fill="currentColor">USD</text><text x="140" y="140" font-size="13" fill="currentColor">Apparel</text><text x="240" y="140" font-size="13" fill="currentColor">477.00</text><text x="320" y="140" font-size="13" fill="currentColor">0</text>
<text x="40" y="160" font-size="13" fill="currentColor">USD</text><text x="140" y="160" font-size="13" fill="currentColor">Camping</text><text x="240" y="160" font-size="13" fill="currentColor">438.50</text><text x="320" y="160" font-size="13" fill="currentColor">0</text>
<text x="40" y="180" font-size="13" fill="currentColor">USD</text><text x="140" y="180" font-size="13" fill="currentColor">Hiking</text><text x="240" y="180" font-size="13" fill="currentColor">89.85</text><text x="320" y="180" font-size="13" fill="currentColor">0</text>
<text x="370" y="110" font-size="13" fill="currentColor">leg 1: GROUP BY currency, category</text>
<text x="370" y="130" font-size="13" fill="currentColor">grouping() is 0 for both columns</text>
<text x="300" y="214" font-size="13" fill="currentColor" text-anchor="middle">UNION ALL</text>
<rect x="30" y="224" width="320" height="48" fill="none" stroke="currentColor" stroke-dasharray="6 3"/>
<text x="40" y="244" font-size="13" fill="currentColor">CAD</text><text x="140" y="244" font-size="13" fill="currentColor">NULL</text><text x="240" y="244" font-size="13" fill="currentColor">1122.35</text><text x="320" y="244" font-size="13" fill="currentColor">1</text>
<text x="40" y="264" font-size="13" fill="currentColor">USD</text><text x="140" y="264" font-size="13" fill="currentColor">NULL</text><text x="240" y="264" font-size="13" fill="currentColor">1005.35</text><text x="320" y="264" font-size="13" fill="currentColor">1</text>
<text x="370" y="244" font-size="13" fill="currentColor">leg 2: GROUP BY currency</text>
<text x="370" y="264" font-size="13" fill="currentColor">category: a subtotal NULL, gid 1</text>
<text x="300" y="294" font-size="13" fill="currentColor" text-anchor="middle">UNION ALL</text>
<rect x="30" y="304" width="320" height="28" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="40" y="323" font-size="13" fill="currentColor">NULL</text><text x="140" y="323" font-size="13" fill="currentColor">NULL</text><text x="240" y="323" font-size="13" fill="currentColor">2127.70</text><text x="320" y="323" font-size="13" fill="currentColor">3</text>
<text x="370" y="316" font-size="13" fill="currentColor">leg 3: () global aggregate</text>
<text x="370" y="336" font-size="13" fill="currentColor">both columns NULL, gid 3</text>
</svg>
<figcaption>Figure 19.3. A GROUPING SETS result is the stacked result of one GROUP BY per grouping set. NULL marks a column that was not grouped in that leg; grouping_id(currency, category) = 2 x grouping(currency) + grouping(category) says which leg a row came from.</figcaption>
</figure>

`ROLLUP (currency, category)` returns the same nine rows. `CUBE (currency, category)` adds a fourth level, the category subtotals, with `gid` 2:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT coalesce(currency, 'ALL') AS currency, coalesce(category, 'ALL') AS category,
       sum(line_amount) AS revenue, grouping_id() AS gid
FROM (... same subquery ...)
GROUP BY ROLLUP (currency, category) ORDER BY gid, currency, category;

SELECT currency, category, sum(line_amount) AS revenue, grouping_id(currency, category) AS gid,
       CASE grouping_id(currency, category)
         WHEN 0 THEN 'currency + category' WHEN 1 THEN 'currency subtotal'
         WHEN 2 THEN 'category subtotal'   WHEN 3 THEN 'grand total' END AS level
FROM (... same subquery ...)
GROUP BY CUBE (currency, category) ORDER BY gid, currency, category;
```
```python
base = spark.sql("SELECT o.currency, p.category, oi.qty * oi.unit_price AS line_amount FROM ...")
base.rollup("currency", "category").agg(F.sum("line_amount").alias("revenue"),
                                        F.grouping_id().alias("gid")).orderBy("gid", "currency", "category")
base.cube("currency", "category").agg(F.sum("line_amount").alias("revenue"), F.grouping_id().alias("gid"))
```

Output (from `ex07_grouping_sets.out`; ROLLUP rows 1 to 6 as above, then the subtotals; CUBE from `gid` 1 on):
```text
ROLLUP:
|CAD     |ALL     |1122.35|1  |
|USD     |ALL     |1005.35|1  |
|ALL     |ALL     |2127.70|3  |
CUBE:
+--------+--------+-------+---+-------------------+
|currency|category|revenue|gid|level              |
+--------+--------+-------+---+-------------------+
|CAD     |NULL    |1122.35|1  |currency subtotal  |
|USD     |NULL    |1005.35|1  |currency subtotal  |
|NULL    |Apparel |954.00 |2  |category subtotal  |
|NULL    |Camping |877.00 |2  |category subtotal  |
|NULL    |Hiking  |296.70 |2  |category subtotal  |
|NULL    |NULL    |2127.70|3  |grand total        |
+--------+--------+-------+---+-------------------+
```

The PySpark `cube` returned 6 rows at `gid` 0, 2 at `gid` 1, 3 at `gid` 2 and 1 at `gid` 3: 2^2 = 4 grouping sets.

**A real NULL and a subtotal NULL look the same.** `coalesce(currency, 'ALL')` is fine when the column has no `NULL`s of its own. `status` does:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT status, count(*) AS orders, grouping(status) AS is_subtotal
FROM silver.orders GROUP BY ROLLUP (status) ORDER BY is_subtotal, status;
```

Output (from `ex07_grouping_sets.out`):
```text
+---------+------+-----------+
|status   |orders|is_subtotal|
+---------+------+-----------+
|NULL     |1     |0          |
|CANCELLED|2     |0          |
|PLACED   |4     |0          |
|SHIPPED  |9     |0          |
|NULL     |16    |1          |
+---------+------+-----------+
```

Two rows show `NULL`. The first is order 1008's missing status, the second is the total. Label with `CASE WHEN grouping(status) = 1 THEN 'ALL' ELSE coalesce(status, 'UNKNOWN') END`, never with `coalesce` alone.

!!! tip "In the interview"
    **"What is the difference between ROLLUP and CUBE?"** `ROLLUP (a, b, c)` gives the hierarchy `(a, b, c), (a, b), (a), ()`, N+1 grouping sets, for drill-down reports such as year, month, day. `CUBE (a, b, c)` gives every combination, 2^N grouping sets, for cross-tab reports. Both are shorthands for `GROUPING SETS`, which is one scan instead of a `UNION ALL` of several `GROUP BY` queries. Use `grouping()` or `grouping_id()` to label subtotal rows, because a real `NULL` in the data looks like a subtotal `NULL`. If a gold table stores several levels, keep the `grouping_id` as a column so readers can filter one level.

## 19.9 Window functions in depth
*Level: expert.*

**The problem.** A `GROUP BY` collapses rows. Many questions need the detail row **and** a number computed over its neighbors: the rank of an order within its customer, the previous order's amount, a running total, a 3-order moving average. Window functions compute those without collapsing. The basics (what `OVER`, `PARTITION BY` and `ORDER BY` do) are in the SQL course chapter [Window functions and ranking](../../databases/sql/13-Window-Functions-Ranking.md); this section covers what interviews probe: ties, frames, the default frame and Spark specifics.

The [Window functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-window-functions) page gives the shape:

```text
function OVER { window_name | ( window_name ) | window_spec }
window_spec  ( [ PARTITION BY partition [ , ... ] ] [ order_by ] [ window_frame ] )
```

and three classes of `function`, with different rules:

| Class | Examples | ORDER BY | Frame |
| --- | --- | --- | --- |
| Ranking | `row_number`, `rank`, `dense_rank`, `ntile`, `percent_rank` | required | "must include an ORDER BY clause, but not a window_frame clause" |
| Analytic | `lag`, `lead`, `nth_value`, `cume_dist` | required for these four (their pages) | `nth_value` uses the frame |
| Aggregate | `sum`, `avg`, `count`, `min`, `max`, `first_value`, `last_value`, `collect_list` | optional | optional; the default depends on `ORDER BY` |

"If no PARTITION clause is specified the partition is comprised of all rows", which on a large table means one task sorts everything. Partition by a key whenever the question allows it.

### Ranking functions and ties

`amount` has many ties (two orders of 318.00, two of 249.00, three of 189.50), which is exactly what ranking questions are about:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, amount,
       row_number()   OVER (ORDER BY amount DESC) AS rn,
       rank()         OVER (ORDER BY amount DESC) AS rnk,
       dense_rank()   OVER (ORDER BY amount DESC) AS drnk,
       ntile(4)       OVER (ORDER BY amount DESC) AS quartile,
       round(percent_rank() OVER (ORDER BY amount DESC), 3) AS pct_rank,
       round(cume_dist()    OVER (ORDER BY amount DESC), 3) AS cume
FROM silver.orders ORDER BY amount DESC, order_id;
```
```python
from pyspark.sql.window import Window
(spark.table("silver.orders")
 .withColumn("rn",   F.row_number().over(Window.orderBy(F.desc("amount"), "order_id")))
 .withColumn("rnk",  F.rank().over(Window.orderBy(F.desc("amount"))))
 .withColumn("drnk", F.dense_rank().over(Window.orderBy(F.desc("amount"))))
 .select("order_id", "amount", "rn", "rnk", "drnk").orderBy("rn"))
```

Output (SQL, from `ex08_windows.out`, first 10 of 16 rows):
```text
+--------+------+---+---+----+--------+--------+-----+
|order_id|amount|rn |rnk|drnk|quartile|pct_rank|cume |
+--------+------+---+---+----+--------+--------+-----+
|1005    |318.00|2  |1  |1   |1       |0.0     |0.125|
|1015    |318.00|1  |1  |1   |1       |0.0     |0.125|
|1002    |249.00|4  |3  |2   |1       |0.133   |0.25 |
|1012    |249.00|3  |3  |2   |1       |0.133   |0.25 |
|1003    |189.50|7  |5  |3   |2       |0.267   |0.438|
|1010    |189.50|5  |5  |3   |2       |0.267   |0.438|
|1016    |189.50|6  |5  |3   |2       |0.267   |0.438|
|1007    |159.00|9  |8  |4   |3       |0.467   |0.563|
|1014    |159.00|8  |8  |4   |2       |0.467   |0.563|
|1008    |78.00 |10 |10 |5   |3       |0.6     |0.625|
...
```

- `rank` leaves gaps after ties (1, 1, 3, 3, 5); `dense_rank` does not (1, 1, 2, 2, 3). `row_number` never ties, so it must break ties somehow, and the `row_number` page says "If the order is not unique, the result is non-deterministic." Here 1015 got 1 and 1005 got 2. The PySpark version adds `order_id` to the ordering, and there 1005 is 1.
- `ntile(4)` put the two 159.00 orders in **different** quartiles (2 and 3). The `ntile` page: "If the order is non-unique, the result is non-deterministic."
- `percent_rank` is (rank - 1) / (rows - 1); `cume_dist` is the fraction of rows at or before the current one, ties counted together.

A ranking function without `ORDER BY` is an error:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, row_number() OVER (PARTITION BY customer_id) AS rn FROM silver.orders;
```

Output (from `ex08_windows.out`):
```text
ERROR: [WINDOW_FUNCTION_FRAME_NOT_ORDERED] Window function row_number requires the window to be ordered. You need to add an ORDER BY clause. For example: SELECT row_number() OVER (PARTITION BY window_partition ORDER BY window_ordering) FROM table.
```

### Top-N per group

The biggest two orders per customer. `QUALIFY` filters on a window function result ([chapter 17](17-Databricks-SQL-vs-Standard.md)); in PySpark you add the column and filter it.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT customer_id, order_id, amount
FROM silver.orders
QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY amount DESC, order_id) <= 2
ORDER BY customer_id, amount DESC;
```
```python
(spark.table("silver.orders")
 .withColumn("rn", F.row_number().over(
     Window.partitionBy("customer_id").orderBy(F.desc("amount"), "order_id")))
 .where("rn <= 2").select("customer_id", "order_id", "amount")
 .orderBy("customer_id", F.desc("amount")))
```

Output (SQL and PySpark agree, from `ex08_windows.out`):
```text
+-----------+--------+------+
|customer_id|order_id|amount|
+-----------+--------+------+
|1          |1003    |189.50|
|1          |1014    |159.00|
|2          |1015    |318.00|
|2          |1002    |249.00|
|3          |1007    |159.00|
|3          |1013    |59.90 |
|4          |1005    |318.00|
|4          |1012    |249.00|
+-----------+--------+------+
```

Which ranking function? `row_number` for "exactly N rows", `rank` for "top N including everyone tied with the N-th", `dense_rank` for "the top N distinct values".

### lag and lead

`lag(expr [, offset [, default]])` returns a value from a preceding row; `lead` from a following row. Both accept `IGNORE NULLS`, and the `lag` page says "If there is no row at the specified offset within the partition, the specified `default` is used. The `default` default is `NULL`. You must provide an ORDER BY clause."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT customer_id, order_id, order_ts, amount,
       lag(amount)          OVER w AS prev_amount,
       lag(amount, 1, 0)    OVER w AS prev_or_zero,
       lead(order_ts)       OVER w AS next_ts,
       amount - lag(amount) OVER w AS change,
       timestampdiff(HOUR, lag(order_ts) OVER w, order_ts) AS hours_since_prev
FROM silver.orders
WHERE customer_id IN (1, 4)
WINDOW w AS (PARTITION BY customer_id ORDER BY order_ts)
ORDER BY customer_id, order_ts;
```
```python
w = Window.partitionBy("customer_id").orderBy("order_ts")
(spark.table("silver.orders").where("customer_id = 1")
 .withColumn("prev_amount", F.lag("amount").over(w))
 .withColumn("prev_or_zero", F.lag("amount", 1, 0).over(w))
 .select("order_id", "amount", "prev_amount", "prev_or_zero").orderBy("order_id"))
```

Output (SQL, from `ex08_windows.out`, customer 1):
```text
+-----------+--------+-------------------+------+-----------+------------+-------------------+-------+----------------+
|customer_id|order_id|order_ts           |amount|prev_amount|prev_or_zero|next_ts            |change |hours_since_prev|
+-----------+--------+-------------------+------+-----------+------------+-------------------+-------+----------------+
|1          |1001    |2026-03-01 10:15:00|59.90 |NULL       |0.00        |2026-03-02 09:40:00|NULL   |NULL            |
|1          |1003    |2026-03-02 09:40:00|189.50|59.90      |59.90       |2026-03-04 19:10:00|129.60 |23              |
|1          |1008    |2026-03-04 19:10:00|78.00 |189.50     |189.50      |2026-03-04 19:25:00|-111.50|57              |
|1          |1009    |2026-03-04 19:25:00|39.00 |78.00      |78.00       |2026-04-01 03:20:00|-39.00 |0               |
|1          |1014    |2026-04-01 03:20:00|159.00|39.00      |39.00       |NULL               |120.00 |655             |
...
```

The first row of each partition has no previous row, so `prev_amount` is `NULL` and `change` is `NULL`; the `default` argument (`0`) fills only the `lag` value. `timestampdiff(HOUR, ...)` counts whole hours, so 15 minutes is 0.

### Frames: ROWS, RANGE and the default

An aggregate used as a window function works on a **frame**: a subset of the partition around the current row. The [Window frame clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-window-functions-frame) page defines two modes:

- `ROWS`: "the sliding window frame is expressed in terms of rows preceding or following the current row". Physical positions.
- `RANGE`: the window "must specify an ORDER BY clause with a single expression `obExpr`. The boundaries of the sliding window are then expressed as an offset from the `obExpr` for the current row." Logical values: every row whose `ORDER BY` value is in range, including all rows tied with the current one.

Bounds are `UNBOUNDED PRECEDING`, `n PRECEDING`, `CURRENT ROW`, `n FOLLOWING` and `UNBOUNDED FOLLOWING`; when only a start is given, "the frame stops at the CURRENT ROW".

**The default frame** is not stated on the SQL pages. The Databricks [PySpark `Window` class](https://docs.databricks.com/aws/en/pyspark/reference/classes/window) page states it: "When ordering is not defined, an unbounded window frame (rowFrame, unboundedPreceding, unboundedFollowing) is used by default. When ordering is defined, a growing window frame (rangeFrame, unboundedPreceding, currentRow) is used by default." So `sum(x) OVER (ORDER BY d)` means `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, and every row tied on `d` gets the same running total.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 430" role="img" aria-label="Eleven orders sorted by order date. For the current row, order 1011 on March 4, the ROWS frame covers rows 1 to 8 and sums to 954.30. The RANGE frame covers every row dated on or before March 4, rows 1 to 10, and sums to 1191.30, because the four March 4 orders are tied.">
<text x="20" y="22" font-size="14" fill="currentColor">sum(amount), ordered by order date, UNBOUNDED PRECEDING AND CURRENT ROW</text>
<g font-size="13" fill="currentColor">
<text x="44" y="42">#</text><text x="74" y="42">date</text><text x="174" y="42">order</text><text x="268" y="42" text-anchor="end">amount</text>
<text x="44" y="64">1</text><text x="74" y="64">2026-03-01</text><text x="174" y="64">1001</text><text x="268" y="64" text-anchor="end">59.90</text>
<text x="44" y="90">2</text><text x="74" y="90">2026-03-01</text><text x="174" y="90">1002</text><text x="268" y="90" text-anchor="end">249.00</text>
<text x="44" y="116">3</text><text x="74" y="116">2026-03-02</text><text x="174" y="116">1003</text><text x="268" y="116" text-anchor="end">189.50</text>
<text x="44" y="142">4</text><text x="74" y="142">2026-03-02</text><text x="174" y="142">1004</text><text x="268" y="142" text-anchor="end">39.00</text>
<text x="44" y="168">5</text><text x="74" y="168">2026-03-03</text><text x="174" y="168">1005</text><text x="268" y="168" text-anchor="end">318.00</text>
<text x="44" y="194">6</text><text x="74" y="194">2026-03-03</text><text x="174" y="194">1006</text><text x="268" y="194" text-anchor="end">29.95</text>
<text x="44" y="220">7</text><text x="74" y="220">2026-03-04</text><text x="174" y="220">1009</text><text x="268" y="220" text-anchor="end">39.00</text>
<text x="44" y="246">8</text><text x="74" y="246">2026-03-04</text><text x="174" y="246">1011</text><text x="268" y="246" text-anchor="end">29.95</text>
<text x="44" y="272">9</text><text x="74" y="272">2026-03-04</text><text x="174" y="272">1007</text><text x="268" y="272" text-anchor="end">159.00</text>
<text x="44" y="298">10</text><text x="74" y="298">2026-03-04</text><text x="174" y="298">1008</text><text x="268" y="298" text-anchor="end">78.00</text>
<text x="44" y="324">11</text><text x="74" y="324">2026-03-05</text><text x="174" y="324">1012</text><text x="268" y="324" text-anchor="end">249.00</text>
</g>
<rect x="36" y="229" width="240" height="24" fill="none" stroke="currentColor" stroke-width="2"/>
<text x="18" y="246" font-size="13" fill="currentColor">&#9654;</text>
<rect x="30" y="203" width="252" height="102" fill="none" stroke="currentColor" stroke-dasharray="5 4"/>
<line x1="320" y1="50" x2="320" y2="253" stroke="currentColor" stroke-width="2"/>
<line x1="312" y1="50" x2="320" y2="50" stroke="currentColor" stroke-width="2"/>
<line x1="312" y1="253" x2="320" y2="253" stroke="currentColor" stroke-width="2"/>
<text x="330" y="140" font-size="14" fill="currentColor">ROWS frame</text>
<text x="330" y="158" font-size="13" fill="currentColor">rows 1 to 8</text>
<text x="330" y="176" font-size="13" fill="currentColor">sum = 954.30</text>
<line x1="460" y1="50" x2="460" y2="305" stroke="currentColor" stroke-width="2" stroke-dasharray="8 3"/>
<line x1="452" y1="50" x2="460" y2="50" stroke="currentColor" stroke-width="2"/>
<line x1="452" y1="305" x2="460" y2="305" stroke="currentColor" stroke-width="2"/>
<text x="470" y="200" font-size="14" fill="currentColor">RANGE frame</text>
<text x="470" y="218" font-size="13" fill="currentColor">date &lt;= 2026-03-04</text>
<text x="470" y="236" font-size="13" fill="currentColor">rows 1 to 10</text>
<text x="470" y="254" font-size="13" fill="currentColor">sum = 1191.30</text>
<text x="20" y="356" font-size="13" fill="currentColor">Arrow: the current row, order 1011. Dashed box: the four rows tied on 2026-03-04.</text>
<text x="20" y="378" font-size="13" fill="currentColor">ROWS stops at the current row's position; RANGE also takes every tied row.</text>
<text x="20" y="400" font-size="13" fill="currentColor">With ORDER BY and no frame, the default is RANGE, so a running total</text>
<text x="20" y="422" font-size="13" fill="currentColor">over a non-unique key jumps by whole tie groups.</text>
</svg>
<figcaption>Figure 19.2. The same frame bounds in ROWS and RANGE mode, for one current row inside a group of four tied dates. Values from ex08_windows.out.</figcaption>
</figure>

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT CAST(order_ts AS DATE) AS d, order_id, amount,
       sum(amount) OVER (ORDER BY CAST(order_ts AS DATE)
                         ROWS  BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS rows_total,
       sum(amount) OVER (ORDER BY CAST(order_ts AS DATE)
                         RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS range_total,
       sum(amount) OVER (ORDER BY CAST(order_ts AS DATE))                    AS default_frame_total
FROM silver.orders WHERE order_ts < TIMESTAMP'2026-03-06' ORDER BY d, order_id;
```

Output (from `ex08_windows.out`):
```text
+----------+--------+------+----------+-----------+-------------------+
|d         |order_id|amount|rows_total|range_total|default_frame_total|
+----------+--------+------+----------+-----------+-------------------+
|2026-03-01|1001    |59.90 |59.90     |308.90     |308.90             |
|2026-03-01|1002    |249.00|308.90    |308.90     |308.90             |
|2026-03-02|1003    |189.50|498.40    |537.40     |537.40             |
|2026-03-02|1004    |39.00 |537.40    |537.40     |537.40             |
|2026-03-03|1005    |318.00|855.40    |885.35     |885.35             |
|2026-03-03|1006    |29.95 |885.35    |885.35     |885.35             |
|2026-03-04|1007    |159.00|1113.30   |1191.30    |1191.30            |
|2026-03-04|1008    |78.00 |1191.30   |1191.30    |1191.30            |
|2026-03-04|1009    |39.00 |924.35    |1191.30    |1191.30            |
|2026-03-04|1011    |29.95 |954.30    |1191.30    |1191.30            |
|2026-03-05|1012    |249.00|1440.30   |1440.30    |1440.30            |
+----------+--------+------+----------+-----------+-------------------+
```

Three lessons in one table:

1. The default frame equals `RANGE`: `default_frame_total` matches `range_total` on every row.
2. `RANGE` gives each tie group one value (the total at the end of the day).
3. `ROWS` gave a different total to each 2026-03-04 row, and the order **within** the day was arbitrary: the engine processed 1009, 1011, 1007, 1008 (look at the running values), not the order the result is printed in. A `ROWS` running total over a non-unique key is non-deterministic. Make the `ORDER BY` unique (`ORDER BY order_ts, order_id`) and write the frame explicitly.

### Running totals, moving averages and shares

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, order_ts, amount,
       sum(amount) OVER (ORDER BY order_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
       round(avg(amount) OVER (ORDER BY order_ts ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS moving_avg_3,
       sum(amount) OVER (PARTITION BY date_trunc('MONTH', order_ts) ORDER BY order_ts
                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS month_to_date,
       round(100 * amount / sum(amount) OVER (), 1) AS pct_of_total
FROM silver.orders ORDER BY order_ts;
```
```python
(spark.table("silver.orders")
 .withColumn("running_total", F.sum("amount").over(
     Window.orderBy("order_ts").rowsBetween(Window.unboundedPreceding, Window.currentRow)))
 .withColumn("moving_avg_3", F.round(F.avg("amount").over(
     Window.orderBy("order_ts").rowsBetween(-2, 0)), 2))
 .select("order_id", "amount", "running_total", "moving_avg_3").orderBy("order_ts"))
```

Output (from `ex08_windows.out`, rows around the month change):
```text
+--------+-------------------+------+-------------+------------+-------------+------------+
|order_id|order_ts           |amount|running_total|moving_avg_3|month_to_date|pct_of_total|
+--------+-------------------+------+-------------+------------+-------------+------------+
|1001    |2026-03-01 10:15:00|59.90 |59.90        |59.90       |59.90        |2.5         |
|1002    |2026-03-01 11:05:00|249.00|308.90       |154.45      |308.90       |10.6        |
|1003    |2026-03-02 09:40:00|189.50|498.40       |166.13      |498.40       |8.0         |
...
|1013    |2026-03-15 13:10:00|59.90 |1689.70      |166.13      |1689.70      |2.5         |
|1014    |2026-04-01 03:20:00|159.00|1848.70      |136.13      |159.00       |6.7         |
|1015    |2026-04-02 08:00:00|318.00|2166.70      |178.97      |477.00       |13.5        |
|1016    |2026-04-06 11:15:00|189.50|2356.20      |222.17      |666.50       |8.0         |
+--------+-------------------+------+-------------+------------+-------------+------------+
```

The PySpark columns match the first five SQL rows. Notes:

- `rowsBetween(-2, 0)` in PySpark is `ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`; `Window.unboundedPreceding` and `Window.currentRow` are the named bounds.
- In the first two rows the 3-row moving average covers fewer than three values (59.90, then 154.45). If the report needs `NULL` until there are three values, add `CASE WHEN count(*) OVER (same window) = 3 THEN ... END`.
- A running total that resets each month is a `PARTITION BY date_trunc('MONTH', ...)`: `month_to_date` restarts at order 1014.
- `sum(amount) OVER ()` (empty window: all rows, no order) gives the grand total on every row, so a share of total needs no join.

### RANGE with an interval: "the last 48 hours"

With `RANGE`, the offset is a value of the `ORDER BY` type. For a timestamp it is an interval, so the frame is "every order in the 48 hours up to this one", however many rows that is:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, order_ts, amount,
       sum(amount) OVER (ORDER BY order_ts RANGE BETWEEN INTERVAL 48 HOURS PRECEDING AND CURRENT ROW) AS last_48h,
       count(*)    OVER (ORDER BY order_ts RANGE BETWEEN INTERVAL 48 HOURS PRECEDING AND CURRENT ROW) AS n_48h
FROM silver.orders WHERE order_ts < TIMESTAMP'2026-03-08' ORDER BY order_ts;
SELECT order_id, sum(amount) OVER (ORDER BY order_ts, order_id RANGE BETWEEN 1 PRECEDING AND CURRENT ROW) AS x
FROM silver.orders;
```
```python
(spark.table("silver.orders").where("order_ts < '2026-03-08'")
 .withColumn("epoch", F.unix_timestamp("order_ts"))
 .withColumn("last_48h", F.sum("amount").over(Window.orderBy("epoch").rangeBetween(-48 * 3600, 0)))
 .select("order_id", "order_ts", "amount", "last_48h").orderBy("order_ts"))
```

Output (from `ex08_windows.out`, trimmed; PySpark `last_48h` is identical):
```text
+--------+-------------------+------+--------+-----+
|order_id|order_ts           |amount|last_48h|n_48h|
+--------+-------------------+------+--------+-----+
|1001    |2026-03-01 10:15:00|59.90 |59.90   |1    |
|1002    |2026-03-01 11:05:00|249.00|308.90  |2    |
|1003    |2026-03-02 09:40:00|189.50|498.40  |3    |
|1004    |2026-03-02 14:20:00|39.00 |537.40  |4    |
|1005    |2026-03-03 08:55:00|318.00|855.40  |5    |
|1006    |2026-03-03 17:30:00|29.95 |576.45  |4    |
...
|1012    |2026-03-05 16:45:00|249.00|584.90  |6    |
|1010    |2026-03-07 10:00:00|189.50|438.50  |2    |
+--------+-------------------+------+--------+-----+
ERROR: [DATATYPE_MISMATCH.RANGE_FRAME_MULTI_ORDER] Cannot resolve "(ORDER BY order_ts ASC NULLS FIRST, order_id ASC NULLS FIRST RANGE BETWEEN 1 PRECEDING AND CURRENT ROW)" due to data type mismatch: A range window frame with value boundaries canno...
```

At order 1006 (2026-03-03 17:30) the window starts at 2026-03-01 17:30, so orders 1001 and 1002 dropped out. In PySpark, `rangeBetween` takes numbers, so order by epoch seconds (`F.unix_timestamp`) and give the bounds in seconds. A `RANGE` frame with offsets accepts only one `ORDER BY` expression, which is the `RANGE_FRAME_MULTI_ORDER` error above.

### The last_value trap

`first_value` with the default frame works as expected. `last_value` does not: the default frame ends at the current row (and its ties), so the "last value" is the current row's own value.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT customer_id, order_id, order_ts,
       first_value(order_id) OVER (PARTITION BY customer_id ORDER BY order_ts) AS first_order,
       last_value(order_id)  OVER (PARTITION BY customer_id ORDER BY order_ts) AS last_value_default,
       last_value(order_id)  OVER (PARTITION BY customer_id ORDER BY order_ts
                                   ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_value_full,
       max(order_ts) OVER (PARTITION BY customer_id) AS last_ts_no_order
FROM silver.orders WHERE customer_id = 1 ORDER BY order_ts;
```
```python
w = Window.partitionBy("customer_id").orderBy("order_ts")
(spark.table("silver.orders").where("customer_id = 1")
 .withColumn("last_value_default", F.last("order_id").over(w))
 .withColumn("last_value_full", F.last("order_id").over(
     w.rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)))
 .select("order_id", "last_value_default", "last_value_full").orderBy("order_ts"))
```

Output (SQL and PySpark agree, from `ex08_windows.out`):
```text
+-----------+--------+-------------------+-----------+------------------+---------------+-------------------+
|customer_id|order_id|order_ts           |first_order|last_value_default|last_value_full|last_ts_no_order   |
+-----------+--------+-------------------+-----------+------------------+---------------+-------------------+
|1          |1001    |2026-03-01 10:15:00|1001       |1001              |1014           |2026-04-01 03:20:00|
|1          |1003    |2026-03-02 09:40:00|1001       |1003              |1014           |2026-04-01 03:20:00|
|1          |1008    |2026-03-04 19:10:00|1001       |1008              |1014           |2026-04-01 03:20:00|
|1          |1009    |2026-03-04 19:25:00|1001       |1009              |1014           |2026-04-01 03:20:00|
|1          |1014    |2026-04-01 03:20:00|1001       |1014              |1014           |2026-04-01 03:20:00|
+-----------+--------+-------------------+-----------+------------------+---------------+-------------------+
```

Two fixes: write the full frame (`ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`), or flip the order and use `first_value(...) OVER (... ORDER BY order_ts DESC)`. An aggregate with no `ORDER BY` in its window (`max(order_ts) OVER (PARTITION BY customer_id)`) uses the whole partition.

### IGNORE NULLS: carry the last known value forward

`first_value`, `last_value`, `lag`, `lead` and `nth_value` accept `IGNORE NULLS`. With a frame that ends at the current row, `last_value(x) IGNORE NULLS` is a **forward fill**: each row gets the most recent non-`NULL` value. Order 1008 has no status:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, order_ts, status,
       last_value(status) IGNORE NULLS OVER (PARTITION BY customer_id ORDER BY order_ts
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)            AS status_filled,
       lag(status)              OVER (PARTITION BY customer_id ORDER BY order_ts) AS prev_status,
       lag(status) IGNORE NULLS OVER (PARTITION BY customer_id ORDER BY order_ts) AS prev_non_null_status,
       nth_value(order_id, 2)   OVER (PARTITION BY customer_id ORDER BY order_ts
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)    AS second_order
FROM silver.orders WHERE customer_id = 1 ORDER BY order_ts;
```
```python
(spark.table("silver.orders").where("customer_id = 1")
 .withColumn("status_filled", F.last("status", ignorenulls=True).over(
     Window.partitionBy("customer_id").orderBy("order_ts").rowsBetween(Window.unboundedPreceding, 0)))
 .select("order_id", "status", "status_filled").orderBy("order_ts"))
```

Output (from `ex08_windows.out`; PySpark `status_filled` is the same):
```text
+--------+-------------------+-------+-------------+-----------+--------------------+------------+
|order_id|order_ts           |status |status_filled|prev_status|prev_non_null_status|second_order|
+--------+-------------------+-------+-------------+-----------+--------------------+------------+
|1001    |2026-03-01 10:15:00|SHIPPED|SHIPPED      |NULL       |NULL                |1003        |
|1003    |2026-03-02 09:40:00|PLACED |PLACED       |SHIPPED    |SHIPPED             |1003        |
|1008    |2026-03-04 19:10:00|NULL   |PLACED       |PLACED     |PLACED              |1003        |
|1009    |2026-03-04 19:25:00|SHIPPED|SHIPPED      |NULL       |PLACED              |1003        |
|1014    |2026-04-01 03:20:00|PLACED |PLACED       |SHIPPED    |SHIPPED             |1003        |
+--------+-------------------+-------+-------------+-----------+--------------------+------------+
```

Order 1008 inherits PLACED. For order 1009, plain `lag` returns 1008's `NULL`, while `lag ... IGNORE NULLS` skips it and returns PLACED. `nth_value(order_id, 2)` returns "the value of `expr` at the row that is the `offset`th row from the beginning of the window frame", so with the full frame every row sees the second order. Forward fill is the standard way to repair sparse CDC or sensor feeds in silver.

### The WINDOW clause and other details

The [WINDOW clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-named-window) "defines and names one or more distinct window specifications once so you can share them across many window functions in the same query". It removes copy-paste errors when five columns use the same window:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, customer_id, amount,
       sum(amount) OVER by_cust                     AS cust_total,
       count(*)    OVER by_cust                     AS cust_orders,
       round(amount / sum(amount) OVER by_cust, 3)  AS share_of_customer,
       rank()      OVER by_cust_amt                 AS rank_in_customer
FROM silver.orders
WHERE customer_id IN (2, 3)
WINDOW by_cust     AS (PARTITION BY customer_id),
       by_cust_amt AS (PARTITION BY customer_id ORDER BY amount DESC)
ORDER BY customer_id, rank_in_customer;
```

Output (from `ex08_windows.out`):
```text
+--------+-----------+------+----------+-----------+-----------------+----------------+
|order_id|customer_id|amount|cust_total|cust_orders|share_of_customer|rank_in_customer|
+--------+-----------+------+----------+-----------+-----------------+----------------+
|1015    |2          |318.00|786.45    |4          |0.404            |1               |
|1002    |2          |249.00|786.45    |4          |0.317            |2               |
|1010    |2          |189.50|786.45    |4          |0.241            |3               |
|1006    |2          |29.95 |786.45    |4          |0.038            |4               |
|1007    |3          |159.00|257.90    |3          |0.617            |1               |
|1013    |3          |59.90 |257.90    |3          |0.232            |2               |
|1004    |3          |39.00 |257.90    |3          |0.151            |3               |
+--------+-----------+------+----------+-----------+-----------------+----------------+
```

In PySpark the equivalent is a Python variable holding a `Window` spec, reused in each `.over(w)`.

Four more behaviors, all run here:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, sum(amount) FILTER (WHERE status = 'SHIPPED') OVER (PARTITION BY customer_id) AS x FROM silver.orders;
SELECT order_id, count(DISTINCT status) OVER (PARTITION BY customer_id) AS x FROM silver.orders;
SELECT customer_id, order_id, size(collect_set(status) OVER (PARTITION BY customer_id)) AS distinct_statuses
FROM silver.orders WHERE customer_id = 4 ORDER BY order_id;
SELECT order_id FROM silver.orders WHERE row_number() OVER (ORDER BY amount) = 1;
```

Output (from `ex08_windows.out`, trimmed):
```text
(FILTER in a window: ran; customer 1 rows show 98.90, customer 2 rows 756.50, ...)
ERROR: [DISTINCT_WINDOW_FUNCTION_UNSUPPORTED] Distinct window functions are not supported: "count(DISTINCT status) OVER (PARTITION BY customer_id ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)". SQLSTATE: 0A000
+-----------+--------+-----------------+
|customer_id|order_id|distinct_statuses|
+-----------+--------+-----------------+
|4          |1005    |3                |
|4          |1011    |3                |
|4          |1012    |3                |
|4          |1016    |3                |
+-----------+--------+-----------------+
ERROR: [WINDOW_FUNCTION_NOT_ALLOWED_IN_CLAUSE] It is not allowed to use window functions inside WHERE clause. SQLSTATE: 42601
```

- **FILTER inside a window**: the Window functions page says an aggregate used as a window function "must not include a FILTER clause". Apache Spark 4.2 accepted it. Whether Databricks rejects it was not tested (not verified); for code that runs on Databricks, write `sum(CASE WHEN status = 'SHIPPED' THEN amount END) OVER (...)`.
- **`count(DISTINCT ...) OVER`** is not supported (the page lists `DISTINCT_WINDOW_FUNCTION_UNSUPPORTED`). `size(collect_set(x) OVER (...))` is the usual workaround. Note also the frame Spark printed in the error: with no `ORDER BY`, the whole partition (`ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`).
- **Window functions in `WHERE`** fail, because `WHERE` runs before windows are computed. Use `QUALIFY`, or compute the window in a subquery and filter outside (practice question 41).

!!! tip "In the interview"
    **"Your running total jumps by the same amount for several rows. Why?"** The `ORDER BY` key has ties and the window has no frame, so the default frame is `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, which includes every row tied with the current one. Make the order unique (`ORDER BY order_ts, order_id`) and write `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`. The same default frame explains why `last_value` returns the current row. Interviewers like this question because the query "works" and the numbers are wrong.

## 19.10 Classic window patterns
*Level: expert.*

These six patterns cover most window-function questions in data engineering interviews. Each is a few lines once you know the trick. The examples use `silver.orders` and a small bronze change feed, `bronze.order_updates`, with several versions of the same order as a CDC feed or a re-delivered file would give:

```text
order_id  status     updated_at
1003      PLACED     2026-03-02 09:40:00
1003      PAID       2026-03-02 09:41:00
1003      SHIPPED    2026-03-03 15:00:00
1003      SHIPPED    2026-03-03 15:00:00   (exact duplicate)
1006      PLACED     2026-03-03 17:30:00
1006      PLACED     2026-03-03 18:00:00   (same status, later)
1006      CANCELLED  2026-03-04 08:00:00
```

### 1. Latest row per key (deduplication)

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, status, updated_at
FROM bronze.order_updates
QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY updated_at DESC) = 1
ORDER BY order_id;

SELECT order_id, max_by(status, updated_at) AS status, max(updated_at) AS updated_at
FROM bronze.order_updates GROUP BY order_id ORDER BY order_id;
```
```python
(spark.table("bronze.order_updates")
 .withColumn("rn", F.row_number().over(Window.partitionBy("order_id").orderBy(F.desc("updated_at"))))
 .where("rn = 1").drop("rn").orderBy("order_id"))
```

Output (all three agree, from `ex09_patterns.out`):
```text
+--------+---------+-------------------+
|order_id|status   |updated_at         |
+--------+---------+-------------------+
|1003    |SHIPPED  |2026-03-03 15:00:00|
|1006    |CANCELLED|2026-03-04 08:00:00|
+--------+---------+-------------------+
```

`row_number` (not `rank`) guarantees exactly one row even with the exact duplicate of 1003. This is the step before a `MERGE` into silver, because `MERGE` fails when several source rows match one target row ([chapter 9](09-Building-Silver.md)). Add a tiebreaker (a sequence number or file name) to the `ORDER BY` when two versions can share a timestamp.

### 2. Change detection: keep only rows where the value changed

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, status, updated_at
FROM bronze.order_updates
QUALIFY lag(status) OVER (PARTITION BY order_id ORDER BY updated_at) IS DISTINCT FROM status
ORDER BY order_id, updated_at;
```

Output (from `ex09_patterns.out`):
```text
+--------+---------+-------------------+
|order_id|status   |updated_at         |
+--------+---------+-------------------+
|1003    |PLACED   |2026-03-02 09:40:00|
|1003    |PAID     |2026-03-02 09:41:00|
|1003    |SHIPPED  |2026-03-03 15:00:00|
|1006    |PLACED   |2026-03-03 17:30:00|
|1006    |CANCELLED|2026-03-04 08:00:00|
+--------+---------+-------------------+
```

`IS DISTINCT FROM` treats the first row's `NULL` from `lag` as "changed", so no `OR prev IS NULL` is needed (the script also shows the longer subquery version with `prev_status IS NULL OR status <> prev_status`; same five rows). This turns a noisy feed into a status history, the input of an SCD type 2 table.

### 3. Gaps and islands: runs of consecutive days

"Find each customer's streaks of consecutive order days." The trick: within a run of consecutive dates, `date - row_number()` is constant. Subtracting the row number from each date gives the same "island key" for every day of a streak.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
WITH days AS (
  SELECT DISTINCT customer_id, CAST(order_ts AS DATE) AS d FROM silver.orders
), grp AS (
  SELECT customer_id, d,
         date_sub(d, CAST(row_number() OVER (PARTITION BY customer_id ORDER BY d) AS INT)) AS island_key
  FROM days
)
SELECT customer_id, min(d) AS streak_start, max(d) AS streak_end, count(*) AS days_in_a_row
FROM grp GROUP BY customer_id, island_key
ORDER BY customer_id, streak_start;
```
```python
(spark.table("silver.orders")
 .select("customer_id", F.to_date("order_ts").alias("d")).distinct()
 .withColumn("island_key", F.date_sub("d", F.row_number().over(
     Window.partitionBy("customer_id").orderBy("d"))))
 .groupBy("customer_id", "island_key")
 .agg(F.min("d").alias("streak_start"), F.max("d").alias("streak_end"), F.count("*").alias("days_in_a_row"))
 .drop("island_key").orderBy("customer_id", "streak_start"))
```

Output (SQL and PySpark agree, from `ex09_patterns.out`, trimmed):
```text
+-----------+------------+----------+-------------+
|customer_id|streak_start|streak_end|days_in_a_row|
+-----------+------------+----------+-------------+
|1          |2026-03-01  |2026-03-02|2            |
|1          |2026-03-04  |2026-03-04|1            |
|1          |2026-04-01  |2026-04-01|1            |
|2          |2026-03-01  |2026-03-01|1            |
...
|4          |2026-03-03  |2026-03-05|3            |
|4          |2026-04-06  |2026-04-06|1            |
+-----------+------------+----------+-------------+
```

Customer 4 ordered on March 3, 4 and 5: row numbers 1, 2, 3, so `d - rn` is March 2 for all three. The `DISTINCT` matters: two orders on one day would otherwise break the arithmetic. The same trick works on integers (`id - row_number()`) to find runs of consecutive ids, or missing ranges in a sequence.

### 4. Sessionization: a new session after 30 minutes of inactivity

"Group each customer's orders into sessions; a gap of more than 30 minutes starts a new session." Two steps: flag the rows that start a session with `lag`, then number the sessions with a running `sum` of the flag.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
WITH flagged AS (
  SELECT customer_id, order_id, order_ts,
         CASE WHEN lag(order_ts) OVER (PARTITION BY customer_id ORDER BY order_ts) IS NULL
                OR order_ts > lag(order_ts) OVER (PARTITION BY customer_id ORDER BY order_ts) + INTERVAL 30 MINUTES
              THEN 1 ELSE 0 END AS new_session
  FROM silver.orders
)
SELECT customer_id, order_id, order_ts, new_session,
       sum(new_session) OVER (PARTITION BY customer_id ORDER BY order_ts
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS session_no
FROM flagged WHERE customer_id = 1 ORDER BY order_ts;
```
```python
w = Window.partitionBy("customer_id").orderBy("order_ts")
(spark.table("silver.orders").where("customer_id = 1")
 .withColumn("prev_ts", F.lag("order_ts").over(w))
 .withColumn("new_session", F.when(F.col("prev_ts").isNull() |
             (F.col("order_ts") > F.col("prev_ts") + F.expr("INTERVAL 30 MINUTES")), 1).otherwise(0))
 .withColumn("session_no", F.sum("new_session").over(w.rowsBetween(Window.unboundedPreceding, 0)))
 .select("order_id", "order_ts", "new_session", "session_no").orderBy("order_ts"))
```

Output (SQL and PySpark agree, from `ex09_patterns.out`):
```text
+-----------+--------+-------------------+-----------+----------+
|customer_id|order_id|order_ts           |new_session|session_no|
+-----------+--------+-------------------+-----------+----------+
|1          |1001    |2026-03-01 10:15:00|1          |1         |
|1          |1003    |2026-03-02 09:40:00|1          |2         |
|1          |1008    |2026-03-04 19:10:00|1          |3         |
|1          |1009    |2026-03-04 19:25:00|0          |3         |
|1          |1014    |2026-04-01 03:20:00|1          |4         |
+-----------+--------+-------------------+-----------+----------+
```

Orders 1008 and 1009, fifteen minutes apart, share session 3. For a batch `GROUP BY`, Spark also has a built-in `session_window(expr, gapDuration)` grouping expression (Applies to: Databricks SQL Databricks Runtime 10.4 LTS and above), which returns a `STRUCT<start, end>` per session:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT customer_id, session_window.start AS s_start, session_window.end AS s_end, count(*) AS orders
FROM silver.orders WHERE customer_id = 1
GROUP BY customer_id, session_window(order_ts, '30 minutes')
ORDER BY s_start;
```

Output (from `ex09_patterns.out`):
```text
+-----------+-------------------+-------------------+------+
|customer_id|s_start            |s_end              |orders|
+-----------+-------------------+-------------------+------+
|1          |2026-03-01 10:15:00|2026-03-01 10:45:00|1     |
|1          |2026-03-02 09:40:00|2026-03-02 10:10:00|1     |
|1          |2026-03-04 19:10:00|2026-03-04 19:55:00|2     |
|1          |2026-04-01 03:20:00|2026-04-01 03:50:00|1     |
+-----------+-------------------+-------------------+------+
```

The session end is the last event plus the gap (19:25 + 30 minutes = 19:55). Streaming windows are covered in [chapter 11](11-Structured-Streaming.md). In a batch interview question, the `lag` + running-sum version is the one interviewers expect you to write by hand, because it shows you understand the logic.

### 5. Month over month

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
WITH monthly AS (
  SELECT date_trunc('MONTH', order_ts) AS month, sum(amount) AS revenue
  FROM silver.orders WHERE status <> 'CANCELLED' OR status IS NULL GROUP BY ALL
)
SELECT month, revenue,
       lag(revenue) OVER (ORDER BY month) AS prev_month,
       round(100 * (revenue - lag(revenue) OVER (ORDER BY month)) / lag(revenue) OVER (ORDER BY month), 1) AS pct_change
FROM monthly ORDER BY month;
```

Output (from `ex09_patterns.out`):
```text
+-------------------+-------+----------+----------+
|month              |revenue|prev_month|pct_change|
+-------------------+-------+----------+----------+
|2026-03-01 00:00:00|1650.70|NULL      |NULL      |
|2026-04-01 00:00:00|477.00 |1650.70   |-71.1     |
+-------------------+-------+----------+----------+
```

Window functions run after `GROUP BY`, so aggregate first (in a CTE or in the same `SELECT`) and then compare rows. `lag` compares with the previous **row**, not the previous calendar month: if a month has no orders, it is missing from `monthly` and the comparison jumps two months. Build a calendar of months and `LEFT JOIN` to it when gaps are possible (practice question 37 shows the same problem with days).

### 6. Time since the previous event

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT customer_id, order_id, CAST(order_ts AS DATE) AS d,
       datediff(order_ts, lag(order_ts) OVER (PARTITION BY customer_id ORDER BY order_ts)) AS days_since_prev
FROM silver.orders
QUALIFY days_since_prev > 14
ORDER BY customer_id;
```

Output (from `ex09_patterns.out`):
```text
+-----------+--------+----------+---------------+
|customer_id|order_id|d         |days_since_prev|
+-----------+--------+----------+---------------+
|1          |1014    |2026-04-01|28             |
|2          |1015    |2026-04-02|26             |
|4          |1016    |2026-04-06|32             |
+-----------+--------+----------+---------------+
```

`QUALIFY` can refer to the `days_since_prev` alias. Customer 3 never had a gap over 14 days (their orders are on March 2, 4 and 15). This is the core of churn and "reactivated customer" flags.

!!! tip "In the interview"
    **"Find users' sessions"** and **"find consecutive login days"** are the two most common live-coding window questions. Say the trick before you type: for sessions, "flag a new session when the gap from `lag` exceeds the timeout, then a running `sum` of the flag is the session number"; for streaks, "`date - row_number()` is constant inside a streak, so group by it". Then mention the edge cases: duplicates on the same day (use `DISTINCT` or `dense_rank`), ties on the timestamp (add a tiebreaker), and the time zone used to define a "day".

## 19.11 Hashing and ids
*Level: intermediate.*

**The problem.** Three common tasks need a hash or a generated id: detecting which customer rows changed since the last load (a row hash for SCD type 2), spreading keys into a fixed number of buckets, and giving rows a key when the source has none.

### The hash functions

| Function | Returns | Use it for |
| --- | --- | --- |
| `md5(expr)` | "an MD5 128-bit checksum of `expr` as a hex string" | row hashes where a 32-character string is fine |
| `sha2(expr, bitLength)` | "a checksum of the `SHA-2` family as a hex string"; "`bitLength` can be 0, `224`, `256`, `384`, or `512`. `bitLength` 0 is equivalent to `256`." | row hashes, pseudonymizing an email for joins across tables |
| `hash(expr1, ...)` | an `INTEGER` | bucketing, quick partitioning; 32 bits collide often on large tables |
| `xxhash64(expr1, ...)` | "a 64-bit hash value", a `BIGINT` | a compact numeric row hash, bucketing |

All four say "Applies to: Databricks SQL Databricks Runtime". The `hash` and `xxhash64` pages add a note (wording from the `hash` page): "The hash value depends on the input data type. For example, `hash(1::INT)` produces a different result than `hash(1::BIGINT)`."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT md5('ana@example.com')              AS md5_hex,
       sha2('ana@example.com', 256)        AS sha256_hex,
       length(sha2('ana@example.com', 256)) AS sha256_len,
       hash('ana@example.com')             AS hash_int,
       xxhash64('ana@example.com')         AS xxhash_bigint,
       typeof(hash('x')) AS t_hash, typeof(xxhash64('x')) AS t_xx;
SELECT hash(1) AS h_int, hash(CAST(1 AS BIGINT)) AS h_bigint, xxhash64(1) AS x_int, xxhash64(1L) AS x_bigint;
```

Output (from `ex10_hash_ids.out`):
```text
+--------------------------------+----------------------------------------------------------------+----------+----------+--------------------+------+------+
|md5_hex                         |sha256_hex                                                      |sha256_len|hash_int  |xxhash_bigint       |t_hash|t_xx  |
+--------------------------------+----------------------------------------------------------------+----------+----------+--------------------+------+------+
|cdb9d6a1dddc375a09cc83e3001598dc|8e43ca37701228e74983efdbd0cff5c16b3b1e5d4e29a7c05626d4d25a018e11|64        |1643265635|-7207750980409741936|int   |bigint|
+--------------------------------+----------------------------------------------------------------+----------+----------+--------------------+------+------+
+----------+-----------+--------------------+--------------------+
|h_int     |h_bigint   |x_int               |x_bigint            |
+----------+-----------+--------------------+--------------------+
|-559580957|-1712319331|-6698625589789238999|-7001672635703045582|
+----------+-----------+--------------------+--------------------+
```

The `INT` 1 and the `BIGINT` 1 hash differently. If one table stores `customer_id` as `INT` and another as `BIGINT`, their hashes never match: cast to one type before hashing. `hash` and `xxhash64` can be negative, which is why bucketing uses `pmod(hash(x), n)` (practice question 16).

### A row hash for change detection, and the NULL trap

To find changed rows, hash the non-key columns of the incoming row and compare with the hash stored in the target. The common first attempt, `sha2(concat_ws('||', a, b, c), 256)`, has a bug that section 19.4 already showed: `concat_ws` skips `NULL`s.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT a, b, c,
       sha2(concat_ws('||', a, b, c), 256) = sha2(concat_ws('||', 'x', NULL, 'y'), 256) AS same_as_row1_ws,
       concat_ws('||', a, b, c) AS ws_text,
       concat_ws('||', coalesce(a, '<null>'), coalesce(b, '<null>'), coalesce(c, '<null>')) AS safe_text,
       xxhash64(a, b, c) AS xx_multi_arg
FROM VALUES ('x', NULL, 'y'), ('x', 'y', NULL), (NULL, 'x', 'y') AS t(a, b, c);
```
```python
cols = ["name", "email", "city", "country"]
(spark.table("silver.customers").select(
    "customer_id",
    F.sha2(F.concat_ws("||", *[F.coalesce(F.col(c), F.lit("<null>")) for c in cols]), 256).alias("row_hash"))
 .orderBy("customer_id"))
```

Output (from `ex10_hash_ids.out`; the PySpark row hashes for the four customers are in the file):
```text
+----+----+----+---------------+-------+------------+--------------------+
|a   |b   |c   |same_as_row1_ws|ws_text|safe_text   |xx_multi_arg        |
+----+----+----+---------------+-------+------------+--------------------+
|x   |NULL|y   |true           |x||y   |x||<null>||y|-3274121240623841382|
|x   |y   |NULL|true           |x||y   |x||y||<null>|-3274121240623841382|
|NULL|x   |y   |true           |x||y   |<null>||x||y|-3274121240623841382|
+----+----+----+---------------+-------+------------+--------------------+
```

Three different rows, one text and one hash. A customer whose city changes from `'Calgary'` to `NULL` while another field shifts into its place would look unchanged. The multi-argument `xxhash64(a, b, c)` collided too: in this run, a `NULL` argument did not change the hash, so its position was lost. The fix is to make `NULL` visible and positional, as `safe_text` does: `coalesce` each column to a marker that cannot occur in the data, then hash. Also pick a separator that cannot occur in the values, or `'a||' + 'b'` and `'a' + '||b'` produce the same text.

On Databricks, Lakeflow pipelines (formerly Delta Live Tables) can track history for you with `AUTO CDC` (formerly `APPLY CHANGES`), see [chapter 14](14-Data-Quality-and-CDC.md). A hand-written `MERGE` with a row hash is the portable version ([chapter 9](09-Building-Silver.md)).

### uuid

`uuid()` returns "a `STRING` formatted as a canonical UUID 36-character string" and "The function is non-deterministic."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT length(uuid()) AS len, uuid() = uuid() AS same_call_twice;
```

Output (from `ex10_hash_ids.out`):
```text
+---+---------------+
|len|same_call_twice|
+---+---------------+
|36 |false          |
+---+---------------+
```

A non-deterministic id is fine when it is written once (an `INSERT` into a table). It is a problem in a view or in a DataFrame that is computed twice: a retried task, or two actions on the same uncached DataFrame, can produce different ids for the same row. Generate it, write it, then read it back.

### monotonically_increasing_id is not a sequence

`monotonically_increasing_id()` "Returns monotonically increasing 64-bit integers", and its page says "The generated ID is guaranteed to be monotonically increasing and unique, but not consecutive. The function is non-deterministic, so it may return different values if called multiple times for the same row." The Apache Spark API docs give the reason: "The current implementation puts the partition ID in the upper 31 bits, and the record number within each partition in the lower 33 bits."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
df = spark.table("silver.orders").repartition(3, "customer_id")
(df.withColumn("mono_id", F.monotonically_increasing_id())
   .withColumn("partition", F.spark_partition_id())
   .select("order_id", "partition", "mono_id").orderBy("mono_id"))
```
```sql
SELECT order_id, row_number() OVER (ORDER BY order_id) AS consecutive_id
FROM silver.orders ORDER BY order_id LIMIT 5;
```

Output (from `ex10_hash_ids.out`, trimmed):
```text
+--------+---------+----------+
|order_id|partition|mono_id   |
+--------+---------+----------+
|1010    |0        |0         |
|1011    |0        |1         |
...
|1007    |0        |10        |
|1009    |1        |8589934592|
|1014    |1        |8589934593|
|1001    |1        |8589934594|
|1003    |1        |8589934595|
|1008    |1        |8589934596|
+--------+---------+----------+
+--------+--------------+
|order_id|consecutive_id|
+--------+--------------+
|1001    |1             |
|1002    |2             |
...
```

Partition 0 got ids 0 to 10, partition 1 starts at 8589934592 (2^33). The ids depend on how the data happens to be partitioned, so the same row gets a different id after a repartition or on the next run. `row_number() OVER (ORDER BY ...)` gives consecutive numbers, but a window with no `PARTITION BY` moves every row to one task, which does not scale and still renumbers on every run.

For a stable surrogate key in a table, use an identity column (`GENERATED ALWAYS AS IDENTITY`, [chapter 20](20-Tables-in-Databricks-SQL.md)) or a hash of the business key (`xxhash64` or `sha2` of the natural key, cast to one type first).

!!! tip "In the interview"
    **"Can you use `monotonically_increasing_id` as a surrogate key?"** Only as a unique id inside one job run. It is unique and increasing but not consecutive, and it is not stable: the value depends on the partition layout, so a rerun or a retried task can give a different id to the same row. For keys that other tables join to, use an identity column or a deterministic hash of the business key. For row hashes in SCD type 2, `coalesce` every column before `concat_ws`, or a `NULL` makes different rows hash the same.

## 19.12 AI functions (Databricks only)
*Level: intermediate.*

**The problem.** A support table has free-text messages that should be tagged ("damaged", "late", "billing"), or product reviews that need a sentiment score, before they reach a gold dashboard. Databricks provides SQL functions that call a language model on each row. None of them exist in Apache Spark, so nothing in this section was run here.

The [AI Functions](https://docs.databricks.com/aws/en/large-language-models/ai-functions) page describes two kinds:

- **Task-specific functions**, "Purpose-built functions optimized for a specific task, such as document parsing, entity extraction, classification, and sentiment analysis". Examples: `ai_classify`, `ai_extract`, `ai_parse_document`, `ai_analyze_sentiment`, `ai_summarize`, `ai_translate`, `ai_mask`.
- **`ai_query`**, "The general-purpose function for task and model flexibility. Provide a prompt and choose any supported Foundation Model API."

Every function page read for this section says "Applies to: Databricks SQL Databricks Runtime". The availability rules are on the pages, not in that label:

| Rule | Quoted from |
| --- | --- |
| "AI Functions are not available on Classic SQL warehouses." | AI Functions page |
| "Databricks Runtime 15.4 LTS or above is required. For an upcoming change to this requirement, see AI Functions require Databricks Runtime 17.3 LTS or above. Databricks Runtime 18.2 or above is recommended for the best performance and access to the latest features." | AI Functions page and each function page |
| "This function is only available in some regions" (`ai_classify`, `ai_extract`); "only available on workspaces in regions that support AI Functions optimized for batch inference" (`ai_analyze_sentiment`, `ai_summarize`, `ai_mask`, `ai_translate`, `ai_gen`) | function pages |
| "This functionality is in Public Preview" | `ai_analyze_sentiment`, `ai_summarize`, `ai_mask`, `ai_translate`, `ai_gen` pages |
| `ai_query` "Invokes an existing Databricks Model Serving endpoint"; the endpoint argument requires that "The definer must have `CAN QUERY` permission on the endpoint." | `ai_query` page |

*Databricks only, not run here. Syntax from [ai_classify function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_classify).*
```sql
SELECT ai_classify(
  'My order 1003 arrived with a torn rain shell.',
  '["damaged_item", "late_delivery", "billing"]',
  MAP('version', '2.1')
) AS label;
```

`ai_classify(content, labels [, options])` takes the labels as a JSON string (an array of names, or an object mapping names to descriptions; "`labels` must contain at least 2 labels, and no more than 500 labels"). The page marks version 2.1 as recommended and says that in version 2.1 "each classification is a per-label object with a `value` key"; the function "Returns a `VARIANT`" (reading `VARIANT` values is in [chapter 18](18-Semi-Structured-Data.md)).

*Databricks only, not run here. Syntax from [ai_analyze_sentiment function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_analyze_sentiment).*
```sql
SELECT review_id, ai_analyze_sentiment(review_text) AS sentiment
FROM shop.bronze.product_reviews;
```

`ai_analyze_sentiment(content)` returns "A `STRING`. The value is chosen from `'positive'`, `'negative'`, `'neutral'`, or `'mixed'`. Returns `null` if the sentiment cannot be detected." (`shop.bronze.product_reviews` is a hypothetical table; Red Rock Supply has no review text.)

*Databricks only, not run here. Syntax from [ai_query function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query).*
```sql
SELECT order_id,
       ai_query('system.ai.meta-llama-3-3-70b-instruct',
                'Write a one-line shipping note for an order of ' || CAST(amount AS STRING) || ' ' || currency) AS note
FROM shop.silver.orders
LIMIT 10;
```

`ai_query(endpoint, request)` sends one request per row to a Model Serving endpoint; the endpoint name above is the one used in the page's own example. The longer form `ai_query(endpoint, request, returnType, failOnError)` adds `failOnError`, "A boolean literal that defaults to true. Requires Databricks Runtime 15.3 or above"; with `failOnError => false` "the function returns a `STRUCT` object that contains the parsed response and the error message string", so one failed row does not fail the whole query.

**Cost.** The AI Functions page: "The compute that runs your query is always billed". Task-specific functions such as `ai_classify`, `ai_summarize` and `ai_translate` "run inference on Databricks-managed serverless GPU infrastructure ... billed in addition to your query compute", and `ai_query` "is billed for the Model Serving endpoint you specify". The page adds that "AI Function inference costs are recorded in the `system.billing.usage` table". No prices are given here; they change and depend on the contract.

**In pipelines.** The page says AI Functions "can be run from Databricks SQL, notebooks, Lakeflow pipelines, and Workflows" (it uses both the new pipelines name and the old jobs name in one sentence), and that "For large-scale batch inference" you can integrate them "into your production workflows, like Lakeflow pipelines, jobs, and Structured Streaming".

!!! tip "In the interview"
    **"How would you add sentiment or classification to a pipeline on Databricks?"** Use an AI function in the silver-to-gold step: `ai_analyze_sentiment` or `ai_classify` for a fixed task, `ai_query` for a custom prompt or model, inside a Lakeflow pipeline (formerly Delta Live Tables, [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) or a Lakeflow Job (formerly Databricks Jobs, with the menu item "Workflows"; the [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) say "The product known as Databricks Jobs is now Lakeflow Jobs" and that the Workflows item in the left navigation was removed, its functionality now under Jobs & Pipelines). Then cover the engineering points: run it incrementally so each row is scored once (inference is billed per call, on top of compute), store the model output with the date or version used, handle failures with `failOnError => false` and a quarantine of failed rows, check availability (not on Classic SQL warehouses, Databricks Runtime 15.4 LTS or above, region limits, several functions in Public Preview), and track cost in `system.billing.usage`.

## 19.13 Practice questions
*Level: beginner to expert.*

Answers marked "Run here" come from `ex11_practice.py` (output in `ex11_practice.out`) or from the section scripts named in the answer.

### Dates and times

**Q1. What do these three expressions return? `datediff(DATE'2026-03-01', DATE'2026-03-31')`, `timestampdiff(DAY, DATE'2026-03-01', DATE'2026-03-31')`, `datediff(DAY, DATE'2026-03-31', DATE'2026-03-01')`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```text
    +---+---+---+
    |a  |b  |c  |
    +---+---+---+
    |-30|30 |-30|
    +---+---+---+
    ```

    **Why:** the two-argument `datediff(endDate, startDate)` puts the end first, so passing the earlier date first gives a negative number. The three-argument forms (`timestampdiff`, `datediff(unit, ...)`) put the start first. The same function name has opposite argument orders depending on the number of arguments.

**Q2. For order 1008 (`2026-03-04 19:10:00`), what do `date_trunc('MONTH', order_ts)`, `trunc(order_ts, 'MM')` and `trunc(order_ts, 'DAY')` return?**

??? success "Answer"
    `2026-03-01 00:00:00` (a `TIMESTAMP`), `2026-03-01` (a `DATE`) and `NULL` (section 19.2, `ex01_dates.out`).

    **Why:** `date_trunc(unit, expr)` returns a `TIMESTAMP`; `trunc(expr, unit)` returns a `DATE`, takes its arguments the other way round, and knows only year, quarter, month and week units. An unknown unit gives `NULL`, not an error, so a typo in the unit silently empties a column.

**Q3. A monthly report shows dates such as `2026-15-01` and `2026-20-01`. Find the bug.**

??? success "Answer"
    The format string is `'yyyy-mm-dd'`. Lowercase `mm` is minutes; months are `MM`. In section 19.3 `date_format(order_ts, 'yyyy-mm-dd')` gave `2026-15-01` for an order at 10:15. Fix: `date_format(order_ts, 'yyyy-MM-dd')`.

    **Why:** both letters are valid, so nothing fails. The same family of bugs: `DD` (day-of-year) instead of `dd`, `hh` (12-hour clock) instead of `HH`.

**Q4. Orders are stored in UTC. Write daily revenue for March 31 to April 2 in Edmonton local time.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT CAST(from_utc_timestamp(order_ts, 'America/Edmonton') AS DATE) AS local_day,
           count(*) AS orders, sum(amount) AS revenue
    FROM silver.orders
    WHERE order_ts >= TIMESTAMP'2026-03-31 06:00:00' AND order_ts < TIMESTAMP'2026-04-03 06:00:00'
    GROUP BY ALL ORDER BY local_day;
    ```

    ```text
    +----------+------+-------+
    |local_day |orders|revenue|
    +----------+------+-------+
    |2026-03-31|1     |159.00 |
    |2026-04-02|1     |318.00 |
    +----------+------+-------+
    ```

    **Why:** order 1014 is at 03:20 UTC on April 1, which is 21:20 on March 31 in Edmonton (UTC-6 in summer time), so it belongs to March 31. Convert first, then truncate. The `WHERE` bounds are the local midnights expressed in UTC, which keeps the filter on the raw column. The alternative is `SET TIME ZONE 'America/Edmonton'` for the job.

**Q5. Which type would you use for (a) `order_ts` from the web shop, (b) a store's opening time "09:00" that should read 09:00 in any session?**

??? success "Answer"
    (a) `TIMESTAMP`: an order happens at one instant, stored in UTC and displayed in the session time zone. (b) `TIMESTAMP_NTZ`: a wall-clock reading that must not shift (Applies to: Databricks SQL Databricks Runtime 13.3 LTS and above; Public Preview on its page).

    **Why:** in section 19.3 the `TIMESTAMP` column moved six hours under `SET TIME ZONE 'America/Edmonton'` and the `TIMESTAMP_NTZ` column did not. Note that creating a Delta table with an NTZ column enabled the `timestampNtz` table feature, and that CSV and JSON schema inference still gives `TIMESTAMP`.

**Q6. A bronze string column holds ISO timestamps, `dd/MM/yyyy HH:mm` strings and unix epochs. How do you parse it in one expression, and what do you do with what is left?**

??? success "Answer"
    A `coalesce` of `try_` parsers, most specific first: `coalesce(try_to_timestamp(s), try_to_timestamp(s, 'dd/MM/yyyy HH:mm'), timestamp_seconds(try_cast(s AS BIGINT)))`. Section 19.3 ran it on `bronze.orders_raw`: six rows parsed, `'not a date'` became `NULL`. Count or quarantine the `NULL`s.

    **Why:** each `try_` parser returns `NULL` instead of failing, so `coalesce` takes the first one that worked. A format that is ambiguous for some values (`02/03/2026` is valid as `dd/MM` and `MM/dd`) cannot be fixed by ordering the parsers; it needs a rule from the source.

**Q7. `SELECT to_date('01/03/2026')` fails. Why, and how do you fix it?**

??? success "Answer"
    Without a format, `to_date` is `CAST(expr AS DATE)`, which expects `yyyy-MM-dd`; under ANSI mode the result is `CAST_INVALID_INPUT` (section 19.3). Give the format: `to_date('01/03/2026', 'dd/MM/yyyy')` returned `2026-03-01`. Use `try_to_date` (Databricks Runtime 17.2 and above) or `try_to_timestamp` (11.3 LTS and above) to get `NULL` instead of an error.

    **Why:** with ANSI mode off the same call returns `NULL` silently (the `to_date` page: "in Databricks Runtime, set spark.sql.ansi.enabled to `false`" to get `NULL` instead of an error; not run here), which is how bad dates used to slip into silver.

**Q8. A job moved to a runtime where ANSI mode is on by default and now fails with `CAST_INVALID_INPUT` on a `customer_id` value `'x7'`. What are your options, and which do you pick?**

??? success "Answer"
    Use `try_cast(customer_id AS INT)` at the bronze-to-silver step, count the rows that become `NULL` (`count_if(try_cast(customer_id AS INT) IS NULL)` found 1 in section 19.5) and send them to a quarantine table. Do not turn ANSI mode off for the job.

    **Why:** ANSI mode surfaced a real data problem. Turning it off would also bring back silent overflow ("wraps" the result, per the `sum` page) and silent `NULL`s from bad casts in every other expression of the job. See [chapter 17](17-Databricks-SQL-vs-Standard.md), section 17.2, for the defaults per product.

**Q9. A customer signed up on January 31 and cancelled on February 28. Is their tenure 0 months or 1 month?**

??? success "Answer"
    It depends on the function. `timestampdiff(MONTH, TIMESTAMP'2026-01-31 00:00:00', TIMESTAMP'2026-02-28 00:00:00')` returned 0, and `months_between(DATE'2026-02-28', DATE'2026-01-31')` returned 1.0 (section 19.2).

    **Why:** `timestampdiff` counts a month as elapsed only when "the calendar day and time is equal or greater to the start" (28 is less than 31). `months_between` treats two month-end dates as a whole number of months. Agree on the business rule first, then choose the function.

### Strings

**Q10. `concat('RRS-', status)` returns `NULL` for some rows. Why, and what are two fixes?**

??? success "Answer"
    `status` is `NULL` for those rows (order 1008), and `concat` (and `||`) return `NULL` if any argument is `NULL`. Fixes: `concat('RRS-', coalesce(status, 'UNKNOWN'))`, or `concat_ws('-', 'RRS', status)`, which skips `NULL` arguments (it returned `RRS-1008` in section 19.4).

    **Why:** `concat_ws` is convenient for display, but because it drops `NULL`s silently it is wrong for row hashes (Q43).

**Q11. `split('a.b.c', '.')` returns `[, , , , , ]`. Why?**

??? success "Answer"
    The second argument of `split` is a regular expression, and `.` matches any character, so every character is a separator. Use `split('a.b.c', '[.]')` (returned `[a, b, c]`) or `split_part`, which takes a plain delimiter.

    **Why:** the `split` page says the argument "is a regular expression". The same applies to `|`, `$` and other regex metacharacters used as delimiters.

**Q12. Give three ways to get the domain of `ana@example.com`, and say which index base each uses.**

??? success "Answer"
    `split_part(email, '@', 2)` (1-based), `split(email, '@')[1]` (array subscript, 0-based), `regexp_extract(email, '^([^@]+)@(.+)$', 2)` (group 2). In PySpark, also `F.substring_index("email", "@", -1)`. All returned `example.com` in section 19.4.

    **Why:** mixing the 1-based `split_part` with the 0-based `[ ]` subscript is a classic off-by-one bug. `split_part` with part 0 raises `INVALID_INDEX_OF_ZERO`.

**Q13. `regexp_extract('order 1001', '(\d+)', 1)` returns `d`. Why?**

??? success "Answer"
    In a normal SQL string literal the backslash is an escape character, so `'\d'` becomes the letter `d` before the regex engine sees it. Write `'(\\d+)'` or, as the pages recommend, a raw literal `r'(\d+)'`; both returned `1001` (section 19.4).

    **Why:** the query does not fail, it matches the wrong thing. In PySpark, pass a Python raw string (`r"(\d+)"`).

**Q14. Phone numbers arrive as `+1 (403) 555-0101`, `303.555.0102` and `435-555-0103`. How do you normalize them?**

??? success "Answer"
    `regexp_replace(phone, '[^0-9]', '')` keeps only digits: `14035550101`, `3035550102`, `4355550103` (section 19.4). Then apply a rule for the country code (for example, keep the last 10 digits for North American numbers) and flag values with an unexpected length.

    **Why:** removing everything that is not a digit is simpler and safer than listing every separator. A `NULL` phone stays `NULL`.

### Numbers and conditionals

**Q15. What do `round(2.5)`, `bround(2.5)`, `round(3.5)` and `bround(3.5)` return, and when would you use `bround`?**

??? success "Answer"
    3, 2, 4, 4 (section 19.5). `round` is `HALF_UP`; `bround` is `HALF_EVEN` ("banker's rounding"), which rounds a 5 toward the even digit.

    **Why:** over many values, `HALF_UP` pushes totals up slightly; `HALF_EVEN` balances out. Some financial systems require it, so match the rounding of the source system when you reconcile totals.

**Q16. You bucket customers with `hash(customer_id) % 4`. Some buckets are negative. Fix it.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id, hash(customer_id) AS h,
           hash(customer_id) % 4 AS pct_bucket, pmod(hash(customer_id), 4) AS pmod_bucket
    FROM silver.customers ORDER BY customer_id;
    ```

    ```text
    +-----------+-----------+----------+-----------+
    |customer_id|h          |pct_bucket|pmod_bucket|
    +-----------+-----------+----------+-----------+
    |1          |-559580957 |-1        |3          |
    |2          |1765031574 |2         |2          |
    |3          |-1823081949|-1        |3          |
    |4          |-397064898 |-2        |2          |
    +-----------+-----------+----------+-----------+
    ```

    **Why:** `hash` returns a signed `INT`, and `%` keeps the sign of the dividend. `pmod` returns the "positive remainder", always 0 to 3 here.

**Q17. `amount` is `DECIMAL(10,2)`. What are the types of `sum(amount)` and `avg(amount)`?**

??? success "Answer"
    `DECIMAL(20,2)` and `DECIMAL(14,6)` (`typeof` in section 19.5).

    **Why:** the `sum` page: `DECIMAL(p + min(10, 31-p), s)`; the `avg` page: `DECIMAL(p + 4, s + 4)`. The extra precision is room for large totals; the extra scale keeps the average exact to more places. Round only at the presentation step.

**Q18. What does `CAST(123456.789 AS DECIMAL(5,2))` do under ANSI mode, and what does `try_cast` do?**

??? success "Answer"
    The cast fails with `NUMERIC_VALUE_OUT_OF_RANGE` ("cannot be represented as Decimal(5, 2)"); `try_cast` returns `NULL` (section 19.5).

    **Why:** `DECIMAL(5,2)` holds at most 999.99. A cast that only loses scale still worked here and rounded half up (`CAST(5.345 AS DECIMAL(3,2))` returned 5.35).

**Q19. Compute the average item price per order (`amount / sum(qty)`) so that a `qty` of 0 cannot fail the job.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT o.order_id, o.amount, sum(oi.qty) AS units,
           round(try_divide(o.amount, sum(oi.qty)), 2)      AS per_unit_try_divide,
           round(o.amount / nullif(sum(oi.qty), 0), 2)      AS per_unit_nullif
    FROM silver.orders o JOIN silver.order_items oi USING (order_id)
    WHERE o.order_id IN (1001, 1005, 1007)
    GROUP BY o.order_id, o.amount ORDER BY o.order_id;
    ```

    ```text
    +--------+------+-----+-------------------+---------------+
    |order_id|amount|units|per_unit_try_divide|per_unit_nullif|
    +--------+------+-----+-------------------+---------------+
    |1001    |59.90 |2    |29.95              |29.95          |
    |1005    |318.00|2    |159.00             |159.00         |
    |1007    |159.00|1    |159.00             |159.00         |
    +--------+------+-----+-------------------+---------------+
    ```

    **Why:** both return `NULL` when the divisor is 0. `try_divide` (Applies to: Databricks SQL Databricks Runtime 10.4 LTS and above) is shorter; `x / nullif(y, 0)` is portable SQL.

**Q20. `CASE status WHEN NULL THEN 'missing' ELSE 'present' END` returns `'present'` for order 1008, whose status is `NULL`. Why?**

??? success "Answer"
    The simple `CASE` compares `status = NULL`, which is `NULL`, never true. Use the searched form: `CASE WHEN status IS NULL THEN 'missing' ELSE 'present' END` (section 19.6 shows both).

    **Why:** every comparison with `NULL` using `=` or `<>` is unknown. `decode` is the exception: its page says "For this function `NULL` matches `NULL`."

**Q21. Explain `coalesce`, `nvl`, `nvl2` and `nullif` with one example each on `status`.**

??? success "Answer"
    For order 1008 (`NULL`) and 1003 (`PLACED`), section 19.6 returned: `coalesce(status, 'UNKNOWN')` and `nvl(status, 'UNKNOWN')` give `UNKNOWN` / `PLACED`; `nvl2(status, 'has status', 'no status')` gives `no status` / `has status`; `nullif(status, 'PLACED')` gives `NULL` / `NULL` (the first because the input is `NULL`, the second because it equals `'PLACED'`).

    **Why:** `nvl` and `ifnull` are two-argument synonyms of `coalesce`; `coalesce` takes any number of arguments and stops at the first non-`NULL` one. `nullif` turns a sentinel value into `NULL`, which is how `x / nullif(y, 0)` works.

**Q22. What do `greatest(1, NULL, 3)` and `1 + NULL` return?**

??? success "Answer"
    3 and `NULL` (section 19.6).

    **Why:** `greatest` and `least` skip `NULL` arguments (like the `max` and `min` aggregates); arithmetic does not. `greatest(updated_at, last_order_ts)` therefore gives a "last activity" value even for a customer with no orders.

### Aggregates and grouping

**Q23. On `silver.orders` (16 rows, one `NULL` status, statuses SHIPPED, PLACED and CANCELLED), what do `count(*)`, `count(status)` and `count(DISTINCT status)` return?**

??? success "Answer"
    16, 15 and 3 (section 19.7).

    **Why:** `count(expr)` counts non-`NULL` values, and `DISTINCT` counts distinct non-`NULL` values. "How many statuses are there?" has two defensible answers (3 or 4 with "unknown"); say which one you report.

**Q24. A dashboard shows "average shipped order value" as 102.58, but finance says 182.37. Which query is right?**

??? success "Answer"
    Finance. `avg(CASE WHEN status = 'SHIPPED' THEN amount END)` returned 182.366667: the average over the 9 shipped orders. `avg(CASE WHEN status = 'SHIPPED' THEN amount ELSE 0 END)` returned 102.581250: shipped revenue divided by all 16 orders (section 19.7).

    **Why:** aggregates skip `NULL`s, so a `CASE` without `ELSE` removes the row from the denominator, while `ELSE 0` keeps it. Better still, write `avg(amount) FILTER (WHERE status = 'SHIPPED')`.

**Q25. In one query per currency, return shipped revenue, the number of cancelled orders and the number of orders with no status. Then write it in PySpark.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT currency,
           sum(amount) FILTER (WHERE status = 'SHIPPED')   AS shipped_revenue,
           count(*)    FILTER (WHERE status = 'CANCELLED') AS cancelled_orders,
           count_if(status IS NULL)                        AS missing_status
    FROM silver.orders GROUP BY currency ORDER BY currency;
    ```

    ```python
    (spark.table("silver.orders").groupBy("currency").agg(
        F.sum(F.when(F.col("status") == "SHIPPED", F.col("amount"))).alias("shipped_revenue"),
        F.count(F.when(F.col("status") == "CANCELLED", 1)).alias("cancelled_orders"),
        F.count_if(F.col("status").isNull()).alias("missing_status"))
     .orderBy("currency"))
    ```

    ```text
    +--------+---------------+----------------+--------------+
    |currency|shipped_revenue|cancelled_orders|missing_status|
    +--------+---------------+----------------+--------------+
    |CAD     |665.90         |1               |1             |
    |USD     |975.40         |1               |0             |
    +--------+---------------+----------------+--------------+
    ```

    **Why:** one scan instead of three queries. PySpark has no `FILTER` clause, but `F.when` without `otherwise` gives `NULL` for the other rows, which `sum` and `count` skip. Both versions returned the same table.

**Q26. When do you use `max_by(status, order_ts)` and when `row_number()` to get each customer's latest status?**

??? success "Answer"
    `max_by` with `GROUP BY customer_id` when you need one or two columns from the latest row; it returned PLACED, SHIPPED, SHIPPED, CANCELLED for customers 1 to 4 (section 19.7). `QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY order_ts DESC) = 1` when you need the whole row, as in deduplication before a `MERGE` (section 19.10).

    **Why:** both pick an arbitrary row when the latest timestamp is tied (`max_by`: "the result is non-deterministic"), so add a tiebreaker to the `ORDER BY` of `row_number`, or to the ordering expression of `max_by` (for example a struct of timestamp and id).

**Q27. A job builds `collect_list(order_id)` per customer and a test that compares the list with `[1001, 1003, 1008, 1009, 1014]` fails now and then. Why?**

??? success "Answer"
    "The order of elements in the array is non-deterministic" (`collect_list` page). In section 19.7, `F.listagg` without an order returned `1009,1014,1001,1003,1008` for customer 1. Fix: `array_sort(collect_list(order_id))` for natural order, `transform(array_sort(collect_list(struct(order_ts, order_id))), x -> x.order_id)` for order by another column, or `listagg(...) WITHIN GROUP (ORDER BY ...)` (Databricks Runtime 16.4 and later).

    **Why:** the order depends on which partition and task each row came from, which changes with data size and cluster layout.

**Q28. When is `approx_count_distinct` the right choice, and how accurate is it?**

??? success "Answer"
    For distinct counts on very large data where a small error is acceptable, such as daily unique visitors on a dashboard. The page says it uses HyperLogLog++ and results "are accurate within a default value of 5%", configurable with `relativeSD`. Use exact `count(DISTINCT ...)` for billing, reconciliation and anything audited.

    **Why:** an exact distinct count must shuffle every distinct value; the sketch keeps a small fixed-size state per group, which also makes it cheap to compute per partition and merge.

**Q29. On the 16 order amounts, `median(amount)` is 159.0 and `percentile(amount, array(0.25, 0.75))` is `[54.675, 204.375]`. Why is 54.675 not an order amount, and what would `percentile_approx` return?**

??? success "Answer"
    The exact `percentile` interpolates between the two neighboring values. `percentile_approx` returns "the smallest value in the ordered group ... such that no more than `percentile` of `expr` values is less than the value or equal to that value", which is always one of the actual values; at 0.5 it returned 159.0 (section 19.7).

    **Why:** the exact percentile has to consider every value of the group; the approximate one trades precision for memory through its `accuracy` argument (default 10000, relative error `1.0/accuracy`). `median` returns a `DOUBLE`, `percentile_approx` the type of `expr` here (`decimal(10,2)`).

**Q30. In one query, return daily revenue, a monthly subtotal and a grand total since March 30, and label the level of each row.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT date_trunc('MONTH', order_ts) AS month, CAST(order_ts AS DATE) AS day,
           sum(amount) AS revenue,
           grouping_id(date_trunc('MONTH', order_ts), CAST(order_ts AS DATE)) AS gid
    FROM silver.orders
    WHERE order_ts >= TIMESTAMP'2026-03-30'
    GROUP BY GROUPING SETS ((date_trunc('MONTH', order_ts), CAST(order_ts AS DATE)),
                            (date_trunc('MONTH', order_ts)), ())
    ORDER BY gid, month, day;
    ```

    ```text
    +-------------------+----------+-------+---+
    |month              |day       |revenue|gid|
    +-------------------+----------+-------+---+
    |2026-04-01 00:00:00|2026-04-01|159.00 |0  |
    |2026-04-01 00:00:00|2026-04-02|318.00 |0  |
    |2026-04-01 00:00:00|2026-04-06|189.50 |0  |
    |2026-04-01 00:00:00|NULL      |666.50 |1  |
    |NULL               |NULL      |666.50 |3  |
    +-------------------+----------+-------+---+
    ```

    **Why:** `gid` 0 is a day row, 1 a month subtotal (day not grouped), 3 the grand total. `ROLLUP (month, day)` gives the same three levels. The two 666.50 rows are equal only because one month falls in the range.

**Q31. How many grouping sets do `ROLLUP (a, b, c)` and `CUBE (a, b, c)` produce?**

??? success "Answer"
    4 and 8. The GROUP BY page: "The N elements of a `ROLLUP` specification result in N+1 `GROUPING SETS`" and "The N elements of a `CUBE` specification results in 2^N `GROUPING SETS`." In section 19.8, `CUBE (currency, category)` produced rows at 4 levels (`gid` 0, 1, 2, 3).

    **Why:** `ROLLUP` removes columns from the right only (a hierarchy); `CUBE` takes every subset. A `CUBE` over many columns grows fast, so list the needed sets with `GROUPING SETS` instead.

### Windows

**Q32. For the orders of 189.50 and more, show `row_number`, `rank` and `dense_rank` ordered by amount descending.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT amount,
           row_number() OVER (ORDER BY amount DESC, order_id) AS rn,
           rank()       OVER (ORDER BY amount DESC)           AS rnk,
           dense_rank() OVER (ORDER BY amount DESC)           AS drnk
    FROM silver.orders WHERE amount >= 189.50 ORDER BY amount DESC, order_id;
    ```

    ```text
    +------+---+---+----+
    |amount|rn |rnk|drnk|
    +------+---+---+----+
    |318.00|1  |1  |1   |
    |318.00|2  |1  |1   |
    |249.00|3  |3  |2   |
    |249.00|4  |3  |2   |
    |189.50|5  |5  |3   |
    |189.50|6  |5  |3   |
    |189.50|7  |5  |3   |
    +------+---+---+----+
    ```

    **Why:** `rank` skips numbers after a tie, `dense_rank` does not, `row_number` breaks ties; `order_id` in its `ORDER BY` makes the tie-break deterministic.

**Q33. Find the best-selling product (by line revenue) in each category, keeping ties.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT p.category, p.name, sum(oi.qty * oi.unit_price) AS revenue
    FROM silver.order_items oi JOIN silver.products p USING (product_id)
    GROUP BY p.category, p.name
    QUALIFY rank() OVER (PARTITION BY p.category ORDER BY revenue DESC) = 1
    ORDER BY p.category;
    ```

    ```text
    +--------+-----------------+-------+
    |category|name             |revenue|
    +--------+-----------------+-------+
    |Apparel |Rain Shell       |954.00 |
    |Camping |Down Sleeping Bag|568.50 |
    |Hiking  |Trekking Poles   |179.70 |
    +--------+-----------------+-------+
    ```

    **Why:** the window runs after `GROUP BY`, so it can rank aggregated revenue, and `QUALIFY` can refer to the `revenue` alias. `rank` keeps every product tied for first; `row_number` would keep one arbitrarily.

**Q34. Write a running total of `amount` per customer in order of `order_ts`, in SQL and PySpark.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT customer_id, order_id, order_ts, amount,
           sum(amount) OVER (PARTITION BY customer_id ORDER BY order_ts
                             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS customer_running_total
    FROM silver.orders WHERE customer_id IN (2, 3) ORDER BY customer_id, order_ts;
    ```

    ```python
    (spark.table("silver.orders").where("customer_id IN (2, 3)")
     .withColumn("customer_running_total", F.sum("amount").over(
         Window.partitionBy("customer_id").orderBy("order_ts")
         .rowsBetween(Window.unboundedPreceding, Window.currentRow)))
     .select("customer_id", "order_id", "amount", "customer_running_total")
     .orderBy("customer_id", "order_ts"))
    ```

    ```text
    +-----------+--------+-------------------+------+----------------------+
    |customer_id|order_id|order_ts           |amount|customer_running_total|
    +-----------+--------+-------------------+------+----------------------+
    |2          |1002    |2026-03-01 11:05:00|249.00|249.00                |
    |2          |1006    |2026-03-03 17:30:00|29.95 |278.95                |
    |2          |1010    |2026-03-07 10:00:00|189.50|468.45                |
    |2          |1015    |2026-04-02 08:00:00|318.00|786.45                |
    |3          |1004    |2026-03-02 14:20:00|39.00 |39.00                 |
    |3          |1007    |2026-03-04 12:00:00|159.00|198.00                |
    |3          |1013    |2026-03-15 13:10:00|59.90 |257.90                |
    +-----------+--------+-------------------+------+----------------------+
    ```

    **Why:** write the frame explicitly as `ROWS`; the default would be `RANGE`, which gives tied timestamps the same total. The PySpark version returned the same running totals.

**Q35. `last_value(order_id) OVER (PARTITION BY customer_id ORDER BY order_ts)` returns the current row's own `order_id`. Why, and how do you get the customer's last order?**

??? success "Answer"
    With `ORDER BY` and no frame, the default frame is `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, so the last row of the frame is the current row. Use `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING` (returned 1014 on every row of customer 1 in section 19.9) or `first_value(order_id) OVER (PARTITION BY customer_id ORDER BY order_ts DESC)`.

    **Why:** the default frame is stated on the Databricks PySpark `Window` page: "When ordering is defined, a growing window frame (rangeFrame, unboundedPreceding, currentRow) is used by default."

**Q36. What is the difference between `ROWS BETWEEN 2 PRECEDING AND CURRENT ROW` and `RANGE BETWEEN 2 PRECEDING AND CURRENT ROW`?**

??? success "Answer"
    `ROWS` counts physical rows: the current row and the two before it. `RANGE` uses values of the single `ORDER BY` expression: every row whose value is between (current value - 2) and the current value, including all rows tied with the current row. On a date column, `RANGE BETWEEN INTERVAL 2 DAYS PRECEDING AND CURRENT ROW` means "the last three calendar days", however many rows that is (Figure 19.2, Q37).

    **Why:** `ROWS` is right for "the last N events", `RANGE` for "the last N days or hours". `RANGE` with an offset needs exactly one `ORDER BY` expression (`RANGE_FRAME_MULTI_ORDER` otherwise).

**Q37. Compute a trailing 3-day revenue total per day. Some days have no orders. Why do `ROWS` and `RANGE` disagree?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    WITH daily AS (
      SELECT CAST(order_ts AS DATE) AS d, sum(amount) AS revenue FROM silver.orders
      WHERE order_ts < TIMESTAMP'2026-03-16' GROUP BY ALL
    )
    SELECT d, revenue,
           sum(revenue) OVER (ORDER BY d ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)                 AS rows_3,
           sum(revenue) OVER (ORDER BY d RANGE BETWEEN INTERVAL 2 DAYS PRECEDING AND CURRENT ROW) AS range_3_days
    FROM daily ORDER BY d;
    ```

    ```text
    +----------+-------+------+------------+
    |d         |revenue|rows_3|range_3_days|
    +----------+-------+------+------------+
    |2026-03-01|308.90 |308.90|308.90      |
    |2026-03-02|228.50 |537.40|537.40      |
    |2026-03-03|347.95 |885.35|885.35      |
    |2026-03-04|305.95 |882.40|882.40      |
    |2026-03-05|249.00 |902.90|902.90      |
    |2026-03-07|189.50 |744.45|438.50      |
    |2026-03-15|59.90  |498.40|59.90       |
    +----------+-------+------+------------+
    ```

    **Why:** there are no rows for March 6 or March 8 to 14. `ROWS` takes "the previous two rows", which on March 15 reach back to March 5 and 7. `RANGE` with an interval takes only March 13 to 15. The other fix is to join `daily` to a complete calendar (with 0 for missing days) and then use `ROWS`.

**Q38. Find each customer's streaks of consecutive order days. Explain the trick.**

??? success "Answer"
    Take distinct (customer, day) pairs, compute `island_key = date_sub(d, row_number() OVER (PARTITION BY customer_id ORDER BY d))`, then group by customer and `island_key` with `min(d)`, `max(d)` and `count(*)` (section 19.10, pattern 3). Customer 4 ordered on March 3, 4 and 5, which gave one streak of 3 days.

    **Why:** inside a run of consecutive days, the date and the row number both increase by 1 per row, so their difference is constant; a gap changes it. The `DISTINCT` step matters because two orders on one day would add a row number without adding a day.

**Q39. Split each customer's orders into sessions, where a gap of more than 30 minutes starts a new session.**

??? success "Answer"
    Flag the start of a session with `CASE WHEN lag(order_ts) OVER w IS NULL OR order_ts > lag(order_ts) OVER w + INTERVAL 30 MINUTES THEN 1 ELSE 0 END`, then number sessions with a running `sum` of the flag over `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` (section 19.10, pattern 4). For customer 1, orders 1008 (19:10) and 1009 (19:25) share session 3. In a `GROUP BY`, `session_window(order_ts, '30 minutes')` returns the same sessions as start and end times.

    **Why:** the running sum of "start" flags increases by one at each session start, so it is a session number. The same two steps solve "group events into visits", "trips" and "work shifts".

**Q40. Order 1008 has no status. For each order of customer 1, show the most recent non-`NULL` status before it, and fill 1008's status from the previous order.**

??? success "Answer"
    `lag(status) IGNORE NULLS OVER (PARTITION BY customer_id ORDER BY order_ts)` for the previous non-`NULL` status (for order 1009 it returned PLACED, while plain `lag` returned 1008's `NULL`), and `last_value(status) IGNORE NULLS OVER (PARTITION BY customer_id ORDER BY order_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)` to forward-fill (order 1008 became PLACED). In PySpark: `F.last("status", ignorenulls=True)` over the same window (section 19.9).

    **Why:** `IGNORE NULLS` makes the function skip `NULL` values. The explicit frame ending at the current row is what makes `last_value` a forward fill.

**Q41. `SELECT order_id FROM silver.orders WHERE row_number() OVER (ORDER BY amount) = 1` fails. Why, and give two fixes.**

??? success "Answer"
    It fails with `WINDOW_FUNCTION_NOT_ALLOWED_IN_CLAUSE` (section 19.9) because `WHERE` is evaluated before window functions. Fixes: `QUALIFY`, or a subquery:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```sql
    SELECT * FROM (
      SELECT order_id, amount, row_number() OVER (ORDER BY amount DESC, order_id) AS rn FROM silver.orders
    ) WHERE rn = 1;
    ```

    ```text
    +--------+------+---+
    |order_id|amount|rn |
    +--------+------+---+
    |1005    |318.00|1  |
    +--------+------+---+
    ```

    **Why:** the logical order is `FROM`, `WHERE`, `GROUP BY`, `HAVING`, window functions, `QUALIFY`, `SELECT` list, `ORDER BY`. Filtering on a window result needs a later clause.

### Hashing, ids and AI functions

**Q42. A colleague uses `monotonically_increasing_id()` as the surrogate key of a dimension table. What can go wrong?**

??? success "Answer"
    The ids are unique and increasing but not consecutive (partition 1 started at 8589934592 in section 19.11), and they depend on the partition layout, so the same customer gets a different id when the job reruns or the data is repartitioned. Facts loaded earlier would point to the wrong or a missing dimension row. Use an identity column ([chapter 20](20-Tables-in-Databricks-SQL.md)) or a deterministic hash of the business key.

    **Why:** the page says the function "is non-deterministic, so it may return different values if called multiple times for the same row".

**Q43. An SCD type 2 job uses `sha2(concat_ws('||', name, email, city), 256)` to detect changes and misses some. Why?**

??? success "Answer"
    `concat_ws` skips `NULL`s, so `('x', NULL, 'y')`, `('x', 'y', NULL)` and `(NULL, 'x', 'y')` all become the text `x||y` and the same hash (section 19.11). A value that moves between columns, or a column that becomes `NULL` while another changes, is invisible. Fix: `concat_ws('||', coalesce(name, '<null>'), coalesce(email, '<null>'), coalesce(city, '<null>'))`, with a marker and a separator that cannot occur in the data.

    **Why:** in this run the multi-argument `xxhash64(a, b, c)` collided on the same three rows, so switching hash functions does not fix it; making `NULL` visible does.

**Q44. Which hash function would you choose for (a) spreading keys into 16 buckets, (b) a row hash for change detection on a 500-million-row table, (c) pseudonymizing an email column that analysts join on?**

??? success "Answer"
    (a) `pmod(xxhash64(key), 16)` or `pmod(hash(key), 16)`: fast and numeric. (b) `sha2(..., 256)` or `md5(...)` of the `NULL`-safe concatenation, or `xxhash64` if a 64-bit value is enough for your tolerance of collisions; a 32-bit `hash` collides too often at that size. (c) `sha2(lower(trim(email)), 256)`, so the same email always gives the same value in every table.

    **Why:** the trade-off is speed and size against collision probability. Also cast keys to one type first, because "The hash value depends on the input data type."

**Q45. A team wants to use `ai_classify` in a pipeline on a Classic SQL warehouse and on a Databricks Runtime 14.3 LTS job cluster. What do you tell them?**

??? success "Answer"
    Neither works. The AI Functions page says "AI Functions are not available on Classic SQL warehouses" and "Databricks Runtime 15.4 LTS or above is required", with an upcoming change to 17.3 LTS or above; 18.2 or above is recommended. They also need a workspace in a supported region. Run it on a SQL warehouse that is not Classic, or on a job cluster with a supported runtime.

    **Why:** the "Applies to" label of `ai_classify` says only "Databricks SQL Databricks Runtime"; the real limits are in the requirements section. Also mention cost: task-specific functions are "billed in addition to your query compute", recorded in `system.billing.usage`.

## Sources
- [`add_months` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/add_months) (last updated Sep 11, 2026)
- [`ai_analyze_sentiment` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_analyze_sentiment) (last updated Nov 6, 2026)
- [`ai_classify` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_classify) (last updated Nov 5, 2026)
- [`ai_extract` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_extract) (last updated Nov 5, 2026)
- [`ai_gen` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_gen) (last updated Nov 6, 2026)
- [`ai_mask` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_mask) (last updated Nov 6, 2026)
- [`ai_query` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query) (last updated Nov 5, 2026)
- [`ai_summarize` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_summarize) (last updated Nov 6, 2026)
- [`ai_translate` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_translate) (last updated Nov 6, 2026)
- [Alphabetical list of built-in functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-functions-builtin-alpha) (last updated Sep 11, 2026)
- [`any_value` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/any_value) (last updated Sep 11, 2026)
- [`approx_count_distinct` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/approx_count_distinct) (last updated Sep 11, 2026)
- [`approx_percentile` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/approx_percentile) (last updated Sep 11, 2026)
- [`array_agg` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/array_agg) (last updated Sep 11, 2026)
- [`avg` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/avg) (last updated Oct 28, 2026)
- [`bool_and` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/bool_and) (last updated Sep 11, 2026)
- [`bool_or` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/bool_or) (last updated Sep 11, 2026)
- [`bround` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/bround) (last updated Sep 11, 2026)
- [`btrim` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/btrim) (last updated Sep 11, 2026)
- [Built-in functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-functions-builtin) (last updated Nov 3, 2026)
- [`case` expression](https://docs.databricks.com/aws/en/sql/language-manual/functions/case) (last updated Sep 11, 2026)
- [`ceil` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ceil) (last updated Sep 11, 2026)
- [`coalesce` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/coalesce) (last updated Sep 11, 2026)
- [`collate` expression](https://docs.databricks.com/aws/en/sql/language-manual/functions/collate) (last updated Sep 11, 2026)
- [`collation` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/collation) (last updated Sep 11, 2026)
- [Collation support for Delta Lake](https://docs.databricks.com/aws/en/tables/features/collation) (last updated Sep 11, 2026)
- [Collation](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-collation) (last updated Sep 11, 2026)
- [`collect_list` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/collect_list) (last updated Sep 11, 2026)
- [`collect_set` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/collect_set) (last updated Sep 11, 2026)
- [`concat` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/concat) (last updated Sep 11, 2026)
- [`concat_ws` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/concat_ws) (last updated Sep 11, 2026)
- [`convert_timezone` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/convert_timezone) (last updated Sep 11, 2026)
- [`count` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/count) (last updated Sep 11, 2026)
- [`count_if` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/count_if) (last updated Sep 11, 2026)
- [`cume_dist` analytic window function](https://docs.databricks.com/aws/en/sql/language-manual/functions/cume_dist) (last updated Sep 11, 2026)
- [`curdate` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/curdate) (last updated Sep 11, 2026)
- [`current_date` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/current_date) (last updated Sep 11, 2026)
- [`current_timestamp` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/current_timestamp) (last updated Oct 30, 2026)
- [`date_add` (days) function](https://docs.databricks.com/aws/en/sql/language-manual/functions/date_add) (last updated Sep 11, 2026)
- [`date_add` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/date_add3) (last updated Sep 11, 2026)
- [`date_diff` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/date_diff) (last updated Oct 30, 2026)
- [`date_format` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/date_format) (last updated Sep 11, 2026)
- [`date_part` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/date_part) (last updated Oct 30, 2026)
- [`date_sub` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/date_sub) (last updated Sep 11, 2026)
- [`date_trunc` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/date_trunc) (last updated Sep 11, 2026)
- [`dateadd` (timestamp) function](https://docs.databricks.com/aws/en/sql/language-manual/functions/dateadd) (last updated Oct 30, 2026)
- [`dateadd` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/dateadd2) (last updated Oct 30, 2026)
- [`datediff` (timestamp) function](https://docs.databricks.com/aws/en/sql/language-manual/functions/datediff3) (last updated Sep 11, 2026)
- [`datediff` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/datediff) (last updated Sep 11, 2026)
- [Datetime patterns](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-datetime-pattern) (last updated Sep 11, 2026)
- [`dayofweek` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/dayofweek) (last updated Sep 11, 2026)
- [`DECIMAL` type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/decimal-type) (last updated Sep 11, 2026)
- [`decode` (key) function](https://docs.databricks.com/aws/en/sql/language-manual/functions/decode) (last updated Sep 11, 2026)
- [`dense_rank` ranking window function](https://docs.databricks.com/aws/en/sql/language-manual/functions/dense_rank) (last updated Sep 11, 2026)
- [DESCRIBE FUNCTION](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-describe-function) (last updated Sep 11, 2026)
- [`div` operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/div) (last updated Oct 28, 2026)
- [`every` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/every) (last updated Sep 11, 2026)
- [`extract` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/extract) (last updated Sep 11, 2026)
- [`first` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/first) (last updated Sep 11, 2026)
- [`first_value` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/first_value) (last updated Sep 11, 2026)
- [`floor` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/floor) (last updated Sep 11, 2026)
- [`format_string` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/format_string) (last updated Sep 11, 2026)
- [`from_unixtime` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/from_unixtime) (last updated Sep 11, 2026)
- [`from_utc_timestamp` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/from_utc_timestamp) (last updated Sep 11, 2026)
- [`greatest` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/greatest) (last updated Sep 11, 2026)
- [GROUP BY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-groupby) (last updated Sep 11, 2026)
- [`grouping` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/grouping) (last updated Sep 11, 2026)
- [`grouping_id` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/grouping_id) (last updated Sep 11, 2026)
- [`hash` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/hash) (last updated Sep 11, 2026)
- [`if` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/if) (last updated Sep 11, 2026)
- [`iff` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/iff) (last updated Sep 11, 2026)
- [`ifnull` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ifnull) (last updated Sep 11, 2026)
- [`initcap` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/initcap) (last updated Sep 11, 2026)
- [`instr` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/instr) (last updated Sep 11, 2026)
- [June 2025 (release notes)](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026)
- [`lag` analytic window function](https://docs.databricks.com/aws/en/sql/language-manual/functions/lag) (last updated Sep 11, 2026)
- [`last` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/last) (last updated Sep 11, 2026)
- [`last_day` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/last_day) (last updated Sep 11, 2026)
- [`last_value` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/last_value) (last updated Sep 11, 2026)
- [`lead` analytic window function](https://docs.databricks.com/aws/en/sql/language-manual/functions/lead) (last updated Sep 11, 2026)
- [`least` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/least) (last updated Sep 11, 2026)
- [`left` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/left) (last updated Sep 11, 2026)
- [`levenshtein` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/levenshtein) (last updated Sep 11, 2026)
- [`listagg` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/listagg) (last updated Sep 16, 2026)
- [`locate` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/locate) (last updated Sep 11, 2026)
- [`lower` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/lower) (last updated Sep 11, 2026)
- [`lpad` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/lpad) (last updated Sep 11, 2026)
- [`ltrim` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ltrim) (last updated Sep 11, 2026)
- [`make_date` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/make_date) (last updated Sep 11, 2026)
- [`make_timestamp` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/make_timestamp) (last updated Oct 30, 2026)
- [`make_timestamp_ntz` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/make_timestamp_ntz) (last updated Oct 30, 2026)
- [`max_by` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/max_by) (last updated Nov 5, 2026)
- [`md5` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/md5) (last updated Sep 11, 2026)
- [`mean` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/mean) (last updated Sep 11, 2026)
- [`median` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/median) (last updated Sep 11, 2026)
- [`min_by` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/min_by) (last updated Nov 5, 2026)
- [`mod` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/mod) (last updated Sep 11, 2026)
- [`mode` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/mode) (last updated Sep 11, 2026)
- [`monotonically_increasing_id` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/monotonically_increasing_id) (last updated Sep 11, 2026)
- [`months_between` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/months_between) (last updated Sep 11, 2026)
- [`next_day` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/next_day) (last updated Sep 11, 2026)
- [`now` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/now) (last updated Oct 30, 2026)
- [`nth_value` analytic window function](https://docs.databricks.com/aws/en/sql/language-manual/functions/nth_value) (last updated Sep 11, 2026)
- [`ntile` ranking window function](https://docs.databricks.com/aws/en/sql/language-manual/functions/ntile) (last updated Sep 11, 2026)
- [NULL semantics](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-null-semantics) (last updated Sep 11, 2026)
- [`nullif` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/nullif) (last updated Sep 11, 2026)
- [`nullifzero` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/nullifzero) (last updated Sep 11, 2026)
- [`nvl` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/nvl) (last updated Sep 11, 2026)
- [`nvl2` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/nvl2) (last updated Sep 11, 2026)
- [`percent_rank` ranking window function](https://docs.databricks.com/aws/en/sql/language-manual/functions/percent_rank) (last updated Sep 11, 2026)
- [`percentile` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/percentile) (last updated Sep 11, 2026)
- [`percentile_approx` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/percentile_approx) (last updated Sep 11, 2026)
- [`pmod` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/pmod) (last updated Sep 11, 2026)
- [`position` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/position) (last updated Sep 11, 2026)
- [`printf` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/printf) (last updated Sep 11, 2026)
- [QUALIFY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-qualify) (last updated Sep 11, 2026)
- [`rank` ranking window function](https://docs.databricks.com/aws/en/sql/language-manual/functions/rank) (last updated Sep 11, 2026)
- [`regexp` operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/regexp) (last updated Sep 11, 2026)
- [`regexp_extract` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/regexp_extract) (last updated Sep 11, 2026)
- [`regexp_extract_all` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/regexp_extract_all) (last updated Sep 11, 2026)
- [`regexp_like` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/regexp_like) (last updated Sep 11, 2026)
- [`regexp_replace` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/regexp_replace) (last updated Sep 11, 2026)
- [`right` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/right) (last updated Sep 11, 2026)
- [`rlike` operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/rlike) (last updated Sep 11, 2026)
- [`round` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/round) (last updated Sep 11, 2026)
- [`row_number` ranking window function](https://docs.databricks.com/aws/en/sql/language-manual/functions/row_number) (last updated Sep 11, 2026)
- [`rpad` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/rpad) (last updated Sep 11, 2026)
- [`rtrim` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/rtrim) (last updated Sep 11, 2026)
- [`session_window` grouping expression](https://docs.databricks.com/aws/en/sql/language-manual/functions/session_window) (last updated Sep 11, 2026)
- [SET TIME ZONE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-conf-mgmt-set-timezone) (last updated Sep 11, 2026)
- [`sha2` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/sha2) (last updated Sep 11, 2026)
- [SHOW FUNCTIONS](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-show-functions) (last updated Sep 11, 2026)
- [`some` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/some) (last updated Sep 11, 2026)
- [`split` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/split) (last updated Sep 11, 2026)
- [`split_part` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/split_part) (last updated Sep 11, 2026)
- [SQL data type rules](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-datatype-rules) (last updated Oct 28, 2026)
- [`std` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/std) (last updated Sep 11, 2026)
- [`stddev` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/stddev) (last updated Sep 11, 2026)
- [`string_agg` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/string_agg) (last updated Oct 6, 2026)
- [`substr` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/substr) (last updated Sep 11, 2026)
- [`substring` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/substring) (last updated Sep 11, 2026)
- [`sum` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/sum) (last updated Oct 28, 2026)
- [`TIMESTAMP` type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/timestamp-type) (last updated Oct 30, 2026)
- [`TIMESTAMP_NTZ` type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/timestamp-ntz-type) (last updated Oct 30, 2026)
- [`timestamp_seconds` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/timestamp_seconds) (last updated Oct 30, 2026)
- [`timestampadd` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/timestampadd) (last updated Sep 11, 2026)
- [`timestampdiff` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/timestampdiff) (last updated Sep 11, 2026)
- [TIMEZONE](https://docs.databricks.com/aws/en/sql/language-manual/parameters/timezone) (last updated Sep 11, 2026)
- [`to_date` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/to_date) (last updated Oct 30, 2026)
- [`to_number` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/to_number) (last updated Sep 11, 2026)
- [`to_timestamp` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/to_timestamp) (last updated Oct 30, 2026)
- [`to_utc_timestamp` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/to_utc_timestamp) (last updated Sep 11, 2026)
- [Transform unstructured data using AI Functions](https://docs.databricks.com/aws/en/large-language-models/ai-functions) (last updated Nov 5, 2026)
- [`translate` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/translate) (last updated Sep 11, 2026)
- [`trim` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/trim) (last updated Sep 11, 2026)
- [`trunc` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/trunc) (last updated Sep 11, 2026)
- [`try_add` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_add) (last updated Sep 11, 2026)
- [`try_avg` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_avg) (last updated Sep 11, 2026)
- [`try_cast` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_cast) (last updated Oct 28, 2026)
- [`try_divide` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_divide) (last updated Oct 28, 2026)
- [`try_element_at` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_element_at) (last updated Sep 11, 2026)
- [`try_make_timestamp` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_make_timestamp) (last updated Oct 30, 2026)
- [`try_mod` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_mod) (last updated Sep 11, 2026)
- [`try_multiply` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_multiply) (last updated Sep 11, 2026)
- [`try_subtract` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_subtract) (last updated Sep 11, 2026)
- [`try_sum` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_sum) (last updated Sep 11, 2026)
- [`try_to_date` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_to_date) (last updated Oct 30, 2026)
- [`try_to_number` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_to_number) (last updated Sep 11, 2026)
- [`try_to_timestamp` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_to_timestamp) (last updated Oct 30, 2026)
- [`unix_timestamp` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/unix_timestamp) (last updated Sep 11, 2026)
- [`upper` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/upper) (last updated Sep 11, 2026)
- [`uuid` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/uuid) (last updated Sep 11, 2026)
- [`variance` aggregate function](https://docs.databricks.com/aws/en/sql/language-manual/functions/variance) (last updated Sep 11, 2026)
- [`weekday` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/weekday) (last updated Sep 11, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [Window class](https://docs.databricks.com/aws/en/pyspark/reference/classes/window) (last updated Sep 11, 2026)
- [WINDOW clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-named-window) (last updated Sep 11, 2026)
- [Window frame clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-window-functions-frame) (last updated Sep 11, 2026)
- [Window functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-window-functions) (last updated Oct 5, 2026)
- [`xxhash64` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/xxhash64) (last updated Sep 11, 2026)
- [`zeroifnull` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/zeroifnull) (last updated Sep 11, 2026)
- [`||` (pipe pipe sign) operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/pipepipesign) (last updated Sep 11, 2026)
- [pyspark.sql.functions.monotonically_increasing_id](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.monotonically_increasing_id.html) (Apache Spark docs; no date shown)
