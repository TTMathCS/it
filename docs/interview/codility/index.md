# Codility test prep for data engineers

A Codility test is made of several short tasks, chosen by the employer for the role. This guide prepares for
the mix you heard about: **two SQL tasks and one Python task**. (Your own test may differ: the
number of tasks, the time limit and the allowed languages are shown on the test's intro page linked in your
invitation, per [Codility's candidate FAQ](https://app.codility.com/candidate-faq/).)

!!! abstract "Your test: 3 tasks in 150 minutes"
    Your invitation is for a **150-minute, 3-task** Codility test in Python or SQL. The page
    **[Your test: 3 tasks in 150 minutes](your-test.md)** explains what the invitation means, how to split the
    time, and has a **five-day plan** (Thursday 12 to Monday 16 November, about five hours a day, SQL first).

!!! tip "Do this first"
    Take Codility's free **[demo test](https://app.codility.com/demo/take-sample-test/)**. It is the real
    editor, you can repeat it as often as you like, and it shows the language versions Codility uses.

## What is here

| Page | What it is | Time |
|---|---|---|
| [Your test: 3 tasks in 150 minutes](your-test.md) | What your invitation means, the time split, the five-day plan | 15 min |
| [Full mock A](full-mock-a.md) | Your test's format: 3 tasks in 150 minutes, PostgreSQL (Sat 14) | 150 min |
| [Full mock B](full-mock-b.md) | 3 tasks in 150 minutes (Sun 15) | 150 min |
| [Full mock C](full-mock-c.md) | 3 tasks in 150 minutes, 1 SQL + 2 Python (Mon 16) | 150 min |
| [Cheat sheet](cheat-sheet.md) | The one page to read the day before and the hour before | 10 min |
| [How a Codility test works](how-codility-works.md) | Timer, Run, hidden tests, scoring | 15 min |
| [Plan for 2 SQL + 1 Python](test-day-plan.md) | Time split, reading a task, which SQL dialect to pick | 15 min |
| [Mock test 1](mock-test-1.md) | Timed rehearsal, 2 SQL + 1 Python | 80 min |
| [SQL practice set](sql-practice.md) | 53 tasks by pattern, easy to hard | as long as you have |
| [Python practice set](python-practice.md) | 52 tasks by technique, data wrangling and algorithms | as long as you have |
| [Advanced Python](python-advanced.md) | 10 hard tasks: heaps, Dijkstra, union-find, dynamic programming, BFS, LRU | as long as you have |
| [Advanced SQL: twelve hard cases](../../databases/sql/advanced-cases.md) | Prices over time, FIFO, overlapping periods, cohorts, attribution, recursive walks | as long as you have |
| [SQL practice: set 3](sql-practice-set-3.md) | 8 more tasks, PostgreSQL and SQLite | as long as you have |
| [PostgreSQL practice: account data](postgres-practice-bank.md) | 8 PostgreSQL tasks: DISTINCT ON, FILTER, date_trunc, generate_series | as long as you have |
| [PostgreSQL practice: harder patterns](postgres-practice-harder.md) | 8 harder PostgreSQL tasks: streaks, percentiles, pivots, recursion | as long as you have |
| [Python practice: set 3](python-practice-set-3.md) | 8 more data-wrangling tasks | as long as you have |
| [Mock test 2](mock-test-2.md) | Timed rehearsal | 70 min |
| [Mock test 3](mock-test-3.md) | Timed rehearsal, harder SQL | 75 min |
| [Mock test 4](mock-test-4.md) | The last rehearsal | 75 min |
| [Mock test 5](mock-test-5.md) | Extra rehearsal, SQL tested on SQLite | 80 min |
| [Mock test 6](mock-test-6.md) | Extra rehearsal, SQL tested on SQLite | 80 min |
| [Find the bug: 20 SQL drills](sql-bug-drills.md) | Spot the mistake in a query that looks right | 40 min |
| [Mock test 8](mock-test-8.md) | Full-length rehearsal like the real test: 2 PostgreSQL + 1 Python | 150 min |
| [Flash cards](flash-cards.md) | Quick questions for the last evening: SQL, Python, Databricks | 30 min |
| [Asked aloud](asked-aloud.md) | 30 SQL and pipeline questions an interviewer may ask out loud | 30 min |
| [The 15 most common mistakes](common-mistakes.md) | Read before the test | 10 min |
| [Codility's own tasks](codility-tasks.md) | All three free SQL tasks on Codility's real grader, the lessons for Python, and other sites to practise on | as long as you have |

Every task here has its **solution and explanation folded away**: try it first, then open the green box. Every
task is graded **Easy**, **Medium** or **Hard** and comes with its own tables, as a real test task does.

## Study plans

The date of the test is not known yet, so here are three plans. Pick the one that fits the time you have left.
Sit every mock **timed**, in one go, and only then open the solutions.

=== "1 day"

    About five hours.

    1. [Cheat sheet](cheat-sheet.md), [How a Codility test works](how-codility-works.md) and
       [Plan for 2 SQL + 1 Python](test-day-plan.md) (40 min).
    2. Codility's [demo test](https://app.codility.com/demo/take-sample-test/), once (30 min).
    3. [Mock test 1](mock-test-1.md), timed (80 min), then read every solution, including the wrong answers
       (30 min).
    4. From the [SQL practice set](sql-practice.md), the first two tasks of groups A, B, C and D (about 90 min).
    5. [The 15 most common mistakes](common-mistakes.md), then the cheat sheet again before you sleep.

=== "3 days"

    About three hours a day.

    * **Day 1.** The cheat sheet, how the test works, the test-day plan, Codility's demo test. Then
      [Mock test 1](mock-test-1.md), timed, and its solutions.
    * **Day 2.** [SQL practice](sql-practice.md) groups A to D (the Easy and Medium tasks first), and Codility's
      three [SQL tasks](codility-tasks.md#sql-exercise-6) on the real grader.
    * **Day 3.** [Python practice](python-practice.md) groups A to D, then [Mock test 2](mock-test-2.md), timed.
      Finish with [the 15 most common mistakes](common-mistakes.md) and the cheat sheet.

=== "1 week"

    About two hours a day.

    * **Day 1.** The cheat sheet, how the test works, the test-day plan, Codility's demo test, then
      [Mock test 1](mock-test-1.md).
    * **Day 2.** [SQL practice](sql-practice.md) groups A and B, and Codility's SqlSum and SqlEventsDelta.
    * **Day 3.** SQL practice groups C and D, and Codility's SqlWorldCup. Any topic that felt shaky: the matching
      chapter of the [SQL course](../../databases/sql/index.md).
    * **Day 4.** [Python practice](python-practice.md) groups A and B, and Codility lessons 1 to 4 (the rest as time allows;
      see [the order of work](codility-tasks.md)).
    * **Day 5.** [Mock test 2](mock-test-2.md). Then Python practice groups C and D.
    * **Day 6.** [Mock test 3](mock-test-3.md). Then SQL practice groups E to G and Python groups E to I, as time allows.
    * **Day 7.** [Mock test 4](mock-test-4.md), [the 15 most common mistakes](common-mistakes.md), the cheat
      sheet. Stop early and rest.

## How every answer was checked

* **SQL:** each answer was run on **PostgreSQL 16** and **SQLite 3.53**, the two SQL dialects Codility offers
  in its own SQL practice tasks ("SQL (PostgreSQL)" and "SQL (SQLite)", seen on
  [Codility's SQL exercise](https://app.codility.com/programmers/trainings/6/) on 11 Nov 2026). Each was checked
  on the example, on hand-made edge cases, on 150 to 200 random small tables compared with a separate Python
  answer, and on a large table, timed. Every "common wrong answer" shown was run too, and the guide names the
  case it fails.
* **Python:** each answer was run on Python 3.13 with the examples, edge cases, hundreds of random inputs
  compared with a slow but obviously correct answer, and the largest input the limits allow, timed. Each
  solution states its cost (for example O(N log N)) and names the slow answer that would fail the large
  hidden tests; where that slow answer is shown, it was run and timed.
* **This guide could not check which Python version Codility runs;** the editor shows it (open the demo test to
  see it). The answers here use only plain Python 3 that works on any recent version.

!!! note "About Codility's own tasks"
    Codility publishes free practice tasks. This guide links to them and describes them in its own words; it
    does not copy their text. All tasks written out here are original, in the same style.

## How this guide and the SQL course fit together

The [SQL course](../../databases/sql/index.md) teaches each topic from the start (joins, grouping, window
functions and so on), with exercises after each chapter and two practice sets on its sample shop database:
[Practice set A](../../databases/sql/30-Practice-Set-A.md) and
[Practice set B](../../databases/sql/31-Practice-Set-B.md). This guide is the **test-style** part: every task
has its own fresh tables, an exact result to match and a time to aim for, as on Codility. Learn a topic in the
course, then practise it here.
