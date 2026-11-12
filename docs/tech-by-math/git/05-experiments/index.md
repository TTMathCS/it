# Experiments and Demonstrations

## Small Scripts Demonstrating Git's Mathematical Concepts

This section contains simple, educational scripts (20-30 lines each) that demonstrate the mathematical principles behind Git. These are not production tools but learning aids to make abstract concepts concrete.

## Hash and Content Addressing

### `hash_demo.py`
**Concept**: How Git uses SHA-1 hashing for content-addressable storage
**Demonstration**: Show how identical content always produces the same hash

```python
# Preview of concept:
# - Hash different content types (blob, tree, commit)
# - Show how changing one bit changes entire hash
# - Demonstrate collision resistance properties
```

### `merkle_integrity.py`
**Concept**: Merkle tree properties for integrity verification
**Demonstration**: How changing any object affects all parent hashes

## Graph Theory Demonstrations

### `dag_walker.py`
**Concept**: Topological traversal of commit DAG
**Demonstration**: Different ways to walk commit history

```python
# Preview of concept:
# - Build a simple commit DAG
# - Show breadth-first vs depth-first traversal
# - Demonstrate topological ordering
```

### `lca_finder.py`
**Concept**: Lowest Common Ancestor algorithm
**Demonstration**: Find merge base between two commits

### `reachability.py`
**Concept**: Ancestor relationship queries
**Demonstration**: Determine if one commit is reachable from another

## Diff and Merge Algorithms

### `myers_diff.py`
**Concept**: Myers' diff algorithm implementation
**Demonstration**: Compute minimal edit script between two sequences

```python
# Preview of concept:
# - Simple implementation of Myers algorithm
# - Show edit graph construction
# - Demonstrate optimal path finding
```

### `three_way_merge.py`
**Concept**: Three-way merge with conflict detection
**Demonstration**: Merge two sequences using common ancestor

### `lcs_demo.py`
**Concept**: Longest Common Subsequence computation
**Demonstration**: Foundation algorithm for diff operations

## Compression and Storage

### `delta_compression.py`
**Concept**: Delta encoding for efficient storage
**Demonstration**: Store differences instead of full content

```python
# Preview of concept:
# - Create delta between two similar objects
# - Show compression ratio improvements
# - Demonstrate delta chain reconstruction
```

### `packfile_simulation.py`
**Concept**: How Git packs objects for efficiency
**Demonstration**: Group similar objects and apply delta compression

## Distributed Scenarios

### `merge_conflict_demo.py`
**Concept**: Mathematical model of merge conflicts
**Demonstration**: When and why conflicts occur

### `branch_divergence.py`
**Concept**: How branches can diverge and converge
**Demonstration**: Model concurrent development scenarios

## Integrity and Verification

### `repository_verify.py`
**Concept**: Complete repository integrity checking
**Demonstration**: Verify all objects and references

### `corruption_detection.py`
**Concept**: How Git detects data corruption
**Demonstration**: Simulate corruption and show detection

## Interactive Demonstrations

### `commit_graph_visualizer.py`
**Concept**: Visual representation of commit DAG
**Demonstration**: ASCII art visualization of branch structure

### `hash_collision_probability.py`
**Concept**: Birthday paradox applied to Git hashes
**Demonstration**: Calculate collision probability for repository sizes

## Running the Experiments

Each script is self-contained and includes:
- Clear documentation of the mathematical concept
- Simple implementation demonstrating the principle
- Expected output and explanation
- Variations to try

### Prerequisites
- Python 3.7+ (most scripts)
- Basic understanding of the mathematical concepts
- No external dependencies beyond standard library

### Usage Pattern
```bash
python hash_demo.py          # Run basic demonstration
python hash_demo.py --help   # Show options and explanations
python hash_demo.py --verbose # Show detailed mathematical steps
```

## Files in This Section

- `hash_demo.py` - Content addressing and cryptographic hashing
- `merkle_integrity.py` - Merkle tree integrity properties
- `dag_walker.py` - Graph traversal algorithms
- `lca_finder.py` - Lowest common ancestor computation
- `reachability.py` - Ancestry queries and reachability
- `myers_diff.py` - Myers' diff algorithm implementation
- `three_way_merge.py` - Three-way merge with conflict detection
- `lcs_demo.py` - Longest common subsequence algorithm
- `delta_compression.py` - Delta encoding demonstration
- `packfile_simulation.py` - Object packing strategies
- `merge_conflict_demo.py` - Conflict detection and modeling
- `branch_divergence.py` - Concurrent development scenarios
- `repository_verify.py` - Integrity verification algorithms
- `corruption_detection.py` - Data corruption detection
- `commit_graph_visualizer.py` - DAG visualization
- `hash_collision_probability.py` - Collision probability analysis