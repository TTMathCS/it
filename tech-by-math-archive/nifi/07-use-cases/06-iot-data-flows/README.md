# IoT Data Flows: Edge Computing and Sensor Data Pipeline

> *"IoT data processing is the mathematical symphony of distributed systems - orchestrating thousands of edge devices through network theory and statistical aggregation."*

## Overview

This use case demonstrates IoT sensor data collection and processing using NiFi's distributed processing capabilities. It showcases how network theory, statistical aggregation, and edge computing mathematics enable reliable collection and analysis of massive sensor data streams.

## Mathematical Foundation

**Network Theory**: IoT networks modeled as graph structures with nodes (sensors) and edges (communication links) subject to reliability constraints.

**Key Equation**: `System_Reliability = ∏(Individual_Sensor_Reliability) × Network_Path_Reliability`

**Statistical Aggregation**: Sensor data fusion using Kalman filtering and weighted averaging for noise reduction and accuracy improvement.

## Scenario

**Business Context**: Smart manufacturing facility with 50,000+ sensors monitoring temperature, pressure, vibration, and energy consumption across production lines.

**Requirements**:
- Collect data from 50,000 sensors every 30 seconds (1,667 messages/second)
- Process both edge analytics and centralized aggregation
- Real-time anomaly detection with <5 second alert latency
- 99.9% data collection reliability with network fault tolerance

## Flow Architecture

```
[Sensor Networks] → [Edge NiFi] → [MQTT Broker] → [Central NiFi] → [Analytics Platform]
    ↓                 ↓              ↓             ↓                ↓
[Temperature]    → [Local Proc] → [Buffer Queue] → [Aggregation] → [Time-Series DB]
[Pressure]       → [Filter/Val] → [Compression] → [Anomaly Det] → [Alert System]  
[Vibration]      → [Edge Analy] → [Batch Send] → [Data Quality] → [Dashboard]
[Energy]         → [Cache/Buff] → [Resilience] → [Storage Opt] → [Reports]
```

## Mathematical Analysis

### Sensor Data Generation Model

**Poisson Process for Sensor Events**:
```
Sensor Count: 50,000 sensors
Sampling Interval: 30 seconds per sensor
Event Rate (λ): 50,000 / 30 = 1,667 events/second
Daily Data Volume: 1,667 × 86,400 = 144M sensor readings/day

Message Size Distribution:
  Temperature: 64 bytes (sensor_id, timestamp, value, location)
  Pressure: 64 bytes  
  Vibration: 128 bytes (includes frequency spectrum)
  Energy: 96 bytes (includes power factor, harmonics)

Average Message Size: 88 bytes
Daily Data Volume: 144M × 88 bytes = 12.7 GB/day
```

**Network Reliability Model**:
```
Individual Sensor Reliability: 99.5% uptime
Network Path Reliability: 99.8% (redundant communication paths)
Edge Gateway Reliability: 99.9% (clustered gateways)

End-to-End Reliability = 0.995 × 0.998 × 0.999 = 99.2%
Expected Data Loss: 0.8% = 1.15M readings/day lost
Acceptable Loss Threshold: < 1% (meets requirement)
```

### Edge Computing Optimization

**Edge Processing Distribution**:
```
Edge Processing Ratio: 80% (local filtering, anomaly detection)
Central Processing Ratio: 20% (aggregation, complex analytics)

Edge Processing Load: 1,667 × 0.8 = 1,333 events/second per edge cluster
Central Processing Load: 1,667 × 0.2 = 333 events/second
Bandwidth Savings: 80% reduction in network traffic
```

**Statistical Aggregation Mathematics**:
```
Sensor Noise Model: Gaussian with σ = 2% of reading
Moving Average Window: 10 readings (5-minute window)
Kalman Filter Parameters:
  Process Noise (Q): 0.01
  Measurement Noise (R): 0.04  
  Initial Uncertainty (P): 1.0

Filtered_Value = Previous_Estimate + Kalman_Gain × (Measurement - Previous_Estimate)
Kalman_Gain = P / (P + R)
Updated_Uncertainty = (1 - Kalman_Gain) × P + Q
```

### Performance Optimization

**Queue Management**:
```
MQTT Buffer Size: 100,000 messages per topic
Edge Cache Size: 50MB per gateway (1 hour of data)
Compression Ratio: 60% (time-series data compression)
Network Batch Size: 1000 readings per transmission

Buffer_Utilization = Incoming_Rate / Processing_Rate
Target_Utilization: 70% (safety margin for bursts)
Required_Processing_Rate: 1,667 / 0.7 = 2,381 events/second capacity
```

## Implementation Details

### Edge Data Collection

**ConsumeMQTT (Sensor Ingestion)**:
```
Broker URL: tcp://iot-mqtt-broker:1883
Topic Filter: sensors/+/+/data
QoS: 1 (at least once delivery)
Client ID Suffix: ${hostname()}-${UUID()}
Session State: Clean Session = false
Max Queue Size: 100000
```

**EvaluateJsonPath (Sensor Parsing)**:
```
sensor.id: $.sensor_id
sensor.type: $.sensor_type
sensor.location: $.location  
sensor.timestamp: $.timestamp
sensor.value: $.value
sensor.unit: $.unit
quality.flags: $.quality_flags
```

**RouteOnAttribute (Sensor Type Routing)**:
```
Temperature: ${sensor.type:equals('temperature')}
Pressure: ${sensor.type:equals('pressure')}
Vibration: ${sensor.type:equals('vibration')}  
Energy: ${sensor.type:equals('energy')}
Critical: ${sensor.value:gt(${sensor.threshold})}
Normal: ${sensor.value:le(${sensor.threshold})}
```

### Edge Analytics Processing

**UpdateAttribute (Statistical Processing)**:
```
moving_average: ${sensor.value:movingAverage(10)}
std_deviation: ${sensor.value:standardDeviation(10)}
z_score: ${sensor.value:minus(${moving_average}):divide(${std_deviation})}
anomaly_flag: ${z_score:abs():gt(2.0)}
processing.timestamp: ${now()}
```

**ExecuteScript (Kalman Filtering)**:
```
Script Engine: python
Script Body: |
  # Kalman filter implementation
  def kalman_filter(measurement, previous_estimate, previous_uncertainty):
      # Process noise and measurement noise
      Q = 0.01  # Process noise
      R = 0.04  # Measurement noise
      
      # Prediction step
      predicted_estimate = previous_estimate
      predicted_uncertainty = previous_uncertainty + Q
      
      # Update step  
      kalman_gain = predicted_uncertainty / (predicted_uncertainty + R)
      updated_estimate = predicted_estimate + kalman_gain * (measurement - predicted_estimate)
      updated_uncertainty = (1 - kalman_gain) * predicted_uncertainty
      
      return updated_estimate, updated_uncertainty
```

### Central Aggregation

**MergeContent (Batch Aggregation)**:
```
Merge Format: Binary Concatenation
Merge Strategy: Bin-Packing Algorithm
Min Entries: 1000 readings
Max Entries: 10000 readings
Max Bin Size: 10MB
Correlation Attribute: sensor.location
Demarcator: \n (newline separated JSON)
```

**QueryRecord (Time-Series Aggregation)**:
```
Record Reader: JSON Reader
Record Writer: JSON Writer
SQL Query: |
  SELECT 
    sensor_type,
    location,
    DATE_TRUNC('minute', timestamp) as minute_bucket,
    AVG(value) as avg_value,
    MIN(value) as min_value, 
    MAX(value) as max_value,
    STDDEV(value) as std_dev,
    COUNT(*) as reading_count
  FROM FLOWFILE
  GROUP BY sensor_type, location, minute_bucket
```

### Output and Storage

**PutInfluxDB (Time-Series Storage)**:
```
Database URL: http://influxdb-cluster:8086
Database Name: manufacturing_sensors
Measurement: sensor_readings
Tag Fields: sensor_id,location,sensor_type
Field Names: value,quality_flags,anomaly_flag
Batch Size: 5000 points
Flush Duration: 10 seconds
```

**PublishKafka (Real-time Alerts)**:
```
Topic: sensor-anomaly-alerts
Bootstrap Servers: kafka-cluster:9092
Message Key Field: sensor.id
Compression: gzip
Batch Size: 100KB
Linger Duration: 5ms (low latency for alerts)
```

## Expected Performance

### Throughput Metrics
- **Events/Second**: 1,500-2,000 (sustained processing)
- **Peak Throughput**: 3,000 events/second (burst handling)
- **Alert Latency**: 2-5 seconds (anomaly to notification)
- **Data Compression**: 60-80% size reduction

### Resource Usage
- **CPU**: 16-32 cores (distributed across edge and central)
- **Memory**: 32-64GB heap (time-series buffering and analytics)
- **Network**: 20-50 Mbps (sensor data and alerts)
- **Storage**: 1-5TB (time-series data retention)

## Monitoring and Alerting

### Key Metrics to Track
```
nifi.throughput.sensor_events_per_second > 1500
nifi.data_quality.missing_sensors < 50 (out of 50,000)
nifi.alert_latency.anomaly_detection < 5000ms
nifi.network_reliability.packet_loss < 0.1%
```

### IoT-Specific Metrics
```
Sensor_Availability = Active_Sensors / Total_Sensors > 99.0%
Data_Freshness = avg(current_time - sensor_timestamp) < 60_seconds
Edge_Processing_Rate = Edge_Events / Total_Events > 75%
Anomaly_Detection_Accuracy = True_Positives / (True_Positives + False_Positives) > 95%
```

### Alert Conditions
- More than 100 sensors offline simultaneously
- Alert generation latency exceeds 10 seconds
- Data loss rate exceeds 1% for 15 minutes
- Edge gateway CPU utilization exceeds 90%

## Scaling Strategies

### Horizontal Scaling
- **Geographic Distribution**: Regional edge clusters near sensor networks
- **Sensor Partitioning**: Dedicated flows for different sensor types
- **Load Balancing**: Round-robin distribution across processing nodes

### Vertical Scaling
- **Memory Optimization**: Larger buffers for time-series data
- **CPU Optimization**: More concurrent processing for analytics
- **Network Optimization**: Higher bandwidth for peak sensor loads

### Edge Computing Scaling
```python
def calculate_edge_resources(sensor_count, processing_ratio):
    total_events_per_second = sensor_count / 30  # 30-second intervals
    edge_events = total_events_per_second * processing_ratio
    
    # Resource requirements per 1000 events/second
    cpu_cores_needed = edge_events / 1000 * 2
    memory_gb_needed = edge_events / 1000 * 4
    
    return cpu_cores_needed, memory_gb_needed
```

## Common Issues and Solutions

### Network Connectivity Issues
```
Problem: Intermittent network connectivity causes data loss
Solution: Implement store-and-forward with local buffering
Math: Buffer_Size = Max_Outage_Duration × Data_Generation_Rate
```

### Sensor Drift and Calibration
```
Problem: Sensor readings drift over time affecting accuracy
Solution: Implement statistical process control with drift detection
Math: Drift_Detection = |Current_Average - Baseline_Average| > 3σ
```

### Edge Resource Constraints
```
Problem: Limited processing power at edge locations
Solution: Adaptive processing based on available resources  
Math: Processing_Level = Available_CPU / Required_CPU × Base_Processing_Level
```

### Time Synchronization
```
Problem: Sensor timestamps inconsistent across devices
Solution: Network Time Protocol (NTP) synchronization with drift correction
Math: Corrected_Timestamp = Raw_Timestamp + Clock_Offset - Network_Delay/2
```

## Edge vs Central Processing Distribution

### Edge Processing (80% of load)
```
Functions:
  - Data validation and filtering
  - Simple anomaly detection (threshold-based)
  - Data compression and batching
  - Local caching for network outages

Resource Allocation:
  - CPU: 8 cores per edge cluster (1000 sensors)
  - Memory: 16GB per edge cluster
  - Storage: 100GB local cache per cluster
```

### Central Processing (20% of load)  
```
Functions:
  - Complex analytics and machine learning
  - Cross-sensor correlation analysis
  - Historical trend analysis
  - Dashboard and reporting

Resource Allocation:
  - CPU: 32 cores central cluster
  - Memory: 128GB central cluster  
  - Storage: 10TB time-series database
```

## Cost Optimization

### Edge Infrastructure Costs
```
Edge Gateways: 50 gateways × $2,000 = $100,000 (one-time)
Edge Computing: 50 × 8 cores × $0.05/hour = $20/hour = $14,400/month
Edge Storage: 50 × 100GB × $0.10/GB = $500/month
Edge Network: 50 × $50/month = $2,500/month
```

### Central Infrastructure Costs
```
Central Compute: 32 cores × $0.10/hour = $3.20/hour = $2,304/month
Central Storage: 10TB × $23/TB = $230/month
Network Transfer: 1TB/month × $0.09/GB = $90/month
Time-Series Database: $500/month (managed service)
```

### Cost per Sensor Reading
```
Total Monthly Cost: $20,324
Total Sensor Readings/Month: 4.32B readings
Cost per 1M Readings: $20,324 / 4,320 = $4.70 per million readings
Cost per Sensor/Month: $20,324 / 50,000 = $0.41 per sensor per month
```

## Next Steps

1. **Design Sensor Network Topology**: Map physical sensor locations to logical data flows
2. **Implement Edge Analytics**: Deploy statistical processing and anomaly detection
3. **Configure MQTT Infrastructure**: Set up reliable message queuing with persistence
4. **Test Fault Tolerance**: Validate behavior during network outages and sensor failures
5. **Optimize Resource Allocation**: Balance edge vs central processing based on requirements

---

*"IoT data mastery lies in the mathematical orchestration of distributed intelligence - where edge computing meets the elegance of statistical signal processing."*