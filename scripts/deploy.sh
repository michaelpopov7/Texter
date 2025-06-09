#!/bin/bash

# SMS AI Agent Deployment Script
# This script automates the deployment of the SMS AI Agent to Google Cloud Functions

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
FUNCTION_NAME="sms-ai-agent"
RUNTIME="python311"
REGION="us-central1"
MEMORY="512MB"
TIMEOUT="60s"
MAX_INSTANCES="100"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command_exists gcloud; then
        print_error "Google Cloud CLI (gcloud) is not installed."
        print_error "Please install it from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    if ! command_exists python3; then
        print_error "Python 3 is not installed."
        exit 1
    fi
    
    if [ ! -f ".env" ]; then
        print_error ".env file not found. Please create it from env.example"
        exit 1
    fi
    
    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt not found."
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Validate environment variables
validate_env() {
    print_status "Validating environment variables..."
    
    required_vars=(
        "TWILIO_ACCOUNT_SID"
        "TWILIO_AUTH_TOKEN"
        "TWILIO_PHONE_NUMBER"
        "GOOGLE_CLOUD_PROJECT"
    )
    
    missing_vars=()
    
    # Source .env file to check variables
    set -a
    source .env
    set +a
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    # Check for at least one LLM provider
    if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
        missing_vars+=("OPENAI_API_KEY or ANTHROPIC_API_KEY")
    fi
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        print_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        exit 1
    fi
    
    print_success "Environment variables validated"
}

# Check Google Cloud authentication and project
check_gcloud() {
    print_status "Checking Google Cloud authentication..."
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null; then
        print_error "Not authenticated with Google Cloud. Please run: gcloud auth login"
        exit 1
    fi
    
    current_project=$(gcloud config get-value project 2>/dev/null)
    if [ "$current_project" != "$GOOGLE_CLOUD_PROJECT" ]; then
        print_warning "Current project ($current_project) doesn't match GOOGLE_CLOUD_PROJECT ($GOOGLE_CLOUD_PROJECT)"
        print_status "Setting project to $GOOGLE_CLOUD_PROJECT"
        gcloud config set project "$GOOGLE_CLOUD_PROJECT"
    fi
    
    print_success "Google Cloud authentication verified"
}

# Enable required APIs
enable_apis() {
    print_status "Enabling required Google Cloud APIs..."
    
    apis=(
        "cloudfunctions.googleapis.com"
        "cloudbuild.googleapis.com"
        "firestore.googleapis.com"
        "logging.googleapis.com"
    )
    
    for api in "${apis[@]}"; do
        print_status "Enabling $api..."
        gcloud services enable "$api" --quiet
    done
    
    print_success "APIs enabled"
}

# Check if Firestore is initialized
check_firestore() {
    print_status "Checking Firestore database..."
    
    if ! gcloud firestore databases list --format="value(name)" 2>/dev/null | grep -q "(default)"; then
        print_warning "Firestore database not found. Creating..."
        print_status "Creating Firestore database in Native mode..."
        gcloud firestore databases create --region="$REGION" --quiet
        print_success "Firestore database created"
    else
        print_success "Firestore database exists"
    fi
}

# Deploy the function
deploy_function() {
    print_status "Deploying Cloud Function..."
    
    # Update .env for production
    temp_env=$(mktemp)
    cp .env "$temp_env"
    
    # Set production-specific variables
    sed -i.bak 's/LOCAL_DEVELOPMENT=true/LOCAL_DEVELOPMENT=false/' .env
    sed -i.bak 's/DEBUG_MODE=true/DEBUG_MODE=false/' .env
    
    # Deploy the function
    gcloud functions deploy "$FUNCTION_NAME" \
        --runtime="$RUNTIME" \
        --trigger-http \
        --allow-unauthenticated \
        --entry-point=main \
        --memory="$MEMORY" \
        --timeout="$TIMEOUT" \
        --max-instances="$MAX_INSTANCES" \
        --env-vars-file=.env \
        --region="$REGION" \
        --quiet
    
    # Restore original .env
    mv "$temp_env" .env
    
    if [ $? -eq 0 ]; then
        print_success "Function deployed successfully"
    else
        print_error "Function deployment failed"
        exit 1
    fi
}

# Get function URL
get_function_url() {
    print_status "Getting function URL..."
    
    FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" \
        --region="$REGION" \
        --format="value(httpsTrigger.url)")
    
    if [ -n "$FUNCTION_URL" ]; then
        print_success "Function URL: $FUNCTION_URL"
        print_status "Webhook URL for Twilio: ${FUNCTION_URL}/sms"
        
        # Save URL to file for reference
        echo "$FUNCTION_URL" > .function_url
        print_status "Function URL saved to .function_url"
    else
        print_error "Could not retrieve function URL"
        exit 1
    fi
}

# Test the deployed function
test_function() {
    print_status "Testing deployed function..."
    
    health_url="${FUNCTION_URL}/health"
    response=$(curl -s -o /dev/null -w "%{http_code}" "$health_url")
    
    if [ "$response" = "200" ]; then
        print_success "Function health check passed"
    else
        print_warning "Function health check returned HTTP $response"
        print_warning "Check the function logs: gcloud functions logs read $FUNCTION_NAME --region=$REGION"
    fi
}

# Display post-deployment instructions
show_instructions() {
    echo ""
    echo "=========================================="
    print_success "Deployment completed successfully!"
    echo "=========================================="
    echo ""
    echo "📱 Next steps:"
    echo ""
    echo "1. Configure Twilio webhook:"
    echo "   - Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/active"
    echo "   - Click on your phone number"
    echo "   - Set webhook URL to: ${FUNCTION_URL}/sms"
    echo "   - Set HTTP method to: POST"
    echo "   - Save configuration"
    echo ""
    echo "2. Test your SMS agent:"
    echo "   - Send a text message to: $TWILIO_PHONE_NUMBER"
    echo "   - Try sending: 'hello', 'help', or 'status'"
    echo ""
    echo "3. Monitor your function:"
    echo "   - View logs: gcloud functions logs tail $FUNCTION_NAME --region=$REGION"
    echo "   - View metrics: https://console.cloud.google.com/functions/details/$REGION/$FUNCTION_NAME"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   - Check logs if messages aren't working"
    echo "   - Verify Twilio webhook configuration"
    echo "   - Ensure API keys have sufficient credits"
    echo ""
}

# Main deployment process
main() {
    echo "=========================================="
    echo "   SMS AI Agent Deployment Script"
    echo "=========================================="
    echo ""
    
    check_prerequisites
    validate_env
    check_gcloud
    enable_apis
    check_firestore
    deploy_function
    get_function_url
    test_function
    show_instructions
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --function-name)
            FUNCTION_NAME="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --memory)
            MEMORY="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --function-name NAME    Set function name (default: sms-ai-agent)"
            echo "  --region REGION        Set deployment region (default: us-central1)"
            echo "  --memory MEMORY        Set memory allocation (default: 512MB)"
            echo "  --help                 Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main deployment
main 