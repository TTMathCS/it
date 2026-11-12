# Code Signing Performance Metrics

## Overview

This document establishes performance benchmarks, monitoring methodologies, and optimization strategies for code signing systems. Performance metrics are essential for ensuring efficient software development workflows and identifying optimization opportunities in PKI-based code signing infrastructure.

## Performance Baseline Metrics

### Code Signing Operation Performance

#### RSA vs ECC Signing Performance
```python
import time
import statistics
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import hashes, serialization

def benchmark_signing_algorithms(iterations=100):
    """
    Benchmark RSA vs ECC signing performance for code signing
    """
    # RSA 3072-bit key generation and signing
    rsa_times = []
    rsa_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=3072
    )
    
    test_data = b"Sample code to be signed"
    
    for _ in range(iterations):
        start_time = time.perf_counter()
        signature = rsa_key.sign(
            test_data,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        end_time = time.perf_counter()
        rsa_times.append((end_time - start_time) * 1000)
    
    # ECDSA P-384 signing
    ecc_times = []
    ecc_key = ec.generate_private_key(ec.SECP384R1())
    
    for _ in range(iterations):
        start_time = time.perf_counter()
        signature = ecc_key.sign(
            test_data,
            ec.ECDSA(hashes.SHA256())
        )
        end_time = time.perf_counter()
        ecc_times.append((end_time - start_time) * 1000)
    
    return {
        "rsa_3072": {
            "mean_ms": statistics.mean(rsa_times),
            "p95_ms": sorted(rsa_times)[int(0.95 * len(rsa_times))],
            "std_dev": statistics.stdev(rsa_times)
        },
        "ecdsa_p384": {
            "mean_ms": statistics.mean(ecc_times),
            "p95_ms": sorted(ecc_times)[int(0.95 * len(ecc_times))],
            "std_dev": statistics.stdev(ecc_times)
        }
    }

# Expected baseline performance on modern hardware
BASELINE_SIGNING_PERFORMANCE = {
    "rsa_3072": {"mean_ms": 15, "p95_ms": 25},
    "ecdsa_p384": {"mean_ms": 3, "p95_ms": 8}
}
```

### HSM Performance Characteristics
```python
def benchmark_hsm_operations():
    """
    Benchmark HSM-based code signing operations
    """
    hsm_metrics = {
        "key_generation": {
            "rsa_3072": {"mean_seconds": 45, "p95_seconds": 65},
            "ecdsa_p384": {"mean_seconds": 8, "p95_seconds": 15}
        },
        "signing_operations": {
            "rsa_3072": {"mean_ms": 150, "p95_ms": 250},
            "ecdsa_p384": {"mean_ms": 45, "p95_ms": 80}
        },
        "certificate_storage": {
            "max_certificates": 1000,
            "lookup_time_ms": {"mean": 5, "p95": 12}
        },
        "concurrent_operations": {
            "max_simultaneous": 10,
            "degradation_factor": 1.2  # 20% slower per additional operation
        }
    }
    
    return hsm_metrics
```

## Build System Performance Integration

### CI/CD Pipeline Metrics
```bash
#!/bin/bash
# measure_build_performance.sh

measure_signing_impact() {
    local build_without_signing
    local build_with_signing
    
    echo "=== Code Signing Performance Impact Analysis ==="
    
    # Measure build time without signing
    start_time=$(date +%s.%N)
    make clean && make build
    end_time=$(date +%s.%N)
    build_without_signing=$(echo "$end_time - $start_time" | bc -l)
    
    echo "Build without signing: ${build_without_signing}s"
    
    # Measure build time with signing
    start_time=$(date +%s.%N)
    make clean && make build && make sign
    end_time=$(date +%s.%N)
    build_with_signing=$(echo "$end_time - $start_time" | bc -l)
    
    echo "Build with signing: ${build_with_signing}s"
    
    # Calculate overhead
    overhead=$(echo "$build_with_signing - $build_without_signing" | bc -l)
    percentage=$(echo "scale=2; ($overhead / $build_without_signing) * 100" | bc -l)
    
    echo "Signing overhead: ${overhead}s (${percentage}%)"
    
    # Performance thresholds
    if (( $(echo "$percentage > 20" | bc -l) )); then
        echo "WARNING: Signing overhead exceeds 20% threshold"
    fi
}

measure_signing_impact
```

### Timestamp Authority Response Times
```python
def monitor_tsa_performance():
    """
    Monitor timestamp authority response times
    """
    import requests
    import time
    
    tsa_endpoints = [
        "http://timestamp.company.com:8080/tsa",
        "http://timestamp.digicert.com",
        "http://timestamp.comodoca.com"
    ]
    
    performance_data = {}
    
    for endpoint in tsa_endpoints:
        response_times = []
        
        for _ in range(10):
            start_time = time.perf_counter()
            try:
                response = requests.get(endpoint, timeout=10)
                end_time = time.perf_counter()
                response_times.append((end_time - start_time) * 1000)
            except requests.RequestException:
                response_times.append(10000)  # 10 second timeout
        
        performance_data[endpoint] = {
            "mean_ms": sum(response_times) / len(response_times),
            "max_ms": max(response_times),
            "availability": len([t for t in response_times if t < 10000]) / 10
        }
    
    return performance_data
```

## Performance Monitoring and Alerting

### Real-time Performance Monitoring
```python
def setup_performance_monitoring():
    """
    Configure performance monitoring for code signing operations
    """
    monitoring_config = {
        "signing_operation_metrics": {
            "response_time_threshold_ms": 1000,
            "error_rate_threshold_percent": 5,
            "throughput_threshold_ops_per_minute": 60
        },
        "hsm_metrics": {
            "connection_timeout_ms": 5000,
            "key_operation_timeout_ms": 30000,
            "health_check_interval_seconds": 60
        },
        "certificate_validation_metrics": {
            "chain_validation_threshold_ms": 500,
            "crl_check_threshold_ms": 2000,
            "ocsp_response_threshold_ms": 1000
        },
        "build_system_metrics": {
            "signing_step_timeout_minutes": 10,
            "queue_depth_threshold": 20,
            "failure_rate_threshold_percent": 2
        }
    }
    
    alert_conditions = {
        "critical": [
            "signing_failures > 10% in 5 minutes",
            "hsm_unavailable > 30 seconds",
            "certificate_expired"
        ],
        "warning": [
            "signing_time > 30 seconds",
            "tsa_response_time > 10 seconds",
            "queue_depth > 50% capacity"
        ]
    }
    
    return {"config": monitoring_config, "alerts": alert_conditions}
```

### Performance Dashboard Metrics
```bash
#!/bin/bash
# generate_performance_dashboard.sh

generate_dashboard_data() {
    local output_file="/var/www/html/signing_dashboard.json"
    
    cat > "$output_file" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "signing_operations": {
        "total_today": $(grep "SIGN_SUCCESS" /var/log/codesign.log | wc -l),
        "average_time_ms": $(awk '/signing_time/ {sum+=$3; count++} END {print (count>0 ? sum/count : 0)}' /var/log/codesign.log),
        "success_rate": "$(awk 'BEGIN{s=0;f=0} /SIGN_SUCCESS/{s++} /SIGN_FAILED/{f++} END{print (s+f>0 ? s/(s+f)*100 : 0)}' /var/log/codesign.log)%"
    },
    "hsm_status": {
        "connected": $(systemctl is-active hsm-service >/dev/null && echo "true" || echo "false"),
        "key_operations_per_hour": $(grep "HSM_KEY_OP" /var/log/hsm.log | wc -l),
        "error_rate": "$(grep -c "HSM_ERROR" /var/log/hsm.log)%"
    },
    "certificate_status": {
        "valid_certificates": $(find /opt/certificates -name "*.pem" -exec openssl x509 -in {} -noout -checkend 86400 \; 2>/dev/null | grep -c "not expire"),
        "expiring_soon": $(find /opt/certificates -name "*.pem" -exec openssl x509 -in {} -noout -checkend 2592000 \; 2>/dev/null | grep -c "will expire")
    }
}
EOF
    
    echo "Dashboard data generated: $output_file"
}

generate_dashboard_data
```

## Optimization Strategies

### Performance Tuning Recommendations
```python
def analyze_performance_bottlenecks():
    """
    Analyze and provide recommendations for performance optimization
    """
    optimization_strategies = {
        "algorithm_selection": {
            "recommendation": "Use ECDSA P-384 instead of RSA 3072-bit for 5x speed improvement",
            "expected_improvement": "80% faster signing operations",
            "implementation_effort": "Medium"
        },
        "hsm_optimization": {
            "recommendation": "Implement connection pooling and session reuse",
            "expected_improvement": "50% reduction in connection overhead",
            "implementation_effort": "High"
        },
        "certificate_caching": {
            "recommendation": "Cache certificate chain validation results",
            "expected_improvement": "70% faster validation for repeated operations",
            "implementation_effort": "Low"
        },
        "parallel_signing": {
            "recommendation": "Sign multiple files concurrently",
            "expected_improvement": "3-5x throughput increase",
            "implementation_effort": "Medium"
        },
        "local_timestamp_authority": {
            "recommendation": "Deploy internal TSA to reduce network latency",
            "expected_improvement": "90% reduction in timestamp delays",
            "implementation_effort": "High"
        }
    }
    
    return optimization_strategies
```

### Load Testing and Capacity Planning
```bash
#!/bin/bash
# load_test_code_signing.sh

run_load_test() {
    local concurrent_jobs=10
    local test_duration=300  # 5 minutes
    
    echo "=== Code Signing Load Test ==="
    echo "Concurrent jobs: $concurrent_jobs"
    echo "Test duration: $test_duration seconds"
    
    # Create test files
    mkdir -p /tmp/load_test
    for i in $(seq 1 100); do
        dd if=/dev/zero of="/tmp/load_test/test_$i.exe" bs=1M count=1 2>/dev/null
    done
    
    # Start load test
    start_time=$(date +%s)
    end_time=$((start_time + test_duration))
    
    signed_count=0
    failed_count=0
    
    while [[ $(date +%s) -lt $end_time ]]; do
        for job in $(seq 1 $concurrent_jobs); do
            {
                file="/tmp/load_test/test_$((RANDOM % 100 + 1)).exe"
                if signtool sign /fd SHA256 "$file" >/dev/null 2>&1; then
                    ((signed_count++))
                else
                    ((failed_count++))
                fi
            } &
        done
        wait
        sleep 1
    done
    
    # Calculate results
    total_operations=$((signed_count + failed_count))
    ops_per_second=$(echo "scale=2; $total_operations / $test_duration" | bc)
    success_rate=$(echo "scale=2; $signed_count * 100 / $total_operations" | bc)
    
    echo "Results:"
    echo "  Total operations: $total_operations"
    echo "  Operations/second: $ops_per_second"
    echo "  Success rate: $success_rate%"
    echo "  Failed operations: $failed_count"
    
    # Cleanup
    rm -rf /tmp/load_test
}

run_load_test
```

## Performance Benchmarking Results

### Expected Performance Baselines

| Operation | RSA 3072 | ECDSA P-384 | HSM RSA | HSM ECDSA |
|-----------|----------|-------------|---------|-----------|
| Key Generation | 2000ms | 50ms | 45000ms | 8000ms |
| Signing Operation | 15ms | 3ms | 150ms | 45ms |
| Verification | 2ms | 8ms | N/A | N/A |
| Certificate Chain Validation | 5ms | 5ms | 5ms | 5ms |

### Throughput Expectations

| Scenario | Operations/Minute | Concurrent Limit |
|----------|------------------|------------------|
| Single-threaded Signing | 240 (RSA) / 1200 (ECDSA) | 1 |
| Multi-threaded Signing | 800 (RSA) / 3600 (ECDSA) | 4 |
| HSM-based Signing | 60 (RSA) / 180 (ECDSA) | 10 |
| Build Pipeline Integration | 30 (including validation) | 5 |

This performance metrics framework enables comprehensive monitoring and optimization of code signing infrastructure to maintain efficient software development workflows.