# Certificate Authority Performance Metrics

## Overview

This document establishes performance benchmarks, monitoring methodologies, and optimization strategies for Certificate Authority operations. Performance metrics are crucial for ensuring service availability, scalability, and operational efficiency.

## Key Performance Indicators

### Certificate Issuance Performance
```python
def ca_performance_metrics():
    return {
        "throughput_metrics": {
            "certificates_per_hour": 1000,      # Target issuance rate
            "csr_processing_time": "< 30 seconds",  # Average processing
            "validation_time": "< 60 seconds",   # Domain validation
            "certificate_delivery": "< 5 minutes"  # End-to-end delivery
        },
        "availability_metrics": {
            "ca_service_uptime": "99.9%",       # Service availability
            "ocsp_response_time": "< 200ms",    # OCSP query response
            "crl_update_frequency": "24 hours", # CRL publishing
            "hsm_availability": "99.99%"       # HSM uptime
        },
        "scalability_metrics": {
            "concurrent_requests": 100,         # Simultaneous CSRs
            "peak_throughput": 5000,            # Max certificates/hour
            "database_capacity": "10M certificates", # Storage limit
            "network_bandwidth": "1 Gbps"      # Network capacity
        }
    }
```

### HSM Performance Monitoring
```bash
#!/bin/bash
# hsm_performance_monitor.sh

echo "=== HSM Performance Monitoring ==="

# Monitor HSM response times
test_hsm_performance() {
    local iterations=10
    local total_time=0
    
    for i in $(seq 1 $iterations); do
        start_time=$(date +%s.%N)
        
        # Test HSM operation (key generation or signing)
        pkcs11-tool --module /usr/lib/pkcs11/libCryptoki2_64.so \
            --login --pin $HSM_PIN \
            --test > /dev/null 2>&1
        
        end_time=$(date +%s.%N)
        operation_time=$(echo "$end_time - $start_time" | bc)
        total_time=$(echo "$total_time + $operation_time" | bc)
    done
    
    average_time=$(echo "scale=3; $total_time / $iterations" | bc)
    echo "HSM Average Response Time: ${average_time}s"
    
    # Alert if performance degrades
    if (( $(echo "$average_time > 1.0" | bc -l) )); then
        logger "HSM_PERFORMANCE_ALERT: Response time ${average_time}s exceeds threshold"
    fi
}

# Monitor HSM utilization
check_hsm_utilization() {
    # Check active sessions
    active_sessions=$(lunacm -c "partition showInfo" | grep "Active Sessions" | awk '{print $3}')
    max_sessions=$(lunacm -c "partition showInfo" | grep "Max Sessions" | awk '{print $3}')
    
    utilization=$(echo "scale=2; $active_sessions / $max_sessions * 100" | bc)
    echo "HSM Session Utilization: ${utilization}%"
    
    if (( $(echo "$utilization > 80" | bc -l) )); then
        logger "HSM_CAPACITY_ALERT: Session utilization ${utilization}% is high"
    fi
}

test_hsm_performance
check_hsm_utilization
```

## Performance Benchmarking

### Certificate Issuance Benchmarks
```python
def benchmark_certificate_issuance():
    """Benchmark different aspects of certificate issuance"""
    
    benchmarks = {
        "csr_validation": {
            "rsa_2048": "15ms",
            "rsa_3072": "25ms", 
            "ecdsa_p256": "8ms",
            "ecdsa_p384": "12ms"
        },
        "certificate_signing": {
            "rsa_2048_ca": "50ms",
            "rsa_4096_ca": "180ms",
            "ecdsa_p384_ca": "25ms"
        },
        "database_operations": {
            "csr_storage": "5ms",
            "certificate_storage": "10ms",
            "serial_number_generation": "2ms",
            "index_updates": "8ms"
        },
        "network_operations": {
            "domain_validation": "2000ms",
            "email_validation": "5000ms",
            "ct_log_submission": "1000ms",
            "ocsp_update": "100ms"
        }
    }
    
    return benchmarks

# Performance testing script
def run_performance_test(iterations=1000):
    """Run comprehensive CA performance tests"""
    
    print(f"Running CA performance test with {iterations} iterations...")
    
    # Test certificate generation pipeline
    start_time = time.time()
    
    for i in range(iterations):
        # Simulate CSR processing
        process_csr()
        validate_domain()
        generate_certificate()
        update_database()
        
    end_time = time.time()
    
    total_time = end_time - start_time
    throughput = iterations / total_time
    
    return {
        "total_time": total_time,
        "throughput": f"{throughput:.2f} certificates/second",
        "average_time": f"{(total_time/iterations)*1000:.2f}ms per certificate"
    }
```

### OCSP Responder Performance
```bash
#!/bin/bash
# ocsp_performance_test.sh

echo "=== OCSP Responder Performance Test ==="

OCSP_URL="http://ocsp.example.com:8080"
TEST_CERT="/secure/test_certificates/test_cert.pem"
CA_CERT="/secure/ca/certs/ca-chain.cert.pem"

# Test OCSP response times
test_ocsp_performance() {
    local iterations=100
    local total_time=0
    local successful_requests=0
    
    for i in $(seq 1 $iterations); do
        start_time=$(date +%s.%N)
        
        # Send OCSP request
        response=$(openssl ocsp -issuer "$CA_CERT" \
            -cert "$TEST_CERT" \
            -url "$OCSP_URL" \
            -text -noverify 2>/dev/null)
        
        end_time=$(date +%s.%N)
        
        if echo "$response" | grep -q "Response verify OK"; then
            ((successful_requests++))
            request_time=$(echo "$end_time - $start_time" | bc)
            total_time=$(echo "$total_time + $request_time" | bc)
        fi
    done
    
    if [ $successful_requests -gt 0 ]; then
        average_time=$(echo "scale=3; $total_time / $successful_requests" | bc)
        success_rate=$(echo "scale=2; $successful_requests / $iterations * 100" | bc)
        
        echo "OCSP Performance Results:"
        echo "- Average Response Time: ${average_time}s"
        echo "- Success Rate: ${success_rate}%"
        echo "- Successful Requests: $successful_requests/$iterations"
    else
        echo "ERROR: No successful OCSP requests"
    fi
}

test_ocsp_performance
```

## Resource Utilization Monitoring

### System Resource Monitoring
```python
def monitor_ca_resources():
    """Monitor CA system resource utilization"""
    
    import psutil
    import time
    
    # CPU utilization
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Memory utilization  
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    
    # Disk utilization
    disk = psutil.disk_usage('/secure')
    disk_percent = (disk.used / disk.total) * 100
    
    # Network statistics
    network = psutil.net_io_counters()
    
    metrics = {
        "timestamp": time.time(),
        "cpu_utilization": f"{cpu_percent}%",
        "memory_utilization": f"{memory_percent}%", 
        "disk_utilization": f"{disk_percent:.1f}%",
        "network_bytes_sent": network.bytes_sent,
        "network_bytes_received": network.bytes_recv
    }
    
    # Check for resource alerts
    alerts = []
    if cpu_percent > 80:
        alerts.append("High CPU utilization")
    if memory_percent > 85:
        alerts.append("High memory utilization")
    if disk_percent > 90:
        alerts.append("Low disk space")
    
    return {"metrics": metrics, "alerts": alerts}
```

### Database Performance Monitoring
```bash
#!/bin/bash
# database_performance_monitor.sh

echo "=== CA Database Performance Monitoring ==="

DB_PATH="/secure/ca_database.db"

# Check database size and growth
check_database_size() {
    db_size=$(du -h "$DB_PATH" | cut -f1)
    echo "Database Size: $db_size"
    
    # Check certificate count
    cert_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM certificates;")
    echo "Certificate Count: $cert_count"
    
    # Check recent growth
    recent_certs=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM certificates WHERE created_at > datetime('now', '-24 hours');")
    echo "Certificates Issued (24h): $recent_certs"
}

# Test database query performance
test_query_performance() {
    echo "Testing database query performance..."
    
    # Time common queries
    time sqlite3 "$DB_PATH" "SELECT * FROM certificates WHERE status='active' LIMIT 1000;" > /dev/null
    time sqlite3 "$DB_PATH" "SELECT * FROM certificates WHERE serial_number='1234567890';" > /dev/null
    time sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM certificates GROUP BY issuer_ca;" > /dev/null
}

check_database_size
test_query_performance
```

## Performance Optimization

### Optimization Strategies
```python
def ca_optimization_recommendations():
    return {
        "hardware_optimization": {
            "dedicated_hsm": "Use dedicated HSM for high throughput",
            "ssd_storage": "Use SSD storage for database operations",
            "network_optimization": "Implement load balancing for high availability",
            "cpu_scaling": "Scale CPU cores for concurrent processing"
        },
        "software_optimization": {
            "database_indexing": "Optimize database indexes for common queries",
            "connection_pooling": "Implement database connection pooling",
            "caching": "Cache frequently accessed certificates and CRLs",
            "parallel_processing": "Process multiple CSRs in parallel"
        },
        "operational_optimization": {
            "batch_processing": "Process certificates in batches during low usage",
            "automated_renewal": "Implement automated certificate renewal",
            "monitoring_alerts": "Set up proactive performance monitoring",
            "capacity_planning": "Plan for peak usage periods"
        }
    }
```

### Performance Tuning Configuration
```bash
# CA performance tuning script
#!/bin/bash
# tune_ca_performance.sh

echo "=== CA Performance Tuning ==="

# Optimize database settings
optimize_database() {
    echo "Optimizing database performance..."
    
    sqlite3 /secure/ca_database.db << EOF
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 10000;
PRAGMA temp_store = memory;
VACUUM;
ANALYZE;
EOF
    
    echo "Database optimization complete"
}

# Optimize system settings
optimize_system() {
    echo "Optimizing system performance..."
    
    # Increase file descriptor limits
    echo "* soft nofile 65536" >> /etc/security/limits.conf
    echo "* hard nofile 65536" >> /etc/security/limits.conf
    
    # Optimize network settings
    echo "net.core.rmem_max = 268435456" >> /etc/sysctl.conf
    echo "net.core.wmem_max = 268435456" >> /etc/sysctl.conf
    
    sysctl -p
    echo "System optimization complete"
}

optimize_database
optimize_system
```

## Service Level Agreements

### Performance SLAs
- **Certificate Issuance**: 95% of certificates issued within 5 minutes
- **OCSP Response Time**: 99% of queries responded to within 200ms
- **Service Availability**: 99.9% uptime (8.77 hours downtime/year max)
- **CRL Updates**: Published within 1 hour of certificate revocation
- **Validation Response**: Domain validation completed within 2 minutes

### Monitoring and Alerting
```bash
# SLA monitoring script
#!/bin/bash
# sla_monitor.sh

# Check certificate issuance SLA
check_issuance_sla() {
    # Count certificates issued in last hour that took > 5 minutes
    slow_issuances=$(sqlite3 /secure/ca_database.db \
        "SELECT COUNT(*) FROM certificates WHERE 
         created_at > datetime('now', '-1 hour') AND 
         (julianday(issued_at) - julianday(requested_at)) * 1440 > 5;")
    
    total_issuances=$(sqlite3 /secure/ca_database.db \
        "SELECT COUNT(*) FROM certificates WHERE 
         created_at > datetime('now', '-1 hour');")
    
    if [ $total_issuances -gt 0 ]; then
        sla_compliance=$(echo "scale=2; (($total_issuances - $slow_issuances) / $total_issuances) * 100" | bc)
        echo "Issuance SLA Compliance: ${sla_compliance}%"
        
        if (( $(echo "$sla_compliance < 95" | bc -l) )); then
            logger "SLA_ALERT: Certificate issuance SLA below 95%: ${sla_compliance}%"
        fi
    fi
}

check_issuance_sla
```

This performance metrics framework provides comprehensive monitoring and optimization capabilities for maintaining high-performance CA operations.