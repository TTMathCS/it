# Tech by Math, tutorial 2: the opening question, for real. 100 million rows on PostgreSQL 16, one index on the key,
# then one lookup. The table is UNLOGGED and has a single column, only to save time and disk while building it
# (about 6 GB in all); neither changes the shape of the B-tree or the pages a lookup reads.
import time
import psycopg2

conn = psycopg2.connect(host="localhost", user="postgres", dbname="postgres")
conn.autocommit = True
cur = conn.cursor()


def q(sql):
    cur.execute(sql)
    return cur.fetchall() if cur.description else None


q("CREATE EXTENSION IF NOT EXISTS pgstattuple")
q("SET max_parallel_workers_per_gather = 0")
q("SET maintenance_work_mem = '512MB'")
q("DROP TABLE IF EXISTS big")
t0 = time.time()
q("CREATE UNLOGGED TABLE big (order_id bigint NOT NULL)")
q("INSERT INTO big SELECT g FROM generate_series(1, 100000000) g")
q("CREATE INDEX big_id ON big (order_id)")
q("VACUUM ANALYZE big")
print(f"built in {time.time() - t0:.0f} s")
level, internal, leaf, density = q("SELECT tree_level, internal_pages, leaf_pages, avg_leaf_density FROM pgstatindex('big_id')")[0]
heap, = q("SELECT pg_relation_size('big') / 8192")[0]
print(f"rows 100,000,000; table pages {heap:,}; index levels {level + 1}; leaf pages {leaf:,}; "
      f"internal pages {internal:,}; leaf pages {density}% full")
for label, setting in (("index-only scan (the answer is in the index)", "on"),
                       ("index scan that also visits the table, as for a wider row", "off")):
    q(f"SET enable_indexonlyscan = {setting}")
    print(label)
    q("EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY OFF) SELECT * FROM big WHERE order_id = 76543210")
    for row in q("EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY OFF) SELECT * FROM big WHERE order_id = 76543210"):
        print("  " + row[0])
q("DROP TABLE big")
