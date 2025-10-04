# 🚀 Setup Guide - A10 Hackathon Dashboard

Complete setup guide for running the dashboard with Fly.io, Prisma, and GitHub OAuth.

## Prerequisites

- Python 3.10+
- Poetry
- Docker Desktop
- GitHub account

## Quick Start (5 Minutes)

### 1. Clone and Install

```bash
cd /path/to/a10-hackathon
poetry install
```

### 2. Configure Environment

```bash
# Copy example
cp .env.example .env

# Edit .env and add:
# - GITHUB_CLIENT_ID (from GitHub OAuth app)
# - GITHUB_CLIENT_SECRET (from GitHub OAuth app)
# - SESSION_SECRET (generate with: openssl rand -hex 32)
# - DATABASE_URL (from Prisma/Neon)
# - ENABLE_AUTH="true"
```

### 3. Setup GitHub OAuth

1. Go to https://github.com/settings/developers
2. New OAuth App:
   - Homepage: `http://localhost:8080`
   - Callback: `http://localhost:8080/auth/callback`
3. Copy Client ID & Secret to `.env`

### 4. Setup Database (Prisma)

Your DATABASE_URL is already configured!

```bash
# Generate Prisma Client
poetry run prisma generate --schema=prisma/schema.prisma

# Create tables
poetry run prisma db push --schema=prisma/schema.prisma
```

### 5. Run Dashboard

```bash
poetry run python dashboard_server.py
```

Visit http://localhost:8080 🎉

## Using the Dashboard

1. **Login** with GitHub (top-right button)
2. **Generate API Token** (API Tokens tab)
3. **Configure Claude** with your token
4. **Monitor containers** in real-time

## Install MCP in Claude Desktop

```bash
./install_mcp_interactive.sh
```

Follow the prompts to configure authentication and settings!

## Deploy to Fly.io

```bash
./deploy_flyio.sh
```

See `DEPLOY_FLYIO.md` for details.

## Documentation

- **SETUP_GUIDE.md** (this file) - Quick start
- **DEPLOY_FLYIO.md** - Production deployment
- **GITHUB_OAUTH_SETUP.md** - OAuth configuration
- **SETUP_AUTH.md** - Authentication details
- **AUTH_ARCHITECTURE.md** - How auth works
- **QUICK_COMMANDS.md** - Command reference
- **README.md** - Project overview

## Troubleshooting

See individual guides for detailed troubleshooting.

Quick fixes:
- Hard refresh browser (Cmd+Shift+R)
- Check `.env` file exists and has all variables
- Restart dashboard after `.env` changes
- Check logs: `tail -f logs/dashboard.log`

🎉 That's it!
