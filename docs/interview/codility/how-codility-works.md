# How a Codility test works

Everything on this page comes from Codility's own pages, read on 11 November 2026: the
[candidate FAQ](https://app.codility.com/candidate-faq/) and the
[SQL practice exercise](https://app.codility.com/programmers/trainings/6/). Where something is not stated
there, this page says **unknown**.

## The invitation and the clock

* You get an e-mail with a link. The link opens an **intro page** that shows the number of tasks, the
  languages you may use and the time limit.
* Until you press **Start**, you can leave and come back. Once you start, **the timer cannot be paused or
  stopped**, so plan to do the whole test in one sitting. You must start within the window the employer set.
* Tests "typically last between half an hour and two hours". The limit you see is for the **whole test**, not
  per task.
* The time you take is **not part of the automated score**; Codility says tests are designed to give enough
  time without rushing.
* When time runs out, the code in the editor is **submitted automatically** and the test ends.

## The editor

* Everything happens in the browser; no software to install (unless your employer uses the Codility app).
  Use a laptop or desktop: Codility says phones and tablets are not supported.
* Tasks usually ask you to write or change a **short program (usually 10 to 20 lines)** or a query.
* **Keep the function signature** exactly as given (`def solution(A):` and so on). You may add helper
  functions and imports. Some tasks limit how much of the starting code you may change; then the task is about
  making as few edits as possible.
* **Run** compiles your code and runs it on the example test case. You can **add your own test cases**.
  You can run as many times as you like.
* "OK" after Run does **not** mean the task is solved; it only checks the example.
* Codility saves your code automatically. You can move between tasks freely. **Submit** a task when you are
  sure: after that you cannot change it.
* If the test allows it, you may write in your own editor and paste the code back; Run it in Codility
  afterwards to make sure it still works. The language version Codility uses is shown in its interface.
* Use only the **standard library** of the language unless the task says otherwise.
* You do **not** need to check that the inputs obey the task's stated assumptions.

## How you are scored

* After you finish, Codility runs your solutions against **multiple test cases** that check **correctness**
  ("whether your code handles corner cases") and **scalability** ("whether your code remains practical as the
  data size grows").
* Your code must compile (or, for SQL, run) to earn anything.
* Points come from the hidden tests your solution passes. **Style** is not part of the automated score in most
  tasks, but some tasks score it and the employer may read your code.
* Whether you see your results depends on the employer.
* Some tests track your screen or camera; it depends on the employer's policy.

## SQL tasks

* In Codility's own SQL practice tasks, the **language menu offers "SQL (PostgreSQL)" and "SQL (SQLite)"**.
  An employer's test may restrict this; read which dialect your task states before you type.
* The practice task shows the table definition (`CREATE TABLE ...`), example rows and the rows your query should
  return. One of them notes that **the column names do not matter but their order does**. Do not rely on that:
  use the names and order the task asks for.
* The SQLite version Codility runs is **unknown**. Window functions (`ROW_NUMBER`, `LAG` and so on) need SQLite
  3.25 or newer, `FULL OUTER JOIN` needs 3.39 or newer and `STRING_AGG` 3.44 or newer. If your SQLite query
  fails on one of these, try the PostgreSQL dialect or a different way to write it.

## Codility's free practice

* **[Demo test](https://app.codility.com/demo/take-sample-test/)**: the real test screen, as often as you like.
* **[Lessons](https://app.codility.com/programmers/lessons/1-iterations/)**: 17 short lessons, each with
  reading and practice tasks (arrays, counting, prefix sums, sorting, stacks, and more). The Python practice set
  in this guide links to the most useful ones.
* **[Exercise 6: SQL](https://app.codility.com/programmers/trainings/6/)**: three SQL tasks, rated elementary,
  easy and medium. The SQL practice set links to each and says which skill it practises.
