# NJ Apartment Rental Price Prediction Pipeline

> **Automated MLOps pipeline for discovering underpriced rental apartments in North New Jersey using XGBoost, MLflow, and AWS**

[![Infrastructure](https://img.shields.io/badge/Infrastructure-Terraform-7B42BC?logo=terraform)](./infrastructure)
[![ML Framework](https://img.shields.io/badge/ML-XGBoost-FF6600?logo=xgboost)](./src/models)
[![Tracking](https://img.shields.io/badge/MLflow-Tracking-0194E2?logo=mlflow)](./infrastructure/modules/mlflow_server)
[![AWS](https://img.shields.io/badge/AWS-Lambda%20%7C%20ECS%20%7C%20S3-FF9900?logo=amazonaws)](./infrastructure)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?logo=githubactions)](./github/workflows)

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Infrastructure](#infrastructure)
- [CI/CD Pipeline](#cicd-pipeline)
- [Local Development](#local-development)
- [Deployment](#deployment)
- [Daily Operations](#daily-operations)
- [Monitoring & Alerts](#monitoring--alerts)
- [Configuration](#configuration)
- [Manual Operations](#manual-operations)
- [Cost & Scaling](#cost--scaling)
- [Troubleshooting](#troubleshooting)
- [Future Roadmap](#future-roadmap)

---

## 🎯 Overview

This project automates the discovery of underpriced rental apartments in North New Jersey (focusing on areas along the NJ Transit Morristown/Morris & Essex Lines for easy NYC commuting). The system:

- **Collects** rental listings daily from Rentcast API
- **Predicts** fair market prices using an XGBoost regression model
- **Identifies** properties priced below predicted value (potential deals)
- **Alerts** via email with ranked opportunities and detailed CSV reports
- **Retrains** the model weekly with accumulated prediction data
- **Monitors** performance, data quality, and drift via CloudWatch

### Business Value

- **For Investors**: Identify undervalued rental properties before the market corrects
- **For Renters**: Find apartments priced below market value for better deals
- **Current Performance**: Model RMSE of ~$611 on rental prices averaging $2,000-$6,000/month

### Sample Output

```
Found 4 great apartment deals today!

📊 Summary:
- Total listings checked: 10
- Good deals found: 4
- Average savings: $314/month
- Total potential savings: $1,256/month

🏆 Top Deal:
  Apartment - $3,200/month
  Predicted Fair Price: $2,704
  Your Savings: $496/month
  Location: Morristown, NJ
  2 bed, 1 bath
```

---

## 🏗️ Architecture

### System Diagram

![Architecture Diagram](docs/architecture-diagram.png)

### Component Breakdown

#### **Data Sources**
- **Rentcast API**: Real-time rental listings for North NJ
- **S3 Training Data**: Historical labeled data + accumulated daily predictions

#### **ML Infrastructure (24/7)**
- **MLflow Server**: ECS Fargate service with ALB for experiment tracking and model registry
- **RDS PostgreSQL**: MLflow backend store + monitoring metrics
- **S3 MLflow Bucket**: Model artifacts and experiment metadata

#### **Training Pipeline (Weekly - Sundays)**
- **EventBridge Scheduler**: Triggers training at midnight Sunday
- **ECS Fargate Task**: Runs hyperparameter tuning and model training
- **MLflow Integration**: Logs experiments, metrics, and registers best model
- **Training Data Accumulator**: Grows dataset with validated predictions

#### **Prediction Pipeline (Daily - 11 AM)**
- **EventBridge Scheduler**: Triggers daily predictions
- **Lambda Function**: Collects listings, loads latest model, generates predictions
- **Email Notifications**: SES sends ranked deals with CSV attachment
- **S3 Storage**: Saves predictions and accumulates training data

#### **Monitoring & Alerts**
- **CloudWatch Logs**: Centralized logging for all components
- **CloudWatch Metrics**: Custom metrics for model performance and data quality
- **SNS Topics**: Email/SMS alerts for failures and drift detection
- **Grafana**: Optional dashboards for local monitoring

#### **CI/CD Pipeline**
- **GitHub Actions**: Automated build, test, and deploy on push to `develop`/`main`
- **Amazon ECR**: Docker image registry for Lambda and ECS
- **Terraform**: Infrastructure as Code for consistent deployments

---

## ✨ Key Features

### MLOps Capabilities
- ✅ **Automated Model Training**: Weekly retraining with hyperparameter optimization
- ✅ **Experiment Tracking**: MLflow tracks all experiments with metrics and artifacts
- ✅ **Model Registry**: Versioned models with staging/production promotion
- ✅ **Data Drift Detection**: Monitors feature distributions and prediction quality
- ✅ **Performance Monitoring**: Tracks RMSE, prediction counts, and data quality
- ✅ **Incremental Learning**: Accumulates validated predictions for continuous improvement

### DevOps Capabilities
- ✅ **Infrastructure as Code**: Complete Terraform modules for reproducible deployments
- ✅ **CI/CD Automation**: GitHub Actions for build, test, and deploy
- ✅ **Environment Separation**: Isolated staging/production environments
- ✅ **Secrets Management**: AWS Secrets Manager for API keys and credentials
- ✅ **High Availability**: ECS Fargate with health checks and auto-restart
- ✅ **Cost Optimization**: Lambda for lightweight tasks, ECS for compute-intensive jobs

### Production Features
- ✅ **Serverless Predictions**: Lambda scales automatically with demand
- ✅ **Email Notifications**: Automated deal alerts with CSV attachments
- ✅ **Error Handling**: Comprehensive logging and SNS alerts for failures
- ✅ **Data Accumulation**: Self-improving model with growing training dataset
- ✅ **Manual Triggers**: On-demand training and prediction testing

---

## 📦 Prerequisites

### Required Tools
- **AWS Account** with appropriate IAM permissions
- **Terraform** >= 1.6.0
- **Docker** and Docker Compose
- **Python** 3.9+
- **AWS CLI** configured with credentials
- **Git** for version control

### Required AWS Services
- Lambda (daily predictions)
- ECS Fargate (MLflow server + training)
- ECR (Docker image registry)
- S3 (data storage)
- RDS PostgreSQL (MLflow backend)
- EventBridge (scheduling)
- SES (email notifications)
- Secrets Manager (API keys)
- CloudWatch (logging/metrics)
- SNS (alerts)

### API Keys
- **Rentcast API Key**: Sign up at [rentcast.io](https://www.rentcast.io)
  - Store in AWS Secrets Manager as `apartment-pipeline-api-keys-{environment}`
  - JSON format: `{"RENTCAST_API_KEY": "your-key-here"}`

---

## 🚀 Quick Start

### Option 1: Deploy to AWS (Recommended)

```bash
# 1. Clone repository
git clone <your-repo-url>
cd apartment-rental-ml-pipeline

# 2. Configure AWS credentials
aws configure

# 3. Create Rentcast API secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name apartment-pipeline-api-keys-staging \
  --secret-string '{"RENTCAST_API_KEY":"your-key-here"}' \
  --region us-east-1

# 4. Update email configuration in deployment/lambda_daily_run.py
# Edit SENDER_EMAIL and RECIPIENT_EMAIL variables

# 5. Configure GitHub secrets (for CI/CD)
# In GitHub repo settings > Secrets and variables > Actions, add:
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY

# 6. Push to trigger deployment
git checkout -b develop
git push origin develop

# GitHub Actions will:
# - Build Docker image
# - Push to ECR
# - Deploy infrastructure via Terraform
# - Update Lambda and ECS tasks
```

### Option 2: Local Development

```bash
# 1. Install dependencies
./scripts/setup.sh

# Or manually:
pip install -r requirements.txt

# 2. Set environment variables
export AWS_PROFILE=default
export AWS_REGION=us-east-1
export API_KEY=your-rentcast-api-key

# 3. Start local infrastructure (optional)
docker-compose up -d

# This starts:
# - PostgreSQL (monitoring + Prefect metadata)
# - Grafana (dashboards on port 3000)
# - Adminer (DB admin on port 8080)
# - Prefect Server (orchestration UI on port 4200)

# 4. Test locally
python deployment/invoke_lambda.py    # Test daily predictions
python deployment/test_real_model.py  # Test with specific parameters
```

---

## 🏗️ Infrastructure

### Terraform Modules

The infrastructure is organized into reusable Terraform modules:

```
infrastructure/
├── environments/
│   └── staging/
│       ├── main.tf           # Orchestrates all modules
│       ├── variables.tf      # Environment-specific variables
│       └── outputs.tf        # Resource outputs
└── modules/
    ├── s3/                   # S3 buckets (MLflow, training, predictions)
    ├── lambda/               # Lambda function (daily predictions)
    ├── ecs_training/         # ECS Fargate training tasks
    ├── mlflow_server/        # ECS MLflow tracking server
    └── rds_postgres/         # PostgreSQL database
```

### Key Resources Created

| Resource | Purpose | Configuration |
|----------|---------|---------------|
| **S3 Buckets** | Data storage | `apartment-pipeline-{mlflow/training/predictions}-{env}-{account}` |
| **Lambda Function** | Daily predictions | 10GB memory, 15min timeout, EventBridge trigger |
| **ECS Cluster** | Container orchestration | Fargate launch type |
| **MLflow Service** | Experiment tracking | Always-on ECS service with ALB |
| **Training Task** | Weekly model training | On-demand Fargate task |
| **RDS Instance** | PostgreSQL database | db.t3.micro, 20GB storage |
| **ECR Repository** | Docker images | `apartment-pipeline-{env}` |
| **EventBridge Rules** | Scheduling | Daily 11 AM, Weekly Sunday midnight |
| **SNS Topic** | Alerts | Email subscriptions for failures |
| **Secrets Manager** | API keys | `apartment-pipeline-api-keys-{env}` |

### Module Usage Example

```hcl
# infrastructure/environments/staging/main.tf

module "mlflow_server" {
  source = "../../modules/mlflow_server"
  
  environment    = var.environment
  vpc_id         = module.networking.vpc_id
  subnet_ids     = module.networking.private_subnet_ids
  database_url   = module.rds.connection_url
  mlflow_bucket  = module.s3.mlflow_bucket_name
}

module "lambda" {
  source = "../../modules/lambda"
  
  environment          = var.environment
  image_uri            = var.image_uri
  mlflow_tracking_uri  = module.mlflow_server.tracking_uri
  mlflow_bucket        = module.s3.mlflow_bucket_name
  training_bucket      = module.s3.training_bucket_name
  predictions_bucket   = module.s3.predictions_bucket_name
}
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow

**File**: `.github/workflows/deploy-staging.yml`

**Trigger**:
- Push to `develop` or `main` branches
- Changes to: `src/`, `deployment/`, `infrastructure/`, `requirements.txt`
- Manual workflow dispatch

**Jobs**:

1. **Build & Push Docker Image**
   - Checkout code
   - Configure AWS credentials
   - Login to ECR
   - Build multi-platform Docker image (linux/amd64)
   - Push with tags: `latest`, `staging-{sha}`, `staging-{run-number}`
   - Cache layers for faster builds

2. **Deploy Infrastructure**
   - Wait for ECR image propagation (30s)
   - Initialize Terraform with S3 backend
   - Run `terraform plan` with new image URI
   - Apply changes automatically
   - Output Lambda and ECS task names

3. **Integration Tests** (Disabled - TODO)
   - Planned: API tests, model validation, data quality checks

4. **Smoke Tests** (Disabled - TODO)
   - Planned: Live endpoint checks, prediction verification

5. **Deployment Summary**
   - Generate GitHub Actions summary with job statuses
   - Report deployment success/failure

### Deployment Flow

```
Code Push → GitHub Actions → Build Docker → Push to ECR
                ↓
           Terraform Plan → Terraform Apply → Update Lambda/ECS
                ↓
           Tests (TODO) → Deploy Summary → Slack/Email (TODO)
```

### Manual Deployment

```bash
# From infrastructure/environments/staging/

# 1. Initialize Terraform
terraform init

# 2. Plan changes
terraform plan \
  -var="image_uri=123456789.dkr.ecr.us-east-1.amazonaws.com/apartment-pipeline-staging:latest" \
  -var="environment=staging"

# 3. Apply changes
terraform apply -auto-approve

# 4. Verify deployment
terraform output
```

---

## 💻 Local Development

### Project Structure

```
apartment-rental-ml-pipeline/
├── src/
│   ├── config/
│   │   └── environment.py      # Environment configuration manager
│   ├── data/
│   │   ├── collection.py       # Rentcast API data collector
│   │   └── accumulator.py      # Training data accumulator
│   ├── models/
│   │   └── training.py         # Model training with MLflow
│   ├── monitoring/
│   │   └── config.py           # CloudWatch/SNS monitoring
│   └── utils/
│       └── email.py            # Email utilities (legacy)
├── deployment/
│   ├── Dockerfile              # Multi-stage Docker build
│   ├── lambda_daily_run.py     # Daily prediction Lambda handler
│   ├── lambda_training.py      # Training Lambda handler (legacy)
│   ├── invoke_lambda.py        # Local Lambda testing
│   ├── invoke_training.py      # Manual ECS training trigger
│   └── test_real_model.py      # Model validation script
├── infrastructure/
│   ├── environments/
│   │   └── staging/            # Staging Terraform config
│   └── modules/                # Reusable Terraform modules
├── deployment/
│   ├── docker-compose.yml      # Local development stack
│   └── requirements.txt        # Python dependencies
├── scripts/
│   └── setup.sh                # Environment setup script
└── .github/
    └── workflows/
        └── deploy-staging.yml  # CI/CD pipeline
```

### Running Components Locally

#### 1. Local MLflow Server (Optional)

```bash
# Using docker-compose
docker-compose up grafana db adminer prefect-server

# Or manually
mlflow server \
  --backend-store-uri sqlite:///mlflow.db \
  --default-artifact-root ./mlruns \
  --host 0.0.0.0 \
  --port 5000
```

#### 2. Test Data Collection

```python
from src.data.collection import ApartmentDataCollector

collector = ApartmentDataCollector(api_key="your-key")
df = collector.collect_listings(max_pages=2)
print(f"Collected {len(df)} listings")
```

#### 3. Test Model Training

```bash
# Locally (uses local MLflow)
export MLFLOW_TRACKING_URI=http://localhost:5000
python src/models/training.py

# Against AWS MLflow server
export MLFLOW_TRACKING_URI=http://staging-mlflow-alb-*.us-east-1.elb.amazonaws.com
export ENVIRONMENT=staging
python src/models/training.py
```

#### 4. Test Daily Predictions

```bash
# Test Lambda locally with dry run
python deployment/invoke_lambda.py

# Test with real model
python deployment/test_real_model.py
```

### Development Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Make changes and test locally**
   ```bash
   python deployment/invoke_lambda.py  # Test predictions
   python src/models/training.py       # Test training
   ```

3. **Push to trigger CI/CD**
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin feature/your-feature
   ```

4. **Merge to develop** (triggers staging deployment)
   ```bash
   git checkout develop
   git merge feature/your-feature
   git push origin develop
   ```

---

## 🚀 Deployment

### Initial Setup (One-time)

#### 1. Configure AWS

```bash
# Configure AWS CLI
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-east-1)

# Verify identity
aws sts get-caller-identity
```

#### 2. Create Secrets

```bash
# Create Rentcast API key secret
aws secretsmanager create-secret \
  --name apartment-pipeline-api-keys-staging \
  --description "API keys for apartment rental pipeline" \
  --secret-string '{"RENTCAST_API_KEY":"your-actual-key"}' \
  --region us-east-1

# Verify secret
aws secretsmanager get-secret-value \
  --secret-id apartment-pipeline-api-keys-staging \
  --region us-east-1 \
  --query SecretString \
  --output text
```

#### 3. Configure Email Notifications

Edit `deployment/lambda_daily_run.py`:

```python
# Update these variables
SENDER_EMAIL = "your-verified-sender@example.com"
RECIPIENT_EMAIL = "your-recipient@example.com"
```

**Important**: Both emails must be verified in AWS SES (Simple Email Service)

```bash
# Verify email addresses in SES
aws ses verify-email-identity --email-address your-email@example.com --region us-east-1
```

#### 4. Set Up GitHub Secrets

In your GitHub repository:
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Add repository secrets:
   - `AWS_ACCESS_KEY_ID`: Your AWS access key
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key

#### 5. Deploy Infrastructure

```bash
# Method 1: Via GitHub Actions (Recommended)
git checkout develop
git push origin develop
# GitHub Actions will automatically deploy

# Method 2: Manual Terraform deployment
cd infrastructure/environments/staging
terraform init
terraform plan -var="image_uri=<ecr-image-uri>" -var="environment=staging"
terraform apply -auto-approve
```

### Updating the System

#### Update Application Code

```bash
# 1. Make changes to Python code in src/ or deployment/
# 2. Commit and push
git add .
git commit -m "Update prediction logic"
git push origin develop

# GitHub Actions will:
# - Build new Docker image
# - Push to ECR
# - Update Lambda function
# - Update ECS task definitions
```

#### Update Infrastructure

```bash
# 1. Make changes to Terraform files
# 2. Commit and push
git add infrastructure/
git commit -m "Add new S3 bucket for reports"
git push origin develop

# GitHub Actions will run terraform apply automatically
```

#### Rollback Deployment

```bash
# Option 1: Revert Git commit
git revert HEAD
git push origin develop

# Option 2: Deploy specific image tag
cd infrastructure/environments/staging
terraform apply -var="image_uri=123456.dkr.ecr.us-east-1.amazonaws.com/apartment-pipeline-staging:staging-abc123"
```

---

## 📅 Daily Operations

### Automated Schedules

#### Daily Predictions (11:00 AM EST)
1. **EventBridge** triggers Lambda function
2. **Lambda** collects listings from Rentcast API
3. **Lambda** loads latest model from MLflow
4. **Lambda** generates predictions and finds deals
5. **Lambda** sends email with top deals + CSV attachment
6. **Lambda** accumulates predictions to training data
7. **CloudWatch** logs execution and metrics

#### Weekly Training (Sunday 12:00 AM EST)
1. **EventBridge** triggers ECS Fargate task
2. **ECS Task** loads accumulated training data from S3
3. **ECS Task** runs hyperparameter tuning (50 trials)
4. **ECS Task** trains final model with best parameters
5. **MLflow** logs experiments, metrics, and model
6. **ECS Task** registers model in MLflow registry
7. **S3** stores model run_id for daily predictions
8. **CloudWatch** monitors training progress

### What Gets Emailed Daily

**Subject**: "Apartment Deals - {date}"

**Content**:
- Summary statistics (total checked, deals found, avg savings)
- Top 10 best deals with:
  - Property type and price
  - Predicted fair price
  - Your monthly savings
  - Location, bedrooms, bathrooms
  - Property details (year built, lot size)
  - Link to listing (if available)

**Attachment**: `apartment_deals_{date}.csv`
- All deals sorted by savings
- Full property details
- Prediction confidence metrics

### Monitoring Daily Operations

#### CloudWatch Logs

```bash
# View daily prediction logs
aws logs tail /aws/lambda/apartment-pipeline-daily-predictions-staging --follow

# View training logs
aws logs tail /ecs/staging-training --follow
```

#### CloudWatch Metrics

Custom metrics tracked:
- `pipeline_success/failure` - Execution status
- `daily_predictions_count` - Number of predictions made
- `good_deals_found` - Properties below predicted price
- `avg_predicted_price` - Average model prediction
- `training_rmse` - Model performance
- `data_quality_missing_pct` - Data completeness
- `num_drifted_columns` - Feature drift detection

#### View Metrics Dashboard

```bash
# In AWS Console:
CloudWatch → Dashboards → Create custom dashboard
Namespace: MLPipeline/ApartmentRent

# Or use Grafana (local)
http://localhost:3000
Username: admin
Password: admin
```

---

## 📊 Monitoring & Alerts

### CloudWatch Monitoring

#### Custom Metrics

All metrics are published to namespace `MLPipeline/ApartmentRent`:

**Pipeline Execution**:
- `pipeline_start` - Pipeline initiated
- `pipeline_success` - Successful completion
- `pipeline_failure` - Execution failure

**Data Quality**:
- `data_quality_missing_pct` - Percentage of missing values
- `data_quality_row_count` - Dataset size
- `data_quality_duplicates` - Duplicate records
- `avg_price` - Average rental price

**Model Performance**:
- `model_rmse` - Root Mean Square Error
- `training_samples` - Training dataset size
- `test_samples` - Test dataset size

**Drift Detection**:
- `prediction_drift_score` - Distribution shift in predictions
- `num_drifted_columns` - Features with detected drift
- `missing_values_share` - Data completeness changes

### SNS Alerts

Alerts are sent via SNS topic for:

**Pipeline Failures**:
- Lambda execution errors
- ECS task failures
- API connection issues

**Data Quality Issues**:
- Missing values > 20%
- Low data volume (< 50 listings)
- High duplicate rate

**Model Performance Degradation**:
- RMSE > $500 threshold
- Prediction drift score > 0.5

**Drift Detection**:
- Significant feature distribution changes
- High prediction drift

### Alert Configuration

```bash
# Subscribe email to SNS topic
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789:apartment-pipeline-alerts-staging \
  --protocol email \
  --notification-endpoint your-email@example.com

# Confirm subscription via email link
```

### Grafana Dashboards (Local Development)

Access: `http://localhost:3000`

**Available Dashboards**:
1. **Pipeline Health**: Success/failure rates, execution times
2. **Data Quality**: Missing values, duplicates, volume trends
3. **Model Performance**: RMSE over time, prediction distributions
4. **Business Metrics**: Deals found, average savings, property types

---

## ⚙️ Configuration

### Environment Variables

The system uses AWS environment variables (set by Terraform):

**Lambda Function**:
```bash
ENVIRONMENT=staging
AWS_REGION=us-east-1
MLFLOW_BUCKET=apartment-pipeline-mlflow-staging-{account}
TRAINING_BUCKET=apartment-pipeline-training-staging-{account}
PREDICTIONS_BUCKET=apartment-pipeline-predictions-staging-{account}
MLFLOW_TRACKING_URI=http://staging-mlflow-alb-*.elb.amazonaws.com
SECRET_NAME=apartment-pipeline-api-keys-staging
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:{account}:apartment-pipeline-alerts-staging
LOG_LEVEL=INFO
```

**ECS Training Task**:
```bash
ENVIRONMENT=staging
AWS_REGION=us-east-1
MLFLOW_BUCKET=apartment-pipeline-mlflow-staging-{account}
MLFLOW_TRACKING_URI=http://staging-mlflow-alb-*.elb.amazonaws.com
MLFLOW_EXPERIMENT_NAME=apartment-rental-price-prediction
```

### Secrets Management

**AWS Secrets Manager**:
- Secret Name: `apartment-pipeline-api-keys-{environment}`
- Format: JSON
- Required Keys:
  - `RENTCAST_API_KEY`: Your Rentcast API key

**Accessing Secrets in Code**:

```python
from src.config.environment import get_secret

# Automatically retrieves from Secrets Manager
api_key = get_secret('RENTCAST_API_KEY')
```

### Email Configuration

**SES Setup**:
1. Verify sender email in AWS SES
2. Verify recipient email (required in SES sandbox)
3. Update `deployment/lambda_daily_run.py`:

```python
SENDER_EMAIL = "notifications@yourdomain.com"
RECIPIENT_EMAIL = "your-email@example.com"
```

**Production**: Request SES production access to send to any email

### Search Parameters

**Default Search** (hardcoded in `src/data/collection.py`):
- **Location**: Morristown, NJ (40.831, -74.402)
- **Radius**: 12 miles
- **Transit Lines**: NJ Transit Morris & Essex Lines
- **Stations**: 26 stations from Hoboken to Hackettstown
- **Limit**: 500 listings per page, up to 15 pages (7,500 total)

**To Change Location**:
1. Update `collection.py` `DEFAULT_URL` with new coordinates
2. Update `training.py` `nj_transit_locations` dictionary with new stations
3. Retrain model with new region data

---

## 🛠️ Manual Operations

### Trigger Training Manually

```bash
# Option 1: Using invoke_training.py script
python deployment/invoke_training.py

# Option 2: Via AWS CLI
aws ecs run-task \
  --cluster staging-mlflow-cluster \
  --task-definition staging-training \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"

# Option 3: Via AWS Console
# ECS → Clusters → staging-mlflow-cluster → Tasks → Run new task
```

### Test Daily Predictions

```bash
# Dry run (mock model, no email)
python deployment/invoke_lambda.py

# Real model with limited listings
python deployment/test_real_model.py
# Configured for: 5 listings, $50 min savings

# Custom parameters via AWS CLI
aws lambda invoke \
  --function-name apartment-pipeline-daily-predictions-staging \
  --payload '{"dry_run": false, "limit": 20, "min_savings": 100}' \
  response.json
```

### View MLflow Experiments

```bash
# Get MLflow UI URL
terraform output -raw mlflow_tracking_uri

# Access via browser
http://staging-mlflow-alb-*.us-east-1.elb.amazonaws.com

# View specific experiment
http://staging-mlflow-alb-*.us-east-1.elb.amazonaws.com/#/experiments/0
```

### Check Training Data Growth

```python
from src.data.accumulator import TrainingDataAccumulator

accumulator = TrainingDataAccumulator()
stats = accumulator.get_training_stats()

print(f"Base dataset: {stats['base_size']:,} rows")
print(f"Accumulated: {stats['accumulated_size']:,} rows")
print(f"Growth: +{stats['growth']:,} ({stats['growth_percentage']:.1f}%)")
```

### Reset Accumulated Training Data

```python
from src.data.accumulator import TrainingDataAccumulator

accumulator = TrainingDataAccumulator()
rows = accumulator.reset_accumulated_data()
print(f"Reset to base dataset: {rows:,} rows")
```

### View Recent Predictions

```bash
# List recent prediction files in S3
aws s3 ls s3://apartment-pipeline-predictions-staging-{account}/daily/ --recursive

# Download specific prediction
aws s3 cp s3://apartment-pipeline-predictions-staging-{account}/daily/predictions_20240104.csv ./

# View in terminal
cat predictions_20240104.csv | column -t -s,
```

### Debug Lambda Function

```bash
# Tail logs in real-time
aws logs tail /aws/lambda/apartment-pipeline-daily-predictions-staging --follow

# Get last 100 lines
aws logs tail /aws/lambda/apartment-pipeline-daily-predictions-staging --since 1h

# Search for errors
aws logs filter-pattern /aws/lambda/apartment-pipeline-daily-predictions-staging --filter-pattern ERROR
```

### Debug ECS Training Task

```bash
# List recent tasks
aws ecs list-tasks --cluster staging-mlflow-cluster

# Describe task
aws ecs describe-tasks --cluster staging-mlflow-cluster --tasks <task-arn>

# View logs
aws logs tail /ecs/staging-training --follow
```

---

## 💰 Cost & Scaling

### Estimated Monthly Costs (Staging)

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| **ECS Fargate** | MLflow server (24/7) + Weekly training | ~$25 |
| **RDS PostgreSQL** | db.t3.micro (20GB storage) | ~$15 |
| **Lambda** | Daily executions (10GB memory, 5min avg) | ~$2 |
| **S3** | ~10GB data storage + requests | ~$1 |
| **ECR** | Docker image storage (~2GB) | ~$0.50 |
| **CloudWatch** | Logs + custom metrics | ~$3 |
| **Data Transfer** | Minimal cross-AZ | ~$1 |
| **SES** | Email notifications (daily) | Free tier |
| **EventBridge** | Scheduling rules | Free |
| **Secrets Manager** | 1 secret | ~$0.40 |
| **SNS** | Alerts (low volume) | Free tier |
| **Total** | | **~$50-70/month** |

### Cost Optimization Tips

1. **Stop MLflow Server when not needed**
   ```bash
   # Scale down MLflow service
   aws ecs update-service \
     --cluster staging-mlflow-cluster \
     --service staging-mlflow-service \
     --desired-count 0
   ```

2. **Use Lambda for training** (if feasible)
   - Current: ECS Fargate (~$5 per training run)
   - Alternative: Lambda (limited to 15min, 10GB memory)

3. **Reduce RDS instance size**
   - Current: db.t3.micro
   - Consider: db.t3.micro with storage autoscaling

4. **Optimize Docker images**
   - Current: ~2GB
   - Use multi-stage builds (already implemented)
   - Remove unnecessary dependencies

5. **S3 Lifecycle policies**
   ```bash
   # Archive old predictions to Glacier after 90 days
   aws s3api put-bucket-lifecycle-configuration \
     --bucket apartment-pipeline-predictions-staging-{account} \
     --lifecycle-configuration file://lifecycle.json
   ```

### Scaling Considerations

**Current Limits**:
- Daily predictions: ~500-7,500 listings (configurable)
- Training data: ~50,000 rows (growing)
- Prediction latency: ~3-5 minutes
- Training time: ~15-20 minutes

**Scale to Production**:
1. **Increase Lambda resources**
   - Memory: 10GB → 15GB (for larger datasets)
   - Timeout: 900s → 900s (already at max)

2. **Parallel processing**
   - Use Lambda Step Functions for batch processing
   - Split large datasets across multiple invocations

3. **Dedicated RDS instance**
   - db.t3.micro → db.t3.medium
   - Enable read replicas for queries

4. **Multi-region deployment**
   - Replicate infrastructure across regions
   - Use Route 53 for DNS routing

5. **Caching layer**
   - ElastiCache for frequent model loads
   - Reduce S3 GET requests

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Lambda Timeout (Daily Predictions)

**Symptom**: Lambda exceeds 15-minute timeout

**Causes**:
- Too many listings to process
- MLflow model load slow from S3
- API rate limiting

**Solutions**:
```bash
# Reduce listing limit
python deployment/invoke_lambda.py
# Edit payload: {'limit': 100}  # Instead of 500

# Check MLflow bucket accessibility
aws s3 ls s3://apartment-pipeline-mlflow-staging-{account}/models/

# Verify Lambda has internet access (NAT Gateway)
# Check VPC configuration in Terraform
```

#### 2. Training Task Fails

**Symptom**: ECS task stops with non-zero exit code

**Causes**:
- Insufficient memory
- MLflow server unreachable
- S3 permissions missing

**Solutions**:
```bash
# Check task logs
aws logs tail /ecs/staging-training --follow

# Verify MLflow server is running
curl http://staging-mlflow-alb-*.us-east-1.elb.amazonaws.com/health

# Test network connectivity
aws ecs run-task \
  --cluster staging-mlflow-cluster \
  --task-definition staging-training-debug \
  --overrides '{"containerOverrides":[{"name":"training","command":["curl","http://staging-mlflow-alb-*.elb.amazonaws.com"]}]}'
```

#### 3. No Email Received

**Symptom**: Predictions complete but no email sent

**Causes**:
- SES not configured in us-east-1
- Email addresses not verified
- SES in sandbox mode

**Solutions**:
```bash
# Verify SES email addresses
aws ses list-verified-email-addresses --region us-east-1

# Send test email
aws ses send-email \
  --from sender@example.com \
  --to recipient@example.com \
  --subject "Test" \
  --text "Test" \
  --region us-east-1

# Check Lambda CloudWatch logs for SES errors
aws logs filter-pattern /aws/lambda/apartment-pipeline-daily-predictions-staging --filter-pattern "SES"
```

#### 4. High RMSE / Poor Predictions

**Symptom**: Model RMSE > $1,000 or nonsensical predictions

**Causes**:
- Insufficient training data
- Data drift (market changes)
- Feature engineering issues

**Solutions**:
```python
# Check training data quality
from src.data.accumulator import TrainingDataAccumulator
accumulator = TrainingDataAccumulator()
stats = accumulator.get_training_stats()
print(stats)

# Retrain with more data
python deployment/invoke_training.py

# Review MLflow experiments
# Look for: feature importance, outliers, data distribution
```

#### 5. Terraform Apply Fails

**Symptom**: `terraform apply` errors during deployment

**Common Errors**:

```bash
# Error: Image not found in ECR
# Solution: Build and push image first
docker build -t apartment-pipeline .
docker tag apartment-pipeline:latest {account}.dkr.ecr.us-east-1.amazonaws.com/apartment-pipeline-staging:latest
docker push {account}.dkr.ecr.us-east-1.amazonaws.com/apartment-pipeline-staging:latest

# Error: Insufficient IAM permissions
# Solution: Add required policies to Terraform execution role
aws iam attach-role-policy \
  --role-name TerraformExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/PowerUserAccess

# Error: State lock error
# Solution: Force unlock (careful!)
terraform force-unlock <lock-id>
```

#### 6. Data Collection Fails

**Symptom**: 0 listings returned from API

**Causes**:
- Invalid API key
- API rate limit exceeded
- Rentcast API downtime
- Invalid search parameters

**Solutions**:
```python
# Test API key manually
from src.data.collection import ApartmentDataCollector
collector = ApartmentDataCollector(api_key="your-key")
df = collector.collect_listings(max_pages=1)
print(f"Collected {len(df)} listings")

# Check API status
curl -H "X-Api-Key: your-key" \
  "https://api.rentcast.io/v1/listings/rental/long-term?latitude=40.83&longitude=-74.40&radius=5&limit=10"

# Verify secret in Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id apartment-pipeline-api-keys-staging \
  --query SecretString \
  --output text
```

### Debug Checklist

When issues occur, check these in order:

1. ✅ **CloudWatch Logs**: Check for error messages
   ```bash
   aws logs tail /aws/lambda/apartment-pipeline-daily-predictions-staging
   ```

2. ✅ **IAM Permissions**: Verify Lambda/ECS roles have required policies

3. ✅ **Network Configuration**: Ensure NAT Gateway for internet access

4. ✅ **Secrets Manager**: Verify API keys are accessible

5. ✅ **S3 Buckets**: Check data exists and is readable

6. ✅ **MLflow Server**: Verify server is healthy
   ```bash
   curl http://staging-mlflow-alb-*.elb.amazonaws.com/health
   ```

7. ✅ **EventBridge Rules**: Check schedules are enabled

8. ✅ **SES Configuration**: Verify emails in correct region

9. ✅ **Resource Limits**: Check Lambda timeout, memory, ECS task limits

10. ✅ **Recent Changes**: Review recent Git commits or Terraform changes

### Getting Help

**CloudWatch Insights Query** (Find errors in last 24h):

```sql
fields @timestamp, @message
| filter @message like /ERROR/ or @message like /Exception/
| sort @timestamp desc
| limit 100
```

**View All Resource Tags**:

```bash
# Find all resources for this project
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=apartment-pipeline \
  --region us-east-1
```

---

## 🚀 Future Roadmap

### Planned Features

#### Short-term (Next 2-3 Months)

- [ ] **Multi-environment Support**
  - Copy staging to `production` and `dev` environments
  - Environment-specific Terraform workspaces
  - Separate GitHub Actions workflows

- [ ] **Integration Tests**
  - API response validation
  - Model prediction quality tests
  - Data schema validation
  - S3 data integrity checks

- [ ] **Smoke Tests**
  - Endpoint health checks post-deployment
  - Prediction accuracy verification
  - Email delivery confirmation

- [ ] **Enhanced Monitoring**
  - Custom Grafana dashboards in AWS
  - Slack integration for alerts
  - Weekly summary reports
  - Cost tracking dashboards

- [ ] **Improved Email Notifications**
  - HTML-formatted emails with images
  - Interactive property cards
  - Map visualization of deals
  - Historical price trends

#### Medium-term (3-6 Months)

- [ ] **Model Improvements**
  - Add property amenities (parking, pets, utilities)
  - Include crime rate and school ratings
  - Seasonal price adjustments
  - Ensemble models (XGBoost + LightGBM)

- [ ] **Automated Retraining Triggers**
  - Retrain on significant drift detection
  - Adaptive training frequency based on data volume
  - A/B testing of model versions

- [ ] **Web Dashboard**
  - Real-time deal browsing
  - Historical price charts
  - Map-based property search
  - Email subscription management

- [ ] **Data Enrichment**
  - Zillow/Trulia data cross-reference
  - Property tax information
  - Neighborhood demographics
  - Transit schedule integration

- [ ] **Geographic Expansion**
  - Configurable search regions
  - Multi-city support (NYC, Boston, Philadelphia)
  - Custom transit line selection

#### Long-term (6-12 Months)

- [ ] **Mobile App**
  - Push notifications for new deals
  - Saved searches and favorites
  - Property comparison tool

- [ ] **Advanced Analytics**
  - Price trend forecasting
  - Occupancy rate estimation
  - Investment ROI calculator
  - Comparable property analysis

- [ ] **Community Features**
  - User reviews and ratings
  - Deal sharing and comments
  - Landlord reputation tracking

- [ ] **API Monetization**
  - Public API for predictions
  - Webhook integrations
  - Premium features for real estate agents

### Known Limitations

1. **Geographic Scope**: Hardcoded for North NJ transit lines
   - Requires code changes to expand regions

2. **Email Delivery**: SES sandbox limits
   - Need production access for unrestricted sending

3. **Data Freshness**: Daily updates only
   - Missing intraday price changes

4. **Model Features**: Limited to basic property attributes
   - No amenities, school ratings, or crime data

5. **Training Frequency**: Weekly only
   - Could benefit from more frequent updates in volatile markets

6. **Testing Coverage**: Minimal automated tests
   - Need comprehensive test suite

7. **Disaster Recovery**: No backup/restore automation
   - Manual recovery process for infrastructure

### Contributing

This is a personal project, but suggestions and improvements are welcome! To contribute:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request with detailed description

---

## 📝 License

This project is for educational and personal use. Rentcast API usage subject to their terms of service.

---

## 📧 Contact

For questions or suggestions, please open an issue in the GitHub repository.

---

## 🙏 Acknowledgments

- **Rentcast API** for rental listing data
- **MLflow** for experiment tracking
- **AWS** for cloud infrastructure
- **Terraform** for IaC capabilities
- **XGBoost** for the predictive model

---

**Last Updated**: January 2025  
**Version**: 2.0 (MLOps + DevOps)  
**Status**: Production-ready (Staging environment)
