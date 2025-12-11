# RESYNC v5.3.13 - Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Production Deployment](#production-deployment)
4. [Database Setup](#database-setup)
5. [Environment Configuration](#environment-configuration)
6. [Health Checks](#health-checks)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- Python 3.11+
- PostgreSQL 14+ with pgvector extension
- Redis 6+ (required for multi-worker deployments)
- 4GB RAM minimum (8GB recommended)
- 20GB disk space

### Required Services
- PostgreSQL database
- Redis (for session/cache in production)
- TWS (HCL Workload Automation) - optional

---

## Quick Start

### 1. Clone and Install
```bash
git clone <repository-url>
cd resync-project
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings

# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Initialize Database
```bash
# Create database
createdb resync

# Run migrations
alembic upgrade head
```

### 4. Start Development Server
```bash
uvicorn resync.fastapi_app.main:app --reload --port 8000
```

---

## Production Deployment

### Recommended Architecture
```
                    ┌─────────────────┐
                    │   Load Balancer │
                    │   (nginx/HAProxy)│
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
        │  Worker 1  │  │  Worker 2  │  │  Worker N  │
        │  (Gunicorn)│  │  (Gunicorn)│  │  (Gunicorn)│
        └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
        │ PostgreSQL│  │   Redis   │  │    TWS    │
        └───────────┘  └───────────┘  └───────────┘
```

### Using Gunicorn
```bash
# Install gunicorn
pip install gunicorn uvicorn[standard]

# Production start
gunicorn resync.fastapi_app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --enable-stdio-inheritance
```

### Using Docker
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn[standard]

COPY . .

EXPOSE 8000
CMD ["gunicorn", "resync.fastapi_app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

### Systemd Service
```ini
[Unit]
Description=RESYNC API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=resync
Group=resync
WorkingDirectory=/opt/resync
Environment="PATH=/opt/resync/venv/bin"
EnvironmentFile=/opt/resync/.env
ExecStart=/opt/resync/venv/bin/gunicorn resync.fastapi_app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Database Setup

### PostgreSQL Setup
```sql
-- Create user and database
CREATE USER resync WITH PASSWORD 'your_secure_password';
CREATE DATABASE resync OWNER resync;

-- Connect to database and enable extensions
\c resync
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Run Migrations
```bash
# Check current status
alembic current

# Upgrade to latest
alembic upgrade head

# Rollback one step (if needed)
alembic downgrade -1
```

### Create Initial Admin User
```python
# Using Python shell
from resync.core.database.repositories.admin_users import AdminUserRepository

async def create_admin():
    repo = AdminUserRepository()
    await repo.create_user(
        username="admin",
        email="admin@example.com",
        password="secure_password_here",
        role="admin"
    )
```

---

## Environment Configuration

### Required Variables (Production)
| Variable | Description | Example |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment name | `production` |
| `SECRET_KEY` | JWT signing key | (32+ char random string) |
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://...` |
| `ADMIN_USERNAME` | Admin username | `admin` |
| `ADMIN_PASSWORD` | Admin password | (secure password) |

### Recommended Variables (Production)
| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection | `redis://localhost:6379` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `CORS_ALLOW_ORIGINS` | Allowed CORS origins | (your domains) |

### Security Checklist
- [ ] `SECRET_KEY` is set and unique
- [ ] `ENVIRONMENT=production`
- [ ] `CORS_ALLOW_ORIGINS` is not `*`
- [ ] Database credentials are secure
- [ ] Redis is password-protected
- [ ] HTTPS is enabled via reverse proxy

---

## Health Checks

### Endpoints
| Endpoint | Purpose | Use Case |
|----------|---------|----------|
| `GET /health/liveness` | Is process running? | Kubernetes liveness probe |
| `GET /health/readiness` | Is app ready for traffic? | Kubernetes readiness probe |
| `GET /health/summary` | Full health status | Monitoring dashboards |
| `GET /health/core` | Core services status | Debugging |

### Kubernetes Probes
```yaml
livenessProbe:
  httpGet:
    path: /health/liveness
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/readiness
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

### Expected Responses
```json
// GET /health/liveness - 200 OK
{"status": "alive", "timestamp": "2024-12-11T14:30:00Z"}

// GET /health/readiness - 200 OK (or 503 if not ready)
{"status": "ready", "database": "connected", "redis": "connected"}
```

---

## Monitoring

### Prometheus Metrics
Metrics are exposed at `GET /metrics` in Prometheus format.

Key metrics:
- `http_requests_total` - Request count by endpoint
- `http_request_duration_seconds` - Request latency
- `db_connections_active` - Active database connections
- `cache_hits_total` - Cache hit rate

### Structured Logging
All logs are JSON-formatted for easy parsing:
```json
{
  "timestamp": "2024-12-11T14:30:00.123Z",
  "level": "info",
  "event": "request_completed",
  "correlation_id": "abc123",
  "duration_ms": 45,
  "status_code": 200
}
```

### Alerting Recommendations
- **High Priority**: 5xx error rate > 1%
- **Medium Priority**: Response time p95 > 2s
- **Low Priority**: Database connection pool > 80%

---

## Troubleshooting

### Common Issues

#### 1. "SECRET_KEY must be configured in production"
```bash
# Generate and set SECRET_KEY
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

#### 2. Database Connection Failed
```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check migrations
alembic current
alembic upgrade head
```

#### 3. Redis Connection Failed
```bash
# Test Redis
redis-cli -u $REDIS_URL ping

# Run without Redis (development only)
export RESYNC_DISABLE_REDIS=true
```

#### 4. Permission Denied on Startup
```bash
# Check file permissions
ls -la /opt/resync/.env
chmod 600 /opt/resync/.env
chown resync:resync /opt/resync/.env
```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with verbose output
uvicorn resync.fastapi_app.main:app --log-level debug
```

### Support Contacts
- Documentation: https://docs.resync.example.com
- Issues: https://github.com/your-org/resync/issues
- Email: support@example.com

---

## Rollback Procedures

### Application Rollback
```bash
# If using systemd
sudo systemctl stop resync
cd /opt/resync
git checkout v5.3.12  # Previous version
pip install -r requirements.txt
sudo systemctl start resync
```

### Database Rollback
```bash
# Rollback last migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 20241210_0001
```

### Emergency Procedures
1. **High Error Rate**: Scale down to 1 worker, check logs
2. **Database Overload**: Enable read replicas, check slow queries
3. **Memory Issues**: Restart workers, check for memory leaks
