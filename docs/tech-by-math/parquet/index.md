# Apache Parquet

*The math under column files: how Parquet makes a table several times smaller than CSV, and how a filter can read only a few percent of it. Worked on a million orders written with pyarrow, with every size predicted by hand and then read from the file itself.*

| Tutorial | The question it answers |
| --- | --- |
| [1. Column files: run-length, dictionary coding, min/max skipping](01-Column-Files.md) | Why is the Parquet copy several times smaller, and why does a date filter read so little of it? |

The practical side is the [Databricks book](../../data-engineering/databricks/index.md), chapters 4 and 22. [How a tutorial works](../index.md#how-a-tutorial-works).
