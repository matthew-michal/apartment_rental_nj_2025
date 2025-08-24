-- Initialize apartment monitoring database and Prefect database
-- This script runs when the PostgreSQL container starts

-- Create the Prefect database first
CREATE DATABASE prefect_db;

-- Connect to apartment_monitoring database (this should already exist from POSTGRES_DB env var)
\c apartment_monitoring;

-- Create apartment metrics table
CREATE TABLE IF NOT EXISTS apartment_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    prediction_drift FLOAT DEFAULT 0,
    num_drifted_columns INTEGER DEFAULT 0,
    share_missing_values FLOAT DEFAULT 0,
    target_drift FLOAT DEFAULT 0,
    prediction_mae FLOAT DEFAULT 0,
    prediction_rmse FLOAT DEFAULT 0,
    data_points INTEGER DEFAULT 0,
    avg_predicted_price FLOAT DEFAULT 0,
    avg_actual_price FLOAT DEFAULT 0,
    price_diff_std FLOAT DEFAULT 0,
    good_deals_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_apartment_metrics_timestamp ON apartment_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_apartment_metrics_created_at ON apartment_metrics(created_at);

-- Insert sample data for testing
INSERT INTO apartment_metrics (
    timestamp, prediction_drift, num_drifted_columns, share_missing_values,
    target_drift, prediction_mae, prediction_rmse, data_points,
    avg_predicted_price, avg_actual_price, price_diff_std, good_deals_count
) VALUES 
    (NOW() - INTERVAL '7 days', 0.15, 2, 0.05, 0.12, 150.5, 200.3, 145, 2800.50, 2750.25, 125.75, 8),
    (NOW() - INTERVAL '6 days', 0.18, 3, 0.03, 0.14, 165.2, 215.8, 132, 2850.75, 2800.10, 135.20, 12),
    (NOW() - INTERVAL '5 days', 0.12, 1, 0.02, 0.08, 142.8, 188.4, 156, 2775.25, 2825.50, 118.90, 6),
    (NOW() - INTERVAL '4 days', 0.20, 4, 0.08, 0.16, 178.3, 225.7, 124, 2900.00, 2780.75, 142.65, 15),
    (NOW() - INTERVAL '3 days', 0.14, 2, 0.04, 0.11, 155.7, 198.2, 139, 2825.80, 2795.30, 128.45, 9),
    (NOW() - INTERVAL '2 days', 0.16, 3, 0.06, 0.13, 162.4, 207.9, 148, 2875.25, 2810.60, 133.85, 11),
    (NOW() - INTERVAL '1 day', 0.13, 1, 0.03, 0.09, 148.9, 192.6, 151, 2800.95, 2840.20, 122.30, 7);

-- Create a view for recent metrics (last 30 days)
CREATE OR REPLACE VIEW recent_apartment_metrics AS
SELECT * FROM apartment_metrics 
WHERE timestamp >= NOW() - INTERVAL '30 days'
ORDER BY timestamp DESC;

-- Grant permissions for both databases
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Switch to prefect database and grant permissions
\c prefect_db;
GRANT ALL PRIVILEGES ON DATABASE prefect_db TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;