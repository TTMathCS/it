---
robots: noindex, nofollow
search:
  exclude: true
hide:
  - navigation
  - toc
---

# Systems I have worked with

The systems I have used and looked after in DevOps work, in alphabetical order, with the parts of each I worked on.
Some I know in depth, others only as far as the job needed.

| System | Components | What it is for |
|---|---|---|
| Ansible | AAP, AWX | Automates server setup and changes with playbooks; AAP and AWX run them from a web console. |
| Argo CD | | Keeps Kubernetes clusters in step with the configuration stored in Git (GitOps). |
| Artifactory | | Stores build artifacts and packages for many languages in one repository manager. |
| Certificates | certificate monitoring, certificate process | Issuing, renewing and watching the TLS certificates that services use, before they expire. |
| Cryptography | | Keys, ciphers and signatures behind secure connections and stored secrets. |
| Dell ECS | | Dell's object storage platform, with an S3-compatible interface. |
| Docker | image registry, image scanning | Packages applications as container images; the registry stores them and scanning checks them for known flaws. |
| Dremio | Dremio pipelines, Parquet | A query engine for data lakes; Parquet is the column file format it reads. |
| Dynatrace | | Monitors applications and infrastructure, and traces requests across services. |
| Elasticsearch | ES tools, Kibana, Logstash | Search and log analytics; Logstash brings data in and Kibana shows it. |
| GCP | Cloud SQL, Composer (Airflow), Dataproc, Deployment, Environments, Filestore, GCS, IAM, KMS, Monitoring and logging, Networking, Secret Manager, Vulnerabilities, Qlik, Tamr | Google Cloud: managed databases, workflows, Spark and Hadoop clusters, storage, access control, keys and networks. |
| Git / Bitbucket | | Version control for code and configuration, hosted on Bitbucket. |
| Grafana | | Dashboards and alerts over metrics and logs. |
| Guacamole | | Remote desktop and SSH access through a web browser. |
| Helm | | Packages and installs applications on Kubernetes as charts. |
| Jenkins | installation, jobs | Builds, tests and deploys software through automated jobs. |
| Kafka | Confluent, Kadeck, Schema Registry | Streams events between systems; Schema Registry keeps message formats in check, Kadeck is a tool to look inside topics. |
| Kerberos | | Network sign-in with tickets, so passwords are not sent over the network. |
| Kubernetes | cert-manager, CNI, etcd, ingress-nginx, local clusters, Longhorn, operators, Rancher, RKE, storage | Runs containers across a cluster of machines, with networking, storage and certificates as add-ons. |
| LDAP / Active Directory | | Directories of users and groups that many systems use for sign-in. |
| Linux | RHEL upgrade | The server operating system; keeping Red Hat Enterprise Linux up to date. |
| MinIO | | Object storage with an S3-compatible interface, run on your own servers. |
| MySQL | | A widely used open-source relational database. |
| Network | | Addresses, routing, firewalls and name lookup between systems. |
| NGINX | | Web server and reverse proxy in front of applications. |
| NiFi | NiFi operators, NiFi Registry, NiFi Toolkit | Moves and transforms data between systems through visual flows. |
| Oracle | | A commercial relational database. |
| PostgreSQL | | An open-source relational database. |
| Prometheus | Alertmanager | Collects metrics over time; Alertmanager sends the alerts. |
| Proxy | | Forwards traffic between networks and controls what may pass. |
| Salt | | Configuration management and remote commands across many servers. |
| Spark (on-premises) | | Distributed data processing on your own cluster. |
| SSH | | Secure remote sign-in and file copy. |
| SSO | | Single sign-on: one login for many applications. |
| Tenable | | Scans systems for vulnerabilities. |
| Terraform | | Builds and changes infrastructure from code. |
| Vault | | Stores secrets and hands them out with access control. |
| VDS | | |
| Vulnerabilities | | Finding, ranking and fixing security weaknesses across systems. |
| Windows | | Microsoft's operating system on servers and desktops. |
| ZooKeeper | | Keeps configuration and coordinates distributed systems such as Kafka and NiFi. |
| General operations | accounts, cron jobs, dev tools, SA tools, servers | Everyday administration: user accounts, scheduled jobs, tools and the servers themselves. |
