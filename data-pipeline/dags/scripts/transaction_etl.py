#!/usr/bin/env python3
"""
transaction_etl.py - Extract, transform and load e-wallet transactions
"""

import json
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from kafka import KafkaConsumer
import logging
import argparse
from datetime import datetime
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path):
    """Load configuration from a JSON file"""
    with open(config_path, 'r') as f:
        return json.load(f)

def connect_to_db(config):
    """Create a connection to PostgreSQL"""
    conn = psycopg2.connect(
        host=config['postgresql']['host'],
        port=config['postgresql']['port'],
        user=config['postgresql']['user'],
        password=config['postgresql']['password'],
        database=config['postgresql']['database']
    )
    return conn

def ensure_data_warehouse_schema(conn, schema_name):
    """Ensure the data warehouse schema exists"""
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
        
        # Create fact_transactions table
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema_name}.fact_transactions (
            transaction_id VARCHAR(255) PRIMARY KEY,
            user_id INT NOT NULL,
            transaction_type VARCHAR(50) NOT NULL,
            amount DECIMAL(19, 4) NOT NULL,
            currency VARCHAR(3) NOT NULL,
            status VARCHAR(20) NOT NULL,
            transaction_time TIMESTAMP NOT NULL,
            merchant_id VARCHAR(255),
            category VARCHAR(100),
            latitude DECIMAL(9, 6),
            longitude DECIMAL(9, 6),
            device_id VARCHAR(255),
            ip_address VARCHAR(45),
            is_flagged BOOLEAN DEFAULT FALSE,
            etl_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create dim_users table for dimensional modeling
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema_name}.dim_users (
            user_id INT PRIMARY KEY,
            username VARCHAR(255),
            email VARCHAR(255),
            country VARCHAR(100),
            account_status VARCHAR(50),
            registration_date TIMESTAMP,
            last_login TIMESTAMP,
            user_type VARCHAR(50),
            etl_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create dim_time for time-based analysis
        cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {schema_name}.dim_time (
            time_id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP UNIQUE,
            hour INT,
            day INT,
            month INT,
            year INT,
            day_of_week INT,
            week_of_year INT,
            is_weekend BOOLEAN,
            quarter INT
        )
        """)
        
        conn.commit()
        logger.info(f"Ensured data warehouse schema and tables exist")

def extract_from_kafka(config, topic, max_records=None):
    """Extract transaction data from Kafka topic"""
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=config['kafka']['bootstrap_servers'],
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=10000  # Stop consuming after 10 seconds of inactivity
    )
    
    records = []
    count = 0
    
    logger.info(f"Starting to consume from Kafka topic: {topic}")
    for message in consumer:
        records.append(message.value)
        count += 1
        
        if max_records and count >= max_records:
            break
    
    consumer.close()
    logger.info(f"Extracted {len(records)} records from Kafka")
    return records

def transform_transactions(transactions):
    """Transform transaction data"""
    if not transactions:
        return pd.DataFrame()
    
    # Convert to DataFrame
    df = pd.DataFrame(transactions)
    
    # Handle missing values
    df['merchant_id'] = df.get('merchant_id', pd.Series([None] * len(df)))
    df['category'] = df.get('category', pd.Series([None] * len(df)))
    df['latitude'] = df.get('latitude', pd.Series([None] * len(df)))
    df['longitude'] = df.get('longitude', pd.Series([None] * len(df)))
    df['device_id'] = df.get('device_id', pd.Series([None] * len(df)))
    df['ip_address'] = df.get('ip_address', pd.Series([None] * len(df)))
    
    # Convert transaction_time to datetime
    df['transaction_time'] = pd.to_datetime(df['transaction_time'])
    
    # Flag potentially suspicious transactions (example criteria)
    df['is_flagged'] = (
        (df['amount'] > 10000) |  # Large transactions
        (df['transaction_type'] == 'INTERNATIONAL' & (df['amount'] > 5000))  # Large international transfers
    )
    
    # Add ETL timestamp
    df['etl_updated_at'] = datetime.now()
    
    return df

def load_dimension_time(conn, schema_name, timestamps):
    """Load time dimension with timestamps from transactions"""
    with conn.cursor() as cur:
        for ts in timestamps:
            dt = pd.to_datetime(ts)
            # Check if this timestamp already exists
            cur.execute(f"SELECT 1 FROM {schema_name}.dim_time WHERE timestamp = %s", (dt,))
            if not cur.fetchone():
                # Insert new time dimension record
                cur.execute(f"""
                INSERT INTO {schema_name}.dim_time (
                    timestamp, hour, day, month, year, day_of_week, week_of_year, is_weekend, quarter
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """, (
                    dt,
                    dt.hour,
                    dt.day,
                    dt.month,
                    dt.year,
                    dt.dayofweek,
                    dt.weekofyear,
                    dt.dayofweek >= 5,  # 5 = Saturday, 6 = Sunday
                    (dt.month - 1) // 3 + 1
                ))
        conn.commit()
        logger.info(f"Loaded time dimension with {len(timestamps)} records")

def load_to_warehouse(conn, df, schema_name, table_name):
    """Load transformed data to the data warehouse"""
    if df.empty:
        logger.warning("No data to load")
        return 0
    
    # Convert DataFrame to list of tuples
    records = df.to_records(index=False)
    data = [tuple(x) for x in records]
    
    # Get column names from DataFrame
    columns = df.columns.tolist()
    
    # Generate the INSERT query
    insert_query = f"""
    INSERT INTO {schema_name}.{table_name} ({', '.join(columns)})
    VALUES %s
    ON CONFLICT (transaction_id) DO UPDATE SET
    {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != 'transaction_id'])}
    """
    
    # Execute the insert
    with conn.cursor() as cur:
        execute_values(cur, insert_query, data)
        conn.commit()
    
    logger.info(f"Loaded {len(data)} records into {schema_name}.{table_name}")
    return len(data)

def extract_transform_load(config_path):
    """Main ETL function"""
    # Load configuration
    config = load_config(config_path)
    schema_name = config['postgresql']['data_warehouse_schema']
    
    try:
        # Connect to database
        conn = connect_to_db(config)
        
        # Ensure data warehouse schema and tables exist
        ensure_data_warehouse_schema(conn, schema_name)
        
        # Extract transactions from Kafka
        transactions = extract_from_kafka(
            config, 
            config['kafka']['transaction_topic'],
            config['batch_size']
        )
        
        if not transactions:
            logger.info("No new transactions to process")
            return 0
        
        # Transform transactions
        transformed_df = transform_transactions(transactions)
        
        # Load time dimension
        load_dimension_time(conn, schema_name, transformed_df['transaction_time'])
        
        # Load transactions fact table
        records_loaded = load_to_warehouse(conn, transformed_df, schema_name, 'fact_transactions')
        
        return records_loaded
        
    except Exception as e:
        logger.error(f"ETL process failed: {str(e)}", exc_info=True)
        raise
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    parser = argparse.ArgumentParser(description='E-Wallet Transaction ETL')
    parser.add_argument('--config', required=True, help='Path to configuration file')
    args = parser.parse_args()
    
    try:
        records_processed = extract_transform_load(args.config)
        logger.info(f"ETL job completed successfully. Processed {records_processed} records.")
    except Exception as e:
        logger.error(f"ETL job failed: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()