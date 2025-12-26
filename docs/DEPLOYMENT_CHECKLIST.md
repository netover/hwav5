# ✅ CHECKLIST DE DEPLOYMENT - AGENT SCRIPTS

## 📅 **PLANEJAMENTO**

### **Decisão:**
- [ ] Aprovação para implementar
- [ ] Budget aprovado ($3,700)
- [ ] Timeline acordado (2 semanas)
- [ ] Kick-off meeting agendado

### **Recursos Alocados:**
- [ ] Developer (16h)
- [ ] DevOps (10h)
- [ ] QA (6h)
- [ ] Ops (8h)
- [ ] TWS Admin (12h)

---

## 🔧 **SEMANA 1: SETUP RESYNC**

### **Dia 1: Development**
- [ ] Criar arquivo `workstation_metrics_api.py`
- [ ] Criar arquivo `alembic_migration_workstation_metrics.py`
- [ ] Ajustar `down_revision` na migration
- [ ] Adicionar router ao `main.py`
- [ ] Code review completo

### **Dia 2: Database**
- [ ] Rodar migration: `alembic upgrade head`
- [ ] Verificar tabela criada: `\d workstation_metrics_history`
- [ ] Verificar indexes: `\di workstation_metrics_history*`
- [ ] Testar insert manual
- [ ] Testar query

### **Dia 3: API Setup**
- [ ] Gerar API key: `resync-cli api-key create`
- [ ] Guardar API key em local seguro
- [ ] Configurar endpoint no Resync
- [ ] Restart Resync: `systemctl restart resync`
- [ ] Verificar logs: `tail -f /var/log/resync/api.log`

### **Dia 4: Testes**
- [ ] Testar health check: `curl .../metrics/health`
- [ ] Executar `test_metrics_simulator.sh`
- [ ] Verificar dados no banco
- [ ] Testar query endpoint
- [ ] Testar alertas (métricas críticas)

### **Dia 5: Deploy Produção**
- [ ] Deploy em staging (se houver)
- [ ] Testes QA em staging
- [ ] Deploy em produção
- [ ] Smoke tests produção
- [ ] Monitorar logs (1 hora)

**✅ FASE 1 COMPLETA!**

---

## 🚀 **SEMANA 2: DEPLOYMENT FTAS**

### **Preparação:**
- [ ] Editar `collect_metrics.sh`
- [ ] Configurar RESYNC_URL (linha 19)
- [ ] Configurar API_KEY (linha 22)
- [ ] Testar script localmente (se possível)
- [ ] Criar lista de FTAs: `fta_list.txt`

---

### **Dia 1: Piloto (1 FTA)**

**FTA:** `WS-DEV-01` (escolher FTA de desenvolvimento)

- [ ] Copiar script: `scp collect_metrics.sh usuario@ws-dev-01:/tmp/`
- [ ] SSH na FTA: `ssh usuario@ws-dev-01`
- [ ] Criar diretório: `sudo mkdir -p /opt/tws/scripts`
- [ ] Mover script: `sudo mv /tmp/collect_metrics.sh /opt/tws/scripts/`
- [ ] Permissão: `sudo chmod +x /opt/tws/scripts/collect_metrics.sh`
- [ ] Testar manual: `sudo /opt/tws/scripts/collect_metrics.sh`
- [ ] Verificar log: `tail -f /var/log/tws_metrics_collector.log`
- [ ] Ver "SUCCESS" no log ✅
- [ ] Configurar cron: `echo '*/5 * * * * /opt/tws/scripts/collect_metrics.sh' | sudo crontab -`
- [ ] Verificar crontab: `sudo crontab -l`
- [ ] Esperar 5 minutos
- [ ] Verificar execução automática no log
- [ ] Query banco: verificar WS-DEV-01 aparecendo
- [ ] Aprovar para próximas FTAs ✅

---

### **Dia 2: FTAs DEV (3 FTAs)**

| FTA | Status | Notas |
|-----|--------|-------|
| WS-DEV-02 | [ ] | |
| WS-DEV-03 | [ ] | |
| WS-DEV-04 | [ ] | |

**Para cada FTA:**
- [ ] Deployment (copiar script, configurar cron)
- [ ] Teste manual
- [ ] Validação (verificar logs)
- [ ] Query banco (verificar dados)

**Fim do dia:**
- [ ] 4 FTAs DEV enviando métricas ✅
- [ ] Nenhum erro crítico
- [ ] Aprovação para QA/HML

---

### **Dia 3: FTAs QA/HML (4 FTAs)**

| FTA | Status | Notas |
|-----|--------|-------|
| WS-QA-01 | [ ] | |
| WS-QA-02 | [ ] | |
| WS-HML-01 | [ ] | |
| WS-HML-02 | [ ] | |

**Para cada FTA:**
- [ ] Deployment
- [ ] Teste manual
- [ ] Validação

**Fim do dia:**
- [ ] 8 FTAs total enviando métricas ✅
- [ ] Volume de dados esperado
- [ ] Aprovação para PROD

---

### **Dia 4: FTAs PROD - Parte 1 (6 FTAs)**

| FTA | Status | Notas |
|-----|--------|-------|
| WS-PROD-01 | [ ] | |
| WS-PROD-02 | [ ] | |
| WS-PROD-03 | [ ] | |
| WS-PROD-04 | [ ] | |
| WS-PROD-05 | [ ] | |
| WS-PROD-06 | [ ] | |

**Para cada FTA:**
- [ ] Deployment (horário de menor impacto)
- [ ] Teste manual
- [ ] Validação

**Fim do dia:**
- [ ] 14 FTAs total enviando ✅
- [ ] Monitoramento contínuo
- [ ] Nenhum impacto em produção

---

### **Dia 5: FTAs PROD - Parte 2 (6 FTAs)**

| FTA | Status | Notas |
|-----|--------|-------|
| WS-PROD-07 | [ ] | |
| WS-PROD-08 | [ ] | |
| WS-PROD-09 | [ ] | |
| WS-PROD-10 | [ ] | |
| WS-PROD-11 | [ ] | |
| WS-PROD-12 | [ ] | |

**Para cada FTA:**
- [ ] Deployment
- [ ] Teste manual
- [ ] Validação

**Fim do dia:**
- [ ] **20 FTAs total enviando** ✅✅✅
- [ ] **100% cobertura**
- [ ] Documentação atualizada
- [ ] Troubleshooting guide testado

**✅ FASE 2 COMPLETA!**

---

## 📊 **VALIDAÇÃO FINAL (Dia 5 tarde)**

### **Métricas Técnicas:**

```sql
-- Check 1: Quantas FTAs enviando?
SELECT COUNT(DISTINCT workstation) as ftas_sending
FROM workstation_metrics_history
WHERE received_at > NOW() - INTERVAL '1 hour';
```
- [ ] **Target: 20 FTAs** ✅

```sql
-- Check 2: Última métrica de cada FTA
SELECT 
  workstation,
  MAX(received_at) as last_metric,
  AGE(NOW(), MAX(received_at)) as age
FROM workstation_metrics_history
GROUP BY workstation
ORDER BY last_metric DESC;
```
- [ ] **Target: Todas < 10 minutos** ✅

```sql
-- Check 3: Volume de dados (última hora)
SELECT 
  COUNT(*) as total_metrics,
  COUNT(DISTINCT workstation) as workstations
FROM workstation_metrics_history
WHERE received_at > NOW() - INTERVAL '1 hour';
```
- [ ] **Target: ~240 metrics (20 FTAs × 12/hora)** ✅

```sql
-- Check 4: Storage usado
SELECT pg_size_pretty(pg_total_relation_size('workstation_metrics_history'));
```
- [ ] **Target: < 10 MB (primeiros dias)** ✅

---

### **Métricas de Negócio:**

- [ ] Deployment completado em **2 semanas** ✅
- [ ] Custo dentro do budget: **$3,700** ✅
- [ ] Nenhum downtime ou impacto
- [ ] Documentação completa criada
- [ ] Time treinado e confortável

---

## 📋 **HANDOFF PARA OPS**

### **Documentação Entregue:**
- [ ] README.md
- [ ] DEPLOYMENT_GUIDE.md
- [ ] EXECUTIVE_SUMMARY.md
- [ ] Códigos comentados
- [ ] Queries SQL úteis

### **Acesso Configurado:**
- [ ] Ops tem acesso ao banco
- [ ] Ops tem acesso aos logs
- [ ] Ops sabe onde encontrar scripts
- [ ] Ops sabe troubleshooting básico

### **Monitoramento Setup:**
- [ ] Dashboard criado (opcional)
- [ ] Alertas configurados (opcional)
- [ ] Runbook de troubleshooting
- [ ] Escalation path definido

### **Treinamento:**
- [ ] Sessão de treinamento realizada
- [ ] Q&A session
- [ ] Ops confortável com solução
- [ ] Contatos de suporte definidos

---

## 🎉 **ACEITE FINAL**

### **Critérios de Sucesso:**

- [ ] ✅ **100% FTAs enviando métricas** (20/20)
- [ ] ✅ **Frequência correta** (~12 metrics/FTA/hora)
- [ ] ✅ **Latência OK** (< 1s p99)
- [ ] ✅ **Uptime > 99.5%** (nenhum gap > 10 min)
- [ ] ✅ **Nenhum erro crítico**

### **Aprovação:**

- [ ] **Dev Team:** Código aprovado e em produção
- [ ] **DevOps:** Infra estável e monitorada
- [ ] **QA:** Testes passaram
- [ ] **Ops:** Confortável com handoff
- [ ] **TWS Admin:** FTAs funcionando normalmente
- [ ] **Stakeholder:** ROI validado e aprovado

**✅ DEPLOYMENT APROVADO!**

---

## 🚀 **PRÓXIMOS PASSOS**

### **Semana 3: Monitoramento**
- [ ] Coletar 7 dias de dados
- [ ] Validar completude e qualidade
- [ ] Estabelecer baseline por FTA
- [ ] Documentar padrões observados

### **Semana 4+: Workflows**
- [ ] Implementar Capacity Forecasting
- [ ] Implementar Enhanced Predictive Maintenance
- [ ] Implementar Resource Optimization
- [ ] **Atingir ROI de $750k/ano** 🎯

---

## 📞 **CONTATOS**

| Papel | Nome | Email | Telefone |
|-------|------|-------|----------|
| **Tech Lead** | | | |
| **DevOps Lead** | | | |
| **TWS Admin** | | | |
| **Product Owner** | | | |

---

## 📝 **NOTAS / ISSUES**

_Espaço para anotar problemas encontrados, soluções, lições aprendidas:_

---

**Data Início:** ___/___/______  
**Data Conclusão:** ___/___/______  
**Status Final:** [ ] ✅ SUCESSO  [ ] ⚠️ PARCIAL  [ ] ❌ FALHOU

**Assinatura PM:** ____________________  
**Data:** ___/___/______
