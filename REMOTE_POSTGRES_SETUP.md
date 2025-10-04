# 🌐 Remote PostgreSQL Setup

Use a **hosted PostgreSQL** database for both local development and production! No Docker needed! 🎉

## Why Remote PostgreSQL?

✅ **Same database everywhere** - Local dev uses production-like setup  
✅ **No Docker required** - Works on any machine  
✅ **Free tiers available** - Neon, Supabase, Railway  
✅ **Instant backups** - Managed by the provider  
✅ **Better performance** - Optimized infrastructure  

## Quick Start

### 1. Get a PostgreSQL Database

Choose one of these providers (all have free tiers):

#### Option A: Neon.tech (Recommended) ⭐

**Why Neon:**
- 🆓 Free tier with 0.5GB storage
- ⚡ Serverless (scales to zero)
- 🌍 Global edge network
- 🔄 Instant branching (dev/staging/prod)

**Setup:**
1. Go to https://neon.tech
2. Sign up with GitHub
3. Create a new project
4. Copy connection string: `postgresql://user:pass@ep-xxx.neon.tech/dbname`

#### Option B: Supabase

**Why Supabase:**
- 🆓 Free tier with 500MB storage
- 🎁 Includes auth, storage, real-time
- 📊 Built-in pgAdmin-like UI

**Setup:**
1. Go to https://supabase.com
2. Create new project
3. Go to Settings → Database
4. Copy connection string (Transaction mode)

#### Option C: Railway

**Why Railway:**
- 🆓 $5/month free credits
- 🚂 Great for full-stack apps
- 📦 Can host your app + database

**Setup:**
1. Go to https://railway.app
2. New Project → PostgreSQL
3. Copy connection string from Variables tab

#### Option D: Fly.io Postgres

**Why Fly.io:**
- 💰 Free tier (3 VMs)
- 🌐 Global deployment
- 🔗 Same platform as your app

**Setup:**
```bash
# Create Postgres cluster
fly postgres create --name a10-db --region sjc

# Get connection string
fly postgres connect -a a10-db
```

### 2. Update .env File

```bash
# Copy example
cp .env.example .env

# Edit .env and add your connection string
DATABASE_URL="postgresql+asyncpg://user:pass@host:port/dbname"
```

**Important:** Add `+asyncpg` after `postgresql` for async support!

**Example:**
```bash
# Neon
DATABASE_URL="postgresql+asyncpg://oliver:pass123@ep-cool-sunset-123.us-east-1.aws.neon.tech/a10_hackathon"

# Supabase
DATABASE_URL="postgresql+asyncpg://postgres:pass123@db.abcdefgh.supabase.co:5432/postgres"

# Railway
DATABASE_URL="postgresql+asyncpg://postgres:pass123@containers-us-west1.railway.app:5432/railway"
```

### 3. Install Dependencies

```bash
poetry install
```

### 4. Run Migrations

```bash
# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply to database
alembic upgrade head
```

### 5. Verify Connection

```bash
python -c "
import asyncio
from database import check_db_connection
result = asyncio.run(check_db_connection())
print('✅ Connected to database!' if result else '❌ Connection failed')
"
```

### 6. Migrate Data (Optional)

```bash
# If you have existing JSON data
python migrate_json_to_postgres.py --dry-run  # Preview
python migrate_json_to_postgres.py            # Migrate
```

### 7. Start Dashboard

```bash
python dashboard_server.py
```

## Managing Multiple Environments

### Development, Staging, Production

Use different connection strings for each environment:

**.env.local** (Local dev):
```bash
DATABASE_URL="postgresql+asyncpg://user:pass@dev-db.neon.tech/a10_dev"
```

**.env.staging** (Staging):
```bash
DATABASE_URL="postgresql+asyncpg://user:pass@staging-db.neon.tech/a10_staging"
```

**Production** (Set in Fly.io):
```bash
fly secrets set DATABASE_URL="postgresql://user:pass@prod-db.neon.tech/a10_prod"
```

### Neon Database Branching

Neon allows you to create instant database branches!

```bash
# Create branch for testing
neonctl branches create --name test-feature

# Get branch connection string
neonctl connection-string test-feature

# Use in .env for testing
DATABASE_URL="postgresql+asyncpg://user:pass@ep-branch-123.neon.tech/dbname"

# Delete branch when done
neonctl branches delete test-feature
```

## Connection String Format

### Basic Format

```
postgresql+asyncpg://username:password@host:port/database
```

### With SSL (Recommended)

```
postgresql+asyncpg://username:password@host:port/database?sslmode=require
```

### Full Options

```
postgresql+asyncpg://user:pass@host:port/db?sslmode=require&connect_timeout=10&command_timeout=5
```

**Common Options:**
- `sslmode=require` - Require SSL connection
- `connect_timeout=10` - Connection timeout (seconds)
- `command_timeout=5` - Query timeout (seconds)
- `pool_size=5` - Connection pool size
- `max_overflow=10` - Max extra connections

## Database Management UI

### Option 1: Provider's Built-in UI

Most providers include a database UI:
- **Neon**: SQL Editor in dashboard
- **Supabase**: Table Editor + SQL Editor
- **Railway**: Database UI
- **Fly.io**: Use Prisma Studio or pgAdmin

### Option 2: Prisma Studio (Recommended)

```bash
# Install Prisma CLI
npm install -g prisma

# Open Prisma Studio
npx prisma studio
```

### Option 3: pgAdmin (Desktop App)

1. Download from https://www.pgadmin.org/
2. Add new server with your connection string
3. Browse tables visually

### Option 4: psql (Command Line)

```bash
# Install PostgreSQL client
brew install postgresql  # macOS
sudo apt install postgresql-client  # Linux

# Connect
psql "postgresql://user:pass@host:port/dbname"

# List tables
\dt

# Query
SELECT * FROM users;
```

## Security Best Practices

### 1. Never Commit Connection Strings

```bash
# Add to .gitignore
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
echo ".env.*.local" >> .gitignore
```

### 2. Use Environment Variables

```python
# ✅ Good
DATABASE_URL = os.getenv("DATABASE_URL")

# ❌ Bad
DATABASE_URL = "postgresql://user:pass@host/db"
```

### 3. Rotate Passwords Regularly

Most providers let you reset passwords in their dashboard.

### 4. Use Read-Only Replicas

For analytics/reporting, use read-only connection strings.

### 5. Enable SSL

Always use `sslmode=require` in production.

## Troubleshooting

### "Connection refused"

Check:
1. ✅ Connection string is correct
2. ✅ `+asyncpg` is added to URL
3. ✅ Database exists
4. ✅ User has access
5. ✅ IP is whitelisted (if required)

### "SSL required"

Add to connection string:
```bash
DATABASE_URL="postgresql+asyncpg://...?sslmode=require"
```

### "Too many connections"

Adjust pool size in `database/connection.py`:
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,        # Max connections
    max_overflow=10,    # Extra connections
)
```

### "Slow queries"

1. Add indexes to frequently queried columns
2. Use `EXPLAIN ANALYZE` to optimize queries
3. Enable connection pooling
4. Consider read replicas

## Migration from Local to Remote

### Step 1: Export Local Data

```bash
# If you were using local PostgreSQL
pg_dump -h localhost -U postgres a10_hackathon > backup.sql
```

### Step 2: Import to Remote

```bash
# Restore to remote database
psql "postgresql://user:pass@host:port/dbname" < backup.sql
```

### Step 3: Update .env

```bash
# Change from local to remote
DATABASE_URL="postgresql+asyncpg://user:pass@remote-host:port/dbname"
```

## Cost Comparison

| Provider | Free Tier | Paid Plans Start |
|----------|-----------|------------------|
| **Neon** | 0.5GB | $19/month |
| **Supabase** | 500MB | $25/month |
| **Railway** | $5 credits | $5/month (usage) |
| **Fly.io** | 3 VMs | Usage-based |

For this project, **free tier is plenty!** 🎉

## Monitoring

### Check Database Size

```sql
SELECT 
    pg_size_pretty(pg_database_size('a10_hackathon')) as size;
```

### Check Table Sizes

```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Check Connection Count

```sql
SELECT 
    count(*) as connections
FROM pg_stat_activity
WHERE datname = 'a10_hackathon';
```

## Backup Strategy

### Automatic Backups

All providers offer automatic backups:
- **Neon**: Continuous (point-in-time recovery)
- **Supabase**: Daily backups (7-day retention)
- **Railway**: Daily snapshots
- **Fly.io**: Continuous backup

### Manual Backup

```bash
# Backup to file
pg_dump "postgresql://user:pass@host:port/db" > backup_$(date +%Y%m%d).sql

# Backup with compression
pg_dump "postgresql://..." | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Restore from Backup

```bash
# Restore
psql "postgresql://user:pass@host:port/db" < backup.sql

# Restore from compressed
gunzip -c backup.sql.gz | psql "postgresql://..."
```

## Production Deployment (Fly.io)

### Option 1: Use Fly.io Postgres

```bash
# Create database
fly postgres create --name a10-db

# Attach to app
fly postgres attach --app a10-dashboard --postgres-app a10-db

# DATABASE_URL is automatically set!
```

### Option 2: Use External Database (Neon/Supabase)

```bash
# Set connection string as secret
fly secrets set DATABASE_URL="postgresql://user:pass@neon.tech/db"

# Deploy
fly deploy
```

**Why use external database:**
- ✅ Better free tier
- ✅ Built-in backups
- ✅ Easier scaling
- ✅ One less thing to manage on Fly.io

## Summary

✅ **No Docker needed** - Use hosted PostgreSQL  
✅ **Same setup everywhere** - Local = Production  
✅ **Free tier sufficient** - 0.5-500MB included  
✅ **Managed backups** - Automated by provider  
✅ **Easy scaling** - Upgrade plan when needed  

**Recommended:** Start with **Neon.tech** for the best free tier! 🚀

## Next Steps

1. ✅ Sign up for Neon/Supabase/Railway
2. ✅ Get connection string
3. ✅ Update `.env` file
4. ✅ Run `alembic upgrade head`
5. ✅ Start building! 🎉

