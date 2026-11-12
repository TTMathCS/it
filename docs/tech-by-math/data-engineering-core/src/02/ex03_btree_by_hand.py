# Tech by Math, tutorial 2: checks the by-hand work. (1) The order-3 B-tree of section 2.3 and its two inserts.
# (2) The height bounds of section 2.4 for a PostgreSQL bigint index, next to the height of a freshly built index.
import math

# ---------- (1) An order-3 B-tree: every node holds 1 or 2 keys; an inner node with k keys has k + 1 children. ----------


class Node:
    def __init__(self, keys, children=None):
        self.keys, self.children = keys, children or []


def show(root):
    level, out = [root], []
    while level:
        out.append("   ".join("[" + " ".join(map(str, n.keys)) + "]" for n in level))
        level = [c for n in level for c in n.children]
    return "\n".join(out)


def search(root, key):
    node, path = root, []
    while True:
        path.append(node.keys)
        if key in node.keys or not node.children:
            return path, key in node.keys
        node = node.children[sum(k < key for k in node.keys)]


def insert(root, key):
    """Insert into the leaf; a node that reaches 3 keys splits and pushes its middle key up. Returns the new root."""
    def ins(node):
        if node.children:
            i = sum(k < key for k in node.keys)
            up = ins(node.children[i])
            if up is None:
                return None
            mid, right = up
            node.keys.insert(i, mid)
            node.children.insert(i + 1, right)
        else:
            node.keys = sorted(node.keys + [key])
        if len(node.keys) <= 2:
            return None
        print(f"    split [{' '.join(map(str, node.keys))}]: {node.keys[1]} goes up")
        right = Node(node.keys[2:], node.children[2:])
        mid = node.keys[1]
        node.keys, node.children = node.keys[:1], node.children[:2]
        return mid, right

    up = ins(root)
    if up is None:
        return root
    print("    the root split: the tree grows one level, at the top")
    return Node([up[0]], [root, up[1]])


L = lambda *k: Node(list(k))
root = Node([50], [Node([20], [L(10, 15), L(30)]),
                   Node([70, 85], [L(60), L(75, 80), L(90)])])
print("The tree of 2.3 (11 keys, 3 levels):")
print(show(root))
print("search 80 reads:", search(root, 80))
for key in (12, 78):
    print(f"insert {key}:")
    root = insert(root, key)
    print(show(root))
print("Exercise E3: insert 16, then 17:")
for key in (16, 17):
    print(f"insert {key}:")
    root = insert(root, key)
    print(show(root))

# ---------- (2) Height bounds for a PostgreSQL bigint B-tree ----------
# A leaf page of 8192 bytes has 8152 bytes for items; one item = 16 bytes + a 4-byte line pointer = 20 bytes.
PAGE_ITEMS = (8192 - 24 - 16) // 20       # 407 items, the most a page can hold
FULL_ROWS = PAGE_ITEMS - 1                # 406 rows: one item on a non-rightmost leaf is the high key
M = PAGE_ITEMS                            # the most children an inner page can have
D = math.ceil(M / 2)                      # the fewest children of a half-full inner page
print()
print(f"page items {PAGE_ITEMS}, rows per full leaf {FULL_ROWS}, max fan-out m = {M}, half fan-out d = {D}")


def built_levels(n, leaf_rows=366, inner_children=284):
    """Levels of an index made by CREATE INDEX: leaves 90% full (366 rows), inner pages 70% full (about 284)."""
    pages, levels = math.ceil(n / leaf_rows), 1
    while pages > 1:
        pages, levels = math.ceil(pages / inner_children), levels + 1
    return levels


print(f"{'rows N':>16} {'fewest levels':>13} {'most levels':>11} {'CREATE INDEX gives':>18}")
for n in (10 ** 3, 10 ** 5, 10 ** 7, 10 ** 8, 10 ** 9, 10 ** 10, 10 ** 12):
    leaves_full = math.ceil(n / FULL_ROWS)           # fewest leaves: every leaf full
    leaves_half = max(1, n // math.ceil(FULL_ROWS / 2))  # most leaves: every leaf half full
    h_min = 1
    while M ** (h_min - 1) < leaves_full:           # h levels give at most m^(h-1) leaves
        h_min += 1
    h_max = 1 if leaves_half == 1 else 2
    while 2 * D ** (h_max - 1) <= leaves_half:      # h levels need at least 2 d^(h-2) leaves
        h_max += 1
    print(f"{n:>16,} {h_min:>13} {h_max:>11} {built_levels(n):>18}")
