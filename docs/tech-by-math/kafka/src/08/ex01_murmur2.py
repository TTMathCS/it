# Tech by Math, Kafka tutorial 8: Kafka's murmur2 in Python, checked against the test vectors in
# Kafka 4.3.2's UtilsTest.testMurmur2, then the partitions of a few keys.
from kmath import murmur2, to_positive, partition_for_key, to_int32

cases = {b"21": -973932308, b"foobar": -790332482, b"a-little-bit-long-string": -985981536,
         b"a-little-bit-longer-string": -1486304829,
         b"lkjh234lh9fiuh90y23oiuhsafujhadof229phr9h19h89h8": -58897971, b"abc": 479470107}
print("Kafka's own test vectors:")
for k, want in cases.items():
    got = murmur2(k)
    print(f"   murmur2({k.decode()!r:<52}) = {got:>12}  expected {want:>12}  {'ok' if got == want else 'DIFFERENT'}")
assert all(murmur2(k) == v for k, v in cases.items())

print("\ntoPositive keeps the low 31 bits; it is not the absolute value (Java's Math.abs, on 32-bit ints):")
for h in (-973932308, 479470107, -2147483648):
    print(f"   hash {h:>14,}: toPositive = {to_positive(h):>13,}   Math.abs = {to_int32(abs(h)):>14,}")

print("\nKeys customer-1 .. customer-8 on a topic with 6 partitions:")
for i in range(1, 9):
    key = f"customer-{i}"
    h = murmur2(key.encode())
    print(f"   {key:<11} murmur2 = {h:>12}  toPositive = {to_positive(h):>13,}  mod 6 = {partition_for_key(key, 6)}")
