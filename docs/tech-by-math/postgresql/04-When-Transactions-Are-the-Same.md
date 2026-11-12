# 4. When are two transactions "the same": serializability graphs

*Two people book the last seat on a flight at the same moment, and both bookings succeed. Nobody's code has a bug that shows when it runs alone; the bug is in how the two runs interleave. This tutorial gives the precise meaning of "the database ran them safely", which is that the result is the same as running them one at a time, and a test for it that you can do with a pencil: draw one arrow per conflict and look for a cycle. It proves the test, uses it to explain lost updates, write skew and the double-booked seat, and then shows each of them on PostgreSQL 16, at each isolation level, with the real two-session timelines.*

!!! abstract "In this tutorial"
    **You will learn:**

    - how to write a concurrent run as a **schedule** of reads and writes
    - which pairs of steps **conflict**, and why swapping two steps that do not conflict changes nothing
    - the **precedence graph**, and the theorem: a schedule is conflict-serializable exactly when its graph has no cycle, with the proof
    - why snapshot isolation (PostgreSQL's REPEATABLE READ) allows write skew, and how SERIALIZABLE catches it
    - three ways to fix the last seat, and the retry loop that SERIALIZABLE requires

    **You need:** what a transaction is (`BEGIN` ... `COMMIT`) and what a directed graph is. The SQL side is [SQL ch 20. Transactions and isolation](../../databases/sql/20-Transactions-and-Isolation.md); graphs and topological order are in [Algorithms, ch 15](https://cs.akadian.ca/books/algorithms/15-Graphs-and-Graph-Search/).

    **How to learn from it:** read 4.1 to 4.3, close the page, redraw the graphs of the four schedules in 4.3 on paper, then try the exercises in 4.7 before opening any answer. Plan about three hours.

**About the examples.** The two-session timelines were run by the IT site's tool `tools/txdemo.py`, which opens two connections to PostgreSQL 16 and runs the steps in the order shown; the result column is what really came back. The graph computations are checked by [ex01_precedence.py](src/04/ex01_precedence.py) ([output](src/04/ex01.out.txt)).

## 4.1 The question

A flight has 2 seats, and Cai has booked one. The booking program does the obvious thing:

```sql
BEGIN;
SELECT COUNT(*) FROM bookings WHERE flight_id = 1;   -- 1 booked, 2 seats: there is room
INSERT INTO bookings VALUES (1, 'Ana');
COMMIT;
```

Ana and Ben run it at the same moment. Both see 1 booked, both insert, both commit. The flight now has **3 bookings for 2 seats**. On PostgreSQL this happens at the default isolation level (READ COMMITTED) and also at REPEATABLE READ (4.5 shows both). Each transaction, run alone, is correct. What exactly went wrong, and how can a database tell?

## 4.2 The idea: correct means "as if one at a time"

Running transactions one after the other is always safe if each is correct alone. Running them truly one at a time is too slow, so a database interleaves their steps. The standard definition of "safe" is:

> A concurrent run is **serializable** if its result is the same as the result of running the same transactions one at a time, in **some** order.

Any order will do. If Ana's transaction ran entirely before Ben's, Ben would have seen 2 booked and stopped; the other way round, Ana would have stopped. Either way, 2 bookings. The real run gave 3, which matches **neither** order. That is the bug, stated precisely.

To test a run without trying every order, look only at the steps that **conflict**: two steps of different transactions on the same data, at least one of them a write. Their order matters, so it fixes which transaction must come first in any equivalent one-at-a-time order. Draw that as an arrow. If the arrows go round in a circle, no order can satisfy them all.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 220" role="img" aria-label="Two circles, Ana and Ben. An arrow from Ana to Ben is labelled: Ana counted the bookings before Ben added one, so Ana must come first. An arrow from Ben to Ana is labelled: Ben counted the bookings before Ana added one, so Ben must come first. The two arrows make a cycle.">
<g fill="none" stroke="currentColor">
<circle cx="150" cy="110" r="42" stroke-width="2.5"/>
<circle cx="490" cy="110" r="42" stroke-width="2.5"/>
<path d="M 190 92 C 270 40, 370 40, 450 92" stroke-width="2.5"/>
<path d="M 450 128 C 370 180, 270 180, 190 128" stroke-width="2.5"/>
<path d="M 450 92 l -14 -2 m 14 2 l -6 -12" stroke-width="2.5"/>
<path d="M 190 128 l 14 2 m -14 -2 l 6 12" stroke-width="2.5"/>
</g>
<g font-size="13" fill="currentColor" text-anchor="middle">
<text x="150" y="115" font-weight="bold" font-size="15">Ana</text>
<text x="490" y="115" font-weight="bold" font-size="15">Ben</text>
<text x="320" y="28">Ana counted before Ben inserted:</text>
<text x="320" y="46" font-weight="bold">Ana must come first</text>
<text x="320" y="190">Ben counted before Ana inserted:</text>
<text x="320" y="208" font-weight="bold">Ben must come first</text>
</g>
</svg>
<figcaption>Figure 4.1. The precedence graph of the double booking. Each arrow says "this one must come first in any equivalent one-at-a-time order". Together they say both must come first: a cycle, so no such order exists.</figcaption>
</figure>

## 4.3 The math by hand

### Step 1. Write the run as a schedule

Keep only reads and writes of data items. **r1(a)** means "transaction 1 reads item a", **w2(a)** means "transaction 2 writes item a". A **schedule** is the sequence of all steps of all transactions, in the order they happened. Each transaction's own steps stay in its own order.

### Step 2. Which pairs conflict

Two steps **conflict** when they belong to different transactions, touch the same item, and at least one is a write:

| Pair on the same item | Conflict? | Why the order matters |
| --- | --- | --- |
| r1(a), r2(a) | no | two reads see the same value either way |
| r1(a), w2(a) | yes | T1 sees the old value or the new one |
| w1(a), r2(a) | yes | T2 sees T1's value or the one before |
| w1(a), w2(a) | yes | the last write is what stays |

Steps on **different** items never conflict. Two neighbouring steps that do not conflict can be swapped and nothing changes: every read returns the same value and the final data is the same. Two schedules are **conflict-equivalent** if one can be turned into the other by such swaps; equivalently, they order every conflicting pair the same way.

### Step 3. A schedule that is serializable

```text
S2 = r1(a) w1(a) r2(a) w2(a) r1(b) w1(b) r2(b) w2(b)
```

T1 updates a, then T2 updates a, then T1 updates b, then T2 updates b. Swap step by step: `r1(b) w1(b)` touch only b, and `r2(a) w2(a)` touch only a, so they never conflict; slide `r1(b) w1(b)` left past `r2(a) w2(a)`:

```text
r1(a) w1(a) r1(b) w1(b) r2(a) w2(a) r2(b) w2(b)   =   all of T1, then all of T2
```

A serial schedule, reached by legal swaps: S2 is **conflict-serializable**, equivalent to T1 then T2. The graph agrees: every conflicting pair (r1(a)/w2(a), w1(a)/r2(a), w1(a)/w2(a), and the same three on b) has T1's step first, so there is one arrow, **T1 → T2**, and no cycle.

### Step 4. The lost update

Both transactions add to a balance by reading it and writing back a new value:

```text
S1 = r1(a) r2(a) w1(a) w2(a)
```

Conflicting pairs: r1(a) before w2(a) gives **T1 → T2**. r2(a) before w1(a) gives **T2 → T1**. (And w1(a) before w2(a), T1 → T2 again.) Two arrows in opposite directions: a **cycle**. Not serializable. In words: T2's write is based on a value read before T1's write, so T1's deposit is overwritten and lost.

### Step 5. The last seat

The count reads the **set** of bookings of flight 1; call it P. Inserting a booking for flight 1 writes P (it changes what that count returns). So:

```text
S3 = r1(P) r2(P) w1(P) w2(P)
```

The same shape as the lost update: r1(P) before w2(P) gives T1 → T2, r2(P) before w1(P) gives T2 → T1. Cycle: Figure 4.1. The difference from the lost update is that the two writes are **different new rows**. No row is written by both, which is why row-level protections miss it (4.5).

### Step 6. Write skew: the doctors on call

A hospital rule: at least one of Kim and Lee is on call. Each, while both are on call, checks that the other is on call and goes off call:

```text
S4 = r1(k) r1(l) r2(k) r2(l) w1(k) w2(l)
```

Conflicting pairs: r1(l) before w2(l), so **T1 → T2**; r2(k) before w1(k), so **T2 → T1**. A cycle again, and nobody is on call. Each transaction wrote a different item, so there is **no write–write conflict at all**: both arrows come from a read followed by another transaction's write. That kind of pair, read then overwrite, is called a **read–write antidependency**, and it is the shape behind both the last seat and write skew.

## 4.4 Why it is true

**Theorem.** A schedule is conflict-serializable if and only if its precedence graph has no cycle. (The graph: one node per transaction; an arrow Ti → Tj whenever a step of Ti conflicts with a later step of Tj.)

**Proof, "only if".** Suppose the schedule is conflict-equivalent to a serial schedule in which the transactions run in some order. Conflict-equivalent schedules order every conflicting pair the same way. So for every arrow Ti → Tj, Ti's step comes before Tj's step in the serial schedule too, and in a serial schedule that means all of Ti comes before all of Tj. Every arrow therefore points forward in one fixed order of the transactions. Arrows that all point forward in a line cannot form a cycle.

**Proof, "if".** Suppose the graph has no cycle. Then it has a **topological order**, a list of all the transactions in which every arrow points forward. (Why one exists: a finite graph with no cycle has a node with no incoming arrow, since otherwise you could walk backwards along incoming arrows forever and, with finitely many nodes, would repeat one, which is a cycle. Put that node first, remove it, and repeat on the rest, which still has no cycle.) Let T be the serial schedule that runs the transactions in that order. For every conflicting pair, the schedule's order is the arrow's direction, which is also T's order. So the schedule and T order every conflicting pair the same way: they are conflict-equivalent, and the schedule is conflict-serializable. ∎

The proof also says how to find the order: the topological sort. For S2 it is T1 then T2. The script checks the theorem by brute force on a small case: every interleaving of three transactions of two steps each (T1 = r(x) w(y), T2 = r(y) w(z), T3 = r(z) w(x)), 6! / (2! 2! 2!) = **90** schedules. For each, it tests the graph for a cycle and, separately, tries all 3! = 6 serial orders for an equivalent one. The graph test and the brute force agree on **90 of 90**; 42 of the schedules are serializable.

### What the isolation levels do with this

- **Locks.** If every transaction locks what it reads (shared) and what it writes (exclusive) and keeps all its locks until it ends, the schedule is always conflict-serializable. This is **two-phase locking**, and the proof is that a conflicting pair can only happen in the order the locks were granted, which follows the order the transactions finish their locking. It is safe, but readers block writers.
- **Snapshot isolation**, which is PostgreSQL's REPEATABLE READ: each transaction reads from a snapshot of the data as of its start, and if two transactions write the **same row**, the second to commit fails. That rule blocks lost updates (two writes of item a). It does **not** block S3 and S4, where the two writes are different rows: the cycle is made only of read–write antidependencies. Fekete and colleagues (2005) proved that this is the only way snapshot isolation can go wrong: every non-serializable run under it has a cycle containing two read–write antidependencies in a row between transactions that overlapped in time.
- **Serializable snapshot isolation**, PostgreSQL's SERIALIZABLE since version 9.1: snapshot isolation plus tracking of read–write antidependencies. When it sees a transaction with one coming in and one going out (the "dangerous structure" of the theorem above), it aborts one of the transactions. It may abort some runs that were in fact serializable, because it looks for the structure, not for a whole cycle; it never lets a non-serializable one commit.

## 4.5 See it in the database

### READ COMMITTED: three bookings for two seats

<!-- txdemo seat-rc pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
| 2 |  | <code>BEGIN</code> | <code>BEGIN</code> |
| 3 | <code>SELECT COUNT(*) AS booked FROM bookings WHERE flight_id = 1</code> |  | booked = 1 |
| 4 |  | <code>SELECT COUNT(*) AS booked FROM bookings WHERE flight_id = 1</code> | booked = 1 |
| 5 | <code>INSERT INTO bookings VALUES (1, 'Ana')</code> |  | <code>INSERT 0 1</code> |
| 6 |  | <code>INSERT INTO bookings VALUES (1, 'Ben')</code> | <code>INSERT 0 1</code> |
| 7 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 8 |  | <code>COMMIT</code> | <code>COMMIT</code> |
| 9 | <code>SELECT COUNT(*) AS booked FROM bookings WHERE flight_id = 1</code> |  | booked = 3 |
<!-- /txdemo -->

### REPEATABLE READ: the same

<!-- txdemo seat-rr pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN ISOLATION LEVEL REPEATABLE READ</code> |  | <code>BEGIN</code> |
| 2 |  | <code>BEGIN ISOLATION LEVEL REPEATABLE READ</code> | <code>BEGIN</code> |
| 3 | <code>SELECT COUNT(*) AS booked FROM bookings WHERE flight_id = 1</code> |  | booked = 1 |
| 4 |  | <code>SELECT COUNT(*) AS booked FROM bookings WHERE flight_id = 1</code> | booked = 1 |
| 5 | <code>INSERT INTO bookings VALUES (1, 'Ana')</code> |  | <code>INSERT 0 1</code> |
| 6 |  | <code>INSERT INTO bookings VALUES (1, 'Ben')</code> | <code>INSERT 0 1</code> |
| 7 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 8 |  | <code>COMMIT</code> | <code>COMMIT</code> |
| 9 | <code>SELECT COUNT(*) AS booked FROM bookings WHERE flight_id = 1</code> |  | booked = 3 |
<!-- /txdemo -->

The two inserts are different rows, so snapshot isolation's rule (the second writer of the **same** row fails) never fires. Compare the lost update in [SQL ch 20](../../databases/sql/20-Transactions-and-Isolation.md#lost-update), where REPEATABLE READ does stop the second write, because there both transactions write the same row.

### SERIALIZABLE: the second commit is refused

<!-- txdemo seat-serializable pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN ISOLATION LEVEL SERIALIZABLE</code> |  | <code>BEGIN</code> |
| 2 |  | <code>BEGIN ISOLATION LEVEL SERIALIZABLE</code> | <code>BEGIN</code> |
| 3 | <code>SELECT COUNT(*) AS booked FROM bookings WHERE flight_id = 1</code> |  | booked = 1 |
| 4 |  | <code>SELECT COUNT(*) AS booked FROM bookings WHERE flight_id = 1</code> | booked = 1 |
| 5 | <code>INSERT INTO bookings VALUES (1, 'Ana')</code> |  | <code>INSERT 0 1</code> |
| 6 |  | <code>INSERT INTO bookings VALUES (1, 'Ben')</code> | <code>INSERT 0 1</code> |
| 7 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 8 |  | <code>COMMIT</code> | **error:** <code>could not serialize access due to read/write dependencies among transactions</code> |
| 9 | <code>SELECT COUNT(*) AS booked FROM bookings WHERE flight_id = 1</code> |  | booked = 2 |
<!-- /txdemo -->

PostgreSQL saw the two read–write antidependencies of Figure 4.1 and refused Ben's commit with error code 40001 (`serialization_failure`). Ben's insert is rolled back: 2 bookings. The program must now **retry** Ben's whole transaction, which this time sees 2 booked and stops. Exercise E7 does this in Python.

### A fix without SERIALIZABLE: make the conflict a row conflict

Keep a counter of free seats on the flight row, with a `CHECK (seats_left >= 0)` constraint, and take a seat by updating it:

<!-- txdemo seat-counter pg -->
<p class="sql-tested">Run by <code>tools/txdemo.py</code> on PostgreSQL 16, two connections, in this order.</p>

| # | Session A | Session B | Result |
| --- | --- | --- | --- |
| 1 | <code>BEGIN</code> |  | <code>BEGIN</code> |
| 2 |  | <code>BEGIN</code> | <code>BEGIN</code> |
| 3 | <code>UPDATE flights SET seats_left = seats_left - 1 WHERE id = 1</code> |  | <code>UPDATE 1</code> |
| 4 |  | <code>UPDATE flights SET seats_left = seats_left - 1 WHERE id = 1</code> | *waits: the row is locked by the other session* |
| 5 | <code>INSERT INTO bookings VALUES (1, 'Ana')</code> |  | <code>INSERT 0 1</code> |
| 6 | <code>COMMIT</code> |  | <code>COMMIT</code> |
| 7 |  | *(its waiting statement finishes)* | **error:** <code>new row for relation "flights" violates check constraint "flights_seats_left_check"</code> |
| 8 |  | <code>ROLLBACK</code> | <code>ROLLBACK</code> |
| 9 | <code>SELECT COUNT(*) AS booked FROM bookings WHERE flight_id = 1</code> |  | booked = 2 |
<!-- /txdemo -->

Both transactions now **write the same row**. Ben's update waits for Ana's lock; when Ana commits, Ben's update runs on the new value, 0, would make it −1, and the constraint stops it. The invariant "no more bookings than seats" is now enforced by the database, at READ COMMITTED.

## 4.6 Where it breaks

- **Conflict-serializability is stricter than needed.** Some schedules give a correct result but have a cycle, for example when a value is written and later overwritten without anyone reading it in between ("blind writes"). The broader notion, **view serializability**, accepts more, but testing it is NP-complete (Papadimitriou, 1979). Databases use the conflict version because it can be checked step by step.
- **Sets, not just rows.** S3 treats "the bookings of flight 1" as one item. A lock on existing rows does not cover a row that does not exist yet (a **phantom**). Real systems handle this with locks on ranges of an index or, in PostgreSQL's SERIALIZABLE, with predicate locks on what each query read.
- **Aborts are part of the contract.** SERIALIZABLE in PostgreSQL turns anomalies into errors. Every transaction that runs at that level must be ready to be retried from the start, whole: the program, not the database, re-runs the reads and decisions. A retry can fail again if another transaction is still running (E7's run shows one transaction needing three tries).
- **False alarms.** SSI looks for the two-antidependency structure, not for the full cycle, so it aborts some serializable runs; queries that read a whole table take coarser predicate locks and cause more of these. The PostgreSQL documentation lists ways to reduce them, such as declaring transactions `READ ONLY` when they are.
- **Serializable says nothing about real time.** "Equivalent to some serial order" allows an order in which a transaction that started later counts as earlier. Systems spread over several machines need a stronger promise (*strict* serializability, or *linearizability* for single items), which belongs to the distributed-systems tutorials of a later phase.
- **The invariant has to be in the data.** Every fix above works because the rule "no more bookings than seats" became something the database could see conflict on: a row, a constraint, a predicate. A rule that lives only in the program's `if` statement is invisible to the database at every level below SERIALIZABLE.

## 4.7 Exercises

1 to 4 with a pencil. 5 and 6 are short arguments. 7 is code.

**E1. Draw the precedence graph and decide: serializable or not? If yes, give the serial order.**
(a) `r1(x) w2(x) r3(x) w1(y) r2(y)`
(b) `r1(x) r2(y) w3(x) w2(x) r1(z) w3(z)`
(c) `w1(x) r2(x) w2(y) r3(y) w3(z) r1(z)`

??? success "Answer"
    (a) r1(x) before w2(x): T1 → T2; w2(x) before r3(x): T2 → T3; w1(y) before r2(y): T1 → T2. No cycle: **T1, T2, T3**.
    (b) r1(x) before w3(x): T1 → T3; r1(x) before w2(x): T1 → T2; w3(x) before w2(x): T3 → T2; r1(z) before w3(z): T1 → T3. No cycle: **T1, T3, T2**.
    (c) T1 → T2 (x), T2 → T3 (y), T3 → T1 (z): a **cycle** of three, not serializable.
    All three checked by [ex01_precedence.py](src/04/ex01_precedence.py) ([output](src/04/ex01.out.txt)).

**E2. Turn S2 into "all of T1, then all of T2" by swapping neighbours one pair at a time, naming each swap. Why is each swap allowed?**

??? success "Answer"
    S2 = r1(a) w1(a) r2(a) w2(a) r1(b) w1(b) r2(b) w2(b). Swap w2(a) and r1(b): different items. Then r2(a) and r1(b): different items. Now r1(a) w1(a) r1(b) r2(a) w2(a) w1(b) ...; swap w2(a) and w1(b): different items; then r2(a) and w1(b): different items. Result: r1(a) w1(a) r1(b) w1(b) r2(a) w2(a) r2(b) w2(b). Four swaps, each of two steps on different items, which never conflict, so each leaves every read and the final data unchanged.

**E3. Three transactions of two steps each. How many serial orders are there, and how many interleavings? In the script's example, how many interleavings are serializable?**

??? success "Answer"
    Serial orders: 3! = 6. Interleavings: 6 steps, each transaction's two in its own order: 6! / (2! × 2! × 2!) = 720 / 8 = **90**. The script found **42** of them serializable, and its graph test agreed with brute force on all 90.

**E4. In the doctors' schedule S4, which kinds of conflict make the two arrows? Why does REPEATABLE READ let both transactions commit, while it stops the lost update S1?**

??? success "Answer"
    Both arrows are read–write antidependencies: r1(l) then w2(l), and r2(k) then w1(k). Snapshot isolation only refuses a commit when two concurrent transactions **write the same item**. In S1 both write a, so the second fails. In S4 one writes k and the other l: no shared write, so both commit, and the cycle is made entirely of read-then-overwrite pairs, exactly the case Fekete's theorem describes.

**E5. Give two more fixes for the last seat, apart from the seat counter of 4.5 and SERIALIZABLE, and say which conflict each one creates.**

??? success "Answer"
    (1) `SELECT ... FROM flights WHERE id = 1 FOR UPDATE` before counting: both transactions now lock the same flight row, so Ben waits for Ana and then counts 2 (a write–write style conflict on the flight row, created by the lock). (2) A `seats` table with one row per seat and a unique constraint on (flight_id, seat_no), booking a specific free seat: two bookings of the same seat collide on the unique index, and the second fails. Both turn the set-level conflict of S3 into a conflict on one row that every isolation level sees.

**E6. Show that a finite directed graph with no cycle has a node with no incoming arrow.**

??? success "Answer"
    Suppose every node has an incoming arrow. Start anywhere and step backwards along an incoming arrow, again and again. With n nodes, after n steps you have visited n + 1 nodes, so some node appears twice: the walk between its two visits, read forwards, is a cycle. That contradicts "no cycle", so some node has no incoming arrow.

**E7. Write the booking as a Python function that runs at SERIALIZABLE and retries when PostgreSQL raises a serialization failure. Run two bookings at once for the last seat.**

??? success "Answer"
    The core, from [ex02_retry.py](src/04/ex02_retry.py) (psycopg2; the full script also makes both threads read before either writes, so the conflict happens every run):

    ```python
    for attempt in range(1, 6):
        try:
            with con:  # one transaction: commits at the end of the block, rolls back on an error
                c = con.cursor()
                c.execute("SELECT seats FROM flights4 WHERE id = 1")
                seats, = c.fetchone()
                c.execute("SELECT count(*) FROM bookings4 WHERE flight_id = 1")
                booked, = c.fetchone()
                if booked >= seats:
                    return "full"
                c.execute("INSERT INTO bookings4 VALUES (1, %s)", (passenger,))
            return "booked"
        except psycopg2.errors.SerializationFailure:
            pass  # run the whole transaction again, reads included
    ```

    A real run ([output](src/04/ex02.out.txt)):

    ```text
    Ben, try 1: 40001 could not serialize access due to read/write dependencies among transactions; trying again
    Ana, try 1: booked (saw 1 of 2)
    Ben, try 2: 40001 could not serialize access due to read/write dependencies among transactions; trying again
    Ben, try 3: 2 of 2 booked, the flight is full
    bookings: ('Ana, Cai', 2)
    ```

    Which of Ana and Ben wins changes from run to run; the bookings are always 2. Note that the retry re-runs the **reads**: retrying only the insert would book the seat Ben no longer has.

## 4.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a double booking, a lost update or a broken rule between two jobs or two users, and how it was found.)*

## 4.9 Further reading

On your own sites:

- Directed graphs, cycles and topological order: [Algorithms, ch 15. Graphs and graph search](https://cs.akadian.ca/books/algorithms/15-Graphs-and-Graph-Search/)
- The SQL side: [20. Transactions and isolation](../../databases/sql/20-Transactions-and-Isolation.md), which shows the lost update and the doctors' write skew as timelines

Original sources:

- K. P. Eswaran, J. N. Gray, R. A. Lorie and I. L. Traiger, "The Notions of Consistency and Predicate Locks in a Database System", *Communications of the ACM* 19(11), 1976. Serializability, two-phase locking and phantoms.
- C. H. Papadimitriou, "The Serializability of Concurrent Database Updates", *Journal of the ACM* 26(4), 1979. Conflict and view serializability, and the hardness of testing the latter.
- P. A. Bernstein, V. Hadzilacos and N. Goodman, *Concurrency Control and Recovery in Database Systems*, Addison-Wesley, 1987. The textbook treatment of the theorem in 4.4.
- A. Fekete, D. Liarokapis, E. O'Neil, P. O'Neil and D. Shasha, "Making Snapshot Isolation Serializable", *ACM Transactions on Database Systems* 30(2), 2005.
- M. J. Cahill, U. Röhm and A. D. Fekete, "Serializable Isolation for Snapshot Databases", *Proceedings of ACM SIGMOD*, 2008; D. R. K. Ports and K. Grittner, "Serializable Snapshot Isolation in PostgreSQL", *Proceedings of the VLDB Endowment* 5(12), 2012.
- PostgreSQL 16 documentation: [Transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html).

## Glossary

- **Schedule**: the order in which the reads and writes of several transactions actually happened.
- **Serial schedule**: one transaction at a time, no interleaving.
- **Serializable**: giving the same result as some serial schedule.
- **Conflict**: two steps of different transactions on the same item, at least one a write.
- **Conflict-serializable**: turnable into a serial schedule by swapping neighbouring steps that do not conflict.
- **Precedence graph**: one node per transaction, an arrow Ti → Tj for each conflict where Ti's step came first.
- **Topological order**: a list of a graph's nodes in which every arrow points forward; exists exactly when there is no cycle.
- **Lost update**: two read-then-write transactions on the same item; one write overwrites the other.
- **Write skew**: two transactions read the same data, then write different items, together breaking a rule each checked.
- **Read–write antidependency**: a transaction reads an item that another, concurrent one then writes.
- **Phantom**: a row that did not exist when a query read a set, inserted by another transaction.
- **Two-phase locking**: take locks as needed, release none until the end; guarantees conflict-serializability.
- **Snapshot isolation**: each transaction reads a snapshot from its start; concurrent writes to the same row are refused. PostgreSQL's REPEATABLE READ.
- **Serializable snapshot isolation (SSI)**: snapshot isolation plus detection of dangerous antidependency structures. PostgreSQL's SERIALIZABLE.
