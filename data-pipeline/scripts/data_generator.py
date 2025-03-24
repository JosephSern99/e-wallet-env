#!/usr/bin/env python3
"""
data_generator.py - Generate synthetic e-wallet transaction data for testing
"""

import json
import random
from datetime import datetime, timedelta
from kafka import KafkaProducer
import logging
import argparse
import time
import uuid

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

def get_kafka_producer(bootstrap_servers):
    """Create a Kafka producer"""
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

def generate_transaction():
    """Generate a random transaction"""
    transaction_types = ['DEPOSIT', 'WITHDRAWAL', 'TRANSFER', 'PAYMENT', 'INTERNATIONAL']
    currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD']
    statuses = ['COMPLETED', 'PENDING', 'FAILED', 'REVERSED']
    categories = ['FOOD', 'SHOPPING', 'ENTERTAINMENT', 'TRAVEL', 'UTILITIES', 'OTHER']
    
    # Random user id between 1 and 1000
    user_id = random.randint(1, 1000)
    
    # Random transaction amount between 1 and 20000
    amount = round(random.uniform(1, 20000), 2)
    
    # Generate random coordinates (roughly covering the US)
    latitude = random.uniform(24.0, 49.0)
    longitude = random.uniform(-125.0, -66.0)
    
    # Generate a timestamp within the last week
    now = datetime.now()
    transaction_time = (now - timedelta(days=random.randint(0, 7), 
                                       hours=random.randint(0, 23),
                                       minutes=random.randint(0, 59),
                                       seconds=random.randint(0, 59))).isoformat()
    
    return {
        'transaction_id': str(uuid.uuid4()),
        'user_id': user_id,
        'transaction_type': random.choice(transaction_types),
        'amount': amount,
        'currency': random.choice(currencies),
        'status': random.choice(statuses),
        'transaction_time': transaction_time,
        'merchant_id': f'MERCH-{random.randint(1000, 9999)}' if random.random() > 0.3 else None,
        'category': random.choice(categories) if random.random() > 0.2 else None,
        'latitude': latitude,
        'longitude': longitude,
        'device_id': f'DEV-{random.randint(10000, 99999)}',
        'ip_address': f'{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}'
    }

def generate_user_activity():
    """Generate random user activity"""
    activity_types = ['LOGIN', 'LOGOUT', 'VIEW_TRANSACTION', 'UPDATE_PROFILE', 'CHANGE_PASSWORD', 'ADD_CARD']
    platforms = ['WEB', 'ANDROID', 'IOS', 'API']
    
    # Random user id between 1 and 1000
    user_id = random.randint(1, 1000)
    
    # Generate a timestamp within the last week
    now = datetime.now()
    activity_time = (now - timedelta(days=random.randint(0, 7), 
                                    hours=random.randint(0, 23),
                                    minutes=random.randint(0, 59),
                                    seconds=random.randint(0, 59))).isoformat()
    
    return {
        'activity_id': str(uuid.uuid4()),
        'user_id': user_id,
        'activity_type': random.choice(activity_types),
        'platform': random.choice(platforms),
        'activity_time': activity_time,
        'device_id': f'DEV-{random.randint(10000, 99999)}',
        'ip_address': f'{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}',
        'session_id': str(uuid.uuid4()),
        'success': random.random() > 0.1  # 10% chance of failure
    }

def produce_data(config_path, num_transactions, num_activities):
    """Produce synthetic data to Kafka topics"""
    config = load_config(config_path)
    producer = get_kafka_producer(config['kafka']['bootstrap_servers'])
    
    # Generate and send transaction data
    for _ in range(num_transactions):
        transaction = generate_transaction()
        producer.send(config['kafka']['transaction_topic'], transaction)
        if _ % 100 == 0:
            logger.info(f"Generated {_} transactions")
    
    # Generate and send user activity data
    for _ in range(num_activities):
        activity = generate_user_activity()
        producer.send(config['kafka']['user_activity_topic'], activity)
        if _ % 100 == 0:
            logger.info(f"Generated {_} user activities")
    
    # Ensure all messages are sent
    producer.flush()
    logger.info(f"Successfully produced {num_transactions} transactions and {num_activities} user activities")

def main():
    parser = argparse.ArgumentParser(description='E-Wallet Data Generator')
    parser.add_argument('--config', required=True, help='Path to configuration file')
    parser.add_argument('--transactions', type=int, default=1000, help='Number of transactions to generate')
    parser.add_argument('--activities', type=int, default=2000, help='Number of user activities to generate')
    args = parser.parse_args()
    
    try:
        produce_data(args.config, args.transactions, args.activities)
    except Exception as e:
        logger.error(f"Data generation failed: {str(e)}", exc_info=True)
        exit(1)

if __name__ == "__main__":
    main()