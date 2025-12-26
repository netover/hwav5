"""
Testes para resync/tool_definitions/tws_tools.py
COBERTURA ALVO: 0% → 95%
FOCO: Ferramentas TWS (status, troubleshooting)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resync.core.exceptions import (
    ToolConnectionError,
    ToolExecutionError,
    ToolProcessingError,
    TWSConnectionError,
)
from resync.tools.definitions.tws import (
    TWSStatusTool,
    TWSTroubleshootingTool,
    tws_status_tool,
    tws_troubleshooting_tool,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_tws_client():
    """Mock do OptimizedTWSClient"""
    # Criar mock com spec para passar validação Pydantic
    from resync.services.tws_service import OptimizedTWSClient

    client = AsyncMock(spec=OptimizedTWSClient)

    # Mock de workstation
    mock_ws1 = MagicMock()
    mock_ws1.name = "TWS_PROD_01"
    mock_ws1.status = "LINKED"

    mock_ws2 = MagicMock()
    mock_ws2.name = "TWS_PROD_02"
    mock_ws2.status = "LINKED"

    # Mock de job
    mock_job1 = MagicMock()
    mock_job1.name = "BACKUP_DAILY"
    mock_job1.workstation = "TWS_PROD_01"
    mock_job1.status = "SUCC"

    mock_job2 = MagicMock()
    mock_job2.name = "DATA_PROCESSING"
    mock_job2.workstation = "TWS_PROD_02"
    mock_job2.status = "SUCC"

    # Mock de system status
    mock_status = MagicMock()
    mock_status.workstations = [mock_ws1, mock_ws2]
    mock_status.jobs = [mock_job1, mock_job2]

    client.get_system_status = AsyncMock(return_value=mock_status)

    return client


@pytest.fixture
def tws_status_tool_with_client(mock_tws_client):
    """TWSStatusTool com client mocado"""
    tool = TWSStatusTool()
    tool.tws_client = mock_tws_client  # Injetar diretamente após criação
    return tool


@pytest.fixture
def tws_troubleshooting_tool_with_client(mock_tws_client):
    """TWSTroubleshootingTool com client mocado"""
    tool = TWSTroubleshootingTool()
    tool.tws_client = mock_tws_client  # Injetar diretamente após criação
    return tool


# ============================================================================
# TESTES DE TWSStatusTool - HAPPY PATH
# ============================================================================


class TestTWSStatusToolHappyPath:
    """Testes de casos bem-sucedidos do TWSStatusTool"""

    @pytest.mark.asyncio
    async def test_get_tws_status_success(self, tws_status_tool_with_client):
        """Teste busca bem-sucedida de status TWS"""
        # Arrange
        tool = tws_status_tool_with_client

        # Act
        result = await tool.get_tws_status()

        # Assert
        assert result is not None
        assert "Situação atual do TWS" in result
        assert "TWS_PROD_01" in result
        assert "TWS_PROD_02" in result
        assert "BACKUP_DAILY" in result
        assert "DATA_PROCESSING" in result
        assert "LINKED" in result
        assert "SUCC" in result

    @pytest.mark.asyncio
    async def test_get_tws_status_formats_workstations(self, tws_status_tool_with_client):
        """Teste formatação de workstations no resultado"""
        # Arrange
        tool = tws_status_tool_with_client

        # Act
        result = await tool.get_tws_status()

        # Assert
        assert "Workstations:" in result
        assert "TWS_PROD_01 (LINKED)" in result
        assert "TWS_PROD_02 (LINKED)" in result

    @pytest.mark.asyncio
    async def test_get_tws_status_formats_jobs(self, tws_status_tool_with_client):
        """Teste formatação de jobs no resultado"""
        # Arrange
        tool = tws_status_tool_with_client

        # Act
        result = await tool.get_tws_status()

        # Assert
        assert "Jobs:" in result
        assert "BACKUP_DAILY on TWS_PROD_01 (SUCC)" in result
        assert "DATA_PROCESSING on TWS_PROD_02 (SUCC)" in result

    @pytest.mark.asyncio
    async def test_get_tws_status_empty_workstations(self, mock_tws_client):
        """Teste quando não há workstations"""
        # Arrange
        mock_status = MagicMock()
        mock_status.workstations = []
        mock_status.jobs = []
        mock_tws_client.get_system_status = AsyncMock(return_value=mock_status)

        tool = TWSStatusTool()
        tool.tws_client = mock_tws_client

        # Act
        result = await tool.get_tws_status()

        # Assert
        assert "Nenhuma encontrada" in result

    @pytest.mark.asyncio
    async def test_get_tws_status_empty_jobs(self, mock_tws_client):
        """Teste quando não há jobs"""
        # Arrange
        mock_ws = MagicMock()
        mock_ws.name = "TWS_PROD_01"
        mock_ws.status = "LINKED"

        mock_status = MagicMock()
        mock_status.workstations = [mock_ws]
        mock_status.jobs = []
        mock_tws_client.get_system_status = AsyncMock(return_value=mock_status)

        tool = TWSStatusTool()
        tool.tws_client = mock_tws_client

        # Act
        result = await tool.get_tws_status()

        # Assert
        assert "Nenhum encontrado" in result
        assert "TWS_PROD_01" in result


# ============================================================================
# TESTES DE TWSStatusTool - ERROR HANDLING
# ============================================================================


class TestTWSStatusToolErrors:
    """Testes de erro do TWSStatusTool"""

    @pytest.mark.asyncio
    async def test_get_tws_status_no_client(self):
        """Teste erro quando client não está disponível"""
        # Arrange
        tool = TWSStatusTool(tws_client=None)

        # Act & Assert
        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.get_tws_status()

        assert "TWS client not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_tws_status_connection_error(self, mock_tws_client):
        """Teste erro de conexão com TWS"""
        # Arrange
        mock_tws_client.get_system_status = AsyncMock(
            side_effect=TWSConnectionError("Connection refused")
        )
        tool = TWSStatusTool()
        tool.tws_client = mock_tws_client

        # Act & Assert
        with pytest.raises(ToolConnectionError) as exc_info:
            await tool.get_tws_status()

        assert "Falha de comunicação com o TWS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_tws_status_value_error(self, mock_tws_client):
        """Teste erro de processamento de dados"""
        # Arrange
        mock_tws_client.get_system_status = AsyncMock(side_effect=ValueError("Invalid data format"))
        tool = TWSStatusTool()
        tool.tws_client = mock_tws_client

        # Act & Assert
        with pytest.raises(ToolProcessingError) as exc_info:
            await tool.get_tws_status()

        assert "Erro ao processar os dados" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_tws_status_unexpected_error(self, mock_tws_client):
        """Teste erro inesperado"""
        # Arrange
        mock_tws_client.get_system_status = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        tool = TWSStatusTool()
        tool.tws_client = mock_tws_client

        # Act & Assert
        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.get_tws_status()

        assert "erro inesperado" in str(exc_info.value).lower()


# ============================================================================
# TESTES DE TWSTroubleshootingTool - HAPPY PATH
# ============================================================================


class TestTWSTroubleshootingToolHappyPath:
    """Testes de casos bem-sucedidos do TWSTroubleshootingTool"""

    @pytest.mark.asyncio
    async def test_analyze_failures_no_issues(self, mock_tws_client):
        """Teste quando não há problemas"""
        # Arrange
        tool = TWSTroubleshootingTool()
        tool.tws_client = mock_tws_client

        # Act
        result = await tool.analyze_failures()

        # Assert
        assert result is not None
        assert "Nenhuma falha crítica encontrada" in result
        assert "ambiente TWS parece estável" in result

    @pytest.mark.asyncio
    async def test_analyze_failures_with_failed_jobs(self, mock_tws_client):
        """Teste detecção de jobs falhados"""
        # Arrange
        mock_ws = MagicMock()
        mock_ws.name = "TWS_PROD_01"
        mock_ws.status = "LINKED"

        mock_job_failed = MagicMock()
        mock_job_failed.name = "BACKUP_DAILY"
        mock_job_failed.workstation = "TWS_PROD_01"
        mock_job_failed.status = "ABEND"

        mock_status = MagicMock()
        mock_status.workstations = [mock_ws]
        mock_status.jobs = [mock_job_failed]
        mock_tws_client.get_system_status = AsyncMock(return_value=mock_status)

        tool = TWSTroubleshootingTool()
        tool.tws_client = mock_tws_client

        # Act
        result = await tool.analyze_failures()

        # Assert
        assert "Análise de Problemas no TWS" in result
        assert "Jobs com Falha" in result
        assert "BACKUP_DAILY" in result
        assert "TWS_PROD_01" in result

    @pytest.mark.asyncio
    async def test_analyze_failures_with_down_workstations(self, mock_tws_client):
        """Teste detecção de workstations com problema"""
        # Arrange
        mock_ws_down = MagicMock()
        mock_ws_down.name = "TWS_PROD_02"
        mock_ws_down.status = "UNLINKED"

        mock_status = MagicMock()
        mock_status.workstations = [mock_ws_down]
        mock_status.jobs = []
        mock_tws_client.get_system_status = AsyncMock(return_value=mock_status)

        tool = TWSTroubleshootingTool()
        tool.tws_client = mock_tws_client

        # Act
        result = await tool.analyze_failures()

        # Assert
        assert "Workstations com Problemas" in result
        assert "TWS_PROD_02" in result
        assert "UNLINKED" in result

    @pytest.mark.asyncio
    async def test_analyze_failures_multiple_issues(self, mock_tws_client):
        """Teste múltiplos problemas simultaneamente"""
        # Arrange
        mock_ws_down = MagicMock()
        mock_ws_down.name = "TWS_PROD_02"
        mock_ws_down.status = "UNLINKED"

        mock_job1_failed = MagicMock()
        mock_job1_failed.name = "BACKUP_DAILY"
        mock_job1_failed.workstation = "TWS_PROD_01"
        mock_job1_failed.status = "ABEND"

        mock_job2_failed = MagicMock()
        mock_job2_failed.name = "DATA_SYNC"
        mock_job2_failed.workstation = "TWS_PROD_02"
        mock_job2_failed.status = "ABEND"

        mock_status = MagicMock()
        mock_status.workstations = [mock_ws_down]
        mock_status.jobs = [mock_job1_failed, mock_job2_failed]
        mock_tws_client.get_system_status = AsyncMock(return_value=mock_status)

        tool = TWSTroubleshootingTool()
        tool.tws_client = mock_tws_client

        # Act
        result = await tool.analyze_failures()

        # Assert
        assert "Jobs com Falha (2)" in result
        assert "Workstations com Problemas (1)" in result
        assert "BACKUP_DAILY" in result
        assert "DATA_SYNC" in result
        assert "TWS_PROD_02" in result

    @pytest.mark.asyncio
    async def test_analyze_failures_case_insensitive_status(self, mock_tws_client):
        """Teste que status é case insensitive"""
        # Arrange
        mock_job_abend = MagicMock()
        mock_job_abend.name = "JOB1"
        mock_job_abend.workstation = "WS1"
        mock_job_abend.status = "abend"  # lowercase

        mock_job_abend2 = MagicMock()
        mock_job_abend2.name = "JOB2"
        mock_job_abend2.workstation = "WS2"
        mock_job_abend2.status = "ABEND"  # uppercase

        mock_status = MagicMock()
        mock_status.workstations = []
        mock_status.jobs = [mock_job_abend, mock_job_abend2]
        mock_tws_client.get_system_status = AsyncMock(return_value=mock_status)

        tool = TWSTroubleshootingTool()
        tool.tws_client = mock_tws_client

        # Act
        result = await tool.analyze_failures()

        # Assert
        assert "Jobs com Falha (2)" in result
        assert "JOB1" in result
        assert "JOB2" in result


# ============================================================================
# TESTES DE TWSTroubleshootingTool - ERROR HANDLING
# ============================================================================


class TestTWSTroubleshootingToolErrors:
    """Testes de erro do TWSTroubleshootingTool"""

    @pytest.mark.asyncio
    async def test_analyze_failures_no_client(self):
        """Teste erro quando client não está disponível"""
        # Arrange
        tool = TWSTroubleshootingTool(tws_client=None)

        # Act & Assert
        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.analyze_failures()

        assert "TWS client not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_analyze_failures_connection_error(self, mock_tws_client):
        """Teste erro de conexão"""
        # Arrange
        mock_tws_client.get_system_status = AsyncMock(
            side_effect=TWSConnectionError("Connection timeout")
        )
        tool = TWSTroubleshootingTool()
        tool.tws_client = mock_tws_client

        # Act & Assert
        with pytest.raises(ToolConnectionError) as exc_info:
            await tool.analyze_failures()

        assert "Falha de comunicação" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_analyze_failures_value_error(self, mock_tws_client):
        """Teste erro de processamento"""
        # Arrange
        mock_tws_client.get_system_status = AsyncMock(
            side_effect=ValueError("Invalid status format")
        )
        tool = TWSTroubleshootingTool()
        tool.tws_client = mock_tws_client

        # Act & Assert
        with pytest.raises(ToolProcessingError) as exc_info:
            await tool.analyze_failures()

        assert "Erro ao processar" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_analyze_failures_attribute_error(self, mock_tws_client):
        """Teste erro de atributo ausente"""
        # Arrange
        mock_tws_client.get_system_status = AsyncMock(
            side_effect=AttributeError("'NoneType' object has no attribute 'status'")
        )
        tool = TWSTroubleshootingTool()
        tool.tws_client = mock_tws_client

        # Act & Assert
        with pytest.raises(ToolProcessingError) as exc_info:
            await tool.analyze_failures()

        assert "Erro ao processar" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_analyze_failures_unexpected_error(self, mock_tws_client):
        """Teste erro inesperado"""
        # Arrange
        mock_tws_client.get_system_status = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        tool = TWSTroubleshootingTool()
        tool.tws_client = mock_tws_client

        # Act & Assert
        with pytest.raises(ToolExecutionError) as exc_info:
            await tool.analyze_failures()

        assert "erro inesperado" in str(exc_info.value).lower()


# ============================================================================
# TESTES DE INSTÂNCIAS GLOBAIS
# ============================================================================


class TestToolInstances:
    """Testes para instâncias globais dos tools"""

    def test_tws_status_tool_instance_exists(self):
        """Teste que instância global existe"""
        # Assert
        assert tws_status_tool is not None
        assert isinstance(tws_status_tool, TWSStatusTool)

    def test_tws_troubleshooting_tool_instance_exists(self):
        """Teste que instância global existe"""
        # Assert
        assert tws_troubleshooting_tool is not None
        assert isinstance(tws_troubleshooting_tool, TWSTroubleshootingTool)

    def test_tool_instances_are_singletons(self):
        """Teste que instâncias globais são reutilizáveis"""
        # Arrange - Get references
        tool1 = tws_status_tool
        tool2 = tws_status_tool

        # Assert - Same instance
        assert tool1 is tool2


# ============================================================================
# TESTES DE MODELO BASE TWSToolReadOnly
# ============================================================================


class TestTWSToolReadOnlyModel:
    """Testes para modelo base TWSToolReadOnly"""

    def test_tool_creation_without_client(self):
        """Teste criação de tool sem client"""
        # Arrange & Act
        tool = TWSStatusTool()

        # Assert
        assert tool.tws_client is None

    def test_tool_creation_with_client(self, mock_tws_client):
        """Teste criação de tool com client"""
        # Arrange & Act
        tool = TWSStatusTool()
        tool.tws_client = mock_tws_client

        # Assert
        assert tool.tws_client is not None
        assert tool.tws_client == mock_tws_client

    def test_tool_client_injection(self, mock_tws_client):
        """Teste injeção de client após criação"""
        # Arrange
        tool = TWSStatusTool()
        assert tool.tws_client is None

        # Act
        tool.tws_client = mock_tws_client

        # Assert
        assert tool.tws_client is not None
        assert tool.tws_client == mock_tws_client


# ============================================================================
# TESTES DE INTEGRAÇÃO
# ============================================================================


@pytest.mark.integration
class TestTWSToolsIntegration:
    """Testes de integração entre tools"""

    @pytest.mark.asyncio
    async def test_sequential_tool_execution(self, mock_tws_client):
        """Teste execução sequencial de múltiplos tools"""
        # Arrange
        status_tool = TWSStatusTool()
        status_tool.tws_client = mock_tws_client
        troubleshooting_tool = TWSTroubleshootingTool()
        troubleshooting_tool.tws_client = mock_tws_client

        # Act
        status_result = await status_tool.get_tws_status()
        troubleshooting_result = await troubleshooting_tool.analyze_failures()

        # Assert
        assert status_result is not None
        assert troubleshooting_result is not None
        assert "Situação atual" in status_result
        assert mock_tws_client.get_system_status.call_count == 2

    @pytest.mark.asyncio
    async def test_same_client_multiple_tools(self, mock_tws_client):
        """Teste que mesmo client pode ser usado em múltiplos tools"""
        # Arrange
        tool1 = TWSStatusTool()
        tool1.tws_client = mock_tws_client
        tool2 = TWSTroubleshootingTool()
        tool2.tws_client = mock_tws_client

        # Act
        result1 = await tool1.get_tws_status()
        result2 = await tool2.analyze_failures()

        # Assert
        assert tool1.tws_client is tool2.tws_client
        assert result1 is not None
        assert result2 is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
