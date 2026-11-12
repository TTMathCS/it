# 8. How Kubernetes places pods and counts them

*A new pod asks for half a core and 1 GiB of memory. Three nodes have room. Kubernetes picks one in a fraction of a second, by giving each node a score out of 100. Later, traffic doubles, and the autoscaler decides to go from 4 pods to 6. Both decisions are short pieces of arithmetic in Kubernetes' source code. This tutorial does them by hand, shows why the default "spread" placement can leave a cluster unable to fit a large pod while 14 cores sit free, and why the autoscaler deliberately ignores small changes.*

!!! abstract "In this tutorial"
    **You will learn:**

    - resource units: millicores, and why `512Mi` and `512M` differ by almost 5%
    - the filter step: a pod fits a node only if every request fits in what is left
    - the default scores, `LeastAllocated` and `BalancedAllocation`, computed by hand for three nodes, including Go's whole-number division
    - spreading against packing: the same 40 pods on 14 nodes, and what each leaves free
    - the lower bound on nodes, `⌈total requests / node size⌉` for each resource
    - the Horizontal Pod Autoscaler's rule, `⌈replicas × current / target⌉`, its 10% tolerance, and what that tolerance does over a day

    **You need:** fractions, percentages, rounding up (`⌈4.2⌉ = 5`), and a standard deviation of two numbers (half their difference).

    **How to learn from it:** read 8.1 to 8.3, close the page, redo the scores and the autoscaler cases of 8.3 on paper, then try the exercises in 8.7 before opening any answer. Plan about two hours.

**About the examples. No Kubernetes cluster ran for this tutorial.** The rules are copied into Python from Kubernetes 1.34.1's source: `least_allocated.go`, `most_allocated.go`, `balanced_allocation.go` and `resource_allocation.go` (scheduler scoring), `default_plugins.go` and `defaults.go` (default weights), `replica_calculator.go` and `utilization.go` (the autoscaler), and the controller defaults (tolerance 0.1). The placement of 40 pods and the day of traffic are **simulations** of those rules, not runs of a real scheduler, which also weighs many other things (8.6). The scripts and their full output: [k8s_math.py](src/08/k8s_math.py) (the rules), [ex01_scheduler.py](src/08/ex01_scheduler.py) ([output](src/08/ex01.out.txt)), [ex02_hpa.py](src/08/ex02_hpa.py) ([output](src/08/ex02.out.txt)), and the answer to exercise E7, [ex03_no_balance.py](src/08/ex03_no_balance.py).

## 8.1 The question

Every node in the cluster has 4 cores and 16 GiB of memory. Three nodes already carry pods that requested:

| node | CPU requested | memory requested |
| --- | ---: | ---: |
| node-a | 3,000m | 4,096Mi |
| node-b | 1,000m | 12,288Mi |
| node-c | 2,000m | 8,192Mi |

1. A new pod requests `cpu: 500m, memory: 1Gi`. Which node does the scheduler choose, and why?
2. Over a day, 40 pods arrive on a cluster of 14 nodes. Does the default placement leave room for a pod that needs 2 full cores?
3. A web service has 4 pods at 90% CPU against a target of 60%. How many pods does the autoscaler ask for? And at 65%?

## 8.2 The idea: requests are promises, and the scheduler does bookkeeping

A pod declares **requests**: the CPU and memory it is guaranteed. The scheduler never looks at how busy a node really is; it adds up the requests of the pods placed on each node and compares them with the node's **allocatable** capacity. Placement is bookkeeping on promises.

For each new pod the scheduler runs two phases:

1. **Filter**: drop every node where the pod does not fit (for each resource, requests already placed + this pod's request ≤ allocatable), and nodes ruled out by other rules (taints, affinity, ports, volumes).
2. **Score**: each scoring plugin gives each remaining node a score from 0 to 100; the node with the highest weighted total wins (ties broken at random).

The **Horizontal Pod Autoscaler** (HPA) works on another level: it changes how many copies (**replicas**) of a pod exist, by comparing measured use with a target.

## 8.3 The math by hand

### Step 1. Units

CPU is counted in **millicores**: `1` core = `1000m`, so `500m` is half a core. Memory uses two families of suffixes:

```text
Mi = 2^20 bytes = 1,048,576       M = 10^6 bytes = 1,000,000
Gi = 2^30 bytes = 1,073,741,824   G = 10^9 bytes = 1,000,000,000
```

`512Mi = 536,870,912` bytes but `512M = 512,000,000`: a 4.86% difference. `1Gi / 1G = 1.0737`, 7.37% (`ex01`). Mixing the two in requests and limits is a classic way to be off by a few percent, and the difference grows with each prefix (Ti against T: about 10%).

### Step 2. Filter

The new pod needs 500m and 1,024Mi. After placing it, each node would carry:

| node | CPU after | memory after | fits in 4,000m and 16,384Mi? |
| --- | ---: | ---: | --- |
| node-a | 3,500m | 5,120Mi | yes |
| node-b | 1,500m | 13,312Mi | yes |
| node-c | 2,500m | 9,216Mi | yes |

All three pass.

### Step 3. Score: LeastAllocated

The default `NodeResourcesFit` scoring strategy is `LeastAllocated`, with CPU and memory weighted 1 each. For each resource:

```text
score = (capacity − requested) × 100 / capacity        (whole-number division, as in Go)
```

where `requested` includes the new pod. Then the weighted average over the resources, again with whole-number division:

| node | CPU: (4000 − req) × 100 / 4000 | memory: (16384 − req) × 100 / 16384 | average |
| --- | ---: | ---: | ---: |
| node-a | 500 × 100 / 4000 = 12 | 11,264 × 100 / 16,384 = 68 | (12 + 68) / 2 = **40** |
| node-b | 2500 × 100 / 4000 = 62 | 3,072 × 100 / 16,384 = 18 | (62 + 18) / 2 = **40** |
| node-c | 1500 × 100 / 4000 = 37 | 7,168 × 100 / 16,384 = 43 | (37 + 43) / 2 = **40** |

(Whole-number division drops fractions: `2500 × 100 / 4000 = 62.5` becomes 62.) A three-way tie: on average, each node would be 60% full. LeastAllocated prefers emptier nodes, which spreads pods out, but it cannot tell these three apart.

### Step 4. Score: BalancedAllocation

`NodeResourcesBalancedAllocation` (also on by default, weight 1) prefers nodes whose CPU and memory are used in the same proportion. With fractions `f_cpu` and `f_mem` after placement, the standard deviation of two numbers is half their difference, and

```text
score = (1 − |f_cpu − f_mem| / 2) × 100        (cut to a whole number)
```

| node | f_cpu | f_mem | score |
| --- | ---: | ---: | ---: |
| node-a | 0.875 | 0.3125 | (1 − 0.28125) × 100 = **71** |
| node-b | 0.375 | 0.8125 | (1 − 0.21875) × 100 = **78** |
| node-c | 0.625 | 0.5625 | (1 − 0.03125) × 100 = **96** |

Totals (both plugins weight 1): node-a 111, node-b 118, **node-c 136** (`ex01`). The pod goes to node-c. The idea behind the balance score: node-a would be left with plenty of memory but almost no CPU, which no pod can use without CPU. In the default configuration other plugins also score (taints with weight 3, node affinity, topology spread and pod affinity with weight 2, image locality with weight 1); for three identical nodes with no special rules they give equal scores, and this example assumes so.

### Step 5. Spreading against packing

`ex01` places 40 pods, each requesting a random size (250m to 1,500m of CPU, 512Mi to 4Gi of memory), one after another on 14 empty nodes, each time on the node with the best total score:

| strategy | nodes in use | empty nodes | largest free CPU on one node |
| --- | ---: | ---: | ---: |
| spread (LeastAllocated, the default) | 14 | 0 | 1,500m |
| pack (MostAllocated) | 11 | 3 | 4,000m |

The pods need 40,250m of CPU in all, so at least `⌈40,250 / 4,000⌉ = 11` nodes, whatever the strategy: a **lower bound**. Packing reaches it and leaves 3 nodes empty, which a cluster autoscaler could remove to save money. Spreading uses all 14 nodes; 15,750m of CPU is free in total, yet **no node has 2 free cores**, so a pod requesting 2,000m would not fit anywhere. That is **fragmentation**: free capacity in pieces too small to use.

Spreading is the default for a reason: when a node fails, fewer pods go down with it, and each pod has room to grow. `MostAllocated` is a setting to choose deliberately, usually together with a cluster autoscaler.

### Step 6. The autoscaler's rule

The HPA measures the pods' average CPU use as a whole percentage of their requests, divides by the target, and

```text
ratio    = current utilisation / target utilisation
replicas = ⌈ratio × current replicas⌉      unless 0.9 ≤ ratio ≤ 1.1, then no change
```

(`replica_calculator.go`; the 0.1 tolerance is the controller's default.) Worked (`ex02`), target 60%:

| pods | utilisation | ratio | new pods |
| ---: | ---: | ---: | ---: |
| 4 | 90% | 1.500 | ⌈6.0⌉ = **6** |
| 10 | 65% | 1.083 | within tolerance: **10** |
| 10 | 50% | 0.833 | ⌈8.33⌉ = **9** |
| 3 | 200% | 3.333 | ⌈10.0⌉ = **10** |
| 6 | 54% | 0.900 | within tolerance: **6** |

Why multiply? If the load stays the same and is shared evenly, `n` pods at utilisation `u` carry `n × u` in total; to bring each to the target `t`, you need `n × u / t` pods. Rounding up keeps utilisation at or below the target.

## 8.4 Why it is true

**The lower bound on nodes.** Requests on a node cannot exceed its capacity, so `k` nodes hold at most `k × capacity` of each resource. If the total CPU requested is `R`, then `k × 4,000 ≥ R`, so `k ≥ R / 4,000`, and `k` is whole, so `k ≥ ⌈R / 4,000⌉`. The same holds for memory; the larger of the two is the bound. Finding the smallest number of nodes exactly is the **bin-packing problem**, which is NP-hard: no efficient method is known that always finds the optimum. The scheduler does not try; it places one pod at a time, greedily.

**Ties in LeastAllocated.** With equal weights and equal node sizes, the LeastAllocated score is `100 − (average fraction used) × 100`, up to rounding. Three nodes with the same average fraction (60% here) tie, whatever their mix. That is exactly the gap BalancedAllocation fills.

**The HPA's fixed point.** If utilisation is exactly on target, the ratio is 1 and nothing changes. The tolerance band makes every replica count `n` stable for a range of loads: from `0.9 × t × n` to `1.1 × t × n`, measured in the same units. Without the band, measurement noise around the target would add and remove a pod every few seconds. The price is that the HPA can sit at up to 10% above or below the target indefinitely. In `ex02`'s day of traffic, at 13:00 the service runs at 63% with 19 pods, where `⌈12 / 0.6⌉ = 20` would be exact, and the same 19 pods stay from 11:00 to 15:00 as the load rises and falls inside the band.

## 8.5 See it in the model

`ex01` prints the scores of steps 3 and 4 and the placement of step 5, node by node:

```text
spread (LeastAllocated, the default) : 14 nodes in use, 0 empty; the largest free cpu on one node: 1500m
   cpu% per node:  75  62  93  87  68  75  62  81  62  62  62  68  81  62
pack (MostAllocated)                 : 11 nodes in use, 3 empty; the largest free cpu on one node: 4000m
   cpu% per node: 100 100 100  87 100 100 100  93  75  75  75   0   0   0
```

`ex02` runs the autoscaler over a day whose demand rises from 3 cores at night to 12 at 13:00 and back, with pods requesting 1 core each:

```text
09:00 demand  8.61 cores -> 15 pods (utilisation  57%; ceil(demand / 0.6) = 15)
10:00 demand 10.04 cores -> 15 pods (utilisation  66%; ceil(demand / 0.6) = 17)
11:00 demand 11.11 cores -> 19 pods (utilisation  58%; ceil(demand / 0.6) = 19)
13:00 demand 12.00 cores -> 19 pods (utilisation  63%; ceil(demand / 0.6) = 20)
```

At 10:00, 66% is within 10% of 60% (ratio 1.1 exactly), so nothing happens; an hour later the ratio leaves the band and the HPA jumps by 4 pods at once.

## 8.6 Where it breaks

- **Requests are not use.** The scheduler places by requests. A pod that requests 100m and uses 2 cores overloads its node without the scheduler knowing; a pod that requests 4 cores and uses 0.1 wastes a node. Good requests are the input to all the arithmetic above.
- **Pods without requests.** For scoring, a pod with no CPU or memory request counts as 100m and 200Mi (`DefaultMilliCPURequest`, `DefaultMemoryRequest` in the source), so it still spreads, but for fitting it counts as zero.
- **Many other scores.** Taints, affinity, topology spread, image locality and others add their own scores, often with larger weights. The resource scores of steps 3 and 4 decide only among nodes the others rate equally.
- **Fragmentation.** Step 5: spreading leaves free capacity in small pieces. Large pods may need preemption, a packing strategy, or dedicated nodes.
- **The autoscaler acts with delay and memory.** Metrics are averaged over a window; scaling down by default waits through a 5-minute stabilisation window; pods that are starting or not ready are treated specially (`replica_calculator.go`). The rule of step 6 is the core, not the whole.
- **Utilisation can exceed 100%.** A pod may use more CPU than it requested (up to its limit), so utilisation of 200% is possible and the ratio can be large (the 3-pods-at-200% row).

## 8.7 Exercises

Do 1 to 5 with a pencil. 6 needs a few lines of thought. 7 is code.

**E1. A node has 8 cores and 32Gi. Pods on it request 5,500m and 20Gi. A new pod requests 1,500m and 4Gi. Compute the LeastAllocated and BalancedAllocation scores.**

??? success "Answer"
    After placing: 7,000m of 8,000m and 24Gi of 32Gi. LeastAllocated: CPU `1000 × 100 / 8000 = 12` (12.5 cut to 12), memory `8 × 100 / 32 = 25`; average `(12 + 25) / 2 = 18` (18.5 cut). Balanced: fractions 0.875 and 0.75, `(1 − 0.0625) × 100 = 93` (93.75 cut).

**E2. How many bytes is `3Gi`? `3G`? Which is larger, and by how much?**

??? success "Answer"
    `3 × 1,073,741,824 = 3,221,225,472`; `3,000,000,000`. `3Gi` is larger by 221,225,472 bytes, 7.37%.

**E3. 50 pods each request 700m and 3Gi. Nodes have 4 cores and 16Gi. What is the lower bound on nodes? How many pods fit on one node, and so how many nodes are really needed?**

??? success "Answer"
    CPU: `50 × 700 = 35,000m`, `⌈35,000 / 4,000⌉ = 9`. Memory: `150Gi`, `⌈150 / 16⌉ = 10`. Lower bound 10. Per node: CPU allows `⌊4000 / 700⌋ = 5` pods, memory `⌊16 / 3⌋ = 5`: 5 pods, so `⌈50 / 5⌉ = 10` nodes, and the bound is reached. (Each node keeps 500m and 1Gi unused: pieces too small for another pod.)

**E4. The HPA target is 70%. 8 pods run at 84%. Then the load falls and they run at 58%. What does the HPA do each time?**

??? success "Answer"
    `84 / 70 = 1.2`, outside the band: `⌈1.2 × 8⌉ = ⌈9.6⌉ = 10` pods. Then, with 8 pods at 58% (say before the new ones start): `58 / 70 = 0.829`: `⌈0.829 × 8⌉ = ⌈6.63⌉ = 7` pods (and the 5-minute stabilisation window would delay this scale-down in a real cluster).

**E5. With target 60% and 20 pods, between which utilisations does the HPA do nothing? How many cores of total use is that, if each pod requests 1 core?**

??? success "Answer"
    Ratio from 0.9 to 1.1: utilisation from 54% to 66%. Total use from `0.54 × 20 = 10.8` to `0.66 × 20 = 13.2` cores. Any load in that 2.4-core range keeps 20 pods.

**E6. A team sets every pod's CPU request to 2 cores "to be safe", while the pods use about 0.3. What happens to placement, and to the HPA with a 60% target?**

??? success "Answer"
    Placement: each node of 4 cores takes only 2 such pods, so the cluster needs far more nodes than the real use requires. HPA: utilisation is use divided by request, `0.3 / 2 = 15%`, so the ratio is `0.25` and the HPA scales down to the minimum allowed; it never scales up until use passes about 1.3 cores per pod. Requests far from real use break both.

**E7. (Code.) With `k8s_math.py`, place the same 40 pods as `ex01` with BalancedAllocation switched off (score by LeastAllocated only), and compare the largest free CPU on one node.**

??? success "Answer"
    In `ex01_scheduler.py`, change `s = score(req) + balanced(req, alloc)` to `s = score(req)` and run it again ([ex03_no_balance.py](src/08/ex03_no_balance.py), [output](src/08/ex03.out.txt)). Spreading still uses all 14 nodes, but the pods land differently: CPU per node now ranges from 43% to 100%, and the largest free CPU on one node is 2,250m, so this time a 2-core pod would fit. Packing still uses 11 nodes. The lower bound of 11 nodes and the 15,750m of total free CPU do not change: they depend only on the pods' totals. Small changes in scoring move the fragments around; they do not remove them.

## 8.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a pod stuck in Pending, a cluster that would not scale down, or an autoscaler that surprised you, and which step explained it.)*

## 8.9 Further reading

On your own sites:

- Greedy algorithms and NP-hard problems: [the CS site](https://cs.akadian.ca/)
- Load and partitions in data systems: [Spark 8. Shuffles and skew](../spark/08-Shuffles-and-Skew.md), [Kafka 8. The log, offsets and lag](../kafka/08-Log-Offsets-and-Lag.md)

Original sources:

- Kubernetes 1.34.1 source, at [github.com/kubernetes/kubernetes](https://github.com/kubernetes/kubernetes/tree/v1.34.1): `pkg/scheduler/framework/plugins/noderesources/` (scores), `pkg/scheduler/apis/config/v1/default_plugins.go` (weights), `pkg/controller/podautoscaler/replica_calculator.go` and `metrics/utilization.go` (the HPA), `pkg/scheduler/util/pod_resources.go` (default requests).
- Kubernetes documentation: "Scheduling Framework", "Resource Bin Packing", "Horizontal Pod Autoscaling" (kubernetes.io).
- A. Verma, L. Pedrosa, M. Korupolu, D. Oppenheimer, E. Tune and J. Wilkes, "Large-scale cluster management at Google with Borg", *EuroSys 2015*. The system Kubernetes grew from, with a discussion of spreading and packing.
- E. G. Coffman, M. R. Garey and D. S. Johnson, "Approximation algorithms for bin packing: a survey", in *Approximation Algorithms for NP-Hard Problems*, 1996.

## Glossary

- **Pod**: the smallest unit Kubernetes runs: one or more containers placed together.
- **Request**: the CPU and memory a pod is guaranteed; what the scheduler counts.
- **Limit**: the most a pod may use; not used for placement.
- **Allocatable**: what a node offers to pods, after the system's own share.
- **Millicore (m)**: a thousandth of a CPU core.
- **Mi, Gi / M, G**: powers of 2 (2^20, 2^30 bytes) against powers of 10 (10^6, 10^9 bytes).
- **Filter / score**: the scheduler's two phases: drop nodes that cannot take the pod, then rank the rest.
- **LeastAllocated / MostAllocated**: scores that prefer emptier (spread) or fuller (pack) nodes.
- **BalancedAllocation**: a score that prefers nodes whose CPU and memory fill evenly.
- **Bin packing**: placing items of given sizes into the fewest bins of fixed size.
- **Fragmentation**: free capacity split into pieces too small to use.
- **HPA**: Horizontal Pod Autoscaler, which changes the number of replicas from measured use.
- **Tolerance**: the band around the target (±10% by default) in which the HPA does nothing.
