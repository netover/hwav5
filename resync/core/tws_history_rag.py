"""
TWS RAG Integration - Ingestão de Status para Consultas Históricas

Este módulo permite queries em linguagem natural sobre o histórico do TWS,
como "o que aconteceu ontem?" ou "quais jobs falharam na semana passada?".

Funcionalidades:
- Ingestão de eventos/status para RAG
- Processamento de queries temporais
- Geração de resumos contextuais
- Integração com LLM para respostas

Autor: Resync Team
Versão: 5.2
"""

import re
from datetime import datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class TWSHistoryRAG:
    """
    Componente RAG para consultas históricas do TWS.

    Permite que usuários façam perguntas em linguagem natural
    sobre o histórico de jobs, workstations e eventos.
    """

    # Padrões temporais em português e inglês
    TIME_PATTERNS = {
        # Português
        r"ontem": lambda: (datetime.now() - timedelta(days=1), datetime.now() - timedelta(days=1)),
        r"hoje": lambda: (datetime.now(), datetime.now()),
        r"essa semana|esta semana|semana atual": lambda: (
            datetime.now() - timedelta(days=datetime.now().weekday()),
            datetime.now(),
        ),
        r"semana passada|última semana": lambda: (
            datetime.now() - timedelta(days=datetime.now().weekday() + 7),
            datetime.now() - timedelta(days=datetime.now().weekday()),
        ),
        r"esse mês|este mês|mês atual": lambda: (datetime.now().replace(day=1), datetime.now()),
        r"mês passado|último mês": lambda: (
            (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1),
            datetime.now().replace(day=1) - timedelta(days=1),
        ),
        r"últimos? (\d+) dias?": lambda m: (
            datetime.now() - timedelta(days=int(m.group(1))),
            datetime.now(),
        ),
        r"últimas? (\d+) horas?": lambda m: (
            datetime.now() - timedelta(hours=int(m.group(1))),
            datetime.now(),
        ),
        # English
        r"yesterday": lambda: (
            datetime.now() - timedelta(days=1),
            datetime.now() - timedelta(days=1),
        ),
        r"today": lambda: (datetime.now(), datetime.now()),
        r"this week": lambda: (
            datetime.now() - timedelta(days=datetime.now().weekday()),
            datetime.now(),
        ),
        r"last week": lambda: (
            datetime.now() - timedelta(days=datetime.now().weekday() + 7),
            datetime.now() - timedelta(days=datetime.now().weekday()),
        ),
        r"last (\d+) days?": lambda m: (
            datetime.now() - timedelta(days=int(m.group(1))),
            datetime.now(),
        ),
        r"last (\d+) hours?": lambda m: (
            datetime.now() - timedelta(hours=int(m.group(1))),
            datetime.now(),
        ),
    }

    # Padrões de intenção
    INTENT_PATTERNS = {
        "failures": [
            r"falh(ou|aram|as?)|abend|erro|problem",
            r"fail(ed|ures?)|error|problem",
            r"o que deu errado",
            r"what (went wrong|failed)",
        ],
        "summary": [
            r"resum(o|ir)|acontec(eu|eram)",
            r"summar(y|ize)|happened|overview",
            r"o que (aconteceu|houve)",
            r"what happened",
        ],
        "workstations": [
            r"workstation|ws|servidor|agent",
            r"offline|online|status",
        ],
        "specific_job": [
            r"job (\w+)",
            r"cadeia (\w+)",
            r"stream (\w+)",
        ],
        "patterns": [
            r"padr(ão|ões)|tend(ência|ências)|recorr",
            r"pattern|trend|recurring",
        ],
    }

    def __init__(self, status_store: Any = None, llm_client: Any = None):
        """
        Inicializa o componente RAG.

        Args:
            status_store: TWSStatusStore para acesso aos dados
            llm_client: Cliente LLM para geração de respostas
        """
        self.status_store = status_store
        self.llm_client = llm_client

        logger.info("tws_history_rag_initialized")

    async def query(self, question: str) -> dict[str, Any]:
        """
        Processa uma query em linguagem natural.

        Args:
            question: Pergunta do usuário

        Returns:
            Resposta estruturada com contexto e texto
        """
        logger.info("processing_history_query", question=question)

        # 1. Extrai período temporal
        start_date, end_date = self._extract_time_range(question)

        # 2. Identifica intenção
        intent = self._identify_intent(question)

        # 3. Extrai entidades específicas (job names, etc.)
        entities = self._extract_entities(question)

        # 4. Busca dados relevantes
        context = await self._gather_context(start_date, end_date, intent, entities)

        # 5. Gera resposta
        response = await self._generate_response(question, context)

        return {
            "success": True,
            "question": question,
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "intent": intent,
            "entities": entities,
            "context": context,
            "response": response,
        }

    def _extract_time_range(self, text: str) -> tuple[datetime, datetime]:
        """Extrai período temporal da query."""
        text_lower = text.lower()

        for pattern, resolver in self.TIME_PATTERNS.items():
            match = re.search(pattern, text_lower)
            if match:
                try:
                    if callable(resolver):
                        # Verifica se é um pattern com grupos
                        result = resolver(match) if match.groups() else resolver()

                        start, end = result

                        # Ajusta para início e fim do dia
                        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
                        end = end.replace(hour=23, minute=59, second=59, microsecond=999999)

                        return start, end
                except Exception as e:
                    logger.warning("time_extraction_error", pattern=pattern, error=str(e))

        # Default: últimas 24 horas
        end = datetime.now()
        start = end - timedelta(hours=24)
        return start, end

    def _identify_intent(self, text: str) -> str:
        """Identifica a intenção da query."""
        text_lower = text.lower()

        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent

        return "summary"  # Default

    def _extract_entities(self, text: str) -> dict[str, list[str]]:
        """Extrai entidades mencionadas na query."""
        entities = {
            "jobs": [],
            "workstations": [],
            "streams": [],
        }

        # Padrões para jobs
        job_patterns = [
            r"job[s]?\s+([A-Z0-9_]+)",
            r"([A-Z][A-Z0-9_]{2,})",  # Nomes em maiúsculo
        ]

        for pattern in job_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities["jobs"].extend([m.upper() for m in matches])

        # Remove duplicatas
        entities["jobs"] = list(set(entities["jobs"]))

        # Padrões para workstations
        ws_patterns = [
            r"workstation\s+(\w+)",
            r"ws\s+(\w+)",
            r"servidor\s+(\w+)",
        ]

        for pattern in ws_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities["workstations"].extend(matches)

        entities["workstations"] = list(set(entities["workstations"]))

        return entities

    async def _gather_context(
        self,
        start_date: datetime,
        end_date: datetime,
        intent: str,
        entities: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Coleta contexto relevante do histórico."""
        context = {
            "events": [],
            "summary": {},
            "patterns": [],
            "job_history": {},
        }

        if not self.status_store:
            logger.warning("no_status_store_available")
            return context

        try:
            # Busca eventos do período
            if intent in ["summary", "failures"]:
                events = await self.status_store.get_events_in_range(
                    start_time=start_date,
                    end_time=end_date,
                    severity="error" if intent == "failures" else None,
                    limit=200,
                )
                context["events"] = events

            # Resumo diário
            if intent == "summary":
                context["summary"] = await self.status_store.get_daily_summary(start_date)

            # Histórico de jobs específicos
            for job_name in entities.get("jobs", []):
                history = await self.status_store.get_job_history(
                    job_name=job_name,
                    days=(end_date - start_date).days + 1,
                    limit=50,
                )
                if history:
                    context["job_history"][job_name] = history

            # Padrões detectados
            if intent == "patterns":
                patterns = await self.status_store.get_patterns(min_confidence=0.5)
                context["patterns"] = patterns

        except Exception as e:
            logger.error("context_gathering_error", error=str(e))

        return context

    async def _generate_response(
        self,
        question: str,
        context: dict[str, Any],
    ) -> str:
        """Gera resposta em linguagem natural."""

        # Se temos LLM, usa para gerar resposta mais elaborada
        if self.llm_client:
            return await self._generate_llm_response(question, context)

        # Fallback: resposta baseada em templates
        return self._generate_template_response(context)

    async def _generate_llm_response(
        self,
        question: str,
        context: dict[str, Any],
    ) -> str:
        """Gera resposta usando LLM."""
        try:
            # Prepara contexto para o LLM
            context_text = self._format_context_for_llm(context)

            prompt = f"""Você é um assistente especializado em HCL Workload Automation (TWS).
Com base nos dados históricos fornecidos, responda à pergunta do usuário de forma clara e objetiva.

DADOS HISTÓRICOS:
{context_text}

PERGUNTA DO USUÁRIO:
{question}

RESPOSTA:"""

            # Chama LLM
            return await self.llm_client.generate(prompt)

        except Exception as e:
            logger.error("llm_response_error", error=str(e))
            return self._generate_template_response(context)

    def _format_context_for_llm(self, context: dict[str, Any]) -> str:
        """Formata contexto para prompt do LLM."""
        parts = []

        # Resumo
        if context.get("summary"):
            summary = context["summary"]
            parts.append(f"RESUMO DO DIA {summary.get('date', 'N/A')}:")
            parts.append(f"- Jobs completados: {summary.get('status_counts', {}).get('SUCC', 0)}")
            parts.append(f"- Jobs com falha: {summary.get('status_counts', {}).get('ABEND', 0)}")
            parts.append(f"- Total de eventos: {summary.get('total_events', 0)}")
            parts.append(f"- Eventos críticos: {summary.get('critical_events', 0)}")
            parts.append("")

        # Eventos relevantes
        events = context.get("events", [])
        if events:
            parts.append(f"EVENTOS ({len(events)} encontrados):")
            for event in events[:20]:  # Limita para não sobrecarregar
                parts.append(
                    f"- [{event.get('severity', 'N/A').upper()}] "
                    f"{event.get('timestamp', 'N/A')}: {event.get('message', 'N/A')}"
                )
            if len(events) > 20:
                parts.append(f"... e mais {len(events) - 20} eventos")
            parts.append("")

        # Histórico de jobs
        job_history = context.get("job_history", {})
        for job_name, history in job_history.items():
            parts.append(f"HISTÓRICO DO JOB {job_name}:")
            for record in history[:10]:
                parts.append(
                    f"- {record.get('timestamp', 'N/A')}: "
                    f"Status={record.get('status', 'N/A')}, "
                    f"RC={record.get('return_code', 'N/A')}"
                )
            parts.append("")

        # Padrões
        patterns = context.get("patterns", [])
        if patterns:
            parts.append("PADRÕES DETECTADOS:")
            for pattern in patterns[:5]:
                parts.append(
                    f"- {pattern.get('description', 'N/A')} "
                    f"(confiança: {pattern.get('confidence', 0) * 100:.0f}%)"
                )
            parts.append("")

        return "\n".join(parts)

    def _generate_template_response(self, context: dict[str, Any]) -> str:
        """Gera resposta baseada em templates."""
        parts = []

        # Resumo
        if context.get("summary"):
            summary = context["summary"]
            parts.append(f"📊 **Resumo de {summary.get('date', 'hoje')}:**")
            parts.append(summary.get("summary", "Sem dados disponíveis."))
            parts.append("")

        # Falhas
        events = context.get("events", [])
        failures = [e for e in events if e.get("severity") in ["error", "critical"]]

        if failures:
            parts.append(f"⚠️ **{len(failures)} eventos de erro/crítico:**")
            for event in failures[:5]:
                parts.append(f"- {event.get('message', 'N/A')}")
            if len(failures) > 5:
                parts.append(f"... e mais {len(failures) - 5}")
            parts.append("")

        # Jobs específicos
        job_history = context.get("job_history", {})
        for job_name, history in job_history.items():
            success_count = sum(1 for h in history if h.get("status") == "SUCC")
            fail_count = sum(1 for h in history if h.get("status") == "ABEND")
            parts.append(f"📋 **Job {job_name}:** {success_count} sucessos, {fail_count} falhas")

        # Padrões
        patterns = context.get("patterns", [])
        if patterns:
            parts.append("\n🔍 **Padrões detectados:**")
            for pattern in patterns[:3]:
                parts.append(f"- {pattern.get('description', 'N/A')}")

        if not parts:
            return "Não encontrei dados relevantes para o período especificado."

        return "\n".join(parts)

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    async def what_happened_yesterday(self) -> dict[str, Any]:
        """Atalho para 'o que aconteceu ontem?'"""
        return await self.query("o que aconteceu ontem?")

    async def failures_today(self) -> dict[str, Any]:
        """Atalho para 'quais jobs falharam hoje?'"""
        return await self.query("quais jobs falharam hoje?")

    async def job_status(self, job_name: str, days: int = 7) -> dict[str, Any]:
        """Atalho para histórico de um job."""
        return await self.query(f"histórico do job {job_name} nos últimos {days} dias")

    async def detected_patterns(self) -> dict[str, Any]:
        """Atalho para padrões detectados."""
        return await self.query("quais padrões foram detectados?")


# =============================================================================
# TOOL DEFINITION FOR AGENT
# =============================================================================

TWS_HISTORY_TOOL = {
    "type": "function",
    "function": {
        "name": "query_tws_history",
        "description": """Consulta o histórico do TWS (HCL Workload Automation).
Use para responder perguntas sobre:
- O que aconteceu em um período (ontem, semana passada, etc.)
- Quais jobs falharam
- Status de jobs específicos
- Padrões de falha detectados
- Problemas em workstations""",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Pergunta em linguagem natural sobre o histórico do TWS",
                },
            },
            "required": ["question"],
        },
    },
}


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_rag_instance: TWSHistoryRAG | None = None


def get_tws_history_rag() -> TWSHistoryRAG | None:
    """Retorna instância singleton do RAG."""
    return _rag_instance


def init_tws_history_rag(
    status_store: Any = None,
    llm_client: Any = None,
) -> TWSHistoryRAG:
    """Inicializa o RAG singleton."""
    global _rag_instance

    _rag_instance = TWSHistoryRAG(
        status_store=status_store,
        llm_client=llm_client,
    )

    return _rag_instance
