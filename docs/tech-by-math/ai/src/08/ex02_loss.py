# Cross-entropy loss and perplexity.
import math

print("Part 1. Loss of one prediction = -ln(probability given to the right word)")
for p in (1.0, 0.9, 0.5, 0.245, 0.1, 0.01):
    print(f"   p = {p:<6} loss {(-math.log(p)) or 0.0:.4f} nats")

print()
print("Part 2. A four-word sentence")
probs = [0.5, 0.25, 0.8, 0.1]
losses = [-math.log(p) for p in probs]
mean = sum(losses) / len(losses)
print("   losses:", [round(x, 4) for x in losses])
print(f"   mean loss {mean:.4f}; perplexity e^{mean:.4f} = {math.exp(mean):.4f}")
geo = math.prod(probs) ** (1 / len(probs))
print(f"   check: 1 / geometric mean of the probabilities = 1 / {geo:.4f} = {1 / geo:.4f}")

print()
print("Part 3. Guessing uniformly over a vocabulary of V words")
for V in (2, 26, 50_257):
    print(f"   V = {V:>6,}: loss ln V = {math.log(V):.4f} nats, perplexity {V:,}")
print(f"   in bits: log2(50,257) = {math.log2(50_257):.2f}")
