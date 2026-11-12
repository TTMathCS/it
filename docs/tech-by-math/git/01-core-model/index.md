# Core Model: Git as a Merkle DAG

> *"Git is fundamentally a content-addressable filesystem with a VCS user interface written on top of it."* - Scott Chacon

## Overview

Git revolutionizes version control by treating it as a **mathematical structure** rather than a file management system. This section explores the elegant mathematical model that makes Git's unique capabilities possible.

## The Fundamental Mathematical Model

Git models version control as a **Directed Acyclic Graph (DAG)** with **cryptographic integrity** through content-addressable storage. Every Git repository is essentially a Merkle tree where each node is identified by the cryptographic hash of its contents.

### Visual Representation
```
                    Repository State
                         |
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    v                    v                    v
[Objects DB]        [References]        [Working Tree]
    │                    │                    │
    ├─ Commits          ├─ Branches          └─ Current files
    ├─ Trees            ├─ Tags
    └─ Blobs            └─ HEAD
```

**Interactive Demo**: 🎮 [Git Object Model Visualizer](https://git-school.github.io/visualizing-git/)

## Core Axioms

These five mathematical principles form the foundation of Git's design:

### 1. **Immutability** 🔒
Once an object is created and hashed, its content never changes.

**Mathematical Expression**: `∀ object o: hash(o) = h ⇒ content(o) = constant`

**Real-world Analogy**: Like a fingerprint, once computed, an object's hash uniquely identifies that exact content forever.

**Implementation Detail**: Git stores objects in `.git/objects/` using the first 2 characters of the hash as directory name and remaining 38 as filename.

### 2. **Content Addressing** 🎯
Objects are identified solely by the SHA-1 hash of their content.

**Mathematical Expression**: `object_id = SHA1(object_type + " " + content_size + "\0" + content)`

**Example**:
```bash
# These commands will always produce the same hash for the same content
echo "Hello, Git!" | git hash-object --stdin
# Output: 4ab299c8ad1ed8573488262809b8e1d65788a3b2
```

**Benefits**: Automatic deduplication, integrity verification, distributed consistency

### 3. **Structural Integrity** ⛓️
Parent-child relationships are cryptographically verified through hash chains.

**Mathematical Expression**: `commit.parent_hash ⊂ commit.hash_computation`

**Merkle Property**: Any change in history propagates upward, changing all subsequent hashes.

**Security Implication**: Makes tampering with Git history computationally infeasible.

### 4. **Reachability** 🌐
Repository state is determined by what commits are reachable from branch heads.

**Graph Theory**: Uses reachability in DAGs to determine which objects are part of repository state.

**Mathematical Expression**: `repo_state = {o | o is reachable from any ref in refs/}`

**Practical Effect**: Unreachable objects can be garbage collected without affecting repository integrity.

### 5. **Distributed Consensus** 🤝
Any two repositories with the same commit history are mathematically equivalent.

**Mathematical Expression**: `repo1.commits = repo2.commits ⇒ repo1 ≡ repo2`

**Consequence**: No central authority needed - any repository can serve as the "canonical" version.

## Formal Mathematical Model

### Repository Structure
```
Repository = (Objects, References, WorkingTree)

Objects = {
  Commit: (tree_hash, parent_hashes[], message, author, timestamp)
  Tree: (entries[] → {name, mode, hash})
  Blob: (content)
}

References = {
  Branch: name → commit_hash
  Tag: name → commit_hash
  HEAD: symbolic_ref → branch_name
}

WorkingTree = current_filesystem_state
```

### Object Type Hierarchy
```
                    Git Object
                        |
        ┌───────────────┼───────────────┐
        │               │               │
      Commit          Tree            Blob
        |               |               |
   ┌────┼────┐         │          Raw Content
   │    │    │         │               |
 tree parent msg    entries[]      (immutable)
   |    |    |         |
  SHA  SHA  str   [{name,mode,SHA}]
```

**Interactive Tool**: 🔧 [Git Object Browser](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects)

## Mathematical Properties

### 1. **DAG Structure** 📊
Commits form a directed acyclic graph where edges point from child to parent.

**Formal Definition**: 
- G = (V, E) where V = commits, E = parent relationships
- ∀ v ∈ V: v has finite in-degree (finite parents)
- ∀ v ∈ V: no path v → v (acyclic property)

**Topological Properties**:
- Always has a topological ordering
- Reachability is well-defined
- Merge base (LCA) always exists for connected commits

**Visual Example**:
```
    A ← B ← D ← F    (main branch)
        ↖   ↗
          C ← E      (feature branch)
```

### 2. **Merkle Property** 🌳
Any change in history changes all subsequent hashes, creating tamper-evident history.

**Mathematical Proof**:
- If content(x) changes → hash(x) changes
- If parent_hash ∈ commit_computation → parent change propagates
- Therefore: any historical change invalidates all descendant commits

**Security Implication**: O(1) integrity verification for entire repository state

**External Reference**: 📖 [Merkle Trees in Cryptography](https://en.wikipedia.org/wiki/Merkle_tree)

### 3. **Collision Resistance** 🛡️
SHA-1 properties ensure object integrity (being migrated to SHA-256 for enhanced security).

**Current Status**:
- SHA-1: 160-bit output, ~2^80 operations to find collision
- SHA-256: 256-bit output, ~2^128 operations to find collision
- Git is transitioning to SHA-256 for new repositories

**Probability Analysis**:
- For 10^6 objects: collision probability ≈ 10^-35 (SHA-1)
- Birthday paradox starts affecting at ~2^80 objects

**Migration Resources**: 🔄 [SHA-256 Transition Plan](https://git-scm.com/docs/hash-function-transition)

### 4. **Partial Order** ⩽
Commits have a natural partial ordering based on ancestry.

**Formal Definition**: 
- a ≤ b iff a is reachable from b (a is ancestor of b)
- Properties: reflexive, transitive, antisymmetric
- Not total order: concurrent commits are incomparable

**Applications**:
- Merge base computation (greatest lower bound)
- Branch fast-forward detection
- Topological sorting for git log

## Advanced Concepts

### Content-Addressable Storage
Git implements a **Content-Addressable Storage (CAS)** system where:

```
store(content) → hash
retrieve(hash) → content
∀ content: retrieve(store(content)) = content
```

**Benefits**:
- 🔄 Automatic deduplication (same content = same hash)
- 🔍 Integrity verification (content corruption detectable)
- 🌐 Location independence (hash valid across all repositories)

**Implementation**: Uses filesystem as key-value store with hash as key.

### Distributed Consensus Model
Git achieves consistency without traditional consensus algorithms:

**Local Consistency**: Each repository maintains strong consistency
**Global Convergence**: Repositories converge when they share the same commits
**No Coordination**: No need for leader election or global state

**Comparison with Traditional Systems**:
| Property | Git | Traditional VCS |
|----------|-----|-----------------|
| Consistency | Eventual | Immediate |
| Availability | High | Limited |
| Partition Tolerance | Full | None |

## Practical Implications

### Why Git is Fast
1. **O(1) Operations**: Branch creation, switching (just pointer updates)
2. **Merkle Benefits**: O(log n) integrity verification
3. **Content Addressing**: Automatic caching and deduplication
4. **Local Operations**: Most commands don't require network

### Why Git Scales
1. **Distributed Architecture**: No single bottleneck
2. **Efficient Storage**: Delta compression in packfiles
3. **Smart Protocol**: Only transfers needed objects
4. **Parallel Operations**: Independent repository operations

## External Resources

### Academic Papers
- 📄 [The Git Object Model](https://github.com/git/git/blob/master/Documentation/gitcore-tutorial.txt) - Original design document
- 📄 [Merkle Trees](https://people.eecs.berkeley.edu/~raluca/cs261-f15/readings/merkle.pdf) - Foundational cryptography paper

### Interactive Tools
- 🎮 [Learn Git Branching](https://learngitbranching.js.org/) - Visual Git learning
- 🔧 [Git Internals Browser](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects) - Explore Git objects
- 📊 [Git Graph Visualizer](https://git-graph.vercel.app/) - DAG visualization tool

### Documentation
- 📖 [Pro Git - Git Internals](https://git-scm.com/book/en/v2/Git-Internals-Plumbing-and-Porcelain)
- 📖 [Git Object Model Documentation](https://git-scm.com/docs/git-cat-file)

## Files in This Section

- `model-definition.md` - Formal mathematical definition with proofs
- `object-types.md` - Detailed breakdown of Git's object model
- `dag-properties.md` - Graph-theoretic properties of the commit graph
- `merkle-tree.md` - How Git implements Merkle tree concepts
- `examples/` - Practical examples and exercises
  - `hash-computation.py` - Script demonstrating hash calculations
  - `dag-traversal.py` - DAG walking algorithms
  - `merkle-verification.py` - Integrity verification examples

---

**Next**: Explore the [Mathematical Toolkit](../02-math-toolkit/index.md) that Git builds upon. 🧮

**Previous**: Return to [Main README](../index.md) 🏠