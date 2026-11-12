# Skipping files by their min/max statistics (Iceberg keeps a lower and an
# upper bound per column per data file). A file can be skipped when its
# range [min, max] cannot contain a row that matches the filter.
import math
import random

def overlaps(lo, hi, qlo, qhi):        # file range vs query range, both inclusive
    return not (hi < qlo or lo > qhi)

print("Part 1. Six files and the filter amount BETWEEN 900 AND 1000")
files = [("f1", 5, 480), ("f2", 120, 870), ("f3", 400, 950), ("f4", 990, 1500), ("f5", 1010, 2000), ("f6", 30, 899)]
read = []
for name, lo, hi in files:
    keep = overlaps(lo, hi, 900, 1000)
    read.append(keep)
    print(f"   {name}: min {lo:>5}, max {hi:>5}  ->  {'read' if keep else 'skip'}")
print(f"   read {sum(read)} of {len(files)}")

print()
print("Part 2. The same 1,000,000 rows in 100 files of 10,000, filter x >= 0.99")
random.seed(8)
rows = [random.random() for _ in range(1_000_000)]
def files_read(values, per_file, qlo, qhi):
    n = 0
    for i in range(0, len(values), per_file):
        chunk = values[i:i + per_file]
        n += overlaps(min(chunk), max(chunk), qlo, qhi)
    return n
print(f"   rows in arrival order : read {files_read(rows, 10_000, 0.99, 1.0):>3} of 100 files")
s = sorted(rows)
print(f"   rows sorted by x      : read {files_read(s, 10_000, 0.99, 1.0):>3} of 100 files")
print(f"   rows that match       : {sum(x >= 0.99 for x in rows):,} ({sum(x >= 0.99 for x in rows)/len(rows):.2%})")

print()
print("Part 3. Chance a random file of k rows can be skipped for x >= 0.9: all k rows below 0.9, 0.9^k")
for k in (1, 5, 10, 20, 50, 100, 10_000):
    sim = 0
    trials = 20_000 if k <= 100 else 200
    for _ in range(trials):
        sim += max(random.random() for _ in range(k)) < 0.9
    f = f"{0.9**k:.3g}" if k <= 1000 else f"10^{k * math.log10(0.9):.0f} (too small for a float)"
    print(f"   k = {k:>6}: formula {f}   simulated {sim/trials:.3g} ({trials:,} trials)")

print()
print("Part 4. Partitions by day: a table of 365 daily partitions, a query for 7 days")
total_files = 365 * 40
print(f"   365 days x 40 files a day = {total_files:,} files; the 7 days hold {7*40} files = {7/365:.1%} of the table")
