# Full mock C: 3 tasks in 150 minutes

The last full rehearsal, for Monday 16 November, best in the morning. This one has one SQL task and two Python tasks, in case your test's mix is different from 2 SQL + 1 Python. It has the format of your test: **three tasks, 150 minutes, in one sitting, no pause.**
**Set a timer for 150 minutes** and do not open a solution until the timer ends.

| Task | Type | Level | Aim for |
|---|---|---|---|
| 1 | SQL | Medium | 35 minutes |
| 2 | Python | Medium | 30 minutes |
| 3 | Python | Hard | 45 minutes |

Every SQL task here was tested on **PostgreSQL only** (`sql-postgres` in the test's language menu). The Python
tasks use the standard library only.

**How to take it.** Read all three tasks first (10 minutes) and start with the one you see the clearest path
for. Write each answer in a plain text editor or on paper, the way you would type it into Codility's editor.
When the timer ends, paste each answer into its **Try it here** box: Run checks it on the example, **Check** also
on the edge cases from the solution. Then open the solutions, including the wrong answers, and write down every
mistake you made.

Before you open a solution, write down the edge cases you thought of. Then compare with the list in the solution.

---

### Task&nbsp;1: Ledger and bank do not agree

**Level:** Medium · **Aim for:** 35 minutes

A finance team keeps its own `ledger` of money in and out of each account (`amount` is negative for money out), and
receives the bank's statement as `bank`. Each day, the totals should agree.

Write an SQL query (PostgreSQL) that compares, for every **account and day that appears in either table**, the sum
of `ledger.amount` (by `posted_on`) with the sum of `bank.amount` (by `booked_on`). A side with no rows for that
account and day counts as 0. Return only the account-days where the two totals **differ**:

* `account`, `day`;
* `ledger_total`, `bank_total`;
* `difference`: `ledger_total - bank_total`.

Sort by `account`, then `day`. (An account-day whose totals are equal is not returned, even if one side has no
rows: for example two ledger rows of +5 and −5 and nothing in the bank.)

**Tables**

```sql
CREATE TABLE ledger (
    id        INTEGER PRIMARY KEY,
    account   VARCHAR(10) NOT NULL,
    posted_on DATE NOT NULL,
    amount    INTEGER NOT NULL
);
CREATE TABLE bank (
    id        INTEGER PRIMARY KEY,
    account   VARCHAR(10) NOT NULL,
    booked_on DATE NOT NULL,
    amount    INTEGER NOT NULL
);
```

**Example data**

`ledger`

| id | account | posted_on | amount |
|---|---|---|---|
| 1 | A1 | 2026-06-01 | 100 |
| 2 | A1 | 2026-06-01 | -40 |
| 3 | A1 | 2026-06-02 | 25 |
| 4 | B2 | 2026-06-01 | 70 |
| 5 | B2 | 2026-06-03 | 5 |
| 6 | B2 | 2026-06-03 | -5 |

`bank`

| id | account | booked_on | amount |
|---|---|---|---|
| 1 | A1 | 2026-06-01 | 60 |
| 2 | A1 | 2026-06-02 | 20 |
| 3 | B2 | 2026-06-01 | 30 |
| 4 | B2 | 2026-06-01 | 40 |
| 5 | B2 | 2026-06-02 | 15 |
| 6 | C3 | 2026-06-01 | -10 |

**Your query should return**

| account | day | ledger_total | bank_total | difference |
|---|---|---|---|---|
| A1 | 2026-06-02 | 25 | 20 | 5 |
| B2 | 2026-06-02 | 0 | 15 | -15 |
| C3 | 2026-06-01 | 0 | -10 | 10 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**
    
    ```sql
    WITH l AS (                      -- 1. one row per account and day on each side
        SELECT account, posted_on AS day, SUM(amount) AS total
        FROM ledger
        GROUP BY account, posted_on
    ),
    b AS (
        SELECT account, booked_on AS day, SUM(amount) AS total
        FROM bank
        GROUP BY account, booked_on
    )
    SELECT COALESCE(l.account, b.account) AS account,       -- 2. FULL JOIN keeps days found on one side only
           COALESCE(l.day, b.day)         AS day,
           COALESCE(l.total, 0)           AS ledger_total,
           COALESCE(b.total, 0)           AS bank_total,
           COALESCE(l.total, 0) - COALESCE(b.total, 0) AS difference
    FROM l
    FULL OUTER JOIN b ON b.account = l.account AND b.day = l.day
    WHERE COALESCE(l.total, 0) <> COALESCE(b.total, 0)
    ORDER BY account, day;
    ```
    
    **Why it works**
    
    * **Aggregate each side first** to one row per account and day. Joining the raw rows would pair every ledger row
      with every bank row of the same day (2 × 2 = 4 rows for A1 on 1 June) and multiply both totals.
    * **`FULL OUTER JOIN`** keeps account-days that appear on only one side: B2 on 2 June is only in the bank, A1 on 2
      June is in both, C3 is only in the bank. A `LEFT JOIN` from the ledger would lose the bank-only days.
    * After a full join, either side can be `NULL`, so take the key from whichever side has it
      (`COALESCE(l.account, b.account)`) and turn a missing total into 0.
    * Compare the **COALESCEd** totals in `WHERE`. `l.total <> b.total` is not true when one side is `NULL`, so the
      one-sided days would silently disappear.
    * B2 on 3 June has +5 and −5 in the ledger and nothing in the bank: both totals are 0, so it is not returned.
    * In the result, `ORDER BY account, day` uses the output names; in PostgreSQL an `ORDER BY` can name a `SELECT`
      alias.
    
    **Tested on PostgreSQL 16.** Every case below gave exactly the expected rows, columns and order:
    
    * the example above;
    * edge case: bank rows only;
    * edge case: ledger rows only;
    * edge case: same account, different days on each side;
    * edge case: everything agrees;
    * edge case: two rows each side, totals differ;
    * edge case: both empty;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.21 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: LEFT JOIN from the ledger loses bank-only days"
    
        ```sql
        WITH l AS (SELECT account, posted_on AS day, SUM(amount) AS total FROM ledger GROUP BY 1, 2),
        b AS (SELECT account, booked_on AS day, SUM(amount) AS total FROM bank GROUP BY 1, 2)
        SELECT l.account, l.day, l.total AS ledger_total, COALESCE(b.total, 0) AS bank_total,
               l.total - COALESCE(b.total, 0) AS difference
        FROM l LEFT JOIN b ON b.account = l.account AND b.day = l.day
        WHERE l.total <> COALESCE(b.total, 0) ORDER BY account, day;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.
    
    ??? failure "A common wrong answer: join the raw rows, then sum (fan-out)"
    
        ```sql
        SELECT l.account, l.posted_on AS day, SUM(l.amount) AS ledger_total, SUM(b.amount) AS bank_total,
               SUM(l.amount) - SUM(b.amount) AS difference
        FROM ledger l JOIN bank b ON b.account = l.account AND b.booked_on = l.posted_on
        GROUP BY l.account, l.posted_on HAVING SUM(l.amount) <> SUM(b.amount) ORDER BY account, day;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.
    
    ??? failure "A common wrong answer: <> on the raw totals drops one-sided days"
    
        ```sql
        WITH l AS (SELECT account, posted_on AS day, SUM(amount) AS total FROM ledger GROUP BY 1, 2),
        b AS (SELECT account, booked_on AS day, SUM(amount) AS total FROM bank GROUP BY 1, 2)
        SELECT COALESCE(l.account, b.account) AS account, COALESCE(l.day, b.day) AS day,
               COALESCE(l.total, 0) AS ledger_total, COALESCE(b.total, 0) AS bank_total,
               COALESCE(l.total, 0) - COALESCE(b.total, 0) AS difference
        FROM l FULL OUTER JOIN b ON b.account = l.account AND b.day = l.day
        WHERE l.total <> b.total ORDER BY account, day;
        ```
        
        Checked on PostgreSQL 16: this fails on **sample**.



---

### Task&nbsp;2: Days until a higher price

**Level:** Medium · **Aim for:** 30 minutes

`P[i]` is the closing price of a share on day `i`. For every day, find how many days you have to wait until a
**strictly higher** closing price. If no later day has a higher price, the answer for that day is `0`.

Return the answers as a list of the same length as `P`.

**Examples**

* `solution([30, 38, 32, 31, 35, 40, 36])` returns `[1, 4, 2, 1, 1, 0, 0]`
* `solution([5, 4, 3])` returns `[0, 0, 0]`
* `solution([])` returns `[]`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `P`, is an integer within the range [0..100,000];
* each `P[i]` is an integer within the range [1..1,000,000,000].

Start from:

```python
def solution(P):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(P):
        answer = [0] * len(P)
        waiting = []                         # days still waiting for a higher price; their prices never rise
        for day, price in enumerate(P):
            while waiting and P[waiting[-1]] < price:
                d = waiting.pop()            # today is the first higher price for day d
                answer[d] = day - d
            waiting.append(day)
        return answer                        # days left in the stack never found one: their answer stays 0
    ```
    
    **Why it works**
    
    * The plain answer looks forward from every day. On a falling price (each day lower than the day before) every day
      looks all the way to the end: about `N²/2` = 5 billion steps for 100,000 days.
    * The **monotonic stack** answers each day exactly once. The stack holds the days that have not yet seen a higher
      price; their prices go down (or stay equal) from the bottom of the stack to the top, because a higher price would
      already have removed the days below it.
    * Each new price pops every waiting day that is lower: today is their answer. Each day is pushed once and popped
      at most once, so the whole loop is `O(N)` even though it has a `while` inside a `for`.
    * `<`, not `<=`: an equal price is not higher, so a day with the same price stays waiting (edge case "an equal
      price is not higher").
    * The same pattern answers "next greater element", "how many days since a higher price" (walk the other way), and
      the largest rectangle under a bar chart.
    
    **Cost:** O(N) time, O(N) memory: each day is pushed and popped at most once.
    
    **The slow answer:** Looking forward from every day: O(N²), about 5 billion steps on a falling price.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, an equal price is not higher: `solution([7, 7, 8])` returns `[2, 1, 0]`;
    * edge case, rising every day: `solution([1, 2, 3, 4])` returns `[1, 1, 1, 0]`;
    * edge case, one day: `solution([10])` returns `[0]`;
    * edge case, a dip and a recovery: `solution([9, 1, 2, 3, 10])` returns `[4, 1, 1, 1, 0]`;
    * 800 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.007s.
    
    ??? failure "A common wrong answer: popping on an equal price too (<= instead of <)"
    
        ```python
        def solution(P):
            answer = [0] * len(P)
            waiting = []
            for day, price in enumerate(P):
                while waiting and P[waiting[-1]] <= price:
                    d = waiting.pop()
                    answer[d] = day - d
                waiting.append(day)
            return answer
        ```
        
        Checked: edge: an equal price is not higher: got [1, 1, 0] want [2, 1, 0].
    
    ??? failure "A common wrong answer: returning the higher price instead of the number of days"
    
        ```python
        def solution(P):
            answer = [0] * len(P)
            waiting = []
            for day, price in enumerate(P):
                while waiting and P[waiting[-1]] < price:
                    d = waiting.pop()
                    answer[d] = price
                waiting.append(day)
            return answer
        ```
        
        Checked: example: got [38, 40, 35, 35, 40, 0, 0] want [1, 4, 2, 1, 1, 0, 0].
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(P):
            answer = []
            for i in range(len(P)):
                wait = 0
                for j in range(i + 1, len(P)):
                    if P[j] > P[i]:
                        wait = j - i
                        break
                answer.append(wait)
            return answer
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.007s).



---

### Task&nbsp;3: When does the pipeline finish?

**Level:** Hard · **Aim for:** 45 minutes

A data pipeline has `N` jobs, numbered from `0` to `N - 1`. Job `i` takes `D[i]` minutes. There are `M`
dependencies: for each `k`, job `B[k]` can start only after job `A[k]` has finished. A job starts as soon as all
the jobs it depends on have finished, and any number of jobs can run at the same time. The pipeline starts at
minute `0`.

Return the minute at which the last job finishes. If the dependencies contain a **cycle** (some job would have to
wait for itself, directly or through other jobs), the pipeline can never finish: return `-1`.

**Examples**

* `solution([3, 2, 4, 1], [0, 0, 1, 2], [1, 2, 3, 3])` returns `8`
* `solution([5, 1, 1], [], [])` returns `5`
* `solution([1, 1, 1], [0, 1, 2], [1, 2, 0])` returns `-1`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `D`, is an integer within the range [1..100,000];
* `M`, the length of `A` and `B`, is an integer within the range [0..200,000];
* each `D[i]` is an integer within the range [0..10,000];
* each `A[k]` and `B[k]` is an integer within the range [0..N - 1];
* the same dependency may be listed more than once.

Start from:

```python
def solution(D, A, B):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import deque
    
    def solution(D, A, B):
        n = len(D)
        after = [[] for _ in range(n)]       # after[a]: the jobs that wait for a
        waits_for = [0] * n                  # how many unfinished jobs each job still waits for
        for a, b in zip(A, B):
            after[a].append(b)
            waits_for[b] += 1
        start = [0] * n                      # earliest start of each job
        ready = deque(i for i in range(n) if waits_for[i] == 0)
        done = 0
        last = 0
        while ready:
            j = ready.popleft()
            done += 1
            finish = start[j] + D[j]
            last = max(last, finish)
            for k in after[j]:
                start[k] = max(start[k], finish)    # k waits for the slowest job it depends on
                waits_for[k] -= 1
                if waits_for[k] == 0:
                    ready.append(k)
        return last if done == n else -1     # jobs never ready are stuck in (or behind) a cycle
    ```
    
    **Why it works**
    
    * This is **topological order** (Kahn's algorithm): keep a count of what each job still waits for, start with the
      jobs that wait for nothing, and each time a job finishes, lower the count of the jobs after it. A job whose count
      reaches 0 is ready.
    * Each job's start is the **latest** finish among the jobs it waits for (`max`, not the sum): the jobs before it
      run at the same time. This is the "critical path" of the pipeline.
    * A cycle shows itself without any extra search: the jobs in it never reach a count of 0, so fewer than `N` jobs
      are ever done. Jobs that wait for a cycle are stuck too; either way the answer is `-1`.
    * A repeated dependency is counted twice in `waits_for` and lowered twice, so it does no harm.
    * Recursion (a depth-first search that asks "when does each job I wait for finish?") is the other common answer.
      It is correct, but a chain of 100,000 jobs goes 100,000 calls deep and Python stops at about 1,000
      (`RecursionError`). In a Codility test, prefer the loop with a queue.
    * Each job and each dependency is handled once: `O(N + M)`.
    
    **Cost:** O(N + M) time and memory.
    
    **The slow answer:** A recursive search is O(N + M) too, but a chain of 100,000 jobs is 100,000 calls deep: RecursionError.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, a job that depends on itself: `solution([4, 4], [1], [1])` returns `-1`;
    * edge case, the same dependency twice: `solution([2, 3], [0, 0], [1, 1])` returns `5`;
    * edge case, jobs that take 0 minutes: `solution([0, 0, 0], [0, 1], [1, 2])` returns `0`;
    * edge case, a cycle away from the long path: `solution([100, 1, 1], [1, 2], [2, 1])` returns `-1`;
    * edge case, one job: `solution([7], [], [])` returns `7`;
    * edge case, dependencies listed in no particular order: `solution([1, 10, 1], [2, 1], [1, 0])` returns `12`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.182s.
    
    ??? failure "A common wrong answer: adding up every duration, as if the jobs ran one after another"
    
        ```python
        def solution(D, A, B):
            return sum(D)
        ```
        
        Checked: example: got 10 want 8.
    
    ??? failure "A common wrong answer: ignoring cycles"
    
        ```python
        from collections import deque
        
        def solution(D, A, B):
            n = len(D)
            after = [[] for _ in range(n)]
            waits_for = [0] * n
            for a, b in zip(A, B):
                after[a].append(b)
                waits_for[b] += 1
            start = [0] * n
            ready = deque(i for i in range(n) if waits_for[i] == 0)
            last = 0
            while ready:
                j = ready.popleft()
                finish = start[j] + D[j]
                last = max(last, finish)
                for k in after[j]:
                    start[k] = max(start[k], finish)
                    waits_for[k] -= 1
                    if waits_for[k] == 0:
                        ready.append(k)
            return last
        ```
        
        Checked: example: got 0 want -1.
    
    ??? failure "A common wrong answer: recursion: right on small inputs, fails on a long chain"
    
        ```python
        def solution(D, A, B):
            n = len(D)
            before = [[] for _ in range(n)]
            for a, b in zip(A, B):
                before[b].append(a)
            finish = [None] * n
            state = [0] * n                      # 0 new, 1 being computed, 2 done
        
            def end(j):
                if state[j] == 1:
                    raise ValueError("cycle")
                if state[j] == 0:
                    state[j] = 1
                    finish[j] = D[j] + max((end(a) for a in before[j]), default=0)
                    state[j] = 2
                return finish[j]
        
            try:
                return max(end(j) for j in range(n))
            except ValueError:
                return -1
        ```
        
        Checked: RecursionError on the large input.



---

## After the mock

This was the last rehearsal: no new material after it. Go through your mistakes list from all three full
mocks once, then the [cheat sheet](cheat-sheet.md), then stop early and sleep well. On Tuesday, ten minutes on the
cheat sheet and one easy task you have solved before is all the warm-up you need.
