# Crypto Mining Protection

## Overview

The MCP sandbox includes **automatic crypto mining detection and termination** to prevent abuse. This protects against both network-heavy and CPU-intensive mining operations.

## Detection Methods

### 1. CPU Mining Detection (Primary)

Detects hash calculation loops and CPU-intensive mining:

**Pattern:**
- Sustained CPU usage > 85% for 10+ seconds
- Typical of Bitcoin/Ethereum mining simulations
- Hash calculation loops, proof-of-work algorithms

**Action:**
- 🔴 **AUTO-KILL**: Container is automatically terminated
- Alert logged with details (CPU %, duration, etc.)
- Marked as "cpu_mining" in alerts

**Example code that triggers detection:**
```python
import hashlib
import time

# This will be detected and killed
nonce = 0
while True:  # Sustained high CPU
    hash_output = hashlib.sha256(f"block{nonce}".encode()).hexdigest()
    nonce += 1
```

### 2. Network Mining Detection

Detects pool mining and network-heavy operations:

**Patterns:**
- High CPU (>80%) + High network rate (>5 MB/s)
- Sustained network usage > 100 MB total
- Network rate spikes (5x above average)

**Actions:**
- Alerts logged (may not auto-kill)
- Visible in dashboard
- Can be configured for auto-termination

### 3. Anomaly Detection

Statistical anomaly detection:

- Compares current metrics vs. historical average
- Flags unusual spikes in network or CPU
- Learns normal behavior per container

## Configuration

### Thresholds (in `monitor.py`)

```python
# CPU Mining
CPU_MINING_THRESHOLD = 85      # % CPU to trigger detection
CPU_MINING_DURATION = 10       # Seconds of sustained high CPU
CPU_MINING_AUTO_KILL = True    # Auto-terminate on detection

# Network Monitoring
NETWORK_RATE_WARNING_MBPS = 10    # Warn at 10 MB/s
NETWORK_RATE_CRITICAL_MBPS = 50   # Critical at 50 MB/s
NETWORK_TOTAL_WARNING_MB = 100    # Warn at 100 MB total
NETWORK_TOTAL_CRITICAL_MB = 500   # Critical at 500 MB total
NETWORK_ANOMALY_THRESHOLD = 5.0   # Flag 5x above average
```

### Adjusting Thresholds

For stricter protection:
```python
CPU_MINING_THRESHOLD = 70      # Lower threshold (more sensitive)
CPU_MINING_DURATION = 5        # Faster detection
```

For looser protection (ML workloads):
```python
CPU_MINING_THRESHOLD = 95      # Higher threshold
CPU_MINING_DURATION = 30       # Longer grace period
```

## How It Works

### Detection Flow

1. **Monitoring Loop** (every 1 second):
   - Collects CPU, memory, network metrics
   - Calculates network rates (bytes/sec)
   - Tracks high CPU duration

2. **When High CPU Detected** (>85%):
   - Starts timer for this container
   - Logs warning: "Container started high CPU usage"
   - Continues monitoring

3. **After Sustained Period** (10 seconds):
   - Creates alert: "CRYPTO MINING DETECTED"
   - If auto-kill enabled: Terminates container immediately
   - Stores alert in history
   - Logs error with details

4. **If CPU Normalizes**:
   - Resets timer
   - Logs: "Container CPU normalized"
   - No alert generated

### Alert Structure

```json
{
  "container_id": "abc123def456",
  "name": "sandbox_xyz",
  "alert_type": "cpu_mining",
  "severity": "critical",
  "timestamp": 1696348800.0,
  "auto_killed": true,
  "details": {
    "cpu_percent": 98.5,
    "duration_seconds": 12.3,
    "threshold": 85
  },
  "message": "🚨 CRYPTO MINING DETECTED: Container sandbox_xyz has sustained 98.5% CPU for 12.3s - Likely running hash calculations! 🔪 Container TERMINATED automatically."
}
```

## API Endpoints

### Get All Alerts

```bash
GET /api/alerts?limit=50
```

**Response:**
```json
{
  "alerts": [...],
  "count": 5
}
```

### Get Critical Alerts Only

```bash
GET /api/alerts/critical?limit=20
```

Returns only critical alerts (auto-killed containers, severe issues).

### Get Alerts for Specific Container

```bash
GET /api/containers/{container_id}/alerts?limit=20
```

### Get Crashes (includes mining kills)

```bash
GET /api/crashes?limit=50
```

Mining-terminated containers appear here with exit code 137 (SIGKILL).

## Usage

### Start Monitoring

The monitoring service runs automatically with the dashboard:

```bash
# Start dashboard (includes monitoring)
./run_dashboard.sh

# Or manually
poetry run python dashboard_server.py
```

### View Alerts in Dashboard

1. Open dashboard: http://localhost:8080
2. Navigate to "Alerts" section
3. See real-time alerts with severity indicators
4. Filter by type, severity, container

### Test Mining Detection

```bash
# Run the test suite
poetry run python test_mining_detection.py
```

This will:
- Create a sandbox
- Execute mining code
- Verify detection and termination
- Check for false positives

## Logs

Mining detection produces clear logs:

### When High CPU Starts

```
⚠️  Container sandbox_abc123 started high CPU usage: 92.1%
```

### When Mining Detected

```
🚨 CRYPTO MINING DETECTED: Container sandbox_abc123 has sustained 95.3% CPU for 11.2s - Likely running hash calculations or crypto mining!
🔪 TERMINATED container sandbox_abc123 for suspected crypto mining
```

### When CPU Normalizes

```
✅ Container sandbox_abc123 CPU normalized after 3.5s
```

## False Positives

### Legitimate High CPU Use Cases

Some legitimate tasks may have high CPU:
- Machine learning training
- Large dataset processing
- Complex mathematical computations
- Video encoding
- Image processing

### Avoiding False Positives

1. **Break up computation**:
   ```python
   # Bad: Sustained 100% CPU
   result = sum(i**2 for i in range(1000000000))
   
   # Good: Periodic breaks
   for batch in batches:
       result = process(batch)
       time.sleep(0.1)  # CPU drops, resets timer
   ```

2. **Increase thresholds** for ML workloads:
   ```python
   CPU_MINING_DURATION = 60  # Allow 60s of high CPU
   ```

3. **Disable auto-kill**, rely on manual review:
   ```python
   CPU_MINING_AUTO_KILL = False
   ```

## Best Practices

### For Operators

1. **Monitor the alerts dashboard** regularly
2. **Review false positives** and adjust thresholds
3. **Set up alerting** for critical events
4. **Log aggregation** for audit trails
5. **Periodic threshold tuning** based on workload

### For Users

1. **Avoid infinite loops** with high CPU
2. **Add sleep/delays** in computation loops
3. **Break up large tasks** into chunks
4. **Profile your code** before running
5. **Request threshold adjustment** if needed

## Integration

### With MCP Server

The MCP server automatically integrates with monitoring when the dashboard is running. No code changes needed.

### With External Monitoring

Export alerts to external systems:

```python
# In monitor.py or custom integration
import requests

def send_alert_to_slack(alert):
    if alert.severity == "critical":
        requests.post(SLACK_WEBHOOK, json={
            "text": f"🚨 {alert.message}"
        })

# Hook into alert generation
for alert in network_alerts:
    self.network_alerts.append(alert)
    send_alert_to_slack(alert)  # Custom integration
```

## Troubleshooting

### Mining Not Detected

**Problem:** Crypto mining code runs without being killed.

**Solutions:**
1. Ensure dashboard/monitor is running:
   ```bash
   ./run_dashboard.sh
   ```

2. Check thresholds are appropriate:
   ```python
   # In monitor.py
   CPU_MINING_THRESHOLD = 85  # Lower if needed
   CPU_MINING_DURATION = 10   # Reduce if needed
   ```

3. Verify auto-kill is enabled:
   ```python
   CPU_MINING_AUTO_KILL = True
   ```

### False Positives

**Problem:** Legitimate code being killed.

**Solutions:**
1. Increase duration threshold:
   ```python
   CPU_MINING_DURATION = 30  # More grace time
   ```

2. Add breaks in your code:
   ```python
   import time
   for i in range(iterations):
       # Heavy computation
       if i % 100 == 0:
           time.sleep(0.01)  # Brief pause
   ```

3. Temporarily disable auto-kill for testing:
   ```python
   CPU_MINING_AUTO_KILL = False
   ```

### Alerts Not Visible

**Problem:** Mining happened but no alerts in API.

**Check:**
1. Monitor is running (started with dashboard)
2. Container ID matches (12-char short ID)
3. Check logs for error messages
4. Verify network connectivity to Docker daemon

## Performance Impact

### Monitoring Overhead

- **CPU**: < 1% overhead (metrics collected every second)
- **Memory**: ~50 MB for monitoring service
- **Network**: Minimal (local Docker socket only)
- **Disk**: Alerts stored in memory (100 most recent)

### Container Impact

- **No impact** during normal operation
- **Immediate termination** on detection (SIGKILL)
- **No graceful shutdown** for mining containers

## Security Considerations

### What This Protects Against

✅ CPU-intensive crypto mining
✅ Hash calculation loops
✅ Proof-of-work abuse
✅ Sustained resource abuse
✅ Network data exfiltration patterns

### What This Does NOT Protect Against

❌ Brief CPU spikes (< 10 seconds)
❌ Low-intensity mining (< 85% CPU)
❌ Distributed mining (multiple low-CPU containers)
❌ Memory-intensive attacks
❌ Storage abuse

### Additional Protection

For comprehensive protection, combine with:
- Resource limits (CPU, memory, PIDs, network)
- Time limits (sandbox timeout)
- Network egress filtering
- Rate limiting per user/IP
- Authentication and authorization

## Summary

The crypto mining protection provides:

✅ **Automatic detection** of CPU and network mining patterns
✅ **Auto-termination** of suspected mining containers
✅ **Real-time alerts** with detailed metrics
✅ **Dashboard visualization** of threats
✅ **Configurable thresholds** for different workloads
✅ **API access** to alert history
✅ **Minimal performance impact**

This makes the MCP sandbox hostile to crypto mining while allowing legitimate computation workloads.

