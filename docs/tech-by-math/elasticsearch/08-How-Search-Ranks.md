# 8. How search finds and ranks: the inverted index, BM25 and shards

*You type `red rock` into a shop's search box. In a few milliseconds Elasticsearch finds the matching products among millions and puts the best first. Why is a page that says "red" five times not the best match? Why can the same document get a different score tomorrow, or on another shard? And why can an index of 5 shards be split into 10 but never into 7? This tutorial computes the whole thing by hand on six tiny documents, using the exact formulas from the source code of Lucene (the library inside Elasticsearch) and Elasticsearch itself.*

!!! abstract "In this tutorial"
    **You will learn:**

    - the inverted index: why finding documents that contain a word is a lookup, and `red AND rock` is a merge of two sorted lists
    - BM25, the default score: rare words count more (idf), repeating a word helps less and less (saturation), and long documents are discounted (length normalisation)
    - two details of Lucene's version: the `(k1 + 1)` factor is dropped because it never changes the order, and a document's length is stored in one byte, so long lengths are rounded down by up to about 11%
    - why one document can score differently on different shards
    - Elasticsearch's routing rule, `floorMod(murmur3(_id), routing_shards) / routing_factor`, and why a split sends each old shard's documents to exactly `k` new shards

    **You need:** natural logarithms (`ln 2 ≈ 0.693`), fractions, and remainders. The Kafka course's [8. The log, offsets and lag](../kafka/08-Log-Offsets-and-Lag.md) uses the same kind of key-to-partition rule; reading its step 5 first helps with step 6 here.

    **How to learn from it:** read 8.1 to 8.3, close the page, redo the scores of 8.3 on paper, then try the exercises in 8.7 before opening any answer. Plan about two and a half hours.

**About the examples. No Elasticsearch cluster ran for this tutorial.** The formulas are copied into Python from the source code: Lucene 10.3.1's `BM25Similarity.java` and `SmallFloat.java`, and Elasticsearch 9.1's `Murmur3HashFunction.java`, `IndexRouting.java` and `MetadataCreateIndexService.java`. The hash is checked against the seven known values in Elasticsearch's own `Murmur3HashFunctionTests`: all seven agree. Python computes in 64-bit floats, Lucene in 32-bit ones, so real scores can differ in the 7th significant digit. The scripts and their full output: [lucene_math.py](src/08/lucene_math.py) (the formulas), [ex01_routing.py](src/08/ex01_routing.py) ([output](src/08/ex01.out.txt)), [ex02_bm25.py](src/08/ex02_bm25.py) ([output](src/08/ex02.out.txt)) and [ex03_norms_shards.py](src/08/ex03_norms_shards.py) ([output](src/08/ex03.out.txt)).

## 8.1 The question

A shop indexes six product descriptions:

| doc | text | length (words) |
| ---: | --- | ---: |
| 1 | red rock and red sand | 5 |
| 2 | red dust storm over the rock fields of arcadia | 9 |
| 3 | the rock shop sells rock | 5 |
| 4 | sand and dust | 3 |
| 5 | red red red red red | 5 |
| 6 | a red sky at dawn | 5 |

1. How does the search find the documents containing `red` or `rock` without reading all six?
2. In what order should documents 1, 2, 3, 5 and 6 be shown for the query `red rock`, and why does document 5, which says "red" five times, not come first?
3. The shop's index has 5 shards. Which shard holds a given product, and what happens when the index is split?

## 8.2 The idea: turn the documents inside out

Reading every document for every query would be far too slow. An **inverted index** stores, for each word (a **term**), the sorted list of documents that contain it, with how often (the **postings list**):

```text
red   → (1, ×2) (2, ×1) (5, ×5) (6, ×1)
rock  → (1, ×1) (2, ×1) (3, ×2)
sand  → (1, ×1) (4, ×1)
dust  → (2, ×1) (4, ×1)
```

Finding the documents with `rock` is now one lookup. `red AND rock` walks the two sorted lists side by side, like merging two sorted piles of cards, and keeps the numbers present in both: documents 1 and 2. The walk takes at most `|red| + |rock|` steps; Lucene also stores skip pointers that let it jump ahead in the longer list.

Then each matching document gets a **score**, and the results are sorted by it. Elasticsearch's default score is **BM25** (Robertson and colleagues, 1990s), which adds up, over the query's terms:

```text
score(term, doc) = idf(term) × freq / (freq + k1 × (1 − b + b × dl / avgdl))
idf(term)        = ln(1 + (N − n + 0.5) / (n + 0.5))
```

with `freq` the term's count in the document, `dl` the document's length, `avgdl` the average length, `N` the number of documents, `n` the number that contain the term, and the defaults `k1 = 1.2`, `b = 0.75`. These are the exact expressions in Lucene 10.3.1's source.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 210" role="img" aria-label="A graph of the term-frequency part of BM25 against the number of times a word appears, from 1 to 10. It rises quickly at first, 0.455 at one occurrence, 0.625 at two, 0.714 at three, then flattens towards 1, reaching 0.893 at ten.">
<g font-size="12" fill="currentColor">
<g stroke="currentColor" fill="none">
<line x1="60" y1="170" x2="600" y2="170"/><line x1="60" y1="170" x2="60" y2="20"/>
<line x1="60" y1="30" x2="600" y2="30" stroke-dasharray="4 4" opacity="0.6"/>
<polyline stroke-width="2.5" points="114,106.4 168,82.5 222,70.0 276,62.3 330,57.1 384,53.3 438,50.5 492,48.3 546,46.5 600,45.0"/>
</g>
<g>
<circle cx="114" cy="106.4" r="3.5"/><circle cx="168" cy="82.5" r="3.5"/><circle cx="222" cy="70" r="3.5"/><circle cx="330" cy="57.1" r="3.5"/><circle cx="600" cy="45" r="3.5"/>
</g>
<text x="20" y="34">1.0</text><text x="20" y="174">0</text>
<text x="104" y="190">1</text><text x="158" y="190">2</text><text x="212" y="190">3</text><text x="320" y="190">5</text><text x="590" y="190">10</text>
<text x="120" y="122">0.455</text><text x="174" y="100">0.625</text><text x="228" y="88">0.714</text><text x="336" y="75">0.806</text><text x="560" y="62">0.893</text>
<text x="250" y="206">freq (times the word appears, document of average length)</text>
</g>
</svg>
<figcaption>Figure 8.1. The term-frequency part of BM25, <code>freq / (freq + 1.2)</code> for a document of average length (<code>ex02</code>). The second occurrence adds 0.17, the tenth adds almost nothing; the curve never passes 1.</figcaption>
</figure>

## 8.3 The math by hand

### Step 1. Rare words count more: idf

`N = 6`. `red` is in `n = 4` documents, `rock` in `n = 3`:

```text
idf(red)  = ln(1 + (6 − 4 + 0.5) / (4 + 0.5)) = ln(1 + 2.5/4.5) = ln(1.556) = 0.4418
idf(rock) = ln(1 + (6 − 3 + 0.5) / (3 + 0.5)) = ln(1 + 3.5/3.5) = ln 2      = 0.6931
```

A match on `rock` is worth about 1.57 times a match on `red`, because `rock` says more about a document: fewer documents have it. A word in every document gets `ln(1 + 0.5 / (N + 0.5))`, close to 0. The `+ 1` inside the logarithm (Lucene's choice) keeps idf positive even for words in more than half the documents.

### Step 2. Repeating a word helps less and less: saturation

For a document of exactly average length, `dl / avgdl = 1` and the bracket is `1 − b + b = 1`, so the term-frequency part is `freq / (freq + 1.2)`:

| freq | 1 | 2 | 3 | 5 | 10 | 100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `freq / (freq + 1.2)` | 0.455 | 0.625 | 0.714 | 0.806 | 0.893 | 0.988 |

It can never exceed 1. Saying `red` five times gives 0.806, less than twice what saying it once gives. `k1` sets how fast the curve flattens: with `k1 = 0` any number of occurrences counts the same as one, and a very large `k1` makes the score grow almost in proportion to `freq`.

### Step 3. Long documents are discounted: length normalisation

The bracket `1 − b + b × dl / avgdl` grows with the document's length. Here `avgdl = 32 / 6 = 5.333`. Document 2 has 9 words:

```text
1 − 0.75 + 0.75 × 9 / 5.333 = 0.25 + 1.2656 = 1.5156
tf part for freq 1 = 1 / (1 + 1.2 × 1.5156) = 1 / 2.8188 = 0.3548
```

against `1 / (1 + 1.2 × 0.9531) = 0.4665` for one occurrence in a 5-word document. The idea: a word mentioned once in a long text is weaker evidence than once in a short one. `b = 0` switches this off; `b = 1` divides fully by the relative length.

### Step 4. The scores for `red rock`

Add the two terms' contributions (`ex02`):

| doc | red: freq, tf part | rock: freq, tf part | score |
| ---: | --- | --- | ---: |
| 1 | 2, 0.6362 | 1, 0.4665 | 0.4418 × 0.6362 + 0.6931 × 0.4665 = **0.6044** |
| 3 | — | 2, 0.6362 | 0.6931 × 0.6362 = **0.4410** |
| 2 | 1, 0.3548 | 1, 0.3548 | 0.4418 × 0.3548 + 0.6931 × 0.3548 = **0.4027** |
| 5 | 5, 0.8138 | — | 0.4418 × 0.8138 = **0.3596** |
| 6 | 1, 0.4665 | — | 0.4418 × 0.4665 = **0.2061** |

The order is 1, 3, 2, 5, 6. Document 1 has both words and is short. Document 3 has only `rock`, but `rock` is the rarer, more telling word, and it appears twice. Document 2 has both words but is long. Document 5's five `red`s are capped by saturation and weighted by `red`'s low idf, so it comes fourth.

### Step 5. Two details of Lucene's BM25

**No `(k1 + 1)`.** The textbook formula multiplies each term by `(k1 + 1) = 2.2`. That multiplies every score by the same 2.2, which never changes the order (`ex02` prints both versions). Lucene leaves it out.

**Lengths in one byte.** Lucene stores each document's length (its "norm") in a single byte, using a small floating-point code (`SmallFloat.intToByte4`). Lengths up to 40 are exact; above that, only the first few binary digits are kept, rounding down (`ex03`):

| length | 40 | 41 | 100 | 250 | 1,000 | 5,000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| read back as | 40 | 40 | 96 | 248 | 984 | 4,632 |

The largest rounding, over all lengths up to 100,000, is 11.1%. So two documents of 100 and 101 words are scored as equally long, and scores for long documents are slightly optimistic. One byte per document instead of four is worth it for a value that only shifts scores a little.

### Step 6. Which shard holds a document

An Elasticsearch index is split into **shards**, each a separate Lucene index. A document goes to

```text
shard = floorMod(murmur3(routing), routing_shards) / routing_factor
```

where `routing` is the document's `_id` unless you give another value, `murmur3` is the 32-bit MurmurHash3 of the routing string's UTF-16 bytes, `routing_shards` is fixed when the index is created, and `routing_factor = routing_shards / shards`. `floorMod` is the remainder made non-negative.

For an index created with 5 shards, Elasticsearch picks `routing_shards` as the largest `5 × 2^k` that is at most 1,024: `5 × 128 = 640`, so `routing_factor = 128`. Worked (`ex01`): `murmur3("order-1042") = −1,435,775,536`. `floorMod(−1,435,775,536, 640) = 464`: the remainder of a negative number is made non-negative by adding 640 enough times. Then `464 / 128 = 3` (whole-number division): **shard 3**.

So the hash first picks one of 640 thin **slots**, and each shard owns a block of 128 consecutive slots: shard 0 has slots 0 to 127, shard 1 has 128 to 255, and so on.

**Splitting.** The `_split` API can turn the 5 shards into 10, keeping `routing_shards = 640`. Now `routing_factor = 64`: each new shard owns 64 slots. Old shard `s` owned slots `128s` to `128s + 127`; those are exactly the slots of new shards `2s` and `2s + 1`. Every document of old shard 3 lands in new shard 6 or 7, never anywhere else. On 100,000 ids, `ex01` finds each old shard feeding exactly two new shards, about half each.

A split to 7 shards is not allowed: 7 does not divide 640, and no grouping of 640 equal slots gives 7 equal blocks. The new count must be a multiple of the old one and divide `routing_shards`: from 5, that means 10, 20, 40, 80, 160, 320 or 640. Compare Kafka (step 5 of its tutorial), where going from 12 to 13 partitions moves 92% of the keys: Elasticsearch simply does not allow such a change.

## 8.4 Why it is true

**Postings intersection.** Both lists are sorted. Compare their heads: if equal, output it and advance both; otherwise advance the smaller. Each step advances at least one list, so the walk ends within `|A| + |B|` steps, and it outputs exactly the common numbers.

**Saturation.** `f / (f + K)` with `K > 0` increases with `f`, stays below 1, and its increase from `f` to `f + 1` is `K / ((f + K)(f + 1 + K))`, which shrinks as `f` grows: each extra occurrence adds less.

**Dropping `(k1 + 1)`.** Every term's contribution is multiplied by the same positive constant, so every document's total is too, and sorting by `c × score` gives the same order as sorting by `score`.

**The split.** Let `x = floorMod(hash, 640)`, a slot from 0 to 639. With 5 shards, the shard is `⌊x / 128⌋`; with 10, `⌊x / 64⌋`. If `⌊x / 128⌋ = s`, then `128 s ≤ x < 128 s + 128`, so `64 × 2s ≤ x < 64 × (2s + 2)`, and `⌊x / 64⌋` is `2s` or `2s + 1`. The same argument works for any split factor `k` that divides `routing_shards / shards`: old shard `s` feeds new shards `ks` to `ks + k − 1`.

**Why BM25 has this shape.** BM25 comes from a probabilistic model of relevance (the "2-Poisson" model of term occurrences), simplified by Robertson and Walker into the formula above. That derivation is not reproduced here. The formula is an engineered approximation, chosen because it ranks well in evaluations, not a theorem.

## 8.5 See it in code

`ex01` checks the hash against Elasticsearch's test values:

```text
'hello'                                       0xd7c31989  expected 0xd7c31989  ok
'The quick brown fox jumps over the lazy dog' 0xe07db09c  expected 0xe07db09c  ok
...                                                                 (all seven ok)
```

then spreads 100,000 ids over 5 shards (`19,801`, `20,097`, `20,150`, `19,946`, `20,006`) and splits them into 10:

```text
shard 0 -> 0 (9,906 docs), 1 (9,895 docs)
shard 1 -> 2 (10,098 docs), 3 (9,999 docs)
...
shard 4 -> 8 (10,028 docs), 9 (9,978 docs)
```

`ex02` prints the postings lists and every number of steps 1 to 4. `ex03` prints the length table of step 5 and the shard example of 8.6.

## 8.6 Where it breaks

- **Each shard has its own statistics.** By default (`query_then_fetch`) each shard computes idf from its own documents. In `ex03`, a document with `regolith` twice scores **2.85** on a shard where 10 of 1,000 documents mention regolith, and **1.00** on one where 200 of 1,000 do; with statistics over the whole index (`dfs_query_then_fetch`), it would score 1.41. On big indexes with random routing the shards' statistics are close and this hardly matters; on small indexes or custom routing it can reorder results. Deleted documents also count in the statistics until segments merge.
- **Scores are for sorting, not for comparing.** A score of 0.6 in one query and 0.4 in another mean nothing relative to each other; idf and avgdl change with the query and the data.
- **Words, not meaning.** BM25 matches terms after analysis (lower-casing, stemming, synonyms if configured). A product described as "crimson stone" scores 0 for `red rock`. That gap is what vector (semantic) search addresses, with different math.
- **Custom routing can make hot shards.** Routing by customer puts each customer's documents on one shard: the hot-key problem of [Spark's tutorial 8](../spark/08-Shuffles-and-Skew.md) and Kafka's step 6.
- **Shard counts are fixed in advance.** Only splits by factors of `routing_shards / shards` and shrinks to divisors are possible (step 6). An index with 1 shard gets `routing_shards = 1024`, so it can be split to any power of 2 up to 1,024.
- **Rounding of lengths** (step 5) makes long documents' scores slightly optimistic and ties some that differ.

## 8.7 Exercises

Do 1 to 5 with a pencil. 6 needs a few lines of thought. 7 is code.

**E1. In an index of `N = 1,000` documents, `mars` appears in 9 and `the` in 990. Compute both idfs.**

??? success "Answer"
    `mars`: `ln(1 + (1000 − 9 + 0.5)/(9 + 0.5)) = ln(1 + 991.5/9.5) = ln(105.37) = 4.657`. `the`: `ln(1 + 10.5/990.5) = ln(1.0106) = 0.0105`. A match on `mars` is worth about 440 times a match on `the`.

**E2. With `k1 = 1.2` and a document of average length, how many occurrences does a word need for its tf part to pass 0.75? With `k1 = 2`?**

??? success "Answer"
    `f / (f + k1) > 0.75` means `f > 3 k1`. For `k1 = 1.2`: `f > 3.6`, so 4 occurrences (`4 / 5.2 = 0.769`). For `k1 = 2`: `f > 6`, so 7.

**E3. Recompute document 2's score for `red rock` with `b = 0` (no length normalisation). Does it pass document 3?**

??? success "Answer"
    With `b = 0` the bracket is 1 for every document, so freq 1 gives `1 / 2.2 = 0.4545` and freq 2 gives `2 / 3.2 = 0.625`. Document 2: `0.4418 × 0.4545 + 0.6931 × 0.4545 = 0.5158`. Document 3: `0.6931 × 0.625 = 0.4332`. Yes: without the length penalty, document 2 moves above document 3.

**E4. An index was created with 3 shards. What is `routing_shards`? Which shard counts can it be split into?**

??? success "Answer"
    The largest `3 × 2^k ≤ 1024` is `3 × 256 = 768`. Splits must be multiples of 3 that divide 768: 6, 12, 24, 48, 96, 192, 384, 768.

**E5. With 5 shards and `routing_shards = 640`, a document's hash gives `floorMod(hash, 640) = 300`. Which shard is it on? After a split to 20 shards?**

??? success "Answer"
    5 shards: `300 / 128 = 2` (shard 2, slots 256 to 383). 20 shards: `routing_factor = 640 / 20 = 32`, `300 / 32 = 9`: shard 9, one of the new shards 8 to 11 that old shard 2 feeds.

**E6. A support site's search returns a short FAQ page above a long manual chapter that explains the problem in depth. Which part of BM25 favours the FAQ, and what could you change?**

??? success "Answer"
    Length normalisation (step 3): the same number of matches counts more in a short document. Lowering `b` for that field (in the index's similarity settings) reduces the penalty on long documents; another option is to index the manual by section, so each section is a shorter document of its own.

**E7. (Code.) Using `lucene_math.py`, find for every length from 41 to 1,000 the length Lucene reads back, and count how many different values those 960 lengths collapse into.**

??? success "Answer"
    ```python
    from lucene_math import int_to_byte4, byte4_to_int

    back = {byte4_to_int(int_to_byte4(L)) for L in range(41, 1001)}
    print(len(back), sorted(back)[:8])
    ```

    It prints `48 [40, 42, 44, 46, 48, 50, 52, 54]`: the 960 lengths share only 48 values. The steps between them start at 2 and double every 8 values, like a floating-point number with 3 bits after the leading one. ([ex04_byte_lengths.py](src/08/ex04_byte_lengths.py), [output](src/08/ex04.out.txt).)

## 8.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a search result that surprised you, and which part of BM25 or of shard statistics explained it.)*

## 8.9 Further reading

On your own sites:

- The same key-to-partition idea: [Kafka 8. The log, offsets and lag](../kafka/08-Log-Offsets-and-Lag.md) and [Spark 8. Shuffles and skew](../spark/08-Shuffles-and-Skew.md)
- Logarithms: [the Math site](https://math.akadian.ca/)

Original sources:

- S. E. Robertson and S. Walker, "Some simple effective approximations to the 2-Poisson model for probabilistic weighted retrieval", *SIGIR 1994*.
- S. Robertson and H. Zaragoza, "The Probabilistic Relevance Framework: BM25 and Beyond", *Foundations and Trends in Information Retrieval* 3(4), 2009.
- Lucene 10.3.1 source: `BM25Similarity.java`, `SmallFloat.java`, at [github.com/apache/lucene](https://github.com/apache/lucene).
- Elasticsearch 9.1 source: `IndexRouting.java`, `Murmur3HashFunction.java`, `MetadataCreateIndexService.java`, at [github.com/elastic/elasticsearch](https://github.com/elastic/elasticsearch).
- C. D. Manning, P. Raghavan and H. Schütze, *Introduction to Information Retrieval*, Cambridge University Press, 2008, chapters 1 and 11 (free online).

## Glossary

- **Term**: a word (after analysis) as stored in the index.
- **Inverted index**: for each term, the sorted list of documents that contain it.
- **Postings list**: that list, with the count of the term in each document.
- **idf**: inverse document frequency, how rare a term is: `ln(1 + (N − n + 0.5)/(n + 0.5))`.
- **Saturation**: each extra occurrence of a term adding less to the score.
- **Length normalisation**: discounting matches in longer documents.
- **BM25**: the default scoring formula combining the three.
- **Norm**: a document's field length, stored by Lucene in one byte.
- **Shard**: one part of an index, itself a complete Lucene index.
- **Routing**: choosing a document's shard from a hash of its `_id` (or a routing value).
- **Split**: turning each shard into `k` shards without re-hashing documents across groups.
