# SMS AI Agent Architecture

This document provides a comprehensive overview of the SMS AI Agent architecture, including system design, component interactions, and data flow.

## System Overview

The SMS AI Agent is a production-ready system that enables users to interact with an AI assistant via SMS messages. The system is built using a serverless architecture on Google Cloud Platform, ensuring scalability, reliability, and cost-effectiveness.

## High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│   User's Phone  │◄──►│  Twilio SMS API │◄──►│ Google Cloud    │
│                 │    │                 │    │ Functions       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │                 │
                                              │ LangChain Agent │
                                              │                 │
                                              └─────────────────┘
                                                        │
                        ┌───────────────────────────────┼───────────────────────────────┐
                        ▼                               ▼                               ▼
              ┌─────────────────┐             ┌─────────────────┐             ┌─────────────────┐
              │                 │             │                 │             │                 │
              │ Google Firestore│             │   LLM Provider  │             │ External APIs   │
              │   (Memory)      │             │ (OpenAI/Claude) │             │ (Weather, etc.) │
              │                 │             │                 │             │                 │
              └─────────────────┘             └─────────────────┘             └─────────────────┘
```

## Component Architecture

### 1. Entry Point Layer (`main.py`)

**Responsibilities:**
- HTTP request handling for Google Cloud Functions
- Routing requests to appropriate handlers
- Centralized logging and error handling
- Health check endpoints

**Key Features:**
- Flask-based HTTP server
- Structured logging with Google Cloud integration
- Request validation and security
- Graceful error handling

### 2. SMS Handler Layer (`src/sms_handler.py`)

**Responsibilities:**
- Twilio webhook processing
- SMS message parsing and validation
- TwiML response generation
- Special command handling

**Key Features:**
- Multi-message support for long responses
- Special commands (help, reset, status)
- Message length management
- Error response handling

### 3. Security Layer (`src/security.py`)

**Responsibilities:**
- Twilio webhook signature validation
- Rate limiting per user
- Input sanitization
- Security policy enforcement

**Components:**
- `TwilioValidator`: Webhook signature verification
- `RateLimiter`: Time-based rate limiting
- `InputSanitizer`: Message content cleaning
- `SecurityManager`: Coordinated security operations

### 4. AI Agent Layer (`src/agent.py`)

**Responsibilities:**
- LangChain ReAct agent orchestration
- LLM provider integration
- Response generation and formatting
- Tool execution coordination

**Key Features:**
- Multi-provider LLM support (OpenAI, Anthropic)
- Custom prompt templates for SMS context
- Response length optimization
- Error recovery mechanisms

### 5. Memory Management Layer (`src/memory.py`)

**Responsibilities:**
- Persistent conversation storage
- Context window management
- Conversation expiration
- Multi-user isolation

**Components:**
- `FirestoreChatMessageHistory`: Custom LangChain memory backend
- `ConversationMemory`: Memory management coordination
- Automatic conversation cleanup
- Context formatting for agent prompts

### 6. Tools Layer (`src/tools.py`)

**Responsibilities:**
- External API integration
- Utility functions for the agent
- Tool result formatting
- Error handling for external services

**Available Tools:**
- `WeatherTool`: OpenWeatherMap integration
- `WebSearchTool`: Internet search capability
- `CalculatorTool`: Mathematical calculations
- `TimeTool`: Current date and time
- `HelpTool`: System information and guidance

### 7. Configuration Layer (`src/config.py`)

**Responsibilities:**
- Environment variable management
- Configuration validation
- Provider-specific settings
- Development/production mode handling

**Features:**
- Pydantic-based validation
- Hierarchical configuration
- Environment-specific overrides
- API key management

## Data Flow

### 1. Incoming SMS Message Flow

```
1. User sends SMS → Twilio
2. Twilio webhook → Google Cloud Function
3. Security validation (signature, rate limiting)
4. SMS data extraction and sanitization
5. Route to SMS handler
6. Check for special commands
7. If regular message → AI Agent processing
8. Agent retrieves conversation memory
9. Agent invokes LLM with context and tools
10. Response formatting for SMS
11. TwiML response generation
12. Response sent back through Twilio
13. Memory updated with conversation
```

### 2. Agent Processing Flow

```
1. Receive user message and phone number
2. Load conversation memory from Firestore
3. Add user message to memory
4. Format conversation context for agent
5. Prepare agent input with tools and memory
6. Execute ReAct agent with LLM
7. Agent may use tools for information gathering
8. Generate response based on agent output
9. Format response for SMS constraints
10. Add AI response to memory
11. Return formatted response
```

### 3. Memory Management Flow

```
1. User identified by phone number
2. Check for existing conversation in Firestore
3. If exists, load and validate (not expired)
4. If expired or not exists, create new conversation
5. Apply conversation window limits
6. Store messages with timestamps
7. Automatic cleanup of old conversations
```

## Scalability Design

### Horizontal Scaling

- **Stateless Functions**: Each request is independent
- **Auto-scaling**: Google Cloud Functions scales from 0 to 100 instances
- **Connection Pooling**: Efficient Firestore connections
- **Caching**: Memory instances cached per function instance

### Performance Optimizations

- **Cold Start Mitigation**: Lightweight initialization
- **Memory Management**: Conversation windowing
- **Response Optimization**: SMS-specific formatting
- **Error Recovery**: Graceful degradation

### Resource Management

- **Memory Allocation**: 512MB per function instance
- **Timeout Handling**: 60-second maximum execution time
- **Concurrent Requests**: Up to 1000 per instance
- **Rate Limiting**: Per-user limits to prevent abuse

## Security Architecture

### Authentication & Authorization

- **Webhook Security**: Twilio signature validation
- **API Key Management**: Secure environment variable handling
- **Service Accounts**: Google Cloud IAM roles
- **Input Validation**: Comprehensive sanitization

### Rate Limiting

```
Per-User Limits:
- 5 messages per minute
- 50 messages per hour
- Sliding window implementation
- Graceful limit enforcement
```

### Data Protection

- **Conversation Privacy**: 24-hour expiration by default
- **Secure Storage**: Firestore with IAM controls
- **Logging**: Structured logs without sensitive data
- **Error Handling**: No data leakage in errors

## Monitoring & Observability

### Logging Strategy

```
Structured Logging Levels:
- DEBUG: Detailed execution flow
- INFO: Normal operations
- WARNING: Recoverable issues
- ERROR: Error conditions
- CRITICAL: System failures
```

### Metrics Collection

- **Response Times**: Function execution duration
- **Error Rates**: Success/failure ratios
- **Memory Usage**: Resource utilization
- **Conversation Stats**: User engagement metrics

### Health Monitoring

- **Health Endpoints**: `/health` for monitoring
- **Function Status**: Deployment verification
- **External API Status**: Provider availability
- **Database Connectivity**: Firestore health

## Deployment Architecture

### Environment Management

```
Development → Testing → Production
     │            │           │
     ▼            ▼           ▼
Local Function → Staging → Production Function
     │            │           │
     ▼            ▼           ▼
Local Firestore → Test DB → Production DB
```

### CI/CD Integration

- **Automated Deployment**: Script-based deployment
- **Environment Validation**: Configuration checks
- **Health Verification**: Post-deployment testing
- **Rollback Capability**: Version management

## Error Handling Strategy

### Error Classification

1. **User Errors**: Invalid input, rate limits
2. **System Errors**: Function failures, timeouts
3. **External Errors**: API failures, network issues
4. **Configuration Errors**: Missing keys, invalid settings

### Recovery Mechanisms

- **Graceful Degradation**: Fallback responses
- **Retry Logic**: Transient error handling
- **Circuit Breakers**: External API protection
- **User Communication**: Clear error messages

## Extension Points

### Adding New Tools

1. Create tool class inheriting from `BaseTool`
2. Implement `_run` method with tool logic
3. Add to `ToolManager._initialize_tools()`
4. Update documentation and tests

### Adding New LLM Providers

1. Add provider configuration to `Config`
2. Extend `_initialize_llm()` in `SMSAgent`
3. Update validation logic
4. Add provider-specific error handling

### Custom Memory Backends

1. Implement `BaseChatMessageHistory` interface
2. Create provider-specific implementation
3. Update `ConversationMemory` initialization
4. Add configuration options

## Performance Considerations

### Latency Optimization

- **Function Warm-up**: Keep instances warm
- **Database Queries**: Efficient Firestore operations
- **LLM Calls**: Optimized token usage
- **Response Caching**: Tool result caching

### Cost Optimization

- **Function Pricing**: Pay-per-use model
- **Memory Allocation**: Right-sized resources
- **LLM Usage**: Token count optimization
- **Storage Costs**: Conversation cleanup

### Monitoring Guidelines

- **Response Time Targets**: < 3 seconds for typical requests
- **Error Rate Thresholds**: < 1% error rate
- **Memory Utilization**: < 80% average usage
- **Cost Alerts**: Budget-based notifications

---

This architecture provides a robust, scalable, and maintainable foundation for the SMS AI Agent while ensuring security, performance, and cost-effectiveness in production environments. 