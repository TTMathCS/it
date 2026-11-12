# 8. Names from contents: hashes and the commit graph

*Change one letter in one file, commit, and the commit gets a completely new 40-character name. So do the folders above the file, and nothing else does. Short ids are 7 characters in a small project and 12 in a large one. Two files could in principle get the same name, yet nobody worries about it. A branch is "2 ahead, 2 behind", and a merge knows where to start. All of this follows from one idea: git names everything by a hash of its contents. This tutorial works through it with real git, and shows that every id can be recomputed from its definition.*

!!! abstract "In this tutorial"
    **You will learn:**

    - how git names a file: `SHA-1("blob <size>\0" + bytes)`, and why the same file has the same id on every computer
    - why one changed byte changes the file's id, every folder above it and the commit, and nothing else (a Merkle tree)
    - the birthday count: how many pairs of ids share their first `k` hex digits, and git's rule for the length of short ids
    - the difference between an accidental collision (never seen) and a constructed one (SHA-1, 2017), and what git did about it
    - branches as sets of ancestors: `main..feature` is a set difference, "ahead/behind" are two set sizes, and the merge base is the newest common ancestor
    - the three-way merge rule, line region by line region, and why it needs the base

    **You need:** counting pairs (`N(N − 1)/2`), powers of 2 and 16, and sets (intersection, difference). No cryptography: the hash is used as a black box with two properties, stated in 8.2.

    **How to learn from it:** read 8.1 to 8.3, close the page, redo the examples of 8.3 on paper, then try the exercises in 8.7 before opening any answer. Plan about two hours.

**About the examples.** Every git result came from git 2.43.0, run by the scripts next to this page in throwaway repositories, with fixed author names and dates so that the ids come out the same on every run. Each id is also recomputed from its definition with Python's `hashlib`, and the two agree. Git's rule for short ids is quoted from its source code (`object-name.c`, git 2.43.0). The scripts and their full output: [ex01_objects.py](src/08/ex01_objects.py) ([output](src/08/ex01.out.txt)), [ex02_short_ids.py](src/08/ex02_short_ids.py) ([output](src/08/ex02.out.txt)), [ex03_graph.py](src/08/ex03_graph.py) ([output](src/08/ex03.out.txt)), and the answer to exercise E7, [ex04_tree.py](src/08/ex04_tree.py) ([output](src/08/ex04.out.txt)).

## 8.1 The question

A small repository has three files: `README`, `docs/prices.txt` and `docs/guide/start.txt`. You change `step 2` to `step 3` in the last one and commit.

1. Which of git's stored objects get new ids, and which are reused?
2. Could two different files ever get the same id? How likely is that, and what would it take to do it on purpose?
3. Why does git print `abc2fb5d` (8 characters) for a commit in one repository and `405084e` (7) in another?
4. Your branch `feature` is "2 ahead, 2 behind" `main`. Which commits are those, and from which commit does a merge start?

## 8.2 The idea: the name of a thing is a hash of the thing

Git stores everything as **objects** in a database, under names called **object ids**. There are four kinds:

- a **blob**: the bytes of one file (no name, no date);
- a **tree**: one folder, a list of entries `(mode, type, id, name)`, each pointing to a blob or another tree;
- a **commit**: the id of the root tree, the ids of the parent commits, an author, a committer, dates and a message;
- a **tag**: a named pointer to another object (not used in this tutorial).

The id of an object is

```text
id = SHA-1( "<type> <size in bytes>\0" + contents )
```

written as 40 hex digits (160 bits). `\0` is a single zero byte. A repository created with `git init --object-format=sha256` uses SHA-256 instead, with 64 hex digits (`ex01` checks both).

This tutorial uses only two properties of the hash function:

1. **It is a function.** The same bytes give the same id, on every computer, forever.
2. **It looks random.** A tiny change in the input gives an unrelated output, and nobody can find two inputs with the same output except by trying (or, for SHA-1, with the special attack of step 4).

Because the name is computed from the contents, the database is **content-addressed**: to look something up you need its contents' fingerprint, and if the stored bytes ever got corrupted, recomputing the hash would reveal it.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 230" role="img" aria-label="A commit points to a root tree, which points to the blob README and the tree docs; docs points to the blob prices.txt and the tree guide; guide points to the blob start.txt. The changed blob start.txt and the trees guide, docs and root, and the commit, are drawn bold: they get new ids. README and prices.txt keep theirs.">
<g font-size="13" fill="currentColor">
<g fill="none" stroke="currentColor">
<rect x="20" y="20" width="110" height="34" rx="5" stroke-width="2.5"/>
<rect x="20" y="100" width="110" height="34" rx="5" stroke-width="2.5"/>
<rect x="190" y="60" width="130" height="34" rx="5"/>
<rect x="190" y="140" width="110" height="34" rx="5" stroke-width="2.5"/>
<rect x="360" y="100" width="150" height="34" rx="5"/>
<rect x="360" y="180" width="120" height="34" rx="5" stroke-width="2.5"/>
<rect x="520" y="180" width="110" height="34" rx="5" stroke-width="2.5"/>
<line x1="75" y1="54" x2="75" y2="100"/>
<line x1="130" y1="110" x2="190" y2="80"/><line x1="130" y1="124" x2="190" y2="154"/>
<line x1="300" y1="150" x2="360" y2="120"/><line x1="300" y1="164" x2="360" y2="194"/>
<line x1="480" y1="197" x2="520" y2="197"/>
</g>
<text x="32" y="42" font-weight="bold">commit</text>
<text x="32" y="122" font-weight="bold">tree /</text>
<text x="200" y="82">blob README</text>
<text x="200" y="162" font-weight="bold">tree docs</text>
<text x="370" y="122">blob prices.txt</text>
<text x="370" y="202" font-weight="bold">tree guide</text>
<text x="528" y="202" font-weight="bold">start.txt</text>
<text x="190" y="30">bold: new id after the edit</text>
</g>
</svg>
<figcaption>Figure 8.1. The objects of one commit. Editing <code>start.txt</code> changes its blob's id, so the tree that lists it changes, and so on up to the commit (bold). The other two blobs are reused unchanged.</figcaption>
</figure>

## 8.3 The math by hand

### Step 1. A file's id

The file `hello` followed by a newline is 6 bytes: `h e l l o \n`. Git hashes

```text
"blob 6" + zero byte + "hello\n"      (13 bytes in all)
```

and gets `ce013625030ba8dba906f756967f9e9ca394464a`. The SHA-1 computation itself is too long for a pencil; the input is not, and that is the part to know. Compare (`ex01`):

| contents | header | id |
| --- | --- | --- |
| (empty file) | `blob 0` | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` |
| `hello\n` | `blob 6` | `ce013625030ba8dba906f756967f9e9ca394464a` |
| `Hello\n` | `blob 6` | `e965047ad7c57865823c7d992b1d046ea66edf78` |
| `hello!\n` | `blob 7` | `4effa19f4f75f846c3229b9dbdbad14eff362f32` |

One capital letter, and the id shares nothing with the old one. The file's name and date are not in the blob, so two files with the same bytes, anywhere, in any repository, have the same blob id and are stored once.

### Step 2. One byte up the tree

A tree's contents are its list of entries, and each entry contains the id of what it points to. In the example, `docs/guide/start.txt` changes, so:

1. its blob id changes;
2. the tree `docs/guide` lists that id, so its contents change, so its id changes;
3. the tree `docs` lists the id of `docs/guide`: new id;
4. the root tree lists the id of `docs`: new id;
5. the commit names the root tree: new id.

`README` and `docs/prices.txt` have the same bytes as before, so their ids are unchanged, and the new trees simply point to the old blobs. Measured (`ex01`):

| object | before | after |
| --- | --- | --- |
| commit | `cf1fd4b1dda3` | `5593696f4a82` (changed) |
| tree `/` | `1d408b8d34bc` | `d6c091397058` (changed) |
| tree `docs` | `a59e1955b52e` | `269d5682f356` (changed) |
| tree `docs/guide` | `7b2f24db034b` | `86a5bd2554a4` (changed) |
| blob `README` | `ea2ae6d3d7f8` | `ea2ae6d3d7f8` |
| blob `docs/prices.txt` | `e5551ac0db1e` | `e5551ac0db1e` |
| blob `docs/guide/start.txt` | `a84c222b8d6b` | `d664f07580a1` (changed) |

A change to a file at depth `d` (here 2 folders deep) creates `d + 3` new objects: the blob, `d + 1` trees, the commit. A repository with a million files still only adds a handful of objects per small commit.

A tree of hashes like this is a **Merkle tree** (after Ralph Merkle, 1987). It has two consequences. First, to compare two snapshots, git compares the root tree ids; if equal, the snapshots are identical. If not, it opens only the entries whose ids differ: the cost depends on what changed, not on the size of the project. Second, because each commit contains its parents' ids, **a commit id pins down the whole history behind it**: change anything in any old commit and every id after it changes.

### Step 3. How many digits are enough: the birthday count

Ids are 160 bits, but people type short prefixes such as `5593696`. How long must a prefix be?

Take `N` objects and look at their first `k` hex digits, `16^k` possible values. A pair of objects shares a prefix with probability `1 / 16^k`, and there are `N(N − 1)/2` pairs, so the expected number of pairs sharing a prefix is

```text
pairs ≈ N(N − 1)/2 / 16^k
```

This is the **birthday count**: it grows with `N²`, not with `N`, which is why collisions appear sooner than intuition says. For `N = 200,000` ids (`ex02`):

| k (hex digits) | pairs measured | predicted |
| ---: | ---: | ---: |
| 4 | 305,580 | 305,174.3 |
| 5 | 19,035 | 19,073.4 |
| 6 | 1,165 | 1,192.1 |
| 7 | 86 | 74.5 |
| 8 | 4 | 4.7 |
| 9 | 1 | 0.3 |

Git's rule (`object-name.c`) picks the default short length from the number of objects `N`:

```text
bits   = msb(N) + 1          (the number of binary digits of N)
digits = ⌈bits / 2⌉, but at least 7
```

Why halve? `N < 2^bits`, so `N² < 2^(2 × bits)`. With `digits ≥ bits / 2` hex digits, `16^digits = 2^(4 × digits) ≥ 2^(2 × bits) > N²`, so the expected number of colliding pairs, about `N² / 2 / 16^digits`, is below one half. Git's comment says the same in words: "we have on the order of 2^len objects, which expects a collision at 2^(len/2)".

| objects N | bits | short id length |
| ---: | ---: | ---: |
| 1,000 | 10 | 7 (the minimum) |
| 20,002 | 15 | 8 |
| 70,002 | 17 | 9 |
| 1,000,000 | 20 | 10 |
| 10,000,000 | 24 | 12 |

The rows for 20,002 and 70,002 objects were measured with real git: `git rev-parse --short HEAD` printed 8 and 9 digits (`ex02`). Git also checks: if the chosen prefix happens to be shared, it prints more digits. But a prefix that is unique today can become ambiguous as the project grows, so scripts and documents should keep full ids.

For full ids the same formula is reassuring: a billion objects give `10^18 / 2 / 2^160 ≈ 3 × 10^-31` expected colliding pairs.

### Step 4. Accidents against attacks

Step 3 is about accidents: ids of ordinary files. An attacker who *tries* to make two files with one id faces the same birthday count: with `2^80` attempts there are about `2^159` pairs, each colliding with probability `2^-160`, so about half a colliding pair is expected. `2^80` is about `1.2 × 10^24` hash computations, out of reach.

In 2017, Marc Stevens and colleagues published the first SHA-1 collision, two different PDF files with the same SHA-1 ("SHAttered"), using a weakness in SHA-1's design: about `2^63` SHA-1 computations instead of `2^80`, large but possible. Git's answer came the same year: git 2.13 made the "detect attempt to create collisions" variant of SHA-1 by Marc Stevens and Dan Shumow its default (git's release notes). It computes SHA-1 normally but refuses input that shows the traces of this kind of attack. The longer-term answer is SHA-256 repositories (`--object-format=sha256`). The [Retired hashes](https://cryptography.akadian.ca/07-hash/Retired/) page of the Cryptography site tells the SHA-1 story in full.

### Step 5. Branches as sets

A commit's **ancestors** are the commit itself, its parents, their parents, and so on. Write `anc(X)` for that set. A branch name is just a pointer to one commit, so a branch "contains" exactly `anc(tip)`.

The example history (`ex03`): `A`, `B` on `main`; `feature` branches from `B` and gets `D`, `E`; `main` gets `C`, `F`.

```text
A ─ B ─ C ─ F      main
     \
      D ─ E        feature
```

- `anc(main) = {A, B, C, F}`, `anc(feature) = {A, B, D, E}`.
- **Common ancestors**: `anc(main) ∩ anc(feature) = {A, B}`.
- **Merge base**: a common ancestor that is not an ancestor of another common ancestor. `A` is an ancestor of `B`, so the merge base is `B`.
- `git log main..feature` shows `anc(feature) \ anc(main) = {D, E}`: "feature is 2 ahead".
- `git log feature..main` shows `anc(main) \ anc(feature) = {C, F}`: "2 behind".

Every one of these was printed by real git and matches (`ex03`). The two-dot notation `X..Y` is exactly a set difference, "in `Y` but not in `X`".

### Step 6. The three-way merge rule

To merge, git compares three versions of each file: the merge **base**, **ours** and **theirs**. For each region of lines:

| base vs ours | base vs theirs | result |
| --- | --- | --- |
| same | same | base |
| changed | same | ours |
| same | changed | theirs |
| changed | changed, to the same text | that text |
| changed | changed, differently | **conflict** |

Worked (`ex03`, with `git merge-file`): an 11-line file where ours changes line 2 (`green` to `GREEN`), theirs changes line 5 (`blue` to `BLUE`), both change line 8 to `PINK`, and ours changes line 11 to `grey` while theirs changes it to `silver`. The result takes `GREEN`, `BLUE` and `PINK` automatically and marks one conflict, line 11, with `<<<<<<<`, `=======` and `>>>>>>>`. Git returns exit code 1, the number of conflicts.

Why the base? Looking at ours (`GREEN`) and theirs (`green`) alone, you cannot tell which side changed the line. The base says it was `green`, so ours changed it and ours wins. That is why the merge base of step 5 matters.

## 8.4 Why it is true

**Same contents, same id.** The id is a function of the header and contents only; the header is a function of the type and size. So identical contents give identical ids, which is what makes de-duplication automatic.

**Changes travel up, and only up.** By induction on depth: an object's contents contain the ids of the objects it points to, and nothing about the objects pointing to it. A change to an object changes its id (assuming no collision), so it changes the contents of every object that points to it, and so on up to the commit. Objects not on the path from the change to the root have unchanged contents, so unchanged ids.

**The birthday count.** For each of the `N(N − 1)/2` pairs, let `X` be 1 if the pair shares its first `k` digits and 0 otherwise. Each `X` is 1 with probability `1 / 16^k` if the hash looks random. The expected number of shared pairs is the sum of the expectations, `N(N − 1)/2 / 16^k`, by linearity of expectation (which needs no independence). The measured counts in step 3 match this closely, as one random sample should.

**Branch arithmetic.** `X..Y` is defined by git as the commits reachable from `Y` but not from `X`, which is the set difference of step 5. There can be more than one merge base: in a "criss-cross" history where two branches have merged each other, two common ancestors may each not be an ancestor of the other. `git merge-base --all` lists them, and git's merge then first merges those bases into a temporary base.

**The merge rule.** The table of step 6 is the definition. What it guarantees: a change made on only one side is never lost, and a conflict is raised whenever both sides changed the same region differently. What it does not guarantee: that the merged file works.

## 8.5 See it in git

`ex01` recomputes a commit id from git's own bytes: `git cat-file commit HEAD` gives the 197-byte commit text

```text
tree d6c0913970589432f4ab74acf8b614dac9fda8cc
parent cf1fd4b1dda3aa28e634b40217d1935b1154b974
author Ada <ada@example.com> 1767268800 +0000
committer Ada <ada@example.com> 1767268800 +0000

second
```

and `SHA-1("commit 197\0" + those bytes) = 5593696f4a824fd4961ce4fe1ece7cf64f37ba6b`, exactly what `git rev-parse HEAD` prints. The `parent` line is how the commit pins its history; the dates are part of the contents, which is why the same change committed a second later gets a different id.

`ex02` measured the short ids of step 3 and the birthday table. `ex03` printed the graph of step 5:

```text
* 81e7a9f F
* fef87f9 C
| * 6596867 E
| * bac419f D
|/
* e881efc B
* a184a0f A
```

with `git merge-base main feature` = `B` and `git rev-list --left-right --count main...feature` = `2 2`.

## 8.6 Where it breaks

- **Neighbouring lines conflict.** Git merges regions, not single lines. In `ex03` part 3, ours changes line 2 and theirs line 3 of a 4-line file; git reports a conflict covering both, although no line was changed twice. Changes need at least one unchanged line between them to merge cleanly.
- **A clean merge is not a correct program.** One side renames a function, the other adds a new call to the old name, in a different file: no conflict, broken build. The rule of step 6 knows lines, not meaning.
- **Short ids age.** Once a repository passes 2^14 = 16,384 objects, git starts printing 8 digits (step 3), and a 7-digit id written in an old ticket may by then match more than one object. Write full ids anywhere they must last.
- **Renames are not stored.** A tree records names and blob ids; git *guesses* renames afterwards by comparing contents (`-M`, similarity 50% by default in `git diff`). A file both renamed and heavily edited may not be recognised.
- **SHA-1 is weakened.** Step 4. Collision detection blocks the known attack; SHA-256 repositories avoid the question. A repository uses one format; moving an existing project to the other is a separate conversion.
- **Signing is separate.** An id proves that contents match the id, not who made them. That is what signed commits and tags are for.

## 8.7 Exercises

Do 1 to 6 with a pencil. 7 is code.

**E1. What bytes does git hash for a file containing `Mars` and a newline? What is the size in the header?**

??? success "Answer"
    `Mars\n` is 5 bytes, so git hashes `blob 5`, a zero byte, then `Mars\n`: 12 bytes in all. The result is `2293932e2b93eb644be961c65019f828309366bc` (computed with `hashlib`; `git hash-object` gives the same).

**E2. You edit `src/app/web/api/handlers.py` and commit. How many new objects does the commit create? Which existing trees are reused?**

??? success "Answer"
    The file is 4 folders deep (`src`, `app`, `web`, `api`): 1 blob, 5 trees (root, `src`, `src/app`, `src/app/web`, `src/app/web/api`) and 1 commit, so 7 objects (`d + 3` with `d = 4`). Every other tree and blob, in every other folder, is reused as it is.

**E3. A repository has 1,000,000 objects. About how many pairs share their first 7 hex digits? Their first 10?**

??? success "Answer"
    `N(N − 1)/2 ≈ 5 × 10^11` pairs. With 7 digits, `16^7 = 268,435,456`: about 1,863 shared pairs, so a 7-digit id would often be ambiguous. With 10 digits, `16^10 ≈ 1.1 × 10^12`: about 0.45. Git's rule gives 10 for a million objects (step 3), for exactly this reason.

**E4. Using git's rule, how many hex digits does a short id get with 3,000,000 objects? With 40,000?**

??? success "Answer"
    `2^21 = 2,097,152 ≤ 3,000,000 < 2^22`, so 22 bits and `⌈22/2⌉ = 11` digits. `2^15 = 32,768 ≤ 40,000 < 2^16`, so 16 bits and 8 digits.

**E5. History: `A ─ B ─ C ─ D` on `main`; `topic` branches from `C` with `X`, `Y`; then `main` gets `E`. What are `main..topic`, `topic..main` and the merge base? After `topic` is merged into `main` with a merge commit `M`, what is `main..topic`?**

??? success "Answer"
    `topic` branches from `C`, so `anc(topic) = {A, B, C, X, Y}` and `anc(main) = {A, B, C, D, E}`. `main..topic = {X, Y}`, `topic..main = {D, E}`, merge base `C`. After the merge, `M` has parents `E` and `Y`, so `anc(main) ⊇ {X, Y}` and `main..topic` is empty: topic is "0 ahead".

**E6. Base `a b c d e f g` (one word per line, 7 lines). Ours: `a B c d e f G`. Theirs: `a b c D e f h`. What does the merge produce?**

??? success "Answer"
    Line 2: only ours changed: `B`. Line 4: only theirs: `D`. Line 7: both changed, differently (`G` against `h`): conflict. Lines 2, 4 and 7 are separated by unchanged lines, so the result is `a B c D e f` and a conflict on the last line; `git merge-file` agrees (`ex03`, part 4).

**E7. (Code.) A tree is stored as, for each entry sorted by name, `<mode> <name>\0` followed by the 20 raw bytes of the id; its id is SHA-1 of `tree <size>\0` plus that. Using the ids printed in `ex01.out.txt` (`README` and `docs`), compute the root tree id of the second commit and compare with git's.**

??? success "Answer"
    ```python
    import hashlib

    def tree_id(entries):
        body = b"".join(mode.encode() + b" " + name.encode() + b"\0" + bytes.fromhex(oid)
                        for mode, name, oid in entries)
        return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()

    print(tree_id([("100644", "README", "ea2ae6d3d7f82720f73a3ef28c653d220772a40e"),
                   ("40000", "docs", "269d5682f356e77b9b0bff0b7b8414a895b74be4")]))
    ```

    It prints `d6c0913970589432f4ab74acf8b614dac9fda8cc`, the `tree` line of the second commit. Note the folder mode `40000`: `git cat-file -p` displays it as `040000`, but the stored bytes have no leading zero. ([ex04_tree.py](src/08/ex04_tree.py), [output](src/08/ex04.out.txt).)

## 8.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a merge that surprised you, an ambiguous short id, or a history question that the sets of step 5 answer.)*

## 8.9 Further reading

On your own sites:

- Hash functions: [SHA-2](https://cryptography.akadian.ca/07-hash/SHA-2/) and [Retired hashes](https://cryptography.akadian.ca/07-hash/Retired/) on the Cryptography site
- Hashing in general: [Algorithms, ch 7. Searching and hashing](https://cs.akadian.ca/books/algorithms/07-Searching-and-Hashing/)
- Linearity of expectation: [Probability, ch 6. Expectation and variance](https://math.akadian.ca/books/probability/06-Expectation-and-Variance.html)

Original sources:

- S. Chacon and B. Straub, *Pro Git*, 2nd edition, chapter 10 "Git Internals" (free at git-scm.com). The object format.
- R. C. Merkle, "A Digital Signature Based on a Conventional Encryption Function", *CRYPTO '87*. Hash trees.
- M. Stevens, E. Bursztein, P. Karpman, A. Albertini and Y. Markov, "The first collision for full SHA-1", *CRYPTO 2017*.
- Git 2.13.0 release notes (`Documentation/RelNotes/2.13.0.txt`): collision-detecting SHA-1 made the default.
- Git 2.43.0 source, `object-name.c` (`repo_find_unique_abbrev_r`) and `object-name.h` (`FALLBACK_DEFAULT_ABBREV 7`), at [github.com/git/git](https://github.com/git/git/tree/v2.43.0).

## Glossary

- **Object**: anything git stores: a blob, tree, commit or tag.
- **Object id**: the hash of an object's header and contents, 40 hex digits for SHA-1.
- **Blob**: a file's bytes.
- **Tree**: a folder: a list of names with the ids of their blobs and trees.
- **Commit**: a snapshot (root tree id) plus parent ids, author, dates and message.
- **Content-addressed**: stored under a name computed from the contents.
- **Merkle tree**: a tree in which each node's name is a hash of its children's names.
- **Birthday count**: the expected number of pairs sharing a value, `N(N − 1)/2` divided by the number of possible values.
- **Ancestors**: a commit and everything reachable through its parents.
- **Merge base**: the newest common ancestor of two commits, where a three-way merge starts.
- **Three-way merge**: combining ours and theirs by comparing each with the base.
