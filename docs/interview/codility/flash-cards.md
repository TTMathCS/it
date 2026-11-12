# Flash cards

Short questions for the last evening before the test. Read the question, say your answer out loud, then open
the box. The SQL and Python cards come first; the Databricks cards at the end are for a data engineering
interview rather than the Codility test.

Each SQL card has its query and the result it gave on **SQLite 3.54** against the small tables at the
[bottom of this page](#the-tables-the-sql-cards-use). The Python cards were run on **Python 3.9**. Nothing on
this page was run on PostgreSQL, so the PostgreSQL remarks are not tested. The Databricks answers come from the
[interview chapter](../../data-engineering/databricks/24-Interview.md) and the
[medallion chapter](../../data-engineering/databricks/07-Medallion-Architecture.md) of the Databricks course.

## Window functions

**1. Two people tie for top salary. What do ROW_NUMBER, RANK and DENSE_RANK give?**

??? success "Answer"
    ROW_NUMBER 1,2,3 (ties split by luck unless you add a tie-break), RANK 1,1,3 (skips), DENSE_RANK 1,1,2 (no gap).

    ```sql
    SELECT name, salary,
      ROW_NUMBER() OVER (ORDER BY salary DESC, name) AS rn,
      RANK()       OVER (ORDER BY salary DESC) AS rnk,
      DENSE_RANK() OVER (ORDER BY salary DESC) AS drnk
    FROM emp WHERE dept = 'Eng' ORDER BY rn
    ```

    Result:

    ```text
    name | salary | rn | rnk | drnk
    Ana | 120 | 1 | 1 | 1
    Bo | 120 | 2 | 1 | 1
    Cy | 100 | 3 | 3 | 2
    Di | 90 | 4 | 4 | 3
    ```

**2. Top 2 earners per department, ties included?**

??? success "Answer"
    Rank inside a CTE with PARTITION BY dept, then filter rnk <= 2 outside. Use RANK if ties should all come in, ROW_NUMBER for exactly 2.

    ```sql
    WITH r AS (
      SELECT dept, name, salary, RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS rnk
      FROM emp WHERE salary IS NOT NULL)
    SELECT dept, name, salary FROM r WHERE rnk <= 2 ORDER BY dept, salary DESC, name
    ```

    Result:

    ```text
    dept | name | salary
    Eng | Ana | 120
    Eng | Bo | 120
    Ops | Ed | 80
    Ops | Gus | 70
    ```

**3. Can I write WHERE RANK() OVER (...) = 1?**

??? success "Answer"
    No. Windows are worked out after WHERE, GROUP BY and HAVING, so they only exist in SELECT and ORDER BY. Wrap it in a CTE or subquery.

    ```sql
    SELECT name FROM emp WHERE RANK() OVER (ORDER BY salary DESC) = 1
    ```

    Result:

    ```text
    error: misuse of window function RANK()
    ```

**4. Running total by day?**

??? success "Answer"
    SUM(x) OVER (ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW). Say ROWS so each row adds exactly one row.

    ```sql
    SELECT day, amt,
      SUM(amt) OVER (ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS run
    FROM sales ORDER BY day, amt DESC
    ```

    Result:

    ```text
    day | amt | run
    2026-05-01 | 10 | 10
    2026-05-02 | 20 | 30
    2026-05-02 | 5 | 35
    2026-05-04 | 7 | 42
    ```

**5. SUM(x) OVER (ORDER BY day) with no frame: what goes wrong on a repeated day?**

??? success "Answer"
    The default frame is RANGE ... CURRENT ROW, so all rows of the same day are peers and all get the total up to the end of that day.

    ```sql
    SELECT day, amt, SUM(amt) OVER (ORDER BY day) AS run FROM sales ORDER BY day, amt DESC
    ```

    Result:

    ```text
    day | amt | run
    2026-05-01 | 10 | 10
    2026-05-02 | 20 | 35
    2026-05-02 | 5 | 35
    2026-05-04 | 7 | 42
    ```

**6. What does LAG return on the first row, and how do I change it?**

??? success "Answer"
    NULL. The third argument is the fallback: LAG(x, 1, 0). LEAD is the same looking forward.

    ```sql
    SELECT day, amt, LAG(amt) OVER (ORDER BY day, amt) AS prev,
      LAG(amt, 1, 0) OVER (ORDER BY day, amt) AS prev0,
      LEAD(amt) OVER (ORDER BY day, amt) AS nxt
    FROM sales ORDER BY day, amt
    ```

    Result:

    ```text
    day | amt | prev | prev0 | nxt
    2026-05-01 | 10 | NULL | 0 | 5
    2026-05-02 | 5 | 10 | 10 | 20
    2026-05-02 | 20 | 5 | 5 | 7
    2026-05-04 | 7 | 20 | 20 | NULL
    ```

**7. Show each row next to its department total without losing rows?**

??? success "Answer"
    SUM(salary) OVER (PARTITION BY dept). No ORDER BY inside, so the frame is the whole partition.

    ```sql
    SELECT name, dept, salary, SUM(salary) OVER (PARTITION BY dept) AS dept_total
    FROM emp ORDER BY dept, name
    ```

    Result:

    ```text
    name | dept | salary | dept_total
    Ana | Eng | 120 | 430
    Bo | Eng | 120 | 430
    Cy | Eng | 100 | 430
    Di | Eng | 90 | 430
    Ed | Ops | 80 | 150
    Fay | Ops | NULL | 150
    Gus | Ops | 70 | 150
    ```

**8. Share of department payroll as a percent with 1 decimal?**

??? success "Answer"
    ROUND(100.0 * salary / SUM(salary) OVER (PARTITION BY dept), 1). The 100.0 stops integer division.

    ```sql
    SELECT name, dept, ROUND(100.0 * salary / SUM(salary) OVER (PARTITION BY dept), 1) AS pct
    FROM emp WHERE salary IS NOT NULL ORDER BY dept, name
    ```

    Result:

    ```text
    name | dept | pct
    Ana | Eng | 27.9
    Bo | Eng | 27.9
    Cy | Eng | 23.3
    Di | Eng | 20.9
    Ed | Ops | 53.3
    Gus | Ops | 46.7
    ```

**9. 3-row moving average?**

??? success "Answer"
    AVG(x) OVER (ORDER BY d ROWS BETWEEN 2 PRECEDING AND CURRENT ROW). The first rows average fewer values.

    ```sql
    SELECT day, amt, ROUND(AVG(amt) OVER (ORDER BY day, amt ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS ma3
    FROM sales ORDER BY day, amt
    ```

    Result:

    ```text
    day | amt | ma3
    2026-05-01 | 10 | 10.0
    2026-05-02 | 5 | 7.5
    2026-05-02 | 20 | 11.67
    2026-05-04 | 7 | 10.67
    ```

**10. Why does LAST_VALUE(x) OVER (ORDER BY d) just give back the current row?**

??? success "Answer"
    The default frame ends at the current row (and its peers). Give the full frame, or use FIRST_VALUE with the order flipped.

    ```sql
    SELECT name, salary,
      LAST_VALUE(name) OVER (ORDER BY salary) AS lv_default,
      LAST_VALUE(name) OVER (ORDER BY salary ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS lv_full
    FROM emp WHERE dept = 'Ops' AND salary IS NOT NULL ORDER BY salary
    ```

    Result:

    ```text
    name | salary | lv_default | lv_full
    Gus | 70 | Gus | Ed
    Ed | 80 | Ed | Ed
    ```

## Joins and NULLs

**11. What is NULL = NULL? And NULL <> 1?**

??? success "Answer"
    Both are NULL (unknown), and WHERE keeps only true. Use IS NULL / IS NOT NULL.

    ```sql
    SELECT NULL = NULL AS eq, NULL <> 1 AS ne, NULL IS NULL AS is_null
    ```

    Result:

    ```text
    eq | ne | is_null
    NULL | NULL | 1
    ```

**12. Customers whose id is NOT IN (SELECT cust_id FROM orders). Why do I get nothing?**

??? success "Answer"
    orders.cust_id has a NULL, so x NOT IN (..., NULL) is never true. Use NOT EXISTS or LEFT JOIN ... IS NULL.

    ```sql
    SELECT 'not in' AS how, COUNT(*) FROM cust WHERE id NOT IN (SELECT cust_id FROM orders)
    UNION ALL
    SELECT 'not exists', COUNT(*) FROM cust c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.cust_id = c.id)
    ```

    Result:

    ```text
    how | COUNT(*)
    not in | 0
    not exists | 1
    ```

**13. LEFT JOIN orders, then WHERE o.status = 'shipped'. Where did Cal go?**

??? success "Answer"
    The WHERE throws away the NULL rows the LEFT JOIN made, so it acts like an INNER JOIN. Put the right-table filter in ON.

    ```sql
    SELECT 'in where' AS how, COUNT(*) FROM cust c LEFT JOIN orders o ON o.cust_id = c.id WHERE o.status = 'shipped'
    UNION ALL
    SELECT 'in on', COUNT(*) FROM cust c LEFT JOIN orders o ON o.cust_id = c.id AND o.status = 'shipped'
    ```

    Result:

    ```text
    how | COUNT(*)
    in where | 2
    in on | 3
    ```

**14. Orders per customer, zero included: COUNT(*) or COUNT(o.id)?**

??? success "Answer"
    COUNT(o.id). COUNT(*) counts the NULL-filled row from the LEFT JOIN as 1.

    ```sql
    SELECT c.name, COUNT(*) AS star, COUNT(o.id) AS real_count
    FROM cust c LEFT JOIN orders o ON o.cust_id = c.id GROUP BY c.id, c.name ORDER BY c.id
    ```

    Result:

    ```text
    name | star | real_count
    Ann | 2 | 2
    Ben | 1 | 1
    Cal | 1 | 0
    ```

**15. Rows in A with no match in B, fast on any database?**

??? success "Answer"
    LEFT JOIN B ON key WHERE B.key IS NULL (test a column that is never NULL in B, like its id). NOT EXISTS is the same idea.

    ```sql
    SELECT c.name FROM cust c LEFT JOIN orders o ON o.cust_id = c.id WHERE o.id IS NULL
    ```

    Result:

    ```text
    name
    Cal
    ```

**16. I join orders to items and SUM(amount). Why is it too big?**

??? success "Answer"
    Fan-out: an order with 2 items shows up twice. Sum each table at its own grain first, then join.

    ```sql
    SELECT 'joined' AS how, SUM(o.amount) FROM orders o JOIN items i ON i.order_id = o.id
    UNION ALL
    SELECT 'right', SUM(amount) FROM orders WHERE id IN (SELECT order_id FROM items)
    ```

    Result:

    ```text
    how | SUM(o.amount)
    joined | 130
    right | 80
    ```

**17. Does a NULL key ever match in a join?**

??? success "Answer"
    No, NULL = NULL is not true. Order 13 has cust_id NULL and drops out of an INNER JOIN.

    ```sql
    SELECT o.id, c.name FROM orders o JOIN cust c ON c.id = o.cust_id ORDER BY o.id
    ```

    Result:

    ```text
    id | name
    10 | Ann
    11 | Ann
    12 | Ben
    ```

**18. COALESCE vs NULLIF, and safe division?**

??? success "Answer"
    COALESCE(a, b) = first non-NULL. NULLIF(a, b) = NULL when a = b. x / NULLIF(y, 0) gives NULL instead of a divide-by-zero.

    ```sql
    SELECT name, COALESCE(city, 'none') AS city, NULLIF(city, 'Oslo') AS not_oslo, 10 / NULLIF(0, 0) AS safe FROM cust ORDER BY id
    ```

    Result:

    ```text
    name | city | not_oslo | safe
    Ann | Oslo | NULL | NULL
    Ben | none | NULL | NULL
    Cal | Rome | Rome | NULL
    ```

**19. Where do NULLs go in ORDER BY?**

??? success "Answer"
    SQLite and MySQL put them first in ASC; PostgreSQL and Oracle put them last. Write NULLS FIRST / NULLS LAST (SQLite since 3.30) when it matters.

    ```sql
    SELECT name, salary FROM emp WHERE dept = 'Ops' ORDER BY salary;
    SELECT name, salary FROM emp WHERE dept = 'Ops' ORDER BY salary NULLS LAST
    ```

    Result:

    ```text
    name | salary
    Fay | NULL
    Gus | 70
    Ed | 80
    name | salary
    Gus | 70
    Ed | 80
    Fay | NULL
    ```

**20. AVG(salary) vs SUM(salary)/COUNT(*) when one salary is NULL?**

??? success "Answer"
    AVG skips NULLs (divides by 2 here); SUM/COUNT(*) divides by every row. Use COALESCE(salary, 0) only if the task says NULL means 0.

    ```sql
    SELECT AVG(salary) AS avg, SUM(salary) * 1.0 / COUNT(*) AS per_row FROM emp WHERE dept = 'Ops'
    ```

    Result:

    ```text
    avg | per_row
    75.0 | 50.0
    ```

## GROUP BY rules

**21. WHERE or HAVING?**

??? success "Answer"
    WHERE filters rows before grouping, HAVING filters groups after. A condition on COUNT/SUM goes in HAVING.

    ```sql
    SELECT dept, COUNT(*) AS n FROM emp WHERE salary >= 80 GROUP BY dept HAVING COUNT(*) >= 2
    ```

    Result:

    ```text
    dept | n
    Eng | 4
    ```

**22. SELECT dept, name, MAX(salary) ... GROUP BY dept: does it run?**

??? success "Answer"
    Every SELECT column must be grouped or aggregated. PostgreSQL refuses this (not run here, no PostgreSQL on the Mac). SQLite runs it and, with a lone MAX, takes name from the max row; with a tie it picks one. Do not rely on it.

    ```sql
    SELECT dept, name, MAX(salary) FROM emp GROUP BY dept ORDER BY dept
    ```

    Result:

    ```text
    dept | name | MAX(salary)
    Eng | Ana | 120
    Ops | Ed | 80
    ```

**23. Count shipped and new orders in one pass?**

??? success "Answer"
    Conditional aggregation: SUM(CASE WHEN status = 'shipped' THEN 1 ELSE 0 END), one per column.

    ```sql
    SELECT SUM(CASE WHEN status = 'shipped' THEN 1 ELSE 0 END) AS shipped,
           SUM(CASE WHEN status = 'new' THEN 1 ELSE 0 END) AS new_ones FROM orders
    ```

    Result:

    ```text
    shipped | new_ones
    2 | 2
    ```

**24. How many different customers ordered?**

??? success "Answer"
    COUNT(DISTINCT cust_id). It skips NULLs too.

    ```sql
    SELECT COUNT(cust_id) AS rows_with_cust, COUNT(DISTINCT cust_id) AS customers FROM orders
    ```

    Result:

    ```text
    rows_with_cust | customers
    3 | 2
    ```

**25. Do NULLs make one group or many?**

??? success "Answer"
    One. GROUP BY (and DISTINCT) put all NULLs together, even though NULL = NULL is not true.

    ```sql
    SELECT cust_id, COUNT(*) FROM orders GROUP BY cust_id ORDER BY cust_id
    ```

    Result:

    ```text
    cust_id | COUNT(*)
    NULL | 1
    1 | 2
    2 | 1
    ```

**26. Average order as a ratio: why is SUM(a)/COUNT(*) a whole number?**

??? success "Answer"
    Both are integers, so it is integer division in SQLite and PostgreSQL. Multiply by 1.0 first. AVG itself is fine.

    ```sql
    SELECT SUM(amount) / COUNT(*) AS int_div, SUM(amount) * 1.0 / COUNT(*) AS real_div, 7 / 2 AS seven_halves FROM orders WHERE cust_id = 1 OR id = 13
    ```

    Result:

    ```text
    int_div | real_div | seven_halves
    36 | 36.666666666666664 | 3
    ```

## Dedupe patterns

**27. Keep only the latest event per user?**

??? success "Answer"
    ROW_NUMBER() OVER (PARTITION BY user ORDER BY ts DESC, id DESC) in a CTE, keep rn = 1. The id breaks ties on equal timestamps.

    ```sql
    WITH r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY ts DESC, id DESC) AS rn FROM events)
    SELECT user_id, ts, val FROM r WHERE rn = 1 ORDER BY user_id
    ```

    Result:

    ```text
    user_id | ts | val
    u1 | 2026-05-01 10:00 | b
    u2 | 2026-05-02 08:00 | c
    u3 | 2026-05-03 12:00 | d
    ```

**28. Which keys appear more than once?**

??? success "Answer"
    GROUP BY the key columns HAVING COUNT(*) > 1.

    ```sql
    SELECT user_id, ts, val, COUNT(*) AS n FROM events GROUP BY user_id, ts, val HAVING COUNT(*) > 1
    ```

    Result:

    ```text
    user_id | ts | val | n
    u2 | 2026-05-02 08:00 | c | 2
    ```

**29. Delete exact duplicates, keep one copy?**

??? success "Answer"
    DELETE WHERE id NOT IN (SELECT MIN(id) ... GROUP BY the columns that define a duplicate). Safe here because MIN(id) is never NULL.

    ```sql
    DELETE FROM events WHERE id NOT IN (SELECT MIN(id) FROM events GROUP BY user_id, ts, val);
    SELECT id, user_id, ts FROM events ORDER BY id
    ```

    Result:

    ```text
    id | user_id | ts
    1 | u1 | 2026-05-01 09:00
    2 | u1 | 2026-05-01 10:00
    3 | u2 | 2026-05-02 08:00
    5 | u3 | 2026-05-03 12:00
    ```

**30. SELECT DISTINCT a, b: distinct on a only?**

??? success "Answer"
    No, on the whole output row. DISTINCT a, b is the same as GROUP BY a, b. For "one row per a" use ROW_NUMBER.

    ```sql
    SELECT DISTINCT user_id, val FROM events ORDER BY user_id, val
    ```

    Result:

    ```text
    user_id | val
    u1 | a
    u1 | b
    u2 | c
    u3 | d
    ```

**31. UNION or UNION ALL?**

??? success "Answer"
    UNION removes duplicate rows (sort/hash, slower); UNION ALL keeps all. Use ALL unless you want dedupe.

    ```sql
    SELECT (SELECT COUNT(*) FROM (SELECT dept FROM emp UNION SELECT dept FROM emp)) AS u,
           (SELECT COUNT(*) FROM (SELECT dept FROM emp UNION ALL SELECT dept FROM emp)) AS u_all
    ```

    Result:

    ```text
    u | u_all
    2 | 14
    ```

**32. Friend pairs stored both ways (x,y) and (y,x). Count each pair once?**

??? success "Answer"
    Order the pair: SELECT DISTINCT MIN(a,b), MAX(a,b) in SQLite (LEAST/GREATEST in PostgreSQL), or WHERE a < b if both directions are always there.

    ```sql
    SELECT DISTINCT MIN(a, b) AS p, MAX(a, b) AS q FROM friends ORDER BY p, q
    ```

    Result:

    ```text
    p | q
    x | y
    x | z
    ```

## Dates

**33. First day of the month and the month as YYYY-MM in SQLite?**

??? success "Answer"
    date(d, 'start of month') and strftime('%Y-%m', d). PostgreSQL: date_trunc('month', d)::date and to_char(d, 'YYYY-MM').

    ```sql
    SELECT day, date(day, 'start of month') AS first, strftime('%Y-%m', day) AS ym FROM orders ORDER BY id
    ```

    Result:

    ```text
    day | first | ym
    2026-03-01 | 2026-03-01 | 2026-03
    2026-03-03 | 2026-03-01 | 2026-03
    2026-03-03 | 2026-03-01 | 2026-03
    2026-04-02 | 2026-04-01 | 2026-04
    ```

**34. Days between two dates?**

??? success "Answer"
    SQLite: julianday(d2) - julianday(d1) (a real, wrap in CAST AS INTEGER). PostgreSQL: d2 - d1 on date columns.

    ```sql
    SELECT julianday('2026-04-02') - julianday('2026-03-01') AS days, date('2026-03-01', '+7 days') AS plus7
    ```

    Result:

    ```text
    days | plus7
    32.0 | 2026-03-08
    ```

**35. Monthly revenue, sorted?**

??? success "Answer"
    GROUP BY strftime('%Y-%m', day). ISO text sorts the same way as dates.

    ```sql
    SELECT strftime('%Y-%m', day) AS ym, SUM(amount) AS revenue FROM orders GROUP BY ym ORDER BY ym
    ```

    Result:

    ```text
    ym | revenue
    2026-03 | 100
    2026-04 | 40
    ```

**36. Daily totals with the empty days shown as 0?**

??? success "Answer"
    Build the calendar with a recursive CTE, LEFT JOIN the facts to it, COALESCE(SUM(..), 0).

    ```sql
    WITH RECURSIVE d(day) AS (SELECT '2026-05-01' UNION ALL SELECT date(day, '+1 day') FROM d WHERE day < '2026-05-04')
    SELECT d.day, COALESCE(SUM(s.amt), 0) AS total FROM d LEFT JOIN sales s ON s.day = d.day GROUP BY d.day ORDER BY d.day
    ```

    Result:

    ```text
    day | total
    2026-05-01 | 10
    2026-05-02 | 25
    2026-05-03 | 0
    2026-05-04 | 7
    ```

**37. Longest run of days in a row (gaps and islands)?**

??? success "Answer"
    day minus ROW_NUMBER() is constant inside a streak. Group by user and that value; COUNT(*) is the streak length.

    ```sql
    WITH t AS (SELECT user_id, day, julianday(day) - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY day) AS grp FROM logins)
    SELECT user_id, MIN(day) AS start, MAX(day) AS stop, COUNT(*) AS len FROM t GROUP BY user_id, grp ORDER BY user_id, start
    ```

    Result:

    ```text
    user_id | start | stop | len
    u1 | 2026-05-01 | 2026-05-03 | 3
    u1 | 2026-05-05 | 2026-05-06 | 2
    u2 | 2026-05-02 | 2026-05-02 | 1
    ```

**38. Dates stored as text in SQLite: when does comparing them break?**

??? success "Answer"
    Only zero-padded YYYY-MM-DD compares right. '2026-1-15' sorts after '2026-02-01', and date() gives NULL for it.

    ```sql
    SELECT '2026-1-15' > '2026-02-01' AS wrong, '2026-01-15' > '2026-02-01' AS right, date('2026-1-15') AS parsed
    ```

    Result:

    ```text
    wrong | right | parsed
    1 | 0 | NULL
    ```

## Python dict, list and sorting

**39. Count how often each word appears?**

??? success "Answer"
    collections.Counter(words), or d[w] = d.get(w, 0) + 1.

    ```python
    from collections import Counter
    w = 'a b a c b a'.split()
    d = {}
    for x in w:
        d[x] = d.get(x, 0) + 1
    print(Counter(w), d)
    ```

    Result:

    ```text
    Counter({'a': 3, 'b': 2, 'c': 1}) {'a': 3, 'b': 2, 'c': 1}
    ```

**40. Group rows into lists by key?**

??? success "Answer"
    defaultdict(list) and append; no "if key not in d" needed.

    ```python
    from collections import defaultdict
    g = defaultdict(list)
    for dept, name in [('Eng', 'Ana'), ('Ops', 'Ed'), ('Eng', 'Bo')]:
        g[dept].append(name)
    print(dict(g))
    ```

    Result:

    ```text
    {'Eng': ['Ana', 'Bo'], 'Ops': ['Ed']}
    ```

**41. Sort by score high to low, then name A to Z?**

??? success "Answer"
    key=lambda r: (-r[1], r[0]). A text key cannot be negated: to sort it Z to A, sort twice instead (see the next card).

    ```python
    r = [('bo', 5), ('al', 7), ('cy', 5)]
    print(sorted(r, key=lambda t: (-t[1], t[0])))
    ```

    Result:

    ```text
    [('al', 7), ('bo', 5), ('cy', 5)]
    ```

**42. Is Python sort stable, and why care?**

??? success "Answer"
    Yes. Equal keys keep their order, so you can sort by the minor key first, then the major key.

    ```python
    r = [('bo', 'x'), ('al', 'y'), ('cy', 'x')]
    r.sort(key=lambda t: t[0])
    r.sort(key=lambda t: t[1], reverse=True)
    print(r)
    ```

    Result:

    ```text
    [('al', 'y'), ('bo', 'x'), ('cy', 'x')]
    ```

**43. Top 2 most common, or 2 largest numbers?**

??? success "Answer"
    Counter.most_common(2); heapq.nlargest(2, a) is O(n log k), cheaper than a full sort when k is small.

    ```python
    from collections import Counter
    import heapq
    print(Counter('abracadabra').most_common(2), heapq.nlargest(2, [5, 1, 9, 3]))
    ```

    Result:

    ```text
    [('a', 5), ('b', 2)] [9, 5]
    ```

**44. Does a dict keep insertion order?**

??? success "Answer"
    Yes, guaranteed since Python 3.7. Updating a key keeps its place; deleting and re-adding moves it to the end.

    ```python
    d = {'b': 1, 'a': 2}
    d['b'] = 9
    d['c'] = 3
    print(list(d))
    ```

    Result:

    ```text
    ['b', 'a', 'c']
    ```

**45. Queue in Python: list.pop(0)?**

??? success "Answer"
    No, pop(0) shifts everything, O(n). Use collections.deque: append and popleft are O(1).

    ```python
    from collections import deque
    q = deque([1, 2, 3])
    q.append(4)
    print(q.popleft(), list(q))
    ```

    Result:

    ```text
    1 [2, 3, 4]
    ```

**46. Remove duplicates but keep the first-seen order?**

??? success "Answer"
    list(dict.fromkeys(a)). set(a) loses the order.

    ```python
    a = [3, 1, 3, 2, 1]
    print(list(dict.fromkeys(a)))
    ```

    Result:

    ```text
    [3, 1, 2]
    ```

**47. grid = [[0] * 3] * 3; grid[0][0] = 1. What happened?**

??? success "Answer"
    All three rows are the same list, so every row changed. Use [[0] * 3 for _ in range(3)].

    ```python
    g = [[0] * 3] * 3
    g[0][0] = 1
    h = [[0] * 3 for _ in range(3)]
    h[0][0] = 1
    print(g, h)
    ```

    Result:

    ```text
    [[1, 0, 0], [1, 0, 0], [1, 0, 0]] [[1, 0, 0], [0, 0, 0], [0, 0, 0]]
    ```

**48. Find two numbers that add to a target in one pass?**

??? success "Answer"
    Keep a dict value -> index; for each x look up target - x before storing x. O(n) instead of O(n^2).

    ```python
    def two_sum(a, t):
        seen = {}
        for i, x in enumerate(a):
            if t - x in seen:
                return seen[t - x], i
            seen[x] = i
    print(two_sum([3, 8, 2, 7], 9))
    ```

    Result:

    ```text
    (2, 3)
    ```

## Complexity

**49. for x in a: if x in b (b a list, both 10^5 long). Fast enough?**

??? success "Answer"
    No: each "in list" is O(n), so O(n^2) = 10^10 steps. Make b a set first: O(n) total.

    ```python
    import time
    a = list(range(20000)); b = list(range(10000, 30000))
    t = time.time(); n1 = sum(1 for x in a if x in b); t1 = time.time() - t
    s = set(b); t = time.time(); n2 = sum(1 for x in a if x in s); t2 = time.time() - t
    print(n1, n2, 'list slower:', t1 > 10 * t2)
    ```

    Result:

    ```text
    10000 10000 list slower: True
    ```

**50. N up to 10^5: what can I afford, and what are sort and bisect?**

??? success "Answer"
    O(n) or O(n log n). sorted() is O(n log n); bisect on a sorted list is O(log n); dict/set lookups are O(1) on average. O(n^2) is too slow past about 10^4.

    ```python
    import bisect
    a = sorted([7, 1, 5, 3])
    print(a, bisect.bisect_left(a, 5), bisect.bisect_right(a, 5), bisect.bisect_left(a, 4))
    ```

    Result:

    ```text
    [1, 3, 5, 7] 2 3 2
    ```

## Databricks: Platform

**51. What is a lakehouse?**

??? success "Answer"
    Lake benefits (cheap object storage, open formats, any data, ML access) plus warehouse benefits (ACID, schemas,
    governance, fast SQL), on one copy of the data. On Databricks: Spark, Delta Lake, Unity Catalog.

**52. Control plane vs compute plane?**

??? success "Answer"
    Control plane: backend services and web app in the Databricks account. Compute plane: where data is processed; in
    your cloud account for classic compute, in a Databricks serverless plane for serverless.

**53. Where should scheduled production work run?**

??? success "Answer"
    Job compute or serverless, not an all-purpose cluster: non-interactive work costs much less on job compute.

**54. Which streaming triggers work on serverless notebooks and jobs?**

??? success "Answer"
    Only `AvailableNow` (recommended) and `Once`. A stream that runs all the time needs classic compute or a pipeline.

**55. Standard vs dedicated access mode (and old names)?**

??? success "Answer"
    Standard (formerly shared): multi-user, users isolated by Lakeguard; the recommended default. Dedicated (formerly
    single user): one user or group; needed for ML runtime, GPUs, spark-submit.

**56. What is Photon and when does it not help?**

??? success "Answer"
    C++ vectorized engine; Catalyst still plans, Photon executes, falls back to Spark for what it lacks. Little gain for
    queries under about two seconds; no stateful streaming; does not fix a Python UDF, skew or tiny files.

**57. Managed vs external table: what happens on DROP?**

??? success "Answer"
    Managed (default, recommended): UC manages the files; `UNDROP` works for 7 days, then files are purged. External:
    only metadata is removed, files stay.

**58. What does predictive optimization do?**

??? success "Answer"
    Runs `OPTIMIZE`, `VACUUM` and `ANALYZE` on UC managed tables when worthwhile; on by default, serverless, recommended
    for all managed tables.

**59. Old names: Lakeflow pipelines, Lakeflow Jobs, AUTO CDC, OpenSharing, disk cache?**

??? success "Answer"
    Delta Live Tables (`import dlt`), Databricks Jobs (Workflows menu), `APPLY CHANGES`, Delta Sharing, Delta cache.
    Say both names once.

## Databricks: Spark

**60. Transformation vs action?**

??? success "Answer"
    Transformations only add to the plan; actions (`count`, `collect`, `show`, a write) run jobs. An error in a
    transformation shows up only when an action runs.

**61. Narrow vs wide, and how do you see a shuffle?**

??? success "Answer"
    Narrow: one input partition per output partition (`filter`, `select`). Wide: rows with the same key must meet
    (`groupBy`, `join`, `distinct`, `repartition`). A shuffle is an `Exchange` node in the plan.

**62. Job, stage, task?**

??? success "Answer"
    Job: started by one action. Stage: a set of tasks, a new one at each shuffle. Task: one partition's work on one
    executor.

**63. Three partition numbers to know?**

??? success "Answer"
    `maxPartitionBytes` 128 MB on read, `shuffle.partitions` 200 after a shuffle, AQE advisory size 64 MB on Databricks.

**64. `repartition` vs `coalesce`?**

??? success "Answer"
    `repartition` always shuffles and can go up or down. `coalesce` only goes down, without a shuffle. `coalesce(1)`
    before a write can make the whole upstream run on one node.

**65. When does Spark pick a broadcast hash join?**

??? success "Answer"
    When a side is under the threshold (10 MB in open-source Spark; AQE on Databricks 30 MB) or with a `BROADCAST`
    hint. The big side is not shuffled. Two big tables: sort-merge join.

**66. A small dimension is not broadcast. Why?**

??? success "Answer"
    Stale or missing statistics overestimate it; join type cannot broadcast that side (left side of `LEFT OUTER`); AQE
    refuses when most partitions are empty. Fix: `ANALYZE TABLE` or a hint.

**67. What does AQE do, and what can it not do?**

??? success "Answer"
    Switches to broadcast joins, coalesces small partitions, splits skewed partitions, propagates empty relations. Not
    for streaming, no join reordering, no skew handling in broadcast joins.

**68. When does AQE call a partition skewed?**

??? success "Answer"
    Larger than 5 times the median and larger than 256 MB; only in sort-merge and shuffle hash joins.

**69. Skew fixes in order?**

??? success "Answer"
    AQE skew handling, broadcast the small side, handle the hot key (or NULL keys) separately, salt the key.

**70. `cache()` vs disk cache?**

??? success "Answer"
    `cache()`: you call it, lazy, in memory or disk, release with `unpersist()`. Disk cache: automatic SSD copy of
    Parquet/Delta files, never stale; recommended for repeated reads.

**71. Partition pruning vs data skipping?**

??? success "Answer"
    Pruning skips whole partition directories. Skipping uses per-file min/max stats in the log, by default for the
    first 32 columns.

## Databricks: Delta Lake

**72. How does the transaction log work?**

??? success "Answer"
    `_delta_log` holds one JSON commit per version (20-digit names) listing actions; a Parquet checkpoint replays all
    actions up to a version. Files from a failed job are never listed, so nobody sees them.

**73. How does Delta give ACID?**

??? success "Answer"
    Atomic log commit; optimistic concurrency (validate before commit, fail on conflict); snapshot isolation for reads,
    WriteSerializable for writes; durable object storage. No locks.

**74. Two jobs write the same table at once?**

??? success "Answer"
    Blind appends do not conflict. Two `MERGE`s, or `UPDATE` plus `DELETE` on the same rows, can: the later one fails
    (e.g. `ConcurrentAppendException`). Fix: disjoint predicates in `ON`, serialize, retry, row-level concurrency.

**75. What limits time travel?**

??? success "Answer"
    `delta.logRetentionDuration` (30 days) and `delta.deletedFileRetentionDuration` (7 days, what `VACUUM` uses). You
    need both the log and the data files. Not a backup.

**76. `RESTORE` vs a time travel query?**

??? success "Answer"
    A query only reads an old version. `RESTORE` commits a new version that brings the old files back; history stays.
    All or nothing for the table.

**77. `VACUUM` risks?**

??? success "Answer"
    Deletes unreferenced files older than 7 days; kills time travel to those versions; too short a retention can break
    a running writer (safety check blocks it). Keep checkpoints in a folder starting with `_`.

**78. What does `OPTIMIZE` do?**

??? success "Answer"
    Compacts small files into bigger ones (and clusters by liquid keys). Same data before and after; old files stay
    until `VACUUM`.

**79. Partitioning, Z-order or liquid clustering?**

??? success "Answer"
    Liquid clustering for all new tables: up to 4 keys, change keys without a rewrite, `CLUSTER BY AUTO` on managed
    tables. Partition only tables over 1 TB, at least 1 GB per partition.

**80. Deletion vectors?**

??? success "Answer"
    `DELETE`/`UPDATE`/`MERGE` mark rows removed instead of rewriting files. Physically removed by `OPTIMIZE`,
    `REORG ... APPLY (PURGE)` or auto compaction. For GDPR: `REORG ... PURGE`, then `VACUUM`.

**81. Change Data Feed?**

??? success "Answer"
    Row changes with `_change_type` (`insert`, `update_preimage`, `update_postimage`, `delete`), `_commit_version`,
    `_commit_timestamp`. Read with `table_changes` or `readChangeFeed`. Stream from it when the table gets updates.

**82. Schema enforcement vs evolution?**

??? success "Answer"
    Enforcement (default) rejects unknown columns and bad types. Evolution is opt-in per write: `mergeSchema`,
    `MERGE WITH SCHEMA EVOLUTION`. Any schema change stops streams reading the table.

**83. `MERGE` fails with "multiple source rows matched". Fix?**

??? success "Answer"
    The source has two rows for one key. Deduplicate the source first (`QUALIFY row_number() ... = 1`). `MERGE` only
    dedups against the target; into an empty target both copies are inserted with no error.

## Databricks: Medallion

**84. The three layers in one line each?**

??? success "Answer"
    Bronze: raw, appended, plus ingest metadata (rule: lose nothing). Silver: validated, typed, deduplicated, joined
    (trust every row). Gold: business models and aggregates (answer the question). A best practice, not a requirement;
    also called multi-hop.

**85. Why strings or `VARIANT` in bronze?**

??? success "Answer"
    So a schema change or a bad value never drops data; typing at bronze turned `12.O0` into NULL and lost the text.
    Add `_metadata.file_name` and a load time.

**86. Why keep bronze if the source keeps its data, and why not ingest straight into silver?**

??? success "Answer"
    Sources cannot be trusted to replay (Kafka retention, lifecycle rules, overwritten rows). Direct-to-silver brings
    failures from schema changes and corrupt records, and leaves nothing to replay from.

**87. How do layers map to Unity Catalog?**

??? success "Answer"
    A catalog per environment (or environment and domain), schemas `bronze`, `silver`, `gold` inside. Analysts get
    `SELECT` on gold (maybe silver), only service principals write production. Docs example: `ops.bronze/silver/gold`.

**88. Drop, fail or quarantine a bad row?**

??? success "Answer"
    Fail when the whole batch is wrong; drop when nobody will fix it; quarantine (side table with the reason) for real
    data with a fixable problem, usually. Count bad rows and alert.

**89. How do you make every hop safe to rerun?**

??? success "Answer"
    Bronze: ingestion checkpoint loads each file once. Silver: dedup the batch, `MERGE` on the key with a newer-wins
    guard (`WHEN MATCHED AND s.updated_at > t.updated_at`). Gold: replace a range (`REPLACE WHERE`), never append
    totals. Prove it with zero inserted and updated in `DESCRIBE HISTORY`.

## The tables the SQL cards use

Paste these into SQLite to run any card yourself.

```sql
CREATE TABLE emp(id INT, name TEXT, dept TEXT, salary INT);
INSERT INTO emp VALUES (1,'Ana','Eng',120),(2,'Bo','Eng',120),(3,'Cy','Eng',100),(4,'Di','Eng',90),
 (5,'Ed','Ops',80),(6,'Fay','Ops',NULL),(7,'Gus','Ops',70);
CREATE TABLE cust(id INT, name TEXT, city TEXT);
INSERT INTO cust VALUES (1,'Ann','Oslo'),(2,'Ben',NULL),(3,'Cal','Rome');
CREATE TABLE orders(id INT, cust_id INT, status TEXT, amount INT, day TEXT);
INSERT INTO orders VALUES (10,1,'shipped',50,'2026-03-01'),(11,1,'new',20,'2026-03-03'),
 (12,2,'shipped',30,'2026-03-03'),(13,NULL,'new',40,'2026-04-02');
CREATE TABLE items(order_id INT, item TEXT);
INSERT INTO items VALUES (10,'pen'),(10,'cup'),(12,'pad');
CREATE TABLE events(id INT, user_id TEXT, ts TEXT, val TEXT);
INSERT INTO events VALUES (1,'u1','2026-05-01 09:00','a'),(2,'u1','2026-05-01 10:00','b'),
 (3,'u2','2026-05-02 08:00','c'),(4,'u2','2026-05-02 08:00','c'),(5,'u3','2026-05-03 12:00','d');
CREATE TABLE logins(user_id TEXT, day TEXT);
INSERT INTO logins VALUES ('u1','2026-05-01'),('u1','2026-05-02'),('u1','2026-05-03'),
 ('u1','2026-05-05'),('u1','2026-05-06'),('u2','2026-05-02');
CREATE TABLE sales(day TEXT, amt INT);
INSERT INTO sales VALUES ('2026-05-01',10),('2026-05-02',20),('2026-05-02',5),('2026-05-04',7);
CREATE TABLE friends(a TEXT, b TEXT);
INSERT INTO friends VALUES ('x','y'),('y','x'),('x','z');
```
