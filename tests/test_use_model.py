from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel

spark = SparkSession.builder \
    .appName("UseDocumentQualityClassifier") \
    .master("local[*]") \
    .getOrCreate()

model_path = "/home/edward/projects/cuda-python-demo/models/document-quality-classifier"

model = PipelineModel.load(model_path)

df = spark.createDataFrame([
    (1, "This is a clear math homework document with complete questions and answers."),
    (2, "Bad scan unreadable random symbols missing text."),
    (3, "This article explains Spark ML classification and model training."),
    (4, "This technical document explains Java JDBC connection to Oracle database using spark sql."),
], ["id", "text"])

result = model.transform(df)

result.show(truncate=False)

spark.stop()