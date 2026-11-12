# PKI Algorithms

> *"Algorithms are the poetry of computation."* - Donald Knuth

## Overview

PKI's security depends on carefully implemented cryptographic algorithms that transform mathematical theory into practical security solutions. This section explores the key algorithms that make PKI work - from key generation and digital signatures to certificate validation and revocation checking.

## Core Algorithm Categories

PKI algorithms can be categorized into several fundamental groups, each serving specific security functions:

### Algorithm Classification
```
                    PKI Algorithm Ecosystem
                              |
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   Key Management      Digital Signatures    Certificate Operations
        │                     │                     │
    ┌───┼───┐             ┌───┼───┐             ┌───┼───┐
   Key   Key             RSA   ECDSA           Path  Revocation
   Gen   Exchange       DSA   EdDSA          Validation Checking
```

## Asymmetric Key Algorithms

### RSA Algorithm Family

**RSA Key Generation**:
```python
def rsa_key_generation(key_size):
    # 1. Generate two distinct large primes
    p = generate_large_prime(key_size // 2)
    q = generate_large_prime(key_size // 2)
    
    # 2. Compute modulus
    n = p * q
    
    # 3. Compute Euler's totient function
    phi_n = (p - 1) * (q - 1)
    
    # 4. Choose public exponent (commonly 65537)
    e = 65537
    assert gcd(e, phi_n) == 1
    
    # 5. Compute private exponent
    d = mod_inverse(e, phi_n)
    
    # 6. Return key pair
    public_key = (n, e)
    private_key = (n, d)
    
    return public_key, private_key
```

**RSA Encryption/Decryption**:
```python
def rsa_encrypt(message, public_key):
    n, e = public_key
    return pow(message, e, n)

def rsa_decrypt(ciphertext, private_key):
    n, d = private_key
    return pow(ciphertext, d, n)
```

**RSA Digital Signatures (PKCS#1 v2.1)**:
```python
def rsa_sign_pss(message, private_key, hash_func=sha256):
    # 1. Hash message
    mHash = hash_func(message)
    
    # 2. Apply PSS encoding
    encoded_message = pss_encode(mHash, key_length, hash_func)
    
    # 3. Convert to integer
    m = bytes_to_int(encoded_message)
    
    # 4. Apply RSA private key operation
    n, d = private_key
    signature = pow(m, d, n)
    
    return int_to_bytes(signature)

def rsa_verify_pss(message, signature, public_key, hash_func=sha256):
    # 1. Convert signature to integer
    s = bytes_to_int(signature)
    
    # 2. Apply RSA public key operation
    n, e = public_key
    encoded_message = pow(s, e, n)
    
    # 3. Convert back to bytes
    em = int_to_bytes(encoded_message)
    
    # 4. Verify PSS encoding
    mHash = hash_func(message)
    return pss_verify(mHash, em, key_length, hash_func)
```

**Security Properties**:
- **Key Size**: Minimum 2048 bits (112-bit security), 3072 bits recommended (128-bit security)
- **Padding Schemes**: OAEP for encryption, PSS for signatures (avoid PKCS#1 v1.5)
- **Performance**: Slower than ECC, but widely supported and well-understood

### Elliptic Curve Algorithms

**ECDSA (Elliptic Curve Digital Signature Algorithm)**:
```python
def ecdsa_key_generation(curve):
    # 1. Select random private key
    private_key = random_int(1, curve.order - 1)
    
    # 2. Compute public key
    public_key = private_key * curve.generator
    
    return private_key, public_key

def ecdsa_sign(message, private_key, curve, hash_func=sha256):
    # 1. Hash message
    e = bytes_to_int(hash_func(message))
    
    # 2. Generate random nonce k
    k = random_int(1, curve.order - 1)
    
    # 3. Compute r = (k * G).x mod n
    point = k * curve.generator
    r = point.x % curve.order
    
    # 4. Compute s = k^(-1) * (e + r * private_key) mod n
    k_inv = mod_inverse(k, curve.order)
    s = (k_inv * (e + r * private_key)) % curve.order
    
    return (r, s)

def ecdsa_verify(message, signature, public_key, curve, hash_func=sha256):
    r, s = signature
    
    # 1. Verify signature values in range
    if not (1 <= r < curve.order and 1 <= s < curve.order):
        return False
    
    # 2. Hash message
    e = bytes_to_int(hash_func(message))
    
    # 3. Compute signature verification
    w = mod_inverse(s, curve.order)
    u1 = (e * w) % curve.order
    u2 = (r * w) % curve.order
    
    # 4. Compute point
    point = u1 * curve.generator + u2 * public_key
    
    # 5. Verify
    return r == (point.x % curve.order)
```

**EdDSA (Edwards-curve Digital Signature Algorithm)**:
```python
def ed25519_sign(message, private_key):
    # 1. Hash private key to get secret scalar and nonce prefix
    h = sha512(private_key)
    a = bytes_to_int(h[:32])
    prefix = h[32:]
    
    # 2. Compute public key
    public_key = a * curve25519.generator
    
    # 3. Compute nonce
    r = sha512(prefix + message)
    r_scalar = bytes_to_int(r) % curve25519.order
    
    # 4. Compute R = r * G
    R = r_scalar * curve25519.generator
    
    # 5. Compute challenge
    k = sha512(R.encode() + public_key.encode() + message)
    k_scalar = bytes_to_int(k) % curve25519.order
    
    # 6. Compute signature
    s = (r_scalar + k_scalar * a) % curve25519.order
    
    return R.encode() + s.to_bytes(32)
```

**Security Properties**:
- **Key Size**: 256-bit keys provide 128-bit security (equivalent to 3072-bit RSA)
- **Performance**: Significantly faster than RSA
- **Deterministic Signatures**: EdDSA uses deterministic nonce generation (safer than ECDSA)

## Certificate Validation Algorithms

### X.509 Certificate Path Validation

**Path Building Algorithm**:
```python
def build_certificate_path(target_cert, cert_store, trust_anchors):
    """
    Build certificate path from target certificate to trust anchor
    RFC 4158 - Certificate Path Building
    """
    paths = []
    
    def build_path_recursive(current_cert, current_path, visited):
        # Check if current certificate is a trust anchor
        if is_trust_anchor(current_cert, trust_anchors):
            paths.append(current_path + [current_cert])
            return
        
        # Find potential issuer certificates
        issuers = find_issuer_certificates(current_cert, cert_store)
        
        for issuer_cert in issuers:
            # Avoid loops
            if issuer_cert in visited:
                continue
            
            # Verify signature relationship
            if verify_certificate_signature(current_cert, issuer_cert):
                new_visited = visited.copy()
                new_visited.add(issuer_cert)
                build_path_recursive(
                    issuer_cert, 
                    current_path + [current_cert], 
                    new_visited
                )
    
    # Start path building
    build_path_recursive(target_cert, [], set())
    
    return paths

def validate_certificate_path(cert_path, trust_anchors, validation_time):
    """
    Validate certificate path according to RFC 5280
    """
    if not cert_path:
        return False, "Empty certificate path"
    
    # 1. Verify trust anchor
    trust_anchor = cert_path[-1]
    if not is_trust_anchor(trust_anchor, trust_anchors):
        return False, "Path does not end with trust anchor"
    
    # 2. Validate each certificate in path
    for i in range(len(cert_path) - 1):
        subject_cert = cert_path[i]
        issuer_cert = cert_path[i + 1]
        
        # a. Verify signature
        if not verify_certificate_signature(subject_cert, issuer_cert):
            return False, f"Invalid signature on certificate {i}"
        
        # b. Check validity periods
        if not is_certificate_valid_at_time(subject_cert, validation_time):
            return False, f"Certificate {i} not valid at validation time"
        
        # c. Verify issuer/subject name chaining
        if subject_cert.issuer != issuer_cert.subject:
            return False, f"Name chaining broken at certificate {i}"
        
        # d. Check basic constraints
        if not check_basic_constraints(issuer_cert, len(cert_path) - i - 2):
            return False, f"Basic constraints violated by certificate {i+1}"
        
        # e. Check key usage
        if not check_key_usage(issuer_cert, "keyCertSign"):
            return False, f"Certificate {i+1} cannot sign certificates"
    
    # 3. Check revocation status
    for cert in cert_path[:-1]:  # Skip trust anchor
        if is_certificate_revoked(cert):
            return False, f"Certificate {cert.subject} is revoked"
    
    return True, "Certificate path valid"
```

### Certificate Revocation Checking

**CRL (Certificate Revocation List) Processing**:
```python
def process_crl(crl_data, issuer_cert):
    """
    Process Certificate Revocation List according to RFC 5280
    """
    # 1. Parse CRL
    crl = parse_crl(crl_data)
    
    # 2. Verify CRL signature
    if not verify_crl_signature(crl, issuer_cert):
        raise ValueError("Invalid CRL signature")
    
    # 3. Check CRL validity period
    current_time = datetime.utcnow()
    if current_time < crl.this_update or current_time > crl.next_update:
        raise ValueError("CRL not valid at current time")
    
    # 4. Build revocation set
    revoked_serials = set()
    for revoked_cert in crl.revoked_certificates:
        revoked_serials.add(revoked_cert.serial_number)
    
    return revoked_serials

def check_certificate_revocation_crl(certificate, crl_cache):
    """
    Check if certificate is revoked using CRL
    """
    issuer = certificate.issuer
    
    # 1. Get CRL for issuer
    if issuer not in crl_cache:
        crl_url = get_crl_distribution_point(certificate)
        crl_data = download_crl(crl_url)
        issuer_cert = find_certificate_by_subject(issuer)
        crl_cache[issuer] = process_crl(crl_data, issuer_cert)
    
    # 2. Check if certificate serial is in revoked list
    return certificate.serial_number in crl_cache[issuer]
```

**OCSP (Online Certificate Status Protocol)**:
```python
def ocsp_request(certificate, issuer_certificate):
    """
    Create OCSP request according to RFC 6960
    """
    # 1. Create certificate ID
    cert_id = create_cert_id(certificate, issuer_certificate)
    
    # 2. Build OCSP request
    request = OCSPRequest()
    request.cert_id = cert_id
    request.nonce = os.urandom(16)  # Optional anti-replay
    
    return request.encode()

def ocsp_verify_response(response_data, ocsp_responder_cert):
    """
    Verify OCSP response signature and extract status
    """
    # 1. Parse response
    response = parse_ocsp_response(response_data)
    
    # 2. Verify response signature
    if not verify_ocsp_signature(response, ocsp_responder_cert):
        raise ValueError("Invalid OCSP response signature")
    
    # 3. Check response freshness
    if not is_ocsp_response_fresh(response):
        raise ValueError("OCSP response is stale")
    
    # 4. Extract certificate status
    return response.cert_status

def check_certificate_revocation_ocsp(certificate, issuer_certificate):
    """
    Check certificate revocation status using OCSP
    """
    # 1. Get OCSP responder URL
    ocsp_url = get_ocsp_url(certificate)
    
    # 2. Create and send OCSP request
    request = ocsp_request(certificate, issuer_certificate)
    response_data = send_ocsp_request(ocsp_url, request)
    
    # 3. Find OCSP responder certificate
    ocsp_responder_cert = find_ocsp_responder_certificate(response_data)
    
    # 4. Verify response and get status
    status = ocsp_verify_response(response_data, ocsp_responder_cert)
    
    return status == "revoked"
```

## Key Exchange Algorithms

### ECDH (Elliptic Curve Diffie-Hellman)

```python
def ecdh_key_exchange():
    """
    Elliptic Curve Diffie-Hellman key exchange
    """
    # Alice's side
    alice_private = random_int(1, curve.order - 1)
    alice_public = alice_private * curve.generator
    
    # Bob's side
    bob_private = random_int(1, curve.order - 1)
    bob_public = bob_private * curve.generator
    
    # Shared secret computation
    alice_shared = alice_private * bob_public
    bob_shared = bob_private * alice_public
    
    # Both should be equal
    assert alice_shared == bob_shared
    
    # Derive symmetric key from shared point
    shared_secret = alice_shared.x.to_bytes(32)
    symmetric_key = sha256(shared_secret)
    
    return symmetric_key
```

### RSA Key Transport

```python
def rsa_key_transport(symmetric_key, recipient_public_key):
    """
    RSA key transport (encrypt symmetric key with RSA)
    """
    # Encrypt symmetric key with recipient's RSA public key
    encrypted_key = rsa_oaep_encrypt(symmetric_key, recipient_public_key)
    
    return encrypted_key

def rsa_key_transport_decrypt(encrypted_key, recipient_private_key):
    """
    Decrypt transported symmetric key
    """
    symmetric_key = rsa_oaep_decrypt(encrypted_key, recipient_private_key)
    
    return symmetric_key
```

## Hash Algorithms for PKI

### Secure Hash Algorithms

**SHA-256 Implementation Concept**:
```python
def sha256_compress(message_block, hash_values):
    """
    SHA-256 compression function (simplified concept)
    """
    # Initialize working variables
    a, b, c, d, e, f, g, h = hash_values
    
    # Prepare message schedule
    w = prepare_message_schedule(message_block)
    
    # Main compression loop
    for t in range(64):
        T1 = h + sigma1(e) + ch(e, f, g) + K[t] + w[t]
        T2 = sigma0(a) + maj(a, b, c)
        
        h = g
        g = f
        f = e
        e = (d + T1) % (2**32)
        d = c
        c = b
        b = a
        a = (T1 + T2) % (2**32)
    
    # Add compressed chunk to hash values
    return [(a + hash_values[0]) % (2**32),
            (b + hash_values[1]) % (2**32),
            (c + hash_values[2]) % (2**32),
            (d + hash_values[3]) % (2**32),
            (e + hash_values[4]) % (2**32),
            (f + hash_values[5]) % (2**32),
            (g + hash_values[6]) % (2**32),
            (h + hash_values[7]) % (2**32)]
```

**Hash Algorithm Selection**:
```python
def select_hash_algorithm(security_level):
    """
    Select appropriate hash algorithm for security level
    """
    hash_algorithms = {
        80: "SHA-1",      # Deprecated - only for legacy compatibility
        112: "SHA-224",   # 112-bit security
        128: "SHA-256",   # 128-bit security (recommended minimum)
        192: "SHA-384",   # 192-bit security
        256: "SHA-512"    # 256-bit security
    }
    
    return hash_algorithms.get(security_level, "SHA-256")
```

## Performance Analysis

### Algorithm Performance Comparison

```python
# Typical performance characteristics (operations per second)
ALGORITHM_PERFORMANCE = {
    "RSA-2048": {
        "key_generation": 10,      # per second
        "signature": 500,          # per second
        "verification": 15000,     # per second
        "encryption": 15000,       # per second
        "decryption": 500          # per second
    },
    "ECDSA-P256": {
        "key_generation": 1000,    # per second
        "signature": 5000,         # per second
        "verification": 2000,      # per second
    },
    "Ed25519": {
        "key_generation": 10000,   # per second
        "signature": 50000,        # per second
        "verification": 15000,     # per second
    }
}

def benchmark_algorithm(algorithm, operation, iterations=1000):
    """
    Benchmark cryptographic algorithm performance
    """
    start_time = time.time()
    
    for _ in range(iterations):
        perform_operation(algorithm, operation)
    
    end_time = time.time()
    total_time = end_time - start_time
    ops_per_second = iterations / total_time
    
    return ops_per_second
```

### Complexity Analysis

**Certificate Path Validation Complexity**:
- **Time Complexity**: O(n × m × k) where:
  - n = number of certificates in store
  - m = maximum path length
  - k = average signature verification time
- **Space Complexity**: O(p × m) where p = number of possible paths
- **Optimization**: Use certificate indexing and caching

**Revocation Checking Complexity**:
- **CRL Processing**: O(r) where r = number of revoked certificates
- **OCSP Request**: O(1) per certificate
- **Certificate Transparency**: O(log n) for Merkle tree proof verification

## Algorithm Security Considerations

### Common Implementation Vulnerabilities

```python
def secure_random_generation():
    """
    Proper random number generation for cryptographic keys
    """
    # WRONG: Predictable random number generation
    # random.seed(time.time())
    # private_key = random.randint(1, curve.order - 1)
    
    # CORRECT: Use cryptographically secure random number generator
    private_key = secrets.randbelow(curve.order - 1) + 1
    
    return private_key

def secure_signature_verification():
    """
    Proper signature verification implementation
    """
    def verify_signature(message, signature, public_key):
        # WRONG: Early return on invalid signature format
        # if not is_valid_format(signature):
        #     return False
        
        # CORRECT: Use constant-time comparison to prevent timing attacks
        try:
            expected_signature = compute_signature(message, public_key)
            return constant_time_compare(signature, expected_signature)
        except:
            # Return False in constant time even on errors
            return False
```

### Side-Channel Attack Prevention

```python
def constant_time_compare(a, b):
    """
    Compare two byte strings in constant time to prevent timing attacks
    """
    if len(a) != len(b):
        return False
    
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    
    return result == 0

def secure_modular_exponentiation(base, exponent, modulus):
    """
    Secure modular exponentiation resistant to side-channel attacks
    """
    # Use Montgomery ladder or similar constant-time algorithm
    result = 1
    base = base % modulus
    
    # Process exponent bits in constant time
    for bit_position in range(exponent.bit_length()):
        # Always perform both squaring and multiplication
        result_squared = (result * result) % modulus
        result_multiplied = (result_squared * base) % modulus
        
        # Select result based on exponent bit (constant time)
        bit = (exponent >> bit_position) & 1
        result = constant_time_select(bit, result_multiplied, result_squared)
    
    return result
```

## Files in This Section

- `rsa-algorithms.md` - RSA key generation, encryption, and signature algorithms
- `elliptic-curve-algorithms.md` - ECDSA, EdDSA, and ECDH implementations
- `certificate-validation.md` - Path building and validation algorithms
- `revocation-checking.md` - CRL processing and OCSP protocols
- `hash-algorithms.md` - Cryptographic hash functions and security analysis
- `key-exchange.md` - Key agreement and transport protocols
- `performance-optimization.md` - Algorithm optimization and benchmarking
- `security-considerations.md` - Implementation vulnerabilities and countermeasures

---

**Next**: [Failure Models - Attack Vectors and Vulnerabilities](../04-failure-models/README.md) ⚠️  
**Previous**: [Mathematical Toolkit](../02-math-toolkit/README.md) 🧮  
**See Also**: [Experiments](../05-experiments/README.md) for algorithm demonstrations 🧪