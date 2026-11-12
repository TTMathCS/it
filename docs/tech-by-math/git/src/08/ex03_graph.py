# Tech by Math, Git tutorial 8: the commit graph as sets of ancestors, and the three-way merge rule.
# Real git (2.43) in a throwaway repository; fixed dates make the ids repeatable.
import os
import subprocess
import tempfile

ENV = dict(os.environ, GIT_AUTHOR_NAME="Ada", GIT_AUTHOR_EMAIL="ada@example.com", GIT_COMMITTER_NAME="Ada",
           GIT_COMMITTER_EMAIL="ada@example.com", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")


def make(d):
    tick = [0]

    def git(*args, check=True):
        tick[0] += 1
        env = dict(ENV, GIT_AUTHOR_DATE=f"2026-01-01T12:{tick[0] // 60:02d}:{tick[0] % 60:02d}+0000")
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
        p = subprocess.run(["git", *args], cwd=d, env=env, capture_output=True, text=True)
        if check and p.returncode:
            raise RuntimeError(p.stderr)
        return p.stdout.strip()
    return git


def commit(git, d, name, path="notes.txt", text=None):
    with open(os.path.join(d, path), "a") as f:
        f.write(text or f"{name}\n")
    git("add", path)
    git("commit", "-q", "-m", name)
    return git("rev-parse", "--short=7", "HEAD")


with tempfile.TemporaryDirectory() as d:
    git = make(d)
    git("init", "-q", "-b", "main")
    names = {}
    for n in "ABC":
        names[n] = commit(git, d, n)
    git("checkout", "-q", "-b", "feature", "HEAD~1")             # branch from B
    for n in "DE":
        names[n] = commit(git, d, n, path="feature.txt")
    git("checkout", "-q", "main")
    names["F"] = commit(git, d, "F")
    label = {v: k for k, v in names.items()}

    def labels(revs):
        return sorted(label[r[:7]] for r in revs.split())

    print("Part 1. History: A - B - C - F on main, and B - D - E on feature")
    print("   git log --graph --oneline --all:")
    for line in git("log", "--graph", "--format=%h %s", "--all").splitlines():
        print("      " + line)
    anc_main = labels(git("rev-list", "main"))
    anc_feat = labels(git("rev-list", "feature"))
    print(f"   ancestors of main    (git rev-list main):    {anc_main}")
    print(f"   ancestors of feature (git rev-list feature): {anc_feat}")
    print(f"   common ancestors: {sorted(set(anc_main) & set(anc_feat))}")
    print(f"   git merge-base main feature: {label[git('merge-base', 'main', 'feature')[:7]]}")
    print(f"   git rev-list main..feature (in feature, not in main): {labels(git('rev-list', 'main..feature'))}")
    print(f"   git rev-list feature..main (in main, not in feature): {labels(git('rev-list', 'feature..main'))}")
    print(f"   git rev-list --left-right --count main...feature: {git('rev-list', '--left-right', '--count', 'main...feature')}  (main ahead, feature ahead)")



def merge3(title, base, ours, theirs):
    print(title)
    with tempfile.TemporaryDirectory() as d:
        for n, t in (("ours", ours), ("base", base), ("theirs", theirs)):
            with open(os.path.join(d, n), "w") as f:
                f.write("\n".join(t) + "\n")
        p = subprocess.run(["git", "merge-file", "-p", "ours", "base", "theirs"], cwd=d, capture_output=True, text=True, env=ENV)
    print(f"   {'line':<5} {'base':<7} {'ours':<7} {'theirs':<7}")
    for i, (b, o, t) in enumerate(zip(base, ours, theirs), 1):
        print(f"   {i:<5} {b:<7} {o:<7} {t:<7}")
    print(f"   result (exit code {p.returncode} = number of conflicts):")
    for line in p.stdout.splitlines():
        print("      " + line)


base = ["red", "green", "a", "b", "blue", "c", "d", "pink", "e", "f", "white"]
ours = ["red", "GREEN", "a", "b", "blue", "c", "d", "PINK", "e", "f", "grey"]
theirs = ["red", "green", "a", "b", "BLUE", "c", "d", "PINK", "e", "f", "silver"]
merge3("\nPart 2. Three-way merge, line by line (git merge-file ours base theirs); changes two lines apart", base, ours, theirs)
merge3("\nPart 3. The same kind of edits on neighbouring lines", ["red", "green", "blue", "black"],
       ["red", "GREEN", "blue", "black"], ["red", "green", "BLUE", "black"])
merge3("\nPart 4. Exercise E6: changes one unchanged line apart", list("abcdefg"), list("aBcdefG"), list("abcDefh"))
