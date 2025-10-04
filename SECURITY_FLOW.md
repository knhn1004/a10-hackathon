# Security Flow Documentation

## Complete Multi-Layer Security Architecture

This document explains how both security layers (Ollama LLM + Random Forest ML) work together to protect against malicious code execution.

---

## 🛡️ Layer 1: Pre-Execution LLM Filter (Ollama)

**Location**: `mcp_server.py` lines 384-506  
**Model**: Llama 3.1 via Ollama  
**Trigger**: Before ANY code execution

### When It Runs:
1. ✅ **`execute_python`** - Direct code execution (line 965-967)
2. ✅ **`execute_from_url`** - URL-fetched code execution (line 1085-1087)

### Flow:
```
User submits code
    ↓
MCP Server receives request (execute_python or execute_from_url)
    ↓
SandboxManager.execute_code() called
    ↓
🛡️ LLM Filter Review (if CODE_FILTER_ENABLED)
    ├─ Review timeout: 30 seconds
    ├─ Analyzes code for threats
    └─ Returns: decision (accept/reject), confidence, threats, reasons
    ↓
Decision == "reject" ?
    ├─ YES → ❌ REJECT execution, return error with details
    └─ NO  → ✅ Proceed to execute in sandbox
```

### Code Location (`mcp_server.py`):
```python
# Lines 384-506 in execute_code()
if CODE_FILTER_ENABLED:
    code_filter = get_code_filter()
    if code_filter:
        logger.info("🛡️ Running LLM security review before execution...")
        
        review_result = await asyncio.wait_for(
            asyncio.to_thread(code_filter.review_code, code),
            timeout=30.0
        )
        
        if review_result.decision == "reject":
            # CODE REJECTED - raise detailed error
            raise ValueError(error_message)
        else:
            logger.info("✅ CODE APPROVED by LLM filter")
```

### What It Detects:
- File system manipulation (`os`, `shutil`)
- Network operations (`socket`, `urllib`, `requests`)
- Process execution (`subprocess`, `os.system`)
- Cryptocurrency mining keywords
- Data exfiltration patterns
- Code obfuscation attempts

### Logging:
- All reviews logged to: `llm_reviews.json`
- Accessible via dashboard: `/api/llm/reviews`

---

## 🤖 Layer 2: Runtime ML Monitoring (Random Forest)

**Location**: `monitor.py` lines 782-880  
**Model**: Random Forest Classifier (scikit-learn)  
**Trigger**: Every 1 second for running containers

### When It Runs:
- Continuously monitors ALL running sandbox containers
- Independent background task started by MCP server (line 1298-1302)
- Analyzes time-series behavior patterns

### Flow:
```
Container starts executing code
    ↓
Monitor collects metrics every 1 second
    ↓
After 8 samples collected (8 seconds)
    ↓
🤖 ML Model Analysis
    ├─ Extract 19 time-series features
    ├─ CPU patterns (mean, std, sustained load)
    ├─ Memory trends
    ├─ Network activity
    ├─ Log pattern analysis
    └─ Random Forest prediction
    ↓
Prediction = "mining" AND confidence >= 85%?
    ├─ YES → 🚨 Alert + Auto-kill (if enabled)
    └─ NO  → Continue monitoring
```

### Code Location (`monitor.py`):
```python
# Lines 1120-1133 in collect_all_metrics()
if self.ml_detector and self.ml_detector.model:
    ml_alert = await self._check_ml_mining(metrics)
    if ml_alert:
        self.network_alerts.append(ml_alert)
        logger.error(ml_alert.message)
```

```python
# Lines 782-880: _check_ml_mining() method
async def _check_ml_mining(self, metrics: ContainerMetrics):
    # Need 8+ samples for prediction
    if len(history) < ML_MINING_MIN_SAMPLES:
        return None
    
    # Extract features
    features = self.ml_detector.extract_features(metrics_dicts, log_text)
    prediction, confidence = self.ml_detector.predict(features)
    
    # Act on high-confidence predictions
    if prediction == "mining" and confidence >= 0.85:
        # Create alert
        alert = NetworkAlert(...)
        
        # Auto-kill if enabled
        if ML_MINING_AUTO_KILL:
            await container.kill()
```

### Features Analyzed (19 total):
1. `cpu_mean` - Average CPU usage
2. `cpu_std` - CPU standard deviation
3. `cpu_max` - Maximum CPU spike
4. `cpu_min` - Minimum CPU usage
5. `cpu_trend` - CPU trend direction
6. `cpu_sustained_high` - % time above 80%
7. `cpu_sustained_moderate` - % time above 50%
8. `mem_mean` - Average memory usage
9. `mem_std` - Memory standard deviation
10. `mem_trend` - Memory trend
11. `net_rx_rate_mean` - Network receive rate
12. `net_tx_rate_mean` - Network transmit rate
13. `net_total_bytes` - Total network bytes
14. `net_variance` - Network variance
15. `block_read_rate` - Disk read rate
16. `block_write_rate` - Disk write rate
17. `execution_duration` - How long running
18. `sample_count` - Number of samples
19. `output_repetition_score` - Log repetition (mining indicator)

### What It Detects:
- **Sustained high CPU usage** - Mining loops
- **Repetitive log patterns** - Hash calculation output
- **Moderate but consistent CPU** - Stealthy mining
- **Combined CPU + network patterns** - Pool mining
- **Time-series anomalies** - Unusual behavior

### Configuration (`monitor.py` lines 46-71):
```python
# High CPU mining
CPU_MINING_THRESHOLD = 85
CPU_MINING_DURATION = 10
CPU_MINING_AUTO_KILL = False  # Currently disabled

# Moderate CPU mining (stealthy)
CPU_MODERATE_THRESHOLD = 50
CPU_MODERATE_DURATION = 30
CPU_MODERATE_AUTO_KILL = False  # Currently disabled

# ML detection
ML_MINING_CONFIDENCE_THRESHOLD = 0.85  # 85% confidence
ML_MINING_AUTO_KILL = False  # Currently disabled
ML_MINING_MIN_SAMPLES = 8  # 8 seconds of data
```

---

## 📊 Complete Execution Flow

### Example: User executes code via `execute_python`

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Request                                             │
│    Tool: execute_python                                     │
│    Sandbox: abc123                                          │
│    Code: "while True: hash(...)"                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. MCP Server (mcp_server.py)                              │
│    • Receives request                                       │
│    • Validates sandbox ownership                            │
│    • Calls: SandboxManager.execute_code()                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. 🛡️ LAYER 1: LLM Pre-Execution Filter                    │
│    • Import: from code_safety_filter import get_filter     │
│    • Model: Llama 3.1 via Ollama                           │
│    • Timeout: 30 seconds                                    │
│    • Analysis: Check for malicious patterns                 │
│    Decision?                                                │
│      ├─ REJECT → Return error, stop execution              │
│      └─ ACCEPT → Continue to execution                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Code Execution in Sandbox                                │
│    • POST to http://localhost:{port}/execute                │
│    • Container runs code with resource limits               │
│    • CPU: 50%, Memory: 512MB                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. 🤖 LAYER 2: ML Runtime Monitoring                       │
│    • Monitor runs in background (started at server init)    │
│    • Collects metrics every 1 second                        │
│    • After 8 seconds:                                       │
│      └─ Extract 19 features from time-series               │
│      └─ Random Forest prediction                            │
│      └─ If mining detected (85%+ conf):                    │
│          ├─ Create alert                                    │
│          ├─ Log to network_alerts                           │
│          └─ Kill container (if auto-kill enabled)          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Return Results                                           │
│    • Normal: stdout, stderr, plots                          │
│    • Crashed: Crash report with logs                        │
│    • Mining Detected: Mining alert message                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Current Configuration Status

### LLM Filter (Ollama):
- ✅ **Enabled**: `CODE_FILTER_ENABLED = True` (if Ollama available)
- ✅ **Active for**: `execute_python` AND `execute_from_url`
- ✅ **Logs to**: `llm_reviews.json`
- ⚙️ **Timeout**: 30 seconds
- ⚙️ **Fallback**: If LLM fails, code proceeds with warning

### ML Model (Random Forest):
- ✅ **Enabled**: `MONITORING_ENABLED = True` (if monitor.py imported)
- ✅ **Active for**: All running sandbox containers
- ✅ **Model loaded**: If `models/mining_detector.pkl` exists
- ⚙️ **Sample requirement**: 8 seconds of metrics (8 samples)
- ⚙️ **Confidence threshold**: 85% for action
- ⚠️ **Auto-kill**: Currently **DISABLED** (all auto-kill flags = False)

### Auto-Kill Settings (monitor.py):
```python
CPU_MINING_AUTO_KILL = False          # Line 42
CPU_MODERATE_AUTO_KILL = False        # Line 48
ML_MINING_AUTO_KILL = False           # Line 63
RUNTIME_CHECK_ENABLED = False         # Line 69
```

**Note**: All auto-kill features are currently disabled for safety. Alerts are logged but containers are not automatically terminated.

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `mcp_server.py` | MCP server, LLM filter integration |
| `monitor.py` | ML monitoring, feature extraction |
| `ml_mining_detector.py` | Random Forest model, prediction logic |
| `code_safety_filter.py` | Ollama LLM integration |
| `models/mining_detector.pkl` | Trained Random Forest model |
| `models/scaler.pkl` | Feature scaler for ML |
| `llm_reviews.json` | LLM review history |
| `dashboard_server.py` | Monitoring dashboard API |
| `dashboard.html` | Real-time monitoring UI |

---

## 🔍 Verification Checklist

### To verify both layers are working:

#### LLM Filter:
1. ✅ Check Ollama is running: `curl http://localhost:11434/api/tags`
2. ✅ Check filter loaded: Look for "🛡️ LLM Code Filter: Enabled" in server logs
3. ✅ Test rejection: Execute obvious malicious code (e.g., `os.system('rm -rf /')`)
4. ✅ Check logs: Verify entries in `llm_reviews.json`
5. ✅ Dashboard: View reviews at `http://localhost:8080/api/llm/reviews`

#### ML Model:
1. ✅ Check model exists: `ls -lh models/mining_detector.pkl`
2. ✅ Check monitor loaded: Look for "🤖 ML mining detector loaded" in logs
3. ✅ Test detection: Execute mining-like code (sustained high CPU)
4. ✅ Check predictions: Look for "🤖 ML Prediction" in logs (after 8 seconds)
5. ✅ Dashboard: View alerts at `http://localhost:8080/api/alerts`

---

## 🎯 Summary

### Both Security Layers Are Active:

✅ **execute_python** → Goes through LLM filter (line 965-967) → Monitored by ML  
✅ **execute_from_url** → Goes through LLM filter (line 1085-1087) → Monitored by ML

### Defense-in-Depth Strategy:

1. **Pre-execution (LLM)**: Catch obvious threats before they run
2. **Runtime (ML)**: Detect subtle behavioral patterns during execution
3. **Combined**: If LLM misses something, ML catches it; if ML needs time to detect, LLM already blocked obvious threats

### Why Both Are Needed:

- **LLM**: Fast, blocks obvious threats immediately, but can be fooled by obfuscation
- **ML**: Detects actual behavior patterns, harder to evade, but needs runtime data

Together they provide comprehensive protection! 🛡️

