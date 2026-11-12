# An aggregation reflection, built by hand: group the raw rows by the
# dimensions (region, and the order time cut to a DATE, Dremio's default
# granularity for a timestamp dimension) and keep the measures Dremio
# offers: SUM, COUNT, MIN, MAX and an approximate distinct count (a
# HyperLogLog sketch). Then answer queries from it and compare with the raw rows.
# The sketch here is a textbook HyperLogLog with 2^12 registers, the same
# register count as Dremio's (lgConfigK = 12); it is not Dremio's code.
import datetime as dt
import hashlib
import math
import random
from collections import defaultdict

random.seed(2026)
REGIONS = ["North", "South", "East", "West", "Centre", "Coast", "Lakes", "Hills"]
START = dt.datetime(2025, 1, 1)
customers = {c: random.choice(REGIONS) for c in range(1, 30_001)}   # each customer lives in one region
orders = []
for _ in range(200_000):
    c = random.randint(1, 30_000)
    ts = START + dt.timedelta(seconds=random.randrange(365 * 86_400))
    cents = random.randint(500, 50_000)
    orders.append((customers[c], ts, c, cents))

P = 12
M = 1 << P
def h64(c):
    return int.from_bytes(hashlib.blake2b(str(c).encode(), digest_size=8).digest(), "big")
def hll_add(reg, c):
    x = h64(c)
    idx = x >> (64 - P)                          # first 12 bits pick the register
    rest = x & ((1 << (64 - P)) - 1)
    rank = (64 - P) - rest.bit_length() + 1     # leading zeros in the other 52 bits, plus 1
    if rank > reg[idx]:
        reg[idx] = rank
def hll_merge(a, b):
    return bytearray(max(x, y) for x, y in zip(a, b))
def hll_estimate(reg):
    alpha = 0.7213 / (1 + 1.079 / M)
    e = alpha * M * M / sum(2.0 ** -r for r in reg)
    zeros = reg.count(0)
    if e <= 2.5 * M and zeros:
        e = M * math.log(M / zeros)              # small counts: linear counting
    return e

# build the reflection
refl = {}
for region, ts, c, cents in orders:
    key = (region, ts.date())
    r = refl.get(key)
    if r is None:
        r = refl[key] = {"sum": 0, "count": 0, "min": cents, "max": cents, "hll": bytearray(M), "exact": set()}
    r["sum"] += cents
    r["count"] += 1
    r["min"] = min(r["min"], cents)
    r["max"] = max(r["max"], cents)
    hll_add(r["hll"], c)
    r["exact"].add(c)                            # kept only to show the wrong way below

print("Part 1. Size")
print(f"   raw rows: {len(orders):,}; reflection rows: {len(refl):,}; at most {len(REGIONS)} regions x 365 days = {len(REGIONS)*365:,}")

print()
print("Part 2. Revenue, orders, average and largest order per region: raw rows vs the reflection")
raw = defaultdict(lambda: {"sum": 0, "count": 0, "max": 0, "cust": set()})
for region, ts, c, cents in orders:
    g = raw[region]; g["sum"] += cents; g["count"] += 1; g["max"] = max(g["max"], cents); g["cust"].add(c)
roll = defaultdict(lambda: {"sum": 0, "count": 0, "max": 0, "days_avg": [], "hll": bytearray(M), "sum_daily_distinct": 0})
for (region, day), r in refl.items():
    g = roll[region]
    g["sum"] += r["sum"]; g["count"] += r["count"]; g["max"] = max(g["max"], r["max"])
    g["days_avg"].append(r["sum"] / r["count"])
    g["hll"] = hll_merge(g["hll"], r["hll"])
    g["sum_daily_distinct"] += len(r["exact"])
ok = True
for region in REGIONS:
    a, b = raw[region], roll[region]
    same = a["sum"] == b["sum"] and a["count"] == b["count"] and a["max"] == b["max"]
    ok &= same
    avg_raw = a["sum"] / a["count"] / 100
    avg_refl = b["sum"] / b["count"] / 100
    avg_wrong = sum(b["days_avg"]) / len(b["days_avg"]) / 100
    print(f"   {region:<6} revenue ${a['sum']/100:>13,.2f}  orders {a['count']:>6,}  max ${a['max']/100:>7,.2f}"
          f"  avg ${avg_raw:,.4f} = sum/count ${avg_refl:,.4f}; mean of daily averages ${avg_wrong:,.4f}")
print(f"   sums, counts and maxima equal the raw answer exactly: {ok}")

print()
print("Part 3. Distinct customers per region")
errs = []
for region in REGIONS:
    exact = len(raw[region]["cust"])
    est = hll_estimate(roll[region]["hll"])
    wrong = roll[region]["sum_daily_distinct"]
    errs.append(abs(est - exact) / exact)
    print(f"   {region:<6} exact {exact:>5,}  sum of daily distinct counts {wrong:>6,} (wrong)  merged sketch {est:>8,.0f} ({(est-exact)/exact:+.2%})")
print(f"   sketch: {M:,} registers; textbook standard error 1.04/sqrt({M:,}) = {1.04/math.sqrt(M):.2%}; largest error here {max(errs):.2%}")
