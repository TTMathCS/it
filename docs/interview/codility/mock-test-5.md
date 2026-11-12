# Mock test 5

One more rehearsal, with three topics the other mocks do not use. **Set a timer for 80 minutes.**

| Task | Type | Level | Aim for |
|---|---|---|---|
| 1 | SQL | Medium | 15 minutes |
| 2 | SQL | Hard | 25 minutes |
| 3 | Python | Medium | 30 minutes |

That leaves 10 minutes to go back over the edge cases of all three. Before you open a solution, write down the
edge cases you tested. Then compare with the list in the solution.

---

### Task&nbsp;1: Revenue month by month

**Level:** Medium · **Aim for:** 15 minutes

A shop keeps one row per order. Write an SQL query that returns one row for **every month that has at least one
order**, with three columns:

* `month`: the month as text `'YYYY-MM'`;
* `revenue`: the total `amount` of that month's orders;
* `change`: `revenue` minus the revenue of the row before it in the result (the previous month that has orders),
  or `NULL` for the first row.

Sort by `month`, oldest first. Orders can span several years.

**Tables**

```sql
CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date  DATE NOT NULL,
    amount      INTEGER NOT NULL
);
```

**Example data**

`orders`

| id | customer_id | order_date | amount |
|---|---|---|---|
| 1 | 1 | 2025-11-20 | 100 |
| 2 | 2 | 2025-12-03 | 250 |
| 3 | 1 | 2025-12-28 | 50 |
| 4 | 3 | 2026-01-15 | 200 |
| 5 | 2 | 2026-03-01 | 400 |
| 6 | 1 | 2026-03-31 | 100 |
| 7 | 3 | 2026-11-05 | 80 |

**Your query should return**

| month | revenue | change |
|---|---|---|
| 2025-11 | 100 | NULL |
| 2025-12 | 300 | 200 |
| 2026-01 | 200 | -100 |
| 2026-03 | 500 | 300 |
| 2026-11 | 80 | -420 |

??? success "Solution and explanation (open after you try)"

    **SQLite**
    
    ```sql
    WITH m AS (
        SELECT strftime('%Y-%m', order_date) AS month, SUM(amount) AS revenue
        FROM orders
        GROUP BY strftime('%Y-%m', order_date)
    )
    SELECT month, revenue,
           revenue - LAG(revenue) OVER (ORDER BY month) AS change
    FROM m
    ORDER BY month;
    ```
    
    **PostgreSQL** (not run): the same query with `TO_CHAR(order_date, 'YYYY-MM')` in both places where
    `strftime` is.
    
    **Why it works**
    
    * **Total first, then LAG.** `LAG` looks at the row before. If you run it on the orders, "the row before" is
      another order, not another month. So the CTE makes one row per month, and `LAG` runs on that.
    * **Year and month together.** `'%Y-%m'` keeps November 2025 and November 2026 apart. Grouping by the month
      number alone adds them up into one row.
    * **The text sorts right.** `'2025-12'` comes before `'2026-01'` as text, because the year is first and the
      month has two digits. So `ORDER BY month` is also date order.
    * **The first row stays NULL.** `LAG` gives `NULL` when there is no row before, and `revenue - NULL` is
      `NULL`. The task asks for exactly that, so do not wrap it in `COALESCE`.
    * A month with no orders (February 2026 here) has no row, so March is compared with January. That is what the
      task says.
    
    **Tested on SQLite 3.54.** Every case below gave exactly the expected rows, compared with a separate Python answer:
    
    * the example above;
    * edge case: empty table;
    * edge case: one order;
    * edge case: the same month in two years;
    * edge case: revenue goes down;
    * edge case: many orders on one day;
    * 300 random small tables;
    * a large table of 200,000 rows: 0.08 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: month number only (two Novembers become one)"
    
        ```sql
        WITH m AS (SELECT strftime('%m', order_date) AS month, SUM(amount) AS revenue FROM orders GROUP BY 1)
        SELECT month, revenue, revenue - LAG(revenue) OVER (ORDER BY month) AS change FROM m ORDER BY month;
        ```
        
        Checked: wrong on **sample, one order, same month in two years, revenue goes down, many orders on one day**
        (the month comes out as `'11'`, not `'2025-11'`).
    
    ??? failure "A common wrong answer: LAG on the orders, not on the months"
    
        ```sql
        SELECT DISTINCT strftime('%Y-%m', order_date) AS month,
               SUM(amount) OVER (PARTITION BY strftime('%Y-%m', order_date)) AS revenue,
               amount - LAG(amount) OVER (ORDER BY order_date, id) AS change
        FROM orders ORDER BY month;
        ```
        
        Checked: wrong on **sample, many orders on one day**.
    
    ??? failure "A common wrong answer: COALESCE turns the first change into 0"
    
        ```sql
        WITH m AS (SELECT strftime('%Y-%m', order_date) AS month, SUM(amount) AS revenue FROM orders GROUP BY 1)
        SELECT month, revenue, COALESCE(revenue - LAG(revenue) OVER (ORDER BY month), 0) AS change
        FROM m ORDER BY month;
        ```
        
        Checked: wrong on **sample, one order, same month in two years, revenue goes down, many orders on one day**.



---

### Task&nbsp;2: Median salary

**Level:** Hard · **Aim for:** 25 minutes

Write an SQL query that returns the **median salary of each department**: one row per department that has
employees, with `dept` and `median_salary`, sorted by `dept`.

The median is the middle salary once a department's salaries are sorted. When a department has an even number of
employees, it is the average of the two middle salaries. Do not use a built-in median or percentile function (SQLite
has none, and the test may run on SQLite).

**Tables**

```sql
CREATE TABLE employees (
    id     INTEGER PRIMARY KEY,
    dept   VARCHAR(20) NOT NULL,
    salary INTEGER NOT NULL
);
```

**Example data**

`employees`

| id | dept | salary |
|---|---|---|
| 1 | Data | 3000 |
| 2 | Data | 1000 |
| 3 | Data | 2000 |
| 4 | Ops | 4000 |
| 5 | Ops | 1000 |
| 6 | Ops | 3000 |
| 7 | Ops | 2000 |
| 8 | Legal | 5000 |
| 9 | Sales | 2000 |
| 10 | Sales | 2000 |
| 11 | Sales | 7000 |
| 12 | Sales | 2000 |

**Your query should return**

| dept | median_salary |
|---|---|
| Data | 2000.0 |
| Legal | 5000.0 |
| Ops | 2500.0 |
| Sales | 2000.0 |

??? success "Solution and explanation (open after you try)"

    **SQLite and PostgreSQL** (only run on SQLite)
    
    ```sql
    WITH r AS (
        SELECT dept, salary,
               ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary) AS rn,
               COUNT(*) OVER (PARTITION BY dept) AS cnt
        FROM employees
    )
    SELECT dept, AVG(salary) AS median_salary
    FROM r
    WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)
    GROUP BY dept
    ORDER BY dept;
    ```
    
    **Why it works**
    
    * **Number the rows, count the group.** `ROW_NUMBER()` puts 1, 2, 3, ... on each department's salaries in
      order, and `COUNT(*) OVER` puts the department's size on every row.
    * **The two middle positions.** With integer division, `(cnt + 1) / 2` and `(cnt + 2) / 2` are the same
      number when `cnt` is odd (3 gives 2 and 2) and the two middle numbers when it is even (4 gives 2 and 3).
      `AVG` of one row is that row; `AVG` of two rows is the half-way value. One rule covers both cases.
    * **`ROW_NUMBER`, not `RANK`.** Sales has three salaries of 2000. `RANK` gives them all 1 and the next one 4,
      so positions 2 and 3 do not exist and Sales goes missing. `ROW_NUMBER` never repeats a number.
    * **`AVG` turns the result into a decimal** (2000.0, 2500.0), so an even group like 1 and 2 gives 1.5, not 1.
      In PostgreSQL `AVG` of integers is a `numeric`; it prints as `2000.0000000000000000`, same value.
    
    **Tested on SQLite 3.54.** Every case below gave exactly the expected rows, compared with a separate Python answer:
    
    * the example above;
    * edge case: empty table;
    * edge case: one employee;
    * edge case: two employees whose salaries add up to an odd number;
    * edge case: all salaries equal;
    * edge case: ties around the middle;
    * 300 random small tables;
    * a large table of 200,000 rows: 0.22 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: AVG alone is the mean, not the median"
    
        ```sql
        SELECT dept, AVG(salary) AS median_salary FROM employees GROUP BY dept ORDER BY dept;
        ```
        
        Checked: wrong on **sample, ties around the middle**.
    
    ??? failure "A common wrong answer: RANK skips numbers on ties"
    
        ```sql
        WITH r AS (SELECT dept, salary, RANK() OVER (PARTITION BY dept ORDER BY salary) AS rn,
                          COUNT(*) OVER (PARTITION BY dept) AS cnt FROM employees)
        SELECT dept, AVG(salary) AS median_salary FROM r WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)
        GROUP BY dept ORDER BY dept;
        ```
        
        Checked: wrong on **sample, all salaries equal**.
    
    ??? failure "A common wrong answer: only the lower middle row"
    
        ```sql
        WITH r AS (SELECT dept, salary, ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary) AS rn,
                          COUNT(*) OVER (PARTITION BY dept) AS cnt FROM employees)
        SELECT dept, AVG(salary) AS median_salary FROM r WHERE rn = (cnt + 1) / 2
        GROUP BY dept ORDER BY dept;
        ```
        
        Checked: wrong on **sample, two employees, odd sum**.



---

### Task&nbsp;3: How many people?

**Level:** Medium · **Aim for:** 30 minutes

A sign-up system has created duplicate accounts. `A[i]` is the list of email addresses on account `i`. Two accounts
belong to the **same person** if they share an email address, or if they are linked through a chain of accounts that
each share one with the next. Emails are compared exactly as written (`Ann@x` and `ann@x` are different).

Write a function `solution(A)` that returns the number of different people.

**Examples**

* `solution([["ana@x", "ana@y"], ["bo@x"], ["ana@y", "cy@z"], ["cy@z", "dee@z"]])` returns `2`
  (accounts 0, 2 and 3 are one person; account 1 is another)
* `solution([["p@q"], ["p@q"], ["r@s"]])` returns `2`

**Write an efficient algorithm for the following assumptions:**

* `N`, the number of accounts, is an integer within the range [0..100,000];
* each account has between 1 and 10 emails, and there are at most 300,000 emails in all;
* each email is a string of 1 to 50 characters.

Start from:

```python
def solution(A):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A):
        parent = list(range(len(A)))
        
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]   # shorten the path as we walk
                x = parent[x]
            return x
        
        owner = {}                      # email -> first account that had it
        people = len(A)
        for i, emails in enumerate(A):
            for e in emails:
                if e in owner:
                    a, b = find(i), find(owner[e])
                    if a != b:
                        parent[a] = b
                        people -= 1
                else:
                    owner[e] = i
        return people
    ```
    
    **Why it works**
    
    * **Start with every account as its own person**, so `people = N`. Each time two accounts that are not yet
      joined turn out to share an email, two groups become one and `people` goes down by one.
    * **Union-find** keeps the groups. `parent` points each account at another in its group; following the
      pointers ends at the group's root. Two accounts are in the same group when `find` gives the same root. The
      line `parent[x] = parent[parent[x]]` makes the paths shorter every time we walk them, so `find` stays fast
      even on a long chain.
    * **The dictionary `owner`** remembers one account for each email. When the email shows up again, join the
      two accounts. There is no need to compare every pair of accounts.
    * **Why a chain needs this.** In `[["a"], ["b"], ["a", "b"]]` accounts 0 and 1 share nothing, but account 2
      joins them, so the answer is 1. Any answer that decides "new person or not" when it first sees an account
      gets 2.
    
    **Cost:** about O(E) for E emails in all (union-find is close to constant per step), O(N + E) memory.
    
    **The slow answer:** keep a set of emails per group and merge any two sets that overlap, over and over. That
    compares pairs of groups, O(N²) in the worst case: about 5 billion checks for 100,000 accounts.
    
    **Tested** (Python 3.9; standard library only):
    
    * the examples above;
    * edge case, no accounts: `solution([])` returns `0`;
    * edge case, one account: `solution([["a@b"]])` returns `1`;
    * edge case, a chain joined late: `solution([["a"], ["b"], ["a", "b"]])` returns `1`;
    * edge case, the same email twice in one account: `solution([["a", "a"], ["b"]])` returns `2`;
    * edge case, five accounts all holding `"x"`: returns `1`;
    * edge case, case matters: `solution([["Ann@x"], ["ann@x"]])` returns `2`;
    * 1500 random small inputs, each compared with the slow answer;
    * the largest input the limits allow (100,000 accounts, 300,000 emails): 0.102 s;
    * 100,000 accounts each sharing one email with the next, given in reverse order: 1 person, 0.045 s.
    
    ??? failure "A common wrong answer: only looks back, never joins two older groups"
    
        ```python
        def solution(A):
            seen, people = set(), 0
            for emails in A:
                if not any(e in seen for e in emails):
                    people += 1
                seen.update(emails)
            return people
        ```
        
        Checked: wrong on **chain joined late** (returns 2, want 1). It passes both examples, which is why it is
        a trap.



---

## After the mock

Count the edge cases in each solution that your own answer gets right. On the real test, the hidden tests are cases
like these, and each one you miss costs points even when the example passes.
