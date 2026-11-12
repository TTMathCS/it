# E8: five answers, each right with chance 0.4; wrong answers are spread over
# 10 different wrong values. How often is the most common answer the right one?
import random
from collections import Counter

rng = random.Random(11)
def run(p_right, n, n_wrong, trials=200_000):
    wins = 0
    for _ in range(trials):
        answers = ["right" if rng.random() < p_right else f"wrong{rng.randrange(n_wrong)}" for _ in range(n)]
        c = Counter(answers)
        top = max(c.values())
        leaders = [a for a, k in c.items() if k == top]
        wins += rng.choice(leaders) == "right"      # a tie is broken at random
    return wins / trials
for n_wrong in (1, 2, 10, 100):
    print(f"   5 answers, p = 0.4, {n_wrong:>3} possible wrong answers: most common answer right {run(0.4, 5, n_wrong):.3f}")
