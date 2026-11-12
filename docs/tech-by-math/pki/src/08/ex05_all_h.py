# Tech by Math, PKI tutorial 8, exercise E7: sign every h with the toy key and count fixed points h^e = h.
from math import gcd

p, q, e = 61, 53, 17
n = p * q
d = pow(e, -1, (p - 1) * (q - 1))
assert all(pow(pow(h, d, n), e, n) == h for h in range(2, n))
fixed = sum(1 for h in range(n) if pow(h, e, n) == h)
print(d, fixed, "formula:", (1 + gcd(e - 1, p - 1)) * (1 + gcd(e - 1, q - 1)))
