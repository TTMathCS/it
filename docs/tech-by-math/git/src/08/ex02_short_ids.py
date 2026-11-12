# Tech by Math, Git tutorial 8: how many hex digits a short id needs. Part 1 counts shared prefixes among
# 200,000 real blob ids (the git formula, in hashlib); part 2 asks real git (2.43) for short ids in
# repositories of growing size; part 3 is git's own rule (object-name.c), in Python.
import hashlib
import os
import subprocess
import tempfile
from collections import Counter

N = 200_000
ids = [hashlib.sha1(b"blob %d\0" % len(d) + d).hexdigest()
       for d in (f"order {i}\n".encode() for i in range(N))]
print(f"Part 1. {N:,} blob ids; pairs that share their first k hex digits")
print(f"   {'k':>2} {'pairs measured':>15} {'predicted N(N-1)/2 / 16^k':>27}")
for k in range(4, 10):
    c = Counter(x[:k] for x in ids)
    pairs = sum(v * (v - 1) // 2 for v in c.values())
    pred = N * (N - 1) / 2 / 16 ** k
    print(f"   {k:>2} {pairs:>15,} {pred:>27,.1f}")


def git_rule(count):
    """object-name.c, repo_find_unique_abbrev_r: bits = msb(count) + 1, hex = ceil(bits / 2), at least 7."""
    bits = count.bit_length()       # = msb(count) + 1
    return max(7, (bits + 1) // 2)


ENV = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null", GIT_AUTHOR_NAME="Ada",
           GIT_AUTHOR_EMAIL="ada@example.com", GIT_COMMITTER_NAME="Ada", GIT_COMMITTER_EMAIL="ada@example.com",
           GIT_AUTHOR_DATE="2026-01-01T12:00:00+0000", GIT_COMMITTER_DATE="2026-01-01T12:00:00+0000")
print("\nPart 2. Real git: the length of 'git rev-parse --short HEAD' as the repository grows (after git gc)")
for files in (100, 20_000, 70_000):
    with tempfile.TemporaryDirectory() as d:
        run = lambda *a: subprocess.run(["git", *a], cwd=d, env=ENV, capture_output=True, check=True).stdout.decode()
        run("init", "-q")
        run("config", "gc.auto", "0")          # no automatic gc in the background; we run it ourselves
        for i in range(files):
            with open(os.path.join(d, f"f{i}.txt"), "w") as f:
                f.write(f"order {i}\n")
        run("add", ".")
        run("commit", "-q", "-m", "many files")
        run("gc", "-q")
        objects = int([l for l in run("count-objects", "-v").splitlines() if l.startswith("in-pack")][0].split()[1])
        short = run("rev-parse", "--short", "HEAD").strip()
        print(f"   {files:>6,} files -> {objects:>6,} objects: short id {short} ({len(short)} hex digits); rule gives {git_rule(objects)}")

print("\nPart 3. Git's rule for larger repositories")
for count in (1_000, 100_000, 1_000_000, 10_000_000, 100_000_000):
    print(f"   {count:>11,} objects: {count.bit_length()} bits -> {git_rule(count)} hex digits")
