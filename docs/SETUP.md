# Complete Setup Guide for SMS AI Agent

This guide provides detailed step-by-step instructions for setting up the SMS AI Agent from scratch.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Twilio Setup](#twilio-setup)
3. [Google Cloud Platform Setup](#google-cloud-platform-setup)
4. [API Keys and External Services](#api-keys-and-external-services)
5. [Local Development Setup](#local-development-setup)
6. [Production Deployment](#production-deployment)
7. [Testing and Verification](#testing-and-verification)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

Before starting, ensure you have:

- [ ] A computer with Python 3.11 or higher
- [ ] A Google Cloud Platform account (free tier is sufficient to start)
- [ ] A Twilio account
- [ ] An OpenAI or Anthropic API account
- [ ] Basic familiarity with command line operations

## Twilio Setup

### Step 1: Create Twilio Account

1. Go to [Twilio.com](https://www.twilio.com)
2. Click "Sign up for free"
3. Complete the registration process
4. Verify your phone number when prompted

### Step 2: Get a Phone Number

1. In the Twilio Console, navigate to **Phone Numbers** > **Manage** > **Buy a number**
2. Choose your country and select "SMS" capability
3. Pick a phone number you like
4. Click "Buy" (this will cost ~$1/month)

### Step 3: Gather Twilio Credentials

1. In the Twilio Console, go to **Account** > **API keys & tokens**
2. Note down these values:
   - **Account SID** (starts with AC...)
   - **Auth Token** (click to reveal)
   - **Phone Number** (from Step 2, including the + sign)

## Google Cloud Platform Setup

### Step 1: Create GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click **Select a project** > **New Project**
3. Enter a project name (e.g., "sms-ai-agent")
4. Note the **Project ID** (you'll need this later)
5. Click **Create**

### Step 2: Enable Required APIs

```bash
# Install Google Cloud CLI if you haven't already
# https://cloud.google.com/sdk/docs/install

# Authenticate with Google Cloud
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable logging.googleapis.com
gcloud services enable run.googleapis.com
```

### Step 3: Set Up Firestore Database

```bash
# Create Firestore database in Native mode
gcloud firestore databases create --region=us-central1
```

Alternatively, through the console:
1. Go to **Firestore** in the Google Cloud Console
2. Click **Create database**
3. Choose **Native mode**
4. Select a region (us-central1 recommended)
5. Click **Create**

### Step 4: Create Service Account (Optional but Recommended)

```bash
# Create service account
gcloud iam service-accounts create sms-ai-agent \
    --display-name="SMS AI Agent Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:sms-ai-agent@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:sms-ai-agent@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"
```

## API Keys and External Services

### OpenAI Setup (Recommended)

1. Go to [OpenAI Platform](https://platform.openai.com)
2. Sign up or log in
3. Navigate to **API keys**
4. Click **Create new secret key**
5. Copy the key (starts with sk-...)
6. Set up billing if you haven't already

### Anthropic Setup (Alternative)

1. Go to [Anthropic Console](https://console.anthropic.com)
2. Sign up or log in
3. Navigate to **API Keys**
4. Create a new API key
5. Copy the key

### OpenWeatherMap Setup (Optional)

1. Go to [OpenWeatherMap](https://openweathermap.org/api)
2. Sign up for a free account
3. Go to **API keys** tab
4. Copy your default API key

### SerpAPI Setup (Optional)

1. Go to [SerpAPI](https://serpapi.com)
2. Sign up for an account
3. Get your API key from the dashboard

## Local Development Setup

### Step 1: Clone and Set Up Project

```bash
# Clone the repository (or download the code)
git clone <repository-url>
cd sms-ai-agent

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Copy the example environment file
cp env.example .env

# Edit the .env file with your values
nano .env  # or use your preferred editor
```

Fill in the `.env` file with your actual values:

```bash
# Required
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GOOGLE_CLOUD_PROJECT=your-gcp-project-id

# For local development
LOCAL_DEVELOPMENT=true
DEBUG_MODE=true
LOG_LEVEL=DEBUG
```

### Step 3: Test Local Setup

```bash
# Run the application locally
python main.py

# You should see output like:
# * Running on http://127.0.0.1:8080
```

### Step 4: Set Up Local Webhook Testing (Optional)

For testing Twilio webhooks locally:

```bash
# Install ngrok
# https://ngrok.com/download

# In a new terminal, expose your local server
ngrok http 8080

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Use this URL + /sms for Twilio webhook configuration
```

## Production Deployment

### Step 1: Prepare for Deployment

Update your `.env` file for production:

```bash
LOCAL_DEVELOPMENT=false
DEBUG_MODE=false
LOG_LEVEL=INFO
WEBHOOK_VALIDATION_ENABLED=true
```

### Step 2: Deploy to Google Cloud Functions

```bash
# Deploy the function
gcloud functions deploy sms-ai-agent \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point main \
  --memory 512MB \
  --timeout 60s \
  --env-vars-file .env \
  --region us-central1

# Get the function URL
FUNCTION_URL=$(gcloud functions describe sms-ai-agent \
  --region us-central1 \
  --format="value(httpsTrigger.url)")

echo "Function deployed at: $FUNCTION_URL"
```

### Step 3: Configure Twilio Webhook

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to **Phone Numbers** > **Manage** > **Active numbers**
3. Click on your phone number
4. In the **Messaging** section:
   - Set **Webhook URL** to: `YOUR_FUNCTION_URL/sms`
   - Set **HTTP Method** to: `POST`
5. Click **Save**

## Testing and Verification

### Step 1: Test Basic Functionality

Send an SMS to your Twilio number:

1. **Test message**: "Hello"
   - Expected response: Greeting from the AI agent

2. **Test help**: "help"
   - Expected response: Help message with available features

3. **Test calculation**: "Calculate 2 + 2"
   - Expected response: "4" or similar

### Step 2: Test Special Commands

- Send "status" - Should show agent status
- Send "reset" - Should clear conversation history
- Send "info" - Should show agent information

### Step 3: Test Tools (if configured)

- **Weather**: "What's the weather in London?"
- **Time**: "What time is it?"
- **Calculator**: "Calculate 15% of 200"

### Step 4: Monitor Logs

```bash
# View recent logs
gcloud functions logs read sms-ai-agent --limit 20

# Stream live logs
gcloud functions logs tail sms-ai-agent
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Function Deployment Fails

**Error**: Permission denied or API not enabled

**Solution**:
```bash
# Ensure all APIs are enabled
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Check your authentication
gcloud auth list
```

#### 2. Twilio Webhook Errors

**Error**: Webhook returns 500 error

**Solution**:
1. Check function logs: `gcloud functions logs read sms-ai-agent`
2. Verify environment variables in deployed function
3. Test function URL directly: `curl YOUR_FUNCTION_URL/health`

#### 3. No Response from AI

**Error**: Agent doesn't respond or gives error messages

**Solution**:
1. Check API keys are correct and have credits
2. Verify Firestore permissions
3. Test with simple messages first

#### 4. Conversation Memory Issues

**Error**: Agent doesn't remember previous messages

**Solution**:
1. Check Firestore database exists and is accessible
2. Verify Google Cloud Project ID is correct
3. Check service account permissions

### Debugging Commands

```bash
# Test function locally
curl -X POST http://localhost:8080/health

# Check function status
gcloud functions describe sms-ai-agent

# View environment variables
gcloud functions describe sms-ai-agent --format="value(environmentVariables)"

# Test Firestore connection
gcloud firestore collections list
```

### Getting Help

If you encounter issues not covered here:

1. Check the function logs for detailed error messages
2. Verify all environment variables are set correctly
3. Test each component individually
4. Check the troubleshooting section in the main README

### Cost Monitoring

Keep an eye on costs:

```bash
# Check Cloud Functions usage
gcloud functions list

# Monitor Firestore usage in the console
# Go to Firestore > Usage tab

# Check API usage for LLM providers in their respective dashboards
```

## Next Steps

After successful setup:

1. **Customize the agent**: Modify `AGENT_PERSONALITY` and other settings
2. **Add more tools**: Extend functionality in `src/tools.py`
3. **Set up monitoring**: Configure alerts for errors or high usage
4. **Scale as needed**: Adjust function memory and timeout based on usage

## Security Considerations

- Keep your API keys secure and never commit them to version control
- Regularly rotate API keys
- Monitor usage for unexpected spikes
- Set up budget alerts in Google Cloud
- Review Twilio usage regularly

---

Congratulations! Your SMS AI Agent should now be fully operational. Users can text your Twilio number and receive intelligent responses from your AI agent. 