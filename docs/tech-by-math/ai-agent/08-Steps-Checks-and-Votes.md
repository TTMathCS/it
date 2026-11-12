# 8. Steps, checks and votes: the arithmetic of agents

*An AI agent is a language model in a loop: it thinks, calls a tool, reads the result, and decides what to do next, until the task is done or it gives up. Whether such an agent is useful at work is mostly decided by arithmetic that has nothing to do with the model's inner workings: how small errors pile up over many steps, how much a check that catches mistakes is worth, when asking several times and voting helps, how many steps the loop takes, and how fast the text it carries grows. This tutorial does each by hand and checks it with a program.*

!!! abstract "In this tutorial"
    **You will learn:**

    - why a 20-step task with 95% reliable steps succeeds only about one time in three: `p^n`, and the shortcut `e^(−n(1−p))`
    - what a check-and-retry step is worth, why the quality of the check matters more than the number of retries, and the ceiling `p / (1 − (1 − p) d)`
    - when majority voting over several answers helps (each answer more often right than wrong, and errors not shared), and when it makes things worse
    - the agent loop as a Markov chain: the expected number of steps, the chance of finishing, and the effect of a step budget
    - why the text an agent sends grows with the square of its number of steps, and what summarising saves

    **You need:** powers, sums, and the chance of independent events happening together. [AI 8. How a language model picks the next word](../ai/08-How-a-Language-Model-Picks-the-Next-Word.md) explains the model inside the loop; this tutorial treats it as a step that is right with some probability.

    **How to learn from it:** read 8.1 to 8.3, close the page, redo the examples of 8.3 on paper, then try the exercises in 8.7 before opening any answer. Plan about two hours.

**About the examples.** No agent or model was run. Every number comes from a **model**: each step is right or wrong with a fixed chance, independently of the others unless stated. Real agents are not so tidy, and their real success rates are unknown here; the point is how the numbers combine. Each formula is checked against a seeded **simulation** of the same model in Python (and numpy for the matrix). The scripts and their full output: [ex01_chains.py](src/08/ex01_chains.py) ([output](src/08/ex01.out.txt)), [ex02_voting.py](src/08/ex02_voting.py) ([output](src/08/ex02.out.txt)), [ex03_loop.py](src/08/ex03_loop.py) ([output](src/08/ex03.out.txt)), [ex04_context.py](src/08/ex04_context.py) ([output](src/08/ex04.out.txt)) and [ex05_plurality.py](src/08/ex05_plurality.py) ([output](src/08/ex05.out.txt)).

## 8.1 The question

1. An agent fixes a failing data pipeline in 20 steps: read the logs, find the cause, edit the code, run the tests, and so on. Each step is right 95% of the time. How often is the whole task right?
2. After each step a test checks the result and the step is retried if the test fails. How much does that help, if the test catches 90% of mistakes?
3. A question is asked five times and the most common answer is kept. When is that better than asking once?
4. The agent's loop is "think, call a tool, check", repeated. How many steps does a task take on average, and what does a limit of 12 steps cost?
5. Each step adds 500 tokens of text to the conversation, which is sent in full every time. How many tokens does a 40-step run send?

## 8.2 The idea: chances multiply, checks divide the errors, and history adds up

Three facts do almost all the work:

- **Independent chances multiply.** If each step is right with chance `p`, independently, all `n` steps are right with chance `p × p × … × p = p^n`.
- **A check turns some failures into retries.** A wrong step that is caught costs time, not the task. Only the mistakes that slip through count.
- **An agent re-reads its whole history at every step.** Each step sends everything so far, so the totals grow like `1 + 2 + … + n`.

The rest of the tutorial is these three facts applied to the questions of 8.1.

## 8.3 The math by hand

### Step 1. Long chains

With `p = 0.95` and `n = 20`:

```text
0.95^20 = 0.358
```

By hand, with logarithms: `ln 0.95 = −0.0513`, times 20 is `−1.026`, and `e^(−1.026) = 0.358`. A useful shortcut: for `p` close to 1, `ln p ≈ −(1 − p)`, so

```text
p^n ≈ e^(−n(1 − p))
```

Here `n(1 − p) = 20 × 0.05 = 1`, and `e^(−1) = 0.368`, close to 0.358. The shortcut says the task fails about as often as "one expected error" suggests: when `n(1 − p) = 1`, success is about 37%.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 215" role="img" aria-label="The chance that every step of a task is right, against the number of steps from 0 to 50, for steps right 99, 95 and 90 percent of the time. At 20 steps the chances are 0.82, 0.36 and 0.12; at 50 steps 0.61, 0.08 and 0.005.">
<g font-size="12" fill="currentColor">
<g stroke="currentColor" fill="none">
<line x1="60" y1="170" x2="600" y2="170"/><line x1="60" y1="170" x2="60" y2="25"/>
<line x1="276" y1="170" x2="276" y2="25" stroke-dasharray="4 4" opacity="0.5"/>
<polyline stroke-width="2.5" points="60.0,30.0 81.6,32.8 103.2,35.5 124.8,38.2 146.4,40.8 168.0,43.4 189.6,45.9 211.2,48.4 232.8,50.8 254.4,53.2 276.0,55.5 297.6,57.8 319.2,60.0 340.8,62.2 362.4,64.3 384.0,66.4 405.6,68.5 427.2,70.5 448.8,72.5 470.4,74.4 492.0,76.3 513.6,78.2 535.2,80.0 556.8,81.8 578.4,83.6 600.0,85.3"/>
<polyline stroke-width="2.5" opacity="0.7" points="60.0,30.0 81.6,43.7 103.2,56.0 124.8,67.1 146.4,77.1 168.0,86.2 189.6,94.3 211.2,101.7 232.8,108.4 254.4,114.4 276.0,119.8 297.6,124.7 319.2,129.1 340.8,133.1 362.4,136.7 384.0,140.0 405.6,142.9 427.2,145.5 448.8,147.9 470.4,150.1 492.0,152.0 513.6,153.8 535.2,155.3 556.8,156.8 578.4,158.1 600.0,159.2"/>
<polyline stroke-width="2.5" opacity="0.4" points="60.0,30.0 81.6,56.6 103.2,78.1 124.8,95.6 146.4,109.7 168.0,121.2 189.6,130.5 211.2,138.0 232.8,144.1 254.4,149.0 276.0,153.0 297.6,156.2 319.2,158.8 340.8,161.0 362.4,162.7 384.0,164.1 405.6,165.2 427.2,166.1 448.8,166.8 470.4,167.4 492.0,167.9 513.6,168.3 535.2,168.6 556.8,168.9 578.4,169.1 600.0,169.3"/>
</g>
<text x="30" y="34">1.0</text><text x="46" y="174">0</text>
<text x="56" y="188">0</text><text x="268" y="188">20</text><text x="590" y="188">50</text>
<text x="540" y="100">p = 0.99</text><text x="540" y="148">p = 0.95</text><text x="286" y="150">p = 0.90</text>
<text x="284" y="52">0.82</text><text x="284" y="116">0.36</text>
<text x="250" y="206">steps in the task</text>
</g>
</svg>
<figcaption>Figure 8.1. The chance that all <code>n</code> steps are right, <code>p^n</code>, for steps right 99%, 95% and 90% of the time (<code>ex01</code>). At 20 steps: 0.82, 0.36 and 0.12.</figcaption>
</figure>

To make a 20-step task succeed 90% of the time without checks, each step must satisfy `p^20 = 0.9`, so `p = 0.9^(1/20) = 0.9947`: about one error in 190 steps.

### Step 2. Checks and retries

Now each step may be tried up to `k` times. An attempt is right with chance `p`. A wrong attempt is **caught** by a check with chance `d` (and tried again), or slips through with chance `1 − d` and spoils the task. A step ends well if the first attempt is right; or the first is wrong and caught and the second is right; and so on:

```text
P(step right) = p × (1 + (1 − p)d + ((1 − p)d)² + … + ((1 − p)d)^(k−1))
```

With `p = 0.95`, `d = 0.9`, `k = 3`: `(1 − p)d = 0.05 × 0.9 = 0.045`, and

```text
P(step right) = 0.95 × (1 + 0.045 + 0.002) = 0.95 × 1.047 = 0.9947
20 steps: 0.9947^20 = 0.899
```

The check lifts the task from 36% to 90%. With a perfect check (`d = 1`) and three attempts, a step fails only if all three attempts are wrong, `0.05³ = 0.000125`, and 20 steps succeed 99.75% of the time. With a check that catches only half the mistakes, 20 steps succeed 59% of the time.

More retries hardly help once a check is imperfect. With unlimited attempts the sum is a geometric series:

```text
P(step right) → p / (1 − (1 − p)d) = 0.95 / 0.955 = 0.99476
```

Ten attempts give 0.99476 against 0.99467 for three. The mistakes that slip past the check, `(1 − p)(1 − d) = 0.5%` per attempt, set the ceiling. Improving the check is what moves it.

### Step 3. Asking several times and voting

Ask the same question `n` times (`n` odd), each answer right with chance `p`, independently, and keep the majority. With `p = 0.6` and `n = 3`, the majority is right if 2 or 3 answers are right:

```text
P = 3 × 0.6² × 0.4 + 0.6³ = 0.432 + 0.216 = 0.648
```

With `n = 5`: `10 × 0.6³ × 0.4² + 5 × 0.6⁴ × 0.4 + 0.6⁵ = 0.346 + 0.259 + 0.078 = 0.683`. With 15 answers, 0.787. Voting helps, slowly, and each answer costs as much as the first.

Two conditions are needed (Condorcet, 1785):

- **Each answer must be right more often than wrong.** With `p = 0.45`, the majority of 5 is right only 40.7% of the time, worse than one answer. Voting amplifies whichever side is ahead.
- **The answers must not share their mistakes.** If, with chance `c`, all five answers are copies of one draw (the same misunderstanding every time), the result is `c × 0.6 + (1 − c) × 0.683`. With `c = 0.9` that is 0.608: almost nothing gained for five times the cost.

### Step 4. The loop as a Markov chain

Model the agent's loop with three working states, **Think → Act → Check**, and two ends, **Done** and **Give up**. After Check: Done with chance 0.50, back to Think with chance 0.45, Give up with chance 0.05.

Each round is 3 steps and ends the run with chance `0.50 + 0.05 = 0.55`. The number of rounds is a **geometric** number with mean `1 / 0.55 = 1.818`, so

```text
expected steps = 3 × 1.818 = 5.45
P(Done) = 0.50 / 0.55 = 0.909
```

The general method, which works for any loop, is the **fundamental matrix** `N = (I − Q)^(−1)`, where `Q` holds the chances of moving between working states. Its rows give the expected number of visits to each state; adding a row gives the expected steps, and `N × R` (with `R` the chances of moving to the ends) gives the chance of each end. `ex03` computes `N` and gets 5.4545 steps and 0.9091 for Done, and a simulation of 200,000 runs gives 5.4446 and 0.9097.

A **step budget** of 12 steps allows 4 rounds. The run is Done within them with chance

```text
0.50 × (1 + 0.45 + 0.45² + 0.45³) = 0.50 × 1.743 = 0.872
```

The budget costs 0.909 − 0.872 = 3.7 points of success, and in exchange no run takes more than 12 steps. The simulation gives 0.8725.

### Step 5. A growing history

Suppose the first request sends `s = 2,000` tokens (instructions and the task), and each step adds `t = 500` tokens (the tool's output and the model's reasoning). Step `i` sends `s + (i − 1)t` tokens, so a run of `n` steps sends

```text
total = n × s + t × (0 + 1 + … + (n − 1)) = n s + t n(n − 1)/2
```

For 40 steps: `40 × 2,000 + 500 × 40 × 39 / 2 = 80,000 + 390,000 = 470,000` tokens, against 135,000 for 20 steps. Twice the steps, 3.5 times the tokens; the `n²` term takes over.

A model's **context window** `W` caps one request: step `k` fits while `2,000 + (k − 1) × 500 ≤ W`. For `W = 200,000`, `k ≤ 397`. Long before that, cost and slowness bite. Replacing the history by a 1,000-token summary every 10 steps keeps each request at or below 7,500 tokens, and a 40-step run sends 200,000 tokens instead of 470,000 (`ex04`). A summary can drop a detail that a later step needed; that is the price.

## 8.4 Why it is true

**Multiplying chances.** For independent events, the chance that all happen is the product of their chances. "Independent" is the strong assumption here; real steps of a task can make related mistakes, in which case `p^n` can be too pessimistic or too optimistic.

**The shortcut.** `ln p = ln(1 − (1 − p)) ≈ −(1 − p)` when `1 − p` is small (the first term of the series `ln(1 − x) = −x − x²/2 − …`), so `p^n = e^(n ln p) ≈ e^(−n(1 − p))`.

**The retry formula** splits by the number of caught failures before the first right attempt: `j` caught failures then a right attempt has chance `((1 − p)d)^j × p`, for `j = 0, …, k − 1`. A geometric series `1 + x + x² + …` with `x < 1` adds up to `1 / (1 − x)`, which gives the ceiling.

**Voting** counts the right answers among `n`: a binomial number. The majority is right when more than `n/2` are. If `p > 1/2`, the fraction of right answers tends to `p` as `n` grows (law of large numbers), so the majority is right with chance tending to 1; if `p < 1/2`, to 0.

**The fundamental matrix.** `N = I + Q + Q² + Q³ + …`: entry `(i, j)` of `Q^m` is the chance of being in working state `j` after `m` moves from `i`, and adding over all `m` counts the expected visits. The series adds up to `(I − Q)^(−1)` because every run ends, so `Q^m` shrinks to 0.

**The sum of the history.** `0 + 1 + … + (n − 1) = n(n − 1)/2`: write the sum forwards and backwards and add, giving `n − 1` in each of `n` places.

## 8.5 See it in code

`ex01` compares the retry formula with 200,000 simulated tasks:

```text
d = 0.0, k = 1: formula 0.3585, simulated 0.3590
d = 0.9, k = 3: formula 0.8987, simulated 0.8995
```

`ex02` the voting sums and the shared-mistake model:

```text
p = 0.6: n=1: 0.600, n=3: 0.648, n=5: 0.683, n=9: 0.733, n=15: 0.787
c = 0.9: majority of 5 right 0.608 (simulated 0.606); one answer alone 0.600
```

`ex03` the fundamental matrix and the simulation:

```text
expected steps from Think: 5.4545   (by hand: 3 steps a round, 1 / 0.55 = 1.8182 rounds, 5.4545 steps)
average steps 5.4446, Done 0.9097, Done within 12 steps 0.8725
```

`ex04` the token totals, by a loop and by the formula:

```text
n = 40: loop   470,000  formula n s + t n(n-1)/2 =   470,000  per step   11,750
```

## 8.6 Where it breaks

- **Steps are not independent.** An agent that misreads the task early makes every later step "right" for the wrong goal. Then `p^n` is beside the point; checking the plan early is worth more than checking each step.
- **Checks are not free or perfect.** A test suite catches some mistakes and not others; a model asked to check its own work can share the mistake it is checking for (the shared-mistake case of step 3).
- **Answers are not just right or wrong.** When wrong answers differ from one another, the most common answer can be right even when fewer than half are (exercise 8): with 10 different wrong answers and `p = 0.4`, the most common of five answers is right 64% of the time.
- **Real chances are unknown.** The values 0.95, 0.9 and 0.6 are made up. Measuring them for a given agent and task, on enough tries, is the real work.
- **Costs per token** differ by model and change over time; this tutorial counts tokens, not money.
- **Irreversible actions.** A retry assumes a failed step can be undone. Sending an email or deleting data cannot be retried away; those steps need a person's approval, not arithmetic.

## 8.7 Exercises

Do 1 to 6 with a pencil. 7 needs a little care. 8 is code.

**E1. A task has 10 steps, each right 99% of the time. Find the chance it succeeds, exactly and with the shortcut.**

??? success "Answer"
    `0.99^10 = 0.904`. Shortcut: `e^(−10 × 0.01) = e^(−0.1) = 0.905`.

**E2. Each step must be at least how reliable for a 50-step task to succeed 80% of the time?**

??? success "Answer"
    `p = 0.8^(1/50) = e^(ln 0.8 / 50) = e^(−0.2231 / 50) = e^(−0.00446) = 0.99555`: about one error in 225 steps.

**E3. Steps are right 90% of the time, and a check catches 80% of mistakes, with up to 2 attempts. Find the chance one step ends well, and the ceiling with unlimited attempts.**

??? success "Answer"
    `(1 − p)d = 0.1 × 0.8 = 0.08`. Two attempts: `0.9 × (1 + 0.08) = 0.972`. Ceiling: `0.9 / (1 − 0.08) = 0.978`.

**E4. Answers are right with chance 0.7. Find the chance that the majority of 3 is right.**

??? success "Answer"
    `3 × 0.7² × 0.3 + 0.7³ = 0.441 + 0.343 = 0.784`.

**E5. In the loop of step 4, Check leads to Done with chance 0.3, back to Think with 0.6, and Give up with 0.1. Find the expected steps and the chance of Done.**

??? success "Answer"
    A round ends with chance 0.4, so `1 / 0.4 = 2.5` rounds, `3 × 2.5 = 7.5` steps. Done: `0.3 / 0.4 = 0.75`.

**E6. With `s = 1,000` and `t = 1,000`, how many tokens do 30 steps send? And 60?**

??? success "Answer"
    `30 × 1,000 + 1,000 × 30 × 29 / 2 = 30,000 + 435,000 = 465,000`. For 60: `60,000 + 1,000 × 60 × 59 / 2 = 60,000 + 1,770,000 = 1,830,000`, almost four times as many.

**E7. Why can asking a model to "check its own answer" help less than running a separate test, even if both catch the same share of mistakes on average?**

??? success "Answer"
    Step 2 assumes the check catches a mistake independently of how it was made. A model checking its own answer tends to miss exactly the mistakes it is prone to make, so its catches and its errors are related; the mistakes it misses are the common ones. A separate test (running the code, comparing with known data) fails in different ways, so its catches are closer to independent, which is what the formula needs.

**E8. (Code.) Five answers are each right with chance 0.4; wrong answers are spread over `m` different wrong values. Simulate how often the most common answer is right, for `m` = 1, 2, 10 and 100.**

??? success "Answer"
    See [ex05_plurality.py](src/08/ex05_plurality.py). The results ([output](src/08/ex05.out.txt)): 0.318, 0.448, 0.639 and 0.707. With one wrong value it is plain majority voting with `p < 1/2`, worse than one answer. With many different wrong values, the wrong answers split their votes, and the right answer, even at 40%, is usually the most common.

## 8.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: an agent or automation that failed on a long task, a check that saved it, or a bill that grew faster than expected, and which step explained it.)*

## 8.9 Further reading

On your own sites:

- [AI 8. How a language model picks the next word](../ai/08-How-a-Language-Model-Picks-the-Next-Word.md): the model inside the loop
- [NiFi 8. Back pressure, retries and partitions](../nifi/08-Back-Pressure-Retries-Partitions.md): retries with back-off in a data flow
- The [Math](https://math.akadian.ca/) site: probability, the binomial distribution and Markov chains

Original sources:

- Marquis de Condorcet, *Essai sur l'application de l'analyse à la probabilité des décisions rendues à la pluralité des voix*, 1785 (the jury theorem).
- J. G. Kemeny and J. L. Snell, *Finite Markov Chains*, 1960 (the fundamental matrix).
- S. Yao and others, "ReAct: Synergizing Reasoning and Acting in Language Models", *ICLR 2023* (the think, act, observe loop).
- X. Wang and others, "Self-Consistency Improves Chain of Thought Reasoning in Language Models", *ICLR 2023* (sampling several answers and taking the most common).

## Glossary

- **Agent**: a model in a loop that calls tools and decides its next step from the results.
- **Step**: one turn of the loop; here, right or wrong with some chance.
- **Independent events**: events where one happening does not change the chance of the other.
- **Check**: a test of a step's result that can send it back for another try.
- **Majority vote, plurality**: keeping the answer given by more than half, or simply the most common one.
- **Binomial number**: how many of `n` independent tries succeed.
- **Markov chain**: states with fixed chances of moving between them; **absorbing** states are ones you never leave.
- **Fundamental matrix**: `(I − Q)^(−1)`, the expected visits to each working state.
- **Step budget**: a limit on the number of steps of one run.
- **Token**: a word or piece of a word; the unit models read and are billed by.
- **Context window**: the most tokens a model can take in one request.
