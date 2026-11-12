# Full mock B: 3 tasks in 150 minutes

The second full rehearsal, for Sunday 15 November. It has the format of your test: **three tasks, 150 minutes, in one sitting, no pause.**
**Set a timer for 150 minutes** and do not open a solution until the timer ends.

| Task | Type | Level | Aim for |
|---|---|---|---|
| 1 | SQL | Medium | 30 minutes |
| 2 | SQL | Hard | 45 minutes |
| 3 | Python | Medium | 35 minutes |

Every SQL task here was tested on **PostgreSQL only** (`sql-postgres` in the test's language menu). The Python
tasks use the standard library only.

**How to take it.** Read all three tasks first (10 minutes) and start with the one you see the clearest path
for. Write each answer in a plain text editor or on paper, the way you would type it into Codility's editor.
When the timer ends, paste each answer into its **Try it here** box: Run checks it on the example, **Check** also
on the edge cases from the solution. Then open the solutions, including the wrong answers, and write down every
mistake you made.

Before you open a solution, write down the edge cases you thought of. Then compare with the list in the solution.

---

### Task&nbsp;1: From first to second order

**Level:** Medium · **Aim for:** 30 minutes

A shop wants to know how quickly customers come back. A customer's orders are put in order by `ordered_on`, and
orders on the same day by `id`; the first two in that order are the customer's **first** and **second** order (they
can be on the same day).

Write an SQL query (PostgreSQL) that returns one row for each customer with **at least two orders**:

* `customer_id`;
* `first_on` and `second_on`: the dates of the first and second order;
* `days_between`: the number of days from the first to the second (0 if the same day);
* `trend`: `'up'` if the second order's `amount` is higher than the first's, `'down'` if lower, `'same'` if equal.

Sort by `days_between`, then by `customer_id`.

**Tables**

```sql
CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    ordered_on  DATE NOT NULL,
    amount      INTEGER NOT NULL
);
```

**Example data**

`orders`

| id | customer_id | ordered_on | amount |
|---|---|---|---|
| 1 | 7 | 2026-04-01 | 30 |
| 2 | 7 | 2026-04-09 | 45 |
| 3 | 7 | 2026-04-02 | 20 |
| 4 | 8 | 2026-04-03 | 50 |
| 5 | 9 | 2026-04-05 | 25 |
| 6 | 9 | 2026-04-05 | 25 |
| 7 | 9 | 2026-04-06 | 10 |
| 8 | 10 | 2026-04-02 | 60 |
| 9 | 10 | 2026-04-30 | 15 |

**Your query should return**

| customer_id | first_on | second_on | days_between | trend |
|---|---|---|---|---|
| 9 | 2026-04-05 | 2026-04-05 | 0 | same |
| 7 | 2026-04-01 | 2026-04-02 | 1 | down |
| 10 | 2026-04-02 | 2026-04-30 | 28 | down |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**
    
    ```sql
    WITH numbered AS (
        SELECT customer_id, ordered_on, amount,
               ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY ordered_on, id) AS n
        FROM orders
    )
    SELECT f.customer_id,
           f.ordered_on                AS first_on,
           s.ordered_on                AS second_on,
           s.ordered_on - f.ordered_on AS days_between,
           CASE WHEN s.amount > f.amount THEN 'up'
                WHEN s.amount < f.amount THEN 'down'
                ELSE 'same' END        AS trend
    FROM numbered f
    JOIN numbered s ON s.customer_id = f.customer_id AND s.n = 2
    WHERE f.n = 1
    ORDER BY days_between, f.customer_id;
    ```
    
    **Why it works**
    
    * `ROW_NUMBER` numbers each customer's orders 1, 2, 3, ... in the order the task defines, with `id` breaking ties
      on the same day. Then a **self-join** puts order 1 and order 2 of the same customer side by side. A customer with
      one order has no `n = 2` row, so the inner join drops them, as asked.
    * Why not `RANK`? Two orders on the same day would both get rank 1 and there would be no rank 2. `ROW_NUMBER`
      never ties.
    * Why not "the first date after the first order"? A second order on the **same day** as the first (customer 9) has
      no later date; numbering handles it.
    * In PostgreSQL a date minus a date is a whole number of days.
    * Another way to write it: `LEAD(ordered_on) OVER (...)` and `LEAD(amount) OVER (...)` on each row, then keep the
      rows with `n = 1`. Same result, one pass.
    
    **Tested on PostgreSQL 16.** Every case below gave exactly the expected rows, columns and order:
    
    * the example above;
    * edge case: a customer with one order;
    * edge case: same day, order decided by id;
    * edge case: three orders on one day;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.24 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: RANK instead of ROW_NUMBER"
    
        ```sql
        WITH n AS (SELECT customer_id, ordered_on, amount,
               RANK() OVER (PARTITION BY customer_id ORDER BY ordered_on) AS n FROM orders)
        SELECT f.customer_id, f.ordered_on AS first_on, s.ordered_on AS second_on, s.ordered_on - f.ordered_on AS days_between,
               CASE WHEN s.amount > f.amount THEN 'up' WHEN s.amount < f.amount THEN 'down' ELSE 'same' END AS trend
        FROM n f JOIN n s ON s.customer_id = f.customer_id AND s.n = 2 WHERE f.n = 1
        ORDER BY days_between, f.customer_id;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.
    
    ??? failure "A common wrong answer: the second order as the next later date"
    
        ```sql
        WITH f AS (SELECT customer_id, MIN(ordered_on) AS first_on FROM orders GROUP BY customer_id),
        s AS (SELECT o.customer_id, MIN(o.ordered_on) AS second_on FROM orders o JOIN f ON f.customer_id = o.customer_id
              WHERE o.ordered_on > f.first_on GROUP BY o.customer_id)
        SELECT f.customer_id, f.first_on, s.second_on, s.second_on - f.first_on AS days_between, 'same' AS trend
        FROM f JOIN s ON s.customer_id = f.customer_id ORDER BY days_between, f.customer_id;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.
    
    ??? failure "A common wrong answer: no tie-break on the same day"
    
        ```sql
        WITH n AS (SELECT customer_id, ordered_on, amount,
               ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY ordered_on, amount DESC) AS n FROM orders)
        SELECT f.customer_id, f.ordered_on AS first_on, s.ordered_on AS second_on, s.ordered_on - f.ordered_on AS days_between,
               CASE WHEN s.amount > f.amount THEN 'up' WHEN s.amount < f.amount THEN 'down' ELSE 'same' END AS trend
        FROM n f JOIN n s ON s.customer_id = f.customer_id AND s.n = 2 WHERE f.n = 1
        ORDER BY days_between, f.customer_id;
        ```
        
        Checked on PostgreSQL 16: this fails on **edge: same day, order decided by id**.
        
        Here the tie on the same day is broken by `amount` instead of `id`, so it picks a different first order.



---

### Task&nbsp;2: Active and returning users each month

**Level:** Hard · **Aim for:** 45 minutes

Every sign-in to an app is one row of `logins` (a user can sign in many times a day).

A user is **active** in a month if they signed in at least once in it. An active user is **retained** in a month if
they were also active in the **previous calendar month**.

Write an SQL query (PostgreSQL) that returns one row for **every month** from the month of the earliest sign-in to
the month of the latest one, **including months with no sign-ins**, with:

* `month`: the month as text `'YYYY-MM'`;
* `active_users`: the number of different active users that month;
* `retained_users`: how many of them were active in the month before.

Sort by `month`. Return no rows if the table is empty.

**Tables**

```sql
CREATE TABLE logins (
    user_id  INTEGER NOT NULL,
    login_at TIMESTAMP NOT NULL
);
```

**Example data**

`logins`

| user_id | login_at |
|---|---|
| 1 | 2025-12-30 22:10:00 |
| 1 | 2026-01-02 08:00:00 |
| 1 | 2026-01-02 09:30:00 |
| 2 | 2026-01-15 12:00:00 |
| 2 | 2026-03-03 10:00:00 |
| 3 | 2026-03-31 23:59:00 |
| 1 | 2026-04-01 00:01:00 |
| 3 | 2026-04-20 07:45:00 |

**Your query should return**

| month | active_users | retained_users |
|---|---|---|
| 2025-12 | 1 | 0 |
| 2026-01 | 2 | 1 |
| 2026-02 | 0 | 0 |
| 2026-03 | 2 | 0 |
| 2026-04 | 2 | 1 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**
    
    ```sql
    WITH active AS (                 -- 1. one row per user and month they were active
        SELECT DISTINCT user_id, date_trunc('month', login_at)::date AS month
        FROM logins
    ),
    months AS (                            -- 2. every month from the first to the last, even empty ones
        SELECT generate_series(MIN(month), MAX(month), INTERVAL '1 month')::date AS month
        FROM active
    )
    SELECT to_char(m.month, 'YYYY-MM') AS month,
           COUNT(cur.user_id)          AS active_users,
           COUNT(prev.user_id)         AS retained_users
    FROM months m
    LEFT JOIN active cur  ON cur.month = m.month
    LEFT JOIN active prev ON prev.user_id = cur.user_id
                         AND prev.month = (m.month - INTERVAL '1 month')::date
    GROUP BY m.month
    ORDER BY m.month;
    ```
    
    **Why it works**
    
    * **Step 1** reduces the log to one row per user per month (`DISTINCT` after `date_trunc('month', ...)`), so a user
      who signs in ten times in January counts once.
    * **Step 2** builds the list of months with `generate_series` (a "date spine"), so a month with no sign-ins still
      gets a row. Without it, February would be missing from the example. If the table is empty, `MIN` and `MAX` are
      `NULL` and `generate_series` returns no rows: no rows, as asked.
    * The two `LEFT JOIN`s attach the active users of each month (`cur`), and for each of them the same user in the
      month before (`prev`). `COUNT(column)` skips `NULL`s: an empty month counts 0 users, and a user with no `prev`
      row is not counted as retained. `COUNT(*)` would count the empty month as 1.
    * "Previous **calendar** month" means `month - 1 month`, not "the user's previous active month". User 2 in the
      example was active in January and March, not February, so in March they are not retained. `LAG` over each
      user's months would wrongly count them.
    * December to January crosses a year; `INTERVAL '1 month'` handles it (user 1 in the example).
    
    **Tested on PostgreSQL 16.** Every case below gave exactly the expected rows, columns and order:
    
    * the example above;
    * edge case: one sign-in;
    * edge case: a user back after a month away is not retained;
    * edge case: many sign-ins of one user in one month count once;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.33 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: no list of months (empty months missing)"
    
        ```sql
        WITH a AS (SELECT DISTINCT user_id, date_trunc('month', login_at)::date AS month FROM logins)
        SELECT to_char(cur.month, 'YYYY-MM') AS month, COUNT(cur.user_id) AS active_users, COUNT(prev.user_id) AS retained_users
        FROM a cur LEFT JOIN a prev ON prev.user_id = cur.user_id AND prev.month = (cur.month - INTERVAL '1 month')::date
        GROUP BY cur.month ORDER BY cur.month;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.
    
    ??? failure "A common wrong answer: retained = active in any earlier month (LAG)"
    
        ```sql
        WITH a AS (SELECT DISTINCT user_id, date_trunc('month', login_at)::date AS month FROM logins),
        l AS (SELECT *, LAG(month) OVER (PARTITION BY user_id ORDER BY month) AS before FROM a),
        months AS (SELECT generate_series(MIN(month), MAX(month), INTERVAL '1 month')::date AS month FROM a)
        SELECT to_char(m.month, 'YYYY-MM') AS month, COUNT(l.user_id) AS active_users, COUNT(l.before) AS retained_users
        FROM months m LEFT JOIN l ON l.month = m.month GROUP BY m.month ORDER BY m.month;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.
    
    ??? failure "A common wrong answer: COUNT(*) counts an empty month as 1"
    
        ```sql
        WITH a AS (SELECT DISTINCT user_id, date_trunc('month', login_at)::date AS month FROM logins),
        months AS (SELECT generate_series(MIN(month), MAX(month), INTERVAL '1 month')::date AS month FROM a)
        SELECT to_char(m.month, 'YYYY-MM') AS month, COUNT(*) AS active_users, COUNT(prev.user_id) AS retained_users
        FROM months m LEFT JOIN a cur ON cur.month = m.month
        LEFT JOIN a prev ON prev.user_id = cur.user_id AND prev.month = (m.month - INTERVAL '1 month')::date
        GROUP BY m.month ORDER BY m.month;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.



---

### Task&nbsp;3: Sessions from a click log

**Level:** Medium · **Aim for:** 35 minutes

A click log has one entry per click: user `U[i]` clicked at second `T[i]`. The log was collected from several
servers, so it is **not in time order**, and one user can have two clicks at the same second.

A **session** is a run of one user's clicks where each click comes at most `G` seconds after that user's previous
click. A pause of **more than** `G` seconds starts a new session. The length of a session is the time from its
first click to its last click (a session of one click has length 0).

Return a list of two integers: the number of sessions of all users together, and the length of the longest
session. For an empty log, return `[0, 0]`.

**Examples**

* `solution([7, 7, 7, 9], [100, 130, 300, 120], 60)` returns `[3, 30]`
* `solution([5, 5, 5], [50, 10, 30], 20)` returns `[1, 40]`
* `solution([], [], 10)` returns `[0, 0]`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `U` and `T`, is an integer within the range [0..100,000];
* each `U[i]` is an integer within the range [1..1,000,000,000];
* each `T[i]` is an integer within the range [0..1,000,000,000];
* `G` is an integer within the range [0..1,000,000,000].

Start from:

```python
def solution(U, T, G):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import defaultdict
    
    def solution(U, T, G):
        times = defaultdict(list)
        for u, t in zip(U, T):
            times[u].append(t)               # group by user (like GROUP BY / PARTITION BY)
        sessions = longest = 0
        for ts in times.values():
            ts.sort()                        # each user's clicks in time order
            start = ts[0]
            sessions += 1
            for prev, t in zip(ts, ts[1:]):
                if t - prev > G:             # a long pause: close the session, open a new one
                    longest = max(longest, prev - start)
                    start = t
                    sessions += 1
            longest = max(longest, ts[-1] - start)   # close the last session of this user
        return [sessions, longest]
    ```
    
    **Why it works**
    
    * This is the SQL "sessions" task (`LAG`, a flag for "new session", a running `SUM`) written in Python: **group by
      user, sort each group by time, then walk it once**.
    * Sorting is required: the log is not in time order. Sorting each user's list separately costs `O(N log N)` in
      total, the same as one big sort of `(user, time)` pairs, which also works.
    * "More than `G`" starts a new session, so the test is `t - prev > G`; a pause of exactly `G` keeps the session.
      Read this kind of word ("more than", "at least") twice in the real test.
    * Close the **last** session of each user after the loop: the loop only closes a session when a new one starts.
    * The slow answer looks up each user's clicks by scanning the whole log once per user: with 1,000 users and 100,000
      clicks that is 100 million steps.
    
    **Cost:** O(N log N) time for the sorts, O(N) memory.
    
    **The slow answer:** Scanning the whole log once for every user: O(U·N), 100 million steps for 1,000 users.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, a pause of exactly G stays in the session: `solution([1, 1], [0, 10], 10)` returns `[1, 10]`;
    * edge case, a pause of G + 1 starts a new one: `solution([1, 1], [0, 11], 10)` returns `[2, 0]`;
    * edge case, two clicks at the same second with G = 0: `solution([3, 3, 3], [5, 5, 6], 0)` returns `[2, 0]`;
    * edge case, clicks of different users never join: `solution([1, 2], [0, 1], 100)` returns `[2, 0]`;
    * edge case, one user, one click: `solution([4], [999], 5)` returns `[1, 0]`;
    * 800 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.022s.
    
    ??? failure "A common wrong answer: not sorting: assuming the log is in time order"
    
        ```python
        from collections import defaultdict
        
        def solution(U, T, G):
            times = defaultdict(list)
            for u, t in zip(U, T):
                times[u].append(t)
            sessions = longest = 0
            for ts in times.values():
                start = ts[0]
                sessions += 1
                for prev, t in zip(ts, ts[1:]):
                    if t - prev > G:
                        longest = max(longest, prev - start)
                        start = t
                        sessions += 1
                longest = max(longest, ts[-1] - start)
            return [sessions, longest]
        ```
        
        Checked: example: got [1, 0] want [1, 40].
    
    ??? failure "A common wrong answer: a pause of exactly G starts a new session (>= instead of >)"
    
        ```python
        from collections import defaultdict
        
        def solution(U, T, G):
            times = defaultdict(list)
            for u, t in zip(U, T):
                times[u].append(t)
            sessions = longest = 0
            for ts in times.values():
                ts.sort()
                start = ts[0]
                sessions += 1
                for prev, t in zip(ts, ts[1:]):
                    if t - prev >= G:
                        longest = max(longest, prev - start)
                        start = t
                        sessions += 1
                longest = max(longest, ts[-1] - start)
            return [sessions, longest]
        ```
        
        Checked: example: got [3, 0] want [1, 40].
    
    ??? failure "A common wrong answer: forgetting to close the last session"
    
        ```python
        from collections import defaultdict
        
        def solution(U, T, G):
            times = defaultdict(list)
            for u, t in zip(U, T):
                times[u].append(t)
            sessions = longest = 0
            for ts in times.values():
                ts.sort()
                start = ts[0]
                sessions += 1
                for prev, t in zip(ts, ts[1:]):
                    if t - prev > G:
                        longest = max(longest, prev - start)
                        start = t
                        sessions += 1
            return [sessions, longest]
        ```
        
        Checked: example: got [1, 0] want [1, 40].
    
    ??? failure "A common wrong answer: scanning the whole log once for every user (slow)"
    
        ```python
        def solution(U, T, G):
            sessions = longest = 0
            for u in set(U):
                ts = sorted(t for v, t in zip(U, T) if v == u)
                start = ts[0]
                sessions += 1
                for prev, t in zip(ts, ts[1:]):
                    if t - prev > G:
                        longest = max(longest, prev - start)
                        start = t
                        sessions += 1
                longest = max(longest, ts[-1] - start)
            return [sessions, longest]
        ```
        
        Checked: slow: 3.0s.



---

## After the mock

Compare with [Full mock A](full-mock-a.md): did the same kind of mistake come back? Task 1 is about
**numbering rows inside a group** (`ROW_NUMBER`), task 2 about **a list of every month** and comparing one month
with the one before, task 3 about **sessions** (sort, then look at the gap to the previous row). Read
[the 15 most common mistakes](common-mistakes.md) and tick the ones you made. Tomorrow: [Full mock C](full-mock-c.md).
