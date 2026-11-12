# Python practice set

Fifty-two tasks in the style of a Codility programming task: a function `solution(...)`, examples, and limits
that tell you how fast the answer must be. They are grouped by the technique they practise. A data engineer's
Python task is as likely to be **data wrangling** as a classic algorithm, so both are here: about half work with
log lines, CSV text, records, joins, dates and nested data, and the rest are the algorithm patterns of Codility's
lessons (counting, prefix sums, sliding windows, stacks, sorting, graphs, binary search).

Every solution states its **cost** (for example O(N log N)) and the **slow answer** that would fail the large
hidden tests; where that slow answer is shown, it was run on the largest input and stopped after 5 seconds.

**How to practise:** for each task, first read the limits and decide the target cost (the table in the
[cheat sheet](cheat-sheet.md) helps), write the code, run the examples, then add your own edge cases **before**
opening the solution.

Every answer in parts A to G was run on Python 3.13 with the examples, the listed edge cases, 500 or more random small inputs
compared with a slow but obviously correct answer, and the largest input the limits allow, timed. Every "common
wrong answer" was run too; its box says which case it fails or how long it took before it was stopped.

!!! tip "Codility's own Python practice"
    The [Codility lessons](codility-tasks.md#python-the-lessons) have graded tasks for each technique below.
    Doing two or three of them on the real grader is the best rehearsal for the editor.

## A. Counting, grouping and joining with dictionaries

### 1. First repeated ID

**Level:** Easy · **Aim for:** 10 minutes

A pipeline receives record IDs in the order of list `A`. Return the ID whose **second appearance comes first**
(the first moment you see an ID you have seen before). Return `-1` if no ID repeats.

**Examples**

* `solution([4, 7, 2, 7, 4])` returns `7`
* `solution([1, 2, 2, 1])` returns `2`
* `solution([5, 6])` returns `-1`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* each element of `A` is an integer within the range [−1,000,000,000..1,000,000,000].

Start from:

```python
def solution(A):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A):
        seen = set()
        for x in A:
            if x in seen:        # set lookup is O(1) on average
                return x
            seen.add(x)
        return -1
    ```
    
    **Why it works**
    
    * Walk through the list once, remembering what you have seen in a **set**. The first value already in the set is
      the answer. O(N) time, O(N) memory.
    * Two traps. Using `A.count(x) > 1` answers a different question ("the first value that repeats anywhere"):
      for `[1, 2, 2, 1]` it returns 1, but 2 is the first value seen twice. And remembering values in a **list**
      makes each `in` check a scan, O(N²) overall: on 100,000 distinct values that is about 5 billion comparisons.
    
    **Cost:** O(N) time, O(N) memory.
    
    **The slow answer:** Remembering the values in a list makes each `in` a scan: O(N²).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `-1`;
    * edge case, negative and zero: `solution([0, -3, -3, 0])` returns `-3`;
    * edge case, all equal: `solution([9, 9, 9])` returns `9`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.008s.
    
    ??? failure "A common wrong answer: count() answers a different question"
    
        ```python
        def solution(A):
            for x in A:
                if A.count(x) > 1:
                    return x
            return -1
        ```
        
        Checked: example: got 4 want 7.
    
    ??? failure "A common wrong answer: a list instead of a set (too slow)"
    
        ```python
        def solution(A):
            seen = []
            for x in A:
                if x in seen:
                    return x
                seen.append(x)
            return -1
        ```
        
        Checked: timed out after 5.0s on the large input.



### 2. Most frequent error code

**Level:** Easy · **Aim for:** 8 minutes

`A` lists the error codes logged today. Return the code that occurs **most often**. If several codes share the
highest count, return the **smallest** of them. `A` is not empty.

**Examples**

* `solution([500, 404, 500, 404, 503])` returns `404`
* `solution([7])` returns `7`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [1..100,000];
* each element of `A` is an integer within the range [0..1,000,000].

Start from:

```python
def solution(A):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import Counter
    
    def solution(A):
        counts = Counter(A)
        best = max(counts.values())
        return min(code for code, c in counts.items() if c == best)
    ```
    
    **Why it works**
    
    * `collections.Counter` counts everything in one pass. Then find the highest count and, among codes with that
      count, take the smallest.
    * `Counter(A).most_common(1)` is tempting, but on a tie it returns the code that was **seen first**, not the
      smallest; the "larger code first in a tie" case shows it.
    * Read every tie rule in a task statement; hidden tests almost always include a tie.
    
    **Cost:** O(N) time, O(D) memory for D different codes.
    
    **The slow answer:** Calling `A.count(x)` for every code scans the whole list each time: O(N·D).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, all different: `solution([30, 10, 20])` returns `10`;
    * edge case, larger code first in a tie: `solution([9, 9, 3, 3])` returns `3`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.017s.
    
    ??? failure "A common wrong answer: most_common breaks ties by first appearance"
    
        ```python
        from collections import Counter
        
        def solution(A):
            return Counter(A).most_common(1)[0][0]
        ```
        
        Checked: example: got 500 want 404.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(A):
            return sorted(set(A), key=lambda x: (-A.count(x), x))[0]
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.017s).



### 3. Pairs that add up to K

**Level:** Medium · **Aim for:** 15 minutes

Return the number of pairs of positions `(i, j)` with `i < j` and `A[i] + A[j] == K`. Values may repeat; each
pair of positions counts once.

**Examples**

* `solution([1, 5, 3, 3, 7], 6)` returns `2`
* `solution([2, 2, 2], 4)` returns `3`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* each element of `A` and `K` are integers within the range [−1,000,000..1,000,000].

Start from:

```python
def solution(A, K):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import Counter
    
    def solution(A, K):
        seen = Counter()
        pairs = 0
        for x in A:
            pairs += seen[K - x]     # every earlier partner forms a pair with x
            seen[x] += 1
        return pairs
    ```
    
    **Why it works**
    
    * For each value `x`, the partners it needs are earlier values equal to `K - x`. Keep a `Counter` of values seen
      so far; add how many partners exist, then record `x`. One pass, O(N).
    * Count **before** adding `x`, so a value never pairs with itself (`[3]` with `K = 6` gives 0) and each pair is
      counted once.
    * A `set` instead of a `Counter` loses duplicates: `[2, 2, 2]` with `K = 4` has 3 pairs.
    * The answer can reach about 5 billion for 100,000 equal values; Python integers do not overflow, but in Java or
      C you would need a 64-bit type.
    
    **Cost:** O(N) time, O(N) memory.
    
    **The slow answer:** Two nested loops over all pairs: O(N²).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([], 0)` returns `0`;
    * edge case, no pair: `solution([1, 2], 10)` returns `0`;
    * edge case, negatives: `solution([-1, 1, 0, 0], 0)` returns `2`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.013s.
    
    ??? failure "A common wrong answer: a set loses repeated values"
    
        ```python
        def solution(A, K):
            seen = set()
            pairs = 0
            for x in A:
                if K - x in seen:
                    pairs += 1
                seen.add(x)
            return pairs
        ```
        
        Checked: example: got 2 want 3.
    
    ??? failure "A common wrong answer: two loops (right, too slow)"
    
        ```python
        def solution(A, K):
            n = len(A)
            return sum(1 for i in range(n) for j in range(i + 1, n) if A[i] + A[j] == K)
        ```
        
        Checked: timed out after 5.0s on the large input.



### 4. Most frequent words

**Level:** Medium · **Aim for:** 10 minutes

`S` is text made of lower-case words separated by single spaces. Return a **list** of the `K` most frequent
words, most frequent first; words with the same count are ordered alphabetically. If there are fewer than `K`
different words, return them all.

**Examples**

* `solution('spark sql data sql lake data sql', 2)` returns `['sql', 'data']`
* `solution('b a c a b', 3)` returns `['a', 'b', 'c']`

**Write an efficient algorithm for the following assumptions:**

* the length of `S` is within the range [0..1,000,000];
* `K` is an integer within the range [1..1,000].

Start from:

```python
def solution(S, K):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import Counter
    
    def solution(S, K):
        counts = Counter(S.split())
        ranked = sorted(counts, key=lambda w: (-counts[w], w))
        return ranked[:K]
    ```
    
    **Why it works**
    
    * Count with `Counter`, then sort the words by a **key tuple**: `(-count, word)`. The minus sign puts high counts
      first; the word itself breaks ties alphabetically. Tuples compare item by item, so one sort does both.
    * `Counter.most_common(K)` orders ties by first appearance, not alphabetically ("b" would come before "a" in the
      second example).
    * `S.split()` with no argument returns `[]` for an empty string; `S.split(" ")` would return `[""]`.
    
    **Cost:** O(W + D log D) time for W words with D different ones, O(D) memory.
    
    **The slow answer:** Picking the best word K times with `list.count`: O(K·D·W).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty text: `solution('', 3)` returns `[]`;
    * edge case, K larger than the number of words: `solution('x y', 5)` returns `['x', 'y']`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.036s.
    
    ??? failure "A common wrong answer: most_common ignores the alphabetical tie rule"
    
        ```python
        from collections import Counter
        
        def solution(S, K):
            return [w for w, _ in Counter(S.split()).most_common(K)]
        ```
        
        Checked: example: got ['b', 'a', 'c'] want ['a', 'b', 'c'].
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(S, K):
            ws = S.split()
            uniq = sorted(set(ws))
            out = []
            for _ in range(min(K, len(uniq))):
                best = None
                for w in uniq:
                    if w in out:
                        continue
                    if best is None or ws.count(w) > ws.count(best):
                        best = w
                out.append(best)
            return out
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.036s).



### 5. The value that fills most of the list

**Level:** Easy · **Aim for:** 10 minutes

Return the value that occurs in **more than half** of the elements of `A`. If there is no such value, return
`-1`.

**Examples**

* `solution([3, 4, 3, 2, 3, 3])` returns `3`
* `solution([1, 2, 1, 2])` returns `-1`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* each element of `A` is an integer within the range [0..1,000,000,000].

Start from:

```python
def solution(A):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import Counter
    
    def solution(A):
        if not A:
            return -1
        value, count = Counter(A).most_common(1)[0]
        return value if count * 2 > len(A) else -1
    ```
    
    **Why it works**
    
    * Count with a `Counter`, take the most common value, and **check it really is more than half**:
      `count * 2 > len(A)` uses whole numbers only, so there is no rounding question. O(N) time.
    * "More than half" excludes exactly half (edge case `[5, 5, 1, 2]`).
    * Codility's lesson 8 shows a way with O(1) memory (keep one candidate and a counter, then check it). The
      `Counter` answer uses O(N) memory, which these limits allow.
    
    **Cost:** O(N) time, O(N) memory.
    
    **The slow answer:** Calling `A.count(x)` for every different value: O(N²) when all differ.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `-1`;
    * edge case, one element: `solution([7])` returns `7`;
    * edge case, exactly half is not enough: `solution([5, 5, 1, 2])` returns `-1`;
    * edge case, most common but not a majority: `solution([4, 4, 1, 2, 3])` returns `-1`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.008s.
    
    ??? failure "A common wrong answer: >= half instead of > half"
    
        ```python
        from collections import Counter
        
        def solution(A):
            if not A:
                return -1
            value, count = Counter(A).most_common(1)[0]
            return value if count * 2 >= len(A) else -1
        ```
        
        Checked: example: got 1 want -1.
    
    ??? failure "A common wrong answer: the most common value without the check"
    
        ```python
        from collections import Counter
        
        def solution(A):
            return Counter(A).most_common(1)[0][0] if A else -1
        ```
        
        Checked: example: got 1 want -1.



### 6. Latest version of each record

**Level:** Medium · **Aim for:** 15 minutes

A change feed delivers records as tuples `(key, version, value)`, not in order. For each key keep the record with
the **highest version**; if the same key and version arrive more than once, the one that arrives **later** in `R`
wins. Return a list of `(key, value)` tuples, sorted by key.

**Examples**

* `solution([('a', 2, 'x'), ('b', 1, 'y'), ('a', 1, 'z')])` returns `[('a', 'x'), ('b', 'y')]`
* `solution([('k', 5, 'old'), ('k', 5, 'new')])` returns `[('k', 'new')]`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* keys and values are strings of letters and digits;
* each version is an integer within the range [0..1,000,000,000].

Start from:

```python
def solution(R):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(R):
        best = {}                                     # key -> (version, value)
        for key, version, value in R:
            if key not in best or version >= best[key][0]:   # >=: a later duplicate wins
                best[key] = (version, value)
        return [(key, best[key][1]) for key in sorted(best)]
    ```
    
    **Why it works**
    
    * One dict, one pass: keep the best record seen so far for each key. This is how a pipeline deduplicates a
      change feed (the SQL version is `ROW_NUMBER() OVER (PARTITION BY key ORDER BY version DESC, arrival DESC)`).
    * `>=` and not `>`: with equal versions the record seen later replaces the earlier one, which is the tie rule.
    * "Last one wins" alone (`best[key] = value` for every record) is only right if the feed arrives in version
      order; the edge case "an older version arrives last" catches it.
    
    **Cost:** O(N + K log K) time for K different keys, O(K) memory.
    
    **The slow answer:** Scanning all records again for every key: O(N·K).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `[]`;
    * edge case, an older version arrives last: `solution([('a', 3, 'p'), ('a', 7, 'q'), ('a', 1, 'r')])` returns `[('a', 'q')]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.062s.
    
    ??? failure "A common wrong answer: > lets the earlier duplicate win"
    
        ```python
        def solution(R):
            best = {}
            for key, version, value in R:
                if key not in best or version > best[key][0]:
                    best[key] = (version, value)
            return [(key, best[key][1]) for key in sorted(best)]
        ```
        
        Checked: example: got [('k', 'old')] want [('k', 'new')].
    
    ??? failure "A common wrong answer: assuming the feed is in version order"
    
        ```python
        def solution(R):
            best = {}
            for key, version, value in R:
                best[key] = value
            return sorted(best.items())
        ```
        
        Checked: example: got [('a', 'z'), ('b', 'y')] want [('a', 'x'), ('b', 'y')].
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(R):
            out = []
            for key in sorted({r[0] for r in R}):
                cands = [(r[1], i, r[2]) for i, r in enumerate(R) if r[0] == key]
                out.append((key, max(cands)[2]))
            return out
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.062s).



### 7. Total spent by every customer

**Level:** Easy · **Aim for:** 10 minutes

`C` is a list of customers `(id, name)` with unique ids and names. `O` is a list of orders `(customer_id,
amount)`; some orders belong to customers not in `C` and must be ignored. Return a list of `(name, total)` tuples
for **every** customer in `C`, with `total` 0 for a customer with no orders, sorted by total from highest to
lowest, then by name.

**Examples**

* `solution([(1, 'ana'), (2, 'ben'), (3, 'cy')], [(1, 30), (3, 5), (1, 10), (9, 99)])` returns `[('ana', 40), ('cy', 5), ('ben', 0)]`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `C`, and `M`, the length of `O`, are integers within the range [0..100,000];
* each amount is an integer within the range [1..10,000].

Start from:

```python
def solution(C, O):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(C, O):
        total = {cid: 0 for cid, _ in C}           # every customer starts at 0 (the "LEFT" part)
        for cid, amount in O:
            if cid in total:                       # ignore orders of unknown customers
                total[cid] += amount
        rows = [(name, total[cid]) for cid, name in C]
        return sorted(rows, key=lambda r: (-r[1], r[0]))
    ```
    
    **Why it works**
    
    * This is a SQL `LEFT JOIN ... GROUP BY` written in Python: a dict that **starts with every customer at 0** keeps
      the customers who have no orders, and `if cid in total` drops orders that match nobody.
    * Sorting by two keys in opposite directions: `key=lambda r: (-r[1], r[0])` (negate the number). For a text key
      that has to go in reverse, sort twice instead: Python's sort is stable, so sort by the second key first, then
      by the first key (that is what the reference answer does).
    * The nested loop ("for each customer, add up its orders") is the plain answer, but it is O(N·M).
    
    **Cost:** O(N log N + M) time, O(N) memory.
    
    **The slow answer:** For each customer, a loop over all orders: O(N·M).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no orders: `solution([(1, 'ana'), (2, 'ben')], [])` returns `[('ana', 0), ('ben', 0)]`;
    * edge case, no customers: `solution([], [(1, 5)])` returns `[]`;
    * edge case, a tie on the total: `solution([(1, 'dee'), (2, 'ana')], [(1, 5), (2, 5)])` returns `[('ana', 5), ('dee', 5)]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.147s.
    
    ??? failure "A common wrong answer: starting from the orders loses customers with none"
    
        ```python
        def solution(C, O):
            names = dict(C)
            total = {}
            for cid, amount in O:
                if cid in names:
                    total[cid] = total.get(cid, 0) + amount
            return sorted(((names[c], t) for c, t in total.items()), key=lambda r: (-r[1], r[0]))
        ```
        
        Checked: example: got [('ana', 40), ('cy', 5)] want [('ana', 40), ('cy', 5), ('ben', 0)].
    
    ??? failure "A common wrong answer: a loop over the orders for every customer (too slow)"
    
        ```python
        def solution(C, O):
            rows = [(name, sum(a for c, a in O if c == cid)) for cid, name in C]
            return sorted(rows, key=lambda r: (-r[1], r[0]))
        ```
        
        Checked: timed out after 5.0s on the large input.



### 8. Top customer in each city

**Level:** Medium · **Aim for:** 15 minutes

Each string in `R` is one purchase, `"name,city,amount"`, where `amount` is a whole number of cents. A customer is
a (name, city) pair, and their total is the sum of their purchases. For **each city**, find the customer with the
highest total; if several tie, take the name that comes first alphabetically. Return a list of strings
`"city:name"`, sorted by city.

**Examples**

* `solution(['ana,lima,500', 'ben,lima,300', 'ben,lima,300', 'cy,oslo,50'])` returns `['lima:ben', 'oslo:cy']`
* `solution([])` returns `[]`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* names and cities are non-empty and contain only lower-case letters;
* each amount is an integer within the range [0..1,000,000].

Start from:

```python
def solution(R):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import defaultdict
    
    def solution(R):
        total = defaultdict(int)
        for row in R:
            name, city, amount = row.split(",")
            total[(city, name)] += int(amount)       # int(): "300" + "300" would be "300300"
        best = {}                                    # city -> (total, name)
        for (city, name), t in total.items():
            b = best.get(city)
            if b is None or t > b[0] or (t == b[0] and name < b[1]):
                best[city] = (t, name)
        return [city + ":" + best[city][1] for city in sorted(best)]
    ```
    
    **Why it works**
    
    * Two passes, the way you would do it in SQL: first **group and sum** (a `dict` keyed by `(city, name)`, like
      `GROUP BY city, name`), then **pick the best per city** (like a `RANK() ... = 1`).
    * The tie rule is written into the comparison: a bigger total wins, and an equal total wins only with a smaller
      name. Another way is `min(..., key=lambda x: (-total, name))`.
    * `int(amount)`: the split gives strings, and adding strings glues them together.
    * Return exactly what is asked: a `list` of `str`, sorted by city. A dict or a list of tuples would fail the
      grader even with the right content.
    
    **Cost:** O(N log C) time for N rows and C cities (the final sort), O(N) memory.
    
    **The slow answer:** Re-adding every customer's rows for every city: O(N²) in the worst case.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, a tie goes to the earlier name: `solution(['dee,rome,10', 'ana,rome,10'])` returns `['rome:ana']`;
    * edge case, the same name in two cities is two customers: `solution(['ana,lima,5', 'ana,oslo,7', 'ben,lima,6'])` returns `['lima:ben', 'oslo:ana']`;
    * edge case, a zero amount: `solution(['cy,oslo,0'])` returns `['oslo:cy']`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.110s.
    
    ??? failure "A common wrong answer: the biggest single purchase instead of the biggest total"
    
        ```python
        def solution(R):
            best = {}
            for row in R:
                name, city, amount = row.split(",")
                a = int(amount)
                if city not in best or a > best[city][0] or (a == best[city][0] and name < best[city][1]):
                    best[city] = (a, name)
            return [c + ":" + best[c][1] for c in sorted(best)]
        ```
        
        Checked: example: got ['lima:ana', 'oslo:cy'] want ['lima:ben', 'oslo:cy'].
    
    ??? failure "A common wrong answer: ties go to whoever came first in the list"
    
        ```python
        from collections import defaultdict
        
        def solution(R):
            total = defaultdict(int)
            for row in R:
                name, city, amount = row.split(",")
                total[(city, name)] += int(amount)
            best = {}
            for (city, name), t in total.items():
                if city not in best or t > best[city][0]:
                    best[city] = (t, name)
            return [c + ":" + best[c][1] for c in sorted(best)]
        ```
        
        Checked: edge: a tie goes to the earlier name: got ['rome:dee'] want ['rome:ana'].
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(R):
            rows = [r.split(",") for r in R]
            out = []
            for city in sorted({c for _, c, _ in rows}):
                names = sorted({n for n, c, _ in rows if c == city})
                totals = [(-sum(int(a) for n2, c2, a in rows if n2 == n and c2 == city), n) for n in names]
                out.append(city + ":" + min(totals)[1])
            return out
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.110s).



## B. Strings, parsing, dates and nested data

### 9. Longest run in a status string

**Level:** Easy · **Aim for:** 8 minutes

`S` records a job's status once a minute, one character per minute (for example `"OOXXXO"`). Return the length
of the **longest run of identical consecutive characters**, or 0 if `S` is empty.

**Examples**

* `solution('OOXXXO')` returns `3`
* `solution('ABBA')` returns `2`

**Write an efficient algorithm for the following assumptions:**

* the length of `S` is within the range [0..200,000];
* `S` consists only of upper-case letters.

Start from:

```python
def solution(S):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(S):
        best = run = 0
        prev = None
        for ch in S:
            run = run + 1 if ch == prev else 1
            prev = ch
            best = max(best, run)   # update on every character, so a run at the end counts
        return best
    ```
    
    **Why it works**
    
    * Keep the length of the current run; reset it to 1 when the character changes.
    * The classic bug is updating `best` **only when the character changes**: the last run is never compared, so
      `"OXXOOOO"` returns 2 instead of 4.
    * `itertools.groupby(S)` groups consecutive equal characters and is a neat one-liner; it is in the standard
      library, so it is allowed.
    
    **Cost:** O(N) time, O(1) memory.
    
    **The slow answer:** Starting a new count from every position is O(N²) on a string of one letter repeated.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution('')` returns `0`;
    * edge case, one character: `solution('Q')` returns `1`;
    * edge case, longest run at the end: `solution('OXXOOOO')` returns `4`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.011s.
    
    ??? failure "A common wrong answer: best updated only on a change"
    
        ```python
        def solution(S):
            best = run = 0
            prev = None
            for ch in S:
                if ch == prev:
                    run += 1
                else:
                    best = max(best, run)
                    run = 1
                prev = ch
            return best
        ```
        
        Checked: edge: one character: got 0 want 1.



### 10. Run-length encoding

**Level:** Easy · **Aim for:** 8 minutes

Compress `S` by replacing each run of a repeated letter with the letter followed by the run's length; a letter
that appears once in a row is written alone. For example `"aaabccdddd"` becomes `"a3bc2d4"`.

**Examples**

* `solution('aaabccdddd')` returns `'a3bc2d4'`
* `solution('abc')` returns `'abc'`

**Write an efficient algorithm for the following assumptions:**

* the length of `S` is within the range [0..200,000];
* `S` consists of lower-case letters.

Start from:

```python
def solution(S):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(S):
        out = []
        i = 0
        while i < len(S):
            j = i
            while j < len(S) and S[j] == S[i]:
                j += 1
            run = j - i
            out.append(S[i] if run == 1 else f"{S[i]}{run}")
            i = j
        return "".join(out)
    ```
    
    **Why it works**
    
    * Find each run with two indexes: `i` at its start, `j` moving to the first different letter. Each letter is
      visited once, so it is O(N) even though there are two loops.
    * Collect pieces in a list and `"".join` them at the end; building a long string with `+=` in a loop can be slow
      in some Python versions.
    * Run lengths can have two or more digits (`z12`).
    
    **Cost:** O(N) time, O(N) memory for the answer.
    
    **The slow answer:** Adding to a string with `+` inside a loop can copy the whole string each time in some Pythons; collecting the pieces in a list and joining once is always O(N).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution('')` returns `''`;
    * edge case, one long run: `solution('zzzzzzzzzzzz')` returns `'z12'`;
    * edge case, single letter: `solution('q')` returns `'q'`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.034s.
    
    ??? failure "A common wrong answer: writes 1 after single letters"
    
        ```python
        import itertools
        
        def solution(S):
            return "".join(ch + str(len(list(g))) for ch, g in itertools.groupby(S))
        ```
        
        Checked: example: got 'a3b1c2d4' want 'a3bc2d4'.



### 11. Count log levels

**Level:** Medium · **Aim for:** 12 minutes

`S` is the text of a log file. Each non-empty line looks like `"2026-11-10 12:00:01 ERROR db timeout"`: a date,
a time, a level, then an optional message. Lines are separated by `"\n"`; the text may end with a newline, and
there may be empty lines, which you ignore.

Return a string listing each level that occurs with its count, as `LEVEL:count`, separated by commas, **sorted by
level name**. Return `""` if there are no log lines.

**Examples**

* `solution('2026-11-10 12:00:01 ERROR db timeout\n2026-11-10 12:00:02 INFO ok\n\n2026-11-10 12:00:09 ERROR retry\n')` returns `'ERROR:2,INFO:1'`

**Write an efficient algorithm for the following assumptions:**

* the length of `S` is within the range [0..1,000,000].

Start from:

```python
def solution(S):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import Counter
    
    def solution(S):
        counts = Counter()
        for line in S.split("\n"):
            parts = line.split()
            if len(parts) >= 3:          # skip empty lines
                counts[parts[2]] += 1
        return ",".join(f"{level}:{counts[level]}" for level in sorted(counts))
    ```
    
    **Why it works**
    
    * Split into lines, split each line into words, and count the third word. `line.split()` with no argument splits
      on any run of spaces and returns `[]` for an empty line, which the length check skips.
    * `S.split("\n")` on text that ends with a newline gives a final `""`; code that does `line.split(" ")[2]`
      without a check crashes with `IndexError` on it, and a crash scores 0 on that test.
    * **Return the exact format asked for**: a string, comma-separated, sorted, no spaces, `""` when empty.
      An f-string and `",".join(...)` build it cleanly.
    
    **Cost:** O(L) time for L characters of input, O(1) memory besides the counts.
    
    **The slow answer:** speed is not the trap in this task; any answer that reads the input once is fast enough. The hidden tests check the rules and the edge cases.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty text: `solution('')` returns `''`;
    * edge case, only blank lines: `solution('\n\n')` returns `''`;
    * edge case, no message after the level: `solution('2026-01-01 00:00:00 WARN')` returns `'WARN:1'`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.008s.
    
    ??? failure "A common wrong answer: crashes on an empty line"
    
        ```python
        def solution(S):
            counts = {}
            for line in S.split("\n"):
                level = line.split(" ")[2]
                counts[level] = counts.get(level, 0) + 1
            return ",".join(f"{k}:{counts[k]}" for k in sorted(counts))
        ```
        
        Checked: example: IndexError list index out of range.
    
    ??? failure "A common wrong answer: a dict printed instead of the string asked for"
    
        ```python
        from collections import Counter
        
        def solution(S):
            return str(dict(Counter(l.split()[2] for l in S.split("\n") if l.strip())))
        ```
        
        Checked: example: got "{'ERROR': 2, 'INFO': 1}" want 'ERROR:2,INFO:1'.



### 12. Add up durations

**Level:** Easy · **Aim for:** 10 minutes

`D` is a list of job durations, each a string `"HH:MM:SS"`. Return the total as a string in the same form:
hours with **at least two digits** (more if needed; the total may exceed 24 or even 99 hours), then minutes and
seconds with two digits each.

**Examples**

* `solution(['01:30:00', '00:45:30'])` returns `'02:15:30'`
* `solution(['23:59:59', '00:00:01'])` returns `'24:00:00'`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `D`, is within the range [0..100,000];
* each duration has hours 00..99, minutes and seconds 00..59.

Start from:

```python
def solution(D):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(D):
        total = 0
        for d in D:
            h, m, s = map(int, d.split(":"))
            total += h * 3600 + m * 60 + s
        h, rest = divmod(total, 3600)
        m, s = divmod(rest, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    ```
    
    **Why it works**
    
    * Turn everything into **one unit** (seconds), add, then convert back with `divmod`. Adding hours, minutes and
      seconds separately means handling carries by hand.
    * `f"{h:02d}"` pads to two digits but allows more, so 100 hours prints as `100`.
    * `str(datetime.timedelta(seconds=total))` looks handy but prints `1 day, 0:00:00` after 24 hours and `2:15:30`
      without the leading zero.
    
    **Cost:** O(N) time, O(1) memory.
    
    **The slow answer:** speed is not the trap in this task; any answer that reads the input once is fast enough. The hidden tests check the rules and the edge cases.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty list: `solution([])` returns `'00:00:00'`;
    * edge case, over 99 hours: `solution(['99:59:59', '00:00:01'])` returns `'100:00:00'`;
    * edge case, seconds carry into minutes and hours: `solution(['00:59:59', '00:00:01'])` returns `'01:00:00'`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.050s.
    
    ??? failure "A common wrong answer: timedelta prints days"
    
        ```python
        import datetime
        
        def solution(D):
            total = datetime.timedelta()
            for d in D:
                h, m, s = map(int, d.split(":"))
                total += datetime.timedelta(hours=h, minutes=m, seconds=s)
            return str(total)
        ```
        
        Checked: example: got '2:15:30' want '02:15:30'.



### 13. Rows with the wrong number of fields

**Level:** Medium · **Aim for:** 12 minutes

`S` is a CSV file as text: lines separated by `"\n"`, fields separated by `","` (no quotes, no escaped commas).
The text may end with a single newline, which does not start a new line. Return the list of **line numbers
(counting from 1)** whose number of fields is not `K`, in increasing order. An empty line in the middle has one
(empty) field. Return `[]` if `S` is empty.

**Examples**

* `solution('a,b,c\n1,2,3\n4,5\n6,7,8,9\n', 3)` returns `[3, 4]`
* `solution('x,y\n,\n', 2)` returns `[]`

**Write an efficient algorithm for the following assumptions:**

* the length of `S` is within the range [0..1,000,000];
* `K` is an integer within the range [1..100].

Start from:

```python
def solution(S, K):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(S, K):
        if S == "":
            return []
        lines = S.split("\n")
        if S.endswith("\n"):
            lines.pop()          # a final newline ends the last line; it is not a new, empty line
        return [i for i, line in enumerate(lines, start=1) if len(line.split(",")) != K]
    ```
    
    **Why it works**
    
    * `"a,b".split(",")` gives two fields, `"".split(",")` gives one (an empty field), and `",".split(",")` gives two;
      that matches how CSV counts fields.
    * The only trap is the final newline: `"a\nb\n".split("\n")` is `["a", "b", ""]`, and that last `""` is not a
      row. `str.splitlines()` drops it for you; the reference answer uses that.
    * `enumerate(..., start=1)` gives 1-based line numbers directly. Return a **list**, as asked.
    * Real CSV files can have quoted fields with commas inside; then use the standard `csv` module. This task says
      there are none.
    
    **Cost:** O(L) time for L characters of input.
    
    **The slow answer:** speed is not the trap in this task; any answer that reads the input once is fast enough. The hidden tests check the rules and the edge cases.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty file: `solution('', 2)` returns `[]`;
    * edge case, empty line in the middle: `solution('a,b\n\nc,d', 2)` returns `[2]`;
    * edge case, no trailing newline: `solution('a\nb,c', 1)` returns `[2]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.019s.
    
    ??? failure "A common wrong answer: counts the final newline as a bad row"
    
        ```python
        def solution(S, K):
            if S == "":
                return []
            return [i for i, line in enumerate(S.split("\n"), 1) if len(line.split(",")) != K]
        ```
        
        Checked: example: got [3, 4, 5] want [3, 4].



### 14. Compare version numbers

**Level:** Easy · **Aim for:** 10 minutes

`A` and `B` are version numbers such as `"1.10.2"`: whole numbers separated by dots. Return `1` if `A` is newer,
`-1` if `B` is newer and `0` if they are the same version. Missing parts count as 0, so `"1.2"` and `"1.2.0"` are
the same; leading zeros do not matter (`"1.02"` equals `"1.2"`).

**Examples**

* `solution('1.10.2', '1.9')` returns `1`
* `solution('2.0', '2')` returns `0`
* `solution('0.9.1', '0.10')` returns `-1`

**Write an efficient algorithm for the following assumptions:**

* each string has 1 to 50 parts; each part is 1 to 9 digits.

Start from:

```python
def solution(A, B):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from itertools import zip_longest
    
    def solution(A, B):
        a = [int(p) for p in A.split(".")]
        b = [int(p) for p in B.split(".")]
        for x, y in zip_longest(a, b, fillvalue=0):
            if x != y:
                return 1 if x > y else -1
        return 0
    ```
    
    **Why it works**
    
    * Compare **numbers**, part by part. As text, `"10" < "9"` because `"1"` comes before `"9"`; as floats, `1.10`
      equals `1.1`.
    * `itertools.zip_longest(..., fillvalue=0)` pads the shorter version with zeros, which is what "missing parts
      count as 0" means. `int("02")` is 2, which handles leading zeros.
    
    **Cost:** O(P) time for P parts.
    
    **The slow answer:** speed is not the trap in this task; any answer that reads the input once is fast enough. The hidden tests check the rules and the edge cases.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, leading zeros: `solution('1.02', '1.2')` returns `0`;
    * edge case, trailing zeros: `solution('1.0.0.0', '1')` returns `0`;
    * edge case, longer is newer: `solution('1.0.1', '1')` returns `1`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    
    ??? failure "A common wrong answer: comparing strings"
    
        ```python
        def solution(A, B):
            return (A > B) - (A < B)
        ```
        
        Checked: example: got -1 want 1.
    
    ??? failure "A common wrong answer: comparing as floats"
    
        ```python
        def solution(A, B):
            a, b = float(".".join(A.split(".")[:2])), float(".".join(B.split(".")[:2]))
            return (a > b) - (a < b)
        ```
        
        Checked: example: got -1 want 1.



### 15. Days with no data

**Level:** Medium · **Aim for:** 12 minutes

`D` lists the dates (`"YYYY-MM-DD"`) on which a daily feed arrived, in any order, possibly with repeats. Return the
list of **dates between the earliest and the latest date that are missing**, in increasing order, in the same
format.

**Examples**

* `solution(['2026-03-03', '2026-02-27', '2026-03-01', '2026-03-01'])` returns `['2026-02-28', '2026-03-02']`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* all dates are valid and between 2000-01-01 and 2099-12-31.

Start from:

```python
def solution(D):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from datetime import date, timedelta
    
    def solution(D):
        if not D:
            return []
        have = {date.fromisoformat(d) for d in D}
        day, last = min(have), max(have)
        missing = []
        while day < last:
            day += timedelta(days=1)
            if day not in have:
                missing.append(day.isoformat())
        return missing
    ```
    
    **Why it works**
    
    * Let the standard `datetime` module do calendar arithmetic: `date.fromisoformat`, `+ timedelta(days=1)`,
      `.isoformat()`. It knows month lengths and leap years (two edge cases check them).
    * Put the dates you have in a **set** so each "is this day present?" check is O(1).
    * `min` and `max` of ISO date strings also work as text, because `YYYY-MM-DD` sorts in calendar order.
    * Building dates by hand ("day + 1, and if it is over 30...") is where bugs live.
    
    **Cost:** O(N + R) time for R days in the range, O(N) memory.
    
    **The slow answer:** Checking `day in D` on the list instead of a set: O(N·R).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `[]`;
    * edge case, one date: `solution(['2026-01-01'])` returns `[]`;
    * edge case, leap year: `solution(['2024-02-28', '2024-03-01'])` returns `['2024-02-29']`;
    * edge case, over new year: `solution(['2025-12-30', '2026-01-02'])` returns `['2025-12-31', '2026-01-01']`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.046s.
    
    ??? failure "A common wrong answer: adding 1 to the day number"
    
        ```python
        def solution(D):
            if not D:
                return []
            have = set(D)
            lo, hi = min(D), max(D)
            out = []
            y, m, d = map(int, lo.split("-"))
            cur = lo
            while cur < hi:
                d += 1
                if d > 30:
                    d = 1
                    m += 1
                    if m > 12:
                        m, y = 1, y + 1
                cur = "%04d-%02d-%02d" % (y, m, d)
                if cur < hi and cur not in have:
                    out.append(cur)
            return out
        ```
        
        Checked: example: got ['2026-02-28', '2026-02-29', '2026-02-30', '2026-03-02'] want ['2026-02-28', '2026-03-02'].
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        import datetime
        
        def solution(D):
            if not D:
                return []
            lo, hi = min(D), max(D)
            out = []
            d = datetime.date.fromisoformat(lo)
            while d.isoformat() < hi:
                if d.isoformat() not in D:
                    out.append(d.isoformat())
                d = datetime.date.fromordinal(d.toordinal() + 1)
            return out
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.046s).



### 16. Longest gap between logins

**Level:** Medium · **Aim for:** 15 minutes

`L` lists login times `"YYYY-MM-DD HH:MM"` in no particular order; the same time can appear more than once.
Return the longest gap, in minutes, between two logins that follow each other in time. Return 0 if there are
fewer than two logins.

**Examples**

* `solution(['2026-03-01 09:00', '2026-03-01 08:30', '2026-03-01 09:05'])` returns `30`
* `solution(['2026-03-01 23:50', '2026-03-02 00:10'])` returns `20`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* all times are valid and between 2000-01-01 00:00 and 2099-12-31 23:59.

Start from:

```python
def solution(L):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from datetime import datetime
    
    def solution(L):
        times = sorted(datetime.strptime(s, "%Y-%m-%d %H:%M") for s in L)
        best = 0
        for a, b in zip(times, times[1:]):
            best = max(best, int((b - a).total_seconds()) // 60)
        return best
    ```
    
    **Why it works**
    
    * Turn each string into a `datetime`, sort, and compare neighbours. Subtracting two `datetime`s gives a
      `timedelta`; `total_seconds() // 60` is whole minutes. Dates take care of midnight and month ends for you.
    * Times written `YYYY-MM-DD HH:MM` also sort correctly **as text**, so sorting the strings first is fine. What
      fails is doing arithmetic on the clock part only (`HH*60 + MM`): across midnight, 00:10 minus 23:50 is
      negative.
    * `datetime.fromisoformat(s)` also reads this format on any Python 3.7 or newer and is faster than `strptime`.
      100,000 `strptime` calls took about 0.4 s here, within the limit.
    
    **Cost:** O(N log N) time for the sort, O(N) memory.
    
    **The slow answer:** speed is not the trap in this task; any answer that reads the input once is fast enough. The hidden tests check the rules and the edge cases.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `0`;
    * edge case, one login: `solution(['2026-03-01 10:00'])` returns `0`;
    * edge case, the same time twice: `solution(['2026-03-01 10:00', '2026-03-01 10:00'])` returns `0`;
    * edge case, across a month end: `solution(['2026-02-28 23:00', '2026-03-01 01:00'])` returns `120`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.562s.
    
    ??? failure "A common wrong answer: minutes of the day only (breaks at midnight)"
    
        ```python
        def solution(L):
            mins = sorted(int(s[11:13]) * 60 + int(s[14:16]) for s in L)
            return max([b - a for a, b in zip(mins, mins[1:])] + [0])
        ```
        
        Checked: example: got 1420 want 20.
    
    ??? failure "A common wrong answer: not sorting first"
    
        ```python
        from datetime import datetime
        
        def solution(L):
            times = [datetime.strptime(s, "%Y-%m-%d %H:%M") for s in L]
            best = 0
            for a, b in zip(times, times[1:]):
                best = max(best, int((b - a).total_seconds()) // 60)
            return best
        ```
        
        Checked: example: got 35 want 30.



### 17. Events per ISO week

**Level:** Medium · **Aim for:** 15 minutes

`D` is a list of dates `"YYYY-MM-DD"`, one per event. Count the events in each **ISO week** (weeks start on
Monday, and week 1 of a year is the week that contains that year's first Thursday). Return a list of
`(week, count)` tuples, where `week` is written `"YYYY-Www"` with the ISO year and a two-digit week number (for
example `"2025-W01"`), sorted by week.

**Examples**

* `solution(['2026-03-02', '2026-03-08', '2026-03-09'])` returns `[('2026-W10', 2), ('2026-W11', 1)]`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* all dates are valid and between 2000-01-01 and 2099-12-31.

Start from:

```python
def solution(D):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import Counter
    from datetime import date
    
    def solution(D):
        counts = Counter()
        for d in D:
            year, week, _ = date.fromisoformat(d).isocalendar()   # the ISO year, not d's year
            counts[f"{year}-W{week:02d}"] += 1
        return sorted(counts.items())
    ```
    
    **Why it works**
    
    * `date.isocalendar()` returns the ISO year, week number and weekday. **The ISO year is not always the calendar
      year**: 30 December 2024 belongs to week 1 of 2025, and 1 January 2021 to week 53 of 2020. Building the label
      from `d.year` gets exactly those days wrong.
    * `strftime("%W")` is a different week numbering (weeks start on Monday, but week 1 starts at the first Monday,
      and days before it are week 0). `%G-W%V` gives the ISO label, but `%Y-W%V` mixes the calendar year with the ISO
      week. Both wrong answers below were run and fail the year-end cases.
    * Sorting the labels as text works because they are fixed width: year first, then a two-digit week.
    
    **Cost:** O(N + W log W) time for W different weeks.
    
    **The slow answer:** speed is not the trap in this task; any answer that reads the input once is fast enough. The hidden tests check the rules and the edge cases.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `[]`;
    * edge case, 30 December 2024 is in week 1 of 2025: `solution(['2024-12-29', '2024-12-30', '2025-01-01'])` returns `[('2024-W52', 1), ('2025-W01', 2)]`;
    * edge case, 1 January 2021 is in week 53 of 2020: `solution(['2021-01-01', '2021-01-04'])` returns `[('2020-W53', 1), ('2021-W01', 1)]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.107s.
    
    ??? failure "A common wrong answer: %Y-W%V: calendar year with the ISO week"
    
        ```python
        from collections import Counter
        from datetime import date
        
        def solution(D):
            c = Counter(date.fromisoformat(d).strftime("%Y-W%V") for d in D)
            return sorted(c.items())
        ```
        
        Checked: edge: 30 December 2024 is in week 1 of 2025: got [('2024-W01', 1), ('2024-W52', 1), ('2025-W01', 1)] want [('2024-W52', 1), ('2025-W01', 2)].
    
    ??? failure "A common wrong answer: %W is not the ISO week"
    
        ```python
        from collections import Counter
        from datetime import date
        
        def solution(D):
            c = Counter(date.fromisoformat(d).strftime("%Y-W%W") for d in D)
            return sorted(c.items())
        ```
        
        Checked: example: got [('2026-W09', 2), ('2026-W10', 1)] want [('2026-W10', 2), ('2026-W11', 1)].



### 18. Parse a query string

**Level:** Easy · **Aim for:** 10 minutes

`S` is the part of a web address after the `?`, such as `"a=1&b=2&a=3"`. Split it on `&` into parts and skip
empty parts. In each part, the **key** is everything before the first `=` and the **value** everything after it
(the value may itself contain `=`). A part with no `=` has the value `""`. Return a `dict` that maps each key to
the **list** of its values, in the order they appear.

**Examples**

* `solution('a=1&b=2&a=3')` returns `{'a': ['1', '3'], 'b': ['2']}`
* `solution('flag&x=')` returns `{'flag': [''], 'x': ['']}`

**Write an efficient algorithm for the following assumptions:**

* the length of `S` is within the range [0..1,000,000];
* `S` does not contain spaces.

Start from:

```python
def solution(S):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(S):
        out = {}
        for part in S.split("&"):
            if not part:
                continue                                  # "&&" or a trailing "&"
            key, _, value = part.partition("=")           # split at the FIRST "=" only
            out.setdefault(key, []).append(value)
        return out
    ```
    
    **Why it works**
    
    * `str.partition("=")` splits at the **first** `=` and always returns three parts, so a missing `=` gives an
      empty value with no special case. `split("=", 1)` also splits once, but returns one item when there is no `=`.
    * `dict.setdefault(key, [])` returns the list for `key`, creating it the first time: the shortest way to group
      values in a dict. `collections.defaultdict(list)` does the same, but the task asks for a plain `dict`, so you
      would have to convert it.
    * Repeated keys keep **all** values in order; `out[key] = value` would keep only the last one.
    
    **Cost:** O(L) time for L characters.
    
    **The slow answer:** speed is not the trap in this task; any answer that reads the input once is fast enough. The hidden tests check the rules and the edge cases.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty string: `solution('')` returns `{}`;
    * edge case, empty parts: `solution('&&a=1&')` returns `{'a': ['1']}`;
    * edge case, = inside the value: `solution('token=ab==&q=x=y')` returns `{'token': ['ab=='], 'q': ['x=y']}`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.020s.
    
    ??? failure "A common wrong answer: split('=') breaks on a second ="
    
        ```python
        def solution(S):
            out = {}
            for part in S.split("&"):
                if part:
                    if "=" in part:
                        key, value = part.split("=")
                    else:
                        key, value = part, ""
                    out.setdefault(key, []).append(value)
            return out
        ```
        
        Checked: edge: = inside the value: ValueError too many values to unpack (expected 2).
    
    ??? failure "A common wrong answer: only the last value of each key"
    
        ```python
        def solution(S):
            out = {}
            for part in S.split("&"):
                if part:
                    key, _, value = part.partition("=")
                    out[key] = [value]
            return out
        ```
        
        Checked: example: got {'a': ['3'], 'b': ['2']} want {'a': ['1', '3'], 'b': ['2']}.



### 19. Sum a column of a CSV file

**Level:** Medium · **Aim for:** 15 minutes

`S` is the text of a CSV file: the first line holds the column names, then one line per row, each line ending
with `"\n"`. Fields are separated by commas. A field that contains a comma or a quote is wrapped in double
quotes, and a quote inside it is written twice (`""`). No field contains a line break, and there are no blank
lines. Return the sum of the integers in the column named `C`; an empty field counts as 0.

**Examples**

* `solution('name,qty\n"Smith, Ana",3\nBen,4\n', 'qty')` returns `7`
* `solution('qty,note\n5,"say ""hi"", ok"\n,\n', 'qty')` returns `5`

**Write an efficient algorithm for the following assumptions:**

* the length of `S` is within the range [1..1,000,000];
* column `C` exists;
* every non-empty field of column `C` is an integer within the range [−1,000,000..1,000,000].

Start from:

```python
def solution(S, C):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    import csv
    import io
    
    def solution(S, C):
        reader = csv.reader(io.StringIO(S))     # handles quotes, commas in quotes, doubled quotes
        header = next(reader)
        col = header.index(C)
        total = 0
        for row in reader:
            if row[col] != "":
                total += int(row[col])
        return total
    ```
    
    **Why it works**
    
    * Use the **`csv` module** from the standard library: it knows the quoting rules, which `line.split(",")` does
      not. `"Smith, Ana"` is one field, and `split` makes it two, so every later column shifts by one.
    * `io.StringIO(S)` makes a string look like a file, which is what `csv.reader` reads.
    * Find the column **by name** from the header (`header.index(C)`) instead of assuming its position.
    * The `csv` module is part of standard Python, so it is allowed wherever "standard library only" applies. Codility
      says to use standard libraries unless the task says otherwise; whether pandas is installed is not known, and
      for a task like this it is not needed.
    
    **Cost:** O(L) time for L characters.
    
    **The slow answer:** speed is not the trap in this task; any answer that reads the input once is fast enough. The hidden tests check the rules and the edge cases.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, header only: `solution('a,b\n', 'b')` returns `0`;
    * edge case, the column is not the first: `solution('note,qty\n"a,b,c",2\nx,-3\n', 'qty')` returns `-1`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.041s.
    
    ??? failure "A common wrong answer: split(',') breaks quoted fields"
    
        ```python
        def solution(S, C):
            lines = S.split("\n")[:-1]
            col = lines[0].split(",").index(C)
            total = 0
            for line in lines[1:]:
                v = line.split(",")[col]
                if v != "":
                    total += int(v)
            return total
        ```
        
        Checked: example: ValueError invalid literal for int() with base 10: ' Ana"'.



### 20. Flatten a nested record

**Level:** Medium · **Aim for:** 15 minutes

`D` is a dictionary whose keys are non-empty strings without dots and whose values are integers or further
dictionaries of the same kind. Return a flat `dict` that maps the **dotted path** of every integer to that
integer: `{"a": 1, "b": {"c": 2}}` becomes `{"a": 1, "b.c": 2}`. An empty dictionary inside `D` adds nothing.

**Examples**

* `solution({'a': 1, 'b': {'c': 2, 'd': {'e': 3}}})` returns `{'a': 1, 'b.c': 2, 'b.d.e': 3}`
* `solution({'x': {}})` returns `{}`

**Write an efficient algorithm for the following assumptions:**

* `D` holds at most 100,000 integers in total;
* dictionaries are nested at most **5,000** levels deep.

Start from:

```python
def solution(D):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(D):
        out = {}
        stack = [("", D)]                        # (path so far, dictionary to visit)
        while stack:
            prefix, d = stack.pop()
            for key, value in d.items():
                path = prefix + key
                if isinstance(value, dict):
                    stack.append((path + ".", value))
                else:
                    out[path] = value
        return out
    ```
    
    **Why it works**
    
    * The natural answer is recursive ("flatten each inner dict and add its keys"), and on ordinary data it is fine.
      But the limits say **5,000 levels**, and Python stops at about 1,000 nested calls by default with
      `RecursionError`. The recursive answer below was run on a 3,000-level input and failed exactly so.
    * An **explicit stack** (a list of "work still to do") replaces the recursion: no depth limit, same result.
      Whenever a Python task allows deep nesting or long chains, use a loop with a stack or a queue.
      (`sys.setrecursionlimit` can be raised, but very deep recursion can then crash the whole process.)
    * A `dict` compares equal regardless of key order, so visiting in stack order is fine.
    
    **Cost:** O(T) time and memory for T keys in all.
    
    **The slow answer:** Not slow but broken: a recursive answer hits Python's recursion limit on deep input.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution({})` returns `{}`;
    * edge case, a key used at two levels: `solution({'a': {'a': 1}, 'b': 2})` returns `{'a.a': 1, 'b': 2}`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.007s.
    
    ??? failure "A common wrong answer: recursion hits Python's limit on deep input"
    
        ```python
        def solution(D):
            out = {}
            for key, value in D.items():
                if isinstance(value, dict):
                    for k, v in solution(value).items():
                        out[key + "." + k] = v
                else:
                    out[key] = value
            return out
        ```
        
        Checked: RecursionError on the large input.



## C. Sorting and intervals

### 21. Sessions from timestamps

**Level:** Medium · **Aim for:** 10 minutes

`T` holds the times (in seconds) of one user's clicks, **in no particular order**. A new session starts when more
than `G` seconds pass since the previous click. Return the number of sessions (0 if there are no clicks).

**Examples**

* `solution([100, 5, 20, 2000], 60)` returns `3`
* `solution([0, 60, 120], 60)` returns `1`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* each element of `T` is an integer within the range [0..1,000,000,000];
* `G` is an integer within the range [0..1,000,000].

Start from:

```python
def solution(T, G):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(T, G):
        if not T:
            return 0
        times = sorted(T)                 # the clicks arrive unordered
        sessions = 1
        for prev, cur in zip(times, times[1:]):
            if cur - prev > G:
                sessions += 1
        return sessions
    ```
    
    **Why it works**
    
    * Sort first; then a session starts at the first click and at every click more than `G` seconds after the
      previous one. `zip(times, times[1:])` walks over neighbouring pairs.
    * The statement says "in no particular order": forgetting to sort is the trap. `sorted(T)` returns a new list and
      leaves the caller's list unchanged; `T.sort()` would change the input in place, which is usually fine in a test
      but worth knowing.
    * The same idea in SQL is the "Count sessions" task in the SQL practice set.
    
    **Cost:** O(N log N) time for the sort, O(N) memory.
    
    **The slow answer:** Checking every click against every other click: O(N²).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no clicks: `solution([], 10)` returns `0`;
    * edge case, same second twice: `solution([7, 7], 0)` returns `1`;
    * edge case, gap of exactly G: `solution([0, 30], 30)` returns `1`;
    * edge case, gap of G + 1: `solution([0, 31], 30)` returns `2`;
    * edge case, out of order, one session: `solution([30, 0, 60], 30)` returns `1`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.033s.
    
    ??? failure "A common wrong answer: not sorting first"
    
        ```python
        def solution(T, G):
            if not T:
                return 0
            s = 1
            for a, b in zip(T, T[1:]):
                if abs(b - a) > G:
                    s += 1
            return s
        ```
        
        Checked: edge: out of order, one session: got 2 want 1.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(T, G):
            n = 0
            for t in set(T):
                if not any(t - G <= u < t for u in T):
                    n += 1
            return n
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.033s).



### 22. Total busy time

**Level:** Medium · **Aim for:** 15 minutes

Job `i` keeps a server busy from time `S[i]` to time `E[i]` (`S[i] < E[i]`). Jobs may overlap. Return the
**total length of time** during which at least one job is running.

**Examples**

* `solution([1, 2, 10], [5, 6, 12])` returns `7`
* `solution([0, 5], [5, 7])` returns `7`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* each element of `S` and `E` is an integer within the range [0..1,000,000,000].

Start from:

```python
def solution(S, E):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(S, E):
        total = 0
        cur_start = cur_end = None
        for s, e in sorted(zip(S, E)):
            if cur_end is None or s > cur_end:      # a gap: close the current block
                if cur_end is not None:
                    total += cur_end - cur_start
                cur_start, cur_end = s, e
            else:                                   # overlaps or touches: extend the block
                cur_end = max(cur_end, e)
        if cur_end is not None:
            total += cur_end - cur_start
        return total
    ```
    
    **Why it works**
    
    * **Merge intervals:** sort jobs by start time, then walk through them keeping one "current block". A job that
      starts after the block ends closes it; otherwise it may stretch the block's end. Add each closed block's length.
    * Sorting makes it O(N log N). Adding up `E[i] - S[i]` counts overlaps twice.
    * `max(cur_end, e)` matters when a short job sits inside a long one (the edge case "one inside another").
    * The reference answer, one entry per time unit, is only usable for tiny times: with times up to a billion it
      would need billions of entries.
    
    **Cost:** O(N log N) time for the sort, O(N) memory.
    
    **The slow answer:** Marking every covered second in a set needs up to a billion entries.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no jobs: `solution([], [])` returns `0`;
    * edge case, one inside another: `solution([0, 2], [10, 3])` returns `10`;
    * edge case, identical jobs: `solution([4, 4], [6, 6])` returns `2`;
    * edge case, jobs not in time order: `solution([10, 0], [12, 5])` returns `7`;
    * 800 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.098s.
    
    ??? failure "A common wrong answer: adding lengths double-counts overlaps"
    
        ```python
        def solution(S, E):
            return sum(e - s for s, e in zip(S, E))
        ```
        
        Checked: example: got 10 want 7.
    
    ??? failure "A common wrong answer: merging without sorting first"
    
        ```python
        def solution(S, E):
            total = 0
            cs = ce = None
            for s, e in zip(S, E):
                if ce is None or s > ce:
                    if ce is not None:
                        total += ce - cs
                    cs, ce = s, e
                else:
                    ce = max(ce, e)
            return total + (ce - cs if ce is not None else 0)
        ```
        
        Checked: edge: jobs not in time order: got 2 want 7.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(S, E):
            busy = set()
            for s, e in zip(S, E):
                busy.update(range(s, e))
            return len(busy)
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.098s).



### 23. Merge maintenance windows

**Level:** Medium · **Aim for:** 15 minutes

Each element of `A` is a maintenance window `[start, end]` with `start < end`; a window covers the time from
`start` up to `end`. Windows that overlap or **touch** (one ends exactly when the other starts) form one longer
window. Return the merged windows as a list of `[start, end]` lists, sorted by start.

**Examples**

* `solution([[1, 3], [2, 6], [8, 10], [15, 18]])` returns `[[1, 6], [8, 10], [15, 18]]`
* `solution([[5, 7], [1, 5]])` returns `[[1, 7]]`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* `0 ≤ start < end ≤ 1,000,000,000`.

Start from:

```python
def solution(A):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A):
        merged = []
        for start, end in sorted(A):                 # by start time
            if merged and start <= merged[-1][1]:    # overlaps or touches the last one
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        return merged
    ```
    
    **Why it works**
    
    * **Sort by start, then one pass.** After sorting, a window can only merge with the last merged window, so you
      compare with `merged[-1]` and either extend it or start a new one.
    * `max(...)` when extending: a window inside the last one (edge case) must not shrink it.
    * `<=` makes touching windows merge, as the task says. Read that rule in every interval task; it is often the
      only difference between two tasks.
    * `sorted(A)` sorts the `[start, end]` lists by start, then end. The lists inside the answer are new lists, so
      changing them does not change the caller's input, which is a good habit.
    
    **Cost:** O(N log N) time for the sort, O(N) memory.
    
    **The slow answer:** Marking every covered second needs up to a billion entries.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `[]`;
    * edge case, one window inside another: `solution([[1, 10], [2, 3], [4, 5]])` returns `[[1, 10]]`;
    * edge case, not in time order: `solution([[8, 9], [1, 2], [2, 4]])` returns `[[1, 4], [8, 9]]`;
    * edge case, identical windows: `solution([[3, 4], [3, 4]])` returns `[[3, 4]]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.135s.
    
    ??? failure "A common wrong answer: not sorting first"
    
        ```python
        def solution(A):
            merged = []
            for start, end in A:
                if merged and start <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], end)
                else:
                    merged.append([start, end])
            return merged
        ```
        
        Checked: example: got [[5, 7]] want [[1, 7]].
    
    ??? failure "A common wrong answer: end = the new end, without max()"
    
        ```python
        def solution(A):
            merged = []
            for start, end in sorted(A):
                if merged and start <= merged[-1][1]:
                    merged[-1][1] = end
                else:
                    merged.append([start, end])
            return merged
        ```
        
        Checked: edge: one window inside another: got [[1, 3], [4, 5]] want [[1, 10]].
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(A):
            covered = set()
            for s, e in A:
                covered.update(range(s, e))
            out = []
            for t in sorted(covered):
                if out and out[-1][1] == t:
                    out[-1][1] = t + 1
                else:
                    out.append([t, t + 1])
            return out
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.135s).



## D. Prefix sums, sliding windows and two pointers

### 24. Best K consecutive days

**Level:** Easy · **Aim for:** 10 minutes

`A[i]` is the number of rows loaded on day `i`. Return the **largest total of any `K` consecutive days**.

**Examples**

* `solution([2, 1, 5, 1, 3, 2], 3)` returns `9`
* `solution([-5, -2, -9], 1)` returns `-2`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [1..100,000];
* `K` is an integer within the range [1..N];
* each element of `A` is an integer within the range [−10,000..10,000].

Start from:

```python
def solution(A, K):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A, K):
        window = sum(A[:K])
        best = window
        for i in range(K, len(A)):
            window += A[i] - A[i - K]    # slide: add the new day, drop the oldest
            best = max(best, window)
        return best
    ```
    
    **Why it works**
    
    * **Sliding window:** keep the sum of the current `K` days; moving one day forward adds one value and removes
      one. O(N) instead of O(N·K).
    * Start `best` from the first window, not from 0: when every total is negative, 0 would be wrong.
    * Summing each slice from scratch is correct but does up to 2.5 billion additions when `N` is 100,000 and `K`
      is 50,000.
    
    **Cost:** O(N) time, O(1) memory.
    
    **The slow answer:** Re-adding every window from scratch: O(N·K).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, K equals N: `solution([1, 2, 3], 3)` returns `6`;
    * edge case, all negative: `solution([-1, -1, -1], 2)` returns `-2`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.006s.
    
    ??? failure "A common wrong answer: best starts at 0"
    
        ```python
        def solution(A, K):
            best = 0
            w = sum(A[:K])
            best = max(best, w)
            for i in range(K, len(A)):
                w += A[i] - A[i - K]
                best = max(best, w)
            return best
        ```
        
        Checked: example: got 0 want -2.
    
    ??? failure "A common wrong answer: re-summing every window (too slow)"
    
        ```python
        def solution(A, K):
            return max(sum(A[i:i + K]) for i in range(len(A) - K + 1))
        ```
        
        Checked: timed out after 5.0s on the large input.



### 25. Biggest rise in a sensor reading

**Level:** Easy · **Aim for:** 10 minutes

`A[i]` is a sensor reading at minute `i`. Return the biggest rise `A[j] − A[i]` with `i < j`. If the reading never
rises (or there are fewer than two readings), return 0.

**Examples**

* `solution([7, 1, 5, 3, 6, 4])` returns `5`
* `solution([9, 8, 2])` returns `0`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* each element of `A` is an integer within the range [−1,000,000..1,000,000].

Start from:

```python
def solution(A):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A):
        best = 0
        low = None                      # lowest reading so far
        for x in A:
            if low is not None:
                best = max(best, x - low)
            if low is None or x < low:
                low = x
        return best
    ```
    
    **Why it works**
    
    * Walk once and remember the **lowest reading so far**. The best rise ending at minute `j` is `A[j]` minus that
      low; the answer is the best of those. O(N) time, O(1) memory. This is the idea of Codility's lesson 9
      ("maximum slice").
    * `max(A) - min(A)` ignores the order: in `[5, 9, 1]` it gives 8, but the 1 comes after the 9.
    * Starting `best` at 0 makes "never rises" return 0 with no special case.
    
    **Cost:** O(N) time, O(1) memory.
    
    **The slow answer:** Trying every pair: O(N²).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `0`;
    * edge case, one reading: `solution([4])` returns `0`;
    * edge case, the lowest value comes last: `solution([5, 9, 1])` returns `4`;
    * edge case, negative readings: `solution([-5, -9, -2])` returns `7`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.009s.
    
    ??? failure "A common wrong answer: max(A) - min(A) ignores the order"
    
        ```python
        def solution(A):
            return max(A) - min(A) if A else 0
        ```
        
        Checked: example: got 6 want 5.
    
    ??? failure "A common wrong answer: every pair (right, too slow)"
    
        ```python
        def solution(A):
            best = 0
            for i in range(len(A)):
                for j in range(i + 1, len(A)):
                    best = max(best, A[j] - A[i])
            return best
        ```
        
        Checked: timed out after 5.0s on the large input.



### 26. Pairs within a budget

**Level:** Medium · **Aim for:** 15 minutes

`P` lists prices, in no particular order. Return the number of pairs of **different positions** `i < j` with
`P[i] + P[j] ≤ K`.

**Examples**

* `solution([4, 1, 3, 2], 5)` returns `4`
* `solution([5, 5], 9)` returns `0`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* each element of `P` and `K` are integers within the range [0..1,000,000,000].

Start from:

```python
def solution(P, K):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(P, K):
        p = sorted(P)
        i, j = 0, len(p) - 1
        pairs = 0
        while i < j:
            if p[i] + p[j] <= K:
                pairs += j - i      # p[i] fits with every price from i+1 up to j
                i += 1
            else:
                j -= 1              # p[j] is too big for anything left
        return pairs
    ```
    
    **Why it works**
    
    * **Sort, then two pointers** from both ends. If the smallest plus the largest fits, the smallest fits with
      *every* price between them, so add `j - i` at once and move the left pointer. If it does not fit, the largest
      price fits with nothing left, so move the right pointer. O(N log N) for the sort, then O(N).
    * The answer can be close to 5 billion (100,000 × 99,999 / 2). Python integers do not overflow; in other languages
      this is a trap.
    * Equal prices are different positions, so `[2, 2, 2]` with `K = 4` has 3 pairs.
    
    **Cost:** O(N log N) time for the sort, then O(N).
    
    **The slow answer:** Trying every pair: O(N²).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([], 10)` returns `0`;
    * edge case, equal prices: `solution([2, 2, 2], 4)` returns `3`;
    * edge case, one price: `solution([1], 100)` returns `0`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.036s.
    
    ??? failure "A common wrong answer: counting a price paired with itself"
    
        ```python
        def solution(P, K):
            p = sorted(P)
            i, j = 0, len(p) - 1
            pairs = 0
            while i <= j:
                if p[i] + p[j] <= K:
                    pairs += j - i + 1
                    i += 1
                else:
                    j -= 1
            return pairs
        ```
        
        Checked: example: got 6 want 4.
    
    ??? failure "A common wrong answer: two loops (right, too slow)"
    
        ```python
        def solution(P, K):
            n = len(P)
            return sum(1 for i in range(n) for j in range(i + 1, n) if P[i] + P[j] <= K)
        ```
        
        Checked: timed out after 5.0s on the large input.



### 27. Many range totals

**Level:** Medium · **Aim for:** 12 minutes

For each query `i`, compute the total of `A[P[i]]` to `A[Q[i]]` inclusive (`P[i] <= Q[i]`). Return the list of
totals, one per query, in order.

**Examples**

* `solution([3, 1, 4, 1, 5], [0, 1, 4], [2, 3, 4])` returns `[8, 6, 5]`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `A`, and `M`, the number of queries, are within the range [1..100,000];
* each element of `A` is an integer within the range [−1,000..1,000].

Start from:

```python
def solution(A, P, Q):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A, P, Q):
        prefix = [0]
        for x in A:
            prefix.append(prefix[-1] + x)     # prefix[k] = A[0] + ... + A[k-1]
        return [prefix[q + 1] - prefix[p] for p, q in zip(P, Q)]
    ```
    
    **Why it works**
    
    * **Prefix sums:** one pass builds `prefix`, then each query is one subtraction. O(N + M) instead of O(N·M).
    * Note the `+ 1`: `prefix` has one more entry than `A`, and the slice is inclusive of `Q[i]`.
    * Same idea as Codility's lesson 5 tasks; see [Codility's own tasks](codility-tasks.md).
    
    **Cost:** O(N + M) time, O(N) memory.
    
    **The slow answer:** Summing each slice separately: O(N·M).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, whole array: `solution([1, 2], [0], [1])` returns `[3]`;
    * edge case, single element: `solution([7], [0], [0])` returns `[7]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.011s.
    
    ??? failure "A common wrong answer: summing each slice (too slow)"
    
        ```python
        def solution(A, P, Q):
            return [sum(A[p:q + 1]) for p, q in zip(P, Q)]
        ```
        
        Checked: timed out after 5.0s on the large input.
    
    ??? failure "A common wrong answer: off by one at the end"
    
        ```python
        def solution(A, P, Q):
            prefix = [0]
            for x in A:
                prefix.append(prefix[-1] + x)
            return [prefix[q] - prefix[p] for p, q in zip(P, Q)]
        ```
        
        Checked: example: got [4, 5, 0] want [8, 6, 5].



### 28. Slices that sum to K

**Level:** Medium · **Aim for:** 18 minutes

Return the number of **slices** (runs of one or more consecutive elements) of `A` whose sum is exactly `K`.
Elements may be negative.

**Examples**

* `solution([1, 2, 3, -3, 3], 3)` returns `5`
* `solution([0, 0], 0)` returns `3`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* each element of `A` and `K` are integers within the range [−1,000..1,000].

Start from:

```python
def solution(A, K):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import defaultdict
    
    def solution(A, K):
        seen = defaultdict(int)
        seen[0] = 1                 # the empty prefix
        prefix = count = 0
        for x in A:
            prefix += x
            count += seen[prefix - K]   # earlier prefixes that leave exactly K
            seen[prefix] += 1
        return count
    ```
    
    **Why it works**
    
    * The sum of slice `A[i..j]` is `prefix[j+1] - prefix[i]`. It equals `K` exactly when an earlier prefix sum was
      `prefix - K`. Keep a dict of how many times each prefix sum has appeared: one pass, O(N).
    * Start with `seen[0] = 1` so slices that begin at index 0 are counted.
    * A sliding window (move the left edge when the sum is too big) only works when all numbers are positive; with
      negatives it misses slices.
    
    **Cost:** O(N) time, O(N) memory.
    
    **The slow answer:** Adding up every slice: O(N²) slices.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([], 0)` returns `0`;
    * edge case, negatives: `solution([-1, -1, 1], -1)` returns `3`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.055s.
    
    ??? failure "A common wrong answer: sliding window assumes positive numbers"
    
        ```python
        def solution(A, K):
            left = s = count = 0
            for right, x in enumerate(A):
                s += x
                while s > K and left <= right:
                    s -= A[left]
                    left += 1
                if s == K and left <= right:
                    count += 1
            return count
        ```
        
        Checked: example: got 3 want 5.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(A, K):
            n = len(A)
            return sum(1 for i in range(n) for j in range(i, n) if sum(A[i:j + 1]) == K)
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.055s).



### 29. Shortest stretch reaching a target

**Level:** Medium · **Aim for:** 15 minutes

All values in `A` are positive. Return the length of the **shortest run of consecutive elements whose total is at
least `S`**, or 0 if no run reaches `S`.

**Examples**

* `solution([2, 3, 1, 2, 4, 3], 7)` returns `2`
* `solution([1, 1, 1], 5)` returns `0`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* each element of `A` is an integer within the range [1..10,000];
* `S` is an integer within the range [1..1,000,000,000].

Start from:

```python
def solution(A, S):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A, S):
        best = len(A) + 1
        left = total = 0
        for right, x in enumerate(A):
            total += x
            while total >= S:              # shrink from the left while still enough
                best = min(best, right - left + 1)
                total -= A[left]
                left += 1
        return best if best <= len(A) else 0
    ```
    
    **Why it works**
    
    * Because every value is positive, adding an element can only raise the total and removing one can only lower
      it. So two pointers work: grow on the right, and while the total is big enough, record the length and shrink
      from the left. O(N).
    * With negative values this shortcut breaks (compare "Slices that sum to K").
    * `best` starts at an impossible value (`len(A) + 1`) so "never found" is easy to detect.
    
    **Cost:** O(N) time, O(1) memory.
    
    **The slow answer:** Trying every start and end: O(N²).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([], 3)` returns `0`;
    * edge case, one element is enough: `solution([1, 9, 1], 9)` returns `1`;
    * edge case, needs the whole array: `solution([2, 2, 2], 6)` returns `3`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.020s.
    
    ??? failure "A common wrong answer: stops at the first stretch found, not the shortest"
    
        ```python
        def solution(A, S):
            total = 0
            for right, x in enumerate(A):
                total += x
                if total >= S:
                    return right + 1
            return 0
        ```
        
        Checked: example: got 4 want 2.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(A, S):
            n = len(A)
            for length in range(1, n + 1):
                for i in range(n - length + 1):
                    if sum(A[i:i + length]) >= S:
                        return length
            return 0
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.020s).



### 30. Longest stretch with at most K kinds

**Level:** Medium · **Aim for:** 18 minutes

Return the length of the **longest run of consecutive elements of `A` that contains at most `K` different
values**.

**Examples**

* `solution([1, 2, 1, 3, 3, 4, 3], 2)` returns `4`
* `solution([5, 5, 5], 1)` returns `3`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* `K` is an integer within the range [1..N+1];
* each element of `A` is an integer within the range [0..1,000,000,000].

Start from:

```python
def solution(A, K):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import defaultdict
    
    def solution(A, K):
        count = defaultdict(int)
        left = best = 0
        for right, x in enumerate(A):
            count[x] += 1
            while len(count) > K:          # too many kinds: move the left edge
                y = A[left]
                count[y] -= 1
                if count[y] == 0:
                    del count[y]           # so len(count) is the number of kinds
                left += 1
            best = max(best, right - left + 1)
        return best
    ```
    
    **Why it works**
    
    * **Two pointers (the caterpillar):** extend the right edge one step at a time; whenever the window holds more
      than `K` kinds, move the left edge until it is valid again. Each element enters and leaves once: O(N).
    * Keep a count per value and **delete a value when its count reaches 0**; otherwise `len(count)` keeps counting
      values that have left the window.
    
    **Cost:** O(N) time, O(K) memory.
    
    **The slow answer:** Growing a window from every start: O(N²) when the whole list has K kinds or fewer.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([], 1)` returns `0`;
    * edge case, K larger than the number of values: `solution([1, 2, 3], 5)` returns `3`;
    * edge case, all different, K = 1: `solution([1, 2, 3], 1)` returns `1`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.028s.
    
    ??? failure "A common wrong answer: not deleting zero counts"
    
        ```python
        from collections import defaultdict
        
        def solution(A, K):
            count = defaultdict(int)
            left = best = 0
            for right, x in enumerate(A):
                count[x] += 1
                while len(count) > K and left <= right:
                    count[A[left]] -= 1
                    left += 1
                best = max(best, right - left + 1)
            return best
        ```
        
        Checked: example: got 3 want 4.



## E. Stacks

### 31. Deepest bracket nesting

**Level:** Easy · **Aim for:** 10 minutes

`S` is an expression that may contain round brackets and other characters. If the brackets are **properly
nested** (every `(` is closed by a later `)`, and no `)` comes before its `(`), return the **maximum nesting
depth** (0 if there are no brackets). Otherwise return `-1`.

**Examples**

* `solution('(a+(b*c))+(d)')` returns `2`
* `solution('a)(b')` returns `-1`
* `solution('x+y')` returns `0`

**Write an efficient algorithm for the following assumptions:**

* the length of `S` is within the range [0..200,000].

Start from:

```python
def solution(S):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(S):
        depth = best = 0
        for ch in S:
            if ch == "(":
                depth += 1
                best = max(best, depth)
            elif ch == ")":
                depth -= 1
                if depth < 0:          # a ")" with nothing open
                    return -1
        return best if depth == 0 else -1
    ```
    
    **Why it works**
    
    * With only one kind of bracket, a counter is enough (a stack is needed when there are several kinds, as in
      Codility's Brackets task). Two checks: the counter must **never go below zero**, and it must **end at zero**.
    * Only checking that the numbers of `(` and `)` are equal accepts `")("`.
    
    **Cost:** O(N) time, O(1) memory.
    
    **The slow answer:** speed is not the trap in this task; any answer that reads the input once is fast enough. The hidden tests check the rules and the edge cases.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution('')` returns `0`;
    * edge case, unclosed: `solution('((a)')` returns `-1`;
    * edge case, closing first: `solution(')(')` returns `-1`;
    * edge case, deep: `solution('(' * 1000 + ')' * 1000)` returns `1000`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.011s.
    
    ??? failure "A common wrong answer: only comparing the counts"
    
        ```python
        def solution(S):
            if S.count("(") != S.count(")"):
                return -1
            d = m = 0
            for c in S:
                d += (c == "(") - (c == ")")
                m = max(m, d)
            return m
        ```
        
        Checked: example: got 0 want -1.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(S):
            t = "".join(c for c in S if c in "()")
            best = 0
            while "()" in t:
                best += 1
                t = t.replace("()", "")
            if t:
                return -1
            d = m = 0
            for c in S:
                d += (c == "(") - (c == ")")
                m = max(m, d)
            return m
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.011s).



### 32. Days until a warmer reading

**Level:** Medium · **Aim for:** 18 minutes

`T[i]` is the temperature on day `i`. Return a list `R` of the same length where `R[i]` is the number of days
after day `i` until a **strictly warmer** day, or 0 if there is none.

**Examples**

* `solution([3, 1, 4, 1, 5])` returns `[2, 1, 2, 1, 0]`
* `solution([5, 5, 5])` returns `[0, 0, 0]`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* each element of `T` is an integer within the range [−100..100].

Start from:

```python
def solution(T):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(T):
        R = [0] * len(T)
        waiting = []                      # stack of days still waiting for a warmer day
        for i, t in enumerate(T):
            while waiting and T[waiting[-1]] < t:
                j = waiting.pop()
                R[j] = i - j
            waiting.append(i)
        return R
    ```
    
    **Why it works**
    
    * A **monotonic stack**: it holds the days that have not yet found a warmer day, and their temperatures never
      rise from bottom to top. A new, warmer day answers every colder day on top of the stack.
    * Each day is pushed once and popped at most once, so it is O(N), although it has a loop inside a loop.
    * Looking ahead from every day is O(N²): on 100,000 equal temperatures (no day is ever warmer) that is about 5 billion
      comparisons.
    
    **Cost:** O(N) time, O(N) memory: each day enters and leaves the stack once.
    
    **The slow answer:** Looking ahead from every day: O(N²) when no day is warmer.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `[]`;
    * edge case, falling: `solution([3, 2, 1])` returns `[0, 0, 0]`;
    * edge case, rising: `solution([1, 2, 3])` returns `[1, 1, 0]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.007s.
    
    ??? failure "A common wrong answer: looking ahead from every day (too slow)"
    
        ```python
        def solution(T):
            R = []
            for i in range(len(T)):
                r = 0
                for j in range(i + 1, len(T)):
                    if T[j] > T[i]:
                        r = j - i
                        break
                R.append(r)
            return R
        ```
        
        Checked: timed out after 5.0s on the large input.
    
    ??? failure "A common wrong answer: warmer or equal"
    
        ```python
        def solution(T):
            R = [0] * len(T)
            st = []
            for i, t in enumerate(T):
                while st and T[st[-1]] <= t:
                    j = st.pop()
                    R[j] = i - j
                st.append(i)
            return R
        ```
        
        Checked: example: got [1, 1, 0] want [0, 0, 0].



## F. Graphs and grids

### 33. Groups of linked tables

**Level:** Medium · **Aim for:** 18 minutes

A warehouse has `N` tables numbered `0` to `N − 1`. For each `i`, tables `A[i]` and `B[i]` are linked by a foreign
key. Linked tables, directly or through other tables, form a group. Return the **number of groups** (a table with
no links is a group on its own).

**Examples**

* `solution(5, [0, 1, 3], [1, 2, 4])` returns `2`
* `solution(3, [], [])` returns `3`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* `M`, the length of `A` and `B`, is within the range [0..200,000];
* each element of `A` and `B` is within the range [0..N−1].

Start from:

```python
def solution(N, A, B):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(N, A, B):
        parent = list(range(N))
    
        def find(x):                     # follow parents to the group's root
            while parent[x] != x:
                parent[x] = parent[parent[x]]   # shorten the path as we go
                x = parent[x]
            return x
    
        groups = N
        for a, b in zip(A, B):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb          # join two groups
                groups -= 1
        return groups
    ```
    
    **Why it works**
    
    * **Union-find** (disjoint sets): every table points to a parent; the root names the group. Linking two tables
      joins their roots, and each successful join removes one group from the count.
    * The `find` loop shortens paths as it goes, which keeps it fast; it is a loop, not recursion, so very long
      chains cannot hit Python's recursion limit.
    * A breadth-first search over an adjacency list (`collections.deque`) works just as well; avoid recursive
      depth-first search here for the same reason.
    
    **Cost:** About O(N + M) time (union-find with path shortening), O(N) memory.
    
    **The slow answer:** Relabelling until nothing changes can take one pass per link: O(N·M) on a long chain.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no tables: `solution(0, [], [])` returns `0`;
    * edge case, a table linked to itself: `solution(2, [1], [1])` returns `2`;
    * edge case, a cycle: `solution(3, [0, 1, 2], [1, 2, 0])` returns `1`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.026s.
    
    ??? failure "A common wrong answer: counting links instead of groups"
    
        ```python
        def solution(N, A, B):
            return N - len(A)
        ```
        
        Checked: edge: a table linked to itself: got 1 want 2.



### 34. Count the blocks on a map

**Level:** Medium · **Aim for:** 20 minutes

`G` is a map given as a list of equal-length strings; `"#"` is land and `"."` is water. Land squares that touch
**up, down, left or right** belong to the same block. Return the **number of blocks**.

**Examples**

* `solution(['##..', '#..#', '..##'])` returns `2`
* `solution(['#.#', '.#.', '#.#'])` returns `5`

**Write an efficient algorithm for the following assumptions:**

* the map has 0 to 1,000 rows and 0 to 1,000 columns.

Start from:

```python
def solution(G):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import deque
    
    def solution(G):
        rows = len(G)
        cols = len(G[0]) if rows else 0
        seen = [[False] * cols for _ in range(rows)]
        blocks = 0
        for r in range(rows):
            for c in range(cols):
                if G[r][c] == "#" and not seen[r][c]:
                    blocks += 1
                    seen[r][c] = True
                    queue = deque([(r, c)])          # breadth-first, no recursion
                    while queue:
                        y, x = queue.popleft()
                        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                            if 0 <= ny < rows and 0 <= nx < cols and G[ny][nx] == "#" and not seen[ny][nx]:
                                seen[ny][nx] = True
                                queue.append((ny, nx))
        return blocks
    ```
    
    **Why it works**
    
    * Scan every square; each unvisited land square starts a new block, and a **breadth-first search** marks the
      whole block as seen. Every square is handled once: O(rows × columns).
    * Mark a square as seen **when you add it to the queue**, not when you take it out; otherwise the same square can
      be queued many times.
    * **Why not a recursive search?** It is shorter to write, but a block of a million squares means a million
      nested calls, and Python stops at about 1,000 by default with `RecursionError`. A crash scores 0 on that
      hidden test. Use a `deque` or a list as an explicit stack.
    
    **Cost:** O(rows × columns) time and memory.
    
    **The slow answer:** Not slow but broken: a recursive search on a 1,000 × 1,000 map hits Python's recursion limit.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty map: `solution([])` returns `0`;
    * edge case, all water: `solution(['...', '...'])` returns `0`;
    * edge case, one big block: `solution(['###', '###'])` returns `1`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.878s.
    
    ??? failure "A common wrong answer: recursive search hits the recursion limit"
    
        ```python
        def solution(G):
            rows = len(G)
            cols = len(G[0]) if rows else 0
            seen = set()
        
            def fill(r, c):
                if r < 0 or c < 0 or r >= rows or c >= cols or G[r][c] != "#" or (r, c) in seen:
                    return
                seen.add((r, c))
                fill(r + 1, c); fill(r - 1, c); fill(r, c + 1); fill(r, c - 1)
        
            n = 0
            for r in range(rows):
                for c in range(cols):
                    if G[r][c] == "#" and (r, c) not in seen:
                        n += 1
                        fill(r, c)
            return n
        ```
        
        Checked: RecursionError on the large input.
    
    ??? failure "A common wrong answer: diagonal neighbours joined too"
    
        ```python
        def solution(G):
            cells = {(r, c) for r, row in enumerate(G) for c, ch in enumerate(row) if ch == "#"}
            n = 0
            while cells:
                n += 1
                st = [cells.pop()]
                while st:
                    r, c = st.pop()
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            p = (r + dr, c + dc)
                            if p in cells:
                                cells.remove(p)
                                st.append(p)
            return n
        ```
        
        Checked: example: got 1 want 5.



### 35. Run order for pipeline tasks

**Level:** Hard · **Aim for:** 25 minutes

A pipeline has tasks `0` to `N − 1`. For each `i`, task `A[i]` must finish before task `B[i]` starts. Return a
list with **all tasks in a valid run order**. When several tasks are ready to run, always run the one with the
**smallest number** first, so the answer is unique. If the rules contain a cycle (no valid order exists), return
an empty list.

**Examples**

* `solution(4, [2, 0, 1], [1, 1, 3])` returns `[0, 2, 1, 3]`
* `solution(2, [0, 1], [1, 0])` returns `[]`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [0..100,000];
* `M`, the length of `A` and `B`, is within the range [0..200,000];
* each element of `A` and `B` is within the range [0..N−1], and `A[i] != B[i]`.

Start from:

```python
def solution(N, A, B):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    import heapq
    
    def solution(N, A, B):
        after = [[] for _ in range(N)]
        waiting_on = [0] * N               # how many tasks must finish first
        for a, b in zip(A, B):
            after[a].append(b)
            waiting_on[b] += 1
        ready = [t for t in range(N) if waiting_on[t] == 0]
        heapq.heapify(ready)               # always take the smallest ready task
        order = []
        while ready:
            t = heapq.heappop(ready)
            order.append(t)
            for nxt in after[t]:
                waiting_on[nxt] -= 1
                if waiting_on[nxt] == 0:
                    heapq.heappush(ready, nxt)
        return order if len(order) == N else []
    ```
    
    **Why it works**
    
    * This is a **topological sort**, the same thing a workflow scheduler (Airflow, Databricks Jobs) does with a
      DAG. Count, for each task, how many tasks it waits on; tasks waiting on none are ready.
    * Take a ready task, run it, and lower the count of every task after it; any that reach 0 become ready.
      A **heap** (`heapq`) hands out the smallest ready task in O(log N), which the tie rule needs.
    * If some tasks never become ready, they are stuck in a cycle: fewer than `N` tasks were run, so return `[]`.
    * The same rule listed twice is counted twice and released twice, so duplicates need no special care.
    * With a plain list and `min()` instead of a heap, each step scans all ready tasks: O(N²) in the worst case.
    
    **Cost:** O((N + M) log N) time, O(N + M) memory.
    
    **The slow answer:** Using `min()` on a plain list of ready tasks: O(N²).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no rules: `solution(3, [], [])` returns `[0, 1, 2]`;
    * edge case, no tasks: `solution(0, [], [])` returns `[]`;
    * edge case, same rule twice: `solution(2, [1, 1], [0, 0])` returns `[1, 0]`;
    * edge case, a released task is smaller than one already waiting: `solution(3, [0], [1])` returns `[0, 1, 2]`;
    * edge case, a cycle among some tasks only: `solution(3, [1, 2], [2, 1])` returns `[]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.060s.
    
    ??? failure "A common wrong answer: a FIFO queue ignores the smallest-first rule"
    
        ```python
        from collections import deque
        
        def solution(N, A, B):
            after = [[] for _ in range(N)]
            w = [0] * N
            for a, b in zip(A, B):
                after[a].append(b)
                w[b] += 1
            q = deque(t for t in range(N) if w[t] == 0)
            order = []
            while q:
                t = q.popleft()
                order.append(t)
                for n in after[t]:
                    w[n] -= 1
                    if w[n] == 0:
                        q.append(n)
            return order if len(order) == N else []
        ```
        
        Checked: edge: a released task is smaller than one already waiting: got [0, 2, 1] want [0, 1, 2].
    
    ??? failure "A common wrong answer: no cycle check"
    
        ```python
        import heapq
        
        def solution(N, A, B):
            after = [[] for _ in range(N)]
            w = [0] * N
            for a, b in zip(A, B):
                after[a].append(b)
                w[b] += 1
            r = [t for t in range(N) if w[t] == 0]
            heapq.heapify(r)
            order = []
            while r:
                t = heapq.heappop(r)
                order.append(t)
                for n in after[t]:
                    w[n] -= 1
                    if w[n] == 0:
                        heapq.heappush(r, n)
            return order
        ```
        
        Checked: edge: a cycle among some tasks only: got [0] want [].
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(N, A, B):
            done, order = set(), []
            rules = list(zip(A, B))
            while len(order) < N:
                ready = [t for t in range(N) if t not in done and all(a in done for a, b in rules if b == t)]
                if not ready:
                    return []
                t = min(ready)
                done.add(t)
                order.append(t)
            return order
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.060s).



## G. Binary search on the answer

### 36. Smallest daily capacity

**Level:** Hard · **Aim for:** 25 minutes

Files of sizes `W[0], W[1], ...` must be uploaded **in this order** within `D` days. Each day uploads a run of the
next files whose total size is at most the daily capacity `C` (a file cannot be split). Return the **smallest `C`**
that finishes all files within `D` days.

**Examples**

* `solution([3, 2, 2, 4, 1, 4], 3)` returns `6`
* `solution([1, 2, 3, 1, 1], 4)` returns `3`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [1..100,000];
* each element of `W` is within the range [1..10,000];
* `D` is an integer within the range [1..N].

Start from:

```python
def solution(W, D):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(W, D):
        def days_needed(cap):
            days, load = 1, 0
            for w in W:
                if load + w > cap:       # start a new day
                    days += 1
                    load = 0
                load += w
            return days
    
        low, high = max(W), sum(W)      # the answer lies in this range
        while low < high:
            mid = (low + high) // 2
            if days_needed(mid) <= D:
                high = mid               # mid works; try smaller
            else:
                low = mid + 1            # mid is too small
        return low
    ```
    
    **Why it works**
    
    * **Binary search on the answer.** For a given capacity, a greedy pass counts the days needed (fill each day as
      much as possible). A bigger capacity never needs more days, so the "works / does not work" answers form one
      switch from no to yes, and binary search finds the switch.
    * The range: the capacity must be at least the biggest file (`max(W)`) and never needs to exceed the total
      (`sum(W)`, everything in one day).
    * Codility's lesson 14 has tasks of this kind.
    
    **Cost:** O(N log S) time, where S is the total weight: about 30 passes of O(N).
    
    **The slow answer:** Trying every capacity from the largest file up: O(N·S).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, one day: `solution([5, 5, 5], 1)` returns `15`;
    * edge case, one file per day: `solution([5, 9, 2], 3)` returns `9`;
    * edge case, single file: `solution([7], 1)` returns `7`;
    * edge case, files cannot be split: `solution([5, 5, 6], 2)` returns `10`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.140s.
    
    ??? failure "A common wrong answer: average per day is not enough"
    
        ```python
        def solution(W, D):
            return max(max(W), -(-sum(W) // D))
        ```
        
        Checked: edge: files cannot be split: got 8 want 10.
    
    ??? failure "A common wrong answer: trying every capacity (too slow)"
    
        ```python
        def solution(W, D):
            cap = max(W)
            while True:
                days, load = 1, 0
                for w in W:
                    if load + w > cap:
                        days += 1
                        load = 0
                    load += w
                if days <= D:
                    return cap
                cap += 1
        ```
        
        Checked: timed out after 5.0s on the large input.



## H. More data-engineering tasks

Eight more tasks of the kind a data engineer gets: cleaning and counting, merging sorted streams, a change feed with
deletes, row checks, a rate limiter, the busiest hour, a quoted CSV line and a limited forward fill. Standard library
only. Every solution passes its tests (shown inside) on Python 3.9 and 3.13, and 500 random small inputs each,
compared with a slow but obviously correct answer.

### 37. Clean e-mails, count per domain

**Level:** Easy · **Aim for:** 12 minutes

A sign-up form saves e-mail addresses as the user typed them. `A` is a list of those strings. Clean each one:
remove spaces at both ends and make it lower case. A cleaned address is **valid** when it has no space inside,
exactly one `@`, a non-empty part before the `@`, and a domain after it that has a dot which is not its first or
last character. Ignore invalid ones, and count each valid address once even if it appears many times.

Return a list of `(domain, count)` tuples: the number of different valid addresses per domain, the biggest count
first, ties by domain name A to Z.

```text
def solution(A): -> list of (str, int)
```

**Examples**

* `solution([' Ann@Mail.com', 'ann@mail.com', 'bob@mail.com ', 'x@y.org'])` returns `[('mail.com', 2), ('y.org', 1)]`
* `solution(['no-at-sign', 'a@b', '@c.com', 'a@@c.com'])` returns `[]`
* `solution(['a@x.io', 'b@x.io', 'c@a.io', 'd@a.io'])` returns `[('a.io', 2), ('x.io', 2)]`

**Limits:** `len(A)` up to 100,000; each string up to 100 characters.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A):
        seen = set()
        cnt = {}
        for s in A:
            e = s.strip().lower()
            if ' ' in e or e.count('@') != 1:
                continue
            user, dom = e.split('@')
            if not user or '.' not in dom or dom[0] == '.' or dom[-1] == '.':
                continue
            if e in seen:
                continue
            seen.add(e)
            cnt[dom] = cnt.get(dom, 0) + 1
        return sorted(cnt.items(), key=lambda x: (-x[1], x[0]))
    ```

    Clean first, then dedupe on the cleaned text: `' Ann@Mail.com'` and `'ann@mail.com'` are the same person. A common
    slip is to dedupe the raw strings and count Ann twice.

    **Cost:** O(N·L) to clean N strings of length L, plus O(D log D) to sort D domains.

    **Tests**

    ```python
    # tests
    assert solution([' Ann@Mail.com', 'ann@mail.com', 'bob@mail.com ', 'x@y.org']) == [('mail.com', 2), ('y.org', 1)]
    assert solution(['no-at-sign', 'a@b', '@c.com', 'a@@c.com']) == []
    assert solution(['a@x.io', 'b@x.io', 'c@a.io', 'd@a.io']) == [('a.io', 2), ('x.io', 2)]
    assert solution([]) == []
    assert solution(['a b@x.io', 'a@.io', 'a@io.', '   ']) == []
    assert solution(['A@X.IO', 'a@x.io']) == [('x.io', 1)]
    print('task 1: ok')
    ```


### 38. Merge two sorted event streams

**Level:** Easy · **Aim for:** 10 minutes

Two collectors send events as `(time, name)` tuples. `A` and `B` are each already sorted by time. Return one list
with all events of both, sorted by time. When an event in `A` and an event in `B` have the same time, the one from
`A` comes first; events from the same list keep their order. Do it in one pass, without sorting again.

```text
def solution(A, B): -> list of (int, str)
```

**Examples**

* `solution([(1, 'a'), (5, 'b')], [(2, 'x'), (9, 'y')])` returns `[(1, 'a'), (2, 'x'), (5, 'b'), (9, 'y')]`
* `solution([(3, 'a')], [(3, 'x'), (3, 'y')])` returns `[(3, 'a'), (3, 'x'), (3, 'y')]`
* `solution([], [(1, 'x')])` returns `[(1, 'x')]`

**Limits:** each list up to 1,000,000 events; times are integers.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A, B):
        i = j = 0
        out = []
        while i < len(A) and j < len(B):
            if A[i][0] <= B[j][0]:
                out.append(A[i])
                i += 1
            else:
                out.append(B[j])
                j += 1
        return out + A[i:] + B[j:]
    ```

    `<=` and not `<` is what puts `A` first on a tie. In real code `list(heapq.merge(A, B, key=lambda e: e[0]))` does the
    same and keeps the same tie rule, but the interview usually wants the two pointers. Comparing whole tuples
    (`A[i] <= B[j]`) is wrong: it breaks ties by name.

    **Cost:** O(N + M) time and memory. `sorted(A + B)` is O((N+M) log (N+M)) and ignores that the input is sorted.

    **Tests**

    ```python
    # tests
    import random
    assert solution([(1, 'a'), (5, 'b')], [(2, 'x'), (9, 'y')]) == [(1, 'a'), (2, 'x'), (5, 'b'), (9, 'y')]
    assert solution([(3, 'a')], [(3, 'x'), (3, 'y')]) == [(3, 'a'), (3, 'x'), (3, 'y')]
    assert solution([], [(1, 'x')]) == [(1, 'x')]
    assert solution([], []) == []
    assert solution([(2, 'z')], [(2, 'a')]) == [(2, 'z'), (2, 'a')]
    for _ in range(500):
        A = sorted((random.randint(0, 9), random.choice('abc')) for _ in range(random.randint(0, 8)))
        B = sorted((random.randint(0, 9), random.choice('xyz')) for _ in range(random.randint(0, 8)))
        assert solution(A, B) == sorted(A + B, key=lambda e: e[0])   # sorted is stable, so A wins ties
    print('task 2: ok')
    ```


### 39. Final table from a change feed with deletes

**Level:** Medium · **Aim for:** 15 minutes

A database sends its changes as tuples `(time, op, key, value)`, where `op` is `'I'` (insert), `'U'` (update) or
`'D'` (delete, value `None`). The tuples can arrive **out of time order**. Build the table as it is after all
changes: for each key only its change with the latest time counts; if two changes of one key have the same time,
the one later in `R` counts. A key whose latest change is a delete is not in the table.

Return the table as a list of `(key, value)` tuples sorted by key.

```text
def solution(R): -> list of (str, str)
```

**Examples**

* `solution([(1, 'I', 'a', 'x'), (2, 'U', 'a', 'y'), (1, 'I', 'b', 'z')])` returns `[('a', 'y'), ('b', 'z')]`
* `solution([(5, 'D', 'a', None), (3, 'U', 'a', 'old')])` returns `[]`
* `solution([(4, 'D', 'k', None), (4, 'I', 'k', 'back')])` returns `[('k', 'back')]`

**Limits:** `len(R)` up to 200,000.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(R):
        last = {}
        for t, op, key, val in R:
            if key not in last or t >= last[key][0]:
                last[key] = (t, op, val)
        return sorted((k, v[2]) for k, v in last.items() if v[1] != 'D')
    ```

    Keep the delete as a record in the dict and drop deleted keys only at the end. The common wrong answer removes the
    key the moment a delete arrives (`last.pop(key)`); then an older update that arrives later (example 2) puts it back.

    **Cost:** O(N + K log K) for K keys, O(K) memory.

    **Tests**

    ```python
    # tests
    import random
    assert solution([(1, 'I', 'a', 'x'), (2, 'U', 'a', 'y'), (1, 'I', 'b', 'z')]) == [('a', 'y'), ('b', 'z')]
    assert solution([(5, 'D', 'a', None), (3, 'U', 'a', 'old')]) == []
    assert solution([(4, 'D', 'k', None), (4, 'I', 'k', 'back')]) == [('k', 'back')]
    assert solution([]) == []

    def slow(R):
        out = []
        for k in sorted({r[2] for r in R}):
            t, i, op, val = max((r[0], i, r[1], r[3]) for i, r in enumerate(R) if r[2] == k)
            if op != 'D':
                out.append((k, val))
        return out

    for _ in range(500):
        R = []
        for _ in range(random.randint(0, 10)):
            op = random.choice('IUD')
            R.append((random.randint(0, 4), op, random.choice('abc'), None if op == 'D' else random.choice('pqrs')))
        assert solution(R) == slow(R)
    print('task 3: ok')
    ```


### 40. Check every row of an upload

**Level:** Medium · **Aim for:** 20 minutes

`S` is a CSV text: lines split by `"\n"`, fields by `","`, no quotes. Line 1 is the header `id,date,amount`.
Blank lines are skipped. Each other line is checked in this order, and only its **first** problem is reported:

1. `'fields'`: it does not have exactly 3 fields;
2. `'id'`: the id is not a whole number of digits `0-9` greater than 0;
3. `'duplicate'`: the same id (as a number, so `7` and `007` are the same) was already used on an earlier line
   whose id passed check 2;
4. `'date'`: the date is not a real date written `YYYY-MM-DD`;
5. `'amount'`: the amount is not digits with an optional dot and one or two more digits (`12`, `3.5`, `0.99`).

Return a list of `(line number, problem)` for the bad lines, line numbers counted from 1 (the header is line 1).

```text
def solution(S): -> list of (int, str)
```

**Examples**

* `solution('id,date,amount\n1,2026-01-31,9.99\n2,2026-02-30,5\n')` returns `[(3, 'date')]`
* `solution('id,date,amount\n7,2026-03-01,1\n007,2026-03-02,2\n0,2026-03-03,3')` returns `[(3, 'duplicate'), (4, 'id')]`
* `solution('id,date,amount\n5,2026-04-01\n\n6,2026-04-01,1.234\n8,20260401,1')` returns `[(2, 'fields'), (4, 'amount'), (5, 'date')]`

**Limits:** `S` up to 1,000,000 characters.

??? success "Solution and explanation (open after you try)"

    ```python
    import re
    from datetime import date

    def solution(S):
        out, ids = [], set()
        for n, line in enumerate(S.split('\n')[1:], 2):
            if line.strip() == '':
                continue
            f = line.split(',')
            if len(f) != 3:
                out.append((n, 'fields'))
                continue
            i, d, a = f
            if not re.fullmatch(r'[0-9]+', i) or int(i) == 0:
                out.append((n, 'id'))
                continue
            if int(i) in ids:
                out.append((n, 'duplicate'))
                continue
            ids.add(int(i))
            try:
                ok = bool(re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', d)) and date.fromisoformat(d)
            except ValueError:
                ok = False
            if not ok:
                out.append((n, 'date'))
            elif not re.fullmatch(r'[0-9]+(\.[0-9]{1,2})?', a):
                out.append((n, 'amount'))
        return out
    ```

    Two traps. `str.isdigit()` says yes to `'²'`, so the id check uses `[0-9]`. And since Python 3.11
    `date.fromisoformat` also takes `'20260401'`, so the regex fixes the format and `fromisoformat` checks that the day
    exists (it rejects 30 February).

    **Cost:** O(len(S)) time; O(number of ids) memory.

    **Tests**

    ```python
    # tests
    assert solution('id,date,amount\n1,2026-01-31,9.99\n2,2026-02-30,5\n') == [(3, 'date')]
    assert solution('id,date,amount\n7,2026-03-01,1\n007,2026-03-02,2\n0,2026-03-03,3') == [(3, 'duplicate'), (4, 'id')]
    assert solution('id,date,amount\n5,2026-04-01\n\n6,2026-04-01,1.234\n8,20260401,1') == [(2, 'fields'), (4, 'amount'), (5, 'date')]
    assert solution('id,date,amount') == []
    assert solution('id,date,amount\n²,2026-01-01,1') == [(2, 'id')]
    assert solution('id,date,amount\n3,2024-02-29,.5\n4,2023-02-29,1') == [(2, 'amount'), (3, 'date')]
    assert solution('id,date,amount\n9,2026-13-01,1\n9,2026-01-01,1') == [(2, 'date'), (3, 'duplicate')]
    print('task 4: ok')
    ```


### 41. Rate limiter

**Level:** Medium · **Aim for:** 15 minutes

An API lets each client make at most `K` requests in any `W` seconds. `T` is the list of one client's request
times in seconds, sorted. A request at time `t` is **accepted** if fewer than `K` accepted requests have a time in
`(t - W, t]`; otherwise it is rejected, and a rejected request does not count against later ones. Return the
number of rejected requests.

```text
def solution(T, K, W): -> int
```

**Examples**

* `solution([1, 2, 3, 4], 2, 3)` returns `1` (the request at 3 is rejected; at 4 the request at 1 has left the window)
* `solution([0, 0, 0, 10], 1, 10)` returns `2`
* `solution([], 5, 60)` returns `0`

**Limits:** `len(T)` up to 1,000,000; `1 <= K <= 1,000,000`; `1 <= W <= 10^9`.

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import deque

    def solution(T, K, W):
        q = deque()
        rej = 0
        for t in T:
            while q and q[0] <= t - W:
                q.popleft()
            if len(q) < K:
                q.append(t)
            else:
                rej += 1
        return rej
    ```

    The deque holds only accepted requests still in the window. Each time goes in and out at most once. The usual wrong
    answer puts every request in the deque, so rejected ones keep blocking; in example 2 it gives the same answer, but
    `solution([0, 5, 10], 1, 10)` must be `1` and it gives `2`.

    **Cost:** O(N) time, O(K) memory. Counting back through all earlier requests for each one is O(N²).

    **Tests**

    ```python
    # tests
    import random
    assert solution([1, 2, 3, 4], 2, 3) == 1
    assert solution([0, 0, 0, 10], 1, 10) == 2
    assert solution([], 5, 60) == 0
    assert solution([0, 5, 10], 1, 10) == 1
    assert solution([7, 7, 7], 3, 1) == 0

    def slow(T, K, W):
        acc, rej = [], 0
        for t in T:
            if sum(1 for a in acc if t - W < a <= t) < K:
                acc.append(t)
            else:
                rej += 1
        return rej

    for _ in range(500):
        T = sorted(random.randint(0, 20) for _ in range(random.randint(0, 15)))
        K, W = random.randint(1, 4), random.randint(1, 8)
        assert solution(T, K, W) == slow(T, K, W)
    print('task 5: ok')
    ```


### 42. Busiest hour for each service

**Level:** Medium · **Aim for:** 15 minutes

`L` is a list of log lines like `'2026-11-11T10:15:02 auth ERROR token expired'`: a timestamp, a space, the
service name, a space, then anything. Lines that are empty or only spaces are skipped. For each service find the
hour (the first 13 characters of the timestamp, like `'2026-11-11T10'`) with the most lines; if hours tie, take
the earliest. Return a list of `(service, hour, count)` sorted by service.

```text
def solution(L): -> list of (str, str, int)
```

**Examples**

* `solution(['2026-11-11T10:00:01 auth INFO ok', '2026-11-11T11:05:00 auth ERROR x', '2026-11-11T11:59:59 auth INFO y'])`
  returns `[('auth', '2026-11-11T11', 2)]`
* `solution(['2026-01-01T09:00:00 db INFO a', '2026-01-01T08:00:00 db INFO b', ''])` returns `[('db', '2026-01-01T08', 1)]`
* `solution(['2026-05-05T05:00:00 web GET /', '2026-05-05T05:30:00 api GET /', '2026-05-05T05:31:00 web GET /a'])`
  returns `[('api', '2026-05-05T05', 1), ('web', '2026-05-05T05', 2)]`

**Limits:** `len(L)` up to 500,000.

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import Counter

    def solution(L):
        c = Counter()
        for line in L:
            if line.strip():
                ts, svc = line.split()[:2]
                c[svc, ts[:13]] += 1
        best = {}
        for (svc, h), n in c.items():
            if svc not in best or (-n, h) < (-best[svc][1], best[svc][0]):
                best[svc] = (h, n)
        return [(s, h, n) for s, (h, n) in sorted(best.items())]
    ```

    Count by the pair (service, hour) in one pass, then keep the best hour per service. The hour strings sort the same
    way as the times, so the earliest hour is the smallest string. `Counter.most_common(1)` breaks ties by first seen,
    not by earliest hour, so it is wrong when the lines are out of order (example 2).

    **Cost:** O(N) to count plus O(S log S) to sort S services.

    **Tests**

    ```python
    # tests
    assert solution(['2026-11-11T10:00:01 auth INFO ok', '2026-11-11T11:05:00 auth ERROR x', '2026-11-11T11:59:59 auth INFO y']) == [('auth', '2026-11-11T11', 2)]
    assert solution(['2026-01-01T09:00:00 db INFO a', '2026-01-01T08:00:00 db INFO b', '']) == [('db', '2026-01-01T08', 1)]
    assert solution(['2026-05-05T05:00:00 web GET /', '2026-05-05T05:30:00 api GET /', '2026-05-05T05:31:00 web GET /a']) == [('api', '2026-05-05T05', 1), ('web', '2026-05-05T05', 2)]
    assert solution([]) == []
    assert solution(['   ', '2026-01-01T00:00:00 x']) == [('x', '2026-01-01T00', 1)]
    print('task 6: ok')
    ```


### 43. Split a CSV line that has quotes

**Level:** Medium · **Aim for:** 20 minutes

Split one CSV line `S` into its fields **without** the `csv` module. Fields are split by commas. A field may be
wrapped in double quotes; inside quotes a comma is part of the field and two double quotes `""` stand for one `"`.
The quotes around a field are not part of it. You can assume the line is well formed: a quote opens only at the
start of a field and the closing quote is followed by a comma or the end of the line. An empty `S` is one empty
field.

```text
def solution(S): -> list of str
```

**Examples**

* `solution('a,b,c')` returns `['a', 'b', 'c']`
* `solution('1,"Smith, Ann",42')` returns `['1', 'Smith, Ann', '42']`
* `solution('"say ""hi""",,""')` returns `['say "hi"', '', '']`

**Limits:** `len(S)` up to 1,000,000.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(S):
        out, cur, q, i = [], [], False, 0
        while i < len(S):
            ch = S[i]
            if q:
                if ch != '"':
                    cur.append(ch)
                elif i + 1 < len(S) and S[i + 1] == '"':
                    cur.append('"')
                    i += 1
                else:
                    q = False
            elif ch == '"':
                q = True
            elif ch == ',':
                out.append(''.join(cur))
                cur = []
            else:
                cur.append(ch)
            i += 1
        out.append(''.join(cur))
        return out
    ```

    One flag says whether we are inside quotes. Characters go into a list and are joined once per field; adding to a
    string one character at a time can be O(N²). `S.split(',')` is the common wrong answer: it breaks `"Smith, Ann"`.

    **Cost:** O(N) time and memory.

    **Tests**

    ```python
    # tests
    import csv, random
    assert solution('a,b,c') == ['a', 'b', 'c']
    assert solution('1,"Smith, Ann",42') == ['1', 'Smith, Ann', '42']
    assert solution('"say ""hi""",,""') == ['say "hi"', '', '']
    assert solution('') == ['']
    assert solution(',') == ['', '']
    assert solution('""""') == ['"']
    for _ in range(500):
        fields = [''.join(random.choice('ab ,"') for _ in range(random.randint(0, 4))) for _ in range(random.randint(1, 5))]
        line = ','.join('"' + f.replace('"', '""') + '"' if (',' in f or '"' in f or random.random() < 0.3) else f for f in fields)
        assert solution(line) == fields
        if line:
            assert solution(line) == next(csv.reader([line]))
    print('task 7: ok')
    ```


### 44. Fill gaps, but not too far

**Level:** Easy · **Aim for:** 10 minutes

A sensor reports once a minute; `A` is the list of readings, with `None` where a reading is missing. Fill each
`None` with the last real reading before it, but only for the first `K` missing readings in a row: after `K`
filled minutes in a row the value is too old, so the rest of that gap stays `None`. `None` values before the first
real reading stay `None`. Return the new list (`A` itself is not changed).

```text
def solution(A, K): -> list
```

**Examples**

* `solution([5, None, None, 7], 2)` returns `[5, 5, 5, 7]`
* `solution([1, None, None, None, 2, None], 2)` returns `[1, 1, 1, None, 2, 2]`
* `solution([None, 0, None], 1)` returns `[None, 0, 0]`

**Limits:** `len(A)` up to 1,000,000; `0 <= K <= len(A)`.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A, K):
        out, last, run = [], None, 0
        for x in A:
            if x is None:
                run += 1
                out.append(last if run <= K else None)
            else:
                last, run = x, 0
                out.append(x)
        return out
    ```

    `run` counts the missing readings since the last real one. Test with `x is None`, never `if not x`: a reading of
    `0` is real (example 3). This is what `pandas` `ffill(limit=K)` does, written by hand.

    **Cost:** O(N) time and memory.

    **Tests**

    ```python
    # tests
    assert solution([5, None, None, 7], 2) == [5, 5, 5, 7]
    assert solution([1, None, None, None, 2, None], 2) == [1, 1, 1, None, 2, 2]
    assert solution([None, 0, None], 1) == [None, 0, 0]
    assert solution([], 3) == []
    assert solution([4, None], 0) == [4, None]
    a = [1, None]
    assert solution(a, 1) == [1, 1] and a == [1, None]
    print('task 8: ok')
    ```

## I. More data-engineering tasks, second set

Eight more: top K per group, a left join of records, duplicate files, a running median, a schema check,
packing messages into batches, dotted keys into a nested dict and events per UTC day. Standard library
only. Every solution passes its tests (shown inside) on Python 3.9 and 3.13.

### 45. Top K scores in each group

**Level:** Easy · **Aim for:** 12 minutes

`A` is a list of `(group, name, score)` tuples, for example game scores by country. For each group keep the `K`
best rows: the highest score first, ties by name A to Z. Return a `dict` that maps each group to its list of
`(name, score)` tuples. A group with fewer than `K` rows keeps all of them.

```text
def solution(A, K): -> dict of str -> list of (str, int)
```

**Examples**

* `solution([('ca', 'ann', 5), ('ca', 'bob', 9), ('ca', 'cy', 7), ('us', 'dan', 1)], 2)` returns `{'ca': [('bob', 9), ('cy', 7)], 'us': [('dan', 1)]}`
* `solution([('x', 'b', 3), ('x', 'a', 3), ('x', 'c', 3)], 2)` returns `{'x': [('a', 3), ('b', 3)]}`
* `solution([], 3)` returns `{}`

**Limits:** `len(A)` up to 1,000,000; `K` from 1 to 100.

??? success "Solution and explanation (open after you try)"

    ```python
    import heapq

    def solution(A, K):
        g = {}
        for grp, name, sc in A:
            g.setdefault(grp, []).append((name, sc))
        return {k: heapq.nsmallest(K, v, key=lambda x: (-x[1], x[0])) for k, v in g.items()}
    ```

    `nsmallest` with the key `(-score, name)` gives "highest score, then name A to Z" in one go. `nlargest` with key
    `(score, name)` looks the same but breaks ties Z to A. Sorting each whole group also works, but costs O(N log N)
    where `nsmallest` keeps only a heap of K.

    **Cost:** O(N log K) time, O(N) memory for the groups.

    **Tests**

    ```python
    # tests
    import random
    assert solution([('ca', 'ann', 5), ('ca', 'bob', 9), ('ca', 'cy', 7), ('us', 'dan', 1)], 2) == {'ca': [('bob', 9), ('cy', 7)], 'us': [('dan', 1)]}
    assert solution([('x', 'b', 3), ('x', 'a', 3), ('x', 'c', 3)], 2) == {'x': [('a', 3), ('b', 3)]}
    assert solution([], 3) == {}
    assert solution([('g', 'a', -1)], 1) == {'g': [('a', -1)]}
    for _ in range(300):
        A = [(random.choice('pq'), random.choice('abcd'), random.randint(0, 4)) for _ in range(random.randint(0, 12))]
        K = random.randint(1, 4)
        want = {}
        for grp in set(r[0] for r in A):
            want[grp] = sorted([(n, s) for g2, n, s in A if g2 == grp], key=lambda x: (-x[1], x[0]))[:K]
        assert solution(A, K) == want
    print('task 1: ok')
    ```


### 46. Left join two lists of records

**Level:** Easy · **Aim for:** 15 minutes

`L` and `R` are lists of dicts (rows), and `key` is a column name that every row of both lists has. Return the left
join, the way SQL does it: for each row of `L`, in order, one output row for every row of `R` with the same key
value (in `R`'s order), made of the `L` row plus the `R` row's other columns. A row of `L` with no match gives one
output row whose `R` columns are all `None`. The `R` columns are every column seen in `R` other than `key`. No
column other than `key` is in both lists.

```text
def solution(L, R, key): -> list of dict
```

**Examples**

* `solution([{'id': 1, 'n': 'a'}, {'id': 2, 'n': 'b'}], [{'id': 1, 'city': 'X'}], 'id')` returns `[{'id': 1, 'n': 'a', 'city': 'X'}, {'id': 2, 'n': 'b', 'city': None}]`
* `solution([{'id': 1}], [{'id': 1, 'v': 5}, {'id': 1, 'v': 6}], 'id')` returns `[{'id': 1, 'v': 5}, {'id': 1, 'v': 6}]`
* `solution([{'id': 3}], [], 'id')` returns `[{'id': 3}]`

**Limits:** each list up to 200,000 rows.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(L, R, key):
        idx = {}
        cols = {}
        for r in R:
            idx.setdefault(r[key], []).append(r)
            for c in r:
                if c != key:
                    cols[c] = None
        out = []
        for l in L:
            for r in idx.get(l[key], [{}]):
                row = dict(l)
                row.update({c: r.get(c) for c in cols})
                out.append(row)
        return out
    ```

    Build an index of `R` by key once; then each `L` row is a dict lookup. The `[{}]` default is the "no match" row.
    A row of `R` that lacks one of the `R` columns gets `None` for it too (`r.get(c)`), like SQL does. The slow way,
    a loop over `R` inside a loop over `L`, is O(N·M) and times out at 200,000 each.

    **Cost:** O(N + M + output size) time and memory.

    **Tests**

    ```python
    # tests
    import random
    assert solution([{'id': 1, 'n': 'a'}, {'id': 2, 'n': 'b'}], [{'id': 1, 'city': 'X'}], 'id') == [{'id': 1, 'n': 'a', 'city': 'X'}, {'id': 2, 'n': 'b', 'city': None}]
    assert solution([{'id': 1}], [{'id': 1, 'v': 5}, {'id': 1, 'v': 6}], 'id') == [{'id': 1, 'v': 5}, {'id': 1, 'v': 6}]
    assert solution([{'id': 3}], [], 'id') == [{'id': 3}]
    assert solution([], [{'id': 1, 'v': 2}], 'id') == []
    assert solution([{'k': 1}], [{'k': 1, 'a': 1}, {'k': 2, 'b': 2}], 'k') == [{'k': 1, 'a': 1, 'b': None}]
    L0 = [{'id': 1, 'n': 'a'}]
    solution(L0, [{'id': 1, 'v': 9}], 'id')
    assert L0 == [{'id': 1, 'n': 'a'}]
    for _ in range(300):
        L = [{'id': random.randint(0, 4), 'n': i} for i in range(random.randint(0, 6))]
        R = [{'id': random.randint(0, 4), 'v': i} for i in range(random.randint(0, 6))]
        want = []
        for l in L:
            m = [r for r in R if r['id'] == l['id']]
            if m:
                want += [{'id': l['id'], 'n': l['n'], 'v': r['v']} for r in m]
            else:
                want.append(dict(l, v=None) if R else dict(l))
        assert solution(L, R, 'id') == want
    print('task 2: ok')
    ```


### 47. Find duplicate files by content

**Level:** Easy · **Aim for:** 12 minutes

A backup tool lists files as `(path, content)` tuples, the content as a string. Find the files whose content is
exactly the same. Return a list of groups: each group is the sorted list of paths that share one content, only
groups of 2 or more, and the groups sorted by their first path. Do not keep the contents in memory as keys; use a
SHA-256 hash of each content (from `hashlib`) instead, as a real tool would for big files.

```text
def solution(F): -> list of list of str
```

**Examples**

* `solution([('a.txt', 'hi'), ('b.txt', 'yo'), ('c.txt', 'hi')])` returns `[['a.txt', 'c.txt']]`
* `solution([('z', ''), ('y', ''), ('x', 'q'), ('w', 'q')])` returns `[['w', 'x'], ['y', 'z']]`
* `solution([('only', 'one')])` returns `[]`

**Limits:** up to 100,000 files; contents up to 10,000 characters each.

??? success "Solution and explanation (open after you try)"

    ```python
    import hashlib

    def solution(F):
        g = {}
        for path, text in F:
            h = hashlib.sha256(text.encode()).hexdigest()
            g.setdefault(h, []).append(path)
        return sorted(sorted(v) for v in g.values() if len(v) > 1)
    ```

    `hashlib` works on bytes, so `.encode()` first; forgetting it is a `TypeError`. Two different contents with the
    same SHA-256 have never been found, so the hash is safe as a key here. A real tool often groups by file size first
    and hashes only sizes that repeat, which saves reading most files.

    **Cost:** O(total characters) for the hashes, plus O(N log N) to sort the paths.

    **Tests**

    ```python
    # tests
    import random
    assert solution([('a.txt', 'hi'), ('b.txt', 'yo'), ('c.txt', 'hi')]) == [['a.txt', 'c.txt']]
    assert solution([('z', ''), ('y', ''), ('x', 'q'), ('w', 'q')]) == [['w', 'x'], ['y', 'z']]
    assert solution([('only', 'one')]) == []
    assert solution([]) == []
    assert solution([('a', 'é'), ('b', 'é'), ('c', 'e')]) == [['a', 'b']]
    for _ in range(300):
        F = [('p%d' % i, random.choice(['', 'a', 'b', 'ab'])) for i in range(random.randint(0, 8))]
        by = {}
        for p, t in F:
            by.setdefault(t, []).append(p)
        assert solution(F) == sorted(sorted(v) for v in by.values() if len(v) > 1)
    print('task 3: ok')
    ```


### 48. Median after every reading

**Level:** Medium · **Aim for:** 20 minutes

A sensor sends integer readings one by one; `A` is the list of them in order. After each reading, report the
median of all readings so far: the middle one when the count is odd, the mean of the two middle ones when it is even
(that can be a float like `2.5`). Return the list of medians.

```text
def solution(A): -> list of numbers
```

**Examples**

* `solution([5, 15, 1, 3])` returns `[5, 10.0, 5, 4.0]`
* `solution([2, 2, 2])` returns `[2, 2.0, 2]`
* `solution([-1, 4])` returns `[-1, 1.5]`

**Limits:** `len(A)` up to 200,000.

??? success "Solution and explanation (open after you try)"

    ```python
    import heapq

    def solution(A):
        lo, hi, out = [], [], []          # lo: max-heap (negated) of the smaller half, hi: min-heap
        for x in A:
            heapq.heappush(lo, -x)
            heapq.heappush(hi, -heapq.heappop(lo))
            if len(hi) > len(lo):
                heapq.heappush(lo, -heapq.heappop(hi))
            out.append(-lo[0] if len(lo) > len(hi) else (-lo[0] + hi[0]) / 2)
        return out
    ```

    Two heaps: `lo` holds the smaller half (negated, since `heapq` is a min-heap), `hi` the bigger half, and `lo` has
    the same size or one more. Each new value goes through `lo` into `hi`, so every value in `lo` stays at most every
    value in `hi`. Sorting after each reading is O(N² log N); `bisect.insort` is O(N²) because of the list shifts.

    **Cost:** O(N log N) time, O(N) memory.

    **Tests**

    ```python
    # tests
    import random, statistics
    assert solution([5, 15, 1, 3]) == [5, 10.0, 5, 4.0]
    assert solution([2, 2, 2]) == [2, 2.0, 2]
    assert solution([-1, 4]) == [-1, 1.5]
    assert solution([]) == []
    for _ in range(300):
        A = [random.randint(-5, 5) for _ in range(random.randint(0, 15))]
        assert solution(A) == [statistics.median(A[:i + 1]) for i in range(len(A))]
    print('task 4: ok')
    ```


### 49. Check a record against a schema

**Level:** Medium · **Aim for:** 20 minutes

An API sends JSON records, already loaded as Python dicts. `S` is the schema: a dict that maps each field name to a
type (`int`, `float`, `str` or `bool`), to a list of one schema item such as `[str]` (a list whose items all match
it), or to a nested schema dict. `D` is a record, always a dict. Report every problem as a `(path, problem)` tuple:

* `'missing'`: a field of the schema is not in the record;
* `'extra'`: the record has a field the schema does not have;
* `'type'`: the value has the wrong type. `bool` is not an `int` here, and a `float` field also takes an `int`.

A path joins field names with dots, and a list item adds `[i]`: `tags[2]`, `address.city`. Stop going down a value
whose type is wrong. Return the problems sorted.

```text
def solution(S, D): -> list of (str, str)
```

**Examples**

* `solution({'id': int, 'tags': [str]}, {'id': 7, 'tags': ['a', 3]})` returns `[('tags[1]', 'type')]`
* `solution({'id': int, 'addr': {'city': str}}, {'id': True, 'addr': {}, 'x': 1})` returns `[('addr.city', 'missing'), ('id', 'type'), ('x', 'extra')]`
* `solution({'price': float, 'tags': [str]}, {'price': 3, 'tags': 'a'})` returns `[('tags', 'type')]`

**Limits:** schema and record nested at most 50 levels; at most 100,000 values in a record.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(S, D):
        out = []
        def go(s, v, p):
            if isinstance(s, dict):
                if type(v) is not dict:
                    return out.append((p, 'type'))
                for k in s:
                    q = p + '.' + k if p else k
                    if k in v:
                        go(s[k], v[k], q)
                    else:
                        out.append((q, 'missing'))
                out.extend((p + '.' + k if p else k, 'extra') for k in v if k not in s)
            elif isinstance(s, list):
                if type(v) is not list:
                    return out.append((p, 'type'))
                for i, x in enumerate(v):
                    go(s[0], x, '%s[%d]' % (p, i))
            elif not (type(v) is s or (s is float and type(v) is int)):
                out.append((p, 'type'))
        go(S, D, '')
        return sorted(out)
    ```

    The trap is `isinstance(True, int)`, which is `True`: a flag sent where a number is wanted would pass. So compare
    `type(v) is s`. The recursion follows the schema, which is at most 50 deep, so Python's limit of 1,000 is safe.

    **Cost:** O(number of values in `D` + size of `S`), plus the final sort of the problems.

    **Tests**

    ```python
    # tests
    assert solution({'id': int, 'tags': [str]}, {'id': 7, 'tags': ['a', 3]}) == [('tags[1]', 'type')]
    assert solution({'id': int, 'addr': {'city': str}}, {'id': True, 'addr': {}, 'x': 1}) == [('addr.city', 'missing'), ('id', 'type'), ('x', 'extra')]
    assert solution({'price': float, 'tags': [str]}, {'price': 3, 'tags': 'a'}) == [('tags', 'type')]
    assert solution({}, {}) == []
    assert solution({'ok': bool}, {'ok': 1}) == [('ok', 'type')]
    assert solution({'n': int}, {'n': 2.0}) == [('n', 'type')]
    assert solution({'a': {'b': int}}, {'a': 5}) == [('a', 'type')]
    S = {'rows': [{'id': int, 'v': [float]}]}
    assert solution(S, {'rows': [{'id': 1, 'v': [1, 2.5]}, {'id': 'x', 'v': [None], 'z': 0}]}) == [('rows[1].id', 'type'), ('rows[1].v[0]', 'type'), ('rows[1].z', 'extra')]
    assert solution({'m': [[int]]}, {'m': [[1], [2, 'x']]}) == [('m[1][1]', 'type')]
    print('task 5: ok')
    ```


### 50. Pack messages into batches

**Level:** Easy · **Aim for:** 15 minutes

A loader sends messages to an API that takes at most `N` messages per call and at most `B` characters in total per
call. `A` is the list of messages (strings), in order. Fill batches greedily, keeping the order: add each message to
the current batch, and start a new batch when adding it would break either limit. A message longer than `B` can
never fit, so it goes alone in its own batch (the API will reject it, and the caller logs that). Return the list of
batches.

```text
def solution(A, N, B): -> list of list of str
```

**Examples**

* `solution(['aa', 'bb', 'cc', 'dd', 'ee'], 2, 100)` returns `[['aa', 'bb'], ['cc', 'dd'], ['ee']]`
* `solution(['abc', 'de', 'fghi', 'j'], 10, 5)` returns `[['abc', 'de'], ['fghi', 'j']]`
* `solution(['a', 'toolong', 'b'], 5, 3)` returns `[['a'], ['toolong'], ['b']]`

**Limits:** `len(A)` up to 1,000,000; `N` and `B` at least 1.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A, N, B):
        out, cur, size = [], [], 0
        for m in A:
            if cur and (len(cur) == N or size + len(m) > B):
                out.append(cur)
                cur, size = [], 0
            cur.append(m)
            size += len(m)
        if cur:
            out.append(cur)
        return out
    ```

    The `cur and` part is what puts a too-long message in its own batch instead of a loop that never ends or an empty
    batch. Only a count limit? Then `[A[i:i + N] for i in range(0, len(A), N)]` is the one-liner, and in Python 3.12
    `itertools.batched(A, N)` does it (not on 3.9, not run here).

    **Cost:** O(N) time; each message is looked at once.

    **Tests**

    ```python
    # tests
    import random
    assert solution(['aa', 'bb', 'cc', 'dd', 'ee'], 2, 100) == [['aa', 'bb'], ['cc', 'dd'], ['ee']]
    assert solution(['abc', 'de', 'fghi', 'j'], 10, 5) == [['abc', 'de'], ['fghi', 'j']]
    assert solution(['a', 'toolong', 'b'], 5, 3) == [['a'], ['toolong'], ['b']]
    assert solution([], 3, 3) == []
    assert solution(['', '', ''], 2, 0) == [['', ''], ['']]
    for _ in range(500):
        A = ['x' * random.randint(0, 6) for _ in range(random.randint(0, 12))]
        N, B = random.randint(1, 4), random.randint(1, 8)
        got = solution(A, N, B)
        assert [m for b in got for m in b] == A
        for i, b in enumerate(got):
            assert 1 <= len(b) <= N and (sum(map(len, b)) <= B or len(b) == 1)
            if i + 1 < len(got):
                nxt = got[i + 1][0]
                assert len(b) == N or sum(map(len, b)) + len(nxt) > B
    print('task 6: ok')
    ```


### 51. Dotted keys back into a nested dict

**Level:** Medium · **Aim for:** 15 minutes

A config file was stored flat: `D` maps dotted paths such as `'db.host'` to integer values. Build the nested dict
back: `{'a': 1, 'b.c': 2}` becomes `{'a': 1, 'b': {'c': 2}}`. Path parts are non-empty and have no dots. If two keys
clash, so that one path needs to be both a value and a dict (`'a'` and `'a.b'`), return `None`, whatever their
order in `D`.

```text
def solution(D): -> dict or None
```

**Examples**

* `solution({'db.host': 1, 'db.port': 2, 'debug': 0})` returns `{'db': {'host': 1, 'port': 2}, 'debug': 0}`
* `solution({'a.b.c': 5})` returns `{'a': {'b': {'c': 5}}}`
* `solution({'a.b': 1, 'a': 2})` returns `None`

**Limits:** `D` has up to 100,000 keys; each key has up to 50 parts.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(D):
        out = {}
        for k, v in D.items():
            *path, last = k.split('.')
            cur = out
            for p in path:
                cur = cur.setdefault(p, {})
                if type(cur) is not dict:
                    return None
            if last in cur:
                return None
            cur[last] = v
            # values are ints, never dicts, so a later 'x.y' under an int 'x' fails above
        return out
    ```

    There are two ways to clash and each order hits one of the two checks: `'a'` first, then `'a.b'` finds an int on
    its way down; `'a.b'` first, then `'a'` finds the key taken. The reverse of task 20 on the page (flatten a nested
    record): flattening the answer gives `D` back, which the tests check.

    **Cost:** O(total parts in all keys) time and memory.

    **Tests**

    ```python
    # tests
    import random
    assert solution({'db.host': 1, 'db.port': 2, 'debug': 0}) == {'db': {'host': 1, 'port': 2}, 'debug': 0}
    assert solution({'a.b.c': 5}) == {'a': {'b': {'c': 5}}}
    assert solution({'a.b': 1, 'a': 2}) is None
    assert solution({'a': 2, 'a.b': 1}) is None
    assert solution({'x.y': 1, 'x.y.z': 2}) is None
    assert solution({}) == {}
    def flat(d, p=''):
        r = {}
        for k, v in d.items():
            q = p + '.' + k if p else k
            r.update(flat(v, q) if isinstance(v, dict) else {q: v})
        return r
    for _ in range(300):
        D = {'.'.join(random.choice('ab') for _ in range(random.randint(1, 3))): random.randint(0, 9) for _ in range(random.randint(0, 5))}
        keys = list(D)
        clash = any(a != b and b.startswith(a + '.') for a in keys for b in keys)
        got = solution(D)
        assert (got is None) == clash
        if got is not None:
            assert flat(got) == D
    print('task 7: ok')
    ```


### 52. Events per UTC day from mixed time zones

**Level:** Medium · **Aim for:** 15 minutes

Servers in different countries log events with local timestamps in ISO 8601 form, `YYYY-MM-DDTHH:MM:SS` followed by
an offset: `+HH:MM`, `-HH:MM` or `Z` (which means UTC). A timestamp with no offset is already UTC. Count the events
per **UTC** date and return a list of `(date, count)` tuples, dates as `'YYYY-MM-DD'`, oldest first. Days with no
events are left out.

```text
def solution(A): -> list of (str, int)
```

**Examples**

* `solution(['2026-03-01T23:30:00-05:00', '2026-03-02T01:00:00Z'])` returns `[('2026-03-02', 2)]`
* `solution(['2026-03-01T00:30:00+02:00', '2026-03-01T12:00:00'])` returns `[('2026-02-28', 1), ('2026-03-01', 1)]`
* `solution(['2024-12-31T23:59:59-00:01'])` returns `[('2025-01-01', 1)]`

**Limits:** `len(A)` up to 500,000; all timestamps are valid.

??? success "Solution and explanation (open after you try)"

    ```python
    from datetime import datetime, timezone

    def solution(A):
        cnt = {}
        for s in A:
            t = datetime.fromisoformat(s.replace('Z', '+00:00'))
            if t.tzinfo:
                t = t.astimezone(timezone.utc)
            d = t.date().isoformat()
            cnt[d] = cnt.get(d, 0) + 1
        return sorted(cnt.items())
    ```

    Two traps. `fromisoformat` takes `'Z'` only from Python 3.11 on (from the Python docs, not run here), so it is
    replaced first and the code runs the same on 3.9. And `t.date()` on the local time gives the local day, which is
    what example 1 gets wrong: 23:30 in New York is already the next day in UTC. `astimezone` on a timestamp with no
    offset would treat it as the Mac's local time, hence the `if`.

    **Cost:** O(N) to parse and count, plus O(D log D) to sort D days.

    **Tests**

    ```python
    # tests
    assert solution(['2026-03-01T23:30:00-05:00', '2026-03-02T01:00:00Z']) == [('2026-03-02', 2)]
    assert solution(['2026-03-01T00:30:00+02:00', '2026-03-01T12:00:00']) == [('2026-02-28', 1), ('2026-03-01', 1)]
    assert solution(['2024-12-31T23:59:59-00:01']) == [('2025-01-01', 1)]
    assert solution([]) == []
    assert solution(['2024-02-29T22:00:00-03:00', '2024-03-01T00:00:00Z', '2024-02-29T23:59:59+00:00']) == [('2024-02-29', 1), ('2024-03-01', 2)]
    assert solution(['2026-06-01T05:00:00+05:30']) == [('2026-05-31', 1)]
    print('task 8: ok')
    ```
