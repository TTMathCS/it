# Experiments: Hands-on Elasticsearch Demonstrations

> *"In theory, there is no difference between theory and practice. In practice, there is."* - Yogi Berra

## Overview

This section provides practical experiments to demonstrate the mathematical concepts and algorithms discussed in previous sections. Through hands-on examples, you'll explore search relevance, distributed system behavior, performance characteristics, and failure scenarios in controlled environments.

## Search Relevance Experiments

### Experiment 1: TF-IDF vs BM25 Scoring Comparison

**Objective**: Compare the effectiveness of TF-IDF and BM25 ranking functions on a test dataset.

**Setup**:
```bash
# Create test index with dual analyzers
PUT /relevance_test
{
  "settings": {
    "number_of_shards": 1,
    "analysis": {
      "analyzer": {
        "standard_analyzer": {
          "type": "standard"
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "similarity": "BM25"
      },
      "title_tfidf": {
        "type": "text", 
        "similarity": "classic"
      },
      "content": {
        "type": "text"
      }
    }
  }
}

# Index sample documents
POST /relevance_test/_bulk
{"index": {}}
{"title": "Elasticsearch basics tutorial", "title_tfidf": "Elasticsearch basics tutorial", "content": "Learn the fundamentals of Elasticsearch search engine"}
{"index": {}}
{"title": "Advanced Elasticsearch features", "title_tfidf": "Advanced Elasticsearch features", "content": "Explore advanced search capabilities and aggregations"}
{"index": {}}
{"title": "Elasticsearch performance tuning", "title_tfidf": "Elasticsearch performance tuning", "content": "Optimize your Elasticsearch cluster for better performance"}
```

**Experiment**:
```bash
# Query with BM25 scoring
GET /relevance_test/_search
{
  "query": {
    "match": {
      "title": "Elasticsearch tutorial"
    }
  },
  "explain": true
}

# Query with TF-IDF scoring
GET /relevance_test/_search
{
  "query": {
    "match": {
      "title_tfidf": "Elasticsearch tutorial"
    }
  },
  "explain": true
}
```

**Expected Results**:
- BM25 provides better relevance for short documents
- TF-IDF may over-emphasize term frequency in longer documents
- Score explanations show mathematical computation differences

**Analysis**:
```python
# Analyze scoring differences
import json
import matplotlib.pyplot as plt

def compare_scoring_functions(bm25_results, tfidf_results):
    # Extract scores and document lengths
    bm25_scores = [hit['_score'] for hit in bm25_results['hits']['hits']]
    tfidf_scores = [hit['_score'] for hit in tfidf_results['hits']['hits']]
    
    # Correlation analysis
    correlation = np.corrcoef(bm25_scores, tfidf_scores)[0, 1]
    
    # Visualization
    plt.scatter(bm25_scores, tfidf_scores)
    plt.xlabel('BM25 Scores')
    plt.ylabel('TF-IDF Scores')
    plt.title(f'BM25 vs TF-IDF Correlation: {correlation:.3f}')
    
    return correlation
```

### Experiment 2: Field Boosting Impact Analysis

**Objective**: Quantify the effect of field boosting on search results ranking.

**Setup**:
```bash
# Create index with multiple fields
PUT /boost_test
{
  "mappings": {
    "properties": {
      "title": {"type": "text"},
      "abstract": {"type": "text"},
      "content": {"type": "text"},
      "category": {"type": "keyword"}
    }
  }
}

# Index academic papers dataset
POST /boost_test/_bulk
{"index": {}}
{"title": "Machine Learning Algorithms", "abstract": "Comprehensive overview of ML algorithms", "content": "Detailed explanation of supervised learning...", "category": "AI"}
{"index": {}}
{"title": "Database Systems", "abstract": "Modern database architecture", "content": "Relational and NoSQL databases comparison...", "category": "Database"}
```

**Experiment**:
```bash
# Baseline query (no boosting)
GET /boost_test/_search
{
  "query": {
    "multi_match": {
      "query": "machine learning",
      "fields": ["title", "abstract", "content"]
    }
  }
}

# Query with field boosting
GET /boost_test/_search
{
  "query": {
    "multi_match": {
      "query": "machine learning", 
      "fields": ["title^3", "abstract^2", "content^1"],
      "type": "best_fields"
    }
  }
}
```

**Mathematical Analysis**:
```python
def analyze_boost_impact(baseline_results, boosted_results):
    # Calculate score changes
    baseline_scores = {hit['_id']: hit['_score'] for hit in baseline_results['hits']['hits']}
    boosted_scores = {hit['_id']: hit['_score'] for hit in boosted_results['hits']['hits']}
    
    # Rank correlation (Spearman)
    from scipy.stats import spearmanr
    
    common_ids = set(baseline_scores.keys()) & set(boosted_scores.keys())
    baseline_ranks = [baseline_scores[id] for id in common_ids]
    boosted_ranks = [boosted_scores[id] for id in common_ids]
    
    correlation, p_value = spearmanr(baseline_ranks, boosted_ranks)
    
    # NDCG calculation for ranking quality
    def calculate_ndcg(relevant_docs, search_results, k=10):
        dcg = sum([1/np.log2(i+2) for i, doc_id in enumerate(search_results[:k]) if doc_id in relevant_docs])
        idcg = sum([1/np.log2(i+2) for i in range(min(k, len(relevant_docs)))])
        return dcg / idcg if idcg > 0 else 0
    
    return correlation, p_value
```

## Performance Analysis Experiments

### Experiment 3: Shard Count vs Query Performance

**Objective**: Demonstrate the relationship between shard count and query latency.

**Setup**:
```python
# Performance test framework
import time
import statistics
import concurrent.futures

def create_test_index(index_name, shard_count):
    index_config = {
        "settings": {
            "number_of_shards": shard_count,
            "number_of_replicas": 0,
            "refresh_interval": "1s"
        }
    }
    
    # Create index via Elasticsearch API
    es_client.indices.create(index=index_name, body=index_config)
    
    # Index test documents
    documents = generate_test_documents(10000)  # 10k documents
    bulk_index_documents(index_name, documents)

def measure_query_performance(index_name, query, iterations=100):
    latencies = []
    
    for _ in range(iterations):
        start_time = time.perf_counter()
        result = es_client.search(index=index_name, body=query)
        end_time = time.perf_counter()
        
        latencies.append((end_time - start_time) * 1000)  # ms
    
    return {
        'mean': statistics.mean(latencies),
        'median': statistics.median(latencies),
        'p95': statistics.quantiles(latencies, n=20)[18],  # 95th percentile
        'p99': statistics.quantiles(latencies, n=100)[98]  # 99th percentile
    }
```

**Experiment Execution**:
```python
# Test different shard configurations
shard_configurations = [1, 2, 4, 8, 16]
query = {
    "query": {
        "match": {
            "content": "search elasticsearch performance"
        }
    },
    "size": 10
}

results = {}
for shard_count in shard_configurations:
    index_name = f"perf_test_{shard_count}_shards"
    create_test_index(index_name, shard_count)
    
    # Wait for index to be ready
    time.sleep(5)
    
    # Measure performance
    perf_metrics = measure_query_performance(index_name, query)
    results[shard_count] = perf_metrics
    
    print(f"Shards: {shard_count}, Mean Latency: {perf_metrics['mean']:.2f}ms")
```

**Expected Results**:
- Optimal shard count depends on data size and query patterns
- Too few shards: Limited parallelism
- Too many shards: Overhead dominates

### Experiment 4: Aggregation Performance Scaling

**Objective**: Analyze how aggregation performance scales with data volume.

**Setup**:
```bash
# Create time-series index
PUT /metrics_test
{
  "settings": {
    "number_of_shards": 5,
    "number_of_replicas": 0
  },
  "mappings": {
    "properties": {
      "timestamp": {"type": "date"},
      "metric_name": {"type": "keyword"},
      "value": {"type": "double"},
      "host": {"type": "keyword"},
      "datacenter": {"type": "keyword"}
    }
  }
}
```

**Performance Test**:
```python
def generate_metrics_data(num_points):
    """Generate time-series data for testing"""
    import random
    from datetime import datetime, timedelta
    
    base_time = datetime.now() - timedelta(days=7)
    metrics = ['cpu.usage', 'memory.usage', 'disk.io', 'network.rx']
    hosts = [f'host-{i:03d}' for i in range(50)]
    datacenters = ['us-east', 'us-west', 'eu-west']
    
    documents = []
    for i in range(num_points):
        doc = {
            'timestamp': base_time + timedelta(minutes=i),
            'metric_name': random.choice(metrics),
            'value': random.uniform(0, 100),
            'host': random.choice(hosts),
            'datacenter': random.choice(datacenters)
        }
        documents.append(doc)
    
    return documents

# Test aggregation performance at different scales
data_sizes = [10000, 50000, 100000, 500000, 1000000]

aggregation_query = {
    "size": 0,
    "aggs": {
        "metrics_over_time": {
            "date_histogram": {
                "field": "timestamp",
                "calendar_interval": "1h"
            },
            "aggs": {
                "avg_cpu": {
                    "filter": {"term": {"metric_name": "cpu.usage"}},
                    "aggs": {
                        "avg_value": {"avg": {"field": "value"}}
                    }
                },
                "by_datacenter": {
                    "terms": {"field": "datacenter"},
                    "aggs": {
                        "avg_value": {"avg": {"field": "value"}}
                    }
                }
            }
        }
    }
}

for size in data_sizes:
    # Index data
    data = generate_metrics_data(size)
    bulk_index_documents('metrics_test', data)
    
    # Measure aggregation performance
    start_time = time.perf_counter()
    result = es_client.search(index='metrics_test', body=aggregation_query)
    latency = (time.perf_counter() - start_time) * 1000
    
    print(f"Data Size: {size}, Aggregation Latency: {latency:.2f}ms")
```

## Distributed System Experiments

### Experiment 5: Node Failure Simulation

**Objective**: Observe cluster behavior during node failures and recovery.

**Setup**:
```python
# Cluster health monitoring
def monitor_cluster_health():
    health = es_client.cluster.health()
    return {
        'status': health['status'],
        'active_shards': health['active_shards'],
        'relocating_shards': health['relocating_shards'],
        'unassigned_shards': health['unassigned_shards'],
        'number_of_nodes': health['number_of_nodes']
    }

def simulate_node_failure(node_name):
    """Simulate node failure by stopping Elasticsearch process"""
    import subprocess
    
    # Stop Elasticsearch service on target node
    subprocess.run(['ssh', node_name, 'sudo systemctl stop elasticsearch'])
    
    # Monitor cluster response
    health_timeline = []
    for i in range(60):  # Monitor for 60 seconds
        health = monitor_cluster_health()
        health['timestamp'] = time.time()
        health_timeline.append(health)
        
        print(f"T+{i}s: Status={health['status']}, Nodes={health['number_of_nodes']}")
        time.sleep(1)
    
    return health_timeline
```

**Experiment**:
```python
# Test cluster resilience
initial_health = monitor_cluster_health()
print(f"Initial cluster state: {initial_health}")

# Simulate failure of a data node
failure_timeline = simulate_node_failure('elasticsearch-node-2')

# Analyze recovery characteristics
def analyze_recovery_timeline(timeline):
    # Time to detection
    detection_time = None
    for entry in timeline:
        if entry['status'] != 'green':
            detection_time = entry['timestamp'] - timeline[0]['timestamp']
            break
    
    # Time to recovery
    recovery_time = None
    for entry in reversed(timeline):
        if entry['status'] == 'green':
            recovery_time = entry['timestamp'] - timeline[0]['timestamp']
            break
    
    return {
        'detection_time': detection_time,
        'recovery_time': recovery_time,
        'max_unassigned_shards': max([e['unassigned_shards'] for e in timeline])
    }

recovery_stats = analyze_recovery_timeline(failure_timeline)
print(f"Recovery Analysis: {recovery_stats}")
```

### Experiment 6: Network Partition Testing

**Objective**: Test cluster behavior during network partitions (split-brain scenarios).

**Setup**:
```bash
# Create test cluster with 3 master-eligible nodes
# Node configuration for split-brain prevention
discovery.zen.minimum_master_nodes: 2  # (3/2) + 1
discovery.zen.ping_timeout: 30s
discovery.zen.fd.ping_interval: 1s
discovery.zen.fd.ping_timeout: 30s
```

**Network Partition Simulation**:
```python
import subprocess
import time

def create_network_partition(nodes_group1, nodes_group2):
    """Simulate network partition using iptables"""
    
    # Block traffic between groups
    for node1 in nodes_group1:
        for node2 in nodes_group2:
            # Block node1 -> node2
            subprocess.run([
                'ssh', node1, 
                f'sudo iptables -A OUTPUT -d {node2} -j DROP'
            ])
            
            # Block node2 -> node1  
            subprocess.run([
                'ssh', node2,
                f'sudo iptables -A OUTPUT -d {node1} -j DROP'
            ])

def heal_network_partition(all_nodes):
    """Remove iptables rules to heal partition"""
    for node in all_nodes:
        subprocess.run([
            'ssh', node,
            'sudo iptables -F OUTPUT'  # Flush OUTPUT chain
        ])

# Test split-brain prevention
nodes = ['es-node-1', 'es-node-2', 'es-node-3']

# Create partition: 2 nodes vs 1 node
create_network_partition(['es-node-1', 'es-node-2'], ['es-node-3'])

# Monitor both partitions
for i in range(120):  # 2 minutes
    for node in nodes:
        try:
            # Check if node thinks it's master
            health = es_client.cluster.health(master_timeout='5s')
            master_node = es_client.cat.master(format='json')[0]['node']
            print(f"Node {node}: Master={master_node}, Status={health['status']}")
        except:
            print(f"Node {node}: Not responding")
    
    time.sleep(1)

# Heal partition and observe recovery
heal_network_partition(nodes)
```

## Search Quality Experiments

### Experiment 7: A/B Testing for Search Relevance

**Objective**: Compare different relevance models using statistical significance testing.

**Setup**:
```python
import scipy.stats as stats
import numpy as np

class SearchExperiment:
    def __init__(self, control_config, treatment_config):
        self.control_config = control_config
        self.treatment_config = treatment_config
        self.control_results = []
        self.treatment_results = []
    
    def run_query(self, query, config):
        """Execute query with given configuration"""
        # Modify query based on configuration
        if config.get('boost_title'):
            query['query']['multi_match']['fields'] = ['title^3', 'content^1']
        
        return es_client.search(body=query)
    
    def measure_relevance(self, results, ground_truth):
        """Calculate relevance metrics (NDCG, MRR, etc.)"""
        # Simplified relevance calculation
        relevant_docs = set(ground_truth)
        search_results = [hit['_id'] for hit in results['hits']['hits']]
        
        # Mean Reciprocal Rank
        mrr = 0
        for i, doc_id in enumerate(search_results):
            if doc_id in relevant_docs:
                mrr = 1 / (i + 1)
                break
        
        return mrr
    
    def run_experiment(self, queries_with_ground_truth, sample_size=1000):
        """Run A/B test experiment"""
        
        for query_data in queries_with_ground_truth[:sample_size]:
            query, ground_truth = query_data['query'], query_data['relevant_docs']
            
            # Randomly assign to control or treatment
            if np.random.random() < 0.5:
                results = self.run_query(query, self.control_config)
                relevance = self.measure_relevance(results, ground_truth)
                self.control_results.append(relevance)
            else:
                results = self.run_query(query, self.treatment_config)
                relevance = self.measure_relevance(results, ground_truth)
                self.treatment_results.append(relevance)
    
    def statistical_analysis(self):
        """Perform statistical significance testing"""
        
        # Two-sample t-test
        t_stat, p_value = stats.ttest_ind(self.treatment_results, self.control_results)
        
        # Effect size (Cohen's d)
        pooled_std = np.sqrt(((len(self.treatment_results) - 1) * np.var(self.treatment_results) + 
                             (len(self.control_results) - 1) * np.var(self.control_results)) / 
                            (len(self.treatment_results) + len(self.control_results) - 2))
        
        cohens_d = (np.mean(self.treatment_results) - np.mean(self.control_results)) / pooled_std
        
        return {
            't_statistic': t_stat,
            'p_value': p_value,
            'effect_size': cohens_d,
            'treatment_mean': np.mean(self.treatment_results),
            'control_mean': np.mean(self.control_results),
            'significant': p_value < 0.05
        }

# Run experiment
control_config = {'boost_title': False}
treatment_config = {'boost_title': True}

experiment = SearchExperiment(control_config, treatment_config)
experiment.run_experiment(test_queries)
results = experiment.statistical_analysis()

print(f"Experiment Results: {results}")
```

### Experiment 8: Query Performance Under Load

**Objective**: Measure query performance degradation under increasing load.

**Setup**:
```python
import concurrent.futures
import numpy as np
from collections import defaultdict

def load_test_scenario(query, concurrent_users, duration_seconds):
    """Simulate concurrent user load"""
    
    results = defaultdict(list)
    start_time = time.time()
    
    def single_user_simulation(user_id):
        user_latencies = []
        user_start = time.time()
        
        while (time.time() - user_start) < duration_seconds:
            query_start = time.perf_counter()
            try:
                response = es_client.search(body=query, timeout='10s')
                latency = (time.perf_counter() - query_start) * 1000
                user_latencies.append(latency)
            except Exception as e:
                # Record timeout/error
                user_latencies.append(float('inf'))
            
            # Think time between queries
            time.sleep(np.random.exponential(1.0))  # Average 1 second
        
        return user_id, user_latencies
    
    # Launch concurrent users
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
        future_to_user = {
            executor.submit(single_user_simulation, user_id): user_id 
            for user_id in range(concurrent_users)
        }
        
        for future in concurrent.futures.as_completed(future_to_user):
            user_id, latencies = future.result()
            results[user_id] = latencies
    
    return results

# Progressive load testing
user_loads = [1, 5, 10, 20, 50, 100]
test_query = {
    "query": {"match": {"content": "elasticsearch performance"}},
    "size": 10
}

load_test_results = {}
for load in user_loads:
    print(f"Testing with {load} concurrent users...")
    
    results = load_test_scenario(test_query, load, 60)  # 60-second test
    
    # Aggregate metrics
    all_latencies = [lat for user_lats in results.values() for lat in user_lats if lat != float('inf')]
    error_rate = sum(1 for user_lats in results.values() for lat in user_lats if lat == float('inf')) / sum(len(user_lats) for user_lats in results.values())
    
    load_test_results[load] = {
        'mean_latency': np.mean(all_latencies) if all_latencies else float('inf'),
        'p95_latency': np.percentile(all_latencies, 95) if all_latencies else float('inf'),
        'p99_latency': np.percentile(all_latencies, 99) if all_latencies else float('inf'),
        'error_rate': error_rate,
        'throughput': len(all_latencies) / 60  # queries per second
    }
    
    print(f"Load {load}: Mean={load_test_results[load]['mean_latency']:.1f}ms, "
          f"P95={load_test_results[load]['p95_latency']:.1f}ms, "
          f"Error Rate={load_test_results[load]['error_rate']:.2%}")
```

## Data Analysis and Visualization

### Experiment Results Analysis

```python
import matplotlib.pyplot as plt
import seaborn as sns

def plot_performance_results():
    """Visualize experiment results"""
    
    # Performance vs Load
    plt.figure(figsize=(12, 8))
    
    loads = list(load_test_results.keys())
    mean_latencies = [load_test_results[load]['mean_latency'] for load in loads]
    p95_latencies = [load_test_results[load]['p95_latency'] for load in loads]
    
    plt.subplot(2, 2, 1)
    plt.plot(loads, mean_latencies, marker='o', label='Mean')
    plt.plot(loads, p95_latencies, marker='s', label='P95')
    plt.xlabel('Concurrent Users')
    plt.ylabel('Latency (ms)')
    plt.title('Query Latency vs Load')
    plt.legend()
    
    # Throughput vs Load
    throughput = [load_test_results[load]['throughput'] for load in loads]
    plt.subplot(2, 2, 2)
    plt.plot(loads, throughput, marker='o', color='green')
    plt.xlabel('Concurrent Users')
    plt.ylabel('Queries/Second')
    plt.title('Throughput vs Load')
    
    # Error Rate vs Load
    error_rates = [load_test_results[load]['error_rate'] * 100 for load in loads]
    plt.subplot(2, 2, 3)
    plt.plot(loads, error_rates, marker='o', color='red')
    plt.xlabel('Concurrent Users')
    plt.ylabel('Error Rate (%)')
    plt.title('Error Rate vs Load')
    
    # Latency Distribution
    plt.subplot(2, 2, 4)
    # Show distribution for moderate load
    moderate_load = loads[len(loads)//2]
    sample_latencies = [lat for user_lats in load_test_scenario(test_query, moderate_load, 30).values() 
                       for lat in user_lats if lat != float('inf')]
    plt.hist(sample_latencies, bins=30, alpha=0.7)
    plt.xlabel('Latency (ms)')
    plt.ylabel('Frequency')
    plt.title(f'Latency Distribution ({moderate_load} users)')
    
    plt.tight_layout()
    plt.show()

# Statistical analysis of results
def performance_regression_analysis():
    """Analyze performance regression patterns"""
    
    loads = np.array(list(load_test_results.keys()))
    latencies = np.array([load_test_results[load]['mean_latency'] for load in loads])
    
    # Fit polynomial regression
    coeffs = np.polyfit(loads, latencies, 2)  # Quadratic fit
    poly_func = np.poly1d(coeffs)
    
    # Predict breaking point (where latency > 1000ms)
    breaking_point = None
    for load in range(1, 200):
        if poly_func(load) > 1000:  # 1 second threshold
            breaking_point = load
            break
    
    return {
        'regression_coefficients': coeffs,
        'predicted_breaking_point': breaking_point,
        'r_squared': np.corrcoef(loads, latencies)[0, 1]**2
    }

regression_results = performance_regression_analysis()
print(f"Performance Regression Analysis: {regression_results}")
```

## Experiment Conclusions

### Key Findings

1. **Search Relevance**: BM25 generally outperforms TF-IDF for typical search scenarios
2. **Field Boosting**: Title boosting significantly improves relevance for document collections
3. **Shard Performance**: Optimal shard count balances parallelism with coordination overhead
4. **Load Characteristics**: Query latency increases exponentially under high concurrent load
5. **Failure Recovery**: Cluster recovery time depends on data size and network bandwidth

### Best Practices from Experiments

1. **Relevance Tuning**: Use A/B testing to validate relevance improvements
2. **Performance Testing**: Regular load testing prevents production surprises
3. **Capacity Planning**: Plan for 2x expected peak load with safety margins
4. **Monitoring**: Implement comprehensive metrics for early problem detection
5. **Resilience**: Test failure scenarios regularly in controlled environments

### Statistical Significance

All experiments should meet statistical significance criteria:
- **Sample Size**: Minimum 1000 observations per condition
- **P-value**: < 0.05 for significance
- **Effect Size**: Cohen's d > 0.2 for practical significance
- **Confidence Interval**: 95% confidence level

---

## Running the Experiments

### Prerequisites
```bash
# Required Python packages
pip install elasticsearch pandas numpy scipy matplotlib seaborn

# Required system access
- Elasticsearch cluster with API access
- SSH access to cluster nodes (for failure simulation)
- Network configuration privileges (for partition testing)
```

### Safety Guidelines
1. **Non-Production Testing**: Run experiments on dedicated test clusters
2. **Backup Data**: Ensure all test data is backed up or easily reproducible
3. **Resource Limits**: Set memory and CPU limits to prevent system overload
4. **Monitoring**: Monitor system resources during experiments
5. **Rollback Plan**: Have procedures to quickly restore normal operations

---

> *"Experiments are the compass that guides us from theoretical understanding to practical mastery."* - Scientific Method

**Next**: [References - Academic Papers and Documentation](../06-references/index.md) 📚  
**Previous**: [Failure Models - Error Handling and Resilience](../04-failure-models/index.md) 🛡️