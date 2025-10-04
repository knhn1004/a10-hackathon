# 🚀 PostgreSQL Quick Start

Get your remote PostgreSQL database set up in **5 minutes**!

## Option 1: Automated Setup (Recommended)

```bash
# One command does everything!
./setup_remote_db.sh
```

This will:
1. ✅ Check your DATABASE_URL
2. ✅ Test connection
3. ✅ Create database schema
4. ✅ Migrate existing JSON data (optional)
5. ✅ Ready to run!

## Option 2: Manual Setup

### Step 1: Get PostgreSQL Connection String

**Neon.tech** (Recommended - Best free tier):
1. Go to https://console.neon.tech
2. Sign up with GitHub
3. Create new project
4. Copy connection string

### Step 2: Update .env

```bash
cp .env.example .env
```

Edit `.env` and add:
```bash
DATABASE_URL="postgresql+asyncpg://user:pass@host.neon.tech/dbname"
```

**Important:** Must include `+asyncpg` after `postgresql`!

### Step 3: Install Dependencies

```bash
poetry install
```

### Step 4: Create Schema

```bash
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

### Step 5: Test

```bash
python -c "import asyncio; from database import check_db_connection; print('✅ Works!' if asyncio.run(check_db_connection()) else '❌ Failed')"
```

## You're Done! 🎉

Now run your dashboard:
```bash
python dashboard_server.py
```

See `REMOTE_POSTGRES_SETUP.md` for detailed docs.
