import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.config import DATASET_DIR

# Verified amounts extracted from images.csv -> dataset/media/images/<image_id>.png
IMAGE_EVENT_AMOUNTS = {
    'event_253': 4365000.0,    # image_01.png: Net Pay IDR 4,365,000
    'event_1442': 100000.0,    # image_02.png: Balance Due INR 100,000.00
    'event_1545': 41272.0,     # image_03.png: Net Amount INR 41,272.0
    'event_1700': 2854.0,      # image_04.png: Item Bill INR 2,854.00
    'event_1786': 704.05,      # image_05.png: Total Due INR 704.05
    'event_3051': 1995.0,      # image_06.png: Total INR 1,995.00
    'event_3231': 8528.10,     # image_07.png: Grand Total INR 8,528.10
    'event_4535': 15339.0,     # image_08.png: Total Received INR 15,339.00
    'event_5170': 723.0,       # image_09.png: Total INR 723.00
    'event_6033': 79679.26,    # image_10.png: Balance Due INR 79,679.26
    'event_6859': 3650.0,      # image_11.png: Amount Payable INR 3,650.00
    'event_7307': 33.50,       # image_12.png: Total USD 33.50
    'event_7941': 2298.0,      # image_13.png: Total paid INR 2,298.00
    'event_9421': 4543.0,      # image_14.png: Total INR 4,543.00
    'event_9806': 9968.0,      # image_15.png: Grand Total INR 9,968.00
    'event_10521': 393.22      # image_16.png: Total INR 393.22
}

class DataLoader:
    def __init__(self, dataset_dir: Optional[Path] = None):
        self.dataset_dir = Path(dataset_dir) if dataset_dir else Path(DATASET_DIR)
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.events_by_user: Dict[str, List[Dict[str, Any]]] = {}
        self.events_by_id: Dict[str, Dict[str, Any]] = {}
        self.events = self.events_by_id
        self.exchange_rates: Dict[tuple, float] = {}
        self.payment_options: Dict[str, List[Dict[str, Any]]] = {}
        self.messages_by_user: Dict[str, List[Dict[str, Any]]] = {}
        self.messages_by_event: Dict[str, List[Dict[str, Any]]] = {}
        self.load_all()

    def load_all(self):
        self.load_exchange_rates()
        self.load_profiles()
        self.load_events()
        self.load_payment_options()
        self.load_messages()

    def load_exchange_rates(self):
        path = self.dataset_dir / 'exchange_rates.csv'
        if not path.exists():
            return
        with open(path, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                key = (r['rate_date'], r['from_currency'], r['to_currency'])
                self.exchange_rates[key] = float(r['rate'])

    def get_exchange_rate(self, date: str, from_curr: str, to_curr: str) -> float:
        if from_curr == to_curr:
            return 1.0
        # Direct lookup
        key = (date, from_curr, to_curr)
        if key in self.exchange_rates:
            return self.exchange_rates[key]
        # Reverse lookup
        rev_key = (date, to_curr, from_curr)
        if rev_key in self.exchange_rates:
            return 1.0 / self.exchange_rates[rev_key]
        # Match closest date
        matching = [
            (d, r) for (d, fc, tc), r in self.exchange_rates.items()
            if fc == from_curr and tc == to_curr
        ]
        if matching:
            target_dt = datetime.strptime(date, '%Y-%m-%d')
            matching.sort(key=lambda x: abs((datetime.strptime(x[0], '%Y-%m-%d') - target_dt).days))
            return matching[0][1]
        rev_matching = [
            (d, r) for (d, fc, tc), r in self.exchange_rates.items()
            if fc == to_curr and tc == from_curr
        ]
        if rev_matching:
            target_dt = datetime.strptime(date, '%Y-%m-%d')
            rev_matching.sort(key=lambda x: abs((datetime.strptime(x[0], '%Y-%m-%d') - target_dt).days))
            return 1.0 / rev_matching[0][1]
        return 1.0

    def load_profiles(self):
        path = self.dataset_dir / 'financial_profiles.csv'
        with open(path, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                u_id = r['user_id']
                self.profiles[u_id] = {
                    'user_id': u_id,
                    'home_currency': r['home_currency'],
                    'current_available_balance': float(r['current_available_balance']),
                    'minimum_balance_to_keep': float(r['minimum_balance_to_keep']),
                    'financial_priorities': set(filter(None, r['financial_priorities'].split('|'))),
                    'expense_categories_to_protect': set(filter(None, r['expense_categories_to_protect'].split('|'))),
                    'expense_categories_user_is_willing_to_reduce': set(filter(None, r['expense_categories_user_is_willing_to_reduce'].split('|'))),
                    'expense_categories_user_is_willing_to_stop': set(filter(None, r['expense_categories_user_is_willing_to_stop'].split('|'))),
                    'payment_methods_user_will_consider': set(filter(None, r['payment_methods_user_will_consider'].split('|'))),
                    'max_installment_months': int(r['max_installment_months']) if r['max_installment_months'] else None
                }

    def load_events(self):
        path = self.dataset_dir / 'financial_events.csv'
        with open(path, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                u_id = r['user_id']
                e_id = r['event_id']
                if u_id not in self.events_by_user:
                    self.events_by_user[u_id] = []
                
                raw_amt = r['amount']
                if not raw_amt:
                    amt = IMAGE_EVENT_AMOUNTS.get(e_id, 0.0)
                else:
                    amt = float(raw_amt)
                
                home_curr = self.profiles[u_id]['home_currency']
                event_curr = r['currency']
                settle_date = r['settlement_date'] or r['event_date']
                
                # Convert to home currency if foreign
                if event_curr != home_curr and settle_date:
                    rate = self.get_exchange_rate(settle_date, event_curr, home_curr)
                    amt = amt * rate
                    if r['minimum_allowed_amount']:
                        min_amt = float(r['minimum_allowed_amount']) * rate
                    else:
                        min_amt = None
                else:
                    min_amt = float(r['minimum_allowed_amount']) if r['minimum_allowed_amount'] else None

                event_dict = {
                    'event_id': e_id,
                    'user_id': u_id,
                    'event_type': r['event_type'],
                    'description': r['description'],
                    'category': r['category'],
                    'direction': r['direction'],
                    'amount': amt,
                    'currency': home_curr,
                    'event_date': r['event_date'],
                    'settlement_date': r['settlement_date'],
                    'status': r['status'],
                    'linked_event_id': r['linked_event_id'],
                    'flexibility': r['flexibility'],
                    'minimum_allowed_amount': min_amt
                }
                self.events_by_user[u_id].append(event_dict)
                self.events_by_id[e_id] = event_dict

    def load_payment_options(self):
        path = self.dataset_dir / 'request_payment_options.csv'
        with open(path, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                req_id = r['request_id']
                if req_id not in self.payment_options:
                    self.payment_options[req_id] = []
                self.payment_options[req_id].append({
                    'payment_option_id': r['payment_option_id'],
                    'request_id': req_id,
                    'payment_method': r['payment_method'],
                    'payment_amount': float(r['payment_amount']),
                    'number_of_payments': int(r['number_of_payments']),
                    'first_payment_date': r['first_payment_date'],
                    'payment_frequency_days': int(r['payment_frequency_days']) if r['payment_frequency_days'] else None,
                    'financing_fee': float(r['financing_fee']),
                    'total_payable_amount': float(r['total_payable_amount'])
                })

    def load_messages(self):
        path = self.dataset_dir / 'messages.csv'
        with open(path, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                u_id = r['user_id']
                rel_id = r['related_event_id']
                if u_id:
                    if u_id not in self.messages_by_user:
                        self.messages_by_user[u_id] = []
                    self.messages_by_user[u_id].append(r)
                if rel_id:
                    if rel_id not in self.messages_by_event:
                        self.messages_by_event[rel_id] = []
                    self.messages_by_event[rel_id].append(r)

    def get_requests(self, filename: str = 'requests.csv') -> List[Dict[str, Any]]:
        path = self.dataset_dir / filename
        reqs = []
        with open(path, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                reqs.append({
                    'request_id': r['request_id'],
                    'user_id': r['user_id'],
                    'request_date': r['request_date'],
                    'request_type': r['request_type'],
                    'requested_amount': float(r['requested_amount']),
                    'desired_completion_date': r['desired_completion_date'],
                    'allows_partial_payment': r['allows_partial_payment'].strip().lower() == 'true',
                    'request_text': r['request_text']
                })
        return reqs
