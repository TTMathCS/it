# Advanced SQL: twelve hard cases from real work

*The hardest kind of SQL an analytics or data engineering test asks for, and the kind of question a data team meets
every week: prices that change over time, stock valued first in first out, subscriptions that overlap, funnels with
a time limit, cohorts, marketing attribution, balances that depend on the row before, org charts, gaps, and merging
duplicate customers. Each case says what the situation is, which technique answers it and why, shows a worked query
with its real result, and ends with an exercise of your own with a **Check** button.*

!!! abstract "How this page works"
    - Each case brings its own small tables (a grey "loads on" line under them) or uses the
      [sample shop](sample-database.md). Press **Run this** under any query to change it and run it again.
    - **Dialect: PostgreSQL**, the database of your test. Several cases use features SQLite does not have
      (`LATERAL`, `generate_series`, arrays, `RANGE` with an interval).
    - Read the case, cover the worked query, and try to write it yourself first. Then do the exercise without
      looking back.
    - **You need:** [11. CTEs](11-CTEs-and-Recursive-CTEs.md), [13. window functions: ranking](13-Window-Functions-Ranking.md),
      [14. LAG, LEAD, running totals](14-Window-Functions-Lag-Lead-Running-Totals.md) and
      [16. dates](16-Dates-and-Time-Series.md). The [analytics workshop](analytics-workshop.md) is the easier step
      before this page.

| Case | The situation | The technique |
| --- | --- | --- |
| [A.1](#point-in-time) | Which price was in force on the day of each sale? | Point-in-time join on a validity range (a "type 2" history) |
| [A.2](#fifo) | What did the goods sold cost, oldest stock first? | Cumulative ranges and their overlap (FIFO) |
| [A.3](#merge-periods) | Overlapping subscriptions: when was a customer really covered? | Running maximum, a "new period" flag, a running count |
| [A.4](#funnel-time) | Who viewed, then added to cart, then bought, within an hour? | Step-by-step joins, each step after the one before |
| [A.5](#cohorts) | Of the customers who started in January, how many came back each month? | Cohort and month number, then a share of the cohort |
| [A.6](#attribution) | Which marketing channel gets the credit for a sale? | `LATERAL` with `LIMIT 1`; splitting revenue with a window count |
| [A.7](#top-n-other) | Top 3 products and everything else as "Other" | `ROW_NUMBER`, then grouping by a `CASE` |
| [A.8](#rolling-distinct) | Active customers over the last 7 days, every day | A calendar joined to a date range (`COUNT(DISTINCT)` can't be a window) |
| [A.9](#recursive-balance) | A wallet that declines a payment when the money is not there | A recursive CTE that walks the rows one by one |
| [A.10](#org-rollup) | Every manager's whole team, all levels down | A recursive CTE of (boss, person below) pairs |
| [A.11](#gaps-ranges) | Missing invoice numbers, and free time between meetings | `LEAD` and a running maximum, written as ranges |
| [A.12](#golden-record) | One clean record from several messy duplicates | Most recent non-NULL value per field: `ARRAY_AGG ... FILTER` |

## A.1 The price in force on the day of the sale { #point-in-time }

**The situation.** Prices change. A history table keeps every price a product ever had, each with the date it
started (`valid_from`) and the date it stopped (`valid_to`, not included; NULL while it is still the price). This is
called a **type 2 history** (or "slowly changing dimension, type 2"), and it is how warehouses keep the past. To
value a sale you need the price that was in force **on the day of the sale**, not today's price.

<!-- sql setup -->
```sql
CREATE TABLE price_history (
  product_id INTEGER       NOT NULL,
  price      NUMERIC(8,2)  NOT NULL,
  valid_from DATE          NOT NULL,
  valid_to   DATE                       -- not included; NULL = still in force
);
INSERT INTO price_history VALUES
  (1, 10.00, '2026-01-01', '2026-02-01'),
  (1, 12.00, '2026-02-01', '2026-03-15'),
  (1, 11.00, '2026-03-15', NULL),
  (2,  5.00, '2026-01-01', NULL),
  (3, 20.00, '2026-02-01', '2026-03-01'),
  (3, 22.00, '2026-03-01', NULL);
CREATE TABLE product_sales (
  sale_id    INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL,
  sold_on    DATE    NOT NULL,
  qty        INTEGER NOT NULL
);
INSERT INTO product_sales VALUES
  (1, 1, '2026-01-15', 2),
  (2, 1, '2026-02-01', 1),
  (3, 1, '2026-03-14', 3),
  (4, 1, '2026-03-15', 1),
  (5, 2, '2026-02-20', 4),
  (6, 3, '2026-01-20', 1),
  (7, 3, '2026-03-01', 2);
CREATE TABLE price_changes (
  product_id INTEGER       NOT NULL,
  changed_on DATE          NOT NULL,
  new_price  NUMERIC(8,2)  NOT NULL
);
INSERT INTO price_changes VALUES
  (1, '2026-01-01', 10.00), (1, '2026-02-01', 12.00), (1, '2026-03-15', 11.00),
  (2, '2026-01-01',  5.00),
  (3, '2026-02-01', 20.00), (3, '2026-03-01', 22.00);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

**The technique: a point-in-time join.** Join each sale to the history row whose range contains the sale's date:
`sold_on >= valid_from AND (valid_to IS NULL OR sold_on < valid_to)`. The join condition is a **range test**, not an
equality, and that is the whole idea. Because the ranges of one product never overlap, each sale finds at most one
row.

<!-- sql pg -->
```sql
SELECT s.sale_id, s.product_id, s.sold_on, s.qty,
       h.price,
       s.qty * h.price AS revenue
FROM product_sales s
LEFT JOIN price_history h
       ON h.product_id = s.product_id
      AND s.sold_on >= h.valid_from                          -- started on or before the sale
      AND (h.valid_to IS NULL OR s.sold_on < h.valid_to)     -- and had not stopped yet
ORDER BY s.sale_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 7 rows.</p>

| sale_id | product_id | sold_on | qty | price | revenue |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 2026-01-15 | 2 | 10.00 | 20.00 |
| 2 | 1 | 2026-02-01 | 1 | 12.00 | 12.00 |
| 3 | 1 | 2026-03-14 | 3 | 12.00 | 36.00 |
| 4 | 1 | 2026-03-15 | 1 | 11.00 | 11.00 |
| 5 | 2 | 2026-02-20 | 4 | 5.00 | 20.00 |
| 6 | 3 | 2026-01-20 | 1 | *NULL* | *NULL* |
| 7 | 3 | 2026-03-01 | 2 | 22.00 | 44.00 |
<!-- /result -->

Read the boundaries: sale 2 is on 1 February, the day the price changed, and gets the **new** price because
`valid_from` is included and `valid_to` is not. Sale 6 happened before product 3 had any price, so the `LEFT JOIN`
keeps it with NULL; an inner join would lose it silently, and a revenue total would be too low with no warning.

**Why `valid_to` is "not included".** With half-open ranges (`from <= d < to`) one range ends exactly where the next
begins, and every day belongs to exactly one range. With both ends included, the change day would match two rows
and the sale would be counted twice.

**A.1 Exercise.** Many systems store only the **date each price started**: the table `price_changes` above
(`product_id`, `changed_on`, `new_price`). Build the validity ranges yourself (each range ends when the next change
of the same product starts) and return the revenue of each product. Sales with no price in force are left out.
Return `product_id`, `revenue`, sorted by `product_id`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH periods AS (
      SELECT product_id,
             new_price  AS price,
             changed_on AS valid_from,
             LEAD(changed_on) OVER (PARTITION BY product_id ORDER BY changed_on) AS valid_to
      FROM price_changes
    )
    SELECT s.product_id, SUM(s.qty * p.price) AS revenue
    FROM product_sales s
    JOIN periods p
      ON p.product_id = s.product_id
     AND s.sold_on >= p.valid_from
     AND (p.valid_to IS NULL OR s.sold_on < p.valid_to)
    GROUP BY s.product_id
    ORDER BY s.product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | product_id | revenue |
    | --- | --- |
    | 1 | 79.00 |
    | 2 | 20.00 |
    | 3 | 44.00 |
    <!-- /result -->

    `LEAD(changed_on)` gives each change the date of the **next** change of the same product, which is exactly
    where its range ends; the last change has no next one, so its `valid_to` is NULL (still in force). The inner
    `JOIN` drops sale 6, as asked.

## A.2 The cost of goods sold, oldest stock first (FIFO) { #fifo }

**The situation.** A shop buys the same product several times at different costs (lots) and sells it in pieces.
Accounting values each sale **first in, first out**: the units sold come from the oldest lot that still has stock.
A sale of 7 units may take the last 4 units of one lot and 3 of the next.

<!-- sql setup -->
```sql
CREATE TABLE stock_lots (
  lot_id     INTEGER PRIMARY KEY,
  product_id INTEGER       NOT NULL,
  bought_on  DATE          NOT NULL,
  qty        INTEGER       NOT NULL,
  unit_cost  NUMERIC(8,2)  NOT NULL
);
INSERT INTO stock_lots VALUES
  (1, 1, '2026-01-02', 10, 4.00),
  (2, 1, '2026-01-10',  5, 5.00),
  (3, 1, '2026-01-20', 10, 6.00),
  (4, 2, '2026-01-05',  8, 2.50);
CREATE TABLE stock_sales (
  sale_id    INTEGER PRIMARY KEY,
  product_id INTEGER NOT NULL,
  sold_on    DATE    NOT NULL,
  qty        INTEGER NOT NULL
);
INSERT INTO stock_sales VALUES
  (1, 1, '2026-01-12', 6),
  (2, 1, '2026-01-15', 7),
  (3, 1, '2026-01-25', 4),
  (4, 2, '2026-01-06', 3);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

**The technique: cumulative ranges and their overlap.** Line the units up. With running totals, lot 1 holds units
0 to 10 of product 1, lot 2 units 10 to 15, lot 3 units 15 to 25. The sales line up the same way: sale 1 takes units
0 to 6, sale 2 units 6 to 13, sale 3 units 13 to 17. A sale takes from a lot exactly the units where their two
ranges **overlap**, and the size of an overlap is `LEAST(end1, end2) - GREATEST(start1, start2)`. No loop is needed.

<!-- sql pg -->
```sql
WITH lots AS (
  SELECT lot_id, product_id, unit_cost,
         SUM(qty) OVER w - qty AS from_unit,            -- units bought before this lot
         SUM(qty) OVER w       AS to_unit               -- ... and including it
  FROM stock_lots
  WINDOW w AS (PARTITION BY product_id ORDER BY bought_on, lot_id ROWS UNBOUNDED PRECEDING)
),
sales AS (
  SELECT sale_id, product_id,
         SUM(qty) OVER w - qty AS from_unit,
         SUM(qty) OVER w       AS to_unit
  FROM stock_sales
  WINDOW w AS (PARTITION BY product_id ORDER BY sold_on, sale_id ROWS UNBOUNDED PRECEDING)
)
SELECT s.sale_id, s.product_id,
       SUM(LEAST(s.to_unit, l.to_unit) - GREATEST(s.from_unit, l.from_unit))               AS units,
       SUM((LEAST(s.to_unit, l.to_unit) - GREATEST(s.from_unit, l.from_unit)) * l.unit_cost) AS cost
FROM sales s
JOIN lots l
  ON l.product_id = s.product_id
 AND l.from_unit < s.to_unit          -- the two ranges overlap
 AND s.from_unit < l.to_unit
GROUP BY s.sale_id, s.product_id
ORDER BY s.sale_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

| sale_id | product_id | units | cost |
| --- | --- | --- | --- |
| 1 | 1 | 6 | 24.00 |
| 2 | 1 | 7 | 31.00 |
| 3 | 1 | 4 | 22.00 |
| 4 | 2 | 3 | 7.50 |
<!-- /result -->

Check sale 2 by hand: units 6 to 13 take units 6 to 10 of lot 1 (4 × 4.00 = 16.00) and units 10 to 13 of lot 2
(3 × 5.00 = 15.00), 31.00 in all. `WINDOW w AS (...)` names a window once so that two columns can share it.
`ROWS UNBOUNDED PRECEDING` makes the running total add one row at a time even when two lots were bought on the same
day. The query assumes no sale is bigger than the stock bought so far; a real system checks that first.

**A.2 Exercise.** After all the sales, what is left in stock, valued at the cost of the lots it is still in?
Return `product_id`, `units_left`, `value_left`, sorted by `product_id`. (A product with no sales keeps all its
units.)

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH lots AS (
      SELECT product_id, unit_cost,
             SUM(qty) OVER w - qty AS from_unit,
             SUM(qty) OVER w       AS to_unit
      FROM stock_lots
      WINDOW w AS (PARTITION BY product_id ORDER BY bought_on, lot_id ROWS UNBOUNDED PRECEDING)
    ),
    sold AS (
      SELECT product_id, SUM(qty) AS units_sold
      FROM stock_sales
      GROUP BY product_id
    )
    SELECT l.product_id,
           SUM(GREATEST(0, l.to_unit - GREATEST(l.from_unit, COALESCE(s.units_sold, 0))))               AS units_left,
           SUM(GREATEST(0, l.to_unit - GREATEST(l.from_unit, COALESCE(s.units_sold, 0))) * l.unit_cost) AS value_left
    FROM lots l
    LEFT JOIN sold s ON s.product_id = l.product_id
    GROUP BY l.product_id
    ORDER BY l.product_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 2 rows.</p>

    | product_id | units_left | value_left |
    | --- | --- | --- |
    | 1 | 8 | 48.00 |
    | 2 | 5 | 12.50 |
    <!-- /result -->

    FIFO sells units 0 to `units_sold` first, so what is left of a lot is the part of its range **above**
    `units_sold`: from `GREATEST(from_unit, units_sold)` to `to_unit`, or nothing (`GREATEST(0, ...)`) when the lot
    is used up. The `LEFT JOIN` with `COALESCE(..., 0)` keeps products that were never sold.

## A.3 Overlapping subscriptions: when was a customer covered? { #merge-periods }

**The situation.** A customer can hold several subscriptions that overlap, touch, or sit inside each other (a
renewal bought before the old one ended, a gift month). The business wants the real **coverage periods**: the
stretches of time when the customer had at least one subscription. Periods run from `start_date` up to `end_date`,
with `end_date` not included.

<!-- sql setup -->
```sql
CREATE TABLE subscriptions (
  customer_id INTEGER NOT NULL,
  start_date  DATE    NOT NULL,
  end_date    DATE    NOT NULL      -- not included
);
INSERT INTO subscriptions VALUES
  (1, '2026-01-01', '2026-02-01'),
  (1, '2026-01-20', '2026-03-01'),
  (1, '2026-03-01', '2026-03-15'),
  (1, '2026-05-01', '2026-06-01'),
  (2, '2026-02-01', '2026-04-01'),
  (2, '2026-02-10', '2026-02-20'),
  (3, '2026-01-10', '2026-01-11');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

**The technique: merging intervals.** Sort each customer's subscriptions by start. A subscription **starts a new
period** when it begins after every earlier subscription has ended, that is after the running **maximum** of the
earlier end dates (the maximum, not the previous row's end: a short subscription inside a long one must not end the
period). Turn that into a 1/0 flag, and a running `SUM` of the flags numbers the periods. Then each period is one
`GROUP BY`. This is gaps and islands for ranges instead of single days.

<!-- sql pg -->
```sql
WITH ordered AS (
  SELECT customer_id, start_date, end_date,
         MAX(end_date) OVER (PARTITION BY customer_id ORDER BY start_date, end_date
                             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS covered_until
  FROM subscriptions
),
flagged AS (
  SELECT customer_id, start_date, end_date,
         CASE WHEN covered_until IS NULL OR start_date > covered_until THEN 1 ELSE 0 END AS new_period
  FROM ordered
),
numbered AS (
  SELECT customer_id, start_date, end_date,
         SUM(new_period) OVER (PARTITION BY customer_id ORDER BY start_date, end_date
                               ROWS UNBOUNDED PRECEDING) AS period_no
  FROM flagged
)
SELECT customer_id, period_no,
       MIN(start_date) AS period_start,
       MAX(end_date)   AS period_end
FROM numbered
GROUP BY customer_id, period_no
ORDER BY customer_id, period_no;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

| customer_id | period_no | period_start | period_end |
| --- | --- | --- | --- |
| 1 | 1 | 2026-01-01 | 2026-03-15 |
| 1 | 2 | 2026-05-01 | 2026-06-01 |
| 2 | 1 | 2026-02-01 | 2026-04-01 |
| 3 | 1 | 2026-01-10 | 2026-01-11 |
<!-- /result -->

`ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING` means "every earlier row, but not this one". The first row has no
earlier row, so `covered_until` is NULL and it always starts a period. `start_date > covered_until` (not `>=`) makes
subscriptions that **touch** (one ends on 1 March, the next starts on 1 March) one period, as customer 1 shows.
Customer 2's second subscription sits inside the first and changes nothing.

**A.3 Exercise.** For each customer: the number of coverage periods and the total number of days covered (a day
covered by two subscriptions counts once). Return `customer_id`, `periods`, `days_covered`, sorted by
`customer_id`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH ordered AS (
      SELECT customer_id, start_date, end_date,
             MAX(end_date) OVER (PARTITION BY customer_id ORDER BY start_date, end_date
                                 ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS covered_until
      FROM subscriptions
    ),
    numbered AS (
      SELECT customer_id, start_date, end_date,
             SUM(CASE WHEN covered_until IS NULL OR start_date > covered_until THEN 1 ELSE 0 END)
               OVER (PARTITION BY customer_id ORDER BY start_date, end_date ROWS UNBOUNDED PRECEDING) AS period_no
      FROM ordered
    ),
    periods AS (
      SELECT customer_id, MIN(start_date) AS period_start, MAX(end_date) AS period_end
      FROM numbered
      GROUP BY customer_id, period_no
    )
    SELECT customer_id,
           COUNT(*)                         AS periods,
           SUM(period_end - period_start)   AS days_covered
    FROM periods
    GROUP BY customer_id
    ORDER BY customer_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | customer_id | periods | days_covered |
    | --- | --- | --- |
    | 1 | 2 | 104 |
    | 2 | 1 | 59 |
    | 3 | 1 | 1 |
    <!-- /result -->

    Merge first, then measure: once the periods do not overlap, their lengths can simply be added. Summing
    `end_date - start_date` over the raw subscriptions would count customer 1's overlap in January twice and
    customer 2's inner subscription on top of the outer one. In PostgreSQL one date minus another is a whole number
    of days, and since `end_date` is not included, no `+ 1` is needed.

## A.4 A funnel with an order and a time limit { #funnel-time }

**The situation.** A product team asks: of the visitors who viewed a product, how many then added it to the cart, and
how many then bought, **within one hour of first viewing it**? Order matters (a cart before the view does not count)
and so does time.

<!-- sql setup -->
```sql
CREATE TABLE funnel_events (
  user_id INTEGER     NOT NULL,
  ts      TIMESTAMP   NOT NULL,
  step    VARCHAR(10) NOT NULL       -- 'view', 'cart' or 'buy'
);
INSERT INTO funnel_events VALUES
  (1, '2026-03-02 10:00', 'view'), (1, '2026-03-02 10:05', 'cart'), (1, '2026-03-02 10:20', 'buy'),
  (2, '2026-03-02 10:00', 'view'), (2, '2026-03-02 10:10', 'buy'),
  (3, '2026-03-02 09:00', 'cart'), (3, '2026-03-02 09:10', 'view'), (3, '2026-03-02 09:20', 'buy'),
  (4, '2026-03-02 11:00', 'view'), (4, '2026-03-02 11:30', 'cart'), (4, '2026-03-02 12:30', 'buy'),
  (5, '2026-03-02 12:00', 'view'), (5, '2026-03-02 12:01', 'cart'), (5, '2026-03-02 12:02', 'cart'),
  (5, '2026-03-02 12:50', 'buy'),
  (6, '2026-03-02 13:00', 'cart');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

**The technique: one CTE per step, each starting after the step before.** Step 1 is each user's first view. Step 2
joins the cart events that come **after** that view and keeps the first one. Step 3 joins the purchases after that
cart and no later than one hour after the view. A user who fails a step simply has no row in the next CTE, so
counting the rows of each CTE gives the funnel.

<!-- sql pg -->
```sql
WITH viewed AS (
  SELECT user_id, MIN(ts) AS view_ts
  FROM funnel_events
  WHERE step = 'view'
  GROUP BY user_id
),
carted AS (
  SELECT v.user_id, v.view_ts, MIN(e.ts) AS cart_ts
  FROM viewed v
  JOIN funnel_events e
    ON e.user_id = v.user_id AND e.step = 'cart' AND e.ts > v.view_ts
  GROUP BY v.user_id, v.view_ts
),
bought AS (
  SELECT c.user_id, MIN(e.ts) AS buy_ts
  FROM carted c
  JOIN funnel_events e
    ON e.user_id = c.user_id AND e.step = 'buy'
   AND e.ts > c.cart_ts
   AND e.ts <= c.view_ts + INTERVAL '1 hour'
  GROUP BY c.user_id
)
SELECT (SELECT COUNT(*) FROM viewed) AS viewed,
       (SELECT COUNT(*) FROM carted) AS carted,
       (SELECT COUNT(*) FROM bought) AS bought;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 1 row.</p>

| viewed | carted | bought |
| --- | --- | --- |
| 5 | 3 | 2 |
<!-- /result -->

User 2 bought without a cart, so the purchase does not count; user 3 put the item in the cart **before** viewing it;
user 4 bought 90 minutes after the view, too late. Users 1 and 5 complete the funnel; user 6 never viewed and is not
in it at all. A plain `COUNT(DISTINCT user_id) FILTER (WHERE step = 'buy')` would have counted users 2, 3 and 4 as
buyers too: the order of the steps is the whole difficulty.

**A.4 Exercise.** For every user who viewed: how far they got, as `'view'`, `'cart'` or `'buy'` (with the same rules),
and for those who bought, the minutes from the view to the purchase (NULL otherwise). Return `user_id`,
`furthest_step`, `minutes_to_buy`, sorted by `user_id`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH viewed AS (
      SELECT user_id, MIN(ts) AS view_ts
      FROM funnel_events WHERE step = 'view'
      GROUP BY user_id
    ),
    carted AS (
      SELECT v.user_id, v.view_ts, MIN(e.ts) AS cart_ts
      FROM viewed v
      JOIN funnel_events e ON e.user_id = v.user_id AND e.step = 'cart' AND e.ts > v.view_ts
      GROUP BY v.user_id, v.view_ts
    ),
    bought AS (
      SELECT c.user_id, MIN(e.ts) AS buy_ts
      FROM carted c
      JOIN funnel_events e ON e.user_id = c.user_id AND e.step = 'buy'
                          AND e.ts > c.cart_ts AND e.ts <= c.view_ts + INTERVAL '1 hour'
      GROUP BY c.user_id
    )
    SELECT v.user_id,
           CASE WHEN b.user_id IS NOT NULL THEN 'buy'
                WHEN c.user_id IS NOT NULL THEN 'cart'
                ELSE 'view' END                                        AS furthest_step,
           CAST(EXTRACT(EPOCH FROM b.buy_ts - v.view_ts) / 60 AS INTEGER) AS minutes_to_buy
    FROM viewed v
    LEFT JOIN carted c ON c.user_id = v.user_id
    LEFT JOIN bought b ON b.user_id = v.user_id
    ORDER BY v.user_id;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 5 rows.</p>

    | user_id | furthest_step | minutes_to_buy |
    | --- | --- | --- |
    | 1 | buy | 20 |
    | 2 | view | *NULL* |
    | 3 | view | *NULL* |
    | 4 | cart | *NULL* |
    | 5 | buy | 50 |
    <!-- /result -->

    The same three steps, but instead of counting each CTE, `LEFT JOIN` them all to `viewed`: a NULL in `carted` or
    `bought` means the user stopped before that step, and `CASE` names the furthest step reached. A timestamp minus
    a timestamp is an `INTERVAL`; `EXTRACT(EPOCH FROM ...)` turns it into seconds.

## A.5 Cohorts: who came back, month by month { #cohorts }

**The situation.** "Of the customers whose first order was in January, how many ordered again in February, March,
April?" A **cohort** is a group of customers who started in the same period. Retention is the share of the cohort
that is still active N months later. This uses the shop's `orders` (any status).

**The technique.** Three steps. (1) One row per customer per month they ordered in (`DISTINCT`, so two orders in a
month count once). (2) Each customer's cohort is their first month. (3) For each activity row, the **month number**
is the number of months since the cohort month (0 = the first month). Then count per cohort and month number, and
divide by the cohort's size.

<!-- sql pg -->
```sql
WITH active AS (
  SELECT DISTINCT customer_id, CAST(date_trunc('month', order_date) AS DATE) AS month
  FROM orders
  WHERE customer_id IS NOT NULL
),
cohort AS (
  SELECT customer_id, MIN(month) AS cohort_month
  FROM active
  GROUP BY customer_id
),
activity AS (
  SELECT c.cohort_month,
         CAST((EXTRACT(YEAR FROM a.month) - EXTRACT(YEAR FROM c.cohort_month)) * 12
              + EXTRACT(MONTH FROM a.month) - EXTRACT(MONTH FROM c.cohort_month) AS INTEGER) AS month_no,
         a.customer_id
  FROM active a
  JOIN cohort c ON c.customer_id = a.customer_id
),
sizes AS (
  SELECT cohort_month, COUNT(*) AS cohort_size
  FROM cohort
  GROUP BY cohort_month
)
SELECT a.cohort_month, a.month_no, COUNT(*) AS active, s.cohort_size,
       ROUND(100.0 * COUNT(*) / s.cohort_size, 1) AS pct
FROM activity a
JOIN sizes s ON s.cohort_month = a.cohort_month
GROUP BY a.cohort_month, a.month_no, s.cohort_size
ORDER BY a.cohort_month, a.month_no;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 8 rows.</p>

| cohort_month | month_no | active | cohort_size | pct |
| --- | --- | --- | --- | --- |
| 2026-01-01 | 0 | 4 | 4 | 100.0 |
| 2026-01-01 | 1 | 2 | 4 | 50.0 |
| 2026-01-01 | 2 | 3 | 4 | 75.0 |
| 2026-01-01 | 3 | 2 | 4 | 50.0 |
| 2026-02-01 | 0 | 3 | 3 | 100.0 |
| 2026-02-01 | 1 | 1 | 3 | 33.3 |
| 2026-02-01 | 2 | 1 | 3 | 33.3 |
| 2026-03-01 | 0 | 2 | 2 | 100.0 |
<!-- /result -->

`date_trunc('month', d)` sets a date back to the first day of its month, so every order of one month gets the same
value. The month number is written with years too (`* 12`), so that December to January counts as 1, not -11. Month
0 is always 100%: everyone in a cohort was active in the month they started.

**A.5 Exercise.** The same numbers as a **matrix**, the way a dashboard shows them: one row per cohort with its size
and the percentage active in month 1, 2 and 3 (0 when nobody was). Return `cohort_month`, `cohort_size`, `m1`, `m2`,
`m3`, sorted by `cohort_month`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH active AS (
      SELECT DISTINCT customer_id, CAST(date_trunc('month', order_date) AS DATE) AS month
      FROM orders
      WHERE customer_id IS NOT NULL
    ),
    cohort AS (
      SELECT customer_id, MIN(month) AS cohort_month FROM active GROUP BY customer_id
    ),
    activity AS (
      SELECT c.cohort_month, a.customer_id,
             CAST((EXTRACT(YEAR FROM a.month) - EXTRACT(YEAR FROM c.cohort_month)) * 12
                  + EXTRACT(MONTH FROM a.month) - EXTRACT(MONTH FROM c.cohort_month) AS INTEGER) AS month_no
      FROM active a JOIN cohort c ON c.customer_id = a.customer_id
    )
    SELECT cohort_month,
           COUNT(*) FILTER (WHERE month_no = 0) AS cohort_size,
           ROUND(100.0 * COUNT(*) FILTER (WHERE month_no = 1) / COUNT(*) FILTER (WHERE month_no = 0), 1) AS m1,
           ROUND(100.0 * COUNT(*) FILTER (WHERE month_no = 2) / COUNT(*) FILTER (WHERE month_no = 0), 1) AS m2,
           ROUND(100.0 * COUNT(*) FILTER (WHERE month_no = 3) / COUNT(*) FILTER (WHERE month_no = 0), 1) AS m3
    FROM activity
    GROUP BY cohort_month
    ORDER BY cohort_month;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | cohort_month | cohort_size | m1 | m2 | m3 |
    | --- | --- | --- | --- | --- |
    | 2026-01-01 | 4 | 50.0 | 75.0 | 50.0 |
    | 2026-02-01 | 3 | 33.3 | 33.3 | 0.0 |
    | 2026-03-01 | 2 | 0.0 | 0.0 | 0.0 |
    <!-- /result -->

    A **pivot**: one `COUNT(*) FILTER (WHERE month_no = n)` per column turns the month numbers into columns. Every
    customer is active in month 0 of their own cohort, so `COUNT(*) FILTER (WHERE month_no = 0)` is the cohort's
    size and needs no separate CTE. A count of nobody is 0, not NULL, so empty months show 0.0 without `COALESCE`.

## A.6 Which channel gets the credit? Attribution { #attribution }

**The situation.** Before buying, a customer may click an ad, open an email, see a social post. Marketing wants to
know which **channel** led to each sale. Two common rules: **last touch** (the latest touch before the sale gets all
the credit) and **linear** (every touch in the window shares the credit equally). Touches count only within 7 days
before the conversion; a conversion with none is `'direct'`.

<!-- sql setup -->
```sql
CREATE TABLE touches (
  user_id INTEGER     NOT NULL,
  ts      TIMESTAMP   NOT NULL,
  channel VARCHAR(10) NOT NULL
);
INSERT INTO touches VALUES
  (1, '2026-03-01 09:00', 'search'),
  (1, '2026-03-03 12:00', 'email'),
  (1, '2026-03-20 08:00', 'social'),
  (2, '2026-03-02 10:00', 'social'),
  (3, '2026-02-01 10:00', 'search'),
  (4, '2026-03-05 09:00', 'email'),
  (4, '2026-03-05 09:30', 'search');
CREATE TABLE conversions (
  conv_id INTEGER       PRIMARY KEY,
  user_id INTEGER       NOT NULL,
  ts      TIMESTAMP     NOT NULL,
  revenue NUMERIC(8,2)  NOT NULL
);
INSERT INTO conversions VALUES
  (1, 1, '2026-03-04 10:00', 100.00),
  (2, 1, '2026-03-21 10:00',  50.00),
  (3, 2, '2026-03-12 10:00',  80.00),
  (4, 3, '2026-03-01 10:00',  40.00),
  (5, 4, '2026-03-05 09:30',  60.00);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

**The technique: `LATERAL` with `ORDER BY ... LIMIT 1`.** A `LATERAL` subquery runs once for each row on its left
and can use that row's columns, so "the latest touch of **this** user before **this** conversion" is a subquery with
`ORDER BY ts DESC LIMIT 1`. `LEFT JOIN LATERAL ... ON TRUE` keeps conversions that find no touch.

<!-- sql pg -->
```sql
SELECT c.conv_id, c.user_id, c.revenue,
       COALESCE(t.channel, 'direct') AS last_touch
FROM conversions c
LEFT JOIN LATERAL (
  SELECT channel
  FROM touches t
  WHERE t.user_id = c.user_id
    AND t.ts <= c.ts                              -- before (or at) the conversion
    AND t.ts >  c.ts - INTERVAL '7 days'          -- but not more than 7 days before
  ORDER BY t.ts DESC
  LIMIT 1
) t ON TRUE
ORDER BY c.conv_id;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 5 rows.</p>

| conv_id | user_id | revenue | last_touch |
| --- | --- | --- | --- |
| 1 | 1 | 100.00 | email |
| 2 | 1 | 50.00 | social |
| 3 | 2 | 80.00 | direct |
| 4 | 3 | 40.00 | direct |
| 5 | 4 | 60.00 | search |
<!-- /result -->

Conversion 2 is credited to the social post the day before, not the email two weeks earlier. Conversion 3's only
touch was 10 days earlier and conversion 4's was a month earlier, so both are `'direct'`. Without `LATERAL` the same
answer takes a join to all touches in the window plus `ROW_NUMBER() ... = 1` in a CTE; both are fine in a test.

**A.6 Exercise.** Linear attribution: split each conversion's revenue equally among its touches in the 7 days before
it (with the same rules); conversions with no touch give all their revenue to `'direct'`. Return `channel`,
`revenue` (rounded to 2 decimals), largest first, then by `channel`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH matched AS (
      SELECT c.conv_id, c.revenue, t.channel
      FROM conversions c
      LEFT JOIN touches t
             ON t.user_id = c.user_id
            AND t.ts <= c.ts
            AND t.ts >  c.ts - INTERVAL '7 days'
    ),
    shares AS (
      SELECT COALESCE(channel, 'direct') AS channel,
             revenue / COUNT(*) OVER (PARTITION BY conv_id) AS share
      FROM matched
    )
    SELECT channel, ROUND(SUM(share), 2) AS revenue
    FROM shares
    GROUP BY channel
    ORDER BY revenue DESC, channel;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

    | channel | revenue |
    | --- | --- |
    | direct | 120.00 |
    | email | 80.00 |
    | search | 80.00 |
    | social | 50.00 |
    <!-- /result -->

    The `LEFT JOIN` gives one row per (conversion, touch), or one row with a NULL channel when there is no touch.
    `COUNT(*) OVER (PARTITION BY conv_id)` puts the number of rows of each conversion on every one of its rows, so
    dividing the revenue by it gives each touch its equal share, and the shares of one conversion add back up to its
    revenue. Conversion 1 gives 50.00 each to search and email.

## A.7 The top 3, and everything else as "Other" { #top-n-other }

**The situation.** A chart or a report has room for three products. The rest must still be counted, as one row
called `Other`, placed last, so that the total stays right. This uses the shop's `order_items` and `products`.

**The technique.** Rank the products once with `ROW_NUMBER`, then **group by a `CASE`**: the name for ranks 1 to 3,
`'Other'` for the rest. Sorting by the smallest rank in each group keeps the top three in order and puts `Other`
(whose smallest rank is 4) last.

<!-- sql pg -->
```sql
WITH revenue AS (
  SELECT p.product_id, p.name, SUM(i.quantity * i.unit_price) AS revenue
  FROM order_items i
  JOIN products p ON p.product_id = i.product_id
  GROUP BY p.product_id, p.name
),
ranked AS (
  SELECT name, revenue, ROW_NUMBER() OVER (ORDER BY revenue DESC, name) AS rn
  FROM revenue
)
SELECT CASE WHEN rn <= 3 THEN name ELSE 'Other' END             AS product,
       SUM(revenue)                                                AS revenue,
       ROUND(100.0 * SUM(revenue) / (SELECT SUM(revenue) FROM revenue), 1) AS pct
FROM ranked
GROUP BY CASE WHEN rn <= 3 THEN name ELSE 'Other' END
ORDER BY MIN(rn);
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

| product | revenue | pct |
| --- | --- | --- |
| Office chair | 437.00 | 38.9 |
| Desk lamp | 122.50 | 10.9 |
| Tea kettle | 94.00 | 8.4 |
| Other | 469.00 | 41.8 |
<!-- /result -->

The percentages add up to 100 (give or take rounding), which is the point of keeping `Other`. `ROW_NUMBER` with
`name` as a tie-break guarantees exactly three named rows; with `RANK`, a tie for third place would name four.

**A.7 Exercise.** The two customers who spent the most (sum of `quantity * unit_price` over all their orders), by
name, and everyone else together as `'Everyone else'`, last. Guest orders (no customer) are left out. Return
`customer`, `customers` (how many customers the row stands for), `spent`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH spent AS (
      SELECT c.customer_id, c.name, SUM(i.quantity * i.unit_price) AS spent
      FROM orders o
      JOIN customers c   ON c.customer_id = o.customer_id
      JOIN order_items i ON i.order_id = o.order_id
      GROUP BY c.customer_id, c.name
    ),
    ranked AS (
      SELECT name, spent, ROW_NUMBER() OVER (ORDER BY spent DESC, customer_id) AS rn
      FROM spent
    )
    SELECT CASE WHEN rn <= 2 THEN name ELSE 'Everyone else' END AS customer,
           COUNT(*)   AS customers,
           SUM(spent) AS spent
    FROM ranked
    GROUP BY CASE WHEN rn <= 2 THEN name ELSE 'Everyone else' END
    ORDER BY MIN(rn);
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | customer | customers | spent |
    | --- | --- | --- |
    | Ana Silva | 1 | 289.00 |
    | Ben Okafor | 1 | 241.50 |
    | Everyone else | 7 | 542.00 |
    <!-- /result -->

    Group by `customer_id` (not by name) in the first step: the shop has two customers called Ana Silva, and grouping
    by name would add their spending together. The inner join to `customers` leaves out the guest order.

## A.8 Active customers over the last 7 days, for every day { #rolling-distinct }

**The situation.** "Weekly active users" on every day: for each day, how many **different** customers logged in
during that day and the 6 days before. This uses the shop's `logins` (1 to 10 March 2026).

**The technique.** The natural idea, `COUNT(DISTINCT customer_id) OVER (ORDER BY day ROWS 6 PRECEDING)`, is not
allowed: PostgreSQL does not accept `DISTINCT` in a window function. Instead, make a **calendar** of the days with
`generate_series`, join each day to every login in its 7-day range, and count distinct customers with an ordinary
`GROUP BY`. The calendar also gives a row to days with no logins at all.

<!-- sql pg -->
```sql
WITH days AS (
  SELECT CAST(d AS DATE) AS day
  FROM generate_series(DATE '2026-03-01', DATE '2026-03-10', INTERVAL '1 day') AS g(d)
)
SELECT d.day,
       COUNT(DISTINCT l.customer_id) AS active_7d
FROM days d
LEFT JOIN logins l
       ON l.login_date BETWEEN d.day - 6 AND d.day      -- this day and the 6 before
GROUP BY d.day
ORDER BY d.day;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 10 rows.</p>

| day | active_7d |
| --- | --- |
| 2026-03-01 | 2 |
| 2026-03-02 | 2 |
| 2026-03-03 | 3 |
| 2026-03-04 | 3 |
| 2026-03-05 | 3 |
| 2026-03-06 | 3 |
| 2026-03-07 | 3 |
| 2026-03-08 | 4 |
| 2026-03-09 | 4 |
| 2026-03-10 | 4 |
<!-- /result -->

`generate_series(start, stop, step)` makes one row per value; with dates and a 1-day interval, one row per day. The
`LEFT JOIN` keeps a day that has no login in its window, and `COUNT(DISTINCT l.customer_id)` gives it 0 (a count
ignores the NULL). A customer who logged in on three of the seven days counts once. On a big table this join grows
with days × logins per window, which is fine for daily numbers over a year.

**A.8 Exercise.** For each day in March 2026 that had orders: that day's order value (sum of `quantity *
unit_price`) and the value of the 7 days ending that day (that day and the 6 before, counting calendar days, not
rows). Return `order_date`, `day_value`, `value_7d`, sorted by date.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH daily AS (
      SELECT o.order_date, SUM(i.quantity * i.unit_price) AS day_value
      FROM orders o
      JOIN order_items i ON i.order_id = o.order_id
      GROUP BY o.order_date
    ),
    rolling AS (
      SELECT order_date, day_value,
             SUM(day_value) OVER (ORDER BY order_date
                                  RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW) AS value_7d
      FROM daily
    )
    SELECT order_date, day_value, value_7d
    FROM rolling
    WHERE order_date >= DATE '2026-03-01' AND order_date < DATE '2026-04-01'
    ORDER BY order_date;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 6 rows.</p>

    | order_date | day_value | value_7d |
    | --- | --- | --- |
    | 2026-03-01 | 181.00 | 181.00 |
    | 2026-03-05 | 36.00 | 217.00 |
    | 2026-03-09 | 49.00 | 85.00 |
    | 2026-03-18 | 49.50 | 49.50 |
    | 2026-03-22 | 25.00 | 74.50 |
    | 2026-03-25 | 43.00 | 68.00 |
    <!-- /result -->

    `RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW` covers the rows whose **date** is within 6 days
    before the current one, however many rows that is. `ROWS BETWEEN 6 PRECEDING` would take the 6 previous
    **rows**, which span more than a week when some days have no orders. Two traps: compute the window over all
    days **before** filtering to March (a `WHERE` in the same query runs first and would cut off the days of late
    February that early March needs), and remember that this is a sum, which windows allow, unlike `COUNT(DISTINCT)`.

## A.9 A balance that depends on the row before { #recursive-balance }

**The situation.** A prepaid wallet: deposits add money; a payment is **declined**, and changes nothing, when it is
larger than the balance at that moment. Show each transaction's outcome and the balance after it.

<!-- sql setup -->
```sql
CREATE TABLE wallet_tx (
  tx_id  INTEGER       PRIMARY KEY,
  amount NUMERIC(8,2)  NOT NULL          -- positive: deposit, negative: payment
);
INSERT INTO wallet_tx VALUES
  (1, 50.00), (2, -30.00), (3, -40.00), (4, 25.00), (5, -45.00), (6, -1.00), (8, 10.00);
CREATE TABLE points_tx (
  n      INTEGER PRIMARY KEY,
  amount INTEGER NOT NULL
);
INSERT INTO points_tx VALUES (1, 60), (2, 30), (3, 40), (4, -50), (5, 70), (6, -20);
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

**The technique: a recursive CTE that walks the rows in order.** A running `SUM` can't do this: whether payment 3 is
declined depends on the balance, and the balance depends on which earlier payments were declined. A recursive CTE
can carry a value from one row to the next. The **start** is the first transaction; the **step** joins the next
transaction to the row just made and decides with `CASE`. Number the rows first, since `tx_id` may have gaps (there
is no 7).

<!-- sql pg -->
```sql
WITH RECURSIVE tx AS (
  SELECT ROW_NUMBER() OVER (ORDER BY tx_id) AS n, tx_id, amount
  FROM wallet_tx
),
walk AS (
  SELECT n, tx_id, amount,
         CASE WHEN amount < 0 THEN 'declined' ELSE 'ok' END AS outcome,
         CASE WHEN amount < 0 THEN 0 ELSE amount END        AS balance
  FROM tx
  WHERE n = 1
  UNION ALL
  SELECT t.n, t.tx_id, t.amount,
         CASE WHEN w.balance + t.amount < 0 THEN 'declined' ELSE 'ok' END,
         CASE WHEN w.balance + t.amount < 0 THEN w.balance ELSE w.balance + t.amount END
  FROM walk w
  JOIN tx t ON t.n = w.n + 1                -- the next transaction
)
SELECT tx_id, amount, outcome, balance
FROM walk
ORDER BY n;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 7 rows.</p>

| tx_id | amount | outcome | balance |
| --- | --- | --- | --- |
| 1 | 50.00 | ok | 50.00 |
| 2 | -30.00 | ok | 20.00 |
| 3 | -40.00 | declined | 20.00 |
| 4 | 25.00 | ok | 45.00 |
| 5 | -45.00 | ok | 0.00 |
| 6 | -1.00 | declined | 0.00 |
| 8 | 10.00 | ok | 10.00 |
<!-- /result -->

The step runs again and again, each time on the one row it made last, until there is no next transaction. Payment
3 (40.00) is declined because only 20.00 is left; payment 6 (1.00) is declined at a balance of 0. Recursive CTEs
are slow on millions of rows (they go one row at a time), but in a test they are often the only way to express
"each row depends on the decision made for the row before".

**A.9 Exercise.** Loyalty points (`points_tx`, in the order of `n`, no gaps) can never go above **100**: points
earned beyond 100 are lost. Spending is never larger than the balance in this data. Return `n`, `amount`, `balance`
(after the transaction) and `lost` (points lost on that transaction, 0 if none), sorted by `n`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH RECURSIVE walk AS (
      SELECT n, amount,
             LEAST(100, amount)               AS balance,
             GREATEST(0, amount - 100)        AS lost
      FROM points_tx
      WHERE n = 1
      UNION ALL
      SELECT p.n, p.amount,
             LEAST(100, w.balance + p.amount),
             GREATEST(0, w.balance + p.amount - 100)
      FROM walk w
      JOIN points_tx p ON p.n = w.n + 1
    )
    SELECT n, amount, balance, lost
    FROM walk
    ORDER BY n;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 6 rows.</p>

    | n | amount | balance | lost |
    | --- | --- | --- | --- |
    | 1 | 60 | 60 | 0 |
    | 2 | 30 | 90 | 0 |
    | 3 | 40 | 100 | 30 |
    | 4 | -50 | 50 | 0 |
    | 5 | 70 | 100 | 20 |
    | 6 | -20 | 80 | 0 |
    <!-- /result -->

    `LEAST(100, x)` caps the balance; `GREATEST(0, x - 100)` is how much was above the cap. A running `SUM` would
    give 130 after transaction 3 and carry the 30 lost points into every later balance, which is why the cap needs
    the row-by-row walk.

## A.10 Every manager's whole team, all levels down { #org-rollup }

**The situation.** HR wants, for each manager, the size and the payroll of their **whole** team: the people who
report to them, the people who report to those, and so on. The shop's `employees` has `manager_id`.

**The technique: a recursive CTE of pairs.** Start with every direct pair (manager, employee). The step says: if B
is below A, then everyone who reports to B is also below A. When no new pairs come, the CTE holds every (boss,
person below) pair at every depth, and an ordinary `GROUP BY` boss adds them up.

<!-- sql pg -->
```sql
WITH RECURSIVE below AS (
  SELECT manager_id AS boss, employee_id
  FROM employees
  WHERE manager_id IS NOT NULL                  -- every direct report
  UNION ALL
  SELECT b.boss, e.employee_id                  -- people who report to someone already below the boss
  FROM below b
  JOIN employees e ON e.manager_id = b.employee_id
)
SELECT m.name             AS manager,
       COUNT(*)           AS team_size,
       SUM(e.salary)      AS team_payroll
FROM below b
JOIN employees m ON m.employee_id = b.boss
JOIN employees e ON e.employee_id = b.employee_id
GROUP BY m.employee_id, m.name
ORDER BY team_size DESC, manager;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 4 rows.</p>

| manager | team_size | team_payroll |
| --- | --- | --- |
| Maya Rossi | 11 | 917000 |
| Omar Aziz | 3 | 205000 |
| Tom Becker | 3 | 335000 |
| Kwame Mensah | 2 | 52000 |
<!-- /result -->

Maya Rossi is at the top, so everyone else is below her. `SUM(e.salary)` skips Leo Park, whose salary is NULL, while
`COUNT(*)` still counts him: the two numbers answer different questions. If the data could contain a loop (A
manages B, B manages A), this CTE would never stop; real code adds a depth limit or a path check, as in the
exercise.

**A.10 Exercise.** Every employee's **chain of command** from the top, as text like `Maya Rossi > Tom Becker >
Sam Lee`, and their depth (the top is 1). Return `employee`, `depth`, `chain`, sorted by `chain`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH RECURSIVE chain AS (
      SELECT employee_id, name, 1 AS depth, CAST(name AS TEXT) AS chain
      FROM employees
      WHERE manager_id IS NULL                       -- start at the top
      UNION ALL
      SELECT e.employee_id, e.name, c.depth + 1, c.chain || ' > ' || e.name
      FROM chain c
      JOIN employees e ON e.manager_id = c.employee_id
      WHERE c.depth < 20                             -- a safety stop if the data had a loop
    )
    SELECT name AS employee, depth, chain
    FROM chain
    ORDER BY chain;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 12 rows.</p>

    | employee | depth | chain |
    | --- | --- | --- |
    | Maya Rossi | 1 | Maya Rossi |
    | Kwame Mensah | 2 | Maya Rossi > Kwame Mensah |
    | Ella Novak | 3 | Maya Rossi > Kwame Mensah > Ella Novak |
    | Leo Park | 3 | Maya Rossi > Kwame Mensah > Leo Park |
    | Omar Aziz | 2 | Maya Rossi > Omar Aziz |
    | Nina Berg | 3 | Maya Rossi > Omar Aziz > Nina Berg |
    | Raj Patel | 3 | Maya Rossi > Omar Aziz > Raj Patel |
    | Zoe Martin | 3 | Maya Rossi > Omar Aziz > Zoe Martin |
    | Tom Becker | 2 | Maya Rossi > Tom Becker |
    | Lucia Gomez | 3 | Maya Rossi > Tom Becker > Lucia Gomez |
    | Priya Nair | 3 | Maya Rossi > Tom Becker > Priya Nair |
    | Sam Lee | 3 | Maya Rossi > Tom Becker > Sam Lee |
    <!-- /result -->

    This one walks **down** from the top, carrying the path so far and adding one name per level. `CAST(name AS
    TEXT)` matters: the start row decides the column's type, and a `VARCHAR(50)` column would be too short for a long
    chain (PostgreSQL stops with an error when the types of the two parts differ). Sorting by the chain lists each
    team right under its manager, like an org chart.

## A.11 Gaps written as ranges { #gaps-ranges }

**The situation.** Auditors ask which invoice numbers are missing, written as ranges ("7 to 9"), not one number per
row. A calendar asks the same question about time: when is nobody in a meeting?

<!-- sql setup -->
```sql
CREATE TABLE invoices (invoice_no INTEGER PRIMARY KEY);
INSERT INTO invoices VALUES (1), (2), (3), (5), (6), (10), (11), (12), (13), (14), (16), (17);
CREATE TABLE meetings (
  meeting_id INTEGER   PRIMARY KEY,
  starts_at  TIMESTAMP NOT NULL,
  ends_at    TIMESTAMP NOT NULL
);
INSERT INTO meetings VALUES
  (1, '2026-03-02 09:30', '2026-03-02 10:00'),
  (2, '2026-03-02 09:45', '2026-03-02 10:30'),
  (3, '2026-03-02 11:00', '2026-03-02 11:15'),
  (4, '2026-03-02 11:20', '2026-03-02 12:00'),
  (5, '2026-03-02 13:00', '2026-03-02 14:30'),
  (6, '2026-03-02 14:00', '2026-03-02 16:45');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

**The technique.** Put each number next to the **next** one with `LEAD`. Where the next number is more than one
higher, the numbers in between are missing: from `invoice_no + 1` to `next_no - 1`.

<!-- sql pg -->
```sql
WITH paired AS (
  SELECT invoice_no, LEAD(invoice_no) OVER (ORDER BY invoice_no) AS next_no
  FROM invoices
)
SELECT invoice_no + 1 AS missing_from,
       next_no - 1    AS missing_to
FROM paired
WHERE next_no - invoice_no > 1
ORDER BY missing_from;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

| missing_from | missing_to |
| --- | --- |
| 4 | 4 |
| 7 | 9 |
| 15 | 15 |
<!-- /result -->

The last invoice has no next one (`next_no` is NULL), and `NULL - 17 > 1` is not true, so it adds no row. Numbers
missing **before the first** invoice (if it were not 1) or after the last are outside what `LEAD` can see; when a
task cares, add the expected first and last numbers to the list with a `UNION ALL`.

**A.11 Exercise.** The free slots of **at least 30 minutes** on 2 March 2026 between 09:00 and 17:00, when nobody is
in a meeting. Meetings can overlap. Return `free_from`, `free_until`, `minutes`, sorted by `free_from`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    WITH m AS (
      SELECT starts_at, ends_at FROM meetings
      UNION ALL SELECT TIMESTAMP '2026-03-02 09:00', TIMESTAMP '2026-03-02 09:00'   -- the day starts
      UNION ALL SELECT TIMESTAMP '2026-03-02 17:00', TIMESTAMP '2026-03-02 17:00'   -- the day ends
    ),
    g AS (
      SELECT starts_at,
             MAX(ends_at) OVER (ORDER BY starts_at, ends_at
                                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS free_from
      FROM m
    )
    SELECT free_from,
           starts_at                                                  AS free_until,
           CAST(EXTRACT(EPOCH FROM starts_at - free_from) / 60 AS INTEGER) AS minutes
    FROM g
    WHERE starts_at - free_from >= INTERVAL '30 minutes'
    ORDER BY free_from;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | free_from | free_until | minutes |
    | --- | --- | --- |
    | 2026-03-02 09:00:00 | 2026-03-02 09:30:00 | 30 |
    | 2026-03-02 10:30:00 | 2026-03-02 11:00:00 | 30 |
    | 2026-03-02 12:00:00 | 2026-03-02 13:00:00 | 60 |
    <!-- /result -->

    Two ideas from earlier cases. The **running maximum** of the earlier end times (A.3) is when the room becomes
    free; comparing with only the previous meeting's end would invent a gap at 14:30, inside meeting 6. And two
    zero-length "meetings" at 09:00 and 17:00 act as **bookends**, so the free time before the first meeting and
    after the last one is found by the same rule. The gaps of 5 and 15 minutes are too short and are left out.

## A.12 One clean record from messy duplicates { #golden-record }

**The situation.** The same customer arrives from several sources with small differences: the email in capitals or
with a trailing space, a phone in one record, a city in another, a newer name. A **golden record** keeps one row
per customer, and for each field the **most recent value that is not missing**.

<!-- sql setup -->
```sql
CREATE TABLE customer_records (
  record_id  INTEGER     PRIMARY KEY,
  email      VARCHAR(50) NOT NULL,
  name       VARCHAR(50),
  phone      VARCHAR(20),
  city       VARCHAR(30),
  updated_at DATE        NOT NULL
);
INSERT INTO customer_records VALUES
  (1, 'ana@example.com',   'Ana',       '555-0101', NULL,      '2026-01-05'),
  (2, 'ANA@example.com ',  'Ana Silva', NULL,       'Toronto', '2026-02-10'),
  (3, 'ana@example.com',   NULL,        '555-0199', NULL,      '2026-03-01'),
  (4, 'ben@example.com',   'Ben',       NULL,       'Lagos',   '2026-01-20'),
  (5, 'ben@example.com',   'Benjamin',  NULL,       NULL,      '2026-02-01'),
  (6, 'cy@example.com',    'Cy',        NULL,       NULL,      '2026-02-02');
```

<!-- result -->
<p class="sql-tested">These tables load on PostgreSQL 16 and SQLite 3.53.</p>
<!-- /result -->

**The technique.** First a **matching key** that makes duplicates equal: `LOWER(TRIM(email))`. Then, per field,
"the latest value that is not NULL". `MAX` gives the largest, not the latest. In PostgreSQL,
`ARRAY_AGG(x ORDER BY updated_at DESC)` collects the group's values newest first, `FILTER (WHERE x IS NOT NULL)` leaves
out the missing ones, and `[1]` takes the first element of the array.

<!-- sql pg -->
```sql
SELECT LOWER(TRIM(email)) AS email,
       (ARRAY_AGG(name  ORDER BY updated_at DESC) FILTER (WHERE name  IS NOT NULL))[1] AS name,
       (ARRAY_AGG(phone ORDER BY updated_at DESC) FILTER (WHERE phone IS NOT NULL))[1] AS phone,
       (ARRAY_AGG(city  ORDER BY updated_at DESC) FILTER (WHERE city  IS NOT NULL))[1] AS city,
       COUNT(*) AS records
FROM customer_records
GROUP BY LOWER(TRIM(email))
ORDER BY email;
```

<!-- result -->
<p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

| email | name | phone | city | records |
| --- | --- | --- | --- | --- |
| ana@example.com | Ana Silva | 555-0199 | Toronto | 3 |
| ben@example.com | Benjamin | *NULL* | Lagos | 2 |
| cy@example.com | Cy | *NULL* | *NULL* | 1 |
<!-- /result -->

Ana's newest record (3) has no name and no city, so those come from older records: the name from record 2, the city
from record 2, the phone from record 3. Without the `FILTER`, the newest NULL would win. On databases without
arrays, the same answer takes one `ROW_NUMBER() OVER (PARTITION BY key ORDER BY updated_at DESC)` per field, each
over the rows where that field is not NULL, joined back together.

**A.12 Exercise.** For each customer (the same matching key): the number of records, the date of the first and of
the latest record, and the most recent known city, or `'unknown'` when no record has one. Return `email`, `records`,
`first_seen`, `last_seen`, `city`, sorted by `email`.

??? success "Answer"
    <!-- sql pg -->
    ```sql
    SELECT LOWER(TRIM(email)) AS email,
           COUNT(*)           AS records,
           MIN(updated_at)    AS first_seen,
           MAX(updated_at)    AS last_seen,
           COALESCE((ARRAY_AGG(city ORDER BY updated_at DESC) FILTER (WHERE city IS NOT NULL))[1],
                    'unknown') AS city
    FROM customer_records
    GROUP BY LOWER(TRIM(email))
    ORDER BY email;
    ```

    <!-- result -->
    <p class="sql-tested">Ran on PostgreSQL 16. 3 rows.</p>

    | email | records | first_seen | last_seen | city |
    | --- | --- | --- | --- | --- |
    | ana@example.com | 3 | 2026-01-05 | 2026-03-01 | Toronto |
    | ben@example.com | 2 | 2026-01-20 | 2026-02-01 | Lagos |
    | cy@example.com | 1 | 2026-02-02 | 2026-02-02 | unknown |
    <!-- /result -->

    When every city of a group is NULL, the `FILTER` leaves an empty array and `[1]` of it is NULL, which
    `COALESCE` turns into `'unknown'`. `MIN` and `MAX` of a date are the first and the latest, so they need no array.

## What to take away { #summary }

| When the task says | Reach for |
| --- | --- |
| "the price / status / owner **at the time** of" | a join on `valid_from <= d < valid_to` (A.1); build `valid_to` with `LEAD` (A.1 exercise) |
| "first in, first out", "allocate", "which lot" | running totals as ranges, and `LEAST(ends) - GREATEST(starts)` for the overlap (A.2) |
| "overlapping", "continuous", "covered", "free time" | a running `MAX` of earlier ends, a new-period flag, a running `SUM` (A.3, A.11) |
| "then", "after", "within an hour" | one CTE per step, each joined on `ts >` the step before (A.4) |
| "cohort", "retention", "came back" | first period per customer, a month number, a share of the cohort (A.5) |
| "the latest ... before each ..." | `LEFT JOIN LATERAL (... ORDER BY ts DESC LIMIT 1) ON TRUE` (A.6) |
| "split", "share equally" | divide by `COUNT(*) OVER (PARTITION BY ...)` (A.6 exercise) |
| "top N and the rest" | `ROW_NUMBER`, then `GROUP BY CASE WHEN rn <= N ...` (A.7) |
| "distinct ... over the last 7 days" | a calendar joined to a date range, then `COUNT(DISTINCT)` (A.8) |
| "sum over the last 7 **days**" | `RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW` (A.8 exercise) |
| "declined if", "capped at", "can't go below" | a recursive CTE that walks the rows (A.9) |
| "everyone under", "all levels", "chain" | a recursive CTE of pairs, or of paths (A.10) |
| "missing numbers", "gaps" | `LEAD(x) - x > 1` (A.11) |
| "merge duplicates", "latest known value" | a matching key, then `(ARRAY_AGG(x ORDER BY t DESC) FILTER (WHERE x IS NOT NULL))[1]` (A.12) |

**Next:** the timed tasks of the [Codility test prep](../../interview/codility/index.md), and the
[full mocks](../../interview/codility/full-mock-a.md).
