# Tech by Math, Elasticsearch tutorial 8: which shard a document goes to. Murmur3 checked against the known
# values in Elasticsearch 9.1's Murmur3HashFunctionTests; then routing and splitting, in Python (no cluster).
from collections import Counter
from lucene_math import es_hash, num_routing_shards, shard_for

known = {"hell": 0x5A0CB7C3, "hello": 0xD7C31989, "hello w": 0x22AB2984, "hello wo": 0xDF0CA123,
         "hello wor": 0xE7744D61, "The quick brown fox jumps over the lazy dog": 0xE07DB09C,
         "The quick brown fox jumps over the lazy cog": 0x4E63D2AD}
print("Elasticsearch's own test values:")
for s, want in known.items():
    got = es_hash(s) & 0xFFFFFFFF
    print(f"   {s!r:<47} {got:#010x}  expected {want:#010x}  {'ok' if got == want else 'DIFFERENT'}")
assert all((es_hash(s) & 0xFFFFFFFF) == v for s, v in known.items())

print("\nnumber_of_routing_shards chosen for an index of n primary shards (n x 2^k, at most 1024):")
print("   " + ", ".join(f"{n} -> {num_routing_shards(n)}" for n in (1, 2, 3, 5, 6, 10, 30)))

h = es_hash("order-1042")
print(f"\nWorked: _id 'order-1042', 5 shards: hash {h}, floorMod(hash, 640) = {h % 640}, / 128 = {h % 640 // 128}")

ids = [f"order-{i}" for i in range(1, 100_001)]
c = Counter(shard_for(x, 5) for x in ids)
print(f"\n100,000 ids on 5 shards: {[c[s] for s in range(5)]}")

pairs = Counter()
for x in ids:
    old = shard_for(x, 5)
    new = shard_for(x, 10, routing_shards=640)    # _split keeps number_of_routing_shards = 640
    pairs[(old, new)] += 1
print("Split 5 -> 10 shards (routing shards stay 640): old shard -> new shards it feeds")
for s in range(5):
    print(f"   shard {s} -> " + ", ".join(f"{n} ({cnt:,} docs)" for (o, n), cnt in sorted(pairs.items()) if o == s))
