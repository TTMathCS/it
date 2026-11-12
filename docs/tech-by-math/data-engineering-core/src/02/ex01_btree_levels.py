# Tech by Math, tutorial 2: how tall is a real B-tree? Builds tables of 1 thousand to 10 million rows on PostgreSQL 16,
# indexes them, and reads the tree's shape with the pgstattuple and pageinspect extensions. Then counts the pages one
# lookup reads, with and without the index, with EXPLAIN (ANALYZE, BUFFERS).
# Needs a local PostgreSQL 16 where the user may CREATE EXTENSION (here: user postgres, trust on localhost).
import psycopg2

conn = psycopg2.connect(host="localhost", user="postgres", dbname="postgres")
conn.autocommit = True
cur = conn.cursor()


def q(sql):
    cur.execute(sql)
    return cur.fetchall() if cur.description else None


q("CREATE EXTENSION IF NOT EXISTS pgstattuple")
q("CREATE EXTENSION IF NOT EXISTS pageinspect")
q("SET max_parallel_workers_per_gather = 0")  # one process, so each plan prints one buffer count

print("Part 1. The shape of the index on a bigint key, for growing tables")
print(f"{'rows':>11} {'levels':>6} {'leaf pages':>10} {'inner pages':>11} {'root children':>13} {'rows/leaf':>9} {'leaf full %':>11}")
for n in (1_000, 100_000, 10_000_000):
    t = f"orders_{n}"
    q(f"DROP TABLE IF EXISTS {t}")
    q(f"CREATE TABLE {t} (order_id bigint NOT NULL, region int NOT NULL, amount int NOT NULL)")
    q(f"INSERT INTO {t} SELECT g, g % 4, (g::bigint * 7919) % 1000 FROM generate_series(1, {n}) g")
    q(f"CREATE INDEX {t}_id ON {t} (order_id)")
    q(f"VACUUM ANALYZE {t}")
    level, = q(f"SELECT tree_level FROM pgstatindex('{t}_id')")[0]
    internal, leaf, density = q(f"SELECT internal_pages, leaf_pages, avg_leaf_density FROM pgstatindex('{t}_id')")[0]
    root, = q(f"SELECT root FROM bt_metap('{t}_id')")[0]
    root_items, = q(f"SELECT live_items FROM bt_page_stats('{t}_id', {root})")[0]
    # a leaf in the middle of the index: the leftmost leaf is block 1 for an index built by CREATE INDEX
    leaf_items, = q(f"SELECT live_items FROM bt_page_stats('{t}_id', 1)")[0]
    # live_items of a leaf that is not the rightmost includes one extra item, the page's high key, hence leaf_items - 1.
    # pgstatindex counts the root among the internal pages.
    # tree_level counts the levels above the leaves, so the number of levels is tree_level + 1
    print(f"{n:>11,} {level + 1:>6} {leaf:>10,} {internal:>11,} {root_items:>13} {leaf_items - 1:>9} {density:>11}")

t = "orders_10000000"
print()
print("Part 2. Size of one index entry (a leaf page of the 10 million row index)")
print(q(f"SELECT live_items, avg_item_size, page_size, free_size FROM bt_page_stats('{t}_id', 1)"))
print("The tree, level by level (block numbers of the pages on each level are not shown, only their count):")
root, level = q(f"SELECT root, level FROM bt_metap('{t}_id')")[0]
print(f"  root is block {root}, at level {level} (level 0 = leaves)")

print()
print("Part 3. One lookup, with the index")
q(f"EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY OFF) SELECT * FROM {t} WHERE order_id = 7654321")  # warm up
for row in q(f"EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY OFF) SELECT * FROM {t} WHERE order_id = 7654321"):
    print("  " + row[0])

print()
print("Part 4. The same lookup when the index cannot be used (the column is wrapped in an expression)")
for row in q(f"EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY OFF) SELECT * FROM {t} WHERE order_id + 0 = 7654321"):
    print("  " + row[0])
heap_pages, = q(f"SELECT pg_relation_size('{t}') / 8192")[0]
print(f"  the table has {heap_pages:,} pages of 8 kB")

print()
print("Part 5. Low selectivity: an index on region (4 values, 25% of rows each)")
q(f"CREATE INDEX IF NOT EXISTS {t}_region ON {t} (region)")
q(f"ANALYZE {t}")
for where in ("region = 2", "region IN (1, 2, 3)", "order_id BETWEEN 1000 AND 1100"):
    print(f"  -- WHERE {where}")
    q(f"EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY OFF) SELECT count(amount) FROM {t} WHERE {where}")
    for row in q(f"EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY OFF) SELECT count(amount) FROM {t} WHERE {where}"):
        print("  " + row[0])
q(f"DROP INDEX {t}_region")

print()
print("Part 6. The cost on every write: WAL records for inserting 100,000 rows into a copy with 0, 1 and 2 indexes")
for k in (0, 1, 2):
    q("DROP TABLE IF EXISTS w")
    q("CREATE TABLE w (order_id bigint, region int, amount int)")
    if k >= 1:
        q("CREATE INDEX w_id ON w (order_id)")
    if k >= 2:
        q("CREATE INDEX w_amount ON w (amount)")
    plan = q("EXPLAIN (ANALYZE, BUFFERS, WAL, COSTS OFF, TIMING OFF, SUMMARY OFF) "
             "INSERT INTO w SELECT g, g % 4, (g::bigint * 7919) % 1000 FROM generate_series(1, 100000) g")
    wal = [r[0].strip() for r in plan if r[0].strip().startswith("WAL")][0]
    size, = q("SELECT pg_total_relation_size('w') / 8192")[0]
    print(f"  {k} index(es): {wal}; table + indexes = {size:,} pages")
q("DROP TABLE w")
