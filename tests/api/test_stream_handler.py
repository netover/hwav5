"""
Testes para resync/api/utils/stream_handler.py
COBERTURA ALVO: 0% → 95%
FOCO: Streaming de respostas via WebSocket
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocketDisconnect

from resync.api.utils.stream_handler import AgentResponseStreamer


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_websocket():
    """Mock do WebSocket"""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def mock_agent_streaming():
    """Mock de agent com suporte a streaming"""
    agent = AsyncMock()
    
    # Criar async generator para stream
    async def mock_stream(query):
        """Mock stream generator"""
        chunks = ["Hello", " ", "World", "!"]
        for chunk in chunks:
            yield chunk
    
    agent.stream = mock_stream
    agent.arun = AsyncMock(return_value="Fallback response")
    return agent


@pytest.fixture
def mock_agent_non_streaming():
    """Mock de agent SEM suporte a streaming"""
    agent = MagicMock()
    # Configurar arun como coroutine real
    async def mock_arun(query):
        return "Non-streaming response"
    agent.arun = mock_arun
    # Sem método stream (delattr para ter certeza)
    if hasattr(agent, 'stream'):
        delattr(agent, 'stream')
    return agent


# ============================================================================
# TESTES DE STREAMING - HAPPY PATH
# ============================================================================

class TestAgentResponseStreamerHappyPath:
    """Testes de casos bem-sucedidos de streaming"""
    
    @pytest.mark.asyncio
    async def test_stream_response_with_streaming_agent(
        self, mock_websocket, mock_agent_streaming
    ):
        """Teste streaming com agent que suporta stream()"""
        # Arrange
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        result = await streamer.stream_response(mock_agent_streaming, "Test query")
        
        # Assert
        assert result == "Hello World!"
        assert streamer.full_response == "Hello World!"
        # Verificar que send_json foi chamado para cada chunk + stream_end
        assert mock_websocket.send_json.call_count >= 4  # 4 chunks + stream_end
    
    
    @pytest.mark.asyncio
    async def test_stream_response_sends_chunks(
        self, mock_websocket, mock_agent_streaming
    ):
        """Teste que chunks são enviados individualmente"""
        # Arrange
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        await streamer.stream_response(mock_agent_streaming, "Test query")
        
        # Assert
        calls = mock_websocket.send_json.call_args_list
        
        # Verificar que chunks foram enviados
        chunk_calls = [call for call in calls if call[0][0].get("is_chunk")]
        assert len(chunk_calls) >= 4  # 4 chunks: "Hello", " ", "World", "!"
    
    
    @pytest.mark.asyncio
    async def test_stream_response_sends_stream_end(
        self, mock_websocket, mock_agent_streaming
    ):
        """Teste que stream_end marker é enviado"""
        # Arrange
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        await streamer.stream_response(mock_agent_streaming, "Test query")
        
        # Assert
        calls = mock_websocket.send_json.call_args_list
        
        # Verificar que stream_end foi enviado
        stream_end_calls = [
            call for call in calls 
            if call[0][0].get("type") == "stream_end"
        ]
        assert len(stream_end_calls) == 1
    
    
    @pytest.mark.asyncio
    async def test_stream_response_accumulates_full_response(
        self, mock_websocket, mock_agent_streaming
    ):
        """Teste que resposta completa é acumulada"""
        # Arrange
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        result = await streamer.stream_response(mock_agent_streaming, "Test query")
        
        # Assert
        assert result == "Hello World!"
        assert streamer.full_response == "Hello World!"


# ============================================================================
# TESTES DE NON-STREAMING
# ============================================================================

class TestAgentResponseStreamerNonStreaming:
    """Testes para agents sem streaming"""
    
    @pytest.mark.asyncio
    async def test_stream_response_non_streaming_agent(
        self, mock_websocket, mock_agent_non_streaming
    ):
        """Teste fallback para agent sem stream()"""
        # Arrange
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        result = await streamer.stream_response(
            mock_agent_non_streaming, "Test query"
        )
        
        # Assert
        assert result == "Non-streaming response"
        assert streamer.full_response == "Non-streaming response"
        # Verificar que mensagem foi enviada
        assert mock_websocket.send_json.call_count >= 1
    
    
    @pytest.mark.asyncio
    async def test_non_streaming_sends_single_message(
        self, mock_websocket, mock_agent_non_streaming
    ):
        """Teste que resposta não-streaming envia mensagem única"""
        # Arrange
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        await streamer.stream_response(mock_agent_non_streaming, "Test query")
        
        # Assert
        # Deve ter enviado 1 mensagem (não chunks)
        calls = mock_websocket.send_json.call_args_list
        assert len(calls) == 1
        
        # Verificar conteúdo da mensagem
        message = calls[0][0][0]
        assert message["message"] == "Non-streaming response"
        assert message["type"] == "stream"
    
    
    @pytest.mark.asyncio
    async def test_agent_without_stream_method(self, mock_websocket):
        """Teste agent que não tem método stream"""
        # Arrange
        agent = MagicMock()
        async def mock_arun(query):
            return "Fallback response"
        agent.arun = mock_arun
        # Sem método stream
        if hasattr(agent, 'stream'):
            delattr(agent, 'stream')
        
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        result = await streamer.stream_response(agent, "Test query")
        
        # Assert
        assert streamer.full_response == "Fallback response"
        assert result == "Fallback response"
        # Verificar que mensagem foi enviada
        assert mock_websocket.send_json.call_count >= 1


# ============================================================================
# TESTES DE ERROR HANDLING
# ============================================================================

class TestAgentResponseStreamerErrors:
    """Testes de tratamento de erros"""
    
    @pytest.mark.asyncio
    async def test_websocket_disconnect_during_streaming(
        self, mock_websocket, mock_agent_streaming
    ):
        """Teste desconexão durante streaming"""
        # Arrange
        mock_websocket.send_json = AsyncMock(
            side_effect=WebSocketDisconnect(code=1001)
        )
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act & Assert
        with pytest.raises(WebSocketDisconnect):
            await streamer.stream_response(mock_agent_streaming, "Test query")
    
    
    @pytest.mark.asyncio
    async def test_agent_raises_exception(self, mock_websocket):
        """Teste agent que levanta exceção"""
        # Arrange
        agent = AsyncMock()
        agent.stream = MagicMock(side_effect=RuntimeError("Agent error"))
        agent.arun = AsyncMock(side_effect=RuntimeError("Agent error"))
        
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        result = await streamer.stream_response(agent, "Test query")
        
        # Assert
        # Deve retornar mensagem de erro
        assert "Erro no processamento" in result
    
    
    @pytest.mark.asyncio
    async def test_error_message_sent_to_client(self, mock_websocket):
        """Teste que mensagem de erro é enviada ao cliente"""
        # Arrange
        agent = MagicMock()
        async def mock_arun_error(query):
            raise RuntimeError("Agent error")
        agent.arun = mock_arun_error
        # Sem método stream para forçar uso de arun
        if hasattr(agent, 'stream'):
            delattr(agent, 'stream')
        
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        await streamer.stream_response(agent, "Test query")
        
        # Assert
        # Verificar que mensagem de erro foi enviada
        calls = mock_websocket.send_json.call_args_list
        error_calls = [
            call for call in calls 
            if call[0][0].get("type") == "error"
        ]
        assert len(error_calls) >= 1
    
    
    @pytest.mark.asyncio
    async def test_error_sending_error_message(self, mock_websocket):
        """Teste quando falha ao enviar mensagem de erro"""
        # Arrange
        agent = MagicMock()
        async def mock_arun_error(query):
            raise RuntimeError("Agent error")
        agent.arun = mock_arun_error
        # Sem método stream
        if hasattr(agent, 'stream'):
            delattr(agent, 'stream')
        
        # Primeiro send_json falha (ao tentar enviar erro)
        mock_websocket.send_json = AsyncMock(
            side_effect=Exception("WebSocket closed")
        )
        
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act - Não deve levantar exceção
        result = await streamer.stream_response(agent, "Test query")
        
        # Assert
        assert "Erro no processamento" in result


# ============================================================================
# TESTES DE MENSAGENS
# ============================================================================

class TestAgentResponseStreamerMessages:
    """Testes de formatação de mensagens"""
    
    @pytest.mark.asyncio
    async def test_stream_message_format(
        self, mock_websocket, mock_agent_streaming
    ):
        """Teste formato de mensagem de streaming"""
        # Arrange
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        await streamer.stream_response(mock_agent_streaming, "Test query")
        
        # Assert
        calls = mock_websocket.send_json.call_args_list
        chunk_call = calls[0]  # Primeira mensagem
        message = chunk_call[0][0]
        
        assert message["type"] == "stream"
        assert message["sender"] == "agent"
        assert "message" in message
        assert "is_chunk" in message
    
    
    @pytest.mark.asyncio
    async def test_stream_end_message_format(
        self, mock_websocket, mock_agent_streaming
    ):
        """Teste formato de mensagem stream_end"""
        # Arrange
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        await streamer.stream_response(mock_agent_streaming, "Test query")
        
        # Assert
        calls = mock_websocket.send_json.call_args_list
        stream_end_call = calls[-1]  # Última mensagem
        message = stream_end_call[0][0]
        
        assert message["type"] == "stream_end"
    
    
    @pytest.mark.asyncio
    async def test_error_message_format(self, mock_websocket):
        """Teste formato de mensagem de erro"""
        # Arrange
        agent = MagicMock()
        async def mock_arun_error(query):
            raise RuntimeError("Test error")
        agent.arun = mock_arun_error
        # Sem método stream
        if hasattr(agent, 'stream'):
            delattr(agent, 'stream')
        
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        await streamer.stream_response(agent, "Test query")
        
        # Assert
        calls = mock_websocket.send_json.call_args_list
        error_call = [c for c in calls if c[0][0].get("type") == "error"][0]
        message = error_call[0][0]
        
        assert message["type"] == "error"
        assert message["sender"] == "system"
        assert "message" in message


# ============================================================================
# TESTES DE UTILIDADES
# ============================================================================

class TestAgentResponseStreamerUtilities:
    """Testes de métodos utilitários"""
    
    def test_is_async_iterator_with_async_generator(self):
        """Teste detecção de async iterator"""
        # Arrange
        async def async_gen():
            yield "test"
        
        gen = async_gen()
        
        # Act
        result = AgentResponseStreamer._is_async_iterator(gen)
        
        # Assert
        assert result is True
    
    
    def test_is_async_iterator_with_non_async(self):
        """Teste detecção de não-async iterator"""
        # Arrange
        regular_list = ["a", "b", "c"]
        
        # Act
        result = AgentResponseStreamer._is_async_iterator(regular_list)
        
        # Assert
        assert result is False
    
    
    def test_is_async_iterator_with_string(self):
        """Teste com string (não é async iterator)"""
        # Arrange
        text = "not an iterator"
        
        # Act
        result = AgentResponseStreamer._is_async_iterator(text)
        
        # Assert
        assert result is False


# ============================================================================
# TESTES DE INICIALIZAÇÃO
# ============================================================================

class TestAgentResponseStreamerInitialization:
    """Testes de inicialização do streamer"""
    
    def test_streamer_initialization(self, mock_websocket):
        """Teste inicialização básica"""
        # Arrange & Act
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Assert
        assert streamer.websocket == mock_websocket
        assert streamer.full_response == ""
    
    
    @pytest.mark.asyncio
    async def test_streamer_reset_between_calls(self, mock_websocket, mock_agent_streaming):
        """Teste que full_response não persiste entre chamadas"""
        # Arrange
        streamer1 = AgentResponseStreamer(mock_websocket)
        
        # Act
        result1 = await streamer1.stream_response(mock_agent_streaming, "Query 1")
        
        # Nova instância
        streamer2 = AgentResponseStreamer(mock_websocket)
        
        # Assert
        assert streamer2.full_response == ""
        assert streamer1.full_response == result1


# ============================================================================
# TESTES DE EDGE CASES
# ============================================================================

class TestAgentResponseStreamerEdgeCases:
    """Testes de casos edge"""
    
    @pytest.mark.asyncio
    async def test_empty_stream(self, mock_websocket):
        """Teste stream vazio"""
        # Arrange
        agent = AsyncMock()
        
        async def empty_stream(query):
            """Stream que não yielda nada"""
            return
            yield  # unreachable
        
        agent.stream = empty_stream
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        result = await streamer.stream_response(agent, "Test query")
        
        # Assert
        assert result == ""
        assert streamer.full_response == ""
    
    
    @pytest.mark.asyncio
    async def test_single_chunk_stream(self, mock_websocket):
        """Teste stream com único chunk"""
        # Arrange
        agent = AsyncMock()
        
        async def single_chunk_stream(query):
            yield "Single chunk"
        
        agent.stream = single_chunk_stream
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        result = await streamer.stream_response(agent, "Test query")
        
        # Assert
        assert result == "Single chunk"
        assert streamer.full_response == "Single chunk"
    
    
    @pytest.mark.asyncio
    async def test_large_chunks(self, mock_websocket):
        """Teste chunks muito grandes"""
        # Arrange
        agent = AsyncMock()
        
        async def large_chunk_stream(query):
            yield "A" * 1000
            yield "B" * 1000
        
        agent.stream = large_chunk_stream
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        result = await streamer.stream_response(agent, "Test query")
        
        # Assert
        assert len(result) == 2000
        assert "A" * 1000 in result
        assert "B" * 1000 in result
    
    
    @pytest.mark.asyncio
    async def test_unicode_in_stream(self, mock_websocket):
        """Teste caracteres Unicode no stream"""
        # Arrange
        agent = AsyncMock()
        
        async def unicode_stream(query):
            yield "Hello "
            yield "世界 "
            yield "🎉"
        
        agent.stream = unicode_stream
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        result = await streamer.stream_response(agent, "Test query")
        
        # Assert
        assert "Hello 世界 🎉" == result
    
    
    @pytest.mark.asyncio
    async def test_non_string_chunks(self, mock_websocket):
        """Teste chunks que não são string"""
        # Arrange
        agent = AsyncMock()
        
        async def mixed_type_stream(query):
            yield 123
            yield None
            yield {"data": "value"}
        
        agent.stream = mixed_type_stream
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        result = await streamer.stream_response(agent, "Test query")
        
        # Assert
        # Deve converter tudo para string
        assert "123" in result
        assert "None" in result
        assert "data" in result


# ============================================================================
# TESTES DE INTEGRAÇÃO
# ============================================================================

@pytest.mark.integration
class TestAgentResponseStreamerIntegration:
    """Testes de integração"""
    
    @pytest.mark.asyncio
    async def test_complete_streaming_workflow(self, mock_websocket):
        """Teste workflow completo de streaming"""
        # Arrange
        agent = AsyncMock()
        
        async def complete_stream(query):
            yield "Processing"
            yield " your"
            yield " request"
            yield "..."
        
        agent.stream = complete_stream
        streamer = AgentResponseStreamer(mock_websocket)
        
        # Act
        result = await streamer.stream_response(agent, "Complete workflow test")
        
        # Assert
        assert result == "Processing your request..."
        
        # Verificar sequência de mensagens
        calls = mock_websocket.send_json.call_args_list
        assert len(calls) >= 4  # 4 chunks + stream_end
        
        # Verificar que stream_end é a última
        assert calls[-1][0][0]["type"] == "stream_end"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
