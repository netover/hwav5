# 📘 GUIA DE DEPLOYMENT - WORKSTATION METRICS COLLECTION

## 🎯 **OBJETIVO**

Coletar métricas de CPU, Memory e Disk de cada FTA/Workstation TWS e enviar para Resync via HTTP POST.

---

## 📋 **PRÉ-REQUISITOS**

### **1. Resync (Servidor)**

- ✅ Resync v5.10+ instalado e rodando
- ✅ PostgreSQL acessível
- ✅ API endpoint configurado (porta 443 ou 8000)
- ✅ API Key gerada para autenticação

### **2. FTAs/Workstations**

Cada FTA precisa ter:
- ✅ Bash shell (versão 4.0+)
- ✅ `curl` instalado
- ✅ Permissão para criar arquivos em `/opt/tws/scripts/`
- ✅ Permissão para editar crontab
- ✅ Conectividade HTTP/HTTPS para Resync (porta 443)

### **3. Comandos Disponíveis**

O script detecta automaticamente, mas ajuda ter:
- `top` ou `mpstat` ou `sar` (para CPU)
- `free` (Linux) ou `vm_stat` (macOS) ou `svmon` (AIX) (para Memory)
- `df` (para Disk)
- `uptime` (para Load Average)

---

## 🚀 **DEPLOYMENT PASSO A PASSO**

### **PARTE 1: SETUP NO RESYNC (Servidor)**

#### **Step 1.1: Criar Migration do Banco**

```bash
# No servidor Resync
cd /opt/resync

# Copiar migration
cp /path/to/alembic_migration_workstation_metrics.py \
   alembic/versions/add_workstation_metrics.py

# IMPORTANTE: Editar o arquivo e ajustar 'down_revision'
# para apontar para a última migration existente
nano alembic/versions/add_workstation_metrics.py
# Mudar: down_revision = 'previous_revision'
# Para:  down_revision = 'última_migration_id'

# Rodar migration
alembic upgrade head

# Verificar tabela criada
psql -U resync -d resync -c "\d workstation_metrics_history"
```

---

#### **Step 1.2: Adicionar API Endpoint**

```bash
# Copiar código do endpoint
cp /path/to/workstation_metrics_api.py \
   resync/api/v1/metrics/workstation.py

# Editar main router para incluir endpoint
nano resync/api/main.py
```

```python
# Adicionar no main.py:
from resync.api.v1.metrics.workstation import router as metrics_router

# ...

app.include_router(metrics_router)
```

```bash
# Restart Resync
systemctl restart resync

# Verificar endpoint
curl https://resync.company.com/api/v1/metrics/health
# Deve retornar: {"status": "healthy", ...}
```

---

#### **Step 1.3: Gerar API Key**

```bash
# Opção A: Usar CLI do Resync
resync-cli api-key create \
  --name "FTA Metrics Collector" \
  --scope "metrics:write" \
  --expires "2025-12-31"

# Opção B: Via Python
python3 << 'EOF'
import secrets
api_key = f"rsk_{secrets.token_urlsafe(32)}"
print(f"API Key: {api_key}")
# Salvar no banco: INSERT INTO api_keys ...
EOF

# COPIAR A API KEY GERADA!
# Exemplo: rsk_abc123xyz789...
```

**⚠️ IMPORTANTE:** Guardar a API key em local seguro!

---

#### **Step 1.4: Testar Endpoint (Localhost)**

```bash
# Test payload
cat > test_metrics.json << 'EOF'
{
  "workstation": "TEST-WS-01",
  "timestamp": "2024-12-25T10:30:00Z",
  "metrics": {
    "cpu_percent": 45.2,
    "memory_percent": 62.8,
    "disk_percent": 78.5,
    "load_avg_1min": 2.15,
    "cpu_count": 8,
    "total_memory_gb": 32,
    "total_disk_gb": 500
  },
  "metadata": {
    "os_type": "linux-gnu",
    "hostname": "test-ws-01.company.com",
    "collector_version": "1.0.0"
  }
}
EOF

# Test POST
curl -X POST https://resync.company.com/api/v1/metrics/workstation \
  -H "Content-Type: application/json" \
  -H "X-API-Key: rsk_abc123xyz789..." \
  -d @test_metrics.json

# Deve retornar:
# {
#   "status": "success",
#   "message": "Metrics stored successfully for TEST-WS-01",
#   ...
# }

# Verificar no banco
psql -U resync -d resync -c \
  "SELECT * FROM workstation_metrics_history WHERE workstation = 'TEST-WS-01';"
```

**✅ Se tudo OK, Resync está pronto!**

---

### **PARTE 2: DEPLOYMENT NAS FTAs (Workstations)**

#### **Step 2.1: Preparar Script**

```bash
# No seu laptop/desktop, editar o script:
nano collect_metrics.sh

# AJUSTAR as seguintes linhas:

# Linha 19: URL do Resync
RESYNC_URL="https://resync.company.com/api/v1/metrics/workstation"

# Linha 22: API Key gerada no Step 1.3
API_KEY="rsk_abc123xyz789..."

# Salvar e sair (Ctrl+X, Y, Enter)
```

---

#### **Step 2.2: Deploy em UMA FTA (Teste)**

**Escolha 1 FTA para teste inicial** (ex: WS-DEV-01)

```bash
# 1. Copiar script para a FTA
scp collect_metrics.sh usuario@ws-dev-01:/tmp/

# 2. SSH na FTA
ssh usuario@ws-dev-01

# 3. Mover para diretório correto
sudo mkdir -p /opt/tws/scripts
sudo mv /tmp/collect_metrics.sh /opt/tws/scripts/
sudo chmod +x /opt/tws/scripts/collect_metrics.sh

# 4. Criar diretório de logs
sudo mkdir -p /var/log
sudo touch /var/log/tws_metrics_collector.log
sudo chmod 666 /var/log/tws_metrics_collector.log

# 5. Testar script manualmente
sudo /opt/tws/scripts/collect_metrics.sh

# Verificar log
tail -f /var/log/tws_metrics_collector.log

# Deve aparecer:
# [2024-12-25 10:30:00] Starting metrics collection for WS-DEV-01
# [2024-12-25 10:30:01] Collected: CPU=45.2% MEM=62.8% DISK=78.5% LOAD=2.15
# [2024-12-25 10:30:02] SUCCESS: Metrics sent (HTTP 201)
# [2024-12-25 10:30:02] Metrics collection completed successfully
```

**✅ Se aparecer "SUCCESS", script funcionando!**

---

#### **Step 2.3: Configurar Cron (Execução Automática)**

```bash
# Ainda na FTA (ws-dev-01)

# Editar crontab
sudo crontab -e

# Adicionar linha (executa cada 5 minutos):
*/5 * * * * /opt/tws/scripts/collect_metrics.sh >> /var/log/tws_metrics_collector.log 2>&1

# Salvar e sair

# Verificar crontab criado
sudo crontab -l

# Esperar 5 minutos e verificar log
tail -20 /var/log/tws_metrics_collector.log

# Deve aparecer execuções automáticas!
```

---

#### **Step 2.4: Validar no Resync**

```bash
# No servidor Resync, verificar se métricas estão chegando

# Query recentes (últimos 30 minutos)
psql -U resync -d resync << 'EOF'
SELECT 
  workstation,
  timestamp,
  cpu_percent,
  memory_percent,
  disk_percent,
  received_at
FROM workstation_metrics_history
WHERE workstation = 'WS-DEV-01'
  AND received_at > NOW() - INTERVAL '30 minutes'
ORDER BY received_at DESC
LIMIT 10;
EOF

# Deve aparecer registros a cada 5 minutos!
```

**✅ Se dados aparecem, deployment na FTA OK!**

---

#### **Step 2.5: Rollout para TODAS FTAs**

**Agora que testou em 1 FTA, fazer deploy em todas:**

##### **OPÇÃO A: Manual (FTA por FTA)**

```bash
# Para cada FTA:
FTA_NAME="WS-PROD-01"  # Ajustar para cada FTA

scp collect_metrics.sh usuario@$FTA_NAME:/tmp/
ssh usuario@$FTA_NAME << 'EOF'
sudo mkdir -p /opt/tws/scripts
sudo mv /tmp/collect_metrics.sh /opt/tws/scripts/
sudo chmod +x /opt/tws/scripts/collect_metrics.sh
sudo mkdir -p /var/log
sudo touch /var/log/tws_metrics_collector.log
sudo chmod 666 /var/log/tws_metrics_collector.log
echo '*/5 * * * * /opt/tws/scripts/collect_metrics.sh >> /var/log/tws_metrics_collector.log 2>&1' | sudo crontab -
EOF

# Testar
ssh usuario@$FTA_NAME "sudo /opt/tws/scripts/collect_metrics.sh"
```

---

##### **OPÇÃO B: Semi-Automatizado (Loop)**

```bash
# Criar arquivo com lista de FTAs
cat > fta_list.txt << 'EOF'
WS-PROD-01
WS-PROD-02
WS-PROD-03
WS-PROD-04
WS-PROD-05
EOF

# Loop de deployment
while read FTA; do
  echo "=== Deploying to $FTA ==="
  
  scp collect_metrics.sh usuario@$FTA:/tmp/ || {
    echo "ERROR: Failed to copy to $FTA"
    continue
  }
  
  ssh usuario@$FTA << 'EOSSH'
sudo mkdir -p /opt/tws/scripts
sudo mv /tmp/collect_metrics.sh /opt/tws/scripts/
sudo chmod +x /opt/tws/scripts/collect_metrics.sh
sudo mkdir -p /var/log
sudo touch /var/log/tws_metrics_collector.log
sudo chmod 666 /var/log/tws_metrics_collector.log
echo '*/5 * * * * /opt/tws/scripts/collect_metrics.sh >> /var/log/tws_metrics_collector.log 2>&1' | sudo crontab -
sudo /opt/tws/scripts/collect_metrics.sh
EOSSH
  
  if [ $? -eq 0 ]; then
    echo "✅ $FTA: SUCCESS"
  else
    echo "❌ $FTA: FAILED"
  fi
  
  echo ""
  sleep 2
done < fta_list.txt

echo "Deployment complete!"
```

---

##### **OPÇÃO C: Ansible (Mais Profissional)**

```yaml
# playbook.yml
---
- name: Deploy TWS Metrics Collector
  hosts: tws_ftas
  become: yes
  
  vars:
    script_path: /opt/tws/scripts/collect_metrics.sh
    log_path: /var/log/tws_metrics_collector.log
  
  tasks:
    - name: Create scripts directory
      file:
        path: /opt/tws/scripts
        state: directory
        mode: '0755'
    
    - name: Copy metrics collector script
      copy:
        src: collect_metrics.sh
        dest: "{{ script_path }}"
        mode: '0755'
    
    - name: Create log file
      file:
        path: "{{ log_path }}"
        state: touch
        mode: '0666'
    
    - name: Configure cron job
      cron:
        name: "TWS Metrics Collector"
        minute: "*/5"
        job: "{{ script_path }} >> {{ log_path }} 2>&1"
        user: root
    
    - name: Test script execution
      command: "{{ script_path }}"
      register: test_result
      changed_when: false
    
    - name: Display test result
      debug:
        var: test_result.stdout_lines
```

```bash
# Executar playbook
ansible-playbook -i inventory.ini playbook.yml

# Inventory example:
# [tws_ftas]
# ws-prod-01 ansible_host=10.0.1.10
# ws-prod-02 ansible_host=10.0.1.11
# ws-prod-03 ansible_host=10.0.1.12
```

---

## 🔍 **VERIFICAÇÃO E MONITORAMENTO**

### **Check 1: Quantas FTAs estão enviando?**

```sql
-- No PostgreSQL do Resync
SELECT 
  workstation,
  COUNT(*) as total_metrics,
  MIN(timestamp) as first_metric,
  MAX(timestamp) as last_metric,
  MAX(received_at) as last_received
FROM workstation_metrics_history
WHERE received_at > NOW() - INTERVAL '1 hour'
GROUP BY workstation
ORDER BY workstation;
```

---

### **Check 2: FTAs que NÃO estão enviando?**

```bash
# Lista de FTAs esperadas
cat > expected_ftas.txt << 'EOF'
WS-PROD-01
WS-PROD-02
WS-PROD-03
WS-PROD-04
WS-PROD-05
EOF

# FTAs que enviaram métricas (última hora)
psql -U resync -d resync -t -c "
SELECT DISTINCT workstation 
FROM workstation_metrics_history 
WHERE received_at > NOW() - INTERVAL '1 hour'
ORDER BY workstation
" > sending_ftas.txt

# Comparar
echo "=== FTAs NOT sending metrics ==="
comm -23 <(sort expected_ftas.txt) <(sort sending_ftas.txt)
```

---

### **Check 3: Métricas críticas?**

```sql
-- FTAs com CPU > 90%
SELECT 
  workstation,
  timestamp,
  cpu_percent,
  memory_percent,
  disk_percent
FROM workstation_metrics_history
WHERE received_at > NOW() - INTERVAL '1 hour'
  AND (
    cpu_percent > 90 
    OR memory_percent > 90 
    OR disk_percent > 85
  )
ORDER BY cpu_percent DESC, memory_percent DESC;
```

---

### **Check 4: Volume de dados**

```sql
-- Estatísticas gerais
SELECT 
  COUNT(*) as total_records,
  COUNT(DISTINCT workstation) as total_workstations,
  MIN(timestamp) as oldest_metric,
  MAX(timestamp) as newest_metric,
  pg_size_pretty(pg_total_relation_size('workstation_metrics_history')) as table_size
FROM workstation_metrics_history;

-- Por dia
SELECT 
  DATE(received_at) as date,
  COUNT(*) as records_per_day,
  COUNT(DISTINCT workstation) as workstations_per_day
FROM workstation_metrics_history
GROUP BY DATE(received_at)
ORDER BY date DESC
LIMIT 7;
```

---

## 🐛 **TROUBLESHOOTING**

### **Problema 1: Script não envia métricas**

```bash
# SSH na FTA
ssh usuario@ws-prod-01

# Executar script manualmente com verbose
bash -x /opt/tws/scripts/collect_metrics.sh

# Verificar conectividade
curl -v https://resync.company.com/api/v1/metrics/health

# Verificar se curl está instalado
which curl

# Verificar se API key está correta
grep "API_KEY" /opt/tws/scripts/collect_metrics.sh
```

---

### **Problema 2: Métricas não aparecem no banco**

```bash
# No Resync, verificar logs da API
tail -100 /var/log/resync/api.log | grep "metrics"

# Verificar se API está rodando
curl https://resync.company.com/api/v1/metrics/health

# Verificar se migration rodou
psql -U resync -d resync -c "\dt workstation_metrics_history"
```

---

### **Problema 3: Cron não executa**

```bash
# SSH na FTA
ssh usuario@ws-prod-01

# Verificar se cron está rodando
sudo systemctl status cron  # ou crond

# Verificar crontab
sudo crontab -l

# Verificar logs do cron
sudo tail -50 /var/log/cron  # ou /var/log/syslog

# Testar execução manual
sudo /opt/tws/scripts/collect_metrics.sh
```

---

### **Problema 4: CPU/Memory não detecta corretamente**

```bash
# SSH na FTA
ssh usuario@ws-prod-01

# Testar comandos individualmente
top -bn1 | grep "Cpu(s)"
free | grep Mem
df -h /

# Se AIX:
topas -d 1 -n 1
svmon -G
lsdev -Cc processor

# Se macOS:
top -l 1 | grep "CPU usage"
vm_stat
```

---

## 📊 **DASHBOARD (OPCIONAL)**

### **Query para Grafana/Metabase:**

```sql
-- Última métrica de cada FTA
SELECT DISTINCT ON (workstation)
  workstation,
  timestamp,
  cpu_percent,
  memory_percent,
  disk_percent,
  load_avg_1min,
  received_at
FROM workstation_metrics_history
ORDER BY workstation, timestamp DESC;

-- Tendência (últimas 24h)
SELECT 
  workstation,
  DATE_TRUNC('hour', timestamp) as hour,
  AVG(cpu_percent) as avg_cpu,
  AVG(memory_percent) as avg_memory,
  AVG(disk_percent) as avg_disk
FROM workstation_metrics_history
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY workstation, DATE_TRUNC('hour', timestamp)
ORDER BY workstation, hour;
```

---

## ✅ **CHECKLIST FINAL**

### **Resync (Servidor):**

- [ ] Migration criada e executada
- [ ] Tabela `workstation_metrics_history` existe
- [ ] API endpoint configurado e rodando
- [ ] API key gerada e guardada
- [ ] Teste com `test_metrics.json` passou

### **FTAs (Cada Workstation):**

- [ ] Script copiado para `/opt/tws/scripts/`
- [ ] Permissão de execução (`chmod +x`)
- [ ] API key configurada no script
- [ ] URL do Resync configurada
- [ ] Teste manual executado com sucesso
- [ ] Cron configurado (cada 5 minutos)
- [ ] Log file criado e escrevendo
- [ ] Métricas aparecendo no banco

### **Validação:**

- [ ] Query SQL mostra todas FTAs enviando
- [ ] Última métrica < 10 minutos
- [ ] Nenhuma FTA faltando
- [ ] Volume de dados esperado (~12 records/FTA/hora)

---

## 🎉 **DEPLOYMENT COMPLETO!**

Você agora tem:
- ✅ Métricas de CPU, Memory, Disk de TODAS FTAs
- ✅ Dados atualizados cada 5 minutos
- ✅ Histórico armazenado no PostgreSQL
- ✅ Pronto para Capacity Forecasting! 🚀

**Próximo passo:** Implementar workflows de análise!
