# Tech by Math, Kafka tutorial 8: the range assignor (as described in Kafka 4.3.2's RangeAssignor.java:
# partitions in numeric order, consumers in name order, p // c each, the first p % c get one extra),
# and how fast a group can read when every partition carries the same traffic. A model, not a broker.
import math


def range_assign(p, consumers):
    consumers = sorted(consumers)
    c = len(consumers)
    each, extra = divmod(p, c)
    out, start = {}, 0
    for i, name in enumerate(consumers):
        n = each + (1 if i < extra else 0)
        out[name] = list(range(start, start + n))
        start += n
    return out


p = 12
print(f"A topic with {p} partitions. One consumer reads R msg/s; each partition receives the same traffic.")
print(f"   {'consumers':>9}  {'partitions per consumer':<50} {'idle':>4}  {'max per consumer':>16}  {'group speed (x R)':>17}")
for c in (1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 16):
    a = range_assign(p, [f"c{i:02d}" for i in range(c)])
    sizes = [len(v) for v in a.values()]
    worst = max(sizes)
    print(f"   {c:>9}  {str(sizes):<50} {sizes.count(0):>4}  {worst:>16}  {p / worst:>17.2f}")
print("\nExample assignment, 12 partitions, 5 consumers:")
for k, v in range_assign(12, ["c00", "c01", "c02", "c03", "c04"]).items():
    print(f"   {k}: {v}")
print("\nDivisors (the consumer counts that divide the partitions evenly):")
for n in (10, 12, 24, 60):
    print(f"   {n:>2} partitions: {[d for d in range(1, n + 1) if n % d == 0]}")
