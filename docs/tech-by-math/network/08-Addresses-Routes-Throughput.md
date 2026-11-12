# 8. Addresses, routes and throughput

*A packet leaves your laptop for `10.20.6.200`. A router compares the address with a table, picks the most specific matching route, and sends the packet along a path chosen by Dijkstra's algorithm from link costs. The connection on top of it never runs faster than one window per round trip, and on a lossy link its speed falls with the square root of the loss rate. Every step is short arithmetic: AND with a mask, a smallest sum, a division. This tutorial does each by hand and checks it with a program.*

!!! abstract "In this tutorial"
    **You will learn:**

    - how a prefix length becomes a mask, and how one AND finds the network of any address
    - how many subnets and hosts a split gives, as powers of 2
    - longest-prefix match: why the most specific route wins, worked on a five-route table
    - link costs as `reference / bandwidth`, Dijkstra's algorithm step by step on six routers, and what goes wrong when every fast link costs 1
    - the window limit `rate ≤ window / RTT` and the bandwidth-delay product
    - the Mathis formula `rate ≈ (MSS / RTT) × √(3 / (2p))`, derived from the sawtooth of TCP's congestion window and checked by simulation
    - the Internet checksum, and one kind of error it cannot see

    **You need:** binary numbers, powers of 2, and square roots. The Networks site's [Math for networks](https://networks.akadian.ca/books/math/) book goes deeper into each topic; this tutorial is a worked tour.

    **How to learn from it:** read 8.1 to 8.3, close the page, redo the examples of 8.3 on paper, then try the exercises in 8.7 before opening any answer. Plan about two and a half hours.

**About the examples.** Everything here is computed in Python. Subnets and route matches are checked against Python's standard `ipaddress` module; Dijkstra's result against trying every possible path; the TCP formula against a **simulation** of the congestion window (a model, not a real TCP stack); the checksum against the rule a receiver applies. The scripts and their full output: [ex01_subnets.py](src/08/ex01_subnets.py) ([output](src/08/ex01.out.txt)), [ex02_dijkstra.py](src/08/ex02_dijkstra.py) ([output](src/08/ex02.out.txt)), [ex03_tcp.py](src/08/ex03_tcp.py) ([output](src/08/ex03.out.txt)) and [ex04_checksum.py](src/08/ex04_checksum.py) ([output](src/08/ex04.out.txt)).

## 8.1 The question

1. A laptop has address `192.168.10.77/26`. What is its network, and which addresses are its neighbours?
2. A router's table has routes for `0.0.0.0/0`, `10.0.0.0/8`, `10.20.0.0/16`, `10.20.4.0/22` and `10.20.6.128/25`. Where does it send `10.20.6.200`? `10.20.6.5`?
3. Six routers are linked at 100, 1,000 and 10,000 Mbit/s. Which path does traffic from A to F take, and why can a careless setting send it over the slowest links?
4. A file transfer between two cities 100 ms apart reaches only 5 Mbit/s on a 1 Gbit/s line. Why, and what would fix it?

## 8.2 The idea: everything is a comparison or a sum

An IPv4 address is a 32-bit number, written as four bytes in decimal. A **prefix** `a.b.c.d/n` names the block of addresses whose first `n` bits equal those of `a.b.c.d`. A router's **forwarding table** is a list of prefixes, each with where to send matching packets. For each packet it finds the matching prefix with the largest `n`: **longest-prefix match**.

The table itself is filled by a routing protocol. A link-state protocol such as OSPF gives every link a **cost**, floods the map of links to every router, and each router runs **Dijkstra's algorithm** to find the cheapest path to every destination.

On top, TCP sends data in **segments** and may have at most one **window** of unacknowledged data in flight. Acknowledgements come back one **round-trip time** (RTT) later. Each of these turns into one line of arithmetic.

## 8.3 The math by hand

### Step 1. Mask and network

`/26` means 26 one-bits followed by 6 zero-bits: `255.255.255.192`. AND the address with the mask, bit by bit (`ex01`):

```text
address   11000000.10101000.00001010.01001101   192.168.10.77
mask /26  11111111.11111111.11111111.11000000   255.255.255.192
AND       11000000.10101000.00001010.01000000   192.168.10.64    network
```

Setting the 6 host bits to 1 instead gives the **broadcast** address `192.168.10.127`. The block holds `2^6 = 64` addresses, of which 62 can be hosts (the first is the network, the last the broadcast). In decimal, only the last byte needed work: `77 AND 192 = 64`, because 192 = `11000000` keeps the top two bits of 77 = `01001101`.

Splitting: `10.20.0.0/22` has `2^(32 − 22) = 1,024` addresses. Cut into `/24`s it gives `2^(24 − 22) = 4` subnets; into `/26`s, `2^(26 − 22) = 16` subnets of 64. The `ipaddress` module lists the same (`ex01`).

### Step 2. Longest-prefix match

For `10.20.6.200`, test each route: does the address AND the route's mask equal the route's prefix?

| route | mask | 10.20.6.200 AND mask | match? |
| --- | --- | --- | --- |
| 0.0.0.0/0 | 0.0.0.0 | 0.0.0.0 | yes |
| 10.0.0.0/8 | 255.0.0.0 | 10.0.0.0 | yes |
| 10.20.0.0/16 | 255.255.0.0 | 10.20.0.0 | yes |
| 10.20.4.0/22 | 255.255.252.0 | 10.20.4.0 | yes (6 AND 252 = 4) |
| 10.20.6.128/25 | 255.255.255.128 | 10.20.6.128 | yes (200 AND 128 = 128) |

All five match; the longest, `/25`, wins: the packet goes to the printers' network. For `10.20.6.5`, the `/25` test gives `5 AND 128 = 0`, so `10.20.6.0` ≠ `10.20.6.128`: no match, and the `/22` wins. `10.20.9.9` fails the `/22` (`9 AND 252 = 8`, not 4) and goes to the `/16`; `8.8.8.8` matches only `/0`, the default route. All five answers agree with `ipaddress` (`ex01`).

Why the longest? A longer prefix is a smaller block inside the larger ones, so it is a more specific statement about where those addresses are. The default route `/0` matches everything and is the answer of last resort.

### Step 3. Costs and Dijkstra

Give each link the cost `reference / bandwidth`. With a reference of 10,000 Mbit/s: 100 Mbit/s costs 100, 1,000 costs 10, 10,000 costs 1. The network of `ex02`:

```text
A–B 10    A–C 100   B–C 10    B–D 100
C–E 10    E–D 10    E–F 100   D–F 1
```

**Dijkstra's algorithm** keeps a tentative distance for every router, starts with A at 0, and repeats: take the unfinished router with the smallest tentative distance, mark it finished, and for each neighbour check whether going through it is cheaper ("relax" the link).

| finish | at | updates |
| --- | ---: | --- |
| A | 0 | B = 10, C = 100 |
| B | 10 | C = 20 (via B, cheaper than 100), D = 110 |
| C | 20 | E = 30 |
| E | 30 | D = 40 (cheaper than 110), F = 130 |
| D | 40 | F = 41 |
| F | 41 | nothing |

So A reaches F at cost 41 along A–B–C–E–D–F: five links, all of 1,000 Mbit/s or more. `ex02` checks every simple path from A to each router and finds the same five answers.

**The reference matters.** With a reference of 100 Mbit/s, every link of 100 Mbit/s *or faster* gets cost `max(1, 100 / bw) = 1`, and the cost becomes a hop count. Then A–B–D–F (3 hops) wins, and it crosses the 100 Mbit/s link B–D, while A–B–C–E–D–F never drops below 1,000 Mbit/s (`ex02`). The algorithm is right in both cases; the costs were wrong in the second. Set the reference at least as high as the fastest link.

### Step 4. The window limit

TCP may have at most one window `W` of unacknowledged bytes in flight. The first acknowledgement returns one RTT after sending, so in each RTT at most `W` bytes leave:

```text
rate ≤ W / RTT
```

With the classic maximum window of 64 KiB (65,536 bytes) and RTT 100 ms: `65,536 × 8 / 0.1 = 5,242,880` bit/s, about **5.2 Mbit/s**, whatever the line's speed (question 4). At RTT 1 ms the same window allows 524 Mbit/s (`ex03`).

Turned around: to fill a line of bandwidth `B` with round trip `RTT`, the window must be at least the **bandwidth-delay product** `B × RTT`: for 1 Gbit/s and 80 ms, `10^9 × 0.08 / 8 = 10,000,000` bytes, about 9.5 MiB. TCP's window-scale option (RFC 7323) lets windows grow far beyond 64 KiB; operating systems tune buffers automatically, within configured maximums.

### Step 5. Loss: the square-root law

TCP's congestion control (in its classic form) grows its window by one segment per round trip and halves it on a loss: **additive increase, multiplicative decrease**. If one segment in `1/p` is lost, the window settles into a sawtooth between `W/2` and `W`.

In one tooth, the window goes from `W/2` to `W` in `W/2` round trips, sending on average `3W/4` segments per round trip, so `(W/2) × (3W/4) = 3W²/8` segments per tooth. One tooth ends with one loss, so `3W²/8 = 1/p`, and `W = √(8 / (3p))`. The average rate is `(3W/4)` segments per RTT:

```text
rate ≈ (MSS / RTT) × (3/4) × √(8 / (3p)) = (MSS / RTT) × √(3 / (2p))
```

This is the formula of Mathis and colleagues (1997). With MSS = 1,460 bytes and RTT = 100 ms, the simulation of `ex03` (window +1 per round trip, halved after every `1/p` segments) gives:

| loss rate p | simulated | formula |
| ---: | ---: | ---: |
| 1% | 1.40 Mbit/s | 1.43 Mbit/s |
| 0.1% | 4.52 Mbit/s | 4.52 Mbit/s |
| 0.01% | 14.27 Mbit/s | 14.31 Mbit/s |
| 0.001% | 45.15 Mbit/s | 45.24 Mbit/s |

Ten times less loss gives only `√10 ≈ 3.16` times more speed, and doubling the RTT halves the speed. That is why long-distance transfers on slightly lossy links are slow, even on fast lines.

### Step 6. The Internet checksum

IPv4 protects its 20-byte header with a 16-bit checksum (RFC 1071). Add the header's ten 16-bit words, with the checksum field set to 0; fold any carry above 16 bits back into the low 16 bits; and take the ones' complement (flip every bit). Worked on a real-shaped header (`ex04`):

```text
words      4500 0054 a6f2 4000 4001 0000 c0a8 0a4d c0a8 0a01
sum        0x301e5
fold       0x01e5 + 0x3 = 0x01e8
checksum   ~0x01e8 = 0xfe17
```

The receiver adds all ten words *including* the checksum and folds: the result must be `0xffff`, and here it is. Flip one bit of the destination address and the folded sum becomes `0x0100`: caught. But swap two 16-bit words and the sum is unchanged, because addition does not care about order: **not caught**. The checksum is cheap and catches common accidents, not all errors; links use stronger CRCs underneath.

## 8.4 Why it is true

**AND finds the network.** The mask has 1s exactly in the prefix positions. AND keeps a bit where the mask is 1 and clears it where the mask is 0, so `address AND mask` keeps the prefix and zeroes the host part, which is the definition of the network address.

**Longest-prefix match is well defined.** Two prefixes either do not overlap or one contains the other (a block of `2^k` aligned addresses splits into two aligned halves, and so on). So the matching prefixes of an address are nested, like Russian dolls, and the longest is the innermost: the most specific route.

**Dijkstra is correct with costs ≥ 0.** When the closest unfinished router `u` is taken, its tentative distance `d` is final: any other path to `u` must leave the finished set through some unfinished router whose distance is already at least `d`, and adding non-negative costs cannot make it shorter. By induction, every finished distance is the true shortest. With negative costs this argument fails, and so can the algorithm; link costs are never negative.

**The window limit.** Data sent at time `t` is acknowledged no earlier than `t + RTT`, and until then it counts against the window. So in any interval of one RTT, at most one window can be sent.

**The square-root law.** Derived in step 5 for a deterministic sawtooth with one loss per tooth. Real losses are random, timeouts and slow start add their own effects, and modern algorithms (such as CUBIC, Linux's default) grow the window differently, so the formula is a guide to how speed scales, not a prediction to the decimal. The simulation matches it because the simulation makes the same assumptions.

**The checksum.** Ones' complement addition with end-around carry is commutative and associative, so the sum does not depend on word order. That is exactly why swapped words go unnoticed. The receiver's sum of all words including the checksum `c` is `S + ~S`, which is `0xffff` in ones' complement arithmetic.

## 8.5 See it in code

`ex01` prints the bit patterns of step 1 and the five route matches of step 2, each confirmed by `ipaddress`:

```text
10.20.6.200  -> 10.20.6.128/25  (printers)
10.20.6.5    -> 10.20.4.0/22    (lab)
10.20.9.9    -> 10.20.0.0/16    (campus)
10.99.1.1    -> 10.0.0.0/8      (core)
8.8.8.8      -> 0.0.0.0/0       (internet)
```

`ex02` prints the Dijkstra steps of step 3 and the brute-force check:

```text
A -> F:  41 via A-B-C-E-D-F  brute force:  41 via A-B-C-E-D-F
A -> F by hop count: 3 hops via A-B-D-F; slowest link on it 100 Mbit/s
```

`ex03` prints the window table and the simulation of step 5; `ex04` the checksum of step 6 with its two tampering tests.

## 8.6 Where it breaks

- **IPv6** uses 128-bit addresses and the same prefix arithmetic, with `2^64` addresses in a typical subnet; "how many hosts" stops being a constraint. Its header has no checksum at all; it relies on the link below and on transport checksums.
- **Real routers** do longest-prefix match in specialised data structures (tries) or hardware, not by scanning a list; the answer is the same.
- **Costs are a policy.** Dijkstra finds the cheapest path for the costs it is given; between organisations, BGP chooses routes by policy, not by shortest path at all.
- **Equal-cost paths.** When several paths tie, routers usually spread traffic over them (ECMP), by hashing each connection's addresses and ports so one connection stays on one path: the same hashing idea as Kafka's partitions.
- **The square-root law is a model** (step 5 and 8.4). Use it for how speed scales with loss and RTT, not for exact numbers on a real network.
- **Middleboxes.** Firewalls and NAT rewrite addresses and ports, and must recompute checksums when they do.

## 8.7 Exercises

Do 1 to 5 with a pencil. 6 needs a few lines of thought. 7 is code.

**E1. For `172.16.45.200/20`, find the mask, the network, the broadcast address and the number of usable hosts.**

??? success "Answer"
    `/20` = `255.255.240.0`. Third byte: `45 AND 240 = 32` (45 = `00101101`, 240 = `11110000`, AND = `00100000`). Network `172.16.32.0`. Host bits: 12, so broadcast = network + `2^12 − 1`: third byte `32 + 15 = 47`, fourth `255`: `172.16.47.255`. Usable hosts `2^12 − 2 = 4,094`.

**E2. Split `192.168.0.0/24` into subnets of at least 50 hosts each. What prefix length, how many subnets, and what are they?**

??? success "Answer"
    50 hosts need 6 host bits (`2^6 − 2 = 62 ≥ 50`; 5 bits give only 30). Prefix `/26`, `2^(26 − 24) = 4` subnets: `192.168.0.0/26`, `.64/26`, `.128/26`, `.192/26`.

**E3. Using the table of step 2, where do `10.20.7.130` and `10.20.3.1` go?**

??? success "Answer"
    `10.20.7.130`: `/25` test: third byte 7 ≠ 6, no. `/22`: `7 AND 252 = 4`, yes: lab. `10.20.3.1`: `/22`: `3 AND 252 = 0`, not 4, no; `/16` matches: campus.

**E4. In the network of step 3, link E–D fails. What is the new shortest path from A to F, and its cost?**

??? success "Answer"
    Without E–D, the paths to F are through B–D–F or C–E–F. A–B–D–F costs `10 + 100 + 1 = 111`; A–B–C–E–F costs `10 + 10 + 10 + 100 = 130`. So A–B–D–F, cost 111.

**E5. A backup runs over a 10 Gbit/s link with RTT 40 ms. What window does it need to fill the link? With a 4 MiB window, what is its maximum rate?**

??? success "Answer"
    Bandwidth-delay product: `10^10 × 0.04 / 8 = 50,000,000` bytes, about 47.7 MiB. With 4 MiB: `4 × 1,048,576 × 8 / 0.04 = 838,860,800` bit/s, about 839 Mbit/s, less than a tenth of the link.

**E6. A video service sees 0.5% packet loss to one country, with RTT 150 ms. Using the square-root law, what rate can one TCP connection expect with MSS 1,460 bytes? What helps more: halving the loss or halving the RTT?**

??? success "Answer"
    `(1460 × 8 / 0.15) × √(3 / (2 × 0.005)) = 77,867 × √300 = 77,867 × 17.32 ≈ 1.35 Mbit/s`. Halving the loss multiplies the rate by `√2 ≈ 1.41`; halving the RTT doubles it. A server closer to the viewers (a CDN) helps more than a cleaner link.

**E7. (Code.) Write the Internet checksum as a function, and find two different 4-word messages with the same checksum that do not differ only by word order.**

??? success "Answer"
    ```python
    def checksum(words):
        s = sum(words)
        while s >> 16:
            s = (s & 0xFFFF) + (s >> 16)
        return ~s & 0xFFFF

    a = [0x1234, 0x0001, 0x0000, 0xABCD]
    b = [0x1233, 0x0002, 0x0000, 0xABCD]   # one word down by 1, another up by 1
    print(hex(checksum(a)), hex(checksum(b)))
    ```

    Both give `0x41fd`: any change that keeps the sum of the words the same is invisible. ([ex05_collide.py](src/08/ex05_collide.py), [output](src/08/ex05.out.txt).)

## 8.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a slow transfer, a routing surprise or a subnet mistake you met, and which step explained it.)*

## 8.9 Further reading

On your own sites:

- The Networks site: [Math for networks](https://networks.akadian.ca/books/math/) (masks, queues, graphs, capacity) and [IPv4 addressing and subnets](https://networks.akadian.ca/books/networks/08-IPv4-Addressing-and-Subnets/)
- Little's law and queues, used in [Kafka 8. The log, offsets and lag](../kafka/08-Log-Offsets-and-Lag.md)

Original sources:

- E. W. Dijkstra, "A note on two problems in connexion with graphs", *Numerische Mathematik* 1, 1959.
- J. Moy, RFC 2328, *OSPF Version 2*, 1998.
- M. Mathis, J. Semke, J. Mahdavi and T. Ott, "The macroscopic behavior of the TCP congestion avoidance algorithm", *ACM SIGCOMM Computer Communication Review* 27(3), 1997.
- R. Braden, D. Borman and C. Partridge, RFC 1071, *Computing the Internet Checksum*, 1988.
- RFC 4632, *Classless Inter-domain Routing (CIDR)*, 2006; RFC 7323, *TCP Extensions for High Performance* (window scaling), 2014.

## Glossary

- **Prefix / CIDR block**: the addresses sharing their first `n` bits, written `a.b.c.d/n`.
- **Mask**: `n` one-bits then zeros; AND with it gives the network.
- **Broadcast address**: the last address of a block (host bits all 1).
- **Longest-prefix match**: choosing, among matching routes, the one with the longest prefix.
- **Link-state routing**: every router learns the whole map of links and computes paths itself (OSPF, IS-IS).
- **Dijkstra's algorithm**: shortest paths from one node, for non-negative costs.
- **RTT**: round-trip time.
- **Window**: the most unacknowledged data a TCP sender may have in flight.
- **Bandwidth-delay product**: bandwidth × RTT, the window needed to fill a path.
- **AIMD**: additive increase, multiplicative decrease, TCP's classic congestion control.
- **MSS**: maximum segment size, the data in one TCP segment.
- **Ones' complement checksum**: the 16-bit sum with end-around carry, inverted.
