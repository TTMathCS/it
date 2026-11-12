# Certificate Authority Troubleshooting Guide

## Overview

This troubleshooting guide addresses common issues encountered in Certificate Authority operations, providing systematic diagnostic procedures and proven resolution strategies for CA infrastructure, certificate issuance, and operational challenges.

## Common CA Issues

### 1. Certificate Issuance Failures

#### Symptoms
- CSR processing fails with validation errors
- Certificate generation hangs or times out
- Database errors during certificate storage

#### Diagnostic Steps
```bash
#!/bin/bash
# diagnose_issuance_failure.sh

CSR_FILE="$1"
echo "=== Certificate Issuance Diagnostics ==="

# Validate CSR format and content
validate_csr() {
    echo "Validating CSR format..."
    if ! openssl req -text -noout -verify -in "$CSR_FILE"; then
        echo "ERROR: Invalid CSR format or signature"
        return 1
    fi
    
    # Check key size
    KEY_SIZE=$(openssl req -text -noout -in "$CSR_FILE" | grep "Public-Key" | grep -o '[0-9]\+')
    if [ "$KEY_SIZE" -lt 2048 ]; then
        echo "WARNING: Key size $KEY_SIZE bits is below recommended 2048 bits"
    fi
    
    echo "CSR validation passed"
    return 0
}

# Check CA database connectivity
check_database() {
    echo "Checking CA database..."
    if sqlite3 /secure/ca_database.db "SELECT COUNT(*) FROM certificates;" > /dev/null 2>&1; then
        echo "Database connectivity: OK"
    else
        echo "ERROR: Cannot connect to CA database"
        return 1
    fi
}

# Verify HSM connectivity
check_hsm() {
    echo "Checking HSM connectivity..."
    if pkcs11-tool --module /usr/lib/pkcs11/libCryptoki2_64.so --login --pin "$HSM_PIN" --test; then
        echo "HSM connectivity: OK"
    else
        echo "ERROR: HSM connection failed"
        return 1
    fi
}

validate_csr "$CSR_FILE"
check_database
check_hsm
```

#### Resolution Steps
1. **CSR Format Issues**:
```bash
# Convert CSR to correct format
openssl req -in malformed.csr -out corrected.csr -outform PEM

# Re-verify CSR after conversion
openssl req -text -noout -verify -in corrected.csr
```

2. **Database Connection Issues**:
```bash
# Check database locks
lsof /secure/ca_database.db

# Repair database if corrupted
sqlite3 /secure/ca_database.db "PRAGMA integrity_check;"
sqlite3 /secure/ca_database.db "VACUUM;"
```

### 2. OCSP Responder Problems

#### Symptoms
- OCSP queries timing out
- "Response verify failed" errors
- OCSP service not responding

#### Diagnostic Procedure
```bash
#!/bin/bash
# diagnose_ocsp_issues.sh

OCSP_URL="$1"
TEST_CERT="$2"
CA_CERT="$3"

echo "=== OCSP Responder Diagnostics ==="

# Test OCSP URL accessibility
test_ocsp_connectivity() {
    echo "Testing OCSP URL accessibility..."
    if curl -s --max-time 10 -I "$OCSP_URL" | grep -q "200 OK"; then
        echo "OCSP URL accessible"
        return 0
    else
        echo "ERROR: OCSP URL not accessible"
        return 1
    fi
}

# Test OCSP response
test_ocsp_response() {
    echo "Testing OCSP response..."
    response=$(openssl ocsp -issuer "$CA_CERT" -cert "$TEST_CERT" -url "$OCSP_URL" -text 2>&1)
    
    if echo "$response" | grep -q "Response verify OK"; then
        echo "OCSP response: Valid"
    elif echo "$response" | grep -q "Response Verify Failure"; then
        echo "ERROR: OCSP response verification failed"
        echo "Check OCSP signing certificate validity"
    else
        echo "ERROR: OCSP query failed"
        echo "$response"
    fi
}

test_ocsp_connectivity "$OCSP_URL"
test_ocsp_response
```

#### Resolution Steps
1. **OCSP Service Issues**:
```bash
# Restart OCSP responder service
systemctl restart ocsp-responder
systemctl status ocsp-responder

# Check OCSP responder logs
journalctl -u ocsp-responder -f
```

2. **OCSP Certificate Issues**:
```bash
# Renew OCSP signing certificate
cd /secure/ocsp
openssl req -new -keyout certs/ocsp_new.key -out certs/ocsp_new.csr
openssl ca -in certs/ocsp_new.csr -out certs/ocsp_new.crt -extensions ocsp_cert
```

### 3. HSM Connectivity Issues

#### Symptoms
- "HSM not found" errors
- Key generation/signing operations fail
- HSM authentication failures

#### Diagnostic Steps
```bash
#!/bin/bash
# diagnose_hsm_issues.sh

echo "=== HSM Diagnostics ==="

# Check HSM hardware connectivity
check_hsm_hardware() {
    echo "Checking HSM hardware connectivity..."
    if lsusb | grep -i "SafeNet\|Gemalto\|Utimaco"; then
        echo "HSM hardware detected"
    else
        echo "WARNING: No HSM hardware detected via USB"
    fi
    
    # Check PCIe HSM cards
    if lspci | grep -i "SafeNet\|Gemalto\|Utimaco"; then
        echo "HSM PCIe card detected"
    fi
}

# Test HSM software stack
check_hsm_software() {
    echo "Checking HSM software stack..."
    
    # Check PKCS#11 library
    if [ -f "/usr/lib/pkcs11/libCryptoki2_64.so" ]; then
        echo "PKCS#11 library found"
    else
        echo "ERROR: PKCS#11 library not found"
        return 1
    fi
    
    # Test basic HSM connectivity
    if pkcs11-tool --module /usr/lib/pkcs11/libCryptoki2_64.so --list-slots; then
        echo "HSM slots accessible"
    else
        echo "ERROR: Cannot access HSM slots"
        return 1
    fi
}

# Check HSM authentication
check_hsm_auth() {
    echo "Checking HSM authentication..."
    read -s -p "Enter HSM PIN: " HSM_PIN
    echo
    
    if pkcs11-tool --module /usr/lib/pkcs11/libCryptoki2_64.so --login --pin "$HSM_PIN" --test; then
        echo "HSM authentication successful"
    else
        echo "ERROR: HSM authentication failed"
        return 1
    fi
}

check_hsm_hardware
check_hsm_software
check_hsm_auth
```

#### Resolution Steps
1. **Hardware Issues**:
```bash
# Reset USB HSM connection
echo "Resetting USB HSM..."
echo "0" > /sys/bus/usb/devices/X-Y/authorized
sleep 2
echo "1" > /sys/bus/usb/devices/X-Y/authorized
```

2. **Software Issues**:
```bash
# Reinstall HSM client software
apt-get remove --purge safenet-lunaclient
apt-get install safenet-lunaclient

# Reconfigure HSM client
/usr/safenet/lunaclient/bin/vtl createConnection -hostname hsm.example.com
```

### 4. CRL Generation Problems

#### Symptoms
- CRL generation fails or hangs
- CRL not updating with revoked certificates
- CRL distribution issues

#### Diagnostic and Resolution
```bash
#!/bin/bash
# fix_crl_issues.sh

echo "=== CRL Troubleshooting ==="

CA_DIR="/secure/issuingca_ssl"
cd "$CA_DIR"

# Check CRL generation
generate_fresh_crl() {
    echo "Generating fresh CRL..."
    
    # Backup existing CRL
    cp crl/ca.crl.pem crl/ca.crl.pem.backup
    
    # Generate new CRL
    if openssl ca -config openssl_ca.cnf -gencrl -out crl/ca.crl.pem; then
        echo "CRL generation successful"
        
        # Convert to DER format
        openssl crl -in crl/ca.crl.pem -outform DER -out crl/ca.crl
        
        # Update web distribution
        cp crl/ca.crl* /var/www/html/crl/
        echo "CRL distribution updated"
    else
        echo "ERROR: CRL generation failed"
        return 1
    fi
}

# Validate CRL content
validate_crl() {
    echo "Validating CRL content..."
    
    # Check CRL format
    if openssl crl -in crl/ca.crl.pem -text -noout > /dev/null; then
        echo "CRL format: Valid"
    else
        echo "ERROR: Invalid CRL format"
        return 1
    fi
    
    # Check update times
    NEXT_UPDATE=$(openssl crl -in crl/ca.crl.pem -nextupdate -noout)
    echo "CRL Next Update: $NEXT_UPDATE"
}

generate_fresh_crl
validate_crl
```

## Emergency Recovery Procedures

### CA Database Recovery
```bash
#!/bin/bash
# emergency_ca_recovery.sh

BACKUP_DIR="/secure/backups"
RECOVERY_DATE=$(date +%Y%m%d_%H%M%S)

echo "=== CA Emergency Recovery ==="

# Database recovery
recover_ca_database() {
    echo "Recovering CA database..."
    
    # Find latest backup
    LATEST_BACKUP=$(find "$BACKUP_DIR" -name "ca_database_*.db" | sort | tail -1)
    
    if [ -n "$LATEST_BACKUP" ]; then
        echo "Found backup: $LATEST_BACKUP"
        
        # Create recovery copy
        cp "$LATEST_BACKUP" "/secure/ca_database_recovered_$RECOVERY_DATE.db"
        
        # Verify database integrity
        if sqlite3 "/secure/ca_database_recovered_$RECOVERY_DATE.db" "PRAGMA integrity_check;" | grep -q "ok"; then
            echo "Database recovery successful"
            
            # Replace active database (with backup)
            cp /secure/ca_database.db "/secure/ca_database_failed_$RECOVERY_DATE.db"
            cp "/secure/ca_database_recovered_$RECOVERY_DATE.db" /secure/ca_database.db
        else
            echo "ERROR: Recovered database failed integrity check"
        fi
    else
        echo "ERROR: No database backups found"
    fi
}

# HSM key recovery
recover_hsm_keys() {
    echo "Checking HSM key availability..."
    
    if pkcs11-tool --module /usr/lib/pkcs11/libCryptoki2_64.so --list-objects --type privkey; then
        echo "HSM private keys accessible"
    else
        echo "WARNING: HSM private keys not accessible"
        echo "Manual HSM recovery may be required"
    fi
}

recover_ca_database
recover_hsm_keys
```

### Certificate Chain Validation Recovery
```bash
#!/bin/bash
# rebuild_certificate_chains.sh

echo "=== Certificate Chain Reconstruction ==="

# Rebuild certificate chains for all issuing CAs
rebuild_chains() {
    for ca_dir in /secure/issuingca_*; do
        ca_name=$(basename "$ca_dir")
        echo "Rebuilding chain for $ca_name..."
        
        cd "$ca_dir"
        
        # Reconstruct full chain
        cat "certs/${ca_name}.cert.pem" \
            "/secure/policyca/certs/policyca.cert.pem" \
            "/secure/rootca/certs/ca.cert.pem" > "certs/ca-chain.cert.pem"
        
        # Verify reconstructed chain
        if openssl verify -CAfile "/secure/rootca/certs/ca.cert.pem" "certs/ca-chain.cert.pem"; then
            echo "Chain reconstruction successful for $ca_name"
        else
            echo "ERROR: Chain reconstruction failed for $ca_name"
        fi
    done
}

rebuild_chains
```

## Monitoring and Alerting Setup

### Automated Health Checks
```bash
#!/bin/bash
# ca_health_check.sh

echo "=== CA Health Check ==="

# Check critical CA services
check_services() {
    services=("ca-enrollment" "ocsp-responder" "crl-updater")
    
    for service in "${services[@]}"; do
        if systemctl is-active --quiet "$service"; then
            echo "✓ $service: Running"
        else
            echo "✗ $service: Not running"
            logger "CA_HEALTH_ALERT: $service is not running"
        fi
    done
}

# Check certificate expiration warnings
check_ca_expiration() {
    echo "Checking CA certificate expiration..."
    
    for cert_file in /secure/*/certs/*.cert.pem; do
        days_remaining=$(openssl x509 -checkend 7776000 -in "$cert_file" 2>/dev/null)
        if [ $? -ne 0 ]; then
            cert_subject=$(openssl x509 -subject -noout -in "$cert_file" | cut -d= -f2-)
            echo "WARNING: Certificate expiring soon: $cert_subject"
            logger "CA_EXPIRATION_WARNING: $cert_subject expires within 90 days"
        fi
    done
}

# Check disk space
check_disk_space() {
    disk_usage=$(df /secure | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 90 ]; then
        echo "CRITICAL: Disk usage ${disk_usage}% exceeds threshold"
        logger "CA_DISK_CRITICAL: Disk usage ${disk_usage}%"
    fi
}

check_services
check_ca_expiration
check_disk_space
```

## Performance Troubleshooting

### Slow Certificate Issuance
```python
def diagnose_slow_issuance():
    """Identify bottlenecks in certificate issuance process"""
    
    bottlenecks = {
        "csr_validation": "Check CSR parsing and validation logic",
        "domain_validation": "Verify DNS resolution and HTTP validation",
        "hsm_operations": "Monitor HSM response times and utilization",
        "database_writes": "Check database indexing and transaction locks",
        "network_latency": "Test network connectivity to validation endpoints",
        "resource_contention": "Monitor CPU, memory, and I/O utilization"
    }
    
    print("Potential Certificate Issuance Bottlenecks:")
    for bottleneck, solution in bottlenecks.items():
        print(f"- {bottleneck}: {solution}")
    
    return bottlenecks

# Performance optimization checklist
optimization_checklist = [
    "Enable database WAL mode for concurrent access",
    "Implement connection pooling for database operations", 
    "Use batch processing for high-volume issuance",
    "Cache frequently accessed certificates and CRLs",
    "Optimize network timeouts for validation operations",
    "Monitor and tune HSM session limits",
    "Implement horizontal scaling for high availability"
]
```

This troubleshooting guide provides systematic approaches to diagnosing and resolving the most common CA operational issues.