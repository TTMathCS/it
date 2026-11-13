# 28. Dialect differences

*Every database speaks its own version of SQL, called a dialect. The core (`SELECT`, joins, `GROUP BY`, window
functions) is nearly the same everywhere; the edges (dates, text functions, division, upserts, quoting) are not.
This chapter collects every difference between PostgreSQL and SQLite met in this course, with runs that prove the
most surprising ones, then gives the same common tasks in the other databases a data engineer meets.*

!!! abstract "In this chapter"
    **You will learn:**

    - the PostgreSQL and SQLite differences that change answers, not just syntax
    - one table of where each was shown in this course
    - the same everyday tasks in MySQL, SQL Server, Oracle, Snowflake, BigQuery and Databricks
    - habits that make SQL run on more than one database

    **You need:** Parts I and II. This is a reference chapter: come back to it whenever a query that worked in one
    place fails, or quietly gives a different answer, in another.

## 28.1 PostgreSQL and SQLite: differences that change the answer { #answers }

A syntax error is the harmless kind of difference: you see it at once. These are the dangerous ones, where both databases run
the query and return different results.

**Division and casting.** Integer division is the same on both (`7 / 2` is 3). Casting is not:

<!-- sql pgerror -->
```sql
SELECT CAST(3.99 AS INTEGER) AS cast_down,
       CAST('12abc' AS INTEGER) AS cast_text;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>invalid input syntax for type integer: "12abc"</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 1 row.</p>
<!-- /result -->

PostgreSQL refuses `'12abc'`, and run on its own, `CAST(3.99 AS INTEGER)` gives 4: it rounds. SQLite reads the
leading digits (12) and cuts off the fraction (3).

<!-- sql pg -->
```sql
SELECT CAST(3.99 AS INTEGER) AS cast_down, 7 / 2 AS int_div, CAST(7 AS NUMERIC) / 2 AS numeric_div;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| cast_down | int_div | numeric_div |
| --- | --- | --- |
| 4 | 3 | 3.5000000000000000 |
<!-- /result -->

<!-- sql sqlite -->
```sql
SELECT CAST(3.99 AS INTEGER) AS cast_down, 7 / 2 AS int_div, CAST(7 AS NUMERIC) / 2 AS numeric_div;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| cast_down | int_div | numeric_div |
| --- | --- | --- |
| 3 | 3 | 3 |
<!-- /result -->

SQLite's `NUMERIC` turns `7` into an integer again, so the division stays whole. Write `7 * 1.0 / 2` or
`CAST(7 AS REAL) / 2` when you want 3.5 on both ([chapter 4](04-Expressions-Case-Numbers-Dates-Cast.md#cast)).

**Division by zero.** PostgreSQL stops with an error; SQLite returns NULL and carries on:

<!-- sql pgerror -->
```sql
SELECT 10 / 0 AS result;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>division by zero</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 1 row.</p>
<!-- /result -->

Use `x / NULLIF(y, 0)` to get NULL on both ([chapter 4](04-Expressions-Case-Numbers-Dates-Cast.md#coalesce-nullif)).

**LIKE and case.** PostgreSQL's `LIKE` is case-sensitive; SQLite's ignores the case of the letters A to Z:

**Task:** Count the customers whose name starts with a small "a".

<!-- sql pg -->
```sql
SELECT COUNT(*) AS names_starting_a FROM customers WHERE name LIKE 'a%';
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| names_starting_a |
| --- |
| 0 |
<!-- /result -->

<!-- sql sqlite -->
```sql
SELECT COUNT(*) AS names_starting_a FROM customers WHERE name LIKE 'a%';
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| names_starting_a |
| --- |
| 2 |
<!-- /result -->

Write `LOWER(name) LIKE 'a%'` to get the same answer on both ([chapter 5](05-Text-Functions-and-Pattern-Matching.md#like-case)).

**Where NULLs sort.** PostgreSQL puts NULLs last in ascending order, SQLite first. The same `ORDER BY` gives rows in
a different order, which a test checker counts as wrong:

**Task:** Show the first 2 customers by city.

<!-- sql pg -->
```sql
SELECT customer_id, city FROM customers ORDER BY city LIMIT 2;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

| customer_id | city |
| --- | --- |
| 2 | Lagos |
| 10 | Lisbon |
<!-- /result -->

<!-- sql sqlite -->
```sql
SELECT customer_id, city FROM customers ORDER BY city LIMIT 2;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 2 rows.</p>

| customer_id | city |
| --- | --- |
| 5 | *NULL* |
| 2 | Lagos |
<!-- /result -->

Add `NULLS FIRST` or `NULLS LAST` (both databases accept them; SQLite since 3.30) whenever the sorted column can be
NULL ([chapter 6](06-Null-and-Three-Valued-Logic.md#sorting)).

**Rounding.** `ROUND` on a `NUMERIC` in PostgreSQL rounds exact decimals half away from zero; SQLite rounds a binary
floating-point number, which can land a cent away. The tax on a 9.50 item is the classic case
([chapter 4](04-Expressions-Case-Numbers-Dates-Cast.md#rounding)):

**Task:** Show product 11's price with 13% tax, rounded to cents.

<!-- sql pg -->
```sql
SELECT ROUND(price * 1.13, 2) AS with_tax FROM products WHERE product_id = 11;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| with_tax |
| --- |
| 10.74 |
<!-- /result -->

<!-- sql sqlite -->
```sql
SELECT ROUND(price * 1.13, 2) AS with_tax FROM products WHERE product_id = 11;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| with_tax |
| --- |
| 10.73 |
<!-- /result -->

**Invalid dates.** PostgreSQL refuses 30 February; SQLite's `date()` rolls it over into March
([chapter 16](16-Dates-and-Time-Series.md#storage)):

<!-- sql pgerror -->
```sql
SELECT CAST('2026-02-30' AS DATE) AS d;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>date/time field value out of range: "2026-02-30"</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 1 row.</p>
<!-- /result -->

## 28.2 PostgreSQL and SQLite: every difference in this course { #table }

| Topic | PostgreSQL 16 | SQLite 3.53 | Chapter |
| --- | --- | --- | --- |
| `CAST(3.99 AS INTEGER)` | 4 (rounds) | 3 (truncates) | [4](04-Expressions-Case-Numbers-Dates-Cast.md#cast) |
| `CAST('12abc' AS INTEGER)` | error | 12 | [4](04-Expressions-Case-Numbers-Dates-Cast.md#cast) |
| `CAST(7 AS NUMERIC) / 2` | 3.5 | 3 | [4](04-Expressions-Case-Numbers-Dates-Cast.md#cast) |
| `ROUND(double precision, 2)` | error: use `NUMERIC` | works | [4](04-Expressions-Case-Numbers-Dates-Cast.md#round-error) |
| `ROUND(price * 1.13, 2)` | exact decimal | binary float, can differ by a cent | [4](04-Expressions-Case-Numbers-Dates-Cast.md#rounding) |
| `10 / 0` | error | NULL | [4](04-Expressions-Case-Numbers-Dates-Cast.md#arithmetic) |
| `LIKE` | case-sensitive (`ILIKE` ignores case) | ignores case of A to Z | [5](05-Text-Functions-and-Pattern-Matching.md#like-case) |
| Regular expressions | `~`, `REGEXP_REPLACE` ... | not built in | [5](05-Text-Functions-and-Pattern-Matching.md#regex) |
| Find, split text | `STRPOS`, `SPLIT_PART`, `LEFT`, `RIGHT` | `INSTR`, `SUBSTR` | [5](05-Text-Functions-and-Pattern-Matching.md#split) |
| `STRING_AGG(x, ', ' ORDER BY x)` | yes | yes (3.44+); older: `GROUP_CONCAT` | [5](05-Text-Functions-and-Pattern-Matching.md#string-agg) |
| NULLs in `ORDER BY ... ASC` | last | first | [6](06-Null-and-Three-Valued-Logic.md#sorting) |
| `IS DISTINCT FROM` | yes | yes (3.39+); also `IS NOT` | [6](06-Null-and-Three-Valued-Logic.md#is-null) |
| `"double quotes"` | a column name | a column name, or text if no such column | [2](02-Select-Where-Order-By-Limit.md#quotes) |
| `SELECT` alias in `WHERE` / `HAVING` | error | works | [3](03-The-Order-a-Query-Runs-In.md#differences) |
| column neither grouped nor aggregated | error | works (value from some row) | [7](07-Aggregation-Group-By-Having.md#select-rule) |
| `ORDER BY` a column not in `SELECT DISTINCT` | error | works | [3](03-The-Order-a-Query-Runs-In.md#differences) |
| Date type | real `DATE`, `TIMESTAMP` | text `'YYYY-MM-DD'`, functions `date()`, `strftime()` | [16](16-Dates-and-Time-Series.md#storage) |
| `DATE '2026-01-01'` literal | yes | no | [16](16-Dates-and-Time-Series.md#storage) |
| Date arithmetic | `d + 7`, `INTERVAL`, `DATE_TRUNC`, `EXTRACT` | `date(d, '+7 days')`, `strftime`, `julianday` | [16](16-Dates-and-Time-Series.md#arithmetic) |
| `GROUPING SETS`, `ROLLUP`, `CUBE` | yes | no: `UNION ALL` | [27](27-Grouping-Sets-Rollup-Cube-Lateral.md#union-all) |
| `LATERAL` | yes | no: window functions, `json_each` | [27](27-Grouping-Sets-Rollup-Cube-Lateral.md#lateral) |
| `FILTER (WHERE ...)` | yes | yes (3.30+) | [27](27-Grouping-Sets-Rollup-Cube-Lateral.md#filter) |
| `MERGE` | yes (15+) | no: `ON CONFLICT` | [17](17-Insert-Update-Delete-Merge.md#merge) |
| `ON CONFLICT ... DO UPDATE` | yes | yes; `INSERT ... SELECT` needs a `WHERE` | [17](17-Insert-Update-Delete-Merge.md#upsert), [22](22-Duplicates-and-Incremental-Loads.md#incremental) |
| `UPDATE ... FROM`, `RETURNING` | yes | yes (3.33+, 3.35+) | [17](17-Insert-Update-Delete-Merge.md#update-from) |
| `DELETE ... USING`, `TRUNCATE` | yes | no | [17](17-Insert-Update-Delete-Merge.md#delete) |
| Types | enforced; `VARCHAR(n)` length checked | stored as given unless `STRICT` | [18](18-Create-Table-Types-Constraints.md#affinity) |
| Auto-numbered id | `GENERATED ALWAYS AS IDENTITY` | `INTEGER PRIMARY KEY` | [18](18-Create-Table-Types-Constraints.md#identity) |
| Error inside a transaction | whole transaction aborted | only that statement undone | [20](20-Transactions-and-Isolation.md#errors) |
| Concurrent writers | row locks, isolation levels | one writer at a time | [20](20-Transactions-and-Isolation.md#sqlite) |
| Views | `CREATE OR REPLACE`; updatable | drop and create; read-only | [21](21-Views-and-Materialized-Views.md#replace) |
| Materialized views | yes | no: summary table | [21](21-Views-and-Materialized-Views.md#materialized) |
| JSON | `JSONB` type, GIN index | JSON functions on text | [24](24-JSON-and-Arrays.md#storing) |
| Arrays | yes | no: JSON arrays | [24](24-JSON-and-Arrays.md#arrays) |
| `EXPLAIN` | `EXPLAIN`, `EXPLAIN ANALYZE` | `EXPLAIN QUERY PLAN` | [25](25-Indexes-and-Explain.md#seq-scan) |

The pattern: **SQLite is forgiving, PostgreSQL is strict.** A query correct on PostgreSQL almost always runs on
SQLite; the reverse often fails. When a test lets you choose, a query you checked on PostgreSQL is the safer one.

## 28.3 The same task in other databases { #others }

These come from each product's documentation and are **not run here** (only PostgreSQL and SQLite are installed for
this course). Check the version you use: databases add functions every year.

### Rows, text and NULLs { #others-basics }

| Task | MySQL 8 | SQL Server | Oracle | Snowflake | BigQuery | Databricks |
| --- | --- | --- | --- | --- | --- | --- |
| first 10 rows | `LIMIT 10` | `TOP (10)` or `OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY` | `FETCH FIRST 10 ROWS ONLY` | `LIMIT 10` | `LIMIT 10` | `LIMIT 10` |
| join text | `CONCAT(a, b)` (`\|\|` means OR by default) | `a + b` or `CONCAT(a, b)` | `a \|\| b` | `a \|\| b` | `a \|\| b` or `CONCAT` | `a \|\| b` or `concat` |
| `7 / 2` | 3.5000 | 3 | 3.5 | 3.5 | 3.5 (`DIV(7, 2)` is 3) | 3.5 (`7 div 2` is 3) |
| list in a group | `GROUP_CONCAT(x SEPARATOR ', ')` | `STRING_AGG(x, ', ')` | `LISTAGG(x, ', ')` | `LISTAGG(x, ', ')` | `STRING_AGG(x, ', ')` | `array_join(collect_list(x), ', ')` |
| NULL-safe equal | `a <=> b` | `IS NOT DISTINCT FROM` (2022+) | `DECODE(a, b, 1, 0) = 1` | `IS NOT DISTINCT FROM` | `IS NOT DISTINCT FROM` | `a <=> b` or `IS NOT DISTINCT FROM` |
| quote a name | `` `name` `` | `[name]` | `"NAME"` | `"NAME"` | `` `name` `` | `` `name` `` |
| `LIKE` and case | ignores case (default collation) | ignores case (default collation) | case-sensitive | case-sensitive; `ILIKE` | case-sensitive | case-sensitive; `ILIKE` |
| filter a window function | subquery | subquery | subquery | `QUALIFY` | `QUALIFY` | `QUALIFY` |

Two that surprise people: **Oracle treats an empty string `''` as NULL**, so `WHERE x = ''` never matches; and
**`7 / 2` is 3.5 in most databases but 3 in PostgreSQL, SQLite and SQL Server**, so a ratio of two integer counts
silently loses its fraction there.

### Dates { #others-dates }

| Task | MySQL 8 | SQL Server | Oracle | Snowflake | BigQuery | Databricks |
| --- | --- | --- | --- | --- | --- | --- |
| today | `CURRENT_DATE` | `CAST(GETDATE() AS DATE)` | `TRUNC(SYSDATE)` | `CURRENT_DATE` | `CURRENT_DATE()` | `current_date()` |
| add 7 days | `DATE_ADD(d, INTERVAL 7 DAY)` | `DATEADD(day, 7, d)` | `d + 7` | `DATEADD(day, 7, d)` | `DATE_ADD(d, INTERVAL 7 DAY)` | `date_add(d, 7)` |
| days between | `DATEDIFF(d2, d1)` | `DATEDIFF(day, d1, d2)` | `d2 - d1` | `DATEDIFF(day, d1, d2)` | `DATE_DIFF(d2, d1, DAY)` | `datediff(d2, d1)` |
| month number | `MONTH(d)` | `MONTH(d)` | `EXTRACT(MONTH FROM d)` | `MONTH(d)` | `EXTRACT(MONTH FROM d)` | `month(d)` |
| first of month | `DATE_FORMAT(d, '%Y-%m-01')` | `DATEFROMPARTS(YEAR(d), MONTH(d), 1)` | `TRUNC(d, 'MM')` | `DATE_TRUNC('month', d)` | `DATE_TRUNC(d, MONTH)` | `date_trunc('MONTH', d)` |

Note the argument order of "days between": MySQL and Databricks take (later, earlier), BigQuery
(later, earlier, unit); SQL Server and Snowflake take
(unit, earlier, later). PostgreSQL subtracts dates directly (`d2 - d1`), and SQLite uses
`julianday(d2) - julianday(d1)`.

### Changing data and keys { #others-changes }

| Task | MySQL 8 | SQL Server | Oracle | Snowflake | BigQuery | Databricks |
| --- | --- | --- | --- | --- | --- | --- |
| upsert | `INSERT ... ON DUPLICATE KEY UPDATE` | `MERGE` | `MERGE` | `MERGE` | `MERGE` | `MERGE INTO` |
| auto-numbered id | `AUTO_INCREMENT` | `IDENTITY(1, 1)` | `GENERATED AS IDENTITY` | `AUTOINCREMENT` / `IDENTITY` | none (`GENERATE_UUID()`) | `GENERATED ALWAYS AS IDENTITY` |
| table change inside a transaction | commits first | rolls back with it | commits first | commits first | not allowed in a transaction (except temporary tables) | one atomic write per statement |

For Databricks in depth, including its own functions and how they differ from the standard, see
[17. Databricks SQL vs standard SQL](../../data-engineering/databricks/17-Databricks-SQL-vs-Standard.md) in the
Databricks course.

## 28.4 Writing SQL that travels { #portable }

- Prefer the standard spellings: `COALESCE` (not `IFNULL`, `NVL`, `ISNULL`), `CASE` (not `IF`, `IIF`, `DECODE`),
  `CAST` (not `::`), `<>` (not `!=`, though most accept both), explicit `JOIN ... ON` (never commas with the join in
  `WHERE`).
- Single quotes for text, always. Double quotes only for names, and only when a name needs them.
- Write dates as `'YYYY-MM-DD'` text and compare with half-open ranges (`>= start AND < end`); keep date functions in
  one place (a CTE) so a port changes one line.
- Make division and rounding explicit: `* 1.0` before dividing integers, `ROUND(CAST(x AS NUMERIC), 2)` for money.
- Always `ORDER BY` with a tie-breaker, and `NULLS FIRST/LAST` when the column can be NULL.
- Do not lean on forgiving behaviour: an alias in `WHERE`, an ungrouped column, a text-to-number cast that "works".
- When the dialect is unknown (an interview whiteboard), say which one you are writing and name the one function
  that would change.

## 28.5 Summary { #summary }

- Most differences are syntax and fail loudly. The dangerous ones change results: casting, division by zero,
  `LIKE` and case, NULL sort order, rounding, invalid dates, an error inside a transaction.
- SQLite is forgiving, PostgreSQL strict: check on PostgreSQL when you can.
- Across products, dates, string aggregation, upserts, quoting and integer division are where queries need
  changing.

## Practice { #practice }

**28.1** This query runs on SQLite but fails on PostgreSQL. Fix it so it runs on both and returns the same rows.

```sql
SELECT category, COUNT(*) AS n, name
FROM products
GROUP BY category
HAVING n > 2;
```

??? success "Answer"
    Two problems: `name` is neither grouped nor aggregated (SQLite returns a name from some row of the group), and
    `HAVING` uses the alias `n`. Decide what the name should be (here, the first alphabetically), and repeat the
    aggregate.

    <!-- sql -->
    ```sql
    SELECT category, COUNT(*) AS n, MIN(name) AS first_name
    FROM products
    GROUP BY category
    HAVING COUNT(*) > 2
    ORDER BY category;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | category | n | first_name |
    | --- | --- | --- |
    | Home | 4 | Bookend |
    | Office | 4 | Fountain pen |
    <!-- /result -->

**28.2** A share of cancelled orders is computed as `SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) / COUNT(*)`
and comes out as 0. On which databases, why, and what is the fix?

??? success "Answer"
    On PostgreSQL, SQLite and SQL Server, where an integer divided by an integer is an integer: 2 / 20 is 0. Multiply
    by `1.0` first (or cast to a decimal type), then round:

    <!-- sql -->
    ```sql
    SELECT ROUND(SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 3) AS cancelled_share
    FROM orders;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | cancelled_share |
    | --- |
    | 0.100 |
    <!-- /result -->

    On MySQL, Oracle, Snowflake, BigQuery and Databricks the original already gives 0.1, because `/` returns a
    fraction there.

**28.3** Rewrite for SQL Server: `SELECT name FROM customers ORDER BY signup_date DESC LIMIT 3;`

??? success "Answer"
    `SELECT TOP (3) name FROM customers ORDER BY signup_date DESC;` or, in the standard form that SQL Server also
    accepts, `... ORDER BY signup_date DESC OFFSET 0 ROWS FETCH NEXT 3 ROWS ONLY;`. If two customers can share the
    third date, add a tie-breaker to the `ORDER BY` (or SQL Server's `TOP (3) WITH TIES` to return them all).

**28.4** Your query must return customers sorted by city, with customers without a city at the end, and must give
the same order on PostgreSQL and SQLite. Write it.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id, name, city
    FROM customers
    ORDER BY city NULLS LAST, customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

    | customer_id | name | city |
    | --- | --- | --- |
    | 2 | Ben Okafor | Lagos |
    | 10 | Ana Silva | Lisbon |
    | 8 | Hana Sato | Osaka |
    | 7 | Gus Novak | Prague |
    | 4 | Dana Kim | Seoul |
    | 3 | Chen Wei | Shanghai |
    | 1 | Ana Silva | Toronto |
    | 6 | Farah Haddad | Toronto |
    | 9 | Ivan Petrov | Toronto |
    | 5 | Eli Cohen | *NULL* |
    <!-- /result -->

    Without `NULLS LAST`, Eli (no city) would be last on PostgreSQL and first on SQLite. `customer_id` breaks the tie
    between the three Toronto customers.

**Next:** [29. Safe SQL](29-Safe-SQL.md).
