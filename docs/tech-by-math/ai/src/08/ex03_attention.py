# Scaled dot-product attention, by hand and with numpy:
#   weights = softmax(q . k / sqrt(d)) over the earlier tokens, output = weights @ V
# (the same steps as multihead_attn in OpenAI's GPT-2 code, for one head)
import numpy as np
np.set_printoptions(suppress=True, precision=4)

def softmax(z):
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)

print("Part 1. Three tokens, d = 2")
Q = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
K = np.array([[1.0, 0.0], [0.0, 2.0], [1.0, 1.0]])
V = np.array([[10.0, 0.0], [0.0, 10.0], [5.0, 5.0]])
d = Q.shape[1]
S = Q @ K.T / np.sqrt(d)
print("   scores q.k / sqrt(2):\n", S)
mask = np.triu(np.ones((3, 3), dtype=bool), k=1)       # a token may not look at later tokens
S_masked = np.where(mask, -np.inf, S)
W = softmax(S_masked)
print("   weights after the causal mask and softmax:\n", W)
print("   outputs (weights @ V):\n", W @ V)

print()
print("Part 2. Why divide by sqrt(d): random q and k with mean 0, variance 1")
rng = np.random.default_rng(42)
for d in (2, 16, 64, 256):
    q = rng.standard_normal((20_000, d))
    k = rng.standard_normal((20_000, d))
    dots = (q * k).sum(axis=1)
    print(f"   d = {d:>3}: variance of q.k = {dots.var():7.2f} (theory {d}); after / sqrt(d): {(dots / np.sqrt(d)).var():.3f}")

print()
print("Part 3. What the scale does to the weights: 16 keys, d = 256, largest weight on average")
q = rng.standard_normal((2_000, 1, 256))
k = rng.standard_normal((2_000, 16, 256))
raw = (q * k).sum(axis=2)
print(f"   without scaling: {softmax(raw).max(axis=1).mean():.3f}   with scaling: {softmax(raw / 16).max(axis=1).mean():.3f}")
