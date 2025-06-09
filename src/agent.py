"""
SMS AI Agent Implementation

This module contains the main LangChain ReAct agent that handles SMS conversations,
maintains memory, and uses tools to provide enhanced responses.
"""

import time
from typing import Dict, Any, Optional

import structlog
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from .config import Config
from .memory import ConversationMemory
from .tools import ToolManager
from .exceptions import LLMProviderError, AgentToolError


logger = structlog.get_logger(__name__)


class SMSAgent:
    """Main SMS AI agent that handles conversations and tool usage."""
    
    def __init__(self, config: Config, memory_manager: ConversationMemory):
        """
        Initialize the SMS agent.
        
        Args:
            config: Application configuration
            memory_manager: Conversation memory manager
        """
        self.config = config
        self.memory_manager = memory_manager
        
        # Initialize LLM
        self.llm = self._initialize_llm()
        
        # Initialize tools
        self.tool_manager = ToolManager(config)
        
        # Create agent
        self.agent_executor = self._create_agent()
        
        logger.info(
            "SMS Agent initialized",
            llm_provider=config.primary_llm_provider,
            tool_count=len(self.tool_manager.get_tools())
        )
    
    def _initialize_llm(self):
        """Initialize the language model based on configuration."""
        llm_config = self.config.get_llm_config()
        
        try:
            if llm_config['provider'] == 'openai':
                llm = ChatOpenAI(
                    openai_api_key=llm_config['api_key'],
                    model_name=llm_config['model'],
                    temperature=llm_config['temperature'],
                    max_tokens=llm_config['max_tokens'],
                    timeout=30
                )
                logger.info("Initialized OpenAI LLM", model=llm_config['model'])
                
            elif llm_config['provider'] == 'anthropic':
                llm = ChatAnthropic(
                    anthropic_api_key=llm_config['api_key'],
                    model=llm_config['model'],
                    max_tokens=llm_config['max_tokens'],
                    timeout=30
                )
                logger.info("Initialized Anthropic LLM", model=llm_config['model'])
                
            else:
                raise LLMProviderError(f"Unknown LLM provider: {llm_config['provider']}")
            
            return llm
            
        except Exception as e:
            logger.error("Failed to initialize LLM", error=str(e), provider=llm_config['provider'])
            raise LLMProviderError(f"LLM initialization failed: {e}")
    
    def _create_agent(self) -> AgentExecutor:
        """Create the ReAct agent with tools and memory."""
        # Create custom prompt template optimized for SMS
        prompt_template = self._create_sms_prompt_template()
        
        # Create the ReAct agent
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tool_manager.get_tools(),
            prompt=prompt_template
        )
        
        # Create agent executor with proper configuration
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tool_manager.get_tools(),
            verbose=self.config.debug_mode,
            max_iterations=5,  # Limit iterations for SMS context
            handle_parsing_errors=True,
            return_intermediate_steps=False
        )
        
        return agent_executor
    
    def _create_sms_prompt_template(self) -> PromptTemplate:
        """Create a prompt template optimized for SMS conversations."""
        template = """You are {agent_name}, a helpful AI assistant accessible via SMS. 
You are {agent_personality}.

IMPORTANT SMS CONSTRAINTS:
- Keep responses concise and under 160 characters when possible
- Use clear, conversational language
- Break long responses into shorter messages if needed
- Be helpful and direct

AVAILABLE TOOLS:
{tools}

CONVERSATION CONTEXT:
{chat_history}

Current conversation:
User: {input}

Think about what the user needs and determine if you should use any tools to help them.

{agent_scratchpad}

Remember: Keep your response concise and SMS-friendly. If you need to use a tool, be specific about what information you're looking for."""
        
        return PromptTemplate(
            template=template,
            input_variables=["input", "chat_history", "agent_scratchpad"],
            partial_variables={
                "agent_name": self.config.agent_name,
                "agent_personality": self.config.agent_personality,
                "tools": self._format_tools_for_prompt()
            }
        )
    
    def _format_tools_for_prompt(self) -> str:
        """Format available tools for the prompt."""
        tools_text = []
        for tool in self.tool_manager.get_tools():
            tools_text.append(f"- {tool.name}: {tool.description}")
        
        return "\n".join(tools_text)
    
    async def process_message(self, 
                            phone_number: str, 
                            message: str, 
                            request_id: str) -> str:
        """
        Process an incoming SMS message and generate a response.
        
        Args:
            phone_number: User's phone number
            message: User's message content
            request_id: Unique request identifier for logging
            
        Returns:
            AI agent's response message
        """
        start_time = time.time()
        
        logger.info(
            "Processing message",
            phone_number=phone_number,
            message_length=len(message),
            request_id=request_id
        )
        
        try:
            # Get user's conversation memory
            memory = self.memory_manager.get_memory_for_user(phone_number)
            
            # Add user message to memory
            self.memory_manager.add_user_message(phone_number, message)
            
            # Get conversation context
            chat_history = self._format_chat_history(memory)
            
            # Prepare agent input
            agent_input = {
                "input": message,
                "chat_history": chat_history
            }
            
            # Run the agent
            logger.debug("Invoking agent", request_id=request_id)
            result = self.agent_executor.invoke(agent_input)
            
            # Extract the response
            response = result.get("output", "I'm sorry, I couldn't process that message.")
            
            # Ensure response is SMS-appropriate
            response = self._format_response_for_sms(response)
            
            # Add AI response to memory
            self.memory_manager.add_ai_message(phone_number, response)
            
            processing_time = time.time() - start_time
            
            logger.info(
                "Message processed successfully",
                phone_number=phone_number,
                response_length=len(response),
                processing_time=processing_time,
                request_id=request_id
            )
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            logger.error(
                "Error processing message",
                phone_number=phone_number,
                error=str(e),
                processing_time=processing_time,
                request_id=request_id
            )
            
            # Return a graceful error message
            error_response = self._get_error_response(e)
            
            # Still add to memory for consistency
            try:
                self.memory_manager.add_ai_message(phone_number, error_response)
            except Exception:
                pass  # Don't fail on memory error during error handling
            
            return error_response
    
    def _format_chat_history(self, memory) -> str:
        """Format chat history for the agent prompt."""
        try:
            messages = memory.chat_memory.messages
            if not messages:
                return "No previous conversation."
            
            # Format recent messages (last 10)
            formatted_messages = []
            for message in messages[-10:]:
                if hasattr(message, 'content'):
                    if message.__class__.__name__ == 'HumanMessage':
                        formatted_messages.append(f"User: {message.content}")
                    elif message.__class__.__name__ == 'AIMessage':
                        formatted_messages.append(f"Assistant: {message.content}")
            
            return "\n".join(formatted_messages) if formatted_messages else "No previous conversation."
            
        except Exception as e:
            logger.warning("Error formatting chat history", error=str(e))
            return "Previous conversation unavailable."
    
    def _format_response_for_sms(self, response: str) -> str:
        """Format response to be appropriate for SMS."""
        if not response:
            return "I'm sorry, I couldn't generate a response."
        
        # Remove excessive whitespace
        response = " ".join(response.split())
        
        # Truncate if too long, but try to keep it readable
        max_length = self.config.max_sms_length
        if len(response) > max_length:
            # Try to truncate at a sentence boundary
            sentences = response.split('. ')
            truncated = ""
            
            for sentence in sentences:
                test_text = truncated + sentence + ". "
                if len(test_text) <= max_length - len(self.config.message_truncation_suffix):
                    truncated = test_text
                else:
                    break
            
            if truncated:
                response = truncated.rstrip() + self.config.message_truncation_suffix
            else:
                # Fall back to character truncation
                response = response[:max_length - len(self.config.message_truncation_suffix)] + self.config.message_truncation_suffix
        
        return response
    
    def _get_error_response(self, error: Exception) -> str:
        """Generate an appropriate error response for users."""
        if isinstance(error, LLMProviderError):
            return "I'm having trouble with my language processing right now. Please try again in a moment."
        elif isinstance(error, AgentToolError):
            return "I encountered an issue while looking up information. Please try rephrasing your question."
        else:
            return "I'm experiencing technical difficulties. Please try again later."
    
    def get_agent_stats(self) -> Dict[str, Any]:
        """Get statistics about the agent."""
        return {
            "llm_provider": self.config.primary_llm_provider,
            "available_tools": [tool.name for tool in self.tool_manager.get_tools()],
            "tool_count": len(self.tool_manager.get_tools()),
            "max_sms_length": self.config.max_sms_length,
            "agent_name": self.config.agent_name
        }
    
    def clear_user_conversation(self, phone_number: str) -> None:
        """Clear conversation history for a specific user."""
        self.memory_manager.clear_conversation(phone_number)
        logger.info("Cleared conversation for user", phone_number=phone_number) 