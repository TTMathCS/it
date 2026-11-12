# Tech by Math, Kafka tutorial 8: consumer lag, catch-up time and Little's law, in a simulation of one
# partition's log (offsets) and one consumer. This is a model written in Python, not a Kafka broker.
import math
import random
from collections import deque

print("Part 1. Steady rates: lag 1,200,000, producers add 2,000 msg/s, the consumer reads 2,500 msg/s")
log_end, committed = 1_200_000, 0       # offsets: the next offset to write, the next offset to read
lam, mu = 2_000, 2_500
t = 0
while log_end - committed > 0:
    log_end += lam
    committed = min(log_end, committed + mu)
    t += 1
    if t in (1, 60, 600):
        print(f"   after {t:>4} s: log-end offset {log_end:>10,}, committed {committed:>10,}, lag {log_end - committed:>10,}")
print(f"   caught up after {t:,} s; formula L / (mu - lambda) = 1,200,000 / 500 = {1_200_000 // 500:,} s")

print("\nPart 2. Random traffic: Poisson arrivals, 1,000 msg/s on average. Each second the consumer reads up to")
print("        1,250 messages, but in some seconds it reads nothing (busy: garbage collection, a rebalance).")
print("        Little's law check: average lag = arrival rate x average wait.")


def poisson(mean):
    """Poisson draw as a sum of 10 draws by Knuth's method (exact: a sum of Poissons is Poisson)."""
    total = 0
    for _ in range(10):
        limit, k, p = math.exp(-mean / 10), 0, 1.0
        while True:
            p *= random.random()
            if p <= limit:
                break
            k += 1
        total += k
    return total


def run(avail, T=20_000, seed=8):
    random.seed(seed)
    queue = deque()                    # [arrival second, how many] in offset order
    lag_sum = wait_sum = read = arrivals = 0
    for sec in range(T):
        a = poisson(1_000)
        arrivals += a
        if a:
            queue.append([sec, a])
        take = 1_250 if random.random() < avail else 0
        while take and queue:
            s0, c = queue[0]
            k = min(c, take)
            wait_sum += k * (sec - s0)
            read += k
            take -= k
            if k == c:
                queue.popleft()
            else:
                queue[0][1] -= k
        lag_sum += sum(c for _, c in queue)
    lam = arrivals / T
    return lam, lag_sum / T, wait_sum / read


print(f"   {'consumer free':>13} {'capacity/s':>10} {'utilisation':>11} {'average lag':>12} {'average wait':>12} {'lambda x W':>11}")
for avail in (1.0, 0.95, 0.90, 0.85, 0.82):
    lam, lag, w = run(avail)
    print(f"   {avail:>12.0%} {1_250 * avail:>10,.1f} {lam / (1_250 * avail):>11.3f} {lag:>12,.1f} {w:>11.3f}s {lam * w:>11,.1f}")
