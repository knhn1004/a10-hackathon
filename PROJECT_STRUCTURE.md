# Project Structure

## 🚀 Deployment Files (Use These Tomorrow)

### Production Ready
- **`deploy.sh`** ⭐ - One-command deployment for VPS (DigitalOcean, AWS, etc.)
- **`PRODUCTION_DEPLOYMENT.md`** ⭐ - Complete deployment guide
- **`READY_FOR_DEPLOYMENT.md`** ⭐ - Tomorrow's checklist and summary

### Alternative: Fly.io
- **`deploy_flyio.sh`** - Deploy to Fly.io
- **`fly.toml`** - Fly.io configuration
- **`DEPLOY_FLYIO.md`** - Fly.io deployment guide
- **`FLYIO_SETUP_COMPLETE.md`** - Fly.io setup docs
- **`Dockerfile.dashboard`** - Dashboard Docker image

---

## 🏗️ Core Application Files

### Main Services
- **`auth_proxy.py`** ⭐ - Multi-user authentication proxy (port 8000)
- **`mcp_server.py`** ⭐ - MCP server with sandbox tools
- **`dashboard_server.py`** ⭐ - Token management & analytics (port 8080)
- **`dashboard.html`** - Dashboard UI
- **`monitor.py`** - Container monitoring service

### Security & ML
- **`code_safety_filter.py`** - LLM-based code safety filter
- **`ml_mining_detector.py`** - Cryptocurrency mining detection
- **`ml_temporal_detector.py`** - Temporal pattern anomaly detection
- **`train_model.py`** - Train ML models
- **`collect_training_data.py`** - Collect training data for ML

### Database
- **`token_manager_prisma.py`** - Token management with Prisma
- **`database/prisma_client.py`** - Prisma database client
- **`prisma/schema.prisma`** - Database schema

---

## 📝 Documentation (Keep for Reference)

### Primary Docs
- **`README.md`** - Main project readme
- **`LOCAL_SETUP.md`** - Local development setup
- **`MCP_README.md`** - MCP-specific documentation

### Deployment Guides
- **`MULTI_USER_DEPLOYMENT.md`** - Multi-user architecture explained
- **`CLOUDFLARE_ISSUE.md`** - Why Cloudflare tunnel doesn't work for ChatGPT

### Setup Guides
- **`DASHBOARD_GUIDE.md`** - Dashboard usage
- **`ML_DETECTION_README.md`** - ML detection system
- **`SETUP_AUTH.md`** - Authentication setup
- **`SETUP_GUIDE.md`** - General setup guide
- **`SECURITY_FLOW.md`** - Security flow documentation
- **`GITHUB_OAUTH_SETUP.md`** - GitHub OAuth setup
- **`QUICK_COMMANDS.md`** - Quick command reference

---

## 🛠️ Setup & Installation Scripts

### Local Development
- **`quickstart.sh`** - Quick local setup
- **`install_mcp.sh`** - Install MCP for Claude Desktop (macOS/Linux)
- **`install_mcp.bat`** - Install MCP for Claude Desktop (Windows)
- **`run_dashboard.sh`** - Run dashboard standalone
- **`run_with_cloudflare.sh`** - Run with Cloudflare tunnel (has ChatGPT issues)
- **`RESTART_SERVICES.sh`** - Restart all services
- **`setup_llm_filter.sh`** - Setup LLM code filter

### Testing
- **`test_auth_proxy.sh`** - Test authentication proxy
- **`sandbox_server.py`** - Sandbox server for testing
- **`ollama_mcp_client.py`** - Test client for MCP

---

## 🐳 Docker & Configuration

- **`Dockerfile`** - Main Docker image for code sandboxes
- **`Dockerfile.dashboard`** - Dashboard Docker image
- **`mcp_config.json`** - MCP configuration
- **`claude_desktop_config.example.json`** - Claude Desktop config example
- **`pyproject.toml`** - Python dependencies
- **`poetry.lock`** - Locked Python dependencies
- **`requirements-llm-filter.txt`** - LLM filter requirements

---

## 📊 Data & Models

### Directories
- **`data/`** - Training data for ML models
- **`models/`** - Trained ML models
  - `mining_detector.pkl` - Mining detection model
  - `scaler.pkl` - Data scaler for ML
- **`logs/`** - Application logs
  - `auth_proxy.log`
  - `dashboard.log`
  - `mcpo.log`
  - `mcp.log`
  - `monitor.log`
  - `cloudflare.log`
- **`database/`** - Database files
- **`prisma/`** - Prisma ORM files and migrations

---

## 🎯 What to Use Tomorrow

**For VPS Deployment (Recommended):**
1. `deploy.sh` - Run this on your server
2. `PRODUCTION_DEPLOYMENT.md` - Follow this guide
3. `READY_FOR_DEPLOYMENT.md` - Your checklist

**For Fly.io Deployment (Alternative):**
1. `deploy_flyio.sh` - Run this locally
2. `DEPLOY_FLYIO.md` - Follow this guide

**Core files that will run:**
- `auth_proxy.py` - Handles ChatGPT requests
- `mcp_server.py` - Executes code in sandboxes
- `dashboard_server.py` - Manages user tokens

---

## 🗑️ Cleaned Up (Removed Today)

- `mcp_http_server.py` - Abandoned HTTP server attempt
- `mcp_rest_server.py` - Abandoned REST server attempt
- `openapi_with_auth.json` - Manual file, not needed
- `run_mcpo.sh` - Replaced by deploy.sh
- `CHATGPT_SETUP.md` - Redundant with production docs
- `CLOUDFLARE_OUTPUT_FIX.md` - Historical fixes
- `CLOUDFLARE_QUICKSTART.txt` - Cloudflare has issues
- `CLOUDFLARE_TUNNEL_SETUP.md` - Cloudflare has issues
- `FIXES_APPLIED.md` - Historical fixes
- `QUICK_CHATGPT_GUIDE.txt` - Redundant
- `MULTI_USER_AUTH.md` - Covered in deployment docs

---

## 📦 File Count Summary

- **Core Application:** 15 files
- **Documentation:** 14 files
- **Setup Scripts:** 11 files
- **Configuration:** 6 files
- **Deployment:** 5 files

**Total:** ~51 essential files (cleaned from ~62)

---

## 🎯 Quick Reference

**Deploy to VPS:** `./deploy.sh`
**Test locally:** `./test_auth_proxy.sh`
**Run dashboard:** `./run_dashboard.sh`
**Quick setup:** `./quickstart.sh`

All ready for tomorrow's deployment! 🚀

