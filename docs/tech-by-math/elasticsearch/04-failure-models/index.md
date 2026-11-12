# Failure Models: Error Handling and Resilience

> *"In distributed systems, failure is not an exception—it's the norm. Design for failure from the beginning."* - Distributed Systems Architecture

## Overview

Elasticsearch operates in distributed environments where failures are inevitable. This section explores the mathematical models for understanding, predicting, and mitigating various types of failures that can affect search and analytics operations. We examine network partitions, node failures, data corruption, and performance degradation through probabilistic models and resilience strategies.

## Types of System Failures

### Node Failures

**Crash-Stop Failures**:
```
Probability Model: P(node_failure) = 1 - e^(-λt)
where λ = failure rate (failures per unit time)
      t = operational time

Mean Time Between Failures (MTBF): E[T] = 1/λ
Mean Time To Repair (MTTR): E[R] = 1/μ where μ = repair rate

Availability: A = MTBF / (MTBF + MTTR) = λ / (λ + μ)
```

**Byzantine Failures** (Arbitrary behavior):
```
Detection Probability: P(detection) = 1 - (2/3)^n
where n = number of monitoring nodes

Byzantine Fault Tolerance: Requires 3f + 1 nodes to tolerate f failures
Consensus Safety: Guaranteed with > 2/3 honest nodes
```

**Transient Failures** (Temporary unavailability):
```
Recovery Model: P(recovery) = 1 - e^(-μt)
where μ = recovery rate

Expected Recovery Time: E[recovery] = 1/μ
```

### Network Failures

**Partition Probability Model**:
```
Link Failure Model: P(link_failure) = 1 - e^(-λ_link × t)
Network Partition: P(partition) ≈ k × P(link_failure)
where k = critical links for connectivity

Partition Duration: Exponentially distributed with rate μ_repair
Expected Duration: E[partition_time] = 1/μ_repair
```

**Message Loss and Delay**:
```
Message Loss: P(loss) = p per message
Cumulative Loss: P(k losses in n messages) = C(n,k) × p^k × (1-p)^(n-k)

Network Delay: Log-normal distribution
P(delay > t) = 1 - Φ((ln(t) - μ)/σ)
where Φ = standard normal CDF
```

### Data Corruption

**Silent Data Corruption**:
```
Bit Error Rate: BER = number of error bits / total bits transmitted
Sector Error Rate: SER ≈ BER × sector_size_bits

Detection Probability with Checksums:
P(detection) = 1 - (1/2)^checksum_bits

Undetected Error Rate: UER = BER × (1 - P(detection))
```

**Disk Failures**:
```
Bathtub Curve Model:
λ(t) = λ₀ + βt^(β-1) + λ₁

Early Life: λ₀ (manufacturing defects)
Useful Life: Constant failure rate
Wear-out: λ₁ (mechanical degradation)

Annual Failure Rate (AFR): Typically 0.5-2% for enterprise drives
```

## Resilience Strategies

### Replication Models

**Primary-Backup Replication**:
```
Consistency Model:
- Strong Consistency: Read/Write to primary only
- Eventual Consistency: Writes propagate asynchronously

Failure Recovery Time:
T_recovery = T_detection + T_leader_election + T_state_transfer

Availability with n replicas:
A_system = 1 - P(all_replicas_fail)^n ≈ 1 - (1-A_node)^n
```

**Quorum-Based Systems**:
```
Quorum Size: Q = floor(n/2) + 1 for majority
Write Quorum: W nodes must acknowledge write
Read Quorum: R nodes must respond to read

Consistency Guarantee: R + W > n ensures strong consistency
Availability: System available if ≥ Q nodes operational

CAP Theorem Trade-off:
- CP System: Unavailable during partitions (W ≥ Q)
- AP System: Inconsistent during partitions (W < Q)
```

### Circuit Breaker Pattern

**Mathematical Model**:
```
States: CLOSED, OPEN, HALF_OPEN
Failure Threshold: τ failures in window W

Transition Probabilities:
P(CLOSED → OPEN) = 1 if failure_count ≥ τ
P(OPEN → HALF_OPEN) = 1 after timeout T_open
P(HALF_OPEN → CLOSED) = 1 if success_count ≥ σ
P(HALF_OPEN → OPEN) = 1 if failure occurs

Success Rate Recovery:
Expected recovery time: E[T] = T_open + (expected probe attempts × T_probe)
```

### Exponential Backoff

**Backoff Strategy**:
```
Wait Time: T_wait = min(T_max, T_base × 2^attempt_number)
With Jitter: T_wait = T_wait × (0.5 + random(0, 0.5))

Collision Probability: P(collision) = 1/2^attempt_number
Expected Attempts: E[attempts] = ∑(k × P(success_on_attempt_k))

Load Reduction: Factor = 1 / (1 + retry_rate × backoff_factor)
```

### Bulkhead Pattern

**Resource Isolation**:
```
Thread Pool Sizing: N_threads = N_cores × (1 + wait_time/service_time)
Connection Pool: N_connections = throughput × average_latency

Failure Containment:
P(cascade_failure) = P(resource_exhaustion) × P(dependency_failure)

Isolation Effectiveness: 1 - P(cross_pool_impact)
```

## Performance Degradation Models

### Queue Theory for Load Handling

**M/M/1 Queue Model**:
```
Arrival Rate: λ requests/second
Service Rate: μ requests/second
Utilization: ρ = λ/μ

Response Time: E[T] = 1/(μ - λ) = 1/(μ(1 - ρ))
Queue Length: E[N] = ρ/(1 - ρ)

Stability Condition: ρ < 1 (arrival rate < service rate)
```

**Load Shedding Strategy**:
```
Admission Control: P(admit) = max(0, 1 - (current_load/capacity)^α)
where α controls admission curve steepness

Drop Probability: P(drop) = min(1, (queue_size/max_queue_size)^β)

Throughput under overload: T = μ × (1 - P(drop))
```

### Cascading Failure Prevention

**Failure Propagation Model**:
```
Basic Reproduction Number: R₀ = β × k × D
where β = transmission probability
      k = average connections per node  
      D = duration of infectious period

Cascade Threshold: Critical failure fraction = 1/R₀
Epidemic Prevention: R₀ < 1 prevents cascade

Mitigation Strategies:
- Reduce β: Circuit breakers, timeouts
- Reduce k: Service isolation, bulkheads  
- Reduce D: Fast failure detection, quick recovery
```

## Monitoring and Detection

### Anomaly Detection Models

**Statistical Process Control**:
```
Control Limits: μ ± k×σ where k typically = 2 or 3
Out of Control: P(false_alarm) = P(|X| > k×σ) ≈ 2×(1 - Φ(k))

EWMA (Exponentially Weighted Moving Average):
EWMA_t = λ×X_t + (1-λ)×EWMA_(t-1)
Control Limit: μ ± L×σ×√(λ/(2-λ))

Detection Delay: ARL (Average Run Length) = 1/P(detection_per_sample)
```

**Change Point Detection**:
```
CUSUM Algorithm:
S_t = max(0, S_(t-1) + (X_t - μ₀ - δ/2))
Alarm when S_t > h (threshold)

Detection Probability: P_d = 1 - β (Type II error)
False Alarm Rate: FAR = α (Type I error)

Average Run Length to Detection: ARL₁ ≈ (log(1-β))/(-log(1-α))
```

### Health Check Strategies

**Heartbeat Protocol**:
```
Heartbeat Interval: T_hb
Failure Detection Time: T_fd = k × T_hb (after k missed beats)

False Positive Rate: P(false_positive) = P(network_delay > T_fd)
False Negative Rate: P(false_negative) = P(node_fails_between_beats)

Optimal Heartbeat: T_optimal = √(C_network/C_false_positive × MTBF)
```

**Gossip-Based Failure Detection**:
```
Gossip Period: T_gossip
Propagation Time: E[T_prop] = log(n) × T_gossip
where n = number of nodes

Detection Accuracy: Improves with redundant reports
P(correct_detection) = 1 - (1 - p)^k
where p = individual detector accuracy, k = reports
```

## Recovery Strategies

### Data Recovery Models

**RAID Recovery**:
```
RAID 1 (Mirroring):
MTTR = 1/μ (single disk repair time)
Data Loss Probability: P(loss) = (λ × MTTR)² (both disks fail)

RAID 5 (Parity):
Rebuild Time: T_rebuild = disk_size / rebuild_throughput  
URE (Unrecoverable Read Error): ≈ 10^(-14) to 10^(-15) per bit
P(data_loss) ≈ n × disk_size × URE during rebuild

RAID 6 (Double Parity):
Tolerates 2 simultaneous failures
P(data_loss) ≈ C(n,3) × (λ × MTTR)³
```

**Distributed System Recovery**:
```
State Transfer Models:
- Full State: T_recovery = state_size / network_bandwidth
- Incremental: T_recovery = changed_state / bandwidth
- Log Replay: T_recovery = log_entries × processing_time

Checkpointing Strategy:
Checkpoint Interval: T_opt = √(2 × checkpoint_cost / failure_rate)
Recovery Time: E[T_recovery] = checkpoint_interval/2 + log_replay_time
```

### Consensus During Failures

**Raft Consensus**:
```
Leader Election:
Election Timeout: Randomized in [T, 2T] to avoid split votes
Term Length: Until leader failure or new election

Log Replication:
Majority Requirement: ⌊n/2⌋ + 1 acknowledgments  
Commit Rule: Entry committed when majority replicated

Safety Properties:
- Election Safety: ≤ 1 leader per term
- Leader Append-Only: Leaders never overwrite entries
- Log Matching: Identical entries at same index/term
- Leader Completeness: Committed entries appear in future leaders
- State Machine Safety: Same command at index → same result
```

**Byzantine Fault Tolerance**:
```
PBFT (Practical Byzantine Fault Tolerance):
Phases: Pre-prepare, Prepare, Commit
Message Complexity: O(n²) per operation
Fault Tolerance: f < n/3 Byzantine nodes

View Change Protocol:
Timeout-based leader change
New view requires 2f+1 view-change messages
Safety: Ensures liveness despite f Byzantine failures
```

## Capacity Planning Under Failures

### Redundancy Calculations

**N+K Redundancy**:
```
Active Units: N (minimum required)
Spare Units: K (redundancy)
Total Units: N + K

Availability: A = ∑(i=0 to K) C(N+K, i) × A_unit^(N+K-i) × (1-A_unit)^i
where sum includes states with ≤ K failures

Cost-Effectiveness: Marginal availability per additional spare unit
ΔA/ΔCost = (A_(N+K+1) - A_(N+K)) / unit_cost
```

**Load-Based Capacity**:
```
Peak Load Multiplier: M = peak_load / average_load
Safety Factor: S = capacity / (peak_load × (1 - planned_failure_rate))

Required Capacity: C = M × average_load × S / (1 - failure_probability)

Over-provisioning: OP = (deployed_capacity - minimum_capacity) / minimum_capacity
```

### Cost-Benefit Analysis

**Availability Investment**:
```
Cost of Downtime: C_down = revenue_loss_rate × downtime_hours
Cost of High Availability: C_ha = infrastructure_cost + operational_cost

Break-even Analysis:
Investment justified when: C_ha < C_down × P(downtime) × business_impact

Diminishing Returns:
Additional investment effectiveness decreases as availability approaches 100%
Marginal cost per "nine": Cost increases exponentially (90% → 99% → 99.9%)
```

### SLA Design

**Service Level Objectives**:
```
Availability Target: 99.9% (8.77 hours downtime/year)
Error Budget: 0.1% = 43.8 minutes/month

Error Budget Allocation:
- Planned Maintenance: 50%
- Infrastructure Failures: 30%  
- Application Issues: 20%

Burn Rate: Current error rate / error budget rate
Alert Threshold: Burn rate > budget_depletion_acceptable_time
```

## Real-World Failure Scenarios

### Search Service Degradation

**Scenario: Query Latency Spike**:
```
Normal Response Time: P50 = 100ms, P99 = 500ms
Degraded Performance: P50 = 2s, P99 = 10s

User Impact Model:
P(user_abandonment) = 1 - e^(-latency/tolerance_threshold)
Tolerance Threshold: ~3 seconds for search applications

Revenue Impact: abandonment_rate × conversion_rate × average_order_value
```

**Mitigation Strategy**:
```
Circuit Breaker: Open after 10 consecutive timeouts > 1s
Fallback Response: Cached results or simplified search
Recovery: Gradual traffic increase after P99 < 2s for 60s

Load Shedding: Drop 20% of traffic when P95 > 1.5s
Priority Queue: VIP users get normal service during degradation
```

### Data Consistency Issues

**Scenario: Split-Brain During Network Partition**:
```
Partition Probability: P(partition) = 0.001 (network reliability)
Resolution Time: T_resolution = detection_time + manual_intervention
Data Divergence: Operations_in_partition × time_to_resolution

Consistency Repair:
- Vector Clock Comparison: O(n) for conflict detection
- Last-Writer-Wins: Simple but may lose data
- Merge Functions: Application-specific conflict resolution
```

**Prevention Strategy**:
```
Quorum Requirements: W + R > N ensures consistency
Witness Node: Prevents split-brain in two-datacenter setup
Fencing: Disable minority partition to prevent writes

Monitoring: Alert on partition detection within 30 seconds
Automation: Automatic failover only with clear majority
```

### Cascading Failures

**Scenario: Load-Induced Cascade**:
```
Initial Trigger: 20% increase in query volume
Service Degradation: Response time increases → timeout rate increases
Cascade Effect: Retries amplify load → more services degrade

Mathematical Model:
Load_amplification = base_load × (1 + retry_rate × timeout_rate)
Cascade_factor = ∏(service_dependency_chain) amplification_factors

Recovery Strategy:
- Exponential Backoff: Reduces retry storm
- Circuit Breakers: Isolates failing services  
- Load Shedding: Maintains core service availability
```

---

## Failure Prediction Models

### Predictive Maintenance

**Survival Analysis**:
```
Hazard Function: λ(t) = f(t) / (1 - F(t))
where f(t) = probability density, F(t) = cumulative distribution

Weibull Distribution: Common for reliability modeling
λ(t) = (β/η) × (t/η)^(β-1)
where β = shape parameter, η = scale parameter

Predictive Indicators:
- Disk SMART metrics
- Memory error rates  
- Network packet loss
- CPU temperature trends
```

### Machine Learning for Failure Prediction

**Feature Engineering**:
```
Time Series Features:
- Moving averages (1h, 24h, 7d)
- Rate of change (first derivative)
- Volatility (rolling standard deviation)
- Seasonal decomposition

Leading Indicators:
- Resource utilization trends
- Error rate patterns
- Performance metric drift
- Dependency health scores
```

---

## Testing Failure Scenarios

### Chaos Engineering

**Failure Injection Framework**:
```
Failure Types:
- Latency injection: Add random delays
- Packet loss: Drop network packets  
- Resource exhaustion: Consume CPU/memory
- Dependency failures: Mock service unavailability

Blast Radius Control:
- Start with non-production environments
- Limit impact scope (single service, region)
- Implement kill switches for experiments
- Monitor business metrics during tests

Hypothesis Testing:
H₀: System maintains SLA during failure
H₁: System degrades beyond acceptable limits
Statistical significance: p < 0.05 for experiment conclusions
```

### Disaster Recovery Testing

**Recovery Time Objectives**:
```
RTO (Recovery Time Objective): Maximum acceptable downtime
RPO (Recovery Point Objective): Maximum acceptable data loss

DR Testing Schedule:
- Tabletop exercises: Monthly discussion-based
- Component testing: Weekly automated tests
- Full DR drill: Quarterly complete failover
- Chaos experiments: Daily controlled failures

Success Metrics:
- Actual RTO vs target RTO
- Data consistency verification
- Service functionality validation
- Team response time effectiveness
```

---

## Best Practices Summary

### Design Principles
1. **Fail Fast**: Detect and report failures immediately
2. **Graceful Degradation**: Reduce functionality rather than complete failure
3. **Isolation**: Prevent failure propagation between components
4. **Redundancy**: Multiple layers of backup and failover
5. **Monitoring**: Comprehensive observability and alerting

### Implementation Guidelines
1. **Timeouts**: Set at every service boundary
2. **Retries**: Implement exponential backoff with jitter
3. **Circuit Breakers**: Protect against cascading failures
4. **Health Checks**: Deep and shallow health verification
5. **Capacity Planning**: Plan for N+1 or N+2 redundancy

---

> *"The best failure is one that teaches you something and happens in a safe environment."* - Chaos Engineering Principle

**Next**: [Experiments - Practical Resilience Testing](../05-experiments/index.md) 🧪  
**Previous**: [Algorithms - Search and Indexing](../03-algorithms/index.md) ⚡