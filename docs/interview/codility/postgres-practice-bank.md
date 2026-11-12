# PostgreSQL practice: account data

Eight tasks written for PostgreSQL, using what it offers in a test: DISTINCT ON, FILTER, date_trunc and intervals, generate_series, string_agg and RANGE window frames, on accounts, payments and balances. Every solution was run on PostgreSQL 16 with the example and gave exactly the expected result. They have not had random or large-table tests, so write your own edge cases before you open a solution.

### 1. Money in and out per account per month

**Topic:** date_trunc and FILTER (WHERE ...)

Each row of `txns` is one card or transfer movement. A positive `amount` is money in (a credit), a negative one is money out (a debit). Amounts are whole dollars.

For every account and every calendar month in which it had at least one movement, return `account_id`, `month` (the first day of the month, as a date), `txn_count`, `credits` (how many credits), `debits` (how many debits), `money_in` (sum of credits) and `money_out` (sum of debits as a positive number). A month with no credits shows `0`, not `NULL`. Sort by `account_id`, then `month`.

**Tables and example data**

```sql
CREATE TABLE txns (
    txn_id     INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    ts         TIMESTAMP NOT NULL,
    amount     INTEGER NOT NULL
);
INSERT INTO txns VALUES (1, 1, '2026-01-03 10:00:00', 1000);
INSERT INTO txns VALUES (2, 1, '2026-01-15 12:30:00', -200);
INSERT INTO txns VALUES (3, 1, '2026-01-31 23:59:59', -50);
INSERT INTO txns VALUES (4, 1, '2026-02-01 00:00:00', -300);
INSERT INTO txns VALUES (5, 2, '2026-01-20 09:00:00', -80);
INSERT INTO txns VALUES (6, 2, '2026-01-21 09:00:00', -20);
INSERT INTO txns VALUES (7, 2, '2026-03-02 08:00:00', 500);
INSERT INTO txns VALUES (8, 1, '2026-02-14 18:00:00', 250);
```

**Your query should return**

| account_id | month | txn_count | credits | debits | money_in | money_out |
|---|---|---|---|---|---|---|
| 1 | 2026-01-01 | 3 | 1 | 2 | 1000 | 250 |
| 1 | 2026-02-01 | 2 | 1 | 1 | 250 | 300 |
| 2 | 2026-01-01 | 2 | 0 | 2 | 0 | 100 |
| 2 | 2026-03-01 | 1 | 1 | 0 | 500 | 0 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    SELECT account_id,
           date_trunc('month', ts)::date AS month,
           COUNT(*) AS txn_count,
           COUNT(*) FILTER (WHERE amount > 0) AS credits,
           COUNT(*) FILTER (WHERE amount < 0) AS debits,
           COALESCE(SUM(amount) FILTER (WHERE amount > 0), 0) AS money_in,
           COALESCE(SUM(-amount) FILTER (WHERE amount < 0), 0) AS money_out
    FROM txns
    GROUP BY account_id, date_trunc('month', ts)
    ORDER BY account_id, month;
    ```

    **Why it works**

    1. `date_trunc('month', ts)` cuts every timestamp back to midnight on the 1st, so all rows of a month share one key; `::date` drops the `00:00:00`.
    2. `FILTER (WHERE ...)` makes one aggregate look only at some rows. It is the short form of `SUM(CASE WHEN ... THEN amount END)`.
    3. A filtered `SUM` over no rows is `NULL` (account 2 in January has no credits), so `COALESCE(..., 0)` is needed. A filtered `COUNT` already gives `0`.
    4. `23:59:59` on 31 January stays in January and `00:00:00` on 1 February goes to February: no string cutting, no off-by-one.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 2. Top three merchants per customer in one line

**Topic:** string_agg with ORDER BY

`card_txns` holds card purchases. For each customer, rank merchants by the customer's total spend there, highest first; on a tie the merchant name decides (A before Z).

Return `customer_id` and `top_merchants`: the names of the top three merchants (fewer if the customer used fewer) in rank order, joined with `', '`. Sort by `customer_id`.

**Tables and example data**

```sql
CREATE TABLE card_txns (
    txn_id      INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    merchant    TEXT NOT NULL,
    amount      INTEGER NOT NULL
);
INSERT INTO card_txns VALUES (1, 1, 'Grocer', 40);
INSERT INTO card_txns VALUES (2, 1, 'Cafe', 12);
INSERT INTO card_txns VALUES (3, 1, 'Grocer', 35);
INSERT INTO card_txns VALUES (4, 1, 'Fuel', 60);
INSERT INTO card_txns VALUES (5, 1, 'Cafe', 8);
INSERT INTO card_txns VALUES (6, 1, 'Books', 25);
INSERT INTO card_txns VALUES (7, 1, 'Cafe', 5);
INSERT INTO card_txns VALUES (8, 2, 'Airline', 900);
INSERT INTO card_txns VALUES (9, 3, 'Grocer', 10);
INSERT INTO card_txns VALUES (10, 3, 'Cafe', 10);
```

**Your query should return**

| customer_id | top_merchants |
|---|---|
| 1 | Grocer, Fuel, Books |
| 2 | Airline |
| 3 | Cafe, Grocer |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    WITH totals AS (
        SELECT customer_id, merchant, SUM(amount) AS spent
        FROM card_txns
        GROUP BY customer_id, merchant
    ),
    ranked AS (
        SELECT customer_id, merchant,
               ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY spent DESC, merchant) AS rn
        FROM totals
    )
    SELECT customer_id, string_agg(merchant, ', ' ORDER BY rn) AS top_merchants
    FROM ranked
    WHERE rn <= 3
    GROUP BY customer_id
    ORDER BY customer_id;
    ```

    **Why it works**

    1. Sum first, rank second: customer 1's Cafe total is 25 from three small rows, which ties Books at 25.
    2. `ROW_NUMBER` with `merchant` as the second sort key breaks that tie the same way every run (Books before Cafe), so exactly three names come out.
    3. `string_agg(merchant, ', ' ORDER BY rn)` sets the order inside the string. Without the `ORDER BY` the order of the names is not promised.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 3. Month-end balance snapshot

**Topic:** DISTINCT ON

`balance_log` gets a row every time an account's balance changes; `balance` is the balance right after that change. Two rows can carry the same `logged_at`; then the larger `log_id` was written last.

For each account and each month in which it has log rows, return the balance at the end of that month: `account_id`, `month_end` (the last day of the month, as a date) and `balance`. Sort by `account_id`, then `month_end`.

**Tables and example data**

```sql
CREATE TABLE balance_log (
    log_id     INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    logged_at  TIMESTAMP NOT NULL,
    balance    INTEGER NOT NULL
);
INSERT INTO balance_log VALUES (1, 1, '2026-01-05 10:00:00', 500);
INSERT INTO balance_log VALUES (2, 1, '2026-01-31 23:59:59', 450);
INSERT INTO balance_log VALUES (3, 1, '2026-02-01 00:00:00', 300);
INSERT INTO balance_log VALUES (4, 1, '2026-02-20 15:00:00', 320);
INSERT INTO balance_log VALUES (5, 1, '2026-02-20 15:00:00', 310);
INSERT INTO balance_log VALUES (6, 2, '2026-01-10 09:00:00', 1000);
INSERT INTO balance_log VALUES (7, 2, '2026-03-03 12:00:00', 900);
INSERT INTO balance_log VALUES (8, 2, '2026-03-31 08:00:00', 950);
```

**Your query should return**

| account_id | month_end | balance |
|---|---|---|
| 1 | 2026-01-31 | 450 |
| 1 | 2026-02-28 | 310 |
| 2 | 2026-01-31 | 1000 |
| 2 | 2026-03-31 | 950 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    SELECT DISTINCT ON (account_id, date_trunc('month', logged_at))
           account_id,
           (date_trunc('month', logged_at) + INTERVAL '1 month' - INTERVAL '1 day')::date AS month_end,
           balance
    FROM balance_log
    ORDER BY account_id, date_trunc('month', logged_at), logged_at DESC, log_id DESC;
    ```

    **Why it works**

    1. `DISTINCT ON (a, b)` keeps the first row of each `(a, b)` group, and "first" means first by the `ORDER BY`.
    2. So the `ORDER BY` must start with the same expressions as `DISTINCT ON`, then say which row wins: latest `logged_at`, then latest `log_id` for the 20 February tie (310, not 320).
    3. Start of month + 1 month - 1 day is the last day of the month, also for February (28th in 2026).
    4. Account 2 has no February row, so it has no February snapshot. Filling that month would need a calendar of months (see task 7).

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 4. Accounts dormant for 90 days

**Topic:** interval arithmetic and COALESCE with LEFT JOIN

An account is dormant on 30 June 2026 if nothing happened on it from `2026-06-30` minus 90 days (that is, from `2026-04-01 00:00:00`) onward. Its last activity is its latest transaction, or its opening date if it never had one.

Return the dormant accounts with `account_id`, `last_activity` (a date) and `days_quiet` (whole days from `last_activity` to 30 June 2026). Sort by `days_quiet` from most to fewest, then `account_id`.

**Tables and example data**

```sql
CREATE TABLE accounts (
    account_id INTEGER PRIMARY KEY,
    opened_on  DATE NOT NULL
);
CREATE TABLE txns (
    txn_id     INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    ts         TIMESTAMP NOT NULL,
    amount     INTEGER NOT NULL
);
INSERT INTO accounts VALUES (1, '2025-01-10');
INSERT INTO accounts VALUES (2, '2025-06-01');
INSERT INTO accounts VALUES (3, '2026-01-15');
INSERT INTO accounts VALUES (4, '2026-05-01');
INSERT INTO accounts VALUES (5, '2025-11-20');
INSERT INTO txns VALUES (1, 1, '2025-12-01 10:00:00', 200);
INSERT INTO txns VALUES (2, 1, '2026-03-31 23:59:00', -40);
INSERT INTO txns VALUES (3, 2, '2026-04-01 00:00:00', -15);
INSERT INTO txns VALUES (4, 5, '2026-02-10 14:00:00', 75);
```

**Your query should return**

| account_id | last_activity | days_quiet |
|---|---|---|
| 3 | 2026-01-15 | 166 |
| 5 | 2026-02-10 | 140 |
| 1 | 2026-03-31 | 91 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    SELECT a.account_id,
           COALESCE(MAX(t.ts)::date, a.opened_on) AS last_activity,
           DATE '2026-06-30' - COALESCE(MAX(t.ts)::date, a.opened_on) AS days_quiet
    FROM accounts a
    LEFT JOIN txns t ON t.account_id = a.account_id
    GROUP BY a.account_id, a.opened_on
    HAVING COALESCE(MAX(t.ts), a.opened_on) < DATE '2026-06-30' - INTERVAL '90 days'
    ORDER BY days_quiet DESC, a.account_id;
    ```

    **Why it works**

    1. `LEFT JOIN` keeps accounts with no transactions (3 and 4); their `MAX(t.ts)` is `NULL`, and `COALESCE` falls back to `opened_on`.
    2. `DATE '2026-06-30' - INTERVAL '90 days'` is the timestamp `2026-04-01 00:00:00`. Account 2's movement at exactly that moment counts as activity, so it is not dormant; account 1's at 23:59 the day before does not save it.
    3. A date minus a date is a whole number of days in PostgreSQL, so `days_quiet` needs no `EXTRACT`.
    4. Account 4 never moved but was opened on 1 May, so it is new, not dormant. An inner join would have lost accounts 3 and 4 and given a wrong answer for 3.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 5. The transaction that made the account overdrawn

**Topic:** running balance with a ROWS frame

Every account in `txns` starts at a balance of 0. Post the movements in order of `ts`; two movements with the same `ts` are posted in `txn_id` order.

Return the movements that took an account from zero or above to below zero: `account_id`, `txn_id`, `ts`, `amount` and `balance` (after this movement). Movements that keep an already negative balance negative are not listed. Sort by `account_id`, `ts`, `txn_id`.

**Tables and example data**

```sql
CREATE TABLE txns (
    txn_id     INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    ts         TIMESTAMP NOT NULL,
    amount     INTEGER NOT NULL
);
INSERT INTO txns VALUES (1, 1, '2026-03-01 09:00:00', 100);
INSERT INTO txns VALUES (2, 1, '2026-03-02 10:00:00', -80);
INSERT INTO txns VALUES (3, 1, '2026-03-02 10:00:00', -50);
INSERT INTO txns VALUES (4, 1, '2026-03-03 08:00:00', 40);
INSERT INTO txns VALUES (5, 1, '2026-03-04 12:00:00', -25);
INSERT INTO txns VALUES (6, 1, '2026-03-04 13:00:00', -5);
INSERT INTO txns VALUES (7, 2, '2026-03-01 11:00:00', -10);
INSERT INTO txns VALUES (8, 2, '2026-03-05 09:00:00', 50);
INSERT INTO txns VALUES (9, 3, '2026-03-02 10:00:00', 30);
INSERT INTO txns VALUES (10, 3, '2026-03-02 10:00:00', -30);
```

**Your query should return**

| account_id | txn_id | ts | amount | balance |
|---|---|---|---|---|
| 1 | 3 | 2026-03-02 10:00:00 | -50 | -30 |
| 1 | 5 | 2026-03-04 12:00:00 | -25 | -15 |
| 2 | 7 | 2026-03-01 11:00:00 | -10 | -10 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    WITH r AS (
        SELECT account_id, txn_id, ts, amount,
               SUM(amount) OVER (PARTITION BY account_id ORDER BY ts, txn_id
                                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS balance
        FROM txns
    )
    SELECT account_id, txn_id, ts, amount, balance
    FROM r
    WHERE balance < 0 AND balance - amount >= 0
    ORDER BY account_id, ts, txn_id;
    ```

    **Why it works**

    1. The running `SUM` is the balance after each row; `balance - amount` is the balance just before it, so no `LAG` is needed.
    2. With `ORDER BY ts` alone the default frame is `RANGE`, and rows 2 and 3 (same `ts`) would both get -30. Row 2 would then look like it went from 50 to -30 and be listed wrongly.
    3. Adding `txn_id` to the order and saying `ROWS` gives each row its own balance: row 2 leaves 20, row 3 leaves -30.
    4. Account 3 ends at exactly 0, which is not overdrawn; account 1 goes negative twice and both times are listed.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 6. Card charges repeated within 5 minutes

**Topic:** window frame with RANGE and an interval

A charge is a suspected duplicate if an earlier charge with the same `account_id`, `merchant` and `amount` happened at most 5 minutes (300 seconds) before it. The first charge of such a run is not a duplicate. No two charges of one account share a timestamp.

Return the suspected duplicates: `txn_id`, `account_id`, `merchant`, `amount`, `ts`. Sort by `txn_id`.

**Tables and example data**

```sql
CREATE TABLE charges (
    txn_id     INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    merchant   TEXT NOT NULL,
    amount     INTEGER NOT NULL,
    ts         TIMESTAMP NOT NULL
);
INSERT INTO charges VALUES (1, 1, 'Cafe', 5, '2026-03-01 08:00:00');
INSERT INTO charges VALUES (2, 1, 'Cafe', 5, '2026-03-01 08:03:00');
INSERT INTO charges VALUES (3, 1, 'Cafe', 5, '2026-03-01 08:07:30');
INSERT INTO charges VALUES (4, 1, 'Cafe', 6, '2026-03-01 08:08:00');
INSERT INTO charges VALUES (5, 2, 'Cafe', 5, '2026-03-01 08:01:00');
INSERT INTO charges VALUES (6, 1, 'Grocer', 40, '2026-03-01 09:00:00');
INSERT INTO charges VALUES (7, 1, 'Grocer', 40, '2026-03-01 09:05:00');
INSERT INTO charges VALUES (8, 1, 'Grocer', 40, '2026-03-01 09:10:01');
```

**Your query should return**

| txn_id | account_id | merchant | amount | ts |
|---|---|---|---|---|
| 2 | 1 | Cafe | 5 | 2026-03-01 08:03:00 |
| 3 | 1 | Cafe | 5 | 2026-03-01 08:07:30 |
| 7 | 1 | Grocer | 40 | 2026-03-01 09:05:00 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    WITH w AS (
        SELECT c.*,
               COUNT(*) OVER (PARTITION BY account_id, merchant, amount ORDER BY ts
                              RANGE BETWEEN INTERVAL '5 minutes' PRECEDING AND CURRENT ROW) AS n
        FROM charges c
    )
    SELECT txn_id, account_id, merchant, amount, ts
    FROM w
    WHERE n > 1
    ORDER BY txn_id;
    ```

    **Why it works**

    1. `RANGE BETWEEN INTERVAL '5 minutes' PRECEDING AND CURRENT ROW` holds every row of the group whose `ts` is in the 5 minutes up to this row, ends included. `ROWS` would count rows, not time.
    2. `n > 1` means some earlier matching charge is in that window. Row 3 is 7.5 minutes after row 1 but 4.5 after row 2, so it is flagged.
    3. Row 7 is exactly 5:00 after row 6 and is flagged; row 8 is 5:01 after row 7 and is not.
    4. Rows 4 (other amount) and 5 (other account) fall in other partitions. If two charges could share a timestamp they would be peers in `RANGE` and both get flagged, which is why the task rules that out.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 7. Daily balances with quiet days filled in

**Topic:** generate_series and COALESCE with LEFT JOIN

`accounts` gives each account's balance at the start of 1 March 2026. `txns` lists that week's movements by date.

Return the end-of-day balance for every account on every day from 1 to 5 March 2026, also days with no movement and accounts with no movement at all: `account_id`, `day`, `balance`. Sort by `account_id`, then `day`.

**Tables and example data**

```sql
CREATE TABLE accounts (
    account_id      INTEGER PRIMARY KEY,
    opening_balance INTEGER NOT NULL
);
CREATE TABLE txns (
    txn_id     INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    txn_date   DATE NOT NULL,
    amount     INTEGER NOT NULL
);
INSERT INTO accounts VALUES (1, 500);
INSERT INTO accounts VALUES (2, 0);
INSERT INTO accounts VALUES (3, 1000);
INSERT INTO txns VALUES (1, 1, '2026-03-01', -50);
INSERT INTO txns VALUES (2, 1, '2026-03-01', 200);
INSERT INTO txns VALUES (3, 1, '2026-03-04', -100);
INSERT INTO txns VALUES (4, 2, '2026-03-02', 300);
INSERT INTO txns VALUES (5, 2, '2026-03-05', -120);
INSERT INTO txns VALUES (6, 1, '2026-03-05', -25);
```

**Your query should return**

| account_id | day | balance |
|---|---|---|
| 1 | 2026-03-01 | 650 |
| 1 | 2026-03-02 | 650 |
| 1 | 2026-03-03 | 650 |
| 1 | 2026-03-04 | 550 |
| 1 | 2026-03-05 | 525 |
| 2 | 2026-03-01 | 0 |
| 2 | 2026-03-02 | 300 |
| 2 | 2026-03-03 | 300 |
| 2 | 2026-03-04 | 300 |
| 2 | 2026-03-05 | 180 |
| 3 | 2026-03-01 | 1000 |
| 3 | 2026-03-02 | 1000 |
| 3 | 2026-03-03 | 1000 |
| 3 | 2026-03-04 | 1000 |
| 3 | 2026-03-05 | 1000 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    WITH days AS (
        SELECT d::date AS day
        FROM generate_series(DATE '2026-03-01', DATE '2026-03-05', INTERVAL '1 day') AS g(d)
    ),
    daily AS (
        SELECT account_id, txn_date, SUM(amount) AS net
        FROM txns
        GROUP BY account_id, txn_date
    )
    SELECT a.account_id, d.day,
           a.opening_balance
             + SUM(COALESCE(x.net, 0)) OVER (PARTITION BY a.account_id ORDER BY d.day) AS balance
    FROM accounts a
    CROSS JOIN days d
    LEFT JOIN daily x ON x.account_id = a.account_id AND x.txn_date = d.day
    ORDER BY a.account_id, d.day;
    ```

    **Why it works**

    1. `generate_series` with a 1-day step makes the calendar; `CROSS JOIN` with `accounts` gives one row for every account and day (15 rows), even for account 3, which never moved.
    2. Movements are summed per day first; joining raw rows would give two rows for account 1 on 1 March and break the running sum.
    3. `LEFT JOIN` keeps quiet days, `COALESCE(x.net, 0)` turns their missing net into 0, and the running `SUM` carries the balance forward. Days are unique per account, so the default `RANGE` frame is safe here.
    4. The cast `d::date` matters: `generate_series` over dates returns timestamps, and the join to `txn_date` and the output want dates.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.


### 8. Failed payments and their retries

**Topic:** a CTE chain of three steps

A payment can be tried several times; each try is a row in `attempts` with `status` `'ok'` or `'failed'`. A payment is recovered when some try succeeds. Only failed tries before the first success count; a failed try after the payment already went through (a stray retry) is ignored.

For each payment with at least one counted failed try, return `payment_id`, `failed_tries` and `outcome` (`'recovered'` or `'gave up'`). Sort by `payment_id`. Write it as three named steps.

**Tables and example data**

```sql
CREATE TABLE attempts (
    attempt_id INTEGER PRIMARY KEY,
    payment_id INTEGER NOT NULL,
    tried_at   TIMESTAMP NOT NULL,
    status     TEXT NOT NULL
);
INSERT INTO attempts VALUES (1, 10, '2026-03-01 09:00:00', 'failed');
INSERT INTO attempts VALUES (2, 10, '2026-03-01 09:05:00', 'failed');
INSERT INTO attempts VALUES (3, 10, '2026-03-01 09:20:00', 'ok');
INSERT INTO attempts VALUES (4, 11, '2026-03-01 10:00:00', 'ok');
INSERT INTO attempts VALUES (5, 12, '2026-03-01 10:30:00', 'failed');
INSERT INTO attempts VALUES (6, 12, '2026-03-01 11:30:00', 'failed');
INSERT INTO attempts VALUES (7, 12, '2026-03-01 13:30:00', 'failed');
INSERT INTO attempts VALUES (8, 13, '2026-03-01 11:00:00', 'failed');
INSERT INTO attempts VALUES (9, 13, '2026-03-01 11:10:00', 'ok');
INSERT INTO attempts VALUES (10, 13, '2026-03-01 11:30:00', 'failed');
INSERT INTO attempts VALUES (11, 14, '2026-03-01 12:00:00', 'ok');
INSERT INTO attempts VALUES (12, 14, '2026-03-01 12:05:00', 'failed');
```

**Your query should return**

| payment_id | failed_tries | outcome |
|---|---|---|
| 10 | 2 | recovered |
| 12 | 3 | gave up |
| 13 | 1 | recovered |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**

    ```sql
    WITH first_ok AS (
        SELECT payment_id, MIN(tried_at) FILTER (WHERE status = 'ok') AS ok_at
        FROM attempts
        GROUP BY payment_id
    ),
    fails AS (
        SELECT a.payment_id, COUNT(*) AS failed_tries
        FROM attempts a
        JOIN first_ok f ON f.payment_id = a.payment_id
        WHERE a.status = 'failed' AND (f.ok_at IS NULL OR a.tried_at < f.ok_at)
        GROUP BY a.payment_id
    ),
    summary AS (
        SELECT x.payment_id, x.failed_tries,
               CASE WHEN f.ok_at IS NULL THEN 'gave up' ELSE 'recovered' END AS outcome
        FROM fails x
        JOIN first_ok f ON f.payment_id = x.payment_id
    )
    SELECT payment_id, failed_tries, outcome
    FROM summary
    ORDER BY payment_id;
    ```

    **Why it works**

    1. Step 1 finds each payment's first success; it is `NULL` when there was none (payment 12).
    2. Step 2 counts only failures before that moment. Payment 13's failure at 11:30 and payment 14's at 12:05 come after a success and are dropped, so 14 has no row at all.
    3. Step 3 labels each payment from step 1's time. Each step is small enough to run and check on its own, which is the point of a chain.
    4. Payment 11 never failed, so step 2 gives it no row and it is not listed.

    **Tested on PostgreSQL 16** with the example above: exactly the expected rows, columns and order.
