# File Processing: Large-Scale Batch Data Pipeline

> *"File processing is the mathematical optimization of resource allocation - balancing memory, CPU, and I/O for maximum throughput efficiency."*

## Overview

This use case demonstrates large-scale file processing using NiFi's resource management algorithms and batch optimization techniques. It showcases how mathematical models for memory allocation, I/O scheduling, and parallel processing enable efficient handling of massive file workloads.

## Mathematical Foundation

**Resource Allocation Theory**: File processing modeled as a constrained optimization problem balancing memory usage, CPU utilization, and I/O throughput.

**Key Equation**: `Optimal_Batch_Size = √(2 × Setup_Cost × Demand_Rate / Holding_Cost_Per_Unit)`

**Queuing Theory Application**: File processing queues analyzed using M/G/1 models with batch service disciplines.

## Scenario

**Business Context**: Media company processing 100TB+ of video, audio, and image files daily for content analysis, transcoding, and archival.

**Requirements**:
- Process 10,000+ files per day ranging from 1MB to 10GB each
- Support multiple file formats (MP4, AVI, JPG, PNG, PDF, CSV)
- Maintain processing SLA of 4 hours for 95% of files
- Optimize storage costs through intelligent compression and archiving

## Flow Architecture

```
[File Sources] → GetFile → RouteOnAttribute → [Format-Specific Processing]
    ↓              ↓            ↓                    ↓
[SFTP/S3/NFS] → [File Discovery] → [Size-Based Routing] → [Video/Audio/Image/Document]
    ↓              ↓            ↓                    ↓
[Batch Formation] → [Parallel Processing] → [Quality Validation] → [Output Storage]
    ↓              ↓            ↓                    ↓
[Memory Management] → [Resource Allocation] → [Error Recovery] → [Archive/Delete]
```

## Mathematical Analysis

### Batch Size Optimization

**Economic Order Quantity (EOQ) Model**:
```
Setup Cost (S): 30 seconds per batch initialization
Demand Rate (D): 10,000 files/day = 0.116 files/second
Holding Cost (H): $0.001 per file per hour in queue

Optimal Batch Size = √(2 × S × D / H)
Optimal Batch Size = √(2 × 30 × 0.116 / 0.001) = √6960 ≈ 83 files per batch

Batch Processing Frequency: 10,000 files / 83 files per batch = 120 batches per day
Average Queue Time: 83 files / 2 / 0.116 files/sec = 358 seconds ≈ 6 minutes
```

**Memory-Constrained Batch Sizing**:
```
Available Memory: 32GB heap
Average File Size: 500MB
Memory per FlowFile: 1KB (metadata only, content on disk)
Content Claim Overhead: 100MB per batch (temporary processing)

Memory-Based Batch Limit = (Available_Memory - System_Overhead) / (Memory_per_File + Content_Overhead/Batch_Size)
Memory Batch Limit = (32GB - 8GB) / (1KB + 100MB/83) ≈ 19,000 files

Effective Batch Size = min(Optimal_EOQ_Size, Memory_Batch_Limit) = min(83, 19000) = 83 files
```

### I/O Performance Modeling

**Sequential vs Random I/O Analysis**:
```
Sequential Read Speed: 150 MB/second (typical SSD)
Random Read Speed: 50 MB/second (typical SSD) 
File Size Distribution:
  Small (< 10MB): 60% of files
  Medium (10MB - 1GB): 30% of files  
  Large (> 1GB): 10% of files

Sequential Processing Time:
  Small Files: 10MB / 150 MB/s = 0.067 seconds
  Medium Files: 500MB / 150 MB/s = 3.33 seconds
  Large Files: 5GB / 150 MB/s = 33.3 seconds

Weighted Average Processing Time = 0.6 × 0.067 + 0.3 × 3.33 + 0.1 × 33.3 = 4.37 seconds per file
```

### Parallel Processing Optimization

**Amdahl's Law Application**:
```
Sequential Portion (s): 20% (file discovery, metadata extraction)
Parallel Portion (p): 80% (content processing, transformation)
Number of Processors (n): 16 cores

Theoretical Speedup = 1 / (s + p/n) = 1 / (0.2 + 0.8/16) = 1 / (0.2 + 0.05) = 4.0x

Practical Speedup (accounting for overhead): 3.2x
Effective Processing Rate: 4.37 seconds / 3.2 = 1.37 seconds per file
Daily Capacity: 86,400 seconds / 1.37 seconds = 63,066 files per day (vs 10,000 required)
```

### Performance Optimization

**Resource Allocation**:
```
CPU Allocation:
  File Discovery: 2 cores (I/O bound)
  Content Processing: 12 cores (CPU bound)
  Output Writing: 2 cores (I/O bound)

Memory Allocation:
  FlowFile Repository: 4GB
  Content Repository: 20GB  
  System/JVM: 8GB

Concurrent Tasks per Processor:
  GetFile: 4 tasks (limited by file system performance)
  RouteOnAttribute: 8 tasks (CPU bound)
  Content Processing: 16 tasks (maximize CPU usage)
  PutFile: 4 tasks (limited by output I/O)
```

## Implementation Details

### File Discovery and Routing

**GetFile (Multiple Sources)**:
```
Input Directory: /data/incoming
File Filter: .*\.(mp4|avi|jpg|png|pdf|csv)$
Batch Size: 100 files
Keep Source File: false
Minimum File Age: 60 sec
Recursive: true
Maximum Files per Directory: 10000
```

**ListS3 (Cloud Storage)**:
```
Bucket: media-processing-input
Prefix: incoming/
Use Versions: false
Min Age: 60 sec
Write Object Tags: true
Requester Pays: false
```

**RouteOnAttribute (Size-Based Routing)**:
```
Small Files: ${file.size:lt(10485760)} (< 10MB)
Medium Files: ${file.size:ge(10485760):and(${file.size:lt(1073741824)})} (10MB - 1GB)  
Large Files: ${file.size:ge(1073741824)} (> 1GB)
Extension: ${filename:getExtension():toLowerCase()}
```

### Content Processing

**UpdateAttribute (Metadata Extraction)**:
```
file.processed.timestamp: ${now()}
file.original.path: ${absolute.path}
file.size.category: ${file.size:lt(10485760):ifElse('small', ${file.size:lt(1073741824):ifElse('medium', 'large')})}
processing.priority: ${file.size:divide(1048576):multiply(-1):plus(1000)}
```

**ExecuteStreamCommand (External Processing)**:
```
Command: /usr/local/bin/ffmpeg
Command Arguments: -i;${absolute.path};-vcodec;libx264;-acodec;aac;${output.path}
Working Directory: /tmp/nifi-processing
Max Concurrent Tasks: 4 (I/O intensive)
```

**CompressContent (Storage Optimization)**:
```
Compression Format: gzip
Compression Level: 6 (balanced speed/ratio)
Update Filename: true
Batch Size: 50 files (reduce compression overhead)
```

### Output Management

**MergeContent (Batch Optimization)**:
```
Merge Strategy: Bin-Packing Algorithm
Max Bin Count: 10
Min Entries: 100 files
Max Entries: 1000 files  
Max Bin Size: 1GB
Correlation Attribute Name: processing.batch.id
```

**PutS3Object (Archival Storage)**:
```
Bucket: media-archive-processed
Storage Class: GLACIER_IR (cost optimization)
Multipart Threshold: 100MB
Multipart Part Size: 64MB
Server Side Encryption: AES256
```

## Expected Performance

### Throughput Metrics
- **Files/Hour**: 2,000-3,000 (depending on file size mix)
- **Data Volume/Hour**: 500GB-2TB processed
- **Processing Latency**: 30 seconds to 10 minutes per file
- **Queue Depth**: < 500 files (optimal flow control)

### Resource Usage
- **CPU**: 12-16 cores (content processing intensive)
- **Memory**: 24-32GB heap (batch processing and caching)
- **Disk I/O**: 100-500 MB/second (sequential reads/writes)
- **Network**: 50-200 MB/second (cloud storage transfers)

## Monitoring and Alerting

### Key Metrics to Track
```
nifi.throughput.files_per_hour > 2000
nifi.processing_time.p95 < 600_seconds
nifi.queue_depth.file_processing < 1000
nifi.error_rate.file_corruption < 0.1%
```

### Resource Utilization Metrics
```
Disk_Usage_Rate = (Read_MB + Write_MB) / Available_IO_Bandwidth < 80%
Memory_Utilization = Used_Heap / Max_Heap < 85%
CPU_Utilization = Processing_Time / Total_Time < 90%
Queue_Wait_Time = avg(file_queue_time) < 300_seconds
```

### Alert Conditions
- File processing rate drops below 1,500 files/hour
- Queue depth exceeds 2,000 files
- Processing error rate exceeds 1%
- Disk space usage exceeds 90%

## Scaling Strategies

### Horizontal Scaling
- **Directory Partitioning**: Multiple GetFile processors for different directories
- **File Type Specialization**: Dedicated flows for video, audio, image processing
- **Geographic Distribution**: Regional processing clusters near data sources

### Vertical Scaling
- **Memory Optimization**: Larger heaps for bigger batch processing
- **CPU Scaling**: More cores for parallel content processing
- **Storage Optimization**: Faster SSDs or NVMe drives for I/O intensive operations

### Dynamic Resource Allocation
```python
def adjust_batch_size(current_queue_depth, processing_rate):
    if current_queue_depth > 1000:
        return min(current_batch_size * 1.2, max_batch_size)
    elif current_queue_depth < 100:
        return max(current_batch_size * 0.8, min_batch_size)
    return current_batch_size
```

## Common Issues and Solutions

### Memory Management
```
Problem: OutOfMemoryError during large file processing
Solution: Implement streaming processing with content claims
Math: Content_Claim_Size = File_Size, Memory_Usage = Metadata_Only (~1KB per file)
```

### I/O Bottlenecks
```
Problem: Disk I/O becomes bottleneck for high file counts
Solution: Optimize file access patterns and use parallel I/O
Math: Optimal_Concurrent_IO = Available_Bandwidth / Average_Transfer_Rate
```

### Processing Imbalances
```
Problem: Large files cause processing delays for smaller files
Solution: Implement priority queuing based on file size
Math: Priority_Score = Base_Priority - (File_Size / Size_Normalization_Factor)
```

### Error Recovery
```
Problem: File corruption or processing failures lose data
Solution: Implement checkpointing and retry mechanisms
Math: Retry_Delay = Base_Delay × 2^Attempt_Count (exponential backoff)
```

## File Type Specific Optimizations

### Video Processing (MP4, AVI)
```
Processing Strategy:
  Transcode in parallel: 4 concurrent ffmpeg processes
  Memory allocation: 2GB per transcoding process
  Quality settings: CRF 23 (balanced quality/size)
  Expected processing time: 0.5x realtime duration
```

### Image Processing (JPG, PNG)
```
Batch Processing:
  Group size: 500 images per batch
  Processing tool: ImageMagick convert
  Operations: Resize, compress, format conversion
  Memory usage: 100MB per batch
```

### Document Processing (PDF, CSV)
```
Text Extraction:
  Tool: Apache Tika
  Concurrent processes: 8
  Memory per process: 512MB
  OCR enabled: For scanned PDFs
```

## Cost Optimization

### Storage Costs
```
Input Storage (S3 Standard): 100TB × $23/TB = $2,300/month
Processing Storage (SSD): 10TB × $100/TB = $1,000/month
Output Storage (Glacier IR): 80TB × $4/TB = $320/month
Total Storage Cost: ~$3,620/month
```

### Compute Costs
```
Processing Infrastructure: 16 cores × $0.10/hour × 720 hours = $1,152/month
Network Transfer: 50TB × $0.09/GB = $4,500/month
Monitoring & Management: $200/month
Total Compute Cost: ~$5,852/month
```

### Cost per File
```
Total Files/Month: 300,000 files
Total Cost: $9,472/month
Cost per File: ~$0.032 per file
Cost per GB Processed: ~$3.16 per GB
```

## Next Steps

1. **Design File Type Matrix**: Map processing requirements to file formats
2. **Implement Batch Optimization**: Configure optimal batch sizes based on EOQ
3. **Set Up Resource Monitoring**: Deploy comprehensive performance tracking
4. **Test Scaling Scenarios**: Validate horizontal and vertical scaling
5. **Optimize Cost Structure**: Implement storage tiering and compression strategies

---

*"File processing mastery combines the elegance of mathematical optimization with the pragmatism of resource constraints - where batch theory meets the reality of finite memory and I/O."*