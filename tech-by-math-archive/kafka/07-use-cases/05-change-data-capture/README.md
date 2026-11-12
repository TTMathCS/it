# Change Data Capture (CDC)

## Overview
Synchronize product catalog changes across multiple systems (search index, cache, analytics) in real-time using Kafka Connect and Debezium for reliable data streaming.

## Business Problem
**Challenge**: RetailCorp needs to keep search engines, caches, and analytics systems synchronized with database changes without impacting production database performance.

## Mathematical Foundation
```
Database Change Rate: 1,000 changes/minute peak
Processing Latency Target: <100ms end-to-end
Consistency Model: Eventual consistency with ordering guarantees
Convergence Time: Network_Delay + Processing_Time = 5ms + 20ms = 25ms avg
```

## Architecture
```
MySQL Database → Debezium CDC → Kafka → Search Indexer
                                      → Cache Invalidator
                                      → Analytics Updater
                                      → Backup System
```

## Key Topics
- **retailcorp.product_catalog.products** (8 partitions, 30-day retention)
- **retailcorp.product_catalog.categories** (4 partitions, 30-day retention)
- **schema-changes** (1 partition, 365-day retention)

## Simplified Workflow

### 1. CDC Connector Configuration
```json
{
  "name": "product-catalog-connector",
  "config": {
    "connector.class": "io.debezium.connector.mysql.MySqlConnector",
    "database.hostname": "mysql-primary",
    "database.server.name": "retailcorp",
    "table.include.list": "product_catalog.products,product_catalog.categories",
    "transforms": "unwrap",
    "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState"
  }
}
```

### 2. Change Event Processing
```java
@KafkaListener(topics = "retailcorp.product_catalog.products")
public void handleProductChange(
        @Header("__op") String operation,
        @Payload ProductChangeEvent event) {
    
    switch (operation) {
        case "c":  // Create
            handleProductCreated(event.getAfter());
            break;
        case "u":  // Update
            handleProductUpdated(event.getBefore(), event.getAfter());
            break;
        case "d":  // Delete
            handleProductDeleted(event.getBefore());
            break;
    }
}
```

### 3. Exactly-Once Processing
```java
@Transactional("kafkaTransactionManager")
public void processProductChange(ProductChangeEvent event) {
    // Idempotency check using database transaction ID
    if (changeExists(event.getTransactionId(), event.getOffset())) return;
    
    // Update local systems within transaction
    productRepository.save(event.getAfter());
    kafkaTemplate.send("product-search-updates", createSearchEvent(event));
    kafkaTemplate.send("product-cache-invalidations", createCacheEvent(event));
    
    // Record processing to prevent duplicates
    processedChangeRepository.save(new ProcessedChange(event));
}
```

## Data Consistency Analysis
```
Ordering Guarantee: Per-partition ordering maintained
- Changes for same product ID → same partition (by primary key)
- Maintains causal ordering of database operations

Recovery Time Analysis:
Failure_Detection = 30s (heartbeat timeout)
Consumer_Restart = 10s (application startup)
Catch_up_Time = Backlog_Size ÷ Processing_Rate
Total_Recovery = 40s + Catch_up_Time

For 1000 pending changes at 100 changes/second:
Total_Recovery = 40s + (1000 ÷ 100)s = 50s
```

## Key Metrics
- **Change Processing Rate**: 1,000+ changes/minute sustained
- **End-to-End Latency**: <100ms (95th percentile)
- **Data Freshness**: Systems synchronized within 50ms
- **Reliability**: Zero data loss with exactly-once processing

## Benefits
- **Real-time Synchronization**: Immediate data consistency across systems
- **Zero Database Impact**: No additional load on production database
- **Complete Audit Trail**: Full history of all data changes
- **Fault Tolerance**: Automatic recovery from failures with no data loss