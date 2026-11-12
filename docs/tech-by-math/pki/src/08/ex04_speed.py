# Tech by Math, PKI tutorial 8: how much faster an RSA-2048 verify is than a sign, on this machine
# (OpenSSL 3.0's own benchmark, 2 seconds each; the absolute numbers depend on the computer).
import subprocess

out = subprocess.run(["openssl", "speed", "-seconds", "2", "rsa2048"], capture_output=True, text=True).stdout
lines = out.strip().splitlines()[-2:]
print("\n".join(lines))
sign_s, verify_s = map(float, lines[-1].split()[-2:])
print(f"verifies per sign: {verify_s / sign_s:.1f}")
