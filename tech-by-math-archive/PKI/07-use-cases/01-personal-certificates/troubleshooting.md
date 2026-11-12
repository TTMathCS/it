# Personal Certificates Troubleshooting Guide

## Overview

This comprehensive troubleshooting guide addresses common issues encountered in personal certificate management, providing systematic diagnostic procedures and proven resolution strategies. Issues are categorized by symptom type with step-by-step resolution approaches.

## Diagnostic Framework

### Issue Classification System
```python
def classify_certificate_issue(symptoms, error_messages):
    """
    Systematically classify certificate issues for targeted troubleshooting
    """
    issue_patterns = {
        "certificate_validation_failure": [
            "certificate verify failed",
            "unable to get local issuer certificate",
            "certificate has expired",
            "certificate not yet valid"
        ],
        "private_key_issues": [
            "private key does not match",
            "unable to load private key",
            "bad decrypt",
            "wrong private key"
        ],
        "application_integration": [
            "certificate not found",
            "access denied",
            "certificate store error",
            "no suitable certificate"
        ],
        "network_connectivity": [
            "timeout",
            "connection refused",
            "OCSP responder error",
            "CRL download failed"
        ]
    }
    
    detected_issues = []
    
    for category, patterns in issue_patterns.items():
        for pattern in patterns:
            if any(pattern.lower() in msg.lower() for msg in error_messages):
                detected_issues.append({
                    "category": category,
                    "confidence": calculate_confidence_score(symptoms, pattern),
                    "priority": get_issue_priority(category)
                })
    
    return sorted(detected_issues, key=lambda x: (x["priority"], -x["confidence"]))
```

### System Environment Assessment
```bash
#!/bin/bash
# comprehensive_system_assessment.sh

echo "=== Personal Certificate System Assessment ==="
echo "Timestamp: $(date)"
echo "User: $(whoami)"
echo "Hostname: $(hostname)"

# Operating System Information
echo -e "\n=== Operating System ==="
uname -a

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "Windows Version:"
    ver
    
    echo -e "\nCertificate Store Status:"
    certlm.msc /s | head -10
    
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macOS Version:"
    sw_vers
    
    echo -e "\nKeychain Status:"
    security list-keychains
    
else
    echo "Linux Distribution:"
    lsb_release -a 2>/dev/null || cat /etc/os-release
    
    echo -e "\nNSS Database Status:"
    if [[ -d "$HOME/.mozilla/firefox" ]]; then
        find "$HOME/.mozilla/firefox" -name "cert9.db" -exec ls -la {} \;
    fi
fi

# OpenSSL Configuration
echo -e "\n=== OpenSSL Information ==="
openssl version -a
echo "OpenSSL Config: $(openssl version -d)"

# Certificate Directory Status
echo -e "\n=== Certificate Directory Status ==="
if [[ -d "$HOME/.pki" ]]; then
    echo "PKI Directory Structure:"
    tree "$HOME/.pki" 2>/dev/null || find "$HOME/.pki" -type f -exec ls -la {} \;
else
    echo "PKI directory not found: $HOME/.pki"
fi

# Network Connectivity Tests
echo -e "\n=== Network Connectivity ==="
echo "Testing OCSP responders:"
timeout 5 curl -s -I http://ocsp.digicert.com >/dev/null && echo "DigiCert OCSP: OK" || echo "DigiCert OCSP: FAIL"
timeout 5 curl -s -I http://ocsp.sectigo.com >/dev/null && echo "Sectigo OCSP: OK" || echo "Sectigo OCSP: FAIL"

echo -e "\nTesting CRL endpoints:"
timeout 5 curl -s -I http://crl.usertrust.com/USERTrustRSACertificationAuthority.crl >/dev/null && echo "UserTrust CRL: OK" || echo "UserTrust CRL: FAIL"
```

## Common Issues and Resolutions

### Certificate Validation Failures

#### Issue 1: "Certificate verify failed: unable to get local issuer certificate"

**Symptoms**:
- Certificate validation fails
- Error message indicates missing issuer certificate
- Applications cannot establish secure connections

**Root Cause Analysis**:
```bash
#!/bin/bash
# diagnose_missing_issuer.sh

CERT_PATH="$1"
if [[ -z "$CERT_PATH" ]]; then
    echo "Usage: $0 <certificate_path>"
    exit 1
fi

echo "=== Certificate Chain Analysis ==="

# Extract certificate details
echo "Certificate Subject:"
openssl x509 -subject -noout -in "$CERT_PATH"

echo -e "\nCertificate Issuer:"
openssl x509 -issuer -noout -in "$CERT_PATH"

# Check if certificate is self-signed
SUBJECT=$(openssl x509 -subject -noout -in "$CERT_PATH" | cut -d= -f2-)
ISSUER=$(openssl x509 -issuer -noout -in "$CERT_PATH" | cut -d= -f2-)

if [[ "$SUBJECT" == "$ISSUER" ]]; then
    echo -e "\nCertificate Type: Self-signed"
else
    echo -e "\nCertificate Type: CA-issued"
    
    # Extract Authority Key Identifier
    echo -e "\nAuthority Key Identifier:"
    openssl x509 -text -noout -in "$CERT_PATH" | grep -A1 "Authority Key Identifier"
    
    # Check for missing intermediate certificates
    echo -e "\nChecking for missing intermediate certificates..."
    openssl verify -verbose -CAfile /etc/ssl/certs/ca-certificates.pem "$CERT_PATH" 2>&1 | \
        grep -q "unable to get local issuer certificate" && \
        echo "DIAGNOSIS: Missing intermediate certificate in chain"
fi
```

**Resolution Steps**:
1. **Download Complete Certificate Chain**:
```bash
# Method 1: Extract full chain from server
echo | openssl s_client -servername example.com -connect example.com:443 \
    -showcerts 2>/dev/null | \
    awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/{print}' > fullchain.pem

# Method 2: Download intermediate certificates manually
ISSUER_URL=$(openssl x509 -text -noout -in certificate.pem | \
    grep "CA Issuers" | \
    sed 's/.*URI://')

if [[ -n "$ISSUER_URL" ]]; then
    curl -s "$ISSUER_URL" -o intermediate.der
    openssl x509 -inform DER -in intermediate.der -out intermediate.pem
    cat certificate.pem intermediate.pem > fullchain.pem
fi
```

2. **Verify Certificate Chain**:
```bash
# Test the complete chain
openssl verify -CAfile ca-bundle.pem fullchain.pem

# If successful, replace original certificate
mv fullchain.pem ~/.pki/certs/alice_email.pem
```

#### Issue 2: "Certificate has expired"

**Symptoms**:
- Applications reject certificate
- Browser shows security warnings
- Email clients fail to send signed messages

**Root Cause Analysis**:
```bash
#!/bin/bash
# diagnose_expired_certificate.sh

CERT_PATH="$1"

echo "=== Certificate Validity Analysis ==="

# Check certificate validity dates
echo "Certificate Validity:"
openssl x509 -dates -noout -in "$CERT_PATH"

# Calculate days until/since expiration
NOT_AFTER=$(openssl x509 -enddate -noout -in "$CERT_PATH" | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$NOT_AFTER" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$NOT_AFTER" +%s)
CURRENT_EPOCH=$(date +%s)
DAYS_DIFF=$(( (EXPIRY_EPOCH - CURRENT_EPOCH) / 86400 ))

if [[ $DAYS_DIFF -lt 0 ]]; then
    echo "STATUS: Certificate EXPIRED ${DAYS_DIFF#-} days ago"
    echo "ACTION REQUIRED: Certificate renewal needed immediately"
elif [[ $DAYS_DIFF -lt 30 ]]; then
    echo "STATUS: Certificate expires in $DAYS_DIFF days"
    echo "ACTION RECOMMENDED: Schedule certificate renewal"
else
    echo "STATUS: Certificate valid for $DAYS_DIFF days"
fi

# Check certificate usage in applications
echo -e "\n=== Application Usage Check ==="
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "Checking Windows Certificate Store usage..."
    # Windows-specific certificate usage check would go here
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Checking macOS Keychain usage..."
    security find-certificate -a -c "$(openssl x509 -subject -noout -in "$CERT_PATH" | cut -d= -f2-)" ~/Library/Keychains/login.keychain-db
else
    echo "Checking NSS database usage..."
    # Linux NSS database check would go here
fi
```

**Resolution Steps**:
1. **Immediate Certificate Renewal**:
```bash
# Generate new CSR with existing private key
openssl req -new -key ~/.pki/private/alice_master.key \
    -out ~/.pki/csr/alice_renewal.csr \
    -config ~/.pki/openssl.cnf

# Submit renewal request to CA
# (Process varies by CA - typically via web interface or API)

# After receiving new certificate, validate and install
openssl verify -CAfile ~/.pki/certs/ca_chain.pem ~/.pki/certs/alice_renewed.pem
```

2. **Update Application Configurations**:
```bash
# Update PKCS#12 bundle for applications
openssl pkcs12 -export \
    -out ~/.pki/certs/alice_renewed.p12 \
    -inkey ~/.pki/private/alice_master.key \
    -in ~/.pki/certs/alice_renewed.pem \
    -certfile ~/.pki/certs/ca_chain.pem
```

### Private Key Issues

#### Issue 3: "Private key does not match certificate"

**Symptoms**:
- SSL/TLS handshake failures
- S/MIME signing operations fail
- Application reports key mismatch

**Diagnostic Procedure**:
```bash
#!/bin/bash
# diagnose_key_mismatch.sh

CERT_PATH="$1"
KEY_PATH="$2"

echo "=== Key-Certificate Matching Analysis ==="

# Extract public key from certificate
CERT_PUBKEY_HASH=$(openssl x509 -pubkey -noout -in "$CERT_PATH" | \
    openssl rsa -pubin -outform DER 2>/dev/null | \
    openssl dgst -sha256 -hex)

echo "Certificate public key hash: $CERT_PUBKEY_HASH"

# Extract public key from private key
if openssl ec -in "$KEY_PATH" -noout 2>/dev/null; then
    # EC private key
    KEY_PUBKEY_HASH=$(openssl ec -in "$KEY_PATH" -pubout -outform DER 2>/dev/null | \
        openssl dgst -sha256 -hex)
    echo "EC private key public component hash: $KEY_PUBKEY_HASH"
elif openssl rsa -in "$KEY_PATH" -noout 2>/dev/null; then
    # RSA private key
    KEY_PUBKEY_HASH=$(openssl rsa -in "$KEY_PATH" -pubout -outform DER 2>/dev/null | \
        openssl dgst -sha256 -hex)
    echo "RSA private key public component hash: $KEY_PUBKEY_HASH"
else
    echo "ERROR: Unable to process private key format"
    exit 1
fi

# Compare hashes
if [[ "$CERT_PUBKEY_HASH" == "$KEY_PUBKEY_HASH" ]]; then
    echo "RESULT: Private key matches certificate ✓"
else
    echo "RESULT: Private key does NOT match certificate ✗"
    echo "ACTION REQUIRED: Use correct private key or regenerate certificate"
fi
```

**Resolution Strategies**:
1. **Locate Correct Private Key**:
```bash
# Search for matching private keys
for key_file in ~/.pki/private/*.key; do
    echo "Checking: $key_file"
    if ./diagnose_key_mismatch.sh certificate.pem "$key_file" | grep -q "matches certificate"; then
        echo "FOUND: Matching private key at $key_file"
        break
    fi
done
```

2. **Generate New Certificate with Existing Key**:
```bash
# If you have the correct private key but wrong certificate
openssl req -new -key correct_private.key -out new_csr.csr
# Submit CSR to CA for new certificate issuance
```

#### Issue 4: "Unable to load private key" / "Bad decrypt"

**Symptoms**:
- Private key file cannot be read
- Password-protected keys fail to decrypt
- Permission denied errors

**Diagnostic Steps**:
```bash
#!/bin/bash
# diagnose_private_key_access.sh

KEY_PATH="$1"

echo "=== Private Key Access Analysis ==="

# Check file existence and permissions
if [[ ! -f "$KEY_PATH" ]]; then
    echo "ERROR: Private key file does not exist: $KEY_PATH"
    exit 1
fi

echo "File permissions: $(ls -la "$KEY_PATH")"

# Check file readability
if [[ ! -r "$KEY_PATH" ]]; then
    echo "ERROR: File is not readable by current user"
    echo "SOLUTION: Fix file permissions with: chmod 400 $KEY_PATH"
    exit 1
fi

# Determine key format and encryption status
echo -e "\nPrivate key format analysis:"
if grep -q "BEGIN ENCRYPTED PRIVATE KEY" "$KEY_PATH"; then
    echo "Format: PKCS#8 Encrypted"
    echo "Testing password decryption..."
    read -s -p "Enter private key password: " password
    echo
    if openssl pkcs8 -in "$KEY_PATH" -passin pass:"$password" -noout 2>/dev/null; then
        echo "Password validation: SUCCESS"
    else
        echo "Password validation: FAILED"
        echo "SOLUTION: Verify correct password or recover from backup"
    fi
elif grep -q "BEGIN RSA PRIVATE KEY" "$KEY_PATH"; then
    if grep -q "Proc-Type: 4,ENCRYPTED" "$KEY_PATH"; then
        echo "Format: Traditional RSA Encrypted"
        read -s -p "Enter private key password: " password
        echo
        if openssl rsa -in "$KEY_PATH" -passin pass:"$password" -noout 2>/dev/null; then
            echo "Password validation: SUCCESS"
        else
            echo "Password validation: FAILED"
        fi
    else
        echo "Format: Traditional RSA Unencrypted"
        if openssl rsa -in "$KEY_PATH" -noout 2>/dev/null; then
            echo "Key validation: SUCCESS"
        else
            echo "Key validation: FAILED - File may be corrupted"
        fi
    fi
elif grep -q "BEGIN EC PRIVATE KEY" "$KEY_PATH"; then
    echo "Format: Traditional EC"
    if openssl ec -in "$KEY_PATH" -noout 2>/dev/null; then
        echo "Key validation: SUCCESS"
    else
        echo "Key validation: FAILED"
    fi
elif grep -q "BEGIN PRIVATE KEY" "$KEY_PATH"; then
    echo "Format: PKCS#8 Unencrypted"
    if openssl pkcs8 -in "$KEY_PATH" -nocrypt -noout 2>/dev/null; then
        echo "Key validation: SUCCESS"
    else
        echo "Key validation: FAILED"
    fi
else
    echo "Format: Unknown or corrupted"
    echo "SOLUTION: Restore from backup or regenerate key pair"
fi
```

**Resolution Approaches**:
1. **Password Recovery**:
```bash
# If password is forgotten, try common passwords
common_passwords=("password" "123456" "certificate" "$(whoami)" "$(hostname)")

for pwd in "${common_passwords[@]}"; do
    if openssl rsa -in private.key -passin pass:"$pwd" -noout 2>/dev/null; then
        echo "Password found: $pwd"
        break
    fi
done
```

2. **Key Format Conversion**:
```bash
# Convert between different private key formats
# PKCS#8 to traditional RSA
openssl pkcs8 -in pkcs8_key.pem -traditional -out rsa_key.pem

# Traditional RSA to PKCS#8
openssl pkcs8 -topk8 -in rsa_key.pem -out pkcs8_key.pem

# Remove password protection (if needed for troubleshooting)
openssl rsa -in encrypted_key.pem -out unencrypted_key.pem
chmod 400 unencrypted_key.pem
```

### Application Integration Issues

#### Issue 5: Email Client Certificate Problems

**Symptoms**:
- Unable to send signed emails
- Email client doesn't recognize certificate
- S/MIME options grayed out

**Thunderbird-Specific Troubleshooting**:
```bash
#!/bin/bash
# thunderbird_certificate_troubleshooting.sh

echo "=== Thunderbird Certificate Troubleshooting ==="

# Find Thunderbird profile directory
TB_PROFILE=""
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    TB_PROFILE="$APPDATA/Thunderbird/Profiles"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    TB_PROFILE="$HOME/Library/Thunderbird/Profiles"
else
    TB_PROFILE="$HOME/.thunderbird"
fi

if [[ ! -d "$TB_PROFILE" ]]; then
    echo "ERROR: Thunderbird profile directory not found"
    exit 1
fi

# Find active profile
ACTIVE_PROFILE=$(find "$TB_PROFILE" -name "*.default-*" -type d | head -1)
if [[ -z "$ACTIVE_PROFILE" ]]; then
    echo "ERROR: No active Thunderbird profile found"
    exit 1
fi

echo "Active Profile: $ACTIVE_PROFILE"

# Check certificate database
CERT_DB="$ACTIVE_PROFILE/cert9.db"
if [[ -f "$CERT_DB" ]]; then
    echo "Certificate database found: $CERT_DB"
    
    # List personal certificates
    echo -e "\nPersonal certificates in Thunderbird:"
    certutil -L -d sql:"$ACTIVE_PROFILE" -n "Personal"
    
    # Check for certificate validity
    certutil -V -d sql:"$ACTIVE_PROFILE" -u S -n "Alice Thompson"
else
    echo "ERROR: Certificate database not found"
fi

# Check S/MIME preferences
PREFS_FILE="$ACTIVE_PROFILE/prefs.js"
if [[ -f "$PREFS_FILE" ]]; then
    echo -e "\nS/MIME configuration:"
    grep -i "mail.identity.*\.signing_cert_name\|mail.identity.*\.encryption_cert_name" "$PREFS_FILE"
fi
```

**Resolution Steps**:
1. **Re-import Certificate**:
```bash
# Export certificate from system store
openssl pkcs12 -export -out email_cert.p12 \
    -in ~/.pki/certs/alice_email.pem \
    -inkey ~/.pki/private/alice_master.key \
    -certfile ~/.pki/certs/ca_chain.pem

# Import into Thunderbird (manual process)
echo "Manual steps required:"
echo "1. Open Thunderbird → Preferences → Privacy & Security"
echo "2. Click 'Manage Certificates'"
echo "3. Your Certificates tab → Import"
echo "4. Select email_cert.p12"
```

2. **Configure S/MIME Settings**:
```bash
# Thunderbird S/MIME configuration
echo "Configure S/MIME in Thunderbird:"
echo "1. Account Settings → [Email Account] → End-to-End Encryption"
echo "2. Select certificate for Digital Signing"
echo "3. Select certificate for Encryption"
echo "4. Enable 'Sign messages by default'"
```

#### Issue 6: Browser Certificate Problems

**Symptoms**:
- Client certificate authentication fails
- Browser doesn't prompt for certificate selection
- "No suitable certificate" errors

**Browser-Specific Diagnostics**:
```bash
#!/bin/bash
# browser_certificate_diagnostics.sh

echo "=== Browser Certificate Diagnostics ==="

# Chrome/Chromium certificate check
if command -v google-chrome >/dev/null 2>&1; then
    echo "Chrome certificate store check:"
    # Chrome uses system certificate store
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Chrome uses NSS database:"
        find ~/.mozilla/firefox -name "cert9.db" 2>/dev/null | head -1
    fi
fi

# Firefox certificate check
if command -v firefox >/dev/null 2>&1; then
    echo -e "\nFirefox certificate check:"
    FF_PROFILE=$(find ~/.mozilla/firefox -name "*.default-*" -type d | head -1)
    if [[ -n "$FF_PROFILE" ]]; then
        echo "Firefox profile: $FF_PROFILE"
        if [[ -f "$FF_PROFILE/cert9.db" ]]; then
            echo "Personal certificates in Firefox:"
            certutil -L -d sql:"$FF_PROFILE" | grep -E "^[^,]*,,"
        fi
    fi
fi

# Test client certificate authentication
echo -e "\nTesting client certificate authentication:"
read -p "Enter test URL requiring client certificates: " TEST_URL
if [[ -n "$TEST_URL" ]]; then
    curl -v --cert ~/.pki/certs/alice_email.pem \
         --key ~/.pki/private/alice_master.key \
         "$TEST_URL" 2>&1 | grep -E "SSL certificate|client certificate"
fi
```

### Network and Connectivity Issues

#### Issue 7: OCSP/CRL Validation Failures

**Symptoms**:
- Certificate validation takes very long
- "OCSP responder error" messages
- Applications timeout during certificate validation

**Network Diagnostics**:
```bash
#!/bin/bash
# network_certificate_diagnostics.sh

echo "=== Certificate Validation Network Diagnostics ==="

# Extract OCSP and CRL URLs from certificate
CERT_PATH="$1"
if [[ -z "$CERT_PATH" ]]; then
    echo "Usage: $0 <certificate_path>"
    exit 1
fi

echo "Certificate: $CERT_PATH"

# Extract OCSP responder URL
OCSP_URL=$(openssl x509 -text -noout -in "$CERT_PATH" | \
    grep -A1 "OCSP - URI" | \
    grep "URI:" | \
    sed 's/.*URI://')

if [[ -n "$OCSP_URL" ]]; then
    echo "OCSP Responder: $OCSP_URL"
    
    # Test OCSP responder connectivity
    echo "Testing OCSP connectivity..."
    if curl -s --max-time 10 -I "$OCSP_URL" >/dev/null; then
        echo "OCSP responder: ACCESSIBLE"
    else
        echo "OCSP responder: NOT ACCESSIBLE"
        echo "SOLUTION: Check firewall/proxy settings"
    fi
    
    # Test actual OCSP request
    echo "Testing OCSP validation..."
    openssl ocsp -issuer ~/.pki/certs/ca_chain.pem \
                 -cert "$CERT_PATH" \
                 -url "$OCSP_URL" \
                 -noverify 2>&1 | head -5
else
    echo "No OCSP responder URL found in certificate"
fi

# Extract CRL distribution points
CRL_URLS=$(openssl x509 -text -noout -in "$CERT_PATH" | \
    grep -A3 "CRL Distribution Points" | \
    grep "URI:" | \
    sed 's/.*URI://')

if [[ -n "$CRL_URLS" ]]; then
    echo -e "\nCRL Distribution Points:"
    echo "$CRL_URLS" | while read -r crl_url; do
        echo "CRL URL: $crl_url"
        
        # Test CRL accessibility
        if curl -s --max-time 10 -I "$crl_url" >/dev/null; then
            echo "CRL: ACCESSIBLE"
            
            # Download and check CRL
            curl -s "$crl_url" -o temp_crl.crl
            if openssl crl -inform DER -in temp_crl.crl -text -noout >/dev/null 2>&1; then
                echo "CRL format: DER (valid)"
            elif openssl crl -inform PEM -in temp_crl.crl -text -noout >/dev/null 2>&1; then
                echo "CRL format: PEM (valid)"
            else
                echo "CRL format: INVALID"
            fi
            rm -f temp_crl.crl
        else
            echo "CRL: NOT ACCESSIBLE"
        fi
    done
fi
```

## Advanced Troubleshooting Techniques

### Certificate Transparency Log Analysis
```bash
#!/bin/bash
# certificate_transparency_analysis.sh

DOMAIN="$1"
if [[ -z "$DOMAIN" ]]; then
    echo "Usage: $0 <domain_name>"
    exit 1
fi

echo "=== Certificate Transparency Analysis for $DOMAIN ==="

# Query crt.sh database
echo "Querying Certificate Transparency logs..."
CT_RESULTS=$(curl -s "https://crt.sh/?q=$DOMAIN&output=json" | jq -r '.[] | "\(.id) \(.name_value) \(.not_before) \(.not_after)"' | head -10)

if [[ -n "$CT_RESULTS" ]]; then
    echo "Recent certificates found:"
    echo "$CT_RESULTS"
    
    # Check for unexpected certificates
    echo -e "\nAnalyzing for suspicious certificates..."
    echo "$CT_RESULTS" | while read -r line; do
        cert_id=$(echo "$line" | cut -d' ' -f1)
        cert_names=$(echo "$line" | cut -d' ' -f2)
        
        # Look for wildcard certificates or unexpected subdomains
        if echo "$cert_names" | grep -q "*\."; then
            echo "ALERT: Wildcard certificate found - ID: $cert_id"
        fi
        
        # Check for certificates from unexpected CAs
        # (This would require additional analysis of the certificate details)
    done
else
    echo "No certificates found in CT logs for $DOMAIN"
fi
```

### Hardware Security Module Diagnostics
```bash
#!/bin/bash
# hsm_diagnostics.sh

echo "=== Hardware Security Module Diagnostics ==="

# Check for TPM availability
if command -v tpm2_getcap >/dev/null 2>&1; then
    echo "TPM 2.0 detected"
    echo "TPM Status:"
    tpm2_getcap properties-fixed | grep -E "TPM2_PT_MANUFACTURER|TPM2_PT_VENDOR_STRING|TPM2_PT_FIRMWARE_VERSION"
    
    # Test TPM random number generation
    echo -e "\nTesting TPM random generation:"
    tpm2_getrandom 16 | xxd
else
    echo "TPM not available or not configured"
fi

# Check for PKCS#11 tokens
if command -v pkcs11-tool >/dev/null 2>&1; then
    echo -e "\nPKCS#11 Token Detection:"
    pkcs11-tool --list-slots
    
    # List certificates on tokens
    pkcs11-tool --list-objects --type cert | head -20
else
    echo "PKCS#11 tools not available"
fi

# Check for smart card readers
if command -v pcsc_scan >/dev/null 2>&1; then
    echo -e "\nSmart Card Reader Detection:"
    timeout 5s pcsc_scan 2>/dev/null || echo "No smart card readers detected or timeout"
fi
```

## Recovery Procedures

### Emergency Certificate Recovery
```bash
#!/bin/bash
# emergency_certificate_recovery.sh

BACKUP_DIR="$HOME/.pki/backup"
RECOVERY_DATE=$(date +%Y%m%d_%H%M%S)

echo "=== Emergency Certificate Recovery ==="
echo "Recovery session: $RECOVERY_DATE"

# Create recovery workspace
RECOVERY_DIR="/tmp/cert_recovery_$RECOVERY_DATE"
mkdir -p "$RECOVERY_DIR"
cd "$RECOVERY_DIR"

# Attempt to recover from various backup sources
echo "Searching for certificate backups..."

# Method 1: Local backups
if [[ -d "$BACKUP_DIR" ]]; then
    echo "Found local backup directory: $BACKUP_DIR"
    LATEST_BACKUP=$(find "$BACKUP_DIR" -name "*.tar.gz" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
    if [[ -n "$LATEST_BACKUP" ]]; then
        echo "Latest backup: $LATEST_BACKUP"
        tar -xzf "$LATEST_BACKUP" -C ./
        echo "Backup extracted to recovery workspace"
    fi
fi

# Method 2: System certificate stores
echo -e "\nSearching system certificate stores..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows Certificate Store export
    powershell -Command "Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object {$_.Subject -like '*Alice*'} | Export-Certificate -FilePath 'recovered_cert.der'"
    if [[ -f "recovered_cert.der" ]]; then
        openssl x509 -inform DER -in recovered_cert.der -out recovered_cert.pem
        echo "Certificate recovered from Windows Certificate Store"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS Keychain export
    security find-certificate -a -p ~/Library/Keychains/login.keychain-db > keychain_certs.pem
    if [[ -s "keychain_certs.pem" ]]; then
        echo "Certificates exported from macOS Keychain"
    fi
fi

# Method 3: Browser certificate stores
if [[ -d "$HOME/.mozilla/firefox" ]]; then
    FF_PROFILE=$(find "$HOME/.mozilla/firefox" -name "*.default-*" -type d | head -1)
    if [[ -n "$FF_PROFILE" ]]; then
        cp "$FF_PROFILE/cert9.db" ./firefox_cert.db 2>/dev/null
        echo "Firefox certificate database copied for analysis"
    fi
fi

# Analyze recovered certificates
echo -e "\n=== Recovery Analysis ==="
for cert_file in *.pem *.crt; do
    if [[ -f "$cert_file" ]]; then
        echo "Analyzing: $cert_file"
        openssl x509 -subject -dates -noout -in "$cert_file" 2>/dev/null | head -2
    fi
done

echo -e "\nRecovery workspace: $RECOVERY_DIR"
echo "Review recovered certificates and copy needed files to ~/.pki/"
```

This comprehensive troubleshooting guide provides systematic approaches to diagnosing and resolving the most common personal certificate management issues.