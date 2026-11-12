# Tech by Math, Kafka tutorial 8: how evenly Kafka's key rule spreads keys, a hot key, and what
# changing the number of partitions does. Pure Python (kmath.py = Kafka 4.3.2's rule); no broker.
import math
from collections import Counter
from kmath import murmur2, to_positive

def spread(keys, n):
    c = Counter(to_positive(murmur2(k.encode())) % n for k in keys)
    return [c.get(p, 0) for p in range(n)]

print("Part 1. K distinct keys customer-1 .. customer-K, each with one message, on n = 12 partitions")
n = 12
for K in (120, 1_200, 12_000, 120_000):
    loads = spread([f"customer-{i}" for i in range(1, K + 1)], n)
    mean = K / n
    formula = mean + math.sqrt(2 * mean * math.log(n))
    print(f"   K = {K:>7,}: fullest partition {max(loads):>6,}, mean {mean:>8,.0f}, max/mean {max(loads) / mean:.3f}; "
          f"balls-into-bins estimate {formula:,.0f} ({formula / mean:.3f})")

print("\nPart 2. 120,000 messages from 12,000 customers, one customer sends 30% of them")
msgs = Counter({f"customer-{i}": 7 for i in range(1, 12_001)})        # 84,000 ordinary messages
msgs["customer-7"] += 36_000                                            # customer-7: 7 + 36,000 = 36,007
total = sum(msgs.values())
loads = [0] * n
for k, cnt in msgs.items():
    loads[to_positive(murmur2(k.encode())) % n] += cnt
hot_p = to_positive(murmur2(b"customer-7")) % n
print(f"   total {total:,} messages, mean per partition {total / n:,.0f}")
print(f"   customer-7 goes to partition {hot_p}; that partition holds {loads[hot_p]:,} = {loads[hot_p] / (total / n):.2f} x the mean")
print(f"   all partitions: {loads}")

print("\nPart 3. Keys that change partition when a topic grows")
keys = [f"customer-{i}" for i in range(1, 120_001)]
hs = [to_positive(murmur2(k.encode())) for k in keys]
for a, b in ((12, 13), (12, 24), (12, 18), (6, 12)):
    moved = sum(1 for h in hs if h % a != h % b)
    predicted = 1 - min(a, b) / math.lcm(a, b)          # 9.3 step 5: a key stays iff h mod lcm < min(a, b)
    print(f"   {a:>2} -> {b:>2} partitions: {moved / len(hs):.2%} of the keys move; predicted 1 - {min(a, b)}/{math.lcm(a, b)} = {predicted:.2%}")
