# IoT Data Processing

## Overview
Collect and process data from 10,000+ IoT sensors for smart city applications including traffic management and environmental monitoring.

## Business Problem
**Challenge**: Smart city needs to process massive streams of sensor data in real-time for traffic optimization, environmental alerts, and predictive maintenance.

## Mathematical Foundation
```
Sensor Count: 10,000 sensors
Reading Frequency: Every 30 seconds
Total Readings: 10,000 × (3600/30) = 1,200,000 readings/hour
Data Volume: 1,200,000 × 200 bytes = 240 MB/hour
Daily Storage: 240 MB × 24 = 5.76 GB/day (11.52 GB with RF=2)
```

## Architecture
```
IoT Sensors → Edge Gateway → Kafka → Stream Processing → Time Series DB
                                   → ML Pipeline → Prediction API
                                   → Alert System → Emergency Response
```

## Key Topics
- **sensor-data** (24 partitions, 1-hour retention)
- **traffic-events** (12 partitions, 24-hour retention)
- **environmental-alerts** (6 partitions, 7-day retention)

## Simplified Workflow

### 1. Sensor Data Schema
```json
{
  "sensor_id": "string",
  "timestamp": "long",
  "location": {"latitude": "double", "longitude": "double"},
  "sensor_type": "TEMPERATURE|HUMIDITY|AIR_QUALITY|TRAFFIC",
  "value": "double",
  "unit": "string"
}
```

### 2. High-Throughput Ingestion
```java
// Optimized producer for IoT data
Properties props = new Properties();
props.put("batch.size", 65536);      // 64KB batches
props.put("linger.ms", 50);          // 50ms batching window
props.put("compression.type", "lz4");
props.put("acks", "1");              // Performance over durability

// Partition by sensor ID for ordering
String partitionKey = reading.getSensorId();
producer.send(new ProducerRecord<>("sensor-data", partitionKey, reading));
```

### 3. Real-time Anomaly Detection
```java
// Stream processing with 10-minute windows
sensorStream
    .groupBy((key, value) -> value.getSensorType() + "-" + value.getLocationHash())
    .windowedBy(TimeWindows.of(Duration.ofMinutes(10)))
    .aggregate(SensorAggregation::new, (key, value, aggregate) -> aggregate.add(value))
    .filter((key, aggregate) -> isAnomalous(aggregate))  // 3-sigma rule
    .to("sensor-anomalies");
```

## Capacity Planning
```
Required Partitions = Data_Rate ÷ Target_Partition_Rate
                   = (240 MB/hour ÷ 3600) ÷ (10 MB/s)
                   = 0.067 MB/s ÷ 10 MB/s ≈ 1 partition

Recommended: 24 partitions for parallelism and future growth
Consumer Scaling: 3 consumers for load distribution
```

## Key Metrics
- **Ingestion Rate**: 333+ readings/second sustained
- **Processing Latency**: <200ms for anomaly detection
- **Data Retention**: 1 hour for sensor data, 7 days for alerts
- **Anomaly Detection**: 3-sigma statistical threshold

## Benefits
- **Real-time Monitoring**: Immediate detection of environmental issues
- **Predictive Maintenance**: Early warning for equipment failures
- **Traffic Optimization**: Dynamic traffic light adjustment
- **Cost Efficiency**: Edge processing reduces bandwidth requirements