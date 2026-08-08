from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import Tokenizer, StopWordsRemover, HashingTF, IDF
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.evaluation import BinaryClassificationEvaluator


spark = SparkSession.builder \
    .appName("TrainDocumentQualityClassifier") \
    .master("local[*]") \
    .getOrCreate()

# 1. Labeled training documents
training_docs = spark.createDataFrame([
    (1, "This technical document explains Java JDBC connection to Oracle database.", 1.0),
    (2, "This article explains Spark ML classification and model training.", 1.0),
    (3, "This tutorial describes customer risk scoring using machine learning.", 1.0),
    (4, "This page explains Apache Spark pipelines and feature engineering.", 1.0),
    (5, "Oracle JDBC connection troubleshooting guide for developers.", 1.0),

    (6, "Buy now!!! Discount discount discount!!!", 0.0),
    (7, "Home about contact privacy policy login menu.", 0.0),
    (8, "Click here click here click here free free free.", 0.0),
    (9, "Advertisement sponsored link limited offer!!!", 0.0),
    (10, "Navigation footer copyright terms conditions.", 0.0)
], ["doc_id", "text", "label"])

# 2. Split data
train_data, test_data = training_docs.randomSplit([0.8, 0.2], seed=42)

# 3. Text processing stages
tokenizer = Tokenizer(
    inputCol="text",
    outputCol="words"
)

remover = StopWordsRemover(
    inputCol="words",
    outputCol="filtered_words"
)

hashing_tf = HashingTF(
    inputCol="filtered_words",
    outputCol="raw_features",
    numFeatures=1000
)

idf = IDF(
    inputCol="raw_features",
    outputCol="features"
)

# 4. Classification algorithm
lr = LogisticRegression(
    featuresCol="features",
    labelCol="label",
    predictionCol="prediction",
    probabilityCol="probability",
    rawPredictionCol="rawPrediction"
)

# 5. Build pipeline
pipeline = Pipeline(stages=[
    tokenizer,
    remover,
    hashing_tf,
    idf,
    lr
])

# 6. Train model
model = pipeline.fit(train_data)

# 7. Evaluate model
predictions = model.transform(test_data)

predictions.select(
    "doc_id",
    "text",
    "label",
    "probability",
    "prediction"
).show(truncate=False)

evaluator = BinaryClassificationEvaluator(
    labelCol="label",
    rawPredictionCol="rawPrediction",
    metricName="areaUnderROC"
)

auc = evaluator.evaluate(predictions)
print("AUC:", auc)

# 8. Save trained model
model_path = "/tmp/document-quality-classifier"
model.write().overwrite().save(model_path)

print("Saved model to:", model_path)

spark.stop()