# Algorithms: NiFi's Mathematical Engine

> *"NiFi's power lies not just in its visual interface, but in the sophisticated algorithms that optimize data flow automatically."*

## Overview

This section explores the core algorithms that power NiFi's data flow optimization, scheduling, and resource management. Understanding these algorithms enables better flow design and performance tuning.

## Core Algorithm Categories

### 1. Flow Optimization Algorithms 🚀

#### Topological Sorting
**Purpose**: Determines safe execution order for processors in a DAG.

**Algorithm**: Kahn's Algorithm
```
Input: Directed Acyclic Graph G = (V, E)
Output: Topologically sorted order

1. Calculate in-degree for each vertex
2. Add vertices with in-degree 0 to queue
3. While queue is not empty:
   - Remove vertex from queue
   - Add to sorted order
   - Decrease in-degree of all neighbors
   - Add neighbors with in-degree 0 to queue
4. Return sorted order
```

**NiFi Application**: Ensures processors execute in dependency order, preventing deadlocks.

#### Load Balancing Algorithm
**Purpose**: Distributes FlowFiles across multiple processor instances.

**Round-Robin Distribution**:
```
def distribute_flowfiles(flowfiles, processor_instances):
    current_instance = 0
    for flowfile in flowfiles:
        assign_to_processor(flowfile, processor_instances[current_instance])
        current_instance = (current_instance + 1) % len(processor_instances)
```

**Least Connections Algorithm**:
```
def least_connections_balance(flowfiles, processor_instances):
    for flowfile in flowfiles:
        least_busy = min(processor_instances, key=lambda p: p.active_tasks)
        assign_to_processor(flowfile, least_busy)
```

### 2. Scheduling Algorithms ⏰

#### Timer-Driven Scheduling
**Purpose**: Executes processors at fixed intervals.

**Algorithm**: Periodic execution with configurable intervals
```
class TimerScheduler:
    def schedule_processor(self, processor, interval_seconds):
        while processor.is_running():
            execute_processor_cycle(processor)
            sleep(interval_seconds)
```

**Mathematical Model**: Fixed-rate execution following periodic function `f(t) = t mod interval`

#### Event-Driven Scheduling  
**Purpose**: Executes processors when FlowFiles are available.

**Algorithm**: Reactive execution based on queue state
```
class EventScheduler:
    def monitor_queues(self):
        for connection in self.connections:
            if connection.has_flowfiles() and not connection.backpressure_active():
                schedule_downstream_processor(connection.destination)
```

**Mathematical Model**: Event-driven execution following Poisson arrival process

#### CRON-Based Scheduling
**Purpose**: Executes processors based on calendar schedules.

**Algorithm**: Cron expression evaluation
```
def evaluate_cron(cron_expression, current_time):
    # Parse: minute hour day month weekday
    # Return: True if current_time matches expression
    return cron_match(cron_expression, current_time)
```

### 3. Backpressure Management 🛡️

#### Queue-Based Backpressure
**Purpose**: Prevents system overload through automatic flow control.

**Threshold Algorithm**:
```
def check_backpressure(connection):
    return (connection.queue_size >= connection.size_threshold or 
            connection.oldest_flowfile_age >= connection.age_threshold)

def apply_backpressure(connection):
    if check_backpressure(connection):
        connection.source_processor.throttle_execution()
        return True
    return False
```

**Mathematical Model**: Binary control system with hysteresis
```
backpressure_on = queue_size ≥ threshold_high
backpressure_off = queue_size ≤ threshold_low (where threshold_low < threshold_high)
```

#### Exponential Backoff
**Purpose**: Gradually reduces processing rate when backpressure occurs.

**Algorithm**:
```
def exponential_backoff(attempt_count, base_delay=1.0, max_delay=60.0):
    delay = min(base_delay * (2 ** attempt_count), max_delay)
    return delay
```

**Mathematical Formula**: `delay = min(base_delay × 2^attempt, max_delay)`

### 4. Clustering and Coordination 🤝

#### Leader Election Algorithm
**Purpose**: Selects primary coordinator in NiFi cluster.

**Raft Consensus Algorithm** (simplified):
```
class RaftNode:
    def start_election(self):
        self.current_term += 1
        self.vote_for_self()
        
        votes_received = 1
        for node in self.cluster_nodes:
            if node.request_vote(self.current_term):
                votes_received += 1
                
        if votes_received > len(self.cluster_nodes) / 2:
            self.become_leader()
```

**Mathematical Property**: Requires majority consensus (> n/2 votes) for safety

#### State Synchronization
**Purpose**: Keeps cluster nodes synchronized.

**Eventually Consistent Model**:
```
def synchronize_state(local_state, remote_states):
    merged_state = local_state.copy()
    
    for remote_state in remote_states:
        for key, value in remote_state.items():
            if key not in merged_state or value.timestamp > merged_state[key].timestamp:
                merged_state[key] = value
                
    return merged_state
```

### 5. Resource Management 💾

#### Memory Management Algorithm
**Purpose**: Manages FlowFile content claims and repository space.

**Reference Counting**:
```
class ContentRepository:
    def create_claim(self, content):
        claim_id = generate_uuid()
        self.claims[claim_id] = ContentClaim(content, ref_count=1)
        return claim_id
        
    def increment_claim(self, claim_id):
        self.claims[claim_id].ref_count += 1
        
    def decrement_claim(self, claim_id):
        self.claims[claim_id].ref_count -= 1
        if self.claims[claim_id].ref_count == 0:
            self.delete_content(claim_id)
```

#### Disk Space Management
**Purpose**: Manages repository disk usage with automatic cleanup.

**LRU Eviction Algorithm**:
```
class LRURepository:
    def evict_old_content(self, space_needed):
        sorted_claims = sorted(self.claims.items(), 
                             key=lambda x: x[1].last_accessed)
        
        space_freed = 0
        for claim_id, claim in sorted_claims:
            if space_freed >= space_needed:
                break
            self.delete_claim(claim_id)
            space_freed += claim.size
```

## Performance Optimization Algorithms

### Flow Path Optimization

**Shortest Path for Latency**:
```
def optimize_for_latency(flow_graph):
    # Use Dijkstra's algorithm with processing time as weight
    return dijkstra_shortest_path(flow_graph, weight='processing_time')
```

**Maximum Flow for Throughput**:
```
def optimize_for_throughput(flow_graph):
    # Use Ford-Fulkerson with capacity constraints
    return ford_fulkerson_max_flow(flow_graph, weight='max_capacity')
```

### Dynamic Load Balancing

**Weighted Round-Robin**:
```
def weighted_round_robin(flowfiles, processors):
    total_weight = sum(p.performance_weight for p in processors)
    
    for flowfile in flowfiles:
        # Select processor based on weight distribution
        selected = weighted_random_choice(processors, 'performance_weight')
        assign_to_processor(flowfile, selected)
```

**Adaptive Load Balancing**:
```
def adaptive_load_balance(flowfiles, processors):
    # Adjust weights based on recent performance
    for processor in processors:
        recent_performance = calculate_recent_throughput(processor)
        processor.performance_weight = recent_performance
    
    return weighted_round_robin(flowfiles, processors)
```

## Algorithm Complexity Analysis

### Time Complexity

| Algorithm | Best Case | Average Case | Worst Case |
|-----------|-----------|--------------|------------|
| Topological Sort | O(V + E) | O(V + E) | O(V + E) |
| Load Balancing | O(1) | O(1) | O(n) |
| Backpressure Check | O(1) | O(1) | O(1) |
| Leader Election | O(n) | O(n log n) | O(n²) |
| Content Cleanup | O(1) amortized | O(log n) | O(n) |

### Space Complexity

| Component | Memory Usage | Disk Usage |
|-----------|-------------|------------|
| FlowFile Repository | O(active_flowfiles) | O(total_flowfiles) |
| Content Repository | O(unique_content) | O(total_content_size) |
| Provenance Repository | O(1) | O(historical_events) |
| Configuration | O(processors + connections) | O(flow_definition) |

## Real-World Algorithm Tuning

### Backpressure Tuning

**Conservative Settings** (High Reliability):
```
connection.backpressure.object.threshold = 1000
connection.backpressure.size.threshold = 100 MB
connection.backpressure.age.threshold = 5 minutes
```

**Aggressive Settings** (High Throughput):
```
connection.backpressure.object.threshold = 100000
connection.backpressure.size.threshold = 10 GB  
connection.backpressure.age.threshold = 60 minutes
```

### Scheduling Optimization

**CPU-Intensive Processors**:
```
# Reduce concurrent tasks to prevent CPU thrashing
nifi.processor.scheduling.strategy = TIMER_DRIVEN
nifi.processor.run.schedule = 100 ms
nifi.processor.max.concurrent.tasks = 2
```

**I/O-Bound Processors**:
```
# Increase concurrency to maximize I/O utilization  
nifi.processor.scheduling.strategy = EVENT_DRIVEN
nifi.processor.max.concurrent.tasks = 10
```

## Algorithm Monitoring and Metrics

### Performance Metrics

**Throughput Measurement**:
```
throughput = flowfiles_processed / time_period
latency = average_time_in_system_per_flowfile  
utilization = active_processing_time / total_time
```

**Resource Utilization**:
```
memory_utilization = used_heap_memory / max_heap_memory
disk_utilization = repository_size / available_disk_space
cpu_utilization = processing_threads / available_cores
```

### Algorithm Effectiveness

**Load Balancing Effectiveness**:
```
balance_score = 1 - (max_load - min_load) / max_load
where load = processor_utilization
```

**Backpressure Efficiency**:
```
backpressure_efficiency = uptime_without_overflow / total_uptime
```

## Next Steps

1. 🔧 **Apply to [Use Cases](../07-use-cases/index.md)** - See algorithms in action with real scenarios
2. 🧪 **Test in [Experiments](../05-experiments/index.md)** - Measure algorithm performance empirically  
3. 📊 **Study [Failure Models](../04-failure-models/index.md)** - Understand algorithm behavior under stress
4. 📚 **Reference [Academic Papers](../06-references/index.md)** - Deep dive into algorithm theory

---

*"Great algorithms are invisible - they optimize performance so seamlessly that users focus on business logic, not technical complexity."*