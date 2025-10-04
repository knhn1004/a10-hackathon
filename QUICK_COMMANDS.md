# ⚡ Quick Commands Reference

All commands use Poetry for dependency management!

## 🚀 Running the Application

```bash
# Start dashboard server
poetry run python dashboard_server.py

# Start MCP server
poetry run python mcp_server.py

# Run both (in separate terminals)
```

## 🗄️ Database Setup

```bash
# One-command setup (recommended)
./setup_remote_db.sh

# Manual setup
cp .env.example .env                                    # Copy config
# Edit .env and add DATABASE_URL
poetry run alembic revision --autogenerate -m "Init"   # Create migration
poetry run alembic upgrade head                         # Apply migration
poetry run python migrate_json_to_postgres.py          # Migrate data
```

## 📊 Database Migrations

```bash
# Create new migration (after model changes)
poetry run alembic revision --autogenerate -m "Description"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1

# Check current version
poetry run alembic current

# View history
poetry run alembic history
```

## 🧪 Testing

```bash
# Test database connection
poetry run python -c "import asyncio; from database import check_db_connection; print('✅ Connected!' if asyncio.run(check_db_connection()) else '❌ Failed')"

# Test MCP server
poetry run python test_mcp_server.py

# Test migration (dry run)
poetry run python migrate_json_to_postgres.py --dry-run
```

## 📦 Package Management

```bash
# Install dependencies
poetry install

# Add new package
poetry add package-name

# Update lock file
poetry lock --no-update

# Show installed packages
poetry show

# Check for outdated packages
poetry show --outdated
```

## 🛠️ Development

```bash
# Run with auto-reload (watchdog)
pip install watchdog[watchmedo]
watchmedo auto-restart --pattern="*.py" --recursive -- poetry run python dashboard_server.py

# View logs
tail -f logs/dashboard.log
tail -f logs/mcp.log

# Format code (if you have black)
poetry run black .

# Type checking (if you have mypy)
poetry run mypy dashboard_server.py
```

## 🚢 Deployment (Fly.io)

```bash
# Deploy to Fly.io
./deploy_flyio.sh

# Or manually
fly deploy

# View logs
fly logs

# SSH into container
fly ssh console

# Run migrations in production
fly ssh console -C "poetry run alembic upgrade head"
```

## 🗃️ Database Management

```bash
# Connect to database
psql "$DATABASE_URL"

# Backup database
pg_dump "$DATABASE_URL" > backup.sql

# Restore database
psql "$DATABASE_URL" < backup.sql

# View tables
psql "$DATABASE_URL" -c "\dt"

# Query data
psql "$DATABASE_URL" -c "SELECT * FROM users;"
```

## 🔐 Secrets Management

```bash
# Local (.env)
cp .env.example .env
# Edit .env and add secrets

# Production (Fly.io)
fly secrets set KEY=value
fly secrets list
```

## 🧹 Cleanup

```bash
# Remove __pycache__
find . -type d -name "__pycache__" -exec rm -r {} +

# Remove .pyc files
find . -type f -name "*.pyc" -delete

# Clean poetry cache
poetry cache clear --all pypi
```

## 📚 Documentation

- `POSTGRES_QUICKSTART.md` - 5-minute setup
- `REMOTE_POSTGRES_SETUP.md` - Full PostgreSQL guide
- `DEPLOY_FLYIO.md` - Deployment guide
- `SETUP_AUTH.md` - Authentication setup
- `LOCAL_SETUP.md` - Local development

## 💡 Tips

- Always use `poetry run` for Python commands
- Use `.env` for local config
- Use `fly secrets` for production secrets
- Run migrations before deploying
- Test locally before deploying

## 🆘 Troubleshooting

```bash
# Poetry lock file issues
poetry lock --no-update
poetry install

# Database connection issues
poetry run python -c "from database import check_db_connection; import asyncio; asyncio.run(check_db_connection())"

# Package conflicts
poetry update

# Clear everything and reinstall
rm -rf .venv
poetry install
```

Happy coding! 🚀
