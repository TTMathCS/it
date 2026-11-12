# Tech by Math, tutorial 4: precedence graphs. Builds the graph of a schedule, looks for a cycle, and gives a serial
# order when there is none. Then checks the theorem "conflict-serializable exactly when the graph has no cycle" by brute
# force on every interleaving of three small transactions.
# A schedule is written like "r1(x) w2(x) c1": read or write by transaction 1 or 2 of item x. Commits are left out.
import re
from itertools import permutations


def parse(schedule):
    return [(m[0], int(m[1]), m[2]) for m in re.findall(r"([rw])(\d)\((\w+)\)", schedule)]


def conflicts(ops):
    """Pairs (i, j), i before j, of operations of different transactions on the same item, at least one a write."""
    return [(i, j) for i in range(len(ops)) for j in range(i + 1, len(ops))
            if ops[i][1] != ops[j][1] and ops[i][2] == ops[j][2] and "w" in (ops[i][0], ops[j][0])]


def graph(ops):
    return sorted({(ops[i][1], ops[j][1]) for i, j in conflicts(ops)})


def topo(nodes, edges):
    """A serial order that respects every edge, or None if the graph has a cycle (Kahn's algorithm)."""
    edges, order = set(edges), []
    nodes = set(nodes)
    while nodes:
        free = sorted(n for n in nodes if not any(b == n for a, b in edges if a in nodes))
        if not free:
            return None
        order.append(free[0])
        nodes.remove(free[0])
    return order


def equivalent_serial(ops):
    """Brute force: a serial order in which every conflicting pair is in the same order as in the schedule."""
    txs = sorted({t for _, t, _ in ops})
    for order in permutations(txs):
        pos = {t: k for k, t in enumerate(order)}
        if all(pos[ops[i][1]] < pos[ops[j][1]] for i, j in conflicts(ops)):
            return list(order)
    return None


def show(name, schedule):
    ops = parse(schedule)
    edges = graph(ops)
    order = topo({t for _, t, _ in ops}, edges)
    print(f"{name}: {schedule}")
    print(f"   conflicting pairs: {', '.join(f'{ops[i][0]}{ops[i][1]}({ops[i][2]}) before {ops[j][0]}{ops[j][1]}({ops[j][2]})' for i, j in conflicts(ops))}")
    print(f"   edges: {', '.join(f'T{a} -> T{b}' for a, b in edges) or 'none'}")
    print(f"   {'serializable, as ' + ' then '.join(f'T{t}' for t in order) if order else 'cycle: not conflict-serializable'}")


show("S1 lost update", "r1(a) r2(a) w1(a) w2(a)")
show("S2 one after the other, item by item", "r1(a) w1(a) r2(a) w2(a) r1(b) w1(b) r2(b) w2(b)")
show("S3 last seat (P = the set of bookings of flight 1)", "r1(P) r2(P) w1(P) w2(P)")
show("S4 doctors on call (write skew)", "r1(k) r1(l) r2(k) r2(l) w1(k) w2(l)")
show("E2a", "r1(x) w2(x) r3(x) w1(y) r2(y)")
show("E2b", "r1(x) r2(y) w3(x) w2(x) r1(z) w3(z)")
show("E2c", "w1(x) r2(x) w2(y) r3(y) w3(z) r1(z)")

# The theorem, checked on every interleaving of three transactions of two steps each
T = {1: [("r", "x"), ("w", "y")], 2: [("r", "y"), ("w", "z")], 3: [("r", "z"), ("w", "x")]}


def interleavings(left):
    if not any(left.values()):
        yield []
        return
    for t, steps in left.items():
        if steps:
            rest = dict(left)
            rest[t] = steps[1:]
            for tail in interleavings(rest):
                yield [(steps[0][0], t, steps[0][1])] + tail


total = acyclic = agree = 0
for ops in interleavings(T):
    total += 1
    a = topo({1, 2, 3}, graph(ops)) is not None
    b = equivalent_serial(ops) is not None
    acyclic += a
    agree += a == b
print(f"\nT1 = r(x) w(y), T2 = r(y) w(z), T3 = r(z) w(x): {total} interleavings, {acyclic} with no cycle, "
      f"graph test and brute force agree on {agree} of {total}")
