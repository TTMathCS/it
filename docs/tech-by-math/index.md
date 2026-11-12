# Tech by Math

*The mathematics under the systems people use every day, one course per system: databases, Spark, Kafka, search, Kubernetes, git, certificates, networks and AI. Each course is built to be learned with a pencil.*

## The systems

| System | What is there now |
| --- | --- |
| [PostgreSQL](postgresql/index.md) | 4 checked tutorials: joins and NULL logic, B-tree indexes, the planner's row estimates, serializable transactions |
| [Apache Parquet](parquet/index.md) | 1 checked tutorial: column files, compression and min/max skipping |
| [Apache Spark](spark/index.md) | The 2025 drafts (7 parts) and 2 checked tutorials: shuffles and skew; which aggregates split (sums, medians, distinct counts) |
| [Apache Kafka](kafka/index.md) | The 2025 drafts (7 parts) and 1 checked tutorial: the log, offsets and lag |
| [Elasticsearch](elasticsearch/index.md) | The 2025 drafts (7 parts) and 1 checked tutorial: the inverted index, BM25 and shards |
| [Dremio](dremio/index.md) | The 2025 drafts (7 parts) and 1 checked tutorial: columns, files and reflections |
| [Apache NiFi](nifi/index.md) | The 2025 drafts (7 parts) |
| [Kubernetes](kubernetes/index.md) | The 2025 drafts (7 parts) and 1 checked tutorial: the scheduler and the autoscaler |
| [Git](git/index.md) | The 2025 drafts (7 parts) and 1 checked tutorial: hashes, the commit graph and merges |
| [PKI and certificates](pki/index.md) | The 2025 drafts (7 parts) and 1 checked tutorial: signatures and certificate chains |
| [Computer networks](network/index.md) | The 2025 drafts (7 parts) and 1 checked tutorial: addresses, routes and throughput |
| [AI](ai/index.md) | The 2025 drafts (7 parts) |
| [AI agents](ai-agent/index.md) | The 2025 drafts: concepts, tools and use cases |

**The 2025 drafts** were written in August 2025 and moved here as they were. They have not been checked yet: some formulas have no source, some "proofs" claim more than is true, and the people in their stories are invented. Each part of each system follows the same seven steps: the core model, the math toolkit, the algorithms, the failure models, experiments, references and use cases.

## How a tutorial works

The **checked tutorials** follow one shape:

1. **The question.** One real situation, such as "one Spark task runs 40 minutes while 199 take 2".
2. **The idea in plain words**, with a drawing.
3. **The math by hand.** A tiny example you can do on paper, every step shown.
4. **Why it is true.** A short proof or argument, with its assumptions stated. A rule of thumb is labelled as one.
5. **See it in the real system.** Queries and scripts that were run, with their real output; the scripts are linked from each tutorial.
6. **Where it breaks.** The limits and the known failures.
7. **Exercises**, from pencil to small code. Answers are folded: try first, then open.
8. **What I saw at work**, a box for your own notes, and **further reading**.

**How to learn from one:** read up to "the math by hand", close the page, redo the example on paper, then do the exercises before opening any answer. About three hours each.

The math itself is taught on the sister sites, so these tutorials link to it instead of repeating it: [Math](https://math.akadian.ca/) (probability, statistics, linear algebra, logic), [Computer science](https://cs.akadian.ca/) (algorithms, machine learning), [Networks](https://networks.akadian.ca/) and [Cryptography](https://cryptography.akadian.ca/).
