---
title: SQL, from beginner to expert
---

# SQL, from beginner to expert

*SQL is the language for asking questions of data kept in tables. It is fifty years old and still the first thing a
data engineer is tested on. This course goes from the first SELECT to window functions, query plans and data
modelling, with a sample shop database used in every chapter. Every example has been run on PostgreSQL and on SQLite,
and the table under it is what the database really returned.*

## Why PostgreSQL and SQLite

They are the two SQL choices Codility offers in its practice SQL tasks (seen on Codility's own practice page,
11 Nov 2026; a real employer's test lists its languages on its first page, so check there). They are also free and
easy to install. Almost everything here is **standard SQL** and works on MySQL, SQL Server and Oracle too; where a
database does it differently, the chapter says so, and [chapter 28](28-Dialect-Differences.md) collects the
differences. Results on MySQL, SQL Server and Oracle have not been tested here.

## How to use it

- **Preparing for an interview soon?** Follow the [fast track](fast-track.md). It picks the chapters that matter
  most and puts them in the order to read them.
- **Coming back after a while?** Read the [cheat sheet](cheat-sheet.md), then the chapters where it felt rusty.
- **Starting out?** Read in order from chapter 1.
- **Practise on the examples.** Most examples are a **Task** box: the task is written at the top of the box as
  `--` comments, with the columns the answer must return. Write your query under it, press **Check**, and only
  then open **Solution** to compare.
- **Try everything, right on the page.** Every example has a **Run this** button and every exercise a **Try it
  here** box with **Check**: a real PostgreSQL running inside your browser, loaded with the
  [sample database](sample-database.md). Change the examples and see what happens. There is a free
  [playground](sample-database.md#playground) too, and you can still load the database on your own computer.
  How the **Run** buttons on these pages run a real PostgreSQL inside your browser, and whether that is safe, is
  explained in [WebAssembly: real programs inside a web page](../../programming/webassembly/index.md).

## How a chapter works

- **The opening box** says what the chapter covers and what you need first.
- **Every query is followed by its result.** The small line above the result says where it ran: "Ran on PostgreSQL
  16 and SQLite 3.53: same rows on both." Where the two differ, both versions are shown in tabs.
- **Interview tips** name the usual wrong answer, run it, and show it failing on the sample data.
- **Practice** ends each chapter: questions from easy to hard. The answer, its result and the explanation are folded
  under each one. Try first, then open it.

## Contents

| Part | Chapters |
| --- | --- |
| **Start** | [Fast track](fast-track.md) · [Cheat sheet](cheat-sheet.md) · [Which technique does this wording ask for?](which-technique.md) · [The sample database](sample-database.md) |
| **I. Foundations** | [1. Tables, rows and keys](01-Tables-Rows-and-Keys.md) · [2. SELECT, WHERE, ORDER BY, LIMIT](02-Select-Where-Order-By-Limit.md) · [3. The order a query really runs in](03-The-Order-a-Query-Runs-In.md) · [4. Expressions: CASE, numbers, dates, CAST](04-Expressions-Case-Numbers-Dates-Cast.md) · [5. Text functions and pattern matching](05-Text-Functions-and-Pattern-Matching.md) · [6. NULL and three-valued logic](06-Null-and-Three-Valued-Logic.md) |
| **II. Interview core** | [7. Aggregation: GROUP BY and HAVING](07-Aggregation-Group-By-Having.md) · [8. Joins: inner, left, right, full, cross](08-Joins-Inner-Left-Right-Full-Cross.md) · [9. Self, semi and anti joins](09-Self-Semi-and-Anti-Joins.md) · [10. Subqueries](10-Subqueries.md) · [11. CTEs and recursive CTEs](11-CTEs-and-Recursive-CTEs.md) · [12. UNION, INTERSECT, EXCEPT](12-Set-Operations.md) · [13. Window functions: ranking](13-Window-Functions-Ranking.md) · [14. Window functions: LAG, LEAD and running totals](14-Window-Functions-Lag-Lead-Running-Totals.md) · [15. Classic interview patterns](15-Classic-Interview-Patterns.md) · [16. Dates and time series](16-Dates-and-Time-Series.md) |
| **III. Changing data and designing tables** | [17. INSERT, UPDATE, DELETE, MERGE](17-Insert-Update-Delete-Merge.md) · [18. CREATE TABLE, types, constraints](18-Create-Table-Types-Constraints.md) · [19. Data modelling](19-Data-Modelling.md) · [20. Transactions and isolation](20-Transactions-and-Isolation.md) · [21. Views and materialized views](21-Views-and-Materialized-Views.md) · [22. Duplicates and incremental loads](22-Duplicates-and-Incremental-Loads.md) · [23. Data quality checks](23-Data-Quality-Checks.md) · [24. JSON and arrays](24-JSON-and-Arrays.md) |
| **IV. Expert** | [25. Indexes and EXPLAIN](25-Indexes-and-Explain.md) · [26. Making slow queries fast](26-Making-Slow-Queries-Fast.md) · [27. GROUPING SETS, ROLLUP, CUBE, LATERAL](27-Grouping-Sets-Rollup-Cube-Lateral.md) · [28. Dialect differences](28-Dialect-Differences.md) · [29. Safe SQL](29-Safe-SQL.md) |
| **V. Practice** | [30. Practice set A](30-Practice-Set-A.md) · [31. Practice set B](31-Practice-Set-B.md) · [32. Mock tests](32-Mock-Tests.md) · [SQL drills: quick reps](drills.md) · [Analytics workshop: payments and website visits](analytics-workshop.md) · [Advanced SQL: twelve hard cases](advanced-cases.md) · [Glossary](glossary.md) |

Codility-style tasks on other small databases (employees, sensor readings, logins, payments, flights) are in the
[Codility test prep](../../interview/codility/index.md) guide under Interview prep.
