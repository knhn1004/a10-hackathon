# GitHub OAuth Setup Guide

Quick guide to setting up GitHub OAuth for local development.

## Step 1: Create GitHub OAuth App

1. Go to https://github.com/settings/developers
2. Click **"OAuth Apps"** in the left sidebar
3. Click **"New OAuth App"**

## Step 2: Fill in Application Details

### For Local Development

```
Application name: A10 Hackathon Dashboard (Local)
Homepage URL: http://localhost:8080
Authorization callback URL: http://localhost:8080/auth/callback
Application description: (optional) Code sandbox monitoring dashboard
```

Click **"Register application"**

### For Production (Fly.io)

Create a SEPARATE OAuth app for production:

```
Application name: A10 Hackathon Dashboard (Production)
Homepage URL: https://your-app-name.fly.dev
Authorization callback URL: https://your-app-name.fly.dev/auth/callback
Application description: (optional) Code sandbox monitoring dashboard
```

⚠️ **Important:** Use separate OAuth apps for dev and prod!

## Step 3: Get Credentials

After creating the app, you'll see:

- **Client ID**: `Iv1.abc123def456...`
- Click **"Generate a new client secret"**
- **Client Secret**: `ghp_abc123xyz...`

⚠️ **Copy the Client Secret now** - you won't see it again!

## Step 4: Update .env File

```bash
# Copy the example
cp .env.example .env

# Edit .env and add your credentials
```

Add to `.env`:

```bash
# GitHub OAuth (Local Development)
GITHUB_CLIENT_ID="Iv1.abc123def456..."
GITHUB_CLIENT_SECRET="ghp_abc123xyz..."
SESSION_SECRET="your_random_32_byte_string"
ENABLE_AUTH="true"
```

Generate session secret:
```bash
openssl rand -hex 32
```

## Step 5: Test Locally

```bash
# Start dashboard
poetry run python dashboard_server.py

# Visit http://localhost:8080
# Click "Sign in with GitHub"
# Should redirect to GitHub, then back to your dashboard
```

## Step 6: Production Setup (Fly.io)

```bash
# Use the PRODUCTION OAuth app credentials
fly secrets set GITHUB_CLIENT_ID="Iv1.prod_client_id..."
fly secrets set GITHUB_CLIENT_SECRET="ghp_prod_secret..."
fly secrets set SESSION_SECRET="$(openssl rand -hex 32)"
fly secrets set ENABLE_AUTH="true"

# Deploy
fly deploy
```

## Callback URL Reference

| Environment | Homepage URL | Callback URL |
|-------------|--------------|--------------|
| **Local Dev** | `http://localhost:8080` | `http://localhost:8080/auth/callback` |
| **Fly.io** | `https://your-app.fly.dev` | `https://your-app.fly.dev/auth/callback` |
| **Custom Domain** | `https://dashboard.yourdomain.com` | `https://dashboard.yourdomain.com/auth/callback` |

## Troubleshooting

### "Redirect URI mismatch" Error

Check that your callback URL in GitHub OAuth app matches **exactly**:
- ✅ `http://localhost:8080/auth/callback`
- ❌ `http://localhost:8080/callback`
- ❌ `http://127.0.0.1:8080/auth/callback`
- ❌ `http://localhost:8080/auth/callback/`

### "Client ID/Secret not found"

Make sure you:
1. Created the OAuth app
2. Generated a client secret
3. Copied both to `.env`
4. Restarted the dashboard server

### Login Loop

Check:
1. SESSION_SECRET is set and random
2. Cookies are enabled in browser
3. Try clearing cookies: `http://localhost:8080/logout`

### Still Not Working?

Check dashboard logs:
```bash
tail -f logs/dashboard.log
```

Look for OAuth errors and check:
- Client ID matches
- Client Secret is correct
- Callback URL matches exactly

## Testing

After setup, you should be able to:

1. ✅ Visit `http://localhost:8080`
2. ✅ See login page
3. ✅ Click "Sign in with GitHub"
4. ✅ Redirect to GitHub
5. ✅ Approve access
6. ✅ Redirect back to dashboard
7. ✅ See dashboard (logged in!)

## Security Notes

- 🔒 Never commit `.env` to git
- 🔒 Use separate OAuth apps for dev/prod
- 🔒 Rotate secrets periodically
- 🔒 Use HTTPS in production
- 🔒 Keep client secrets secret!

## Quick Reference

```bash
# Local development
GITHUB_CLIENT_ID="Iv1.abc123..."
GITHUB_CLIENT_SECRET="ghp_abc123..."
SESSION_SECRET="$(openssl rand -hex 32)"
ENABLE_AUTH="true"

# Production (Fly.io secrets)
fly secrets set GITHUB_CLIENT_ID="..."
fly secrets set GITHUB_CLIENT_SECRET="..."
fly secrets set SESSION_SECRET="$(openssl rand -hex 32)"
fly secrets set ENABLE_AUTH="true"
```

That's it! 🎉
