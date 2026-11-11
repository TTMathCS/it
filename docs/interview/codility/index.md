# Codility test prep for data engineers

A Codility test is made of several short tasks, chosen by the employer for the role. This guide prepares for
the mix you heard about: **two SQL tasks and one Python task**. (Your own test may differ: the
number of tasks, the time limit and the allowed languages are shown on the test's intro page linked in your
invitation, per [Codility's candidate FAQ](https://app.codility.com/candidate-faq/).)

!!! tip "Do this first"
    Take Codility's free **[demo test](https://app.codility.com/demo/take-sample-test/)**. It is the real
    editor, you can repeat it as often as you like, and it shows the language versions Codility uses.

## How to use this guide

| Step | Page | Time |
|---|---|---|
| 1 | [Cheat sheet](cheat-sheet.md): the one page to read the day before and the hour before | 10 min |
| 2 | [How a Codility test works](how-codility-works.md): timer, Run, hidden tests, scoring | 15 min |
| 3 | [Plan for 2 SQL + 1 Python](test-day-plan.md): time split, reading a task, choosing the SQL dialect | 15 min |
| 4 | [Mock test 1](mock-test-1.md): sit it timed, 80 minutes, then open the solutions | 80 min |
| 5 | [SQL practice set](sql-practice.md): 28 tasks by pattern, easy to hard | as long as you have |
| 6 | [Codility's own tasks](codility-tasks.md): the real grader, with links and hints | as long as you have |
| 7 | [Python practice set](python-practice.md): 24 tasks by technique | as long as you have |
| 8 | [Mock test 2](mock-test-2.md): a second timed rehearsal | 70 min |
| 9 | [The 15 most common mistakes](common-mistakes.md): read before the test | 10 min |

Every task here has its **solution and explanation folded away**: try it first, then open the green box.

## How every answer was checked

* **SQL:** each answer was run on **PostgreSQL 16** and **SQLite 3.53**, the two SQL dialects Codility offers
  in its own SQL practice tasks ("SQL (PostgreSQL)" and "SQL (SQLite)", seen on
  [Codility's SQL exercise](https://app.codility.com/programmers/trainings/6/) on 11 Nov 2026). Each was checked
  on the example, on hand-made edge cases, on 150 to 200 random small tables compared with a separate Python
  answer, and on a large table, timed. Every "common wrong answer" shown was run too, and the guide names the
  case it fails.
* **Python:** each answer was run on Python 3.13 with the examples, edge cases, hundreds of random inputs
  compared with a slow but obviously correct answer, and the largest input the limits allow, timed.
* **The Python version Codility runs is not known from outside;** the FAQ says it is shown in the Codility
  interface. The answers here use only plain Python 3 that works on any recent version.

!!! note "About Codility's own tasks"
    Codility publishes free practice tasks. This guide links to them and describes them in its own words; it
    does not copy their text. All tasks written out here are original, in the same style.

For the SQL itself (joins, grouping, window functions and so on), the
[SQL course](../../databases/sql/index.md) teaches each topic from the start; this guide links to its chapters.
