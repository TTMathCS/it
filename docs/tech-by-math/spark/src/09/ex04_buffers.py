# Tech by Math, Spark tutorial 9: the partial buffers Spark 4.2 keeps for stddev and avg (read from the physical plan).
from pyspark.sql import SparkSession, functions as F
spark = SparkSession.builder.master("local[2]").config("spark.ui.enabled","false").getOrCreate(); spark.sparkContext.setLogLevel("ERROR")
df = spark.range(10).select((F.col("id")%2).alias("k"), F.col("id").cast("double").alias("x"))
for line in df.groupBy("k").agg(F.stddev("x"), F.avg("x")).\
    _jdf.queryExecution().executedPlan().toString().splitlines():
    if "Aggregate" in line: print(line.strip()[:220])
spark.stop()
