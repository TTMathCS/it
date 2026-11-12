# Email Security Troubleshooting Guide

## Overview

This comprehensive troubleshooting guide addresses common issues encountered in email security implementations using S/MIME certificates and PKI infrastructure. Issues are systematically categorized with diagnostic procedures and proven resolution strategies for enterprise email security deployments.

## Diagnostic Framework

### Issue Classification System
```python
def classify_email_security_issue(symptoms, error_messages, system_context):
    """
    Systematically classify email security issues for targeted troubleshooting
    """
    issue_patterns = {
        "certificate_validation_failure": [
            "certificate verify failed",
            "unable to get local issuer certificate",
            "certificate has expired",
            "certificate not yet valid",
            "unable to verify the first certificate"
        ],
        "smime_encryption_issues": [
            "encryption failed",
            "no suitable certificate found",
            "recipient certificate not found",
            "invalid recipient",
            "encryption algorithm not supported"
        ],
        "smime_signature_issues": [
            "signature verification failed",
            "signer certificate not found",
            "invalid signature",
            "signature algorithm not supported",
            "certificate chain invalid"
        ],
        "email_gateway_issues": [
            "gateway processing error",
            "policy violation",
            "content filtering blocked",
            "virus scanning failed",
            "dlp policy triggered"
        ],
        "client_integration_issues": [
            "outlook certificate error",
            "thunderbird smime configuration",
            "certificate import failed",
            "private key not accessible",
            "certificate store error"
        ]
    }
    
    detected_issues = []
    
    for category, patterns in issue_patterns.items():
        for pattern in patterns:
            if any(pattern.lower() in msg.lower() for msg in error_messages):
                detected_issues.append({
                    "category": category,
                    "pattern": pattern,
                    "confidence": calculate_confidence_score(symptoms, pattern),
                    "priority": get_issue_priority(category, system_context)
                })
    
    return sorted(detected_issues, key=lambda x: (x["priority"], -x["confidence"]))
```

### System Environment Assessment
```bash
#!/bin/bash
# comprehensive_email_security_assessment.sh

echo "=== Email Security System Assessment ==="
echo "Timestamp: $(date)"
echo "System: $(hostname)"
echo "User: $(whoami)"

# Email System Information
echo -e "\n=== Email Infrastructure ==="
if systemctl is-active --quiet postfix; then
    echo "Postfix Status: Running"
    postconf -n | grep -E "(tls|smime|cert)"
elif systemctl is-active --quiet sendmail; then
    echo "Sendmail Status: Running"
    sendmail -bt -C/etc/mail/sendmail.cf < /dev/null 2>&1 | head -5
elif command -v powershell >/dev/null; then
    echo "Exchange Server Detection:"
    powershell "Get-Service MSExchangeServiceHost -ErrorAction SilentlyContinue"
fi

# Certificate Store Analysis
echo -e "\n=== Certificate Store Status ==="
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "Windows Certificate Store:"
    certlm.msc /s | head -10
    
    echo -e "\nS/MIME Certificates:"
    powershell "Get-ChildItem Cert:\CurrentUser\My | Where-Object {$_.EnhancedKeyUsageList -match 'Secure Email'}"
    
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "macOS Keychain:"
    security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain | grep -c "BEGIN CERTIFICATE"
    
    echo -e "\nS/MIME Certificates:"
    security find-certificate -a -c "smime" login.keychain
    
else
    echo "NSS Database Status:"
    if [[ -d "$HOME/.mozilla/firefox" ]]; then
        find "$HOME/.mozilla/firefox" -name "cert9.db" -exec ls -la {} \;
    fi
    
    if [[ -d "/etc/pki/tls/certs" ]]; then
        echo -e "\nSystem Certificates:"
        ls -la /etc/pki/tls/certs/ | head -10
    fi
fi

# OpenSSL Configuration
echo -e "\n=== OpenSSL Configuration ==="
openssl version -a
echo "Config Directory: $(openssl version -d)"

# S/MIME Capability Test
echo -e "\n=== S/MIME Capability Test ==="
if command -v openssl >/dev/null; then
    echo "Testing S/MIME encryption capability..."
    echo "Test message" | openssl smime -encrypt -aes256 \
        -in /dev/stdin -out /tmp/test_encrypted.p7m \
        /etc/ssl/certs/ca-certificates.crt 2>/dev/null \
        && echo "S/MIME encryption: OK" || echo "S/MIME encryption: FAILED"
fi

# Email Client Detection
echo -e "\n=== Email Client Configuration ==="
if command -v thunderbird >/dev/null; then
    echo "Thunderbird detected"
    find ~/.thunderbird -name "prefs.js" -exec grep -l "mail.identity.*cert" {} \; 2>/dev/null
fi

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "Outlook Configuration:"
    reg query "HKCU\\Software\\Microsoft\\Office\\16.0\\Outlook\\Security" /v "EncryptionCert" 2>/dev/null || echo "No Outlook encryption certificate configured"
fi

# Network Connectivity Tests
echo -e "\n=== Network Connectivity ==="
echo "Testing OCSP responders:"
timeout 5 curl -s -I http://ocsp.digicert.com >/dev/null && echo "DigiCert OCSP: OK" || echo "DigiCert OCSP: FAIL"
timeout 5 curl -s -I http://ocsp.comodoca.com >/dev/null && echo "Comodo OCSP: OK" || echo "Comodo OCSP: FAIL"

echo "Testing CRL distribution:"
timeout 5 curl -s -I http://crl.microsoft.com/pki/mscorp/crl/msitwww2.crl >/dev/null && echo "Microsoft CRL: OK" || echo "Microsoft CRL: FAIL"

echo -e "\n=== Assessment Complete ==="
```

## Common Issues and Solutions

### 1. Certificate Validation Failures

#### Issue: Certificate Chain Validation Errors
```bash
# Diagnostic commands
openssl verify -verbose -CAfile /etc/ssl/certs/ca-bundle.crt certificate.pem

# Common error: "unable to get local issuer certificate"
# Solution: Add intermediate certificates to chain
cat user_cert.pem intermediate.pem root.pem > full_chain.pem

# Test the complete chain
openssl verify -CAfile root.pem -untrusted intermediate.pem user_cert.pem
```

**Resolution Steps:**
1. **Identify Missing Intermediate Certificates**:
```bash
# Extract certificate chain information
openssl x509 -in certificate.pem -noout -text | grep -A2 "Issuer:"
openssl x509 -in certificate.pem -noout -text | grep -A2 "Subject:"

# Download missing intermediate certificates
wget "http://crt.sectigo.com/SectigoRSADomainValidationSecureServerCA.crt"
openssl x509 -inform DER -in SectigoRSADomainValidationSecureServerCA.crt -outform PEM -out intermediate.pem
```

2. **Rebuild Certificate Bundle**:
```bash
# Create proper certificate chain
cat certificate.pem > complete_chain.pem
cat intermediate.pem >> complete_chain.pem
cat root_ca.pem >> complete_chain.pem

# Verify the rebuilt chain
openssl verify -CAfile root_ca.pem -untrusted intermediate.pem certificate.pem
```

#### Issue: Certificate Expiration
```python
def check_certificate_expiration(cert_path):
    """
    Comprehensive certificate expiration checking
    """
    import subprocess
    import datetime
    from dateutil import parser
    
    try:
        # Get certificate expiration date
        result = subprocess.run([
            'openssl', 'x509', '-in', cert_path, '-noout', '-enddate'
        ], capture_output=True, text=True, check=True)
        
        # Parse expiration date
        exp_line = result.stdout.strip()
        exp_date_str = exp_line.split('=')[1]
        exp_date = parser.parse(exp_date_str)
        
        # Calculate days until expiration
        now = datetime.datetime.now(exp_date.tzinfo)
        days_until_exp = (exp_date - now).days
        
        if days_until_exp < 0:
            return {"status": "EXPIRED", "days": abs(days_until_exp)}
        elif days_until_exp < 30:
            return {"status": "EXPIRING_SOON", "days": days_until_exp}
        else:
            return {"status": "VALID", "days": days_until_exp}
            
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

# Automated renewal check
def setup_certificate_renewal_monitoring():
    """
    Setup automated certificate renewal monitoring
    """
    cron_job = """
# Check email certificates daily at 2 AM
0 2 * * * /usr/local/bin/check_email_certificates.sh
"""
    
    renewal_script = """
#!/bin/bash
# check_email_certificates.sh
CERT_DIR="/etc/ssl/email-certs"
THRESHOLD_DAYS=30

for cert in "$CERT_DIR"/*.pem; do
    if [[ -f "$cert" ]]; then
        days=$(python3 -c "
import subprocess, datetime
from dateutil import parser
result = subprocess.run(['openssl', 'x509', '-in', '$cert', '-noout', '-enddate'], capture_output=True, text=True)
exp_date = parser.parse(result.stdout.split('=')[1])
days_left = (exp_date - datetime.datetime.now(exp_date.tzinfo)).days
print(days_left)
")
        
        if [[ $days -lt $THRESHOLD_DAYS ]]; then
            echo "WARNING: Certificate $cert expires in $days days"
            # Trigger renewal process
            /usr/local/bin/renew_certificate.sh "$cert"
        fi
    fi
done
"""
    
    return {"cron_job": cron_job, "script": renewal_script}
```

### 2. S/MIME Encryption and Signing Issues

#### Issue: Recipient Certificate Not Found
```bash
# Diagnostic: Check recipient certificate availability
openssl smime -encrypt -in message.txt -out encrypted.p7m \
    recipient_cert.pem 2>&1 | grep -i "error"

# Common causes and solutions:
# 1. Certificate not in directory/LDAP
# 2. Certificate expired or revoked
# 3. Wrong certificate format
```

**Resolution Steps:**
1. **Certificate Directory Lookup**:
```bash
# LDAP certificate lookup
ldapsearch -x -H ldap://directory.company.com \
    -b "dc=company,dc=com" \
    "(mail=user@company.com)" userSMIMECertificate

# Active Directory certificate lookup
powershell "Get-ADUser -Filter {mail -eq 'user@company.com'} -Properties certificates"
```

2. **Certificate Format Conversion**:
```bash
# Convert DER to PEM format
openssl x509 -inform DER -in certificate.der -outform PEM -out certificate.pem

# Extract certificate from PKCS#12 bundle
openssl pkcs12 -in certificate.p12 -clcerts -nokeys -out certificate.pem

# Verify certificate format
openssl x509 -in certificate.pem -text -noout
```

#### Issue: S/MIME Signature Verification Failures
```python
def diagnose_signature_verification():
    """
    Comprehensive S/MIME signature verification diagnostics
    """
    diagnostic_steps = {
        "certificate_chain_validation": {
            "command": "openssl smime -verify -in signed_message.p7m -CAfile ca_bundle.pem",
            "common_errors": [
                "certificate verify failed",
                "unable to get local issuer certificate"
            ],
            "solutions": [
                "Add intermediate certificates to CA bundle",
                "Check certificate revocation status",
                "Verify certificate validity period"
            ]
        },
        "signature_algorithm_check": {
            "command": "openssl smime -verify -in signed_message.p7m -noverify -text",
            "common_errors": [
                "unsupported signature algorithm",
                "weak hash algorithm"
            ],
            "solutions": [
                "Update OpenSSL to support modern algorithms",
                "Configure client to use stronger algorithms",
                "Check algorithm policy restrictions"
            ]
        },
        "certificate_purpose_validation": {
            "command": "openssl x509 -in signer_cert.pem -noout -ext keyUsage,extendedKeyUsage",
            "required_extensions": [
                "Digital Signature",
                "E-mail Protection"
            ],
            "solutions": [
                "Request new certificate with correct key usage",
                "Verify certificate template configuration"
            ]
        }
    }
    
    return diagnostic_steps
```

### 3. Email Client Integration Issues

#### Issue: Outlook S/MIME Configuration Problems
```powershell
# Outlook S/MIME Diagnostic Script
function Diagnose-OutlookSMIME {
    param(
        [string]$UserEmail
    )
    
    Write-Host "=== Outlook S/MIME Diagnostics ==="
    
    # Check certificate installation
    $certs = Get-ChildItem Cert:\CurrentUser\My | Where-Object {
        $_.Subject -match $UserEmail -or $_.SubjectAlternativeName -match $UserEmail
    }
    
    if ($certs.Count -eq 0) {
        Write-Host "ERROR: No certificates found for $UserEmail"
        Write-Host "Solution: Install S/MIME certificate in personal store"
        return
    }
    
    foreach ($cert in $certs) {
        Write-Host "Certificate Found:"
        Write-Host "  Subject: $($cert.Subject)"
        Write-Host "  Issuer: $($cert.Issuer)"
        Write-Host "  Valid From: $($cert.NotBefore)"
        Write-Host "  Valid To: $($cert.NotAfter)"
        
        # Check key usage
        $keyUsage = $cert.Extensions | Where-Object {$_.Oid.Value -eq "2.5.29.15"}
        if ($keyUsage) {
            Write-Host "  Key Usage: $($keyUsage.Format($true))"
        }
        
        # Check extended key usage
        $extKeyUsage = $cert.Extensions | Where-Object {$_.Oid.Value -eq "2.5.29.37"}
        if ($extKeyUsage -and $extKeyUsage.Format($true) -match "Secure Email") {
            Write-Host "  S/MIME: Supported"
        } else {
            Write-Host "  S/MIME: NOT Supported - Certificate not suitable for email"
        }
        
        # Check private key availability
        if ($cert.HasPrivateKey) {
            Write-Host "  Private Key: Available"
        } else {
            Write-Host "  Private Key: Missing - Cannot sign or decrypt"
        }
    }
    
    # Check Outlook registry settings
    $regPath = "HKCU:\Software\Microsoft\Office\16.0\Outlook\Security"
    if (Test-Path $regPath) {
        $encCert = Get-ItemProperty -Path $regPath -Name "EncryptionCert" -ErrorAction SilentlyContinue
        $sigCert = Get-ItemProperty -Path $regPath -Name "SigningCert" -ErrorAction SilentlyContinue
        
        Write-Host "`nOutlook S/MIME Configuration:"
        Write-Host "  Encryption Certificate: $($encCert.EncryptionCert -ne $null ? 'Configured' : 'Not Set')"
        Write-Host "  Signing Certificate: $($sigCert.SigningCert -ne $null ? 'Configured' : 'Not Set')"
    }
}

# Usage
Diagnose-OutlookSMIME -UserEmail "user@company.com"
```

#### Issue: Thunderbird S/MIME Setup Problems
```bash
#!/bin/bash
# thunderbird_smime_diagnostic.sh

diagnose_thunderbird_smime() {
    local profile_path="$HOME/.thunderbird"
    
    echo "=== Thunderbird S/MIME Diagnostics ==="
    
    # Find Thunderbird profiles
    if [[ ! -d "$profile_path" ]]; then
        echo "ERROR: Thunderbird profile directory not found"
        echo "Solution: Install and run Thunderbird first"
        return 1
    fi
    
    # Check profiles.ini
    profiles_ini="$profile_path/profiles.ini"
    if [[ ! -f "$profiles_ini" ]]; then
        echo "ERROR: Thunderbird profiles.ini not found"
        return 1
    fi
    
    # Extract default profile path
    default_profile=$(grep "Path=" "$profiles_ini" | head -1 | cut -d'=' -f2)
    profile_dir="$profile_path/$default_profile"
    
    echo "Profile Directory: $profile_dir"
    
    # Check certificate database
    cert_db="$profile_dir/cert9.db"
    if [[ -f "$cert_db" ]]; then
        echo "Certificate Database: Found"
        
        # Check for S/MIME certificates (requires NSS tools)
        if command -v certutil >/dev/null; then
            echo "S/MIME Certificates:"
            certutil -L -d "sql:$profile_dir" | grep -E "(u,|U,)" || echo "  No user certificates found"
        fi
    else
        echo "Certificate Database: Missing"
        echo "Solution: Import certificates into Thunderbird"
    fi
    
    # Check S/MIME preferences
    prefs_file="$profile_dir/prefs.js"
    if [[ -f "$prefs_file" ]]; then
        echo -e "\nS/MIME Configuration:"
        
        # Check encryption preferences
        if grep -q "mail.identity.*encryptionpolicy" "$prefs_file"; then
            echo "  Encryption Policy: Configured"
            grep "encryptionpolicy" "$prefs_file"
        else
            echo "  Encryption Policy: Not configured"
        fi
        
        # Check signing preferences
        if grep -q "mail.identity.*sign_mail" "$prefs_file"; then
            echo "  Digital Signing: Configured"
            grep "sign_mail" "$prefs_file"
        else
            echo "  Digital Signing: Not configured"
        fi
        
        # Check certificate preferences
        if grep -q "mail.identity.*.*cert" "$prefs_file"; then
            echo "  Certificate Selection: Configured"
            grep "cert" "$prefs_file" | grep "mail.identity"
        else
            echo "  Certificate Selection: Not configured"
        fi
    fi
    
    echo -e "\n=== Configuration Recommendations ==="
    echo "1. Import personal S/MIME certificate: Settings > Privacy & Security > Certificates > Manage Certificates"
    echo "2. Configure account S/MIME: Account Settings > End-to-End Encryption"
    echo "3. Set encryption policy: Account Settings > End-to-End Encryption > S/MIME"
}

diagnose_thunderbird_smime
```

### 4. Email Gateway and Infrastructure Issues

#### Issue: Email Gateway Certificate Processing Errors
```bash
#!/bin/bash
# email_gateway_diagnostics.sh

diagnose_email_gateway() {
    echo "=== Email Gateway S/MIME Diagnostics ==="
    
    # Check gateway logs
    if [[ -f "/var/log/mail.log" ]]; then
        echo "Recent S/MIME processing errors:"
        tail -1000 /var/log/mail.log | grep -i -E "(smime|encrypt|decrypt|sign|verify)" | tail -20
    fi
    
    # Check Postfix TLS configuration
    if command -v postconf >/dev/null; then
        echo -e "\nPostfix TLS Configuration:"
        postconf | grep -E "(tls|smime)" | head -20
        
        echo -e "\nPostfix Certificate Configuration:"
        postconf | grep -E "(cert|key)" | head -10
    fi
    
    # Check certificate files
    echo -e "\nCertificate File Status:"
    for cert_file in /etc/ssl/certs/mail-server.pem /etc/ssl/private/mail-server.key; do
        if [[ -f "$cert_file" ]]; then
            echo "  $cert_file: Found"
            ls -la "$cert_file"
            
            # Check certificate validity
            if [[ "$cert_file" == *.pem ]]; then
                openssl x509 -in "$cert_file" -noout -dates 2>/dev/null || echo "    Certificate validation failed"
            fi
        else
            echo "  $cert_file: Missing"
        fi
    done
    
    # Check CA bundle
    ca_bundle="/etc/ssl/certs/ca-certificates.crt"
    if [[ -f "$ca_bundle" ]]; then
        echo -e "\nCA Bundle Status:"
        echo "  File: $ca_bundle"
        echo "  Size: $(wc -c < "$ca_bundle") bytes"
        echo "  Certificates: $(grep -c "BEGIN CERTIFICATE" "$ca_bundle")"
    fi
}

diagnose_email_gateway
```

### 5. Performance and Scalability Issues

#### Issue: Slow S/MIME Processing
```python
def diagnose_smime_performance():
    """
    Diagnose S/MIME performance issues
    """
    import time
    import subprocess
    import statistics
    
    def benchmark_smime_operations():
        """
        Benchmark S/MIME encryption/decryption performance
        """
        operations = ['encrypt', 'decrypt', 'sign', 'verify']
        results = {}
        
        for operation in operations:
            times = []
            
            for i in range(10):  # Run 10 iterations
                start_time = time.time()
                
                if operation == 'encrypt':
                    subprocess.run([
                        'openssl', 'smime', '-encrypt', '-in', '/dev/stdin',
                        '-out', '/tmp/test_encrypt.p7m', 'recipient_cert.pem'
                    ], input=b"test message", check=True)
                
                elif operation == 'decrypt':
                    subprocess.run([
                        'openssl', 'smime', '-decrypt', '-in', '/tmp/test_encrypt.p7m',
                        '-out', '/tmp/test_decrypt.txt', '-inkey', 'private_key.pem',
                        '-recip', 'recipient_cert.pem'
                    ], check=True)
                
                elif operation == 'sign':
                    subprocess.run([
                        'openssl', 'smime', '-sign', '-in', '/dev/stdin',
                        '-out', '/tmp/test_sign.p7m', '-signer', 'signer_cert.pem',
                        '-inkey', 'signer_key.pem'
                    ], input=b"test message", check=True)
                
                elif operation == 'verify':
                    subprocess.run([
                        'openssl', 'smime', '-verify', '-in', '/tmp/test_sign.p7m',
                        '-CAfile', 'ca_bundle.pem', '-out', '/tmp/verified.txt'
                    ], check=True)
                
                end_time = time.time()
                times.append((end_time - start_time) * 1000)  # Convert to milliseconds
            
            results[operation] = {
                'mean_ms': statistics.mean(times),
                'median_ms': statistics.median(times),
                'max_ms': max(times),
                'min_ms': min(times)
            }
        
        return results
    
    # Performance optimization recommendations
    optimization_recommendations = {
        'certificate_caching': 'Implement certificate caching to reduce LDAP lookups',
        'hardware_acceleration': 'Use hardware-accelerated cryptographic operations',
        'algorithm_selection': 'Prefer ECC over RSA for better performance',
        'concurrent_processing': 'Process multiple S/MIME operations in parallel',
        'certificate_validation_caching': 'Cache certificate validation results'
    }
    
    return {
        'benchmarks': benchmark_smime_operations(),
        'recommendations': optimization_recommendations
    }
```

## Advanced Troubleshooting Scenarios

### Scenario 1: Mass Certificate Deployment Issues
```bash
#!/bin/bash
# mass_certificate_deployment_troubleshooting.sh

troubleshoot_mass_deployment() {
    local deployment_log="$1"
    local user_list="$2"
    
    echo "=== Mass Certificate Deployment Troubleshooting ==="
    
    # Analyze deployment success/failure rates
    total_users=$(wc -l < "$user_list")
    successful_deployments=$(grep -c "SUCCESS" "$deployment_log")
    failed_deployments=$(grep -c "FAILED" "$deployment_log")
    
    echo "Deployment Statistics:"
    echo "  Total Users: $total_users"
    echo "  Successful: $successful_deployments"
    echo "  Failed: $failed_deployments"
    echo "  Success Rate: $(( successful_deployments * 100 / total_users ))%"
    
    # Categorize failure types
    echo -e "\nFailure Analysis:"
    grep "FAILED" "$deployment_log" | cut -d':' -f3 | sort | uniq -c | sort -nr
    
    # Generate remediation script
    cat > remediate_failed_deployments.sh << 'EOF'
#!/bin/bash
# Remediate failed certificate deployments

while IFS=':' read -r username email status reason; do
    if [[ "$status" == "FAILED" ]]; then
        case "$reason" in
            "LDAP_TIMEOUT")
                echo "Retrying LDAP operation for $username..."
                # Implement LDAP retry logic
                ;;
            "CERTIFICATE_GENERATION_FAILED")
                echo "Regenerating certificate for $username..."
                # Implement certificate regeneration
                ;;
            "EMAIL_DELIVERY_FAILED")
                echo "Resending certificate to $email..."
                # Implement email retry logic
                ;;
        esac
    fi
done < deployment_failures.log
EOF
    
    chmod +x remediate_failed_deployments.sh
    echo "Remediation script generated: remediate_failed_deployments.sh"
}
```

### Scenario 2: Certificate Authority Integration Issues
```python
def troubleshoot_ca_integration():
    """
    Troubleshoot certificate authority integration issues
    """
    diagnostic_tests = {
        'ca_connectivity': {
            'test': 'curl -I https://ca.company.com/certsrv/',
            'expected': 'HTTP/1.1 200 OK',
            'issues': ['Network connectivity', 'CA service down', 'DNS resolution']
        },
        'ca_authentication': {
            'test': 'Test CA admin credentials',
            'issues': ['Expired credentials', 'Account locked', 'Permission changes']
        },
        'certificate_template_availability': {
            'test': 'Query available certificate templates',
            'issues': ['Template deleted', 'Permission denied', 'Template misconfiguration']
        },
        'ca_database_connectivity': {
            'test': 'Test CA database connection',
            'issues': ['Database offline', 'Connection timeout', 'Authentication failure']
        }
    }
    
    return diagnostic_tests

def automated_ca_health_check():
    """
    Automated CA health check script
    """
    health_check_script = """
#!/bin/bash
# ca_health_check.sh

check_ca_service() {
    local ca_url="$1"
    
    # Test HTTP connectivity
    if curl -s -I "$ca_url" | grep -q "200 OK"; then
        echo "CA Service: HEALTHY"
        return 0
    else
        echo "CA Service: UNHEALTHY"
        return 1
    fi
}

check_certificate_issuance() {
    local test_csr="$1"
    
    # Submit test certificate request
    response=$(curl -s -X POST "$CA_URL/certreq" -d @"$test_csr")
    
    if echo "$response" | grep -q "certificate issued"; then
        echo "Certificate Issuance: WORKING"
        return 0
    else
        echo "Certificate Issuance: FAILED"
        echo "Error: $response"
        return 1
    fi
}

check_crl_access() {
    local crl_url="$1"
    
    # Download and validate CRL
    if curl -s "$crl_url" | openssl crl -inform DER -noout 2>/dev/null; then
        echo "CRL Access: WORKING"
        return 0
    else
        echo "CRL Access: FAILED"
        return 1
    fi
}

# Main health check
echo "=== CA Health Check ==="
check_ca_service "$CA_URL"
check_certificate_issuance "$TEST_CSR"
check_crl_access "$CRL_URL"
"""
    
    return health_check_script
```

## Emergency Response Procedures

### Critical Issue: Suspected Certificate Compromise
```bash
#!/bin/bash
# emergency_certificate_compromise_response.sh

handle_certificate_compromise() {
    local compromised_cert="$1"
    local incident_id="$2"
    
    echo "=== EMERGENCY: Certificate Compromise Response ==="
    echo "Incident ID: $incident_id"
    echo "Compromised Certificate: $compromised_cert"
    echo "Timestamp: $(date)"
    
    # Immediate containment
    echo "Step 1: Immediate Certificate Revocation"
    openssl ca -revoke "$compromised_cert" -config /etc/ssl/openssl.cnf
    
    echo "Step 2: Update CRL"
    openssl ca -gencrl -out /etc/ssl/crl/emergency-$(date +%Y%m%d-%H%M).crl \
        -config /etc/ssl/openssl.cnf
    
    echo "Step 3: Block Certificate in Email Gateway"
    # Add certificate serial to blocked list
    cert_serial=$(openssl x509 -in "$compromised_cert" -noout -serial | cut -d'=' -f2)
    echo "$cert_serial" >> /etc/mail/blocked_certificates.txt
    
    echo "Step 4: Notify Security Team"
    # Send emergency notification
    echo "Certificate compromise detected. Serial: $cert_serial" | \
        mail -s "URGENT: Certificate Compromise - $incident_id" security@company.com
    
    echo "Step 5: Forensic Evidence Collection"
    # Collect logs and system state
    mkdir -p "/var/log/security/compromise-$incident_id"
    cp "$compromised_cert" "/var/log/security/compromise-$incident_id/"
    grep "$cert_serial" /var/log/mail.log > "/var/log/security/compromise-$incident_id/mail_usage.log"
    
    echo "=== Emergency Response Complete ==="
    echo "Next steps: Full forensic analysis and user notification"
}

# Usage: handle_certificate_compromise "/path/to/compromised.pem" "INC-2024-001"
```

This comprehensive troubleshooting guide provides systematic approaches to diagnosing and resolving email security issues across all components of a PKI-based email security infrastructure.