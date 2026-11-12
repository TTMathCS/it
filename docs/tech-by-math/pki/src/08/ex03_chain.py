# Tech by Math, PKI tutorial 8: a three-level chain (root CA -> intermediate CA -> shop.example), built with
# Python's cryptography package, checked by OpenSSL 3.0's `openssl verify`, and one signature checked by hand.
# Fixed dates; the keys are fresh on each run, so ids and signatures differ between runs.
import datetime as dt
import hashlib
import os
import subprocess
import tempfile
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

T = lambda y, m, d: dt.datetime(y, m, d, tzinfo=dt.timezone.utc)


def name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def cert(subject, subject_key, issuer, issuer_key, start, end, ca, pathlen=None, dns=None):
    b = (x509.CertificateBuilder().subject_name(name(subject)).issuer_name(name(issuer))
         .public_key(subject_key.public_key()).serial_number(x509.random_serial_number())
         .not_valid_before(start).not_valid_after(end)
         .add_extension(x509.BasicConstraints(ca=ca, path_length=pathlen), critical=True))
    if dns:
        b = b.add_extension(x509.SubjectAlternativeName([x509.DNSName(dns)]), critical=False)
    return b.sign(issuer_key, hashes.SHA256())


keys = {k: rsa.generate_private_key(public_exponent=65537, key_size=2048) for k in ("root", "inter", "leaf", "other")}
root = cert("Toy Root CA", keys["root"], "Toy Root CA", keys["root"], T(2026, 1, 1), T(2036, 1, 1), True, 1)
inter = cert("Toy Issuing CA", keys["inter"], "Toy Root CA", keys["root"], T(2026, 1, 1), T(2031, 1, 1), True, 0)
leaf = cert("shop.example", keys["leaf"], "Toy Issuing CA", keys["inter"], T(2026, 6, 1), T(2026, 12, 31), False, dns="shop.example")
forged = cert("shop.example", keys["leaf"], "Toy Issuing CA", keys["other"], T(2026, 6, 1), T(2026, 12, 31), False, dns="shop.example")

with tempfile.TemporaryDirectory() as d:
    def save(fn, c):
        with open(os.path.join(d, fn), "wb") as f:
            f.write(c.public_bytes(serialization.Encoding.PEM))
    save("root.pem", root), save("inter.pem", inter), save("leaf.pem", leaf), save("forged.pem", forged)
    der = bytearray(leaf.public_bytes(serialization.Encoding.DER))
    der[-1] ^= 0x01                                   # flip one bit of the signature
    with open(os.path.join(d, "tampered.der"), "wb") as f:
        f.write(der)
    subprocess.run(["openssl", "x509", "-inform", "DER", "-in", "tampered.der", "-out", "tampered.pem"], cwd=d, check=True)

    def verify(label, *args):
        p = subprocess.run(["openssl", "verify", *args], cwd=d, capture_output=True, text=True)
        out = (p.stdout + p.stderr).strip().splitlines()
        print(f"   {label:<45} -> {out[-1] if p.returncode == 0 else next(l for l in out if 'depth lookup' in l)}")

    at = lambda y, m, dd: str(int(T(y, m, dd).timestamp()))
    print("openssl verify (time fixed with -attime):")
    verify("full chain, 2026-11-12", "-attime", at(2026, 11, 12), "-CAfile", "root.pem", "-untrusted", "inter.pem", "leaf.pem")
    verify("full chain, name shop.example", "-attime", at(2026, 11, 12), "-verify_hostname", "shop.example", "-CAfile", "root.pem", "-untrusted", "inter.pem", "leaf.pem")
    verify("full chain, name evil.example", "-attime", at(2026, 11, 12), "-verify_hostname", "evil.example", "-CAfile", "root.pem", "-untrusted", "inter.pem", "leaf.pem")
    verify("full chain, 2027-02-01 (leaf expired)", "-attime", at(2027, 2, 1), "-CAfile", "root.pem", "-untrusted", "inter.pem", "leaf.pem")
    verify("leaf without the intermediate", "-attime", at(2026, 11, 12), "-CAfile", "root.pem", "leaf.pem")
    verify("one bit of the leaf's signature flipped", "-attime", at(2026, 11, 12), "-CAfile", "root.pem", "-untrusted", "inter.pem", "tampered.pem")
    verify("leaf signed by a key that is not the CA's", "-attime", at(2026, 11, 12), "-CAfile", "root.pem", "-untrusted", "inter.pem", "forged.pem")
    verify("intermediate trusted, root unknown", "-attime", at(2026, 11, 12), "-CAfile", "inter.pem", "leaf.pem")
    verify("same, with -partial_chain", "-attime", at(2026, 11, 12), "-partial_chain", "-CAfile", "inter.pem", "leaf.pem")

pub = keys["inter"].public_key().public_numbers()
s = int.from_bytes(leaf.signature, "big")
block = pow(s, pub.e, pub.n).to_bytes(256, "big")
tbs_hash = hashlib.sha256(leaf.tbs_certificate_bytes).hexdigest()
print("\nThe leaf's signature, checked by hand with the intermediate's public key (n, e):")
print(f"   the leaf's to-be-signed part: {len(leaf.tbs_certificate_bytes)} bytes; its SHA-256 {tbs_hash}")
print(f"   last 32 bytes of s^e mod n:                         {block[-32:].hex()}")
print(f"   equal: {block[-32:].hex() == tbs_hash}; block starts {block[:3].hex()}...")
keys["inter"].public_key().verify(leaf.signature, leaf.tbs_certificate_bytes, padding.PKCS1v15(), hashes.SHA256())
print("   (the cryptography package's own verify() agrees: no exception)")
