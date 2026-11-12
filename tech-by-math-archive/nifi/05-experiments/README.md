# Experiments: Hands-On NiFi Mathematical Validation

> *"Theory without practice is sterile, but practice without theory is blind. NiFi experiments bridge mathematical concepts with real-world performance."*

## Overview

This section provides hands-on experiments to validate NiFi's mathematical properties and measure real-world performance against theoretical models.

## Experiment Categories

### 1. Flow Network Performance 📊

#### Experiment 1: Throughput vs. Latency Trade-offs

**Objective**: Validate queuing theory predictions for NiFi flow performance.

**Setup**:
```
Source → Transform → Sink
- GenerateFlowFile (configurable rate)
- UpdateAttribute (simulated processing time)  
- LogAttribute (measure completion time)
```

**Variables**:
- Input rate: 100, 500, 1000, 5000 FlowFiles/second
- Processing time: 10ms, 50ms, 100ms, 500ms per FlowFile
- Queue size: 1000, 10000, 100000 objects

**Measurements**:
```python
# Key metrics to collect
throughput = completed_flowfiles / time_period
average_latency = sum(completion_times) / flowfile_count
queue_depth = average_queue_size_over_time
utilization = processing_time / total_time
```

**Expected Results**: Validate Little's Law (L = λW)
```
theoretical_queue_length = arrival_rate * average_processing_time
measured_queue_length = observed_average_queue_depth
```

#### Experiment 2: Backpressure Effectiveness

**Objective**: Measure backpressure algorithm performance under load.

**Setup**:
```
FastSource → SlowProcessor → Sink
- GenerateFlowFile (high rate)
- Sleep processor (simulate bottleneck)
- Monitor queue buildup and recovery
```

**Test Scenarios**:
1. **No Backpressure**: Monitor system behavior until failure
2. **Conservative Thresholds**: 1000 objects, 100MB, 1 minute
3. **Aggressive Thresholds**: 100000 objects, 10GB, 60 minutes

### 2. Algorithm Validation 🧮

#### Experiment 3: Load Balancing Efficiency

**Objective**: Compare load balancing algorithms in NiFi clusters.

**Setup**:
```python
# Simulate different load balancing strategies
strategies = [
    "round_robin",
    "least_connections", 
    "weighted_round_robin",
    "random"
]

# Measure distribution effectiveness
def measure_load_distribution(strategy, duration_minutes=10):
    processor_loads = {}
    total_processed = 0
    
    # Run test and collect metrics
    results = run_load_test(strategy, duration_minutes)
    
    # Calculate balance score
    max_load = max(processor_loads.values())
    min_load = min(processor_loads.values()) 
    balance_score = 1 - (max_load - min_load) / max_load
    
    return balance_score
```

#### Experiment 4: Clustering Consensus Performance

**Objective**: Measure leader election time under various failure scenarios.

**Test Cases**:
1. **Clean Election**: Start cluster from scratch
2. **Leader Failure**: Kill current leader, measure election time
3. **Network Partition**: Isolate nodes, measure split-brain handling
4. **Rejoining Nodes**: Node returns after partition heals

### 3. Failure Recovery Validation 🛠️

#### Experiment 5: Recovery Time Measurement

**Objective**: Validate theoretical recovery models against actual performance.

**Failure Scenarios**:
```python
failure_tests = [
    {
        "type": "processor_crash",
        "expected_recovery": "< 30 seconds",
        "data_loss": "none (guaranteed delivery)"
    },
    {
        "type": "node_failure", 
        "expected_recovery": "< 60 seconds",
        "data_loss": "none (cluster failover)"
    },
    {
        "type": "network_partition",
        "expected_recovery": "< 300 seconds", 
        "data_loss": "none (consistency over availability)"
    }
]
```

### 4. Mathematical Property Validation 🔬

#### Experiment 6: Information Theory Applications

**Objective**: Measure data entropy and compression effectiveness.

**Setup**:
```python
def measure_data_entropy(data_samples):
    """Calculate Shannon entropy of data stream"""
    from collections import Counter
    import math
    
    # Count symbol frequencies
    symbol_counts = Counter(data_samples)
    total_symbols = len(data_samples)
    
    # Calculate entropy
    entropy = 0
    for count in symbol_counts.values():
        probability = count / total_symbols
        entropy -= probability * math.log2(probability)
    
    return entropy

# Test different data types
test_datasets = [
    "random_data",      # High entropy
    "structured_json",  # Medium entropy  
    "repeated_patterns", # Low entropy
    "compressed_data"   # Very low entropy
]
```

#### Experiment 7: Graph Theory Validation

**Objective**: Verify flow optimization algorithms.

**Test Flow Topologies**:
```
1. Linear Chain: A → B → C → D
2. Fan-Out: A → [B, C, D] → E  
3. Fan-In: [A, B, C] → D → E
4. Complex DAG: Mixed fan-out/fan-in with multiple paths
```

**Measurements**:
- Critical path length (theoretical vs. measured)
- Maximum flow capacity (Ford-Fulkerson prediction vs. actual)
- Bottleneck identification accuracy

## Experimental Setup Scripts

### Environment Preparation

```bash
# NiFi cluster setup for experiments
docker-compose up -d nifi-cluster

# Wait for cluster formation
./scripts/wait-for-cluster.sh

# Load test flow templates
./scripts/load-experiment-templates.sh
```

### Data Generation

```python
# Generate synthetic datasets for testing
def generate_test_data(data_type, size_mb):
    generators = {
        "random": generate_random_data,
        "structured": generate_json_data,
        "temporal": generate_time_series,
        "hierarchical": generate_xml_data
    }
    
    return generators[data_type](size_mb)

# Create reproducible test data
test_datasets = {
    "small": generate_test_data("random", 1),    # 1MB
    "medium": generate_test_data("structured", 100), # 100MB  
    "large": generate_test_data("temporal", 1000)    # 1GB
}
```

### Performance Monitoring

```python
class NiFiPerformanceMonitor:
    def __init__(self, nifi_api_url):
        self.api_url = nifi_api_url
        self.metrics_history = []
        
    def collect_metrics(self):
        """Collect real-time performance metrics"""
        return {
            "throughput": self.get_throughput(),
            "queue_depths": self.get_queue_depths(),
            "processor_utilization": self.get_processor_stats(),
            "memory_usage": self.get_memory_stats(),
            "error_rates": self.get_error_rates()
        }
        
    def run_experiment(self, duration_minutes):
        """Run experiment and collect metrics"""
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        while time.time() < end_time:
            metrics = self.collect_metrics()
            self.metrics_history.append({
                "timestamp": time.time(),
                "metrics": metrics
            })
            time.sleep(10)  # Sample every 10 seconds
            
        return self.analyze_results()
```

## Expected Experimental Results

### Throughput Scalability

**Linear Scaling Hypothesis**:
```
Expected: throughput ∝ number_of_processors (up to bottleneck)
Reality: Overhead from coordination reduces efficiency
```

**Performance Model**:
```
actual_throughput = theoretical_throughput × efficiency_factor
where efficiency_factor = f(cluster_size, coordination_overhead)
```

### Queue Behavior Validation

**Little's Law Validation**:
```
Theory: L = λ × W
Experiment: Measure L, λ, W independently
Expected Result: <5% deviation from theoretical prediction
```

**Backpressure Effectiveness**:
```
Without Backpressure: System failure when λ ≥ μ
With Backpressure: Graceful degradation, no data loss
```

### Failure Recovery Performance

**Recovery Time Objectives**:
```
Processor Failure: <30 seconds (measured vs. theoretical)
Node Failure: <60 seconds (cluster consensus time)
Network Partition: <5 minutes (partition detection + recovery)
```

## Experimental Validation Checklist

### Mathematical Properties
- [ ] Little's Law holds for queue analysis
- [ ] Maximum flow algorithms predict bottlenecks accurately  
- [ ] Load balancing distributes work within 5% of optimal
- [ ] Failure recovery meets theoretical time bounds

### Performance Characteristics  
- [ ] Linear throughput scaling up to resource limits
- [ ] Memory usage grows predictably with flow complexity
- [ ] Network overhead scales logarithmically with cluster size
- [ ] Disk I/O performance matches theoretical models

### Reliability Guarantees
- [ ] Zero data loss under normal failure scenarios
- [ ] Backpressure prevents system overload
- [ ] Cluster maintains consistency during partitions
- [ ] Recovery procedures restore full functionality

## Running the Experiments

### Quick Start

```bash
# Clone experiment repository
git clone https://github.com/nifi-experiments/math-validation.git
cd math-validation

# Set up environment
./scripts/setup-environment.sh

# Run basic validation suite
./scripts/run-basic-experiments.sh

# Generate performance report
./scripts/generate-report.sh
```

### Advanced Testing

```python
# Custom experiment runner
from nifi_experiments import ExperimentRunner

runner = ExperimentRunner()

# Define custom experiment
experiment = {
    "name": "custom_throughput_test",
    "duration": 60,  # minutes
    "variables": {
        "input_rate": [100, 500, 1000],
        "processing_delay": [10, 50, 100],  # ms
        "queue_size": [1000, 10000]
    }
}

# Execute and analyze
results = runner.execute(experiment)
report = runner.generate_analysis(results)
```

## Next Steps

1. 🎯 **Apply to [Use Cases](../07-use-cases/)** - Use experimental insights to optimize real scenarios
2. 📊 **Compare with [Theory](../02-math-toolkit/)** - Validate mathematical models against measurements  
3. ⚙️ **Tune [Algorithms](../03-algorithms/)** - Optimize parameters based on experimental results
4. 📚 **Document [Findings](../06-references/)** - Contribute experimental results to knowledge base

---

*"Experiments transform theoretical understanding into practical wisdom, revealing where mathematics meets the messy reality of distributed systems."*