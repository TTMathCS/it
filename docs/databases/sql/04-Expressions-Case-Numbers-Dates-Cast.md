# 4. Expressions: CASE, numbers, dates, CAST

*An expression computes a value from other values: a price with tax, a label from a number, the year of a date.
This chapter covers the building blocks used in every later query: arithmetic and its whole-number trap, rounding,
`CASE`, `COALESCE` and `NULLIF`, changing types with `CAST`, and a first look at dates. It is also where PostgreSQL
and SQLite differ most in small ways, so every difference that can change a test answer is run on both.*

!!! abstract "In this chapter"
    **You will learn:**

    - arithmetic, and why `7 / 2` is `3`
    - `ROUND`, `CEIL`, `FLOOR`, and the PostgreSQL error `function round(double precision, integer) does not exist`
    - `CASE` in its two forms, and why the order of the `WHEN`s matters
    - `COALESCE` for defaults and `NULLIF` against division by zero
    - `CAST`, and the places where the two databases convert differently
    - date literals, today's date, adding days and taking out the year
    - true and false: PostgreSQL's `boolean` and SQLite's 1 and 0

    **You need:** [chapter 2](02-Select-Where-Order-By-Limit.md) and [chapter 3](03-The-Order-a-Query-Runs-In.md).

## 4.1 Arithmetic { #arithmetic }

`+`, `-`, `*`, `/` and `%` (remainder) work as expected, with one catch: when **both** sides of `/` are whole
numbers, the result is a whole number, cut toward zero.

<!-- sql -->
```sql
SELECT 7 / 2      AS int_div,
       7 / 2.0    AS dec_div,
       -7 / 2     AS neg_div,
       7 % 3      AS remainder;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| int_div | dec_div | neg_div | remainder |
| --- | --- | --- | --- |
| 3 | 3.5000000000000000 | -3 | 1 |
<!-- /result -->

`7 / 2` is `3`, not `3.5`, on PostgreSQL, SQLite and SQL Server; MySQL returns `3.5000` and Oracle `3.5`. Make one side a
decimal (`2.0`, or `1.0 *` in front) whenever you divide counts. Do not reach for `CAST(... AS NUMERIC)` for this: on
SQLite it leaves a whole number whole ([section 4.5](#cast) shows it). This is the reason for most wrong
percentages in tests; [chapter 7](07-Aggregation-Group-By-Having.md#division) shows it with real counts.

Division by zero is where the databases part ways:

<!-- sql pgerror -->
```sql
SELECT 10 / 0 AS result;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>division by zero</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 1 row.</p>
<!-- /result -->

PostgreSQL stops with an error; SQLite (and MySQL) quietly return NULL. Never rely on the quiet version. Guard the
divisor with `NULLIF` ([section 4.4](#coalesce-nullif)).

## 4.2 Rounding { #rounding }

`ROUND(x, n)` rounds to n decimal places; `ROUND(x)` to a whole number. `CEIL` rounds up and `FLOOR` rounds down
(`CEILING` also works on PostgreSQL). `ABS` drops the sign.

<!-- sql -->
```sql
SELECT ROUND(18.456, 2) AS r2,
       ROUND(2.5)       AS r_half,
       CEIL(2.1)        AS up,
       FLOOR(-2.1)      AS down,
       ABS(-3)          AS absolute;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| r2 | r_half | up | down | absolute |
| --- | --- | --- | --- | --- |
| 18.46 | 3 | 3 | -3 | 3 |
<!-- /result -->

`FLOOR(-2.1)` is `-3`: down means toward minus infinity, not toward zero. (In SQLite, `CEIL` and `FLOOR` come with
its optional maths functions, which recent builds include; very old copies lack them.)

### The PostgreSQL ROUND error { #round-error }

PostgreSQL has two families of decimal numbers: exact `NUMERIC` (also called `DECIMAL`) and approximate floating
point, `DOUBLE PRECISION` (also `FLOAT`) and `REAL`. `ROUND(x, n)` with a number of places exists **only for
`NUMERIC`**:

<!-- sql pgerror -->
```sql
SELECT ROUND(CAST(10 AS DOUBLE PRECISION) / 3, 2) AS third;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>function round(double precision, integer) does not exist</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 1 row.</p>
<!-- /result -->

You meet this error without writing `DOUBLE PRECISION` yourself: some functions return floating point, such as
`EXTRACT` before PostgreSQL 14, `random()`, and `AVG` of a `REAL` column. The fix is to cast to `NUMERIC` first:

<!-- sql -->
```sql
SELECT ROUND(CAST(CAST(10 AS DOUBLE PRECISION) / 3 AS NUMERIC), 2) AS third;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| third |
| --- |
| 3.33 |
<!-- /result -->

On PostgreSQL the short form is `ROUND((10::float / 3)::numeric, 2)`; `::` is PostgreSQL's own cast operator and
does not run on SQLite. In a test, `CAST(... AS NUMERIC)` works on both.

!!! note "Halfway cases"
    `ROUND(2.5)` gives 3 on both databases. PostgreSQL rounds **floating point** halves to the
    nearest even number instead (`ROUND(CAST(2.5 AS DOUBLE PRECISION))` is 2), and floating point cannot store most
    decimals exactly anyway. Money and anything a test will compare to the cent should be `NUMERIC`, as the prices
    here are.

## 4.3 CASE { #case }

`CASE` is SQL's "if". The **searched** form tests conditions in order and returns the first match:

**Task:** Label every product 'premium' (100 or more), 'mid' (20 or more) or 'budget': name, price and `band`, most expensive first (ties by name).

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT name, price,
           CASE
             WHEN price >= 100 THEN 'premium'
             WHEN price >= 20  THEN 'mid'
             ELSE 'budget'
           END AS band
    FROM products
    ORDER BY price DESC, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 11 rows.</p>

    | name | price | band |
    | --- | --- | --- |
    | Office chair | 149.00 | premium |
    | Monitor stand | 32.00 | mid |
    | Tea kettle | 32.00 | mid |
    | Gift card | 25.00 | mid |
    | Desk lamp | 24.50 | mid |
    | Wall clock | 24.50 | mid |
    | Fountain pen | 18.00 | budget |
    | Plant pot | 12.25 | budget |
    | Bookend | 9.50 | budget |
    | Coffee mug | 8.75 | budget |
    | Notebook | 3.25 | budget |
    <!-- /result -->

Without `ELSE`, a row that matches no `WHEN` gets NULL. The **simple** form compares one expression with values:

**Task:** For orders 112 to 116, show the status and a `stage`: 'done' for shipped, 'waiting' for pending, by order id.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT order_id, status,
           CASE status
             WHEN 'shipped'   THEN 'done'
             WHEN 'pending'   THEN 'waiting'
           END AS stage
    FROM orders
    WHERE order_id BETWEEN 112 AND 116
    ORDER BY order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | order_id | status | stage |
    | --- | --- | --- |
    | 112 | shipped | done |
    | 113 | cancelled | *NULL* |
    | 114 | shipped | done |
    | 115 | shipped | done |
    | 116 | pending | waiting |
    <!-- /result -->

Order 113 is cancelled, which no `WHEN` names, so its stage is NULL. The simple form cannot test for NULL:
`CASE x WHEN NULL THEN ...` never matches, because it compares with `=`. Use `CASE WHEN x IS NULL THEN ...`.

!!! failure "The usual wrong answer: the WHENs in the wrong order"
    <!-- sql -->
    ```sql
    SELECT name, price,
           CASE
             WHEN price >= 20  THEN 'mid'
             WHEN price >= 100 THEN 'premium'
             ELSE 'budget'
           END AS band
    FROM products
    WHERE price >= 100;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | name | price | band |
    | --- | --- | --- |
    | Office chair | 149.00 | mid |
    <!-- /result -->

    The office chair costs 149.00, and still comes out as `mid`. `CASE` stops at the first true `WHEN`, and
    `price >= 20` is true first. Put the narrowest condition first.

`CASE` can go anywhere an expression can: in `ORDER BY` for a custom order, and inside aggregates to count with a
condition ([chapter 7](07-Aggregation-Group-By-Having.md#conditional)). A custom order:

**Task:** List orders 112 to 119 with pending first, then shipped, then the rest; by order id within each.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT order_id, status
    FROM orders
    WHERE order_id BETWEEN 112 AND 119
    ORDER BY CASE status WHEN 'pending' THEN 1 WHEN 'shipped' THEN 2 ELSE 3 END,
             order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 8 rows.</p>

    | order_id | status |
    | --- | --- |
    | 116 | pending |
    | 119 | pending |
    | 112 | shipped |
    | 114 | shipped |
    | 115 | shipped |
    | 117 | shipped |
    | 118 | shipped |
    | 113 | cancelled |
    <!-- /result -->

All the `THEN` results of one `CASE` should be the same type. PostgreSQL refuses `CASE WHEN ... THEN 'none' ELSE
price END` (text and a number); SQLite allows it. Cast one side so they match.

## 4.4 COALESCE and NULLIF { #coalesce-nullif }

`COALESCE(a, b, ...)` returns the first argument that is not NULL: a default for missing values.

**Task:** For customers 3, 5 and 8, show the email or 'no email', and the city or, when it is missing, the country, as `place`.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT customer_id, name,
           COALESCE(email, 'no email') AS email,
           COALESCE(city, country)     AS place
    FROM customers
    WHERE customer_id IN (3, 5, 8)
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | customer_id | name | email | place |
    | --- | --- | --- | --- |
    | 3 | Chen Wei | no email | Shanghai |
    | 5 | Eli Cohen | eli@example.com | Israel |
    | 8 | Hana Sato | no email | Osaka |
    <!-- /result -->

`NULLIF(a, b)` does the opposite: it returns NULL when `a = b`, otherwise `a`. Its main use is a safe divisor:
dividing by NULL gives NULL instead of an error.

**Task:** For the numbers 0, 4 and 5, show 100 divided by each, with NULL instead of an error for 0.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT n, 100 / NULLIF(n, 0) AS hundred_over_n
    FROM (SELECT 0 AS n UNION ALL SELECT 4 UNION ALL SELECT 5) AS t
    ORDER BY n;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | n | hundred_over_n |
    | --- | --- |
    | 0 | *NULL* |
    | 4 | 25 |
    | 5 | 20 |
    <!-- /result -->

(The `(SELECT 0 AS n UNION ALL ...)` builds a tiny table of three numbers on the spot; [chapter 12](12-Set-Operations.md)
explains `UNION ALL`.) The pair `COALESCE(x / NULLIF(y, 0), 0)` turns "divide, but 0 when there is nothing to divide
by" into one line. [Chapter 6](06-Null-and-Three-Valued-Logic.md) covers NULL in full.

## 4.5 CAST: changing types { #cast }

`CAST(value AS type)` converts a value. The common targets are `INTEGER`, `NUMERIC` (or `DECIMAL(p, s)`), `TEXT`
(`VARCHAR` on some databases) and `DATE`.

**Task:** Turn the text '42' into a number, and product 2's price into text.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT CAST('42' AS INTEGER)      AS from_text,
           CAST(price AS TEXT)        AS price_text
    FROM products
    WHERE product_id = 2;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | from_text | price_text |
    | --- | --- |
    | 42 | 3.25 |
    <!-- /result -->

PostgreSQL is strict about types and SQLite is relaxed, and a few conversions give **different answers**.

**Casting to NUMERIC to get decimals.** On PostgreSQL, `NUMERIC` is an exact decimal type, so this divides as
decimals:

<!-- sql pg -->
```sql
SELECT CAST(7 AS NUMERIC) / 2 AS half;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| half |
| --- |
| 3.5000000000000000 |
<!-- /result -->

<!-- sql sqlite -->
```sql
SELECT CAST(7 AS NUMERIC) / 2 AS half;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| half |
| --- |
| 3 |
<!-- /result -->

SQLite has no decimal type. `NUMERIC` there means "store it as a whole number if it is one, otherwise as floating
point", so `CAST(7 AS NUMERIC)` is still the whole number 7, and `7 / 2` is 3. `1.0 * 7 / 2` (or `CAST(7 AS REAL)`)
gives 3.5 on both.

**Decimal to integer** is the other conversion that matters:

<!-- sql pg -->
```sql
SELECT CAST(3.99 AS INTEGER) AS pos, CAST(-3.99 AS INTEGER) AS neg;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| pos | neg |
| --- | --- |
| 4 | -4 |
<!-- /result -->

<!-- sql sqlite -->
```sql
SELECT CAST(3.99 AS INTEGER) AS pos, CAST(-3.99 AS INTEGER) AS neg;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

| pos | neg |
| --- | --- |
| 3 | -3 |
<!-- /result -->

PostgreSQL **rounds** (4 and -4); SQLite **cuts off** the decimals (3 and -3). SQL Server and MySQL also differ
(SQL Server cuts off, MySQL rounds). When the question says "round", write `ROUND`; when it says "whole part", write
`FLOOR` (for positive numbers) or `TRUNC` (PostgreSQL, and SQLite with its maths functions). Never let `CAST` decide.

Text that is not a number is the other difference:

<!-- sql pgerror -->
```sql
SELECT CAST('12abc' AS INTEGER) AS n;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>invalid input syntax for type integer: "12abc"</code></p>
<p class="sql-tested sql-noerror">SQLite 3.53: no error, it runs and returns 1 row.</p>
<!-- /result -->

SQLite reads the leading digits and ignores the rest, returning 12; PostgreSQL refuses. When you load messy data,
PostgreSQL's error is the friend: it tells you about the bad row instead of storing a wrong number. [Chapter
23](23-Data-Quality-Checks.md) shows how to find such rows before casting.

!!! tip "Interview tip: numbers stored as text sort as text"
    `'10' < '9'` is true for text, because `'1'` comes before `'9'`. If a column of numbers is stored as text,
    `ORDER BY` and `MAX` work alphabetically and give wrong answers: cast first, `ORDER BY CAST(code AS INTEGER)`.

## 4.6 Dates: a first look { #dates }

PostgreSQL has real `DATE`, `TIMESTAMP` and `INTERVAL` types. SQLite has none: it stores dates as text
(`'2026-03-15'`) and has functions that understand that text. The ISO format `YYYY-MM-DD` works on both and sorts
correctly as text, which is why the shop uses it everywhere.

Adding days and taking out the year are written differently:

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT order_id, order_date,
           order_date + 7                 AS due_date,
           EXTRACT(YEAR FROM order_date)  AS yr,
           EXTRACT(MONTH FROM order_date) AS mon
    FROM orders
    WHERE order_id IN (101, 112, 120)
    ORDER BY order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | order_id | order_date | due_date | yr | mon |
    | --- | --- | --- | --- | --- |
    | 101 | 2026-01-03 | 2026-01-10 | 2026 | 1 |
    | 112 | 2026-03-01 | 2026-03-08 | 2026 | 3 |
    | 120 | 2026-04-05 | 2026-04-12 | 2026 | 4 |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    SELECT order_id, order_date,
           date(order_date, '+7 days')                    AS due_date,
           CAST(strftime('%Y', order_date) AS INTEGER)    AS yr,
           CAST(strftime('%m', order_date) AS INTEGER)    AS mon
    FROM orders
    WHERE order_id IN (101, 112, 120)
    ORDER BY order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 3 rows.</p>

    | order_id | order_date | due_date | yr | mon |
    | --- | --- | --- | --- | --- |
    | 101 | 2026-01-03 | 2026-01-10 | 2026 | 1 |
    | 112 | 2026-03-01 | 2026-03-08 | 2026 | 3 |
    | 120 | 2026-04-05 | 2026-04-12 | 2026 | 4 |
    <!-- /result -->

What the pieces do: on PostgreSQL, `order_date + 7` adds 7 days and `EXTRACT(YEAR FROM d)` takes out one part of a
date as a number. On SQLite, `date(d, '+7 days')` moves a date, and `strftime('%Y', d)` formats a date as text
(`%Y` the year, `%m` the month, `%d` the day), which `CAST(... AS INTEGER)` turns into a number.

A few more facts worth knowing now, all covered with examples in [chapter 16](16-Dates-and-Time-Series.md):

- Today: `CURRENT_DATE` works on both; SQLite also has `date('now')`. Both give the date in UTC on SQLite, and in the
  session's time zone on PostgreSQL.
- PostgreSQL writes a date literal as `DATE '2026-03-15'`; a plain `'2026-03-15'` also works where the other side is
  a date. On SQLite, `DATE '...'` is not valid; write the text.
- One date minus another is a whole number of days on PostgreSQL; SQLite needs `julianday(a) - julianday(b)`.
- PostgreSQL rejects an impossible date such as `'2026-02-30'`; SQLite's `date('2026-02-30')` quietly returns
  `2026-03-02`. Check dates from outside before trusting them.

## 4.7 True and false { #booleans }

A comparison is itself an expression with a true or false value, and it can be selected:

**Task:** For the Kitchen products, show name, price and whether the price is over 20 (true or false), by product id.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT name, price, price > 20 AS over_20
    FROM products
    WHERE category = 'Kitchen'
    ORDER BY product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | name | price | over_20 |
    | --- | --- | --- |
    | Coffee mug | 8.75 | false |
    | Tea kettle | 32.00 | true |
    <!-- /result -->

PostgreSQL has a `boolean` type and shows `true` and `false` (`t` and `f` in its `psql` program). SQLite has no
boolean type: a comparison gives 1 or 0, and `TRUE` and `FALSE` are just other names for 1 and 0. The rows above
are the same on both; only the display differs. This is why counting with a condition is written portably as
`SUM(CASE WHEN ... THEN 1 ELSE 0 END)`: `SUM(price > 20)` works on SQLite and MySQL but is an error on PostgreSQL,
which cannot add booleans.

## 4.8 Summary { #summary }

- Whole number / whole number is a whole number on PostgreSQL and SQLite. Multiply by `1.0` or cast first.
- Division by zero: an error on PostgreSQL, NULL on SQLite. Guard with `NULLIF(divisor, 0)`.
- `ROUND(x, n)` on PostgreSQL needs `NUMERIC`: `ROUND(CAST(x AS NUMERIC), n)`.
- `CASE` returns the first true `WHEN`; put the narrowest first; no `ELSE` means NULL.
- `COALESCE` picks the first non-NULL value; `NULLIF` turns a value into NULL.
- `CAST(3.99 AS INTEGER)` is 4 on PostgreSQL and 3 on SQLite. Say what you mean with `ROUND` or `FLOOR`.
- `CAST(x AS NUMERIC)` gives exact decimals on PostgreSQL but leaves whole numbers whole on SQLite, where decimal
  arithmetic is floating point. For decimal division write `1.0 *`.
- Write dates as `YYYY-MM-DD`. Date arithmetic differs by database; chapter 16 has the full list.
- Comparisons are booleans on PostgreSQL and 1 or 0 on SQLite; count with `SUM(CASE ...)`.

## Practice { #practice }

**4.1** For the Home products: `name`, `price`, and `price_with_tax` (price × 1.13, rounded to 2 places). Cheapest
first, then by name. Run it on both databases and compare the answers.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT name, price, ROUND(price * 1.13, 2) AS price_with_tax
    FROM products
    WHERE category = 'Home'
    ORDER BY price, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | name | price | price_with_tax |
    | --- | --- | --- |
    | Bookend | 9.50 | 10.74 |
    | Plant pot | 12.25 | 13.84 |
    | Desk lamp | 24.50 | 27.69 |
    | Wall clock | 24.50 | 27.69 |
    <!-- /result -->

    <!-- sql sqlite -->
    ```sql
    SELECT name, price, ROUND(price * 1.13, 2) AS price_with_tax
    FROM products
    WHERE category = 'Home'
    ORDER BY price, name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 4 rows.</p>

    | name | price | price_with_tax |
    | --- | --- | --- |
    | Bookend | 9.5 | 10.73 |
    | Plant pot | 12.25 | 13.84 |
    | Desk lamp | 24.5 | 27.68 |
    | Wall clock | 24.5 | 27.68 |
    <!-- /result -->

    The bookend and the two 24.50 products differ by a cent. 9.50 × 1.13 is exactly 10.735. PostgreSQL works in exact
    `NUMERIC` and rounds the half up to 10.74; SQLite works in floating point, where 10.735 is stored as a hair below
    it (10.73499999...), so it rounds down to 10.73. Neither is a bug. A test's checker normally computes its expected
    answer on the same database as yours, so this rarely costs marks, but it explains a one-cent difference when you
    compare with an answer computed elsewhere. `price` is `NUMERIC` on PostgreSQL, so `ROUND(..., 2)` works there
    directly; had it been floating point, it would need `CAST(... AS NUMERIC)` first.

**4.2** Label each employee's salary: `high` for 120,000 and over, `medium` from 70,000 up to (not including) 120,000, `low` below
70,000, and `unknown` when it is missing. Return `name`, `salary`, `band`, by `employee_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name, salary,
           CASE
             WHEN salary IS NULL   THEN 'unknown'
             WHEN salary >= 120000 THEN 'high'
             WHEN salary >= 70000  THEN 'medium'
             ELSE 'low'
           END AS band
    FROM employees
    ORDER BY employee_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 12 rows.</p>

    | name | salary | band |
    | --- | --- | --- |
    | Maya Rossi | 180000 | high |
    | Tom Becker | 140000 | high |
    | Priya Nair | 120000 | high |
    | Sam Lee | 120000 | high |
    | Lucia Gomez | 95000 | medium |
    | Omar Aziz | 110000 | medium |
    | Nina Berg | 70000 | medium |
    | Raj Patel | 70000 | medium |
    | Zoe Martin | 65000 | low |
    | Kwame Mensah | 75000 | medium |
    | Ella Novak | 52000 | low |
    | Leo Park | *NULL* | unknown |
    <!-- /result -->

    Without the `IS NULL` line, Leo Park would fall through every `WHEN` (a comparison with NULL is never true) and
    land in `ELSE`: labelled `low`, which is wrong.

**4.3** What do these return on PostgreSQL? `SELECT 5 / 2, 5 % 2, 5 / 2.0, CAST(2.5 AS INTEGER)`. Then on SQLite.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT 5 / 2 AS a, 5 % 2 AS b, 5 / 2.0 AS c, CAST(2.5 AS INTEGER) AS d;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

    | a | b | c | d |
    | --- | --- | --- | --- |
    | 2 | 1 | 2.5000000000000000 | 3 |
    <!-- /result -->

    <!-- sql sqlite -->
    ```sql
    SELECT 5 / 2 AS a, 5 % 2 AS b, 5 / 2.0 AS c, CAST(2.5 AS INTEGER) AS d;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

    | a | b | c | d |
    | --- | --- | --- | --- |
    | 2 | 1 | 2.5 | 2 |
    <!-- /result -->

    The same except the last column: PostgreSQL rounds 2.5 to 3 (halves away from zero for exact numbers), SQLite
    cuts it to 2.

**4.4** For each sale line where the price paid differs from today's list price, the discount as a percentage of the
list price, rounded to 1 place. Return `order_id`, `product_id`, `list_price`, `unit_price`, `discount_pct`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT i.order_id, i.product_id, p.price AS list_price, i.unit_price,
           ROUND(100.0 * (p.price - i.unit_price) / p.price, 1) AS discount_pct
    FROM order_items i
    JOIN products p ON p.product_id = i.product_id
    WHERE i.unit_price <> p.price
    ORDER BY i.order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | order_id | product_id | list_price | unit_price | discount_pct |
    | --- | --- | --- | --- | --- |
    | 109 | 5 | 32.00 | 30.00 | 6.3 |
    | 120 | 6 | 149.00 | 139.00 | 6.7 |
    <!-- /result -->

    This needs a join, which [chapter 8](08-Joins-Inner-Left-Right-Full-Cross.md) teaches; the expression is the
    point here. `100.0 *` keeps the division decimal (here both prices are `NUMERIC` anyway, but the habit is free).

**4.5** Sort the orders of March 2026 so that pending orders come first, then shipped, then cancelled, and by date
within each. Return `order_id`, `order_date`, `status`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT order_id, order_date, status
    FROM orders
    WHERE order_date >= '2026-03-01' AND order_date < '2026-04-01'
    ORDER BY CASE status WHEN 'pending' THEN 1 WHEN 'shipped' THEN 2 WHEN 'cancelled' THEN 3 END,
             order_date, order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 6 rows.</p>

    | order_id | order_date | status |
    | --- | --- | --- |
    | 116 | 2026-03-22 | pending |
    | 112 | 2026-03-01 | shipped |
    | 114 | 2026-03-09 | shipped |
    | 115 | 2026-03-18 | shipped |
    | 117 | 2026-03-25 | shipped |
    | 113 | 2026-03-05 | cancelled |
    <!-- /result -->

    `CASE` turns each status into a number (pending 1, shipped 2, cancelled 3), and the rows are sorted by that
    number. This is how to sort in an order that is not alphabetical. `order_date` and then `order_id` sort the
    rows within each status, so the order is the same on every run.


**Next:** [5. Text functions and pattern matching](05-Text-Functions-and-Pattern-Matching.md).
