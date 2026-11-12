# 8. Back pressure, retries and partitions

*A NiFi flow pulls files from a server, transforms them and sends them on. One step is slower than the others, a database sometimes refuses a write, and the flow runs on three machines that must share the work. NiFi handles each with a small rule: a queue that says "full" at 10,000 FlowFiles or 1 GB, a wait that doubles after each failure, and a hash that sends every FlowFile with the same key to the same machine. This tutorial works each rule by hand from NiFi's source code and checks it with a program.*

!!! abstract "In this tutorial"
    **You will learn:**

    - when a connection's queue counts as full, and which of its two limits trips first for a given FlowFile size
    - how back pressure turns a fast source and a slow step into one steady flow, how long the queue takes to fill, and how long a FlowFile then waits (Little's law)
    - NiFi's retry back-off `min(max, 2^r × base)`, and how long ten retries take with the default settings
    - Java's `String.hashCode`, worked by hand
    - jump consistent hashing, the rule behind "partition by attribute": why it spreads keys evenly, and why adding a fourth machine moves only a quarter of the keys, all to the new machine

    **You need:** powers of 2, division, and remainders. The queue arithmetic is the same as in [Kafka 8. The log, offsets and lag](../kafka/08-Log-Offsets-and-Lag.md).

    **How to learn from it:** read 8.1 to 8.3, close the page, redo the examples of 8.3 on paper, then try the exercises in 8.7 before opening any answer. Plan about two hours.

**About the examples.** No NiFi was run for this tutorial. The rules were read from Apache NiFi's source code (the `main` branch, November 2026) and ported to Python: `AbstractFlowFileQueue.isFull`, `NiFiProperties` (the default thresholds), `ProcessorNode` (the default retry settings), `StandardProcessSession.calculateBackoffTime` and `CorrelationAttributePartitioner`. The partitioner port reproduces NiFi's own unit test and every test value of Google Guava's `consistentHash`, which it is copied from. The queue is a **simulation** in steps of one second, a model of the scheduler and not the scheduler itself. The scripts and their full output: [nifi_math.py](src/08/nifi_math.py) (the ported rules), [ex01_partition.py](src/08/ex01_partition.py) ([output](src/08/ex01.out.txt)), [ex02_backpressure.py](src/08/ex02_backpressure.py) ([output](src/08/ex02.out.txt)), [ex03_backoff.py](src/08/ex03_backoff.py) ([output](src/08/ex03.out.txt)) and [ex04_grow.py](src/08/ex04_grow.py) ([output](src/08/ex04.out.txt)).

## 8.1 The question

1. A connection holds FlowFiles of 500 KB each. How many fit before NiFi calls it full?
2. A source makes 300 FlowFiles a second and the next step handles 200. What happens to the queue between them, and how long does a FlowFile wait?
3. A write to a database fails and is retried with the default settings. How long until NiFi gives up?
4. Three NiFi machines share the work, and all FlowFiles of one customer must go to the same machine. Which machine gets customer `"1"`? When a fourth machine joins, how many customers move?

## 8.2 The idea: limits, waits and hashes

In NiFi, data moves as **FlowFiles** (a piece of content plus attributes) through **processors**, joined by **connections**. Each connection is a queue. Three rules keep a flow healthy:

- **Back pressure.** Each connection has two thresholds, a number of FlowFiles and a data size. By default (`nifi.properties`) they are **10,000** FlowFiles and **1 GB**. When the queue reaches either one, NiFi stops scheduling the processor that feeds it, until the queue drops below again.
- **Retry with back-off.** A relationship such as `failure` can be marked to **retry**: the FlowFile is put back and tried again, up to 10 times by default, waiting longer after each failure.
- **Partition by attribute.** A connection in a cluster can be **load-balanced**. With the strategy "partition by attribute", every FlowFile with the same value of an attribute goes to the same machine, chosen by a hash of that value.

Each of these turns into one line of arithmetic.

## 8.3 The math by hand

### Step 1. When is a queue full?

NiFi's rule, from `AbstractFlowFileQueue.isFull`:

```text
full  ⟺  count ≥ 10,000   or   bytes ≥ 1 GB
```

NiFi's units are powers of 1024, so 1 GB = `1024³ = 1,073,741,824` bytes. The two limits meet when each FlowFile is `1,073,741,824 / 10,000 ≈ 107,374` bytes, about 105 KB. Smaller FlowFiles hit the count first; larger ones hit the size first.

For FlowFiles of 500,000 bytes: `1,073,741,824 / 500,000 = 2,147.5`. After 2,147 FlowFiles the queue holds 1,073,500,000 bytes, still under; the 2,148th takes it to 1,074,000,000, over. So the queue is full at **2,148** FlowFiles, far below 10,000. `ex02` agrees.

### Step 2. Back pressure and the waiting time

A source makes 300 FlowFiles a second; the next processor handles 200. The queue between them grows by `300 − 200 = 100` a second, so it reaches 10,000 after about `10,000 / 100 = 100` seconds.

Then back pressure starts. Whenever the queue is full, the source is not scheduled; when the processor has taken some away, the source runs again. From then on the source can only add what the processor removes, so the whole flow runs at **200 a second**: the speed of its slowest step. Nothing is lost and no memory runs out; the queue just stays near 10,000.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 210" role="img" aria-label="The number of FlowFiles in the queue over 200 seconds. It rises in a straight line from 0 to 10,000 in about 100 seconds, then stays at the 10,000 threshold, moving between 9,800 and 10,200, while the source is switched off and on.">
<g font-size="12" fill="currentColor">
<g stroke="currentColor" fill="none">
<line x1="60" y1="170" x2="600" y2="170"/><line x1="60" y1="170" x2="60" y2="20"/>
<line x1="60" y1="30" x2="600" y2="30" stroke-dasharray="4 4" opacity="0.6"/>
<polyline stroke-width="2.5" points="60,170 322,34 330,30 600,31"/>
</g>
<text x="8" y="34">10,000</text><text x="44" y="174">0</text>
<text x="56" y="188">0</text><text x="322" y="188">100</text><text x="590" y="188">200</text>
<text x="350" y="24">back-pressure threshold</text>
<text x="200" y="150">filling at 300 − 200 = 100 a second</text>
<text x="390" y="54">full: the flow runs at 200 a second</text>
<text x="290" y="204">seconds</text>
</g>
</svg>
<figcaption>Figure 8.1. The queue between a source of 300 a second and a processor of 200 a second (<code>ex02</code>). It fills in about 100 seconds, then back pressure holds it near 10,000, between 9,800 and 10,200.</figcaption>
</figure>

How long does a FlowFile wait in the full queue? **Little's law** says that, on average, the number waiting equals the arrival rate times the waiting time: `L = λ × W`. Here `L = 10,000` and `λ = 200` a second, so

```text
W = L / λ = 10,000 / 200 = 50 seconds
```

The simulation measures 49.5 seconds for the last 20,000 FlowFiles. The 10,000 threshold is a waiting room of 50 seconds at this speed; a larger threshold would only make the wait longer, not the flow faster.

The limit is checked **before** the source runs, not during, so one run can take the queue past it. In the simulation the source adds 300 at a time, and the queue reaches 10,200. Back pressure is a soft limit.

### Step 3. Retry and back-off

When a FlowFile is routed to a relationship marked for retry, NiFi rolls it back and adds 1 to its retry count `r` (stored as an attribute). Before the next try it waits

```text
wait = min(max back-off, 2^r × base)
```

where `r` is the number of retries so far, the maximum is 10 minutes, and the base is the processor's **penalty duration**, 30 seconds by default (or its **yield duration**, 1 second, if back-off is set to yield the processor instead). It retries while `r < 10`, the default number of attempts.

With the defaults the waits are 30, 60, 120, 240 and 480 seconds, then `2^5 × 30 = 960` is capped at 600 for the remaining five:

```text
30 + 60 + 120 + 240 + 480 + 5 × 600 = 930 + 3,000 = 3,930 seconds ≈ 65.5 minutes
```

So a FlowFile that keeps failing is retried for over an hour before it goes to `failure`. With the yield setting the waits are `1, 2, 4, …, 512` seconds, which add up to `2^10 − 1 = 1,023` seconds, about 17 minutes. Doubling means a short outage is retried quickly, and a long one is not hammered: after an hour the processor tries only once every 10 minutes.

### Step 4. Java's String.hashCode

Partition by attribute starts from Java's `hashCode` of the attribute's value. For a string `s` of `n` characters:

```text
hashCode(s) = s[0] × 31^(n−1) + s[1] × 31^(n−2) + … + s[n−1]      (kept to 32 bits)
```

where each character counts as its code number. For a one-character string it is just the code: `"1"` is 49, `"2"` is 50, `"4"` is 52. For `"ab"`: `97 × 31 + 98 = 3,105`. For `"east"`: `((101 × 31 + 97) × 31 + 115) × 31 + 116 = 3,105,789`. A missing attribute counts as 0.

Different strings can share a hash: `"Aa" = 65 × 31 + 97 = 2,112` and `"BB" = 66 × 31 + 66 = 2,112`. They will always land on the same machine.

### Step 5. Jump consistent hashing

To turn the hash into one of `n` machines, NiFi does not take `hash mod n`. It uses **jump consistent hashing** (Lamping and Veach, 2014), copied from Google Guava's `consistentHash`:

```text
candidate = 0
repeat:
    draw r in (0, 1] from a random-number generator seeded with the hash
    next = floor((candidate + 1) / r)
    if next < n:  candidate = next      (jump forward)
    else:         return candidate
```

The generator is a fixed formula, so the same hash always draws the same numbers and lands on the same machine. For `"1"` (hash 49) and three machines, `ex01` prints the draws:

```text
candidate 0: r = 0.604797, (candidate + 1) / r = 1.653 -> 1  (below 3: jump)
candidate 1: r = 0.526906, (candidate + 1) / r = 3.796 -> 3  (3 or more: stop at 1)
```

So customer `"1"` goes to machine 1 (counting from 0). With four machines, the jump to 3 is allowed, so the same customer moves to the new machine 3, and stays there for 5, 6 or 10 machines. NiFi's own unit test checks `"4"`, `"1"` and `"2"` on three machines and expects 0, 1 and 2; the port gives the same.

Now the key property. When a fourth machine joins, a key moves only if one of its jumps lands on 3, the new machine; otherwise all its draws and jumps are the same as before. `ex01` puts 30,000 customer ids on 3 machines and then 4:

```text
on 3 nodes: [9990, 9994, 10016]
on 4 nodes: [7500, 7492, 7495, 7513]
jump hash: 7,513 keys moved (25.0%), every one of them to the new node: True
plain hash mod n, for comparison: 22,501 keys moved (75.0%)
```

A quarter of the keys move, exactly the quarter the new machine should take, and nothing moves between the old machines. With `hash mod n`, three quarters would move.

## 8.4 Why it is true

**The threshold is an "or".** Either limit makes the queue full, so the one reached first decides. The count is reached first exactly when `10,000 × size < 1 GB`, that is when FlowFiles average under about 105 KB.

**The flow runs at its slowest step.** In the long run, what enters a queue must leave it or the queue grows; back pressure stops it growing past the threshold, so what enters equals what leaves, which is the slow step's rate. Every step before it is slowed to the same rate by its own full queue in turn.

**Little's law** holds for any queue that is stable over time, whatever the order of service: count FlowFile-seconds of waiting in two ways, as the sum over FlowFiles of their waits (`λ × W` per second) or as the sum over seconds of the number waiting (`L` per second). Both count the same thing.

**The doubling sum.** `1 + 2 + 4 + … + 2^(k−1) = 2^k − 1`, because adding 1 to the left side doubles the last term again and again. So ten doublings from 1 second add up to 1,023 seconds, and from 30 seconds they would be `30 × 1,023 = 30,690` seconds without the 10-minute cap.

**Jump hashing moves `1/n` of the keys.** Compare `n − 1` machines with `n`. A key that ends on candidate `c` with `n − 1` machines stopped because its next jump, `floor((c + 1) / r)`, was `n − 1` or more, which has probability `(c + 1) / (n − 1)`. With `n` machines it ends differently only if that jump is exactly `n − 1`, that is below `n`, which has probability `(c + 1) / (n − 1) − (c + 1) / n`. Divide one by the other: the chance of moving is `1 − (n − 1) / n = 1/n`, whatever `c` was. A key that jumps to `n − 1` stops there, because the next jump `floor(n / r)` is at least `n`. So `1/n` of the keys move, all to the new machine, and each old machine loses the same share; starting from one machine, every machine ends with `1/n` of the keys. `ex04` measures 50.0%, 33.3%, 25.0%, 20.1% and 16.6% for 2 to 6 machines.

**Mod n moves most keys.** A key stays when `h mod 3 = h mod 4`, which for evenly spread hashes happens for 3 of every 12 values (`h mod 12` = 0, 1, 2), a quarter; so three quarters move.

## 8.5 See it in code

`ex01` checks the port against Guava's own test values and NiFi's unit test:

```text
inputs 0..19, 100 buckets: [0, 55, 62, 8, 45, 59, 86, 97, 82, 59, 73, 37, 17, 56, 86, 21, 90, 37, 38, 83] ok
consistentHash(2, 100001) = 80343  Guava test 80343  ok
'1': hashCode = 49 (the character code), partition 1  NiFi test expects 1
```

`ex02` finds which limit trips first and runs the queue of step 2:

```text
FlowFiles of   500,000 bytes: full at  2,148 FlowFiles (size threshold)
throughput once throttled: 200/s; wait of the last 20,000 FlowFiles: about 49.5 s
```

`ex03` prints the two back-off tables of step 3, ending `all 10 retries: 3,930 s = 65.5 min`.

## 8.6 Where it breaks

- **Back pressure is soft.** The check comes before a processor runs, so one run can pass the threshold (step 2). A processor that writes many FlowFiles in one run, such as one that splits a file, can pass it by a lot.
- **Thresholds are per connection.** A long flow with ten connections can hold ten times 10,000 FlowFiles, and its total waiting time is the sum of the waits.
- **A slow step stays slow.** Back pressure protects the machine; it does not make the slow step faster. Only more threads, more machines or less work per FlowFile do that.
- **Retry needs an idempotent target.** A write that failed halfway may be done twice. Whether that is safe depends on the system written to, not on NiFi.
- **Yield stops everything.** With "yield", the whole processor waits, not just the failing FlowFile; one bad FlowFile delays all the good ones behind it.
- **Hot keys.** Partition by attribute keeps a key on one machine. If one customer has half the data, one machine gets half the work, the same skew as in [Spark 8](../spark/08-Shuffles-and-Skew.md). Strings with equal hashes (`"Aa"`, `"BB"`) always share a machine.
- **Removing a machine.** Jump hashing moves the fewest keys when the last machine is added or removed. If a machine in the middle leaves, more keys move; how NiFi orders the machines' partitions when that happens was not checked here.

## 8.7 Exercises

Do 1 to 6 with a pencil. 7 needs a little care. 8 is code.

**E1. A connection keeps the defaults. FlowFiles are 1 MB (1,048,576 bytes) each. At how many FlowFiles is the queue full?**

??? success "Answer"
    `1,073,741,824 / 1,048,576 = 1,024` exactly. At 1,024 FlowFiles the bytes equal 1 GB, and the rule is "≥", so the queue is full at 1,024.

**E2. FlowFiles of 50 KB (51,200 bytes): which threshold trips first?**

??? success "Answer"
    The count: `10,000 × 51,200 = 512,000,000` bytes is under 1 GB. Under about 105 KB, the count always trips first.

**E3. A source makes 1,000 FlowFiles a minute, the next step handles 600 a minute, and the threshold is 10,000. When is the queue full, and how long do FlowFiles then wait?**

??? success "Answer"
    It grows by 400 a minute, so it is full after `10,000 / 400 = 25` minutes. Then the flow runs at 600 a minute and `W = 10,000 / 600 ≈ 16.7` minutes.

**E4. A processor's penalty duration is 10 seconds, the maximum back-off 2 minutes, and the retry count 5. List the waits and their total.**

??? success "Answer"
    `min(120, 2^r × 10)` for `r = 0…4`: 10, 20, 40, 80, 120 (160 capped). Total 270 seconds, 4.5 minutes.

**E5. Compute Java's hashCode of `"abc"` and of `"Ab"` and `"BC"`.**

??? success "Answer"
    `"abc"`: `(97 × 31 + 98) × 31 + 99 = 3,105 × 31 + 99 = 96,354`. `"Ab"`: `65 × 31 + 98 = 2,113`. `"BC"`: `66 × 31 + 67 = 2,113`, the same.

**E6. A cluster grows from 4 to 5 machines. With jump hashing, what fraction of keys moves, and where? With `hash mod n`?**

??? success "Answer"
    Jump hashing: `1/5 = 20%`, all to the new machine (`ex04` measures 20.1%). Mod n: a key stays when `h mod 4 = h mod 5`, which is 4 of every 20 values of `h mod 20` (0 to 3), so 80% move.

**E7. Why does a bigger back-pressure threshold not make a flow faster? What does it change?**

??? success "Answer"
    Once the queue is full, the flow runs at the slowest step's rate, whatever the threshold. A bigger threshold only makes the queue, and so the wait `W = L / λ`, longer (and uses more disk). It can help a little with short bursts, by letting the source keep running while the slow step catches up.

**E8. (Code.) Grow a cluster from 1 to 6 machines and print, at each step, the fraction of keys that move and whether they all go to the new machine.**

??? success "Answer"
    ```python
    from nifi_math import partition_for

    keys = [f"order-{i}" for i in range(60_000)]
    prev = [partition_for(k, 1) for k in keys]
    for n in range(2, 7):
        cur = [partition_for(k, n) for k in keys]
        moved = [(a, b) for a, b in zip(prev, cur) if a != b]
        print(n, len(moved) / len(keys), all(b == n - 1 for a, b in moved))
        prev = cur
    ```
    The fractions are 50.0%, 33.3%, 25.0%, 20.1% and 16.6%, and every moved key goes to the new machine. ([ex04_grow.py](src/08/ex04_grow.py), [output](src/08/ex04.out.txt).)

## 8.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a queue that filled up, a retry storm or a hot key in a NiFi flow, and which step explained it.)*

## 8.9 Further reading

On your own sites:

- [Kafka 8. The log, offsets and lag](../kafka/08-Log-Offsets-and-Lag.md): Little's law and lag, and hashing keys to partitions
- [Spark 8. Shuffles and skew](../spark/08-Shuffles-and-Skew.md): what a hot key does to one machine

Original sources:

- Apache NiFi, source code on GitHub: `AbstractFlowFileQueue.java`, `NiFiProperties.java`, `ProcessorNode.java`, `StandardProcessSession.java`, `CorrelationAttributePartitioner.java` and its test.
- Apache NiFi, *User Guide* (back pressure, prioritization, retry, load balancing) and *Administration Guide* (`nifi.queue.backpressure.count` and `.size`).
- J. Lamping and E. Veach, "A Fast, Minimal Memory, Consistent Hash Algorithm", 2014.
- Google Guava, `Hashing.consistentHash` and `HashingTest`.
- J. D. C. Little, "A proof for the queuing formula: L = λW", *Operations Research* 9(3), 1961.

## Glossary

- **FlowFile**: one piece of data in NiFi, content plus attributes.
- **Connection**: the queue between two processors.
- **Back pressure**: not scheduling a processor while its outgoing queue is full.
- **Object and size thresholds**: the count (default 10,000) and data size (default 1 GB) at which a queue is full.
- **Little's law**: `L = λW`, number waiting = arrival rate × wait.
- **Penalty, yield**: a FlowFile set aside for a time, or a processor paused for a time.
- **Back-off**: waiting longer after each failure, here doubling up to a maximum.
- **Load balancing**: spreading a connection's FlowFiles over the machines of a cluster.
- **Jump consistent hashing**: choosing one of `n` buckets so that going to `n + 1` moves only `1/(n + 1)` of the keys, all to the new bucket.
