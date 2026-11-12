# Partition by attribute: Java's String.hashCode, then jump consistent hashing.
from nifi_math import java_string_hash, find_index, partition_for

print("Part 1. Guava's own test values for consistentHash")
golden100 = [0, 55, 62, 8, 45, 59, 86, 97, 82, 59, 73, 37, 17, 56, 86, 21, 90, 37, 38, 83]
got = [find_index(i, 100) for i in range(20)]
print("   inputs 0..19, 100 buckets:", got, "ok" if got == golden100 else "DIFFERENT")
for key, n, want in [(10863919174838991, 11, 6), (2016238256797177309, 11, 3), (1673758223894951030, 11, 5),
                     (2, 100001, 80343), (2201, 100001, 22152), (2202, 100001, 15018)]:
    g = find_index(key, n)
    print(f"   consistentHash({key}, {n}) = {g}  Guava test {want}  {'ok' if g == want else 'DIFFERENT'}")

print()
print("Part 2. NiFi's own test: values '4', '1', '2' over three nodes")
for v, want in [("4", 0), ("1", 1), ("2", 2)]:
    h = java_string_hash(v)
    print(f"   '{v}': hashCode = {h} (the character code), partition {partition_for(v, 3)}  NiFi test expects {want}")
print(f"   no attribute: hash 0, partition {partition_for(None, 3)}")

print()
print("Part 2b. The jumps for '1' (hash 49): each step draws r in (0, 1] and jumps to floor((candidate + 1) / r)")
M64 = (1 << 64) - 1
state, cand = 49, 0
while True:
    state = (2862933555777941757 * state + 1) & M64
    r = ((state >> 33) + 1) / 2.0 ** 31
    nxt = int((cand + 1) / r)
    print(f"   candidate {cand}: r = {r:.6f}, (candidate + 1) / r = {(cand + 1) / r:,.3f} -> {nxt}", end="")
    if nxt < 3:
        print("  (below 3: jump)")
        cand = nxt
    else:
        print(f"  (3 or more: stop at {cand})")
        break
for n in (4, 5, 6, 10):
    print(f"   with {n} nodes the same key goes to {find_index(49, n)}")

print()
print("Part 3. String.hashCode by hand")
for s in ["ab", "east", "Aa", "BB"]:
    print(f"   '{s}': {java_string_hash(s)}")
print("   'ab' = 97 x 31 + 98 = 3105;  'Aa' = 65 x 31 + 97 = 2112 = 66 x 31 + 66 = 'BB'")

print()
print("Part 4. 30,000 customer ids over 3 nodes, then a 4th node joins")
keys = [f"cust-{i}" for i in range(30_000)]
p3 = [partition_for(k, 3) for k in keys]
p4 = [partition_for(k, 4) for k in keys]
print("   on 3 nodes:", [p3.count(i) for i in range(3)])
print("   on 4 nodes:", [p4.count(i) for i in range(4)])
moved = sum(a != b for a, b in zip(p3, p4))
print(f"   jump hash: {moved:,} keys moved ({moved/len(keys):.1%}), every one of them to the new node: {all(b == 3 for a, b in zip(p3, p4) if a != b)}")
m3 = [java_string_hash(k) % 3 for k in keys]
m4 = [java_string_hash(k) % 4 for k in keys]
mm = sum(a != b for a, b in zip(m3, m4))
print(f"   plain hash mod n, for comparison: {mm:,} keys moved ({mm/len(keys):.1%})")
