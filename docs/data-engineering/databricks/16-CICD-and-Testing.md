# 16. CI/CD and testing

*A Red Rock Supply engineer edits the silver notebook in production at 5 p.m., the 2 a.m. run duplicates every
order, and the finance dashboard is wrong by morning. This chapter is about never doing that. It covers how a
Databricks project moves from a developer's branch to production: Git, Declarative Automation Bundles (formerly
Databricks Asset Bundles), dev, staging and prod targets with one catalog each, service principals and secret-free
authentication for CI, and a GitHub Actions workflow. It then covers testing: a small Python package of silver
transformations with pytest unit tests that ran here on Apache Spark 4.2 with Delta Lake 4.4.1, including a `MERGE`
idempotency test and a schema test, plus data tests and integration tests. Interviewers ask "how do you test a Spark
job?" and "how do you deploy to production safely?" in almost every data engineering loop.*

!!! abstract "In this chapter"
    **You will learn:**

    - why data pipelines need CI/CD, and what is different from application code (state, reruns, data)
    - the Databricks flow: Git folders and short-lived branches, dev, staging and prod workspaces, one catalog per
      environment, promoting code and never data
    - Declarative Automation Bundles: `databricks.yml`, targets, variables and substitutions, `run_as`, and the
      `bundle validate / plan / deploy / run / destroy` commands
    - what development mode and production mode change, and what a bundle's identity is
    - authentication for CI: service principals, OAuth machine-to-machine, workload identity federation
    - a GitHub Actions workflow that tests, validates and deploys a bundle with `databricks/setup-cli`
    - the testing pyramid for data pipelines: unit tests, bundle validation, integration tests, data tests
    - pytest with a local SparkSession: fixtures, `assertDataFrameEqual`, `assertSchemaEqual`, a Delta `MERGE`
      rerun test, and what a failing test tells you
    - Databricks Connect for running the same tests against a workspace

    **You need:** [2. Workspace tour](02-Workspace-Tour.md) (Git folders, the CLI, Databricks Connect),
    [9. Building silver](09-Building-Silver.md) (the transformations tested here) and
    [15. Lakeflow Jobs](15-Lakeflow-Jobs.md) (the job the bundle deploys). Generic `MERGE`:
    [Insert, update, delete, merge](../../databases/sql/17-Insert-Update-Delete-Merge.md).

    **Levels:** sections 16.1 to 16.3 beginner, 16.4 to 16.7 intermediate, 16.8 and 16.9 expert.

**About the examples.** The Python package, its tests and the SQL data tests ran here on Apache Spark 4.2.0 with
Delta Lake 4.4.1 and pytest 9.2.0; the code and the captured output are in `src/ch16/`. Bundles, the Databricks CLI,
GitHub Actions and Databricks Connect need a workspace or a GitHub repository, so those blocks are labeled
"Databricks only, not run here" and copy their syntax from the page named in the label.

## 16.1 Why data pipelines need CI/CD

*Level: beginner.*

Databricks defines CI/CD as "the process of developing and delivering software in short, frequent cycles through
the use of automation pipelines", and says it "is becoming increasingly necessary in data engineering and data
science" ([CI/CD on Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/)). **Continuous integration**
(CI) means every change is merged often and checked automatically (tests, validation). **Continuous delivery**
(CD) means the checked change is deployed by automation, not by a person copying files.

Data pipelines need this more than most code, for three reasons:

1. **A pipeline has state.** A web page with a bug is fixed by deploying the old version. A silver job with a bug
   has already written wrong rows into `shop.silver.orders`, and gold has already aggregated them. Rolling back the
   code does not roll back the data. Catching the bug before it reaches production is worth much more.
2. **Pipelines rerun.** Retries, repair runs and backfills run the same code on the same input again. A change
   that turns a `MERGE` into an append passes a quick manual check and doubles the data on the first rerun. Only a
   test that runs the code twice finds it (16.7).
3. **The job definition is code too.** The schedule, the compute, the parameters, the run-as identity and the
   permissions decide what runs at 2 a.m. If they are clicked together in the UI, nobody can review them, compare
   them across environments, or restore them. The Databricks guidance puts it bluntly: "if something isn't in
   version control, it doesn't exist" ([Developer best practices on
   Databricks](https://docs.databricks.com/aws/en/developers/best-practices)).

The CI/CD page lists the flow Databricks recommends: **version** (Git), **code** (notebooks or an IDE), **build**
(bundle artifacts), **deploy** (bundles from a CI tool such as GitHub Actions), **test** ("Use tools like pytest to
test your integrations"), **run** (`databricks bundle run`) and **monitor**. It names the principles behind them:
"version all files and unify asset management, define infrastructure as code, isolate environments, automate
testing, and monitor and automate rollbacks."

| Tool | What it is for |
| --- | --- |
| Declarative Automation Bundles | "the recommended approach to CI/CD on Databricks": jobs, pipelines and code deployed as one unit |
| Databricks Terraform provider | Workspaces and cloud infrastructure. "Use Terraform only for external resources" and admin actions; bundles for all other Databricks resources ([best practices](https://docs.databricks.com/aws/en/developers/best-practices)) |
| Git folders (production Git folder) | Deploys only code files; job configurations stay outside source control |
| GitHub Actions, Azure DevOps, Jenkins | The CI system that runs tests and calls the Databricks CLI |

## 16.2 The workflow: branches, environments and catalogs

*Level: beginner.*

### Git and Git folders

[Chapter 2](02-Workspace-Tour.md) showed Git folders (formerly
[Repos](https://docs.databricks.com/aws/en/repos/what-happened-repos)): each developer clones the project into their
own Git folder, works on a branch, commits and pushes, and opens the pull request in GitHub. Databricks recommends
"a single repository for both code and bundle configuration" and "a trunk-based branching strategy to minimize merge
conflicts and ensure the main branch is always in a deployable state" ([CI/CD workflows on
Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/flows)). In trunk-based development there is one
long-lived branch, `main`; feature branches live for days, not months. The best-practices page describes the loop:

1. Develop locally or in the workspace and deploy to a development workspace to test changes.
2. Create a short-lived feature branch and sync your changes to it regularly.
3. When testing is finished, merge the feature branch into `main`.
4. "CI/CD automatically deploys the main branch to a staging workspace and automated tests are triggered."
5. "When the staging tests and checks pass, CI/CD deploys the main branch to a production workspace."

A **production Git folder** (an admin-owned folder that "should be updated only by automation when PRs are
merged") is the alternative when you can only deploy code. Its limit: "Configurations for jobs or pipelines that
run assets in the Git folder ... are not in source control"
([CI/CD with Databricks Git folders](https://docs.databricks.com/aws/en/repos/ci-cd),
[CI/CD on Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/)). Bundles put both in Git.

### Environments: workspaces and catalogs

An **environment** is a separate place to run the same code: development for trying things, staging for checking
the merged result on realistic data, production for the real thing. The best-practices page sizes it by team:
"Small teams (up to 5 data engineers): Start with two workspaces (development and production)"; "Growing teams
(5+ data engineers): Move to three workspaces (development, staging, and production)", with staging "functionally
representative of production". Regulated industries physically isolate workspaces and cloud accounts.

For data, the same page says:

- "Use a single Unity Catalog metastore and create separate catalogs for dev, staging (if applicable), and
  production, mirroring your workspace layout."
- "Use personal schemas for individual developers for development and staging (non-production) catalogs."
- "Bind the production catalog in `ISOLATED` mode to the production workspace only", so that "production data is
  unreachable from development or staging environments, even if an identity is misconfigured."

For Red Rock Supply that gives:

| | Dev | Staging | Prod |
| --- | --- | --- | --- |
| Workspace | dev | staging | prod |
| Catalog | `shop_dev` | `shop_staging` | `shop` (bound to prod only) |
| Bundle target | `dev`, development mode | `staging`, production mode | `prod`, production mode |
| Who deploys | each developer, own login | CI, service principal | CI, service principal |
| Jobs run as | the developer | a staging service principal | a prod service principal |

(The rest of this book writes `shop.silver.orders`: that is the production catalog.)

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="One Git repository is deployed with bundle deploy to three targets. Dev workspace, development mode, catalog shop_dev, deployed by each developer. Staging workspace, production mode, catalog shop_staging, deployed by CI after merge. Prod workspace, production mode, catalog shop bound to prod, deployed by CI after staging passes. The same commit is promoted; data is not copied.">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="20" y="14" width="600" height="44" rx="6"/>
<rect x="20" y="104" width="180" height="132" rx="6"/>
<rect x="230" y="104" width="180" height="132" rx="6"/>
<rect x="440" y="104" width="180" height="132" rx="6"/>
<line x1="110" y1="58" x2="110" y2="96"/>
<line x1="320" y1="58" x2="320" y2="96"/>
<line x1="530" y1="58" x2="530" y2="96"/>
<line x1="110" y1="258" x2="522" y2="258" stroke-dasharray="5 4"/>
</g>
<g fill="currentColor">
<polygon points="110,104 105,94 115,94"/>
<polygon points="320,104 315,94 325,94"/>
<polygon points="530,104 525,94 535,94"/>
<polygon points="530,258 520,253 520,263"/>
</g>
<g fill="currentColor" font-size="14" text-anchor="middle">
<text x="320" y="41">Git repository: code + databricks.yml + tests, one branch: main</text>
<text x="110" y="128">dev workspace</text>
<text x="320" y="128">staging workspace</text>
<text x="530" y="128">prod workspace</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="110" y="152">mode: development</text>
<text x="110" y="174">catalog: shop_dev</text>
<text x="110" y="196">personal schemas</text>
<text x="110" y="218">deployed by: you</text>
<text x="320" y="152">mode: production</text>
<text x="320" y="174">catalog: shop_staging</text>
<text x="320" y="196">integration tests</text>
<text x="320" y="218">deployed by: CI</text>
<text x="530" y="152">mode: production</text>
<text x="530" y="174">catalog: shop</text>
<text x="530" y="196">bound to prod only</text>
<text x="530" y="218">deployed by: CI</text>
<text x="320" y="284">the same commit is promoted; data is never copied between catalogs</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="end">
<text x="102" y="84">deploy -t dev</text>
<text x="312" y="84">deploy -t staging</text>
<text x="522" y="84">deploy -t prod</text>
</g>
</svg>
<figcaption>Figure 16.1. Dev, staging and prod for Red Rock Supply. One repository, one bundle with three targets.
Only the target settings differ (workspace, catalog, mode, run-as identity); the code and job definitions are the
same commit in every environment.</figcaption>
</figure>

### Promote code, not data

**Promoting code** means the same commit moves from dev to staging to prod, and each environment runs it against
its own data. Staging is fed from its own sources (or a sample of them), never by copying production tables into a
lower catalog, and never by copying tables "up" from dev to prod. Why:

- Production tables are rebuilt by production code from production sources, so they always match the code that
  is deployed. A table copied up from dev was built by whatever code a developer ran that day.
- Lower environments do not hold production data, so their weaker access rules do not leak it. The `ISOLATED`
  binding above enforces this.
- A failed deployment is fixed by deploying the previous commit; nothing has to be reconciled by hand.

This is a design principle, not a product feature; the Databricks page states it as "Treat 'all tests pass on the
main branch and in staging' as the gate for promoting artifacts to production."

!!! tip "In the interview"
    **"How do you separate dev, staging and prod on Databricks?"** Separate workspaces (two for a small team, three
    once the team grows), one Unity Catalog metastore, and one catalog per environment, with the production catalog
    bound in `ISOLATED` mode to the production workspace. One bundle (Declarative Automation Bundles, formerly
    [Databricks Asset Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/)) has a
    target per environment; only the target's variables, such as the catalog name, differ. We promote the same
    commit through the environments; we never copy data between them.

## 16.3 Declarative Automation Bundles

*Level: beginner.*

Declarative Automation Bundles are "formerly known as Databricks Asset Bundles"
([What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/)); interviewers
still say Asset Bundles or DABs. A bundle is a folder of source files plus YAML that describes the Databricks
resources the code needs: "Ultimately a bundle is an end-to-end definition of a project, including how the project
should be structured, tested, and deployed." It contains workspace configuration, source files (notebooks, Python
files), resource definitions (Lakeflow Jobs, formerly Databricks Jobs, see the
[June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june); Lakeflow pipelines,
formerly [Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt); dashboards, model
serving endpoints, MLflow experiments and models) and unit and integration tests. Bundles are "a feature of the Databricks CLI"; the page
requires CLI "version v0.218.0 or above" and workspace files enabled.

You start from a template (`databricks bundle init` offers `default-python` and others) or write the files by hand.
The Red Rock Supply silver bundle looks like this:

```text
redrock_silver/
  databricks.yml            bundle name, variables, targets
  resources/
    silver_job.yml          the Lakeflow job
  src/
    load_silver.ipynb       thin notebook: read parameters, call the package
    check_silver.ipynb      data tests after the load
    redrock/
      transforms.py         pure DataFrame functions (16.7)
      writers.py            the MERGE into silver
  tests/                    pytest unit tests (run in CI)
  conftest.py               the local SparkSession fixture
  pyproject.toml
```

### databricks.yml

*Databricks only, not run here. Syntax from [the GitHub Actions bundle example](https://docs.databricks.com/aws/en/dev-tools/ci-cd/github), [Deployment modes](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes), [Specify a run identity](https://docs.databricks.com/aws/en/dev-tools/bundles/run-as) and the [Configuration reference](https://docs.databricks.com/aws/en/dev-tools/bundles/reference).*

```yaml
bundle:
  name: redrock_silver

include:
  - resources/*.yml

variables:
  catalog:
    description: The Unity Catalog catalog for this environment

targets:
  dev:
    mode: development
    default: true
    workspace:
      host: https://<dev-workspace-url>
    variables:
      catalog: shop_dev

  staging:
    mode: production
    workspace:
      host: https://<staging-workspace-url>
    variables:
      catalog: shop_staging
    run_as:
      service_principal_name: <staging-runner-application-id>

  prod:
    mode: production
    git:
      branch: main
    workspace:
      host: https://<prod-workspace-url>
    variables:
      catalog: shop
    run_as:
      service_principal_name: <prod-runner-application-id>
    permissions:
      - level: CAN_VIEW
        group_name: data-engineers
```

Top-level mappings apply to every target; a target overrides them. The keys a target may hold include `mode`,
`default`, `workspace`, `variables`, `run_as`, `permissions`, `git`, `presets`, `resources` and `artifacts`
([Configuration reference](https://docs.databricks.com/aws/en/dev-tools/bundles/reference)). Top-level
`permissions` levels are `CAN_VIEW`, `CAN_MANAGE` and `CAN_RUN`.

### The job resource

*Databricks only, not run here. Syntax from [Bundle configuration examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples) and [the GitHub Actions bundle example](https://docs.databricks.com/aws/en/dev-tools/ci-cd/github).*

```yaml
resources:
  jobs:
    silver_job:
      name: redrock_silver_orders
      parameters:
        - name: catalog
          default: ${var.catalog}
      tasks:
        - task_key: load_silver
          notebook_task:
            notebook_path: ../src/load_silver.ipynb
        - task_key: check_silver
          depends_on:
            - task_key: load_silver
          notebook_task:
            notebook_path: ../src/check_silver.ipynb
      schedule:
        quartz_cron_expression: '0 0 6 * * ?'
        timezone_id: UTC
```

`pause_status` is left out on purpose. The Jobs API default is `UNPAUSED`, so the schedule runs in staging and
prod, and development mode pauses it in dev. An explicit `pause_status: UNPAUSED` would win over development mode:
"To unpause an individual job, set the `pause_status` to `UNPAUSED`"
([Deployment modes](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes)), so every developer's
dev copy would run on the 6 a.m. schedule.

No cluster is defined: "you can either omit the `clusters` setting for a job with a notebook task, or you can
specify an environment" to run on serverless; for Python script, Python wheel and dbt tasks, "`environment_key` is
required for serverless compute" ([Bundle configuration
examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples)). Chapter 15 covers tasks, `depends_on`
and schedules; [chapter 6](06-Compute.md) shows the same job on a job cluster.

The notebook stays thin. It reads the job parameter, calls the tested package and writes:

*Databricks only, not run here. Imports from [Work with Python and R modules](https://docs.databricks.com/aws/en/files/workspace-modules); parameters from [Access parameter values from a task](https://docs.databricks.com/aws/en/jobs/parameter-use).*

```python
from redrock.transforms import bronze_to_silver
from redrock.writers import merge_orders

catalog = dbutils.widgets.get("catalog")
silver, quarantine = bronze_to_silver(spark.read.table(f"{catalog}.bronze.orders"))
merge_orders(spark, silver, f"{catalog}.silver.orders")
quarantine.write.mode("overwrite").saveAsTable(f"{catalog}.silver.orders_quarantine")
```

`import redrock` works without a `sys.path` change because "In Databricks Runtime 11.3 LTS and above, the current
working directory of your notebook is automatically added to the Python path", and the notebook sits in `src/`
next to the package. The quarantine table is overwritten, not appended, so a rerun does not duplicate it (Q30).

### Variables and substitutions

A **substitution** is a value the CLI fills in at deploy time, such as `${bundle.name}`, `${bundle.target}`,
`${workspace.current_user.short_name}`, `${workspace.file_path}` or `${resources.jobs.<job-name>.id}`. A **custom
variable** is declared under `variables` and referenced as `${var.<name>}`
([Substitutions and variables](https://docs.databricks.com/aws/en/dev-tools/bundles/variables)). A variable can
also `lookup` the ID of a named object (a cluster, a warehouse, a service principal and so on); "An error occurs if
an object with the specified name does not exist, or if there is more than one object with the specified name."

When a variable has several values, the CLI stops at the first it finds, in this order:

1. a `--var="<key>=<value>"` option on the `bundle` command
2. an environment variable named `BUNDLE_VAR_<name>`
3. the `.databricks/bundle/<target>/variable-overrides.json` file
4. the target's `variables` mapping
5. the variable's `default`

!!! warning "Bundle variables are not job parameters"
    "Bundle variables are deployment-time variables. They are interpreted when you deploy the bundle." Passing a
    different `--var` to `bundle run` does not change a job that is already deployed. To change a value per run,
    use a job parameter (the job above maps `catalog` to one) and `bundle run --params`.

!!! tip "In the interview"
    **"What are Declarative Automation Bundles (Databricks Asset Bundles)?"** Infrastructure as code for
    Databricks: YAML in the same Git repository as the code describes the jobs, pipelines and other resources,
    with one target per environment. The Databricks CLI validates, deploys and runs them, and CI calls the CLI.
    Databricks calls them "the recommended approach to CI/CD on Databricks"; the older name is Databricks Asset
    Bundles ([rename](https://docs.databricks.com/aws/en/dev-tools/bundles/)).

## 16.4 Bundle commands and deployment modes

*Level: intermediate.*

### The commands

*Databricks only, not run here. Syntax from [`bundle` command group](https://docs.databricks.com/aws/en/dev-tools/cli/bundle-commands).*

```bash
databricks bundle init                           # start from a template
databricks bundle validate -t dev                # check the configuration
databricks bundle plan -t staging                # show what deploy would change, change nothing
databricks bundle deploy -t staging              # create or update the resources
databricks bundle run -t staging silver_job      # run the deployed job and wait
databricks bundle run -t dev --params catalog=shop_dev silver_job
databricks bundle destroy -t dev                 # delete what this bundle deployed
```

| Command | What it does (from the command page) |
| --- | --- |
| `validate` | "Validate bundle configuration files are syntactically correct." Prints the bundle's name, target, host, user and path, and warns about properties not in the schema |
| `plan` | "Show the deployment plan ... without making any changes", for example `create jobs.my_bundle_job` |
| `deploy` | Creates resources that do not exist, updates those that do, and removes resources taken out of the configuration "if it was previously deployed" |
| `run` | Runs a job, pipeline, app or script by key; job parameters with `--params`; for pipelines `--refresh-all`, `--full-refresh-all`, `--validate-only` |
| `destroy` | "permanently deletes a bundle's previously-deployed jobs, pipelines, and artifacts. This action cannot be undone." Prompts unless `--auto-approve` |

`deploy` also has `--fail-on-active-runs`, `--force` (overrides the Git branch check), `--force-lock` ("only ...
if the previous deployment crashed or was interrupted and left a stale lock file") and `--select`, which Databricks
recommends "only using ... for deploying resources to development workspaces. It is not intended for use in
production."

### A bundle's identity

How does `deploy` know which job in the workspace is "its" job? Not by name. "A bundle deployment tracks the
resources it creates in the target workspace by their IDs as a state that is stored in the workspace file system."
The state lives under the bundle's `root_path`, which "defaults to `~/.bundle/${bundle.name}/${bundle.target}`", so
"a bundle's identity is comprised of the identity of the deployer, the bundle's name, and the bundle's target name."
Consequences:

- Two developers deploying the same bundle to `dev` do not collide: each has their own root path.
- Renaming the bundle or the target creates a new identity. The next deploy creates new jobs, and the old ones are
  left behind, no longer managed. "A resource's association with a bundle can only be forgotten if you change the
  bundle name, the bundle target, or the workspace."
- Do not use a `/Shared` path as the production `root_path`: "The `/Shared` folder is writable by all workspace
  users, which means anyone could modify your deployed production code" ([Configuration
  reference](https://docs.databricks.com/aws/en/dev-tools/bundles/reference)).

### Development mode and production mode

`mode` is optional: "Deployment modes are a convenience for applying a group of commonly used settings at once"
([Deployment modes](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes)).

| | `mode: development` | `mode: production` |
| --- | --- | --- |
| Resource names | prefixed `[dev ${workspace.current_user.short_name}]`, jobs and pipelines tagged `dev` | unchanged |
| Lakeflow pipelines | marked `development: true` | validated to be `development: false` |
| Schedules and triggers | paused | as configured |
| Concurrent job runs | enabled for all jobs | as configured |
| Deployment lock | disabled | on (the default) |
| `--cluster-id` override | allowed | not allowed |
| Git branch | no check listed for this mode | must equal the target's `git.branch`, if set (`--force` overrides) |
| Without a service principal | no check | validates paths are not overridden to a user and that `run_as` and `permissions` are set |

So `databricks bundle deploy -t dev` gives you a paused, prefixed copy of the job that cannot fire on its own
schedule and cannot be confused with the real one. Production mode adds guard rails. Custom `presets` (for example
`name_prefix`, `trigger_pause_status`, `jobs_max_concurrent_runs`, `tags`) change the defaults; "presets override the
default mode behavior, and settings of individual resources override the presets."

### Who deploys and who runs

"Databricks recommends that you use service principals for production deployments. You can enforce this by setting
`run_as` to a service principal." A **service principal** is "an identity created for use with automated tools and
applications" ([Service principals for CI/CD](https://docs.databricks.com/aws/en/dev-tools/auth/service-principals)).
`run_as` takes a `user_name` or a `service_principal_name` and separates the deploying identity from the running
one; when they differ, "only jobs and pipelines are supported"
([Specify a run identity](https://docs.databricks.com/aws/en/dev-tools/bundles/run-as)). The best-practices page goes
further: "Use separate service principals for deployment and runtime." The deployment principal "should have
minimal data access"; each production job gets its own run-as principal "scoped only to the data and resources that
workload requires".

!!! tip "In the interview"
    **"How do you deploy to production safely?"** Nobody deploys to production by hand. Jobs and pipelines are
    defined in a bundle (Declarative Automation Bundles, formerly
    [Databricks Asset Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/)). A merge to `main` triggers
    CI: unit tests, then `bundle deploy` and a run of the job in staging with data checks, then
    `bundle deploy -t prod` behind an approval. The prod target uses production mode (Git branch check, no cluster override), CI
    authenticates as a deployment service principal through workload identity federation, and the job runs as a
    separate run-as service principal with access only to its tables. The production catalog is bound to the
    production workspace. To roll back, revert the commit and let the same pipeline deploy it.

## 16.5 Authentication for CI

*Level: intermediate.*

CI needs to call the Databricks API without a person at the keyboard. The options, from weakest to strongest:

| Method | What CI stores | What Databricks says |
| --- | --- | --- |
| Personal access token of a user | a long-lived user token | use a service principal "instead of your Databricks user or your Databricks personal access token" |
| Service principal personal access token | a long-lived SP token | "Databricks recommends OAuth machine-to-machine (M2M) authentication over personal access tokens for CI/CD workflows" |
| OAuth M2M | SP client ID and OAuth secret | tokens are generated and refreshed for you; "Each access token is valid for one hour" |
| Workload identity federation | nothing secret (SP client ID only) | "the most secure way to authenticate your automated flows to Databricks" |

Sources: [Service principals for CI/CD](https://docs.databricks.com/aws/en/dev-tools/auth/service-principals),
[OAuth M2M](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-m2m),
[CI/CD workflows on Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/flows).

**OAuth M2M** (machine-to-machine): you create an OAuth secret for the service principal (lifetime up to 730 days)
and give CI `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET`; the CLI exchanges them for
one-hour access tokens. A secret can be **scoped** to APIs such as `sql` or `jobs`, and "Databricks recommends
binding each secret to only the scopes its integration needs." The secret still has to be stored and rotated.

**Workload identity federation** removes the secret. GitHub (like Azure DevOps, GitLab and others) issues a
signed token (a JWT, JSON Web Token) whose `sub` claim "encodes the repository, branch, tag, pull/merge request, or
environment that triggered the workflow". A **federation
policy** on the Databricks service principal says which issuer and subject to trust. The CLI then "automatically
fetch[es] workload identity tokens from GitHub and exchange[s] them for Databricks OAuth tokens"
([Enable workload identity federation for GitHub
Actions](https://docs.databricks.com/aws/en/dev-tools/auth/provider-github)). For GitHub:

- issuer `https://token.actions.githubusercontent.com`, audience your Databricks account ID (the default)
- entity type: the default is **Branch**; "Databricks recommends using **Environment**", which you get by setting
  `environment:` on the GitHub Actions job
- the subject must match the token's `sub` claim exactly. For a repository created, renamed or transferred before
  July 15, 2026 it looks like `repo:<org>/<repo>:environment:prod`; newer ones include numeric IDs, such as
  `repo:octo-org@123456/octo-repo@456789:environment:prod`
- in the workflow: `permissions: id-token: write`, and the variables `DATABRICKS_AUTH_TYPE: github-oidc`,
  `DATABRICKS_HOST` and `DATABRICKS_CLIENT_ID` (the service principal's application ID)

*Databricks only, not run here. Syntax from [Enable workload identity federation for GitHub Actions](https://docs.databricks.com/aws/en/dev-tools/auth/provider-github).*

```bash
databricks account service-principal-federation-policy create 5581763342009999 --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["<databricks-account-id>"],
    "subject": "repo:red-rock-supply/redrock-silver:environment:prod"
  }
}'
```

One policy per GitHub environment: the staging job's token has subject `...:environment:staging`, so it cannot use
the prod principal.

!!! warning "Secrets in CI"
    Never put a token in the workflow file: register it as a GitHub encrypted secret
    ([Service principals for CI/CD](https://docs.databricks.com/aws/en/dev-tools/auth/service-principals)). Do not
    commit "Tokens or credentials" or "Local data examples and files with PII"; runtime secrets belong in "workspace-level
    secret management backed by a cloud secret manager" synced into Databricks secret scopes ([Developer best
    practices](https://docs.databricks.com/aws/en/developers/best-practices)). With workload identity federation
    there is no Databricks secret in GitHub at all.

!!! tip "In the interview"
    **"How do you keep secrets out of code?"** Three places, three answers. CI authenticates to Databricks with
    workload identity federation, so no Databricks token is stored anywhere; if that is not available, an OAuth M2M
    secret for a service principal lives in GitHub encrypted (environment) secrets, scoped and rotated. Jobs read
    passwords for source systems from Databricks secret scopes (`dbutils.secrets.get`), backed by the cloud
    secret manager. The repository has no credentials and no PII sample files, enforced with `.gitignore` and
    review.

## 16.6 The testing pyramid for data pipelines

*Level: intermediate.*

The **testing pyramid** says: many fast, cheap tests at the bottom, fewer slow, expensive ones at the top. For a
Databricks project the best-practices page names three layers ("Implement testing layers"):

1. "**Unit tests**: Keep business logic in importable `src/` modules and cover it with `pytest` or an equivalent
   framework. Run these on every pull request so failures block merges."
2. "**Bundle validation**: Run `bundle validate` locally. In CI, prefer `bundle deploy` to a non-production
   workspace to catch YAML and resource-mapping issues before production deploys."
3. "**Integration tests in staging**: After deploying to staging, run end-to-end jobs with completion checks and
   critical data-quality assertions such as row-count or schema expectations."

Data pipelines need a fourth kind that ordinary software does not: **data tests**, which check the data itself
(row counts reconcile, keys are unique, values are in range) inside every run, in every environment, including
production. Code can be correct and the data still wrong, because a source changed.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 300" role="img" aria-label="Testing pyramid. Bottom, widest: unit tests with pytest and local Spark, every pull request, no workspace. Next: bundle validate and deploy to dev, needs credentials. Next: integration tests in staging, real compute and data. Top: data tests in every run.">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<polygon points="20,260 400,260 365,210 55,210"/>
<polygon points="55,210 365,210 330,160 90,160"/>
<polygon points="90,160 330,160 295,110 125,110"/>
<polygon points="125,110 295,110 210,40"/>
<line x1="628" y1="250" x2="628" y2="60"/>
</g>
<g fill="currentColor">
<polygon points="628,50 623,62 633,62"/>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="210" y="240">Unit tests (pytest, local Spark)</text>
<text x="210" y="190">Bundle validate + deploy to dev</text>
<text x="210" y="140">Integration in staging</text>
<text x="210" y="98">Data tests</text>
<text x="210" y="284">many, fast, cheap, no workspace</text>
</g>
<g fill="currentColor" font-size="13">
<text x="420" y="232">every PR, no workspace</text>
<text x="420" y="250">seconds to minutes</text>
<text x="420" y="182">every PR, needs credentials</text>
<text x="420" y="200">catches YAML mistakes</text>
<text x="420" y="132">after merge, real data</text>
<text x="420" y="150">runs the job end to end</text>
<text x="420" y="74">inside every run,</text>
<text x="420" y="92">in every environment</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="end">
<text x="620" y="40">slower, closer to real data</text>
</g>
</svg>
<figcaption>Figure 16.2. The testing pyramid for a Databricks pipeline. Unit tests run on a laptop or CI runner with
no workspace; the upper layers need Databricks. Data tests sit at the top because they check real data, in every run.</figcaption>
</figure>

| Test kind | Example for Red Rock Supply | Where it runs | Needs Databricks? |
| --- | --- | --- | --- |
| Unit | `latest_per_order` keeps the `SHIPPED` row | laptop, CI runner | no |
| Unit with Delta | running `merge_orders` twice changes nothing | laptop, CI runner (local Delta) | no |
| Bundle validation | `bundle validate`, `bundle deploy -t dev` | CI runner, calling the workspace | yes |
| Integration | run `silver_job` in staging, then check `shop_staging.silver.orders` | staging workspace | yes |
| Data | `assert_true(count(*) = count(DISTINCT order_id))` after the load | every run, every environment | runs where the job runs |

### Testing notebooks or modules?

You can test code that lives in a notebook, but it is harder. The Databricks page compares three layouts and
recommends one: "For Python and R notebooks, Databricks recommends storing functions and their unit tests outside of
notebooks" ([Unit testing for Databricks
notebooks](https://docs.databricks.com/aws/en/notebooks/testing)). The best-practices page adds "Do not treat
notebooks as the primary container for business logic" and keep them as "thin orchestration and visualization
layers". Reasons that matter in an interview:

- A function in a `.py` module can be imported by pytest on a CI runner. A notebook cell cannot.
- A notebook mixes logic with reads and writes of real tables, so its "test" needs a workspace and real data.
- A notebook cannot be imported as a Python module on Databricks Runtime 16.0 and above
  ([What are workspace files?](https://docs.databricks.com/aws/en/files/workspace)).

In the workspace, files named `test_*.py` or `*_test.py` get a **Tests** pane with run buttons ([Python unit
testing in the workspace](https://docs.databricks.com/aws/en/files/python-unit-tests)), and the notebook testing
page shows running pytest from a notebook:

*Databricks only, not run here. Syntax from [Unit testing for Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/testing).*

```python
import pytest
import sys

# Skip writing pyc files on a readonly filesystem.
sys.dont_write_bytecode = True

# Run pytest.
retcode = pytest.main([".", "-v", "-p", "no:cacheprovider"])

# Fail the cell execution if there are any test failures.
assert retcode == 0, "The pytest invocation failed. See the log for details."
```

## 16.7 Unit tests with pytest and a local SparkSession

*Level: intermediate.*

A **unit test** checks one small piece of code with a small, hand-made input and a known answer. For Spark the
piece is a function that takes DataFrames and returns DataFrames, and the input is a DataFrame of three to ten rows
built inside the test. The trick is design, not tooling: keep reads, writes, table names and configuration out of
the transformation functions, and they become easy to test.

### The code under test

The silver logic from [chapter 9](09-Building-Silver.md), refactored into a package. `transforms.py` holds pure
functions (no reads, no writes); `writers.py` holds the one function that touches a table.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
# src/redrock/transforms.py
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import (DecimalType, IntegerType, StringType, StructField,
                               StructType, TimestampType)

# The contract of shop.silver.orders. A schema test compares against this.
SILVER_ORDERS_SCHEMA = StructType([
    StructField("order_id", IntegerType()),
    StructField("customer_id", IntegerType()),
    StructField("order_ts", TimestampType()),
    StructField("status", StringType()),
    StructField("amount", DecimalType(10, 2)),
    StructField("currency", StringType()),
    StructField("updated_at", TimestampType()),
])
SILVER_COLUMNS = [f.name for f in SILVER_ORDERS_SCHEMA.fields]

VALID_CURRENCIES = ["CAD", "USD"]


def type_orders(bronze: DataFrame) -> DataFrame:
    """Cast the raw string columns of bronze orders. Bad values become NULL, never an error."""
    return bronze.select(
        F.col("order_id").alias("raw_order_id"),
        F.col("order_ts").alias("raw_order_ts"),
        F.col("amount").alias("raw_amount"),
        F.col("order_id").try_cast("int").alias("order_id"),
        F.col("customer_id").try_cast("int").alias("customer_id"),
        F.try_to_timestamp("order_ts").alias("order_ts"),
        F.upper(F.trim("status")).alias("status"),
        F.col("amount").try_cast("decimal(10,2)").alias("amount"),
        F.nullif(F.upper(F.trim("currency")), F.lit("")).alias("currency"),
        F.try_to_timestamp("updated_at").alias("updated_at"),
        "_source_file",
    )


def add_dq_errors(typed: DataFrame) -> DataFrame:
    """Add dq_errors: the list of every rule the row fails (empty list = valid)."""
    rules = [
        (F.col("order_id").isNull(), F.lit("order_id missing or not an integer")),
        (F.col("customer_id").isNull(), F.lit("customer_id missing")),
        (F.col("order_ts").isNull(), F.concat(F.lit("order_ts not a timestamp: "),
                                              F.coalesce("raw_order_ts", F.lit("NULL")))),
        (F.col("amount").isNull(), F.concat(F.lit("amount not a number: "),
                                            F.coalesce("raw_amount", F.lit("NULL")))),
        (F.col("amount") < 0, F.lit("amount negative")),
        (F.col("currency").isNull() | ~F.col("currency").isin(VALID_CURRENCIES),
         F.lit("currency missing or unknown")),
    ]
    checks = F.array(*[F.when(failed, message) for failed, message in rules])
    return typed.withColumn("dq_errors", F.filter(checks, lambda e: e.isNotNull()))


def split_valid_invalid(checked: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Every row goes to exactly one side: size(dq_errors) is never NULL here."""
    valid = checked.where(F.size("dq_errors") == 0).select(*SILVER_COLUMNS)
    invalid = checked.where(F.size("dq_errors") > 0).select(
        "raw_order_id", "raw_order_ts", "raw_amount", "dq_errors", "_source_file")
    return valid, invalid


def latest_per_order(events: DataFrame) -> DataFrame:
    """One row per order_id: the latest updated_at wins."""
    w = Window.partitionBy("order_id").orderBy(F.col("updated_at").desc())
    return (events.withColumn("_rn", F.row_number().over(w))
                  .where("_rn = 1")
                  .drop("_rn"))


def bronze_to_silver(bronze: DataFrame) -> tuple[DataFrame, DataFrame]:
    """The whole silver step: (silver orders, quarantine)."""
    valid, invalid = split_valid_invalid(add_dq_errors(type_orders(bronze)))
    return latest_per_order(valid), invalid
```

```python
# src/redrock/writers.py
from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession


def merge_orders(spark: SparkSession, updates: DataFrame, target_table: str) -> None:
    """Upsert one row per order into silver. Safe to rerun with the same batch."""
    target = DeltaTable.forName(spark, target_table)
    (target.alias("t")
        .merge(updates.alias("s"), "t.order_id = s.order_id")
        .whenMatchedUpdateAll(condition="s.updated_at > t.updated_at")
        .whenNotMatchedInsertAll()
        .execute())
```

This is the DataFrame form of the SQL in chapter 9: `try_cast` and `try_to_timestamp` instead of `CAST`, the list
of failed rules built with `filter(array(...))`, `row_number` for the latest event, and the out-of-order guard
`s.updated_at > t.updated_at` in the `MERGE`. `Column.try_cast` is a PySpark 4.0 addition, so it needs
Spark 4.0 or later.

### The fixture

A pytest **fixture** is a function that prepares something a test needs; a test asks for it by naming it as a
parameter. Starting Spark takes seconds, so the SparkSession fixture has `scope="session"`: it is created once for
the whole run and stopped at the end. The PySpark testing guide uses the same `yield` pattern ([Testing
PySpark](https://spark.apache.org/docs/latest/api/python/getting_started/testing_pyspark.html)).

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
# conftest.py (project root)
import os

import pytest
from pyspark.sql import SparkSession

BRONZE_DDL = ("order_id STRING, customer_id STRING, order_ts STRING, status STRING, "
              "amount STRING, currency STRING, updated_at STRING, _source_file STRING")

F1, F2 = "orders_2026-03-01.json", "orders_2026-03-02.json"
BRONZE_ROWS = [
    ("1001", "7", "2026-03-01T10:15:00Z", "PLACED", "59.90", "CAD", "2026-03-01T10:15:00Z", F1),
    ("1001", "7", "2026-03-01T10:15:00Z", "PLACED", "59.90", "CAD", "2026-03-01T10:15:00Z", F1),
    ("1002", "8", "2026-03-01T11:00:00Z", "PLACED", "120.00", "cad", "2026-03-01T11:00:00Z", F1),
    ("1002", "8", "2026-03-01T11:00:00Z", " shipped ", "120.00", "CAD", "2026-03-02T09:00:00Z", F2),
    ("1003", "9", "2026-03-01T12:30:00Z", "PLACED", "abc", "CAD", "2026-03-01T12:30:00Z", F1),
    ("1004", None, "2026-03-01T12:45:00Z", "PLACED", "15.00", "USD", "2026-03-01T12:45:00Z", F1),
    ("1007", "7", "2026-03-02T08:00:00Z", "PLACED", "-5.00", "", "2026-03-02T08:00:00Z", F2),
]


@pytest.fixture(scope="session")
def spark(tmp_path_factory):
    """One local SparkSession with Delta Lake for the whole test run."""
    builder = (SparkSession.builder
               .master("local[1]")
               .appName("redrock-tests")
               .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
               .config("spark.sql.catalog.spark_catalog",
                       "org.apache.spark.sql.delta.catalog.DeltaCatalog")
               .config("spark.sql.warehouse.dir", str(tmp_path_factory.mktemp("warehouse")))
               .config("spark.sql.shuffle.partitions", "1")
               .config("spark.ui.enabled", "false")
               .config("spark.sql.session.timeZone", "UTC"))
    jars = os.environ.get("DELTA_JARS")  # local jar files, for machines without Maven access
    if jars:
        builder = builder.config("spark.jars", jars)
    else:
        from delta import configure_spark_with_delta_pip  # downloads the Delta jars
        builder = configure_spark_with_delta_pip(builder)
    session = builder.getOrCreate()
    yield session
    session.stop()


@pytest.fixture
def bronze(spark):
    return spark.createDataFrame(BRONZE_ROWS, BRONZE_DDL)
```

Each setting has a reason:

- `local[1]` and `spark.sql.shuffle.partitions=1`: test data is tiny. The default is 200 shuffle partitions
  ([Spark 4.2.0 performance tuning](https://spark.apache.org/docs/4.2.0/sql-performance-tuning.html)); adaptive
  query execution coalesces small ones "to avoid too many small tasks", but one partition keeps every shuffle in a
  test to a single small task and makes the suite faster and more predictable.
- `spark.sql.session.timeZone=UTC`: Spark parses timestamp strings without an offset, and `show()` prints
  timestamps, in the session time zone, so pin it. It does not cover the Python side: `collect()` and
  `createDataFrame` from a Python `datetime` convert in the Python process's local time zone. A check run here with
  the session zone pinned to UTC but `TZ=America/Vancouver`: `show()` printed `2026-03-01 11:00:00` and `collect()`
  returned `03:00`. The tests below compare with naive `datetime` values, so they pass on a CI runner in UTC and fail
  on a laptop in Vancouver unless the test process also runs in UTC (for example `TZ=UTC python -m pytest`).
- `tmp_path_factory`: a fresh warehouse folder per run, so tables from the last run cannot leak into this one.
- The Delta extension and catalog settings make `DeltaTable` and Delta SQL work. `configure_spark_with_delta_pip`
  comes with the `delta-spark` pip package and adds the matching Delta Maven package to the session (it downloads
  the jars on first use). The run here used local jar files through `DELTA_JARS` instead, the standard setup of this
  environment; the Maven download path was not run here.
- `bronze` is function-scoped: each test gets its own DataFrame, so tests cannot affect each other.

### The tests

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
# tests/test_transforms.py
import datetime as dt
from decimal import Decimal

from pyspark.testing.utils import assertDataFrameEqual, assertSchemaEqual

from redrock.transforms import (SILVER_ORDERS_SCHEMA, add_dq_errors, bronze_to_silver,
                                latest_per_order, split_valid_invalid, type_orders)


def test_type_orders_casts_and_cleans(spark):
    raw = spark.createDataFrame(
        [("1002", "8", "2026-03-01T11:00:00Z", " shipped ", "120.00", "cad",
          "2026-03-02T09:00:00Z", "f.json")],
        "order_id STRING, customer_id STRING, order_ts STRING, status STRING, "
        "amount STRING, currency STRING, updated_at STRING, _source_file STRING")
    row = type_orders(raw).first()
    assert row.order_id == 1002
    assert row.status == "SHIPPED"
    assert row.currency == "CAD"
    assert row.amount == Decimal("120.00")
    assert row.order_ts == dt.datetime(2026, 3, 1, 11, 0)


def test_bad_rows_get_every_reason(bronze):
    checked = add_dq_errors(type_orders(bronze))
    errors = {r.raw_order_id: r.dq_errors for r in checked.where("size(dq_errors) > 0").collect()}
    assert errors == {
        "1003": ["amount not a number: abc"],
        "1004": ["customer_id missing"],
        "1007": ["amount negative", "currency missing or unknown"],
    }


def test_every_bronze_row_lands_exactly_once(bronze):
    valid, invalid = split_valid_invalid(add_dq_errors(type_orders(bronze)))
    assert valid.count() + invalid.count() == bronze.count()


def test_latest_per_order_keeps_the_newest_event(spark):
    events = spark.createDataFrame(
        [(1002, "PLACED", dt.datetime(2026, 3, 1, 11, 0)),
         (1002, "SHIPPED", dt.datetime(2026, 3, 2, 9, 0)),
         (1001, "PLACED", dt.datetime(2026, 3, 1, 10, 15))],
        "order_id INT, status STRING, updated_at TIMESTAMP")
    expected = spark.createDataFrame(
        [(1001, "PLACED", dt.datetime(2026, 3, 1, 10, 15)),
         (1002, "SHIPPED", dt.datetime(2026, 3, 2, 9, 0))],
        "order_id INT, status STRING, updated_at TIMESTAMP")
    assertDataFrameEqual(latest_per_order(events), expected)


def test_silver_schema_is_the_contract(bronze):
    silver, _ = bronze_to_silver(bronze)
    assertSchemaEqual(silver.schema, SILVER_ORDERS_SCHEMA)


def test_bronze_to_silver_end_to_end(spark, bronze):
    silver, quarantine = bronze_to_silver(bronze)
    expected = spark.createDataFrame(
        [(1001, 7, dt.datetime(2026, 3, 1, 10, 15), "PLACED", Decimal("59.90"), "CAD",
          dt.datetime(2026, 3, 1, 10, 15)),
         (1002, 8, dt.datetime(2026, 3, 1, 11, 0), "SHIPPED", Decimal("120.00"), "CAD",
          dt.datetime(2026, 3, 2, 9, 0))],
        SILVER_ORDERS_SCHEMA)
    assertDataFrameEqual(silver, expected)
    assert quarantine.count() == 3
```

Two PySpark helpers do the comparing ([Testing
PySpark](https://spark.apache.org/docs/latest/api/python/getting_started/testing_pyspark.html)):

- `assertDataFrameEqual(actual, expected)` compares rows and schema and prints a diff on failure. In PySpark
  4.2.0 its defaults (read from the function signature here) are `checkRowOrder=False`, `ignoreNullable=True`,
  `ignoreColumnOrder=False`, `rtol=1e-05`: row order does not matter, which is right for Spark, where row order is
  not guaranteed without `ORDER BY`. Its docstring adds: "schema equality is checked only when `expected` is a
  DataFrame (not a list of Rows)."
- `assertSchemaEqual(actual, expected)` compares two `StructType`s (default `ignoreNullable=True`). The schema test
  is the contract test: if someone changes `amount` to `DOUBLE`, it fails before gold breaks.

The `MERGE` tests use a real Delta table in the local warehouse. The idempotency test runs the same batch twice and
checks both the table and the commit metrics in `DESCRIBE HISTORY`:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
# tests/test_merge.py
import datetime as dt
from decimal import Decimal

import pytest
from pyspark.testing.utils import assertDataFrameEqual

from redrock.transforms import SILVER_ORDERS_SCHEMA, bronze_to_silver
from redrock.writers import merge_orders


@pytest.fixture
def silver_table(spark):
    """An empty Delta table with the silver schema, dropped after the test."""
    name = "silver_orders_test"
    spark.sql(f"DROP TABLE IF EXISTS {name}")
    spark.createDataFrame([], SILVER_ORDERS_SCHEMA).write.format("delta").saveAsTable(name)
    yield name
    spark.sql(f"DROP TABLE IF EXISTS {name}")


def test_merge_is_idempotent(spark, bronze, silver_table):
    silver, _ = bronze_to_silver(bronze)

    merge_orders(spark, silver, silver_table)
    after_first = spark.read.table(silver_table).collect()

    merge_orders(spark, silver, silver_table)          # the same batch again: a rerun
    after_second = spark.read.table(silver_table)

    assertDataFrameEqual(after_second, after_first)
    last = spark.sql(f"DESCRIBE HISTORY {silver_table}").orderBy("version", ascending=False).first()
    assert last.operation == "MERGE"
    assert last.operationMetrics["numTargetRowsInserted"] == "0"
    assert last.operationMetrics["numTargetRowsUpdated"] == "0"


def test_late_older_event_does_not_overwrite_newer(spark, bronze, silver_table):
    silver, _ = bronze_to_silver(bronze)
    merge_orders(spark, silver, silver_table)

    stale = spark.createDataFrame(
        [(1002, 8, dt.datetime(2026, 3, 1, 11, 0), "PLACED", Decimal("120.00"), "CAD",
          dt.datetime(2026, 3, 1, 11, 0))],
        SILVER_ORDERS_SCHEMA)
    merge_orders(spark, stale, silver_table)

    status = spark.read.table(silver_table).where("order_id = 1002").first().status
    assert status == "SHIPPED"
```

Why is `.collect()` called on `after_first`? A DataFrame is a query, not a snapshot: if the test kept the
DataFrame, it would re-read the table after the second `MERGE` and compare the table with itself. Collecting the
rows freezes the first result (and because `expected` is then a list of Rows, only the rows are compared). The
`.format("delta")` matters too: in open-source Spark the default table format is
Parquet, and `DeltaTable.forName` on a Parquet table fails with `DELTA_MISSING_DELTA_TABLE` (it happened while
writing this chapter). On Databricks, Delta is the default.

`pyproject.toml` tells pytest where the code and tests are:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```toml
[project]
name = "redrock"
version = "0.1.0"
requires-python = ">=3.10"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
filterwarnings = ["ignore:PySpark does not yet fully support pandas:FutureWarning"]
```

The run (the twelve tests include the four "write the test" answers of 16.10; long paths shortened):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
$ python -m pytest -v
============================= test session starts ==============================
platform linux -- Python 3.13.18, pytest-9.2.0, pluggy-1.7.0 -- .../v2/bin/python
rootdir: .../redrock_silver
configfile: pyproject.toml
testpaths: tests
collecting ... collected 12 items

tests/test_merge.py::test_merge_is_idempotent PASSED                     [  8%]
tests/test_merge.py::test_late_older_event_does_not_overwrite_newer PASSED [ 16%]
tests/test_practice.py::test_amount_and_currency_are_normalized PASSED   [ 25%]
tests/test_practice.py::test_null_amount_is_quarantined_with_a_reason PASSED [ 33%]
tests/test_practice.py::test_silver_has_one_row_per_order PASSED         [ 41%]
tests/test_practice.py::test_empty_batch_gives_empty_silver_with_the_contract_schema PASSED [ 50%]
tests/test_transforms.py::test_type_orders_casts_and_cleans PASSED       [ 58%]
tests/test_transforms.py::test_bad_rows_get_every_reason PASSED          [ 66%]
tests/test_transforms.py::test_every_bronze_row_lands_exactly_once PASSED [ 75%]
tests/test_transforms.py::test_latest_per_order_keeps_the_newest_event PASSED [ 83%]
tests/test_transforms.py::test_silver_schema_is_the_contract PASSED      [ 91%]
tests/test_transforms.py::test_bronze_to_silver_end_to_end PASSED        [100%]

======================== 12 passed in 207.08s (0:03:27) ========================
```

The 207 seconds are this shared, heavily loaded machine (load average above 30 on 4 cores); the same suite on an
idle laptop is usually much faster, but Spark start-up still dominates, which is why the session fixture matters.

### What a failing test tells you

The point of a test is the day it fails. Here is the "NULL hole" bug from chapter 9: a split written as
`amount >= 0` versus `NOT (amount >= 0)`. The row with amount `abc` (NULL after `try_cast`) satisfies neither, so
it disappears.

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
# bug_demo/test_null_hole.py
from redrock.transforms import type_orders


def split_buggy(typed):
    good = typed.where("amount >= 0")
    bad = typed.where("NOT (amount >= 0)")
    return good, bad


def test_every_bronze_row_lands_exactly_once(bronze):
    good, bad = split_buggy(type_orders(bronze))
    assert good.count() + bad.count() == bronze.count()
```

```text
$ python -m pytest bug_demo
collected 1 item

bug_demo/test_null_hole.py F                                             [100%]

=================================== FAILURES ===================================
___________________ test_every_bronze_row_lands_exactly_once ___________________
...
    def test_every_bronze_row_lands_exactly_once(bronze):
        good, bad = split_buggy(type_orders(bronze))
>       assert good.count() + bad.count() == bronze.count()
E       assert (5 + 1) == 7
...
bug_demo/test_null_hole.py:13: AssertionError
=========================== short test summary info ============================
FAILED bug_demo/test_null_hole.py::test_every_bronze_row_lands_exactly_once
============================== 1 failed in 30.78s ==============================
```

(Trimmed: the full output, with pytest's explanation of each `count()` and Spark's start-up log, is in
`src/ch16/pytest_bug_demo.out`.) `5 + 1 == 7` says one row went nowhere. A reconciliation test is cheap to write
and catches a whole family of bugs: wrong filters, inner joins that drop rows, NULL comparisons.

!!! warning "assertDataFrameEqual and pandas 3"
    The first run of this suite failed in the three tests that call `assertDataFrameEqual`, with
    `ImportError: cannot import name 'DateOffset' from 'pandas.tseries.frequencies'`. When pandas and pyarrow are
    installed, PySpark 4.2.0's `assertDataFrameEqual` imports `pyspark.pandas`, which does not import with
    pandas 3.1.1. PySpark itself prints a FutureWarning that it "does not yet fully support pandas >= 3.0.0"
    and recommends staying below 3.0.0 "for now". The suite above ran with pandas 2.3.3. Pin `pandas<3` in the test environment
    (until a PySpark release says otherwise), and pin your test dependencies in general: a test suite that breaks
    because a library moved is a CI failure that has nothing to do with your code.

!!! tip "In the interview"
    **"How do you test a Spark job?"** I keep transformations as pure functions that take and return DataFrames, in
    a Python package, and the notebook or job only reads, calls and writes. Unit tests use pytest with a
    session-scoped local SparkSession (one shuffle partition, UTC time zone) and tiny DataFrames with the edge
    cases: NULLs, duplicates, bad strings, late events. I compare with `assertDataFrameEqual` and pin the output
    schema with `assertSchemaEqual`. The `MERGE` gets its own test against a local Delta table: run the same batch
    twice and the second run must change nothing. Above that, CI deploys the bundle to staging and runs the job,
    and data tests (reconciliation, unique keys) run inside every production run.

## 16.8 Data tests and integration tests

*Level: expert.*

### Data tests inside the job

Unit tests prove the code does what you meant. They cannot prove that today's file from the ERP system is sane.
**Data tests** run against the real tables after each load and fail the run when the data breaks a rule. The
`check_silver` task of the job is that test. In SQL, `assert_true(condition [, message])` "Returns an error if
`expr` is not true" and returns NULL otherwise; the error condition is `USER_RAISED_EXCEPTION`, SQLSTATE `P0001`
([assert_true function](https://docs.databricks.com/aws/en/sql/language-manual/functions/assert_true)). Open-source
Spark has the same function. Run here on tables built by the package (flat names, no Unity Catalog):

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```sql
SELECT assert_true(count(*) = count(DISTINCT order_id),
                   'silver_orders has duplicate order_id values') AS unique_check
FROM silver_orders;

SELECT assert_true(
         (SELECT count(*) FROM bronze_orders) =
         (SELECT count(*) FROM silver_order_events) + (SELECT count(*) FROM quarantine_orders),
         'bronze rows were lost or duplicated on the way to silver') AS reconcile_check;
```

```text
+------------+
|unique_check|
+------------+
|NULL        |
+------------+

+---------------+
|reconcile_check|
+---------------+
|NULL           |
+---------------+
```

Both pass (NULL). Then the script simulated a bad rerun that appended the silver batch instead of merging it, and
ran the uniqueness check again:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```text
-- simulate a bad rerun that appended instead of merging
SparkRuntimeException: [USER_RAISED_EXCEPTION] silver_orders has duplicate order_id values SQLSTATE: P0001
```

The same check in PySpark, which also shows which keys are duplicated:

*Run here: Apache Spark 4.2 + Delta Lake 4.4.1.*

```python
from pyspark.sql import functions as F
dupes = (spark.read.table("silver_orders").groupBy("order_id").count()
         .where(F.col("count") > 1))
dupes.show()
```

```text
+--------+-----+
|order_id|count|
+--------+-----+
|    1001|    2|
|    1002|    2|
+--------+-----+
```

In a Databricks notebook task, `spark.sql(...)` of the `assert_true` query with `.collect()` raises, the task fails,
and the job's failure notifications (if configured) fire before anyone reads the bad data. `count(DISTINCT order_id)` ignores NULLs,
so a NULL key also fails the check, which is what you want in silver. In Lakeflow pipelines (formerly
[Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)) the built-in form is
**expectations** (warn, drop, or fail the update); see [chapter 14](14-Data-Quality-and-CDC.md) and
[Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations). Delta
`CHECK` constraints ([chapter 9](09-Building-Silver.md)) reject bad rows at write time.

### Integration tests in staging

An **integration test** checks that the pieces work together on the real platform: the bundle deploys, the job
finds its tables, the service principal has its grants, serverless has the libraries, and the output is right. The
simplest integration test is the pipeline itself: CI runs `databricks bundle run -t staging silver_job`, which waits
for the run and fails if any task fails, including `check_silver`.

For checks written as pytest, **Databricks Connect** runs the DataFrame part on Databricks compute from any Python
process, including a CI runner ([chapter 2](02-Workspace-Tour.md)). The Databricks page on testing shows the
pattern with `DatabricksSession.builder.getOrCreate()`:

*Databricks only, not run here. Syntax from [Testing for Databricks Connect for Python](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/python/testing).*

```python
# tests_integration/test_staging_silver.py  (its own virtual environment: databricks-connect, no pyspark)
import pytest
from databricks.connect import DatabricksSession

CATALOG = "shop_staging"


@pytest.fixture(scope="session")
def spark():
    return DatabricksSession.builder.getOrCreate()


def test_silver_orders_has_one_row_per_order(spark):
    dupes = (spark.read.table(f"{CATALOG}.silver.orders")
             .groupBy("order_id").count().where("count > 1"))
    assert dupes.count() == 0


def test_transform_runs_on_databricks(spark):
    from redrock.transforms import bronze_to_silver
    silver, _ = bronze_to_silver(spark.read.table(f"{CATALOG}.bronze.orders").limit(1000))
    assert silver.columns == ["order_id", "customer_id", "order_ts", "status",
                              "amount", "currency", "updated_at"]
```

Two traps from the same page:

- "Databricks Connect and PySpark are mutually exclusive." The unit tests need `pyspark` (local Spark); the
  integration tests need `databricks-connect`. Keep them in separate virtual environments (or separate CI jobs).
- "When running Databricks Connect from the terminal, `pytest` only works with the DEFAULT configuration profile."
  In CI, the environment variables of 16.5 provide the credentials instead of a profile file; the compute (a
  cluster or serverless) must also be configured, see [Compute configuration for Databricks
  Connect](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/cluster-config).

Databricks Connect is also how you debug from an IDE: set a breakpoint in `bronze_to_silver`, run against the dev
catalog, inspect the DataFrame on real data. The same pure functions run on a laptop's local Spark and on Databricks
compute; only the fixture differs.

## 16.9 A GitHub Actions pipeline

*Level: expert.*

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 320" role="img" aria-label="What runs where. Your laptop: write code and tests, pytest with local Spark, bundle deploy to dev with your own login. GitHub Actions runner: checkout, pytest with local Spark, bundle deploy and run as a service principal via workload identity federation. Databricks workspace: bundle files and state, jobs and pipelines, job runs on serverless against the environment's catalog.">
<g fill="none" stroke="currentColor" stroke-width="1.5">
<rect x="20" y="36" width="180" height="200" rx="6" stroke-dasharray="5 4"/>
<rect x="230" y="36" width="180" height="200" rx="6" stroke-dasharray="5 4"/>
<rect x="440" y="36" width="180" height="200" rx="6" stroke-dasharray="5 4"/>
<rect x="30" y="50" width="160" height="36" rx="4"/>
<rect x="30" y="100" width="160" height="36" rx="4"/>
<rect x="30" y="150" width="160" height="36" rx="4"/>
<rect x="240" y="50" width="160" height="36" rx="4"/>
<rect x="240" y="100" width="160" height="36" rx="4"/>
<rect x="240" y="150" width="160" height="36" rx="4"/>
<rect x="450" y="50" width="160" height="36" rx="4"/>
<rect x="450" y="100" width="160" height="36" rx="4"/>
<rect x="450" y="150" width="160" height="36" rx="4"/>
<line x1="400" y1="168" x2="442" y2="168"/>
<polyline points="110,186 110,262 530,262 530,244"/>
</g>
<g fill="currentColor">
<polygon points="450,168 440,163 440,173"/>
<polygon points="530,236 525,246 535,246"/>
</g>
<g fill="currentColor" font-size="14" text-anchor="middle">
<text x="110" y="26">Your laptop</text>
<text x="320" y="26">GitHub Actions runner</text>
<text x="530" y="26">Databricks workspace</text>
</g>
<g fill="currentColor" font-size="13" text-anchor="middle">
<text x="110" y="73">write code + tests</text>
<text x="110" y="123">pytest, local Spark</text>
<text x="110" y="173">bundle deploy -t dev</text>
<text x="320" y="73">checkout repo</text>
<text x="320" y="123">pytest, local Spark</text>
<text x="320" y="173">bundle deploy / run</text>
<text x="530" y="73">files in .bundle/</text>
<text x="530" y="123">jobs + pipelines</text>
<text x="530" y="173">job run, serverless</text>
<text x="530" y="222">catalog per environment</text>
</g>
<g fill="currentColor" font-size="13">
<text x="20" y="286">you: deploy -t dev with your own login (OAuth U2M)</text>
<text x="20" y="308">CI: deploy -t staging / prod as a service principal (workload identity federation)</text>
</g>
</svg>
<figcaption>Figure 16.3. What runs where. Unit tests run with local Spark on the laptop and on the CI runner, with no
workspace and no credentials. Only the bundle commands talk to Databricks, and in CI they do so as a service
principal.</figcaption>
</figure>

Databricks documents GitHub Actions on its own page ("This feature is in Public Preview") and publishes one action,
`databricks/setup-cli`, "A composite action that sets up the Databricks CLI in a GitHub Actions workflow"
([GitHub Actions](https://docs.databricks.com/aws/en/dev-tools/ci-cd/github)). The workflow below puts the pieces of
this chapter together for Red Rock Supply: unit tests on every pull request and push, `bundle validate` against dev
on pull requests, and on a merge to `main` a staging deploy and run, then a production deploy.

*Databricks only, not run here. Syntax from [GitHub Actions](https://docs.databricks.com/aws/en/dev-tools/ci-cd/github) (Nov 4, 2026), [Enable workload identity federation for GitHub Actions](https://docs.databricks.com/aws/en/dev-tools/auth/provider-github) (Oct 2, 2026) and the [setup-cli README](https://github.com/databricks/setup-cli).*

```yaml
# .github/workflows/redrock-silver.yml
name: redrock-silver CI/CD

on:
  pull_request:
    branches:
      - main
  push:
    branches:
      - main

permissions:
  id-token: write   # required for workload identity federation
  contents: read

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install pytest pyspark==4.2.0 delta-spark==4.4.1 "pandas<3" pyarrow
      - run: python -m pytest -v

  validate-dev:
    needs: unit-tests
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    environment: dev
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      DATABRICKS_CLIENT_ID: ${{ secrets.DATABRICKS_CLIENT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: databricks/setup-cli@v1.25.0
      - run: databricks bundle validate -t dev

  deploy-staging:
    needs: unit-tests
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: staging
    concurrency: staging_environment
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      DATABRICKS_CLIENT_ID: ${{ secrets.DATABRICKS_CLIENT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: databricks/setup-cli@v1.25.0
      - run: databricks bundle deploy -t staging
      - run: databricks bundle run -t staging silver_job

  deploy-prod:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: prod
    concurrency: prod_environment
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      DATABRICKS_CLIENT_ID: ${{ secrets.DATABRICKS_CLIENT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: databricks/setup-cli@v1.25.0
      - run: databricks bundle deploy -t prod
```

How to read it:

- **Triggers.** `pull_request` to `main` runs the tests and validation; `push` to `main` (a merged pull request)
  deploys. `needs:` makes the jobs a chain: no deploy without green unit tests, no prod without a successful
  staging deploy and run.
- **Unit tests need no Databricks.** The runner installs Java (Spark 4.2 "runs on Java 17/21/25, Scala 2.13, Python
  3.10+", [Spark 4.2.0 overview](https://spark.apache.org/docs/4.2.0/)), PySpark, `delta-spark` and pytest, then runs
  the same suite as 16.7. The conftest fixture downloads the Delta jars through `configure_spark_with_delta_pip`
  (not run here).
- **Environments.** Each deploy job names a GitHub **environment** (`dev`, `staging`, `prod`). That gives each one
  its own `DATABRICKS_HOST` variable and `DATABRICKS_CLIENT_ID` secret (a different workspace and service principal
  per environment) and its own federation subject, `...:environment:prod`. Keep `DATABRICKS_HOST` equal to the
  target's `workspace.host`.
- **Approval.** In GitHub, an environment can have **required reviewers**: "Use required reviewers to require a
  specific person or team to approve workflow jobs that reference the environment", and "a job cannot access
  environment secrets until one of the required reviewers approves it" ([Deployments and environments, GitHub
  docs source](https://github.com/github/docs/blob/main/content/actions/reference/workflows-and-actions/deployments-and-environments.md)).
  Setting it on `prod` turns `deploy-prod` into a release button. (On GitHub Free, Pro and Team plans this is only
  available for public repositories, per the same page.)
- **No secret.** `DATABRICKS_CLIENT_ID` is stored as a secret in the Databricks example, but it is an ID, not a
  credential. With `DATABRICKS_AUTH_TYPE: github-oidc` and `id-token: write`, there is no Databricks token at all.
  The Databricks token-based examples instead set `DATABRICKS_TOKEN` from a GitHub secret.
- **`concurrency`.** Deploys to one environment run one at a time, so two merges in quick succession do not deploy
  over each other. GitHub allows `concurrency` per job (`jobs.<job_id>.concurrency` in the workflow syntax); the
  Databricks Git folder example sets `concurrency: prod_environment` for its whole workflow.
- **Action versions.** `actions/checkout@v4` and `actions/setup-java@v4` are what the Databricks JAR example uses
  (its other examples use `actions/checkout@v3`); GitHub's own docs currently show `actions/checkout@v6` and
  `actions/setup-python@v5`.
- **Pinned CLI.** `@main` always installs the latest CLI; a release tag pins it. The Databricks JAR example pins
  `databricks/setup-cli@v1.23.0` ("Pin to a specific version"); the README's example tag is `v1.25.0`. Pinning
  means a new CLI release cannot break a production deploy without a commit that you can see.
- **The staging run is the integration test.** `bundle run` waits for the job and fails the CI job if the run
  fails, so a `check_silver` failure in staging stops the prod deploy.

### Rollbacks and hotfixes

Because each deploy is a commit, rolling back is deploying an older commit: revert the bad commit on `main` and the
same workflow redeploys. The best-practices page: "Revert or roll back the affected bundle to the last known good
version", use a hotfix "only for urgent, narrowly scoped fixes", and "Merge any hotfix back to the main branch
immediately". Keep bundles small ("Put everything that a single team owns into one bundle") so that a rollback
touches one workload. Remember 16.1: rolling back code does not roll back data. If bad rows were written, the fix is
data work (Delta time travel or `RESTORE`, see [chapter 4](04-Delta-Lake.md), or a rerun of the fixed code from
bronze).

!!! warning "Common CI/CD mistakes"
    - Deploying to production from a laptop "just this once". The state and the job now reflect an uncommitted
      version. Production deploys come only from CI on `main`.
    - Using `bundle deploy --select` or `--force` in production pipelines; the page reserves `--select` for
      development.
    - Renaming the bundle or a target in `databricks.yml`: the next deploy creates new jobs and leaves the old ones
      running.
    - Setting `root_path` to `/Shared/...` for prod: every workspace user can change the deployed code.
    - Letting the deploying service principal also run the jobs with broad data access; split deploy and run-as
      principals.

## 16.10 Practice questions

*Level: mixed.*

**Q1. Why does a data pipeline need CI/CD even more than a web application?**

??? success "Answer"
    A pipeline has state: a bug writes wrong rows into silver and gold, and rolling back the code does not roll back
    the data. Pipelines also rerun (retries, repairs, backfills), so non-idempotent code fails later, not at once.
    And the job definition (schedule, compute, run-as, permissions) is part of the behavior, so it must be versioned
    and reviewed like code.

    **Why:** the Databricks principle "if something isn't in version control, it doesn't exist" applies to job
    configuration as much as to `.py` files; automation catches the bug before it reaches stateful tables.

**Q2. What are Declarative Automation Bundles, what was their old name, and what does a bundle contain?**

??? success "Answer"
    Infrastructure as code for Databricks, formerly Databricks Asset Bundles
    ([page](https://docs.databricks.com/aws/en/dev-tools/bundles/)). A bundle is a folder with `databricks.yml`
    (and included YAML files) that describes resources such as Lakeflow Jobs (formerly Databricks Jobs,
    [rename](https://docs.databricks.com/aws/en/release-notes/product/2025/june)) and Lakeflow pipelines (formerly
    [Delta Live Tables](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt)), plus the source files (notebooks, Python), tests and
    per-environment targets. The Databricks CLI validates, deploys and runs it.

    **Why:** the page calls a bundle "an end-to-end definition of a project, including how the project should be
    structured, tested, and deployed".

**Q3. A colleague runs `databricks bundle run -t prod --var="catalog=shop_backfill" silver_job` expecting the job to
write to `shop_backfill`. It writes to `shop`. Why, and what should they do?**

??? success "Answer"
    Bundle variables are resolved at deploy time; `bundle run` starts the job that was already deployed with
    `catalog = shop`. To change a value per run, pass a job parameter:
    `databricks bundle run -t prod --params catalog=shop_backfill silver_job` (the job maps `catalog` to a job
    parameter, and the notebook reads it with `dbutils.widgets.get`).

    **Why:** "Bundle variables are deployment-time variables ... passing different values for variables for the run
    of the job will not apply. Instead, pass values to a job run using job parameters."

**Q4. List four things development mode does on deploy.**

??? success "Answer"
    Prefixes resource names with `[dev <short user name>]` and tags jobs and pipelines `dev`; marks pipelines
    `development: true`; pauses all schedules and triggers; enables concurrent runs; disables the deployment lock;
    allows `--cluster-id` to override cluster definitions.

    **Why:** each makes a personal copy safe and fast to iterate on: it cannot fire on a schedule, cannot be mistaken
    for the real job, and can reuse an all-purpose cluster.

**Q5. What does production mode check?**

??? success "Answer"
    That pipelines are `development: false`; that the current Git branch equals the target's `git.branch` if one is
    set (`--force` overrides); and, if you do not use a service principal, that paths are not overridden to a user
    and that `run_as` and `permissions` are set. It also refuses `--cluster-id` overrides.

    **Why:** production mode turns the most common accidents (deploying a feature branch, a personal path, a dev
    pipeline) into validation errors. The page recommends service principals, enforced with `run_as`.

**Q6. You rename `bundle.name` from `redrock_silver` to `redrock_orders` and deploy to prod. What happens to the
existing job?**

??? success "Answer"
    The new name is a new bundle identity (the default `root_path` is `~/.bundle/${bundle.name}/${bundle.target}`),
    so the deploy creates a new job, and the old job is no longer tracked. Nothing deletes or pauses it, so it keeps
    its schedule and keeps running.
    Two jobs now load silver. Destroy the old deployment first (with the old name), or bind the existing job to the
    new bundle (`databricks bundle deployment bind`).

    **Why:** "Resource names are not used to correlate between a bundle deployment and a resource instance"; the
    state maps keys to IDs under the root path.

**Q7. What does `databricks bundle destroy -t dev` delete, and why must it never be in a production pipeline
casually?**

??? success "Answer"
    It "permanently deletes a bundle's previously-deployed jobs, pipelines, and artifacts. This action cannot be
    undone." It prompts unless `--auto-approve` is given. In CI there is no one to answer the prompt, so a script
    would need `--auto-approve`, which deletes the production jobs and pipelines without a second look. Use it for
    dev cleanup; protect critical resources with the `lifecycle` setting.

    **Why:** the command page documents the warning and the `lifecycle` setting "to prevent specific resources from
    being destroyed".

**Q8. A variable `catalog` has `default: shop_dev`, the `staging` target sets `catalog: shop_staging`, and CI runs
`BUNDLE_VAR_catalog=shop_tmp databricks bundle deploy -t staging`. Which value is used?**

??? success "Answer"
    `shop_tmp`. The order is `--var`, then `BUNDLE_VAR_` environment variables, then `variable-overrides.json`, then
    the target's `variables`, then the default.

    **Why:** the CLI looks in that order, "stopping when it finds a value for a variable"; environment variables
    come before target settings. A stray
    environment variable in CI can silently redirect a deploy, so keep them out of shared runners.

**Q9. Why should CI not use a personal access token of a team member?**

??? success "Answer"
    The pipeline would act with that person's full rights, stop working when they leave or rotate the token, and
    every action would be audited as them. A service principal can be granted exactly what CI needs, disabled
    without affecting people, and survives staff changes. Better still, use OAuth M2M or workload identity
    federation instead of any personal access token.

    **Why:** Databricks recommends "a Databricks service principal and its token instead of your Databricks user"
    and "OAuth machine-to-machine (M2M) authentication over personal access tokens for CI/CD workflows".

**Q10. OAuth M2M or workload identity federation for GitHub Actions? Explain the difference.**

??? success "Answer"
    Workload identity federation. With OAuth M2M, CI stores the service principal's client ID and OAuth secret and
    exchanges them for one-hour tokens; the secret must be stored, scoped and rotated. With federation, GitHub
    issues a signed token (JWT) for the workflow run, a federation policy on the service principal trusts that
    issuer and subject, and the CLI exchanges it for a Databricks OAuth token. Nothing secret is stored.

    **Why:** Databricks: workload identity federation "eliminates the need for Databricks secrets, which makes it the
    most secure way to authenticate your automated flows to Databricks."

**Q11. Which settings does a GitHub Actions job need for workload identity federation?**

??? success "Answer"
    `permissions: id-token: write` (so GitHub issues the token), and the environment variables
    `DATABRICKS_AUTH_TYPE: github-oidc`, `DATABRICKS_HOST` (the workspace URL) and `DATABRICKS_CLIENT_ID` (the
    service principal's application ID). With the recommended Environment entity type, the job also sets
    `environment: prod` (or staging), which becomes part of the token subject.

    **Why:** these are the values on [Enable workload identity federation for GitHub
    Actions](https://docs.databricks.com/aws/en/dev-tools/auth/provider-github).

**Q12. Federated deploys worked for months. After the repository was transferred to a new GitHub organization, every
deploy fails to authenticate. What is the likely cause?**

??? success "Answer"
    The federation policy's subject no longer matches the token's `sub` claim. The subject contains the organization
    and repository, and repositories created, renamed or transferred on or after July 15, 2026 use a format with
    numeric IDs (`repo:octo-org@123456/octo-repo@456789:environment:prod`). Update the policy's subject to the new
    exact value.

    **Why:** "Databricks matches the **Subject** against the token's `sub` claim exactly, and GitHub's `sub` format
    depends on when the repository was created."

**Q13. Why use separate service principals for deploying and for running the job?**

??? success "Answer"
    The deployment principal needs rights to create jobs and write the bundle folder, but almost no data access. The
    run-as principal needs `SELECT`/`MODIFY` on its own tables only. If the CI identity leaks, it cannot read
    production data; if you tighten data grants, deployments still work.

    **Why:** best-practices page: "Use separate service principals for deployment and runtime"; the deployment one
    "should have minimal data access". In the bundle, `run_as` sets the runtime identity.

**Q14. How do you stop a misconfigured dev job from writing into the production catalog?**

??? success "Answer"
    Bind the production catalog in `ISOLATED` mode to the production workspace only, so it is unreachable from the
    dev and staging workspaces whatever the grants say. Also parameterize the catalog per target (`shop_dev`,
    `shop_staging`, `shop`) so dev code never names the prod catalog.

    **Why:** Databricks: `ISOLATED` "ensures that production data is unreachable from development or staging
    environments, even if an identity is misconfigured."

**Q15. What does "promote code, not data" mean? How does staging get its data?**

??? success "Answer"
    The same commit is deployed to dev, staging and prod; each environment builds its tables from its own sources
    with that code. Tables are never copied from dev to prod. Staging is fed by its own (or sampled, masked)
    sources, so it exercises ingestion too.

    **Why:** a production table must always be the output of the deployed production code; a copied table hides
    which code built it, and copying production data down weakens its protection.

**Q16. When would you use a production Git folder instead of a bundle?**

??? success "Answer"
    When you can only deploy code files and have no external CI/CD pipeline, or an external orchestrator such as
    Airflow runs the notebooks. CI (or a person) pulls the folder to the latest `main`. The cost: job and pipeline
    configurations are not in source control.

    **Why:** Databricks recommends bundles and describes the Git folder approach as the option "when you don't have
    access to external CI/CD pipelines".

**Q17. Describe trunk-based development for a Databricks project.**

??? success "Answer"
    One long-lived branch, `main`, always deployable. Developers work in short-lived feature branches, test in the
    dev workspace (`bundle deploy -t dev`), and merge through a pull request with green CI. CI deploys `main` to
    staging and runs tests; when they pass, it deploys `main` to production.

    **Why:** Databricks recommends trunk-based branching "to minimize merge conflicts and ensure the main branch is
    always in a deployable state"; long-lived environment branches drift apart.

**Q18. Name the layers of testing for a Databricks pipeline and where each runs.**

??? success "Answer"
    Unit tests (pytest, local Spark, every pull request, no workspace); bundle validation (`validate`, or a deploy
    to a non-production workspace, every pull request); integration tests in staging (deploy and run the job end to
    end after merge); data tests (assertions on the real tables inside every run in every environment).

    **Why:** the first three are the Databricks best-practices "testing layers"; data tests exist because correct
    code can still receive wrong data.

**Q19. Why should the silver logic live in `.py` modules rather than in notebook cells?**

??? success "Answer"
    Functions in modules can be imported by pytest on a laptop or CI runner and tested with tiny DataFrames; notebook
    cells cannot be imported (and a notebook cannot be imported as a module at all on Databricks Runtime 16.0 and
    above). Modules also get normal code review and reuse. The notebook stays a thin entry point: read
    parameters, call the functions, write.

    **Why:** Databricks recommends storing Python functions and their tests outside notebooks and keeping notebooks
    as "thin orchestration and visualization layers".

**Q20. Classify each as unit, integration or data test: (a) `latest_per_order` keeps the newest event; (b) the job
in staging finishes and `shop_staging.silver.orders` exists; (c) after each load, bronze rows equal silver events
plus quarantine rows; (d) running `merge_orders` twice on a local Delta table changes nothing.**

??? success "Answer"
    (a) unit; (b) integration; (c) data test; (d) unit (it uses a local Delta table, but it tests one function
    with a known input, no workspace).

    **Why:** the difference is what is under test (one function, the deployed system, or the data itself) and where
    it runs.

**Q21. Why is the SparkSession fixture `scope="session"`, with one shuffle partition and a pinned time zone?**

??? success "Answer"
    Starting Spark costs seconds, so one session serves all tests. The default is 200 shuffle partitions; adaptive
    query execution coalesces small ones, but for five rows one partition is enough and keeps the suite fast and
    predictable. Spark parses and displays timestamps in the session time zone, so pin it to `UTC`; but `collect()`
    and `createDataFrame` from Python `datetime` values use the Python process's local zone, so also run the tests
    with `TZ=UTC`. Then the same test passes on every laptop and runner (16.7).

    **Why:** slow and machine-dependent tests get skipped or ignored; a suite must be fast and deterministic to be
    trusted.

**Q22. What does `assertDataFrameEqual(actual, expected)` check by default, and why is row order ignored?**

??? success "Answer"
    It compares the rows and the schema and prints a diff on failure. In PySpark 4.2.0 the defaults are
    `checkRowOrder=False`, `ignoreNullable=True`, `ignoreColumnOrder=False`, and `rtol=1e-05`/`atol=1e-08` for
    approximate float equality. Row order is ignored because Spark gives no order without `ORDER BY`.

    **Why:** comparing ordered lists of rows would make tests fail randomly when partitioning changes.

**Q23. Find the bug: this test passes on a laptop and fails now and then in CI.**

*A snippet to read for the bug; not run.*

```python
def test_latest(spark):
    out = latest_per_order(events).collect()
    assert out == [Row(order_id=1001, status="PLACED"), Row(order_id=1002, status="SHIPPED")]
```

??? success "Answer"
    `collect()` returns rows in whatever order the partitions produce them; nothing sorts them. Compare
    order-insensitively: `assertDataFrameEqual(latest_per_order(events), expected_df)` (default
    `checkRowOrder=False`), or sort both sides (`sorted(out)`), or add `orderBy("order_id")` before `collect()`.

    **Why:** row order after a shuffle depends on partitioning and timing; a flaky test is worse than none because
    people learn to ignore it.

**Q24. Find the bug: two events for order 1005 have the same `updated_at`. Sometimes silver keeps `SHIPPED`,
sometimes `CANCELLED`. What is wrong with `latest_per_order`, and how do you fix and test it?**

??? success "Answer"
    The window orders only by `updated_at`, so a tie is broken arbitrarily by `row_number`. Add a deterministic
    tie-breaker, for example a source sequence number or `_ingest_ts`, then a stable column:

    *A sketch, not run here.*

    ```python
    w = (Window.partitionBy("order_id")
               .orderBy(F.col("updated_at").desc(), F.col("_ingest_ts").desc(), F.col("status")))
    ```

    Test it with two rows that tie on `updated_at` and assert which one wins.

    **Why:** `row_number` over a non-unique order is non-deterministic; reruns can flip the result, which breaks
    idempotency in a way the rerun test of 16.7 only catches if its data contains a tie.

**Q25. Write the test: `type_orders` must turn amount `"12.5"` into `Decimal("12.50")` and currency `" usd "` into
`"USD"`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (In `tests/test_practice.py`; it passed in the run in 16.7.)

    ```python
    def test_amount_and_currency_are_normalized(spark):
        raw = spark.createDataFrame(
            [("1010", "7", "2026-03-03T09:00:00Z", "PLACED", "12.5", " usd ",
              "2026-03-03T09:00:00Z", "f.json")], BRONZE_DDL)
        row = type_orders(raw).first()
        assert (row.amount, row.currency) == (Decimal("12.50"), "USD")
    ```

    **Why:** one row, one function, one known answer. `try_cast` to `DECIMAL(10,2)` keeps two decimal places, and
    Python compares `Decimal("12.50")` exactly; a `float` would invite rounding surprises.

**Q26. Write the test: a NULL amount must be quarantined with the reason `amount not a number: NULL`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (Passed in the run in 16.7.)

    ```python
    def test_null_amount_is_quarantined_with_a_reason(spark):
        raw = spark.createDataFrame(
            [("1011", "7", "2026-03-03T09:00:00Z", "PLACED", None, "CAD",
              "2026-03-03T09:00:00Z", "f.json")], BRONZE_DDL)
        row = add_dq_errors(type_orders(raw)).first()
        assert row.dq_errors == ["amount not a number: NULL"]
    ```

    **Why:** NULL is the input most often forgotten. `concat` with a NULL returns NULL, so the function wraps the raw
    value in `coalesce(raw_amount, 'NULL')`; this test proves the message is not lost, and that `amount < 0` (NULL
    for a NULL amount) does not add a second reason.

**Q27. Write the test: silver must have exactly one row per `order_id`.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (Passed in the run in 16.7.)

    ```python
    def test_silver_has_one_row_per_order(bronze):
        silver, _ = bronze_to_silver(bronze)
        duplicates = silver.groupBy("order_id").count().where(F.col("count") > 1)
        assert duplicates.count() == 0
    ```

    **Why:** the fixture contains a duplicated event (1001 twice) and two states of 1002, so the test fails if
    deduplication is removed. A uniqueness test only means something if the input has duplicates.

**Q28. Write the test: an empty bronze batch must give empty silver and quarantine, with the contract schema.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (Passed in the run in 16.7.)

    ```python
    def test_empty_batch_gives_empty_silver_with_the_contract_schema(spark):
        silver, quarantine = bronze_to_silver(spark.createDataFrame([], BRONZE_DDL))
        assert silver.count() == 0 and quarantine.count() == 0
        assertSchemaEqual(silver.schema, SILVER_ORDERS_SCHEMA)
    ```

    **Why:** empty input is a real case (a holiday with no orders, an incremental run with nothing new). A creating
    `MERGE` or `saveAsTable` downstream must still get the right schema, not an empty DataFrame with guessed types.

**Q29. Write the test that proves `merge_orders` is safe to rerun. What exactly do you assert?**

??? success "Answer"
    Merge the batch into an empty Delta table, `collect()` the result, merge the same batch again, and assert the
    table equals the first result and that the last `DESCRIBE HISTORY` entry is a `MERGE` with
    `numTargetRowsInserted == "0"` and `numTargetRowsUpdated == "0"`. That is `test_merge_is_idempotent` in 16.7,
    which passed.

    **Why:** equal contents prove the outcome; the commit metrics prove the second run did no work. The `collect()`
    matters: a DataFrame re-reads the table, so without it the test compares the table with itself.

**Q30. Scenario: after a retry of the silver job, `shop.silver.orders_quarantine` has every bad row twice, but
`shop.silver.orders` is fine. Why?**

??? success "Answer"
    Silver is written with a `MERGE` keyed on `order_id`, which is idempotent. The quarantine table is written with
    `mode("append")` from a batch that re-reads the same bronze rows, so every rerun appends them again. Make it
    idempotent: overwrite it when the job rebuilds it from all of bronze (as the notebook in 16.3 does), or `MERGE`
    on a key such as (`_source_file`, `raw_order_id`), or process only new bronze rows with a checkpointed stream.

    **Why:** every write in a job must be safe to repeat, not just the main table; retries and repair runs rerun the
    whole task.

**Q31. Scenario: the unit tests pass on your laptop but fail in CI with
`ImportError: cannot import name 'DateOffset' from 'pandas.tseries.frequencies'` in the tests that use
`assertDataFrameEqual`. What happened?**

??? success "Answer"
    CI installed the newest pandas (3.x). With pandas and pyarrow present, PySpark 4.2.0's `assertDataFrameEqual`
    imports `pyspark.pandas`, which fails to import with pandas 3. Your laptop has pandas 2. Pin `pandas<3` (as
    PySpark's own warning recommends) and pin all test dependencies so CI and laptops match.

    **Why:** this exact failure happened while writing this chapter (pandas 3.1.1); the suite passed with pandas
    2.3.3. Unpinned dependencies make CI fail for reasons unrelated to your change.

**Q32. Scenario: you `pip install pyspark` into the virtual environment you use for Databricks Connect, and the
integration tests break. Why?**

??? success "Answer"
    "Databricks Connect and PySpark are mutually exclusive"; the page points to its "Conflicting PySpark
    installations" troubleshooting entry. Use separate virtual environments: one with `pyspark` and `delta-spark`
    for local unit tests, one with `databricks-connect` for tests against a workspace.

    **Why:** the Databricks Connect testing page states the conflict and links its troubleshooting entry.

**Q33. What does `databricks bundle validate` catch, and what does it not catch?**

??? success "Answer"
    It checks that the configuration files are syntactically correct, resolves the target, and warns about
    properties that are not in the resource schema; it prints the bundle's identity (name, target, host, user,
    path). It does not run your code, does not check that tables exist or that the run-as principal has grants, and
    does not prove the job succeeds. For that, deploy to a non-production workspace and run the job.

    **Why:** the best-practices page: "In CI, prefer `bundle deploy` to a non-production workspace to catch YAML and
    resource-mapping issues before production deploys."

**Q34. You deployed the bundle with `-t dev`. The job has a daily 6 a.m. schedule. Will it run tomorrow in dev?**

??? success "Answer"
    No. Development mode "Pauses all schedules and triggers on deployed resources". The dev copy, named
    `[dev <your short name>] redrock_silver_orders`, runs only when you start it (`bundle run -t dev silver_job`).
    To unpause one job in dev, set its `schedule.pause_status` to `UNPAUSED` explicitly.

    **Why:** otherwise every developer's copy would load data on the production schedule.

**Q35. Two developers deploy the same bundle to the dev workspace. Do their jobs collide? Do their tables?**

??? success "Answer"
    Their jobs do not: each deploy has its own `root_path` under the deployer's home folder and its own
    `[dev <name>]` prefix. Their tables can, if both jobs write to the same `shop_dev.silver.orders`. Use personal
    schemas in dev (for example the Databricks example sets `schema: ${workspace.current_user.short_name}` in the dev
    target) so each developer writes their own copy.

    **Why:** bundle identity covers workspace objects, not Unity Catalog tables; the best-practices page recommends a
    personal schema per user because "This prevents developers from overwriting each other's tables in a shared
    workspace."

**Q36. A production deploy fails with a Git branch validation error. Why, and what is the right fix?**

??? success "Answer"
    The prod target sets `git: branch: main`, and the deploy ran from another branch (for example a hotfix branch,
    or a workflow triggered on a pull request). Production mode checks that the current branch equals the target's
    branch. The right fix is to merge to `main` and let CI deploy; `--force` overrides the check and should not
    appear in a production pipeline.

    **Why:** the check exists to make "only `main` reaches production" a rule enforced by the tool.

**Q37. Write a SQL data test for the job: fail the run if any bronze row is neither in silver events nor in
quarantine.**

??? success "Answer"
    *Run here: Apache Spark 4.2 + Delta Lake 4.4.1.* (It returned NULL, meaning pass, in 16.8.)

    ```sql
    SELECT assert_true(
             (SELECT count(*) FROM bronze_orders) =
             (SELECT count(*) FROM silver_order_events) + (SELECT count(*) FROM quarantine_orders),
             'bronze rows were lost or duplicated on the way to silver') AS reconcile_check;
    ```

    **Why:** `assert_true` returns NULL when the condition holds and raises `USER_RAISED_EXCEPTION` otherwise, so the
    task, and the job, fails. In production, compare the counts for the batch just processed (for example by
    `_source_file` or ingest date), not the whole history, so the check stays cheap.

**Q38. Where do secrets live in this setup?**

??? success "Answer"
    Nowhere in the repository. CI to Databricks: no secret with workload identity federation (or an OAuth M2M
    secret in GitHub environment secrets). Jobs to source systems: Databricks secret scopes backed by the cloud
    secret manager, read at run time with `dbutils.secrets.get`. `databricks.yml` holds only IDs and names (host
    URLs, service principal application IDs, catalog names).

    **Why:** Databricks says not to commit "Tokens or credentials" and to use "workspace-level secret management
    backed by a cloud secret manager"; GitHub environment secrets are released only to jobs that reference the
    environment, after any required approval.

**Q39. A bad change reached production and the silver job wrote wrong statuses for two hours. Walk through the
recovery.**

??? success "Answer"
    1. Stop the damage: pause the job or let the failing data check stop it.
    2. Roll back the code: revert the commit on `main`; CI redeploys the last good version.
    3. Repair the data: the bad commits are in the Delta history, so restore silver to the version before them
       (time travel or `RESTORE`, chapter 4) and rerun the fixed code from bronze for the affected window; then
       rebuild the gold tables that read it.
    4. Prevent it: add the test that would have caught it, and the data test if a rule was missing.

    **Why:** code and data roll back separately. Bundles make the code rollback a normal deploy; Delta history and a
    bronze layer that keeps raw data make the data repair possible.

## Sources

- [CI/CD on Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/) (last updated Nov 5, 2026)
- [CI/CD workflows on Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/flows) (last updated Nov 5, 2026)
- [Developer best practices on Databricks](https://docs.databricks.com/aws/en/developers/best-practices) (last updated Nov 4, 2026)
- [GitHub Actions](https://docs.databricks.com/aws/en/dev-tools/ci-cd/github) (last updated Nov 4, 2026)
- [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/) (last updated Nov 5, 2026)
- [Configuration reference](https://docs.databricks.com/aws/en/dev-tools/bundles/reference) (last updated Nov 5, 2026)
- [Declarative Automation Bundles deployment modes](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes) (last updated Nov 4, 2026)
- [Substitutions and variables in Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/variables) (last updated Sep 14, 2026)
- [Specify a run identity for a Declarative Automation Bundles workflow](https://docs.databricks.com/aws/en/dev-tools/bundles/run-as) (last updated Oct 7, 2026)
- [Bundle configuration examples](https://docs.databricks.com/aws/en/dev-tools/bundles/examples) (last updated Oct 29, 2026)
- [Jobs API, Create a new job](https://docs.databricks.com/api/workspace/jobs/create) (`schedule.pause_status` default `UNPAUSED`; the API page shows no date, read Nov 11, 2026)
- [Develop a job with Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/jobs-tutorial) (last updated Nov 5, 2026)
- [Declarative Automation Bundles library dependencies](https://docs.databricks.com/aws/en/dev-tools/bundles/library-dependencies) (last updated Sep 11, 2026)
- [`bundle` command group](https://docs.databricks.com/aws/en/dev-tools/cli/bundle-commands) (last updated Nov 4, 2026)
- [Service principals for CI/CD](https://docs.databricks.com/aws/en/dev-tools/auth/service-principals) (last updated Nov 6, 2026)
- [Authorize Databricks service principal access to Databricks with OAuth](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-m2m) (last updated Oct 30, 2026)
- [Authenticate access to Databricks using OAuth token federation](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-federation) (last updated Sep 11, 2026)
- [Enable workload identity federation in CI/CD](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-federation-provider) (last updated Sep 11, 2026)
- [Enable workload identity federation for GitHub Actions](https://docs.databricks.com/aws/en/dev-tools/auth/provider-github) (last updated Oct 2, 2026)
- [CI/CD with Databricks Git folders](https://docs.databricks.com/aws/en/repos/ci-cd) (last updated Sep 11, 2026)
- [What happened to Databricks Repos?](https://docs.databricks.com/aws/en/repos/what-happened-repos) (last updated Sep 11, 2026)
- [Unit testing for Databricks notebooks](https://docs.databricks.com/aws/en/notebooks/testing) (last updated Jan 21, 2025)
- [Python unit testing in the workspace](https://docs.databricks.com/aws/en/files/python-unit-tests) (last updated Sep 11, 2026)
- [What are workspace files?](https://docs.databricks.com/aws/en/files/workspace) (last updated Sep 11, 2026)
- [Work with Python and R modules](https://docs.databricks.com/aws/en/files/workspace-modules) (last updated Sep 11, 2026)
- [Access parameter values from a task](https://docs.databricks.com/aws/en/jobs/parameter-use) (last updated Nov 5, 2026)
- [Testing for Databricks Connect for Python](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/python/testing) (last updated Sep 11, 2026)
- [Compute configuration for Databricks Connect](https://docs.databricks.com/aws/en/dev-tools/databricks-connect/cluster-config) (last updated Sep 11, 2026)
- [assert_true function](https://docs.databricks.com/aws/en/sql/language-manual/functions/assert_true) (last updated Sep 11, 2026)
- [Manage data quality with pipeline expectations](https://docs.databricks.com/aws/en/ldp/expectations) (last updated Oct 26, 2026)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/concepts/where-is-dlt) (last updated Sep 11, 2026)
- [June 2025 release notes](https://docs.databricks.com/aws/en/release-notes/product/2025/june) (last updated Oct 29, 2026)
- [Testing PySpark](https://spark.apache.org/docs/latest/api/python/getting_started/testing_pyspark.html) (Apache Spark docs, version 4.3.0 at reading, read Nov 11, 2026)
- [Spark 4.2.0 overview](https://spark.apache.org/docs/4.2.0/) (read Nov 11, 2026)
- [Spark 4.2.0 performance tuning](https://spark.apache.org/docs/4.2.0/sql-performance-tuning.html) (read Nov 11, 2026)
- [databricks/setup-cli README](https://github.com/databricks/setup-cli) (read from the repository's main branch, Nov 11, 2026)
- [GitHub docs: Deployments and environments](https://github.com/github/docs/blob/main/content/actions/reference/workflows-and-actions/deployments-and-environments.md) (source file read from the github/docs repository, Nov 11, 2026; docs.github.com was not reachable from here)
- [GitHub docs: Workflow syntax for GitHub Actions](https://github.com/github/docs/blob/main/content/actions/reference/workflows-and-actions/workflow-syntax.md) and the docs' action-version snippets (`data/reusables/actions/`) (source files read from the github/docs repository, Nov 11, 2026)
