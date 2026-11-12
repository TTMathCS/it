# Device Identity Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying device identity infrastructure using PKI certificates for IoT devices, mobile devices, and network equipment. It covers technical implementation, configuration requirements, and operational procedures for enterprise device identity management.

## Prerequisites

### Software Requirements
- OpenSSL 3.0+ (cryptographic operations)
- Device management platforms (Intune, JAMF, VMware Workspace ONE)
- Certificate Authority infrastructure (internal or external)
- Device provisioning systems
- Network access control (NAC) systems
- SCEP/EST protocol support

### Hardware Requirements
- TPM 2.0 or secure element for key storage
- Network connectivity for certificate enrollment
- Device management infrastructure
- PKI infrastructure components
- Secure provisioning environment

## Pre-Deployment Planning

### Device Identity Architecture
```python
def plan_device_identity_architecture(device_types, scale, security_level):
    """
    Plan device identity architecture based on organizational requirements
    """
    architectures = {
        "small_basic": {
            "enrollment_protocol": "SCEP",
            "ca_integration": "external_ca",
            "device_attestation": "software_based",
            "certificate_lifetime": "1_year"
        },
        "enterprise_standard": {
            "enrollment_protocol": "EST",
            "ca_integration": "internal_ca",
            "device_attestation": "tpm_based",
            "certificate_lifetime": "2_years",
            "nac_integration": True
        },
        "high_security": {
            "enrollment_protocol": "custom_api",
            "ca_integration": "air_gapped_ca",
            "device_attestation": "hardware_hsm",
            "certificate_lifetime": "6_months",
            "nac_integration": True,
            "continuous_monitoring": True
        }
    }
    
    return architectures.get(f"{scale}_{security_level}", architectures["enterprise_standard"])
```

### Certificate Template Design
```bash
# Device identity certificate template
DEVICE_CERT_TEMPLATE='{
    "template_name": "DeviceIdentity",
    "validity_period": "2_years",
    "key_usage": ["digitalSignature", "keyEncipherment"],
    "extended_key_usage": ["clientAuth", "serverAuth"],
    "subject_alt_names": ["dNSName", "iPAddress"],
    "key_algorithm": "ECDSA_P256",
    "device_attestation": "required"
}'

# IoT device template
IOT_CERT_TEMPLATE='{
    "template_name": "IoTDevice",
    "validity_period": "5_years",
    "key_usage": ["digitalSignature"],
    "extended_key_usage": ["clientAuth"],
    "key_algorithm": "ECDSA_P256",
    "lightweight_profile": true
}'
```

## Step-by-Step Deployment

### Step 1: Certificate Authority Configuration

#### 1.1 Device Identity CA Setup
```bash
# Create device identity CA structure
mkdir -p /opt/device-ca/{root,intermediate,certs,crl,private,devices}
chmod 700 /opt/device-ca/private

# Generate device identity root CA
openssl ecparam -genkey -name prime256v1 -out /opt/device-ca/private/device-root-ca.key
openssl req -new -x509 -days 7300 -key /opt/device-ca/private/device-root-ca.key \
    -out /opt/device-ca/certs/device-root-ca.pem \
    -config /opt/device-ca/device-root.cnf

# Create intermediate CA for device enrollment
openssl ecparam -genkey -name prime256v1 -out /opt/device-ca/private/device-intermediate-ca.key
openssl req -new -key /opt/device-ca/private/device-intermediate-ca.key \
    -out /opt/device-ca/csr/device-intermediate-ca.csr \
    -config /opt/device-ca/device-intermediate.cnf

# Sign intermediate certificate
openssl ca -in /opt/device-ca/csr/device-intermediate-ca.csr \
    -out /opt/device-ca/certs/device-intermediate-ca.pem \
    -config /opt/device-ca/device-root.cnf \
    -extensions v3_intermediate_ca -days 3650
```

### Step 2: SCEP Server Configuration

#### 2.1 SCEP Service Setup
```bash
# Install and configure SCEP server
mkdir -p /opt/scep-server/{config,certs,logs}

# Configure SCEP server
cat > /opt/scep-server/config/scep.conf << 'EOF'
[scep]
ca_cert = /opt/device-ca/certs/device-intermediate-ca.pem
ca_key = /opt/device-ca/private/device-intermediate-ca.key
challenge_password = SecureChallenge123
max_poll_time = 3600
cert_validity_days = 730

[security]
require_challenge = true
allow_renewal = true
max_cert_per_device = 1
EOF

# Create SCEP service script
cat > /opt/scep-server/scep_service.py << 'EOF'
#!/usr/bin/env python3
"""
SCEP Server for Device Certificate Enrollment
"""
import http.server
import ssl
import subprocess
from urllib.parse import parse_qs, urlparse

class SCEPHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)
        
        if parsed_path.path == '/scep':
            operation = params.get('operation', [''])[0]
            
            if operation == 'GetCACert':
                self.send_ca_cert()
            elif operation == 'GetCACaps':
                self.send_ca_capabilities()
            else:
                self.send_error(400, "Invalid operation")
        else:
            self.send_error(404, "Not found")
    
    def do_POST(self):
        if self.path.startswith('/scep'):
            content_length = int(self.headers['Content-Length'])
            scep_request = self.rfile.read(content_length)
            
            # Process SCEP enrollment request
            self.process_scep_request(scep_request)
        else:
            self.send_error(404, "Not found")
    
    def send_ca_cert(self):
        with open('/opt/device-ca/certs/device-intermediate-ca.pem', 'rb') as f:
            ca_cert = f.read()
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-x509-ca-cert')
        self.send_header('Content-Length', str(len(ca_cert)))
        self.end_headers()
        self.wfile.write(ca_cert)
    
    def send_ca_capabilities(self):
        caps = "POSTPKIOperation\nSHA-256\nAES"
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(caps.encode())

if __name__ == '__main__':
    server = http.server.HTTPServer(('0.0.0.0', 8080), SCEPHandler)
    server.serve_forever()
EOF

chmod +x /opt/scep-server/scep_service.py
```

### Step 3: Device Provisioning Integration

#### 3.1 Mobile Device Management
```powershell
# Intune device certificate profile
$certificateProfile = @{
    "@odata.type" = "#microsoft.graph.androidDeviceOwnerScepCertificateProfile"
    displayName = "Device Identity Certificate"
    description = "PKI certificate for device authentication"
    scepServerUrl = "https://scep.company.com:8080/scep"
    subjectNameFormat = "customFormat"
    subjectNameFormatString = "CN={{DeviceName}},O=Company"
    subjectAlternativeNameType = "custom"
    customSubjectAlternativeNames = @(
        @{
            sanType = "domainNameService"
            name = "{{DeviceName}}.company.com"
        }
    )
    certificateValidityPeriodValue = 2
    certificateValidityPeriodScale = "years"
    keySize = 256
    hashAlgorithm = "sha256"
    keyUsage = "digitalSignature", "keyEncipherment"
    extendedKeyUsages = @(
        @{
            name = "Client Authentication"
            objectIdentifier = "1.3.6.1.5.5.7.3.2"
        }
    )
}

# Create certificate profile via Microsoft Graph API
Invoke-RestMethod -Uri "https://graph.microsoft.com/v1.0/deviceManagement/deviceConfigurations" `
    -Method POST -Body ($certificateProfile | ConvertTo-Json -Depth 10) `
    -Headers @{Authorization="Bearer $accessToken"; "Content-Type"="application/json"}
```

#### 3.2 Network Device Provisioning
```bash
#!/bin/bash
# network_device_provisioning.sh

provision_network_device() {
    local device_ip="$1"
    local device_type="$2"
    local device_serial="$3"
    
    echo "Provisioning device certificate for $device_ip ($device_type)"
    
    # Generate device key pair
    openssl ecparam -genkey -name prime256v1 -out "device_${device_serial}.key"
    
    # Create certificate signing request
    openssl req -new -key "device_${device_serial}.key" \
        -out "device_${device_serial}.csr" \
        -config device.cnf \
        -subj "/CN=${device_serial}.company.com/O=Company/OU=Network Infrastructure"
    
    # Submit CSR to CA
    curl -X POST https://ca.company.com/api/enroll \
        -H "Content-Type: application/pkcs10" \
        -H "Authorization: Bearer $CA_TOKEN" \
        --data-binary @"device_${device_serial}.csr" \
        -o "device_${device_serial}.pem"
    
    # Install certificate on device (example for Cisco devices)
    if [[ "$device_type" == "cisco" ]]; then
        scp "device_${device_serial}.pem" admin@$device_ip:/bootflash/
        ssh admin@$device_ip "
            configure terminal
            crypto pki import device_cert pkcs12 bootflash:device_${device_serial}.pem password
            crypto pki trustpoint device_cert
            enrollment url https://ca.company.com/
            exit
        "
    fi
    
    echo "Device certificate provisioned successfully"
}

# Example usage
provision_network_device "10.1.1.100" "cisco" "SN123456789"
```

### Step 4: IoT Device Certificate Management

#### 4.1 Embedded Device Integration
```c
/* embedded_device_cert.c - Example for embedded device certificate management */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <mbedtls/pk.h>
#include <mbedtls/entropy.h>
#include <mbedtls/ctr_drbg.h>
#include <mbedtls/x509_csr.h>

int generate_device_certificate(const char* device_id) {
    mbedtls_pk_context key;
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context ctr_drbg;
    mbedtls_x509write_csr req;
    
    const char *pers = "device_cert_gen";
    unsigned char output_buf[4096];
    int ret = 0;
    
    // Initialize contexts
    mbedtls_pk_init(&key);
    mbedtls_entropy_init(&entropy);
    mbedtls_ctr_drbg_init(&ctr_drbg);
    mbedtls_x509write_csr_init(&req);
    
    // Seed the random number generator
    if ((ret = mbedtls_ctr_drbg_seed(&ctr_drbg, mbedtls_entropy_func, &entropy,
                                     (const unsigned char *)pers, strlen(pers))) != 0) {
        printf("mbedtls_ctr_drbg_seed returned %d\n", ret);
        goto exit;
    }
    
    // Generate key pair
    if ((ret = mbedtls_pk_setup(&key, mbedtls_pk_info_from_type(MBEDTLS_PK_ECKEY))) != 0) {
        printf("mbedtls_pk_setup returned %d\n", ret);
        goto exit;
    }
    
    if ((ret = mbedtls_ecp_gen_key(MBEDTLS_ECP_DP_SECP256R1,
                                   mbedtls_pk_ec(key),
                                   mbedtls_ctr_drbg_random, &ctr_drbg)) != 0) {
        printf("mbedtls_ecp_gen_key returned %d\n", ret);
        goto exit;
    }
    
    // Create CSR
    mbedtls_x509write_csr_set_key(&req, &key);
    mbedtls_x509write_csr_set_md_alg(&req, MBEDTLS_MD_SHA256);
    
    // Set subject
    char subject[256];
    snprintf(subject, sizeof(subject), "CN=%s.iot.company.com,O=Company,OU=IoT Devices", device_id);
    
    if ((ret = mbedtls_x509write_csr_set_subject_name(&req, subject)) != 0) {
        printf("mbedtls_x509write_csr_set_subject_name returned %d\n", ret);
        goto exit;
    }
    
    // Generate CSR
    if ((ret = mbedtls_x509write_csr_pem(&req, output_buf, sizeof(output_buf),
                                         mbedtls_ctr_drbg_random, &ctr_drbg)) != 0) {
        printf("mbedtls_x509write_csr_pem returned %d\n", ret);
        goto exit;
    }
    
    printf("Generated CSR for device %s:\n%s\n", device_id, output_buf);
    
exit:
    mbedtls_x509write_csr_free(&req);
    mbedtls_pk_free(&key);
    mbedtls_ctr_drbg_free(&ctr_drbg);
    mbedtls_entropy_free(&entropy);
    
    return ret;
}

int main() {
    return generate_device_certificate("DEVICE001");
}
```

## Post-Deployment Configuration

### Device Certificate Monitoring
```bash
#!/bin/bash
# device_cert_monitoring.sh

monitor_device_certificates() {
    echo "=== Device Certificate Monitoring ==="
    echo "Date: $(date)"
    
    # Check certificate expiration
    find /opt/device-ca/devices -name "*.pem" | while read cert; do
        device_id=$(openssl x509 -in "$cert" -noout -subject | sed 's/.*CN=\([^,]*\).*/\1/')
        expiry_date=$(openssl x509 -in "$cert" -noout -enddate | cut -d= -f2)
        days_left=$(( ($(date -d "$expiry_date" +%s) - $(date +%s)) / 86400 ))
        
        if [[ $days_left -lt 30 ]]; then
            echo "WARNING: Certificate for device $device_id expires in $days_left days"
            # Trigger automatic renewal
            trigger_device_renewal "$device_id"
        fi
    done
    
    # Check device connectivity
    active_devices=$(grep -c "CERT_AUTH_SUCCESS" /var/log/radius.log)
    total_devices=$(find /opt/device-ca/devices -name "*.pem" | wc -l)
    
    echo "Active devices: $active_devices / $total_devices"
}

trigger_device_renewal() {
    local device_id="$1"
    echo "Triggering certificate renewal for device: $device_id"
    
    # Send renewal notification via device management system
    curl -X POST https://mdm.company.com/api/renew-certificate \
        -H "Content-Type: application/json" \
        -d "{\"device_id\": \"$device_id\"}"
}

monitor_device_certificates
```

This deployment guide ensures comprehensive device identity management through proper PKI implementation across various device types and platforms.