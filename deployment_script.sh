#!/bin/bash

# Deployment script for Apartment ML Pipeline with Monitoring
set -e

echo "🏠 Deploying Apartment ML Pipeline with Evidently Monitoring..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required tools are installed
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    if ! command -v serverless &> /dev/null; then
        print_warning "Serverless Framework is not installed. Install with: npm install -g serverless"
    fi
    
    if ! command -v aws &> /dev/null; then
        print_warning "AWS CLI is not installed. Please install AWS CLI for full functionality."
    fi
    
    print_status "Prerequisites check completed."
}

# Set up directory structure
setup_directories() {
    print_status "Setting up directory structure..."
    
    mkdir -p config
    mkdir -p dashboards
    mkdir -p data
    mkdir -p logs
    
    print_status "Directory structure created."
}

# Set up environment variables
setup_environment() {
    print_status "Setting up environment variables..."
    
    if [ ! -f .env ]; then
        cat > .env << EOF
# Database Configuration
POSTGRES_DB=apartment_monitoring
POSTGRES_USER=postgres
POSTGRES_PASSWORD=example

# Grafana Configuration
GF_SECURITY_ADMIN_PASSWORD=admin

# AWS Configuration (update these with your values)
AWS_REGION=us-east-1
MLFLOW_BUCKET=mlflow-bucket
TRAINING_BUCKET=training-data

# Email Configuration
SENDER_EMAIL=sender@gmail.com
RECIPIENT_EMAIL=recipient@gmail.com
EOF
        print_status "Environment file created. Please update .env with your actual values."
    else
        print_status "Environment file already exists."
    fi
}

# Set up AWS SSM parameters
setup_ssm_parameters() {
    print_status "Setting up AWS SSM parameters..."
    
    read -p "Do you want to set up AWS SSM parameters? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Setting up SSM parameters..."
        
        # MLflow URI
        read -p "Enter your MLflow tracking URI: " mlflow_uri
        aws ssm put-parameter --name "/ml-pipeline/mlflow-uri" --value "$mlflow_uri" --type "String" --overwrite || print_warning "Failed to set MLflow URI parameter"
        
        # API Key
        read -s -p "Enter your API key: " api_key
        echo
        aws ssm put-parameter --name "/ml-pipeline/api-key" --value "$api_key" --type "SecureString" --overwrite || print_warning "Failed to set API key parameter"
        
        # Email Password
        read -s -p "Enter your email password: " email_password
        echo
        aws ssm put-parameter --name "/ml-pipeline/email-password" --value "$email_password" --type "SecureString" --overwrite || print_warning "Failed to set email password parameter"
        
        print_status "SSM parameters setup completed."
    else
        print_warning "Skipping SSM parameters setup. Make sure to set them manually later."
    fi
}

# Start local monitoring stack
start_monitoring_stack() {
    print_status "Starting local monitoring stack..."
    
    docker-compose up -d
    
    # Wait for services to be ready
    print_status "Waiting for services to be ready..."
    sleep 30
    
    # Check if services are running
    if docker-compose ps | grep -q "Up"; then
        print_status "Monitoring stack started successfully!"
        print_status "Grafana: http://localhost:3000 (admin/admin)"
        print_status "Adminer: http://localhost:8080"
        print_status "Prometheus: http://localhost:9090"
    else
        print_error "Some services failed to start. Check logs with: docker-compose logs"
    fi
}

# Deploy Lambda functions
deploy_lambda_functions() {
    print_status "Deploying Lambda functions..."
    
    read -p "Do you want to deploy Lambda functions to AWS? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v serverless &> /dev/null; then
            print_status "Deploying with Serverless Framework..."
            serverless deploy --verbose
            print_status "Lambda functions deployed successfully!"
        else
            print_error "Serverless Framework not found. Please install it first."
        fi
    else
        print_warning "Skipping Lambda deployment."
    fi
}

# Update Grafana datasource configuration
update_grafana_config() {
    print_status "Updating Grafana configuration..."
    
    # Wait for user to provide RDS endpoint if deploying to AWS
    read -p "Enter your RDS endpoint (or press Enter to use localhost): " rds_endpoint
    
    if [ ! -z "$rds_endpoint" ]; then
        sed -i.bak "s/localhost:5432/$rds_endpoint:5432/g" config/grafana_datasources.yaml
        print_status "Grafana datasource updated with RDS endpoint: $rds_endpoint"
    else
        print_status "Using localhost for database connection."
    fi
}

# Main deployment function
main() {
    echo "🏠 Apartment ML Pipeline Deployment Script"
    echo "=========================================="
    
    check_prerequisites
    setup_directories
    setup_environment
    update_grafana_config
    start_monitoring_stack
    setup_ssm_parameters
    deploy_lambda_functions
    
    echo ""
    print_status "Deployment completed!"
    echo ""
    echo "📊 Access your monitoring dashboard:"
    echo "   Grafana: http://localhost:3000 (admin/admin)"
    echo "   Adminer: http://localhost:8080"
    echo "   Prometheus: http://localhost:9090"
    echo ""
    echo "🔧 Next steps:"
    echo "   1. Update the RDS endpoint in config/grafana_datasources.yaml if using AWS RDS"
    echo "   2. Configure your API keys in AWS SSM Parameter Store"
    echo "   3. Test the pipeline with a manual trigger"
    echo "   4. Monitor the Grafana dashboard for data quality metrics"
    echo ""
    print_status "Happy monitoring! 🚀"
}

# Run main function
main "$@"