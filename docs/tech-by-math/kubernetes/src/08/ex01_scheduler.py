# Tech by Math, Kubernetes tutorial 8: scoring three nodes for one pod, then placing 40 pods with the
# default "spread" score and with the "pack" score. A model in Python of the scheduler's scoring rules
# (k8s_math.py); no cluster ran. CPU in millicores, memory in MiB.
import random
from k8s_math import least_requested, most_requested, weighted, balanced, fits

alloc = (4000, 16384)   # every node: 4 cores, 16 GiB
nodes = {"node-a": (3000, 4096), "node-b": (1000, 12288), "node-c": (2000, 8192)}  # already requested
pod = (500, 1024)
print(f"Pod requests cpu {pod[0]}m, memory {pod[1]}Mi. Each node has cpu {alloc[0]}m, memory {alloc[1]}Mi.")
print(f"   {'node':<7} {'cpu after':>10} {'mem after':>10} {'fit':>4} {'least cpu':>9} {'least mem':>9} {'Fit score':>9} {'Balanced':>8} {'total':>6}")
for name, used in nodes.items():
    req = tuple(u + p for u, p in zip(used, pod))
    ok = fits(used, pod, alloc)
    lc, lm = least_requested(req[0], alloc[0]), least_requested(req[1], alloc[1])
    fit = weighted(least_requested, req, alloc)
    bal = balanced(req, alloc)
    print(f"   {name:<7} {req[0]:>9}m {req[1]:>8}Mi {'yes' if ok else 'no':>4} {lc:>9} {lm:>9} {fit:>9} {bal:>8} {fit + bal:>6}")


def place(pods, score, n_nodes):
    used = [(0, 0)] * n_nodes
    for p in pods:
        best, best_s = None, -1
        for i, u in enumerate(used):
            if fits(u, p, alloc):
                req = tuple(a + b for a, b in zip(u, p))
                s = score(req) + balanced(req, alloc)
                if s > best_s:            # first best node wins a tie (the real scheduler picks among ties at random)
                    best, best_s = i, s
        if best is None:
            return None
        used[best] = tuple(a + b for a, b in zip(used[best], p))
    return used


random.seed(8)
pods = [(random.choice([250, 500, 1000, 1500]), random.choice([512, 1024, 2048, 4096])) for _ in range(40)]
tot = [sum(p[i] for p in pods) for i in range(2)]
lb = max(-(-tot[0] // alloc[0]), -(-tot[1] // alloc[1]))
print(f"\n40 pods, total cpu {tot[0]}m, memory {tot[1]}Mi: they need at least {lb} nodes (ceil of total / one node, per resource)")
print("Placed one by one on a cluster of 14 empty nodes, best total score first:")
for label, sc in (("spread (LeastAllocated, the default)", lambda r: weighted(least_requested, r, alloc)),
                  ("pack (MostAllocated)", lambda r: weighted(most_requested, r, alloc))):
    used = place(pods, sc, 14)
    busy = [u for u in used if u != (0, 0)]
    free_cpu = max(alloc[0] - u[0] for u in used)
    print(f"   {label:<37}: {len(busy)} nodes in use, {14 - len(busy)} empty; the largest free cpu on one node: {free_cpu}m")
    print("      cpu% per node: " + " ".join(f"{u[0] * 100 // alloc[0]:>3}" for u in used))

print("\nUnits: 1 core = 1000m;  1Mi = 2^20 bytes, 1M = 10^6 bytes")
for a, b in (("512Mi", 512 * 2**20), ("512M", 512 * 10**6), ("1Gi", 2**30), ("1G", 10**9)):
    print(f"   {a:<6} = {b:>13,} bytes")
print(f"   1Gi / 1G = {2**30 / 10**9:.4f};  512Mi / 512M = {2**20 / 10**6:.4f}")
