# How reliability compounds over the steps of an agent's task, with and without checks.
# Exact formulas, then a seeded simulation of the same model.
import random

def chain(p, n):
    return p ** n

def step_with_checks(p, d, k):
    """One step, up to k attempts. Each attempt is right with chance p; a wrong
    attempt is caught by the check with chance d (then retried) or slips through."""
    return p * sum(((1 - p) * d) ** j for j in range(k))

print("Part 1. Every step must be right: P = p^n")
for p in (0.99, 0.95, 0.90):
    print(f"   p = {p}: " + ", ".join(f"n={n}: {chain(p, n):.3f}" for n in (1, 5, 10, 20, 50)))

print()
print("Part 2. Checks and retries (p = 0.95 per attempt, 20 steps)")
for d, k in [(0.0, 1), (1.0, 3), (0.9, 3), (0.5, 3), (0.9, 10)]:
    s = step_with_checks(0.95, d, k)
    print(f"   check catches {d:.0%} of errors, up to {k:>2} attempts: one step {s:.5f}, 20 steps {s ** 20:.4f}")

lim = 0.95 / (1 - 0.05 * 0.9)
print(f"   unlimited attempts, check catches 90%: p / (1 - (1 - p) d) = {lim:.5f}; 20 steps {lim ** 20:.4f}")

print()
print("Part 3. Simulation of part 2, 200,000 tasks each")
rng = random.Random(8)
def simulate(p, d, k, n, tasks=200_000):
    ok = 0
    for _ in range(tasks):
        good = True
        for _ in range(n):
            for attempt in range(k):
                if rng.random() < p:
                    break                      # right: next step
                if rng.random() < d and attempt < k - 1:
                    continue                   # caught: try again
                good = False                   # slipped through, or out of attempts
                break
            if not good:
                break
        ok += good
    return ok / tasks
for d, k in [(0.0, 1), (1.0, 3), (0.9, 3)]:
    print(f"   d = {d}, k = {k}: formula {step_with_checks(0.95, d, k) ** 20:.4f}, simulated {simulate(0.95, d, k, 20):.4f}")
