# Web Authentication Troubleshooting Guide

## Overview

Comprehensive troubleshooting guide for SSL/TLS certificate-based web authentication issues, covering common problems, diagnostic techniques, and resolution strategies with mathematical analysis of failure modes.

## Mathematical Foundation for Diagnostics

### Certificate Validation State Machine

```
Certificate Validation States:
S₀ = Initial State (Certificate Received)
S₁ = Chain Construction (Path Building)
S₂ = Signature Verification 
S₃ = Revocation Checking
S₄ = Policy Validation
S₅ = Success State
Sₑ = Error States (Various Failure Modes)

Transition Probabilities:
P(S₀ → S₁) = trust_store_coverage_rate
P(S₁ → S₂) = chain_construction_success_rate  
P(S₂ → S₃) = signature_verification_success_rate
P(S₃ → S₄) = revocation_check_success_rate
P(S₄ → S₅) = policy_compliance_rate

Overall Success Rate = ∏P(Sᵢ → Sᵢ₊₁)
```

### Error Classification Framework

```python
def classify_ssl_error(error_type, error_subtype):
    """
    Mathematical classification of SSL/TLS errors
    """
    error_taxonomy = {
        "certificate_errors": {
            "expired": {"severity": 0.9, "frequency": 0.15},
            "self_signed": {"severity": 0.8, "frequency": 0.25},
            "untrusted_issuer": {"severity": 0.7, "frequency": 0.20},
            "hostname_mismatch": {"severity": 0.6, "frequency": 0.18},
            "revoked": {"severity": 0.95, "frequency": 0.02}
        },
        "protocol_errors": {
            "version_mismatch": {"severity": 0.5, "frequency": 0.08},
            "cipher_mismatch": {"severity": 0.4, "frequency": 0.05},
            "handshake_failure": {"severity": 0.7, "frequency": 0.07}
        }
    }
    
    # Risk score calculation
    if error_type in error_taxonomy and error_subtype in error_taxonomy[error_type]:
        risk_score = error_taxonomy[error_type][error_subtype]["severity"] * \
                     error_taxonomy[error_type][error_subtype]["frequency"]
    else:
        risk_score = 0.5  # Default risk for unknown errors
    
    return risk_score
```

## Common Certificate Issues

### 1. Certificate Expiration

**Symptoms**:
- Browser warnings: "Your connection is not secure"
- SSL error codes: SSL_ERROR_EXPIRED_CERT_ALERT
- Failed HTTPS connections

**Diagnostic Commands**:
```bash
# Check certificate expiration
openssl x509 -in certificate.pem -text -noout | grep "Not After"

# Check remote certificate expiration
echo | openssl s_client -servername example.com -connect example.com:443 2>/dev/null | openssl x509 -noout -dates

# Automated expiration checking
openssl x509 -in certificate.pem -checkend 86400 && echo "Certificate valid for 24 hours" || echo "Certificate expires within 24 hours"
```

**Mathematical Analysis**:
```python
def certificate_expiration_analysis(cert_not_before, cert_not_after, current_time):
    """
    Analyze certificate expiration timeline
    """
    import datetime
    
    time_remaining = cert_not_after - current_time
    total_validity = cert_not_after - cert_not_before
    
    metrics = {
        "days_remaining": time_remaining.days,
        "validity_percentage_used": 1 - (time_remaining / total_validity),
        "renewal_urgency": max(0, 1 - time_remaining.days / 30),  # 30-day renewal window
        "risk_level": "HIGH" if time_remaining.days < 7 else "MEDIUM" if time_remaining.days < 30 else "LOW"
    }
    
    return metrics
```

**Resolution Steps**:
1. Generate new CSR with updated validity period
2. Submit to CA for renewed certificate
3. Install new certificate with overlapping validity
4. Update monitoring to prevent future expirations

### 2. Hostname Verification Failures

**Symptoms**:
- SSL error: SSL_ERROR_BAD_CERT_DOMAIN
- Certificate hostname does not match server hostname
- Browser security warnings

**Diagnostic Process**:
```bash
# Extract Subject Alternative Names (SAN)
openssl x509 -in certificate.pem -text -noout | grep -A 1 "Subject Alternative Name"

# Check certificate subject
openssl x509 -in certificate.pem -subject -noout

# Test hostname verification
openssl s_client -servername actual-hostname.com -connect actual-hostname.com:443 -verify_hostname actual-hostname.com
```

**Mathematical Hostname Matching Algorithm**:
```python
import re

def hostname_verification(cert_names, requested_hostname):
    """
    RFC 6125 compliant hostname verification
    """
    def wildcard_match(pattern, hostname):
        # Convert wildcard pattern to regex
        # *.example.com matches foo.example.com but not foo.bar.example.com
        regex_pattern = pattern.replace('.', r'\.').replace('*', r'[^.]+')
        regex_pattern = f'^{regex_pattern}$'
        return bool(re.match(regex_pattern, hostname, re.IGNORECASE))
    
    # Check exact matches first
    for name in cert_names:
        if name.lower() == requested_hostname.lower():
            return {"match": True, "type": "exact", "matched_name": name}
    
    # Check wildcard matches
    for name in cert_names:
        if '*' in name and wildcard_match(name, requested_hostname):
            return {"match": True, "type": "wildcard", "matched_name": name}
    
    return {"match": False, "type": None, "matched_name": None}
```

**Resolution Strategies**:
1. **Certificate Reissuance**: Include all required hostnames in SAN
2. **Wildcard Certificates**: Use `*.domain.com` for multiple subdomains
3. **Multi-Domain Certificates**: Include all domains in single certificate
4. **Load Balancer Configuration**: SNI (Server Name Indication) setup

### 3. Certificate Chain Issues

**Symptoms**:
- SSL error: SSL_ERROR_UNKNOWN_CA_ALERT
- Incomplete certificate chain
- Intermediate certificate missing

**Chain Validation Diagnostics**:
```bash
# Verify complete certificate chain
openssl verify -CApath /etc/ssl/certs/ -untrusted intermediate.pem certificate.pem

# Check chain completeness
openssl s_client -showcerts -servername example.com -connect example.com:443 </dev/null

# Analyze chain structure
openssl crl2pkcs7 -nocrl -certfile fullchain.pem | openssl pkcs7 -print_certs -text -noout
```

**Chain Construction Algorithm**:
```python
def build_certificate_chain(end_entity_cert, intermediate_certs, trust_anchors):
    """
    Build and validate certificate chain using graph traversal
    """
    from collections import defaultdict, deque
    
    # Build issuer-subject graph
    cert_graph = defaultdict(list)
    all_certs = [end_entity_cert] + intermediate_certs + trust_anchors
    
    for cert in all_certs:
        issuer = cert.issuer
        for potential_child in all_certs:
            if potential_child.subject == issuer:
                cert_graph[cert].append(potential_child)
    
    # BFS to find valid path to trust anchor
    queue = deque([(end_entity_cert, [end_entity_cert])])
    visited = set()
    
    while queue:
        current_cert, path = queue.popleft()
        
        if current_cert in trust_anchors:
            return {"valid": True, "path": path, "length": len(path)}
        
        if current_cert in visited:
            continue
        visited.add(current_cert)
        
        for next_cert in cert_graph[current_cert]:
            if next_cert not in visited:
                queue.append((next_cert, path + [next_cert]))
    
    return {"valid": False, "path": None, "length": 0}
```

### 4. Revocation Check Failures

**Symptoms**:
- OCSP responder timeouts
- CRL download failures
- Revocation unknown status

**OCSP Diagnostics**:
```bash
# Check OCSP responder
openssl ocsp -issuer intermediate.pem -cert certificate.pem -text -url http://ocsp.ca.example.com

# Test OCSP stapling
echo | openssl s_client -servername example.com -connect example.com:443 -status

# Verify CRL accessibility
wget -O- http://crl.ca.example.com/ca.crl | openssl crl -inform DER -text -noout
```

**Revocation Check Performance Model**:
```python
def revocation_performance_analysis():
    """
    Analyze revocation checking performance and reliability
    """
    methods = {
        "OCSP": {
            "average_response_time": 150,  # milliseconds
            "cache_hit_rate": 0.85,
            "availability": 0.999,
            "bandwidth_per_check": 1024   # bytes
        },
        "CRL": {
            "average_response_time": 500,  # milliseconds  
            "cache_hit_rate": 0.95,
            "availability": 0.995,
            "bandwidth_per_check": 102400  # bytes (full CRL)
        },
        "OCSP_Stapling": {
            "average_response_time": 0,    # included in handshake
            "cache_hit_rate": 1.0,
            "availability": 0.999,
            "bandwidth_per_check": 0       # no additional bandwidth
        }
    }
    
    def calculate_effective_performance(method):
        base_time = methods[method]["average_response_time"]
        hit_rate = methods[method]["cache_hit_rate"]
        availability = methods[method]["availability"]
        
        # Weighted average considering cache hits and failures
        effective_time = (base_time * (1 - hit_rate)) + \
                        (base_time * 0.1 * hit_rate) + \
                        (30000 * (1 - availability))  # 30s timeout penalty
        
        return {
            "method": method,
            "effective_response_time": effective_time,
            "reliability_score": hit_rate * availability,
            "recommended": effective_time < 1000 and availability > 0.99
        }
    
    return {method: calculate_effective_performance(method) for method in methods}
```

## Protocol-Level Issues

### 5. TLS Version Incompatibility

**Symptoms**:
- Handshake failures
- Protocol version errors
- Legacy client connectivity issues

**Version Compatibility Matrix**:
```
Client/Server    TLS 1.0    TLS 1.1    TLS 1.2    TLS 1.3
TLS 1.0            ✓          ✗          ✗          ✗
TLS 1.1            ✗          ✓          ✗          ✗  
TLS 1.2            ✗          ✗          ✓          ✗
TLS 1.3            ✗          ✗          ✗          ✓
Mixed Support      ✓          ✓          ✓          ✗
```

**Diagnostic Commands**:
```bash
# Test specific TLS versions
openssl s_client -tls1_2 -connect example.com:443
openssl s_client -tls1_3 -connect example.com:443

# Check supported protocols
nmap --script ssl-enum-ciphers -p 443 example.com
```

### 6. Cipher Suite Mismatches

**Performance vs Security Trade-offs**:
```python
def cipher_suite_analysis():
    """
    Analyze cipher suite security and performance characteristics
    """
    cipher_suites = {
        "ECDHE-ECDSA-AES256-GCM-SHA384": {
            "security_level": 0.95,
            "performance_score": 0.85,
            "forward_secrecy": True,
            "quantum_resistant": False
        },
        "ECDHE-RSA-AES256-GCM-SHA384": {
            "security_level": 0.90,
            "performance_score": 0.80,
            "forward_secrecy": True,
            "quantum_resistant": False
        },
        "AES256-GCM-SHA384": {
            "security_level": 0.75,
            "performance_score": 0.95,
            "forward_secrecy": False,
            "quantum_resistant": False
        }
    }
    
    def calculate_suitability(cipher_suite, security_weight=0.7):
        suite = cipher_suites[cipher_suite]
        
        suitability_score = (
            suite["security_level"] * security_weight +
            suite["performance_score"] * (1 - security_weight)
        )
        
        # Penalty for lack of forward secrecy
        if not suite["forward_secrecy"]:
            suitability_score *= 0.8
            
        return suitability_score
    
    return {
        suite: calculate_suitability(suite) 
        for suite in cipher_suites
    }
```

## Systematic Troubleshooting Methodology

### Phase 1: Initial Assessment

```bash
#!/bin/bash
# SSL/TLS Health Check Script

HOSTNAME="$1"
PORT="${2:-443}"

echo "=== SSL/TLS Health Check for $HOSTNAME:$PORT ==="

# 1. Basic connectivity
echo "1. Testing basic connectivity..."
timeout 10 nc -z "$HOSTNAME" "$PORT" && echo "✓ Port reachable" || echo "✗ Connection failed"

# 2. Certificate chain analysis
echo "2. Analyzing certificate chain..."
CERT_INFO=$(echo | timeout 10 openssl s_client -servername "$HOSTNAME" -connect "$HOSTNAME:$PORT" -verify_return_error 2>/dev/null)

if echo "$CERT_INFO" | grep -q "Verify return code: 0"; then
    echo "✓ Certificate chain valid"
else
    echo "✗ Certificate chain issues detected"
    echo "$CERT_INFO" | grep "verify error\|Verify return code"
fi

# 3. Certificate expiration
echo "3. Checking certificate expiration..."
EXPIRY=$(echo "$CERT_INFO" | openssl x509 -noout -dates 2>/dev/null | grep "notAfter" | cut -d= -f2)
if [ -n "$EXPIRY" ]; then
    EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null)
    CURRENT_EPOCH=$(date +%s)
    DAYS_LEFT=$(( (EXPIRY_EPOCH - CURRENT_EPOCH) / 86400 ))
    
    if [ "$DAYS_LEFT" -gt 30 ]; then
        echo "✓ Certificate expires in $DAYS_LEFT days"
    elif [ "$DAYS_LEFT" -gt 7 ]; then
        echo "⚠ Certificate expires in $DAYS_LEFT days - renewal recommended"
    else
        echo "✗ Certificate expires in $DAYS_LEFT days - urgent renewal required"
    fi
fi

# 4. Hostname verification
echo "4. Verifying hostname..."
if echo "$CERT_INFO" | grep -q "verify error:num=62"; then
    echo "✗ Hostname verification failed"
else
    echo "✓ Hostname verification passed"
fi

# 5. Protocol and cipher analysis
echo "5. Testing protocol support..."
for version in tls1_2 tls1_3; do
    if timeout 5 openssl s_client -"$version" -connect "$HOSTNAME:$PORT" </dev/null 2>/dev/null | grep -q "Protocol.*TLS"; then
        echo "✓ $version supported"
    else
        echo "✗ $version not supported"
    fi
done
```

### Phase 2: Deep Diagnostics

**Error Pattern Analysis**:
```python
def analyze_ssl_logs(log_entries):
    """
    Analyze SSL error patterns for systematic troubleshooting
    """
    import re
    from collections import Counter
    
    error_patterns = {
        r'certificate verify failed': 'certificate_validation',
        r'hostname.*doesn.*match': 'hostname_mismatch',
        r'certificate.*expired': 'certificate_expired',
        r'self.signed certificate': 'self_signed',
        r'unable to get local issuer certificate': 'missing_intermediate',
        r'certificate revoked': 'certificate_revoked',
        r'handshake failure': 'handshake_failure',
        r'protocol version': 'protocol_mismatch',
        r'no shared cipher': 'cipher_mismatch'
    }
    
    error_counts = Counter()
    error_details = []
    
    for entry in log_entries:
        timestamp = entry.get('timestamp')
        message = entry.get('message', '')
        
        for pattern, error_type in error_patterns.items():
            if re.search(pattern, message, re.IGNORECASE):
                error_counts[error_type] += 1
                error_details.append({
                    'timestamp': timestamp,
                    'error_type': error_type,
                    'message': message
                })
                break
    
    # Calculate error rate trends
    total_errors = sum(error_counts.values())
    error_distribution = {
        error_type: count / total_errors 
        for error_type, count in error_counts.items()
    }
    
    return {
        'error_counts': dict(error_counts),
        'error_distribution': error_distribution,
        'error_details': error_details,
        'primary_issues': error_counts.most_common(3)
    }
```

## Resolution Playbooks

### Certificate Issues Resolution Matrix

```
Issue Type              Immediate Action           Long-term Solution           Prevention
Certificate Expired     Deploy emergency cert      Implement renewal automation Monitoring alerts (30d)
Hostname Mismatch      Update certificate SAN     Wildcard or multi-domain     DNS change procedures  
Missing Intermediate   Install intermediate       Automated chain building     Chain validation tests
Untrusted Issuer       Update trust store        Use trusted CA               CA evaluation process
Certificate Revoked    Revoke and reissue        Certificate lifecycle mgmt   Regular security audits
```

### Performance Optimization for Common Issues

**Certificate Validation Caching**:
```python
def implement_cert_cache():
    """
    Implement certificate validation result caching
    """
    cache_strategy = {
        "validation_results": {
            "ttl": 300,  # 5 minutes for positive results
            "negative_ttl": 60,  # 1 minute for failures
            "max_size": 10000  # Maximum cached entries
        },
        "certificate_chains": {
            "ttl": 3600,  # 1 hour for chain construction
            "max_size": 5000
        },
        "revocation_status": {
            "ttl": 1800,  # 30 minutes for OCSP responses
            "max_size": 50000
        }
    }
    
    # Cache hit rate optimization
    expected_hit_rates = {
        "validation_results": 0.85,
        "certificate_chains": 0.92,
        "revocation_status": 0.78
    }
    
    performance_improvement = sum(expected_hit_rates.values()) / len(expected_hit_rates)
    
    return {
        "cache_strategy": cache_strategy,
        "expected_performance_gain": f"{performance_improvement:.1%}",
        "memory_requirement": "~50MB for typical load"
    }
```

## Monitoring and Alerting for Prevention

### Key Metrics to Monitor

1. **Certificate Health Metrics**:
   - Days until expiration
   - Validation success rate
   - Chain construction time
   - Revocation check latency

2. **Protocol Performance Metrics**:
   - Handshake completion time
   - Cipher negotiation failures
   - Protocol version distribution
   - Session resumption rate

3. **Error Rate Monitoring**:
   ```sql
   -- Certificate validation error rate
   SELECT 
       date_trunc('hour', timestamp) as hour,
       count(case when error_type = 'certificate_validation' then 1 end) as cert_errors,
       count(*) as total_attempts,
       (count(case when error_type = 'certificate_validation' then 1 end) * 100.0 / count(*)) as error_rate
   FROM ssl_handshake_logs 
   WHERE timestamp > NOW() - INTERVAL '24 hours'
   GROUP BY hour
   ORDER BY hour DESC;
   ```

### Automated Remediation Scripts

```bash
#!/bin/bash
# Automated SSL issue detection and remediation

DOMAIN="$1"
ALERT_THRESHOLD_DAYS=30

# Function to check certificate expiration
check_expiration() {
    local domain="$1"
    local expiry_date=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
    
    if [ -n "$expiry_date" ]; then
        local expiry_epoch=$(date -d "$expiry_date" +%s)
        local current_epoch=$(date +%s)
        local days_left=$(( (expiry_epoch - current_epoch) / 86400 ))
        
        if [ "$days_left" -le "$ALERT_THRESHOLD_DAYS" ]; then
            echo "ALERT: Certificate for $domain expires in $days_left days"
            # Trigger certificate renewal process
            trigger_renewal "$domain"
        fi
    fi
}

# Function to trigger certificate renewal
trigger_renewal() {
    local domain="$1"
    echo "Initiating automated certificate renewal for $domain"
    
    # Integration with ACME client (certbot, acme.sh, etc.)
    # This would trigger your automated renewal process
    /usr/bin/certbot renew --cert-name "$domain" --quiet --no-self-upgrade
    
    # Verify renewal success
    if [ $? -eq 0 ]; then
        echo "Certificate renewal successful for $domain"
        # Restart web services if needed
        systemctl reload nginx
    else
        echo "Certificate renewal failed for $domain - manual intervention required"
        # Send alert to operations team
        send_alert "Certificate renewal failed for $domain"
    fi
}

check_expiration "$DOMAIN"
```

This comprehensive troubleshooting guide provides mathematical analysis of SSL/TLS issues, systematic diagnostic approaches, and automated remediation strategies for maintaining robust PKI-based web authentication systems.