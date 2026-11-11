# Mock test 2

A second full rehearsal: two SQL tasks and one Python task. **Set a timer for 70 minutes.** Sit it a day or two
after Mock test 1, after some of the practice sets.

| Task | Type | Aim for |
|---|---|---|
| 1 | SQL | 20 minutes |
| 2 | SQL | 25 minutes |
| 3 | Python | 25 minutes |

Before you open a solution, write down the edge cases you tested. Then compare with the list in the solution.

---

### Task&nbsp;1: Ticket report by priority

**Level:** Medium · **Aim for:** 20 minutes

A support team logs tickets; `closed` is `NULL` while a ticket is still open. Write an SQL query that returns one
row per `priority` that has tickets, with:

* `still_open`: the number of tickets not yet closed;
* `avg_days`: the average number of days from `opened` to `closed` over **closed** tickets only, **rounded to one
  decimal place**; `NULL` if the priority has no closed ticket.

Sort by `priority`.

**Tables**

```sql
CREATE TABLE tickets (
    id       INTEGER PRIMARY KEY,
    priority INTEGER NOT NULL,
    opened   DATE NOT NULL,
    closed   DATE
);
```

**Example data**

`tickets`

| id | priority | opened | closed |
|---|---|---|---|
| 1 | 1 | 2026-03-01 | 2026-03-02 |
| 2 | 1 | 2026-03-01 | 2026-03-05 |
| 3 | 1 | 2026-03-03 | NULL |
| 4 | 2 | 2026-02-27 | 2026-03-01 |
| 5 | 3 | 2026-03-04 | NULL |
| 6 | 2 | 2026-03-02 | 2026-03-02 |
| 7 | 2 | 2026-03-01 | 2026-03-02 |

**Your query should return**

| priority | still_open | avg_days |
|---|---|---|
| 1 | 1 | 2.5 |
| 2 | 0 | 1.0 |
| 3 | 1 | NULL |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**
    
    ```sql
    SELECT priority,
           COUNT(*) - COUNT(closed)        AS still_open,
           ROUND(AVG(closed - opened), 1)  AS avg_days
    FROM tickets
    GROUP BY priority
    ORDER BY priority;
    ```
    
    **SQLite**
    
    ```sql
    SELECT priority,
           COUNT(*) - COUNT(closed)                               AS still_open,
           ROUND(AVG(julianday(closed) - julianday(opened)), 1)   AS avg_days
    FROM tickets
    GROUP BY priority
    ORDER BY priority;
    ```
    
    **Why it works**
    
    * **Let NULLs do the work.** `COUNT(closed)` counts only closed tickets, so `COUNT(*) - COUNT(closed)` is the
      number still open. For an open ticket, `closed - opened` is `NULL`, and `AVG` skips `NULL`s, so the average is
      over closed tickets only, and `NULL` when there are none. No `CASE` or `WHERE` needed.
    * A `WHERE closed IS NOT NULL` would be wrong: it removes the open tickets that `still_open` must count, and
      priority 3 (only open tickets) would disappear.
    * **Days between dates:** PostgreSQL `date - date` is a whole number of days; `AVG` of whole numbers is `numeric`,
      so `ROUND(..., 1)` works. SQLite has no date type: `julianday(closed) - julianday(opened)` gives the days.
    * Rounding: 4 / 3 = 1.333... becomes 1.3 (an edge case checks it).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: closed the same day (0 days);
    * edge case: over a leap day;
    * edge case: thirds round to one decimal;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.02 s, SQLite 3.53 0.06 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: WHERE removes open tickets"
    
        PostgreSQL:
        
        ```sql
        SELECT priority, COUNT(*) - COUNT(closed) AS still_open, ROUND(AVG(closed - opened), 1) AS avg_days
        FROM tickets WHERE closed IS NOT NULL GROUP BY priority ORDER BY priority;
        ```
        
        SQLite:
        
        ```sql
        SELECT priority, COUNT(*) - COUNT(closed) AS still_open, ROUND(AVG(julianday(closed) - julianday(opened)), 1) AS avg_days
        FROM tickets WHERE closed IS NOT NULL GROUP BY priority ORDER BY priority;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: treating open tickets as 0 days"
    
        PostgreSQL:
        
        ```sql
        SELECT priority, COUNT(*) - COUNT(closed) AS still_open, ROUND(AVG(COALESCE(closed - opened, 0)), 1) AS avg_days
        FROM tickets GROUP BY priority ORDER BY priority;
        ```
        
        SQLite:
        
        ```sql
        SELECT priority, COUNT(*) - COUNT(closed) AS still_open, ROUND(AVG(COALESCE(julianday(closed) - julianday(opened), 0)), 1) AS avg_days
        FROM tickets GROUP BY priority ORDER BY priority;
        ```
        
        Checked: this gives a wrong result on **sample**.



---

### Task&nbsp;2: First overdraft

**Level:** Medium to hard · **Aim for:** 25 minutes

Every account starts at 0, and each `ledger` row adds `amount` (negative for withdrawals) at time `booked_at`;
`(account, booked_at)` is unique. Write an SQL query that returns, for every account whose balance **ever goes
below zero**, the **first** moment it does: `account`, `booked_at` and the `balance` right after that row. Sort by
`account`. Accounts that never go below zero do not appear.

**Tables**

```sql
CREATE TABLE ledger (
    account   VARCHAR(10) NOT NULL,
    booked_at TIMESTAMP NOT NULL,
    amount    INTEGER NOT NULL
);
```

**Example data**

`ledger`

| account | booked_at | amount |
|---|---|---|
| A | 2026-04-01 09:00:00 | 50 |
| A | 2026-04-02 09:00:00 | -70 |
| A | 2026-04-03 09:00:00 | 100 |
| A | 2026-04-04 09:00:00 | -200 |
| B | 2026-04-01 10:00:00 | 10 |
| B | 2026-04-01 11:00:00 | -10 |
| C | 2026-04-05 08:00:00 | -5 |

**Your query should return**

| account | booked_at | balance |
|---|---|---|
| A | 2026-04-02 09:00:00 | -20 |
| C | 2026-04-05 08:00:00 | -5 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH running AS (
        SELECT account, booked_at,
               SUM(amount) OVER (PARTITION BY account ORDER BY booked_at
                                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS balance
        FROM ledger
    ),
    negatives AS (
        SELECT account, booked_at, balance,
               ROW_NUMBER() OVER (PARTITION BY account ORDER BY booked_at) AS rn
        FROM running
        WHERE balance < 0
    )
    SELECT account, booked_at, balance
    FROM negatives
    WHERE rn = 1
    ORDER BY account;
    ```
    
    **Why it works**
    
    * Step 1: a **running balance** per account (`SUM ... OVER (PARTITION BY account ORDER BY booked_at ...)`).
    * Step 2: keep only rows where it is below zero, and take each account's first such row with `ROW_NUMBER`.
    * The filter on `balance` must come **after** the running sum is computed, which is why the steps are separate
      CTEs. Filtering negative amounts first would compute a different running total.
    * `MIN(balance)` per account finds the lowest point, not the first time below zero (account A goes to −20 first
      and to −120 later).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: exactly zero is not below zero;
    * edge case: rows stored out of time order;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.17 s, SQLite 3.53 0.22 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: lowest balance instead of the first time below zero"
    
        ```sql
        WITH r AS (SELECT account, booked_at, SUM(amount) OVER (PARTITION BY account ORDER BY booked_at
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS balance FROM ledger),
        m AS (SELECT account, MIN(balance) AS lo FROM r GROUP BY account)
        SELECT r.account, r.booked_at, r.balance FROM r JOIN m ON m.account = r.account AND r.balance = m.lo
        WHERE m.lo < 0 ORDER BY r.account;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: running total without ORDER BY (the account's final balance)"
    
        ```sql
        WITH r AS (SELECT account, booked_at, SUM(amount) OVER (PARTITION BY account) AS balance FROM ledger),
        n AS (SELECT account, booked_at, balance, ROW_NUMBER() OVER (PARTITION BY account ORDER BY booked_at) AS rn FROM r WHERE balance < 0)
        SELECT account, booked_at, balance FROM n WHERE rn = 1 ORDER BY account;
        ```
        
        Checked: this gives a wrong result on **sample**.



---

### Task&nbsp;3: Late events

**Level:** Easy to medium · **Aim for:** 25 minutes

A streaming job receives events in arrival order; `T[i]` is the event time of the `i`-th event to arrive. The job
keeps a **watermark**: the largest event time seen **before** the current event, minus `W`. An event is **late**
if its time is strictly less than the watermark. The first event is never late.

Return the list of **positions** (0-based) of the late events, in increasing order.

**Examples**

* `solution([10, 12, 6, 20, 14, 16], 5)` returns `[2, 4]`
* `solution([5, 4, 3], 0)` returns `[1, 2]`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..200,000];
* each element of `T` is an integer within the range [0..1,000,000,000];
* `W` is an integer within the range [0..1,000,000,000].

Start from:

```python
def solution(T, W):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(T, W):
        late = []
        max_seen = None
        for i, t in enumerate(T):
            if max_seen is not None and t < max_seen - W:
                late.append(i)
            if max_seen is None or t > max_seen:
                max_seen = t
        return late
    ```
    
    **Why it works**
    
    * Keep one number: the largest event time seen so far. Compare each event with it, then update it. O(N) time,
      O(1) extra memory besides the answer. (Updating first gives the same answers here: an event that raises the
      maximum can never be below the maximum minus `W`.)
    * A late event never lowers the watermark: the maximum only grows (edge case "the watermark never moves back").
    * `max(T[:i])` for every event is the same rule written directly, but it is O(N²): with 200,000 events, about
      20 billion steps.
    * `<`, not `<=`: an event exactly on the watermark is on time (edge case). Starting `max_seen` at 0 instead of
      "nothing yet" would also work here because times are not negative, but `None` says what you mean.
    * Stream processors such as Spark Structured Streaming (used on Databricks) use watermarks in this spirit to
      decide when data is too late to change a result.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no events: `solution([], 5)` returns `[]`;
    * edge case, exactly on the watermark is on time: `solution([100, 95], 5)` returns `[]`;
    * edge case, one unit below the watermark is late: `solution([100, 94], 5)` returns `[1]`;
    * edge case, the watermark never moves back: `solution([50, 30, 46], 5)` returns `[1]`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.017s.
    
    ??? failure "A common wrong answer: <= puts on-time events in the late list"
    
        ```python
        def solution(T, W):
            late = []
            m = None
            for i, t in enumerate(T):
                if m is not None and t <= m - W:
                    late.append(i)
                m = t if m is None else max(m, t)
            return late
        ```
        
        Checked: edge: exactly on the watermark is on time: got [1] want [].
    
    ??? failure "A common wrong answer: max of the prefix every time (too slow)"
    
        ```python
        def solution(T, W):
            return [i for i in range(1, len(T)) if T[i] < max(T[:i]) - W]
        ```
        
        Checked: timed out after 5.0s on the large input.



---

## After the mock

Go to [the 15 most common mistakes](common-mistakes.md) and tick off the ones you made in either mock. Those are
the ones to watch for in the real test.
