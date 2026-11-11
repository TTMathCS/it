# 21. Programming in SQL

*Most Databricks SQL you write is one declarative statement: a query, a `MERGE`, a `CREATE TABLE`. Real jobs also need the parts around that statement: a value that changes per run, a check that stops a bad load, a loop over days to backfill, a table name chosen at run time, a reusable calculation, a rule that hides rows from some users. This chapter covers the tools Databricks SQL gives you for that: SQL scripting (`BEGIN ... END` with variables, `IF`, loops and error handlers), dynamic SQL with `EXECUTE IMMEDIATE`, SQL and Python user-defined functions, stored procedures, recursive CTEs, views, row filters and column masks. Interviewers ask about these to see whether you know when procedural SQL is the right tool, whether you can parameterize a query without opening it to SQL injection, and whether you know what Unity Catalog adds on top of open-source Spark.*

!!! abstract "In this chapter"
    **You will learn:**

    - what a SQL script is (a `BEGIN ... END` compound statement), how local variables, scopes and labels work, and how they differ from session variables
    - control flow: `IF`, the `CASE` statement, `WHILE`, `REPEAT`, `LOOP`, `FOR`, `ITERATE` and `LEAVE`
    - error handling: conditions, `EXIT` and `CONTINUE` handlers, `SIGNAL`, `RESIGNAL`, `GET DIAGNOSTICS`, and `BEGIN ATOMIC`
    - dynamic SQL done safely: parameter markers inside scripts, `EXECUTE IMMEDIATE ... INTO ... USING`, `IDENTIFIER`, and what SQL injection looks like
    - SQL scalar and table functions, Unity Catalog Python UDFs, and why a SQL UDF is usually faster than a Python one
    - stored procedures: `CREATE PROCEDURE`, `CALL`, `IN`/`OUT`/`INOUT` parameters and `SQL SECURITY`
    - recursive CTEs (date spines, hierarchies) and their limits
    - views, dynamic views, row filters and column masks
    - which parts run in open-source Apache Spark 4.2 and which are Databricks only

    **You need:** [chapter 17](17-Databricks-SQL-vs-Standard.md) (section 17.9 introduces parameter markers, `IDENTIFIER`, session variables and named arguments; this chapter builds on it), [chapter 5](05-Unity-Catalog.md) (catalogs, schemas and privileges), and [chapter 18](18-Semi-Structured-Data.md) for lambdas.

    **Levels:** sections 21.1 to 21.3 beginner, 21.4 to 21.8 intermediate, 21.9 and 21.10 expert.

**About the examples.** All "Run here" examples use the Red Rock Supply tables (`customers`, `products`, `orders`, `order_items`) in a schema called `silver`, and write results to a schema called `gold`. On Databricks these would be Unity Catalog names such as `shop.silver.orders` and `shop.gold.daily_revenue`; locally there is no Unity Catalog, so the catalog is Spark's built-in `spark_catalog`. The `orders` table has 8 rows (orders 1001 to 1008, four in CAD and four in USD); order 1004 is `CANCELLED` and order 1008 has a `NULL` status on purpose. The scripts are in `src/ch21/` (`rrs.py` creates the tables) with their full output in the matching `.out` files. Error messages are shortened here to the error class and first sentence.

A SQL script is sent to Spark as one statement. Locally that means one `spark.sql("BEGIN ... END")` call; in a Databricks notebook the compound statement "must be the only statement in the cell" (BEGIN END compound statement page).

**Version lines.** Every Databricks feature below carries the "Applies to" line of its reference page. "Databricks SQL" means SQL warehouses; "Databricks Runtime N and above" means clusters and serverless compute at that runtime. Where the local open-source engine behaved differently from a Databricks page, or a claim could not be tested, the text says so.

## 21.1 The toolbox at a glance
*Level: beginner.*

**The problem.** A nightly job must load yesterday's orders into a gold table. Yesterday changes every night. If `silver.orders` has rows without a status, the load should stop and say why. Sometimes you must backfill a week. Analysts want the "net of tax" calculation written once, not copied into twenty dashboards. And the finance team may see every order while support staff see only Canadian customers.

Without procedural features, these needs are met outside SQL: by a scheduler, a Python script that builds SQL strings, or a database's own procedural language (PL/pgSQL, T-SQL). Databricks SQL now has most of these pieces inside SQL itself:

| Need | Tool | Applies to (reference page) | Runs on open-source Spark 4.2 here? |
| --- | --- | --- | --- |
| A value that lives for the session | Session variable: `DECLARE VARIABLE`, `SET VAR` | Databricks SQL, Databricks Runtime 14.1 and above | Yes ([17.9](17-Databricks-SQL-vs-Standard.md)) |
| A value supplied by the caller | Parameter markers `:name` and `?` | Databricks SQL, Databricks Runtime (named markers: 12.1 and above; unnamed: 13.3 and above) | Yes, without the Delta extension (21.5) |
| A table or column name supplied at run time | `IDENTIFIER(...)` | Databricks SQL, Databricks Runtime 13.3 LTS and above | Yes |
| A statement built at run time | `EXECUTE IMMEDIATE` | Databricks SQL, Databricks Runtime 14.3 and above | Yes |
| Variables, `IF`, loops, error handlers | SQL scripting (`BEGIN ... END`) | Databricks SQL, Databricks Runtime 16.3 and above | Mostly; no `SIGNAL`, `RESIGNAL`, `GET DIAGNOSTICS` or `ATOMIC`; `CONTINUE` handlers and cursors only behind configuration flags that are off by default (21.4) |
| A reusable calculation or parameterized query | SQL UDF (`CREATE FUNCTION ... RETURN`) | Databricks SQL, Databricks Runtime | Yes |
| Python logic callable from SQL, governed | `CREATE FUNCTION ... LANGUAGE PYTHON` | Databricks SQL, Databricks Runtime 13.3 LTS and above; needs Unity Catalog | No |
| A saved script with parameters, run by name | `CREATE PROCEDURE`, `CALL` | Databricks SQL, Databricks Runtime 17.0 and above; Unity Catalog only | No |
| Hierarchies and generated series | `WITH RECURSIVE` | Databricks SQL, Databricks Runtime 17.0 and later | Yes |
| Hide rows or values per user | Row filters and column masks | Databricks SQL, Databricks Runtime 12.2 LTS and above; Unity Catalog only | No |

Section 17.9 already shows the basics of parameter markers, `IDENTIFIER`, session variables, single `EXECUTE IMMEDIATE` statements and named arguments (`name => value`). This chapter uses them inside scripts and functions and does not repeat the basics. SQL pipe syntax (`|>`) is in [section 17.10](17-Databricks-SQL-vs-Standard.md); higher-order functions and lambdas (`transform(arr, x -> ...)`) are in [section 18.8](18-Semi-Structured-Data.md). One lambda rule matters for this chapter: the Lambda functions page says the lambda body is "any simple expression referencing `paramN`, which does not contain a subquery or a SQL user-defined function" (practice question 30 shows what the local engine does).

!!! tip "In the interview"
    **"Can you write procedural logic in Databricks SQL?"** Yes. Since Databricks Runtime 16.3 (and on SQL warehouses), SQL scripting gives you `BEGIN ... END` blocks with local variables, `IF`, `CASE`, `WHILE`, `FOR` loops and error handlers, and since Runtime 17.0 you can save a script as a stored procedure in Unity Catalog and run it with `CALL`. Then add the caveat: loops are for orchestration (one statement per day, per table), not for processing rows, because one set-based statement is far faster than a row-by-row loop.

## 21.2 SQL scripts: blocks, local variables and scope
*Level: beginner.*

**The problem.** A daily load is several statements that share values: the run date, a row count, a status. With single statements you either repeat the value in every statement or keep it in session variables that outlive the job. You want a unit that holds its own variables and runs top to bottom.

**The tool.** A **SQL script** is one **compound statement**: `BEGIN`, a list of statements each ending in `;`, `END`. The SQL scripting page: "Any SQL script consists of and starts with a compound statement block (`BEGIN ... END`)" (Applies to: Databricks SQL, Databricks Runtime 16.3 and above). The page calls the syntax "SQL/PSM standard-based" (SQL/PSM is the procedural part of the SQL standard).

The order inside a block is fixed by the syntax on the BEGIN END compound statement page:

*Syntax summary from [BEGIN END compound statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/compound-stmt) (a grammar, not a runnable statement).*
```text
[ label : ] BEGIN [ ATOMIC ]
  [ { declare_variable | declare_condition } ; [...] ]
  [ declare_cursor ; [...] ]
  [ declare_handler ; [...] ]
  [ SQL_statement ; [...] ]
END [ label ]
```

So: variables and conditions first, then cursors, then handlers, then the statements. A **local variable** (`DECLARE name type [DEFAULT expr]`) exists only inside its block. If you leave out the type you must give a `DEFAULT`, and the type comes from it; without a default the variable starts as `NULL`. Inside a script you assign with plain `SET x = ...`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE run_date DATE DEFAULT DATE'2026-03-01';
  DECLARE n_orders INT;
  SET n_orders = (SELECT count(*) FROM silver.orders WHERE to_date(order_ts) = run_date);
  VALUES (run_date, n_orders);
END
```

Output:
```text
+----------+----+
|col1      |col2|
+----------+----+
|2026-03-01|2   |
+----------+----+
```

A realistic step does DML. This one makes a day's load **idempotent** (safe to rerun) by deleting the day before inserting it, then returns the gold rows:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE run_date DATE DEFAULT DATE'2026-03-03';
  DELETE FROM gold.daily_revenue WHERE order_date = run_date;
  INSERT INTO gold.daily_revenue
    SELECT to_date(order_ts), currency, count(*), sum(amount)
    FROM silver.orders
    WHERE to_date(order_ts) = run_date AND coalesce(status, '') <> 'CANCELLED'
    GROUP BY ALL;
  SELECT * FROM gold.daily_revenue ORDER BY order_date, currency;
END
```

Output (the same two rows again when the script runs a second time, see `ex01_script_basics.out`):
```text
+----------+--------+------+-------+
|order_date|currency|orders|revenue|
+----------+--------+------+-------+
|2026-03-03|CAD     |1     |318.00 |
|2026-03-03|USD     |1     |29.95  |
+----------+--------+------+-------+
```

On Databricks you would more often write this as one `INSERT INTO ... REPLACE WHERE order_date = ...` or a `MERGE` (see chapter 20); the script form is shown because it is the shape every multi-step load takes.

### Result sets

The compound statement page says: "Any `SELECT` or `VALUES` statement produces a result set that the invoker can consume." What the caller actually sees depends on the client. Locally, `spark.sql()` returned only the **last** result:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  SELECT 'first' AS step;
  SELECT 'second' AS step;
END
```

Output:
```text
+------+
|step  |
+------+
|second|
+------+
```

How the Databricks SQL editor or a notebook cell displays a script with several result sets is **not verified** here. For stored procedures, the CREATE PROCEDURE page states the rule directly: "The last executed query is the result set of a procedure."

### Several variables, nested blocks and labels

Since Databricks Runtime 17.2 one `DECLARE` can name several variables ("Prior to Databricks Runtime 17.2 you can only declare one variable at a time"). A nested `BEGIN ... END` opens a new **scope**: a variable declared inside hides an outer one with the same name, and disappears at the inner `END`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE lo, hi DECIMAL(10,2) DEFAULT 100;
  DECLARE label = 'big orders';
  SET hi = 300;
  SELECT label, count(*) AS n FROM silver.orders WHERE amount BETWEEN lo AND hi;
END;

BEGIN
  DECLARE x INT DEFAULT 1;
  inner_blk: BEGIN
    DECLARE x INT DEFAULT 2;
    SET x = x + 10;
  END inner_blk;
  VALUES (x);
END;
```

Output (two separate runs):
```text
+----------+---+
|label     |n  |
+----------+---+
|big orders|3  |
+----------+---+

+----+
|col1|
+----+
|1   |
+----+
```

Both `lo` and `hi` got the default 100; `hi` was then set to 300, and three orders (249.00, 189.50, 159.00) fall in the range. In the second script, `SET x = x + 10` changed the inner `x`; the outer `x` is still 1.

A **label** (`name:` before `BEGIN` or a loop, repeated after `END`) names a block so that `LEAVE`, `ITERATE` and qualified variable names (`b1.x`) can refer to it. The page has one rule that surprises people: "label must not be specified for a top level compound statement or for an `ATOMIC` compound statement."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
load_day: BEGIN
  VALUES (1);
END load_day
```

Output:
```text
ERROR: [PARSE_SYNTAX_ERROR] Syntax error at or near 'load_day'. SQLSTATE: 42601 (line 1, pos 0)
```

### Local variables and session variables

A **session variable** (`DECLARE VARIABLE` outside any script, see [section 17.9](17-Databricks-SQL-vs-Standard.md)) lives until the session ends; a local variable lives until its block ends. The SQL scripting page names session variables as the way "to pass scalar values or small sets of arrays or maps from one SQL script to another", and parameter markers as the way to pass values in "from a notebook widget, Python, or another language".

One syntax rule bites everyone. The SET variable page: "Outside of a compound statement the keywords `VAR` or `VARIABLE` are mandatory to disambiguate from a SET config statement. Within a compound statement `VAR` or `VARIABLE` are not allowed."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
DECLARE VARIABLE run_count INT DEFAULT 0;   -- a session variable

BEGIN
  SET VAR run_count = run_count + 1;        -- not allowed inside a script
END;

BEGIN
  SET run_count = run_count + 1;            -- plain SET also reaches session variables
END;

SELECT run_count;
```

Output:
```text
ERROR: [PARSE_SYNTAX_ERROR] Syntax error at or near 'run_count': extra input 'run_count'. SQLSTATE: 42601 (line 2, pos 10)

+---------+
|run_count|
+---------+
|1        |
+---------+
```

Names resolve "from the innermost scope outward" (SQL scripting page), so a local variable with the same name as a session variable hides it inside the block.

### What happens when a statement fails

Without an error handler, the first failing statement ends the script and the error goes to the caller. Statements that already ran are **not** undone: the page describes `NOT ATOMIC` as "if an SQL statement within the compound fails, previous SQL statements will not be rolled back. This is the default behavior when `ATOMIC` is not specified."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  INSERT INTO gold.load_log VALUES ('step 1 done');
  SELECT 1 / 0;
  INSERT INTO gold.load_log VALUES ('step 2 done');
END;
SELECT * FROM gold.load_log;
```

Output:
```text
ERROR: [DIVIDE_BY_ZERO] Division by zero. Use `try_divide` to tolerate divisor being 0 and return NULL instead. If necessary set "spark.sql.ansi.enabled" to "false" to bypass this error. SQLSTATE: 22012

+-----------+
|step       |
+-----------+
|step 1 done|
+-----------+
```

Section 21.4 shows how to catch the error, and `BEGIN ATOMIC` for all-or-nothing blocks.

!!! warning "A script is not a transaction"
    Each statement in a plain `BEGIN ... END` commits on its own. If step 3 of 5 fails, steps 1 and 2 stay done. Either make every step idempotent (delete-then-insert, `MERGE`, `REPLACE WHERE`) so a rerun is safe, or use `BEGIN ATOMIC` where it is supported (section 21.4).

## 21.3 Control flow: IF, CASE, loops, ITERATE and LEAVE
*Level: beginner.*

**The problem.** A load must branch (stop if the data is bad, warn if it is a little bad) and repeat (one pass per day of a backfill, one pass per table of an audit). Every statement in this section "may only be used within a compound statement", and all carry "Applies to: Databricks SQL Databricks Runtime 16.3 and above" on their pages (the CASE statement page lists only "Databricks Runtime 16.3 and above").

| Statement | Shape | Use it for |
| --- | --- | --- |
| `IF` | `IF c THEN ... [ELSEIF c THEN ...] [ELSE ...] END IF` | Branches on conditions |
| `CASE` statement | `CASE expr WHEN v THEN ... END CASE` or `CASE WHEN c THEN ... END CASE` | Branches on one value (simple) or on conditions (searched) |
| `WHILE` | `[lbl:] WHILE c DO ... END WHILE [lbl]` | Repeat while a condition is true (checked before each pass) |
| `REPEAT` | `[lbl:] REPEAT ... UNTIL c END REPEAT [lbl]` | Repeat until a condition is true (checked after each pass, so at least once) |
| `LOOP` | `[lbl:] LOOP ... END LOOP [lbl]` | Repeat until a `LEAVE` |
| `FOR` | `[lbl:] FOR [var AS] query DO ... END FOR [lbl]` | Once per row of a query |
| `ITERATE lbl` | | Skip to the next pass of loop `lbl` |
| `LEAVE lbl` | | Exit loop or block `lbl` |

### IF and the CASE statement

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE bad_rows INT;
  SET bad_rows = (SELECT count_if(status IS NULL) FROM silver.orders);
  IF bad_rows = 0 THEN
    VALUES ('ok: load gold');
  ELSEIF bad_rows <= 2 THEN
    VALUES ('warn: ' || bad_rows || ' order(s) without status, loading anyway');
  ELSE
    VALUES ('stop: too many bad rows');
  END IF;
END
```

Output:
```text
+-----------------------------------------------+
|col1                                           |
+-----------------------------------------------+
|warn: 1 order(s) without status, loading anyway|
+-----------------------------------------------+
```

Two details from the IF page: the keyword is `ELSEIF` (one word), and the `ELSE` branch runs when "all `condition` are `false` or `null`". A `NULL` condition is not true. Comparing with an unset variable is the usual way to get one:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE threshold INT;                    -- no DEFAULT: NULL
  IF (SELECT count(*) FROM silver.orders) > threshold THEN
    VALUES ('then branch');
  ELSE
    VALUES ('else branch (threshold is NULL)');
  END IF;
END
```

Output:
```text
+-------------------------------+
|col1                           |
+-------------------------------+
|else branch (threshold is NULL)|
+-------------------------------+
```

The **`CASE` statement** runs statements; the `CASE` *expression* you know from queries returns a value ([section 19.6](19-Function-Toolbox.md)). They look alike, but the statement ends with `END CASE` and each branch holds statements ending in `;`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE mode STRING DEFAULT 'incremental';
  CASE mode
    WHEN 'full' THEN
      SELECT 'full reload' AS plan, count(*) AS rows_to_read FROM silver.orders;
    WHEN 'incremental' THEN
      SELECT 'last day only' AS plan, count(*) AS rows_to_read
      FROM silver.orders WHERE order_ts >= TIMESTAMP'2026-03-04';
    ELSE
      VALUES ('unknown mode', 0);
  END CASE;
END
```

Output:
```text
+-------------+------------+
|plan         |rows_to_read|
+-------------+------------+
|last day only|2           |
+-------------+------------+
```

When no `WHEN` matches and there is no `ELSE`, the local engine simply went on to the next statement (`ex02_control_flow.out`, test 4). The Databricks CASE statement page does not say what happens in that case, so this is **not verified** for Databricks. Write an `ELSE` that fails loudly when an unknown value is a bug.

### WHILE and REPEAT: a backfill

A **backfill** reloads a range of past days. With a loop, each day reuses the idempotent delete-then-insert from section 21.2:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE d DATE DEFAULT DATE'2026-03-01';
  WHILE d <= DATE'2026-03-04' DO
    DELETE FROM gold.daily_revenue WHERE order_date = d;
    INSERT INTO gold.daily_revenue
      SELECT to_date(order_ts), currency, count(*), sum(amount)
      FROM silver.orders
      WHERE to_date(order_ts) = d AND coalesce(status, '') <> 'CANCELLED'
      GROUP BY ALL;
    SET d = d + INTERVAL 1 DAY;
  END WHILE;
  SELECT * FROM gold.daily_revenue ORDER BY order_date, currency;
END
```

Output:
```text
+----------+--------+------+-------+
|order_date|currency|orders|revenue|
+----------+--------+------+-------+
|2026-03-01|CAD     |1     |59.90  |
|2026-03-01|USD     |1     |249.00 |
|2026-03-02|CAD     |1     |189.50 |
|2026-03-03|CAD     |1     |318.00 |
|2026-03-03|USD     |1     |29.95  |
|2026-03-04|CAD     |1     |78.00  |
|2026-03-04|USD     |1     |159.00 |
+----------+--------+------+-------+
```

The same seven rows come from one `SELECT ... WHERE to_date(order_ts) BETWEEN DATE'2026-03-01' AND DATE'2026-03-04' ... GROUP BY ALL` (also in the `.out` file). That one statement reads the table once; the loop ran eight DML statements. The Databricks loop pages make the same point, ending each loop example with "Compare with the much more efficient relational computation". A loop over days still makes sense when each day is large, when you want to commit day by day, or when a failure should leave the finished days in place.

`WHILE` checks its condition before each pass; `REPEAT ... UNTIL` checks after, so its body always runs at least once. A `NULL` condition stops a `WHILE` before the first pass:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE stop_at INT;          -- NULL
  DECLARE w INT DEFAULT 0;
  DECLARE r INT DEFAULT 0;
  WHILE w < stop_at DO SET w = w + 1; END WHILE;
  REPEAT SET r = r + 1; UNTIL r >= 0 END REPEAT;
  VALUES (w, r);
END
```

Output:
```text
+----+----+
|col1|col2|
+----+----+
|0   |1   |
+----+----+
```

### LOOP, ITERATE and LEAVE

`LOOP` has no condition; you leave it with `LEAVE label`. `ITERATE label` skips the rest of the current pass. Both need the label: plain `LEAVE;` is a syntax error (`[PARSE_SYNTAX_ERROR] Syntax error at or near ';'` in `ex02_control_flow.out`).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE id INT DEFAULT 1000;
  DECLARE total DECIMAL(12,2) DEFAULT 0;
  scan: LOOP
    SET id = id + 1;
    IF id > 1006 THEN LEAVE scan; END IF;
    IF (SELECT status FROM silver.orders WHERE order_id = id) = 'CANCELLED' THEN
      ITERATE scan;
    END IF;
    SET total = total + (SELECT amount FROM silver.orders WHERE order_id = id);
  END LOOP scan;
  VALUES (id, total);
END
```

Output:
```text
+----+------+
|col1|col2  |
+----+------+
|1007|846.35|
+----+------+
```

Orders 1001 to 1006 without the cancelled 1004: 59.90 + 249.00 + 189.50 + 318.00 + 29.95 = 846.35. This is a teaching example of the syntax; in real code it is one `SELECT sum(amount) ... WHERE order_id BETWEEN 1001 AND 1006 AND status <> 'CANCELLED'`.

With nested loops, the label says which loop to leave:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE i INT DEFAULT 0;
  DECLARE j INT;
  DECLARE pairs STRING DEFAULT '';
  outer_loop: WHILE i < 3 DO
    SET i = i + 1;
    SET j = 0;
    inner_loop: WHILE j < 3 DO
      SET j = j + 1;
      IF i * j = 4 THEN LEAVE outer_loop; END IF;
      SET pairs = pairs || i || j || ' ';
    END WHILE inner_loop;
  END WHILE outer_loop;
  VALUES (trim(pairs));
END
```

Output:
```text
+-----------+
|col1       |
+-----------+
|11 12 13 21|
+-----------+
```

At `i = 2, j = 2` the product is 4 and `LEAVE outer_loop` ends both loops; `LEAVE inner_loop` would only have ended the inner one.

### FOR: once per row of a query

`FOR [name AS] query DO ... END FOR` runs its body once per row. Inside, the query's columns are available unqualified (`amount`) or qualified with the loop variable name (`o.amount`); the FOR page says "To qualify loop column references, use the `variable_name`, not the `label`."

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  FOR o AS SELECT order_id, amount FROM silver.orders WHERE status IS NULL ORDER BY order_id DO
    INSERT INTO gold.load_log VALUES ('order ' || o.order_id || ' has no status, amount ' || o.amount);
  END FOR;
  SELECT * FROM gold.load_log;
END
```

Output:
```text
+--------------------------------------+
|msg                                   |
+--------------------------------------+
|order 1008 has no status, amount 78.00|
+--------------------------------------+
```

Notes from the FOR page worth knowing:

- If the loop body modifies the table the query reads, "For Delta tables, the query will remain unaffected."
- "Databricks does not guarantee the full execution of the query if the `FOR` loop completes prematurely due to a `LEAVE` statement or an error condition."
- "Often `FOR` loops can be replaced with relational queries, which are typically more efficient." The log insert above is better written as one `INSERT INTO gold.load_log SELECT 'order ' || order_id || ... FROM silver.orders WHERE status IS NULL`.

A good use of `FOR` is a loop over *metadata*: a list of tables, dates or currencies, where each pass runs one set-based statement. Section 21.5 loops over table names with `EXECUTE IMMEDIATE`.

!!! warning "The order of ITERATE and LEAVE checks matters"
    In a loop body, an `ITERATE` placed before a `LEAVE` check can skip that check for the very row that should stop the loop. Practice question 9 shows a `FOR` loop meant to stop at order 1006 that reads all 8 rows for this reason.

## 21.4 Error handling: conditions, handlers, SIGNAL and RESIGNAL
*Level: intermediate.*

**The problem.** A nightly script should not just die with "Division by zero". It should write a log row saying which step failed, perhaps skip an optional step, and still fail the job so that the scheduler alerts someone. That is what **condition handlers** do.

**The terms.**

- A **condition** is a named error: a Databricks error class such as `DIVIDE_BY_ZERO`, a `SQLSTATE` (a five-character code, for example `'22012'` for division by zero), or one you declare: `DECLARE late_data CONDITION FOR SQLSTATE '45001'`.
- A **handler** is code that runs when a condition is raised inside its block: `DECLARE { EXIT | CONTINUE } HANDLER FOR condition_values handler_action`. The action is one statement; use a nested `BEGIN ... END` for several.
- `SQLEXCEPTION` catches "any `SQLSTATE` which is not `XX***` and not `02***`"; `NOT FOUND` catches SQLSTATE class `'02'`, such as the end of a cursor.

The SQL scripting page sets the rules for choosing the **most appropriate handler** (Figure 21.1):

- "The applicable condition handlers defined in the innermost compound statement within which the exception was raised are appropriate."
- "If more than one appropriate handler is available, the most specific handler is the most appropriate. For example, a handler on a named condition is more specific than one on a named `SQLSTATE`." `SQLEXCEPTION` is the least specific.
- "A condition handler cannot apply to any statement defined in its own body or the body of any condition handler declared in the same compound statement." An error inside a handler goes outward.
- "An `EXIT` handler executes its statement, then exits the compound statement that declared the handler." A `CONTINUE` handler resumes after the failing statement.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 330" role="img" aria-label="A SQL script is a top-level BEGIN END block. It declares variables, conditions and handlers in a fixed order. A nested labeled block has its own handler. When a statement fails, the innermost block's handlers are searched first and the most specific one wins; if none matches, the search moves to the outer block; if nothing matches, the error goes to the caller.">
<defs><marker id="a21-1" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<rect x="8" y="8" width="624" height="314" rx="8" fill="none" stroke="currentColor" stroke-width="1.5"/>
<text x="22" y="32" font-size="15" font-weight="bold" fill="currentColor">BEGIN   (top-level block: no label allowed)</text>
<text x="34" y="56" font-size="13" fill="currentColor">1. DECLARE variables and conditions</text>
<text x="34" y="76" font-size="13" fill="currentColor">2. DECLARE EXIT HANDLER FOR SQLEXCEPTION ... (outer handler)</text>
<rect x="34" y="90" width="372" height="134" rx="6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="5 3"/>
<text x="48" y="112" font-size="14" font-weight="bold" fill="currentColor">load_orders: BEGIN</text>
<text x="60" y="136" font-size="13" fill="currentColor">DECLARE EXIT HANDLER FOR DIVIDE_BY_ZERO ...</text>
<text x="60" y="160" font-size="13" fill="currentColor">INSERT ...  (done, stays done)</text>
<text x="60" y="184" font-size="13" font-weight="bold" fill="currentColor">SELECT amount / 0   -- error raised here</text>
<text x="48" y="212" font-size="14" font-weight="bold" fill="currentColor">END load_orders</text>
<line x1="392" y1="180" x2="436" y2="150" stroke="currentColor" stroke-width="1.5" marker-end="url(#a21-1)"/>
<rect x="438" y="90" width="182" height="134" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="450" y="112" font-size="14" font-weight="bold" fill="currentColor">Which handler runs?</text>
<text x="450" y="136" font-size="13" fill="currentColor">a. innermost block first</text>
<text x="450" y="158" font-size="13" fill="currentColor">b. most specific wins:</text>
<text x="462" y="178" font-size="13" fill="currentColor">name &gt; SQLSTATE &gt;</text>
<text x="462" y="198" font-size="13" fill="currentColor">SQLEXCEPTION</text>
<text x="450" y="218" font-size="13" fill="currentColor">c. none: go outward</text>
<line x1="120" y1="224" x2="120" y2="246" stroke="currentColor" stroke-width="1.5" marker-end="url(#a21-1)"/>
<text x="130" y="242" font-size="13" fill="currentColor">inner EXIT handler ran: carry on below</text>
<text x="34" y="266" font-size="13" fill="currentColor">3. next statement after END load_orders</text>
<text x="34" y="290" font-size="13" fill="currentColor">4. outer handler ran: leave the script (Databricks: RESIGNAL to fail it)</text>
<text x="22" y="314" font-size="15" font-weight="bold" fill="currentColor">END   (no handler matched anywhere: the error goes to the caller)</text>
</svg>
<figcaption>Figure 21.1. How blocks and handlers nest in a SQL script. Declarations come first in a fixed order (variables and conditions, cursors, handlers), then statements. A failing statement is handled by the most specific handler of the innermost block that has one; an EXIT handler then leaves the block that declared it.</figcaption>
</figure>

### EXIT handlers in practice

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE EXIT HANDLER FOR DIVIDE_BY_ZERO
    BEGIN
      VALUES ('no shipped CAD orders on that day, rate not computed');
    END;
  SELECT count_if(status = 'CANCELLED') / count_if(status = 'SHIPPED') AS cancel_rate
  FROM silver.orders
  WHERE currency = 'CAD' AND to_date(order_ts) = DATE'2026-03-02';
END
```

Output:
```text
+----------------------------------------------------+
|col1                                                |
+----------------------------------------------------+
|no shipped CAD orders on that day, rate not computed|
+----------------------------------------------------+
```

On 2 March the only CAD order (1003) is `PLACED`, so the divisor is 0 and the handler runs. (In real code, `try_divide` returns `NULL` instead of failing; the handler is here to show the mechanism.) The same handler written as `FOR SQLSTATE '22012'` catches it too. When both a named handler and a `SQLEXCEPTION` handler exist, the named one wins:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN VALUES ('generic SQLEXCEPTION handler'); END;
  DECLARE EXIT HANDLER FOR DIVIDE_BY_ZERO
    BEGIN VALUES ('DIVIDE_BY_ZERO handler'); END;
  SELECT 100 / 0;
END
```

Output:
```text
+----------------------+
|col1                  |
+----------------------+
|DIVIDE_BY_ZERO handler|
+----------------------+
```

`EXIT` leaves only the block that declared the handler. Put an optional step in its own nested block, and the script goes on after it:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE steps STRING DEFAULT '';
  load_orders: BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
      BEGIN SET steps = steps || 'orders FAILED; '; END;
    SET steps = steps || 'orders started; ';
    SELECT CAST('abc' AS INT);
    SET steps = steps || 'orders done; ';
  END load_orders;
  SET steps = steps || 'customers done';
  VALUES (steps);
END
```

Output:
```text
+---------------------------------------------+
|col1                                         |
+---------------------------------------------+
|orders started; orders FAILED; customers done|
+---------------------------------------------+
```

`orders done` never ran: the handler ran and left `load_orders`. Then execution continued after `END load_orders`.

### Log, then fail anyway

Swallowing every error is the classic mistake: the job shows green while gold is half loaded. The usual pattern is to log and then re-raise. On Databricks you write `RESIGNAL` (below). Open-source Spark 4.2 has no `RESIGNAL`, so this run uses the built-in `raise_error` function, which is also available on Databricks:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
      INSERT INTO gold.load_log VALUES (current_timestamp(), 'daily_revenue', 'FAILED');
      SELECT raise_error('daily_revenue load failed, see gold.load_log');
    END;
  INSERT INTO gold.load_log VALUES (current_timestamp(), 'daily_revenue', 'STARTED');
  SELECT CAST('not a number' AS DECIMAL(10,2));
END;

SELECT step, outcome FROM gold.load_log ORDER BY run_ts, outcome DESC;
```

Output:
```text
ERROR: [USER_RAISED_EXCEPTION] daily_revenue load failed, see gold.load_log SQLSTATE: P0001

+-------------+-------+
|step         |outcome|
+-------------+-------+
|daily_revenue|STARTED|
|daily_revenue|FAILED |
+-------------+-------+
```

The error raised inside the handler was not caught by the same `SQLEXCEPTION` handler (a handler does not apply to its own body), so it reached the caller, and the log row written before it stayed.

Two more behaviors from `ex03_handlers.out`: a handler for a declared condition (`FOR SQLSTATE '45001'`) does not catch a division by zero, which then fails the script normally; and a `SQLEXCEPTION` handler catches `raise_error` (SQLSTATE `P0001`).

!!! warning "Local quirk: errors inside a `SET x = (subquery)`"
    In this local Spark 4.2 build, when a runtime error (here a division by zero computed from table data) happens inside the scalar subquery of a `SET` statement, the script fails with `java.lang.NullPointerException: Cannot invoke "String.toUpperCase(java.util.Locale)" because "condition" is null` instead of calling the matching handler (`ex03_handlers.out`, test 10). The same expression as a plain `SELECT` statement is handled correctly (test 1). This looks like an open-source engine bug; whether Databricks has it is **not verified**.

### Databricks only: CONTINUE handlers, SIGNAL, RESIGNAL, GET DIAGNOSTICS

With its default settings, open-source Spark 4.2 rejects all four (`ex03_handlers.out`, test 9): a `CONTINUE` handler gives `[UNSUPPORTED_FEATURE.CONTINUE_EXCEPTION_HANDLER] ... CONTINUE exception handler is not supported. Use EXIT handler.`, and `SIGNAL` and `GET DIAGNOSTICS` are syntax errors (a separate check gave the same syntax error for `RESIGNAL`). The Spark 4.2.0 SQL scripting page describes `CONTINUE` handlers and cursors, and the engine does have them, but behind two configuration flags that are off by default and are not mentioned on that page: `spark.sql.scripting.continueHandlerEnabled` and `spark.sql.scripting.cursorEnabled`. Without them a cursor fails with `UNSUPPORTED_FEATURE.SQL_CURSOR`; with both set to `true`, the test 9 `CONTINUE` handler script returned `-1`, and a cursor loop ended by a `CONTINUE HANDLER FOR NOT FOUND` ran correctly. `SIGNAL` and `RESIGNAL` stayed syntax errors with the flags on. On Databricks all four exist with these version lines:

| Feature | What it does | Applies to (page) |
| --- | --- | --- |
| `DECLARE CONTINUE HANDLER` | Runs the handler, then "execution resumes with the statement following the one that raised the condition" | Databricks Runtime 18.1 and above (BEGIN END compound statement) |
| `SIGNAL` | Raises a condition: a declared one, a system error class, or a `SQLSTATE` with a message | Databricks SQL, Databricks Runtime 16.3 and above |
| `RESIGNAL` | Inside a handler: "Re-raises the condition handled by the condition handler" | Databricks SQL, Databricks Runtime 16.3 and above |
| `GET DIAGNOSTICS CONDITION 1 ...` | Inside a handler: reads `MESSAGE_TEXT`, `RETURNED_SQLSTATE`, `MESSAGE_ARGUMENTS`, `CONDITION_IDENTIFIER`, `LINE_NUMBER` | Databricks SQL, Databricks Runtime 16.3 and above |
| `GET DIAGNOSTICS v = ROW_COUNT` | Rows affected by the most recent DML statement | Databricks SQL, Databricks Runtime 18 LTS and above |

*Databricks only, not run here. Syntax from [SIGNAL statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/signal-stmt), [RESIGNAL statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/resignal-stmt) and [GET DIAGNOSTICS statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/get-diagnostics-stmt).*
```sql
-- Syntax
SIGNAL { condition_name
         [ SET { MESSAGE_ARGUMENTS = argument_map |
                 MESSAGE_TEXT = message_str } ] |
         SQLSTATE [VALUE] sqlstate [ SET MESSAGE_TEXT = message_str ] }

RESIGNAL

GET DIAGNOSTICS CONDITION 1
  { variable_name = condition_info_item } [, ...]
GET DIAGNOSTICS
  { variable_name = statement_info_item } [, ...]
```

Put together, a load that refuses an empty day, logs every failure with its details, and still fails the run:

*Databricks only, not run here. Syntax from [SIGNAL statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/signal-stmt), [RESIGNAL statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/resignal-stmt) and [GET DIAGNOSTICS statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/get-diagnostics-stmt).*
```sql
BEGIN
  DECLARE run_date DATE DEFAULT DATE'2026-03-05';
  DECLARE rc BIGINT;
  DECLARE no_orders CONDITION FOR SQLSTATE '45001';
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
      DECLARE msg STRING;
      DECLARE state STRING;
      GET DIAGNOSTICS CONDITION 1 msg = MESSAGE_TEXT, state = RETURNED_SQLSTATE;
      INSERT INTO shop.gold.load_log VALUES (current_timestamp(), 'daily_revenue', 'FAILED ' || state || ': ' || msg);
      RESIGNAL;
    END;

  SET rc = (SELECT count(*) FROM shop.silver.orders WHERE to_date(order_ts) = run_date);
  IF rc = 0 THEN
    SIGNAL no_orders SET MESSAGE_TEXT = 'no orders for the run date';
  END IF;

  DELETE FROM shop.gold.daily_revenue WHERE order_date = run_date;
  INSERT INTO shop.gold.daily_revenue
    SELECT to_date(order_ts), currency, count(*), sum(amount)
    FROM shop.silver.orders
    WHERE to_date(order_ts) = run_date AND coalesce(status, '') <> 'CANCELLED'
    GROUP BY ALL;
  GET DIAGNOSTICS rc = ROW_COUNT;      -- Databricks Runtime 18 LTS and above
  INSERT INTO shop.gold.load_log VALUES (current_timestamp(), 'daily_revenue', 'OK, ' || rc || ' rows');
END
```

Details from the pages:

- `GET DIAGNOSTICS CONDITION 1` must be "the first statement in the handler".
- A declared condition without `FOR SQLSTATE` gets SQLSTATE `'45000'`; a declared SQLSTATE "must not start with '00', '01', or 'XX'".
- `SIGNAL SQLSTATE '...'` raises `USER_RAISED_EXCEPTION` with that SQLSTATE.
- The SIGNAL page: "Databricks recommends using RESIGNAL to raise conditions from within a handler. RESIGNAL builds a diagnostic stack in the SQL Standard, while `SIGNAL` clears the stack."
- `ROW_COUNT` must be read "immediately after the DML statement": any other statement in between, or a `CALL`, clears it. Writes to non-Delta tables return `NULL`. (The page notes that "Databricks Runtime 18 is newer than Databricks Runtime 18.0, 18.1, and 18.2", because features now ship as dated updates to Runtime 18.)
- With `CONTINUE` handlers and cursors (both Runtime 18.1 and above), a `NOT FOUND` handler catches `CURSOR_NO_MORE_ROWS` (SQLSTATE `'02000'`) to end a `FETCH` loop. `FOR` covers most of what a cursor loop does, so this chapter does not go further into cursors (`DECLARE ... CURSOR FOR query`, `OPEN`, `FETCH`, `CLOSE`; Databricks Runtime 18.1 and above per the SQL scripting page).

In open-source Spark 4.2, `raise_error('message')` is the way to fail on purpose (test 8 above). It raises `USER_RAISED_EXCEPTION` with SQLSTATE `P0001`, which a `SQLEXCEPTION` handler catches. It also exists on Databricks, so it is a portable choice when you do not need a custom SQLSTATE.

### BEGIN ATOMIC: all or nothing

*Databricks only, not run here. Syntax from [BEGIN END compound statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/compound-stmt).*
```sql
BEGIN ATOMIC
  DELETE FROM shop.gold.daily_revenue WHERE order_date = DATE'2026-03-03';
  INSERT INTO shop.gold.daily_revenue
    SELECT to_date(order_ts), currency, count(*), sum(amount)
    FROM shop.silver.orders
    WHERE to_date(order_ts) = DATE'2026-03-03' AND coalesce(status, '') <> 'CANCELLED'
    GROUP BY ALL;
END;
```

`ATOMIC` "Applies to: Databricks SQL Databricks Runtime 17.0 and above" and is in **Public Preview**. "All statements within the block run as a single transactional unit: either all statements succeed together, or all changes are rolled back if any statement fails." With it, the delete and the insert commit together or not at all; the page says atomic blocks have "the same isolation, visibility, error handling, and limit semantics as explicit interactive transactions". The restrictions on the page matter in practice:

- No exception handlers inside an atomic block, no nested `BEGIN ATOMIC`, no atomic block inside a non-atomic block or inside a handler, and no label.
- Only DML (`INSERT`, `UPDATE`, `DELETE`, `MERGE`), `SELECT`, variable declarations and assignments, control flow such as `IF` and `SIGNAL`, and calls to atomic stored procedures. "DDL statements and other operations are not supported."
- "Multi-table transactions require Databricks Runtime 18.0 and above and catalog commits enabled on all tables. Single-table atomic transactions work in Databricks Runtime 17.0 and above."
- Variable assignments are not rolled back.

Open-source Spark 4.2 rejects `BEGIN ATOMIC` with a syntax error (`ex03_handlers.out`, test 9).

!!! tip "In the interview"
    **"How do you handle errors in a Databricks SQL script?"** Declare handlers at the top of a block: `DECLARE EXIT HANDLER FOR SQLEXCEPTION` (or for a specific error class or SQLSTATE, which wins over the generic one). In the handler, read the details with `GET DIAGNOSTICS CONDITION 1`, write a log row, and `RESIGNAL` so the job still fails and alerts. Put optional steps in their own nested block so an `EXIT` handler only leaves that step, and remember that without `BEGIN ATOMIC` earlier statements stay committed, so each step must be safe to rerun.

## 21.5 Dynamic SQL without SQL injection
*Level: intermediate.*

**The problem.** Some SQL is only known at run time: the currency a dashboard user picked, the table a job should audit, the date a backfill should reload. The quick way is to glue strings: `'... WHERE currency = ''' || input || ''''` in SQL, or an f-string in Python. That is how **SQL injection** happens: input that contains SQL syntax becomes part of the statement.

Databricks SQL has three tools that keep values and names out of the SQL text ([section 17.9](17-Databricks-SQL-vs-Standard.md) has the single-statement basics):

- **Parameter markers** (`:name`, `?`) for values. The Parameter markers page: "Using parameter markers protects your code from SQL injection attacks since it clearly separates provided values from the structure of the SQL statements."
- **`IDENTIFIER(...)`** for names of tables, columns, functions, schemas and catalogs: it "enables SQL-injection-safe parameterization of identifiers in SQL statements".
- **`EXECUTE IMMEDIATE sql_string [INTO vars] [USING args]`** for a whole statement chosen at run time, with its own markers bound by `USING`.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Top: string concatenation glues the input CAD' OR '1'='1 into the SQL text before parsing, so the parser sees an OR condition and all 8 orders match. Bottom: with a parameter marker the SQL text is parsed first and the input is bound afterwards as one string value, so no order matches. IDENTIFIER accepts only a valid name.">
<defs><marker id="a21-2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<text x="10" y="22" font-size="15" font-weight="bold" fill="currentColor">Concatenation: input becomes SQL text</text>
<rect x="10" y="34" width="190" height="56" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="20" y="56" font-size="13" fill="currentColor">'... currency = ''' ||</text>
<text x="20" y="78" font-size="13" fill="currentColor">input || ''''</text>
<line x1="200" y1="62" x2="232" y2="62" stroke="currentColor" stroke-width="1.5" marker-end="url(#a21-2)"/>
<rect x="234" y="34" width="250" height="56" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="244" y="56" font-size="13" fill="currentColor">parser reads: currency = 'CAD'</text>
<text x="244" y="78" font-size="13" font-weight="bold" fill="currentColor">OR '1'='1'</text>
<line x1="484" y1="62" x2="516" y2="62" stroke="currentColor" stroke-width="1.5" marker-end="url(#a21-2)"/>
<rect x="518" y="34" width="112" height="56" rx="6" fill="none" stroke="currentColor" stroke-width="1.5"/>
<text x="530" y="56" font-size="13" fill="currentColor">every row</text>
<text x="530" y="78" font-size="13" font-weight="bold" fill="currentColor">n = 8</text>
<text x="10" y="132" font-size="15" font-weight="bold" fill="currentColor">Parameter marker: parse first, bind the value after</text>
<rect x="10" y="144" width="190" height="56" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="20" y="166" font-size="13" fill="currentColor">'... currency = :cur'</text>
<text x="20" y="188" font-size="13" fill="currentColor">USING input AS cur</text>
<line x1="200" y1="172" x2="232" y2="172" stroke="currentColor" stroke-width="1.5" marker-end="url(#a21-2)"/>
<rect x="234" y="144" width="250" height="56" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
<text x="244" y="166" font-size="13" fill="currentColor">parsed: currency = :cur</text>
<text x="244" y="188" font-size="13" fill="currentColor">then :cur = one STRING</text>
<line x1="484" y1="172" x2="516" y2="172" stroke="currentColor" stroke-width="1.5" marker-end="url(#a21-2)"/>
<rect x="518" y="144" width="112" height="56" rx="6" fill="none" stroke="currentColor" stroke-width="1.5"/>
<text x="530" y="166" font-size="13" fill="currentColor">no match</text>
<text x="530" y="188" font-size="13" font-weight="bold" fill="currentColor">n = 0</text>
<text x="10" y="242" font-size="15" font-weight="bold" fill="currentColor">Names: IDENTIFIER(:tbl)</text>
<text x="10" y="266" font-size="13" fill="currentColor">The value must parse as a name (catalog.schema.table). 'silver.orders; DROP TABLE x'</text>
<text x="10" y="288" font-size="13" fill="currentColor">is rejected with a parse error instead of running a second statement.</text>
</svg>
<figcaption>Figure 21.2. Static SQL text with parameter markers versus SQL text built by concatenation. The input here is <code>CAD' OR '1'='1</code>; both counts are real outputs from section 21.5.</figcaption>
</figure>

!!! note "How these examples ran"
    As in section 17.9, the Delta Lake SQL extension in this local setup stops parameter markers from binding (`UNBOUND_SQL_PARAMETER`, also for `EXECUTE IMMEDIATE ... USING`). The examples in this section ran on a plain Spark 4.2 session with the same tables stored as Parquet (`ex04_dynamic_sql.py`). This is a quirk of the local test setup, not a Databricks behavior.

### Parameter markers inside a script

A whole script can use parameter markers; the caller binds them once. The SQL scripting page lists this as the way to pass values "from a notebook widget, Python, or another language to the SQL Script".

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```python
spark.sql("""BEGIN
  DECLARE n INT;
  SET n = (SELECT count(*) FROM silver.orders WHERE currency = :cur AND amount >= :min_amt);
  VALUES (:cur, n);
END""", args={"cur": "CAD", "min_amt": 100}).show()
```

Output:
```text
+----+----+
|col1|col2|
+----+----+
|CAD |2   |
+----+----+
```

The two CAD orders of at least 100 are 1003 (189.50) and 1005 (318.00).

### EXECUTE IMMEDIATE

*Syntax summary from [EXECUTE IMMEDIATE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-execute-immediate) (a grammar, not a runnable statement).*
```text
EXECUTE IMMEDIATE sql_string
        [ INTO var_name [, ...] ]
        [ USING { arg_expr [ AS ] [alias] } [, ...] ]
```

"Applies to: Databricks SQL Databricks Runtime 14.3 and above." The string must hold one well-formed statement, with markers that are "all positional (`?`) or all named (`:parm1`)". `INTO` puts a one-row result into variables. Two version notes from the page: "Prior to Databricks Runtime 17.3 `sql_string` must a literal or a variable. And you cannot nest `EXECUTE IMMEDIATE` statements", and before 17.3 each `USING` argument "must a literal or a variable" (the page's wording).

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```sql
EXECUTE IMMEDIATE 'SELECT count(*) AS n FROM silver.orders WHERE currency = ?' USING 'USD';

EXECUTE IMMEDIATE 'SELECT count(*) AS n FROM silver.orders WHERE currency = :c AND amount > :a'
  USING 'CAD' AS c, 100 AS a;

DECLARE VARIABLE n_orders BIGINT;
DECLARE VARIABLE revenue DECIMAL(12,2);
EXECUTE IMMEDIATE 'SELECT count(*), sum(amount) FROM silver.orders WHERE status = :s'
  INTO n_orders, revenue USING 'SHIPPED' AS s;
SELECT n_orders, revenue;
```

Output:
```text
+---+
|n  |
+---+
|4  |
+---+

+---+
|n  |
+---+
|2  |
+---+

+--------+-------+
|n_orders|revenue|
+--------+-------+
|4       |785.90 |
+--------+-------+
```

`INTO` follows the page's rules exactly: more than one row is an error, no rows sets the variables to `NULL`, and a statement that is not a query cannot use `INTO` (`INVALID_STATEMENT_FOR_EXECUTE_INTO`).

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```sql
EXECUTE IMMEDIATE 'SELECT order_id FROM silver.orders' INTO n_orders;
EXECUTE IMMEDIATE 'SELECT order_id FROM silver.orders WHERE order_id = 9999' INTO n_orders;
SELECT n_orders;
```

Output:
```text
ERROR: [ROW_SUBQUERY_TOO_MANY_ROWS] More than one row returned by a subquery used as a row. SQLSTATE: 21000

+--------+
|n_orders|
+--------+
|NULL    |
+--------+
```

### What SQL injection looks like

Here the "user input" is the classic `CAD' OR '1'='1`, stored in a variable. Glued into the text, it closes the quote and adds an `OR` that is always true:

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```sql
DECLARE VARIABLE user_input STRING DEFAULT 'CAD'' OR ''1''=''1';

-- WRONG: the input becomes SQL
EXECUTE IMMEDIATE
  'SELECT count(*) AS n FROM silver.orders WHERE currency = ''' || user_input || '''';

-- RIGHT: the input is bound as one value
EXECUTE IMMEDIATE 'SELECT count(*) AS n FROM silver.orders WHERE currency = :cur'
  USING user_input AS cur;
```

Output:
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

The concatenated version returned all 8 orders; the bound version compared `currency` with the whole string `CAD' OR '1'='1` and found none. With a `DELETE` instead of a `count(*)`, the first version would have deleted every row.

### Names: IDENTIFIER, never concatenation

A marker is a value, so it cannot be a table name. `IDENTIFIER` takes a constant string (a literal, a marker, a variable) and treats it as a name, so the string must parse as a name:

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```sql
DECLARE VARIABLE tbl STRING DEFAULT 'silver.orders';
SELECT count(*) AS n FROM IDENTIFIER(tbl);

SET VAR tbl = 'silver.orders; DROP TABLE silver.customers';
SELECT count(*) AS n FROM IDENTIFIER(tbl);
SELECT count(*) AS n FROM silver.customers;      -- still there
```

Output:
```text
+---+
|n  |
+---+
|8  |
+---+

ERROR: [PARSE_SYNTAX_ERROR] Syntax error at or near ';'. SQLSTATE: 42601

+---+
|n  |
+---+
|4  |
+---+
```

`IDENTIFIER` is the safe way to choose a table, but it does not decide *which* tables a caller may choose. If the name comes from a user, also check it against an allowed list, or rely on Unity Catalog privileges.

### A metadata loop: row counts for several tables

`FOR`, `EXECUTE IMMEDIATE` and `IDENTIFIER` together give a small audit that runs one set-based count per table:

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```sql
BEGIN
  DECLARE n BIGINT;
  DECLARE report STRING DEFAULT '';
  FOR t AS SELECT tbl FROM VALUES ('silver.customers'), ('silver.orders'), ('silver.order_items') AS v(tbl) DO
    EXECUTE IMMEDIATE 'SELECT count(*) FROM IDENTIFIER(:name)' INTO n USING t.tbl AS name;
    SET report = report || t.tbl || '=' || n || ' ';
  END FOR;
  VALUES (trim(report));
END
```

Output:
```text
+-------------------------------------------------------+
|col1                                                   |
+-------------------------------------------------------+
|silver.customers=4 silver.orders=8 silver.order_items=8|
+-------------------------------------------------------+
```

The `USING` argument here is a loop column, not a literal or variable. That ran on open-source Spark 4.2; on Databricks Runtime below 17.3 the page's rule ("`arg_expr` must a literal or a variable") suggests copying `t.tbl` into a local variable first. On Databricks you would typically read the list from `information_schema.tables` instead of a `VALUES` list.

`EXECUTE IMMEDIATE` also accepts the statement text from a variable, which is useful when a script picks one of several prepared statements:

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```sql
BEGIN
  DECLARE stmt STRING DEFAULT 'SELECT currency, count(*) AS n FROM silver.orders WHERE status = ? GROUP BY ALL ORDER BY ALL';
  EXECUTE IMMEDIATE stmt USING 'SHIPPED';
END
```

Output:
```text
+--------+---+
|currency|n  |
+--------+---+
|CAD     |2  |
|USD     |2  |
+--------+---+
```

### The same rules in PySpark

In Python, pass values with `args=` (markers) and names through `IDENTIFIER(:t)`, or skip SQL text altogether with the DataFrame API, where a value can never become syntax:

*Run here: Apache Spark 4.2 (plain session, see the note above).*
```python
from pyspark.sql import functions as F

cur, table_name = "CAD' OR '1'='1", "silver.orders"

spark.table(table_name).where(F.col("currency") == cur).count()          # 0
spark.table(table_name).where(F.col("currency") == "CAD").count()        # 4
spark.sql("SELECT count(*) AS n FROM IDENTIFIER(:t) WHERE currency = :c",
          args={"t": table_name, "c": "CAD"}).show()                      # n = 4

# WRONG: an f-string puts the input into the SQL text
spark.sql(f"SELECT count(*) AS n FROM {table_name} WHERE currency = '{cur}'").show()   # n = 8
```

The counts in the comments are the real outputs (`ex04_dynamic_sql.out`).

!!! tip "In the interview"
    **"How do you parameterize a query safely in Databricks?"** Values go in parameter markers (`:name` or `?`), bound by the caller: `spark.sql(..., args=...)`, a notebook or dashboard parameter, the Statement Execution API, or `EXECUTE IMMEDIATE ... USING`. Object names go through `IDENTIFIER(:name)`, which only accepts a valid name. I never build SQL with f-strings or `||` from input: the marker is parsed as a value after the statement's structure is fixed, so input like `CAD' OR '1'='1` matches nothing instead of everything. In PySpark the DataFrame API avoids SQL text entirely.

!!! warning "Concatenation is still sometimes needed, but never with raw input"
    The EXECUTE IMMEDIATE page's own last example builds a function name with `'SELECT ' || func || '(c1) ...'`. When a keyword or function name truly must vary, pick it from a fixed set inside your code (`CASE mode WHEN 'sum' THEN ...`), not from user input.

## 21.6 User-defined functions: SQL and Python
*Level: intermediate.*

**The problem.** "Net of 5% sales tax" is written as `amount / 1.05` in one dashboard, `amount * 0.95` in another (which is wrong), and with a different rounding in a third. A calculation used in many places should be defined once, named, documented and governed.

**The tool.** A **SQL user-defined function (SQL UDF)** is a named expression or query: `CREATE FUNCTION name(params) RETURNS type RETURN expression_or_query`. The CREATE FUNCTION page (Applies to: Databricks SQL, Databricks Runtime) covers SQL, Python, Scala and Java functions:

*Syntax summary from [CREATE FUNCTION (SQL, Python, Scala, and Java)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-sql-function) (a grammar, not a runnable statement).*
```text
CREATE [OR REPLACE] [TEMPORARY] FUNCTION [IF NOT EXISTS]
    function_name ( [ function_parameter [, ...] ] )
    { [ RETURNS data_type ] |
      RETURNS TABLE [ ( column_spec [, ...]) ] }
    [ characteristic [...] ]
    { AS dollar_quoted_string | HANDLER handler_name [ AS dollar_quoted_string ] | RETURN { expression | query } }

function_parameter
    parameter_name data_type [DEFAULT default_expression] [COMMENT parameter_comment]
```

On Databricks a permanent function lives in Unity Catalog (`shop.silver.net_amount`), and running it needs the `EXECUTE` privilege. `TEMPORARY` functions live in `system.session` for the current session only.

### Scalar SQL UDFs

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE FUNCTION silver.net_amount(gross DECIMAL(10,2), tax_rate DECIMAL(4,3) DEFAULT 0.05)
  RETURNS DECIMAL(10,2)
  COMMENT 'Gross amount without sales tax'
  RETURN CAST(gross / (1 + tax_rate) AS DECIMAL(10,2));

SELECT order_id, amount, silver.net_amount(amount) AS net_5pct,
       silver.net_amount(amount, tax_rate => 0.13) AS net_13pct
FROM silver.orders WHERE order_id IN (1001, 1002) ORDER BY order_id;
```

Output:
```text
+--------+------+--------+---------+
|order_id|amount|net_5pct|net_13pct|
+--------+------+--------+---------+
|1001    |59.90 |57.05   |53.01    |
|1002    |249.00|237.14  |220.35   |
+--------+------+--------+---------+
```

`DEFAULT` makes a parameter optional ("When you specify a default for one parameter, all following parameters must also have a default", and "`DEFAULT` is supported for `LANGUAGE SQL` only"). Named arguments (`tax_rate => 0.13`) work for SQL and Python UDFs from Databricks Runtime 14.1 ([section 17.9](17-Databricks-SQL-vs-Standard.md) has the rules). `DECIMAL` is used on purpose: section 17.9 shows a `FLOAT` rate turning 130 into 129.

A scalar UDF's body may also be a query, which makes it "read SQL data":

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE FUNCTION silver.customer_order_count(cid INT)
  RETURNS BIGINT
  RETURN SELECT count(*) FROM silver.orders o WHERE o.customer_id = cid;

SELECT customer_id, name, silver.customer_order_count(customer_id) AS n_orders
FROM silver.customers ORDER BY customer_id;
```

Output:
```text
+-----------+------------+--------+
|customer_id|name        |n_orders|
+-----------+------------+--------+
|1          |Ana Lopez   |3       |
|2          |Ben Okafor  |2       |
|3          |Chloe Martin|2       |
|4          |Dev Patel   |1       |
+-----------+------------+--------+
```

This is convenient, but it is a correlated subquery per row in disguise; a `JOIN ... GROUP BY` says the same thing more plainly and gives the optimizer the full picture.

### What a SQL UDF body may not contain

From the CREATE FUNCTION page: the `RETURN` expression of a scalar function "cannot contain" aggregate functions, window functions, ranking functions, or "row producing functions such as explode". And from DECLARE VARIABLE: session variables cannot be referenced in "the body of a persisted SQL UDF". Both errors happen at `CREATE` time:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE FUNCTION silver.bad_total(x DECIMAL(10,2)) RETURNS DECIMAL(20,2) RETURN sum(x);

DECLARE VARIABLE vat DECIMAL(4,3) DEFAULT 0.05;
CREATE OR REPLACE FUNCTION silver.bad_net(x DECIMAL(10,2)) RETURNS DECIMAL(10,2) RETURN x / (1 + vat);
CREATE OR REPLACE TEMPORARY FUNCTION net_session(x DECIMAL(10,2)) RETURNS DECIMAL(10,2) RETURN x / (1 + vat);
SELECT net_session(105.00) AS net;
```

Output:
```text
ERROR: [USER_DEFINED_FUNCTIONS.CANNOT_CONTAIN_COMPLEX_FUNCTIONS] User defined function is invalid: SQL scalar function cannot contain aggregate/window/generate functions: sum(x) SQLSTATE: 42601

ERROR: [INVALID_TEMP_OBJ_REFERENCE] Cannot create the persistent object `silver`.`bad_net` of the type FUNCTION because it references to the temporary object `vat` of the type VARIABLE. ...

+------+
|net   |
+------+
|100.00|
+------+
```

A temporary function may use a session variable, because both die with the session. A persistent function may not: it would break for every other session. Pass the value as a parameter instead.

### SQL table functions

`RETURNS TABLE (...)` makes a **table function**, called in `FROM`. It is a parameterized view: one definition, a different filter per call.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE FUNCTION silver.orders_of(cid INT, only_status STRING DEFAULT NULL)
  RETURNS TABLE (order_id INT, order_ts TIMESTAMP, status STRING, amount DECIMAL(10,2))
  RETURN SELECT order_id, order_ts, status, amount
         FROM silver.orders
         WHERE customer_id = orders_of.cid
           AND (orders_of.only_status IS NULL OR status = orders_of.only_status);

SELECT * FROM silver.orders_of(1) ORDER BY order_id;

SELECT c.name, o.order_id, o.amount
FROM silver.customers c, LATERAL silver.orders_of(c.customer_id, 'SHIPPED') o
ORDER BY c.name, o.order_id;
```

Output:
```text
+--------+-------------------+-------+------+
|order_id|order_ts           |status |amount|
+--------+-------------------+-------+------+
|1001    |2026-03-01 10:15:00|SHIPPED|59.90 |
|1003    |2026-03-02 09:40:00|PLACED |189.50|
|1008    |2026-03-04 19:10:00|NULL   |78.00 |
+--------+-------------------+-------+------+

+------------+--------+------+
|name        |order_id|amount|
+------------+--------+------+
|Ana Lopez   |1001    |59.90 |
|Ben Okafor  |1002    |249.00|
|Chloe Martin|1007    |159.00|
|Dev Patel   |1005    |318.00|
+------------+--------+------+
```

Inside the body, parameters are qualified with the function name (`orders_of.cid`). The page allows the unqualified name too, but qualifying avoids a clash with a column of the same name, which is a real risk when a parameter is called `status` or `customer_id`. `LATERAL` calls the function once per row of the table on its left.

`DESCRIBE FUNCTION [EXTENDED]` shows the signature and, with `EXTENDED`, the body, `Deterministic` and `Data Access` (`READS SQL DATA` for `orders_of`, see `ex05_udfs.out`).

### Why a SQL UDF is usually faster than a Python UDF

A SQL UDF is an expression the optimizer can see. Locally, the plan for `silver.net_amount(amount)` contains no function call at all, only the body with the default filled in:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
EXPLAIN SELECT silver.net_amount(amount) AS net FROM silver.orders;
```

Output (the `Project` line of the physical plan):
```text
*(1) Project [cast((amount#2788 / 1.050) as decimal(10,2)) AS net#2779]
```

A session-scoped PySpark UDF with the same logic gives the same numbers, but the plan has a separate Python step:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
from decimal import Decimal, ROUND_HALF_UP
from pyspark.sql.functions import udf
from pyspark.sql.types import DecimalType

@udf(returnType=DecimalType(10, 2), useArrow=False)   # classic pickled UDF (see the Arrow note below)
def net_amount_py(gross):
    if gross is None:
        return None
    return (gross / Decimal("1.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

spark.udf.register("net_amount_py", net_amount_py)
spark.sql("""SELECT order_id, amount, net_amount_py(amount) AS net_py, silver.net_amount(amount) AS net_sql
             FROM silver.orders WHERE order_id <= 1003 ORDER BY order_id""").show()
plan = spark.sql("EXPLAIN SELECT net_amount_py(amount) AS net FROM silver.orders").collect()[0][0]
print("\n".join(l.strip() for l in plan.split("\n") if "EvalPython" in l or "Project" in l))
```

Output (the result, then the two relevant lines of the physical plan):
```text
+--------+------+------+-------+
|order_id|amount|net_py|net_sql|
+--------+------+------+-------+
|1001    |59.90 |57.05 |57.05  |
|1002    |249.00|237.14|237.14 |
|1003    |189.50|180.48|180.48 |
+--------+------+------+-------+

*(2) Project [pythonUDF0#3789 AS net#3698]
+- BatchEvalPython [net_amount_py(amount#3707)#3709], [pythonUDF0#3789]
```

`BatchEvalPython` means rows are serialized from the JVM to a Python worker process and back, and the optimizer cannot look inside the function. Without `useArrow=False`, this local Spark 4.2 picks the Arrow path: the same function registered with the defaults shows `+- ArrowEvalPython [net_amount_arrow(amount#3799)#3801], [pythonUDF0#3881], 101` in its plan, and running it failed in the Python worker (`ex05_udfs.out`; the worker's traceback ends in `ModuleNotFoundError: No module named 'pyarrow'`). That was a slip in the test setup, not a Spark limit: the script did not set `PYSPARK_PYTHON`, so Spark started its Python workers with the system `python3`, which has no pyarrow, while the virtual environment that ran the driver has pyarrow 26.0.1. With the workers pointed at that environment (as in [chapter 3](03-Apache-Spark.md), which timed an Arrow UDF on this engine), the same Arrow UDF ran and returned 57.05 and 237.14 for orders 1001 and 1002. Arrow moves rows in columnar batches, which is cheaper, but the function is still opaque to the optimizer.

The Databricks guidance agrees, in different words. The row filter and column mask page: "Prefer SQL to Python UDFs. Python UDFs are less performant than SQL and offer fewer optimization opportunities." The UDF overview: "Built-in Apache Spark functions are optimized for distributed processing and offer better performance at scale." So the order of preference is: built-in functions and expressions (including higher-order functions, [section 18.8](18-Semi-Structured-Data.md)), then a SQL UDF, then a Python UDF for logic SQL cannot express.

The PySpark DataFrame equivalent of the net-amount column, and the way to call a catalog SQL UDF from PySpark:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
from pyspark.sql import functions as F

(spark.table("silver.orders").where(F.col("order_id") <= 1003)
 .select("order_id", "amount",
         (F.col("amount") / F.lit(1.05)).cast("decimal(10,2)").alias("net"))
 .orderBy("order_id").show())

(spark.table("silver.orders").where("order_id <= 1003")
 .select("order_id", F.expr("silver.net_amount(amount)").alias("net"))
 .orderBy("order_id").show())
```

Output (both give the same `net` column):
```text
+--------+------+------+
|order_id|amount|   net|
+--------+------+------+
|    1001| 59.90| 57.05|
|    1002|249.00|237.14|
|    1003|189.50|180.48|
+--------+------+------+
```

The UDF page uses the same `expr("catalog.schema.function(...)")` pattern for Unity Catalog functions in PySpark.

### Python UDFs in Unity Catalog

Some logic is awkward in SQL: a checksum algorithm, a library call, a custom tokenizer. `CREATE FUNCTION ... LANGUAGE PYTHON` stores Python code as a Unity Catalog function that SQL can call like any other. The CREATE FUNCTION page: "Applies to: Databricks SQL Databricks Runtime 13.3 LTS and above ... Python UDFs require Unity Catalog on serverless or pro SQL warehouses, or a Unity Catalog-enabled compute resource." Open-source Spark 4.2 does not parse it (`[PARSE_SYNTAX_ERROR] Syntax error at or near 'AS': missing 'RETURN'` in `ex07_views.out`).

*Databricks only, not run here. Syntax from [CREATE FUNCTION (SQL, Python, Scala, and Java)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-sql-function) and [SQL and Python user-defined functions (UDFs) in Unity Catalog](https://docs.databricks.com/aws/en/udf/unity-catalog).*
```sql
CREATE OR REPLACE FUNCTION shop.silver.mask_email(email STRING)
  RETURNS STRING
  LANGUAGE PYTHON
  DETERMINISTIC
  COMMENT 'Keeps the first and last letter of the user name and the domain'
AS $$
  if email is None or '@' not in email:
      return None
  user, domain = email.split('@', 1)
  if len(user) <= 2:
      return '*' * len(user) + '@' + domain
  return user[0] + '*' * (len(user) - 2) + user[-1] + '@' + domain
$$;

SELECT customer_id, shop.silver.mask_email(email) AS email FROM shop.silver.customers;

GRANT EXECUTE ON FUNCTION shop.silver.mask_email TO `support-team`;
```

What the pages say about Python UDFs in Unity Catalog:

- The body goes between `$$ ... $$` (or `$tag$ ... $tag$`) and ends with `return`. Parameters arrive as Python values of the mapped type, and "return values should match the declared `data_type`".
- `DEFAULT` values for parameters are "supported for `LANGUAGE SQL` only".
- If you do not say otherwise, "For Python, Scala, and Java functions, the function is `NOT DETERMINISTIC`." Add `DETERMINISTIC` when the same input always gives the same output; the UDF page says this "allows query optimizations to improve performance".
- Without an `ENVIRONMENT` clause the code can use the standard library and a fixed list of packages printed on the CREATE FUNCTION page. Extra PyPI packages or wheels go in `ENVIRONMENT (dependencies = '[...]', environment_version = '...')` ("Applies to: Databricks SQL Databricks Runtime 16.2 and above"; on classic compute, an `environment_version` other than `'None'` needs Databricks Runtime 18.2 or above).
- To create one you need `USE CATALOG`, `USE SCHEMA` and `CREATE FUNCTION` on the schema; to run it, `EXECUTE` on the function.
- "If a view includes a Unity Catalog Python UDF, it fails on classic SQL warehouses."
- The UDF page lists more variants with their own version lines: batch Python UDFs (`PARAMETER STYLE PANDAS` with a `HANDLER`, Databricks Runtime 16.3 and above), Python UDTFs registered in Unity Catalog, and Scala or Java UDFs from a JAR (Databricks Runtime 18.2 and above).

### Unity Catalog UDF or session-scoped UDF?

The "What are user-defined functions (UDFs)?" page separates two families:

| | Unity Catalog governed UDFs | Session-scoped UDFs |
| --- | --- | --- |
| How you create one | `CREATE FUNCTION catalog.schema.name ...` (SQL, Python, Scala, Java) | `CREATE TEMPORARY FUNCTION`, or PySpark `@udf` / `spark.udf.register` |
| Lives | "Persisted in Unity Catalog and reusable across sessions" | "Exist only for the current session" |
| Governance | "Governed by Unity Catalog permissions and discoverable in Catalog Explorer" | "Scoped to the current SparkSession. Not governed or shared." |
| Best for | "Sharing functions securely across teams, notebooks, jobs, and pro and serverless SQL warehouses" | "Quick, iterative development within a single notebook or job" |

The same page's advice on when to write a UDF at all: "Use UDFs for logic that is difficult to express with built-in Apache Spark functions. Built-in Apache Spark functions are optimized for distributed processing and offer better performance at scale."

!!! tip "In the interview"
    **"When would you write a UDF, and which kind?"** First try built-in functions and expressions, including higher-order functions; they are optimized and need no maintenance. If the logic is reused, wrap it in a SQL UDF in Unity Catalog: it is governed with `EXECUTE`, and the optimizer sees its body as a normal expression. Use a Python UDF (in Unity Catalog for sharing, or a session-scoped PySpark UDF for one notebook) only for logic SQL cannot express, and mark it `DETERMINISTIC` when it is.

## 21.7 Stored procedures: CREATE PROCEDURE and CALL
*Level: intermediate.*

**The problem.** The daily-load script from section 21.2 works, but it lives in a notebook cell. Another team wants to run it for their date, a job wants to call it, and you want to grant "may run the load" without granting "may write to gold directly". A script pasted into many places drifts apart.

**The tool.** A **stored procedure** is a SQL script saved under a name in Unity Catalog, with parameters. The SQL scripting page: "Using the CREATE PROCEDURE statement you can persist a SQL Script in Unity Catalog. You can then GRANT the access to the procedure to other principals. Those principals can then use the CALL statement to invoke the procedure." (SQL Stored Procedures: Applies to Databricks SQL, Databricks Runtime 17.0 and above.) `CREATE PROCEDURE` is marked "Unity Catalog only", and open-source Spark 4.2 does not have it (`CREATE PROCEDURE` is a syntax error here, see `ex07_views.out`), so everything in this section is Databricks only.

*Databricks only, not run here. Syntax from [CREATE PROCEDURE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-procedure).*
```sql
CREATE [OR REPLACE] PROCEDURE [IF NOT EXISTS]
    procedure_name ( [ procedure_parameter [, ...] ] )
    [ characteristic [...] ]
    AS compound_statement

procedure_parameter
    [ IN | OUT | INOUT ] parameter_name data_type
    [ DEFAULT default_expression ] [ COMMENT parameter_comment ]

characteristic
  { LANGUAGE SQL |
    SQL SECURITY { INVOKER | DEFINER } |
    NOT DETERMINISTIC |
    COMMENT procedure_comment |
    DEFAULT COLLATION default_collation_name |
    MODIFIES SQL DATA }
```

Points from the CREATE PROCEDURE and CALL pages:

- "`SQL SECURITY INVOKER` or `SQL SECURITY DEFINER`, and `LANGUAGE SQL` are required." Leaving them out is a common first error.
- Parameters are `IN` (the default), `OUT` (starts as `NULL`, returned when the procedure ends without an unhandled error) or `INOUT`. `DEFAULT` is allowed only on `IN` parameters, and once one parameter has a default, all later ones need one.
- For `OUT` and `INOUT` parameters, the `CALL` argument "must be a session variable, or local variable". "If the procedure fails the argument values of the `OUT` and `INOUT` parameters remain unchanged."
- Arguments must match the parameter type; the CALL page's example is to write `DATE'2015-01-01'`, not `'2015-01-01'`, for a `DATE` parameter.
- Calls can be named (`CALL p(y => 10, x => 5)`) and "Procedure calls can be nested up to 64 levels."
- The body is checked for syntax when the procedure is created, but "is not validated for semantic correctness until the procedure is invoked". A typo in a table name shows up at the first `CALL`, not at `CREATE`.
- "The last executed query is the result set of a procedure."

Here is the daily load as a procedure, written for Unity Catalog names. It returns the number of rows written through an `OUT` parameter:

*Databricks only, not run here. Syntax from [CREATE PROCEDURE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-procedure) and [CALL](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-call).*
```sql
CREATE OR REPLACE PROCEDURE shop.gold.load_daily_revenue(
    IN  run_date DATE COMMENT 'day to (re)load',
    OUT rows_written BIGINT)
  LANGUAGE SQL
  SQL SECURITY INVOKER
  COMMENT 'Idempotent load of one day into shop.gold.daily_revenue'
AS BEGIN
  DELETE FROM shop.gold.daily_revenue WHERE order_date = run_date;
  INSERT INTO shop.gold.daily_revenue
    SELECT to_date(order_ts), currency, count(*), sum(amount)
    FROM shop.silver.orders
    WHERE to_date(order_ts) = run_date AND coalesce(status, '') <> 'CANCELLED'
    GROUP BY ALL;
  SET rows_written = (SELECT count(*) FROM shop.gold.daily_revenue WHERE order_date = run_date);
END;

DECLARE VARIABLE n BIGINT;
CALL shop.gold.load_daily_revenue(DATE'2026-03-03', n);
SELECT n;
```

On Databricks Runtime 18 LTS and above you could read the inserted row count directly with `GET DIAGNOSTICS rc = ROW_COUNT` right after the `INSERT` (section 21.4) instead of counting again.

Related statements, all "Databricks SQL, Databricks Runtime 17.0 and above": `DESCRIBE PROCEDURE [EXTENDED] name`, `DROP PROCEDURE [IF EXISTS] name`. A procedure and a function share one namespace: "The procedure name must be unique for all routines (procedures and functions) in the schema."

### Who runs the body: SQL SECURITY

- **`SQL SECURITY INVOKER`**: "any SQL statements in the body of the procedure run under the authority of the user invoking the procedure", and names resolve with the caller's current catalog, schema and path. The caller needs privileges on everything the body touches.
- **`SQL SECURITY DEFINER`** (its own label on the page: "Applies to: Databricks SQL"): the body runs "under the authority of the owner (definer) of the procedure". "The invoker only requires the `EXECUTE` privilege on the procedure." The catalog, schema, path and SQL configurations (such as `ANSI_MODE` and the time zone) are captured when the procedure is created. `session_user()` still returns the caller, which is what audit logging wants.

`DEFINER` is how you give a team "run the gold load" without "write to gold". Creating a procedure needs `USE CATALOG`, `USE SCHEMA` and `CREATE FUNCTION` on the schema; "Creating a procedure does not require privileges on objects referenced in its body."

!!! tip "In the interview"
    **"Function or procedure?"** A function (UDF) computes and returns a value or a table and is used inside a query (`SELECT net_amount(amount)`, `FROM orders_of(1)`). A procedure is a saved script you run on its own with `CALL`: it can run DML and DDL, loop, handle errors, and return values through `OUT` parameters. If it changes data, it is a procedure; if it is part of a query, it is a function. Procedures need Databricks Runtime 17.0 or a SQL warehouse, and Unity Catalog.

## 21.8 Recursive CTEs: series and hierarchies
*Level: intermediate.*

**The problem.** Two classic tasks do not fit a normal query. A daily report must show *every* day, including days without orders, but you cannot `GROUP BY` days that have no rows. And a category tree (Camping under Outdoor gear, Shelter under Camping) has an unknown depth, so no fixed number of self-joins walks it.

**The tool.** A **recursive CTE** (`WITH RECURSIVE`) is a CTE that refers to itself. It has a **base case** (the seed rows) and a **step** that produces new rows from the previous step's rows, joined with `UNION ALL`. Spark repeats the step until it returns no rows.

*Syntax summary from [Common table expression (CTE)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-cte) (a grammar, not a runnable statement).*
```text
WITH [ RECURSIVE ] common_table_expression [, ...]

common_table_expression
  view_identifier [ ( column_identifier [, ...] ) ] [ recursion_limit ] [ AS ] ( query | recursive_query )

recursion_limit
  MAX RECURSION LEVEL maxLevel

recursive_query
  base_case_query UNION ALL step_case_query
```

`RECURSIVE` and `MAX RECURSION LEVEL`: "Applies to: Databricks SQL Databricks Runtime 17.0 and later." Open-source Spark 4.2 runs them.

### A date spine

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
WITH RECURSIVE days(d) AS (
  SELECT DATE'2026-02-28'                                    -- base case
  UNION ALL
  SELECT d + INTERVAL 1 DAY FROM days WHERE d < DATE'2026-03-05'   -- step
)
SELECT days.d AS order_date,
       count(o.order_id) AS orders,
       coalesce(sum(o.amount), 0) AS revenue
FROM days LEFT JOIN silver.orders o ON to_date(o.order_ts) = days.d
GROUP BY days.d ORDER BY days.d;
```

Output:
```text
+----------+------+-------+
|order_date|orders|revenue|
+----------+------+-------+
|2026-02-28|0     |0.00   |
|2026-03-01|2     |308.90 |
|2026-03-02|2     |228.50 |
|2026-03-03|2     |347.95 |
|2026-03-04|2     |237.00 |
|2026-03-05|0     |0.00   |
+----------+------+-------+
```

The two empty days appear with 0 because the spine is on the left of the `LEFT JOIN` (this counts all orders, including the cancelled one). For a plain series, though, recursion is not needed: `SELECT explode(sequence(DATE'2026-02-28', DATE'2026-03-05', INTERVAL 1 DAY)) AS d` returns the same six dates in one step (`ex06_recursive_cte.out`). Interviewers like to hear both.

### Walking a hierarchy

The shop's categories form a tree. The example builds it as a temporary view of `(category, parent)` pairs:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE TEMP VIEW category_tree(category, parent) AS VALUES
  ('Outdoor gear', NULL),
  ('Camping', 'Outdoor gear'), ('Hiking', 'Outdoor gear'), ('Apparel', 'Outdoor gear'),
  ('Shelter', 'Camping'), ('Sleep', 'Camping'), ('Lighting', 'Hiking');

WITH RECURSIVE tree(category, path, depth) AS (
  SELECT category, category, 0 FROM category_tree WHERE parent IS NULL
  UNION ALL
  SELECT c.category, t.path || ' > ' || c.category, t.depth + 1
  FROM category_tree c JOIN tree t ON c.parent = t.category
)
SELECT * FROM tree ORDER BY path;
```

Output:
```text
+------------+--------------------------------+-----+
|category    |path                            |depth|
+------------+--------------------------------+-----+
|Outdoor gear|Outdoor gear                    |0    |
|Apparel     |Outdoor gear > Apparel          |1    |
|Camping     |Outdoor gear > Camping          |1    |
|Shelter     |Outdoor gear > Camping > Shelter|2    |
|Sleep       |Outdoor gear > Camping > Sleep  |2    |
|Hiking      |Outdoor gear > Hiking           |1    |
|Lighting    |Outdoor gear > Hiking > Lighting|2    |
+------------+--------------------------------+-----+
```

Each pass of the step adds one level: pass 1 finds the children of the root, pass 2 their children, and pass 3 finds nothing, which ends the recursion. Starting from another node gives "everything under Camping", which can then be joined to products and sales (`ex06_recursive_cte.out`, test 3: Camping lines total 438.50).

### Limits and common mistakes

From the CTE page:

- `MAX RECURSION LEVEL`: "The default value is 100." Exceeding it raises `RECURSION_LEVEL_LIMIT_EXCEEDED`.
- "The total size of the result set is limited to 1,000,000 rows. This limit can be overridden if the `SELECT` statement driving the recursive CTE includes a `LIMIT` clause", and from Databricks Runtime 17.2 "`LIMIT ALL` suspends the limit completely."
- Recursive CTEs "are not supported for `UPDATE`, `DELETE`, and `MERGE` statements", and random number generators in the step "can generate the same random number in each iteration".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
-- no stop condition
WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n)
SELECT max(i) FROM n;

-- a lower limit
WITH RECURSIVE n(i) MAX RECURSION LEVEL 3 AS (
  SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 10)
SELECT * FROM n;

-- an outer LIMIT stops an endless recursion early
WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n)
SELECT * FROM n LIMIT 3;

-- UNION instead of UNION ALL
WITH RECURSIVE n(i) AS (SELECT 1 UNION SELECT i + 1 FROM n WHERE i < 3)
SELECT * FROM n;

-- RECURSIVE keyword forgotten
WITH n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 3)
SELECT * FROM n;
```

Output:
```text
ERROR: [RECURSION_LEVEL_LIMIT_EXCEEDED] Recursion level limit 100 reached but query has not exhausted, try increasing it like 'WITH RECURSIVE t(col) MAX RECURSION LEVEL 200'. SQLSTATE: 42836

ERROR: [RECURSION_LEVEL_LIMIT_EXCEEDED] Recursion level limit 3 reached but query has not exhausted, try increasing it like 'WITH RECURSIVE t(col) MAX RECURSION LEVEL 200'. SQLSTATE: 42836

+---+
|i  |
+---+
|1  |
|2  |
|3  |
+---+

ERROR: [UNION_NOT_SUPPORTED_IN_RECURSIVE_CTE] The UNION operator is not yet supported within recursive common table expressions (WITH clauses that refer to themselves, directly or indirectly). Please use UNION ALL instead. SQLSTATE: 42836; line 1 pos 0

ERROR: [TABLE_OR_VIEW_NOT_FOUND] The table or view `n` cannot be found. Verify the spelling and correctness of the schema and catalog.
```

Because only `UNION ALL` is allowed, a graph with cycles (A to B to A) recurses forever unless you stop it yourself: keep the visited path in an array and add `NOT array_contains(path, next_node)` to the step, as the CTE page's route example does.

!!! tip "In the interview"
    **"How do you get every day in a report, including days with no sales?"** Build a date spine and `LEFT JOIN` the facts to it. In Databricks the short way is `explode(sequence(start, end, INTERVAL 1 DAY))`; a recursive CTE also works (Databricks Runtime 17.0 and above). For hierarchies of unknown depth (categories, org charts, bills of materials) a recursive CTE is the tool: a base case, a step joined with `UNION ALL`, and a stop condition, with a default limit of 100 recursion levels.

## 21.9 Views, dynamic views, row filters and column masks
*Level: expert.*

**The problem.** Analysts should query "revenue per customer" without rewriting the join, and support staff should not see full e-mail addresses or customers outside Canada. The first need is about reuse, the second about access control. Views solve the first and can solve the second; Unity Catalog row filters and column masks solve the second more firmly.

### Views

The "What is a view?" page: "A view is a read-only object that is the result of a query over one or more tables and views in a Unity Catalog metastore." "Creating a view does not process or write any data. Only the query text is registered to the metastore." Each query of the view runs that text again. (Materialized views, which do store results, are in [chapter 13](13-Declarative-Pipelines.md); metric views define reusable measures in YAML and are not covered here.)

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE VIEW gold.v_customer_revenue AS
SELECT c.customer_id, c.name, c.country, count(o.order_id) AS orders, sum(o.amount) AS revenue
FROM silver.customers c JOIN silver.orders o USING (customer_id)
WHERE o.status = 'SHIPPED'
GROUP BY ALL;

SELECT * FROM gold.v_customer_revenue ORDER BY customer_id;
```

Output:
```text
+-----------+------------+-------+------+-------+
|customer_id|name        |country|orders|revenue|
+-----------+------------+-------+------+-------+
|1          |Ana Lopez   |CA     |1     |59.90  |
|2          |Ben Okafor  |US     |1     |249.00 |
|3          |Chloe Martin|US     |1     |159.00 |
|4          |Dev Patel   |CA     |1     |318.00 |
+-----------+------------+-------+------+-------+
```

Facts about views from the CREATE VIEW and "What is a view?" pages:

- **Temporary views** "are visible only to the session that created them and are dropped when the session ends". Their scope depends on where you are: "In notebooks and jobs, temporary views are scoped to the notebook or script level", while "In Databricks SQL, temporary views are scoped to the query level. Multiple statements within the same query can use the temp view, but it cannot be referenced in other queries, even within the same dashboard."
- **Global temporary views** are "a legacy Databricks feature"; "Databricks recommends against using global temp views."
- **`CREATE OR REPLACE VIEW`** on a non-Unity-Catalog-managed view "does not preserve privileges granted on the original view" and is like a drop and create; "Use ALTER VIEW to change a view in place without dropping its privileges." For Unity Catalog managed views, Databricks Runtime 18.3 added `COPY *` / `NOCOPY *` to choose; from Runtime 19 the metadata is kept by default.
- **Session variables** cannot be used in "the body of a persisted view" (DECLARE VARIABLE page), and before Databricks Runtime 18.0 parameter markers could not appear in a view either (Parameter markers page). Locally, a persistent view that uses a session variable fails with `INVALID_TEMP_OBJ_REFERENCE`, and a temporary view with the same query works (`ex07_views.out`, test 2).
- **Permissions**: on SQL warehouses and standard compute, Unity Catalog "checks the view owner's permissions on the underlying data". A reader needs `SELECT` on the view (plus `USE CATALOG` and `USE SCHEMA`), not on its tables. That is what makes a view usable as a security layer.

### Schema binding

What happens to `SELECT *` views when the base table gets a new column? The `WITH SCHEMA` clause ("Applies to: Databricks Runtime 15.3 and above") decides. The default is `SCHEMA COMPENSATION`, under which extra columns from a star "are ignored"; `SCHEMA EVOLUTION` adopts "added and dropped columns if the view does not include an explicit `column_list`".

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE VIEW gold.v_products_default AS SELECT * FROM silver.products;
CREATE OR REPLACE VIEW gold.v_products_evolve WITH SCHEMA EVOLUTION AS SELECT * FROM silver.products;
ALTER TABLE silver.products ADD COLUMN weight_kg DECIMAL(6,2);

SELECT * FROM gold.v_products_default WHERE product_id = 1;
SELECT * FROM gold.v_products_evolve  WHERE product_id = 1;
```

Output:
```text
+----------+-------------+--------+------+
|product_id|name         |category|price |
+----------+-------------+--------+------+
|1         |Trail Tent 2P|Camping |249.00|
+----------+-------------+--------+------+

+----------+-------------+--------+------+---------+
|product_id|name         |category|price |weight_kg|
+----------+-------------+--------+------+---------+
|1         |Trail Tent 2P|Camping |249.00|NULL     |
+----------+-------------+--------+------+---------+
```

### Dynamic views

A **dynamic view** is a view whose result depends on who runs it. The "Create a dynamic view" page lists the functions: `session_user()` (the current user's e-mail), `is_account_group_member()` ("Recommended for use in dynamic views against Unity Catalog data") and `is_member()` (workspace-level groups, "provided for compatibility with the existing Hive metastore. Avoid using it with views against Unity Catalog data"). It also says: "Databricks recommends that you not grant users the ability to read the tables and views referenced in the view."

The group functions do not exist in open-source Spark (`is_account_group_member` gives `UNRESOLVED_ROUTINE` locally), so the local run shows the same shape with `current_user()`, which returned `root` here:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
CREATE OR REPLACE VIEW gold.v_customers_masked AS
SELECT customer_id, name,
       CASE WHEN current_user() = 'data_steward' THEN email
            ELSE regexp_replace(email, '^[^@]+', '***') END AS email,
       country
FROM silver.customers
WHERE current_user() = 'data_steward' OR country = 'CA';

SELECT * FROM gold.v_customers_masked ORDER BY customer_id;
```

Output:
```text
+-----------+---------+---------------+-------+
|customer_id|name     |email          |country|
+-----------+---------+---------------+-------+
|1          |Ana Lopez|***@example.com|CA     |
|4          |Dev Patel|***@example.com|CA     |
+-----------+---------+---------------+-------+
```

On Databricks the same view uses group membership, the pattern on the dynamic views page:

*Databricks only, not run here. Syntax from [Create a dynamic view](https://docs.databricks.com/aws/en/views/dynamic).*
```sql
CREATE OR REPLACE VIEW shop.gold.v_customers_masked AS
SELECT customer_id, name,
       CASE WHEN is_account_group_member('support-leads') THEN email
            ELSE regexp_replace(email, '^[^@]+', '***') END AS email,
       country
FROM shop.silver.customers
WHERE is_account_group_member('finance') OR country = 'CA';
```

Reading a dynamic view needs a SQL warehouse, standard access mode, or dedicated access mode on Databricks Runtime 15.4 LTS or above ("You cannot read dynamic views using dedicated compute on Databricks Runtime 15.3 or below").

### Row filters and column masks

A dynamic view protects data only if users cannot query the base table, and every new consumer needs the view. A **row filter** and a **column mask** move the rule onto the table itself, so it applies to every query on that table. The overview page: "Row filters and column masks are Unity Catalog access controls that restrict the rows and column values a user can see at query time."

- A **row filter** is a SQL UDF returning `BOOLEAN`, attached with `ALTER TABLE ... SET ROW FILTER f ON (columns)`. "If the function returns `FALSE` or `NULL` the row is filtered out." Each table has one row filter.
- A **column mask** is a SQL UDF whose first parameter is the column's value, attached with `ALTER TABLE ... ALTER COLUMN c SET MASK f [USING COLUMNS (...)]`. "Each column can have one mask."

Both clauses: "Applies to: Databricks SQL Databricks Runtime 12.2 LTS and above Unity Catalog only". Open-source Spark 4.2 rejects them with a syntax error (`ex07_views.out`, test 5).

*Databricks only, not run here. Syntax from [Manually apply row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/manually-apply), [`ROW FILTER` clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-row-filter) and [Column `mask` clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-column-mask).*
```sql
-- Row filter: the finance group sees every customer, everyone else only Canadian ones
CREATE OR REPLACE FUNCTION shop.silver.ca_or_finance(country STRING)
  RETURN is_account_group_member('finance') OR country = 'CA';

ALTER TABLE shop.silver.customers SET ROW FILTER shop.silver.ca_or_finance ON (country);

-- Column mask: only the support-leads group sees full e-mail addresses
CREATE OR REPLACE FUNCTION shop.silver.email_mask(email STRING)
  RETURN CASE WHEN is_account_group_member('support-leads') THEN email
              ELSE regexp_replace(email, '^[^@]+', '***') END;

ALTER TABLE shop.silver.customers ALTER COLUMN email SET MASK shop.silver.email_mask;

-- Remove them (drop the filter BEFORE dropping its function)
ALTER TABLE shop.silver.customers DROP ROW FILTER;
ALTER TABLE shop.silver.customers ALTER COLUMN email DROP MASK;
```

Rules and traps from the pages:

- **Who can attach them**: `EXECUTE` on the function, `USE SCHEMA` and `USE CATALOG`; on an existing table you must be the owner or have both `MANAGE` and `SELECT` on it.
- **Only SQL UDFs**: "A SQL UDF that is registered in Unity Catalog. To use Python or Scala logic, first create a Python or Scala UDF, then create a SQL UDF that calls it."
- **Drop order**: "You must perform the `ALTER TABLE ... DROP ROW FILTER` command before you drop the function. If you don't, the table will be in an inaccessible state."
- **Type mismatch trap**: column values are implicitly cast to the UDF's parameter types. "With ANSI mode disabled (`spark.sql.ansi.enabled = false`), uncastable values are silently converted to `NULL`", which "can produce incorrect results, such as a row filter that returns all rows instead of filtering them". Declare parameters with the column's exact type.
- **Masks run first**: "The mask is applied as soon as each row is fetched from the data source. Any expressions, predicates, or ordering are applied after the masking." A join on a masked column compares masked values.
- **Performance**: "Use simple UDFs", "Prefer SQL to Python UDFs", and use expressions "that never throw errors, such as `try_divide`", because a possible error stops the compiler from pushing operations down.
- **Compute**: reading a table with filters or masks needs a SQL warehouse, standard access mode (formerly shared access mode) on Databricks Runtime 12.2 LTS or above, or dedicated access mode (formerly single user access mode) on Databricks Runtime 15.4 LTS or above with serverless compute enabled for the workspace.
- **Limitations** (selected): you "cannot apply row-level security or column masks to a view"; time travel is not supported with table-level filters or masks; deep and shallow clones are not supported on such tables; table-level filters and masks cannot be shared through OpenSharing (formerly Delta Sharing); `REPLACE TABLE` keeps existing filters and masks.

**ABAC instead of one table at a time.** For many tables, the page recommends attribute-based access control: "Databricks recommends ABAC policies when you need consistent row filtering and column masking across many tables. ABAC policies attach at the catalog or schema level and apply automatically based on governed tags." ABAC is in [chapter 23](23-Governance-and-Operations.md).

| Approach | Applies to | Managed with | Best for (overview page) |
| --- | --- | --- | --- |
| Table-level row filters and column masks | Individual tables and columns | `ALTER TABLE`, by the owner or a user with `MANAGE` | "Table-specific logic" |
| ABAC policies | Tables and columns matched by tags | `CREATE POLICY` on a catalog, schema or table | "Centralized rules applied automatically across many tables" |
| Dynamic views | A view over one or more tables | SQL in the view | "Sharing a curated or transformed version of the data" |

!!! tip "In the interview"
    **"How do you stop support staff from seeing customer e-mails and non-Canadian customers?"** In Unity Catalog, attach a column mask to `email` and a row filter on `country` to the table: both are SQL UDFs that check `is_account_group_member(...)`, and they apply to every query, notebook and dashboard. If the same rule must cover many tables, use ABAC policies on governed tags instead. A dynamic view also works, but only if users are denied the base table and every consumer goes through the view.

## 21.10 SQL script, Python notebook or job?
*Level: expert.*

**The problem.** The same nightly load can be a SQL script, a stored procedure, a PySpark notebook, a Lakeflow pipeline (formerly Delta Live Tables) or a task in a Lakeflow Job (formerly Databricks Jobs; the [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) record the rename and the removal of the Workflows menu item). An interviewer who asks "where would you put this logic?" wants to hear the trade-offs, not one favorite tool. This section is guidance from experience, not a Databricks rule.

| Situation | Good fit | Why |
| --- | --- | --- |
| A few SQL steps with a parameter, a check and a log row; the team writes SQL | SQL script, or a stored procedure if others must call it | Stays in one language; runs on a SQL warehouse; a procedure can be granted with `EXECUTE` and run by name (section 21.7) |
| Logic that needs Python libraries, API calls, files, unit tests with pytest, or complex branching | Python notebook or Python file (PySpark) | Full language, real test tooling, `spark.sql(..., args=...)` for safe SQL (chapter 16) |
| Tables that depend on each other and refresh incrementally, with data quality expectations | Lakeflow pipelines (formerly Delta Live Tables; see [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) | Declarative dependencies, incremental processing and expectations ([chapter 13](13-Declarative-Pipelines.md)) |
| Scheduling, retries, alerts, ordering of several steps (SQL, notebooks, pipelines) | Lakeflow Jobs (formerly Databricks Jobs / Workflows) | Orchestration belongs in the job, not in a `WHILE` loop ([chapter 15](15-Lakeflow-Jobs.md)) |
| A calculation used inside many queries and dashboards | SQL UDF in Unity Catalog | One definition, governed with `EXECUTE`; the optimizer sees the SQL body (section 21.6) |
| Per-user row or column restrictions | Row filters, column masks, or ABAC policies | Enforced on the table for every query (section 21.9, [chapter 23](23-Governance-and-Operations.md)) |

Rules of thumb that hold in all cases:

- **Set-based first.** A loop that runs one statement per row is the slowest way to do anything in Spark. Loop over days, tables or batches, never over rows. The Databricks loop pages compare their own loop examples with "the much more efficient relational computation".
- **Parameters as values, names through `IDENTIFIER`, never string concatenation** (section 21.5).
- **Make each step idempotent**, because a plain script is not a transaction (section 21.2).
- **Keep orchestration in the job.** Retries, schedules and dependencies between steps are easier to see and operate in a Lakeflow Job than inside a long script.

!!! tip "In the interview"
    **"When would you use SQL scripting instead of a Python notebook?"** When the logic is a handful of SQL statements with simple control flow (a run date, a quality gate, a backfill over days, a log row) and the people who maintain it work in SQL or on a SQL warehouse. I would switch to Python when I need libraries, external calls, or proper unit tests, and I would put scheduling and retries in a Lakeflow Job (formerly Databricks Jobs, the "Workflows" menu; [renamed in June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june)) either way. In both cases the heavy lifting stays in set-based statements, not loops over rows.

## 21.11 Practice questions
*Level: mixed.*

Answers marked "Run here" ran on Apache Spark 4.2 + Delta Lake 4.4.1 (`ex08_practice.py` and the section scripts); the rest are labeled.

### Scripts, variables and control flow

**Q1. What is a SQL script in Databricks, and on which compute can you run one?**

??? success "Answer"
    A SQL script is one compound statement, `BEGIN ... END`, holding declarations (variables, conditions, cursors, handlers, in that order) and then statements: DML, DDL, queries, `SET`, `EXECUTE IMMEDIATE`, control flow and nested blocks. The SQL scripting page says it "Applies to: Databricks SQL Databricks Runtime 16.3 and above", so SQL warehouses and clusters or serverless compute on Runtime 16.3 or later. In a notebook the compound statement must be the only statement in its cell.

    **Why:** the interviewer is checking that you know scripting is recent and version-gated, and that a script is one statement from the client's point of view.

**Q2. This fails with a syntax error. Why, and what is the fix?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  SET VAR run_count = run_count + 1;
END
```

??? success "Answer"
    Inside a compound statement the `VAR`/`VARIABLE` keyword is not allowed. Write `SET run_count = run_count + 1;`, which works for local variables and for session variables. Outside a script it is the other way round: `SET VAR` is required, because plain `SET x = ...` is read as a configuration setting.

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1 (from `ex01_script_basics.out`).*
    ```text
    ERROR: [PARSE_SYNTAX_ERROR] Syntax error at or near 'run_count': extra input 'run_count'. SQLSTATE: 42601 (line 2, pos 10)
    ```

    **Why:** the SET variable page: "Outside of a compound statement the keywords `VAR` or `VARIABLE` are mandatory ... Within a compound statement `VAR` or `VARIABLE` are not allowed."

**Q3. How do a local variable and a session variable differ, and how do you pass a value from Python into a SQL script?**

??? success "Answer"
    A local variable (`DECLARE x INT` inside `BEGIN ... END`) exists until its block ends and is hidden by a same-named variable in an inner block. A session variable (`DECLARE VARIABLE x INT` outside any script) lives until the session ends and can carry values from one script to the next. From Python, pass values as parameter markers: `spark.sql("BEGIN ... :cur ... END", args={"cur": "CAD"})`; a notebook widget or the Statement Execution API does the same.

    **Why:** the SQL scripting page names exactly these two ways: session variables between scripts, parameter markers from "a notebook widget, Python, or another language".

**Q4. What does this print?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  b1: BEGIN
    DECLARE x INT DEFAULT 1;
    b2: BEGIN
      DECLARE x INT DEFAULT 2;
      SET b1.x = b1.x + x;
      VALUES (b1.x, x);
    END b2;
  END b1;
END
```

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```text
    +----+----+
    |col1|col2|
    +----+----+
    |3   |2   |
    +----+----+
    ```

    Unqualified `x` is the innermost one (2). `b1.x` names the outer variable through its block label, so it becomes 1 + 2 = 3.

    **Why:** names resolve from the innermost scope outward, and labels "disambiguate duplicate variable names". Note the labels are on nested blocks: the top-level block may not have one.

**Q5. Find the bug.**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1, in the same shape with another label (the answer shows the error).*
```sql
nightly_load: BEGIN
  DECLARE run_date DATE DEFAULT current_date() - 1;
  ...
END nightly_load
```

??? success "Answer"
    A label is not allowed on the top-level compound statement ("label must not be specified for a top level compound statement or for an `ATOMIC` compound statement"). Remove it, or put the work in a labeled nested block inside an unlabeled `BEGIN ... END`. Locally the labeled version fails with `[PARSE_SYNTAX_ERROR] Syntax error at or near 'load_day'` (`ex01_script_basics.out`, same shape with another label).

    **Why:** labels exist so that `LEAVE`, `ITERATE` and qualified names can refer to an enclosing block; nothing encloses the top level.

**Q6. What does this print?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE i INT DEFAULT 10;
  DECLARE n INT DEFAULT 0;
  REPEAT
    SET n = n + 1;
    SET i = i + 5;
  UNTIL i > 10
  END REPEAT;
  VALUES (i, n);
END
```

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```text
    +----+----+
    |col1|col2|
    +----+----+
    |15  |1   |
    +----+----+
    ```

    `REPEAT` checks its condition after the body, so the body runs once even though `i` already starts at 10; after one pass `i = 15 > 10` and the loop ends. A `WHILE i <= 10` loop with the same start would also run once here, but a `WHILE` whose condition is false (or `NULL`) at the start runs zero times.

    **Why:** "Repeat the execution of a list of statements until a condition is true" (REPEAT page) versus "while a condition is true" (WHILE page).

**Q7. What is the difference between the `CASE` statement and the `CASE` expression?**

??? success "Answer"
    The `CASE` expression returns a value and can be used in any query (`SELECT CASE WHEN amount > 100 THEN 'big' END`). The `CASE` statement chooses which *statements* to run, ends with `END CASE`, and exists only inside a compound statement. Both have a simple form (`CASE expr WHEN value`) and a searched form (`CASE WHEN condition`).

    **Why:** the CASE statement page points to the CASE expression page "For case expressions that yield result values". Mixing them up gives syntax errors that are hard to read.

**Q8. Write a script that reloads `gold.daily_revenue` (one row per day and currency, cancelled orders excluded) for 1 to 4 March 2026, one day at a time, so that a rerun gives the same result.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1 (the output is in section 21.3).*
    ```sql
    BEGIN
      DECLARE d DATE DEFAULT DATE'2026-03-01';
      WHILE d <= DATE'2026-03-04' DO
        DELETE FROM gold.daily_revenue WHERE order_date = d;
        INSERT INTO gold.daily_revenue
          SELECT to_date(order_ts), currency, count(*), sum(amount)
          FROM silver.orders
          WHERE to_date(order_ts) = d AND coalesce(status, '') <> 'CANCELLED'
          GROUP BY ALL;
        SET d = d + INTERVAL 1 DAY;
      END WHILE;
    END
    ```

    Delete-then-insert per day makes each pass idempotent. `coalesce(status, '')` keeps the order with a `NULL` status (a plain `status <> 'CANCELLED'` would drop it, because `NULL <> 'CANCELLED'` is not true).

    **Why:** an interviewer will then ask "can you do it without a loop?". Yes: one `DELETE ... WHERE order_date BETWEEN ...` and one `INSERT ... GROUP BY` (or `INSERT ... REPLACE WHERE`, chapter 20) does the whole range in one pass. Loop per day only when each day is big or should commit separately.

**Q9. This loop is meant to add up shipped CAD amounts and stop at order 1006. What does it print, and why does it not stop where intended?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE shipped_cad DECIMAL(12,2) DEFAULT 0;
  DECLARE seen INT DEFAULT 0;
  rows_loop: FOR r AS SELECT order_id, status, amount, currency FROM silver.orders ORDER BY order_id DO
    SET seen = seen + 1;
    IF currency <> 'CAD' THEN ITERATE rows_loop; END IF;
    IF r.order_id >= 1006 THEN LEAVE rows_loop; END IF;
    IF status = 'SHIPPED' THEN SET shipped_cad = shipped_cad + amount; END IF;
  END FOR rows_loop;
  VALUES (seen, shipped_cad);
END
```

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1 (`ex02_control_flow.out`, test 10).*
    ```text
    +----+------+
    |col1|col2  |
    +----+------+
    |8   |377.90|
    +----+------+
    ```

    Order 1006 is in USD, so `ITERATE` skips to the next row before the `LEAVE` check runs; so does 1007. The first CAD row with an id of at least 1006 is 1008, the last row, so all 8 rows were read. The sum is right by luck: 59.90 (1001) + 318.00 (1005); 1003 is `PLACED`. Fix: put the `LEAVE` check first, or better, filter in the query (`WHERE currency = 'CAD' AND status = 'SHIPPED' AND order_id < 1006`) and drop the loop.

    **Why:** statement order inside a loop body matters, and a `FOR` over rows is usually a query in disguise.

**Q10. A five-step script fails at step 3. What state are the tables in, and how do you design for that?**

??? success "Answer"
    Steps 1 and 2 are committed; step 3 failed; 4 and 5 never ran. A plain `BEGIN ... END` is `NOT ATOMIC` by default: "previous SQL statements will not be rolled back". Design each step to be idempotent (delete-then-insert, `MERGE`, `INSERT ... REPLACE WHERE`) so a rerun of the whole script is safe, log progress, and use `BEGIN ATOMIC` (Public Preview, Databricks Runtime 17.0 and above) where all-or-nothing matters and its restrictions fit. Locally, a script that inserted a log row and then divided by zero left the log row in place (`ex01_script_basics.out`, test 9).

    **Why:** "is a script a transaction?" is a common trick question. Without `ATOMIC`, no.

### Error handling

**Q11. What is the difference between an EXIT and a CONTINUE handler, and where can you use each?**

??? success "Answer"
    An `EXIT` handler runs its action and then leaves the compound statement that declared it; execution goes on after that block's `END`. A `CONTINUE` handler runs its action and resumes "with the statement following the one that raised the condition". `EXIT` is available with SQL scripting (Databricks Runtime 16.3 and above, SQL warehouses); `CONTINUE` needs Databricks Runtime 18.1 and above. Open-source Spark 4.2 rejects `CONTINUE` handlers with `UNSUPPORTED_FEATURE.CONTINUE_EXCEPTION_HANDLER` (`ex03_handlers.out`) unless the flag `spark.sql.scripting.continueHandlerEnabled` is set to `true`, which is off by default (section 21.4).

    **Why:** `CONTINUE` is how you skip one bad step and keep going; with only `EXIT`, you get the same effect by wrapping the optional step in its own nested block (section 21.4).

**Q12. A block declares `EXIT HANDLER FOR SQLEXCEPTION` and `EXIT HANDLER FOR DIVIDE_BY_ZERO`. A statement divides by zero. Which handler runs?**

??? success "Answer"
    The `DIVIDE_BY_ZERO` handler. Among the handlers of the innermost block, the most specific wins: a named condition beats a `SQLSTATE`, which beats `SQLEXCEPTION`. The local run printed `DIVIDE_BY_ZERO handler` (section 21.4).

    **Why:** this is the "most appropriate handler" rule on the SQL scripting page.

**Q13. What does this print?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```sql
BEGIN
  DECLARE msg STRING DEFAULT 'start';
  b: BEGIN
    DECLARE EXIT HANDLER FOR DIVIDE_BY_ZERO SET msg = msg || ' > handled';
    SET msg = msg || ' > before';
    SET msg = msg || (1 / 0);
    SET msg = msg || ' > after';
  END b;
  SET msg = msg || ' > end';
  VALUES (msg);
END
```

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```text
    +------------------------------+
    |col1                          |
    +------------------------------+
    |start > before > handled > end|
    +------------------------------+
    ```

    The division fails, the `EXIT` handler appends ` > handled` and leaves block `b`, so ` > after` never runs; the outer block continues with ` > end`. The handler action here is a single statement, so it needs no `BEGIN ... END`.

    **Why:** `EXIT` exits the block that *declared* the handler, not the whole script.

**Q14. A scheduled script has `DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN INSERT INTO load_log ...; END;`. The job is always green, but gold is sometimes half loaded. Why, and what is the fix?**

??? success "Answer"
    The handler catches every error, logs it and then ends the block normally, so the script returns success and the scheduler never sees a failure. After logging, re-raise: on Databricks with `RESIGNAL` (Databricks Runtime 16.3 and above), or with `raise_error('...')`, which also works in open-source Spark (section 21.4 shows the log row kept and the run failing with `USER_RAISED_EXCEPTION`). Also make the steps idempotent so the rerun after the alert is safe.

    *Databricks only, not run here. Syntax from [RESIGNAL statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/resignal-stmt).*
    ```sql
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
      BEGIN
        INSERT INTO shop.gold.load_log VALUES (current_timestamp(), 'daily_revenue', 'FAILED');
        RESIGNAL;
      END;
    ```

    **Why:** swallowing errors is the most common error-handling bug in any language; the interviewer wants "log and re-raise".

**Q15. Inside a handler, should you use SIGNAL or RESIGNAL to fail the script?**

??? success "Answer"
    `RESIGNAL`, to re-raise the condition being handled. The SIGNAL page: "Databricks recommends using RESIGNAL to raise conditions from within a handler. RESIGNAL builds a diagnostic stack in the SQL Standard, while `SIGNAL` clears the stack." Use `SIGNAL` to raise your *own* condition in normal code, for example `SIGNAL no_orders SET MESSAGE_TEXT = 'no orders for the run date'` after a check. Both are Databricks only here (open-source Spark 4.2 gives a syntax error for `SIGNAL`).

    **Why:** `RESIGNAL` keeps the original error class and message for whoever reads the failure.

**Q16. What is `GET DIAGNOSTICS ... = ROW_COUNT` for, and what are its traps?**

??? success "Answer"
    It returns the number of rows affected by the most recent DML statement as a `BIGINT` (Databricks SQL, Databricks Runtime 18 LTS and above), so a script can log "inserted N rows" or fail when N is 0. Traps from the GET DIAGNOSTICS page: read it immediately after the DML, because any other statement or a `CALL` clears it; it is `NULL` after non-DML statements, inside a handler, and for writes to non-Delta tables; at most one `ROW_COUNT` assignment per statement. The `CONDITION 1` form reads the message, SQLSTATE, condition name and line number of the error being handled, and must be the first statement in the handler.

    **Why:** row counts in a load log are standard practice; knowing the exact rules shows you have used it.

**Q17. What does `BEGIN ATOMIC` give you, and what can you not put inside it?**

??? success "Answer"
    All statements in the block commit together or roll back together (Databricks SQL, Databricks Runtime 17.0 and above, Public Preview). Not allowed inside: exception handlers, nested `BEGIN ATOMIC`, a label, DDL ("Only DML operations ..., `SELECT` statements, variable declarations and assignments, control-flow statements ..., and calls to atomic stored procedures are allowed"). Multi-table atomic blocks need Databricks Runtime 18.0 and catalog commits on all tables. Variable assignments are not rolled back.

    **Why:** an atomic delete-and-reinsert of a day means readers never see the day missing.

**Q18. Write a script that refuses to load `gold.customer_revenue` (shipped revenue per customer) while `silver.orders` has orders without a status, and loads it otherwise.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```sql
    BEGIN
      DECLARE bad INT;
      SET bad = (SELECT count_if(status IS NULL) FROM silver.orders);
      IF bad > 0 THEN
        SELECT raise_error(bad || ' order(s) without status, gold not loaded');
      END IF;
      INSERT OVERWRITE gold.customer_revenue
        SELECT customer_id, sum(amount) FROM silver.orders WHERE status = 'SHIPPED' GROUP BY ALL;
      SELECT * FROM gold.customer_revenue ORDER BY customer_id;
    END
    ```

    Output with order 1008 still without status, then after `UPDATE silver.orders SET status = 'PLACED' WHERE status IS NULL`:
    ```text
    ERROR: [USER_RAISED_EXCEPTION] 1 order(s) without status, gold not loaded SQLSTATE: P0001

    +-----------+-------+
    |customer_id|revenue|
    +-----------+-------+
    |1          |59.90  |
    |2          |249.00 |
    |3          |159.00 |
    |4          |318.00 |
    +-----------+-------+
    ```

    On Databricks you could declare `DECLARE bad_data CONDITION FOR SQLSTATE '45001'` and `SIGNAL bad_data SET MESSAGE_TEXT = ...` instead of `raise_error`, which gives callers a SQLSTATE they can handle specifically.

    **Why:** a quality gate before gold is one of the most useful things a short script does. In Lakeflow pipelines (formerly Delta Live Tables, [renamed](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) the same idea is an expectation that fails the update ([chapter 14](14-Data-Quality-and-CDC.md)).

### Dynamic SQL

**Q19. A colleague builds `EXECUTE IMMEDIATE 'SELECT ... WHERE currency = ''' || user_input || ''''`. Show what goes wrong and fix it.**

??? success "Answer"
    With `user_input = CAD' OR '1'='1` the statement becomes `... WHERE currency = 'CAD' OR '1'='1'`, which is true for every row: locally it counted all 8 orders. Bind the value instead: `EXECUTE IMMEDIATE '... WHERE currency = :cur' USING user_input AS cur`, which counted 0, because the whole input was compared as one string (section 21.5, `ex04_dynamic_sql.out`).

    **Why:** a parameter marker is bound after the statement is parsed, so input can never change the statement's structure. That is the definition of SQL injection protection.

**Q20. Can a parameter marker stand for a table name? How do you choose a table at run time?**

??? success "Answer"
    No: a marker is a value, and `SELECT ... FROM :tbl` is a syntax error ([section 17.9](17-Databricks-SQL-vs-Standard.md)). Wrap it in `IDENTIFIER(:tbl)` (or `IDENTIFIER(var)` with a variable). The string must parse as a name; locally `'silver.orders; DROP TABLE silver.customers'` failed with `PARSE_SYNTAX_ERROR` and the customers table was untouched. If users supply the name, also restrict it to an allowed list or rely on Unity Catalog privileges.

    **Why:** `IDENTIFIER` "enables SQL-injection-safe parameterization of identifiers" (Databricks SQL, Databricks Runtime 13.3 LTS and above).

**Q21. What happens with `EXECUTE IMMEDIATE '<query>' INTO v` when the query returns no rows? Two rows? A statement that is not a query?**

??? success "Answer"
    No rows: `v` becomes `NULL`. Two or more rows: `ROW_SUBQUERY_TOO_MANY_ROWS`. Not a query: `INVALID_STATEMENT_FOR_EXECUTE_INTO`. All three are on the EXECUTE IMMEDIATE page; the first two are in `ex04_dynamic_sql.out`.

    **Why:** a lookup that silently returns `NULL` can make a later comparison quietly false, as in section 21.3; check for `NULL` after `INTO` when a missing row is an error.

**Q22. Find the bug in this notebook code, where `cur` comes from a widget.**

*Databricks only, not run here (`dbutils` needs a workspace); the same f-string query ran here with a fixed value in `ex04_dynamic_sql.out`.*
```python
cur = dbutils.widgets.get("currency")
spark.sql(f"SELECT count(*) FROM shop.silver.orders WHERE currency = '{cur}'").show()
```

??? success "Answer"
    The widget value is pasted into the SQL text, so a value like `CAD' OR '1'='1` changes the query (locally the f-string version counted 8 instead of 0). Bind it:

    *Databricks only, not run here (`dbutils` needs a workspace); the `spark.sql(..., args=...)` part ran here in section 21.5.*
    ```python
    cur = dbutils.widgets.get("currency")
    spark.sql("SELECT count(*) FROM shop.silver.orders WHERE currency = :cur",
              args={"cur": cur}).show()
    ```

    Or use the DataFrame API: `spark.table("shop.silver.orders").where(F.col("currency") == cur).count()`.

    **Why:** "Python ... using its `pyspark.sql.SparkSession.sql()` API" is one of the ways the Parameter markers page lists to supply markers.

**Q23. Why does `EXECUTE IMMEDIATE 'SELECT ? + :b' USING 1, 2 AS b` fail?**

??? success "Answer"
    Markers in one statement must be all positional or all named: `[INVALID_QUERY_MIXED_QUERY_PARAMETERS] Parameterized query must either use positional, or named parameters, but not both.` (`ex04_dynamic_sql.out`). Use `:a + :b` with `USING 1 AS a, 2 AS b`.

    **Why:** the EXECUTE IMMEDIATE page: "they must be all positional (`?`) or all named (`:parm1`)".

**Q24. Write a script that returns the row count of each of `silver.customers`, `silver.orders` and `silver.order_items` in one string.**

??? success "Answer"
    *Run here: Apache Spark 4.2 (plain session, see section 21.5).*
    ```sql
    BEGIN
      DECLARE n BIGINT;
      DECLARE report STRING DEFAULT '';
      FOR t AS SELECT tbl FROM VALUES ('silver.customers'), ('silver.orders'), ('silver.order_items') AS v(tbl) DO
        EXECUTE IMMEDIATE 'SELECT count(*) FROM IDENTIFIER(:name)' INTO n USING t.tbl AS name;
        SET report = report || t.tbl || '=' || n || ' ';
      END FOR;
      VALUES (trim(report));
    END
    ```
    ```text
    +-------------------------------------------------------+
    |col1                                                   |
    +-------------------------------------------------------+
    |silver.customers=4 silver.orders=8 silver.order_items=8|
    +-------------------------------------------------------+
    ```

    **Why:** looping over metadata (tables, dates) with one set-based statement per pass is the right use of a loop; `IDENTIFIER` keeps the table name safe.

### Functions and procedures

**Q25. Why does `CREATE FUNCTION silver.bad_total(x DECIMAL(10,2)) RETURNS DECIMAL(20,2) RETURN sum(x)` fail?**

??? success "Answer"
    A scalar SQL UDF computes one value from one row's arguments; its `RETURN` expression "cannot contain" aggregate, window or ranking functions, or row-producing functions such as `explode`. Locally: `[USER_DEFINED_FUNCTIONS.CANNOT_CONTAIN_COMPLEX_FUNCTIONS] ... SQL scalar function cannot contain aggregate/window/generate functions: sum(x)`. Aggregate in the query that calls the UDF instead, or make the body a query (`RETURN SELECT sum(...) FROM ...`) or a table function if you need a set.

    **Why:** shows you understand that a scalar UDF is applied per row.

**Q26. A persistent SQL UDF refers to a session variable `vat`. What happens, and what should you do instead?**

??? success "Answer"
    `CREATE` fails: locally `[INVALID_TEMP_OBJ_REFERENCE] Cannot create the persistent object ... because it references to the temporary object vat of the type VARIABLE`; the DECLARE VARIABLE page lists "the body of a persisted SQL UDF" among the places variables cannot be used. Make the rate a parameter with a `DEFAULT` (`tax_rate DECIMAL(4,3) DEFAULT 0.05`), or use a temporary function if it is truly session-only.

    **Why:** a persistent object must not depend on something that exists only in one session.

**Q27. You have a choice between a SQL UDF and a Python UDF for `amount / 1.05` rounded to cents. Which do you pick, and how would you show the difference?**

??? success "Answer"
    The SQL UDF (or no UDF at all: a plain expression). `EXPLAIN` shows why: the SQL UDF disappears into a plain `Project` with the arithmetic, while the Python UDF appears as a separate Python evaluation step (`BatchEvalPython` or `ArrowEvalPython`) that ships rows to a Python worker and back (section 21.6). Databricks says the same: "Prefer SQL to Python UDFs. Python UDFs are less performant than SQL and offer fewer optimization opportunities." Use Python only for logic SQL cannot express.

    **Why:** a common interview code review: "this UDF does what a built-in does; delete it".

**Q28. What is the difference between a Unity Catalog Python UDF (`CREATE FUNCTION ... LANGUAGE PYTHON`) and a PySpark `@udf`?**

??? success "Answer"
    The Unity Catalog function is persisted in a schema, governed with `GRANT EXECUTE`, discoverable in Catalog Explorer, and callable from SQL warehouses (serverless or pro), notebooks and jobs; it needs Unity Catalog and Databricks Runtime 13.3 LTS or above. A PySpark `@udf` (or `spark.udf.register`) is session-scoped: it exists only in that SparkSession, is "not governed or shared", and suits quick development in one notebook or job. Python UDFs in Unity Catalog are `NOT DETERMINISTIC` unless you declare `DETERMINISTIC`.

    **Why:** the UDF overview page's comparison table is exactly this; knowing it shows you think about governance, not just code.

**Q29. Write a table function `silver.top_orders(n)` returning the `n` largest orders. Why does the obvious version with `LIMIT n` fail here?**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```sql
    CREATE OR REPLACE FUNCTION silver.top_orders(n INT)
      RETURNS TABLE (order_id INT, amount DECIMAL(10,2))
      RETURN SELECT order_id, amount FROM silver.orders ORDER BY amount DESC LIMIT n;
    ```
    ```text
    ERROR: [INVALID_LIMIT_LIKE_EXPRESSION.IS_UNFOLDABLE] The limit like expression "outer(top_orders.n)" is invalid. The limit expression must evaluate to a constant value. SQLSTATE: 42K0E; line 1 pos 70;
    ```

    Rank in a subquery and filter on the rank instead:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```sql
    CREATE OR REPLACE FUNCTION silver.top_orders(n INT)
      RETURNS TABLE (order_id INT, amount DECIMAL(10,2))
      RETURN SELECT order_id, amount
             FROM (SELECT order_id, amount, row_number() OVER (ORDER BY amount DESC) AS rn FROM silver.orders)
             WHERE rn <= top_orders.n;

    SELECT * FROM silver.top_orders(2);
    ```
    ```text
    +--------+------+
    |order_id|amount|
    +--------+------+
    |1005    |318.00|
    |1002    |249.00|
    +--------+------+
    ```

    **Why:** `LIMIT` needs a constant when the query is planned; a function parameter is a value that arrives at call time. Ranking with a filter has no such restriction. (Only tested on open-source Spark 4.2; Databricks behavior for `LIMIT` with a parameter is not verified.)

**Q30. Can you call a SQL UDF inside a lambda, as in `transform(prices, x -> silver.with_tax(x))`?**

??? success "Answer"
    No. The Lambda functions page says the lambda body is an expression "which does not contain a subquery or a SQL user-defined function", and the local engine agrees:

    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```text
    ERROR: [UNSUPPORTED_FEATURE.LAMBDA_FUNCTION_WITH_SQL_UDF] The feature is not supported: Lambda function with SQL UDF spark_catalog.silver.with_tax in a higher order function. SQLSTATE: 0A000; line 1 pos 83
    ```

    Inline the expression: `transform(prices, x -> x * 1.05)` returned `[10.5000, 21.0000]` for `[10, 20]`. Higher-order functions are in [section 18.8](18-Semi-Structured-Data.md).

    **Why:** a small rule that catches people who try to reuse UDFs everywhere.

**Q31. Function or stored procedure: how do you decide?**

??? success "Answer"
    A function returns a value or a table and is used *inside* a query; it should not change data. A procedure (`CREATE PROCEDURE ... AS BEGIN ... END`, Databricks SQL and Databricks Runtime 17.0 and above, Unity Catalog only) is a saved script run on its own with `CALL`: it can run DML and DDL, loop, handle errors, return values through `OUT`/`INOUT` parameters and return the last query's result set. Both share one namespace per schema and are governed with `EXECUTE`.

    **Why:** people coming from T-SQL or PL/SQL expect procedures; this shows you know they exist in Databricks now and when they fit.

**Q32. `CALL shop.gold.load_daily_revenue(DATE'2026-03-03', 0)` fails, where the second parameter is `OUT rows_written BIGINT`. Why?**

??? success "Answer"
    For `OUT` and `INOUT` parameters, "the argument must be a session variable, or local variable", because the procedure writes the result back into it. Declare one first: `DECLARE VARIABLE n BIGINT; CALL shop.gold.load_daily_revenue(DATE'2026-03-03', n); SELECT n;`. If the procedure fails, `n` keeps its old value.

    *Databricks only, not run here. Syntax from [CALL](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-call).*

    **Why:** reading the CALL page's argument rules; also note `DATE'...'` rather than a string for a `DATE` parameter.

**Q33. You want an analyst group to run the gold load, but not to write to gold tables directly. How?**

??? success "Answer"
    Create the procedure with `SQL SECURITY DEFINER` and grant the group `EXECUTE` on it. The body then runs "under the authority of the owner (definer) of the procedure", and "The invoker only requires the `EXECUTE` privilege on the procedure". With `SQL SECURITY INVOKER`, the caller would need write privileges on the gold tables. The `DEFINER` characteristic is labeled "Applies to: Databricks SQL" on the CREATE PROCEDURE page. `session_user()` inside the body still returns the caller, so audit logs record who ran it.

    **Why:** the same idea as a view or `SECURITY DEFINER` routine in other databases: grant the action, not the underlying access.

### Recursive CTEs, views and access control

**Q34. Orders should be numbered 1001 to 1010 without gaps. Write a query that lists the missing ids.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```sql
    WITH RECURSIVE ids(id) AS (
      SELECT 1001 UNION ALL SELECT id + 1 FROM ids WHERE id < 1010
    )
    SELECT id AS missing_order_id FROM ids
    WHERE id NOT IN (SELECT order_id FROM silver.orders) ORDER BY id;
    ```
    ```text
    +----------------+
    |missing_order_id|
    +----------------+
    |1009            |
    |1010            |
    +----------------+
    ```

    `explode(sequence(1001, 1010))` builds the same series without recursion. Prefer `NOT EXISTS` or a `LEFT ANTI JOIN` over `NOT IN` if `order_id` could be `NULL`: one `NULL` in the subquery makes `NOT IN` return no rows.

    **Why:** gap detection is a classic; the `NOT IN` and `NULL` remark is the follow-up interviewers like.

**Q35. A recursive CTE has no stop condition. What happens on Databricks, and how is it limited?**

??? success "Answer"
    It stops with `RECURSION_LEVEL_LIMIT_EXCEEDED` after the default 100 levels (set another with `MAX RECURSION LEVEL n`). The result is also limited to 1,000,000 rows unless the outer query has a `LIMIT` (and from Databricks Runtime 17.2 `LIMIT ALL` removes the limit). Locally, the same query with `LIMIT 3` returned 1, 2, 3 and stopped (section 21.8).

    **Why:** shows you know recursion is bounded and how to bound it yourself.

**Q36. Why does `CREATE VIEW gold.v_big_orders AS SELECT * FROM silver.orders WHERE amount >= min_amt` fail when `min_amt` is a session variable, and what are the alternatives?**

??? success "Answer"
    A persisted view cannot reference a session variable (DECLARE VARIABLE page); locally it fails with `INVALID_TEMP_OBJ_REFERENCE`. Alternatives: a temporary view (which worked locally and returned 4 orders), a SQL table function with a parameter (`silver.big_orders(min_amt)`), or, from Databricks Runtime 18.0, a parameter marker in the view definition (the Parameter markers page lifts the DDL restriction there). That last one is not a per-query parameter: the page allows a marker "wherever you can use a literal of the parameter marker's type", so the value is bound when the view is created, as if typed in as a literal (inferred from that wording, not tested here).

    **Why:** a table function is the "parameterized view" most people are looking for.

**Q37. Row filter, dynamic view or ABAC policy: when do you use each?**

??? success "Answer"
    A **row filter / column mask** is attached to one table with `ALTER TABLE`, so every query on that table is restricted: good for table-specific rules. An **ABAC policy** attaches at catalog or schema level and applies through governed tags to every matching table: Databricks recommends it "when you need consistent row filtering and column masking across many tables". A **dynamic view** wraps tables in a view using `is_account_group_member()`: good for sharing a curated, joined or reshaped version of the data, but only safe if users cannot read the base tables. All need Unity Catalog.

    **Why:** the comparison table on the row filters and column masks overview page; see [chapter 23](23-Governance-and-Operations.md) for ABAC.

**Q38. A row filter function was declared `f(dept INT)` but the column `department` is a `STRING`. With ANSI mode off, users see every row. Why?**

??? success "Answer"
    The column value is implicitly cast to the parameter type. With ANSI mode disabled, "uncastable values are silently converted to `NULL`", so the function sees `NULL` for `'exec'` and `'engineering'`; the documented example's filter returned true for `NULL` input, so every row passed. Declare the parameter with the column's exact type (`STRING`), and keep ANSI mode on so a bad cast raises an error instead.

    *Databricks only, not run here. Syntax from [Row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/).*

    **Why:** a security control that fails open is the worst kind of bug; the page documents this exact case.

**Q39. Someone ran `DROP FUNCTION shop.silver.ca_or_finance` and now nobody can query `shop.silver.customers`. What happened, and how do you fix it?**

??? success "Answer"
    The function was still attached as the table's row filter. The Manually apply page: "You must perform the `ALTER TABLE ... DROP ROW FILTER` command before you drop the function. If you don't, the table will be in an inaccessible state." Fix with `ALTER TABLE shop.silver.customers DROP ROW FILTER;` (or recreate the function), and next time drop the filter first.

    *Databricks only, not run here. Syntax from [Manually apply row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/manually-apply).*

    **Why:** failing closed (no access) is the safe default, but it is still an outage.

**Q40. Your team must build a nightly gold load with a quality gate, a backfill option and a log table, and alert on failure. Where would you put each part?**

??? success "Answer"
    The transformations as set-based SQL (`MERGE` or `INSERT ... REPLACE WHERE`) in a stored procedure or SQL script with a run-date parameter, an `IF` quality gate that raises an error, and log rows (with `RESIGNAL` or `raise_error` after logging). Backfill by calling the same procedure for a range of dates, or with one set-based statement over the range. Schedule, retries and failure alerts in a Lakeflow Job (formerly Databricks Jobs, the "Workflows" menu item; [renamed in June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june)). If the team works mostly in Python or needs unit tests and libraries, the same steps go in a PySpark notebook or file with `spark.sql(..., args=...)`; if the tables form a dependency graph with expectations, Lakeflow pipelines (formerly Delta Live Tables, [renamed](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) fit better.

    **Why:** the interviewer is testing judgment: SQL scripting for SQL-shaped logic, the job for orchestration, and no row-by-row loops.

## Sources

- [SQL scripting](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-scripting) (last updated Sep 11, 2026)
- [BEGIN END compound statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/compound-stmt) (last updated Oct 9, 2026)
- [IF THEN ELSE statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/if-stmt) (last updated Sep 11, 2026)
- [CASE statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/case-stmt) (last updated Sep 11, 2026)
- [WHILE statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/while-stmt) (last updated Sep 11, 2026)
- [REPEAT statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/repeat-stmt) (last updated Sep 11, 2026)
- [LOOP statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/loop-stmt) (last updated Sep 11, 2026)
- [FOR statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/for-stmt) (last updated Oct 15, 2026)
- [ITERATE statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/iterate-stmt) (last updated Oct 15, 2026)
- [LEAVE statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/leave-stmt) (last updated Oct 15, 2026)
- [SIGNAL statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/signal-stmt) (last updated Sep 11, 2026)
- [RESIGNAL statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/resignal-stmt) (last updated Sep 11, 2026)
- [GET DIAGNOSTICS statement](https://docs.databricks.com/aws/en/sql/language-manual/control-flow/get-diagnostics-stmt) (last updated Sep 11, 2026)
- [SET variable](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-set-variable) (last updated Sep 11, 2026)
- [DECLARE VARIABLE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-declare-variable) (last updated Sep 11, 2026)
- [Parameter markers](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-parameter-marker) (last updated Sep 11, 2026)
- [IDENTIFIER clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-names-identifier-clause) (last updated Oct 15, 2026)
- [EXECUTE IMMEDIATE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-execute-immediate) (last updated Sep 11, 2026)
- [CREATE FUNCTION (SQL, Python, Scala, and Java)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-sql-function) (last updated Nov 6, 2026)
- [What are user-defined functions (UDFs)?](https://docs.databricks.com/aws/en/udf/) (last updated Sep 22, 2026)
- [SQL and Python user-defined functions (UDFs) in Unity Catalog](https://docs.databricks.com/aws/en/udf/unity-catalog) (last updated Nov 6, 2026)
- [Lambda functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-lambda-functions) (last updated Sep 11, 2026)
- [CREATE PROCEDURE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-procedure) (last updated Nov 3, 2026)
- [CALL](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-call) (last updated Sep 11, 2026)
- [DESCRIBE PROCEDURE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-aux-describe-procedure) (last updated Sep 11, 2026)
- [DROP PROCEDURE](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-drop-procedure) (last updated Nov 3, 2026)
- [Common table expression (CTE)](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-cte) (last updated Sep 11, 2026)
- [What is a view?](https://docs.databricks.com/aws/en/views/) (last updated Oct 15, 2026)
- [CREATE VIEW](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-create-view) (last updated Oct 29, 2026)
- [Create a dynamic view](https://docs.databricks.com/aws/en/views/dynamic) (last updated Oct 6, 2026)
- [Row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/) (last updated Nov 6, 2026)
- [Manually apply row filters and column masks](https://docs.databricks.com/aws/en/data-governance/unity-catalog/filters-and-masks/manually-apply) (last updated Oct 8, 2026)
- [`ROW FILTER` clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-row-filter) (last updated Sep 11, 2026)
- [Column `mask` clause](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-ddl-column-mask) (last updated Sep 11, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026)
- [SQL Scripting, Apache Spark 4.2.0 documentation](https://spark.apache.org/docs/4.2.0/sql-ref-scripting.html) (no last-updated date on the page)
- [compound statement, Apache Spark 4.2.0 documentation](https://spark.apache.org/docs/4.2.0/control-flow/compound-stmt.html) (no last-updated date on the page)
