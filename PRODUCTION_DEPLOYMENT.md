# Production Deployment Guide

## Overview
Deploy your MCP server to a cloud provider where ChatGPT can access it without Cloudflare bot blocking.

---

## Option 1: DigitalOcean Droplet (Easiest)

### Setup (5 minutes)
```bash
# 1. Create a droplet (Ubuntu 22.04, $6/month)
# 2. SSH into your droplet
ssh root@your-droplet-ip

# 3. Install dependencies
apt update && apt upgrade -y
apt install -y python3-pip docker.io git curl

# 4. Clone your repo
git clone https://github.com/yourusername/a10-hackathon.git
cd a10-hackathon

# 5. Install Python dependencies
pip3 install poetry
poetry install

# 6. Build Docker image
docker build -t code-sandbox:latest .

# 7. Start services
export MCP_API_TOKEN="your_token_here"  # Optional for local dashboard
./run_dashboard.sh &  # Dashboard on port 8080
python3 auth_proxy.py &  # Auth proxy on port 8000
```

### Access URLs
- Dashboard: `http://YOUR_DROPLET_IP:8080`
- MCP API: `http://YOUR_DROPLET_IP:8000`
- OpenAPI: `http://YOUR_DROPLET_IP:8000/openapi.json`

### ChatGPT Configuration
```
URL: http://YOUR_DROPLET_IP:8000/openapi.json
Auth: Bearer Token
Token: [User's personal token from dashboard]
```

### Optional: Add HTTPS with Let's Encrypt
```bash
apt install -y certbot nginx
# Configure nginx as reverse proxy
# Get SSL cert: certbot --nginx -d yourdomain.com
```

---

## Option 2: Railway (Easiest, Free Tier)

### Setup
1. Go to https://railway.app
2. Create new project → Deploy from GitHub
3. Add environment variables:
   ```
   PORT=8000
   DASHBOARD_URL=http://localhost:8080
   ```
4. Railway auto-deploys on push
5. Get public URL from Railway dashboard

### ChatGPT Configuration
```
URL: https://your-app.railway.app/openapi.json
Auth: Bearer Token
Token: [User's token]
```

---

## Option 3: Google Cloud Run (Serverless)

### Create Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install poetry && poetry install
RUN docker pull python:3.11-slim  # For sandboxes

EXPOSE 8000

CMD ["bash", "-c", "python3 dashboard_server.py & python3 auth_proxy.py"]
```

### Deploy
```bash
gcloud run deploy mcp-server \
  --source . \
  --port 8000 \
  --allow-unauthenticated \
  --region us-central1
```

### ChatGPT Configuration
```
URL: https://mcp-server-xxxxx-uc.a.run.app/openapi.json
```

---

## Option 4: AWS EC2 (Most Control)

### Launch Instance
1. Ubuntu 22.04 t3.micro (free tier)
2. Security Group: Allow ports 8000, 8080
3. Elastic IP for static address

### Setup
```bash
# Same as DigitalOcean steps
# Then configure nginx for HTTPS
```

---

## Option 5: Fly.io (Good for Docker)

### fly.toml
```toml
app = "mcp-server"

[build]
  dockerfile = "Dockerfile"

[[services]]
  internal_port = 8000
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]
  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]
```

### Deploy
```bash
fly launch
fly deploy
```

---

## Recommended Setup Script for Any VPS

Create `deploy.sh`:
```bash
#!/bin/bash
# Production deployment script

set -e

echo "🚀 Starting MCP Server Deployment"

# Build Docker image
docker build -t code-sandbox:latest .

# Start Dashboard
python3 dashboard_server.py > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "✅ Dashboard started (PID: $DASHBOARD_PID)"

# Wait for dashboard
sleep 3

# Get Python path
PYTHON_PATH=$(poetry env info -p)/bin/python

# Start MCPO backend (internal)
uvx mcpo --port 8001 -- "$PYTHON_PATH" mcp_server.py > logs/mcpo.log 2>&1 &
MCPO_PID=$!
echo "✅ MCPO started (PID: $MCPO_PID)"

# Wait for MCPO
sleep 3

# Start Auth Proxy (public)
python3 auth_proxy.py > logs/auth_proxy.log 2>&1 &
PROXY_PID=$!
echo "✅ Auth Proxy started (PID: $PROXY_PID)"

echo ""
echo "════════════════════════════════════════"
echo "✨ MCP Server Running!"
echo "════════════════════════════════════════"
echo ""
echo "📋 Services:"
echo "  • Dashboard: http://localhost:8080"
echo "  • Auth Proxy: http://localhost:8000"
echo "  • MCPO Backend: http://localhost:8001 (internal)"
echo ""
echo "🌐 Public URLs:"
echo "  • OpenAPI: http://YOUR_IP:8000/openapi.json"
echo "  • Dashboard: http://YOUR_IP:8080"
echo ""
echo "📊 Logs:"
echo "  • tail -f logs/auth_proxy.log"
echo "  • tail -f logs/mcpo.log"
echo "  • tail -f logs/dashboard.log"
echo ""
echo "🛑 To stop:"
echo "  kill $DASHBOARD_PID $MCPO_PID $PROXY_PID"
echo ""

# Keep script running
trap "echo ''; echo '🛑 Stopping services...'; kill $DASHBOARD_PID $MCPO_PID $PROXY_PID 2>/dev/null; exit 0" INT TERM
wait
```

Make it executable:
```bash
chmod +x deploy.sh
./deploy.sh
```

---

## Monitoring in Production

### Keep services running with PM2
```bash
npm install -g pm2

# Start services
pm2 start dashboard_server.py --name dashboard --interpreter python3
pm2 start auth_proxy.py --name proxy --interpreter python3

# Auto-restart on reboot
pm2 startup
pm2 save
```

### Check logs
```bash
pm2 logs dashboard
pm2 logs proxy
```

---

## Security Checklist

- [ ] Use HTTPS (Let's Encrypt or cloud provider SSL)
- [ ] Firewall: Only allow ports 80, 443, 8000, 8080
- [ ] Rate limiting on auth proxy
- [ ] Regular security updates
- [ ] Monitor logs for suspicious activity
- [ ] Backup dashboard database regularly

---

## Cost Comparison

| Provider | Cost | Setup Time | Ease |
|----------|------|------------|------|
| DigitalOcean | $6/mo | 10 min | ⭐⭐⭐⭐⭐ |
| Railway | Free tier | 5 min | ⭐⭐⭐⭐⭐ |
| Fly.io | ~$3/mo | 10 min | ⭐⭐⭐⭐ |
| GCP Cloud Run | Pay-per-use | 15 min | ⭐⭐⭐ |
| AWS EC2 | Free tier | 15 min | ⭐⭐⭐ |

---

## Testing After Deployment

```bash
# 1. Test OpenAPI endpoint
curl http://YOUR_IP:8000/openapi.json

# 2. Test authentication
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -X POST http://YOUR_IP:8000/create_sandbox \
     -H "Content-Type: application/json" -d '{}'

# 3. Configure in ChatGPT
# URL: http://YOUR_IP:8000/openapi.json
# Auth: Bearer Token
# Token: [from dashboard]

# 4. Test in ChatGPT
# Ask: "Create a Python sandbox and calculate factorial of 10"
```

---

## Next Steps

1. Choose a deployment platform (recommend DigitalOcean or Railway)
2. Deploy using steps above
3. Get public URL
4. Configure ChatGPT with the URL
5. Generate tokens from dashboard for each user
6. Test!

Your MCP server is ready to deploy! 🚀

