from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .master("local[*]")
    .appName("verify-hadoop-classes")
    .getOrCreate()
)

version = spark._jvm.org.apache.hadoop.util.VersionInfo.getVersion()
default_fs = spark.sparkContext._jsc.hadoopConfiguration().get("fs.defaultFS")

print("Hadoop version visible to Spark:", version)
print("fs.defaultFS:", default_fs)

spark.stop()
