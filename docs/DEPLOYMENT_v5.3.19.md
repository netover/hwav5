# Resync v5.3.19 - Guia de Deploy para Produção

## 📋 Checklist Pré-Deploy

### ✅ Correções de Segurança (v5.3.19)

1. **Regex de Sanitização Corrigida**
   - Permite emails (`@`)
   - Permite nomes técnicos (`_`)
   - Permite textos empresariais (`&`)
   - Permite paths/datas (`/`)
   - XSS ainda bloqueado (`<`, `>`)

2. **Health Checks Implementados**
   - `/api/v1/liveness` - Probe de vida (sempre responde se app está rodando)
   - `/api/v1/readiness` - Probe de prontidão (verifica DB e Redis)
   - `/api/v1/health/detailed` - Status detalhado para dashboards

---

## 🔧 Configuração de Deploy

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: resync-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: resync
        image: resync:5.3.19
        ports:
        - containerPort: 8000
        
        # IMPORTANTE: Use readiness, não o /health HTML
        livenessProbe:
          httpGet:
            path: /api/v1/liveness
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 15
          failureThreshold: 3
          
        readinessProbe:
          httpGet:
            path: /api/v1/readiness
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
          failureThreshold: 3
          
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: resync-secrets
              key: secret-key
```

### Docker Compose

```yaml
version: '3.8'
services:
  resync:
    image: resync:5.3.19
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/readiness"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Load Balancer (AWS ALB)

```json
{
  "TargetGroup": {
    "HealthCheckPath": "/api/v1/readiness",
    "HealthCheckProtocol": "HTTP",
    "HealthCheckIntervalSeconds": 30,
    "HealthyThresholdCount": 2,
    "UnhealthyThresholdCount": 3,
    "Matcher": {
      "HttpCode": "200"
    }
  }
}
```

---

## 🔐 Variáveis de Ambiente Obrigatórias

```bash
# OBRIGATÓRIO em produção (app não sobe sem)
SECRET_KEY=<string-aleatoria-de-32-chars-ou-mais>

# RECOMENDADO (warnings se não definido)
TWS_USER=<usuario-tws>
TWS_PASSWORD=<senha-tws>

# DATABASE
DATABASE_URL=postgresql://user:pass@host:5432/resync
DATABASE_POOL_SIZE=20

# REDIS (opcional, app degrada graciosamente)
REDIS_URL=redis://host:6379/0
```

---

## 📊 Endpoints de Monitoramento

| Endpoint | Uso | Retorno |
|----------|-----|---------|
| `/api/v1/liveness` | K8s Liveness | `{"status": "alive"}` |
| `/api/v1/readiness` | K8s Readiness | `{"status": "ready", "checks": {...}}` |
| `/api/v1/health/detailed` | Dashboards | Status detalhado com métricas |
| `/health` | ⚠️ Apenas visual | HTML estático (não usar para probes!) |

---

## ⚠️ Notas Importantes

### 1. NÃO use `/health` para health checks automatizados
O endpoint `/health` retorna HTML estático e **não verifica** o banco de dados ou Redis.
Use sempre `/api/v1/readiness` para probes de infraestrutura.

### 2. Comportamento de Degradação
- Se Redis estiver indisponível: App continua funcionando (cache desabilitado)
- Se Database estiver indisponível: `/api/v1/readiness` retorna 503

### 3. Sanitização de Input
A nova regex permite mais caracteres para usabilidade, mas mantém segurança:

```python
# ✅ Agora permitidos
"user@domain.com"     # Emails
"job_stream_001"      # Nomes técnicos
"P&D Department"      # Textos empresariais
"2024/01/15"          # Datas

# ❌ Ainda bloqueados
"<script>alert(1)</script>"   # XSS
"SELECT * FROM users"          # * não permitido
```

---

## 🧪 Validação Pós-Deploy

```bash
# 1. Verificar liveness
curl http://localhost:8000/api/v1/liveness
# Esperado: {"status": "alive", "timestamp": "..."}

# 2. Verificar readiness (deve retornar 200)
curl -w "%{http_code}" http://localhost:8000/api/v1/readiness
# Esperado: 200

# 3. Verificar status detalhado
curl http://localhost:8000/api/v1/health/detailed | jq
# Esperado: {"status": "healthy", "checks": {...}}

# 4. Testar sanitização
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Contact admin@company.com about job_ETL_001"}'
# Email e underscore devem ser preservados
```

---

## 📝 Changelog v5.3.19

### Security
- ✅ Regex de sanitização expandida (permite @, _, &, /)
- ✅ Funções auxiliares: `sanitize_input_strict()`, `validate_email()`
- ✅ XSS e injection ainda bloqueados

### Observability
- ✅ `/api/v1/liveness` - Kubernetes liveness probe
- ✅ `/api/v1/readiness` - Kubernetes readiness probe com verificação de DB/Redis
- ✅ `/api/v1/health/detailed` - Status detalhado para dashboards

### Tests
- ✅ 14 novos testes de regressão para sanitização
- ✅ Testes de validação de email
- ✅ Testes de cenários TWS reais
