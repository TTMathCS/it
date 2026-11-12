# Your test: 3 tasks in 150 minutes

This page is about one real invitation: a **150-minute Codility assessment with three tasks** for an
analytics engineering role, in **Python or SQL** (PostgreSQL or another SQL dialect). It says what the
invitation means in practice, how to split the time, and gives a **five-day plan** from Thursday 12 to Monday
16 November, about five hours a day, with most of the time on SQL.

Everything on this page is preparation. Nothing here is meant to be open or used during the test itself.

## What the invitation says, and what it means

| The invitation says | What it means for you |
|---|---|
| **3 tasks, 150 minutes**, solve them in any order | About **45 minutes a task** with time left to read and check. The limit is for the whole test, not per task. Longer than the 70 to 80 minute mocks in this guide, so the tasks are likely harder than a warm-up: expect at least one Medium-Hard SQL task (window functions, gaps, dates) and one Python task where speed matters. |
| **No option to pause** | Block 2 hours 45 minutes with nothing else on: no calls, phone away. Start only when you are ready; the clock starts when you press Start. |
| Your solution must handle **all corner cases and large input**; passing the example test **does not** mean it is correct; the example is **not part of the score** | The score comes from hidden tests. Before you submit, write your own small tests: empty table or list, one row, ties, NULLs, duplicates, dates on a boundary. For Python, think about the biggest N in the limits and make sure the answer is O(N) or O(N log N), not O(N²). For SQL on large tables, prefer joins, `GROUP BY` and window functions to a subquery that runs once per row. |
| **Write pseudocode if you can't complete the task** in the language; "even if the answer doesn't compile, that is fine, we would like to see the logical approach" | Never leave a task empty. If you are stuck, write your plan as comments in the editor (the steps, the edge cases, the idea), then code as much of it as you can. Code that runs still earns more: the hidden tests only count what runs. Get a simple correct answer running first, then make it faster. |
| Languages: **Python, SQL, sql and sql-postgres**; "availability depends on the task", "the choice might be limited" | Each task has its own language menu. **sql-postgres** is PostgreSQL. Which engine plain "sql" stands for is not said in the invitation; on Codility's own SQL practice page the two SQL choices are "SQL (PostgreSQL)" and "SQL (SQLite)", so it is probably SQLite (not confirmed). **Pick PostgreSQL whenever you can** (reasons in [Plan for 2 SQL + 1 Python](test-day-plan.md#which-sql-dialect)). Read the task's menu before you type. |
| **Keyboard and mouse actions are tracked** and shown to the hiring team; no video or audio | Everything you type in the editor is recorded and a person may replay it. Type your answer in the Codility editor, think in comments there, and test with the Run button. Follow the [Code of Honour](https://app.codility.com/code-of-honour/): your own work, no outside help. |
| **Take the demo test** first | Do it today, and once more on Monday: [Codility's demo test](https://app.codility.com/demo/take-sample-test/). It is the real editor, with Run and your own test cases. Learn where the language menu, Run, the test-case box and Submit are, so none of it costs time on Tuesday. |
| You get **feedback with a score** at the end | The score is the share of hidden tests passed, per task. [Codility's example feedback](https://app.codility.com/public-report-feedback/) shows what it looks like. |
| If the browser closes, **use the invitation link** to get back | Your code is saved as you type. The timer keeps running while you are away. |
| Special arrangements: tell the test sponsor; technical problems: support@codility.com | Ask before the test, not during it. |

## Splitting 150 minutes

| Part | Minutes | What you do |
|---|---|---|
| Read all three tasks | 10 | Read each one fully. Note the output columns, the sort order and the limits. Decide the order: start with the one you see the clearest path for. |
| First task | 40 | Running answer first, then edge cases, then speed. |
| Second task | 40 | The same. |
| Third task | 40 | The same. |
| Check all three | 15 | Re-run each with your own edge cases. Re-read each task's wording against your output (names, order, sort, rounding). |
| Spare | 5 | Something always takes longer. |

**The 15-minute rule.** If you have been stuck on one task for 15 minutes past its share, leave the best
running answer you have (or your plan in comments), move to the next task, and come back at the end.

**Submit is final.** Do not submit a task until you have checked it; you can move between tasks freely without
submitting.

## The five-day plan

Five hours a day, most of it on SQL, and three full timed rehearsals in the real format: three tasks in 150
minutes. The three full mocks (A, B and C) and a new set of harder SQL and Python tasks are being added to this
guide on Thursday and Friday; their links will appear here.

=== "Thu 12"

    **Today: get the feel of the test and wake up the SQL.** About 5 hours.

    | Time | What |
    |---|---|
    | 30 min | This page, the [cheat sheet](cheat-sheet.md) and [Plan for 2 SQL + 1 Python](test-day-plan.md) |
    | 30 min | [Codility's demo test](https://app.codility.com/demo/take-sample-test/), once, to learn the screen |
    | 90 min | Learning: SQL fast track, [Day 1](../../databases/sql/fast-track.md#day-1) steps 3 to 6 (the order a query runs in, NULL, GROUP BY and HAVING, joins). Run the examples. |
    | 2 h | [SQL practice](sql-practice.md) group A (tasks 1 to 8) and the first half of group B. Try each one before you open the answer, and write your own edge cases. |

=== "Fri 13"

    **Window functions and CTEs: the heart of analytics SQL.** About 5 hours.

    | Time | What |
    |---|---|
    | 90 min | Learning: SQL fast track [Day 1](../../databases/sql/fast-track.md#day-1) steps 7 and 8 (anti joins, subqueries and CTEs), then [Day 2](../../databases/sql/fast-track.md#day-2) (window functions) |
    | 2 h | [SQL practice](sql-practice.md): rest of group B, then group C (ranking, previous rows, running totals) |
    | 30 min | Codility's three free SQL tasks on the real grader ([list](codility-tasks.md#sql-exercise-6)) |
    | 1 h | [Python practice](python-practice.md) group A (dictionaries) and group D (prefix sums, sliding windows) |

=== "Sat 14"

    **First full rehearsal.** About 5 hours.

    | Time | What |
    |---|---|
    | 150 min | **Full mock A** (three tasks, 150 minutes), timed, in one go, on paper or in a plain editor; then check each answer in its Try it box |
    | 60 min | Read every solution of the mock, including the wrong answers. Write down each mistake. |
    | 90 min | [SQL practice](sql-practice.md) group D (sequences, gaps and time) |

=== "Sun 15"

    **Second full rehearsal, then the hard patterns.** About 5 hours.

    | Time | What |
    |---|---|
    | 150 min | **Full mock B**, timed |
    | 45 min | Its solutions and your mistakes list |
    | 75 min | [SQL practice](sql-practice.md) groups E, F and G: pick the patterns that felt weakest; [Python practice](python-practice.md) group C (sorting and intervals) |
    | 30 min | [The 15 most common mistakes](common-mistakes.md) |

=== "Mon 16"

    **Last rehearsal, then rest.** About 3 to 4 hours.

    | Time | What |
    |---|---|
    | 150 min | **Full mock C**, timed, in the morning |
    | 30 min | Its solutions; your mistakes list from all three mocks |
    | 20 min | [Codility's demo test](https://app.codility.com/demo/take-sample-test/) once more, the [cheat sheet](cheat-sheet.md) |
    | | Stop early. Sleep well. |

=== "Tue 17"

    **Test day.**

    * No new material. Ten minutes on the [cheat sheet](cheat-sheet.md) and one easy task you have solved before,
      to warm up.
    * Laptop on power, a stable connection, a quiet room, water, 2 hours 45 minutes free.
    * Read all three tasks first. Running answer first, edge cases second, speed third. Pseudocode in comments
      if stuck. Check before you submit.

## A checklist for every task

=== "SQL"

    1. **Output:** which columns, in which order, with which names? (Codility checks the order of columns.)
    2. **Rows:** one row per what? Must groups with no rows still appear (`LEFT JOIN`, `COALESCE(…, 0)`)?
    3. **Sort:** by what, which direction, what breaks ties?
    4. **Traps:** NULLs, duplicates, ties, empty tables, dates on a boundary, integer division, rounding.
    5. **Build it in steps** in a `WITH` query, running each step.
    6. **Test** with your own rows: add an `INSERT` of an edge case if the task's editor allows test data;
       otherwise reason through each trap above against your query.
    7. **Speed:** no subquery that runs once for every row of a large table when a join or a window does it once.

=== "Python"

    1. **Read the limits.** N up to 100,000 or more means O(N) or O(N log N).
    2. **Write the plain idea in a comment**, then the code.
    3. **Run the example**, then your own: empty input, one item, all equal, negatives, the largest values.
    4. **Speed:** replace a loop inside a loop with a `dict`, a `set`, sorting, prefix sums, two pointers or a
       sliding window.
    5. **Keep the function signature** as given, and return the value (no `print`).

## Where the details come from

The test's format, rules and wording come from the invitation you received (12 November 2026). Codility's
general rules (the timer, Run, hidden tests, scoring) are on the page [How a Codility test works](how-codility-works.md),
from [Codility's candidate FAQ](https://app.codility.com/candidate-faq/).
