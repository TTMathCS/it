# 1. What Databricks is and why companies use it

*Before an interviewer asks how you would build a silver table, they often ask something simpler: what is
Databricks, what is a lakehouse, and why would a company pick it over a data warehouse? This chapter answers those
questions in today's product names (with the older names interviewers still use), shows where your data and your
compute actually live, separates the open-source pieces from the Databricks-only ones, and ends with a map of the
rest of the book. It introduces Red Rock Supply, the small shop whose data every chapter uses.*

!!! abstract "In this chapter"
    **You will learn:**

    - what problem Databricks solves, and how a lakehouse differs from a data warehouse and a plain data lake
    - the main pieces of the platform in their current names, each with its older name: Apache Spark, Delta Lake,
      Unity Catalog, Lakeflow (Connect, pipelines, Jobs), Databricks SQL, notebooks, serverless compute,
      Declarative Automation Bundles, OpenSharing, and the AI/BI and machine learning tools
    - accounts and workspaces, the control plane and the compute plane (classic and serverless), and where the data
      is stored
    - which clouds Databricks runs on and how it bills (DBUs)
    - which pieces are open source and which need Databricks, with a small run showing that a Delta table is
      Parquet files plus a log
    - what a data engineer does on Databricks in a normal day, and which chapters to read first for an interview

    **You need:** nothing. Some SQL helps; the [SQL course](../../databases/sql/index.md) covers it.

    **Levels:** sections 1.1 to 1.3 and 1.8 beginner, 1.4 to 1.7 intermediate. Nothing here is expert level; the
    deep dives start in chapter 3.

## 1.1 The problem: Red Rock Supply's data is in too many places

*Level: beginner.*

**Red Rock Supply** is a small online shop that sells outdoor gear: tents, packs, stoves. It is the example used in
every chapter of this book. Its data looks like most companies' data, only smaller:

- The web shop writes every order event as a JSON file into cloud storage, for example
  `{"order_id": 1001, "customer_id": 7, "order_ts": "2026-03-01T10:15:00Z", "status": "PLACED", "amount": "59.90", "currency": "CAD", "items": [{"product_id": 3, "qty": 2, "unit_price": "29.95"}]}`.
- The shop's application database holds `customers`, `products`, `orders` and `order_items`.
- Finance wants daily revenue; marketing wants to know which customers come back; someone wants to forecast tent
  demand for the summer.

A common older setup splits this across two systems. The raw files stay in cheap cloud storage (a **data lake**), a
nightly job copies a cleaned part of them into a separate **data warehouse** for reports, and the data scientists
read the raw files directly because the warehouse does not hold what they need. The result is two copies of the
data, two sets of permissions, extra pipelines that copy between them, and reports that disagree with the models
because they were built from different copies at different times.

Databricks describes itself as "a unified, open analytics platform for building, deploying, sharing, and
maintaining enterprise-grade data, analytics, and AI solutions at scale", which "integrates with cloud storage and
security in your cloud account, and manages and deploys cloud infrastructure for you" ([What is
Databricks?](https://docs.databricks.com/aws/en/introduction/)). In plain words: one platform, on top of the
company's own cloud storage, where data engineering, SQL reporting and machine learning all work from the same
tables. The docs call the platform the **Databricks Data + AI Platform**. Older Databricks material calls it the
"Data Intelligence Platform": a Databricks blog post of November 15, 2023 is titled [What is a data intelligence
platform](https://www.databricks.com/blog/what-is-a-data-intelligence-platform), and the old product address
`databricks.com/product/data-intelligence-platform` now redirects to the [Data + AI
Platform](https://www.databricks.com/product/platform) page. No official page states when or why the name changed
(not verified).

In this book Red Rock's tables live in a Unity Catalog catalog called `shop`, with one schema per medallion layer:
`shop.bronze`, `shop.silver` and `shop.gold` (chapter 7 explains the layers). The tables are:

- `customers(customer_id INT, name STRING, email STRING, city STRING, country STRING, updated_at TIMESTAMP)`
- `products(product_id INT, name STRING, category STRING, price DECIMAL(10,2))`
- `orders(order_id INT, customer_id INT, order_ts TIMESTAMP, status STRING, amount DECIMAL(10,2), currency STRING)`
- `order_items(order_id INT, product_id INT, qty INT, unit_price DECIMAL(10,2))`

## 1.2 Data warehouse, data lake and lakehouse

*Level: beginner.*

**A data warehouse** is a database built for analytics: clean, structured tables and fast SQL for business
intelligence (BI) reports. The Databricks lakehouse page notes that warehouses have "powered business intelligence
(BI) decisions for about 30 years", are "designed for data that is unlikely to change with high frequency", and that
"many data warehouses rely on proprietary formats, which often limit support for machine learning"
([What is a data lakehouse?](https://docs.databricks.com/aws/en/lakehouse/)).

**A data lake** is cheap cloud object storage (Amazon S3, Azure Data Lake Storage, Google Cloud Storage) holding
files of any kind. The same page: "a data lake permanently and cheaply stores data of any nature in any format", and
"many organizations use data lakes for data science and machine learning, but not for BI reporting due to its
unvalidated nature". A folder of files has no transactions: a job that fails halfway leaves half-written files, and
nothing stops a writer from adding a file with the wrong columns.

**A data lakehouse** "is a data management system that combines the benefits of data lakes and data warehouses".
Per the same page, it provides "open, direct access to data stored in standard data formats", "indexing protocols
optimized for machine learning and data science", and "low query latency and high reliability for BI and advanced
analytics", by "combining an optimized metadata layer with validated data stored in standard formats in cloud object
storage".

| | Data warehouse | Data lake | Lakehouse |
| --- | --- | --- | --- |
| Where data is stored | Inside the warehouse, often in a proprietary format | Files in cloud object storage | Files in cloud object storage, in open formats (Delta Lake on Databricks) |
| Kinds of data | Structured tables | Anything: JSON, CSV, Parquet, images, logs | Anything; tables get a schema and transactions |
| Transactions and schema checks | Yes | No (a folder of files) | Yes, from the table format's transaction log |
| Main users | BI analysts | Data scientists, engineers | BI, data engineering and ML on the same tables |
| Typical weakness | Copies data in; ML tools struggle with the format | Unreliable for reporting; no transactions | You still need good design (layers, governance) |

The lakehouse page says the Databricks lakehouse rests on three technologies:

- **Apache Spark**, "a massively scalable engine that runs on compute resources decoupled from storage";
- **Delta Lake**, "an optimized storage layer that supports ACID transactions and schema enforcement";
- **Unity Catalog**, "a unified, fine-grained governance solution for data and AI".

Compute **decoupled from storage** means the files sit in object storage and machines are started only when there
is work to do; you can stop every machine and the data is still there.

The same page links the lakehouse to the **medallion architecture**: data "moves through layers of staging and
transformation", usually called bronze (raw), silver (validated) and gold (enriched). That pattern is the subject of
[chapter 7](07-Medallion-Architecture.md).

!!! warning "A lakehouse still does data warehousing"
    "Lakehouse instead of a warehouse" does not mean "no warehouse features". Databricks describes Databricks SQL as
    "a cloud data warehouse built on lakehouse architecture" that "runs directly on your data lake" ([Data
    warehousing on Databricks](https://docs.databricks.com/aws/en/sql/)). The difference is where the data lives
    and in what format, not whether you can run fast SQL.

!!! tip "In the interview"
    **"What is a lakehouse?"** A lakehouse combines a data lake and a data warehouse: the data stays as files in
    open formats in cheap cloud object storage, and a table format with a transaction log (Delta Lake on
    Databricks) adds what the lake lacked: ACID transactions, schema enforcement and time travel. On top of that,
    one governance layer (Unity Catalog) controls access. The point is one copy of the data serving BI, data
    engineering and ML, instead of a lake plus a warehouse kept in sync by copy jobs.

!!! tip "In the interview"
    **"Why Databricks over a traditional data warehouse?"** Start from the problem, not the product: one copy of
    the data in open formats in our own cloud storage, used by SQL, Python pipelines, streaming and ML alike, with
    compute that scales separately from storage and one place for permissions and lineage. Then be fair: a team
    doing only BI on structured data may be well served by a warehouse, and Databricks SQL is itself a warehouse
    product; the gain is largest when the same data also feeds engineering pipelines, streaming and ML.

## 1.3 The pieces of the platform, in today's names

*Level: beginner.*

Databricks renamed several products in 2025 and 2026. Interviewers who learned the platform earlier will use the old
names, so learn both and say both once ("Lakeflow pipelines, formerly Delta Live Tables"). Figure 1.1 shows how the
pieces stack; the table below lists them.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 430" role="img" aria-label="The Databricks platform as layers. At the top, how you work: notebooks, SQL editor, Git folders, bundles, CLI and REST API. Below, four workload areas: Lakeflow for ingestion, pipelines and jobs; Databricks SQL with SQL warehouses and AI/BI; AI and machine learning with MLflow and Model Serving; OpenSharing for sharing outside the organization. Below them, compute running Apache Spark and Photon; then Unity Catalog governance; then Delta Lake tables and volumes; and at the bottom your cloud object storage.">
<g font-size="13" fill="currentColor" text-anchor="middle">
<rect x="8" y="8" width="624" height="40" rx="6" fill="none" stroke="currentColor"/>
<text x="320" y="33">How you work: notebooks, SQL editor, Git folders, bundles, CLI, REST API</text>
<rect x="8" y="62" width="148" height="96" rx="6" fill="none" stroke="currentColor"/>
<text x="82" y="84" font-weight="bold">Lakeflow</text>
<text x="82" y="106">Connect (ingest)</text>
<text x="82" y="124">pipelines (ETL)</text>
<text x="82" y="142">Jobs (orchestrate)</text>
<rect x="166" y="62" width="148" height="96" rx="6" fill="none" stroke="currentColor"/>
<text x="240" y="84" font-weight="bold">Databricks SQL</text>
<text x="240" y="106">SQL warehouses</text>
<text x="240" y="124">AI/BI dashboards</text>
<text x="240" y="142">Genie Agents</text>
<rect x="326" y="62" width="148" height="96" rx="6" fill="none" stroke="currentColor"/>
<text x="400" y="84" font-weight="bold">AI and ML</text>
<text x="400" y="106">MLflow</text>
<text x="400" y="124">Model Serving</text>
<text x="400" y="142">Feature Store</text>
<rect x="484" y="62" width="148" height="96" rx="6" fill="none" stroke="currentColor"/>
<text x="558" y="84" font-weight="bold">OpenSharing</text>
<text x="558" y="106">share data with</text>
<text x="558" y="124">other organizations</text>
<text x="558" y="142">(was Delta Sharing)</text>
<rect x="8" y="172" width="624" height="52" rx="6" fill="none" stroke="currentColor"/>
<text x="320" y="194" font-weight="bold">Compute: serverless, classic clusters, SQL warehouses</text>
<text x="320" y="214">running Apache Spark (and Photon, the Databricks-native engine)</text>
<rect x="8" y="238" width="624" height="52" rx="6" fill="none" stroke="currentColor"/>
<text x="320" y="260" font-weight="bold">Unity Catalog: governance</text>
<text x="320" y="280">permissions, lineage, audit for catalog.schema.table (e.g. shop.silver.orders)</text>
<rect x="8" y="304" width="624" height="52" rx="6" fill="none" stroke="currentColor"/>
<text x="320" y="326" font-weight="bold">Delta Lake tables and volumes</text>
<text x="320" y="346">tables = Parquet data files + a transaction log; volumes hold other files</text>
<rect x="8" y="370" width="624" height="52" rx="6" fill="none" stroke="currentColor" stroke-dasharray="6 4"/>
<text x="320" y="392" font-weight="bold">Cloud object storage</text>
<text x="320" y="412">Amazon S3, Azure Data Lake Storage Gen2, Google Cloud Storage</text>
</g>
</svg>
<figcaption>Figure 1.1. The Databricks platform as layers. The data sits as open-format files in cloud object storage; Delta Lake turns them into tables; Unity Catalog governs them; compute running Spark processes them; the workloads on top (Lakeflow, Databricks SQL, AI and ML, OpenSharing) all use the same tables.</figcaption>
</figure>

| Piece | What it does | Older name | Official page (last updated) |
| --- | --- | --- | --- |
| Apache Spark | The distributed engine: "the technology powering compute clusters and SQL warehouses in Databricks" | | [Apache Spark overview](https://docs.databricks.com/aws/en/spark/) (Sep 11, 2026) |
| Photon | "the Databricks-native vectorized query engine"; the default engine for all SQL warehouses | | [What is Photon?](https://docs.databricks.com/aws/en/compute/photon) (Sep 11, 2026) |
| Delta Lake | The table format: Parquet data files plus a transaction log; "the default format for all operations on Databricks" | | [What is Delta Lake in Databricks?](https://docs.databricks.com/aws/en/delta/) (Sep 11, 2026) |
| Unity Catalog | Governance: access control, auditing, lineage, discovery, the `catalog.schema.object` namespace | (before it: the legacy Hive metastore, still provided "for customers that have not adopted Unity Catalog") | [What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) (Sep 11, 2026) |
| Lakeflow Connect | Ingestion connectors for databases, SaaS applications, files and streams | | [What is Lakeflow Connect?](https://docs.databricks.com/aws/en/ingestion/overview) (Nov 5, 2026) |
| Lakeflow pipelines ("Spark Declarative Pipelines on Lakeflow") | Declarative batch and streaming pipelines of streaming tables and materialized views | Delta Live Tables (DLT) | [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (Sep 11, 2026) |
| Lakeflow Jobs | Orchestration: jobs made of tasks, with triggers, parameters and notifications | Databricks Jobs; the menu item was "Workflows" | [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (Oct 29, 2026) |
| Lakeflow Designer | Visual, drag-and-drop data preparation backed by code | | [Data engineering with Databricks](https://docs.databricks.com/aws/en/data-engineering/) (Nov 5, 2026) |
| Databricks SQL and SQL warehouses | The data warehousing product and the compute it runs on | | [Data warehousing on Databricks](https://docs.databricks.com/aws/en/sql/) (Oct 15, 2026) |
| Notebooks | Code and results in one document; Python, SQL, Scala and R | | [Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/) (Oct 12, 2026) |
| Git folders | Workspace folders synced with a Git repository | Repos | [Databricks components](https://docs.databricks.com/aws/en/getting-started/concepts) (Oct 29, 2026) |
| Serverless compute | Compute that Databricks allocates and manages for notebooks, jobs and pipelines | | [Connect to serverless compute](https://docs.databricks.com/aws/en/compute/serverless/) (Oct 22, 2026) |
| Declarative Automation Bundles | Projects (code plus YAML definitions of jobs, pipelines and more) deployed as one unit, for CI/CD | Databricks Asset Bundles (DABs) | [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (Nov 5, 2026) |
| OpenSharing | Sharing data and AI assets with people outside your organization, "regardless of whether they use Databricks" | Delta Sharing | [What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/) (Oct 27, 2026); rename: [From Delta Sharing to OpenSharing](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next) (blog, Nov 5, 2026) |
| AI/BI: dashboards and Genie Agents | Dashboards, and natural-language questions over curated data | Genie Agents were "Genie Spaces" | [Databricks AI/BI](https://docs.databricks.com/aws/en/ai-bi/) (Oct 30, 2026); [Genie Agents](https://docs.databricks.com/aws/en/genie-agents/) (Nov 2, 2026) |
| Machine learning | Databricks Runtime for ML, managed MLflow, Feature Store, Model Serving | | [Machine learning on Databricks](https://docs.databricks.com/aws/en/machine-learning/) (Nov 5, 2026) |
| Lakebase | A managed Postgres database for transactional (OLTP) work, integrated with the platform | | [What is Databricks?](https://docs.databricks.com/aws/en/introduction/) (Oct 29, 2026) |

A few words on each group, and where the book covers it.

**Engine and storage.** Apache Spark splits work across many machines ([chapter 3](03-Apache-Spark.md)). On
Databricks it runs inside the **Databricks Runtime**, which "includes Apache Spark but also adds a number of components
and updates" ([Databricks components](https://docs.databricks.com/aws/en/getting-started/concepts)), among them
Photon. Delta Lake is the table format: "by default, all tables created in Databricks are Delta tables", and a Delta
table "stores data as a directory of files on cloud object storage" (same page). [Chapter 4](04-Delta-Lake.md) goes
deep; section 1.6 shows a tiny run.

**Governance.** Unity Catalog "is automatically enabled for all Databricks workspaces created after November 8, 2023"
([What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/)). It gives every table
a three-part name such as `shop.silver.orders` and decides who may read or change it ([chapter 5](05-Unity-Catalog.md)).

**Lakeflow** is "a unified solution for ingestion, transformation, and orchestration of your data, and includes
Lakeflow Connect, Lakeflow pipelines, Lakeflow Designer, and Lakeflow Jobs" ([Data engineering with
Databricks](https://docs.databricks.com/aws/en/data-engineering/)).

- **Lakeflow Connect** brings data in: managed connectors (databases with change data capture, SaaS applications
  such as Salesforce, file services, message buses), or SQL and Spark APIs when you need more control
  ([chapter 8](08-Bronze-Ingestion.md)).
- **Lakeflow pipelines**, formerly Delta Live Tables, are "built on Apache Spark Declarative Pipelines". You declare
  the tables you want and the pipeline works out the order and runs it ([Spark Declarative Pipelines on
  Lakeflow](https://docs.databricks.com/aws/en/ldp/)). In Python, `import dlt` becomes
  `from pyspark import pipelines as dp`; old code still works ([What happened to
  DLT?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)). Release notes from mid-2025 use a third
  name, "Lakeflow Declarative Pipelines" ([Lakeflow pipelines release
  notes](https://docs.databricks.com/aws/en/release-notes/dlt/)), and the docs URLs contain `ldp`, so you may also
  hear "LDP". Chapters [13](13-Declarative-Pipelines.md) and [14](14-Data-Quality-and-CDC.md).
- **Lakeflow Jobs**, formerly Databricks Jobs (the left menu item was "Workflows"), runs tasks (notebooks,
  pipelines, Python scripts, SQL and more) as a graph, on a schedule or when new data arrives
  ([Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/); chapter [15](15-Lakeflow-Jobs.md)). The June 2025
  release notes record both changes: "The product known as Databricks Jobs is now Lakeflow Jobs", and "The
  **Pipelines** and **Workflows** items in the left navigation have been removed" in favor of **Jobs & Pipelines**.

**Databricks SQL** runs on **SQL warehouses**, compute made for SQL and BI. There are "three types of SQL warehouses:
Classic, Pro, and Serverless", and "Databricks recommends using serverless warehouses where available"
([Databricks components](https://docs.databricks.com/aws/en/getting-started/concepts)). The SQL dialect has its own
extras ([chapter 17](17-Databricks-SQL-vs-Standard.md) onward).

**Notebooks and serverless compute.** Most engineering work starts in a notebook attached to compute. Serverless
compute lets you "run workloads without provisioning any compute resources in your cloud account", is "available by
default in most workspaces", and "workspaces that have Unity Catalog enabled automatically have access to serverless
compute" ([Connect to serverless compute](https://docs.databricks.com/aws/en/compute/serverless/)). Chapters
[2](02-Workspace-Tour.md) and [6](06-Compute.md).

**Declarative Automation Bundles**, formerly Databricks Asset Bundles, are "an infrastructure-as-code (IaC) approach
to managing your Databricks projects": jobs, pipelines and other resources are described in YAML files next to the
code and deployed together to each environment ([What are Declarative Automation
Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/); chapter 16).

**OpenSharing**, formerly Delta Sharing, shares live data without copying it. Databricks-to-Databricks sharing
works between Unity Catalog workspaces; the Databricks-to-Open protocol shares tables "with users on any computing
platform" ([What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/)). The Databricks blog says
"Delta Sharing has evolved into OpenSharing" and that "existing Delta Sharing setups keep working"
([From Delta Sharing to OpenSharing](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next)).
[Chapter 23](23-Governance-and-Operations.md).

**AI/BI and machine learning, briefly.** AI/BI covers dashboards, **Genie Agents** (a natural-language chat over
curated data; "Genie Agents were formerly known as Genie Spaces") and Unity Catalog semantics such as metric views
([Databricks AI/BI](https://docs.databricks.com/aws/en/ai-bi/), [Genie
Agents](https://docs.databricks.com/aws/en/genie-agents/)). For machine learning, Databricks provides the Databricks
Runtime for Machine Learning, a managed MLflow, a Feature Store and Model Serving ([Databricks
components](https://docs.databricks.com/aws/en/getting-started/concepts)). A data engineer's job is mostly to feed
these tools clean gold tables; this book does not cover them further.

!!! tip "In the interview"
    **"What is Lakeflow? Give the old names."** Lakeflow is Databricks' data engineering family: Lakeflow Connect
    for ingestion, Lakeflow pipelines (formerly Delta Live Tables, DLT) for declarative ETL, and Lakeflow Jobs
    (formerly Databricks Jobs, which most people called Workflows) for orchestration. Say both names once, for
    example "Lakeflow pipelines, which used to be Delta Live Tables", and move on. The renames are documented in
    [What happened to DLT?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) and the
    [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june).

## 1.4 Account, workspace, control plane and compute plane

*Level: intermediate.*

**Account and workspaces.** A Databricks **account** "is the top-level construct": at the account level you manage
identities, workspaces, Unity Catalog metastores, and billing ([High-level
architecture](https://docs.databricks.com/aws/en/getting-started/high-level-architecture)). A **workspace** is "the
collaboration environment where users run compute workloads such as ingestion, interactive exploration, scheduled
jobs, and ML training". A Unity Catalog **metastore** is "the central governance system for data assets"; it is
attached to workspaces, and one metastore can be linked "to multiple Databricks workspaces in the same region, giving
each workspace the same data view" (same page). Red Rock might have a development workspace and a production
workspace, both seeing the `shop` catalog through one metastore.

**Control plane and compute plane.** "Databricks operates out of a control plane and a compute plane" (same page):

- The **control plane** "includes the backend services that Databricks manages in your Databricks account. The
  control plane is located in the Databricks account, not your cloud account. The web application is in the control
  plane."
- The **compute plane** "is where your data is processed". There are two kinds:
    - **Classic compute plane**: for classic compute, "the compute resources are in your AWS account" (or your Azure
      or Google Cloud account), inside "each workspace's virtual network in the customer's AWS account".
    - **Serverless compute plane**: for serverless compute, the resources "run in a serverless compute plane in your
      Databricks account", in the same region as the workspace, "within a network boundary for the workspace, with
      various layers of security to isolate different Databricks customer workspaces".

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 330" role="img" aria-label="Two boxes. Left, the Databricks account: the control plane with the web application and backend services, the serverless compute plane running serverless notebooks, jobs, pipelines and SQL warehouses, and default storage used by serverless workspaces. Right, your cloud account: the classic compute plane with compute you configure in your own virtual network, and your cloud object storage holding your tables, volumes and raw files, and the workspace storage bucket of classic workspaces. Arrows: the control plane manages both compute planes; both compute planes read and write your cloud storage.">
<defs><marker id="arr-1-2" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="currentColor"/></marker></defs>
<g font-size="13" fill="currentColor" text-anchor="middle">
<text x="158" y="20" font-weight="bold">Databricks account</text>
<text x="482" y="20" font-weight="bold">Your cloud account (AWS, Azure or GCP)</text>
<rect x="8" y="30" width="300" height="292" rx="8" fill="none" stroke="currentColor" stroke-dasharray="6 4"/>
<rect x="332" y="30" width="300" height="292" rx="8" fill="none" stroke="currentColor" stroke-dasharray="6 4"/>
<rect x="24" y="46" width="268" height="96" rx="6" fill="none" stroke="currentColor"/>
<text x="158" y="70" font-weight="bold">Control plane</text>
<text x="158" y="92">web application and</text>
<text x="158" y="112">backend services</text>
<text x="158" y="132">that Databricks manages</text>
<rect x="24" y="162" width="268" height="84" rx="6" fill="none" stroke="currentColor"/>
<text x="158" y="186" font-weight="bold">Serverless compute plane</text>
<text x="158" y="208">serverless notebooks, jobs,</text>
<text x="158" y="228">pipelines, SQL warehouses</text>
<rect x="24" y="262" width="268" height="48" rx="6" fill="none" stroke="currentColor"/>
<text x="158" y="282" font-weight="bold">Default storage</text>
<text x="158" y="300">(used by serverless workspaces)</text>
<rect x="348" y="46" width="268" height="96" rx="6" fill="none" stroke="currentColor"/>
<text x="482" y="70" font-weight="bold">Classic compute plane</text>
<text x="482" y="92">compute you configure,</text>
<text x="482" y="112">running in your own</text>
<text x="482" y="132">virtual network</text>
<rect x="348" y="162" width="268" height="148" rx="6" fill="none" stroke="currentColor"/>
<text x="482" y="186" font-weight="bold">Your cloud object storage</text>
<text x="482" y="210">your tables, volumes and raw files</text>
<text x="482" y="230">(registered in Unity Catalog)</text>
<text x="482" y="262">workspace storage bucket</text>
<text x="482" y="282">(classic workspaces)</text>
</g>
<g stroke="currentColor" fill="none" stroke-width="1.5">
<line x1="292" y1="94" x2="345" y2="94" marker-end="url(#arr-1-2)"/>
<line x1="158" y1="142" x2="158" y2="159" marker-end="url(#arr-1-2)"/>
<line x1="482" y1="142" x2="482" y2="159" marker-end="url(#arr-1-2)"/>
<line x1="292" y1="210" x2="345" y2="230" marker-end="url(#arr-1-2)"/>
<line x1="158" y1="246" x2="158" y2="259" marker-end="url(#arr-1-2)"/>
</g>
</svg>
<figcaption>Figure 1.2. The control plane (web application, backend services) always runs in the Databricks account and manages compute. Classic compute runs in your own cloud account; serverless compute runs in a serverless compute plane in the Databricks account. Both process the data in your cloud object storage. Serverless workspaces also have Databricks-managed default storage.</figcaption>
</figure>

**Where the data lives.** Your tables are files in cloud object storage, registered in Unity Catalog. Which storage
depends on the workspace type:

- **Classic workspaces** "require you to provide an S3 bucket and prefix to use as the workspace storage bucket",
  which "is in your AWS account" and holds internal workspace system data and, where Unity Catalog was enabled
  automatically, the default workspace catalog ([High-level
  architecture](https://docs.databricks.com/aws/en/getting-started/high-level-architecture)). Your own catalogs and
  tables go in cloud storage you register with Unity Catalog ([chapter 5](05-Unity-Catalog.md)).
- **Serverless workspaces** use **default storage**, "a fully managed object storage platform that provides
  ready-to-use storage in your Databricks account", for workspace storage and for the default catalog; "you can
  create additional catalogs in either default storage or in your own cloud object storage" ([Default storage in
  Databricks](https://docs.databricks.com/aws/en/storage/default-storage)).

So the honest one-line answer is: in a classic setup, your tables and the compute are in your cloud account and the
control plane is Databricks'; with serverless, the compute (and, if you choose default storage, the storage) is in
the Databricks account. Even in classic workspaces, some features (for example Clean Rooms and data classification)
keep metadata, derived data and other artifacts in the workspace's default storage ([Default storage in
Databricks](https://docs.databricks.com/aws/en/storage/default-storage)).

!!! warning "DBFS root and mounts are legacy"
    Older tutorials store data under `dbfs:/` paths and "mounts". The docs say "storing and accessing data using
    DBFS root or DBFS mounts is a deprecated pattern and not recommended by Databricks", and recommend Unity Catalog
    for all data access ([Databricks components](https://docs.databricks.com/aws/en/getting-started/concepts)).
    Use Unity Catalog tables and volumes instead.

**Which clouds.** "Databricks workspaces can be hosted on Amazon AWS, Microsoft Azure, and Google Cloud Platform"
([Databricks clouds and regions](https://docs.databricks.com/aws/en/resources/supported-regions)). You choose the
region when you create a workspace. On Azure the product is called **Azure Databricks**, and its docs live on
Microsoft Learn ([What is Azure Databricks?](https://learn.microsoft.com/en-us/azure/databricks/introduction/));
its introduction page opens with the same description as the AWS one, with Azure services in place of AWS ones. Some features are
available only in some regions; the regions page links the list.

!!! tip "In the interview"
    **"Where is our data processed, and does it leave our cloud account?"** The control plane (web app, backend
    services) is always in the Databricks account. With classic compute, the machines run in our own cloud account
    and virtual network, next to our storage. With serverless compute, the machines run in Databricks' serverless
    compute plane, in the same region, inside a network boundary per workspace, and read our storage from there. So
    the answer depends on which compute we use, and on whether our catalogs use our own storage or Databricks-managed
    default storage.

## 1.5 How Databricks bills: DBUs

*Level: intermediate.*

"Databricks bills based on Databricks units (DBUs), which are units of processing capability per hour based on VM
instance type" ([Databricks components](https://docs.databricks.com/aws/en/getting-started/concepts)). Billing is
handled at the account level (same page).

What else you pay depends on the compute type: "Total costs include Databricks Units (DBUs) plus virtual machine,
disk, and associated network costs. Note that for serverless services, the DBU cost already includes the virtual
machine costs" ([Best practices for cost
optimization](https://docs.databricks.com/aws/en/lakehouse-architecture/cost-optimization/best-practices)). So for
classic compute you get two bills, one from Databricks (DBUs) and one from the cloud provider (the machines); for
serverless the machine cost is inside the DBU price.

The kind of compute matters too. The same page says that for non-interactive workloads, "on job compute, the
non-interactive workloads will cost significantly less than on all-purpose compute". That is why a nightly pipeline
should not run on a shared interactive cluster. Usage is recorded in the system table `system.billing.usage`: each
row has a `usage_unit` (the reference page's example is `DBU`), a `usage_quantity`, and a `cloud` column whose values
are `AWS`, `AZURE` or `GCP` ([Billable usage system table
reference](https://docs.databricks.com/aws/en/admin/system-tables/billing)). Prices are not given here; the
[Compute](https://docs.databricks.com/aws/en/compute/) page points to the Databricks pricing page.
[Chapter 6](06-Compute.md) covers cost in detail.

## 1.6 Open source and Databricks-only

*Level: intermediate.*

Databricks says these "open source projects" were "originally created by Databricks employees": Delta Lake and
OpenSharing, MLflow, Apache Spark and Structured Streaming, Redash, and Unity Catalog ([What is
Databricks?](https://docs.databricks.com/aws/en/introduction/)). Knowing which parts are open matters in an
interview for two reasons: open formats are the main answer to "are we locked in?", and you should know which of
your skills transfer to any Spark platform.

| Piece | Open source? | What Databricks adds or differs |
| --- | --- | --- |
| Apache Spark, Structured Streaming | Yes, Apache projects | Runs them in the Databricks Runtime, with Photon and other additions |
| Delta Lake | Yes ([delta.io](https://delta.io)); "the Delta Lake transaction log has a well-defined open protocol that can be used by any system to read the log" ([What is Delta Lake in Databricks?](https://docs.databricks.com/aws/en/delta/)) | Optimizations and products that "build upon the guarantees provided by Apache Spark and Delta Lake" (same page) |
| Unity Catalog | Yes: "Unity Catalog is also available as an open-source implementation" ([What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/)) | This book uses the Unity Catalog built into Databricks |
| Spark Declarative Pipelines | Yes, in Apache Spark from version 4.1 ([What happened to DLT?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt); [Spark programming guide](https://spark.apache.org/docs/4.2.0/declarative-pipelines-programming-guide.html)) | Lakeflow pipelines add "AUTO CDC, data quality expectations, and a queryable event log", plus continuous mode, update flows and `foreachBatch` sinks ([Apache Spark Declarative Pipelines](https://docs.databricks.com/aws/en/ldp/concepts/spark-declarative-pipelines)) |
| MLflow | Yes | A "fully managed and hosted version of MLflow", with the model registry in Unity Catalog, Model Serving and enterprise security ([MLflow on Databricks](https://docs.databricks.com/aws/en/mlflow/)) |
| OpenSharing | Yes: an open protocol, now a Linux Foundation project ([blog](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next)) | The OpenSharing server "built into Databricks", integrated with Unity Catalog, plus Marketplace and Clean Rooms ([What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/)) |
| Photon, Auto Loader, Lakeflow Connect and Jobs, serverless compute, SQL warehouses, AI/BI, Declarative Automation Bundles | No: these are Databricks features | Photon is described as "Databricks-native" ([What is Photon?](https://docs.databricks.com/aws/en/compute/photon)) |

### See for yourself: a Delta table is Parquet files plus a log

Because Delta Lake is open source, you can see how it works without a Databricks workspace. The run below creates a
Red Rock `orders` table on open-source Spark with Delta Lake, adds two orders, then one more, and lists what is on
disk. There is no Unity Catalog here, so the table is a plain local table called `orders` instead of
`shop.bronze.orders`, and the statement says `USING DELTA`; on Databricks, Delta is already the default. The full
script is `src/ch01/ch01_01_delta_is_files.py`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
sql("""CREATE TABLE orders (
  order_id INT, customer_id INT, order_ts TIMESTAMP,
  status STRING, amount DECIMAL(10,2), currency STRING
) USING DELTA""")
sql("""INSERT INTO orders VALUES
  (1001, 7, TIMESTAMP'2026-03-01 10:15:00', 'PLACED', 59.90, 'CAD'),
  (1002, 3, TIMESTAMP'2026-03-01 11:02:00', 'PLACED', 120.00, 'CAD')""")
sql("INSERT INTO orders VALUES (1003, 7, TIMESTAMP'2026-03-02 09:30:00', 'PLACED', 18.50, 'CAD')")

# 1. What is on disk (checksum .crc side files skipped)
for root, _dirs, files in sorted(os.walk(table_dir)):
    for f in sorted(files):
        if not f.endswith(".crc"):
            print(os.path.relpath(os.path.join(root, f), table_dir))

# 2. The actions recorded in commit 1 (the first INSERT)
with open(os.path.join(table_dir, "_delta_log", "00000000000000000001.json")) as fh:
    for line in fh:
        action = json.loads(line)
        kind = next(iter(action))
        extra = ""
        if kind == "commitInfo":
            extra = " operation=" + action[kind]["operation"]
        if kind == "add":
            extra = " numRecords=" + str(json.loads(action[kind]["stats"])["numRecords"])
        print(kind + extra)

# 3. The table history, read from that log
sql("DESCRIBE HISTORY orders").select("version", "operation").orderBy("version").show()
```

```text
part-00000-1fb29415-9d5f-4309-a675-179fa76d58e2-c000.snappy.parquet
part-00000-79815eda-a65f-4fdf-a004-f21502045852-c000.snappy.parquet
part-00001-6ca22ece-7a0b-4dec-bbbb-124ccfcbc5b9-c000.snappy.parquet
_delta_log/00000000000000000000.json
_delta_log/00000000000000000001.json
_delta_log/00000000000000000002.json

commitInfo operation=WRITE
add numRecords=1
add numRecords=1

+-------+------------+
|version|   operation|
+-------+------------+
|      0|CREATE TABLE|
|      1|       WRITE|
|      2|       WRITE|
+-------+------------+
```

What this shows:

- The data is ordinary **Parquet** files (three of them). Any Parquet reader can open them.
- The `_delta_log` folder holds one JSON **commit** file per table version: version 0 created the table, versions 1
  and 2 are the two inserts. A reader finds the current table by reading the log, not by listing the folder.
- Commit 1 records the operation and one `add` action per new data file. The first `INSERT` had two rows and wrote
  two files, one row each, because the local engine ran that insert as two parallel tasks; the number of files
  follows the work split, not the number of rows.
- `DESCRIBE HISTORY` is just the log read back as a table. Time travel, `MERGE`, ACID commits and schema
  enforcement all come from this log; [chapter 4](04-Delta-Lake.md) shows each one.

On Databricks you rarely look at these files: for a managed table, Unity Catalog "handles both governance and the
underlying file storage lifecycle" ([What is Unity
Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/)). The format is the same.

!!! tip "In the interview"
    **"What in Databricks is open source, and what is not?"** Open: Apache Spark and Structured Streaming, Delta
    Lake (an open protocol any engine can read), MLflow, Unity Catalog (an open-source implementation exists),
    Spark Declarative Pipelines (in Apache Spark from 4.1; Lakeflow pipelines, formerly Delta Live Tables, are
    built on it), and the OpenSharing protocol (formerly Delta Sharing). Databricks-only: Photon, Auto Loader,
    Lakeflow Connect and Lakeflow Jobs (formerly Databricks Jobs, the Workflows menu item), serverless compute, SQL warehouses, and pipeline extras
    such as `AUTO CDC` (formerly `APPLY CHANGES`) and expectations. The data stays in open formats in cloud storage,
    which limits lock-in.

## 1.7 A data engineer's day on Databricks

*Level: intermediate.*

What does the job look like? Here is a plausible day for the engineer who owns Red Rock Supply's order data. The
tools are real; the day is an illustration, and each step points to the chapter that teaches it.

| When | What happens | Tool | Chapter |
| --- | --- | --- | --- |
| Morning | A failure email arrives: last night's job failed at the silver step. Jobs can send notifications "via email, Slack, custom webhooks" ([Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/)). | Lakeflow Jobs (formerly Databricks Jobs, the Workflows menu item): run history, task output | [15](15-Lakeflow-Jobs.md) |
| | The cause: duplicate order events made a `MERGE` fail with "multiple source rows matched". Fix the deduplication, then repair the run: a repair re-runs "only the subset of unsuccessful tasks and any dependent tasks" ([Troubleshoot and repair job failures](https://docs.databricks.com/aws/en/jobs/repair-job-failures)). | Notebook, Delta `MERGE`, repair run | [9](09-Building-Silver.md), [7](07-Medallion-Architecture.md) |
| Late morning | Marketing wants `customers` from a new CRM. Set up ingestion into bronze. | Lakeflow Connect or Auto Loader | [8](08-Bronze-Ingestion.md) |
| After lunch | Add a data quality rule: drop orders with a negative `amount` and count them. | Lakeflow pipelines (formerly Delta Live Tables), expectations | [13](13-Declarative-Pipelines.md), [14](14-Data-Quality-and-CDC.md) |
| | An analyst says the daily sales dashboard is slow. Read the query profile, check file layout and clustering. | SQL warehouse, query profile, `OPTIMIZE` | [22](22-Performance-Tuning.md) |
| Afternoon | Code review, then deploy the changed job and pipeline from Git to production. | Git folders, Declarative Automation Bundles (formerly Databricks Asset Bundles), CLI | 16 |
| End of day | Grant the finance group read access to `shop.gold`; check what last week's jobs cost. | Unity Catalog `GRANT`, system tables | [5](05-Unity-Catalog.md), [23](23-Governance-and-Operations.md) |

Most of the day is SQL and PySpark on Delta tables, organized as bronze, silver and gold. That is why this book
spends its depth on Spark, Delta, the medallion layers and Databricks SQL.

## 1.8 How to read the rest of this book

*Level: beginner.*

**Interview soon?** Read in this order (the same fast path as the [front page](index.md)):

1. [24. The data engineer interview](24-Interview.md): skim the questions to find your weak spots.
2. [7. The medallion architecture](07-Medallion-Architecture.md): asked in almost every Databricks interview.
3. [4. Delta Lake](04-Delta-Lake.md): the transaction log, `MERGE`, time travel.
4. [9. Building silver](09-Building-Silver.md): deduplication, late data, SCD Type 1 and 2.
5. [3. Apache Spark](03-Apache-Spark.md): driver and executors, shuffles, joins, skew.
6. [17. Databricks SQL vs standard SQL](17-Databricks-SQL-vs-Standard.md): `QUALIFY`, `GROUP BY ALL` and the rest.
7. Then [19. The function toolbox](19-Function-Toolbox.md), [25. PySpark coding practice](25-PySpark-Practice.md),
   [22. Performance tuning](22-Performance-Tuning.md), [11. Structured Streaming](11-Structured-Streaming.md), and
   [13](13-Declarative-Pipelines.md) and [14](14-Data-Quality-and-CDC.md) on pipelines.

**Starting out?** Read in order. [Chapter 2](02-Workspace-Tour.md) tours the workspace. To practise on the real
product, **Databricks Free Edition** is "a no-cost version of Databricks" in "a serverless-only, quota-limited
environment"; it "replaced the legacy Databricks Community Edition, which was retired in 2025" ([Sign up for
Databricks Free Edition](https://docs.databricks.com/aws/en/getting-started/free-edition)).

| Part | What it covers |
| --- | --- |
| I. Foundations (1 to 6) | The platform, the workspace, Spark, Delta Lake, Unity Catalog, compute |
| II. The medallion architecture (7 to 12) | Bronze, silver and gold; ingestion; streaming; a full project on Red Rock data |
| III. Lakeflow (13 to 16) | Pipelines (formerly DLT), data quality and CDC, Jobs, CI/CD with bundles |
| IV. Databricks SQL (17 to 21) | The dialect, nested data, functions, table features, SQL programming |
| V. Deep dive (22, 23) | Performance tuning; governance, sharing and operations |
| VI. The interview (24, 25) | 100+ questions with answers; PySpark coding practice |

**How to read the code labels.** *Run here* means the code ran on open-source Apache Spark 4.2 with Delta Lake 4.4.1
and the output shown is real. *Databricks only, not run here* means the code needs a Databricks workspace (Unity
Catalog grants, Auto Loader, Lakeflow pipelines, system tables) and its syntax was checked against the linked page.

## 1.9 Practice questions

*Level: beginner to intermediate.*

**Q1. In two or three sentences, what is a data lakehouse?**

??? success "Answer"
    A data lakehouse is "a data management system that combines the benefits of data lakes and data warehouses".
    The data stays as files in open formats in cloud object storage (the lake part), and a metadata layer with a
    transaction log adds ACID transactions, schemas and fast, reliable queries (the warehouse part). One copy serves
    BI, data engineering and ML.

    **Why:** the key idea is "one copy, open format, warehouse guarantees". An answer that says only "a lake with
    SQL on top" misses the transactions and governance.

**Q2. According to the Databricks lakehouse page, which three technologies does the Databricks lakehouse rest on, and what does each contribute?**

??? success "Answer"
    Apache Spark (a scalable engine on compute decoupled from storage), Delta Lake (a storage layer with ACID
    transactions and schema enforcement) and Unity Catalog (unified, fine-grained governance for data and AI).

    **Why:** this is the shortest accurate description of "how Databricks works" and a good opening to any platform
    question.

**Q3. Give one weakness of a plain data lake and one of a traditional data warehouse that a lakehouse addresses.**

??? success "Answer"
    Data lake: a folder of files has no transactions or schema checks, so a failed job can leave half-written data
    and nothing stops wrong columns; the Databricks page notes lakes are often not used for BI "due to its
    unvalidated nature". Warehouse: data must be copied in, and "many data warehouses rely on proprietary formats,
    which often limit support for machine learning".

    **Why:** the lakehouse keeps the lake's open, cheap storage and adds the warehouse's reliability through the
    table format, so neither copy job nor second system is needed.

**Q4. Red Rock keeps raw order files in a bucket and copies a cleaned subset into a warehouse every night. Finance's revenue report and the data science team's numbers disagree. What is the likely cause, and what would a lakehouse change?**

??? success "Answer"
    The two teams read different copies built at different times with different logic: finance reads the nightly
    warehouse copy, data science reads the raw files. On a lakehouse both read the same governed tables (for example
    `shop.silver.orders` and `shop.gold` aggregates), so there is one definition of an order and one refresh.

    **Why:** "single source of truth" and fewer copy pipelines are the business reasons the lakehouse page gives.
    The medallion layers (chapter 7) then make clear which table each team should read.

**Q5. An interviewer asks about "DLT" and "Databricks Workflows". What are they called today?**

??? success "Answer"
    Delta Live Tables (DLT) is now **Lakeflow pipelines** ("Spark Declarative Pipelines on Lakeflow"), built on
    open-source Apache Spark Declarative Pipelines ([What happened to
    DLT?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)). Databricks Jobs, which the menu called
    Workflows, is now **Lakeflow Jobs** ([June 2025 release
    notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june)). Old DLT code still works.

    **Why:** answer with both names ("Lakeflow pipelines, formerly Delta Live Tables") so the interviewer knows you
    recognise the old name and know the current one.

**Q6. What are Declarative Automation Bundles, and what were they called before?**

??? success "Answer"
    Declarative Automation Bundles, formerly Databricks Asset Bundles (DABs), are an infrastructure-as-code way to
    manage Databricks projects: source files plus YAML definitions of resources such as Lakeflow Jobs and Lakeflow
    pipelines, deployed together to a target environment for CI/CD.

    **Why:** interviewers ask "how do you promote a pipeline from dev to prod?"; bundles (chapter 16) are the
    Databricks answer.

**Q7. What is OpenSharing, what was it called, and can Red Rock share a table with a supplier that does not use Databricks?**

??? success "Answer"
    OpenSharing, formerly Delta Sharing, is the secure way to share data and AI assets with people outside your
    organization. Yes: the Databricks-to-Open sharing protocol shares tabular data from a Unity Catalog workspace
    "with users on any computing platform". Existing Delta Sharing setups keep working.

    **Why:** sharing without copying is a standard design question. The rename is from the Databricks blog
    [From Delta Sharing to OpenSharing](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next).

**Q8. Where is the Databricks web application: in the control plane or the compute plane? In whose account?**

??? success "Answer"
    In the control plane, which "is located in the Databricks account, not your cloud account".

    **Why:** the control plane is the management side (UI, backend services); the compute plane is where data is
    processed.

**Q9. For classic compute and for serverless compute, where do the machines that process your data run?**

??? success "Answer"
    Classic compute: in your own cloud account, in the workspace's virtual network (the classic compute plane).
    Serverless compute: in the serverless compute plane in the Databricks account, in the same region as the
    workspace.

    **Why:** this difference drives networking, security reviews and start-up time. Serverless starts faster
    because you are not creating machines in your account.

**Q10. A security reviewer asks: "If we use Databricks, does our customer data leave our cloud account?" How do you answer accurately?**

??? success "Answer"
    It depends on the setup. With classic compute and catalogs in our own storage, the data and the machines that
    process it stay in our cloud account, and the control plane is in Databricks' account (some features, such as
    Clean Rooms and data classification, still keep derived data in Databricks-managed default storage). With serverless compute,
    processing happens in Databricks' serverless compute plane, within a network boundary for the workspace. And
    in a serverless workspace, catalogs created on default storage are stored in Databricks-managed storage, while
    catalogs can also be put in our own cloud storage.

    **Why:** a flat "no, never" is wrong once serverless is in use; a precise answer names the compute type and
    the storage choice.

**Q11. Which clouds can host Databricks workspaces?**

??? success "Answer"
    Amazon Web Services, Microsoft Azure and Google Cloud Platform. On Azure the product is called Azure Databricks.

    **Why:** the concepts are the same on all three; storage names differ (S3, ADLS Gen2, Google Cloud Storage).

**Q12. What is a DBU, and is a classic cluster's cost only DBUs?**

??? success "Answer"
    A Databricks unit is a unit of "processing capability per hour based on VM instance type"; Databricks bills in
    DBUs. For classic compute the total also includes the cloud provider's "virtual machine, disk, and associated
    network costs". For serverless, "the DBU cost already includes the virtual machine costs".

    **Why:** forgetting the cloud bill makes classic compute look cheaper than it is when comparing it with
    serverless.

**Q13. A nightly ETL notebook runs on the team's always-on all-purpose cluster. What would you change, and why?**

??? success "Answer"
    Run it as a Lakeflow Jobs task (formerly Databricks Jobs, under the Workflows menu) on job compute or serverless compute instead. The cost
    guidance says non-interactive workloads "cost significantly less" on job compute than on all-purpose compute,
    and a job cluster exists only for the run.

    **Why:** all-purpose compute is for interactive work; using it for scheduled jobs costs more and lets
    interactive users and the job get in each other's way.

**Q14. In the run in section 1.6, how many JSON files are in `_delta_log` after `CREATE TABLE` and two `INSERT` statements, and why?**

??? success "Answer"
    Three: `00000000000000000000.json` (version 0, `CREATE TABLE`), `...01.json` (first `INSERT`) and `...02.json`
    (second `INSERT`). Each successful write is one commit, and each commit is one numbered JSON file.

    **Why:** the version number in `DESCRIBE HISTORY` is the commit file's number; that is how time travel finds an
    old version (chapter 4).

**Q15. The first `INSERT` in section 1.6 added two rows, and commit 1 shows two `add` actions with `numRecords=1` each. Why two files for two rows?**

??? success "Answer"
    The local engine ran the insert as two parallel tasks, and each task wrote its own Parquet file. The number of
    data files follows how the write was split into tasks, not the number of rows.

    **Why:** this is the root of the "small files" problem: many small writes or many tasks writing little data
    produce many small files, which `OPTIMIZE` later compacts (chapters 4 and 22).

**Q16. Find the mistake: "Delta Lake is a proprietary Databricks format, so other engines cannot read our tables."**

??? success "Answer"
    Delta Lake is open-source software, the data files are Parquet, and "the Delta Lake transaction log has a
    well-defined open protocol that can be used by any system to read the log". Other engines with Delta support can
    read the tables.

    **Why:** Databricks originally developed Delta Lake, but it is open source; the run in 1.6 used open-source
    Delta Lake with no Databricks software.

**Q17. Is Unity Catalog open source?**

??? success "Answer"
    Yes, there is an open-source implementation: "Unity Catalog is also available as an open-source
    implementation". On Databricks you use the Unity Catalog built into the platform, which this book covers.

    **Why:** a common outdated answer is "Unity Catalog is proprietary". Do not claim beyond what the page says
    about how the two versions compare.

**Q18. What do Lakeflow pipelines (formerly Delta Live Tables) add on top of open-source Apache Spark Declarative Pipelines?**

??? success "Answer"
    Per the Databricks page: `AUTO CDC` (SCD Type 1 and Type 2, and AUTO CDC from snapshot), data quality
    expectations, a queryable event log, update flows and `foreachBatch` sinks, and continuous mode. Streaming
    tables, materialized views, temporary views, append flows, sinks and automatic dependency resolution are in both.

    **Why:** interviewers like "what is open and what is not". `AUTO CDC` (formerly `APPLY CHANGES`) is the most
    common example of a Databricks-only pipeline feature (chapter 14).

**Q19. Is Photon part of Apache Spark?**

??? success "Answer"
    No. Photon is "the Databricks-native vectorized query engine". It is compatible with Spark APIs, so existing
    code runs on it without changes, but it is a Databricks feature, not part of open-source Spark. It is the
    default engine for all SQL warehouses.

    **Why:** knowing this separates platform features from Spark knowledge; chapter 6 covers when Photon helps.

**Q20. Write the PySpark DataFrame version of this query on the local `orders` table from section 1.6:**
`SELECT customer_id, SUM(amount) AS total FROM orders GROUP BY customer_id ORDER BY customer_id`

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

    ```python
    from pyspark.sql import functions as F

    (spark.table("orders")
          .groupBy("customer_id")
          .agg(F.sum("amount").alias("total"))
          .orderBy("customer_id")
          .show())
    ```

    ```text
    +-----------+------+
    |customer_id| total|
    +-----------+------+
    |          3|120.00|
    |          7| 78.40|
    +-----------+------+
    ```

    The SQL version returned the same two rows. Customer 7 has two orders, 59.90 + 18.50 = 78.40.

    **Why:** interviews ask for DataFrame code as often as SQL. `groupBy` plus `agg` with an alias is the DataFrame
    form of `GROUP BY` with `SUM(...) AS`; chapter 3 shows more side by side.

**Q21. On Databricks, write a query that counts Red Rock's silver orders by status. Use the full table name.**

??? success "Answer"
    *Databricks only, not run here. Three-level name from [High-level architecture](https://docs.databricks.com/aws/en/getting-started/high-level-architecture).*

    ```sql
    SELECT status, count(*) AS orders
    FROM shop.silver.orders
    GROUP BY status;
    ```

    **Why:** Unity Catalog names objects as `catalog.schema.object`. In this book the catalog is `shop` and the
    schemas are the medallion layers, so silver orders are `shop.silver.orders`. Locally, with no Unity Catalog,
    the run-here examples use plain names such as `orders`.

**Q22. Explain account, workspace and metastore in one sentence each.**

??? success "Answer"
    The account is the top level where identities, workspaces, metastores and billing are managed. A workspace is
    the environment where people run notebooks, jobs, pipelines and ML training. A Unity Catalog metastore is the
    central governance system for data assets; it is attached to workspaces, and one metastore can serve several
    workspaces in the same region so they see the same data.

    **Why:** this explains how dev and prod workspaces can share one catalog (chapter 5).

**Q23. Which tool fits each need? (a) run a notebook then a pipeline every night at 2 AM; (b) ingest Salesforce data; (c) let analysts run ad hoc SQL; (d) let business users ask questions about sales in plain English.**

??? success "Answer"
    (a) Lakeflow Jobs (formerly Databricks Jobs / Workflows). (b) Lakeflow Connect, which has managed SaaS
    connectors such as Salesforce. (c) A SQL warehouse (serverless where available) with the SQL editor or a BI
    tool. (d) A Genie Agent (formerly a Genie Space) curated on gold tables.

    **Why:** matching the tool to the job is how platform knowledge shows in a design question.

**Q24. Does serverless compute for notebooks, jobs and pipelines have to be switched on before you can use it?**

??? success "Answer"
    Usually not. The docs say serverless compute "is available by default in most workspaces and does not require
    enablement", and "workspaces that have Unity Catalog enabled automatically have access to serverless compute".

    **Why:** the word "most" matters: the page does not promise every workspace, so check the workspace rather than
    assume.

**Q25. True or false: "With a lakehouse we no longer need data warehousing."**

??? success "Answer"
    False as stated. A lakehouse removes the need for a *separate* warehouse copy, but warehousing is still done:
    Databricks SQL is described as "a cloud data warehouse built on lakehouse architecture", running on SQL
    warehouses over the same tables.

    **Why:** interviewers test whether "lakehouse" is understood as an architecture, not as "no SQL analytics".

**Q26. A tutorial reads data from `dbfs:/mnt/raw/orders`. Should a new Red Rock pipeline do the same?**

??? success "Answer"
    No. "Storing and accessing data using DBFS root or DBFS mounts is a deprecated pattern and not recommended by
    Databricks." Use Unity Catalog: volumes for raw files and tables for tabular data, with access controlled by
    grants.

    **Why:** mounts bypass Unity Catalog's permissions and lineage; older code you meet on the job may still use
    them, and migrating away is part of many projects.

**Q27. You want to practise on the real product without a company account. What can you use, and what did it replace?**

??? success "Answer"
    Databricks Free Edition: a no-cost, serverless-only, quota-limited workspace. It replaced the legacy Community
    Edition, which was retired in 2025.

    **Why:** a few hours in a real workspace makes the workspace tour (chapter 2) and Unity Catalog names concrete.

**Q28. "Why would you choose Databricks over a cloud data warehouse?" Give a balanced answer.**

??? success "Answer"
    For: one copy of data in open formats (Delta Lake) in our own cloud storage, used by SQL, Python pipelines,
    streaming and ML alike; compute that scales separately from storage, including serverless; one governance layer
    (Unity Catalog) for tables, files and models; and the open-source base (Spark, Delta) limits lock-in. Against or
    neutral: for a small team doing only SQL reporting on structured data, a warehouse may be simpler, and
    Databricks SQL itself is a warehouse product, so the choice is less about "warehouse or not" than about how many
    kinds of work share the data.

    **Why:** a one-sided sales pitch sounds rehearsed. Naming when the advantage is small shows judgment.

## Sources

- [What is Databricks?](https://docs.databricks.com/aws/en/introduction/) (last updated Oct 29, 2026)
- [The Databricks Data + AI Platform](https://www.databricks.com/product/platform) (databricks.com product page; the page shows no date)
- [What is a data intelligence platform](https://www.databricks.com/blog/what-is-a-data-intelligence-platform) (Databricks blog, Nov 15, 2023)
- [What is a data lakehouse?](https://docs.databricks.com/aws/en/lakehouse/) (last updated Oct 29, 2026)
- [High-level architecture](https://docs.databricks.com/aws/en/getting-started/high-level-architecture) (last updated Oct 29, 2026)
- [Databricks components](https://docs.databricks.com/aws/en/getting-started/concepts) (last updated Oct 29, 2026)
- [The scope of the Databricks platform](https://docs.databricks.com/aws/en/lakehouse-architecture/scope) (last updated Nov 5, 2026)
- [Data engineering with Databricks](https://docs.databricks.com/aws/en/data-engineering/) (last updated Nov 5, 2026)
- [What is Lakeflow Connect?](https://docs.databricks.com/aws/en/ingestion/overview) (last updated Nov 5, 2026)
- [Spark Declarative Pipelines on Lakeflow](https://docs.databricks.com/aws/en/ldp/) (last updated Oct 22, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [Apache Spark Declarative Pipelines](https://docs.databricks.com/aws/en/ldp/concepts/spark-declarative-pipelines) (last updated Oct 9, 2026)
- [Lakeflow pipelines release notes and the release upgrade process](https://docs.databricks.com/aws/en/release-notes/dlt/) (last updated Oct 16, 2026)
- [Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/) (last updated Nov 5, 2026)
- [Troubleshoot and repair job failures](https://docs.databricks.com/aws/en/jobs/repair-job-failures) (last updated Nov 5, 2026)
- [June 2025 (release notes)](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026)
- [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (last updated Nov 5, 2026)
- [What is OpenSharing?](https://docs.databricks.com/aws/en/opensharing/) (last updated Oct 27, 2026)
- [From Delta Sharing to OpenSharing: what changed, what's next](https://www.databricks.com/blog/delta-sharing-opensharing-what-changed-whats-next) (Databricks blog, Nov 5, 2026)
- [Data warehousing on Databricks](https://docs.databricks.com/aws/en/sql/) (last updated Oct 15, 2026)
- [Connect to a SQL warehouse](https://docs.databricks.com/aws/en/compute/sql-warehouse/) (last updated Oct 9, 2026)
- [Compute](https://docs.databricks.com/aws/en/compute/) (last updated Nov 5, 2026)
- [Connect to serverless compute](https://docs.databricks.com/aws/en/compute/serverless/) (last updated Oct 22, 2026)
- [What is Photon?](https://docs.databricks.com/aws/en/compute/photon) (last updated Sep 11, 2026)
- [Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/) (last updated Oct 12, 2026)
- [Apache Spark overview](https://docs.databricks.com/aws/en/spark/) (last updated Sep 11, 2026)
- [What is Delta Lake in Databricks?](https://docs.databricks.com/aws/en/delta/) (last updated Sep 11, 2026)
- [What is Unity Catalog?](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) (last updated Sep 11, 2026)
- [Default storage in Databricks](https://docs.databricks.com/aws/en/storage/default-storage) (last updated Nov 10, 2026)
- [Databricks clouds and regions](https://docs.databricks.com/aws/en/resources/supported-regions) (last updated Oct 21, 2026)
- [What is Azure Databricks?](https://learn.microsoft.com/en-us/azure/databricks/introduction/) (last updated Oct 29, 2026)
- [Best practices for cost optimization](https://docs.databricks.com/aws/en/lakehouse-architecture/cost-optimization/best-practices) (last updated Oct 29, 2026)
- [Billable usage system table reference](https://docs.databricks.com/aws/en/admin/system-tables/billing) (last updated Nov 6, 2026)
- [Databricks AI/BI](https://docs.databricks.com/aws/en/ai-bi/) (last updated Oct 30, 2026)
- [Genie Agents](https://docs.databricks.com/aws/en/genie-agents/) (last updated Nov 2, 2026)
- [Machine learning on Databricks](https://docs.databricks.com/aws/en/machine-learning/) (last updated Nov 5, 2026)
- [MLflow on Databricks](https://docs.databricks.com/aws/en/mlflow/) (last updated Oct 6, 2026)
- [Sign up for Databricks Free Edition](https://docs.databricks.com/aws/en/getting-started/free-edition) (last updated Sep 11, 2026)
- [Spark Declarative Pipelines Programming Guide](https://spark.apache.org/docs/4.2.0/declarative-pipelines-programming-guide.html) (Apache Spark 4.2.0 docs; the page shows no last-updated date)
