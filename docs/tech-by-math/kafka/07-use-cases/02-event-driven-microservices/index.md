# Event-Driven Microservices

## Overview
Build resilient payment processing system with event-driven architecture using Kafka for service decoupling and reliable message delivery.

## Business Problem
**Challenge**: FinTech platform needs to coordinate multiple services (payment, inventory, notification, fraud detection) while maintaining consistency and fault tolerance.

## Mathematical Foundation
```
Service Chain Availability: Individual service = 99.9%
Number of Services: 5
Base Availability: (0.999)^5 = 99.5%
With Compensation: 99.5% + (1-99.5%) × 95% = 99.975%
```

## Architecture
```
Payment API → payment-events → Order Service
                             → Inventory Service
                             → Notification Service
                             → Fraud Detection
                             → Analytics Service
```

## Key Topics
- **payment-events** (6 partitions, 30-day retention)
- **order-events** (4 partitions, 90-day retention)
- **inventory-events** (8 partitions, 7-day retention)

## Simplified Workflow

### 1. Event Schema
```json
{
  "event_id": "uuid",
  "event_type": "PAYMENT_INITIATED|COMPLETED|FAILED",
  "user_id": "string",
  "amount": "decimal",
  "correlation_id": "uuid"
}
```

### 2. Saga Pattern Implementation
```java
@KafkaListener(topics = "payment-events")
public void handlePaymentEvent(PaymentEvent event) {
    switch (event.getEventType()) {
        case PAYMENT_INITIATED:
            processPaymentInitiation(event);
            break;
        case PAYMENT_COMPLETED:
            completePaymentSaga(event);
            break;
        case PAYMENT_FAILED:
            rollbackPaymentSaga(event);
            break;
    }
}
```

### 3. Exactly-Once Processing
```java
@Transactional("kafkaTransactionManager")
public void processPayment(PaymentEvent event) {
    // Idempotency check
    if (paymentExists(event.getCorrelationId())) return;
    
    // Business logic + event publishing in transaction
    Payment payment = paymentRepository.save(new Payment(event));
    kafkaTemplate.send("payment-completed", successEvent);
}
```

## Performance Analysis
```
Expected Processing Time per Payment:
- Payment validation: 50ms
- Inventory check: 30ms (parallel with fraud check: 80ms)
- Payment processing: 200ms
- Event publishing: 10ms
Total: 50ms + 80ms + 200ms + 10ms = 340ms
```

## Key Metrics
- **Processing Time**: <500ms per transaction (95th percentile)
- **Success Rate**: >99.9% transaction completion
- **Recovery Time**: <60 seconds for failed transactions
- **Throughput**: 1,000+ transactions/second

## Benefits
- **Service Decoupling**: Services communicate via events, not direct calls
- **Fault Tolerance**: Automatic retry and compensation mechanisms
- **Scalability**: Independent scaling of each microservice
- **Auditability**: Complete event history for compliance and debugging