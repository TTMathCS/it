# Plan for 2 SQL + 1 Python

## Split the time

Your time limit is shown on the intro page (it is set by the employer). As a starting plan, split it like this
and adjust once you have read the tasks:

| Part | Share | In a 90-minute test | In a 120-minute test |
|---|---|---|---|
| Read all three tasks | 5% | 5 min | 5 min |
| SQL task 1 | 25% | 22 min | 30 min |
| SQL task 2 | 25% | 22 min | 30 min |
| Python task | 40% | 36 min | 48 min |
| Final check of all three | 5% | 5 min | 7 min |

If one task is stuck for more than about ten minutes past its share, leave a working partial answer, move on,
and come back. A partial answer that runs earns the hidden tests it passes; a query with a syntax error earns
nothing.

## Read a SQL task like a checklist

Before you type, write these five lines in a comment at the top of the editor:

```sql
-- OUTPUT: which columns, in which order, with which names?
-- ROWS:   one row per what? ("for each ...", "only ... that have ...", "including ... with none")
-- SORT:   by what, which direction, and the tie-breaker?
-- TRAPS:  NULLs? duplicates? empty groups? ties? dates?
-- DIALECT: PostgreSQL or SQLite?
```

Then build the query **one step at a time**, running it after each step:

1. `FROM` and the joins. Run it with `SELECT *` and look at the rows.
2. `WHERE` filters.
3. `GROUP BY` and the aggregates, then `HAVING`.
4. Window functions, in a CTE (`WITH step AS (...)`), if the task needs "per group" ranking or "previous row".
5. The final `SELECT` list with the right names, and `ORDER BY`.

Then add your own test rows (see "Write your own edge cases" in every solution of this guide).

## Which SQL dialect?

**Default: choose PostgreSQL**, if the task lets you pick. Use SQLite only if it is the one you have actually
used and PostgreSQL is not. The reasons, all from running the answers in this guide on both:

1. **PostgreSQL stops on mistakes that SQLite accepts quietly.** A column that is neither grouped nor
   aggregated, or a `SELECT` alias used in `WHERE`, is an error in PostgreSQL, so you see it when you press Run.
   SQLite returns *some* answer, and the hidden tests find the bug instead of you.
2. **Dates are real dates.** In PostgreSQL `d + 1` is the next day and `d2 - d1` a number of days. In SQLite a
   date is text: you need `date(d, '+1 day')` and `julianday()`, and `CAST('2026-03-01 10:00' AS TIMESTAMP)`
   gives the number 2026.
3. **The SQLite version Codility runs is not known.** Several things in SQLite exist only from a certain version
   (window functions 3.25, `NULLS FIRST` 3.30, `FULL JOIN` and `IS DISTINCT FROM` 3.39, `STRING_AGG` 3.44).
   They have been in PostgreSQL for many years.

Two PostgreSQL habits to keep: `ROUND(x, 2)` needs a `numeric` (write `100.0 * ...` or `CAST(x AS NUMERIC)`),
and dividing by zero is an error, so write `NULLIF(divisor, 0)`.

The table shows what differs. Every cell was checked on PostgreSQL 16 and SQLite 3.53.

| What you want | PostgreSQL | SQLite |
|---|---|---|
| Replace NULL with a value | `COALESCE(x, 0)` | `COALESCE(x, 0)` (also `IFNULL`) |
| SQL Server's `ISNULL(x, 0)` | error | error |
| First N rows | `LIMIT n` | `LIMIT n` |
| SQL Server's `TOP n` | error | error |
| 5 divided by 2 | `5/2` gives 2; `5 * 1.0 / 2` gives 2.5 | the same |
| Round to 2 places | `ROUND(numeric, 2)`; on a float it is an error, so `ROUND(x::numeric, 2)` | `ROUND(x, 2)` |
| `CAST(7.9 AS INTEGER)` | 8 (rounds) | 7 (cuts off) |
| Yesterday | `d - 1` or `d - INTERVAL '1 day'` | `date(d, '-1 day')` |
| Days between two dates | `d2 - d1` (an integer) | `julianday(d2) - julianday(d1)` |
| Year of a date | `EXTRACT(YEAR FROM d)` | `strftime('%Y', d)` (text) |
| `CAST('2026-03-01 10:00' AS TIMESTAMP)` | a timestamp | **2026**: SQLite has no timestamp type; keep dates as text |
| Bigger of two values | `GREATEST(a, b)` | `MAX(a, b)` |
| Join text | `a \|\| b` or `CONCAT(a, b)` | the same |
| Glue a group's text together | `STRING_AGG(x, ',')` | `GROUP_CONCAT(x, ',')`; `STRING_AGG` from 3.44 |
| Case-insensitive match | `ILIKE`, or `LOWER(a) LIKE LOWER(b)` | `LIKE` already ignores case for A to Z |
| Where NULLs go in `ORDER BY x` | last (first with `DESC`) | first (last with `DESC`) |
| Control NULL position | `NULLS FIRST` / `NULLS LAST` | the same (SQLite 3.30 and newer) |
| Column not in `GROUP BY` | error | allowed (returns an arbitrary row's value: a hidden bug) |
| Use a `SELECT` alias in `WHERE` | error | allowed |
| Use a `SELECT` alias in `ORDER BY` | allowed | allowed |
| Divide by zero | error "division by zero" | `NULL` |
| "Different, treating NULLs as equal" | `a IS DISTINCT FROM b` | the same from SQLite 3.39; before that `a IS NOT b` |
| `FULL OUTER JOIN` | yes | from SQLite 3.39 |
| `ORDER BY name` after a `UNION` | works | can fail with "does not match any column" (seen with a three-part `UNION ALL` of joins); give the column a name with `AS` in the first `SELECT` |
| A list of days between two dates | `generate_series(a, b, INTERVAL '1 day')` or a recursive CTE | a recursive CTE with `date(d, '+1 day')` |

The safe habits that work everywhere: `COALESCE`, `LIMIT`, `CASE WHEN`, `||`, `* 1.0` before dividing, aliases
only in `ORDER BY`, and every non-aggregated column in `GROUP BY`.

## Python: the order of work

1. Read the limits. Decide the target cost (see the table in the [cheat sheet](cheat-sheet.md)).
2. Write the plainest correct idea in a comment, then the code.
3. Run the example. Add your own tests: empty, one item, all equal, the largest values.
4. If the plain idea is O(N²) and N can be 100,000, improve it now: sorting, a `dict`, a `set`, prefix sums,
   two pointers, or a sliding window.
5. Return the value; remove debug `print`s.
