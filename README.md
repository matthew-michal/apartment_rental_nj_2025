# 🏠 Apartment ML Pipeline with Monitoring & Orchestration

A comprehensive machine learning pipeline for North New Jersey apartment rental price prediction featuring real-time monitoring, automated orchestration, and intelligent alerting.

## 🎯 What This Pipeline Does

- **🔄 Daily Predictions**: Automatically pulls fresh apartment listings and predicts fair market prices
- **📊 Weekly Training**: Retrains models with hyperparameter optimization using latest market data
- **🔍 Data Quality Monitoring**: Real-time drift detection using Evidently AI
- **📈 Interactive Dashboards**: Grafana visualizations for pipeline health and business metrics
- **📧 Smart Alerts**: Email notifications for good deals, data issues, and system failures
- **🚀 Flexible Deployment**: Run locally with Docker or deploy to AWS Lambda
- **⚡ Workflow Orchestration**: Prefect flows for reliable, observable pipeline execution

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Data Sources  │    │  Prefect Flows   │    │   Monitoring    │
│                 │───▶│                  │───▶│                 │
│ • Rentcast API  │    │ • Daily Preds    │    │ • Evidently AI  │
│ • NJ Listings   │    │ • Weekly Training│    │ • Grafana       │
└─────────────────┘    │ • Email Alerts   │    │ • PostgreSQL    │
                       └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │   ML Pipeline    │    │   Storage       │
                       │                  │    │                 │
                       │ • XGBoost Model  │    │ • S3 Buckets    │
                       │ • Hyperopt Tuning│    │ • MLflow        │
                       │ • Station Features│    │ • Model Registry│
                       └──────────────────┘    └─────────────────┘
```

## 📁 Project Structure

```
apartment-ml-pipeline/
├── 🚀 Quick Start
│   ├── deployment_script.sh         # One-click deployment
│   ├── docker-compose-final.yml     # Full service orchestration
│   └── .env                         # Environment configuration
├── 🤖 ML Pipeline Core
│   ├── training_model.py            # XGBoost training with Hyperopt
│   ├── lambda_daily_run.py          # Daily predictions + monitoring
│   ├── lambda_training.py           # Weekly model retraining
│   ├── ml_pipeline_flows.py         # Prefect workflow definitions
│   └── initial_data_pull_test.py    # Rentcast API integration
├── 📊 Monitoring & Alerting
│   ├── monitoring_config.py         # CloudWatch + SNS alerting
│   ├── email_options.py            # Email notification system
│   └── init_db_fixed.sql           # Database schema + sample data
├── 🎨 Dashboards & Config
│   ├── config/
│   │   ├── grafana_datasources.yaml
│   │   ├── grafana_dashboards.yaml
│   │   └── prometheus.yml
│   └── dashboards/
├── ☁️ Cloud Deployment (Optional)
│   ├── serverless.yml              # AWS Lambda deployment
│   ├── requirements.txt            # Python dependencies
│   ├── prefect.yaml               # Prefect deployment config
│   └── package.json               # Serverless plugins
└── 📄 Data & Documentation
    ├── cached_data.csv             # Sample apartment data
    ├── training_load.csv           # Training dataset
    ├── reference_data.csv          # Drift detection reference
    └── run_id.txt                  # Latest model run ID
```

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- **Docker** & **Docker Compose** installed
- **Python 3.9+** 
- **Git** for cloning
- **API key** for live data (optional - works with sample data)

### Option 1: Automated Deployment (Recommended)
```bash
# Clone repository
git clone <your-repository>
cd apartment-ml-pipeline

# Make deployment script executable
chmod +x deployment_script.sh

# Run one-click deployment
./deployment_script.sh
```

The script will:
- ✅ Check prerequisites (Docker, Docker Compose)
- ✅ Create directory structure
- ✅ Generate `.env` file with defaults
- ✅ Start all services (PostgreSQL, Grafana, Prefect, etc.)
- ✅ Setup sample data for immediate testing
- ✅ Provide access URLs and next steps

### Option 2: Manual Setup
```bash
# Clone and navigate
git clone <your-repository>
cd apartment-ml-pipeline

# Create environment file
cp .env.example .env  # Edit with your values

# Start services
docker-compose -f docker-compose-final.yml up -d

# Wait for services to be ready (2-3 minutes)
docker-compose ps
```

## 🔧 Environment Configuration

### Generated .env File
The deployment script creates a `.env` file with these defaults:

```bash
# Database Configuration
POSTGRES_DB=apartment_monitoring
POSTGRES_USER=postgres
POSTGRES_PASSWORD=example

# Grafana Configuration
GF_SECURITY_ADMIN_PASSWORD=admin

# AWS Configuration (update with your values)
AWS_REGION=us-east-1
MLFLOW_BUCKET=mlflow-artifact-mmichal
TRAINING_BUCKET=training-data-bucket-mmichal-apartments-nj

# Email Configuration
SENDER_EMAIL=matthew.michal11@gmail.com
RECIPIENT_EMAIL=matthew.michal11@gmail.com
```

### 🔒 Production Configuration (Important!)
**Update these values before production use:**

```bash
# 1. Secure your passwords
POSTGRES_PASSWORD=your_secure_database_password
GF_SECURITY_ADMIN_PASSWORD=your_grafana_admin_password

# 2. Update AWS resources (if using cloud deployment)
MLFLOW_BUCKET=your-unique-mlflow-bucket
TRAINING_BUCKET=your-unique-training-bucket

# 3. Configure email settings
SENDER_EMAIL=your-email@gmail.com
RECIPIENT_EMAIL=recipient@gmail.com

# 4. Add API key for live data (optional)
API_KEY=your_rentcast_api_key
```

## 🌐 Service Access

After deployment, access your services:

| Service | URL | Credentials | Purpose |
|---------|-----|-------------|---------|
| **🎨 Grafana Dashboard** | http://localhost:3000 | admin / admin | ML pipeline monitoring |
| **🗄️ Database Admin** | http://localhost:8080 | - | PostgreSQL management |
| **⚡ Prefect UI** | http://localhost:4200 | - | Workflow orchestration |
| **📊 Prometheus** | http://localhost:9090 | - | Metrics collection |

### 🎯 Your First Look at the Dashboard
1. Go to http://localhost:3000
2. Login with `admin` / `admin`
3. Navigate to **Dashboards** → **Apartment ML Pipeline Monitoring**
4. See real-time metrics with sample data!

**Key Panels to Watch:**
- **Data Drift Over Time**: Should stay below 0.3
- **Good Deals Found**: Business KPI tracking
- **Model Performance**: MAE and RMSE trends
- **Daily Data Volume**: Listings processed

## 🤖 Prefect Orchestration

### Flow Definitions
This pipeline includes three main Prefect flows:

1. **`daily_predictions_flow`**: 
   - Pulls fresh apartment data
   - Makes price predictions
   - Monitors data drift
   - Sends email alerts for good deals

2. **`weekly_training_flow`**:
   - Retrains ML model with latest data
   - Performs hyperparameter tuning
   - Updates model registry
   - Validates performance

3. **`full_ml_pipeline`**:
   - Runs complete pipeline (training + predictions)
   - Useful for initial setup or major updates

### Setting Up Prefect Flows

#### Deploy Flows
```bash
# Install Prefect (if not already installed)
pip install prefect==2.20.20

# Deploy daily predictions
prefect deployment build ml_pipeline_flows.py:daily_predictions_flow \
  -n "daily-apartment-predictions" \
  -q "ml-pipeline"
prefect deployment apply daily_predictions_flow-deployment.yaml

# Deploy weekly training
prefect deployment build ml_pipeline_flows.py:weekly_training_flow \
  -n "weekly-model-training" \
  -q "ml-pipeline"
prefect deployment apply weekly_training_flow-deployment.yaml
```

#### Default Schedule
The flows are configured with these schedules:
- **Daily Predictions**: 5:00 AM EST daily (`0 5 * * *`)
- **Weekly Training**: 1:00 AM EST Sundays (`0 1 * * 0`)

#### Manual Execution
```bash
# Run daily predictions manually
prefect deployment run "daily-apartment-predictions"

# Run weekly training manually
prefect deployment run "weekly-model-training"

# Or use the Prefect UI at http://localhost:4200
```

## 📊 Monitoring & Alerting

### Evidently AI Monitoring
The pipeline tracks these data quality metrics:
- **Prediction Drift**: Changes in model predictions over time
- **Target Drift**: Distribution shifts in actual apartment prices
- **Feature Drift**: Changes in input feature distributions
- **Missing Values**: Data completeness monitoring
- **Model Performance**: MAE, RMSE tracking

### Alert Thresholds
| Metric | Warning Threshold | Critical Threshold |
|--------|-------------------|-------------------|
| **Prediction Drift** | > 0.2 | > 0.5 |
| **Drifted Columns** | > 2 | > 5 |
| **Missing Values** | > 10% | > 20% |
| **MAE (Price)** | > $150 | > $250 |
| **Daily Volume** | < 100 listings | < 50 listings |

### CloudWatch Integration (AWS)
When deployed to AWS, the pipeline automatically sends metrics to CloudWatch:
- Custom namespace: `MLPipeline/ApartmentRent`
- SNS alerts for failures and quality issues
- Automated scaling based on processing volume

## 🔄 Data Flow

### Daily Operation
1. **6:00 AM**: Prefect triggers daily predictions flow
2. **6:05 AM**: Fresh data pulled from Rentcast API
3. **6:10 AM**: ML model makes price predictions
4. **6:15 AM**: Evidently calculates drift metrics
5. **6:20 AM**: Results stored in PostgreSQL
6. **6:25 AM**: Email sent with good deals (apartments >$100 under predicted)
7. **6:30 AM**: Grafana dashboard updates with new metrics

### Weekly Training
1. **Sunday 1:00 AM**: Training flow triggered
2. **1:05 AM**: Latest apartment data collected
3. **1:10 AM**: Feature engineering (station proximity, etc.)
4. **1:15 AM**: Hyperparameter optimization with Hyperopt
5. **1:45 AM**: Best model trained and registered in MLflow
6. **2:00 AM**: Model performance validation
7. **2:05 AM**: New model deployed for daily predictions

## ☁️ AWS Cloud Deployment (Optional)

### Prerequisites
```bash
# Install Serverless Framework
npm install -g serverless
npm install --save-dev serverless-python-requirements

# Configure AWS credentials
aws configure
```

### Deploy to AWS
```bash
# Set up AWS SSM parameters (secure storage)
aws ssm put-parameter --name "/ml-pipeline/mlflow-uri" --value "your-mlflow-uri" --type "String"
aws ssm put-parameter --name "/ml-pipeline/api-key" --value "your-api-key" --type "SecureString"
aws ssm put-parameter --name "/ml-pipeline/email-password" --value "your-email-password" --type "SecureString"

# Deploy with Serverless Framework
serverless deploy --verbose

# Verify deployment
aws lambda list-functions --query 'Functions[?contains(FunctionName, `apartment-ml-pipeline`)]'
```

### AWS Resources Created
- **Lambda Functions**: `dailyPredictions`, `weeklyTraining`
- **S3 Buckets**: MLflow artifacts, training data
- **SNS Topic**: `ml-pipeline-alerts` for notifications
- **IAM Roles**: Least-privilege access for Lambda functions
- **CloudWatch**: Custom metrics and log retention

## 🛠️ Development & Testing

### Test Individual Components
```bash
# Test data pulling
python initial_data_pull_test.py

# Test model training locally
python training_model.py

# Test Prefect flows
python ml_pipeline_flows.py

# Test email notifications
python -c "from email_options import quick_send_csv; import pandas as pd; quick_send_csv(pd.DataFrame({'test': [1]}), 'your@email.com', 'sender@email.com', 'password')"
```

### View Logs & Debug
```bash
# Docker service logs
docker-compose logs -f grafana
docker-compose logs -f prefect-server
docker-compose logs -f db

# Prefect flow logs
prefect flow-run logs <flow-run-id>

# Database debugging
docker-compose exec db psql -U postgres -d apartment_monitoring
SELECT * FROM apartment_metrics ORDER BY timestamp DESC LIMIT 10;
```

### Local Development Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Set environment variables
export PREFECT_API_URL="http://localhost:4200/api"
export AWS_PROFILE="default"

# Run flows locally
python ml_pipeline_flows.py
```

## 🔍 Troubleshooting

### Common Issues

#### 🐳 Docker Services Won't Start
```bash
# Check status
docker-compose ps

# View logs
docker-compose logs <service-name>

# Restart all services
docker-compose down && docker-compose up -d

# Reset completely (removes data)
docker-compose down -v && docker-compose up -d
```

#### 🗄️ Database Connection Issues
```bash
# Test database connectivity
docker-compose exec db pg_isready -U postgres

# Check if databases exist
docker-compose exec db psql -U postgres -l

# Connect manually
docker-compose exec db psql -U postgres -d apartment_monitoring
```

#### ⚡ Prefect Flow Issues
```bash
# Check Prefect server health
curl http://localhost:4200/health

# View agent status
prefect agent ls

# Check work queues
prefect work-queue ls

# Restart Prefect services
docker-compose restart prefect-server prefect-agent
```

#### 🎨 Grafana Dashboard Problems
```bash
# Restart Grafana
docker-compose restart grafana

# Test datasource connection
# Go to Grafana → Configuration → Data Sources → Test

# Re-import dashboard
# Dashboards → Import → Upload apartment_monitoring_dashboard.json
```

#### 📧 Email Notifications Not Working
```bash
# Check email configuration in .env
cat .env | grep EMAIL

# Test email settings
python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('your-email@gmail.com', 'your-app-password')
print('Email connection successful!')
server.quit()
"
```

### Performance Issues

#### High Memory Usage
```yaml
# In docker-compose-final.yml, adjust resources:
ml-pipeline:
  deploy:
    resources:
      limits:
        memory: 4G
        cpus: '2.0'
```

#### Slow Predictions
```python
# In ml_pipeline_flows.py, process data in batches:
@task
def process_predictions_batch(df, batch_size=1000):
    # Process data in smaller chunks
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        # Process batch...
```

## 🔒 Security & Best Practices

### 1. Secure Your Installation
```bash
# Change default passwords (update .env)
POSTGRES_PASSWORD=your_very_secure_password_here
GF_SECURITY_ADMIN_PASSWORD=your_grafana_admin_password

# Set proper permissions
chmod 600 .env
```

### 2. API Key Security
```bash
# Never commit API keys to git
echo ".env" >> .gitignore
echo "*.key" >> .gitignore

# Use environment variables
export API_KEY="your_api_key_here"
```

### 3. Production Security Checklist
- [ ] Change all default passwords
- [ ] Enable SSL/TLS for Grafana
- [ ] Configure firewall rules
- [ ] Set up VPN access if needed
- [ ] Regular security updates
- [ ] Monitor access logs

## 🎯 Business Value & Use Cases

### For Real Estate Professionals
- **Market Intelligence**: Identify underpriced properties automatically
- **Portfolio Analysis**: Monitor price trends across different areas
- **Client Alerts**: Automated notifications for good deals matching criteria

### For Property Investors
- **Deal Flow**: Daily email updates with investment opportunities
- **Market Timing**: Understand when to buy based on price predictions
- **Risk Management**: Data drift alerts indicate market changes

### For Data Scientists
- **Production ML**: End-to-end pipeline with monitoring
- **Drift Detection**: Real-world implementation of data quality monitoring
- **A/B Testing**: Framework for testing model improvements

## 📈 Performance Metrics

### Typical Performance
- **Data Processing**: ~1,000 listings in 2-3 minutes
- **Model Training**: ~5-10 minutes for hyperparameter tuning
- **Prediction Accuracy**: MAE typically $120-180 for NJ market
- **System Uptime**: >99% with proper monitoring

### Scalability
- **Current Capacity**: Handles 5,000+ daily listings
- **Storage**: Efficient data retention (30 days monitoring, 1 year training data)
- **Cost**: ~$20-50/month on AWS for moderate usage

## 🤝 Contributing & Customization

### Adding New Features
```bash
# Create feature branch
git checkout -b feature/new-monitoring-metric

# Add your changes
# Update configuration files as needed

# Test locally
docker-compose up -d

# Submit pull request
```

### Custom Dashboards
1. Create dashboard in Grafana UI
2. Export JSON: Settings → JSON Model → Copy to Clipboard
3. Save to `dashboards/` directory
4. Update `config/grafana_dashboards.yaml` if needed

### New Data Sources
1. Add API integration to `initial_data_pull_test.py`
2. Update feature engineering in `training_model.py`
3. Modify monitoring schema in `init_db_fixed.sql`
4. Update Grafana queries for new metrics

## 📞 Support & Maintenance

### Regular Maintenance (Weekly)
- [ ] Review model performance metrics in Grafana
- [ ] Check for data drift trends
- [ ] Validate email notifications are working
- [ ] Review good deals identified for accuracy
- [ ] Monitor system resource usage

### Monthly Tasks
- [ ] Update dependencies: `pip install -r requirements.txt --upgrade`
- [ ] Archive old monitoring data
- [ ] Review and optimize database queries
- [ ] Security audit of stored credentials
- [ ] Test backup and recovery procedures

### Getting Help
1. **Check Logs**: Start with `docker-compose logs <service>`
2. **Review Documentation**: Check troubleshooting section above
3. **Community Support**: 
   - Prefect: https://docs.prefect.io
   - Grafana: https://grafana.com/docs/
   - Evidently: https://docs.evidentlyai.com/

## 🎉 Success Indicators

You'll know the pipeline is working correctly when:
- ✅ Grafana dashboard shows data flowing every day
- ✅ Email notifications arrive with apartment listings
- ✅ Model performance metrics remain stable
- ✅ Data drift scores stay within acceptable ranges
- ✅ Prefect flows complete successfully without manual intervention

## 🎈 Next Steps

### Immediate (First Week)
1. **Customize Email Recipients**: Update `email_options.py` with your preferred contacts
2. **Add Your API Key**: Set `API_KEY` in `.env` for live data
3. **Configure Alerts**: Set up Grafana notifications for your thresholds
4. **Test End-to-End**: Run manual flow execution to verify everything works

### Short Term (First Month)
1. **Expand Coverage**: Add new geographical areas or property types
2. **Improve Features**: Add commute times, school ratings, crime data
3. **Business Rules**: Customize "good deal" logic for your market
4. **Performance Tuning**: Optimize for your specific data volume

### Long Term (3-6 Months)
1. **Advanced Models**: Experiment with deep learning approaches
2. **Real-Time Processing**: Implement streaming pipeline for immediate alerts
3. **Mobile App**: Build mobile interface for deal notifications
4. **Multi-Market**: Expand to other metro areas

---

## 📄 License & Usage

This project is designed for educational and personal use. Please ensure compliance with:
- Data source terms of service (Rentcast API)
- Email service provider policies
- Cloud provider usage limits and costs
- Local data protection regulations

---

## 🚀 Ready to Find Great Apartment Deals?

Your comprehensive apartment ML pipeline is now ready to:
- 🔍 **Automatically discover** underpriced rentals
- 📊 **Monitor market trends** with professional dashboards  
- ⚡ **Scale effortlessly** from local development to cloud production
- 🎯 **Alert you instantly** when opportunities arise
- 📈 **Learn continuously** from market changes

**🎯 Quick Start Reminder:**
```bash
./deployment_script.sh
# Wait 3 minutes...
# Visit http://localhost:3000
# Start finding great deals! 🏠✨
```

Happy apartment hunting! 🎉