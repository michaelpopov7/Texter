"""
SMS AI Agent - Google Cloud Function Entry Point

This module serves as the main entry point for the Google Cloud Function
that handles Twilio SMS webhooks and orchestrates AI agent responses.
"""

import logging
import os
from typing import Any, Dict

from flask import Flask, Request, Response, request
from google.cloud import logging as cloud_logging
import structlog

from src.config import Config
from src.sms_handler import SMSHandler
from src.agent import SMSAgent
from src.memory import ConversationMemory
from src.security import TwilioValidator
from src.exceptions import SMSAgentError, TwilioValidationError


# Initialize structured logging
def setup_logging():
    """Configure structured logging for production."""
    if os.getenv('GOOGLE_CLOUD_PROJECT'):
        # Production: Use Google Cloud Logging
        client = cloud_logging.Client()
        client.setup_logging()
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


setup_logging()
logger = structlog.get_logger(__name__)

# Initialize components
config = Config()
twilio_validator = TwilioValidator(config.twilio_auth_token)
conversation_memory = ConversationMemory(config)
sms_agent = SMSAgent(config, conversation_memory)
sms_handler = SMSHandler(config, sms_agent)

app = Flask(__name__)


@app.route('/sms', methods=['POST'])
def handle_sms_webhook(request: Request = None) -> Response:
    """
    Handle incoming SMS messages from Twilio webhook.
    
    This is the main entry point for all SMS interactions.
    """
    if request is None:
        request = request
    
    request_id = request.headers.get('X-Request-ID', 'unknown')
    
    logger.info(
        "Received SMS webhook",
        request_id=request_id,
        method=request.method,
        content_type=request.content_type
    )
    
    try:
        # Validate request is from Twilio
        if not twilio_validator.validate_request(request):
            logger.warning(
                "Invalid Twilio webhook signature",
                request_id=request_id,
                url=request.url,
                user_agent=request.headers.get('User-Agent')
            )
            raise TwilioValidationError("Invalid webhook signature")
        
        # Extract SMS data
        sms_data = _extract_sms_data(request)
        
        logger.info(
            "Processing SMS message",
            request_id=request_id,
            from_number=sms_data.get('from_number'),
            message_length=len(sms_data.get('body', ''))
        )
        
        # Process message through SMS handler
        response_xml = sms_handler.process_message(sms_data, request_id)
        
        logger.info(
            "SMS processed successfully",
            request_id=request_id,
            response_length=len(response_xml)
        )
        
        return Response(
            response_xml,
            mimetype='application/xml',
            status=200
        )
        
    except TwilioValidationError as e:
        logger.error(
            "Twilio validation failed",
            request_id=request_id,
            error=str(e)
        )
        return Response("Forbidden", status=403)
        
    except SMSAgentError as e:
        logger.error(
            "SMS agent error",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__
        )
        
        # Send error response to user
        error_response = sms_handler.create_error_response(
            "I'm having trouble processing your message right now. Please try again later."
        )
        return Response(error_response, mimetype='application/xml', status=200)
        
    except Exception as e:
        logger.exception(
            "Unexpected error processing SMS",
            request_id=request_id,
            error=str(e)
        )
        
        # Send generic error response to user
        error_response = sms_handler.create_error_response(
            "Sorry, I'm experiencing technical difficulties. Please try again later."
        )
        return Response(error_response, mimetype='application/xml', status=200)


def _extract_sms_data(request: Request) -> Dict[str, Any]:
    """Extract SMS data from Twilio webhook request."""
    form_data = request.form.to_dict()
    
    return {
        'message_sid': form_data.get('MessageSid'),
        'account_sid': form_data.get('AccountSid'),
        'from_number': form_data.get('From'),
        'to_number': form_data.get('To'),
        'body': form_data.get('Body', '').strip(),
        'num_media': int(form_data.get('NumMedia', 0)),
        'from_city': form_data.get('FromCity'),
        'from_state': form_data.get('FromState'),
        'from_country': form_data.get('FromCountry'),
        'timestamp': form_data.get('DateSent')
    }


@app.route('/health', methods=['GET'])
def health_check() -> Response:
    """Health check endpoint for monitoring."""
    try:
        # Quick health checks
        config.validate()
        
        return Response(
            '{"status": "healthy", "service": "sms-ai-agent"}',
            mimetype='application/json',
            status=200
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return Response(
            '{"status": "unhealthy", "error": "Configuration invalid"}',
            mimetype='application/json',
            status=503
        )


@app.route('/', methods=['GET'])
def root() -> Response:
    """Root endpoint with service information."""
    return Response(
        '{"service": "SMS AI Agent", "version": "1.0.0", "status": "running"}',
        mimetype='application/json',
        status=200
    )


# Google Cloud Functions entry point
def main(request: Request) -> Response:
    """
    Main entry point for Google Cloud Functions.
    
    Args:
        request: HTTP request object from Google Cloud Functions
        
    Returns:
        Response object with appropriate HTTP status and content
    """
    with app.test_request_context(
        path=request.path,
        method=request.method,
        headers=request.headers,
        data=request.get_data(),
        query_string=request.query_string
    ):
        try:
            if request.path == '/sms' and request.method == 'POST':
                return handle_sms_webhook(request)
            elif request.path == '/health' and request.method == 'GET':
                return health_check()
            elif request.path == '/' and request.method == 'GET':
                return root()
            else:
                return Response("Not Found", status=404)
                
        except Exception as e:
            logger.exception("Unhandled error in main entry point", error=str(e))
            return Response("Internal Server Error", status=500)


if __name__ == '__main__':
    # Local development server
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080))) 