# Learning: the gradient of softmax + cross-entropy is p - y.
# Checked against finite differences, then used to train a tiny next-word model.
import numpy as np
np.set_printoptions(suppress=True, precision=4)

def softmax(z):
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)

def loss(z, target):
    return -np.log(softmax(z)[target])

print("Part 1. Scores 2, 1, 0; the right word is the second (index 1)")
z = np.array([2.0, 1.0, 0.0]); t = 1
p = softmax(z); y = np.eye(3)[t]
g = p - y
print("   p =", p, " loss", round(float(loss(z, t)), 4))
print("   gradient p - y =", g)
h = 1e-6
fd = np.array([(loss(z + h * np.eye(3)[i], t) - loss(z - h * np.eye(3)[i], t)) / (2 * h) for i in range(3)])
print("   finite differences =", fd, " largest gap", f"{np.abs(fd - g).max():.1e}")
lr = 0.5
z2 = z - lr * g
print(f"   one step with learning rate {lr}: z = {z2}, p = {softmax(z2)}, loss {float(loss(z2, t)):.4f}")

print()
print("Part 2. Random scores for 10 words, 5 checks of p - y against finite differences")
rng = np.random.default_rng(1)
worst = 0.0
for _ in range(5):
    z = rng.standard_normal(10) * 3; t = int(rng.integers(10))
    g = softmax(z) - np.eye(10)[t]
    fd = np.array([(loss(z + h * np.eye(10)[i], t) - loss(z - h * np.eye(10)[i], t)) / (2 * h) for i in range(10)])
    worst = max(worst, float(np.abs(fd - g).max()))
print(f"   largest gap over all checks: {worst:.1e}")

print()
print("Part 3. A next-word model for one tiny text, trained by gradient descent")
text = "the cat sat on the mat . the cat ate the rat . the dog sat on the cat .".split()
vocab = sorted(set(text)); ix = {w: i for i, w in enumerate(vocab)}; n = len(vocab)
pairs = [(ix[a], ix[b]) for a, b in zip(text, text[1:])]
X = np.array([a for a, _ in pairs]); Y = np.array([b for _, b in pairs])
W = np.zeros((n, n))                          # W[a, b] = score of word b after word a
counts = np.zeros((n, n)); np.add.at(counts, (X, Y), 1)
best = counts / counts.sum(axis=1, keepdims=True).clip(min=1)
with np.errstate(divide="ignore", invalid="ignore"):
    floor = -np.nansum(counts * np.log(np.where(best > 0, best, 1))) / len(pairs)
for step in range(0, 3001):
    P = softmax(W[X])
    L = -np.log(P[np.arange(len(Y)), Y]).mean()
    if step in (0, 10, 100, 1000, 3000):
        print(f"   step {step:>4}: mean loss {L:.4f}")
    G = P.copy(); G[np.arange(len(Y)), Y] -= 1
    grad = np.zeros_like(W); np.add.at(grad, X, G / len(Y))
    W -= 5.0 * grad
print(f"   lowest possible loss for this text (from the counts): {floor:.4f}")
P_the = softmax(W[ix["the"]])
print("   after 'the', learned vs counted:")
for w in ("cat", "mat", "rat", "dog"):
    print(f"      {w:<4} learned {P_the[ix[w]]:.4f}   counted {best[ix['the'], ix[w]]:.4f}")
