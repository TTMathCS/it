# Mock test 6

One more rehearsal, with three topics the other mocks do not use. **Set a timer for 80 minutes.**

| Task | Type | Level | Aim for |
|---|---|---|---|
| 1 | SQL | Medium | 20 minutes |
| 2 | SQL | Hard | 25 minutes |
| 3 | Python | Medium | 35 minutes |

Read all three tasks first. Before you open a solution, write down the edge cases you tested. Then compare with the
list in the solution.

---

### Task&nbsp;1: Tried every tea

**Level:** Medium · **Aim for:** 20 minutes

A tea shop sells products in categories. Write an SQL query that returns the `customer` name of every customer who
has ordered **every product in the category `'tea'`** at least once, sorted by name. Ordering the same tea twice
still counts once, and what else a customer bought does not matter. If the shop has no tea products, return no rows.

Assume customer names are unique and every order points to a real customer and product.

**Tables**

```sql
CREATE TABLE customers (
    id   INTEGER PRIMARY KEY,
    name VARCHAR(40) NOT NULL
);
CREATE TABLE products (
    id       INTEGER PRIMARY KEY,
    name     VARCHAR(40) NOT NULL,
    category VARCHAR(20) NOT NULL
);
CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id  INTEGER NOT NULL
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
| 5 | Eve |

`products`

| id | name | category |
|---|---|---|
| 1 | Green | tea |
| 2 | Black | tea |
| 3 | Mint | tea |
| 4 | Mug | gear |
| 5 | Pot | gear |

`orders`

| id | customer_id | product_id |
|---|---|---|
| 1 | 1 | 1 |
| 2 | 1 | 2 |
| 3 | 1 | 3 |
| 4 | 2 | 1 |
| 5 | 2 | 1 |
| 6 | 2 | 2 |
| 7 | 3 | 1 |
| 8 | 3 | 2 |
| 9 | 3 | 4 |
| 10 | 3 | 5 |
| 11 | 4 | 3 |
| 12 | 4 | 2 |
| 13 | 4 | 1 |
| 14 | 4 | 1 |
| 15 | 5 | 1 |
| 16 | 5 | 2 |
| 17 | 5 | 4 |

**Your query should return**

| customer |
|---|
| Ana |
| Dee |

??? success "Solution and explanation (open after you try)"

    **SQLite and PostgreSQL** (only run on SQLite)
    
    ```sql
    SELECT c.name AS customer
    FROM customers c
    JOIN orders o ON o.customer_id = c.id
    JOIN products p ON p.id = o.product_id
    WHERE p.category = 'tea'
    GROUP BY c.id, c.name
    HAVING COUNT(DISTINCT p.id) = (SELECT COUNT(*) FROM products WHERE category = 'tea')
    ORDER BY customer;
    ```
    
    **Why it works**
    
    * Keep only the tea rows, then count how many **different** teas each customer has. A customer who has all of
      them has exactly as many as the shop sells.
    * **`DISTINCT`** stops a repeat order from counting twice: Ben ordered Green twice and Black once, which is 3
      rows but only 2 teas.
    * **`WHERE` before `GROUP BY`** stops other products from filling the count: Eve has Green, Black and a Mug,
      3 different products but only 2 teas.
    * No tea products: the `WHERE` keeps no rows, so there are no groups and no output, as asked.
    
    **Tested on SQLite 3.54.0.** Every case below gave exactly the expected rows:
    
    * the example above: `[('Ana',), ('Dee',)]`;
    * edge case: no tea products: `[]`;
    * edge case: no orders: `[]`;
    * edge case: one tea product only: `[('Ben',)]`;
    * 300 random tests, each compared with a separate Python answer built from sets: 0 mismatches.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: COUNT(*) instead of COUNT(DISTINCT ...)"
    
        `HAVING COUNT(*) = (...)` counts order rows. On the sample it returns `[('Ana',), ('Ben',)]`: Ben gets in
        with a repeat order, and Dee (4 rows) drops out.
    
    ??? failure "A common wrong answer: no WHERE filter"
    
        Counting every distinct product, not only teas, returns `[('Ana',), ('Dee',), ('Eve',)]` on the sample:
        Eve's mug stands in for the tea she never ordered.



---

### Task&nbsp;2: Price on the order date

**Level:** Hard · **Aim for:** 25 minutes

Prices change over time. A row of `prices` says that from `valid_from` on (that day included) the product costs
`price`, until its next row. Write an SQL query that returns **every order** with `order_id`, `product` and `price`:
the price that was in force on the order's date, or `NULL` if the product had no price yet. Sort by `order_id`.

**Tables**

```sql
CREATE TABLE prices (
    product    VARCHAR(20) NOT NULL,
    valid_from DATE NOT NULL,
    price      INTEGER NOT NULL,
    PRIMARY KEY (product, valid_from)
);
CREATE TABLE orders (
    id         INTEGER PRIMARY KEY,
    product    VARCHAR(20) NOT NULL,
    order_date DATE NOT NULL
);
```

**Example data**

`prices`

| product | valid_from | price |
|---|---|---|
| tea | 2026-01-01 | 4 |
| tea | 2026-03-01 | 5 |
| tea | 2026-06-15 | 6 |
| mug | 2026-02-01 | 9 |

`orders`

| id | product | order_date |
|---|---|---|
| 1 | tea | 2026-02-10 |
| 2 | tea | 2026-03-01 |
| 3 | mug | 2026-01-20 |
| 4 | tea | 2026-07-01 |
| 5 | mug | 2026-05-05 |

**Your query should return**

| order_id | product | price |
|---|---|---|
| 1 | tea | 4 |
| 2 | tea | 5 |
| 3 | mug | NULL |
| 4 | tea | 6 |
| 5 | mug | 9 |

??? success "Solution and explanation (open after you try)"

    **SQLite and PostgreSQL** (only run on SQLite)
    
    ```sql
    SELECT o.id AS order_id, o.product,
           (SELECT p.price FROM prices p
            WHERE p.product = o.product AND p.valid_from <= o.order_date
            ORDER BY p.valid_from DESC LIMIT 1) AS price
    FROM orders o
    ORDER BY o.id;
    ```
    
    **Why it works**
    
    * For each order, look only at that product's prices that had already started (`valid_from <= order_date`) and
      take the newest of them. That is the one in force on the day.
    * **`<=`, not `<`.** Order 2 is on the very day the price changed to 5, and the new price counts that day.
    * A scalar subquery that finds nothing gives `NULL`, so order 3 (a mug bought before mugs had a price) stays in
      the result with no extra code.
    * With the primary key on `(product, valid_from)` the database finds each price through the index.
    
    The same answer with a window function, if you prefer joins (SQLite 3.25 or later):
    
    ```sql
    WITH m AS (
        SELECT o.id, o.product, p.price,
               ROW_NUMBER() OVER (PARTITION BY o.id ORDER BY p.valid_from DESC) AS rn
        FROM orders o
        LEFT JOIN prices p ON p.product = o.product AND p.valid_from <= o.order_date
    )
    SELECT id AS order_id, product, price FROM m WHERE rn = 1 ORDER BY id;
    ```
    
    It must be a `LEFT JOIN`, or order 3 vanishes. It joins every order to all its earlier prices, so it is slower
    on big tables.
    
    **Tested on SQLite 3.54.0.** Every case below gave exactly the expected rows, for both queries:
    
    * the example above: `[(1, 'tea', 4), (2, 'tea', 5), (3, 'mug', None), (4, 'tea', 6), (5, 'mug', 9)]`;
    * edge case: no orders: `[]`;
    * edge case: no prices: `[(1, 'tea', None), (2, 'tea', None)]`;
    * 300 random tests: 0 mismatches for the subquery, 0 for the window version;
    * a large test of 50,000 prices and 100,000 orders: subquery 0.09 s, window version 1.57 s.
    
    **Write your own edge cases before you submit.** The list above is the kind of thing hidden tests try.
    
    ??? failure "A common wrong answer: today's price for every order"
    
        Joining each order to the product's latest `valid_from` overall ignores the order date. On the sample it
        gives `[(1, 'tea', 6), (2, 'tea', 6), (3, 'mug', 9), (4, 'tea', 6), (5, 'mug', 9)]`.
    
    ??? failure "A common wrong answer: < instead of <="
    
        With `p.valid_from < o.order_date` order 2 gets the old price: `(2, 'tea', 4)` instead of 5.



---

### Task&nbsp;3: Smallest truck

**Level:** Medium · **Aim for:** 35 minutes

A warehouse ships packages in a fixed order: `W[i]` is the weight of the `i`-th package. Each day one truck leaves
with the next packages in the line, as many as fit: the total weight on a truck can not go over its capacity, and
the order can not change. Write a function `solution(W, D)` that returns the **smallest capacity** that ships every
package within `D` days.

**Examples**

* `solution([3, 2, 2, 4, 1, 4], 3)` returns `6` (days: 3+2, 2+4, 1+4)
* `solution([1, 9, 1], 2)` returns `10`
* `solution([5, 5, 5], 1)` returns `15`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `W`, is an integer within the range [1..100,000];
* each element of `W` is an integer within the range [1..10,000];
* `D` is an integer within the range [1..N].

Start from:

```python
def solution(W, D):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(W, D):
        def days(cap):
            d, load = 1, 0
            for w in W:
                if load + w > cap:
                    d, load = d + 1, 0
                load += w
            return d
        lo, hi = max(W), sum(W)
        while lo < hi:
            mid = (lo + hi) // 2
            if days(mid) <= D:
                hi = mid
            else:
                lo = mid + 1
        return lo
    ```
    
    **Why it works**
    
    * **Checking one capacity is easy:** fill each truck until the next package does not fit. Filling greedily
      never uses more days than any other split, so `days(cap)` is the fewest days for that capacity.
    * **The answer is a turning point.** A bigger truck never needs more days, so the capacities that work are
      everything from some value up. Binary search finds that value.
    * **The range:** the truck must carry the heaviest package (`max(W)`), and `sum(W)` always works in one day.
    
    **Cost:** about 30 rounds of the search (sum is at most a billion), each O(N): O(N log(sum W)).
    
    **Tested** (Python 3.9.6; standard library only):
    
    * the examples above;
    * `solution([1, 2, 3, 4, 5], 5)` returns `5`;
    * edge case, one package: `solution([7], 1)` returns `7`;
    * `solution([4, 4, 4, 4], 3)` returns `8`;
    * edge case, the heaviest packages: `solution([10000, 10000, 10000, 10000, 10000], 2)` returns `30000`;
    * 2000 random tests, each compared with a brute force that tries every way to cut the line into at most `D`
      runs: 0 mismatches;
    * the largest input the limits allow, N = 100,000: D = 1 0.138s, D = 7 0.143s, D = 100,000 0.172s.
    
    ??? failure "A common wrong answer: starting the search at 1"
    
        With `lo = 1` the search tries trucks smaller than the heaviest package, and `days()` quietly puts that
        package on a truck anyway. `solution([2, 8], 2)` then returns `2` (right: `8`), and `([1, 9, 1], 3)`
        returns `1` (right: `9`).
    
    ??? failure "A common wrong answer: the average load"
    
        `max(max(W), ceil(sum(W) / D))` ignores that packages can not be split. On `([4, 4, 4, 4], 3)` it gives
        `6`, but a truck of 6 takes one package a day and needs 4 days; the answer is `8`.
    
    ??? failure "A common wrong answer: trying every capacity from max(W) up (right answer, too slow)"
    
        With `N = 100,000` packages of 10,000 and `D = 2`, it has to step through 490,000 capacities with an
        O(N) check each. It was stopped after 5 seconds.



---

## After the mock

Count the edge cases in each solution that your own answer gets right. On the real test the hidden tests are cases
like these, and each one you miss costs points even when the example passes.
