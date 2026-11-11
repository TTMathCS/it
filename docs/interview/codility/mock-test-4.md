# Mock test 4

The last rehearsal, best taken two or three days before the test. **Set a timer for 75 minutes.**

| Task | Type | Level | Aim for |
|---|---|---|---|
| 1 | SQL | Medium | 15 minutes |
| 2 | SQL | Hard | 25 minutes |
| 3 | Python | Hard | 30 minutes |

Before you open a solution, write down the edge cases you tested. Then compare with the list in the solution.

---

### Task&nbsp;1: Best seller in each region

**Level:** Medium · **Aim for:** 15 minutes

Each row of `sales` is one sale. A product's total in a region is the sum of `amount` over its sales there.
Write an SQL query that returns, for each region, the product(s) with the **highest total** in that region (if
several tie, return all of them): `region`, `product`, `total`. Sort by `region`, then `product`.

**Tables**

```sql
CREATE TABLE sales (
    id      INTEGER PRIMARY KEY,
    region  VARCHAR(20) NOT NULL,
    product VARCHAR(20) NOT NULL,
    amount  INTEGER NOT NULL
);
```

**Example data**

`sales`

| id | region | product | amount |
|---|---|---|---|
| 1 | east | apples | 5 |
| 2 | east | pears | 3 |
| 3 | east | pears | 3 |
| 4 | north | figs | 4 |
| 5 | north | apples | 4 |
| 6 | south | pears | 9 |
| 7 | south | apples | 2 |
| 8 | south | apples | 2 |
| 9 | south | apples | 2 |

**Your query should return**

| region | product | total |
|---|---|---|
| east | pears | 6 |
| north | apples | 4 |
| north | figs | 4 |
| south | pears | 9 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH t AS (
        SELECT region, product, SUM(amount) AS total,
               RANK() OVER (PARTITION BY region ORDER BY SUM(amount) DESC) AS rk
        FROM sales
        GROUP BY region, product
    )
    SELECT region, product, total
    FROM t
    WHERE rk = 1
    ORDER BY region, product;
    ```
    
    **Why it works**
    
    * **A window function over an aggregate.** In a grouped query, window functions run *after* `GROUP BY`, so
      `RANK() OVER (... ORDER BY SUM(amount) DESC)` ranks the groups by their totals in one step.
    * `RANK` gives tied totals the same rank, so every product tied for first has `rk = 1`. `ROW_NUMBER` would keep
      just one of them, chosen arbitrarily.
    * The filter `rk = 1` needs the CTE: a window function's result cannot be used in `WHERE` or `HAVING` of the same
      query.
    * The first wrong answer below also shows the "largest single row instead of largest total" mistake: east's
      biggest single sale is apples (5), but pears total 6.
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: one sale only;
    * edge case: empty table;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 200,000 rows: PostgreSQL 16 0.11 s, SQLite 3.53 0.18 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: largest single sale instead of largest total"
    
        ```sql
        SELECT s.region, s.product, s.amount AS total FROM sales s
        WHERE s.amount = (SELECT MAX(amount) FROM sales x WHERE x.region = s.region)
        ORDER BY s.region, s.product;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: ROW_NUMBER keeps one of the tied products"
    
        ```sql
        WITH t AS (SELECT region, product, SUM(amount) AS total,
               ROW_NUMBER() OVER (PARTITION BY region ORDER BY SUM(amount) DESC) AS rk
        FROM sales GROUP BY region, product)
        SELECT region, product, total FROM t WHERE rk = 1 ORDER BY region, product;
        ```
        
        Checked: this gives a wrong result on **sample**.



---

### Task&nbsp;2: Parts list for a bike

**Level:** Hard · **Aim for:** 25 minutes

Each row of `components` says that one `parent` is built from `qty` units of `child`. A child can itself have
children, the same part can be used in several assemblies, and there are no loops. A **basic part** is one that
is never a parent. Write an SQL query that returns how many units of each basic part are needed to build **one
`'bike'`**: `part` and `units`, sorted by `part`. If `'bike'` has no components, return no rows.

**Tables**

```sql
CREATE TABLE components (
    parent VARCHAR(20) NOT NULL,
    child  VARCHAR(20) NOT NULL,
    qty    INTEGER NOT NULL
);
```

**Example data**

`components`

| parent | child | qty |
|---|---|---|
| bike | wheel | 2 |
| bike | frame | 1 |
| bike | seat | 1 |
| wheel | spoke | 32 |
| wheel | bolt | 2 |
| wheel | tyre | 1 |
| frame | bolt | 4 |
| frame | tube | 3 |
| scooter | wheel | 2 |
| scooter | deck | 1 |

**Your query should return**

| part | units |
|---|---|
| bolt | 8 |
| seat | 1 |
| spoke | 64 |
| tube | 3 |
| tyre | 2 |

??? success "Solution and explanation (open after you try)"

    **Runs unchanged on PostgreSQL and SQLite**
    
    ```sql
    WITH RECURSIVE need(part, units) AS (
        SELECT child, qty FROM components WHERE parent = 'bike'     -- what one bike needs directly
        UNION ALL
        SELECT c.child, n.units * c.qty                              -- what those parts need, multiplied
        FROM need n
        JOIN components c ON c.parent = n.part
    )
    SELECT part, SUM(units) AS units
    FROM need
    WHERE part NOT IN (SELECT parent FROM components)               -- basic parts only
    GROUP BY part
    ORDER BY part;
    ```
    
    **Why it works**
    
    * A **recursive CTE** walks down the parts tree. The first part is the bike's direct components; the recursive
      part joins each part found so far to its own children and **multiplies** the quantities, because 2 wheels each
      needing 2 bolts is 4 bolts.
    * The same basic part can be reached along several paths (bolts come from the wheels and from the frame), so the
      last step adds them up with `SUM ... GROUP BY part`.
    * **`UNION ALL`, not `UNION`.** `UNION` removes duplicate rows, and two paths that happen to give the same
      (part, units) pair, here (`bolt`, 4) from the wheels and (`bolt`, 4) from the frame, would be counted once.
    * `NOT IN (SELECT parent ...)` is safe here because `parent` is declared `NOT NULL`. With a column that can be
      `NULL` it would return nothing at all (see "Customers who never ordered" in the
      [SQL practice set](sql-practice.md)).
    * "No loops" matters: with a loop, a recursive CTE would run forever (both databases would keep going until they
      run out of memory or are stopped).
    
    **Tested on PostgreSQL 16 and SQLite 3.53.** Every case below gave exactly the expected rows, columns and order on both:
    
    * the example above;
    * edge case: no bike in the table;
    * edge case: four levels deep;
    * 150 random small tables, each compared with a separate Python answer;
    * a large table of 100,000 rows: PostgreSQL 16 0.24 s, SQLite 3.53 0.15 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: UNION drops a second path with the same numbers"
    
        ```sql
        WITH RECURSIVE need(part, units) AS (
            SELECT child, qty FROM components WHERE parent = 'bike'
            UNION
            SELECT c.child, n.units * c.qty FROM need n JOIN components c ON c.parent = n.part)
        SELECT part, SUM(units) AS units FROM need WHERE part NOT IN (SELECT parent FROM components)
        GROUP BY part ORDER BY part;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: quantities not multiplied"
    
        ```sql
        WITH RECURSIVE need(part, units) AS (
            SELECT child, qty FROM components WHERE parent = 'bike'
            UNION ALL
            SELECT c.child, c.qty FROM need n JOIN components c ON c.parent = n.part)
        SELECT part, SUM(units) AS units FROM need WHERE part NOT IN (SELECT parent FROM components)
        GROUP BY part ORDER BY part;
        ```
        
        Checked: this gives a wrong result on **sample**.
    
    ??? failure "A common wrong answer: assemblies left in the list"
    
        ```sql
        WITH RECURSIVE need(part, units) AS (
            SELECT child, qty FROM components WHERE parent = 'bike'
            UNION ALL
            SELECT c.child, n.units * c.qty FROM need n JOIN components c ON c.parent = n.part)
        SELECT part, SUM(units) AS units FROM need GROUP BY part ORDER BY part;
        ```
        
        Checked: this gives a wrong result on **sample**.



---

### Task&nbsp;3: Stock levels with a minimum

**Level:** Hard · **Aim for:** 30 minutes

A warehouse has `N` products, numbered 0 to `N − 1`, each with a stock level that starts at 0. `ops` is a list of
operations, applied in order:

* `("add", i, q)`: the stock of product `i` grows by `q`;
* `("floor", v)`: every product with stock **below `v`** is raised to exactly `v`.

Return the list of the `N` final stock levels.

**Examples**

* `solution(3, [('add', 0, 2), ('floor', 1), ('add', 2, 5), ('floor', 3)])` returns `[3, 3, 6]`
* `solution(2, [('floor', 4), ('add', 1, 1)])` returns `[4, 5]`

**Write an efficient algorithm for the following assumptions:**

* `N` and `M`, the number of operations, are integers within the range [1..100,000];
* `0 ≤ i < N`; `q` is an integer within the range [1..1,000]; `v` is an integer within the range [0..1,000,000,000].

Start from:

```python
def solution(N, ops):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(N, ops):
        stock = [0] * N
        base = 0                       # the highest floor so far, not yet written into stock
        for op in ops:
            if op[0] == "add":
                _, i, q = op
                stock[i] = max(stock[i], base) + q    # apply the pending floor to this one product first
            else:
                base = max(base, op[1])               # a lower floor changes nothing
        return [max(s, base) for s in stock]          # apply the pending floor to everyone, once
    ```
    
    **Why it works**
    
    * Doing what the task says, a loop over all `N` products for every `floor`, is O(N·M): with 100,000 of each,
      10 billion steps. The reference answer, shown below in its own box, does exactly that, and was stopped after
      5 seconds on the large test.
    * **Be lazy.** Do not apply a floor to everyone; remember it in `base`. A product only needs the floor when it is
      next touched (an `add`) and at the very end. Floors combine as a maximum, so only the highest one matters.
    * Why `max(stock[i], base) + q` is right: every floor before the product's last `add` was already applied to it
      then, so `max(stock, base)` adds exactly the floors that came after. Adds only increase stock, so an old floor
      can never become active again.
    * `base = op[1]` instead of `max(...)` is the classic slip: a later, lower floor would undo a higher one.
    * Codility's lesson 4 has a task built on the same lazy idea; this is the version to recognise.
    
    **Cost:** O(N + M) time, O(N) memory.
    
    **The slow answer:** Applying every floor to all N products: O(N·M).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no operations: `solution(2, [])` returns `[0, 0]`;
    * edge case, a lower floor after a higher one: `solution(2, [('floor', 5), ('floor', 3)])` returns `[5, 5]`;
    * edge case, an add after a floor starts from the floor: `solution(1, [('floor', 10), ('add', 0, 1), ('floor', 10)])` returns `[11]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.016s.
    
    ??? failure "A common wrong answer: a lower floor replaces a higher one"
    
        ```python
        def solution(N, ops):
            stock = [0] * N
            base = 0
            for op in ops:
                if op[0] == "add":
                    stock[op[1]] = max(stock[op[1]], base) + op[2]
                else:
                    base = op[1]
            return [max(s, base) for s in stock]
        ```
        
        Checked: edge: a lower floor after a higher one: got [3, 3] want [5, 5].
    
    ??? failure "A common wrong answer: adding before applying the pending floor"
    
        ```python
        def solution(N, ops):
            stock = [0] * N
            base = 0
            for op in ops:
                if op[0] == "add":
                    stock[op[1]] += op[2]
                else:
                    base = max(base, op[1])
            return [max(s, base) for s in stock]
        ```
        
        Checked: example: got [3, 3, 5] want [3, 3, 6].
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(N, ops):
            stock = [0] * N
            for op in ops:
                if op[0] == "add":
                    stock[op[1]] += op[2]
                else:
                    stock = [max(s, op[1]) for s in stock]
            return stock
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.016s).



---

## After the mock

Read [the 15 most common mistakes](common-mistakes.md) once more and tick the ones you made in any of the four
mocks. On the day, go through the [cheat sheet](cheat-sheet.md) in the hour before you press Start.
