# Advanced Python: ten hard tasks

*The hardest kind of Python task a coding test sets: the plain answer is easy to write and far too slow, and the fast
one needs a data structure or an idea you have to know. Each task below says which technique it needs and why,
has a **Try it here** box that runs your code in the browser, and a folded solution with the slow answer, the cost,
and the wrong answers people usually give.*

!!! abstract "How to use this page"
    - Read the **technique** note before each task. If the idea is new to you, read the solution of that task first,
      then come back to it the next day and write it from a blank editor.
    - The limits matter: with `N` up to 100,000, an `O(N²)` answer is about 5 billion steps and fails the hidden
      speed tests. Every task here has an `O(N log N)` or `O(N)` answer.
    - **Run** tries the examples; **Check** also tries the edge cases listed in the solution. The hidden tests of a
      real test also try the largest inputs, so check the cost of your answer.
    - Easier tasks first? The [Python practice set](python-practice.md) builds up to these.

| Task | Technique | What it is for |
| --- | --- | --- |
| [1](#1-assign-jobs-to-servers) | Two heaps | "the smallest free ..." and "the next to finish ..." again and again |
| [2](#2-cheapest-route-between-data-centres) | Dijkstra (a heap of costs) | the cheapest path when links cost different amounts |
| [3](#3-when-did-the-network-become-connected) | Union-find | groups that merge over time |
| [4](#4-longest-rising-sequence-of-prices) | Dynamic programming with `bisect` | the longest increasing subsequence |
| [5](#5-most-profit-from-jobs-that-do-not-overlap) | Dynamic programming with `bisect` | choosing a set of jobs with the most value |
| [6](#6-running-median-of-response-times) | Two heaps, balanced | the median of a growing stream |
| [7](#7-longest-stretch-with-as-many-passes-as-failures) | Prefix balance and a dictionary | "as many of A as of B" in one pass |
| [8](#8-search-box-suggestions) | Sorting and `bisect` | prefix search |
| [9](#9-shortest-walk-through-a-warehouse) | Breadth-first search | the fewest steps on a grid or a graph |
| [10](#10-hits-of-a-small-cache) | `OrderedDict` | an LRU cache |

---

### 1. Assign jobs to servers

**Level:** Hard · **Aim for:** 40 minutes

!!! info "Technique: heaps"
    `heapq` keeps a list in heap order, so the smallest item is always `h[0]`; `heappush` and `heappop` cost
    `O(log n)`. Push tuples to order by several things at once: `(finish_time, server_number)`. For the largest
    instead of the smallest, push negated values.

A cluster has `K` servers, numbered from `0` to `K - 1`. Jobs arrive in order: job `i` arrives at second `A[i]`
(the arrival times never go down) and runs for `D[i]` seconds on one server. A server that finishes at second `t` can
take a job arriving at second `t`.

* A job that arrives when some servers are free goes to the free server with the **smallest number**.
* When no server is free, the job waits. Waiting jobs are served in the order they arrived, each on the first server
  to become free; if several become free at the same second, the one with the smallest number.

Return a list with the number of the server that runs each job.

**Examples**

* `solution(2, [0, 1, 2, 3], [5, 1, 2, 3])` returns `[0, 1, 1, 1]`
* `solution(3, [0, 0, 0, 0], [2, 2, 2, 2])` returns `[0, 1, 2, 0]`
* `solution(4, [], [])` returns `[]`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `A` and `D`, is an integer within the range [0..100,000];
* `K` is an integer within the range [1..100,000];
* `A` is sorted in non-decreasing order, each `A[i]` within the range [0..1,000,000,000];
* each `D[i]` is an integer within the range [1..1,000,000].

Start from:

```python
def solution(K, A, D):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    import heapq
    
    def solution(K, A, D):
        free = list(range(K))                # numbers of the free servers (already a valid heap)
        busy = []                            # (second it becomes free, server number)
        now = 0                              # waiting jobs start in order, so time never goes back
        out = []
        for a, d in zip(A, D):
            now = max(now, a)
            while busy and busy[0][0] <= now:            # every server done by now is free again
                heapq.heappush(free, heapq.heappop(busy)[1])
            if not free:                                 # nobody free: wait for the first to finish
                now, s = heapq.heappop(busy)
                heapq.heappush(free, s)
                while busy and busy[0][0] == now:        # others finishing at the same second
                    heapq.heappush(free, heapq.heappop(busy)[1])
            s = heapq.heappop(free)                      # the smallest free number
            heapq.heappush(busy, (now + d, s))
            out.append(s)
        return out
    ```
    
    **Why it works**
    
    * **A heap** (`heapq`) is a list kept in an order where the smallest item is always at index 0: `heappush` and
      `heappop` cost `O(log n)`. Reach for one whenever a task asks again and again for "the smallest" or "the
      earliest" of a changing set.
    * Two heaps model the two states of a server. `free` holds server numbers, so `heappop(free)` is the smallest free
      number. `busy` holds `(finish second, number)`, so `busy[0]` is the next server to finish, and among servers
      finishing at the same second, the smallest number.
    * `now` is the second the current job starts. Waiting jobs start in arrival order, so the next job can't start
      before the previous one did: `now = max(now, a)`.
    * When nobody is free, the job starts when the first server finishes. Servers finishing at that **same** second
      are moved to `free` too, so that the smallest number among them is chosen.
    * The plain answer looks through all `K` servers for every job: `O(N·K)`, 5 billion steps at the limits.
    
    **Cost:** O(N log K) time, O(K) memory.
    
    **The slow answer:** Looking through all K servers for every job: O(N·K), 5 billion steps at the limits.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, two servers free: the smaller number wins, not the one free for longer: `solution(2, [0, 0, 5], [3, 1, 1])` returns `[0, 1, 0]`;
    * edge case, a server that ends at the arrival second is free: `solution(1, [0, 3], [3, 1])` returns `[0, 0]`;
    * edge case, one server, everyone waits: `solution(1, [0, 0, 0], [2, 2, 2])` returns `[0, 0, 0]`;
    * edge case, waiting jobs keep their order: `solution(2, [0, 0, 1, 1], [4, 2, 1, 1])` returns `[0, 1, 1, 1]`;
    * edge case, a job that waited also finishes later: `solution(2, [0, 0, 0, 3], [3, 3, 1, 1])` returns `[0, 1, 0, 1]`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.125s.
    
    ??? failure "A common wrong answer: one heap of (free second, number): picks the server free for longest"
    
        ```python
        import heapq
        
        def solution(K, A, D):
            servers = [(0, s) for s in range(K)]
            now = 0
            out = []
            for a, d in zip(A, D):
                now = max(now, a)
                t, s = heapq.heappop(servers)
                now = max(now, t)
                heapq.heappush(servers, (now + d, s))
                out.append(s)
            return out
        ```
        
        Checked: edge: two servers free: the smaller number wins, not the one free for longer: got [0, 1, 1] want [0, 1, 0].
    
    ??? failure "A common wrong answer: starting each job at its arrival, even when it had to wait"
    
        ```python
        import heapq
        
        def solution(K, A, D):
            free = list(range(K))
            busy = []
            out = []
            for a, d in zip(A, D):
                while busy and busy[0][0] <= a:
                    heapq.heappush(free, heapq.heappop(busy)[1])
                if free:
                    s = heapq.heappop(free)
                else:
                    _, s = heapq.heappop(busy)
                heapq.heappush(busy, (a + d, s))
                out.append(s)
            return out
        ```
        
        Checked: edge: a job that waited also finishes later: got [0, 1, 0, 0] want [0, 1, 0, 1].
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(K, A, D):
            free_at = [0] * K                    # when each server is free again
            now = 0
            out = []
            for a, d in zip(A, D):
                now = max(now, a)
                if min(free_at) > now:
                    now = min(free_at)           # wait for the first server to finish
                s = min(i for i in range(K) if free_at[i] <= now)
                free_at[s] = now + d
                out.append(s)
            return out
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.125s).



---

### 2. Cheapest route between data centres

**Level:** Hard · **Aim for:** 35 minutes

!!! info "Technique: Dijkstra's shortest path"
    When every step costs the same, breadth-first search finds the shortest path. When steps cost different (non
    negative) amounts, keep a heap of `(cost so far, place)` and always continue from the cheapest. Build an
    adjacency list (`links[x]` = the neighbours of `x`) first.

There are `N` data centres, numbered from `0` to `N - 1`, and `M` network links. Link `k` joins centres `A[k]` and
`B[k]` in **both directions** and costs `C[k]` to use. Two centres may be joined by several links, and a link may
join a centre to itself.

Return the lowest total cost of sending data from centre `0` to centre `N - 1`, or `-1` if it can't get there.

**Examples**

* `solution(4, [0, 0, 1, 2], [1, 2, 3, 3], [1, 5, 10, 1])` returns `6`
* `solution(3, [0], [1], [4])` returns `-1`
* `solution(1, [], [], [])` returns `0`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [1..100,000];
* `M`, the length of `A`, `B` and `C`, is an integer within the range [0..200,000];
* each `A[k]` and `B[k]` is within the range [0..N - 1];
* each `C[k]` is an integer within the range [0..10,000].

Start from:

```python
def solution(N, A, B, C):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    import heapq
    
    def solution(N, A, B, C):
        links = [[] for _ in range(N)]
        for a, b, c in zip(A, B, C):
            links[a].append((b, c))
            links[b].append((a, c))          # both directions
        best = [None] * N                    # final cost of each centre, once known
        todo = [(0, 0)]                      # (cost so far, centre): cheapest first
        while todo:
            cost, x = heapq.heappop(todo)
            if best[x] is not None:          # already reached more cheaply: an old entry, skip it
                continue
            best[x] = cost
            if x == N - 1:
                return cost
            for y, c in links[x]:
                if best[y] is None:
                    heapq.heappush(todo, (cost + c, y))
        return -1
    ```
    
    **Why it works**
    
    * This is **Dijkstra's algorithm**: always continue from the cheapest place reached so far. A heap of
      `(cost, centre)` gives that place in `O(log n)`. The first time a centre comes out of the heap, its cost is final,
      because every other route to it would go through something at least as expensive (costs are never negative).
    * The same centre can be pushed several times with different costs. Instead of updating entries inside the heap,
      skip the old ones when they come out (`if best[x] is not None: continue`). This is the usual Python way.
    * Building the adjacency list `links` first makes "the links of `x`" a list lookup, not a scan of all `M` links.
    * **Breadth-first search finds the fewest links, not the lowest cost**: in the edge case "the cheapest route has
      more links", the direct link costs 10 and the two-link route costs 2.
    * Cost: `O((N + M) log M)`. The plain answer (Bellman-Ford, relaxing every link `N` times) is `O(N·M)`, but it also
      works with negative costs, which Dijkstra does not.
    
    **Cost:** O((N + M) log M) time, O(N + M) memory.
    
    **The slow answer:** Bellman-Ford, relaxing every link N times: O(N·M).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, the cheapest route has more links: `solution(3, [0, 0, 1], [2, 1, 2], [10, 1, 1])` returns `2`;
    * edge case, links work both ways: `solution(3, [1, 2], [0, 1], [2, 3])` returns `5`;
    * edge case, several links between the same centres: `solution(2, [0, 1, 0], [1, 0, 1], [9, 4, 7])` returns `4`;
    * edge case, free links: `solution(3, [0, 1], [1, 2], [0, 0])` returns `0`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.441s.
    
    ??? failure "A common wrong answer: breadth-first search: the fewest links instead of the lowest cost"
    
        ```python
        from collections import deque
        
        def solution(N, A, B, C):
            links = [[] for _ in range(N)]
            for a, b, c in zip(A, B, C):
                links[a].append((b, c))
                links[b].append((a, c))
            cost = [None] * N
            cost[0] = 0
            q = deque([0])
            while q:
                x = q.popleft()
                for y, c in links[x]:
                    if cost[y] is None:
                        cost[y] = cost[x] + c
                        q.append(y)
            return -1 if cost[N - 1] is None else cost[N - 1]
        ```
        
        Checked: example: got 11 want 6.
    
    ??? failure "A common wrong answer: links used in one direction only"
    
        ```python
        import heapq
        
        def solution(N, A, B, C):
            links = [[] for _ in range(N)]
            for a, b, c in zip(A, B, C):
                links[a].append((b, c))
            best = [None] * N
            todo = [(0, 0)]
            while todo:
                cost, x = heapq.heappop(todo)
                if best[x] is not None:
                    continue
                best[x] = cost
                for y, c in links[x]:
                    if best[y] is None:
                        heapq.heappush(todo, (cost + c, y))
            return -1 if best[N - 1] is None else best[N - 1]
        ```
        
        Checked: edge: links work both ways: got -1 want 5.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(N, A, B, C):
            INF = float("inf")
            dist = [INF] * N
            dist[0] = 0
            for _ in range(N):                   # Bellman-Ford: relax every link N times
                for a, b, c in zip(A, B, C):
                    if dist[a] + c < dist[b]:
                        dist[b] = dist[a] + c
                    if dist[b] + c < dist[a]:
                        dist[a] = dist[b] + c
            return -1 if dist[N - 1] == INF else dist[N - 1]
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.441s).



---

### 3. When did the network become connected?

**Level:** Hard · **Aim for:** 35 minutes

!!! info "Technique: union-find"
    A `parent` list where each item points towards the representative of its group. `root(x)` follows the pointers;
    joining two groups is one assignment. With path shortening, both are close to `O(1)`. Use it for "are these
    connected?", "how many groups?", "when did everything join?".

`N` machines, numbered from `0` to `N - 1`, start with no connections. Over time, links are switched on: at second
`T[k]` a link between machines `A[k]` and `B[k]` comes up, and it stays up. Two machines can talk if there is a path of
links between them. The links are listed in **no particular order** of time.

Return the first second at which **every** machine can talk to every other, or `-1` if that never happens. With
only one machine, return `0`.

**Examples**

* `solution(4, [0, 1, 2, 0], [1, 2, 3, 3], [5, 3, 9, 4])` returns `5`
* `solution(3, [0], [1], [1])` returns `-1`
* `solution(1, [], [], [])` returns `0`

**Write an efficient algorithm for the following assumptions:**

* `N` is an integer within the range [1..100,000];
* `M`, the length of `A`, `B` and `T`, is an integer within the range [0..200,000];
* each `A[k]` and `B[k]` is within the range [0..N - 1];
* each `T[k]` is an integer within the range [0..1,000,000,000].

Start from:

```python
def solution(N, A, B, T):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(N, A, B, T):
        parent = list(range(N))              # each machine starts as its own group
    
        def root(x):                         # the group's representative
            while parent[x] != x:
                parent[x] = parent[parent[x]]    # shorten the path as we go
                x = parent[x]
            return x
    
        groups = N
        if groups == 1:
            return 0
        for t, a, b in sorted(zip(T, A, B)):     # links in time order
            ra, rb = root(a), root(b)
            if ra != rb:
                parent[ra] = rb              # join the two groups
                groups -= 1
                if groups == 1:
                    return t
        return -1
    ```
    
    **Why it works**
    
    * **Union-find** (also called disjoint sets) keeps machines in groups and answers two questions fast: "which group
      is `x` in?" (`root`) and "join these two groups". Each group is a small tree; its root names the group.
    * Sort the links by time and add them one by one. A link inside one group changes nothing; a link between two groups
      joins them and lowers the count of groups by 1. The moment the count reaches 1, every machine can talk to every
      other.
    * `parent[x] = parent[parent[x]]` (path halving) keeps the trees flat, so each `root` call is almost constant time.
    * Counting links is not enough: three links can make a loop of three machines and leave the fourth alone (edge
      case "enough links, but they form a loop").
    * Cost: `O(M log M)` for the sort plus nearly `O(M)` for the joins. The plain answer rebuilds the network and
      searches it for every second: `O(M·(N + M))`.
    
    **Cost:** O(M log M) time for the sort; the joins are nearly O(M). O(N + M) memory.
    
    **The slow answer:** Rebuilding and searching the network for every second: O(M·(N + M)).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, enough links, but they form a loop and leave one machine out: `solution(4, [0, 1, 2], [1, 2, 0], [1, 2, 3])` returns `-1`;
    * edge case, links switched on at the same second: `solution(3, [0, 1], [1, 2], [7, 7])` returns `7`;
    * edge case, a link from a machine to itself: `solution(2, [0, 0], [0, 1], [1, 2])` returns `2`;
    * edge case, a later link joins the last group: `solution(3, [0, 1, 0], [1, 0, 2], [1, 2, 9])` returns `9`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.409s.
    
    ??? failure "A common wrong answer: links taken in the order given, not in time order"
    
        ```python
        def solution(N, A, B, T):
            parent = list(range(N))
        
            def root(x):
                while parent[x] != x:
                    x = parent[x]
                return x
        
            groups = N
            if groups == 1:
                return 0
            for a, b, t in zip(A, B, T):
                ra, rb = root(a), root(b)
                if ra != rb:
                    parent[ra] = rb
                    groups -= 1
                    if groups == 1:
                        return t
            return -1
        ```
        
        Checked: example: got 9 want 5.
    
    ??? failure "A common wrong answer: counting links: N - 1 links means connected"
    
        ```python
        def solution(N, A, B, T):
            if N == 1:
                return 0
            times = sorted(t for a, b, t in zip(A, B, T) if a != b)
            return times[N - 2] if len(times) >= N - 1 else -1
        ```
        
        Checked: edge: enough links, but they form a loop and leave one machine out: got 3 want -1.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(N, A, B, T):
            if N == 1:
                return 0
            for limit in sorted(set(T)):         # try each second, from the earliest
                adj = [[] for _ in range(N)]
                for a, b, t in zip(A, B, T):
                    if t <= limit:
                        adj[a].append(b)
                        adj[b].append(a)
                seen = {0}
                stack = [0]
                while stack:
                    x = stack.pop()
                    for y in adj[x]:
                        if y not in seen:
                            seen.add(y)
                            stack.append(y)
                if len(seen) == N:
                    return limit
            return -1
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.409s).



---

### 4. Longest rising sequence of prices

**Level:** Hard · **Aim for:** 35 minutes

!!! info "Technique: dynamic programming"
    Solve the problem for every prefix (or every item, in a useful order) and build each answer from earlier ones.
    The trick is choosing **what to remember**: here, the smallest possible last value of a rising pick of each
    length. `bisect_left(a, x)` finds in `O(log n)` where `x` belongs in the sorted list `a`.

`P` lists a share's closing prices, day by day. Pick some of the days, keeping their order (the days need not be
next to each other), so that each picked price is **strictly higher** than the one picked before. Return the largest
number of days you can pick.

**Examples**

* `solution([10, 9, 2, 5, 3, 7, 101, 18])` returns `4`
* `solution([7, 7, 7])` returns `1`
* `solution([])` returns `0`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `P`, is an integer within the range [0..100,000];
* each `P[i]` is an integer within the range [1..1,000,000,000].

Start from:

```python
def solution(P):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from bisect import bisect_left
    
    def solution(P):
        tails = []        # tails[k]: the smallest last price of any rising pick of length k + 1
        for p in P:
            k = bisect_left(tails, p)        # the first tail >= p
            if k == len(tails):
                tails.append(p)              # p extends the longest pick so far
            else:
                tails[k] = p                 # p is a lower (better) end for picks of length k + 1
        return len(tails)
    ```
    
    **Why it works**
    
    * This is the **longest increasing subsequence**, a classic of **dynamic programming**: solve the problem for
      every prefix and build on those answers. The plain version keeps, for every day, the longest pick ending there and
      looks back at all earlier days: `O(N²)`, 5 billion steps for 100,000 days.
    * The fast version keeps one short list, `tails`, where `tails[k]` is the **smallest** price a rising pick of length
      `k + 1` can end on. A lower end is always better, because more later prices can follow it. The list is always
      sorted, so `bisect_left` finds in `O(log N)` where a new price belongs.
    * A price larger than every tail makes the longest pick one longer. Otherwise it replaces the first tail that is
      not smaller than it. `tails` is **not** itself a valid pick, only its length is the answer.
    * `bisect_left`, not `bisect_right`: an equal price must replace the tail, not be appended after it, because equal
      is not rising (edge case "equal prices are not rising").
    
    **Cost:** O(N log N) time, O(N) memory.
    
    **The slow answer:** The longest pick ending on each day, looking back at every earlier day: O(N²).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, a falling price: `solution([5, 4, 3, 2, 1])` returns `1`;
    * edge case, equal prices are not rising: `solution([1, 2, 2, 3])` returns `3`;
    * edge case, the best picks are not next to each other: `solution([3, 1, 4, 1, 5, 9, 2, 6])` returns `4`;
    * edge case, one day: `solution([42])` returns `1`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.020s.
    
    ??? failure "A common wrong answer: bisect_right: counts equal prices as rising"
    
        ```python
        from bisect import bisect_right
        
        def solution(P):
            tails = []
            for p in P:
                k = bisect_right(tails, p)
                if k == len(tails):
                    tails.append(p)
                else:
                    tails[k] = p
            return len(tails)
        ```
        
        Checked: example: got 3 want 1.
    
    ??? failure "A common wrong answer: the longest run of rising days next to each other"
    
        ```python
        def solution(P):
            best = run = 0
            for i, p in enumerate(P):
                run = run + 1 if i and p > P[i - 1] else 1
                best = max(best, run)
            return best
        ```
        
        Checked: example: got 3 want 4.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(P):
            best = [1] * len(P)                  # best[i]: longest rising pick ending on day i
            for i in range(len(P)):
                for j in range(i):
                    if P[j] < P[i]:
                        best[i] = max(best[i], best[j] + 1)
            return max(best, default=0)
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.020s).



### 5. Most profit from jobs that do not overlap

**Level:** Hard · **Aim for:** 45 minutes

A contractor is offered `N` jobs. Job `i` runs from time `S[i]` up to time `E[i]` (the end is not included, so a
job ending at time `t` and one starting at `t` can both be taken) and pays `P[i]`. The contractor can do one job at a
time. Return the largest total pay from a set of jobs that do not overlap.

**Examples**

* `solution([1, 2, 3, 3], [3, 4, 5, 6], [50, 10, 40, 70])` returns `120`
* `solution([1, 2, 3, 4, 6], [3, 5, 10, 6, 9], [20, 20, 100, 70, 60])` returns `150`
* `solution([], [], [])` returns `0`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `S`, `E` and `P`, is an integer within the range [0..100,000];
* `0 ≤ S[i] < E[i] ≤ 1,000,000,000`;
* each `P[i]` is an integer within the range [1..1,000,000].

Start from:

```python
def solution(S, E, P):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from bisect import bisect_right
    
    def solution(S, E, P):
        jobs = sorted(zip(E, S, P))          # by end time
        ends = [e for e, _, _ in jobs]
        best = [0] * (len(jobs) + 1)         # best[k]: most pay using only the first k jobs (by end)
        for k, (e, s, p) in enumerate(jobs):
            j = bisect_right(ends, s, 0, k)  # jobs among the first k that end at or before s
            best[k + 1] = max(best[k],       # skip job k
                              best[j] + p)   # take job k, after the best of the jobs that end in time
        return best[-1]
    ```
    
    **Why it works**
    
    * **Dynamic programming with a choice per item.** Sort the jobs by end time. For each job there are two choices:
      skip it (keep the best so far, `best[k]`), or take it and add its pay to the best you could do with the jobs that
      **end by the time it starts**. Take the larger.
    * Because the jobs are sorted by end, "the jobs that end by time `s`" are a **prefix** of the list, and
      `bisect_right(ends, s, 0, k)` finds its length in `O(log N)`. `bisect_right` (not `bisect_left`) includes jobs that
      end exactly at `s`: touching jobs may both be taken.
    * A **greedy** rule (always take the job that ends first, or the one that pays most) fails: in the edge case "one
      long job pays more", the three short jobs end first but pay 3 in all, against 100.
    * Cost: `O(N log N)`. The plain version scans every earlier job for each job: `O(N²)`.
    
    **Cost:** O(N log N) time, O(N) memory.
    
    **The slow answer:** Scanning every earlier job for each job: O(N²).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, one long job pays more than many short ones: `solution([0, 0, 1, 2], [10, 1, 2, 3], [100, 1, 1, 1])` returns `100`;
    * edge case, jobs that touch can both be taken: `solution([0, 5], [5, 10], [3, 4])` returns `7`;
    * edge case, identical jobs: only one can be taken: `solution([2, 2], [4, 4], [6, 6])` returns `6`;
    * edge case, one job: `solution([0], [1], [5])` returns `5`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.115s.
    
    ??? failure "A common wrong answer: greedy: take the job that ends first, whenever it fits"
    
        ```python
        def solution(S, E, P):
            total, free_from = 0, None
            for e, s, p in sorted(zip(E, S, P)):
                if free_from is None or s >= free_from:
                    total += p
                    free_from = e
            return total
        ```
        
        Checked: example: got 90 want 120.
    
    ??? failure "A common wrong answer: bisect_left: jobs that touch are treated as overlapping"
    
        ```python
        from bisect import bisect_left
        
        def solution(S, E, P):
            jobs = sorted(zip(E, S, P))
            ends = [e for e, _, _ in jobs]
            best = [0] * (len(jobs) + 1)
            for k, (e, s, p) in enumerate(jobs):
                j = bisect_left(ends, s, 0, k)
                best[k + 1] = max(best[k], best[j] + p)
            return best[-1]
        ```
        
        Checked: example: got 70 want 120.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(S, E, P):
            jobs = sorted(zip(E, S, P))
            best = [0] * (len(jobs) + 1)
            for k, (e, s, p) in enumerate(jobs):
                j = 0
                for i in range(k):               # look at every earlier job
                    if jobs[i][0] <= s:
                        j = i + 1
                best[k + 1] = max(best[k], best[j] + p)
            return best[-1]
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.115s).



---

### 6. Running median of response times

**Level:** Hard · **Aim for:** 35 minutes

!!! info "Technique: two heaps"
    Split the items into a smaller half (a max-heap, stored as negatives) and a larger half (a min-heap), and keep
    their sizes within one of each other. The median is then at the top of one heap, available in `O(1)` after
    every insert.

A monitoring job reads response times one by one: `A[0]`, `A[1]`, and so on. After each new reading it reports the
**median** of all readings so far: the middle value when they are sorted. When the count is even, it reports the
**smaller** of the two middle values (so the answer is always one of the readings).

Return the list of reported values, one per reading.

**Examples**

* `solution([5, 15, 1, 3])` returns `[5, 5, 5, 3]`
* `solution([2, 2, 2])` returns `[2, 2, 2]`
* `solution([])` returns `[]`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `A`, is an integer within the range [0..100,000];
* each `A[i]` is an integer within the range [0..1,000,000,000].

Start from:

```python
def solution(A):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    import heapq
    
    def solution(A):
        low = []     # the smaller half, as negatives: -low[0] is the largest of the small half
        high = []    # the larger half: high[0] is the smallest of the large half
        out = []
        for x in A:
            if low and x > -low[0]:
                heapq.heappush(high, x)
            else:
                heapq.heappush(low, -x)
            # keep the halves balanced: low has the same number of items as high, or one more
            if len(low) > len(high) + 1:
                heapq.heappush(high, -heapq.heappop(low))
            elif len(high) > len(low):
                heapq.heappush(low, -heapq.heappop(high))
            out.append(-low[0])              # the largest of the small half is the (lower) median
        return out
    ```
    
    **Why it works**
    
    * **Two heaps** split the readings into a smaller half and a larger half. Python's `heapq` only gives the smallest
      item, so the smaller half stores **negated** values: then `-low[0]` is its largest item. The median is always at
      the boundary between the halves.
    * Each new reading goes to the half it belongs to, then one item moves across if the halves differ in size by more
      than allowed. Keeping `low` equal to `high` or one bigger makes `-low[0]` the middle value for an odd count and
      the smaller middle value for an even count.
    * Each step costs `O(log N)`, so the whole list costs `O(N log N)`. Sorting again after every reading costs
      `O(N² log N)`.
    * The same structure answers "the median of a moving stream", and with lazy deletion, "the median of the last K".
    
    **Cost:** O(N log N) time, O(N) memory.
    
    **The slow answer:** Sorting all readings again after each one: O(N² log N).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, rising readings: `solution([1, 2, 3, 4, 5])` returns `[1, 1, 2, 2, 3]`;
    * edge case, falling readings: `solution([5, 4, 3, 2, 1])` returns `[5, 4, 4, 3, 3]`;
    * edge case, one reading: `solution([7])` returns `[7]`;
    * edge case, an even count reports the smaller middle: `solution([10, 20])` returns `[10, 10]`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.040s.
    
    ??? failure "A common wrong answer: the larger middle value when the count is even"
    
        ```python
        def solution(A):
            out = []
            for i in range(len(A)):
                s = sorted(A[:i + 1])
                out.append(s[len(s) // 2])
            return out
        ```
        
        Checked: example: got [5, 15, 5, 5] want [5, 5, 5, 3].
    
    ??? failure "A common wrong answer: no rebalancing: the halves drift apart"
    
        ```python
        import heapq
        
        def solution(A):
            low, high, out = [], [], []
            for x in A:
                if low and x > -low[0]:
                    heapq.heappush(high, x)
                else:
                    heapq.heappush(low, -x)
                out.append(-low[0])
            return out
        ```
        
        Checked: example: got [5, 5, 5, 5] want [5, 5, 5, 3].
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(A):
            out = []
            for i in range(len(A)):
                s = sorted(A[:i + 1])
                out.append(s[(len(s) - 1) // 2])
            return out
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.040s).



---

### 7. Longest stretch with as many passes as failures

**Level:** Medium · **Aim for:** 25 minutes

!!! info "Technique: prefix sums and a dictionary"
    A running total turns "a stretch with total X" into "two positions whose running totals differ by X". A
    dictionary from running total to its first position answers that in one pass.

`S` records the nightly test runs of a project: `'P'` for a pass and `'F'` for a failure. Return the length of the
longest stretch of **consecutive** nights with exactly as many passes as failures (0 if there is none).

**Examples**

* `solution('PFFPPF')` returns `6`
* `solution('PPPF')` returns `2`
* `solution('')` returns `0`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `S`, is an integer within the range [0..100,000];
* `S` contains only the characters `'P'` and `'F'`.

Start from:

```python
def solution(S):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    def solution(S):
        first = {0: -1}      # balance -> the first position where it was seen (-1: before the start)
        balance = best = 0
        for i, c in enumerate(S):
            balance += 1 if c == "P" else -1
            if balance in first:
                best = max(best, i - first[balance])   # equal balances: the stretch between is even
            else:
                first[balance] = i
        return best
    ```
    
    **Why it works**
    
    * **A running balance:** add 1 for a pass and subtract 1 for a failure. A stretch has as many passes as failures
      exactly when the balance is the **same** at its two ends. So the question becomes: which two positions with the
      same balance are furthest apart?
    * Remember only the **first** position of each balance (a dictionary). At every later position with that balance,
      the stretch since the first one is balanced; the first is the furthest back, so it gives the longest.
    * `{0: -1}` stands for the empty start: the balance is 0 before the first night, so a balanced stretch that starts
      on night 0 is found too.
    * This is the same idea as "slices that sum to K" (a prefix sum and a dictionary), and it answers any "equal number
      of two kinds" question in `O(N)`. Checking every stretch is `O(N²)`.
    
    **Cost:** O(N) time, O(N) memory.
    
    **The slow answer:** Counting passes and failures in every stretch: O(N²).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, all passes: `solution('PPPP')` returns `0`;
    * edge case, the stretch is in the middle: `solution('PPFPFFPP')` returns `6`;
    * edge case, one of each: `solution('FP')` returns `2`;
    * edge case, several equal stretches: `solution('PFPFPPP')` returns `4`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.010s.
    
    ??? failure "A common wrong answer: updating the position every time: keeps the latest, not the first"
    
        ```python
        def solution(S):
            last = {0: -1}
            balance = best = 0
            for i, c in enumerate(S):
                balance += 1 if c == "P" else -1
                if balance in last:
                    best = max(best, i - last[balance])
                last[balance] = i
            return best
        ```
        
        Checked: example: got 4 want 6.
    
    ??? failure "A common wrong answer: only stretches that start on the first night"
    
        ```python
        def solution(S):
            balance = best = 0
            for i, c in enumerate(S):
                balance += 1 if c == "P" else -1
                if balance == 0:
                    best = i + 1
            return best
        ```
        
        Checked: example: got 0 want 2.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(S):
            best = 0
            for i in range(len(S)):
                p = f = 0
                for j in range(i, len(S)):
                    if S[j] == "P":
                        p += 1
                    else:
                        f += 1
                    if p == f:
                        best = max(best, j - i + 1)
            return best
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.010s).



---

### 8. Search box suggestions

**Level:** Medium · **Aim for:** 30 minutes

!!! info "Technique: sort once, search many times"
    In a sorted list, everything that starts with the same prefix sits together, and `bisect` finds where it begins
    in `O(log n)`. Many "search" tasks are a sort plus a binary search.

A search box suggests words as the user types. `W` is the list of known words (it may contain the same word more than
once). For each query `Q[j]`, return up to **three different** words that start with the query, in alphabetical
order (the first three alphabetically). Return a list with one list of suggestions per query.

**Examples**

* `solution(['mouse', 'monitor', 'mousepad', 'money', 'mobile', 'monitor'], ['mo', 'mou', 'x'])` returns `[['mobile', 'money', 'monitor'], ['mouse', 'mousepad'], []]`
* `solution([], ['a'])` returns `[[]]`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `W`, and `M`, the length of `Q`, are integers within the range [0..100,000];
* every word and query is a non-empty string of lower-case letters `a` to `z`, at most 20 characters long.

Start from:

```python
def solution(W, Q):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from bisect import bisect_left
    
    def solution(W, Q):
        words = sorted(set(W))               # unique, alphabetical
        out = []
        for q in Q:
            i = bisect_left(words, q)        # the first word >= q: where words starting with q begin
            found = []
            while i < len(words) and len(found) < 3 and words[i].startswith(q):
                found.append(words[i])
                i += 1
            out.append(found)
        return out
    ```
    
    **Why it works**
    
    * **Sort once, then binary search.** In a sorted list, all the words that start with `q` sit **next to each other**,
      starting at the first word that is not smaller than `q`. `bisect_left` finds that place in `O(log N)`, and the
      answer is at most the three words from there on that still start with `q`.
    * `set(W)` first: repeated words must be suggested once.
    * Check `startswith` for each of the three: after the matching words come words that are larger but do not start
      with `q` (after `"mou..."` comes `"x"`), and a query with no match at all finds such a word straight away.
    * Cost: `O(N log N)` to sort, then `O(log N + 3)` per query, with at most 20 letters per comparison. The plain
      answer scans every word for every query: `O(N·M)`, 10 billion comparisons at the limits.
    * A **trie** (a tree of letters) is the textbook structure for prefixes; sorting plus `bisect` gives the same result
      in a few lines, which is what a timed test needs.
    
    **Cost:** O(N log N) to sort, then O(log N) per query.
    
    **The slow answer:** Scanning every word for every query: O(N·M).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, a query that is itself a word: `solution(['car', 'card', 'care', 'cart'], ['car'])` returns `[['car', 'card', 'care']]`;
    * edge case, repeated words are suggested once: `solution(['ab', 'ab', 'ab', 'abc'], ['a'])` returns `[['ab', 'abc']]`;
    * edge case, a query longer than every word: `solution(['go'], ['gopher'])` returns `[[]]`;
    * edge case, words after the matches do not count: `solution(['apple', 'banana', 'berry'], ['app'])` returns `[['apple']]`;
    * edge case, no queries: `solution(['a', 'b'], [])` returns `[]`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.118s.
    
    ??? failure "A common wrong answer: no set(): repeated words are suggested twice"
    
        ```python
        from bisect import bisect_left
        
        def solution(W, Q):
            words = sorted(W)
            out = []
            for q in Q:
                i = bisect_left(words, q)
                found = []
                while i < len(words) and len(found) < 3 and words[i].startswith(q):
                    found.append(words[i])
                    i += 1
                out.append(found)
            return out
        ```
        
        Checked: edge: repeated words are suggested once: got [['ab', 'ab', 'ab']] want [['ab', 'abc']].
    
    ??? failure "A common wrong answer: taking the next three words without checking the prefix"
    
        ```python
        from bisect import bisect_left
        
        def solution(W, Q):
            words = sorted(set(W))
            return [words[bisect_left(words, q):bisect_left(words, q) + 3] for q in Q]
        ```
        
        Checked: edge: words after the matches do not count: got [['apple', 'banana', 'berry']] want [['apple']].
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(W, Q):
            return [sorted({w for w in W if w.startswith(q)})[:3] for q in Q]
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.118s).



---

### 9. Shortest walk through a warehouse

**Level:** Medium · **Aim for:** 30 minutes

!!! info "Technique: breadth-first search"
    A `deque` of places to visit, nearest first, and a record of places already seen. On a grid, a "place" is a
    `(row, column)` pair and its neighbours are the four cells around it.

A warehouse floor is a grid given as a list of equal-length strings. `'.'` is floor, `'#'` is a shelf, `'S'` is where
a robot starts and `'E'` is where it must go (each appears exactly once). In one step the robot moves to the next
cell up, down, left or right (not diagonally), never onto a shelf or off the grid.

Return the smallest number of steps from `S` to `E`, or `-1` if `E` can't be reached.

**Examples**

* `solution(['S.#', '..#', '#.E'])` returns `4`
* `solution(['S#E'])` returns `-1`
* `solution(['SE'])` returns `1`

**Write an efficient algorithm for the following assumptions:**

* the grid has `R` rows and `C` columns, with `R · C` within the range [2..250,000];
* every string has length `C` and contains only `.`, `#`, `S` and `E`.

Start from:

```python
def solution(G):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import deque
    
    def solution(G):
        R, C = len(G), len(G[0])
        for r in range(R):
            for c in range(C):
                if G[r][c] == "S":
                    start = (r, c)
        dist = {start: 0}
        q = deque([start])                   # cells to visit, nearest first
        while q:
            r, c = q.popleft()
            if G[r][c] == "E":
                return dist[(r, c)]
            for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= nr < R and 0 <= nc < C and G[nr][nc] != "#" and (nr, nc) not in dist:
                    dist[(nr, nc)] = dist[(r, c)] + 1
                    q.append((nr, nc))
        return -1
    ```
    
    **Why it works**
    
    * **Breadth-first search (BFS)** explores the grid in rings: first every cell 1 step away, then every cell 2 steps
      away, and so on. A `deque` (a queue with fast `popleft`) keeps that order. The first time `E` comes out of the
      queue, its distance is the shortest; every step costs the same, so no heap is needed (compare Dijkstra, where steps
      have different costs).
    * Mark a cell as seen **when it is added** to the queue (`dist[...] = ...`), not when it is taken out; otherwise the
      same cell can be added many times and the search slows down badly on open floors.
    * `list.pop(0)` instead of `deque.popleft()` gives the same answer but costs `O(n)` per step.
    * A depth-first search finds **a** path, not the shortest one.
    * Cost: `O(R·C)`: each cell is visited once. The plain answer relaxes every cell until nothing changes, which can
      take as many rounds as the path is long.
    
    **Cost:** O(R·C) time and memory: each cell is visited once.
    
    **The slow answer:** Relaxing every cell until nothing changes: O((R·C)²) in the worst case.
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, a long way round: `solution(['S.#E', '.#..', '....'])` returns `7`;
    * edge case, an open floor: `solution(['S..', '...', 'E..'])` returns `2`;
    * edge case, walled in: `solution(['S#.', '##.', '..E'])` returns `-1`;
    * edge case, diagonal moves are not allowed: `solution(['S#', '#E'])` returns `-1`;
    * edge case, a single column: `solution(['S', '.', '.', 'E'])` returns `3`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.305s.
    
    ??? failure "A common wrong answer: diagonal moves allowed"
    
        ```python
        from collections import deque
        
        def solution(G):
            R, C = len(G), len(G[0])
            start = next((r, c) for r in range(R) for c in range(C) if G[r][c] == "S")
            dist = {start: 0}
            q = deque([start])
            while q:
                r, c = q.popleft()
                if G[r][c] == "E":
                    return dist[(r, c)]
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < R and 0 <= nc < C and G[nr][nc] != "#" and (nr, nc) not in dist:
                            dist[(nr, nc)] = dist[(r, c)] + 1
                            q.append((nr, nc))
            return -1
        ```
        
        Checked: example: got 2 want 4.
    
    ??? failure "A common wrong answer: depth-first search: the first path found, not the shortest"
    
        ```python
        def solution(G):
            R, C = len(G), len(G[0])
            start = next((r, c) for r in range(R) for c in range(C) if G[r][c] == "S")
            dist = {start: 0}
            stack = [start]
            while stack:
                r, c = stack.pop()
                if G[r][c] == "E":
                    return dist[(r, c)]
                for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                    if 0 <= nr < R and 0 <= nc < C and G[nr][nc] != "#" and (nr, nc) not in dist:
                        dist[(nr, nc)] = dist[(r, c)] + 1
                        stack.append((nr, nc))
            return -1
        ```
        
        Checked: edge: an open floor: got 6 want 2.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(G):
            R, C = len(G), len(G[0])
            INF = float("inf")
            d = [[INF] * C for _ in range(R)]
            for r in range(R):
                for c in range(C):
                    if G[r][c] == "S":
                        d[r][c] = 0
            changed = True
            while changed:                       # relax every cell until nothing improves
                changed = False
                for r in range(R):
                    for c in range(C):
                        if G[r][c] == "#":
                            continue
                        for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                            if 0 <= nr < R and 0 <= nc < C and d[nr][nc] + 1 < d[r][c]:
                                d[r][c] = d[nr][nc] + 1
                                changed = True
            for r in range(R):
                for c in range(C):
                    if G[r][c] == "E":
                        return -1 if d[r][c] == INF else d[r][c]
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.305s).



---

### 10. Hits of a small cache

**Level:** Medium · **Aim for:** 25 minutes

!!! info "Technique: an ordered dictionary"
    `collections.OrderedDict` is a dictionary that also keeps its keys in order, with `move_to_end(key)` and
    `popitem(last=False)` in `O(1)`: a dictionary and a queue at once.

A service keeps the results of at most `C` different keys in a cache. Requests arrive in the order of `R`. For each
request:

* if the key is in the cache, it is a **hit**, and the key becomes the most recently used;
* otherwise it is a miss: the key is added as the most recently used, and if the cache then holds more than `C`
  keys, the **least recently used** key is removed.

Return the number of hits. With `C = 0` nothing is ever kept.

**Examples**

* `solution(2, [1, 2, 1, 3, 2, 1])` returns `1`
* `solution(3, [5, 5, 5])` returns `2`
* `solution(0, [1, 1])` returns `0`

**Write an efficient algorithm for the following assumptions:**

* `N`, the length of `R`, is an integer within the range [0..100,000];
* `C` is an integer within the range [0..100,000];
* each key is an integer within the range [0..1,000,000,000].

Start from:

```python
def solution(C, R):
    pass
```

??? success "Solution and explanation (open after you try)"

    ```python
    from collections import OrderedDict
    
    def solution(C, R):
        cache = OrderedDict()                # keys from least to most recently used
        hits = 0
        for key in R:
            if key in cache:
                hits += 1
                cache.move_to_end(key)       # now the most recently used
            elif C > 0:
                cache[key] = True            # added at the end: most recently used
                if len(cache) > C:
                    cache.popitem(last=False)    # remove from the front: least recently used
        return hits
    ```
    
    **Why it works**
    
    * An **LRU cache** (least recently used) needs two things at once: "is this key in the cache?" in `O(1)`, like a
      dictionary, and "which key was used longest ago?" in `O(1)`, like a queue. `collections.OrderedDict` gives both:
      it remembers the order of its keys, `move_to_end` moves a key to the newest end, and `popitem(last=False)` removes
      the oldest.
    * Since Python 3.7 a plain `dict` keeps insertion order too; `del d[k]; d[k] = v` moves a key to the end, and
      `next(iter(d))` is the oldest key. `OrderedDict` says what you mean.
    * The trap is the word **used**: a hit must move the key to the newest end. Without that, the cache removes the
      oldest **added** key (first in, first out), which is a different policy and gives a different count.
    * Cost: `O(N)`. A list works but `key in cache` and `remove` scan it: `O(N·C)`.
    
    **Cost:** O(N) time, O(C) memory.
    
    **The slow answer:** A list as the cache: every `in` and `remove` scans it, O(N·C).
    
    **Tested** (Python 3.13; standard library only):
    
    * the examples above;
    * edge case, a hit protects a key from removal: `solution(2, [1, 2, 1, 3, 1])` returns `2`;
    * edge case, room for everything: `solution(10, [1, 2, 3, 1, 2, 3])` returns `3`;
    * edge case, a cache of one: `solution(1, [4, 4, 5, 4])` returns `1`;
    * edge case, no requests: `solution(3, [])` returns `0`;
    * 1000 random small inputs, each compared with a slow but obviously correct answer;
    * the largest input the limits allow: 0.037s.
    
    ??? failure "A common wrong answer: first in, first out: a hit does not refresh the key"
    
        ```python
        from collections import OrderedDict
        
        def solution(C, R):
            cache = OrderedDict()
            hits = 0
            for key in R:
                if key in cache:
                    hits += 1
                elif C > 0:
                    cache[key] = True
                    if len(cache) > C:
                        cache.popitem(last=False)
            return hits
        ```
        
        Checked: example: got 2 want 1.
    
    ??? failure "A common wrong answer: removing before adding, even on a hit (off by one)"
    
        ```python
        from collections import OrderedDict
        
        def solution(C, R):
            cache = OrderedDict()
            hits = 0
            for key in R:
                if len(cache) >= C and cache:
                    cache.popitem(last=False)
                if key in cache:
                    hits += 1
                    cache.move_to_end(key)
                elif C > 0:
                    cache[key] = True
            return hits
        ```
        
        Checked: example: got 0 want 1.
    
    ??? failure "The plain answer: right, but too slow"
    
        ```python
        def solution(C, R):
            cache = []                           # least recently used first
            hits = 0
            for key in R:
                if key in cache:
                    hits += 1
                    cache.remove(key)
                    cache.append(key)
                elif C > 0:
                    cache.append(key)
                    if len(cache) > C:
                        cache.pop(0)
            return hits
        ```
        
        It gives the right answers (the random tests compare against it), but it was stopped after 5 seconds on the largest input (the answer above takes 0.037s).



---

## After these tasks

Every task here is a pattern that comes back in other clothes: the heap in task 1 schedules meeting rooms, the
union-find in task 3 finds duplicate accounts that share an email or a phone, the dynamic programming in task 5 picks
projects within a budget. When a new task looks hard, ask which of these ten it is. Then try the
[full mocks](full-mock-a.md) in the real format.
