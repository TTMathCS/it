# Start here

*How this site works, and where to begin.*

## How the site is laid out

Every system has its own course, and every course sits in a category. The address says both:
`it.akadian.ca/databases/sql/` is the SQL course in the Databases category. The **Books** tab lists the categories;
open one to see its courses, and open a course to see its chapters.

| Category | What goes there |
| --- | --- |
| Databases | The SQL language, and each database system (PostgreSQL, MySQL, SQL Server, Oracle, MongoDB, Redis ...) |
| Data engineering | Moving and shaping data at scale: Databricks and the medallion model, Spark, Airflow, dbt, Kafka |
| Data warehouses and BI | Snowflake, BigQuery, Redshift, Power BI, Tableau |
| Programming | [WebAssembly](../programming/webassembly/index.md) (how PostgreSQL runs in a browser); later Python, Java, JavaScript, Bash. SQL lives under Databases and is linked from here |
| Cloud | AWS, Azure, Google Cloud |
| DevOps | Git, Docker, Kubernetes, Terraform, CI/CD |
| Servers and operating systems | Linux, Windows Server, virtual machines |
| Enterprise applications | ERP, CRM and IT service management systems |
| Identity and security | Directories, single sign-on, access control (network security is on [networks.akadian.ca](https://networks.akadian.ca/)) |
| Monitoring and operations | Logs, metrics, alerts, incidents |
| AI and machine learning | Models, pipelines and the platforms that run them |
| Interview prep | Practice for coding tests such as Codility |

A category appears in the menu once its first course is written.

## How a course works

- **Chapters in order.** Each chapter needs only the ones before it, and opens with a box saying what it covers and
  what you need first.
- **Real results.** Every example is run on a real system, and the result shown under it is what the system really
  printed. The line above each result says where it was run.
- **Practice with hidden answers.** Each chapter ends with questions. The answer and the explanation are folded
  underneath: try first, then open.
- **Interview tips** name the usual wrong answer and show it failing.

## Where to begin

- [SQL interview fast track](../databases/sql/fast-track.md): a two-day plan through the SQL course.
- [SQL cheat sheet](../databases/sql/cheat-sheet.md): the whole language on one page.
- [The sample database](../databases/sql/sample-database.md): the small shop every SQL example uses, ready to load
  on your own computer.
