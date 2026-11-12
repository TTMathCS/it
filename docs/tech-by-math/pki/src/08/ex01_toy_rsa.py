# Tech by Math, PKI tutorial 8: RSA with numbers small enough for a pencil (p = 61, q = 53).
# Toy sizes only: real keys use primes of about 300 digits (see ex02).
p, q, e = 61, 53, 17
n, phi = p * q, (p - 1) * (q - 1)
print(f"n = p x q = {p} x {q} = {n};  phi = (p-1)(q-1) = {p - 1} x {q - 1} = {phi};  e = {e}")

print("\nExtended Euclid for e x d = 1 (mod phi): divide, keep the remainders")
a, b = phi, e
rows = []
while b:
    rows.append((a, b, a // b, a % b))
    a, b = b, a % b
for a_, b_, qt, r in rows:
    print(f"   {a_:>5} = {qt:>3} x {b_:>4} + {r}")
d = pow(e, -1, phi)
print(f"   back-substitution gives d = {d};  check: e x d = {e * d} = {e * d // phi} x {phi} + {e * d % phi}")

h = 65   # the "hash" of the message, a number below n
s = pow(h, d, n)
print(f"\nSign h = {h}:   s = h^d mod n = {h}^{d} mod {n} = {s}")
print(f"Verify:        s^e mod n = {s}^{e} mod {n} = {pow(s, e, n)}  (equals h: accepted)")
print(f"Forged s+1:    {(s + 1)}^{e} mod {n} = {pow(s + 1, e, n)}  (not h: rejected)")


def square_and_multiply(x, k, m):
    bits = bin(k)[2:]
    r, steps, mults = 1, [], 0
    for i, bit in enumerate(bits):
        if i:
            r = r * r % m
            mults += 1
            steps.append(f"square -> {r}")
        if bit == "1":
            r = r * x % m if i else x % m
            mults += 1 if i else 0
            steps.append(f"x{x} -> {r}" if i else f"start with {x}")
    return r, bits, steps, mults


r, bits, steps, mults = square_and_multiply(s, e, n)
print(f"\nVerification by square-and-multiply: e = {e} = binary {bits}")
for st in steps:
    print("   " + st)
print(f"   result {r}, using {mults} multiplications instead of {e - 1}")
for k, name in ((65537, "e = 65537, the usual public exponent"), (2 ** 2048 - 1, "a 2048-bit exponent of all ones (worst case)")):
    b = bin(k)[2:]
    print(f"   {name}: {len(b) - 1} squarings + {b.count('1') - 1} multiplications")
