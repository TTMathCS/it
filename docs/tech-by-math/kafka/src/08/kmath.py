# Kafka's key -> partition rule, written in Python from Kafka 4.3.2's source:
#   Utils.murmur2 (clients/src/main/java/org/apache/kafka/common/utils/Utils.java)
#   BuiltInPartitioner.partitionForKey = Utils.toPositive(Utils.murmur2(serializedKey)) % numPartitions
M32 = 0xFFFFFFFF


def to_int32(x):
    x &= M32
    return x - (1 << 32) if x & 0x80000000 else x


def murmur2(data: bytes) -> int:
    length = len(data)
    m, r = 0x5BD1E995, 24
    h = (0x9747B28C ^ length) & M32
    for i in range(length // 4):
        k = int.from_bytes(data[4 * i:4 * i + 4], "little")
        k = (k * m) & M32
        k ^= k >> r
        k = (k * m) & M32
        h = (h * m) & M32
        h ^= k
    rest = length % 4
    idx = length - rest
    if rest == 3:
        h ^= data[idx + 2] << 16
    if rest >= 2:
        h ^= data[idx + 1] << 8
    if rest >= 1:
        h ^= data[idx]
        h = (h * m) & M32
    h ^= h >> 13
    h = (h * m) & M32
    h ^= h >> 15
    return to_int32(h)


def to_positive(n: int) -> int:
    return n & 0x7FFFFFFF


def partition_for_key(key: str, num_partitions: int) -> int:
    """A String key, serialized as UTF-8 bytes (Kafka's StringSerializer default)."""
    return to_positive(murmur2(key.encode("utf-8"))) % num_partitions
