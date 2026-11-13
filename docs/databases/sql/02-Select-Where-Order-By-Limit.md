# 2. SELECT, WHERE, ORDER BY, LIMIT

*Four clauses answer most simple questions: which columns (`SELECT`), which rows (`WHERE`), in what order
(`ORDER BY`) and how many (`LIMIT`). This chapter covers each, with the small details that decide whether an answer
is marked right: single and double quotes, `AND` before `OR`, `BETWEEN` including both ends, `DISTINCT` on the whole
row, and ties at the edge of a `LIMIT`.*

!!! abstract "In this chapter"
    **You will learn:**

    - choosing columns, computing new ones, and naming them with `AS`
    - single quotes for text, double quotes for names, and what SQLite does when you mix them up
    - `WHERE` with comparisons, `AND`, `OR`, `NOT`, `IN` and `BETWEEN`
    - `DISTINCT`, and why it applies to the whole row
    - `ORDER BY` on several columns, on an expression, and the tie-break every test answer needs
    - `LIMIT` and `OFFSET`, the standard `FETCH FIRST`, and `WITH TIES`

    **You need:** [chapter 1](01-Tables-Rows-and-Keys.md) and the [sample database](sample-database.md).

## 2.1 SELECT and FROM { #select }

`SELECT` lists the columns you want, `FROM` names the table. Columns come back in the order you list them.

<!-- sql -->
```sql
SELECT name, category, price
FROM products
ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

| name | category | price |
| --- | --- | --- |
| Desk lamp | Home | 24.50 |
| Notebook | Office | 3.25 |
| Fountain pen | Office | 18.00 |
| Coffee mug | Kitchen | 8.75 |
| Tea kettle | Kitchen | 32.00 |
| Office chair | Office | 149.00 |
| Monitor stand | Office | 32.00 |
| Plant pot | Home | 12.25 |
| Wall clock | Home | 24.50 |
| Gift card | *NULL* | 25.00 |
| Bookend | Home | 9.50 |
<!-- /result -->

`SELECT *` returns every column in the table's order. It is handy for a first look and wrong in a test answer: a
checker compares columns by position, and `*` returns columns the question did not ask for. List them.

## 2.2 Computed columns and aliases { #aliases }

A column in `SELECT` can be any expression. `AS` gives the result a name, an **alias**:

<!-- sql -->
```sql
SELECT order_id, product_id,
       quantity * unit_price AS line_value
FROM order_items
WHERE order_id = 103
ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| order_id | product_id | line_value |
| --- | --- | --- |
| 103 | 2 | 16.25 |
| 103 | 4 | 17.50 |
<!-- /result -->

`AS` can be left out (`quantity * unit_price line_value`), but writing it makes a missing comma easy to spot:
`SELECT name category FROM products` is not an error, it returns one column, `name`, labelled `category`.

## 2.3 Single quotes and double quotes { #quotes }

!!! tip "The rule in one line"
    **Single quotes for values, double quotes for names.** `'Tom Becker'` is a piece of text. `"Tom Becker"` is the
    name of a column, and PostgreSQL will look for a column with that name.

In standard SQL, **single quotes** make a piece of text, a **string literal**: `'Toronto'`. **Double quotes**
surround a **name** (an **identifier**: a column, table or alias name), and they are needed only when the name has a
space, capital letters or a reserved word in it: `"Order Date"`.

Mixing them up is one of the most common errors on PostgreSQL:

<!-- sql pgerror -->
```sql
SELECT name, city
FROM customers
WHERE city = "Toronto";
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>column "Toronto" does not exist</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 3 rows.</p>
<!-- /result -->

PostgreSQL looked for a **column** called `Toronto` and found none. The same happens with a name: here is "the
employees who report to Tom Becker", written with a self-join ([chapter 9](09-Self-Semi-and-Anti-Joins.md)) and
double quotes round the name:

<!-- sql pgerror -->
```sql
SELECT e.employee_id, e.name, e.salary
FROM employees e
JOIN employees m ON e.manager_id = m.employee_id
WHERE m.name = "Tom Becker";
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>column "Tom Becker" does not exist</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 3 rows.</p>
<!-- /result -->

When you see **`column "..." does not exist`** and the word in the quotes is a value, not a column, the fix is
the quotes. The query itself was right:

<!-- sql -->
```sql
SELECT e.employee_id, e.name, e.salary
FROM employees e
JOIN employees m ON e.manager_id = m.employee_id
WHERE m.name = 'Tom Becker'
ORDER BY e.employee_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| employee_id | name | salary |
| --- | --- | --- |
| 3 | Priya Nair | 120000 |
| 4 | Sam Lee | 120000 |
| 5 | Lucia Gomez | 95000 |
<!-- /result -->

**Why it works in SQLite and MySQL.** SQLite, for compatibility with old MySQL code, treats a double-quoted word that
is not a column name as text, so both queries above run there; the SQLite manual calls this a misfeature. MySQL by
default reads double quotes as text too, and quotes names with backticks: `` `order date` ``. SQL Server uses square
brackets: `[order date]`. Anyone who learned SQL on MySQL or SQLite carries the habit over, and a test running
PostgreSQL fails it. [Chapter 28](28-Dialect-Differences.md) collects these differences.

### A quote inside text { #apostrophe }

A single quote inside text is written **twice**: `'O''Brien'` is the seven letters `O'Brien`. Doubling is the
standard way and works on every database:

<!-- sql -->
```sql
SELECT 'O''Brien' AS surname,
       LENGTH('O''Brien') AS letters;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| surname | letters |
| --- | --- |
| O'Brien | 7 |
<!-- /result -->

A double quote inside single quotes needs nothing special: `'He said "hi"'`. PostgreSQL also has
**dollar quoting**, `$$O'Brien$$`, handy for long text full of quotes; it is PostgreSQL only.

### When double quotes are needed { #double-quotes }

Only for a name that would not work bare. The common case is a column name for a report, with spaces and
capitals:

<!-- sql -->
```sql
SELECT customer_id AS "Customer ID",
       name        AS "Full name"
FROM customers
ORDER BY customer_id
LIMIT 3;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| Customer ID | Full name |
| --- | --- |
| 1 | Ana Silva |
| 2 | Ben Okafor |
| 3 | Chen Wei |
<!-- /result -->

The other case is a name that is a **reserved word**, a word SQL itself uses, such as `order`, `group`, `user` or
`select`. A table called `order` sounds natural for a shop, but bare, the word confuses the parser:

<!-- sql error -->
```sql
CREATE TABLE order (order_id INTEGER PRIMARY KEY);
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>syntax error at or near "order"</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>near "order": syntax error</code></p>
<!-- /result -->

`CREATE TABLE "order"` works, but then every query must write `"order"` with the quotes. That is why the sample shop
calls it `orders`. (After `AS`, PostgreSQL accepts most reserved words without quotes, but a plain name such as
`order_no` is still clearer.)

**Why to avoid double-quoted names when you can.** PostgreSQL turns every name you write **without** quotes into
lower case, so `SELECT Name FROM customers` and `SELECT NAME FROM customers` both find the column `name`. With quotes
the case is kept exactly, so `"Name"` is a different name, and it does not exist:

<!-- sql pgerror -->
```sql
SELECT "Name"
FROM customers;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>column "Name" does not exist</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 10 rows.</p>
<!-- /result -->

A table created as `CREATE TABLE "Orders"` must then be written `"Orders"`, with the quotes and the capital, in
every query for ever. That is why database names are usually lower case with underscores (`order_date`), which never
need quotes. SQLite ignores the case of names, so this one runs there.

## 2.4 WHERE: choosing rows { #where }

`WHERE` keeps the rows for which a condition is true. The comparison operators are `=`, `<>` (not equal; `!=` also
works on every database in this course), `<`, `<=`, `>` and `>=`. They work on numbers, text and dates:

<!-- sql -->
```sql
SELECT customer_id, name, signup_date
FROM customers
WHERE signup_date >= '2026-02-01'
ORDER BY signup_date, customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| customer_id | name | signup_date |
| --- | --- | --- |
| 6 | Farah Haddad | 2026-02-02 |
| 7 | Gus Novak | 2026-02-14 |
| 8 | Hana Sato | 2026-02-28 |
| 9 | Ivan Petrov | 2026-03-03 |
| 10 | Ana Silva | 2026-03-15 |
<!-- /result -->

The date is written as text in the ISO format `'YYYY-MM-DD'`. PostgreSQL turns it into a date because the column is
a `DATE`; SQLite stores dates as text, and ISO dates sort correctly as text. Other formats (`'02/01/2026'`) are
ambiguous and break on one database or the other: always write `YYYY-MM-DD`.

### AND, OR, NOT, and which comes first { #and-or }

`AND` needs both conditions, `OR` either, `NOT` turns a condition around. `AND` is evaluated **before** `OR`, the way
multiplication comes before addition. Forgetting that is the classic mistake:

!!! failure "The usual wrong answer: Home or Kitchen products over 20"
    <!-- sql -->
    ```sql
    SELECT name, category, price
    FROM products
    WHERE category = 'Home' OR category = 'Kitchen' AND price > 20
    ORDER BY product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | name | category | price |
    | --- | --- | --- |
    | Desk lamp | Home | 24.50 |
    | Tea kettle | Kitchen | 32.00 |
    | Plant pot | Home | 12.25 |
    | Wall clock | Home | 24.50 |
    | Bookend | Home | 9.50 |
    <!-- /result -->

    The plant pot (12.25) and the bookend (9.50) should not be there. The database read it as
    `Home OR (Kitchen AND price > 20)`, so every Home product came back whatever its price.

Parentheses say what you mean:

<!-- sql -->
```sql
SELECT name, category, price
FROM products
WHERE (category = 'Home' OR category = 'Kitchen') AND price > 20
ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| name | category | price |
| --- | --- | --- |
| Desk lamp | Home | 24.50 |
| Tea kettle | Kitchen | 32.00 |
| Wall clock | Home | 24.50 |
<!-- /result -->

Whenever a `WHERE` mixes `AND` and `OR`, add the parentheses even if you think you know the order. Readers (and
markers) should not have to work it out.

### IN and BETWEEN { #in-between }

`IN` is a short way to write several `=` joined by `OR`:

<!-- sql -->
```sql
SELECT name, category, price
FROM products
WHERE category IN ('Home', 'Kitchen') AND price > 20
ORDER BY product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| name | category | price |
| --- | --- | --- |
| Desk lamp | Home | 24.50 |
| Tea kettle | Kitchen | 32.00 |
| Wall clock | Home | 24.50 |
<!-- /result -->

`BETWEEN a AND b` includes **both** ends: it means `>= a AND <= b`.

<!-- sql -->
```sql
SELECT name, price
FROM products
WHERE price BETWEEN 12.25 AND 25.00
ORDER BY price, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

| name | price |
| --- | --- |
| Plant pot | 12.25 |
| Fountain pen | 18.00 |
| Desk lamp | 24.50 |
| Wall clock | 24.50 |
| Gift card | 25.00 |
<!-- /result -->

The plant pot (12.25) and the gift card (25.00) sit exactly on the ends and are included. With timestamps,
`BETWEEN` has a trap at the upper end; [chapter 16](16-Dates-and-Time-Series.md) shows it and the safer form
`>= start AND < next_day`. `NOT IN` and `NOT BETWEEN` turn them around, and `NOT IN` has a trap of its own with NULLs
([chapter 9](09-Self-Semi-and-Anti-Joins.md#anti)).

`WHERE email = NULL` never finds anything; missing values need `IS NULL`. That is the subject of
[chapter 6](06-Null-and-Three-Valued-Logic.md), and pattern matching with `LIKE` is in
[chapter 5](05-Text-Functions-and-Pattern-Matching.md).

## 2.5 DISTINCT { #distinct }

`SELECT DISTINCT` removes duplicate rows from the result:

<!-- sql -->
```sql
SELECT DISTINCT country
FROM customers
ORDER BY country;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 8 rows.</p>

| country |
| --- |
| Canada |
| China |
| Czechia |
| Israel |
| Japan |
| Nigeria |
| Portugal |
| South Korea |
<!-- /result -->

Ten customers, eight countries: Canada appears three times in the table and once here. `DISTINCT` applies to the
**whole row**, not to the first column:

<!-- sql -->
```sql
SELECT DISTINCT country, city
FROM customers
WHERE country = 'Canada'
ORDER BY city;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| country | city |
| --- | --- |
| Canada | Toronto |
<!-- /result -->

Canada still appears once, because all three Canadian customers live in Toronto. Add a column that differs, such as
`name`, and all three rows come back. `DISTINCT` also treats NULLs as equal to each other, so two customers with no
city would give one NULL row.

!!! tip "Interview tip"
    Reaching for `DISTINCT` to make duplicates go away is often a sign that a join multiplied the rows
    ([chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md#fan-out)). It hides the symptom; sums computed before it are
    still wrong. Ask why the duplicates are there before adding it.

## 2.6 ORDER BY { #order-by }

`ORDER BY` sorts the result: `ASC` (smallest first, the default) or `DESC`. With several columns, the second only
decides between rows that tie on the first:

<!-- sql -->
```sql
SELECT name, department, salary
FROM employees
WHERE salary IS NOT NULL
ORDER BY department, salary DESC, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

| name | department | salary |
| --- | --- | --- |
| Tom Becker | Engineering | 140000 |
| Priya Nair | Engineering | 120000 |
| Sam Lee | Engineering | 120000 |
| Lucia Gomez | Engineering | 95000 |
| Maya Rossi | Management | 180000 |
| Omar Aziz | Sales | 110000 |
| Nina Berg | Sales | 70000 |
| Raj Patel | Sales | 70000 |
| Zoe Martin | Sales | 65000 |
| Kwame Mensah | Support | 75000 |
| Ella Novak | Support | 52000 |
<!-- /result -->

Departments A to Z; within each department, highest salary first; for equal salaries (Priya Nair and Sam Lee, Nina
Berg and Raj Patel), by name. Without that last column the order of the tied pairs would be up to the database.

You can sort by an alias from `SELECT`, by an expression, or by a column you do not show:

<!-- sql -->
```sql
SELECT order_id, product_id, quantity * unit_price AS line_value
FROM order_items
WHERE order_id IN (101, 103, 105)
ORDER BY line_value DESC, order_id, product_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

| order_id | product_id | line_value |
| --- | --- | --- |
| 101 | 1 | 24.50 |
| 105 | 3 | 18.00 |
| 103 | 4 | 17.50 |
| 103 | 2 | 16.25 |
| 101 | 2 | 9.75 |
| 105 | 2 | 6.50 |
<!-- /result -->

`ORDER BY 3` (the third column) also works, but it breaks silently when the column list changes; name the column.

Where NULLs go in a sort differs between databases: PostgreSQL puts them last in ascending order; SQLite, MySQL and
SQL Server put them first. `NULLS FIRST` and `NULLS LAST` decide it on PostgreSQL and SQLite; [chapter 6](06-Null-and-Three-Valued-Logic.md#sorting)
shows them.

## 2.7 LIMIT and OFFSET { #limit }

`LIMIT n` keeps the first n rows of the sorted result; `OFFSET m` skips m rows first.

<!-- sql -->
```sql
SELECT name, price
FROM products
ORDER BY price DESC, name
LIMIT 3;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| name | price |
| --- | --- |
| Office chair | 149.00 |
| Monitor stand | 32.00 |
| Tea kettle | 32.00 |
<!-- /result -->

<!-- sql -->
```sql
SELECT name, price
FROM products
ORDER BY price DESC, name
LIMIT 3 OFFSET 3;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| name | price |
| --- | --- |
| Gift card | 25.00 |
| Desk lamp | 24.50 |
| Wall clock | 24.50 |
<!-- /result -->

The second query is "page 2" with three rows a page. `LIMIT` without `ORDER BY` returns some rows, in no promised
order; it is almost always a mistake.

!!! failure "The usual wrong answer: the most expensive products, top 2"
    The two dearest products by price are the office chair (149.00) and then a tie: the tea kettle and the monitor
    stand both cost 32.00. `ORDER BY price DESC LIMIT 2` returns the chair and **one** of the two, whichever the
    database happens to meet first. The answer is neither complete nor repeatable. Either the question wants a
    tie-break (then add it: `ORDER BY price DESC, name`), or it wants every product at the top two prices, which is
    a ranking question ([chapter 13](13-Window-Functions-Ranking.md)).

### The standard spelling: FETCH FIRST { #fetch-first }

`LIMIT` is not in the SQL standard, though PostgreSQL, SQLite and MySQL all have it. The standard writes
`OFFSET m ROWS FETCH FIRST n ROWS ONLY`; PostgreSQL, Oracle (12c and later) and SQL Server (with `OFFSET`) accept it,
SQLite does not. PostgreSQL 13 and later also have `WITH TIES`, which keeps every row that ties with the last one:

<!-- sql pg -->
```sql
SELECT name, price
FROM products
ORDER BY price DESC
FETCH FIRST 2 ROWS WITH TIES;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

| name | price |
| --- | --- |
| Office chair | 149.00 |
| Tea kettle | 32.00 |
| Monitor stand | 32.00 |
<!-- /result -->

Asked for 2 rows, it returned 3, because the second and third tie. SQL Server writes `SELECT TOP 2 WITH TIES ...`.
On SQLite, use a ranking function instead ([chapter 13](13-Window-Functions-Ranking.md)).

## 2.8 Comments and layout { #comments }

`--` starts a comment to the end of the line; `/* ... */` can span lines. Line breaks and spaces do not matter to
the database, so lay a query out one clause per line. A query that ends with `;` is complete; in a test editor the
semicolon is usually optional for a single query, but it never hurts.

<!-- sql -->
```sql
-- Products in the Office category, cheapest first
SELECT name, price
FROM products
WHERE category = 'Office'   /* exact match: 'office' would find nothing */
ORDER BY price, name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| name | price |
| --- | --- |
| Notebook | 3.25 |
| Fountain pen | 18.00 |
| Monitor stand | 32.00 |
| Office chair | 149.00 |
<!-- /result -->

### How to lay out a query { #layout }

The database ignores spaces, line breaks and the case of keywords, so any layout runs. Layout is for the people who
read the query, and the first of them is you, ten minutes later, looking for a mistake. A common style, used in this
course:

| Rule | Example |
| --- | --- |
| Keywords in capitals, names in lower case | `SELECT`, `FROM`, `COUNT(*)`; `order_date` |
| Each clause starts a new line, at the left edge | `SELECT` ... / `FROM` ... / `WHERE` ... / `GROUP BY` ... / `ORDER BY` ... |
| A short list of plain columns may stay on one line | `SELECT name, price` |
| Otherwise one column per line, indented, comma at the end of the line | as in the example below |
| A name (`AS`) for every computed column | `COUNT(*) AS orders` |
| Each `JOIN` on its own line, its `ON` on the same line or indented under it | `LEFT JOIN customers c ON c.customer_id = o.customer_id` |
| With more than one table, a short alias per table and the alias on every column | `o.status`, `c.name` |
| Each `AND` of a long `WHERE` on its own line | as in the example below |
| A long query as named steps with `WITH`, each step indented inside its brackets | [chapter 11](11-CTEs-and-Recursive-CTEs.md) |

**Columns on one line or one per line?** Both are correct. Two or three plain columns read well on one line. Once a
column is an expression (`COUNT(*)`, a `CASE`, a calculation) or there are more than three, one per line is
easier to read, to compare with the task's list of output columns, and to change. Whatever you choose, be consistent
within a query.

Here is a query written in one line, as it is often typed in a hurry:

<!-- sql pg -->
```sql
select o.status, count(*) from orders o left join customers c on o.customer_id = c.customer_id group by status
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

| status | count |
| --- | --- |
| cancelled | 2 |
| pending | 2 |
| shipped | 16 |
<!-- /result -->

It runs, but three things are hard to see. The join to `customers` does nothing: no column of `c` is used, and a
`LEFT JOIN` keeps every order anyway, so the counts are the same without it. The count has no name, so each
database invents one (PostgreSQL calls it `count`, SQLite `count(*)`). And there is no
`ORDER BY`, so the order of the rows is luck. The same question, laid out and cleaned up:

<!-- sql -->
```sql
SELECT
    o.status,
    COUNT(*) AS orders
FROM orders o
GROUP BY o.status
ORDER BY o.status;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| status | orders |
| --- | --- |
| cancelled | 2 |
| pending | 2 |
| shipped | 16 |
<!-- /result -->

A longer query in the same style. Each line does one thing, so each can be checked against the task on its own:

<!-- sql -->
```sql
SELECT
    c.country,
    COUNT(o.order_id)              AS shipped_orders,
    COUNT(DISTINCT o.customer_id)  AS customers
FROM customers c
JOIN orders o
    ON o.customer_id = c.customer_id
WHERE o.status = 'shipped'
  AND o.order_date >= '2026-02-01'
GROUP BY c.country
HAVING COUNT(o.order_id) >= 2
ORDER BY shipped_orders DESC, c.country;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| country | shipped_orders | customers |
| --- | --- | --- |
| Canada | 4 | 2 |
<!-- /result -->

Lining up the `AS` names, as above, is optional; some teams like it, some don't. In a timed test, do not spend
minutes on layout: one clause per line and a name for every computed column is enough.

## 2.9 Summary { #summary }

- `SELECT` the columns asked for, in the order asked; avoid `*` in answers. Name computed columns with `AS`.
- Single quotes for text, double quotes for names. SQLite forgives `"Toronto"`; PostgreSQL does not, and says
  `column "Toronto" does not exist`. A quote inside text is doubled: `'O''Brien'`. See [2.3](#quotes).
- `AND` before `OR`: add parentheses whenever both appear.
- `IN (...)` for a list; `BETWEEN` includes both ends.
- `DISTINCT` works on the whole row and treats NULLs as equal.
- Always `ORDER BY`, with a tie-break that makes the order unique. NULLs sort differently by database.
- `LIMIT` cuts ties arbitrarily; `FETCH FIRST ... WITH TIES` (PostgreSQL) or a ranking keeps them.
- Lay a query out one clause per line, with a name for every computed column ([how to lay out a query](#layout)).

## Practice { #practice }

**2.1** Customers in Canada or Japan who signed up in 2026. Return `name`, `country`, `signup_date`, by
`signup_date`, then `name`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, country, signup_date
    FROM customers
    WHERE country IN ('Canada', 'Japan')
      AND signup_date >= '2026-01-01' AND signup_date < '2027-01-01'
    ORDER BY signup_date, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | name | country | signup_date |
    | --- | --- | --- |
    | Farah Haddad | Canada | 2026-02-02 |
    | Hana Sato | Japan | 2026-02-28 |
    | Ivan Petrov | Canada | 2026-03-03 |
    <!-- /result -->

    Ana Silva (1) is Canadian but signed up in November 2025, so she is out. With `OR` instead of `IN`, the country
    test would need parentheses.

**2.2** Every product line of orders 109 and 117 with its value (quantity × price paid). Return `order_id`,
`product_id`, `line_value`, highest value first, then `order_id`, then `product_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT order_id, product_id, quantity * unit_price AS line_value
    FROM order_items
    WHERE order_id IN (109, 117)
    ORDER BY line_value DESC, order_id, product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | order_id | product_id | line_value |
    | --- | --- | --- |
    | 109 | 4 | 35.00 |
    | 109 | 5 | 30.00 |
    | 117 | 3 | 18.00 |
    | 117 | 2 | 16.25 |
    | 117 | 4 | 8.75 |
    <!-- /result -->

    `quantity * unit_price AS line_value` computes a new column and names it. `ORDER BY line_value` may use that
    name because `ORDER BY` runs after `SELECT`; `WHERE` could not. `IN (109, 117)` is a short way to write
    `order_id = 109 OR order_id = 117`.


**2.3** The distinct statuses that orders have, alphabetically.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT DISTINCT status
    FROM orders
    ORDER BY status;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | status |
    | --- |
    | cancelled |
    | pending |
    | shipped |
    <!-- /result -->

    `DISTINCT` removes repeated rows from the result, so each status appears once. Use it for "the different
    values of ..."; to count them, use `COUNT(DISTINCT status)`.


**2.4** The three most recently hired employees. Return `name`, `hire_date`, newest first.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, hire_date
    FROM employees
    ORDER BY hire_date DESC, name
    LIMIT 3;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | name | hire_date |
    | --- | --- |
    | Leo Park | 2026-01-12 |
    | Zoe Martin | 2025-01-06 |
    | Lucia Gomez | 2024-09-01 |
    <!-- /result -->

    No two hire dates are equal here, but the `, name` tie-break costs nothing and protects the answer if the data
    changes.

**2.5** What does this return, and why? Then fix it to return Office products costing under 10 or over 100.

```sql
SELECT name, price FROM products
WHERE category = 'Office' AND price < 10 OR price > 100;
```

??? success "Answer"
    It reads as `(Office AND price < 10) OR price > 100`: the notebook, plus every product over 100 from any category.
    Here that happens to be only the office chair, so the answer looks right by luck; a Home product over 100 would
    slip in. The fix:

    <!-- sql -->
    ```sql
    SELECT name, price
    FROM products
    WHERE category = 'Office' AND (price < 10 OR price > 100)
    ORDER BY price, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | name | price |
    | --- | --- |
    | Notebook | 3.25 |
    | Office chair | 149.00 |
    <!-- /result -->

**2.6** Products 4 to 6 in price order, most expensive first (that is, skip the three dearest). Return `name`,
`price`; break ties by `name`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, price
    FROM products
    ORDER BY price DESC, name
    LIMIT 3 OFFSET 3;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | name | price |
    | --- | --- |
    | Gift card | 25.00 |
    | Desk lamp | 24.50 |
    | Wall clock | 24.50 |
    <!-- /result -->

    The desk lamp and the wall clock tie at 24.50; the tie-break by name puts the desk lamp first.

**2.7** Orders placed in February 2026 that are not shipped. Return `order_id`, `order_date`, `status`, by
`order_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT order_id, order_date, status
    FROM orders
    WHERE order_date >= '2026-02-01' AND order_date < '2026-03-01'
      AND status <> 'shipped'
    ORDER BY order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 0 rows.</p>

    | order_id | order_date | status |
    | --- | --- | --- |
    | *(no rows)* | | |
    <!-- /result -->

    No rows: every February order was shipped. An empty result is a correct answer; a test can expect it. The
    half-open date range (`>=` the first, `<` the first of the next month) is the habit to keep: it works for dates
    and timestamps alike.

**Next:** [3. The order a query really runs in](03-The-Order-a-Query-Runs-In.md).
