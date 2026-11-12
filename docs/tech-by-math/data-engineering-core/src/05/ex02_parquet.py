# Tech by Math, tutorial 5: a million orders as CSV and as Parquet (pyarrow 26), what the Parquet file stores per column
# and per row group, and how many bytes a date filter really reads, counted by wrapping the file in a byte counter.
import io
import os
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

OUT = "/tmp/tbm05"
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(2026)
N = 1_000_000
cities = [f"City {k:02d}" for k in range(50)]
weights = 1 / np.arange(1, 51)                       # a few big cities, a long tail
days = np.sort(rng.integers(0, 365, N))              # the orders arrive day by day, so the file is in date order
df = pd.DataFrame({
    "order_id": np.arange(1, N + 1),
    "order_date": (np.datetime64("2026-01-01") + days.astype("timedelta64[D]")).astype("datetime64[D]"),
    "customer_id": rng.integers(1, 100_001, N),
    "city": rng.choice(cities, N, p=weights / weights.sum()),
    "status": rng.choice(["delivered", "shipped", "returned", "lost"], N, p=[0.85, 0.10, 0.04, 0.01]),
    "amount": rng.integers(1, 1001, N),
})
table = pa.Table.from_pandas(df, preserve_index=False)
table = table.set_column(1, "order_date", pc.cast(table["order_date"], pa.date32()))  # a date, not a timestamp
shuffled = table.take(rng.permutation(N))           # the same rows in random order

df.to_csv(f"{OUT}/orders.csv", index=False)
files = {"csv": f"{OUT}/orders.csv"}
for name, t, comp in (("parquet, no compression", table, "none"), ("parquet, snappy (default)", table, "snappy"),
                      ("parquet, zstd", table, "zstd"), ("parquet, snappy, rows shuffled", shuffled, "snappy")):
    path = f"{OUT}/{name.replace(' ', '_').replace(',', '').replace('(', '').replace(')', '')}.parquet"
    pq.write_table(t, path, compression=comp, row_group_size=50_000)
    files[name] = path
# tuned: order_id, which only counts up, stored as differences (DELTA_BINARY_PACKED) instead of in a dictionary
files["parquet, zstd, order_id as deltas"] = f"{OUT}/tuned.parquet"
pq.write_table(table, files["parquet, zstd, order_id as deltas"], compression="zstd", row_group_size=50_000,
               use_dictionary=["order_date", "customer_id", "city", "status", "amount"],
               column_encoding={"order_id": "DELTA_BINARY_PACKED"})

print("Part 1. File sizes for 1,000,000 orders")
csv_size = os.path.getsize(files["csv"])
for name, path in files.items():
    size = os.path.getsize(path)
    print(f"   {name:<32} {size:>12,} bytes   {csv_size / size:5.1f} times smaller than the CSV")

sorted_file = files["parquet, snappy (default)"]
meta = pq.ParquetFile(sorted_file).metadata
print(f"\nPart 2. Inside the snappy file: {meta.num_rows:,} rows, {meta.num_row_groups} row groups of 50,000 rows")
print(f"   {'column':<12} {'encodings (row group 0)':<44} {'bytes before compression':>24} {'bytes stored':>12}")
for c in range(meta.num_columns):
    col0 = meta.row_group(0).column(c)
    raw = sum(meta.row_group(g).column(c).total_uncompressed_size for g in range(meta.num_row_groups))
    stored = sum(meta.row_group(g).column(c).total_compressed_size for g in range(meta.num_row_groups))
    print(f"   {col0.path_in_schema:<12} {', '.join(col0.encodings):<44} {raw:>24,} {stored:>12,}")

tuned = pq.ParquetFile(files["parquet, zstd, order_id as deltas"]).metadata
print("   order_id in the tuned file:", ", ".join(tuned.row_group(0).column(0).encodings), "-",
      f"{sum(tuned.row_group(g).column(0).total_uncompressed_size for g in range(tuned.num_row_groups)):,} bytes before compression,",
      f"{sum(tuned.row_group(g).column(0).total_compressed_size for g in range(tuned.num_row_groups)):,} stored")
print("   distinct customer_id values in row group 0:",
      pc.count_distinct(pq.ParquetFile(sorted_file).read_row_group(0, columns=["customer_id"])["customer_id"]).as_py())

print("\nPart 3. Statistics kept for order_date, first 4 row groups (sorted file, then shuffled file)")
for name in ("parquet, snappy (default)", "parquet, snappy, rows shuffled"):
    m = pq.ParquetFile(files[name]).metadata
    print(f"   {name}:", [(str(m.row_group(g).column(1).statistics.min), str(m.row_group(g).column(1).statistics.max))
                          for g in range(4)])


class CountingFile(io.RawIOBase):
    """A read-only file that counts the bytes pyarrow asks for."""
    def __init__(self, path):
        self.f, self.bytes = open(path, "rb"), 0
    def readable(self): return True
    def seekable(self): return True
    def seek(self, off, whence=0): return self.f.seek(off, whence)
    def tell(self): return self.f.tell()
    def readinto(self, b):
        n = self.f.readinto(b)
        self.bytes += n
        return n


print("\nPart 4. One day of orders: WHERE order_date = 2026-07-15")
import datetime
day = pa.scalar(datetime.date(2026, 7, 15), type=pa.date32())
for name in ("parquet, snappy (default)", "parquet, snappy, rows shuffled"):
    path = files[name]
    m = pq.ParquetFile(path).metadata
    keep = [g for g in range(m.num_row_groups)
            if m.row_group(g).column(1).statistics.min <= day.as_py() <= m.row_group(g).column(1).statistics.max]
    cf = CountingFile(path)
    t = pq.read_table(pa.PythonFile(cf, mode="r"), filters=[("order_date", "=", day.as_py())], pre_buffer=False)
    size = os.path.getsize(path)
    if len(keep) == 1:
        st = lambda g: (str(m.row_group(g).column(1).statistics.min), str(m.row_group(g).column(1).statistics.max))
        print(f"   {name}: the day is in row group {keep[0]} of 0-{m.num_row_groups - 1}, range {st(keep[0])}; "
              f"last row group {st(m.num_row_groups - 1)}")
    print(f"   {name}: row groups whose min/max include the day: {len(keep)} of {m.num_row_groups}; "
          f"rows found {t.num_rows:,}; bytes read {cf.bytes:,} of {size:,} ({cf.bytes / size:.1%})")

print("\nPart 5. One column only: SELECT sum(amount) reads")
cf = CountingFile(sorted_file)
t = pq.read_table(pa.PythonFile(cf, mode="r"), columns=["amount"], pre_buffer=False)
print(f"   sum {pc.sum(t['amount']).as_py():,}; bytes read {cf.bytes:,} of {os.path.getsize(sorted_file):,} "
      f"({cf.bytes / os.path.getsize(sorted_file):.1%})")
