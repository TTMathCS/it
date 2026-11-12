# Web Authentication PKI Deployment Guide

## Overview

This guide covers the deployment of PKI infrastructure for secure web authentication using SSL/TLS certificates. It addresses server certificate deployment, client certificate authentication, and browser integration for comprehensive web security.

## SSL/TLS Server Certificate Deployment

### Certificate Requirements
```python
def web_server_cert_requirements():
    return {
        "certificate_type": "Domain Validated (DV) or Extended Validation (EV)",
        "key_algorithm": "RSA 2048-bit or ECDSA P-256",
        "validity_period": "1-2 years maximum",
        "subject_alternative_names": ["www.example.com", "api.example.com"],
        "key_usage": ["digitalSignature", "keyEncipherment"],
        "extended_key_usage": ["serverAuth"],
        "certificate_transparency": "Required for public CAs"
    }
```

### Automated Certificate Deployment
```bash
#!/bin/bash
# deploy_web_certificates.sh

DOMAIN="$1"
WEBSERVER="$2"  # nginx, apache, haproxy

echo "=== Web Certificate Deployment ==="

# Generate private key
generate_private_key() {
    echo "Generating private key for $DOMAIN..."
    openssl genpkey -algorithm RSA -out "/etc/ssl/private/${DOMAIN}.key" -pkcs8 -aes256
    chmod 400 "/etc/ssl/private/${DOMAIN}.key"
}

# Generate CSR
generate_csr() {
    echo "Generating certificate signing request..."
    openssl req -new -key "/etc/ssl/private/${DOMAIN}.key" \
        -out "/tmp/${DOMAIN}.csr" \
        -subj "/CN=${DOMAIN}/O=Organization/C=US" \
        -config <(
        echo '[req]'
        echo 'distinguished_name = req_distinguished_name'
        echo 'req_extensions = v3_req'
        echo '[req_distinguished_name]'
        echo '[v3_req]'
        echo 'keyUsage = keyEncipherment, dataEncipherment'
        echo 'extendedKeyUsage = serverAuth'
        echo "subjectAltName = @alt_names"
        echo '[alt_names]'
        echo "DNS.1 = ${DOMAIN}"
        echo "DNS.2 = www.${DOMAIN}"
        )
}

# Configure web server
configure_webserver() {
    case "$WEBSERVER" in
        "nginx")
            cat > "/etc/nginx/sites-available/${DOMAIN}" << EOF
server {
    listen 443 ssl http2;
    server_name ${DOMAIN} www.${DOMAIN};
    
    ssl_certificate /etc/ssl/certs/${DOMAIN}.pem;
    ssl_certificate_key /etc/ssl/private/${DOMAIN}.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
    
    location / {
        root /var/www/${DOMAIN};
        index index.html;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    return 301 https://\$server_name\$request_uri;
}
EOF
            nginx -t && systemctl reload nginx
            ;;
        "apache")
            cat > "/etc/apache2/sites-available/${DOMAIN}.conf" << EOF
<VirtualHost *:443>
    ServerName ${DOMAIN}
    ServerAlias www.${DOMAIN}
    DocumentRoot /var/www/${DOMAIN}
    
    SSLEngine on
    SSLCertificateFile /etc/ssl/certs/${DOMAIN}.pem
    SSLCertificateKeyFile /etc/ssl/private/${DOMAIN}.key
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256
    
    Header always set Strict-Transport-Security "max-age=63072000"
</VirtualHost>

<VirtualHost *:80>
    ServerName ${DOMAIN}
    ServerAlias www.${DOMAIN}
    Redirect permanent / https://${DOMAIN}/
</VirtualHost>
EOF
            apache2ctl configtest && systemctl reload apache2
            ;;
    esac
}

generate_private_key
generate_csr
echo "Submit CSR to Certificate Authority, then install issued certificate"
echo "After certificate installation, run: configure_webserver"
```

## Client Certificate Authentication

### Client Certificate Setup
```bash
#!/bin/bash
# setup_client_cert_auth.sh

echo "=== Client Certificate Authentication Setup ==="

# Configure Nginx for client certificate authentication
configure_nginx_client_auth() {
    cat >> /etc/nginx/sites-available/secure-site << 'EOF'
server {
    listen 443 ssl;
    server_name secure.example.com;
    
    # Server certificate
    ssl_certificate /etc/ssl/certs/server.pem;
    ssl_certificate_key /etc/ssl/private/server.key;
    
    # Client certificate authentication
    ssl_client_certificate /etc/ssl/certs/client-ca.pem;
    ssl_verify_client on;
    ssl_verify_depth 2;
    
    location / {
        # Pass client certificate info to backend
        proxy_set_header X-SSL-Client-Verify $ssl_client_verify;
        proxy_set_header X-SSL-Client-DN $ssl_client_s_dn;
        proxy_set_header X-SSL-Client-Serial $ssl_client_serial;
        
        proxy_pass http://backend;
    }
}
EOF
}

# Test client certificate
test_client_certificate() {
    local client_cert="$1"
    local client_key="$2"
    local server_url="$3"
    
    echo "Testing client certificate authentication..."
    curl -v --cert "$client_cert" --key "$client_key" "$server_url"
}

configure_nginx_client_auth
echo "Client certificate authentication configured"
```

## Certificate Lifecycle Management

### Automated Renewal with ACME
```python
#!/usr/bin/env python3
# acme_renewal.py

import subprocess
import sys
import json
from datetime import datetime, timedelta

class ACMEManager:
    def __init__(self, config_file):
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.certbot_cmd = self.config.get('certbot_path', '/usr/bin/certbot')
        self.domains = self.config.get('domains', [])
        self.webserver = self.config.get('webserver', 'nginx')
    
    def renew_certificates(self):
        """Renew certificates using Certbot/ACME"""
        print("Starting certificate renewal process...")
        
        for domain_config in self.domains:
            domain = domain_config['domain']
            email = domain_config['email']
            
            print(f"Processing domain: {domain}")
            
            # Check if certificate exists and needs renewal
            if self.needs_renewal(domain):
                print(f"Certificate for {domain} needs renewal")
                self.request_certificate(domain, email)
            else:
                print(f"Certificate for {domain} is still valid")
    
    def needs_renewal(self, domain, days_threshold=30):
        """Check if certificate needs renewal"""
        try:
            cert_path = f"/etc/letsencrypt/live/{domain}/cert.pem"
            result = subprocess.run([
                'openssl', 'x509', '-checkend', str(days_threshold * 24 * 3600),
                '-noout', '-in', cert_path
            ], capture_output=True)
            
            return result.returncode != 0
        except Exception as e:
            print(f"Error checking certificate for {domain}: {e}")
            return True
    
    def request_certificate(self, domain, email):
        """Request new certificate via ACME"""
        cmd = [
            self.certbot_cmd, 'certonly',
            '--webroot', '-w', f'/var/www/{domain}',
            '-d', domain, '-d', f'www.{domain}',
            '--email', email,
            '--agree-tos',
            '--non-interactive'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Certificate obtained successfully for {domain}")
                self.reload_webserver()
            else:
                print(f"Certificate request failed for {domain}: {result.stderr}")
        except Exception as e:
            print(f"Error requesting certificate: {e}")
    
    def reload_webserver(self):
        """Reload web server to use new certificates"""
        try:
            subprocess.run(['systemctl', 'reload', self.webserver], check=True)
            print(f"{self.webserver} reloaded successfully")
        except subprocess.CalledProcessError as e:
            print(f"Error reloading {self.webserver}: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: acme_renewal.py <config_file>")
        sys.exit(1)
    
    manager = ACMEManager(sys.argv[1])
    manager.renew_certificates()
```

## Security Configuration

### SSL/TLS Best Practices
```bash
#!/bin/bash
# ssl_security_hardening.sh

echo "=== SSL/TLS Security Hardening ==="

# Generate strong DH parameters
generate_dhparams() {
    echo "Generating DH parameters (this may take a while)..."
    openssl dhparam -out /etc/ssl/certs/dhparams.pem 2048
}

# Configure secure SSL settings for Nginx
configure_nginx_ssl() {
    cat > /etc/nginx/conf.d/ssl.conf << 'EOF'
# SSL Configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;

# OCSP Stapling
ssl_stapling on;
ssl_stapling_verify on;
resolver 8.8.8.8 8.8.4.4 valid=300s;
resolver_timeout 5s;

# Session settings
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 1d;
ssl_session_tickets off;

# DH parameters
ssl_dhparam /etc/ssl/certs/dhparams.pem;

# Security headers
add_header Strict-Transport-Security "max-age=63072000" always;
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
EOF
}

generate_dhparams
configure_nginx_ssl
echo "SSL security hardening complete"
```

## Monitoring and Validation

### Certificate Monitoring
```bash
#!/bin/bash
# monitor_web_certificates.sh

echo "=== Web Certificate Monitoring ==="

DOMAINS_FILE="/etc/ssl/domains.txt"
LOG_FILE="/var/log/cert_monitor.log"

# Check certificate expiration
check_certificate_expiration() {
    while read -r domain; do
        echo "Checking certificate for $domain..."
        
        # Get certificate expiration
        expiry_date=$(echo | openssl s_client -servername "$domain" \
            -connect "$domain:443" 2>/dev/null | \
            openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
        
        if [ -n "$expiry_date" ]; then
            expiry_epoch=$(date -d "$expiry_date" +%s)
            current_epoch=$(date +%s)
            days_remaining=$(( (expiry_epoch - current_epoch) / 86400 ))
            
            echo "$(date): $domain expires in $days_remaining days" >> "$LOG_FILE"
            
            if [ $days_remaining -lt 30 ]; then
                echo "WARNING: Certificate for $domain expires in $days_remaining days"
                # Send alert
                echo "Certificate expiration warning for $domain" | \
                    mail -s "Certificate Expiration Alert" admin@example.com
            fi
        else
            echo "ERROR: Could not retrieve certificate for $domain"
        fi
    done < "$DOMAINS_FILE"
}

# Validate SSL configuration
validate_ssl_config() {
    echo "Validating SSL configuration..."
    
    # Test SSL Labs API (simplified)
    for domain in $(cat "$DOMAINS_FILE"); do
        echo "SSL validation for $domain:"
        
        # Basic SSL test with OpenSSL
        echo | openssl s_client -servername "$domain" \
            -connect "$domain:443" 2>/dev/null | \
            openssl x509 -noout -issuer -subject -dates
        
        # Test cipher suites
        nmap --script ssl-enum-ciphers -p 443 "$domain" 2>/dev/null | \
            grep -E "(TLS|SSL)" | head -5
    done
}

check_certificate_expiration
validate_ssl_config
```

This deployment guide provides comprehensive procedures for implementing secure web authentication using PKI infrastructure with automated management and monitoring capabilities.