# Tech by Math, Elasticsearch tutorial 8: an inverted index and BM25 scores for six tiny documents, computed
# with Lucene 10.3.1's formula (lucene_math.py). Python doubles; Lucene uses 32-bit floats, so its scores can
# differ in the 7th significant digit.
import re
from collections import Counter, defaultdict
from lucene_math import idf, tf_part, int_to_byte4, byte4_to_int, K1, B

docs = {
    1: "red rock and red sand",
    2: "red dust storm over the rock fields of arcadia",
    3: "the rock shop sells rock",
    4: "sand and dust",
    5: "red red red red red",
    6: "a red sky at dawn",
}
tok = {d: re.findall(r"[a-z]+", t) for d, t in docs.items()}
index = defaultdict(list)
for d, words in tok.items():
    for w, f in sorted(Counter(words).items()):
        index[w].append((d, f))
print("Inverted index (term -> postings: document, frequency):")
for w in ("red", "rock", "sand", "dust"):
    print(f"   {w:<5} -> {index[w]}")

N = len(docs)
dl = {d: len(w) for d, w in tok.items()}
avgdl = sum(dl.values()) / N
print(f"\nN = {N} documents; lengths {dl}; avgdl = {sum(dl.values())}/{N} = {avgdl}")
print(f"k1 = {K1}, b = {B}")
for w in ("red", "rock"):
    n = len(index[w])
    print(f"   idf({w}) = ln(1 + ({N} - {n} + 0.5) / ({n} + 0.5)) = {idf(n, N):.4f}")

print("\nQuery 'red rock': score = sum over the two terms of idf x freq / (freq + k1 (1 - b + b dl / avgdl))")
scores = {}
for d in docs:
    total, parts = 0.0, []
    for w in ("red", "rock"):
        f = dict(index[w]).get(d, 0)
        if f:
            dlq = byte4_to_int(int_to_byte4(dl[d]))   # Lucene stores the length in one byte (exact below 40)
            t = tf_part(f, dlq, avgdl)
            total += idf(len(index[w]), N) * t
            parts.append(f"{w}: f={f}, tf part {t:.4f}")
    scores[d] = total
    print(f"   doc {d} (length {dl[d]}): {'; '.join(parts) or 'no match':<52} score {total:.4f}")
print("Ranking:", [d for d, s in sorted(scores.items(), key=lambda x: -x[1]) if s > 0])

print("\nClassic BM25 multiplies each term by (k1 + 1) = 2.2; every score is 2.2 times larger, same ranking:")
print("   " + ", ".join(f"doc {d}: {s * (K1 + 1):.4f}" for d, s in sorted(scores.items(), key=lambda x: -x[1]) if s > 0))

print("\nSaturation: the tf part for a document of average length, freq = 1, 2, 3, 5, 10, 100 (limit 1):")
print("   " + ", ".join(f"{f}: {tf_part(f, avgdl, avgdl):.3f}" for f in (1, 2, 3, 5, 10, 100)))
