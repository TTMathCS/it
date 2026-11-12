# Personal Certificates Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying personal certificate infrastructure for individual users. It covers the technical implementation details, configuration requirements, and operational procedures necessary for secure personal certificate management.

## Prerequisites

### Software Requirements
- OpenSSL 3.0+ (cryptographic operations)
- Email client supporting S/MIME (Thunderbird, Outlook)
- Web browser with certificate management (Firefox, Chrome, Edge)
- Certificate management tools (certlm.msc on Windows, Keychain on macOS)

### Knowledge Requirements
- Basic understanding of public key cryptography
- Command line operations
- Email client configuration
- Browser security settings

### Hardware Requirements
- Secure storage for private keys (recommended: TPM, HSM, or encrypted storage)
- Backup storage solution
- Network connectivity for certificate authority interactions

## Pre-Deployment Planning

### Identity Verification Strategy
```python
def plan_identity_verification(user_type, risk_level):
    """
    Plan identity verification approach based on user profile
    """
    verification_methods = {
        "individual_low": {
            "email_verification": True,
            "phone_verification": False,
            "document_verification": False,
            "in_person_verification": False
        },
        "individual_medium": {
            "email_verification": True,
            "phone_verification": True,
            "document_verification": True,
            "in_person_verification": False
        },
        "professional_high": {
            "email_verification": True,
            "phone_verification": True,
            "document_verification": True,
            "in_person_verification": True
        }
    }
    
    return verification_methods.get(f"{user_type}_{risk_level}", {})
```

### Certificate Authority Selection
1. **Public CAs**: DigiCert, Let's Encrypt, GlobalSign
2. **Private CAs**: Internal organizational CAs
3. **Self-signed**: Development and testing environments only

### Key Algorithm Selection
```bash
# Recommended algorithms by use case
EMAIL_SIGNING="EC prime256v1"        # S/MIME email signatures
WEB_CLIENT="EC prime256v1"           # Client authentication
CODE_SIGNING="RSA 3072"              # Software signing (longer validity)
DOCUMENT_SIGNING="RSA 3072"          # Legal document signatures
```

## Step-by-Step Deployment

### Step 1: Environment Preparation

#### 1.1 Create Secure Directory Structure
```bash
# Create certificate management directory
mkdir -p ~/.pki/{private,certs,csr,backup}
chmod 700 ~/.pki/private
chmod 755 ~/.pki/{certs,csr,backup}

# Set up OpenSSL configuration
cat > ~/.pki/openssl.cnf << 'EOF'
[ req ]
default_bits = 2048
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[ req_distinguished_name ]
CN = Alice Thompson
emailAddress = alice@example.com
O = Freelance Developer
C = US

[ v3_req ]
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = emailProtection, clientAuth
subjectAltName = @alt_names

[ alt_names ]
email.1 = alice@example.com
EOF
```

#### 1.2 Generate Master Key Pair
```bash
# Generate EC private key for maximum efficiency
openssl ecparam -genkey -name prime256v1 \
    -out ~/.pki/private/alice_master.key

# Secure private key permissions
chmod 400 ~/.pki/private/alice_master.key

# Generate corresponding public key
openssl ec -in ~/.pki/private/alice_master.key \
    -pubout -out ~/.pki/certs/alice_master_public.pem
```

**Mathematical Foundation**: The private key `d` is generated from a cryptographically secure random number generator within the range `[1, n-1]` where `n` is the order of the elliptic curve group. The public key `Q = d × G` is computed through elliptic curve point multiplication.

### Step 2: Certificate Enrollment Process

#### 2.1 Generate Certificate Signing Request
```bash
# Create CSR for email certificate
openssl req -new -key ~/.pki/private/alice_master.key \
    -config ~/.pki/openssl.cnf \
    -out ~/.pki/csr/alice_email.csr

# Verify CSR content
openssl req -text -noout -verify -in ~/.pki/csr/alice_email.csr
```

#### 2.2 Submit to Certificate Authority
```bash
# Example API submission (replace with actual CA endpoint)
curl -X POST https://api.ca.example.com/v1/certificates \
    -H "Content-Type: application/pkcs10" \
    -H "Authorization: Bearer YOUR_API_TOKEN" \
    --data-binary @~/.pki/csr/alice_email.csr
```

#### 2.3 Certificate Retrieval and Validation
```bash
# Download issued certificate
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
    https://api.ca.example.com/v1/certificates/12345 \
    -o ~/.pki/certs/alice_email.pem

# Download CA certificate chain
curl https://ca.example.com/certs/chain.pem \
    -o ~/.pki/certs/ca_chain.pem

# Verify certificate chain
openssl verify -CAfile ~/.pki/certs/ca_chain.pem \
    ~/.pki/certs/alice_email.pem
```

### Step 3: Client Application Integration

#### 3.1 Email Client Configuration (Thunderbird)
```bash
# Create PKCS#12 bundle for email client
openssl pkcs12 -export \
    -out ~/.pki/certs/alice_email.p12 \
    -inkey ~/.pki/private/alice_master.key \
    -in ~/.pki/certs/alice_email.pem \
    -certfile ~/.pki/certs/ca_chain.pem \
    -name "Alice Thompson Email Certificate"

# Thunderbird import steps:
# 1. Preferences → Privacy & Security
# 2. Certificates → Manage Certificates
# 3. Your Certificates → Import → Select alice_email.p12
```

#### 3.2 Browser Configuration (Firefox)
```bash
# Firefox certificate import:
# 1. Settings → Privacy & Security
# 2. Certificates → View Certificates
# 3. Your Certificates → Import → Select alice_email.p12
# 4. Enable for Client Authentication
```

#### 3.3 System Keystore Integration

**Windows:**
```powershell
# Import to Windows Certificate Store
certutil -user -p "password" -importpfx alice_email.p12
```

**macOS:**
```bash
# Import to macOS Keychain
security import alice_email.p12 -k ~/Library/Keychains/login.keychain-db
```

**Linux:**
```bash
# Install in NSS database (used by Firefox/Chrome)
pk12util -i alice_email.p12 -d ~/.mozilla/firefox/profile/
```

### Step 4: Automated Certificate Management

#### 4.1 Renewal Monitoring Script
```bash
#!/bin/bash
# certificate_monitor.sh

CERT_PATH="$HOME/.pki/certs/alice_email.pem"
THRESHOLD_DAYS=30

# Check certificate expiration
EXPIRY_DATE=$(openssl x509 -enddate -noout -in "$CERT_PATH" | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s)
CURRENT_EPOCH=$(date +%s)
DAYS_REMAINING=$(( (EXPIRY_EPOCH - CURRENT_EPOCH) / 86400 ))

if [ $DAYS_REMAINING -lt $THRESHOLD_DAYS ]; then
    echo "WARNING: Certificate expires in $DAYS_REMAINING days"
    # Trigger renewal process
    ./renew_certificate.sh
fi
```

#### 4.2 Backup and Recovery Procedures
```bash
#!/bin/bash
# backup_certificates.sh

BACKUP_DIR="$HOME/.pki/backup/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup private keys (encrypted)
tar czf "$BACKUP_DIR/private_keys_encrypted.tar.gz" \
    -C "$HOME/.pki" private/

# Backup certificates and CSRs
tar czf "$BACKUP_DIR/certificates.tar.gz" \
    -C "$HOME/.pki" certs/ csr/

echo "Backup completed: $BACKUP_DIR"
```

### Step 5: Security Hardening

#### 5.1 Private Key Protection
```bash
# Use TPM for key storage (Windows)
certreq -enroll -machine -cert 12345 tpm:

# Use hardware token (PKCS#11)
pkcs11-tool --module /usr/lib/x86_64-linux-gnu/opensc-pkcs11.so \
    --write-object ~/.pki/private/alice_master.key \
    --type privkey --id 01 --login
```

#### 5.2 Access Control Implementation
```bash
# Set restrictive file permissions
find ~/.pki -type f -name "*.key" -exec chmod 400 {} \;
find ~/.pki -type d -exec chmod 700 {} \;

# Create access audit log
cat > ~/.pki/audit.sh << 'EOF'
#!/bin/bash
logger "PKI access: $USER accessed $1 at $(date)"
EOF
```

## Validation and Testing

### Functional Testing
```bash
# Test S/MIME signing
echo "Test message" | openssl smime -sign \
    -signer ~/.pki/certs/alice_email.pem \
    -inkey ~/.pki/private/alice_master.key

# Test certificate chain validation
openssl verify -CAfile ~/.pki/certs/ca_chain.pem \
    ~/.pki/certs/alice_email.pem

# Test client authentication (if applicable)
curl --cert ~/.pki/certs/alice_email.pem \
     --key ~/.pki/private/alice_master.key \
     https://secure.example.com/api/profile
```

### Security Testing
```bash
# Verify private key security
ls -la ~/.pki/private/
# Should show 400 permissions for .key files

# Test backup integrity
tar -tzf ~/.pki/backup/latest/private_keys_encrypted.tar.gz

# Verify certificate revocation status
openssl ocsp -issuer ~/.pki/certs/ca_chain.pem \
    -cert ~/.pki/certs/alice_email.pem \
    -url http://ocsp.ca.example.com
```

## Post-Deployment Configuration

### Monitoring Setup
1. Certificate expiration monitoring
2. Revocation status checking
3. Usage logging and auditing
4. Backup verification

### Maintenance Schedule
- **Daily**: Automated backup verification
- **Weekly**: Certificate status checks
- **Monthly**: Security audit and log review
- **Quarterly**: Full backup and recovery testing
- **Annually**: Certificate renewal planning

## Troubleshooting Common Issues

### Private Key Issues
```bash
# Verify private key integrity
openssl ec -in ~/.pki/private/alice_master.key -check

# Test private key matching with certificate
CERT_PUBKEY=$(openssl x509 -pubkey -noout -in ~/.pki/certs/alice_email.pem)
KEY_PUBKEY=$(openssl ec -pubout -in ~/.pki/private/alice_master.key)
diff <(echo "$CERT_PUBKEY") <(echo "$KEY_PUBKEY")
```

### Certificate Chain Issues
```bash
# Debug certificate chain
openssl verify -verbose -CAfile ~/.pki/certs/ca_chain.pem \
    ~/.pki/certs/alice_email.pem

# Check certificate details
openssl x509 -text -noout -in ~/.pki/certs/alice_email.pem
```

This deployment guide provides a comprehensive foundation for personal certificate implementation with proper security controls and operational procedures.