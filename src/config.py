"""
Configuration Management for SMS AI Agent

This module handles all configuration settings including environment variables,
API keys, and deployment-specific settings with proper validation.
"""

import os
from typing import Optional, List
from pydantic import BaseSettings, validator, Field
from pydantic_settings import BaseSettings as PydanticBaseSettings


class Config(PydanticBaseSettings):
    """Main configuration class with environment variable support and validation."""
    
    # Twilio Configuration
    twilio_account_sid: str = Field(..., env='TWILIO_ACCOUNT_SID')
    twilio_auth_token: str = Field(..., env='TWILIO_AUTH_TOKEN')
    twilio_phone_number: str = Field(..., env='TWILIO_PHONE_NUMBER')
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(None, env='OPENAI_API_KEY')
    openai_model: str = Field('gpt-3.5-turbo', env='OPENAI_MODEL')
    openai_temperature: float = Field(0.7, env='OPENAI_TEMPERATURE')
    openai_max_tokens: int = Field(150, env='OPENAI_MAX_TOKENS')
    
    # Anthropic Configuration
    anthropic_api_key: Optional[str] = Field(None, env='ANTHROPIC_API_KEY')
    anthropic_model: str = Field('claude-3-haiku-20240307', env='ANTHROPIC_MODEL')
    
    # Google Cloud Configuration
    google_cloud_project: Optional[str] = Field(None, env='GOOGLE_CLOUD_PROJECT')
    firestore_collection: str = Field('conversations', env='FIRESTORE_COLLECTION')
    
    # Agent Configuration
    agent_name: str = Field('AI Assistant', env='AGENT_NAME')
    agent_personality: str = Field(
        'helpful, friendly, and concise', 
        env='AGENT_PERSONALITY'
    )
    max_conversation_length: int = Field(20, env='MAX_CONVERSATION_LENGTH')
    conversation_timeout_hours: int = Field(24, env='CONVERSATION_TIMEOUT_HOURS')
    
    # SMS Configuration
    max_sms_length: int = Field(1600, env='MAX_SMS_LENGTH')  # Twilio limit
    message_truncation_suffix: str = Field('...', env='MESSAGE_TRUNCATION_SUFFIX')
    
    # External API Configuration
    openweather_api_key: Optional[str] = Field(None, env='OPENWEATHER_API_KEY')
    serpapi_key: Optional[str] = Field(None, env='SERPAPI_KEY')
    
    # Rate Limiting
    rate_limit_per_user_per_minute: int = Field(5, env='RATE_LIMIT_PER_USER_PER_MINUTE')
    rate_limit_per_user_per_hour: int = Field(50, env='RATE_LIMIT_PER_USER_PER_HOUR')
    
    # Development/Debug
    debug_mode: bool = Field(False, env='DEBUG_MODE')
    log_level: str = Field('INFO', env='LOG_LEVEL')
    local_development: bool = Field(False, env='LOCAL_DEVELOPMENT')
    
    # Security
    webhook_validation_enabled: bool = Field(True, env='WEBHOOK_VALIDATION_ENABLED')
    allowed_origins: List[str] = Field(['twilio.com'], env='ALLOWED_ORIGINS')
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        
    @validator('twilio_phone_number')
    def validate_phone_number(cls, v):
        """Validate Twilio phone number format."""
        if not v.startswith('+'):
            raise ValueError('Phone number must start with +')
        if len(v.replace('+', '').replace(' ', '').replace('-', '')) < 10:
            raise ValueError('Phone number must be at least 10 digits')
        return v
    
    @validator('openai_temperature')
    def validate_temperature(cls, v):
        """Validate OpenAI temperature parameter."""
        if not 0.0 <= v <= 2.0:
            raise ValueError('Temperature must be between 0.0 and 2.0')
        return v
    
    @validator('openai_max_tokens')
    def validate_max_tokens(cls, v):
        """Validate OpenAI max tokens parameter."""
        if v < 1 or v > 4000:
            raise ValueError('Max tokens must be between 1 and 4000')
        return v
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of: {valid_levels}')
        return v.upper()
    
    def validate(self) -> None:
        """Perform additional validation checks."""
        # Ensure at least one LLM provider is configured
        if not self.openai_api_key and not self.anthropic_api_key:
            raise ValueError(
                'At least one LLM provider must be configured '
                '(OpenAI or Anthropic)'
            )
        
        # Validate Google Cloud setup for production
        if not self.local_development and not self.google_cloud_project:
            raise ValueError(
                'GOOGLE_CLOUD_PROJECT must be set for production deployment'
            )
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return bool(self.google_cloud_project and not self.local_development)
    
    @property
    def primary_llm_provider(self) -> str:
        """Get the primary LLM provider to use."""
        if self.openai_api_key:
            return 'openai'
        elif self.anthropic_api_key:
            return 'anthropic'
        else:
            raise ValueError('No LLM provider configured')
    
    def get_llm_config(self) -> dict:
        """Get LLM configuration for the primary provider."""
        if self.primary_llm_provider == 'openai':
            return {
                'provider': 'openai',
                'api_key': self.openai_api_key,
                'model': self.openai_model,
                'temperature': self.openai_temperature,
                'max_tokens': self.openai_max_tokens
            }
        elif self.primary_llm_provider == 'anthropic':
            return {
                'provider': 'anthropic',
                'api_key': self.anthropic_api_key,
                'model': self.anthropic_model,
                'max_tokens': self.openai_max_tokens  # Use same limit
            }
    
    def get_firestore_config(self) -> dict:
        """Get Firestore configuration."""
        return {
            'project': self.google_cloud_project,
            'collection': self.firestore_collection
        }
    
    def get_twilio_config(self) -> dict:
        """Get Twilio configuration."""
        return {
            'account_sid': self.twilio_account_sid,
            'auth_token': self.twilio_auth_token,
            'phone_number': self.twilio_phone_number
        }
    
    def get_agent_config(self) -> dict:
        """Get agent configuration."""
        return {
            'name': self.agent_name,
            'personality': self.agent_personality,
            'max_conversation_length': self.max_conversation_length,
            'conversation_timeout_hours': self.conversation_timeout_hours
        }
    
    def get_external_apis_config(self) -> dict:
        """Get external API configurations."""
        return {
            'openweather': {
                'api_key': self.openweather_api_key,
                'enabled': bool(self.openweather_api_key)
            },
            'serpapi': {
                'api_key': self.serpapi_key,
                'enabled': bool(self.serpapi_key)
            }
        }


# Global configuration instance
_config = None

def get_config() -> Config:
    """Get global configuration instance (singleton pattern)."""
    global _config
    if _config is None:
        _config = Config()
        _config.validate()
    return _config 