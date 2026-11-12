# PKI Experiments and Demonstrations

## Overview

This directory contains practical demonstrations of PKI cryptographic operations and mathematical principles. These experiments help illustrate the theoretical concepts from the core model and math toolkit through working code examples.

## Available Experiments

### 1. Certificate Validation Demo (`certificate_validation_demo.py`)

A comprehensive demonstration of PKI certificate validation processes including:

- **Certificate Generation**: Creates a complete certificate hierarchy (Root CA → Intermediate CA → End Entity)
- **Chain Building**: Demonstrates how certificate chains are constructed from end entity to root
- **Signature Verification**: Shows cryptographic signature validation using RSA/SHA-256
- **Trust Anchor Management**: Illustrates how root CAs are stored and used for validation
- **Revocation Checking**: Simulates certificate revocation list (CRL) checking
- **Hash Integrity**: Demonstrates tamper detection using cryptographic hashes
- **Digital Signatures**: Shows signature creation and verification processes

**Key Features**:
- Real X.509 certificate generation using industry-standard formats
- Complete certificate chain validation algorithm implementation  
- Tamper detection demonstrations showing hash avalanche effects
- Revocation simulation showing immediate security response
- Educational output with step-by-step validation results

**Mathematical Concepts Demonstrated**:
- RSA key generation and cryptographic operations
- SHA-256 hash function properties and collision resistance
- Digital signature algorithms (RSA-PKCS#1)
- Certificate chain trust propagation mathematics
- Modular arithmetic in cryptographic operations

## Requirements

### Python Dependencies

```bash
# Core cryptography library
pip install cryptography>=3.4.8

# Standard library modules (included with Python)
import hashlib
import hmac
import base64
import json
from datetime import datetime, timezone, timedelta
import secrets
```

### System Requirements

- **Python**: 3.7 or higher
- **Operating System**: Cross-platform (Windows, macOS, Linux)
- **Memory**: Minimum 512MB RAM for RSA key generation
- **CPU**: Any modern processor (RSA operations are CPU-intensive)

## Running the Experiments

### Certificate Validation Demo

```bash
# Navigate to experiments directory
cd PKI/05-experiments

# Run the comprehensive demo
python certificate_validation_demo.py
```

**Expected Output**:
```
PKI CERTIFICATE VALIDATION DEMO
============================================================
This demo illustrates core PKI cryptographic operations:
1. Certificate chain building and validation
2. Digital signature verification  
3. Hash integrity checking
4. Trust anchor management

Generating demo certificate hierarchy...
✓ Certificate hierarchy generated
Added trust anchor: Demo Root CA

=== VALIDATING CERTIFICATE CHAIN (3 certificates) ===
✓ Root CA is trusted: Demo Root CA

Validating certificate 1/3: demo.example.com
  ✓ Certificate is within validity period
  ✓ Certificate is not revoked
  ✓ Signature verification successful

Validating certificate 2/3: Demo Intermediate CA
  ✓ Certificate is within validity period
  ✓ Certificate is not revoked
  ✓ Signature verification successful

Validating certificate 3/3: Demo Root CA
  ✓ Certificate is within validity period
  ✓ Certificate is not revoked

✓ CERTIFICATE CHAIN VALIDATION SUCCESSFUL

============================================================
CERTIFICATE REVOCATION DEMONSTRATION
============================================================
Revoking intermediate certificate...
Revoked certificate with serial: 1234567890
✓ Revocation correctly detected: Certificate is revoked (serial: 1234567890)

============================================================
HASH INTEGRITY DEMONSTRATION
============================================================
Original data: Certificate: CN=demo.example.com, Valid=2025-2026
SHA-256 hash:  a1b2c3d4e5f6...

Tampered data: Certificate: CN=evil.example.com, Valid=2025-2026  
SHA-256 hash:  f6e5d4c3b2a1...

Integrity check: FAIL - TAMPERING DETECTED
Different bits: 128/256 (50.0%)

============================================================
DIGITAL SIGNATURE DEMONSTRATION
============================================================
Message to sign: This certificate is issued by Demo CA to demo.example.com
Signature created: MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
✓ Signature verification: VALID
✓ Tampered message verification: CORRECTLY REJECTED

============================================================
DEMO COMPLETED SUCCESSFULLY
============================================================
Key takeaways:
• PKI uses mathematical foundations to provide cryptographic security
• Certificate chains enable scalable trust relationships
• Digital signatures provide authenticity and integrity  
• Hash functions enable tamper detection
• Revocation mechanisms provide immediate security response
```

## Experiment Details

### Certificate Generation Process

The demo creates a realistic PKI hierarchy:

1. **Root CA Certificate**:
   - 4096-bit RSA key pair for maximum security
   - 20-year validity period (typical for root CAs)
   - Self-signed with CA basic constraints
   - Key usage limited to certificate signing

2. **Intermediate CA Certificate**:
   - 2048-bit RSA key pair (standard for intermediates)
   - 10-year validity period
   - Signed by root CA
   - Path length constraint set to 0 (can only sign end entities)

3. **End Entity Certificate**:
   - 2048-bit RSA key pair
   - 1-year validity period (typical for SSL certificates)
   - Signed by intermediate CA
   - Subject Alternative Name (SAN) extension for DNS names
   - Key usage for digital signature and key encipherment

### Validation Algorithm Implementation

The certificate validation follows RFC 5280 standards:

```python
def validate_certificate_chain(chain):
    """RFC 5280 compliant certificate chain validation"""
    
    # 1. Trust anchor verification
    if root_certificate not in trust_store:
        raise ValidationError("Untrusted root")
    
    # 2. For each certificate in chain:
    for cert in chain:
        # a) Check validity period
        verify_temporal_validity(cert)
        
        # b) Check revocation status  
        check_revocation_status(cert)
        
        # c) Verify cryptographic signature
        verify_signature(cert, issuer_cert)
        
        # d) Validate certificate constraints
        check_basic_constraints(cert)
        check_key_usage(cert)
        
    return VALIDATION_SUCCESS
```

### Cryptographic Operations Demonstrated

**RSA Key Generation**:
```python
# Generate RSA-2048 key pair
private_key = rsa.generate_private_key(
    public_exponent=65537,      # Standard exponent
    key_size=2048,              # NIST recommended minimum
    backend=default_backend()
)
```

**Digital Signature Creation**:
```python  
# Sign certificate data with RSA-SHA256
signature = ca_private_key.sign(
    certificate_data,
    padding.PKCS1v15(),         # PKCS#1 v1.5 padding
    hashes.SHA256()             # SHA-256 hash algorithm
)
```

**Hash Integrity Verification**:
```python
# Compute SHA-256 hash for integrity checking
hash_value = hashlib.sha256(certificate_data).hexdigest()

# Verify integrity by comparing hashes
integrity_valid = (original_hash == current_hash)
```

## Educational Value

### Mathematical Concepts Illustrated

1. **Modular Arithmetic**: RSA operations demonstrate modular exponentiation
2. **Prime Number Theory**: Key generation shows factorization-based security
3. **Hash Functions**: SHA-256 demonstrates avalanche effect and collision resistance
4. **Digital Signatures**: RSA-PKCS#1 shows authentication and non-repudiation
5. **Trust Hierarchies**: Certificate chains demonstrate transitive trust relationships

### Security Properties Demonstrated

1. **Authenticity**: Digital signatures prove certificate origin
2. **Integrity**: Hash functions detect any tampering attempts
3. **Non-Repudiation**: Private key signatures provide mathematical proof
4. **Confidentiality**: Public key encryption (demonstrated in signature verification)
5. **Authorization**: Certificate constraints control usage permissions

### Real-World Applications

The demo simulates actual PKI operations used in:
- **HTTPS/TLS**: Web browser certificate validation
- **Code Signing**: Software authenticity verification
- **Email Security**: S/MIME certificate processing
- **VPN Authentication**: Client certificate validation
- **Document Signing**: PDF and document integrity protection

## Advanced Experiments

### Custom Certificate Extensions

Modify the demo to add custom certificate extensions:

```python
# Add custom extension to certificate
cert = cert.add_extension(
    x509.UnrecognizedExtension(
        oid=x509.ObjectIdentifier("1.2.3.4.5.6.7.8.9"),
        value=b"Custom PKI Demo Extension Data"
    ),
    critical=False
)
```

### Different Cryptographic Algorithms

Experiment with elliptic curve cryptography:

```python
from cryptography.hazmat.primitives.asymmetric import ec

# Generate ECDSA key pair
private_key = ec.generate_private_key(
    ec.SECP256R1(),  # P-256 curve
    default_backend()
)
```

### Certificate Transparency Simulation

Add certificate transparency log simulation:

```python
def add_to_ct_log(certificate):
    """Simulate adding certificate to CT log"""
    merkle_tree_leaf = hash_certificate_for_ct(certificate)
    sct = generate_signed_certificate_timestamp(certificate)
    return sct
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Install cryptography library
   ```bash
   pip install --upgrade cryptography
   ```

2. **RSA Key Generation Slow**: Normal for 4096-bit keys (may take several seconds)

3. **Certificate Validation Fails**: Check system time for validity period issues

### Performance Considerations

- **RSA Key Generation**: 4096-bit keys take significantly longer than 2048-bit
- **Signature Verification**: Public key operations are much faster than private key
- **Hash Operations**: SHA-256 is optimized and very fast for typical certificate sizes

## Further Reading

- **RFC 5280**: Internet X.509 Public Key Infrastructure Certificate and Certificate Revocation List (CRL) Profile
- **RFC 3647**: Internet X.509 Public Key Infrastructure Certificate Policy and Certification Practices Framework
- **NIST SP 800-57**: Recommendations for Key Management
- **PKCS #1**: RSA Cryptography Specifications

These experiments provide hands-on experience with the mathematical and cryptographic foundations that make PKI a cornerstone of modern digital security.