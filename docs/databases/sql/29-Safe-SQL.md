# 29. Safe SQL

*A data engineer's queries run with real data and real permissions. This chapter covers the two sides of safety:
who may read and change what (roles, `GRANT`, views and row-level security), and how a program builds a query
without letting its input rewrite it (SQL injection, and parameters that stop it). It ends with habits for
handling personal data.*

!!! abstract "In this chapter"
    **You will learn:**

    - roles, `GRANT` and `REVOKE`, and least privilege
    - hiding columns and rows: views, column privileges and row-level security
    - SQL injection: how it works, and parameterized queries that prevent it
    - what cannot be a parameter (table and column names), and `LIKE` input
    - masking and protecting personal data, and keeping credentials out of code

    **You need:** [chapter 21](21-Views-and-Materialized-Views.md). The permission examples are PostgreSQL only:
    SQLite has no users or permissions; whoever can open the database file can read and change all of it.

## 29.1 Roles and privileges { #grant }

PostgreSQL controls access with **roles**. A role can be a person, a program, or a group that other roles belong
to. A role may do only what it has been **granted**: a privilege (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, ...) on an
object (a table, a view, a schema).

The examples below create a role `support` and then act as it with `SET LOCAL ROLE`, which lasts until the end of
the transaction (each example here is rolled back, so the role never really exists). Support staff may look up
customers but must not see their emails, so they get the `customers_public` view and nothing else:

<!-- sql pg -->
```sql
CREATE ROLE support NOLOGIN;
CREATE VIEW customers_public AS SELECT customer_id, name, city, country FROM customers;
GRANT SELECT ON customers_public TO support;

SET LOCAL ROLE support;
SELECT customer_id, name, city FROM customers_public WHERE country = 'Canada' ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

| customer_id | name | city |
| --- | --- | --- |
| 1 | Ana Silva | Toronto |
| 6 | Farah Haddad | Toronto |
| 9 | Ivan Petrov | Toronto |
<!-- /result -->

Reading the table itself is refused:

<!-- sql pg error -->
```sql
CREATE ROLE support NOLOGIN;
CREATE VIEW customers_public AS SELECT customer_id, name, city, country FROM customers;
GRANT SELECT ON customers_public TO support;

SET LOCAL ROLE support;
SELECT email FROM customers;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>permission denied for table customers</code></p>
<!-- /result -->

The view runs with its **owner's** privileges, so `support` can read the columns the view shows without any right
on the table (since PostgreSQL 15, `WITH (security_invoker = true)` makes a view check the caller's
privileges instead). That is what makes views a security tool. PostgreSQL can also grant single columns, which does the
same without a view:

<!-- sql pg error -->
```sql
CREATE ROLE support NOLOGIN;
GRANT SELECT (customer_id, name, city, country) ON customers TO support;

SET LOCAL ROLE support;
SELECT name FROM customers WHERE customer_id = 1;
SELECT email FROM customers WHERE customer_id = 1;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>permission denied for table customers</code></p>
<!-- /result -->

The first `SELECT` works; the second is refused.

The statements to know:

| Statement | Does |
| --- | --- |
| `CREATE ROLE analyst LOGIN PASSWORD '...'` | a role that can log in (a user) |
| `CREATE ROLE readers NOLOGIN` + `GRANT readers TO analyst` | a group, and putting someone in it |
| `GRANT SELECT ON orders TO readers` | read one table |
| `GRANT USAGE ON SCHEMA sales TO readers` + `GRANT SELECT ON ALL TABLES IN SCHEMA sales TO readers` | read every existing table in a schema (both are needed) |
| `ALTER DEFAULT PRIVILEGES IN SCHEMA sales GRANT SELECT ON TABLES TO readers` | ... and tables created later |
| `REVOKE INSERT, UPDATE, DELETE ON orders FROM etl` | take privileges away |

**Least privilege** is the rule behind all of it: each person and each program gets the smallest set of rights its
job needs. Reporting tools read only; a load job writes only to its own tables; nobody uses a superuser for daily
work. Grant to groups rather than to people, so that access follows the job, not the person.

## 29.2 Row-level security { #rls }

Views and column grants hide columns. **Row-level security** (RLS) hides rows: a policy adds a condition to every
query on the table, for every role it applies to. Here the Canadian support team sees only Canadian customers,
whatever query they write:

<!-- sql pg -->
```sql
CREATE ROLE support_ca NOLOGIN;
GRANT SELECT ON customers TO support_ca;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
CREATE POLICY only_canada ON customers FOR SELECT TO support_ca
  USING (country = 'Canada');

SET LOCAL ROLE support_ca;
SELECT COUNT(*) AS customers_visible FROM customers;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| customers_visible |
| --- |
| 3 |
<!-- /result -->

Three of ten customers are visible, with no `WHERE` in the query. Superusers and roles with `BYPASSRLS` always bypass
policies; the table's owner does too, unless `ALTER TABLE ... FORCE ROW LEVEL SECURITY` is set. Real policies usually compare with who is asking, for example
`USING (region = current_setting('app.region'))` or a lookup of `current_user` in a mapping table. Snowflake,
Databricks and BigQuery have their own row filters and column masks built on the same idea.

## 29.3 SQL injection { #injection }

Programs build queries from input: a name typed in a search box, a file name, a value from an API. If the program
pastes the input into the SQL text, the input can **change the query**. That is SQL injection, one of the oldest
and still one of the most common security holes.

A lookup that pastes the name into the text, in Python:

```python
name = input_from_user
sql = f"SELECT customer_id, email FROM customers WHERE name = '{name}'"   # WRONG
rows = con.execute(sql).fetchall()
```

With a normal name it works. Now the "name" is `x' OR '1'='1`. The quote in the input ends the text early, and the
query the database receives is:

<!-- sql -->
```sql
SELECT customer_id, email FROM customers WHERE name = 'x' OR '1'='1'
ORDER BY customer_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 10 rows.</p>

| customer_id | email |
| --- | --- |
| 1 | ana@example.com |
| 2 | ben@example.com |
| 3 | *NULL* |
| 4 | dana@example.com |
| 5 | eli@example.com |
| 6 | farah@example.com |
| 7 | gus@example.com |
| 8 | *NULL* |
| 9 | ivan@example.com |
| 10 | ana.silva@example.com |
<!-- /result -->

Every customer's email, for anyone who can type. Worse input can end the statement and add another (`'; DROP TABLE
customers; --`), where the driver allows several statements at once.

**The fix is a parameterized query.** The SQL text has a placeholder and the value is passed separately; the driver or the
database makes sure it is treated only as a value, never as SQL, whatever characters it contains.

=== "SQLite (Python sqlite3)"

    ```python
    rows = con.execute(
        "SELECT customer_id, email FROM customers WHERE name = ?",
        (name,),
    ).fetchall()
    ```

=== "PostgreSQL (Python psycopg2)"

    ```python
    cur.execute(
        "SELECT customer_id, email FROM customers WHERE name = %s",
        (name,),
    )
    rows = cur.fetchall()
    ```

With the same input, both return no rows: nobody is called `x' OR '1'='1`. (Checked with Python 3, `sqlite3` and
`psycopg2` on this course's shop database: the pasted version returned all 10 customers on both databases, the
parameterized version none.) The placeholder differs by driver (`?`, `%s`, `:name`, `$1`), the rule does not:
**never build SQL text from input with `+`, `||`, `f"..."` or `format`**. Escaping quotes by hand is not a fix; it is
easy to get wrong.

Parameters can also help performance: with drivers that use server-side prepared statements, the database can prepare the statement once and run it many times with different
values.

### What cannot be a parameter { #identifiers }

Parameters stand for **values**. A table name, a column name, `ASC` or `DESC` cannot be parameters. When those must
come from input (a "sort by" choice), check them against a fixed list of allowed names and refuse anything else:

```python
allowed = {"name", "city", "signup_date"}
if sort_column not in allowed:
    raise ValueError("unknown column")
sql = f"SELECT customer_id FROM customers ORDER BY {sort_column}, customer_id"
```

For PostgreSQL, psycopg2's `sql.Identifier(sort_column)` quotes a name safely, and inside the database
`format('... %I ...', name)` does the same in dynamic SQL (`%L` quotes a value). An allow-list is still the
stronger check: it also stops valid names you did not mean to expose.

### Input inside LIKE { #like-input }

A parameter is safe from injection, but its `%` and `_` still act as wildcards inside `LIKE`. A search for `50%`
matches "500 off" too. Escape them in the program (put `\` before `\`, `%` and `_`), and name the escape character:
PostgreSQL uses backslash by default, SQLite has none until you say `ESCAPE '\'`, and writing it works on both.

<!-- sql -->
```sql
SELECT '50% off'  LIKE '50\%%' ESCAPE '\' AS matches_50_percent,
       '500 off'  LIKE '50\%%' ESCAPE '\' AS matches_500;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| matches_50_percent | matches_500 |
| --- | --- |
| true | false |
<!-- /result -->

## 29.4 Personal data and secrets { #personal-data }

Pipelines copy data from place to place, and every copy of personal data (names, emails, addresses, birth dates,
anything that identifies a person) is one more place it can leak from. Habits that help:

- **Copy less.** Load only the columns analysis needs. The safest email column is the one you never copied.
- **Mask what people see.** A view or a masking policy that shows `a***@example.com`, or the last four digits of a
  number, is enough for most support and analysis work (practice [29.3](#practice)).
- **Pseudonymize keys.** Replace an email by a hash when it is only needed to join or count distinct people.
  PostgreSQL has `sha256()` (on `bytea`) and `md5()`; add a secret "salt" before hashing, or anyone can hash a list
  of known emails and match them.
- **Know where deletion has to reach.** When a person asks to be deleted, every copy must go: raw files, staging,
  history tables, backups by their schedule. A pipeline that carries one customer key everywhere
  ([chapter 22](22-Duplicates-and-Incremental-Loads.md#change-detection)) makes this possible: every copy can be found
  by that key and really deleted, not only marked as deleted.
- **Keep credentials out of code.** Connection passwords and keys go in a secret manager or environment variables
  set by the scheduler, never in a script, a notebook or a repository. Use a separate account per pipeline, so one
  can be revoked without stopping the others.
- **Limit the damage of a mistake.** Run ad hoc queries as a read-only role; set a `statement_timeout` for
  interactive sessions; use transactions and the habits in [chapter 17](17-Insert-Update-Delete-Merge.md#habits)
  before any `UPDATE` or `DELETE`.

## 29.5 Summary { #summary }

- PostgreSQL grants privileges to roles; give each person and program the least it needs, through group roles.
- Hide columns with views or column grants, rows with row-level security policies.
- SQLite has no permissions: protect the file.
- SQL injection happens when input is pasted into SQL text. Use parameterized queries, always; allow-list
  identifiers; escape `%` and `_` in `LIKE` input.
- Copy, show and keep as little personal data as the job needs; mask, hash with a salt, and keep secrets out of
  code.

!!! question "Asked aloud: security"
    ??? note "What is SQL injection and how do you prevent it?"
        Input pasted into SQL text can close a string and add its own conditions or statements, so a user controls the
        query. Prevent it with parameterized queries (prepared statements), where values travel separately from the SQL
        and are never parsed as SQL. For identifiers that must vary, use an allow-list. Also run the application with a
        least-privilege account, so a mistake cannot drop tables.

    ??? note "What is the principle of least privilege?"
        Every user and service gets only the permissions its task requires, and no more: read-only for reporting, write
        access only to the tables a job loads, no superuser for daily work. It limits what a mistake, a bug or a stolen
        credential can do.

    ??? note "How would you give analysts access to a table but hide personal columns?"
        Grant them a view (or column-level privileges) that leaves out or masks the personal columns, and no privilege on
        the base table. In warehouses, use masking policies or column-level security, and row-level security if they
        must also see only some rows.

    ??? note "How does row-level security work?"
        A policy attached to a table adds a condition to every query that a given role runs on it, so the role sees (or
        changes) only matching rows, whatever its query says. Conditions usually depend on the current user or a
        session setting. Superusers always bypass it; table owners do too unless it is forced.

    ??? note "How should a pipeline store its database password?"
        Not in code or in the repository. Use the platform's secret store (a secrets manager, a key vault, Databricks
        secrets) or environment variables injected at run time, give each pipeline its own account with least
        privilege, and rotate credentials. Prefer short-lived tokens or managed identities where the platform offers
        them.

    ??? note "How do you protect personal data in a data warehouse?"
        Collect and copy only what is needed; restrict access with roles, views, masking and row filters; pseudonymize
        identifiers with salted hashes or tokens where the real value is not needed; encrypt in transit and at rest;
        log access; and design so that a person's data can be found and deleted everywhere.

## Practice { #practice }

**29.1** Write the statements that create a group role `reporting`, let it read every table in schema `public`
(now and in future), and put the login role `dana` in it.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    CREATE ROLE reporting NOLOGIN;
    GRANT USAGE ON SCHEMA public TO reporting;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO reporting;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO reporting;
    CREATE ROLE dana LOGIN;
    GRANT reporting TO dana;

    SET LOCAL ROLE dana;
    SELECT COUNT(*) AS orders FROM orders;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

    | orders |
    | --- |
    | 20 |
    <!-- /result -->

    `ALTER DEFAULT PRIVILEGES` covers tables created later by the role that runs it (add `FOR ROLE etl` for tables
    another role creates). In real life `dana` would also get a password or another way to log in.

**29.2** This code builds a query from a date the user picks. What is wrong, and how do you fix it?
`sql = "SELECT * FROM orders WHERE order_date >= '" + start + "'"`

??? success "Answer"
    The date is pasted into the SQL text, so `start` can contain a quote and its own SQL: injection. Send it as a
    parameter: `con.execute("SELECT ... FROM orders WHERE order_date >= ?", (start,))` (or `%s` with psycopg2). It is
    also good practice to parse and check the date in the program first, and to list the columns instead of `*`.

**29.3** Show customers' emails masked as the first letter, `***`, and the domain (`a***@example.com`), and NULL for
customers with no email.

??? success "Answer"
    === "PostgreSQL"

        <!-- sql pg -->
        ```sql
        SELECT customer_id,
               LEFT(email, 1) || '***' || SUBSTR(email, STRPOS(email, '@')) AS masked_email
        FROM customers
        WHERE customer_id <= 4
        ORDER BY customer_id;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

        | customer_id | masked_email |
        | --- | --- |
        | 1 | a***@example.com |
        | 2 | b***@example.com |
        | 3 | *NULL* |
        | 4 | d***@example.com |
        <!-- /result -->

    === "SQLite"

        <!-- sql sqlite same -->
        ```sql
        SELECT customer_id,
               SUBSTR(email, 1, 1) || '***' || SUBSTR(email, INSTR(email, '@')) AS masked_email
        FROM customers
        WHERE customer_id <= 4
        ORDER BY customer_id;
        ```

        <!-- result -->
        <p class="sql-tested">Ran on SQLite 3.53: same rows as the other version. 4 rows.</p>

        | customer_id | masked_email |
        | --- | --- |
        | 1 | a***@example.com |
        | 2 | b***@example.com |
        | 3 | *NULL* |
        | 4 | d***@example.com |
        <!-- /result -->

    `||` with a NULL gives NULL, so customer 3 (no email) gets NULL without any extra code.

**29.4** A search box lets users find products whose name contains what they typed. Write the SQL with a
placeholder, and say what the program must do with the input first.

??? success "Answer"
    `SELECT product_id, name FROM products WHERE LOWER(name) LIKE ? ESCAPE '\' ORDER BY name` (with `%s` for
    psycopg2). The program escapes `\`, `%` and `_` in the input, lower-cases it, and passes `'%' + escaped + '%'` as
    the parameter. The placeholder stops injection; the escaping stops the user's `%` and `_` acting as wildcards; the
    `LOWER` on both sides makes the search ignore case on every database.

**Next:** practise everything on [practice set A](30-Practice-Set-A.md), [practice set B](31-Practice-Set-B.md) and
the [mock tests](32-Mock-Tests.md).
