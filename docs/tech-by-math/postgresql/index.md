# PostgreSQL

*The math under a relational database, worked on PostgreSQL 16: the set algebra of joins, why an index lookup reads four pages out of hundreds of thousands, how the planner guesses row counts and picks a join order, and when two transactions running at once are safe. Every query and script on these pages was run, and the output shown is the real one.*

| Tutorial | The question it answers |
| --- | --- |
| [1. Joins are set math: relational algebra and NULL logic](01-Joins-Are-Set-Math.md) | Why does `NOT IN` return nothing when the list holds one NULL? |
| [2. Why an index is fast: B-tree height by hand](02-Why-an-Index-Is-Fast.md) | How is one row out of 100 million found by reading four or five pages? |
| [3. How the planner guesses: row estimates and join order](03-How-the-Planner-Guesses.md) | Why did the planner pick a plan that ran for an hour? |
| [4. When are two transactions "the same": serializability graphs](04-When-Transactions-Are-the-Same.md) | How can two people both book the last seat? |

The practical side is the [SQL course](../../databases/sql/index.md). [How a tutorial works](../index.md#how-a-tutorial-works).
