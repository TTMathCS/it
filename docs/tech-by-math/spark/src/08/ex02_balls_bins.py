# Tech by Math, pilot: K equal keys thrown at random into n partitions. How far is the fullest partition above the mean?
# Compares the simulated maximum with the approximation mean + sqrt(2 * mean * ln n) (Raab and Steger 1998,
# valid when K is much larger than n ln n).
import math
import numpy as np

rng = np.random.default_rng(2026)
TRIALS = 200

def sim(K, n):
    maxes = []
    for _ in range(TRIALS):
        counts = np.bincount(rng.integers(0, n, size=K), minlength=n)
        maxes.append(counts.max())
    return float(np.mean(maxes)), int(np.min(maxes)), int(np.max(maxes))

print(f"{'n':>5} {'K':>9} {'n ln n':>8} {'mean':>8} {'formula max':>11} {'simulated max (avg)':>19} {'range':>11} {'sim max/mean':>12}")
for n, K in [(8, 64), (8, 16), (200, 2000), (200, 20000), (200, 200000), (200, 1000000), (3, 8)]:
    mean = K / n
    formula = mean + math.sqrt(2 * mean * math.log(n))
    avg, lo, hi = sim(K, n)
    print(f"{n:>5} {K:>9} {n * math.log(n):>8.0f} {mean:>8.1f} {formula:>11.1f} {avg:>19.1f} {f'{lo}-{hi}':>11} {avg / mean:>12.3f}")

# Salting is a second throw: k slices of the hot key (H rows) land at random in n partitions.
# Predicted fullest partition = (H / k) * (average largest number of slices in one partition) + cold rows per partition.
print()
H, COLD, n = 240060, 300000 - 240060, 8
print(f"{'k':>4} {'avg max slices':>14} {'range':>7} {'predicted fullest partition':>27}")
for k in (2, 4, 8, 16, 32, 64, 256):
    avg, lo, hi = sim(k, n)
    print(f"{k:>4} {avg:>14.2f} {f'{lo}-{hi}':>7} {H / k * avg + COLD / n:>27.0f}")

# Expected number of empty partitions when k salt values of one key land at random in n partitions: n (1 - 1/n)^k
print()
for k, n in [(8, 8), (16, 8), (64, 8)]:
    print(f"k = {k:>2} salts into n = {n}: expected empty partitions = {n * (1 - 1 / n) ** k:.3f}")
