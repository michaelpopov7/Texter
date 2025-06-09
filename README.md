# SMS AI Agent

A production-ready SMS AI agent that allows users to text a dedicated phone number and receive intelligent responses powered by LangChain and deployed on Google Cloud Functions.

## 🚀 Features

- **SMS Interface**: Users text a phone number to interact with the AI
- **Conversation Memory**: Maintains context across SMS sessions using Firestore
- **LangChain Integration**: Powered by LangChain with ReAct agent framework
- **Multiple LLM Providers**: Supports OpenAI and Anthropic
- **Built-in Tools**: Weather, web search, calculator, time, and help tools
- **Security**: Twilio webhook validation and rate limiting
- **Scalable**: Auto-scaling Google Cloud Functions deployment
- **Production Ready**: Comprehensive error handling, logging, and monitoring

## 📋 Prerequisites

- Python 3.11+
- Google Cloud Platform account
- Twilio account with phone number
- OpenAI or Anthropic API key
- (Optional) OpenWeatherMap API key for weather features

## 🛠️ Quick Setup

### 1. Clone and Install Dependencies

```bash
git clone <repository-url>
cd sms-ai-agent
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy the example environment file
cp env.example .env

# Edit .env with your actual values
nano .env
```

Required environment variables:
- `TWILIO_ACCOUNT_SID`: Your Twilio Account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token  
- `TWILIO_PHONE_NUMBER`: Your Twilio phone number (with +)
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`: LLM provider API key
- `GOOGLE_CLOUD_PROJECT`: Your GCP project ID

### 3. Set Up Google Cloud Platform

```bash
# Install Google Cloud CLI
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable logging.googleapis.com

# Initialize Firestore (choose Native mode)
gcloud firestore databases create --region=us-central1
```

### 4. Deploy to Google Cloud Functions

```bash
# Deploy the function
gcloud functions deploy sms-ai-agent \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point main \
  --memory 512MB \
  --timeout 60s \
  --env-vars-file .env

# Get the trigger URL
gcloud functions describe sms-ai-agent --format="value(httpsTrigger.url)"
```

### 5. Configure Twilio Webhook

1. Go to [Twilio Console](https://console.twilio.com/)
2. Navigate to Phone Numbers > Manage > Active numbers
3. Click on your phone number
4. Set the webhook URL to: `https://YOUR_FUNCTION_URL/sms`
5. Set HTTP method to POST
6. Save configuration

## 🏗️ Architecture

```
User SMS → Twilio → Google Cloud Function → LangChain Agent → Response
                                      ↓
                                 Firestore (Memory)
                                      ↓
                              External APIs (Weather, Search)
```

### Components

- **main.py**: Google Cloud Function entry point
- **src/agent.py**: LangChain ReAct agent implementation
- **src/memory.py**: Firestore-backed conversation memory
- **src/tools.py**: Available tools for the agent
- **src/sms_handler.py**: Twilio SMS processing
- **src/security.py**: Security and validation
- **src/config.py**: Configuration management

## 💬 Usage Examples

Once deployed, users can text your Twilio number:

```
User: "Hello!"
Agent: "Hi! I'm your AI assistant. I can help with weather, calculations, current time, and general questions. What can I do for you?"

User: "What's the weather in New York?"
Agent: "Weather in New York: Clear Sky
Temperature: 72°F (feels like 75°F)
Humidity: 45%"

User: "Calculate 15% of 250"
Agent: "15% of 250 = 37.5"

User: "What time is it?"
Agent: "Current time: Tuesday, January 23, 2024 at 02:30 PM"
```

### Special Commands

- `help` - Show available features
- `reset` - Clear conversation history
- `status` - Check agent status
- `info` - Agent information

## 🔧 Configuration

### Environment Variables

See `env.example` for all available configuration options.

Key settings:
- **Agent Personality**: Customize the agent's behavior
- **Rate Limiting**: Control usage per user
- **SMS Length**: Manage message truncation
- **Tool Configuration**: Enable/disable specific tools

### LLM Providers

#### OpenAI
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=150
```

#### Anthropic
```bash
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-3-haiku-20240307
```

## 🧪 Local Development

```bash
# Set LOCAL_DEVELOPMENT=true in .env
LOCAL_DEVELOPMENT=true

# Run locally
python main.py

# Test with ngrok
ngrok http 8080
# Use ngrok URL for Twilio webhook testing
```

## 🔒 Security Features

- **Webhook Validation**: Verifies requests come from Twilio
- **Rate Limiting**: Prevents abuse (5 messages/minute, 50/hour per user)
- **Input Sanitization**: Cleans user input
- **Error Handling**: Graceful failure modes

## 📊 Monitoring

### Logs
```bash
# View function logs
gcloud functions logs read sms-ai-agent --limit 50

# Real-time logs
gcloud functions logs tail sms-ai-agent
```

### Metrics
- Response times
- Error rates
- Memory usage
- Conversation statistics

## 🛠️ Development

### Adding New Tools

1. Create tool class in `src/tools.py`:

```python
class MyCustomTool(BaseTool):
    name = "my_tool"
    description = "Description of what the tool does"
    
    def _run(self, query: str) -> str:
        # Tool implementation
        return "Tool response"
```

2. Add to ToolManager in `_initialize_tools()`:

```python
tools.append(MyCustomTool())
```

### Testing

```bash
# Run tests
pytest tests/

# Test specific component
pytest tests/test_agent.py -v
```

## 📚 API Documentation

### Health Check
```
GET /health
Response: {"status": "healthy", "service": "sms-ai-agent"}
```

### SMS Webhook
```
POST /sms
Content-Type: application/x-www-form-urlencoded
Body: Twilio webhook data
Response: TwiML XML
```

## 🚨 Troubleshooting

### Common Issues

1. **Function timeout**: Increase timeout in deploy.yaml
2. **Memory issues**: Increase memory allocation
3. **Firestore permissions**: Check service account permissions
4. **Twilio webhook errors**: Verify URL and signature validation

### Debug Mode
```bash
DEBUG_MODE=true
LOG_LEVEL=DEBUG
```

## 💰 Cost Optimization

- **Function scaling**: Adjust min/max instances
- **Memory allocation**: Start with 512MB, adjust as needed
- **LLM usage**: Monitor token consumption
- **Firestore**: Regular cleanup of old conversations

## 📈 Scaling Considerations

- **Auto-scaling**: Configured for 0-100 instances
- **Rate limiting**: Adjust based on usage patterns
- **Memory management**: Conversation windowing
- **Database optimization**: Firestore indexing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs
3. Open an issue with detailed information

---

Built with ❤️ using LangChain, Google Cloud Functions, and Twilio 