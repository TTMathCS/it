# Softmax and temperature: from scores (logits) to probabilities.
import numpy as np
np.set_printoptions(suppress=True)

def softmax(z):
    z = np.asarray(z, dtype=float)
    z = z - z.max()                  # as GPT-2's code does: subtract the largest score first
    e = np.exp(z)
    return e / e.sum()

words = ["Mars", "Earth", "cheese"]
z = np.array([2.0, 1.0, 0.0])
print("Part 1. Scores 2, 1, 0 for", words)
e = np.exp(z)
print(f"   e^2 = {e[0]:.4f}, e^1 = {e[1]:.4f}, e^0 = {e[2]:.4f}, sum {e.sum():.4f}")
print("   probabilities:", np.round(softmax(z), 4))

print()
print("Part 2. Temperature T: softmax(z / T)")
for T in (0.25, 0.5, 1.0, 2.0, 10.0):
    print(f"   T = {T:>5}: {np.round(softmax(z / T), 4)}")

print()
print("Part 3. Adding the same number to every score changes nothing")
print("   z + 100:", np.round(softmax(z + 100), 4))

print()
print("Part 4. Why subtract the largest score: scores 1000, 999, 998")
big = np.array([1000.0, 999.0, 998.0])
with np.errstate(over="ignore", invalid="ignore"):
    naive = np.exp(big) / np.exp(big).sum()
print("   naive e^z / sum:", naive, " (e^1000 overflows a float)")
print("   after subtracting 1000:", np.round(softmax(big), 4))

print()
print("Part 5. Sampling 100,000 next words at T = 1 (seeded)")
rng = np.random.default_rng(8)
p = softmax(z)
draws = rng.choice(3, size=100_000, p=p)
for i, w in enumerate(words):
    print(f"   {w:<7} expected {p[i]:.4f}  drawn {np.mean(draws == i):.4f}")
