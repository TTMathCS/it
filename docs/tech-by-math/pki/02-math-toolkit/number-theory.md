# Number Theory Foundations for PKI

## Introduction

Public Key Infrastructure (PKI) is built upon deep mathematical foundations from number theory. Understanding these concepts explains why RSA, Elliptic Curve Cryptography, and other PKI algorithms are both secure and computationally feasible. This document explores the mathematical principles that make secure digital certificates possible.

## Modular Arithmetic: The Foundation of PKI

### Basic Definitions

**Modular arithmetic** is arithmetic performed over a finite set of integers, which forms the mathematical basis for all PKI cryptographic operations.

**Congruence Relation**: Two integers `a` and `b` are congruent modulo `n` if they have the same remainder when divided by `n`.

**Notation**: `a ≡ b (mod n)` means `n | (a - b)`

**Example**:
```
17 ≡ 5 (mod 12)  because 17 = 1×12 + 5 and 5 = 0×12 + 5
-7 ≡ 5 (mod 12)  because -7 = -1×12 + 5
```

### Modular Arithmetic Operations

**Addition**: `(a + b) mod n = ((a mod n) + (b mod n)) mod n`
**Multiplication**: `(a × b) mod n = ((a mod n) × (b mod n)) mod n`
**Exponentiation**: `a^k mod n` (computed efficiently using fast exponentiation)

**Fast Exponentiation Algorithm**:
```python
def mod_exp(base, exp, mod):
    """Compute base^exp mod mod efficiently"""
    result = 1
    base = base % mod
    
    while exp > 0:
        if exp % 2 == 1:
            result = (result * base) % mod
        exp = exp >> 1
        base = (base * base) % mod
    
    return result

# Example: Compute 2^100 mod 13
result = mod_exp(2, 100, 13)  # Result: 9
```

**Time Complexity**: O(log exp), making large exponentiations feasible

### Modular Multiplicative Inverse

The **multiplicative inverse** of `a` modulo `n` is an integer `x` such that `ax ≡ 1 (mod n)`.

**Existence**: Inverse exists if and only if `gcd(a, n) = 1`

**Extended Euclidean Algorithm**:
```python
def extended_gcd(a, b):
    """Extended Euclidean algorithm"""
    if a == 0:
        return b, 0, 1
    
    gcd, x1, y1 = extended_gcd(b % a, a)
    x = y1 - (b // a) * x1
    y = x1
    
    return gcd, x, y

def mod_inverse(a, n):
    """Find modular multiplicative inverse"""
    gcd, x, y = extended_gcd(a, n)
    if gcd != 1:
        raise ValueError("Inverse does not exist")
    return (x % n + n) % n

# Example: Find inverse of 7 mod 13
inv = mod_inverse(7, 13)  # Result: 2 (because 7×2 ≡ 1 (mod 13))
```

## Prime Numbers and Primality Testing

### Fundamental Theorem of Arithmetic

Every integer greater than 1 can be uniquely factored into prime numbers.

**Importance for PKI**: The security of RSA relies on the difficulty of factoring large composite numbers into their prime factors.

### Prime Generation for RSA

**Requirements for RSA primes**:
1. **Large size**: Typically 1024 bits each for RSA-2048
2. **Random selection**: Cryptographically secure random generation
3. **Primality**: Must be prime (not composite)
4. **Distinct**: p ≠ q for security

**Safe Primes**: A prime p is "safe" if (p-1)/2 is also prime
- **Advantage**: Provides additional security against certain attacks
- **Example**: p = 23 is safe because (23-1)/2 = 11 is prime

### Primality Testing Algorithms

**Miller-Rabin Primality Test**: Probabilistic algorithm used in practice
```python
import random

def miller_rabin(n, k=5):
    """Miller-Rabin primality test"""
    if n < 2:
        return False
    if n == 2 or n == 3:
        return True
    if n % 2 == 0:
        return False
    
    # Write n-1 as 2^r * d
    r = 0
    d = n - 1
    while d % 2 == 0:
        r += 1
        d //= 2
    
    # Perform k rounds of testing
    for _ in range(k):
        a = random.randint(2, n - 2)
        x = pow(a, d, n)
        
        if x == 1 or x == n - 1:
            continue
        
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    
    return True

# Usage
is_prime = miller_rabin(982451653)  # Test large number
```

**Error Probability**: At most 4^(-k) for k rounds
**Industry Standard**: k = 64 rounds for cryptographic applications

## Euler's Theorem and RSA Mathematics

### Euler's Totient Function

**Definition**: φ(n) counts integers from 1 to n that are coprime to n

**For prime p**: φ(p) = p - 1
**For RSA modulus n = pq**: φ(n) = (p-1)(q-1)

**Example**:
```
φ(12) = |{1, 5, 7, 11}| = 4
φ(13) = 12 (since 13 is prime)
```

### Euler's Theorem

**Statement**: If gcd(a, n) = 1, then a^φ(n) ≡ 1 (mod n)

**Special Case (Fermat's Little Theorem)**: If p is prime and gcd(a, p) = 1, then a^(p-1) ≡ 1 (mod p)

### RSA Key Generation Mathematics

**RSA Algorithm**:
1. Choose distinct primes p, q
2. Compute n = pq and φ(n) = (p-1)(q-1)
3. Choose e such that gcd(e, φ(n)) = 1
4. Compute d ≡ e^(-1) (mod φ(n))

**Key Relationship**: ed ≡ 1 (mod φ(n))

**RSA Correctness Proof**:
```
For message M:
Encryption: C ≡ M^e (mod n)
Decryption: C^d ≡ (M^e)^d ≡ M^(ed) (mod n)

Since ed ≡ 1 (mod φ(n)), we have ed = kφ(n) + 1 for some k
Therefore: M^(ed) ≡ M^(kφ(n)+1) ≡ M^(kφ(n)) × M ≡ (M^φ(n))^k × M (mod n)

By Euler's theorem: M^φ(n) ≡ 1 (mod n)
So: (M^φ(n))^k ≡ 1^k ≡ 1 (mod n)
Therefore: C^d ≡ 1 × M ≡ M (mod n)
```

## Discrete Logarithm Problem

### Definition

Given g, h, and p, find x such that g^x ≡ h (mod p)

**Notation**: x = log_g(h) mod p

**Example**: 
```
Find x such that 3^x ≡ 4 (mod 7)
By trial: 3^1 ≡ 3, 3^2 ≡ 2, 3^3 ≡ 6, 3^4 ≡ 4 (mod 7)
Answer: x = 4
```

### Computational Complexity

**Best Known Algorithms**:
- **Pollard's Rho**: O(√p) time, O(1) space
- **Index Calculus**: Subexponential for certain groups
- **Pohlig-Hellman**: Efficient when p-1 has small prime factors

**Security Requirement**: Choose p such that p-1 has large prime factors

### Digital Signature Algorithm (DSA) Mathematics

**Parameter Generation**:
1. Choose prime p (typically 2048 or 3072 bits)
2. Choose prime q that divides (p-1) (typically 256 bits)
3. Find generator g of order q mod p

**Key Generation**:
- Private key: x ∈ [1, q-1]
- Public key: y ≡ g^x (mod p)

**Signature Generation**:
```
To sign message M:
1. Choose random k ∈ [1, q-1]
2. Compute r ≡ (g^k mod p) mod q
3. Compute s ≡ k^(-1)(H(M) + xr) (mod q)
Signature: (r, s)
```

**Signature Verification**:
```
To verify signature (r,s) on message M:
1. Compute w ≡ s^(-1) (mod q)
2. Compute u1 ≡ H(M)w (mod q)
3. Compute u2 ≡ rw (mod q)
4. Compute v ≡ (g^u1 × y^u2 mod p) mod q
5. Accept if v = r
```

## Elliptic Curve Mathematics

### Elliptic Curve Definition

**Weierstrass Form**: y² = x³ + ax + b (mod p)

**Discriminant**: Δ = -16(4a³ + 27b²) ≠ 0 (ensures non-singular curve)

**Point Addition**: Geometric operation that forms a group

### Point Addition Algorithm

**Case 1: P + O = P** (O is point at infinity)
**Case 2: P + (-P) = O** (inverse points)
**Case 3: P ≠ Q** (distinct finite points)
```
λ = (y₂ - y₁) × (x₂ - x₁)^(-1) mod p
x₃ = λ² - x₁ - x₂ mod p
y₃ = λ(x₁ - x₃) - y₁ mod p
```

**Case 4: P = Q** (point doubling)
```
λ = (3x₁² + a) × (2y₁)^(-1) mod p
x₃ = λ² - 2x₁ mod p
y₃ = λ(x₁ - x₃) - y₁ mod p
```

### Elliptic Curve Discrete Logarithm Problem (ECDLP)

**Problem**: Given points P and Q on elliptic curve, find k such that Q = kP

**Security**: Best known attacks require O(√n) operations where n is curve order

**Advantage**: Smaller key sizes for equivalent security
- 256-bit ECC ≈ 3072-bit RSA
- 384-bit ECC ≈ 7680-bit RSA

### Popular Elliptic Curves

**P-256 (secp256r1)**:
- p = 2²⁵⁶ - 2²²⁴ + 2¹⁹² + 2⁹⁶ - 1
- a = -3, b = specific value
- NIST standard, widely implemented

**Curve25519**:
- Montgomery form: y² = x³ + 486662x² + x
- Designed for high performance and security
- Used in modern protocols (Signal, TLS 1.3)

## Computational Complexity and Security

### Hard Problems in Number Theory

**Integer Factorization Problem**:
- **Problem**: Factor n = pq where p, q are large primes
- **Difficulty**: No known polynomial-time algorithm
- **Best Algorithm**: General Number Field Sieve (GNFS)
- **Complexity**: exp(O(∛(log n log log n)²))

**RSA Problem**:
- **Problem**: Given (n, e, c), find m such that m^e ≡ c (mod n)
- **Relation**: At least as hard as factoring n
- **Security**: Forms basis of RSA cryptosystem

**Discrete Logarithm Problem**:
- **Multiplicative Group**: mod p
- **Elliptic Curve Group**: ECDLP
- **Complexity**: Subexponential for mod p, exponential for elliptic curves

### Security Parameter Selection

**RSA Key Sizes**:
```
Security Level | RSA Modulus | Symmetric Equivalent
80-bit        | 1024 bits   | 80-bit key (DEPRECATED)
112-bit       | 2048 bits   | 112-bit key (CURRENT)
128-bit       | 3072 bits   | 128-bit key (FUTURE)
192-bit       | 7680 bits   | 192-bit key (HIGH)
256-bit       | 15360 bits  | 256-bit key (MAXIMUM)
```

**ECC Key Sizes**:
```
Security Level | ECC Key Size | Hash Function
112-bit       | 224 bits     | SHA-224
128-bit       | 256 bits     | SHA-256
192-bit       | 384 bits     | SHA-384
256-bit       | 521 bits     | SHA-512
```

## Quantum Threats and Post-Quantum Cryptography

### Shor's Algorithm Impact

**Quantum Algorithm**: Efficiently factors integers and solves discrete logarithm
- **Classical Complexity**: Exponential
- **Quantum Complexity**: Polynomial O((log n)³)

**Timeline**: Large-scale quantum computers estimated 10-30 years

### Post-Quantum Alternatives

**Lattice-Based Cryptography**:
- **Problems**: Learning With Errors (LWE), Ring-LWE
- **Algorithms**: CRYSTALS-Kyber (encryption), CRYSTALS-Dilithium (signatures)
- **Advantage**: Believed quantum-resistant

**Code-Based Cryptography**:
- **Problems**: Syndrome decoding
- **Algorithms**: Classic McEliece
- **History**: Longest-studied post-quantum approach

**Multivariate Cryptography**:
- **Problems**: Solving multivariate polynomial systems
- **Applications**: Primarily signatures
- **Trade-offs**: Small signatures, large public keys

## Practical Implementation Considerations

### Random Number Generation

**Entropy Requirements**: Cryptographic security depends on unpredictable randomness
- **Prime Generation**: Requires high-quality entropy
- **Key Generation**: Private keys must be unpredictable
- **Nonce Selection**: Critical for signature security

**Entropy Sources**:
- **Hardware**: CPU random number generators, environmental noise
- **Software**: /dev/urandom, CryptGenRandom, etc.
- **Standards**: NIST SP 800-90A for deterministic random bit generators

### Side-Channel Attack Prevention

**Timing Attacks**: Prevent information leakage through execution time
```python
def constant_time_compare(a, b):
    """Constant-time comparison"""
    if len(a) != len(b):
        return False
    
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0
```

**Power Analysis**: Use randomization and masking
**Fault Attacks**: Implement redundant calculations and checks

These number-theoretic foundations provide the mathematical security guarantees that make PKI trustworthy for global-scale digital identity and secure communications. Understanding these concepts is essential for implementing, auditing, and evolving PKI systems.