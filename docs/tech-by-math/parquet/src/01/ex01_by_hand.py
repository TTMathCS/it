# Tech by Math, tutorial 5: checks the by-hand work of 5.3. Dictionary coding, run-length coding and bit-packing of a
# 12-value column, the same column sorted, and min/max skipping over row groups of 3 rows.
import math

city = ["Oslo", "Oslo", "Oslo", "Lagos", "Lagos", "Toronto", "Toronto", "Toronto", "Toronto", "Oslo", "Oslo", "Lagos"]


def runs(values):
    out = []
    for v in values:
        if out and out[-1][0] == v:
            out[-1][1] += 1
        else:
            out.append([v, 1])
    return out


def report(name, values):
    dictionary = sorted(set(values))
    codes = [dictionary.index(v) for v in values]
    bits = max(1, math.ceil(math.log2(len(dictionary))))
    plain = sum(len(v) for v in values)
    r = runs(codes)
    print(f"{name}: {values}")
    print(f"   plain text: {plain} bytes = {plain * 8} bits")
    print(f"   dictionary {dict(enumerate(dictionary))}; codes {codes}")
    print(f"   bit-packed codes: {len(values)} x {bits} bits = {len(values) * bits} bits")
    print(f"   runs (code, length): {[tuple(x) for x in r]} -> {len(r)} runs; value changes: "
          f"{sum(a != b for a, b in zip(codes, codes[1:]))}")


report("as written", city)
report("sorted", sorted(city))

# Entropy of the column: the fewest bits per value any code can average, for values drawn with these frequencies
freq = {v: city.count(v) / len(city) for v in set(city)}
H = -sum(p * math.log2(p) for p in freq.values())
print(f"   entropy of the column's frequencies {freq}: {H:.3f} bits per value, {H * len(city):.1f} bits for 12 values")

# min/max skipping: 12 days of sales, 4 row groups of 3 rows
day = [5, 1, 9, 2, 12, 7, 3, 11, 6, 8, 4, 10]
for name, values in (("days as loaded", day), ("days sorted", sorted(day))):
    groups = [values[i:i + 3] for i in range(0, 12, 3)]
    print(f"\n{name}: groups {groups}")
    print("   min/max per group:", [(min(g), max(g)) for g in groups])
    for lo, hi in ((7, 7), (10, 12)):
        read = [k for k, g in enumerate(groups) if not (max(g) < lo or min(g) > hi)]
        hits = [k for k, g in enumerate(groups) if any(lo <= x <= hi for x in g)]
        print(f"   WHERE day BETWEEN {lo} AND {hi}: must read groups {read}, groups that really hold a match {hits}")
