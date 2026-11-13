# Analytics workshop: payments and website visits

*The everyday work of an analytics engineer, on two tables that behave like real data: payments, where one order
can have a failed attempt, a split payment, a refund or a double charge, and page views, which have to be cut into
sessions and funnels. Every example runs in your browser (press **Run this**), and every exercise has a
**Check** button. This is the kind of SQL a data engineering test asks for.*

!!! abstract "In this workshop"
    **You will learn:**

    - why you **aggregate before you join**, and the wrong totals you get if you don't
    - revenue that counts refunds and ignores failed payments, with `SUM(CASE ...)` and `FILTER`
    - **reconciling** two sources: what was ordered against what was paid
    - finding and removing **duplicates** with `GROUP BY ... HAVING` and `ROW_NUMBER`
    - the **latest row per key** (the last payment attempt of each order)
    - **sessions** from a click stream: `LAG`, a 30-minute gap, a running count
    - a **funnel**: how many visitors reached each step, and the conversion rate

    **You need:** [7. GROUP BY](07-Aggregation-Group-By-Having.md), [8. joins](08-Joins-Inner-Left-Right-Full-Cross.md), [11. CTEs](11-CTEs-and-Recursive-CTEs.md), [13. window functions: ranking](13-Window-Functions-Ranking.md) and [14. LAG, LEAD, running totals](14-Window-Functions-Lag-Lead-Running-Totals.md). The tables are
    `orders`, `order_items`, `payments` and `page_views` of the [sample database](sample-database.md#payments);
    look at their rows first.

    **Dialect:** PostgreSQL. Where SQLite needs something different, a note says so.

## W.1 Aggregate first, then join { #aggregate-first }

The most common wrong total in analytics SQL comes from joining two "many" tables to the same parent. Order 106
has **two items** and **two payments**. Join both to the order and you get 2 × 2 = 4 rows, so every sum is doubled:

<!-- sql -->
```sql
SELECT o.order_id,
       SUM(i.quantity * i.unit_price) AS items_total,
       SUM(p.amount)                  AS paid_total
FROM orders o
JOIN order_items i ON i.order_id = o.order_id
JOIN payments p    ON p.order_id = o.order_id
WHERE o.order_id = 106
GROUP BY o.order_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

| order_id | items_total | paid_total |
| --- | --- | --- |
| 106 | 113.00 | 113.00 |
<!-- /result -->

The real numbers are 56.50 ordered and 56.50 paid. Each item row was repeated once per payment, and each payment
once per item. This is called **fan-out**, and it gives no error: the numbers just look a little too big.

The fix is to **sum each "many" table on its own, one row per order, and join the results**:

**Task:** For order 106, show the items total and the amount paid, correctly.

??? success "Solution"

    <!-- sql -->
    ```sql
    WITH items AS (
      SELECT order_id, SUM(quantity * unit_price) AS items_total
      FROM order_items
      GROUP BY order_id
    ),
    paid AS (
      SELECT order_id, SUM(amount) AS paid_total
      FROM payments
      GROUP BY order_id
    )
    SELECT o.order_id, i.items_total, p.paid_total
    FROM orders o
    JOIN items i ON i.order_id = o.order_id
    JOIN paid p  ON p.order_id = o.order_id
    WHERE o.order_id = 106;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | order_id | items_total | paid_total |
    | --- | --- | --- |
    | 106 | 56.50 | 56.50 |
    <!-- /result -->

!!! tip "The rule"
    Before you join, ask: **how many rows per key** does each side have? If both sides of a join can have many rows
    for the same key, aggregate at least one of them to one row per key first.

## W.2 Revenue that counts refunds and ignores failures { #revenue }

A payment row is an **attempt**. A failed attempt moved no money; a refund moved money back. So "revenue" is the
sum of `paid` amounts plus the (negative) `refunded` amounts, and failed rows must be left out.

Per month, with `date_trunc` to cut each timestamp down to the first day of its month:

**Task:** For each month, show gross payments, refunds, net and the number of failed attempts.

??? success "Solution"

    <!-- sql pg -->
    ```sql
    SELECT date_trunc('month', paid_at)::date                       AS month,
           SUM(amount) FILTER (WHERE status = 'paid')                AS gross,
           SUM(amount) FILTER (WHERE status = 'refunded')            AS refunds,
           SUM(amount) FILTER (WHERE status IN ('paid', 'refunded')) AS net,
           COUNT(*)    FILTER (WHERE status = 'failed')              AS failed_attempts
    FROM payments
    GROUP BY 1
    ORDER BY 1;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | month | gross | refunds | net | failed_attempts |
    | --- | --- | --- | --- | --- |
    | 2026-01-01 | 273.50 | -32.00 | 241.50 | 1 |
    | 2026-02-01 | 277.50 | *NULL* | 277.50 | 0 |
    | 2026-03-01 | 322.50 | *NULL* | 322.50 | 0 |
    | 2026-04-01 | 302.50 | *NULL* | 302.50 | 1 |
    <!-- /result -->

`FILTER (WHERE ...)` is PostgreSQL's short way to aggregate only some rows. The portable way, which also works on
SQLite, MySQL and SQL Server, is `SUM(CASE WHEN ... THEN amount END)`: the `CASE` gives `NULL` for the other rows,
and `SUM` skips `NULL`s. Note what it returns when **no** row matches: `NULL`, not 0.

**Task:** For each payment method, show attempts, paid, failed and the refunded amount, most attempts first.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT method,
           COUNT(*)                                              AS attempts,
           SUM(CASE WHEN status = 'paid'   THEN 1 ELSE 0 END)    AS paid,
           SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)    AS failed,
           SUM(CASE WHEN status = 'refunded' THEN amount END)    AS refunded_amount
    FROM payments
    GROUP BY method
    ORDER BY attempts DESC, method NULLS LAST;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | method | attempts | paid | failed | refunded_amount |
    | --- | --- | --- | --- | --- |
    | card | 16 | 13 | 2 | -32.00 |
    | paypal | 4 | 4 | 0 | *NULL* |
    | gift | 1 | 1 | 0 | *NULL* |
    | *NULL* | 1 | 1 | 0 | *NULL* |
    <!-- /result -->

Three things to see in this result:

* `GROUP BY method` puts all the `NULL` methods in **one group** of their own (payment 10). `GROUP BY` treats
  `NULL`s as equal, even though `NULL = NULL` is not true in a `WHERE`.
* `NULLS LAST` puts that group at the end of its tie. Without it, PostgreSQL sorts `NULL` last and SQLite sorts it
  first: say where `NULL`s go whenever a sort column can be `NULL`.
* `refunded_amount` is `NULL` where a method had no refund: `SUM` of nothing is `NULL`. Wrap it in
  `COALESCE(..., 0)` when the task wants a 0.
* `THEN 1 ELSE 0` with `SUM` counts rows; `COUNT(CASE WHEN ... THEN 1 END)` does the same.

!!! note "SQLite"
    SQLite has `FILTER` from version 3.30, but no `date_trunc`: use `strftime('%Y-%m-01', paid_at)` for the month.

## W.3 Reconcile two sources { #reconcile }

A data engineer is often asked: **does what we sold match what we were paid?** Here, the order's value is the sum
of its items, and what was received is the sum of its paid and refunded payments. List every order where they
differ, with the reason in words. Every order must be checked, including the ones with **no payment at all**, so the
payment side is joined with `LEFT JOIN`:

**Task:** List the orders whose money received does not match the ordered amount, with the kind of problem.

??? success "Solution"

    <!-- sql -->
    ```sql
    WITH items AS (
      SELECT order_id, SUM(quantity * unit_price) AS ordered
      FROM order_items
      GROUP BY order_id
    ),
    received AS (
      SELECT order_id, SUM(amount) AS received
      FROM payments
      WHERE status IN ('paid', 'refunded')
      GROUP BY order_id
    )
    SELECT o.order_id, o.status, i.ordered,
           COALESCE(r.received, 0) AS received,
           CASE
             WHEN r.order_id IS NULL      THEN 'no money received'
             WHEN r.received = 0          THEN 'paid, then refunded'
             WHEN r.received > i.ordered  THEN 'paid too much'
             ELSE                              'paid too little'
           END AS problem
    FROM orders o
    JOIN items i         ON i.order_id = o.order_id
    LEFT JOIN received r ON r.order_id = o.order_id
    WHERE COALESCE(r.received, 0) <> i.ordered
    ORDER BY o.order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | order_id | status | ordered | received | problem |
    | --- | --- | --- | --- | --- |
    | 104 | cancelled | 32.00 | 0.00 | paid, then refunded |
    | 113 | cancelled | 36.00 | 0 | no money received |
    | 116 | pending | 25.00 | 0 | no money received |
    | 119 | pending | 24.50 | 0 | no money received |
    | 120 | shipped | 139.00 | 278.00 | paid too much |
    <!-- /result -->

Read the result against the data: order 104 was paid and then fully refunded, so it received 0 for 32.00 of items
(the order is cancelled, so that is expected; a real report would leave cancelled orders out). Orders 113 and
116 never had a payment, order 119 had only a failed one, and order 120 was **charged twice**.

The `WHERE status IN (...)` sits **inside** the `received` step, before the `LEFT JOIN`. Put it in the outer `WHERE`
instead and the orders with no payment disappear, because their `status` would be `NULL`: the
[LEFT JOIN trap](08-Joins-Inner-Left-Right-Full-Cross.md) of chapter 8.

## W.4 Find the duplicates, then keep one { #duplicates }

Two payments for the same order, amount, time and status are a **double charge** (or the same event loaded twice).
`GROUP BY` every column that should be unique, and keep the groups with more than one row:

**Task:** Find the payments that appear more than once with the same order, time, amount and status, with how many copies.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT order_id, paid_at, amount, status, COUNT(*) AS copies
    FROM payments
    GROUP BY order_id, paid_at, amount, status
    HAVING COUNT(*) > 1;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | order_id | paid_at | amount | status | copies |
    | --- | --- | --- | --- | --- |
    | 120 | 2026-04-05 12:30:00 | 139.00 | paid | 2 |
    <!-- /result -->

To **keep one row of each group** (for example to build a clean table), number the rows inside each group with
`ROW_NUMBER` and keep number 1. The `ORDER BY` inside the window says which copy survives: here the lowest
`payment_id`.

**Task:** For order 120, keep one row of each set of duplicate payments (the lowest payment id).

??? success "Solution"

    <!-- sql -->
    ```sql
    WITH numbered AS (
      SELECT *,
             ROW_NUMBER() OVER (PARTITION BY order_id, paid_at, amount, status
                                ORDER BY payment_id) AS copy_no
      FROM payments
    )
    SELECT payment_id, order_id, paid_at, amount, status
    FROM numbered
    WHERE copy_no = 1 AND order_id = 120;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | payment_id | order_id | paid_at | amount | status |
    | --- | --- | --- | --- | --- |
    | 21 | 120 | 2026-04-05 12:30:00 | 139.00 | paid |
    <!-- /result -->

`SELECT DISTINCT` would also remove the copy, but only if **every** column matches; the two rows still differ in
`payment_id`, so `DISTINCT` keeps both. `ROW_NUMBER` lets you say which columns define "the same".

## W.5 The latest row for each key { #latest }

"What is the **current** state of each order's payment?" is the latest attempt per order. Number the attempts per
order from the newest, and keep number 1. A tie in time needs a tie-break, or the answer can change from run to
run: here the higher `payment_id` wins.

**Task:** For orders 102, 104, 119 and 120, show the latest payment of each order.

??? success "Solution"

    <!-- sql -->
    ```sql
    WITH ranked AS (
      SELECT order_id, payment_id, paid_at, status,
             ROW_NUMBER() OVER (PARTITION BY order_id
                                ORDER BY paid_at DESC, payment_id DESC) AS rn
      FROM payments
    )
    SELECT order_id, payment_id, paid_at, status
    FROM ranked
    WHERE rn = 1 AND order_id IN (102, 104, 119, 120)
    ORDER BY order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 4 rows.</p>

    | order_id | payment_id | paid_at | status |
    | --- | --- | --- | --- |
    | 102 | 3 | 2026-01-03 18:44:00 | paid |
    | 104 | 6 | 2026-01-22 10:00:00 | refunded |
    | 119 | 20 | 2026-04-02 22:10:00 | failed |
    | 120 | 22 | 2026-04-05 12:30:00 | paid |
    <!-- /result -->

Order 102's latest attempt is the PayPal payment that succeeded; order 104's is the refund; order 119's is its only,
failed, attempt.

!!! note "PostgreSQL's shortcut"
    `SELECT DISTINCT ON (order_id) ... ORDER BY order_id, paid_at DESC, payment_id DESC` keeps the first row of each
    `order_id` in that order. It is shorter, but PostgreSQL-only; `ROW_NUMBER` works everywhere.

## W.6 Sessions from a click stream { #sessions }

Websites log one row per page. A **session** is a visit: the rule used here (a common one) is that **a gap of more
than 30 minutes between two pages of the same visitor starts a new session**. Three steps, each a CTE:

1. For each view, the time of the same visitor's **previous** view: `LAG(viewed_at)`.
2. A flag: 1 if this view **starts** a session (no previous view, or the gap is more than 30 minutes), else 0.
3. A **running sum** of the flag per visitor numbers the sessions: 1, 1, 1, 2, 2, ...

**Task:** Split each visitor's page views into sessions, where a gap of more than 30 minutes starts a new one: show the gap, the new-session flag and the session number.

??? success "Solution"

    <!-- sql pg -->
    ```sql
    WITH gaps AS (
      SELECT view_id, visitor_id, viewed_at, page,
             LAG(viewed_at) OVER (PARTITION BY visitor_id ORDER BY viewed_at, view_id) AS prev_at
      FROM page_views
    ),
    flags AS (
      SELECT *,
             CASE WHEN prev_at IS NULL
                    OR viewed_at - prev_at > INTERVAL '30 minutes' THEN 1 ELSE 0 END AS new_session
      FROM gaps
    )
    SELECT visitor_id, view_id, viewed_at, page, viewed_at - prev_at AS gap, new_session,
           SUM(new_session) OVER (PARTITION BY visitor_id ORDER BY viewed_at, view_id) AS session_no
    FROM flags
    WHERE visitor_id IN ('v1', 'v3')
    ORDER BY visitor_id, viewed_at, view_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 11 rows.</p>

    | visitor_id | view_id | viewed_at | page | gap | new_session | session_no |
    | --- | --- | --- | --- | --- | --- | --- |
    | v1 | 1 | 2026-04-05 12:00:00 | home | *NULL* | 1 | 1 |
    | v1 | 2 | 2026-04-05 12:03:10 | product | 0:03:10 | 0 | 1 |
    | v1 | 3 | 2026-04-05 12:10:00 | cart | 0:06:50 | 0 | 1 |
    | v1 | 4 | 2026-04-05 12:29:30 | checkout | 0:19:30 | 0 | 1 |
    | v1 | 5 | 2026-04-05 12:30:05 | thanks | 0:00:35 | 0 | 1 |
    | v1 | 6 | 2026-04-05 18:45:00 | home | 6:14:55 | 1 | 2 |
    | v1 | 7 | 2026-04-05 18:46:00 | product | 0:01:00 | 0 | 2 |
    | v3 | 13 | 2026-04-05 10:00:00 | home | *NULL* | 1 | 1 |
    | v3 | 14 | 2026-04-05 10:02:00 | product | 0:02:00 | 0 | 1 |
    | v3 | 15 | 2026-04-05 10:31:59 | product | 0:29:59 | 0 | 1 |
    | v3 | 16 | 2026-04-05 11:02:00 | checkout | 0:30:01 | 1 | 2 |
    <!-- /result -->

Look at `v3`: a gap of 29 minutes 59 seconds stays in session 1; the next gap, 30 minutes 1 second, starts session 2.
Check the boundary the task asks for: "more than 30 minutes" is `>`, "30 minutes or more" is `>=`.

With a session number on every row, one more `GROUP BY` gives a **sessions table**: one row per visit, with its
start, end, length and number of pages.

**Task:** For each visitor and session, show start, end, length and number of pages.

??? success "Solution"

    <!-- sql pg -->
    ```sql
    WITH gaps AS (
      SELECT visitor_id, viewed_at, view_id,
             LAG(viewed_at) OVER (PARTITION BY visitor_id ORDER BY viewed_at, view_id) AS prev_at
      FROM page_views
    ),
    numbered AS (
      SELECT *,
             SUM(CASE WHEN prev_at IS NULL OR viewed_at - prev_at > INTERVAL '30 minutes' THEN 1 ELSE 0 END)
               OVER (PARTITION BY visitor_id ORDER BY viewed_at, view_id) AS session_no
      FROM gaps
    )
    SELECT visitor_id, session_no,
           MIN(viewed_at)                  AS started,
           MAX(viewed_at)                  AS ended,
           MAX(viewed_at) - MIN(viewed_at) AS length,
           COUNT(*)                        AS pages
    FROM numbered
    GROUP BY visitor_id, session_no
    ORDER BY visitor_id, session_no;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 8 rows.</p>

    | visitor_id | session_no | started | ended | length | pages |
    | --- | --- | --- | --- | --- | --- |
    | v1 | 1 | 2026-04-05 12:00:00 | 2026-04-05 12:30:05 | 0:30:05 | 5 |
    | v1 | 2 | 2026-04-05 18:45:00 | 2026-04-05 18:46:00 | 0:01:00 | 2 |
    | v2 | 1 | 2026-04-05 09:00:00 | 2026-04-05 09:20:00 | 0:20:00 | 4 |
    | v2 | 2 | 2026-04-05 09:55:00 | 2026-04-05 09:55:00 | 0:00:00 | 1 |
    | v3 | 1 | 2026-04-05 10:00:00 | 2026-04-05 10:31:59 | 0:31:59 | 3 |
    | v3 | 2 | 2026-04-05 11:02:00 | 2026-04-05 11:02:00 | 0:00:00 | 1 |
    | v4 | 1 | 2026-04-04 23:50:00 | 2026-04-05 00:12:00 | 0:22:00 | 3 |
    | v5 | 1 | 2026-04-05 14:00:00 | 2026-04-05 14:00:00 | 0:00:00 | 1 |
    <!-- /result -->

Visitor `v4`'s session starts at 23:50 on 4 April and ends after midnight: the rule is about the **gap**, not the
calendar day, so it stays one session. If a report counts "sessions per day", decide which day a session belongs to
(usually the day it **started**) and say so.

!!! note "SQLite"
    SQLite stores these timestamps as text, so `viewed_at - prev_at` does not work. Compare seconds instead:
    `(julianday(viewed_at) - julianday(prev_at)) * 86400 > 1800`.

## W.7 A funnel { #funnel }

A **funnel** counts how many visitors reached each step: home, product, cart, checkout, thanks. First, one row per
visitor with a 1 or 0 for each step (`MAX` of a `CASE`: did **any** of their rows have that page?):

**Task:** For each visitor, show 1 or 0 for whether they saw each page: home, product, cart, checkout, thanks.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT visitor_id,
           MAX(CASE WHEN page = 'home'     THEN 1 ELSE 0 END) AS saw_home,
           MAX(CASE WHEN page = 'product'  THEN 1 ELSE 0 END) AS saw_product,
           MAX(CASE WHEN page = 'cart'     THEN 1 ELSE 0 END) AS saw_cart,
           MAX(CASE WHEN page = 'checkout' THEN 1 ELSE 0 END) AS saw_checkout,
           MAX(CASE WHEN page = 'thanks'   THEN 1 ELSE 0 END) AS saw_thanks
    FROM page_views
    GROUP BY visitor_id
    ORDER BY visitor_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 5 rows.</p>

    | visitor_id | saw_home | saw_product | saw_cart | saw_checkout | saw_thanks |
    | --- | --- | --- | --- | --- | --- |
    | v1 | 1 | 1 | 1 | 1 | 1 |
    | v2 | 1 | 1 | 1 | 0 | 0 |
    | v3 | 1 | 1 | 0 | 1 | 0 |
    | v4 | 1 | 1 | 1 | 0 | 0 |
    | v5 | 0 | 1 | 0 | 0 | 0 |
    <!-- /result -->

Then sum each column to get the funnel, and divide to get the conversion. Two habits: multiply by `100.0` (not
`100`) so the division is not integer division, and divide by `NULLIF(x, 0)` so an empty step gives `NULL`
instead of an error.

**Task:** Count the visitors, how many reached product, cart and checkout, how many bought, and the conversion percentage.

??? success "Solution"

    <!-- sql -->
    ```sql
    WITH steps AS (
      SELECT visitor_id,
             MAX(CASE WHEN page = 'product'  THEN 1 ELSE 0 END) AS product,
             MAX(CASE WHEN page = 'cart'     THEN 1 ELSE 0 END) AS cart,
             MAX(CASE WHEN page = 'checkout' THEN 1 ELSE 0 END) AS checkout,
             MAX(CASE WHEN page = 'thanks'   THEN 1 ELSE 0 END) AS thanks
      FROM page_views
      GROUP BY visitor_id
    )
    SELECT COUNT(*)      AS visitors,
           SUM(product)  AS reached_product,
           SUM(cart)     AS reached_cart,
           SUM(checkout) AS reached_checkout,
           SUM(thanks)   AS bought,
           ROUND(100.0 * SUM(thanks) / NULLIF(COUNT(*), 0), 1) AS conversion_pct
    FROM steps;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | visitors | reached_product | reached_cart | reached_checkout | bought | conversion_pct |
    | --- | --- | --- | --- | --- | --- |
    | 5 | 5 | 3 | 2 | 1 | 20.0 |
    <!-- /result -->

This counts a step even when it was reached **out of order**: `v3` reached checkout without a cart. A stricter
funnel counts a step only if the steps before it happened earlier; that needs the time of each step
(`MIN(CASE WHEN page = 'cart' THEN viewed_at END)`) and comparisons between them. Read the task to see which one it
asks for.

## W.8 Count events after removing repeats { #dedupe-events }

Views 9 and 10 are the same page, for the same visitor, at the same second: a page reload or a logging bug. Counting
**distinct** combinations removes them. `COUNT(DISTINCT ...)` takes one column, so count the distinct rows of a
subquery instead:

**Task:** Count the page-view rows, and the events left after removing exact repeats.

??? success "Solution"

    <!-- sql -->
    ```sql
    SELECT COUNT(*) AS all_rows,
           (SELECT COUNT(*)
            FROM (SELECT DISTINCT visitor_id, viewed_at, page, product_id FROM page_views) d) AS distinct_events
    FROM page_views;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 1 row.</p>

    | all_rows | distinct_events |
    | --- | --- |
    | 20 | 19 |
    <!-- /result -->

`DISTINCT` treats two `NULL` `product_id`s as equal, which is what you want here.

## Practice { #practice }

Each exercise has a **Try it here** box. Write your query, press **Check**, then open the answer.

**W.1** For each customer who has at least one order, the number of orders and the total **paid** (sum of payments
with status `paid` only). Return `customer_id`, `orders`, `total_paid`, sorted by `customer_id`. Customers whose
orders have no paid payment show 0. (Careful: an order can have several payments.)

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH paid AS (
      SELECT order_id, SUM(amount) AS paid
      FROM payments
      WHERE status = 'paid'
      GROUP BY order_id
    )
    SELECT o.customer_id,
           COUNT(*)                     AS orders,
           COALESCE(SUM(p.paid), 0)     AS total_paid
    FROM orders o
    LEFT JOIN paid p ON p.order_id = o.order_id
    WHERE o.customer_id IS NOT NULL
    GROUP BY o.customer_id
    ORDER BY o.customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 9 rows.</p>

    | customer_id | orders | total_paid |
    | --- | --- | --- |
    | 1 | 5 | 428.00 |
    | 2 | 3 | 205.50 |
    | 3 | 2 | 56.50 |
    | 4 | 2 | 205.50 |
    | 5 | 2 | 36.75 |
    | 6 | 2 | 65.00 |
    | 7 | 1 | 36.75 |
    | 8 | 1 | 49.00 |
    | 10 | 1 | 43.00 |
    <!-- /result -->

    Payments are summed per order first, so `COUNT(*)` counts orders, not order-payment pairs. Without that step,
    customer 1 would show 6 orders instead of 5, and twice the money for order 120, which has two `paid` rows.

**W.2** Every order that has **no successful payment** (no payment with status `paid`), with its status. Return
`order_id`, `status`, sorted by `order_id`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT o.order_id, o.status
    FROM orders o
    WHERE NOT EXISTS (
      SELECT 1 FROM payments p
      WHERE p.order_id = o.order_id AND p.status = 'paid'
    )
    ORDER BY o.order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | order_id | status |
    | --- | --- |
    | 113 | cancelled |
    | 116 | pending |
    | 119 | pending |
    <!-- /result -->

    An anti join: "orders for which no paid payment exists". Order 119 has a payment row, but a failed one, so it
    belongs in the list; a `LEFT JOIN payments ... WHERE p.order_id IS NULL` without the status condition in the
    `ON` would miss it.

**W.3** The share of payment **attempts** that failed, per method, as a percentage with one decimal. Leave out the
rows with no method. Return `method`, `attempts`, `failed_pct`, sorted by `method`.

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT method,
           COUNT(*) AS attempts,
           ROUND(100.0 * SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) / COUNT(*), 1) AS failed_pct
    FROM payments
    WHERE method IS NOT NULL
    GROUP BY method
    ORDER BY method;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 3 rows.</p>

    | method | attempts | failed_pct |
    | --- | --- | --- |
    | card | 16 | 12.5 |
    | gift | 1 | 0.0 |
    | paypal | 4 | 0.0 |
    <!-- /result -->

    `SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)` counts the failed attempts, and dividing by `COUNT(*)`
    (all attempts of that method) gives the share. `100.0` keeps the division decimal; `WHERE method IS NOT
    NULL` drops the rows with no method before grouping.


**W.4** Each day's net revenue (paid plus refunded, failed left out) and the **running total** since the first
day. Return `day`, `net`, `running_total`, sorted by `day`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH daily AS (
      SELECT CAST(paid_at AS DATE) AS day, SUM(amount) AS net
      FROM payments
      WHERE status IN ('paid', 'refunded')
      GROUP BY CAST(paid_at AS DATE)
    )
    SELECT day, net,
           SUM(net) OVER (ORDER BY day) AS running_total
    FROM daily
    ORDER BY day;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 16 rows.</p>

    | day | net | running_total |
    | --- | --- | --- |
    | 2026-01-03 | 183.25 | 183.25 |
    | 2026-01-15 | 33.75 | 217.00 |
    | 2026-01-20 | 32.00 | 249.00 |
    | 2026-01-22 | -32.00 | 217.00 |
    | 2026-01-28 | 24.50 | 241.50 |
    | 2026-02-02 | 93.25 | 334.75 |
    | 2026-02-10 | 50.00 | 384.75 |
    | 2026-02-14 | 65.00 | 449.75 |
    | 2026-02-20 | 32.50 | 482.25 |
    | 2026-02-21 | 36.75 | 519.00 |
    | 2026-03-01 | 181.00 | 700.00 |
    | 2026-03-09 | 49.00 | 749.00 |
    | 2026-03-18 | 49.50 | 798.50 |
    | 2026-03-25 | 43.00 | 841.50 |
    | 2026-04-01 | 24.50 | 866.00 |
    | 2026-04-05 | 278.00 | 1144.00 |
    <!-- /result -->

    Aggregate to one row per day first, then run the window over the days. A window `SUM` with `ORDER BY` and no
    frame adds up every row up to and including the current one; since each day is one row here, ties are not a
    problem. (On SQLite use `date(paid_at)` for the day.)

**W.5** For each order that has more than one payment row, the number of rows and the time between its first and
last attempt. Return `order_id`, `attempts`, `first_to_last`, sorted by `order_id`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT order_id,
           COUNT(*)                    AS attempts,
           MAX(paid_at) - MIN(paid_at) AS first_to_last
    FROM payments
    GROUP BY order_id
    HAVING COUNT(*) > 1
    ORDER BY order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | order_id | attempts | first_to_last |
    | --- | --- | --- |
    | 102 | 2 | 0:04:00 |
    | 104 | 2 | 1 day, 19:30:00 |
    | 106 | 2 | 0:01:00 |
    | 120 | 2 | 0:00:00 |
    <!-- /result -->

    In PostgreSQL, subtracting two timestamps gives an `interval`, printed as days and hours.

**W.6** For each signed-in visitor's page views (leave out guests), the number of **sessions** (30-minute rule).
Return `customer_id`, `sessions`, sorted by `customer_id`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH gaps AS (
      SELECT customer_id, viewed_at,
             LAG(viewed_at) OVER (PARTITION BY visitor_id ORDER BY viewed_at, view_id) AS prev_at
      FROM page_views
      WHERE customer_id IS NOT NULL
    )
    SELECT customer_id,
           SUM(CASE WHEN prev_at IS NULL OR viewed_at - prev_at > INTERVAL '30 minutes' THEN 1 ELSE 0 END)
             AS sessions
    FROM gaps
    GROUP BY customer_id
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | customer_id | sessions |
    | --- | --- |
    | 1 | 2 |
    | 2 | 2 |
    | 4 | 1 |
    <!-- /result -->

    Each session starts with exactly one flagged row, so the number of sessions is the sum of the flags; there is
    no need to number them.

**W.7** The products that were put in a cart but are not in any order of the **same customer**. Return
`customer_id`, `product_id`, sorted by both. (Use `page = 'cart'` rows; guests have no orders, leave them out.)

??? success "Answer"
    <!-- sql -->
    ```sql
    SELECT DISTINCT v.customer_id, v.product_id
    FROM page_views v
    WHERE v.page = 'cart'
      AND v.customer_id IS NOT NULL
      AND NOT EXISTS (
        SELECT 1
        FROM orders o
        JOIN order_items i ON i.order_id = o.order_id
        WHERE o.customer_id = v.customer_id
          AND i.product_id  = v.product_id
      )
    ORDER BY v.customer_id, v.product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 2 rows.</p>

    | customer_id | product_id |
    | --- | --- |
    | 2 | 5 |
    | 4 | 9 |
    <!-- /result -->

    `DISTINCT` because customer 2 had the same product in the cart twice. Customer 1's cart product (6, the office
    chair) is in order 120, so it is not in the list.

**W.8** Each order's **current** payment status: the status of its latest attempt (latest `paid_at`, then the
highest `payment_id`), or `'none'` when the order has no payment. Return `order_id`, `payment_status`, sorted by
`order_id`, for every order.

??? success "Answer"
    <!-- sql -->
    ```sql
    WITH ranked AS (
      SELECT order_id, status,
             ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY paid_at DESC, payment_id DESC) AS rn
      FROM payments
    )
    SELECT o.order_id, COALESCE(r.status, 'none') AS payment_status
    FROM orders o
    LEFT JOIN ranked r ON r.order_id = o.order_id AND r.rn = 1
    ORDER BY o.order_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16 and SQLite 3.53: same rows on both. 20 rows.</p>

    | order_id | payment_status |
    | --- | --- |
    | 101 | paid |
    | 102 | paid |
    | 103 | paid |
    | 104 | refunded |
    | 105 | paid |
    | 106 | paid |
    | 107 | paid |
    | 108 | paid |
    | 109 | paid |
    | 110 | paid |
    | 111 | paid |
    | 112 | paid |
    | 113 | none |
    | 114 | paid |
    | 115 | paid |
    | 116 | none |
    | 117 | paid |
    | 118 | paid |
    | 119 | failed |
    | 120 | paid |
    <!-- /result -->

    `r.rn = 1` belongs in the `ON`, not in the `WHERE`: in the `WHERE` it would remove orders 113 and 116, whose
    `rn` is `NULL` after the `LEFT JOIN`.

## Summary { #summary }

| Task | Pattern |
| --- | --- |
| Totals from two "many" tables | aggregate each to one row per key, then join |
| Revenue with refunds and failures | `SUM(CASE WHEN status ... THEN amount END)` or `FILTER (WHERE ...)` |
| Do two sources agree? | aggregate both, `LEFT JOIN`, `COALESCE`, compare |
| Duplicates | `GROUP BY` the columns that should be unique `HAVING COUNT(*) > 1`; keep one with `ROW_NUMBER() ... = 1` |
| Latest row per key | `ROW_NUMBER() OVER (PARTITION BY key ORDER BY time DESC, id DESC) = 1` |
| Sessions | `LAG` the time, flag gaps over the limit, running `SUM` of the flag |
| Funnel | `MAX(CASE WHEN step ...)` per visitor, then `SUM` each step |
| Percentages | `100.0 * part / NULLIF(whole, 0)`, then `ROUND` |
