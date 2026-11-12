---
title: The data engineering core
---

# The data engineering core

*Eight tutorials on the math under the systems a data engineer works with: relational databases, query planners, transactions, column files, Apache Spark and Apache Kafka. They sit under the [SQL course](../../databases/sql/index.md) and the [Databricks book](../../data-engineering/databricks/index.md): those teach how to use the systems, these teach why they behave as they do.*

## How a tutorial works

1. **The question.** One real situation, such as "one Spark task runs 40 minutes while 199 take 2".
2. **The idea in plain words**, with a drawing.
3. **The math by hand.** A tiny example you can do on paper, every step shown.
4. **Why it is true.** A short proof or argument, with its assumptions stated. A rule of thumb is labelled as one.
5. **See it in the real system.** Queries and scripts that were run, with their real output; the scripts are linked from each tutorial.
6. **Where it breaks.** The limits and the known failures.
7. **Exercises**, from pencil to small code. Answers are folded: try first, then open.
8. **What I saw at work**, a box for your own notes, and **further reading**.

**How to learn from one:** read up to "the math by hand", close the page, redo the example on paper, then do the exercises before opening any answer. About three hours each.

## Contents

| Tutorial | The question it answers |
| --- | --- |
| 1. Joins are set math: relational algebra and NULL logic | Why does `NOT IN` return nothing when the list holds one NULL? *(being written)* |
| 2. Why an index is fast: B-tree height by hand | How is one row out of 100 million found by reading about four pages? *(being written)* |
| 3. How the planner guesses: row estimates and join order | Why did the planner pick a plan that ran for an hour? *(being written)* |
| 4. When are two transactions "the same": serializability graphs | How can two people both book the last seat? *(being written)* |
| 5. Column files: run-length, dictionary coding, min/max skipping | Why is the Parquet copy ten times smaller, and why does a date filter read so little of it? *(being written)* |
| [6. Shuffles and skew in Spark](06-Shuffles-and-Skew.md) | Why does one task run 40 minutes while 199 take 2, and how much does salting help? |
| 7. Why sums split and medians do not | Why can Spark sum in one pass but needs a full sort for an exact median? *(being written)* |
| 8. Kafka: the log, offsets, lag and exactly-once | Consumer lag keeps rising: how many consumers are needed? *(being written)* |

The tutorials can be read in any order; each says what it needs.
