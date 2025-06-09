"""
Security Module for SMS AI Agent

This module handles security features including Twilio webhook validation,
rate limiting, and input sanitization.
"""

import hashlib
import hmac
import base64
from typing import Dict, Any
from urllib.parse import urlencode
import time
from collections import defaultdict, deque

import structlog
from flask import Request

from .exceptions import TwilioValidationError, RateLimitError


logger = structlog.get_logger(__name__)


class TwilioValidator:
    """Validates Twilio webhook requests for security."""
    
    def __init__(self, auth_token: str):
        """Initialize with Twilio auth token."""
        self.auth_token = auth_token.encode('utf-8')
    
    def validate_request(self, request: Request) -> bool:
        """
        Validate that the request came from Twilio.
        
        Args:
            request: Flask request object
            
        Returns:
            True if request is valid, False otherwise
        """
        try:
            # Get the expected signature from headers
            signature = request.headers.get('X-Twilio-Signature', '')
            if not signature:
                logger.warning("Missing X-Twilio-Signature header")
                return False
            
            # Build the expected signature
            url = request.url
            if request.method == 'POST':
                # Get form data and sort parameters
                params = request.form.to_dict()
                if params:
                    sorted_params = sorted(params.items())
                    param_string = urlencode(sorted_params)
                    data_to_sign = url + param_string
                else:
                    data_to_sign = url
            else:
                data_to_sign = url
            
            # Compute expected signature
            expected_signature = self._compute_signature(data_to_sign)
            
            # Compare signatures
            is_valid = hmac.compare_digest(signature, expected_signature)
            
            if not is_valid:
                logger.warning(
                    "Twilio signature validation failed",
                    expected_signature=expected_signature,
                    received_signature=signature,
                    url=url
                )
            
            return is_valid
            
        except Exception as e:
            logger.error("Error validating Twilio signature", error=str(e))
            return False
    
    def _compute_signature(self, data: str) -> str:
        """Compute the expected signature for the given data."""
        mac = hmac.new(self.auth_token, data.encode('utf-8'), hashlib.sha1)
        return base64.b64encode(mac.digest()).decode('utf-8')


class RateLimiter:
    """Rate limiter to prevent abuse of the SMS service."""
    
    def __init__(self, 
                 per_minute_limit: int = 5, 
                 per_hour_limit: int = 50):
        """
        Initialize rate limiter.
        
        Args:
            per_minute_limit: Maximum requests per minute per user
            per_hour_limit: Maximum requests per hour per user
        """
        self.per_minute_limit = per_minute_limit
        self.per_hour_limit = per_hour_limit
        
        # Store request timestamps for each user
        self.minute_requests = defaultdict(deque)
        self.hour_requests = defaultdict(deque)
    
    def check_rate_limit(self, user_id: str) -> bool:
        """
        Check if user has exceeded rate limits.
        
        Args:
            user_id: Unique identifier for the user (phone number)
            
        Returns:
            True if within limits, False if exceeded
            
        Raises:
            RateLimitError: If rate limit is exceeded
        """
        current_time = time.time()
        
        # Clean old entries and check minute limit
        minute_queue = self.minute_requests[user_id]
        self._clean_old_requests(minute_queue, current_time, 60)
        
        if len(minute_queue) >= self.per_minute_limit:
            logger.warning(
                "Rate limit exceeded (per minute)",
                user_id=user_id,
                current_count=len(minute_queue),
                limit=self.per_minute_limit
            )
            raise RateLimitError(
                f"Rate limit exceeded: {self.per_minute_limit} messages per minute"
            )
        
        # Clean old entries and check hour limit
        hour_queue = self.hour_requests[user_id]
        self._clean_old_requests(hour_queue, current_time, 3600)
        
        if len(hour_queue) >= self.per_hour_limit:
            logger.warning(
                "Rate limit exceeded (per hour)",
                user_id=user_id,
                current_count=len(hour_queue),
                limit=self.per_hour_limit
            )
            raise RateLimitError(
                f"Rate limit exceeded: {self.per_hour_limit} messages per hour"
            )
        
        # Add current request timestamp
        minute_queue.append(current_time)
        hour_queue.append(current_time)
        
        return True
    
    def _clean_old_requests(self, queue: deque, current_time: float, window_seconds: int):
        """Remove timestamps older than the window."""
        cutoff_time = current_time - window_seconds
        while queue and queue[0] < cutoff_time:
            queue.popleft()


class InputSanitizer:
    """Sanitizes user input to prevent injection attacks."""
    
    @staticmethod
    def sanitize_message(message: str) -> str:
        """
        Sanitize incoming SMS message content.
        
        Args:
            message: Raw message content
            
        Returns:
            Sanitized message content
        """
        if not message:
            return ""
        
        # Basic sanitization
        sanitized = message.strip()
        
        # Remove null bytes and control characters
        sanitized = ''.join(char for char in sanitized 
                          if ord(char) >= 32 or char in '\n\r\t')
        
        # Limit length to prevent memory issues
        max_length = 2000  # Generous limit for SMS
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
            logger.warning(
                "Message truncated during sanitization",
                original_length=len(message),
                truncated_length=len(sanitized)
            )
        
        return sanitized
    
    @staticmethod
    def sanitize_phone_number(phone_number: str) -> str:
        """
        Sanitize phone number for storage and logging.
        
        Args:
            phone_number: Raw phone number
            
        Returns:
            Sanitized phone number
        """
        if not phone_number:
            return ""
        
        # Keep only digits, +, -, and spaces
        sanitized = ''.join(char for char in phone_number 
                          if char.isdigit() or char in '+-() ')
        
        return sanitized.strip()


class SecurityManager:
    """Main security manager that coordinates all security features."""
    
    def __init__(self, config):
        """Initialize security manager with configuration."""
        self.config = config
        self.twilio_validator = TwilioValidator(config.twilio_auth_token)
        self.rate_limiter = RateLimiter(
            per_minute_limit=config.rate_limit_per_user_per_minute,
            per_hour_limit=config.rate_limit_per_user_per_hour
        )
        self.input_sanitizer = InputSanitizer()
    
    def validate_and_sanitize_request(self, request: Request) -> Dict[str, Any]:
        """
        Perform comprehensive validation and sanitization of incoming request.
        
        Args:
            request: Flask request object
            
        Returns:
            Dictionary with sanitized request data
            
        Raises:
            TwilioValidationError: If webhook validation fails
            RateLimitError: If rate limits are exceeded
        """
        # Validate Twilio webhook if enabled
        if self.config.webhook_validation_enabled:
            if not self.twilio_validator.validate_request(request):
                raise TwilioValidationError("Invalid Twilio webhook signature")
        
        # Extract and sanitize form data
        form_data = request.form.to_dict()
        
        sanitized_data = {
            'message_sid': form_data.get('MessageSid', ''),
            'account_sid': form_data.get('AccountSid', ''),
            'from_number': self.input_sanitizer.sanitize_phone_number(
                form_data.get('From', '')
            ),
            'to_number': self.input_sanitizer.sanitize_phone_number(
                form_data.get('To', '')
            ),
            'body': self.input_sanitizer.sanitize_message(
                form_data.get('Body', '')
            ),
            'num_media': int(form_data.get('NumMedia', 0)),
            'from_city': form_data.get('FromCity', ''),
            'from_state': form_data.get('FromState', ''),
            'from_country': form_data.get('FromCountry', ''),
            'timestamp': form_data.get('DateSent', '')
        }
        
        # Check rate limits
        if sanitized_data['from_number']:
            self.rate_limiter.check_rate_limit(sanitized_data['from_number'])
        
        return sanitized_data 