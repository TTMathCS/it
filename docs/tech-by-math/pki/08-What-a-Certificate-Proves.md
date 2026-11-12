# 8. What a certificate proves: signatures and chains

*Your browser trusts `shop.example` because of three certificates it checked in a few milliseconds. What exactly did it check, and why can nobody else make a certificate that passes? This tutorial does RSA with numbers small enough for a pencil, then shows that a real 2048-bit signature made by OpenSSL is the very same arithmetic, `s^e mod n`, with one line of Python. Then it builds a toy chain of certificates and breaks it six different ways to see which check catches each.*

!!! abstract "In this tutorial"
    **You will learn:**

    - RSA in four lines: `n = p × q`, `e × d ≡ 1`, sign `s = h^d mod n`, verify `s^e mod n = h`, worked with `p = 61`, `q = 53`
    - how to find `d` with Euclid's algorithm, by hand
    - square-and-multiply, and why verifying (17 multiplications) is so much cheaper than signing (thousands)
    - what is really inside a real RSA-2048 signature: `00 01 ff … ff 00`, a fixed label, and the SHA-256 of the message
    - a certificate as "a public key and a name, signed by someone else", and a chain as signatures checked one after another up to a root you already trust
    - which mistakes each check catches: wrong name, expired, missing intermediate, tampered, signed by the wrong key, unknown root

    **You need:** remainders (`17 mod 5 = 2`), powers, and patience with one long division. The [Cryptography site's book](https://cryptography.akadian.ca/book/) covers the number theory in depth; here it is used, not proved.

    **How to learn from it:** read 8.1 to 8.3, close the page, redo the toy RSA of 8.3 on paper, then try the exercises in 8.7 before opening any answer. Plan about two and a half hours.

**About the examples.** The toy RSA is plain Python. The real signatures are made by OpenSSL 3.0.13 and checked by `openssl` and by hand in Python. The chain is built with Python's `cryptography` package and checked by `openssl verify`, with the date fixed by `-attime` so that "expired" can be tested without waiting. Keys are generated fresh on each run, so long numbers in the output differ from run to run; the structure and every OK or error do not. The scripts and their full output: [ex01_toy_rsa.py](src/08/ex01_toy_rsa.py) ([output](src/08/ex01.out.txt)), [ex02_real_rsa.py](src/08/ex02_real_rsa.py) ([output](src/08/ex02.out.txt)), [ex03_chain.py](src/08/ex03_chain.py) ([output](src/08/ex03.out.txt)), [ex04_speed.py](src/08/ex04_speed.py) ([output](src/08/ex04.out.txt)), and the answer to exercise E7, [ex05_all_h.py](src/08/ex05_all_h.py).

## 8.1 The question

A browser connects to `shop.example`. The server sends two certificates: one for `shop.example`, issued by "Toy Issuing CA", and one for "Toy Issuing CA", issued by "Toy Root CA". The browser already has "Toy Root CA" in its list of trusted roots.

1. What is a signature, as a number, and how is it checked?
2. Why can the browser check a signature quickly, while nobody without the private key can make one?
3. What does the browser check in the chain, and what goes wrong if any one piece is missing or altered?

## 8.2 The idea: anyone can check, only one can sign

A **digital signature** scheme has two keys. The **private key** makes signatures; the **public key** checks them. Anyone may have the public key. The scheme is safe when checking is easy, and making a signature that checks is infeasible without the private key.

A **certificate** is a short document that says "this public key belongs to this name, from this date to that date", **signed by an issuer** (a certificate authority, CA). It does not prove anything by itself. It proves something to someone who trusts the issuer's public key. That key comes from the issuer's own certificate, signed by its issuer, and so on, until a **root**: a certificate that signs itself and is trusted only because it is already in the browser's or the operating system's list.

<figure class="mars-fig" markdown="0">
<svg viewBox="0 0 640 220" role="img" aria-label="Three boxes in a row: Toy Root CA (trusted, self-signed), Toy Issuing CA, and shop.example. Arrows show that the root's key checks the issuing CA's signature, and the issuing CA's key checks shop.example's signature.">
<g font-size="13" fill="currentColor">
<g fill="none" stroke="currentColor">
<rect x="20" y="40" width="170" height="120" rx="6" stroke-width="2.5"/>
<rect x="235" y="40" width="170" height="120" rx="6"/>
<rect x="450" y="40" width="170" height="120" rx="6"/>
<line x1="190" y1="100" x2="235" y2="100"/><line x1="405" y1="100" x2="450" y2="100"/>
<path d="M228 96 L235 100 L228 104"/><path d="M443 96 L450 100 L443 104"/>
</g>
<text x="32" y="62" font-weight="bold">Toy Root CA</text>
<text x="32" y="84">key: root</text><text x="32" y="104">signed by: itself</text><text x="32" y="124">in the trust store</text><text x="32" y="144">CA: yes</text>
<text x="247" y="62" font-weight="bold">Toy Issuing CA</text>
<text x="247" y="84">key: inter</text><text x="247" y="104">signed by: root</text><text x="247" y="124">sent by the server</text><text x="247" y="144">CA: yes</text>
<text x="462" y="62" font-weight="bold">shop.example</text>
<text x="462" y="84">key: leaf</text><text x="462" y="104">signed by: inter</text><text x="462" y="124">sent by the server</text><text x="462" y="144">CA: no</text>
<text x="20" y="190">Each arrow: the left key checks the signature on the right certificate.</text>
<text x="20" y="210">Trust flows from the left box only because you already trust it.</text>
</g>
</svg>
<figcaption>Figure 8.1. The toy chain of 8.5. The browser checks two signatures, right to left in what it was sent, left to right in trust.</figcaption>
</figure>

## 8.3 The math by hand

### Step 1. An RSA key from two primes

Choose two primes, `p = 61` and `q = 53` (real keys use primes of about 309 digits each). Then

```text
n   = p × q             = 61 × 53 = 3,233
phi = (p − 1)(q − 1)    = 60 × 52 = 3,120
e   = 17                 (the public exponent; it must share no factor with phi)
```

The public key is `(n, e) = (3233, 17)`. The private key is the number `d` with `e × d ≡ 1 (mod phi)`, that is, `17 d` leaves remainder 1 when divided by 3,120.

### Step 2. Finding `d` with Euclid

Divide, then divide the divisor by the remainder, until the remainder is 0 (`ex01`):

```text
3120 = 183 × 17 + 9
  17 =   1 × 9  + 8
   9 =   1 × 8  + 1
```

Now run the lines backwards to write 1 as a combination of 3,120 and 17:

```text
1 = 9 − 8
  = 9 − (17 − 9)          = 2 × 9 − 17
  = 2 × (3120 − 183 × 17) − 17
  = 2 × 3120 − 367 × 17
```

So `−367 × 17 ≡ 1 (mod 3120)`, and `d = −367 + 3120 = 2,753`. Check: `17 × 2753 = 46,801 = 15 × 3,120 + 1`.

The whole security rests on this step being easy **only if you know `p` and `q`**: computing `phi` needs them. From `n = 3233` alone, finding `p` and `q` means factoring, trivial here and, as far as anyone knows, infeasible for a 617-digit `n`.

### Step 3. Sign and verify

To sign a message, first reduce it to a number `h` below `n` (in real life, a hash; here `h = 65`):

```text
sign:    s = h^d mod n = 65^2753 mod 3233 = 588
verify:  s^e mod n     = 588^17 mod 3233  = 65   = h   → accepted
```

A forger who tries `s = 589` gets `589^17 mod 3233 = 2,838`, not 65: rejected (`ex01`). Why it works is in 8.4: `(h^d)^e = h^(de)`, and `de = 1 + 15 × phi`, which brings `h` back.

### Step 4. Square-and-multiply: why checking is cheap

`588^17` does not need 16 multiplications. Write `17` in binary, `10001`, and read the bits from the left: start with 588, then for each further bit **square**, and if the bit is 1 also **multiply by 588**, always reducing mod 3,233:

| bit | operation | value mod 3233 |
| --- | --- | ---: |
| 1 | start | 588 |
| 0 | square | 3,046 |
| 0 | square | 2,639 |
| 0 | square | 439 |
| 1 | square, then × 588 | 1,974, then 65 |

Five multiplications instead of 16. In general, an exponent with `b` bits costs `b − 1` squarings plus one multiplication per extra 1-bit. The usual public exponent is `e = 65537 = 2^16 + 1`, binary `1` followed by fifteen `0`s and a `1`: **16 squarings and 1 multiplication**. The private exponent `d` is as long as `n`, about 2,048 bits, with about half its bits 1: roughly 2,047 squarings and 1,000 multiplications, on 2,048-bit numbers. Signing is the slow side by design.

Measured on this machine with OpenSSL's own benchmark (`ex04`): 3,041 signatures per second against 56,542 verifications, about 19 times faster. The operation count above suggests an even larger gap; real signing uses a shortcut (the Chinese remainder theorem, working mod `p` and mod `q` separately, about four times faster), and both sides pay fixed costs that the count ignores.

### Step 5. What a real signature contains

`ex02` makes a fresh 2048-bit key with OpenSSL, signs a 47-byte message with `openssl dgst -sha256 -sign`, and then computes `s^e mod n` in Python with the public key. The 256-byte result is

```text
00 01 | ff ff ff … (202 bytes of ff) | 00 | 3031300d060960864801650304020105000420 | SHA-256 of the message (32 bytes)
```

and its last 32 bytes equal `hashlib.sha256(message)` exactly. The front part is the **PKCS #1 v1.5 padding**: `00 01`, enough `ff` bytes to fill 256, a `00`, then a fixed 19-byte label meaning "what follows is a SHA-256 hash". So the signature is the toy of step 3 with `h` = "the padded SHA-256 of the message". Add one character to the message and `openssl dgst -verify` answers `Verification failure` (`ex02`): the hash changes, so `s^e mod n` no longer matches it.

Hashing first is what makes signing a long message possible (RSA can only sign a number below `n`), and it means **the signature is only as strong as the hash**: two messages with the same hash share every signature (8.6).

### Step 6. Checking a chain

To trust `shop.example`'s certificate, the browser:

1. finds the issuer named in it (Toy Issuing CA) among the certificates it was sent, and checks the leaf's signature with the issuer's public key;
2. does the same for the issuer: its issuer is Toy Root CA, which is in the trust store, so the issuer's signature is checked with the root's key, and the chain ends;
3. checks the dates of every certificate against the current time;
4. checks that every issuer is allowed to issue (`CA: yes`, the *basic constraints* extension) and that `shop.example` is the name it asked for (the *subject alternative name*).

Signature checks are step 3 and 4 of this page applied to each link: two `s^e mod n` computations with `e = 65537`, a few dozen 2048-bit multiplications. That is why a browser can do it on every new connection.

## 8.4 Why it is true

**Why verification gives `h` back.** We need `(h^d)^e ≡ h (mod n)`. Since `de = 1 + k × phi` for some whole `k` (step 2, here `k = 15`), `h^(de) = h × (h^phi)^k`. Euler's theorem says `h^phi ≡ 1 (mod n)` when `h` shares no factor with `n`; then `h^(de) ≡ h × 1^k = h`. (The case where `h` shares a factor with `n` also works, by checking mod `p` and mod `q` separately; that proof is in the Cryptography site's book.) Real OpenSSL keys use `lcm(p − 1, q − 1)` in place of `phi`, which is smaller and works for the same reason; `ex02` checks `e × d mod lcm(p − 1, q − 1) = 1` for its key.

**Why `d` exists.** `e × d ≡ 1 (mod phi)` has a solution exactly when `e` and `phi` share no factor; Euclid's algorithm of step 2 finds it whenever it exists.

**Why square-and-multiply is right.** Reading the bits of `e` from the left, the value after each step is `x^(the bits read so far)`: squaring doubles the exponent (appends a 0), multiplying by `x` adds 1 (turns that 0 into a 1). After the last bit the exponent is `e`.

**Why forging is hard.** Not proved here, and not proved anywhere: RSA's security is an assumption. Anyone who can factor `n` can compute `d` (steps 1 and 2), so RSA is at most as hard as factoring. No efficient method to factor numbers of this size is publicly known, and none is known to compute signatures without `d`. A large enough quantum computer would factor efficiently (Shor's algorithm, 1994), which is why new standards for signatures that do not rely on factoring exist.

**Why a chain gives trust.** Each check shows only: "the holder of this issuer key signed this certificate". Chained, the browser concludes that the root's holder vouched for the intermediate, which vouched for the leaf. Every bit of trust comes from the root being in the trust store; nothing in the mathematics makes a root trustworthy.

## 8.5 See it in OpenSSL

`ex03` builds the chain of figure 8.1 (root valid 2026 to 2036, intermediate 2026 to 2031, leaf from 1 June to 31 December 2026, named `shop.example`) and asks `openssl verify` about it in nine situations:

| situation | `openssl verify` says |
| --- | --- |
| full chain, on 2026-11-12 | `leaf.pem: OK` |
| full chain, expected name `shop.example` | `OK` |
| full chain, expected name `evil.example` | error 62: hostname mismatch |
| full chain, on 2027-02-01 | error 10: certificate has expired |
| leaf and root, intermediate missing | error 20: unable to get local issuer certificate |
| one bit of the leaf's signature flipped | error 7: certificate signature failure |
| a leaf naming the right issuer, signed by another key | error 7: certificate signature failure |
| only the intermediate trusted, root unknown | error 2: unable to get issuer certificate |
| same, with `-partial_chain` | `OK` |

Each row is one of the checks of step 6 failing alone. Two rows deserve a second look. The forged leaf has the right issuer *name*, which costs nothing to write; only the signature check catches it. And the last row shows that trusting an intermediate directly is a choice (`-partial_chain`), not a default.

Finally, `ex03` repeats step 5 on the certificate itself: it takes the leaf's "to-be-signed" part (the bytes of name, key, dates and extensions, about 470 bytes), hashes it with SHA-256, and compares with the last 32 bytes of `s^e mod n` computed from the leaf's signature and the intermediate's public key. They are equal. **A certificate is its contents plus the issuer's signature on their hash**, nothing more.

## 8.6 Where it breaks

- **A weak hash breaks every signature that uses it.** In 2008, Alexander Sotirov, Marc Stevens and colleagues made two certificate contents with the same MD5 hash, got a real CA to sign the harmless one, and so obtained a valid signature on a CA certificate of their own ("MD5 considered harmful today"). Signatures moved to SHA-256 for this reason. Browsers stopped accepting SHA-1 certificates in early 2017, shortly before the first SHA-1 collision was published (see the [Git tutorial](../git/08-Names-From-Contents.md), step 4).
- **Toy sizes and textbook RSA are unsafe.** `n = 3233` factors instantly; signing a raw number without padding allows forgeries by multiplying signatures together (exercise E5). Real systems use 2048-bit or larger keys and a padding such as PKCS #1 v1.5 or PSS.
- **Time.** "Expired" depends on the verifier's clock. A device with a wrong clock rejects good certificates or accepts expired ones.
- **Revocation.** A stolen private key stays mathematically valid until the certificate expires. Revocation lists and OCSP exist to say "do not trust this any more", and checking them is often slow or skipped. Short-lived certificates are the other answer.
- **The trust store is the real root.** Any root in it can vouch for any name. A wrongly trusted or compromised root breaks everything below it, with no mathematical warning.
- **Quantum computers** would break RSA by factoring (8.4). Standards for post-quantum signatures exist; this tutorial does not cover them.

## 8.7 Exercises

Do 1 to 5 with a pencil. 6 needs a few lines of thought. 7 is code.

**E1. With `p = 5`, `q = 11`, `e = 3`: compute `n`, `phi` and `d`. Sign `h = 7` and verify.**

??? success "Answer"
    `n = 55`, `phi = 4 × 10 = 40`. `40 = 13 × 3 + 1`, so `1 = 40 − 13 × 3`, `d ≡ −13 ≡ 27 (mod 40)`; check `3 × 27 = 81 = 2 × 40 + 1`. Sign: `7^27 mod 55`. Square-and-multiply on `27 = 11011`: start 7; square 49, × 7 = 343 mod 55 = 13; square 169 mod 55 = 4; square 16, × 7 = 112 mod 55 = 2; square 4, × 7 = 28. So `s = 28`. Verify: `28^3 = 21,952 = 399 × 55 + 7`, so `s^3 mod 55 = 7 = h`.

**E2. How many squarings and multiplications does square-and-multiply need for `e = 3`, `e = 17` and `e = 65537`? For a 3072-bit `d` with 1,500 one-bits?**

??? success "Answer"
    `3 = 11`: 1 squaring + 1 multiplication. `17 = 10001`: 4 + 1. `65537 = 1` and 15 zeros and `1`: 16 + 1. The 3072-bit `d`: 3,071 squarings + 1,499 multiplications.

**E3. Why does `e = 65537` work with almost every key, but `e = 2` never does?**

??? success "Answer"
    `e` must share no factor with `phi = (p − 1)(q − 1)`. For odd primes `p` and `q`, `p − 1` is even, so `phi` is even and `e = 2` always shares the factor 2. `65537` is prime, so it fails only when it divides `p − 1` or `q − 1`, which key generation simply avoids.

**E4. A browser sees a chain leaf → intermediate → root, where the root is in its trust store. List the signature checks it performs and the key it uses for each.**

??? success "Answer"
    Two: the leaf's signature with the intermediate's public key, and the intermediate's signature with the root's public key. The root's self-signature proves nothing (anyone can sign their own certificate); the root is trusted because it is in the store.

**E5. Textbook RSA (no hash, no padding) with the key of step 1. You see signatures `s₁ = 588` on `h₁ = 65` and `s₂` on `h₂ = 2`. Show that `s₁ × s₂ mod n` is a valid signature on `130`, without knowing `d`.**

??? success "Answer"
    `(s₁ s₂)^e = s₁^e × s₂^e ≡ h₁ × h₂ = 65 × 2 = 130 (mod 3233)`. So the product of two signatures signs the product of the two numbers: a forgery of a message nobody signed. Hashing and padding destroy this structure, because the padded hash of a message is not the product of two other padded hashes.

**E6. A company's internal tool fails with "unable to get local issuer certificate" for a site that works in the browser. Using the table of 8.5, what is the likely cause, and what is the fix?**

??? success "Answer"
    Error 20: the tool reached a certificate whose issuer it cannot find. Most often the server sends only its leaf, and the browser filled in the intermediate from its cache or downloaded it, while the tool does not. Fix the server to send the full chain (leaf plus intermediates). Turning verification off is not a fix.

**E7. (Code.) With Python's `pow`, find `d` for the key of step 1, sign every `h` from 2 to 3,232, and check that every signature verifies. Then count how many `h` have `h^e mod n = h` already (signatures that equal their message).**

??? success "Answer"
    ```python
    from math import gcd

    p, q, e = 61, 53, 17
    n = p * q
    d = pow(e, -1, (p - 1) * (q - 1))
    assert all(pow(pow(h, d, n), e, n) == h for h in range(2, n))
    fixed = sum(1 for h in range(n) if pow(h, e, n) == h)
    print(d, fixed, "formula:", (1 + gcd(e - 1, p - 1)) * (1 + gcd(e - 1, q - 1)))
    ```

    It prints `2753 25 formula: 25`: every signature verifies, and 25 of the 3,233 numbers (including 0 and 1) are their own signature. A formula predicts it: mod 61, the solutions of `h^17 = h` number `1 + gcd(16, 60) = 5`; mod 53, `1 + gcd(16, 52) = 5`; combined by the Chinese remainder theorem, `5 × 5 = 25`. (The script prints the formula's value next to the count.) ([ex05_all_h.py](src/08/ex05_all_h.py), [output](src/08/ex05.out.txt).)

## 8.8 What I saw at work

!!! quote "Your notes"
    *(Left for you: a certificate error you met, which check in the table of 8.5 it was, and what fixed it.)*

## 8.9 Further reading

On your own sites:

- The Cryptography site: [the book](https://cryptography.akadian.ca/book/), [SHA-2](https://cryptography.akadian.ca/07-hash/SHA-2/), [Retired hashes](https://cryptography.akadian.ca/07-hash/Retired/)
- The same hash ideas in Git: [8. Names from contents](../git/08-Names-From-Contents.md)

Original sources:

- R. L. Rivest, A. Shamir and L. Adleman, "A Method for Obtaining Digital Signatures and Public-Key Cryptosystems", *Communications of the ACM* 21(2), 1978.
- RFC 8017, *PKCS #1: RSA Cryptography Specifications Version 2.2* (2016): the padding of step 5 (EMSA-PKCS1-v1_5) and PSS.
- RFC 5280, *Internet X.509 Public Key Infrastructure Certificate and CRL Profile* (2008): certificates and path validation.
- A. Sotirov, M. Stevens, J. Appelbaum, A. Lenstra, D. Molnar, D. A. Osvik and B. de Weger, "MD5 considered harmful today: Creating a rogue CA certificate", 2008.
- P. W. Shor, "Algorithms for quantum computation: discrete logarithms and factoring", *FOCS 1994*.

## Glossary

- **Public key / private key**: the checking key anyone may have, and the signing key only its owner has.
- **RSA**: the signature (and encryption) scheme built on `n = p × q` and exponents `e`, `d` with `e × d ≡ 1`.
- **Modulus `n`**: the product of the two secret primes; its size in bits is the key size.
- **Square-and-multiply**: computing a power by reading the exponent's bits, squaring for each bit and multiplying for each 1.
- **Padding**: the fixed structure placed around the hash before signing (PKCS #1 v1.5 or PSS).
- **Certificate**: a public key, a name, dates and extensions, signed by an issuer.
- **Certificate authority (CA)**: an issuer of certificates.
- **Root**: a self-signed CA certificate trusted because it is in the trust store.
- **Intermediate**: a CA certificate between the root and the leaf.
- **Chain (path) validation**: checking every signature, date, name and constraint from the leaf up to a trusted root.
