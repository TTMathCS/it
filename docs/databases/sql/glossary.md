# Glossary

*The terms used in this course, in alphabetical order, each with a one- or two-line meaning and the chapter where
it is explained. Interviewers often use these words without explaining them.*

## A to C { #a-c }

| Term | Meaning | See |
| --- | --- | --- |
| ACID | The four promises of a transaction: atomicity, consistency, isolation, durability. | [20.2](20-Transactions-and-Isolation.md#acid) |
| Aggregate function | A function that turns many rows into one value: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`. | [7](07-Aggregation-Group-By-Having.md#aggregates) |
| Alias | A new name for a column or table in one query (`AS total`). | [2](02-Select-Where-Order-By-Limit.md#aliases) |
| Anti-join | Rows of one table with **no** match in another (`NOT EXISTS`, `LEFT JOIN ... IS NULL`). | [9](09-Self-Semi-and-Anti-Joins.md#anti) |
| Autocommit | Each statement is its own transaction, committed when it finishes. | [20](20-Transactions-and-Isolation.md#autocommit) |
| B-tree | The usual kind of index: a shallow tree of sorted pages. | [25](25-Indexes-and-Explain.md#b-tree) |
| Bitmap scan | PostgreSQL's way of reading many rows found through an index: mark the pages, then read each page once. | [25](25-Indexes-and-Explain.md#b-tree) |
| Bronze, silver, gold | The medallion layers of a lakehouse: raw data, cleaned data, data ready for reports. | [24](24-JSON-and-Arrays.md#design), Databricks course |
| Cardinality | The number of distinct values in a column; also "one-to-many" and similar descriptions of a relationship. | [1](01-Tables-Rows-and-Keys.md#relationships) |
| CASE | SQL's if-then-else expression. | [4](04-Expressions-Case-Numbers-Dates-Cast.md#case) |
| CAST | Converting a value to another type. | [4](04-Expressions-Case-Numbers-Dates-Cast.md#cast) |
| CDC | Change data capture: reading a database's log to get every insert, update and delete as an event. | [22](22-Duplicates-and-Incremental-Loads.md#change-detection) |
| Check constraint | A rule each row must pass (`CHECK (price > 0)`). | [18](18-Create-Table-Types-Constraints.md#constraints) |
| Clustered index | The table stored in the order of one key; a database has at most one per table. | [25](25-Indexes-and-Explain.md#summary) |
| COALESCE | The first non-NULL of its arguments. | [4](04-Expressions-Case-Numbers-Dates-Cast.md#coalesce-nullif) |
| COMMIT, ROLLBACK | `COMMIT` makes a transaction's changes permanent; `ROLLBACK` throws them all away. | [20.1](20-Transactions-and-Isolation.md#begin) |
| Composite key | A key made of several columns. | [1](01-Tables-Rows-and-Keys.md#composite-key) |
| Conformed dimension | One dimension table shared by several fact tables, so their results line up side by side. | [19](19-Data-Modelling.md) |
| Correlated subquery | A subquery that refers to the outer row, so it can run once per row. | [10](10-Subqueries.md#correlated), [26](26-Making-Slow-Queries-Fast.md) |
| Covering index | An index holding every column a query needs, so the table is not read. | [25](25-Indexes-and-Explain.md#covering) |
| Cross join | Every row of one table paired with every row of another. | [8](08-Joins-Inner-Left-Right-Full-Cross.md#cross) |
| CTE | Common table expression: a named step of a query, written with `WITH`. | [11](11-CTEs-and-Recursive-CTEs.md#with) |
| CUBE | Grouping by every combination of the listed columns. | [27](27-Grouping-Sets-Rollup-Cube-Lateral.md#cube) |

## D to I { #d-i }

| Term | Meaning | See |
| --- | --- | --- |
| date_trunc | Cuts a date or timestamp down to the start of its month, week, day and so on, for grouping by period. | [16.3](16-Dates-and-Time-Series.md#truncate) |
| DDL, DML, DCL, TCL | Families of statements: defining tables, changing data, granting rights, controlling transactions. | [1](01-Tables-Rows-and-Keys.md#statement-families) |
| Deadlock | Two transactions each waiting for a lock the other holds; the database cancels one. | [20](20-Transactions-and-Isolation.md#deadlock) |
| DECIMAL, NUMERIC | Exact numbers with a fixed count of digits (`NUMERIC(8,2)`); use them for money, not floating point. | [4](04-Expressions-Case-Numbers-Dates-Cast.md) |
| Derived table | A subquery in `FROM`. | [10](10-Subqueries.md#derived) |
| Dialect | One database's version of SQL. | [28](28-Dialect-Differences.md) |
| Dimension table | A table describing the who, what, where of facts (customers, products, dates). | [19](19-Data-Modelling.md#star) |
| Dirty read | Seeing another transaction's change before it commits. | [20](20-Transactions-and-Isolation.md#isolation) |
| ETL, ELT | Extract, transform, load: the order in which a pipeline cleans data; ELT loads first and transforms inside the warehouse. | [22](22-Duplicates-and-Incremental-Loads.md) |
| EXPLAIN | Shows the plan the database chose for a query; `EXPLAIN ANALYZE` also runs it. | [25](25-Indexes-and-Explain.md#seq-scan) |
| Fact table | A table of events or measurements (sales lines) with keys to dimensions. | [19](19-Data-Modelling.md#star) |
| Fan-out | A join that multiplies rows, so sums count things more than once. | [8](08-Joins-Inner-Left-Right-Full-Cross.md#fan-out) |
| FILTER | A condition attached to one aggregate: `COUNT(*) FILTER (WHERE ...)`. | [27](27-Grouping-Sets-Rollup-Cube-Lateral.md#filter) |
| Foreign key | A column whose values must exist as a key in another table. | [1](01-Tables-Rows-and-Keys.md#foreign-key) |
| Frame | The rows a window function looks at around the current row (`ROWS BETWEEN ...`). | [14](14-Window-Functions-Lag-Lead-Running-Totals.md#frames) |
| Full load | Copying the whole source every time. | [22](22-Duplicates-and-Incremental-Loads.md#incremental) |
| Gaps and islands | Finding runs of consecutive values (days in a row) and the gaps between them. | [15](15-Classic-Interview-Patterns.md#islands) |
| Grain | What one row of a fact table means: "one row per order line". | [19](19-Data-Modelling.md#grain) |
| GROUPING SETS | Several groupings in one query. | [27](27-Grouping-Sets-Rollup-Cube-Lateral.md#cube) |
| Hash join | A join that builds a hash table of the smaller input. | [25](25-Indexes-and-Explain.md#join-algorithms) |
| HAVING | A filter on groups, run after `GROUP BY`; `WHERE` filters rows before grouping. | [7.5](07-Aggregation-Group-By-Having.md#having) |
| Idempotent | Safe to run twice: the second run changes nothing. | [22](22-Duplicates-and-Incremental-Loads.md#idempotent) |
| Identifier | The name of a table, column or alias. Written bare (`order_date`), or in **double** quotes when it has spaces, capitals or a reserved word (`"Full name"`). | [2.3](02-Select-Where-Order-By-Limit.md#double-quotes) |
| Incremental load | Copying only what changed since the last load. | [22](22-Duplicates-and-Incremental-Loads.md#incremental) |
| Index | A sorted structure of column values with pointers to rows, for fast lookups. | [25](25-Indexes-and-Explain.md#b-tree) |
| Inner join | Keeps only the pairs of rows that match on the join condition; rows with no match on either side drop out. | [8.1](08-Joins-Inner-Left-Right-Full-Cross.md#inner) |
| Isolation level | How much a transaction sees of others running at the same time. | [20](20-Transactions-and-Isolation.md#isolation) |

## J to R { #j-r }

| Term | Meaning | See |
| --- | --- | --- |
| JSONB | PostgreSQL's parsed, indexable JSON type. | [24](24-JSON-and-Arrays.md#storing) |
| LAG, LEAD | Window functions reading the previous or next row. | [14](14-Window-Functions-Lag-Lead-Running-Totals.md#lag-lead) |
| LATERAL | A subquery in `FROM` that can use the rows to its left. | [27](27-Grouping-Sets-Rollup-Cube-Lateral.md#lateral) |
| Left join | Keeps every row of the left table; where the right table has no match, its columns are NULL. | [8.2](08-Joins-Inner-Left-Right-Full-Cross.md#left) |
| Lost update | Two read-then-write transactions where the second overwrites the first. | [20](20-Transactions-and-Isolation.md#lost-update) |
| Many-to-many | A relationship where each row on both sides can link to many on the other (students and courses); it needs a junction table holding one row per pair. | [1.5](01-Tables-Rows-and-Keys.md#relationships) |
| Materialized view | A view whose result is stored and refreshed on demand. | [21](21-Views-and-Materialized-Views.md#materialized) |
| MERGE | One statement that inserts, updates or deletes depending on a match. | [17](17-Insert-Update-Delete-Merge.md#merge) |
| Moving average | The average over a sliding set of rows, such as the last 3 days, done with a window frame. | [14.5](14-Window-Functions-Lag-Lead-Running-Totals.md#moving) |
| MVCC | Multi-version concurrency control: readers see a snapshot while writers make new row versions. | [20](20-Transactions-and-Isolation.md#mvcc) |
| Natural key | A key that means something outside the database (an email, a product code). | [19](19-Data-Modelling.md#star) |
| Nested loop | A join that looks up matches in the inner input for each outer row. | [25](25-Indexes-and-Explain.md#join-algorithms) |
| Non-repeatable read | Reading the same row twice in one transaction and getting different values, because another transaction committed in between. | [20](20-Transactions-and-Isolation.md#isolation) |
| Normal forms | Rules for storing each fact once (1NF, 2NF, 3NF). | [19](19-Data-Modelling.md#normal-forms) |
| NULL | "No value" or "unknown"; comparisons with it are UNKNOWN. | [6](06-Null-and-Three-Valued-Logic.md#meaning) |
| OLTP, OLAP | Systems for many small transactions versus systems for large analytic queries. | [19](19-Data-Modelling.md#oltp-olap) |
| One big table (OBT) | A single wide table with the facts and their dimension columns already joined in, so reports need no joins. | [19](19-Data-Modelling.md) |
| One-to-many | A relationship where one row (a customer) has many rows on the other side (orders); the foreign key sits on the many side. | [1.5](01-Tables-Rows-and-Keys.md#relationships) |
| One-to-one | A relationship where each row has at most one row on the other side (a customer and a profile); made with a foreign key that is also unique or the primary key. A join over it never adds rows. | [1.5](01-Tables-Rows-and-Keys.md#one-to-one) |
| Partition (window) | The group a window function works within (`PARTITION BY`). | [13](13-Window-Functions-Ranking.md#aggregate-windows) |
| Partitioning (table) | Storing a big table in parts by a column such as date, so filters skip parts. | [25](25-Indexes-and-Explain.md#index-types) |
| Phantom | New rows appearing when the same query runs again in one transaction. | [20](20-Transactions-and-Isolation.md#isolation) |
| Pivot | Turning values of a column into columns. | [27](27-Grouping-Sets-Rollup-Cube-Lateral.md#pivot), [15](15-Classic-Interview-Patterns.md#pivot) |
| Primary key | The column(s) that identify each row; unique and not NULL. | [1](01-Tables-Rows-and-Keys.md#primary-key) |
| Query plan | The steps the database chose to run a query. | [25](25-Indexes-and-Explain.md) |
| Read committed, repeatable read | Two isolation levels: read committed lets each statement see the latest commits; repeatable read keeps one snapshot for the whole transaction. | [20](20-Transactions-and-Isolation.md#read-committed) |
| Reconciliation | Checking that two copies of data agree (row counts, totals, keys only on one side) after a load. | [23.9](23-Data-Quality-Checks.md#reconcile) |
| Recursive CTE | A CTE that refers to itself, for hierarchies and sequences. | [11](11-CTEs-and-Recursive-CTEs.md#recursive) |
| Reserved word | A word SQL itself uses (`order`, `group`, `user`, `select`); as a name it needs double quotes, so better to pick another name. | [2.3](02-Select-Where-Order-By-Limit.md#double-quotes) |
| ROLLUP | Subtotals along a hierarchy, and a grand total. | [27](27-Grouping-Sets-Rollup-Cube-Lateral.md#rollup) |
| Row-level security | Policies that limit which rows a role can see or change. | [29](29-Safe-SQL.md#rls) |
| ROW_NUMBER, RANK, DENSE_RANK | Ranking window functions that differ on ties: 1,2,3,4 / 1,1,3,4 / 1,1,2,3. | [13.3](13-Window-Functions-Ranking.md#ties) |
| Running total | A sum that grows row by row in order (`SUM(x) OVER (ORDER BY ...)`). | [14.3](14-Window-Functions-Lag-Lead-Running-Totals.md#running) |

## S to Z { #s-z }

| Term | Meaning | See |
| --- | --- | --- |
| Sargable | A condition that can use an index: the column is not wrapped in a calculation. | [25](25-Indexes-and-Explain.md#sargable) |
| Savepoint | A bookmark inside a transaction to roll back to. | [20](20-Transactions-and-Isolation.md#savepoint) |
| SCD | Slowly changing dimension: type 1 overwrites, type 2 keeps every version with dates. | [19](19-Data-Modelling.md#scd), [22](22-Duplicates-and-Incremental-Loads.md#scd2) |
| Selectivity | The share of rows a condition keeps; an index helps when it is small. | [25](25-Indexes-and-Explain.md#selectivity) |
| Self join | A table joined to itself. | [9](09-Self-Semi-and-Anti-Joins.md#self) |
| Semi-join | Rows of one table with **at least one** match in another (`EXISTS`, `IN`). | [9](09-Self-Semi-and-Anti-Joins.md#semi) |
| Seq scan | Reading the whole table. | [25](25-Indexes-and-Explain.md#seq-scan) |
| Serializable | The strictest isolation level: the result equals some one-at-a-time order. | [20](20-Transactions-and-Isolation.md#write-skew) |
| Set operations | `UNION`, `INTERSECT`, `EXCEPT`: combining results row by row. | [12](12-Set-Operations.md#union) |
| Snowflake schema | A star schema whose dimensions are split into further tables (product, then category), so more joins. | [19](19-Data-Modelling.md) |
| SQL injection | Input pasted into SQL text that changes the query. | [29](29-Safe-SQL.md#injection) |
| Staging table | Where raw data lands, often as text, before checks and loading. | [23](23-Data-Quality-Checks.md#batch) |
| Star schema | A fact table in the middle, joined to dimension tables around it. | [19](19-Data-Modelling.md#star) |
| String literal | A piece of text written in a query, in **single** quotes: `'Toronto'`. A quote inside it is doubled: `'O''Brien'`. | [2.3](02-Select-Where-Order-By-Limit.md#quotes) |
| Subquery | A query inside another query, in `WHERE`, `FROM` or `SELECT`. | [10](10-Subqueries.md) |
| Surrogate key | A meaningless number used as a key, instead of a natural key. | [19](19-Data-Modelling.md#star) |
| Three-valued logic | TRUE, FALSE and UNKNOWN, the result of comparing with NULL. | [6](06-Null-and-Three-Valued-Logic.md#three-valued) |
| Top N per group | Picking the first few rows in each group, usually rank with `ROW_NUMBER` in a CTE, then filter outside. | [13.4](13-Window-Functions-Ranking.md#top-n) |
| Transaction | Statements that happen together or not at all. | [20](20-Transactions-and-Isolation.md#begin) |
| Upsert | Insert a row, or update it if its key already exists. | [17](17-Insert-Update-Delete-Merge.md#upsert) |
| View | A saved query used like a table. | [21](21-Views-and-Materialized-Views.md#create-view) |
| Watermark | The point (usually a timestamp) up to which data has been loaded. | [22](22-Duplicates-and-Incremental-Loads.md#incremental) |
| Window function | A calculation over related rows that keeps every row (`... OVER (...)`). | [13](13-Window-Functions-Ranking.md#aggregate-windows) |
| Write skew | Two transactions each make a valid change based on the same read, and together break a rule. | [20](20-Transactions-and-Isolation.md#write-skew) |
