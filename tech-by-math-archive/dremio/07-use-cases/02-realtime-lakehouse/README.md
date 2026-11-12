# Real-Time Data Lakehouse Analytics

![Real-Time Lakehouse Workflow](workflow.svg)

## Overview

This use case demonstrates how Dremio enables unified real-time analytics on streaming IoT data while maintaining access to historical data lake context for comprehensive insights, eliminating the complexity of traditional Lambda architectures.

## Business Scenario

**Company**: StreamTech Analytics Inc.  
**Challenge**: Enable real-time analytics on streaming IoT data while maintaining access to historical data lake context for comprehensive insights.

**Key Players**:
- **Alex Chen** (IoT Platform Engineer) - Managing 100K+ sensors generating 50GB data per hour
- **Maria Santos** (Real-time Analytics Lead) - Building dashboards showing current vs historical trends
- **David Park** (ML Engineer) - Training models that need both streaming features and historical context
- **Jennifer Liu** (Operations Director) - Needs real-time alerts with historical context for decision making

## The Traditional Streaming Analytics Problem

**Day 1 - The Real-time vs Historical Data Dilemma**:
```
Alex:     "Our IoT sensors generate massive streams but we lose historical context"
Maria:    "Lambda architecture is too complex - maintaining batch and stream processing separately"
David:    "ML models need streaming features but also 2 years of historical training data"
Jennifer: "Real-time alerts are useless without understanding if this is normal or anomalous"
```

**Traditional Approach Limitations**:
- **Lambda Architecture Complexity**: Separate batch and stream processing pipelines
- **Data Synchronization Issues**: Batch and real-time views often inconsistent
- **Storage Explosion**: Hot storage for streaming, cold storage for historical data
- **Query Complexity**: Different APIs for real-time vs historical data access
- **Latency Trade-offs**: Either fast queries on limited data or slow queries on complete data

## How Dremio Enables Unified Real-time Analytics

**Day 1 - Streaming Data Ingestion Setup**:
```bash
# Configure Kafka source for real-time IoT data
curl -X POST http://dremio-coordinator:9047/apiv2/source \
  -H "Content-Type: application/json" \
  -d '{
    "name": "iot_stream",
    "type": "KAFKA",
    "config": {
      "kafkaBootstrapServers": "kafka-cluster:9092",
      "kafkaSaslMechanism": "PLAIN",
      "topics": [
        "sensor_readings",
        "device_status", 
        "alerts"
      ],
      "tableRefreshIntervalSeconds": 30
    }
  }'

# Configure S3 source for historical data lake
curl -X POST http://dremio-coordinator:9047/apiv2/source \
  -H "Content-Type: application/json" \
  -d '{
    "name": "historical_datalake",
    "type": "S3",
    "config": {
      "credentialType": "AWS_PROFILE",
      "buckets": [
        "streamtech-historical-data",
        "streamtech-ml-features"
      ],
      "compatibilityMode": true
    }
  }'

# Configure time-series database source
curl -X POST http://dremio-coordinator:9047/apiv2/source \
  -H "Content-Type: application/json" \
  -d '{
    "name": "timeseries_db",
    "type": "INFLUXDB", 
    "config": {
      "hostname": "influxdb.streamtech.com",
      "port": 8086,
      "database": "sensor_metrics",
      "retentionPolicy": "autogen"
    }
  }'
```

**Day 3 - Real-time Analytics with Historical Context**:
```sql
-- Create unified view combining streaming and historical data
CREATE VDS sensor_analytics_unified AS
WITH current_readings AS (
  SELECT 
    sensor_id,
    timestamp,
    temperature,
    pressure,
    vibration,
    status
  FROM iot_stream.sensor_readings
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
),
historical_context AS (
  SELECT 
    sensor_id,
    DATE_TRUNC('hour', timestamp) as hour_timestamp,
    AVG(temperature) as avg_temp_historical,
    STDDEV(temperature) as stddev_temp_historical,
    MAX(pressure) as max_pressure_historical,
    COUNT(*) as reading_count
  FROM historical_datalake.sensors.hourly_aggregates
  WHERE DATE_TRUNC('hour', timestamp) >= CURRENT_DATE - INTERVAL 30 DAY
    AND DATE_TRUNC('hour', timestamp) < DATE_TRUNC('hour', CURRENT_TIMESTAMP)
  GROUP BY sensor_id, DATE_TRUNC('hour', timestamp)
)
SELECT 
  cr.sensor_id,
  cr.timestamp,
  cr.temperature,
  cr.pressure,
  cr.vibration,
  cr.status,
  
  -- Real-time anomaly detection using historical context
  hc.avg_temp_historical,
  hc.stddev_temp_historical,
  
  -- Z-score for anomaly detection: |x - μ| / σ
  ABS(cr.temperature - hc.avg_temp_historical) / 
    NULLIF(hc.stddev_temp_historical, 0) as temperature_z_score,
  
  -- Classification based on statistical analysis
  CASE 
    WHEN ABS(cr.temperature - hc.avg_temp_historical) / 
         NULLIF(hc.stddev_temp_historical, 0) > 3 THEN 'CRITICAL_ANOMALY'
    WHEN ABS(cr.temperature - hc.avg_temp_historical) / 
         NULLIF(hc.stddev_temp_historical, 0) > 2 THEN 'WARNING'
    ELSE 'NORMAL'
  END as anomaly_classification,
  
  -- Trend analysis
  cr.temperature - hc.avg_temp_historical as temp_deviation
  
FROM current_readings cr
LEFT JOIN historical_context hc 
  ON cr.sensor_id = hc.sensor_id 
  AND DATE_TRUNC('hour', cr.timestamp) = hc.hour_timestamp;

-- Query executes in 1.2 seconds combining real-time and historical data
-- Processes 50K current readings with 30 days of historical context
```

**Day 7 - Advanced Real-time ML Feature Engineering**:
```sql
-- Create ML feature store combining streaming and historical features
CREATE VDS ml_features_realtime AS
WITH streaming_features AS (
  SELECT 
    sensor_id,
    timestamp,
    
    -- Real-time statistical features (5-minute windows)
    AVG(temperature) OVER (
      PARTITION BY sensor_id 
      ORDER BY timestamp 
      ROWS BETWEEN 10 PRECEDING AND CURRENT ROW
    ) as temp_ma_5min,
    
    STDDEV(vibration) OVER (
      PARTITION BY sensor_id 
      ORDER BY timestamp 
      ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
    ) as vibration_stddev_10min,
    
    -- Rate of change features
    temperature - LAG(temperature, 5) OVER (
      PARTITION BY sensor_id 
      ORDER BY timestamp
    ) as temp_rate_of_change,
    
    -- Frequency domain features using FFT approximation
    temperature,
    pressure,
    vibration
    
  FROM iot_stream.sensor_readings
  WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
),
historical_features AS (
  SELECT 
    sensor_id,
    
    -- Historical statistical profiles
    AVG(temperature) as historical_temp_mean,
    STDDEV(temperature) as historical_temp_stddev,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY pressure) as historical_pressure_p95,
    
    -- Seasonal features
    AVG(CASE WHEN EXTRACT(hour FROM timestamp) BETWEEN 6 AND 18 
             THEN temperature END) as day_temp_avg,
    AVG(CASE WHEN EXTRACT(hour FROM timestamp) BETWEEN 19 AND 5 
             THEN temperature END) as night_temp_avg,
             
    -- Failure history features
    COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as historical_failure_count,
    MAX(CASE WHEN status = 'FAILED' THEN timestamp END) as last_failure_timestamp
    
  FROM historical_datalake.sensors.readings
  WHERE timestamp >= CURRENT_DATE - INTERVAL 90 DAY
  GROUP BY sensor_id
)
SELECT 
  sf.*,
  hf.historical_temp_mean,
  hf.historical_temp_stddev,
  hf.historical_pressure_p95,
  hf.day_temp_avg,
  hf.night_temp_avg,
  hf.historical_failure_count,
  
  -- Derived ML features
  (sf.temp_ma_5min - hf.historical_temp_mean) / hf.historical_temp_stddev as temp_z_score,
  (sf.temperature - hf.day_temp_avg) / NULLIF(hf.day_temp_avg, 0) as temp_seasonal_deviation,
  
  -- Time-since-last-failure feature
  EXTRACT(epoch FROM (sf.timestamp - hf.last_failure_timestamp)) / 86400.0 as days_since_failure,
  
  -- Composite risk score
  CASE 
    WHEN hf.historical_failure_count > 5 AND sf.temp_rate_of_change > 10 THEN 0.9
    WHEN sf.vibration_stddev_10min > hf.historical_temp_stddev * 2 THEN 0.7
    WHEN ABS(sf.temp_ma_5min - hf.historical_temp_mean) > 2 * hf.historical_temp_stddev THEN 0.6
    ELSE 0.1
  END as predictive_failure_risk

FROM streaming_features sf
LEFT JOIN historical_features hf ON sf.sensor_id = hf.sensor_id;
```

## Architecture Overview

```
Real-time Data Sources:
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Kafka Stream   │  │  IoT Sensors    │  │  Event Stream   │
│                 │  │                 │  │                 │
│ • Sensor Data   │  │ • Temperature   │  │ • User Actions  │
│ • Device Status │  │ • Pressure      │  │ • System Events │
│ • Alerts/Alarms │  │ • Vibration     │  │ • Transactions  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
Historical Data Sources:       │
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   S3 Data Lake  │  │   InfluxDB      │  │   Parquet       │
│                 │  │                 │  │                 │
│ • Historical    │  │ • Time Series   │  │ • Aggregated    │
│   Sensor Data   │  │   Metrics       │  │   Features      │
│ • ML Training   │  │ • Performance   │  │ • Model Results │
│   Data          │  │   Data          │  │ • Predictions   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
Dremio Lakehouse Platform:     │
┌─────────────────────────────────────────────────────────────┐
│                  Unified Query Engine                      │
│  ┌─────────────────┐ ┌─────────────────┐ ┌────────────────┐│
│  │ Coordinator     │ │ Executor Node 1 │ │ Executor Node 2││
│  │ • Stream Proc   │ │ • Real-time     │ │ • Historical   ││
│  │ • Query Planning│ │   Processing    │ │   Analytics    ││
│  │ • Metadata Mgmt │ │ • Reflections   │ │ • ML Features  ││
│  │ • Security      │ │ • Caching       │ │ • Caching      ││
│  └─────────────────┘ └─────────────────┘ └────────────────┘│
└─────────────────────────────────────────────────────────────┘
                               │
Real-time Applications:        │
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Real-time       │  │ ML Inference    │  │ Operational     │
│ Dashboards      │  │ Pipeline        │  │ Alerts          │
│                 │  │                 │  │                 │
│ • Live Metrics  │  │ • Anomaly       │  │ • Threshold     │
│ • Trend Analysis│ │   Detection     │  │   Violations    │
│ • Comparative   │  │ • Predictive    │  │ • System Health │
│   Views         │  │   Maintenance   │  │ • Performance   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Mathematical Foundation

### Real-time Anomaly Detection Mathematics

```python
import numpy as np
from scipy import stats

class RealTimeAnomalyDetector:
    def __init__(self, historical_window_days=30):
        self.historical_window = historical_window_days
        self.z_score_threshold = 3.0
        self.seasonal_window_hours = 168  # 1 week for seasonal patterns
    
    def calculate_statistical_features(self, historical_data, current_readings):
        """
        Calculate statistical features for anomaly detection
        Uses Z-score: Z = (X - μ) / σ where μ is mean, σ is standard deviation
        """
        
        features = {}
        
        for sensor_id in current_readings:
            # Get historical statistics for this sensor
            hist_data = historical_data[sensor_id]
            current_data = current_readings[sensor_id]
            
            # Basic statistical features
            historical_mean = np.mean(hist_data['temperature'])
            historical_std = np.std(hist_data['temperature'])
            
            # Z-score for current reading
            z_score = (current_data['temperature'] - historical_mean) / historical_std
            
            # Seasonal adjustment (compare to same time in previous weeks)
            seasonal_data = self._get_seasonal_data(hist_data, current_data['timestamp'])
            seasonal_mean = np.mean(seasonal_data) if seasonal_data else historical_mean
            seasonal_z_score = (current_data['temperature'] - seasonal_mean) / historical_std
            
            # Rate of change analysis
            recent_readings = self._get_recent_readings(current_data, window_minutes=30)
            if len(recent_readings) > 1:
                rate_of_change = (recent_readings[-1] - recent_readings[0]) / len(recent_readings)
            else:
                rate_of_change = 0
            
            # Multi-variate anomaly detection (Mahalanobis distance)
            feature_vector = np.array([
                current_data['temperature'],
                current_data['pressure'], 
                current_data['vibration']
            ])
            
            historical_features = np.array([
                hist_data['temperature'],
                hist_data['pressure'],
                hist_data['vibration']
            ]).T
            
            mahalanobis_distance = self._calculate_mahalanobis_distance(
                feature_vector, historical_features
            )
            
            features[sensor_id] = {
                'z_score': z_score,
                'seasonal_z_score': seasonal_z_score,
                'rate_of_change': rate_of_change,
                'mahalanobis_distance': mahalanobis_distance,
                'anomaly_score': self._calculate_composite_anomaly_score(
                    z_score, seasonal_z_score, rate_of_change, mahalanobis_distance
                )
            }
        
        return features
    
    def _calculate_mahalanobis_distance(self, point, historical_data):
        """
        Calculate Mahalanobis distance for multivariate anomaly detection
        D²(x) = (x - μ)ᵀ Σ⁻¹ (x - μ)
        """
        mean = np.mean(historical_data, axis=0)
        cov = np.cov(historical_data.T)
        
        # Handle singular covariance matrix
        try:
            inv_cov = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            # Use pseudo-inverse for singular matrices
            inv_cov = np.linalg.pinv(cov)
        
        diff = point - mean
        distance = np.sqrt(np.dot(np.dot(diff, inv_cov), diff.T))
        
        return distance
    
    def _calculate_composite_anomaly_score(self, z_score, seasonal_z_score, 
                                          rate_of_change, mahalanobis_distance):
        """
        Combine multiple anomaly indicators into a single score
        Uses weighted combination with sigmoid transformation
        """
        
        # Normalize individual scores
        z_score_norm = abs(z_score) / 5.0  # Normalize by 5-sigma
        seasonal_norm = abs(seasonal_z_score) / 3.0
        rate_norm = abs(rate_of_change) / 10.0  # Normalize by expected max rate
        mahal_norm = mahalanobis_distance / 10.0
        
        # Weighted combination
        weighted_score = (
            0.3 * z_score_norm +
            0.25 * seasonal_norm +
            0.25 * rate_norm +
            0.2 * mahal_norm
        )
        
        # Apply sigmoid transformation to get 0-1 score
        composite_score = 1 / (1 + np.exp(-5 * (weighted_score - 0.5)))
        
        return composite_score
```

### Stream Processing Mathematics

```python
class StreamProcessingOptimizer:
    def __init__(self):
        self.window_sizes = [60, 300, 900, 3600]  # 1min, 5min, 15min, 1hour
        
    def optimize_window_sizes(self, data_characteristics):
        """
        Optimize sliding window sizes for stream processing
        Uses Little's Law: L = λW where L=items in system, λ=arrival rate, W=waiting time
        """
        
        arrival_rate = data_characteristics['events_per_second']
        processing_capacity = data_characteristics['processing_rate']
        latency_requirement = data_characteristics['max_latency_seconds']
        
        # Calculate optimal window size based on throughput requirements
        optimal_window = min(
            latency_requirement,
            processing_capacity / arrival_rate * 0.8  # 80% utilization target
        )
        
        # Ensure window size is practical (between 1 second and 1 hour)
        optimal_window = max(1, min(3600, optimal_window))
        
        return {
            'optimal_window_seconds': optimal_window,
            'expected_throughput': processing_capacity,
            'buffer_size': int(arrival_rate * optimal_window * 1.2),  # 20% buffer
            'memory_requirement_mb': self._estimate_memory_usage(
                arrival_rate, optimal_window, data_characteristics['avg_record_size_bytes']
            )
        }
    
    def _estimate_memory_usage(self, arrival_rate, window_size, record_size):
        """Estimate memory usage for streaming windows"""
        records_in_window = arrival_rate * window_size
        total_bytes = records_in_window * record_size
        # Add overhead for processing structures (2x factor)
        return int(total_bytes * 2 / (1024 * 1024))  # Convert to MB
```

## Real-time Reflection Configuration

```sql
-- Create optimized reflections for real-time queries
ALTER TABLE sensor_analytics_unified
CREATE REFLECTION realtime_sensor_summary
USING DIMENSIONS (
    sensor_id,
    DATE_TRUNC('minute', timestamp) as minute_timestamp,
    anomaly_classification
)
MEASURES (
    COUNT(*) as reading_count,
    AVG(temperature) as avg_temperature,
    MAX(temperature_z_score) as max_z_score,
    COUNT(CASE WHEN anomaly_classification = 'CRITICAL_ANOMALY' THEN 1 END) as critical_count
)
-- Refresh every 30 seconds for near real-time updates
USING REFRESH (INCREMENTAL UPDATE INTERVAL 30 SECONDS);

-- Create raw reflection for high-performance access to recent data
ALTER TABLE sensor_analytics_unified  
CREATE REFLECTION recent_raw_data
USING RAW REFLECTION
PARTITION BY (DATE_TRUNC('hour', timestamp))
LOCALSORT BY (sensor_id, timestamp)
-- Keep only last 7 days in fast reflection
WHERE timestamp >= CURRENT_DATE - INTERVAL 7 DAY;
```

## Stream Processing Pipeline

```python
class StreamProcessingPipeline:
    def __init__(self, dremio_client):
        self.dremio = dremio_client
        self.batch_size = 1000
        self.processing_interval_seconds = 30
        
    def process_sensor_stream(self):
        """Process incoming sensor data stream"""
        
        while True:
            try:
                # Read batch of new sensor readings
                new_readings = self.read_stream_batch()
                
                if new_readings:
                    # Process anomaly detection
                    anomaly_results = self.detect_anomalies(new_readings)
                    
                    # Update real-time features  
                    feature_updates = self.update_ml_features(new_readings)
                    
                    # Trigger alerts if needed
                    self.check_alert_conditions(anomaly_results)
                    
                    # Update dashboards
                    self.update_realtime_dashboards(anomaly_results, feature_updates)
                
                time.sleep(self.processing_interval_seconds)
                
            except Exception as e:
                self.handle_processing_error(e)
    
    def detect_anomalies(self, readings):
        """Run real-time anomaly detection queries"""
        
        query = """
        WITH current_batch AS (
          SELECT * FROM VALUES {} AS t(sensor_id, timestamp, temperature, pressure, vibration)
        ),
        anomaly_analysis AS (
          SELECT 
            cb.*,
            sau.temperature_z_score,
            sau.anomaly_classification,
            sau.temp_deviation
          FROM current_batch cb
          LEFT JOIN sensor_analytics_unified sau 
            ON cb.sensor_id = sau.sensor_id 
            AND cb.timestamp = sau.timestamp
        )
        SELECT * FROM anomaly_analysis
        WHERE temperature_z_score > 2.0 OR anomaly_classification = 'CRITICAL_ANOMALY'
        """.format(self.format_readings_for_values(readings))
        
        return self.dremio.execute_query(query)
```

## Results and Business Impact

**Quantitative Results (After 4 Months)**:
- **Query Latency**: 95% of real-time queries complete within 1.2 seconds
- **Data Freshness**: Real-time analytics with < 30 second latency from source
- **Anomaly Detection**: 98.5% accuracy with 3.2% false positive rate
- **Infrastructure Cost**: 45% reduction vs separate batch/stream architectures  
- **Operational Efficiency**: 60% reduction in time to detect and respond to issues

**Mathematical Performance Validation**:
```sql
-- Real-time performance metrics query
SELECT 
    DATE_TRUNC('hour', query_timestamp) as hour,
    COUNT(*) as total_queries,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY execution_time_ms) as p50_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY execution_time_ms) as p95_latency_ms,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY execution_time_ms) as p99_latency_ms,
    COUNT(*) / 3600.0 as queries_per_second,
    
    -- Little's Law validation: L = λW
    (COUNT(*) / 3600.0) * (AVG(execution_time_ms) / 1000.0) as avg_concurrent_queries,
    
    -- SLA compliance metrics
    SUM(CASE WHEN execution_time_ms <= 1000 THEN 1 ELSE 0 END) / COUNT(*) as sla_compliance_rate
    
FROM realtime_query_log 
WHERE query_timestamp >= CURRENT_TIMESTAMP - INTERVAL 24 HOUR
  AND query_type IN ('STREAMING_ANALYTICS', 'REALTIME_FEATURES')
GROUP BY DATE_TRUNC('hour', query_timestamp)
ORDER BY hour DESC;
```

**Business Value Achieved**:
- **Predictive Maintenance**: $2.3M annual savings from preventing equipment failures
- **Operational Excellence**: 78% improvement in mean time to detection (MTTD)
- **Resource Optimization**: 34% reduction in unnecessary maintenance interventions
- **Data-Driven Decisions**: Real-time insights enable proactive rather than reactive operations

## Next Steps

- **[Self-Service BI](../01-self-service-bi/README.md)**: Add real-time capabilities to your business intelligence platform
- **[ML Feature Engineering](../03-ml-feature-engineering/README.md)**: Use real-time features for advanced machine learning models
- **[Cost Optimization](../04-cost-optimization/README.md)**: Optimize infrastructure costs with unified lakehouse architecture

## References

- **[Core Model](../../01-core-model/README.md)**: Mathematical foundations of distributed processing
- **[Math Toolkit](../../02-math-toolkit/README.md)**: Statistical analysis and time series tools
- **[Algorithms](../../03-algorithms/README.md)**: Stream processing and distributed execution algorithms