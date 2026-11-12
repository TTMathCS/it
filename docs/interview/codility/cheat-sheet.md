# Cheat sheet

One page. Read it the day before and again in the hour before the test.

## The day before

* Take Codility's **[demo test](https://app.codility.com/demo/take-sample-test/)** once more, on the
  computer you will use. Note the Python version and the SQL dialects it shows.
* Use a **laptop or desktop**, not a phone or tablet (Codility says phones and tablets are not supported).
* Use a supported browser. If the test shares your screen, Codility lists Chrome 131 or newer, Chromium
  Edge 130 or newer, or Opera 114 or newer.
* Open the invitation link and read the intro page: **number of tasks, allowed languages, time limit**, and
  the window in which you must start. Opening the link does not start the clock; pressing **Start** does.
* Block out the whole time limit plus 15 minutes. **The timer cannot be paused** once you start.

## In the first five minutes

1. Read **all three tasks** before writing anything. You can move freely between tasks.
2. Start with the task you find easiest. A finished easy task beats two half-finished hard ones.
3. For each SQL task, **check the selected dialect** (PostgreSQL or SQLite) before typing.

## SQL: before you submit each query

* **Columns:** exactly the ones asked for, **in the order asked**. Use the names asked for, too.
* **Sort order:** the `ORDER BY` the task states, **with every tie-breaker** it mentions.
* **Rows that must not disappear:** "every department, even with no employees" means `LEFT JOIN`, then
  `COUNT(column)` (not `COUNT(*)`) and `COALESCE(SUM(...), 0)`.
* **NULLs:** `= NULL` is never true; use `IS NULL`. `NOT IN (subquery)` returns nothing if the subquery
  has a NULL; use `LEFT JOIN ... WHERE right.id IS NULL` (fast on both databases).
  `NOT EXISTS` is also correct but can be very slow on SQLite when the join column has no index.
* **Duplicates:** could the same person, day or pair appear twice? Use `DISTINCT` or group first.
* **Integer division:** `5/2` is `2` in both PostgreSQL and SQLite. Write `5 * 1.0 / 2` for 2.5.
* **Rounding:** in PostgreSQL, `ROUND(x, 2)` works on numeric values but fails on a float
  (`double precision`). `ROUND(AVG(int_column), 2)` works in both.
* **Dates:** PostgreSQL has real dates (`d - 1`, `EXTRACT`); SQLite stores text (`date(d, '-1 day')`,
  `strftime`, `julianday`).
* **Ranking with ties:** `ROW_NUMBER` (no ties), `RANK` (1, 1, 3), `DENSE_RANK` (1, 1, 2). Pick the
  one the task describes.
* **Run it** on the example, then **add your own cases**: an empty table, a group with no rows, a tie,
  duplicates, NULLs.

## Python: before you submit

* **Read the limits** and pick the algorithm from them:

    | Largest N | Fast enough | Usually too slow |
    |---|---|---|
    | up to about 1,000 | O(N²) | O(2^N) |
    | up to 100,000 or 1,000,000 | O(N) or O(N log N) | O(N²) |
    | values up to 10^9 | work with the N items, not one slot per value | an array of size max value |

* Keep the **function signature** exactly as given; add helper functions if you like.
* **Return** the answer in the type asked for (an `int`, a `str`, a `list`); do not `print` it.
* Edge cases: empty list, one element, all equal, negatives, zero, the largest values, duplicates.
* **No deep recursion:** Python's default recursion limit is 1,000 calls, so a recursive walk over
  100,000 items crashes. Use a loop or an explicit stack.
* Python integers never overflow, so you need no special care for big sums (other languages do).
* Fast tools: `set` and `dict` for "have I seen it" (not `x in list` inside a loop), `sorted(..., key=...)`,
  `collections.Counter`, `collections.deque` (not `list.pop(0)`), `heapq`, `bisect`.
* Only the **standard library**, unless the task says otherwise (Codility's FAQ). Whether pandas is
  available is unknown; do not count on it.

## The last five minutes

* Code that is in the editor when time runs out is **submitted automatically**, so it must at least run.
  Never leave a half-typed line.
* "OK" after **Run** only means the example passed. Hidden tests decide the score.
* Once you press **Submit** on a task you cannot change it.
