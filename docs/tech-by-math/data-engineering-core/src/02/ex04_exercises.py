# Tech by Math, tutorial 2: checks for exercises E2 and E5.
# E2: a uuid key is 16 bytes, twice a bigint. How many rows per leaf page, and how many levels for 1 million rows?
# E5: if a fraction p of the rows match and the matches are spread at random, what share of the table's pages
#     holds at least one match? Formula 1 - (1 - p)^r for r rows per page, against a simulation.
import numpy as np
import psycopg2

conn = psycopg2.connect(host="localhost", user="postgres", dbname="postgres")
conn.autocommit = True
cur = conn.cursor()
cur.execute("CREATE EXTENSION IF NOT EXISTS pgstattuple")
cur.execute("CREATE EXTENSION IF NOT EXISTS pageinspect")
cur.execute("DROP TABLE IF EXISTS u")
cur.execute("CREATE TABLE u (id uuid NOT NULL)")
cur.execute("INSERT INTO u SELECT gen_random_uuid() FROM generate_series(1, 1000000)")
cur.execute("CREATE INDEX u_id ON u (id)")
cur.execute("SELECT tree_level + 1, leaf_pages, internal_pages FROM pgstatindex('u_id')")
levels, leaf, internal = cur.fetchone()
cur.execute("SELECT live_items, avg_item_size FROM bt_page_stats('u_id', 1)")
items, size = cur.fetchone()
print(f"E2 uuid index, 1,000,000 rows: item size {size} bytes, {items - 1} rows on a leaf (plus the high key), "
      f"{leaf:,} leaf pages, {internal} inner pages, {levels} levels")
cur.execute("DROP TABLE u")

print()
rng = np.random.default_rng(2026)
r, pages = 185, 54_055   # rows per table page and pages of the 10 million row table in ex01
print(f"E5 {'p':>7} {'formula':>8} {'simulated':>9}")
for p in (0.0001, 0.001, 0.01, 0.05):
    hit = rng.random((pages, r)) < p          # one row = one cell; True where the row matches
    print(f"   {p:>7.2%} {1 - (1 - p) ** r:>8.1%} {hit.any(axis=1).mean():>9.1%}")
