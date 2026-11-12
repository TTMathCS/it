# Tech by Math, tutorial 3: choosing a join order. Estimates every intermediate result with
# |R join S| = |R| x |S| / max(V(R,a), V(S,a)) (a product when no condition links them), scores a plan by the sum of
# its intermediate result sizes (the final result is the same for every order, so it is left out), then finds the best
# left-deep order twice: by trying all n! orders, and by dynamic programming over subsets. Also counts the orders.
from itertools import permutations
from math import factorial


def solve(name, sizes, preds):
    """sizes: {table: rows after its own filters}; preds: {(t1, t2): max(V(t1,a), V(t2,a))}."""
    tables = sorted(sizes)

    def size(group):
        rows = 1
        for t in group:
            rows *= sizes[t]
        for (a, b), v in preds.items():
            if a in group and b in group:
                rows /= v
        return rows

    def cost(order):
        return sum(size(order[:k]) for k in range(2, len(order)))  # intermediate results only

    print(f"\n{name}: {len(tables)} tables, sizes {sizes}")
    results = sorted((cost(o), o) for o in permutations(tables))
    seen = set()
    print("  every left-deep order (A B C means (A join B) join C); swapping the first two gives the same cost:")
    for c, o in results:
        key = (frozenset(o[:2]),) + o[2:]
        if key in seen:
            continue
        seen.add(key)
        steps = " -> ".join(f"{size(o[:k]):,.0f}" for k in range(2, len(o) + 1))
        print(f"    {' '.join(o):<10} sizes {steps:<36} cost {c:>12,.0f}")

    # dynamic programming: best[S] = cheapest way to build the set S, adding one table at a time
    best = {frozenset([t]): (0, (t,)) for t in tables}
    for k in range(2, len(tables) + 1):
        for group in {frozenset(o[:k]) for o in permutations(tables)}:
            here = size(group) if k < len(tables) else 0
            best[group] = min((best[group - {t}][0] + here, best[group - {t}][1] + (t,)) for t in group)
    c, o = best[frozenset(tables)]
    print(f"  dynamic programming: best order {' '.join(o)}, cost {c:,.0f}; "
          f"brute force best cost {results[0][0]:,.0f}; {2 ** len(tables) - 1} subsets looked at")


# The by-hand example of 3.3: orders O, customers C filtered to one country (10 of 1,000), shipments S.
solve("3.3 by hand", {"O": 10_000, "C": 10, "S": 10_000}, {("C", "O"): 1_000, ("O", "S"): 10_000})
# Exercise E4: add products P (100 rows), linked to orders by product_id.
solve("E4", {"O": 10_000, "C": 10, "S": 10_000, "P": 100}, {("C", "O"): 1_000, ("O", "S"): 10_000, ("O", "P"): 100})

print("\nHow many orders are there?")
print(f"  {'n':>3} {'left-deep n!':>16} {'any shape (2n-2)!/(n-1)!':>26} {'subsets 2^n - 1':>16}")
for n in (2, 3, 4, 5, 8, 10, 12, 20):
    print(f"  {n:>3} {factorial(n):>16,} {factorial(2 * n - 2) // factorial(n - 1):>26,} {2 ** n - 1:>16,}")
