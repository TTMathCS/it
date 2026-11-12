# Tech by Math, Networks tutorial 8: link costs from bandwidth and Dijkstra's shortest paths on six routers,
# step by step, checked against trying every simple path.
import heapq
from itertools import permutations

REF = 10_000  # reference bandwidth in Mbit/s: cost = REF / bandwidth
links = {("A", "B"): 1000, ("A", "C"): 100, ("B", "C"): 1000, ("B", "D"): 100, ("C", "E"): 1000,
         ("D", "F"): 10_000, ("E", "D"): 1000, ("E", "F"): 100}
cost = {}
for (u, v), bw in links.items():
    cost.setdefault(u, {})[v] = REF // bw
    cost.setdefault(v, {})[u] = REF // bw
print(f"Link costs = {REF:,} / bandwidth (Mbit/s):")
print("   " + ", ".join(f"{u}-{v} {bw:,} -> {REF // bw}" for (u, v), bw in links.items()))

print("\nDijkstra from A (take the closest unfinished router, then relax its links):")
dist, prev, done = {"A": 0}, {}, set()
heap = [(0, "A")]
while heap:
    d, u = heapq.heappop(heap)
    if u in done:
        continue
    done.add(u)
    changes = []
    for v, c in sorted(cost[u].items()):
        if v not in done and d + c < dist.get(v, 10**9):
            dist[v], prev[v] = d + c, u
            heapq.heappush(heap, (d + c, v))
            changes.append(f"{v}={d + c}")
    print(f"   finish {u} at {d:>3}; update {', '.join(changes) or 'nothing'}")


def path(t):
    p = [t]
    while p[-1] != "A":
        p.append(prev[p[-1]])
    return "-".join(reversed(p))


print("\nResult, and a check by trying every simple path:")
nodes = sorted(cost)
for t in nodes[1:]:
    best = min((sum(cost[a][b] for a, b in zip(p, p[1:])), "-".join(p))
               for k in range(0, len(nodes) - 1)
               for mid in permutations([n for n in nodes if n not in ("A", t)], k)
               for p in [("A",) + mid + (t,)]
               if all(b in cost[a] for a, b in zip(p, p[1:])))
    print(f"   A -> {t}: {dist[t]:>3} via {path(t):<12} brute force: {best[0]:>3} via {best[1]}")

print("\nWith a reference of 100 Mbit/s instead, every link of 100 Mbit/s or more costs 1 (cost = max(1, 100 // bw)):")
print("   " + ", ".join(f"{u}-{v} {max(1, 100 // bw)}" for (u, v), bw in links.items()) + "  -> hop count only")


def shortest(costfn, src, dst):
    best = {src: (0, src)}
    heap = [(0, src, src)]
    seen = set()
    while heap:
        d, u, pth = heapq.heappop(heap)
        if u in seen:
            continue
        seen.add(u)
        for v in sorted(cost[u]):
            nd = d + costfn(u, v)
            if v not in seen and nd < best.get(v, (10**9,))[0]:
                best[v] = (nd, pth + "-" + v)
                heapq.heappush(heap, (nd, v, pth + "-" + v))
    return best[dst]


bw = {**links, **{(v, u): b for (u, v), b in links.items()}}
d, p = shortest(lambda u, v: 1, "A", "F")
print(f"   A -> F by hop count: {d} hops via {p}; slowest link on it {min(bw[(a, b)] for a, b in zip(p.split('-'), p.split('-')[1:])):,} Mbit/s")
d, p = shortest(lambda u, v: cost[u][v], "A", "F")
print(f"   A -> F by cost 10,000 / bw: cost {d} via {p}; slowest link on it {min(bw[(a, b)] for a, b in zip(p.split('-'), p.split('-')[1:])):,} Mbit/s")
