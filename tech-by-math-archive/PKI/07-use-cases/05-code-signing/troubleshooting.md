# Code Signing Troubleshooting Guide

## Overview

This troubleshooting guide addresses common issues in code signing implementations using PKI certificates. Issues are systematically categorized with diagnostic procedures and resolution strategies for enterprise software development environments.

## Diagnostic Framework

### Issue Classification System
```python
def classify_code_signing_issue(symptoms, error_messages, platform):
    """
    Systematically classify code signing issues for targeted troubleshooting
    """
    issue_patterns = {
        "certificate_issues": [
            "certificate not found",
            "private key not accessible",
            "certificate expired",
            "certificate revoked"
        ],
        "signing_failures": [
            "signing failed",
            "invalid signature",
            "timestamp failed",
            "hash mismatch"
        ],
        "platform_specific": [
            "authenticode error",
            "codesign failed",
            "jarsigner error",
            "gpg signing failed"
        ],
        "hsm_issues": [
            "hsm not found",
            "pkcs11 error",
            "token not present",
            "pin incorrect"
        ]
    }
    
    detected_issues = []
    for category, patterns in issue_patterns.items():
        for pattern in patterns:
            if any(pattern.lower() in msg.lower() for msg in error_messages):
                detected_issues.append({
                    "category": category,
                    "pattern": pattern,
                    "platform": platform
                })
    
    return detected_issues
```

## Common Issues and Solutions

### 1. Certificate and Key Issues

#### Issue: Certificate Not Found
```bash
# Diagnostic commands for Windows
certlm.msc  # Check certificate store
Get-ChildItem Cert:\CurrentUser\My | Where-Object {$_.Subject -match "Code"}

# Diagnostic commands for Linux/macOS
openssl x509 -in certificate.pem -text -noout
ls -la ~/.ssl/certificates/

# Solution: Install certificate properly
# Windows
Import-PfxCertificate -FilePath codesign.pfx -CertStoreLocation Cert:\CurrentUser\My

# Linux/macOS
cp certificate.pem ~/.ssl/certificates/
chmod 600 ~/.ssl/certificates/certificate.pem
```

#### Issue: Private Key Access Problems
```bash
# Check key permissions
ls -la /path/to/private.key
# Should show restricted permissions (600)

# HSM key access test
/usr/safenet/lunaclient/bin/cmu list
pkcs11-tool --list-objects --type privkey

# Solution: Fix permissions and HSM connectivity
chmod 600 private.key
# For HSM: verify partition access and PIN
```

### 2. Platform-Specific Signing Issues

#### Windows Authenticode Problems
```batch
REM Test signtool functionality
signtool verify /pa /v signed_file.exe
signtool sign /debug /v /fd SHA256 /tr http://timestamp.url file.exe

REM Common solutions:
REM 1. Update signtool version
REM 2. Check certificate store location
REM 3. Verify timestamp authority accessibility
```

#### macOS Code Signing Issues
```bash
# Diagnostic commands
security find-identity -v -p codesigning
codesign --verify --verbose=4 MyApp.app
spctl --assess --verbose MyApp.app

# Common solutions
# 1. Re-sign with proper identity
codesign --force --sign "Developer ID" --timestamp MyApp.app

# 2. Check keychain access
security list-keychains
security unlock-keychain login.keychain
```

#### Java JAR Signing Problems
```bash
# Verify JAR signature
jarsigner -verify -verbose application.jar

# Re-sign with proper configuration
jarsigner -digestalg SHA-256 -sigalg SHA256withRSA \
    -keystore keystore.p12 -storetype PKCS12 \
    application.jar mykey

# Check for timestamp issues
jarsigner -verify -verbose -certs application.jar | grep -i timestamp
```

### 3. HSM Integration Issues

#### HSM Connectivity Problems
```bash
#!/bin/bash
# hsm_diagnostic_script.sh

echo "=== HSM Diagnostics ==="

# Check HSM connectivity
if command -v /usr/safenet/lunaclient/bin/lunacm >/dev/null; then
    echo "Luna HSM Status:"
    /usr/safenet/lunaclient/bin/lunacm -s
fi

# Check PKCS#11 configuration
if [[ -f /usr/lib/libpkcs11.so ]]; then
    echo "PKCS#11 Library: Found"
    pkcs11-tool --list-slots
else
    echo "ERROR: PKCS#11 library not found"
fi

# Test key access
pkcs11-tool --list-objects --type privkey
```

### 4. Build System Integration Issues

#### CI/CD Pipeline Failures
```yaml
# GitHub Actions troubleshooting
- name: Debug Code Signing
  run: |
    echo "Checking certificate availability..."
    Get-ChildItem Cert:\CurrentUser\My
    
    echo "Testing signtool..."
    signtool.exe sign /fd SHA256 /debug test.exe
    
    echo "Checking timestamp connectivity..."
    Test-NetConnection -ComputerName timestamp.company.com -Port 80
```

#### Jenkins Pipeline Issues
```groovy
// Add debugging to Jenkins pipeline
stage('Debug Signing Environment') {
    steps {
        script {
            if (isUnix()) {
                sh 'openssl version'
                sh 'ls -la ~/.ssl/certificates/'
            } else {
                bat 'signtool /?'
                bat 'certlm.msc /s'
            }
        }
    }
}
```

### 5. Timestamp Authority Issues

#### TSA Connectivity Problems
```bash
# Test timestamp authority connectivity
curl -I http://timestamp.authority.com
openssl ts -query -data test.txt -out test.tsq
curl -H "Content-Type: application/timestamp-query" \
     --data-binary @test.tsq \
     http://timestamp.authority.com/tsa

# Verify timestamp response
openssl ts -reply -in test.tsr -text
```

## Performance Troubleshooting

### Slow Signing Operations
```python
def benchmark_signing_performance():
    """
    Benchmark code signing performance
    """
    import time
    import subprocess
    
    test_file = "test_binary.exe"
    iterations = 10
    times = []
    
    for i in range(iterations):
        start = time.time()
        subprocess.run(['signtool', 'sign', '/fd', 'SHA256', test_file], 
                      capture_output=True)
        end = time.time()
        times.append(end - start)
    
    avg_time = sum(times) / len(times)
    print(f"Average signing time: {avg_time:.2f} seconds")
    
    if avg_time > 30:
        print("WARNING: Signing performance is slow")
        print("Recommendations:")
        print("- Check HSM connectivity")
        print("- Verify timestamp authority response time")
        print("- Consider local TSA deployment")
    
    return times
```

## Emergency Response Procedures

### Certificate Compromise Response
```bash
#!/bin/bash
# emergency_codesign_response.sh

emergency_response() {
    local cert_serial="$1"
    local incident_id="$2"
    
    echo "=== EMERGENCY: Code Signing Certificate Compromise ==="
    echo "Certificate Serial: $cert_serial"
    echo "Incident ID: $incident_id"
    
    # Immediate revocation
    openssl ca -revoke cert.pem -config ca.cnf
    
    # Update CRL
    openssl ca -gencrl -out emergency.crl -config ca.cnf
    
    # Block in build systems
    echo "$cert_serial" >> /etc/security/blocked_certs.txt
    
    # Notify security team
    echo "Certificate compromise: $cert_serial" | \
        mail -s "URGENT: Code Sign Cert Compromise" security@company.com
}
```

### Build System Incident Response
```bash
# Isolate compromised build system
iptables -A INPUT -j DROP
iptables -A OUTPUT -j DROP

# Preserve forensic evidence
mkdir -p /forensics/incident-$(date +%Y%m%d-%H%M)
cp /var/log/build.log /forensics/incident-$(date +%Y%m%d-%H%M)/
find /opt/build -name "*.signed" -exec cp {} /forensics/incident-$(date +%Y%m%d-%H%M)/ \;

# Rebuild from clean state
rm -rf /opt/build/*
git clone --depth 1 https://repo.company.com/project.git /opt/build/
```

This troubleshooting guide provides systematic approaches to diagnosing and resolving code signing issues across platforms and infrastructure components.