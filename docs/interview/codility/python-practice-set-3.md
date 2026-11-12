# Python practice: set 3

Eight more tasks in the style of the [Python practice set](python-practice.md). Standard library only; every solution passes its tests (shown inside) on Python 3.9 and 3.13. Write your own edge cases before you open a solution.

### 1. Parse an Apache access log line

**Level:** Easy · **Aim for:** 15 minutes

`S` is one line of a web server access log in the common format:
`127.0.0.1 - ann [10/Oct/2026:13:55:36 -0700] "GET /a.png HTTP/1.1" 200 2326`. The parts are: client address, an
unused field, user (`-` if none), time in brackets, the request in quotes (method, path, protocol), status code
(3 digits) and bytes sent (`-` means 0). Return a dict with keys `ip`, `user` (`None` for `-`), `time` (ISO 8601
string with the offset kept), `method`, `path`, `status` (int) and `bytes` (int). Return `None` if the line does
not fit the format or the time is not a real date.

```text
def solution(S): -> dict or None
```

**Examples**

* `solution('127.0.0.1 - ann [10/Oct/2026:13:55:36 -0700] "GET /a.png HTTP/1.1" 200 2326')` returns `{'ip': '127.0.0.1', 'user': 'ann', 'time': '2026-10-10T13:55:36-07:00', 'method': 'GET', 'path': '/a.png', 'status': 200, 'bytes': 2326}`
* `solution('10.0.0.2 - - [01/Jan/2026:00:00:00 +0000] "POST /api HTTP/1.0" 304 -')` returns a dict with `user` `None` and `bytes` `0`
* `solution('10.0.0.2 - - [31/Feb/2026:00:00:00 +0000] "GET / HTTP/1.0" 200 5')` returns `None` (no 31 February)

**Limits:** `len(S)` up to 10,000.

??? success "Solution and explanation (open after you try)"

    ```python
    import re
    from datetime import datetime

    P = re.compile(r'(\S+) \S+ (\S+) \[([^\]]+)\] "(\S+) (\S+) [^"]*" (\d{3}) (\d+|-)$')

    def solution(S):
        m = P.match(S)
        if not m:
            return None
        ip, user, ts, meth, path, st, sz = m.groups()
        try:
            t = datetime.strptime(ts, '%d/%b/%Y:%H:%M:%S %z')
        except ValueError:
            return None
        return {'ip': ip, 'user': None if user == '-' else user, 'time': t.isoformat(),
                'method': meth, 'path': path, 'status': int(st), 'bytes': 0 if sz == '-' else int(sz)}
    ```

    Splitting on spaces breaks here: the time has a space before the offset and the request has two. A regex with one
    group per part is shorter and also rejects bad lines. `strptime` checks the date itself (31 February fails).
    `%b` reads month names in the current locale; on the Mac it is English, so `Oct` works (not tried in another
    locale).

    **Cost:** O(L) for a line of length L.

    **Tests**

    ```python
    # tests
    assert solution('127.0.0.1 - ann [10/Oct/2026:13:55:36 -0700] "GET /a.png HTTP/1.1" 200 2326') == {'ip': '127.0.0.1', 'user': 'ann', 'time': '2026-10-10T13:55:36-07:00', 'method': 'GET', 'path': '/a.png', 'status': 200, 'bytes': 2326}
    r = solution('10.0.0.2 - - [01/Jan/2026:00:00:00 +0000] "POST /api HTTP/1.0" 304 -')
    assert r['user'] is None and r['bytes'] == 0 and r['status'] == 304 and r['time'] == '2026-01-01T00:00:00+00:00'
    assert solution('10.0.0.2 - - [31/Feb/2026:00:00:00 +0000] "GET / HTTP/1.0" 200 5') is None
    assert solution('') is None
    assert solution('10.0.0.2 - - [01/Jan/2026:00:00:00 +0000] "-" 400 0') is None
    assert solution('10.0.0.2 - - [01/Jan/2026:00:00:00 +0000] "GET / HTTP/1.0" 20 5') is None
    assert solution('10.0.0.2 - - [01/Jan/2026:00:00:00 +0000] "GET / HTTP/1.0" 200 5 extra') is None
    assert solution('::1 - bo [29/Feb/2024:23:59:59 +0530] "DELETE /x?id=3 HTTP/2" 204 0')['time'] == '2024-02-29T23:59:59+05:30'
    print('task 1: ok')
    ```


### 2. Drop repeats inside a time window

**Level:** Easy · **Aim for:** 12 minutes

`E` is a stream of events as `(t, key)` tuples, sorted by time `t` in seconds (an int). The same alert or message
often arrives many times in a row. Keep an event only if no **kept** event with the same key happened less than
`W` seconds before it (so `t - last_kept >= W` keeps it). Return the kept events in order.

```text
def solution(E, W): -> list of (int, str)
```

**Examples**

* `solution([(0, 'a'), (3, 'a'), (5, 'b'), (10, 'a')], 10)` returns `[(0, 'a'), (5, 'b'), (10, 'a')]`
* `solution([(0, 'x'), (4, 'x'), (8, 'x'), (12, 'x')], 5)` returns `[(0, 'x'), (8, 'x')]`
* `solution([], 60)` returns `[]`

**Limits:** `len(E)` up to 1,000,000; `1 <= W <= 10^9`.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(E, W):
        last = {}
        out = []
        for t, k in E:
            if k not in last or t - last[k] >= W:
                last[k] = t
                out.append((t, k))
        return out
    ```

    The trap is example 2: compare with the last **kept** event, not the last one seen. Updating `last[k]` on every
    event would drop 8 and 12 too, because each repeat pushes the window forward and a steady stream never gets
    through. In a real stream that never ends, `last` grows with the keys; old keys can be removed once `t` is `W`
    past them.

    **Cost:** O(N) time, O(K) memory for K keys.

    **Tests**

    ```python
    # tests
    import random
    assert solution([(0, 'a'), (3, 'a'), (5, 'b'), (10, 'a')], 10) == [(0, 'a'), (5, 'b'), (10, 'a')]
    assert solution([(0, 'x'), (4, 'x'), (8, 'x'), (12, 'x')], 5) == [(0, 'x'), (8, 'x')]
    assert solution([], 60) == []
    assert solution([(7, 'a'), (7, 'a'), (7, 'b')], 1) == [(7, 'a'), (7, 'b')]
    for _ in range(300):
        t = 0
        E = []
        for _ in range(random.randint(0, 15)):
            t += random.randint(0, 3)
            E.append((t, random.choice('ab')))
        W = random.randint(1, 6)
        want = []
        for e in E:
            if all(not (k == e[1] and e[0] - s < W) for s, k in want):
                want.append(e)
        assert solution(E, W) == want
    print('task 2: ok')
    ```


### 3. Group anagrams

**Level:** Easy · **Aim for:** 10 minutes

`A` is a list of words, for example product tags typed by users. Two words are in the same group if one is the
other with its letters reordered, ignoring upper and lower case. Return the groups as a list of lists: each group
keeps its words in input order, and the groups are in the order of their first word. Repeated words stay.

```text
def solution(A): -> list of list of str
```

**Examples**

* `solution(['listen', 'Silent', 'abc', 'enlist', 'cab'])` returns `[['listen', 'Silent', 'enlist'], ['abc', 'cab']]`
* `solution(['a', 'b', 'a'])` returns `[['a', 'a'], ['b']]`
* `solution([])` returns `[]`

**Limits:** up to 100,000 words, each up to 100 letters.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A):
        g = {}
        for w in A:
            g.setdefault(''.join(sorted(w.lower())), []).append(w)
        return list(g.values())
    ```

    The sorted letters are the same for every word in a group, so they make a dict key. Since Python 3.7 a dict keeps
    insertion order, which gives "groups in order of their first word" for free. Comparing every pair of words is
    O(N²) and too slow at 100,000.

    **Cost:** O(N · L log L) time for N words of length L, O(N · L) memory.

    **Tests**

    ```python
    # tests
    import random
    assert solution(['listen', 'Silent', 'abc', 'enlist', 'cab']) == [['listen', 'Silent', 'enlist'], ['abc', 'cab']]
    assert solution(['a', 'b', 'a']) == [['a', 'a'], ['b']]
    assert solution([]) == []
    assert solution(['', '']) == [['', '']]
    for _ in range(300):
        A = [''.join(random.choice('abAB') for _ in range(random.randint(0, 3))) for _ in range(random.randint(0, 10))]
        want = []
        for w in A:
            for grp in want:
                if sorted(grp[0].lower()) == sorted(w.lower()):
                    grp.append(w)
                    break
            else:
                want.append([w])
        assert solution(A) == want
    print('task 3: ok')
    ```


### 4. Maximum of every window

**Level:** Medium · **Aim for:** 20 minutes

`A` is a list of readings (ints), one per minute. For every block of `K` consecutive readings, from the first
block to the last, find the largest reading. Return the list of these `len(A) - K + 1` maximums, or `[]` if
`len(A) < K`.

```text
def solution(A, K): -> list of int
```

**Examples**

* `solution([1, 3, -1, -3, 5, 3, 6, 7], 3)` returns `[3, 3, 5, 5, 6, 7]`
* `solution([4, 2, 2], 1)` returns `[4, 2, 2]`
* `solution([9, 8], 3)` returns `[]`

**Limits:** `len(A)` up to 1,000,000; `1 <= K <= 1,000,000`.

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import deque

    def solution(A, K):
        q = deque()
        out = []
        for i, x in enumerate(A):
            while q and A[q[-1]] <= x:
                q.pop()
            q.append(i)
            if q[0] <= i - K:
                q.popleft()
            if i >= K - 1:
                out.append(A[q[0]])
        return out
    ```

    The deque holds indexes whose values go down from front to back. A reading smaller than a newer one can never be
    a maximum again, so it is popped from the back. The front is the maximum of the window; it leaves when it falls
    out on the left. Each index goes in and out once. `max(A[i:i+K])` for every `i` is O(N·K): 10^12 steps at the
    limits. A running total trick (task 24) does not work for a maximum, because you cannot "subtract" the reading
    that leaves.

    **Cost:** O(N) time, O(K) memory.

    **Tests**

    ```python
    # tests
    import random
    assert solution([1, 3, -1, -3, 5, 3, 6, 7], 3) == [3, 3, 5, 5, 6, 7]
    assert solution([4, 2, 2], 1) == [4, 2, 2]
    assert solution([9, 8], 3) == []
    assert solution([5, 5, 5, 5], 2) == [5, 5, 5]
    assert solution([1, 2, 3], 3) == [3]
    for _ in range(500):
        A = [random.randint(-5, 5) for _ in range(random.randint(0, 15))]
        K = random.randint(1, 6)
        assert solution(A, K) == [max(A[i:i + K]) for i in range(len(A) - K + 1)]
    print('task 4: ok')
    ```


### 5. Diff two config dicts

**Level:** Medium · **Aim for:** 20 minutes

`A` is the old config and `B` the new one: dicts with string keys whose values are ints, strings, bools, lists or
nested dicts. Return every difference as a tuple `(path, kind, old, new)`, where `path` joins the keys with dots,
and `kind` is `'added'` (old is `None`), `'removed'` (new is `None`) or `'changed'`. When both sides have a dict
at the same key, go inside instead of reporting it. A value whose type changed (for example `1` to `True` or to
`'1'`) is `'changed'`. Order the result by path, comparing key by key (so `a.b` comes before `a_x`).

```text
def solution(A, B): -> list of (str, str, any, any)
```

**Examples**

* `solution({'db': {'host': 'x', 'port': 5432}, 'debug': False}, {'db': {'host': 'y', 'port': 5432}, 'v': 2})` returns `[('db.host', 'changed', 'x', 'y'), ('debug', 'removed', False, None), ('v', 'added', None, 2)]`
* `solution({'a': 1}, {'a': True})` returns `[('a', 'changed', 1, True)]`
* `solution({'a': {'b': 1}}, {'a': 5})` returns `[('a', 'changed', {'b': 1}, 5)]`

**Limits:** up to 100,000 keys in total, nested up to 50 levels.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A, B):
        out = []
        def go(a, b, p):
            for k in sorted(set(a) | set(b)):
                q = p + k
                if k not in b:
                    out.append((q, 'removed', a[k], None))
                elif k not in a:
                    out.append((q, 'added', None, b[k]))
                elif type(a[k]) is dict and type(b[k]) is dict:
                    go(a[k], b[k], q + '.')
                elif type(a[k]) != type(b[k]) or a[k] != b[k]:
                    out.append((q, 'changed', a[k], b[k]))
        go(A, B, '')
        return out
    ```

    Walking both dicts with the keys sorted at every level gives the order "key by key". Sorting the finished path
    strings does not: `'-'` comes before `'.'` in ASCII, so `'a-b'` would sort before `'a.b'`, while key by key `'a'`
    comes before `'a-b'` (the last test checks this). The other trap is `1 == True` and `1 == 1.0` in Python, so `!=`
    alone misses a config that switched from a number to a flag; checking the type also catches it. 50 levels is far below Python's default recursion limit of 1000.

    **Cost:** O(N log N) time for N keys (the sorts), O(N) memory.

    **Tests**

    ```python
    # tests
    assert solution({'db': {'host': 'x', 'port': 5432}, 'debug': False}, {'db': {'host': 'y', 'port': 5432}, 'v': 2}) == [('db.host', 'changed', 'x', 'y'), ('debug', 'removed', False, None), ('v', 'added', None, 2)]
    assert solution({'a': 1}, {'a': True}) == [('a', 'changed', 1, True)]
    assert solution({'a': {'b': 1}}, {'a': 5}) == [('a', 'changed', {'b': 1}, 5)]
    assert solution({}, {}) == []
    assert solution({'x': [1, 2]}, {'x': [1, 2]}) == []
    assert solution({'x': [1, 2]}, {'x': [2, 1]}) == [('x', 'changed', [1, 2], [2, 1])]
    assert solution({'a': {'b': 1}, 'a-b': 1, 'a_x': 1}, {'a': {'b': 2}, 'a_x': 1}) == [('a.b', 'changed', 1, 2), ('a-b', 'removed', 1, None)]
    assert solution({'a': {}}, {'a': {'n': {'m': 1}}}) == [('a.n', 'added', None, {'m': 1})]
    assert solution({'p': 1}, {'p': 1.0}) == [('p', 'changed', 1, 1.0)]
    print('task 5: ok')
    ```


### 6. Retry wait schedule

**Level:** Easy · **Aim for:** 12 minutes

A job that calls a flaky service retries with growing waits. The first wait is `base` milliseconds, and each next
wait is `factor` times the one before, but never more than `cap`. The job makes at most `tries` attempts in total
(so at most `tries - 1` waits), and the waits together may not go over `budget` milliseconds: stop before the
first wait that would go over. Return the list of waits. All inputs are ints. This is a pure function: it plans
the waits and does not sleep.

```text
def solution(base, factor, cap, tries, budget): -> list of int
```

**Examples**

* `solution(100, 2, 1000, 6, 10000)` returns `[100, 200, 400, 800, 1000]`
* `solution(100, 2, 1000, 10, 1500)` returns `[100, 200, 400, 800]` (these add up to 1500; the next wait, 1000, would make 2500)
* `solution(500, 3, 500, 1, 9999)` returns `[]` (one attempt, no retry)

**Limits:** `1 <= base <= cap <= 10^9`; `1 <= factor <= 10`; `1 <= tries <= 1,000,000`; `0 <= budget <= 10^15`.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(base, factor, cap, tries, budget):
        out, d, total = [], base, 0
        for _ in range(tries - 1):
            w = min(d, cap)
            if total + w > budget:
                break
            out.append(w)
            total += w
            if d < cap:
                d *= factor
        return out
    ```

    The obvious `min(cap, base * factor ** i)` is right, but with a million tries `factor ** i` becomes a number with
    hundreds of thousands of digits, and each step gets slower. Growing `d` only while it is under the cap keeps every
    number small. In a real system each wait usually gets random "jitter" so many clients do not retry at the same
    moment; that part is left out to keep the answer testable.

    **Cost:** O(tries) time, O(answer) memory.

    **Tests**

    ```python
    # tests
    import random
    assert solution(100, 2, 1000, 6, 10000) == [100, 200, 400, 800, 1000]
    assert solution(100, 2, 1000, 10, 1500) == [100, 200, 400, 800]
    assert solution(500, 3, 500, 1, 9999) == []
    assert solution(10, 1, 10, 4, 25) == [10, 10]
    assert solution(5, 2, 100, 3, 0) == []
    assert len(solution(1, 10, 10**9, 1000000, 10**15)) == 999999
    for _ in range(300):
        b = random.randint(1, 20); c = random.randint(b, 100); f = random.randint(1, 4)
        n = random.randint(1, 10); bud = random.randint(0, 300)
        want = []
        for i in range(n - 1):
            w = min(c, b * f ** i)
            if sum(want) + w > bud:
                break
            want.append(w)
        assert solution(b, f, c, n, bud) == want
    print('task 6: ok')
    ```


### 7. Clean phone numbers

**Level:** Medium · **Aim for:** 18 minutes

`A` is a list of phone numbers typed into a sign-up form in Canada and the US. A number is valid if, after removing
spaces, `-`, `.`, `(` and `)`, it has 10 digits, or 11 digits starting with `1`. A `+` is allowed only as the first
character, and then the number must be the 11-digit form. Any other character makes it invalid. The 10-digit part
(without the leading `1`) is area code, exchange and line; the area code and the exchange may not start with `0`
or `1`. Return a pair: the sorted list of distinct valid numbers written as `+1` and 10 digits, and how many
entries were invalid.

```text
def solution(A): -> (list of str, int)
```

**Examples**

* `solution(['(416) 555-0199', '+1 416.555.0199', '1-647-555-0100'])` returns `(['+14165550199', '+16475550100'], 0)`
* `solution(['555-0199', '+4165550199', '(116) 555-0199', '416 555 O199'])` returns `([], 4)`
* `solution([])` returns `([], 0)`

**Limits:** up to 1,000,000 entries, each up to 40 characters.

??? success "Solution and explanation (open after you try)"

    ```python
    def norm(s):
        s = s.strip()
        plus = s.startswith('+')
        if plus:
            s = s[1:]
        if any(c not in '0123456789 -.()' for c in s):
            return None
        d = ''.join(c for c in s if c in '0123456789')
        if len(d) == 11 and d[0] == '1':
            d = d[1:]
        elif plus or len(d) != 10:
            return None
        if d[0] in '01' or d[3] in '01':
            return None
        return '+1' + d

    def solution(A):
        ok, bad = set(), 0
        for s in A:
            r = norm(s)
            if r:
                ok.add(r)
            else:
                bad += 1
        return sorted(ok), bad
    ```

    Two traps. `str.isdigit()` is true for characters like `'²'` and Arabic-Indic digits, so a test with it would let
    them in; checking against `'0123456789'` does not. And `'+4165550199'` has 10 digits, but a `+` says a country
    code follows, and 4 is not 1, so it is rejected instead of quietly read as Toronto. The letter `O` in example 2
    (not a zero) is the usual typo.

    **Cost:** O(total length) time, O(V) memory for V valid numbers, plus O(V log V) to sort.

    **Tests**

    ```python
    # tests
    assert solution(['(416) 555-0199', '+1 416.555.0199', '1-647-555-0100']) == (['+14165550199', '+16475550100'], 0)
    assert solution(['555-0199', '+4165550199', '(116) 555-0199', '416 555 O199']) == ([], 4)
    assert solution([]) == ([], 0)
    assert solution(['416 155 0199']) == ([], 1)
    assert solution(['4165550199', '  4165550199  ']) == (['+14165550199'], 0)
    assert solution(['416555019²', '٤١٦5550199']) == ([], 2)
    assert solution(['1+4165550199', '++14165550199']) == ([], 2)
    assert solution(['21234567890', '2123456789']) == (['+12123456789'], 1)
    print('task 7: ok')
    ```


### 8. History rows from a change feed

**Level:** Medium · **Aim for:** 20 minutes

`A` is a list of changes `(key, date, value)`: from `date` (an ISO string like `'2026-03-01'`) on, `key` has
`value`. The list is in arrival order, not sorted. If one key has two changes on the same date, the one that
arrived later wins. Build the history table: one row `(key, value, valid_from, valid_to)` per version, where
`valid_to` is the date of the next version of that key, or `None` for the current one. A change that sets the same
value as the version before it is not a new version. Return the rows sorted by key, then `valid_from`.

```text
def solution(A): -> list of (str, any, str, str or None)
```

**Examples**

* `solution([('c1', '2026-01-05', 'Paris'), ('c1', '2026-01-01', 'Oslo'), ('c2', '2026-02-01', 'Rome')])` returns `[('c1', 'Oslo', '2026-01-01', '2026-01-05'), ('c1', 'Paris', '2026-01-05', None), ('c2', 'Rome', '2026-02-01', None)]`
* `solution([('k', '2026-01-01', 1), ('k', '2026-01-02', 1), ('k', '2026-01-03', 2)])` returns `[('k', 1, '2026-01-01', '2026-01-03'), ('k', 2, '2026-01-03', None)]`
* `solution([('k', '2026-01-01', 1), ('k', '2026-01-01', 7)])` returns `[('k', 7, '2026-01-01', None)]`

**Limits:** `len(A)` up to 1,000,000.

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(A):
        g = {}
        for k, d, v in A:
            g.setdefault(k, {})[d] = v
        out = []
        for k in sorted(g):
            rows = []
            for d, v in sorted(g[k].items()):
                if rows and rows[-1][1] == v:
                    continue
                if rows:
                    rows[-1][3] = d
                rows.append([k, v, d, None])
            out += [tuple(r) for r in rows]
        return out
    ```

    A dict of dates per key makes "later arrival wins" one assignment. ISO dates sort correctly as strings, so no
    parsing is needed. The step people miss is example 2: without the `continue`, an unchanged value makes an extra
    row and the history shows a change that never happened. This is the table a warehouse calls a type 2 slowly
    changing dimension.

    **Cost:** O(N log N) time, O(N) memory.

    **Tests**

    ```python
    # tests
    import random
    assert solution([('c1', '2026-01-05', 'Paris'), ('c1', '2026-01-01', 'Oslo'), ('c2', '2026-02-01', 'Rome')]) == [('c1', 'Oslo', '2026-01-01', '2026-01-05'), ('c1', 'Paris', '2026-01-05', None), ('c2', 'Rome', '2026-02-01', None)]
    assert solution([('k', '2026-01-01', 1), ('k', '2026-01-02', 1), ('k', '2026-01-03', 2)]) == [('k', 1, '2026-01-01', '2026-01-03'), ('k', 2, '2026-01-03', None)]
    assert solution([('k', '2026-01-01', 1), ('k', '2026-01-01', 7)]) == [('k', 7, '2026-01-01', None)]
    assert solution([]) == []
    assert solution([('k', '2026-01-02', 1), ('k', '2026-01-01', 2), ('k', '2026-01-03', 2)]) == [('k', 2, '2026-01-01', '2026-01-02'), ('k', 1, '2026-01-02', '2026-01-03'), ('k', 2, '2026-01-03', None)]
    for _ in range(300):
        A = [(random.choice('ab'), '2026-01-0' + str(random.randint(1, 5)), random.randint(0, 2)) for _ in range(random.randint(0, 10))]
        want = []
        for k in sorted(set(r[0] for r in A)):
            days = sorted(set(d for kk, d, v in A if kk == k))
            vals = [[v for kk, dd, v in A if kk == k and dd == d][-1] for d in days]
            keep = [i for i in range(len(days)) if i == 0 or vals[i] != vals[i - 1]]
            for j, i in enumerate(keep):
                want.append((k, vals[i], days[i], days[keep[j + 1]] if j + 1 < len(keep) else None))
        assert solution(A) == want
    print('task 8: ok')
    ```
