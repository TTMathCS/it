# 8. The log, offsets and lag

*After a two-hour outage, the billing service is 1.2 million messages behind on the `orders` topic. Producers keep writing 2,000 messages a second. Will it catch up, and when? Would more consumers help, and how many? Why is one partition four times busier than the others, and why does adding partitions scramble which customer goes where? Each question has a pencil-sized answer once Kafka is seen for what it is: a set of numbered, append-only lists. Every number below comes from a script next to this page.*

!!! abstract "In this tutorial"
    **You will learn:**

    - what an offset, the log-end offset, the committed offset and the lag are, and why lag is a subtraction
    - Kafka's exact rule for sending a keyed message to a partition, `toPositive(murmur2(key)) mod n`, and why it is not `abs`
    - the catch-up time `L / (μ − λ)`, and why it is infinite when `μ ≤ λ`
    - why a group can never read faster than its busiest consumer, and why 12 partitions read by 5 consumers is no faster than by 4
    - Little's law, `L = λ × W`, which turns a lag in messages into a delay in seconds, and why lag explodes as the consumer nears full use
    - what fraction of keys move when a topic grows from `a` to `b` partitions: `1 − min(a, b) / lcm(a, b)`

    **You need:** remainders, averages, and least common multiples. The Spark course's [8. Shuffles and skew](../spark/08-Shuffles-and-Skew.md) uses the same hashing idea, and its step 4 (balls into bins) is used again here.

    **How to learn from it:** read 8.1 to 8.3, close the page, redo the examples of 8.3 on paper, then try the exercises in 8.7 before opening any answer. Plan about two and a half hours.

**About the examples. No Kafka broker ran for this tutorial.** The numbers come from small Python programs. The key-to-partition rule is copied from Kafka 4.3.2's source (`Utils.murmur2`, `Utils.toPositive` and `BuiltInPartitioner.partitionForKey`) and checked against the six test values in Kafka's own `UtilsTest.testMurmur2`: all six agree. Lag, queues and consumer groups are **simulations** (a model of one partition and its consumer), clearly labelled as such. The scripts and their full output: [kmath.py](src/08/kmath.py) (the rule), [ex01_murmur2.py](src/08/ex01_murmur2.py) ([output](src/08/ex01.out.txt)), [ex02_spread.py](src/08/ex02_spread.py) ([output](src/08/ex02.out.txt)), [ex03_lag.py](src/08/ex03_lag.py) ([output](src/08/ex03.out.txt)) and [ex04_range.py](src/08/ex04_range.py) ([output](src/08/ex04.out.txt)), and the answer to exercise E7, [ex05_salt.py](src/08/ex05_salt.py).

## 8.1 The question

The `orders` topic has 12 partitions. The billing service reads it as a consumer group of 5 consumers. After an outage the dashboard shows a total lag of 1,200,000 messages. Producers write 2,000 messages per second; the group, now running again, reads 2,500 per second.

1. When will the group have caught up?
2. The team wants to add consumers. Which numbers of consumers make the group faster, and which change nothing?
3. One partition has four times the traffic of the others. Why, and can more consumers fix it?
4. Someone proposes growing the topic from 12 to 13 partitions. What happens to the customers' order of events?

## 8.2 The idea: a partition is a numbered list that only grows

A Kafka **topic** is split into **partitions**. Each partition is a **log**: a list of messages to which new messages are only ever appended at the end. Every message gets the next number in its partition, its **offset**: 0, 1, 2, … Offsets are never reused and never change.

Three numbers describe a partition and one consumer group reading it:

- the **log-end offset**: the offset the next message will get (so the number of messages ever written, if nothing was deleted);
- the **committed offset**: the offset of the next message the group will read (Kafka stores it for the group);
- the **lag**: log-end offset − committed offset, the number of messages written and not yet read.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 170" role="img" aria-label="A partition drawn as 12 numbered boxes, offsets 0 to 11. Boxes 0 to 4 are read. The committed offset points at box 5. The log-end offset points just after box 11, at 12. The 7 boxes from 5 to 11 are the lag.">
<g font-size="13" fill="currentColor">
<g stroke="currentColor" fill="none">
<rect x="20" y="50" width="40" height="40"/><rect x="60" y="50" width="40" height="40"/><rect x="100" y="50" width="40" height="40"/><rect x="140" y="50" width="40" height="40"/><rect x="180" y="50" width="40" height="40"/>
<rect x="220" y="50" width="40" height="40" stroke-width="2.5"/><rect x="260" y="50" width="40" height="40" stroke-width="2.5"/><rect x="300" y="50" width="40" height="40" stroke-width="2.5"/><rect x="340" y="50" width="40" height="40" stroke-width="2.5"/><rect x="380" y="50" width="40" height="40" stroke-width="2.5"/><rect x="420" y="50" width="40" height="40" stroke-width="2.5"/><rect x="460" y="50" width="40" height="40" stroke-width="2.5"/>
<rect x="500" y="50" width="40" height="40" stroke-dasharray="4 3"/>
</g>
<text x="35" y="75">0</text><text x="75" y="75">1</text><text x="115" y="75">2</text><text x="155" y="75">3</text><text x="195" y="75">4</text>
<text x="235" y="75" font-weight="bold">5</text><text x="275" y="75" font-weight="bold">6</text><text x="315" y="75" font-weight="bold">7</text><text x="355" y="75" font-weight="bold">8</text><text x="395" y="75" font-weight="bold">9</text><text x="430" y="75" font-weight="bold">10</text><text x="470" y="75" font-weight="bold">11</text>
<text x="508" y="75" opacity="0.7">12</text>
<text x="20" y="30">read</text>
<text x="220" y="30">lag = 12 − 5 = 7 messages</text>
<text x="545" y="75">← next write</text>
<line x1="240" y1="98" x2="240" y2="120" stroke="currentColor"/><text x="180" y="140">committed offset = 5</text>
<line x1="520" y1="98" x2="520" y2="120" stroke="currentColor"/><text x="440" y="140">log-end offset = 12</text>
</g>
</svg>
<figcaption>Figure 8.1. One partition: messages 0 to 4 have been read; the group's committed offset is 5; the next message will get offset 12. The lag is the subtraction 12 − 5.</figcaption>
</figure>

A message with a **key** (a customer number, an order id) goes to a partition chosen from the key alone, so all messages with the same key land in the same partition, in the order they were sent. **Order is kept within a partition, and only there.** Within a consumer group, each partition is read by exactly one consumer at a time, so the partition is also the unit of parallel reading.

## 8.3 The math by hand

### Step 1. From key to partition

The Java producer (Kafka 4.3.2) sends a keyed message to

```text
partition = toPositive(murmur2(key bytes)) mod n
```

where `murmur2` is a 32-bit hash function, `toPositive(h)` keeps the low 31 bits of `h` (`h & 0x7fffffff`), and `n` is the number of partitions. For a String key, the bytes are its UTF-8 encoding.

Worked for the key `customer-7` and `n = 6` (`ex01`):

1. `murmur2("customer-7") = −1,283,830,537`. A 32-bit number is negative when its top bit is set.
2. Clearing the top bit adds `2³¹ = 2,147,483,648` to a negative number: `−1,283,830,537 + 2,147,483,648 = 863,653,111`.
3. `863,653,111 mod 6`. A number's remainder by 6 follows from its remainders by 2 and by 3. It is odd, so it is 1 mod 2. Its digits add to `8+6+3+6+5+3+1+1+1 = 34`, and `34 mod 3 = 1`, so it is 1 mod 3. The remainder by 6 that is odd and 1 mod 3 is **1**.

So every `customer-7` message goes to partition 1 of 6. With 12 partitions it would go to partition 7 (`863,653,111 = 12 × 71,971,092 + 7`).

**Why not `abs`?** Java's `Math.abs` of the most negative 32-bit number, `−2,147,483,648`, is `−2,147,483,648` itself, because `+2,147,483,648` does not fit. A negative remainder would be a crash. `toPositive` maps it to 0 instead (`ex01`). (Spark's `pmod` of tutorial 8 solves the same problem differently.)

### Step 2. Lag and the catch-up time

Lag `L = 1,200,000`. Producers add `λ = 2,000` messages per second; the group reads `μ = 2,500`. Each second the lag changes by `λ − μ = −500`. So

```text
catch-up time = L / (μ − λ) = 1,200,000 / 500 = 2,400 s = 40 minutes
```

The simulation in `ex03` (part 1) steps second by second and reaches lag 0 after exactly 2,400 seconds. If `μ ≤ λ` the lag never shrinks: adding consumers is then the only cure, and step 3 says when it helps.

Note what did **not** matter: the 1.2 million could have come from a two-hour outage or a ten-minute one. Only the backlog and the *difference* of rates count. With `μ = 2,100` the same backlog takes `1,200,000 / 100 = 12,000 s`, more than three hours.

### Step 3. How many consumers are worth having

Kafka's classic consumer groups (the default `group.protocol` in the 4.3.2 Java client) assign partitions with the **range assignor** first in their default list: partitions in number order, consumers in name order, each consumer gets `⌊p / c⌋` partitions, and the first `p mod c` consumers get one more. For `p = 12`, `c = 5`: `12 = 5 × 2 + 2`, so the sizes are `3, 3, 2, 2, 2` (`ex04`).

Suppose every partition carries the same traffic and one consumer can read `R` messages per second. The consumer with the most partitions, `⌈p / c⌉` of them, is the bottleneck: it must read `⌈p / c⌉ / p` of all traffic at speed `R`. So the whole group reads at most

```text
group speed = R × p / ⌈p / c⌉
```

For `p = 12`:

| consumers c | partitions per consumer | ⌈p / c⌉ | group speed |
| ---: | --- | ---: | ---: |
| 4 | 3, 3, 3, 3 | 3 | 4 R |
| 5 | 3, 3, 2, 2, 2 | 3 | 4 R |
| 6 | 2, 2, 2, 2, 2, 2 | 2 | 6 R |
| 7 to 11 | some 2s, some 1s | 2 | 6 R |
| 12 | all 1s | 1 | 12 R |
| 13 | twelve 1s and one 0 | 1 | 12 R (one consumer idle) |

Only the divisors of `p` (1, 2, 3, 4, 6, 12) are worth paying for; between them, extra consumers wait on the busiest one. And never more than `p` consumers: the extra ones get nothing. This is why partition counts like 12, 24 or 60, with many divisors, are popular (`ex04` lists them).

### Step 4. Little's law: from messages to seconds

A lag of 5,000 messages is nothing on a topic with 50,000 messages a second, and a lot on one with 5 a second. Little's law converts. For any system that messages enter and leave, in the long run

```text
L = λ × W
average number waiting = arrival rate × average time each waits
```

so `W = L / λ`. A steady lag of 1,309.8 messages on a partition receiving 1,000 messages per second means each message waits about 1.31 seconds before it is read.

Lag also grows sharply as the consumer approaches full use. In `ex03` (part 2) messages arrive at random, 1,000 per second on average, and the consumer reads up to 1,250 per second, but in some seconds it reads nothing (busy with garbage collection or a rebalance). The **utilisation** is the arrival rate divided by the consumer's average capacity:

| consumer free | average capacity | utilisation | average lag | average wait | λ × W |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100% | 1,250.0 /s | 0.800 | 0.0 | 0.000 s | 0.0 |
| 95% | 1,187.5 /s | 0.842 | 181.5 | 0.181 s | 181.5 |
| 90% | 1,125.0 /s | 0.889 | 500.0 | 0.500 s | 500.0 |
| 85% | 1,062.5 /s | 0.942 | 1,309.8 | 1.309 s | 1,309.8 |
| 82% | 1,025.0 /s | 0.976 | 3,222.4 | 3.221 s | 3,222.4 |

Two lessons. Little's law holds in every row (last column against the lag column; the reason is in 8.4). And going from 89% to 98% busy multiplies the lag by more than 6. A consumer that "keeps up on average" can still carry a large, jumpy lag.

### Step 5. Growing a topic moves keys

The partition of a key is `h mod n`, with `h = toPositive(murmur2(key))`. Change `n` from `a` to `b` and a key stays put only if `h mod a = h mod b`.

Both remainders depend only on `h mod lcm(a, b)`. In one block of `lcm(a, b)` consecutive values of `h`, the two remainders are equal exactly for the first `min(a, b)` values (proved in 8.4). If the hash looks random, the fraction of keys that **stay** is `min(a, b) / lcm(a, b)`.

| from → to | lcm | keys that move, predicted | measured on 120,000 keys (`ex02`) |
| --- | ---: | ---: | ---: |
| 12 → 13 | 156 | 1 − 12/156 = 92.31% | 92.24% |
| 12 → 18 | 36 | 1 − 12/36 = 66.67% | 66.90% |
| 12 → 24 | 24 | 1 − 12/24 = 50.00% | 50.28% |
| 6 → 12 | 12 | 1 − 6/12 = 50.00% | 49.90% |

Growing 12 → 13 moves almost every customer. Their old messages stay in the old partition, new ones go to the new one, and a consumer can read a customer's new messages before the old ones. Doubling moves only half, but still breaks the order for those keys. Kafka does not move old messages when partitions are added.

### Step 6. A hot key cannot be split

Spread first: with `K` distinct keys on `n` partitions, how full is the fullest? Exactly as in Spark tutorial 8, step 4, the balls-into-bins estimate is `K/n + √(2 (K/n) ln n)`. For 12,000 keys on 12 partitions: `1,000 + √(2 × 1,000 × 2.485) = 1,070`; the real Kafka rule gives 1,060 (`ex02`). Even spreading is a matter of having many keys.

Now let `customer-7` send 30% of all messages: 36,007 of 120,000, the rest spread over 12,000 customers. It goes to partition 7, which then holds 42,846 messages, **4.28 times the mean** of 10,000 (`ex02`). One consumer reads partition 7, whatever the group size. If that consumer reads `R` per second, the whole topic can take at most `R × 120,000 / 42,846 = 2.8 R` per second, even with 12 consumers. The bound of Spark tutorial 8, `max(m/n, h)`, applies unchanged: a key's messages stay together because the order of each customer's events must be kept.

## 8.4 Why it is true

**Same key, same partition.** `murmur2` is a fixed function of the key's bytes, so a key's partition depends only on its bytes and on `n`. As long as `n` stays the same, every message of a key goes to the same log, and offsets give them a total order there.

**Lag and catch-up.** The lag is a difference of two counters. In each second, the log-end offset grows by `λ` and the committed offset by `μ` (while there is something to read), so the lag shrinks by `μ − λ`; after `t` seconds it is `L − (μ − λ) t`, which is zero at `t = L / (μ − λ)`.

**Little's law, by counting.** Draw one bar per message, from the second it arrives to the second it is read. Add up the bars' lengths in two ways. Second by second: in each second, count the bars passing through it; that count is the lag at that second, so the total is `T × (average lag)`. Message by message: the total is `(number of messages) × (average wait)` = `λT × W`. Both count the same bars, so `average lag = λ × W`. In `ex03` the two columns agree because the program measures exactly these two sums. The only error comes from messages still unread when the simulation stops, which is why the law needs a **stable** system, one whose lag does not grow forever. (John Little proved the general version, for averages over time in any stable queue, in 1961.) Why lag grows so fast near full use is a theorem of queueing theory that this tutorial does not prove; the table shows it.

**Which keys stay.** Write `h = q × L + r` with `L = lcm(a, b)` and `0 ≤ r < L`. Since `a` and `b` both divide `L`, `h mod a = r mod a` and `h mod b = r mod b`. Say `a ≤ b`. If `r < a`, both remainders equal `r`. If `r ≥ a`, suppose `r mod a = r mod b = s`. Then `r − s` is a multiple of both `a` and `b`, hence of `L`. But `0 ≤ s < a ≤ r < L` makes `0 < r − s < L`, and no multiple of `L` lies strictly between 0 and `L`. So the remainders are equal for exactly `a = min(a, b)` of every `L` consecutive values.

**The busiest consumer.** The range assignor gives `⌊p/c⌋` or `⌈p/c⌉` partitions to each consumer, with at least one getting `⌈p/c⌉`. That consumer's share of equal traffic is `⌈p/c⌉ / p`, and it reads at most `R`, so the group's total is at most `R p / ⌈p/c⌉`.

## 8.5 See it in code

### Kafka's hash, reproduced

`kmath.py` writes Kafka 4.3.2's `murmur2` in Python. `ex01` checks it against the six test values in Kafka's own test suite:

```text
murmur2('21'                     ) =   -973932308  expected   -973932308  ok
murmur2('foobar'                 ) =   -790332482  expected   -790332482  ok
murmur2('abc'                    ) =    479470107  expected    479470107  ok
...                                                             (all six ok)
```

and lists the partitions of `customer-1` to `customer-8` on 6 partitions: 3, 2, 4, 1, 0, 1, 1, 2. Three of eight keys land in partition 1, none in partition 5: the unevenness of few keys.

### Many keys spread evenly; one hot key does not

`ex02`, part 1, `K` keys with one message each on 12 partitions:

| keys K | fullest partition | mean | max / mean | balls-into-bins estimate |
| ---: | ---: | ---: | ---: | ---: |
| 120 | 16 | 10 | 1.600 | 1.705 |
| 1,200 | 115 | 100 | 1.150 | 1.223 |
| 12,000 | 1,060 | 1,000 | 1.060 | 1.070 |
| 120,000 | 10,216 | 10,000 | 1.022 | 1.022 |

Part 2, the hot customer: partition loads `[7420, 7119, 6601, 6804, 6951, 6685, 7091, 42846, 6944, 7147, 7301, 7091]`.

### The simulations

`ex03` and `ex04` are the models behind the tables of steps 2 to 4. They are not measurements of a Kafka cluster: real consumers fetch in batches, commit offsets every few seconds (so the committed offset, and the lag it implies, jumps), and pause during rebalances. The arithmetic of steps 2 to 4 does not depend on those details; the exact numbers in the tables do.

## 8.6 Where it breaks

- **Messages without a key are not hashed.** In the Java producer they go to the partition chosen by the built-in "sticky" partitioner (KIP-794): it fills a batch for one partition, then moves on, so keyless traffic spreads evenly over time. Step 1 applies to keyed messages only.
- **The bytes, not the meaning.** The hash is of the serialized key. The same customer sent as the string `"7"` and as a 4-byte integer 7 has different bytes, so it can land in different partitions. All producers of a topic must serialize keys the same way, and other clients must use the same hash (some non-Java clients default to a different one; check yours).
- **Custom partitioners** replace step 1 entirely.
- **Lag in messages hides time.** Compare lags in seconds (`L / λ`, step 4), not in messages, across topics with different rates.
- **Little's law needs stability.** With `μ ≤ λ` there is no long-run average to speak of; step 2 applies instead.
- **More consumers than partitions do not help** a classic consumer group (step 3). Kafka 4 also has share groups (KIP-932), where several consumers share one partition and give up its ordering; this tutorial does not cover them. The newer consumer group protocol (KIP-848, `group.protocol=consumer`) assigns partitions on the broker, with its own assignors; the arithmetic of step 3 holds for any assignor that gives some consumer `⌈p / c⌉` partitions.
- **Adding partitions breaks per-key order** (step 5). If order matters, create a topic with enough partitions from the start, or migrate to a new topic deliberately.

## 8.7 Exercises

Do 1 to 5 with a pencil. 6 needs a few lines of thought. 7 is code.

**E1. `murmur2` of a key is `−58,897,971` (one of Kafka's test values). Which partition does it go to with 10 partitions? With 12?**

??? success "Answer"
    `toPositive = −58,897,971 + 2,147,483,648 = 2,088,585,677`. Mod 10: the last digit, **7**. Mod 12: `2,088,585,677 = 12 × 174,048,806 + 5`, so **5**. (Check: mod 4 from the last two digits, `77 mod 4 = 1`; mod 3 from the digit sum, `2+0+8+8+5+8+5+6+7+7 = 56`, `56 mod 3 = 2`; the remainder by 12 that is 1 mod 4 and 2 mod 3 is 5.)

**E2. A group is 3,000,000 messages behind. Producers write 4,000 per second; each of its consumers reads 1,000 per second, and the topic has 24 partitions with equal traffic. How long does it take to catch up with 6 consumers? With 8? With 10?**

??? success "Answer"
    Group speed `= 1,000 × 24 / ⌈24 / c⌉`. `c = 6`: `⌈4⌉ = 4`, speed 6,000/s, catch-up `3,000,000 / (6,000 − 4,000) = 1,500 s` (25 min). `c = 8`: `⌈3⌉ = 3`, speed 8,000/s, `3,000,000 / 4,000 = 750 s`. `c = 10`: `⌈2.4⌉ = 3`, still 8,000/s, still 750 s: the two extra consumers buy nothing. 12 consumers would give 12,000/s and 375 s.

**E3. A partition receives 200 messages per second, and its lag hovers around 3,000. About how old is a message when it is read? The service promises "within 10 seconds". Is it met on average?**

??? success "Answer"
    `W = L / λ = 3,000 / 200 = 15 s`. Not met, even on average. Little's law gives the average, so some messages wait longer still.

**E4. What fraction of keys keep their partition when a topic grows from 10 to 15 partitions? From 8 to 12? From 16 to 32?**

??? success "Answer"
    `min / lcm`: 10 → 15: `10 / 30 = 1/3` stay (2/3 move). 8 → 12: `8 / 24 = 1/3` stay. 16 → 32: `16 / 32 = 1/2` stay. Growing to a multiple is the least disruptive, and even then half the keys move.

**E5. Retention: a topic receives 3,000 messages per second of 1 KB each, keeps them 7 days (Kafka's default `log.retention.hours=168`), and has 3 copies of every partition. How much disk does it need across the cluster?**

??? success "Answer"
    `3,000 × 1 KB × 604,800 s = 1,814,400,000 KB ≈ 1.81 TB` per copy (taking 1 KB = 1,000 bytes; compression and per-message overhead ignored). Three copies: about **5.4 TB**. Disk is rate × size × time × copies: a product, so halving any one factor halves the total.

**E6. A payment topic is keyed by account. One merchant account sends 40% of the messages. Name two ways to read faster without losing the order of each account's payments, and one way that would lose it.**

??? success "Answer"
    Faster with order kept: make the consumer of the hot partition itself faster (for example, write to the database in batches instead of one payment at a time), or move the hot merchant to its own topic so that its consumer does nothing else while the other accounts are read by the rest of the group. Lost: keying by a random or round-robin value (or no key), which spreads the merchant over all partitions so its payments can be read out of order.

**E7. (Code.) With `kmath.py`, find the partition of `customer-1` to `customer-100,000` for 12 partitions, then count how many partitions the keys of a customer occupy if you key by `customer-N:salt` with `salt` in 0..3. What did salting buy, and what did it cost?**

??? success "Answer"
    ```python
    from collections import Counter
    from kmath import partition_for_key

    plain = Counter(partition_for_key(f"customer-{i}", 12) for i in range(1, 100_001))
    spread = [len({partition_for_key(f"customer-{i}:{s}", 12) for s in range(4)}) for i in range(1, 1001)]
    print(sorted(plain.values()), Counter(spread))
    ```

    It prints the 12 partition counts, from 8,155 to 8,564 around the mean 8,333, and `Counter({4: 557, 3: 397, 2: 45, 1: 1})`: of the first 1,000 customers, 557 have their 4 salted keys in 4 different partitions, 397 in 3, 45 in 2, and 1 in only one. By pencil, the chance that 4 random throws into 12 partitions all differ is `12 × 11 × 10 × 9 / 12⁴ = 0.573`. Salting lets up to 4 consumers share a hot customer, but that customer's messages are no longer in one ordered log: the consumer side must re-order them (by a sequence number) if order matters. ([ex05_salt.py](src/08/ex05_salt.py), [output](src/08/ex05.out.txt).)

## 8.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a lagging consumer group you met, its partitions and consumers, and what fixed it.)*

## 8.9 Further reading

On your own sites:

- Remainders and least common multiples: [the Math site](https://math.akadian.ca/)
- Hashing: [Algorithms, ch 7. Searching and hashing](https://cs.akadian.ca/books/algorithms/07-Searching-and-Hashing/)
- The same hashing in Spark: [8. Shuffles and skew in Spark](../spark/08-Shuffles-and-Skew.md)

Original sources:

- J. Kreps, "The Log: What every software engineer should know about real-time data's unifying abstraction", LinkedIn Engineering blog, 2013. The log as the central idea.
- J. D. C. Little, "A proof for the queuing formula L = λW", *Operations Research* 9(3), 1961.
- M. Raab and A. Steger, "'Balls into Bins': A Simple and Tight Analysis", *RANDOM 1998*. The estimate of step 6.
- Kafka 4.3.2 source: `clients/.../common/utils/Utils.java` (`murmur2`, `toPositive`), `clients/.../producer/internals/BuiltInPartitioner.java`, `clients/.../consumer/RangeAssignor.java`, `clients/.../consumer/ConsumerConfig.java` (defaults), at [github.com/apache/kafka](https://github.com/apache/kafka/tree/4.3.2).
- Kafka Improvement Proposals KIP-794 (sticky partitioner), KIP-848 (new consumer group protocol), KIP-932 (share groups), on the Apache Kafka wiki.

## Glossary

- **Topic**: a named stream of messages, split into partitions.
- **Partition**: one append-only log; the unit of order and of parallel reading.
- **Offset**: a message's position in its partition, 0, 1, 2, …
- **Log-end offset**: the offset the next message will get.
- **Committed offset**: the next offset a consumer group will read, stored by Kafka.
- **Lag**: log-end offset minus committed offset.
- **Consumer group**: consumers that share the reading of a topic; each partition goes to one of them.
- **Assignor**: the rule that decides which consumer reads which partition.
- **Utilisation**: arrival rate divided by the consumer's capacity.
- **Little's law**: average number waiting = arrival rate × average wait.
- **lcm**: least common multiple, the smallest number both numbers divide.
