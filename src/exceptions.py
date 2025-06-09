"""
Custom Exception Classes for SMS AI Agent

This module defines custom exceptions for better error handling
and debugging throughout the application.
"""


class SMSAgentError(Exception):
    """Base exception class for SMS Agent errors."""
    pass


class TwilioValidationError(SMSAgentError):
    """Raised when Twilio webhook validation fails."""
    pass


class ConversationMemoryError(SMSAgentError):
    """Raised when there's an issue with conversation memory operations."""
    pass


class LLMProviderError(SMSAgentError):
    """Raised when there's an issue with LLM provider interactions."""
    pass


class AgentToolError(SMSAgentError):
    """Raised when there's an issue with agent tool execution."""
    pass


class ConfigurationError(SMSAgentError):
    """Raised when there's a configuration issue."""
    pass


class RateLimitError(SMSAgentError):
    """Raised when rate limits are exceeded."""
    pass


class MessageProcessingError(SMSAgentError):
    """Raised when there's an issue processing SMS messages."""
    pass


class ExternalAPIError(SMSAgentError):
    """Raised when external API calls fail."""
    pass 