# Log Aggregation and Monitoring

## Overview
Centralize logs from 500+ microservices for monitoring, troubleshooting, and security analysis using Kafka as a scalable log transport layer.

## Business Problem
**Challenge**: CloudOps platform needs to collect, process, and analyze logs from hundreds of microservices for real-time monitoring and security threat detection.

## Mathematical Foundation
```
Service Count: 500 microservices
Log Rate: 100 logs/minute per service
Total Rate: 500 × 100 = 50,000 logs/minute = 833 logs/second
Average Log Size: 1 KB
Total Throughput: 833 KB/second ≈ 0.8 MB/second
Peak Load (5x): 4 MB/second
```

## Architecture
```
Microservices → Filebeat → Kafka → Logstash → Elasticsearch → Kibana
                                 → Stream Processor → Alert Manager
                                 → Security Scanner → SIEM System
```

## Key Topics
- **application-logs** (12 partitions, 7-day retention)
- **security-events** (6 partitions, 30-day retention)
- **performance-metrics** (8 partitions, 1-day retention)

## Simplified Workflow

### 1. Log Entry Format
```json
{
  "timestamp": "2025-08-26T14:30:00.123Z",
  "service_name": "user-service",
  "level": "INFO|WARN|ERROR|DEBUG",
  "message": "string",
  "request_id": "uuid",
  "host": "string",
  "fields": {"response_time_ms": "int", "status_code": "int"}
}
```

### 2. Log Processing Pipeline
```java
@KafkaListener(topics = "application-logs", concurrency = "12")
public void processLogEntry(LogEntry logEntry) {
    // Enrich log entry with metadata
    EnrichedLogEntry enriched = enrichLogEntry(logEntry);
    
    // Route based on log level
    switch (logEntry.getLevel()) {
        case "ERROR":
            handleErrorLog(enriched);
            break;
        case "WARN":
            handleWarningLog(enriched);
            break;
    }
    
    // Send to downstream systems
    sendToElasticsearch(enriched);
    if (isSecurityRelevant(enriched)) {
        sendToSecuritySystem(enriched);
    }
}
```

### 3. Real-time Alerting
```java
// Alert on error rate spike using stream processing
logs.filter((key, log) -> "ERROR".equals(log.getLevel()))
    .groupBy((key, log) -> log.getServiceName())
    .windowedBy(TimeWindows.of(Duration.ofMinutes(5)))
    .count()
    .toStream()
    .filter((key, count) -> count > 10)  // >10 errors in 5 minutes
    .foreach((key, count) -> alertManager.sendAlert(
        "High error rate: " + key.key() + ", count: " + count));
```

## Capacity Planning
```
Partition Strategy:
Target per-partition rate: 4 MB/second ÷ 12 partitions ≈ 0.33 MB/second
Consumer Scaling: 12 consumers (1 per partition)
Batch Processing: 1000 records per poll for efficiency

Storage Requirements:
Daily volume: 0.8 MB/s × 86400s = 69 GB/day
With replication factor 2: 138 GB/day
7-day retention: 138 GB × 7 = 966 GB total
```

## Key Metrics
- **Ingestion Rate**: 833+ logs/second sustained (4,000+ peak)
- **Processing Latency**: <2 seconds for log indexing
- **Error Detection**: <30 seconds for critical alerts
- **Storage Efficiency**: 7-day retention with automated cleanup

## Benefits
- **Centralized Monitoring**: Single pane of glass for all services
- **Real-time Alerting**: Immediate notification of critical issues
- **Security Analysis**: Automated threat detection and correlation
- **Troubleshooting**: Fast root cause analysis with request tracing