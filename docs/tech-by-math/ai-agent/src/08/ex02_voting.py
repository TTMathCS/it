# Asking several times and taking the majority answer ("self-consistency").
# Exact binomial sums, then a model where the answers are not independent.
import math, random

def majority(p, n):
    """Chance that more than half of n independent answers are right (n odd)."""
    return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(n // 2 + 1, n + 1))

print("Part 1. Independent answers, right with chance p; majority of n")
for p in (0.6, 0.8, 0.45):
    print(f"   p = {p}: " + ", ".join(f"n={n}: {majority(p, n):.3f}" for n in (1, 3, 5, 9, 15)))
print("   by hand, p = 0.6, n = 3: 3 x 0.6^2 x 0.4 + 0.6^3 = 0.432 + 0.216 = 0.648")

print()
print("Part 2. Answers that share their mistakes: with chance c all n answers copy one draw")
rng = random.Random(3)
for c in (0.0, 0.5, 0.9):
    exact = c * 0.6 + (1 - c) * majority(0.6, 5)
    ok = 0
    for _ in range(200_000):
        if rng.random() < c:
            ok += rng.random() < 0.6
        else:
            ok += sum(rng.random() < 0.6 for _ in range(5)) >= 3
    print(f"   c = {c}: majority of 5 right {exact:.3f} (simulated {ok / 200_000:.3f}); one answer alone 0.600")

print()
print("Part 3. Cost: n answers cost n times as much")
for n in (1, 3, 5, 9, 15):
    print(f"   n = {n:>2}: accuracy {majority(0.6, n):.3f} at {n:>2}x the cost")
