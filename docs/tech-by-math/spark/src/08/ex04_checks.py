# Tech by Math, pilot: checks behind the exercises (answers in the tutorial come from this output).
import math, sys
import numpy as np
sys.path.insert(0, sys.argv[1])
from ex03_murmur3 import murmur3_int, pmod
from pyspark.sql import SparkSession, functions as F

print("== E1: customers 1..6 into n = 4")
rows = {1: 100, 2: 50, 3: 70, 4: 30, 5: 40, 6: 10}
load = [0] * 4
for c, r in rows.items():
    p = pmod(murmur3_int(c), 4); load[p] += r
    print(f"customer {c}: hash {murmur3_int(c)}, partition {p}")
print("loads", load, "mean", sum(load) / 4, "max/mean", round(max(load) / (sum(load) / 4), 2))

print("\n== E3: keys needed for max within 10% of mean, n = 200")
n = 200
per = 2 * math.log(n) / 0.1 ** 2
print(f"K/n >= {per:.1f}, K >= {per * n:.0f}")

print("\n== E4: hot key 600,000 of 2,000,000, n = 100, cold per partition 14,000")
rng = np.random.default_rng(7)
for k in (100, 1000, 10000):
    mx = [np.bincount(rng.integers(0, 100, size=k), minlength=100).max() for _ in range(200)]
    avg = float(np.mean(mx)); f = k / 100 + math.sqrt(2 * (k / 100) * math.log(100))
    print(f"k = {k}: slice = {600000 / k:.0f} rows, avg max slices (sim) = {avg:.1f} (formula {f:.1f}), "
          f"worst partition ~ {600000 / k * avg + 14000:.0f} vs mean 20000")

spark = (SparkSession.builder.master("local[2]").config("spark.ui.enabled", "false").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
print("\n== E8: hash of two columns")
df = spark.createDataFrame([(7, s) for s in range(4)], "customer_id int, salt int")
for r in df.select("customer_id", "salt", F.hash("customer_id", "salt").alias("h")).collect():
    mine = murmur3_int(r["salt"], seed=murmur3_int(r["customer_id"]) & 0xFFFFFFFF)
    print(f"(7, {r['salt']}): spark {r['h']}, by hand {mine}, partition n=8: {pmod(r['h'], 8)}")

print("\n== E8: partition(key, 200) by hand vs Spark for keys 1..1000")
sp = [r["p"] for r in spark.range(1, 1001).select(F.pmod(F.hash(F.col("id").cast("int")), F.lit(200)).alias("p")).collect()]
mine = [pmod(murmur3_int(k), 200) for k in range(1, 1001)]
print("agree:", sum(a == b for a, b in zip(sp, mine)), "of 1000")

print("\n== E6: does Spark drop NULL keys before the shuffle?")
o = spark.createDataFrame([(1, None), (2, 5)], "order_id int, promo_id int")
p = spark.createDataFrame([(5, "AUTUMN")], "promo_id int, code string")
spark.conf.set("spark.sql.autoBroadcastJoinThreshold", "-1")
print("-- inner join"); o.join(p, "promo_id", "inner").explain()
print("-- left join"); o.join(p, "promo_id", "left").explain()
spark.stop()
