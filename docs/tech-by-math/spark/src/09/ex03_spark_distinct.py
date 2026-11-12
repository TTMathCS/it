# Tech by Math, Spark tutorial 9: exact against approximate distinct counts, and the size of a
# percentile_approx summary for three accuracies. Spark 4.2, local mode.
# Shuffle sizes are the sum over all stages of the query, read from Spark's monitoring API.
import json
import time
import urllib.request
from pyspark.sql import SparkSession, functions as F

spark = (SparkSession.builder.master("local[4]").config("spark.ui.port", "4047")
         .config("spark.sql.adaptive.enabled", "false").config("spark.ui.showConsoleProgress", "false")
         .config("spark.sql.shuffle.partitions", "4").getOrCreate())
sc = spark.sparkContext
sc.setLogLevel("ERROR")
api = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # localhost: no proxy
base = f"http://localhost:4047/api/v1/applications/{sc.applicationId}"


def stages():
    time.sleep(1)
    return {s["stageId"]: s for s in json.load(api.open(base + "/stages?status=complete"))}


N = 1_000_000
df = spark.range(0, N, numPartitions=4).select((F.col("id") % 10).alias("k"),
                                               ((F.col("id") * 7919) % 100_003).alias("x"))
exact_total = df.select("x").distinct().count()
print(f"Distinct x values in the whole table (exact): {exact_total:,}")
print("Per group k (10 groups), all shuffles of the query added up:")
for name, agg in (("count_distinct", F.count_distinct("x")),
                  ("approx_count_distinct rsd 0.05", F.approx_count_distinct("x")),
                  ("approx_count_distinct rsd 0.01", F.approx_count_distinct("x", 0.01))):
    before = set(stages())
    rows = sorted(df.groupBy("k").agg(agg.alias("d")).collect())
    new = [s for i, s in stages().items() if i not in before]
    recs = sum(s["shuffleWriteRecords"] for s in new)
    byts = sum(s["shuffleWriteBytes"] for s in new)
    print(f"   {name:<31}: {recs:>9,} rows, {byts:>10,} bytes through the shuffle; group 0 -> {rows[0]['d']:,}, group 1 -> {rows[1]['d']:,}")
truth = {r["k"]: r["d"] for r in df.groupBy("k").agg(F.count_distinct("x").alias("d")).collect()}
for rsd in (0.05, 0.01):
    est = {r["k"]: r["d"] for r in df.groupBy("k").agg(F.approx_count_distinct("x", rsd).alias("d")).collect()}
    errs = [abs(est[k] - truth[k]) / truth[k] for k in sorted(truth)]
    print(f"   rsd {rsd}: relative errors of the 10 groups: " + ", ".join(f"{e:.2%}" for e in errs)
          + f";  largest {max(errs):.2%}")
print("\nThe same 10 groups: percentile_approx(x, 0.5, accuracy), 25,000 rows per group in each of the 4 input partitions")
for acc in (100, 1000, 10000):
    before = set(stages())
    df.groupBy("k").agg(F.percentile_approx("x", 0.5, acc)).collect()
    new = [s for i, s in stages().items() if i not in before]
    print(f"   accuracy {acc:>6}: {sum(s['shuffleWriteRecords'] for s in new):>3} rows, "
          f"{sum(s['shuffleWriteBytes'] for s in new):>10,} bytes through the shuffle")
spark.stop()
