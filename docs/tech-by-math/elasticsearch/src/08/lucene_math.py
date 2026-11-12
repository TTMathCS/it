# Lucene 10.3.1's BM25 and length encoding, and Elasticsearch 9.1's shard routing, written in Python from
# their source code: lucene/.../similarities/BM25Similarity.java, lucene/.../util/SmallFloat.java,
# elasticsearch/.../cluster/routing/{Murmur3HashFunction,IndexRouting}.java and
# MetadataCreateIndexService.calculateNumRoutingShards.
import math

# ---- BM25 (Lucene's form: no (k1 + 1) factor; see BM25Similarity.doScore) ----
K1, B = 1.2, 0.75


def idf(n, N):
    return math.log(1 + (N - n + 0.5) / (n + 0.5))


def tf_part(freq, dl, avgdl, k1=K1, b=B):
    return freq / (freq + k1 * (1 - b + b * dl / avgdl))


# ---- SmallFloat.intToByte4 / byte4ToInt: a document length stored in one byte ----
def _long_to_int4(i):
    nbits = i.bit_length()
    if nbits < 4:
        return i
    shift = nbits - 4
    return ((i >> shift) & 0x07) | ((shift + 1) << 3)


def _int4_to_long(i):
    bits, shift = i & 0x07, (i >> 3) - 1
    return bits if shift == -1 else (bits | 0x08) << shift


NUM_FREE_VALUES = 255 - _long_to_int4(2**31 - 1)


def int_to_byte4(i):
    return i if i < NUM_FREE_VALUES else NUM_FREE_VALUES + _long_to_int4(i - NUM_FREE_VALUES)


def byte4_to_int(b):
    return b if b < NUM_FREE_VALUES else NUM_FREE_VALUES + _int4_to_long(b - NUM_FREE_VALUES)


# ---- MurmurHash3 x86_32, seed 0, over the routing string as UTF-16 little-endian bytes ----
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
    return h - (1 << 32) if h & 0x80000000 else h


def es_hash(routing: str):
    return murmur3_32(routing.encode("utf-16-le"))


def num_routing_shards(num_shards):
    log2_shards = (num_shards - 1).bit_length()          # ceil(log2(num_shards))
    return num_shards << max(1, 10 - log2_shards)


def shard_for(routing: str, num_shards, routing_shards=None):
    rs = routing_shards or num_routing_shards(num_shards)
    return (es_hash(routing) % rs) // (rs // num_shards)  # Python % is Java's Math.floorMod for a positive divisor
