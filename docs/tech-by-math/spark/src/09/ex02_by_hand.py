# Tech by Math, Spark tutorial 9: the pencil examples of 9.3, checked in plain Python (no Spark).
from fractions import Fraction
from statistics import median

parts = [[4, 8, 6], [10, 30], [1, 2, 3, 5, 7]]  # three partitions of one group
allv = [v for p in parts for v in p]

print("Step 1. A sum in pieces")
partial = [sum(p) for p in parts]
print(f"   partial sums {partial}, merged {sum(partial)}, sum of all {sum(allv)}")

print("\nStep 2. Averages")
means = [Fraction(sum(p), len(p)) for p in parts]
print(f"   partition means {[str(m) for m in means]}")
print(f"   mean of the means {float(sum(means) / len(means)):.4f}  (wrong)")
pairs = [(sum(p), len(p)) for p in parts]
s, n = map(sum, zip(*pairs))
print(f"   (sum, count) pairs {pairs} -> merged ({s}, {n}) -> {s}/{n} = {s / n:.4f};  true mean {sum(allv) / len(allv):.4f}")

print("\nStep 3. Medians")
meds = [median(p) for p in parts]
print(f"   partition medians {meds}, median of the medians {median(meds)}, true median {median(allv)}")
print(f"   sorted values {sorted(allv)}")

# the adversary: A is known; B has j tiny values and m - j huge ones; every a_i can be the lower median
A = [3, 7, 9, 12, 20]
m = len(A)
print(f"\n   adversary for A = {A} (m = {m}): lower median of A + B, where B = j tiny values and {m}-j huge ones")
for j in range(m):
    B = [-1000] * j + [1000] * (m - j)
    print(f"      j = {j}: lower median = {sorted(A + B)[m - 1]}")

print("\nStep 4. A summary that keeps every g-th value, with its rank")
P1 = list(range(1, 201, 2))     # 100 odd numbers
P2 = list(range(2, 401, 4))     # 100 numbers 2, 6, 10, ...
g = 10


def summary(xs, g):
    xs = sorted(xs)
    keep = [(xs[i], i + 1) for i in range(g - 1, len(xs), g)]  # (value, its exact rank in this partition)
    return keep, len(xs)


def estimate_rank(summaries, v):
    """Rank of v in the union: lower and upper bounds from the kept ranks only."""
    lo = hi = 0
    for keep, n in summaries:
        below = [r for (x, r) in keep if x <= v]
        above = [r for (x, r) in keep if x > v]
        lo += below[-1] if below else 0
        hi += (above[0] - 1) if above else n
    return lo, hi


S1, S2 = summary(P1, g), summary(P2, g)
print(f"   P1: {len(P1)} values, summary keeps {len(S1[0])}: {S1[0][:3]} ...")
print(f"   P2: {len(P2)} values, summary keeps {len(S2[0])}: {S2[0][:3]} ...")
N = len(P1) + len(P2)
allp = sorted(P1 + P2)
worst = 0
for v in sorted({x for x, _ in S1[0] + S2[0]}):
    lo, hi = estimate_rank([S1, S2], v)
    true = sum(1 for x in allp if x <= v)
    assert lo <= true <= hi
    worst = max(worst, hi - lo)
print(f"   N = {N}; for every kept value the true rank lies in [lo, hi]; widest interval hi - lo = {worst} (bound: 2 x (g - 1) = {2 * (g - 1)})")
cand = sorted({x for x, _ in S1[0] + S2[0]}, key=lambda v: abs(sum(estimate_rank([S1, S2], v)) / 2 - N / 2))[0]
lo, hi = estimate_rank([S1, S2], cand)
true = sum(1 for x in allp if x <= cand)
print(f"   median estimate from the summaries: {cand} (rank between {lo} and {hi}); its true rank {true} of {N}; true median {allp[N // 2 - 1]}")

print("\nStep 5. Floating point addition is not associative")
a, b, c = 0.1, 0.2, 0.3
print(f"   (0.1 + 0.2) + 0.3 = {repr((a + b) + c)}")
print(f"   0.1 + (0.2 + 0.3) = {repr(a + (b + c))}")
print(f"   1e16 + 1 - 1e16 = {repr(1e16 + 1 - 1e16)};  1e16 - 1e16 + 1 = {repr(1e16 - 1e16 + 1)}")
