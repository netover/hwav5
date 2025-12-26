# Resync v5.3.22 - Production Deployment Checklist

## ✅ Pre-Deployment Verification

### Security Configuration
- [ ] `SECRET_KEY` set via environment variable (32+ characters)
- [ ] `ENVIRONMENT=production` configured
- [ ] `CORS_ALLOW_ORIGINS` set to specific production domains (no wildcards)
- [ ] `ENFORCE_HTTPS=true` (when behind TLS-terminating proxy)
- [ ] `DEBUG=false` confirmed
- [ ] `LOG_LEVEL=INFO` or `WARNING` (not DEBUG)

### Database Configuration
- [ ] `DATABASE_SSL_MODE=require` or higher
- [ ] Pool sizes appropriate for server capacity
- [ ] Connection string not exposed in logs
- [ ] Backup automation configured

### Infrastructure
- [ ] Reverse proxy configured (nginx/traefik)
- [ ] TLS certificates valid and auto-renewing
- [ ] Redis available (or app runs in degraded mode)
- [ ] Firewall rules configured

## 📋 Environment Variables Checklist

### Critical (Must Be Set)
```bash
ENVIRONMENT=production
SECRET_KEY=<your-32+-character-secret>
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/resync
DATABASE_SSL_MODE=require
ADMIN_PASSWORD=<secure-password>
```

### Security (Recommended)
```bash
CORS_ALLOW_ORIGINS=https://yourdomain.com
ENFORCE_HTTPS=true
SESSION_TIMEOUT_MINUTES=30
RATE_LIMIT_CRITICAL_PER_MINUTE=10
```

### Performance (Adjust for Your Server)
```bash
# Single VM (4 CPU cores, 8GB RAM)
WORKERS=4
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
REDIS_POOL_MAX_SIZE=20

# Docker/Kubernetes (scale horizontally)
WORKERS=2
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
```

## 🔒 Security Headers Verification

After deployment, verify these headers are present:
```bash
curl -I https://your-domain.com/health
```

Expected headers:
- `Content-Security-Policy` or `Content-Security-Policy-Report-Only`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security` (if enforce_https=true)
- `Permissions-Policy`

## 📊 Health Check Verification

```bash
# Basic health
curl https://your-domain.com/health

# Detailed health (requires auth)
curl -H "Authorization: Bearer <token>" https://your-domain.com/api/v1/health/detailed
```

## 🚀 Deployment Commands

### Single VM with Gunicorn
```bash
# Export environment
export $(cat .env | xargs)

# Run with gunicorn
gunicorn resync.fastapi_app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers ${WORKERS:-4} \
    --bind 127.0.0.1:8000 \
    --timeout ${WORKER_TIMEOUT:-120} \
    --graceful-timeout ${GRACEFUL_TIMEOUT:-30}
```

### Docker
```bash
docker build -t resync:v5.3.22 .
docker run -d \
    --name resync \
    --env-file .env \
    -p 8000:8000 \
    resync:v5.3.22
```

### Kubernetes
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

## 🔄 Rollback Plan

1. Keep previous version container/deployment ready
2. Database migrations are backward compatible
3. Rollback command:
   ```bash
   # Docker
   docker stop resync
   docker run -d --name resync resync:v5.3.21
   
   # Kubernetes
   kubectl rollout undo deployment/resync
   ```

## 📈 Post-Deployment Monitoring

1. Check application logs for errors
2. Monitor health endpoint response times
3. Verify Redis connection (if enabled)
4. Check database connection pool usage
5. Monitor rate limiting metrics

## ⚠️ Known Limitations

- Redis is optional but recommended for multi-worker deployments
- HSTS requires running behind HTTPS
- Session timeout affects token validity
- Rate limits are per-IP by default

## 📞 Support

For issues, check:
1. Application logs: `journalctl -u resync -f`
2. Health endpoint: `/health`
3. Metrics endpoint: `/api/v1/monitoring/metrics`
