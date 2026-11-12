# Tech by Math, Git tutorial 8: an object's name is a hash of its contents. Every id below is computed
# twice: by the formula in Python (hashlib) and by real git (2.43). Fixed dates make the commit ids repeatable.
import hashlib
import os
import subprocess
import tempfile

ENV = dict(os.environ, GIT_AUTHOR_NAME="Ada", GIT_AUTHOR_EMAIL="ada@example.com", GIT_COMMITTER_NAME="Ada",
           GIT_COMMITTER_EMAIL="ada@example.com", GIT_AUTHOR_DATE="2026-01-01T12:00:00+0000",
           GIT_COMMITTER_DATE="2026-01-01T12:00:00+0000", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")


def git(*args, cwd, data=None):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, input=data, capture_output=True, check=True).stdout


def blob_id(data, algo="sha1"):
    return hashlib.new(algo, b"blob %d\0" % len(data) + data).hexdigest()


print("Part 1. A blob's id is SHA-1 of 'blob <size>\\0' followed by the bytes")
with tempfile.TemporaryDirectory() as d:
    git("init", "-q", cwd=d)
    for data in (b"", b"hello\n", b"hello!\n", b"Hello\n"):
        by_git = git("hash-object", "--stdin", cwd=d, data=data).decode().strip()
        print(f"   {data!r:<11} header {('blob %d' % len(data))!r:<9} formula {blob_id(data)}  git {by_git}  {'same' if by_git == blob_id(data) else 'DIFFERENT'}")
with tempfile.TemporaryDirectory() as d:
    git("init", "-q", "--object-format=sha256", cwd=d)
    by_git = git("hash-object", "--stdin", cwd=d, data=b"hello\n").decode().strip()
    print(f"   in a SHA-256 repository, b'hello\\n': formula {blob_id(b'hello\n', 'sha256')}")
    print(f"   {'':<43}git {by_git}")

print("\nPart 2. Change one byte deep in the tree: which object ids change?")
with tempfile.TemporaryDirectory() as d:
    git("init", "-q", "-b", "main", cwd=d)
    os.makedirs(os.path.join(d, "docs", "guide"))
    files = {"README": b"Mars shop\n", "docs/prices.txt": b"rock 5\nsand 2\n", "docs/guide/start.txt": b"step 1\nstep 2\n"}
    for p, b in files.items():
        with open(os.path.join(d, p), "wb") as f:
            f.write(b)
    git("add", ".", cwd=d)
    git("commit", "-q", "-m", "first", cwd=d)

    def ids():
        out = {"commit": git("rev-parse", "HEAD", cwd=d).decode().strip()}
        for path in ("", "docs", "docs/guide"):
            out[f"tree /{path}"] = git("rev-parse", f"HEAD:{path}", cwd=d).decode().strip()
        for path in files:
            out[f"blob {path}"] = git("rev-parse", f"HEAD:{path}", cwd=d).decode().strip()
        return out

    before = ids()
    with open(os.path.join(d, "docs/guide/start.txt"), "wb") as f:
        f.write(b"step 1\nstep 3\n")           # one byte: 2 -> 3
    git("commit", "-q", "-a", "-m", "second", cwd=d)
    after = ids()
    for k in before:
        print(f"   {k:<26} {before[k][:12]} -> {after[k][:12]}   {'CHANGED' if before[k] != after[k] else 'same'}")
    print("\n   the root tree, as git stores it (git cat-file -p HEAD^{tree}):")
    for line in git("cat-file", "-p", "HEAD^{tree}", cwd=d).decode().splitlines():
        print("      " + line)
    print("   the second commit (git cat-file -p HEAD):")
    for line in git("cat-file", "-p", "HEAD", cwd=d).decode().splitlines():
        print("      " + line)
    raw = git("cat-file", "commit", "HEAD", cwd=d)
    print(f"   SHA-1 of 'commit {len(raw)}\\0' + those {len(raw)} bytes = {hashlib.sha1(b'commit %d\0' % len(raw) + raw).hexdigest()}")
    print(f"   git rev-parse HEAD                     = {after['commit']}")
