import os
import pyspark

spark_home = os.path.dirname(pyspark.__file__)
print("PySpark package:", spark_home)
print("Jars folder:", os.path.join(spark_home, "jars"))