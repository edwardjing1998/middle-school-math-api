import json
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers="kafka:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

message = {
    "id": 1,
    "text": "This is a test message from cuda-python-demo"
}

future = producer.send("document-topic", message)
record_metadata = future.get(timeout=10)

producer.flush()
producer.close()

print("Message sent:", message)
print("Topic:", record_metadata.topic)
print("Partition:", record_metadata.partition)
print("Offset:", record_metadata.offset)