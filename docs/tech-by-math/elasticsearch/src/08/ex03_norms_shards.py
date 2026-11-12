# Tech by Math, Elasticsearch tutorial 8: (1) Lucene keeps each document's length in one byte, so long lengths
# are rounded; (2) each shard computes idf from its own documents, so one document can score differently
# depending on its shard. Python, with Lucene's formulas from lucene_math.py; no cluster.
from lucene_math import int_to_byte4, byte4_to_int, idf, tf_part

print(f"Part 1. One-byte lengths: exact up to {next(i for i in range(1, 10**6) if byte4_to_int(int_to_byte4(i)) != i) - 1}")
for L in (10, 39, 40, 41, 50, 100, 101, 250, 1000, 1234, 5000):
    b = int_to_byte4(L)
    print(f"   length {L:>5} -> byte {b:>3} -> read back as {byte4_to_int(b):>5}")
worst = max((L - byte4_to_int(int_to_byte4(L))) / L for L in range(1, 100_001))
print(f"   largest relative rounding for lengths 1..100,000: {worst:.1%} (always rounded down)")

print("\nPart 2. The same document on two shards with different statistics, query 'regolith'")
# shard A: 1,000 docs, 10 contain 'regolith'; shard B: 1,000 docs, 200 contain it. avgdl 100 on both.
doc = dict(freq=2, dl=100)
for name, n, N in (("shard A", 10, 1000), ("shard B", 200, 1000), ("whole index (dfs)", 210, 2000)):
    i = idf(n, N)
    print(f"   {name:<18} n = {n:>3}, N = {N:>4}: idf {i:.4f}, score {i * tf_part(doc['freq'], doc['dl'], 100):.4f}")
