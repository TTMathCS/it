# E8: doubling the bucket count splits each bucket in two.
# bucket[16](x) is always bucket[32](x) mod 16, because 16 divides 32.
from ex02_iceberg import hash_long, bucket

moved = {}
for cid in range(1, 100_001):
    h = hash_long(cid)
    b16, b32 = bucket(h, 16), bucket(h, 32)
    assert b32 % 16 == b16
    moved.setdefault(b16, set()).add(b32)
print("bucket[32] mod 16 == bucket[16] for all 100,000 ids: True")
for b in (0, 3, 15):
    print(f"   ids in bucket {b:>2} of 16 went to buckets {sorted(moved[b])} of 32")
# with 24 buckets (16 does not divide 24) a bucket of 16 scatters
scatter = {}
for cid in range(1, 100_001):
    h = hash_long(cid)
    scatter.setdefault(bucket(h, 16), set()).add(bucket(h, 24))
print(f"   with 24 buckets instead, bucket 3 of 16 spreads over {len(scatter[3])} of the 24")
