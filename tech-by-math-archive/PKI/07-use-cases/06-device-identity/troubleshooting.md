# Device Identity Troubleshooting Guide

## Overview

This troubleshooting guide addresses common issues in device identity implementations using PKI certificates across IoT devices, mobile devices, and network equipment. Issues are categorized with diagnostic procedures and resolution strategies for enterprise device identity management.

## Diagnostic Framework

### Issue Classification System
```python
def classify_device_identity_issue(device_type, symptoms, error_messages):
    """
    Classify device identity issues for targeted troubleshooting
    """
    issue_patterns = {
        "enrollment_failures": [
            "SCEP enrollment failed",
            "certificate request rejected",
            "invalid challenge password",
            "device not authorized"
        ],
        "certificate_validation_issues": [
            "certificate expired",
            "certificate revoked",
            "chain validation failed",
            "untrusted CA"
        ],
        "device_connectivity_problems": [
            "network access denied",
            "authentication failed",
            "device quarantined",
            "NAC policy violation"
        ],
        "platform_specific_issues": [
            "TPM not available",
            "secure element error",
            "keystore access denied",
            "MDM profile failed"
        ]
    }
    
    detected_issues = []
    for category, patterns in issue_patterns.items():
        for pattern in patterns:
            if any(pattern.lower() in msg.lower() for msg in error_messages):
                detected_issues.append({
                    "category": category,
                    "pattern": pattern,
                    "device_type": device_type,
                    "priority": get_issue_priority(category, device_type)
                })
    
    return detected_issues
```

## Common Issues and Solutions

### 1. Device Enrollment Problems

#### Issue: SCEP Enrollment Failures
```bash
# Diagnostic commands for SCEP enrollment
curl -v "https://scep.company.com:8080/scep?operation=GetCACert"
curl -v "https://scep.company.com:8080/scep?operation=GetCACaps"

# Test SCEP enrollment manually
openssl req -new -keyout device-test.key -out device-test.csr -nodes \
    -subj "/CN=test-device.company.com/O=Company"

# Submit SCEP request
curl -X POST "https://scep.company.com:8080/scep" \
    -H "Content-Type: application/octet-stream" \
    --data-binary @device-test.p7b

# Common solutions:
# 1. Verify challenge password
# 2. Check device authorization
# 3. Validate network connectivity
# 4. Review CA certificate chain
```

#### Issue: Mobile Device Certificate Profile Failures
```powershell
# Intune certificate profile troubleshooting
Get-IntuneManagedDevice | Where-Object {$_.deviceName -eq "ProblemDevice"}

# Check certificate deployment status
Get-DeviceConfigurationDeviceStatus -DeviceConfigurationId $profileId

# Common solutions:
# 1. Verify SCEP server accessibility
# 2. Check device compliance status
# 3. Validate certificate template settings
# 4. Review MDM enrollment status

# JAMF certificate troubleshooting (macOS)
sudo profiles show -type enrollment
sudo profiles show -type configuration

# Check certificate in keychain
security find-certificate -a -p login.keychain
```

### 2. Certificate Validation Issues

#### Issue: Certificate Chain Validation Failures
```bash
# Verify certificate chain for device
device_cert="/opt/devices/device123.pem"
ca_bundle="/opt/ca/ca-bundle.pem"

# Test certificate validation
openssl verify -CAfile "$ca_bundle" "$device_cert"

# Check certificate details
openssl x509 -in "$device_cert" -text -noout | grep -A5 "Issuer:"
openssl x509 -in "$device_cert" -text -noout | grep -A5 "Subject:"

# Validate certificate usage
openssl x509 -in "$device_cert" -text -noout | grep -A10 "X509v3 extensions"

# Solutions:
# 1. Rebuild certificate chain with intermediates
# 2. Update CA trust store
# 3. Check certificate revocation status
```

### 3. Device-Specific Issues

#### IoT Device Certificate Problems
```bash
#!/bin/bash
# iot_device_diagnostic.sh

diagnose_iot_device() {
    local device_id="$1"
    local device_ip="$2"
    
    echo "=== IoT Device Certificate Diagnostics ==="
    echo "Device ID: $device_id"
    echo "Device IP: $device_ip"
    
    # Test network connectivity
    if ping -c 3 "$device_ip" >/dev/null 2>&1; then
        echo "Network connectivity: OK"
    else
        echo "Network connectivity: FAILED"
        return 1
    fi
    
    # Test HTTPS certificate
    echo | openssl s_client -connect "$device_ip:443" -servername "$device_id" 2>/dev/null | \
        openssl x509 -noout -dates -subject -issuer
    
    # Check device certificate file
    device_cert="/opt/device-ca/devices/${device_id}.pem"
    if [[ -f "$device_cert" ]]; then
        echo "Device certificate: Found"
        
        # Check expiration
        expiry_date=$(openssl x509 -in "$device_cert" -noout -enddate | cut -d= -f2)
        days_left=$(( ($(date -d "$expiry_date" +%s) - $(date +%s)) / 86400 ))
        echo "Certificate expires in: $days_left days"
        
        if [[ $days_left -lt 30 ]]; then
            echo "WARNING: Certificate expires soon"
            trigger_certificate_renewal "$device_id"
        fi
    else
        echo "Device certificate: NOT FOUND"
        echo "Solution: Re-enroll device certificate"
        initiate_device_enrollment "$device_id"
    fi
}

trigger_certificate_renewal() {
    local device_id="$1"
    echo "Triggering certificate renewal for $device_id"
    
    # Send renewal command to device (example for MQTT)
    mosquitto_pub -h mqtt.company.com -t "devices/$device_id/renew-cert" -m "renew"
}
```

#### Network Device Certificate Issues
```bash
#!/bin/bash
# network_device_troubleshooting.sh

troubleshoot_network_device() {
    local device_ip="$1"
    local device_type="$2"
    
    echo "=== Network Device Certificate Troubleshooting ==="
    echo "Device: $device_ip ($device_type)"
    
    # Test SSH connectivity
    if timeout 10 ssh -o ConnectTimeout=5 admin@"$device_ip" "show version" >/dev/null 2>&1; then
        echo "SSH connectivity: OK"
        
        # Check certificate status on device
        case "$device_type" in
            "cisco")
                ssh admin@"$device_ip" "show crypto pki certificates"
                ;;
            "juniper")
                ssh admin@"$device_ip" "show security pki certificate"
                ;;
            "arista")
                ssh admin@"$device_ip" "show management security ssl profile"
                ;;
        esac
    else
        echo "SSH connectivity: FAILED"
        echo "Solutions:"
        echo "1. Check network connectivity"
        echo "2. Verify SSH credentials" 
        echo "3. Check device management interface"
    fi
}
```

### 4. Mobile Device Management Issues

#### Android Device Certificate Problems
```bash
# Android device certificate diagnostics
adb devices  # List connected devices

# Check certificate store
adb shell "am start -a android.credentials.INSTALL"

# View installed certificates
adb shell "pm list packages | grep certificate"

# Check device compliance
curl -X GET "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices" \
    -H "Authorization: Bearer $access_token" | \
    jq '.value[] | select(.deviceName=="ProblemDevice")'
```

#### iOS Device Certificate Issues
```bash
# iOS device certificate troubleshooting
# Check MDM profile installation
sudo profiles -P

# Verify certificate in keychain
security find-certificate -a -Z

# Check device enrollment status
curl -X GET "https://api.apple.com/1/deviceManagement/devices" \
    -H "Authorization: Bearer $token"
```

### 5. Performance and Scale Issues

#### Large-Scale Device Enrollment Problems
```python
def diagnose_enrollment_performance():
    """
    Diagnose performance issues in large-scale device enrollment
    """
    import time
    import concurrent.futures
    
    def test_enrollment_endpoint(device_id):
        start_time = time.time()
        try:
            # Simulate enrollment request
            response = requests.post(
                "https://scep.company.com:8080/scep",
                headers={'Content-Type': 'application/octet-stream'},
                timeout=30
            )
            end_time = time.time()
            return {
                'device_id': device_id,
                'success': response.status_code == 200,
                'response_time': end_time - start_time
            }
        except Exception as e:
            return {
                'device_id': device_id,
                'success': False,
                'error': str(e)
            }
    
    # Test concurrent enrollments
    device_ids = [f"test-device-{i:03d}" for i in range(50)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(test_enrollment_endpoint, device_ids))
    
    # Analyze results
    success_rate = sum(1 for r in results if r['success']) / len(results)
    avg_response_time = sum(r.get('response_time', 0) for r in results if r['success']) / sum(1 for r in results if r['success'])
    
    print(f"Enrollment Performance Test Results:")
    print(f"Success Rate: {success_rate:.2%}")
    print(f"Average Response Time: {avg_response_time:.2f}s")
    
    if success_rate < 0.95:
        print("WARNING: Low enrollment success rate")
        print("Recommendations:")
        print("- Scale SCEP server infrastructure")
        print("- Implement load balancing")
        print("- Optimize certificate generation")
    
    if avg_response_time > 10:
        print("WARNING: Slow enrollment response times")
        print("Recommendations:")
        print("- Optimize CA response times")
        print("- Implement certificate caching")
        print("- Use faster key generation algorithms")

diagnose_enrollment_performance()
```

### 6. Network Access Control Issues

#### Certificate-Based NAC Problems
```bash
#!/bin/bash
# nac_troubleshooting.sh

troubleshoot_nac_access() {
    local device_id="$1"
    local device_ip="$2"
    
    echo "=== NAC Certificate Troubleshooting ==="
    echo "Device: $device_id ($device_ip)"
    
    # Check device authentication logs
    grep "$device_ip" /var/log/radius.log | tail -10
    
    # Test RADIUS authentication
    echo "User-Name = $device_id, User-Password = certificate" | \
        radclient radius.company.com:1812 auth testing123
    
    # Check certificate in NAC policy
    device_cert_serial=$(openssl x509 -in "/opt/devices/${device_id}.pem" -noout -serial | cut -d= -f2)
    
    # Verify certificate not revoked
    openssl crl -in /opt/ca/crl.pem -noout -text | grep -i "$device_cert_serial"
    
    if [[ $? -eq 0 ]]; then
        echo "ERROR: Device certificate is revoked"
        echo "Solution: Re-enroll device certificate"
    else
        echo "Certificate revocation status: OK"
    fi
    
    # Check NAC policy assignment
    curl -X GET "https://nac.company.com/api/device-policy/$device_id" \
        -H "Authorization: Bearer $nac_token" | jq '.'
}
```

## Emergency Response Procedures

### Mass Device Certificate Revocation
```bash
#!/bin/bash
# emergency_device_revocation.sh

emergency_revoke_devices() {
    local device_list_file="$1"
    local incident_id="$2"
    
    echo "=== EMERGENCY: Mass Device Certificate Revocation ==="
    echo "Incident ID: $incident_id"
    echo "Device List: $device_list_file"
    
    # Create emergency CRL
    emergency_crl="/opt/ca/crl/emergency-$(date +%Y%m%d-%H%M).crl"
    
    # Revoke certificates for all devices in list
    while IFS= read -r device_id; do
        if [[ -n "$device_id" && ! "$device_id" =~ ^# ]]; then
            echo "Revoking certificate for device: $device_id"
            
            device_cert="/opt/device-ca/devices/${device_id}.pem"
            if [[ -f "$device_cert" ]]; then
                openssl ca -revoke "$device_cert" -config /opt/device-ca/ca.cnf
                
                # Immediately block device access
                device_ip=$(get_device_ip "$device_id")
                iptables -A INPUT -s "$device_ip" -j DROP
                
                # Update NAC system
                curl -X POST "https://nac.company.com/api/quarantine-device" \
                    -H "Content-Type: application/json" \
                    -d "{\"device_id\": \"$device_id\", \"reason\": \"emergency_revocation\"}"
            fi
        fi
    done < "$device_list_file"
    
    # Generate and distribute emergency CRL
    openssl ca -gencrl -out "$emergency_crl" -config /opt/device-ca/ca.cnf
    
    # Distribute CRL to all validation points
    distribute_emergency_crl "$emergency_crl"
    
    echo "Emergency revocation completed"
}

distribute_emergency_crl() {
    local crl_file="$1"
    
    # Upload to CRL distribution points
    scp "$crl_file" crl-server1.company.com:/var/www/html/crl/
    scp "$crl_file" crl-server2.company.com:/var/www/html/crl/
    
    # Notify all NAC systems
    for nac_server in nac1.company.com nac2.company.com; do
        curl -X POST "https://$nac_server/api/update-crl" \
            -H "Content-Type: application/octet-stream" \
            --data-binary @"$crl_file"
    done
}
```

### Device Recovery Procedures
```bash
#!/bin/bash
# device_recovery.sh

recover_compromised_device() {
    local device_id="$1"
    local recovery_method="$2"
    
    echo "=== Device Recovery Procedure ==="
    echo "Device: $device_id"
    echo "Recovery Method: $recovery_method"
    
    case "$recovery_method" in
        "certificate_renewal")
            # Generate new certificate
            echo "Generating new certificate for recovered device..."
            generate_device_certificate "$device_id"
            
            # Remove device from quarantine
            curl -X DELETE "https://nac.company.com/api/quarantine-device/$device_id"
            ;;
            
        "factory_reset")
            # Trigger factory reset (if supported)
            echo "Initiating factory reset for device..."
            trigger_device_factory_reset "$device_id"
            
            # Re-enroll device after reset
            schedule_device_enrollment "$device_id"
            ;;
            
        "firmware_update")
            # Push firmware update to device
            echo "Pushing firmware update to device..."
            push_firmware_update "$device_id"
            ;;
    esac
    
    echo "Device recovery procedure completed"
}
```

This troubleshooting guide provides comprehensive diagnostic procedures and solutions for device identity management issues across diverse device types and deployment scenarios.