# Tech by Math, Spark tutorial 9, exercise E8: merging (n, mean, M2) variance summaries.
import random, statistics

def summ(xs):
    n, m = len(xs), sum(xs) / len(xs)
    return n, m, sum((x - m) ** 2 for x in xs)

def merge(a, b):
    na, ma, m2a = a
    nb, mb, m2b = b
    n = na + nb
    d = mb - ma
    return n, ma + d * nb / n, m2a + m2b + d * d * na * nb / n

random.seed(1)
xs = [random.gauss(50, 12) for _ in range(1000)]
cuts = sorted(random.sample(range(1, 1000), 6))
pieces = [xs[i:j] for i, j in zip([0] + cuts, cuts + [1000])]
random.shuffle(pieces)
total = summ(pieces[0])
for p in pieces[1:]:
    total = merge(total, summ(p))
n, mean, m2 = total
print(m2 / (n - 1), statistics.variance(xs))
