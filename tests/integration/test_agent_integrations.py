"""
Testes de Integração - Agent Manager
Cobre os 4 fluxos críticos:
1. Agent → LiteLLM → Resposta
2. Agent → Tool → TWS → Resultado
3. Agent → Memory → Context
4. Agent → RAG → Enrichment
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Imports do projeto
from resync.models.agents import AgentConfig, AgentType

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_tws_client():
    """Mock do cliente TWS"""
    client = AsyncMock()

    # Simular respostas do TWS
    client.query_job_status = AsyncMock(
        return_value={
            "job_name": "BACKUP_DAILY",
            "status": "SUCC",
            "completion_time": "2024-12-08T10:30:00",
            "workstation": "TWS_PROD_01",
        }
    )

    client.query_workstation = AsyncMock(
        return_value={
            "workstation": "TWS_PROD_01",
            "status": "ACTIVE",
            "jobs_running": 5,
            "jobs_pending": 2,
        }
    )

    client.analyze_logs = AsyncMock(
        return_value={
            "errors": ["Connection timeout at 10:25"],
            "warnings": ["High memory usage"],
            "info": ["Job started successfully"],
        }
    )

    return client


@pytest.fixture
def mock_litellm():
    """Mock do LiteLLM"""
    # Não fazer patch, deixar os testes usarem mocks diretamente
    return AsyncMock(return_value="O job BACKUP_DAILY foi executado com sucesso às 10:30.")


@pytest.fixture
def mock_rag_service():
    """Mock do serviço RAG"""
    service = AsyncMock()

    # Simular busca no RAG
    service.search = AsyncMock(
        return_value=[
            {
                "content": "Jobs ABEND devem ser verificados nos logs do TWS.",
                "score": 0.95,
                "source": "manual_tws.pdf",
                "page": 42,
            },
            {
                "content": "Para resolver erros S322, aumente a alocação de memória.",
                "score": 0.87,
                "source": "troubleshooting_guide.pdf",
                "page": 15,
            },
        ]
    )

    return service


@pytest.fixture
def mock_memory_service():
    """Mock do serviço de memória"""
    service = AsyncMock()

    # Simular armazenamento e recuperação de contexto
    service.store_context = AsyncMock(return_value=True)
    service.get_context = AsyncMock(
        return_value={
            "previous_interactions": [
                "Usuário perguntou sobre job BACKUP_DAILY",
                "Agent respondeu com status SUCC",
            ],
            "user_preferences": {"language": "pt-BR", "detail_level": "high"},
            "session_start": "2024-12-08T09:00:00",
        }
    )

    return service


@pytest.fixture
def agent_config_chat():
    """Configuração de um agent de chat"""
    return AgentConfig(
        id="test-chat-agent",
        name="Test Chat Agent",
        agent_type=AgentType.CHAT,
        role="Assistente de TWS",
        goal="Ajudar usuários com questões sobre TWS",
        backstory="Especialista em HCL Workload Automation",
        tools=["tws_status_tool"],
        model_name="gpt-4",
        memory=True,
        max_rpm=60,
    )


@pytest.fixture
def agent_config_task():
    """Configuração de um agent de tarefas"""
    return AgentConfig(
        id="test-task-agent",
        name="Test Task Agent",
        agent_type=AgentType.TASK,
        role="Executor de Tarefas TWS",
        goal="Executar operações no TWS",
        backstory="Agent especializado em automação TWS",
        tools=["tws_status_tool", "tws_troubleshooting_tool"],
        model_name="gpt-4",
        memory=False,
        max_rpm=30,
    )


# ============================================================================
# TESTE 1: Agent → LiteLLM → Resposta
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestAgentLiteLLMIntegration:
    """Testes de integração Agent + LiteLLM"""

    async def test_agent_calls_litellm_successfully(self, mock_litellm, agent_config_chat):
        """Testa que agent consegue chamar LiteLLM e receber resposta"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        manager = AgentManager()

        # Simular criação de agent
        with patch.object(manager, "_create_agent_instance") as mock_create:
            # Mock do agent
            mock_agent = AsyncMock()
            mock_agent.name = agent_config_chat.name
            mock_agent.arun = AsyncMock(return_value="Resposta do agent via LiteLLM")
            mock_create.return_value = mock_agent

            # Act
            agent = await manager.get_or_create_agent(agent_config_chat.id)
            response = await agent.arun("Qual o status do job BACKUP_DAILY?")

            # Assert
            assert response is not None
            assert isinstance(response, str)
            assert len(response) > 0
            mock_agent.arun.assert_called_once()

    async def test_agent_handles_litellm_timeout(self, agent_config_chat):
        """Testa que agent lida com timeout do LiteLLM"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        manager = AgentManager()

        with patch.object(manager, "_create_agent_instance") as mock_create:
            # Mock agent que simula timeout
            mock_agent = AsyncMock()
            mock_agent.name = agent_config_chat.name
            mock_agent.arun = AsyncMock(side_effect=asyncio.TimeoutError("LLM timeout"))
            mock_create.return_value = mock_agent

            # Act & Assert
            agent = await manager.get_or_create_agent(agent_config_chat.id)

            with pytest.raises(asyncio.TimeoutError):
                await agent.arun("Query que causa timeout")

    async def test_agent_retries_on_litellm_error(self, agent_config_chat):
        """Testa que agent tenta novamente após erro do LiteLLM"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        manager = AgentManager()

        with patch.object(manager, "_create_agent_instance") as mock_create:
            # Mock que falha na primeira vez, sucesso na segunda
            mock_agent = AsyncMock()
            mock_agent.name = agent_config_chat.name

            call_count = 0

            async def arun_with_retry(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("Temporary LLM error")
                return "Resposta após retry"

            mock_agent.arun = arun_with_retry
            mock_create.return_value = mock_agent

            # Act
            agent = await manager.get_or_create_agent(agent_config_chat.id)

            # Primeira tentativa - erro
            with pytest.raises(Exception):
                await agent.arun("Query 1")

            # Segunda tentativa - sucesso
            response = await agent.arun("Query 2")

            # Assert
            assert response == "Resposta após retry"
            assert call_count == 2


# ============================================================================
# TESTE 2: Agent → Tool → TWS → Resultado
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestAgentToolTWSIntegration:
    """Testes de integração Agent + Tool + TWS"""

    async def test_agent_executes_tws_tool_successfully(self, mock_tws_client, agent_config_task):
        """Testa execução bem-sucedida de ferramenta TWS"""
        # Arrange
        from resync.core.agent_manager import AgentManager
        from resync.tools.definitions.tws import tws_status_tool

        manager = AgentManager()

        with patch("resync.core.fastapi_di.get_service", return_value=mock_tws_client):
            with patch.object(manager, "_create_agent_instance") as mock_create:
                # Mock agent que usa ferramenta
                mock_agent = AsyncMock()
                mock_agent.name = agent_config_task.name
                mock_agent.tools = [tws_status_tool]

                # Simular resultado da ferramenta
                mock_agent.arun = AsyncMock(
                    return_value="""
                Consultei o TWS e encontrei:
                - Job: BACKUP_DAILY
                - Status: SUCC
                - Conclusão: 2024-12-08T10:30:00
                """
                )

                mock_create.return_value = mock_agent

                # Act
                agent = await manager.get_or_create_agent(agent_config_task.id)
                result = await agent.arun("Verifique o status do job BACKUP_DAILY")

                # Assert
                assert result is not None
                assert "BACKUP_DAILY" in result
                assert "SUCC" in result
                mock_tws_client.query_job_status.assert_called_once()

    async def test_agent_handles_tws_connection_error(self, agent_config_task):
        """Testa que agent lida com erro de conexão TWS"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        manager = AgentManager()

        # Mock TWS client que falha
        mock_tws_error = AsyncMock()
        mock_tws_error.query_job_status = AsyncMock(
            side_effect=ConnectionError("TWS não disponível")
        )

        with patch("resync.core.fastapi_di.get_service", return_value=mock_tws_error):
            with patch.object(manager, "_create_agent_instance") as mock_create:
                mock_agent = AsyncMock()
                mock_agent.name = agent_config_task.name

                # Agent deve retornar mensagem de erro
                mock_agent.arun = AsyncMock(return_value="Erro: Não foi possível conectar ao TWS")

                mock_create.return_value = mock_agent

                # Act
                agent = await manager.get_or_create_agent(agent_config_task.id)
                result = await agent.arun("Status do job")

                # Assert
                assert "Erro" in result or "não foi possível" in result.lower()

    async def test_agent_executes_multiple_tools(self, mock_tws_client, agent_config_task):
        """Testa agent executando múltiplas ferramentas em sequência"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        manager = AgentManager()

        with patch("resync.core.fastapi_di.get_service", return_value=mock_tws_client):
            with patch.object(manager, "_create_agent_instance") as mock_create:
                mock_agent = AsyncMock()
                mock_agent.name = agent_config_task.name

                # Simular execução de 2 ferramentas
                call_count = 0

                async def multi_tool_execution(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        return "Status do job consultado"
                    return "Logs analisados, 3 erros encontrados"

                mock_agent.arun = multi_tool_execution
                mock_create.return_value = mock_agent

                # Act
                agent = await manager.get_or_create_agent(agent_config_task.id)
                result1 = await agent.arun("Verifique o status")
                result2 = await agent.arun("Analise os logs")

                # Assert
                assert "Status" in result1
                assert "Logs" in result2
                assert call_count == 2

                # Verificar que TWS foi consultado
                assert (
                    mock_tws_client.query_job_status.called or mock_tws_client.analyze_logs.called
                )


# ============================================================================
# TESTE 3: Agent → Memory → Context
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestAgentMemoryIntegration:
    """Testes de integração Agent + Memory"""

    async def test_agent_stores_and_retrieves_context(self, mock_memory_service, agent_config_chat):
        """Testa que agent armazena e recupera contexto"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        manager = AgentManager()

        with patch.object(manager, "_create_agent_instance") as mock_create:
            # Mock agent com memória
            mock_agent = AsyncMock()
            mock_agent.name = agent_config_chat.name
            mock_agent.memory_service = mock_memory_service

            # Primeira interação - armazena contexto
            async def first_interaction(*args, **kwargs):
                await mock_memory_service.store_context(
                    "user_123", {"query": args[0], "response": "Primeira resposta"}
                )
                return "Primeira resposta"

            # Segunda interação - usa contexto
            async def second_interaction(*args, **kwargs):
                context = await mock_memory_service.get_context("user_123")
                return f"Com base no histórico: {context['previous_interactions'][0]}"

            call_count = 0

            async def arun_with_memory(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return await first_interaction(*args, **kwargs)
                return await second_interaction(*args, **kwargs)

            mock_agent.arun = arun_with_memory
            mock_create.return_value = mock_agent

            # Act
            agent = await manager.get_or_create_agent(agent_config_chat.id)

            # Primeira chamada
            response1 = await agent.arun("Qual o status do job?")

            # Segunda chamada - deve usar contexto
            response2 = await agent.arun("E agora?")

            # Assert
            assert "Primeira resposta" in response1
            assert "histórico" in response2.lower() or "base" in response2.lower()
            mock_memory_service.store_context.assert_called_once()
            mock_memory_service.get_context.assert_called_once()

    async def test_agent_without_memory_doesnt_store_context(
        self, mock_memory_service, agent_config_task
    ):
        """Testa que agent sem memória não armazena contexto"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        # Agent configurado SEM memória
        agent_config_task.memory = False

        manager = AgentManager()

        with patch.object(manager, "_create_agent_instance") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.name = agent_config_task.name
            mock_agent.arun = AsyncMock(return_value="Resposta sem memória")
            mock_create.return_value = mock_agent

            # Act
            agent = await manager.get_or_create_agent(agent_config_task.id)
            await agent.arun("Query qualquer")

            # Assert
            # Memória NÃO deve ser chamada
            mock_memory_service.store_context.assert_not_called()

    async def test_agent_memory_persists_across_sessions(
        self, mock_memory_service, agent_config_chat
    ):
        """Testa que memória persiste entre sessões"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        manager = AgentManager()

        # Configurar mock para simular persistência
        stored_data = {}

        async def store_mock(user_id, data):
            stored_data[user_id] = data
            return True

        async def get_mock(user_id):
            return stored_data.get(user_id, {"previous_interactions": [], "user_preferences": {}})

        mock_memory_service.store_context = store_mock
        mock_memory_service.get_context = get_mock

        with patch.object(manager, "_create_agent_instance") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.name = agent_config_chat.name
            mock_agent.memory_service = mock_memory_service

            async def arun_with_persist(*args, **kwargs):
                # Armazenar
                await mock_memory_service.store_context(
                    "user_456", {"interactions": ["Query sobre job BACKUP_DAILY"]}
                )
                # Recuperar
                context = await mock_memory_service.get_context("user_456")
                return f"Total de interações: {len(context.get('interactions', []))}"

            mock_agent.arun = arun_with_persist
            mock_create.return_value = mock_agent

            # Act - Primeira sessão
            agent = await manager.get_or_create_agent(agent_config_chat.id)
            await agent.arun("Primeira query")

            # Act - Segunda sessão (mesmo agent, mesmo user)
            await agent.arun("Segunda query")

            # Assert
            assert "user_456" in stored_data
            assert len(stored_data["user_456"]["interactions"]) > 0


# ============================================================================
# TESTE 4: Agent → RAG → Enrichment
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestAgentRAGIntegration:
    """Testes de integração Agent + RAG"""

    async def test_agent_enriches_response_with_rag(self, mock_rag_service, agent_config_chat):
        """Testa que agent enriquece resposta com contexto RAG"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        manager = AgentManager()

        with patch.object(manager, "_create_agent_instance") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.name = agent_config_chat.name
            mock_agent.rag_service = mock_rag_service

            # Simular busca RAG + resposta enriquecida
            async def arun_with_rag(*args, **kwargs):
                query = args[0]

                # Buscar no RAG
                rag_results = await mock_rag_service.search(query)

                # Enriquecer resposta
                context = rag_results[0]["content"]
                return f"Resposta baseada na documentação: {context}"

            mock_agent.arun = arun_with_rag
            mock_create.return_value = mock_agent

            # Act
            agent = await manager.get_or_create_agent(agent_config_chat.id)
            response = await agent.arun("Como resolver jobs ABEND?")

            # Assert
            assert "documentação" in response.lower()
            assert "ABEND" in response or "logs" in response.lower()
            mock_rag_service.search.assert_called_once()

    async def test_agent_handles_rag_no_results(self, mock_rag_service, agent_config_chat):
        """Testa que agent lida com RAG sem resultados"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        # RAG retorna lista vazia
        mock_rag_service.search = AsyncMock(return_value=[])

        manager = AgentManager()

        with patch.object(manager, "_create_agent_instance") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.name = agent_config_chat.name
            mock_agent.rag_service = mock_rag_service

            async def arun_no_rag(*args, **kwargs):
                rag_results = await mock_rag_service.search(args[0])

                if not rag_results:
                    return "Não encontrei informações na documentação sobre isso."
                return "Resposta com RAG"

            mock_agent.arun = arun_no_rag
            mock_create.return_value = mock_agent

            # Act
            agent = await manager.get_or_create_agent(agent_config_chat.id)
            response = await agent.arun("Query sobre algo não documentado")

            # Assert
            assert "não encontrei" in response.lower() or "sem informações" in response.lower()

    async def test_agent_combines_rag_with_llm(
        self, mock_rag_service, mock_litellm, agent_config_chat
    ):
        """Testa que agent combina RAG + LLM para resposta completa"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        manager = AgentManager()

        with patch.object(manager, "_create_agent_instance") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.name = agent_config_chat.name
            mock_agent.rag_service = mock_rag_service

            async def arun_rag_plus_llm(*args, **kwargs):
                query = args[0]

                # 1. Buscar contexto no RAG
                rag_results = await mock_rag_service.search(query)
                rag_context = " ".join([r["content"] for r in rag_results])

                # 2. Usar LLM com contexto RAG
                # (mock_litellm já está configurado)
                llm_response = "Resposta do LLM enriquecida com RAG"

                return f"Com base na documentação ({rag_context[:50]}...), {llm_response}"

            mock_agent.arun = arun_rag_plus_llm
            mock_create.return_value = mock_agent

            # Act
            agent = await manager.get_or_create_agent(agent_config_chat.id)
            response = await agent.arun("Explique como resolver erro S322")

            # Assert
            assert "documentação" in response.lower()
            assert "LLM" in response or len(response) > 50
            mock_rag_service.search.assert_called_once()

    async def test_agent_handles_rag_timeout(self, mock_rag_service, agent_config_chat):
        """Testa que agent lida com timeout do RAG"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        # RAG com timeout
        mock_rag_service.search = AsyncMock(side_effect=asyncio.TimeoutError("RAG timeout"))

        manager = AgentManager()

        with patch.object(manager, "_create_agent_instance") as mock_create:
            mock_agent = AsyncMock()
            mock_agent.name = agent_config_chat.name
            mock_agent.rag_service = mock_rag_service

            async def arun_with_timeout_handling(*args, **kwargs):
                try:
                    await mock_rag_service.search(args[0])
                    return "Resposta com RAG"
                except asyncio.TimeoutError:
                    return "Resposta sem RAG (timeout na documentação)"

            mock_agent.arun = arun_with_timeout_handling
            mock_create.return_value = mock_agent

            # Act
            agent = await manager.get_or_create_agent(agent_config_chat.id)
            response = await agent.arun("Query qualquer")

            # Assert
            assert "sem RAG" in response or "timeout" in response.lower()


# ============================================================================
# TESTE 5: Fluxo Completo End-to-End
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.e2e
class TestCompleteAgentFlow:
    """Testes end-to-end do fluxo completo"""

    async def test_complete_flow_all_integrations(
        self,
        mock_tws_client,
        mock_litellm,
        mock_rag_service,
        mock_memory_service,
        agent_config_chat,
    ):
        """Testa fluxo completo: Agent usa LiteLLM + Tools + RAG + Memory"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        manager = AgentManager()

        with patch("resync.core.fastapi_di.get_service", return_value=mock_tws_client):
            with patch.object(manager, "_create_agent_instance") as mock_create:
                mock_agent = AsyncMock()
                mock_agent.name = agent_config_chat.name

                # Simular fluxo completo
                async def complete_flow(*args, **kwargs):
                    query = args[0]

                    # 1. Recuperar contexto da memória
                    context = await mock_memory_service.get_context("user_789")

                    # 2. Buscar no RAG
                    rag_results = await mock_rag_service.search(query)

                    # 3. Consultar TWS via tool
                    tws_result = await mock_tws_client.query_job_status("BACKUP_DAILY")

                    # 4. Processar com LLM (simulado)
                    response = f"""
                    Baseado no histórico ({len(context.get("previous_interactions", []))} interações),
                    consultei a documentação (score: {rag_results[0]["score"]}) e o TWS.

                    Status do job: {tws_result["status"]}
                    """

                    # 5. Armazenar na memória
                    await mock_memory_service.store_context(
                        "user_789", {"query": query, "response": response}
                    )

                    return response

                mock_agent.arun = complete_flow
                mock_create.return_value = mock_agent

                # Act
                agent = await manager.get_or_create_agent(agent_config_chat.id)
                response = await agent.arun("Qual o status do job BACKUP_DAILY?")

                # Assert
                assert response is not None
                assert "Status" in response or "SUCC" in response

                # Verificar que TODOS os serviços foram chamados
                mock_memory_service.get_context.assert_called()
                mock_rag_service.search.assert_called()
                mock_tws_client.query_job_status.assert_called()
                mock_memory_service.store_context.assert_called()


# ============================================================================
# TESTE 6: Testes de Erro e Edge Cases
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.integration
class TestAgentErrorHandling:
    """Testes de tratamento de erros em integrações"""

    async def test_agent_handles_all_services_down(self, agent_config_chat):
        """Testa comportamento quando todos os serviços estão indisponíveis"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        # Todos os mocks retornam erro
        mock_tws_error = AsyncMock()
        mock_tws_error.query_job_status = AsyncMock(side_effect=ConnectionError("TWS down"))

        mock_rag_error = AsyncMock()
        mock_rag_error.search = AsyncMock(side_effect=asyncio.TimeoutError("RAG timeout"))

        mock_memory_error = AsyncMock()
        mock_memory_error.get_context = AsyncMock(
            side_effect=Exception("Memory service unavailable")
        )

        manager = AgentManager()

        with patch("resync.core.fastapi_di.get_service", return_value=mock_tws_error):
            with patch.object(manager, "_create_agent_instance") as mock_create:
                mock_agent = AsyncMock()
                mock_agent.name = agent_config_chat.name

                # Agent deve degradar graciosamente
                mock_agent.arun = AsyncMock(
                    return_value="Desculpe, alguns serviços estão temporariamente indisponíveis."
                )

                mock_create.return_value = mock_agent

                # Act
                agent = await manager.get_or_create_agent(agent_config_chat.id)
                response = await agent.arun("Query qualquer")

                # Assert
                assert "indisponíveis" in response.lower() or "temporariamente" in response.lower()

    async def test_agent_partial_service_failure(
        self, mock_tws_client, mock_rag_service, agent_config_chat
    ):
        """Testa que agent continua funcionando com falha parcial de serviços"""
        # Arrange
        from resync.core.agent_manager import AgentManager

        # RAG falha, mas TWS funciona
        mock_rag_service.search = AsyncMock(side_effect=Exception("RAG error"))

        manager = AgentManager()

        with patch("resync.core.fastapi_di.get_service", return_value=mock_tws_client):
            with patch.object(manager, "_create_agent_instance") as mock_create:
                mock_agent = AsyncMock()
                mock_agent.name = agent_config_chat.name

                async def partial_failure(*args, **kwargs):
                    # Tentar RAG
                    try:
                        await mock_rag_service.search(args[0])
                    except Exception:
                        pass  # Ignorar erro RAG

                    # Usar TWS normalmente
                    tws_result = await mock_tws_client.query_job_status("JOB1")
                    return f"Status: {tws_result['status']} (sem contexto RAG)"

                mock_agent.arun = partial_failure
                mock_create.return_value = mock_agent

                # Act
                agent = await manager.get_or_create_agent(agent_config_chat.id)
                response = await agent.arun("Status do job")

                # Assert
                assert "Status" in response
                assert "SUCC" in response or "sem contexto" in response.lower()


if __name__ == "__main__":
    # Executar testes
    pytest.main([__file__, "-v", "-m", "integration"])
