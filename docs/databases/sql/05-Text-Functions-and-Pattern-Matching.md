# 5. Text functions and pattern matching

*Names, emails, codes and free text need cleaning, cutting and matching. This chapter covers the text functions that
come up in tests and in real data work: joining text, changing case, taking pieces out, trimming, replacing, `LIKE`
patterns, regular expressions, and gluing many rows into one string. Text is where PostgreSQL and SQLite differ most
in function names, and in one place where the same query gives different rows: `LIKE` and capital letters.*

!!! abstract "In this chapter"
    **You will learn:**

    - joining text with `||` and `CONCAT`, and what each does with NULL
    - `LENGTH`, `UPPER`, `LOWER`, `SUBSTR`, `TRIM`, `REPLACE`
    - finding a character and splitting text at it (an email's domain), on both databases
    - comparing text without caring about capitals
    - `LIKE` with `%` and `_`, why it matches different rows on PostgreSQL and SQLite, and `ILIKE`
    - regular expressions on PostgreSQL
    - `STRING_AGG`: many rows into one comma-separated string

    **You need:** [chapters 2](02-Select-Where-Order-By-Limit.md) and [4](04-Expressions-Case-Numbers-Dates-Cast.md).

## 5.1 Joining text { #concat }

`||` joins two pieces of text on PostgreSQL, SQLite and Oracle (the SQL standard spelling). If either side is NULL,
the result is NULL (except on Oracle, which treats NULL as empty text here). `CONCAT(...)` joins any number of pieces and **skips** NULLs:

<!-- sql -->
```sql
SELECT customer_id,
       name || ' <' || email || '>'      AS with_pipes,
       CONCAT(name, ' <', email, '>')    AS with_concat
FROM customers
WHERE customer_id IN (2, 3)
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| customer_id | with_pipes | with_concat |
| --- | --- | --- |
| 2 | Ben Okafor <ben@example.com> | Ben Okafor <ben@example.com> |
| 3 | *NULL* | Chen Wei <> |
<!-- /result -->

Chen Wei has no email, so `||` gives NULL for the whole value while `CONCAT` just leaves the email out. Neither is
"right"; choose on purpose, or say what a missing part should look like with `COALESCE(email, 'no email')`.
(`CONCAT` is in PostgreSQL, MySQL and SQL Server, and in SQLite from version 3.44. In MySQL, `||` means `OR` unless
a setting changes it, and `CONCAT` returns NULL if any piece is NULL; `CONCAT_WS(' ', ...)` is the one that skips
NULLs there.)

## 5.2 Length and case { #length-case }

<!-- sql -->
```sql
SELECT name,
       LENGTH(name) AS chars,
       UPPER(name)  AS upper_name,
       LOWER(name)  AS lower_name
FROM customers
WHERE customer_id IN (1, 6)
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| name | chars | upper_name | lower_name |
| --- | --- | --- | --- |
| Ana Silva | 9 | ANA SILVA | ana silva |
| Farah Haddad | 12 | FARAH HADDAD | farah haddad |
<!-- /result -->

`LENGTH` counts characters (SQL Server calls it `LEN`, and it ignores trailing spaces). SQLite's built-in `UPPER`
and `LOWER` change only the English letters A to Z; PostgreSQL also handles accented letters (`LOWER('À')` is `à`
there, but stays `À` on SQLite). PostgreSQL also has `INITCAP('ana silva')`, giving `Ana Silva`; SQLite does not.

## 5.3 Taking pieces out { #substr }

`SUBSTR(text, start, length)` takes `length` characters starting at position `start`. Positions count from **1**,
not 0. Leave out the length to take everything to the end.

<!-- sql -->
```sql
SELECT name,
       SUBSTR(name, 1, 3) AS first_three,
       SUBSTR(name, 5)    AS from_fifth
FROM customers
WHERE customer_id IN (1, 2)
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| name | first_three | from_fifth |
| --- | --- | --- |
| Ana Silva | Ana | Silva |
| Ben Okafor | Ben | Okafor |
<!-- /result -->

PostgreSQL also has `LEFT(text, n)` and `RIGHT(text, n)`, and the standard form `SUBSTRING(text FROM 2 FOR 3)`;
SQLite has neither (it accepts `SUBSTRING(text, 2, 3)` only as another name for `SUBSTR`), so `SUBSTR` is the
portable choice.

### Finding a character, and splitting at it { #split }

The position of one piece of text inside another is `STRPOS(text, '@')` (or the standard `POSITION('@' IN text)`)
on PostgreSQL, and `INSTR(text, '@')` on SQLite and MySQL. Both return 0 when it is not there. Cutting an email
into its name and its domain is a common task:

=== "PostgreSQL"

    <!-- sql pg -->
    ```sql
    SELECT email,
           SUBSTR(email, 1, STRPOS(email, '@') - 1) AS local_part,
           SUBSTR(email, STRPOS(email, '@') + 1)    AS domain
    FROM customers
    WHERE customer_id IN (1, 10)
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | email | local_part | domain |
    | --- | --- | --- |
    | ana@example.com | ana | example.com |
    | ana.silva@example.com | ana.silva | example.com |
    <!-- /result -->

=== "SQLite"

    <!-- sql sqlite same -->
    ```sql
    SELECT email,
           SUBSTR(email, 1, INSTR(email, '@') - 1) AS local_part,
           SUBSTR(email, INSTR(email, '@') + 1)    AS domain
    FROM customers
    WHERE customer_id IN (1, 10)
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 2 rows.</p>

    | email | local_part | domain |
    | --- | --- | --- |
    | ana@example.com | ana | example.com |
    | ana.silva@example.com | ana.silva | example.com |
    <!-- /result -->

PostgreSQL has a shorter way: `SPLIT_PART(email, '@', 2)` returns the second piece when the text is cut at every
`@`. It also gives the first word of a name, `SPLIT_PART(name, ' ', 1)`. SQLite has no split function; the
`SUBSTR` and `INSTR` pair is the way there.

## 5.4 Trimming and replacing { #trim-replace }

`TRIM` removes spaces from both ends; `LTRIM` and `RTRIM` from one end. Given a second argument, they remove those
characters instead. `REPLACE(text, from, to)` replaces every copy of one piece of text.

<!-- sql -->
```sql
SELECT '[' || TRIM('   Toronto  ') || ']'   AS trimmed,
       LTRIM('000120', '0')                AS no_leading_zeros,
       REPLACE('416-555-0199', '-', '')     AS digits_only;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| trimmed | no_leading_zeros | digits_only |
| --- | --- | --- |
| [Toronto] | 120 | 4165550199 |
<!-- /result -->

Spaces at the ends are a classic reason for a join or a `GROUP BY` to miss: `'Toronto '` is not equal to
`'Toronto'`. Trimming (and lower-casing) both sides before comparing is the first step of most data clean-ups
([chapter 23](23-Data-Quality-Checks.md)). The standard SQL spelling is
`TRIM(LEADING '0' FROM x)`, which PostgreSQL accepts and SQLite does not; `LTRIM(x, '0')` works on both.

A handy trick: the number of times a letter appears is the length lost when you remove it.

<!-- sql -->
```sql
SELECT name, LENGTH(name) - LENGTH(REPLACE(LOWER(name), 'a', '')) AS letter_a
FROM customers
WHERE customer_id <= 4
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

| name | letter_a |
| --- | --- |
| Ana Silva | 3 |
| Ben Okafor | 1 |
| Chen Wei | 0 |
| Dana Kim | 2 |
<!-- /result -->

## 5.5 Comparing text and capital letters { #case-sensitive }

`=` on text is **case-sensitive** on PostgreSQL and SQLite: `'ana silva' = 'Ana Silva'` is false. (MySQL and SQL
Server usually compare without regard to case, because of their default collation; check, never assume.) To compare
without caring about capitals, lower-case both sides:

<!-- sql -->
```sql
SELECT customer_id, name
FROM customers
WHERE LOWER(name) = LOWER('ANA SILVA')
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| customer_id | name |
| --- | --- |
| 1 | Ana Silva |
| 10 | Ana Silva |
<!-- /result -->

Sorting text also depends on the database's **collation**, its rules for which letter comes first. Whether `'ab'`
sorts before `'B'` differs between a plain byte order (capitals first) and a language-aware one. For a test this
rarely matters, because names usually start with a capital; when it does, sort by `LOWER(name)`.

## 5.6 LIKE { #like }

`LIKE` matches a pattern: `%` stands for any number of characters (including none) and `_` for exactly one.

<!-- sql -->
```sql
SELECT name
FROM products
WHERE name LIKE '%o_k%'
ORDER BY name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| name |
| --- |
| Bookend |
| Notebook |
| Wall clock |
<!-- /result -->

`%o_k%` means "anything, an o, any one character, a k, anything": `Bookend` and `Notebook` match through "ook", and
`Wall clock` through "ock".
`NOT LIKE` turns it around. To match a real `%` or `_`, mark it with an escape character:
`LIKE '%\_%' ESCAPE '\'`.

### The same LIKE, different rows { #like-case }

Here is the trap. `LIKE` is case-sensitive on PostgreSQL, but **not** on SQLite (for the letters A to Z):

<!-- sql pg -->
```sql
SELECT customer_id, name
FROM customers
WHERE name LIKE 'ana%'
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 0 rows.</p>

| customer_id | name |
| --- | --- |
| *(no rows)* | |
<!-- /result -->

<!-- sql sqlite -->
```sql
SELECT customer_id, name
FROM customers
WHERE name LIKE 'ana%'
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on SQLite 3.53. 2 rows.</p>

| customer_id | name |
| --- | --- |
| 1 | Ana Silva |
| 10 | Ana Silva |
<!-- /result -->

PostgreSQL found nothing, because every name starts with a capital. SQLite found both Ana Silvas. MySQL behaves like
SQLite with its default collation; SQL Server depends on its collation, usually case-insensitive.

PostgreSQL's case-insensitive version is `ILIKE`, which SQLite does not have. The portable answer works the same on
every database:

<!-- sql -->
```sql
SELECT customer_id, name
FROM customers
WHERE LOWER(name) LIKE 'ana%'
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| customer_id | name |
| --- | --- |
| 1 | Ana Silva |
| 10 | Ana Silva |
<!-- /result -->

!!! tip "Interview tip"
    If a test question says "names starting with a" and does not mention capitals, ask yourself which it means, and
    write `LOWER(name) LIKE 'a%'`: it is correct on every database and shows you knew about the difference. If the
    question clearly means an exact, case-sensitive match on SQLite, `GLOB 'A*'` is SQLite's case-sensitive pattern
    match (with `*` and `?` in place of `%` and `_`).

A pattern that starts with `%` cannot use an ordinary index, so `LIKE '%son'` reads the whole table;
[chapter 26](26-Making-Slow-Queries-Fast.md) has the details.

## 5.7 Regular expressions (PostgreSQL) { #regex }

For patterns `LIKE` cannot express, PostgreSQL has regular expressions: `~` (matches, case-sensitive), `~*`
(case-insensitive), and `!~` and `!~*` for "does not match".

<!-- sql pg -->
```sql
SELECT name
FROM products
WHERE name ~ '^[A-Z][a-z]+ [a-z]+$'
ORDER BY name;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 9 rows.</p>

| name |
| --- |
| Coffee mug |
| Desk lamp |
| Fountain pen |
| Gift card |
| Monitor stand |
| Office chair |
| Plant pot |
| Tea kettle |
| Wall clock |
<!-- /result -->

The pattern means "a capital, some small letters, one space, some small letters, and nothing else": two-word product
names. Three functions do most of the work:

<!-- sql pg -->
```sql
SELECT email,
       REGEXP_REPLACE(email, '^(.).*@', '\1***@') AS masked,
       SUBSTRING(email FROM '@(.*)$')             AS domain,
       email ~ '^[^@]+@[^@]+\.[a-z]+$'            AS looks_valid
FROM customers
WHERE email IS NOT NULL AND customer_id <= 4
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

| email | masked | domain | looks_valid |
| --- | --- | --- | --- |
| ana@example.com | a***@example.com | example.com | true |
| ben@example.com | b***@example.com | example.com | true |
| dana@example.com | d***@example.com | example.com | true |
<!-- /result -->

`REGEXP_REPLACE` rewrites the match (`\1` is the first group in brackets); `SUBSTRING(... FROM pattern)` returns the
part in brackets; `~` gives true or false. PostgreSQL also has `REGEXP_MATCHES`, `REGEXP_SPLIT_TO_TABLE` and, from
version 15, `REGEXP_COUNT` and `REGEXP_LIKE`.

SQLite has the syntax `x REGEXP pattern`, but no built-in function behind it: unless the program using SQLite adds
one, it fails with "no such function: REGEXP" (the `sqlite3` command-line program does add one; Python's `sqlite3`
module and most libraries do not). In a test on SQLite, use `LIKE`, `GLOB`, `INSTR` and `SUBSTR`
instead. MySQL has `REGEXP` / `REGEXP_LIKE`; SQL Server only recently gained regular expression functions (in SQL
Server 2025), so older versions use `LIKE` with character ranges like `[0-9]`.

## 5.8 Many rows into one string { #string-agg }

`STRING_AGG(text, separator)` is an aggregate: it glues the values of a group into one piece of text. Put an
`ORDER BY` inside it, or the order of the pieces is not guaranteed:

<!-- sql -->
```sql
SELECT category, STRING_AGG(name, ', ' ORDER BY name) AS products
FROM products
WHERE category IS NOT NULL
GROUP BY category
ORDER BY category;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

| category | products |
| --- | --- |
| Home | Bookend, Desk lamp, Plant pot, Wall clock |
| Kitchen | Coffee mug, Tea kettle |
| Office | Fountain pen, Monitor stand, Notebook, Office chair |
<!-- /result -->

`STRING_AGG` with `ORDER BY` inside works on PostgreSQL and on SQLite from version 3.44. Older SQLite and MySQL
call it `GROUP_CONCAT` (MySQL: `GROUP_CONCAT(name ORDER BY name SEPARATOR ', ')`); SQL Server writes
`STRING_AGG(name, ', ') WITHIN GROUP (ORDER BY name)`; Oracle and Snowflake have `LISTAGG`. NULL values are skipped.
The reverse, one string into many rows, is PostgreSQL's `STRING_TO_TABLE` or `UNNEST(STRING_TO_ARRAY(...))`
([chapter 24](24-JSON-and-Arrays.md)).

## 5.9 Function names side by side { #names }

| Task | PostgreSQL | SQLite | Portable |
| --- | --- | --- | --- |
| join text | <code>a &#124;&#124; b</code>, `CONCAT(a, b)` | <code>a &#124;&#124; b</code>, `CONCAT` (3.44+) | <code>&#124;&#124;</code> (NULL makes NULL; not MySQL or SQL Server) |
| length | `LENGTH` | `LENGTH` | `LENGTH` (SQL Server: `LEN`) |
| piece | `SUBSTR`, `SUBSTRING`, `LEFT`, `RIGHT` | `SUBSTR` | `SUBSTR(s, start, len)` |
| find | `STRPOS(s, x)`, `POSITION(x IN s)` | `INSTR(s, x)` | none |
| split | `SPLIT_PART(s, '@', 2)` | `SUBSTR` + `INSTR` | none |
| case-insensitive match | `ILIKE`, `~*` | `LIKE` already is | `LOWER(s) LIKE 'x%'` |
| regular expression | `~`, `REGEXP_REPLACE` | not built in | none |
| pad | `LPAD('7', 3, '0')` | `printf('%03d', 7)` | none |
| rows into a string | `STRING_AGG` | `STRING_AGG` (3.44+), `GROUP_CONCAT` | `STRING_AGG` on these two |

## 5.10 Summary { #summary }

- `||` makes NULL if any part is NULL; `CONCAT` skips NULLs.
- Positions in text count from 1. `SUBSTR` is the portable way to take pieces.
- Finding a character: `STRPOS` on PostgreSQL, `INSTR` on SQLite. Split with `SPLIT_PART` or `SUBSTR` + `INSTR`.
- `TRIM` and `LOWER` before comparing text from different sources.
- `=` is case-sensitive on both. `LIKE` is case-sensitive on PostgreSQL and not on SQLite. Write
  `LOWER(x) LIKE 'pattern'` to get the same rows everywhere.
- Regular expressions are built into PostgreSQL, not SQLite.
- `STRING_AGG(x, ', ' ORDER BY x)` turns a group into one string.

## Practice { #practice }

**5.1** The number of customers per email domain, most first, then by domain. Customers without an email are left out.
Return `domain`, `customers`.

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        SELECT SPLIT_PART(email, '@', 2) AS domain, COUNT(*) AS customers
        FROM customers
        WHERE email IS NOT NULL
        GROUP BY SPLIT_PART(email, '@', 2)
        ORDER BY customers DESC, domain;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

        | domain | customers |
        | --- | --- |
        | example.com | 8 |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        SELECT SUBSTR(email, INSTR(email, '@') + 1) AS domain, COUNT(*) AS customers
        FROM customers
        WHERE email IS NOT NULL
        GROUP BY SUBSTR(email, INSTR(email, '@') + 1)
        ORDER BY customers DESC, domain;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 1 row.</p>

        | domain | customers |
        | --- | --- |
        | example.com | 8 |
        <!-- /result -->

    Every customer here uses example.com, so there is one row with 8. Without `WHERE email IS NOT NULL`, the two
    customers with no email would form a group of their own with a NULL domain.

**5.2** Products whose name contains the letters "ee" or "oo" (any capitals). Return `name`, alphabetically. Make the
answer give the same rows on both databases.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT name
    FROM products
    WHERE LOWER(name) LIKE '%ee%' OR LOWER(name) LIKE '%oo%'
    ORDER BY name;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | name |
    | --- |
    | Bookend |
    | Coffee mug |
    | Notebook |
    <!-- /result -->

    With `AND` instead of `OR` you would get names containing both. The `LOWER` makes no difference to these rows, but
    it is what makes the answer safe for a name such as "OOlong tea".

**5.3** Each employee's initials, made from the first letter of each of their two names (Maya Rossi → MR). Return
`name`, `initials`, by `employee_id`, for employees 1 to 4.

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        SELECT name,
               SUBSTR(name, 1, 1) || SUBSTR(name, STRPOS(name, ' ') + 1, 1) AS initials
        FROM employees
        WHERE employee_id <= 4
        ORDER BY employee_id;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

        | name | initials |
        | --- | --- |
        | Maya Rossi | MR |
        | Tom Becker | TB |
        | Priya Nair | PN |
        | Sam Lee | SL |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        SELECT name,
               SUBSTR(name, 1, 1) || SUBSTR(name, INSTR(name, ' ') + 1, 1) AS initials
        FROM employees
        WHERE employee_id <= 4
        ORDER BY employee_id;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 4 rows.</p>

        | name | initials |
        | --- | --- |
        | Maya Rossi | MR |
        | Tom Becker | TB |
        | Priya Nair | PN |
        | Sam Lee | SL |
        <!-- /result -->

    The second initial is the character just after the space. On PostgreSQL,
    `LEFT(SPLIT_PART(name, ' ', 2), 1)` is another way to get it.

**5.4** For each department, the names of its employees in one string, alphabetically, separated by `; `. Return
`department`, `staff`, by department.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT department, STRING_AGG(name, '; ' ORDER BY name) AS staff
    FROM employees
    GROUP BY department
    ORDER BY department;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | department | staff |
    | --- | --- |
    | Engineering | Lucia Gomez; Priya Nair; Sam Lee; Tom Becker |
    | Management | Maya Rossi |
    | Sales | Nina Berg; Omar Aziz; Raj Patel; Zoe Martin |
    | Support | Ella Novak; Kwame Mensah; Leo Park |
    <!-- /result -->

    `STRING_AGG(name, '; ' ORDER BY name)` is an aggregate: like `SUM` adds numbers, it joins the group's texts
    into one, with `'; '` between them, in the order given. Without its own `ORDER BY`, the names come in any
    order.


**5.5** What does each database return for `SELECT COUNT(*) FROM products WHERE name LIKE 'office%'`, and why? Write a
version that returns 1 on both.

??? success "Answer"
    PostgreSQL returns 0 (its `LIKE` is case-sensitive and the name is "Office chair"); SQLite returns 1 (its `LIKE`
    ignores the case of A to Z).

    <!-- sql pg -->
    ```sql
    SELECT COUNT(*) AS n FROM products WHERE name LIKE 'office%';
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

    | n |
    | --- |
    | 0 |
    <!-- /result -->

    <!-- sql sqlite -->
    ```sql
    SELECT COUNT(*) AS n FROM products WHERE name LIKE 'office%';
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 1 row.</p>

    | n |
    | --- |
    | 1 |
    <!-- /result -->

    The version that agrees:

    <!-- sql -->
    ```sql
    SELECT COUNT(*) AS n FROM products WHERE LOWER(name) LIKE 'office%';
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | n |
    | --- |
    | 1 |
    <!-- /result -->

**5.6** Show each customer's email masked as its first letter, three stars, and the domain (`ana@example.com` →
`a***@example.com`), for customers who have one. Write it without regular expressions so it runs on SQLite too.
Return `customer_id`, `masked`.

??? success "Answer"
    <!-- sql sqlite -->
    ```sql
    SELECT customer_id,
           SUBSTR(email, 1, 1) || '***' || SUBSTR(email, INSTR(email, '@')) AS masked
    FROM customers
    WHERE email IS NOT NULL
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on SQLite 3.53. 8 rows.</p>

    | customer_id | masked |
    | --- | --- |
    | 1 | a***@example.com |
    | 2 | b***@example.com |
    | 4 | d***@example.com |
    | 5 | e***@example.com |
    | 6 | f***@example.com |
    | 7 | g***@example.com |
    | 9 | i***@example.com |
    | 10 | a***@example.com |
    <!-- /result -->

    On PostgreSQL, write `STRPOS` in place of `INSTR`, or use the `REGEXP_REPLACE` from [section 5.7](#regex).
    `SUBSTR(email, INSTR(email, '@'))` starts **at** the `@`, so it keeps it.

**Next:** [6. NULL and three-valued logic](06-Null-and-Three-Valued-Logic.md).
