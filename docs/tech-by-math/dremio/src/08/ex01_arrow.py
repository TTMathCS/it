# Arrow's column layout, counted by hand and checked with pyarrow.
# Rules (Arrow Columnar Format spec): a validity bitmap of ceil(n/8) bytes,
# bit j of byte j//8 says whether slot j is valid; fixed-width values take
# n * width bytes; strings take n+1 int32 offsets plus their UTF-8 bytes.
# Buffers are padded to a multiple of 8 or 64 bytes (64 recommended).
import math
import pyarrow as pa

def pad(n, to=64):
    return (n + to - 1) // to * to

print("Part 1. The spec's own example: ['joe', None, None, 'mark']")
a = pa.array(["joe", None, None, "mark"])
validity, offsets, data = a.buffers()
print("   validity byte 0:", format(validity.to_pybytes()[0], "08b"), "(bit j from the right is slot j)")
print("   offsets        :", list(memoryview(offsets).cast("i")[:5]))
print("   value bytes    :", data.to_pybytes()[:7])

print()
print("Part 2. One million int32 values, 1 in 10 null")
n = 1_000_000
vals = [None if i % 10 == 0 else i for i in range(n)]
a = pa.array(vals, type=pa.int32())
bm, d = a.buffers()
print(f"   by hand: bitmap ceil({n:,}/8) = {math.ceil(n/8):,} bytes, data {n:,} x 4 = {4*n:,} bytes")
print(f"   pyarrow: bitmap {bm.size:,} bytes, data {d.size:,} bytes, null_count {a.null_count:,}")
print(f"   padded to 64: bitmap {pad(math.ceil(n/8)):,}, data {pad(4*n):,}")
print(f"   the bitmap costs {math.ceil(n/8)/(4*n):.1%} of the data")
# check the bit rule on a few slots
bits = bm.to_pybytes()
for j in (0, 1, 9, 10, 11):
    v = (bits[j // 8] >> (j % 8)) & 1
    print(f"   slot {j:>2}: bit {v}  (value {vals[j]})")

print()
print("Part 3. Strings: offsets + bytes")
words = ["Toronto", "Ottawa", None, "Montréal", "Québec"]
a = pa.array(words)
bm, off, data = a.buffers()
utf8 = sum(len(w.encode()) for w in words if w)
print("   offsets:", list(memoryview(off).cast("i")[:len(words)+1]))
print(f"   by hand: offsets ({len(words)}+1) x 4 = {(len(words)+1)*4} bytes, data {utf8} bytes (é is 2 bytes in UTF-8)")
print(f"   pyarrow: data buffer {data.size} bytes")

print()
print("Part 4. Padding as written by Arrow IPC (the format Arrow Flight sends)")
for n in (1, 7, 8, 100, 1000):
    batch = pa.record_batch([pa.array(range(n), type=pa.int32())], names=["x"])
    msg = pa.ipc.read_message(batch.serialize())
    print(f"   n={n:>5}: data {4*n:>5} bytes, by hand padded to 8 -> {pad(4*n, 8):>5}, to 64 -> {pad(4*n):>5};"
          f" pyarrow IPC body {msg.body.size:>5}")

print()
print("Part 5. Column pruning: a query that uses 3 of 40 int64 columns of 2 billion rows")
rows, cols, used = 2_000_000_000, 40, 3
per_col = rows * 8
print(f"   one column: {per_col/1e9:.0f} GB; all {cols}: {cols*per_col/1e9:.0f} GB; the {used} used: {used*per_col/1e9:.0f} GB ({used/cols:.1%})")
