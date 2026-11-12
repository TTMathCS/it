# Math Toolkit: Information Retrieval and Distributed Systems

> *"Information retrieval is fundamentally about probability, statistics, and the mathematics of relevance."* - Christopher Manning, Introduction to Information Retrieval

## Overview

This section provides the mathematical foundation underlying Elasticsearch's search and analytics capabilities. We explore the statistical models, algorithmic approaches, and distributed systems theory that enable scalable, relevant search across massive datasets.

## Information Retrieval Mathematics

### Statistical Foundations

**Term Frequency-Inverse Document Frequency (TF-IDF)**:
```
tf-idf(t,d) = tf(t,d) × idf(t)

where:
tf(t,d) = count(t,d) / |d|
idf(t) = log(|D| / |{d ∈ D : t ∈ d}|)
```

**Okapi BM25 Ranking Function**:
```
BM25(q,d) = ∑ᵢ idf(qᵢ) × [f(qᵢ,d) × (k₁ + 1)] / [f(qᵢ,d) + k₁ × (1 - b + b × |d|/avgdl)]

Parameters:
- k₁ ∈ [1.2, 2.0]: term frequency saturation parameter
- b ∈ [0, 1]: field length normalization parameter  
- avgdl: average document length in collection
```

**Vector Space Model**:
```
Documents: d = (w₁, w₂, ..., wₙ)
Queries: q = (q₁, q₂, ..., qₙ)

Cosine Similarity: sim(d,q) = cos(θ) = (d·q) / (||d|| × ||q||)
```

### Probabilistic Models

**Language Model Scoring**:
```
P(q|d) = ∏ᵢ P(tᵢ|d)^count(tᵢ,q)

Jelinek-Mercer Smoothing:
P(t|d) = λ × P_ml(t|d) + (1-λ) × P_ml(t|C)

Dirichlet Smoothing:
P(t|d) = [count(t,d) + μ × P(t|C)] / [|d| + μ]
```

**Divergence from Randomness (DFR)**:
```
weight(t,d) = tf_norm(t,d) × (-log₂[P_random(tf_norm(t,d))])

where P_random follows geometric, Poisson, or binomial distribution
```

## Text Analysis and Processing

### N-gram Analysis
```
Unigrams: ["elastic", "search", "distributed"]
Bigrams: ["elastic search", "search distributed"]  
Trigrams: ["elastic search distributed"]

N-gram Probability:
P(wᵢ|w₁...wᵢ₋₁) ≈ P(wᵢ|wᵢ₋ₙ₊₁...wᵢ₋₁)
```

### Edit Distance and Fuzzy Matching
```
Levenshtein Distance:
lev(a,b) = |a| if |b| = 0
         = |b| if |a| = 0  
         = lev(tail(a), tail(b)) if a[0] = b[0]
         = 1 + min(lev(tail(a), b), lev(a, tail(b)), lev(tail(a), tail(b))) otherwise

Damerau-Levenshtein: Includes transposition operations
```

### Phonetic Matching
```
Soundex Algorithm: Maps words to 4-character codes
Metaphone: Improved phonetic algorithm handling English pronunciation
Double Metaphone: Handles multiple pronunciations per word
```

## Distributed Systems Mathematics

### Consistent Hashing
```
Hash Ring: hash_function: key → [0, 2³²)
Node Placement: hash(node_id) → position on ring
Key Routing: key routes to first node clockwise from hash(key)

Load Balance: With virtual nodes, standard deviation ≈ √(ln N / N)
```

### Replication and Consistency

**Quorum Systems**:
```
N = total replicas
R = read quorum size  
W = write quorum size

Strong Consistency: R + W > N
Eventual Consistency: R + W ≤ N

Probability of Consistency: P = 1 - (1 - p)^R where p = probability of up-to-date replica
```

**Vector Clocks**:
```
Vector Clock: VC = [T₁, T₂, ..., Tₙ] where Tᵢ = logical timestamp for node i

Partial Ordering:
VC₁ < VC₂ iff ∀i: VC₁[i] ≤ VC₂[i] ∧ ∃j: VC₁[j] < VC₂[j]
VC₁ || VC₂ iff VC₁ ≮ VC₂ ∧ VC₂ ≮ VC₁ (concurrent)
```

### Load Balancing Algorithms

**Weighted Round Robin**:
```
Weight Assignment: wᵢ = capacity_i / ∑capacity_j
Current Weight: cwᵢ = cwᵢ + wᵢ
Selection: node = argmax(cwᵢ)
Update: cw_selected -= 1
```

**Least Connections**:
```
Selection: node = argmin(active_connections_i / weight_i)
```

## Time Series Analysis

### Moving Averages
```
Simple Moving Average: SMA_n = (x₁ + x₂ + ... + xₙ) / n

Exponential Moving Average: 
EMA_today = (Value_today × α) + (EMA_yesterday × (1-α))
where α = smoothing factor
```

### Anomaly Detection
```
Z-Score Method: 
z = (x - μ) / σ
Anomaly if |z| > threshold (typically 2 or 3)

Seasonal Decomposition:
Y(t) = Trend(t) + Seasonal(t) + Irregular(t)

Isolation Forest:
Anomaly Score = 2^(-E(h(x))/c(n))
where E(h(x)) = average path length, c(n) = average path length of BST
```

### Percentile Approximation

**T-Digest Algorithm**:
```
Compression: δ = scale_factor × log(total_count)
Centroid Weight: wᵢ ≤ 4 × total_count × δ(q) × (1-q) / δ²
Quantile: q ≈ (sum of weights below + weight/2) / total_weight
```

## Aggregation Mathematics

### Statistical Functions
```
Count: |S|
Sum: ∑ᵢ xᵢ  
Mean: μ = (∑ᵢ xᵢ) / n
Variance: σ² = ∑ᵢ(xᵢ - μ)² / (n-1)
Standard Deviation: σ = √σ²

Skewness: γ₁ = E[(X-μ)³] / σ³
Kurtosis: γ₂ = E[(X-μ)⁴] / σ⁴ - 3
```

### Histogram Construction
```
Fixed-Width Bins: 
bin_width = (max - min) / num_bins
bin_index = floor((value - min) / bin_width)

Adaptive Binning:
Scott's Rule: bin_width = 3.5σ / ∛n
Freedman-Diaconis: bin_width = 2 × IQR / ∛n
```

### Cardinality Estimation

**HyperLogLog Algorithm**:
```
Hash Function: h: domain → [0, 2^L)  
Leading Zeros: ρ(h(x)) = position of first 1-bit
Register Update: M[j] = max(M[j], ρ(h(x)))

Cardinality Estimate:
E = α_m × m² / ∑ᵢ 2^(-M[i])

where α_m = constant based on m (number of buckets)
```

**MinHash for Set Similarity**:
```
Jaccard Similarity: J(A,B) = |A ∩ B| / |A ∪ B|
MinHash Estimate: E[min_hash(A) = min_hash(B)] = J(A,B)

LSH Probability: P(collision) = s^r where s = similarity, r = hash functions
```

## Performance Analysis Mathematics

### Query Complexity

**Term Lookup Complexity**:
```
Binary Search: O(log |V|) where V = vocabulary
Hash Lookup: O(1) average case, O(|V|) worst case
Trie Lookup: O(|term|) where |term| = term length
```

**Boolean Query Processing**:
```
AND Operation: O(min(|P₁|, |P₂|)) using two-pointer technique
OR Operation: O(|P₁| + |P₂|) using merge algorithm  
NOT Operation: O(|D|) requires full document iteration
```

**Top-K Retrieval**:
```
Heap-based: O(n log k) where n = documents, k = results
Threshold Algorithm: O(k log k) with sorted access
Block-Max WAND: O(k) with pre-computed upper bounds
```

### Storage Analysis

**Index Size Estimation**:
```
Vocabulary Size: |V| ≈ K × |D|^β where β ≈ 0.5 (Heap's Law)
Index Size: |I| ≈ |V| × avgdf + |D| × avgdl
Compression Ratio: typically 10-30% of original text size

Zipf Distribution: frequency(rank) = α / rank^s
where s ≈ 1 for natural language
```

**Memory Requirements**:
```
Field Data: O(|D| × field_cardinality × sizeof(value))
Doc Values: O(|D| × |fields|) with compression
Query Cache: O(filter_count × filter_complexity)
```

### Scalability Models

**Amdahl's Law for Parallel Search**:
```
Speedup = 1 / (s + p/N)
where s = sequential fraction, p = parallel fraction, N = processors
```

**Universal Scalability Law**:
```
C(N) = N / (1 + α(N-1) + βN(N-1))
where α = contention coefficient, β = coherence coefficient
```

## Machine Learning Integration

### Learning to Rank

**RankNet Loss Function**:
```
P_ij = σ(s_i - s_j) = 1 / (1 + e^(-(s_i - s_j)))
Loss = -∑_ij [S_ij × log P_ij + (1-S_ij) × log(1-P_ij)]
```

**LambdaMART Gradient**:
```
λ_ij = ∂C/∂s_i = σ(1 - P_ij) × |Δ_NDCG_ij|
where Δ_NDCG_ij = change in NDCG from swapping documents i and j
```

### Feature Engineering
```
Query-Document Features:
- BM25 score components
- Field-specific TF-IDF scores  
- Edit distance metrics
- Geographic proximity
- Temporal recency

Query-Independent Features:
- PageRank-style authority scores
- Click-through rates
- Conversion rates
- Social signals
```

## Advanced Topics

### Semantic Search Mathematics

**Word Embeddings (Word2Vec)**:
```
Skip-gram Model: P(c|w) = exp(v'_c · v_w) / ∑_c' exp(v'_c' · v_w)
CBOW Model: P(w|C) = exp(v_w · ∑_c v_c) / ∑_w' exp(v_w' · ∑_c v_c)

Cosine Similarity: cos(w₁,w₂) = w₁·w₂ / (||w₁|| × ||w₂||)
```

**Latent Semantic Analysis (LSA)**:
```
SVD Decomposition: M = UΣV^T
Dimensionality Reduction: M_k = U_k Σ_k V_k^T
Document Similarity: sim(d_i, d_j) = cos(U_k[i], U_k[j])
```

### Graph-based Ranking

**PageRank Algorithm**:
```
PR(A) = (1-d)/N + d × ∑_i PR(T_i)/C(T_i)

where:
- d = damping factor (typically 0.85)
- N = number of pages
- T_i = pages linking to A  
- C(T_i) = outbound links from T_i

Matrix Form: PR = (1-d)/N × e + d × M × PR
```

**HITS Algorithm (Hyperlink-Induced Topic Search)**:
```
Authority Update: a(p) = ∑_q h(q) where q → p
Hub Update: h(p) = ∑_q a(q) where p → q

Converges to principal eigenvectors of A^T A and AA^T
```

---

## Practical Applications

### Index Optimization
```python
# Field-specific boosting
query = {
  "multi_match": {
    "query": "search term",
    "fields": ["title^2.0", "content^1.0", "tags^1.5"],
    "type": "best_fields"
  }
}

# Mathematical interpretation:
# score = max(2.0 × BM25(title), 1.0 × BM25(content), 1.5 × BM25(tags))
```

### Performance Tuning
```python
# Shard sizing calculation
optimal_shard_size = cluster_memory × 0.5 / expected_indices
optimal_shard_count = total_data_size / optimal_shard_size

# Replica calculation for availability
required_replicas = ceil(log(target_availability) / log(node_reliability))
```

---

## Further Reading

**Academic Papers**:
- Salton & Buckley (1988): "Term-weighting approaches in automatic text retrieval"
- Robertson & Walker (1994): "Some simple effective approximations to the 2-Poisson model"
- Zhai & Lafferty (2001): "A study of smoothing methods for language models"

**Books**:
- Manning, Raghavan & Schütze: "Introduction to Information Retrieval"
- Croft, Metzler & Strohman: "Search Engines: Information Retrieval in Practice"
- Lynch: "Distributed Algorithms"

---

> *"The best search algorithms combine statistical rigor with computational efficiency."* - Information Retrieval Principle

**Next**: [Algorithms - Search and Indexing Implementation](../03-algorithms/index.md) ⚡  
**Previous**: [Core Model - Distributed Search System](../01-core-model/index.md) 🏠