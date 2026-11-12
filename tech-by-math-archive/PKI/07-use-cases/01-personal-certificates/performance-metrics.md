# Personal Certificates Performance Metrics

## Overview

This document establishes performance benchmarks, monitoring methodologies, and optimization strategies for personal certificate management systems. Performance metrics are critical for ensuring user experience quality and identifying optimization opportunities.

## Performance Baseline Metrics

### Key Generation Performance

#### Elliptic Curve (P-256) Key Generation
```python
import time
import statistics
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

def benchmark_ec_key_generation(iterations=1000):
    """
    Benchmark elliptic curve key generation performance
    """
    times = []
    
    for _ in range(iterations):
        start_time = time.perf_counter()
        private_key = ec.generate_private_key(ec.SECP256R1())
        end_time = time.perf_counter()
        times.append((end_time - start_time) * 1000)  # Convert to milliseconds
    
    return {
        "algorithm": "ECDSA P-256",
        "iterations": iterations,
        "mean_time_ms": statistics.mean(times),
        "median_time_ms": statistics.median(times),
        "std_dev_ms": statistics.stdev(times),
        "min_time_ms": min(times),
        "max_time_ms": max(times),
        "p95_time_ms": sorted(times)[int(0.95 * len(times))]
    }

# Expected baseline performance on modern hardware
BASELINE_EC_PERFORMANCE = {
    "mean_time_ms": 2.5,
    "p95_time_ms": 4.0,
    "hardware_spec": "Intel Core i5-8400, 8GB RAM"
}
```

#### RSA Key Generation
```python
def benchmark_rsa_key_generation(key_sizes=[2048, 3072, 4096], iterations=100):
    """
    Benchmark RSA key generation across different key sizes
    """
    from cryptography.hazmat.primitives.asymmetric import rsa
    
    results = {}
    
    for key_size in key_sizes:
        times = []
        
        for _ in range(iterations):
            start_time = time.perf_counter()
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)
        
        results[f"RSA-{key_size}"] = {
            "mean_time_ms": statistics.mean(times),
            "p95_time_ms": sorted(times)[int(0.95 * len(times))],
            "iterations": iterations
        }
    
    return results

# Expected baseline performance
BASELINE_RSA_PERFORMANCE = {
    "RSA-2048": {"mean_time_ms": 45, "p95_time_ms": 65},
    "RSA-3072": {"mean_time_ms": 180, "p95_time_ms": 250},
    "RSA-4096": {"mean_time_ms": 450, "p95_time_ms": 600}
}
```

### Certificate Operations Performance

#### Certificate Chain Validation
```python
def benchmark_certificate_validation(chain_lengths=[1, 2, 3, 4, 5], iterations=500):
    """
    Benchmark certificate chain validation performance
    """
    import subprocess
    import tempfile
    import os
    
    results = {}
    
    for chain_length in chain_lengths:
        times = []
        
        # Create test certificate chain
        test_chain = create_test_certificate_chain(chain_length)
        
        for _ in range(iterations):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                f.write(test_chain)
                chain_file = f.name
            
            try:
                start_time = time.perf_counter()
                result = subprocess.run([
                    'openssl', 'verify', '-CAfile', 'ca_bundle.pem', chain_file
                ], capture_output=True, text=True)
                end_time = time.perf_counter()
                
                if result.returncode == 0:
                    times.append((end_time - start_time) * 1000)
            finally:
                os.unlink(chain_file)
        
        if times:
            results[f"chain_length_{chain_length}"] = {
                "mean_time_ms": statistics.mean(times),
                "p95_time_ms": sorted(times)[int(0.95 * len(times))],
                "successful_validations": len(times)
            }
    
    return results

# Expected baseline validation performance
BASELINE_VALIDATION_PERFORMANCE = {
    "chain_length_1": {"mean_time_ms": 15, "p95_time_ms": 25},
    "chain_length_2": {"mean_time_ms": 28, "p95_time_ms": 40},
    "chain_length_3": {"mean_time_ms": 42, "p95_time_ms": 60},
    "chain_length_4": {"mean_time_ms": 55, "p95_time_ms": 80}
}
```

#### S/MIME Operations
```python
def benchmark_smime_operations(message_sizes=[1024, 10240, 102400], iterations=100):
    """
    Benchmark S/MIME signing and verification operations
    """
    results = {
        "signing": {},
        "verification": {}
    }
    
    for size in message_sizes:
        test_message = "A" * size
        
        # Benchmark signing
        signing_times = []
        signed_messages = []
        
        for _ in range(iterations):
            start_time = time.perf_counter()
            signed_msg = sign_smime_message(test_message)
            end_time = time.perf_counter()
            
            signing_times.append((end_time - start_time) * 1000)
            signed_messages.append(signed_msg)
        
        results["signing"][f"{size}_bytes"] = {
            "mean_time_ms": statistics.mean(signing_times),
            "throughput_kb_s": (size * iterations) / (sum(signing_times) / 1000) / 1024
        }
        
        # Benchmark verification
        verification_times = []
        
        for signed_msg in signed_messages[:iterations]:
            start_time = time.perf_counter()
            verify_smime_signature(signed_msg)
            end_time = time.perf_counter()
            
            verification_times.append((end_time - start_time) * 1000)
        
        results["verification"][f"{size}_bytes"] = {
            "mean_time_ms": statistics.mean(verification_times),
            "throughput_kb_s": (size * len(verification_times)) / (sum(verification_times) / 1000) / 1024
        }
    
    return results
```

### Certificate Store Operations

#### Certificate Lookup Performance
```python
def benchmark_certificate_store_operations():
    """
    Benchmark certificate store lookup and enumeration operations
    """
    import platform
    
    if platform.system() == "Windows":
        return benchmark_windows_certstore()
    elif platform.system() == "Darwin":
        return benchmark_macos_keychain()
    else:
        return benchmark_nss_database()

def benchmark_windows_certstore():
    """
    Windows Certificate Store performance benchmarks
    """
    import win32crypt
    import pywintypes
    
    store_types = [
        ("MY", "Personal certificates"),
        ("CA", "Certificate authorities"), 
        ("ROOT", "Trusted root certificates")
    ]
    
    results = {}
    
    for store_name, description in store_types:
        times = []
        cert_counts = []
        
        for _ in range(50):  # 50 iterations
            start_time = time.perf_counter()
            
            try:
                store = win32crypt.CertOpenSystemStore(0, store_name)
                cert_count = 0
                
                # Enumerate all certificates
                cert = win32crypt.CertEnumCertificatesInStore(store, None)
                while cert:
                    cert_count += 1
                    cert = win32crypt.CertEnumCertificatesInStore(store, cert)
                
                win32crypt.CertCloseStore(store, 0)
                
            except pywintypes.error:
                continue
            
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)
            cert_counts.append(cert_count)
        
        if times:
            results[store_name] = {
                "description": description,
                "mean_enumeration_time_ms": statistics.mean(times),
                "average_cert_count": statistics.mean(cert_counts),
                "time_per_cert_ms": statistics.mean(times) / max(statistics.mean(cert_counts), 1)
            }
    
    return results
```

## Performance Monitoring Framework

### Real-time Performance Monitoring
```python
class PersonalCertificatePerformanceMonitor:
    """
    Real-time performance monitoring for personal certificate operations
    """
    
    def __init__(self):
        self.metrics = {
            "key_generation": [],
            "certificate_validation": [],
            "signing_operations": [],
            "store_operations": []
        }
        self.thresholds = {
            "key_generation_ms": 10.0,      # EC key generation
            "validation_ms": 100.0,         # Certificate validation
            "signing_ms": 50.0,            # S/MIME signing
            "store_lookup_ms": 200.0        # Certificate store lookup
        }
    
    def record_operation(self, operation_type, duration_ms, success=True):
        """
        Record performance metrics for certificate operations
        """
        metric_data = {
            "timestamp": time.time(),
            "duration_ms": duration_ms,
            "success": success,
            "thread_id": threading.current_thread().ident
        }
        
        self.metrics[operation_type].append(metric_data)
        
        # Check for performance degradation
        if duration_ms > self.thresholds.get(f"{operation_type}_ms", float('inf')):
            self.alert_performance_degradation(operation_type, duration_ms)
    
    def get_performance_summary(self, time_window_minutes=60):
        """
        Get performance summary for specified time window
        """
        current_time = time.time()
        window_start = current_time - (time_window_minutes * 60)
        
        summary = {}
        
        for operation_type, measurements in self.metrics.items():
            # Filter measurements within time window
            recent_measurements = [
                m for m in measurements 
                if m["timestamp"] >= window_start and m["success"]
            ]
            
            if recent_measurements:
                durations = [m["duration_ms"] for m in recent_measurements]
                summary[operation_type] = {
                    "count": len(recent_measurements),
                    "mean_duration_ms": statistics.mean(durations),
                    "p95_duration_ms": sorted(durations)[int(0.95 * len(durations))],
                    "success_rate": len([m for m in recent_measurements if m["success"]]) / len(recent_measurements)
                }
        
        return summary
    
    def detect_performance_anomalies(self):
        """
        Detect performance anomalies using statistical analysis
        """
        anomalies = []
        
        for operation_type, measurements in self.metrics.items():
            if len(measurements) < 30:  # Need sufficient data
                continue
            
            recent_measurements = measurements[-30:]  # Last 30 operations
            durations = [m["duration_ms"] for m in recent_measurements if m["success"]]
            
            if len(durations) < 10:
                continue
            
            # Calculate z-score for latest measurements
            mean_duration = statistics.mean(durations)
            std_dev = statistics.stdev(durations) if len(durations) > 1 else 0
            
            if std_dev > 0:
                latest_durations = durations[-5:]  # Last 5 operations
                for duration in latest_durations:
                    z_score = abs(duration - mean_duration) / std_dev
                    if z_score > 2.0:  # More than 2 standard deviations
                        anomalies.append({
                            "operation_type": operation_type,
                            "duration_ms": duration,
                            "z_score": z_score,
                            "severity": "high" if z_score > 3.0 else "medium"
                        })
        
        return anomalies
```

### Performance Dashboard
```python
def generate_performance_dashboard(monitor, output_format="text"):
    """
    Generate performance dashboard with key metrics
    """
    summary = monitor.get_performance_summary()
    anomalies = monitor.detect_performance_anomalies()
    
    dashboard_data = {
        "timestamp": datetime.now().isoformat(),
        "performance_summary": summary,
        "anomalies": anomalies,
        "health_score": calculate_health_score(summary),
        "recommendations": generate_performance_recommendations(summary, anomalies)
    }
    
    if output_format == "json":
        return json.dumps(dashboard_data, indent=2)
    else:
        return format_text_dashboard(dashboard_data)

def calculate_health_score(performance_summary):
    """
    Calculate overall performance health score (0-100)
    """
    scores = []
    
    thresholds = {
        "key_generation": 10.0,
        "certificate_validation": 100.0,
        "signing_operations": 50.0,
        "store_operations": 200.0
    }
    
    for operation_type, metrics in performance_summary.items():
        threshold = thresholds.get(operation_type, 100.0)
        actual = metrics.get("p95_duration_ms", threshold)
        
        # Score: 100 when at/below threshold, decreasing as performance degrades
        score = max(0, 100 - ((actual - threshold) / threshold) * 50)
        scores.append(score)
    
    return statistics.mean(scores) if scores else 50
```

## Optimization Strategies

### Algorithm Selection Optimization
```python
def optimize_algorithm_selection(use_case_requirements):
    """
    Select optimal cryptographic algorithms based on use case requirements
    """
    recommendations = {}
    
    # Key generation algorithm selection
    if use_case_requirements.get("performance_critical", False):
        if use_case_requirements.get("security_level") == "high":
            recommendations["key_algorithm"] = "ECDSA P-384"
            recommendations["expected_keygen_time_ms"] = 8
        else:
            recommendations["key_algorithm"] = "ECDSA P-256"
            recommendations["expected_keygen_time_ms"] = 3
    else:
        if use_case_requirements.get("long_term_validity", False):
            recommendations["key_algorithm"] = "RSA 3072"
            recommendations["expected_keygen_time_ms"] = 200
        else:
            recommendations["key_algorithm"] = "RSA 2048"
            recommendations["expected_keygen_time_ms"] = 50
    
    # Signature algorithm selection
    signature_algorithms = {
        "ECDSA P-256": "SHA256withECDSA",
        "ECDSA P-384": "SHA384withECDSA", 
        "RSA 2048": "SHA256withRSA",
        "RSA 3072": "SHA256withRSA"
    }
    
    recommendations["signature_algorithm"] = signature_algorithms[recommendations["key_algorithm"]]
    
    return recommendations
```

### Hardware Acceleration
```python
def detect_hardware_acceleration():
    """
    Detect available hardware acceleration capabilities
    """
    capabilities = {
        "aes_ni": False,
        "rdrand": False,
        "tpm_available": False,
        "pkcs11_tokens": []
    }
    
    # Check for AES-NI support
    try:
        import cpuinfo
        cpu_flags = cpuinfo.get_cpu_info().get('flags', [])
        capabilities["aes_ni"] = 'aes' in cpu_flags
        capabilities["rdrand"] = 'rdrand' in cpu_flags
    except ImportError:
        pass
    
    # Check for TPM
    try:
        import subprocess
        result = subprocess.run(['tpm2_getcap', 'properties-fixed'], 
                              capture_output=True, text=True)
        capabilities["tpm_available"] = result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Check for PKCS#11 tokens
    try:
        import PyKCS11
        pkcs11 = PyKCS11.PyKCS11Lib()
        pkcs11.load()  # Load default library
        slots = pkcs11.getSlotList()
        for slot in slots:
            token_info = pkcs11.getTokenInfo(slot)
            capabilities["pkcs11_tokens"].append({
                "slot": slot,
                "label": token_info.label.strip(),
                "manufacturer": token_info.manufacturerID.strip()
            })
    except (ImportError, Exception):
        pass
    
    return capabilities

def optimize_for_hardware(capabilities):
    """
    Optimize performance based on available hardware capabilities
    """
    optimizations = []
    
    if capabilities["aes_ni"]:
        optimizations.append({
            "feature": "AES-NI",
            "recommendation": "Use AES encryption for key protection",
            "expected_improvement": "3-5x faster symmetric encryption"
        })
    
    if capabilities["rdrand"]:
        optimizations.append({
            "feature": "RDRAND",
            "recommendation": "Use hardware random number generator",
            "expected_improvement": "Higher entropy, faster key generation"
        })
    
    if capabilities["tpm_available"]:
        optimizations.append({
            "feature": "TPM",
            "recommendation": "Store private keys in TPM",
            "expected_improvement": "Hardware-backed key protection"
        })
    
    if capabilities["pkcs11_tokens"]:
        for token in capabilities["pkcs11_tokens"]:
            optimizations.append({
                "feature": f"PKCS#11 Token: {token['label']}",
                "recommendation": "Use hardware token for key operations",
                "expected_improvement": "Hardware-backed cryptographic operations"
            })
    
    return optimizations
```

### Performance Tuning Guidelines

#### Memory Optimization
```bash
#!/bin/bash
# Memory optimization for certificate operations

# Set appropriate OpenSSL memory limits
export OPENSSL_malloc_fd=1
export OPENSSL_malloc_init=1

# Configure certificate store caching
echo "Optimizing certificate store cache..."

# Windows Certificate Store optimization
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Enable certificate store caching
    reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography\OID\EncodingType 0\CertDllCreateCertificateChainEngine\Config" /v MaxCachedCertificates /t REG_DWORD /d 1000 /f
fi

# Firefox NSS database optimization
if [[ -d "$HOME/.mozilla/firefox" ]]; then
    for profile in "$HOME/.mozilla/firefox"/*.default*/; do
        if [[ -f "$profile/cert9.db" ]]; then
            echo "Optimizing NSS database: $profile"
            # Vacuum NSS database to optimize performance
            sqlite3 "$profile/cert9.db" "VACUUM;"
        fi
    done
fi
```

#### Network Optimization
```python
def optimize_network_operations():
    """
    Optimize network operations for certificate-related activities
    """
    optimizations = {
        "ocsp_optimization": {
            "enable_ocsp_stapling": True,
            "ocsp_cache_timeout": 3600,  # 1 hour
            "ocsp_responder_timeout": 10  # 10 seconds
        },
        "crl_optimization": {
            "enable_crl_caching": True,
            "crl_cache_duration": 86400,  # 24 hours
            "delta_crl_support": True
        },
        "ca_certificate_optimization": {
            "ca_bundle_caching": True,
            "ca_bundle_update_interval": 604800,  # 7 days
            "prefer_local_ca_bundles": True
        }
    }
    
    return optimizations

def implement_connection_pooling():
    """
    Implement connection pooling for CA communications
    """
    import urllib3
    
    # Configure connection pooling for CA APIs
    http = urllib3.PoolManager(
        num_pools=5,
        maxsize=10,
        retries=urllib3.Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
    )
    
    return http
```

## Performance Testing Framework

### Automated Performance Testing
```python
def automated_performance_test_suite():
    """
    Comprehensive automated performance test suite
    """
    test_results = {}
    
    # Test 1: Key Generation Performance
    print("Testing key generation performance...")
    test_results["key_generation"] = {
        "ec_p256": benchmark_ec_key_generation(),
        "rsa_2048": benchmark_rsa_key_generation([2048])[0]
    }
    
    # Test 2: Certificate Operations
    print("Testing certificate operations...")
    test_results["certificate_operations"] = benchmark_certificate_validation()
    
    # Test 3: S/MIME Operations
    print("Testing S/MIME operations...")
    test_results["smime_operations"] = benchmark_smime_operations()
    
    # Test 4: Store Operations
    print("Testing certificate store operations...")
    test_results["store_operations"] = benchmark_certificate_store_operations()
    
    # Generate performance report
    generate_performance_report(test_results)
    
    return test_results

def generate_performance_report(test_results):
    """
    Generate comprehensive performance report
    """
    report = f"""
# Personal Certificate Performance Test Report

Generated: {datetime.now().isoformat()}

## Key Generation Performance
- ECDSA P-256: {test_results['key_generation']['ec_p256']['mean_time_ms']:.2f}ms (mean)
- RSA 2048: {test_results['key_generation']['rsa_2048']['mean_time_ms']:.2f}ms (mean)

## Certificate Validation Performance
- Chain Length 1: {test_results['certificate_operations']['chain_length_1']['mean_time_ms']:.2f}ms
- Chain Length 3: {test_results['certificate_operations']['chain_length_3']['mean_time_ms']:.2f}ms

## Recommendations
{generate_optimization_recommendations(test_results)}
"""
    
    with open("performance_report.md", "w") as f:
        f.write(report)
    
    return report
```

This comprehensive performance metrics framework provides the tools and methodologies needed to monitor, analyze, and optimize personal certificate system performance.