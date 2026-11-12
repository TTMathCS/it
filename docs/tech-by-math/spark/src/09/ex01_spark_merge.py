# Tech by Math, Spark tutorial 9: what crosses the shuffle when Spark 4.2 adds up, and what an exact median keeps.
# Local mode, 4 input partitions. Shuffle sizes are read from Spark's own monitoring API (the UI's REST endpoint).
import json
import time
import urllib.request
from pyspark.sql import SparkSession, functions as F

spark = (SparkSession.builder.master("local[4]").config("spark.ui.port", "4047")
         .config("spark.sql.adaptive.enabled", "false").config("spark.ui.showConsoleProgress", "false").config("spark.sql.shuffle.partitions", "4").getOrCreate())
sc = spark.sparkContext
sc.setLogLevel("ERROR")
api = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # localhost: no proxy


def last_shuffle(label):
    """Shuffle records and bytes written by the newest stage that wrote any."""
    time.sleep(1)
    base = f"http://localhost:4047/api/v1/applications/{sc.applicationId}"
    stages = json.load(api.open(base + "/stages?status=complete"))
    s = max((s for s in stages if s["shuffleWriteRecords"] > 0), key=lambda s: s["stageId"])
    print(f"   {label}: {s['shuffleWriteRecords']:>3} rows, {s['shuffleWriteBytes']:>10,} bytes written to the shuffle")


N = 1_000_000
df = spark.range(0, N, numPartitions=4).select((F.col("id") % 10).alias("k"),
                                               ((F.col("id") * 7919) % 100_003).cast("double").alias("x"))
print("Part 1. A million rows, 10 groups, 4 input partitions: what each aggregate sends through the shuffle")
for name, agg in (("count", F.count("x")), ("sum", F.sum("x")), ("avg", F.avg("x")),
                  ("percentile_approx(x, 0.5, 10000)", F.percentile_approx("x", 0.5, 10000)),
                  ("exact median", F.median("x")), ("collect_list", F.collect_list("x"))):
    df.groupBy("k").agg(agg.alias("a")).select(F.size("a") if name == "collect_list" else "a").collect()
    last_shuffle(f"{name:<34}")

print("\nPart 2. The plans of a sum, an exact median and an approximate one")
for name, agg in (("sum", F.sum("x")), ("exact median", F.median("x")),
                  ("percentile_approx", F.percentile_approx("x", 0.5, 10000))):
    print(f"   -- {name}")
    plan = df.groupBy("k").agg(agg)._jdf.queryExecution().executedPlan().toString()
    for line in plan.splitlines():
        if "Aggregate" in line:
            print("   " + line.strip()[:150])

print("\nPart 3. Exact against approximate median of the million x values")
exact = df.agg(F.median("x")).first()[0]
xs = sorted(r[0] for r in df.select("x").collect())
for acc in (100, 1000, 10000):
    approx = df.agg(F.percentile_approx("x", 0.5, acc)).first()[0]
    rank = sum(1 for v in xs if v <= approx)  # where the answer really sits in the sorted data
    print(f"   accuracy {acc:>6}: answer {approx:>9.1f}, its rank {rank:>7,} of {N:,} "
          f"(the middle is {N // 2:,}; off by {abs(rank - N // 2) / N:.4%} of the rows; allowed 1/accuracy = {1 / acc:.4%})")
print(f"   exact median: {exact}; the two middle values of the sorted data: {xs[N // 2 - 1]}, {xs[N // 2]}")

print("\nPart 4. The same doubles summed in 1, 4 and 16 partitions")
vals = spark.range(0, N).select((F.lit(0.1) * (F.col("id") % 7 + 1)).alias("v"))
for p in (1, 4, 16):
    print(f"   {p:>2} partitions: {repr(vals.repartition(p, 'v').agg(F.sum('v')).first()[0])}")
print(f"   exact (as a fraction): sum of 0.1 x (i % 7 + 1) = {sum((i % 7 + 1) for i in range(N)) / 10}")
spark.stop()
