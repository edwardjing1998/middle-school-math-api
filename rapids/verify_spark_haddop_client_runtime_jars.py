import os
import pyspark

pyspark_dir = os.path.dirname(pyspark.__file__)
jars_dir = os.path.join(pyspark_dir, "jars")

print("PySpark package:", pyspark_dir)
print("Jars folder:", jars_dir)

if not os.path.isdir(jars_dir):
    raise SystemExit("ERROR: PySpark jars folder does not exist")

jars = sorted(os.listdir(jars_dir))

print("Total JAR files:", len(jars))

keywords = ["hadoop", "hdfs", "yarn", "mapreduce"]
matched = [jar for jar in jars if any(k in jar.lower() for k in keywords)]

print()
print("Hadoop/HDFS/YARN related JARs:")
for jar in matched[:100]:
    print("  " + jar)

print()
required_keywords = ["hadoop-client-api", "hadoop-client-runtime"]

missing = []
for keyword in required_keywords:
    if not any(keyword in jar.lower() for jar in jars):
        missing.append(keyword)

if missing:
    print("WARNING: Missing expected JAR keyword(s):", ", ".join(missing))
else:
    print("OK: Found Hadoop client API/runtime JARs")
