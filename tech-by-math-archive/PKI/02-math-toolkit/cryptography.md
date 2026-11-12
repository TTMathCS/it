# Cryptographic Foundations of PKI

## Introduction

Public Key Infrastructure (PKI) is fundamentally built on asymmetric cryptography, which enables secure communication between parties who have never met and scalable identity verification. Understanding these cryptographic foundations explains why PKI can provide authentication, integrity, confidentiality, and non-repudiation at global scale.

## Public Key Cryptography: The Mathematical Foundation

### RSA Algorithm: PKI's Workhorse

**RSA** (Rivest-Shamir-Adleman) is the most widely used asymmetric cryptographic algorithm in PKI systems.

**Mathematical Foundation**:
- **Key Generation**: Based on the difficulty of factoring large composite numbers
- **Security**: Relies on the **Integer Factorization Problem**
- **Key Sizes**: 2048-bit (current standard), 3072-bit (future), 4096-bit (high security)

**Key Generation Process**:
```
1. Choose two large prime numbers: p, q (typically 1024 bits each for RSA-2048)
2. Compute modulus: n = p × q
3. Compute Euler's totient: φ(n) = (p-1)(q-1)
4. Choose public exponent: e (commonly 65537 = 2^16 + 1)
5. Compute private exponent: d ≡ e^(-1) (mod φ(n))

Public Key: (n, e)
Private Key: (n, d)
```

**Mathematical Properties**:
- **Encryption**: `C = M^e mod n`
- **Decryption**: `M = C^d mod n`
- **Key Relationship**: `e × d ≡ 1 (mod φ(n))`

**Implementation Example**:
```python
import hashlib
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

def generate_rsa_keypair(key_size=2048):
    """Generate RSA key pair for PKI use"""
    key = RSA.generate(key_size)
    public_key = key.publickey()
    return public_key, key

def sign_certificate(certificate_data, private_key):
    """Sign certificate using RSA-SHA256"""
    hash_obj = hashlib.sha256(certificate_data.encode('utf-8'))
    signature = pkcs1_15.new(private_key).sign(hash_obj)
    return signature

def verify_certificate(certificate_data, signature, public_key):
    """Verify certificate signature"""
    hash_obj = hashlib.sha256(certificate_data.encode('utf-8'))
    try:
        pkcs1_15.new(public_key).verify(hash_obj, signature)
        return True
    except (ValueError, TypeError):
        return False
```

### Elliptic Curve Cryptography (ECC)

**ECC** provides equivalent security to RSA with smaller key sizes, making it ideal for mobile devices and IoT applications.

**Mathematical Foundation**:
- **Curve Equation**: `y² = x³ + ax + b (mod p)`
- **Security**: Based on **Elliptic Curve Discrete Logarithm Problem (ECDLP)**
- **Efficiency**: 256-bit ECC ≈ 3072-bit RSA security

**Popular Curves in PKI**:
1. **P-256 (secp256r1)**: NIST standard, widely supported
2. **P-384 (secp384r1)**: Higher security level
3. **Curve25519**: High performance, designed for security

**Key Size Comparison**:
```
Security Level | RSA    | ECC
80-bit        | 1024   | 160
112-bit       | 2048   | 224
128-bit       | 3072   | 256
192-bit       | 7680   | 384
256-bit       | 15360  | 512
```

## Digital Signatures: Authenticity and Integrity

### Digital Signature Algorithm (DSA)

Digital signatures provide **authentication**, **integrity**, and **non-repudiation** in PKI.

**RSA Signatures (PKCS#1)**:
```
1. Hash message: h = H(message)
2. Sign hash: s = h^d mod n
3. Verify: h' = s^e mod n, check h' = H(message)
```

**ECDSA (Elliptic Curve DSA)**:
```
1. Hash message: h = H(message)
2. Generate random k
3. Compute r = (k × G).x mod n
4. Compute s = k^(-1) × (h + r × private_key) mod n
5. Signature: (r, s)
```

**Security Properties**:
- **Unforgeability**: Only private key holder can create valid signatures
- **Integrity**: Any message modification invalidates signature
- **Non-repudiation**: Mathematical proof of origin

### Hash Functions in PKI

**SHA-256**: Current standard for certificate signatures
- **Output**: 256 bits
- **Security**: ~128-bit security level
- **Performance**: Optimized for hardware and software

**SHA-384/SHA-512**: Higher security variants
- **Use Cases**: High-security applications, long-term certificates
- **Output**: 384 bits / 512 bits respectively

**Hash Function Properties Critical for PKI**:
1. **Collision Resistance**: Infeasible to find two inputs with same hash
2. **Preimage Resistance**: Given hash, infeasible to find original input
3. **Second Preimage Resistance**: Given input, infeasible to find different input with same hash

## Certificate Cryptographic Structure

### X.509 Certificate Format

**ASN.1 Structure**:
```
Certificate ::= SEQUENCE {
    tbsCertificate       TBSCertificate,
    signatureAlgorithm   AlgorithmIdentifier,
    signatureValue       BIT STRING
}

TBSCertificate ::= SEQUENCE {
    version              [0] Version OPTIONAL,
    serialNumber         CertificateSerialNumber,
    signature            AlgorithmIdentifier,
    issuer               Name,
    validity             Validity,
    subject              Name,
    subjectPublicKeyInfo SubjectPublicKeyInfo,
    ...
}
```

**Cryptographic Binding**:
```
Certificate = {
    ToBeSigned: {
        Subject: "CN=example.com,O=Company,C=US"
        PublicKey: RSA-2048 public key
        Validity: Not Before / Not After dates
        Extensions: Key Usage, SAN, etc.
    }
    Signature: RSA-SHA256(ToBeSigned, CA_PrivateKey)
}
```

### Certificate Chain Validation

**Chain Building Algorithm**:
```python
def build_certificate_chain(end_entity_cert, cert_store):
    """Build and validate certificate chain"""
    chain = [end_entity_cert]
    current_cert = end_entity_cert
    
    while not is_self_signed(current_cert):
        issuer_cert = find_issuer(current_cert, cert_store)
        if not issuer_cert:
            raise ValidationError("Issuer certificate not found")
        
        if not verify_signature(current_cert, issuer_cert.public_key):
            raise ValidationError("Invalid signature")
        
        chain.append(issuer_cert)
        current_cert = issuer_cert
    
    return chain

def validate_certificate_chain(chain, trust_anchors):
    """Validate complete certificate chain"""
    # Check trust anchor
    root_cert = chain[-1]
    if root_cert not in trust_anchors:
        raise ValidationError("Untrusted root certificate")
    
    # Validate each certificate in chain
    for cert in chain:
        validate_certificate_constraints(cert)
        check_certificate_revocation(cert)
        verify_temporal_validity(cert)
    
    return True
```

## Key Management and Cryptographic Lifecycle

### Key Generation and Storage

**Cryptographic Requirements**:
1. **Entropy**: Keys must be generated with sufficient randomness
2. **Key Strength**: Appropriate key sizes for security requirements
3. **Secure Storage**: Private keys protected against unauthorized access

**Hardware Security Modules (HSMs)**:
- **FIPS 140-2 Level 3/4**: Tamper-resistant hardware
- **Key Generation**: Hardware random number generators
- **Signing**: Private keys never leave HSM
- **Performance**: Dedicated cryptographic processors

**Key Escrow and Recovery**:
```
Key Escrow Process:
1. Generate key pair in secure environment
2. Split private key using secret sharing (Shamir's scheme)
3. Store shares in separate secure locations
4. Require k-of-n shares for key recovery
```

### Cryptographic Agility in PKI

**Algorithm Migration Strategy**:
```
Phase 1: Preparation
- Deploy new algorithm support in CA systems
- Update certificate profiles and policies
- Test interoperability with existing infrastructure

Phase 2: Transition
- Issue certificates with new algorithms
- Maintain support for legacy algorithms
- Cross-certify between old and new root CAs

Phase 3: Migration
- Phase out weak algorithms
- Revoke certificates using deprecated algorithms
- Update all systems to use new algorithms
```

**Post-Quantum Cryptography Preparation**:
- **Timeline**: NIST standardization complete (2024)
- **Algorithms**: CRYSTALS-Kyber (encryption), CRYSTALS-Dilithium (signatures)
- **Key Sizes**: Significantly larger than current algorithms
- **Migration Plan**: Hybrid certificates during transition period

## Advanced Cryptographic Protocols

### Certificate Transparency (CT)

**Merkle Tree Structure**:
```
CT Log = Merkle Tree of Certificates
├── Root Hash (signed by log operator)
├── Intermediate Nodes
└── Leaf Nodes (individual certificates)

Properties:
- Append-only: Cannot modify past entries
- Publicly verifiable: Anyone can audit the log
- Cryptographic proof: Inclusion/consistency proofs
```

**Signed Certificate Timestamps (SCTs)**:
```python
def generate_sct(certificate, log_private_key):
    """Generate Signed Certificate Timestamp"""
    timestamp = current_time_ms()
    
    data_to_sign = {
        'version': 1,
        'log_id': log_public_key_hash,
        'timestamp': timestamp,
        'extensions': '',
        'certificate': certificate
    }
    
    signature = sign(serialize(data_to_sign), log_private_key)
    
    return {
        'version': 1,
        'log_id': log_public_key_hash,
        'timestamp': timestamp,
        'signature': signature
    }
```

### Online Certificate Status Protocol (OCSP)

**Cryptographic OCSP Response**:
```
OCSPResponse ::= SEQUENCE {
    responseStatus    OCSPResponseStatus,
    responseBytes     ResponseBytes OPTIONAL
}

ResponseData ::= SEQUENCE {
    version           [0] Version OPTIONAL,
    responderID       ResponderID,
    producedAt        Time,
    responses         SEQUENCE OF SingleResponse,
    responseExtensions [1] Extensions OPTIONAL
}

-- Response is cryptographically signed
signature = RSA-SHA256(ResponseData, OCSP_Responder_PrivateKey)
```

## Security Analysis and Threat Model

### Cryptographic Threat Vectors

**Private Key Compromise**:
- **Impact**: Complete loss of security for affected certificates
- **Mitigation**: Key escrow, hardware protection, certificate revocation
- **Detection**: Anomalous certificate issuance, behavioral analysis

**Weak Random Number Generation**:
- **Vulnerability**: Predictable keys vulnerable to attack
- **Examples**: Debian OpenSSL bug (2008), RSA key factorization
- **Prevention**: Certified random number generators, entropy validation

**Algorithm Vulnerabilities**:
- **SHA-1 Deprecation**: Collision attacks demonstrated
- **RSA Key Sizes**: 1024-bit keys factored, 2048-bit minimum
- **Quantum Threats**: Shor's algorithm breaks RSA/ECC

### Cryptographic Best Practices

**Key Generation**:
```python
# Secure key generation example
import secrets
from cryptography.hazmat.primitives.asymmetric import rsa

def secure_key_generation():
    """Generate cryptographically secure RSA key"""
    # Use system's secure random number generator
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    return private_key

def validate_key_strength(public_key):
    """Validate RSA public key parameters"""
    if public_key.key_size < 2048:
        raise ValueError("Key size too small")
    
    if public_key.public_numbers().e not in [3, 65537]:
        raise ValueError("Insecure public exponent")
    
    return True
```

**Signature Validation**:
```python
def secure_signature_verification(certificate, signature, ca_public_key):
    """Comprehensive signature verification"""
    
    # 1. Check certificate format
    validate_certificate_format(certificate)
    
    # 2. Verify cryptographic signature
    if not verify_signature(certificate.tbs_certificate, signature, ca_public_key):
        raise ValidationError("Invalid cryptographic signature")
    
    # 3. Check algorithm strength
    if certificate.signature_algorithm.name == 'sha1WithRSAEncryption':
        raise ValidationError("Deprecated signature algorithm")
    
    # 4. Validate key parameters
    validate_key_strength(ca_public_key)
    
    return True
```

## Performance and Implementation Considerations

### Cryptographic Performance Optimization

**RSA Performance Characteristics**:
- **Key Generation**: Expensive (seconds for 2048-bit)
- **Signature Generation**: Moderate (private key operations)
- **Signature Verification**: Fast (public key operations)
- **Optimization**: Chinese Remainder Theorem for private key operations

**ECC Performance Advantages**:
- **Key Generation**: Faster than equivalent-strength RSA
- **Signature Generation**: Significantly faster
- **Bandwidth**: Smaller signatures and certificates
- **Mobile-Friendly**: Lower computational requirements

**Hardware Acceleration**:
- **AES-NI**: Hardware AES acceleration
- **Intel SHA Extensions**: SHA acceleration
- **ARM TrustZone**: Secure cryptographic execution
- **HSM Integration**: Dedicated cryptographic hardware

### Cryptographic Implementation Security

**Side-Channel Attack Prevention**:
```python
def constant_time_comparison(a, b):
    """Constant-time string comparison"""
    if len(a) != len(b):
        return False
    
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    
    return result == 0

def secure_random_padding():
    """Generate cryptographically secure padding"""
    return secrets.token_bytes(32)
```

**Memory Protection**:
- **Key Zeroization**: Clear sensitive data from memory
- **Protected Memory**: Use secure memory allocation
- **Stack Protection**: Guard against buffer overflows

This cryptographic foundation enables PKI to provide scalable, secure digital identity and trust services. The mathematical properties of these algorithms ensure that PKI can deliver authentication, integrity, confidentiality, and non-repudiation at global scale while remaining computationally efficient and implementationally secure.