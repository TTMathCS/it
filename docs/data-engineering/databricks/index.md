---
title: Databricks and the medallion model
---

# Databricks and the medallion model

*Databricks is a data platform built on Apache Spark and Delta Lake. Many data engineering teams run their pipelines
on it, and the medallion model (bronze, silver and gold layers) is the usual way to organize the data. This course
goes from "what is Databricks" to performance tuning and governance, with the Databricks SQL dialect covered in
depth. It is written for one goal first: being ready for a data engineer interview.*

## Old names and new names

Databricks renamed several products in 2025 and 2026. Interviewers and older blog posts often use the old names, so
learn both. Each row links the official page that states the rename. The date is the page's own "last updated"
date, as read on 11 Nov 2026.

| Name today | Older name you will still hear | Where Databricks says so |
| --- | --- | --- |
| Lakeflow pipelines ("Spark Declarative Pipelines on Lakeflow"), built on open-source Apache Spark Declarative Pipelines; Python module `pyspark.pipelines` | Delta Live Tables (DLT), `import dlt` | [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (Sep 11, 2026) |
| `AUTO CDC` | `APPLY CHANGES` (still works) | [The AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc) (Nov 9, 2026): "The AUTO CDC APIs replace the APPLY CHANGES APIs and have the same syntax" |
| Lakeflow Jobs | Databricks Jobs; the menu item was called Workflows | [Release notes, June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (Oct 29, 2026): "The product known as Databricks Jobs is now Lakeflow Jobs" |
| Declarative Automation Bundles | Databricks Asset Bundles (DABs) | [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (Nov 5, 2026) |
| OpenSharing | Delta Sharing | [From Delta Sharing to OpenSharing](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next) (Databricks blog, Nov 5, 2026) |
| Standard access mode / dedicated access mode | Shared access mode / single-user (assigned) access mode | [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) (Oct 30, 2026) |

In an interview, say both: "Lakeflow pipelines, which used to be called Delta Live Tables".

## How to use it

- **Interview in the next few days?** Read in this order: [24. The data engineer interview](24-Interview.md) (skim
  the questions to see where you are weak), [7. The medallion architecture](07-Medallion-Architecture.md),
  [4. Delta Lake](04-Delta-Lake.md), [9. Building silver](09-Building-Silver.md),
  [3. Apache Spark](03-Apache-Spark.md), [17. Databricks SQL vs standard SQL](17-Databricks-SQL-vs-Standard.md),
  [19. The function toolbox](19-Function-Toolbox.md), [25. PySpark coding practice](25-PySpark-Practice.md),
  [22. Performance tuning](22-Performance-Tuning.md), [11. Structured Streaming](11-Structured-Streaming.md), then
  13 and 14 on pipelines.
- **Rusty on SQL itself?** The [SQL course](../../databases/sql/index.md) covers standard SQL. This course only
  teaches what Databricks does differently or adds.
- **Starting out?** Read in order from chapter 1.

## How a chapter works

- **The opening box** says what you will learn, what to read first, and which sections are beginner, intermediate or
  expert.
- **Every code block has a label.** *Run here* means it was run on Apache Spark 4.2 with Delta Lake 4.4.1 (the
  open-source engines Databricks is built on), and the output under it is the real output. *Databricks only, not run
  here* means it needs a Databricks workspace (Unity Catalog, Auto Loader, Lakeflow pipelines, system tables and so
  on); its syntax was checked against the linked official page.
- **"In the interview" boxes** give a likely question and a short answer you could say out loud.
- **Practice questions** end every chapter. Each answer and its explanation are folded; try first, then open it.
- **Sources** list the official pages used, each with its "last updated" date. Databricks changes quickly: when a
  page and this course disagree, trust the page. Where the official pages disagree with each other, or a claim could
  not be checked, the text says so.

## Contents

| Part | Chapters |
| --- | --- |
| **I. Foundations** | [1. What Databricks is](01-What-Is-Databricks.md) · [2. A tour of the workspace](02-Workspace-Tour.md) · [3. Apache Spark for data engineers](03-Apache-Spark.md) · [4. Delta Lake](04-Delta-Lake.md) · [5. Unity Catalog](05-Unity-Catalog.md) · [6. Compute](06-Compute.md) |
| **II. The medallion architecture** | [7. The medallion architecture explained](07-Medallion-Architecture.md) · [8. Into bronze: ingestion](08-Bronze-Ingestion.md) · [9. Building silver](09-Building-Silver.md) · 10. Building gold · [11. Structured Streaming](11-Structured-Streaming.md) · 12. A complete medallion project |
| **III. Lakeflow** | 13. Spark Declarative Pipelines (formerly DLT) · 14. Data quality and change data capture · 15. Lakeflow Jobs · 16. CI/CD and testing |
| **IV. Databricks SQL** | [17. Databricks SQL vs standard SQL](17-Databricks-SQL-vs-Standard.md) · [18. Nested and semi-structured data](18-Semi-Structured-Data.md) · [19. The function toolbox](19-Function-Toolbox.md) · 20. Tables in Databricks SQL · 21. Programming in SQL |
| **V. Deep dive** | [22. Performance tuning](22-Performance-Tuning.md) · 23. Governance, sharing and operations |
| **VI. Interview** | [24. The data engineer interview](24-Interview.md) · [25. PySpark coding practice](25-PySpark-Practice.md) · Glossary |

Chapters without a link are still being written; they appear here as soon as they pass their checks.

## The sample data

Every chapter uses the same small shop, **Red Rock Supply**, which sells outdoor gear: `customers`, `products`,
`orders` and `order_items`, and raw order events that arrive as JSON files. In examples written for Databricks the
tables live in a catalog called `shop`, with one schema per layer (`shop.bronze`, `shop.silver`, `shop.gold`). Run-here
examples have no Unity Catalog, so they use plain table names or local schemas, and say so.
