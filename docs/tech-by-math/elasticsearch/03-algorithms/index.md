# Algorithms: Search and Indexing Implementation

> *"The efficiency of a search system is determined by the algorithms that power its core operations."* - Modern Search Engine Design

## Overview

This section explores the algorithms that make Elasticsearch's distributed search and real-time analytics possible. We cover indexing algorithms, query processing, distributed coordination, and optimization techniques that enable sub-second search across massive datasets.

## Indexing Algorithms

### Inverted Index Construction

**Basic Inverted Index Algorithm**:
```python
def build_inverted_index(documents):
    index = defaultdict(list)
    for doc_id, document in enumerate(documents):
        terms = tokenize_and_normalize(document)
        for position, term in enumerate(terms):
            posting = {
                'doc_id': doc_id,
                'term_frequency': terms.count(term),
                'position': position,
                'field': extract_field(document, term)
            }
            index[term].append(posting)
    
    # Sort posting lists by document ID for efficient intersection
    for term in index:
        index[term].sort(key=lambda x: x['doc_id'])
    
    return index

Time Complexity: O(|D| × |T|) where D = documents, T = average terms per document
Space Complexity: O(|V| × |P|) where V = vocabulary, P = total postings
```

**Segment-based Indexing (Elasticsearch Model)**:
```python
def segment_based_indexing(documents, segment_size=1000):
    segments = []
    current_segment = []
    
    for document in documents:
        current_segment.append(document)
        
        if len(current_segment) >= segment_size:
            # Build immutable segment
            segment = {
                'inverted_index': build_inverted_index(current_segment),
                'doc_values': build_column_store(current_segment),
                'metadata': extract_segment_metadata(current_segment),
                'timestamp': current_time()
            }
            segments.append(segment)
            current_segment = []
    
    return segments

Benefits:
- Immutable segments enable concurrent reads during writes
- Periodic merging reduces search overhead
- Easy to implement real-time search with refresh operations
```

### Text Analysis Pipeline

**Tokenization Algorithm**:
```python
def standard_tokenizer(text):
    # Unicode-aware tokenization
    tokens = []
    current_token = ""
    
    for char in text:
        if is_letter_or_digit(char):
            current_token += char
        else:
            if current_token:
                tokens.append(current_token)
                current_token = ""
    
    if current_token:
        tokens.append(current_token)
    
    return tokens

def keyword_tokenizer(text):
    # Treats entire field as single token
    return [text.strip()] if text.strip() else []
```

**N-gram Generation**:
```python
def generate_ngrams(tokens, min_gram=2, max_gram=3):
    ngrams = []
    for token in tokens:
        # Character n-grams for fuzzy matching
        for n in range(min_gram, min(max_gram + 1, len(token) + 1)):
            for i in range(len(token) - n + 1):
                ngrams.append(token[i:i + n])
    
    return ngrams

# Edge n-grams for autocomplete
def generate_edge_ngrams(token, min_gram=1, max_gram=10):
    return [token[:i] for i in range(min_gram, min(max_gram + 1, len(token) + 1))]
```

**Stemming and Lemmatization**:
```python
def porter_stemmer(word):
    # Simplified Porter stemming algorithm
    word = word.lower()
    
    # Step 1a: Remove plurals
    if word.endswith('sses'):
        word = word[:-2]  # sses -> ss
    elif word.endswith('ies'):
        word = word[:-2]  # ies -> i
    elif word.endswith('ss'):
        pass  # ss -> ss
    elif word.endswith('s') and len(word) > 1:
        word = word[:-1]  # s -> (empty)
    
    # Additional steps for suffix removal...
    return word

Time Complexity: O(|word|) for each word
Accuracy: ~70-80% for English text
```

## Query Processing Algorithms

### Boolean Query Processing

**Two-Pointer Intersection Algorithm**:
```python
def intersect_posting_lists(list1, list2):
    result = []
    i, j = 0, 0
    
    while i < len(list1) and j < len(list2):
        if list1[i].doc_id == list2[j].doc_id:
            # Merge posting information
            merged_posting = merge_postings(list1[i], list2[j])
            result.append(merged_posting)
            i += 1
            j += 1
        elif list1[i].doc_id < list2[j].doc_id:
            i += 1
        else:
            j += 1
    
    return result

Time Complexity: O(|P1| + |P2|) where P1, P2 are posting list sizes
Space Complexity: O(min(|P1|, |P2|)) for result size
```

**Skip List Optimization**:
```python
class SkipListPosting:
    def __init__(self, doc_id, next_ptr=None, skip_ptr=None):
        self.doc_id = doc_id
        self.next_ptr = next_ptr
        self.skip_ptr = skip_ptr  # Points to posting √|P| positions ahead

def skip_list_intersect(list1, list2):
    result = []
    p1, p2 = list1.head, list2.head
    
    while p1 and p2:
        if p1.doc_id == p2.doc_id:
            result.append(p1.doc_id)
            p1, p2 = p1.next_ptr, p2.next_ptr
        elif p1.doc_id < p2.doc_id:
            # Use skip pointer if beneficial
            if p1.skip_ptr and p1.skip_ptr.doc_id <= p2.doc_id:
                p1 = p1.skip_ptr
            else:
                p1 = p1.next_ptr
        else:
            if p2.skip_ptr and p2.skip_ptr.doc_id <= p1.doc_id:
                p2 = p2.skip_ptr
            else:
                p2 = p2.next_ptr
    
    return result

Expected Time Complexity: O(√(|P1| × |P2|)) for uniform distributions
```

### Ranked Retrieval Algorithms

**Top-K Heap Algorithm**:
```python
import heapq

def top_k_search(query_terms, k=10):
    # Min-heap to maintain top-k results
    result_heap = []
    candidate_docs = get_candidate_documents(query_terms)
    
    for doc_id in candidate_docs:
        score = calculate_bm25_score(doc_id, query_terms)
        
        if len(result_heap) < k:
            heapq.heappush(result_heap, (score, doc_id))
        elif score > result_heap[0][0]:  # Better than worst in heap
            heapq.heapreplace(result_heap, (score, doc_id))
    
    # Return results in descending score order
    return sorted(result_heap, reverse=True)

Time Complexity: O(|C| log k) where C = candidate documents
Space Complexity: O(k) for heap storage
```

**Block-Max WAND Algorithm**:
```python
def block_max_wand(query_terms, k=10):
    # Pre-compute maximum possible scores for blocks
    iterators = [get_posting_iterator(term) for term in query_terms]
    block_max_scores = compute_block_max_scores(iterators)
    
    threshold = 0.0
    results = []
    
    while any(it.has_next() for it in iterators):
        # Find pivot point where sum of max scores >= threshold
        pivot = find_pivot(iterators, block_max_scores, threshold)
        
        if pivot is None:
            break
            
        # Evaluate documents at pivot
        doc_id = min(it.current_doc() for it in iterators if it.current_doc() >= pivot)
        
        # Skip blocks that can't contribute to top-k
        upper_bound = sum(block_max_scores[term][doc_id] for term in query_terms)
        
        if upper_bound >= threshold:
            score = calculate_exact_score(doc_id, query_terms)
            if score >= threshold:
                results.append((score, doc_id))
                if len(results) > k:
                    results.sort(reverse=True)
                    results = results[:k]
                    threshold = results[-1][0]
        
        # Advance iterators
        advance_iterators(iterators, doc_id + 1)
    
    return sorted(results, reverse=True)

Time Complexity: O(k) in best case with effective pruning
Speedup: 5-10x over naive top-k for large collections
```

## Distributed Algorithms

### Consistent Hashing for Shard Allocation

**Basic Consistent Hashing**:
```python
import hashlib
from bisect import bisect_left

class ConsistentHash:
    def __init__(self, nodes=None, virtual_nodes=100):
        self.virtual_nodes = virtual_nodes
        self.ring = {}
        self.sorted_keys = []
        
        if nodes:
            for node in nodes:
                self.add_node(node)
    
    def add_node(self, node):
        for i in range(self.virtual_nodes):
            key = self.hash(f"{node}:{i}")
            self.ring[key] = node
            self.sorted_keys.append(key)
        self.sorted_keys.sort()
    
    def remove_node(self, node):
        for i in range(self.virtual_nodes):
            key = self.hash(f"{node}:{i}")
            del self.ring[key]
            self.sorted_keys.remove(key)
    
    def get_node(self, key):
        if not self.ring:
            return None
        
        hash_key = self.hash(key)
        idx = bisect_left(self.sorted_keys, hash_key)
        
        # Wrap around if necessary
        if idx == len(self.sorted_keys):
            idx = 0
            
        return self.ring[self.sorted_keys[idx]]
    
    def hash(self, key):
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

Load Balance Variance: O(log N / N) with virtual nodes
Minimal Data Movement: Only 1/N keys reassigned when node added/removed
```

### Distributed Query Coordination

**Scatter-Gather Pattern**:
```python
async def execute_distributed_query(query, indices):
    # Phase 1: Scatter query to all relevant shards
    shard_requests = []
    for index in indices:
        for shard in index.shards:
            shard_query = adapt_query_for_shard(query, shard)
            shard_requests.append(execute_shard_query(shard, shard_query))
    
    # Execute all shard queries concurrently
    shard_results = await asyncio.gather(*shard_requests)
    
    # Phase 2: Gather and merge results
    merged_results = merge_shard_results(shard_results, query.size)
    
    # Phase 3: Fetch full documents for top results (if needed)
    if query.fetch_source:
        doc_requests = [fetch_document(hit.doc_id, hit.shard) for hit in merged_results]
        documents = await asyncio.gather(*doc_requests)
        merged_results = attach_documents(merged_results, documents)
    
    return merged_results

def merge_shard_results(shard_results, target_size):
    # Merge sorted result lists using min-heap
    import heapq
    
    heap = []
    result_iterators = [iter(results) for results in shard_results]
    
    # Initialize heap with first result from each shard
    for i, iterator in enumerate(result_iterators):
        try:
            first_result = next(iterator)
            heapq.heappush(heap, (-first_result.score, i, first_result, iterator))
        except StopIteration:
            continue
    
    merged = []
    while heap and len(merged) < target_size:
        neg_score, shard_idx, result, iterator = heapq.heappop(heap)
        merged.append(result)
        
        # Add next result from same shard
        try:
            next_result = next(iterator)
            heapq.heappush(heap, (-next_result.score, shard_idx, next_result, iterator))
        except StopIteration:
            continue
    
    return merged

Time Complexity: O(S × log S × K) where S = shards, K = target size
Network Calls: 1 round trip for query + 1 for document fetch
```

### Cluster State Management

**Raft Consensus Algorithm (Simplified)**:
```python
class RaftNode:
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers
        self.state = 'follower'  # follower, candidate, leader
        self.current_term = 0
        self.voted_for = None
        self.log = []
        self.commit_index = 0
        self.last_applied = 0
    
    def start_election(self):
        self.state = 'candidate'
        self.current_term += 1
        self.voted_for = self.node_id
        
        # Request votes from peers
        votes = 1  # Vote for self
        for peer in self.peers:
            if self.request_vote(peer):
                votes += 1
        
        # Become leader if majority votes received
        if votes > len(self.peers) // 2:
            self.become_leader()
        else:
            self.state = 'follower'
    
    def request_vote(self, peer):
        # Send RequestVote RPC
        last_log_index = len(self.log) - 1
        last_log_term = self.log[-1].term if self.log else 0
        
        return peer.handle_vote_request(
            term=self.current_term,
            candidate_id=self.node_id,
            last_log_index=last_log_index,
            last_log_term=last_log_term
        )
    
    def become_leader(self):
        self.state = 'leader'
        # Send heartbeats to maintain leadership
        for peer in self.peers:
            self.send_heartbeat(peer)

Properties:
- Safety: At most one leader per term
- Liveness: Eventually elects leader if majority available
- Consistency: All committed entries appear in same order
```

## Aggregation Algorithms

### Histogram Construction

**Dynamic Histogram Algorithm**:
```python
def build_dynamic_histogram(values, max_buckets=100):
    if not values:
        return []
    
    # Start with single bucket
    buckets = [{'min': min(values), 'max': max(values), 'count': len(values)}]
    
    for value in sorted(values):
        # Find appropriate bucket
        target_bucket = find_bucket(buckets, value)
        
        if target_bucket:
            update_bucket(target_bucket, value)
        else:
            # Create new bucket
            new_bucket = {'min': value, 'max': value, 'count': 1}
            buckets.append(new_bucket)
        
        # Merge buckets if too many
        if len(buckets) > max_buckets:
            merge_closest_buckets(buckets)
    
    return buckets

def merge_closest_buckets(buckets):
    # Find pair of buckets with minimum merge cost
    min_cost = float('inf')
    merge_idx = 0
    
    for i in range(len(buckets) - 1):
        cost = calculate_merge_cost(buckets[i], buckets[i + 1])
        if cost < min_cost:
            min_cost = cost
            merge_idx = i
    
    # Merge the selected buckets
    left, right = buckets[merge_idx], buckets[merge_idx + 1]
    merged = {
        'min': min(left['min'], right['min']),
        'max': max(left['max'], right['max']),
        'count': left['count'] + right['count']
    }
    
    buckets[merge_idx:merge_idx + 2] = [merged]

Time Complexity: O(n log b) where n = values, b = max buckets
Space Complexity: O(b) for bucket storage
Error Bound: Configurable based on merge strategy
```

### Percentile Approximation

**T-Digest Algorithm Implementation**:
```python
class TDigest:
    def __init__(self, delta=100):
        self.delta = delta  # Compression parameter
        self.centroids = []  # List of (mean, weight) tuples
        self.count = 0
    
    def add(self, value, weight=1):
        self.count += weight
        
        # Find insertion point to maintain sorted order
        insertion_point = self.find_insertion_point(value)
        
        # Try to merge with nearby centroids
        merged = False
        for i in range(max(0, insertion_point - 1), min(len(self.centroids), insertion_point + 2)):
            if self.can_merge(i, value, weight):
                self.merge_centroid(i, value, weight)
                merged = True
                break
        
        if not merged:
            # Insert new centroid
            new_centroid = (value, weight)
            self.centroids.insert(insertion_point, new_centroid)
        
        # Periodically compress to maintain size bounds
        if len(self.centroids) > self.delta * 2:
            self.compress()
    
    def can_merge(self, centroid_idx, value, weight):
        if centroid_idx >= len(self.centroids):
            return False
            
        centroid_mean, centroid_weight = self.centroids[centroid_idx]
        
        # Calculate quantile position
        q = self.quantile_of_centroid(centroid_idx)
        
        # Maximum weight allowed by compression function
        max_weight = 4 * self.count * self.delta_function(q) * (1 - q) / (self.delta ** 2)
        
        return centroid_weight + weight <= max_weight
    
    def delta_function(self, q):
        # Compression function - higher compression at extremes
        return self.delta * q * (1 - q)
    
    def quantile(self, q):
        if not self.centroids or q < 0 or q > 1:
            return None
        
        target_rank = q * self.count
        current_rank = 0
        
        for i, (mean, weight) in enumerate(self.centroids):
            if current_rank + weight >= target_rank:
                # Interpolate within centroid
                if i == 0 or i == len(self.centroids) - 1:
                    return mean  # Use exact value at extremes
                else:
                    # Linear interpolation
                    fraction = (target_rank - current_rank) / weight
                    if i > 0:
                        prev_mean = self.centroids[i - 1][0]
                        return prev_mean + fraction * (mean - prev_mean)
                    else:
                        return mean
            current_rank += weight
        
        return self.centroids[-1][0]  # Should not reach here

Space Complexity: O(δ) centroids
Accuracy: Error typically < 0.1% for middle quantiles
```

## Performance Optimization Algorithms

### Query Cache Implementation

**LRU Cache with Frequency Tracking**:
```python
class QueryCache:
    def __init__(self, max_size=1000, frequency_window=1000):
        self.max_size = max_size
        self.frequency_window = frequency_window
        
        self.cache = {}  # query_hash -> (result, frequency, last_access)
        self.access_order = []  # LRU order
        self.frequency_counter = defaultdict(int)
    
    def get(self, query_hash):
        if query_hash in self.cache:
            result, freq, _ = self.cache[query_hash]
            
            # Update access statistics
            self.cache[query_hash] = (result, freq + 1, time.time())
            self.move_to_end(query_hash)
            
            return result
        return None
    
    def put(self, query_hash, result):
        current_time = time.time()
        
        if len(self.cache) >= self.max_size:
            self.evict_least_valuable()
        
        self.cache[query_hash] = (result, 1, current_time)
        self.access_order.append(query_hash)
    
    def evict_least_valuable(self):
        # Use combination of LRU and frequency
        candidates = []
        current_time = time.time()
        
        for query_hash in self.access_order[:self.max_size // 4]:  # Consider oldest 25%
            result, freq, last_access = self.cache[query_hash]
            age = current_time - last_access
            value_score = freq / (1 + age / 3600)  # Decay over time
            candidates.append((value_score, query_hash))
        
        # Evict lowest value entry
        candidates.sort()
        evict_hash = candidates[0][1]
        
        del self.cache[evict_hash]
        self.access_order.remove(evict_hash)

Hit Rate: Typically 60-80% for search workloads
Eviction Strategy: Balances recency and frequency
```

### Index Segment Merging

**Log-Structured Merge Tree (LSM) Style**:
```python
def merge_segments(segments, target_size=1000000):
    # Sort segments by size for optimal merging
    segments.sort(key=lambda s: s.size)
    
    merge_queue = []
    for segment in segments:
        merge_queue.append(segment)
        
        # Check if merge is needed
        while should_merge(merge_queue):
            merge_candidates = select_merge_candidates(merge_queue)
            merged_segment = perform_merge(merge_candidates)
            
            # Remove merged segments and add result
            for candidate in merge_candidates:
                merge_queue.remove(candidate)
            merge_queue.append(merged_segment)
    
    return merge_queue

def should_merge(segments):
    # Merge if too many small segments
    small_segments = [s for s in segments if s.size < target_size // 10]
    return len(small_segments) > 4

def perform_merge(segments):
    # Merge inverted indexes
    merged_index = defaultdict(list)
    doc_id_mapping = {}
    new_doc_id = 0
    
    for segment in segments:
        # Remap document IDs to avoid conflicts
        segment_doc_mapping = {}
        for old_doc_id in segment.document_ids:
            segment_doc_mapping[old_doc_id] = new_doc_id
            doc_id_mapping[new_doc_id] = segment.get_document(old_doc_id)
            new_doc_id += 1
        
        # Merge posting lists
        for term, postings in segment.inverted_index.items():
            for posting in postings:
                new_posting = posting.copy()
                new_posting['doc_id'] = segment_doc_mapping[posting['doc_id']]
                merged_index[term].append(new_posting)
    
    # Sort merged posting lists
    for term in merged_index:
        merged_index[term].sort(key=lambda p: p['doc_id'])
    
    return Segment(merged_index, doc_id_mapping)

Benefits:
- Reduces search overhead (fewer segments to query)
- Improves compression ratios
- Removes deleted documents
- Balances write and read performance
```

---

## Algorithm Complexity Summary

### Search Operations
| Operation | Time Complexity | Space Complexity | Notes |
|-----------|----------------|------------------|-------|
| Term Lookup | O(log V) | O(1) | Binary search in term dictionary |
| Boolean AND | O(min(P₁, P₂)) | O(result) | Two-pointer intersection |
| Boolean OR | O(P₁ + P₂) | O(P₁ + P₂) | Merge operation |
| Top-K Retrieval | O(C log K) | O(K) | Heap-based selection |
| Phrase Query | O(P₁ × P₂) | O(positions) | Position intersection |
| Wildcard Query | O(V) | O(matches) | Term enumeration |

### Indexing Operations
| Operation | Time Complexity | Space Complexity | Notes |
|-----------|----------------|------------------|-------|
| Document Indexing | O(T log V) | O(T) | T = terms per document |
| Segment Creation | O(D × T log T) | O(D × T) | D = documents per segment |
| Segment Merging | O(S₁ + S₂) | O(S₁ + S₂) | Linear merge of sorted lists |
| Index Refresh | O(1) | O(1) | Makes segments searchable |

### Distributed Operations
| Operation | Time Complexity | Space Complexity | Notes |
|-----------|----------------|------------------|-------|
| Shard Routing | O(1) | O(1) | Hash-based routing |
| Query Broadcasting | O(S) | O(S) | S = number of shards |
| Result Merging | O(S log K) | O(S × K) | Merge from S shards |
| Cluster State Update | O(N) | O(state) | N = number of nodes |

---

## Next Steps

**Implementation Details**: Continue to [Failure Models](../04-failure-models/index.md) for error handling and resilience patterns.

**Hands-on Examples**: Jump to [Experiments](../05-experiments/index.md) for practical algorithm implementations.

**Performance Tuning**: Explore optimization techniques in production environments.

---

> *"Good algorithms are the foundation of fast search. Great algorithms make fast search scalable."* - Search Engine Architecture

**Next**: [Failure Models - Error Handling and Resilience](../04-failure-models/index.md) 🛡️  
**Previous**: [Math Toolkit - Statistical Foundations](../02-math-toolkit/index.md) 📊