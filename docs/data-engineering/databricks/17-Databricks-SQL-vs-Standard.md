# 17. Databricks SQL vs standard SQL

*You already know SQL: SELECT, joins, GROUP BY, window functions. This chapter is about the parts of Databricks SQL that are different from the SQL you learned, or that do not exist in standard SQL at all. Some differences are conveniences (`QUALIFY`, `GROUP BY ALL`, `SELECT * EXCEPT`, pipe syntax) that make everyday data engineering queries shorter. Others are traps: backticks instead of double quotes for names, ANSI mode turning silent `NULL`s into errors, `SORT BY` that does not sort the whole result, and `NULL` comparisons that quietly drop rows. Interviewers like both kinds: the first shows you write idiomatic Databricks SQL, the second shows you have debugged real pipelines.*

!!! abstract "In this chapter"
    **You will learn:**

    - where Databricks SQL runs (SQL warehouses, the SQL editor, notebooks) and how to read the "Applies to" labels in the reference
    - what ANSI mode changes, and its defaults on SQL warehouses, Databricks Runtime and serverless compute
    - identifiers, backticks, case rules, string literals and comments
    - three-level names (`catalog.schema.table`), `USE CATALOG` / `USE SCHEMA`, and how Databricks resolves a name
    - the SELECT shortcuts: `QUALIFY`, `GROUP BY ALL`, `ORDER BY ALL`, `SELECT * EXCEPT`, lateral column aliases
    - reshaping with `PIVOT`, `UNPIVOT`, `LATERAL VIEW` and table-valued functions
    - Spark-specific clauses: `SORT BY`, `DISTRIBUTE BY`, `CLUSTER BY`, hints, `TABLESAMPLE`, `EXPLAIN`
    - set operators including `EXCEPT ALL`, `MINUS` and `INTERSECT ALL`
    - parameter markers (`:name`, `?`), the `IDENTIFIER` clause, session variables, named arguments (`=>`)
    - SQL pipe syntax (`|>`), NULL-safe comparison (`<=>`, `IS DISTINCT FROM`) and `MATCH_RECOGNIZE`
    - the PySpark DataFrame equivalent of each shortcut (`Window` + `row_number` for `QUALIFY`, `drop`, `pivot`, `unpivot`, `exceptAll`, `eqNullSafe`, `left_anti`)

    **You need:** chapter 3 (partitions and shuffles), chapter 5 (catalogs and schemas), chapter 6 (SQL warehouses), and general SQL from the [SQL course](../../databases/sql/index.md).

    **Levels:** sections 17.1 to 17.4 beginner, 17.5 to 17.9 and 17.11 intermediate, 17.10 and 17.12 expert.

Part IV goes deeper in later chapters: semi-structured data, `VARIANT` and higher-order functions are in [chapter 18](18-Semi-Structured-Data.md); the function library (dates, strings, `try_` functions, aggregates, window frames) is in chapter 19; `CREATE TABLE` options, `MERGE` extras, time travel and `CLONE` are in chapter 20; SQL scripting, UDFs, stored procedures and row filters are in chapter 21. This chapter only points to them.

**About the examples.** All "Run here" examples use the Red Rock Supply tables (`customers`, `products`, `orders`, `order_items`) in a schema called `silver`. On Databricks they would live in Unity Catalog as `shop.silver.orders`; locally there is no Unity Catalog, so the catalog is Spark's built-in `spark_catalog`. The scripts are in `src/ch17/` with their full output in the matching `.out` files. Error lines are shortened here to the error class and its first sentence. The `orders` table has 8 rows, and one of them (order 1008) has a `NULL` status on purpose.

Where a SQL feature has a short PySpark DataFrame equivalent, it is shown next to the SQL, because interviews ask for both. Those snippets come from `ex09_pyspark.py`, which runs each DataFrame version and compares its rows with the SQL version; the line `same rows as the SQL: True` in an output is that check. Generic SQL (joins, grouping, window functions, `MERGE`) is not repeated here; the [SQL course](../../databases/sql/index.md) covers it.

**What is and is not verified.** Every Databricks statement below comes from the official page cited next to it. Remarks about standard SQL and PostgreSQL are general background: they were not checked against the ISO standard or the PostgreSQL manual for this chapter (the PostgreSQL site could not be reached from the test machine). Where a local run disagreed with a Databricks page, or a claim could not be tested, the text says **not verified**.

## 17.1 Where Databricks SQL runs
*Level: beginner.*

"Databricks SQL" means two things, and interviewers sometimes mix them up. It is the **product** for data warehousing on Databricks (the SQL editor, dashboards, alerts, SQL warehouses), and it is the **SQL dialect** you write everywhere on the platform. The "Data warehousing on Databricks" page describes the product as "a cloud data warehouse built on lakehouse architecture" that "supports ANSI SQL with Delta Lake extensions".

You run Databricks SQL in three main places:

| Where | Compute | What to know |
| --- | --- | --- |
| **SQL editor** | a SQL warehouse | The browser editor for queries: autocomplete, parameter widgets, results, visualizations, version history. Opened from **SQL Editor** in the sidebar. |
| **Notebooks** | serverless compute, an all-purpose cluster, or a SQL warehouse | A SQL cell (or a `%sql` cell in a Python notebook) runs on whatever the notebook is attached to. When a notebook is attached to a SQL warehouse, only SQL and Markdown cells run; "running a cell in any other language (such as Python or R) throws an error". |
| **Jobs, dashboards, alerts, JDBC/ODBC tools** | a SQL warehouse (or job compute for notebooks) | Scheduled SQL, AI/BI dashboards and BI tools all send SQL to a warehouse. |

A **SQL warehouse** is "a compute resource that lets you query and explore data on Databricks", in three types (serverless, pro and classic); Databricks "recommends using serverless SQL warehouses when available". Chapter 6 covers the types, sizing and cost.

The dialect is the same everywhere, but versions differ. A SQL warehouse runs the Databricks SQL engine, which Databricks updates for you. A cluster runs a specific **Databricks Runtime** (DBR) version, for example 15.4 LTS or 17.3 LTS. That is why every page of the SQL reference starts with an **"Applies to"** label. The "How to use the SQL reference" page explains how to read it:

| Label on the page | Meaning |
| --- | --- |
| Databricks SQL, Databricks Runtime | all versions of both |
| Databricks SQL | SQL warehouses only |
| Databricks SQL, Databricks Runtime 11.3 LTS and above | all of Databricks SQL, and DBR 11.3 LTS or later |
| Databricks Runtime 11.3 LTS and above (no "Databricks SQL") | DBR only, not on SQL warehouses |

A parameter can have its own label that overrides the page's label. In this chapter each feature's label is quoted as the page states it.

!!! tip "In the interview"
    **"What is the difference between running SQL on a SQL warehouse and on a cluster?"** Both run Databricks SQL on Spark, but a SQL warehouse is compute built for SQL only (serverless, pro or classic, with Photon), versioned by Databricks, and used by the SQL editor, dashboards and BI tools. A cluster runs a chosen Databricks Runtime version and also runs Python, Scala and R. Feature availability follows the reference's "Applies to" label, so a feature marked "Databricks Runtime 18.0 and above" needs at least that runtime on a cluster.

Open-source Apache Spark SQL is the base of the dialect, and that is why most examples in this chapter run on the local Spark 4.2 engine. Where Databricks behaves differently, the text says so.

## 17.2 ANSI mode: errors instead of silent NULLs
*Level: beginner.*

**The problem.** Older Spark followed Hive's lenient rules. Divide by zero and you got `NULL`. Cast `'12.5kg'` to `INT` and you got `NULL`. Add 1 to the largest `TINYINT` and the value wrapped around to a negative number. Nothing failed, so bad data flowed straight into silver and gold tables, and someone found the hole weeks later in a report.

**The fix is ANSI mode**: the engine follows the SQL standard and raises an error for invalid operations. The `ANSI_MODE` page puts it this way: in non-ANSI mode, "arithmetic operations performed on numeric types may return overflowed values or NULL, while in ANSI mode such operations return an error."

Here is the same set of statements with ANSI mode on (the Spark 4 default) and then off.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT 1/0;
SELECT CAST('12.5kg' AS INT);
SELECT 127Y + 1Y;                 -- Y = TINYINT literal
SELECT CAST(12345 AS TINYINT);
SELECT CAST(5.1 AS INT);
SELECT typeof(5 - '3');
SELECT size(NULL);
-- then: SET spark.sql.ansi.enabled = false; and the same seven statements again
```

Output (from `ex10_compact.out`, one line per statement: the value, or the error class and the first sentence of the message):
```text
=== spark.sql.ansi.enabled = true ===
SELECT 1/0                      ERROR: [DIVIDE_BY_ZERO] Division by zero.
SELECT CAST('12.5kg' AS INT)    ERROR: [CAST_INVALID_INPUT] The value '12.5kg' of the type "STRING" cannot be cast to "INT" because it is malformed.
SELECT 127Y + 1Y                ERROR: [BINARY_ARITHMETIC_OVERFLOW] 127S + 1S caused overflow.
SELECT CAST(12345 AS TINYINT)   ERROR: [CAST_OVERFLOW] The value 12345 of the type "INT" cannot be cast to "TINYINT" due to an overflow.
SELECT CAST(5.1 AS INT)         5
SELECT typeof(5 - '3')          bigint
SELECT size(NULL)               NULL

=== spark.sql.ansi.enabled = false ===
SELECT 1/0                      NULL
SELECT CAST('12.5kg' AS INT)    NULL
SELECT 127Y + 1Y                -128
SELECT CAST(12345 AS TINYINT)   57
SELECT CAST(5.1 AS INT)         5
SELECT typeof(5 - '3')          double
SELECT size(NULL)               -1
```

The `try_` functions return `NULL` for one expression and leave the session's mode alone (chapter 19 lists them):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT try_divide(1, 0) AS a, try_cast('12.5kg' AS INT) AS b,
       try_add(127Y, 1Y) AS c, '42'::INT AS d;
```

Output (from `ex01_ansi.out`):
```text
+----+----+----+---+
|a   |b   |c   |d  |
+----+----+----+---+
|NULL|NULL|NULL|42 |
+----+----+----+---+
```

What ANSI mode changes, in four groups, from the `ANSI_MODE` page:

1. **Arithmetic**: overflow and division by zero raise errors (`1/0`, `1 % 0`, `127y + 1y`).
2. **Functions**: invalid input raises errors in functions such as `to_date`, `to_timestamp`, `make_date`, `element_at` with a missing key, and an array index out of range. `size(NULL)` returns `NULL` instead of `-1`.
3. **Explicit casts**: an invalid string (`cast('a' AS INTEGER)`) or a numeric overflow (`cast(12345 AS BYTE)`) raises an error. Some casts are rejected at compile time, for example `cast(TRUE AS TIMESTAMP)`.
4. **Implicit type coercion**: the rules become consistent. With ANSI off, "when using a STRING type with any arithmetic operator, the string is implicitly cast to DOUBLE", which is why `typeof(5 - '3')` is `double` above and `bigint` with ANSI on. With ANSI on, adding two string columns (`'5' + '7.6'`) is a type error; with ANSI off it returns 12.6.

A separate setting, `spark.sql.storeAssignmentPolicy`, controls casts during `INSERT`. It "defaults to `ANSI` and is independent of `spark.sql.ansi.enabled`". So inserting `'two'` into an `INT` column failed in the run even before ANSI mode was turned off:

```text
>>> INSERT INTO t_ins VALUES ('two')
ERROR: [CAST_INVALID_INPUT] The value 'two' of the type "STRING" cannot be cast to "INT" because it is malformed.
```

### The defaults, by compute type

| Compute | Setting | Default | Source page |
| --- | --- | --- | --- |
| SQL warehouse | `ANSI_MODE` | `TRUE` "for accounts created on or after October 19, 2022" | ANSI_MODE |
| Databricks Runtime (clusters) | `spark.sql.ansi.enabled` | "Enabled by default in Apache Spark 4.0 and Databricks Runtime 17.0 and above" | ANSI compliance in Databricks Runtime |
| Serverless notebooks and jobs | `spark.sql.ansi.enabled` | "ANSI mode is enabled by default" | Serverless compute limitations |

The `ANSI_MODE` page carries the label "Applies to: Databricks SQL". On a warehouse you change it per session with `SET`, or an admin changes it for all warehouses in the workspace's SQL configuration parameters.

*Databricks only, not run here. Syntax from [ANSI_MODE](https://docs.databricks.com/aws/en/sql/language-manual/parameters/ansi_mode).*
```sql
SET ansi_mode = false;   -- this session only, on a SQL warehouse
SELECT cast('a' AS INTEGER);   -- NULL instead of an error
```

On serverless compute you can set `spark.sql.ansi.enabled` to `false`, but the serverless migration page notes that serverless "applies ANSI rules to implicit casts on table inserts regardless of this setting, because `spark.sql.storeAssignmentPolicy` cannot be changed on serverless compute."

!!! warning "Upgrading a cluster can break a working job"
    A job that ran for years on DBR 15.4 LTS can fail after moving to DBR 17.x or to serverless with `CAST_INVALID_INPUT` or `DIVIDE_BY_ZERO`, because ANSI mode is now on by default. The data did not change; the rules did. Databricks recommends replacing the failing operation with its `try_` form (`try_cast`, `try_divide`, `try_add`) "instead of disabling ANSI mode, because ANSI mode surfaces data quality issues that a silent `NULL` hides."

Two shorthand casts are worth knowing. `expr::type` is a synonym for `cast` ("Applies to: Databricks SQL Databricks Runtime"), and it ran here (`'42'::INT` above). `expr ?:: type` is a synonym for `try_cast`; its page says "Applies to: Databricks Runtime 15.3 and above". It did not parse on open-source Spark 4.2. Because the label does not list Databricks SQL, it should not work on a SQL warehouse; that is **not verified**.

*Databricks only, not run here. Syntax from [`?::` (question double colon sign) operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/questiondoublecolonsign).*
```sql
SELECT '20' ?:: INTEGER;       -- 20
SELECT 'twenty' ?:: INTEGER;   -- NULL
```

!!! note "One difference found while testing"
    The `ANSI_MODE` page lists `cast(5.1 AS INTEGER)` as an error under ANSI mode ("Truncation"). On open-source Spark 4.2 with ANSI mode on, the same cast returned `5` (see the output above). **Not verified** on a SQL warehouse: test decimal-to-integer truncation on your own warehouse before relying on either behavior.

!!! tip "In the interview"
    **"What does ANSI mode do, and is it on?"** It makes Spark SQL follow the standard: overflow, division by zero, malformed casts and invalid function input raise errors instead of returning `NULL` or a wrapped value, and implicit casts follow consistent type-precedence rules. It is on by default on SQL warehouses (accounts created since October 19, 2022), on Databricks Runtime 17.0 and above, and on serverless. When bad values are expected, use `try_cast` or `try_divide` on that column rather than turning ANSI mode off for the whole job.

## 17.3 Identifiers, case, literals and comments
*Level: beginner.*

### Backticks, not double quotes

In standard SQL and PostgreSQL, `"order total"` is a quoted identifier (a column name). In Databricks SQL, names that need quoting go in **backticks**: the Identifiers page says Databricks supports "delimited identifiers, which are enclosed within backticks." Double quotes make a **string literal** (allowed, though the STRING type page says this "is discouraged as it is not standard SQL"). That one difference causes a classic bug, shown in practice question 6: `SELECT "order_id" FROM orders` returns the text `order_id` on every row.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT ORDER_ID, Amount FROM ORDERS WHERE Order_Id = 1001;

SELECT amount   AS `order total ($)`,
       currency AS `cur-code`,
       1        AS `a``b`
FROM orders WHERE order_id = 1001;

SELECT amount AS order-total FROM orders WHERE order_id = 1001;
```

Output:
```text
+--------+------+
|ORDER_ID|Amount|
+--------+------+
|1001    |59.90 |
+--------+------+

+---------------+--------+---+
|order total ($)|cur-code|a`b|
+---------------+--------+---+
|59.90          |CAD     |1  |
+---------------+--------+---+

ERROR: [INVALID_IDENTIFIER] The unquoted identifier order-total is invalid and must be back quoted as: `order-total`.
```

The rules from the Identifiers and Names pages:

- **Case.** "Identifiers are case-insensitive when referenced." `ORDERS`, `Orders` and `orders` are the same table. Unity Catalog "stores all object names as lowercase", but it "preserves column name casing" while queries stay case-insensitive. Standard SQL folds unquoted names to upper case and PostgreSQL folds them to lower case; in both, a quoted name becomes case-sensitive. Databricks has no case-sensitive mode for names in normal use, so you cannot have two columns that differ only in case.
- **Regular identifiers** use ASCII letters, digits and `_`. Anything else (space, hyphen, non-ASCII letters such as `Ä`) needs backticks. A backtick inside a name is doubled: `` `a``b` ``.
- **Unity Catalog object names** cannot exceed 255 characters, and a period, space or forward slash is not allowed even with backticks.
- **Reserved words.** Databricks "does not formally disallow any specific literals from being used as identifiers", but a few words (`JOIN`, `LEFT`, `UNION`, `EXCEPT`, `MINUS` and others) need backticks when used as a table alias. Locally `SELECT 1 AS select` worked, while `... AS left(a)` was a syntax error. In Databricks Runtime, setting both `spark.sql.ansi.enabled` and `spark.sql.ansi.enforceReservedKeywords` to true makes ANSI reserved words unusable as plain identifiers (`enforceReservedKeywords` is `false` by default).

### String literals

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT 'Red Rock' AS single_q, "Red Rock" AS double_q,
       'O\'Neil' AS escaped, 'Red ' 'Rock ' 'Supply' AS chained;
SELECT length('C:\new') AS regular_len, length(r'C:\new') AS raw_len;
```

Output:
```text
+--------+--------+-------+---------------+
|single_q|double_q|escaped|chained        |
+--------+--------+-------+---------------+
|Red Rock|Red Rock|O'Neil |Red Rock Supply|
+--------+--------+-------+---------------+

+-----------+-------+
|regular_len|raw_len|
+-----------+-------+
|5          |6      |
+-----------+-------+
```

Three things differ from standard SQL here:

- **Backslash escapes.** In a regular literal, `\n` is a newline, `\t` a tab, `\'` a single quote, `\\` one backslash. So `'C:\new'` holds 5 characters (`C`, `:`, newline, `e`, `w`). Standard SQL has no backslash escapes; you double the quote (`'O''Neil'`).
- **Raw literals** with an `r` prefix have no escape character, so `r'C:\new'` is 6 characters. Useful for regular expressions and Windows paths. "Applies to: Databricks SQL Databricks Runtime 10.4 LTS and above".
- **Chained literals**: adjacent literals join without `||` or `concat`. The STRING type page labels this "Applies to: Databricks Runtime 18.0 and later"; it also ran on Spark 4.2 here.

!!! warning "The `$` in notebooks"
    The STRING type page warns that in a Databricks notebook "the `$` (dollar) sign introduces a widget and needs to be escaped with `\$` to be preserved in a string literal." `SELECT 'Hou$e'` in a notebook cell can come back as `Hou`.

### Comments

`--` starts a comment to the end of the line, and `/* ... */` is a bracketed comment. Bracketed comments **nest** in Databricks SQL: `/* outer /* nested */ still a comment */` is one comment. That ran here and returned `1` for `SELECT /* outer /* nested */ still a comment */ 1 AS x`. A comment that starts with `/*+` is not ignored: it is a **hint** (section 17.8).

## 17.4 Three-level names and name resolution
*Level: beginner.*

**The problem.** A warehouse used to have one namespace: `schema.table`. With Unity Catalog, a workspace sees many catalogs (`shop`, `finance`, `system`, `samples`), and the same schema name (`silver`) can exist in several of them. You need a way to say exactly which table you mean, and a way to stop typing the catalog in every query.

**The three-level name** `catalog.schema.table` names one table uniquely (chapter 5 explains the hierarchy). `USE CATALOG` and `USE SCHEMA` set the defaults for shorter names.

*Databricks only, not run here. Syntax from [USE CATALOG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-use-catalog).*
```sql
USE CATALOG shop;             -- also resets the current schema to `default`
USE SCHEMA silver;
SELECT current_catalog(), current_schema();   -- shop  silver
SELECT * FROM orders;                         -- shop.silver.orders
SELECT * FROM gold.daily_sales;               -- shop.gold.daily_sales
SELECT * FROM finance.ledger.entries;         -- another catalog, fully qualified
```

Labels: `USE CATALOG` "Applies to: Databricks SQL Databricks Runtime 10.4 LTS and above, Unity Catalog only"; `USE SCHEMA` "Applies to: Databricks SQL Databricks Runtime 10.4 LTS and above". Two details from those pages are popular interview checks: **setting the catalog resets the schema to `default`**, and `USE SCHEMA main.my_schema` sets both catalog and schema at once. `SCHEMA`, `DATABASE` and `NAMESPACE` are interchangeable keywords, and `SCHEMA` is preferred.

Locally the only catalog is `spark_catalog`, but the schema part works the same:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT current_catalog() AS cat, current_schema() AS sch;
USE SCHEMA silver;
SELECT current_catalog() AS cat, current_schema() AS sch;
SELECT (SELECT count(*) FROM spark_catalog.silver.orders) AS three_part,
       (SELECT count(*) FROM silver.orders)               AS two_part,
       (SELECT count(*) FROM orders)                      AS one_part;
```

Output:
```text
+-------------+-------+
|cat          |sch    |
+-------------+-------+
|spark_catalog|default|
+-------------+-------+

+-------------+------+
|cat          |sch   |
+-------------+------+
|spark_catalog|silver|
+-------------+------+

+----------+--------+--------+
|three_part|two_part|one_part|
+----------+--------+--------+
|8         |8       |8       |
+----------+--------+--------+
```

(The first two results are from `ex02_names.out`, the last from `ex10_compact.out`.)

### How Databricks finds a table

The Name resolution page gives the rules. A **qualified** name is completed from the session: three parts are unique, and two parts (`silver.orders`) get the current catalog in front. An **unqualified** name (`orders`) is looked up in order: first a **common table expression** (CTE) in scope, starting with the nearest `WITH`; then the session's temporary views and tables; then the current schema. If nothing matches, you get `TABLE_OR_VIEW_NOT_FOUND`.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="How Databricks resolves a table name: three-part names are unique, two-part names get the current catalog, one-part names are looked up as a CTE, then a temporary view, then the current schema.">
  <g font-family="sans-serif" font-size="13" fill="currentColor">
    <rect x="10" y="20" width="170" height="40" rx="6" fill="none" stroke="currentColor"/>
    <text x="95" y="45" text-anchor="middle">shop.silver.orders</text>
    <rect x="200" y="20" width="430" height="40" rx="6" fill="none" stroke="currentColor"/>
    <text x="415" y="45" text-anchor="middle">three parts: unique, used as written</text>
    <line x1="180" y1="40" x2="196" y2="40" stroke="currentColor"/>
    <polygon points="196,36 200,40 196,44" fill="currentColor"/>

    <rect x="10" y="80" width="170" height="40" rx="6" fill="none" stroke="currentColor"/>
    <text x="95" y="105" text-anchor="middle">silver.orders</text>
    <rect x="200" y="80" width="430" height="40" rx="6" fill="none" stroke="currentColor"/>
    <text x="415" y="105" text-anchor="middle">two parts: current_catalog() is added in front</text>
    <line x1="180" y1="100" x2="196" y2="100" stroke="currentColor"/>
    <polygon points="196,96 200,100 196,104" fill="currentColor"/>

    <rect x="10" y="150" width="170" height="40" rx="6" fill="none" stroke="currentColor"/>
    <text x="95" y="175" text-anchor="middle">orders</text>
    <line x1="180" y1="170" x2="196" y2="170" stroke="currentColor"/>
    <polygon points="196,166 200,170 196,174" fill="currentColor"/>
    <rect x="200" y="150" width="125" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="2"/>
    <text x="262" y="175" text-anchor="middle">1. CTE in scope</text>
    <line x1="325" y1="170" x2="339" y2="170" stroke="currentColor"/>
    <polygon points="339,166 343,170 339,174" fill="currentColor"/>
    <rect x="343" y="150" width="150" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="2"/>
    <text x="418" y="175" text-anchor="middle">2. temp view / table</text>
    <line x1="493" y1="170" x2="507" y2="170" stroke="currentColor"/>
    <polygon points="507,166 511,170 507,174" fill="currentColor"/>
    <rect x="511" y="150" width="119" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="2"/>
    <text x="570" y="175" text-anchor="middle">3. current schema</text>
    <text x="415" y="212" text-anchor="middle">not found at a step: go to the next one; first match wins</text>
    <text x="415" y="236" text-anchor="middle">nothing matched: TABLE_OR_VIEW_NOT_FOUND</text>
    <text x="320" y="272" text-anchor="middle">Databricks SQL and DBR 19+: steps 2 and 3 follow the PATH setting</text>
    <text x="320" y="290" text-anchor="middle">(default PATH: system.session, system.builtin, system.ai, CURRENT_SCHEMA)</text>
  </g>
</svg>
<figcaption>Figure 17.1. Table name resolution. A CTE shadows a temporary view, and a temporary view shadows a table with the same name in the current schema. Qualify the name to skip the shadowing.</figcaption>
</figure>

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE TEMPORARY VIEW orders AS SELECT 'temp view' AS src;
SELECT * FROM orders;                               -- the temp view
SELECT count(*) AS n FROM silver.orders;            -- the table
WITH orders AS (SELECT 'cte' AS src) SELECT * FROM orders;   -- the CTE
```

Output:
```text
+---------+
|src      |
+---------+
|temp view|
+---------+

+---+
|n  |
+---+
|8  |
+---+

+---+
|src|
+---+
|cte|
+---+
```

In Databricks SQL and Databricks Runtime 19 and above, unqualified names follow a **schema search path**, the `PATH` parameter. Its system default is `system.session, system.builtin, system.ai, CURRENT_SCHEMA`: temporary objects live in `system.session`, built-in functions in `system.builtin`, and your current schema is the last entry. In Databricks Runtime 18 and below the order was fixed (temporary view, then the current schema). For tables, both orders give the result shown above. A persistent view captures the path when it is created, so a later `USE SCHEMA` by the reader does not change what the view reads.

!!! warning "A temporary view can hide a real table"
    If a notebook creates `CREATE TEMP VIEW orders AS ...` for testing, every later `SELECT * FROM orders` in that session reads the view, not `shop.silver.orders`. Production code should use fully qualified names, or at least `schema.table`, so a stray temp view or `USE` statement cannot redirect it.

### Lateral column aliases

Standard SQL does not let a SELECT expression use an alias defined earlier in the same SELECT list. Databricks does: the Name resolution page calls it **lateral column aliasing** ("Applies to: Databricks SQL Databricks Runtime 12.2 LTS and above").

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, amount * 0.05 AS tax, amount + tax AS total
FROM orders WHERE order_id IN (1001, 1002) ORDER BY order_id;
```

Output:
```text
+--------+-------+--------+
|order_id|tax    |total   |
+--------+-------+--------+
|1001    |2.9950 |62.8950 |
|1002    |12.4500|261.4500|
+--------+-------+--------+
```

A real column wins over a lateral alias with the same name: if `orders` had a column called `tax`, `amount + tax` would use the column.

In PySpark each `withColumn` sees the columns added before it, so the same idea is a chain:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
from decimal import Decimal
from pyspark.sql import functions as F

(orders.filter(F.col("order_id").isin(1001, 1002))
       .withColumn("tax", F.col("amount") * F.lit(Decimal("0.05")))
       .withColumn("total", F.col("amount") + F.col("tax"))
       .select("order_id", "tax", "total"))
```

```text
same rows as the SQL: True
```

The `Decimal` matters: the first run used the Python float `0.05`, which made `tax` a `DOUBLE`, and the rows no longer matched the SQL result, where the literal `0.05` is a `DECIMAL`.

## 17.5 SELECT shortcuts: QUALIFY, GROUP BY ALL, ORDER BY ALL, * EXCEPT
*Level: intermediate.*

These four features exist to remove boilerplate that every data engineer writes daily. First, a picture of when each clause takes effect.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 260" role="img" aria-label="Logical order of SELECT clause evaluation in Databricks SQL, in ten steps from FROM to LIMIT, with QUALIFY after window functions.">
  <g font-family="sans-serif" font-size="13" fill="currentColor">
    <rect x="10" y="30" width="108" height="56" rx="6" fill="none" stroke="currentColor"/>
    <text x="64" y="53" text-anchor="middle">1. FROM, JOIN</text>
    <text x="64" y="72" text-anchor="middle">PIVOT, TVFs</text>
    <rect x="138" y="30" width="108" height="56" rx="6" fill="none" stroke="currentColor"/>
    <text x="192" y="63" text-anchor="middle">2. WHERE</text>
    <rect x="266" y="30" width="108" height="56" rx="6" fill="none" stroke="currentColor"/>
    <text x="320" y="53" text-anchor="middle">3. GROUP BY</text>
    <text x="320" y="72" text-anchor="middle">(or ALL)</text>
    <rect x="394" y="30" width="108" height="56" rx="6" fill="none" stroke="currentColor"/>
    <text x="448" y="63" text-anchor="middle">4. HAVING</text>
    <rect x="522" y="30" width="108" height="56" rx="6" fill="none" stroke="currentColor"/>
    <text x="576" y="53" text-anchor="middle">5. window</text>
    <text x="576" y="72" text-anchor="middle">functions</text>
    <line x1="118" y1="58" x2="134" y2="58" stroke="currentColor"/><polygon points="134,54 138,58 134,62" fill="currentColor"/>
    <line x1="246" y1="58" x2="262" y2="58" stroke="currentColor"/><polygon points="262,54 266,58 262,62" fill="currentColor"/>
    <line x1="374" y1="58" x2="390" y2="58" stroke="currentColor"/><polygon points="390,54 394,58 390,62" fill="currentColor"/>
    <line x1="502" y1="58" x2="518" y2="58" stroke="currentColor"/><polygon points="518,54 522,58 518,62" fill="currentColor"/>
    <line x1="576" y1="86" x2="576" y2="146" stroke="currentColor"/><polygon points="572,146 576,150 580,146" fill="currentColor"/>
    <rect x="522" y="150" width="108" height="56" rx="6" fill="none" stroke="currentColor" stroke-width="3"/>
    <text x="576" y="183" text-anchor="middle">6. QUALIFY</text>
    <rect x="394" y="150" width="108" height="56" rx="6" fill="none" stroke="currentColor"/>
    <text x="448" y="173" text-anchor="middle">7. SELECT list</text>
    <text x="448" y="192" text-anchor="middle">DISTINCT</text>
    <rect x="266" y="150" width="108" height="56" rx="6" fill="none" stroke="currentColor"/>
    <text x="320" y="173" text-anchor="middle">8. UNION,</text>
    <text x="320" y="192" text-anchor="middle">EXCEPT ...</text>
    <rect x="138" y="150" width="108" height="56" rx="6" fill="none" stroke="currentColor" stroke-dasharray="5 3"/>
    <text x="192" y="173" text-anchor="middle">9. ORDER BY</text>
    <text x="192" y="192" text-anchor="middle">or SORT BY</text>
    <rect x="10" y="150" width="108" height="56" rx="6" fill="none" stroke="currentColor"/>
    <text x="64" y="173" text-anchor="middle">10. LIMIT</text>
    <text x="64" y="192" text-anchor="middle">OFFSET</text>
    <line x1="522" y1="178" x2="506" y2="178" stroke="currentColor"/><polygon points="506,174 502,178 506,182" fill="currentColor"/>
    <line x1="394" y1="178" x2="378" y2="178" stroke="currentColor"/><polygon points="378,174 374,178 378,182" fill="currentColor"/>
    <line x1="266" y1="178" x2="250" y2="178" stroke="currentColor"/><polygon points="250,174 246,178 250,182" fill="currentColor"/>
    <line x1="138" y1="178" x2="122" y2="178" stroke="currentColor"/><polygon points="122,174 118,178 122,182" fill="currentColor"/>
    <text x="320" y="238" text-anchor="middle">thick box: Databricks extra; dashed box: SORT BY / DISTRIBUTE BY / CLUSTER BY replace ORDER BY</text>
  </g>
</svg>
<figcaption>Figure 17.2. The logical order in which a query's clauses take effect (a mental model; the optimizer may execute things in a different physical order). QUALIFY filters after window functions are computed, the same way HAVING filters after GROUP BY. The pipe operators of section 17.10 come after LIMIT and OFFSET in the query grammar.</figcaption>
</figure>

### QUALIFY

**The problem.** You cannot use a window function in `WHERE`, because `WHERE` runs before window functions are computed (step 2 vs step 5 in Figure 17.2). The classic workaround wraps the query in a subquery or CTE and filters the window result outside. The most common case in data engineering is **deduplication**: keep the latest row per key.

**QUALIFY** "filters the results of window functions" ("Applies to: Databricks SQL Databricks Runtime 10.4 LTS and above"). It is to window functions what `HAVING` is to aggregates.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
-- customer_updates has 6 rows: 2 versions of customer 1, 1 of customer 2, 3 of customer 3
SELECT customer_id, city, updated_at
FROM customer_updates
QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY updated_at DESC) = 1
ORDER BY customer_id;

-- the same without QUALIFY
SELECT customer_id, city, updated_at
FROM (SELECT *, row_number() OVER (PARTITION BY customer_id ORDER BY updated_at DESC) AS rn
      FROM customer_updates)
WHERE rn = 1
ORDER BY customer_id;
```

Output (both queries):
```text
+-----------+------+-------------------+
|customer_id|city  |updated_at         |
+-----------+------+-------------------+
|1          |Banff |2026-02-10 10:00:00|
|2          |Denver|2026-01-07 12:30:00|
|3          |Golden|2026-02-20 15:00:00|
+-----------+------+-------------------+
```

Rules from the QUALIFY page: at least one window function must appear in the SELECT list or the QUALIFY clause, and the QUALIFY expressions "cannot contain aggregate functions". Breaking the first rule:

```text
>>> SELECT customer_id FROM customer_updates QUALIFY customer_id > 1
ERROR: [QUALIFY_REQUIRES_WINDOW_FUNCTION] The QUALIFY clause requires at least one window function in the current SELECT list or the QUALIFY condition.
```

The DataFrame API has no `QUALIFY`. You compute the window column, filter on it and drop it:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
from pyspark.sql import Window, functions as F

w = Window.partitionBy("customer_id").orderBy(F.col("updated_at").desc())
latest = (spark.table("customer_updates")
          .withColumn("rn", F.row_number().over(w))
          .filter(F.col("rn") == 1)
          .select("customer_id", "city", "updated_at")
          .orderBy("customer_id"))
latest.show(truncate=False)
```

Output (from `ex09_pyspark.out`):
```text
+-----------+------+-------------------+
|customer_id|city  |updated_at         |
+-----------+------+-------------------+
|1          |Banff |2026-02-10 10:00:00|
|2          |Denver|2026-01-07 12:30:00|
|3          |Golden|2026-02-20 15:00:00|
+-----------+------+-------------------+

same rows as the SQL: True
```

`row_number()` keeps exactly one row per key even with ties; `rank()` keeps all tied rows. The SQL course's [ranking chapter](../../databases/sql/13-Window-Functions-Ranking.md) covers the difference, and [Duplicates and incremental loads](../../databases/sql/22-Duplicates-and-Incremental-Loads.md) covers dedup patterns.

!!! tip "In the interview"
    **"Deduplicate a bronze table, keeping the latest record per order."** `SELECT * FROM bronze_orders QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY ingest_ts DESC) = 1`. Mention why `row_number()` and not `rank()` (ties would keep duplicates), and that the `ORDER BY` inside `OVER` must be deterministic, or reruns can pick different rows. Using `QUALIFY` signals you know the dialect. If asked for DataFrame code: `Window.partitionBy("order_id").orderBy(F.col("ingest_ts").desc())`, then `withColumn("rn", F.row_number().over(w)).filter("rn = 1").drop("rn")`.

### GROUP BY ALL and ORDER BY ALL

`GROUP BY ALL` is "a shorthand notation to add all SELECT-list expressions not containing aggregate functions as `group_expression`s" ("Applies to: Databricks SQL Databricks Runtime 12.2 LTS and above"). `ORDER BY ALL` sorts by every SELECT-list expression in order; a direction given once (`ORDER BY ALL DESC`) applies to each of them (also 12.2 LTS and above).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT c.country, o.currency, count(*) AS orders, sum(o.amount) AS revenue
FROM orders o JOIN customers c USING (customer_id)
GROUP BY ALL
ORDER BY ALL;

SELECT country, city FROM customers ORDER BY ALL DESC;

SELECT customer_id, amount * count(*) AS x FROM orders GROUP BY ALL;
```

Output:
```text
+-------+--------+------+-------+
|country|currency|orders|revenue|
+-------+--------+------+-------+
|CA     |CAD     |4     |645.40 |
|US     |USD     |4     |476.95 |
+-------+--------+------+-------+

+-------+---------+
|country|city     |
+-------+---------+
|US     |Moab     |
|US     |Denver   |
|CA     |Vancouver|
|CA     |Calgary  |
+-------+---------+

ERROR: [MISSING_AGGREGATION] The non-aggregating expression "amount" is based on columns which are not participating in the GROUP BY clause.
```

The last query shows the limit of `GROUP BY ALL`: the expression `amount * count(*)` contains an aggregate, so it is not added to the grouping list, but it also uses the plain column `amount`. The page warns that `GROUP BY ALL` "is not guaranteed to produce a set of group expressions which can be resolved". If the SELECT list has no non-aggregate expression at all, `GROUP BY ALL` is the same as no `GROUP BY` (one global row).

PySpark has no `GROUP BY ALL`: `groupBy()` always names its columns.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
(orders.join(customers, "customer_id")
       .groupBy("country", "currency")
       .agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue"))
       .orderBy("country", "currency"))
```

```text
same rows as the SQL: True
```

!!! warning "GROUP BY ALL changes with the SELECT list"
    With `GROUP BY ALL`, adding a column to the SELECT list silently adds it to the grouping, which changes the grain of the result (for example, from one row per country to one row per country and city). That is usually what you want in exploration, but in a gold table it can double row counts without any error. In production models, some teams prefer explicit grouping columns for that reason.

### SELECT * EXCEPT

`* EXCEPT (col, ...)` "prunes columns or fields from the referenceable set of columns" ("Applies to: Databricks SQL Databricks Runtime 11.3 LTS and above"). It is handy for dropping audit columns, PII or a duplicated join key.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT * EXCEPT (email, updated_at) FROM customers ORDER BY customer_id;

SELECT * EXCEPT (o.customer_id)
FROM orders o JOIN customers c ON o.customer_id = c.customer_id LIMIT 1;
```

Output:
```text
+-----------+------------+---------+-------+
|customer_id|name        |city     |country|
+-----------+------------+---------+-------+
|1          |Ana Lopez   |Calgary  |CA     |
|2          |Ben Okafor  |Denver   |US     |
|3          |Chloe Martin|Moab     |US     |
|4          |Dev Patel   |Vancouver|CA     |
+-----------+------------+---------+-------+

+--------+-------------------+-------+------+--------+-----------+---------+---------------+-------+-------+-------------------+
|order_id|order_ts           |status |amount|currency|customer_id|name     |email          |city   |country|updated_at         |
+--------+-------------------+-------+------+--------+-----------+---------+---------------+-------+-------+-------------------+
|1001    |2026-03-01 10:15:00|SHIPPED|59.90 |CAD    |1          |Ana Lopez|ana@example.com|Calgary|CA     |2026-01-05 09:00:00|
+--------+-------------------+-------+------+--------+-----------+---------+---------------+-------+-------+-------------------+
```

The second query keeps only one `customer_id` (the one from `c`). The star page adds three details: you can remove a **field** of a struct (`* EXCEPT (c2.b)`); naming a column twice raises `EXCEPT_OVERLAPPING_COLUMNS`; and the hidden `_metadata` column is never part of `*` (chapter 8 uses it). Before Databricks Runtime 15.0 the star clause could only appear in the SELECT list; newer versions also allow it in places such as function arguments (`array(*)`, `coalesce(TA.*)`).

The DataFrame equivalent is `drop`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
df = customers.drop("email", "updated_at")
print(df.columns)
```

```text
['customer_id', 'name', 'city', 'country']
same rows as the SQL: True
```

### Aggregate FILTER

`agg(...) FILTER (WHERE condition)` is standard SQL, not a Databricks extra, so this chapter does not teach it; Databricks supports it, and PIVOT (section 17.6) is defined in terms of it. Practice question 17 shows the `NULL` trap it shares with every other filter.

### When an alias and a column share a name

`HAVING`, `ORDER BY` and `QUALIFY` can use SELECT-list aliases as well as table columns. When a name matches both, the Name resolution page says: "`ORDER BY` prefers the `SELECT` list alias", "`HAVING` prefers the table column", and "`QUALIFY` prefers the table column over the `SELECT` list alias (same as `HAVING`)". The page's own examples ran here:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE TEMPORARY VIEW t(a, b) AS VALUES (1, 10), (2, 20), (3, 30);
SELECT -a AS a FROM t ORDER BY a LIMIT 1;
SELECT sum(b) AS a FROM t GROUP BY a HAVING a > 1;
SELECT -row_number() OVER (ORDER BY b) AS a FROM t QUALIFY a > 1;
```

Output:
```text
+---+
|a  |
+---+
|-3 |
+---+

+---+
|a  |
+---+
|20 |
|30 |
+---+

+---+
|a  |
+---+
+---+
```

The first two match the Databricks page. The third differs: the Databricks page shows `-2` and `-3` (QUALIFY used the column `a`), while open-source Spark 4.2 returned no rows, which means it used the alias (all aliases are negative, so `a > 1` is never true). Which of the two a current SQL warehouse does is **not verified**. The lesson is the same on both engines: **never give an alias the name of an existing column** if you then filter or sort on it.

## 17.6 Reshaping: PIVOT, UNPIVOT, LATERAL VIEW and table-valued functions
*Level: intermediate.*

### PIVOT

**The problem.** A report wants one row per product category and one column per currency. In standard SQL you write one `sum(CASE WHEN currency = 'CAD' THEN ... END)` per column. **PIVOT** "transforms the rows of the preceding table_reference by rotating unique values of a specified column list into separate columns" ("Applies to: Databricks SQL Databricks Runtime").

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT * FROM (
  SELECT p.category, o.currency, oi.qty * oi.unit_price AS line_amount
  FROM order_items oi
  JOIN orders o   ON o.order_id = oi.order_id
  JOIN products p ON p.product_id = oi.product_id)
PIVOT (sum(line_amount) FOR currency IN ('CAD' AS cad, 'USD' AS usd))
ORDER BY category;
```

Output:
```text
+--------+------+------+
|category|cad   |usd   |
+--------+------+------+
|Apparel |318.00|159.00|
|Camping |189.50|249.00|
|Hiking  |137.90|68.95 |
+--------+------+------+
```

How it works, from the PIVOT page: every column of the input that is not used in an aggregate or in the `FOR` list becomes a **grouping column** (here `category`). For each value in the `IN` list, PIVOT makes one column whose cell is the aggregate computed with `FILTER (WHERE currency IN (...))`. With two aggregates, the columns are named `alias_aggalias`:

```text
PIVOT (sum(qty) AS units, count(*) AS lines FOR currency IN ('CAD' AS cad, 'USD' AS usd))
+--------+---------+---------+---------+---------+
|category|cad_units|cad_lines|usd_units|usd_lines|
+--------+---------+---------+---------+---------+
|Apparel |2        |1        |1        |1        |
|Camping |1        |1        |1        |1        |
|Hiking  |4        |2        |2        |2        |
+--------+---------+---------+---------+---------+
```

In PySpark, `pivot` sits between `groupBy` and the aggregate. Give the values list: the PySpark docstring calls the form without it "less efficient", because Spark first has to compute the distinct values.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
(lines.groupBy("category")              # lines: category, currency, line_amount
      .pivot("currency", ["CAD", "USD"])
      .agg(F.sum("line_amount"))
      .orderBy("category"))
```

Output (from `ex09_pyspark.out`):
```text
+--------+------+------+
|category|CAD   |USD   |
+--------+------+------+
|Apparel |318.00|159.00|
|Camping |189.50|249.00|
|Hiking  |137.90|68.95 |
+--------+------+------+

same rows as the SQL: True
```

The columns are named after the values (`CAD`, `USD`); rename them with `withColumnRenamed` if you need `cad` and `usd`.

!!! warning "PIVOT traps"
    - The `IN` values must be **literals**; a subquery gives `NON_LITERAL_PIVOT_VALUES`. You must know the output columns when you write the query.
    - Extra columns in the input become grouping columns. Selecting `o.order_id` in the inner query would give one row per order instead of per category. Always pivot from a subquery that has exactly the grouping, pivot and value columns.
    - A value not in the `IN` list is silently dropped, and a combination with no rows gives `NULL`, not 0.

### UNPIVOT

UNPIVOT does the opposite: it rotates columns into rows ("Applies to: Databricks SQL Databricks Runtime 12.2 LTS and above"). Rows whose value is `NULL` are removed by default (`EXCLUDE NULLS`); `INCLUDE NULLS` keeps them.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE TEMPORARY VIEW targets(category, jan, feb, mar) AS VALUES
  ('Camping', 1000, 1200, NULL),
  ('Hiking',   400,  450,  500);

SELECT * FROM targets
UNPIVOT (target FOR month IN (jan, feb, mar))
ORDER BY category, month;

SELECT * FROM targets
UNPIVOT INCLUDE NULLS (target FOR month IN (jan, feb, mar))
WHERE category = 'Camping' ORDER BY month;
```

Output:
```text
+--------+-----+------+
|category|month|target|
+--------+-----+------+
|Camping |feb  |1200  |
|Camping |jan  |1000  |
|Hiking  |feb  |450   |
|Hiking  |jan  |400   |
|Hiking  |mar  |500   |
+--------+-----+------+

+--------+-----+------+
|category|month|target|
+--------+-----+------+
|Camping |feb  |1200  |
|Camping |jan  |1000  |
|Camping |mar  |NULL  |
+--------+-----+------+
```

The name column (`month`) is a `STRING`, and the value column gets the least common type of the unpivoted columns. If they have no common type, you get `UNPIVOT_VALUE_DATA_TYPE_MISMATCH`.

The PySpark `unpivot` method has a different default: it **keeps** `NULL` values, like `INCLUDE NULLS`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
up = spark.table("targets").unpivot("category", ["jan", "feb", "mar"], "month", "target")
up.orderBy("category", "month").show(truncate=False)
up.dropna(subset=["target"])     # the SQL default (EXCLUDE NULLS)
```

Output (from `ex09_pyspark.out`; the two checks compare with `UNPIVOT INCLUDE NULLS` and with plain `UNPIVOT`):
```text
+--------+-----+------+
|category|month|target|
+--------+-----+------+
|Camping |feb  |1200  |
|Camping |jan  |1000  |
|Camping |mar  |NULL  |
|Hiking  |feb  |450   |
|Hiking  |jan  |400   |
|Hiking  |mar  |500   |
+--------+-----+------+

same rows as the SQL: True

same rows as the SQL: True
```

### LATERAL VIEW and table-valued functions

**The problem.** Raw order events carry an array of items. To get one row per item, you apply a **generator** function such as `explode` to each row and join the generated rows back to their parent row.

The old Hive syntax is `LATERAL VIEW`. The reference now says: "In Databricks SQL and starting with Databricks Runtime 12.2 this clause is deprecated. You should invoke a table valued generator function as a table_reference." A **table-valued function** (TVF) is a function that returns rows, called in `FROM`. With the keyword `LATERAL`, it can use columns of the tables to its left.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
-- raw_orders: 1001 has 1 item, 1009 has 2 items, 1010 has an empty array
-- old style
SELECT order_id, item.product_id, item.qty
FROM raw_orders LATERAL VIEW explode(items) x AS item
ORDER BY order_id, item.product_id;

-- recommended style: a TVF in FROM
SELECT r.order_id, i.col.product_id, i.col.qty
FROM raw_orders r, LATERAL explode(r.items) AS i
ORDER BY r.order_id, i.col.product_id;

-- keep orders with no items
SELECT r.order_id, i.col.product_id
FROM raw_orders r, LATERAL explode_outer(r.items) AS i
ORDER BY r.order_id, i.col.product_id;
```

Output:
```text
+--------+----------+---+
|order_id|product_id|qty|
+--------+----------+---+
|1001    |3         |2  |
|1009    |1         |1  |
|1009    |4         |3  |
+--------+----------+---+

+--------+----------+
|order_id|product_id|
+--------+----------+
|1001    |3         |
|1009    |1         |
|1009    |4         |
|1010    |NULL      |
+--------+----------+
```

The first table is the LATERAL VIEW query; the TVF query returned the same three rows (see `ex04_reshape.out`), and the second table is the `explode_outer` query. Order 1010 disappears from a plain `explode`, exactly like an inner join with no match. `LATERAL VIEW OUTER explode(...)` or the TVF `explode_outer` keeps it with `NULL`s. Other generators work the same way: `posexplode` adds the position, `inline` turns an array of structs into columns, `stack` splits values into rows, and `range(start, end, step)` makes a number sequence:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT r.order_id, x.product_id, x.qty
FROM raw_orders r, LATERAL inline(r.items) AS x ORDER BY r.order_id, x.product_id;
SELECT * FROM range(10, 20, 5);
```

Output:
```text
+--------+----------+---+
|order_id|product_id|qty|
+--------+----------+---+
|1001    |3         |2  |
|1009    |1         |1  |
|1009    |4         |3  |
+--------+----------+---+

+---+
|id |
+---+
|10 |
|15 |
+---+
```

In PySpark the generators are functions you call in `select`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
raw.select("order_id", F.explode("items").alias("item")).select("order_id", "item.product_id", "item.qty")
raw.select("order_id", F.explode_outer("items").alias("item")).select("order_id", "item.product_id")
raw.select("order_id", F.inline("items"))
```

```text
same rows as the SQL: True
same rows as the SQL: True
same rows as the SQL: True
```

(The `.out` file also prints the `explode_outer` table, with the `NULL` row for order 1010.)

The TVF page labels generators in `FROM` as "Applies to: Databricks SQL Databricks Runtime 12.2 LTS and above". Arrays, structs and `explode` in depth are the subject of [chapter 18](18-Semi-Structured-Data.md).

## 17.7 SORT BY, DISTRIBUTE BY, CLUSTER BY and paging
*Level: intermediate.*

These clauses come from Hive and only make sense on a distributed engine. They talk about **partitions**, the chunks of data that Spark processes in parallel (chapter 3).

| Clause | What it does | Total order? |
| --- | --- | --- |
| `ORDER BY` | sorts the whole result | yes, "guarantees a total order in the output" |
| `DISTRIBUTE BY x` | repartitions so rows with the same `x` are in the same partition; "does not sort the data within each partition" | no |
| `SORT BY y` | sorts rows "within each Spark partition" | no |
| `CLUSTER BY x` | `DISTRIBUTE BY x` + `SORT BY x`; "does not guarantee a total order of output" | no |

The Query page says `ORDER BY` "is mutually exclusive with `SORT BY`, `CLUSTER BY`, and `DISTRIBUTE BY`". `DISTRIBUTE BY` and `SORT BY` can be combined. To make partitions visible, the example below sets 2 shuffle partitions, turns off adaptive query execution (which would otherwise merge small partitions) and prints `spark_partition_id()`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SET spark.sql.shuffle.partitions = 2;
SET spark.sql.adaptive.enabled = false;

SELECT spark_partition_id() AS part, customer_id, amount
FROM (SELECT * FROM orders DISTRIBUTE BY customer_id SORT BY amount DESC);

SELECT spark_partition_id() AS part, customer_id, order_id
FROM (SELECT * FROM orders CLUSTER BY customer_id);

SELECT * FROM orders ORDER BY amount CLUSTER BY customer_id;
```

Output:
```text
+----+-----------+------+
|part|customer_id|amount|
+----+-----------+------+
|0   |4          |318.00|
|0   |2          |249.00|
|0   |2          |29.95 |
|1   |1          |189.50|
|1   |3          |159.00|
|1   |1          |78.00 |
|1   |1          |59.90 |
|1   |3          |39.00 |
+----+-----------+------+

+----+-----------+--------+
|part|customer_id|order_id|
+----+-----------+--------+
|0   |2          |1002    |
|0   |2          |1006    |
|0   |4          |1005    |
|1   |1          |1001    |
|1   |1          |1003    |
|1   |1          |1008    |
|1   |3          |1004    |
|1   |3          |1007    |
+----+-----------+--------+

ERROR: [UNSUPPORTED_FEATURE.COMBINATION_QUERY_RESULT_CLAUSES] The feature is not supported: Combination of ORDER BY/SORT BY/DISTRIBUTE BY/CLUSTER BY.
```

Look at the first result: amounts go down inside partition 0 and again inside partition 1, but read top to bottom they are not sorted (`29.95` comes before `189.50`). That is `SORT BY`. Why would anyone want it? To prepare data for writing: `DISTRIBUTE BY` controls which rows land in the same task (and so the same output file), and `SORT BY` orders rows inside each file without the cost of one global sort. For a result someone reads, always use `ORDER BY`.

The DataFrame names are clearer about what happens: `repartition` is `DISTRIBUTE BY`, `sortWithinPartitions` is `SORT BY`, and `orderBy` (or `sort`) is `ORDER BY`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1 (same settings as above).*
```python
(orders.repartition("customer_id")
       .sortWithinPartitions(F.desc("amount"))
       .select(F.spark_partition_id().alias("part"), "customer_id", "amount"))
```

```text
same rows as the SQL: True
```

Here the check compares the rows in order, partition numbers included, so the DataFrame produced exactly the first table above.

!!! warning "Two different CLUSTER BYs"
    `SELECT ... CLUSTER BY col` is this query clause (distribute and sort). `CREATE TABLE ... CLUSTER BY (col)` is **liquid clustering**, a table layout feature with nothing to do with query output (chapter 20 and chapter 22). Interviewers sometimes ask about one to see if you confuse it with the other.

### LIMIT and OFFSET

`LIMIT n` and `OFFSET n` are the familiar clauses; the differences are in the details. `OFFSET` has the label "Applies to: Databricks SQL Databricks Runtime 11.3 LTS and above". `LIMIT ALL` means no limit. Both take a constant integer expression (`LIMIT length('SPARK')` is allowed, `LIMIT length(name)` is not). The standard `FETCH FIRST n ROWS ONLY` is not in the Databricks LIMIT syntax.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT order_id, amount FROM orders ORDER BY order_id LIMIT 3 OFFSET 3;
```

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
orders.orderBy("order_id").offset(3).limit(3).select("order_id", "amount")   # PySpark
```

Output (both; the DataFrame version matched the SQL rows in order):
```text
+--------+------+
|order_id|amount|
+--------+------+
|1004    |39.00 |
|1005    |318.00|
|1006    |29.95 |
+--------+------+
```

Without `ORDER BY`, which rows `LIMIT` returns is not defined, and on a distributed engine it really does change between runs. The OFFSET page warns that "the skipped rows still get processed", so deep pages are expensive; practice question 24 shows keyset paging instead.

### TABLESAMPLE

`TABLESAMPLE` reads a sample: `(p PERCENT)`, `(n ROWS)` or `(BUCKET x OUT OF y)`, with optional `REPEATABLE (seed)` ("Applies to: Databricks SQL Databricks Runtime 11.3 LTS and above" for `REPEATABLE`).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
-- big has 10,000 rows
SELECT (SELECT count(*) FROM big TABLESAMPLE (10 PERCENT) REPEATABLE (42)) AS run_1,
       (SELECT count(*) FROM big TABLESAMPLE (10 PERCENT) REPEATABLE (42)) AS run_2,
       (SELECT count(*) FROM big TABLESAMPLE (5 ROWS))                     AS five_rows;
```

Output (from `ex10_compact.out`):
```text
+-----+-----+---------+
|run_1|run_2|five_rows|
+-----+-----+---------+
|1018 |1018 |5        |
+-----+-----+---------+
```

In PySpark, `spark.range(10000).sample(fraction=0.1, seed=42).count()` also returned 1018, twice (`ex09_pyspark.out`). `sample()` takes a fraction, not a row count.

The page's notes matter: the sample is approximate (1,018 rows, not 1,000); "`TABLESAMPLE (num_rows ROWS)` is not a simple random sample but instead is implemented using `LIMIT`"; and sampling happens before `WHERE`, so it does not benefit from filter pushdown.

## 17.8 Set operators, hints and EXPLAIN
*Level: intermediate.*

### Set operators

Databricks supports `UNION`, `INTERSECT` and `EXCEPT`, each with `ALL` or `DISTINCT` (the default), and accepts **`MINUS`** as a synonym for `EXCEPT` (Oracle users will recognize it). The Set operators page states that "`INTERSECT` has a higher precedence than `UNION` and `EXCEPT`", and that columns are matched by position with "a least common type for each respective column".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE TEMPORARY VIEW number1(c) AS VALUES (3), (1), (2), (2), (3), (4);
CREATE OR REPLACE TEMPORARY VIEW number2(c) AS VALUES (5), (1), (1), (2);

SELECT c FROM number1 EXCEPT        SELECT c FROM number2 ORDER BY c;   -- 3, 4
SELECT c FROM number1 MINUS         SELECT c FROM number2 ORDER BY c;   -- 3, 4
SELECT c FROM number1 EXCEPT ALL    SELECT c FROM number2 ORDER BY c;
SELECT c FROM number1 INTERSECT     SELECT c FROM number2 ORDER BY c;
SELECT c FROM number1 INTERSECT ALL SELECT c FROM number2 ORDER BY c;
SELECT 1 AS c UNION SELECT 2 INTERSECT SELECT 3 ORDER BY c;
SELECT 1 AS a, 2 AS b UNION ALL SELECT 20 AS b, 10 AS a;
```

Output (the first six statements from `ex10_compact.out`, one line each; the last from `ex05_sort_sets.out`):
```text
EXCEPT          3, 4
MINUS           3, 4
EXCEPT ALL      2, 3, 3, 4
INTERSECT       1, 2
INTERSECT ALL   1, 2
UNION/INTERSECT 1
```

```text
+---+---+
|a  |b  |
+---+---+
|1  |2  |
|20 |10 |
+---+---+
```

`EXCEPT ALL` works like subtracting counts: `number1` has two 2s and two 3s, `number2` has one 2, so one 2 and both 3s remain. `INTERSECT ALL` keeps the smaller count of each value: 1 appears once in `number1` and 2 appears once in `number2`, so the result is 1 and 2. `SELECT 1 UNION SELECT 2 INTERSECT SELECT 3` returns 1, because the `INTERSECT` runs first (`{2} ∩ {3}` is empty). And the last query is a classic bug: the second SELECT's aliases are ignored, `20` lands in column `a`.

The DataFrame methods have different names, and one of them is a trap: `union()` is `UNION ALL` (it keeps duplicates) and matches columns by position. `unionByName()` matches by name. `subtract()` is `EXCEPT DISTINCT`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
# n1, n2: DataFrames with the same values as number1 and number2
n1.subtract(n2); n1.exceptAll(n2); n1.intersect(n2); n1.intersectAll(n2); n1.union(n2)
```

Output (from `ex09_pyspark.out`, one line per method):
```text
subtract       3, 4
exceptAll      2, 3, 3, 4
intersect      1, 2
intersectAll   1, 2
union          1, 1, 1, 2, 2, 2, 3, 3, 4, 5
```

Practice question 40 shows the positional `union()` bug next to `unionByName()`.

!!! warning "The reference page's example output"
    On the Set operators page (last updated Sep 11, 2026), the example output for `EXCEPT ALL` shows `3, 3, 4` and for `INTERSECT ALL` shows `1, 2, 2`. Both contradict the definitions on the same page ("each row in subquery2 will remove exactly one of possibly multiple matches from subquery1"). The local engine returned `2, 3, 3, 4` and `1, 2`, which match the definitions. What a SQL warehouse returns is **not verified**; the definitions are the safer guide. Be ready to reason it out from the definition if an interviewer asks.

### Hints

A **hint** is a comment of the form `/*+ ... */` right after `SELECT` that suggests a plan. The Hints page lists three groups:

- **Partitioning hints**: `COALESCE(n)`, `REPARTITION(n, col)`, `REPARTITION_BY_RANGE(n, col)`, `REBALANCE(col)`. `REBALANCE` evens out output partition sizes before a write (to avoid too-small or too-big files) and "is ignored if AQE is not enabled".
- **Join hints**: `BROADCAST` (aliases `BROADCASTJOIN`, `MAPJOIN`), `MERGE` (aliases `SHUFFLE_MERGE`, `MERGEJOIN`), `SHUFFLE_HASH`, `SHUFFLE_REPLICATE_NL`. If both sides have different hints, priority is `BROADCAST` over `MERGE` over `SHUFFLE_HASH` over `SHUFFLE_REPLICATE_NL`.
- **Skew hints**, which the page now points to an archived page for.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SET spark.sql.autoBroadcastJoinThreshold = -1;   -- stop Spark from broadcasting on its own
EXPLAIN SELECT o.order_id, c.name
        FROM orders o JOIN customers c ON o.customer_id = c.customer_id;
EXPLAIN SELECT /*+ BROADCAST(c) */ o.order_id, c.name
        FROM orders o JOIN customers c ON o.customer_id = c.customer_id;

SELECT spark_partition_id() AS part, count(*) AS n
FROM (SELECT /*+ REPARTITION(3) */ * FROM orders) GROUP BY 1 ORDER BY 1;
```

Output (the join line of each plan, from `ex10_compact.out`; then the `REPARTITION` result, from `ex05_sort_sets.out`):
```text
no hint      -> SortMergeJoin [customer_id#2701], [customer_id#2706], Inner
BROADCAST(c) -> BroadcastHashJoin [customer_id#3049], [customer_id#3054], Inner, BuildRight, false, false
```

```text
+----+---+
|part|n  |
+----+---+
|0   |3  |
|1   |3  |
|2   |2  |
+----+---+
```

Hints are suggestions. The page says Databricks "is not guaranteed to use the join strategy suggested by the hint", for example when the join type does not support it. And "when a table name is occluded by an alias you must use the alias name in the hint": with `FROM customers AS c`, write `BROADCAST(c)`, not `BROADCAST(customers)`. On Databricks, adaptive query execution and Photon often choose well on their own; chapter 22 covers join strategies.

In PySpark the hint is a function around the small side, `orders.join(F.broadcast(customers), "customer_id")`, or the method `customers.hint("broadcast")`. The first form ran here and changed the plan the same way (`ex09_pyspark.out`: `SortMergeJoin` without it, `BroadcastHashJoin` with it).

### EXPLAIN

`EXPLAIN [EXTENDED | CODEGEN | COST | FORMATTED] statement` shows the plan; by default only the physical plan. `EXTENDED` adds the parsed, analyzed and optimized logical plans; `FORMATTED` prints an outline plus details per node. Standard SQL has no `EXPLAIN`, and unlike PostgreSQL's `EXPLAIN ANALYZE`, Databricks `EXPLAIN` does not run the query. On Databricks you read actual runtime numbers in the query profile (chapter 22).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
EXPLAIN FORMATTED SELECT currency, sum(amount) FROM orders GROUP BY currency;
```

Output (first part):
```text
== Physical Plan ==
AdaptiveSparkPlan (5)
+- HashAggregate (4)
   +- Exchange (3)
      +- HashAggregate (2)
         +- Scan parquet spark_catalog.silver.orders (1)
```

Read it bottom-up: scan, a partial aggregate on each partition, an `Exchange` (the shuffle by `currency`), the final aggregate. For a DataFrame, `df.explain(mode="formatted")` prints the same plan. On a SQL warehouse with Photon the operator names differ (Photon operators), but the shape is the same.

## 17.9 Parameters, IDENTIFIER, session variables and named arguments
*Level: intermediate.*

**The problem.** Pipelines and dashboards run the same query with different values: a date, a currency, sometimes a table name. Gluing user input into SQL text (`f"... WHERE currency = '{cur}'"`) works until someone passes `CAD' OR '1'='1`, which is **SQL injection**. Databricks SQL has four tools to avoid it.

!!! note "How these examples ran"
    In this local setup, the Delta Lake SQL extension (Delta 4.4.1 on Spark 4.2) stopped parameter markers from binding: every marker reported `UNBOUND_SQL_PARAMETER`. The examples in this section therefore ran on a plain Spark 4.2 session with the tables stored as Parquet (see `ex06_params_vars.py`). This is a quirk of the local test setup, not a Databricks behavior.

### Parameter markers

A **parameter marker** is a typed placeholder whose value is supplied by the API that runs the statement, separately from the SQL text. The Parameter markers page: "Using parameter markers protects your code from SQL injection attacks since it clearly separates provided values from the structure of the SQL statements." Two kinds exist, and "you cannot mix named and unnamed parameter markers in the same SQL statement":

- **Named**, `:name` ("Applies to: Databricks Runtime 12.1 and above" on the page's section label).
- **Unnamed**, `?`, bound by position ("Applies to: Databricks Runtime 13.3 and above").

These two section labels leave out "Databricks SQL", which by the rule in section 17.1 would mean "not on SQL warehouses". Here that reading is wrong: the page's top label is "Databricks SQL Databricks Runtime", and the same page lists "Databricks SQL through the Statement Execution API" as a way to supply the values. Read the section labels as the minimum runtime on a cluster.

Values come from the Statement Execution API, from PySpark `spark.sql(..., args=...)`, from Scala or Java, and in the UI from the SQL editor, notebooks and dashboards, where typing `:parameter_name` creates a parameter widget.

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```python
spark.sql("""SELECT order_id, amount FROM orders
             WHERE currency = :cur AND amount >= :min_amt ORDER BY order_id""",
          args={"cur": "CAD", "min_amt": 100}).show()

spark.sql("""SELECT order_id, amount FROM orders
             WHERE currency = ? AND amount >= ? ORDER BY order_id""",
          args=["USD", 100]).show()

spark.sql("SELECT * FROM orders WHERE currency = :cur AND amount > ?", args={"cur": "CAD"})

evil = "CAD' OR '1'='1"
spark.sql("SELECT count(*) AS n FROM orders WHERE currency = :cur", args={"cur": evil}).show()
```

Output:
```text
+--------+------+
|order_id|amount|
+--------+------+
|1003    |189.50|
|1005    |318.00|
+--------+------+

+--------+------+
|order_id|amount|
+--------+------+
|1002    |249.00|
|1007    |159.00|
+--------+------+

ERROR: [INVALID_QUERY_MIXED_QUERY_PARAMETERS] Parameterized query must either use positional, or named parameters, but not both.

+---+
|n  |
+---+
|0  |
+---+
```

The injection attempt counts zero rows: the whole string `CAD' OR '1'='1` was compared as one value. Practice question 29 shows the same input glued into the SQL text, where it returns all 8 rows.

*Databricks only, not run here. Syntax from [Use named parameter markers](https://docs.databricks.com/aws/en/sql/user/queries/query-parameters).*
```sql
-- In the SQL editor: typing :min_amount creates a widget where you pick the type and value
SELECT order_id, amount
FROM shop.silver.orders
WHERE amount >= :min_amount;
```

### The IDENTIFIER clause

A marker is a value, so it cannot stand for a table or column name. `SELECT count(*) FROM :tbl` is a syntax error. The **IDENTIFIER clause** "enables SQL-injection-safe parameterization of identifiers" by interpreting a constant string as a table, column, function, schema or catalog name ("Applies to: Databricks SQL Databricks Runtime 13.3 LTS and above").

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```python
spark.sql("SELECT count(*) AS n FROM :tbl", args={"tbl": "orders"})
spark.sql("SELECT count(*) AS n FROM IDENTIFIER(:tbl)", args={"tbl": "silver.orders"}).show()
spark.sql("SELECT IDENTIFIER(:col) AS picked FROM orders WHERE order_id = 1001",
          args={"col": "currency"}).show()
```

Output:
```text
ERROR: [PARSE_SYNTAX_ERROR] Syntax error at or near ':'.

+---+
|n  |
+---+
|8  |
+---+

+------+
|picked|
+------+
|CAD   |
+------+
```

The string must be a valid name, so `'orders; DROP TABLE x'` cannot sneak in a second statement. Version details from the page: in Databricks SQL and Databricks Runtime 18.0 and above ("Applies to: Databricks SQL Databricks Runtime 18.0 and above") the clause can be used for any part of a multipart name and with coalesced strings such as `IDENTIFIER(:schema '.' :table)`; before 18.0 you write `IDENTIFIER(:schema || '.' || :table)` (the expression form is deprecated from 18.0), and you cannot qualify an IDENTIFIER clause or use it as a qualifier (`myschema.IDENTIFIER(:tab)` fails).

### Session variables

`DECLARE VARIABLE` "creates a session private, temporary variable you can reference wherever a constant expression can be used" ("Applies to: Databricks SQL Databricks Runtime 14.1 and above"). You change it with `SET VAR` (or `SET VARIABLE`), never with plain `SET`, which is for configuration parameters.

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```sql
DECLARE VARIABLE min_amt DECIMAL(10,2) DEFAULT 100;
DECLARE target_cur = 'USD';                       -- type taken from the default
SELECT order_id, amount FROM orders
WHERE currency = target_cur AND amount >= min_amt ORDER BY order_id;

SET VAR min_amt = 200;
SELECT min_amt, session.min_amt AS qualified, system.session.min_amt AS fully_qualified;

SET VAR (min_amt, target_cur) = (SELECT min(amount), max(currency) FROM orders);
VALUES (min_amt, target_cur);

SET VARIABLE min_amt = DEFAULT;
VALUES (min_amt);

SET min_amt = 5;
SELECT min_amt FROM VALUES (1) AS t(min_amt);

DECLARE tbl STRING DEFAULT 'silver.products';
SELECT count(*) AS n FROM IDENTIFIER(tbl);
```

Output:
```text
+--------+------+
|order_id|amount|
+--------+------+
|1002    |249.00|
|1007    |159.00|
+--------+------+

+-------+---------+---------------+
|min_amt|qualified|fully_qualified|
+-------+---------+---------------+
|200.00 |200.00   |200.00         |
+-------+---------+---------------+

+-----+----+
|col1 |col2|
+-----+----+
|29.95|USD |
+-----+----+

+------+
|col1  |
+------+
|100.00|
+------+

ERROR: [UNSUPPORTED_FEATURE.SET_VARIABLE_USING_SET] The feature is not supported: `min_amt` is a VARIABLE and cannot be updated using the SET statement. Use SET VARIABLE `min_amt` = ... instead.

+-------+
|min_amt|
+-------+
|1      |
+-------+

+---+
|n  |
+---+
|5  |
+---+
```

Points from the DECLARE VARIABLE and SET variable pages:

- Variables are the **outermost scope**: a column with the same name wins (the `SELECT min_amt FROM VALUES (1) AS t(min_amt)` result is 1). Qualify with `session.` or `system.session.` to be sure you get the variable.
- `SET VAR (a, b) = (query)` needs a query that returns at most one row; with no rows, the variables become `NULL`.
- `SET VAR x = DEFAULT` re-evaluates the default expression.
- Variables cannot be used in a check constraint, a generated column, a default expression, or the body of a persisted view or SQL UDF.
- Inside a SQL script (`BEGIN ... END`), you write `SET x = ...` without `VAR`. Scripting is in chapter 21.

### EXECUTE IMMEDIATE

When even `IDENTIFIER` is not enough (for example a whole statement built at runtime), `EXECUTE IMMEDIATE` runs a SQL string, binds parameter markers with `USING`, and can put a one-row result `INTO` variables ("Applies to: Databricks SQL Databricks Runtime 14.3 and above").

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```sql
DECLARE n_orders INT;
EXECUTE IMMEDIATE 'SELECT count(*) FROM silver.orders WHERE currency = :c'
  INTO n_orders USING 'CAD' AS c;
VALUES (n_orders);
```

Output:
```text
+----+
|col1|
+----+
|4   |
+----+
```

### Named arguments in function calls

Functions can be called with **named arguments**, `name => value` ("Applies to: Databricks SQL Databricks Runtime 14.0 and above" for the named parameter syntax on the Function invocation page). It works for SQL UDFs, Python UDFs and selected built-in functions that have many optional parameters (`read_files` is the best-known example). Positional arguments may come first, then named ones, but never a positional argument after a named one.

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```sql
CREATE TEMPORARY FUNCTION add_tax(amount DOUBLE, rate DOUBLE DEFAULT 0.05)
  RETURNS DOUBLE RETURN round(amount * (1 + rate), 2);

SELECT add_tax(100) AS by_position,
       add_tax(rate => 0.13, amount => 100) AS by_name,
       add_tax(100, rate => 0.12) AS mixed;
SELECT add_tax(amount => 100, 0.12);
SELECT mask('Ana-Lopez-42', upperChar => 'X', digitChar => '#') AS masked;
```

Output:
```text
+-----------+-------+-----+
|by_position|by_name|mixed|
+-----------+-------+-----+
|105.0      |113.0  |112.0|
+-----------+-------+-----+

ERROR: [UNEXPECTED_POSITIONAL_ARGUMENT] Cannot invoke routine `add_tax` because it contains positional argument(s) following the named argument assigned to `amount`; please rearrange them so the positional arguments come first

+------------+
|masked      |
+------------+
|Xxx-Xxxxx-##|
+------------+
```

The `mask` page says named invocation is supported "in Databricks SQL and Databricks Runtime 13.3 LTS and above". One caution: on open-source Spark 4.2, arguments you leave out keep their documented defaults (the lowercase letters became `x` above), but the `mask` page's own named-argument examples show omitted arguments left unmasked (running the page's example `mask('AaBb123-&^ % Ä', lowerChar => 'z', otherChar => 'X')` here gave `XzXznnnXXXXXXX`, see `ex06_params_vars.out`). Which behavior Databricks has is **not verified**; check on your runtime before relying on it.

The example uses `DOUBLE` on purpose. The Function invocation page's own example declares `increase(base INT, factor FLOAT DEFAULT 1) RETURNS INT` and shows `increase(100, factor => 1.3)` returning 130. Locally it returned 129:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE TEMPORARY FUNCTION increase(base INT, factor FLOAT DEFAULT 1) RETURNS INT RETURN base * factor;
SELECT increase(factor => 1.2, base => 100) AS out_of_order,
       increase(100, factor => 1.3) AS mixed, increase(base => 100) AS dflt;
SELECT CAST(1.3 AS FLOAT) * 100 AS float_product;
```

Output (from `ex10_compact.out`; the type column is left out here):
```text
+------------+-----+----+
|out_of_order|mixed|dflt|
+------------+-----+----+
|120         |129  |100 |
+------------+-----+----+

+------------------+
|float_product     |
+------------------+
|129.99999523162842|
+------------------+
```

`1.3` stored as `FLOAT` is slightly less than 1.3, and the `INT` return type cuts 129.999... down to 129. The page's 130 is **not verified**; the lesson is not to use `FLOAT` for values like rates or money.

*Databricks only, not run here. Syntax from [Function invocation](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-function-invocation).*
```sql
SELECT * FROM read_files(
  's3://bucket/path',
  format => 'csv',
  schema => 'id int, ts timestamp, event string');
```

!!! tip "In the interview"
    **"How do you parameterize a table name safely?"** Not with string concatenation. Pass the name as a parameter marker and wrap it in `IDENTIFIER(:tbl)`, or put it in a session variable and use `IDENTIFIER(var)`. Values go in `:name` or `?` markers, which are bound as data and cannot change the statement. `EXECUTE IMMEDIATE` is the last resort for SQL that must be built as text.

## 17.10 SQL pipe syntax
*Level: expert.*

**The problem.** A SQL query is written in one order (`SELECT ... FROM ... WHERE ... GROUP BY ... HAVING ... ORDER BY`) but runs in another (Figure 17.2). Multi-step logic ends up as nested subqueries or a chain of CTEs read inside out.

**SQL pipe syntax** writes a query in the order it runs. You start from a table and add one operation at a time, each separated by `|>` and each consuming the result of the step before. The SQL Pipeline Syntax page: "Any query can have zero or more pipe operators as a suffix", "Operators can apply in any order, any number of times", with the label "Applies to: Databricks SQL Databricks Runtime 16.2 and above". In Databricks Runtime 18.0 and above, a single `|` can replace `|>`.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 230" role="img" aria-label="A SQL pipeline: FROM orders, WHERE shipped, JOIN customers, AGGREGATE by country, WHERE revenue over 100, ORDER BY revenue. Row counts 8, 4, 4, 2, 2, 2.">
  <g font-family="sans-serif" font-size="13" fill="currentColor">
    <rect x="10" y="20" width="190" height="60" rx="6" fill="none" stroke="currentColor"/>
    <text x="105" y="45" text-anchor="middle" font-family="monospace">FROM orders AS o</text>
    <text x="105" y="66" text-anchor="middle">8 rows, 6 columns</text>
    <rect x="225" y="20" width="190" height="60" rx="6" fill="none" stroke="currentColor"/>
    <text x="320" y="45" text-anchor="middle" font-family="monospace">|&gt; WHERE shipped</text>
    <text x="320" y="66" text-anchor="middle">4 rows</text>
    <rect x="440" y="20" width="190" height="60" rx="6" fill="none" stroke="currentColor"/>
    <text x="535" y="45" text-anchor="middle" font-family="monospace">|&gt; JOIN customers</text>
    <text x="535" y="66" text-anchor="middle">4 rows, 12 columns</text>
    <line x1="200" y1="50" x2="221" y2="50" stroke="currentColor"/><polygon points="221,46 225,50 221,54" fill="currentColor"/>
    <line x1="415" y1="50" x2="436" y2="50" stroke="currentColor"/><polygon points="436,46 440,50 436,54" fill="currentColor"/>
    <path d="M535 80 L535 100 L105 100 L105 116" fill="none" stroke="currentColor"/>
    <polygon points="101,116 105,120 109,116" fill="currentColor"/>
    <rect x="10" y="120" width="190" height="60" rx="6" fill="none" stroke="currentColor"/>
    <text x="105" y="145" text-anchor="middle" font-family="monospace">|&gt; AGGREGATE ...</text>
    <text x="105" y="166" text-anchor="middle">GROUP BY country: 2 rows</text>
    <rect x="225" y="120" width="190" height="60" rx="6" fill="none" stroke="currentColor"/>
    <text x="320" y="145" text-anchor="middle" font-family="monospace">|&gt; WHERE revenue&gt;100</text>
    <text x="320" y="166" text-anchor="middle">2 rows (acts as HAVING)</text>
    <rect x="440" y="120" width="190" height="60" rx="6" fill="none" stroke="currentColor"/>
    <text x="535" y="145" text-anchor="middle" font-family="monospace">|&gt; ORDER BY revenue</text>
    <text x="535" y="166" text-anchor="middle">2 rows, sorted</text>
    <line x1="200" y1="150" x2="221" y2="150" stroke="currentColor"/><polygon points="221,146 225,150 221,154" fill="currentColor"/>
    <line x1="415" y1="150" x2="436" y2="150" stroke="currentColor"/><polygon points="436,146 440,150 436,154" fill="currentColor"/>
    <text x="320" y="212" text-anchor="middle">each step reads the table produced by the step before it, top left to bottom right</text>
  </g>
</svg>
<figcaption>Figure 17.3. The pipeline from the example below, with the row count after each step (from the real run). A WHERE after AGGREGATE does the job of HAVING; no subquery is needed.</figcaption>
</figure>

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
-- classic SQL
SELECT c.country, count(*) AS orders, sum(o.amount) AS revenue
FROM orders o JOIN customers c ON o.customer_id = c.customer_id
WHERE o.status = 'SHIPPED'
GROUP BY c.country
HAVING sum(o.amount) > 100
ORDER BY revenue DESC;

-- the same as a pipeline
FROM orders AS o
|> WHERE o.status = 'SHIPPED'
|> JOIN customers AS c ON o.customer_id = c.customer_id
|> AGGREGATE count(*) AS orders, sum(o.amount) AS revenue GROUP BY c.country
|> WHERE revenue > 100
|> ORDER BY revenue DESC;
```

Output (both queries):
```text
+-------+------+-------+
|country|orders|revenue|
+-------+------+-------+
|US     |2     |408.00 |
|CA     |2     |377.90 |
+-------+------+-------+
```

If you write PySpark, this shape is familiar: a DataFrame chain is already a pipeline, one method per step.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
(orders.filter(F.col("status") == "SHIPPED")
       .join(customers, "customer_id")
       .groupBy("country")
       .agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue"))
       .filter(F.col("revenue") > 100)
       .orderBy(F.desc("revenue")))
```

```text
same rows as the SQL: True
```

The operators, from the Piped operation page:

| Operator | What it does |
| --- | --- |
| `SELECT expr, ...` | projects columns (in DBR 18.0+ it may also aggregate with `GROUP BY`) |
| `EXTEND expr AS name` | appends columns; may use aliases defined earlier in the same `EXTEND` |
| `SET col = expr` | replaces existing columns |
| `DROP col, ...` | removes columns |
| `AS alias` | names the result so later steps can qualify columns with it |
| `WHERE` | filters (before or after aggregation, wherever it appears) |
| `AGGREGATE agg AS name GROUP BY expr` | aggregates; "grouping columns appear before the aggregated columns" |
| `JOIN`, `ORDER BY`, `LIMIT`, `OFFSET` | as usual |
| `UNION` / `EXCEPT` / `INTERSECT`, `TABLESAMPLE`, `PIVOT`, `UNPIVOT` | as usual, applied to the running result |

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
FROM orders
|> WHERE currency = 'CAD'
|> EXTEND amount * 0.05 AS gst
|> EXTEND amount + gst AS total
|> SET total = round(total, 1)
|> DROP customer_id, order_ts, status
|> AS cad_orders
|> SELECT cad_orders.order_id, cad_orders.total
|> ORDER BY total DESC
|> LIMIT 2;

FROM orders |> AGGREGATE currency GROUP BY currency;

FROM orders | WHERE amount > 200 | SELECT order_id, amount | ORDER BY order_id;
```

Output:
```text
+--------+-----+
|order_id|total|
+--------+-----+
|1005    |333.9|
|1003    |199.0|
+--------+-----+

ERROR: [PIPE_OPERATOR_AGGREGATE_EXPRESSION_CONTAINS_NO_AGGREGATE_FUNCTION] Non-grouping expression currency#2626 is provided as an argument to the |> AGGREGATE pipe operator but does not contain any aggregate function

+--------+------+
|order_id|amount|
+--------+------+
|1002    |249.00|
|1005    |318.00|
+--------+------+
```

The second statement shows the rule that trips people up: in `AGGREGATE`, the grouping column goes **only** in `GROUP BY`, not in the aggregate list (it is added to the output automatically, first). The third statement uses the single `|` token, which the docs give for Databricks Runtime 18.0 and above; it also parsed on open-source Spark 4.2.

A pipe can follow any query, not only `FROM`: `SELECT currency, amount FROM orders WHERE amount > 100 |> AGGREGATE count(*) AS n GROUP BY currency` ran here and returned `CAD 2`, `USD 2`.

!!! tip "In the interview"
    **"What is SQL pipe syntax and why use it?"** It writes a query top to bottom in execution order: `FROM t |> WHERE ... |> AGGREGATE ... GROUP BY ... |> ORDER BY ...`. Each step works on the previous result, so filtering after an aggregate is just another `WHERE`, and adding a computed column is `EXTEND` instead of a subquery. It is available in Databricks SQL and Databricks Runtime 16.2 and above, and in open-source Spark 4. The trade-off: teammates and tools that only know classic SQL may find it unfamiliar.

## 17.11 NULL semantics: `<=>`, IS DISTINCT FROM and the usual traps
*Level: intermediate.*

Databricks follows standard three-valued logic: a comparison with `NULL` returns `NULL` (unknown), and `WHERE` keeps only rows where the condition is **true**. What Databricks adds is a short **null-safe equality operator**, `<=>`: it "returns `true` if both are `NULL`, `false` if one of the them is `NULL`" and "is a synonym for `expr1 is not distinct from expr2`". The function `equal_null(a, b)` does the same ("Applies to: Databricks SQL Databricks Runtime 11.3 LTS and above").

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
SELECT NULL = NULL AS eq, NULL <=> NULL AS null_safe_eq,
       1 <=> NULL AS one_ns_null, NULL IS DISTINCT FROM NULL AS is_distinct,
       1 IS DISTINCT FROM NULL AS one_distinct, equal_null(NULL, NULL) AS eq_null;

SELECT order_id FROM orders WHERE status <> 'CANCELLED' ORDER BY order_id;
SELECT order_id FROM orders WHERE status IS DISTINCT FROM 'CANCELLED' ORDER BY order_id;

SELECT order_id FROM orders WHERE customer_id NOT IN (1, 2, NULL);
```

Output (the truth table and the `NOT IN` result from `ex07_pipe_nulls.out`; the two order lists from `ex10_compact.out`):
```text
+----+------------+-----------+-----------+------------+-------+
|eq  |null_safe_eq|one_ns_null|is_distinct|one_distinct|eq_null|
+----+------------+-----------+-----------+------------+-------+
|NULL|true        |false      |false      |true        |true   |
+----+------------+-----------+-----------+------------+-------+
```

```text
status <> 'CANCELLED'                 1001, 1002, 1003, 1005, 1006, 1007
status IS DISTINCT FROM 'CANCELLED'   1001, 1002, 1003, 1005, 1006, 1007, 1008
```

```text
+--------+
|order_id|
+--------+
+--------+
```

The first two traps are ordinary three-valued logic, the same in any SQL engine: `<>` drops the `NULL`-status order 1008, and `NOT IN` with a `NULL` in the list returns nothing (use `NOT EXISTS`, practice question 35). The third is where `<=>` earns its place: **joins and MERGE conditions on nullable keys.** `ON s.k = t.k` never matches two `NULL` keys; `ON s.k <=> t.k` does. This matters for change detection in `MERGE` (chapter 20) and for SCD comparisons (`WHEN MATCHED AND NOT (t.city <=> s.city)`).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE TEMPORARY VIEW src(k, v) AS VALUES (1, 'a'), (NULL, 'b');
CREATE OR REPLACE TEMPORARY VIEW tgt(k, w) AS VALUES (1, 'x'), (NULL, 'y');
SELECT s.k, v, w FROM src s JOIN tgt t ON s.k = t.k;
SELECT s.k, v, w FROM src s JOIN tgt t ON s.k <=> t.k ORDER BY v;
```

Output:
```text
+---+---+---+
|k  |v  |w  |
+---+---+---+
|1  |a  |x  |
+---+---+---+

+----+---+---+
|k   |v  |w  |
+----+---+---+
|1   |a  |x  |
|NULL|b  |y  |
+----+---+---+
```

The DataFrame API spells `<=>` as `eqNullSafe`, and the safe form of `NOT IN` as a left anti join:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
orders.filter(F.col("status") != "CANCELLED").count()             # 6
orders.filter(~F.col("status").eqNullSafe("CANCELLED")).count()   # 7
# src, tgt: DataFrames with the same rows as the two views above
src.join(tgt, src.k == tgt.k).count()                             # 1
src.join(tgt, src.k.eqNullSafe(tgt.k)).count()                    # 2
blocked = spark.createDataFrame([(2,), (None,)], "customer_id INT")
orders.join(blocked, "customer_id", "left_anti")                  # orders of everyone but customer 2
```

Output (from `ex09_pyspark.out`):
```text
status != 'CANCELLED'            -> 6 rows
~status.eqNullSafe('CANCELLED')  -> 7 rows
join on ==          -> 1 rows
join on eqNullSafe  -> 2 rows

left_anti -> 1001, 1003, 1004, 1005, 1007, 1008
```

In grouping, `DISTINCT` and set operators, NULLs are treated as equal to each other: `GROUP BY status` puts the one `NULL` status in its own group, and `SELECT NULL UNION SELECT NULL` returns a single row (both ran here; see `ex07_pipe_nulls.out`). The NULL semantics page states that set operations compare "in a null-safe manner". Sorting: NULLs come first in ascending order and last in descending order unless you write `NULLS FIRST` / `NULLS LAST`. PostgreSQL does the reverse by default (NULLs sort as larger than any value), so a query ported from PostgreSQL can change its row order.

!!! tip "In the interview"
    **"What is `<=>`?"** The null-safe equality operator: true when both sides are equal or both are `NULL`, false when only one is `NULL`, never `NULL` itself. It is the same as `IS NOT DISTINCT FROM`. Use it in join and `MERGE` conditions on nullable columns, and in change detection, where `NULL = NULL` would otherwise look like a change or a missing match.

## 17.12 MATCH_RECOGNIZE (row pattern matching)
*Level: expert.*

**The problem.** Find runs of consecutive rising prices, V-shaped dips, or user sessions split by gaps. With window functions this takes several layers of `lag`, flags and running sums.

**MATCH_RECOGNIZE** is the SQL standard's row pattern recognition clause (from SQL:2016). It partitions and orders the rows, then matches a regular-expression-like pattern of named row conditions. The Databricks page labels it "Applies to: Databricks SQL Databricks Runtime 19 and above" and marks it **Beta**. It is not in open-source Spark 4.2; the local run gave `[PARSE_SYNTAX_ERROR] Syntax error at or near 'BY'`.

*Databricks only, not run here. Syntax from [MATCH_RECOGNIZE clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-match-recognize).*
```sql
-- runs of consecutive increases in order amount, per customer
SELECT customer_id, start_ts, end_ts, run_length
FROM shop.silver.orders
MATCH_RECOGNIZE (
  PARTITION BY customer_id
  ORDER BY order_ts
  MEASURES FIRST(order_ts) AS start_ts,
           LAST(order_ts)  AS end_ts,
           COUNT(*)        AS run_length
  ONE ROW PER MATCH
  AFTER MATCH SKIP PAST LAST ROW
  PATTERN ( strt up+ )
  DEFINE up AS amount > PREV(amount) ) AS m;
```

How to read it: `strt` has no `DEFINE` entry, so it matches any row and anchors the run; `up+` matches one or more following rows whose amount is greater than the previous row's (`PREV(amount)`). `ONE ROW PER MATCH` returns the partition columns plus the `MEASURES`; `ALL ROWS PER MATCH` returns every matched row. In this Beta release the page says `AFTER MATCH` supports only `SKIP PAST LAST ROW`, and `PARTITION BY` accepts column references only. PostgreSQL does not have `MATCH_RECOGNIZE`.

## 17.13 Side by side: standard SQL, PostgreSQL and Databricks SQL
*Level: intermediate.*

The Databricks column comes from the pages cited in this chapter. The standard SQL and PostgreSQL columns are general knowledge for orientation; they were not checked against the ISO standard or the PostgreSQL manual for this book.

| Task | Standard SQL | PostgreSQL | Databricks SQL |
| --- | --- | --- | --- |
| Quote a name with special characters | `"order total"` | `"order total"` | `` `order total` `` |
| Unquoted name case | folded to upper case | folded to lower case | case-insensitive; Unity Catalog stores object names in lower case |
| String literal | `'x'`, quote doubled: `'O''Neil'` | `'x'`, `E'\n'` for escapes | `'x'` with backslash escapes, `r'raw'`, `"x"` (discouraged) |
| Bad cast / overflow / divide by zero | error | error | error in ANSI mode (default today); `NULL` or wrap-around when ANSI is off |
| Cast that returns NULL on failure | none | none built in | `try_cast(x AS t)`, `x ?:: t` (DBR 15.3+) |
| Cast shorthand | `CAST(x AS t)` | `CAST`, `x::t` | `CAST`, `x::t` |
| Null-safe equality | `IS NOT DISTINCT FROM` | `IS NOT DISTINCT FROM` | `<=>`, `IS NOT DISTINCT FROM`, `equal_null()` |
| Filter on a window function | subquery or CTE | subquery or CTE | `QUALIFY` |
| Group by all non-aggregated columns | list them | list them | `GROUP BY ALL` |
| Sort by every selected column | list them | list them | `ORDER BY ALL` |
| All columns except a few | list them | list them | `SELECT * EXCEPT (a, b)` |
| Reuse an alias in the same SELECT | not allowed | not allowed | lateral column alias (DBR 12.2 LTS+) |
| First n rows | `FETCH FIRST n ROWS ONLY` | `LIMIT n` or `FETCH FIRST` | `LIMIT n` |
| Skip rows | `OFFSET n ROWS` | `OFFSET n` | `OFFSET n` (DBR 11.3 LTS+) |
| Rows to columns | `FILTER` or `CASE` per column | `FILTER`, or `crosstab()` from an extension | `PIVOT (agg FOR col IN (...))` |
| Columns to rows | `UNION ALL` or `LATERAL (VALUES ...)` | same, or `unnest` | `UNPIVOT (val FOR name IN (...))` |
| One row per array element | `UNNEST` | `unnest()` | `explode()` as a TVF in `FROM`, or `LATERAL VIEW` |
| Set difference keeping duplicates | `EXCEPT ALL` | `EXCEPT ALL` | `EXCEPT ALL` or `MINUS ALL` |
| Sample rows | `TABLESAMPLE BERNOULLI (p)` | `TABLESAMPLE BERNOULLI / SYSTEM (p)` | `TABLESAMPLE (p PERCENT | n ROWS | BUCKET x OUT OF y)` |
| Control physical layout of results | not in SQL | not in SQL | `DISTRIBUTE BY`, `SORT BY`, `CLUSTER BY`, hints `/*+ ... */` |
| Bind values safely | `?` in dynamic SQL | `$1`, `$2` in prepared statements | `:name` or `?` parameter markers |
| Parameterize a table name | dynamic SQL | `EXECUTE format(...)` in PL/pgSQL | `IDENTIFIER(:tbl)`, `EXECUTE IMMEDIATE` |
| Variables outside procedures | no | no (psql client variables only) | `DECLARE VARIABLE`, `SET VAR` (DBR 14.1+) |
| Named function arguments | not verified | `name => value` | `name => value` (DBR 14.0+) |
| Pipe syntax | no | no | `FROM t |> WHERE ... |> AGGREGATE ...` (DBR 16.2+) |
| Row pattern matching | `MATCH_RECOGNIZE` | no | `MATCH_RECOGNIZE` (DBR 19+, Beta) |
| Show the plan | not in SQL | `EXPLAIN`, `EXPLAIN ANALYZE` (runs it) | `EXPLAIN [EXTENDED | CODEGEN | COST | FORMATTED]` (does not run it) |
| Default NULL sort position | implementation-defined | NULLs last in `ASC` | NULLs first in `ASC`, last in `DESC` |
| Nested `/* */` comments | yes | yes | yes |

The DataFrame side, for the features in this chapter that have a direct equivalent (each one ran in `ex09_pyspark.py`; most were checked row for row against the SQL version):

| Databricks SQL | PySpark DataFrame |
| --- | --- |
| `QUALIFY row_number() OVER (...) = 1` | `withColumn("rn", F.row_number().over(w)).filter("rn = 1").drop("rn")` |
| `GROUP BY ALL` | `groupBy("col1", "col2")` (no shorthand) |
| `SELECT * EXCEPT (a, b)` | `drop("a", "b")` |
| lateral column alias | chained `withColumn` calls |
| `PIVOT (agg FOR c IN (...))` | `groupBy(...).pivot("c", [...]).agg(...)` |
| `UNPIVOT` (drops `NULL`s) | `unpivot(ids, values, name, value)` (keeps `NULL`s) |
| `LATERAL explode(...)`, `explode_outer`, `inline` | `F.explode`, `F.explode_outer`, `F.inline` in `select` |
| `DISTRIBUTE BY` / `SORT BY` | `repartition(col)` / `sortWithinPartitions(col)` |
| `LIMIT n OFFSET m` | `offset(m).limit(n)` |
| `TABLESAMPLE (p PERCENT) REPEATABLE (s)` | `sample(fraction=p/100, seed=s)` |
| `EXCEPT` / `EXCEPT ALL` | `subtract` / `exceptAll` |
| `INTERSECT` / `INTERSECT ALL` | `intersect` / `intersectAll` |
| `UNION ALL` (by position) | `union` (by position); `unionByName` (by name) |
| `/*+ BROADCAST(c) */` | `F.broadcast(c)` |
| `a <=> b` | `a.eqNullSafe(b)` |
| `NOT EXISTS (...)` | `join(other, key, "left_anti")` |
| pipe syntax `|>` | a method chain |

!!! tip "In the interview"
    **"Name five things in Databricks SQL that standard SQL does not have."** `QUALIFY`; `GROUP BY ALL` and `ORDER BY ALL`; `SELECT * EXCEPT`; `PIVOT` / `UNPIVOT`; the `<=>` operator; `try_cast` and the other `try_` functions; parameter markers with `IDENTIFIER`; session variables; pipe syntax; `SORT BY` / `DISTRIBUTE BY` / `CLUSTER BY`; time travel on Delta tables (`VERSION AS OF`, `@v123`, chapter 20). Pick ones you have used and say what problem each solves.

## 17.14 Practice questions
*Level: mixed.*

**Q1. In the reference, one page says "Applies to: Databricks SQL Databricks Runtime 14.1 and above" and another says "Applies to: Databricks Runtime 15.3 and above". What does each mean for a query on a SQL warehouse?**

??? success "Answer"
    The first feature works on all SQL warehouses and on clusters running DBR 14.1 or later. The second label does not mention Databricks SQL, so per the "How to use the SQL reference" page the feature is for Databricks Runtime 15.3 and later only, not for SQL warehouses.

    **Why:** SQL warehouses and clusters version separately. The "Applies to" label is the first thing to check when a statement works in a notebook but fails on a warehouse (or the reverse).

**Q2. What does `SELECT 1/0` return on a new SQL warehouse, and what does `SELECT try_divide(1, 0)` return?**

??? success "Answer"
    On a warehouse with the default `ANSI_MODE = TRUE`, `1/0` raises `DIVIDE_BY_ZERO`. `try_divide(1, 0)` returns `NULL` (the run in section 17.2 shows both). With `ANSI_MODE` off, `1/0` would return `NULL`.

    **Why:** ANSI mode turns invalid arithmetic into errors. The `try_` functions give you `NULL` for one expression without changing the session's mode.

**Q3. A nightly job that cast `amount_raw` (a string) to `DECIMAL(10,2)` ran for a year on DBR 15.4 LTS. After moving to DBR 17.3 LTS it fails with `CAST_INVALID_INPUT`. What changed, and how do you fix it?**

??? success "Answer"
    ANSI mode is enabled by default in Databricks Runtime 17.0 and above. Before, a value like `'n/a'` silently became `NULL`; now the cast fails. Fix the expression, not the session:

    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT order_id, try_cast(amount_raw AS DECIMAL(10,2)) AS amount
    FROM raw_amounts ORDER BY order_id;
    ```

    ```text
    +--------+------+
    |order_id|amount|
    +--------+------+
    |1       |59.90 |
    |2       |NULL  |
    |3       |NULL  |
    +--------+------+
    ```

    **Why:** `try_cast` keeps the old `NULL` behavior where you expect bad input, while the rest of the job keeps ANSI protection. Better still, count or quarantine the `NULL` results so the bad rows are visible (`'12,50'` above is probably a real amount written with a comma).

**Q4. With ANSI mode off, what does `SELECT CAST(12345 AS TINYINT)` return, and why is that dangerous?**

??? success "Answer"
    `57` (from the run in section 17.2). `TINYINT` holds -128 to 127, and the value wraps around. With ANSI on, it raises `CAST_OVERFLOW`.

    **Why:** a wrong number that looks plausible is worse than an error or a `NULL`; nothing tells you the data is corrupt.

**Q5. A colleague proposes `SET spark.sql.ansi.enabled = false` at the top of every notebook "so jobs stop failing". What do you answer?**

??? success "Answer"
    Do not. Turning ANSI mode off hides data quality problems: bad casts become `NULL`, overflows wrap silently. Databricks recommends the `try_*` functions "instead of disabling ANSI mode, because ANSI mode surfaces data quality issues that a silent `NULL` hides". Also, on serverless the insert-time casts follow ANSI rules regardless, because `spark.sql.storeAssignmentPolicy` cannot be changed there.

    **Why:** fix the specific expressions that can see bad input, and route bad rows to a quarantine table ([chapter 9](09-Building-Silver.md)).

**Q6. Find the bug: `SELECT "order_id" AS c FROM orders LIMIT 2` returns the word `order_id` twice instead of order numbers.**

??? success "Answer"
    In Databricks SQL, double quotes make a string literal, not an identifier. Use backticks (or nothing):

    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT "order_id" AS c FROM orders LIMIT 2;
    SELECT `order_id` AS c FROM orders ORDER BY c LIMIT 2;
    ```

    ```text
    +--------+
    |c       |
    +--------+
    |order_id|
    |order_id|
    +--------+

    +----+
    |c   |
    +----+
    |1001|
    |1002|
    +----+
    ```

    **Why:** PostgreSQL and standard SQL use double quotes for identifiers, so code ported from them runs without error and returns constants. It is a silent bug.

**Q7. Are `SELECT Order_ID FROM ORDERS` and `SELECT order_id FROM orders` the same query? Can a Unity Catalog table have columns `Amount` and `amount`?**

??? success "Answer"
    Yes, the same: "Identifiers are case-insensitive when referenced." No, two columns that differ only in case would be ambiguous, because references ignore case. Unity Catalog stores object names (catalogs, schemas, tables) in lower case and preserves the casing of column names for display.

    **Why:** this differs from PostgreSQL, where `"Amount"` and `amount` can be two different columns.

**Q8. A source system delivers a column called `unit price (CAD)`. Write a query that selects products whose unit price is over 150.**

??? success "Answer"
    Use backticks every time you reference it:

    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT name, `unit price (CAD)` FROM price_list
    WHERE `unit price (CAD)` > 150 ORDER BY name;
    ```

    ```text
    +-----------------+----------------+
    |name             |unit price (CAD)|
    +-----------------+----------------+
    |Down Sleeping Bag|189.50          |
    |Rain Shell       |159.00          |
    |Trail Tent 2P    |249.00          |
    +-----------------+----------------+
    ```

    **Why:** spaces and parentheses are not allowed in a regular identifier. In practice, rename such columns in silver (`unit_price_cad`) so nobody needs backticks downstream.

**Q9. You run `USE SCHEMA shop.silver` and then `USE CATALOG finance`. What do `current_catalog()` and `current_schema()` return?**

??? success "Answer"
    `finance` and `default`. The USE CATALOG page: "Setting the catalog also resets the current schema to `default`."

    **Why:** scripts that switch catalogs and assume the schema stays the same end up reading or creating tables in `finance.default`.

**Q10. A notebook created `CREATE TEMP VIEW orders AS SELECT * FROM orders WHERE amount > 100` while testing. The current schema is `shop.silver`. What does a later `SELECT count(*) FROM orders` read? And `WITH orders AS (...) SELECT * FROM orders`?**

??? success "Answer"
    The temporary view: for unqualified names, temporary views come before the current schema (fixed order in DBR 18 and below; through the default `PATH`, where `system.session` comes before `CURRENT_SCHEMA`, in Databricks SQL and DBR 19+). In the `WITH` query, the CTE wins over both. To read the table, write `silver.orders` or `shop.silver.orders`.

    **Why:** shadowing is silent. Section 17.4 shows all three cases running.

**Q11. Rewrite with QUALIFY: keep each customer's largest order.**

*Run here: Apache Spark 4.2 (plain session).*
```sql
SELECT customer_id, order_id, amount FROM (
  SELECT *, rank() OVER (PARTITION BY customer_id ORDER BY amount DESC) AS rnk FROM orders) x
WHERE rnk = 1 ORDER BY customer_id;
```

??? success "Answer"
    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT customer_id, order_id, amount FROM orders
    QUALIFY rank() OVER (PARTITION BY customer_id ORDER BY amount DESC) = 1
    ORDER BY customer_id;
    ```

    ```text
    +-----------+--------+------+
    |customer_id|order_id|amount|
    +-----------+--------+------+
    |1          |1003    |189.50|
    |2          |1002    |249.00|
    |3          |1007    |159.00|
    |4          |1005    |318.00|
    +-----------+--------+------+
    ```

    Both versions returned these rows. **Why:** `QUALIFY` filters after window functions are computed, so no wrapper query is needed. With `rank()`, a customer with two orders of the same top amount would get two rows; use `row_number()` if you need exactly one.

**Q12. What does `SELECT customer_id FROM customer_updates QUALIFY customer_id > 1` return?**

??? success "Answer"
    An error, `QUALIFY_REQUIRES_WINDOW_FUNCTION` (section 17.5 shows the run). At least one window function must appear in the SELECT list or the QUALIFY clause. Use `WHERE` for a plain filter.

**Q13. Rewrite with GROUP BY ALL: `SELECT country, city, count(*) AS n FROM customers GROUP BY country, city ORDER BY country, city`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT country, city, count(*) AS n FROM customers GROUP BY ALL ORDER BY ALL;
    ```

    ```text
    +-------+---------+---+
    |country|city     |n  |
    +-------+---------+---+
    |CA     |Calgary  |1  |
    |CA     |Vancouver|1  |
    |US     |Denver   |1  |
    |US     |Moab     |1  |
    +-------+---------+---+
    ```

    **Why:** `GROUP BY ALL` groups by every SELECT expression without an aggregate (`country`, `city`); `ORDER BY ALL` sorts by every SELECT expression, which here includes `n` as a last tie-breaker. That is harmless, but notice it is not exactly the original `ORDER BY country, city`.

**Q14. Find the bug: `SELECT customer_id, amount * count(*) AS x FROM orders GROUP BY ALL` fails with `MISSING_AGGREGATION`. Why, and what was probably meant?**

??? success "Answer"
    `GROUP BY ALL` adds only expressions without aggregates, so it groups by `customer_id`. The expression `amount * count(*)` contains an aggregate, so it is not a grouping expression, but it also uses `amount`, which is neither grouped nor aggregated. The intent was almost certainly total spend per customer:

    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT customer_id, sum(amount) AS total FROM orders GROUP BY ALL ORDER BY customer_id;
    ```

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

    **Why:** the GROUP BY page warns that `GROUP BY ALL` "is not guaranteed to produce a set of group expressions which can be resolved".

**Q15. What does `SELECT country, city FROM customers ORDER BY ALL DESC` sort by?**

??? success "Answer"
    By `country DESC`, then `city DESC`. The ORDER BY page says that if a sort direction is given after `ALL`, "they apply to each expression". The run in section 17.5 returned US/Moab, US/Denver, CA/Vancouver, CA/Calgary.

**Q16. Write a query that returns every column of `orders` except `currency` and `order_ts`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT * EXCEPT (currency, order_ts) FROM orders ORDER BY order_id LIMIT 3;
    ```

    ```text
    +--------+-----------+-------+------+
    |order_id|customer_id|status |amount|
    +--------+-----------+-------+------+
    |1001    |1          |SHIPPED|59.90 |
    |1002    |2          |SHIPPED|249.00|
    |1003    |1          |PLACED |189.50|
    +--------+-----------+-------+------+
    ```

    **Why:** `* EXCEPT` (DBR 11.3 LTS and above) avoids listing columns and keeps working when new columns are added. The flip side: new columns also flow through automatically, which may not be what a gold table contract wants.

**Q17. Finance says CAD revenue excluding cancelled orders should be 645.40, but `sum(amount) FILTER (WHERE status <> 'CANCELLED')` gives 567.40. No CAD order is cancelled. Find the bug.**

??? success "Answer"
    Order 1008 (78.00 CAD) has a `NULL` status. `NULL <> 'CANCELLED'` is `NULL`, so the filter drops it.

    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT sum(amount) FILTER (WHERE status <> 'CANCELLED') AS buggy,
           sum(amount) FILTER (WHERE status IS DISTINCT FROM 'CANCELLED') AS fixed
    FROM orders WHERE currency = 'CAD';
    ```

    ```text
    +------+------+
    |buggy |fixed |
    +------+------+
    |567.40|645.40|
    +------+------+
    ```

    **Why:** any comparison with `NULL` is unknown, and filters keep only true rows. `IS DISTINCT FROM` treats `NULL` as a value, so it is distinct from `'CANCELLED'`. Also ask why a status is `NULL` in silver at all.

**Q18. Write a PIVOT that counts orders per currency with one column per status, including a column for unknown (NULL) status.**

??? success "Answer"
    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT * FROM (SELECT currency, coalesce(status, 'UNKNOWN') AS status FROM orders)
    PIVOT (count(*) FOR status IN ('PLACED' AS placed, 'SHIPPED' AS shipped,
                                   'CANCELLED' AS cancelled, 'UNKNOWN' AS unknown))
    ORDER BY currency;
    ```

    ```text
    +--------+------+-------+---------+-------+
    |currency|placed|shipped|cancelled|unknown|
    +--------+------+-------+---------+-------+
    |CAD     |1     |2      |NULL     |1      |
    |USD     |1     |2      |1        |NULL   |
    +--------+------+-------+---------+-------+
    ```

    **Why:** `IN` values must be literals, so the `NULL` status is mapped to a literal first. Empty cells are `NULL`, not 0, because each cell is an aggregate over zero rows; wrap the result in `coalesce(..., 0)` in a report.

**Q19. The `targets` view has 2 rows and 3 month columns, and one cell is `NULL`. How many rows does `UNPIVOT (target FOR month IN (jan, feb, mar))` return, and how many with `INCLUDE NULLS`?**

??? success "Answer"
    5 and 6 (section 17.6). The default is `EXCLUDE NULLS`, so the Camping/March row with a `NULL` target is removed.

    **Why:** a missing target and a target of zero mean different things; choose deliberately. Watch the default when you switch APIs: PySpark's `DataFrame.unpivot` keeps the `NULL` row (6 rows in `ex09_pyspark.out`), so add `.dropna(subset=["target"])` to match the SQL default.

**Q20. Rewrite without the deprecated LATERAL VIEW: `SELECT order_id, pid FROM baskets LATERAL VIEW explode(product_ids) e AS pid`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT b.order_id, e.pid
    FROM baskets b, LATERAL explode(b.product_ids) AS e(pid)
    ORDER BY b.order_id, e.pid;
    ```

    ```text
    +--------+---+
    |order_id|pid|
    +--------+---+
    |1001    |3  |
    |1009    |1  |
    |1009    |4  |
    +--------+---+
    ```

    The LATERAL VIEW version returned the same rows. **Why:** the reference says LATERAL VIEW is deprecated in Databricks SQL and from DBR 12.2, and recommends calling the generator as a table reference.

**Q21. After exploding the `items` array, order 1010 is missing from the silver table. Why, and what are two fixes?**

??? success "Answer"
    Order 1010 has an empty array; `explode` produces no rows for it, so the order vanishes (like an inner join). Fixes: `LATERAL VIEW OUTER explode(items)` or the TVF `explode_outer(r.items)`, both of which return one row with `NULL`s (section 17.6 shows the run). In PySpark, `F.explode_outer("items")` instead of `F.explode("items")`.

    **Why:** silently losing parent rows breaks row-count reconciliation between bronze and silver.

**Q22. A report query ends with `SORT BY order_ts`, and the output looks unsorted. Why?**

??? success "Answer"
    `SORT BY` sorts only within each Spark partition. With more than one partition, the output is a concatenation of separately sorted chunks, a "partially ordered result". Use `ORDER BY` for a total order.

    **Why:** `SORT BY` exists to order rows inside each output file before writing, which is cheaper than a global sort.

**Q23. What is the difference between `SELECT ... CLUSTER BY customer_id` and `CREATE TABLE ... CLUSTER BY (customer_id)`?**

??? success "Answer"
    The first is a query clause: repartition by `customer_id` and sort within each partition (`DISTRIBUTE BY` + `SORT BY`), with no total order. The second defines **liquid clustering** for a Delta table, a storage layout that helps data skipping (chapter 20, chapter 22).

**Q24. Show page 3 of the orders list, 3 orders per page, ordered by `order_id`. Why is this approach a poor fit for a large table?**

??? success "Answer"
    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT order_id FROM orders ORDER BY order_id LIMIT 3 OFFSET 6;
    ```

    ```text
    +--------+
    |order_id|
    +--------+
    |1007    |
    |1008    |
    +--------+
    ```

    Only two rows, because there are 8 orders. **Why it scales badly:** the OFFSET page says skipped rows "still get processed", so page 1,000 sorts and discards 2,997 rows. Keyset paging (`WHERE order_id > :last_id ORDER BY order_id LIMIT 3`) reads only what it returns. And without `ORDER BY`, pages could overlap or skip rows between runs.

**Q25. `number1` holds 3, 1, 2, 2, 3, 4 and `number2` holds 5, 1, 1, 2. What does `number1 EXCEPT ALL number2` return? And `INTERSECT ALL`?**

??? success "Answer"
    `EXCEPT ALL`: 2, 3, 3, 4. Each row of `number2` removes one matching row of `number1`: the 1 is removed once, one of the two 2s is removed, and 5 has nothing to remove. `INTERSECT ALL`: 1, 2 (the smaller count of each common value). Both ran in section 17.8.

    **Why:** `ALL` versions work on counts (multisets). Note that the reference page's own example output differs; reason from the definition.

**Q26. What does `SELECT 1 AS c UNION SELECT 2 INTERSECT SELECT 3` return?**

??? success "Answer"
    One row, `1`. `INTERSECT` has higher precedence than `UNION`, so it is `1 UNION (2 INTERSECT 3)`, and `2 INTERSECT 3` is empty. With parentheses, `(SELECT 1 UNION SELECT 2) INTERSECT SELECT 3` returns no rows (both ran; see `ex05_sort_sets.out`).

**Q27. An analyst uses `TABLESAMPLE (1000 ROWS)` to get a random sample for a data quality check. What is wrong?**

??? success "Answer"
    The TABLESAMPLE page says `(num_rows ROWS)` "is not a simple random sample but instead is implemented using `LIMIT`", so it tends to return the first rows Spark reads. Use `TABLESAMPLE (p PERCENT)`, with `REPEATABLE (seed)` if the check must be reproducible; the count is approximate (1,018 for 10 percent of 10,000 in the run).

**Q28. You add `/*+ BROADCAST(customers) */` to `SELECT ... FROM orders o JOIN customers c ON ...`, and the plan still shows a sort-merge join. Name two possible reasons.**

??? success "Answer"
    (1) The table is aliased, and the Hints page says "when a table name is occluded by an alias you must use the alias name in the hint": write `BROADCAST(c)`. (2) Hints are suggestions; the strategy may not support the join type (for example, broadcasting the preserved side of an outer join), and Databricks "is not guaranteed to use the join strategy suggested by the hint".

    **Why:** in section 17.8, `BROADCAST(c)` changed `SortMergeJoin` into `BroadcastHashJoin`.

**Q29. Find the bug and fix it:**

*Run here: Apache Spark 4.2 (plain session), with a sample input; the answer shows the output.*
```python
cur = request_param   # comes from a dashboard user
spark.sql(f"SELECT count(*) AS n FROM orders WHERE currency = '{cur}'")
```

??? success "Answer"
    It is open to SQL injection. With `cur = "CAD' OR '1'='1"`, the condition becomes always true. Bind the value with a parameter marker:

    *Run here: Apache Spark 4.2 (plain session).*
    ```python
    user_input = "CAD' OR '1'='1"
    spark.sql(f"SELECT count(*) AS n FROM orders WHERE currency = '{user_input}'").show()
    spark.sql("SELECT count(*) AS n FROM orders WHERE currency = :cur",
              args={"cur": user_input}).show()
    ```

    ```text
    +---+
    |n  |
    +---+
    |8  |
    +---+

    +---+
    |n  |
    +---+
    |0  |
    +---+
    ```

    **Why:** with a marker, the whole input is one string value and cannot change the statement's structure.

**Q30. `spark.sql("SELECT count(*) FROM :tbl", args={"tbl": "silver.products"})` fails with a syntax error. Fix it.**

??? success "Answer"
    A parameter marker stands for a value, not a name. Wrap it in the IDENTIFIER clause:

    *Run here: Apache Spark 4.2 (plain session).*
    ```python
    spark.sql("SELECT count(*) AS n FROM IDENTIFIER(:tbl)", args={"tbl": "silver.products"}).show()
    ```

    ```text
    +---+
    |n  |
    +---+
    |5  |
    +---+
    ```

    **Why:** `IDENTIFIER` (DBSQL and DBR 13.3 LTS and above) turns a constant string into an object name safely; the string must be a valid name, so it cannot inject extra SQL.

**Q31. After `DECLARE VARIABLE min_amt INT DEFAULT 100`, the statement `SET min_amt = 5` fails. Why?**

??? success "Answer"
    Plain `SET` changes configuration parameters. Outside a SQL script, a variable needs `SET VAR min_amt = 5` (or `SET VARIABLE`); the run in section 17.9 shows the error `UNSUPPORTED_FEATURE.SET_VARIABLE_USING_SET`. Inside a `BEGIN ... END` compound statement it is the other way round: `SET min_amt = 5`, and `VAR` is not allowed.

**Q32. A session variable `region` holds `'west'`. What does `SELECT region FROM stores` return if `stores` has a column called `region`?**

??? success "Answer"
    The column's values. Variables are the outermost scope, so a column with the same name wins (the run in section 17.9 shows `1`, the column, not the variable). Write `session.region` to get the variable.

    **Why:** silent shadowing is a common bug when variables have generic names; a prefix such as `v_region` avoids it.

**Q33. Rewrite as a pipeline: `SELECT currency, avg(amount) AS avg_amount FROM orders WHERE status = 'SHIPPED' GROUP BY currency ORDER BY currency`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    FROM orders
    |> WHERE status = 'SHIPPED'
    |> AGGREGATE avg(amount) AS avg_amount GROUP BY currency
    |> ORDER BY currency;
    ```

    ```text
    +--------+----------+
    |currency|avg_amount|
    +--------+----------+
    |CAD     |188.950000|
    |USD     |204.000000|
    +--------+----------+
    ```

    The classic query returned the same rows. **Why:** pipe syntax follows execution order; `currency` appears only in `GROUP BY` and comes out as the first column.

**Q34. Find the bug: `FROM orders |> AGGREGATE currency GROUP BY currency` (the goal is the list of distinct currencies).**

??? success "Answer"
    Every expression in the `AGGREGATE` list must contain an aggregate function; grouping columns go only in `GROUP BY`. The error is `PIPE_OPERATOR_AGGREGATE_EXPRESSION_CONTAINS_NO_AGGREGATE_FUNCTION`. For distinct values, use `SELECT DISTINCT`:

    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    FROM orders |> SELECT DISTINCT currency |> ORDER BY currency;
    ```

    ```text
    +--------+
    |currency|
    +--------+
    |CAD     |
    |USD     |
    +--------+
    ```

    Open-source Spark 4.2 also accepted `|> AGGREGATE GROUP BY currency` (an empty aggregate list), but the Databricks syntax diagram shows at least one aggregate expression, so that form was not verified for Databricks.

**Q35. `SELECT order_id FROM orders WHERE customer_id NOT IN (SELECT customer_id FROM blocked)` returns no rows, although only customer 2 is blocked. Why, and what is the fix?**

??? success "Answer"
    `blocked` also contains a `NULL`. `x NOT IN (2, NULL)` is `x <> 2 AND x <> NULL`, and `x <> NULL` is never true, so no row passes. Use `NOT EXISTS`, which ignores the `NULL`:

    *Run here: Apache Spark 4.2 (plain session).*
    ```sql
    SELECT order_id FROM orders o
    WHERE NOT EXISTS (SELECT 1 FROM blocked b WHERE b.customer_id = o.customer_id)
    ORDER BY order_id;
    ```

    ```text
    +--------+
    |order_id|
    +--------+
    |1001    |
    |1003    |
    |1004    |
    |1005    |
    |1007    |
    |1008    |
    +--------+
    ```

    In PySpark, the same safe form is a left anti join, which returned the same six orders:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```python
    blocked = spark.createDataFrame([(2,), (None,)], "customer_id INT")
    orders.join(blocked, "customer_id", "left_anti").select("order_id").orderBy("order_id")
    ```

    ```text
    left_anti -> 1001, 1003, 1004, 1005, 1007, 1008
    ```

    **Why:** standard three-valued logic. `NOT EXISTS` or a left anti join ignores the `NULL` because an equality with `NULL` simply never matches.

**Q36. A `MERGE` that updates changed customer rows uses `WHEN MATCHED AND t.city <> s.city THEN UPDATE ...`. Customers whose city changes from `NULL` to `'Banff'` are never updated. Why, and what is the fix?**

??? success "Answer"
    `NULL <> 'Banff'` is `NULL`, not true, so the `WHEN MATCHED` condition fails. Use the null-safe form: `WHEN MATCHED AND NOT (t.city <=> s.city)` (or `t.city IS DISTINCT FROM s.city`).

    **Why:** `<=>` never returns `NULL`: it is true for two `NULL`s and false when only one side is `NULL` (section 17.11 shows the truth table from the run). `MERGE` itself is covered in chapter 20 and the SQL course's [MERGE chapter](../../databases/sql/17-Insert-Update-Delete-Merge.md).

**Q37. Can you use MATCH_RECOGNIZE on a SQL warehouse? On a DBR 17.3 LTS cluster?**

??? success "Answer"
    On a SQL warehouse, yes: the page says "Applies to: Databricks SQL Databricks Runtime 19 and above", and the feature is in Beta. On DBR 17.3 LTS, no; it needs Databricks Runtime 19 or above. It is not in open-source Spark 4.2 either (it failed to parse here).

    **Why:** Beta features can change; check the page before relying on one in production.

**Q38. Why does `add_tax(amount => 100, 0.12)` fail, while `add_tax(100, rate => 0.12)` works?**

??? success "Answer"
    Named and positional arguments can be mixed only with positional ones first. After a named argument, a positional one is rejected with `UNEXPECTED_POSITIONAL_ARGUMENT` (section 17.9 shows the run). The Function invocation page states the same rule.

**Q39. Why might an alias named like an existing column give different results in `ORDER BY` and `HAVING`?**

??? success "Answer"
    The Name resolution page says `ORDER BY` prefers the SELECT-list alias, while `HAVING` (and `QUALIFY`, per the same page) prefer the table column. So `SELECT sum(b) AS a FROM t GROUP BY a HAVING a > 1` filters on the column `a`, not on `sum(b)`. In the local test, open-source Spark 4.2 resolved the name in `QUALIFY` to the alias instead, so engines can even disagree.

    **Why:** the safe habit is to never reuse a column name as an alias in queries that filter or sort on it.

**Q40. Find the bug: two daily extracts are combined with `df_a.union(df_b)`. `df_a` has columns `(a, b)`, `df_b` has the same columns in the order `(b, a)`, and the combined data has the values swapped for every row from `df_b`.**

??? success "Answer"
    `union()` matches columns by position, like SQL `UNION ALL`, and ignores the names of the second input. Use `unionByName()`:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```python
    a = spark.sql("SELECT 1 AS a, 2 AS b")
    b = spark.sql("SELECT 20 AS b, 10 AS a")
    a.union(b).show()
    a.unionByName(b).show()
    ```

    ```text
    +---+---+
    |a  |b  |
    +---+---+
    |1  |2  |
    |20 |10 |
    +---+---+

    +---+---+
    |a  |b  |
    +---+---+
    |1  |2  |
    |10 |20 |
    +---+---+
    ```

    **Why:** no error is raised when the types are compatible, so the bug is silent. Note also that `union()` keeps duplicates (it is `UNION ALL`, not `UNION`); add `.distinct()` if you need set semantics.

## Sources

- [Data warehousing on Databricks](https://docs.databricks.com/aws/en/sql/) (last updated Oct 15, 2026)
- [Connect to a SQL warehouse](https://docs.databricks.com/aws/en/compute/sql-warehouse/) (last updated Oct 9, 2026)
- [SQL warehouse types](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-types) (last updated Oct 30, 2026)
- [Databricks SQL editor](https://docs.databricks.com/aws/en/sql/user/sql-editor/) (last updated Oct 30, 2026)
- [Notebook compute resources](https://docs.databricks.com/aws/en/notebooks/notebook-compute) (last updated Sep 11, 2026)
- [How to use the SQL reference](https://docs.databricks.com/aws/en/sql/language-manual/how-to-use) (last updated Sep 11, 2026)
- [ANSI_MODE](https://docs.databricks.com/aws/en/sql/language-manual/parameters/ansi_mode) (last updated Sep 11, 2026)
- [ANSI compliance in Databricks Runtime](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-ansi-compliance) (last updated Sep 11, 2026)
- [Configuration parameters](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-parameters) (last updated Oct 29, 2026)
- [Serverless compute limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations) (last updated Nov 5, 2026)
- [Migrate from classic compute to serverless compute](https://docs.databricks.com/aws/en/compute/serverless/migration) (last updated Nov 5, 2026)
- [`::` (colon colon sign) operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/coloncolonsign) (last updated Sep 11, 2026)
- [`?::` (question double colon sign) operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/questiondoublecolonsign) (last updated Sep 11, 2026)
- [Identifiers](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-identifiers) (last updated Sep 11, 2026)
- [Names](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-names) (last updated Nov 2, 2026)
- [Reserved words and schemas](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-reserved-words) (last updated Sep 11, 2026)
- [`STRING` type](https://docs.databricks.com/aws/en/sql/language-manual/data-types/string-type) (last updated Sep 11, 2026)
- [Adding comments to SQL statements](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-comment) (last updated Sep 11, 2026)
- [USE CATALOG](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-use-catalog) (last updated Oct 29, 2026)
- [USE SCHEMA](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-use-schema) (last updated Sep 11, 2026)
- [USE DATABASE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-usedb) (last updated Sep 11, 2026)
- [Name resolution](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-name-resolution) (last updated Oct 29, 2026)
- [PATH](https://docs.databricks.com/aws/en/sql/language-manual/parameters/path) (last updated Oct 29, 2026)
- [Query](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-query) (last updated Sep 11, 2026)
- [`SELECT` (subselect)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select) (last updated Sep 11, 2026)
- [QUALIFY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-qualify) (last updated Sep 11, 2026)
- [GROUP BY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-groupby) (last updated Sep 11, 2026)
- [ORDER BY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-orderby) (last updated Oct 6, 2026)
- [* (star) clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-star) (last updated Sep 11, 2026)
- [PIVOT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-pivot) (last updated Sep 11, 2026)
- [UNPIVOT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-unpivot) (last updated Sep 11, 2026)
- [LATERAL VIEW clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-lateral-view) (last updated Sep 11, 2026)
- [Table-valued function (TVF) invocation](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-tvf) (last updated Sep 11, 2026)
- [SORT BY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-sortby) (last updated Oct 6, 2026)
- [DISTRIBUTE BY clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-distributeby) (last updated Sep 11, 2026)
- [CLUSTER BY clause (SELECT)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-clusterby) (last updated Sep 11, 2026)
- [LIMIT clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-limit) (last updated Sep 11, 2026)
- [OFFSET clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-offset) (last updated Sep 11, 2026)
- [TABLESAMPLE clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-sampling) (last updated Sep 11, 2026)
- [Set operators](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-setops) (last updated Sep 11, 2026)
- [Hints](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-hints) (last updated Oct 12, 2026)
- [EXPLAIN](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-explain) (last updated Sep 11, 2026)
- [Parameter markers](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-parameter-marker) (last updated Sep 11, 2026)
- [Use named parameter markers](https://docs.databricks.com/aws/en/sql/user/queries/query-parameters) (last updated Oct 27, 2026)
- [IDENTIFIER clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-names-identifier-clause) (last updated Oct 15, 2026)
- [DECLARE VARIABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-declare-variable) (last updated Sep 11, 2026)
- [SET variable](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-set-variable) (last updated Sep 11, 2026)
- [EXECUTE IMMEDIATE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-execute-immediate) (last updated Sep 11, 2026)
- [Function invocation](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-function-invocation) (last updated Sep 11, 2026)
- [`mask` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/mask) (last updated Sep 11, 2026)
- [SQL Pipeline Syntax](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-pipeline) (last updated Sep 11, 2026)
- [Piped operation](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-pipeop) (last updated Sep 11, 2026)
- [NULL semantics](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-null-semantics) (last updated Sep 11, 2026)
- [`<=>` (lt eq gt sign) operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/lteqgtsign) (last updated Sep 11, 2026)
- [`is distinct` operator](https://docs.databricks.com/aws/en/sql/language-manual/functions/isdistinct) (last updated Sep 11, 2026)
- [`equal_null` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/equal_null) (last updated Sep 11, 2026)
- [MATCH_RECOGNIZE clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-match-recognize) (last updated Oct 21, 2026)
