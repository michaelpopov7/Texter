"""
SMS Handler for Twilio Integration

This module handles SMS message processing, Twilio webhook responses,
and message formatting for the SMS AI agent.
"""

import asyncio
from typing import Dict, Any, Optional
from xml.sax.saxutils import escape

import structlog
from twilio.twiml.messaging_response import MessagingResponse

from .config import Config
from .agent import SMSAgent
from .exceptions import MessageProcessingError


logger = structlog.get_logger(__name__)


class SMSHandler:
    """Handles SMS message processing and Twilio webhook responses."""
    
    def __init__(self, config: Config, agent: SMSAgent):
        """
        Initialize SMS handler.
        
        Args:
            config: Application configuration
            agent: SMS AI agent instance
        """
        self.config = config
        self.agent = agent
        
        logger.info("SMS Handler initialized")
    
    def process_message(self, sms_data: Dict[str, Any], request_id: str) -> str:
        """
        Process incoming SMS message and generate TwiML response.
        
        Args:
            sms_data: Dictionary containing SMS message data
            request_id: Unique request identifier
            
        Returns:
            TwiML XML response string
        """
        try:
            # Extract message details
            phone_number = sms_data.get('from_number')
            message_body = sms_data.get('body', '').strip()
            message_sid = sms_data.get('message_sid')
            
            if not phone_number:
                raise MessageProcessingError("Missing phone number in SMS data")
            
            if not message_body:
                # Handle empty messages
                response_text = "I received your message but it appears to be empty. Please send me a text message and I'll be happy to help!"
                return self._create_twiml_response(response_text)
            
            logger.info(
                "Processing SMS message",
                phone_number=phone_number,
                message_length=len(message_body),
                message_sid=message_sid,
                request_id=request_id
            )
            
            # Check for special commands
            if self._is_special_command(message_body):
                response_text = self._handle_special_command(message_body, phone_number)
            else:
                # Process message through AI agent
                response_text = asyncio.run(
                    self.agent.process_message(phone_number, message_body, request_id)
                )
            
            # Create TwiML response
            twiml_response = self._create_twiml_response(response_text)
            
            logger.info(
                "SMS message processed successfully",
                phone_number=phone_number,
                response_length=len(response_text),
                request_id=request_id
            )
            
            return twiml_response
            
        except Exception as e:
            logger.error(
                "Error processing SMS message",
                error=str(e),
                request_id=request_id,
                sms_data=sms_data
            )
            
            # Create error response
            error_message = "I'm sorry, I encountered an error processing your message. Please try again."
            return self._create_twiml_response(error_message)
    
    def _is_special_command(self, message: str) -> bool:
        """Check if message is a special command."""
        message_lower = message.lower().strip()
        special_commands = [
            'help', '/help', '?',
            'reset', '/reset', 'clear',
            'status', '/status',
            'info', '/info'
        ]
        return message_lower in special_commands
    
    def _handle_special_command(self, message: str, phone_number: str) -> str:
        """Handle special commands."""
        command = message.lower().strip()
        
        if command in ['help', '/help', '?']:
            return self._get_help_message()
        
        elif command in ['reset', '/reset', 'clear']:
            self.agent.clear_user_conversation(phone_number)
            return "Your conversation history has been cleared. Starting fresh!"
        
        elif command in ['status', '/status']:
            return self._get_status_message()
        
        elif command in ['info', '/info']:
            return self._get_info_message()
        
        else:
            return "Unknown command. Type 'help' for available commands."
    
    def _get_help_message(self) -> str:
        """Get help message for users."""
        help_text = f"""
🤖 {self.config.agent_name} Help

I can help you with:
• Questions & conversations
• Weather information
• Math calculations
• Current time & date
• General assistance

Commands:
• help - Show this message
• reset - Clear conversation
• status - Check my status

Just text me naturally! 😊
""".strip()
        
        return help_text
    
    def _get_status_message(self) -> str:
        """Get status message."""
        stats = self.agent.get_agent_stats()
        
        status_text = f"""
🟢 {self.config.agent_name} Status: Online

Provider: {stats['llm_provider'].title()}
Tools: {stats['tool_count']} available
Memory: Active

Ready to help! 🚀
""".strip()
        
        return status_text
    
    def _get_info_message(self) -> str:
        """Get information about the agent."""
        info_text = f"""
ℹ️ {self.config.agent_name}

AI-powered SMS assistant
Powered by LangChain
Conversations remembered for 24h
Secure & private

How can I help you today?
""".strip()
        
        return info_text
    
    def _create_twiml_response(self, message: str) -> str:
        """
        Create TwiML response for Twilio.
        
        Args:
            message: Response message to send
            
        Returns:
            TwiML XML string
        """
        try:
            # Ensure message is not too long for SMS
            if len(message) > self.config.max_sms_length:
                # Split into multiple messages if needed
                return self._create_multi_message_response(message)
            
            # Create single message response
            response = MessagingResponse()
            response.message(message)
            
            return str(response)
            
        except Exception as e:
            logger.error("Error creating TwiML response", error=str(e), message=message)
            
            # Fallback response
            fallback_response = MessagingResponse()
            fallback_response.message("I'm having trouble responding right now. Please try again.")
            return str(fallback_response)
    
    def _create_multi_message_response(self, long_message: str) -> str:
        """
        Create TwiML response with multiple messages for long content.
        
        Args:
            long_message: Long message to split
            
        Returns:
            TwiML XML string with multiple messages
        """
        response = MessagingResponse()
        
        # Split message into chunks
        max_chunk_size = self.config.max_sms_length - 10  # Leave room for part indicators
        
        # Try to split at sentence boundaries first
        sentences = long_message.split('. ')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            test_chunk = current_chunk + sentence + ". "
            if len(test_chunk) <= max_chunk_size:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # If we still have chunks that are too long, split by characters
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= max_chunk_size:
                final_chunks.append(chunk)
            else:
                # Split by characters
                while len(chunk) > max_chunk_size:
                    final_chunks.append(chunk[:max_chunk_size])
                    chunk = chunk[max_chunk_size:]
                if chunk:
                    final_chunks.append(chunk)
        
        # Add messages to response
        for i, chunk in enumerate(final_chunks[:3]):  # Limit to 3 messages max
            if len(final_chunks) > 1:
                part_indicator = f"({i+1}/{min(len(final_chunks), 3)}) "
                message_text = part_indicator + chunk
            else:
                message_text = chunk
            
            response.message(message_text)
        
        # If there are more than 3 chunks, add a continuation message
        if len(final_chunks) > 3:
            response.message("(Message continued... type 'more' for the rest)")
        
        return str(response)
    
    def create_error_response(self, error_message: str) -> str:
        """
        Create a TwiML error response.
        
        Args:
            error_message: Error message to send
            
        Returns:
            TwiML XML string
        """
        try:
            response = MessagingResponse()
            response.message(error_message)
            return str(response)
        except Exception:
            # Absolute fallback
            return '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Service temporarily unavailable.</Message>
</Response>'''
    
    def validate_sms_data(self, sms_data: Dict[str, Any]) -> bool:
        """
        Validate SMS data contains required fields.
        
        Args:
            sms_data: SMS data dictionary
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['from_number', 'to_number', 'body']
        
        for field in required_fields:
            if field not in sms_data:
                logger.warning("Missing required SMS field", field=field)
                return False
        
        # Additional validation
        if not sms_data['from_number'].startswith('+'):
            logger.warning("Invalid phone number format", from_number=sms_data['from_number'])
            return False
        
        return True
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """Get SMS handler statistics."""
        return {
            "max_sms_length": self.config.max_sms_length,
            "agent_name": self.config.agent_name,
            "special_commands_enabled": True,
            "multi_message_support": True
        } 