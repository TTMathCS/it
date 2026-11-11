# Mock test 1

Two SQL tasks and one Python task, in the style of a Codility first round. **Set a timer for 80 minutes** and
work as you would in the real test:

* Read all three tasks first. Write your answers in a real editor and run them: for SQL, any PostgreSQL or
  SQLite (for example [an online SQLite](https://sqlite.org/fiddle/) or a local PostgreSQL); for Python, any
  Python 3.
* Make up your own test rows and inputs before you look at the solutions.
* Only when the timer ends, open the green boxes. Each one shows the tested answer, why it works, the edge cases
  it was checked on, and the common wrong answers with the case each one fails.

| Task | Type | Aim for |
|---|---|---|
| 1 | SQL | 20 minutes |
| 2 | SQL | 25 minutes |
| 3 | Python | 35 minutes |

---

### Task&nbsp;1: Department payroll

**Level:** Medium · **Aim for:** 20 minutes

A company keeps its departments and employees in two tables (below). Write an SQL query that returns
**one row per department, including departments that have no employees**, with three columns:

* `department`: the department's name;
* `headcount`: the number of employees in that department;
* `total_salary`: the sum of their salaries, or `0` if the department has no employees.

Employees whose `dept_id` is `NULL` belong to no department and are not counted anywhere.
Sort the rows by `total_salary` from highest to lowest; when two departments have the same total, sort them by
name from A to Z.

Assume that department names are unique, every non-NULL `dept_id` matches a department, and salaries are positive.

**Tables**

```sql
CREATE TABLE departments (
    id   INTEGER PRIMARY KEY,
    name VARCHAR(40) NOT NULL
);
CREATE TABLE employees (
    id      INTEGER PRIMARY KEY,
    name    VARCHAR(40) NOT NULL,
    dept_id INTEGER,
    salary  INTEGER NOT NULL
);
```

**Example data**

`departments`

| id | name |
|---|---|
| 1 | Data |
| 2 | Sales |
| 3 | Legal |
| 4 | Ops |

`employees`

| id | name | dept_id | salary |
|---|---|---|---|
| 1 | Ana | 1 | 5000 |
| 2 | Ben | 1 | 4000 |
| 3 | Cy | 2 | 6000 |
| 4 | Dee | 2 | 3000 |
| 5 | Eli | NULL | 7000 |
| 6 | Fay | 4 | 2500 |

**Your query should return**

| department | headcount | total_salary |
|---|---|---|
| Data | 2 | 9000 |
| Sales | 2 | 9000 |
| Ops | 1 | 2500 |
| Legal | 0 | 0 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT d.name              AS department,
           COUNT(e.id)            AS headcount,
           COALESCE(SUM(e.salary), 0) AS total_salary
    FROM departments d
    LEFT JOIN employees e ON e.dept_id = d.id
    GROUP BY d.id, d.name
    ORDER BY total_salary DESC, department ASC;
    ```
    
    **Why it works**
    
    * **`LEFT JOIN` from `departments`** keeps a department even when no employee matches it ("Legal" in the example).
      With an inner `JOIN` that row disappears.
    * **`COUNT(e.id)`, not `COUNT(*)`.** For a department with no employees, the left join produces one row whose
      employee columns are all `NULL`. `COUNT(*)` counts that row (giving 1); `COUNT(e.id)` counts only non-NULL ids
      (giving 0).
    * **`COALESCE(SUM(...), 0)`.** `SUM` over nothing but NULLs is `NULL`, not 0. The task asks for 0.
    * **Group by `d.id, d.name`.** Grouping by the key is the safe habit (two departments could share a name in
      other tasks); adding `d.name` lets you select it in every dialect.
    * **Two sort keys.** "Data" and "Sales" both total 9000; only the second key, `department ASC`, makes the
      order certain. Without it the database may return either order, and a hidden test with a tie fails.
    * Employees with `dept_id IS NULL` simply never match a department, so they drop out with no extra code.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: no employees at all;
    * edge case: no departments;
    * edge case: every employee has no department;
    * edge case: tie on total, names decide;
    * 200 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.07 s, SQLite 3.53 0.24 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: INNER JOIN drops empty departments"
    
        ```sql
        SELECT d.name AS department, COUNT(e.id) AS headcount, SUM(e.salary) AS total_salary
        FROM departments d JOIN employees e ON e.dept_id = d.id
        GROUP BY d.id, d.name ORDER BY total_salary DESC, department ASC;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: COUNT(*) counts the empty department as 1"
    
        ```sql
        SELECT d.name AS department, COUNT(*) AS headcount, COALESCE(SUM(e.salary), 0) AS total_salary
        FROM departments d LEFT JOIN employees e ON e.dept_id = d.id
        GROUP BY d.id, d.name ORDER BY total_salary DESC, department ASC;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: SUM without COALESCE gives NULL, not 0"
    
        ```sql
        SELECT d.name AS department, COUNT(e.id) AS headcount, SUM(e.salary) AS total_salary
        FROM departments d LEFT JOIN employees e ON e.dept_id = d.id
        GROUP BY d.id, d.name ORDER BY total_salary DESC, department ASC;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: no tie-breaker in ORDER BY"
    
        ```sql
        SELECT d.name AS department, COUNT(e.id) AS headcount, COALESCE(SUM(e.salary), 0) AS total_salary
        FROM departments d LEFT JOIN employees e ON e.dept_id = d.id
        GROUP BY d.id, d.name ORDER BY total_salary DESC;
        ```
        
        Checked: this gives a wrong result on **edge: tie on total, names decide, sample**.



---

### Task&nbsp;2: Longest login streak

**Level:** Hard · **Aim for:** 25 minutes

The table `logins` gets one row every time a user signs in; a user may sign in several times on the same day.
A **streak** is a run of consecutive calendar days on which the user signed in at least once.

Write an SQL query that returns, **for every user in the table**, two columns:

* `user_id`;
* `longest_streak`: the length, in days, of that user's longest streak.

Sort by `longest_streak` from highest to lowest, then by `user_id` from lowest to highest.

**Tables**

```sql
CREATE TABLE logins (
    user_id    INTEGER NOT NULL,
    login_date DATE NOT NULL
);
```

**Example data**

`logins`

| user_id | login_date |
|---|---|
| 7 | 2026-03-01 |
| 7 | 2026-03-02 |
| 7 | 2026-03-02 |
| 7 | 2026-03-03 |
| 7 | 2026-03-05 |
| 3 | 2026-02-27 |
| 3 | 2026-02-28 |
| 3 | 2026-03-01 |
| 9 | 2026-03-10 |

**Your query should return**

| user_id | longest_streak |
|---|---|
| 3 | 3 |
| 7 | 3 |
| 9 | 1 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**
    
    ```sql
    WITH days AS (                       -- one row per user per day
        SELECT DISTINCT user_id, login_date FROM logins
    ),
    grouped AS (                         -- same value of grp = same unbroken run
        SELECT user_id,
               login_date - CAST(ROW_NUMBER() OVER (PARTITION BY user_id
                                                    ORDER BY login_date) AS INTEGER) AS grp
        FROM days
    )
    SELECT user_id, MAX(run_length) AS longest_streak
    FROM (SELECT user_id, grp, COUNT(*) AS run_length
          FROM grouped
          GROUP BY user_id, grp) runs
    GROUP BY user_id
    ORDER BY longest_streak DESC, user_id ASC;
    ```
    
    **SQLite**
    
    ```sql
    WITH days AS (                       -- one row per user per day
        SELECT DISTINCT user_id, login_date FROM logins
    ),
    grouped AS (                         -- same value of grp = same unbroken run
        SELECT user_id,
               julianday(login_date) - ROW_NUMBER() OVER (PARTITION BY user_id
                                                          ORDER BY login_date) AS grp
        FROM days
    )
    SELECT user_id, MAX(run_length) AS longest_streak
    FROM (SELECT user_id, grp, COUNT(*) AS run_length
          FROM grouped
          GROUP BY user_id, grp) runs
    GROUP BY user_id
    ORDER BY longest_streak DESC, user_id ASC;
    ```
    
    **Why it works**
    
    This is the classic **gaps and islands** pattern.
    
    1. **One row per user per day first** (`SELECT DISTINCT`). A second sign-in on the same day must not count as
       another day; without `DISTINCT` it also breaks the trick in step 2.
    2. **Number each user's days in date order** with `ROW_NUMBER()`. Inside one unbroken run, the date goes up by
       one day exactly when the row number goes up by one, so **date minus row number is the same value for every
       day of the run**, and changes after any gap. That value (`grp`) labels the run.
    
        | login_date | row number | date − row number |
        |---|---|---|
        | 2026-03-01 | 1 | 2026-02-28 |
        | 2026-03-02 | 2 | 2026-02-28 |
        | 2026-03-03 | 3 | 2026-02-28 |
        | 2026-03-05 | 4 | 2026-03-01 |
    
    3. **Count the days in each run**, then take each user's longest.
    
    **Why the two dialects differ.** In PostgreSQL, `date - integer` gives a date, but `ROW_NUMBER()` returns a
    `bigint` and there is no `date - bigint` operator, so the row number is cast to `INTEGER`. SQLite has no date
    type: dates are text, so `julianday()` turns each into a day number first. Both use real calendar arithmetic, so
    streaks over a month end, a leap day or New Year are counted correctly (those are among the tested edge cases);
    subtracting the day of the month would break there.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: empty table;
    * edge case: same day logged many times;
    * edge case: duplicate inside a streak;
    * edge case: streak over a leap day;
    * edge case: streak over new year;
    * 200 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.30 s, SQLite 3.53 0.53 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: forgetting DISTINCT (a repeated day breaks the run)"
    
        PostgreSQL:
        
        ```sql
        WITH grouped AS (
            SELECT user_id, login_date - CAST(ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY login_date) AS INTEGER) AS grp
            FROM logins)
        SELECT user_id, MAX(run_length) AS longest_streak
        FROM (SELECT user_id, grp, COUNT(*) AS run_length FROM grouped GROUP BY user_id, grp) runs
        GROUP BY user_id ORDER BY longest_streak DESC, user_id ASC;
        ```
        
        SQLite:
        
        ```sql
        WITH grouped AS (
            SELECT user_id, julianday(login_date) - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY login_date) AS grp
            FROM logins)
        SELECT user_id, MAX(run_length) AS longest_streak
        FROM (SELECT user_id, grp, COUNT(*) AS run_length FROM grouped GROUP BY user_id, grp) runs
        GROUP BY user_id ORDER BY longest_streak DESC, user_id ASC;
        ```
        
        Checked: this gives a wrong result on **edge: duplicate inside a streak**.
    
    ??? failure "A common wrong answer: using the day of the month (breaks at month end)"
    
        PostgreSQL:
        
        ```sql
        WITH days AS (SELECT DISTINCT user_id, login_date FROM logins),
        grouped AS (
            SELECT user_id, EXTRACT(DAY FROM login_date) - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY login_date) AS grp
            FROM days)
        SELECT user_id, MAX(run_length) AS longest_streak
        FROM (SELECT user_id, grp, COUNT(*) AS run_length FROM grouped GROUP BY user_id, grp) runs
        GROUP BY user_id ORDER BY longest_streak DESC, user_id ASC;
        ```
        
        SQLite:
        
        ```sql
        WITH days AS (SELECT DISTINCT user_id, login_date FROM logins),
        grouped AS (
            SELECT user_id, CAST(strftime('%d', login_date) AS INTEGER) - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY login_date) AS grp
            FROM days)
        SELECT user_id, MAX(run_length) AS longest_streak
        FROM (SELECT user_id, grp, COUNT(*) AS run_length FROM grouped GROUP BY user_id, grp) runs
        GROUP BY user_id ORDER BY longest_streak DESC, user_id ASC;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: counting days, not runs"
    
        ```sql
        SELECT user_id, COUNT(DISTINCT login_date) AS longest_streak
        FROM logins GROUP BY user_id ORDER BY longest_streak DESC, user_id ASC;
        ```
        
        Checked: this gives a wrong result on **sample**.



Related chapters in the SQL course:
[window functions for ranking](../../databases/sql/13-Window-Functions-Ranking.md),
[dates and time series](../../databases/sql/16-Dates-and-Time-Series.md),
[classic interview patterns](../../databases/sql/15-Classic-Interview-Patterns.md).

---

### Task&nbsp;3: Busiest moment

**Level:** Medium · **Aim for:** 35 minutes

A data platform logs its batch jobs. Job `i` starts at time `S[i]` and ends at time `E[i]` (in seconds). A job is
running at every moment `t` with `S[i] <= t < E[i]`, so a job that ends at time `t` and a job that starts at time
`t` are **not** running at the same time.

Write a function `solution(S, E)` that returns the largest number of jobs running at the same moment
(0 if there are no jobs).

**Examples**

* `solution([1, 2, 4, 7], [5, 3, 8, 9])` returns `2`
* `solution([0, 5], [5, 10])` returns `1`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of both lists, is an integer within the range [0..100,000];
* each element of `S` and `E` is an integer within the range [0..1,000,000,000];
* `S[i] < E[i]` for every `i`.

Start from:

```python
def solution(S, E):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(S, E):
        # One event per start (+1) and per end (-1).
        events = [(s, 1) for s in S] + [(e, -1) for e in E]
        # At the same moment, (t, -1) sorts before (t, 1): a job that ends at t
        # is gone before a job that starts at t arrives.
        events.sort()
        running = best = 0
        for _, change in events:
            running += change
            best = max(best, running)
        return best
    ```
    
    **Why it works**
    
    **Read the limits first.** N can be 100,000, so checking every pair of jobs is about 10^10 steps: far too slow.
    Times go up to a billion, so an array with one counter per second is too big. That leaves sorting:
    O(N log N).
    
    **Sweep line.** Turn every job into two events: `+1` at its start and `-1` at its end. Walk through the events in
    time order, keeping a running total; the largest total seen is the answer.
    
    **The one tricky detail is a tie in time.** If one job ends at 5 and another starts at 5, they do not overlap,
    so the end must be processed first. Python sorts tuples element by element, and `-1 < 1`, so `(5, -1)` comes
    before `(5, 1)` with no extra code.
    
    **Cost:** O(N log N) time for the sort, O(N) memory.
    
    **The slow answer:** Comparing every pair of visits is O(N²): about 5 billion steps for 100,000 visits.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no jobs: `solution([], [])` returns `0`;
    * edge case, one job: `solution([3], [4])` returns `1`;
    * edge case, all identical: `solution([2, 2, 2], [6, 6, 6])` returns `3`;
    * edge case, touching chain: `solution([0, 1, 2, 3], [1, 2, 3, 4])` returns `1`;
    * edge case, one long job covers all: `solution([0, 1, 3, 5], [100, 2, 4, 6])` returns `2`;
    * edge case, huge times: `solution([0, 999999999], [1000000000, 1000000000])` returns `2`;
    * 1500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.159s.
    
    ??? failure "A common wrong answer: counting a job that ends at t as still running"
    
        ```python
        def solution(S, E):
            events = [(s, 0) for s in S] + [(e, 1) for e in E]   # starts sort first: wrong
            events.sort()
            running = best = 0
            for _, kind in events:
                running += 1 if kind == 0 else -1
                best = max(best, running)
            return best
        ```
        
        Checked: example: got 2 want 1.
    
    ??? failure "A common wrong answer: checking every pair (right answer, too slow)"
    
        ```python
        def solution(S, E):
            best = 0
            for t in S:
                best = max(best, sum(1 for s, e in zip(S, E) if s <= t < e))
            return best
        ```
        
        Checked: timed out after 5.0s on the large input.



---

## Score yourself

For each task, count the edge cases listed in its solution that **your** answer would get right. In the real
test, each hidden test you pass earns points, so an answer that handles the example but not the empty table or
the tie loses those points.
