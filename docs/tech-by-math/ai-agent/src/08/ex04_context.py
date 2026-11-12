# Context growth: every step sends the whole conversation so far, so the input
# tokens of a run grow with the square of the number of steps.
s, t = 2_000, 500          # starting prompt, tokens added per step (tool output and reasoning)

def total_by_loop(n):
    return sum(s + (i - 1) * t for i in range(1, n + 1))

def total_formula(n):
    return n * s + t * n * (n - 1) // 2

print("Part 1. Input tokens sent over a run of n steps")
for n in (1, 10, 20, 40, 80):
    a, b = total_by_loop(n), total_formula(n)
    print(f"   n = {n:>2}: loop {a:>9,}  formula n s + t n(n-1)/2 = {b:>9,}  per step {a / n:>8,.0f}")
print(f"   20 -> 40 steps: x{total_formula(40) / total_formula(20):.2f} tokens; 40 -> 80: x{total_formula(80) / total_formula(40):.2f}")

print()
print("Part 2. When does one request pass a context window of W tokens?")
for W in (32_000, 128_000, 200_000):
    i = 1
    while s + (i - 1) * t <= W:
        i += 1
    print(f"   W = {W:>7,}: steps 1 to {i - 1} fit, step {i} is the first to need more (by hand: step k fits while k <= (W - s) / t + 1 = {(W - s) / t + 1:,.0f})")

print()
print("Part 3. Keeping only a summary: after every 10 steps, replace the history by 1,000 tokens")
def total_with_summary(n, every=10, summary=1_000):
    total, ctx = 0, s
    for i in range(1, n + 1):
        total += ctx
        ctx += t
        if i % every == 0:
            ctx = s + summary
    return total
for n in (20, 40, 80):
    print(f"   n = {n:>2}: full history {total_formula(n):>9,}   with summaries {total_with_summary(n):>9,}")
