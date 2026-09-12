from collections import defaultdict, Counter
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from src.data_loader import DataLoader
from src.message_parser import MessageParser

class Forecaster:
    def __init__(self, data_loader: DataLoader, message_parser: MessageParser):
        self.dl = data_loader
        self.mp = message_parser

    def analyze_user_series(self, user_id: str, request_date: str) -> Dict[str, Any]:
        all_events = self.dl.events_by_user.get(user_id, [])
        facts = self.mp.get_user_facts(user_id)

        past_events = []
        future_events = []
        pending_debits = []

        for e in all_events:
            e_date = e['event_date']
            s_date = e['settlement_date'] or e_date
            status = e['status']

            if status == 'pending':
                if e['direction'] == 'debit' and e['amount']:
                    pending_debits.append({
                        'event_id': e['event_id'],
                        'amount': e['amount'],
                        'date': s_date if s_date >= request_date else request_date,
                        'category': e['category'],
                        'description': e['description']
                    })
            elif status in ('settled', 'scheduled'):
                if s_date < request_date:
                    past_events.append(e)
                else:
                    future_events.append(e)

        salary_info = self._get_salary_info(user_id, past_events, future_events, facts, request_date)
        recurring_expenses = self._detect_recurring_expenses(user_id, past_events, facts, request_date)

        invoices = []
        for inv in facts.get('confirmed_invoices', []):
            if inv['date'] >= request_date:
                invoices.append(inv)

        return {
            'salary_info': salary_info,
            'pending_debits': pending_debits,
            'recurring_expenses': recurring_expenses,
            'confirmed_invoices': invoices
        }

    def _get_salary_info(self, user_id, past_events, future_events, facts, request_date):
        if facts.get('seasonal_ended'):
            return None

        # Check future scheduled salary in events
        for e in future_events:
            if e['direction'] == 'credit' and ('salary' in e['category'] or 'salary' in e['description'].lower() or 'payroll' in e['description'].lower()):
                amt = facts.get('salary_amount_override') or e['amount']
                date = facts.get('salary_date_override') or e['settlement_date']
                dt = datetime.strptime(date, '%Y-%m-%d')
                return {
                    'base_amount': amt,
                    'first_date': date,
                    'day_of_month': dt.day,
                    'arrears': facts.get('salary_arrears', 0.0)
                }

        # Check past salary events
        sal_events = [e for e in past_events if e['direction'] == 'credit' and ('salary' in e['category'] or 'payroll' in e['description'].lower())]
        if not sal_events:
            return None
        sal_events.sort(key=lambda x: x['settlement_date'])
        last_sal = sal_events[-1]

        # Check if final payroll
        if 'final' in last_sal['description'].lower():
            return None

        base_amt = facts.get('salary_amount_override') or last_sal['amount']
        first_date = facts.get('salary_date_override')

        # Find typical settlement day of month (mode of past salaries)
        doms = [datetime.strptime(e['settlement_date'], '%Y-%m-%d').day for e in sal_events]
        day_of_month = Counter(doms).most_common(1)[0][0]

        if not first_date:
            req_dt = datetime.strptime(request_date, '%Y-%m-%d')
            candidate_year = req_dt.year
            candidate_month = req_dt.month
            try:
                candidate_dt = datetime(candidate_year, candidate_month, day_of_month)
            except ValueError:
                candidate_dt = datetime(candidate_year, candidate_month, 28)
            if candidate_dt < req_dt:
                candidate_month += 1
                if candidate_month > 12:
                    candidate_month = 1
                    candidate_year += 1
                try:
                    candidate_dt = datetime(candidate_year, candidate_month, day_of_month)
                except ValueError:
                    candidate_dt = datetime(candidate_year, candidate_month, 28)
            first_date = candidate_dt.strftime('%Y-%m-%d')

        return {
            'base_amount': base_amt,
            'first_date': first_date,
            'day_of_month': day_of_month,
            'arrears': facts.get('salary_arrears', 0.0)
        }

    def _detect_recurring_expenses(self, user_id, past_events, facts, request_date):
        by_cat = defaultdict(list)
        for e in past_events:
            if e['direction'] == 'debit' and e['status'] == 'settled' and e['amount']:
                by_cat[e['category']].append(e)

        recurring = []
        rent_inc = facts.get('rent_increase_pct', 0.0)

        for cat, evs in by_cat.items():
            if len(evs) < 2:
                continue
            evs.sort(key=lambda x: x['settlement_date'])
            dates = [datetime.strptime(x['settlement_date'], '%Y-%m-%d') for x in evs]
            diffs = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            avg_diff = sum(diffs) / len(diffs) if diffs else 0
            last_ev = evs[-1]
            last_dt = dates[-1]

            # Monthly series
            if 25 <= avg_diff <= 35:
                # Mode day of month
                doms = [d.day for d in dates]
                day_of_month = Counter(doms).most_common(1)[0][0]
                amt = last_ev['amount']
                if cat == 'rent' and rent_inc > 0:
                    amt = amt * (1.0 + rent_inc / 100.0)

                flex = last_ev.get('flexibility', 'fixed')
                min_amt = last_ev.get('minimum_allowed_amount')

                recurring.append({
                    'category': cat,
                    'type': 'monthly',
                    'day_of_month': day_of_month,
                    'amount': amt,
                    'last_date': last_ev['settlement_date'],
                    'last_event_id': last_ev['event_id'],
                    'description': last_ev['description'],
                    'flexibility': flex,
                    'minimum_allowed_amount': min_amt
                })
            # Interval series
            elif avg_diff < 25:
                best_int = round(avg_diff)
                recent = evs[-4:]
                mean_amt = sum(x['amount'] for x in recent) / len(recent)

                flex = last_ev.get('flexibility', 'fixed')
                min_amt = last_ev.get('minimum_allowed_amount')

                recurring.append({
                    'category': cat,
                    'type': 'interval',
                    'interval_days': best_int,
                    'amount': mean_amt,
                    'last_date': last_ev['settlement_date'],
                    'last_event_id': last_ev['event_id'],
                    'description': last_ev['description'],
                    'flexibility': flex,
                    'minimum_allowed_amount': min_amt
                })

        return recurring

    def simulate(self, user_id: str, request_date: str, horizon_days: int = 90, 
                 spending_changes: Optional[List[str]] = None,
                 extra_payments: Optional[List[Tuple[str, float]]] = None) -> List[Tuple[str, float]]:
        
        profile = self.dl.profiles[user_id]
        starting_bal = profile['current_available_balance']
        analysis = self.analyze_user_series(user_id, request_date)
        
        spending_changes = spending_changes or []
        extra_payments = extra_payments or []
        
        stopped_events = set()
        reduced_events = {}
        for sc in spending_changes:
            parts = sc.split(':')
            if parts[0] == 'stop':
                stopped_events.add(parts[1])
            elif parts[0] == 'reduce_to':
                reduced_events[parts[1]] = float(parts[2])

        req_dt = datetime.strptime(request_date, '%Y-%m-%d')
        daily_cashflows = defaultdict(float)

        # 1. Extra payments
        for p_date, p_amt in extra_payments:
            daily_cashflows[p_date] -= p_amt

        # 2. Pending debits
        for pd in analysis['pending_debits']:
            daily_cashflows[pd['date']] -= pd['amount']

        # 3. Confirmed invoices from messages
        for inv in analysis['confirmed_invoices']:
            daily_cashflows[inv['date']] += inv['amount']

        # 4. Recurring salary
        sal = analysis['salary_info']
        if sal:
            first_dt = datetime.strptime(sal['first_date'], '%Y-%m-%d')
            first_amt = sal['base_amount'] + sal.get('arrears', 0.0)
            if 0 <= (first_dt - req_dt).days <= horizon_days:
                daily_cashflows[sal['first_date']] += first_amt
            
            curr_y = first_dt.year
            curr_m = first_dt.month
            for _ in range(4):
                curr_m += 1
                if curr_m > 12:
                    curr_m = 1
                    curr_y += 1
                try:
                    next_s_dt = datetime(curr_y, curr_m, sal['day_of_month'])
                except ValueError:
                    next_s_dt = datetime(curr_y, curr_m, 28)
                days_ahead = (next_s_dt - req_dt).days
                if 0 <= days_ahead <= horizon_days:
                    daily_cashflows[next_s_dt.strftime('%Y-%m-%d')] += sal['base_amount']

        # 5. Recurring expenses
        for re_exp in analysis['recurring_expenses']:
            e_id = re_exp['last_event_id']
            if e_id in stopped_events:
                continue
            amt = reduced_events.get(e_id, re_exp['amount'])
            
            if re_exp['type'] == 'monthly':
                dom = re_exp['day_of_month']
                curr_y = req_dt.year
                curr_m = req_dt.month
                for m_offset in range(4):
                    m = curr_m + m_offset
                    y = curr_y + (m - 1) // 12
                    m = (m - 1) % 12 + 1
                    try:
                        exp_dt = datetime(y, m, dom)
                    except ValueError:
                        exp_dt = datetime(y, m, 28)
                    days_ahead = (exp_dt - req_dt).days
                    if 0 <= days_ahead <= horizon_days:
                        daily_cashflows[exp_dt.strftime('%Y-%m-%d')] -= amt

            elif re_exp['type'] == 'interval':
                int_days = re_exp['interval_days']
                last_dt = datetime.strptime(re_exp['last_date'], '%Y-%m-%d')
                curr_dt = last_dt + timedelta(days=int_days)
                while (curr_dt - req_dt).days <= horizon_days:
                    if (curr_dt - req_dt).days >= 0:
                        daily_cashflows[curr_dt.strftime('%Y-%m-%d')] -= amt
                    curr_dt += timedelta(days=int_days)

        # Build daily trajectory
        trajectory = []
        cur_bal = starting_bal
        for day in range(horizon_days + 1):
            day_str = (req_dt + timedelta(days=day)).strftime('%Y-%m-%d')
            cur_bal += daily_cashflows[day_str]
            trajectory.append((day_str, cur_bal))

        return trajectory
