# Algorithms: Core Dremio Implementation Strategies

![Dremio Algorithms](dremio-algorithms.svg)

## Overview

This section explores the core algorithms that power Dremio's data lakehouse platform. These algorithms enable efficient query processing, optimal resource utilization, and seamless data federation across multiple sources.

## Query Optimization Algorithms

### 1. Cost-Based Query Optimizer (CBO)

**Mathematical Foundation and Why This Approach:**

The Cost-Based Query Optimizer (CBO) is fundamental to Dremio's performance because it solves the **query plan selection problem** - choosing the optimal execution plan from an exponentially large search space.

**The Mathematical Challenge:**
Given n relations R₁, R₂, ..., Rₙ with join predicates, the number of possible execution plans grows as:
- Left-deep trees: (n-1)! possible join orders
- Bushy trees: (2n-2)! / 2^(n-1) possible plans
- For n=10 tables: ~3.6 million possible plans

**Why CBO is Essential:**
1. **Optimal Substructure Property**: The optimal plan for joining relations {R₁, R₂, ..., Rₖ} contains optimal subplans for subsets of these relations
2. **Cost Additivity**: Total query cost can be modeled as the sum of individual operation costs: C(plan) = Σᵢ C(opᵢ)
3. **Statistical Foundation**: Cost estimation relies on statistical models that provide expected values with bounded error

**Algorithm Complexity:** O(3ⁿ) using dynamic programming vs O((2n-2)!) for exhaustive search

The heart of Dremio's query processing engine uses sophisticated cost estimation algorithms:

#### Selinger-Style Join Ordering
```python
class QueryOptimizer:
    def __init__(self):
        self.cost_model = CostModel()
        self.statistics = StatisticsCollector()
    
    def optimize_join_order(self, tables, predicates):
        """Dynamic programming approach to optimal join ordering"""
        n = len(tables)
        # dp[mask] = (min_cost, optimal_plan)
        dp = {}
        
        # Initialize single table costs
        for i in range(n):
            mask = 1 << i
            cost = self.cost_model.scan_cost(tables[i])
            dp[mask] = (cost, JoinPlan(tables[i]))
        
        # Build up optimal plans for increasing subset sizes
        for size in range(2, n + 1):
            for mask in range(1 << n):
                if bin(mask).count('1') != size:
                    continue
                
                min_cost = float('inf')
                best_plan = None
                
                # Try all possible left-right splits
                submask = mask
                while submask > 0:
                    if submask != mask and submask in dp:
                        right_mask = mask ^ submask
                        if right_mask in dp:
                            join_cost = self.cost_model.join_cost(
                                dp[submask][1], dp[right_mask][1], predicates
                            )
                            total_cost = dp[submask][0] + dp[right_mask][0] + join_cost
                            
                            if total_cost < min_cost:
                                min_cost = total_cost
                                best_plan = JoinPlan(dp[submask][1], dp[right_mask][1])
                    
                    submask = (submask - 1) & mask
                
                dp[mask] = (min_cost, best_plan)
        
        return dp[(1 << n) - 1][1]
```

#### Cardinality Estimation Algorithm

**Mathematical Foundation and Why This Approach:**

Cardinality estimation is critical for optimal query planning because **join cost is proportional to cardinality**: C_join = O(|R| × |S| × selectivity). Accurate cardinality estimates determine the difference between plans that execute in seconds versus hours.

**The Statistical Challenge:**
Estimate |σ_θ(R)| and |R ⋈_θ S| without executing operations, using limited statistical information.

**Key Mathematical Principles:**
1. **Independence Assumption**: For predicates P₁, P₂: sel(P₁ ∧ P₂) ≈ sel(P₁) × sel(P₂)
2. **Uniform Distribution Assumption**: Values within histogram bins are uniformly distributed
3. **Join Selectivity Formula**: sel(R.A = S.B) ≈ 1/max(distinct(R.A), distinct(S.B))

**Why Histogram-Based Approach:**
- **Space-Time Trade-off**: O(k) space for k bins provides O(1) selectivity estimation
- **Accuracy Bounds**: For well-distributed data, error decreases as O(1/√k)
- **Adaptive Binning**: Equal-frequency binning handles skewed data better than equal-width

**Algorithm Complexity:** O(1) for selectivity queries after O(n log n) histogram construction

```python
class CardinalityEstimator:
    def __init__(self):
        self.histograms = {}
        self.correlation_matrix = {}
    
    def estimate_selection(self, table, predicate):
        """Estimate selectivity for selection predicates"""
        if predicate.column not in self.histograms[table]:
            return 0.1  # Default selectivity
        
        histogram = self.histograms[table][predicate.column]
        return self._histogram_selectivity(histogram, predicate)
    
    def estimate_join(self, left_table, right_table, join_condition):
        """Estimate join cardinality using statistical models"""
        left_cardinality = self.get_table_cardinality(left_table)
        right_cardinality = self.get_table_cardinality(right_table)
        
        if join_condition.type == 'EQUI_JOIN':
            # Use distinct value statistics
            left_distinct = self.get_distinct_count(left_table, join_condition.left_column)
            right_distinct = self.get_distinct_count(right_table, join_condition.right_column)
            
            # Join cardinality estimation
            max_distinct = max(left_distinct, right_distinct)
            join_cardinality = (left_cardinality * right_cardinality) / max_distinct
            
            return min(join_cardinality, left_cardinality * right_cardinality)
        
        return left_cardinality * right_cardinality * 0.1  # Default for complex joins
    
    def _histogram_selectivity(self, histogram, predicate):
        """Calculate selectivity using histogram analysis"""
        if predicate.operator == '=':
            return histogram.point_selectivity(predicate.value)
        elif predicate.operator == '<':
            return histogram.range_selectivity(None, predicate.value)
        elif predicate.operator == '>':
            return histogram.range_selectivity(predicate.value, None)
        elif predicate.operator == 'BETWEEN':
            return histogram.range_selectivity(predicate.min_value, predicate.max_value)
        
        return 0.1  # Default
```

### 2. Predicate Pushdown Algorithm

**Mathematical Foundation and Why This Approach:**

Predicate pushdown is a critical optimization that dramatically reduces data movement and processing costs by applying filters as early as possible in the execution pipeline.

**The Optimization Problem:**
Given a query tree with predicates at various levels, find the optimal placement that minimizes total execution cost:
C_total = C_scan + C_transfer + C_process

**Mathematical Benefits:**
1. **Data Reduction**: If selectivity σ < 1, pushing predicate reduces subsequent operation costs by factor σ
2. **Network Cost Reduction**: C_network = bandwidth × |data_transferred|. Early filtering reduces |data_transferred| by σ
3. **Memory Footprint**: Working set size reduced from |R| to σ × |R|
4. **Join Cost Reduction**: Join cost O(|R| × |S|) becomes O(σ_R × |R| × σ_S × |S|)

**Why Tree-Based Pushdown:**
- **Systematic Coverage**: Tree traversal ensures all optimization opportunities are considered
- **Correctness Preservation**: Maintains query semantics through careful predicate dependency analysis
- **Optimal Placement**: Each predicate is pushed to the lowest valid level in the execution tree

**Algorithm Complexity:** O(n × p) where n = tree nodes, p = predicates per node

**Performance Impact:** Can achieve 10-100x performance improvement for selective queries

Optimizes queries by pushing predicates closer to data sources:

```python
class PredicatePushdown:
    def __init__(self, source_capabilities):
        self.source_capabilities = source_capabilities
    
    def optimize_query(self, query_plan):
        """Push predicates down to optimal execution locations"""
        return self._push_predicates(query_plan, set())
    
    def _push_predicates(self, node, available_columns):
        """Recursively push predicates down the query tree"""
        if node.type == 'SCAN':
            # Base case: apply all applicable predicates to scan
            applicable_predicates = []
            for predicate in node.predicates:
                if self._can_push_to_source(predicate, node.source):
                    applicable_predicates.append(predicate)
            
            node.pushed_predicates = applicable_predicates
            return node
        
        elif node.type == 'JOIN':
            # Process children first
            left_child = self._push_predicates(node.left, available_columns)
            right_child = self._push_predicates(node.right, available_columns)
            
            # Update available columns after join
            new_available = available_columns.union(
                left_child.output_columns,
                right_child.output_columns
            )
            
            # Push join predicates
            pushable_predicates = []
            remaining_predicates = []
            
            for predicate in node.predicates:
                if predicate.columns.issubset(left_child.output_columns):
                    # Push to left child
                    left_child.predicates.append(predicate)
                elif predicate.columns.issubset(right_child.output_columns):
                    # Push to right child
                    right_child.predicates.append(predicate)
                else:
                    # Keep at join level
                    remaining_predicates.append(predicate)
            
            node.predicates = remaining_predicates
            node.left = left_child
            node.right = right_child
            
            return node
        
        elif node.type == 'FILTER':
            # Process child first
            child = self._push_predicates(node.child, available_columns)
            
            # Try to push filter predicates down
            pushable_predicates = []
            remaining_predicates = []
            
            for predicate in node.predicates:
                if predicate.columns.issubset(child.output_columns):
                    child.predicates.append(predicate)
                else:
                    remaining_predicates.append(predicate)
            
            if not remaining_predicates:
                # All predicates pushed down, eliminate filter node
                return child
            
            node.predicates = remaining_predicates
            node.child = child
            return node
        
        return node
    
    def _can_push_to_source(self, predicate, source):
        """Check if predicate can be executed at the source"""
        capabilities = self.source_capabilities.get(source.type, set())
        
        if predicate.operator in capabilities:
            return True
        
        # Check for complex predicates
        if predicate.type == 'COMPLEX' and 'COMPLEX_FILTERS' in capabilities:
            return True
        
        return False
```

## Reflection Management Algorithms

**Mathematical Foundation and Why Reflection Management is Critical:**

Reflections are materialized views that trade storage space for query performance. The fundamental optimization problem is the **materialized view selection problem**: Given limited storage S and a query workload Q, select views V that maximize performance benefit while respecting storage constraints.

**The Multi-Objective Optimization Problem:**
- **Maximize**: Σ_q∈Q freq(q) × speedup(q, V) (total query acceleration)
- **Subject to**: Σ_v∈V size(v) ≤ S (storage constraint)
- **Minimize**: Σ_v∈V maintenance_cost(v) (update overhead)

This is a variant of the **Multi-Dimensional Knapsack Problem**, which is NP-complete, requiring sophisticated heuristics.

### 1. Intelligent Reflection Recommendation

**Mathematical Foundation and Why This Approach:**

The recommendation engine solves a **constrained optimization problem** to select the optimal set of reflections that maximize query performance under resource constraints.

**Key Mathematical Components:**
1. **ROI Calculation**: ROI(reflection) = (Benefit - Cost) / Cost
   - Benefit = Σ_queries freq(q) × acceleration(q, reflection)  
   - Cost = creation_cost + maintenance_cost + storage_cost

2. **Query Pattern Analysis**: Uses **frequency analysis** and **clustering algorithms** to identify common access patterns
   - Time Complexity: O(q log q) for pattern extraction from q queries
   - Space Complexity: O(k) where k is the number of distinct patterns

3. **Greedy Selection with Constraints**: Approximation algorithm that achieves (1-1/e) optimality ratio for submodular benefit functions

**Why This Algorithm Works:**
- **Submodular Property**: Benefit function exhibits diminishing returns - each additional reflection provides less marginal benefit
- **Greedy Optimality**: For submodular functions under cardinality constraints, greedy selection achieves provable approximation bounds
- **Scalability**: O(n² log n) complexity for n reflection candidates vs O(2ⁿ) for exhaustive search

```python
class ReflectionRecommendationEngine:
    def __init__(self):
        self.query_history = QueryHistoryAnalyzer()
        self.cost_benefit_calculator = CostBenefitCalculator()
    
    def recommend_reflections(self, dataset, query_patterns):
        """Generate optimal reflection recommendations"""
        candidates = self._generate_candidates(dataset, query_patterns)
        scored_candidates = []
        
        for candidate in candidates:
            score = self._score_reflection(candidate, query_patterns)
            if score > self.recommendation_threshold:
                scored_candidates.append((candidate, score))
        
        # Sort by score and apply constraints
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return self._apply_resource_constraints(scored_candidates)
    
    def _generate_candidates(self, dataset, query_patterns):
        """Generate reflection candidates based on query patterns"""
        candidates = []
        
        # Analyze common grouping patterns
        common_groups = self._find_common_groupings(query_patterns)
        for group_columns in common_groups:
            # Generate aggregation reflection
            measures = self._find_common_measures(query_patterns, group_columns)
            candidates.append(
                ReflectionCandidate(
                    type='AGGREGATION',
                    dimensions=group_columns,
                    measures=measures,
                    dataset=dataset
                )
            )
        
        # Analyze common filter patterns
        common_filters = self._find_common_filters(query_patterns)
        for filter_columns in common_filters:
            # Generate raw reflection with optimal sort order
            sort_order = self._determine_optimal_sort(query_patterns, filter_columns)
            candidates.append(
                ReflectionCandidate(
                    type='RAW',
                    columns=dataset.columns,
                    sort_order=sort_order,
                    partitions=filter_columns,
                    dataset=dataset
                )
            )
        
        return candidates
    
    def _score_reflection(self, candidate, query_patterns):
        """Score reflection candidate based on expected benefit"""
        total_benefit = 0
        creation_cost = self._estimate_creation_cost(candidate)
        maintenance_cost = self._estimate_maintenance_cost(candidate)
        
        for pattern in query_patterns:
            if self._can_accelerate(candidate, pattern):
                acceleration_benefit = self._calculate_acceleration_benefit(
                    candidate, pattern
                )
                query_frequency = pattern.frequency
                total_benefit += acceleration_benefit * query_frequency
        
        # Calculate ROI
        total_cost = creation_cost + maintenance_cost
        roi = (total_benefit - total_cost) / total_cost if total_cost > 0 else 0
        
        return roi
```

### 2. Reflection Refresh Algorithm

```python
class ReflectionRefreshManager:
    def __init__(self):
        self.dependency_graph = DependencyGraph()
        self.refresh_scheduler = RefreshScheduler()
    
    def schedule_refresh(self, reflection, trigger_type='DATA_CHANGE'):
        """Schedule reflection refresh based on dependencies and policies"""
        refresh_plan = self._create_refresh_plan(reflection, trigger_type)
        
        if refresh_plan.can_execute_immediately():
            self._execute_refresh(refresh_plan)
        else:
            self.refresh_scheduler.schedule(refresh_plan)
    
    def _create_refresh_plan(self, reflection, trigger_type):
        """Create optimal refresh plan considering dependencies"""
        dependencies = self.dependency_graph.get_dependencies(reflection)
        
        # Determine refresh method
        if trigger_type == 'DATA_CHANGE':
            if self._supports_incremental_refresh(reflection):
                method = 'INCREMENTAL'
            else:
                method = 'FULL'
        else:
            method = 'FULL'
        
        # Calculate resource requirements
        resource_requirements = self._estimate_refresh_resources(reflection, method)
        
        # Determine optimal execution time
        optimal_time = self._find_optimal_execution_time(
            reflection, resource_requirements, dependencies
        )
        
        return RefreshPlan(
            reflection=reflection,
            method=method,
            dependencies=dependencies,
            resource_requirements=resource_requirements,
            scheduled_time=optimal_time
        )
    
    def _supports_incremental_refresh(self, reflection):
        """Check if reflection supports incremental refresh"""
        # Check for append-only data sources
        if not reflection.dataset.is_append_only():
            return False
        
        # Check for supported aggregation functions
        for measure in reflection.measures:
            if measure.function not in ['SUM', 'COUNT', 'MIN', 'MAX']:
                return False
        
        # Check for time-based partitioning
        if not reflection.has_time_partition():
            return False
        
        return True
```

## Distributed Execution Algorithms

### 1. Work Distribution Algorithm

```python
class WorkDistributionManager:
    def __init__(self, cluster_topology):
        self.cluster_topology = cluster_topology
        self.load_balancer = LoadBalancer()
        self.resource_monitor = ResourceMonitor()
    
    def distribute_query(self, query_plan, available_executors):
        """Distribute query execution across available executors"""
        # Analyze query characteristics
        parallelism_analysis = self._analyze_parallelism(query_plan)
        resource_requirements = self._estimate_resource_needs(query_plan)
        
        # Create execution fragments
        fragments = self._fragment_query(query_plan, parallelism_analysis)
        
        # Assign fragments to executors
        assignments = self._assign_fragments(
            fragments, available_executors, resource_requirements
        )
        
        return ExecutionPlan(assignments, self._create_coordination_plan(assignments))
    
    def _fragment_query(self, query_plan, parallelism_analysis):
        """Break query into executable fragments"""
        fragments = []
        fragment_id = 0
        
        def fragment_node(node, parent_fragment=None):
            nonlocal fragment_id
            
            if node.type in ['SCAN', 'EXCHANGE']:
                # Create new fragment for scan operations
                fragment = QueryFragment(
                    id=fragment_id,
                    root_operator=node,
                    parallelism=parallelism_analysis.get_parallelism(node),
                    estimated_cost=self._estimate_fragment_cost(node)
                )
                fragments.append(fragment)
                fragment_id += 1
                
                if parent_fragment:
                    parent_fragment.add_dependency(fragment)
                
                return fragment
            
            elif node.type in ['JOIN', 'AGGREGATE', 'SORT']:
                # Create fragment for complex operations
                fragment = QueryFragment(
                    id=fragment_id,
                    root_operator=node,
                    parallelism=parallelism_analysis.get_parallelism(node),
                    estimated_cost=self._estimate_fragment_cost(node)
                )
                
                # Process children
                for child in node.children:
                    child_fragment = fragment_node(child, fragment)
                
                fragments.append(fragment)
                fragment_id += 1
                return fragment
            
            else:
                # Pass through for simple operations
                for child in node.children:
                    return fragment_node(child, parent_fragment)
        
        fragment_node(query_plan)
        return fragments
    
    def _assign_fragments(self, fragments, executors, resource_requirements):
        """Assign query fragments to optimal executors"""
        assignments = {}
        
        # Sort fragments by resource requirements (descending)
        sorted_fragments = sorted(
            fragments, 
            key=lambda f: f.estimated_cost, 
            reverse=True
        )
        
        for fragment in sorted_fragments:
            best_executor = self._find_best_executor(
                fragment, executors, resource_requirements
            )
            
            if best_executor:
                assignments[fragment.id] = ExecutorAssignment(
                    executor=best_executor,
                    fragment=fragment,
                    estimated_start_time=self._estimate_start_time(
                        best_executor, fragment
                    )
                )
                
                # Update executor load
                best_executor.add_load(fragment.estimated_cost)
        
        return assignments
    
    def _find_best_executor(self, fragment, executors, resource_requirements):
        """Find optimal executor for fragment based on multiple criteria"""
        scored_executors = []
        
        for executor in executors:
            if not executor.can_handle(resource_requirements[fragment.id]):
                continue
            
            score = self._calculate_executor_score(executor, fragment)
            scored_executors.append((executor, score))
        
        if not scored_executors:
            return None
        
        # Sort by score and return best executor
        scored_executors.sort(key=lambda x: x[1], reverse=True)
        return scored_executors[0][0]
    
    def _calculate_executor_score(self, executor, fragment):
        """Calculate executor suitability score"""
        # Factors: available resources, data locality, current load
        resource_score = executor.available_resources / executor.total_resources
        locality_score = self._calculate_data_locality_score(executor, fragment)
        load_score = 1.0 - (executor.current_load / executor.capacity)
        
        # Weighted combination
        total_score = (
            0.4 * resource_score +
            0.3 * locality_score +
            0.3 * load_score
        )
        
        return total_score
```

### 2. Fault Tolerance Algorithm

**Mathematical Foundation and Why Fault Tolerance is Critical:**

Distributed query processing faces the fundamental challenge of **maintaining system availability** in the presence of component failures. The mathematical framework is based on **reliability theory** and **failure probability models**.

**Key Mathematical Models:**
1. **System Reliability**: R_system(t) = P(system operational at time t)
2. **MTBF (Mean Time Between Failures)**: E[T_failure] for exponential failure distribution
3. **Recovery Time Optimization**: Minimize E[T_recovery] subject to resource constraints

**The Fault Tolerance Problem:**
Given failure rate λ and n distributed components, the probability of at least one failure in time t is:
P(failure) = 1 - e^(-nλt)

For large distributed systems, this approaches 1, making fault tolerance essential rather than optional.

**Why Checkpoint-Based Recovery:**
- **Mathematical Optimality**: Checkpoint interval T* = √(2C_checkpoint/λ) minimizes total overhead
- **Recovery Cost Reduction**: From O(T_total) without checkpoints to O(T_checkpoint)
- **Availability Improvement**: Reduces MTTR (Mean Time To Repair) by orders of magnitude

**Algorithm Complexity:** O(log n) for failure detection, O(k) for recovery of k affected fragments

```python
class FaultToleranceManager:
    def __init__(self):
        self.failure_detector = FailureDetector()
        self.recovery_planner = RecoveryPlanner()
    
    def handle_executor_failure(self, failed_executor, affected_fragments):
        """Handle executor failure with minimal query disruption"""
        recovery_plan = self._create_recovery_plan(failed_executor, affected_fragments)
        
        if recovery_plan.can_recover():
            self._execute_recovery(recovery_plan)
            return RecoveryResult.SUCCESS
        else:
            return RecoveryResult.QUERY_RESTART_REQUIRED
    
    def _create_recovery_plan(self, failed_executor, affected_fragments):
        """Create recovery plan for failed executor"""
        recovery_actions = []
        
        for fragment in affected_fragments:
            if fragment.has_checkpoint():
                # Resume from checkpoint
                recovery_actions.append(
                    RecoveryAction.RESUME_FROM_CHECKPOINT(fragment)
                )
            elif fragment.is_deterministic():
                # Re-execute fragment
                recovery_actions.append(
                    RecoveryAction.RE_EXECUTE(fragment)
                )
            else:
                # Restart entire query
                return RecoveryPlan.RESTART_QUERY()
        
        return RecoveryPlan(recovery_actions)
    
    def _execute_recovery(self, recovery_plan):
        """Execute recovery actions"""
        for action in recovery_plan.actions:
            if action.type == 'RESUME_FROM_CHECKPOINT':
                self._resume_fragment_from_checkpoint(action.fragment)
            elif action.type == 'RE_EXECUTE':
                self._reschedule_fragment(action.fragment)
```

## Performance Optimization Algorithms

**Mathematical Foundation and Why Performance Optimization is Critical:**

Performance optimization in distributed systems requires solving multiple interconnected **resource allocation problems** under real-time constraints. The mathematical challenge is optimizing system throughput while maintaining stability and fairness.

### 1. Memory Management Algorithm

**Mathematical Foundation and Why Memory Management is Critical:**

Memory management in distributed query processing is a **constrained resource allocation problem** that directly impacts system performance and stability. Poor memory allocation can lead to thrashing, OOM kills, and exponential performance degradation.

**The Optimization Problem:**
Given total memory M and n concurrent operations, find allocation A = [a₁, a₂, ..., aₙ] that:
- **Maximizes**: Σᵢ utility(aᵢ) (total system throughput)
- **Subject to**: Σᵢ aᵢ ≤ M (memory constraint)
- **Constraint**: aᵢ ≥ min_memory(opᵢ) (minimum viable allocation)

**Mathematical Models:**
1. **Memory Pool Partitioning**: Uses **reservoir sampling** theory for fair allocation
2. **LRU Eviction**: Based on **temporal locality principle** - P(access | recent_access) > P(access | no_recent_access)
3. **Working Set Theory**: Memory requirement follows **power-law distribution** - most operations need little memory, few need much

**Why LRU Algorithm:**
- **Optimal for Stack Distance**: Minimizes fault rate for programs with temporal locality
- **Mathematical Proof**: LRU is optimal among all algorithms that don't use future information
- **Complexity**: O(1) access time with proper data structures (doubly-linked list + hash map)

**Performance Impact:** Proper memory management can improve query performance by 2-10x and prevent system instability.

```python
class MemoryManager:
    def __init__(self, total_memory):
        self.total_memory = total_memory
        self.allocations = {}
        self.memory_pools = {
            'QUERY_PROCESSING': MemoryPool(0.6 * total_memory),
            'REFLECTIONS': MemoryPool(0.3 * total_memory),
            'METADATA': MemoryPool(0.1 * total_memory)
        }
    
    def allocate_query_memory(self, query_id, memory_request):
        """Allocate memory for query processing"""
        if self._can_allocate(memory_request, 'QUERY_PROCESSING'):
            allocation = self.memory_pools['QUERY_PROCESSING'].allocate(
                query_id, memory_request
            )
            self.allocations[query_id] = allocation
            return allocation
        else:
            # Try memory eviction
            if self._try_evict_memory(memory_request, 'QUERY_PROCESSING'):
                return self.allocate_query_memory(query_id, memory_request)
            else:
                raise OutOfMemoryError("Cannot allocate requested memory")
    
    def _try_evict_memory(self, required_memory, pool_name):
        """Attempt to evict memory using LRU strategy"""
        pool = self.memory_pools[pool_name]
        evictable_allocations = pool.get_evictable_allocations()
        
        # Sort by last access time (LRU)
        evictable_allocations.sort(key=lambda x: x.last_access_time)
        
        freed_memory = 0
        for allocation in evictable_allocations:
            if freed_memory >= required_memory:
                break
            
            pool.evict(allocation)
            freed_memory += allocation.size
        
        return freed_memory >= required_memory
```

## Next Steps

- **04-failure-models/**: Apply these algorithms in failure scenario analysis
- **05-experiments/**: Validate algorithm performance through practical experiments
- **07-use-cases/**: See these algorithms in action through real-world examples