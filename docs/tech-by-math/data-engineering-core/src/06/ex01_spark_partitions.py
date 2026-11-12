# Tech by Math, pilot "Shuffles and skew in Spark": every Spark number in the tutorial comes from this script.
# Runs on local Apache Spark 4.2.0 (local[2]). AQE is off so that the partition counts asked for are kept.
from pyspark.sql import SparkSession, functions as F

spark = (SparkSession.builder.master("local[2]").appName("tbm-pilot")
         .config("spark.sql.adaptive.enabled", "false")
         .config("spark.ui.enabled", "false")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
print("Spark", spark.version)

def loads(df, label):
    rows = (df.withColumn("p", F.spark_partition_id()).groupBy("p").count().collect())
    counts = {r["p"]: r["count"] for r in rows}
    n = df.rdd.getNumPartitions()
    lst = [counts.get(i, 0) for i in range(n)]
    total = sum(lst)
    print(f"{label}: rows per partition = {lst}; max = {max(lst)}, mean = {total / n:.1f}, max/mean = {max(lst) / (total / n):.2f}")
    return lst

# 1. The real hash values for customers 1..8, and the partition each lands in for n = 3
print("\n== 1. Spark's hash of customer_id and the partition for n = 3")
ids = spark.range(1, 9).select(F.col("id").cast("int").alias("customer_id"))
ids.select("customer_id",
           F.hash("customer_id").alias("hash"),
           F.pmod(F.hash("customer_id"), F.lit(3)).alias("pmod_3")).show()

# 2. Is "partition = pmod(hash(key), n)" really what repartition does? Check on every row.
print("== 2. repartition(n, key) puts each row in pmod(hash(key), n)")
small = spark.range(0, 20000).select((F.col("id") % 997).cast("int").alias("customer_id"))
for n in (3, 8, 200):
    r = small.repartition(n, "customer_id").withColumn("actual", F.spark_partition_id()) \
             .withColumn("predicted", F.pmod(F.hash("customer_id"), F.lit(n)))
    bad = r.filter("actual <> predicted").count()
    print(f"n = {n}: rows = {r.count()}, rows where actual <> predicted = {bad}")

# 3. A hot key: 300,000 orders, customer 7 places 80% (240,000); the rest spread over customers 1..1000
print("\n== 3. Hot key: 300,000 orders, customer 7 has 240,000")
orders = spark.range(0, 300000).select(
    F.col("id").alias("order_id"),
    F.when(F.col("id") % 5 != 0, F.lit(7))
     .otherwise(((F.col("id") / 5) % 1000 + 1).cast("int")).alias("customer_id"),
    ((F.col("id") * 37) % 500 + 1).cast("double").alias("amount"))
top = orders.groupBy("customer_id").count().orderBy(F.desc("count")).limit(3).collect()
print("largest keys:", [(r["customer_id"], r["count"]) for r in top])
n = 8
l = loads(orders.repartition(n, "customer_id"), "by customer_id, n = 8")
h = top[0]["count"]
print(f"lower bound max(total/n, largest key) = max({300000 / n:.0f}, {h}) = {max(300000 / n, h):.0f}; measured max = {max(l)} ({max(l) / h:.3f} x the bound)")

# 4. Salting the hot key with k salt values
print("\n== 4. Salting: key becomes (customer_id, salt), salt = order_id % k")
for k in (2, 4, 8, 16, 32, 64, 256):
    salted = orders.withColumn("salt", F.col("order_id") % k)
    loads(salted.repartition(n, "customer_id", "salt"), f"k = {k:>3}")
# Two-stage sum gives the same answer as the plain sum
k = 16
salted = orders.withColumn("salt", F.col("order_id") % k)
stage1 = salted.groupBy("customer_id", "salt").agg(F.sum("amount").alias("part"))
stage2 = stage1.groupBy("customer_id").agg(F.sum("part").alias("total"))
plain = orders.groupBy("customer_id").agg(F.sum("amount").alias("total"))
print("two-stage salted sum equals plain sum:", sorted(stage2.collect()) == sorted(plain.collect()))
print("partial rows after stage 1:", stage1.count(), "(keys:", plain.count(), ")")

# 5. NULL keys all hash to the same value
print("\n== 5. NULL keys")
nulls = spark.createDataFrame([(None,), (None,), (5,)], "customer_id int")
nulls.select("customer_id", F.hash("customer_id").alias("hash"),
             F.pmod(F.hash("customer_id"), F.lit(8)).alias("pmod_8")).show()
promo = spark.range(0, 100000).select(
    F.when(F.col("id") % 10 < 4, F.lit(None).cast("int"))
     .otherwise((F.col("id") % 5000).cast("int")).alias("promo_id"))
loads(promo.repartition(8, "promo_id"), "promo_id with 40% NULL, n = 8")

# 6. No hot key, but few keys: equal keys hashed by Spark's real hash into n = 200
print("\n== 6. Equal-sized keys through Spark's real hash, n = 200")
for K in (2000, 20000, 200000, 1000000):
    keys = spark.range(0, K).select(F.pmod(F.hash(F.col("id").cast("int")), F.lit(200)).alias("p"))
    c = [r["count"] for r in keys.groupBy("p").count().collect()]
    c += [0] * (200 - len(c))
    print(f"K = {K:>8}: mean = {K / 200:.0f}, max = {max(c)}, min = {min(c)}, max/mean = {max(c) / (K / 200):.3f}")

spark.stop()
