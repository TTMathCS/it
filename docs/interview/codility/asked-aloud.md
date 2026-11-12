# Asked aloud: 30 SQL and pipeline questions

Not every question comes as a task to code. An interviewer may also ask out loud, and you answer in a
sentence or two. Here are 30 of those, from SQL basics to loads and data modelling. Say your answer first,
then open the box.

!!! note "How the examples were checked"
    Every SQL example ran on **SQLite 3.54** (Python's `sqlite3` module), one after another on one
    connection, against the small tables at the end of this page; the output shown is what came back. They
    were not run on PostgreSQL. Questions 23 to 27 have no example: say the answer.

## 1. What is the difference between WHERE and HAVING?

??? success "Answer (open after you try)"

    WHERE filters single rows before they are grouped, so it cannot use SUM or COUNT. HAVING filters whole groups after GROUP BY, so it can. Put a row condition in WHERE even when you also have a HAVING: fewer rows reach the grouping.

    ```sql
    SELECT dept, SUM(salary) AS total FROM emp
    WHERE salary >= 70 GROUP BY dept HAVING SUM(salary) > 100;
    ```

    Output:

    ```
    dept | total
    IT | 250
    ```

## 2. Why can't I use a SELECT alias in WHERE?

??? success "Answer (open after you try)"

    A query runs in a different order from how it is written: FROM and joins, WHERE, GROUP BY, HAVING, SELECT, then ORDER BY and LIMIT. The alias is made in SELECT, after WHERE has already run, so standard SQL does not know it there; ORDER BY comes later and can use it. SQLite and a few others are lenient, so do not rely on that in an interview: repeat the expression or wrap the query in a CTE.

    ```sql
    WITH t AS (SELECT name, salary * 12 AS yearly FROM emp)
    SELECT name, yearly FROM t WHERE yearly > 1000 ORDER BY yearly DESC, name;
    ```

    Output:

    ```
    name | yearly
    Ana | 1080
    Ben | 1080
    ```

## 3. COUNT(*), COUNT(column) and COUNT(DISTINCT column): what is the difference?

??? success "Answer (open after you try)"

    COUNT(*) counts rows. COUNT(column) counts rows where that column is not NULL. COUNT(DISTINCT column) counts the different non-NULL values. A gap between the first two tells you how many NULLs there are.

    ```sql
    SELECT COUNT(*), COUNT(dept), COUNT(DISTINCT dept) FROM emp;
    ```

    Output:

    ```
    COUNT(*) | COUNT(dept) | COUNT(DISTINCT dept)
    6 | 5 | 2
    ```

## 4. Why does NULL = NULL not return true, and what is the NOT IN trap?

??? success "Answer (open after you try)"

    NULL means unknown, so comparing it with anything, even another NULL, gives unknown, and WHERE keeps only true. Test with IS NULL or IS NOT NULL. The trap: `x NOT IN (list)` returns no rows at all when the list holds a NULL, because `x <> NULL` is never true. Use NOT EXISTS instead.

    ```sql
    SELECT (SELECT COUNT(*) FROM cust WHERE id NOT IN (SELECT cust_id FROM orders)) AS not_in,
           (SELECT COUNT(*) FROM cust c WHERE NOT EXISTS
              (SELECT 1 FROM orders o WHERE o.cust_id = c.id)) AS not_exists;
    ```

    Output:

    ```
    not_in | not_exists
    0 | 1
    ```

    Cy has no orders, but NOT IN finds nobody because order 13 has a NULL cust_id.

## 5. My LEFT JOIN lost rows from the left table. Why?

??? success "Answer (open after you try)"

    Almost always a condition on the right-hand table sits in WHERE. For a left row with no match the right columns are NULL, the WHERE test is not true, and the row is dropped, so the LEFT JOIN behaves like an INNER JOIN. Move that condition into ON, or allow NULL in WHERE if that is what you mean.

    ```sql
    SELECT 'where' AS put_in, COUNT(*) FROM cust c LEFT JOIN orders o ON o.cust_id = c.id WHERE o.status = 'paid'
    UNION ALL
    SELECT 'on', COUNT(*) FROM cust c LEFT JOIN orders o ON o.cust_id = c.id AND o.status = 'paid';
    ```

    Output:

    ```
    put_in | COUNT(*)
    where | 1
    on | 3
    ```

    With the test in WHERE only Ana is left; in ON all three customers stay, Ben and Cy with NULLs.

## 6. Why did my join double the totals?

??? success "Answer (open after you try)"

    A join gives one output row per matching pair, so if the right table has several rows per key each left row is repeated, and a SUM over the left table's numbers counts them again (fan-out). Check the grain of both sides before joining: aggregate the many side to one row per key first, then join.

    ```sql
    SELECT SUM(o.amount) AS wrong FROM orders o JOIN pay p ON p.cust_id = o.cust_id;
    SELECT SUM(amount) AS right FROM orders WHERE cust_id IN (SELECT cust_id FROM pay);
    ```

    Output:

    ```
    wrong
    160
    right
    80
    ```

    Ana's orders add up to 80, but each one met two payment rows.

## 7. How do you find customers who never placed an order?

??? success "Answer (open after you try)"

    That is an anti-join. NOT EXISTS is the safest form: it handles NULLs correctly and stops at the first match. LEFT JOIN and then `WHERE right_key IS NULL` also works; avoid NOT IN because of NULLs.

    ```sql
    SELECT c.name FROM cust c LEFT JOIN orders o ON o.cust_id = c.id
    WHERE o.id IS NULL;
    ```

    Output:

    ```
    name
    Cy
    ```

## 8. UNION or UNION ALL?

??? success "Answer (open after you try)"

    UNION ALL stacks the two results as they are. UNION also removes duplicate rows, which costs a sort or hash over the whole result. Use UNION ALL unless you really need the duplicates gone, and say why when you do.

    ```sql
    SELECT (SELECT COUNT(*) FROM (SELECT status FROM orders UNION SELECT status FROM orders)) AS u,
           (SELECT COUNT(*) FROM (SELECT status FROM orders UNION ALL SELECT status FROM orders)) AS ua;
    ```

    Output:

    ```
    u | ua
    2 | 8
    ```

## 9. ROW_NUMBER, RANK and DENSE_RANK: how do they differ?

??? success "Answer (open after you try)"

    All three number rows in the window's order. ROW_NUMBER gives 1, 2, 3 even on ties (which tied row comes first is arbitrary unless you add a tie breaker). RANK gives ties the same number and then skips: 1, 1, 3. DENSE_RANK gives ties the same number with no gap: 1, 1, 2.

    ```sql
    SELECT name, salary, ROW_NUMBER() OVER (ORDER BY salary DESC, name) AS rn,
      RANK() OVER (ORDER BY salary DESC) AS rnk, DENSE_RANK() OVER (ORDER BY salary DESC) AS drk
    FROM emp WHERE salary IS NOT NULL ORDER BY salary DESC, name;
    ```

    Output:

    ```
    name | salary | rn | rnk | drk
    Ana | 90 | 1 | 1 | 1
    Ben | 90 | 2 | 1 | 1
    Dee | 80 | 3 | 3 | 2
    Cy | 70 | 4 | 4 | 3
    Eli | 60 | 5 | 5 | 4
    ```

## 10. How do you get the second-highest salary?

??? success "Answer (open after you try)"

    Rank the distinct salary levels with DENSE_RANK and keep level 2, which also works for any N and returns nothing when there is no second level. For N = 2 only, the largest salary below the maximum is fine too. ROW_NUMBER is wrong here: with two people on the top salary it returns the top salary again.

    ```sql
    WITH l AS (SELECT DISTINCT salary, DENSE_RANK() OVER (ORDER BY salary DESC) AS dr
               FROM emp WHERE salary IS NOT NULL)
    SELECT salary AS second_highest FROM l WHERE dr = 2;
    ```

    Output:

    ```
    second_highest
    80
    ```

## 11. How do you get the top earner in each department?

??? success "Answer (open after you try)"

    Number or rank the rows inside each department with `PARTITION BY dept` in a CTE, then filter outside it, because a window function cannot go in WHERE. Use RANK if ties should all appear, ROW_NUMBER if you need exactly one.

    ```sql
    WITH r AS (SELECT dept, name, salary, RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS rk
               FROM emp WHERE dept IS NOT NULL)
    SELECT dept, name, salary FROM r WHERE rk = 1 ORDER BY dept, name;
    ```

    Output:

    ```
    dept | name | salary
    IT | Ana | 90
    IT | Ben | 90
    Ops | Dee | 80
    ```

## 12. What is the difference between a window function and GROUP BY?

??? success "Answer (open after you try)"

    GROUP BY folds each group into one row. A window function computes over a group of rows but keeps every row, so you can show a row's value next to its group's total, rank or average.

    ```sql
    SELECT name, dept, salary, SUM(salary) OVER (PARTITION BY dept) AS dept_total
    FROM emp WHERE dept IS NOT NULL ORDER BY dept, name;
    ```

    Output:

    ```
    name | dept | salary | dept_total
    Ana | IT | 90 | 250
    Ben | IT | 90 | 250
    Cy | IT | 70 | 250
    Dee | Ops | 80 | 140
    Eli | Ops | 60 | 140
    ```

## 13. How do you compare each row with the previous one?

??? success "Answer (open after you try)"

    LAG(column) OVER (ORDER BY ...) reads the value from the row before, inside the same partition, and LEAD reads the next one. The first row gets NULL, or a default you pass as the third argument.

    ```sql
    SELECT day, amount, amount - LAG(amount) OVER (PARTITION BY cust_id ORDER BY day) AS change
    FROM sales ORDER BY day;
    ```

    Output:

    ```
    day | amount | change
    2026-01-10 | 100 | NULL
    2026-03-01 | 200 | 100
    ```

## 14. How do you write a running total, and why do ROWS and RANGE matter?

??? success "Answer (open after you try)"

    SUM(x) OVER (ORDER BY ...) gives a running total. With an ORDER BY the default frame is RANGE up to the current row, which treats all rows tied on the order column as one step, so tied rows show the same total. Write `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` when you want it to grow row by row.

    ```sql
    SELECT name, salary, SUM(salary) OVER (ORDER BY salary DESC) AS by_range,
      SUM(salary) OVER (ORDER BY salary DESC, name ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS by_rows
    FROM emp WHERE dept = 'IT' ORDER BY salary DESC, name;
    ```

    Output:

    ```
    name | salary | by_range | by_rows
    Ana | 90 | 180 | 90
    Ben | 90 | 180 | 180
    Cy | 70 | 250 | 250
    ```

## 15. How do you find streaks of consecutive days?

??? success "Answer (open after you try)"

    This is gaps and islands. Take the distinct days, subtract each day's ROW_NUMBER from its date: within a streak both rise by one, so the difference stays the same and becomes the streak's label. Group by that label.

    ```sql
    WITH d AS (SELECT DISTINCT cust_id, day FROM logins),
    g AS (SELECT cust_id, day, julianday(day) - ROW_NUMBER() OVER (PARTITION BY cust_id ORDER BY day) AS grp FROM d)
    SELECT cust_id, MIN(day) AS start, MAX(day) AS finish, COUNT(*) AS days FROM g GROUP BY cust_id, grp ORDER BY start;
    ```

    Output:

    ```
    cust_id | start | finish | days
    1 | 2026-03-01 | 2026-03-03 | 3
    1 | 2026-03-05 | 2026-03-06 | 2
    ```

## 16. What is a CTE, and when would you use one instead of a subquery or a temporary table?

??? success "Answer (open after you try)"

    A CTE (`WITH name AS (...)`) is a named subquery that lives only for one statement. It reads top to bottom, can be used more than once in that statement, and can be recursive. It is about readability, not speed; a temporary table is better when a big middle result is reused by several statements or needs an index.

    ```sql
    WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 5)
    SELECT group_concat(i) FROM n;
    ```

    Output:

    ```
    group_concat(i)
    1,2,3,4,5
    ```

## 17. How do you turn rows into columns (a pivot)?

??? success "Answer (open after you try)"

    Group by the row label and write one `SUM(CASE WHEN ... THEN value END)` (or COUNT) per wanted column. It works on every database; some also have a PIVOT keyword, but the CASE form is what interviewers expect.

    ```sql
    SELECT dept, SUM(CASE WHEN salary >= 80 THEN 1 ELSE 0 END) AS high,
      SUM(CASE WHEN salary < 80 THEN 1 ELSE 0 END) AS low FROM emp WHERE dept IS NOT NULL GROUP BY dept;
    ```

    Output:

    ```
    dept | high | low
    IT | 2 | 1
    Ops | 1 | 1
    ```

## 18. How do you find duplicate rows?

??? success "Answer (open after you try)"

    First agree what a duplicate is: equal in every column, or equal on the key that should be unique. Then group by those columns and keep the groups with `HAVING COUNT(*) > 1`. To see the full rows rather than one per group, use `COUNT(*) OVER (PARTITION BY ...)` and filter on it.

    ```sql
    SELECT cust_id, city, updated_at, COUNT(*) AS copies FROM raw
    GROUP BY cust_id, city, updated_at HAVING COUNT(*) > 1;
    ```

    Output:

    ```
    cust_id | city | updated_at | copies
    2 | Lagos | 2026-05-02 | 2
    ```

## 19. How do you keep only the newest row for each key?

??? success "Answer (open after you try)"

    `ROW_NUMBER() OVER (PARTITION BY key ORDER BY updated_at DESC, tie_breaker)` and keep row 1. Do not take MAX of each column separately: the result can mix values from different rows into a row that never existed.

    ```sql
    WITH r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY cust_id ORDER BY updated_at DESC, city) AS rn FROM raw)
    SELECT cust_id, city, updated_at FROM r WHERE rn = 1 ORDER BY cust_id;
    ```

    Output:

    ```
    cust_id | city | updated_at
    1 | Ottawa | 2026-05-03
    2 | Lagos | 2026-05-02
    ```

## 20. How do you delete exact duplicates when the table has no key?

??? success "Answer (open after you try)"

    Use the database's hidden row id (`rowid` in SQLite, `ctid` in PostgreSQL): keep the smallest id of each group and delete the rest. Or rebuild the table from `SELECT DISTINCT` inside one transaction. Then add the missing primary key or unique constraint so they do not come back.

    ```sql
    DELETE FROM raw WHERE rowid NOT IN (SELECT MIN(rowid) FROM raw GROUP BY cust_id, city, updated_at);
    SELECT COUNT(*) AS rows_left FROM raw;
    ```

    Output:

    ```
    rows_left
    3
    ```

    Runs after the previous two examples; 4 rows before, the two Lagos rows were the same.

## 21. What is an idempotent load?

??? success "Answer (open after you try)"

    One you can run twice, or rerun after it failed half way, and end with the same data as one clean run. You get it by upserting or merging on a key, or by deleting the batch or partition and inserting it again in one transaction, and by moving the watermark only after the data has committed. A plain INSERT is not idempotent.

    ```sql
    WITH r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY cust_id ORDER BY updated_at DESC) AS rn FROM raw)
    INSERT INTO target SELECT cust_id, city, updated_at FROM r WHERE rn = 1
    ON CONFLICT(cust_id) DO UPDATE SET city = excluded.city, updated_at = excluded.updated_at
    WHERE excluded.updated_at > target.updated_at;
    ```

    Output:

    ```
    (no rows returned: the statement ran)
    ```

    Ran this statement twice on purpose; the check below gives the same rows either way.

## 22. What is an upsert or MERGE, and what does "newer wins" mean?

??? success "Answer (open after you try)"

    An upsert inserts a row when its key is new and updates the existing row when it is not, in one statement (`MERGE` in PostgreSQL 15+, Snowflake and Databricks; `INSERT ... ON CONFLICT` in PostgreSQL and SQLite). "Newer wins" adds a condition so an older copy that arrives late never overwrites a newer one. The source batch must have one row per key first, or the merge fails or picks one at random.

    ```sql
    SELECT * FROM target ORDER BY cust_id;
    ```

    Output:

    ```
    cust_id | city | updated_at
    1 | Ottawa | 2026-05-03
    2 | Lagos | 2026-05-02
    ```

    The target after the upsert above, run twice: Ana has the newest city, Ottawa.

## 23. Full load or incremental load, and what is a watermark?

??? success "Answer (open after you try)"

    A full load copies the whole source each time: simple, catches deletes and fixes, but gets slower as the table grows. An incremental load copies only rows changed since the last run, found with a watermark: the largest `updated_at` (or id) already loaded. It is fast but needs a trustworthy change column, and misses deletes; many teams run incremental daily plus a full reload or reconciliation now and then.

## 24. What is late-arriving data, and how do you handle it?

??? success "Answer (open after you try)"

    Rows that reach you after you have already loaded their time period, often with an old timestamp, so a watermark on that timestamp skips them for good. Fix it by reading back a window past the watermark (for example the last three days) with an idempotent upsert, or by keeping the watermark on arrival time instead of event time. For facts whose dimension row has not arrived yet, point them at an "unknown" member instead of dropping them.

## 25. How do you detect rows deleted in the source?

??? success "Answer (open after you try)"

    An incremental read cannot see a row that is gone. Compare the full list of source keys with the target (anti-join), read deletes from change data capture (CDC: the database's change log, for example with Debezium), or ask the source for soft deletes with an `is_deleted` flag. In the target, marking a row deleted is usually better than removing it.

## 26. What is a star schema, and how do facts and dimensions differ?

??? success "Answer (open after you try)"

    A fact table in the middle holds events or measurements (one order line, one payment), with numbers to add up and keys to the dimensions. The dimension tables around it describe who, what, where and when, with the attributes you filter and group by. A snowflake schema normalises the dimensions into sub-tables; a star keeps each one flat for simpler, faster queries.

## 27. What is the grain of a fact table?

??? success "Answer (open after you try)"

    What exactly one row represents, for example one line of one order. Decide it first, because every number in the table must be true at that grain. Putting an order-level number such as shipping on each line means it is summed once per line.

## 28. Explain SCD type 1, 2 and 3. How do you join facts to a type 2 dimension?

??? success "Answer (open after you try)"

    Type 1 overwrites the old value, so history is lost. Type 2 closes the old row and adds a new one, with its own surrogate key and `valid_from` / `valid_to` dates, so every past fact keeps the value of its time. Type 3 keeps only the previous value in an extra column. Join type 2 on the business key with a half-open range, `valid_from <= event_date AND event_date < valid_to`, or store the version's surrogate key in the fact when you load it.

    ```sql
    SELECT s.day, d.city FROM sales s JOIN dim_cust d ON d.cust_id = s.cust_id
     AND d.valid_from <= s.day AND s.day < d.valid_to ORDER BY s.day;
    ```

    Output:

    ```
    day | city
    2026-01-10 | Toronto
    2026-03-01 | Vancouver
    ```

## 29. What does an index cost, and why might the database ignore it?

??? success "Answer (open after you try)"

    An index is a separate sorted copy of some columns with pointers to the rows, so lookups, ranges and sorts avoid a full scan. It costs disk and memory, and every insert, delete and update of those columns must change it too, so writes and bulk loads get slower. It goes unused when too many rows match, when the column is wrapped in a function or calculation, or when the query skips the index's first column; `EXPLAIN` shows which.

    ```sql
    CREATE INDEX ix_sales_day ON sales(day);
    EXPLAIN QUERY PLAN SELECT * FROM sales WHERE day >= '2026-02-01';
    EXPLAIN QUERY PLAN SELECT * FROM sales WHERE substr(day, 1, 7) = '2026-03';
    ```

    Output:

    ```
    id | parent | notused | detail
    3 | 0 | 205 | SEARCH sales USING INDEX ix_sales_day (day>?)
    id | parent | notused | detail
    2 | 0 | 216 | SCAN sales
    ```

## 30. How do you turn a JSON array inside a column into rows?

??? success "Answer (open after you try)"

    Join each row to a function that returns one row per array element: `json_each` in SQLite, `jsonb_array_elements` with LATERAL in PostgreSQL, `explode` in Spark and Databricks. Use a left join if rows with an empty array must stay. `->` returns JSON you can keep walking into, `->>` returns a plain value.

    ```sql
    SELECT e.body ->> '$.user' AS usr, t.value AS tag
    FROM events e LEFT JOIN json_each(e.body, '$.tags') t ORDER BY e.id, t.value;
    ```

    Output:

    ```
    usr | tag
    ana | a
    ana | b
    ben | NULL
    ```

## The tables the examples ran on

```sql
CREATE TABLE emp (id INTEGER PRIMARY KEY, name TEXT, dept TEXT, salary INT);
INSERT INTO emp VALUES (1,'Ana','IT',90),(2,'Ben','IT',90),(3,'Cy','IT',70),
  (4,'Dee','Ops',80),(5,'Eli','Ops',60),(6,'Fay',NULL,NULL);
CREATE TABLE cust (id INTEGER PRIMARY KEY, name TEXT);
INSERT INTO cust VALUES (1,'Ana'),(2,'Ben'),(3,'Cy');
CREATE TABLE orders (id INTEGER PRIMARY KEY, cust_id INT, amount INT, status TEXT);
INSERT INTO orders VALUES (10,1,50,'paid'),(11,1,30,'void'),(12,2,20,'void'),(13,NULL,40,'paid');
CREATE TABLE pay (cust_id INT, amount INT);
INSERT INTO pay VALUES (1,5),(1,5);
CREATE TABLE logins (cust_id INT, day TEXT);
INSERT INTO logins VALUES (1,'2026-03-01'),(1,'2026-03-02'),(1,'2026-03-03'),
  (1,'2026-03-05'),(1,'2026-03-06');
CREATE TABLE raw (cust_id INT, city TEXT, updated_at TEXT);
INSERT INTO raw VALUES (1,'Toronto','2026-05-01'),(1,'Ottawa','2026-05-03'),
  (2,'Lagos','2026-05-02'),(2,'Lagos','2026-05-02');
CREATE TABLE target (cust_id INTEGER PRIMARY KEY, city TEXT, updated_at TEXT);
CREATE TABLE dim_cust (sk INTEGER PRIMARY KEY, cust_id INT, city TEXT,
  valid_from TEXT, valid_to TEXT, is_current INT);
INSERT INTO dim_cust VALUES (1,1,'Toronto','1900-01-01','2026-02-15',0),
  (2,1,'Vancouver','2026-02-15','9999-12-31',1);
CREATE TABLE sales (cust_id INT, day TEXT, amount INT);
INSERT INTO sales VALUES (1,'2026-01-10',100),(1,'2026-03-01',200);
CREATE TABLE events (id INT, body TEXT);
INSERT INTO events VALUES (1,'{"user":"ana","tags":["a","b"]}'),(2,'{"user":"ben","tags":[]}');
```
