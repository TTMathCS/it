# Core Model: PKI as a Mathematical Trust Framework

> *"The security of public key cryptography depends on the computational intractability of certain mathematical problems."* - Alfred Menezes, Handbook of Applied Cryptography

## Overview

PKI revolutionizes digital security by treating trust as a **mathematical construct** rather than a social agreement. This section explores the elegant mathematical model that enables PKI's unique capabilities for scalable, verifiable digital trust.

## The Fundamental Mathematical Model

PKI models digital trust as a **Hierarchical Directed Acyclic Graph (HDAG)** with **cryptographic verification** through asymmetric cryptography. Every PKI deployment is essentially a trust tree where each node represents a certificate and edges represent cryptographic signatures.

### Visual Representation
```
                    PKI Trust Architecture
                         |
    ┌────────────────────┼────────────────────┐
    │                    │                    │
    v                    v                    v
[Certificate Store]  [Trust Anchors]    [Validation Engine]
    │                    │                    │
    ├─ Root CAs          ├─ Root Certificates └─ Path Building
    ├─ Intermediate CAs  ├─ Policy Constraints   ├─ Chain Validation
    ├─ End Entity Certs  └─ Trust Points         └─ Revocation Check
    └─ Revoked Certs
```

**Interactive Demo**: 🎮 [PKI Certificate Path Visualizer](https://crt.sh/graph)

## Core Axioms

These six mathematical principles form the foundation of PKI design:

### 1. **Asymmetric Key Relationships** 🔑
Every entity has a mathematically related public-private key pair.

**Mathematical Expression**: `∀ entity e: ∃ (pk, sk) where pk = f(sk) ∧ Decrypt(Encrypt(m, pk), sk) = m`

**Real-world Analogy**: Like a lock and key, where the lock (public key) can be freely shared but only the private key can unlock messages.

**Implementation Detail**: Key pairs are generated using computationally hard mathematical problems (factorization, discrete logarithm, elliptic curve discrete logarithm).

### 2. **Certificate Binding** 📜
Certificates cryptographically bind identity information to public keys.

**Mathematical Expression**: `Certificate = Sign(Identity || PublicKey || Validity || Extensions, CA_PrivateKey)`

**Example**:
```bash
# Certificate contains cryptographically signed assertion
Subject: CN=alice@company.com, O=Company Inc, C=US
Public Key: RSA 2048-bit (e=65537, n=0x9a8b...)
Signature: RSA-SHA256 (signed by Intermediate CA)
```

**Security Property**: Tampering with any certificate field invalidates the signature

### 3. **Hierarchical Trust Propagation** ⛓️
Trust relationships form a directed acyclic graph with cryptographic verification.

**Mathematical Expression**: `Trust(Entity) = ∃ Path(Root → Entity) where ∀ edge: Valid_Signature(child, parent)`

**Trust Chain Property**: 
```
Trust(Root CA) ∧ Valid_Signature(Intermediate, Root) ∧ Valid_Signature(End_Entity, Intermediate)
⟹ Trust(End_Entity)
```

**Graph Theory**: PKI trust relationships form a forest of directed trees rooted at trust anchors.

### 4. **Temporal Validity** ⏰
Certificates have mathematically defined validity periods with precise temporal boundaries.

**Mathematical Expression**: `Valid(cert, t) = (cert.notBefore ≤ t ≤ cert.notAfter) ∧ ¬Revoked(cert, t)`

**Temporal Logic**: Certificate validity follows strict temporal ordering with no gaps or overlaps in renewal chains.

**Practical Effect**: Expired certificates are cryptographically unusable, preventing stale credential attacks.

### 5. **Revocation Immediacy** 🚫
Compromised certificates can be immediately invalidated through cryptographic revocation mechanisms.

**Mathematical Expression**: `Revoked(cert) = cert.serialNumber ∈ CRL(t) ∨ OCSP_Response(cert) = revoked`

**Real-time Property**: Revocation status can be verified in real-time, providing immediate security response.

**Cryptographic Guarantee**: Revoked certificates fail signature verification even if otherwise valid.

### 6. **Non-Repudiation Assurance** ✍️
Digital signatures provide mathematical proof of origin and integrity.

**Mathematical Expression**: `Sign(message, private_key) = signature where Verify(message, signature, public_key) = true`

**Legal Implication**: Digital signatures provide stronger evidence than handwritten signatures in many jurisdictions.

**Cryptographic Strength**: Based on computational complexity theory - breaking signatures requires solving hard mathematical problems.

## Formal Mathematical Model

### PKI Structure Definition
```
PKI = (Certificates, TrustAnchors, RevocationData, ValidationPolicy)

Certificates = {
  X509Certificate: (
    subject: DistinguishedName,
    publicKey: AsymmetricKey,
    issuer: DistinguishedName,
    validity: TimeInterval,
    signature: DigitalSignature,
    extensions: PolicyConstraints[]
  )
}

TrustAnchors = {
  RootCA: self_signed_certificate
  IntermediateCA: certificate_chain_to_root
}

RevocationData = {
  CRL: (issuer, revoked_certificates[], next_update_time),
  OCSP: real_time_revocation_service
}

ValidationPolicy = {
  path_length_constraints: Integer,
  key_usage_restrictions: BitString,
  extended_key_usage: OIDSet,
  name_constraints: NameSpaceSet
}
```

### Certificate Hierarchy
```
                    Root CA
                       |
         ┌─────────────┼─────────────┐
         │             │             │
   Intermediate    Intermediate  Cross-Cert
        CA              CA           CA
         │             │             │
    ┌────┼────┐   ┌────┼────┐       │
    │    │    │   │    │    │       │
   SSL  Code Email Device User   External
  Cert  Sign Cert  Cert  Cert     Root
```

### Cryptographic Operations
```
KeyGeneration: () → (PublicKey, PrivateKey)
SignatureGeneration: (Message, PrivateKey) → Signature  
SignatureVerification: (Message, Signature, PublicKey) → Boolean
CertificateGeneration: (SubjectInfo, SubjectPublicKey, IssuerPrivateKey) → Certificate
PathValidation: (Certificate, TrustAnchor, Policy) → Boolean
```

## Trust Model Analysis

### Mathematical Properties

**1. Transitivity**: `Trust(A,C) if Trust(A,B) ∧ Trust(B,C)`
- Foundation of certificate chain validation
- Enables hierarchical delegation of trust authority
- Requires unbroken cryptographic chain

**2. Non-Symmetry**: `Trust(A,B) ⟹ Trust(B,A)` (generally false)
- Trust flows down the hierarchy, not up
- Subordinate CAs cannot issue certificates for their parents
- Prevents privilege escalation attacks

**3. Temporal Consistency**: `Valid(cert, t1) ∧ Valid(cert, t2) ∧ t1 < t2 ⟹ Valid(cert, ∀t ∈ [t1,t2])`  
- Certificate validity is temporally continuous
- No sudden validity gaps in properly managed PKI
- Supports long-term signature validation

### Security Model

**Computational Security**: Based on computational complexity assumptions
```
RSA Security: Difficulty of integer factorization
ECC Security: Elliptic curve discrete logarithm problem  
DSA Security: Discrete logarithm problem in finite fields
```

**Information Theoretic Properties**:
- Perfect forward secrecy in key exchange protocols
- Collision resistance in hash functions (2^(n/2) attack complexity)
- Birthday paradox considerations in certificate serial numbers

**Attack Resistance**:
- **Chosen Plaintext Attack**: Public key operations are secure
- **Key Recovery Attack**: Computationally infeasible with sufficient key sizes
- **Signature Forgery**: Requires solving underlying hard mathematical problem

## Implementation Considerations

### Performance Characteristics

**Certificate Validation Complexity**:
- Path building: O(n×m) where n=certificates, m=possible paths
- Signature verification: O(log k) where k=key size in bits  
- Revocation checking: O(1) for OCSP, O(n) for CRL parsing

**Storage Requirements**:
- Root certificates: ~1-2 KB each (typically <100 total)
- Intermediate certificates: ~2-4 KB each  
- End entity certificates: ~2-8 KB each
- CRLs: Variable (10 KB to 10+ MB depending on CA size)

### Scalability Analysis

**Trust Anchor Distribution**: O(1) - Root certificates change infrequently
**Certificate Issuance**: O(n) - Scales linearly with number of entities
**Path Validation**: O(d) - Scales with maximum path depth (typically 3-4)
**Revocation Checking**: O(log n) - OCSP responses or CRL delta processing

## Real-World Mathematical Constraints

### Key Size Evolution
```
Year    RSA     ECC     Security Level    Quantum Resistance
2024    2048    256     112-bit          No
2030    3072    384     128-bit          No  
2035+   15360   512     256-bit          Transitional
Future  N/A     N/A     Post-Quantum     Yes (Lattice/Hash-based)
```

### Certificate Lifetime Optimization
```
Root CA: 20-30 years (balance security vs operational continuity)
Intermediate CA: 3-10 years (operational flexibility)
SSL Certificates: 90 days - 2 years (automation vs management overhead)  
Code Signing: 1-3 years (balance security vs developer workflow)
```

## Files in This Section

- `trust-model.md` - Mathematical analysis of PKI trust relationships
- `certificate-formats.md` - X.509 structure and ASN.1 encoding
- `cryptographic-primitives.md` - RSA, ECDSA, and post-quantum algorithms
- `validation-algorithms.md` - Path building and certificate chain verification
- `revocation-mechanisms.md` - CRL, OCSP, and Certificate Transparency
- `performance-analysis.md` - Computational complexity and optimization strategies

## Mathematical Proofs

### Theorem 1: Certificate Chain Validation Completeness
If a valid certificate chain exists from a trust anchor to an end entity certificate, the path validation algorithm will find it.

**Proof Sketch**: The path building algorithm performs a breadth-first search over the certificate graph, ensuring all possible paths are explored up to maximum depth constraints.

### Theorem 2: Signature Verification Correctness  
A digital signature verifies successfully if and only if it was created with the corresponding private key.

**Proof**: Based on the mathematical properties of the underlying asymmetric cryptographic algorithm (RSA, ECDSA, etc.) and the collision resistance of the hash function.

### Theorem 3: Revocation Timeliness Guarantee
A certificate revoked at time t will be detected as invalid by time t + max_revocation_propagation_delay.

**Proof**: Follows from the bounded propagation time of revocation information through CRL publication or OCSP response caching policies.

---

**Next**: [Mathematical Toolkit - Number Theory and Cryptographic Protocols](../02-math-toolkit/README.md) 🧮  
**Previous**: [Main PKI Overview](../README.md) 🏠  
**See Also**: [PKI Algorithms](../03-algorithms/README.md) for implementation details 🔧