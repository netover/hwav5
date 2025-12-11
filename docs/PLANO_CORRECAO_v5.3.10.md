# Plano de Correção v5.3.10

## Validação da Análise

| Item | Análise | Validação | Status |
|------|---------|-----------|--------|
| Ciclo agent_manager ↔ fastapi_di | Existe | ✅ Confirmado | CORRIGIR |
| Ciclo report_strategies ↔ soc2_compliance | Existe | ✅ Confirmado | CORRIGIR |
| Pacotes não usados (exceptions_pkg, etc.) | Não usados | ✅ Confirmado | MARCAR DEPRECATED |
| Imports não usados (~771) | Existem | ❌ Já limpos pelo Ruff | OK |
| except Exception sem exc_info | ~808 | ✅ Já corrigido (841 com exc_info) | OK |
| Status store em memória | Ephemeral | ✅ Confirmado | DOCUMENTAR |
| Threshold tuning hardcoded | 0.05/0.02 | ✅ Confirmado | PARAMETRIZAR |

## Prioridades de Correção

### ALTA PRIORIDADE
1. Resolver ciclos de import (risco de ImportError)
2. Marcar pacotes deprecated

### MÉDIA PRIORIDADE  
3. Documentar status_store como ephemeral
4. Parametrizar threshold tuning

### BAIXA PRIORIDADE
5. Melhorias de design (futura refatoração)

---

## Correções Executadas

### 1. ✅ Ciclo de Import: agent_manager ↔ fastapi_di

**Problema**: `fastapi_di.py` importava `AgentManager` no nível do módulo, criando ciclo com `agent_manager.py`.

**Solução**: Movido o import de `AgentManager` para dentro da função `configure_container()`.

```python
# ANTES (fastapi_di.py)
from resync.core.agent_manager import AgentManager  # Nível do módulo

# DEPOIS
def configure_container(...):
    from resync.core.agent_manager import AgentManager  # Lazy import
```

### 2. ✅ Ciclo de Import: report_strategies ↔ soc2_compliance

**Status**: Já mitigado - ambos os lados usam lazy imports dentro de funções/métodos.

### 3. ✅ Pacotes Não Usados Marcados como Deprecated

Adicionados avisos de deprecação a:
- `resync.core.exceptions_pkg`
- `resync.core.health_service_pkg`  
- `resync.core.security_dashboard_pkg`

```python
# Exemplo de aviso emitido
warnings.warn(
    "resync.core.exceptions_pkg is experimental and not integrated. "
    "Use resync.core.exceptions instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

### 4. ✅ Documentação do status_store Ephemeral

Adicionada documentação clara em `status.py`:

```python
"""
WARNING: EPHEMERAL STATE
========================
The _status_store is an in-memory dictionary that:
- Is NOT shared between multiple worker processes
- Is NOT persisted across server restarts
- Is intended for development/demo purposes only
"""
```

### 5. ✅ Parametrização do Threshold Tuning

Criada classe `ThresholdTuningConfig` com valores configuráveis:

```python
@dataclass
class ThresholdTuningConfig:
    threshold_name: str = "confidence"
    feedback_window: int = 100
    low_rate_threshold: float = 0.5
    high_rate_threshold: float = 0.8
    increase_delta: float = 0.05
    decrease_delta: float = 0.02
```

O método `auto_tune()` agora:
- Usa configuração parametrizada
- Retorna informações detalhadas (old_value, new_value)
- Permite override via parâmetro

---

## Resultado Final

| Item | Status |
|------|--------|
| Ciclo agent_manager ↔ fastapi_di | ✅ Corrigido |
| Ciclo report_strategies ↔ soc2_compliance | ✅ Já mitigado |
| Pacotes deprecated marcados | ✅ 3 pacotes |
| status_store documentado | ✅ Concluído |
| threshold_tuning parametrizado | ✅ Concluído |
| Ruff check | ✅ All passed |
| Sintaxe Python | ✅ All valid |

## Versão: v5.3.10
