# 🛡️ LLM Filter Dashboard Logging

## Overview

All LLM code review results are now **prominently logged** in the dashboard output, making it easy to monitor security decisions in real-time.

## What You'll See

### When Dashboard Starts

```
INFO:dashboard:Starting dashboard server on http://0.0.0.0:8080
INFO:dashboard:🤖 Ollama not running, attempting to start...
INFO:dashboard:🤖 Starting Ollama server...
INFO:dashboard:✅ Ollama server started successfully
INFO:dashboard:🤖 Checking for llama3.1:latest model...
INFO:dashboard:✅ llama3.1:latest model available
INFO:code_safety_filter:🛡️ Code safety filter initialized with llama3.1:latest
INFO:code_safety_filter:   Model: llama3.1:latest
INFO:code_safety_filter:   Ollama URL: http://localhost:11434
INFO:monitor:🤖 ML mining detector loaded successfully
INFO:dashboard:Dashboard server started, monitoring active
```

### When Safe Code is Reviewed (ACCEPTED)

```
INFO:code-sandbox-mcp:🛡️ Running LLM security review before execution...
INFO:code-sandbox-mcp:   Container: sandbox_abc123
INFO:code-sandbox-mcp:   Code length: 247 bytes
INFO:code-sandbox-mcp:🤖 LLM Review Result:
INFO:code-sandbox-mcp:   Decision: ACCEPT
INFO:code-sandbox-mcp:   Confidence: 95.0%
INFO:code-sandbox-mcp:✅ CODE APPROVED by LLM filter for sandbox sandbox_abc123
INFO:code-sandbox-mcp:   Confidence: 95.0%
INFO:code-sandbox-mcp:Executing code in sandbox: sandbox_abc123
```

### When Malicious Code is Detected (REJECTED)

```
INFO:code-sandbox-mcp:🛡️ Running LLM security review before execution...
INFO:code-sandbox-mcp:   Container: sandbox_xyz789
INFO:code-sandbox-mcp:   Code length: 312 bytes
INFO:code-sandbox-mcp:🤖 LLM Review Result:
INFO:code-sandbox-mcp:   Decision: REJECT
INFO:code-sandbox-mcp:   Confidence: 98.0%
INFO:code-sandbox-mcp:   Threats: crypto_mining, resource_exhaustion, infinite_loop
INFO:code-sandbox-mcp:   Reasons: Implements proof-of-work mining algorithm; Infinite loop with hash calculations
ERROR:code-sandbox-mcp:❌ CODE REJECTED by LLM filter for sandbox sandbox_xyz789
ERROR:code-sandbox-mcp:   Threats: crypto_mining, resource_exhaustion, infinite_loop
```

## Log Levels

### INFO (Normal Operations)
- ✅ Filter initialization
- 🛡️ Starting review
- 🤖 Review results
- ✅ Code approved

### ERROR (Security Rejections)
- ❌ Code rejected
- 🚨 Threats detected

### DEBUG (Detailed Info)
- LLM raw responses
- Internal processing details

## Log Format

Each LLM review produces a structured log entry:

```
🛡️ Running LLM security review before execution...
   Container: <sandbox_id>
   Code length: <bytes>

🤖 LLM Review Result:
   Decision: ACCEPT/REJECT
   Confidence: <percentage>
   [Threats: <threat_list>]          # Only if detected
   [Reasons: <reason_summary>]       # Only if rejected

✅ CODE APPROVED / ❌ CODE REJECTED
   Confidence: <percentage>
   [Threats: <detailed_list>]        # Only if rejected
```

## Where to See Logs

### 1. **Dashboard Terminal**
When you run:
```bash
python dashboard_server.py
```

All logs appear in your terminal in real-time.

### 2. **MCP Server Output**
If running the MCP server standalone:
```bash
python mcp_server.py
```

Logs appear in the MCP server output.

### 3. **Container Logs**
Check container execution logs:
```bash
docker logs <container_name>
```

## Testing the Logs

Run the test script to see example outputs:

```bash
python test_llm_logging.py
```

This demonstrates:
- ✅ Safe code being accepted
- ❌ Mining code being rejected
- 📊 Full log format

## Understanding the Logs

### Safe Code Flow
```
🛡️ Starting review
    ↓
🤖 LLM analyzes code
    ↓
✅ Decision: ACCEPT (95% confidence)
    ↓
⚡ Execute in container
```

### Malicious Code Flow
```
🛡️ Starting review
    ↓
🤖 LLM analyzes code
    ↓
❌ Decision: REJECT (98% confidence)
    ↓
🚨 Threats: crypto_mining, infinite_loop
    ↓
🛑 Execution blocked
    ↓
📤 Error message sent to user
```

## Log Analysis Tips

### Look for Patterns

**High rejection rate:**
```bash
grep "CODE REJECTED" dashboard.log | wc -l
```

**Confidence distribution:**
```bash
grep "Confidence:" dashboard.log
```

**Common threats:**
```bash
grep "Threats:" dashboard.log | sort | uniq -c
```

### Real-time Monitoring

Monitor logs as they happen:
```bash
python dashboard_server.py 2>&1 | grep -E "🛡️|🤖|✅|❌"
```

### Filter Specific Events

Only LLM decisions:
```bash
python dashboard_server.py 2>&1 | grep "LLM Review Result"
```

Only rejections:
```bash
python dashboard_server.py 2>&1 | grep "CODE REJECTED"
```

## Example Session

```
# Dashboard startup
INFO:dashboard:Starting dashboard server on http://0.0.0.0:8080
INFO:dashboard:✅ Ollama already running
INFO:code_safety_filter:🛡️ Code safety filter initialized with llama3.1:latest

# User submits safe code
INFO:code-sandbox-mcp:🛡️ Running LLM security review before execution...
INFO:code-sandbox-mcp:🤖 LLM Review Result:
INFO:code-sandbox-mcp:   Decision: ACCEPT
INFO:code-sandbox-mcp:   Confidence: 92.0%
INFO:code-sandbox-mcp:✅ CODE APPROVED by LLM filter for sandbox sandbox_abc123

# User submits mining code
INFO:code-sandbox-mcp:🛡️ Running LLM security review before execution...
INFO:code-sandbox-mcp:🤖 LLM Review Result:
INFO:code-sandbox-mcp:   Decision: REJECT
INFO:code-sandbox-mcp:   Confidence: 99.0%
INFO:code-sandbox-mcp:   Threats: crypto_mining, infinite_loop
ERROR:code-sandbox-mcp:❌ CODE REJECTED by LLM filter for sandbox sandbox_xyz789
ERROR:code-sandbox-mcp:   Threats: crypto_mining, infinite_loop

# User submits another safe code
INFO:code-sandbox-mcp:🛡️ Running LLM security review before execution...
INFO:code-sandbox-mcp:🤖 LLM Review Result:
INFO:code-sandbox-mcp:   Decision: ACCEPT
INFO:code-sandbox-mcp:   Confidence: 88.0%
INFO:code-sandbox-mcp:✅ CODE APPROVED by LLM filter for sandbox sandbox_abc123
```

## Integration with Existing Logs

LLM filter logs appear **alongside** existing monitoring logs:

```
INFO:monitor:🔍 Checking running container: sandbox_abc123 CPU=5.2%
INFO:code-sandbox-mcp:🛡️ Running LLM security review before execution...
INFO:code-sandbox-mcp:✅ CODE APPROVED by LLM filter for sandbox sandbox_abc123
INFO:monitor:🤖 ML Prediction for sandbox_abc123: normal (confidence=92.0%)
INFO:monitor:Cleaning up 1 removed containers from metrics history
```

## Disabling Verbose Logs

If you want quieter logs, set log level to WARNING:

```python
# In dashboard_server.py or mcp_server.py
logging.basicConfig(level=logging.WARNING)
```

Then you'll only see:
- ❌ Rejections (ERROR level)
- ⚠️ Warnings

## Log Persistence

### Save to File

```bash
python dashboard_server.py 2>&1 | tee dashboard.log
```

### Rotate Logs

```bash
python dashboard_server.py 2>&1 | tee -a logs/dashboard_$(date +%Y%m%d_%H%M%S).log
```

### Parse Later

```bash
# Extract all LLM decisions
grep "LLM Review Result" dashboard.log > llm_decisions.txt

# Count accepts vs rejects
grep "CODE APPROVED" dashboard.log | wc -l
grep "CODE REJECTED" dashboard.log | wc -l
```

## Troubleshooting

### Logs Not Appearing?

1. **Check log level:**
   ```python
   logging.basicConfig(level=logging.INFO)  # Not WARNING or ERROR
   ```

2. **Check Ollama is running:**
   ```bash
   curl http://localhost:11434/api/tags
   ```

3. **Check filter is enabled:**
   ```python
   # In mcp_server.py
   print(f"CODE_FILTER_ENABLED: {CODE_FILTER_ENABLED}")
   ```

### Too Many Logs?

Filter to specific events:
```bash
python dashboard_server.py 2>&1 | grep -v "GET /api"
```

## Summary

✅ **All LLM decisions are now visible in dashboard logs**
✅ **Structured, easy-to-read format**
✅ **Color-coded with emojis for quick scanning**
✅ **Integrated with existing monitoring logs**
✅ **Filterable and parseable for analysis**

Your security is now **fully transparent**! 🛡️

