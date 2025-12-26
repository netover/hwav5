"""
Resync Workflows - Usage Examples

Exemplos práticos de como executar os workflows.
"""

# ============================================================================
# EXEMPLO 1: Predictive Maintenance - Execução Manual
# ============================================================================

import asyncio
from workflows.workflow_predictive_maintenance import run_predictive_maintenance

# Executar para um job específico
result = asyncio.run(run_predictive_maintenance(
    job_name="BACKUP_FULL",
    lookback_days=30
))

print(f"Status: {result['status']}")
print(f"Degradation detected: {result['degradation_detected']}")
print(f"Failure probability: {result['failure_probability']}")
print(f"Recommendations: {len(result['recommendations'])}")

# ============================================================================
# EXEMPLO 2: Capacity Forecasting - Execução Manual
# ============================================================================

from workflows.workflow_capacity_forecasting import run_capacity_forecast

# Executar para uma workstation específica
result = asyncio.run(run_capacity_forecast(
    workstation="WS-PROD-01",
    lookback_days=30,
    forecast_days=90
))

print(f"Status: {result['status']}")
print(f"CPU saturation: {result['cpu_saturation_date']}")
print(f"Memory saturation: {result['memory_saturation_date']}")
print(f"Disk saturation: {result['disk_saturation_date']}")
print(f"Confidence: {result['saturation_confidence']:.2%}")

# ============================================================================
# EXEMPLO 3: Aprovar Workflow Pausado (Human-in-the-Loop)
# ============================================================================

from workflows.workflow_predictive_maintenance import approve_workflow

# Aprovar workflow que está aguardando review
result = asyncio.run(approve_workflow(
    workflow_id="pm_BACKUP_FULL_1234567890.123",
    approved=True,
    feedback="Approved after analysis. Proceed with preventive actions."
))

print(f"Workflow resumed: {result['status']}")

# ============================================================================
# EXEMPLO 4: Criar API Key via API
# ============================================================================

import httpx

response = httpx.post(
    "https://resync.company.com/api/v1/admin/api-keys",
    headers={
        "Authorization": "Bearer YOUR_ADMIN_TOKEN",
        "Content-Type": "application/json"
    },
    json={
        "name": "Production FTA Metrics",
        "description": "API key for production FTAs to send metrics",
        "scopes": ["metrics:write"],
        "expires_in_days": 365
    }
)

api_key_data = response.json()
print(f"API Key created: {api_key_data['key']}")
print(f"⚠️  Save this key - it won't be shown again!")

# ============================================================================
# EXEMPLO 5: Listar API Keys
# ============================================================================

response = httpx.get(
    "https://resync.company.com/api/v1/admin/api-keys",
    headers={"Authorization": "Bearer YOUR_ADMIN_TOKEN"}
)

keys = response.json()
print(f"Total keys: {keys['total']}")
for key in keys['keys']:
    print(f"  - {key['name']}: {key['key_prefix']}... (usage: {key['usage_count']})")

# ============================================================================
# EXEMPLO 6: Testar Enhanced Metrics Collection
# ============================================================================

import subprocess
import json

# Executar script de coleta
result = subprocess.run(
    ["/opt/tws/scripts/collect_metrics_enhanced.sh"],
    capture_output=True,
    text=True
)

print(f"Script exit code: {result.returncode}")
print(f"Output: {result.stdout}")

# ============================================================================
# EXEMPLO 7: Query Workstation Metrics via PostgreSQL
# ============================================================================

import asyncpg

async def get_latest_metrics(workstation: str):
    conn = await asyncpg.connect(
        "postgresql://resync:password@localhost/resync"
    )
    
    rows = await conn.fetch("""
        SELECT 
            timestamp,
            cpu_percent,
            memory_percent,
            disk_percent,
            latency_avg_ms,
            packet_loss_percent,
            tcp_connectivity
        FROM workstation_metrics_history
        WHERE workstation = $1
        ORDER BY timestamp DESC
        LIMIT 10
    """, workstation)
    
    await conn.close()
    
    for row in rows:
        print(f"{row['timestamp']}: CPU={row['cpu_percent']}% "
              f"MEM={row['memory_percent']}% "
              f"LATENCY={row['latency_avg_ms']}ms")

asyncio.run(get_latest_metrics("WS-PROD-01"))

# ============================================================================
# EXEMPLO 8: Prefect Deployment via CLI
# ============================================================================

"""
# Create deployment
prefect deployment build \
    workflows/workflow_predictive_maintenance.py:run_predictive_maintenance \
    -n "Predictive Maintenance - Daily" \
    --cron "0 2 * * *" \
    --pool default-pool

# Apply deployment
prefect deployment apply run_predictive_maintenance-deployment.yaml

# Start agent
prefect agent start -q default

# Trigger manually
prefect deployment run "Predictive Maintenance - Daily"
"""

# ============================================================================
# EXEMPLO 9: Webhook para Alertas
# ============================================================================

import httpx

async def send_alert_to_slack(workflow_id: str, message: str):
    """Send workflow alert to Slack."""
    
    webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    
    payload = {
        "text": f"🚨 Resync Alert: {workflow_id}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ]
    }
    
    response = await httpx.AsyncClient().post(webhook_url, json=payload)
    return response.status_code == 200

# Exemplo de uso em workflows:
# async def example_usage():
#     await send_alert_to_slack(
#         workflow_id="pm_BACKUP_FULL_123",
#         message="⚠️ *High failure probability detected*\n"
#                 "Job: BACKUP_FULL\n"
#                 "Probability: 85%\n"
#                 "Estimated failure: 2024-12-30\n"
#                 "Action required: Review recommendations"
#     )

# ============================================================================
# EXEMPLO 10: Integration Test
# ============================================================================

async def integration_test():
    """Test completo do sistema."""
    
    print("1. Testing API health...")
    response = httpx.get("https://resync.company.com/api/v1/metrics/health")
    assert response.status_code == 200
    print("✓ API healthy")
    
    print("2. Testing metrics ingestion...")
    response = httpx.post(
        "https://resync.company.com/api/v1/metrics/workstation",
        headers={"X-API-Key": "YOUR_API_KEY"},
        json={
            "workstation": "TEST-WS",
            "timestamp": "2024-12-25T10:00:00Z",
            "metrics": {
                "cpu_percent": 50.0,
                "memory_percent": 60.0,
                "disk_percent": 70.0,
                "latency_avg_ms": 5.5
            }
        }
    )
    assert response.status_code in [200, 201]
    print("✓ Metrics ingested")
    
    print("3. Testing workflow execution...")
    result = await run_predictive_maintenance("TEST_JOB", lookback_days=7)
    assert result['status'] in ['completed', 'pending_review']
    print("✓ Workflow executed")
    
    print("\n✓ All tests passed!")

# Run integration test
asyncio.run(integration_test())
