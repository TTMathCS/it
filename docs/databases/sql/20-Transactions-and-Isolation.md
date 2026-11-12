# 20. Transactions and isolation

*A transaction groups several statements so that they happen together or not at all. Isolation decides what one
transaction sees of another that is running at the same time. This chapter shows both with real runs: one session
on its own, then two sessions side by side, step by step. It also shows where the two databases in this course
behave very differently when a statement fails halfway through a transaction.*

!!! abstract "In this chapter"
    **You will learn:**

    - `BEGIN`, `COMMIT`, `ROLLBACK` and `SAVEPOINT`, and what autocommit means
    - what ACID stands for, in plain words
    - what happens to a transaction after an error: PostgreSQL and SQLite differ, and the difference can lose money
    - the problems two sessions can cause each other (dirty read, non-repeatable read, phantom, lost update, write
      skew) and the isolation level that stops each
    - three ways to stop a lost update, deadlocks, and retrying
    - SQLite's one-writer rule

    **You need:** [chapter 17](17-Insert-Update-Delete-Merge.md). The single-session examples run through the same
    tool as every other chapter. The two-session timelines are run by `tools/txdemo.py`, which opens two connections
    to one database and runs each step in the order shown.

## 20.1 BEGIN, COMMIT, ROLLBACK { #begin }

Every example in this chapter uses a small table of bank accounts.

<!-- sql setup -->
```sql
CREATE TABLE accounts (
  id      INTEGER PRIMARY KEY,
  owner   VARCHAR(20) NOT NULL,
  balance INTEGER NOT NULL CHECK (balance >= 0)
);
INSERT INTO accounts VALUES (1, 'Ana', 300), (2, 'Ben', 100);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

A transfer of 100 from Ana to Ben is two updates. They belong together: if only the first one happened, 100 would
vanish. `BEGIN` starts a transaction, and `COMMIT` makes all of its changes permanent at once.

<!-- sql raw -->
```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
SELECT owner, balance FROM accounts ORDER BY id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| owner | balance |
| --- | --- |
| Ana | 200 |
| Ben | 200 |
<!-- /result -->

`ROLLBACK` throws away every change since `BEGIN`. Here a mistaken update (no `WHERE`, so every account is
emptied) is undone:

<!-- sql raw -->
```sql
BEGIN;
UPDATE accounts SET balance = 0;
ROLLBACK;
SELECT owner, balance FROM accounts ORDER BY id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| owner | balance |
| --- | --- |
| Ana | 200 |
| Ben | 200 |
<!-- /result -->

The balances are still 200 and 200. `BEGIN TRANSACTION` and `START TRANSACTION` mean the same as `BEGIN` on
PostgreSQL; SQLite accepts `BEGIN` and `BEGIN TRANSACTION` but not `START TRANSACTION`. On both, `END` is another
name for `COMMIT`.

### Autocommit { #autocommit }

Without `BEGIN`, each statement is a transaction of its own and is committed as soon as it finishes. That is called
**autocommit**, and it is how `psql`, the `sqlite3` shell and most database tools behave. Program libraries differ:
Python's `psycopg2`, for example, opens a transaction for you before the first statement, and nothing is saved until
the program calls `conn.commit()`. A data pipeline that "ran without errors but wrote nothing" has often forgotten
that call.

### Undoing part of a transaction: SAVEPOINT { #savepoint }

A savepoint is a bookmark inside a transaction. `ROLLBACK TO SAVEPOINT` undoes the changes made after it and keeps
the ones before it; the transaction stays open.

<!-- sql raw -->
```sql
BEGIN;
UPDATE accounts SET balance = balance + 5 WHERE id = 1;
SAVEPOINT before_fee;
UPDATE accounts SET balance = balance - 50 WHERE id = 2;
ROLLBACK TO SAVEPOINT before_fee;
COMMIT;
SELECT owner, balance FROM accounts ORDER BY id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

| owner | balance |
| --- | --- |
| Ana | 205 |
| Ben | 200 |
<!-- /result -->

Ana's +5 was kept and Ben's −50 was undone. Both databases support savepoints with this syntax.

### Table changes can be rolled back too { #ddl }

On PostgreSQL and SQLite, `CREATE TABLE`, `ALTER TABLE` and `DROP TABLE` take part in the transaction like any
other statement:

<!-- sql raw error -->
```sql
BEGIN;
CREATE TABLE audit_log (id INTEGER);
ROLLBACK;
SELECT * FROM audit_log;
```

<!-- result -->
<p class="sql-tested sql-error">PostgreSQL 16: error: <code>relation "audit_log" does not exist</code></p>
<p class="sql-tested sql-error">SQLite 3.53: error: <code>no such table: audit_log</code></p>
<!-- /result -->

The table never existed. This is not true everywhere: MySQL and Oracle commit the open transaction automatically
before most table changes (from their documentation; not run here), so a migration script that fails halfway leaves
a half-changed database.

## 20.2 ACID { #acid }

The four promises a transaction makes, often asked in interviews:

| Letter | Stands for | In plain words |
| --- | --- | --- |
| A | Atomicity | All of the transaction happens, or none of it. |
| C | Consistency | A transaction moves the data from one valid state to another: every constraint (`CHECK`, `UNIQUE`, foreign keys) holds when it commits. |
| I | Isolation | Transactions running at the same time do not see each other's half-done work. How strictly is set by the isolation level ([20.4](#isolation)). |
| D | Durability | Once `COMMIT` returns, the change survives a crash or a power cut: it has been written to the database's log on disk. |

## 20.3 When a statement fails inside a transaction { #errors }

This is where PostgreSQL and SQLite part ways. The transfer below moves 500 from Ana, who has only 300 (the table's
original balances, 300 and 100), so the second update breaks the `CHECK (balance >= 0)` rule. Then the program
carries on and runs `COMMIT`.

=== "PostgreSQL"

    <!-- txdemo atomic pg -->
    <p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

    | # | Session A | Session B | Result |
    | --- | --- | --- | --- |
    | 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
    | 2 | <code>UPDATE accounts SET balance = balance + 500 WHERE id = 2</code> |  | <code>UPDATE 1</code> |
    | 3 | <code>UPDATE accounts SET balance = balance - 500 WHERE id = 1</code> |  | **error:** <code>new row for relation "accounts" violates check constraint "accounts_balance_check"</code> |
    | 4 | <code>SELECT owner, balance FROM accounts ORDER BY id</code> |  | **error:** <code>current transaction is aborted, commands ignored until end of transaction block</code> |
    | 5 | <code>COMMIT</code> |  | <code>ROLLBACK</code> |
    | 6 | <code>SELECT owner, balance FROM accounts ORDER BY id</code> |  | Ana, 300; Ben, 100 |
    <!-- /txdemo -->

=== "SQLite"

    <!-- txdemo atomic sqlite -->
    <p class="sql-tested">Run by <code>tools/txdemo.py</code> on SQLite 3.53, two connections, in this order.</p>

    | # | Session A | Session B | Result |
    | --- | --- | --- | --- |
    | 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
    | 2 | <code>UPDATE accounts SET balance = balance + 500 WHERE id = 2</code> |  | <code>UPDATE 1</code> |
    | 3 | <code>UPDATE accounts SET balance = balance - 500 WHERE id = 1</code> |  | **error:** <code>CHECK constraint failed: balance >= 0</code> |
    | 4 | <code>SELECT owner, balance FROM accounts ORDER BY id</code> |  | Ana, 300; Ben, 600 |
    | 5 | <code>COMMIT</code> |  | <code>COMMIT</code> |
    | 6 | <code>SELECT owner, balance FROM accounts ORDER BY id</code> |  | Ana, 300; Ben, 600 |
    <!-- /txdemo -->

**On PostgreSQL**, one error spoils the whole transaction. Every later statement is refused ("current transaction is
aborted"), and `COMMIT` does a rollback instead (its reply is `ROLLBACK`). Nothing changed.

**On SQLite**, only the failing statement is undone. The transaction stays open with Ben's +500 in it, and `COMMIT`
saves it: Ben gained 500 that nobody lost. (MySQL behaves like SQLite here, and so does SQL Server unless
`SET XACT_ABORT ON`; from their documentation, not run here.)

The rule that works on every database: **when any statement in a transaction fails, run `ROLLBACK`**. Program
libraries do this for you when the transaction is written as a block, for example `with conn:` in Python.

=== "PostgreSQL"

    <!-- txdemo atomic-rollback pg -->
    <p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

    | # | Session A | Session B | Result |
    | --- | --- | --- | --- |
    | 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
    | 2 | <code>UPDATE accounts SET balance = balance + 500 WHERE id = 2</code> |  | <code>UPDATE 1</code> |
    | 3 | <code>UPDATE accounts SET balance = balance - 500 WHERE id = 1</code> |  | **error:** <code>new row for relation "accounts" violates check constraint "accounts_balance_check"</code> |
    | 4 | <code>ROLLBACK</code> |  | <code>ROLLBACK</code> |
    | 5 | <code>SELECT owner, balance FROM accounts ORDER BY id</code> |  | Ana, 300; Ben, 100 |
    <!-- /txdemo -->

=== "SQLite"

    <!-- txdemo atomic-rollback sqlite -->
    <p class="sql-tested">Run by <code>tools/txdemo.py</code> on SQLite 3.53, two connections, in this order.</p>

    | # | Session A | Session B | Result |
    | --- | --- | --- | --- |
    | 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
    | 2 | <code>UPDATE accounts SET balance = balance + 500 WHERE id = 2</code> |  | <code>UPDATE 1</code> |
    | 3 | <code>UPDATE accounts SET balance = balance - 500 WHERE id = 1</code> |  | **error:** <code>CHECK constraint failed: balance >= 0</code> |
    | 4 | <code>ROLLBACK</code> |  | <code>ROLLBACK</code> |
    | 5 | <code>SELECT owner, balance FROM accounts ORDER BY id</code> |  | Ana, 300; Ben, 100 |
    <!-- /txdemo -->

## 20.4 Two sessions at once: isolation { #isolation }

When two transactions run at the same time, the database has to decide what each one sees of the other. The SQL
standard names four **isolation levels** by the problems they allow. From least to most strict:

| Problem | What happens | READ UNCOMMITTED | READ COMMITTED | REPEATABLE READ | SERIALIZABLE |
| --- | --- | --- | --- | --- | --- |
| Dirty read | You see another transaction's change before it commits (and it may roll back). | possible | prevented | prevented | prevented |
| Non-repeatable read | You read a row twice and get two different values, because someone committed a change in between. | possible | possible | prevented | prevented |
| Phantom | You run the same `WHERE` twice and get more (or fewer) rows, because someone committed an insert in between. | possible | possible | possible | prevented |
| Write skew | Two transactions each read the same data, each make a change that is fine on its own, and together they break a rule. | possible | possible | possible | prevented |

That table is the standard's minimum. **PostgreSQL is stricter**: its READ UNCOMMITTED behaves exactly like READ
COMMITTED (no dirty reads ever), and its REPEATABLE READ also prevents phantoms. Write skew is stopped only by
SERIALIZABLE. All four are shown below on PostgreSQL 16.

The default level differs by database (from each vendor's documentation; only PostgreSQL's is run here):

| Database | Default isolation |
| --- | --- |
| PostgreSQL | READ COMMITTED |
| SQL Server | READ COMMITTED |
| Oracle | READ COMMITTED |
| MySQL (InnoDB) | REPEATABLE READ |
| Snowflake | READ COMMITTED (the only level for tables) |
| Databricks (Delta tables) | WriteSerializable, a level of its own between snapshot and serializable |
| SQLite | SERIALIZABLE in effect, because only one connection can write at a time ([20.7](#sqlite)) |

To choose a level for one transaction on PostgreSQL: `BEGIN ISOLATION LEVEL REPEATABLE READ;` (or `SET TRANSACTION
ISOLATION LEVEL ...` as the first statement after `BEGIN`).

### How PostgreSQL does it: row versions { #mvcc }

PostgreSQL does not make readers wait. An `UPDATE` writes a new version of the row and keeps the old one until no
transaction needs it any more. Each statement (at READ COMMITTED) or each transaction (at REPEATABLE READ and
SERIALIZABLE) reads from a **snapshot**: the committed data as it was when the statement (or the transaction's first statement) started. This is called MVCC,
multi-version concurrency control. The practical result: **readers never block writers, and writers never block
readers.** Two writers changing the same row do wait for each other ([20.5](#lost-update)).

### No dirty reads, even when asked for { #dirty }

Session A empties Ana's account but has not committed. Session B asks for READ UNCOMMITTED and still sees only
committed data:

<!-- txdemo dirty pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
| 2 | <code>UPDATE accounts SET balance = 0 WHERE id = 1</code> |  | <code>UPDATE 1</code> |
| 3 |  | <code>BEGIN ISOLATION LEVEL READ UNCOMMITTED</code> | <code>BEGIN</code> |
| 4 |  | <code>SELECT balance FROM accounts WHERE id = 1</code> | balance = 300 |
| 5 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 6 |  | <code>SELECT balance FROM accounts WHERE id = 1</code> | balance = 0 |
| 7 |  | <code>COMMIT</code> | <code>COMMIT</code> |
<!-- /txdemo -->

### READ COMMITTED: each statement sees the latest commits { #read-committed }

At the default level, A's two identical `SELECT`s give different answers, because B committed a change in between
(a non-repeatable read, step 4). The same happens with a new row (a phantom, step 7).

<!-- txdemo nonrepeatable pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
| 2 | <code>SELECT balance FROM accounts WHERE id = 1</code> |  | balance = 300 |
| 3 |  | <code>UPDATE accounts SET balance = 250 WHERE id = 1</code> | <code>UPDATE 1</code> |
| 4 | <code>SELECT balance FROM accounts WHERE id = 1</code> |  | balance = 250 |
| 5 | <code>SELECT COUNT(*) AS accounts FROM accounts</code> |  | accounts = 2 |
| 6 |  | <code>INSERT INTO accounts VALUES (3, 'Cy', 40)</code> | <code>INSERT 0 1</code> |
| 7 | <code>SELECT COUNT(*) AS accounts FROM accounts</code> |  | accounts = 3 |
| 8 | <code>COMMIT</code> |  | <code>COMMIT</code> |
<!-- /txdemo -->

### REPEATABLE READ: one snapshot for the whole transaction { #repeatable-read }

The same steps, but A's transaction reads from the snapshot taken at its first statement. It sees neither B's
update nor B's insert until it has committed (step 9).

<!-- txdemo repeatable pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN ISOLATION LEVEL REPEATABLE READ</code> |  | <code>BEGIN</code> |
| 2 | <code>SELECT balance FROM accounts WHERE id = 1</code> |  | balance = 300 |
| 3 |  | <code>UPDATE accounts SET balance = 250 WHERE id = 1</code> | <code>UPDATE 1</code> |
| 4 | <code>SELECT balance FROM accounts WHERE id = 1</code> |  | balance = 300 |
| 5 | <code>SELECT COUNT(*) AS accounts FROM accounts</code> |  | accounts = 2 |
| 6 |  | <code>INSERT INTO accounts VALUES (3, 'Cy', 40)</code> | <code>INSERT 0 1</code> |
| 7 | <code>SELECT COUNT(*) AS accounts FROM accounts</code> |  | accounts = 2 |
| 8 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 9 | <code>SELECT balance FROM accounts WHERE id = 1</code> |  | balance = 250 |
<!-- /txdemo -->

A report that runs several queries and must add up (a total on one page, the details on another) should run them
in one REPEATABLE READ transaction.

## 20.5 The lost update { #lost-update }

The most common concurrency bug in real programs. Two programs each read Ana's balance, add a deposit in their own
code, and write the new total back. A deposits 50, B deposits 20. Ana should end with 370.

<!-- txdemo lost-update pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
| 2 | <code>SELECT balance FROM accounts WHERE id = 1</code> |  | balance = 300 |
| 3 |  | <code>BEGIN</code> | <code>BEGIN</code> |
| 4 |  | <code>SELECT balance FROM accounts WHERE id = 1</code> | balance = 300 |
| 5 | <code>UPDATE accounts SET balance = 350 WHERE id = 1</code> |  | <code>UPDATE 1</code> |
| 6 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 7 |  | <code>UPDATE accounts SET balance = 320 WHERE id = 1</code> | <code>UPDATE 1</code> |
| 8 |  | <code>COMMIT</code> | <code>COMMIT</code> |
| 9 | <code>SELECT balance FROM accounts WHERE id = 1</code> |  | balance = 320 |
<!-- /txdemo -->

Ana has 320: A's deposit is gone. Nothing failed, and READ COMMITTED did exactly what it promises. The bug is that
the program decided the new value from a read that was already out of date. Three fixes:

**Fix 1: let the database do the arithmetic.** `SET balance = balance + 20` is read and written in one step. If
another transaction has changed the row and not committed, the update waits, then adds to the committed value.

<!-- txdemo relative-update pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
| 2 | <code>UPDATE accounts SET balance = balance + 50 WHERE id = 1</code> |  | <code>UPDATE 1</code> |
| 3 |  | <code>UPDATE accounts SET balance = balance + 20 WHERE id = 1</code> | *waits: the row is locked by the other session* |
| 4 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 5 |  | *(its waiting statement finishes)* | <code>UPDATE 1</code> |
| 6 | <code>SELECT balance FROM accounts WHERE id = 1</code> |  | balance = 370 |
<!-- /txdemo -->

**Fix 2: lock the row when you read it.** `SELECT ... FOR UPDATE` locks the rows it returns until the transaction
ends. A second `FOR UPDATE` on the same row waits, and then reads the new value (350, step 7), so B computes 370.

<!-- txdemo for-update pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
| 2 | <code>SELECT balance FROM accounts WHERE id = 1 FOR UPDATE</code> |  | balance = 300 |
| 3 |  | <code>BEGIN</code> | <code>BEGIN</code> |
| 4 |  | <code>SELECT balance FROM accounts WHERE id = 1 FOR UPDATE</code> | *waits: the row is locked by the other session* |
| 5 | <code>UPDATE accounts SET balance = 350 WHERE id = 1</code> |  | <code>UPDATE 1</code> |
| 6 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 7 |  | *(its waiting statement finishes)* | balance = 350 |
| 8 |  | <code>UPDATE accounts SET balance = 370 WHERE id = 1</code> | <code>UPDATE 1</code> |
| 9 |  | <code>COMMIT</code> | <code>COMMIT</code> |
| 10 | <code>SELECT balance FROM accounts WHERE id = 1</code> |  | balance = 370 |
<!-- /txdemo -->

`FOR UPDATE` is PostgreSQL, MySQL and Oracle syntax (SQL Server uses a table hint, `WITH (UPDLOCK)`); SQLite has no
row locks and does not accept it. Use it when the new value needs logic too complicated for one `UPDATE`.

**Fix 3: REPEATABLE READ refuses the second write.** If B's snapshot is older than the row's latest committed
version, PostgreSQL rejects B's update instead of overwriting A's work. B must roll back and try again from the
start.

<!-- txdemo rr-conflict pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN ISOLATION LEVEL REPEATABLE READ</code> |  | <code>BEGIN</code> |
| 2 | <code>SELECT balance FROM accounts WHERE id = 1</code> |  | balance = 300 |
| 3 |  | <code>BEGIN ISOLATION LEVEL REPEATABLE READ</code> | <code>BEGIN</code> |
| 4 |  | <code>SELECT balance FROM accounts WHERE id = 1</code> | balance = 300 |
| 5 | <code>UPDATE accounts SET balance = 350 WHERE id = 1</code> |  | <code>UPDATE 1</code> |
| 6 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 7 |  | <code>UPDATE accounts SET balance = 320 WHERE id = 1</code> | **error:** <code>could not serialize access due to concurrent update</code> |
| 8 |  | <code>ROLLBACK</code> | <code>ROLLBACK</code> |
| 9 | <code>SELECT balance FROM accounts WHERE id = 1</code> |  | balance = 350 |
<!-- /txdemo -->

A program that uses REPEATABLE READ or SERIALIZABLE must be ready to **retry**: catch the error (its SQLSTATE code is
`40001`, serialization failure), roll back, and run the whole transaction again.

## 20.6 Write skew, and SERIALIZABLE { #write-skew }

A hospital rule: at least one of its two doctors must be on call. Kim and Lee both feel ill. Each one's transaction
checks that two doctors are on call, so it is safe to go off call, and does so. Each change is fine on its own;
together they break the rule. The two transactions changed **different** rows, so no row lock and no "concurrent
update" check notices.

=== "REPEATABLE READ"

    <!-- txdemo skew-rr pg -->
    <p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

    | # | Session A | Session B | Result |
    | --- | --- | --- | --- |
    | 1 | <code>BEGIN ISOLATION LEVEL REPEATABLE READ</code> |  | <code>BEGIN</code> |
    | 2 |  | <code>BEGIN ISOLATION LEVEL REPEATABLE READ</code> | <code>BEGIN</code> |
    | 3 | <code>SELECT SUM(on_call) AS on_call FROM doctors</code> |  | on_call = 2 |
    | 4 |  | <code>SELECT SUM(on_call) AS on_call FROM doctors</code> | on_call = 2 |
    | 5 | <code>UPDATE doctors SET on_call = 0 WHERE name = 'Kim'</code> |  | <code>UPDATE 1</code> |
    | 6 |  | <code>UPDATE doctors SET on_call = 0 WHERE name = 'Lee'</code> | <code>UPDATE 1</code> |
    | 7 | <code>COMMIT</code> |  | <code>COMMIT</code> |
    | 8 |  | <code>COMMIT</code> | <code>COMMIT</code> |
    | 9 | <code>SELECT SUM(on_call) AS on_call FROM doctors</code> |  | on_call = 0 |
    <!-- /txdemo -->

=== "SERIALIZABLE"

    <!-- txdemo skew-serializable pg -->
    <p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

    | # | Session A | Session B | Result |
    | --- | --- | --- | --- |
    | 1 | <code>BEGIN ISOLATION LEVEL SERIALIZABLE</code> |  | <code>BEGIN</code> |
    | 2 |  | <code>BEGIN ISOLATION LEVEL SERIALIZABLE</code> | <code>BEGIN</code> |
    | 3 | <code>SELECT SUM(on_call) AS on_call FROM doctors</code> |  | on_call = 2 |
    | 4 |  | <code>SELECT SUM(on_call) AS on_call FROM doctors</code> | on_call = 2 |
    | 5 | <code>UPDATE doctors SET on_call = 0 WHERE name = 'Kim'</code> |  | <code>UPDATE 1</code> |
    | 6 |  | <code>UPDATE doctors SET on_call = 0 WHERE name = 'Lee'</code> | <code>UPDATE 1</code> |
    | 7 | <code>COMMIT</code> |  | <code>COMMIT</code> |
    | 8 |  | <code>COMMIT</code> | **error:** <code>could not serialize access due to read/write dependencies among transactions</code> |
    | 9 | <code>SELECT SUM(on_call) AS on_call FROM doctors</code> |  | on_call = 1 |
    <!-- /txdemo -->

At REPEATABLE READ nobody is on call. At SERIALIZABLE, PostgreSQL tracks what each transaction read and refuses the
second commit, because no order of running the two one after the other would give that result. SERIALIZABLE
promises exactly that: the outcome is the same as some order of running the transactions one at a time. The price is
more retries, so it is used where a rule spans several rows and cannot be written as a constraint.

### Deadlocks { #deadlock }

A deadlock is two transactions each waiting for a row the other has locked. A transfers from account 1 to account 2,
B transfers from 2 to 1, and they lock the rows in opposite orders:

<!-- txdemo deadlock pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
| 2 | <code>UPDATE accounts SET balance = balance - 10 WHERE id = 1</code> |  | <code>UPDATE 1</code> |
| 3 |  | <code>BEGIN</code> | <code>BEGIN</code> |
| 4 |  | <code>UPDATE accounts SET balance = balance - 10 WHERE id = 2</code> | <code>UPDATE 1</code> |
| 5 | <code>UPDATE accounts SET balance = balance + 10 WHERE id = 2</code> |  | *waits: the row is locked by the other session* |
| 6 |  | <code>UPDATE accounts SET balance = balance + 10 WHERE id = 1</code> | **error:** <code>deadlock detected</code> |
| 7 | *(its waiting statement finishes)* |  | <code>UPDATE 1</code> |
| 8 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 9 |  | <code>ROLLBACK</code> | <code>ROLLBACK</code> |
| 10 | <code>SELECT owner, balance FROM accounts ORDER BY id</code> |  | Ana, 290; Ben, 110 |
<!-- /txdemo -->

Neither can go on, so PostgreSQL cancels one of them. It checks for a deadlock once a statement has waited for
`deadlock_timeout` (1 second by default); the session whose check finds the cycle gets the error (SQLSTATE `40P01`),
here B, and A goes ahead. B's transaction is aborted and must be rolled back and retried.

Two habits prevent most deadlocks:

- **Lock rows in the same order everywhere**, for example always the lower `id` first.
- **Keep transactions short.** Never wait for a person, a file download or a slow API call while a transaction is
  open; every lock it holds stays held.

## 20.7 SQLite: one writer at a time { #sqlite }

SQLite has no row locks. The whole database file is locked for writing, so only one connection can write at a time.
In its default mode (a rollback journal, as here), a writer does not stop others from reading the last committed
data, but a second writer is turned away with `database is locked`:

<!-- txdemo sqlite-writer sqlite -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on SQLite 3.53, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
| 2 | <code>UPDATE accounts SET balance = 0 WHERE id = 1</code> |  | <code>UPDATE 1</code> |
| 3 |  | <code>SELECT balance FROM accounts WHERE id = 1</code> | balance = 300 |
| 4 |  | <code>UPDATE accounts SET balance = 999 WHERE id = 2</code> | **error:** <code>database is locked</code> |
| 5 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 6 |  | <code>UPDATE accounts SET balance = 999 WHERE id = 2</code> | <code>UPDATE 1</code> |
| 7 |  | <code>SELECT owner, balance FROM accounts ORDER BY id</code> | Ana, 0; Ben, 999 |
<!-- /txdemo -->

Real programs set a **busy timeout** (`PRAGMA busy_timeout = 5000;` waits up to 5 seconds instead of failing at once,
and Python's `sqlite3.connect` waits 5 seconds by default; the run above set it to 0 to show the error). Many also
switch to **WAL mode** (`PRAGMA journal_mode = WAL;`), in which readers and the one writer do not block each other.
A transaction that will write should start with `BEGIN IMMEDIATE`, which takes the write lock at once instead of at
the first write, so it cannot be turned away with `database is locked` halfway through. Because writes take turns, two transactions cannot both commit
changes based on the same old read: one of them is turned away and must roll back, so write skew cannot happen. (A
program that reads in one transaction and writes in another can still lose an update, on SQLite as on any database;
the fixes in [20.5](#lost-update) apply.)

## 20.8 Transactions in data pipelines { #pipelines }

- **Swap a day's data in one transaction.** A job that reloads yesterday's sales with `DELETE` then `INSERT` should
  run both inside `BEGIN ... COMMIT`. Readers then see the old rows or the new rows, never an empty day (practice
  [20.4](#practice)).
- **Make a re-run safe.** A load that fails halfway and is run again should not double the data. One transaction per
  load, plus a delete-then-insert or upsert by key, makes it idempotent ([chapter 22](22-Duplicates-and-Incremental-Loads.md)).
- **Commit big loads in batches, not one row at a time.** A commit per row is slow (each one waits for the disk); one
  transaction for a whole day's millions of rows holds its locks and snapshot for a long time. Batches of thousands of
  rows are the usual middle.
- **Avoid long-running transactions.** On PostgreSQL an open transaction keeps old row versions from being cleaned up
  (`VACUUM` cannot remove versions that a running snapshot may still need), so tables grow. Look for sessions marked
  `idle in transaction` in `pg_stat_activity`.
- **Warehouses differ.** Data warehouses and lakehouses make each statement, or each write to a table, one atomic
  operation. Support for several statements inside one `BEGIN ... COMMIT` varies by platform, so check it before
  relying on it there.

## 20.9 Summary { #summary }

- A transaction is all or nothing: `BEGIN`, then `COMMIT` or `ROLLBACK`. `SAVEPOINT` undoes part of one.
- Without `BEGIN`, tools autocommit each statement; some program libraries do the opposite and need `commit()`.
- After an error, PostgreSQL refuses everything until `ROLLBACK` (and turns `COMMIT` into a rollback); SQLite keeps
  the rest of the transaction and will commit it. Always `ROLLBACK` on error.
- Isolation levels, weakest to strongest: READ UNCOMMITTED, READ COMMITTED (the usual default), REPEATABLE READ,
  SERIALIZABLE. PostgreSQL never allows dirty reads and its REPEATABLE READ also stops phantoms.
- A lost update comes from read, compute in the program, write back. Fix it with `SET x = x + n`, with
  `SELECT ... FOR UPDATE`, or with REPEATABLE READ plus a retry.
- Write skew needs SERIALIZABLE. Deadlocks are prevented by locking in one order and keeping transactions short.
- SQLite lets one connection write at a time; use a busy timeout, WAL mode and `BEGIN IMMEDIATE`.

!!! question "Asked aloud: transactions and isolation"
    ??? note "What does ACID mean?"
        Atomicity: all of a transaction happens or none of it. Consistency: it leaves every constraint satisfied.
        Isolation: concurrent transactions do not see each other's unfinished work, to the degree the isolation level
        sets. Durability: once committed, the change survives a crash, because it is in the log on disk.

    ??? note "Name the isolation levels and what each one prevents."
        READ UNCOMMITTED allows dirty reads. READ COMMITTED prevents dirty reads but allows non-repeatable reads and
        phantoms. REPEATABLE READ also prevents non-repeatable reads (and in PostgreSQL phantoms too). SERIALIZABLE
        prevents everything, including write skew: the result equals some one-at-a-time order. Most databases default
        to READ COMMITTED; MySQL defaults to REPEATABLE READ.

    ??? note "What is a lost update and how do you prevent it?"
        Two transactions read the same value, each computes a new one in the program and writes it back; the second
        write overwrites the first. Prevent it by doing the arithmetic in the `UPDATE` (`SET balance = balance + 20`),
        by locking the row when reading (`SELECT ... FOR UPDATE`), or by optimistic checking: REPEATABLE READ, or a
        version column checked in the `WHERE` (`... WHERE id = 1 AND version = 7`), with a retry when it fails.

    ??? note "What is MVCC?"
        Multi-version concurrency control. An update writes a new row version instead of overwriting, and each
        transaction reads a consistent snapshot of committed versions. Readers do not block writers and writers do not
        block readers. PostgreSQL, Oracle, MySQL InnoDB and SQL Server (with snapshot isolation) work this way. The
        cost is cleaning up old versions (VACUUM in PostgreSQL).

    ??? note "What is a deadlock and what does the database do about it?"
        Two transactions each hold a lock the other needs, so both would wait forever. The database detects the cycle
        and cancels one transaction with an error; the program should roll back and retry. Prevent them by locking rows
        in a consistent order and keeping transactions short.

    ??? note "Optimistic versus pessimistic locking?"
        Pessimistic: lock first (`SELECT ... FOR UPDATE`), so others wait; best when conflicts are frequent.
        Optimistic: do not lock; check at write time that nobody changed the row (a version number or timestamp in the
        `WHERE`, or REPEATABLE READ / SERIALIZABLE), and retry on conflict; best when conflicts are rare.

    ??? note "Your pipeline deletes and reinserts a day of data. Users sometimes see an empty day. Why?"
        The delete and the insert run as two separate transactions (autocommit), so between them the day is empty and
        any reader at that moment sees nothing. Put both in one transaction; readers then see the old rows until the
        commit and the new rows after it. In a lakehouse the same idea is an atomic overwrite of the partition, or a
        `MERGE`.

    ??? note "Why are long-running transactions a problem?"
        They hold their locks the whole time, so other writers queue behind them and deadlocks get likelier. On
        MVCC databases they also keep old row versions alive, so tables and indexes grow (bloat) until the
        transaction ends. And if one fails at the end, all of its work is lost.

## Practice { #practice }

**20.1** Name the problem in this timeline, and the isolation level that would make step 5 return 1 again.
Step 1, A: `BEGIN;` 2, A: `SELECT COUNT(*) FROM orders WHERE status = 'new';` returns 1. 3, B: `INSERT` a new order.
4, B: `COMMIT`. 5, A: the same `SELECT` returns 2.

??? success "Answer"
    A phantom: a new row appeared for the same `WHERE`. The standard requires SERIALIZABLE to prevent it; on
    PostgreSQL, REPEATABLE READ already does (see the timeline in [20.4](#repeatable-read), steps 5 and 7).

**20.2** Write one statement that moves 50 from Ben (id 2) to Ana (id 1), changing both rows at once, so that no
other transaction can ever see one change without the other, even without `BEGIN`.

??? success "Answer"
    One `UPDATE` with a `CASE`. A single statement is always atomic: no one can see one change without the other.

    <!-- sql -->
    ```sql
    UPDATE accounts
    SET balance = balance + CASE id WHEN 1 THEN 50 WHEN 2 THEN -50 END
    WHERE id IN (1, 2);
    SELECT owner, balance FROM accounts ORDER BY id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | owner | balance |
    | --- | --- |
    | Ana | 255 |
    | Ben | 150 |
    <!-- /result -->

    If Ben had less than 50, the `CHECK (balance >= 0)` would fail the whole statement and neither row would change.

**20.3** A program withdraws money with `SELECT balance ...`, checks in its own code that the balance is at least
the amount, then runs `UPDATE accounts SET balance = <new value> ...`. Two withdrawals at the same moment can both
pass the check. Rewrite the withdrawal of 30 from Ben as one statement that cannot overdraw and cannot lose an
update, and say how the program knows it worked.

??? success "Answer"
    Put the check in the `WHERE` and the arithmetic in the `SET`. The program reads the number of rows changed: 1
    means done, 0 means not enough money (or no such account).

    <!-- sql -->
    ```sql
    UPDATE accounts SET balance = balance - 30
    WHERE id = 2 AND balance >= 30
    RETURNING id, balance;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | id | balance |
    | --- | --- |
    | 2 | 170 |
    <!-- /result -->

    If two withdrawals run at once, the second waits for the first to commit and then re-checks `balance >= 30`
    against the new balance (PostgreSQL re-evaluates the `WHERE` on the updated row at READ COMMITTED). The
    `CHECK (balance >= 0)` constraint is a second safety net. `RETURNING` works on both databases (SQLite 3.35+).

**20.4** A nightly job reloads one day of a summary table. Load the table below, then write the reload of 2 January
(new totals: Toronto 120, Lagos 80) so that a reader never sees 2 January empty or half loaded.

<!-- sql setup -->
```sql
CREATE TABLE daily_sales (
  day   DATE        NOT NULL,
  city  VARCHAR(20) NOT NULL,
  total INTEGER     NOT NULL,
  PRIMARY KEY (day, city)
);
INSERT INTO daily_sales VALUES
  ('2026-01-01', 'Toronto', 90), ('2026-01-01', 'Lagos', 40),
  ('2026-01-02', 'Toronto', 100), ('2026-01-02', 'Lagos', 70);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

??? success "Answer"
    Delete and insert inside one transaction. Until `COMMIT`, other sessions keep seeing the old 2 January rows; after
    it, the new ones. Running the job twice gives the same result, because it deletes the day first.

    <!-- sql raw -->
    ```sql
    BEGIN;
    DELETE FROM daily_sales WHERE day = '2026-01-02';
    INSERT INTO daily_sales VALUES ('2026-01-02', 'Toronto', 120), ('2026-01-02', 'Lagos', 80);
    COMMIT;
    SELECT day, city, total FROM daily_sales ORDER BY day, city;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | day | city | total |
    | --- | --- | --- |
    | 2026-01-01 | Lagos | 40 |
    | 2026-01-01 | Toronto | 90 |
    | 2026-01-02 | Lagos | 80 |
    | 2026-01-02 | Toronto | 120 |
    <!-- /result -->

    On a database with `MERGE` or `ON CONFLICT` you could also upsert by `(day, city)`, but that does not remove a city
    that has no sales in the new load; delete-then-insert does.

**20.5** On SQLite, a program runs `BEGIN`, an `INSERT` that works, a second `INSERT` that fails on a `UNIQUE`
constraint, and then `COMMIT` without checking for errors. What is in the table? What would be in it on PostgreSQL?

??? success "Answer"
    On SQLite the first row is saved: only the failing statement was undone, and `COMMIT` committed the rest. On
    PostgreSQL nothing is saved: the error aborted the transaction and `COMMIT` did a rollback. The timelines in
    [20.3](#errors) show the same thing with a `CHECK` constraint. Either way the program should have run `ROLLBACK`
    when the second statement failed.

**20.6** Two nightly jobs both update accounts 1 and 2. Job X updates 1 then 2; job Y updates 2 then 1. Once a month
one of them fails with "deadlock detected". Give two fixes.

??? success "Answer"
    Make both jobs lock the rows in the same order (for example ascending `id`), or change both rows in a single
    statement (as in 20.2), which usually takes the locks in the same order. Also add a retry on
    SQLSTATE `40P01`, because some deadlock risk remains in any busy system.

**Next:** [21. Views and materialized views](21-Views-and-Materialized-Views.md).
