# Key Algorithms

## Core Algorithms That Make Git Work

This section explores the fundamental algorithms that Git uses to maintain repository integrity, perform efficient operations, and handle distributed coordination. Each algorithm is presented with pseudocode, complexity analysis, and mathematical properties.

## Graph Traversal Algorithms

### Topological Walk
**Purpose**: Visit commits in topological order for operations like `git log`
**Complexity**: O(V + E) where V = commits, E = parent relationships

```pseudocode
topological_walk(starting_commits):
    visited = set()
    result = []
    
    function dfs(commit):
        if commit in visited: return
        visited.add(commit)
        
        for parent in commit.parents:
            dfs(parent)
        
        result.append(commit)
    
    for commit in starting_commits:
        dfs(commit)
    
    return reverse(result)
```

### Reachability Query
**Purpose**: Determine if commit A is an ancestor of commit B
**Complexity**: O(V + E) worst case, often much faster with generation numbers

## Merge Algorithms

### Lowest Common Ancestor (LCA)
**Purpose**: Find merge base for three-way merge
**Complexity**: O(V + E) using DFS

```pseudocode
find_lca(commit_a, commit_b):
    ancestors_a = get_all_ancestors(commit_a)
    
    queue = [commit_b]
    visited = set()
    
    while queue:
        current = queue.pop(0)
        if current in ancestors_a:
            return current
        
        if current not in visited:
            visited.add(current)
            queue.extend(current.parents)
    
    return null  # No common ancestor
```

### Three-Way Merge
**Purpose**: Combine changes from two branches using common ancestor
**Complexity**: O(n) where n = total lines in files

## Diff Algorithms

### Myers' Diff Algorithm
**Purpose**: Compute minimal edit script between two sequences
**Complexity**: O(ND) where N = sequence length, D = edit distance

**Core Insight**: Find shortest edit script using dynamic programming on edit graph

### Longest Common Subsequence (LCS)
**Purpose**: Foundation for diff computation
**Complexity**: O(mn) where m, n = sequence lengths

## Storage Algorithms

### Delta Compression
**Purpose**: Store objects efficiently using deltas
**Strategy**: Store base object + sequence of operations

```pseudocode
create_delta(base_object, target_object):
    instructions = []
    base_pos = 0
    target_pos = 0
    
    while target_pos < len(target_object):
        # Find longest match in base
        match = find_longest_match(base_object, target_object[target_pos:])
        
        if match.length > MINIMUM_MATCH:
            instructions.append(COPY(match.base_offset, match.length))
            target_pos += match.length
        else:
            instructions.append(INSERT(target_object[target_pos]))
            target_pos += 1
    
    return encode(instructions)
```

### Packfile Generation
**Purpose**: Compress repository objects for storage/network transfer
**Strategy**: Find similar objects and delta-compress them

## Hash and Integrity Algorithms

### Object Hash Computation
**Purpose**: Generate content-addressable identifiers

```pseudocode
compute_object_hash(object_type, content):
    header = object_type + " " + len(content) + "\0"
    return SHA1(header + content)
```

### Merkle Tree Verification
**Purpose**: Verify integrity of entire repository structure
**Complexity**: O(n) where n = number of objects

## Files in This Section

- `graph-traversal.md` - Topological walk, reachability, BFS/DFS variants
- `merge-algorithms.md` - LCA, three-way merge, conflict resolution
- `diff-algorithms.md` - Myers algorithm, LCS, patience diff
- `compression.md` - Delta compression, packfile generation
- `integrity.md` - Hash computation, Merkle verification
- `complexity-analysis.md` - Performance characteristics and optimizations