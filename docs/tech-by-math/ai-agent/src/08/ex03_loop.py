# The agent loop as an absorbing Markov chain: Think -> Act (call a tool) -> Check,
# then Done, back to Think, or Give up. Expected steps and the chance of success
# from the fundamental matrix N = (I - Q)^-1, checked by simulation.
import numpy as np
import random
np.set_printoptions(suppress=True, precision=4)

states = ["Think", "Act", "Check"]          # transient
ends = ["Done", "GiveUp"]                   # absorbing
Q = np.array([[0, 1, 0],                    # Think -> Act
              [0, 0, 1],                    # Act -> Check
              [0.45, 0, 0]])                # Check -> Think (try again)
R = np.array([[0, 0],
              [0, 0],
              [0.50, 0.05]])                # Check -> Done, Check -> GiveUp
N = np.linalg.inv(np.eye(3) - Q)
print("Part 1. Fundamental matrix N = (I - Q)^-1 (expected visits to each state, starting from each state)")
print(N)
t = N @ np.ones(3)
B = N @ R
print(f"   expected steps from Think: {t[0]:.4f}   (by hand: 3 steps a round, 1 / 0.55 = {1/0.55:.4f} rounds, {3/0.55:.4f} steps)")
print(f"   chance of ending in Done: {B[0, 0]:.4f}, in GiveUp: {B[0, 1]:.4f}   (by hand: 0.50 / 0.55 = {0.5/0.55:.4f})")

print()
print("Part 2. A step budget: stop after at most m rounds of 3 steps")
for m in (1, 2, 3, 4, 6, 10):
    exact = 0.5 * (1 - 0.45 ** m) / 0.55
    print(f"   {m:>2} rounds ({3 * m:>2} steps): Done with chance {exact:.4f}")

print()
print("Part 3. Simulation, 200,000 runs, no budget")
rng = random.Random(5)
steps_total, done, done12 = 0, 0, 0
for _ in range(200_000):
    s, steps = "Think", 0
    while True:
        steps += 1
        if s == "Think":
            s = "Act"
        elif s == "Act":
            s = "Check"
        else:
            r = rng.random()
            if r < 0.50:
                done += 1; done12 += steps <= 12; break
            elif r < 0.55:
                break
            s = "Think"
    steps_total += steps
print(f"   average steps {steps_total / 200_000:.4f}, Done {done / 200_000:.4f}, Done within 12 steps {done12 / 200_000:.4f}")
