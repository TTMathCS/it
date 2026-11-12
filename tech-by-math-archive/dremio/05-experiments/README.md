# Experiments: Hands-on Validation of Dremio Mathematical Models

![Dremio Experiments](dremio-experiments.svg)

## Overview

This section provides practical experiments to validate and demonstrate Dremio's mathematical models in action. These experiments help bridge the gap between theory and practice, allowing you to observe how mathematical concepts translate into real-world performance improvements.

## Query Optimization Experiments

### Experiment 1: Cost-Based Optimization Validation

**Objective**: Validate that cost-based optimization produces better query plans than rule-based approaches.

#### Setup
```sql
-- Create sample tables with known statistics
CREATE TABLE customers (
    customer_id INTEGER,
    customer_name VARCHAR(100),
    region VARCHAR(50),
    signup_date DATE
) PARTITION BY (region);

CREATE TABLE orders (
    order_id INTEGER,
    customer_id INTEGER,
    order_date DATE,
    amount DECIMAL(10,2),
    product_category VARCHAR(50)
) PARTITION BY (DATE_TRUNC('month', order_date));

CREATE TABLE products (
    product_id INTEGER,
    product_name VARCHAR(200),
    category VARCHAR(50),
    price DECIMAL(10,2)
);

-- Insert test data with controlled distributions
INSERT INTO customers VALUES 
    -- 10,000 customers, 70% in 'US', 20% in 'EU', 10% in 'ASIA'
INSERT INTO orders VALUES 
    -- 1,000,000 orders, following Zipf distribution for customers
INSERT INTO products VALUES 
    -- 50,000 products across 20 categories
```

#### Experimental Procedure
```sql
-- Test Query: Join three tables with different selectivity
EXPLAIN PLAN FOR
SELECT 
    c.customer_name,
    c.region,
    o.order_date,
    o.amount,
    p.product_name,
    p.category
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN products p ON o.product_category = p.category
WHERE c.region = 'US'
  AND o.order_date >= '2023-01-01'
  AND p.price < 100;

-- Measure execution metrics
SELECT 
    execution_time_ms,
    rows_processed,
    memory_usage_mb,
    cpu_time_ms
FROM query_profile 
WHERE query_id = LAST_QUERY_ID();
```

#### Expected Results Analysis
```python
# Mathematical model validation
class CostModelValidator:
    def __init__(self):
        self.actual_costs = []
        self.predicted_costs = []
    
    def validate_join_order(self, query_results):
        """Compare actual vs predicted join costs"""
        # Customer table: 10K rows, 70% selectivity for 'US' = 7K rows
        customers_filtered = 10000 * 0.7
        
        # Orders table: 1M rows, ~25% for date range = 250K rows  
        orders_filtered = 1000000 * 0.25
        
        # Products table: 50K rows, ~30% under $100 = 15K rows
        products_filtered = 50000 * 0.30
        
        # Predicted join cardinalities
        join1_cardinality = min(customers_filtered * orders_filtered / 10000, 
                               customers_filtered * orders_filtered)
        
        final_cardinality = min(join1_cardinality * products_filtered / 50000,
                               join1_cardinality)
        
        print(f"Predicted final cardinality: {final_cardinality:,.0f}")
        print(f"Actual final cardinality: {query_results['rows_returned']}")
        
        accuracy = 1 - abs(final_cardinality - query_results['rows_returned']) / final_cardinality
        return accuracy

# Usage
validator = CostModelValidator()
accuracy = validator.validate_join_order(query_results)
print(f"Cardinality estimation accuracy: {accuracy:.2%}")
```

### Experiment 2: Predicate Pushdown Impact Analysis

**Objective**: Measure performance improvements from predicate pushdown optimization.

#### Controlled Test Setup
```sql
-- Test without predicate pushdown (force materialization)
SELECT /*+ NO_PUSHDOWN */ 
    COUNT(*), 
    AVG(amount)
FROM (
    SELECT o.*, c.region, p.category 
    FROM orders o 
    JOIN customers c ON o.customer_id = c.customer_id
    JOIN products p ON o.product_category = p.category
) base_data
WHERE region = 'US' 
  AND category = 'Electronics'
  AND order_date >= '2023-06-01';

-- Test with predicate pushdown (default behavior)
SELECT 
    COUNT(*), 
    AVG(amount)
FROM orders o 
JOIN customers c ON o.customer_id = c.customer_id
JOIN products p ON o.product_category = p.category
WHERE c.region = 'US' 
  AND p.category = 'Electronics'
  AND o.order_date >= '2023-06-01';
```

#### Performance Metrics Collection
```python
class PredicatePushdownAnalyzer:
    def __init__(self):
        self.test_results = {}
    
    def analyze_pushdown_benefit(self, without_pushdown, with_pushdown):
        """Calculate performance improvement from predicate pushdown"""
        
        # Data volume reduction
        rows_processed_reduction = (
            without_pushdown['rows_processed'] - with_pushdown['rows_processed']
        ) / without_pushdown['rows_processed']
        
        # Execution time improvement  
        time_improvement = (
            without_pushdown['execution_time_ms'] - with_pushdown['execution_time_ms']
        ) / without_pushdown['execution_time_ms']
        
        # Memory usage reduction
        memory_reduction = (
            without_pushdown['memory_usage_mb'] - with_pushdown['memory_usage_mb'] 
        ) / without_pushdown['memory_usage_mb']
        
        return {
            'rows_processed_reduction': rows_processed_reduction,
            'execution_time_improvement': time_improvement,
            'memory_usage_reduction': memory_reduction,
            'theoretical_improvement': self._calculate_theoretical_improvement()
        }
    
    def _calculate_theoretical_improvement(self):
        """Calculate theoretical improvement based on selectivity"""
        # Selectivity factors
        region_selectivity = 0.7    # 70% US customers
        category_selectivity = 0.15 # 15% Electronics products  
        date_selectivity = 0.5      # 50% recent orders
        
        # Combined selectivity (assuming independence)
        combined_selectivity = region_selectivity * category_selectivity * date_selectivity
        
        # Theoretical data reduction
        data_reduction = 1 - combined_selectivity
        
        # Performance improvement (non-linear relationship)
        performance_improvement = data_reduction * 0.8  # 80% of data reduction translates to performance
        
        return {
            'expected_data_reduction': data_reduction,
            'expected_performance_improvement': performance_improvement
        }

# Usage
analyzer = PredicatePushdownAnalyzer()
results = analyzer.analyze_pushdown_benefit(no_pushdown_metrics, with_pushdown_metrics)
print(f"Actual time improvement: {results['execution_time_improvement']:.1%}")
print(f"Expected improvement: {results['theoretical_improvement']['expected_performance_improvement']:.1%}")
```

## Reflection Performance Experiments

### Experiment 3: Reflection Acceleration Measurement

**Objective**: Quantify query acceleration achieved through reflections.

#### Baseline Performance Measurement
```sql
-- Create baseline query without reflections
SELECT 
    region,
    DATE_TRUNC('month', order_date) as order_month,
    COUNT(*) as order_count,
    SUM(amount) as total_revenue,
    AVG(amount) as avg_order_value
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE order_date >= '2023-01-01'
GROUP BY region, DATE_TRUNC('month', order_date)
ORDER BY region, order_month;
```

#### Create Optimized Reflection
```sql
-- Create aggregation reflection
ALTER TABLE orders 
CREATE REFLECTION sales_summary_reflection 
USING DIMENSIONS (
    customers.region,
    DATE_TRUNC('month', order_date)
)
MEASURES (
    COUNT(*) as order_count,
    SUM(amount) as total_revenue,
    AVG(amount) as avg_order_value
);

-- Wait for reflection to build and refresh statistics
REFRESH REFLECTION sales_summary_reflection;
```

#### Performance Comparison Analysis
```python
class ReflectionBenefitAnalyzer:
    def __init__(self):
        self.baseline_metrics = {}
        self.reflection_metrics = {}
    
    def analyze_acceleration(self, baseline, with_reflection):
        """Analyze performance acceleration from reflections"""
        
        # Calculate acceleration factors
        time_acceleration = baseline['execution_time_ms'] / with_reflection['execution_time_ms']
        
        # Data scan reduction (reflection pre-aggregated data)
        scan_reduction = (
            baseline['rows_scanned'] - with_reflection['rows_scanned']
        ) / baseline['rows_scanned']
        
        # CPU efficiency improvement
        cpu_efficiency = baseline['cpu_time_ms'] / with_reflection['cpu_time_ms']
        
        # Memory efficiency
        memory_efficiency = baseline['peak_memory_mb'] / with_reflection['peak_memory_mb']
        
        return {
            'time_acceleration_factor': time_acceleration,
            'data_scan_reduction': scan_reduction,
            'cpu_efficiency_factor': cpu_efficiency,
            'memory_efficiency_factor': memory_efficiency,
            'theoretical_analysis': self._theoretical_reflection_benefit(baseline, with_reflection)
        }
    
    def _theoretical_reflection_benefit(self, baseline, reflection):
        """Calculate theoretical benefit based on data reduction"""
        
        # Original data size
        original_rows = 1000000  # 1M orders
        
        # Reflection size (aggregated by region and month)
        regions = 3  # US, EU, ASIA
        months = 12  # Monthly aggregation
        reflection_rows = regions * months  # 36 rows
        
        # Theoretical scan reduction
        theoretical_scan_reduction = 1 - (reflection_rows / original_rows)
        
        # Expected time improvement (logarithmic relationship for aggregation)
        import math
        expected_time_improvement = 1 - math.log(reflection_rows) / math.log(original_rows)
        
        return {
            'theoretical_scan_reduction': theoretical_scan_reduction,
            'expected_time_improvement': expected_time_improvement,
            'compression_ratio': original_rows / reflection_rows
        }

# Usage example
analyzer = ReflectionBenefitAnalyzer() 
benefits = analyzer.analyze_acceleration(baseline_results, reflection_results)
print(f"Time acceleration: {benefits['time_acceleration_factor']:.1f}x")
print(f"Expected improvement: {benefits['theoretical_analysis']['expected_time_improvement']:.1%}")
```

## Distributed Processing Experiments

### Experiment 4: Parallel Processing Scalability

**Objective**: Measure how query performance scales with executor count.

#### Scalability Test Framework
```python
class ParallelProcessingExperiment:
    def __init__(self):
        self.executor_counts = [2, 4, 6, 8, 12, 16]
        self.test_queries = [
            {
                'name': 'large_scan',
                'query': 'SELECT COUNT(*) FROM large_table WHERE condition = ?',
                'expected_scalability': 'linear'
            },
            {
                'name': 'complex_join', 
                'query': 'SELECT * FROM table_a JOIN table_b ON key WHERE filter = ?',
                'expected_scalability': 'sublinear'
            },
            {
                'name': 'aggregation',
                'query': 'SELECT region, COUNT(*), SUM(amount) FROM orders GROUP BY region',
                'expected_scalability': 'logarithmic'
            }
        ]
    
    def run_scalability_test(self, query_config):
        """Run scalability test across different executor counts"""
        results = {}
        
        for executor_count in self.executor_counts:
            # Configure cluster
            configure_cluster(coordinator_count=3, executor_count=executor_count)
            
            # Run query multiple times for statistical significance
            execution_times = []
            for run in range(5):
                start_time = time.time()
                execute_query(query_config['query'])
                end_time = time.time()
                execution_times.append((end_time - start_time) * 1000)  # Convert to ms
            
            # Calculate statistics
            avg_time = sum(execution_times) / len(execution_times)
            std_time = (sum((t - avg_time)**2 for t in execution_times) / len(execution_times))**0.5
            
            results[executor_count] = {
                'avg_execution_time_ms': avg_time,
                'std_deviation_ms': std_time,
                'min_time_ms': min(execution_times),
                'max_time_ms': max(execution_times)
            }
        
        return self._analyze_scalability(results, query_config['expected_scalability'])
    
    def _analyze_scalability(self, results, expected_pattern):
        """Analyze scalability pattern and compare to theoretical expectations"""
        executor_counts = sorted(results.keys())
        execution_times = [results[count]['avg_execution_time_ms'] for count in executor_counts]
        
        # Calculate speedup factors
        baseline_time = execution_times[0]  # Time with minimum executors
        speedup_factors = [baseline_time / time for time in execution_times]
        
        # Calculate efficiency (speedup / executor_count)
        efficiency_factors = [
            speedup_factors[i] / executor_counts[i] 
            for i in range(len(executor_counts))
        ]
        
        # Theoretical analysis
        theoretical_speedup = []
        for count in executor_counts:
            if expected_pattern == 'linear':
                theoretical_speedup.append(count)
            elif expected_pattern == 'sublinear':
                theoretical_speedup.append(count ** 0.8)  # Power law with exponent < 1
            elif expected_pattern == 'logarithmic':
                import math
                theoretical_speedup.append(math.log2(count) + 1)
        
        # Normalize theoretical speedup
        theoretical_speedup = [s / theoretical_speedup[0] for s in theoretical_speedup]
        
        return {
            'actual_speedup': speedup_factors,
            'theoretical_speedup': theoretical_speedup,
            'efficiency': efficiency_factors,
            'scalability_analysis': self._classify_scalability(speedup_factors, executor_counts)
        }
    
    def _classify_scalability(self, speedup_factors, executor_counts):
        """Classify actual scalability pattern"""
        # Calculate correlation with different patterns
        import numpy as np
        
        linear_pattern = executor_counts
        log_pattern = [math.log2(count) + 1 for count in executor_counts]
        sqrt_pattern = [math.sqrt(count) for count in executor_counts]
        
        # Normalize patterns
        linear_pattern = [p / linear_pattern[0] for p in linear_pattern]
        log_pattern = [p / log_pattern[0] for p in log_pattern]  
        sqrt_pattern = [p / sqrt_pattern[0] for p in sqrt_pattern]
        
        # Calculate correlations
        linear_corr = np.corrcoef(speedup_factors, linear_pattern)[0, 1]
        log_corr = np.corrcoef(speedup_factors, log_pattern)[0, 1]
        sqrt_corr = np.corrcoef(speedup_factors, sqrt_pattern)[0, 1]
        
        best_pattern = max([
            ('linear', linear_corr),
            ('logarithmic', log_corr), 
            ('square_root', sqrt_corr)
        ], key=lambda x: x[1])
        
        return {
            'best_fit_pattern': best_pattern[0],
            'correlation_coefficient': best_pattern[1],
            'all_correlations': {
                'linear': linear_corr,
                'logarithmic': log_corr,
                'square_root': sqrt_corr
            }
        }

# Run experiments
experiment = ParallelProcessingExperiment()
for query in experiment.test_queries:
    results = experiment.run_scalability_test(query)
    print(f"\n{query['name']} Scalability Results:")
    print(f"Best fit pattern: {results['scalability_analysis']['best_fit_pattern']}")
    print(f"Correlation: {results['scalability_analysis']['correlation_coefficient']:.3f}")
    print(f"Max speedup: {max(results['actual_speedup']):.1f}x")
    print(f"Efficiency at max scale: {results['efficiency'][-1]:.1%}")
```

## Memory Management Experiments

### Experiment 5: Memory Pressure Impact Analysis

**Objective**: Understand how memory constraints affect query performance.

#### Memory Constraint Testing
```python
class MemoryPressureExperiment:
    def __init__(self):
        self.memory_limits = [4, 8, 16, 32, 64]  # GB
        self.test_workloads = [
            {
                'name': 'memory_intensive_join',
                'memory_factor': 2.5,  # Requires 2.5x data size in memory
                'data_size_gb': 10
            },
            {
                'name': 'large_aggregation',
                'memory_factor': 1.8,
                'data_size_gb': 20
            },
            {
                'name': 'sort_heavy_query',
                'memory_factor': 3.0,
                'data_size_gb': 8
            }
        ]
    
    def run_memory_pressure_test(self, workload):
        """Test query performance under different memory constraints"""
        results = {}
        
        for memory_limit in self.memory_limits:
            # Set memory limit for query execution
            set_query_memory_limit(memory_limit)
            
            # Calculate if workload fits in memory
            required_memory = workload['data_size_gb'] * workload['memory_factor']
            memory_pressure_ratio = required_memory / memory_limit
            
            try:
                # Execute query and measure performance
                start_time = time.time()
                query_result = execute_memory_intensive_query(workload)
                end_time = time.time()
                
                execution_time = (end_time - start_time) * 1000  # ms
                
                # Gather memory statistics
                memory_stats = get_query_memory_stats()
                
                results[memory_limit] = {
                    'execution_time_ms': execution_time,
                    'memory_pressure_ratio': memory_pressure_ratio,
                    'peak_memory_usage_gb': memory_stats['peak_usage_gb'],
                    'spill_to_disk_gb': memory_stats.get('spill_size_gb', 0),
                    'success': True,
                    'performance_degradation': None
                }
                
            except MemoryException as e:
                results[memory_limit] = {
                    'execution_time_ms': None,
                    'memory_pressure_ratio': memory_pressure_ratio,
                    'success': False,
                    'error': str(e)
                }
        
        return self._analyze_memory_impact(results, workload)
    
    def _analyze_memory_impact(self, results, workload):
        """Analyze the impact of memory constraints on performance"""
        
        # Find baseline performance (highest memory limit with no spill)
        baseline = None
        for memory_limit in sorted(results.keys(), reverse=True):
            result = results[memory_limit]
            if result['success'] and result.get('spill_to_disk_gb', 0) == 0:
                baseline = result
                break
        
        if not baseline:
            return {'error': 'No baseline performance found'}
        
        analysis = {
            'baseline_time_ms': baseline['execution_time_ms'],
            'memory_impact_analysis': {},
            'spill_threshold': None,
            'failure_threshold': None
        }
        
        # Analyze performance degradation at each memory level
        for memory_limit, result in results.items():
            if result['success']:
                if baseline['execution_time_ms'] > 0:
                    slowdown_factor = result['execution_time_ms'] / baseline['execution_time_ms']
                else:
                    slowdown_factor = 1.0
                
                analysis['memory_impact_analysis'][memory_limit] = {
                    'slowdown_factor': slowdown_factor,
                    'spill_amount_gb': result.get('spill_to_disk_gb', 0),
                    'memory_pressure': result['memory_pressure_ratio'],
                    'performance_category': self._categorize_performance(slowdown_factor)
                }
                
                # Identify spill threshold
                if result.get('spill_to_disk_gb', 0) > 0 and analysis['spill_threshold'] is None:
                    analysis['spill_threshold'] = memory_limit
                    
            else:
                # Query failed due to memory constraints
                if analysis['failure_threshold'] is None:
                    analysis['failure_threshold'] = memory_limit
        
        # Mathematical model for memory-performance relationship
        analysis['mathematical_model'] = self._fit_memory_performance_model(results)
        
        return analysis
    
    def _categorize_performance(self, slowdown_factor):
        """Categorize performance degradation"""
        if slowdown_factor <= 1.1:
            return 'EXCELLENT'
        elif slowdown_factor <= 1.5:
            return 'GOOD' 
        elif slowdown_factor <= 2.0:
            return 'ACCEPTABLE'
        elif slowdown_factor <= 5.0:
            return 'POOR'
        else:
            return 'CRITICAL'
    
    def _fit_memory_performance_model(self, results):
        """Fit mathematical model to memory-performance relationship"""
        
        # Extract data points where query succeeded
        memory_ratios = []
        slowdown_factors = []
        
        baseline_time = None
        for memory_limit in sorted(results.keys(), reverse=True):
            if results[memory_limit]['success']:
                if baseline_time is None:
                    baseline_time = results[memory_limit]['execution_time_ms']
                
                memory_ratios.append(results[memory_limit]['memory_pressure_ratio'])
                slowdown_factors.append(
                    results[memory_limit]['execution_time_ms'] / baseline_time
                )
        
        if len(memory_ratios) < 3:
            return {'error': 'Insufficient data for model fitting'}
        
        # Fit exponential model: performance_degradation = e^(a * memory_pressure_ratio)
        import numpy as np
        from scipy.optimize import curve_fit
        
        def exponential_model(x, a, b):
            return b * np.exp(a * x)
        
        try:
            params, _ = curve_fit(exponential_model, memory_ratios, slowdown_factors)
            a, b = params
            
            # Calculate R-squared
            predicted = exponential_model(np.array(memory_ratios), a, b)
            ss_res = np.sum((np.array(slowdown_factors) - predicted) ** 2)
            ss_tot = np.sum((np.array(slowdown_factors) - np.mean(slowdown_factors)) ** 2)
            r_squared = 1 - (ss_res / ss_tot)
            
            return {
                'model_type': 'exponential',
                'parameters': {'a': a, 'b': b},
                'r_squared': r_squared,
                'equation': f'slowdown = {b:.3f} * exp({a:.3f} * memory_pressure_ratio)'
            }
            
        except Exception as e:
            return {'error': f'Model fitting failed: {str(e)}'}

# Run memory pressure experiments
memory_experiment = MemoryPressureExperiment()

for workload in memory_experiment.test_workloads:
    print(f"\n=== {workload['name']} Memory Pressure Analysis ===")
    results = memory_experiment.run_memory_pressure_test(workload)
    
    if 'error' not in results:
        print(f"Baseline performance: {results['baseline_time_ms']:.0f}ms")
        print(f"Spill threshold: {results.get('spill_threshold', 'N/A')} GB")
        print(f"Failure threshold: {results.get('failure_threshold', 'N/A')} GB")
        
        if 'error' not in results['mathematical_model']:
            model = results['mathematical_model']
            print(f"Performance model: {model['equation']}")
            print(f"Model fit (R²): {model['r_squared']:.3f}")
```

## Performance Benchmarking Framework

### Experiment 6: Comprehensive Performance Baseline

```python
class DremioPerformanceBenchmark:
    def __init__(self):
        self.tpc_queries = self._load_tpc_queries()
        self.custom_workloads = self._define_custom_workloads()
        
    def run_comprehensive_benchmark(self):
        """Run comprehensive performance benchmark"""
        
        benchmark_results = {
            'system_info': self._collect_system_info(),
            'tpc_results': {},
            'custom_workload_results': {},
            'scalability_results': {},
            'summary_metrics': {}
        }
        
        # Run TPC-like queries
        for query_name, query_sql in self.tpc_queries.items():
            benchmark_results['tpc_results'][query_name] = self._run_query_benchmark(
                query_name, query_sql
            )
        
        # Run custom workloads
        for workload_name, workload_config in self.custom_workloads.items():
            benchmark_results['custom_workload_results'][workload_name] = \
                self._run_workload_benchmark(workload_name, workload_config)
        
        # Generate summary
        benchmark_results['summary_metrics'] = self._generate_summary_metrics(
            benchmark_results
        )
        
        return benchmark_results
    
    def _run_query_benchmark(self, query_name, query_sql):
        """Run individual query benchmark with statistical analysis"""
        
        execution_times = []
        resource_usage = []
        
        # Run multiple iterations for statistical significance
        for iteration in range(10):
            start_time = time.time()
            
            # Execute query
            result = execute_query(query_sql)
            
            end_time = time.time()
            execution_time = (end_time - start_time) * 1000  # ms
            
            # Collect resource usage
            resources = get_resource_usage()
            
            execution_times.append(execution_time)
            resource_usage.append(resources)
        
        # Statistical analysis
        import numpy as np
        
        return {
            'query_name': query_name,
            'iterations': len(execution_times),
            'execution_stats': {
                'mean_ms': np.mean(execution_times),
                'median_ms': np.median(execution_times),
                'std_ms': np.std(execution_times),
                'min_ms': np.min(execution_times),
                'max_ms': np.max(execution_times),
                'p95_ms': np.percentile(execution_times, 95),
                'p99_ms': np.percentile(execution_times, 99)
            },
            'resource_stats': {
                'avg_cpu_usage': np.mean([r['cpu_percent'] for r in resource_usage]),
                'avg_memory_gb': np.mean([r['memory_gb'] for r in resource_usage]),
                'avg_io_mb_per_sec': np.mean([r['io_mb_per_sec'] for r in resource_usage])
            },
            'throughput_queries_per_hour': 3600000 / np.mean(execution_times)  # Convert ms to hour
        }
    
    def _generate_summary_metrics(self, benchmark_results):
        """Generate summary performance metrics"""
        
        all_execution_times = []
        all_throughputs = []
        
        # Collect all execution times
        for query_result in benchmark_results['tpc_results'].values():
            all_execution_times.extend([
                query_result['execution_stats']['mean_ms']
            ])
            all_throughputs.append(query_result['throughput_queries_per_hour'])
        
        for workload_result in benchmark_results['custom_workload_results'].values():
            all_execution_times.append(workload_result['avg_execution_time_ms'])
        
        import numpy as np
        
        return {
            'overall_performance': {
                'avg_query_time_ms': np.mean(all_execution_times),
                'median_query_time_ms': np.median(all_execution_times),
                'total_throughput_qph': sum(all_throughputs),
                'performance_variability': np.std(all_execution_times) / np.mean(all_execution_times)
            },
            'system_efficiency': {
                'queries_per_gb_memory': self._calculate_memory_efficiency(benchmark_results),
                'queries_per_cpu_core': self._calculate_cpu_efficiency(benchmark_results),
                'cost_per_query': self._estimate_cost_per_query(benchmark_results)
            },
            'scalability_metrics': self._analyze_scalability_characteristics(benchmark_results)
        }

# Execute comprehensive benchmark
benchmark = DremioPerformanceBenchmark()
results = benchmark.run_comprehensive_benchmark()

print("=== Dremio Performance Benchmark Results ===")
print(f"Average query time: {results['summary_metrics']['overall_performance']['avg_query_time_ms']:.1f}ms")
print(f"Total throughput: {results['summary_metrics']['overall_performance']['total_throughput_qph']:.0f} queries/hour")
print(f"Performance variability: {results['summary_metrics']['overall_performance']['performance_variability']:.2f}")
```

## Next Steps

- **07-use-cases/**: Apply experimental insights to real-world implementation scenarios
- **04-failure-models/**: Use performance data to validate failure prediction models  
- **03-algorithms/**: Optimize algorithms based on experimental findings