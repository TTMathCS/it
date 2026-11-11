# SQL practice set

Twenty-eight tasks in the style of a Codility SQL task, from easy to hard, grouped by the pattern they practise.
Each gives the tables, example rows and the exact result your query should return.

**How to practise:** write the query in PostgreSQL or SQLite (an online [SQLite fiddle](https://sqlite.org/fiddle/)
is enough), run it on the example, then write two or three edge cases of your own **before** opening the
solution. Each solution lists the edge cases it was tested on and the common wrong answers, with the case each
one fails.

Every answer here was run on PostgreSQL 16 and SQLite 3.53 with the example, the listed edge cases, 150 random
small tables checked against a separate Python answer, and a large table, timed.

!!! tip "Codility's own SQL tasks"
    Codility has three free SQL practice tasks with a real grader. Do them too; the page
    [Codility's own tasks](codility-tasks.md) links each one and says which task here practises the same idea.

## A. Filtering, grouping and the shape of the result

### 1. Cities with new stations

**Level:** Easy · **Aim for:** 10 minutes

A rail company records every station it opens. Write an SQL query that returns each city with **at least two
stations opened on or after 1 January 2025**, in two columns: `city` and `new_stations` (how many such stations it
has). Stations opened before 2025 are not counted. Sort by `new_stations` from highest to lowest, then by `city`
from A to Z.

**Tables**

```sql
CREATE TABLE stations (
    id     INTEGER PRIMARY KEY,
    city   VARCHAR(40) NOT NULL,
    opened DATE NOT NULL
);
```

**Example data**

`stations`

| id | city | opened |
|---|---|---|
| 1 | Oslo | 2025-02-01 |
| 2 | Oslo | 2025-03-09 |
| 3 | Lima | 2024-12-31 |
| 4 | Lima | 2025-01-01 |
| 5 | Lima | 2025-06-30 |
| 6 | Quito | 2025-01-15 |
| 7 | Oslo | 2024-05-05 |

**Your query should return**

| city | new_stations |
|---|---|
| Lima | 2 |
| Oslo | 2 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT city, COUNT(*) AS new_stations
    FROM stations
    WHERE opened >= '2025-01-01'          -- filter rows first (WHERE) ...
    GROUP BY city
    HAVING COUNT(*) >= 2                  -- ... then filter groups (HAVING)
    ORDER BY new_stations DESC, city ASC;
    ```
    
    **Why it works**
    
    * `WHERE` removes **rows** before grouping; `HAVING` removes **groups** after counting. The date condition is
      about single stations, so it belongs in `WHERE`; "at least two" is about the group, so it belongs in `HAVING`.
    * The date literal `'2025-01-01'` works in both dialects: PostgreSQL turns it into a date, and SQLite compares
      the text, which sorts correctly because ISO dates (`YYYY-MM-DD`) sort in calendar order.
    * `>=` includes stations opened exactly on 1 January 2025 (the "Lima" row on that day in the example).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: two old stations only;
    * edge case: one old and one new (not enough);
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.02 s, SQLite 3.53 0.03 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: date filter forgotten"
    
        ```sql
        SELECT city, COUNT(*) AS new_stations FROM stations
        GROUP BY city HAVING COUNT(*) >= 2 ORDER BY new_stations DESC, city ASC;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: > instead of >= on the date"
    
        ```sql
        SELECT city, COUNT(*) AS new_stations FROM stations
        WHERE opened > '2025-01-01' GROUP BY city HAVING COUNT(*) >= 2 ORDER BY new_stations DESC, city ASC;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 2. Busiest day

**Level:** Easy · **Aim for:** 8 minutes

Write an SQL query that returns the single day with the **highest total payments**: `paid_on` and `total`. If
several days share the highest total, return the earliest of them. Return no rows if the table is empty.

**Tables**

```sql
CREATE TABLE payments (
    id      INTEGER PRIMARY KEY,
    paid_on DATE NOT NULL,
    amount  INTEGER NOT NULL
);
```

**Example data**

`payments`

| id | paid_on | amount |
|---|---|---|
| 1 | 2026-05-01 | 30 |
| 2 | 2026-05-02 | 50 |
| 3 | 2026-05-01 | 20 |
| 4 | 2026-05-03 | 10 |

**Your query should return**

| paid_on | total |
|---|---|
| 2026-05-01 | 50 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT paid_on, SUM(amount) AS total
    FROM payments
    GROUP BY paid_on
    ORDER BY total DESC, paid_on ASC
    LIMIT 1;
    ```
    
    **Why it works**
    
    * Group, sort by the total, take the first row. The second sort key, `paid_on ASC`, decides ties exactly as the
      task asks; without it the database may return any of the tied days (both days total 50 in the example).
    * `LIMIT 1` works in PostgreSQL and SQLite. (SQL Server writes `TOP 1`, which both of these reject.)
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: empty table;
    * edge case: later day wins on its own;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.03 s, SQLite 3.53 0.04 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: no tie-breaker"
    
        ```sql
        SELECT paid_on, SUM(amount) AS total FROM payments GROUP BY paid_on ORDER BY total DESC LIMIT 1;
        ```
        
        Checked: this gives a wrong result on **random #6, sample**.
    
    ??? failure "A common wrong answer: MAX of the amounts, not of the daily totals"
    
        ```sql
        SELECT paid_on, amount AS total FROM payments ORDER BY amount DESC, paid_on LIMIT 1;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 3. Visitors in both January and February

**Level:** Easy · **Aim for:** 8 minutes

Write an SQL query that returns the `user_id` of every user who visited **at least once in January 2026 and at
least once in February 2026**. Each user once; sort by `user_id`.

**Tables**

```sql
CREATE TABLE visits (
    user_id    INTEGER NOT NULL,
    visited_on DATE NOT NULL
);
```

**Example data**

`visits`

| user_id | visited_on |
|---|---|
| 1 | 2026-01-05 |
| 1 | 2026-02-01 |
| 2 | 2026-01-31 |
| 2 | 2026-01-30 |
| 3 | 2026-02-14 |
| 4 | 2025-02-10 |
| 4 | 2026-01-10 |

**Your query should return**

| user_id |
|---|
| 1 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT user_id
    FROM visits
    WHERE visited_on >= '2026-01-01' AND visited_on < '2026-02-01'
    INTERSECT
    SELECT user_id
    FROM visits
    WHERE visited_on >= '2026-02-01' AND visited_on < '2026-03-01'
    ORDER BY user_id;
    ```
    
    **Why it works**
    
    * `INTERSECT` keeps rows found in both results, and removes duplicates.
    * Date ranges written as **"on or after the first day, before the first day of the next month"** avoid month
      lengths, leap years and time-of-day problems, and work the same in both dialects.
    * Another way: `GROUP BY user_id HAVING COUNT(DISTINCT <month>) = 2` with a `WHERE` that keeps only those two
      months.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: February of another year;
    * edge case: last and first day;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.04 s, SQLite 3.53 0.05 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: OR returns visitors of either month"
    
        ```sql
        SELECT DISTINCT user_id FROM visits
        WHERE (visited_on >= '2026-01-01' AND visited_on < '2026-03-01') ORDER BY user_id;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: AND on one row can never be true"
    
        ```sql
        SELECT DISTINCT user_id FROM visits
        WHERE visited_on < '2026-02-01' AND visited_on >= '2026-02-01' ORDER BY user_id;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 4. Second-highest score

**Level:** Easy · **Aim for:** 10 minutes

Write an SQL query that returns **one row with one column**, `second_highest`: the second-highest **distinct**
value of `points`. If there is no such value (the table is empty, or every row has the same points), return one
row containing `NULL`.

**Tables**

```sql
CREATE TABLE scores (
    player VARCHAR(40) NOT NULL,
    points INTEGER NOT NULL
);
```

**Example data**

`scores`

| player | points |
|---|---|
| Ana | 90 |
| Ben | 75 |
| Cy | 90 |
| Dee | 60 |

**Your query should return**

| second_highest |
|---|
| 75 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT MAX(points) AS second_highest
    FROM scores
    WHERE points < (SELECT MAX(points) FROM scores);
    ```
    
    **Why it works**
    
    * "The largest value below the largest value" is the second-highest distinct value, whatever the duplicates.
    * An aggregate with no `GROUP BY` **always returns exactly one row**. When no row passes the `WHERE`, `MAX`
      returns `NULL`, which is what the task asks for.
    * The common `LIMIT 1 OFFSET 1` answer fails twice: without `DISTINCT` it returns the top value again when the
      top is repeated (90, 90 in the example), and with `DISTINCT` it returns **no row** instead of a row with
      `NULL` when there is no second value.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: empty table;
    * edge case: all rows equal;
    * edge case: one row;
    * edge case: top value repeated;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.02 s, SQLite 3.53 0.01 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: LIMIT/OFFSET without DISTINCT"
    
        ```sql
        SELECT points AS second_highest FROM scores
        ORDER BY points DESC LIMIT 1 OFFSET 1;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: LIMIT/OFFSET with DISTINCT (no row instead of NULL)"
    
        ```sql
        SELECT DISTINCT points AS second_highest FROM scores
        ORDER BY points DESC LIMIT 1 OFFSET 1;
        ```
        
        Checked: this gives a wrong result on **edge: empty table**.



### 5. Duplicate e-mail addresses

**Level:** Easy to medium · **Aim for:** 10 minutes

A sign-up form saved e-mail addresses exactly as people typed them, with stray spaces at either end and random
capital letters. Two addresses are the same if they match after removing spaces at both ends and ignoring case.
Write an SQL query that returns each address that occurs **more than once**: `email` (trimmed, in lower case) and
`copies`. Sort by `copies` from highest to lowest, then `email`.

**Tables**

```sql
CREATE TABLE raw_signups (
    id    INTEGER PRIMARY KEY,
    email VARCHAR(100) NOT NULL
);
```

**Example data**

`raw_signups`

| id | email |
|---|---|
| 1 | ana@x.io |
| 2 |  Ana@X.io |
| 3 | ben@y.org |
| 4 | ANA@x.IO  |
| 5 | cy@z.net |
| 6 | Cy@z.net |

**Your query should return**

| email | copies |
|---|---|
| ana@x.io | 3 |
| cy@z.net | 2 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT LOWER(TRIM(email)) AS email, COUNT(*) AS copies
    FROM raw_signups
    GROUP BY LOWER(TRIM(email))
    HAVING COUNT(*) > 1
    ORDER BY copies DESC, email;
    ```
    
    **Why it works**
    
    * Clean the value **once, in the grouping key**: `GROUP BY LOWER(TRIM(email))`. Every spelling of the same
      address then falls into one group.
    * Repeat the expression in `GROUP BY` instead of grouping by the alias. Here the alias `email` is also the name
      of a table column, and in both PostgreSQL and SQLite `GROUP BY email` then means the raw **column**, not the
      cleaned value (the first wrong answer below shows it).
    * `TRIM` with no argument removes spaces at both ends in both dialects.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: no duplicates;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.06 s, SQLite 3.53 0.06 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: grouping by the raw value"
    
        ```sql
        SELECT LOWER(TRIM(email)) AS email, COUNT(*) AS copies FROM raw_signups
        GROUP BY email HAVING COUNT(*) > 1 ORDER BY copies DESC, email;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: lower case but no trim"
    
        ```sql
        SELECT LOWER(email) AS email, COUNT(*) AS copies FROM raw_signups
        GROUP BY LOWER(email) HAVING COUNT(*) > 1 ORDER BY copies DESC, email;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 6. Orders by status, one column per status

**Level:** Easy to medium · **Aim for:** 10 minutes

`status` is always one of `'pending'`, `'shipped'` or `'cancelled'`. Write an SQL query that returns one row per
`order_date` that has orders, with the number of orders in each status as three columns: `order_date`,
`pending`, `shipped`, `cancelled` (0 where there are none). Sort by `order_date`.

**Tables**

```sql
CREATE TABLE orders (
    id         INTEGER PRIMARY KEY,
    order_date DATE NOT NULL,
    status     VARCHAR(10) NOT NULL
);
```

**Example data**

`orders`

| id | order_date | status |
|---|---|---|
| 1 | 2026-04-01 | shipped |
| 2 | 2026-04-01 | pending |
| 3 | 2026-04-01 | shipped |
| 4 | 2026-04-02 | cancelled |
| 5 | 2026-04-03 | shipped |

**Your query should return**

| order_date | pending | shipped | cancelled |
|---|---|---|---|
| 2026-04-01 | 1 | 2 | 0 |
| 2026-04-02 | 0 | 0 | 1 |
| 2026-04-03 | 0 | 1 | 0 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT order_date,
           SUM(CASE WHEN status = 'pending'   THEN 1 ELSE 0 END) AS pending,
           SUM(CASE WHEN status = 'shipped'   THEN 1 ELSE 0 END) AS shipped,
           SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
    FROM orders
    GROUP BY order_date
    ORDER BY order_date;
    ```
    
    **Why it works**
    
    * **Conditional aggregation**: inside each group, `CASE` turns every row into 1 or 0 for one status, and `SUM`
      adds them up. This is the portable way to "pivot" rows into columns.
    * `COUNT(CASE WHEN status = 'pending' THEN 1 END)` also works (no `ELSE`, so other rows give `NULL`, which
      `COUNT` skips). But `COUNT(CASE ... THEN 1 ELSE 0 END)` is wrong: `COUNT` counts the zeros too.
    * PostgreSQL also has `COUNT(*) FILTER (WHERE status = 'pending')`, and SQLite supports `FILTER` too from 3.30;
      the `CASE` form works everywhere.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: empty table;
    * edge case: only one status;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.02 s, SQLite 3.53 0.08 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: COUNT with ELSE 0 counts every row"
    
        ```sql
        SELECT order_date,
               COUNT(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
               COUNT(CASE WHEN status = 'shipped' THEN 1 ELSE 0 END) AS shipped,
               COUNT(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
        FROM orders GROUP BY order_date ORDER BY order_date;
        ```
        
        Checked: this gives a wrong result on **sample**.



## B. Joins and rows that must not go missing

### 7. Customers who never ordered

**Level:** Easy · **Aim for:** 10 minutes

Write an SQL query that returns the customers who have **never placed an order**: columns `id` and `name`,
sorted by `id`. Some orders were placed by guests, so their `customer_id` is `NULL`.

**Tables**

```sql
CREATE TABLE customers (
    id   INTEGER PRIMARY KEY,
    name VARCHAR(40) NOT NULL
);
CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER,
    amount      INTEGER NOT NULL
);
```

**Example data**

`customers`

| id | name |
|---|---|
| 1 | Ana |
| 2 | Ben |
| 3 | Cy |
| 4 | Dee |

`orders`

| id | customer_id | amount |
|---|---|---|
| 10 | 1 | 30 |
| 11 | 3 | 12 |
| 12 | NULL | 8 |
| 13 | 1 | 5 |

**Your query should return**

| id | name |
|---|---|
| 2 | Ben |
| 4 | Dee |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT c.id, c.name
    FROM customers c
    LEFT JOIN orders o ON o.customer_id = c.id
    WHERE o.id IS NULL                    -- no matching order was found
    ORDER BY c.id;
    ```
    
    **Why it works**
    
    * The `LEFT JOIN` keeps every customer; a customer with no order gets one row whose order columns are all
      `NULL`. `WHERE o.id IS NULL` keeps exactly those. Test `o.id` (never NULL in a real order), not a column that
      could be NULL anyway. A guest order (`customer_id` NULL) never matches anybody, so it does no harm.
    * `WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)` is also correct, and on PostgreSQL just
      as fast. **On SQLite it can be very slow**: with no index on `orders.customer_id`, SQLite ran the inner query
      once per customer, scanning every order each time. On 50,000 customers and 200,000 orders it took
      **146 seconds**, against **0.1 s** for the `LEFT JOIN` (SQLite 3.53, measured for this guide with `perf_anti_join.py`). A hidden
      performance test with large tables would time out. In SQLite, prefer a join.
    * **The trap is `NOT IN`.** `c.id NOT IN (1, 3, NULL)` is never true: comparing with `NULL` gives "unknown",
      so the whole condition is unknown and every customer is dropped. The query below returns no rows at all on the
      example. Adding `WHERE customer_id IS NOT NULL` inside the subquery fixes it (and it is fast on both).
      See [NULL and three-valued logic](../../databases/sql/06-Null-and-Three-Valued-Logic.md).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: no orders at all;
    * edge case: only guest orders;
    * edge case: everyone ordered;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.03 s, SQLite 3.53 0.09 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: NOT IN with a NULL in the list"
    
        ```sql
        SELECT id, name FROM customers
        WHERE id NOT IN (SELECT customer_id FROM orders)
        ORDER BY id;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: inner JOIN cannot find what is missing"
    
        ```sql
        SELECT DISTINCT c.id, c.name FROM customers c
        JOIN orders o ON o.customer_id <> c.id ORDER BY c.id;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 8. Paid more than their manager

**Level:** Easy to medium · **Aim for:** 10 minutes

`manager_id` is the `id` of the person's manager, or `NULL` for the top of the company. Write an SQL query that
returns every person who earns **strictly more than their own manager**: `employee`, `employee_salary`,
`manager`, `manager_salary`. Sort by `employee`. Names are unique.

**Tables**

```sql
CREATE TABLE staff (
    id         INTEGER PRIMARY KEY,
    name       VARCHAR(40) NOT NULL,
    salary     INTEGER NOT NULL,
    manager_id INTEGER
);
```

**Example data**

`staff`

| id | name | salary | manager_id |
|---|---|---|---|
| 1 | Ana | 300 | NULL |
| 2 | Ben | 320 | 1 |
| 3 | Cy | 150 | 1 |
| 4 | Dee | 200 | 3 |
| 5 | Eli | 150 | 3 |

**Your query should return**

| employee | employee_salary | manager | manager_salary |
|---|---|---|---|
| Ben | 320 | Ana | 300 |
| Dee | 200 | Cy | 150 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT e.name   AS employee,
           e.salary AS employee_salary,
           m.name   AS manager,
           m.salary AS manager_salary
    FROM staff e
    JOIN staff m ON m.id = e.manager_id     -- m is e's manager
    WHERE e.salary > m.salary
    ORDER BY employee;
    ```
    
    **Why it works**
    
    * A **self join**: the same table appears twice under two names. Read `e` as "employee" and `m` as "manager".
    * The join condition says which row is the manager of which: the manager's `id` equals the employee's
      `manager_id`. Swapping it (`e.id = m.manager_id`) pairs each person with their **reports** instead, and is the
      most common mistake.
    * An inner join drops people without a manager, which is right here: they cannot earn more than a manager they
      do not have. See [self, semi and anti joins](../../databases/sql/09-Self-Semi-and-Anti-Joins.md).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: nobody has a manager;
    * edge case: equal pay is not more;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.13 s, SQLite 3.53 0.12 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: join direction reversed"
    
        ```sql
        SELECT e.name AS employee, e.salary AS employee_salary, m.name AS manager, m.salary AS manager_salary
        FROM staff e JOIN staff m ON e.id = m.manager_id WHERE e.salary > m.salary ORDER BY employee;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 9. Salary bands, including empty ones

**Level:** Medium · **Aim for:** 12 minutes

Salaries fall into three bands: `low` (below 3000), `middle` (3000 to 4999) and `high` (5000 or more). Write an SQL
query that returns **all three bands, always**, with `band` and `people` (how many salaries fall in it, 0 if
none). Return them in the order low, middle, high. Salaries are not negative.

**Tables**

```sql
CREATE TABLE payroll (
    name   VARCHAR(40) PRIMARY KEY,
    salary INTEGER NOT NULL
);
```

**Example data**

`payroll`

| name | salary |
|---|---|
| Ana | 2500 |
| Ben | 3000 |
| Cy | 4999 |
| Dee | 7000 |

**Your query should return**

| band | people |
|---|---|
| low | 1 |
| middle | 2 |
| high | 1 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH bands(band, low_end, high_end, sort_key) AS (
        VALUES ('low',    0,    2999,       1),
               ('middle', 3000, 4999,       2),
               ('high',   5000, 1000000000, 3)
    )
    SELECT b.band, COUNT(p.name) AS people
    FROM bands b
    LEFT JOIN payroll p ON p.salary BETWEEN b.low_end AND b.high_end
    GROUP BY b.band, b.sort_key
    ORDER BY b.sort_key;
    ```
    
    **Why it works**
    
    * A `GROUP BY` on a `CASE` expression can only return bands that **have** rows. To show empty bands you need a
      list of all bands to start from, then a `LEFT JOIN` to the data, the same idea as departments with no
      employees in Mock test 1.
    * `VALUES` inside a CTE builds that small table on the fly in both PostgreSQL and SQLite; the column names go in
      `bands(...)`.
    * `sort_key` gives the order the task asks for (alphabetical order would be high, low, middle).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: empty table;
    * edge case: everyone in one band;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.05 s, SQLite 3.53 0.06 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: GROUP BY CASE loses empty bands"
    
        ```sql
        SELECT CASE WHEN salary < 3000 THEN 'low' WHEN salary < 5000 THEN 'middle' ELSE 'high' END AS band,
               COUNT(*) AS people
        FROM payroll GROUP BY 1
        ORDER BY CASE band WHEN 'low' THEN 1 WHEN 'middle' THEN 2 ELSE 3 END;
        ```
        
        Checked: this gives a wrong result on **edge: empty table, sample**.
    
    ??? failure "A common wrong answer: ordering by the band name"
    
        ```sql
        WITH bands(band, low_end, high_end) AS (VALUES ('low', 0, 2999), ('middle', 3000, 4999), ('high', 5000, 1000000000))
        SELECT b.band, COUNT(p.name) AS people FROM bands b LEFT JOIN payroll p ON p.salary BETWEEN b.low_end AND b.high_end
        GROUP BY b.band ORDER BY b.band;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 10. Account balances from transfers

**Level:** Medium · **Aim for:** 12 minutes

Every account started at 0. Write an SQL query that returns the balance of **every account that appears in
either column**: `account` and `balance` (money received minus money sent). Sort by `account`.

**Tables**

```sql
CREATE TABLE transfers (
    id           INTEGER PRIMARY KEY,
    from_account INTEGER NOT NULL,
    to_account   INTEGER NOT NULL,
    amount       INTEGER NOT NULL
);
```

**Example data**

`transfers`

| id | from_account | to_account | amount |
|---|---|---|---|
| 1 | 100 | 200 | 50 |
| 2 | 200 | 300 | 20 |
| 3 | 100 | 200 | 50 |
| 4 | 300 | 100 | 5 |

**Your query should return**

| account | balance |
|---|---|
| 100 | -95 |
| 200 | 80 |
| 300 | 15 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH moves AS (
        SELECT to_account   AS account,  amount AS change FROM transfers
        UNION ALL
        SELECT from_account AS account, -amount AS change FROM transfers
    )
    SELECT account, SUM(change) AS balance
    FROM moves
    GROUP BY account
    ORDER BY account;
    ```
    
    **Why it works**
    
    * Each transfer touches two accounts. **Unpivot** it into two rows, one `+amount` for the receiver and one
      `-amount` for the sender, then add up per account. Every account appears, whichever side it was on.
    * **`UNION ALL`, not `UNION`.** `UNION` removes duplicate rows, so two identical transfers (same account, same
      amount) would count once. Use `UNION` only when you want de-duplication.
    * Joining two separate aggregates ("money in" and "money out") also works, but needs a `FULL OUTER JOIN` and
      `COALESCE` for accounts on only one side; the `UNION ALL` form avoids both.
    * See [set operations](../../databases/sql/12-Set-Operations.md).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: two identical transfers;
    * edge case: an account that only receives;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.07 s, SQLite 3.53 0.14 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: UNION drops identical transfers"
    
        ```sql
        WITH moves AS (SELECT to_account AS account, amount AS change FROM transfers
        UNION SELECT from_account, -amount FROM transfers)
        SELECT account, SUM(change) AS balance FROM moves GROUP BY account ORDER BY account;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: only accounts that sent money"
    
        ```sql
        SELECT t.from_account AS account,
               (SELECT COALESCE(SUM(amount), 0) FROM transfers i WHERE i.to_account = t.from_account) - SUM(t.amount) AS balance
        FROM transfers t GROUP BY t.from_account ORDER BY account;
        ```
        
        Checked: this gives a wrong result on **edge: two identical transfers**.



### 11. Data quality report

**Level:** Medium · **Aim for:** 15 minutes

Before loading `orders` into the warehouse, a pipeline runs three checks. Write an SQL query that returns **exactly
three rows**, one per check, with `check_name` and `failing_rows` (0 when nothing fails):

* `missing_customer`: orders whose `customer_id` is `NULL`;
* `negative_amount`: orders whose `amount` is below 0;
* `unknown_customer`: orders whose `customer_id` is not `NULL` but matches no customer.

Sort by `check_name`.

**Tables**

```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY
);
CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER,
    amount      INTEGER NOT NULL
);
```

**Example data**

`customers`

| id |
|---|
| 1 |
| 2 |

`orders`

| id | customer_id | amount |
|---|---|---|
| 1 | 1 | 10 |
| 2 | NULL | 5 |
| 3 | 7 | -2 |
| 4 | 2 | -1 |
| 5 | 7 | 3 |

**Your query should return**

| check_name | failing_rows |
|---|---|
| missing_customer | 1 |
| negative_amount | 2 |
| unknown_customer | 2 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT 'missing_customer' AS check_name, COUNT(*) AS failing_rows
    FROM orders WHERE customer_id IS NULL
    UNION ALL
    SELECT 'negative_amount', COUNT(*)
    FROM orders WHERE amount < 0
    UNION ALL
    SELECT 'unknown_customer', COUNT(*)
    FROM orders o
    LEFT JOIN customers c ON c.id = o.customer_id
    WHERE o.customer_id IS NOT NULL AND c.id IS NULL
    ORDER BY check_name;
    ```
    
    **Why it works**
    
    * Each check is its own small `SELECT COUNT(*)`, glued with `UNION ALL`. An aggregate without `GROUP BY` always
      returns one row, so a check with no failures still shows `0`.
    * The column names come from the **first** `SELECT` of a `UNION`; the `ORDER BY` at the end sorts the whole result.
    * `unknown_customer` is the anti-join from the "customers who never ordered" task, turned around: orders with no
      matching customer. The `customer_id IS NOT NULL` condition keeps it separate from `missing_customer`.
    * This is how real pipelines test data before loading it; see
      [data quality checks](../../databases/sql/23-Data-Quality-Checks.md).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: clean data;
    * edge case: no orders;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.03 s, SQLite 3.53 0.03 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: one check counts the other's rows"
    
        ```sql
        SELECT 'missing_customer' AS check_name, COUNT(*) AS failing_rows FROM orders WHERE customer_id IS NULL
        UNION ALL SELECT 'negative_amount', COUNT(*) FROM orders WHERE amount < 0
        UNION ALL SELECT 'unknown_customer', COUNT(*) FROM orders o LEFT JOIN customers c ON c.id = o.customer_id WHERE c.id IS NULL
        ORDER BY check_name;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: GROUP BY hides checks with no failures"
    
        ```sql
        SELECT CASE WHEN customer_id IS NULL THEN 'missing_customer' ELSE 'negative_amount' END AS check_name, COUNT(*) AS failing_rows
        FROM orders WHERE customer_id IS NULL OR amount < 0 GROUP BY 1 ORDER BY 1;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 12. Double-booked rooms

**Level:** Medium · **Aim for:** 15 minutes

A guest stays the nights from `check_in` up to the day before `check_out` (`check_out > check_in`), so one guest
can check out on the day the next checks in. Write an SQL query that returns every pair of bookings **of the same
room that share at least one night**: `booking_a` and `booking_b`, with `booking_a < booking_b`, each pair once.
Sort by `booking_a`, then `booking_b`.

**Tables**

```sql
CREATE TABLE bookings (
    id        INTEGER PRIMARY KEY,
    room      INTEGER NOT NULL,
    check_in  DATE NOT NULL,
    check_out DATE NOT NULL
);
```

**Example data**

`bookings`

| id | room | check_in | check_out |
|---|---|---|---|
| 1 | 101 | 2026-09-01 | 2026-09-04 |
| 2 | 101 | 2026-09-03 | 2026-09-05 |
| 3 | 101 | 2026-09-05 | 2026-09-06 |
| 4 | 102 | 2026-09-01 | 2026-09-10 |
| 5 | 101 | 2026-08-30 | 2026-09-07 |

**Your query should return**

| booking_a | booking_b |
|---|---|
| 1 | 2 |
| 1 | 5 |
| 2 | 5 |
| 3 | 5 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT a.id AS booking_a, b.id AS booking_b
    FROM bookings a
    JOIN bookings b
      ON  a.room = b.room
      AND a.id < b.id                      -- each pair once, never a booking with itself
      AND a.check_in < b.check_out         -- a starts before b ends ...
      AND b.check_in < a.check_out         -- ... and b starts before a ends
    ORDER BY booking_a, booking_b;
    ```
    
    **Why it works**
    
    * **Two ranges overlap exactly when each one starts before the other one ends.** This one test covers every
      case: partial overlap, one stay inside another, identical dates. Drawing the cases is slower and easy to get
      wrong.
    * Strict `<` because the end date is not a night of the stay: a check-out on the 2nd and a check-in on the 2nd
      share no night. With `<=` back-to-back stays would be reported.
    * `a.id < b.id` lists each pair once; `a.id <> b.id` would list (1, 2) and (2, 1).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: back-to-back stays;
    * edge case: same dates, different rooms;
    * edge case: one stay inside another;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 20,000 rows: PostgreSQL 16 0.07 s, SQLite 3.53 0.03 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: <= counts back-to-back stays"
    
        ```sql
        SELECT a.id AS booking_a, b.id AS booking_b FROM bookings a JOIN bookings b
        ON a.room = b.room AND a.id < b.id AND a.check_in <= b.check_out AND b.check_in <= a.check_out ORDER BY 1, 2;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: checking only whether b starts inside a"
    
        ```sql
        SELECT a.id AS booking_a, b.id AS booking_b FROM bookings a JOIN bookings b
        ON a.room = b.room AND a.id < b.id AND b.check_in >= a.check_in AND b.check_in < a.check_out ORDER BY 1, 2;
        ```
        
        Checked: this gives a wrong result on **sample**.



## C. Window functions: ranking, previous rows, running totals

### 13. Running total per pipeline

**Level:** Easy to medium · **Aim for:** 12 minutes

Each pipeline loads data once a day at most; `(pipeline, load_date)` is unique. Write an SQL query that returns
every row with a fourth column, `running_total`: the total `rows_loaded` **for that pipeline** from its first load
up to and including that day. Sort by `pipeline`, then `load_date`.

**Tables**

```sql
CREATE TABLE loads (
    pipeline    VARCHAR(20) NOT NULL,
    load_date   DATE NOT NULL,
    rows_loaded INTEGER NOT NULL
);
```

**Example data**

`loads`

| pipeline | load_date | rows_loaded |
|---|---|---|
| web | 2026-03-01 | 100 |
| web | 2026-03-02 | 50 |
| orders | 2026-03-01 | 7 |
| web | 2026-03-04 | 25 |
| orders | 2026-03-03 | 3 |

**Your query should return**

| pipeline | load_date | rows_loaded | running_total |
|---|---|---|---|
| orders | 2026-03-01 | 7 | 7 |
| orders | 2026-03-03 | 3 | 10 |
| web | 2026-03-01 | 100 | 100 |
| web | 2026-03-02 | 50 | 150 |
| web | 2026-03-04 | 25 | 175 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT pipeline, load_date, rows_loaded,
           SUM(rows_loaded) OVER (PARTITION BY pipeline
                                  ORDER BY load_date
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
    FROM loads
    ORDER BY pipeline, load_date;
    ```
    
    **Why it works**
    
    * `SUM(...) OVER (...)` is a **window function**: it adds a value to each row without collapsing the rows the way
      `GROUP BY` does.
    * `PARTITION BY pipeline` restarts the total for each pipeline; `ORDER BY load_date` makes it a running total.
    * The frame `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` says "from the first row to this one". With an
      `ORDER BY` and no frame, the default is `RANGE ... CURRENT ROW`, which also includes later rows that tie on
      `load_date`; here dates are unique per pipeline so both give the same answer, but writing the frame is the
      habit that is always right.
    * See [lag, lead and running totals](../../databases/sql/14-Window-Functions-Lag-Lead-Running-Totals.md).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: empty table;
    * edge case: a day with 0 rows;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 100,000 rows: PostgreSQL 16 0.12 s, SQLite 3.53 0.12 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: no PARTITION BY (one total across pipelines)"
    
        ```sql
        SELECT pipeline, load_date, rows_loaded,
               SUM(rows_loaded) OVER (ORDER BY load_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
        FROM loads ORDER BY pipeline, load_date;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: no ORDER BY in the window (the pipeline's grand total)"
    
        ```sql
        SELECT pipeline, load_date, rows_loaded,
               SUM(rows_loaded) OVER (PARTITION BY pipeline) AS running_total
        FROM loads ORDER BY pipeline, load_date;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 14. Top earner in each department, ties included

**Level:** Medium · **Aim for:** 12 minutes

Write an SQL query that returns, for each department, **every employee whose salary is the highest in that
department** (if two people share the top salary, return both). Columns: `dept`, `name`, `salary`. Sort by
`dept`, then `name`. Names are unique.

**Tables**

```sql
CREATE TABLE employees (
    id     INTEGER PRIMARY KEY,
    name   VARCHAR(40) NOT NULL,
    dept   VARCHAR(20) NOT NULL,
    salary INTEGER NOT NULL
);
```

**Example data**

`employees`

| id | name | dept | salary |
|---|---|---|---|
| 1 | Ana | Data | 5000 |
| 2 | Ben | Data | 5000 |
| 3 | Cy | Data | 4000 |
| 4 | Dee | Ops | 3000 |
| 5 | Eli | Ops | 3500 |
| 6 | Fay | Web | 4200 |

**Your query should return**

| dept | name | salary |
|---|---|---|
| Data | Ana | 5000 |
| Data | Ben | 5000 |
| Ops | Eli | 3500 |
| Web | Fay | 4200 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH ranked AS (
        SELECT dept, name, salary,
               RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS rnk
        FROM employees
    )
    SELECT dept, name, salary
    FROM ranked
    WHERE rnk = 1
    ORDER BY dept, name;
    ```
    
    **Why it works**
    
    * `RANK()` gives tied rows the same rank, so both Ana and Ben get rank 1 in Data. `ROW_NUMBER()` would number
      them 1 and 2 and lose Ben.
    * A window function cannot go in `WHERE` directly (the window is computed after `WHERE`), so the ranking goes
      in a CTE and the filter in the outer query.
    * Another correct way: join to `SELECT dept, MAX(salary) ... GROUP BY dept` and keep rows where the salary
      equals the department maximum.
    * Beware a query that runs in SQLite but is wrong: `SELECT dept, name, MAX(salary) FROM employees GROUP BY dept`.
      PostgreSQL rejects it (`name` is neither grouped nor aggregated). SQLite accepts it and picks the name from one
      top row, so a tie loses a person.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: empty table;
    * edge case: whole department tied;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.15 s, SQLite 3.53 0.15 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: ROW_NUMBER drops ties"
    
        ```sql
        WITH ranked AS (SELECT dept, name, salary,
            ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rn FROM employees)
        SELECT dept, name, salary FROM ranked WHERE rn = 1 ORDER BY dept, name;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: bare column with GROUP BY (error in PostgreSQL, loses ties in SQLite)"
    
        ```sql
        SELECT dept, name, MAX(salary) AS salary
        FROM employees GROUP BY dept ORDER BY dept, name;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 15. Top two products per category

**Level:** Medium · **Aim for:** 15 minutes

Write an SQL query that returns the **two products with the highest revenue in each category** (fewer if the
category has fewer products). If two products have the same revenue, the one whose name comes first
alphabetically ranks higher. Columns: `category`, `product`, `revenue`. Sort by `category`, then `revenue` from
highest to lowest, then `product`.

**Tables**

```sql
CREATE TABLE sales (
    product  VARCHAR(20) PRIMARY KEY,
    category VARCHAR(20) NOT NULL,
    revenue  INTEGER NOT NULL
);
```

**Example data**

`sales`

| product | category | revenue |
|---|---|---|
| atlas | books | 50 |
| bible | books | 80 |
| comic | books | 50 |
| chess | games | 40 |
| drill | tools | 90 |
| hammer | tools | 90 |
| saw | tools | 70 |

**Your query should return**

| category | product | revenue |
|---|---|---|
| books | bible | 80 |
| books | atlas | 50 |
| games | chess | 40 |
| tools | drill | 90 |
| tools | hammer | 90 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH ranked AS (
        SELECT category, product, revenue,
               ROW_NUMBER() OVER (PARTITION BY category
                                  ORDER BY revenue DESC, product ASC) AS rn
        FROM sales
    )
    SELECT category, product, revenue
    FROM ranked
    WHERE rn <= 2
    ORDER BY category, revenue DESC, product;
    ```
    
    **Why it works**
    
    * This is **top-N per group**: number the rows inside each group, keep numbers 1 to N.
    * Here the task wants **exactly** two per category even on ties, and says how to break them, so the right tool is
      `ROW_NUMBER()` with the tie-breaker (`product ASC`) inside the window's `ORDER BY`.
    * Compare with the previous task, where ties had to be **kept**: there `RANK()` was right. Read which one the
      task describes. `DENSE_RANK() <= 2` would return three books here (80, 50, 50).
    * See [window functions for ranking](../../databases/sql/13-Window-Functions-Ranking.md).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: empty table;
    * edge case: three-way tie;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.16 s, SQLite 3.53 0.15 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: DENSE_RANK keeps too many on ties"
    
        ```sql
        WITH ranked AS (SELECT category, product, revenue,
            DENSE_RANK() OVER (PARTITION BY category ORDER BY revenue DESC) AS rn FROM sales)
        SELECT category, product, revenue FROM ranked WHERE rn <= 2 ORDER BY category, revenue DESC, product;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: no tie-breaker inside the window"
    
        ```sql
        WITH ranked AS (SELECT category, product, revenue,
            ROW_NUMBER() OVER (PARTITION BY category ORDER BY revenue DESC) AS rn FROM sales)
        SELECT category, product, revenue FROM ranked WHERE rn <= 2 ORDER BY category, revenue DESC, product;
        ```
        
        Checked: this gives a wrong result on **edge: three-way tie**.



### 16. Latest record per customer

**Level:** Medium · **Aim for:** 12 minutes

A change log keeps every version of each customer's e-mail address. `(customer_id, updated_at)` is unique.
Write an SQL query that returns **the latest version for each customer**: `customer_id`, `email`, `updated_at`.
Sort by `customer_id`.

**Tables**

```sql
CREATE TABLE customer_updates (
    customer_id INTEGER NOT NULL,
    updated_at  TIMESTAMP NOT NULL,
    email       VARCHAR(100) NOT NULL
);
```

**Example data**

`customer_updates`

| customer_id | updated_at | email |
|---|---|---|
| 1 | 2026-05-01 09:00:00 | ana@old.io |
| 1 | 2026-05-03 18:30:00 | ana@new.io |
| 2 | 2026-05-02 10:00:00 | ben@b.org |
| 1 | 2026-05-02 08:00:00 | ana@mid.io |
| 3 | 2026-05-01 00:00:00 | zed@a.net |
| 3 | 2026-05-01 00:00:01 | cy@c.net |

**Your query should return**

| customer_id | email | updated_at |
|---|---|---|
| 1 | ana@new.io | 2026-05-03 18:30:00 |
| 2 | ben@b.org | 2026-05-02 10:00:00 |
| 3 | cy@c.net | 2026-05-01 00:00:01 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH ordered AS (
        SELECT customer_id, email, updated_at,
               ROW_NUMBER() OVER (PARTITION BY customer_id
                                  ORDER BY updated_at DESC) AS rn
        FROM customer_updates
    )
    SELECT customer_id, email, updated_at
    FROM ordered
    WHERE rn = 1
    ORDER BY customer_id;
    ```
    
    **Why it works**
    
    * This is the everyday **de-duplication** step of a data pipeline: keep one row per key, the newest one.
      `ROW_NUMBER() ... ORDER BY updated_at DESC` numbers each customer's rows newest first; keep number 1.
    * Since `(customer_id, updated_at)` is unique there are no ties; if there could be, add a tie-breaker to the
      window's `ORDER BY` so the result is always the same.
    * **Why not `MAX(updated_at)` and `MAX(email)` with `GROUP BY`?** Each `MAX` works on its own column, so you get
      the newest date and the alphabetically last e-mail, which may come from different rows (customer 3 in the
      example gets `zed@a.net`, an old address).
    * SQLite stores the timestamps as text; `'YYYY-MM-DD HH:MM:SS'` text sorts in time order, so the same query
      works.
    * More on this pattern: [duplicates and incremental loads](../../databases/sql/22-Duplicates-and-Incremental-Loads.md).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: one row per customer;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.07 s, SQLite 3.53 0.13 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: MAX of each column mixes rows"
    
        ```sql
        SELECT customer_id, MAX(email) AS email, MAX(updated_at) AS updated_at
        FROM customer_updates GROUP BY customer_id ORDER BY customer_id;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: ascending order keeps the oldest"
    
        ```sql
        WITH o AS (SELECT customer_id, email, updated_at,
            ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY updated_at) AS rn FROM customer_updates)
        SELECT customer_id, email, updated_at FROM o WHERE rn = 1 ORDER BY customer_id;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 17. Month-over-month revenue

**Level:** Medium · **Aim for:** 15 minutes

Write an SQL query that returns one row for each month **that has at least one order**: `month` as text in the
form `YYYY-MM`, `revenue` (the total `amount` that month) and `change` (that month's revenue minus the revenue of
the previous row's month; `NULL` for the first month). Sort by `month`.

**Tables**

```sql
CREATE TABLE orders (
    id         INTEGER PRIMARY KEY,
    order_date DATE NOT NULL,
    amount     INTEGER NOT NULL
);
```

**Example data**

`orders`

| id | order_date | amount |
|---|---|---|
| 1 | 2025-12-03 | 100 |
| 2 | 2025-12-20 | 50 |
| 3 | 2026-01-05 | 90 |
| 4 | 2026-03-01 | 200 |
| 5 | 2026-03-31 | 10 |

**Your query should return**

| month | revenue | change |
|---|---|---|
| 2025-12 | 150 | NULL |
| 2026-01 | 90 | -60 |
| 2026-03 | 210 | 120 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**
    
    ```sql
    WITH monthly AS (
        SELECT TO_CHAR(order_date, 'YYYY-MM') AS month, SUM(amount) AS revenue
        FROM orders
        GROUP BY TO_CHAR(order_date, 'YYYY-MM')
    )
    SELECT month, revenue,
           revenue - LAG(revenue) OVER (ORDER BY month) AS change
    FROM monthly
    ORDER BY month;
    ```
    
    **SQLite**
    
    ```sql
    WITH monthly AS (
        SELECT strftime('%Y-%m', order_date) AS month, SUM(amount) AS revenue
        FROM orders
        GROUP BY strftime('%Y-%m', order_date)
    )
    SELECT month, revenue,
           revenue - LAG(revenue) OVER (ORDER BY month) AS change
    FROM monthly
    ORDER BY month;
    ```
    
    **Why it works**
    
    * Two steps: first **aggregate** to one row per month (the CTE), then use `LAG` over those monthly rows. A window
      function runs after `GROUP BY`, but splitting it into a CTE keeps each step easy to check.
    * `LAG(revenue)` is the previous row's value in the window order; for the first row it is `NULL`, and
      `revenue - NULL` is `NULL`, exactly as asked.
    * **Month text differs by dialect**: PostgreSQL `TO_CHAR(order_date, 'YYYY-MM')`, SQLite
      `strftime('%Y-%m', order_date)`. Both give text like `2026-03`, which sorts in time order.
    * Grouping by the month number alone (`EXTRACT(MONTH ...)`) would merge January 2025 with January 2026; one of
      the edge cases checks exactly that.
    * The task says "the previous row's month", so February 2026, which has no orders, is simply absent and March is
      compared with January. If a task wants missing months shown as 0, you first build a list of all months (a
      calendar table or a recursive CTE); see [dates and time series](../../databases/sql/16-Dates-and-Time-Series.md).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: same month in two years;
    * edge case: empty table;
    * edge case: one month only;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.04 s, SQLite 3.53 0.09 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: grouping by the month number only"
    
        PostgreSQL:
        
        ```sql
        WITH monthly AS (SELECT LPAD(EXTRACT(MONTH FROM order_date)::text, 2, '0') AS month, SUM(amount) AS revenue
            FROM orders GROUP BY 1)
        SELECT month, revenue, revenue - LAG(revenue) OVER (ORDER BY month) AS change FROM monthly ORDER BY month;
        ```
        
        SQLite:
        
        ```sql
        WITH monthly AS (SELECT strftime('%m', order_date) AS month, SUM(amount) AS revenue
            FROM orders GROUP BY 1)
        SELECT month, revenue, revenue - LAG(revenue) OVER (ORDER BY month) AS change FROM monthly ORDER BY month;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: LAG over the orders instead of the months"
    
        PostgreSQL:
        
        ```sql
        SELECT TO_CHAR(order_date, 'YYYY-MM') AS month, SUM(amount) AS revenue,
               SUM(amount) - LAG(amount) OVER (ORDER BY TO_CHAR(order_date, 'YYYY-MM')) AS change
        FROM orders GROUP BY TO_CHAR(order_date, 'YYYY-MM'), amount ORDER BY month;
        ```
        
        SQLite:
        
        ```sql
        SELECT strftime('%Y-%m', order_date) AS month, SUM(amount) AS revenue,
               SUM(amount) - LAG(amount) OVER (ORDER BY strftime('%Y-%m', order_date)) AS change
        FROM orders GROUP BY strftime('%Y-%m', order_date), amount ORDER BY month;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 18. Share of total revenue

**Level:** Medium · **Aim for:** 12 minutes

Each row is one sale. Write an SQL query that returns, for each category, `category`, `revenue` (its total
`amount`) and `pct`: its revenue as a **percentage of all revenue, rounded to 2 decimal places**. Sort by `pct`
from highest to lowest, then `category`. Amounts are positive.

**Tables**

```sql
CREATE TABLE category_sales (
    category VARCHAR(20) NOT NULL,
    amount   INTEGER NOT NULL
);
```

**Example data**

`category_sales`

| category | amount |
|---|---|
| books | 10 |
| games | 25 |
| books | 15 |
| music | 7 |
| tools | 3 |

**Your query should return**

| category | revenue | pct |
|---|---|---|
| books | 25 | 41.67 |
| games | 25 | 41.67 |
| music | 7 | 11.67 |
| tools | 3 | 5.00 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    SELECT category,
           SUM(amount) AS revenue,
           ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 2) AS pct
    FROM category_sales
    GROUP BY category
    ORDER BY pct DESC, category;
    ```
    
    **Why it works**
    
    * `SUM(SUM(amount)) OVER ()` is the grand total: the inner `SUM` is the per-category aggregate, and the window
      with an empty `OVER ()` adds those up across all groups. It saves a separate subquery.
    * **`100.0 *` first.** With whole numbers on both sides, `/` is integer division in PostgreSQL and SQLite
      (`25 / 60` is `0`). Multiplying by `100.0` makes the value a decimal before dividing.
    * `ROUND(..., 2)` works here in PostgreSQL because `100.0 * ...` is a `numeric` value. If you ever divide two
      `double precision` values, PostgreSQL has no two-argument `ROUND` for them; cast first: `ROUND(x::numeric, 2)`.
    * The percentages may not add up to exactly 100 after rounding (three thirds give 33.33 each); that is expected.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: one category is 100%;
    * edge case: thirds (rounding);
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.02 s, SQLite 3.53 0.04 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: integer division"
    
        ```sql
        SELECT category, SUM(amount) AS revenue,
               ROUND(100 * SUM(amount) / (SELECT SUM(amount) FROM category_sales), 2) AS pct
        FROM category_sales GROUP BY category ORDER BY pct DESC, category;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: percentage of the row, not of the total"
    
        ```sql
        SELECT category, SUM(amount) AS revenue,
               ROUND(100.0 * SUM(amount) / SUM(amount), 2) AS pct
        FROM category_sales GROUP BY category ORDER BY pct DESC, category;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 19. New users per day

**Level:** Medium · **Aim for:** 12 minutes

A user is **new** on the day of their first login. Write an SQL query that returns one row for every day on which
at least one user was new: `first_day`, `new_users` (how many users were new that day) and `total_users` (how
many distinct users had appeared by the end of that day). Sort by `first_day`.

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
| 1 | 2026-06-01 |
| 2 | 2026-06-01 |
| 1 | 2026-06-02 |
| 3 | 2026-06-03 |
| 1 | 2026-06-03 |
| 2 | 2026-06-03 |
| 4 | 2026-06-03 |

**Your query should return**

| first_day | new_users | total_users |
|---|---|---|
| 2026-06-01 | 2 | 2 |
| 2026-06-03 | 2 | 4 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH firsts AS (
        SELECT user_id, MIN(login_date) AS first_day
        FROM logins
        GROUP BY user_id
    )
    SELECT first_day,
           COUNT(*) AS new_users,
           SUM(COUNT(*)) OVER (ORDER BY first_day
                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS total_users
    FROM firsts
    GROUP BY first_day
    ORDER BY first_day;
    ```
    
    **Why it works**
    
    * Step 1: one row per user with their first day (`MIN` with `GROUP BY user_id`).
    * Step 2: count users per first day; a running `SUM` of those counts gives the total so far.
    * Counting `COUNT(DISTINCT user_id)` per `login_date` would count returning users again (user 1 on 2 June), and
      2 June would wrongly appear with no new user.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: same user many times on day one;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.04 s, SQLite 3.53 0.08 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: distinct users per day instead of new users"
    
        ```sql
        SELECT login_date AS first_day, COUNT(DISTINCT user_id) AS new_users,
               SUM(COUNT(DISTINCT user_id)) OVER (ORDER BY login_date) AS total_users
        FROM logins GROUP BY login_date ORDER BY first_day;
        ```
        
        Checked: this gives a wrong result on **sample**.



## D. Sequences, gaps and time

### 20. Missing invoice numbers

**Level:** Medium · **Aim for:** 12 minutes

Invoice numbers should have no gaps. Write an SQL query that returns every **run of missing numbers** between the
smallest and the largest existing invoice number: `gap_start` and `gap_end` (the first and last missing number of
the run; equal when only one number is missing). Sort by `gap_start`.

**Tables**

```sql
CREATE TABLE invoices (
    number INTEGER PRIMARY KEY
);
```

**Example data**

`invoices`

| number |
|---|
| 1 |
| 2 |
| 3 |
| 7 |
| 8 |
| 10 |
| 15 |

**Your query should return**

| gap_start | gap_end |
|---|---|
| 4 | 6 |
| 9 | 9 |
| 11 | 14 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH nexts AS (
        SELECT number,
               LEAD(number) OVER (ORDER BY number) AS next_number
        FROM invoices
    )
    SELECT number + 1      AS gap_start,
           next_number - 1 AS gap_end
    FROM nexts
    WHERE next_number > number + 1
    ORDER BY gap_start;
    ```
    
    **Why it works**
    
    * `LEAD(number)` puts the next existing number beside each number. If the next one is more than one higher, the
      numbers in between are missing: from `number + 1` to `next_number - 1`.
    * The last row's `LEAD` is `NULL`; `NULL > anything` is not true, so it is dropped with no extra code.
    * This is the "gaps" half of **gaps and islands**; the login-streak task in Mock test 1 is the "islands" half.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: no gaps;
    * edge case: single row;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.16 s, SQLite 3.53 0.11 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: only the first missing number of each gap"
    
        ```sql
        SELECT number + 1 AS gap_start, number + 1 AS gap_end FROM invoices
        WHERE number + 1 NOT IN (SELECT number FROM invoices) AND number < (SELECT MAX(number) FROM invoices)
        ORDER BY gap_start;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 21. Three hot readings in a row

**Level:** Medium · **Aim for:** 15 minutes

Each sensor numbers its readings; `(sensor_id, reading_no)` is unique, but numbers may skip (a lost reading is
simply absent). Write an SQL query that returns the `sensor_id` of every sensor that has **at least three
consecutive readings above 30**, where "consecutive" means next to each other in `reading_no` order among that
sensor's rows. Sort by `sensor_id`.

**Tables**

```sql
CREATE TABLE readings (
    sensor_id  VARCHAR(10) NOT NULL,
    reading_no INTEGER NOT NULL,
    temp       INTEGER NOT NULL
);
```

**Example data**

`readings`

| sensor_id | reading_no | temp |
|---|---|---|
| A | 1 | 31 |
| A | 2 | 35 |
| A | 3 | 29 |
| A | 4 | 40 |
| A | 5 | 33 |
| B | 1 | 31 |
| B | 2 | 32 |
| B | 5 | 33 |
| C | 1 | 50 |
| C | 2 | 50 |

**Your query should return**

| sensor_id |
|---|
| B |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH seq AS (
        SELECT sensor_id, temp,
               LAG(temp, 1) OVER (PARTITION BY sensor_id ORDER BY reading_no) AS prev1,
               LAG(temp, 2) OVER (PARTITION BY sensor_id ORDER BY reading_no) AS prev2
        FROM readings
    )
    SELECT DISTINCT sensor_id
    FROM seq
    WHERE temp > 30 AND prev1 > 30 AND prev2 > 30
    ORDER BY sensor_id;
    ```
    
    **Why it works**
    
    * `LAG(temp, 1)` and `LAG(temp, 2)` put the previous two readings beside each reading. A row whose own reading and
      both previous readings are above 30 ends a run of three. `DISTINCT` because a long run produces several such
      rows.
    * **Compute the `LAG` before you filter.** If you put `WHERE temp > 30` in the same `SELECT` as the window, the
      filter runs first and removes the cool readings, so readings that were *not* next to each other look
      consecutive (sensor A in the example).
    * Sensor B is a reminder that "consecutive" is defined by the order of the rows, not by the numbers: reading 5
      follows reading 2 because 3 and 4 are missing. If a task says gaps in numbering break a run, compare
      `reading_no` with `LAG(reading_no)` too.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: hot readings split by one cool one;
    * edge case: exactly 30 is not above 30;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.19 s, SQLite 3.53 0.15 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: filtering before LAG"
    
        ```sql
        WITH seq AS (SELECT sensor_id, temp,
            LAG(temp, 1) OVER (PARTITION BY sensor_id ORDER BY reading_no) AS prev1,
            LAG(temp, 2) OVER (PARTITION BY sensor_id ORDER BY reading_no) AS prev2
          FROM readings WHERE temp > 30)
        SELECT DISTINCT sensor_id FROM seq WHERE prev1 IS NOT NULL AND prev2 IS NOT NULL ORDER BY sensor_id;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: counting hot readings anywhere"
    
        ```sql
        SELECT sensor_id FROM readings WHERE temp > 30
        GROUP BY sensor_id HAVING COUNT(*) >= 3 ORDER BY sensor_id;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 22. Customers whose spending always went up

**Level:** Medium · **Aim for:** 15 minutes

A customer buys at most once a day. Write an SQL query that returns every customer with **at least two purchases**
where **each purchase was strictly larger than the one before** (in date order). Sort by `customer_id`.

**Tables**

```sql
CREATE TABLE purchases (
    customer_id INTEGER NOT NULL,
    bought_on   DATE NOT NULL,
    amount      INTEGER NOT NULL
);
```

**Example data**

`purchases`

| customer_id | bought_on | amount |
|---|---|---|
| 1 | 2026-01-01 | 10 |
| 1 | 2026-01-05 | 20 |
| 1 | 2026-01-09 | 30 |
| 2 | 2026-01-01 | 10 |
| 2 | 2026-01-02 | 10 |
| 3 | 2026-01-03 | 50 |
| 3 | 2026-01-01 | 40 |
| 4 | 2026-01-01 | 99 |

**Your query should return**

| customer_id |
|---|
| 1 |
| 3 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH steps AS (
        SELECT customer_id, amount,
               LAG(amount) OVER (PARTITION BY customer_id ORDER BY bought_on) AS prev_amount
        FROM purchases
    )
    SELECT customer_id
    FROM steps
    GROUP BY customer_id
    HAVING COUNT(*) >= 2
       AND SUM(CASE WHEN prev_amount IS NOT NULL AND amount <= prev_amount THEN 1 ELSE 0 END) = 0
    ORDER BY customer_id;
    ```
    
    **Why it works**
    
    * `LAG` pairs each purchase with the one before it. A customer qualifies when **no** step goes down or stays
      level: count the bad steps with `SUM(CASE ...)` and require zero.
    * "For every row, something must hold" is usually written as "the number of rows where it fails is 0".
    * The first purchase has no previous amount; the `prev_amount IS NOT NULL` keeps it from counting as a bad step.
      `HAVING COUNT(*) >= 2` removes customers with a single purchase (customer 4).
    * Comparing the first and last purchase only would accept customer 1 in the "dip" edge case (5 then 12).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: one purchase is not enough;
    * edge case: a dip in the middle;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.07 s, SQLite 3.53 0.13 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: first and last only"
    
        ```sql
        WITH x AS (SELECT customer_id, amount,
            FIRST_VALUE(amount) OVER (PARTITION BY customer_id ORDER BY bought_on) AS f,
            FIRST_VALUE(amount) OVER (PARTITION BY customer_id ORDER BY bought_on DESC) AS l,
            COUNT(*) OVER (PARTITION BY customer_id) AS n FROM purchases)
        SELECT DISTINCT customer_id FROM x WHERE n >= 2 AND l > f ORDER BY customer_id;
        ```
        
        Checked: this gives a wrong result on **edge: a dip in the middle**.
    
    ??? failure "A common wrong answer: >= allows equal amounts"
    
        ```sql
        WITH s AS (SELECT customer_id, amount, LAG(amount) OVER (PARTITION BY customer_id ORDER BY bought_on) AS p FROM purchases)
        SELECT customer_id FROM s GROUP BY customer_id
        HAVING COUNT(*) >= 2 AND SUM(CASE WHEN p IS NOT NULL AND amount < p THEN 1 ELSE 0 END) = 0 ORDER BY customer_id;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 23. Count sessions

**Level:** Medium to hard · **Aim for:** 20 minutes

A **session** is a run of one user's page views in which each view comes **at most 30 minutes** after the
previous one; a gap of more than 30 minutes starts a new session. A user may view two pages at the same second.
Write an SQL query that returns `user_id` and the number of `sessions` for every user in the table. Sort by
`user_id`.

**Tables**

```sql
CREATE TABLE page_views (
    user_id   INTEGER NOT NULL,
    viewed_at TIMESTAMP NOT NULL
);
```

**Example data**

`page_views`

| user_id | viewed_at |
|---|---|
| 1 | 2026-08-01 09:00:00 |
| 1 | 2026-08-01 09:20:00 |
| 1 | 2026-08-01 09:50:00 |
| 1 | 2026-08-01 10:20:01 |
| 2 | 2026-08-01 23:50:00 |
| 2 | 2026-08-02 00:10:00 |
| 3 | 2026-08-01 12:00:00 |

**Your query should return**

| user_id | sessions |
|---|---|
| 1 | 2 |
| 2 | 1 |
| 3 | 1 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**
    
    ```sql
    WITH gaps AS (
        SELECT user_id,
               EXTRACT(EPOCH FROM viewed_at
                       - LAG(viewed_at) OVER (PARTITION BY user_id ORDER BY viewed_at)) AS gap_seconds
        FROM page_views
    )
    SELECT user_id,
           SUM(CASE WHEN gap_seconds IS NULL OR gap_seconds > 1800 THEN 1 ELSE 0 END) AS sessions
    FROM gaps
    GROUP BY user_id
    ORDER BY user_id;
    ```
    
    **SQLite**
    
    ```sql
    WITH gaps AS (
        SELECT user_id,
               CAST(strftime('%s', viewed_at) AS INTEGER)
               - CAST(strftime('%s', LAG(viewed_at) OVER (PARTITION BY user_id ORDER BY viewed_at)) AS INTEGER)
                 AS gap_seconds
        FROM page_views
    )
    SELECT user_id,
           SUM(CASE WHEN gap_seconds IS NULL OR gap_seconds > 1800 THEN 1 ELSE 0 END) AS sessions
    FROM gaps
    GROUP BY user_id
    ORDER BY user_id;
    ```
    
    **Why it works**
    
    * **Sessionization**: a view starts a new session when it is the user's first view (`LAG` is `NULL`) or comes more
      than 1,800 seconds after the previous view. Count the starts.
    * `> 1800`, not `>= 1800`: the task says "at most 30 minutes" stays in the same session. Two edge cases check
      exactly 30:00 and 30:01.
    * **Seconds between two timestamps differ by dialect.** PostgreSQL: subtracting timestamps gives an `interval`,
      and `EXTRACT(EPOCH FROM interval)` turns it into seconds. SQLite: `strftime('%s', t)` gives the Unix time as
      text; cast it to an integer and subtract. Avoid `julianday` differences for exact second boundaries: they are
      floating-point fractions of a day.
    * A data-engineering version of the same idea assigns a session number to every view with a running
      `SUM(...) OVER (PARTITION BY user_id ORDER BY viewed_at)` of the start flags.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: exactly 30 minutes apart (same session);
    * edge case: 30 minutes and 1 second (new session);
    * edge case: same second twice;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.13 s, SQLite 3.53 0.26 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: '30 minutes or more' instead of 'more than 30'"
    
        PostgreSQL:
        
        ```sql
        WITH gaps AS (SELECT user_id, EXTRACT(EPOCH FROM viewed_at - LAG(viewed_at) OVER (PARTITION BY user_id ORDER BY viewed_at)) AS g FROM page_views)
        SELECT user_id, SUM(CASE WHEN g IS NULL OR g >= 1800 THEN 1 ELSE 0 END) AS sessions FROM gaps GROUP BY user_id ORDER BY user_id;
        ```
        
        SQLite:
        
        ```sql
        WITH gaps AS (SELECT user_id, CAST(strftime('%s', viewed_at) AS INTEGER) - CAST(strftime('%s', LAG(viewed_at) OVER (PARTITION BY user_id ORDER BY viewed_at)) AS INTEGER) AS g FROM page_views)
        SELECT user_id, SUM(CASE WHEN g IS NULL OR g >= 1800 THEN 1 ELSE 0 END) AS sessions FROM gaps GROUP BY user_id ORDER BY user_id;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: forgetting the first view of each user"
    
        PostgreSQL:
        
        ```sql
        WITH gaps AS (SELECT user_id, EXTRACT(EPOCH FROM viewed_at - LAG(viewed_at) OVER (PARTITION BY user_id ORDER BY viewed_at)) AS g FROM page_views)
        SELECT user_id, SUM(CASE WHEN g > 1800 THEN 1 ELSE 0 END) AS sessions FROM gaps GROUP BY user_id ORDER BY user_id;
        ```
        
        SQLite:
        
        ```sql
        WITH gaps AS (SELECT user_id, CAST(strftime('%s', viewed_at) AS INTEGER) - CAST(strftime('%s', LAG(viewed_at) OVER (PARTITION BY user_id ORDER BY viewed_at)) AS INTEGER) AS g FROM page_views)
        SELECT user_id, SUM(CASE WHEN g > 1800 THEN 1 ELSE 0 END) AS sessions FROM gaps GROUP BY user_id ORDER BY user_id;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 24. Seven-day retention

**Level:** Hard · **Aim for:** 20 minutes

A user is **retained** if they were active on at least one of the 7 days **after** their sign-up day (days 1 to 7;
activity on the sign-up day itself does not count). `activity` may hold several rows per user per day. Write an SQL
query that returns, for each sign-up date: `signup_date`, `signups` (users who signed up that day) and `retained`
(how many of them were retained). Sort by `signup_date`.

**Tables**

```sql
CREATE TABLE signups (
    user_id     INTEGER PRIMARY KEY,
    signup_date DATE NOT NULL
);
CREATE TABLE activity (
    user_id     INTEGER NOT NULL,
    active_date DATE NOT NULL
);
```

**Example data**

`signups`

| user_id | signup_date |
|---|---|
| 1 | 2026-03-01 |
| 2 | 2026-03-01 |
| 3 | 2026-03-01 |
| 4 | 2026-03-02 |

`activity`

| user_id | active_date |
|---|---|
| 1 | 2026-03-01 |
| 2 | 2026-03-03 |
| 2 | 2026-03-04 |
| 3 | 2026-03-09 |
| 4 | 2026-03-09 |

**Your query should return**

| signup_date | signups | retained |
|---|---|---|
| 2026-03-01 | 3 | 1 |
| 2026-03-02 | 1 | 1 |

??? success "Solution and explanation (open after you try)"

    **PostgreSQL**
    
    ```sql
    SELECT s.signup_date,
           COUNT(DISTINCT s.user_id) AS signups,
           COUNT(DISTINCT a.user_id) AS retained
    FROM signups s
    LEFT JOIN activity a
           ON a.user_id = s.user_id
          AND a.active_date BETWEEN s.signup_date + 1 AND s.signup_date + 7
    GROUP BY s.signup_date
    ORDER BY s.signup_date;
    ```
    
    **SQLite**
    
    ```sql
    SELECT s.signup_date,
           COUNT(DISTINCT s.user_id) AS signups,
           COUNT(DISTINCT a.user_id) AS retained
    FROM signups s
    LEFT JOIN activity a
           ON a.user_id = s.user_id
          AND a.active_date BETWEEN date(s.signup_date, '+1 day') AND date(s.signup_date, '+7 days')
    GROUP BY s.signup_date
    ORDER BY s.signup_date;
    ```
    
    **Why it works**
    
    * The date window goes **in the `ON` clause of the `LEFT JOIN`**, so a user with no qualifying activity still
      keeps one row (with `a.user_id` `NULL`) and is counted in `signups`. Put it in `WHERE` instead and those users
      vanish, so `signups` comes out too small.
    * `COUNT(DISTINCT ...)` on both columns, because a user active on several days in the window produces several
      joined rows. `COUNT(DISTINCT a.user_id)` ignores the `NULL`s of users who were not retained.
    * Dates: PostgreSQL `date + 1`; SQLite `date(d, '+1 day')`, which returns text in the same `YYYY-MM-DD` form
      that the stored dates use, so `BETWEEN` compares correctly. `BETWEEN` includes both ends (day 1 and day 7).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: active only on sign-up day;
    * edge case: active exactly on day 7 and day 8;
    * edge case: window crosses a leap day;
    * edge case: no activity table rows;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.03 s, SQLite 3.53 0.28 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: window in WHERE loses users who did not come back"
    
        PostgreSQL:
        
        ```sql
        SELECT s.signup_date, COUNT(DISTINCT s.user_id) AS signups, COUNT(DISTINCT a.user_id) AS retained
        FROM signups s LEFT JOIN activity a ON a.user_id = s.user_id
        WHERE a.active_date BETWEEN s.signup_date + 1 AND s.signup_date + 7
        GROUP BY s.signup_date ORDER BY s.signup_date;
        ```
        
        SQLite:
        
        ```sql
        SELECT s.signup_date, COUNT(DISTINCT s.user_id) AS signups, COUNT(DISTINCT a.user_id) AS retained
        FROM signups s LEFT JOIN activity a ON a.user_id = s.user_id
        WHERE a.active_date BETWEEN date(s.signup_date, '+1 day') AND date(s.signup_date, '+7 days')
        GROUP BY s.signup_date ORDER BY s.signup_date;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: COUNT without DISTINCT counts active days"
    
        PostgreSQL:
        
        ```sql
        SELECT s.signup_date, COUNT(DISTINCT s.user_id) AS signups, COUNT(a.user_id) AS retained
        FROM signups s LEFT JOIN activity a ON a.user_id = s.user_id AND a.active_date BETWEEN s.signup_date + 1 AND s.signup_date + 7
        GROUP BY s.signup_date ORDER BY s.signup_date;
        ```
        
        SQLite:
        
        ```sql
        SELECT s.signup_date, COUNT(DISTINCT s.user_id) AS signups, COUNT(a.user_id) AS retained
        FROM signups s LEFT JOIN activity a ON a.user_id = s.user_id AND a.active_date BETWEEN date(s.signup_date, '+1 day') AND date(s.signup_date, '+7 days')
        GROUP BY s.signup_date ORDER BY s.signup_date;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 25. Fill in missing meter readings

**Level:** Hard · **Aim for:** 20 minutes

A meter sends a reading every tick, but some readings were lost (`NULL`). Write an SQL query that returns every
`tick` with `reading` replaced, where it is `NULL`, by the **last non-NULL reading before it** (still `NULL` if
there is none yet). Sort by `tick`. Write a query that works in both PostgreSQL and SQLite.

**Tables**

```sql
CREATE TABLE meter (
    tick    INTEGER PRIMARY KEY,
    reading INTEGER
);
```

**Example data**

`meter`

| tick | reading |
|---|---|
| 1 | NULL |
| 2 | 40 |
| 3 | NULL |
| 4 | NULL |
| 5 | 42 |
| 6 | NULL |

**Your query should return**

| tick | reading |
|---|---|
| 1 | NULL |
| 2 | 40 |
| 3 | 40 |
| 4 | 40 |
| 5 | 42 |
| 6 | 42 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH grouped AS (
        SELECT tick, reading,
               COUNT(reading) OVER (ORDER BY tick
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS grp
        FROM meter
    )
    SELECT tick,
           MAX(reading) OVER (PARTITION BY grp) AS reading
    FROM grouped
    ORDER BY tick;
    ```
    
    **Why it works**
    
    * **The trick:** a running `COUNT(reading)` only goes up on rows that have a reading, because `COUNT` skips
      `NULL`s. So each real reading starts a new group number, and the `NULL` rows after it share that number.
    * Inside each group there is exactly one non-NULL reading (or none, for the rows before the first reading), so
      `MAX(reading)` over the group is that reading.
    * Some databases offer `LAST_VALUE(reading IGNORE NULLS)`; PostgreSQL 16 and SQLite do not, which is why this
      two-step form is worth knowing. A single `LAG(reading)` only fills one missing row, not a run of them.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: all NULL;
    * edge case: a reading of 0 is a real value;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.20 s, SQLite 3.53 0.21 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: LAG fills only one missing row"
    
        ```sql
        SELECT tick, COALESCE(reading, LAG(reading) OVER (ORDER BY tick)) AS reading FROM meter ORDER BY tick;
        ```
        
        Checked: this gives a wrong result on **sample**.



## E. Harder patterns

### 26. Median order value per customer

**Level:** Hard · **Aim for:** 20 minutes

Write an SQL query that returns each customer's **median** order amount: `customer_id` and `median_amount`. For
an odd number of orders the median is the middle amount; for an even number it is the average of the two middle
amounts. Sort by `customer_id`. Write a query that works in **both** PostgreSQL and SQLite.

**Tables**

```sql
CREATE TABLE order_values (
    customer_id INTEGER NOT NULL,
    amount      INTEGER NOT NULL
);
```

**Example data**

`order_values`

| customer_id | amount |
|---|---|
| 1 | 10 |
| 1 | 30 |
| 1 | 20 |
| 2 | 5 |
| 2 | 9 |
| 2 | 1 |
| 2 | 7 |
| 3 | 4 |

**Your query should return**

| customer_id | median_amount |
|---|---|
| 1 | 20 |
| 2 | 6 |
| 3 | 4 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH numbered AS (
        SELECT customer_id, amount,
               ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY amount) AS rn,
               COUNT(*)     OVER (PARTITION BY customer_id)                 AS cnt
        FROM order_values
    )
    SELECT customer_id, AVG(amount) AS median_amount
    FROM numbered
    WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)    -- integer division on purpose
    GROUP BY customer_id
    ORDER BY customer_id;
    ```
    
    **Why it works**
    
    * Number each customer's amounts in order and count them. The middle positions are `(cnt + 1) / 2` and
      `(cnt + 2) / 2` with **integer division**: for 4 rows that is 2 and 3, for 5 rows it is 3 and 3. Averaging the
      rows at those positions gives the median in both cases.
    * Here integer division is exactly what we want; in the percentage task it was the bug. Know which one you need.
    * PostgreSQL has a built-in: `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount)`. SQLite has no median
      function, which is why the task asks for the portable form.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: two orders;
    * edge case: repeated amounts;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.13 s, SQLite 3.53 0.21 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: AVG is the mean, not the median"
    
        ```sql
        SELECT customer_id, AVG(amount) AS median_amount FROM order_values
        GROUP BY customer_id ORDER BY customer_id;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: only one middle row for even counts"
    
        ```sql
        WITH n AS (SELECT customer_id, amount,
            ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY amount) AS rn,
            COUNT(*) OVER (PARTITION BY customer_id) AS cnt FROM order_values)
        SELECT customer_id, AVG(amount) AS median_amount FROM n WHERE rn = (cnt + 1) / 2
        GROUP BY customer_id ORDER BY customer_id;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 27. Price in effect on the day of each sale

**Level:** Hard · **Aim for:** 20 minutes

`prices` keeps the history of each product's price: a price applies from its `valid_from` date until the next
`valid_from` of the same product (`(product_id, valid_from)` is unique). Write an SQL query that returns, for
**every sale**, `sale_id` and the `price` in effect on its `sale_date` (`NULL` if the sale happened before the
product's first price). Sort by `sale_id`.

**Tables**

```sql
CREATE TABLE prices (
    product_id INTEGER NOT NULL,
    price      INTEGER NOT NULL,
    valid_from DATE NOT NULL
);
CREATE TABLE sales (
    id         INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    sale_date  DATE NOT NULL
);
```

**Example data**

`prices`

| product_id | price | valid_from |
|---|---|---|
| 1 | 10 | 2026-01-01 |
| 1 | 12 | 2026-02-01 |
| 2 | 7 | 2026-01-15 |

`sales`

| id | product_id | sale_date |
|---|---|---|
| 1 | 1 | 2026-01-31 |
| 2 | 1 | 2026-02-01 |
| 3 | 2 | 2026-01-10 |
| 4 | 2 | 2026-03-01 |
| 5 | 1 | 2026-06-30 |

**Your query should return**

| sale_id | price |
|---|---|
| 1 | 10 |
| 2 | 12 |
| 3 | NULL |
| 4 | 7 |
| 5 | 12 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH periods AS (
        SELECT product_id, price, valid_from,
               LEAD(valid_from) OVER (PARTITION BY product_id ORDER BY valid_from) AS valid_to
        FROM prices
    )
    SELECT s.id AS sale_id, p.price
    FROM sales s
    LEFT JOIN periods p
           ON p.product_id = s.product_id
          AND s.sale_date >= p.valid_from
          AND (p.valid_to IS NULL OR s.sale_date < p.valid_to)
    ORDER BY sale_id;
    ```
    
    **Why it works**
    
    * This is an **as-of join** (also called a point-in-time join), very common in data engineering with
      slowly changing data. First turn each price into a period: `LEAD(valid_from)` is the start of the next price,
      which is where this one stops. The last price has no end (`NULL`).
    * Then join each sale to the period that contains its date: on or after `valid_from`, and before `valid_to` (or
      no end). Half-open periods `[from, to)` never overlap, so each sale matches at most one price.
    * `LEFT JOIN` keeps sales with no price yet, as `NULL`.
    * A correlated subquery (`SELECT price FROM prices WHERE ... ORDER BY valid_from DESC LIMIT 1` for each sale) is
      also correct, but on SQLite without indexes it rescans `prices` for every sale; see the performance note in
      "Customers who never ordered".
    * Background: [data modelling](../../databases/sql/19-Data-Modelling.md).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: no prices at all;
    * edge case: sale on the day a price changes;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 100,000 rows: PostgreSQL 16 0.30 s, SQLite 3.53 0.25 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: latest price ever, not the price on the day"
    
        ```sql
        SELECT s.id AS sale_id, p.price FROM sales s
        LEFT JOIN prices p ON p.product_id = s.product_id
         AND p.valid_from = (SELECT MAX(valid_from) FROM prices x WHERE x.product_id = s.product_id)
        ORDER BY sale_id;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: <= at the end of the period matches two prices"
    
        ```sql
        WITH periods AS (SELECT product_id, price, valid_from,
            LEAD(valid_from) OVER (PARTITION BY product_id ORDER BY valid_from) AS valid_to FROM prices)
        SELECT s.id AS sale_id, p.price FROM sales s LEFT JOIN periods p ON p.product_id = s.product_id
         AND s.sale_date >= p.valid_from AND (p.valid_to IS NULL OR s.sale_date <= p.valid_to) ORDER BY sale_id;
        ```
        
        Checked: this gives a wrong result on **sample**.



### 28. Levels in the org chart

**Level:** Hard · **Aim for:** 15 minutes

The company has one head, whose `manager_id` is `NULL`; everyone else has a manager in the table, and there are no
loops. The head is at level 1, their direct reports at level 2, and so on. Write an SQL query that returns every
person's `name` and `level`. Sort by `level`, then `name`.

**Tables**

```sql
CREATE TABLE org (
    id         INTEGER PRIMARY KEY,
    name       VARCHAR(40) NOT NULL,
    manager_id INTEGER
);
```

**Example data**

`org`

| id | name | manager_id |
|---|---|---|
| 1 | Ana | NULL |
| 2 | Ben | 1 |
| 3 | Cy | 1 |
| 4 | Dee | 3 |
| 5 | Eli | 4 |
| 6 | Fay | 3 |

**Your query should return**

| name | level |
|---|---|
| Ana | 1 |
| Ben | 2 |
| Cy | 2 |
| Dee | 3 |
| Fay | 3 |
| Eli | 4 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH RECURSIVE chart AS (
        SELECT id, name, 1 AS level            -- start: the head
        FROM org
        WHERE manager_id IS NULL
        UNION ALL
        SELECT o.id, o.name, c.level + 1       -- step: people whose manager is already in chart
        FROM org o
        JOIN chart c ON o.manager_id = c.id
    )
    SELECT name, level
    FROM chart
    ORDER BY level, name;
    ```
    
    **Why it works**
    
    * A **recursive CTE** has two parts joined by `UNION ALL`: the starting rows (the head), and a step that joins the
      table to the rows found so far. The step repeats until it finds no new rows.
    * `WITH RECURSIVE` is the spelling both PostgreSQL and SQLite accept.
    * Self-joins can only go a fixed number of levels deep; recursion handles any depth (the edge case checks a chain
      of 30).
    * Each step is one join of the whole table with the newest level, so the cost grows with the **depth** of the
      tree. A company of 100,000 people that is 27 levels deep took under a second on both databases; an
      artificial chain thousands of levels deep took a minute on PostgreSQL without an index on `manager_id`. See [CTEs and recursive CTEs](../../databases/sql/11-CTEs-and-Recursive-CTEs.md).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: only the head;
    * edge case: a long chain;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 100,000 rows: PostgreSQL 16 0.81 s, SQLite 3.53 0.16 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: one self-join only reaches two levels"
    
        ```sql
        SELECT o.name, CASE WHEN o.manager_id IS NULL THEN 1 ELSE 2 END AS level
        FROM org o ORDER BY level, name;
        ```
        
        Checked: this gives a wrong result on **sample**.


