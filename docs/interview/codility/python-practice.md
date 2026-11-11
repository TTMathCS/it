# Python practice set

Twenty-four tasks in the style of a Codility programming task: a function `solution(...)`, examples, and limits
that tell you how fast the answer must be. They are grouped by the technique they practise. Several are
data-engineering flavoured (log lines, CSV rows, durations, dates, pipeline task order).

**How to practise:** for each task, first read the limits and decide the target cost (the table in the
[cheat sheet](cheat-sheet.md) helps), write the code, run the examples, then add your own edge cases **before**
opening the solution.

Every answer was run on Python 3.13 with the examples, the listed edge cases, 500 or more random small inputs
compared with a slow but obviously correct answer, and the largest input the limits allow, timed. Every "common
wrong answer" was run too; its box says which case it fails or how long it took before it was stopped.

!!! tip "Codility's own Python practice"
    The [Codility lessons](codility-tasks.md#python-the-lessons) have graded tasks for each technique below.
    Doing two or three of them on the real grader is the best rehearsal for the editor.

## A. Counting with sets and dictionaries

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `-1`;
    * edge case, negative and zero: `solution([0, -3, -3, 0])` returns `-3`;
    * edge case, all equal: `solution([9, 9, 9])` returns `9`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.006s.
    
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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, all different: `solution([30, 10, 20])` returns `10`;
    * edge case, larger code first in a tie: `solution([9, 9, 3, 3])` returns `3`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.013s.
    
    ??? failure "A common wrong answer: most_common breaks ties by first appearance"
    
        ```python
        from collections import Counter
        
        def solution(A):
            return Counter(A).most_common(1)[0][0]
        ```
        
        Checked: example: got 500 want 404.



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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([], 0)` returns `0`;
    * edge case, no pair: `solution([1, 2], 10)` returns `0`;
    * edge case, negatives: `solution([-1, 1, 0, 0], 0)` returns `2`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.009s.
    
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

**Level:** Easy to medium · **Aim for:** 10 minutes

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty text: `solution('', 3)` returns `[]`;
    * edge case, K larger than the number of words: `solution('x y', 5)` returns `['x', 'y']`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.024s.
    
    ??? failure "A common wrong answer: most_common ignores the alphabetical tie rule"
    
        ```python
        from collections import Counter
        
        def solution(S, K):
            return [w for w, _ in Counter(S.split()).most_common(K)]
        ```
        
        Checked: example: got ['b', 'a', 'c'] want ['a', 'b', 'c'].



## B. Strings and parsing

### 5. Longest run in a status string

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution('')` returns `0`;
    * edge case, one character: `solution('Q')` returns `1`;
    * edge case, longest run at the end: `solution('OXXOOOO')` returns `4`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.008s.
    
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



### 6. Run-length encoding

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution('')` returns `''`;
    * edge case, one long run: `solution('zzzzzzzzzzzz')` returns `'z12'`;
    * edge case, single letter: `solution('q')` returns `'q'`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.023s.
    
    ??? failure "A common wrong answer: writes 1 after single letters"
    
        ```python
        import itertools
        
        def solution(S):
            return "".join(ch + str(len(list(g))) for ch, g in itertools.groupby(S))
        ```
        
        Checked: example: got 'a3b1c2d4' want 'a3bc2d4'.



### 7. Count log levels

**Level:** Easy to medium · **Aim for:** 12 minutes

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty text: `solution('')` returns `''`;
    * edge case, only blank lines: `solution('\n\n')` returns `''`;
    * edge case, no message after the level: `solution('2026-01-01 00:00:00 WARN')` returns `'WARN:1'`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.006s.
    
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



### 8. Add up durations

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty list: `solution([])` returns `'00:00:00'`;
    * edge case, over 99 hours: `solution(['99:59:59', '00:00:01'])` returns `'100:00:00'`;
    * edge case, seconds carry into minutes and hours: `solution(['00:59:59', '00:00:01'])` returns `'01:00:00'`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.026s.
    
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



### 9. Rows with the wrong number of fields

**Level:** Easy to medium · **Aim for:** 12 minutes

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty file: `solution('', 2)` returns `[]`;
    * edge case, empty line in the middle: `solution('a,b\n\nc,d', 2)` returns `[2]`;
    * edge case, no trailing newline: `solution('a\nb,c', 1)` returns `[2]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.013s.
    
    ??? failure "A common wrong answer: counts the final newline as a bad row"
    
        ```python
        def solution(S, K):
            if S == "":
                return []
            return [i for i, line in enumerate(S.split("\n"), 1) if len(line.split(",")) != K]
        ```
        
        Checked: example: got [3, 4, 5] want [3, 4].



### 10. Compare version numbers

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



### 11. Days with no data

**Level:** Easy to medium · **Aim for:** 12 minutes

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `[]`;
    * edge case, one date: `solution(['2026-01-01'])` returns `[]`;
    * edge case, leap year: `solution(['2024-02-28', '2024-03-01'])` returns `['2024-02-29']`;
    * edge case, over new year: `solution(['2025-12-30', '2026-01-02'])` returns `['2025-12-31', '2026-01-01']`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.031s.
    
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



## C. Sorting and intervals

### 12. Sessions from timestamps

**Level:** Easy to medium · **Aim for:** 10 minutes

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no clicks: `solution([], 10)` returns `0`;
    * edge case, same second twice: `solution([7, 7], 0)` returns `1`;
    * edge case, gap of exactly G: `solution([0, 30], 30)` returns `1`;
    * edge case, gap of G + 1: `solution([0, 31], 30)` returns `2`;
    * edge case, out of order, one session: `solution([30, 0, 60], 30)` returns `1`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.027s.
    
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



### 13. Total busy time

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no jobs: `solution([], [])` returns `0`;
    * edge case, one inside another: `solution([0, 2], [10, 3])` returns `10`;
    * edge case, identical jobs: `solution([4, 4], [6, 6])` returns `2`;
    * edge case, jobs not in time order: `solution([10, 0], [12, 5])` returns `7`;
    * 800 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.046s.
    
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



## D. Prefix sums, sliding windows and two pointers

### 14. Best K consecutive days

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, K equals N: `solution([1, 2, 3], 3)` returns `6`;
    * edge case, all negative: `solution([-1, -1, -1], 2)` returns `-2`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.004s.
    
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



### 15. Many range totals

**Level:** Easy to medium · **Aim for:** 12 minutes

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, whole array: `solution([1, 2], [0], [1])` returns `[3]`;
    * edge case, single element: `solution([7], [0], [0])` returns `[7]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.007s.
    
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



### 16. Slices that sum to K

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([], 0)` returns `0`;
    * edge case, negatives: `solution([-1, -1, 1], -1)` returns `3`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.020s.
    
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



### 17. Shortest stretch reaching a target

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([], 3)` returns `0`;
    * edge case, one element is enough: `solution([1, 9, 1], 9)` returns `1`;
    * edge case, needs the whole array: `solution([2, 2, 2], 6)` returns `3`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.011s.
    
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



### 18. Longest stretch with at most K kinds

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([], 1)` returns `0`;
    * edge case, K larger than the number of values: `solution([1, 2, 3], 5)` returns `3`;
    * edge case, all different, K = 1: `solution([1, 2, 3], 1)` returns `1`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.018s.
    
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

### 19. Deepest bracket nesting

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution('')` returns `0`;
    * edge case, unclosed: `solution('((a)')` returns `-1`;
    * edge case, closing first: `solution(')(')` returns `-1`;
    * edge case, deep: `solution('(' * 1000 + ')' * 1000)` returns `1000`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.008s.
    
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



### 20. Days until a warmer reading

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty: `solution([])` returns `[]`;
    * edge case, falling: `solution([3, 2, 1])` returns `[0, 0, 0]`;
    * edge case, rising: `solution([1, 2, 3])` returns `[1, 1, 0]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.004s.
    
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

### 21. Groups of linked tables

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no tables: `solution(0, [], [])` returns `0`;
    * edge case, a table linked to itself: `solution(2, [1], [1])` returns `2`;
    * edge case, a cycle: `solution(3, [0, 1, 2], [1, 2, 0])` returns `1`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.011s.
    
    ??? failure "A common wrong answer: counting links instead of groups"
    
        ```python
        def solution(N, A, B):
            return N - len(A)
        ```
        
        Checked: edge: a table linked to itself: got 1 want 2.



### 22. Count the blocks on a map

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, empty map: `solution([])` returns `0`;
    * edge case, all water: `solution(['...', '...'])` returns `0`;
    * edge case, one big block: `solution(['###', '###'])` returns `1`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.541s.
    
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



### 23. Run order for pipeline tasks

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
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, no rules: `solution(3, [], [])` returns `[0, 1, 2]`;
    * edge case, no tasks: `solution(0, [], [])` returns `[]`;
    * edge case, same rule twice: `solution(2, [1, 1], [0, 0])` returns `[1, 0]`;
    * edge case, a released task is smaller than one already waiting: `solution(3, [0], [1])` returns `[0, 1, 2]`;
    * edge case, a cycle among some tasks only: `solution(3, [1, 2], [2, 1])` returns `[]`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.042s.
    
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



## G. Binary search on the answer

### 24. Smallest daily capacity

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
    * Cost: about 30 greedy passes (log₂ of the range) of O(N) each. Trying capacities one by one could take a billion
      passes. Codility's lesson 14 has tasks of this kind.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, one day: `solution([5, 5, 5], 1)` returns `15`;
    * edge case, one file per day: `solution([5, 9, 2], 3)` returns `9`;
    * edge case, single file: `solution([7], 1)` returns `7`;
    * edge case, files cannot be split: `solution([5, 5, 6], 2)` returns `10`;
    * 500 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.092s.
    
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


