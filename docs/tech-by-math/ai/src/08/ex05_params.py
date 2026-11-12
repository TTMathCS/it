# Counting GPT-2's parameters from the shapes in OpenAI's released code (src/model.py):
#   wte [n_vocab, d], wpe [n_ctx, d]
#   per block: ln_1 g,b [d]; attn c_attn w [d, 3d] b [3d]; attn c_proj w [d, d] b [d];
#              ln_2 g,b [d]; mlp c_fc w [d, 4d] b [4d]; mlp c_proj w [4d, d] b [d]
#   ln_f g,b [d]; the output layer reuses wte (no new parameters)
V, CTX = 50_257, 1024

def count(L, d):
    embed = V * d + CTX * d
    block = (2 * d) + (d * 3 * d + 3 * d) + (d * d + d) + (2 * d) + (d * 4 * d + 4 * d) + (4 * d * d + d)
    return embed + L * block + 2 * d, embed, block

print("Part 1. One block of GPT-2 small (d = 768)")
d = 768
parts = {"ln_1": 2 * d, "attn c_attn": d * 3 * d + 3 * d, "attn c_proj": d * d + d, "ln_2": 2 * d,
         "mlp c_fc": d * 4 * d + 4 * d, "mlp c_proj": 4 * d * d + d}
for k, v in parts.items():
    print(f"   {k:<12} {v:>10,}")
print(f"   block total  {sum(parts.values()):>10,}   (12 d^2 = {12 * d * d:,})")

print()
print("Part 2. The four released sizes (layers and width from the GPT-2 paper, Table 2)")
card = {"small": "124 million", "medium": "355 million", "large": "774 million", "XL": "1.5 billion"}
for name, L, d in [("small", 12, 768), ("medium", 24, 1024), ("large", 36, 1280), ("XL", 48, 1600)]:
    total, embed, block = count(L, d)
    print(f"   {name:<6} L = {L:>2}, d = {d:>4}: {total:>13,} parameters  (model card: {card[name]});"
          f" blocks {L * block / total:.0%}, embeddings {embed / total:.0%}; 12 L d^2 + V d = {12 * L * d * d + V * d:,}")

print()
print("Part 3. Rule of thumb for training compute: about 6 x parameters x tokens")
N = count(12, 768)[0]
for D in (1e9, 10e9, 100e9):
    print(f"   {N / 1e6:.0f}M parameters, {D / 1e9:>4.0f}B tokens: about {6 * N * D:.2e} floating-point operations")
