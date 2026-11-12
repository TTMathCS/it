# Data Ingestion: Database to Data Lake Pipeline

> *"Data ingestion is the foundation of analytics - moving data efficiently from operational systems to analytical platforms."*

## Overview

This use case demonstrates high-throughput data ingestion from relational databases to cloud data lakes, showcasing NiFi's mathematical approach to flow optimization and throughput maximization.

## Mathematical Foundation

**Flow Network Theory**: Data ingestion can be modeled as a maximum flow problem where we want to optimize throughput while respecting capacity constraints.

**Key Equation**: `Throughput = min(Source_Capacity, Transform_Capacity, Sink_Capacity)`

**Queuing Theory Application**: Using Little's Law (L = λW) to optimize queue sizes and prevent bottlenecks.

## Scenario

**Business Context**: E-commerce company needs to move customer transaction data from PostgreSQL to AWS S3 for analytics.

**Requirements**:
- 1M+ records per hour
- Near real-time processing (< 5 minutes latency)
- Data validation and error handling
- Cost-effective cloud storage

## Flow Architecture

```
PostgreSQL → QueryDatabaseTable → ConvertRecord → CompressContent → PutS3Object
              ↓ (on failure)
           HandleError → LogError → DeadLetterQueue
```

## Mathematical Analysis

### Throughput Calculation
```
Source Rate: 1,000,000 records/hour = 278 records/second
Average Record Size: 1KB
Network Bandwidth: 100 Mbps
Expected Throughput: min(278 rec/sec, 12,500 KB/sec / 1KB) = 278 records/second
```

### Queue Sizing
```
Processing Time per Record: 0.01 seconds
Arrival Rate (λ): 278 records/second  
Queue Length (L): λ × W = 278 × 0.01 = ~3 records (minimal queuing)
Recommended Queue Size: 1000 records (safety buffer)
```

### Performance Optimization
```
Concurrent Tasks: 4 (based on database connection pool)
Fetch Size: 10,000 records per query
Compression Ratio: ~70% (reduces S3 costs)
Batch Size for S3: 100 files per hour (optimal for Spark processing)
```

## Implementation Details

### NiFi Processors Configuration

**QueryDatabaseTable**:
```
Database Connection Pool: PostgreSQL-Pool
SQL Query: SELECT * FROM transactions WHERE updated_at > ?
Max Rows: 10000
Schedule: 30 sec (timer-driven)
```

**ConvertRecord**:
```
Record Reader: CSV Reader
Record Writer: Parquet Writer  
Schema Strategy: Infer from data
Include Zero Record FlowFiles: false
```

**CompressContent**:
```
Compression Format: GZIP
Compression Level: 6 (balance speed vs. size)
Update Filename: true
```

**PutS3Object**:
```
Bucket: analytics-data-lake
Storage Class: STANDARD_IA (cost optimization)
Multipart Threshold: 5GB
Multipart Part Size: 5MB
```

## Expected Performance

### Throughput Metrics
- **Records/Second**: 250-300 (under normal conditions)
- **Data Volume**: ~1GB/hour compressed data
- **Latency**: 2-4 minutes end-to-end
- **Error Rate**: < 0.1% with proper error handling

### Resource Usage
- **CPU**: 2-4 cores (depending on compression settings)
- **Memory**: 4-8GB heap (based on queue sizes and content claims)
- **Network**: 10-20 Mbps sustained (bursts to 50 Mbps)
- **Disk**: 10-50GB for repositories (based on retention settings)

## Monitoring and Alerting

### Key Metrics to Track
```
nifi.throughput.records_per_second > 200
nifi.queue_depth.ingestion_queue < 5000  
nifi.error_rate.database_failures < 1%
nifi.latency.end_to_end < 300_seconds
```

### Alert Conditions
- Throughput drops below 150 records/second for > 10 minutes
- Queue depth exceeds 8000 records
- Error rate exceeds 2% for > 5 minutes
- End-to-end latency exceeds 600 seconds

## Scaling Strategies

### Horizontal Scaling
- **Cluster Setup**: 3-node NiFi cluster for high availability
- **Database Partitioning**: Partition by date range or customer ID
- **Parallel Processing**: Multiple table ingestion flows

### Vertical Scaling  
- **Memory Optimization**: Increase heap size for larger batches
- **CPU Optimization**: More concurrent tasks for CPU-bound operations
- **Network Optimization**: Increase bandwidth for high-volume periods

## Common Issues and Solutions

### Database Connection Issues
```
Problem: Connection timeouts during high load
Solution: Increase connection pool size and timeout values
Math: Pool_Size = Concurrent_Tasks × Safety_Factor (typically 1.5x)
```

### S3 Rate Limiting
```
Problem: S3 PUT request rate limiting  
Solution: Implement exponential backoff and request routing
Math: Retry_Delay = Base_Delay × 2^attempt_count (max 60 seconds)
```

### Memory Pressure
```
Problem: OutOfMemoryError during large file processing
Solution: Optimize content claim management and repository settings
Math: Max_Content_Size = Available_Memory × 0.7 / Concurrent_FlowFiles
```

## Cost Optimization

### S3 Storage Costs
```
Daily Data Volume: 24GB compressed
Monthly Cost (Standard): $24 × 31 × $0.023 = ~$17/month
Monthly Cost (Standard-IA): $24 × 31 × $0.0125 = ~$9/month  
Savings with Standard-IA: ~47% reduction
```

### Network Transfer Costs
```
Monthly Transfer: ~740GB
AWS Data Transfer Out: $0.09/GB after first 100GB
Monthly Cost: (740-100) × $0.09 = ~$58/month
```

## Next Steps

1. **Implement Flow**: Build the basic pipeline using the provided configuration
2. **Load Testing**: Use synthetic data to validate throughput expectations  
3. **Monitoring Setup**: Implement alerts and dashboards for key metrics
4. **Optimization**: Tune parameters based on observed performance
5. **Scale Planning**: Design cluster architecture for production deployment

---

*"Successful data ingestion combines mathematical precision with engineering pragmatism - optimizing for throughput while maintaining reliability and cost-effectiveness."*