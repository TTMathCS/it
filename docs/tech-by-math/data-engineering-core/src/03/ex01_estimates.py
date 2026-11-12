# Tech by Math, tutorial 3: how PostgreSQL 16 estimates row counts, and what a wrong estimate does to the plan.
# Builds orders3 (1 million rows) and returns3 (every third order), where city decides province and country,
# then compares the planner's estimates with the real counts, reproduces a slow nested loop, and fixes it with
# CREATE STATISTICS. ANALYZE reads a random sample, so estimates can differ by a few rows from run to run.
import psycopg2

conn = psycopg2.connect(host="localhost", user="postgres", dbname="postgres")
conn.autocommit = True
cur = conn.cursor()


def q(sql):
    cur.execute(sql)
    return cur.fetchall() if cur.description else None


def plan(sql):
    for row in q("EXPLAIN (ANALYZE, TIMING OFF) " + sql):
        if not row[0].startswith("Planning"):
            print("  " + row[0])


q("SET max_parallel_workers_per_gather = 0")
q("DROP TABLE IF EXISTS orders3, returns3, promos3")
q("""CREATE TABLE orders3 (order_id int NOT NULL, city_id int NOT NULL, province_id int NOT NULL,
                           country_id int NOT NULL, amount int NOT NULL)""")
# 1000 cities; city c is in province c / 10 (100 provinces) and country c / 100 (10 countries).
# amount depends only on order_id / 1000, so it is independent of the city.
q("""INSERT INTO orders3 SELECT g, g % 1000, (g % 1000) / 10, (g % 1000) / 100, ((g / 1000)::bigint * 7919) % 1000
     FROM generate_series(1, 1000000) g""")
q("CREATE TABLE returns3 AS SELECT order_id, city_id, province_id, country_id FROM orders3 WHERE order_id % 3 = 0")
q("CREATE TABLE promos3 AS SELECT g + 1000 AS city_id FROM generate_series(0, 999) g")  # cities 1000-1999: no orders
q("ANALYZE orders3")
q("ANALYZE returns3")
q("ANALYZE promos3")

print("Part 1. What ANALYZE stored (pg_stats)")
for row in q("""SELECT tablename, attname, n_distinct, most_common_vals IS NOT NULL AS has_mcv
                FROM pg_stats WHERE tablename IN ('orders3', 'returns3', 'promos3') ORDER BY tablename, attname"""):
    print("  ", row)
print("   table sizes:", q("SELECT relname, reltuples::bigint FROM pg_class WHERE relname IN ('orders3', 'returns3', 'promos3') ORDER BY 1"))

print("\nPart 2. One filter")
plan("SELECT * FROM orders3 WHERE city_id = 7")
print("\nPart 3. Two independent filters")
plan("SELECT * FROM orders3 WHERE city_id = 7 AND amount < 100")
print("\nPart 4. Three filters that are not independent")
plan("SELECT * FROM orders3 WHERE city_id = 7 AND province_id = 0 AND country_id = 0")

JOIN = """SELECT count(*) FROM orders3 o JOIN returns3 r ON r.order_id = o.order_id
WHERE o.city_id = 7 AND o.province_id = 0 AND o.country_id = 0
  AND r.city_id = 7 AND r.province_id = 0 AND r.country_id = 0"""
print("\nPart 5. The join, planned on those estimates")
plan(JOIN)

print("\nPart 6. Tell the planner the columns depend on each other, and plan again")
q("CREATE STATISTICS orders3_place (dependencies) ON city_id, province_id, country_id FROM orders3")
q("CREATE STATISTICS returns3_place (dependencies) ON city_id, province_id, country_id FROM returns3")
q("ANALYZE orders3")
q("ANALYZE returns3")
print("   dependencies found:", q("SELECT dependencies FROM pg_stats_ext WHERE statistics_name = 'orders3_place'")[0][0])
plan("SELECT * FROM orders3 WHERE city_id = 7 AND province_id = 0 AND country_id = 0")
plan(JOIN)

print("\nPart 7. Join size estimates: |R| x |S| / max(V(R), V(S))")
plan("SELECT count(*) FROM orders3 o JOIN returns3 r ON r.order_id = o.order_id")
plan("SELECT count(*) FROM orders3 o JOIN promos3 p ON p.city_id = o.city_id")

print("\nPart 8. Exercise E2: an IN list and a range")
plan("SELECT * FROM orders3 WHERE city_id IN (7, 8) AND amount < 500")

print("\nPart 9. Settings that limit the join-order search")
for s in ("join_collapse_limit", "from_collapse_limit", "geqo_threshold", "default_statistics_target",
          "autovacuum_analyze_scale_factor", "autovacuum_analyze_threshold"):
    print(f"   {s} = {q('SHOW ' + s)[0][0]}")
q("DROP TABLE orders3, returns3, promos3")
