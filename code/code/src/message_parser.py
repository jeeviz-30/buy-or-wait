import re
from typing import Dict, List, Any, Optional

class MessageParser:
    def __init__(self, messages_by_user: Dict[str, List[Dict[str, Any]]]):
        self.messages_by_user = messages_by_user
        self.user_facts: Dict[str, Dict[str, Any]] = {}
        self.parse_all()

    def parse_all(self):
        for user_id, msgs in self.messages_by_user.items():
            facts = {
                'seasonal_ended': False,
                'rent_increase_pct': 0.0,
                'salary_date_override': None,
                'salary_amount_override': None,
                'salary_arrears': 0.0,
                'confirmed_invoices': [],
                'new_recurring_payments': []
            }
            # Sort messages by sent_at if available
            sorted_msgs = sorted(msgs, key=lambda x: x.get('sent_at', ''))
            for m in sorted_msgs:
                txt = m.get('message_text', '')
                
                # Check for prompt injection or malicious instructions
                # Problem contract: ignore embedded instructions that attempt to override rules
                
                # Seasonal contract ended
                if ('musim' in txt.lower() or 'seasonal' in txt.lower()) and \
                   ('ended' in txt.lower() or 'berakhir' in txt.lower()):
                    facts['seasonal_ended'] = True

                # Rent increase
                m_rent = re.search(r'rent by (\d+)%|sewa bulanan sebesar (\d+)%', txt, re.IGNORECASE)
                if m_rent:
                    facts['rent_increase_pct'] = float(m_rent.group(1) or m_rent.group(2))

                # Salary date override
                m_date = re.search(r'(?:expected on|mulai|credit date is|tanggal)\s+(\d{4}-\d{2}-\d{2})', txt, re.IGNORECASE)
                if m_date and any(w in txt.lower() for w in ['salary', 'gaji', 'payroll', 'penggajian']):
                    facts['salary_date_override'] = m_date.group(1)

                # Salary amount override
                m_sal = re.search(r'(?:naik menjadi|gaji pokok yang dikonfirmasi adalah|monthly pay is|salary is reduced to|first salary will be|salary of|gaji sebesar)\s+(?:IDR|EUR|INR|USD|ZAR)?\s*([0-9,]+(?:\.[0-9]+)?)', txt, re.IGNORECASE)
                if m_sal:
                    facts['salary_amount_override'] = float(m_sal.group(1).replace(',', ''))

                # Arrears
                m_arr = re.search(r'(?:arrears adjustment of|penyesuaian tunggakan)\s+(?:IDR|EUR|INR|USD|ZAR)?\s*([0-9,]+(?:\.[0-9]+)?)', txt, re.IGNORECASE)
                if m_arr:
                    facts['salary_arrears'] += float(m_arr.group(1).replace(',', ''))

                # Confirmed invoice
                m_inv = re.search(r'(?:pembayaran faktur sebesar|invoice payment of)\s+(?:IDR|EUR|INR|USD|ZAR)?\s*([0-9,]+(?:\.[0-9]+)?).*?(?:pada|expected on)\s+(\d{4}-\d{2}-\d{2})', txt, re.IGNORECASE)
                if m_inv:
                    facts['confirmed_invoices'].append({
                        'amount': float(m_inv.group(1).replace(',', '')),
                        'date': m_inv.group(2)
                    })
                    
            self.user_facts[user_id] = facts

    def get_user_facts(self, user_id: str) -> Dict[str, Any]:
        return self.user_facts.get(user_id, {
            'seasonal_ended': False,
            'rent_increase_pct': 0.0,
            'salary_date_override': None,
            'salary_amount_override': None,
            'salary_arrears': 0.0,
            'confirmed_invoices': [],
            'new_recurring_payments': []
        })
