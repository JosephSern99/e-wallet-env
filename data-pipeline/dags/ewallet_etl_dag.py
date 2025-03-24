"""
ewallet_etl_dag.py - Airflow DAG to orchestrate the e-wallet data pipeline
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
import os
import sys

# Add the scripts directory to the Python path
sys.path.append('/opt/airflow/dags/scripts')

# Import the ETL functions
from transaction_etl import extract_transform_load

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
}

# Define the DAG
dag = DAG(
    'ewallet_etl',
    default_args=default_args,
    description='E-Wallet ETL pipeline',
    schedule_interval='@hourly',  # Run hourly
    start_date=days_ago(1),
    catchup=False,
)

# Generate test data (for development/testing only)
generate_test_data = BashOperator(
    task_id='generate_test_data',
    bash_command='python /opt/airflow/dags/scripts/data_generator.py --config /opt/airflow/dags/config/pipeline_config.json --transactions 500 --activities 1000',
    dag=dag,
)

# Process transaction data
process_transactions = PythonOperator(
    task_id='process_transactions',
    python_callable=extract_transform_load,
    op_kwargs={'config_path': '/opt/airflow/dags/config/pipeline_config.json'},
    dag=dag,
)

# Create SQL analysis views
create_analysis_views = BashOperator(
    task_id='create_analysis_views',
    bash_command='psql -h postgres -U postgres -d ewallet -f /opt/airflow/dags/sql/create_analysis_views.sql',
    dag=dag,
)

# Define the task dependencies
generate_test_data >> process_transactions >> create_analysis_views