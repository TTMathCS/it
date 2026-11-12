# Iceberg's partition transforms, ported from the table spec and checked
# against the spec's own test values (Appendix B).
#   bucket[N](x)   = (murmur3_x86_32(x) & Integer.MAX_VALUE) % N
#   truncate[W](v) = v - (((v % W) + W) % W)
#   day(ts)        = days since 1970-01-01
import datetime as dt
import uuid
from decimal import Decimal

def murmur3_32(data: bytes, seed=0):
    c1, c2, M = 0xCC9E2D51, 0x1B873593, 0xFFFFFFFF
    rotl = lambda x, r: ((x << r) | (x >> (32 - r))) & M
    h = seed
    n4 = len(data) // 4
    for i in range(n4):
        k = int.from_bytes(data[4 * i:4 * i + 4], "little")
        k = rotl((k * c1) & M, 15) * c2 & M
        h = (rotl(h ^ k, 13) * 5 + 0xE6546B64) & M
    tail, k = data[4 * n4:], 0
    if len(tail) >= 3:
        k ^= tail[2] << 16
    if len(tail) >= 2:
        k ^= tail[1] << 8
    if len(tail) >= 1:
        k ^= tail[0]
        h ^= rotl((k * c1) & M, 15) * c2 & M
    h ^= len(data)
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & M
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & M
    h ^= h >> 16
    return h - (1 << 32) if h & 0x80000000 else h   # as a signed Java int

def hash_long(v):            # int, long, time, timestamp: 8 bytes little-endian
    return murmur3_32(v.to_bytes(8, "little", signed=True))

def min_big_endian(v):       # fewest two's-complement bytes that hold v
    n = 1
    while not -(1 << (8 * n - 1)) <= v < (1 << (8 * n - 1)):
        n += 1
    return v.to_bytes(n, "big", signed=True)

EPOCH = dt.datetime(1970, 1, 1)
def micros(ts):
    d = ts - EPOCH
    return (d.days * 86_400 + d.seconds) * 1_000_000 + d.microseconds

def bucket(h, n):
    return (h & 0x7FFFFFFF) % n

def truncate(v, w):
    return v - (((v % w) + w) % w)

def day(ts):
    return (ts.date() - EPOCH.date()).days

if __name__ == "__main__":
    print("Part 1. The spec's test values (Appendix B)")
    tests = [
        ("int 34 (hashed as a long)", hash_long(34), 2017239379),
        ("long 34L", hash_long(34), 2017239379),
        ("decimal 14.20 (unscaled 1420)", murmur3_32(min_big_endian(int(Decimal("14.20") * 100))), -500754589),
        ("date 2017-11-16", hash_long((dt.date(2017, 11, 16) - dt.date(1970, 1, 1)).days), -653330422),
        ("time 22:31:08", hash_long((22 * 3600 + 31 * 60 + 8) * 1_000_000), -662762989),
        ("timestamp 2017-11-16T22:31:08", hash_long(micros(dt.datetime(2017, 11, 16, 22, 31, 8))), -2047944441),
        ("timestamp ...22:31:08.000001", hash_long(micros(dt.datetime(2017, 11, 16, 22, 31, 8, 1))), -1207196810),
        ("string 'iceberg'", murmur3_32("iceberg".encode()), 1210000089),
        ("uuid f79c3e09-...", murmur3_32(uuid.UUID("f79c3e09-677c-4bbd-a479-3f349cb785e7").bytes), 1488055340),
        ("binary 00 01 02 03", murmur3_32(bytes([0, 1, 2, 3])), -188683207),
        ("string '34' (not the same as int 34)", murmur3_32(b"34"), -427558391),
    ]
    for name, got, want in tests:
        print(f"   {name:<38} {got:>12}  spec {want:>12}  {'ok' if got == want else 'DIFFERENT'}")

    print()
    print("Part 2. bucket[16] of customer ids, by hand for 34")
    h = hash_long(34)
    print(f"   hash 34 = {h}; & 0x7FFFFFFF = {h & 0x7FFFFFFF}; % 16 = {bucket(h, 16)}")
    counts = [0] * 16
    for cid in range(1, 100_001):
        counts[bucket(hash_long(cid), 16)] += 1
    print(f"   100,000 ids 1..100,000 into 16 buckets: fewest {min(counts):,}, most {max(counts):,}, ideal {100_000 // 16:,}")
    h = hash_long(-7)
    print(f"   a negative hash: id -7 -> hash {h}, & 0x7FFFFFFF = {h & 0x7FFFFFFF}, % 16 = {bucket(h, 16)}")

    print()
    print("Part 3. truncate[W]: the remainder must not be negative")
    for v, w in [(1, 10), (-1, 10), (37, 10), (-37, 10), (1234, 100)]:
        naive = v - int(__import__("math").fmod(v, w))
        print(f"   truncate[{w}]({v:>5}) = {truncate(v, w):>5}   (C/Java-style v - v%W would give {naive:>5})")
    print("   spec examples: W=10: 1 -> 0, -1 -> -10;  W=50 on 10.65 (scale 2): ", end="")
    print(f"{truncate(1065, 50) / 100:.2f}")

    print()
    print("Part 4. day(ts): days since 1970-01-01")
    for ts in [dt.datetime(1970, 1, 2, 0, 0), dt.datetime(2017, 11, 16, 22, 31, 8), dt.datetime(2026, 11, 12, 9, 0)]:
        print(f"   {ts}  ->  day {day(ts):,}")
