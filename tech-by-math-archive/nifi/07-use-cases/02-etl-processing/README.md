# ETL Processing: Multi-Source Data Transformation Pipeline

> *"ETL is the art of transforming chaos into order - applying mathematical rigor to data transformation workflows."*

## Overview

This use case demonstrates complex Extract, Transform, Load (ETL) workflows using NiFi's graph-based processing model. It showcases how directed acyclic graphs (DAGs) optimize multi-step data transformations while maintaining data quality and lineage.

## Mathematical Foundation

**Graph Theory**: ETL workflows are modeled as directed acyclic graphs where nodes represent transformations and edges represent data dependencies.

**Key Equation**: `Total_Processing_Time = Σ(Critical_Path_Processing_Times) + Coordination_Overhead`

**Information Theory Application**: Data quality improvements measured through entropy reduction and information gain.

## Scenario

**Business Context**: Financial services company needs to consolidate customer data from multiple systems for regulatory reporting.

**Requirements**:
- Process 500K+ records from 5 different sources daily
- Complex business rules and data validation
- Regulatory compliance with full audit trail
- 99.9% data accuracy requirement

## Flow Architecture

```
[PostgreSQL, Oracle, CSV Files, REST API, Kafka] 
    ↓
[Extract & Validate] → [Data Quality Check] → [Business Rules Engine]
    ↓                        ↓                       ↓
[Schema Normalization] → [Data Enrichment] → [Regulatory Validation]
    ↓                        ↓                       ↓
[Master Data Management] → [Aggregation] → [Data Warehouse Load]
    ↓ (on failure)
[Error Handling] → [Data Steward Queue] → [Manual Review]
```

## Mathematical Analysis

### Graph Complexity Analysis
```
Nodes (Processors): 15 transformation steps
Edges (Connections): 22 data flows
Critical Path Length: 8 sequential steps
Parallel Branches: 3 (source extraction can run simultaneously)
Graph Diameter: 8 (longest path from any source to sink)
```

### Throughput Calculation
```
Source Rate: 500,000 records/day = 5.8 records/second
Average Processing Time per Stage: 0.1 seconds
Critical Path Processing Time: 8 × 0.1 = 0.8 seconds per record
Theoretical Max Throughput: 1/0.8 = 1.25 records/second
Recommended Parallelism: 5.8/1.25 = ~5 parallel instances
```

### Data Quality Mathematics
```
Input Data Entropy: H(X) = -Σ p(xi) × log₂(p(xi))
Output Data Entropy: H(Y) = reduced entropy after cleansing
Information Gain: IG = H(X) - H(Y)
Data Quality Score: 1 - (Errors_Found / Total_Records)
```

### Performance Optimization
```
Concurrent Tasks per Processor: 2-4 (I/O bound operations)
Queue Sizes: 10,000 records (accommodate burst processing)
Batch Processing Size: 1,000 records per FlowFile
Memory Buffer per Transformation: 100MB
```

## Implementation Details

### Source Extraction Processors

**QueryDatabaseTable (PostgreSQL)**:
```
Connection Pool: PostgreSQL-Customer-DB
SQL Query: SELECT * FROM customers WHERE modified_date > ?
Max Rows: 5000
Schedule: 1 hour (timer-driven)
Incremental Column: modified_date
```

**QueryDatabaseTable (Oracle)**:
```
Connection Pool: Oracle-Financial-DB  
SQL Query: SELECT * FROM transactions WHERE created_at > ?
Max Rows: 10000
Schedule: 30 min (timer-driven)
State Management: Distributed cache for checkpoint
```

**GetFile (CSV Processing)**:
```
Input Directory: /data/incoming/csv
File Filter: customer_.*\.csv
Batch Size: 1
Keep Source File: false
Minimum File Age: 10 sec
```

**InvokeHTTP (REST API)**:
```
HTTP Method: GET
Remote URL: https://api.partner.com/customers
Authentication: Bearer token
Request Timeout: 30 sec
Rate Limit: 100 requests/minute
```

### Transformation Processors

**ValidateRecord**:
```
Record Reader: JSON Reader
Record Writer: JSON Writer  
Schema Access Strategy: Use Schema Name Property
Validation Strategy: Whole record validation
Invalid Record Strategy: Route to failure
```

**LookupRecord**:
```
Record Reader: JSON Reader
Record Writer: JSON Writer
Lookup Service: DatabaseRecordLookupService
Result Record Path: /enrichment
Cache Size: 10000 entries
```

**UpdateRecord**:
```
Record Reader: JSON Reader
Record Writer: JSON Writer
Replacement Value Strategy: Record Path Value
Business Rule: if(/account_status == "INACTIVE") then "CLOSED" else /account_status
```

## Expected Performance

### Throughput Metrics
- **Records/Second**: 5-8 (during peak processing)
- **Daily Processing Volume**: 500K-750K records
- **End-to-End Latency**: 2-5 minutes per batch
- **Data Quality Accuracy**: > 99.9%

### Resource Usage
- **CPU**: 8-16 cores (transformation-intensive workload)
- **Memory**: 16-32GB heap (complex transformations and caching)
- **Network**: 5-15 Mbps (multiple data sources)
- **Disk**: 100-500GB for repositories and intermediate storage

## Monitoring and Alerting

### Key Metrics to Track
```
nifi.throughput.etl_pipeline > 4 records/second
nifi.data_quality.error_rate < 0.1%
nifi.processing_time.critical_path < 300 seconds
nifi.queue_depth.transformation_queues < 15000 records
```

### Data Quality Metrics
```
Record_Completeness = (Non_Null_Fields / Total_Required_Fields) × 100%
Schema_Compliance = (Valid_Records / Total_Records) × 100%
Business_Rule_Compliance = (Rules_Passed / Total_Rules) × 100%
Reference_Data_Validity = (Valid_Lookups / Total_Lookups) × 100%
```

### Alert Conditions
- Data quality score drops below 99.5%
- Processing latency exceeds 600 seconds
- Critical path queue depth exceeds 20,000 records
- Source extraction failures exceed 2% error rate

## Scaling Strategies

### Horizontal Scaling
- **Source Partitioning**: Parallel extraction by date ranges or customer segments
- **Transformation Parallelism**: Multiple instances of transformation processors
- **Load Distribution**: Round-robin routing to multiple target systems

### Vertical Scaling
- **Memory Optimization**: Larger heap sizes for complex transformations
- **CPU Optimization**: More concurrent tasks for CPU-intensive operations
- **Cache Optimization**: Distributed caching for lookup operations

## Common Issues and Solutions

### Data Quality Issues
```
Problem: High error rates in transformation logic
Solution: Implement staged validation with intermediate quality gates
Math: Error_Propagation = 1 - ∏(1 - Stage_Error_Rate)
```

### Performance Bottlenecks
```
Problem: Critical path becomes bottleneck
Solution: Identify and parallelize longest processing chains
Math: Speedup = Old_Critical_Path_Time / New_Critical_Path_Time
```

### Memory Management
```
Problem: OutOfMemoryError during complex transformations
Solution: Optimize FlowFile attribute management and content claims
Math: Memory_Per_FlowFile = Content_Size + Attributes_Size + Overhead
```

### Lookup Performance
```
Problem: Slow reference data lookups causing delays
Solution: Implement distributed caching with appropriate TTL
Math: Cache_Hit_Rate = Cache_Hits / (Cache_Hits + Cache_Misses)
```

## Data Lineage and Compliance

### Provenance Tracking
```
Lineage_Graph = DirectedAcyclicGraph(transformations, data_dependencies)
Audit_Trail = {
    source_system: "PostgreSQL Customer DB",
    transformation_steps: ["validate", "enrich", "normalize", "aggregate"],
    business_rules_applied: ["customer_status_mapping", "account_classification"],
    data_quality_checks: ["completeness", "validity", "consistency"],
    target_system: "Regulatory Data Warehouse"
}
```

### Regulatory Compliance
- **Data Retention**: 7 years (configurable retention policies)
- **Audit Requirements**: Complete transformation history
- **Data Privacy**: PII masking and encryption at rest
- **Change Management**: Version control for business rules

## Cost Optimization

### Processing Efficiency
```
CPU Hours per Day: 8 cores × 24 hours = 192 core-hours
Processing Cost: 192 × $0.05 = ~$9.60/day
Monthly Processing Cost: $9.60 × 30 = ~$288/month
```

### Storage Optimization
```
Raw Data Storage: 50GB/day × 30 days = 1.5TB/month
Compressed Storage: 1.5TB × 0.3 = 0.45TB/month (70% compression)
Storage Cost: 0.45TB × $20/TB = ~$9/month
```

### Network Costs
```
Data Transfer: 1.5TB/month between systems
Internal Transfer Cost: $0 (within same cloud region)
External API Calls: 100K calls/month × $0.001 = ~$100/month
```

## Next Steps

1. **Design Transformation Logic**: Map business rules to NiFi processors
2. **Implement Data Quality Framework**: Build validation and error handling
3. **Create Lookup Services**: Configure reference data management
4. **Test End-to-End Pipeline**: Validate with realistic data volumes
5. **Performance Optimization**: Tune based on actual processing patterns

---

*"ETL success lies in the mathematical elegance of data transformation graphs - where every node serves a purpose and every edge carries meaning."*