import os
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / 'dataset'
MEDIA_DIR = DATASET_DIR / 'media' / 'images'
OUTPUT_CSV_PATH = PROJECT_ROOT / 'output.csv'
USAGE_REPORT_PATH = PROJECT_ROOT / 'code' / 'evaluation' / 'usage_report.md'
ROOT_USAGE_REPORT_PATH = PROJECT_ROOT / 'evaluation' / 'usage_report.md'

# Output Columns contract
OUTPUT_COLUMNS = [
    'request_id',
    'amount_safe_to_pay',
    'affordability_status',
    'recommended_payment_method',
    'payment_plan',
    'earliest_date_for_full_payment',
    'spending_changes_needed',
    'decision_explanation'
]

# Allowed Statuses
STATUS_AFFORDABLE_NOW = 'affordable_now'
STATUS_AFFORDABLE_WITH_PLAN = 'affordable_with_plan'
STATUS_AFFORDABLE_LATER = 'affordable_later'
STATUS_NOT_AFFORDABLE = 'not_affordable'

# Allowed Payment Methods
METHOD_FULL_PAYMENT = 'full_payment'
METHOD_PARTIAL_PAYMENT = 'partial_payment'
METHOD_INSTALLMENTS = 'installments'
METHOD_WAIT = 'wait'
METHOD_NOT_RECOMMENDED = 'not_recommended'

# Forecast Horizon
FORECAST_DAYS = 90

# Currency mappings and symbols
CURRENCY_SYMBOLS = {
    'INR': 'INR ',
    'ZAR': 'ZAR ',
    'IDR': 'IDR ',
    'USD': 'USD ',
    'EUR': 'EUR '
}
