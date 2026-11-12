#!/usr/bin/env python3
"""
PKI Certificate Validation Demo

This script demonstrates the core cryptographic operations involved in
PKI certificate validation, including:
- Certificate chain building
- Digital signature verification
- Trust anchor validation
- Revocation checking simulation

Author: PKI Tech-by-Math Project
Date: 2025-08-25
"""

import hashlib
import hmac
import base64
import json
from datetime import datetime, timezone, timedelta
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.backends import default_backend
import secrets

class PKIDemoError(Exception):
    """Custom exception for PKI demo errors"""
    pass

class CertificateGenerator:
    """Generate demo certificates for PKI validation experiments"""
    
    def __init__(self):
        self.backend = default_backend()
    
    def generate_key_pair(self, key_size=2048):
        """Generate RSA key pair"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=self.backend
        )
        return private_key, private_key.public_key()
    
    def create_root_ca(self, common_name="Demo Root CA"):
        """Create self-signed root CA certificate"""
        private_key, public_key = self.generate_key_pair(4096)
        
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PKI Demo Organization"),
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            public_key
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=7300)  # 20 years
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=True,
                crl_sign=True,
                digital_signature=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True,
        ).sign(private_key, hashes.SHA256(), self.backend)
        
        return cert, private_key
    
    def create_intermediate_ca(self, issuer_cert, issuer_key, common_name="Demo Intermediate CA"):
        """Create intermediate CA certificate"""
        private_key, public_key = self.generate_key_pair(2048)
        
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PKI Demo Organization"),
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer_cert.subject
        ).public_key(
            public_key
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=3650)  # 10 years
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=True,
                crl_sign=True,
                digital_signature=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True,
        ).sign(issuer_key, hashes.SHA256(), self.backend)
        
        return cert, private_key
    
    def create_end_entity_cert(self, issuer_cert, issuer_key, common_name="demo.example.com"):
        """Create end entity certificate"""
        private_key, public_key = self.generate_key_pair(2048)
        
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Demo Company"),
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer_cert.subject
        ).public_key(
            public_key
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=365)  # 1 year
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=False,
                crl_sign=False,
                data_encipherment=False,
                key_agreement=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True,
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(common_name),
                x509.DNSName(f"www.{common_name}"),
            ]),
            critical=False,
        ).sign(issuer_key, hashes.SHA256(), self.backend)
        
        return cert, private_key

class CertificateValidator:
    """Validate certificate chains and demonstrate PKI operations"""
    
    def __init__(self, trust_anchors=None):
        self.trust_anchors = trust_anchors or []
        self.revoked_serials = set()  # Simple CRL simulation
    
    def add_trust_anchor(self, cert):
        """Add root CA to trust store"""
        self.trust_anchors.append(cert)
        print(f"Added trust anchor: {cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value}")
    
    def revoke_certificate(self, serial_number):
        """Simulate certificate revocation"""
        self.revoked_serials.add(serial_number)
        print(f"Revoked certificate with serial: {serial_number}")
    
    def verify_signature(self, cert, issuer_cert):
        """Verify certificate signature using issuer's public key"""
        try:
            issuer_public_key = issuer_cert.public_key()
            
            # Verify the signature
            issuer_public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                cert.signature_hash_algorithm
            )
            return True
        except Exception as e:
            print(f"Signature verification failed: {e}")
            return False
    
    def check_validity_period(self, cert):
        """Check if certificate is within validity period"""
        now = datetime.now(timezone.utc)
        if now < cert.not_valid_before:
            raise PKIDemoError(f"Certificate not yet valid (starts {cert.not_valid_before})")
        if now > cert.not_valid_after:
            raise PKIDemoError(f"Certificate expired (ended {cert.not_valid_after})")
        return True
    
    def check_revocation(self, cert):
        """Check if certificate is revoked (simplified CRL check)"""
        if cert.serial_number in self.revoked_serials:
            raise PKIDemoError(f"Certificate is revoked (serial: {cert.serial_number})")
        return True
    
    def build_certificate_chain(self, end_entity_cert, intermediate_certs):
        """Build certificate chain from end entity to root"""
        chain = [end_entity_cert]
        current_cert = end_entity_cert
        available_certs = list(intermediate_certs)
        
        while not self._is_self_signed(current_cert):
            issuer_cert = None
            
            # Look for issuer in intermediate certificates
            for cert in available_certs:
                if current_cert.issuer == cert.subject:
                    issuer_cert = cert
                    available_certs.remove(cert)
                    break
            
            # Look for issuer in trust anchors
            if not issuer_cert:
                for cert in self.trust_anchors:
                    if current_cert.issuer == cert.subject:
                        issuer_cert = cert
                        break
            
            if not issuer_cert:
                raise PKIDemoError(f"Could not find issuer for: {current_cert.subject}")
            
            chain.append(issuer_cert)
            current_cert = issuer_cert
        
        return chain
    
    def validate_certificate_chain(self, chain):
        """Validate complete certificate chain"""
        print(f"\n=== VALIDATING CERTIFICATE CHAIN ({len(chain)} certificates) ===")
        
        # Check that root is trusted
        root_cert = chain[-1]
        if root_cert not in self.trust_anchors:
            raise PKIDemoError("Chain does not end with trusted root CA")
        
        print(f"✓ Root CA is trusted: {root_cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value}")
        
        # Validate each certificate in the chain
        for i, cert in enumerate(chain):
            cert_name = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            print(f"\nValidating certificate {i+1}/{len(chain)}: {cert_name}")
            
            # Check validity period
            try:
                self.check_validity_period(cert)
                print("  ✓ Certificate is within validity period")
            except PKIDemoError as e:
                print(f"  ✗ Validity check failed: {e}")
                raise
            
            # Check revocation status
            try:
                self.check_revocation(cert)
                print("  ✓ Certificate is not revoked")
            except PKIDemoError as e:
                print(f"  ✗ Revocation check failed: {e}")
                raise
            
            # Verify signature (except for self-signed root)
            if i < len(chain) - 1:  # Not the root certificate
                issuer_cert = chain[i + 1]
                if self.verify_signature(cert, issuer_cert):
                    print("  ✓ Signature verification successful")
                else:
                    raise PKIDemoError("Signature verification failed")
        
        print(f"\n✓ CERTIFICATE CHAIN VALIDATION SUCCESSFUL")
        return True
    
    def _is_self_signed(self, cert):
        """Check if certificate is self-signed"""
        return cert.issuer == cert.subject

def demonstrate_hash_integrity():
    """Demonstrate hash-based integrity verification"""
    print("\n" + "="*60)
    print("HASH INTEGRITY DEMONSTRATION")
    print("="*60)
    
    # Original certificate data
    original_data = b"Certificate: CN=demo.example.com, Valid=2025-2026"
    original_hash = hashlib.sha256(original_data).hexdigest()
    
    print(f"Original data: {original_data.decode()}")
    print(f"SHA-256 hash:  {original_hash}")
    
    # Demonstrate tamper detection
    tampered_data = original_data.replace(b"demo.example.com", b"evil.example.com")
    tampered_hash = hashlib.sha256(tampered_data).hexdigest()
    
    print(f"\nTampered data: {tampered_data.decode()}")
    print(f"SHA-256 hash:  {tampered_hash}")
    
    print(f"\nIntegrity check: {'PASS' if original_hash == tampered_hash else 'FAIL - TAMPERING DETECTED'}")
    
    # Demonstrate avalanche effect
    print(f"\nHash difference visualization:")
    print(f"Original:  {original_hash}")
    print(f"Tampered:  {tampered_hash}")
    
    # Count different bits
    diff_count = sum(bin(int(a, 16) ^ int(b, 16)).count('1') 
                    for a, b in zip(original_hash, tampered_hash))
    print(f"Different bits: {diff_count}/256 ({diff_count/256*100:.1f}%)")

def demonstrate_digital_signatures():
    """Demonstrate digital signature creation and verification"""
    print("\n" + "="*60)
    print("DIGITAL SIGNATURE DEMONSTRATION")
    print("="*60)
    
    # Generate key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    
    # Message to sign
    message = b"This certificate is issued by Demo CA to demo.example.com"
    print(f"Message to sign: {message.decode()}")
    
    # Create digital signature
    signature = private_key.sign(
        message,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    
    print(f"Signature created: {base64.b64encode(signature)[:64].decode()}...")
    
    # Verify signature
    try:
        public_key.verify(
            signature,
            message,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        print("✓ Signature verification: VALID")
    except Exception:
        print("✗ Signature verification: INVALID")
    
    # Demonstrate tamper detection
    tampered_message = message.replace(b"demo.example.com", b"evil.example.com")
    try:
        public_key.verify(
            signature,
            tampered_message,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        print("✗ Tampered message verification: UNEXPECTEDLY VALID")
    except Exception:
        print("✓ Tampered message verification: CORRECTLY REJECTED")

def main():
    """Main demonstration function"""
    print("PKI CERTIFICATE VALIDATION DEMO")
    print("=" * 60)
    print("This demo illustrates core PKI cryptographic operations:")
    print("1. Certificate chain building and validation")
    print("2. Digital signature verification")
    print("3. Hash integrity checking")
    print("4. Trust anchor management")
    print()
    
    try:
        # Initialize components
        generator = CertificateGenerator()
        validator = CertificateValidator()
        
        print("Generating demo certificate hierarchy...")
        
        # Create certificate hierarchy
        root_cert, root_key = generator.create_root_ca("Demo Root CA")
        intermediate_cert, intermediate_key = generator.create_intermediate_ca(
            root_cert, root_key, "Demo Intermediate CA"
        )
        end_entity_cert, end_entity_key = generator.create_end_entity_cert(
            intermediate_cert, intermediate_key, "demo.example.com"
        )
        
        print("✓ Certificate hierarchy generated")
        
        # Add root CA to trust store
        validator.add_trust_anchor(root_cert)
        
        # Build and validate certificate chain
        chain = validator.build_certificate_chain(
            end_entity_cert, [intermediate_cert]
        )
        
        validator.validate_certificate_chain(chain)
        
        # Demonstrate revocation
        print(f"\n{'='*60}")
        print("CERTIFICATE REVOCATION DEMONSTRATION")
        print(f"{'='*60}")
        
        print("Revoking intermediate certificate...")
        validator.revoke_certificate(intermediate_cert.serial_number)
        
        try:
            validator.validate_certificate_chain(chain)
        except PKIDemoError as e:
            print(f"✓ Revocation correctly detected: {e}")
        
        # Additional demonstrations
        demonstrate_hash_integrity()
        demonstrate_digital_signatures()
        
        print(f"\n{'='*60}")
        print("DEMO COMPLETED SUCCESSFULLY")
        print(f"{'='*60}")
        print("Key takeaways:")
        print("• PKI uses mathematical foundations to provide cryptographic security")
        print("• Certificate chains enable scalable trust relationships") 
        print("• Digital signatures provide authenticity and integrity")
        print("• Hash functions enable tamper detection")
        print("• Revocation mechanisms provide immediate security response")
        
    except Exception as e:
        print(f"Demo failed with error: {e}")
        raise

if __name__ == "__main__":
    main()