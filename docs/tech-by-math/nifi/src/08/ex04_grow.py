# E8: as a cluster grows from 1 to 6 nodes, what fraction of keys moves at each step,
# and where do they go?
from nifi_math import partition_for

keys = [f"order-{i}" for i in range(60_000)]
prev = [partition_for(k, 1) for k in keys]
for n in range(2, 7):
    cur = [partition_for(k, n) for k in keys]
    moved = [(a, b) for a, b in zip(prev, cur) if a != b]
    to_new = all(b == n - 1 for a, b in moved)
    print(f"   {n - 1} -> {n} nodes: {len(moved):>6,} keys moved ({len(moved)/len(keys):.1%}, ideal 1/{n} = {1/n:.1%}); all to the new node: {to_new}")
    prev = cur
print("   'Ab' and 'BC' hash alike:", partition_for("Ab", 5) == partition_for("BC", 5))
