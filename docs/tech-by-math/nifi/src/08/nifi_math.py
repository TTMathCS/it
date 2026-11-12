# NiFi's arithmetic, ported from its source code (Apache NiFi, main branch).
M64 = (1 << 64) - 1

def java_string_hash(s: str) -> int:
    """Java's String.hashCode: s[0]*31^(n-1) + ... + s[n-1], kept to a signed 32-bit int."""
    h = 0
    for unit in s.encode("utf-16-be").hex(" ", 2).split():   # Java hashes UTF-16 code units
        h = (31 * h + int(unit, 16)) & 0xFFFFFFFF
    return h - (1 << 32) if h & 0x80000000 else h

def find_index(hash_value: int, partitions: int) -> int:
    """CorrelationAttributePartitioner.findIndex: Guava's consistentHash (jump hashing)."""
    state = hash_value & M64                       # the int widened to a Java long
    candidate = 0
    while True:
        state = (2862933555777941757 * state + 1) & M64
        next_double = ((state >> 33) + 1) / 2.0 ** 31
        nxt = int((candidate + 1) / next_double)
        if 0 <= nxt < partitions:
            candidate = nxt
        else:
            return candidate

def partition_for(value, partitions):
    """Partition by attribute: a missing attribute hashes to 0."""
    return find_index(0 if value is None else java_string_hash(value), partitions)

def backoff_ms(retry_count, max_backoff_ms, base_ms):
    """StandardProcessSession.calculateBackoffTime."""
    return int(min(max_backoff_ms, 2 ** retry_count * base_ms))

def is_full(count, nbytes, max_count=10_000, max_bytes=1024 ** 3):
    """AbstractFlowFileQueue.isFull, with the defaults 10,000 FlowFiles and 1 GB (1024^3 bytes)."""
    return (max_count > 0 and count >= max_count) or (max_bytes > 0 and nbytes >= max_bytes)
