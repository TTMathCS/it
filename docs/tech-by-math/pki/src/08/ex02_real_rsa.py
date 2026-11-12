# Tech by Math, PKI tutorial 8: a real RSA-2048 signature made by OpenSSL (3.0), then checked by hand
# with one line of arithmetic, s^e mod n, in Python. The key is made fresh on each run, so the numbers
# differ between runs; the structure does not.
import hashlib
import os
import subprocess
import tempfile
from cryptography.hazmat.primitives import serialization

msg = b"Order 1042: 3 tonnes of regolith, Arcadia City\n"
with tempfile.TemporaryDirectory() as d:
    run = lambda *a: subprocess.run(["openssl", *a], cwd=d, capture_output=True, check=True)
    with open(os.path.join(d, "msg.txt"), "wb") as f:
        f.write(msg)
    run("genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", "key.pem")
    run("pkey", "-in", "key.pem", "-pubout", "-out", "pub.pem")
    run("dgst", "-sha256", "-sign", "key.pem", "-out", "sig.bin", "msg.txt")
    ok = subprocess.run(["openssl", "dgst", "-sha256", "-verify", "pub.pem", "-signature", "sig.bin", "msg.txt"],
                        cwd=d, capture_output=True, text=True).stdout.strip()
    with open(os.path.join(d, "msg.txt"), "ab") as f:
        f.write(b"!")
    bad = subprocess.run(["openssl", "dgst", "-sha256", "-verify", "pub.pem", "-signature", "sig.bin", "msg.txt"],
                         cwd=d, capture_output=True, text=True).stdout.strip()
    pub = serialization.load_pem_public_key(open(os.path.join(d, "pub.pem"), "rb").read()).public_numbers()
    priv = serialization.load_pem_private_key(open(os.path.join(d, "key.pem"), "rb").read(), None).private_numbers()
    sig = open(os.path.join(d, "sig.bin"), "rb").read()

n, e = pub.n, pub.e
print(f"openssl dgst -verify on the message:            {ok}")
print(f"openssl dgst -verify after adding one '!':       {bad}")
print(f"\nn has {n.bit_length()} bits ({len(str(n))} decimal digits); e = {e}")
print(f"p has {priv.p.bit_length()} bits, q has {priv.q.bit_length()} bits; p x q == n: {priv.p * priv.q == n}")
print(f"d has {priv.d.bit_length()} bits; e x d mod lcm(p-1, q-1) = "
      f"{e * priv.d % ((priv.p - 1) * (priv.q - 1) // __import__('math').gcd(priv.p - 1, priv.q - 1))}")
s = int.from_bytes(sig, "big")
m = pow(s, e, n).to_bytes(256, "big")
print(f"\nsignature: {len(sig)} bytes;  s^e mod n, as 256 bytes:")
print(f"   {m[:2].hex()} | {m[2:12].hex()}... ({m[2:].index(0)} bytes of ff) | {m[2 + m[2:].index(0)]:02x} | "
      f"{m[-51:-32].hex()} | {m[-32:].hex()}")
digest = hashlib.sha256(msg).hexdigest()
print(f"   the last 32 bytes:       {m[-32:].hex()}")
print(f"   SHA-256 of the message:  {digest}")
print(f"   equal: {m[-32:].hex() == digest}")
expected = b"\x00\x01" + b"\xff" * (256 - 3 - 19 - 32) + b"\x00" + bytes.fromhex("3031300d060960864801650304020105000420") + bytes.fromhex(digest)
print(f"   whole block equals 00 01 ff..ff 00 + DigestInfo(SHA-256) + hash: {m == expected}")
