# ⚡ QUICK START - AGENT SCRIPTS (1 PÁGINA)

## 🎯 **OBJETIVO**
Coletar métricas de CPU, Memory, Disk das FTAs → Enviar para Resync → Habilitar Capacity Forecasting

**ROI:** +$200k/ano | **Tempo:** 2 semanas | **Custo:** $3.7k

---

## 📦 **ARQUIVOS**

1. **README.md** - Overview completo
2. **EXECUTIVE_SUMMARY.md** - ROI, timeline, recursos
3. **DEPLOYMENT_GUIDE.md** - Passo a passo detalhado
4. **DEPLOYMENT_CHECKLIST.md** - Checklist tracking
5. **collect_metrics.sh** - Script para FTAs
6. **workstation_metrics_api.py** - API endpoint Resync
7. **alembic_migration_workstation_metrics.py** - Migration DB
8. **test_metrics_simulator.sh** - Testes

---

## 🚀 **SETUP RÁPIDO (30 MINUTOS)**

### **1. Setup Resync (15 min)**

```bash
# A. Migration
cd /opt/resync
cp alembic_migration_workstation_metrics.py alembic/versions/
# Editar: ajustar down_revision
alembic upgrade head

# B. API
cp workstation_metrics_api.py resync/api/v1/metrics/workstation.py
# Editar main.py: incluir router
systemctl restart resync

# C. API Key
resync-cli api-key create --name "FTA Metrics"
# Copiar: rsk_abc123xyz789...

# D. Testar
./test_metrics_simulator.sh https://resync.company.com/api/v1/metrics/workstation rsk_abc123 3
```

---

### **2. Deploy 1 FTA Piloto (15 min)**

```bash
# A. Configurar script
nano collect_metrics.sh
# Linha 19: RESYNC_URL="https://resync.company.com/api/v1/metrics/workstation"
# Linha 22: API_KEY="rsk_abc123xyz789..."

# B. Copiar para FTA
scp collect_metrics.sh usuario@ws-dev-01:/tmp/

# C. Instalar
ssh usuario@ws-dev-01
sudo mkdir -p /opt/tws/scripts
sudo mv /tmp/collect_metrics.sh /opt/tws/scripts/
sudo chmod +x /opt/tws/scripts/collect_metrics.sh

# D. Testar
sudo /opt/tws/scripts/collect_metrics.sh
tail /var/log/tws_metrics_collector.log
# Ver: SUCCESS: Metrics sent (HTTP 201) ✅

# E. Cron
echo '*/5 * * * * /opt/tws/scripts/collect_metrics.sh' | sudo crontab -

# F. Validar
sleep 300  # 5 minutos
psql -U resync -d resync -c "SELECT * FROM workstation_metrics_history WHERE workstation='WS-DEV-01' ORDER BY received_at DESC LIMIT 3;"
```

**✅ Se tudo OK: rollout demais FTAs!**

---

## 📋 **ROLLOUT DEMAIS FTAS**

### **Opção A: Manual (FTA por FTA)**
```bash
FTA="WS-PROD-01"
scp collect_metrics.sh usuario@$FTA:/tmp/
ssh usuario@$FTA 'sudo mv /tmp/collect_metrics.sh /opt/tws/scripts/ && sudo chmod +x /opt/tws/scripts/collect_metrics.sh && echo "*/5 * * * * /opt/tws/scripts/collect_metrics.sh" | sudo crontab -'
```

### **Opção B: Loop**
```bash
while read FTA; do
  echo "Deploying to $FTA..."
  scp collect_metrics.sh usuario@$FTA:/tmp/
  ssh usuario@$FTA 'sudo mv /tmp/collect_metrics.sh /opt/tws/scripts/ && sudo chmod +x /opt/tws/scripts/collect_metrics.sh && echo "*/5 * * * * /opt/tws/scripts/collect_metrics.sh" | sudo crontab -'
  echo "✅ $FTA done"
done < fta_list.txt
```

### **Opção C: Ansible** (Ver DEPLOYMENT_GUIDE.md)

---

## ✅ **VALIDAÇÃO**

```sql
-- Quantas FTAs?
SELECT COUNT(DISTINCT workstation) FROM workstation_metrics_history WHERE received_at > NOW() - INTERVAL '1 hour';
-- Target: 20

-- Última métrica?
SELECT workstation, MAX(received_at) FROM workstation_metrics_history GROUP BY workstation ORDER BY MAX(received_at) DESC;
-- Target: Todas < 10 min

-- Volume?
SELECT COUNT(*) FROM workstation_metrics_history WHERE received_at > NOW() - INTERVAL '1 hour';
-- Target: ~240 (20 FTAs × 12/hora)
```

---

## 🐛 **TROUBLESHOOTING RÁPIDO**

| Problema | Solução Rápida |
|----------|----------------|
| **Script não envia** | `bash -x collect_metrics.sh` (debug) |
| **Sem conectividade** | `curl -v https://resync.../metrics/health` |
| **Sem no banco** | Verificar logs: `tail /var/log/resync/api.log` |
| **Cron não roda** | `sudo crontab -l` + `sudo tail /var/log/cron` |

**Detalhes:** Ver DEPLOYMENT_GUIDE.md seção "Troubleshooting"

---

## 📊 **MÉTRICAS DE SUCESSO**

- [ ] 100% FTAs enviando (20/20)
- [ ] Frequência: 12 metrics/FTA/hora
- [ ] Latência: < 1s p99
- [ ] Uptime: > 99.5%
- [ ] Storage: < 100 MB/mês

---

## 🎯 **PRÓXIMOS PASSOS**

1. ✅ **Agora:** Setup Resync + Deploy piloto (30 min)
2. ✅ **Semana 1:** Deploy todas FTAs DEV/QA (3 dias)
3. ✅ **Semana 2:** Deploy todas FTAs PROD (2 dias)
4. ✅ **Semana 3:** Validar 7 dias de dados
5. ✅ **Semana 4+:** Implementar workflows ($750k ROI!)

---

## 📞 **AJUDA**

- **Documentação Completa:** DEPLOYMENT_GUIDE.md
- **Checklist:** DEPLOYMENT_CHECKLIST.md
- **ROI/Timeline:** EXECUTIVE_SUMMARY.md

---

**COMECE AGORA!** ⚡

```bash
# Passo 1: Setup Resync (15 min)
alembic upgrade head
# ...

# Passo 2: Deploy piloto (15 min)
scp collect_metrics.sh usuario@ws-dev-01:/tmp/
# ...

# ✅ 30 minutos = Piloto funcionando!
```
