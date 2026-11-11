# 15. Lakeflow Jobs

*A notebook that works once is not a data platform. Something has to run bronze, then silver, then gold, then the tests, every night, with the right date, on the right compute, as the right identity, and tell someone when it fails. On Databricks that something is Lakeflow Jobs, the product interviewers still call Databricks Jobs or Workflows. This chapter builds the Red Rock Supply nightly job task by task: the task graph with a branch and a loop, parameters, triggers, compute, retries, notifications, repair runs, run-as identities, the job as YAML in a bundle, and how to query job history. Interviewers use orchestration to test whether you think about failure: what happens when a task fails halfway, when the job runs twice, when you must reload last month.*

!!! abstract "In this chapter"
    **You will learn:**

    - jobs, tasks and triggers, and the task types (notebook, Python script, wheel, SQL, pipeline, dbt, JAR, Run Job, If/else, For each)
    - the task graph: dependencies, `Run if` conditions, branching and loops
    - job parameters, task parameters, dynamic value references and task values
    - schedule (Quartz cron), file arrival, table update and continuous triggers, with their limits
    - compute for jobs, retries, timeouts, maximum concurrent runs, queueing, notifications and health rules
    - repair runs, and how to make a task safe to retry
    - run-as identities and job permissions
    - the job as code (Declarative Automation Bundles, CLI, REST API), system tables, backfills, Airflow

    **You need:** [Workspace tour](02-Workspace-Tour.md) (widgets, `dbutils`), [Compute](06-Compute.md) (job compute vs serverless), [The medallion architecture](07-Medallion-Architecture.md), and [Lakeflow Spark Declarative Pipelines](13-Declarative-Pipelines.md) for the jobs-versus-pipelines comparison.

    **Levels:** sections 15.1 to 15.3 beginner, 15.4 to 15.9 intermediate, 15.10 to 15.13 expert.

**About the examples.** A job runs only in a Databricks workspace, so the job YAML, JSON, SQL on system tables and `dbutils` calls are labeled "Databricks only, not run here" with the page their syntax comes from. Two things do run here: a small Python script that reads the Red Rock job YAML and computes the task order and the repair set, and a Spark + Delta script that shows why a retried task must be idempotent.

## 15.1 Jobs, tasks and triggers
*Level: beginner.*

**The problem.** Red Rock Supply has four notebooks: load the day's order files into bronze, clean them into silver, build gold tables, test gold. Run by hand, they depend on someone remembering the order, the date and what to do when step two fails.

**The tool.** "Lakeflow Jobs is workflow automation for Databricks, providing orchestration for data processing workloads so that you can coordinate and run multiple tasks as part of a larger workflow" ([Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/), Nov 5, 2026). The product was renamed in June 2025: "The product known as Databricks Jobs is now Lakeflow Jobs. No migration is required", and on June 18, 2025 "The **Pipelines** and **Workflows** items in the left navigation have been removed, and their functionality is now available from **Jobs & Pipelines**" ([June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june), Oct 29, 2026). So: Workflows was the menu, Databricks Jobs was the product, Lakeflow Jobs is the name today, and the sidebar item is **Jobs & Pipelines**.

The overview page names three concepts:

- **Job**: "the primary resource for coordinating, scheduling, and running your operations." It holds the trigger, parameters, notifications and Git settings.
- **Task**: "a specific unit of work within a job", such as a notebook, a pipeline or a Python script. "The tasks in a job and their dependencies form a directed acyclic graph (DAG)."
- **Trigger**: "a mechanism that initiates running a job based on specific conditions or events", time-based or event-based.

A job needs at least a task, compute to run it, and a unique name; the schedule is optional, because "By default, it only runs when you manually start it" ([Configure and edit Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/configure-job), Nov 5, 2026). One **job run** executes the whole graph once; each task inside it has a **task run**.

Workspace limits from the overview page: 2000 concurrent task runs per workspace (a run that cannot start immediately gets `429 Too Many Requests`), 10000 jobs created per hour (including "runs submit"), 12000 saved jobs, 1000 tasks per job, and job parameters limited to 10,000 characters when tasks use dynamic values.

!!! tip "In the interview"
    **"What is the difference between a job and a pipeline?"** A Lakeflow job (formerly Databricks Jobs, the Workflows menu; [rename note](https://docs.databricks.com/aws/en/release-notes/product/2025/june)) orders *tasks*: run this notebook, then that SQL file, then this pipeline. A Lakeflow pipeline (formerly Delta Live Tables; [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) orders *datasets*: you declare tables and queries and the engine works out the order, checkpoints and retries inside the pipeline. The pipeline task page puts it as "procedural" versus "declarative". In practice you use both: a job runs the pipeline as one task, then the tests, the exports and the notifications around it.

## 15.2 Task types
*Level: beginner.*

The task types page lists about twenty types ([Configure and edit tasks in Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/configure-task), Nov 5, 2026). The ones a data engineer meets most, with the compute each runs on ([Configure compute for jobs](https://docs.databricks.com/aws/en/jobs/compute), Nov 9, 2026):

| Task type | What it runs | Recommended compute (supported) |
| --- | --- | --- |
| Notebook | a notebook; parameters arrive as widgets | serverless jobs (also classic jobs, all-purpose) |
| Python script | a `.py` file; parameters arrive as command-line arguments | serverless jobs (also classic) |
| Python wheel | an entry point in a wheel package | serverless jobs (also classic) |
| SQL | a SQL query, alert or `.sql` file | serverless SQL warehouse (also pro) |
| Pipeline | an update of a Lakeflow pipeline | serverless pipeline (also classic pipeline) |
| dbt | dbt commands against a SQL warehouse | serverless SQL warehouse (also pro) |
| JAR | the main class of a Scala or Java JAR | serverless jobs (also classic) |
| Spark Submit | `spark-submit` | classic jobs only |
| Run Job | another job in the workspace | the called job's own compute |
| If/else condition | a boolean comparison that picks a branch | none |
| For each | a nested task once per input value | the nested task's |

Others on the list: Visual data prep, Clean Room notebook, Database Table Sync and ingestion pipelines, SQL Alert (Public Preview), Dashboards, Power BI, dbt platform (Public Preview), Genie Code, AI Function tasks (Beta) and Lakeflow Integrations (Beta).

A few rules per type that come up in practice:

- **SQL task**: "requires Databricks SQL and a serverless or pro SQL warehouse"; a file "can contain multiple SQL statements separated by semicolons" ([SQL task for jobs](https://docs.databricks.com/aws/en/jobs/tasks/sql), Nov 3, 2026).
- **dbt task**: the commands default to `dbt deps`, `dbt seed` and `dbt run`, run in order, and Databricks "injects the `DBT_ACCESS_TOKEN` for the principal configured in the **Run As** field" ([dbt task for jobs](https://docs.databricks.com/aws/en/jobs/tasks/dbt), Sep 11, 2026).
- **Pipeline task**: in a triggered or scheduled job "the pipeline task starts a single update and stops when the update completes"; in a continuous job it runs the pipeline continuously ([Pipeline task for jobs](https://docs.databricks.com/aws/en/jobs/tasks/pipeline), Nov 5, 2026). You can ask for a full refresh on the task.
- **Run Job task**: "Databricks does not support jobs with circular dependencies or that nest more than three `Run Job` tasks" ([Run Job task for jobs](https://docs.databricks.com/aws/en/jobs/tasks/run-job), Nov 5, 2026).

## 15.3 The task graph: dependencies, Run if, branches and loops
*Level: beginner.*

**Dependencies.** Each task lists the tasks it **depends on**. "Databricks runs upstream tasks before running downstream tasks, running as many of them in parallel as possible" ([Configure task dependencies](https://docs.databricks.com/aws/en/jobs/run-if), Nov 2, 2026). The graph must be acyclic.

**Run if.** By default a task runs only when all its upstream tasks succeeded. The **Run if dependencies** field changes that (same page; the YAML value is in brackets, from [Add tasks to jobs in Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/job-task-types), Nov 6, 2026):

| Run if | YAML `run_if` | Runs when | If not met, the task is |
| --- | --- | --- | --- |
| All succeeded (default) | `ALL_SUCCESS` | all dependencies ran and succeeded | `Upstream failed` |
| At least one succeeded | `AT_LEAST_ONE_SUCCESS` | at least one succeeded | `Upstream failed` |
| None failed | `NONE_FAILED` | none failed and at least one ran | `Upstream failed` |
| All done | `ALL_DONE` | all dependencies ran, whatever their result | (always runs) |
| At least one failed | `AT_LEAST_ONE_FAILED` | at least one failed | `Excluded` |
| All failed | `ALL_FAILED` | all failed | `Excluded` |

The notes under that list matter in interviews: an upstream task with result `Excluded` "is treated as successful" when evaluating `Run if`; tasks marked `Upstream failed` or `Upstream canceled` "are treated as failed, not as skipped"; "If all of a task's dependencies are excluded, the task itself is also excluded", and this cascades down a chain (A excluded, so B excluded, so C excluded); a canceled task run propagates downstream, but failure-handling tasks still run, "for example, to verify a cleanup task runs when a task run is canceled."

**If/else.** The `If/else condition` task compares two operands with an operator; downstream tasks depend on its `true` or its `false` outcome ([Add branching logic to a job with the If/else task](https://docs.databricks.com/aws/en/jobs/tasks/if-else), Sep 11, 2026). Operands can be job parameters, task parameters or task values. Comparison rules: "The `==` and `!=` operators perform string comparison of their operands. For example, `12.0 == 12` evaluates to false", while `>`, `>=`, `<` and `<=` compare numerically, so `12.0 >= 12` is true. The YAML operators are `EQUAL_TO`, `NOT_EQUAL`, `GREATER_THAN`, `GREATER_THAN_OR_EQUAL`, `LESS_THAN` and `LESS_THAN_OR_EQUAL`, and the condition task "does not require a cluster to execute and does not support retries or notifications" (bundle task types page, Nov 6, 2026, and the Jobs API create reference; the If/else UI page, Sep 11, 2026, still points in its step 7 to the advanced settings for retries and notifications, so treat that detail as not verified).

**For each.** The `For each` task "run[s] a nested task in a loop, passing a different set of parameters to each iteration" ([Use a For each task to run another task in a loop](https://docs.databricks.com/aws/en/jobs/tasks/for-each), Nov 5, 2026). The inputs are a JSON array, typed in, or taken from a task value or a job parameter. The nested task reads the current element as `{{input}}`, or a field as `{{input.<key>}}` when the elements are objects. "You cannot add another `For each` task as the nested task." Limits: the **Inputs** box takes 5,000 characters; values behind a task value reference can be up to 48 KB; job parameter values up to 10,000 characters. **Concurrency** sets how many iterations run in parallel; the Jobs API accepts 1 to 100 ([Jobs API, Create a new job](https://docs.databricks.com/api/workspace/jobs/create)).

!!! warning "Set For each concurrency explicitly"
    The UI page (For each task, Nov 5, 2026) says the concurrency "default value is 1"; the bundle task types page (Nov 6, 2026) says that if `concurrency` is not specified, "all iterations may run in parallel subject to cluster and workspace limits." The Jobs API reference gives the 1 to 100 range but no default. The pages disagree, so always set it.

Here is the Red Rock Supply nightly job. The If/else task checks whether bronze loaded any new orders; only then do the silver tasks run, and the For each task builds three gold tables with the same notebook.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 280" role="img" aria-label="Red Rock job graph: bronze_orders, then the if/else task has_new_orders. True leads to silver_customers and silver_orders, false to log_no_data. Both silver tasks lead to the for-each task gold_tables, which runs daily_sales, category_sales and customer_value, then data_tests.">
<defs><marker id="a151" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="6" y="120" width="100" height="50" rx="6"/>
<path d="M122,145 L168,110 L214,145 L168,180 Z"/>
<rect x="246" y="40" width="122" height="46" rx="6"/>
<rect x="246" y="104" width="122" height="46" rx="6"/>
<rect x="246" y="206" width="122" height="46" rx="6"/>
<rect x="392" y="30" width="136" height="180" rx="8" stroke-dasharray="6 4"/>
<rect x="401" y="78" width="118" height="30" rx="5"/>
<rect x="401" y="116" width="118" height="30" rx="5"/>
<rect x="401" y="154" width="118" height="30" rx="5"/>
<rect x="546" y="96" width="88" height="46" rx="6"/>
<line x1="106" y1="145" x2="120" y2="145" marker-end="url(#a151)"/>
<line x1="214" y1="145" x2="244" y2="66" marker-end="url(#a151)"/>
<line x1="214" y1="145" x2="244" y2="127" marker-end="url(#a151)"/>
<polyline points="168,180 168,229 244,229" marker-end="url(#a151)"/>
<line x1="368" y1="63" x2="390" y2="100" marker-end="url(#a151)"/>
<line x1="368" y1="127" x2="390" y2="122" marker-end="url(#a151)"/>
<line x1="528" y1="119" x2="544" y2="119" marker-end="url(#a151)"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="56" y="142" font-weight="bold">bronze_orders</text>
<text x="56" y="160">notebook</text>
<text x="168" y="100" font-weight="bold">has_new_orders</text>
<text x="168" y="149">if/else</text>
<text x="168" y="196">new_rows &gt; 0</text>
<text x="232" y="92">true</text>
<text x="200" y="222">false</text>
<text x="307" y="60" font-weight="bold">silver_customers</text>
<text x="307" y="77">notebook</text>
<text x="307" y="124" font-weight="bold">silver_orders</text>
<text x="307" y="141">notebook</text>
<text x="307" y="226" font-weight="bold">log_no_data</text>
<text x="307" y="243">notebook</text>
<text x="460" y="50" font-weight="bold">gold_tables</text>
<text x="460" y="67">for each, concurrency 3</text>
<text x="460" y="98">daily_sales</text>
<text x="460" y="136">category_sales</text>
<text x="460" y="174">customer_value</text>
<text x="460" y="202">build_gold notebook</text>
<text x="590" y="116" font-weight="bold">data_tests</text>
<text x="590" y="133">notebook</text>
</g>
</svg>
<figcaption>Figure 15.1. The Red Rock Supply job. has_new_orders is an If/else task: silver runs on its true outcome, log_no_data on its false outcome. gold_tables is a For each task that runs one notebook three times, once per gold table.</figcaption>
</figure>

The same job as a bundle resource file. Sections 15.4 to 15.10 explain the job-level keys (parameters, schedule, queue, health, notifications).

*Databricks only, not run here. Syntax from [Declarative Automation Bundles resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources) and [Add tasks to jobs in Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/job-task-types).*
```yaml
resources:
  jobs:
    redrock_daily:
      name: redrock_daily
      parameters:
        - name: run_date
          default: '{{job.trigger.time.iso_date}}'
        - name: catalog
          default: shop
      schedule:
        quartz_cron_expression: '0 0 2 * * ?' # every day at 02:00
        timezone_id: UTC
        pause_status: UNPAUSED
      max_concurrent_runs: 1
      queue:
        enabled: true
      timeout_seconds: 7200
      health:
        rules:
          - metric: RUN_DURATION_SECONDS
            op: GREATER_THAN
            value: 3600
      email_notifications:
        on_failure:
          - data-oncall@example.com
        on_duration_warning_threshold_exceeded:
          - data-oncall@example.com
      tasks:
        - task_key: bronze_orders
          notebook_task:
            notebook_path: ../src/bronze_orders.py
          max_retries: 2
          min_retry_interval_millis: 60000

        - task_key: has_new_orders
          depends_on:
            - task_key: bronze_orders
          condition_task:
            op: GREATER_THAN
            left: '{{tasks.bronze_orders.values.new_rows}}'
            right: '0'

        - task_key: silver_customers
          depends_on:
            - task_key: has_new_orders
              outcome: 'true'
          notebook_task:
            notebook_path: ../src/silver_customers.py

        - task_key: silver_orders
          depends_on:
            - task_key: has_new_orders
              outcome: 'true'
          notebook_task:
            notebook_path: ../src/silver_orders.py

        - task_key: log_no_data
          depends_on:
            - task_key: has_new_orders
              outcome: 'false'
          notebook_task:
            notebook_path: ../src/log_no_data.py

        - task_key: gold_tables
          depends_on:
            - task_key: silver_customers
            - task_key: silver_orders
          for_each_task:
            inputs: '["daily_sales", "category_sales", "customer_value"]'
            concurrency: 3
            task:
              task_key: gold_table_iteration
              notebook_task:
                notebook_path: ../src/build_gold.py
                base_parameters:
                  table: '{{input}}'

        - task_key: data_tests
          depends_on:
            - task_key: gold_tables
          notebook_task:
            notebook_path: ../src/data_tests.py
```

No task names a cluster, so the notebook tasks run on serverless compute; "you can either omit the `clusters` setting for a job with a notebook task, or you can specify an environment" ([Bundle configuration examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples), Oct 29, 2026).

To see the order the scheduler derives from `depends_on`, this script reads the YAML file (saved as `src/ch15/redrock_daily.job.yml`), groups the tasks into "waves" whose upstream tasks are all done, and shows that a back edge makes the graph invalid. It is a model of the documented rule, not Databricks code. The output below is the first part of `job_dag.out`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (Plain Python with PyYAML and `graphlib`; no Spark needed.)
```python
import os
from graphlib import TopologicalSorter, CycleError
import yaml

here = os.path.dirname(os.path.abspath(__file__))
spec = yaml.safe_load(open(os.path.join(here, "redrock_daily.job.yml")))
job = spec["resources"]["jobs"]["redrock_daily"]

graph = {}                      # task -> list of upstream tasks
for t in job["tasks"]:
    deps = t.get("depends_on", [])
    graph[t["task_key"]] = [d["task_key"] for d in deps]
    labels = [d["task_key"] + (f" ({d['outcome']})" if "outcome" in d else "") for d in deps]
    kind = next(k for k in t if k.endswith("_task"))
    print(f"{t['task_key']:<17} {kind:<15} depends on: {', '.join(labels) or '-'}")

print("\nWaves (tasks in one wave can run in parallel):")
ts = TopologicalSorter(graph)
ts.prepare()
wave = 1
while ts.is_active():
    ready = sorted(ts.get_ready())
    print(f"  wave {wave}: {ready}")
    ts.done(*ready)
    wave += 1

fe = next(t for t in job["tasks"] if "for_each_task" in t)
inputs = yaml.safe_load(fe["for_each_task"]["inputs"])  # a JSON array is valid YAML
print(f"\n{fe['task_key']} runs {fe['for_each_task']['task']['task_key']} "
      f"{len(inputs)} times, concurrency {fe['for_each_task']['concurrency']}: {inputs}")

bad = {k: list(v) for k, v in graph.items()}
bad["bronze_orders"].append("data_tests")        # a back edge
try:
    list(TopologicalSorter(bad).static_order())
except CycleError as e:
    print("\nCycle found:", " -> ".join(e.args[1]))
```
```text
bronze_orders     notebook_task   depends on: -
has_new_orders    condition_task  depends on: bronze_orders
silver_customers  notebook_task   depends on: has_new_orders (true)
silver_orders     notebook_task   depends on: has_new_orders (true)
log_no_data       notebook_task   depends on: has_new_orders (false)
gold_tables       for_each_task   depends on: silver_customers, silver_orders
data_tests        notebook_task   depends on: gold_tables

Waves (tasks in one wave can run in parallel):
  wave 1: ['bronze_orders']
  wave 2: ['has_new_orders']
  wave 3: ['log_no_data', 'silver_customers', 'silver_orders']
  wave 4: ['gold_tables']
  wave 5: ['data_tests']

gold_tables runs gold_table_iteration 3 times, concurrency 3: ['daily_sales', 'category_sales', 'customer_value']

Cycle found: bronze_orders -> has_new_orders -> silver_customers -> gold_tables -> data_tests -> bronze_orders
```

Wave 3 lists all three children of the condition, but in a real run only one branch runs: on `true` the two silver tasks run in parallel and `log_no_data` is `Excluded`; on `false` the silver tasks are excluded, and so (all dependencies excluded) are `gold_tables` and `data_tests`.

## 15.4 Parameters, dynamic value references and task values
*Level: intermediate.*

**The problem.** The bronze notebook must know which day to load, and the If/else task must know how many rows bronze loaded. Hard-coding the date breaks reruns and backfills.

**Job parameters** are "key-value pairs that allow you to parameterize jobs with default static or dynamic values", and you can override them when you trigger a run ([Configure job parameters](https://docs.databricks.com/aws/en/jobs/job-parameters), Nov 5, 2026). Keys may contain only `_ - .` and alphanumeric characters. The push-down rule: "For tasks that take key-value parameters, job parameters are pushed down automatically, and if a job parameter and a task parameter share a key, the job parameter takes precedence. Tasks that take JSON-array parameters don't receive job parameters automatically."

**Task parameters** come in two shapes ([Configure task parameters](https://docs.databricks.com/aws/en/jobs/task-parameters), Nov 5, 2026): key-value pairs for notebook, Python wheel (keyword arguments), SQL and Run Job tasks; a JSON array of strings for Python script, Python wheel (positional arguments), JAR, Spark Submit and For each. Inside a notebook you read a parameter with `dbutils.widgets.get("run_date")`; in SQL with a named marker such as `:run_date`; in a script as a command-line argument ([Access parameter values from a task](https://docs.databricks.com/aws/en/jobs/parameter-use), Nov 5, 2026). Chapter 2 covers widgets.

For a Python script task, pass the job parameter into the argument list yourself:

*Databricks only, not run here. Syntax from [Bundle configuration examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples).*
```yaml
        - task_key: export_gold
          spark_python_task:
            python_file: ../src/export_gold.py
            parameters:
              - '--run_date={{job.parameters.run_date}}'
          environment_key: default
```

(`environment_key` is required for Python script, Python wheel and dbt tasks on serverless compute; the job then needs a matching `environments` entry, as in the examples page.)

**Dynamic value references** are placeholders in double curly braces that the job replaces with a string when the run starts ([Dynamic value references](https://docs.databricks.com/aws/en/jobs/dynamic-value-references), Nov 6, 2026). The ones you will use most:

| Reference | Value |
| --- | --- |
| `{{job.id}}`, `{{job.name}}`, `{{job.run_id}}` | the job's ID and name, the job run's ID |
| `{{job.repair_count}}` | number of repair attempts on this run |
| `{{job.start_time.iso_date}}` | the date (UTC) the run started; other arguments: `iso_datetime`, `year`, `month`, `day`, `hour`, `is_weekday`, `timestamp_ms` and more |
| `{{job.trigger.time.iso_date}}` | the date (UTC) the run was triggered, "rounded down to the closest minute for jobs with a cron schedule" |
| `{{job.trigger.type}}` | `periodic`, `one_time`, `run_job_task`, `file_arrival`, `continuous`, `table` or `model` |
| `{{job.parameters.<name>}}` | a job parameter |
| `{{task.name}}`, `{{task.run_id}}`, `{{task.execution_count}}` | the current task; the count includes retries and repairs |
| `{{tasks.<task_name>.result_state}}` | `success`, `failed`, `excluded`, `canceled`, `timedout`, `upstream_failed` and others |
| `{{tasks.<task_name>.values.<value_name>}}` | a task value set by an upstream task |
| `{{tasks.<task_name>.output.rows}}` | the rows of an upstream SQL task (at most 1,000 rows and 48 KB) |
| `{{backfill.iso_date}}` | the start of the time range of one backfill run |

Red Rock's `run_date` uses the trigger time rather than the start time, so a run that waited in the queue still gets the date it was triggered for.

Three rules from that page. "Contents of the double curly braces are not evaluated as expressions, except for date arithmetic" (date arithmetic such as `{{(job.start_time - 1.day).iso_date}}` is in Beta and needs an admin to turn it on). "Syntax errors, including non-existent dynamic reference values and missing braces, are silently ignored and treated as literal strings", except that a wrong name inside a known namespace, such as `{{job.notebook_url}}`, shows an error. And the old names `{{job_id}}`, `{{run_id}}`, `{{start_date}}` and `{{start_time}}` are deprecated in favor of `job.id`, `task.run_id` and `job.start_time.<argument>`.

!!! warning "A typo becomes data"
    Because an unknown reference is kept as a literal string, a misspelled placeholder can reach your notebook as the text `{{...}}` instead of a date, and a filter such as `WHERE order_date = '{{...}}'` then matches nothing. Check the resolved values under **Parameters** on the run details page after the first run.

**Task values** pass a small result from one task to later tasks ([Use task values to pass information between tasks](https://docs.databricks.com/aws/en/jobs/task-values), Nov 5, 2026). `dbutils.jobs.taskValues.set()` and `.get()` are Python functions, usable only in Python notebooks, but any task can read a value through a dynamic value reference. The value must be valid JSON and its JSON form "cannot exceed 48 KiB". Red Rock's bronze notebook ends like this:

*Databricks only, not run here. Syntax from [Use task values to pass information between tasks](https://docs.databricks.com/aws/en/jobs/task-values).*
```python
run_date = dbutils.widgets.get("run_date")          # the job parameter, pushed down
new_rows = (spark.read.table("shop.bronze.orders")
            .where(f"ingest_date = '{run_date}'")
            .count())
dbutils.jobs.taskValues.set(key="new_rows", value=new_rows)
```

The If/else task then compares `{{tasks.bronze_orders.values.new_rows}}` with `0`. Databricks recommends the dynamic value reference over `dbutils.jobs.taskValues.get(taskKey=...)` in downstream code, because the `get` call hard-codes the upstream task name, and it does "not recommend setting default values", which hide misnamed keys. When the upstream task ran inside a For each task, the reference returns a JSON array with one value per iteration, ordered by iteration index (this aggregated read is in Beta, enabled by default).

## 15.5 Triggers
*Level: intermediate.*

A job runs when a trigger fires or when someone (or something) starts it ([Automate jobs with schedules and triggers](https://docs.databricks.com/aws/en/jobs/triggers), Nov 6, 2026).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 296" role="img" aria-label="Six ways to start a run: scheduled, file arrival, table update, continuous, model update or job completion, and manual or external. Each starts a run of the redrock_daily job, subject to max concurrent runs and the queue.">
<defs><marker id="a152" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="8" y="8" width="440" height="40" rx="6"/>
<rect x="8" y="56" width="440" height="40" rx="6"/>
<rect x="8" y="104" width="440" height="40" rx="6"/>
<rect x="8" y="152" width="440" height="40" rx="6"/>
<rect x="8" y="200" width="440" height="40" rx="6" stroke-dasharray="6 4"/>
<rect x="8" y="248" width="440" height="40" rx="6"/>
<rect x="500" y="98" width="132" height="100" rx="8"/>
<line x1="448" y1="28" x2="498" y2="128" marker-end="url(#a152)"/>
<line x1="448" y1="76" x2="498" y2="138" marker-end="url(#a152)"/>
<line x1="448" y1="124" x2="498" y2="146" marker-end="url(#a152)"/>
<line x1="448" y1="172" x2="498" y2="154" marker-end="url(#a152)"/>
<line x1="448" y1="220" x2="498" y2="162" marker-end="url(#a152)"/>
<line x1="448" y1="268" x2="498" y2="172" marker-end="url(#a152)"/>
</g>
<g fill="currentColor" font-size="13">
<text x="18" y="25" font-weight="bold">Scheduled</text>
<text x="18" y="41">Quartz cron + time zone: 0 0 2 * * ? is 02:00 daily</text>
<text x="18" y="73" font-weight="bold">File arrival</text>
<text x="18" y="89">new files under a UC volume or external location</text>
<text x="18" y="121" font-weight="bold">Table update</text>
<text x="18" y="137">any or all of the monitored UC tables changed</text>
<text x="18" y="169" font-weight="bold">Continuous</text>
<text x="18" y="185">a new run when the last one ends; one run at a time</text>
<text x="18" y="217" font-weight="bold">Model update, job completion (Beta)</text>
<text x="18" y="233">a UC model changes, or upstream jobs finish</text>
<text x="18" y="265" font-weight="bold">Manual or external</text>
<text x="18" y="281">Run now, CLI, REST API, Airflow, a Run Job task</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="566" y="126" font-weight="bold">redrock_daily</text>
<text x="566" y="146">one job run</text>
<text x="566" y="166">limited by max</text>
<text x="566" y="184">concurrent runs</text>
</g>
</svg>
<figcaption>Figure 15.2. The ways a run starts. A run that would exceed the job's maximum concurrent runs is skipped, or waits in the queue when queueing is on (section 15.7).</figcaption>
</figure>

**Scheduled.** A simple schedule ("every 12 hours") or an advanced one with period, time and time zone, shown in **Quartz cron syntax** ([Run jobs on a schedule](https://docs.databricks.com/aws/en/jobs/scheduled), Nov 6, 2026). Quartz cron has six required fields and an optional seventh: seconds, minutes, hours, day of month, month, day of week, (year). The `?` means "no specific value" and is allowed only in the day-of-month and day-of-week fields; Quartz does not fully support setting both, so one of them is `?` ([Quartz `CronExpression` documentation](https://github.com/quartz-scheduler/quartz/blob/main/quartz/src/main/java/org/quartz/CronExpression.java)). Examples from the Databricks pages: `0 0 9 * * ?` "runs the job every day at 9:00 AM UTC" (bundle resources page, with `timezone_id: UTC`) and `0 */15 * * * ?` every 15 minutes (the materialized view schedule example). Unix cron's five fields (`0 2 * * *`) are not valid Quartz syntax, because Quartz requires six fields (from the Quartz source; not tested in a workspace).

Three notes from the schedule page: Databricks "enforces a minimum interval of 10 seconds between subsequent runs"; with a time zone that observes daylight saving time "an hourly job is skipped or might appear to be delayed by an hour or two" when the clocks change, so choose UTC to run every absolute hour; and "The job scheduler is not intended for low-latency jobs", runs can be delayed "up to several minutes".

**File arrival.** Starts a run when new files land in a Unity Catalog **volume** or **external location** (or a subpath of one); Unity Catalog must be enabled ([Trigger jobs when new files arrive](https://docs.databricks.com/aws/en/jobs/file-arrival-triggers), Nov 6, 2026). It makes "a best effort to check for new files every minute" and checks subdirectories recursively. Two advanced options shape the runs: **Minimum time between triggers in seconds** (a cooldown) and **Wait after last change in seconds** (a debounce: each new file resets the timer, so a batch of files becomes one run). The API's minimum for both is 60 seconds. Limits: "Only new files trigger runs. Overwriting an existing file with a file of the same name does not trigger a run"; no wildcards in the path; and if the location is *not* enabled for file events, at most 50 jobs per workspace can use such locations and the location can hold up to 10,000 files. The trigger only says "something arrived"; to process exactly the new files, the page pairs it with Auto Loader and `trigger(availableNow=True)`.

*Databricks only, not run here. Syntax from [Declarative Automation Bundles resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources) and [Jobs API, Create a new job](https://docs.databricks.com/api/workspace/jobs/create).*
```yaml
      trigger:
        pause_status: UNPAUSED
        file_arrival:
          url: /Volumes/shop/bronze/landing/orders/
          min_time_between_triggers_seconds: 900
          wait_after_last_change_seconds: 60
```

**Table update.** Starts a run when monitored tables change: Unity Catalog Delta and Iceberg managed tables, external Delta tables, materialized views, streaming tables, and views over supported tables ([Trigger jobs when source tables are updated](https://docs.databricks.com/aws/en/jobs/trigger-table-update), Nov 6, 2026). With several tables you choose **Any table is updated** or **All tables are updated** (`ANY_UPDATED` or `ALL_UPDATED` in the API). The **Run as** principal needs `SELECT` on every monitored table, or "the trigger fails to evaluate and the job does not run". A trigger monitors up to 25 tables, and more than 10 requires file events on every table. The run gets `{{job.trigger.table_update.updated_tables}}` and, per table, the commit version and timestamp that fired it. This is how a gold job can wait for silver instead of guessing a time.

**Continuous.** "To keep the job always running, trigger another job run whenever a job run completes or fails" ([Run jobs continuously](https://docs.databricks.com/aws/en/jobs/continuous), Nov 6, 2026); recommended for always-on streaming. Rules: only one running instance; the gap between runs "should be less than 60 seconds"; "You cannot use task dependencies with a continuous job"; "You cannot use retry policies in a continuous job", instead the whole job is retried with exponential backoff without a retry limit, and a **Task retry mode** of **On failure** (the default) retries failed tasks up to three times for a single-task job before the run is canceled and a new one starts. On serverless compute a continuous job needs bounded streaming triggers such as `Trigger.AvailableNow`; `ProcessingTime` and `Continuous` triggers are not supported there.

**Others.** Model update and job completion triggers are in Beta. Several triggers on one job (up to five during the **Multiple Triggers** Beta) start a run when any one fires; a continuous trigger cannot be combined with others. A workspace can have up to 12,000 active triggers. Any trigger can be paused; a paused trigger starts no new runs, and running ones continue.

!!! tip "In the interview"
    **"Schedule or event trigger for the nightly load?"** If files arrive at unpredictable times, a file arrival trigger with a debounce runs the job when the batch is complete instead of at a fixed hour that is sometimes too early. If the upstream is a table, a table update trigger waits for the real commit. A schedule is right when the business wants data at a fixed time and the inputs are reliably there. Keep the job idempotent either way, because any trigger can fire twice for the same data.

## 15.6 Compute for jobs
*Level: intermediate.*

Chapter 6 compares the compute types; here is what matters for a job ([Configure compute for jobs](https://docs.databricks.com/aws/en/jobs/compute), Nov 9, 2026):

- **Serverless compute for jobs**: if the workspace has Unity Catalog and serverless enabled, "serverless compute is the default for all tasks that support it" (notebook, Python script, dbt, Python wheel and JAR, per [Run your Lakeflow Jobs with serverless compute for workflows](https://docs.databricks.com/aws/en/jobs/run-serverless-jobs), Nov 6, 2026). Databricks recommends it for all job tasks. **Performance optimized** off means standard mode, which tolerates "slightly higher startup latency of 4 to 6 minutes" and consumes fewer DBUs.
- **Classic jobs compute**: a cluster defined in the job, created for the run and terminated after it. Databricks recommends standard access mode for jobs ([Configure classic compute for Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/run-classic-jobs), Nov 6, 2026).
- **Shared job cluster**: one job cluster used by several tasks (`job_clusters` plus `job_cluster_key`, YAML in [chapter 6](06-Compute.md)). It starts with the first task that uses it and stops after the last; it "is scoped to a single job run and cannot be used by other jobs or runs of the same job"; libraries cannot be declared on it, only on the tasks; and tasks on it share one driver JVM, so Scala singletons and loaded libraries persist between tasks.
- **All-purpose compute**: supported, but Databricks "recommends against" it for jobs: a different billing rate, no termination at the end of the run, competition with interactive users. The exceptions are iterative development and very short, frequent jobs.
- **SQL warehouses** run SQL and dbt tasks; **pipeline compute** is configured in the pipeline, not in the job.

## 15.7 Retries, timeouts, concurrency, queueing, notifications and health
*Level: intermediate.*

**Retries.** A retry policy re-runs a failed *task* within the same run. Set it per task: `max_retries` ("If not specified, the task will not be retried"), `min_retry_interval_millis` (default 0, "immediate retry"), `retry_on_timeout` (default false) (bundle task types page, Nov 6, 2026). In the API, `-1` retries indefinitely and `0` never. The UI page ([Configure and edit tasks](https://docs.databricks.com/aws/en/jobs/configure-task), Nov 5, 2026) says "For most configurations, the default setting does not retry any tasks on task failure" (the notifications page, Nov 6, 2026, has a contradicting sentence, "By default, tasks are retried three times before failing fully", so set `max_retries` explicitly); two exceptions: serverless jobs "auto-optimize retries by default", and continuous jobs use exponential backoff.

!!! warning "Serverless may retry on its own"
    "Serverless compute for workflows auto-optimization automatically optimizes the compute used to run your jobs and retries failed tasks." It is on by default. For a task that must run at most once (it sends emails, calls a payment API, appends without a key), turn it off: uncheck **Enable serverless auto-optimization** in the retry dialog, or set `disable_auto_optimization: true` on the task ([Run your Lakeflow Jobs with serverless compute for workflows](https://docs.databricks.com/aws/en/jobs/run-serverless-jobs)). Better still, make the task idempotent (section 15.8).

**Timeouts.** `timeout_seconds` on the job or on a task; 0 means no timeout. "If you configure both **Timeout** and **Retries**, the timeout applies to each retry" ([Configure and edit tasks](https://docs.databricks.com/aws/en/jobs/configure-task)). A run past its timeout gets the status "Timed Out".

**Maximum concurrent runs and queueing.** "By default, the maximum concurrent runs for all new jobs is 1", and "Databricks skips the run if the job has already reached its maximum number of active runs" ([Configure and edit Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/configure-job)). The API caps the value at 1000; setting it to 0 skips all new runs. With **queueing** on, a run that hits the job's concurrency limit, the workspace's active-run limit or the `Run Job` task limit "is queued for up to 48 hours" instead of being skipped. Queueing is "enabled by default for jobs created through the UI after April 15, 2024", and the API's `queue.enabled` defaults to `true`. Keep `max_concurrent_runs: 1` for a job that writes the same tables every run: two overlapping runs of the same MERGE are a recipe for conflicts. Raise it only when runs are independent, for example a backfill split by date.

**Duration and health rules.** A **Warning** duration sends an event when a run is slower than expected; a **Timeout** stops it. In YAML the warning is a health rule, `metric: RUN_DURATION_SECONDS`, `op: GREATER_THAN` (the only operator the API lists), with notifications on `on_duration_warning_threshold_exceeded`. Streaming backlog metrics (`STREAMING_BACKLOG_BYTES`, `_RECORDS`, `_SECONDS`, `_FILES`) are in Public Preview and "aren't supported for pipeline tasks".

**Notifications** go to email or to admin-configured destinations (Slack, Microsoft Teams, PagerDuty, webhooks), on start, success, failure, duration warning and streaming backlog ([Add notifications on a job](https://docs.databricks.com/aws/en/jobs/notifications), Nov 6, 2026). Details that bite:

- "Job-level notifications aren't sent when failed tasks are retried. To receive a failure notification after every failed task, use task notifications instead."
- At most three system destinations per event type, per job or task.
- **Mute notifications until the last retry** (task level), and mute for skipped or canceled runs, cut noise.
- A run that ends **Succeeded with failures** counts as successful: to hear about it, subscribe to **Success**.

## 15.8 Failures, repair runs and idempotent tasks
*Level: intermediate.*

**The problem.** At 02:00 the Red Rock job runs; `silver_orders` fails on a malformed record. `gold_tables` and `data_tests` never start (`Upstream failed`). You fix the parsing bug. Rerunning the whole job would reload bronze and rebuild silver customers for nothing.

**The tool: repair.** "You can repair failed or canceled multi-task jobs by running only the subset of unsuccessful tasks and any dependent tasks" ([Troubleshoot and repair job failures](https://docs.databricks.com/aws/en/jobs/repair-job-failures), Nov 5, 2026). The rules:

- Tasks re-run "with the current job and task settings": your fixed notebook, a changed cluster size.
- You can override parameters in the **Repair job run** dialog.
- A repair stays inside the original run: the matrix view gets a new column, and the run's **Duration** spans the first attempt to the last repair.
- If tasks shared a job cluster, the repair creates a new one (`my_job_cluster` becomes `my_job_cluster_v1`).
- "Repair is supported only with jobs that orchestrate two or more tasks." A single-task job is simply run again.
- In the API, `rerun_all_failed_tasks` or a list in `rerun_tasks`, plus `rerun_dependent_tasks`; a second repair of the same run must pass `latest_repair_id` ([Jobs API, Repair a job run](https://docs.databricks.com/api/workspace/jobs/repairrun)).

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 292" role="img" aria-label="Matrix of a failed run and its repair. bronze_orders, has_new_orders and silver_customers succeeded and are not re-run. silver_orders failed; gold_tables and data_tests were upstream failed. The repair re-runs these three and they succeed. log_no_data was excluded and, by inference, stays excluded.">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="220" y="34" width="180" height="30" rx="4"/>
<rect x="220" y="68" width="180" height="30" rx="4"/>
<rect x="220" y="102" width="180" height="30" rx="4"/>
<rect x="220" y="136" width="180" height="30" rx="4" stroke-width="3.5"/>
<rect x="220" y="170" width="180" height="30" rx="4" stroke-dasharray="2 3"/>
<rect x="220" y="204" width="180" height="30" rx="4"/>
<rect x="220" y="238" width="180" height="30" rx="4"/>
<rect x="430" y="34" width="200" height="30" rx="4" stroke-dasharray="6 4"/>
<rect x="430" y="68" width="200" height="30" rx="4" stroke-dasharray="6 4"/>
<rect x="430" y="102" width="200" height="30" rx="4" stroke-dasharray="6 4"/>
<rect x="430" y="136" width="200" height="30" rx="4"/>
<rect x="430" y="170" width="200" height="30" rx="4" stroke-dasharray="6 4"/>
<rect x="430" y="204" width="200" height="30" rx="4"/>
<rect x="430" y="238" width="200" height="30" rx="4"/>
</g>
<g fill="currentColor" font-size="13">
<text x="12" y="22" font-weight="bold">Task</text>
<text x="12" y="54">bronze_orders</text>
<text x="12" y="88">has_new_orders</text>
<text x="12" y="122">silver_customers</text>
<text x="12" y="156">silver_orders</text>
<text x="12" y="190">log_no_data</text>
<text x="12" y="224">gold_tables (for each)</text>
<text x="12" y="258">data_tests</text>
<text x="12" y="286">thick border = the failure; dashed = not re-run by the repair</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="310" y="22" font-weight="bold">Run at 02:00</text>
<text x="530" y="22" font-weight="bold">Repair 1 at 08:30</text>
<text x="310" y="54">Succeeded</text>
<text x="310" y="88">Succeeded (true)</text>
<text x="310" y="122">Succeeded</text>
<text x="310" y="156" font-weight="bold">Failed</text>
<text x="310" y="190">Excluded</text>
<text x="310" y="224">Upstream failed</text>
<text x="310" y="258">Upstream failed</text>
<text x="530" y="54">kept: Succeeded</text>
<text x="530" y="88">kept: Succeeded</text>
<text x="530" y="122">kept: Succeeded</text>
<text x="530" y="156">Succeeded</text>
<text x="530" y="190">kept: Excluded</text>
<text x="530" y="224">Succeeded</text>
<text x="530" y="258">Succeeded</text>
</g>
</svg>
<figcaption>Figure 15.3. A failed run and its repair, as in the Runs matrix view. The repair re-runs the failed task and the tasks that depend on it, with the current settings; tasks that succeeded keep their result. log_no_data stays excluded because the If/else task that decided the branch is not re-run (an inference from the documented rule, not checked in a workspace).</figcaption>
</figure>

The second half of `job_dag.py` applies the documented rule ("unsuccessful tasks and any dependent tasks") to this run; the output is the last two lines of `job_dag.out`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (Plain Python, continuing the script in 15.3.)
```python
run = {"bronze_orders": "SUCCESS", "has_new_orders": "SUCCESS (true)",
       "silver_customers": "SUCCESS", "silver_orders": "FAILED",
       "log_no_data": "EXCLUDED", "gold_tables": "UPSTREAM_FAILED",
       "data_tests": "UPSTREAM_FAILED"}
unsuccessful = [k for k, v in run.items() if v in ("FAILED", "UPSTREAM_FAILED", "CANCELED", "TIMEDOUT")]
downstream = {k: [c for c, ups in graph.items() if k in ups] for k in graph}
repair, todo = set(), list(unsuccessful)
while todo:
    k = todo.pop()
    if k not in repair:
        repair.add(k)
        todo.extend(downstream[k])
order = [k for k in TopologicalSorter(graph).static_order() if k in repair]
print("Repair re-runs, in order:", order)
print("Not re-run:", sorted(set(graph) - repair))
```
```text
Repair re-runs, in order: ['silver_orders', 'gold_tables', 'data_tests']
Not re-run: ['bronze_orders', 'has_new_orders', 'log_no_data', 'silver_customers']
```

**The catch: idempotency.** The repair page is blunt: "A repair re-runs each unsuccessful task from the beginning. Lakeflow Jobs doesn't make tasks idempotent, so if a task wrote part of its output before it failed, re-running it can duplicate that data." The same is true of retries, of a schedule that fires twice, and of a person who clicks **Run now** again. A task is **idempotent** when running it twice with the same parameters leaves the same result as running it once. The gold task below runs twice for the same `run_date`, first with a plain `INSERT`, then with Delta's `INSERT ... REPLACE WHERE`, then with the DataFrame `replaceWhere` option. Locally there is no Unity Catalog, so the tables are in the default schema. The script first creates `silver_orders` with three orders (two on 2026-03-01 for 59.90 and 120.00, one on 2026-03-02) and two empty gold tables; the full file is `src/ch15/idempotent_gold.py`, its output `idempotent_gold.out`.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*
```python
from datetime import date
run_date = date.fromisoformat("2026-03-01").isoformat()   # the run_date parameter, validated

# Not idempotent: a plain INSERT appends again on every attempt
append_sql = """INSERT INTO gold_daily_sales_append
  SELECT to_date(order_ts), count(*), sum(amount) FROM silver_orders
  WHERE to_date(order_ts) = DATE'{d}' GROUP BY ALL"""
for attempt in (1, 2):
    sql(append_sql.format(d=run_date))
print("Plain INSERT, run twice for the same day:")
show("SELECT * FROM gold_daily_sales_append ORDER BY ALL")

# Idempotent: INSERT ... REPLACE WHERE swaps exactly that day's slice
replace_sql = """INSERT INTO gold_daily_sales REPLACE WHERE order_date = DATE'{d}'
  SELECT to_date(order_ts) AS order_date, count(*) AS orders, sum(amount) AS revenue
  FROM silver_orders WHERE to_date(order_ts) = DATE'{d}' GROUP BY ALL"""
for attempt in (1, 2):
    sql(replace_sql.format(d=run_date))
print("INSERT ... REPLACE WHERE, run twice for the same day:")
show("SELECT * FROM gold_daily_sales ORDER BY ALL")

# The same with the DataFrame API
from pyspark.sql import functions as F
day = (spark.table("silver_orders")
       .where(F.to_date("order_ts") == F.lit(run_date).cast("date"))
       .groupBy(F.to_date("order_ts").alias("order_date"))
       .agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue")))
for attempt in (1, 2):
    (day.write.format("delta").mode("overwrite")
        .option("replaceWhere", f"order_date = '{run_date}'")
        .saveAsTable("gold_daily_sales"))
print("DataFrame replaceWhere, two more attempts:")
show("SELECT * FROM gold_daily_sales ORDER BY ALL")
print("History of gold_daily_sales:")
sql("DESCRIBE HISTORY gold_daily_sales").select("version", "operation").orderBy("version").show(truncate=False)
```
```text
Plain INSERT, run twice for the same day:
>>> SELECT * FROM gold_daily_sales_append ORDER BY ALL
+----------+------+-------+
|order_date|orders|revenue|
+----------+------+-------+
|2026-03-01|2     |179.90 |
|2026-03-01|2     |179.90 |
+----------+------+-------+

INSERT ... REPLACE WHERE, run twice for the same day:
>>> SELECT * FROM gold_daily_sales ORDER BY ALL
+----------+------+-------+
|order_date|orders|revenue|
+----------+------+-------+
|2026-03-01|2     |179.90 |
+----------+------+-------+

DataFrame replaceWhere, two more attempts:
>>> SELECT * FROM gold_daily_sales ORDER BY ALL
+----------+------+-------+
|order_date|orders|revenue|
+----------+------+-------+
|2026-03-01|2     |179.90 |
+----------+------+-------+

History of gold_daily_sales:
+-------+------------+
|version|operation   |
+-------+------------+
|0      |CREATE TABLE|
|1      |WRITE       |
|2      |WRITE       |
|3      |WRITE       |
|4      |WRITE       |
+-------+------------+
```

The plain `INSERT` doubled the day's revenue; the `REPLACE WHERE` versions leave one correct row however often they run, and each attempt is still a separate, auditable commit in the history. Other idempotent patterns: `MERGE` on a business key (silver), Auto Loader or a streaming checkpoint (bronze, which skips files already loaded), and `CREATE OR REPLACE TABLE` for a gold table rebuilt in full. The SQL course covers the generic patterns in [Duplicates and incremental loads](../../databases/sql/22-Duplicates-and-Incremental-Loads.md).

One more tool for the caller's side: `run-now` takes an `idempotency_token`. "If a run with the provided token already exists, the request does not create a new run but returns the ID of the existing run instead", so an orchestrator that retries its HTTP call does not start the job twice ([Jobs API, Trigger a new job run](https://docs.databricks.com/api/workspace/jobs/runnow)). It protects against duplicate *runs*, not against a task that duplicates *data*.

!!! tip "In the interview"
    **"How do you make a job safe to retry?"** Make every task idempotent with respect to its parameters: bronze through Auto Loader or a checkpoint so files are loaded once, silver with `MERGE` on the key, gold by replacing the slice for `run_date` (`INSERT ... REPLACE WHERE`, `replaceWhere`) or rebuilding the table. Derive the date from a parameter, never from "now" inside the code, and check the resolved value when you repair (the Repair dialog lets you override it). Then turn on retries, keep max concurrent runs at 1, and use repair runs for recovery. The repair page itself warns that Lakeflow Jobs (formerly Databricks Jobs, under the Workflows menu; [rename note](https://docs.databricks.com/aws/en/release-notes/product/2025/june)) "doesn't make tasks idempotent".

## 15.9 Run as, service principals and job permissions
*Level: intermediate.*

A job has two kinds of permission ([Manage identities, permissions, and privileges for Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/privileges), Nov 5, 2026):

- **Job permissions** decide who can see and change the job: **CAN VIEW** (see runs), **CAN MANAGE RUN** (trigger and cancel runs), **CAN MANAGE** (edit the definition, permissions, schedule) and **IS OWNER**. "A job cannot have more than one owner", a group cannot be owner, and only workspace admins can change the owner. (The same page also says that a job created while assuming a group gets that group as **Owner** and **Run as**, which disagrees with the "group cannot be owner" rule; not verified in a workspace.)
- **Run as** decides whose privileges the *tasks* use against Unity Catalog tables, volumes, secrets and workspace files. "If _user A_ creates a job, and sets the **Run as** user to _user B_, the job runs with user B's privileges. If _user C_ runs the job, the job still runs with user B's privileges."

By default the creator is both owner and **Run as**. "Databricks recommends changing the **Run as** user to a service principal, so that privileges can be controlled separately from the owner's privileges, and so that jobs do not break when the owner leaves or has changed privileges." A **service principal** is an identity for automation rather than a person. To set **Run as** you need CAN MANAGE or IS OWNER on the job, and you can choose yourself or a service principal "on which you have the **Service Principal User** entitlement". A job resource's `run_as` can also name an account group (`group_name`). Privileges are checked during the run, not all at the start, so revoking a grant mid-run can fail the run late.

*Databricks only, not run here. Syntax from [Specify a run identity for a Declarative Automation Bundles workflow](https://docs.databricks.com/aws/en/dev-tools/bundles/run-as).*
```yaml
bundle:
  name: redrock

targets:
  dev:
    mode: development
    default: true
  prod:
    mode: production
    run_as:
      service_principal_name: '<application-id-of-redrock-prod-sp>'
```

Two SQL details on the same page: the SQL **file** task "is the only SQL task type to respect the **Run as** user fully"; a saved query set to **Run as owner** always runs as the query's owner, even inside a job that runs as a service principal. And the dbt task gets its token from the **Run as** principal, which therefore needs CAN USE on the warehouse.

## 15.10 Jobs as code: bundles, CLI and REST API
*Level: expert.*

**The problem.** A job built by clicking in the UI exists only in one workspace, has no review and no history. Production jobs belong in Git.

**Declarative Automation Bundles** ("formerly known as Databricks Asset Bundles", [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/), Nov 5, 2026) describe jobs, pipelines and their source files in YAML and deploy them per target (dev, prod). The job YAML in section 15.3 is a bundle resource file. The loop, from [Develop a job with Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/jobs-tutorial) (Nov 5, 2026), which requires Databricks CLI 0.218.0 or above:

*Databricks only, not run here. Syntax from [Develop a job with Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/jobs-tutorial) and [Bundle configuration examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples).*
```bash
databricks bundle validate
databricks bundle deploy --target dev
databricks bundle run --target dev redrock_daily
databricks bundle run redrock_daily -- --run_date=2026-03-01   # override a job parameter
databricks bundle run redrock_daily --only +silver_orders       # silver_orders and everything upstream
```

`databricks bundle generate job` writes the YAML for a job that already exists in the workspace (bundle task types page), the usual first step when moving UI-built jobs into Git. The UI also shows any job as YAML ("Switch to code version (YAML)"). Chapter 16 covers targets, CI/CD and service principals for deployment.

**The CLI and REST API** work on jobs directly ([`jobs` command group](https://docs.databricks.com/aws/en/dev-tools/cli/reference/jobs-commands), Sep 11, 2026; Jobs API 2.2, `POST /api/2.2/jobs/create`, `/jobs/run-now`, `/jobs/runs/repair`):

*Databricks only, not run here. Syntax from [`jobs` command group](https://docs.databricks.com/aws/en/dev-tools/cli/reference/jobs-commands).*
```bash
databricks jobs create --json @redrock_daily.json
databricks jobs run-now 123456789 --idempotency-token redrock-2026-03-01
databricks jobs repair-run 987654321 --rerun-all-failed-tasks
```

*Databricks only, not run here. Syntax from [Jobs API, Trigger a new job run](https://docs.databricks.com/api/workspace/jobs/runnow) and [Trigger a single job run](https://docs.databricks.com/aws/en/jobs/run-now).*
```json
{
  "job_id": 123456789,
  "job_parameters": { "run_date": "2026-03-01" },
  "idempotency_token": "redrock-2026-03-01",
  "only": ["silver_orders+"]
}
```

`only` limits the run to some tasks: `+task` adds everything upstream, `task+` everything downstream ([Trigger a single job run](https://docs.databricks.com/aws/en/jobs/run-now), Sep 11, 2026). The UI equivalent is **Run now with different settings**.

## 15.11 Monitoring runs with system tables
*Level: expert.*

The job UI shows one job's runs (the matrix view is the quickest way to spot the failing task). For questions across all jobs ("which jobs failed this week, which got slower"), query the `system.lakeflow` schema ([Jobs system table reference](https://docs.databricks.com/aws/en/admin/system-tables/jobs), Nov 6, 2026). It "was previously known as `workflow`"; it holds `jobs`, `job_tasks`, `job_run_timeline` and `job_task_run_timeline` (plus `pipelines` and `pipeline_update_timeline`), with records from all workspaces of the account in the same region, a free retention of 395 days (indefinite for `pipelines`), and records "typically available within one hour".

Two things to know before writing a query:

- `jobs` and `job_tasks` are **SCD Type 2** tables: every change adds a row. Take the latest row per key (`ROW_NUMBER() ... ORDER BY change_time DESC`), then drop rows with `delete_time` set.
- `job_run_timeline` and `job_task_run_timeline` are immutable, but a run longer than an hour is **sliced into several rows**, and `result_state` is filled only in the last slice. Filter `result_state IS NOT NULL` to get one row per finished run. Its values include `SUCCEEDED`, `FAILED`, `SKIPPED`, `CANCELLED`, `TIMED_OUT`, `ERROR` and `BLOCKED`.

Failed and timed-out runs of the last 7 days, with the job name (adapted from the page's "Enrich job run with a job name" and daily count examples):

*Databricks only, not run here. Syntax from [Jobs system table reference](https://docs.databricks.com/aws/en/admin/system-tables/jobs).*
```sql
WITH jobs AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY workspace_id, job_id ORDER BY change_time DESC) AS rn
  FROM system.lakeflow.jobs QUALIFY rn = 1
)
SELECT jobs.name, r.run_id, r.trigger_type, r.result_state, r.termination_code, r.period_end_time
FROM system.lakeflow.job_run_timeline AS r
LEFT JOIN jobs USING (workspace_id, job_id)
WHERE r.period_start_time > CURRENT_TIMESTAMP() - INTERVAL 7 DAYS
  AND r.result_state IN ('FAILED', 'TIMED_OUT', 'ERROR')
ORDER BY r.period_end_time DESC
```

The same page warns that the duration columns of `job_run_timeline` are filled only for single-task jobs created with the legacy API; "For all non-legacy or multi-task job runs, use the `job_task_run_timeline` table". The `trigger_type` column tells scheduled (`CRON`, `PERIODIC`) runs from manual (`ONETIME`) ones and retries of failed runs (`ONETIME_RETRY`).

## 15.12 Backfills
*Level: expert.*

**The problem.** The hourly or daily job was broken from March 9 to 10, or the business wants last year loaded. You want the same code, run once per missing period.

**The tool.** From **Run now**, choose **Run backfill**, pick a date range and an interval; the job runs once per interval, each run receiving that interval's start ([Backfill jobs](https://docs.databricks.com/aws/en/jobs/backfill-jobs), Nov 6, 2026). You override the date parameter with a backfill reference, for example `run_date` = `{{backfill.iso_date}}`. The rules:

- "The job must handle the parameters that you give it to process the correct data for the backfill date range." A job that reads `current_date()` cannot be backfilled.
- More than 100 runs cannot be started from one backfill: split the range or widen the interval.
- Backfill runs run in parallel up to the job's maximum concurrent runs, so raise it for the backfill if the runs are independent.
- "Backfills always run completely. You can't run a subset of tasks or tables in a backfill."
- Pipeline tasks are not parameterized and cannot run concurrently, so jobs with pipeline tasks backfill sequentially; for pipelines Databricks recommends the "append once" backfill flow instead (chapter 13).

!!! tip "In the interview"
    **"How do you backfill with a job?"** Design for it first: the job takes the period as a parameter (`run_date` defaulting to `{{job.trigger.time.iso_date}}`) and each task replaces exactly that period, so a backfill run and a normal run are the same code path. Then use **Run backfill** (or a loop of `run-now` calls with `job_parameters`) over the range, with max concurrent runs raised only if the periods do not write the same rows. For a Lakeflow pipeline (formerly Delta Live Tables; [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)), use a one-time append flow rather than a full refresh, which would rebuild everything.

## 15.13 Airflow, and when to use what
*Level: expert.*

Many companies already run **Apache Airflow**. Databricks documents how Airflow triggers Lakeflow Jobs through the open source Databricks provider ([Orchestrate Lakeflow Jobs with Apache Airflow](https://docs.databricks.com/aws/en/jobs/how-to/use-airflow-with-jobs), Nov 5, 2026), which needs Airflow 2.5.0 or later and is "not directly supported by Databricks". Two operators start jobs: `DatabricksRunNowOperator` runs an existing job (`jobs/run-now`), and `DatabricksSubmitRunOperator` submits a one-time run with its full specification (`jobs/runs/submit`). "Databricks recommends using the `DatabricksRunNowOperator` because it reduces duplication of job definitions, and job runs triggered with this operator can be found in the Jobs UI."

*Databricks only, not run here. Syntax from [Orchestrate Lakeflow Jobs with Apache Airflow](https://docs.databricks.com/aws/en/jobs/how-to/use-airflow-with-jobs).*
```python
from airflow import DAG
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator
from airflow.utils.dates import days_ago

with DAG("redrock_daily", start_date=days_ago(2), schedule_interval=None,
         default_args={"owner": "airflow"}) as dag:
    run_redrock = DatabricksRunNowOperator(
        task_id="run_redrock_daily",
        databricks_conn_id="databricks_default",
        job_id=JOB_ID,
    )
```

(This is the page's example with Red Rock names. It targets the Airflow version the page was tested with, 2.6.1; check the Airflow docs if you use a newer release.)

The page recommends OAuth or service principal tokens over a user's personal access token for the Airflow connection.

| Need | Use |
| --- | --- |
| Order datasets (bronze to gold tables) with incremental refresh, checkpoints, expectations | a Lakeflow pipeline (formerly Delta Live Tables) |
| Order tasks of any kind, branch, loop, notify, retry, schedule, repair | a Lakeflow job (formerly Databricks Jobs / Workflows) |
| Both: a pipeline plus tests, exports, a dbt run | a job whose tasks include a pipeline task |
| Cross-system DAGs (on-premises databases, other clouds, many tools) already in Airflow | Airflow calling `DatabricksRunNowOperator`, with the Databricks part still a Lakeflow job |

!!! tip "In the interview"
    **"Why not do everything in Airflow?"** You can, but Lakeflow Jobs knows the Databricks side better: task values, repair of only the failed tasks, table update and file arrival triggers, serverless compute, run-as service principals and system tables, all without another server to run. The common split is Airflow for the company-wide schedule and cross-system dependencies, triggering whole Lakeflow jobs (formerly Databricks Jobs, under the Workflows menu; [rename note](https://docs.databricks.com/aws/en/release-notes/product/2025/june)) by ID, so the Databricks job stays the unit you repair and monitor.

## 15.14 Practice questions
*Level: mixed.*

**Q1. Define job, task, task run and trigger in Lakeflow Jobs.**

??? success "Answer"
    A job is the resource that coordinates and schedules work; it holds tasks, trigger, parameters, notifications. A task is one unit of work in the job (a notebook, a pipeline, a SQL file); the tasks and their dependencies form a DAG. A job run executes the graph once, with one task run per task. A trigger starts runs: a schedule, file arrival, table update, continuous, model update or job completion; without one, the job runs only when started manually or through the API.

    **Why:** these are the three concepts on the Lakeflow Jobs overview page; interviewers check that you separate the definition (job) from an execution (run).

**Q2. An interviewer asks about "Workflows". What is it called now, and where is it in the UI?**

??? success "Answer"
    Lakeflow Jobs. The June 2025 release notes say "The product known as Databricks Jobs is now Lakeflow Jobs" and that the Workflows and Pipelines sidebar items were replaced by **Jobs & Pipelines**. Answer with both names: "Lakeflow Jobs, formerly Databricks Jobs, the Workflows menu."

    **Why:** many interviewers learned the product as Workflows; using only the new name can sound like a different product. Source: [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june).

**Q3. Pick the task type: (a) run a Lakeflow pipeline, (b) run a `.sql` file on a warehouse, (c) run one notebook for each of 20 tables, (d) run silver only if bronze loaded rows, (e) start the finance team's job when yours is done.**

??? success "Answer"
    (a) Pipeline task. (b) SQL task of type File, on a serverless or pro SQL warehouse. (c) For each task with the notebook as the nested task, the table name as `{{input}}`. (d) If/else condition task comparing a task value with 0, silver depending on its `true` outcome. (e) Run Job task (or, on the finance side, a job completion trigger, in Beta).

    **Why:** control flow (If/else, For each, Run Job) is built into Jobs; there is no need for a driver notebook that calls `dbutils.notebook.run()` in a loop.

**Q4. `data_tests` failed. A task `alert_team` depends on it with Run if "At least one failed"; a task `publish` depends on it with the default. What happens to each?**

??? success "Answer"
    `alert_team` runs (its condition is met). `publish` does not run and is marked `Upstream failed`. On a successful day it is the other way round: `publish` runs and `alert_team` is marked `Excluded`, which is not a failure.

    **Why:** the default is All succeeded; failure-handling conditions (At least one failed, All failed) mark the task `Excluded` when unmet, so they do not turn a good run red.

**Q5. In a chain A → B → C with default Run if, A is excluded by an If/else branch. What happens to B and C? And if D depends on A and on a task that succeeded?**

??? success "Answer"
    B is excluded because all its dependencies are excluded, and so is C: the exclusion cascades. D runs (with All succeeded), because an `Excluded` upstream task is treated as successful and D has another dependency that succeeded.

    **Why:** the run-if page: "If all of a task's dependencies are excluded, the task itself is also excluded", and "Upstream tasks with the `Excluded` result state are treated as successful".

**Q6. An If/else task compares `{{job.parameters.threshold}}` `==` `12` and the parameter is `12.0`. True or false? What about `>=`?**

??? success "Answer"
    `==` is false: `==` and `!=` compare as strings, and `"12.0"` is not `"12"`. `>=` is true, because `>`, `>=`, `<`, `<=` compare numerically.

    **Why:** stated on the If/else page with exactly this example. For numeric equality use `>=` and `<=` together, or make the producer write a canonical string.

**Q7. Can a For each task contain another For each task? How does the nested task get the current element?**

??? success "Answer"
    No: "You cannot add another `For each` task as the nested task." The nested task reads `{{input}}` (the whole element) or `{{input.<key>}}` (a field, when the inputs are JSON objects), usually as a task parameter such as `table: '{{input}}'`.

    **Why:** to loop over two dimensions, flatten the inputs into one array of objects, or have the nested task be a Run Job task whose job has its own loop.

**Q8. Your For each over 40 tables runs one iteration at a time. Why might that be, and what do you set?**

??? success "Answer"
    The iterations run up to the task's concurrency, and the UI page gives the default as 1. Set **Concurrency** (`concurrency` in YAML) explicitly, up to 100 per the Jobs API, and within what the compute and the source systems can take.

    **Why:** the bundle reference says that without `concurrency` "all iterations may run in parallel"; the UI page says the default is 1. When two pages disagree, set the value instead of relying on a default.

**Q9. Write the bronze notebook code that hands the number of new rows to the If/else task, and the operand the If/else task uses.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Use task values to pass information between tasks](https://docs.databricks.com/aws/en/jobs/task-values).*
    ```python
    new_rows = spark.read.table("shop.bronze.orders").where(
        f"ingest_date = '{dbutils.widgets.get('run_date')}'").count()
    dbutils.jobs.taskValues.set(key="new_rows", value=new_rows)
    ```
    Left operand `{{tasks.bronze_orders.values.new_rows}}`, operator `>` (`GREATER_THAN`), right operand `0`.

    **Why:** task values are set from Python notebooks only; the value must be JSON and at most 48 KiB. Reading it through a dynamic value reference works in any task type and keeps the upstream task name out of downstream code.

**Q10. A notebook task has the parameter `run_date` = `{{job.parameter.run_date}}`. What happens? And with `{{jobs.parameters.run_date}}`?**

??? success "Answer"
    `job` is a known namespace, so the invalid `job.parameter...` reference shows an error, like the page's `{{job.notebook_url}}` example. `jobs.parameters...` is not a known namespace, so it is "silently ignored and treated as literal strings": the notebook receives the text `{{jobs.parameters.run_date}}`. The correct reference is `{{job.parameters.run_date}}`.

    **Why:** the silent case is the dangerous one, because the job succeeds while filtering on a nonsense date. Check the resolved parameters on the run page.

**Q11. The job has a parameter `env=prod`; a notebook task also defines `env=dev`. Which value does the notebook see? And a Python script task?**

??? success "Answer"
    The notebook sees `prod`: job parameters are pushed down to key-value tasks and take precedence over a task parameter with the same key. A Python script task takes a JSON array of arguments and gets no automatic push-down; it sees the job parameter only if its argument list references `{{job.parameters.env}}`.

    **Why:** both rules are on the job parameters page; the UI warns when a task parameter key matches a job parameter.

**Q12. Write the Quartz cron expressions for: every day at 02:00; every 15 minutes; 06:30 Monday to Friday. Why does `0 2 * * *` fail?**

??? success "Answer"
    `0 0 2 * * ?`; `0 */15 * * * ?`; `0 30 6 ? * MON-FRI`. Quartz has seconds as its first field and needs six fields, with `?` ("no specific value") in either day-of-month or day-of-week. `0 2 * * *` is a five-field Unix cron and is not valid Quartz syntax.

    **Why:** the Jobs schedule uses Quartz cron syntax (Run jobs on a schedule page; field list from the Quartz `CronExpression` documentation). Always set `timezone_id` too.

**Q13. An hourly job scheduled in `America/Toronto` missed a run on the night the clocks changed. Bug?**

??? success "Answer"
    Expected behavior. With a time zone that observes daylight saving time, "an hourly job is skipped or might appear to be delayed by an hour or two" when daylight saving time begins or ends. Use UTC for jobs that must run every absolute hour.

    **Why:** stated on the schedule page. Business-hour jobs can stay in local time if a missed or doubled hour is acceptable.

**Q14. Files land in a volume in bursts of 30 files over about 20 seconds, every few minutes. With a file arrival trigger, the job starts several runs per burst. Fix it.**

??? success "Answer"
    Set **Wait after last change in seconds** (for example 60): each new file resets the timer, so the run starts once the burst is complete. Add **Minimum time between triggers** if you also want to cap the frequency. Process the files with Auto Loader (`availableNow`), so each run picks up exactly the files not yet loaded.

    **Why:** the file arrival page describes these as debouncing and cooldown; the API's minimum for both is 60 seconds.

**Q15. A file arrival trigger on `/Volumes/shop/bronze/landing/` stopped firing when the upstream system started overwriting `orders_latest.json` every hour. Why?**

??? success "Answer"
    "Only new files trigger runs. Overwriting an existing file with a file of the same name does not trigger a run." Ask the upstream to write a new, uniquely named file per batch (which also makes bronze replayable), or use a schedule.

    **Why:** a listed limitation of file arrival triggers.

**Q16. The gold job should start when both `shop.silver.orders` and `shop.silver.customers` have new commits. Which trigger, and what can make it silently never run?**

??? success "Answer"
    A table update trigger on both tables with **All tables are updated** (`ALL_UPDATED`). It fails to evaluate (and the job does not run) if the job's **Run as** principal lacks `SELECT` on the tables (and `USE CATALOG`, `USE SCHEMA`). Add failure notifications: the page says to configure notifications on job failure to hear about failed trigger evaluations.

    **Why:** the trigger reads each table's metadata and history as the Run as principal. Limits: up to 25 tables per trigger, more than 10 only with file events.

**Q17. Name three restrictions of continuous jobs.**

??? success "Answer"
    Only one running instance; no task dependencies; no retry policies (the job is retried with exponential backoff instead, and failed tasks are retried when Task retry mode is On failure). Also: on serverless compute only bounded streaming triggers such as `Trigger.AvailableNow` work, and the gap between runs should be under 60 seconds.

    **Why:** all from the Run jobs continuously page. For low-latency streaming on serverless, the page points to a continuous pipeline run by a continuous job.

**Q18. A job scheduled every 10 minutes sometimes takes 15. What happens to the run that fires while the previous one is still running? How do you change it?**

??? success "Answer"
    With the default maximum of 1 concurrent run, the new run is skipped, unless queueing is enabled, in which case it waits (up to 48 hours) and starts when the first run ends. Queueing is on by default for jobs created in the UI after April 15, 2024, and the API reference lists `queue.enabled` with default `true` (whether a job created through the API with no `queue` block gets queueing is not verified, so set it). Raising max concurrent runs lets runs overlap, which is only safe if they do not write the same data.

    **Why:** the configure-job page; an overlapping MERGE into the same table risks write conflicts.

**Q19. A task has 3 retries and a 20-minute timeout. What is the longest it can run in total, roughly? Does a timeout trigger a retry?**

??? success "Answer"
    The timeout applies to each attempt, so up to four attempts of 20 minutes each (plus retry intervals). A timeout is retried only if `retry_on_timeout` is true; its default is false.

    **Why:** "If you configure both **Timeout** and **Retries**, the timeout applies to each retry" (configure-task page); `retry_on_timeout` default from the bundle task reference and the API.

**Q20. Your on-call team gets a job failure email but did not hear about a task that failed twice before succeeding on the third attempt. Is that expected?**

??? success "Answer"
    Yes. "Job-level notifications aren't sent when failed tasks are retried." To hear about each failed attempt, add task-level failure notifications; to hear only when retries are exhausted, use **Mute notifications until the last retry**.

    **Why:** the notifications page. Flapping tasks are worth knowing about: query `job_task_run_timeline` for tasks with several finished rows (`result_state IS NOT NULL`, since runs over an hour are sliced into several rows) per `job_run_id` and `task_key`.

**Q21. A serverless job task sends a confirmation email to each customer. Users report duplicate emails although `max_retries` is 0. Why?**

??? success "Answer"
    Serverless auto-optimization "retries failed tasks" and is enabled by default, in addition to your retry policy. For an at-most-once task, disable it (uncheck the auto-optimization box in the retry dialog, or `disable_auto_optimization: true`), and make the task record what it already sent so a rerun skips it.

    **Why:** the serverless jobs page: "if you have workloads that must be executed at most once, for example, jobs that are not idempotent, you can turn off auto-optimization".

**Q22. What is the difference between a duration warning and a timeout? Write the health rule for "warn after one hour".**

??? success "Answer"
    A warning only emits an event (for a notification) when the run is slower than expected; a timeout stops the run and marks it Timed Out.

    *Databricks only, not run here. Syntax from [Declarative Automation Bundles resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources).*
    ```yaml
    health:
      rules:
        - metric: RUN_DURATION_SECONDS
          op: GREATER_THAN
          value: 3600
    email_notifications:
      on_duration_warning_threshold_exceeded:
        - data-oncall@example.com
    ```

    **Why:** a warning catches the job that will still finish but will miss the 7:00 report; a timeout protects against hung tasks.

**Q23. What does a repair run re-run, with which code and settings, and what can it not do?**

??? success "Answer"
    The unsuccessful tasks (failed, canceled, upstream failed and so on) and the tasks that depend on them; successful tasks keep their results. It uses the current job and task settings, so a fixed notebook or a bigger cluster applies; parameters can be overridden in the dialog. It cannot repair a single-task job (run it again instead), and it does not make tasks idempotent.

    **Why:** the repair page. The repair stays part of the original run, so history and duration show the whole recovery.

**Q24. After a repair, `gold.daily_sales` shows twice the revenue for March 1. What happened, and how do you fix the job and the table?**

??? success "Answer"
    The gold task appended (`INSERT INTO`) before it failed, or appended successfully while a later task failed and the repair (or a retry) ran it again. The run-here output in 15.8 shows the effect: two identical rows for 2026-03-01. Fix the task to replace the slice for its `run_date` (`INSERT INTO ... REPLACE WHERE order_date = ...` or `replaceWhere`, or `MERGE` on the key), then rerun the day once: the replace removes the duplicate.

    **Why:** "Lakeflow Jobs doesn't make tasks idempotent, so if a task wrote part of its output before it failed, re-running it can duplicate that data."

**Q25. Airflow calls `run-now` for your job, the HTTP call times out, Airflow retries, and two job runs start. How do you prevent that?**

??? success "Answer"
    Send an `idempotency_token` (for example the job name plus the logical date) with `run-now`. "If a run with the provided token already exists, the request does not create a new run but returns the ID of the existing run instead." Keep max concurrent runs at 1 as a second guard.

    **Why:** the token deduplicates run requests (at most 64 characters, per the API page). It does not deduplicate data written by tasks.

**Q26. The job was created by a data engineer who has left; it now fails with permission errors. Why, and what is the long-term fix?**

??? success "Answer"
    By default the creator is the job's owner and its **Run as** identity, so the tasks used that person's privileges. When the account was disabled or lost grants, the job lost them too. Fix: set **Run as** to a service principal with exactly the grants the job needs (and have an admin reassign the owner).

    **Why:** the privileges page recommends a service principal "so that jobs do not break when the owner leaves or has changed privileges", and it lets you restrict write access to production data to that principal.

**Q27. An analyst with CAN MANAGE RUN clicks Run now. Whose data permissions does the run use? Can the analyst change the schedule?**

??? success "Answer"
    The Run as identity's, not the analyst's ("Jobs triggered through **Run Now** assume the permissions of the **Run as** user"). The analyst cannot change the schedule: CAN MANAGE RUN allows triggering and canceling runs; editing the definition and pausing schedules needs CAN MANAGE.

    **Why:** this is why job permissions matter: CAN MANAGE RUN lets someone run a job that reads data they cannot read themselves.

**Q28. When is a shared job cluster a good idea, and what are its traps?**

??? success "Answer"
    When several classic-compute tasks run one after another, sharing one job cluster avoids a start-up per task. Traps: it stays on (and billed) while tasks that do not use it run; it is scoped to one run, not shared across jobs or runs; libraries must be declared on tasks, not on the shared cluster; tasks share the driver JVM, so Scala singletons and loaded libraries carry over between tasks; a repair creates a new cluster (`_v1`).

    **Why:** all from the Configure compute for jobs and repair pages. On serverless you do not manage this at all.

**Q29. Give three reasons not to run a production job on the team's all-purpose cluster, and one case where it is acceptable.**

??? success "Answer"
    All-purpose compute is billed at a different rate than jobs compute; it does not terminate when the run ends; it is shared, so jobs compete with interactive users. Acceptable while iterating on a new job, or for very short jobs that run very often, where start-up time dominates (weigh the idle cost).

    **Why:** the classic compute for jobs page lists these reasons and these exceptions; it recommends serverless as the substitute for most such cases.

**Q30. Write a query that lists last week's failed runs of all jobs with their names. What two pitfalls does the system table page warn about?**

??? success "Answer"
    See the query in section 15.11 (join `job_run_timeline` with the latest row per job from `jobs`, filter `result_state`). Pitfalls: `jobs` is SCD Type 2, so you must take the latest row per `workspace_id, job_id` (and exclude deleted jobs if needed); runs longer than an hour are split into several timeline rows and `result_state` is set only on the last one, so filter `result_state IS NOT NULL` or `IN (...)` before counting.

    **Why:** without the dedup, a job renamed three times appears three times; without the filter, long runs are counted several times.

**Q31. Write the YAML for a task `log_no_data` that runs only when the condition task `has_new_orders` is false, and a task `cleanup` that runs after `data_tests` whatever happens.**

??? success "Answer"
    *Databricks only, not run here. Syntax from [Add tasks to jobs in Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/job-task-types).*
    ```yaml
    - task_key: log_no_data
      depends_on:
        - task_key: has_new_orders
          outcome: 'false'
      notebook_task:
        notebook_path: ../src/log_no_data.py
    - task_key: cleanup
      depends_on:
        - task_key: data_tests
      run_if: ALL_DONE
      notebook_task:
        notebook_path: ../src/cleanup.py
    ```

    **Why:** `outcome` "can be specified only for `condition_task`" dependencies; `ALL_DONE` runs after all dependencies finish regardless of their result.

**Q32. Your team built 15 jobs in the UI. How do you move them to Git and deploy them to dev and prod?**

??? success "Answer"
    Create a bundle, run `databricks bundle generate job` for each existing job to get its YAML, add targets (dev in development mode, prod with `run_as` a service principal), then `databricks bundle validate`, `deploy --target ...` and `run`, ideally from CI. The UI's "Switch to code version (YAML)" shows a job's YAML too.

    **Why:** Declarative Automation Bundles (formerly Databricks Asset Bundles; [rename page](https://docs.databricks.com/aws/en/dev-tools/bundles/)) are the documented infrastructure-as-code path for jobs; chapter 16 covers the CI/CD side.

**Q33. Hourly processing failed for March 9 and 10. Describe the backfill, and what the job must already support.**

??? success "Answer"
    Use **Run backfill** on the job: range March 9 00:00 to March 11 00:00, interval 1 hour, which creates 48 runs, each with its hour (for example `run_hour` = `{{backfill.iso_datetime}}`). Raise max concurrent runs if the hours are independent. The job must take the period as a parameter and replace exactly that period's output; a job that uses "now" cannot be backfilled. More than 100 runs in one backfill is not allowed; pipeline tasks run sequentially and are not parameterized.

    **Why:** the Backfill jobs page uses this same two-day, 48-run example and lists the limits.

**Q34. A job contains a pipeline task. Can its backfill run in parallel? What does Databricks recommend for backfilling pipelines?**

??? success "Answer"
    No: pipeline tasks cannot run concurrently, so jobs with pipeline tasks run sequentially, and the pipeline runs as-is (not parameterized). For pipelines, Databricks recommends the pipeline's own append-once backfill flow.

    **Why:** listed on the Backfill jobs page; see chapter 13 for flows in Lakeflow pipelines (formerly Delta Live Tables; [rename page](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)).

**Q35. A teammate wants to wrap the whole medallion flow in one notebook that calls `dbutils.notebook.run()` for each step, scheduled as a single-task job. Argue for a multi-task job instead.**

??? success "Answer"
    A multi-task job gives a visible DAG, parallel branches, per-task retries and timeouts, per-task compute, task values, Run if conditions, repair of only the failed steps (repair needs two or more tasks), per-task history in system tables and per-task notifications. The driver notebook hides all of that inside one task: one failure means rerunning everything or writing your own restart logic.

    **Why:** chapter 2 quotes the docs: `dbutils.notebook.run()` is for cases "Jobs cannot support", such as dynamic, metadata-driven runs; a loop over a list of tables fits a For each task instead.

**Q36. Rerun only `silver_orders` and everything after it, from the CLI, without touching bronze.**

??? success "Answer"
    For a bundle job: `databricks bundle run redrock_daily --only silver_orders+`. Through the API: `run-now` with `"only": ["silver_orders+"]`. Note that `has_new_orders` will not run, so check how the run treats the condition: the safe choice is to run from the first task you need, or use a repair of the failed run, which keeps the earlier results.

    **Why:** the run-now page defines `task+` (task and downstream) and `+task` (task and upstream). Whether a skipped upstream condition task excludes its dependents in such a partial run is not stated on the page (not verified), which is one more reason to prefer repair for recovery.

**Q37. When would you choose Airflow over Lakeflow Jobs, and how do they work together?**

??? success "Answer"
    When the company already schedules many systems in Airflow and the Databricks work is one step in a larger cross-system DAG. Airflow then triggers the Databricks job with `DatabricksRunNowOperator` (recommended over `DatabricksSubmitRunOperator`), and the Lakeflow job keeps the Databricks-side graph, retries, repair and monitoring.

    **Why:** the Airflow page recommends run-now "because it reduces duplication of job definitions, and job runs triggered with this operator can be found in the Jobs UI". The provider is open source and not directly supported by Databricks.

**Q38. The Red Rock job runs Run Job tasks: `redrock_daily` calls `redrock_exports`, which calls `redrock_finance`, which calls `redrock_audit`, which calls `redrock_archive`. Any concern?**

??? success "Answer"
    Yes: Databricks "does not support jobs with circular dependencies or that nest more than three `Run Job` tasks" and "might block deploying jobs with this pattern in a future release". Flatten the chain, for example one parent job with Run Job tasks for each child, or job completion triggers.

    **Why:** deep chains are hard to repair and monitor; each child is a separate job run with its own history.

**Q39. Which compute would you choose for each Red Rock task: bronze notebook, silver and gold notebooks, `data_tests` as a SQL file, a dbt project?**

??? success "Answer"
    Notebooks: serverless compute for jobs (the default when the workspace has Unity Catalog and serverless), standard performance mode for the nightly batch if a few minutes of start-up are acceptable. SQL file: a serverless SQL warehouse. dbt: a serverless SQL warehouse for the SQL dbt generates. Classic job compute only where serverless is not supported (for example Spark Submit) or a needed configuration is not allowed there.

    **Why:** the recommended-compute table on Configure compute for jobs; chapter 6 has the serverless limitations.

**Q40. "What is the difference between Lakeflow Jobs and Lakeflow pipelines, and when do you use both?"**

??? success "Answer"
    Lakeflow Jobs (formerly Databricks Jobs / Workflows) orchestrate tasks procedurally: you define the order, branches, retries and schedule. Lakeflow pipelines (formerly Delta Live Tables) are declarative: you define tables and queries, and the pipeline works out the dependency order, incremental processing, checkpoints and expectations. Use a pipeline for the bronze-silver-gold datasets, and a job to run that pipeline as a task together with the work around it (tests, exports, notifications, dbt), on a trigger.

    **Why:** the pipeline task page: "Lakeflow Jobs provides a procedural approach to defining relationships between tasks. Lakeflow pipelines provide a declarative approach to defining relationships between datasets and transformations." Rename sources: [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) and [What happened to DLT](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt).

## Sources

- [Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/) (last updated Nov 5, 2026)
- [June 2025 (Databricks platform release notes)](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [Configure and edit Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/configure-job) (last updated Nov 5, 2026)
- [Configure and edit tasks in Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/configure-task) (last updated Nov 5, 2026)
- [Configure task dependencies](https://docs.databricks.com/aws/en/jobs/run-if) (last updated Nov 2, 2026)
- [Add branching logic to a job with the If/else task](https://docs.databricks.com/aws/en/jobs/tasks/if-else) (last updated Sep 11, 2026)
- [Use a For each task to run another task in a loop](https://docs.databricks.com/aws/en/jobs/tasks/for-each) (last updated Nov 5, 2026)
- [Run Job task for jobs](https://docs.databricks.com/aws/en/jobs/tasks/run-job) (last updated Nov 5, 2026)
- [Pipeline task for jobs](https://docs.databricks.com/aws/en/jobs/tasks/pipeline) (last updated Nov 5, 2026)
- [SQL task for jobs](https://docs.databricks.com/aws/en/jobs/tasks/sql) (last updated Nov 3, 2026)
- [dbt task for jobs](https://docs.databricks.com/aws/en/jobs/tasks/dbt) (last updated Sep 11, 2026)
- [Configure job parameters](https://docs.databricks.com/aws/en/jobs/job-parameters) (last updated Nov 5, 2026)
- [Configure task parameters](https://docs.databricks.com/aws/en/jobs/task-parameters) (last updated Nov 5, 2026)
- [Access parameter values from a task](https://docs.databricks.com/aws/en/jobs/parameter-use) (last updated Nov 5, 2026)
- [Dynamic value references](https://docs.databricks.com/aws/en/jobs/dynamic-value-references) (last updated Nov 6, 2026)
- [Use task values to pass information between tasks](https://docs.databricks.com/aws/en/jobs/task-values) (last updated Nov 5, 2026)
- [Automate jobs with schedules and triggers](https://docs.databricks.com/aws/en/jobs/triggers) (last updated Nov 6, 2026)
- [Run jobs on a schedule](https://docs.databricks.com/aws/en/jobs/scheduled) (last updated Nov 6, 2026)
- [Trigger jobs when new files arrive](https://docs.databricks.com/aws/en/jobs/file-arrival-triggers) (last updated Nov 6, 2026)
- [Trigger jobs when source tables are updated](https://docs.databricks.com/aws/en/jobs/trigger-table-update) (last updated Nov 6, 2026)
- [Run jobs continuously](https://docs.databricks.com/aws/en/jobs/continuous) (last updated Nov 6, 2026)
- [Trigger a single job run](https://docs.databricks.com/aws/en/jobs/run-now) (last updated Sep 11, 2026)
- [Configure compute for jobs](https://docs.databricks.com/aws/en/jobs/compute) (last updated Nov 9, 2026)
- [Run your Lakeflow Jobs with serverless compute for workflows](https://docs.databricks.com/aws/en/jobs/run-serverless-jobs) (last updated Nov 6, 2026)
- [Configure classic compute for Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/run-classic-jobs) (last updated Nov 6, 2026)
- [Add notifications on a job](https://docs.databricks.com/aws/en/jobs/notifications) (last updated Nov 6, 2026)
- [Troubleshoot and repair job failures](https://docs.databricks.com/aws/en/jobs/repair-job-failures) (last updated Nov 5, 2026)
- [Manage identities, permissions, and privileges for Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/privileges) (last updated Nov 5, 2026)
- [Backfill jobs](https://docs.databricks.com/aws/en/jobs/backfill-jobs) (last updated Nov 6, 2026)
- [Jobs system table reference](https://docs.databricks.com/aws/en/admin/system-tables/jobs) (last updated Nov 6, 2026)
- [Orchestrate Lakeflow Jobs with Apache Airflow](https://docs.databricks.com/aws/en/jobs/how-to/use-airflow-with-jobs) (last updated Nov 5, 2026)
- [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (last updated Nov 5, 2026)
- [Develop a job with Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/jobs-tutorial) (last updated Nov 5, 2026)
- [Declarative Automation Bundles resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources) (last updated Nov 10, 2026)
- [Add tasks to jobs in Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/job-task-types) (last updated Nov 6, 2026)
- [Bundle configuration examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples) (last updated Oct 29, 2026)
- [Specify a run identity for a Declarative Automation Bundles workflow](https://docs.databricks.com/aws/en/dev-tools/bundles/run-as) (last updated Oct 7, 2026)
- [`jobs` command group](https://docs.databricks.com/aws/en/dev-tools/cli/reference/jobs-commands) (last updated Sep 11, 2026)
- Jobs REST API 2.2 reference: [Create a new job](https://docs.databricks.com/api/workspace/jobs/create), [Trigger a new job run](https://docs.databricks.com/api/workspace/jobs/runnow), [Repair a job run](https://docs.databricks.com/api/workspace/jobs/repairrun) (the API reference shows no last-updated date; read Nov 11, 2026)
- [Quartz `CronExpression` source and documentation](https://github.com/quartz-scheduler/quartz/blob/main/quartz/src/main/java/org/quartz/CronExpression.java) (GitHub, main branch, read Nov 11, 2026; the quartz-scheduler.org tutorial that Databricks links to could not be reached from here)
