# Tech by Math, Kafka tutorial 8, exercise E7: plain keys against salted keys (customer-N:salt), 12 partitions.
from collections import Counter
from kmath import partition_for_key

plain = Counter(partition_for_key(f"customer-{i}", 12) for i in range(1, 100_001))
spread = [len({partition_for_key(f"customer-{i}:{s}", 12) for s in range(4)}) for i in range(1, 1001)]
print(sorted(plain.values()), Counter(spread))
