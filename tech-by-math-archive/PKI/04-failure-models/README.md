# PKI Failure Models

> *"The enemy knows the system."* - Shannon's Maxim (Kerckhoffs' Principle)

## Overview

Understanding how PKI can fail is crucial for building robust security systems. This section explores attack vectors, vulnerabilities, and failure modes that can compromise PKI deployments, along with mathematical analysis of attack complexities and mitigation strategies.

## Failure Classification Framework

PKI failures can be systematically categorized based on the component affected and the type of compromise:

### Failure Taxonomy
```
                    PKI Failure Models
                           |
        ┌──────────────────┼──────────────────┐
        │                  │                  │
  Cryptographic      Implementation      Operational
    Failures           Failures          Failures
        │                  │                  │
    ┌───┼───┐          ┌───┼───┐          ┌───┼───┐
   Key  Algorithm     Code  Protocol     CA   Process
  Break  Weakness    Bugs  Flaws        Compromise Errors
```

## Cryptographic Attack Models

### 1. Brute Force Attacks

**RSA Key Factorization**:
```
Attack Complexity: O(exp(∛(64/9 × ln n × ln ln n)))

For RSA-2048: ~2^112 operations (computationally infeasible)
For RSA-1024: ~2^80 operations (borderline feasible with resources)

Time Estimates (assuming 10^12 operations/second):
- RSA-1024: ~38,000 years
- RSA-2048: ~10^21 years
- RSA-3072: ~10^32 years
```

**Elliptic Curve Discrete Logarithm**:
```
Attack Complexity: O(√(πn/2)) using Pollard's rho method

For P-256: ~2^128 operations (computationally infeasible)
For P-224: ~2^112 operations (secure but deprecated)

Time Estimates:
- P-224: ~10^21 years with classical computers
- P-256: ~10^25 years with classical computers
- Both: ~1 week with sufficiently large quantum computer (Shor's algorithm)
```

### 2. Mathematical Weakness Exploitation

**Weak Random Number Generation**:
```python
# Example of predictable ECDSA signatures due to weak randomness
def weak_ecdsa_attack(signatures, public_key, curve):
    """
    Attack ECDSA signatures with repeated or predictable nonces
    """
    # If two signatures use same nonce k:
    # s1 = k^(-1)(h1 + r*d) mod n
    # s2 = k^(-1)(h2 + r*d) mod n
    # 
    # Then: k = (h1 - h2)(s1 - s2)^(-1) mod n
    # And:  d = r^(-1)(s1*k - h1) mod n
    
    for i, sig1 in enumerate(signatures):
        for j, sig2 in enumerate(signatures[i+1:], i+1):
            r1, s1 = sig1.r, sig1.s
            r2, s2 = sig2.r, sig2.s
            
            if r1 == r2:  # Same nonce used!
                h1 = hash_message(sig1.message)
                h2 = hash_message(sig2.message)
                
                # Recover nonce
                k = ((h1 - h2) * mod_inverse(s1 - s2, curve.order)) % curve.order
                
                # Recover private key
                private_key = (mod_inverse(r1, curve.order) * (s1 * k - h1)) % curve.order
                
                return private_key
    
    return None  # Attack failed
```

**Small Subgroup Attacks**:
```python
def small_subgroup_attack(public_key, curve):
    """
    Attack elliptic curve implementations with weak parameter validation
    """
    # Find small order points on the curve
    small_order_points = find_small_order_points(curve)
    
    partial_key_info = {}
    
    for point in small_order_points:
        order = point.order()
        
        # Send point as "public key" in key exchange
        shared_secret = perform_ecdh(point, victim_private_key)
        
        # shared_secret = private_key * point
        # Since point has small order, only limited values possible
        for candidate in range(order):
            if candidate * point == shared_secret:
                partial_key_info[order] = candidate % order
                break
    
    # Use Chinese Remainder Theorem to recover full key
    private_key = chinese_remainder_theorem(partial_key_info)
    return private_key
```

### 3. Quantum Computing Threats

**Shor's Algorithm Impact**:
```
Classical Security vs Quantum Attacks:

Algorithm          Classical Time    Quantum Time (Shor)
RSA-1024          2^80 operations   ~10^6 operations
RSA-2048          2^112 operations  ~10^7 operations  
RSA-3072          2^128 operations  ~10^8 operations
ECC P-256         2^128 operations  ~10^6 operations
ECC P-384         2^192 operations  ~10^7 operations

Post-Quantum Candidates:
- Kyber (Lattice-based): Secure against quantum attacks
- Dilithium (Lattice-based): Quantum-resistant signatures
- SPHINCS+ (Hash-based): Conservative quantum security
```

**Grover's Algorithm Impact on Symmetric Cryptography**:
```
Hash Function      Classical Security    Quantum Security (Grover)
SHA-256           2^256 preimage        2^128 preimage
SHA-256           2^128 collision       2^85 collision  
SHA-384           2^384 preimage        2^192 preimage
SHA-512           2^512 preimage        2^256 preimage

Mitigation: Double hash output sizes for equivalent security
```

## Implementation Vulnerability Models

### 1. Side-Channel Attacks

**Timing Attack Analysis**:
```python
def timing_attack_simulation(implementation, key_size_bits):
    """
    Simulate timing attack against naive RSA implementation
    """
    timings = []
    
    for bit_position in range(key_size_bits):
        # Measure time for modular exponentiation
        # with different bit patterns
        test_exponent = 2 ** bit_position
        
        start_time = time.time()
        result = naive_modexp(base, test_exponent, modulus)
        end_time = time.time()
        
        timing = end_time - start_time
        timings.append((bit_position, timing))
    
    # Analyze timing patterns to deduce key bits
    recovered_key_bits = analyze_timing_patterns(timings)
    return recovered_key_bits

def naive_modexp(base, exponent, modulus):
    """
    Vulnerable modular exponentiation (for demonstration)
    """
    result = 1
    base = base % modulus
    
    while exponent > 0:
        if exponent % 2 == 1:
            result = (result * base) % modulus  # Timing leak here!
        exponent = exponent >> 1
        base = (base * base) % modulus
    
    return result
```

**Power Analysis Countermeasures**:
```python
def constant_time_modexp(base, exponent, modulus):
    """
    Constant-time modular exponentiation resistant to power analysis
    """
    result = 1
    base = base % modulus
    
    # Process all bits, regardless of their value
    for bit_pos in range(exponent.bit_length()):
        bit = (exponent >> bit_pos) & 1
        
        # Always perform both operations
        temp1 = (result * result) % modulus      # Square
        temp2 = (temp1 * base) % modulus         # Multiply
        
        # Select result in constant time
        result = constant_time_select(bit, temp2, temp1)
    
    return result

def constant_time_select(condition, true_value, false_value):
    """
    Select value based on condition without timing leaks
    """
    mask = -(condition & 1)  # 0 or -1 (all bits set)
    return (mask & true_value) | (~mask & false_value)
```

### 2. Fault Injection Attacks

**RSA Fault Attack (Bellcore Attack)**:
```python
def bellcore_attack_simulation(rsa_signature_with_fault):
    """
    Simulate RSA private key recovery using fault injection
    """
    # Attacker induces fault during signature computation
    # causing signature to be computed with wrong prime (p or q)
    
    normal_signature = rsa_sign(message, private_key)
    faulty_signature = rsa_signature_with_fault(message, private_key)  # Fault injected
    
    # Verify both signatures
    normal_verify = pow(normal_signature, public_exponent, n)
    faulty_verify = pow(faulty_signature, public_exponent, n)
    
    # If fault affected only one prime, we can recover it
    if normal_verify != faulty_verify:
        # Compute difference
        diff = normal_signature - faulty_signature
        
        # GCD with modulus reveals one of the prime factors
        gcd_result = gcd(diff, n)
        
        if gcd_result > 1 and gcd_result < n:
            # We've recovered one prime factor!
            p = gcd_result
            q = n // p
            return p, q
    
    return None, None
```

### 3. Implementation Bugs

**Certificate Validation Bypass**:
```python
def vulnerable_certificate_validation(cert_chain):
    """
    Example of vulnerable certificate validation logic
    """
    # BUG 1: Not checking certificate chain completeness
    if len(cert_chain) == 0:
        return False
    
    # BUG 2: Only validating the first certificate
    leaf_cert = cert_chain[0]
    if not is_certificate_valid(leaf_cert):
        return False
    
    # BUG 3: Not verifying signature chain
    # Should verify each cert is signed by the next one
    
    # BUG 4: Not checking revocation status
    
    # BUG 5: Accepting self-signed certificates
    if cert_chain[-1].issuer == cert_chain[-1].subject:
        return True  # This is wrong!
    
    return True

def secure_certificate_validation(cert_chain, trust_anchors):
    """
    Proper certificate validation implementation
    """
    if not cert_chain:
        return False, "Empty certificate chain"
    
    # 1. Verify chain completeness to trust anchor
    if not ends_with_trust_anchor(cert_chain, trust_anchors):
        return False, "Chain does not end with trusted anchor"
    
    # 2. Verify signature chain
    for i in range(len(cert_chain) - 1):
        subject_cert = cert_chain[i]
        issuer_cert = cert_chain[i + 1]
        
        if not verify_signature(subject_cert, issuer_cert.public_key):
            return False, f"Invalid signature on certificate {i}"
    
    # 3. Check all certificates are currently valid
    current_time = datetime.utcnow()
    for i, cert in enumerate(cert_chain):
        if not (cert.not_before <= current_time <= cert.not_after):
            return False, f"Certificate {i} is not currently valid"
    
    # 4. Check revocation status
    for cert in cert_chain[:-1]:  # Skip root
        if is_certificate_revoked(cert):
            return False, f"Certificate {cert.subject} is revoked"
    
    return True, "Certificate chain valid"
```

## Protocol-Level Attacks

### 1. Man-in-the-Middle Attacks

**SSL/TLS Certificate Validation Bypass**:
```python
def mitm_attack_scenario():
    """
    Demonstrate how weak certificate validation enables MITM
    """
    # Attacker scenario:
    # 1. Client connects to attacker's server
    # 2. Attacker presents fake certificate for target domain
    # 3. Weak validation accepts certificate
    # 4. Attacker proxies connection to real server
    
    fake_certificate = create_self_signed_certificate(
        subject="CN=bank.example.com",  # Target domain
        issuer="CN=Fake CA",
        validity_period=365
    )
    
    # Vulnerable client accepts without proper validation
    if weak_certificate_validation(fake_certificate):
        print("Client accepted fake certificate - MITM successful!")
        # Attacker can now intercept/modify all traffic
        return True
    
    return False

def proper_certificate_validation(certificate, hostname):
    """
    Proper certificate validation to prevent MITM
    """
    # 1. Verify certificate chain to trusted root
    if not validate_certificate_chain(certificate):
        return False
    
    # 2. Check certificate is not revoked
    if is_certificate_revoked(certificate):
        return False
    
    # 3. Verify hostname matches certificate
    if not verify_hostname_match(certificate, hostname):
        return False
    
    # 4. Check certificate is currently valid
    if not is_certificate_currently_valid(certificate):
        return False
    
    return True
```

### 2. CA Compromise Attacks

**Rogue Certificate Issuance**:
```python
def ca_compromise_impact_analysis():
    """
    Analyze impact of Certificate Authority compromise
    """
    compromise_scenarios = {
        "root_ca_compromise": {
            "impact": "Complete PKI compromise",
            "affected_certificates": "All certificates in hierarchy",
            "recovery_time": "Months to years",
            "cost": "Millions of dollars",
            "mitigation": "Certificate Transparency, Key Pinning"
        },
        "intermediate_ca_compromise": {
            "impact": "Partial PKI compromise", 
            "affected_certificates": "Certificates signed by intermediate",
            "recovery_time": "Days to weeks",
            "cost": "Hundreds of thousands",
            "mitigation": "Certificate revocation, path length constraints"
        },
        "registration_authority_compromise": {
            "impact": "Domain validation bypass",
            "affected_certificates": "Newly issued certificates",
            "recovery_time": "Hours to days", 
            "cost": "Thousands to tens of thousands",
            "mitigation": "Multi-perspective validation, CAA records"
        }
    }
    
    return compromise_scenarios

def certificate_transparency_monitoring():
    """
    Monitor Certificate Transparency logs for unauthorized certificates
    """
    # Monitor CT logs for certificates issued for your domains
    monitored_domains = ["example.com", "*.example.com"]
    
    new_certificates = query_ct_logs_since(last_check_time)
    
    suspicious_certificates = []
    for cert in new_certificates:
        cert_domains = extract_domains_from_certificate(cert)
        
        for domain in cert_domains:
            if matches_monitored_domain(domain, monitored_domains):
                if not is_authorized_certificate(cert):
                    suspicious_certificates.append(cert)
    
    if suspicious_certificates:
        alert_security_team(suspicious_certificates)
        initiate_incident_response()
```

### 3. Revocation System Attacks

**OCSP Replay Attacks**:
```python
def ocsp_replay_attack():
    """
    Demonstrate OCSP replay attack using old valid responses
    """
    # Attacker intercepts valid OCSP response for certificate
    valid_ocsp_response = capture_ocsp_response()
    
    # Later, after certificate is revoked, replay old response
    # to make revoked certificate appear valid
    
    def replay_old_response(ocsp_request):
        # Return old "good" response instead of current "revoked" status
        return valid_ocsp_response
    
    # Mitigation: Check response freshness and nonce
    def secure_ocsp_validation(ocsp_response):
        # 1. Verify response signature
        if not verify_ocsp_signature(ocsp_response):
            return False
        
        # 2. Check response is fresh (thisUpdate recent)
        max_age = timedelta(hours=24)
        if datetime.utcnow() - ocsp_response.this_update > max_age:
            return False
        
        # 3. Verify nonce matches request (prevent replay)
        if ocsp_response.nonce != original_request.nonce:
            return False
        
        return True
```

## Operational Failure Models

### 1. Key Management Failures

**Private Key Exposure Scenarios**:
```python
def key_exposure_risk_analysis():
    """
    Analyze common private key exposure scenarios
    """
    exposure_vectors = {
        "memory_dumps": {
            "description": "Private keys extracted from memory dumps",
            "probability": 0.15,
            "impact": "High",
            "mitigation": "Memory encryption, secure deletion"
        },
        "backup_compromise": {
            "description": "Unencrypted key backups accessed",
            "probability": 0.25,
            "impact": "High", 
            "mitigation": "Encrypted backups, access controls"
        },
        "insider_threat": {
            "description": "Malicious insider copies keys",
            "probability": 0.05,
            "impact": "High",
            "mitigation": "Role separation, audit logging"
        },
        "software_vulnerabilities": {
            "description": "Bugs allow key extraction",
            "probability": 0.30,
            "impact": "High",
            "mitigation": "Regular updates, code audits"
        },
        "physical_access": {
            "description": "Physical access to key storage",
            "probability": 0.10,
            "impact": "High",
            "mitigation": "Hardware security modules, physical security"
        }
    }
    
    total_risk = sum(v["probability"] for v in exposure_vectors.values())
    return exposure_vectors, total_risk
```

### 2. Configuration Errors

**Common PKI Misconfigurations**:
```python
def pki_misconfiguration_analysis():
    """
    Analyze common PKI configuration errors and their impacts
    """
    misconfigurations = {
        "weak_key_sizes": {
            "description": "Using RSA-1024 or weak ECC curves",
            "prevalence": "15% of deployments",
            "impact": "Cryptographic compromise possible",
            "detection": "Certificate transparency monitoring"
        },
        "missing_revocation_checking": {
            "description": "Not validating certificate revocation",
            "prevalence": "40% of implementations",
            "impact": "Revoked certificates accepted",
            "detection": "Penetration testing"
        },
        "improper_hostname_validation": {
            "description": "Not matching certificate CN/SAN to hostname",
            "prevalence": "25% of implementations", 
            "impact": "Man-in-the-middle attacks possible",
            "detection": "Automated scanning tools"
        },
        "accepting_self_signed_certificates": {
            "description": "Bypassing certificate chain validation",
            "prevalence": "20% of implementations",
            "impact": "Complete bypass of PKI security",
            "detection": "Security code review"
        },
        "weak_certificate_validation": {
            "description": "Incomplete validation of certificate chains",
            "prevalence": "60% of implementations",
            "impact": "Various attacks possible",
            "detection": "Security testing frameworks"
        }
    }
    
    return misconfigurations
```

## Attack Complexity Analysis

### Computational Complexity of Attacks

```python
def attack_complexity_comparison():
    """
    Compare computational complexity of various PKI attacks
    """
    attack_complexities = {
        "RSA_factorization": {
            "1024_bit": 2**80,
            "2048_bit": 2**112, 
            "3072_bit": 2**128,
            "4096_bit": 2**140
        },
        "ECC_discrete_log": {
            "224_bit": 2**112,
            "256_bit": 2**128,
            "384_bit": 2**192,
            "521_bit": 2**260
        },
        "hash_collisions": {
            "SHA1": 2**63,      # Practical attacks exist
            "SHA256": 2**128,
            "SHA384": 2**192,
            "SHA512": 2**256
        },
        "brute_force_symmetric": {
            "AES128": 2**128,
            "AES192": 2**192,
            "AES256": 2**256
        }
    }
    
    return attack_complexities

def economic_attack_analysis(attack_cost_per_operation=1e-15):
    """
    Economic analysis of cryptographic attacks
    """
    complexities = attack_complexity_comparison()
    
    for algorithm, variants in complexities.items():
        print(f"\n{algorithm} Attack Costs:")
        for variant, complexity in variants.items():
            cost = complexity * attack_cost_per_operation
            print(f"  {variant}: ${cost:.2e}")
            
            if cost > 1e12:
                print(f"    Status: Economically infeasible")
            elif cost > 1e9:
                print(f"    Status: Only feasible for nation-states")
            else:
                print(f"    Status: Potentially feasible")
```

## Mitigation Strategies

### Defense in Depth Approach

```python
def implement_pki_defense_layers():
    """
    Implement multiple security layers for PKI protection
    """
    defense_layers = {
        "cryptographic_layer": [
            "Use sufficient key sizes (RSA ≥ 2048, ECC ≥ 256)",
            "Implement proper padding schemes (OAEP, PSS)",
            "Use secure hash functions (SHA-256 or better)",
            "Employ constant-time implementations"
        ],
        "protocol_layer": [
            "Enforce strict certificate validation",
            "Implement certificate pinning",
            "Use Certificate Transparency monitoring",
            "Deploy HSTS and HPKP headers"
        ],
        "implementation_layer": [
            "Regular security code reviews",
            "Fuzzing and penetration testing",
            "Static and dynamic analysis",
            "Secure coding practices"
        ],
        "operational_layer": [
            "Hardware security modules for key storage",
            "Role-based access controls",
            "Comprehensive audit logging",
            "Incident response procedures"
        ],
        "monitoring_layer": [
            "Certificate transparency log monitoring",
            "Real-time threat detection",
            "Anomaly detection systems",
            "Security information and event management"
        ]
    }
    
    return defense_layers
```

## Files in This Section

- `cryptographic-attacks.md` - Mathematical attacks on PKI algorithms
- `implementation-vulnerabilities.md` - Common implementation bugs and fixes
- `protocol-attacks.md` - Network and protocol-level attack vectors
- `operational-failures.md` - Key management and configuration errors
- `side-channel-attacks.md` - Timing, power, and fault injection attacks
- `quantum-threats.md` - Impact of quantum computing on PKI security
- `mitigation-strategies.md` - Defense mechanisms and countermeasures
- `attack-complexity-analysis.md` - Mathematical analysis of attack feasibility

## Key Takeaways

### Critical Vulnerability Classes

1. **Weak Random Number Generation** - Leads to predictable keys and signatures
2. **Implementation Bugs** - Certificate validation bypasses are common
3. **Side-Channel Leakage** - Timing and power analysis can reveal keys
4. **Configuration Errors** - Improper deployment negates cryptographic security
5. **CA Compromise** - Single point of failure for entire trust hierarchies

### Risk Mitigation Priorities

```
Priority 1: Proper certificate validation (prevents most attacks)
Priority 2: Strong key generation and storage (protects core assets)
Priority 3: Comprehensive monitoring (detects ongoing attacks)
Priority 4: Regular security updates (patches known vulnerabilities)
Priority 5: Incident response planning (minimizes damage when breaches occur)
```

---

**Next**: [Experiments - Hands-on PKI Security Demonstrations](../05-experiments/README.md) 🧪  
**Previous**: [Algorithms](../03-algorithms/README.md) 🔧  
**See Also**: [Use Cases](../07-use-cases/README.md) for real-world attack scenarios ⚠️