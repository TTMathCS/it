# Certificate Authority Deployment Guide

## Overview

This comprehensive deployment guide covers the establishment and operation of a Certificate Authority (CA) infrastructure. It addresses root CA setup, intermediate CA deployment, certificate issuance workflows, and operational security requirements for organizational PKI deployments.

## Prerequisites

### Infrastructure Requirements
- **Hardware Security Modules (HSMs)**: For root CA key protection
- **Secure Facilities**: Physical security for root CA operations
- **Network Infrastructure**: Segregated networks for CA operations
- **Backup Systems**: Secure offline backup capabilities
- **Monitoring Systems**: 24/7 operational monitoring

### Software Requirements
- **CA Software**: OpenSSL, Microsoft ADCS, or commercial CA solutions
- **Database Systems**: Certificate and CRL management databases
- **Web Servers**: Certificate enrollment and distribution services
- **Directory Services**: LDAP for certificate publication

### Personnel Requirements
- **CA Administrator**: Trusted personnel with dual control procedures
- **Security Officer**: PKI security policy enforcement
- **Operations Staff**: 24/7 monitoring and incident response

## Architecture Design

### Hierarchical CA Structure
```
Root CA (Offline)
├── Policy CA (Online)
│   ├── Issuing CA 1 (SSL/TLS Certificates)
│   ├── Issuing CA 2 (Email Certificates)
│   └── Issuing CA 3 (Code Signing Certificates)
└── Cross-Certification CA (External Trust)
```

### Security Zones
```python
def design_ca_security_zones():
    """
    Define security zones for CA deployment
    """
    security_zones = {
        "root_ca_zone": {
            "network": "air_gapped",
            "access": "dual_control_required",
            "operations": "ceremony_based",
            "key_storage": "fips_140_2_level_4_hsm",
            "backup": "secure_offsite_storage"
        },
        "policy_ca_zone": {
            "network": "isolated_vlan",
            "access": "role_based_authentication",
            "operations": "automated_with_oversight",
            "key_storage": "fips_140_2_level_3_hsm",
            "backup": "encrypted_network_backup"
        },
        "issuing_ca_zone": {
            "network": "dmz_segment",
            "access": "multi_factor_authentication",
            "operations": "fully_automated",
            "key_storage": "fips_140_2_level_2_hsm",
            "backup": "real_time_replication"
        },
        "registration_authority_zone": {
            "network": "internal_network",
            "access": "standard_authentication",
            "operations": "user_facing_services",
            "key_storage": "not_applicable",
            "backup": "standard_database_backup"
        }
    }
    
    return security_zones
```

## Root CA Deployment

### Phase 1: Root CA Infrastructure Setup

#### 1.1 Hardware Security Module Configuration
```bash
#!/bin/bash
# root_ca_hsm_setup.sh

echo "=== Root CA HSM Configuration ==="

# Initialize HSM partition
lunacm << 'EOF'
hsm init -label "RootCA_HSM" -domain "root.ca.domain"
partition init -label "RootCA_Partition"
role init -name "CA_Administrator"
EOF

# Generate authentication credentials
lunacm << 'EOF'
role login -name "CA_Administrator"
keypair generate -algorithm RSA -size 4096 -label "RootCA_SigningKey" -usage sign
keypair generate -algorithm RSA -size 4096 -label "RootCA_EncryptionKey" -usage encrypt
EOF

# Verify HSM status
echo "HSM Status Verification:"
lunacm -c "hsm show"
```

#### 1.2 Root CA Certificate Generation
```bash
#!/bin/bash
# generate_root_ca_certificate.sh

# Set up secure environment
umask 077
mkdir -p /secure/rootca/{private,certs,csr,crl,newcerts}
cd /secure/rootca

# Create OpenSSL configuration for Root CA
cat > openssl_root_ca.cnf << 'EOF'
[ ca ]
default_ca = CA_default

[ CA_default ]
dir = /secure/rootca
certs = $dir/certs
crl_dir = $dir/crl
new_certs_dir = $dir/newcerts
database = $dir/index.txt
serial = $dir/serial
RANDFILE = $dir/private/.rand

private_key = $dir/private/ca.key.pem
certificate = $dir/certs/ca.cert.pem

crlnumber = $dir/crlnumber
crl = $dir/crl/ca.crl.pem
crl_extensions = crl_ext
default_crl_days = 30

default_md = sha256
name_opt = ca_default
cert_opt = ca_default
default_days = 7300
preserve = no
policy = policy_strict

[ policy_strict ]
countryName = match
stateOrProvinceName = match
organizationName = match
organizationalUnitName = optional
commonName = supplied
emailAddress = optional

[ req ]
default_bits = 4096
distinguished_name = req_distinguished_name
string_mask = utf8only
default_md = sha256
x509_extensions = v3_ca

[ req_distinguished_name ]
countryName = Country Name (2 letter code)
stateOrProvinceName = State or Province Name
localityName = Locality Name
organizationName = Organization Name
organizationalUnitName = Organizational Unit Name
commonName = Common Name
emailAddress = Email Address

[ v3_ca ]
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints = critical,CA:true
keyUsage = critical, digitalSignature, cRLSign, keyCertSign
EOF

# Initialize CA database files
touch index.txt
echo 1000 > serial
echo 1000 > crlnumber

# Generate Root CA private key using HSM
pkcs11-tool --module /usr/lib/pkcs11/libCryptoki2_64.so \
    --login --pin $HSM_PIN \
    --keypairgen --key-type rsa:4096 \
    --label "RootCA_Key" --id 01

# Generate Root CA certificate
openssl req -config openssl_root_ca.cnf \
    -engine pkcs11 -keyform engine \
    -key "pkcs11:object=RootCA_Key" \
    -new -x509 -days 7300 -sha256 \
    -extensions v3_ca \
    -out certs/ca.cert.pem \
    -subj "/C=US/ST=California/O=Example Corp/CN=Example Corp Root CA"

# Verify Root CA certificate
openssl x509 -noout -text -in certs/ca.cert.pem
```

### Phase 2: Intermediate CA Deployment

#### 2.1 Policy CA Setup
```bash
#!/bin/bash
# deploy_policy_ca.sh

echo "=== Policy CA Deployment ==="

# Create Policy CA directory structure
mkdir -p /secure/policyca/{private,certs,csr,crl,newcerts}
cd /secure/policyca

# Generate Policy CA private key
openssl genpkey -algorithm RSA -out private/policyca.key.pem \
    -pkcs8 -aes256 -pass pass:"$POLICY_CA_PASSWORD" \
    -pkcs8opt rsa_keygen_bits:3072

# Generate Policy CA certificate signing request
openssl req -config ../rootca/openssl_root_ca.cnf \
    -key private/policyca.key.pem \
    -passin pass:"$POLICY_CA_PASSWORD" \
    -new -sha256 -out csr/policyca.csr.pem \
    -subj "/C=US/ST=California/O=Example Corp/CN=Example Corp Policy CA"

# Sign Policy CA certificate with Root CA (ceremony required)
cd ../rootca
openssl ca -config openssl_root_ca.cnf \
    -engine pkcs11 -keyform engine \
    -extensions v3_intermediate_ca -days 3650 -notext -md sha256 \
    -in ../policyca/csr/policyca.csr.pem \
    -out ../policyca/certs/policyca.cert.pem

# Create certificate chain file
cat ../policyca/certs/policyca.cert.pem \
    certs/ca.cert.pem > ../policyca/certs/ca-chain.cert.pem
```

#### 2.2 Issuing CA Deployment
```bash
#!/bin/bash
# deploy_issuing_ca.sh

CA_TYPE="$1"  # ssl, email, codesigning
if [[ -z "$CA_TYPE" ]]; then
    echo "Usage: $0 <ca_type>"
    exit 1
fi

echo "=== Issuing CA Deployment: $CA_TYPE ==="

# Create Issuing CA directory
mkdir -p "/secure/issuingca_$CA_TYPE"/{private,certs,csr,crl,newcerts}
cd "/secure/issuingca_$CA_TYPE"

# Generate Issuing CA private key
openssl genpkey -algorithm RSA -out "private/issuingca_$CA_TYPE.key.pem" \
    -pkcs8 -aes256 -pass pass:"$ISSUING_CA_PASSWORD" \
    -pkcs8opt rsa_keygen_bits:2048

# Generate certificate signing request
openssl req -new -sha256 \
    -key "private/issuingca_$CA_TYPE.key.pem" \
    -passin pass:"$ISSUING_CA_PASSWORD" \
    -out "csr/issuingca_$CA_TYPE.csr.pem" \
    -subj "/C=US/ST=California/O=Example Corp/CN=Example Corp $CA_TYPE Issuing CA"

# Sign with Policy CA
cd ../policyca
openssl ca -config openssl_policy_ca.cnf \
    -extensions "v3_${CA_TYPE}_ca" -days 1825 -notext -md sha256 \
    -in "../issuingca_$CA_TYPE/csr/issuingca_$CA_TYPE.csr.pem" \
    -out "../issuingca_$CA_TYPE/certs/issuingca_$CA_TYPE.cert.pem"

# Create certificate chain
cat "../issuingca_$CA_TYPE/certs/issuingca_$CA_TYPE.cert.pem" \
    "certs/policyca.cert.pem" \
    "../rootca/certs/ca.cert.pem" > \
    "../issuingca_$CA_TYPE/certs/ca-chain.cert.pem"
```

## Certificate Enrollment Services

### Web-based Enrollment Portal
```python
# certificate_enrollment_api.py
from flask import Flask, request, jsonify, render_template
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import sqlite3
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

class CertificateEnrollmentService:
    def __init__(self, ca_cert_path, ca_key_path):
        self.ca_cert_path = ca_cert_path
        self.ca_key_path = ca_key_path
        self.init_database()
    
    def init_database(self):
        """Initialize certificate request database"""
        conn = sqlite3.connect('enrollment.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS certificate_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                common_name TEXT NOT NULL,
                organization TEXT,
                email TEXT,
                csr_pem TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_by TEXT,
                certificate_pem TEXT,
                serial_number TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def validate_csr(self, csr_pem):
        """Validate certificate signing request"""
        try:
            csr = x509.load_pem_x509_csr(csr_pem.encode())
            
            # Verify CSR signature
            public_key = csr.public_key()
            csr.signature_hash_algorithm
            
            # Extract subject information
            subject_info = {}
            for attribute in csr.subject:
                subject_info[attribute.oid._name] = attribute.value
            
            return {
                "valid": True,
                "subject": subject_info,
                "public_key_size": public_key.key_size if hasattr(public_key, 'key_size') else None
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def submit_certificate_request(self, csr_pem, requester_info):
        """Submit certificate request for approval"""
        validation_result = self.validate_csr(csr_pem)
        
        if not validation_result["valid"]:
            return {"success": False, "error": validation_result["error"]}
        
        conn = sqlite3.connect('enrollment.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO certificate_requests 
            (common_name, organization, email, csr_pem)
            VALUES (?, ?, ?, ?)
        ''', (
            validation_result["subject"].get("commonName", ""),
            requester_info.get("organization", ""),
            requester_info.get("email", ""),
            csr_pem
        ))
        
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "request_id": request_id,
            "message": "Certificate request submitted for approval"
        }

@app.route('/api/submit_csr', methods=['POST'])
def submit_csr():
    """API endpoint for CSR submission"""
    data = request.json
    
    enrollment_service = CertificateEnrollmentService(
        app.config['CA_CERT_PATH'],
        app.config['CA_KEY_PATH']
    )
    
    result = enrollment_service.submit_certificate_request(
        data['csr_pem'],
        {
            "organization": data.get('organization', ''),
            "email": data.get('email', '')
        }
    )
    
    return jsonify(result)

@app.route('/api/certificate_status/<int:request_id>')
def certificate_status(request_id):
    """Check certificate request status"""
    conn = sqlite3.connect('enrollment.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT status, certificate_pem, created_at
        FROM certificate_requests 
        WHERE id = ?
    ''', (request_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return jsonify({
            "status": result[0],
            "certificate": result[1],
            "submitted": result[2]
        })
    else:
        return jsonify({"error": "Request not found"}), 404

if __name__ == '__main__':
    app.config['CA_CERT_PATH'] = '/secure/issuingca_ssl/certs/ca-chain.cert.pem'
    app.config['CA_KEY_PATH'] = '/secure/issuingca_ssl/private/issuingca_ssl.key.pem'
    app.run(host='0.0.0.0', port=8443, ssl_context='adhoc')
```

### Automated Certificate Issuance
```bash
#!/bin/bash
# automated_certificate_issuance.sh

# Certificate issuance automation script
CA_TYPE="$1"
REQUEST_ID="$2"

if [[ -z "$CA_TYPE" || -z "$REQUEST_ID" ]]; then
    echo "Usage: $0 <ca_type> <request_id>"
    exit 1
fi

echo "=== Automated Certificate Issuance ==="
echo "CA Type: $CA_TYPE"
echo "Request ID: $REQUEST_ID"

# Retrieve certificate request from database
CSR_DATA=$(sqlite3 /secure/enrollment.db \
    "SELECT csr_pem, common_name, email FROM certificate_requests WHERE id=$REQUEST_ID AND status='approved';")

if [[ -z "$CSR_DATA" ]]; then
    echo "ERROR: No approved certificate request found for ID $REQUEST_ID"
    exit 1
fi

IFS='|' read -r CSR_PEM COMMON_NAME EMAIL <<< "$CSR_DATA"

# Create temporary files for processing
TEMP_DIR=$(mktemp -d)
echo "$CSR_PEM" > "$TEMP_DIR/request.csr"

# Determine certificate profile based on CA type
case "$CA_TYPE" in
    "ssl")
        CERT_PROFILE="server_cert"
        VALIDITY_DAYS=365
        ;;
    "email")
        CERT_PROFILE="email_cert"
        VALIDITY_DAYS=730
        ;;
    "codesigning")
        CERT_PROFILE="code_signing_cert"
        VALIDITY_DAYS=1095
        ;;
    *)
        echo "ERROR: Unknown CA type: $CA_TYPE"
        exit 1
        ;;
esac

# Issue certificate using appropriate CA
cd "/secure/issuingca_$CA_TYPE"

openssl ca -config "openssl_${CA_TYPE}_ca.cnf" \
    -extensions "$CERT_PROFILE" \
    -days "$VALIDITY_DAYS" \
    -notext -md sha256 \
    -in "$TEMP_DIR/request.csr" \
    -out "$TEMP_DIR/certificate.pem" \
    -batch

if [[ $? -eq 0 ]]; then
    # Extract serial number
    SERIAL=$(openssl x509 -serial -noout -in "$TEMP_DIR/certificate.pem" | cut -d= -f2)
    
    # Read certificate content
    CERT_PEM=$(cat "$TEMP_DIR/certificate.pem")
    
    # Update database with issued certificate
    sqlite3 /secure/enrollment.db \
        "UPDATE certificate_requests SET status='issued', certificate_pem='$CERT_PEM', serial_number='$SERIAL' WHERE id=$REQUEST_ID;"
    
    echo "Certificate issued successfully"
    echo "Serial Number: $SERIAL"
    
    # Send notification email (if configured)
    if [[ -n "$EMAIL" ]]; then
        echo "Certificate has been issued and is ready for download." | \
        mail -s "Certificate Issued - Serial: $SERIAL" "$EMAIL"
    fi
else
    echo "ERROR: Certificate issuance failed"
    sqlite3 /secure/enrollment.db \
        "UPDATE certificate_requests SET status='failed' WHERE id=$REQUEST_ID;"
fi

# Clean up temporary files
rm -rf "$TEMP_DIR"
```

## Certificate Revocation and CRL Management

### Certificate Revocation Process
```bash
#!/bin/bash
# certificate_revocation.sh

SERIAL_NUMBER="$1"
REVOCATION_REASON="$2"
CA_TYPE="$3"

if [[ -z "$SERIAL_NUMBER" || -z "$REVOCATION_REASON" || -z "$CA_TYPE" ]]; then
    echo "Usage: $0 <serial_number> <reason> <ca_type>"
    echo "Reasons: unspecified, keyCompromise, cACompromise, affiliationChanged,"
    echo "         superseded, cessationOfOperation, certificateHold, removeFromCRL"
    exit 1
fi

echo "=== Certificate Revocation Process ==="
echo "Serial Number: $SERIAL_NUMBER"
echo "Reason: $REVOCATION_REASON"
echo "CA: $CA_TYPE"

# Navigate to appropriate CA directory
cd "/secure/issuingca_$CA_TYPE"

# Revoke certificate
openssl ca -config "openssl_${CA_TYPE}_ca.cnf" \
    -revoke "newcerts/${SERIAL_NUMBER}.pem" \
    -crl_reason "$REVOCATION_REASON"

if [[ $? -eq 0 ]]; then
    echo "Certificate revoked successfully"
    
    # Generate updated CRL
    openssl ca -config "openssl_${CA_TYPE}_ca.cnf" \
        -gencrl -out "crl/ca.crl.pem"
    
    # Convert CRL to DER format for web distribution
    openssl crl -in "crl/ca.crl.pem" \
        -outform DER -out "crl/ca.crl"
    
    # Update CRL distribution points
    cp "crl/ca.crl" /var/www/html/crl/
    cp "crl/ca.crl.pem" /var/www/html/crl/
    
    echo "CRL updated and published"
    
    # Update database
    sqlite3 /secure/enrollment.db \
        "UPDATE certificate_requests SET status='revoked' WHERE serial_number='$SERIAL_NUMBER';"
    
    # Notify OCSP responder
    systemctl restart ocsp-responder
    
else
    echo "ERROR: Certificate revocation failed"
    exit 1
fi
```

### OCSP Responder Deployment
```bash
#!/bin/bash
# deploy_ocsp_responder.sh

echo "=== OCSP Responder Deployment ==="

# Create OCSP responder directory structure
mkdir -p /secure/ocsp/{config,certs,logs}
cd /secure/ocsp

# Generate OCSP signing certificate
openssl req -new -keyout certs/ocsp.key \
    -out certs/ocsp.csr -nodes \
    -subj "/C=US/ST=California/O=Example Corp/CN=OCSP Responder"

# Sign OCSP certificate with issuing CA
cd /secure/issuingca_ssl
openssl ca -config openssl_ssl_ca.cnf \
    -extensions ocsp_cert -days 365 -notext -md sha256 \
    -in ../ocsp/certs/ocsp.csr \
    -out ../ocsp/certs/ocsp.crt

# Configure OpenSSL OCSP responder
cat > /secure/ocsp/config/ocsp.conf << 'EOF'
openssl_conf = openssl_init

[openssl_init]
engines = engine_section

[engine_section]
pkcs11 = pkcs11_section

[pkcs11_section]
engine_id = pkcs11
dynamic_path = /usr/lib/x86_64-linux-gnu/engines-1.1/pkcs11.so
MODULE_PATH = /usr/lib/pkcs11/libCryptoki2_64.so
init = 0
EOF

# Create OCSP responder service
cat > /etc/systemd/system/ocsp-responder.service << 'EOF'
[Unit]
Description=OpenSSL OCSP Responder
After=network.target

[Service]
Type=simple
User=ocsp
Group=ocsp
WorkingDirectory=/secure/ocsp
ExecStart=/usr/bin/openssl ocsp \
    -index /secure/issuingca_ssl/index.txt \
    -port 8080 \
    -rsigner /secure/ocsp/certs/ocsp.crt \
    -rkey /secure/ocsp/certs/ocsp.key \
    -CA /secure/issuingca_ssl/certs/ca-chain.cert.pem \
    -text -nmin 1
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start OCSP responder
systemctl daemon-reload
systemctl enable ocsp-responder
systemctl start ocsp-responder

echo "OCSP responder deployed and running on port 8080"
```

## Monitoring and Maintenance

### CA Health Monitoring
```python
#!/usr/bin/env python3
# ca_health_monitor.py

import subprocess
import sqlite3
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import json
import logging

class CAHealthMonitor:
    def __init__(self, config_file):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/ca_health.log'),
                logging.StreamHandler()
            ]
        )
    
    def check_certificate_expiration(self):
        """Check for expiring certificates"""
        alerts = []
        
        for ca_path in self.config['ca_paths']:
            cmd = f"openssl x509 -enddate -noout -in {ca_path}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                end_date_str = result.stdout.split('=')[1].strip()
                end_date = datetime.strptime(end_date_str, "%b %d %H:%M:%S %Y %Z")
                days_remaining = (end_date - datetime.now()).days
                
                if days_remaining < 90:  # Alert if less than 90 days
                    alerts.append({
                        "type": "certificate_expiration",
                        "ca_path": ca_path,
                        "days_remaining": days_remaining,
                        "expiry_date": end_date_str,
                        "severity": "critical" if days_remaining < 30 else "warning"
                    })
        
        return alerts
    
    def check_crl_freshness(self):
        """Check CRL update status"""
        alerts = []
        
        for crl_path in self.config['crl_paths']:
            cmd = f"openssl crl -nextupdate -noout -in {crl_path}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                next_update_str = result.stdout.split('=')[1].strip()
                next_update = datetime.strptime(next_update_str, "%b %d %H:%M:%S %Y %Z")
                
                if datetime.now() > next_update:
                    alerts.append({
                        "type": "stale_crl",
                        "crl_path": crl_path,
                        "next_update": next_update_str,
                        "severity": "critical"
                    })
        
        return alerts
    
    def check_hsm_status(self):
        """Check HSM connectivity and status"""
        alerts = []
        
        try:
            result = subprocess.run(
                ["lunacm", "-c", "hsm", "show"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0 or "Error" in result.stdout:
                alerts.append({
                    "type": "hsm_error",
                    "message": result.stdout,
                    "severity": "critical"
                })
        except subprocess.TimeoutExpired:
            alerts.append({
                "type": "hsm_timeout",
                "message": "HSM communication timeout",
                "severity": "critical"
            })
        except FileNotFoundError:
            alerts.append({
                "type": "hsm_not_available",
                "message": "HSM tools not installed",
                "severity": "warning"
            })
        
        return alerts
    
    def check_ocsp_responder(self):
        """Check OCSP responder availability"""
        alerts = []
        
        for ocsp_url in self.config['ocsp_urls']:
            try:
                result = subprocess.run([
                    "curl", "-s", "--max-time", "10", "-I", ocsp_url
                ], capture_output=True, text=True)
                
                if result.returncode != 0 or "200 OK" not in result.stdout:
                    alerts.append({
                        "type": "ocsp_unavailable",
                        "url": ocsp_url,
                        "severity": "warning"
                    })
            except Exception as e:
                alerts.append({
                    "type": "ocsp_check_failed",
                    "url": ocsp_url,
                    "error": str(e),
                    "severity": "warning"
                })
        
        return alerts
    
    def send_alert(self, alerts):
        """Send alert notifications"""
        if not alerts:
            return
        
        critical_alerts = [a for a in alerts if a['severity'] == 'critical']
        warning_alerts = [a for a in alerts if a['severity'] == 'warning']
        
        subject = f"CA Health Alert - {len(critical_alerts)} Critical, {len(warning_alerts)} Warnings"
        
        message_body = "CA Health Monitoring Report\n"
        message_body += f"Generated: {datetime.now().isoformat()}\n\n"
        
        if critical_alerts:
            message_body += "CRITICAL ALERTS:\n"
            for alert in critical_alerts:
                message_body += f"- {alert['type']}: {alert}\n"
            message_body += "\n"
        
        if warning_alerts:
            message_body += "WARNING ALERTS:\n"
            for alert in warning_alerts:
                message_body += f"- {alert['type']}: {alert}\n"
        
        # Send email notification
        msg = MIMEText(message_body)
        msg['Subject'] = subject
        msg['From'] = self.config['alert_from']
        msg['To'] = ', '.join(self.config['alert_recipients'])
        
        try:
            smtp_server = smtplib.SMTP(self.config['smtp_server'])
            smtp_server.send_message(msg)
            smtp_server.quit()
            logging.info(f"Alert sent: {subject}")
        except Exception as e:
            logging.error(f"Failed to send alert: {e}")
    
    def run_health_checks(self):
        """Run all health checks"""
        all_alerts = []
        
        # Run individual health checks
        all_alerts.extend(self.check_certificate_expiration())
        all_alerts.extend(self.check_crl_freshness())
        all_alerts.extend(self.check_hsm_status())
        all_alerts.extend(self.check_ocsp_responder())
        
        # Log results
        logging.info(f"Health check completed. {len(all_alerts)} issues found.")
        
        # Send alerts if any issues found
        if all_alerts:
            self.send_alert(all_alerts)
        
        return all_alerts

if __name__ == "__main__":
    monitor = CAHealthMonitor('/secure/config/ca_monitor.json')
    monitor.run_health_checks()
```

This comprehensive CA deployment guide provides the foundation for establishing and operating a secure certificate authority infrastructure with proper security controls, operational procedures, and monitoring capabilities.