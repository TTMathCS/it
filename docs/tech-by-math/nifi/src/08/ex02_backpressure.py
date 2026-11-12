# Back pressure on one connection, simulated second by second.
# A source makes 300 FlowFiles a second; the next processor handles 200.
# NiFi does not schedule the source while its outgoing queue is full
# (10,000 FlowFiles or 1 GB, whichever comes first: AbstractFlowFileQueue.isFull).
from collections import deque
from nifi_math import is_full

print("Part 1. Which threshold trips first?")
GiB = 1024 ** 3
print(f"   1 GB in NiFi = 1024^3 = {GiB:,} bytes; / 10,000 FlowFiles = {GiB / 10_000:,.1f} bytes each")
for size in (2_000, 100_000, 200_000, 500_000, 5_000_000):
    n = 0
    while not is_full(n, n * size):
        n += 1
    which = "count" if n == 10_000 else "size"
    print(f"   FlowFiles of {size:>9,} bytes: full at {n:>6,} FlowFiles ({which} threshold)")

print()
print("Part 2. Source 300/s, processor 200/s, queue threshold 10,000 FlowFiles of 1 KB")
IN, OUT, SIZE = 300, 200, 1024
q = deque()                     # each entry: the second it was queued
done_waits, first_full, peak = [], None, 0
for t in range(0, 400):
    if not is_full(len(q), len(q) * SIZE):         # checked before the source runs
        for _ in range(IN):
            q.append(t)
    peak = max(peak, len(q))
    if first_full is None and is_full(len(q), len(q) * SIZE):
        first_full = t
    for _ in range(min(OUT, len(q))):
        done_waits.append(t - q.popleft())
    if t in (0, 1, 50, 98, 99, 100, 101, 102, 103, 200, 399):
        print(f"   t = {t:>3} s: queue after the processor runs {len(q):>6,}")
print(f"   first full at t = {first_full} s; by hand about 10,000 / (300 - 200) = 100 s (a little sooner here,")
print(f"   because each second the 300 arrive before the 200 leave)")
print(f"   highest queue {peak:,}: the limit is checked before a run, so one run can pass it")
late = done_waits[-200 * 100:]
print(f"   throughput once throttled: {OUT}/s; wait of the last 20,000 FlowFiles: about {sum(late)/len(late):.1f} s")
print(f"   Little's law: wait = queue / throughput = 10,000 / 200 = {10_000 / 200:.0f} s")
