# 6. Compute

*Every query, notebook cell, job and pipeline on Databricks runs on some compute, and compute is most of the bill. This chapter explains the kinds of compute (serverless, classic all-purpose and job compute, SQL warehouses), what Photon and the access modes change, how to read Databricks Runtime version lines, how a classic cluster is sized, and where the money goes. Interviewers ask about compute because the answers show whether you have run production work: "why not run that job on the all-purpose cluster?", "when would you not use serverless?", "how would you cut our Databricks bill?" Almost nothing here runs on open-source Spark, so most examples are Databricks-only syntax copied from the official pages; the few things the local engine can show honestly are run and their output is real.*

!!! abstract "In this chapter"
    **You will learn:**

    - what "compute" means on Databricks and its three families: serverless compute, classic compute, SQL warehouses
    - serverless vs classic: who runs the machines, what you pay for, and the limitations that send you back to classic
    - all-purpose vs job compute, and why scheduled jobs belong on job compute or serverless
    - SQL warehouse types (serverless, pro, classic), their defaults and what each is for
    - Photon: what it speeds up, what it does not, and how it is switched on
    - access modes: standard and dedicated (formerly shared and single user), and what each allows
    - Databricks Runtime versions, LTS, the ML runtime, and how to read "Databricks Runtime 15.4 LTS and above"
    - sizing classic compute: node types, driver vs workers, autoscaling, auto-termination, spot instances, pools, compute policies
    - what drives cost (DBUs, `system.billing.usage`, tags) and how to bring it down
    - which compute Red Rock Supply should use for bronze ingestion, silver/gold jobs, BI dashboards and ad hoc work

    **You need:** [chapter 3](03-Apache-Spark.md) (driver, executors, partitions). [Chapter 5](05-Unity-Catalog.md) helps for the access-mode section.

    **Levels:** sections 6.1 to 6.3 beginner, 6.4 to 6.8 and 6.11 intermediate, 6.9 and 6.10 expert.

**About the examples.** Compute is a Databricks service, so most code blocks here (cluster JSON, compute policy JSON, a job in Declarative Automation Bundles YAML, SQL against `system.billing.usage`) are labeled "Databricks only, not run here" and copy their shape from the page named in the label. The local engine (Apache Spark 4.2.0 with Delta Lake 4.4.1, `local[2]`) can show a few things honestly: where the driver and executors run, which settings can and cannot change in a running session, that `current_version()` does not exist in open-source Spark, and that an open-source plan has no Photon operators. That script and its full output are in `src/ch06/`. Dollar prices are not quoted anywhere: no page used here states them, and they change. Use the Databricks pricing pages and your own `system.billing.list_prices` table.

## 6.1 What compute is
*Level: beginner.*

**The problem.** Code needs machines. A Spark query needs a driver to plan it and executors to run its tasks ([chapter 3](03-Apache-Spark.md#32-cluster-architecture-driver-executors-cores-and-tasks)); a dashboard needs something to answer its SQL within seconds; a nightly pipeline needs machines for an hour and then none. Somebody has to choose, start, size, patch and stop those machines, and pay for them.

**The tool.** The Compute page defines it: "Databricks compute refers to the selection of computing resources available on Databricks to run your data engineering, data science, and analytics workloads." It groups compute into three families:

| Family | Who manages the machines | Used by |
| --- | --- | --- |
| **Serverless compute** | Databricks, in the serverless compute plane | notebooks, Lakeflow Jobs, Lakeflow pipelines |
| **Classic compute** | you configure it; it runs in your cloud account | all-purpose compute, job compute, classic pipeline compute |
| **SQL warehouses** | serverless, or classic/pro in your cloud account | the SQL editor, dashboards, BI tools, SQL tasks in jobs |

A few terms used through the chapter:

- **Compute resource** (still often called a **cluster**): one driver node plus zero or more worker nodes. The configuration reference says "A compute resource consists of one driver node and zero or more worker nodes" and "Databricks runs one executor per worker node. Therefore, the terms executor and worker are used interchangeably in the context of the Databricks architecture."
- **Databricks Runtime (DBR):** "the set of core components that run on your compute"; every version includes Apache Spark (section 6.7).
- **DBU (Databricks unit):** the billing unit. The concepts page: "Databricks bills based on Databricks units (DBUs), which are units of processing capability per hour based on VM instance type." Section 6.10 covers cost.

!!! tip "In the interview"
    **"What kinds of compute does Databricks have?"** Three families. Serverless compute for notebooks, jobs and pipelines, which Databricks provisions and scales. Classic compute that you configure in your own cloud account: all-purpose compute for interactive work and job compute that exists only for a job run. And SQL warehouses for SQL and BI, in serverless, pro or classic form. Then say which you would default to: serverless where the workload supports it, classic when it does not.

## 6.2 Serverless vs classic compute
*Level: beginner.*

**The problem.** Classic clusters take minutes to start, sit idle between commands while still billing, and need someone to pick instance types, runtime versions and sizes. Most teams get some of that wrong.

**Serverless.** "Serverless compute is a Databricks-managed service that allows users to quickly connect to on-demand computing resources for notebooks, workflows, and Lakeflow pipelines." Databricks "automatically allocates and manages the necessary compute resources. This speeds up start-up and scaling times, minimizes idle time, and reduces the need to manage compute resources." It is "a _versionless_ product": Databricks upgrades the serverless runtime itself, and "Serverless workloads always run on the latest runtime version." It "is available by default in most workspaces", but "Legacy workspaces that are not enabled for Unity Catalog do not have access to serverless compute."

**Classic.** "Classic compute refers to all-purpose, jobs, and Lakeflow pipelines compute resources that you create, configure, and manage for your workloads. Classic compute resources are deployed in your cloud provider account." You choose the runtime, node types, number of workers, spot instances, pools and policy (section 6.8).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 290" role="img" aria-label="Classic compute: a driver and workers in your cloud account, you choose the settings, bill is DBUs plus cloud VMs. Serverless: your notebook, job or pipeline runs on machines Databricks manages, bill is DBUs with VM cost included.">
<defs><marker id="a61" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="10" y="32" width="300" height="225" rx="10" stroke-dasharray="6 4"/>
<rect x="330" y="32" width="300" height="225" rx="10" stroke-dasharray="6 4"/>
<rect x="25" y="50" width="120" height="50" rx="6"/>
<rect x="170" y="50" width="125" height="44" rx="6"/>
<rect x="170" y="108" width="125" height="44" rx="6"/>
<rect x="170" y="166" width="125" height="44" rx="6"/>
<line x1="145" y1="70" x2="168" y2="70" marker-end="url(#a61)"/>
<line x1="145" y1="85" x2="168" y2="125" marker-end="url(#a61)"/>
<line x1="135" y1="100" x2="168" y2="182" marker-end="url(#a61)"/>
<rect x="345" y="50" width="270" height="44" rx="6"/>
<rect x="345" y="120" width="270" height="90" rx="6"/>
<line x1="480" y1="94" x2="480" y2="118" marker-end="url(#a61)"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="160" y="22" font-size="14" font-weight="bold">Classic: in your cloud account</text>
<text x="480" y="22" font-size="14" font-weight="bold">Serverless: managed by Databricks</text>
<text x="85" y="72" font-weight="bold">Driver</text>
<text x="85" y="90">on-demand</text>
<text x="232" y="69" font-weight="bold">Worker 1</text>
<text x="232" y="86">1 executor</text>
<text x="232" y="127" font-weight="bold">Worker 2</text>
<text x="232" y="144">1 executor</text>
<text x="232" y="185" font-weight="bold">Worker n</text>
<text x="232" y="202">spot, if allowed</text>
<text x="85" y="128">You choose:</text>
<text x="85" y="146">runtime, nodes,</text>
<text x="85" y="164">workers, spot,</text>
<text x="85" y="182">pools, policy,</text>
<text x="85" y="200">auto-termination</text>
<text x="160" y="240">Bill: DBUs + VMs, disks, network</text>
<text x="480" y="69" font-weight="bold">Your notebook, job or pipeline</text>
<text x="480" y="86">no cluster to configure</text>
<text x="480" y="145">Machines chosen, started,</text>
<text x="480" y="165">scaled and upgraded by</text>
<text x="480" y="185">Databricks; Photon on</text>
<text x="480" y="240">Bill: DBUs (VM cost included)</text>
</g>
</svg>
<figcaption>Figure 6.1. Classic compute runs in your cloud account with settings you choose; serverless compute runs on machines Databricks manages, and its DBU price already includes the virtual machine cost.</figcaption>
</figure>

| | Serverless (notebooks, jobs, pipelines) | Classic (all-purpose, job, pipeline compute) |
| --- | --- | --- |
| Where the machines run | serverless compute plane, managed by Databricks | your cloud account |
| Start-up | fast; serverless jobs in standard performance mode accept "slightly higher startup latency of 4 to 6 minutes" | minutes to start a cluster (no number on the pages used here) |
| What you pay | DBUs; "for serverless services, the DBU cost already includes the virtual machine costs" | DBUs plus "virtual machine, disk, and associated network costs" |
| Runtime version | versionless, always the latest | you pick a Databricks Runtime version |
| Access mode | serverless jobs use standard access mode | standard or dedicated |
| Tuning knobs | almost none: no compute policies, pools, init scripts, compute-scoped libraries, most Spark confs | all of them |
| Requires | Unity Catalog | nothing extra |

**Serverless jobs have a performance mode.** With **Performance optimized** off, "the job uses standard performance mode. This mode uses less compute to reduce costs, making it suitable for workloads that can tolerate slightly higher startup latency of 4 to 6 minutes". With it on, "the job starts and runs faster". "Both modes use the same SKU, but standard performance mode consumes fewer DBUs." A nightly batch is a good fit for standard mode; a job with a tight deadline for performance optimized.

**What serverless does not do.** These limitations from "Serverless compute limitations" (Nov 5, 2026) are the usual answers to "when would you not use serverless?":

- "R is not supported." "Only Spark Connect APIs are supported. Spark RDD APIs are not supported."
- Streaming in serverless notebooks and jobs supports only `Trigger.AvailableNow()` (recommended) and the deprecated `Trigger.Once()`. `ProcessingTime` and `Continuous` triggers fail with `INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED`, and the default trigger is a `ProcessingTime` trigger, so you must set one. For always-on streaming, use a serverless pipeline in continuous mode.
- "The Spark UI is not available"; use the query profile instead.
- Not supported: compute policies, compute-scoped init scripts and libraries, instance pools, compute event logs, "Most Apache Spark compute configurations", Maven coordinates, Databricks Container Services, global temp views.
- "Serverless compute has a maximum runtime of 7 days."
- Serverless notebooks have "a default execution timeout of 2.5 hours (9,000 seconds)" ("Serverless compute for notebooks").
- You must use Unity Catalog for external data.

!!! tip "In the interview"
    **"When would you not use serverless?"** When the workload hits a serverless limitation: R or RDD code, a Spark Submit task, a streaming job that needs a `ProcessingTime` trigger in a job rather than a pipeline, custom Spark configurations, init scripts or container images, a run longer than 7 days, or a workspace without Unity Catalog. Also when the team needs the Spark UI or full control of instance types. Otherwise Databricks recommends serverless for new work, and for cost I would measure both ways in `system.billing.usage` instead of assuming either is cheaper.

## 6.3 All-purpose compute vs job compute
*Level: beginner.*

Classic compute comes in two kinds that can have identical hardware but behave and bill differently.

- **All-purpose compute** is created by a person (Compute, Create compute) for interactive work. Several notebooks attach to it, it keeps running until someone stops it or auto-termination fires, and a terminated one can be restarted. If a job is scheduled on an existing all-purpose cluster that has been terminated, "that compute will autostart."
- **Job compute** is created by the job scheduler for a job run. "When you run a job on a new Job compute (which is usually recommended), the compute terminates and is unavailable for restarting when the job is complete" ("Manage classic compute"). Tasks in one job can share a job compute resource, so the start-up time is paid once per run; tasks that share it "run on the same driver JVM", so singletons and loaded libraries persist between them ("Configure compute for jobs", Nov 9, 2026).

Why scheduled jobs belong on job compute (or serverless jobs):

1. **Price.** "on job compute, the non-interactive workloads will cost significantly less than on all-purpose compute" ("Best practices for cost optimization", Oct 29, 2026). The page sends you to the pricing overview for the rates; the exact ratio is not on a docs page and changes.
2. **Isolation.** "each job can run on a new compute instance, isolating workloads from each other." A colleague's heavy notebook on the shared cluster cannot slow your 2 a.m. load.
3. **No idle time.** Job compute ends with the run; all-purpose compute bills until it is stopped.
4. **Cost attribution.** In `system.billing.usage`, `usage_metadata.job_id` is populated for "Serverless jobs and jobs run on job compute (does not populate for jobs run on all-purpose compute)". Jobs on all-purpose compute disappear into the cluster's bill.
5. **Reproducibility.** The job definition carries its own compute spec (runtime, size), so it runs the same way every night.

!!! tip "In the interview"
    **"Job compute or all-purpose compute for a scheduled job?"** Job compute, or serverless compute for Lakeflow Jobs (formerly Databricks Jobs, the "Workflows" menu; [rename note](https://docs.databricks.com/aws/en/release-notes/product/2025/june)). The Databricks cost guide says non-interactive workloads cost significantly less on job compute; each run gets its own compute that terminates when the run ends, so there is no idle time and no interference from interactive users; and the billing table can attribute the cost to the job, which it cannot for jobs on all-purpose compute. All-purpose compute is for development and exploration, with auto-termination on.

!!! warning "Common mistake"
    Pointing a production job at the team's all-purpose cluster "because it is already running". It pays the all-purpose rate, competes with interactive users, can fail when someone restarts the cluster, and its cost cannot be traced to the job.

## 6.4 SQL warehouses
*Level: intermediate.*

A **SQL warehouse** "is a compute resource that lets you query and explore data on Databricks." It runs only SQL, Photon is always on, and it is what the SQL editor, AI/BI dashboards, alerts and external BI tools (through JDBC/ODBC) connect to. You can also attach a notebook to a pro or serverless warehouse. Databricks creates a small "Starter Warehouse" in a new workspace. SQL tasks and dbt tasks in jobs run on a serverless (recommended) or pro warehouse ("Configure compute for jobs").

There are three types ("SQL warehouse types", Oct 30, 2026):

| Type | Photon | Predictive IO | Intelligent Workload Management | Where the compute runs | Start-up (page's wording) | Use it when |
| --- | --- | --- | --- | --- | --- | --- |
| **Serverless** | yes | yes | yes | Databricks account | "typically between 2 and 6 seconds" | default choice: BI, ETL, exploration |
| **Pro** | yes | yes | no | your AWS account | "typically approximately 4 minutes" | serverless not available in the region, or custom networking (for example federation to databases in your private network or on premises) |
| **Classic** | yes | no | no | your AWS account | "typically approximately 4 minutes" | "entry-level performance" interactive queries |

**Intelligent Workload Management (IWM)** predicts each query's resource needs, queues queries when capacity is short, and "If wait times increase, the autoscaler quickly provisions more clusters". The same page lists a Beta type, Lakehouse Real-Time, for sub-second, high-concurrency `SELECT` queries.

**Settings and defaults** ("Create a SQL warehouse", Sep 11, 2026; "SQL warehouse types"):

| Setting | Default and limits from the page |
| --- | --- |
| Type in the UI | serverless, where the region supports it (pro if it does not) |
| Type through the SQL warehouses API with default parameters | **classic**; set `enable_serverless_compute` to `true` and `warehouse_type` to `pro` for serverless |
| Cluster size | "The default is **X-Large**"; size sets the driver and number of workers of each warehouse cluster |
| Auto stop, pro and classic | 45 minutes default, 10 minutes minimum |
| Auto stop, serverless | 10 minutes default; 5 minutes minimum in the UI, as low as 1 minute through the API |
| Scaling | min and max clusters both 1 by default; "Databricks recommends a cluster for every 10 concurrent queries" |
| Queue | "The maximum number of queries in a queue for all warehouse types is 1,000" ("SQL warehouse sizing, scaling, and queuing behavior") |

Size and scaling answer different problems. A bigger **cluster size** makes each query faster and reduces spill ("If queries are spilling to disk, increase the cluster size"); more **clusters** handle more concurrent queries. A warehouse also restarts on its own when a query, a scheduled job, a JDBC/ODBC connection or a dashboard needs it.

!!! warning "Trap: the API default is not the UI default"
    A warehouse created in the UI is serverless where available, but one created through the SQL warehouses API with default parameters is classic. Infrastructure code should always set `enable_serverless_compute` and `warehouse_type` explicitly, as the page recommends.

!!! tip "In the interview"
    **"Serverless, pro or classic warehouse for our dashboards?"** Serverless: it starts in seconds, so it can auto-stop when nobody is looking (default 10 minutes) and still answer the first click quickly, and IWM adds clusters when many people open dashboards at once. Pro only when serverless is not available in the region or the warehouse must reach databases in our private network. The cost guide notes that slow-starting warehouses tempt teams to leave them running, which is where idle cost comes from.

## 6.5 Photon
*Level: intermediate.*

"Photon is the Databricks-native vectorized query engine that accelerates your SQL workloads, DataFrame API calls, ETL pipelines, and stateless streaming workloads" ("What is Photon?", Sep 11, 2026). Catalyst still plans the query; "Photon takes over at the execution layer, processing data in columnar batches rather than row by row", in native C++ instead of the JVM. For an operation it does not support, "it transparently falls back to the Spark runtime for the remainder of that operation." Results are the same either way.

**What it speeds up:** scans (Parquet, Delta, CSV, JSON) with filter pushdown and row-group skipping, hash joins and aggregations, a columnar shuffle, window functions, sorts, and writes through its native Parquet writer, including `MERGE`, `UPDATE`, `DELETE`, `INSERT` and CTAS; stateless streaming into Delta or Parquet. Predictive I/O and dynamic file pruning in `MERGE`, `UPDATE` and `DELETE` require Photon.

**What it does not speed up** (the page's Limitations section):

- "Photon doesn't support UDFs (User Defined Functions), RDD APIs, or Dataset APIs."
- "Stateful streaming is not supported."
- "Photon doesn't improve queries that normally run in under two seconds", because planning and scheduling dominate.
- The ML runtime page adds that Python libraries such as XGBoost, PyTorch and TensorFlow "will not see an improvement with Photon".

**Where it is on.** "Photon is enabled on serverless compute, SQL warehouses, and serverless Lakeflow pipelines." For classic all-purpose compute, job compute and classic pipelines, Databricks enables it by default in the UI (the **Use Photon Acceleration** checkbox). Through the APIs it is different: "If you create these resources using the Clusters API or Jobs API, you must explicitly enable Photon by setting `runtime_engine` to `PHOTON`. If you use the Pipelines API, set `photon` to `true`." The Clusters API reference confirms that if `runtime_engine` is left unspecified it "defaults to standard".

**Cost.** "Photon instance types consume DBUs at a different rate than the same instance type running the non-Photon runtime." Faster is not automatically cheaper; the cost guide says jobs that run regularly "should be evaluated to see whether they are not only faster but also cheaper with Photon."

**Photon is not in open-source Spark.** The local engine has no Photon and no switch for it: on Databricks, the documented switch is the compute spec (`runtime_engine` in the Clusters and Jobs APIs, the checkbox in the UI), not a session setting. The physical plan of a Red Rock Supply daily-revenue aggregation, run locally, shows only Spark's JVM operators:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
daily = orders.groupBy(F.to_date("order_ts").alias("order_date")).agg(F.sum("amount").alias("revenue"))
plan = daily._jdf.queryExecution().executedPlan().toString()
print(plan)
print("'Photon' appears in the plan:", "photon" in plan.lower())
```
```text
AdaptiveSparkPlan isFinalPlan=false
+- HashAggregate(keys=[_groupingexpression#22], functions=[sum(amount#12)], output=[order_date#13, revenue#14])
   +- Exchange hashpartitioning(_groupingexpression#22, 8), ENSURE_REQUIREMENTS, [plan_id=23]
      +- HashAggregate(keys=[_groupingexpression#22], functions=[partial_sum(amount#12)], output=[_groupingexpression#22, sum#25, isEmpty#26])
         +- Project [cast(amount#9 as decimal(10,2)) AS amount#12, cast(cast(order_ts#7 as timestamp) as date) AS _groupingexpression#22]
            +- Scan ExistingRDD[order_id#5,customer_id#6,order_ts#7,status#8,amount#9,currency#10]

'Photon' appears in the plan: False
```

On Databricks, the same query on Photon compute shows Photon operators in the plan: the Spark UI colors them orange (Spark operators blue), and the query profile on SQL warehouses and serverless shows "the percentage of task time spent in Photon". The exact Photon operator names are not listed on the Photon page, so they are not shown here.

!!! tip "In the interview"
    **"What is Photon and when does it not help?"** Databricks' native C++ vectorized engine; Catalyst plans, Photon executes in columnar batches and falls back to Spark for anything it does not support. It helps long SQL and DataFrame work on large data: scans, joins, aggregations, `MERGE` and writes. It does not help UDFs, RDD or Dataset code, stateful streaming, or queries under about two seconds, and Photon compute bills DBUs at a different rate, so I check cost per run, not only run time.

## 6.6 Access modes
*Level: intermediate.*

**The problem.** A compute resource is a set of shared machines. If two people run code on the same driver JVM, one could read the other's credentials or bypass a row filter. Databricks needs to know, for each compute resource, who may use it and how strongly users are isolated.

**The tool.** "Access mode is a security feature that determines who can use the compute resource and the data they can access using the compute resource. Every compute resource in Databricks has an access mode." The names changed; the Unity Catalog best practices page (Oct 30, 2026) gives both: "standard access mode (formerly shared access mode) or dedicated access mode (formerly single-user or assigned access mode)".

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 290" role="img" aria-label="Standard access mode: several users each in a sandbox connect through Spark Connect and Lakeguard to a shared driver and executors. Dedicated access mode: one user or one group runs code in the driver JVM, and fine-grained filtering is delegated to serverless compute.">
<defs><marker id="a63" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="20" y="40" width="85" height="36" rx="6"/>
<rect x="117" y="40" width="85" height="36" rx="6"/>
<rect x="214" y="40" width="85" height="36" rx="6"/>
<rect x="20" y="112" width="280" height="50" rx="6"/>
<rect x="20" y="196" width="280" height="50" rx="6"/>
<line x1="62" y1="76" x2="62" y2="110" marker-end="url(#a63)"/>
<line x1="160" y1="76" x2="160" y2="110" marker-end="url(#a63)"/>
<line x1="256" y1="76" x2="256" y2="110" marker-end="url(#a63)"/>
<line x1="160" y1="162" x2="160" y2="194" marker-end="url(#a63)"/>
<rect x="380" y="40" width="200" height="36" rx="6"/>
<rect x="340" y="112" width="280" height="50" rx="6"/>
<rect x="340" y="196" width="280" height="50" rx="6" stroke-dasharray="5 4"/>
<line x1="480" y1="76" x2="480" y2="110" marker-end="url(#a63)"/>
<line x1="480" y1="162" x2="480" y2="194" marker-end="url(#a63)"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="160" y="24" font-size="14" font-weight="bold">Standard (formerly shared)</text>
<text x="480" y="24" font-size="14" font-weight="bold">Dedicated (formerly single user)</text>
<text x="62" y="63">User A</text>
<text x="160" y="63">User B</text>
<text x="256" y="63">User C</text>
<text x="160" y="133">each user's code in a sandbox,</text>
<text x="160" y="151">Spark Connect + Lakeguard</text>
<text x="160" y="226">shared driver and executors</text>
<text x="160" y="272">Python, SQL, Scala; no R, no RDDs</text>
<text x="480" y="63">one user or one group</text>
<text x="480" y="133">classic Spark: user code</text>
<text x="480" y="151">shares the driver JVM</text>
<text x="480" y="217">row filters and column masks</text>
<text x="480" y="235">filtered by serverless</text>
<text x="480" y="272">R, RDD APIs, GPUs, ML runtime</text>
</g>
</svg>
<figcaption>Figure 6.2. Standard access mode isolates every user's code from the engine and from other users (Lakeguard), so many users share one resource safely. Dedicated access mode gives one user or group the classic Spark architecture; fine-grained access control there is delegated to serverless compute.</figcaption>
</figure>

| | Standard (formerly shared) | Dedicated (formerly single user / assigned) |
| --- | --- | --- |
| Who can attach | "any user with CAN ATTACH TO permission" | "the assigned single user or group" (group assignment is Public Preview) |
| Isolation | Lakeguard: "runs user code in full isolation with no access to lower-level resources" | classic Spark: "user code isn't isolated from the engine" |
| Languages | Python, SQL, Scala (Scala needs 13.3 LTS and above); R not supported | Python, SQL, Scala, R |
| Not supported | Databricks Runtime ML, GPUs, RDD APIs, Spark Submit tasks, Hive UDFs, socket sources | Unity Catalog Python UDFs (run them on serverless, standard compute, a serverless or pro warehouse, or a pipeline) |
| Row filters, column masks, dynamic views | enforced natively | read on 15.4 LTS and above, write on 16.3 and above, and the workspace must be enabled for serverless compute |
| API value (`data_security_mode`) | `DATA_SECURITY_MODE_STANDARD`; legacy alias `USER_ISOLATION` | `DATA_SECURITY_MODE_DEDICATED`; legacy alias `SINGLE_USER` |

How it works: in standard mode, "Lakeguard uses Spark Connect (introduced with Apache Spark 3.4) to decouple client applications from the driver", and each client "runs in its own isolated container environment"; UDFs are sandboxed on the executors too. On dedicated compute, fine-grained filtering is done for you by the workspace's serverless compute, "This is why fine-grained access control on dedicated compute requires your workspace to be enabled for serverless compute."

**The default.** In the UI, access mode is **Auto**: it "defaults to **Standard** unless a machine learning runtime, a GPU instance type, or a Databricks Runtime lower than 14.3 is selected, in which case **Dedicated** is used." "Databricks recommends that you use standard access mode unless your required functionality is not supported." In the API, `DATA_SECURITY_MODE_AUTO` lets Databricks choose; `NONE` means "no security features are enabled" (the compute-management page still mentions legacy compute with a "No isolation shared" access mode), and the `LEGACY_*` modes "are deprecated starting with Databricks Runtime 15.0". Credential passthrough "is a legacy access mode that is not compatible with Unity Catalog". Serverless compute for jobs "uses standard access mode", so code that runs on serverless must respect standard-mode limits.

!!! tip "In the interview"
    **"Standard or dedicated access mode?"** Standard (formerly shared) by default: many users share one resource, each user's code is isolated by Lakeguard, and Unity Catalog row filters and column masks are enforced directly. Dedicated (formerly single user) when the workload needs something standard mode does not allow: R, RDD APIs, GPUs, the ML runtime, or privileged machine access. On dedicated compute, row filters and masks need 15.4 LTS or above and serverless enabled in the workspace.

## 6.7 Databricks Runtime versions
*Level: intermediate.*

Classic compute runs a **Databricks Runtime** version you choose: Apache Spark plus Databricks' additions (Delta Lake, Photon, connectors, libraries). Serverless compute and SQL warehouses are versioned by Databricks.

**Supported versions** on "Databricks Runtime release notes versions and compatibility" (Nov 4, 2026):

| Version | Apache Spark | Released | End of support |
| --- | --- | --- | --- |
| 19 | 4.2.0 | July 23, 2026 | "Determined at LTS transition" |
| 18 LTS | 4.1.0 | June 10, 2026 | June 10, 2029 |
| 17.3 LTS | 4.0.0 | Oct 22, 2025 | Oct 22, 2028 |
| 16.4 LTS | 3.5.2 | May 9, 2025 | May 9, 2028 |
| 15.4 LTS | 3.5.0 | Aug 19, 2024 | Aug 19, 2027 |
| 14.3 LTS | 3.5.0 | Feb 1, 2024 | Feb 1, 2027 |

Each version has an ML variant ("Databricks Runtime 18 LTS for Machine Learning").

**LTS and the lifecycle** ("Databricks support lifecycles", Nov 6, 2026). A version starts as Beta, becomes GA, and spends "approximately six months" in a feature-development phase in which "Databricks releases new features and fixes under the same version number"; "Clusters receive updates when they restart." It then "transitions to long-term support (LTS)", receiving "Major stability and security fixes ... until the end-of-support date, three years after the GA release date." The model changed with version 19: "Prior to Databricks Runtime 19, Databricks released runtimes as minor feature versions (for example, 18.0, 18.1, 18.2), each with its own Beta and GA release", and for those older non-LTS releases "the end-of-support date is six months after the GA release date." After end of support a version gets no fixes and leaves the UI; at end of life it "becomes unusable", with Databricks making "a best effort" to set that six months after end of support.

**Which version to pick** (configuration reference and classic best practices):

- All-purpose compute: "use the most current version".
- Job compute for operational workloads: "consider using the Long Term Support (LTS) Databricks Runtime version", so you can test before upgrading. The best-practices page simply says "Use the latest long-term support (LTS) Databricks Runtime version."
- ML runtime: "Only select a machine learning runtime if your workload uses GPUs, distributed ML training, or AutoML", because it "installs a large set of libraries that can conflict with your own dependencies". Selecting it sets the access mode to dedicated. For GPU deep-learning work, the ML runtime page now recommends AI Runtime, a serverless GPU offering.

In a cluster spec the version is a key such as `19.x-scala2.13` (Clusters API samples) or `15.4.x-scala2.12` (bundle examples). Compute policies can use `auto:latest-lts`, `auto:latest`, `auto:latest-ml` and similar values, but "Using these values does not make the compute auto-update when a new runtime version is released."

**Reading a version line.** Feature pages and SQL reference pages carry lines such as "Applies to: Databricks SQL Databricks Runtime 15.4 LTS and above". The SQL reference's own guide, [How to use the SQL reference](https://docs.databricks.com/aws/en/sql/language-manual/how-to-use), defines the label: "Databricks SQL Databricks Runtime 11.3 LTS and above" means "All versions of Databricks SQL and Databricks Runtime 11.3 LTS and later", and a label that names only Databricks Runtime is "not supported in Databricks SQL". This book reads feature-page lines the same way:

| Line | Works on | Does not work on |
| --- | --- | --- |
| "Databricks Runtime 15.4 LTS and above" | 15.4 LTS and every later version: 16.4 LTS, 17.3 LTS, 18 LTS, 19 | 14.3 LTS and anything before 15.4 |
| "Databricks SQL Databricks Runtime 16.2 and above" | SQL warehouses, and clusters on 16.2 or later (16.4 LTS, 17.3 LTS, 18 LTS, 19) | a 15.4 LTS cluster |
| "Databricks Runtime 15.4 LTS ML and above" | the ML variants from 15.4 LTS ML | the non-ML runtime, unless stated |
| a line that names only "Databricks Runtime" | clusters | SQL warehouses (not listed) |

Serverless notebooks and jobs always run the latest version, but whether a given feature is supported there is stated separately (serverless limitations and release notes), so check those pages rather than inferring it from a runtime line (not verified as a general rule).

**Which version am I on?** On Databricks, `current_version()` "Returns the current version of Databricks SQL or Databricks Runtime" as a struct whose `dbr_version` is set on clusters and `dbsql_version` on SQL warehouses ("Applies to: Databricks SQL Databricks Runtime 11.3 LTS and above"):

*Databricks only, not run here. Syntax from [`current_version` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/current_version).*
```sql
SELECT current_version().dbr_version;    -- on a cluster
SELECT current_version().dbsql_version;  -- on a SQL warehouse
```

Open-source Spark has `version()` but not `current_version()`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
sql("SELECT version() AS spark_version").show(truncate=False)
sql("SELECT current_version()").show(truncate=False)
```
```text
+----------------------------------------------+
|spark_version                                 |
+----------------------------------------------+
|4.2.0 32f7299601108917fb01920a54e084595b7b3bf8|
+----------------------------------------------+

AnalysisException: [UNRESOLVED_ROUTINE] Cannot resolve routine `current_version` on search path [`system`.`builtin`, `system`.`session`, `spark_catalog`.`default`]. SQLSTATE: 42883; line 1 pos 7
```

!!! warning "Trap"
    "LTS" does not mean "never upgrade". 14.3 LTS reaches end of support on Feb 1, 2027. The lifecycle page includes SQL against `system.compute.clusters` and `system.billing.usage` to find clusters and jobs still on old runtimes; plan upgrades before the date.

## 6.8 Sizing classic compute
*Level: intermediate.*

When a workload must run on classic compute, these are the settings that matter ("Compute configuration reference", Nov 6, 2026, unless noted).

**Node types.** You pick a cloud instance type for the workers and, under Advanced performance, for the driver; "by default the driver node uses the same instance type as the worker node." The cost guide's rules of thumb: memory optimized for "ML, heavy shuffle and spill workloads"; compute optimized for "structured streaming workloads and maintenance jobs (such as optimize and vacuum)"; storage optimized for "workloads that benefit from caching, such as ad-hoc and interactive data analysis"; GPU only for GPU libraries; general purpose otherwise. On AWS, fleet instance types resolve to "the best available instance type of the same size"; for example, `m-fleet.xlarge` resolves to whichever `.xlarge` general purpose type has "the best spot capacity and price at that moment".

**Driver vs workers.** The driver "maintains state information of all notebooks attached to the compute resource", "maintains the SparkContext, interprets all the commands you run", and runs the Spark master. Workers run the executors, one per worker. Choose "a larger driver node type with more memory if you are planning to `collect()` a lot of data from Spark workers and analyze them in the notebook". Size the cluster by **total executor cores** (parallelism), **total executor memory** (how much fits before spilling) and **local storage** (spill and cache), not by worker count: "two workers, each with 16 cores and 128 GB of RAM, has the same compute and memory as ... 8 workers, each with 4 cores and 32 GB of RAM" ("Classic compute configuration best practices", Sep 11, 2026). For complex ETL with joins, that page recommends fewer, larger workers to reduce shuffle.

**Single node.** "To run a Spark job, you need at least one worker node. If the compute resource has zero workers, you can run non-Spark commands on the driver node, but Spark commands will fail." The exception is **single-node compute**, which "Runs Spark locally" with the driver acting "as both master and worker, with no worker nodes"; it suits small data and single-machine ML libraries. That is the same idea as this book's local runs, which use `local[2]`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
print("Spark version:       ", spark.version)
print("master:              ", sc.master)
print("defaultParallelism:  ", sc.defaultParallelism)
print("CPUs on this machine:", os.cpu_count())
print("spark.driver.memory: ", conf.get("spark.driver.memory", "<not set, Spark default applies>"))
print("spark.executor.instances:", conf.get("spark.executor.instances", "<not set>"))
print("spark.dynamicAllocation.enabled:", spark.conf.get("spark.dynamicAllocation.enabled", "<not set>"))
print("spark.sql.shuffle.partitions:", spark.conf.get("spark.sql.shuffle.partitions"))
print("spark.sql.adaptive.enabled:  ", spark.conf.get("spark.sql.adaptive.enabled"))
```
```text
Spark version:        4.2.0
master:               local[2]
defaultParallelism:   2
CPUs on this machine: 4
spark.driver.memory:  <not set, Spark default applies>
spark.executor.instances: <not set>
spark.dynamicAllocation.enabled: <not set>
spark.sql.shuffle.partitions: 4
spark.sql.adaptive.enabled:   true
```

The machine has 4 CPUs but the session asked for 2 threads, so parallelism is 2. Unset values fall back to Spark's defaults (`spark.driver.memory` 1g, `spark.dynamicAllocation.enabled` false, on the Spark 4.2.0 configuration page).

**Settings fixed at start-up.** Spark's configuration page says deploy-related properties "like 'spark.driver.memory', 'spark.executor.instances'" "may not be affected when setting programmatically ... in runtime". Session SQL settings can change at any time; a cluster-level setting cannot change from a running session:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
spark.conf.set("spark.sql.shuffle.partitions", "8")
print("spark.sql.shuffle.partitions now:", spark.conf.get("spark.sql.shuffle.partitions"))
try:
    spark.conf.set("spark.executor.memory", "8g")
except Exception as e:
    print(type(e).__name__ + ":", str(e).splitlines()[0])
spark.conf.set("spark.redrock.turbo_mode", "true")
print("spark.redrock.turbo_mode =", spark.conf.get("spark.redrock.turbo_mode"))
```
```text
spark.sql.shuffle.partitions now: 8
AnalysisException: [CANNOT_MODIFY_CONFIG] Cannot modify the value of the Spark config: "spark.executor.memory".
spark.redrock.turbo_mode = true
```

Two lessons. Memory and node settings belong in the compute configuration, not in a notebook ("Set Spark configuration properties on Databricks": properties set in the compute configuration apply to "All notebooks and jobs run with the compute resource"; set in a notebook, "Only the SparkSession for the current notebook"). And an unknown key is accepted silently, so a misspelled setting "works" without doing anything. Databricks "generally recommends against configuring most Spark properties", and the best-practices page warns that hardcoded values such as `spark.executor.memory` "override the built-in optimizations".

**Autoscaling.** Give a minimum and maximum number of workers and "Databricks then chooses the appropriate number of workers required to run your job." Premium-plan workspaces get **optimized autoscaling**: it "Scales up from min to max in at most 2 scaling events", can scale down when not idle "by looking at the shuffle file state", and scales down if underutilized over the last 40 seconds on job compute or 150 seconds on all-purpose compute. Standard-plan workspaces get the slower standard autoscaling. Three cautions from the same page: "Do not enable Apache Spark Dynamic Allocation (`spark.dynamicAllocation.enabled`) on compute resources that use Databricks autoscaling"; "Autoscaling is not available for `spark-submit` jobs"; and autoscaling "has limitations scaling down cluster size for Structured Streaming workloads", for which Databricks recommends Lakeflow pipelines (formerly Delta Live Tables) with enhanced autoscaling.

**Auto-termination.** "If the difference between the current time and the last command run on the compute resource is more than the inactivity period specified, Databricks automatically terminates that compute resource." The period "must be between 10 and 10,000 minutes (about 7 days)"; `0` turns it off ("Manage classic compute", Nov 5, 2026). "Idle compute continue to accumulate DBU and cloud instance charges during the inactivity period before termination." The UI's default value is not stated on these pages (unknown here). Through the API, the Clusters API reference is explicit: if `autotermination_minutes` is "not set, this cluster will not be automatically terminated." A terminated compute is "automatically and permanently deleted 30 days after termination" unless pinned.

**Spot instances.** Spot (AWS) instances use spare cloud capacity at a lower price but can be reclaimed. In the UI, "The first instance will always be on-demand (the driver node is always on-demand) and subsequent instances will be spot instances." In the API, `aws_attributes.first_on_demand` sets how many nodes are on-demand ("If this value is greater than 0, the cluster driver node in particular will be placed on an on-demand instance"; its default on AWS is `0`) and `availability` is `SPOT`, `ON_DEMAND` or `SPOT_WITH_FALLBACK`. Google Cloud uses `gcp_attributes.availability` (`PREEMPTIBLE_GCP`, `ON_DEMAND_GCP` or `PREEMPTIBLE_WITH_FALLBACK_GCP`); the older `use_preemptible_executors` field is marked deprecated in the Clusters API reference. The cost guide: spot instances "are a good choice for workloads where it is acceptable to take longer because one or more spot instances have been evicted".

**Instance pools.** "Databricks pools are a set of idle, ready-to-use instances. When cluster nodes are created using the idle instances, cluster start and auto-scaling times are reduced." "Databricks does not charge DBUs while instances are idle in the pool. Instance provider billing does apply." A pool has minimum idle instances, maximum capacity and an idle-instance auto-termination time; all clusters in it use the pool's instance type for driver and workers. "Do not use a pool with spot instances as your driver type." Tags differ: pool-backed clusters' cloud instances get the pool and workspace tags, not the cluster tags. And: "If your workload supports serverless compute, Databricks recommends using serverless compute instead of pools."

A classic cluster spec in the Clusters API shape (autoscaling 2 to 8 workers, on-demand driver, spot workers with fallback, Photon, standard access mode, tags, 30-minute auto-termination):

*Databricks only, not run here. Syntax from [Clusters API: Create new cluster](https://docs.databricks.com/api/workspace/clusters/create).*
```json
{
  "cluster_name": "redrock-dev-standard",
  "spark_version": "19.x-scala2.13",
  "node_type_id": "r3.xlarge",
  "autoscale": { "min_workers": 2, "max_workers": 8 },
  "autotermination_minutes": 30,
  "runtime_engine": "PHOTON",
  "data_security_mode": "DATA_SECURITY_MODE_STANDARD",
  "aws_attributes": {
    "availability": "SPOT_WITH_FALLBACK",
    "first_on_demand": 1,
    "spot_bid_price_percent": 100,
    "zone_id": "auto"
  },
  "custom_tags": { "team": "data-eng", "env": "dev" }
}
```

The API page itself recommends "filling out the create compute UI and then copying the generated JSON definition from the UI" rather than writing the JSON from scratch.

!!! tip "In the interview"
    **"How would you size a cluster for a batch job?"** Start from a standard (a policy T-shirt size), think in total cores, memory and local disk rather than worker count, use fewer larger workers for shuffle-heavy joins, turn on autoscaling with a sensible min and max, put workers on spot with an on-demand driver if the job can tolerate a slower run, then measure: CPU use, spill and idle executors in the Spark UI. Heavy spill means more memory per core; low CPU with no spill means the cluster is too big. Fix skew and small files before adding workers.

## 6.9 Compute policies and job clusters as code
*Level: expert.*

**The problem.** Left alone, people create oversized clusters with no auto-termination on whatever runtime they last used. Admins need guardrails without reviewing every cluster.

**The tool.** "A policy is a tool workspace admins can use to limit a user or group's compute creation permissions based on a set of policy rules." Policies can fix values, hide fields, set defaults, cap cost and require tags. A user without the **Unrestricted cluster creation** entitlement "can only create compute resources using their granted policies." Every workspace has four default policies ("Default policies and policy families", Sep 11, 2026): **Personal Compute** (a dedicated single-node resource, available to all users by default), **Shared Compute** (standard access mode, latest LTS), **Power User Compute** (dedicated, latest ML runtime) and **Job Compute** (job compute only, latest LTS). Admins can build custom policies from these families.

A policy definition is JSON, one rule per attribute; attribute paths are Clusters API field names, plus two virtual attributes: `dbus_per_hour` ("the maximum DBUs a resource can use on an hourly basis including the driver node") and `cluster_type` (`all-purpose`, `job` or `dlt`). Rule types are `fixed`, `forbidden`, `allowlist`, `blocklist`, `regex`, `range` and `unlimited`. This job-only policy for Red Rock Supply follows the reference's "Job-only policy" example, with a range on workers, an LTS runtime default, Photon fixed on and a required cost tag:

*Databricks only, not run here. Syntax from [Compute policy reference](https://docs.databricks.com/aws/en/admin/clusters/policy-definition).*
```json
{
  "cluster_type": { "type": "fixed", "value": "job" },
  "dbus_per_hour": { "type": "range", "maxValue": 100 },
  "num_workers": { "type": "range", "minValue": 1, "maxValue": 10 },
  "spark_version": { "type": "unlimited", "defaultValue": "auto:latest-lts" },
  "runtime_engine": { "type": "fixed", "value": "PHOTON", "hidden": true },
  "instance_pool_id": { "type": "forbidden", "hidden": true },
  "custom_tags.cost_center": { "type": "allowlist", "values": ["bronze-ingest", "silver-gold", "bi"] }
}
```

Two details from that page: default values in a policy "don't automatically get applied to compute created with the Clusters API" unless the request sets `apply_policy_default_values` to `true`; and "There can only be one limitation per attribute."

**Job compute as code.** In Declarative Automation Bundles ("formerly known as Databricks Asset Bundles", [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/)), a job declares its compute under `job_clusters`, and tasks point to it by `job_cluster_key`. The cluster fields are the same as in the Clusters API. A Red Rock Supply silver/gold job with one shared job cluster:

*Databricks only, not run here. Syntax from [Override with target settings](https://docs.databricks.com/aws/en/dev-tools/bundles/overrides) and [Declarative Automation Bundles resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources).*
```yaml
resources:
  jobs:
    redrock_silver_gold:
      name: redrock_silver_gold
      job_clusters:
        - job_cluster_key: etl
          new_cluster:
            spark_version: 15.4.x-scala2.12
            node_type_id: i3.xlarge
            autoscale:
              min_workers: 2
              max_workers: 8
            runtime_engine: PHOTON
            data_security_mode: DATA_SECURITY_MODE_STANDARD
            aws_attributes:
              availability: SPOT_WITH_FALLBACK
              first_on_demand: 1
            custom_tags:
              cost_center: silver-gold
      tasks:
        - task_key: build_silver
          job_cluster_key: etl
          notebook_task:
            notebook_path: ../src/build_silver.ipynb
        - task_key: build_gold
          depends_on:
            - task_key: build_silver
          job_cluster_key: etl
          notebook_task:
            notebook_path: ../src/build_gold.ipynb
```

To run the same job on serverless instead, drop `job_clusters` and `job_cluster_key`: "you can either omit the `clusters` setting for a job with a notebook task, or you can specify an environment"; for Python script, Python wheel and dbt tasks, `environment_key` is required ("Bundle configuration examples", Oct 29, 2026).

## 6.10 What drives cost, and how to keep it down
*Level: expert.*

**What you pay.** "Total costs include Databricks Units (DBUs) plus virtual machine, disk, and associated network costs. Note that for serverless services, the DBU cost already includes the virtual machine costs" ("Best practices for cost optimization"). The DBU rate depends on the SKU; SKU names in the docs' examples, such as `STANDARD_ALL_PURPOSE_COMPUTE` and `ENTERPRISE_ALL_PURPOSE_COMPUTE_(PHOTON)`, show that the kind of compute, the plan tier and Photon all matter. The prices are on Databricks' pricing pages and in `system.billing.list_prices`; no docs page used here gives a dollar figure, and they change, so none is quoted.

**Where to see it.** `system.billing.usage` holds one row per usage record with `usage_date`, `sku_name`, `usage_quantity`, `usage_unit` (`DBU`), `custom_tags`, `usage_metadata` (IDs such as `cluster_id`, `job_id`, `warehouse_id`, `instance_pool_id`), `identity_metadata`, `billing_origin_product` (for example `JOBS`, `DLT`, `SQL`, `ALL_PURPOSE`, `INTERACTIVE`), `product_features` (including `is_serverless` and `is_photon`) and `record_type` ("Billable usage system table reference", Nov 6, 2026). Three things to know:

- "Records are typically available within 12 hours"; the serverless FAQ says there "could be up to a 24-hour delay".
- Corrections arrive as `RETRACTION` and `RESTATEMENT` rows, so always `SUM(usage_quantity)` rather than reading single rows.
- Some products share a SKU: data quality monitoring, predictive optimization and "serverless workflows" (the billing page's wording) are all billed under the serverless jobs SKU; `billing_origin_product` tells them apart.

DBUs per product per day over the last 30 days:

*Databricks only, not run here. Syntax from [Monitor costs using system tables](https://docs.databricks.com/aws/en/admin/usage/system-tables).*
```sql
SELECT usage_date, billing_origin_product, SUM(usage_quantity) AS dbus
FROM system.billing.usage
WHERE usage_date >= current_date() - INTERVAL 30 DAYS
  AND usage_unit = 'DBU'
GROUP BY ALL
ORDER BY usage_date, dbus DESC;
```

The same in PySpark:

*Databricks only, not run here. Table and columns from [Billable usage system table reference](https://docs.databricks.com/aws/en/admin/system-tables/billing).*
```python
from pyspark.sql import functions as F
dbus = (spark.table("system.billing.usage")
        .filter((F.col("usage_date") >= F.date_sub(F.current_date(), 30)) & (F.col("usage_unit") == "DBU"))
        .groupBy("usage_date", "billing_origin_product")
        .agg(F.sum("usage_quantity").alias("dbus"))
        .orderBy("usage_date", F.desc("dbus")))
```

List-price cost by team tag for one month, joining `system.billing.list_prices` on the price valid at the time of use (`pricing.effective_list.default` resolves list and promotional prices; it is a list price, not your negotiated price):

*Databricks only, not run here. Syntax from [Monitor costs using system tables](https://docs.databricks.com/aws/en/admin/usage/system-tables).*
```sql
SELECT usage.custom_tags['team'] AS team,
       SUM(usage.usage_quantity * list_prices.pricing.effective_list.default) AS list_cost
FROM system.billing.usage
JOIN system.billing.list_prices ON list_prices.sku_name = usage.sku_name
WHERE usage.usage_end_time >= list_prices.price_start_time
  AND (list_prices.price_end_time IS NULL OR usage.usage_end_time < list_prices.price_end_time)
  AND usage.usage_date BETWEEN '2026-10-01' AND '2026-10-31'
GROUP BY ALL
ORDER BY list_cost DESC;
```

**Tags.** Custom tags on workspaces, compute, SQL warehouses and pools propagate to `system.billing.usage` and to the cloud resources. Tag from day one: "missing tags can't be added to past events." Serverless has no cluster to tag; serverless usage is attributed with **serverless usage policies** (Public Preview), whose tags are "applied to any serverless compute activity incurred by a user assigned to the policy". (In the bundle resource reference the job field is `usage_policy_id`, "The ID of the serverless usage policy to use for this job"; an older `budget_policy_id` field is still listed beside it.) Compute policies can require tags (`custom_tags.<name>`); budgets in the account console send alerts.

**The levers, roughly in order of size:**

1. Scheduled work off all-purpose compute, onto job compute or serverless jobs (section 6.3).
2. Auto-termination on every interactive cluster and auto-stop on every warehouse; serverless warehouses so that stopping is painless.
3. Right-sizing and autoscaling; fewer, larger workers for shuffle-heavy work; no GPUs without GPU libraries.
4. Spot workers with an on-demand driver for jobs that can tolerate a slower run; fleet instance types on AWS.
5. Compute policies that make the cheap choice the default: `dbus_per_hour` caps, `cluster_type`, worker limits, required tags.
6. Triggered instead of always-on streaming when the business does not need second-level freshness: "Databricks recommends using Structured Streaming with the `AvailableNow` trigger for incremental workloads that do not have low latency requirements."
7. Serverless jobs in standard performance mode for batch that is not time critical (fewer DBUs, same SKU).
8. Photon where it measurably lowers cost per run; up-to-date runtimes; Delta tables kept compacted and clustered so jobs read less ([chapter 22](22-Performance-Tuning.md)).
9. Visibility: tags, usage policies, the cost dashboards, budgets with alerts, a monthly review per team.

!!! tip "In the interview"
    **"How would you cut our Databricks bill?"** Measure first: query `system.billing.usage` by `billing_origin_product`, SKU, job and tag for the last 30 days and find the top items. The usual findings are scheduled jobs on all-purpose clusters (move them to job compute or serverless jobs), interactive clusters and warehouses that never stop (auto-termination, serverless warehouses with auto-stop), oversized or always-on clusters (autoscaling, right-sizing, spot workers with an on-demand driver) and always-on streams that could run with `AvailableNow` a few times a day. Then make it stick: compute policies with DBU caps and required tags, serverless usage policies, budgets and alerts, and a monthly review with each team.

## 6.11 Red Rock Supply: choosing compute
*Level: intermediate.*

Red Rock Supply's platform has four kinds of work: JSON order events landing in cloud storage (bronze), nightly silver and gold builds (deduplicated `shop.silver.orders`, SCD 2 customers, daily sales in `shop.gold`), dashboards for the sales team, and ad hoc questions from analysts and engineers. Figure 6.3 is the decision path; the table gives the choice and the reason.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 390" role="img" aria-label="Decision tree. SQL and BI work goes to a serverless SQL warehouse, or a pro warehouse if blocked. Pipelines go to a serverless pipeline, or classic pipeline compute. Scheduled jobs go to serverless jobs, or classic job compute. Interactive notebooks go to a serverless notebook, or all-purpose compute.">
<defs><marker id="a6t" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="220" y="10" width="200" height="38" rx="8"/>
<line x1="300" y1="48" x2="82" y2="78" marker-end="url(#a6t)"/>
<line x1="310" y1="48" x2="242" y2="78" marker-end="url(#a6t)"/>
<line x1="330" y1="48" x2="402" y2="78" marker-end="url(#a6t)"/>
<line x1="340" y1="48" x2="562" y2="78" marker-end="url(#a6t)"/>
<rect x="7" y="80" width="150" height="38" rx="6"/>
<rect x="167" y="80" width="150" height="38" rx="6"/>
<rect x="327" y="80" width="150" height="38" rx="6"/>
<rect x="487" y="80" width="150" height="38" rx="6"/>
<line x1="82" y1="118" x2="82" y2="146" marker-end="url(#a6t)"/>
<line x1="242" y1="118" x2="242" y2="146" marker-end="url(#a6t)"/>
<line x1="402" y1="118" x2="402" y2="146" marker-end="url(#a6t)"/>
<line x1="562" y1="118" x2="562" y2="146" marker-end="url(#a6t)"/>
<rect x="7" y="148" width="150" height="50" rx="6" stroke-width="2.5"/>
<rect x="167" y="148" width="150" height="50" rx="6" stroke-width="2.5"/>
<rect x="327" y="148" width="150" height="50" rx="6" stroke-width="2.5"/>
<rect x="487" y="148" width="150" height="50" rx="6" stroke-width="2.5"/>
<line x1="82" y1="198" x2="82" y2="214" stroke-dasharray="4 3"/>
<line x1="82" y1="240" x2="82" y2="250" marker-end="url(#a6t)"/>
<line x1="242" y1="198" x2="242" y2="214" stroke-dasharray="4 3"/>
<line x1="242" y1="240" x2="242" y2="250" marker-end="url(#a6t)"/>
<line x1="402" y1="198" x2="402" y2="214" stroke-dasharray="4 3"/>
<line x1="402" y1="240" x2="402" y2="250" marker-end="url(#a6t)"/>
<line x1="562" y1="198" x2="562" y2="214" stroke-dasharray="4 3"/>
<line x1="562" y1="240" x2="562" y2="250" marker-end="url(#a6t)"/>
<rect x="7" y="252" width="150" height="84" rx="6"/>
<rect x="167" y="252" width="150" height="84" rx="6"/>
<rect x="327" y="252" width="150" height="84" rx="6"/>
<rect x="487" y="252" width="150" height="84" rx="6"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="320" y="34" font-size="14" font-weight="bold">What is the work?</text>
<text x="82" y="104">SQL, dashboards, BI</text>
<text x="242" y="104">Lakeflow pipeline</text>
<text x="402" y="104">Scheduled job</text>
<text x="562" y="104">Notebook, ad hoc</text>
<text x="82" y="169" font-weight="bold">Serverless SQL</text>
<text x="82" y="187" font-weight="bold">warehouse</text>
<text x="242" y="169" font-weight="bold">Serverless</text>
<text x="242" y="187" font-weight="bold">pipeline</text>
<text x="402" y="169" font-weight="bold">Serverless jobs</text>
<text x="402" y="187" font-weight="bold">(job compute)</text>
<text x="562" y="169" font-weight="bold">Serverless</text>
<text x="562" y="187" font-weight="bold">notebook</text>
<text x="320" y="232">only if a limitation blocks serverless:</text>
<text x="82" y="274">Pro warehouse</text>
<text x="82" y="292">(custom network);</text>
<text x="82" y="310">classic: entry</text>
<text x="82" y="328">level only</text>
<text x="242" y="274">Classic pipeline</text>
<text x="242" y="292">compute</text>
<text x="242" y="310">(Photon, enhanced</text>
<text x="242" y="328">autoscaling)</text>
<text x="402" y="274">Classic job</text>
<text x="402" y="292">compute: LTS,</text>
<text x="402" y="310">Photon, spot</text>
<text x="402" y="328">workers, policy</text>
<text x="562" y="274">All-purpose:</text>
<text x="562" y="292">standard mode;</text>
<text x="562" y="310">dedicated for R,</text>
<text x="562" y="328">RDD, GPU, ML</text>
<text x="320" y="370" font-weight="bold">Never: scheduled production work on all-purpose compute</text>
</g>
</svg>
<figcaption>Figure 6.3. Choosing compute: start from the kind of work, default to the serverless option, and fall back to the classic option only when a serverless limitation applies.</figcaption>
</figure>

| Workload | Choice | Why |
| --- | --- | --- |
| **Bronze ingestion**: Auto Loader picks up new order JSON files | A Lakeflow pipeline (formerly Delta Live Tables) on **serverless**, triggered every 15 minutes or hourly; or a serverless job with `Trigger.AvailableNow()` | Files arrive in bursts; serverless starts fast and stops when done. The serverless trigger rule (no `ProcessingTime` in jobs) fits a triggered design. If the business needs seconds of latency, a serverless pipeline in continuous mode, not a 24/7 job. Fallback: classic job compute, compute-optimized nodes, spot workers. |
| **Silver and gold jobs**: nightly dedupe, SCD 2 `MERGE`, daily sales | **Serverless jobs** in standard performance mode (it can tolerate a 4 to 6 minute start); performance optimized if a morning deadline is tight. Pure-SQL gold steps as SQL tasks on a serverless SQL warehouse | No idle time, no sizing, Photon on. `MERGE` and aggregations are Photon's strengths. Fallback: classic **job compute** on the latest LTS with Photon, autoscaling, spot workers with an on-demand driver, from a job-only policy (the YAML in section 6.9). |
| **BI dashboards** for the sales team | **Serverless SQL warehouse**, auto-stop at the default 10 minutes, max clusters about one per 10 concurrent queries at peak | Starts in seconds so it can stop between uses; IWM adds clusters when the whole team opens the dashboard on Monday morning. Pro only for private-network federation or no serverless in the region. |
| **Ad hoc exploration** | Analysts: the SQL editor on the serverless warehouse. Engineers: **serverless notebooks** | Nothing to start or forget to stop; the notebook timeout (2.5 hours by default) caps runaway queries. Fallback: a small all-purpose cluster in **standard** access mode with auto-termination, from the Shared Compute policy; dedicated only for R, RDD or GPU work. |

Across all four: tag everything (`cost_center` on compute and warehouses, serverless usage policies for serverless), review `system.billing.usage` monthly, and never schedule the nightly jobs on an analyst's all-purpose cluster.

!!! tip "In the interview"
    **"Design the compute for a medallion platform."** Map each layer to the cheapest compute that meets its latency: bronze as a triggered (or, if needed, continuous) serverless Lakeflow pipeline (formerly Delta Live Tables; [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)); silver and gold as serverless jobs or classic job compute on an LTS runtime with Photon; BI on a serverless SQL warehouse with auto-stop and enough clusters for peak concurrency; exploration on serverless notebooks or a standard-mode all-purpose cluster with auto-termination. Then governance: policies, tags and a billing dashboard.

## 6.12 Practice questions
*Level: mixed.*

**Q1. Name the three families of compute on Databricks and one typical use for each.**

??? success "Answer"
    Serverless compute (notebooks, Lakeflow Jobs (formerly Databricks Jobs, the "Workflows" menu; [rename note](https://docs.databricks.com/aws/en/release-notes/product/2025/june)), Lakeflow pipelines (formerly Delta Live Tables; [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)); Databricks provisions and scales it), classic compute (all-purpose for interactive work, job compute for job runs, classic pipeline compute; you configure it in your cloud account), and SQL warehouses (SQL editor, dashboards, BI tools, SQL tasks; serverless, pro or classic).

    **Why:** the Compute page groups everything this way. An interviewer usually follows up with "which would you use for X?", so name a default too: serverless where supported.

**Q2. What is a DBU, and what does a classic job compute run cost besides DBUs?**

??? success "Answer"
    A Databricks unit, "units of processing capability per hour based on VM instance type"; usage is billed in DBUs at a rate that depends on the SKU. A classic run also pays the cloud provider for virtual machines, disks and network. For serverless, the DBU price already includes the VM cost.

    **Why:** comparing serverless and classic on DBUs alone is wrong; classic has a second bill from the cloud provider.

**Q3. A team schedules its nightly ETL notebook on the shared all-purpose cluster that stays on all day. Give four reasons to move it.**

??? success "Answer"
    1. Job compute costs significantly less than all-purpose compute for non-interactive work (cost guide).
    2. Isolation: the job no longer competes with interactive users or breaks when someone restarts the cluster.
    3. No idle cost: job compute terminates when the run ends.
    4. Attribution: `usage_metadata.job_id` is not populated for jobs run on all-purpose compute, so today the job's cost is invisible.
    Move it to serverless jobs, or to classic job compute defined in the job.

    **Why:** this is the most common cost finding in real workspaces.

**Q4. What happens to job compute when the job run finishes? Can you restart it later?**

??? success "Answer"
    It terminates and "is unavailable for restarting when the job is complete." The next run creates new job compute from the job's definition. All-purpose compute, by contrast, can be restarted, and a terminated one autostarts if a job is scheduled on it.

    **Why:** job compute is tied to a run, which is what makes it isolated and free of idle time.

**Q5. A serverless job reads a Kafka topic with `readStream ... writeStream.toTable(...)` and no trigger. It fails with `INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED`. Why, and how do you fix it?**

??? success "Answer"
    Without a trigger, Spark uses `Trigger.ProcessingTime("0 seconds")`, and serverless notebooks and jobs support only `Trigger.AvailableNow()` (and the deprecated `Trigger.Once()`). Fix: add `.trigger(availableNow=True)` and schedule the job, or, for always-on streaming, run it as a serverless Lakeflow pipeline (formerly Delta Live Tables, [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) in continuous mode, or use a continuous job with `AvailableNow`.

    **Why:** the serverless limitations page lists exactly this; it is a classic "works on my cluster, fails on serverless" question.

**Q6. Which SQL warehouse type and settings would you choose for a sales dashboard used by about 40 people during office hours?**

??? success "Answer"
    A serverless SQL warehouse. It starts in about 2 to 6 seconds, so auto-stop (default 10 minutes) can stop it between uses without making the first click slow, and Intelligent Workload Management adds clusters when many queries arrive at once. Set the maximum clusters from peak concurrency (Databricks recommends a cluster for every 10 concurrent queries) and raise the cluster size only if queries spill to disk.

    **Why:** size handles query weight, cluster count handles concurrency; serverless makes idle stopping practical.

**Q7. When would you choose a pro SQL warehouse over serverless?**

??? success "Answer"
    When serverless SQL warehouses are not available in the region, or when the warehouse needs custom-defined networking, for example to federate queries to databases in your private network or on premises. A pro warehouse runs in your cloud account, supports Photon and Predictive IO but not Intelligent Workload Management, and takes about 4 minutes to start.

    **Why:** these are the two cases the "SQL warehouse types" page gives.

**Q8. You create a SQL warehouse with Terraform using the SQL warehouses API defaults. Which type do you get?**

??? success "Answer"
    Classic. With default parameters the API creates a classic warehouse; the UI default is serverless. Set `enable_serverless_compute` to `true` and `warehouse_type` to `pro` to get serverless, and always set the field explicitly.

    **Why:** the warehouse types page documents this difference; it surprises teams that move from UI to infrastructure as code.

**Q9. A query on a Photon-enabled SQL warehouse takes 1.5 seconds. A colleague says "Photon will make it faster." Will it?**

??? success "Answer"
    Not meaningfully. The Photon page says it "doesn't improve queries that normally run in under two seconds", because time there goes into planning and scheduling, not data processing.

    **Why:** Photon pays off on longer queries over large data.

**Q10. Which of these run on Photon, and which fall back to Spark: a hash join, a Python UDF, a stateful streaming aggregation, `MERGE INTO` a Delta table, an RDD `map`?**

??? success "Answer"
    Photon: the hash join and the `MERGE` (Photon's native writer covers `MERGE`, `UPDATE`, `DELETE`, `INSERT`, CTAS). Fallback: the Python UDF, the stateful streaming aggregation and the RDD `map`. "Photon doesn't support UDFs ..., RDD APIs, or Dataset APIs" and "Stateful streaming is not supported." The query still gives correct results.

    **Why:** replacing a Python UDF with built-in functions lets Photon run the whole plan.

**Q11. A cluster is created with the Clusters API and the request has no `runtime_engine`. Is Photon on?**

??? success "Answer"
    No. The Clusters API reference says that if `runtime_engine` is "left unspecified, the runtime engine defaults to standard" (unless a legacy `spark_version` contains `-photon-`). The Photon page also says API users "must explicitly enable Photon by setting `runtime_engine` to `PHOTON`". In the UI the checkbox is on by default, which is why the difference is easy to miss.

    **Why:** UI defaults and API defaults differ for Photon, auto-termination and warehouse type.

**Q12. Find the bugs in this all-purpose cluster spec created through the API for interactive work.**

*Databricks only, not run here. Syntax from [Clusters API: Create new cluster](https://docs.databricks.com/api/workspace/clusters/create).*
```json
{
  "cluster_name": "analytics",
  "spark_version": "19.x-scala2.13",
  "node_type_id": "r3.xlarge",
  "num_workers": 6,
  "aws_attributes": { "availability": "SPOT", "first_on_demand": 0 }
}
```

??? success "Answer"
    1. No `autotermination_minutes`: through the API, if it is "not set, this cluster will not be automatically terminated", so it bills until someone stops it. Add, for example, `"autotermination_minutes": 30` (10 to 10,000, or 0 to disable).
    2. `first_on_demand: 0` with `SPOT` puts the driver on spot too; if the driver is reclaimed the whole cluster fails. Use `"first_on_demand": 1` (the AWS reference: "If this value is greater than 0, the cluster driver node in particular will be placed on an on-demand instance"), ideally with `SPOT_WITH_FALLBACK`.
    3. A fixed `num_workers` for interactive work; `autoscale` with a min and max fits a load that changes during the day.

    **Why:** each of these is a real cost or reliability problem, and a compute policy can prevent all three.

**Q13. A data scientist needs R on a cluster that reads Unity Catalog tables. Which access mode, and why?**

??? success "Answer"
    Dedicated access mode (formerly single user). R is not supported on standard access mode (or on serverless). Dedicated compute is assigned to one user or one group and supports Python, SQL, Scala and R.

    **Why:** standard is the default recommendation; dedicated is for the listed exceptions: R, RDD APIs, GPUs, the ML runtime, privileged machine access.

**Q14. A table has a row filter. A user on dedicated compute running Databricks Runtime 15.3 cannot read it. What is needed?**

??? success "Answer"
    Fine-grained access control on dedicated compute needs Databricks Runtime 15.4 LTS or above for reads (16.3 or above for writes), and the workspace must be enabled for serverless compute, because the filtering is delegated to serverless compute. On 15.3 or below, tables with row filters or column masks cannot be accessed. Alternatively use standard access mode, which enforces filters natively.

    **Why:** dedicated compute uses the classic Spark architecture, so it cannot safely filter in place; Lakeguard on serverless does it.

**Q15. An old cluster JSON has `"data_security_mode": "USER_ISOLATION"`. What does that mean today, and what is the current value?**

??? success "Answer"
    Standard access mode (formerly shared). `USER_ISOLATION` is a legacy alias for `DATA_SECURITY_MODE_STANDARD`; likewise `SINGLE_USER` is a legacy alias for `DATA_SECURITY_MODE_DEDICATED`. The `LEGACY_*` modes are deprecated starting with Databricks Runtime 15.0.

    **Why:** you will meet old names in existing configs, policies and interview questions.

**Q16. A function page says "Applies to: Databricks SQL Databricks Runtime 16.2 and above". Can you use it on (a) a 15.4 LTS cluster, (b) a 17.3 LTS cluster, (c) a SQL warehouse?**

??? success "Answer"
    (a) No: 15.4 is below 16.2. (b) Yes: 17.3 LTS is later than 16.2. (c) Yes: the label lists Databricks SQL. "And above" means the named version and every later one ("How to use the SQL reference": "All versions of Databricks SQL and Databricks Runtime 11.3 LTS and later" for an 11.3 LTS label).

    **Why:** reading version lines quickly is how you avoid "function not found" surprises after deploying to an older cluster.

**Q17. Which Databricks Runtime would you choose for (a) production job compute, (b) an engineer's all-purpose cluster, (c) a GPU fine-tuning job?**

??? success "Answer"
    (a) The latest LTS version, so the job is stable and you can test before upgrading. (b) The most current version, for the latest optimizations. (c) The ML runtime page recommends AI Runtime (serverless GPU) for custom deep-learning work; on classic compute, a Databricks Runtime ML version with a GPU instance type, which uses dedicated access mode.

    **Why:** these are the recommendations on the configuration reference and best-practices pages; ML runtime only when needed, because its many libraries can conflict with yours.

**Q18. What changed about Databricks Runtime versions starting with version 19?**

??? success "Answer"
    Before 19, Databricks released minor feature versions (18.0, 18.1, 18.2...), each with its own Beta and GA, and only some became LTS; non-LTS versions were supported six months. From 19, a version keeps one number, receives new features under that number for about six months after GA, then transitions to LTS with fixes until three years after GA. The supported list shows "19" with end of support "Determined at LTS transition".

    **Why:** older interview prep material still talks about picking "the x.y LTS"; the version lines you read now include "18 LTS" and "19".

**Q19. What does this print on open-source Spark, and what is the Databricks lesson?**

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
try:
    spark.conf.set("spark.executor.memory", "8g")
except Exception as e:
    print(type(e).__name__ + ":", str(e).splitlines()[0])
```

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
    ```text
    AnalysisException: [CANNOT_MODIFY_CONFIG] Cannot modify the value of the Spark config: "spark.executor.memory".
    ```
    Executor memory is fixed when the application starts. On Databricks such settings belong in the compute configuration (or are better left to Databricks' defaults), not in a notebook cell; notebook `spark.conf.set` affects only that session's runtime settings.

    **Why:** "I'll just give the executors more memory from the notebook" does not work; resize the compute instead.

**Q20. On the local engine, `spark.conf.set("spark.redrock.turbo_mode", "true")` succeeds. What does that tell you about tuning by Spark confs?**

??? success "Answer"
    Spark accepts unknown keys without error (the run printed `spark.redrock.turbo_mode = true`), so a misspelled or nonexistent setting looks applied and does nothing. Photon, for example, is enabled through `runtime_engine` in the compute spec, which is the switch the Photon page documents. Check a setting's effect in the plan, the Spark UI or the query profile, and follow Databricks' advice to avoid setting most Spark properties.

    **Why:** silent no-ops are a common source of "we tuned it and nothing changed".

**Q21. When would you make the driver larger than the workers?**

??? success "Answer"
    When the driver does more work than usual: collecting large results (`collect()`, `toPandas()`) to analyze in the notebook, or many notebooks attached to one all-purpose cluster (the driver keeps the state of every attached notebook). Otherwise the default, driver the same type as the workers, is fine.

    **Why:** the configuration reference names exactly this case; most out-of-memory errors on the driver come from pulling data to it.

**Q22. A cluster has 0 workers and is not in single-node mode. What happens to a Spark query?**

??? success "Answer"
    It fails: "To run a Spark job, you need at least one worker node. If the compute resource has zero workers, you can run non-Spark commands on the driver node, but Spark commands will fail." Use single-node compute, which runs Spark locally with the driver acting as master and worker, or add workers.

    **Why:** a multi-node resource cannot be scaled to zero; single node is a distinct mode.

**Q23. Find the bug: a team turns on `spark.dynamicAllocation.enabled=true` in the Spark config of a cluster that also has Databricks autoscaling (2 to 10 workers).**

??? success "Answer"
    The configuration reference says not to: "Do not enable Apache Spark Dynamic Allocation (`spark.dynamicAllocation.enabled`) on compute resources that use Databricks autoscaling." The two make conflicting scaling decisions, "leading to executor churn, `NODES_LOST` errors, and tasks that are never picked up." Remove the setting and let Databricks autoscaling manage workers.

    **Why:** settings copied from an open-source YARN cluster often cause this.

**Q24. Which nodes of a classic job cluster would you put on spot instances, and which not?**

??? success "Answer"
    Workers can be spot (with fallback to on-demand) for jobs that can tolerate a slower run when instances are reclaimed. The driver should be on-demand: in the UI "the driver node is always on-demand"; in the API set `first_on_demand` to at least 1. Never use a pool of spot instances as the driver type. For jobs with a hard deadline, use on-demand workers or a larger margin.

    **Why:** losing a worker slows the job; losing the driver fails it.

**Q25. What do instance pools save, and what do you still pay for?**

??? success "Answer"
    They reduce cluster start and autoscaling time by keeping idle, ready instances. "Databricks does not charge DBUs while instances are idle in the pool", but the cloud provider still bills the idle instances (minimum idle instances never terminate). Also, cloud instances of pool-backed clusters get pool and workspace tags, not cluster tags, so put cost tags on the pool. If the workload can run on serverless, Databricks recommends serverless instead of pools.

    **Why:** pools trade a cloud bill for idle VMs against faster starts; they are not free.

**Q26. Write a compute policy that allows only job compute, at most 10 workers, an LTS runtime by default, Photon, and a required `cost_center` tag from a fixed list.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Compute policy reference](https://docs.databricks.com/aws/en/admin/clusters/policy-definition).*
    ```json
    {
      "cluster_type": { "type": "fixed", "value": "job" },
      "num_workers": { "type": "range", "minValue": 1, "maxValue": 10 },
      "spark_version": { "type": "unlimited", "defaultValue": "auto:latest-lts" },
      "runtime_engine": { "type": "fixed", "value": "PHOTON", "hidden": true },
      "custom_tags.cost_center": { "type": "allowlist", "values": ["bronze-ingest", "silver-gold", "bi"] }
    }
    ```
    `cluster_type` is a virtual attribute (`all-purpose`, `job` or `dlt`); a limiting rule makes the attribute required unless `isOptional` is set. Add `"dbus_per_hour": {"type": "range", "maxValue": ...}` to cap cost per hour. If the policy allows autoscaling, also limit `autoscale.max_workers`, which is a separate attribute in the reference.

    **Why:** policies turn cost rules into defaults instead of reviews.

**Q27. Write SQL for DBUs per day by product for the last 30 days that stays correct after billing corrections.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Monitor costs using system tables](https://docs.databricks.com/aws/en/admin/usage/system-tables).*
    ```sql
    SELECT usage_date, billing_origin_product, SUM(usage_quantity) AS dbus
    FROM system.billing.usage
    WHERE usage_date >= current_date() - INTERVAL 30 DAYS
      AND usage_unit = 'DBU'
    GROUP BY ALL
    ORDER BY usage_date, dbus DESC;
    ```
    Summing is what makes it correct: a correction adds a `RETRACTION` row with a negative quantity and a `RESTATEMENT` row, so the sum cancels the original.

    **Why:** reading individual rows double-counts corrected usage.

**Q28. Finance asks for cost, not DBUs, per team for October. How do you get it, and what is the caveat?**

??? success "Answer"
    Join `system.billing.usage` to `system.billing.list_prices` on `sku_name`, picking the price whose `price_start_time`/`price_end_time` window contains the usage time, multiply `usage_quantity` by `pricing.effective_list.default`, and group by `custom_tags['team']` (query in section 6.10). Caveats: it is the list price, not a negotiated discount; for classic compute the cloud provider's VM, disk and network costs are extra and not in this table; usage without the tag shows as `NULL`; and serverless usage needs serverless usage policies to carry the team tag.

    **Why:** cost reporting questions test whether you know what the billing tables do and do not contain.

**Q29. In `system.billing.usage`, a large share of usage has `usage_metadata.job_id` NULL even though most work is scheduled. Why?**

??? success "Answer"
    `job_id` is populated only for serverless jobs and jobs on job compute; it "does not populate for jobs run on all-purpose compute". The scheduled jobs are probably running on all-purpose clusters (their usage has a `cluster_id` instead). Other NULL rows are expected: SQL warehouses (`warehouse_id`), serverless notebooks, pipelines.

    **Why:** missing job IDs are a symptom of the job-on-all-purpose anti-pattern.

**Q30. A non-idempotent serverless job must never run twice for the same input. What serverless setting matters?**

??? success "Answer"
    Serverless auto-optimization, which "automatically optimizes the compute used to run your jobs and retries failed tasks", is on by default. For workloads that "must be executed at most once", turn it off in the task's retry policy (uncheck "Enable serverless auto-optimization (may include additional retries)"). Better still, make the job idempotent (for example `MERGE` on a key instead of blind appends).

    **Why:** retries you did not configure can duplicate data.

**Q31. Serverless jobs: standard or performance optimized mode for Red Rock Supply's nightly silver build that must finish by 7 a.m. and usually takes 20 minutes starting at 1 a.m.?**

??? success "Answer"
    Standard performance mode. It "uses less compute to reduce costs" and suits workloads that "can tolerate slightly higher startup latency of 4 to 6 minutes"; both modes use the same SKU, but standard consumes fewer DBUs. With six hours of slack, a few minutes of start-up does not matter. Use performance optimized for time-sensitive runs.

    **Why:** the cheapest compute that meets the deadline is the right answer.

**Q32. "Serverless is always cheaper." True?**

??? success "Answer"
    Not as a rule. Serverless removes idle time and start-up waste and its DBU price includes the VMs, which usually wins for bursty and short work. A long, steady, well-sized classic job on spot workers can still compare well. The Databricks serverless FAQ's advice is to run a representative workload and analyze `system.billing.usage`. Also count non-price factors: serverless limitations, no Spark UI, less control.

    **Why:** interviewers want measurement, not slogans.

**Q33. For Red Rock Supply, choose compute for bronze ingestion, silver/gold jobs, sales dashboards and ad hoc exploration, with one reason each.**

??? success "Answer"
    - Bronze: a serverless Lakeflow pipeline (formerly Delta Live Tables, [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) with Auto Loader, triggered on a schedule, or a serverless job with `AvailableNow`; files come in bursts and serverless stops when done. Continuous mode only if the business needs low latency.
    - Silver/gold: serverless jobs (standard mode for nightly runs), or classic job compute on the latest LTS with Photon, autoscaling and spot workers if serverless is blocked; never all-purpose compute.
    - Dashboards: a serverless SQL warehouse with auto-stop and max clusters sized for peak concurrency.
    - Ad hoc: serverless notebooks and the SQL editor on the warehouse; otherwise a standard-mode all-purpose cluster with auto-termination (dedicated only for R, RDD or GPU work).

    **Why:** each choice matches compute to the workload's latency and usage pattern; section 6.11 has the full table.

## Sources

- [Compute](https://docs.databricks.com/aws/en/compute/) (last updated Nov 5, 2026)
- [Connect to serverless compute](https://docs.databricks.com/aws/en/compute/serverless/) (last updated Oct 22, 2026)
- [Serverless compute limitations](https://docs.databricks.com/aws/en/compute/serverless/limitations) (last updated Nov 5, 2026)
- [Serverless compute for notebooks](https://docs.databricks.com/aws/en/compute/serverless/notebooks) (last updated Oct 22, 2026)
- [Run your Lakeflow Jobs with serverless compute for workflows](https://docs.databricks.com/aws/en/jobs/run-serverless-jobs) (last updated Nov 6, 2026)
- [Configure a serverless pipeline](https://docs.databricks.com/aws/en/ldp/serverless) (last updated Oct 12, 2026)
- [Classic compute overview](https://docs.databricks.com/aws/en/compute/use-compute) (last updated Sep 11, 2026)
- [Compute configuration reference](https://docs.databricks.com/aws/en/compute/configure) (last updated Nov 6, 2026)
- [Manage classic compute](https://docs.databricks.com/aws/en/compute/clusters-manage) (last updated Nov 5, 2026)
- [Classic compute configuration best practices](https://docs.databricks.com/aws/en/compute/cluster-config-best-practices) (last updated Sep 11, 2026)
- [Configure compute for jobs](https://docs.databricks.com/aws/en/jobs/compute) (last updated Nov 9, 2026)
- [Standard compute overview](https://docs.databricks.com/aws/en/compute/standard-overview) (last updated Sep 11, 2026)
- [Standard compute requirements and limitations](https://docs.databricks.com/aws/en/compute/standard-limitations) (last updated Nov 5, 2026)
- [Dedicated compute overview](https://docs.databricks.com/aws/en/compute/dedicated-overview) (last updated Oct 15, 2026)
- [Dedicated compute requirements and limitations](https://docs.databricks.com/aws/en/compute/dedicated-limitations) (last updated Oct 15, 2026)
- [How does Databricks enforce user isolation?](https://docs.databricks.com/aws/en/compute/lakeguard) (last updated Sep 11, 2026)
- [Unity Catalog best practices](https://docs.databricks.com/aws/en/data-governance/unity-catalog/best-practices) (last updated Oct 30, 2026)
- [Connect to a SQL warehouse](https://docs.databricks.com/aws/en/compute/sql-warehouse/) (last updated Oct 9, 2026)
- [SQL warehouse types](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-types) (last updated Oct 30, 2026)
- [Create a SQL warehouse](https://docs.databricks.com/aws/en/compute/sql-warehouse/create) (last updated Sep 11, 2026)
- [SQL warehouse sizing, scaling, and queuing behavior](https://docs.databricks.com/aws/en/compute/sql-warehouse/warehouse-behavior) (last updated Nov 5, 2026)
- [What is Photon?](https://docs.databricks.com/aws/en/compute/photon) (last updated Sep 11, 2026)
- [Databricks Runtime release notes versions and compatibility](https://docs.databricks.com/aws/en/release-notes/runtime/) (last updated Nov 4, 2026)
- [Databricks support lifecycles](https://docs.databricks.com/aws/en/release-notes/runtime/databricks-runtime-ver) (last updated Nov 6, 2026)
- [Databricks Runtime 19](https://docs.databricks.com/aws/en/release-notes/runtime/19) (last updated Nov 9, 2026)
- [Databricks Runtime for Machine Learning](https://docs.databricks.com/aws/en/machine-learning/databricks-runtime-ml) (last updated Oct 21, 2026)
- [`current_version` function](https://docs.databricks.com/aws/en/sql/language-manual/functions/current_version) (last updated Sep 11, 2026)
- [How to use the SQL reference](https://docs.databricks.com/aws/en/sql/language-manual/how-to-use) (last updated Sep 11, 2026)
- [Set Spark configuration properties on Databricks](https://docs.databricks.com/aws/en/spark/conf) (last updated Sep 11, 2026)
- [Connect to pools](https://docs.databricks.com/aws/en/compute/pool-index) (last updated Oct 29, 2024)
- [Pool configuration reference](https://docs.databricks.com/aws/en/compute/pools) (last updated Sep 11, 2026)
- [Create and manage compute policies](https://docs.databricks.com/aws/en/admin/clusters/policies) (last updated Sep 28, 2026)
- [Compute policy reference](https://docs.databricks.com/aws/en/admin/clusters/policy-definition) (last updated Oct 1, 2026)
- [Default policies and policy families](https://docs.databricks.com/aws/en/admin/clusters/policy-families) (last updated Sep 11, 2026)
- [Clusters API: Create new cluster](https://docs.databricks.com/api/workspace/clusters/create) (no last-updated date shown on the page; read Nov 11, 2026)
- [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (last updated Nov 5, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026)
- [Declarative Automation Bundles resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources) (last updated Nov 10, 2026)
- [Bundle configuration examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples) (last updated Oct 29, 2026)
- [Override with target settings](https://docs.databricks.com/aws/en/dev-tools/bundles/overrides) (last updated Sep 11, 2026)
- [Databricks components](https://docs.databricks.com/aws/en/getting-started/concepts) (last updated Oct 29, 2026)
- [Best practices for cost optimization](https://docs.databricks.com/aws/en/lakehouse-architecture/cost-optimization/best-practices) (last updated Oct 29, 2026)
- [Billable usage system table reference](https://docs.databricks.com/aws/en/admin/system-tables/billing) (last updated Nov 6, 2026)
- [Monitor costs using system tables](https://docs.databricks.com/aws/en/admin/usage/system-tables) (last updated Sep 11, 2026)
- [Pricing system table reference](https://docs.databricks.com/aws/en/admin/system-tables/pricing) (last updated Feb 4, 2025)
- [Use tags to attribute and track usage](https://docs.databricks.com/aws/en/admin/account-settings/usage-detail-tags) (last updated Oct 9, 2026)
- [Attribute usage with serverless usage policies](https://docs.databricks.com/aws/en/admin/usage/budget-policies) (last updated Sep 28, 2026)
- [Spark Configuration](https://spark.apache.org/docs/4.2.0/configuration.html) (Apache Spark 4.2.0 documentation; no last-updated date shown)
