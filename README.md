# 🏠 North NJ Apartment ML Pipeline

A comprehensive machine learning pipeline for North New Jersey apartment rental price prediction featuring real-time monitoring, automated training data accumulation, and intelligent alerting. Built to help find underpriced rentals along the Morristown/Gladstone train line for NYC commuters.

## 🎯 What This Pipeline Does

- **📈 Growing Dataset**: Automatically accumulates daily prediction data (1.3k+ rows/day) to improve model training over time
- **🔄 Daily Predictions**: Pulls fresh apartment listings and predicts fair market prices with drift monitoring
- **📊 Weekly Training**: Retrains models using accumulated data with hyperparameter optimization
- **📧 Smart Alerts**: Email notifications for good deals (apartments >$100 under predicted price)
- **📈 Interactive Dashboards**: Grafana visualizations for pipeline health and business metrics
- **🚀 Flexible Deployment**: Run locally with Docker or deploy to AWS Lambda
- **⚡ Workflow Orchestration**: Prefect flows for reliable, observable pipeline execution

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Data Sources  │    │  Daily Pipeline  │    │   Training      │
│                 │───►│                  │───►│                 │
│ • Rentcast API  │    │ • 1.3k new rows │    │ • Accumulated   │
│ • NJ Listings   │    │ • Predictions    │    │   data (8k→50k) │
└─────────────────┘    │ • Accumulation   │    │ • Weekly retrain│
                       └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │   Monitoring     │    │   Storage       │
                       │                  │    │                 │
                       │ • Evidently AI  │    │ • S3 Buckets    │
                       │ • Grafana       │    │ • MLflow        │
                       │ • PostgreSQL    │    │ • Model Registry│
                       └──────────────────┘    └─────────────────┘
```

## 📁 Project Structure

```
apartment-rental-nj-2025/
├── 🚀 deployment/
│   ├── lambda/
│   │   ├── lambda_daily_run.py         # Daily predictions with accumulation
│   │   └── lambda_training.py          # Weekly training with accumulated data
│   ├── docker-compose.yml              # Full service orchestration
│   ├── deploy.sh                       # One-click deployment
│   ├── serverless.yml                  # AWS Lambda deployment
│   └── requirements.txt                # Python dependencies
├── 📁 aws/
│   ├── lambda/
│   │   ├── daily_predictions.py        # Clean AWS wrapper
│   │   └── weekly_training.py          # Clean AWS wrapper
│   └── requirements.txt                # AWS-specific minimal deps
├── 📁 src/
│   ├── data/
│   │   ├── collection.py               # Rentcast API integration
│   │   └── accumulator.py              # Training data accumulation
│   ├── models/
│   │   └── training.py                 # XGBoost training with Hyperopt
│   ├── monitoring/
│   │   └── config.py                   # CloudWatch + SNS alerting
│   └── utils/
│       └── email.py                    # Email notification system
├── 📁 workflows/
│   └── prefect_flows.py                # Prefect workflow definitions
├── 📁 config/
│   ├── database/
│   │   └── init.sql                    # Database schema + sample data
│   └── grafana/
│       ├── datasources.yml             # Grafana data connections
│       └── dashboards.yml              # Dashboard provisioning
├── 📁 data/
│   ├── training/
│   │   ├── training_base.csv           # Base 8k training data
│   │   └── training_accumulated.csv    # Growing dataset (created automatically)
│   ├── reference/
│   │   └── reference_data.csv          # Drift detection reference
│   ├── daily/                          # Daily prediction results
│   └── cache/                          # Run IDs and metadata
├── 📁 dashboards/
│   └── apartment_monitoring_dashboard.json
└── 📁 scripts/
    └── setup.sh                        # Environment setup script
```

## 🚀 Quick Start (Complete Walkthrough)

### Step 1: Prerequisites
```bash
# Install required tools
# - Docker & Docker Compose
# - Python 3.9+
# - Git
# - Optional: Pipenv for environment management

# Verify installations
docker --version
docker-compose --version
python --version
git --version
```

### Step 2: Clone and Setup
```bash
# Clone the repository
git clone https://github.com/matthew-michal/apartment_rental_nj_2025.git
cd apartment-rental-nj-2025

# Set up Python environment (choose one)
# Option A: Using Pipenv (recommended)
pip install pipenv
pipenv install -r requirements.txt
pipenv shell

# Option B: Using pip
pip install -r requirements.txt

# Make scripts executable
chmod +x deployment/deploy.sh
chmod +x scripts/setup.sh
```

### Step 3: Environment Configuration
```bash
# Create environment file
cp .env.example .env

# Edit .env with your settings (required for production):
nano .env
```

**Critical .env variables to update:**
```bash
# Database Configuration
POSTGRES_PASSWORD=your_secure_password

# AWS Configuration (for cloud deployment)
MLFLOW_BUCKET=your-unique-mlflow-bucket
TRAINING_BUCKET=your-unique-training-bucket

# Email Configuration (for deal alerts)
SENDER_EMAIL=your-email@gmail.com
RECIPIENT_EMAIL=your-email@gmail.com

# API Configuration (optional - works with sample data)
API_KEY=your_rentcast_api_key
```

### Step 4: Deploy Locally
```bash
# Run the automated deployment
cd deployment
./deploy.sh

# This will:
# ✅ Start PostgreSQL, Grafana, Prefect services
# ✅ Create database schema with sample data
# ✅ Set up monitoring infrastructure
# ✅ Provide access URLs
```

### Step 5: Verify Deployment
```bash
# Check service status
docker-compose ps

# All services should show "Up" status
# If any show "Exit 1", check logs:
docker-compose logs <service-name>

# Test key services
curl http://localhost:3000  # Grafana
curl http://localhost:4200/health  # Prefect
```

## 🌐 Service Access

After successful deployment:

| Service | URL | Credentials | Purpose |
|---------|-----|-------------|---------|
| **📈 Grafana Dashboard** | http://localhost:3000 | admin / admin | ML pipeline monitoring |
| **🗄️ Database Admin** | http://localhost:8080 | postgres / example | PostgreSQL management |
| **⚡ Prefect UI** | http://localhost:4200 | - | Workflow orchestration |
| **📊 Prometheus** | http://localhost:9090 | - | Metrics collection |

### 🎯 First Look at Your Dashboard
1. **Open Grafana**: Go to http://localhost:3000
2. **Login**: Use `admin` / `admin`
3. **Navigate**: Dashboards → Apartment ML Pipeline Monitoring
4. **Explore**: See real-time metrics with sample data

**Key Panels to Monitor:**
- **Data Drift Over Time**: Monitor model performance degradation
- **Good Deals Found**: Track business value delivered
- **Daily Data Volume**: Ensure consistent data flow
- **Training Data Growth**: Watch dataset expand over time

## 🤖 Pipeline Operations

### Understanding the Data Flow

**Daily Operations (Automated):**
1. **6:00 AM EST**: Prefect triggers daily predictions
2. **Data Collection**: ~1,300 new apartment listings pulled from Rentcast API
3. **Predictions**: ML model predicts fair market price for each listing
4. **Good Deals**: Identifies apartments >$100 under predicted price
5. **Email Alert**: Sends top deals to your email
6. **Data Accumulation**: Adds daily data to growing training dataset
7. **Monitoring**: Updates Grafana dashboard with latest metrics

**Weekly Training (Sunday 1:00 AM EST):**
1. **Data Loading**: Uses accumulated dataset (starts at 8k, grows to 50k+)
2. **Feature Engineering**: Adds train station proximity and other features
3. **Hyperparameter Tuning**: Optimizes XGBoost parameters with Hyperopt
4. **Model Training**: Trains new model with latest data
5. **Model Deployment**: Replaces old model for next week's predictions
6. **Performance Validation**: Ensures model quality hasn't degraded

### Manual Pipeline Execution

**Run Daily Predictions:**
```bash
# Using Docker (recommended)
cd deployment
docker-compose exec ml-pipeline python -c "
import sys; sys.path.append('/app')
from deployment.lambda.lambda_daily_run import lambda_handler
result = lambda_handler({'source': 'manual'}, None)
print(result)
"

# Using Prefect UI
# 1. Go to http://localhost:4200
# 2. Navigate to Deployments
# 3. Run "daily-apartment-predictions"
```

**Run Weekly Training:**
```bash
# Using Docker
cd deployment  
docker-compose exec ml-pipeline python -c "
import sys; sys.path.append('/app')
from deployment.lambda.lambda_training import lambda_handler
result = lambda_handler({'source': 'manual'}, None)  
print(result)
"

# Using Prefect UI
# Run "weekly-model-training" deployment
```

### Training Data Accumulation Feature

**How It Works:**
- **Week 1**: Model trains on base 8,000 apartment listings
- **Week 2**: Model trains on 8,000 + ~9,100 new listings = ~17,100 total
- **Week 3**: Model trains on 8,000 + ~18,200 new listings = ~26,200 total
- **Month 3**: Could have 50,000+ listings for much better predictions

**Monitor Growth:**
```bash
# Check current training data size
docker-compose exec ml-pipeline python -c "
import sys; sys.path.append('/app')
from src.data.accumulator import TrainingDataAccumulator
accumulator = TrainingDataAccumulator()
accumulator.get_training_stats()
"
```

**Reset if Needed:**
```bash
# Reset to base dataset (removes accumulated data)
docker-compose exec ml-pipeline python -c "
import sys; sys.path.append('/app')
from src.data.accumulator import TrainingDataAccumulator
accumulator = TrainingDataAccumulator()
accumulator.reset_accumulated_data()
"
```

## 📧 Email Notifications Setup

### Configure Email Alerts
1. **Update .env file:**
```bash
SENDER_EMAIL=your-gmail@gmail.com
RECIPIENT_EMAIL=your-email@gmail.com  # Can be different
```

2. **Gmail Setup (if using Gmail):**
   - Enable 2-factor authentication
   - Generate app password: Google Account → Security → App passwords
   - Use app password in AWS SSM parameter (for cloud) or update code

3. **Test Email:**
```bash
docker-compose exec ml-pipeline python -c "
import sys; sys.path.append('/app')
from src.utils.email import send_predictions_email
import pandas as pd
test_df = pd.DataFrame({'price_preds': [2500], 'price': [2400], 'price_diff': [100]})
send_predictions_email(test_df, 'your@email.com', 'sender@gmail.com', 'password')
"
```

## ☁️ AWS Cloud Deployment (Optional)

### Prerequisites
```bash
# Install AWS tools
npm install -g serverless
npm install serverless-python-requirements
pip install awscli

# Configure AWS credentials
aws configure
```

### Deploy to AWS Lambda
```bash
# Set up secure parameter storage
aws ssm put-parameter --name "/ml-pipeline/mlflow-uri" --value "your-mlflow-uri" --type "String"
aws ssm put-parameter --name "/ml-pipeline/api-key" --value "your-api-key" --type "SecureString"
aws ssm put-parameter --name "/ml-pipeline/email-password" --value "your-email-password" --type "SecureString"

# Deploy functions
cd deployment
serverless deploy --verbose

# Verify deployment
aws lambda list-functions --query 'Functions[?contains(FunctionName, `apartment-ml-pipeline`)]'
```

**AWS Resources Created:**
- **Lambda Functions**: Daily predictions (12:00 PM UTC) and weekly training (6:00 AM UTC Sunday)
- **S3 Buckets**: MLflow artifacts and training data storage
- **SNS Topic**: Alert notifications
- **CloudWatch**: Custom metrics and automated monitoring
- **IAM Roles**: Secure access permissions

## 🔧 Development & Troubleshooting

### Common Issues & Solutions

**🐳 Docker Services Won't Start:**
```bash
# Check service status
docker-compose ps

# View specific service logs
docker-compose logs grafana
docker-compose logs prefect-server
docker-compose logs db

# Restart all services
docker-compose down && docker-compose up -d

# Nuclear option (removes all data)
docker-compose down -v && docker-compose up -d
```

**🗄️ Database Connection Issues:**
```bash
# Test database connectivity
docker-compose exec db pg_isready -U postgres

# Connect to database manually
docker-compose exec db psql -U postgres -d apartment_monitoring

# Check if sample data exists
SELECT COUNT(*) FROM apartment_metrics;
```

**📈 Grafana Dashboard Not Loading:**
```bash
# Restart Grafana
docker-compose restart grafana

# Check if datasource is configured
# Go to Grafana → Configuration → Data Sources
# Should see "PostgreSQL-Apartment-Monitoring" as default

# Re-import dashboard if needed
# Dashboards → Import → Upload apartment_monitoring_dashboard.json
```

**⚡ Prefect Flows Not Running:**
```bash
# Check Prefect server health
curl http://localhost:4200/health

# Check agent status
docker-compose logs prefect-agent

# Restart Prefect services
docker-compose restart prefect-server prefect-agent
```

**📧 Email Notifications Not Working:**
```bash
# Test email configuration
python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('your-email@gmail.com', 'your-app-password')
print('✅ Email connection successful!')
server.quit()
"
```

### View Logs & Debug
```bash
# Pipeline execution logs
docker-compose logs -f ml-pipeline

# Database query debugging
docker-compose exec db psql -U postgres -d apartment_monitoring -c "
SELECT timestamp, good_deals_count, avg_predicted_price 
FROM apartment_metrics 
ORDER BY timestamp DESC 
LIMIT 5;"

# Check training data growth
ls -la data/training/
# Should see training_base.csv and training_accumulated.csv (after first run)
```

### Performance Monitoring

**Key Metrics to Watch:**
- **Data Drift Score**: Should stay < 0.3 (yellow warning), < 0.5 (red alert)
- **Daily Volume**: Consistent 1000+ listings per day
- **Model Performance**: MAE should stay ~$120-180
- **Good Deals**: 5-15 deals per day is typical
- **Training Data Growth**: Should increase ~1300 rows/day

## 📊 Understanding Your Results

### What Constitutes a "Good Deal"?
- **Price Difference**: Actual rent is >$100 less than predicted fair market price
- **Example**: Model predicts $2,800, actual listing is $2,650 = $150 good deal
- **Quality Control**: Model accuracy typically within $120-180 (MAE)

### Interpreting Dashboard Metrics

**Data Drift Over Time:**
- **Green (< 0.2)**: Model performing well, no action needed
- **Yellow (0.2-0.5)**: Monitor closely, consider retraining soon  
- **Red (> 0.5)**: Significant market changes, retrain immediately

**Good Deals Found:**
- **5-15/day**: Normal market conditions
- **20+/day**: Hot market or model needs calibration
- **0-2/day**: Expensive market period or data quality issues

**Training Data Growth:**
- **Week 1**: ~8,000 rows (base data)
- **Month 1**: ~25,000 rows (3x growth)
- **Month 3**: ~50,000+ rows (6x growth, much better predictions)

## 🎯 Customization & Extensions

### Adding New Features
```bash
# Create feature branch
git checkout -b feature/new-analysis

# Example: Add school district scoring
# 1. Update src/data/collection.py to pull school data
# 2. Update src/models/training.py to include school features  
# 3. Update monitoring for new feature drift

# Test locally before deploying
docker-compose exec ml-pipeline python test_new_feature.py
```

### Expanding Geographic Coverage
1. **Update API parameters** in `src/data/collection.py`:
```python
# Current: North NJ (Morristown area)
# Expand to: All of NJ or NYC metro
url = "https://api.rentcast.io/v1/listings/rental/long-term?state=NJ&status=Active&limit=500"
```

2. **Update train station mappings** in `src/models/training.py`
3. **Retrain model** with broader geographic data
4. **Update email templates** for new areas

### Custom Business Rules
```python
# In deployment/lambda/lambda_daily_run.py, modify good deals logic:
# Current: > $100 under predicted
good_deals = df[df['price_diff'] > 100]

# Custom: Add more criteria
good_deals = df[
    (df['price_diff'] > 100) &           # Price criteria
    (df['bedrooms'] >= 2) &             # Size criteria  
    (df['yearBuilt'] >= 2000) &         # Age criteria
    (df['station'] != 'not close')      # Transit criteria
]
```

## 🔮 What's Next?

### Immediate Improvements (Week 1)
- [ ] **Add your API key** for live data instead of sample data
- [ ] **Configure email notifications** with your Gmail credentials
- [ ] **Customize good deal criteria** for your preferences
- [ ] **Set up mobile alerts** using IFTTT or similar

### Short Term (Month 1)  
- [ ] **Expand features**: Add commute times, school ratings, crime data
- [ ] **Improve email formatting**: Rich HTML templates with images
- [ ] **Add filters**: Property type, size, price range preferences
- [ ] **Performance tuning**: Optimize for your data volume and preferences

### Long Term (3-6 months)
- [ ] **Advanced models**: Try deep learning approaches (neural networks)
- [ ] **Real-time processing**: Stream processing for immediate alerts
- [ ] **Mobile app**: React Native or Flutter app for on-the-go alerts  
- [ ] **Multi-market**: Expand to Philadelphia, NYC, or other metros
- [ ] **Predictive analytics**: Forecast market trends, not just current prices

## 📄 License & Legal

This project is designed for personal and educational use. Please ensure compliance with:
- **Rentcast API Terms**: Respect rate limits and usage guidelines
- **Email Service Policies**: Don't spam, follow CAN-SPAM Act
- **AWS Usage**: Monitor costs and stay within free tier if applicable
- **Data Privacy**: Don't share personal data from listings

## 🎉 Success Indicators

You'll know the pipeline is working when:
- ✅ **Daily emails arrive** with apartment listings sorted by deal quality
- ✅ **Grafana dashboard** shows consistent data flow and low drift scores
- ✅ **Training data grows** by ~1300 rows per day automatically
- ✅ **Model performance** stays stable (MAE ~$120-180)
- ✅ **Good deals identified** match your manual market research

## 🚀 Ready to Find Your Perfect Apartment?

Your ML pipeline is now set up to:
- 🔍 **Automatically scan** 1000+ listings daily
- 🧠 **Predict fair prices** using advanced ML algorithms
- 📧 **Alert you instantly** when great deals appear
- 📈 **Learn continuously** from market data to improve over time
- 📊 **Monitor performance** with professional dashboards

**🎯 Quick Reference Commands:**
```bash
# Start the pipeline
cd deployment && ./deploy.sh

# Check status  
docker-compose ps

# View dashboard
open http://localhost:3000

# Manual run
docker-compose exec ml-pipeline python /app/deployment/lambda/lambda_daily_run.py
```

Happy apartment hunting in North New Jersey! 🏠✨

---

**💡 Pro Tip**: The longer you run this pipeline, the better it gets. The training data accumulation means your Week 12 predictions will be significantly more accurate than Week 1!