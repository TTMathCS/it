# 13. Window functions: ranking

*Window functions are what separates a pass from a strong pass in most SQL tests. They compute over a group of related
rows, like an aggregate, but they keep every row instead of collapsing the group into one. That one idea answers a
whole family of questions: the top three products in each category, the second-highest salary, each customer's
latest order, a row's share of its group's total. This chapter covers the window itself (OVER, PARTITION BY, ORDER BY)
and the ranking functions. Their biggest trap is ties, and the sample data is full of them.*

!!! abstract "In this chapter"
    **You will learn:**

    - what `OVER (...)` does, and how a window function differs from GROUP BY
    - aggregates as window functions: a group's total or average on every row
    - `ROW_NUMBER`, `RANK`, `DENSE_RANK`, and what each does with ties
    - top N per group, with ties handled the way the question asks
    - the latest (or first) row for each key
    - why a window function can't go in WHERE, and the CTE that fixes it
    - `NTILE`, `PERCENT_RANK`, `CUME_DIST`, and the `WINDOW` clause

    **You need:** chapters 3, 7 and 11. Window functions work in PostgreSQL 8.4+, SQLite 3.25+, MySQL 8+, SQL Server
    and Oracle.

## 13.1 Aggregates that keep every row { #aggregate-windows }

With GROUP BY, an average per department gives one row per department, and the people are gone. With a window
function, each person keeps their row and gets their department's average beside it:

<!-- sql -->
```sql
SELECT name, department, salary,
       ROUND(AVG(salary) OVER (PARTITION BY department), 0) AS dept_avg,
       salary - ROUND(AVG(salary) OVER (PARTITION BY department), 0) AS vs_dept_avg,
       SUM(salary) OVER () AS company_payroll
FROM employees
WHERE salary IS NOT NULL
ORDER BY department, salary DESC, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

| name | department | salary | dept_avg | vs_dept_avg | company_payroll |
| --- | --- | --- | --- | --- | --- |
| Tom Becker | Engineering | 140000 | 118750 | 21250 | 1097000 |
| Priya Nair | Engineering | 120000 | 118750 | 1250 | 1097000 |
| Sam Lee | Engineering | 120000 | 118750 | 1250 | 1097000 |
| Lucia Gomez | Engineering | 95000 | 118750 | -23750 | 1097000 |
| Maya Rossi | Management | 180000 | 180000 | 0 | 1097000 |
| Omar Aziz | Sales | 110000 | 78750 | 31250 | 1097000 |
| Nina Berg | Sales | 70000 | 78750 | -8750 | 1097000 |
| Raj Patel | Sales | 70000 | 78750 | -8750 | 1097000 |
| Zoe Martin | Sales | 65000 | 78750 | -13750 | 1097000 |
| Kwame Mensah | Support | 75000 | 63500 | 11500 | 1097000 |
| Ella Novak | Support | 52000 | 63500 | -11500 | 1097000 |
<!-- /result -->

`OVER (...)` turns an aggregate into a window function. Inside the brackets:

- **PARTITION BY department** splits the rows into groups (here, departments). The function is computed separately
  in each group, and each row sees only its own group.
- **Empty brackets**, `OVER ()`, mean one group: the whole result. `SUM(salary) OVER ()` is the company payroll on every
  row.

So "employees earning more than their department's average", solved with a subquery in
[chapter 10](10-Subqueries.md#correlated), can also be written by putting the window in a CTE and filtering outside:

<!-- sql -->
```sql
WITH e AS (
  SELECT name, department, salary,
         AVG(salary) OVER (PARTITION BY department) AS dept_avg
  FROM employees
)
SELECT name, department, salary
FROM e
WHERE salary > dept_avg
ORDER BY department, salary DESC, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| name | department | salary |
| --- | --- | --- |
| Tom Becker | Engineering | 140000 |
| Priya Nair | Engineering | 120000 |
| Sam Lee | Engineering | 120000 |
| Omar Aziz | Sales | 110000 |
| Kwame Mensah | Support | 75000 |
<!-- /result -->

**Where windows run.** In the order of chapter 3, window functions are computed **after** WHERE, GROUP BY and
HAVING, and **before** ORDER BY and LIMIT. So they see only the rows that survived WHERE (Leo Park's NULL salary was
filtered out of the first example before any average was taken), and they can't be used in WHERE themselves.

!!! failure "A window function in WHERE"
    <!-- sql error -->
    ```sql
    SELECT name, department, salary
    FROM employees
    WHERE salary > AVG(salary) OVER (PARTITION BY department);
    ```

    <!-- result -->
    <p class="sql-tested sql-error">PostgreSQL 16: error: <code>window functions are not allowed in WHERE</code></p>
    <p class="sql-tested sql-error">SQLite 3.53: error: <code>misuse of window function AVG()</code></p>
    <!-- /result -->

    Both databases refuse. WHERE runs before windows exist. Compute the window in a CTE (or a subquery in FROM) and
    filter in the outer query, as above. This "CTE, then filter" shape is the one to know by heart.

## 13.2 ORDER BY inside the window: numbering rows { #row-number }

The ranking functions need an order: who is first? It goes inside OVER, and has nothing to do with the order of the
output (that is still the final ORDER BY).

<!-- sql -->
```sql
SELECT name, department, salary,
       ROW_NUMBER() OVER (ORDER BY salary DESC, name) AS rn
FROM employees
WHERE salary IS NOT NULL
ORDER BY rn;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

| name | department | salary | rn |
| --- | --- | --- | --- |
| Maya Rossi | Management | 180000 | 1 |
| Tom Becker | Engineering | 140000 | 2 |
| Priya Nair | Engineering | 120000 | 3 |
| Sam Lee | Engineering | 120000 | 4 |
| Omar Aziz | Sales | 110000 | 5 |
| Lucia Gomez | Engineering | 95000 | 6 |
| Kwame Mensah | Support | 75000 | 7 |
| Nina Berg | Sales | 70000 | 8 |
| Raj Patel | Sales | 70000 | 9 |
| Zoe Martin | Sales | 65000 | 10 |
| Ella Novak | Support | 52000 | 11 |
<!-- /result -->

`ROW_NUMBER()` numbers the rows 1, 2, 3, ... in the window's order, with no gaps and no repeats. Two people earn
120,000 (Priya Nair and Sam Lee); `, name` breaks the tie alphabetically. Without a tie-break, which of them gets 4
and which 5 is up to the database and may change from run to run. That is fine for "number the rows", and wrong for
any answer that depends on who is 4th.

Add **PARTITION BY** and the numbering restarts in each group:

<!-- sql -->
```sql
SELECT name, department, salary,
       ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC, name) AS rn_in_dept
FROM employees
WHERE salary IS NOT NULL
ORDER BY department, rn_in_dept;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

| name | department | salary | rn_in_dept |
| --- | --- | --- | --- |
| Tom Becker | Engineering | 140000 | 1 |
| Priya Nair | Engineering | 120000 | 2 |
| Sam Lee | Engineering | 120000 | 3 |
| Lucia Gomez | Engineering | 95000 | 4 |
| Maya Rossi | Management | 180000 | 1 |
| Omar Aziz | Sales | 110000 | 1 |
| Nina Berg | Sales | 70000 | 2 |
| Raj Patel | Sales | 70000 | 3 |
| Zoe Martin | Sales | 65000 | 4 |
| Kwame Mensah | Support | 75000 | 1 |
| Ella Novak | Support | 52000 | 2 |
<!-- /result -->

## 13.3 ROW_NUMBER, RANK and DENSE_RANK: ties { #ties }

The three ranking functions differ only in what they do with ties:

<!-- sql -->
```sql
SELECT name, department, salary,
       ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC, name) AS row_number,
       RANK()       OVER (PARTITION BY department ORDER BY salary DESC)       AS rank,
       DENSE_RANK() OVER (PARTITION BY department ORDER BY salary DESC)       AS dense_rank
FROM employees
WHERE department IN ('Engineering', 'Sales')
ORDER BY department, salary DESC, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 8 rows.</p>

| name | department | salary | row_number | rank | dense_rank |
| --- | --- | --- | --- | --- | --- |
| Tom Becker | Engineering | 140000 | 1 | 1 | 1 |
| Priya Nair | Engineering | 120000 | 2 | 2 | 2 |
| Sam Lee | Engineering | 120000 | 3 | 2 | 2 |
| Lucia Gomez | Engineering | 95000 | 4 | 4 | 3 |
| Omar Aziz | Sales | 110000 | 1 | 1 | 1 |
| Nina Berg | Sales | 70000 | 2 | 2 | 2 |
| Raj Patel | Sales | 70000 | 3 | 2 | 2 |
| Zoe Martin | Sales | 65000 | 4 | 4 | 3 |
<!-- /result -->

| Function | Ties get | After a tie | Engineering |
| --- | --- | --- | --- |
| `ROW_NUMBER()` | different numbers (by tie-break, or by chance) | next number | 1, 2, 3, 4 |
| `RANK()` | the same number | **skips**: as in a race, two seconds, then fourth | 1, 2, 2, 4 |
| `DENSE_RANK()` | the same number | **no gap** | 1, 2, 2, 3 |

`RANK` and `DENSE_RANK` don't need a tie-break: tied rows get the same rank whatever order they are in, so the
result is certain.

**Which to use** depends on the words of the question:

| The question says | Use |
| --- | --- |
| "the top 2 **employees**", exactly two, ties broken by a rule | `ROW_NUMBER()` with the rule as tie-break |
| "the top 2", ties **included** (so maybe more than two) | `RANK() <= 2` |
| "the **2nd highest salary**", "the top 2 **salaries**" (salary levels) | `DENSE_RANK()` |

When a task doesn't say, ask; in a test you can't ask, so choose, and write a one-line comment saying what you did
with ties.

## 13.4 Top N per group { #top-n }

The task: "the two highest-paid people in each department". The shape is always the same: rank in a CTE, filter
outside.

<!-- sql -->
```sql
WITH ranked AS (
  SELECT name, department, salary,
         RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS rnk
  FROM employees
  WHERE salary IS NOT NULL
)
SELECT department, name, salary, rnk
FROM ranked
WHERE rnk <= 2
ORDER BY department, rnk, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

| department | name | salary | rnk |
| --- | --- | --- | --- |
| Engineering | Tom Becker | 140000 | 1 |
| Engineering | Priya Nair | 120000 | 2 |
| Engineering | Sam Lee | 120000 | 2 |
| Management | Maya Rossi | 180000 | 1 |
| Sales | Omar Aziz | 110000 | 1 |
| Sales | Nina Berg | 70000 | 2 |
| Sales | Raj Patel | 70000 | 2 |
| Support | Kwame Mensah | 75000 | 1 |
| Support | Ella Novak | 52000 | 2 |
<!-- /result -->

Engineering shows three people for "top 2": Tom Becker, and Priya Nair and Sam Lee tied for second. Sales likewise.
With RANK that is correct for "the top two, ties included". With ROW_NUMBER, Engineering would show Tom and one of
the two, and with DENSE_RANK, the top two **salary levels**, which here happens to give the same three people but in
general can give many more.

**Without window functions**, top N per group can be written with a correlated count: keep a row if fewer than N rows
in its group are higher. It is slower and harder to read, but some interviewers ask for it:

<!-- sql same -->
```sql
SELECT e.department, e.name, e.salary,
       1 + (SELECT COUNT(*) FROM employees x
            WHERE x.department = e.department AND x.salary > e.salary) AS rnk
FROM employees e
WHERE e.salary IS NOT NULL
  AND (SELECT COUNT(*) FROM employees x
       WHERE x.department = e.department AND x.salary > e.salary) < 2
ORDER BY e.department, rnk, e.name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows as the other version. 9 rows.</p>

| department | name | salary | rnk |
| --- | --- | --- | --- |
| Engineering | Tom Becker | 140000 | 1 |
| Engineering | Priya Nair | 120000 | 2 |
| Engineering | Sam Lee | 120000 | 2 |
| Management | Maya Rossi | 180000 | 1 |
| Sales | Omar Aziz | 110000 | 1 |
| Sales | Nina Berg | 70000 | 2 |
| Sales | Raj Patel | 70000 | 2 |
| Support | Kwame Mensah | 75000 | 1 |
| Support | Ella Novak | 52000 | 2 |
<!-- /result -->

"1 + the number of people earning more" is exactly `RANK()`.

!!! failure "The usual wrong answer: LIMIT"
    <!-- sql -->
    ```sql
    SELECT name, department, salary
    FROM employees
    WHERE department = 'Engineering'
    ORDER BY salary DESC
    LIMIT 2;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | name | department | salary |
    | --- | --- | --- |
    | Tom Becker | Engineering | 140000 |
    | Priya Nair | Engineering | 120000 |
    <!-- /result -->

    Two problems. LIMIT works on the whole result, so it can't give "two per department" at all. And even for one
    department, it cuts the tie at 120,000 in half: which of Priya and Sam appears is down to chance, and nothing in
    the query says the other one exists.


## 13.5 The latest row for each key { #latest }

"Each customer's most recent order." This is the most common window question in data engineering, because it is
also how you keep the newest version of each record when loading data ([chapter 22](22-Duplicates-and-Incremental-Loads.md)).

<!-- sql -->
```sql
WITH ranked AS (
  SELECT o.*,
         ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC, order_id DESC) AS rn
  FROM orders o
  WHERE customer_id IS NOT NULL
)
SELECT customer_id, order_id, order_date, status
FROM ranked
WHERE rn = 1
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

| customer_id | order_id | order_date | status |
| --- | --- | --- | --- |
| 1 | 120 | 2026-04-05 | shipped |
| 2 | 113 | 2026-03-05 | cancelled |
| 3 | 118 | 2026-04-01 | shipped |
| 4 | 112 | 2026-03-01 | shipped |
| 5 | 119 | 2026-04-02 | pending |
| 6 | 116 | 2026-03-22 | pending |
| 7 | 111 | 2026-02-21 | shipped |
| 8 | 114 | 2026-03-09 | shipped |
| 10 | 117 | 2026-03-25 | shipped |
<!-- /result -->

Here ROW_NUMBER is right, because the question wants exactly one order per customer. Two orders on the same day
would tie on date, so `order_id DESC` breaks the tie: the later id wins. Always ask yourself what decides between
two rows with the same date.

A GROUP BY can find each customer's latest **date** (`MAX(order_date)`), but not the other columns of that row. To get
them without a window you would join back on the date, which brings back both rows when two orders share the latest
date. The window version doesn't have that problem.

## 13.6 Ranking groups: windows after GROUP BY { #rank-groups }

Because windows run after GROUP BY, a window function can rank the groups themselves. Customers ranked by shipped
revenue:

<!-- sql -->
```sql
SELECT o.customer_id,
       SUM(i.quantity * i.unit_price) AS revenue,
       RANK() OVER (ORDER BY SUM(i.quantity * i.unit_price) DESC) AS revenue_rank
FROM orders o
JOIN order_items i ON i.order_id = o.order_id
WHERE o.status = 'shipped' AND o.customer_id IS NOT NULL
GROUP BY o.customer_id
ORDER BY revenue_rank, o.customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

| customer_id | revenue | revenue_rank |
| --- | --- | --- |
| 1 | 289.00 | 1 |
| 2 | 205.50 | 2 |
| 4 | 205.50 | 2 |
| 6 | 65.00 | 4 |
| 8 | 49.00 | 5 |
| 10 | 43.00 | 6 |
| 5 | 36.75 | 7 |
| 7 | 36.75 | 7 |
| 3 | 24.50 | 9 |
<!-- /result -->

`SUM(...)` inside the OVER's ORDER BY is the group's total, worked out by the GROUP BY. Customers 2 and 4 tie on
205.50 and share rank 2; the next is 4th.

The share of each group in the total is a window over the grouped rows too:

<!-- sql -->
```sql
SELECT p.category,
       SUM(i.quantity * i.unit_price) AS revenue,
       ROUND(100.0 * SUM(i.quantity * i.unit_price) / SUM(SUM(i.quantity * i.unit_price)) OVER (), 1) AS pct
FROM order_items i
JOIN products p ON p.product_id = i.product_id
WHERE p.category IS NOT NULL
GROUP BY p.category
ORDER BY revenue DESC;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| category | revenue | pct |
| --- | --- | --- |
| Office | 654.25 | 62.5 |
| Home | 220.50 | 21.1 |
| Kitchen | 172.75 | 16.5 |
<!-- /result -->

`SUM(SUM(x)) OVER ()` reads oddly but is right: the inner SUM is each category's total (from GROUP BY), the outer SUM
OVER () adds those totals up across all categories.

## 13.7 NTILE, PERCENT_RANK, CUME_DIST { #ntile }

Three more functions answer "where does this row stand?":

<!-- sql -->
```sql
SELECT name, price,
       NTILE(4)       OVER (ORDER BY price, product_id)  AS quartile,
       ROUND(CAST(PERCENT_RANK() OVER (ORDER BY price) AS NUMERIC), 2) AS pct_rank,
       ROUND(CAST(CUME_DIST()    OVER (ORDER BY price) AS NUMERIC), 2) AS cume_dist
FROM products
ORDER BY price, product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

| name | price | quartile | pct_rank | cume_dist |
| --- | --- | --- | --- | --- |
| Notebook | 3.25 | 1 | 0.00 | 0.09 |
| Coffee mug | 8.75 | 1 | 0.10 | 0.18 |
| Bookend | 9.50 | 1 | 0.20 | 0.27 |
| Plant pot | 12.25 | 2 | 0.30 | 0.36 |
| Fountain pen | 18.00 | 2 | 0.40 | 0.45 |
| Desk lamp | 24.50 | 2 | 0.50 | 0.64 |
| Wall clock | 24.50 | 3 | 0.50 | 0.64 |
| Gift card | 25.00 | 3 | 0.70 | 0.73 |
| Tea kettle | 32.00 | 3 | 0.80 | 0.91 |
| Monitor stand | 32.00 | 4 | 0.80 | 0.91 |
| Office chair | 149.00 | 4 | 1.00 | 1.00 |
<!-- /result -->

- `NTILE(4)` deals the rows into 4 buckets as evenly as possible; with 11 rows the first three get 3 and the last
  gets 2. Ties can land in different buckets, so it needs a tie-break.
- `PERCENT_RANK()` is `(rank - 1) / (rows - 1)`: 0 for the first, 1 for the last.
- `CUME_DIST()` is the share of rows at or below this one's value.

Both return a floating-point number; PostgreSQL's `ROUND(x, 2)` doesn't accept that type, hence the `CAST(... AS
NUMERIC)` (chapter 4).

## 13.8 Naming a window: the WINDOW clause { #window-clause }

When several functions share one window, name it once:

<!-- sql -->
```sql
SELECT name, department, salary,
       RANK()       OVER w AS rnk,
       DENSE_RANK() OVER w AS drnk
FROM employees
WHERE department = 'Sales'
WINDOW w AS (PARTITION BY department ORDER BY salary DESC)
ORDER BY rnk, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| name | department | salary | rnk | drnk |
| --- | --- | --- | --- | --- |
| Omar Aziz | Sales | 110000 | 1 | 1 |
| Nina Berg | Sales | 70000 | 2 | 2 |
| Raj Patel | Sales | 70000 | 2 | 2 |
| Zoe Martin | Sales | 65000 | 4 | 3 |
<!-- /result -->

`WINDOW` goes after HAVING and before ORDER BY. PostgreSQL, SQLite and MySQL have it; SQL Server only since 2022.

## 13.9 Summary { #summary }

- `f(...) OVER (PARTITION BY g ORDER BY o)`: computed per group `g`, in order `o`, keeping every row.
- Aggregates work as windows: `AVG(x) OVER (PARTITION BY g)` is the group's average on each row.
- `ROW_NUMBER` always 1, 2, 3 (needs a tie-break); `RANK` 1, 2, 2, 4; `DENSE_RANK` 1, 2, 2, 3.
- Window functions run after WHERE and GROUP BY, so filter on them in an outer query: CTE, then `WHERE rn = 1`.
- Top N per group: rank in a CTE, filter `<= N`. Latest per key: `ROW_NUMBER() ... ORDER BY date DESC, id DESC`, keep 1.

## Practice { #practice }

**13.1** For each product: its name, category, price, and its price rank within the category (most expensive is 1,
equal prices share a rank, no gaps).

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, category, price,
           DENSE_RANK() OVER (PARTITION BY category ORDER BY price DESC) AS price_rank
    FROM products
    WHERE category IS NOT NULL
    ORDER BY category, price_rank, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

    | name | category | price | price_rank |
    | --- | --- | --- | --- |
    | Desk lamp | Home | 24.50 | 1 |
    | Wall clock | Home | 24.50 | 1 |
    | Plant pot | Home | 12.25 | 2 |
    | Bookend | Home | 9.50 | 3 |
    | Tea kettle | Kitchen | 32.00 | 1 |
    | Coffee mug | Kitchen | 8.75 | 2 |
    | Office chair | Office | 149.00 | 1 |
    | Monitor stand | Office | 32.00 | 2 |
    | Fountain pen | Office | 18.00 | 3 |
    | Notebook | Office | 3.25 | 4 |
    <!-- /result -->

    "Equal prices share a rank, no gaps" is DENSE_RANK. The desk lamp and wall clock share rank 1 in Home.

**13.2** The most expensive product in each category, with ties.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH r AS (
      SELECT name, category, price,
             RANK() OVER (PARTITION BY category ORDER BY price DESC) AS rnk
      FROM products
      WHERE category IS NOT NULL
    )
    SELECT category, name, price
    FROM r
    WHERE rnk = 1
    ORDER BY category, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | category | name | price |
    | --- | --- | --- |
    | Home | Desk lamp | 24.50 |
    | Home | Wall clock | 24.50 |
    | Kitchen | Tea kettle | 32.00 |
    | Office | Office chair | 149.00 |
    <!-- /result -->

    Home has two (tied at 24.50). RANK and DENSE_RANK give the same rows for `= 1`; ROW_NUMBER would drop one of
    them.

**13.3** The second-highest **salary** in the company. If there is no second salary level, return nothing.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH s AS (
      SELECT DISTINCT salary,
             DENSE_RANK() OVER (ORDER BY salary DESC) AS dr
      FROM employees
      WHERE salary IS NOT NULL
    )
    SELECT salary FROM s WHERE dr = 2;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | salary |
    | --- |
    | 140000 |
    <!-- /result -->

    DENSE_RANK numbers salary levels, so `dr = 2` is the second level even if several people share the top.
    `DISTINCT` stops a tied level from appearing twice. [Chapter 15](15-Classic-Interview-Patterns.md#nth-highest)
    has three more ways, including the one that must return NULL rather than nothing.

**13.4** For each department, the most recently hired employee: name and hire date.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH r AS (
      SELECT department, name, hire_date,
             ROW_NUMBER() OVER (PARTITION BY department ORDER BY hire_date DESC, employee_id DESC) AS rn
      FROM employees
    )
    SELECT department, name, hire_date
    FROM r
    WHERE rn = 1
    ORDER BY department;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | department | name | hire_date |
    | --- | --- | --- |
    | Engineering | Lucia Gomez | 2024-09-01 |
    | Management | Maya Rossi | 2019-04-01 |
    | Sales | Zoe Martin | 2025-01-06 |
    | Support | Leo Park | 2026-01-12 |
    <!-- /result -->

**13.5** Number each customer's orders in date order (1 for their first order), for customers 1 and 2, with the
order id as tie-break.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT customer_id, order_id, order_date,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS order_number
    FROM orders
    WHERE customer_id IN (1, 2)
    ORDER BY customer_id, order_number;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 8 rows.</p>

    | customer_id | order_id | order_date | order_number |
    | --- | --- | --- | --- |
    | 1 | 101 | 2026-01-03 | 1 |
    | 1 | 103 | 2026-01-15 | 2 |
    | 1 | 110 | 2026-02-20 | 3 |
    | 1 | 115 | 2026-03-18 | 4 |
    | 1 | 120 | 2026-04-05 | 5 |
    | 2 | 102 | 2026-01-03 | 1 |
    | 2 | 106 | 2026-02-02 | 2 |
    | 2 | 113 | 2026-03-05 | 3 |
    <!-- /result -->

    "Which order number was this for the customer" comes up in questions such as "revenue from first orders versus
    repeat orders": filter `order_number = 1` or `> 1`.

**13.6** Each product's revenue (all orders) and its rank across all products, highest first, with ties sharing a
rank. Include products never sold, with revenue 0.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT p.name,
           COALESCE(SUM(i.quantity * i.unit_price), 0) AS revenue,
           RANK() OVER (ORDER BY COALESCE(SUM(i.quantity * i.unit_price), 0) DESC) AS rnk
    FROM products p
    LEFT JOIN order_items i ON i.product_id = p.product_id
    GROUP BY p.product_id, p.name
    ORDER BY rnk, p.name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

    | name | revenue | rnk |
    | --- | --- | --- |
    | Office chair | 437.00 | 1 |
    | Desk lamp | 122.50 | 2 |
    | Tea kettle | 94.00 | 3 |
    | Notebook | 81.25 | 4 |
    | Coffee mug | 78.75 | 5 |
    | Gift card | 75.00 | 6 |
    | Plant pot | 73.50 | 7 |
    | Fountain pen | 72.00 | 8 |
    | Monitor stand | 64.00 | 9 |
    | Wall clock | 24.50 | 10 |
    | Bookend | 0 | 11 |
    <!-- /result -->

**13.7** Each employee's salary as a percentage of their department's total payroll, one decimal, largest share first
within each department.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT department, name, salary,
           ROUND(100.0 * salary / SUM(salary) OVER (PARTITION BY department), 1) AS pct_of_dept
    FROM employees
    WHERE salary IS NOT NULL
    ORDER BY department, pct_of_dept DESC, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

    | department | name | salary | pct_of_dept |
    | --- | --- | --- | --- |
    | Engineering | Tom Becker | 140000 | 29.5 |
    | Engineering | Priya Nair | 120000 | 25.3 |
    | Engineering | Sam Lee | 120000 | 25.3 |
    | Engineering | Lucia Gomez | 95000 | 20.0 |
    | Management | Maya Rossi | 180000 | 100.0 |
    | Sales | Omar Aziz | 110000 | 34.9 |
    | Sales | Nina Berg | 70000 | 22.2 |
    | Sales | Raj Patel | 70000 | 22.2 |
    | Sales | Zoe Martin | 65000 | 20.6 |
    | Support | Kwame Mensah | 75000 | 59.1 |
    | Support | Ella Novak | 52000 | 40.9 |
    <!-- /result -->

**13.8** Find the customers whose first-ever order was cancelled.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH firsts AS (
      SELECT customer_id, order_id, status,
             ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS rn
      FROM orders
      WHERE customer_id IS NOT NULL
    )
    SELECT customer_id, order_id
    FROM firsts
    WHERE rn = 1 AND status = 'cancelled'
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | customer_id | order_id |
    | --- | --- |
    | 3 | 104 |
    <!-- /result -->

    The status filter must go **outside**, after the numbering. Inside the CTE's WHERE it would number only the
    cancelled orders, and "first cancelled order" is a different question.

**13.9** Without window functions: each department's highest-paid employee(s).

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT e.department, e.name, e.salary
    FROM employees e
    WHERE e.salary = (SELECT MAX(x.salary) FROM employees x WHERE x.department = e.department)
    ORDER BY e.department, e.name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | department | name | salary |
    | --- | --- | --- |
    | Engineering | Tom Becker | 140000 |
    | Management | Maya Rossi | 180000 |
    | Sales | Omar Aziz | 110000 |
    | Support | Kwame Mensah | 75000 |
    <!-- /result -->

    A correlated MAX keeps ties, like `RANK() = 1`. Useful if a test environment is too old for window functions
    (SQLite before 3.25, MySQL before 8).

**Next:** [14. Window functions: LAG, LEAD and running totals](14-Window-Functions-Lag-Lead-Running-Totals.md).
