# Code Signing Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying code signing infrastructure using PKI certificates for software integrity and authenticity verification. It covers the technical implementation details, configuration requirements, and operational procedures necessary for enterprise-grade code signing systems.

## Prerequisites

### Software Requirements
- OpenSSL 3.0+ (cryptographic operations)
- Code signing tools (signtool.exe, jarsigner, codesign, gpg)
- Certificate Authority infrastructure (internal or external)
- Build automation systems (Jenkins, GitHub Actions, Azure DevOps)
- Hardware Security Modules (HSMs) for key protection
- Timestamp authorities for time-stamped signatures

### Knowledge Requirements
- Software development and build processes
- PKI certificate management
- Code signing standards and formats
- Digital signature algorithms and protocols
- Software distribution and deployment methods

### Hardware Requirements
- Secure key storage (HSM, TPM, or encrypted storage)
- Build server infrastructure
- Certificate management systems
- Backup and recovery infrastructure
- Network security controls

## Pre-Deployment Planning

### Code Signing Architecture
```python
def plan_code_signing_architecture(organization_type, security_level, volume):
    """
    Plan code signing architecture based on organizational requirements
    """
    architectures = {
        "startup_basic": {
            "ca_type": "external_ca",
            "key_storage": "software_protected",
            "signing_automation": "manual",
            "timestamping": "public_tsa"
        },
        "enterprise_standard": {
            "ca_type": "internal_ca",
            "key_storage": "network_hsm",
            "signing_automation": "ci_cd_integrated",
            "timestamping": "internal_tsa",
            "key_escrow": True
        },
        "enterprise_high_volume": {
            "ca_type": "hierarchical_ca",
            "key_storage": "dedicated_hsm",
            "signing_automation": "fully_automated",
            "timestamping": "redundant_tsa",
            "key_escrow": True,
            "load_balancing": True
        }
    }
    
    key = f"{organization_type}_{security_level}"
    if volume == "high":
        key += "_high_volume"
    
    return architectures.get(key, architectures["enterprise_standard"])
```

### Certificate Template Design
```bash
# Code signing certificate template configuration
CODE_SIGNING_TEMPLATE='{
    "template_name": "CodeSigning",
    "validity_period": "3_years",
    "key_usage": ["digitalSignature"],
    "extended_key_usage": ["codeSigning"],
    "key_algorithm": "RSA_3072",
    "subject_requirements": {
        "organization_validation": true,
        "extended_validation": false
    },
    "key_protection": "hsm_required",
    "auto_enrollment": false
}'

# Timestamp authority template
TIMESTAMP_TEMPLATE='{
    "template_name": "TimeStamping",
    "validity_period": "5_years", 
    "key_usage": ["digitalSignature"],
    "extended_key_usage": ["timeStamping"],
    "key_algorithm": "RSA_2048",
    "critical_extensions": true
}'
```

### Supported Code Signing Formats
```bash
# Define supported code signing formats and tools
WINDOWS_EXECUTABLES="signtool.exe - Authenticode signatures for .exe, .dll, .msi"
JAVA_APPLICATIONS="jarsigner - JAR file signatures"
APPLE_APPLICATIONS="codesign - macOS and iOS application signatures"  
LINUX_PACKAGES="gpg/dpkg-sig - Debian package signatures"
CONTAINER_IMAGES="cosign/notary - Container image signatures"
POWERSHELL_SCRIPTS="Set-AuthenticodeSignature - PowerShell script signatures"
```

## Step-by-Step Deployment

### Step 1: Certificate Authority Setup

#### 1.1 Code Signing CA Configuration
```bash
# Create code signing CA infrastructure
mkdir -p /opt/codesign-ca/{root,intermediate,certs,crl,private,csr}
chmod 700 /opt/codesign-ca/private

# Generate code signing root CA
openssl genrsa -aes256 -out /opt/codesign-ca/private/codesign-root-ca.key 4096

# Create root CA certificate
openssl req -new -x509 -days 7300 -key /opt/codesign-ca/private/codesign-root-ca.key \
    -out /opt/codesign-ca/certs/codesign-root-ca.pem \
    -config /opt/codesign-ca/openssl-root.cnf \
    -extensions v3_ca

# Create intermediate CA for code signing
openssl genrsa -aes256 -out /opt/codesign-ca/private/codesign-intermediate-ca.key 4096
openssl req -new -key /opt/codesign-ca/private/codesign-intermediate-ca.key \
    -out /opt/codesign-ca/csr/codesign-intermediate-ca.csr \
    -config /opt/codesign-ca/openssl-intermediate.cnf

# Sign intermediate CA certificate
openssl ca -in /opt/codesign-ca/csr/codesign-intermediate-ca.csr \
    -out /opt/codesign-ca/certs/codesign-intermediate-ca.pem \
    -config /opt/codesign-ca/openssl-root.cnf \
    -extensions v3_intermediate_ca -days 3650
```

#### 1.2 Certificate Template Configuration (Windows CA)
```powershell
# Configure code signing certificate template on Windows CA
Import-Module ADCSAdministration

# Create code signing certificate template
$template = @{
    Name = "EnterpriseCodeSigning"
    DisplayName = "Enterprise Code Signing Certificate"
    ValidityPeriod = "Years"
    ValidityPeriodUnits = 3
    KeyUsage = @("DigitalSignature")
    ApplicationPolicies = @("Code Signing")
    SubjectNameFormat = "FullDistinguishedName"
    SubjectRequireCommonName = $true
    KeyMinimumSize = 3072
    KeySpecification = "KeyExchange"
    HashAlgorithm = "SHA256"
    AutoEnrollment = $false
    RequireApproval = $true
}

New-CATemplate @template

# Create timestamp certificate template  
$tsTemplate = @{
    Name = "TimeStampingService"
    DisplayName = "Time Stamping Service Certificate"
    ValidityPeriod = "Years"
    ValidityPeriodUnits = 5
    KeyUsage = @("DigitalSignature")
    ApplicationPolicies = @("Time Stamping")
    SubjectNameFormat = "CommonName"
    KeyMinimumSize = 2048
    CriticalExtensions = $true
}

New-CATemplate @tsTemplate
```

### Step 2: Hardware Security Module Integration

#### 2.1 HSM Configuration for Code Signing
```bash
# Configure HSM for code signing key storage
# Example using SafeNet Luna HSM

# Initialize HSM partition
/usr/safenet/lunaclient/bin/lunacm -s slot=0 -i partition=codesigning

# Generate code signing key in HSM
cat > generate_codesign_key.sh << 'EOF'
#!/bin/bash
# Generate RSA key pair in HSM for code signing

/usr/safenet/lunaclient/bin/cmu generatekeypair -keyType=RSA \
    -keySize=3072 \
    -publicKeyTemplate=codesign_pub.template \
    -privateKeyTemplate=codesign_priv.template \
    -keyLabel="CodeSigning-$(date +%Y%m%d)"

# Export public key for certificate generation
/usr/safenet/lunaclient/bin/cmu exportkey -keyLabel="CodeSigning-$(date +%Y%m%d)" \
    -outputFile=codesign_public.key
EOF

chmod +x generate_codesign_key.sh
./generate_codesign_key.sh
```

#### 2.2 HSM Integration with Signing Tools
```bash
# Configure signing tools to use HSM
# Windows - signtool configuration
cat > signtool_hsm.conf << 'EOF'
# signtool HSM configuration
CERTIFICATE_STORE=MY
HSM_PROVIDER="SafeNet Key Storage Provider"
HSM_CONTAINER="CodeSigning-20241225"
TIMESTAMP_URL="http://timestamp.company.com"
HASH_ALGORITHM=SHA256
EOF

# Java - configure HSM provider
cat > java_hsm.conf << 'EOF'
# Java HSM configuration for jarsigner
name=LunaProvider
library=/usr/lib/libCryptoki2_64.so
slot=0
showInfo=true
EOF

# Configure PKCS#11 provider
echo "security.provider.10=SunPKCS11 java_hsm.conf" >> $JAVA_HOME/jre/lib/security/java.security
```

### Step 3: Timestamp Authority Setup

#### 3.1 Internal Timestamp Authority
```bash
# Setup internal timestamp authority
mkdir -p /opt/tsa/{config,certs,private,logs}

# Generate TSA certificate
openssl genrsa -out /opt/tsa/private/tsa.key 2048
openssl req -new -key /opt/tsa/private/tsa.key -out /opt/tsa/tsa.csr \
    -config /opt/tsa/openssl-tsa.cnf

# Configure TSA service
cat > /opt/tsa/config/tsa.conf << 'EOF'
# TSA Configuration
default_tsa = tsa_config1

[tsa_config1]
dir = /opt/tsa
serial = $dir/tsa_serial.txt
signer_cert = $dir/certs/tsa.pem
private_key = $dir/private/tsa.key
default_policy = tsa_policy1
other_policies = tsa_policy2, tsa_policy3
digests = sha256, sha512
accuracy = secs:1, millisecs:500, microsecs:100
ordering = yes
tsa_name = yes
ess_cert_id_chain = no

[tsa_policy1]
policyIdentifier = 1.2.3.4.1
EOF

# Create TSA service script
cat > /opt/tsa/tsa_service.py << 'EOF'
#!/usr/bin/env python3
"""
Simple HTTP Timestamp Authority Service
"""
import http.server
import subprocess
import tempfile
import os

class TSAHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/tsa':
            content_length = int(self.headers['Content-Length'])
            tsa_request = self.rfile.read(content_length)
            
            # Process TSA request using OpenSSL
            with tempfile.NamedTemporaryFile() as req_file, \
                 tempfile.NamedTemporaryFile() as resp_file:
                
                req_file.write(tsa_request)
                req_file.flush()
                
                # Generate timestamp response
                subprocess.run([
                    'openssl', 'ts', '-reply',
                    '-config', '/opt/tsa/config/tsa.conf',
                    '-section', 'tsa_config1',
                    '-queryfile', req_file.name,
                    '-out', resp_file.name
                ])
                
                # Send response
                resp_file.seek(0)
                tsa_response = resp_file.read()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/timestamp-reply')
                self.send_header('Content-Length', str(len(tsa_response)))
                self.end_headers()
                self.wfile.write(tsa_response)

if __name__ == '__main__':
    server = http.server.HTTPServer(('0.0.0.0', 8080), TSAHandler)
    server.serve_forever()
EOF

chmod +x /opt/tsa/tsa_service.py
```

### Step 4: Build System Integration

#### 4.1 Jenkins Integration
```groovy
// Jenkins pipeline for automated code signing
pipeline {
    agent any
    
    environment {
        SIGNING_CERT_ID = 'code-signing-cert'
        HSM_PIN = credentials('hsm-pin')
        TIMESTAMP_URL = 'http://timestamp.company.com:8080/tsa'
    }
    
    stages {
        stage('Build') {
            steps {
                // Build application
                sh 'make build'
            }
        }
        
        stage('Sign Code') {
            steps {
                script {
                    // Sign Windows executables
                    if (isUnix() == false) {
                        bat """
                            signtool sign /fd SHA256 /tr "${TIMESTAMP_URL}" /td SHA256 \
                                /a /n "Company Code Signing Certificate" \
                                dist/*.exe dist/*.dll
                        """
                    }
                    
                    // Sign JAR files
                    sh """
                        jarsigner -digestalg SHA-256 -sigalg SHA256withRSA \
                            -tsa "${TIMESTAMP_URL}" \
                            -keystore "NONE" -storetype PKCS11 \
                            -providerClass sun.security.pkcs11.SunPKCS11 \
                            -providerArg java_hsm.conf \
                            dist/*.jar "CodeSigning-\$(date +%Y%m%d)"
                    """
                }
            }
        }
        
        stage('Verify Signatures') {
            steps {
                // Verify code signatures
                script {
                    sh '''
                        for file in dist/*; do
                            echo "Verifying signature for $file"
                            if [[ "$file" == *.exe ]] || [[ "$file" == *.dll ]]; then
                                signtool verify /pa /v "$file"
                            elif [[ "$file" == *.jar ]]; then
                                jarsigner -verify -verbose "$file"
                            fi
                        done
                    '''
                }
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'dist/*', fingerprint: true
        }
    }
}
```

#### 4.2 GitHub Actions Integration
```yaml
# .github/workflows/code-signing.yml
name: Code Signing Workflow

on:
  push:
    branches: [main, release/*]
  pull_request:
    branches: [main]

jobs:
  build-and-sign:
    runs-on: [self-hosted, windows]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Build Environment
      run: |
        # Setup build tools
        choco install visualstudio2019buildtools
    
    - name: Build Application
      run: |
        msbuild MyApplication.sln /p:Configuration=Release
    
    - name: Import Code Signing Certificate
      env:
        CERT_PASSWORD: ${{ secrets.CERT_PASSWORD }}
      run: |
        # Import certificate from secure storage
        Import-PfxCertificate -FilePath cert/codesign.pfx -CertStoreLocation Cert:\CurrentUser\My -Password (ConvertTo-SecureString -String $env:CERT_PASSWORD -AsPlainText -Force)
    
    - name: Sign Executables
      env:
        TIMESTAMP_URL: ${{ secrets.TIMESTAMP_URL }}
      run: |
        Get-ChildItem -Path "bin/Release" -Filter "*.exe" | ForEach-Object {
            signtool sign /fd SHA256 /tr $env:TIMESTAMP_URL /td SHA256 /a $_.FullName
        }
    
    - name: Verify Signatures
      run: |
        Get-ChildItem -Path "bin/Release" -Filter "*.exe" | ForEach-Object {
            signtool verify /pa /v $_.FullName
        }
    
    - name: Upload Signed Artifacts
      uses: actions/upload-artifact@v3
      with:
        name: signed-binaries
        path: bin/Release/*.exe
```

### Step 5: Platform-Specific Signing Configuration

#### 5.1 Windows Authenticode Signing
```batch
REM Windows code signing script
@echo off
setlocal

set CERT_NAME="Company Code Signing Certificate"
set TIMESTAMP_URL=http://timestamp.company.com:8080/tsa
set HASH_ALG=SHA256

REM Sign executable files
for %%f in (dist\*.exe dist\*.dll dist\*.msi) do (
    echo Signing %%f
    signtool sign /fd %HASH_ALG% /tr %TIMESTAMP_URL% /td %HASH_ALG% /a /n %CERT_NAME% "%%f"
    
    REM Verify signature
    signtool verify /pa /v "%%f"
    if errorlevel 1 (
        echo ERROR: Signature verification failed for %%f
        exit /b 1
    )
)

echo All files signed successfully
```

#### 5.2 macOS Code Signing
```bash
#!/bin/bash
# macOS code signing script

DEVELOPER_ID="Developer ID Application: Company Name"
TIMESTAMP_URL="http://timestamp.apple.com/ts01"
BUNDLE_PATH="dist/MyApp.app"

# Sign the application bundle
echo "Signing macOS application..."
codesign --force --verify --verbose --sign "$DEVELOPER_ID" \
    --options runtime \
    --timestamp "$BUNDLE_PATH"

# Verify signature
echo "Verifying signature..."
codesign --verify --verbose=2 "$BUNDLE_PATH"
spctl --assess --verbose "$BUNDLE_PATH"

# Create disk image and sign it
echo "Creating and signing disk image..."
hdiutil create -srcfolder "$BUNDLE_PATH" -volname "MyApp" "dist/MyApp.dmg"
codesign --force --sign "$DEVELOPER_ID" "dist/MyApp.dmg"

echo "macOS signing complete"
```

#### 5.3 Linux Package Signing
```bash
#!/bin/bash
# Linux package signing script

GPG_KEY_ID="company@example.com"
PACKAGE_DIR="dist"

# Sign Debian packages
for deb in $PACKAGE_DIR/*.deb; do
    echo "Signing $deb"
    dpkg-sig --sign builder -k "$GPG_KEY_ID" "$deb"
    
    # Verify signature
    dpkg-sig --verify "$deb"
done

# Sign RPM packages
for rpm in $PACKAGE_DIR/*.rpm; do
    echo "Signing $rpm"
    rpm --addsign "$rpm"
    
    # Verify signature
    rpm --checksig "$rpm"
done

# Create repository metadata with signatures
echo "Creating signed repository metadata..."
cd $PACKAGE_DIR

# For Debian repository
dpkg-scanpackages . /dev/null | gzip -9c > Packages.gz
apt-ftparchive release . > Release
gpg --clearsign -o InRelease Release
gpg -abs -o Release.gpg Release

# For RPM repository
createrepo .
gpg --detach-sign --armor repodata/repomd.xml

echo "Package signing complete"
```

## Post-Deployment Configuration

### Certificate Management and Monitoring
```bash
# Automated certificate monitoring script
#!/bin/bash
# monitor_codesign_certs.sh

CERT_STORE="/opt/codesign-ca/certs"
HSM_PARTITION="codesigning"
THRESHOLD_DAYS=60

monitor_certificate_expiration() {
    echo "=== Code Signing Certificate Monitoring ==="
    echo "Date: $(date)"
    
    # Check file-based certificates
    for cert in $CERT_STORE/*.pem; do
        if [[ -f "$cert" ]]; then
            echo "Checking certificate: $cert"
            expiry_date=$(openssl x509 -in "$cert" -noout -enddate | cut -d= -f2)
            days_left=$(( ($(date -d "$expiry_date" +%s) - $(date +%s)) / 86400 ))
            
            if [[ $days_left -lt $THRESHOLD_DAYS ]]; then
                echo "WARNING: Certificate $cert expires in $days_left days"
                # Send alert
                echo "Certificate expiring soon: $cert ($days_left days)" | \
                    mail -s "Code Signing Certificate Expiration Warning" security@company.com
            fi
        fi
    done
    
    # Check HSM-stored certificates
    if command -v /usr/safenet/lunaclient/bin/cmu >/dev/null; then
        echo "Checking HSM certificates..."
        /usr/safenet/lunaclient/bin/cmu list | while read -r key_info; do
            if [[ "$key_info" =~ "CodeSigning" ]]; then
                echo "HSM Key found: $key_info"
                # Additional HSM certificate checks
            fi
        done
    fi
}

# Run monitoring
monitor_certificate_expiration

# Log results
echo "Certificate monitoring completed at $(date)" >> /var/log/codesign_monitor.log
```

### Backup and Recovery Procedures
```bash
# Code signing infrastructure backup script
#!/bin/bash
# backup_codesign_infrastructure.sh

BACKUP_DIR="/backup/codesign/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

echo "=== Code Signing Infrastructure Backup ==="

# Backup CA certificates and CRL
echo "Backing up CA infrastructure..."
cp -r /opt/codesign-ca/certs "$BACKUP_DIR/"
cp -r /opt/codesign-ca/crl "$BACKUP_DIR/"
cp /opt/codesign-ca/index.txt* "$BACKUP_DIR/"
cp /opt/codesign-ca/serial* "$BACKUP_DIR/"

# Backup HSM configuration (not keys - they stay in HSM)
echo "Backing up HSM configuration..."
if [[ -f /usr/safenet/lunaclient/bin/vtl ]] ; then
    /usr/safenet/lunaclient/bin/vtl backup -file "$BACKUP_DIR/hsm_backup.tar"
fi

# Backup timestamp authority configuration
echo "Backing up TSA configuration..."
cp -r /opt/tsa/config "$BACKUP_DIR/"
cp -r /opt/tsa/certs "$BACKUP_DIR/"

# Backup signing scripts and CI/CD configurations
echo "Backing up signing configurations..."
cp -r /opt/signing-scripts "$BACKUP_DIR/"

# Create encrypted archive
echo "Creating encrypted backup archive..."
tar czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
gpg --encrypt --recipient backup@company.com "$BACKUP_DIR.tar.gz"

# Clean up temporary files
rm -rf "$BACKUP_DIR"
rm "$BACKUP_DIR.tar.gz"

echo "Backup complete: $BACKUP_DIR.tar.gz.gpg"
```

This deployment guide ensures comprehensive code signing infrastructure through proper PKI implementation, HSM integration, and automated build system integration for enterprise software development environments.