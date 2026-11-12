# Device Identity Performance Metrics

## Overview

This document establishes performance benchmarks, monitoring methodologies, and optimization strategies for device identity management systems. Performance metrics are critical for ensuring efficient device enrollment, authentication, and lifecycle management in PKI-based device identity infrastructure.

## Performance Baseline Metrics

### Device Enrollment Performance

#### SCEP Enrollment Benchmarks
```python
import time
import statistics
import concurrent.futures

def benchmark_scep_enrollment(concurrent_devices=10, total_devices=100):
    """
    Benchmark SCEP enrollment performance for device identity
    """
    def enroll_device(device_id):
        start_time = time.perf_counter()
        try:
            # Simulate SCEP enrollment process
            key_generation_time = 0.5  # ECC P-256 key generation
            csr_creation_time = 0.1    # CSR creation
            network_time = 2.0         # Network round-trip to CA
            certificate_processing = 1.0  # CA processing time
            
            total_time = key_generation_time + csr_creation_time + network_time + certificate_processing
            time.sleep(total_time)  # Simulate actual processing
            
            end_time = time.perf_counter()
            return {
                'device_id': device_id,
                'success': True,
                'enrollment_time': end_time - start_time,
                'components': {
                    'key_gen': key_generation_time,
                    'csr_creation': csr_creation_time,
                    'network': network_time,
                    'ca_processing': certificate_processing
                }
            }
        except Exception as e:
            return {
                'device_id': device_id,
                'success': False,
                'error': str(e)
            }
    
    # Run concurrent enrollments
    device_ids = [f"device-{i:04d}" for i in range(total_devices)]
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_devices) as executor:
        futures = [executor.submit(enroll_device, device_id) for device_id in device_ids]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    # Calculate metrics
    successful_enrollments = [r for r in results if r['success']]
    enrollment_times = [r['enrollment_time'] for r in successful_enrollments]
    
    return {
        'total_devices': total_devices,
        'successful_enrollments': len(successful_enrollments),
        'success_rate': len(successful_enrollments) / total_devices,
        'mean_enrollment_time': statistics.mean(enrollment_times) if enrollment_times else 0,
        'p95_enrollment_time': sorted(enrollment_times)[int(0.95 * len(enrollment_times))] if enrollment_times else 0,
        'throughput_per_minute': len(successful_enrollments) / (max(enrollment_times) / 60) if enrollment_times else 0
    }

# Expected baseline performance
BASELINE_SCEP_PERFORMANCE = {
    'mean_enrollment_time': 4.0,  # seconds
    'p95_enrollment_time': 8.0,   # seconds
    'success_rate': 0.98,         # 98%
    'max_concurrent_devices': 50,
    'throughput_per_minute': 200
}
```

### Device Authentication Performance
```python
def benchmark_device_authentication():
    """
    Benchmark device certificate authentication performance
    """
    authentication_metrics = {
        'certificate_validation': {
            'chain_validation_time_ms': {'mean': 15, 'p95': 30},
            'crl_check_time_ms': {'mean': 100, 'p95': 250},
            'ocsp_validation_time_ms': {'mean': 50, 'p95': 150},
            'total_validation_time_ms': {'mean': 165, 'p95': 430}
        },
        'network_access_control': {
            'radius_auth_time_ms': {'mean': 20, 'p95': 50},
            'policy_evaluation_time_ms': {'mean': 5, 'p95': 15},
            'network_authorization_time_ms': {'mean': 25, 'p95': 65}
        },
        'device_types': {
            'iot_sensor': {'auth_time_ms': {'mean': 200, 'p95': 500}},
            'mobile_device': {'auth_time_ms': {'mean': 150, 'p95': 300}},
            'network_equipment': {'auth_time_ms': {'mean': 100, 'p95': 200}}
        }
    }
    
    return authentication_metrics
```

## Large-Scale Deployment Performance

### Mass Device Enrollment
```bash
#!/bin/bash
# benchmark_mass_enrollment.sh

benchmark_mass_enrollment() {
    local total_devices=${1:-1000}
    local concurrent_limit=${2:-20}
    local scep_server=${3:-"https://scep.company.com:8080/scep"}
    
    echo "=== Mass Device Enrollment Benchmark ==="
    echo "Total devices: $total_devices"
    echo "Concurrent limit: $concurrent_limit"
    echo "SCEP server: $scep_server"
    
    start_time=$(date +%s)
    
    # Create device list
    seq 1 "$total_devices" | xargs -P "$concurrent_limit" -I {} bash -c "
        device_id=\"test-device-{:04d}\"
        echo \"Enrolling device: \$device_id\"
        
        # Generate key pair
        openssl ecparam -genkey -name prime256v1 -out \"/tmp/\${device_id}.key\" 2>/dev/null
        
        # Create CSR
        openssl req -new -key \"/tmp/\${device_id}.key\" -out \"/tmp/\${device_id}.csr\" \
            -subj \"/CN=\${device_id}.company.com/O=Company/OU=IoT Devices\" 2>/dev/null
        
        # Submit SCEP request
        enrollment_start=\$(date +%s.%N)
        response=\$(curl -s -w \"%{http_code}\" -o \"/tmp/\${device_id}.pem\" \
            -X POST \"$scep_server\" \
            -H \"Content-Type: application/pkcs10\" \
            --data-binary @\"/tmp/\${device_id}.csr\")
        enrollment_end=\$(date +%s.%N)
        
        enrollment_time=\$(echo \"\$enrollment_end - \$enrollment_start\" | bc -l)
        
        if [[ \"\$response\" == \"200\" ]]; then
            echo \"SUCCESS: \$device_id enrolled in \${enrollment_time}s\"
        else
            echo \"FAILED: \$device_id enrollment failed with HTTP \$response\"
        fi
        
        # Cleanup
        rm -f \"/tmp/\${device_id}.key\" \"/tmp/\${device_id}.csr\" \"/tmp/\${device_id}.pem\"
    "
    
    end_time=$(date +%s)
    total_time=$((end_time - start_time))
    
    echo "=== Benchmark Results ==="
    echo "Total enrollment time: ${total_time}s"
    echo "Average time per device: $(echo "scale=2; $total_time / $total_devices" | bc)s"
    echo "Throughput: $(echo "scale=2; $total_devices * 60 / $total_time" | bc) devices/minute"
}

benchmark_mass_enrollment 1000 20
```

### Network Performance Impact
```python
def analyze_network_performance_impact():
    """
    Analyze network performance impact of device identity operations
    """
    network_metrics = {
        'bandwidth_usage': {
            'scep_enrollment': {
                'request_size_bytes': 2048,    # CSR size
                'response_size_bytes': 4096,   # Certificate + chain
                'total_per_device_bytes': 6144
            },
            'certificate_validation': {
                'crl_download_bytes': 50000,   # Average CRL size
                'ocsp_request_bytes': 128,     # OCSP request
                'ocsp_response_bytes': 256     # OCSP response
            }
        },
        'connection_patterns': {
            'enrollment_connections': 'Short-lived, high CPU',
            'validation_connections': 'Frequent, low latency required',
            'renewal_connections': 'Periodic, predictable load'
        },
        'scaling_factors': {
            'devices_per_subnet': 254,
            'enrollment_burst_factor': 10,  # Peak enrollment rate
            'validation_frequency': 'Per connection attempt'
        }
    }
    
    return network_metrics
```

## Performance Monitoring and Alerting

### Real-time Device Identity Monitoring
```python
def setup_device_identity_monitoring():
    """
    Configure real-time monitoring for device identity performance
    """
    monitoring_config = {
        'enrollment_metrics': {
            'enrollment_rate_threshold': 100,      # enrollments per minute
            'enrollment_success_rate_threshold': 0.95,  # 95% success rate
            'enrollment_time_threshold_seconds': 10,
            'concurrent_enrollment_limit': 50
        },
        'authentication_metrics': {
            'auth_response_time_threshold_ms': 500,
            'auth_success_rate_threshold': 0.98,  # 98% success rate
            'failed_auth_attempts_threshold': 100,  # per minute
            'certificate_validation_time_threshold_ms': 200
        },
        'infrastructure_metrics': {
            'ca_response_time_threshold_ms': 2000,
            'scep_server_availability_threshold': 0.999,  # 99.9% uptime
            'certificate_store_access_time_ms': 50
        },
        'device_lifecycle_metrics': {
            'certificate_renewal_success_rate': 0.99,
            'device_connectivity_rate': 0.95,
            'certificate_expiration_buffer_days': 30
        }
    }
    
    alert_conditions = {
        'critical': [
            'SCEP server down > 5 minutes',
            'Certificate enrollment success rate < 90%',
            'Mass device authentication failures'
        ],
        'warning': [
            'Device enrollment rate > 200/minute',
            'Certificate validation time > 500ms',
            'CRL download failures'
        ]
    }
    
    return {'config': monitoring_config, 'alerts': alert_conditions}
```

### Device Performance Dashboard
```bash
#!/bin/bash
# generate_device_performance_dashboard.sh

generate_device_dashboard() {
    local dashboard_file="/var/www/html/device_identity_dashboard.json"
    
    echo "Generating device identity performance dashboard..."
    
    cat > "$dashboard_file" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "enrollment_metrics": {
        "daily_enrollments": $(grep -c "ENROLLMENT_SUCCESS" /var/log/device-identity.log),
        "enrollment_success_rate": "$(awk 'BEGIN{s=0;f=0} /ENROLLMENT_SUCCESS/{s++} /ENROLLMENT_FAILED/{f++} END{print (s+f>0 ? s/(s+f)*100 : 0)}' /var/log/device-identity.log)%",
        "average_enrollment_time": "$(awk '/enrollment_time/ {sum+=$3; count++} END {print (count>0 ? sum/count : 0)}' /var/log/device-identity.log)s"
    },
    "authentication_metrics": {
        "hourly_authentications": $(grep -c "AUTH_SUCCESS" /var/log/radius.log),
        "auth_success_rate": "$(awk 'BEGIN{s=0;f=0} /AUTH_SUCCESS/{s++} /AUTH_FAILED/{f++} END{print (s+f>0 ? s/(s+f)*100 : 0)}' /var/log/radius.log)%",
        "average_auth_time": "$(awk '/auth_time/ {sum+=$3; count++} END {print (count>0 ? sum/count : 0)}' /var/log/radius.log)ms"
    },
    "device_inventory": {
        "total_enrolled_devices": $(find /opt/device-ca/devices -name "*.pem" | wc -l),
        "active_devices": $(grep -c "DEVICE_ACTIVE" /var/log/device-monitoring.log),
        "devices_expiring_soon": $(find /opt/device-ca/devices -name "*.pem" -exec openssl x509 -in {} -noout -checkend 2592000 \; 2>/dev/null | grep -c "will expire")
    },
    "infrastructure_status": {
        "scep_server_status": "$(systemctl is-active scep-server)",
        "ca_server_response_time": "$(curl -o /dev/null -s -w '%{time_total}' https://ca.company.com/health)s",
        "certificate_store_size": "$(du -sh /opt/device-ca/devices | cut -f1)"
    }
}
EOF
    
    echo "Dashboard generated: $dashboard_file"
}

generate_device_dashboard
```

## Optimization Strategies

### Performance Tuning Recommendations
```python
def analyze_device_identity_optimization():
    """
    Analyze and provide recommendations for device identity performance optimization
    """
    optimization_strategies = {
        'enrollment_optimization': {
            'algorithm_selection': {
                'recommendation': 'Use ECDSA P-256 for faster key generation',
                'expected_improvement': '10x faster than RSA 2048-bit',
                'implementation_effort': 'Low'
            },
            'concurrent_processing': {
                'recommendation': 'Implement enrollment queuing and batch processing',
                'expected_improvement': '5x enrollment throughput',
                'implementation_effort': 'Medium'
            },
            'certificate_caching': {
                'recommendation': 'Cache intermediate certificates and templates',
                'expected_improvement': '50% reduction in CA processing time',
                'implementation_effort': 'Low'
            }
        },
        'authentication_optimization': {
            'certificate_validation_caching': {
                'recommendation': 'Cache certificate validation results',
                'expected_improvement': '80% reduction in validation time',
                'implementation_effort': 'Medium'
            },
            'local_crl_mirrors': {
                'recommendation': 'Deploy local CRL distribution points',
                'expected_improvement': '90% reduction in CRL fetch time',
                'implementation_effort': 'High'
            },
            'ocsp_stapling': {
                'recommendation': 'Implement OCSP stapling for devices',
                'expected_improvement': '70% reduction in validation latency',
                'implementation_effort': 'Medium'
            }
        },
        'infrastructure_optimization': {
            'load_balancing': {
                'recommendation': 'Deploy load-balanced SCEP servers',
                'expected_improvement': 'Linear scalability with server count',
                'implementation_effort': 'High'
            },
            'database_optimization': {
                'recommendation': 'Optimize certificate database queries and indexes',
                'expected_improvement': '60% improvement in lookup performance',
                'implementation_effort': 'Medium'
            }
        }
    }
    
    return optimization_strategies
```

### Capacity Planning Model
```python
def calculate_device_identity_capacity():
    """
    Calculate capacity requirements for device identity infrastructure
    """
    capacity_model = {
        'enrollment_capacity': {
            'single_scep_server': {
                'max_concurrent_enrollments': 50,
                'enrollments_per_hour': 1000,
                'daily_enrollment_capacity': 20000
            },
            'load_balanced_cluster': {
                'servers': 3,
                'max_concurrent_enrollments': 150,
                'enrollments_per_hour': 3000,
                'daily_enrollment_capacity': 60000
            }
        },
        'authentication_capacity': {
            'radius_server': {
                'authentications_per_second': 1000,
                'concurrent_devices': 10000,
                'certificate_validations_per_second': 500
            }
        },
        'storage_requirements': {
            'certificate_storage': {
                'avg_certificate_size_bytes': 2048,
                'certificates_per_gb': 500000,
                'retention_period_years': 7
            },
            'log_storage': {
                'daily_log_size_mb': 100,
                'monthly_log_size_gb': 3,
                'retention_period_months': 24
            }
        }
    }
    
    return capacity_model
```

## Performance Benchmarking Results

### Expected Performance Baselines

| Metric | IoT Devices | Mobile Devices | Network Equipment |
|--------|-------------|----------------|-------------------|
| Enrollment Time | 3-5 seconds | 2-4 seconds | 5-8 seconds |
| Authentication Time | 200-500ms | 150-300ms | 100-200ms |
| Certificate Validation | 100-200ms | 80-150ms | 50-100ms |
| Concurrent Enrollments | 20 | 30 | 10 |

### Throughput Expectations

| Scenario | Enrollments/Hour | Authentications/Second | Scalability Limit |
|----------|------------------|----------------------|-------------------|
| Single SCEP Server | 1,000 | 100 | 50 concurrent |
| Load-Balanced Cluster | 3,000 | 500 | 150 concurrent |
| Enterprise Scale | 10,000 | 2,000 | 500 concurrent |

This performance metrics framework enables comprehensive monitoring and optimization of device identity infrastructure to support large-scale device deployments efficiently.