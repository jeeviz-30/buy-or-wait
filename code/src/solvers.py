from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from src.forecaster import Forecaster
from src.data_loader import DataLoader

class Solvers:
    def __init__(self, data_loader: DataLoader, forecaster: Forecaster):
        self.dl = data_loader
        self.fc = forecaster

    def calculate_amount_safe_to_pay(self, user_id: str, request_date: str, requested_amount: float) -> float:
        profile = self.dl.profiles[user_id]
        min_bal = profile['minimum_balance_to_keep']
        
        traj = self.fc.simulate(user_id, request_date, horizon_days=90)
        min_bal_traj = min(b for d, b in traj)
        
        safe = max(0.0, min(requested_amount, min_bal_traj - min_bal))
        if abs(safe - requested_amount) < 1e-4:
            return requested_amount
        return round(safe, 2)

    def find_earliest_date_for_full_payment(self, user_id: str, request_date: str, requested_amount: float) -> str:
        profile = self.dl.profiles[user_id]
        min_bal = profile['minimum_balance_to_keep']
        req_dt = datetime.strptime(request_date, '%Y-%m-%d')
        
        # 1. Check if safe today on request_date
        safe_today = self.calculate_amount_safe_to_pay(user_id, request_date, requested_amount)
        if abs(safe_today - requested_amount) < 1e-4:
            return request_date

        # 2. Check candidate dates in chronological order
        analysis = self.fc.analyze_user_series(user_id, request_date)
        salary_info = analysis.get('salary_info')
        
        candidate_dates = []
        if salary_info:
            first_s_dt = datetime.strptime(salary_info['first_date'], '%Y-%m-%d')
            for m_off in range(4):
                curr_y = first_s_dt.year
                curr_m = first_s_dt.month + m_off
                y = curr_y + (curr_m - 1) // 12
                m = (curr_m - 1) % 12 + 1
                try:
                    s_dt = datetime(y, m, salary_info['day_of_month'])
                except ValueError:
                    s_dt = datetime(y, m, 28)
                days_ahead = (s_dt - req_dt).days
                if 0 <= days_ahead <= 90:
                    candidate_dates.append(s_dt.strftime('%Y-%m-%d'))

        all_dates = set(candidate_dates)
        for d in range(1, 91):
            all_dates.add((req_dt + timedelta(days=d)).strftime('%Y-%m-%d'))
        
        sorted_candidates = sorted(list(all_dates))

        for cand_date in sorted_candidates:
            extra_pay = [(cand_date, requested_amount)]
            traj = self.fc.simulate(user_id, request_date, horizon_days=90, extra_payments=extra_pay)
            d_map = dict(traj)
            
            bal_on_date = d_map.get(cand_date, 0.0)
            if bal_on_date >= min_bal - 1e-4:
                # Check remaining horizon
                post_bals = [b for d, b in traj if d >= cand_date]
                # If post-payment min balance is above min_bal (or within small margin of discretionary buffer)
                if min(post_bals) >= min_bal - 1e-4:
                    return cand_date

        return ""

    def find_spending_changes_for_plan(self, user_id: str, request_date: str, 
                                       payments: List[Tuple[str, float]]) -> Tuple[bool, List[str]]:
        profile = self.dl.profiles[user_id]
        min_bal = profile['minimum_balance_to_keep']
        req_dt = datetime.strptime(request_date, '%Y-%m-%d')
        
        last_pay_dt = max(datetime.strptime(d, '%Y-%m-%d') for d, _ in payments)
        plan_days = 90
        
        # 1. Test without changes
        traj = self.fc.simulate(user_id, request_date, horizon_days=plan_days, extra_payments=payments)
        if min(b for d, b in traj) >= min_bal - 1e-4:
            return True, []

        # 2. Get adjustable recurring expenses
        analysis = self.fc.analyze_user_series(user_id, request_date)
        recurring = analysis['recurring_expenses']
        
        willing_stop = profile['expense_categories_user_is_willing_to_stop']
        willing_reduce = profile['expense_categories_user_is_willing_to_reduce']

        candidate_actions = []
        for re_exp in recurring:
            cat = re_exp['category']
            e_id = re_exp['last_event_id']
            flex = re_exp['flexibility']
            amt = re_exp['amount']
            min_allowed = re_exp.get('minimum_allowed_amount')

            # Can stop?
            if cat in willing_stop and flex in ('stoppable', 'reducible_or_stoppable'):
                candidate_actions.append(('stop', e_id, amt, f"stop:{e_id}"))

            # Can reduce?
            if cat in willing_reduce and flex in ('reducible', 'reducible_or_stoppable') and min_allowed is not None:
                if min_allowed < amt:
                    saving = amt - min_allowed
                    min_str = f"{min_allowed:.2f}".rstrip('0').rstrip('.')
                    candidate_actions.append(('reduce', e_id, saving, f"reduce_to:{e_id}:{min_str}"))

        # Test single changes
        for act in sorted(candidate_actions, key=lambda x: -x[2]):
            changes = [act[3]]
            traj = self.fc.simulate(user_id, request_date, horizon_days=plan_days, 
                                    spending_changes=changes, extra_payments=payments)
            if min(b for d, b in traj) >= min_bal - 1e-4:
                return True, changes

        # Test combinations of 2 changes
        for i in range(len(candidate_actions)):
            for j in range(i + 1, len(candidate_actions)):
                a1 = candidate_actions[i]
                a2 = candidate_actions[j]
                if a1[1] == a2[1]:
                    continue
                changes = [a1[3], a2[3]]
                traj = self.fc.simulate(user_id, request_date, horizon_days=plan_days, 
                                        spending_changes=changes, extra_payments=payments)
                if min(b for d, b in traj) >= min_bal - 1e-4:
                    return True, changes

        # Test combinations of 3 changes
        for i in range(len(candidate_actions)):
            for j in range(i + 1, len(candidate_actions)):
                for k in range(j + 1, len(candidate_actions)):
                    a1 = candidate_actions[i]
                    a2 = candidate_actions[j]
                    a3 = candidate_actions[k]
                    if len({a1[1], a2[1], a3[1]}) < 3:
                        continue
                    changes = [a1[3], a2[3], a3[3]]
                    traj = self.fc.simulate(user_id, request_date, horizon_days=plan_days, 
                                            spending_changes=changes, extra_payments=payments)
                    if min(b for d, b in traj) >= min_bal - 1e-4:
                        return True, changes

        return False, []
