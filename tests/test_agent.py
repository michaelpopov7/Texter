"""
Unit tests for SMS AI Agent functionality.

Run with: pytest tests/test_agent.py -v
"""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from src.config import Config
from src.agent import SMSAgent
from src.memory import ConversationMemory
from src.exceptions import LLMProviderError


class TestSMSAgent:
    """Test cases for SMSAgent class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing."""
        config = Mock(spec=Config)
        config.openai_api_key = "test-key"
        config.anthropic_api_key = None
        config.primary_llm_provider = "openai"
        config.agent_name = "Test Agent"
        config.agent_personality = "helpful and testing"
        config.max_sms_length = 160
        config.message_truncation_suffix = "..."
        config.debug_mode = False
        config.get_llm_config.return_value = {
            'provider': 'openai',
            'api_key': 'test-key',
            'model': 'gpt-3.5-turbo',
            'temperature': 0.7,
            'max_tokens': 150
        }
        return config
    
    @pytest.fixture
    def mock_memory(self):
        """Create a mock memory manager for testing."""
        memory = Mock(spec=ConversationMemory)
        memory.get_memory_for_user.return_value = Mock()
        memory.add_user_message = Mock()
        memory.add_ai_message = Mock()
        return memory
    
    def test_agent_initialization(self, mock_config, mock_memory):
        """Test that agent initializes correctly."""
        with patch('src.agent.ChatOpenAI') as mock_llm:
            agent = SMSAgent(mock_config, mock_memory)
            assert agent.config == mock_config
            assert agent.memory_manager == mock_memory
            mock_llm.assert_called_once()
    
    def test_llm_initialization_openai(self, mock_config, mock_memory):
        """Test OpenAI LLM initialization."""
        with patch('src.agent.ChatOpenAI') as mock_openai:
            agent = SMSAgent(mock_config, mock_memory)
            mock_openai.assert_called_once_with(
                openai_api_key='test-key',
                model_name='gpt-3.5-turbo',
                temperature=0.7,
                max_tokens=150,
                timeout=30
            )
    
    def test_llm_initialization_anthropic(self, mock_config, mock_memory):
        """Test Anthropic LLM initialization."""
        mock_config.anthropic_api_key = "test-anthropic-key"
        mock_config.openai_api_key = None
        mock_config.primary_llm_provider = "anthropic"
        mock_config.get_llm_config.return_value = {
            'provider': 'anthropic',
            'api_key': 'test-anthropic-key',
            'model': 'claude-3-haiku-20240307',
            'max_tokens': 150
        }
        
        with patch('src.agent.ChatAnthropic') as mock_anthropic:
            agent = SMSAgent(mock_config, mock_memory)
            mock_anthropic.assert_called_once_with(
                anthropic_api_key='test-anthropic-key',
                model='claude-3-haiku-20240307',
                max_tokens=150,
                timeout=30
            )
    
    def test_llm_initialization_failure(self, mock_config, mock_memory):
        """Test LLM initialization failure handling."""
        mock_config.get_llm_config.return_value = {
            'provider': 'unknown',
            'api_key': 'test-key'
        }
        
        with pytest.raises(LLMProviderError):
            SMSAgent(mock_config, mock_memory)
    
    @pytest.mark.asyncio
    async def test_process_message_success(self, mock_config, mock_memory):
        """Test successful message processing."""
        # Mock the agent executor
        mock_executor = Mock()
        mock_executor.invoke.return_value = {"output": "Hello! How can I help you?"}
        
        # Mock memory
        mock_user_memory = Mock()
        mock_user_memory.chat_memory.messages = []
        mock_memory.get_memory_for_user.return_value = mock_user_memory
        
        with patch('src.agent.ChatOpenAI'), \
             patch('src.agent.create_react_agent'), \
             patch('src.agent.AgentExecutor', return_value=mock_executor):
            
            agent = SMSAgent(mock_config, mock_memory)
            
            response = await agent.process_message(
                phone_number="+1234567890",
                message="Hello",
                request_id="test-123"
            )
            
            assert response == "Hello! How can I help you?"
            mock_memory.add_user_message.assert_called_once_with("+1234567890", "Hello")
            mock_memory.add_ai_message.assert_called_once_with("+1234567890", "Hello! How can I help you?")
    
    @pytest.mark.asyncio
    async def test_process_message_error_handling(self, mock_config, mock_memory):
        """Test error handling in message processing."""
        # Mock the agent executor to raise an exception
        mock_executor = Mock()
        mock_executor.invoke.side_effect = Exception("Test error")
        
        # Mock memory
        mock_user_memory = Mock()
        mock_user_memory.chat_memory.messages = []
        mock_memory.get_memory_for_user.return_value = mock_user_memory
        
        with patch('src.agent.ChatOpenAI'), \
             patch('src.agent.create_react_agent'), \
             patch('src.agent.AgentExecutor', return_value=mock_executor):
            
            agent = SMSAgent(mock_config, mock_memory)
            
            response = await agent.process_message(
                phone_number="+1234567890",
                message="Hello",
                request_id="test-123"
            )
            
            # Should return a graceful error message
            assert "technical difficulties" in response.lower()
    
    def test_format_response_for_sms_normal(self, mock_config, mock_memory):
        """Test SMS response formatting for normal length messages."""
        with patch('src.agent.ChatOpenAI'), \
             patch('src.agent.create_react_agent'), \
             patch('src.agent.AgentExecutor'):
            
            agent = SMSAgent(mock_config, mock_memory)
            
            response = "This is a normal response."
            formatted = agent._format_response_for_sms(response)
            
            assert formatted == "This is a normal response."
    
    def test_format_response_for_sms_truncation(self, mock_config, mock_memory):
        """Test SMS response formatting with truncation."""
        mock_config.max_sms_length = 50
        mock_config.message_truncation_suffix = "..."
        
        with patch('src.agent.ChatOpenAI'), \
             patch('src.agent.create_react_agent'), \
             patch('src.agent.AgentExecutor'):
            
            agent = SMSAgent(mock_config, mock_memory)
            
            long_response = "This is a very long response that should be truncated because it exceeds the maximum SMS length."
            formatted = agent._format_response_for_sms(long_response)
            
            assert len(formatted) <= 50
            assert formatted.endswith("...")
    
    def test_get_agent_stats(self, mock_config, mock_memory):
        """Test getting agent statistics."""
        with patch('src.agent.ChatOpenAI'), \
             patch('src.agent.create_react_agent'), \
             patch('src.agent.AgentExecutor'):
            
            agent = SMSAgent(mock_config, mock_memory)
            
            stats = agent.get_agent_stats()
            
            assert "llm_provider" in stats
            assert "available_tools" in stats
            assert "tool_count" in stats
            assert "agent_name" in stats
    
    def test_clear_user_conversation(self, mock_config, mock_memory):
        """Test clearing user conversation."""
        with patch('src.agent.ChatOpenAI'), \
             patch('src.agent.create_react_agent'), \
             patch('src.agent.AgentExecutor'):
            
            agent = SMSAgent(mock_config, mock_memory)
            
            agent.clear_user_conversation("+1234567890")
            
            mock_memory.clear_conversation.assert_called_once_with("+1234567890")


class TestAgentIntegration:
    """Integration tests for agent components."""
    
    @pytest.mark.skipif(
        not os.getenv('OPENAI_API_KEY'),
        reason="OpenAI API key not available"
    )
    @pytest.mark.asyncio
    async def test_real_agent_response(self):
        """Test with real OpenAI API (requires API key)."""
        # This test requires actual API credentials
        # Only run if OPENAI_API_KEY is available
        
        config = Config()
        config.openai_api_key = os.getenv('OPENAI_API_KEY')
        config.local_development = True
        
        # Mock memory for this test
        mock_memory = Mock(spec=ConversationMemory)
        mock_user_memory = Mock()
        mock_user_memory.chat_memory.messages = []
        mock_memory.get_memory_for_user.return_value = mock_user_memory
        
        agent = SMSAgent(config, mock_memory)
        
        response = await agent.process_message(
            phone_number="+1234567890",
            message="Hello, what is 2+2?",
            request_id="integration-test"
        )
        
        assert isinstance(response, str)
        assert len(response) > 0
        assert "4" in response or "four" in response.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 