# Tech by Math, pilot: Spark's hash() of an int, recomputed by hand in plain Python.
# MurmurHash3 x86_32 for one 4-byte block (Spark's Murmur3_x86_32.hashInt), seed 42.
# Compare with the hash column printed by ex01_spark_partitions.py.
M32 = 0xFFFFFFFF
C1, C2 = 0xCC9E2D51, 0x1B873593

def rotl(x, r):
    return ((x << r) | (x >> (32 - r))) & M32

def murmur3_int(value, seed=42):
    k1 = value & M32                       # the int's 32 bits
    k1 = (k1 * C1) & M32
    k1 = rotl(k1, 15)
    k1 = (k1 * C2) & M32
    h1 = seed ^ k1
    h1 = rotl(h1, 13)
    h1 = (h1 * 5 + 0xE6546B64) & M32
    h1 ^= 4                                # length in bytes
    h1 ^= h1 >> 16                         # final mix
    h1 = (h1 * 0x85EBCA6B) & M32
    h1 ^= h1 >> 13
    h1 = (h1 * 0xC2B2AE35) & M32
    h1 ^= h1 >> 16
    return h1 - (1 << 32) if h1 >= (1 << 31) else h1   # read as a signed 32-bit int, as Java does

def pmod(a, n):
    return ((a % n) + n) % n               # Python's % is already non-negative for n > 0

if __name__ == "__main__":
  for cid in range(1, 9):
    h = murmur3_int(cid)
    print(f"customer {cid}: hash = {h:>11}, pmod(hash, 3) = {pmod(h, 3)}, pmod(hash, 8) = {pmod(h, 8)}")
  print("Java-style remainder of -559580957 by 3:", -(559580957 % 3), "-> pmod adds 3 ->", pmod(-559580957, 3))
