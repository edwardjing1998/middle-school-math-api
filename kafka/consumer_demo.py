import json
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    "document-topic",
    bootstrap_servers="kafka:9092",
    auto_offset_reset="earliest",
    enable_auto_commit=True,
    group_id="cuda-python-demo-group",
    value_deserializer=lambda v: json.loads(v.decode("utf-8"))
)

print("Waiting for messages...")

for message in consumer:
    print("Received:", message.value)