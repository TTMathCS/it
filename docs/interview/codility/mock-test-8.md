# Mock test 8

A full-length rehearsal: two SQL tasks for PostgreSQL and one Python task, **150 minutes** in all, like the real
test. **Set a timer for 150 minutes.**

| Task | Type | Level | Aim for |
|---|---|---|---|
| 1 | SQL | Medium | 35 minutes |
| 2 | SQL | Hard | 50 minutes |
| 3 | Python | Hard | 50 minutes |

That leaves 15 minutes to go back over the edge cases of all three. Before you open a solution, write down the edge
cases you tested, then compare with the list in the solution.

---

### Task&nbsp;1: Double-booked rooms

**Level:** Medium · **Aim for:** 35 minutes

Each row of `bookings` holds one meeting room from `starts_at` up to `ends_at` (`ends_at` is always later than
`starts_at`). Two bookings of the same room **clash** when they share some time. A booking that ends at 10:00 and
one that starts at 10:00 do not clash. Write an SQL query that returns every clashing pair once: `room`,
`first_id`, `second_id`, with `first_id` the smaller id. Sort by `room`, then `first_id`, then `second_id`.

**Tables**

```sql
CREATE TABLE bookings (
    id        INTEGER PRIMARY KEY,
    room      VARCHAR(20) NOT NULL,
    starts_at TIMESTAMP NOT NULL,
    ends_at   TIMESTAMP NOT NULL
);
```

**Example data**

`bookings`

| id | room | starts_at | ends_at |
|---|---|---|---|
| 1 | blue | 2026-03-02 09:30 | 2026-03-02 09:45 |
| 2 | blue | 2026-03-02 10:00 | 2026-03-02 11:00 |
| 3 | blue | 2026-03-02 09:00 | 2026-03-02 10:00 |
| 4 | blue | 2026-03-02 10:30 | 2026-03-02 12:00 |
| 5 | green | 2026-03-02 09:00 | 2026-03-02 17:00 |
| 6 | green | 2026-03-03 09:00 | 2026-03-03 10:00 |
| 7 | red | 2026-03-02 13:00 | 2026-03-02 14:00 |
| 8 | green | 2026-03-02 16:59 | 2026-03-02 18:00 |

**Your query should return**

| room | first_id | second_id |
|---|---|---|
| blue | 1 | 3 |
| blue | 2 | 4 |
| green | 5 | 8 |

??? success "Solution and explanation (open after you try)"

    ```sql
    SELECT a.room, a.id AS first_id, b.id AS second_id
    FROM bookings a
    JOIN bookings b
      ON b.room = a.room
     AND a.id < b.id
     AND a.starts_at < b.ends_at
     AND b.starts_at < a.ends_at
    ORDER BY a.room, first_id, second_id;
    ```

    **Why it works**

    * **Join the table to itself.** Each row of the join is one pair of bookings of the same room.
    * **`a.id < b.id`** keeps each pair once, the right way round, and never pairs a booking with itself. With
      `<>` every pair shows up twice.
    * **The overlap test is two comparisons.** Two stretches of time share some time exactly when each one starts
      before the other ends. That one rule covers every shape: partly overlapping, one inside the other, the same
      times twice. Trying to list the shapes one by one ("b starts inside a") misses the case where `b` starts
      first and contains `a`, here bookings 1 and 3.
    * **Strict `<`, not `<=`**, because a booking ending at 10:00 and one starting at 10:00 do not clash (bookings
      3 and 2).
    * Bookings 5 and 8 clash by one minute; booking 6 is on another day.

    **Tested.** On PostgreSQL 16 the example gave exactly the expected rows, columns and order. On SQLite 3.54 every case below gave the expected rows:

    * the example above;
    * edge cases: one booking, empty table, the same times twice, one booking inside another, the same times in
      two different rooms;
    * 300 random small tables, each compared with a separate Python answer;
    * a large table of 20,000 rows: 0.57 s. The join is O(n²) per room in the worst case; an index on
      `(room, starts_at)` helps on a real table.

    ??? failure "A common wrong answer: touching bookings counted as a clash"

        ```sql
        SELECT a.room, a.id AS first_id, b.id AS second_id FROM bookings a JOIN bookings b
          ON b.room = a.room AND a.id < b.id AND a.starts_at <= b.ends_at AND b.starts_at <= a.ends_at
        ORDER BY a.room, first_id, second_id;
        ```

        Checked: wrong on the example (it adds blue 2, 3).

    ??? failure "A common wrong answer: only checks that the second booking starts inside the first"

        ```sql
        SELECT a.room, a.id AS first_id, b.id AS second_id FROM bookings a JOIN bookings b
          ON b.room = a.room AND a.id < b.id AND b.starts_at >= a.starts_at AND b.starts_at < a.ends_at
        ORDER BY a.room, first_id, second_id;
        ```

        Checked: wrong on the example (it misses blue 1, 3).

    ??? failure "A common wrong answer: <> instead of <"

        ```sql
        SELECT a.room, a.id AS first_id, b.id AS second_id FROM bookings a JOIN bookings b
          ON b.room = a.room AND a.id <> b.id AND a.starts_at < b.ends_at AND b.starts_at < a.ends_at
        ORDER BY a.room, first_id, second_id;
        ```

        Checked: wrong on the example (every pair twice).

---

### Task&nbsp;2: Fill in the missing readings

**Level:** Hard · **Aim for:** 50 minutes

Each row of `readings` is one reading of a sensor at time `ts`. When the sensor failed, `value` is `NULL`. Write an
SQL query that returns every row with the gaps filled: `sensor`, `ts`, and `value`, where a `NULL` is replaced by
the **last non-NULL value of the same sensor** before it. If a sensor has no value yet, keep `NULL`. Note that `0`
is a real value. Sort by `sensor`, then `ts`.

**Tables**

```sql
CREATE TABLE readings (
    sensor VARCHAR(20) NOT NULL,
    ts     TIMESTAMP NOT NULL,
    value  INTEGER,
    PRIMARY KEY (sensor, ts)
);
```

**Example data**

`readings`

| sensor | ts | value |
|---|---|---|
| a | 2026-05-01 08:00:00 | 10 |
| a | 2026-05-01 08:05:00 | NULL |
| a | 2026-05-01 08:10:00 | NULL |
| a | 2026-05-01 08:15:00 | 7 |
| a | 2026-05-01 08:20:00 | NULL |
| b | 2026-05-01 08:00:00 | NULL |
| b | 2026-05-01 08:05:00 | 3 |
| b | 2026-05-01 08:10:00 | 0 |
| b | 2026-05-01 08:15:00 | NULL |

**Your query should return**

| sensor | ts | value |
|---|---|---|
| a | 2026-05-01 08:00:00 | 10 |
| a | 2026-05-01 08:05:00 | 10 |
| a | 2026-05-01 08:10:00 | 10 |
| a | 2026-05-01 08:15:00 | 7 |
| a | 2026-05-01 08:20:00 | 7 |
| b | 2026-05-01 08:00:00 | NULL |
| b | 2026-05-01 08:05:00 | 3 |
| b | 2026-05-01 08:10:00 | 0 |
| b | 2026-05-01 08:15:00 | 0 |

??? success "Solution and explanation (open after you try)"

    ```sql
    WITH g AS (
        SELECT sensor, ts, value,
               COUNT(value) OVER (PARTITION BY sensor ORDER BY ts) AS grp
        FROM readings
    )
    SELECT sensor, ts,
           MAX(value) OVER (PARTITION BY sensor, grp) AS value
    FROM g
    ORDER BY sensor, ts;
    ```

    **Why it works**

    * Some databases have `LAST_VALUE(value IGNORE NULLS)`; **PostgreSQL 16 does not**, so you need a trick.
    * **`COUNT(value)` counts only non-NULL values.** As a running count it goes up by one at every real reading
      and stays put on every `NULL`. So a real reading and the `NULL`s after it share one number, `grp`: sensor
      `a` gets 1, 1, 1, 2, 2.
    * Each group holds exactly one non-NULL value (or none, for the `NULL`s before a sensor's first reading,
      where `grp` is 0). `MAX(value)` over the group picks that one value and spreads it to the whole group;
      `MAX` ignores `NULL`s, and a group of only `NULL`s stays `NULL`.
    * **`PARTITION BY sensor` in both windows**, or sensor `b`'s first row would take `a`'s last value.
    * `ORDER BY ts` in a window uses the frame "from the start up to this row's `ts`". That is safe here because
      `(sensor, ts)` is the primary key, so no two rows of one sensor share a `ts`.
    * `LAG(value)` only looks one row back, so two `NULL`s in a row break it. A running `MAX` is wrong as soon as a
      value goes down (7 after 10).

    **Tested.** On PostgreSQL 16 the example gave exactly the expected rows, columns and order. On SQLite 3.54 every case below gave the expected rows:

    * the example above;
    * edge cases: all `NULL`, empty table, `0` followed by `NULL`, `NULL` before the first value;
    * 300 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: 0.62 s.

    ??? failure "A common wrong answer: LAG looks only one row back"

        ```sql
        SELECT sensor, ts, COALESCE(value, LAG(value) OVER (PARTITION BY sensor ORDER BY ts)) AS value
        FROM readings ORDER BY sensor, ts;
        ```

        Checked: wrong on the example (`a` at 08:10 stays `NULL`).

    ??? failure "A common wrong answer: COUNT(*) instead of COUNT(value)"

        ```sql
        WITH g AS (SELECT sensor, ts, value, COUNT(*) OVER (PARTITION BY sensor ORDER BY ts) AS grp FROM readings)
        SELECT sensor, ts, MAX(value) OVER (PARTITION BY sensor, grp) AS value FROM g ORDER BY sensor, ts;
        ```

        Checked: wrong on the example (every row is its own group, nothing is filled).

    ??? failure "A common wrong answer: groups not split by sensor"

        ```sql
        WITH g AS (SELECT sensor, ts, value, COUNT(value) OVER (ORDER BY sensor, ts) AS grp FROM readings)
        SELECT sensor, ts, MAX(value) OVER (PARTITION BY grp) AS value FROM g ORDER BY sensor, ts;
        ```

        Checked: wrong on the example (`b` at 08:00 gets 7 from sensor `a`).

    ??? failure "A common wrong answer: a running MAX"

        ```sql
        SELECT sensor, ts, MAX(value) OVER (PARTITION BY sensor ORDER BY ts) AS value
        FROM readings ORDER BY sensor, ts;
        ```

        Checked: wrong on the example (`a` keeps 10 after the 7).

---

### Task&nbsp;3: Worker pool

**Level:** Hard · **Aim for:** 50 minutes

A pipeline has `N` workers, numbered 0 to `N − 1`. `jobs` is a list of `(arrival, duration)` pairs, in order of
arrival (arrival times never go down; two jobs may arrive at the same time). Jobs are handed out in list order:

* if some workers are idle when a job arrives, it goes to the idle worker with the **smallest number**;
* if none is idle, the job waits and goes to the first worker to finish (if several finish at the same moment,
  the smallest number). A waiting job is always served before any job after it in the list.

A worker that finishes at time `t` is idle for a job arriving at `t`. Return, for each job in order, the pair
`(worker, finish time)`.

**Examples**

* `solution(2, [(0, 5), (1, 3), (2, 4), (4, 1), (9, 2)])` returns `[(0, 5), (1, 4), (1, 8), (0, 6), (0, 11)]`
* `solution(1, [(3, 2), (3, 2), (3, 2)])` returns `[(0, 5), (0, 7), (0, 9)]`

**Write an efficient algorithm for the following assumptions:**

* `N` and `M`, the number of jobs, are integers within the range [1..100,000];
* arrival times are integers within the range [0..1,000,000,000]; durations within [1..10,000].

Start from:

```python
def solution(N, jobs):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    import heapq

    def solution(N, jobs):
        free = list(range(N))              # idle workers, smallest number on top
        busy = []                          # (time it is free again, worker)
        out = []
        for a, d in jobs:
            while busy and busy[0][0] <= a:            # everyone done by now is idle again
                heapq.heappush(free, heapq.heappop(busy)[1])
            if free:
                w, start = heapq.heappop(free), a
            else:
                start, w = heapq.heappop(busy)         # wait for the first one to finish
            heapq.heappush(busy, (start + d, w))
            out.append((w, start + d))
        return out
    ```

    **Why it works**

    * **Two heaps, two questions.** "Which idle worker has the smallest number?" is the top of `free`. "Who
      finishes first?" is the top of `busy`, ordered by `(finish time, number)`, so a tie on time gives the
      smallest number for free. (`list(range(N))` is already a valid heap: it is sorted.)
    * **Move the finished workers first.** Before handing out a job, every worker whose finish time is `<=` the
      arrival goes back to `free`. Only then is "the smallest idle number" right. Taking the top of `busy`
      straight away gives the worker that finished first, which is a different worker (3 workers, jobs
      `[(2, 1), (5, 2)]`: worker 0 is idle again at 5, so it gets the second job, not worker 1).
    * **A waiting job starts when its worker finishes**, not when it arrived: in the first example the third job
      arrives at 2 but starts at 4 and finishes at 8.
    * Jobs are handled in list order, so a job that waited has already taken its worker before the next job is
      looked at: that is the "served first" rule, with no queue needed.
    * Each job pushes and pops each heap a few times; each worker moves from `busy` to `free` at most once per job.

    **Cost:** O(N + M log N) time, O(N + M) memory.

    **The slow answer:** for every job, scan all `N` workers for the idle one with the smallest number: O(N·M),
    10 billion steps at the limits.

    **Tested** (Python 3.9.6, standard library only):

    * the examples above;
    * edge case, no jobs: `solution(3, [])` returns `[]`;
    * edge case, a worker that finishes at the arrival time is idle: `solution(3, [(0, 2), (2, 1)])` returns `[(0, 2), (0, 3)]`;
    * edge case, smallest idle number, not the first one freed: `solution(3, [(2, 1), (5, 2)])` returns `[(0, 3), (0, 7)]`;
    * edge case, more workers than jobs: `solution(5, [(7, 1)])` returns `[(0, 8)]`;
    * edge case, two workers finish together: `solution(3, [(0, 4), (0, 4), (0, 1), (2, 9), (4, 1), (4, 1)])` returns `[(0, 4), (1, 4), (2, 1), (2, 11), (0, 5), (1, 5)]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest inputs the limits allow (100,000 jobs): 0.119 s with N = 100,000, 0.028 s with N = 1, 0.054 s
      with N = 1,000 and all jobs arriving at once.

    ??? failure "A common wrong answer: the first worker to finish instead of the smallest idle number"

        ```python
        def solution(N, jobs):
            busy = [(0, w) for w in range(N)]
            out = []
            for a, d in jobs:
                t, w = heapq.heappop(busy)
                start = max(a, t)
                heapq.heappush(busy, (start + d, w))
                out.append((w, start + d))
            return out
        ```

        Checked: edge, a worker that finishes at the arrival time is idle: got [(0, 2), (1, 3)] want [(0, 2), (0, 3)].

    ??? failure "A common wrong answer: a waiting job starts at its arrival"

        ```python
        def solution(N, jobs):
            free, busy, out = list(range(N)), [], []
            for a, d in jobs:
                while busy and busy[0][0] <= a:
                    heapq.heappush(free, heapq.heappop(busy)[1])
                w = heapq.heappop(free) if free else heapq.heappop(busy)[1]
                heapq.heappush(busy, (a + d, w))
                out.append((w, a + d))
            return out
        ```

        Checked: example: got [(0, 5), (1, 4), (1, 6), (0, 5), (0, 11)] want [(0, 5), (1, 4), (1, 8), (0, 6), (0, 11)].

    ??? failure "A common wrong answer: < instead of <= when freeing workers"

        ```python
        def solution(N, jobs):
            free, busy, out = list(range(N)), [], []
            for a, d in jobs:
                while busy and busy[0][0] < a:
                    heapq.heappush(free, heapq.heappop(busy)[1])
                if free:
                    w, start = heapq.heappop(free), a
                else:
                    start, w = heapq.heappop(busy)
                heapq.heappush(busy, (start + d, w))
                out.append((w, start + d))
            return out
        ```

        Checked: edge, a worker that finishes at the arrival time is idle: got [(0, 2), (1, 3)] want [(0, 2), (0, 3)].

---

## After the mock

Read [the 15 most common mistakes](common-mistakes.md) once more and tick the ones you made. Two of them came up
here: the tie rule (smallest number first) and `<` against `<=` at a boundary.
