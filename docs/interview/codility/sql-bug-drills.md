# Find the bug: 20 SQL drills

Each drill gives a task, its tables and a query that looks right but is wrong. Find the bug, write the fix, then open the answer. Most drills match a row of [the 15 most common mistakes](common-mistakes.md).

Every wrong and fixed query was run on PostgreSQL 16 and SQLite 3.54 and gave the same rows on both, except where a drill says otherwise: in drills 10 and 13 PostgreSQL refuses the wrong query with an error (SQLite runs it and gives a misleading answer), and in drill 6 the wrong query's row depends on the database.

## 1. NOT IN with a NULL (mistake #4)

Task: List the customers who never placed an order.

```sql
CREATE TABLE customers (id INT, name TEXT);
INSERT INTO customers VALUES (1,'Ana'),(2,'Ben'),(3,'Cy');
CREATE TABLE orders (id INT, customer_id INT);
INSERT INTO orders VALUES (10,1),(11,NULL);
```

Wrong query:

```sql
SELECT name FROM customers
WHERE id NOT IN (SELECT customer_id FROM orders);
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    (no rows)
    ```

    What goes wrong: One order has no customer. `x NOT IN (1, NULL)` is never true, so nobody comes back.

    Fixed:

    ```sql
    SELECT name FROM customers
    WHERE id NOT IN (SELECT customer_id FROM orders WHERE customer_id IS NOT NULL)
    ORDER BY name;
    ```

    ```text
    name
    ----
    Ben
    Cy
    ```


## 2. COUNT(*) after a LEFT JOIN (mistake #2)

Task: Number of orders per customer, 0 for those with none.

```sql
CREATE TABLE customers (id INT, name TEXT);
INSERT INTO customers VALUES (1,'Ana'),(2,'Ben');
CREATE TABLE orders (id INT, customer_id INT);
INSERT INTO orders VALUES (10,1),(11,1);
```

Wrong query:

```sql
SELECT c.name, COUNT(*) AS n
FROM customers c LEFT JOIN orders o ON o.customer_id = c.id
GROUP BY c.id, c.name ORDER BY c.name;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    name  n
    ----  -
    Ana   2
    Ben   1
    ```

    What goes wrong: Ben gets 1: `COUNT(*)` counts the empty row the LEFT JOIN made for him.

    Fixed:

    ```sql
    SELECT c.name, COUNT(o.id) AS n
    FROM customers c LEFT JOIN orders o ON o.customer_id = c.id
    GROUP BY c.id, c.name ORDER BY c.name;
    ```

    ```text
    name  n
    ----  -
    Ana   2
    Ben   0
    ```


## 3. SUM of nothing (mistake #3)

Task: Total spent per customer, 0 for those with no orders.

```sql
CREATE TABLE customers (id INT, name TEXT);
INSERT INTO customers VALUES (1,'Ana'),(2,'Ben');
CREATE TABLE orders (customer_id INT, amount INT);
INSERT INTO orders VALUES (1,30),(1,20);
```

Wrong query:

```sql
SELECT c.name, SUM(o.amount) AS total
FROM customers c LEFT JOIN orders o ON o.customer_id = c.id
GROUP BY c.id, c.name ORDER BY c.name;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    name  total
    ----  -----
    Ana      50
    Ben
    ```

    What goes wrong: Ben's total is empty (NULL), not 0.

    Fixed:

    ```sql
    SELECT c.name, COALESCE(SUM(o.amount), 0) AS total
    FROM customers c LEFT JOIN orders o ON o.customer_id = c.id
    GROUP BY c.id, c.name ORDER BY c.name;
    ```

    ```text
    name  total
    ----  -----
    Ana      50
    Ben       0
    ```


## 4. WHERE on the right table of a LEFT JOIN (mistake #1)

Task: Every customer with the number of orders they placed in 2026, 0 if none.

```sql
CREATE TABLE customers (id INT, name TEXT);
INSERT INTO customers VALUES (1,'Ana'),(2,'Ben'),(3,'Cy');
CREATE TABLE orders (id INT, customer_id INT, day TEXT);
INSERT INTO orders VALUES (10,1,'2026-02-01'),(11,2,'2025-12-30');
```

Wrong query:

```sql
SELECT c.name, COUNT(o.id) AS n
FROM customers c LEFT JOIN orders o ON o.customer_id = c.id
WHERE o.day >= '2026-01-01'
GROUP BY c.id, c.name ORDER BY c.name;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    name  n
    ----  -
    Ana   1
    ```

    What goes wrong: Only Ana: the WHERE throws away Ben's 2025 row and Cy's empty row, so the LEFT JOIN acts like an inner join.

    Fixed:

    ```sql
    SELECT c.name, COUNT(o.id) AS n
    FROM customers c LEFT JOIN orders o
      ON o.customer_id = c.id AND o.day >= '2026-01-01'
    GROUP BY c.id, c.name ORDER BY c.name;
    ```

    ```text
    name  n
    ----  -
    Ana   1
    Ben   0
    Cy    0
    ```


## 5. Inner JOIN drops rows (mistake #1)

Task: Every department with its head count, 0 for an empty one.

```sql
CREATE TABLE depts (id INT, name TEXT);
INSERT INTO depts VALUES (1,'Ops'),(2,'Lab');
CREATE TABLE staff (id INT, dept_id INT);
INSERT INTO staff VALUES (1,1),(2,1);
```

Wrong query:

```sql
SELECT d.name, COUNT(s.id) AS n
FROM depts d JOIN staff s ON s.dept_id = d.id
GROUP BY d.id, d.name ORDER BY d.name;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    name  n
    ----  -
    Ops   2
    ```

    What goes wrong: Lab is missing: an inner join keeps only departments that have staff.

    Fixed:

    ```sql
    SELECT d.name, COUNT(s.id) AS n
    FROM depts d LEFT JOIN staff s ON s.dept_id = d.id
    GROUP BY d.id, d.name ORDER BY d.name;
    ```

    ```text
    name  n
    ----  -
    Lab   0
    Ops   2
    ```


## 6. Missing tie-break (mistake #5)

Task: The top seller; on a tie, the name first in A-Z.

```sql
CREATE TABLE sales (name TEXT, units INT);
INSERT INTO sales VALUES ('Zed',9),('Amy',9),('Bo',4);
```

Wrong query:

```sql
SELECT name FROM sales ORDER BY units DESC LIMIT 1;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    name
    ----
    Zed
    ```

    What goes wrong: Zed and Amy tie on 9. With no second key the row that comes back is whichever the engine meets first (here Zed).

    Fixed:

    ```sql
    SELECT name FROM sales ORDER BY units DESC, name LIMIT 1;
    ```

    ```text
    name
    ----
    Amy
    ```


## 7. ROW_NUMBER when ties must stay (mistake #6)

Task: The best-paid person in each team, all of them on a tie.

```sql
CREATE TABLE pay (team TEXT, name TEXT, salary INT);
INSERT INTO pay VALUES ('A','Ann',90),('A','Al',90),('A','Ari',70),('B','Bea',80);
```

Wrong query:

```sql
SELECT team, name FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY team ORDER BY salary DESC) AS r FROM pay)
WHERE r = 1 ORDER BY team, name;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    team  name
    ----  ----
    A     Ann
    B     Bea
    ```

    What goes wrong: Team A shows only one of Ann and Al: ROW_NUMBER never gives two rows the same number.

    Fixed:

    ```sql
    SELECT team, name FROM (
      SELECT *, RANK() OVER (PARTITION BY team ORDER BY salary DESC) AS r FROM pay)
    WHERE r = 1 ORDER BY team, name;
    ```

    ```text
    team  name
    ----  ----
    A     Al
    A     Ann
    B     Bea
    ```


## 8. Integer division (mistake #7)

Task: Share of orders that were late, as a fraction.

```sql
CREATE TABLE deliveries (id INT, late INT);
INSERT INTO deliveries VALUES (1,1),(2,0),(3,0),(4,1),(5,1);
```

Wrong query:

```sql
SELECT SUM(late) / COUNT(*) AS rate FROM deliveries;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    rate
    ----
       0
    ```

    What goes wrong: 3 / 5 on two integers is 0.

    Fixed:

    ```sql
    SELECT ROUND(SUM(late) * 1.0 / COUNT(*), 2) AS rate FROM deliveries;
    ```

    ```text
    rate
    ----
     0.6
    ```


## 9. AVG skips NULLs (mistake #3)

Task: Average test score per student, a missed test (NULL) counting as 0.

```sql
CREATE TABLE scores (student TEXT, test INT, score INT);
INSERT INTO scores VALUES ('Ana',1,80),('Ana',2,NULL),('Ben',1,60),('Ben',2,70);
```

Wrong query:

```sql
SELECT student, AVG(score) AS avg FROM scores GROUP BY student ORDER BY student;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    student  avg
    -------  ----
    Ana      80.0
    Ben      65.0
    ```

    What goes wrong: Ana gets 80: AVG leaves the NULL out and divides by 1, not 2.

    Fixed:

    ```sql
    SELECT student, AVG(COALESCE(score, 0)) AS avg FROM scores GROUP BY student ORDER BY student;
    ```

    ```text
    student  avg
    -------  ----
    Ana      40.0
    Ben      65.0
    ```


## 10. GROUP BY missing a column

Task: Total sales per region and year.

```sql
CREATE TABLE sales (region TEXT, yr INT, amount INT);
INSERT INTO sales VALUES ('East',2025,10),('East',2026,5),('West',2026,7);
```

Wrong query:

```sql
SELECT region, yr, SUM(amount) AS total
FROM sales GROUP BY region ORDER BY region;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    region   yr   total
    ------  ----  -----
    East    2025     15
    West    2026      7
    ```

    What goes wrong: East's two years are added into one row and `yr` shows just one of them. SQLite allows it; PostgreSQL refuses it.

    Fixed:

    ```sql
    SELECT region, yr, SUM(amount) AS total
    FROM sales GROUP BY region, yr ORDER BY region, yr;
    ```

    ```text
    region   yr   total
    ------  ----  -----
    East    2025     10
    East    2026      5
    West    2026      7
    ```


## 11. BETWEEN with timestamps

Task: Number of logins on 31 March 2026.

```sql
CREATE TABLE logins (user_id INT, at TEXT);
INSERT INTO logins VALUES (1,'2026-03-31 00:00:00'),(2,'2026-03-31 18:45:10'),(3,'2026-04-01 00:00:00');
```

Wrong query:

```sql
SELECT COUNT(*) AS n FROM logins
WHERE at BETWEEN '2026-03-31' AND '2026-03-31';
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    n
    -
    0
    ```

    What goes wrong: 0. As text, '2026-03-31 00:00:00' is bigger than '2026-03-31', so nothing is between the two ends. With `BETWEEN '2026-03-31' AND '2026-04-01'` you would get 3, the midnight of 1 April included.

    Fixed:

    ```sql
    SELECT COUNT(*) AS n FROM logins
    WHERE at >= '2026-03-31' AND at < '2026-04-01';
    ```

    ```text
    n
    -
    2
    ```


## 12. HAVING vs WHERE

Task: Customers whose orders add up to more than 100.

```sql
CREATE TABLE orders (customer TEXT, amount INT);
INSERT INTO orders VALUES ('Ana',60),('Ana',70),('Ben',150),('Cy',40);
```

Wrong query:

```sql
SELECT customer, SUM(amount) AS total
FROM orders WHERE amount > 100
GROUP BY customer ORDER BY customer;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    customer  total
    --------  -----
    Ben         150
    ```

    What goes wrong: Ana is missing: WHERE tests each order before adding, and none of hers is over 100 by itself.

    Fixed:

    ```sql
    SELECT customer, SUM(amount) AS total
    FROM orders GROUP BY customer
    HAVING SUM(amount) > 100 ORDER BY customer;
    ```

    ```text
    customer  total
    --------  -----
    Ana         130
    Ben         150
    ```


## 13. HAVING used where WHERE was meant

Task: Number of paid orders per customer, for customers with at least one.

```sql
CREATE TABLE orders (customer TEXT, status TEXT);
INSERT INTO orders VALUES ('Ana','paid'),('Ana','open'),('Ben','open'),('Ben','paid'),('Ben','paid');
```

Wrong query:

```sql
SELECT customer, COUNT(*) AS n
FROM orders GROUP BY customer
HAVING status = 'paid' ORDER BY customer;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    customer  n
    --------  -
    Ana       2
    ```

    What goes wrong: The counts include open orders, and `status` in HAVING comes from any one row of the group (here Ben dropped out because his picked row was open). PostgreSQL refuses it.

    Fixed:

    ```sql
    SELECT customer, COUNT(*) AS n
    FROM orders WHERE status = 'paid'
    GROUP BY customer ORDER BY customer;
    ```

    ```text
    customer  n
    --------  -
    Ana       1
    Ben       2
    ```


## 14. Counting days without DISTINCT (mistake #8)

Task: Number of different days each user was active.

```sql
CREATE TABLE visits (user_id INT, day TEXT);
INSERT INTO visits VALUES (1,'2026-05-01'),(1,'2026-05-01'),(1,'2026-05-02'),(2,'2026-05-03');
```

Wrong query:

```sql
SELECT user_id, COUNT(day) AS days FROM visits GROUP BY user_id ORDER BY user_id;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    user_id  days
    -------  ----
          1     3
          2     1
    ```

    What goes wrong: User 1 gets 3: two visits on 1 May count as two days.

    Fixed:

    ```sql
    SELECT user_id, COUNT(DISTINCT day) AS days FROM visits GROUP BY user_id ORDER BY user_id;
    ```

    ```text
    user_id  days
    -------  ----
          1     2
          2     1
    ```


## 15. UNION drops real duplicates (mistake #8)

Task: Total units moved from both warehouses.

```sql
CREATE TABLE w1 (item TEXT, units INT);
CREATE TABLE w2 (item TEXT, units INT);
INSERT INTO w1 VALUES ('bolt',5);
INSERT INTO w2 VALUES ('bolt',5),('nut',2);
```

Wrong query:

```sql
SELECT SUM(units) AS total FROM (
  SELECT item, units FROM w1 UNION SELECT item, units FROM w2);
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    total
    -----
        7
    ```

    What goes wrong: 7: UNION merges the two ('bolt',5) rows, though they are two real shipments.

    Fixed:

    ```sql
    SELECT SUM(units) AS total FROM (
      SELECT item, units FROM w1 UNION ALL SELECT item, units FROM w2);
    ```

    ```text
    total
    -----
       12
    ```


## 16. Filtering before a window function (mistake #9)

Task: For each June reading, the change from the reading before it (May's last one counts).

```sql
CREATE TABLE temps (day TEXT, t INT);
INSERT INTO temps VALUES ('2026-05-31',20),('2026-06-01',23),('2026-06-02',21);
```

Wrong query:

```sql
SELECT day, t - LAG(t) OVER (ORDER BY day) AS change
FROM temps WHERE day >= '2026-06-01' ORDER BY day;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
       day      change
    ----------  ------
    2026-06-01
    2026-06-02      -2
    ```

    What goes wrong: 1 June has no change: WHERE removed 31 May before LAG could see it.

    Fixed:

    ```sql
    WITH x AS (SELECT day, t - LAG(t) OVER (ORDER BY day) AS change FROM temps)
    SELECT * FROM x WHERE day >= '2026-06-01' ORDER BY day;
    ```

    ```text
       day      change
    ----------  ------
    2026-06-01       3
    2026-06-02      -2
    ```


## 17. = NULL instead of IS NULL

Task: Tickets nobody has been given yet.

```sql
CREATE TABLE tickets (id INT, owner TEXT);
INSERT INTO tickets VALUES (1,'Ana'),(2,NULL),(3,NULL);
```

Wrong query:

```sql
SELECT id FROM tickets WHERE owner = NULL;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    (no rows)
    ```

    What goes wrong: Nothing: `owner = NULL` is unknown for every row, never true.

    Fixed:

    ```sql
    SELECT id FROM tickets WHERE owner IS NULL ORDER BY id;
    ```

    ```text
    id
    --
     2
     3
    ```


## 18. <> drops NULL rows

Task: Every ticket not marked 'closed', including those with no status yet.

```sql
CREATE TABLE tickets (id INT, status TEXT);
INSERT INTO tickets VALUES (1,'open'),(2,'closed'),(3,NULL);
```

Wrong query:

```sql
SELECT id FROM tickets WHERE status <> 'closed' ORDER BY id;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    id
    --
     1
    ```

    What goes wrong: Ticket 3 is missing: `NULL <> 'closed'` is unknown, not true.

    Fixed:

    ```sql
    SELECT id FROM tickets WHERE status IS DISTINCT FROM 'closed' ORDER BY id;
    -- SQLite also accepts: status IS NOT 'closed'
    ```

    ```text
    id
    --
     1
     3
    ```


## 19. Join fan-out doubles a sum

Task: Per customer: total paid and number of support calls.

```sql
CREATE TABLE payments (customer TEXT, amount INT);
INSERT INTO payments VALUES ('Ana',10),('Ana',20);
CREATE TABLE calls (customer TEXT, id INT);
INSERT INTO calls VALUES ('Ana',1),('Ana',2),('Ana',3);
```

Wrong query:

```sql
SELECT p.customer, SUM(p.amount) AS paid, COUNT(c.id) AS calls
FROM payments p JOIN calls c ON c.customer = p.customer
GROUP BY p.customer;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    customer  paid  calls
    --------  ----  -----
    Ana         90      6
    ```

    What goes wrong: Paid 90 and 6 calls: every payment row pairs with every call row (2 x 3).

    Fixed:

    ```sql
    SELECT p.customer, p.paid, c.calls FROM
      (SELECT customer, SUM(amount) AS paid FROM payments GROUP BY customer) p
      JOIN (SELECT customer, COUNT(*) AS calls FROM calls GROUP BY customer) c
      ON c.customer = p.customer;
    ```

    ```text
    customer  paid  calls
    --------  ----  -----
    Ana         30      3
    ```


## 20. AND before OR

Task: Orders from Paris or Rome that are over 50.

```sql
CREATE TABLE orders (id INT, city TEXT, amount INT);
INSERT INTO orders VALUES (1,'Paris',80),(2,'Paris',10),(3,'Rome',20),(4,'Rome',90);
```

Wrong query:

```sql
SELECT id FROM orders
WHERE city = 'Paris' OR city = 'Rome' AND amount > 50 ORDER BY id;
```

??? success "What goes wrong, and the fix (open after you try)"

    **What the wrong query gives**

    ```text
    id
    --
     1
     2
     4
    ```

    What goes wrong: Order 2 (Paris, 10) gets in: AND binds first, so it reads Paris OR (Rome AND over 50).

    Fixed:

    ```sql
    SELECT id FROM orders
    WHERE (city = 'Paris' OR city = 'Rome') AND amount > 50 ORDER BY id;
    ```

    ```text
    id
    --
     1
     4
    ```
