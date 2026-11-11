# 2. A tour of the workspace

*Chapter 1 explained what Databricks is. This chapter shows where a data engineer works in it: the sidebar, the
workspace browser, notebooks and the compute they attach to, the SQL editor and query history, Catalog Explorer,
widgets, `dbutils`, Git folders, and the tools outside the browser (the Databricks CLI and Databricks Connect). It
also shows how to practise for free with Databricks Free Edition. Interviewers rarely ask where a button is, but
they do ask how you would set up a project, why `%run` differs from `dbutils.notebook.run()`, and whether
notebooks belong in production. Every menu label here is quoted from a current official page; where no page states
a label, the text says so.*

!!! abstract "In this chapter"
    **You will learn:**

    - the sidebar items in today's names (Workspace, Catalog, Jobs & Pipelines, Compute, SQL Editor, Query History
      and the rest), and which one replaced "Workflows"
    - folders, workspace files and the two notebook formats
    - how a notebook attaches to compute (serverless, all-purpose compute, SQL warehouse) and reads Unity Catalog
      tables; languages, magic commands, `display()` and `_sqldf`
    - the SQL editor, query history (and `system.query.history`) and Catalog Explorer
    - what Databricks Free Edition gives you and what it does not
    - widgets and named parameter markers; `dbutils` (fs, secrets, widgets, notebook, jobs) and what exists outside
      Databricks
    - Git folders (formerly Repos), the Databricks CLI and Databricks Connect
    - when to use notebooks, files and jobs in production

    **You need:** [chapter 1](01-What-Is-Databricks.md). [Chapter 5](05-Unity-Catalog.md) (Unity Catalog) and
    [chapter 6](06-Compute.md) (compute) go deeper into two things this chapter only points at.

    **Levels:** sections 2.1 to 2.5 beginner, 2.6 to 2.9 intermediate, 2.10 expert.

## 2.1 The workspace map

*Level: beginner.*

On the first day at Red Rock Supply you get a link to a **workspace**: "an environment for accessing all of your
Databricks assets", which "organizes objects (notebooks, libraries, dashboards, and experiments) into folders and
provides access to data objects and computational resources" ([Databricks
components](https://docs.databricks.com/aws/en/getting-started/concepts), Oct 29, 2026). Chapter 1 covered how a
workspace sits inside an account and where its compute runs. Here the question is simpler: what is on the screen?

The page [Navigate the Analytics and AI workspace
UI](https://docs.databricks.com/aws/en/workspace/navigate-workspace) (last updated Nov 9, 2026) describes four ways
in: the **homepage**, the **sidebar**, the **+ New** menu and the **search** bar. It lists these sidebar items,
quoted exactly:

| Group on the page | Sidebar items | What a data engineer does there |
| --- | --- | --- |
| Top of the sidebar | Workspace, Recents, Catalog, Jobs & Pipelines, Compute, Discover, Marketplace | **Workspace** opens the workspace browser (2.2). **Catalog** opens Catalog Explorer (2.4). **Jobs & Pipelines** holds jobs and pipelines (chapters 13 and 15). **Compute** lists compute resources ([chapter 6](06-Compute.md)). **Discover** shows curated assets "organized by business domains" ([Workspace UI](https://docs.databricks.com/aws/en/workspace/), Nov 3, 2026). What Recents and Marketplace show is not described on these pages. |
| Analytics | Dashboards, Genie Agents, Alerts, Visual Data Prep | Mostly for analysts; a data engineer feeds them gold tables. |
| Lakehouse | SQL Editor, Queries, Query History, SQL Warehouses | Write SQL against a SQL warehouse, find past runs (2.4). |
| Data Engineering | Runs, Data Ingestion | Listed without a description; what each opens is unknown from the pages checked. |
| AI/ML | Playground, Agents, AI Gateway, Experiments, Features, Models, Serving | Not covered in this book. |

The page adds: "There is a lock icon next to items that require an entitlement you aren't assigned." So a
colleague's sidebar can look different from yours.

**One rename to know.** The June 2025 release notes say: "The **Jobs & Pipelines** item in the left navigation is the
entry point to the Databricks' unified data engineering features, Lakeflow. The **Pipelines** and **Workflows** items
in the left navigation have been removed" ([June 2025](https://docs.databricks.com/aws/en/release-notes/product/2025/june),
Oct 29, 2026). The same notes rename Databricks Jobs to **Lakeflow Jobs**. If an interviewer says "Workflows", they
mean Lakeflow Jobs, now under Jobs & Pipelines. The Jobs & Pipelines UI "provides entry to the Jobs, Lakeflow pipelines, and Lakeflow Connect
UIs" ([Databricks components](https://docs.databricks.com/aws/en/getting-started/concepts)).

**+ New** creates notebooks, queries, repos, jobs, pipelines and other objects, creates compute, and uploads "CSV or
TSV files to Delta Lake". **Search** in the top bar finds notebooks, queries, files, tables registered in Unity
Catalog, jobs and more. Personal settings are under your username, then **Settings**; the workspace name in the top
bar switches workspaces (all from the same navigation page).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 420" role="img" aria-label="Schematic map of the workspace. A top bar with the workspace switcher, search, Genie Code and the user menu. A sidebar listing Workspace, Recents, Catalog, Jobs and Pipelines, Compute, Discover, Marketplace, then the Analytics group, the Lakehouse group (SQL Editor, Queries, Query History, SQL Warehouses), the Data Engineering group (Runs, Data Ingestion) and the AI/ML group. To the right, what the main items open: the plus New menu, the workspace browser, Catalog Explorer, Jobs and Pipelines, Compute, and the SQL editor with query history.">
<g font-size="13" fill="currentColor">
<rect x="8" y="8" width="624" height="36" rx="6" fill="none" stroke="currentColor"/>
<text x="320" y="31" text-anchor="middle">Top bar: workspace name (switch), search, Genie Code, your name &gt; Settings</text>
<rect x="8" y="56" width="232" height="356" rx="6" fill="none" stroke="currentColor"/>
<text x="20" y="78" font-weight="bold">Sidebar</text>
<text x="20" y="100">Workspace</text>
<text x="20" y="118">Recents</text>
<text x="20" y="136">Catalog</text>
<text x="20" y="154">Jobs &amp; Pipelines</text>
<text x="20" y="172">Compute</text>
<text x="20" y="190">Discover</text>
<text x="20" y="208">Marketplace</text>
<text x="20" y="234" font-weight="bold">Analytics</text>
<text x="20" y="252">Dashboards, Genie Agents,</text>
<text x="20" y="270">Alerts, Visual Data Prep</text>
<text x="20" y="296" font-weight="bold">Lakehouse</text>
<text x="20" y="314">SQL Editor, Queries,</text>
<text x="20" y="332">Query History, SQL Warehouses</text>
<text x="20" y="358" font-weight="bold">Data Engineering</text>
<text x="20" y="376">Runs, Data Ingestion</text>
<text x="20" y="400">AI/ML: seven more items</text>
<g text-anchor="middle">
<rect x="256" y="56" width="376" height="48" rx="6" fill="none" stroke="currentColor"/>
<text x="444" y="76" font-weight="bold">+ New menu</text>
<text x="444" y="95">new notebook, query, Git folder, job, cluster</text>
<rect x="256" y="114" width="376" height="56" rx="6" fill="none" stroke="currentColor"/>
<text x="444" y="136" font-weight="bold">Workspace: the workspace browser</text>
<text x="444" y="157">Users (home folders), Shared, Repos; Git folders</text>
<rect x="256" y="180" width="376" height="56" rx="6" fill="none" stroke="currentColor"/>
<text x="444" y="202" font-weight="bold">Catalog: Catalog Explorer</text>
<text x="444" y="223">catalogs, schemas, tables, volumes, lineage</text>
<rect x="256" y="246" width="376" height="56" rx="6" fill="none" stroke="currentColor"/>
<text x="444" y="268" font-weight="bold">Jobs &amp; Pipelines (replaced Workflows)</text>
<text x="444" y="289">Lakeflow Jobs, Lakeflow pipelines (was DLT)</text>
<rect x="256" y="312" width="376" height="48" rx="6" fill="none" stroke="currentColor"/>
<text x="444" y="332" font-weight="bold">Compute</text>
<text x="444" y="351">compute resources you start and manage</text>
<rect x="256" y="370" width="376" height="42" rx="6" fill="none" stroke="currentColor"/>
<text x="444" y="396">SQL Editor, Query History: SQL on a warehouse</text>
</g>
</g>
</svg>
<figcaption>Figure 2.1. The workspace as a map. Item names come from the navigation page (Nov 9, 2026); positions are schematic, not a screenshot. Your sidebar may show a lock icon on items you are not entitled to.</figcaption>
</figure>

!!! warning "Screens change faster than concepts"
    Databricks renames and moves UI items often (Workflows became Jobs & Pipelines in 2025; "Genie Agents were formerly
    known as Genie Spaces", [Genie Agents](https://docs.databricks.com/aws/en/genie-agents/), Nov 2, 2026). The Catalog Explorer page itself warns: "The Catalog Explorer UI is not live in all Databricks
    workspaces" ([What is Catalog Explorer?](https://docs.databricks.com/aws/en/catalog-explorer/), Sep 11, 2026).
    In an interview, name the concept first ("the job UI", "the catalog browser") and the current label second.

## 2.2 Folders, workspace files and notebook formats

*Level: beginner.*

Click **Workspace** to open the workspace browser, where you "create, browse, and organize Databricks objects,
including notebooks, libraries, experiments, queries, dashboards, and alerts, in a single place" ([Workspace
browser](https://docs.databricks.com/aws/en/workspace/workspace-browser), Nov 3, 2026). The same page names three
**special folders**, which you cannot rename or move: Workspace (the root), Shared and Users. Inside the Workspace root
folder you find:

- **Users** contains a home folder for each user. "By default objects in this folder are private to that user."
- **Shared** "is for sharing objects across your organization. All users have full permissions for all objects in
  Shared." Treat it as a scratch area, not a place for production code.
- **Repos** "contains folders backed by Git repositories" (the older location; see 2.8).

Permissions are set on folders: right-click a folder, choose **Share**, and pick users, groups or service principals
and a permission level (same page).

**Workspace files.** Besides notebooks, a workspace holds ordinary files: "Python files (`.py`) files used in custom
modules", "YAML configuration", "Markdown (`.md`) files", small `.csv` files, libraries and logs ([What are workspace
files?](https://docs.databricks.com/aws/en/files/workspace), Sep 11, 2026). Two limits matter: "Workspace file size
is limited to 500MB" (same page), and Databricks recommends "only storing small data files here primarily for development and
testing" ([Work with files on Databricks](https://docs.databricks.com/aws/en/files/), Nov 4, 2026). Raw Red Rock
Supply order files belong in a Unity Catalog **volume** such as `/Volumes/shop/bronze/landing/orders/`
([chapter 5](05-Unity-Catalog.md)), not in the workspace.

**Paths.** Workspace paths start with `/Workspace`, for example `/Workspace/Users/<email>/red-rock`. "We recommend
that all workspace paths carry the `/Workspace` prefix to differentiate them from Volume and DBFS paths"
([Introduction to workspace objects](https://docs.databricks.com/aws/en/workspace/workspace-assets), Nov 6, 2026).

**Notebook formats.** "By default, notebooks in Databricks are created in `.ipynb` (IPython or Jupyter) format", and
you can choose the **source** format instead ([Manage Databricks notebook
format](https://docs.databricks.com/aws/en/notebooks/notebook-format), Nov 3, 2026):

| Format | What it stores | In Git |
| --- | --- | --- |
| IPYNB (default) | "source code, notebook environment, visualization definitions, notebook widgets, and optional outputs"; any language despite the `py` in the name | Outputs can be committed only if a workspace admin allows it |
| Source (`.py`, `.sql`, `.scala`, `.r`) | Only the code | "Notebook outputs aren't included in commits" ([Create and manage Git folders](https://docs.databricks.com/aws/en/repos/git-operations-with-repos)) |

A source notebook is a plain text file that Databricks recognizes by its first line: an asset is a notebook if it
"contains the string `Databricks notebook source` in a comment in the first line" and has a `.py`, `.r`, `.scala` or
`.sql` extension, and `COMMAND` comment lines separate the cells ([Import and export Databricks
notebooks](https://docs.databricks.com/aws/en/notebooks/notebook-export-import), Sep 11, 2026). A two-cell Python
notebook in source format looks like this:

*Databricks only, not run here. Syntax from [Import and export Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/notebook-export-import).*

```python
# Databricks notebook source
from pyspark.sql import functions as F

# COMMAND ----------

orders = spark.read.table("shop.silver.orders")
display(orders.groupBy("status").agg(F.sum("amount").alias("revenue")))
```

That is why source format diffs cleanly in a pull request: it is just Python with comments.

## 2.3 Notebooks: compute, languages and magic commands

*Level: beginner.*

A notebook is "a web-based interface to documents containing a series of runnable cells (commands)" ([Introduction
to workspace objects](https://docs.databricks.com/aws/en/workspace/workspace-assets)). A notebook does nothing until
it is attached to compute.

### Attaching to compute

From [Notebook compute resources](https://docs.databricks.com/aws/en/notebooks/notebook-compute) (Sep 11, 2026):

- **Serverless** is the default: "In workspaces enabled for Unity Catalog, new notebooks default to serverless
  compute. If you don't manually select a compute resource and run a cell, the notebook automatically connects to
  serverless compute."
- **All-purpose compute** (a cluster you or an admin created) needs the **CAN ATTACH TO** permission. A warning
  worth remembering: "As long as a notebook is attached to a compute resource, any user with the CAN RUN permission
  on the notebook has implicit permission to access the compute resource."
- **SQL warehouse**: "you can run SQL and Markdown cells. Running a cell in any other language (such as Python or R)
  throws an error."

On attach, the notebook gets ready-made variables, among them `spark` (the `SparkSession`). The page says: "Don't
create a `SparkSession`, `SparkContext`, or `SQLContext`. Doing so leads to inconsistent behavior."

When a cell reads `shop.silver.orders`, the compute asks Unity Catalog whether you may read it, and only then reads
the Delta files in cloud storage. Figure 2.2 shows the path; [chapter 5](05-Unity-Catalog.md) explains the
privileges and [chapter 6](06-Compute.md) the compute types.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 290" role="img" aria-label="A notebook with a SQL cell and a Python cell attaches to one of three compute choices: serverless, the default in Unity Catalog workspaces; all-purpose compute, which needs CAN ATTACH TO; or a SQL warehouse, which runs SQL and Markdown cells only. The compute asks Unity Catalog for shop.silver.orders; Unity Catalog checks privileges and records lineage; if allowed, the compute reads the Delta files in cloud object storage, and the results flow back to the notebook, where display renders them.">
<defs><marker id="a22" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g font-size="13" fill="currentColor">
<rect x="8" y="20" width="184" height="150" rx="6" fill="none" stroke="currentColor"/>
<text x="100" y="42" text-anchor="middle" font-weight="bold">Notebook</text>
<text x="20" y="66">cell 1: %sql</text>
<text x="20" y="84">SELECT * FROM</text>
<text x="20" y="102">shop.silver.orders</text>
<text x="20" y="130">cell 2: Python</text>
<text x="20" y="148">spark.read.table(...)</text>
<g text-anchor="middle">
<rect x="226" y="20" width="196" height="44" rx="6" fill="none" stroke="currentColor"/>
<text x="324" y="38" font-weight="bold">Serverless</text>
<text x="324" y="56">default in UC workspaces</text>
<rect x="226" y="74" width="196" height="44" rx="6" fill="none" stroke="currentColor"/>
<text x="324" y="92" font-weight="bold">All-purpose compute</text>
<text x="324" y="110">needs CAN ATTACH TO</text>
<rect x="226" y="128" width="196" height="44" rx="6" fill="none" stroke="currentColor"/>
<text x="324" y="146" font-weight="bold">SQL warehouse</text>
<text x="324" y="164">SQL and Markdown cells only</text>
<rect x="456" y="20" width="176" height="100" rx="6" fill="none" stroke="currentColor"/>
<text x="544" y="42" font-weight="bold">Unity Catalog</text>
<text x="544" y="64">checks privileges on</text>
<text x="544" y="82">shop.silver.orders,</text>
<text x="544" y="100">records lineage, audit</text>
<rect x="456" y="190" width="176" height="56" rx="6" fill="none" stroke="currentColor" stroke-dasharray="6 4"/>
<text x="544" y="212" font-weight="bold">Cloud object storage</text>
<text x="544" y="232">Delta files of the table</text>
</g>
<line x1="192" y1="96" x2="224" y2="96" stroke="currentColor" marker-end="url(#a22)"/>
<line x1="422" y1="96" x2="454" y2="70" stroke="currentColor" marker-end="url(#a22)"/>
<line x1="544" y1="120" x2="544" y2="188" stroke="currentColor" marker-end="url(#a22)"/>
<text x="552" y="160" text-anchor="start">if allowed</text>
<path d="M456,232 L100,232 L100,172" fill="none" stroke="currentColor" stroke-dasharray="5 4" marker-end="url(#a22)"/>
<text x="278" y="258" text-anchor="middle">results flow back; display() renders them</text>
</g>
</svg>
<figcaption>Figure 2.2. How a notebook reads a Unity Catalog table. You pick the compute in the notebook's compute selector; Unity Catalog decides whether the read is allowed before any file is touched.</figcaption>
</figure>

### Languages and magic commands

A notebook has a default language (Python, SQL, Scala or R) shown below its name. A cell can switch language with a
**magic command** on its first line: "The supported magic commands are: `%python`, `%r`, `%scala`, and `%sql`." Each
language runs in its own interpreter, so "Variables defined in one language (and hence in the REPL for that
language) are not available in the REPL of another language" ([Develop code in Databricks
notebooks](https://docs.databricks.com/aws/en/notebooks/notebooks-code), Oct 27, 2026). The page adds that REPLs
"can share state only through external resources such as files in DBFS or objects in object storage"; in practice,
write a table. Scala and R are not available
everywhere: serverless notebooks support neither ([Serverless compute
limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations), Nov 5, 2026).

The magic commands a data engineer uses most, from the same page:

| Magic | What it does |
| --- | --- |
| `%sql`, `%python`, `%scala`, `%r` | Run this cell in that language |
| `%md` | Markdown text (headings, notes, images, formulas) |
| `%run` | "Execute another notebook, importing its functions and variables" (2.7) |
| `%pip` | "Install Python packages (notebook-scoped)" |
| `%fs` | "Shorthand for `dbutils.fs` commands" |
| `%sh` | Shell commands; "Runs only on driver node. Use `-e` to fail on error." |
| `%skip` | "Prevents the cell from running when the notebook is executed" |

Two rules from the page: "A notebook cell can only have one cell magic command, and it must be the first line of the
cell", and "`%run` must be in a cell by itself".

`%pip` installs a library for this notebook only: "only the current notebook and any jobs associated with that
notebook have access to that library", and the install does not survive a new session. "`%pip` commands do not
automatically restart the Python process"; after an upgrade you may need `dbutils.library.restartPython()`
([Notebook-scoped Python libraries](https://docs.databricks.com/aws/en/libraries/notebooks-python-libraries), Nov 4,
2026).

### A Red Rock Supply notebook

The same question in two cells, first SQL, then Python:

*Databricks only, not run here. Syntax from [Develop code in Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/notebooks-code) and [Query and visualize data from a notebook](https://docs.databricks.com/aws/en/getting-started/quick-start).*

```python
%sql
SELECT status, count(*) AS orders, sum(amount) AS revenue
FROM shop.silver.orders
GROUP BY status
ORDER BY status
```

```python
from pyspark.sql import functions as F

summary = (spark.read.table("shop.silver.orders")
           .groupBy("status")
           .agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue"))
           .orderBy("status"))
display(summary)
```

Three Databricks extras appear here:

- **`display(df)`** renders a DataFrame as an interactive results table that you can sort, filter and turn into a
  chart. "Table results are limited to 10,000 rows or 2 MB, whichever is lower" ([Known limitations of Databricks
  notebooks](https://docs.databricks.com/aws/en/notebooks/notebook-limitations), Oct 28, 2026): the table may hold
  more; the display shows the first part.
- **`_sqldf`**: "results from a SQL language cell are automatically made available as an implicit DataFrame assigned
  to the variable `_sqldf`". It is reassigned at every SQL cell and "is not available in notebooks that use a SQL
  warehouse for compute" ([Develop code in Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/notebooks-code)).
- **`spark`** is already defined.

What the cells compute is plain Spark, so it runs locally too. Without Unity Catalog, the table is `silver.orders` in
the local catalog:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (`src/ch02/ch02_01_notebook_cell.py`)

```python
spark.sql("""SELECT status, count(*) AS orders, sum(amount) AS revenue
             FROM silver.orders GROUP BY status ORDER BY status""").show(truncate=False)

(spark.read.table("silver.orders")
    .groupBy("status")
    .agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue"))
    .orderBy("status")
    .show())
```

```text
+---------+------+-------+
|status   |orders|revenue|
+---------+------+-------+
|CANCELLED|1     |35.00  |
|PLACED   |1     |59.90  |
|SHIPPED  |2     |338.50 |
+---------+------+-------+

+---------+------+-------+
|   status|orders|revenue|
+---------+------+-------+
|CANCELLED|     1|  35.00|
|   PLACED|     1|  59.90|
|  SHIPPED|     2| 338.50|
+---------+------+-------+
```

The notebook helpers, however, are not part of Apache Spark. In the same local run:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
for name in ["dbutils", "display", "_sqldf"]:
    try:
        eval(name)
        print(f"{name}: defined")
    except NameError as e:
        print(f"{name}: NameError: {e}")
```

```text
dbutils: NameError: name 'dbutils' is not defined
display: NameError: name 'display' is not defined
_sqldf: NameError: name '_sqldf' is not defined
```

Code you want to test outside Databricks should keep its logic in functions that take and return DataFrames, and
leave `display` and `dbutils` to the notebook that calls them (chapter 16).

## 2.4 SQL editor, query history and Catalog Explorer

*Level: beginner.*

### The SQL editor

Click **SQL Editor** in the sidebar. It is where you "write queries, collaborate with colleagues, find available data,
and create visualizations" ([Databricks SQL editor](https://docs.databricks.com/aws/en/sql/user/sql-editor/), Oct 30,
2026). It runs on a **SQL warehouse**: "You must have at least CAN USE permissions on a SQL warehouse to run
queries", and a stopped warehouse "will restart automatically when you run your query" ([Write queries in the new SQL
editor](https://docs.databricks.com/aws/en/sql/user/sql-editor/write-queries), Oct 27, 2026). A schema browser on
the left lists catalogs, schemas and tables.

Parameters use the named marker syntax `:name`, "the same syntax used by other Databricks tools like AI/BI dashboards,
Genie Agents, and notebooks". Adding `:status` to a query shows a parameter widget. Queries from the legacy editor
that use double curly braces to mark parameters must be changed before they run in the new editor ([Work with parameter
widgets](https://docs.databricks.com/aws/en/sql/user/sql-editor/parameter-widgets), Oct 27, 2026).

### Query history

Click **Query History** in the sidebar to see past runs, filtered "by user, date range, compute, duration, query
status, statement type, statement ID, and query tags". Click a query for its full text, status, duration, rows and
"See query profile" ([Query history](https://docs.databricks.com/aws/en/sql/user/queries/query-history), Sep 11,
2026). Two details from that page:

- "If your workspace is enabled for serverless compute, your query history also contains all SQL and Python queries
  run on serverless compute for notebooks and jobs."
- You see your own queries; others see them "if they have at least CAN VIEW access to the SQL warehouse that executed
  the query".

The same data is in a system table, `system.query.history`. "By default, only admins have access" to this table,
and the `statement_text` column "returns `<REDACTED>` by default" except for account admins and members of the
`databricks_pii_access` group ([Query history system table
reference](https://docs.databricks.com/aws/en/admin/system-tables/query-history), Nov 4, 2026). The slowest failed
statements of the last day:

*Databricks only, not run here. Column names from [Query history system table reference](https://docs.databricks.com/aws/en/admin/system-tables/query-history).*

```sql
SELECT executed_by, statement_type, execution_status, total_duration_ms, start_time
FROM system.query.history
WHERE start_time >= current_timestamp() - INTERVAL 1 DAY
  AND execution_status = 'FAILED'
ORDER BY total_duration_ms DESC
LIMIT 20;
```

`execution_status` is `FINISHED`, `FAILED` or `CANCELED`. The query profile is covered in
[chapter 22](22-Performance-Tuning.md).

### Catalog Explorer

"To open Catalog Explorer, click **Catalog** in the sidebar." It has two jobs: "Finding data assets" and "Managing
Unity Catalog and OpenSharing", for example creating catalogs, managing external locations, changing ownership and
granting permissions ([What is Catalog Explorer?](https://docs.databricks.com/aws/en/catalog-explorer/), Sep 11, 2026;
OpenSharing is the new name for Delta Sharing). On a table page you will find tabs named **Columns**, **Sample Data**,
**Details** and **History** ([Explore database objects](https://docs.databricks.com/aws/en/discover/database-objects),
Sep 11, 2026) and **Lineage** ([Lineage in Unity
Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage), Nov 4, 2026). For
`shop.silver.orders`, **History** shows the Delta versions ([chapter 4](04-Delta-Lake.md)) and **Lineage** shows that
it comes from `shop.bronze.orders` and feeds the gold tables.

One practical difference: "You can navigate Unity Catalog-governed database objects in Catalog Explorer without
active compute" ([Write queries in the new SQL
editor](https://docs.databricks.com/aws/en/sql/user/sql-editor/write-queries)), but "You must have access to active
compute to sample data" ([Explore database objects](https://docs.databricks.com/aws/en/discover/database-objects)).

## 2.5 Practising for free: Databricks Free Edition

*Level: beginner.*

You do not need a company account to practise. "Databricks Free Edition is a no-cost version of Databricks designed
for students, educators, hobbyists, and anyone interested in learning or experimenting with data and AI". It "is
available in a serverless-only, quota-limited environment", and "Free Edition replaced the legacy Databricks Community
Edition, which was retired in 2025" ([Sign up for Databricks Free
Edition](https://docs.databricks.com/aws/en/getting-started/free-edition), Sep 11, 2026). A new Free Edition
workspace "includes serverless compute and default storage".

The limits, quoted from [Databricks Free Edition
limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations) (Oct 18, 2026):

| Area | Free Edition |
| --- | --- |
| Compute | "only have access to serverless compute resources. Custom compute configurations are not supported." |
| SQL warehouses | "One SQL warehouse, limited to a `2X-Small` cluster size." |
| Jobs | "Max of 5 concurrent job tasks per account." |
| Lakeflow pipelines | "One active pipeline per pipeline type." |
| Languages | "R and Scala" are not supported. |
| Admin | "One workspace and one metastore per account"; no account console; no SSO or SCIM |
| Quota | If you exceed it, compute is "shut down and unavailable for the rest of the day (and in extreme cases, the rest of the month)"; data and settings are kept |
| Use | "may not be used for commercial purposes"; inactive accounts may be deleted |

The **free trial** is different: it is "designed for organizations and professionals evaluating Databricks for
business use", with credits "valid for 14 days", full platform access and classic compute. The Free Edition terms
include "Databricks reserves the right to train on your data", so practise with made-up data such as Red Rock Supply,
never with an employer's data ([Sign up for
Databricks](https://docs.databricks.com/aws/en/getting-started/free-trial-vs-free-edition), Oct 27, 2026).

The Free Edition page promises the SQL editor, notebooks and Lakeflow ("Ingest, transform, and orchestrate data");
it does not mention `dbutils`, widgets, volumes, Catalog Explorer or Query History either way (not verified for
Free Edition). It cannot show classic
clusters, cluster sizing, access modes ([chapter 6](06-Compute.md)), Scala or account administration. A practice
plan:

1. Create a Git folder from your own GitHub repository (2.8) and a schema per layer: `bronze`, `silver`, `gold`.
   Whether Free Edition lets you create a catalog named `shop` is not stated on the limitations page (not
   verified); if it does not, use the catalog your workspace gives you and keep the schema names.
2. Create a volume for raw files, upload a few Red Rock Supply JSON order files, and build the chapter 12 project.
3. Run it as a job with two tasks, and read your own queries in Query History.

## 2.6 Widgets and parameters

*Level: intermediate.*

The Red Rock Supply daily load must run for any date and status without editing code. **Widgets** "allow you to add
parameters to your notebooks and dashboards", and there are four types: `text`, `dropdown`, `combobox` and
`multiselect`. "Widgets only accept string values" ([Databricks
widgets](https://docs.databricks.com/aws/en/notebooks/widgets), Nov 9, 2026). The arguments are name, default value,
choices (not for `text`) and an optional label:

*Databricks only, not run here. Syntax from [Databricks widgets](https://docs.databricks.com/aws/en/notebooks/widgets).*

```python
dbutils.widgets.dropdown("status", "PLACED", ["PLACED", "SHIPPED", "CANCELLED"], "Order status")
dbutils.widgets.text("min_amount", "100")

status = dbutils.widgets.get("status")                 # always a string
min_amount = float(dbutils.widgets.get("min_amount"))  # convert before comparing with numbers
```

The SQL form, and a SQL cell that uses the value through a **named parameter marker**:

*Databricks only, not run here. Syntax from [Databricks widgets](https://docs.databricks.com/aws/en/notebooks/widgets).*

```sql
CREATE WIDGET DROPDOWN status DEFAULT "PLACED" CHOICES SELECT * FROM (VALUES ("PLACED"), ("SHIPPED"), ("CANCELLED"))
```

```sql
SELECT order_id, customer_id, amount
FROM shop.silver.orders
WHERE status = :status
```

"Parameter markers protect your code from SQL injection attacks by clearly separating provided values from the SQL
statements." To pass a table or schema name, wrap it: "You must use the SQL `IDENTIFIER()` clause to parse strings as
object identifiers" (same page; parameter markers for widgets need Databricks Runtime 15.2 and above). If a notebook
is attached to a SQL warehouse, the UI (**Edit > Add parameter**) "is the only way you can create widgets".

Parameter markers are standard Spark SQL, so the binding itself can be shown locally, with a Python variable standing
in for the widget value. This also shows why you should never paste a widget value into the SQL text.

!!! note "How this example ran"
    In this local setup the Delta Lake SQL extension stops parameter markers from binding (every marker reports
    `UNBOUND_SQL_PARAMETER`; [chapter 17](17-Databricks-SQL-vs-Standard.md) saw the same). This example therefore
    ran on a plain Spark 4.2 session with the table stored as Parquet. It is a quirk of the test setup, not a
    Databricks behavior.

*Run here: Apache Spark 4.2 (plain session without the Delta extension, Parquet table; see the note).* (`src/ch02/ch02_02_parameters.py`)

```python
status_value = "SHIPPED"          # in a Databricks notebook: dbutils.widgets.get("status")
spark.sql("""SELECT order_id, customer_id, amount
             FROM silver.orders
             WHERE status = :status
             ORDER BY order_id""", args={"status": status_value}).show()

spark.sql("SELECT count(*) AS n FROM IDENTIFIER(:tbl)", args={"tbl": "silver.orders"}).show()

bad_value = "SHIPPED' OR '1'='1"
pasted = f"SELECT count(*) AS n FROM silver.orders WHERE status = '{bad_value}'"
spark.sql(pasted).show()
spark.sql("SELECT count(*) AS n FROM silver.orders WHERE status = :status",
          args={"status": bad_value}).show()
```

```text
+--------+-----------+------+
|order_id|customer_id|amount|
+--------+-----------+------+
|    1002|          9|249.00|
|    1003|          7| 89.50|
+--------+-----------+------+

+---+
|  n|
+---+
|  4|
+---+

+---+
|  n|
+---+
|  4|
+---+

+---+
|  n|
+---+
|  0|
+---+
```

The pasted version counted all 4 orders, because the quote in the value changed the `WHERE` clause. The marker
version treated the whole value as one string, which matches no status, so it counted 0.

When the notebook runs as a job task, widgets are also how it receives parameters: "You can also use widgets to
create job and task parameters" ([Serverless compute
limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations)). Chapter 15
shows job parameters in detail.

## 2.7 dbutils

*Level: intermediate.*

**Databricks Utilities** (`dbutils`) "provide modules with commands that enable you to work with your Databricks
environment from notebooks", and "are available in Python, R, and Scala notebooks" ([Databricks Utilities (`dbutils`)
reference](https://docs.databricks.com/aws/en/dev-tools/databricks-utils), Nov 6, 2026). `dbutils.help()` lists the
modules; `dbutils.fs.help("cp")` explains one command. The modules a data engineer uses:

| Module | Typical use | Notes from the reference page |
| --- | --- | --- |
| `fs` | List, copy, move, remove files; `%fs` is the shorthand | Python uses `snake_case` keyword names |
| `secrets` | Read a password or token without writing it in code | Values print as `[REDACTED]` |
| `widgets` | Notebook parameters (2.6) | |
| `notebook` | `run` another notebook as a job; `exit` with a value | "EXPERIMENTAL" in the module list |
| `jobs.taskValues` | Pass small values between tasks of one job run | Python only |
| `library` | `restartPython()` after `%pip` | Most methods deprecated |

### fs: files in volumes

*Databricks only, not run here. Syntax from [Databricks Utilities (dbutils) reference](https://docs.databricks.com/aws/en/dev-tools/databricks-utils).*

```python
dbutils.fs.ls("/Volumes/shop/bronze/landing/orders/")
dbutils.fs.head("/Volumes/shop/bronze/landing/orders/orders_2026-03-01.json", 200)
dbutils.fs.cp("/Volumes/shop/bronze/landing/orders/orders_2026-03-01.json",
              "/Volumes/shop/bronze/archive/orders_2026-03-01.json")
```

Older code uses `dbutils.fs.mount` and `/mnt/...` paths. Databricks recommends moving away from it ("not compatible
with Databricks serverless compute architecture") toward Unity Catalog external locations and volumes (same page).

### secrets

A secret "stores a sensitive value, such as a password, API key, or hashing salt, so that notebooks, jobs, and
functions can use it without the value appearing in code". There are two kinds ([Secret
management](https://docs.databricks.com/aws/en/security/secrets/), Nov 6, 2026):

- **Workspace secret scopes**: "Named collections of secrets in one workspace. Permissions apply to the whole scope."
- **Secrets in Unity Catalog**: "Securable objects (`catalog.schema.secret`) that are available in every workspace
  attached to the metastore", with grants per secret. Reading one needs ownership or `READ SECRET`, and `dbutils` can
  read them on serverless environment version 4 and above or Databricks Runtime 17.3 LTS and above ([Secrets in Unity
  Catalog](https://docs.databricks.com/aws/en/security/secrets/unity-catalog-secrets), Nov 6, 2026).

*Databricks only, not run here. Syntax from [Workspace secret scopes](https://docs.databricks.com/aws/en/security/secrets/workspace-secret-scopes) and [Secrets in Unity Catalog](https://docs.databricks.com/aws/en/security/secrets/unity-catalog-secrets).*

```python
# a workspace secret scope
erp_password = dbutils.secrets.get(scope="red-rock", key="erp-db-password")

# a Unity Catalog secret, shop.app_secrets.erp_db_password
erp_password = dbutils.secrets.get(catalog="shop", schema="app_secrets", key="erp_db_password")
```

!!! warning "Redaction is not access control"
    Databricks "attempts to redact secret values that are read using `dbutils.secrets.get()`", but "Redaction applies
    only to literal secret values. The secret redaction functionality does not prevent deliberate and arbitrary
    transformations of a secret literal" ([Workspace secret
    scopes](https://docs.databricks.com/aws/en/security/secrets/workspace-secret-scopes), Nov 6, 2026). Anyone who
    may read a secret can reveal it. Protect secrets with permissions, not with redaction.

### notebook: run and exit

`dbutils.notebook.run(path, timeout_seconds, arguments)` "starts an ephemeral job that runs immediately" and returns
the value the called notebook passes to `dbutils.notebook.exit()`. "Both parameters and return values must be
strings"; `arguments` sets the widgets of the called notebook; a `timeout_seconds` of 0 means no timeout
([Orchestrate Databricks notebooks and modularize
code](https://docs.databricks.com/aws/en/notebooks/notebook-workflows), Nov 2, 2026). To return several values,
return JSON:

*Databricks only, not run here. Syntax from [Orchestrate Databricks notebooks and modularize code](https://docs.databricks.com/aws/en/notebooks/notebook-workflows).*

```python
# called notebook: load_orders_day
import json
run_date = dbutils.widgets.get("run_date")
# ... load one day of orders into shop.bronze.orders ...
dbutils.notebook.exit(json.dumps({"status": "OK", "run_date": run_date}))
```

```python
# calling notebook
import json
result = json.loads(dbutils.notebook.run("./load_orders_day", 600, {"run_date": "2026-03-01"}))
```

`%run ./includes/common` is different: it runs the whole other notebook inline, so its functions and
variables "become available in the calling notebook", but it "can't return values". Pass widget values with
`%run /path/to/notebook $X="10" $Y="1"` (on a cluster, not a SQL warehouse; [Databricks
widgets](https://docs.databricks.com/aws/en/notebooks/widgets)).

| | `%run` | `dbutils.notebook.run()` |
| --- | --- | --- |
| Where it runs | Inline, inside the calling notebook | A new ephemeral job |
| Variables and functions | Shared with the caller | Not shared |
| Parameters | `$name="value"` to widgets | `arguments` map (strings) |
| Return value | None | One string from `exit()` |
| Typical use | Load shared helper code | Run a notebook per item from a list (metadata-driven) |

!!! warning "A doc example that fails on serverless"
    The notebook-workflows page shows returning data "through temporary views" with
    `createOrReplaceGlobalTempView`. On serverless, "Global temp views are not supported" ([Serverless compute
    limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations)). Return a table name or JSON
    instead.

### jobs.taskValues

Inside a job, one task can hand a small value to a later task: `dbutils.jobs.taskValues.set(key=..., value=...)` in
one task, `dbutils.jobs.taskValues.get(taskKey=..., key=..., default=..., debugValue=...)` in a later one. Values must
be representable as JSON, at most 48 KiB, up to 250 per job run; outside a job, `get` raises a `TypeError` unless you
pass `debugValue` ([Databricks Utilities reference](https://docs.databricks.com/aws/en/dev-tools/databricks-utils)).
Chapter 15 uses them.

### dbutils outside Databricks

`dbutils` is not in Apache Spark (the `NameError` in 2.3). Outside a notebook you have two official routes:

- The **Databricks SDK for Python**: `WorkspaceClient().dbutils`. "From your local development machine, Databricks
  Utilities has access only to the `dbutils.fs`, `dbutils.secrets`, `dbutils.widgets`, and `dbutils.jobs` command
  groups" ([Databricks SDK for Python](https://docs.databricks.com/aws/en/dev-tools/sdk-python), Sep 11, 2026).
- **Databricks Connect** includes the SDK; through it, local widgets "exist only in your local session and can't
  retrieve remote notebook or job task parameters", and task values are not exchanged with remote runs ([Databricks
  Utilities with Databricks Connect for
  Python](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/python/databricks-utilities), Oct 30, 2026).

*Databricks only, not run here. Syntax from [Databricks SDK for Python](https://docs.databricks.com/aws/en/dev-tools/sdk-python).*

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
for f in w.dbutils.fs.ls("/"):
    print(f.path)
```

!!! tip "In the interview"
    **"What is the difference between `%run` and `dbutils.notebook.run()`?"** `%run` runs another notebook inline, so
    its functions and variables become available; it returns nothing. `dbutils.notebook.run()`
    starts a separate ephemeral job, passes string arguments to its widgets and gets one string back from
    `dbutils.notebook.exit()`. For scheduled pipelines, Databricks recommends Lakeflow Jobs (formerly Databricks
    Jobs, the ["Workflows" menu](https://docs.databricks.com/aws/en/release-notes/product/2025/june)) over either one, and workspace files over `%run` for shared code.

## 2.8 Git folders

*Level: intermediate.*

"Repos are now called Git folders." The function is the same; only the terminology changed. Git folders can sit at
any depth under `/Workspace/Users/<user-email>/`, while Repos lived at `/Workspace/Repos/<user email>/<Repo name>`.
Old `/Repos` paths keep working, so "paths in `jobs`, `dbutils.notebook.run`, and `%run` references don't need to
change" ([What happened to Databricks Repos?](https://docs.databricks.com/aws/en/repos/what-happened-repos), Sep 11,
2026).

A Git folder is "a visual Git client and API that integrates Git repositories within your workspace"
([Databricks Git folders](https://docs.databricks.com/aws/en/repos/), Sep 11, 2026). Supported providers include
GitHub, Bitbucket, GitLab, Azure DevOps and AWS CodeCommit, cloud and self-managed ([Databricks Git folders
concepts](https://docs.databricks.com/aws/en/repos/git-folders-concepts), Sep 11, 2026).

The steps, from [Create and manage Git
folders](https://docs.databricks.com/aws/en/repos/git-operations-with-repos) (Sep 11, 2026):

1. Configure Git credentials once. You need `CAN MANAGE` on the parent folder.
2. In **Workspace**, open your user folder, click **Create** > **Git folder**, enter the repository URL, the
   provider and the folder name, then **Create Git folder**. (From the **+ New** menu it is **New** > **Git folder**, per [What happened to
   Databricks Repos?](https://docs.databricks.com/aws/en/repos/what-happened-repos).)
3. Open the Git dialog from the branch button next to a notebook's name, or **Git** beside the folder name.
   **Create Branch**, edit, write a commit message, **Commit & Push**. **Pull** brings in remote changes.
4. Open the pull request in your Git provider, not in Databricks.

Three traps from the same page:

- "Only one user performs Git operations on each Git folder". Switching branches in a shared Git folder switches it
  for everyone in it. Each developer clones their own Git folder.
- "Switching branches might delete workspace assets when the new branch doesn't contain these assets", and switching
  back recreates them "with new IDs and URLs".
- "Git operations that pull upstream changes clear the notebook state."

For deployment, "Databricks recommends Declarative Automation Bundles to package and deploy CI/CD workflows. If you
prefer to deploy only code into the workspace, you can use a production Git folder instead", one that admins create
outside user folders and that "should be updated only by automation when PRs are merged" ([CI/CD with Databricks Git
folders](https://docs.databricks.com/aws/en/repos/ci-cd), Sep 11, 2026). Bundles are "formerly known as Databricks
Asset Bundles" ([What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/));
chapter 16 covers them.

!!! tip "In the interview"
    **"How would you set up a new project in a Databricks workspace?"** One Git repository for the project. Each
    developer clones it into their own Git folder (formerly [Repos](https://docs.databricks.com/aws/en/repos/what-happened-repos)) under `/Workspace/Users/<email>/` and works on a
    feature branch. Logic goes in workspace files (`.py` modules with unit tests); notebooks stay thin entry points.
    Data lives in Unity Catalog (`shop.bronze`, `shop.silver`, `shop.gold`, one catalog per environment), raw files
    in volumes, passwords in secrets. Jobs and pipelines are defined in a Declarative Automation Bundle (formerly
    [Databricks Asset Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/)) and deployed by CI after the pull request is merged; nobody edits production by
    hand.

## 2.9 The Databricks CLI and Databricks Connect

*Level: intermediate.*

### The CLI

"The CLI wraps the Databricks REST API", so anything you click can usually be scripted. Versions 1.0.0 and above are
generally available; "Versions 0.18 and below are legacy CLI", with no further support ([Databricks
CLI](https://docs.databricks.com/aws/en/dev-tools/cli/), Oct 20, 2026). Install and log in (Homebrew on macOS or
Linux; winget, Chocolatey or WSL on Windows):

*Databricks only, not run here. Syntax from [Databricks CLI tutorial](https://docs.databricks.com/aws/en/dev-tools/cli/tutorial).*

```bash
brew tap databricks/tap
brew trust databricks/tap
brew install databricks
databricks -v
databricks auth login --host <workspace-url>
```

`auth login` uses OAuth in the browser and saves a **configuration profile**. Some everyday commands for Red Rock
Supply:

*Databricks only, not run here. Syntax from the [`workspace`](https://docs.databricks.com/aws/en/dev-tools/cli/reference/workspace-commands), [`fs`](https://docs.databricks.com/aws/en/dev-tools/cli/reference/fs-commands), [`secrets`](https://docs.databricks.com/aws/en/dev-tools/cli/reference/secrets-commands) and [`jobs`](https://docs.databricks.com/aws/en/dev-tools/cli/reference/jobs-commands) command group pages.*

```bash
databricks workspace list /Workspace/Users/<your-email>
databricks fs ls dbfs:/Volumes/shop/bronze/landing/orders
databricks fs cp ./orders_2026-03-01.json dbfs:/Volumes/shop/bronze/landing/orders/
databricks secrets create-scope red-rock
databricks secrets put-secret red-rock erp-db-password
databricks jobs list
```

For `put-secret`, the [Workspace secret
scopes](https://docs.databricks.com/aws/en/security/secrets/workspace-secret-scopes) page lists three ways to give the
value: the `--string-value` flag, "when prompted interactively", or standard input. The last two keep the value out of
your shell history. The
`databricks bundle` commands that deploy bundles are covered in chapter 16.

### Databricks Connect

Databricks Connect lets you write Spark code in an IDE on your laptop and run it on Databricks compute. It "is built
on open-source Spark Connect". "General code runs locally", "DataFrame APIs are executed on Databricks compute", and
"UDF code runs on Databricks compute" ([Databricks
Connect](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/), Sep 11, 2026).

*Databricks only, not run here. Syntax from [Tutorial: Run Python code on serverless compute](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/python/tutorial-serverless).*

```bash
pip install "databricks-connect==17.3.*"
```

```python
from databricks.connect import DatabricksSession

spark = DatabricksSession.builder.serverless().profile("<profile-name>").getOrCreate()
orders = spark.read.table("shop.silver.orders")
orders.groupBy("status").count().show()
```

The `groupBy` runs on Databricks; `show()` brings the small result back to your laptop. The version line
(`17.3.*`) is the tutorial's; the tutorial points to the Databricks Connect release notes for the latest versions.

## 2.10 Notebooks, files and jobs in production

*Level: expert.*

Notebooks are excellent for exploring Red Rock Supply's data. The question an interviewer asks is what runs at 2 a.m.
The page [Orchestrate Databricks notebooks and modularize
code](https://docs.databricks.com/aws/en/notebooks/notebook-workflows) (Nov 2, 2026) ranks the options:

| Method | Purpose | The page's verdict |
| --- | --- | --- |
| Lakeflow Jobs | Orchestration | "Recommended method for orchestrating notebooks"; dependencies, schedules, triggers |
| `dbutils.notebook.run()` | Orchestration | Use it "if Jobs cannot support your use case, such as dynamically running a notebook based on a metadata file"; each call starts a new ephemeral job |
| Workspace files | Code modularization | "Recommended method for modularizing code"; version control and IDE testing |
| `%run` | Code modularization | Use it "if you can't access workspace files"; it "can lead to tightly coupled code that's harder to maintain" |

Put together, a production layout for the daily orders load:

- `src/red_rock/transforms.py`: functions such as `clean_orders(df)` that take and return DataFrames, with unit tests
  run in CI (chapter 16).
- `notebooks/load_orders.ipynb` (or a `.py` file): reads widgets or job parameters, imports from `src/`, writes to
  `shop.silver.orders`. No `display()` calls that matter for the result.
- A Lakeflow job (or a Lakeflow pipeline, formerly [Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt), for the declarative parts) defined in a bundle,
  with retries, alerts and a service principal as the run identity (chapter 15).

Why not schedule the exploration notebook as it is? It mixes scratch cells, state and outputs, `%run` chains hide
its dependencies, and nothing in it is unit tested. The job should also run on serverless or job compute rather
than the team's all-purpose cluster: all-purpose compute is supported for notebook tasks, but serverless jobs compute
is the recommended choice ([Configure compute for jobs](https://docs.databricks.com/aws/en/jobs/compute), Nov 9,
2026; [chapter 6](06-Compute.md)).

!!! tip "In the interview"
    **"Do notebooks belong in production?"** As thin entry points, yes: a Lakeflow job (formerly a Databricks job,
    the ["Workflows" menu](https://docs.databricks.com/aws/en/release-notes/product/2025/june)) can run
    a notebook task that reads its parameters and calls tested functions from workspace files. As the place where
    all the logic lives, no: logic in `.py` modules can be unit tested and reviewed, while `%run` chains and
    hand-run cells cannot. Schedule with Lakeflow Jobs, not `dbutils.notebook.run()` loops, unless the list of
    notebooks really comes from metadata at run time.

## 2.11 Practice questions

*Level: mixed.*

**Q1. A senior colleague tells you to "check it in Workflows". Your sidebar has no Workflows item. Where do you go?**

??? success "Answer"
    **Jobs & Pipelines**. The [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) say the **Pipelines** and **Workflows** items "have been
    removed, and their functionality is now available from **Jobs & Pipelines**", and the product formerly known as
    Databricks Jobs is now Lakeflow Jobs.

    **Why:** many people still say "Workflows" for Lakeflow Jobs. Say both names once.

**Q2. Which sidebar item opens Catalog Explorer, and can you browse Unity Catalog tables there with all compute
stopped?**

??? success "Answer"
    **Catalog**. Yes: Unity Catalog objects can be navigated "without active compute". Previewing rows on the
    **Sample Data** tab does need active compute.

    **Why:** metadata comes from Unity Catalog itself; sample rows have to be read from the files by some compute.

**Q3. A notebook attached to a SQL warehouse fails on its first Python cell. The SQL cells worked. Why?**

??? success "Answer"
    On a SQL warehouse "you can run SQL and Markdown cells. Running a cell in any other language (such as Python or
    R) throws an error." Attach the notebook to serverless or all-purpose compute to run Python.

    **Why:** a SQL warehouse is compute built for SQL only.

**Q4. What happens here?**

*Databricks only, not run here. Syntax from [Develop code in Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/notebooks-code).*

```python
min_amount = 100
```

```python
%scala
println(min_amount)
```

??? success "Answer"
    The Scala cell fails: `min_amount` is not defined there. "Variables defined in one language (and hence in the
    REPL for that language) are not available in the REPL of another language." To share data across languages,
    write it somewhere both can read, such as a table. On serverless compute or Free Edition, the Scala cell would
    not run at all: Scala is not supported there.

    **Why:** each language has its own interpreter (REPL) state; the page says REPLs "can share state only through
    external resources".

**Q5. Find the bug.**

*Databricks only, not run here. Syntax from [Orchestrate Databricks notebooks and modularize code](https://docs.databricks.com/aws/en/notebooks/notebook-workflows).*

```python
%run ./includes/common
orders = clean_orders(spark.read.table("shop.bronze.orders"))
```

??? success "Answer"
    `%run` must be "in a cell by itself, because it runs the entire notebook inline". Put `%run ./includes/common`
    alone in one cell and the code in the next cell.

    **Why:** the magic takes over the whole cell.

**Q6. Write Python that creates a dropdown widget `status` with values PLACED, SHIPPED and CANCELLED (default
PLACED) and a text widget `min_amount` (default 100), then reads both.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Databricks widgets](https://docs.databricks.com/aws/en/notebooks/widgets).*

    ```python
    dbutils.widgets.dropdown("status", "PLACED", ["PLACED", "SHIPPED", "CANCELLED"])
    dbutils.widgets.text("min_amount", "100")
    status = dbutils.widgets.get("status")
    min_amount = float(dbutils.widgets.get("min_amount"))
    ```

    **Why:** the arguments are name, default, choices (not for `text`) and an optional label. Widget values are
    strings, hence the `float()`.

**Q7. Find the bug: `if dbutils.widgets.get("min_amount") > 100:` raises an error.**

??? success "Answer"
    "Widgets only accept string values", so the comparison is between a string and an integer, which Python 3
    rejects with a `TypeError`. Convert first: `float(dbutils.widgets.get("min_amount")) > 100`.

    **Why:** every widget value is a string, even one picked from a dropdown.

**Q8. A widget `tbl` holds a table name such as `shop.silver.orders`. Write the SQL cell that counts its rows
safely.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Databricks widgets](https://docs.databricks.com/aws/en/notebooks/widgets).*

    ```sql
    SELECT count(*) AS n FROM IDENTIFIER(:tbl)
    ```

    The same shape ran locally in 2.6 (`IDENTIFIER(:tbl)` returned 4).

    **Why:** a parameter marker is a value, not a name; `IDENTIFIER()` turns the string into an object name, still
    without pasting text into the statement.

**Q9. Find the bug and fix it.**

*Databricks only, not run here. Syntax from [Databricks widgets](https://docs.databricks.com/aws/en/notebooks/widgets).*

```python
status = dbutils.widgets.get("status")
spark.sql(f"SELECT * FROM shop.silver.orders WHERE status = '{status}'")
```

??? success "Answer"
    The value is pasted into the SQL text, so a value like `SHIPPED' OR '1'='1` changes the query (SQL injection).
    In the 2.6 run, the pasted version counted all 4 orders and the marker version counted 0. Fix:

    *Databricks only, not run here. Syntax from [Databricks widgets](https://docs.databricks.com/aws/en/notebooks/widgets); the same pattern ran locally in 2.6.*

    ```python
    spark.sql("SELECT * FROM shop.silver.orders WHERE status = :status", args={"status": status})
    ```

    **Why:** with a marker the value is bound separately from the statement and can never become SQL.

**Q10. What is the difference between `%run` and `dbutils.notebook.run()`?**

??? success "Answer"
    `%run` runs the other notebook inline; its functions and variables become available; it
    returns nothing; it passes widget values as `$name="value"`. `dbutils.notebook.run(path, timeout, arguments)`
    starts a new ephemeral job, sets the called notebook's widgets from the `arguments` map, shares no variables,
    and returns the one string the callee passes to `dbutils.notebook.exit()`.

    **Why:** use `%run` to include helper code (or better, import workspace files), and `dbutils.notebook.run()` for
    a metadata-driven loop that Lakeflow Jobs (formerly Databricks Jobs, the ["Workflows" menu](https://docs.databricks.com/aws/en/release-notes/product/2025/june))
    cannot express.

**Q11. A called notebook must return a status and a row count to its caller. How?**

??? success "Answer"
    `dbutils.notebook.exit(json.dumps({"status": "OK", "rows": 1234}))` in the callee and
    `json.loads(dbutils.notebook.run(...))` in the caller.

    **Why:** "Both parameters and return values must be strings", so structured data is serialized, or written to a
    table whose name is returned.

**Q12. A callee notebook creates a global temp view and returns its name; on serverless compute the caller fails.
Why, and what do you do instead?**

??? success "Answer"
    "Global temp views are not supported" on serverless compute. Write the result to a table (for example a
    scratch table in `shop.silver`) and return its name, or return JSON for small results.

    **Why:** the documented global-temp-view pattern assumes classic compute.

**Q13. `print(dbutils.secrets.get(scope="red-rock", key="erp-db-password"))` shows `[REDACTED]`. Is the secret
therefore safe from everyone who can run this notebook?**

??? success "Answer"
    No. Redaction "applies only to literal secret values" and "does not prevent deliberate and arbitrary
    transformations of a secret literal". Anyone allowed to read the secret can reveal it. Control who may read the
    scope (or, for a Unity Catalog secret, who has `READ SECRET`).

    **Why:** redaction prevents accidents in output, not deliberate reading.

**Q14. Workspace secret scope or Unity Catalog secret for the ERP password used by jobs in dev and prod workspaces?**

??? success "Answer"
    A workspace scope exists in one workspace and has permissions only at scope level. A Unity Catalog secret
    (`catalog.schema.secret`) is available "in every workspace attached to the metastore", has grants per secret and
    is audited. For several workspaces on one metastore, the Unity Catalog secret avoids copying the value, if your
    compute meets the requirement (serverless environment 4 and above, or Databricks Runtime 17.3 LTS and above).
    Note that Databricks Connect reads only workspace scopes ("No" for Unity Catalog secrets on the Secret
    management page).

    **Why:** the choice is about scope of sharing, granularity of access and where the code runs.

**Q15. Your script calls `dbutils.fs.ls(...)` and works in a notebook, but on your laptop it fails with `NameError:
name 'dbutils' is not defined`. Why, and what are your options?**

??? success "Answer"
    `dbutils` is injected into Databricks notebooks; it is not part of Apache Spark (the local run in 2.3 shows the
    same `NameError`). Options: the Databricks SDK for Python (`WorkspaceClient().dbutils`, with only `fs`,
    `secrets`, `widgets` and `jobs` from a local machine), or Databricks Connect, which includes the SDK. Better
    still, keep file listing out of the function you unit test.

    **Why:** interviewers use this to check that you know which parts are Databricks-only.

**Q16. You ran `%pip install --upgrade <package>` but the old version is still imported. Why?**

??? success "Answer"
    "`%pip` commands do not automatically restart the Python process." Run `dbutils.library.restartPython()` after
    installing. The library is notebook-scoped: other notebooks on the same cluster do not see it, and it must be
    reinstalled in a new session.

    **Why:** Python already imported the old module into memory.

**Q17. What changed when Repos became Git folders?**

??? success "Answer"
    Only the terminology and location rules: Git folders can live at any depth under `/Workspace/Users/<email>/`
    (Repos only at `/Workspace/Repos/<email>/<name>`), you create them with **New** > **Git folder**, they support
    more asset types, and they need a remote URL. Existing `/Repos` paths keep working.

    **Why:** both names are in use; say "Git folders, formerly Repos" ([What happened to Databricks Repos?](https://docs.databricks.com/aws/en/repos/what-happened-repos)).

**Q18. Two engineers work in the same Git folder. One switches to a feature branch and the other's notebook
disappears. What happened, and what is the practice?**

??? success "Answer"
    A branch switch applies to everyone using that Git folder, and "Switching branches might delete workspace assets
    when the new branch doesn't contain these assets". Each developer should clone their own Git folder and work on
    their own branch; "Only one user performs Git operations on each Git folder."

    **Why:** a Git folder is one working copy, not one per user.

**Q19. You committed a notebook, but the pull request shows no outputs. Bug?**

??? success "Answer"
    No. "Notebook outputs aren't included in commits by default when notebooks are saved in source file formats". For
    IPYNB notebooks, outputs can be committed only after a workspace admin allows it and the
    `.databricks/commit_outputs` file says so.

    **Why:** outputs can contain data; keeping them out of Git is the safe default.

**Q20. How does Databricks decide that `load_orders.py` in a Git folder is a notebook and not a Python file?**

??? success "Answer"
    A `.py` file is a notebook if it "contains the string `Databricks notebook source` in a comment in the first
    line"; `# COMMAND ----------` lines separate cells. Otherwise it is a workspace file you can import.

    **Why:** this matters because "A notebook cannot be imported as a Python module on Databricks Runtime 16.0 and
    above" ([What are workspace files?](https://docs.databricks.com/aws/en/files/workspace)): shared code must be a
    plain `.py` file.

**Q21. A colleague wants to keep a 2 GB CSV of historical orders in the workspace next to the notebook. Good idea?**

??? success "Answer"
    No. "Workspace file size is limited to 500MB", and Databricks recommends workspace files only for small data
    files for development and testing. Put it in a Unity Catalog volume, for example
    `/Volumes/shop/bronze/landing/orders/`.

    **Why:** volumes are governed storage for files; the workspace is for code and small files.

**Q22. Write SQL that lists today's 20 longest-running statements from the query history system table.**

??? success "Answer"
    *Databricks only, not run here. Column names from [Query history system table reference](https://docs.databricks.com/aws/en/admin/system-tables/query-history).*

    ```sql
    SELECT statement_id, executed_by, statement_type, execution_status, total_duration_ms
    FROM system.query.history
    WHERE start_time >= current_date()
    ORDER BY total_duration_ms DESC
    LIMIT 20;
    ```

    **Why:** the UI shows one query at a time; the system table lets you rank and group. By default only admins can
    read this table, and `statement_text` is redacted unless you are an account admin or in the
    `databricks_pii_access` group.

**Q23. `display(df)` shows 10,000 rows, but `shop.silver.orders` has 1.2 million. Did the query lose rows?**

??? success "Answer"
    No. "Table results are limited to 10,000 rows or 2 MB, whichever is lower." Use `df.count()` or an aggregate to
    check totals, and write results to a table rather than relying on what the notebook shows.

    **Why:** the display is a preview, not the result set.

**Q24. You want to practise Scala and classic cluster sizing on Free Edition. Will it work?**

??? success "Answer"
    No. Free Edition is serverless-only ("Custom compute configurations are not supported"), and "R and Scala" are
    not supported. Practise Python and SQL there; for classic compute, a free trial (full platform, credits for 14
    days) is the documented option.

    **Why:** knowing the limits saves a wasted evening before the interview.

**Q25. What is the difference between Databricks Free Edition, the free trial and Community Edition?**

??? success "Answer"
    Free Edition: no cost, for learning, non-commercial, one serverless workspace with daily quotas. Free trial: for
    business evaluation, full platform, usage credits valid for 14 days. Community Edition: the legacy free product,
    "retired in 2025" and replaced by Free Edition ([Sign up for Databricks Free
    Edition](https://docs.databricks.com/aws/en/getting-started/free-edition)).

    **Why:** an interviewer may ask how you practised; give the current name.

**Q26. With Databricks Connect, where does each line run?**

*Databricks only, not run here. Syntax from [Tutorial: Run Python code on serverless compute](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/python/tutorial-serverless).*

```python
orders = spark.read.table("shop.silver.orders")
big = orders.filter("amount > 100")
rows = big.count()
print(f"{rows} large orders")
```

??? success "Answer"
    The read and the filter build a plan that runs on Databricks compute when `count()` is called; the count comes
    back to the laptop; `print` runs locally. "General code runs locally", "DataFrame APIs are executed on
    Databricks compute".

    **Why:** Databricks Connect is built on Spark Connect: the client sends plans, the server runs them.

**Q27. Name two ways to run a notebook every night at 2 a.m., and say which one you would choose.**

??? success "Answer"
    A Lakeflow job (formerly Databricks Jobs, the ["Workflows" menu](https://docs.databricks.com/aws/en/release-notes/product/2025/june)) with a notebook task and a schedule, or a driver
    notebook that loops over `dbutils.notebook.run()` and is itself scheduled. Choose the Lakeflow job: the docs call
    it the "Recommended method for orchestrating notebooks", with dependencies, retries, schedules and triggers, while
    `dbutils.notebook.run()` is for cases "Jobs cannot support", such as metadata-driven runs.

    **Why:** orchestration belongs in the orchestrator, where failures, retries and history are visible.

## Sources

- [Navigate the Analytics and AI workspace UI](https://docs.databricks.com/aws/en/workspace/navigate-workspace) (last updated Nov 9, 2026)
- [Workspace UI](https://docs.databricks.com/aws/en/workspace/) (last updated Nov 3, 2026)
- [Workspace browser](https://docs.databricks.com/aws/en/workspace/workspace-browser) (last updated Nov 3, 2026)
- [Introduction to workspace objects](https://docs.databricks.com/aws/en/workspace/workspace-assets) (last updated Nov 6, 2026)
- [Databricks components](https://docs.databricks.com/aws/en/getting-started/concepts) (last updated Oct 29, 2026)
- [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026)
- [Genie Agents](https://docs.databricks.com/aws/en/genie-agents/) (last updated Nov 2, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [Configure compute for jobs](https://docs.databricks.com/aws/en/jobs/compute) (last updated Nov 9, 2026)
- [Configure and edit tasks in Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/configure-task) (last updated Nov 5, 2026)
- [Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/) (last updated Oct 12, 2026)
- [Develop code in Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/notebooks-code) (last updated Oct 27, 2026)
- [Notebook compute resources](https://docs.databricks.com/aws/en/notebooks/notebook-compute) (last updated Sep 11, 2026)
- [Known limitations of Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/notebook-limitations) (last updated Oct 28, 2026)
- [Manage Databricks notebook format](https://docs.databricks.com/aws/en/notebooks/notebook-format) (last updated Nov 3, 2026)
- [Import and export Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/notebook-export-import) (last updated Sep 11, 2026)
- [Query and visualize data from a notebook](https://docs.databricks.com/aws/en/getting-started/quick-start) (last updated Feb 13, 2025)
- [Notebook-scoped Python libraries](https://docs.databricks.com/aws/en/libraries/notebooks-python-libraries) (last updated Nov 4, 2026)
- [Databricks widgets](https://docs.databricks.com/aws/en/notebooks/widgets) (last updated Nov 9, 2026)
- [Orchestrate Databricks notebooks and modularize code](https://docs.databricks.com/aws/en/notebooks/notebook-workflows) (last updated Nov 2, 2026)
- [Databricks Utilities (dbutils) reference](https://docs.databricks.com/aws/en/dev-tools/databricks-utils) (last updated Nov 6, 2026)
- [Secret management](https://docs.databricks.com/aws/en/security/secrets/) (last updated Nov 6, 2026)
- [Workspace secret scopes](https://docs.databricks.com/aws/en/security/secrets/workspace-secret-scopes) (last updated Nov 6, 2026)
- [Secrets in Unity Catalog](https://docs.databricks.com/aws/en/security/secrets/unity-catalog-secrets) (last updated Nov 6, 2026)
- [Serverless compute limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations) (last updated Nov 5, 2026)
- [Databricks SDK for Python](https://docs.databricks.com/aws/en/dev-tools/sdk-python) (last updated Sep 11, 2026)
- [What are workspace files?](https://docs.databricks.com/aws/en/files/workspace) (last updated Sep 11, 2026)
- [Work with files on Databricks](https://docs.databricks.com/aws/en/files/) (last updated Nov 4, 2026)
- [Databricks Git folders](https://docs.databricks.com/aws/en/repos/) (last updated Sep 11, 2026)
- [What happened to Databricks Repos?](https://docs.databricks.com/aws/en/repos/what-happened-repos) (last updated Sep 11, 2026)
- [Databricks Git folders concepts](https://docs.databricks.com/aws/en/repos/git-folders-concepts) (last updated Sep 11, 2026)
- [Create and manage Git folders](https://docs.databricks.com/aws/en/repos/git-operations-with-repos) (last updated Sep 11, 2026)
- [CI/CD with Databricks Git folders](https://docs.databricks.com/aws/en/repos/ci-cd) (last updated Sep 11, 2026)
- [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (last updated Nov 5, 2026)
- [Databricks SQL editor](https://docs.databricks.com/aws/en/sql/user/sql-editor/) (last updated Oct 30, 2026)
- [Write queries in the new SQL editor](https://docs.databricks.com/aws/en/sql/user/sql-editor/write-queries) (last updated Oct 27, 2026)
- [Work with parameter widgets](https://docs.databricks.com/aws/en/sql/user/sql-editor/parameter-widgets) (last updated Oct 27, 2026)
- [Query history](https://docs.databricks.com/aws/en/sql/user/queries/query-history) (last updated Sep 11, 2026)
- [Query history system table reference](https://docs.databricks.com/aws/en/admin/system-tables/query-history) (last updated Nov 4, 2026)
- [What is Catalog Explorer?](https://docs.databricks.com/aws/en/catalog-explorer/) (last updated Sep 11, 2026)
- [Explore database objects](https://docs.databricks.com/aws/en/discover/database-objects) (last updated Sep 11, 2026)
- [Lineage in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage) (last updated Nov 4, 2026)
- [Sign up for Databricks Free Edition](https://docs.databricks.com/aws/en/getting-started/free-edition) (last updated Sep 11, 2026)
- [Databricks Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations) (last updated Oct 18, 2026)
- [Sign up for Databricks](https://docs.databricks.com/aws/en/getting-started/free-trial-vs-free-edition) (last updated Oct 27, 2026)
- [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/) (last updated Oct 20, 2026)
- [Databricks CLI tutorial](https://docs.databricks.com/aws/en/dev-tools/cli/tutorial) (last updated Sep 11, 2026)
- [Databricks CLI commands](https://docs.databricks.com/aws/en/dev-tools/cli/commands) (last updated Oct 28, 2026)
- [`workspace` command group](https://docs.databricks.com/aws/en/dev-tools/cli/reference/workspace-commands), [`fs` command group](https://docs.databricks.com/aws/en/dev-tools/cli/reference/fs-commands), [`secrets` command group](https://docs.databricks.com/aws/en/dev-tools/cli/reference/secrets-commands), [`jobs` command group](https://docs.databricks.com/aws/en/dev-tools/cli/reference/jobs-commands) (each last updated Sep 11, 2026)
- [Databricks Connect](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/) (last updated Sep 11, 2026)
- [Tutorial: Run Python code on serverless compute](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/python/tutorial-serverless) (last updated Sep 11, 2026)
- [Databricks Utilities with Databricks Connect for Python](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/python/databricks-utilities) (last updated Oct 30, 2026)
