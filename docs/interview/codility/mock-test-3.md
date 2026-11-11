# Mock test 3

A third rehearsal: two SQL tasks and one Python task. **Set a timer for 75 minutes.** The SQL is a little
harder than in mocks 1 and 2, and the Python task is a data engineering problem rather than a puzzle.

| Task | Type | Level | Aim for |
|---|---|---|---|
| 1 | SQL | Easy | 15 minutes |
| 2 | SQL | Hard | 25 minutes |
| 3 | Python | Medium | 30 minutes |

Before you open a solution, write down the edge cases you tested. Then compare with the list in the solution.

---

### Task&nbsp;1: Library loans

**Level:** Easy · **Aim for:** 15 minutes

A library records each loan; `returned` is `NULL` while the book is still out. Titles are unique. Write an SQL
query that returns **every** book with `title`, `loans` (how many times it was lent, 0 if never) and `on_loan`
(`'yes'` if it has a loan that has not been returned, otherwise `'no'`). Sort by `loans` from highest to lowest,
then `title`.

**Tables**

```sql
CREATE TABLE books (
    id    INTEGER PRIMARY KEY,
    title VARCHAR(60) NOT NULL
);
CREATE TABLE loans (
    id       INTEGER PRIMARY KEY,
    book_id  INTEGER NOT NULL,
    loaned   DATE NOT NULL,
    returned DATE
);
```

**Example data**

`books`

| id | title |
|---|---|
| 1 | Dune |
| 2 | Emma |
| 3 | Kim |
| 4 | Ulysses |

`loans`

| id | book_id | loaned | returned |
|---|---|---|---|
| 1 | 1 | 2026-02-01 | 2026-02-10 |
| 2 | 1 | 2026-02-12 | NULL |
| 3 | 2 | 2026-02-03 | 2026-02-04 |
| 4 | 2 | 2026-02-05 | 2026-02-09 |
| 5 | 3 | 2026-02-07 | NULL |

**Your query should return**

| title | loans | on_loan |
|---|---|---|
| Dune | 2 | yes |
| Emma | 2 | no |
| Kim | 1 | yes |
| Ulysses | 0 | no |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT b.title,
           COUNT(l.id) AS loans,
           CASE WHEN SUM(CASE WHEN l.id IS NOT NULL AND l.returned IS NULL THEN 1 ELSE 0 END) > 0
                THEN 'yes' ELSE 'no' END AS on_loan
    FROM books b
    LEFT JOIN loans l ON l.book_id = b.id
    GROUP BY b.id, b.title
    ORDER BY loans DESC, b.title;
    ```
    
    **Why it works**
    
    * `LEFT JOIN` keeps books that were never lent, and `COUNT(l.id)` gives them 0 (`COUNT(*)` would give 1).
    * **The trap is in `on_loan`.** A never-lent book gets one joined row where *every* loan column is `NULL`,
      including `returned`. So "`returned IS NULL`" alone says that book is on loan. Checking `l.id IS NOT NULL` too
      makes sure there is a real loan.
    * The inner `CASE` turns each row into 1 or 0, `SUM` counts the open loans, and the outer `CASE` turns the count
      into `'yes'` or `'no'`.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: no loans at all;
    * edge case: no books;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.09 s, SQLite 3.53 0.29 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: returned IS NULL also matches books never lent"
    
        ```sql
        SELECT b.title, COUNT(l.id) AS loans,
               CASE WHEN SUM(CASE WHEN l.returned IS NULL THEN 1 ELSE 0 END) > 0 THEN 'yes' ELSE 'no' END AS on_loan
        FROM books b LEFT JOIN loans l ON l.book_id = b.id
        GROUP BY b.id, b.title ORDER BY loans DESC, b.title;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: COUNT(*) gives never-lent books 1"
    
        ```sql
        SELECT b.title, COUNT(*) AS loans,
               CASE WHEN SUM(CASE WHEN l.id IS NOT NULL AND l.returned IS NULL THEN 1 ELSE 0 END) > 0 THEN 'yes' ELSE 'no' END AS on_loan
        FROM books b LEFT JOIN loans l ON l.book_id = b.id
        GROUP BY b.id, b.title ORDER BY loans DESC, b.title;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: inner JOIN drops books never lent"
    
        ```sql
        SELECT b.title, COUNT(l.id) AS loans,
               CASE WHEN SUM(CASE WHEN l.returned IS NULL THEN 1 ELSE 0 END) > 0 THEN 'yes' ELSE 'no' END AS on_loan
        FROM books b JOIN loans l ON l.book_id = b.id
        GROUP BY b.id, b.title ORDER BY loans DESC, b.title;
        ```
        
        Checked: this gives a wrong result on **sample**.



---

### Task&nbsp;2: Busiest moment for each day

**Level:** Hard · **Aim for:** 25 minutes

A call centre logs each call's start and end. Every call ends later than it starts, on the same day. A call is in
progress from `started` up to, **but not including**, `ended`, so a call that ends at 10:05 and one that starts
at 10:05 do not overlap. Write an SQL query that returns, for each day with at least one call, `call_day` (the
date) and `peak` (the largest number of calls in progress at the same moment). Sort by `call_day`.

**Tables**

```sql
CREATE TABLE calls (
    id      INTEGER PRIMARY KEY,
    started TIMESTAMP NOT NULL,
    ended   TIMESTAMP NOT NULL
);
```

**Example data**

`calls`

| id | started | ended |
|---|---|---|
| 1 | 2026-03-01 10:00:00 | 2026-03-01 10:05:00 |
| 2 | 2026-03-01 10:01:00 | 2026-03-01 10:03:00 |
| 3 | 2026-03-01 10:05:00 | 2026-03-01 10:09:00 |
| 4 | 2026-03-01 10:02:00 | 2026-03-01 10:06:00 |
| 5 | 2026-03-02 09:00:00 | 2026-03-02 09:30:00 |

**Your query should return**

| call_day | peak |
|---|---|
| 2026-03-01 | 3 |
| 2026-03-02 | 1 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**
    
    ```sql
    WITH ev AS (                                -- +1 when a call starts, -1 when it ends
        SELECT started AS t, 1 AS delta FROM calls
        UNION ALL
        SELECT ended, -1 FROM calls
    ),
    running AS (
        SELECT CAST(t AS DATE) AS call_day,
               SUM(delta) OVER (PARTITION BY CAST(t AS DATE)
                                ORDER BY t, delta          -- at a tie, -1 (an end) first
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS in_progress
        FROM ev
    )
    SELECT call_day, MAX(in_progress) AS peak
    FROM running
    GROUP BY call_day
    ORDER BY call_day;
    ```
    
    **SQLite**
    
    ```sql
    WITH ev AS (
        SELECT started AS t, 1 AS delta FROM calls
        UNION ALL
        SELECT ended, -1 FROM calls
    ),
    running AS (
        SELECT date(t) AS call_day,
               SUM(delta) OVER (PARTITION BY date(t)
                                ORDER BY t, delta
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS in_progress
        FROM ev
    )
    SELECT call_day, MAX(in_progress) AS peak
    FROM running
    GROUP BY call_day
    ORDER BY call_day;
    ```
    
    **Why it works**
    
    * The **sweep line** from Mock 1's Python task, in SQL. Each call becomes two events, `+1` at its start and `-1`
      at its end. A running `SUM` in time order is the number of calls in progress after each event, and the largest
      running value of the day is the peak.
    * **Ties.** At the same moment an end must count before a start, because touching calls do not overlap.
      `ORDER BY t, delta` does it, since `-1` sorts before `1`.
    * `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` adds one event at a time. Without it, the default frame
      treats rows with the same `t` and `delta` as one step. Here that happens to give the same peak, but writing the
      frame out makes the query say what it means.
    * The date of a timestamp: `CAST(t AS DATE)` in PostgreSQL; `date(t)` in SQLite.
    * A self join ("for each call, count the calls running at its start") is also correct, but it compares every pair
      of calls on a day, which is slow on large tables.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: one ends exactly when the next starts;
    * edge case: three start at the same second;
    * edge case: no calls;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 100,000 rows: PostgreSQL 16 0.17 s, SQLite 3.53 0.36 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: starts counted before ends at the same moment"
    
        PostgreSQL:
        
        ```sql
        WITH ev AS (SELECT started AS t, 1 AS delta FROM calls UNION ALL SELECT ended, -1 FROM calls),
        running AS (SELECT CAST(t AS DATE) AS call_day,
               SUM(delta) OVER (PARTITION BY CAST(t AS DATE) ORDER BY t, delta DESC
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS in_progress FROM ev)
        SELECT call_day, MAX(in_progress) AS peak FROM running GROUP BY call_day ORDER BY call_day;
        ```
        
        SQLite:
        
        ```sql
        WITH ev AS (SELECT started AS t, 1 AS delta FROM calls UNION ALL SELECT ended, -1 FROM calls),
        running AS (SELECT date(t) AS call_day,
               SUM(delta) OVER (PARTITION BY date(t) ORDER BY t, delta DESC
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS in_progress FROM ev)
        SELECT call_day, MAX(in_progress) AS peak FROM running GROUP BY call_day ORDER BY call_day;
        ```
        
        Checked: this gives a wrong result on **edge: one ends exactly when the next starts**.
    
    ??? failure "A common wrong answer: a self join that counts touching calls"
    
        PostgreSQL:
        
        ```sql
        SELECT CAST(a.started AS DATE) AS call_day, MAX(n) AS peak FROM (
          SELECT a.id, a.started, COUNT(*) AS n FROM calls a
          JOIN calls b ON b.started <= a.started AND b.ended >= a.started
          GROUP BY a.id, a.started) a
        GROUP BY CAST(a.started AS DATE) ORDER BY call_day;
        ```
        
        SQLite:
        
        ```sql
        SELECT date(a.started) AS call_day, MAX(n) AS peak FROM (
          SELECT a.id, a.started, COUNT(*) AS n FROM calls a
          JOIN calls b ON b.started <= a.started AND b.ended >= a.started
          GROUP BY a.id, a.started) a
        GROUP BY date(a.started) ORDER BY call_day;
        ```
        
        Checked: this gives a wrong result on **edge: one ends exactly when the next starts**.



---

### Task&nbsp;3: Rate limiter

**Level:** Medium · **Aim for:** 30 minutes

An API accepts at most `K` requests from each user in any window of `W` seconds. `R` lists the requests as
`(user, t)` tuples in time order (`t` never decreases; several requests can share a second). A request at time
`t` is **accepted** if that user has fewer than `K` **accepted** requests with time in `(t − W, t]`, that is,
later than `t − W` and up to `t`. Otherwise it is **rejected**, and a rejected request does not count against
later ones. Return the number of rejected requests.

**Examples**

* `solution([(1, 0), (1, 1), (1, 2), (2, 2), (1, 10)], 2, 10)` returns `1`
* `solution([(7, 5), (7, 5), (7, 5)], 1, 1)` returns `2`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `R`, is an integer within the range [0..200,000];
* users are integers within the range [1..1,000,000];
* times are integers within the range [0..1,000,000,000];
* `K` and `W` are integers within the range [1..1,000,000].

Start from:

```python
def solution(R, K, W):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import defaultdict, deque
    
    def solution(R, K, W):
        accepted = defaultdict(deque)       # user -> times of their accepted requests, oldest first
        rejected = 0
        for user, t in R:
            q = accepted[user]
            while q and q[0] <= t - W:      # older than the window: forget it
                q.popleft()
            if len(q) < K:
                q.append(t)
            else:
                rejected += 1
        return rejected
    ```
    
    **Why it works**
    
    * **A sliding window per user.** Keep each user's accepted times in a `deque`. Because time never goes back,
      times that fall out of the window are always at the front: `popleft()` them, then the length of the deque is
      the number of accepted requests in the window. Each request enters and leaves once: O(N) time.
    * Read the boundary: the window is `(t − W, t]`, so a request exactly `W` seconds old no longer counts (`<=` in
      the `while`). The second edge case checks it.
    * Only **accepted** requests go into the deque. Counting rejected ones too is a different (stricter) limiter, and
      the third edge case tells them apart.
    * A `list` with `pop(0)` would also work but each `pop(0)` moves every element; `deque.popleft()` is O(1).
    * Rate limiters, deduplication windows and "events in the last N minutes" are everyday data engineering
      problems; this is the standard way to do them in one pass.
    
    **Cost:** O(N) time, O(N) memory in the worst case.
    
    **The slow answer:** Scanning all earlier accepted requests for every request: O(N²).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no requests: `solution([], 3, 10)` returns `0`;
    * edge case, the window drops a request at exactly t - W: `solution([(1, 0), (1, 10)], 1, 10)` returns `0`;
    * edge case, rejected requests do not count: `solution([(1, 0), (1, 1), (1, 2), (1, 9)], 1, 9)` returns `2`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.035s.
    
    ??? failure "A common wrong answer: rejected requests counted in the window"
    
        ```python
        from collections import defaultdict, deque
        
        def solution(R, K, W):
            seen = defaultdict(deque)
            rejected = 0
            for user, t in R:
                q = seen[user]
                while q and q[0] <= t - W:
                    q.popleft()
                if len(q) >= K:
                    rejected += 1
                q.append(t)
            return rejected
        ```
        
        Checked: example: got 2 want 1.
    
    ??? failure "A common wrong answer: < instead of <= keeps a request that is exactly W old"
    
        ```python
        from collections import defaultdict, deque
        
        def solution(R, K, W):
            accepted = defaultdict(deque)
            rejected = 0
            for user, t in R:
                q = accepted[user]
                while q and q[0] < t - W:
                    q.popleft()
                if len(q) < K:
                    q.append(t)
                else:
                    rejected += 1
            return rejected
        ```
        
        Checked: example: got 2 want 1.
    
    ??? failure "A common wrong answer: scanning all accepted requests every time (too slow)"
    
        ```python
        def solution(R, K, W):
            acc = []
            rejected = 0
            for user, t in R:
                n = sum(1 for u, s in acc if u == user and t - W < s <= t)
                if n < K:
                    acc.append((user, t))
                else:
                    rejected += 1
            return rejected
        ```
        
        Checked: timed out after 5.0s on the large input.



---

## After the mock

Task 1 hides the trap from mistake 2 in a new place, task 2 is the sweep line from Mock 1 written in SQL, and
task 3 is a sliding window. If one of them cost you more than its time, redo the matching group of the
[SQL practice set](sql-practice.md) or the [Python practice set](python-practice.md), then try
[Mock test 4](mock-test-4.md) on another day.
