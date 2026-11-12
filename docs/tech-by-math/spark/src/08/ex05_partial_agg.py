# Tech by Math, pilot: a groupBy sum adds up inside each map task before the shuffle (partial aggregation).
from pyspark.sql import SparkSession, functions as F
spark = (SparkSession.builder.master("local[2]").config("spark.ui.enabled", "false")
         .config("spark.sql.adaptive.enabled", "false").config("spark.sql.shuffle.partitions", "8").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
orders = spark.range(0, 300000, numPartitions=4).select(
    F.col("id").alias("order_id"),
    F.when(F.col("id") % 5 != 0, F.lit(7)).otherwise(((F.col("id") / 5) % 1000 + 1).cast("int")).alias("customer_id"),
    ((F.col("id") * 37) % 500 + 1).cast("double").alias("amount"))
print("-- groupBy(customer_id).sum(amount)")
orders.groupBy("customer_id").agg(F.sum("amount")).explain()
# rows that cross the shuffle = partial rows: one per (map task, customer) present in that task
partial = orders.withColumn("map_task", F.spark_partition_id()).groupBy("map_task", "customer_id").count()
print("input partitions (map tasks):", orders.rdd.getNumPartitions())
print("rows entering the shuffle for customer 7:", partial.filter("customer_id = 7").count(),
      "| all partial rows:", partial.count(), "| input rows: 300000")
print("-- groupBy(customer_id).collect_list(amount)")
orders.groupBy("customer_id").agg(F.collect_list("amount")).explain()
spark.stop()
